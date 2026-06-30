from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_scoring_fix as fix
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v2 import (
    saturation_report,
    score_row_v2,
    score_rows_v2,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def base_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "variant_id": "synthetic",
        "family_id": "trend_momentum",
        "objective_lane": "standalone_growth",
        "status": "sandbox_family_weak",
        "promotable": "false",
        "paper_candidate_allowed": "false",
        "180d_median_final_equity": 3090.0,
        "ending_equity": 3300.0,
        "total_return": 0.10,
        "sharpe": 0.90,
        "max_drawdown": -180.0,
        "180d_worst_drawdown": -150.0,
        "risk_buffer_vs_minus_600": 420.0,
        "stop_hit_rate": 0.0,
        "stop_risk_breach_flag": "false",
        "delta_vs_active_combo_180d_median": 20.0,
        "active_combo_improvement": 20.0,
        "active_vm_dsr_pair_improvement": 15.0,
        "portfolio_return_risk_improvement": 0.10,
        "drawdown_contribution": 50.0,
        "volatility_contribution": 0.01,
        "correlation_reduction": 0.45,
        "return_drag_penalty": 0.05,
        "duplicate_penalty": 0.0,
        "corr_vs_active_combo": 0.40,
        "trade_count": 80,
        "avg_turnover": 0.04,
        "avg_cash_allocation": 0.10,
        "avg_symbols_held": 2.0,
        "max_symbol_weight": 0.55,
        "data_window_length": 900,
        "target_300_before_stop_rate": 0.0,
        "target_400_before_stop_rate": 0.0,
        "portfolio_level_risk_adjusted_improvement": 0.05,
    }
    row.update(overrides)
    return row


def source_rows() -> list[dict[str, Any]]:
    return [
        base_row(variant_id="good_standalone"),
        base_row(
            variant_id="cash_lagging",
            family_id="breakout_continuation",
            objective_lane="portfolio_contribution_sleeve",
            avg_cash_allocation=0.92,
            avg_symbols_held=0.1,
            trade_count=0,
            delta_vs_active_combo_180d_median=-180.0,
            return_drag_penalty=0.90,
        ),
        base_row(
            variant_id="high_drawdown",
            max_drawdown=-900.0,
            risk_buffer_vs_minus_600=-300.0,
            stop_risk_breach_flag="true",
        ),
        base_row(
            variant_id="duplicate_combo",
            objective_lane="portfolio_contribution_sleeve",
            corr_vs_active_combo=0.98,
            duplicate_penalty=22.0,
            active_combo_improvement=-5.0,
        ),
    ]


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "fix_revised_objective_sandbox_scoring",
            "official_current_next_action": "fix_revised_objective_sandbox_scoring",
            "intraday_research_remains_paused": True,
        },
        "strategies": [
            {"id": "paper_forward_vm_quality_lowvol_proxy_v1", "status": "active_paper_demo_observation"},
            {"id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "status": "active_paper_demo_observation"},
            {"id": "static_all_weather_benchmark_v1", "status": "benchmark_control"},
            {"id": "mfv_equal_weight_trend_filter_v1", "status": "discovery_reject", "paper_forward_active": False},
        ],
    }
    registry_path = root / config.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    roadmap = root / config.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `fix_revised_objective_sandbox_scoring`\n",
        encoding="utf-8",
    )
    source = root / BATCH_OUTPUT_DIR
    rows = source_rows()
    write_csv(source / "batch_002_variant_results.csv", rows, list(rows[0].keys()))
    write_json(source / "revised_objective_sandbox_batch_manifest.json", {"batch_id": "batch_002_revised_objective"})
    audit_dir = root / fix.BATCH_AUDIT_DIR
    write_json(audit_dir / "revised_objective_sandbox_batch_audit_manifest.json", {"scoring_fix_required": True})


@pytest.fixture(scope="module")
def scoring_fix_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_scoring_fix")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = fix.run_revised_objective_sandbox_scoring_fix(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(scoring_fix_run: dict[str, Any]) -> Path:
    return Path(scoring_fix_run["output_dir"])


def manifest(scoring_fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(scoring_fix_run) / "scoring_fix_manifest.json").read_text(encoding="utf-8"))


def consistency(scoring_fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(scoring_fix_run) / "scoring_fix_consistency_check.json").read_text(encoding="utf-8"))


def rescore_rows(scoring_fix_run: dict[str, Any]) -> list[dict[str, str]]:
    with (output(scoring_fix_run) / "batch_002_diagnostic_rescore.csv").open(
        "r", newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def test_scoring_fix_only_mode(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["scoring_fix_only"] is True


def test_no_new_sandbox_batch(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(scoring_fix_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["new_backtests_run"] is False


def test_no_new_performance_metrics_from_raw_data(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["new_performance_metrics_from_raw_data_computed"] is False


def test_batch_002_raw_outputs_unchanged(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["batch_002_raw_outputs_changed"] is False


def test_no_new_variants_created(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["new_variants_created"] is False


def test_variant_statuses_unchanged(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["future_preregistration_candidates_created"] is False


def test_no_formal_preregistration_recommended(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["formal_preregistration_recommended"] is False


def test_no_indicator_library_dependency_added(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["provider_download"] is False


def test_no_intraday_data_used(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(scoring_fix_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(scoring_fix_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["active_strategy_state_changed"] is False
    assert scoring_fix_run["strategies_before"] == scoring_fix_run["strategies_after"]


def test_rejected_strategy_state_preserved(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["rejected_strategy_state_changed"] is False
    assert scoring_fix_run["strategies_before"] == scoring_fix_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["sandbox_can_create_paper_candidates"] is False


def test_standalone_score_v2_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "standalone_growth_score_v2" in manifest(scoring_fix_run)["v2_score_fields"]
    assert "standalone_growth_score_v2" in rescore_rows(scoring_fix_run)[0]


def test_portfolio_contribution_score_v2_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "portfolio_contribution_score_v2" in manifest(scoring_fix_run)["v2_score_fields"]


def test_cash_underinvestment_penalty_exists(scoring_fix_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_run)
    assert "cash_allocation_penalty" in loaded["v2_score_fields"]
    assert "underinvestment_penalty" in loaded["v2_score_fields"]


def test_benchmark_lag_penalty_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "benchmark_lag_penalty" in manifest(scoring_fix_run)["v2_score_fields"]


def test_return_drag_penalty_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "return_drag_penalty_v2" in manifest(scoring_fix_run)["v2_score_fields"]


def test_duplicate_penalty_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "duplicate_penalty_v2" in manifest(scoring_fix_run)["v2_score_fields"]


def test_saturation_flag_exists(scoring_fix_run: dict[str, Any]) -> None:
    assert "score_saturation_flag" in manifest(scoring_fix_run)["v2_score_fields"]


def test_cash_heavy_benchmark_lagging_row_cannot_score_near_100() -> None:
    scored = score_row_v2(
        base_row(
            avg_cash_allocation=0.95,
            avg_symbols_held=0.1,
            trade_count=0,
            delta_vs_active_combo_180d_median=-220.0,
            return_drag_penalty=1.0,
        )
    )
    assert scored["standalone_growth_score_v2"] < 80.0


def test_high_drawdown_row_cannot_score_near_100() -> None:
    scored = score_row_v2(
        base_row(max_drawdown=-950.0, risk_buffer_vs_minus_600=-350.0, stop_risk_breach_flag="true")
    )
    assert scored["standalone_growth_score_v2"] < 80.0


def test_stretch_diagnostics_do_not_force_high_score() -> None:
    scored = score_row_v2(
        base_row(
            target_300_before_stop_rate=1.0,
            target_400_before_stop_rate=1.0,
            max_drawdown=-950.0,
            risk_buffer_vs_minus_600=-350.0,
            delta_vs_active_combo_180d_median=-200.0,
        )
    )
    assert scored["standalone_growth_score_v2"] < 80.0
    assert scored["portfolio_contribution_score_v2"] < 80.0


def test_score_saturation_prevention_passes() -> None:
    rows = score_rows_v2(source_rows())
    report = saturation_report(rows)
    assert report["saturation_failed"] is False
    assert len({round(float(row["standalone_growth_score_v2"]), 4) for row in rows}) > 1


def test_next_action_is_valid(scoring_fix_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_run)["next_action"] in fix.VALID_NEXT_ACTIONS
    assert manifest(scoring_fix_run)["next_action"] == "audit_scoring_fix_before_more_research"


def test_manifest_flags_match_strict_scope(scoring_fix_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_run)
    for key, expected in fix.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(scoring_fix_run)["consistency_passed"] is True
