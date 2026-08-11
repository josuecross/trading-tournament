from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    adopt_single_candidate_cohort_policy_and_run_cfra_stovall_exploration_v1 as batch,
)


def as_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


@pytest.fixture(scope="module", autouse=True)
def generated_packet() -> dict[str, object]:
    result = batch.run()
    assert result["overall_pass"]
    return result


def test_discovery_cohort_policy_v2_changes_only_cohort_size() -> None:
    policy = yaml.safe_load((batch.POLICY_DIR / "discovery_cohort_policy_v2.yaml").read_text(encoding="utf-8"))
    correction = pd.read_csv(batch.POLICY_DIR / "direction_correction_record.csv")
    historical = pd.read_csv(batch.POLICY_DIR / "historical_v4_intake_reconciliation.csv")

    assert policy["permitted_cohort_size"] == {"min": 1, "max": 4}
    assert policy["minimum_two_candidates_required"] is False
    assert policy["quota_fillers_allowed"] is False
    assert as_bool(correction.iloc[0]["candidate_rule_changed"]) is False
    assert as_bool(correction.iloc[0]["candidate_controls_changed"]) is False
    assert as_bool(correction.iloc[0]["single_candidate_execution_authorized"]) is True
    assert historical.iloc[0]["historical_intake_outcome"] == "one_candidate_only_insufficient_for_batch"
    assert int(historical.iloc[0]["source_packages_reviewed"]) == 18
    assert int(historical.iloc[0]["serious_candidates_assessed"]) == 9
    assert int(historical.iloc[0]["independently_qualified_candidates"]) == 1


def test_historical_v4_intake_is_materialized_without_converting_rejections() -> None:
    manifest = yaml.safe_load((batch.SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    sources = pd.read_csv(batch.SOURCE_DIR / "source_library_records.csv")
    catalog = pd.read_csv(batch.SOURCE_DIR / "configuration_trial_catalog.csv")
    rejected = pd.read_csv(batch.SOURCE_DIR / "rejection_ledger.csv")
    overlay = pd.read_csv(batch.SOURCE_DIR / "direction_policy_overlay.csv")

    assert manifest["historical_intake_outcome"] == "one_candidate_only_insufficient_for_batch"
    assert manifest["implementation_previously_authorized"] is False
    assert manifest["implementation_now_authorized_by"] == "discovery_cohort_policy_v2"
    assert list(sources["source_record_id"]) == [batch.SOURCE_RECORD_ID]
    assert list(catalog["strategy_id"]) == [batch.STRATEGY_ID]
    assert int(rejected.iloc[0]["converted_to_strategy_configurations"]) == 0
    assert int(rejected.iloc[0]["converted_to_trials"]) == 0
    assert as_bool(overlay.iloc[0]["only_cohort_policy_changed"]) is True


def test_exact_entity_counts_and_benchmark_reference_roles() -> None:
    counts = json.loads((batch.OUTPUT_DIR / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    cards = pd.read_csv(batch.OUTPUT_DIR / "strategy_cards.csv")
    trials = pd.read_csv(batch.OUTPUT_DIR / "trial_ledger.csv")
    benchmarks = pd.read_csv(batch.OUTPUT_DIR / "benchmark_reference_log.csv")

    assert counts["direction_correction_records"] == 1
    assert counts["source_library_records_materialized"] == 1
    assert counts["strategy_configurations"] == 1
    assert counts["canonical_exploration_trials"] == 1
    assert counts["process_tasks"] == 1
    assert counts["robustness_trials"] == 0
    assert counts["paper_demo_observations"] == 0
    assert len(cards) == 1
    assert len(trials) == 1
    assert set(benchmarks["benchmark_reference_id"]) == set(batch.CONTROLS)
    assert set(benchmarks["entity_type"]) == {"benchmark_reference"}
    assert benchmarks["critical_control"].map(as_bool).sum() == 2


def test_cache_only_preflight_and_event_window_counts() -> None:
    preflight = pd.read_csv(batch.OUTPUT_DIR / "data_preflight_reconciliation.csv")
    common = preflight[preflight["record_type"] == "common_etf_period"].iloc[0]
    events = pd.read_csv(batch.OUTPUT_DIR / "event_execution_ledger.csv")
    windows = pd.read_csv(batch.OUTPUT_DIR / "event_window_inventory.csv")
    prices, _, passed = batch.load_prices()

    assert passed
    assert set(preflight[preflight["record_type"] == "symbol_cache"]["symbol"]) == set(batch.REQUIRED_SYMBOLS)
    assert preflight[preflight["record_type"] == "symbol_cache"]["cache_path"].str.startswith("data/cache/").all()
    assert as_bool(common["provider_access_performed"]) is False
    assert as_bool(common["network_access_performed"]) is False
    assert as_bool(common["signal_count_pass"]) is True
    assert set(events["event_month"]) <= {4, 10}
    assert pd.to_datetime(events["event_date"]).tolist() == batch.event_dates(prices.index)
    assert len(windows) == len(events) - 1
    assert len(windows) >= 20
    assert (windows["chronological_half"] == "first_chronological_half").sum() >= 8
    assert (windows["chronological_half"] == "second_chronological_half").sum() >= 8
    assert windows["entry_and_exit_legs_counted_separately"].map(as_bool).eq(False).all()


def test_timing_accounting_and_weight_invariants_pass() -> None:
    invariants = pd.read_csv(batch.OUTPUT_DIR / "invariant_results.csv")
    events = pd.read_csv(batch.OUTPUT_DIR / "event_execution_ledger.csv")
    results = pd.read_csv(batch.OUTPUT_DIR / "all_trial_results.csv")

    assert set(invariants["status"]) == {"pass"}
    assert events["event_session_return_assigned_to_pre_event_holdings"].map(as_bool).all()
    assert events["new_target_return_begins_following_session"].map(as_bool).all()
    assert results["invariant_pass"].map(as_bool).all()
    assert results["daily_weight_sum_one_within_tolerance"].map(as_bool).all()
    assert results["no_leverage"].map(as_bool).all()
    assert results["no_shorting"].map(as_bool).all()


def test_required_result_grids_and_closed_outcome_are_recorded() -> None:
    all_trials = pd.read_csv(batch.OUTPUT_DIR / "all_trial_results.csv")
    controls = pd.read_csv(batch.OUTPUT_DIR / "control_results.csv")
    halves = pd.read_csv(batch.OUTPUT_DIR / "chronological_half_results.csv")
    years = pd.read_csv(batch.OUTPUT_DIR / "calendar_year_results.csv")
    outcome = pd.read_csv(batch.OUTPUT_DIR / "outcome_summary.csv").iloc[0]
    failures = pd.read_csv(batch.OUTPUT_DIR / "failure_reasons.csv")
    next_action = pd.read_csv(batch.OUTPUT_DIR / "next_actions.csv").iloc[0]

    assert set(all_trials["cost_bps_one_way"]) == {0.0, 5.0, 10.0}
    assert set(controls["cost_bps_one_way"]) == {0.0, 5.0, 10.0}
    assert set(halves["period"]) == {"first_chronological_half", "second_chronological_half"}
    assert set(controls["entity_role"]) == {"benchmark_reference"}
    assert not years.empty
    assert outcome["outcome"] == "closed_exploration"
    assert outcome["primary_failure_reason"] == "period_instability"
    assert failures["primary_failure_reason"].map(as_bool).any()
    assert next_action["exact_next_action"] == batch.NEXT_CLOSED
    assert as_bool(next_action["execute_in_this_task"]) is False


def test_consistency_check_and_protected_boundaries() -> None:
    consistency = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    protected = pd.read_csv(batch.OUTPUT_DIR / "protected_state_reconciliation.csv")
    source = Path(batch.__file__).read_text(encoding="utf-8").lower()

    assert consistency["overall_pass"] is True
    assert consistency["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert consistency["provider_access_performed"] is False
    assert consistency["network_access_performed"] is False
    assert consistency["no_paper_demo_records"] is True
    assert set(protected["status"]) == {"pass"}
    assert "submit_order" not in source
    assert "place_order" not in source
    assert "import requests" not in source
