from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_scoring_fix_audit as audit
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_audit import OUTPUT_DIR as BATCH_AUDIT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix import OUTPUT_DIR as SCORING_FIX_DIR


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


def rescore_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    families = (
        "breakout_continuation",
        "macro_portfolio_contribution",
        "portfolio_combination_sleeve_ensemble",
        "trend_momentum",
        "volatility_regime",
    )
    for index in range(80):
        family_id = families[index % len(families)]
        near_zero = index < 34
        rows.append(
            {
                "variant_id": f"v{index:03d}",
                "family_id": family_id,
                "status": "sandbox_family_weak",
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "score_interpretation_status": "diagnostic_only",
                "standalone_growth_score_v2": 0.0 if near_zero else 35.0,
                "portfolio_contribution_score_v2": 8.0 if family_id == "portfolio_combination_sleeve_ensemble" else 32.0,
                "stretch_diagnostic_score_v2": 20.0,
                "risk_integrity_score_v2": 0.0 if index % 3 else 25.0,
                "overfit_risk_score_v2": 42.0,
                "practicality_score_v2": 40.0,
                "cash_allocation_penalty": 15.0 if family_id == "breakout_continuation" else 0.0,
                "underinvestment_penalty": 8.0 if family_id == "breakout_continuation" else 0.0,
                "benchmark_lag_penalty": 38.0 if family_id in {"breakout_continuation", "macro_portfolio_contribution"} else 2.0,
                "return_drag_penalty_v2": 25.0 if family_id in {"breakout_continuation", "macro_portfolio_contribution"} else 0.0,
                "duplicate_penalty_v2": 36.0 if family_id == "portfolio_combination_sleeve_ensemble" else 0.0,
                "score_saturation_flag": "false",
            }
        )
    return rows


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "audit_scoring_fix_before_more_research",
            "official_current_next_action": "audit_scoring_fix_before_more_research",
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
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `audit_scoring_fix_before_more_research`\n",
        encoding="utf-8",
    )

    rows = rescore_rows()
    scoring_fix = root / SCORING_FIX_DIR
    write_csv(scoring_fix / "batch_002_diagnostic_rescore.csv", rows, list(rows[0].keys()))
    write_json(
        scoring_fix / "scoring_fix_manifest.json",
        {
            "diagnostic_rescore_performed": True,
            "diagnostic_rescore_status": "performed_existing_saved_batch_002_fields_only",
            "candidate_creation_allowed_from_rescore": False,
            "batch_002_raw_outputs_changed": False,
            "variant_statuses_changed": False,
            "family_audit_changed": False,
        },
    )
    write_json(scoring_fix / "scoring_fix_consistency_check.json", {"consistency_passed": True})
    write_json(root / BATCH_OUTPUT_DIR / "revised_objective_sandbox_batch_manifest.json", {"batch_id": "batch_002_revised_objective"})
    write_csv(
        root / BATCH_OUTPUT_DIR / "batch_002_variant_results.csv",
        [{"variant_id": "v001", "status": "sandbox_family_weak"}],
        ["variant_id", "status"],
    )
    write_json(root / BATCH_AUDIT_DIR / "revised_objective_sandbox_batch_audit_manifest.json", {"family_audit_changed": False})


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_scoring_fix_audit")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_revised_objective_sandbox_scoring_fix_audit(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "scoring_fix_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "scoring_fix_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_scoring_fix_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["scoring_fix_audit_only"] is True


def test_no_new_sandbox_batch(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_sandbox_batch_run"] is False


def test_batch_002_not_rerun(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["rerun_batch_002"] is False


def test_no_formal_strategy_discovery(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_backtests_run"] is False


def test_no_new_raw_data_performance_metrics(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_performance_metrics_from_raw_data_computed"] is False


def test_batch_002_raw_outputs_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["batch_002_raw_outputs_changed"] is False


def test_diagnostic_rescore_reviewed(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["diagnostic_rescore_reviewed"] is True


def test_no_new_variants_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_variants_created"] is False


def test_variant_statuses_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["future_preregistration_candidates_created"] is False


def test_no_formal_preregistration_recommended(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["formal_preregistration_recommended"] is False


def test_candidate_creation_blocked_from_rescore(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_creation_allowed_from_rescore"] is False


def test_no_indicator_library_dependency_added(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_intraday_data_used(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["active_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_rejected_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["rejected_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_can_create_paper_candidates"] is False


def test_score_distribution_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "score_distribution_review.md").exists()


def test_family_level_v2_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "family_level_v2_review.md").exists()


def test_do_not_promote_from_rescore_file_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "do_not_promote_from_rescore.md").exists()


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS
    assert manifest(audit_run)["next_action"] == "fix_revised_objective_sandbox_scoring_again"


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["saturation_fixed"] is True
    assert loaded["overcorrection_found"] is True
    assert loaded["v2_calibration_accepted"] is False
    assert consistency(audit_run)["consistency_passed"] is True
