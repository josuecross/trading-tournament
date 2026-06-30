from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import objective_reset_review as review


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
            "current_next_action": "create_objective_reset_review",
            "official_current_next_action": "create_objective_reset_review",
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
    roadmap.write_text("# Research Roadmap\n\n## Compact Current State\n\n- Next action: `create_objective_reset_review`\n", encoding="utf-8")

    manual_dir = root / review.MANUAL_REVIEW_DIR
    write_json(
        manual_dir / "manual_review_after_packet_fix_manifest.json",
        {
            "packet_fix_accepted": True,
            "batch_001_accepted_as_non_promotable_exploration": True,
            "families_actionable_count": 0,
            "future_preregistration_candidate_count": 0,
            "objective_reset_needed": True,
            "next_action": "create_objective_reset_review",
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
    family_rows = [
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
        {
            "family_id": "volatility_regime",
            "source_status": "sandbox_family_weak",
            "actionable_now": "False",
            "audit_conclusion": "risk-buffer failure",
        },
    ]
    write_csv(audit_dir / "sandbox_family_audit.csv", family_rows, ["family_id", "source_status", "actionable_now", "audit_conclusion"])
    (audit_dir / "sandbox_family_audit.md").write_text("family audit unchanged\n", encoding="utf-8")


@pytest.fixture(scope="module")
def objective_review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("objective_reset_review")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_objective_reset_review(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(objective_review_run: dict[str, Any]) -> Path:
    return Path(objective_review_run["output_dir"])


def manifest(objective_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(objective_review_run) / "objective_reset_review_manifest.json").read_text(encoding="utf-8"))


def consistency(objective_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(objective_review_run) / "objective_reset_consistency_check.json").read_text(encoding="utf-8"))


def test_objective_review_only_mode(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["objective_review_only"] is True


def test_no_new_sandbox_batch(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(objective_review_run: dict[str, Any]) -> None:
    loaded = manifest(objective_review_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["new_performance_metrics_computed"] is False


def test_sandbox_results_unchanged(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["future_preregistration_candidates_created"] is False


def test_no_indicator_library_dependency_added(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["provider_download"] is False


def test_no_intraday_data_used(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(objective_review_run: dict[str, Any]) -> None:
    loaded = manifest(objective_review_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(objective_review_run: dict[str, Any]) -> None:
    loaded = manifest(objective_review_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["active_strategy_state_changed"] is False
    assert objective_review_run["strategies_before"] == objective_review_run["strategies_after"]


def test_rejected_strategy_state_preserved(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["rejected_strategy_state_changed"] is False
    assert objective_review_run["strategies_before"] == objective_review_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["intraday_research_remains_paused"] is True


def test_objective_diagnosis_exists(objective_review_run: dict[str, Any]) -> None:
    assert (output(objective_review_run) / "current_objective_diagnosis.md").exists()


def test_constraint_conflict_map_exists(objective_review_run: dict[str, Any]) -> None:
    path = output(objective_review_run) / "constraint_conflict_map.csv"
    assert path.exists()
    rows = list(csv.DictReader(path.open("r", newline="", encoding="utf-8")))
    assert len(rows) >= 13


def test_objective_profiles_review_exists(objective_review_run: dict[str, Any]) -> None:
    assert (output(objective_review_run) / "objective_profiles_review.md").exists()


def test_recommended_objective_exists(objective_review_run: dict[str, Any]) -> None:
    loaded = manifest(objective_review_run)
    assert loaded["recommended_objective_profile"] == review.RECOMMENDED_OBJECTIVE_PROFILE
    assert (output(objective_review_run) / "recommended_objective.md").exists()


def test_active_observation_policy_exists(objective_review_run: dict[str, Any]) -> None:
    assert (output(objective_review_run) / "active_observation_policy.md").exists()


def test_forbidden_next_steps_exists(objective_review_run: dict[str, Any]) -> None:
    assert (output(objective_review_run) / "forbidden_next_steps.md").exists()


def test_next_action_is_valid(objective_review_run: dict[str, Any]) -> None:
    assert manifest(objective_review_run)["next_action"] in review.VALID_NEXT_ACTIONS
    assert manifest(objective_review_run)["next_action"] == "define_revised_etf_wrapper_objective"


def test_manifest_flags_match_strict_scope(objective_review_run: dict[str, Any]) -> None:
    loaded = manifest(objective_review_run)
    for key, expected in review.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(objective_review_run)["consistency_passed"] is True
