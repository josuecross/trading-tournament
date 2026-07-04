from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_percent_b_money_flow_bounded_bt_run import (
    EXPECTED_VARIANTS,
    LANE_ID,
    money_flow_index,
    one_bar_delayed_targets,
    percent_b,
    primary_percent_b_targets,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_run" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_percent_b_money_flow_bounded_bt_run_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_percent_b_money_flow_bounded_bt_run_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def load_rows() -> list[dict[str, str]]:
    with (EVIDENCE / "row_level_results.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def test_manifest_exact_bounded_lane_run_contract() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_percent_b_money_flow_bounded_bt_lane_run"] is True
    assert manifest["source_id"] == "percent_b_money_flow"
    assert manifest["family_id"] == "price_band_money_flow_confirmation"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["indicator_formula_implemented"] is True
    assert manifest["indicator_parameters_source_backed"] is True
    assert manifest["variant_count_planned"] == 5
    assert manifest["variant_count_evaluated"] == 5
    assert manifest["approved_variant_ids"] == list(EXPECTED_VARIANTS)
    assert set(manifest["evaluated_variant_ids"]) == set(EXPECTED_VARIANTS)
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert consistency["consistency_passed"] is True


def test_guardrails_and_non_promotable_outputs() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["bounded_bt_design_changed"] is False
    assert manifest["new_instruments_added"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["other_indicators_added"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True
    assert manifest["candidate_exhaustive_ready"] is False
    assert manifest["paper_demo_eligible"] is False
    assert all(bool_text(row["promotion_eligibility"]) is False for row in rows)
    assert all(bool_text(row["paper_forward_eligibility"]) is False for row in rows)
    assert all(bool_text(row["candidate_exhaustive_eligibility"]) is False for row in rows)


def test_row_results_have_expected_roles_labels_and_criteria_fields() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["data_blocked_row_count"] == 0
    assert {row["variant_id"] for row in rows} == set(EXPECTED_VARIANTS)
    assert {row["variant_role"] for row in rows} == {"source_primary", "timing_sanity", "control"}
    assert {row["research_label"] for row in rows} == {
        "public_source_percent_b_mfi_primary",
        "public_source_percent_b_mfi_timing_sanity",
        "public_source_percent_b_mfi_control_only",
    }
    assert {row["symbols_used"] for row in rows} <= {"SPY", "BIL", "SPY|BIL"}
    assert manifest["results_interpretable"] is True
    assert manifest["usable_diagnostic_evidence"] is True
    assert isinstance(manifest["primary_row_numeric_criteria_pass"], bool)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert primary["indicator_formula_status"] == "percent_b_bb20_2_and_mfi10_calculated_from_local_spy_ohlcv"
    assert "bollinger_band_period=20" in primary["indicator_parameters"]
    assert "money_flow_index_period=10" in primary["indicator_parameters"]


def test_exposure_and_cash_bil_invariants_in_outputs() -> None:
    manifest = load_manifest()
    weights = pd.read_csv(EVIDENCE / "daily_target_weights.csv")
    rows = load_rows()

    assert manifest["invariant_failure_count"] == 0
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert weights["weight_sum"].max() <= 1.000001
    assert weights["risky_exposure"].max() <= 1.000001
    assert weights[["SPY", "BIL"]].min().min() >= -1e-9
    assert not weights[["SPY", "BIL", "weight_sum"]].isna().any().any()
    assert all(bool_text(row["exposure_invariant_pass"]) is True for row in rows)
    assert all(int(float(row["weight_sum_violation_count"])) == 0 for row in rows)
    assert all(int(float(row["negative_weight_violation_count"])) == 0 for row in rows)
    assert all(int(float(row["nan_weight_count"])) == 0 for row in rows)
    assert all(int(float(row["impossible_cash_and_risky_exposure_days"])) == 0 for row in rows)


def test_indicator_and_signal_state_helpers_are_deterministic() -> None:
    index = pd.date_range("2024-01-01", periods=8, freq="D")
    indicators = pd.DataFrame(
        {
            "percent_b": [0.1, 0.9, 0.7, 0.6, 0.1, 0.3, 0.95, 0.4],
            "mfi": [10, 90, 70, 60, 10, 50, 95, 40],
        },
        index=index,
    )
    indicators["entry_signal"] = (indicators["percent_b"] > 0.8) & (indicators["mfi"] > 80)
    indicators["exit_signal"] = (indicators["percent_b"] < 0.2) & (indicators["mfi"] < 20)

    primary = primary_percent_b_targets(indicators)
    delayed = one_bar_delayed_targets(primary)

    assert primary.loc["2024-01-01"].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert primary.loc["2024-01-02"].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert primary.loc["2024-01-04"].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert primary.loc["2024-01-05"].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert delayed.loc["2024-01-02"].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert delayed.loc["2024-01-03"].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert delayed.loc["2024-01-06"].to_dict() == {"SPY": 0.0, "BIL": 1.0}


def test_indicator_formulas_return_bounded_values_after_warmup() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    close = pd.Series(range(1, 31), index=index, dtype=float)
    high = close + 1.0
    low = close - 1.0
    volume = pd.Series(1000.0, index=index)

    pb = percent_b(close, period=20, std_mult=2.0)
    mfi = money_flow_index(high, low, close, volume, period=10)

    assert pb.dropna().between(-10.0, 10.0).all()
    assert mfi.dropna().between(0.0, 100.0).all()
    assert mfi.dropna().iloc[-1] == 100.0


def test_required_evidence_files_and_next_action() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    required = consistency["required_files"]

    assert manifest["next_action"] == "audit_public_source_percent_b_money_flow_bounded_bt_results"
    assert all(required.values())
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
