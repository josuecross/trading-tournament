from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import role_aware_robustness_internal_capture_asymmetry_63d_top3_v1 as subject


OUTPUT = ROOT / "evidence" / "robustness" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exact_candidate_scope_and_methodology_role() -> None:
    standard = subject.load_standard()
    assert subject.STRATEGY_ID == "internal_capture_asymmetry_63d_top3_v1"
    assert subject.PARENT_TRIAL_ID == "accepted47_internal_v1__capture63__top3"
    assert subject.PRIMARY_ROLE == "cross_sectional_allocation_strategy"
    assert subject.PRIMARY_ROLE in standard["primary_role_taxonomy"]
    assert subject.PRIMARY_ROLE not in standard.get("role_specific_hard_gate_contracts", {})


def test_run_outputs_required_packet_and_positive_outcome() -> None:
    result = subject.run()
    assert result["outcome"] == "robustness_positive"
    assert result["failure_reason"] == ""
    assert result["exact_next_action"] == subject.NEXT_POSITIVE
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS


def test_direction_routing_preserves_parent_partial_block() -> None:
    routing = rows("direction_routing_record.csv")
    assert len(routing) == 1
    assert routing[0]["historical_batch_outcome"] == "targeted_internal_batch_partially_blocked"
    assert routing[0]["candidate_specific_state"] == "exploratory_followup_candidate"
    assert routing[0]["direction_decision"] == "advance_existing_followup_to_role_aware_robustness"
    assert routing[0]["batch_wide_block_review_required_before_candidate_robustness"] == "false"


def test_reproduction_and_universal_gates_pass() -> None:
    reproduction = rows("reproduction_results.csv")
    assert reproduction
    assert all(row["reproduction_pass"] == "true" for row in reproduction)
    gates = rows("applicable_gate_matrix.csv")
    blocking = [row for row in gates if row["blocking_or_diagnostic"] == "blocking" and row["applicable"] == "true"]
    assert blocking
    assert all(row["gate_result"] == "pass" for row in blocking)
    role_rows = [row for row in gates if row["gate_id"] == "cross_sectional_allocation_strategy_role_specific_hard_gate_contract"]
    assert len(role_rows) == 1
    assert role_rows[0]["applicable"] == "false"


def test_multiple_testing_and_entity_counts_are_bounded() -> None:
    lineage = {row["lineage_item"]: row["value"] for row in rows("multiple_testing_lineage.csv")}
    assert lineage["architectures_preregistered_in_parent_batch"] == "3"
    assert lineage["canonical_configurations_preregistered"] == "12"
    assert lineage["configurations_actually_performance_executed"] == "8"
    assert lineage["current_robustness_candidate"] == "A1 only"
    counts = json.loads((OUTPUT / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["existing_strategy_configurations_referenced"] == 1
    assert counts["new_strategy_configurations"] == 0
    assert counts["new_robustness_trials"] == 1
    assert counts["paper_demo_eligibility_records"] == 0
    assert counts["handoff_export_packets"] == 0
    assert counts["forward_observations"] == 0


def test_diagnostics_present_but_not_counted_as_trials() -> None:
    assert len(rows("rolling_window_results.csv")) == 6
    assert len(rows("bootstrap_results.csv")) == 3
    assert all(row["blocking_applicable_for_role"] == "false" for row in rows("bootstrap_results.csv"))
    assert len(rows("asset_incremental_attribution.csv")) == 13
    assert len(rows("economic_bucket_attribution.csv")) >= 7
    assert rows("role_valid_concentration_results.csv")


def test_manifest_and_consistency() -> None:
    manifest = yaml.safe_load((OUTPUT / "robustness_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["strategy_id"] == subject.STRATEGY_ID
    assert manifest["parameters"]["lookback_sessions"] == 63
    assert manifest["parameters"]["top_k"] == 3
    assert manifest["robustness_outcome"] == "robustness_positive"
    assert manifest["provider_access"] is False
    assert manifest["network_access"] is False
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["checks"]["architecture_b_duplicate_does_not_block_a1"] is True
    assert consistency["checks"]["a2_a3_a4_not_reconsidered"] is True
    assert consistency["checks"]["protected_state_and_cache_unchanged"] is True


def test_deterministic_rerun_hash_stable() -> None:
    before = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    subject.run()
    after = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    assert after == before
