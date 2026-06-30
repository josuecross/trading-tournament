from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_batch as impl
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    BATCH_ID,
    EXCLUDED_FAMILIES,
    INCLUDED_FAMILIES,
    INITIAL_STATUS,
    MAX_FAMILIES,
    MAX_TOTAL_VARIANTS,
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


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "implement_revised_objective_sandbox_batch",
            "official_current_next_action": "implement_revised_objective_sandbox_batch",
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
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `implement_revised_objective_sandbox_batch`\n",
        encoding="utf-8",
    )

    prereg_dir = root / impl.PREREGISTRATION_DIR
    write_json(
        prereg_dir / "revised_objective_sandbox_preregistration_manifest.json",
        {
            "sandbox_preregistration_only": True,
            "planned_batch_id": BATCH_ID,
            "planned_max_variants": MAX_TOTAL_VARIANTS,
            "planned_family_count": MAX_FAMILIES,
            "old_dollar_target_is_hard_gate": False,
            "sandbox_results_can_promote": False,
            "batch_002_directly_run": False,
            "next_action": "implement_revised_objective_sandbox_batch",
        },
    )

    batch_dir = root / impl.BATCH_DIR
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

    audit_dir = root / impl.BATCH_AUDIT_DIR
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
            }
        ],
        ["family_id", "source_status", "actionable_now", "audit_conclusion"],
    )
    (audit_dir / "sandbox_family_audit.md").write_text("family audit unchanged\n", encoding="utf-8")


@pytest.fixture(scope="module")
def implementation_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_implementation")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = impl.run_revised_objective_sandbox_implementation(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(implementation_run: dict[str, Any]) -> Path:
    return Path(implementation_run["output_dir"])


def manifest(implementation_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(implementation_run) / "revised_objective_sandbox_implementation_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def consistency(implementation_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(implementation_run) / "revised_objective_sandbox_implementation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def variant_rows(implementation_run: dict[str, Any]) -> list[dict[str, str]]:
    path = output(implementation_run) / "batch_002_dry_run_variant_plan.csv"
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_sandbox_implementation_only_mode(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["sandbox_implementation_only"] is True


def test_batch_id_is_revised_objective_batch(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["batch_id"] == BATCH_ID


def test_no_new_sandbox_batch(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(implementation_run: dict[str, Any]) -> None:
    loaded = manifest(implementation_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["new_performance_metrics_computed"] is False


def test_sandbox_results_unchanged(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["future_preregistration_candidates_created"] is False


def test_no_indicator_library_dependency_added(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["provider_download"] is False


def test_no_intraday_data_used(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(implementation_run: dict[str, Any]) -> None:
    loaded = manifest(implementation_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(implementation_run: dict[str, Any]) -> None:
    loaded = manifest(implementation_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["active_strategy_state_changed"] is False
    assert implementation_run["strategies_before"] == implementation_run["strategies_after"]


def test_rejected_strategy_state_preserved(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["rejected_strategy_state_changed"] is False
    assert implementation_run["strategies_before"] == implementation_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["intraday_research_remains_paused"] is True


def test_dry_run_variant_plan_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "batch_002_dry_run_variant_plan.csv").exists()


def test_planned_variant_count_within_limit(implementation_run: dict[str, Any]) -> None:
    rows = variant_rows(implementation_run)
    assert len(rows) == manifest(implementation_run)["planned_variant_count"]
    assert len(rows) <= MAX_TOTAL_VARIANTS


def test_planned_family_count_within_limit(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["planned_family_count"] <= MAX_FAMILIES


def test_included_families_match_preregistration(implementation_run: dict[str, Any]) -> None:
    rows = variant_rows(implementation_run)
    assert set(row["family_id"] for row in rows) == set(INCLUDED_FAMILIES)


def test_excluded_families_match_preregistration(implementation_run: dict[str, Any]) -> None:
    rows = variant_rows(implementation_run)
    assert not (set(row["family_id"] for row in rows) & set(EXCLUDED_FAMILIES))
    assert set(manifest(implementation_run)["excluded_families"]) == set(EXCLUDED_FAMILIES)


def test_every_planned_variant_not_promotable(implementation_run: dict[str, Any]) -> None:
    assert all(row["promotable"] == "false" for row in variant_rows(implementation_run))


def test_every_planned_variant_no_paper_candidate(implementation_run: dict[str, Any]) -> None:
    assert all(row["paper_candidate_allowed"] == "false" for row in variant_rows(implementation_run))


def test_every_planned_variant_non_promotable_status(implementation_run: dict[str, Any]) -> None:
    assert all(row["status"] == INITIAL_STATUS for row in variant_rows(implementation_run))


def test_forbidden_statuses_are_blocked(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["forbidden_statuses_blocked"] is True


def test_revised_scoring_schema_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "revised_scoring_schema.md").exists()


def test_target_tier_mapping_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "target_tier_mapping.md").exists()


def test_portfolio_contribution_schema_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "portfolio_contribution_schema.md").exists()


def test_stretch_diagnostic_schema_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "stretch_diagnostic_schema.md").exists()


def test_old_dollar_target_is_not_hard_gate(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["old_dollar_target_is_hard_gate"] is False


def test_stretch_diagnostics_are_not_promotion_gates(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["stretch_diagnostics_are_promotion_gates"] is False


def test_do_not_run_file_exists(implementation_run: dict[str, Any]) -> None:
    assert (output(implementation_run) / "do_not_run_batch_now.md").exists()


def test_next_action_is_valid(implementation_run: dict[str, Any]) -> None:
    assert manifest(implementation_run)["next_action"] in impl.VALID_NEXT_ACTIONS
    assert manifest(implementation_run)["next_action"] == "run_revised_objective_sandbox_batch"


def test_manifest_flags_match_strict_scope(implementation_run: dict[str, Any]) -> None:
    loaded = manifest(implementation_run)
    for key, expected in impl.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(implementation_run)["consistency_passed"] is True
