from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

import run_active_strategy_evidence_recompute as active_recompute
from strategy_lab.research_os.research import dsr_active_evidence_mismatch_review as review


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "dsr_active_evidence_mismatch_review" / "latest"


def read_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str):
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def synthetic_close(rising: set[str], periods: int = 260) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=periods)
    data: dict[str, list[float]] = {}
    for symbol in [*active_recompute.SECTOR_ASSETS, "BIL"]:
        if symbol == "BIL":
            data[symbol] = [100.0 + idx * 0.01 for idx in range(periods)]
        elif symbol in rising:
            data[symbol] = [50.0 + idx * 0.20 for idx in range(periods)]
        else:
            data[symbol] = [100.0 - idx * 0.05 for idx in range(periods)]
    return pd.DataFrame(data, index=dates)


def test_required_mismatch_review_packet_exists() -> None:
    required = [
        "dsr_mismatch_review.json",
        "dsr_mismatch_review.md",
        "methodology_comparison.csv",
        "metric_comparison.csv",
        "first_divergence.csv",
        "daily_path_comparison.csv",
        "weight_exposure_invariants.csv",
        "artifact_lineage.csv",
        "unresolved_assumptions.csv",
        "superseded_metrics.csv",
        "mismatch_review_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename


def test_root_cause_and_reproducibility_are_recorded() -> None:
    manifest = read_json("dsr_mismatch_review.json")

    assert manifest["target_active_observation_id"] == review.ACTIVE_ID
    assert manifest["root_cause_verdict"] == "unresolved_missing_inputs"
    assert manifest["root_cause_secondary_classification"] == "non_comparable_methodologies"
    assert manifest["recovered_4071_reproducible"] is False
    assert manifest["current_3481_reproducible"] is True
    assert manifest["current_best_final_equity"] == 3481.6998
    assert manifest["current_recompute_defect_found"] is False
    assert manifest["recovered_metric_status"] == "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference"
    assert "current_diagnostic_only_not_historical_replacement" in manifest["defensible_current_diagnostic_reference"]


def test_dsr_recompute_is_deterministic() -> None:
    sample_rows = review.current_sample_rows(ROOT)
    best = max(row["final_equity"] for row in sample_rows)

    assert len(sample_rows) == active_recompute.MAX_WINDOWS_PER_HORIZON
    assert round(best, 4) == 3481.6998


def test_current_dsr_weight_sum_and_exposure_never_exceed_one() -> None:
    rows = read_csv("weight_exposure_invariants.csv")
    by_check = {row["check"]: row for row in rows}

    assert by_check["max_daily_exposure_lte_1"]["passed"] == "True"
    assert by_check["max_daily_weight_sum_lte_1"]["passed"] == "True"
    assert by_check["bil_remainder_not_additive"]["passed"] == "True"
    assert float(by_check["max_daily_exposure_lte_1"]["observed_value"]) <= 1.000001


def test_zero_targets_remain_zero_and_stale_weights_are_removed() -> None:
    best_start, _ = review.best_sample_start(ROOT)
    trace = review.trace_window(ROOT, best_start)

    assert trace
    for row in trace:
        for removed in row["removed_symbols_on_rebalance"]:
            assert removed not in row["weights"]
    assert any(row["rebalanced"] for row in trace)
    assert all(row["weight_sum"] <= 1.000001 for row in trace)


def test_bil_fallback_behavior_for_none_one_two_and_three_sectors() -> None:
    none = active_recompute.dsr_equal_weight(synthetic_close(set()), 220)
    one = active_recompute.dsr_equal_weight(synthetic_close({"XLK"}), 220)
    two = active_recompute.dsr_equal_weight(synthetic_close({"XLK", "XLP"}), 220)
    three = active_recompute.dsr_equal_weight(synthetic_close({"XLK", "XLP", "XLU"}), 220)

    assert none == {"BIL": 1.0}
    assert one == pytest.approx({"XLK": 1.0 / 3.0, "BIL": 2.0 / 3.0})
    assert two == pytest.approx({"XLK": 1.0 / 3.0, "XLP": 1.0 / 3.0, "BIL": 1.0 / 3.0})
    assert three == pytest.approx({"XLK": 1.0 / 3.0, "XLP": 1.0 / 3.0, "XLU": 1.0 / 3.0})


def test_rebalance_timing_and_signal_execution_lag_are_one_trading_day() -> None:
    close, missing = active_recompute.prepare_prices(ROOT)
    assert missing == []
    best_start, _ = review.best_sample_start(ROOT)
    trace = review.trace_window(ROOT, best_start)
    index_positions = {str(date.date()): idx for idx, date in enumerate(close.index)}

    assert trace[0]["date"] == str(close.index[best_start + 1].date())
    assert trace[0]["signal_date"] == str(close.index[best_start].date())
    for row in trace:
        assert index_positions[row["date"]] - index_positions[row["signal_date"]] == 1


def test_per_asset_availability_excludes_xlc_before_inception() -> None:
    close, missing = active_recompute.prepare_prices(ROOT)
    assert missing == []
    early_index = close.index.get_loc(pd.Timestamp("2008-01-03"))

    assert active_recompute.eligible(close, "XLC", early_index) is False
    early_weights = active_recompute.dsr_equal_weight(close, early_index)
    assert "XLC" not in early_weights


def test_date_range_selection_matches_current_recompute_sample_windows() -> None:
    sample_rows = review.current_sample_rows(ROOT)
    windows = [(row["window_start"], row["window_end"]) for row in sample_rows]

    assert windows == [
        ("2008-01-03", "2008-09-19"),
        ("2012-06-06", "2013-02-26"),
        ("2016-11-10", "2017-08-01"),
        ("2021-04-21", "2022-01-05"),
        ("2025-09-30", "2026-06-18"),
    ]


def test_initial_capital_and_final_equity_calculation_match_evidence() -> None:
    sample_rows = review.current_sample_rows(ROOT)
    best = max(sample_rows, key=lambda row: row["final_equity"])

    assert active_recompute.STARTING_EQUITY == 3000.0
    assert round(best["final_equity"], 4) == 3481.6998
    assert round(best["profit_dollars"], 4) == round(best["final_equity"] - 3000.0, 4)


def test_first_divergence_is_artifact_level_due_missing_recovered_path() -> None:
    rows = read_csv("first_divergence.csv")
    assert len(rows) == 1
    row = rows[0]

    assert row["divergence_type"] == "artifact_level"
    assert row["date"] == "not_available"
    assert "Recovered best_final_equity has no source window list" in row["first_assumption_or_transformation"]


def test_metric_taxonomy_does_not_replace_historical_value() -> None:
    rows = read_csv("superseded_metrics.csv")
    best = next(row for row in rows if row["metric"] == "best_final_equity")

    assert best["recovered_value"] == "4071.04"
    assert best["current_recomputed_value"] == "3481.6998"
    assert best["status"] == "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference"
    assert "not a historical replacement" in best["reason"]


def test_consistency_guardrails_hold() -> None:
    consistency = read_json("mismatch_review_consistency_check.json")

    assert consistency["consistency_passed"] is True
    assert consistency["canonical_hashes_unchanged"] is True
    assert consistency["no_new_backtest_run"] is True
    assert consistency["no_provider_download"] is True
    assert consistency["no_strategy_lifecycle_change"] is True
    assert consistency["no_paper_demo_state_change"] is True
    assert consistency["no_frozen_rule_change"] is True
