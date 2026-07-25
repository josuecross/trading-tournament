from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import driesprong_oil_signal_control_strength_audit_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def ensure_evidence() -> None:
    if not (EVIDENCE / "verification_outcome.json").exists():
        impl.run(ROOT)


def read_json(name: str) -> dict:
    ensure_evidence()
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict:
    ensure_evidence()
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    ensure_evidence()
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_existing_corrected_returns_are_not_modified() -> None:
    reconciliation = read_json("existing_evidence_reconciliation.json")
    outcome = read_json("verification_outcome.json")
    consistency = read_json("consistency_check.json")

    assert reconciliation["reconciliation_passed"] is True
    assert reconciliation["source_hashes_before"] == reconciliation["source_hashes_after"]
    assert outcome["source_corrected_evidence_preserved"] is True
    assert consistency["source_corrected_evidence_preserved"] is True


def test_average_exposure_weight_equals_exactly_210_over_242() -> None:
    config = read_yaml("frozen_control_config.yaml")
    outcome = read_json("verification_outcome.json")
    avg = config["average_exposure_control"]

    assert avg["market_state_count"] == 210
    assert avg["evaluation_month_count"] == 242
    assert outcome["average_market_weight_numerator"] == 210
    assert outcome["average_market_weight_denominator"] == 242
    assert abs(float(avg["average_market_weight"]) - (210 / 242)) < 1e-15
    assert abs(float(outcome["average_market_weight"]) - (210 / 242)) < 1e-15


def test_no_alternative_exposure_weights_are_generated() -> None:
    config = read_yaml("frozen_control_config.yaml")
    consistency = read_json("consistency_check.json")

    assert config["no_alternative_exposure_weights_generated"] is True
    assert config["average_exposure_control"]["alternative_exposure_weights_generated"] is False
    assert consistency["only_one_average_exposure_control"] is True


def test_beta_control_uses_one_ols_beta_estimate_only() -> None:
    config = read_yaml("frozen_control_config.yaml")
    outcome = read_json("verification_outcome.json")
    rows = read_csv("beta_matched_control_series.csv")
    betas = {row["estimated_beta"] for row in rows}

    assert config["beta_matched_control"]["estimated_once_over_frozen_evaluation_sample"] is True
    assert config["beta_matched_control"]["beta_capped"] is False
    assert config["beta_matched_control"]["beta_rounded"] is False
    assert config["beta_matched_control"]["beta_optimized"] is False
    assert outcome["beta_estimate_count"] == 1
    assert len(betas) == 1


def test_jensen_alpha_uses_hc1_standard_errors() -> None:
    jensen = read_json("jensen_alpha_audit.json")
    consistency = read_json("consistency_check.json")

    assert jensen["standard_error_method"] == "White_HC1"
    assert jensen["inference"] == "two_sided_t_distribution"
    assert jensen["observation_count"] == 242
    assert abs(jensen["hc1_scale_factor"] - (242 / 240)) < 1e-15
    assert consistency["hc1_standard_errors_used"] is True


def test_bull_and_bear_definitions_compare_market_return_with_rf_return() -> None:
    timing = read_json("market_timing_audit.json")

    assert timing["actual_bull_definition"] == "market_return_t > rf_return_t"
    assert timing["actual_bear_definition"] == "market_return_t <= rf_return_t"
    assert timing["predicted_bull_definition"] == "target_state_t == market"
    assert timing["predicted_bear_definition"] == "target_state_t == risk_free"


def test_timing_test_uses_conditional_bull_and_bear_accuracy() -> None:
    timing = read_json("market_timing_audit.json")
    matrix = read_csv("market_timing_confusion_matrix.csv")
    bear = next(row for row in matrix if row["actual_state"] == "bear_market_return_lte_rf")
    bull = next(row for row in matrix if row["actual_state"] == "bull_market_return_gt_rf")
    p1 = int(bear["predicted_bear_count"]) / int(bear["actual_total"])
    p2 = int(bull["predicted_bull_count"]) / int(bull["actual_total"])

    assert timing["timing_test_uses_conditional_bull_and_bear_accuracy"] is True
    assert abs(timing["conditional_bear_accuracy_p1"] - p1) < 1e-15
    assert abs(timing["conditional_bull_accuracy_p2"] - p2) < 1e-15
    assert abs(timing["p1_plus_p2"] - (p1 + p2)) < 1e-15


def test_switching_costs_are_not_added_to_static_controls() -> None:
    metrics = {row["series_id"]: row for row in read_csv("control_metrics.csv")}
    avg = read_csv("average_exposure_control_series.csv")
    beta = read_csv("beta_matched_control_series.csv")

    assert metrics["average_exposure_static_control"]["switching_cost_bps"] == "0"
    assert metrics["beta_matched_static_control"]["switching_cost_bps"] == "0"
    assert {float(row["switching_cost_rate"]) for row in avg} == {0.0}
    assert {float(row["switching_cost_rate"]) for row in beta} == {0.0}


def test_no_strategy_signal_is_recalculated_or_configuration_altered() -> None:
    outcome = read_json("verification_outcome.json")
    config = read_yaml("frozen_control_config.yaml")
    reconciliation = read_json("existing_evidence_reconciliation.json")

    assert outcome["strategy_signal_recalculated"] is False
    assert outcome["oil_predictor_recomputed"] is False
    assert outcome["fixed_coefficients_changed"] is False
    assert outcome["chronological_split_changed"] is False
    assert outcome["transaction_cost_assumptions_changed"] is False
    assert outcome["data_sources_changed"] is False
    assert outcome["market_or_risk_free_return_definitions_changed"] is False
    assert outcome["parameter_search_run"] is False
    assert outcome["predictor_alternative_tested"] is False
    assert outcome["split_alternative_tested"] is False
    assert outcome["instrument_alternative_tested"] is False
    assert config["dynamic_baseline"]["strategy_signal_recalculated"] is False
    assert reconciliation["strategy_signal_recalculated"] is False


def test_no_overlay_performance_artifact_or_broker_write_is_created() -> None:
    outcome = read_json("verification_outcome.json")
    tm = read_json("trade_management_gate.json")

    assert outcome["overlay_performance_experiment_run"] is False
    assert tm["overlay_performance_experiment_run"] is False
    assert not any("overlay_performance" in path.name for path in EVIDENCE.iterdir())
    assert outcome["broker_write_called"] is False


def test_existing_strategy_and_state_files_remain_unchanged() -> None:
    outcome = read_json("verification_outcome.json")
    consistency = read_json("consistency_check.json")

    assert outcome["state_files_preserved"] is True
    assert consistency["state_files_preserved"] is True
    assert outcome["promotion_eligibility"] is False
    assert outcome["paper_demo_eligibility"] is False
    assert outcome["paper_demo_state_changed"] is False
    assert outcome["candidate_exhaustive_run"] is False
    assert outcome["real_money_recommendation"] is False


def test_outcome_and_trade_management_gate_mapping_are_valid() -> None:
    outcome = read_json("verification_outcome.json")
    tm = read_json("trade_management_gate.json")

    assert outcome["outcome"] in impl.OUTCOMES
    assert outcome["trade_management_gate"] == impl.TRADE_MANAGEMENT_GATES[outcome["outcome"]]
    assert tm["trade_management_gate"] == outcome["trade_management_gate"]
    assert outcome["next_action"] == impl.NEXT_ACTION


def test_output_generation_core_is_deterministic() -> None:
    consistency = read_json("consistency_check.json")
    outcome = read_json("verification_outcome.json")

    assert consistency["consistency_passed"] is True
    assert consistency["source_corrected_evidence_preserved"] is True
    assert consistency["average_exposure_weight_frozen"] is True
    assert outcome["evaluation_month_count"] == 242


def test_ols_hc1_helper_is_deterministic_on_synthetic_data() -> None:
    x = pd.Series(np.linspace(-0.03, 0.04, 20))
    y = pd.Series(0.002 + 0.7 * x + np.linspace(-0.01, 0.01, 20))
    first = impl.ols_with_hc1(x, y)
    second = impl.ols_with_hc1(x, y)

    assert first == second
    assert first["standard_error_method"] == "White_HC1"
