from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_scoring_fix_v3 as fix_v3
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v3 import (
    calibration_report_v3,
    score_row_v3,
    score_rows_v3,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_audit import OUTPUT_DIR as BATCH_AUDIT_DIR


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
        "180d_median_final_equity": 3080.0,
        "ending_equity": 3260.0,
        "total_return": 0.09,
        "sharpe": 0.80,
        "max_drawdown": -230.0,
        "180d_worst_drawdown": -190.0,
        "risk_buffer_vs_minus_600": 370.0,
        "stop_hit_rate": 0.0,
        "stop_risk_breach_flag": "false",
        "delta_vs_active_combo_180d_median": 15.0,
        "active_combo_improvement": 20.0,
        "active_vm_dsr_pair_improvement": 12.0,
        "portfolio_return_risk_improvement": 0.08,
        "drawdown_contribution": 40.0,
        "volatility_contribution": 0.008,
        "correlation_reduction": 0.45,
        "return_drag_penalty": 0.05,
        "duplicate_penalty": 0.0,
        "corr_vs_active_combo": 0.40,
        "trade_count": 85,
        "avg_turnover": 0.04,
        "avg_cash_allocation": 0.12,
        "avg_symbols_held": 2.0,
        "max_symbol_weight": 0.55,
        "data_window_length": 900,
        "target_300_before_stop_rate": 0.0,
        "target_400_before_stop_rate": 0.0,
        "portfolio_level_risk_adjusted_improvement": 0.04,
    }
    row.update(overrides)
    return row


def source_rows() -> list[dict[str, Any]]:
    return [
        base_row(variant_id="strong", family_id="trend_momentum"),
        base_row(
            variant_id="mixed",
            family_id="breakout_continuation",
            objective_lane="portfolio_contribution_sleeve",
            avg_cash_allocation=0.45,
            delta_vs_active_combo_180d_median=-35.0,
            return_drag_penalty=0.20,
            max_drawdown=-360.0,
            risk_buffer_vs_minus_600=240.0,
        ),
        base_row(
            variant_id="cash_lagging",
            family_id="breakout_continuation",
            objective_lane="portfolio_contribution_sleeve",
            avg_cash_allocation=0.95,
            avg_symbols_held=0.05,
            trade_count=0,
            delta_vs_active_combo_180d_median=-220.0,
            return_drag_penalty=1.0,
        ),
        base_row(
            variant_id="high_drawdown",
            family_id="volatility_regime",
            max_drawdown=-980.0,
            risk_buffer_vs_minus_600=-380.0,
            stop_risk_breach_flag="true",
        ),
        base_row(
            variant_id="duplicate_combo",
            family_id="portfolio_combination_sleeve_ensemble",
            objective_lane="portfolio_contribution_sleeve",
            corr_vs_active_combo=0.99,
            duplicate_penalty=25.0,
            active_combo_improvement=-8.0,
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
            "current_next_action": "fix_revised_objective_sandbox_scoring_again",
            "official_current_next_action": "fix_revised_objective_sandbox_scoring_again",
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
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `fix_revised_objective_sandbox_scoring_again`\n",
        encoding="utf-8",
    )
    rows = source_rows()
    write_csv(root / BATCH_OUTPUT_DIR / "batch_002_variant_results.csv", rows, list(rows[0].keys()))
    write_json(root / BATCH_OUTPUT_DIR / "revised_objective_sandbox_batch_manifest.json", {"batch_id": "batch_002_revised_objective"})
    write_json(root / BATCH_AUDIT_DIR / "revised_objective_sandbox_batch_audit_manifest.json", {"family_audit_changed": False})


@pytest.fixture(scope="module")
def scoring_fix_v3_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_scoring_fix_v3")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = fix_v3.run_revised_objective_sandbox_scoring_fix_v3(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(scoring_fix_v3_run: dict[str, Any]) -> Path:
    return Path(scoring_fix_v3_run["output_dir"])


def manifest(scoring_fix_v3_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(scoring_fix_v3_run) / "scoring_fix_v3_manifest.json").read_text(encoding="utf-8"))


def consistency(scoring_fix_v3_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(scoring_fix_v3_run) / "scoring_fix_v3_consistency_check.json").read_text(encoding="utf-8"))


def rescore_rows(scoring_fix_v3_run: dict[str, Any]) -> list[dict[str, str]]:
    with (output(scoring_fix_v3_run) / "batch_002_diagnostic_rescore_v3.csv").open(
        "r", newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def test_scoring_fix_only_mode(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["scoring_fix_only"] is True


def test_scoring_version_v3(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["scoring_version"] == "v3"


def test_no_new_sandbox_batch(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["new_sandbox_batch_run"] is False


def test_batch_002_not_rerun(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["rerun_batch_002"] is False


def test_no_formal_strategy_discovery(scoring_fix_v3_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_v3_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["new_backtests_run"] is False


def test_no_new_raw_data_performance_metrics(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["new_performance_metrics_from_raw_data_computed"] is False


def test_batch_002_raw_outputs_unchanged(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["batch_002_raw_outputs_changed"] is False


def test_no_new_variants_created(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["new_variants_created"] is False


def test_variant_statuses_unchanged(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["future_preregistration_candidates_created"] is False


def test_no_formal_preregistration_recommended(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["formal_preregistration_recommended"] is False


def test_candidate_creation_blocked_from_rescore(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["candidate_creation_allowed_from_rescore"] is False


def test_no_indicator_library_dependency_added(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["provider_download"] is False


def test_no_intraday_data_used(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(scoring_fix_v3_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_v3_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(scoring_fix_v3_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_v3_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["active_strategy_state_changed"] is False
    assert scoring_fix_v3_run["strategies_before"] == scoring_fix_v3_run["strategies_after"]


def test_rejected_strategy_state_preserved(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["rejected_strategy_state_changed"] is False
    assert scoring_fix_v3_run["strategies_before"] == scoring_fix_v3_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["sandbox_can_create_paper_candidates"] is False


def test_v3_standalone_score_exists(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert "standalone_growth_score_v3" in manifest(scoring_fix_v3_run)["v3_score_fields"]
    assert "standalone_growth_score_v3" in rescore_rows(scoring_fix_v3_run)[0]


def test_v3_contribution_score_exists(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert "portfolio_contribution_score_v3" in manifest(scoring_fix_v3_run)["v3_score_fields"]


def test_v3_risk_score_exists(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert "risk_integrity_score_v3" in manifest(scoring_fix_v3_run)["v3_score_fields"]


def test_v3_risk_gate_status_exists(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert "risk_gate_status_v3" in manifest(scoring_fix_v3_run)["v3_score_fields"]


def test_v3_floor_collapse_flag_exists(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert "score_floor_collapse_flag_v3" in manifest(scoring_fix_v3_run)["v3_score_fields"]


def test_cash_heavy_benchmark_lagging_synthetic_row_does_not_score_near_100() -> None:
    scored = score_row_v3(
        base_row(
            avg_cash_allocation=0.95,
            avg_symbols_held=0.05,
            trade_count=0,
            delta_vs_active_combo_180d_median=-240.0,
            return_drag_penalty=1.0,
        )
    )
    assert scored["standalone_growth_score_v3"] < 80.0


def test_high_drawdown_synthetic_row_is_capped_but_mixed_rows_do_not_all_collapse() -> None:
    high_drawdown = score_row_v3(
        base_row(max_drawdown=-1000.0, risk_buffer_vs_minus_600=-400.0, stop_risk_breach_flag="true")
    )
    mixed = score_row_v3(
        base_row(max_drawdown=-360.0, risk_buffer_vs_minus_600=240.0, delta_vs_active_combo_180d_median=-35.0)
    )
    assert high_drawdown["standalone_growth_score_v3"] < 80.0
    assert mixed["standalone_growth_score_v3"] > 5.0


def test_moderate_mixed_evidence_scores_between_weak_and_strong() -> None:
    weak = score_row_v3(base_row(avg_cash_allocation=0.95, trade_count=0, delta_vs_active_combo_180d_median=-240.0))
    mixed = score_row_v3(base_row(max_drawdown=-360.0, risk_buffer_vs_minus_600=240.0, total_return=0.04))
    strong = score_row_v3(base_row(total_return=0.18, sharpe=1.2, delta_vs_active_combo_180d_median=60.0))
    assert weak["standalone_growth_score_v3"] < mixed["standalone_growth_score_v3"] < strong["standalone_growth_score_v3"]


def test_stretch_diagnostics_do_not_force_high_standalone_or_contribution() -> None:
    scored = score_row_v3(
        base_row(
            target_300_before_stop_rate=1.0,
            target_400_before_stop_rate=1.0,
            max_drawdown=-1000.0,
            risk_buffer_vs_minus_600=-400.0,
            delta_vs_active_combo_180d_median=-240.0,
        )
    )
    assert scored["standalone_growth_score_v3"] < 80.0
    assert scored["portfolio_contribution_score_v3"] < 80.0


def test_active_combo_duplicate_row_is_penalized_in_contribution_score() -> None:
    duplicate = score_row_v3(base_row(corr_vs_active_combo=0.99, duplicate_penalty=25.0, active_combo_improvement=-8.0))
    clean = score_row_v3(base_row(corr_vs_active_combo=0.35, duplicate_penalty=0.0, active_combo_improvement=25.0))
    assert duplicate["portfolio_contribution_score_v3"] < clean["portfolio_contribution_score_v3"]


def test_saturation_prevention_passes() -> None:
    rows = score_rows_v3(source_rows())
    report = calibration_report_v3(rows)
    assert report["standalone_saturation_failed"] is False


def test_floor_collapse_prevention_passes() -> None:
    rows = score_rows_v3(source_rows())
    report = calibration_report_v3(rows)
    assert report["standalone_floor_collapse_failed"] is False


def test_next_action_is_valid(scoring_fix_v3_run: dict[str, Any]) -> None:
    assert manifest(scoring_fix_v3_run)["next_action"] in fix_v3.VALID_NEXT_ACTIONS
    assert manifest(scoring_fix_v3_run)["next_action"] == "audit_scoring_fix_v3_before_more_research"


def test_manifest_flags_match_strict_scope(scoring_fix_v3_run: dict[str, Any]) -> None:
    loaded = manifest(scoring_fix_v3_run)
    for key, expected in fix_v3.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(scoring_fix_v3_run)["consistency_passed"] is True
