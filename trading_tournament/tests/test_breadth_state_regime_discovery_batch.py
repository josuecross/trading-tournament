from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import run_active_strategy_evidence_recompute as active
import run_breadth_state_regime_discovery_batch as discovery
import run_breadth_state_regime_preregistration as prereg


def write_price_cache(root: Path, symbol: str, periods: int = 620, drift: float = 0.00018) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [40.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.00025 * ((idx % 13) - 6)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    symbols = sorted(set(discovery.required_symbols()))
    for idx, symbol in enumerate(symbols):
        drift = 0.00004 + idx * 0.000006
        if symbol == "BIL":
            drift = 0.00001
        write_price_cache(root, symbol, drift=drift)


def registry_row(row_id: str, active_flag: bool) -> dict[str, object]:
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active_flag else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "test",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active_flag else "tier2_exploratory",
        "status": "active_observation" if active_flag else "benchmark_watchlist",
        "role": "test",
        "rules_frozen": True,
        "paper_forward_active": active_flag,
        "implementation_status": "implemented" if active_flag else "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "test",
        "latest_evidence_path": "evidence/test/latest",
        "latest_known_result_summary": "test",
        "allowed_next_action": "observe_only" if active_flag else "research_sample_review",
        "forbidden_next_actions": ["run_candidate_exhaustive", "promote_to_real_money"],
        "risk_framework_status": "paper_forward_allowed" if active_flag else "research_sample_only",
        "paper_forward_allowed_by_risk_framework": active_flag,
        "real_money_recommendation": False,
        "promotion_blockers": "none",
        "promotion_requirements": "none",
        "demotion_or_kill_criteria": "none",
        "notes": "test",
        "strategy_id": row_id,
        "family": "test",
        "instrument_lane": "ETF",
        "evidence_tier": "test",
        "current_status": "active_observation" if active_flag else "benchmark_watchlist",
        "allowed_next_actions": ["observe_only"] if active_flag else ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "keep_active_observation" if active_flag else "benchmark_watchlist",
        "promotion_reason": "test",
        "primary_failure_mode": "not_flagged",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "test",
        "evidence_needed": "none",
        "duplicate_of": "",
        "blocked_reason": "",
    }


def write_registry(root: Path) -> None:
    path = root / discovery.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        registry_row(active.VM_ID, True),
        registry_row(active.DSR_ID, True),
        registry_row(active.SPY_200D_ID, True),
    ]
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                    "lane_id": discovery.LANE_ID,
                    "lane_status": "pre_registered_not_run",
                    "candidate_exhaustive_run": False,
                    "paper_forward_active": False,
                    "current_next_action": "run_breadth_state_regime_discovery_batch",
                },
                "risk_framework": {"active_framework": "balanced_speculative_research_v1", "framework_path": "risk_framework/risk_framework.yaml"},
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_active_observations(root: Path) -> None:
    for strategy_id, path in active.active_observation_paths(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_preregistration(root: Path) -> None:
    prereg_dir = root / "evidence" / "pre_registered_lanes" / "breadth_state_regime" / "latest"
    prereg_dir.mkdir(parents=True, exist_ok=True)
    with (prereg_dir / "breadth_state_regime_future_rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_id"], lineterminator="\n")
        writer.writeheader()
        for row_id in discovery.ROW_IDS:
            writer.writerow({"row_id": row_id})
    (prereg_dir / "breadth_state_regime_manifest.json").write_text(
        json.dumps({"lane_id": discovery.LANE_ID, "lane_status": "pre_registered_not_run", "future_rows": discovery.ROW_IDS}),
        encoding="utf-8",
    )


def write_context(root: Path) -> None:
    combo_dir = root / "evidence" / "active_combo_benchmark" / "latest"
    combo_dir.mkdir(parents=True, exist_ok=True)
    (combo_dir / "active_combo_manifest.json").write_text(
        json.dumps({"benchmark_id": discovery.combo.COMBO_ID, "active_combo_is_reference_not_active_strategy": True}),
        encoding="utf-8",
    )
    roadmap = root / discovery.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `run_breadth_state_regime_discovery_batch`\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def synthetic_discovery(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("breadth_state_discovery")
    write_registry(root)
    write_active_observations(root)
    write_preregistration(root)
    write_context(root)
    write_required_cache(root)
    obs_paths = active.active_observation_paths(root)
    before = {sid: file_hash(path) for sid, path in obs_paths.items()}
    result = discovery.run_breadth_state_regime_discovery_batch(root, strict_state=True)
    after = {sid: file_hash(path) for sid, path in obs_paths.items()}
    return {"root": root, "result": result, "before": before, "after": after}


def output_path(synthetic_discovery: dict[str, object]) -> Path:
    return Path(synthetic_discovery["result"]["output_dir"])


def test_only_four_preregistered_rows_are_evaluated(synthetic_discovery: dict[str, object]) -> None:
    rows = list(csv.DictReader((output_path(synthetic_discovery) / "breadth_state_regime_results.csv").open(encoding="utf-8")))
    assert [row["strategy_id"] for row in rows] == discovery.ROW_IDS


def test_fixed_state_thresholds_are_not_changed(synthetic_discovery: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_discovery) / "breadth_state_regime_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["fixed_state_thresholds_unchanged"] is True
    trace = list(csv.DictReader((output_path(synthetic_discovery) / "breadth_state_regime_state_trace.csv").open(encoding="utf-8")))
    assert trace


def test_canary_override_forces_risk_off_when_spy_and_qqq_below_200d() -> None:
    dates = pd.bdate_range("2022-01-01", periods=240)
    data: dict[str, list[float]] = {}
    for symbol in discovery.RISK_ASSETS:
        data[symbol] = list(np.linspace(80, 140, len(dates)))
    data["SPY"] = list(np.linspace(140, 80, len(dates)))
    data["QQQ"] = list(np.linspace(150, 85, len(dates)))
    close = pd.DataFrame(data, index=dates)
    state = discovery.breadth_state(close, 239)
    assert state["state"] == "risk_off"
    assert state["canary_forced_risk_off"] is True


def test_per_asset_availability_used_without_common_start() -> None:
    dates = pd.bdate_range("2022-01-01", periods=240)
    data = {symbol: list(np.linspace(80, 140, len(dates))) for symbol in discovery.RISK_ASSETS}
    data["INDA"] = [float("nan")] * 220 + list(np.linspace(100, 105, 20))
    close = pd.DataFrame(data, index=dates)
    state = discovery.breadth_state(close, 219)
    assert state["available_denominator"] < len(discovery.RISK_ASSETS)
    assert "INDA" in state["unavailable_symbols"]


def test_discovery_cannot_output_candidate_exhaustive(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "breadth_state_regime_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_sample_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    decisions = set(manifest["decisions"].values())
    assert "candidate_exhaustive" not in decisions


def test_discovery_cannot_activate_paper_forward(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "breadth_state_regime_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["paper_forward_activation"] is False
    assert synthetic_discovery["before"] == synthetic_discovery["after"]


def test_discovery_cannot_touch_broker_live_order_paths(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "breadth_state_regime_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False


def test_stop_hit_above_zero_blocks_promotion() -> None:
    blockers = discovery.promotion_blockers(
        "bsr_breadth_state_top_assets_v1",
        {
            "stop_hit_rate": 0.1,
            "risk_buffer_vs_minus_600": 100,
            "delta_vs_active_combo": 100,
            "delta_vs_active_vm": 100,
            "delta_vs_active_dsr": 100,
            "delta_vs_spy_200d": 100,
            "target_300_before_stop_rate": 0.8,
            "target_400_before_stop_rate": 0.6,
            "mean_bil_allocation": 0.1,
            "canary_forced_rate": 0.0,
        },
    )
    assert "stop_hit_above_zero" in blockers


def test_risk_buffer_below_25_blocks_promotion() -> None:
    blockers = discovery.promotion_blockers(
        "bsr_breadth_state_top_assets_v1",
        {
            "stop_hit_rate": 0.0,
            "risk_buffer_vs_minus_600": 24,
            "delta_vs_active_combo": 100,
            "delta_vs_active_vm": 100,
            "delta_vs_active_dsr": 100,
            "delta_vs_spy_200d": 100,
            "target_300_before_stop_rate": 0.8,
            "target_400_before_stop_rate": 0.6,
            "mean_bil_allocation": 0.1,
            "canary_forced_rate": 0.0,
        },
    )
    assert "risk_buffer_below_25" in blockers


def test_marginal_improvement_with_complexity_blocks_promotion() -> None:
    blockers = discovery.promotion_blockers(
        "bsr_breadth_state_defensive_shift_v1",
        {
            "stop_hit_rate": 0.0,
            "risk_buffer_vs_minus_600": 200,
            "delta_vs_active_combo": 6,
            "delta_vs_active_vm": 100,
            "delta_vs_active_dsr": 100,
            "delta_vs_spy_200d": 100,
            "target_300_before_stop_rate": 0.8,
            "target_400_before_stop_rate": 0.6,
            "mean_bil_allocation": 0.1,
            "canary_forced_rate": 0.0,
        },
    )
    assert "marginal_or_negative_active_combo_improvement" in blockers


def test_duplication_of_active_combo_or_spy200d_blocks_promotion() -> None:
    blockers = discovery.promotion_blockers(
        "bsr_breadth_state_active_combo_overlay_v1",
        {
            "stop_hit_rate": 0.0,
            "risk_buffer_vs_minus_600": 200,
            "delta_vs_active_combo": 20,
            "delta_vs_active_vm": 100,
            "delta_vs_active_dsr": 100,
            "delta_vs_spy_200d": 20,
            "target_300_before_stop_rate": 0.8,
            "target_400_before_stop_rate": 0.6,
            "corr_vs_active_combo": 0.99,
            "corr_vs_spy_200d": 0.96,
            "mean_bil_allocation": 0.1,
            "canary_forced_rate": 0.0,
        },
    )
    assert "highly_duplicative_of_active_combo" in blockers
    assert "highly_duplicative_of_spy_200d" in blockers


def test_no_candidate_result_triggers_archive_stop_condition(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "breadth_state_regime_discovery_manifest.json").read_text(encoding="utf-8"))
    if manifest["promotion_candidates_count"] == 0:
        assert manifest["etf_wrapper_track_archived_stopped"] is True
        assert manifest["next_action"] == discovery.NEXT_ACTION_ARCHIVE


def test_evidence_includes_state_frequency_bil_allocation_and_denominator_diagnostics(synthetic_discovery: dict[str, object]) -> None:
    state_rows = list(csv.DictReader((output_path(synthetic_discovery) / "breadth_state_regime_state_frequency.csv").open(encoding="utf-8")))
    trace_rows = list(csv.DictReader((output_path(synthetic_discovery) / "breadth_state_regime_state_trace.csv").open(encoding="utf-8")))
    assert state_rows
    assert trace_rows
    assert {"risk_on_frequency", "neutral_frequency", "risk_off_frequency", "mean_bil_allocation", "mean_available_denominator"} <= set(state_rows[0])
    assert {"available_denominator", "bil_target_weight", "canary_forced_risk_off"} <= set(trace_rows[0])
