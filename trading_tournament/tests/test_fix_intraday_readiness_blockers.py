from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from intraday_research.data_schema import validate_intraday_bars
from intraday_research.fill_model import FillRequest, simulate_market_fill
from intraday_research.kill_switch import KillSwitchRecorder
from intraday_research.risk_engine import IntradayRiskLimits, IntradayRiskState, evaluate_risk_state
from intraday_research.session_timing import build_signal_timing, regular_session

import run_fix_intraday_readiness_blockers as fix


def write_fixture(root: Path) -> None:
    registry_path = root / fix.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "fix_intraday_readiness_blockers",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "rejected_daily_variant_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / fix.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `fix_intraday_readiness_blockers`\n", encoding="utf-8")

    previous = root / fix.PREVIOUS_AUDIT_DIR / "intraday_readiness_manifest.json"
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_text(
        json.dumps(
            {
                "readiness_verdict": "intraday_research_not_ready",
                "next_action": "fix_intraday_readiness_blockers",
                "blocker_count": 9,
                "critical_blocker_count": 6,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def fix_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("fix_intraday_readiness_blockers")
    write_fixture(root)
    before = yaml.safe_load((root / fix.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = fix.run_fix_intraday_readiness_blockers(root)
    after = yaml.safe_load((root / fix.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(fix_run: dict[str, Any]) -> Path:
    return Path(fix_run["output_dir"])


def manifest(fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(fix_run) / "intraday_blocker_fix_manifest.json").read_text(encoding="utf-8"))


def consistency(fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(fix_run) / "intraday_blocker_fix_consistency_check.json").read_text(encoding="utf-8"))


def sample_intraday_rows() -> list[dict[str, Any]]:
    return [
        {
            "symbol": "SPY",
            "timestamp": "2026-06-29T13:30:00Z",
            "open": "100",
            "high": "101",
            "low": "99",
            "close": "100.5",
            "volume": "10000",
            "timeframe": "1Min",
            "source": "synthetic_fixture",
            "adjusted": True,
        },
        {
            "symbol": "SPY",
            "timestamp": "2026-06-29T13:31:00+00:00",
            "open": "100.5",
            "high": "101.5",
            "low": "100",
            "close": "101",
            "volume": "9000",
            "timeframe": "1Min",
            "source": "synthetic_fixture",
            "adjusted": True,
        },
    ]


def test_blocker_fix_only_mode(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["blocker_fix_only"] is True


def test_no_intraday_strategy_backtests(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["intraday_strategy_backtests_run"] is False


def test_no_new_discovery(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["new_discovery_run"] is False


def test_no_new_performance_metrics(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["provider_download"] is False


def test_no_intraday_data_download(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["intraday_data_downloaded"] is False


def test_no_candidate_exhaustive(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(fix_run: dict[str, Any]) -> None:
    loaded = manifest(fix_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["broker_orders_cancelled"] is False


def test_no_live_orders(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["live_orders"] is False


def test_no_accepted_rejected_strategy_state_changes(fix_run: dict[str, Any]) -> None:
    assert fix_run["strategies_before"] == fix_run["strategies_after"]


def test_intraday_data_schema_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_data_schema_contract.md").exists()


def test_intraday_cache_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_cache_contract.md").exists()


def test_session_timing_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_session_timing_contract.md").exists()


def test_fill_model_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_fill_model_contract.md").exists()


def test_risk_engine_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_risk_engine_contract.md").exists()


def test_kill_switch_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_kill_switch_contract.md").exists()


def test_event_logging_contract_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_event_logging_contract.md").exists()


def test_candidate_readiness_gates_exist(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_candidate_readiness_gates.md").exists()


def test_remaining_blockers_table_exists(fix_run: dict[str, Any]) -> None:
    assert (output(fix_run) / "intraday_remaining_blockers.csv").exists()


def test_readiness_verdict_after_fix_is_valid(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["readiness_verdict_after_fix"] in fix.VALID_READINESS_VERDICTS
    assert manifest(fix_run)["readiness_verdict_after_fix"] == "manual_intraday_data_source_review_required"


def test_next_action_is_valid(fix_run: dict[str, Any]) -> None:
    assert manifest(fix_run)["next_action"] in fix.VALID_NEXT_ACTIONS
    assert manifest(fix_run)["next_action"] == "manual_intraday_data_source_review_required"


def test_manifest_flags_match_strict_scope(fix_run: dict[str, Any]) -> None:
    loaded = manifest(fix_run)
    for key, value in fix.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(fix_run)["consistency_passed"] is True


def test_timestamp_validation_accepts_aware_utc_rows() -> None:
    rows = validate_intraday_bars(sample_intraday_rows())
    assert rows[0]["timestamp"].tzinfo is not None
    assert rows[0]["timestamp"].isoformat() == "2026-06-29T13:30:00+00:00"


def test_duplicate_timestamp_rejection() -> None:
    rows = sample_intraday_rows()
    rows[1]["timestamp"] = rows[0]["timestamp"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_intraday_bars(rows)


def test_daily_bars_rejected_as_intraday() -> None:
    rows = sample_intraday_rows()
    rows[0]["timeframe"] = "1Day"
    with pytest.raises(ValueError, match="timeframe"):
        validate_intraday_bars(rows)


def test_completed_bar_timing_contract() -> None:
    session = regular_session(date(2026, 6, 29))
    assert session is not None
    plan = build_signal_timing(session.open_utc + timedelta(minutes=30), 5, session)
    assert plan.completed_bar_only is True
    assert plan.entry_not_before_utc > plan.signal_bar_end_utc


def test_no_lookahead_signal_entry_separation() -> None:
    session = regular_session(date(2026, 6, 29))
    assert session is not None
    plan = build_signal_timing(session.open_utc + timedelta(minutes=10), 1, session)
    assert plan.no_lookahead_enforced is True
    assert plan.entry_not_before_utc == plan.signal_bar_end_utc + timedelta(minutes=1)


def test_simple_slippage_application() -> None:
    result = simulate_market_fill(
        FillRequest(
            side="buy",
            quantity=Decimal("10"),
            reference_price=Decimal("100"),
            bar_low=Decimal("99"),
            bar_high=Decimal("102"),
            spread_cents=Decimal("2"),
            slippage_bps=Decimal("10"),
        )
    )
    assert result.status == "filled"
    assert result.fill_price == Decimal("100.11")


def test_no_fill_placeholder_behavior() -> None:
    result = simulate_market_fill(
        FillRequest(
            side="buy",
            quantity=Decimal("10"),
            reference_price=Decimal("100"),
            bar_low=Decimal("99"),
            bar_high=Decimal("101"),
            force_no_fill_reason="data_quality_halt",
        )
    )
    assert result.status == "no_fill"
    assert result.no_fill_placeholder is True


def test_partial_fill_placeholder_behavior() -> None:
    result = simulate_market_fill(
        FillRequest(
            side="sell",
            quantity=Decimal("10"),
            reference_price=Decimal("100"),
            bar_low=Decimal("99"),
            bar_high=Decimal("101"),
            max_fill_quantity=Decimal("4"),
            allow_partial=True,
        )
    )
    assert result.status == "partial_fill"
    assert result.filled_quantity == Decimal("4")
    assert result.partial_fill_placeholder is True


def test_max_daily_loss_trigger() -> None:
    decision = evaluate_risk_state(
        IntradayRiskState(
            timestamp_utc=datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc),
            daily_realized_pnl=Decimal("-91"),
            latest_bar_timestamp_utc=datetime(2026, 6, 29, 14, 59, tzinfo=timezone.utc),
        ),
        IntradayRiskLimits(max_daily_loss=Decimal("90")),
    )
    assert decision.allowed is False
    assert "max_daily_loss" in decision.reasons


def test_max_trades_per_day_trigger() -> None:
    decision = evaluate_risk_state(
        IntradayRiskState(
            timestamp_utc=datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc),
            trades_today=3,
            latest_bar_timestamp_utc=datetime(2026, 6, 29, 14, 59, tzinfo=timezone.utc),
        ),
        IntradayRiskLimits(max_trades_per_day=3),
    )
    assert decision.allowed is False
    assert "max_trades_per_day" in decision.reasons


def test_force_flat_no_overnight_trigger() -> None:
    decision = evaluate_risk_state(
        IntradayRiskState(
            timestamp_utc=datetime(2026, 6, 29, 21, 0, tzinfo=timezone.utc),
            open_positions={"SPY": Decimal("100")},
            latest_bar_timestamp_utc=datetime(2026, 6, 29, 20, 59, tzinfo=timezone.utc),
        ),
        IntradayRiskLimits(),
    )
    assert decision.force_flat_required is True
    assert "force_flat_no_overnight" in decision.reasons


def test_kill_switch_trigger_recording() -> None:
    recorder = KillSwitchRecorder()
    event = recorder.trigger(
        "data_error",
        "synthetic fixture missing bar",
        datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc),
    )
    assert recorder.active is True
    assert event.reason == "data_error"
