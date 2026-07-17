from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import combo_vm_dsr_usci_paper_forward_eligibility_review_v1 as review


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1" / "latest"
BOUNDED = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"
VALIDATION = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_validation_v1" / "latest"
OBS_YAML = ROOT / "paper_forward_observations" / review.OBSERVATION_ID / "active_observation.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "review_manifest.json",
        "authoritative_evidence_lineage.json",
        "historical_packet_integrity.csv",
        "candidate_fingerprint_verification.json",
        "selection_conditioning_and_regime_disclosure.json",
        "operational_architecture_gate.csv",
        "component_observation_compatibility.csv",
        "cost_accounting_gate.csv",
        "missing_and_stale_data_policy.json",
        "paper_forward_decision.json",
        "direction_owner_activation_record.json",
        "observation_configuration.json",
        "observation_initialization.json",
        "protected_state_verification.json",
        "source_of_truth_changes.csv",
        "review_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_historical_bounded_and_validation_packets_remain_byte_identical() -> None:
    lineage = read_json("authoritative_evidence_lineage.json")
    assert lineage["bounded_screen_byte_identical_after_review"] is True
    assert lineage["validation_byte_identical_after_review"] is True
    for relative_path, expected in lineage["bounded_screen_hashes_before"].items():
        assert sha256(ROOT / relative_path) == expected
        assert lineage["bounded_screen_hashes_after"][relative_path] == expected
    for relative_path, expected in lineage["validation_hashes_before"].items():
        assert sha256(ROOT / relative_path) == expected
        assert lineage["validation_hashes_after"][relative_path] == expected


def test_formal_historical_outcome_labels_remain_unchanged() -> None:
    bounded = json.loads((BOUNDED / "screening_outcome.json").read_text(encoding="utf-8"))
    validation = json.loads((VALIDATION / "validation_outcome.json").read_text(encoding="utf-8"))
    assert bounded["outcome"] == "comparative_evidence_positive"
    assert validation["validation_outcome"] == "validation_supports_paper_forward_review"
    assert read_json("consistency_check.json")["formal_historical_outcome_labels_unchanged"] is True


def test_candidate_weights_and_monthly_schedule_remain_unchanged() -> None:
    fingerprint = read_json("candidate_fingerprint_verification.json")
    assert fingerprint["target_weights"] == {
        review.VM_OBS_ID: 1.0 / 3.0,
        review.DSR_OBS_ID: 1.0 / 3.0,
        review.USCI_OBS_ID: 1.0 / 3.0,
    }
    assert fingerprint["rebalance_rule"] == "first common valid observation session of each calendar month at the close"
    assert fingerprint["between_rebalances"] == "sleeve_values_drift_naturally"
    assert fingerprint["constant_daily_one_third_return_averaging"] is False
    assert read_json("consistency_check.json")["candidate_weights_and_monthly_schedule_unchanged"] is True


def test_existing_observations_and_active_combo_remain_byte_identical() -> None:
    protected = read_json("protected_state_verification.json")
    assert protected["existing_component_observations_and_active_combo_unchanged"] is True
    assert protected["protected_component_and_active_combo_hashes_before"] == protected["protected_component_and_active_combo_hashes_after"]


def test_active_combo_remains_benchmark_reference_only_and_unchanged() -> None:
    active_combo_definition = yaml.safe_load((ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_benchmark_definition.yaml").read_text(encoding="utf-8"))
    active_combo_manifest = json.loads((ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json").read_text(encoding="utf-8"))
    assert active_combo_definition["role"] == "benchmark_reference_only"
    assert active_combo_manifest["active_combo_is_reference_not_active_strategy"] is True
    assert read_json("consistency_check.json")["active_combo_benchmark_reference_only_unchanged"] is True


def test_new_observation_uses_separate_3000_virtual_account() -> None:
    config = read_json("observation_configuration.json")
    init = read_json("observation_initialization.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    assert config["initial_virtual_capital"] == 3000.0
    assert init["derived_sleeve_starting_capital"] == {
        review.VM_OBS_ID: 1000.0,
        review.DSR_OBS_ID: 1000.0,
        review.USCI_OBS_ID: 1000.0,
    }
    assert obs["initial_virtual_capital"] == 3000.0
    assert obs["initial_sleeve_capital"][review.VM_OBS_ID] == 1000.0


def test_existing_component_capital_is_not_reduced_or_reserved() -> None:
    costs = {row["gate"]: row for row in read_csv("cost_accounting_gate.csv")}
    protected = read_json("protected_state_verification.json")
    assert costs["component_capital_not_reduced_or_reserved"]["passed"] == "true"
    assert protected["existing_component_capital_changed"] is False
    assert read_json("consistency_check.json")["existing_component_capital_not_reduced_or_reserved"] is True


def test_sleeve_values_drift_between_monthly_rebalances() -> None:
    config = read_json("observation_configuration.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    assert config["drift_between_rebalances"] is True
    assert obs["drift_between_rebalances"] is True
    assert read_json("consistency_check.json")["sleeve_values_drift_between_monthly_rebalances"] is True


def test_constant_daily_one_third_return_averaging_is_prohibited() -> None:
    fingerprint = read_json("candidate_fingerprint_verification.json")
    assert fingerprint["constant_daily_one_third_return_averaging"] is False
    assert fingerprint["target_weight_forward_filling"] is False
    assert read_json("consistency_check.json")["constant_daily_one_third_return_averaging_prohibited"] is True


def test_monthly_rebalance_restores_one_third_weights() -> None:
    config = read_json("observation_configuration.json")
    assert config["rebalance"] == "monthly"
    assert config["rebalance_session"] == "first_common_valid_session"
    assert all(abs(float(weight) - 1.0 / 3.0) <= 1e-12 for weight in config["component_weights"].values())
    assert read_json("consistency_check.json")["monthly_rebalance_restores_one_third_weights"] is True


def test_turnover_uses_actual_pre_rebalance_sleeve_values() -> None:
    costs = {row["gate"]: row for row in read_csv("cost_accounting_gate.csv")}
    assert costs["turnover_uses_actual_pre_rebalance_sleeve_values"]["passed"] == "true"
    assert read_json("consistency_check.json")["turnover_uses_actual_pre_rebalance_sleeve_values"] is True


def test_component_costs_are_not_reapplied() -> None:
    costs = {row["gate"]: row for row in read_csv("cost_accounting_gate.csv")}
    assert costs["component_costs_not_reapplied"]["passed"] == "true"
    assert read_json("consistency_check.json")["component_costs_not_reapplied"] is True


def test_portfolio_transfer_costs_are_applied_once() -> None:
    costs = {row["gate"]: row for row in read_csv("cost_accounting_gate.csv")}
    assert costs["portfolio_transfer_costs_applied_once"]["passed"] == "true"
    assert "applied once" in costs["portfolio_transfer_costs_applied_once"]["policy"]
    assert read_json("consistency_check.json")["portfolio_transfer_costs_applied_once"] is True


def test_missing_component_returns_are_not_zero_filled() -> None:
    policy = read_json("missing_and_stale_data_policy.json")
    assert policy["missing_component_return_as_zero"] is False
    assert read_json("consistency_check.json")["missing_component_returns_not_zero_filled"] is True


def test_missing_component_returns_are_not_forward_filled() -> None:
    policy = read_json("missing_and_stale_data_policy.json")
    assert policy["forward_fill_missing_component_return"] is False
    assert read_json("consistency_check.json")["missing_component_returns_not_forward_filled"] is True


def test_derived_observation_advances_only_on_complete_common_dates() -> None:
    policy = read_json("missing_and_stale_data_policy.json")
    assert policy["advance_on_partial_component_date"] is False
    assert policy["required_common_component_date"] is True
    assert read_json("consistency_check.json")["derived_observation_advances_only_on_complete_common_dates"] is True


def test_no_historical_research_cache_is_extended_or_refreshed() -> None:
    manifest = read_json("review_manifest.json")
    assert manifest["historical_backtest_run"] is False
    assert manifest["historical_validation_run"] is False
    assert manifest["provider_download"] is False
    assert read_json("consistency_check.json")["no_historical_research_cache_extended_or_refreshed"] is True


def test_no_broker_integration_or_order_placement_is_enabled() -> None:
    decision = read_json("paper_forward_decision.json")
    config = read_json("observation_configuration.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    for payload in (decision, config, obs):
        assert payload.get("broker_integration", False) is False
        assert payload.get("live_orders", False) is False
        assert payload.get("order_placement", False) is False
    assert decision["paper_orders"] is False
    assert obs["paper_orders"] is False
    assert read_json("consistency_check.json")["no_broker_integration_or_order_placement"] is True


def test_no_real_money_flag_becomes_true() -> None:
    decision = read_json("paper_forward_decision.json")
    config = read_json("observation_configuration.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    assert decision["real_money_recommendation"] is False
    assert config["real_money_recommendation"] is False
    assert obs["real_money_recommendation"] is False
    assert read_json("consistency_check.json")["no_real_money_flag_true"] is True


def test_maximum_project_exposure_remains_at_or_below_one() -> None:
    config = read_json("observation_configuration.json")
    fingerprint = read_json("candidate_fingerprint_verification.json")
    assert config["maximum_aggregate_exposure"] <= 1.0
    assert fingerprint["maximum_aggregate_exposure"] <= 1.0
    assert read_json("consistency_check.json")["maximum_project_exposure_lte_1"] is True


def test_output_is_deterministic_except_timestamped_current_observation_data() -> None:
    comparable = [
        path
        for path in sorted(EVIDENCE.iterdir())
        if path.is_file()
        and path.name
        not in {
            "observation_initialization.json",
            "review_manifest.json",
        }
    ]
    before = {path.name: sha256(path) for path in comparable}
    result = review.run()
    after = {path.name: sha256(path) for path in comparable}
    assert result["decision"] == "approve_combo_vm_dsr_usci_paper_forward_observation"
    assert result["next_action"] == "resume_productive_research_while_combo_vm_dsr_usci_observes"
    assert before == after
    assert read_json("consistency_check.json")["output_generation_deterministic_except_timestamped_current_observation_data"] is True


def test_activation_records_are_present_without_promotional_authorization() -> None:
    decision = read_json("paper_forward_decision.json")
    active = yaml.safe_load(ACTIVE_OBSERVATIONS.read_text(encoding="utf-8"))
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert decision["decision"] == "approve_combo_vm_dsr_usci_paper_forward_observation"
    assert decision["next_action"] == "resume_productive_research_while_combo_vm_dsr_usci_observes"
    assert review.OBSERVATION_ID in {row["strategy_id"] for row in active["active_observations"]}
    assert active["latest_combo_vm_dsr_usci_paper_forward_eligibility_review"]["observation_only"] is True
    registry_row = next(row for row in registry["strategies"] if row["id"] == review.OBSERVATION_ID)
    assert registry_row["paper_forward_active"] is True
    assert registry_row["promotion_review_required"] is False
    assert registry_row["candidate_exhaustive_run"] is False
    assert registry_row["real_money_recommendation"] is False


def test_selection_conditioning_and_regime_limitations_remain_explicit() -> None:
    disclosure = read_json("selection_conditioning_and_regime_disclosure.json")
    assert disclosure["current_methodology_evidence_is_selection_conditioned"] is True
    assert disclosure["historical_pre_2021_same_construction_underperformed_active_combo"] is True
    assert disclosure["USCI_pct_total_candidate_gain"] > 0.5
    assert disclosure["paper_forward_observes_currently_applicable_USCI_methodology"] is True
