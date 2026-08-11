from __future__ import annotations

import csv
import json
from collections import Counter

import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_expansion_discovery_yield_evidence_packet_v2 as subject


OUTPUT = ROOT / "evidence" / "research_recovery" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run() -> dict[str, object]:
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_required_packet_and_current_batch_reconciliation() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["task_outcome"] == "phase2_expansion_yield_evidence_complete"
    assert consistency["current_batch_deterministic_hash"] == (
        "sha256:a99e691a48ac4a1d5a27af33a4a25d97c55667dcacdb57b29f67822dee68b159"
    )
    assert consistency["checks"]["current_batch_metrics_reconcile"] is True
    assert consistency["exact_next_action"] == subject.NEXT_ACTION


def test_phase2_and_accepted47_counts_are_separate_and_exact() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    phase2 = consistency["phase2_counts"]
    baseline = consistency["accepted47_counts"]
    assert phase2 == {
        "architectures": 3,
        "architectures_with_followup": 1,
        "eligibility_handoff_outcomes": 0,
        "followups": 1,
        "robustness_passes": 0,
        "robustness_trials": 1,
        "trials": 6,
    }
    assert baseline == {
        "architectures": 15,
        "architectures_with_followup": 4,
        "eligibility_handoff_outcomes": 1,
        "followups": 4,
        "robustness_passes": 1,
        "robustness_trials": 4,
        "trials": 36,
    }


def test_funnel_does_not_count_controls_or_rejections_as_trials() -> None:
    funnel = {row["funnel_stage"]: int(row["count"]) for row in rows("phase2_discovery_funnel.csv")}
    assert funnel["serious_external_source_packages_reviewed"] == 2
    assert funnel["internal_concepts_seriously_assessed"] == 1
    assert funnel["canonical_strategy_configurations"] == 6
    assert funnel["canonical_trials"] == 6
    assert funnel["exploratory_followups"] == 1
    assert funnel["robustness_trials_launched"] == 1
    assert funnel["robustness_passes"] == 0
    assert funnel["research_eligibility_handoff_outcomes"] == 0


def test_failure_categories_retain_reasons_and_reconcile() -> None:
    failures = rows("failure_category_reconciliation.csv")
    assert len(failures) == 41
    counts = Counter(row["normalized_category"] for row in failures)
    assert counts.most_common(2) == [
        ("named_control_dominance", 9),
        ("benchmark_like_behavior", 9),
    ] or counts.most_common(2) == [
        ("benchmark_like_behavior", 9),
        ("named_control_dominance", 9),
    ]
    assert counts["other"] == 6
    assert counts["static_or_exposure_control_dominance"] == 4
    assert all(row["exact_repository_failure_reason"] for row in failures)
    assert all(int(row["closure_count_denominator"]) == 41 for row in failures)


def test_control_gate_information_set_and_exact_failure_causes() -> None:
    primary = [row for row in rows("control_gate_audit.csv") if float(row["cost_bps_one_way"]) == 5.0]
    assert len(primary) == 4
    assert all(row["static_control_dominates"] == "true" for row in primary)
    equal_dominators = {row["configuration_code"] for row in primary if row["equal_weight_control_dominates"] == "true"}
    assert equal_dominators == {"P3"}
    assert all(row["combined_gate_pass"] == "false" for row in primary)
    assert all(row["target_decision_formations_used"] == "227" for row in primary)
    assert all(row["selection_formations_contributing"] == "136" for row in primary)
    assert all(row["reserved_evaluation_formations_contributing"] == "91" for row in primary)
    assert all(row["weights_fixed_before_selection"] == "false" for row in primary)
    assert all(row["selection_period_information_used"] == "true" for row in primary)
    assert all(row["reserved_evaluation_decisions_used"] == "true" for row in primary)
    assert all(row["ex_ante_investable_as_constructed"] == "false" for row in primary)


def test_cost_rows_are_diagnostics_except_five_bps() -> None:
    audit = rows("control_gate_audit.csv")
    assert len(audit) == 12
    by_cost = Counter((float(row["cost_bps_one_way"]), row["cost_role"]) for row in audit)
    assert by_cost[(0.0, "diagnostic_only")] == 4
    assert by_cost[(5.0, "primary_selection_gate")] == 4
    assert by_cost[(10.0, "diagnostic_only")] == 4


def test_reserved_evaluation_performance_remains_unopened() -> None:
    reconciliation = rows("evaluation_access_reconciliation.csv")
    assert len(reconciliation) == 4
    assert all(row["reserved_evaluation_accessed"] == "false" for row in reconciliation)
    assert all(row["reserved_evaluation_performance_row_count"] == "0" for row in reconciliation)
    assert all(row["evaluation_performance_calculated"] == "false" for row in reconciliation)
    assert all(row["evaluation_signal_decisions_present_in_static_control"] == "true" for row in reconciliation)
    assert all(row["evaluation_signal_decision_count"] == "91" for row in reconciliation)


def test_phase2_group_coverage_is_count_based() -> None:
    coverage = rows("phase2_group_coverage.csv")
    assert len(coverage) == 7
    assert sum(int(row["phase2_added_symbol_count"]) for row in coverage) == 41
    classifications = Counter(row["coverage_classification"] for row in coverage)
    assert classifications == Counter({"unexplored": 4, "materially_explored": 2, "lightly_explored": 1})
    materially_explored = {
        row["capability_group"] for row in coverage if row["coverage_classification"] == "materially_explored"
    }
    assert materially_explored == {"factor/style", "U.S. industries"}


def test_bottlenecks_are_indicators_not_direction_choices() -> None:
    bottlenecks = rows("bottleneck_indicators.csv")
    assert {row["indicator"] for row in bottlenecks} == {
        "candidate_supply_bottleneck",
        "source_rule_completeness_bottleneck",
        "duplicate_saturation_bottleneck",
        "control_gate_bottleneck",
        "cost_turnover_bottleneck",
        "robustness_bottleneck",
        "insufficient_phase2_group_coverage",
        "phase2_expansion_not_materially_improving_yield",
    }
    assert all(row["confidence"] in {"high", "medium", "low"} for row in bottlenecks)


def test_no_prohibited_action_and_deterministic_rerun(completed_run: dict[str, object]) -> None:
    first_hash = completed_run["deterministic_evidence_packet_hash"]
    second = subject.run()
    assert second["overall_pass"] is True
    assert second["deterministic_evidence_packet_hash"] == first_hash
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert all(value is False for value in consistency["forbidden_actions"].values())
    assert consistency["checks"]["protected_evidence_and_caches_unchanged"] is True
    assert all(consistency["checks"].values())
