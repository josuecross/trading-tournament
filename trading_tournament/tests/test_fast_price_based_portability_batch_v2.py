from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.fast_price_based_portability_batch_v2 import (
    BATCH_ID,
    MAX_FAMILIES,
    MAX_TRIALS,
    NEXT_ACTION,
    OUTPUT_DIR,
    PARABOLIC_CONFIG,
    V1_COMPLETED_STRATEGIES,
    deterministic_core_hash,
    run,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def unique_in_order(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def test_required_artifacts_and_batch_contract() -> None:
    required = [
        "prior_direction_decisions.json",
        "remaining_strategy_inventory.csv",
        "excluded_strategy_inventory.csv",
        "frozen_universe_reference.json",
        "frozen_batch_manifest.csv",
        "canonical_family_representatives.csv",
        "trial_registry.csv",
        "data_coverage.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "row_outcomes.csv",
        "family_outcomes.csv",
        "family_followup_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "batch_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    consistency = load_json("consistency_check.json")
    assert consistency["batch_id"] == BATCH_ID
    assert consistency["batch_outcome"] == "fast_batch_v2_complete"
    assert consistency["batch_outcome_allowed"] is True
    assert consistency["consistency_passed"] is True
    assert consistency["next_action"] == NEXT_ACTION


def test_v1_families_are_excluded_and_coppock_is_not_rerun() -> None:
    prior = load_json("prior_direction_decisions.json")
    excluded = csv_rows("excluded_strategy_inventory.csv")
    manifest = csv_rows("frozen_batch_manifest.csv")
    selected_ids = {row["strategy_id"] for row in manifest}
    excluded_ids = {row["strategy_id"] for row in excluded}

    assert set(V1_COMPLETED_STRATEGIES).issubset(excluded_ids)
    assert not selected_ids.intersection(V1_COMPLETED_STRATEGIES)
    assert "public_source_coppock_curve_portability_adapter_v1" not in selected_ids
    assert prior["coppock_direction_decision"] == "NO_ADVANCEMENT"
    assert prior["coppock_rerun"] is False
    assert prior["coppock_parameters_changed"] is False


def test_selection_order_caps_and_group_limits_are_deterministic() -> None:
    consistency = load_json("consistency_check.json")
    manifest = csv_rows("frozen_batch_manifest.csv")
    selected_strategy_ids = unique_in_order([row["strategy_id"] for row in manifest])
    selected_symbols = unique_in_order([row["symbol"] for row in manifest])
    group_counts: dict[str, int] = {}
    for row in manifest:
        group_counts[row["candidate_group"]] = group_counts.get(row["candidate_group"], 0) + 1

    assert selected_strategy_ids == [PARABOLIC_CONFIG.strategy_id]
    assert selected_symbols == ["SPY", "XLK", "EFA", "SHY", "GLD", "IYR"]
    assert len(selected_strategy_ids) == 1
    assert len(selected_strategy_ids) <= MAX_FAMILIES
    assert len(manifest) <= MAX_TRIALS
    assert all(count <= 1 for count in group_counts.values())
    assert consistency["eligibility_independent_of_performance"] is True
    assert consistency["family_order_deterministic"] is True
    assert consistency["single_remaining_family_allowed_to_run"] is True


def test_canonical_parameters_and_representative_are_frozen_before_returns() -> None:
    representatives = csv_rows("canonical_family_representatives.csv")
    manifest = csv_rows("frozen_batch_manifest.csv")
    registry = csv_rows("trial_registry.csv")

    assert representatives[0]["canonical_representative_symbol"] == "SPY"
    assert representatives[0]["selection_rule"] == "first compatible instrument in frozen universe order"
    assert representatives[0]["performance_used_for_selection"] == "False"
    assert all(bool_text(row["frozen_before_return_calculation"]) for row in manifest)
    assert all(bool_text(row["trial_registered_before_returns"]) for row in registry)
    assert all('"af_start": 0.02' in row["canonical_parameters"] for row in manifest)
    assert all('"af_increment": 0.02' in row["canonical_parameters"] for row in manifest)
    assert all('"af_maximum": 0.2' in row["canonical_parameters"] for row in manifest)
    assert all("parabolic_sar_wilder_stockcharts_contract_v1" in row["canonical_parameters"] for row in manifest)


def test_every_trial_counted_once_and_rows_are_not_independent_strategies() -> None:
    manifest = csv_rows("frozen_batch_manifest.csv")
    registry = csv_rows("trial_registry.csv")
    outcomes = csv_rows("row_outcomes.csv")
    family_outcomes = csv_rows("family_outcomes.csv")

    manifest_ids = [row["trial_id"] for row in manifest]
    registry_ids = [row["trial_id"] for row in registry]
    outcome_ids = [row["trial_id"] for row in outcomes]
    assert len(set(manifest_ids)) == len(manifest_ids)
    assert set(manifest_ids) == set(registry_ids) == set(outcome_ids)
    assert len(manifest) == len(registry) == len(outcomes) == 6
    assert len(family_outcomes) == 1
    assert all(row["instrument_rows_counted_as_independent_strategies"] == "False" for row in registry)
    assert all(row["instrument_rows_counted_as_independent_strategies"] == "False" for row in outcomes)
    assert family_outcomes[0]["instrument_rows_counted_as_independent_strategies"] == "False"


def test_timeframe_diagnostics_are_existing_halves_not_holdouts() -> None:
    timeframe = csv_rows("timeframe_diagnostics.csv")
    assert len(timeframe) == 6
    for row in timeframe:
        assert row["first_half_valid"] == "True"
        assert row["second_half_valid"] == "True"
        assert row["first_half_start_date"] < row["first_half_end_date"]
        assert row["second_half_start_date"] < row["second_half_end_date"]
        assert row["first_half_end_date"] < row["second_half_start_date"]
        assert row["timeframe_diagnostic_not_holdout"] == "True"


def test_accounting_invariants_and_no_lookahead_cost_labels() -> None:
    consistency = load_json("consistency_check.json")
    invariants = csv_rows("accounting_invariants.csv")

    assert consistency["invariant_failure_count"] == 0
    assert invariants
    for row in invariants:
        assert row["exposure_invariant_pass"] == "True"
        assert float(row["max_daily_exposure"]) <= 1.000001
        assert float(row["max_daily_weight_sum"]) <= 1.000001
        assert row["zero_target_weights_preserved"] == "True"
        assert row["no_stale_weights_after_exits"] == "True"
        assert row["no_lookahead_status"] == "shifted_weight_returns_from_completed_daily_bars"
        assert row["cost_accounting_status"] == "5bps_turnover_cost_and_zero_cost_diagnostic_recorded"
        assert row["static_control_same_calendar"] == "True"


def test_row_and_family_outcomes_are_allowed_and_non_promotional() -> None:
    rows = csv_rows("row_outcomes.csv")
    families = csv_rows("family_outcomes.csv")
    valid_rows = {
        "row_control_strong",
        "row_timeframe_fragile",
        "row_control_weak",
        "row_cost_fragile",
        "insufficient_history",
        "capability_deferred",
        "implementation_or_accounting_defect",
    }
    valid_families = {
        "family_exploratory_followup_candidate",
        "family_timeframe_fragile",
        "family_control_weak",
        "family_cost_fragile",
        "family_capability_deferred",
        "family_implementation_defect",
    }

    assert rows
    assert families
    assert all(row["row_outcome"] in valid_rows for row in rows)
    assert all(row["row_outcome_allowed"] == "True" for row in rows)
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    assert all(row["family_outcome"] in valid_families for row in families)
    assert all(row["family_outcome_allowed"] == "True" for row in families)
    assert all(row["promotion_eligibility"] == "False" for row in families)
    assert all(row["paper_forward_eligibility"] == "False" for row in families)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in families)


def test_no_new_strategy_macro_overlay_registry_paper_broker_or_provider_state() -> None:
    consistency = load_json("consistency_check.json")
    artifact_names = {path.name.lower() for path in EVIDENCE.iterdir()}

    assert consistency["no_new_strategy_or_parameter_generated"] is True
    assert consistency["no_macro_or_fundamental_data_source_called"] is True
    assert consistency["no_overlay_performance_artifact"] is True
    assert all("overlay" not in name for name in artifact_names)
    assert consistency["registry_lifecycle_unchanged"] is True
    assert consistency["active_paper_demo_state_unchanged"] is True
    assert consistency["broker_or_order_path_touched"] is False
    assert consistency["provider_download"] is False
    assert consistency["intraday_data_used"] is False
    assert consistency["paper_forward_activation"] is False
    assert consistency["promotion_candidates_created"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["real_money_recommendation"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
