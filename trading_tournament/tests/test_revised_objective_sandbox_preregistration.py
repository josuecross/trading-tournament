from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_preregistration as review


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


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "pre_register_revised_objective_sandbox_batch",
            "official_current_next_action": "pre_register_revised_objective_sandbox_batch",
            "intraday_research_remains_paused": True,
        },
        "strategies": [
            {
                "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "mfv_equal_weight_trend_filter_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / config.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap = root / config.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `pre_register_revised_objective_sandbox_batch`\n",
        encoding="utf-8",
    )

    revised_objective_dir = root / review.REVISED_OBJECTIVE_DIR
    write_json(
        revised_objective_dir / "revised_etf_objective_manifest.json",
        {
            "revised_objective_profile": "realistic_etf_wrapper_growth_objective",
            "old_dollar_target_reclassified_as_stretch_diagnostic": True,
            "standard_lane_leverage_allowed": False,
            "batch_002_directly_authorized": False,
            "next_action": "pre_register_revised_objective_sandbox_batch",
        },
    )

    batch_dir = root / review.BATCH_DIR
    write_json(
        batch_dir / "sandbox_batch_manifest.json",
        {
            "variant_count_planned": 80,
            "variant_count_evaluated": 80,
            "families_evaluated_count": 7,
            "sandbox_future_preregistration_candidate_count": 0,
        },
    )
    write_csv(
        batch_dir / "sandbox_variant_results.csv",
        [{"variant_id": "v1", "status": "sandbox_family_weak", "promotable": "false", "paper_candidate_allowed": "false"}],
        ["variant_id", "status", "promotable", "paper_candidate_allowed"],
    )
    for name in [
        "sandbox_family_summary.csv",
        "sandbox_benchmark_comparison_summary.csv",
        "sandbox_risk_summary.csv",
        "sandbox_diversification_summary.csv",
        "sandbox_practicality_summary.csv",
    ]:
        write_csv(batch_dir / name, [{"family_id": "breakout_continuation"}], ["family_id"])

    audit_dir = root / review.BATCH_AUDIT_DIR
    write_json(
        audit_dir / "sandbox_batch_audit_manifest.json",
        {
            "sandbox_results_remain_non_promotable": True,
            "forbidden_statuses_absent": True,
            "promotable_true_count": 0,
            "paper_candidate_allowed_true_count": 0,
            "families_actionable_count": 0,
            "source_future_preregistration_candidate_count": 0,
        },
    )
    write_csv(
        audit_dir / "sandbox_family_audit.csv",
        [
            {
                "family_id": "breakout_continuation",
                "source_status": "sandbox_family_interesting",
                "actionable_now": "False",
                "audit_conclusion": "useful diversifier clue, but not actionable",
            },
            {
                "family_id": "portfolio_combination_sleeve_ensemble",
                "source_status": "sandbox_family_interesting",
                "actionable_now": "False",
                "audit_conclusion": "mostly repackages active combo behavior",
            },
        ],
        ["family_id", "source_status", "actionable_now", "audit_conclusion"],
    )
    (audit_dir / "sandbox_family_audit.md").write_text("family audit unchanged\n", encoding="utf-8")


@pytest.fixture(scope="module")
def prereg_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_preregistration")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_revised_objective_sandbox_preregistration(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(prereg_run: dict[str, Any]) -> Path:
    return Path(prereg_run["output_dir"])


def manifest(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(prereg_run) / "revised_objective_sandbox_preregistration_manifest.json").read_text(encoding="utf-8")
    )


def consistency(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(prereg_run) / "revised_objective_sandbox_consistency_check.json").read_text(encoding="utf-8"))


def test_sandbox_preregistration_only_mode(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["sandbox_preregistration_only"] is True


def test_no_new_sandbox_batch(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["new_sandbox_batch_run"] is False
    assert manifest(prereg_run)["batch_002_directly_run"] is False


def test_no_formal_strategy_discovery(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["new_performance_metrics_computed"] is False


def test_sandbox_results_unchanged(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["future_preregistration_candidates_created"] is False


def test_no_indicator_library_dependency_added(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["provider_download"] is False


def test_no_intraday_data_used(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["active_strategy_state_changed"] is False
    assert prereg_run["strategies_before"] == prereg_run["strategies_after"]


def test_rejected_strategy_state_preserved(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["rejected_strategy_state_changed"] is False
    assert prereg_run["strategies_before"] == prereg_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["intraday_research_remains_paused"] is True


def test_batch_purpose_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "batch_002_purpose.md").exists()


def test_batch_001_lessons_applied_file_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "batch_001_lessons_applied.md").exists()


def test_family_selection_file_exists(prereg_run: dict[str, Any]) -> None:
    path = output(prereg_run) / "planned_family_variant_plan.csv"
    rows = list(csv.DictReader(path.open("r", newline="", encoding="utf-8")))
    assert len([row for row in rows if row["planned_status"] != "deprioritized_not_in_batch_002"]) == 5
    assert (output(prereg_run) / "revised_batch_family_selection.md").exists()


def test_revised_scoring_framework_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "revised_scoring_framework.md").read_text(encoding="utf-8")
    assert "standalone_growth_score" in text
    assert "portfolio_contribution_score" in text


def test_target_tier_application_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "target_tier_application.md").exists()


def test_portfolio_contribution_scoring_plan_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "portfolio_contribution_scoring_plan.md").exists()


def test_stretch_diagnostic_policy_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "stretch_diagnostic_policy.md").read_text(encoding="utf-8")
    assert "not a hard gate" in text


def test_do_not_run_file_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "do_not_run_batch_now.md").exists()


def test_next_action_is_valid(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["next_action"] in review.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "implement_revised_objective_sandbox_batch"


def test_manifest_flags_match_strict_scope(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    for key, expected in review.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["planned_batch_id"] == review.PLANNED_BATCH_ID
    assert loaded["planned_max_variants"] == review.PLANNED_MAX_VARIANTS
    assert loaded["planned_family_count"] == review.PLANNED_FAMILY_COUNT
    assert loaded["old_dollar_target_is_hard_gate"] is False
    assert loaded["sandbox_results_can_promote"] is False
    assert consistency(prereg_run)["consistency_passed"] is True
