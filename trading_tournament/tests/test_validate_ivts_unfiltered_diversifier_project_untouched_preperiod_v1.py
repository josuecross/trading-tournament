from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.research import (
    validate_ivts_unfiltered_diversifier_project_untouched_preperiod_v1 as task,
)


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return task.run()


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_and_consistency(result: dict[str, object]) -> None:
    assert result["consistency_passed"] is True
    assert all((task.OUTPUT_DIR / name).exists() for name in task.REQUIRED_ARTIFACTS)


def test_exact_strategy_and_validation_child_lineage(result: dict[str, object]) -> None:
    strategy = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    children = [row for row in trials if row["record_role"] == "new_validation_child"]
    parents = [row for row in trials if row["record_role"] == "carried_forward_read_only"]
    assert len(strategy) == 1
    assert strategy[0]["strategy_id"] == task.STRATEGY_ID
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["adaptation_label"] == "result_driven_exploratory_variant"
    assert len(children) == 1
    assert len(parents) == 1
    assert children[0]["trial_id"] == task.TRIAL_ID
    assert children[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert children[0]["adaptation_label"] == "validation_variant"
    assert children[0]["changed_fields_from_parent"] == (
        "evaluation_period_and_validation_gate_only"
    )
    assert children[0]["preregistered_before_validation_performance"] == "true"
    assert children[0]["validation_period_viewed_before_preregistration"] == "false"


def test_exact_project_untouched_period_is_frozen(result: dict[str, object]) -> None:
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "validation_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["validation_period"]["start"] == "2010-08-10"
    assert manifest["validation_period"]["end"] == "2014-04-16"
    assert manifest["validation_period"]["classification"] == (
        "project_untouched_not_source_untouched"
    )
    assert manifest["development_period"]["use"] == "reproduction_and_context_only"
    assert manifest["validation_period_viewed_before_preregistration"] is False


def test_official_hashes_and_preflight_pass_without_network(
    result: dict[str, object],
) -> None:
    hashes = rows("official_history_hash_reconciliation.csv")
    preflight = rows("validation_period_preflight.csv")
    assert len(hashes) == 4
    assert all(row["status"] == "pass" for row in hashes)
    assert all(row["network_request_performed"] == "false" for row in hashes)
    assert all(row["status"] == "pass" for row in preflight)
    common = next(
        row
        for row in preflight
        if row["check_id"] == "five_common_official_observations_before_start"
    )
    assert int(common["detail"].split()[0]) >= 5


def test_development_period_reproduces_within_one_e_minus_nine(
    result: dict[str, object],
) -> None:
    reproduction = rows("development_period_reproduction.csv")
    assert reproduction
    assert all(row["pass"] == "true" for row in reproduction)
    assert max(abs(float(row["difference"])) for row in reproduction) <= 1e-9
    assert result["development_reproduction_passed"] is True


def test_frozen_signal_controls_and_exposure_weight(result: dict[str, object]) -> None:
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "validation_manifest.yaml").read_text(encoding="utf-8")
    )
    weights = manifest["frozen_exposure_matched_weights"]
    assert weights["SPY"] == task.FROZEN_EXPOSURE_SPY_WEIGHT
    assert weights["IEF"] == task.FROZEN_EXPOSURE_IEF_WEIGHT
    assert weights["recalculated_from_validation_period"] is False
    assert manifest["signal_changed"] is False
    assert manifest["thresholds_changed"] is False
    assert manifest["execution_changed"] is False
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(benchmarks) == 5
    assert {row["benchmark_reference_id"] for row in benchmarks} == set(task.CONTROLS)


def test_exact_six_validation_portfolios_and_costs(result: dict[str, object]) -> None:
    full = rows("validation_portfolio_results.csv")
    assert len(full) == 18
    assert {row["portfolio_id"] for row in full} == set(task.PORTFOLIO_IDS.values())
    assert {float(row["cost_bps"]) for row in full} == {0.0, 5.0, 10.0}
    assert all(row["daily_fixed_weight_return_blend_used"] == "false" for row in full)
    assert all(row["transaction_costs_charged_once"] == "true" for row in full)


def test_half_and_calendar_diagnostics_keep_all_periods(
    result: dict[str, object],
) -> None:
    halves = rows("validation_chronological_half_results.csv")
    years = rows("validation_calendar_year_results.csv")
    assert len(halves) == 12
    assert {row["period"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert len(years) == 30
    assert {int(row["calendar_year"]) for row in years} == {
        2010,
        2011,
        2012,
        2013,
        2014,
    }
    assert {row["complete_calendar_year"] for row in years} == {"true", "false"}


def test_turnover_costs_and_invariants_reconcile(result: dict[str, object]) -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == 18
    assert all(row["outer_turnover_reconciles"] == "true" for row in turnover)
    assert all(row["outer_cost_reconciles"] == "true" for row in turnover)
    assert all(row["inner_and_outer_costs_charged_once"] == "true" for row in turnover)
    assert len(invariants) == 36
    assert all(row["invariant_pass"] == "true" for row in invariants)
    assert all(row["signal_date_return_used"] == "false" for row in invariants)
    assert all(float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9 for row in invariants)


def test_outcome_is_limited_to_diversifier_non_vintage_claim(
    result: dict[str, object],
) -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "validation_positive",
        "validation_mixed",
        "validation_failed",
        "validation_data_or_methodology_blocked",
    }
    assert outcome["standalone_validation_claimed"] == "false"
    assert outcome["point_in_time_historical_data_safety_established"] == "false"
    assert outcome["paper_demo_eligibility_automatically_supported"] == "false"
    if outcome["outcome"] == "validation_positive":
        assert outcome["validated_claim"] == (
            "20pct_diversifier_route_under_current_history_non_vintage_data"
        )


def test_protected_state_prior_evidence_and_cache_unchanged(
    result: dict[str, object],
) -> None:
    check = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_generation_is_deterministic(result: dict[str, object]) -> None:
    first = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    rerun = task.run()
    second = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert rerun["consistency_passed"] is True
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
