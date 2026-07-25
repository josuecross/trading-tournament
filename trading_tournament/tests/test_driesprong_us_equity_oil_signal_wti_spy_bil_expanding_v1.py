from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def ensure_evidence() -> None:
    if not (EVIDENCE / "trial_manifest.json").exists():
        impl.run(ROOT)


def read_json(name: str) -> dict:
    ensure_evidence()
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    ensure_evidence()
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "true"


def synthetic_monthly(rows: int = 184) -> pd.DataFrame:
    periods = pd.period_range("2000-01", periods=rows, freq="M")
    spy = pd.Series(np.linspace(0.001, 0.02, rows), index=periods)
    wti = pd.Series(np.linspace(-0.02, 0.02, rows), index=periods)
    monthly = pd.DataFrame(index=periods)
    monthly["spy_log_return"] = spy
    monthly["wti_log_return"] = wti
    monthly["wti_log_return_lag1"] = wti.shift(1)
    monthly["tb3ms_monthly_log_threshold"] = 0.001
    monthly["data_complete_for_regression_observation"] = monthly[["spy_log_return", "wti_log_return_lag1"]].notna().all(axis=1)
    monthly["data_complete_for_signal"] = monthly[
        ["spy_log_return", "wti_log_return", "wti_log_return_lag1", "tb3ms_monthly_log_threshold"]
    ].notna().all(axis=1)
    return monthly


def test_exactly_180_observations_before_first_signal_and_expanding_not_rolling() -> None:
    regression = impl.expanding_regression_signals(synthetic_monthly(184))
    assert int(regression.iloc[0]["regression_observation_count"]) == impl.INITIAL_REGRESSION_OBSERVATIONS
    assert int(regression.iloc[1]["regression_observation_count"]) == impl.INITIAL_REGRESSION_OBSERVATIONS + 1
    assert regression.iloc[0]["estimation_first_month"] == "2000-02"
    assert regression.iloc[0]["estimation_last_month"] == "2015-01"
    assert regression.iloc[1]["estimation_first_month"] == "2000-02"
    assert regression.iloc[1]["estimation_last_month"] == "2015-02"


def test_oil_return_lag_and_next_month_forecast_timing() -> None:
    monthly = synthetic_monthly(181)
    regression = impl.expanding_regression_signals(monthly)
    first = regression.iloc[0]
    signal_month = pd.Period(first["signal_month"], freq="M")
    assert float(first["current_wti_log_return"]) == float(monthly.loc[signal_month, "wti_log_return"])
    assert first["forecast_month"] == str(signal_month + 1)
    fit = monthly[monthly["data_complete_for_regression_observation"]].iloc[: impl.INITIAL_REGRESSION_OBSERVATIONS]
    assert float(fit.iloc[-1]["wti_log_return_lag1"]) == float(monthly.loc[signal_month - 1, "wti_log_return"])


def test_tb3ms_threshold_uses_prior_month_lag_guard() -> None:
    frame = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            impl.RISK_FREE_SERIES: [1.2, 2.4, 3.6],
        }
    )
    thresholds = impl.tb3ms_monthly_thresholds(frame)
    assert pd.isna(thresholds.loc[pd.Period("2024-01", freq="M")])
    expected = np.log1p((1.2 / 100.0) / 12.0)
    assert abs(float(thresholds.loc[pd.Period("2024-02", freq="M")]) - expected) < 1e-15


def test_no_missing_observation_is_silently_filled_in_monthly_inputs() -> None:
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 101.0, 102.0],
            "BIL": [100.0, 100.1, 100.2],
        },
        index=pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-29"]),
    )
    wti = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(["2024-01-31", "2024-03-29"]),
            impl.PREDICTOR_SERIES: [70.0, 72.0],
        }
    )
    tb = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(["2023-12-01", "2024-01-01", "2024-02-01"]),
            impl.RISK_FREE_SERIES: [3.0, 3.1, 3.2],
        }
    )
    monthly, _, _ = impl.build_monthly_inputs(prices, wti, tb)
    assert "2024-02" not in set(monthly["month"])


def test_targets_are_binary_and_switching_costs_only_on_state_changes() -> None:
    signal_calendar = pd.DataFrame(
        {
            "signal_month": ["2024-01", "2024-02", "2024-03", "2024-04"],
            "spy_month_end_date": ["2024-01-31", "2024-02-29", "2024-03-29", "2024-04-30"],
            "execution_effective_date": ["2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"],
            "target_asset": ["BIL", "BIL", "SPY", "BIL"],
        }
    )
    rows = impl.transaction_rows(signal_calendar)
    assert len(rows) == 2
    assert rows[0]["from_asset"] == "BIL"
    assert rows[0]["to_asset"] == "SPY"
    returns = pd.Series(0.01, index=pd.to_datetime(["2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]))
    _, costs = impl.apply_switching_costs(returns, rows)
    assert float(costs.loc["2024-04-01"]) == impl.SWITCHING_COST_RATE
    assert float(costs.loc["2024-05-01"]) == impl.SWITCHING_COST_RATE
    assert float(costs.loc["2024-03-01"]) == 0.0


def test_identity_overlay_helper_equals_base_exactly() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"SPY": [1.0, 1.0, 0.0], "BIL": [0.0, 0.0, 1.0]}, index=index)
    returns = pd.Series([0.0, 0.01, -0.001], index=index)
    rows = impl.identity_overlay_equality_rows(weights, returns, [{"x": 1}], {"total_return": 0.01})
    assert all(row["exact_match"] is True for row in rows)


def test_manifest_and_guardrail_outputs_are_bounded_and_non_promotable() -> None:
    manifest = read_json("trial_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["strategy_id"] == impl.STRATEGY_ID
    assert manifest["family_id"] == impl.FAMILY_ID
    assert manifest["outcome"] in impl.ALLOWED_OUTCOMES
    assert manifest["initial_regression_observations"] == 180
    assert manifest["parameter_search_run"] is False
    assert manifest["alternative_predictors_tested"] is False
    assert manifest["alternative_equity_etfs_tested"] is False
    assert manifest["overlay_performance_experiment_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_eligibility"] is False
    assert manifest["paper_demo_eligibility"] is False
    assert manifest["paper_demo_activation"] is False
    assert manifest["broker_order_endpoint_called"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["registry_state_changed"] is False
    assert consistency["consistency_passed"] is True


def test_output_targets_invariants_and_identity_when_baseline_runs() -> None:
    manifest = read_json("trial_manifest.json")
    if manifest["outcome"] != "baseline_implemented_for_exploratory_review":
        return
    weights = pd.read_csv(EVIDENCE / "target_weights.csv")
    assert set(weights["held_asset"]) <= {"SPY", "BIL"}
    assert ((weights["SPY"] == 1.0) & (weights["BIL"] == 0.0) | (weights["SPY"] == 0.0) & (weights["BIL"] == 1.0)).all()
    invariants = read_csv("accounting_invariants.csv")
    assert all(bool_text(row["passed"]) for row in invariants)
    identity = read_csv("identity_overlay_equality.csv")
    assert all(bool_text(row["exact_match"]) for row in identity)
    calendar = read_csv("monthly_signal_calendar.csv")
    assert int(calendar[0]["regression_observation_count"]) == 180
    assert all(pd.Period(row["forecast_month"], freq="M") > pd.Period(row["estimation_last_month"], freq="M") for row in calendar)
    if set(weights["held_asset"]) == {"SPY"}:
        baseline = {row["series_id"]: row for row in read_csv("baseline_metrics.csv")}
        benchmarks = {row["benchmark_id"]: row for row in read_csv("benchmark_metrics.csv")}
        assert abs(float(baseline["source_aligned_10bps_baseline"]["total_return"]) - float(benchmarks["SPY_buy_and_hold"]["total_return"])) < 1e-12


def test_no_overlay_performance_output_and_compatibility_map_is_deterministic() -> None:
    ensure_evidence()
    assert not any("overlay_performance" in path.name for path in EVIDENCE.iterdir())
    assert impl.overlay_compatibility_rows() == impl.overlay_compatibility_rows()
    rows = {row["overlay"]: row["classification"] for row in read_csv("overlay_compatibility_map.csv")}
    assert rows["IdentityOverlay"] == "compatible_without_change"
    assert rows["ExposureCapsOverlay"] == "compatible_without_change"
    assert rows["LaggedVolatilityTargetOverlay"] == "not_economically_appropriate"


def test_required_files_exist_and_next_action_is_exact() -> None:
    ensure_evidence()
    manifest = read_json("trial_manifest.json")
    assert impl.REQUIRED_FILES <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert manifest["next_action"] == impl.NEXT_ACTION
