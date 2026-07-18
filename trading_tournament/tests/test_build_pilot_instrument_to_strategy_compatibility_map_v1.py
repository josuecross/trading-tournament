from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.universe_expansion import build_pilot_instrument_to_strategy_compatibility_map_v1 as compat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_instrument_strategy_compatibility_v1"
EVIDENCE_DIR = ROOT / "evidence" / "pilot_instrument_strategy_compatibility_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str):
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def read_yaml(name: str):
    return yaml.safe_load((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_required_outputs_exist_in_design_and_evidence() -> None:
    for name in compat.OUTPUT_FILES:
        assert (OUTPUT_DIR / name).exists(), name
        assert (EVIDENCE_DIR / name).exists(), name


def test_step1_and_step2_remain_byte_identical() -> None:
    payload = read_json("step1_and_step2_hash_verification.json")
    assert payload["step1_and_step2_byte_identical_after_step3"] is True
    assert payload["before"] == payload["after"]
    assert read_json("consistency_check.json")["step1_and_step2_byte_identical"] is True


def test_accepted_pilot_contains_exactly_47_and_dbe_remains_excluded() -> None:
    rows = read_csv("accepted_final_47_universe.csv")
    symbols = [row["symbol"] for row in rows]
    assert symbols == list(compat.ACCEPTED_FINAL_47)
    assert len(symbols) == 47
    assert "DBE" not in symbols
    check = read_json("consistency_check.json")
    assert check["accepted_final_instrument_count"] == 47
    assert check["dbe_excluded"] is True


def test_no_off_list_instrument_enters_and_threshold_is_not_changed() -> None:
    direction = read_yaml("direction_owner_gap_acceptance.yaml")
    check = read_json("consistency_check.json")
    assert direction["liquidity_threshold_unchanged"] is True
    assert direction["off_list_substitution_authorized"] is False
    assert check["off_list_instrument_entered"] is False
    assert check["liquidity_threshold_changed"] is False


def test_energy_commodity_gap_remains_explicit() -> None:
    gap = read_yaml("accepted_exposure_gap.yaml")
    assert gap["gap"]["slot"] == "energy_commodity_pool"
    assert gap["gap"]["proposed_symbol"] == "DBE"
    assert gap["gap"]["off_list_replacement_added"] is False
    assert read_json("consistency_check.json")["energy_commodity_gap_explicit"] is True


def test_no_performance_strategy_or_correlation_calculation_is_recorded() -> None:
    check = read_json("consistency_check.json")
    assert check["returns_volatility_drawdown_correlation_or_strategy_performance_calculated"] is False
    assert check["compatibility_uses_performance_fields"] is False
    assert check["strategy_backtest_run"] is False
    forbidden_metric_headers = {"cagr", "sharpe", "drawdown", "correlation", "total_return"}
    for csv_name in (
        "accepted_final_47_universe.csv",
        "portable_family_inventory.csv",
        "instrument_family_compatibility.csv",
        "economic_group_compatibility.csv",
        "chronological_eligibility.csv",
    ):
        headers = set((OUTPUT_DIR / csv_name).read_text(encoding="utf-8").splitlines()[0].lower().split(","))
        assert headers.isdisjoint(forbidden_metric_headers), csv_name


def test_compatibility_rows_have_rule_based_reasons_and_valid_labels() -> None:
    allowed = {
        "directly_compatible",
        "compatible_with_frozen_cash_proxy",
        "group_level_only",
        "incompatible_mechanism",
        "incompatible_data",
        "incompatible_accounting",
        "duplicate_or_closed_mechanism",
        "future_lane_only",
        "requires_source_verification",
    }
    rows = read_csv("instrument_family_compatibility.csv")
    assert len(rows) == 47 * 5
    assert all(row["rule_based_reason"] for row in rows)
    assert {row["compatibility_label"] for row in rows} <= allowed
    assert all(row["performance_used_for_classification"] == "False" for row in rows)


def test_no_family_exceeds_six_economic_groups() -> None:
    rows = read_csv("economic_group_compatibility.csv")
    for family_id in compat.FAMILY_IDS:
        assert len({row["candidate_group"] for row in rows if row["family_id"] == family_id}) <= 6
    assert read_json("consistency_check.json")["family_exceeds_six_economic_groups"] is False


def test_design_does_not_exceed_47_exact_instrument_trials() -> None:
    design = read_yaml("first_portability_experiment_design.yaml")
    assert design["trial_counting"]["maximum_exact_instrument_trials"] == 47
    assert design["trial_counting"]["exact_configuration_trials_planned_if_source_verified"] == 43
    assert read_json("consistency_check.json")["design_exceeds_47_exact_instrument_trials"] is False


def test_only_one_family_is_recommended_and_next_action_is_source_verification() -> None:
    decision = read_json("recommended_family_decision.json")
    assert decision["compatibility_stage_outcome"] == "family_source_verification_required"
    assert decision["recommended_family"] == "own_return_trend_long_cash"
    assert decision["one_family_recommended"] is True
    assert decision["next_action"] == "direction_owner_source_verification_for_portability_family"


def test_no_rule_parameter_is_selected_from_historical_results() -> None:
    design = read_yaml("first_portability_experiment_design.yaml")
    assert design["parameter_set"] == "pending_source_verification_no_lookback_selected_here"
    assert design["source_and_rule_verification_requirement"]["no_performance_based_parameter_choice"] is True
    assert read_json("consistency_check.json")["historical_results_used_to_select_parameters"] is False


def test_no_pairs_are_generated() -> None:
    guardrails = read_yaml("multiple_testing_guardrails.yaml")
    assert guardrails["pair_generation"] is False
    assert read_json("consistency_check.json")["pair_generation"] is False


def test_no_reserve_wrapper_is_counted_as_independent_evidence() -> None:
    family_schema = read_yaml("family_trial_ledger_schema.yaml")
    design = read_yaml("first_portability_experiment_design.yaml")
    assert family_schema["reserve_wrappers_counted_as_independent_evidence"] is False
    assert design["trial_counting"]["reserve_wrappers_counted_as_independent_evidence"] is False
    assert read_json("consistency_check.json")["reserve_wrapper_counted_as_independent_evidence"] is False


def test_chronological_eligibility_uses_frozen_dates() -> None:
    rows = read_csv("chronological_eligibility.csv")
    assert {row["formation_end"] for row in rows} == {"2016-12-30"}
    assert {row["validation_start"] for row in rows} == {"2017-01-03"}
    assert {row["validation_end"] for row in rows} == {"2021-12-31"}
    assert {row["holdout_start"] for row in rows} == {"2022-01-03"}
    assert {row["frozen_endpoint"] for row in rows} == {"2026-07-16"}
    assert all(row["boundary_chosen_from_results"] == "False" for row in rows)


def test_no_instrument_is_used_before_inception() -> None:
    rows = read_csv("chronological_eligibility.csv")
    assert all(row["used_before_inception"] == "False" for row in rows)
    assert read_json("consistency_check.json")["instrument_used_before_inception"] is False


def test_trial_ledger_schemas_retain_failed_and_excluded_trials() -> None:
    family_schema = read_yaml("family_trial_ledger_schema.yaml")
    exact_schema = read_yaml("exact_configuration_trial_ledger_schema.yaml")
    assert family_schema["retain_failed_and_excluded_trials"] is True
    assert exact_schema["retain_failed_and_excluded_trials"] is True
    assert "failure_or_exclusion_reason" in exact_schema["required_fields"]
    assert read_json("consistency_check.json")["failed_and_excluded_trials_retained_in_ledger_schema"] is True


def test_quantpedia_is_not_accessed() -> None:
    assert read_json("consistency_check.json")["quantpedia_accessed"] is False


def test_strategy_registry_and_active_observations_remain_unchanged() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = compat.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["outcome"] == "family_source_verification_required"
    assert before == after
    check = read_json("consistency_check.json")
    assert check["strategy_registry_byte_identical"] is True
    assert check["active_observations_byte_identical"] is True


def test_no_backtest_runs_or_strategy_screen_is_authorized() -> None:
    decision = read_json("recommended_family_decision.json")
    step4 = read_yaml("step4_requirements.yaml")
    assert decision["backtest_authorized"] is False
    assert decision["new_strategy_screen_authorized"] is False
    assert step4["backtest_authorized_now"] is False
    assert step4["strategy_screen_authorized_now"] is False


def test_output_generation_is_deterministic() -> None:
    files = sorted(path for path in OUTPUT_DIR.iterdir() if path.is_file())
    before = {path.name: sha256(path) for path in files}
    compat.run()
    after = {path.name: sha256(path) for path in files}
    assert before == after
