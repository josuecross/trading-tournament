from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from strategy_lab.research_os.research import combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "preregistration.json",
        "candidate_fingerprint.json",
        "component_source_lineage.csv",
        "duplicate_review.csv",
        "common_date_alignment.csv",
        "frozen_monthly_rebalance_dates.csv",
        "frozen_chronological_blocks.csv",
        "frozen_180d_windows.csv",
        "frozen_252d_windows.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "window_level_results.csv",
        "calendar_year_results.csv",
        "primary_benchmark_relative_metrics.csv",
        "component_contribution.csv",
        "sleeve_weight_drift.csv",
        "diversification_attribution.csv",
        "cost_and_turnover_attribution.csv",
        "accounting_date_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "beta_rotation_direction_memory.json",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_component_identities_and_fingerprints_are_frozen() -> None:
    prereg = read_json("preregistration.json")
    assert prereg["components"] == [
        "vm_quality_lowvol_proxy_v1",
        "dsr_sector_equal_weight_defensive_filter_v1",
        "usci_dynamic_commodity_curve_selection_wrapper_v1",
    ]
    lineage = read_csv("component_source_lineage.csv")
    assert {row["component_id"] for row in lineage} == set(prereg["components"])
    assert all(row["component_fingerprint"] for row in lineage)
    assert read_json("consistency_check.json")["component_identities_and_fingerprints_frozen"] is True


def test_active_combo_and_observations_remain_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["active_combo_remains_byte_identical"] is True
    assert check["VM_DSR_USCI_observations_unchanged"] is True
    assert check["no_paper_demo_observation_or_broker_order"] is True


def test_constant_one_third_daily_return_averaging_is_prohibited() -> None:
    prereg = read_json("preregistration.json")
    assert prereg["constant_weight_daily_return_averaging"] is False
    assert read_json("consistency_check.json")["constant_one_third_daily_return_averaging_prohibited"] is True


def test_sleeve_weights_drift_between_monthly_rebalances() -> None:
    rows = read_csv("sleeve_weight_drift.csv")
    assert rows
    assert any(float(row["maximum_weight_between_rebalances"]) - float(row["minimum_weight_between_rebalances"]) > 0.01 for row in rows)
    assert read_json("consistency_check.json")["sleeve_weights_drift_between_monthly_rebalances"] is True


def test_monthly_rebalances_restore_exact_one_third_targets() -> None:
    events = [row for row in read_csv("cost_and_turnover_attribution.csv") if row.get("cost_layer") == "rebalance_event"]
    assert events
    for row in events[:10]:
        assert abs(float(row["vm_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
        assert abs(float(row["dsr_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
        assert abs(float(row["usci_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
    assert read_json("consistency_check.json")["monthly_rebalances_restore_one_third_targets"] is True


def test_internal_component_costs_are_not_reapplied_and_portfolio_transfer_costs_apply_once() -> None:
    costs = read_csv("cost_and_turnover_attribution.csv")
    component = next(row for row in costs if row["cost_layer"] == "component_internal")
    transfer = next(row for row in costs if row["cost_layer"] == "portfolio_initial_and_monthly_transfers")
    assert component["double_counted"] == "false"
    assert transfer["double_counted"] == "false"
    assert float(transfer["cost_amount"]) > 0
    check = read_json("consistency_check.json")
    assert check["internal_component_costs_not_reapplied"] is True
    assert check["portfolio_level_transfer_costs_applied_once"] is True


def test_turnover_uses_actual_pre_rebalance_sleeve_values() -> None:
    events = [row for row in read_csv("cost_and_turnover_attribution.csv") if row.get("rebalance_type") == "monthly_restore_one_third"]
    assert events
    assert any(row["pre_vm_weight"] and row["pre_dsr_weight"] and row["pre_usci_weight"] for row in events)
    assert read_json("consistency_check.json")["turnover_uses_actual_pre_rebalance_sleeve_values"] is True


def test_missing_component_dates_are_not_filled_and_common_dates_are_used() -> None:
    alignment = read_csv("common_date_alignment.csv")
    assert alignment
    assert all(row["missing_dates_filled_with_zero"] == "false" for row in alignment)
    assert all(row["missing_dates_forward_filled"] == "false" for row in alignment)
    assert read_json("consistency_check.json")["missing_component_dates_not_filled"] is True
    assert read_json("consistency_check.json")["common_aligned_dates_only"] is True


def test_maximum_exposure_never_exceeds_one() -> None:
    inv = read_csv("accounting_date_and_exposure_invariants.csv")[0]
    assert float(inv["maximum_aggregate_exposure"]) <= 1.000001
    assert float(inv["maximum_aggregate_weight_sum"]) <= 1.000001
    assert inv["exposure_never_exceeds_1"] == "true"
    assert read_json("consistency_check.json")["maximum_exposure_never_exceeds_1"] is True


def test_windows_and_rebalance_dates_frozen_before_performance() -> None:
    for filename in ("frozen_monthly_rebalance_dates.csv", "frozen_chronological_blocks.csv", "frozen_180d_windows.csv", "frozen_252d_windows.csv"):
        rows = read_csv(filename)
        assert rows
        assert all(row["frozen_before_performance"] == "true" for row in rows)
    assert read_json("consistency_check.json")["windows_and_rebalance_dates_frozen_before_performance"] is True


def test_no_weight_or_frequency_optimization_occurs() -> None:
    prereg = read_json("preregistration.json")
    assert prereg["no_optimization"] is True
    assert prereg["rebalance_rule"] == "first common valid trading session of each calendar month at the close"
    assert read_json("consistency_check.json")["no_weight_or_frequency_optimization"] is True


def test_output_is_deterministic_and_non_promotional() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    check = read_json("consistency_check.json")
    assert check["output_generation_deterministic"] is True
    assert check["promotion_authorized"] is False
    assert check["paper_demo_authorized"] is False
    assert check["candidate_exhaustive_authorized"] is False
    assert check["real_money_recommendation"] is False
    assert check["consistency_passed"] is True


def test_outcome_is_single_frozen_allowed_label_and_family_state_is_preserved() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert memory["broader_multi_strategy_diversified_portfolio_family_closed"] == "false"
    beta_memory = read_json("beta_rotation_direction_memory.json")
    assert beta_memory["formal_outcome"] == "control_weak"
    assert beta_memory["validation_authorized"] is False
