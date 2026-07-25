from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    BATCH_ID,
    MAX_STRATEGY_CONFIGS,
    MAX_TRIALS,
    NEXT_ACTION,
    OUTPUT_DIR,
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


def test_required_artifacts_exist_and_batch_contract() -> None:
    required = [
        "fast_lane_policy_snapshot.yaml",
        "frozen_universe_reference.json",
        "eligible_strategy_inventory.csv",
        "excluded_strategy_inventory.csv",
        "frozen_batch_manifest.csv",
        "trial_registry.csv",
        "data_coverage.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "trial_outcomes.csv",
        "followup_candidate_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "batch_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    consistency = load_json("consistency_check.json")
    assert consistency["batch_id"] == BATCH_ID
    assert consistency["batch_outcome"] == "fast_batch_complete"
    assert consistency["consistency_passed"] is True
    assert consistency["next_action"] == NEXT_ACTION


def test_frozen_universe_and_deterministic_selection_caps() -> None:
    universe = load_json("frozen_universe_reference.json")
    eligible = csv_rows("eligible_strategy_inventory.csv")
    manifest = csv_rows("frozen_batch_manifest.csv")

    selected_strategy_ids = []
    for row in manifest:
        if row["strategy_id"] not in selected_strategy_ids:
            selected_strategy_ids.append(row["strategy_id"])
    selected_symbols = []
    for row in manifest:
        if row["symbol"] not in selected_symbols:
            selected_symbols.append(row["symbol"])

    assert universe["frozen_universe_found"] is True
    assert universe["frozen_universe_row_count"] >= len(selected_symbols)
    assert len(selected_strategy_ids) <= MAX_STRATEGY_CONFIGS
    assert len(manifest) <= MAX_TRIALS
    assert selected_strategy_ids == [
        "public_source_adx_dmi_portability_adapter_v1",
        "public_source_cci_correction_portability_adapter_v1",
        "public_source_coppock_curve_portability_adapter_v1",
        "public_source_larry_connors_rsi2_portability_adapter_v1",
    ]
    assert selected_symbols == ["SPY", "QQQ", "IWM", "DIA", "VTV", "SCHG"]
    assert all(bool_text(row["performance_used_for_eligibility"]) is False for row in eligible)
    assert all(bool_text(row["canonical_parameters_unchanged"]) is True for row in eligible)


def test_trial_registration_and_no_hidden_variants() -> None:
    manifest = csv_rows("frozen_batch_manifest.csv")
    registry = csv_rows("trial_registry.csv")
    outcomes = csv_rows("trial_outcomes.csv")

    manifest_ids = {row["trial_id"] for row in manifest}
    registry_ids = {row["trial_id"] for row in registry}
    outcome_ids = {row["trial_id"] for row in outcomes}
    assert len(manifest_ids) == len(manifest)
    assert manifest_ids == registry_ids == outcome_ids
    assert all(bool_text(row["frozen_before_return_calculation"]) for row in manifest)
    assert all(bool_text(row["trial_registered_before_returns"]) for row in registry)
    assert all(row["adaptation_label"] == "family_portability_test" for row in registry)
    assert all(bool_text(row["exact_prior_config_closed_or_completed"]) is False for row in registry)


def test_no_macro_credentials_parameter_variants_or_substitutions() -> None:
    consistency = load_json("consistency_check.json")
    eligible = csv_rows("eligible_strategy_inventory.csv")

    assert consistency["eligibility_not_performance_based"] is True
    assert consistency["no_macro_fundamental_alt_data"] is True
    assert consistency["no_new_credentials"] is True
    assert consistency["no_parameter_variants"] is True
    assert consistency["no_performance_selected_substitutions"] is True
    assert all(bool_text(row["macro_or_fundamental_or_alt_data"]) is False for row in eligible)
    assert all(bool_text(row["requires_new_credential"]) is False for row in eligible)
    assert all(bool_text(row["leverage_or_inverse_or_shorting_required"]) is False for row in eligible)


def test_controls_and_static_exposure_controls_are_recorded() -> None:
    controls = csv_rows("control_metrics.csv")
    baseline_vs = csv_rows("baseline_vs_controls.csv")
    control_ids_by_trial: dict[str, set[str]] = {}
    for row in controls:
        control_ids_by_trial.setdefault(row["trial_id"], set()).add(row["control_id"])

    expected_controls = {
        "underlying_buy_hold",
        "BIL_cash",
        "static_average_exposure_control",
        "equal_weight_selected_universe_control",
    }
    assert baseline_vs
    assert set(control_ids_by_trial) == {row["trial_id"] for row in baseline_vs}
    assert all(ids == expected_controls for ids in control_ids_by_trial.values())
    assert all(row["performance_selected_control"] == "False" for row in controls)


def test_accounting_invariants_and_no_lookahead_labels() -> None:
    consistency = load_json("consistency_check.json")
    invariants = csv_rows("accounting_invariants.csv")

    assert consistency["invariant_failure_count"] == 0
    assert invariants
    for row in invariants:
        assert bool_text(row["exposure_invariant_pass"]) is True
        assert float(row["max_daily_exposure"]) <= 1.000001
        assert float(row["max_daily_weight_sum"]) <= 1.000001
        assert row["no_lookahead_status"] == "shifted_weight_returns_from_completed_daily_bars"
        assert row["cost_accounting_status"] == "standard_cost_and_zero_cost_diagnostic_recorded"
        assert bool_text(row["zero_target_weights_preserved"]) is True
        assert bool_text(row["no_stale_weights_after_exits"]) is True


def test_outcomes_are_allowed_and_non_promotional() -> None:
    outcomes = csv_rows("trial_outcomes.csv")
    assert outcomes
    for row in outcomes:
        assert bool_text(row["row_outcome_allowed"]) is True
        assert row["row_outcome"] in {
            "exploratory_followup_candidate",
            "control_weak",
            "cost_fragile",
            "insufficient_history",
            "capability_deferred",
            "implementation_or_accounting_defect",
        }
        assert bool_text(row["exploratory_non_promotable"]) is True
        assert bool_text(row["promotion_eligibility"]) is False
        assert bool_text(row["paper_forward_eligibility"]) is False
        assert bool_text(row["candidate_exhaustive_eligibility"]) is False


def test_no_overlay_paper_demo_registry_or_broker_state_change() -> None:
    consistency = load_json("consistency_check.json")
    names = {path.name for path in EVIDENCE.iterdir()}

    assert consistency["no_overlay_artifact"] is True
    assert all("overlay" not in name.lower() for name in names)
    assert consistency["registry_preserved"] is True
    assert consistency["active_observations_preserved"] is True
    assert consistency["paper_demo_state_changed"] is False
    assert consistency["paper_forward_activation"] is False
    assert consistency["broker_write_function_called"] is False
    assert consistency["provider_download"] is False
    assert consistency["intraday_data_used"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["promotion_candidates_created"] is False
    assert consistency["real_money_recommendation"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)

