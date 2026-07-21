from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from run_trade_management_overlay_comparison import _strategy_only_config, _strategy_source_hash, summarize_result
from run_trade_management_overlay_canonical_exploratory import json_ready, markdown_table, result_hashes
from src.backtester import Backtester, BacktestResult
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.overlays import (
    IdentityOverlay,
    RebalanceBandOverlay,
    TimeStopOverlay,
    TradeManagementOverlay,
    WideATRCatastrophicStopOverlay,
    stable_hash,
)
from src.utils import config_hash, git_commit_hash, load_config, write_json


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "family_portability_batch_v1"
CANONICAL_SOURCE = ROOT / "reports" / "trade_management" / "codex_overlay_v1_canonical_exploratory"
REQUESTED_RANGE = {"start": "2017-01-01", "end": "2020-12-31"}
SLIPPAGES = [0.0, 0.0005, 0.001]
LABEL = "family_portability_test;research_only_exploratory"

CLASS_MECHANICAL_CONTROL = "MECHANICAL_CONTROL"
CLASS_APPLICABLE_EFFECTIVE = "APPLICABLE_EFFECTIVE"
CLASS_APPLICABLE_NO_EFFECT = "APPLICABLE_NO_EFFECT"
CLASS_NOT_APPLICABLE_INTENT_UNIT = "NOT_APPLICABLE_INTENT_UNIT"
CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE = "NOT_APPLICABLE_STRATEGY_LIFECYCLE"
CLASS_FAILED = "FAILED"

OVERLAY_CONFIGS = {
    "IDENTITY": {},
    "OVL-ORD-001": {"min_weight_delta": 0.01, "min_nav_order_pct": 0.001},
    "OVL-EXT-001": {"max_completed_bars": 5},
    "OVL-STP-001": {
        "atr_lookback": 20,
        "atr_multiple": 4.0,
        "fixed_at_entry": True,
        "trailing": False,
        "active_beginning_after_entry": True,
        "base_lifecycle_precedence": True,
    },
}

STRATEGY_META = {
    "A_ETF_sector_momentum": {
        "family_id": "cross_sectional_sector_momentum",
        "strategy_frequency": "weekly_periodic",
        "intent_kind": "risk_amount_dollars",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "top_2_ranked_etfs",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"rebalance_band": 1},
    },
    "B_ETF_trend_following": {
        "family_id": "daily_trend_following_anchor",
        "strategy_frequency": "daily",
        "intent_kind": "risk_amount_dollars",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "up_to_5_ranked_breakouts",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"time_stop": 99},
    },
    "C_swing_trend_pullback": {
        "family_id": "daily_swing_pullback_reversal",
        "strategy_frequency": "daily",
        "intent_kind": "risk_amount_dollars",
        "base_stop_present": True,
        "base_target_present": True,
        "base_trailing_present": False,
        "base_time_exit_present": True,
        "base_time_exit_bars": 20,
        "simultaneous_position_design": "up_to_6_ranked_pullbacks_engine_capped_by_config",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"time_stop": 3},
    },
    "D_mean_reversion": {
        "family_id": "daily_mean_reversion",
        "strategy_frequency": "daily",
        "intent_kind": "risk_amount_dollars",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": False,
        "base_time_exit_present": True,
        "base_time_exit_bars": 5,
        "simultaneous_position_design": "up_to_5_ranked_oversold_etfs",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"time_stop": 1},
    },
    "E_breakout_vcb": {
        "family_id": "daily_breakout_vcb_negative_control",
        "strategy_frequency": "daily",
        "intent_kind": "risk_amount_dollars",
        "base_stop_present": True,
        "base_target_present": True,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "up_to_5_volume_confirmed_breakouts_engine_capped_by_config",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"time_stop": 4, "atr_stop": 1},
    },
    "N1_dual_momentum_taa": {
        "family_id": "cross_asset_dual_momentum_taa",
        "strategy_frequency": "monthly_periodic",
        "intent_kind": "target_weight",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "top_2_risk_assets_plus_defensive_fill",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"rebalance_band": 2},
    },
    "N2_absolute_trend_taa": {
        "family_id": "absolute_trend_taa_anchor",
        "strategy_frequency": "monthly_periodic",
        "intent_kind": "target_weight",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "top_3_absolute_trend_assets_plus_defensive_fill",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"rebalance_band": 3},
    },
    "N3_dual_momentum_vol_scaled": {
        "family_id": "cross_asset_dual_momentum_vol_scaled_taa",
        "strategy_frequency": "monthly_periodic",
        "intent_kind": "target_weight",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "top_2_risk_assets_vol_scaled_plus_defensive_fill",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"rebalance_band": 4},
    },
    "N4_inverse_vol_defensive_allocation": {
        "family_id": "inverse_vol_defensive_allocation",
        "strategy_frequency": "monthly_periodic",
        "intent_kind": "target_weight",
        "base_stop_present": True,
        "base_target_present": False,
        "base_trailing_present": True,
        "base_time_exit_present": False,
        "simultaneous_position_design": "inverse_volatility_weighted_defensive_assets",
        "source_rule_status": "complete_source_rules",
        "family_preference": {"rebalance_band": 3},
    },
    "F_opening_range_breakout": {
        "family_id": "intraday_opening_range_breakout",
        "strategy_frequency": "intraday_shadow",
        "intent_kind": "unknown",
        "base_stop_present": False,
        "base_target_present": False,
        "base_trailing_present": False,
        "base_time_exit_present": False,
        "simultaneous_position_design": "shadow_only",
        "source_rule_status": "incomplete_source_rules",
        "family_preference": {},
    },
    "G_event_driven_momentum": {
        "family_id": "event_driven_momentum",
        "strategy_frequency": "event_shadow",
        "intent_kind": "unknown",
        "base_stop_present": False,
        "base_target_present": False,
        "base_trailing_present": False,
        "base_time_exit_present": False,
        "simultaneous_position_design": "shadow_only",
        "source_rule_status": "incomplete_source_rules",
        "family_preference": {},
    },
}


def strategy_symbols(config: dict[str, Any], strategy_id: str) -> list[str]:
    cfg = config.get("strategies", {}).get(strategy_id, {})
    symbols: set[str] = set()
    for key in ["assets", "risk_assets", "defensive_assets", "risk_off_allowed_assets"]:
        symbols.update(cfg.get(key, []) or [])
    if not symbols and strategy_id in {"A_ETF_sector_momentum", "B_ETF_trend_following", "C_swing_trend_pullback", "D_mean_reversion", "E_breakout_vcb"}:
        symbols.update(config.get("universe", {}).get("symbols", []))
    return sorted(symbols)


def data_status_for(symbols: list[str], data: dict[str, pd.DataFrame]) -> str:
    missing = [symbol for symbol in symbols if symbol not in data or data[symbol].empty]
    return "available_existing_cache" if not missing else "missing_required_data:" + ",".join(missing)


def eligible_overlays_for(strategy_id: str, meta: dict[str, Any]) -> list[str]:
    overlays: list[str] = []
    if (
        meta["intent_kind"] == "target_weight"
        and "periodic" in meta["strategy_frequency"]
        and strategy_id != "N2_absolute_trend_taa"
        and meta["source_rule_status"] == "complete_source_rules"
    ):
        overlays.append("OVL-ORD-001")
    if (
        meta["strategy_frequency"] == "daily"
        and strategy_id != "B_ETF_trend_following"
        and meta["source_rule_status"] == "complete_source_rules"
        and int(meta.get("base_time_exit_bars", 9999)) > 5
    ):
        overlays.append("OVL-EXT-001")
    if (
        meta["strategy_frequency"] == "daily"
        and not meta["base_stop_present"]
        and not meta["base_target_present"]
        and not meta["base_trailing_present"]
        and meta["source_rule_status"] == "complete_source_rules"
    ):
        overlays.append("OVL-STP-001")
    return overlays


def ineligibility_reason(strategy_id: str, meta: dict[str, Any], overlays: list[str], data_status: str) -> str:
    if overlays:
        return ""
    reasons: list[str] = []
    if meta["source_rule_status"] != "complete_source_rules":
        reasons.append("INCOMPLETE_SOURCE_RULES")
    if data_status.startswith("missing"):
        reasons.append("MISSING_REQUIRED_DATA")
    if strategy_id == "N2_absolute_trend_taa":
        reasons.append("ANCHOR_ONLY_NOT_NEW_CANDIDATE")
    if strategy_id == "B_ETF_trend_following":
        reasons.append("ANCHOR_ONLY_NOT_NEW_CANDIDATE")
    if meta["intent_kind"] != "target_weight" and "periodic" in meta["strategy_frequency"]:
        reasons.append("UNSUPPORTED_INTENT_UNIT")
    if meta["strategy_frequency"] == "daily" and int(meta.get("base_time_exit_bars", 9999)) <= 5:
        reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_TIME_EXIT")
    if meta["base_stop_present"]:
        reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_STOP")
    if not overlays and not reasons:
        reasons.append("NOT_APPLICABLE")
    return ";".join(dict.fromkeys(reasons))


def overlay_ineligibility_reason(row: pd.Series, overlay_id: str) -> str:
    strategy_id = str(row["strategy_id"])
    meta = STRATEGY_META[strategy_id]
    reasons: list[str] = []
    if meta["source_rule_status"] != "complete_source_rules":
        reasons.append("INCOMPLETE_SOURCE_RULES")
    if str(row["data_status"]).startswith("missing"):
        reasons.append("MISSING_REQUIRED_DATA")

    if overlay_id == "OVL-ORD-001":
        if strategy_id == "N2_absolute_trend_taa":
            reasons.append("ANCHOR_ONLY_NOT_NEW_CANDIDATE")
        if meta["intent_kind"] != "target_weight":
            reasons.append("UNSUPPORTED_INTENT_UNIT")
        if "periodic" not in meta["strategy_frequency"]:
            reasons.append("NOT_PERIODIC_REBALANCE_STRATEGY")
    elif overlay_id == "OVL-EXT-001":
        if strategy_id == "B_ETF_trend_following":
            reasons.append("ANCHOR_ONLY_NOT_NEW_CANDIDATE")
        if meta["strategy_frequency"] != "daily":
            reasons.append("NOT_DAILY_BAR_STRATEGY")
        if int(meta.get("base_time_exit_bars", 9999)) <= 5:
            reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_TIME_EXIT_5_OR_SHORTER")
    elif overlay_id == "OVL-STP-001":
        if meta["strategy_frequency"] != "daily":
            reasons.append("NOT_DAILY_DIRECTIONAL_STRATEGY")
        if meta["base_stop_present"]:
            reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_STOP")
        if meta["base_target_present"]:
            reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_TARGET")
        if meta["base_trailing_present"]:
            reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_TRAILING_STOP")
        if meta["base_time_exit_present"]:
            reasons.append("BASE_LIFECYCLE_ALREADY_CONTAINS_TIME_EXIT")
    else:
        reasons.append("UNSUPPORTED_OVERLAY_ID")

    return ";".join(dict.fromkeys(reasons)) or "NOT_SELECTED_BY_DETERMINISTIC_ORDER"


def build_inventory(config: dict[str, Any], data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for strategy_id, meta in STRATEGY_META.items():
        symbols = strategy_symbols(config, strategy_id)
        data_status = data_status_for(symbols, data) if symbols else "not_required_or_shadow_unknown"
        overlays = eligible_overlays_for(strategy_id, meta)
        rows.append(
            {
                "strategy_id": strategy_id,
                "family_id": meta["family_id"],
                "strategy_frequency": meta["strategy_frequency"],
                "intent_kind": meta["intent_kind"],
                "base_stop_present": meta["base_stop_present"],
                "base_target_present": meta["base_target_present"],
                "base_trailing_present": meta["base_trailing_present"],
                "base_time_exit_present": meta["base_time_exit_present"],
                "simultaneous_position_design": meta["simultaneous_position_design"],
                "data_status": data_status,
                "source_rule_status": meta["source_rule_status"],
                "base_reproducibility_status": (
                    "existing_backtester_config_reproducible"
                    if strategy_id in config.get("strategies", {}) and meta["source_rule_status"] == "complete_source_rules"
                    else "not_reproducible_in_current_backtester"
                ),
                "eligible_overlays": ",".join(overlays),
                "ineligibility_reason": ineligibility_reason(strategy_id, meta, overlays, data_status),
                "existing_frozen_research_range": f"{REQUESTED_RANGE['start']}:{REQUESTED_RANGE['end']}",
                "selection_key": stable_hash(
                    {
                        "strategy_id": strategy_id,
                        "family_id": meta["family_id"],
                        "frequency": meta["strategy_frequency"],
                        "intent": meta["intent_kind"],
                    }
                )[:16],
            }
        )
    return pd.DataFrame(rows)


def select_candidates(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    rebalance_candidates = inventory[inventory["eligible_overlays"].str.contains("OVL-ORD-001", na=False)].copy()
    rebalance_candidates["preference_rank"] = rebalance_candidates["strategy_id"].map(
        lambda sid: STRATEGY_META[sid]["family_preference"].get("rebalance_band", 99)
    )
    rebalance_candidates = rebalance_candidates.sort_values(
        ["preference_rank", "source_rule_status", "data_status", "strategy_id"],
        ascending=[True, True, True, True],
    )
    for order, (_, row) in enumerate(rebalance_candidates.head(3).iterrows(), start=1):
        selected.append(selection_row(row, "OVL-ORD-001", "rebalance_band", order, "periodic target-weight family"))
    for _, row in inventory.iterrows():
        if row["strategy_id"] not in set(rebalance_candidates.head(3)["strategy_id"]):
            reason = overlay_ineligibility_reason(row, "OVL-ORD-001")
            if row["strategy_id"] in set(rebalance_candidates["strategy_id"]) and row["strategy_id"] not in set(rebalance_candidates.head(3)["strategy_id"]):
                reason = "NOT_SELECTED_BY_DETERMINISTIC_ORDER"
            excluded.append(exclusion_row(row, "OVL-ORD-001", reason))

    time_candidates = inventory[inventory["eligible_overlays"].str.contains("OVL-EXT-001", na=False)].copy()
    time_candidates["preference_rank"] = time_candidates["strategy_id"].map(
        lambda sid: STRATEGY_META[sid]["family_preference"].get("time_stop", 99)
    )
    time_candidates = time_candidates.sort_values(
        ["preference_rank", "source_rule_status", "data_status", "strategy_id"],
        ascending=[True, True, True, True],
    )
    # Breakout remains a negative control only if no mean-reversion, gap, or short-duration reversal candidate exists.
    non_breakout = time_candidates[time_candidates["family_id"] != "daily_breakout_vcb_negative_control"]
    chosen_time = non_breakout.head(2) if not non_breakout.empty else time_candidates.head(2)
    for order, (_, row) in enumerate(chosen_time.iterrows(), start=1):
        selected.append(selection_row(row, "OVL-EXT-001", "time_stop", order, "daily lifecycle family"))
    for _, row in inventory.iterrows():
        if row["strategy_id"] not in set(chosen_time["strategy_id"]):
            reason = overlay_ineligibility_reason(row, "OVL-EXT-001")
            if row["strategy_id"] == "E_breakout_vcb" and not non_breakout.empty:
                reason = "NEGATIVE_CONTROL_NOT_USED_HIGHER_PRIORITY_ELIGIBLE"
            excluded.append(exclusion_row(row, "OVL-EXT-001", reason))

    atr_candidates = inventory[inventory["eligible_overlays"].str.contains("OVL-STP-001", na=False)].copy()
    if atr_candidates.empty:
        excluded.append(
            {
                "strategy_id": "",
                "family_id": "",
                "overlay_id": "OVL-STP-001",
                "trial_name": "wide_atr_catastrophic_stop",
                "exclusion_code": "NO_ELIGIBLE_BASE_WITHOUT_EXISTING_LIFECYCLE_EXIT",
                "reason": "No implemented daily directional strategy lacks base stop, target, and trailing lifecycle exits.",
            }
        )
    else:
        atr_candidates["preference_rank"] = atr_candidates["strategy_id"].map(
            lambda sid: STRATEGY_META[sid]["family_preference"].get("atr_stop", 99)
        )
        atr_candidates = atr_candidates.sort_values(["preference_rank", "strategy_id"])
        row = atr_candidates.iloc[0]
        selected.append(selection_row(row, "OVL-STP-001", "wide_atr_catastrophic_stop", 1, "daily no-base-lifecycle-exit family"))
    for _, row in inventory.iterrows():
        if "OVL-STP-001" not in str(row["eligible_overlays"]).split(","):
            excluded.append(exclusion_row(row, "OVL-STP-001", overlay_ineligibility_reason(row, "OVL-STP-001")))

    return pd.DataFrame(selected), pd.DataFrame(excluded).drop_duplicates(), pd.DataFrame(selected)


def selection_row(row: pd.Series, overlay_id: str, trial_name: str, order: int, hypothesis: str) -> dict[str, Any]:
    return {
        "selection_order": order,
        "strategy_id": row["strategy_id"],
        "family_id": row["family_id"],
        "overlay_id": overlay_id,
        "trial_name": trial_name,
        "selection_basis": "deterministic_family_mechanism_order_no_performance_inputs",
        "selection_evidence": hypothesis,
        "base_research_range": row["existing_frozen_research_range"],
        "expected_applicability": "applicable",
        "negative_control": bool(row["family_id"] == "daily_breakout_vcb_negative_control"),
    }


def exclusion_row(row: pd.Series, overlay_id: str, reason: str) -> dict[str, Any]:
    trial_name = {
        "OVL-ORD-001": "rebalance_band",
        "OVL-EXT-001": "time_stop",
        "OVL-STP-001": "wide_atr_catastrophic_stop",
    }[overlay_id]
    first_code = str(reason).split(";")[0]
    return {
        "strategy_id": row["strategy_id"],
        "family_id": row["family_id"],
        "overlay_id": overlay_id,
        "trial_name": trial_name,
        "exclusion_code": first_code,
        "reason": reason,
    }


def overlay_factory(strategy_id: str, overlay_id: str) -> Callable[[], TradeManagementOverlay]:
    if overlay_id == "OVL-ORD-001":
        return lambda: RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)
    if overlay_id == "OVL-EXT-001":
        return lambda strategy_id=strategy_id: TimeStopOverlay(max_completed_bars=5, strategies=[strategy_id])
    if overlay_id == "OVL-STP-001":
        return lambda: WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)
    raise ValueError(f"Unsupported overlay {overlay_id}")


def run_backtest(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    strategy_id: str,
    trial_name: str,
    slippage: float,
    overlay_factory_: Callable[[], TradeManagementOverlay | None],
) -> tuple[BacktestResult | None, pd.DataFrame, str]:
    strategy_hash = _strategy_source_hash(config, strategy_id)
    try:
        overlay = overlay_factory_()
        result = Backtester(prepared, config).run(
            trial_name,
            REQUESTED_RANGE["start"],
            REQUESTED_RANGE["end"],
            slippage,
            lightweight_outputs=True,
            overlay=overlay,
            run_id=f"family_portability_batch_v1_{strategy_id}_{trial_name}_{int(round(slippage * 10000))}bps",
            base_strategy_id=strategy_id,
            base_strategy_hash=strategy_hash,
        )
        events = result.overlay_events.copy()
        if not events.empty:
            events.insert(0, "slippage_bps_per_side", slippage * 10000.0)
            events.insert(0, "trial_name", trial_name)
            events.insert(0, "strategy_id", strategy_id)
        return result, events, ""
    except Exception as exc:
        return None, pd.DataFrame(), str(exc)


def add_result_row(
    rows: list[dict[str, Any]],
    *,
    result: BacktestResult | None,
    strategy_id: str,
    family_id: str,
    trial_name: str,
    overlay_id: str,
    slippage: float,
    execution_status: str,
    research_classification: str,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    strategy = {
        "strategy_id": strategy_id,
        "kind": STRATEGY_META[strategy_id]["strategy_frequency"],
    }
    if result is None:
        row = {
            "strategy_id": strategy_id,
            "strategy_kind": strategy["kind"],
            "trial_name": trial_name,
            "overlay_id": overlay_id,
            "slippage_bps_per_side": slippage * 10000.0,
            "status": execution_status,
            "error": error,
            "validation_label": LABEL,
        }
        for key in [
            "start",
            "end",
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "max_drawdown_pct",
            "drawdown_duration_days",
            "sharpe",
            "sortino",
            "return_to_drawdown",
            "average_gross_exposure",
            "maximum_gross_exposure",
            "average_cash_weight",
            "turnover",
            "number_of_orders",
            "number_of_fills",
            "modeled_transaction_cost",
            "number_skipped_or_resized_orders",
            "number_stop_events",
            "number_time_exit_events",
            "average_holding_period",
            "trade_mfe",
            "trade_mae",
            "worst_trade",
            "final_equity",
            "number_of_trades",
        ]:
            row[key] = np.nan
    else:
        row = summarize_result(
            result=result,
            strategy_id=strategy_id,
            strategy_kind=strategy["kind"],
            trial_name=trial_name,
            overlay_id=overlay_id,
            slippage=slippage,
            status=execution_status,
            error=error,
            validation_label=LABEL,
        )
    row.update(
        {
            "family_id": family_id,
            "execution_status": execution_status,
            "research_classification": research_classification,
            "overlay_config_hash": stable_hash(OVERLAY_CONFIGS.get(overlay_id, {})),
            "overlay_config": json.dumps(OVERLAY_CONFIGS.get(overlay_id, {}), sort_keys=True),
            "family_portability_label": "family_portability_test",
            "research_label": "research_only_exploratory",
        }
    )
    if extra:
        row.update(extra)
    rows.append(row)


def parse_json_cell(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def trade_sequence(result: BacktestResult) -> list[str]:
    if result.trades.empty:
        return []
    rows = []
    for _, trade in result.trades.iterrows():
        rows.append(
            f"{trade.get('strategy')}:{trade.get('symbol')}:{trade.get('entry_signal_date')}:{trade.get('entry_date')}:{trade.get('exit_date')}:{trade.get('exit_reason')}"
        )
    return rows


def first_trade_divergence(base: BacktestResult, overlay: BacktestResult) -> str:
    left = trade_sequence(base)
    right = trade_sequence(overlay)
    for idx, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return f"sequence={idx} base={a} overlay={b}"
    if len(left) != len(right):
        return f"length_changed base={len(left)} overlay={len(right)}"
    return ""


def metric_delta(base_row: pd.Series, overlay_row: pd.Series, key: str) -> float:
    return float(overlay_row.get(key, np.nan) - base_row.get(key, np.nan))


def rebalance_attribution(
    metrics: pd.DataFrame,
    events: pd.DataFrame,
    results: dict[tuple[str, str, float], BacktestResult],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for strategy_id in ["N1_dual_momentum_taa", "N3_dual_momentum_vol_scaled", "N4_inverse_vol_defensive_allocation"]:
        for slippage in SLIPPAGES:
            bps = slippage * 10000.0
            base_row = metrics[(metrics["strategy_id"] == strategy_id) & (metrics["trial_name"] == "base") & (metrics["slippage_bps_per_side"] == bps)].iloc[0]
            overlay_row = metrics[(metrics["strategy_id"] == strategy_id) & (metrics["trial_name"] == "rebalance_band") & (metrics["slippage_bps_per_side"] == bps)].iloc[0]
            ev = events[(events["strategy_id"] == strategy_id) & (events["trial_name"] == "rebalance_band") & (events["slippage_bps_per_side"] == bps)]
            suppress = ev[ev["decision_type"] == "suppress_order"]
            entry_suppress = suppress[suppress["signal_id"].str.contains(":entry:", na=False)]
            exit_suppress = suppress[suppress["signal_id"].str.contains(":exit:", na=False)]
            min_trade_count = 0
            min_trade_notional = 0.0
            genuine_exit_suppressed = False
            for _, event in suppress.iterrows():
                flags = parse_json_cell(event.get("data_quality_flags"))
                proposed = parse_json_cell(event.get("proposed_order"))
                if flags.get("below_nav_order"):
                    min_trade_count += 1
                    min_trade_notional += float(proposed.get("notional_delta", 0.0) or 0.0)
                if event.get("signal_id", "").find(":exit:") >= 0 and flags.get("base_exit_reason") not in {"monthly_rebalance_exit", None, ""}:
                    genuine_exit_suppressed = True
            return_delta = metric_delta(base_row, overlay_row, "total_return")
            drawdown_delta = metric_delta(base_row, overlay_row, "max_drawdown_pct")
            exposure_delta = metric_delta(base_row, overlay_row, "average_gross_exposure")
            turnover_delta = metric_delta(base_row, overlay_row, "turnover")
            cost_avoided = -metric_delta(base_row, overlay_row, "modeled_transaction_cost")
            mechanisms = []
            if cost_avoided > 0:
                mechanisms.append("DIRECT_COST_REDUCTION")
            if abs(exposure_delta) > 0.01:
                mechanisms.append("EXPOSURE_RETENTION")
            if first_trade_divergence(results[(strategy_id, "base", slippage)], results[(strategy_id, "rebalance_band", slippage)]):
                mechanisms.append("TRADE_PATH_CHANGE")
            if return_delta < 0 and abs(exposure_delta) > 0.01:
                mechanisms.append("HARMFUL_DELAY_OR_STALE_POSITION")
            if not mechanisms:
                mechanisms.append("NO_MEANINGFUL_EFFECT")
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "family_id": STRATEGY_META[strategy_id]["family_id"],
                    "slippage_bps_per_side": bps,
                    "suppressed_entry_adjustments": int(len(entry_suppress)),
                    "suppressed_exit_replacement_pairs": int(len(exit_suppress)),
                    "minimum_trade_suppression_count": min_trade_count,
                    "minimum_trade_suppression_notional": min_trade_notional,
                    "trade_count_change": metric_delta(base_row, overlay_row, "number_of_trades"),
                    "turnover_change": turnover_delta,
                    "corrected_direct_transaction_cost_avoided": cost_avoided,
                    "average_exposure_change": exposure_delta,
                    "maximum_exposure_change": metric_delta(base_row, overlay_row, "maximum_gross_exposure"),
                    "average_cash_weight_change": metric_delta(base_row, overlay_row, "average_cash_weight"),
                    "first_subsequent_trade_path_divergence": first_trade_divergence(
                        results[(strategy_id, "base", slippage)],
                        results[(strategy_id, "rebalance_band", slippage)],
                    ),
                    "genuine_liquidation_reversal_stop_or_risk_exit_suppressed": bool(genuine_exit_suppressed),
                    "return_change": return_delta,
                    "drawdown_change": drawdown_delta,
                    "mechanism_classification": ",".join(mechanisms),
                }
            )
    return pd.DataFrame(rows)


def post_exit_continuation(trades: pd.DataFrame, prepared: dict[str, pd.DataFrame], horizon: int = 5) -> tuple[float, int]:
    values: list[float] = []
    if trades.empty:
        return np.nan, 0
    for _, trade in trades[trades["exit_reason"] == "overlay_time_stop"].iterrows():
        df = prepared.get(str(trade["symbol"]))
        if df is None:
            continue
        dates = pd.to_datetime(df["date"])
        idx = dates.searchsorted(pd.Timestamp(trade["exit_date"]), side="right")
        if idx + horizon - 1 >= len(df):
            continue
        future_close = float(df.iloc[idx + horizon - 1]["close"])
        exit_price = float(trade["exit_price"])
        if exit_price:
            values.append(future_close / exit_price - 1.0)
    return (float(pd.Series(values).mean()) if values else np.nan, len(values))


def time_stop_attribution(
    metrics: pd.DataFrame,
    results: dict[tuple[str, str, float], BacktestResult],
    prepared: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    strategy_id = "C_swing_trend_pullback"
    for slippage in SLIPPAGES:
        bps = slippage * 10000.0
        base_row = metrics[(metrics["strategy_id"] == strategy_id) & (metrics["trial_name"] == "base") & (metrics["slippage_bps_per_side"] == bps)].iloc[0]
        overlay_row = metrics[(metrics["strategy_id"] == strategy_id) & (metrics["trial_name"] == "time_stop") & (metrics["slippage_bps_per_side"] == bps)].iloc[0]
        overlay_result = results[(strategy_id, "time_stop", slippage)]
        time_trades = overlay_result.trades[overlay_result.trades["exit_reason"] == "overlay_time_stop"].copy()
        continuation, continuation_count = post_exit_continuation(time_trades, prepared)
        return_delta = metric_delta(base_row, overlay_row, "total_return")
        drawdown_delta = metric_delta(base_row, overlay_row, "max_drawdown_pct")
        cost_increase = metric_delta(base_row, overlay_row, "modeled_transaction_cost")
        classifications = []
        if return_delta > 0 and drawdown_delta >= 0:
            classifications.append("HORIZON_MATCHED_HELPFUL")
        if return_delta < 0 and drawdown_delta > 0:
            classifications.append("RETURN_REDUCTION_WITH_RISK_REDUCTION")
        if cost_increase > 0 and return_delta < 0:
            classifications.append("COST_DOMINATED")
        if int((time_trades["pnl"] > 0).sum()) > int((time_trades["pnl"] < 0).sum()):
            classifications.append("WINNER_TRUNCATION")
        if not classifications:
            classifications.append("NO_MEANINGFUL_EFFECT")
        rows.append(
            {
                "strategy_id": strategy_id,
                "family_id": STRATEGY_META[strategy_id]["family_id"],
                "slippage_bps_per_side": bps,
                "time_stop_event_count": int(overlay_row.get("number_time_exit_events", 0)),
                "average_holding_period_change": metric_delta(base_row, overlay_row, "average_holding_period"),
                "trade_count_change": metric_delta(base_row, overlay_row, "number_of_trades"),
                "turnover_change": metric_delta(base_row, overlay_row, "turnover"),
                "winners_exited_early": int((time_trades["pnl"] > 0).sum()) if not time_trades.empty else 0,
                "losing_trades_shortened": int((time_trades["pnl"] < 0).sum()) if not time_trades.empty else 0,
                "post_exit_continuation_avg_5d": continuation,
                "post_exit_continuation_observation_count": continuation_count,
                "direct_transaction_cost_increase": cost_increase,
                "average_exposure_change": metric_delta(base_row, overlay_row, "average_gross_exposure"),
                "average_cash_weight_change": metric_delta(base_row, overlay_row, "average_cash_weight"),
                "return_change": return_delta,
                "drawdown_change": drawdown_delta,
                "return_to_drawdown_change": metric_delta(base_row, overlay_row, "return_to_drawdown"),
                "mechanism_classification": ",".join(classifications),
            }
        )
    return pd.DataFrame(rows)


def atr_stop_attribution(excluded: pd.DataFrame) -> pd.DataFrame:
    no_eligible = excluded[excluded["exclusion_code"] == "NO_ELIGIBLE_BASE_WITHOUT_EXISTING_LIFECYCLE_EXIT"]
    if not no_eligible.empty:
        return pd.DataFrame(
            [
                {
                    "strategy_id": "",
                    "family_id": "",
                    "slippage_bps_per_side": "",
                    "overlay_exit_count": 0,
                    "base_lifecycle_precedence_noops": 0,
                    "gap_through_stop_events": 0,
                    "stop_trigger_fill_assumption": "not_run_no_eligible_base",
                    "worst_position_loss_change": np.nan,
                    "turnover_change": np.nan,
                    "return_change": np.nan,
                    "drawdown_change": np.nan,
                    "incremental_lifecycle_decision": False,
                    "mechanism_classification": "NO_ELIGIBLE_BASE_WITHOUT_EXISTING_LIFECYCLE_EXIT",
                }
            ]
        )
    return pd.DataFrame()


def family_fit_matrix(
    rebalance: pd.DataFrame,
    time_stop: pd.DataFrame,
    atr_stop: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (family, frame) in rebalance.groupby("family_id"):
        helpful = frame.assign(helpful=frame["return_change"] > 0)
        rows.append(
            {
                "overlay_id": "OVL-ORD-001",
                "strategy_family": family,
                "strategy_count": int(frame["strategy_id"].nunique()),
                "applicable_count": int(frame["strategy_id"].nunique()),
                "helpful_at_0_bps": bool(helpful.loc[frame["slippage_bps_per_side"] == 0.0, "helpful"].any()),
                "helpful_at_5_bps": bool(helpful.loc[frame["slippage_bps_per_side"] == 5.0, "helpful"].any()),
                "helpful_at_10_bps": bool(helpful.loc[frame["slippage_bps_per_side"] == 10.0, "helpful"].any()),
                "drawdown_reduced": bool((frame["drawdown_change"] > 0).any()),
                "return_reduced": bool((frame["return_change"] < 0).any()),
                "turnover_reduced_or_increased": "reduced" if frame["turnover_change"].mean() < 0 else "increased",
                "principal_mechanism": ",".join(sorted(set(",".join(frame["mechanism_classification"]).split(",")))),
                "principal_failure_mode": "cost_sensitive_or_stale_position" if (frame["return_change"] < 0).any() else "",
                "family_portability_status": (
                    "PROMISING_FOR_DEEPER_EXPLORATION"
                    if bool((frame["return_change"] > 0).all())
                    else "MIXED_COST_SENSITIVE"
                    if bool((frame["return_change"] > 0).any())
                    else "FAMILY_SPECIFIC_NO_GENERALIZATION"
                ),
            }
        )
    for (family, frame) in time_stop.groupby("family_id"):
        rows.append(
            {
                "overlay_id": "OVL-EXT-001",
                "strategy_family": family,
                "strategy_count": int(frame["strategy_id"].nunique()),
                "applicable_count": int(frame["strategy_id"].nunique()),
                "helpful_at_0_bps": bool((frame.loc[frame["slippage_bps_per_side"] == 0.0, "return_change"] > 0).any()),
                "helpful_at_5_bps": bool((frame.loc[frame["slippage_bps_per_side"] == 5.0, "return_change"] > 0).any()),
                "helpful_at_10_bps": bool((frame.loc[frame["slippage_bps_per_side"] == 10.0, "return_change"] > 0).any()),
                "drawdown_reduced": bool((frame["drawdown_change"] > 0).any()),
                "return_reduced": bool((frame["return_change"] < 0).any()),
                "turnover_reduced_or_increased": "reduced" if frame["turnover_change"].mean() < 0 else "increased",
                "principal_mechanism": ",".join(sorted(set(",".join(frame["mechanism_classification"]).split(",")))),
                "principal_failure_mode": "winner_truncation_or_cost" if (frame["return_change"] < 0).any() else "",
                "family_portability_status": (
                    "PROMISING_FOR_DEEPER_EXPLORATION"
                    if bool((frame["return_change"] > 0).all())
                    else "MIXED_COST_SENSITIVE"
                    if bool((frame["return_change"] > 0).any())
                    else "CONSISTENTLY_HARMFUL"
                ),
            }
        )
    if not atr_stop.empty:
        rows.append(
            {
                "overlay_id": "OVL-STP-001",
                "strategy_family": "daily_directional_without_existing_lifecycle_exit",
                "strategy_count": 0,
                "applicable_count": 0,
                "helpful_at_0_bps": False,
                "helpful_at_5_bps": False,
                "helpful_at_10_bps": False,
                "drawdown_reduced": False,
                "return_reduced": False,
                "turnover_reduced_or_increased": "",
                "principal_mechanism": "",
                "principal_failure_mode": "NO_ELIGIBLE_BASE_WITHOUT_EXISTING_LIFECYCLE_EXIT",
                "family_portability_status": "INSUFFICIENT_ELIGIBLE_STRATEGIES",
            }
        )
    return pd.DataFrame(rows)


def run_test_commands() -> None:
    commands = [
        [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
        [
            sys.executable,
            "-m",
            "py_compile",
            "src/overlays.py",
            "src/portfolio.py",
            "src/backtester.py",
            "run_trade_management_family_portability_batch_v1.py",
        ],
    ]
    chunks: list[str] = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        chunks.extend(["$ " + " ".join(cmd), proc.stdout])
        if proc.stderr:
            chunks.append(proc.stderr)
        chunks.append(f"exit_code={proc.returncode}")
    (OUT_DIR / "test_results.txt").write_text("\n".join(chunks), encoding="utf-8")


def write_comparison(
    metrics: pd.DataFrame,
    selection: pd.DataFrame,
    excluded: pd.DataFrame,
    rebalance: pd.DataFrame,
    time_stop: pd.DataFrame,
    atr_stop: pd.DataFrame,
    fit: pd.DataFrame,
) -> None:
    lines = [
        "# Family Portability Batch v1",
        "",
        "Research-only exploratory family-portability test. No validation, optimization, promotion, or paper/demo/live eligibility claim.",
        "",
        "## Deterministic Selections",
        markdown_table(selection, ["strategy_id", "family_id", "overlay_id", "trial_name", "selection_basis"]),
        "",
        "## Canonical Metrics",
        markdown_table(
            metrics,
            [
                "strategy_id",
                "family_id",
                "trial_name",
                "overlay_id",
                "slippage_bps_per_side",
                "research_classification",
                "total_return",
                "max_drawdown_pct",
                "return_to_drawdown",
                "average_gross_exposure",
                "turnover",
                "number_of_trades",
                "modeled_transaction_cost",
            ],
        ),
        "",
        "## Rebalance Attribution",
        markdown_table(rebalance, ["strategy_id", "slippage_bps_per_side", "return_change", "drawdown_change", "trade_count_change", "corrected_direct_transaction_cost_avoided", "mechanism_classification"]),
        "",
        "## Time Stop Attribution",
        markdown_table(time_stop, ["strategy_id", "slippage_bps_per_side", "time_stop_event_count", "return_change", "drawdown_change", "average_holding_period_change", "mechanism_classification"]),
        "",
        "## Wide ATR Attribution",
        markdown_table(atr_stop, ["mechanism_classification", "incremental_lifecycle_decision", "stop_trigger_fill_assumption"]),
        "",
        "## Family Fit",
        markdown_table(fit, ["overlay_id", "strategy_family", "strategy_count", "applicable_count", "helpful_at_0_bps", "helpful_at_5_bps", "helpful_at_10_bps", "family_portability_status"]),
        "",
        "## Exclusions",
        markdown_table(excluded, ["strategy_id", "family_id", "overlay_id", "exclusion_code", "reason"]),
    ]
    (OUT_DIR / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def write_source_of_truth_update(selection: pd.DataFrame, fit: pd.DataFrame) -> None:
    lines = [
        "# Source Of Truth Update",
        "",
        "Family portability batch v1 completed as `family_portability_test;research_only_exploratory`.",
        "",
        "The source framework remains `PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION`; OVL-SIZ-001 was excluded and not recalibrated.",
        "",
        f"New selected strategy-overlay pairs tested: `{len(selection)}`.",
        "",
        markdown_table(fit, ["overlay_id", "strategy_family", "family_portability_status"]),
        "",
        "No promotion candidate, overlay combination, strategy mutation, parameter change, data-download requirement, or paper/demo/live/broker/scheduler/webhook action was created.",
    ]
    (OUT_DIR / "source_of_truth_update.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "config.yaml")
    config["project_root"] = str(ROOT)
    data_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(data_result.data)

    inventory = build_inventory(config, data_result.data)
    selection, excluded, selected_pairs = select_candidates(inventory)
    if len(selected_pairs) > 6:
        raise RuntimeError("Selection exceeded six strategy-overlay pairs.")

    strategy_hashes = {
        row["strategy_id"]: _strategy_source_hash(_strategy_only_config(config, row["strategy_id"]), row["strategy_id"])
        for _, row in inventory.iterrows()
        if row["strategy_id"] in config.get("strategies", {})
    }
    manifest = {
        "run_id": "family_portability_batch_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "labels": ["family_portability_test", "research_only_exploratory"],
        "research_only": True,
        "exploratory": True,
        "source_of_truth": str(CANONICAL_SOURCE),
        "source_framework_status": "PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION",
        "ovl_siz_excluded": True,
        "candidate_selection_rule": "deterministic_family_mechanism_order_no_performance_inputs",
        "selected_strategy_overlay_pairs": selection.to_dict("records"),
        "selection_ordering": selection[["selection_order", "strategy_id", "overlay_id", "family_id"]].to_dict("records"),
        "strategy_hashes": strategy_hashes,
        "overlay_configuration_hashes": {key: stable_hash(value) for key, value in OVERLAY_CONFIGS.items()},
        "overlay_parameter_mappings": OVERLAY_CONFIGS,
        "base_research_ranges": {
            row["strategy_id"]: row["existing_frozen_research_range"]
            for _, row in inventory.iterrows()
            if row["strategy_id"] in set(selection["strategy_id"])
        },
        "intended_cost_assumptions_bps_per_side": [value * 10000.0 for value in SLIPPAGES],
        "applicability_expectations": selection[["strategy_id", "overlay_id", "expected_applicability"]].to_dict("records"),
        "family_hypotheses": {
            "OVL-ORD-001": "Periodic target-weight families may suppress small replacement trades without suppressing genuine exits.",
            "OVL-EXT-001": "Five completed bars may match short-duration pullback/reversal lifecycles but can truncate winners.",
            "OVL-STP-001": "Wide ATR stop requires a base without existing lifecycle exits; none qualified.",
        },
        "negative_control_designations": selection[selection["negative_control"]].to_dict("records"),
        "exclusions_and_reasons": excluded.to_dict("records"),
        "no_combinations": True,
        "paper_demo_live_broker_scheduler_webhook_paths_activated": False,
        "paper_demo_live_broker_scheduler_webhook_paths_modified": False,
        "repository_commit": git_commit_hash(ROOT),
        "config_hash": config_hash(config),
    }
    inventory.to_csv(OUT_DIR / "candidate_inventory.csv", index=False)
    selection.to_csv(OUT_DIR / "candidate_selection.csv", index=False)
    excluded.to_csv(OUT_DIR / "excluded_candidates.csv", index=False)
    write_json(OUT_DIR / "pre_registered_manifest.json", json_ready(manifest))

    metrics_rows: list[dict[str, Any]] = []
    events_frames: list[pd.DataFrame] = []
    identity_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    results: dict[tuple[str, str, float], BacktestResult] = {}

    for _, pair in selection.iterrows():
        strategy_id = pair["strategy_id"]
        family_id = pair["family_id"]
        overlay_id = pair["overlay_id"]
        trial_name = pair["trial_name"]
        strategy_cfg = _strategy_only_config(config, strategy_id)
        for slippage in SLIPPAGES:
            print(f"Running {strategy_id} {trial_name} {slippage * 10000.0:.0f} bps...", flush=True)
            base, _, base_error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="base",
                slippage=slippage,
                overlay_factory_=lambda: None,
            )
            identity, identity_events, identity_error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="identity",
                slippage=slippage,
                overlay_factory_=lambda: IdentityOverlay(),
            )
            overlay_result, overlay_events, overlay_error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name=trial_name,
                slippage=slippage,
                overlay_factory_=overlay_factory(strategy_id, overlay_id),
            )
            base_ok = base is not None
            identity_ok = identity is not None
            overlay_ok = overlay_result is not None
            identity_match = bool(
                base_ok and identity_ok and result_hashes(base)["complete_state_hash"] == result_hashes(identity)["complete_state_hash"]
            )
            add_result_row(
                metrics_rows,
                result=base,
                strategy_id=strategy_id,
                family_id=family_id,
                trial_name="base",
                overlay_id="BASE",
                slippage=slippage,
                execution_status="completed" if base_ok else "failed",
                research_classification=CLASS_MECHANICAL_CONTROL if base_ok else CLASS_FAILED,
                error=base_error,
            )
            add_result_row(
                metrics_rows,
                result=identity,
                strategy_id=strategy_id,
                family_id=family_id,
                trial_name="identity",
                overlay_id="IDENTITY",
                slippage=slippage,
                execution_status="completed" if identity_ok else "failed",
                research_classification=CLASS_MECHANICAL_CONTROL if identity_match else CLASS_FAILED,
                error=identity_error,
                extra={"identity_complete_state_match": identity_match},
            )
            if overlay_id == "OVL-STP-001":
                overlay_class = CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE
            elif overlay_ok and int((overlay_events.get("decision_type", pd.Series(dtype=str)) == "suppress_order").sum()) == 0 and overlay_id == "OVL-ORD-001":
                overlay_class = CLASS_APPLICABLE_NO_EFFECT
            else:
                overlay_class = CLASS_APPLICABLE_EFFECTIVE if overlay_ok else CLASS_FAILED
            add_result_row(
                metrics_rows,
                result=overlay_result,
                strategy_id=strategy_id,
                family_id=family_id,
                trial_name=trial_name,
                overlay_id=overlay_id,
                slippage=slippage,
                execution_status="completed" if overlay_ok else "failed",
                research_classification=overlay_class,
                error=overlay_error,
            )
            identity_rows.append(
                {
                    "strategy_id": strategy_id,
                    "family_id": family_id,
                    "slippage_bps_per_side": slippage * 10000.0,
                    "base_status": "completed" if base_ok else "failed",
                    "identity_status": "completed" if identity_ok else "failed",
                    "complete_state_hash_match": identity_match,
                    "base_complete_state_hash": result_hashes(base)["complete_state_hash"] if base_ok else "",
                    "identity_complete_state_hash": result_hashes(identity)["complete_state_hash"] if identity_ok else "",
                }
            )
            if not identity_match:
                failures.append(
                    {
                        "strategy_id": strategy_id,
                        "family_id": family_id,
                        "overlay_id": "IDENTITY",
                        "slippage_bps_per_side": slippage * 10000.0,
                        "failure_code": "IDENTITY_EQUIVALENCE_FAILED",
                        "details": identity_error,
                    }
                )
            if not overlay_ok:
                failures.append(
                    {
                        "strategy_id": strategy_id,
                        "family_id": family_id,
                        "overlay_id": overlay_id,
                        "slippage_bps_per_side": slippage * 10000.0,
                        "failure_code": "DATA_FEASIBILITY_BLOCKED" if "data" in overlay_error.lower() else "OVERLAY_RUN_FAILED",
                        "details": overlay_error,
                    }
                )
            if base_ok:
                results[(strategy_id, "base", slippage)] = base
            if identity_ok:
                results[(strategy_id, "identity", slippage)] = identity
            if overlay_ok:
                results[(strategy_id, trial_name, slippage)] = overlay_result
            if not identity_events.empty:
                events_frames.append(identity_events)
            if not overlay_events.empty:
                events_frames.append(overlay_events)

    metrics = pd.DataFrame(metrics_rows)
    events = pd.concat(events_frames, ignore_index=True) if events_frames else pd.DataFrame()
    rebalance = rebalance_attribution(metrics, events, results)
    time_stop = time_stop_attribution(metrics, results, prepared)
    atr_stop = atr_stop_attribution(excluded)
    fit = family_fit_matrix(rebalance, time_stop, atr_stop)

    for _, row in excluded.iterrows():
        failures.append(
            {
                "strategy_id": row.get("strategy_id", ""),
                "family_id": row.get("family_id", ""),
                "overlay_id": row.get("overlay_id", ""),
                "slippage_bps_per_side": "",
                "failure_code": row.get("exclusion_code", ""),
                "details": row.get("reason", ""),
            }
        )
    for _, row in metrics[metrics["research_classification"] == CLASS_APPLICABLE_NO_EFFECT].iterrows():
        failures.append(
            {
                "strategy_id": row["strategy_id"],
                "family_id": row["family_id"],
                "overlay_id": row["overlay_id"],
                "slippage_bps_per_side": row["slippage_bps_per_side"],
                "failure_code": "OVERLAY_NO_EFFECT",
                "details": "Overlay completed but made no meaningful decision.",
            }
        )
    failure_registry = pd.DataFrame(failures).drop_duplicates()

    metrics.to_csv(OUT_DIR / "trial_registry.csv", index=False)
    metrics.to_csv(OUT_DIR / "metrics.csv", index=False)
    pd.DataFrame(identity_rows).to_csv(OUT_DIR / "identity_equivalence.csv", index=False)
    events.to_csv(OUT_DIR / "overlay_events.csv", index=False)
    rebalance.to_csv(OUT_DIR / "rebalance_attribution.csv", index=False)
    time_stop.to_csv(OUT_DIR / "time_stop_attribution.csv", index=False)
    atr_stop.to_csv(OUT_DIR / "atr_stop_attribution.csv", index=False)
    fit.to_csv(OUT_DIR / "family_fit_matrix.csv", index=False)
    failure_registry.to_csv(OUT_DIR / "failure_registry.csv", index=False)
    write_comparison(metrics, selection, excluded, rebalance, time_stop, atr_stop, fit)
    write_source_of_truth_update(selection, fit)
    run_test_commands()
    print(f"Family portability batch complete: {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
