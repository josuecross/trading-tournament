from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import driesprong_oil_us_market_source_split_correction_v1 as impl


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


def synthetic_common(n: int = 9) -> pd.DataFrame:
    months = pd.period_range("2020-01", periods=n, freq="M")
    market = pd.Series(np.linspace(-0.02, 0.03, n), index=months)
    rf = pd.Series(0.001, index=months)
    wti = pd.Series(np.linspace(-0.10, 0.10, n), index=months)
    frame = pd.DataFrame(
        {
            "month": months,
            "Mkt-RF": (market - rf).to_numpy() * 100,
            "RF": rf.to_numpy() * 100,
            "market_simple_return": market.to_numpy(),
            "risk_free_simple_return": rf.to_numpy(),
            "market_log_return": np.log1p(market.to_numpy()),
            "risk_free_log_return": np.log1p(rf.to_numpy()),
            "wti_month_end_observation_date": pd.date_range("2020-01-31", periods=n, freq="ME"),
            "wti_month_end_price": np.linspace(50, 60, n),
            "wti_log_return": wti.to_numpy(),
        }
    )
    frame["wti_log_return_lag1"] = frame["wti_log_return"].shift(1)
    frame["regression_pair_valid"] = frame[["market_log_return", "risk_free_log_return", "wti_log_return_lag1"]].notna().all(axis=1)
    return frame


def test_split_is_chronological_deterministic_and_floor_half() -> None:
    common = synthetic_common(11)
    estimation, evaluation, n_pairs, estimation_count = impl.split_pairs(common)
    assert n_pairs == 10
    assert estimation_count == 5
    assert list(estimation["month"]) == list(common[common["regression_pair_valid"]]["month"].iloc[:5])
    assert list(evaluation["month"]) == list(common[common["regression_pair_valid"]]["month"].iloc[5:])
    assert impl.split_pairs(common)[2:] == (n_pairs, estimation_count)


def test_coefficients_are_estimated_once_and_evaluation_excluded() -> None:
    common = synthetic_common(12)
    estimation, evaluation, _, _ = impl.split_pairs(common)
    signals, coeffs = impl.evaluate_fixed_split(estimation, evaluation)
    assert coeffs["estimated_once"] is True
    assert coeffs["estimation_observations"] == len(estimation)
    assert coeffs["evaluation_observations"] == len(evaluation)
    assert coeffs["estimation_last_month"] < coeffs["evaluation_first_month"]
    assert set(signals["coefficients_source"]) == {"first_half_fixed_split_only"}


def test_oil_is_lagged_exactly_one_month() -> None:
    common = synthetic_common(12)
    estimation, evaluation, _, _ = impl.split_pairs(common)
    signals, _ = impl.evaluate_fixed_split(estimation, evaluation)
    first_month = pd.Period(signals.iloc[0]["evaluation_month"], freq="M")
    source = common.set_index("month")
    assert float(signals.iloc[0]["wti_log_return_lag1"]) == float(source.loc[first_month - 1, "wti_log_return"])


def test_market_return_formula_and_percentage_conversion() -> None:
    raw = pd.DataFrame({"Mkt-RF": [2.0], "RF": [0.5]})
    market_simple = (raw["Mkt-RF"] + raw["RF"]) / 100.0
    rf_simple = raw["RF"] / 100.0
    assert float(market_simple.iloc[0]) == 0.025
    assert float(rf_simple.iloc[0]) == 0.005
    assert abs(float(impl.log1p_checked(market_simple).iloc[0]) - np.log1p(0.025)) < 1e-15


def test_log_return_conversion_rejects_lte_minus_100_percent() -> None:
    with pytest.raises(ValueError):
        impl.log1p_checked(pd.Series([-1.0]))
    with pytest.raises(ValueError):
        impl.log1p_checked(pd.Series([-1.01]))


def test_every_target_is_market_or_risk_free_and_cost_once_per_change() -> None:
    common = synthetic_common(18)
    estimation, evaluation, n_pairs, estimation_count = impl.split_pairs(common)
    signals, _ = impl.evaluate_fixed_split(estimation, evaluation)
    assert set(signals["target_state"]) <= {"market", "risk_free"}
    transactions = impl.transaction_rows(signals)
    invariants = impl.invariant_rows(signals, transactions, n_pairs, estimation_count)
    assert all(row["passed"] is True for row in invariants)
    assert len(transactions) == int(signals["state_changed"].sum())


def test_no_expanding_or_rolling_or_alternative_configuration_in_manifest() -> None:
    manifest = read_json("trial_manifest.json")
    assert manifest["expanding_regression_used"] is False
    assert manifest["rolling_regression_used"] is False
    assert manifest["alternative_predictor_tested"] is False
    assert manifest["alternative_split_tested"] is False
    assert manifest["alternative_threshold_tested"] is False
    assert manifest["alternative_instrument_tested"] is False


def test_existing_expanding_variant_artifacts_remain_unchanged() -> None:
    manifest = read_json("trial_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["existing_variant_interpretation"] == "expanding_quantpedia_translation_control_equivalent_over_observed_window"
    assert manifest["existing_variant_artifacts_preserved"] is True
    assert consistency["existing_expanding_variant_artifacts_preserved"] is True


def test_no_overlay_broker_registry_promotion_or_paper_demo_state_change() -> None:
    manifest = read_json("trial_manifest.json")
    tm = read_json("trade_management_onboarding_state.json")
    assert manifest["overlay_performance_experiment_run"] is False
    assert tm["overlay_performance_experiment_run"] is False
    assert manifest["broker_write_called"] is False
    assert manifest["registry_promotion"] is False
    assert manifest["paper_demo_state_changed"] is False
    assert manifest["promotion_eligibility"] is False
    assert manifest["paper_demo_eligibility"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["state_hashes_before"] == manifest["state_hashes_after"]
    assert not any("overlay_performance" in path.name for path in EVIDENCE.iterdir())


def test_generated_evidence_is_complete_and_consistent() -> None:
    ensure_evidence()
    manifest = read_json("trial_manifest.json")
    consistency = read_json("consistency_check.json")
    assert impl.REQUIRED_FILES <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert manifest["outcome"] in impl.OUTCOMES
    assert consistency["consistency_passed"] is True
    if manifest["outcome"] == "source_split_diagnostic_complete":
        assert manifest["estimation_count"] == manifest["valid_regression_pair_count"] // 2
        assert manifest["coefficients_estimated_once"] is True
        assert manifest["evaluation_count"] > 0
        rows = read_csv("target_state_series.csv")
        assert {row["target_state"] for row in rows} <= {"market", "risk_free"}
    assert manifest["next_action"] == impl.NEXT_ACTION
