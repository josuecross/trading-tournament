from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import fixed_scoring_rerun_audit as audit
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_v3_rerun import (
    OUTPUT_DIR as RERUN_DIR,
)


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


def family_rows() -> list[dict[str, Any]]:
    return [
        {
            "family_id": "breakout_continuation",
            "family_status": "sandbox_family_interesting",
            "variants_evaluated": 18,
            "median_standalone_growth_score": 20.67,
            "median_portfolio_contribution_score": 49.44,
            "median_risk_integrity_score": 51.83,
            "median_overfit_risk_score": 32.8,
            "median_practicality_score": 57.0,
            "positive_180d_progress_variants": 18,
            "acceptable_drawdown_risk_integrity_variants": 9,
            "useful_contribution_evidence_variants": 0,
            "stretch_diagnostic_hits": 0,
        },
        {
            "family_id": "macro_portfolio_contribution",
            "family_status": "sandbox_family_weak",
            "variants_evaluated": 12,
            "median_standalone_growth_score": 17.33,
            "median_portfolio_contribution_score": 46.78,
            "median_risk_integrity_score": 27.82,
            "median_overfit_risk_score": 24.0,
            "median_practicality_score": 53.25,
            "positive_180d_progress_variants": 12,
            "acceptable_drawdown_risk_integrity_variants": 4,
            "useful_contribution_evidence_variants": 0,
            "stretch_diagnostic_hits": 0,
        },
    ]


def variant_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, family_id in enumerate(["breakout_continuation", "macro_portfolio_contribution"]):
        rows.append(
            {
                "variant_id": f"v{index}",
                "family_id": family_id,
                "status": "sandbox_family_weak",
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "standalone_growth_score_v3": 25.0,
                "portfolio_contribution_score_v3": 45.0,
                "risk_integrity_score_v3": 30.0,
                "risk_gate_status_v3": "soft_warn",
                "score_saturation_flag_v3": "false",
                "score_floor_collapse_flag_v3": "false",
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
            "current_next_action": "audit_fixed_scoring_revised_objective_sandbox_rerun",
            "official_current_next_action": "audit_fixed_scoring_revised_objective_sandbox_rerun",
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
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `audit_fixed_scoring_revised_objective_sandbox_rerun`\n",
        encoding="utf-8",
    )
    rerun_dir = root / RERUN_DIR
    write_json(
        rerun_dir / "fixed_scoring_rerun_manifest.json",
        {
            "fixed_scoring_rerun": True,
            "batch_id": "batch_002_revised_objective",
            "scoring_version": "v3",
            "preflight_passed": True,
            "preflight_failures": [],
            "preflight_warnings": [],
            "variant_count_planned": 80,
            "variant_count_evaluated": 80,
            "family_count_evaluated": 5,
            "sandbox_future_preregistration_candidate_count": 0,
            "families_actionable_count": 0,
            "sandbox_results_non_promotable": True,
            "active_strategy_state_changed": False,
            "rejected_strategy_state_changed": False,
            "intraday_research_remains_paused": True,
        },
    )
    write_json(rerun_dir / "fixed_scoring_rerun_consistency_check.json", {"consistency_passed": True})
    write_csv(rerun_dir / "batch_002_v3_family_summary.csv", family_rows(), list(family_rows()[0].keys()))
    write_csv(rerun_dir / "batch_002_v3_variant_results.csv", variant_rows(), list(variant_rows()[0].keys()))


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("fixed_scoring_rerun_audit")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_fixed_scoring_rerun_audit(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "fixed_scoring_rerun_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "fixed_scoring_rerun_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_fixed_scoring_rerun_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["fixed_scoring_rerun_audit_only"] is True


def test_audited_batch_id(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["audited_batch_id"] == "batch_002_revised_objective"


def test_scoring_version_v3(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["scoring_version"] == "v3"


def test_no_new_sandbox_batch(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_sandbox_batch_run"] is False


def test_batch_002_not_rerun_by_audit(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["rerun_batch_002"] is False


def test_no_formal_strategy_discovery(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_backtests_run"] is False


def test_no_raw_data_performance_metrics(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_performance_metrics_from_raw_data_computed"] is False


def test_no_new_variants_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_variants_created"] is False


def test_variant_statuses_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["variant_statuses_changed"] is False


def test_family_statuses_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["family_statuses_changed"] is False


def test_no_future_preregistration_candidates_created_by_audit(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["future_preregistration_candidates_created"] is False


def test_no_formal_preregistration_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["formal_preregistration_created"] is False


def test_candidate_creation_blocked_from_audit(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_creation_allowed_from_audit"] is False


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


def test_rerun_consistency_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "rerun_consistency_review.md").exists()


def test_family_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "family_audit_v3.md").exists()


def test_future_preregistration_decision_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "future_preregistration_decision.md").exists()


def test_active_observation_recommendation_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "active_observation_recommendation.md").exists()


def test_do_not_promote_file_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "do_not_promote_after_rerun.md").exists()


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS
    assert manifest(audit_run)["next_action"] == "continue_paper_forward_observation_only"


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["formal_preregistration_recommended"] is False
    assert loaded["breakout_manual_review_recommended"] is False
    assert consistency(audit_run)["consistency_passed"] is True
