from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import risk_parity_trend_etf_wrapper_screen_v1 as screen
from strategy_lab.research_os.research import risk_parity_trend_portfolio_accounting_review_v1 as review


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "risk_parity_trend_portfolio_accounting_review_v1" / "latest"
SCREEN_EVIDENCE = ROOT / "evidence" / "risk_parity_trend_etf_wrapper_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_review_evidence() -> dict[str, object]:
    return review.run()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def synthetic_path(price_b: list[float]) -> screen.ReturnPath:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"])
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0, 121.0], "B": price_b}, index=dates)
    targets = pd.DataFrame(
        {"A": [0.5, 0.5], "B": [0.5, 0.5]},
        index=pd.to_datetime(["2020-01-02", "2020-01-06"]),
    )
    return screen.run_weighted_path("synthetic", prices, targets, ["A", "B"], apply_slippage=True)


def test_different_asset_returns_create_weight_drift_between_rebalances() -> None:
    path = synthetic_path([100.0, 100.0, 100.0, 100.0])
    assert float(path.weights.at[pd.Timestamp("2020-01-02"), "A"]) > 0.5
    assert float(path.weights.at[pd.Timestamp("2020-01-03"), "A"]) > float(path.weights.at[pd.Timestamp("2020-01-02"), "A"])
    assert float(path.weights.at[pd.Timestamp("2020-01-03"), "B"]) < 0.5


def test_no_trade_occurs_between_scheduled_monthly_execution_dates() -> None:
    path = synthetic_path([100.0, 100.0, 100.0, 100.0])
    assert float(path.turnover.at[pd.Timestamp("2020-01-03")]) == pytest.approx(0.0)
    assert float(path.cost.at[pd.Timestamp("2020-01-03")]) == pytest.approx(0.0)


def test_monthly_equal_weight_rebalance_turnover_uses_drifted_pre_trade_weights() -> None:
    path = synthetic_path([100.0, 100.0, 100.0, 100.0])
    rebalance = pd.Timestamp("2020-01-06")
    pre_trade_a = float(path.pre_trade_weights.at[rebalance, "A"])
    expected_turnover = 0.5 * (abs(0.5 - pre_trade_a) + abs(0.5 - float(path.pre_trade_weights.at[rebalance, "B"])))
    assert pre_trade_a != pytest.approx(0.5)
    assert float(path.turnover.at[rebalance]) == pytest.approx(expected_turnover)
    assert float(path.turnover.at[rebalance]) > 0.0


def test_identical_asset_returns_create_no_drift_related_turnover() -> None:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"])
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0, 133.1], "B": [200.0, 220.0, 242.0, 266.2]}, index=dates)
    targets = pd.DataFrame(
        {"A": [0.5, 0.5], "B": [0.5, 0.5]},
        index=pd.to_datetime(["2020-01-02", "2020-01-06"]),
    )
    path = screen.run_weighted_path("synthetic_equal_returns", prices, targets, ["A", "B"], apply_slippage=True)
    assert float(path.weights.at[pd.Timestamp("2020-01-03"), "A"]) == pytest.approx(0.5)
    assert float(path.turnover.at[pd.Timestamp("2020-01-06")]) == pytest.approx(0.0)


def test_transaction_costs_are_charged_only_when_a_trade_occurs() -> None:
    path = synthetic_path([100.0, 100.0, 100.0, 100.0])
    assert float(path.cost.at[pd.Timestamp("2020-01-03")]) == pytest.approx(0.0)
    assert float(path.cost.at[pd.Timestamp("2020-01-06")]) == pytest.approx(float(path.turnover.at[pd.Timestamp("2020-01-06")]) * screen.SLIPPAGE)


def test_daily_returns_use_actual_drifting_holdings_not_constant_targets() -> None:
    path = synthetic_path([100.0, 100.0, 100.0, 100.0])
    date = pd.Timestamp("2020-01-03")
    actual = float(path.pre_trade_weights.at[date, "A"]) * 0.10 + float(path.pre_trade_weights.at[date, "B"]) * 0.0
    constant_target = 0.5 * 0.10
    assert float(path.daily_returns.at[date]) == pytest.approx(actual)
    assert float(path.daily_returns.at[date]) != pytest.approx(constant_target)


def test_review_required_files_and_decision_exist() -> None:
    required = {
        "decision.json",
        "decision.md",
        "accounting_method_inventory.csv",
        "candidate_rebalance_reconstruction.csv",
        "equal_weight_rebalance_reconstruction.csv",
        "target_vs_actual_weights.csv",
        "turnover_and_cost_review.csv",
        "accounting_differences.csv",
        "before_after_metrics.csv",
        "superseded_screening_artifacts.csv",
        "corrected_screening_outcome.json",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    decision = read_json(EVIDENCE / "decision.json")
    assert decision["decision"] == "accounting_defect_confirmed"
    assert decision["previous_metrics_superseded"] is True
    assert decision["original_control_weak_outcome_remains_valid"] is True


def test_target_and_actual_weights_are_reported_separately() -> None:
    rows = read_csv(SCREEN_EVIDENCE / "daily_path_and_weights.csv")
    header = set(rows[0])
    assert "URTH_target_weight" in header
    assert "URTH_pre_trade_weight" in header
    assert "URTH_actual_weight" in header
    assert any(abs(float(row["URTH_target_weight"]) - float(row["URTH_actual_weight"])) > 1e-6 for row in rows)


def test_candidate_mixed_bil_risky_allocations_remain_valid() -> None:
    rows = read_csv(SCREEN_EVIDENCE / "daily_path_and_weights.csv")
    assert any(float(row["BIL_target_weight"]) > 0.0 and float(row["risky_exposure"]) > 0.0 for row in rows)
    invariants = read_csv(SCREEN_EVIDENCE / "exposure_and_weight_invariants.csv")
    mixed = [row for row in invariants if row["invariant"] == "intentional_mixed_bil_risky_allowed"]
    assert mixed and mixed[0]["passed"] == "true"


def test_candidate_and_equal_weight_use_same_accounting_method() -> None:
    rows = read_csv(EVIDENCE / "accounting_method_inventory.csv")
    current = [row for row in rows if row["method_version"] == "corrected_drifting_holdings_method"]
    assert current
    assert current[0]["turnover_basis"] == "0.5 * abs(new target - pre-trade actual)"
    review_rows = read_csv(EVIDENCE / "turnover_and_cost_review.csv")
    assert {row["strategy_id"] for row in review_rows} == {
        screen.CANDIDATE_ID,
        "equal_weight_same_five_risky_etfs_benchmark_only",
    }


def test_frozen_cache_hashes_windows_and_guardrails_remain_unchanged() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    assert check["frozen_windows_unchanged"] is True
    assert check["cache_hashes_unchanged"] is True
    assert check["no_provider_call"] is True
    assert check["no_parameter_search"] is True
    assert check["no_lifecycle_or_paper_demo_state_change"] is True
    screen_manifest = read_json(SCREEN_EVIDENCE / "execution_manifest.json")
    assert screen_manifest["no_provider_calls"] is True
    assert screen_manifest["no_parameter_wrapper_universe_or_window_search"] is True


def test_equal_weight_benchmark_turnover_anomaly_is_fixed() -> None:
    metrics = read_csv(SCREEN_EVIDENCE / "benchmark_metrics.csv")
    equal_rows = [row for row in metrics if row["strategy_id"] == "equal_weight_same_five_risky_etfs_benchmark_only"]
    assert len(equal_rows) == 2
    assert all(float(row["turnover"]) > 0.0 for row in equal_rows)
    assert all(float(row["allocation_change_count"]) > 0.0 for row in equal_rows)


def test_corrected_generation_is_deterministic() -> None:
    first = read_json(EVIDENCE / "decision.json")
    rerun = review.run()
    second = read_json(EVIDENCE / "decision.json")
    assert rerun["consistency_passed"] is True
    assert second == first
