from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.faber_gtaa5_10m_sma_equal_weight_etf_bil_v1 import (
    OUTPUT_DIR,
    RISKY_SLEEVE_COUNT,
    SLEEVE_WEIGHT,
    SMA_MONTHS,
    TASK_ID,
    TRIAL_ID,
    deterministic_core_hash,
    run,
    signal_states,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_and_task_contract() -> None:
    required = [
        "source_packet_used.yaml",
        "exact_duplicate_check.json",
        "repository_fit_check.json",
        "frozen_universe_reference.json",
        "source_to_etf_mapping.csv",
        "frozen_trial_manifest.csv",
        "data_coverage.csv",
        "monthly_price_matrix.csv",
        "sma_signal_audit.csv",
        "target_weights.csv",
        "transactions.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "family_outcome.json",
        "family_followup_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "implementation_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    check = load_json("consistency_check.json")
    assert check["task_id"] == TASK_ID
    assert check["task_outcome"] == "gtaa5_fast_lane_complete"
    assert check["consistency_passed"] is True


def test_source_mapping_contains_exactly_five_risky_sleeves() -> None:
    rows = csv_rows("source_to_etf_mapping.csv")
    risky = [row for row in rows if row["source_sleeve"] != "treasury_bills"]
    by_sleeve = {row["source_sleeve"]: row for row in rows}
    assert len(risky) == RISKY_SLEEVE_COUNT
    assert [row["selected_symbol"] for row in risky] == ["SPY", "EFA", "IEF", "DBC", "IYR"]
    assert by_sleeve["broad_commodities"]["expected_symbol"] == "GSG"
    assert by_sleeve["broad_commodities"]["selected_symbol"] == "DBC"
    assert by_sleeve["us_reits"]["expected_symbol"] == "VNQ"
    assert by_sleeve["us_reits"]["selected_symbol"] == "IYR"
    assert all(row["source_preserving"] == "True" for row in rows)
    assert all(row["selection_performance_independent"] == "True" for row in rows)


def test_sma_rule_activates_deactivates_and_equality_retains_state() -> None:
    index = pd.date_range("2020-01-31", periods=12, freq="ME")
    base = pd.Series([100.0] * 9 + [120.0, 920.0 / 9.0, 90.0], index=index)
    monthly = pd.DataFrame({"SPY": base})
    states, audit = signal_states(monthly, ["SPY"])

    assert SMA_MONTHS == 10
    assert bool(states.loc[index[9], "SPY"]) is True
    assert audit.loc[index[9], "SPY_price"] > audit.loc[index[9], "SPY_sma10"]
    assert bool(states.loc[index[10], "SPY"]) is True
    assert abs(audit.loc[index[10], "SPY_price"] - audit.loc[index[10], "SPY_sma10"]) <= 1e-12
    assert bool(states.loc[index[11], "SPY"]) is False
    assert audit.loc[index[11], "SPY_price"] < audit.loc[index[11], "SPY_sma10"]


def test_every_risky_weight_is_zero_or_twenty_percent_and_bil_receives_inactive_weight() -> None:
    targets = csv_rows("target_weights.csv")
    risky = ["SPY", "EFA", "IEF", "DBC", "IYR"]
    assert targets
    for row in targets:
        active = 0
        for symbol in risky:
            value = float(row[symbol])
            assert value in {0.0, SLEEVE_WEIGHT}
            active += int(value == SLEEVE_WEIGHT)
        bil = float(row["BIL"])
        assert round(bil, 10) in {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}
        assert abs(bil - (1.0 - active * SLEEVE_WEIGHT)) <= 1e-10
        assert abs(float(row["weight_sum"]) - 1.0) <= 1e-10
        assert int(row["active_risky_sleeve_count"]) == active


def test_no_same_period_execution_and_no_ranking_or_parameter_variants() -> None:
    baseline = csv_rows("baseline_metrics.csv")[0]
    manifest = csv_rows("frozen_trial_manifest.csv")[0]
    check = load_json("consistency_check.json")

    assert baseline["first_signal_date"] < baseline["start_date"]
    assert manifest["sma_months"] == "10"
    assert manifest["sleeve_weight"] == "0.2"
    assert manifest["portfolio_trial_count"] == "1"
    assert manifest["frozen_before_return_calculation"] == "True"
    assert check["no_cross_sectional_ranking"] is True
    assert check["no_top_n_logic"] is True
    assert check["sma_length_exactly_10_months"] is True


def test_exact_duplicate_check_did_not_find_verified_portfolio_duplicate() -> None:
    duplicate = load_json("exact_duplicate_check.json")
    assert duplicate["duplicate_check_completed_before_return_calculation"] is True
    assert duplicate["exact_duplicate_found"] is False
    reviewed = {row["name"]: row for row in duplicate["reviewed_records"]}
    assert reviewed["faber_10m_sma_long_bil_portability_v1"]["assessment"] == "not_exact_duplicate"
    assert reviewed["quantpedia_asset_class_trend_following_5asset_10m_v1"]["assessment"] == "not_exact_duplicate"


def test_exactly_one_portfolio_trial_and_identical_control_calendar() -> None:
    manifest = csv_rows("frozen_trial_manifest.csv")
    controls = csv_rows("control_metrics.csv")
    baseline = csv_rows("baseline_metrics.csv")[0]
    control_ids = {row["control_id"] for row in controls}

    assert len(manifest) == 1
    assert manifest[0]["trial_id"] == TRIAL_ID
    assert manifest[0]["portfolio_trial_count"] == "1"
    assert control_ids == {
        "equal_weight_buy_hold_monthly_rebalanced",
        "BIL_buy_hold",
        "static_average_weight_control_ex_post_diagnostic",
        "zero_cost_gtaa_baseline",
        "five_bps_gtaa_diagnostic",
    }
    assert all(row["start_date"] == baseline["start_date"] and row["end_date"] == baseline["end_date"] for row in controls)


def test_costs_apply_only_to_changed_notional() -> None:
    transactions = csv_rows("transactions.csv")
    baseline = csv_rows("baseline_metrics.csv")[0]
    assert transactions
    assert len(transactions) == int(baseline["trade_count"])
    for row in transactions:
        assert row["cost_applies_only_to_changed_notional"] == "True"
        assert float(row["turnover_proxy"]) > 0.0
        assert abs(float(row["cost_return_deduction"]) - float(row["turnover_proxy"]) * float(row["cost_rate"])) <= 1e-15


def test_family_outcome_and_non_promotional_flags() -> None:
    family = load_json("family_outcome.json")
    assert family["family_outcome"] in {
        "family_exploratory_followup_candidate",
        "family_timeframe_fragile",
        "family_control_weak",
        "family_cost_fragile",
        "implementation_or_accounting_defect",
    }
    assert family["family_outcome_allowed"] is True
    assert family["promotion_eligibility"] is False
    assert family["paper_forward_eligibility"] is False
    assert family["candidate_exhaustive_eligibility"] is False


def test_no_overlay_registry_paper_broker_or_provider_state_changes() -> None:
    check = load_json("consistency_check.json")
    names = {path.name.lower() for path in EVIDENCE.iterdir()}
    assert all("overlay" not in name for name in names)
    assert check["no_overlay_output_generated"] is True
    assert check["registry_lifecycle_unchanged"] is True
    assert check["active_paper_demo_state_unchanged"] is True
    assert check["broker_or_order_path_touched"] is False
    assert check["provider_download"] is False
    assert check["intraday_data_used"] is False
    assert check["paper_forward_activation"] is False
    assert check["promotion_candidates_created"] is False
    assert check["candidate_exhaustive_run"] is False
    assert check["real_money_recommendation"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
