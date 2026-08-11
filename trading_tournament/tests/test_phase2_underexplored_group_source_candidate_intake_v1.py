from __future__ import annotations

import csv
import json
from collections import Counter

import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_underexplored_group_source_candidate_intake_v1 as subject


OUTPUT = ROOT / "evidence" / "public_source_strategy_intake" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run() -> dict[str, object]:
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_required_packet_and_zero_qualification_outcome() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["task_outcome"] == "phase2_underexplored_group_no_candidate_qualified"
    assert consistency["exact_next_action"] == "direction_owner_review_phase2_candidate_supply_v2"
    assert consistency["overall_pass"] is True


def test_exactly_nine_serious_candidates_cover_all_priority_groups() -> None:
    ledger = rows("serious_candidate_ledger.csv")
    assert len(ledger) == 9
    assert {row["capability_group"] for row in ledger} == set(subject.GROUPS)
    assert Counter(row["capability_group"] for row in ledger) == Counter(
        {
            "Treasury duration": 3,
            "credit": 2,
            "size/broad/equal-weight equity": 2,
            "commodities/real assets": 1,
            "global/country/regional equity": 1,
        }
    )


def test_every_serious_candidate_has_source_rule_mapping_sample_and_control_evidence() -> None:
    ledger_ids = {row["candidate_id"] for row in rows("serious_candidate_ledger.csv")}
    assert {row["candidate_id"] for row in rows("source_rule_extraction.csv")} == ledger_ids
    assert {row["candidate_id"] for row in rows("source_citations.csv")} == ledger_ids
    assert {row["candidate_id"] for row in rows("lineage_comparison.csv")} == ledger_ids
    assert {row["candidate_id"] for row in rows("instrument_mapping.csv")} == ledger_ids
    assert {row["candidate_id"] for row in rows("sample_feasibility.csv")} == ledger_ids
    assert {row["candidate_id"] for row in rows("control_design.csv")} == ledger_ids


def test_source_rules_materially_unresolved_never_qualify() -> None:
    rules = {row["candidate_id"]: row for row in rows("source_rule_extraction.csv")}
    ledger = {row["candidate_id"]: row for row in rows("serious_candidate_ledger.csv")}
    assert all(row["qualification_status"] == "rejected" for row in ledger.values())
    incomplete = [row for row in rules.values() if row["source_rule_completeness"] == "source_rules_incomplete"]
    assert len(incomplete) == 3
    assert all(row["unresolved_field_classification"] == "material" for row in incomplete)
    assert all(row["unresolved_fields_material"] == "true" for row in incomplete)


def test_novelty_and_lineage_gate_rejects_equal_weight_duplicate() -> None:
    lineage = {row["candidate_id"]: row for row in rows("lineage_comparison.csv")}
    equal_weight = lineage["sp500_equal_weight_quarterly_rebalance_rsp_v1"]
    assert equal_weight["lineage_classification"] == "near_duplicate"
    assert equal_weight["exact_configuration_duplicate"] == "false"
    assert all(row["closed_family_reopened"] == "false" for row in lineage.values())


def test_instrument_mapping_blocks_source_inexact_substitution() -> None:
    mappings = rows("instrument_mapping.csv")
    six_month = next(row for row in mappings if row["source_required_exposure"] == "six-month zero-coupon Treasury")
    assert six_month["mapping_classification"] == "unsupported"
    assert six_month["frozen_symbol_or_mapping"] == ""
    commodity = next(row for row in mappings if row["candidate_id"].startswith("koijen_"))
    assert commodity["mapping_classification"] == "unsupported"
    assert "contract curves" in commodity["mapping_rationale"]


def test_sample_gate_distinguishes_price_history_from_signal_inputs() -> None:
    samples = rows("sample_feasibility.csv")
    assert all(row["tradable_price_history_adequate"] == "true" for row in samples)
    assert sum(row["source_signal_input_history_adequate"] == "true" for row in samples) == 1
    assert next(row for row in samples if row["candidate_id"].startswith("sp500_equal"))["final_sample_feasibility"] == "adequate_but_novelty_gate_failed"


def test_blocking_controls_are_ex_ante_and_ex_post_controls_are_diagnostic_only() -> None:
    controls = rows("control_design.csv")
    blocking = [row for row in controls if row["gate_role"].startswith("blocking")]
    diagnostics = [row for row in controls if row["uses_candidate_decisions"] == "true"]
    assert len(blocking) == 18
    assert len(diagnostics) == 9
    assert all(row["ex_ante_investable"] == "true" for row in blocking)
    assert all(row["uses_candidate_decisions"] == "false" for row in blocking)
    assert all(row["uses_future_returns"] == "false" for row in blocking)
    assert all(row["gate_role"] == "diagnostic_only" for row in diagnostics)
    assert all(row["ex_ante_investable"] == "false" for row in diagnostics)


def test_ranking_uses_no_performance_and_selects_no_work_package() -> None:
    rankings = rows("candidate_ranking.csv")
    assert [int(row["rank"]) for row in rankings] == list(range(1, 10))
    assert all(row["performance_information_used"] == "false" for row in rankings)
    assert all(row["qualified"] == "false" for row in rankings)
    selected = json.loads((OUTPUT / "selected_work_packages.json").read_text(encoding="utf-8"))
    assert selected["selected_work_packages"] == []
    assert selected["combined_future_canonical_trial_budget"] == 0
    assert selected["maximum_allowed_combined_canonical_trial_budget"] == 4


def test_rejection_counts_are_complete_and_standardized() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["rejected_counts_by_reason"] == {
        "data_or_universe_incompatibility": 5,
        "duplicate_or_near_duplicate": 1,
        "source_rules_incomplete_or_proprietary": 3,
    }
    assert sum(consistency["rejected_counts_by_reason"].values()) == 9


def test_entity_separation_and_prohibited_actions() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    counts = consistency["entity_counts"]
    assert counts["strategy_configurations_created"] == 0
    assert counts["experiment_trials_created"] == 0
    assert counts["backtests_run"] == 0
    assert counts["forward_observations_created"] == 0
    assert counts["provider_calls"] == 0
    assert counts["broker_calls"] == 0
    assert all(value is False for value in consistency["forbidden_actions"].values())


def test_frozen_universe_protected_state_and_deterministic_rerun(completed_run: dict[str, object]) -> None:
    first_hash = completed_run["deterministic_evidence_packet_hash"]
    second = subject.run()
    assert second["overall_pass"] is True
    assert second["deterministic_evidence_packet_hash"] == first_hash
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["frozen_universe_hash"] == subject.UNIVERSE_HASH
    assert consistency["checks"]["protected_state_and_prior_evidence_unchanged"] is True
    assert all(consistency["checks"].values())
