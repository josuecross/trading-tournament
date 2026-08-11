from __future__ import annotations

import csv
import json
from collections import Counter

import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_public_signal_etf_mappable_candidate_intake_v2 as subject


OUTPUT = ROOT / "evidence" / "public_source_strategy_intake" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run() -> dict[str, object]:
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_required_packet_and_one_candidate_outcome() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["task_outcome"] == "phase2_public_signal_one_candidate_qualified"
    assert consistency["exact_next_action"] == "acquire_validate_freeze_phase2_public_signal_inputs_v1"
    assert consistency["overall_pass"] is True


def test_ten_serious_candidates_cover_all_priority_groups() -> None:
    ledger = rows("serious_candidate_ledger.csv")
    assert len(ledger) == 10
    assert {row["capability_group"] for row in ledger} == set(subject.GROUPS)
    assert Counter(row["qualification_status"] for row in ledger) == {"rejected": 9, "qualified": 1}


def test_exactly_one_source_complete_work_package_is_selected() -> None:
    ledger = rows("serious_candidate_ledger.csv")
    selected = [row for row in ledger if row["qualification_status"] == "qualified"]
    assert [row["candidate_id"] for row in selected] == [subject.SELECTED_ID]
    assert selected[0]["source_rule_status"] == "source_rules_complete"
    assert selected[0]["lineage_classification"] == "related_but_materially_distinct"
    payload = json.loads((OUTPUT / "selected_work_packages.json").read_text(encoding="utf-8"))
    assert payload["selected_candidate_count"] == 1
    assert payload["combined_future_canonical_trial_budget"] == 1
    assert payload["selected_work_packages"][0]["strategy_implemented"] is False
    assert payload["selected_work_packages"][0]["trial_created"] is False


def test_selected_rule_is_frozen_and_complete() -> None:
    rule = next(row for row in rows("source_rule_extraction.csv") if row["candidate_id"] == subject.SELECTED_ID)
    assert rule["ranking_or_threshold_rule"] == "low when CPI YoY < 1.5%; medium when 1.5% <= CPI YoY <= 2.5%; high when CPI YoY > 2.5%"
    assert "120 monthly observations" in rule["lookback_or_measurement_period"]
    assert "next business day" in rule["transaction_timing"]
    assert rule["unresolved_material_fields"] == ""
    assert rule["rule_invented_or_completed_by_intake"] == "false"


def test_selected_mapping_uses_only_frozen_symbols_and_permitted_classes() -> None:
    mappings = [row for row in rows("tradable_exposure_mapping.csv") if row["candidate_id"] == subject.SELECTED_ID]
    assert {row["frozen_symbol_mapping"] for row in mappings} == {"SPY", "IYR", "GSG", "GLD", "AGG", "TIP"}
    assert {row["mapping_classification"] for row in mappings} <= {
        "exact_match",
        "economically_close_source_preserving_proxy",
    }
    assert all(row["all_symbols_in_frozen_88"] == "true" for row in mappings)
    assert len(subject.FROZEN_SYMBOLS) == 88


def test_external_signal_gate_distinguishes_public_data_from_etf_cache() -> None:
    signals = rows("external_signal_feasibility.csv")
    selected = next(row for row in signals if row["candidate_id"] == subject.SELECTED_ID)
    assert selected["dataset_or_series"] == "CPIAUCNS"
    assert selected["classification"] == "public_with_explicit_release_lag_feasible"
    assert selected["historical_vintages_necessary"] == "true"
    assert selected["historical_vintages_available"] == "true"
    assert selected["lookahead_safe_reconstruction"] == "true"
    assert selected["downloaded_or_ingested_in_this_task"] == "false"
    assert {row["classification"] for row in signals} <= subject.SIGNAL_CLASSIFICATIONS


def test_revised_rejection_taxonomy_is_complete() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["rejected_counts_by_reason"] == {
        "duplicate_or_near_duplicate": 2,
        "mechanism_already_saturated": 1,
        "source_rules_incomplete": 3,
        "unsupported_tradable_exposure": 3,
    }
    assert sum(consistency["rejected_counts_by_reason"].values()) == 9
    ledger = rows("serious_candidate_ledger.csv")
    assert all(row["exact_rejection_reason"] for row in ledger if row["qualification_status"] == "rejected")


def test_prior_v1_rejections_are_protected_and_not_rescued() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["prior_v1_rejection_outcomes_preserved"] == 9
    assert consistency["checks"]["prior_v1_had_nine_rejections"] is True
    assert consistency["checks"]["prior_v1_outcome_preserved"] is True
    ledger = {row["candidate_id"]: row for row in rows("serious_candidate_ledger.csv")}
    assert ledger["maio_fed_funds_change_spy_bil_recursive_v1"]["lineage_classification"] == "duplicate"
    assert ledger["maio_fed_model_yield_gap_spy_bil_recursive_v1"]["lineage_classification"] == "duplicate"


def test_sample_gate_uses_binding_signal_and_etf_history() -> None:
    sample = next(row for row in rows("sample_feasibility.csv") if row["candidate_id"] == subject.SELECTED_ID)
    assert sample["earliest_required_tradable_history"] == "2006-07-21"
    assert sample["binding_research_start"].startswith("2009-08")
    assert int(sample["estimated_independent_formations"]) >= 200
    assert sample["publication_lag_accounted_for"] == "true"
    assert sample["dates_selected_from_performance"] == "false"


def test_controls_preserve_information_sets() -> None:
    controls = rows("control_design.csv")
    assert len(controls) == 30
    blocking = [row for row in controls if row["gate_role"] == "blocking"]
    diagnostic = [row for row in controls if row["gate_role"] == "diagnostic_only"]
    assert len(blocking) == 20
    assert len(diagnostic) == 10
    assert all(row["ex_ante_investable"] == "true" for row in blocking)
    assert all(row["uses_only_information_available_at_decision"] == "true" for row in blocking)
    assert all(row["can_block_future_advancement"] == "false" for row in diagnostic)
    assert all(row["uses_candidate_full_history"] == "true" for row in diagnostic)


def test_no_strategy_trial_performance_or_external_system_action() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    counts = consistency["entity_counts"]
    assert counts["strategy_configurations_created"] == 0
    assert counts["experiment_trials_created"] == 0
    assert counts["backtests_run"] == 0
    assert counts["market_data_provider_calls"] == 0
    assert counts["forward_observations_accessed_or_created"] == 0
    assert counts["broker_calls"] == 0
    assert all(value is False for value in consistency["forbidden_actions"].values())


def test_protected_state_and_deterministic_rerun(completed_run: dict[str, object]) -> None:
    first_hash = completed_run["deterministic_evidence_packet_hash"]
    second = subject.run()
    assert second["overall_pass"] is True
    assert second["deterministic_evidence_packet_hash"] == first_hash
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["frozen_universe_hash"] == subject.UNIVERSE_HASH
    assert consistency["checks"]["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert all(consistency["checks"].values())
