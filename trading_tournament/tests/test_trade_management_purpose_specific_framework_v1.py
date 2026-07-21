from __future__ import annotations

import json
import sys

import pandas as pd
import pytest

from src.backtester import Backtester
from src.overlays import (
    AssetExposureCapOverlay,
    GrossExposureCapOverlay,
    GroupExposureCapOverlay,
    IdentityOverlay,
    MinimumNotionalOverlay,
    RebalanceBandOverlay,
    WeightChangeBandOverlay,
)
from src.portfolio import Portfolio, Position
from src.strategies import EntrySignal, ExitSignal
from src.trade_management_governance import (
    MANAGEMENT_ROLE_OPTIONAL_OVERLAY,
    classify_cap_effect,
    compatibility_contains_performance_fields,
    default_optional_management_count,
    default_optional_overlay_candidate_ids,
    generate_compatibility_matrix,
    implemented_strategy_records,
    validate_management_experiment_plan,
)


def _project_config() -> dict:
    return {
        "starting_equity": 3000.0,
        "hard_stop_equity": 1000.0,
        "project_stop": {"mode": "absolute_floor", "absolute_floor_equity": 1000.0},
        "target_profit_1": 300.0,
        "target_profit_2": 400.0,
        "max_daily_loss": 900.0,
        "max_weekly_loss": 1800.0,
        "max_open_risk": 1000.0,
        "max_cluster_open_risk": 1000.0,
        "max_position_notional_pct": 1.0,
        "reserve_cash_buffer": 0.0,
        "warmup_days": 0,
    }


def _config(strategy: str = "N2_absolute_trend_taa") -> dict:
    return {
        "project": _project_config(),
        "universe": {
            "symbols": ["SPY", "QQQ", "IWM", "BIL"],
            "clusters": {"equity_index": ["SPY", "QQQ", "IWM"], "cash": ["BIL"]},
        },
        "strategy_order": [strategy],
        "strategies": {
            strategy: {
                "enabled": True,
                "allocation": 3000.0,
                "max_strategy_loss": 999.0,
                "risk_per_trade": 30.0,
                "max_positions": 5,
                "max_asset_weight": 0.50,
                "initial_atr_multiple": 2.0,
                "trailing_atr_multiple": 2.5,
            }
        },
        "benchmarks": {"spy": "SPY", "cash_proxy": "BIL", "initial_value": 3000.0},
    }


def _daily_config() -> dict:
    return {
        "project": _project_config(),
        "universe": {"symbols": ["SPY"], "clusters": {"equity_index": ["SPY"]}},
        "strategy_order": ["D_mean_reversion"],
        "strategies": {
            "D_mean_reversion": {
                "enabled": True,
                "allocation": 3000.0,
                "max_strategy_loss": 999.0,
                "risk_per_trade": 30.0,
                "max_positions": 3,
                "max_holding_days": 20,
                "initial_atr_multiple": 1.5,
            }
        },
        "benchmarks": {"spy": "SPY", "cash_proxy": "BIL", "initial_value": 3000.0},
    }


def _synthetic_d_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * 10,
            "high": [102.0] * 10,
            "low": [99.0] * 10,
            "close": [100.0, 99.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0],
            "adj_close": [100.0, 99.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0],
            "volume": [1000] * 10,
            "sma_5": [99.0] * 10,
            "sma_50": [90.0] * 10,
            "sma_100": [90.0] * 10,
            "sma_200": [90.0] * 10,
            "ema_10": [100.0] * 10,
            "atr_20": [1.0] * 10,
            "atr_10": [1.0] * 10,
            "rsi_2": [5.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
            "bb_lower": [90.0] * 10,
            "bb_upper": [110.0] * 10,
            "rv_20": [0.1] * 10,
            "ret_63": [0.1] * 10,
            "ret_126": [0.1] * 10,
            "ret_252": [0.1] * 10,
            "high_20": [99.0] * 10,
            "avg_volume_20": [1000.0] * 10,
            "atr_10_percentile": [0.2] * 10,
            "market_regime": ["bull_normal_volatility"] * 10,
        }
    )
    return {"SPY": df}


def _bind(overlay, strategy: str = "N2_absolute_trend_taa") -> None:
    overlay.bind(
        run_id="unit",
        base_strategy_id=strategy,
        base_strategy_hash="hash",
        data={},
        indexed_data={},
        calendar=[],
        config=_config(strategy),
    )


def _target_signal(symbol: str, weight: float) -> EntrySignal:
    return EntrySignal(
        date=pd.Timestamp("2020-01-31"),
        strategy="N2_absolute_trend_taa",
        symbol=symbol,
        requested_risk=1.0,
        metadata={"target_weight": weight, "atr": 1.0},
    )


def _position(shares: float = 5.0, bars_held: int = 5) -> Position:
    return Position(
        trade_id=1,
        strategy="N2_absolute_trend_taa",
        symbol="SPY",
        entry_date=pd.Timestamp("2020-01-02"),
        entry_price=100.0,
        stop_price=90.0,
        target_price=None,
        shares=shares,
        risk_amount=10.0,
        requested_risk=10.0,
        market_regime_at_entry="bull_normal_volatility",
        bars_held=bars_held,
    )


def _portfolio(position: Position | None = None) -> Portfolio:
    portfolio = Portfolio(_config("N2_absolute_trend_taa"), 0.0)
    if position is not None:
        portfolio.positions.append(position)
    return portfolio


def _monthly_exit(pos: Position) -> ExitSignal:
    return ExitSignal(
        date=pd.Timestamp("2020-01-31"),
        strategy=pos.strategy,
        symbol=pos.symbol,
        trade_id=pos.trade_id,
        reason="monthly_rebalance_exit",
    )


def _base_plan(**updates) -> dict:
    plan = {
        "experiment_id": "tm-plan-1",
        "base_strategy_id": "N2_absolute_trend_taa",
        "base_strategy_hash": "hash",
        "base_stage": "source_exact_base_passed",
        "source_management_included": False,
        "diagnosed_weakness": "EXCESS_SMALL_ORDERS",
        "weakness_evidence_reference": "reports/example/order_diagnostics.csv",
        "selected_overlay_id": "OVL-ORD-MIN-NOTIONAL-V1",
        "overlay_purpose_id": "execution_efficiency",
        "compatibility_reason": "target_weight intent and order-size weakness",
        "negative_or_attribution_control": "STATIC-LOWER-EXPOSURE-CONTROL",
        "parameters": {"min_nav_order_pct": 0.001},
        "adaptation_label": "optional_management_overlay",
        "research_stage": "research_sample",
        "authorized_overlay_count": 1,
        "base_intent_kind": "target_weight",
        "available_data": ("target_weights", "portfolio_nav", "current_positions", "close"),
        "base_lifecycle_features": (),
        "optional_overlay_ids": ("OVL-ORD-MIN-NOTIONAL-V1",),
        "management_role": MANAGEMENT_ROLE_OPTIONAL_OVERLAY,
    }
    plan.update(updates)
    return plan


def test_weight_band_primitive_does_not_apply_minimum_notional_logic() -> None:
    overlay = WeightChangeBandOverlay(min_weight_delta=0.0)
    _bind(overlay)

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.0001)],
        exits=[],
        portfolio=_portfolio(),
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert len(batch.entries) == 1
    assert "below_nav_order" not in set(overlay.events_frame()["reason_code"])


def test_minimum_notional_primitive_does_not_apply_target_weight_logic() -> None:
    overlay = MinimumNotionalOverlay(min_nav_order_pct=0.0)
    _bind(overlay)
    pos = _position(shares=5.0)

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.505)],
        exits=[_monthly_exit(pos)],
        portfolio=_portfolio(pos),
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert len(batch.entries) == 1
    assert len(batch.exits) == 1
    assert "below_weight_band" not in set(overlay.events_frame()["reason_code"])


def test_legacy_rebalance_wrapper_reproduces_historical_combined_behavior() -> None:
    pos = _position(shares=5.0)
    row = {"SPY": pd.Series({"close": 100.0})}

    legacy = RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)
    weight = WeightChangeBandOverlay(min_weight_delta=0.01)
    for overlay in (legacy, weight):
        _bind(overlay)
        batch = overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[_target_signal("SPY", 0.505)],
            exits=[_monthly_exit(pos)],
            portfolio=_portfolio(pos),
            rows=row,
            equity=1000.0,
            pending_exit_ids=set(),
        )
        assert batch.entries == []
        assert batch.exits == []

    legacy_nav = RebalanceBandOverlay(min_weight_delta=0.0, min_nav_order_pct=0.001)
    min_notional = MinimumNotionalOverlay(min_nav_order_pct=0.001)
    for overlay in (legacy_nav, min_notional):
        _bind(overlay)
        batch = overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[_target_signal("QQQ", 0.0009)],
            exits=[],
            portfolio=_portfolio(),
            rows={},
            equity=1000.0,
            pending_exit_ids=set(),
        )
        assert batch.entries == []


def test_weight_band_cannot_suppress_genuine_liquidation_or_risk_exit() -> None:
    overlay = WeightChangeBandOverlay(min_weight_delta=0.01)
    _bind(overlay)
    pos = _position(shares=5.0)
    risk_exit = ExitSignal(
        date=pd.Timestamp("2020-01-31"),
        strategy=pos.strategy,
        symbol=pos.symbol,
        trade_id=pos.trade_id,
        reason="strategy_loss_budget_hit",
    )

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.505)],
        exits=[_monthly_exit(pos), risk_exit],
        portfolio=_portfolio(pos),
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert batch.entries == []
    assert batch.exits == [risk_exit]


def test_minimum_notional_residual_liquidation_policy_is_explicit() -> None:
    overlay = MinimumNotionalOverlay(min_nav_order_pct=0.001)
    _bind(overlay)
    residual = _position(shares=0.005)

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[],
        exits=[_monthly_exit(residual)],
        portfolio=_portfolio(residual),
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert batch.exits == []
    flags = json.loads(overlay.events_frame().iloc[-1]["data_quality_flags"])
    assert flags["small_residual_liquidation"] is True
    assert "residual_liquidation_policy" in flags

    risk_exit = ExitSignal(
        date=pd.Timestamp("2020-01-31"),
        strategy=residual.strategy,
        symbol=residual.symbol,
        trade_id=residual.trade_id,
        reason="strategy_loss_budget_hit",
    )
    risk_batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-02-03"),
        entries=[],
        exits=[risk_exit],
        portfolio=_portfolio(residual),
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert risk_batch.exits == [risk_exit]


def test_gross_asset_and_group_caps_operate_independently() -> None:
    gross = GrossExposureCapOverlay(max_gross_exposure=1.0)
    asset = AssetExposureCapOverlay(per_asset_cap=0.35)
    group = GroupExposureCapOverlay(group_caps={"equity_index": 0.50})
    entries = [_target_signal("SPY", 0.80), _target_signal("QQQ", 0.70)]

    _bind(gross)
    gross_batch = gross.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=entries,
        exits=[],
        portfolio=_portfolio(),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    gross_targets = {entry.symbol: entry.metadata["target_weight"] for entry in gross_batch.entries}
    assert sum(gross_targets.values()) == pytest.approx(1.0)
    assert gross_targets["SPY"] > 0.35

    _bind(asset)
    asset_batch = asset.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=entries,
        exits=[],
        portfolio=_portfolio(),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert {entry.symbol: entry.metadata["target_weight"] for entry in asset_batch.entries} == pytest.approx(
        {"SPY": 0.35, "QQQ": 0.35}
    )

    _bind(group)
    group_batch = group.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=entries,
        exits=[],
        portfolio=_portfolio(),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert {entry.symbol: entry.metadata["target_weight"] for entry in group_batch.entries} == pytest.approx(
        {"SPY": 0.2666666667, "QQQ": 0.2333333333}
    )
    assert set(gross.events_frame()["reason_code"]) == {"overlay_initialized", "gross_exposure_cap"}
    assert set(asset.events_frame()["reason_code"]) == {"overlay_initialized", "asset_exposure_cap"}
    assert set(group.events_frame()["reason_code"]) == {"overlay_initialized", "group_exposure_cap"}


def test_no_effect_cap_classification() -> None:
    overlay = GrossExposureCapOverlay(max_gross_exposure=2.0)
    _bind(overlay)
    overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.25)],
        exits=[],
        portfolio=_portfolio(),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert classify_cap_effect(overlay.events_frame()) == "APPLICABLE_NO_EFFECT"


def test_optional_overlay_count_defaults_to_zero() -> None:
    assert default_optional_management_count() == 0
    assert default_optional_overlay_candidate_ids() == ()


def test_one_compatible_overlay_can_be_authorized() -> None:
    result = validate_management_experiment_plan(_base_plan())

    assert result.authorized is True
    assert result.failure_codes == ()


def test_more_than_one_optional_overlay_fails_closed() -> None:
    result = validate_management_experiment_plan(
        _base_plan(
            authorized_overlay_count=2,
            optional_overlay_ids=("OVL-ORD-MIN-NOTIONAL-V1", "OVL-RISK-GROSS-CAP-V1"),
        )
    )

    assert result.authorized is False
    assert "MULTIPLE_OPTIONAL_OVERLAYS_NOT_AUTHORIZED" in result.failure_codes


def test_legacy_composite_cannot_be_used_for_new_research() -> None:
    result = validate_management_experiment_plan(
        _base_plan(
            selected_overlay_id="OVL-ORD-001",
            optional_overlay_ids=("OVL-ORD-001",),
            parameters={"min_weight_delta": 0.01, "min_nav_order_pct": 0.001},
        )
    )

    assert result.authorized is False
    assert "LEGACY_COMPOSITE_NEW_RESEARCH_FORBIDDEN" in result.failure_codes


def test_holistic_source_system_cannot_be_combined_with_another_overlay() -> None:
    result = validate_management_experiment_plan(
        _base_plan(
            diagnosed_weakness="SOURCE_DEFINED_MANAGEMENT_REPLICATION",
            selected_overlay_id="OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",
            overlay_purpose_id="complete_portfolio_insurance",
            authorized_overlay_count=2,
            optional_overlay_ids=("OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1", "OVL-RISK-GROSS-CAP-V1"),
            available_data=("target_weights", "portfolio_nav", "month_end_calendar", "safe_asset_mapping"),
        )
    )

    assert result.authorized is False
    assert "HOLISTIC_SYSTEM_COMBINATION_NOT_AUTHORIZED" in result.failure_codes


def test_missing_diagnosed_weakness_fails_closed() -> None:
    result = validate_management_experiment_plan(_base_plan(diagnosed_weakness=""))

    assert result.authorized is False
    assert "NO_DIAGNOSED_MANAGEMENT_NEED" in result.failure_codes


def test_purpose_mismatch_fails_closed() -> None:
    result = validate_management_experiment_plan(_base_plan(diagnosed_weakness="EXCESS_GROSS_EXPOSURE"))

    assert result.authorized is False
    assert "OVERLAY_PURPOSE_MISMATCH" in result.failure_codes


def test_source_defined_base_management_is_not_double_counted_as_optional_overlay() -> None:
    result = validate_management_experiment_plan(
        _base_plan(
            source_management_included=True,
            diagnosed_weakness="SOURCE_DEFINED_MANAGEMENT_REPLICATION",
            selected_overlay_id="OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",
            overlay_purpose_id="complete_portfolio_insurance",
            optional_overlay_ids=("OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",),
            available_data=("target_weights", "portfolio_nav", "month_end_calendar", "safe_asset_mapping"),
        )
    )

    assert result.authorized is False
    assert "CONFLICTING_BASE_LIFECYCLE" in result.failure_codes


def test_compatibility_report_contains_no_performance_fields() -> None:
    matrix = generate_compatibility_matrix(implemented_strategy_records(_config()))

    assert matrix
    assert set(matrix[0]) == {
        "strategy_id",
        "strategy_family",
        "intent_kind",
        "source_defined_lifecycle_features",
        "overlay_id",
        "purpose",
        "intent_compatibility",
        "lifecycle_compatibility",
        "data_compatibility",
        "final_applicability",
        "reason_code",
    }
    assert compatibility_contains_performance_fields(matrix) is False


def test_identity_equivalence_remains_unchanged() -> None:
    data = _synthetic_d_data()
    cfg = _daily_config()
    base = Backtester(data, cfg).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)
    identity = Backtester(data, cfg).run(
        "identity",
        "2020-01-01",
        "2020-01-20",
        0.0,
        lightweight_outputs=True,
        overlay=IdentityOverlay(),
        run_id="identity-framework-v1",
    )

    pd.testing.assert_frame_equal(base.equity_curve, identity.equity_curve)
    pd.testing.assert_frame_equal(base.trades, identity.trades)


def test_no_live_broker_module_imported_or_invoked_by_governance_path() -> None:
    before = {name for name in sys.modules if name.startswith("execution_lab")}
    validate_management_experiment_plan(_base_plan())
    generate_compatibility_matrix(implemented_strategy_records(_config()))
    after = {name for name in sys.modules if name.startswith("execution_lab")}

    assert after == before
