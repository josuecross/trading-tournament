from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import max_diversification_cross_asset_etf_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "max_diversification_cross_asset_etf_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> dict[str, object]:
    return screen.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_exist() -> None:
    required = {
        "source_intake_record.yaml",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "duplicate_gate.csv",
        "material_distinction_review.csv",
        "cache_feasibility.csv",
        "optimizer_feasibility.csv",
        "synthetic_optimizer_tests.csv",
        "preregistration.yaml",
        "execution_manifest.json",
        "frozen_window_definitions.csv",
        "monthly_target_weights.csv",
        "daily_actual_weights.csv",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "diversification_ratio_diagnostics.csv",
        "accounting_and_optimizer_invariants.csv",
        "screening_summary.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_manifest_freezes_exact_universe_and_guardrails() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["candidate_id"] == screen.CANDIDATE_ID
    assert manifest["source_id"] == screen.SOURCE_ID
    assert manifest["family"] == screen.FAMILY_ID
    assert manifest["fixed_universe"] == list(screen.RISKY_ASSETS)
    assert manifest["bil_in_optimized_portfolio"] is False
    assert manifest["bil_benchmark_only"] is True
    assert manifest["covariance_window_trading_days"] == 250
    assert manifest["covariance_ddof"] == 1
    assert manifest["long_only"] is True
    assert manifest["fully_invested"] is True
    assert manifest["leverage"] is False
    assert manifest["shorting"] is False
    assert manifest["trend_filter"] is False
    assert manifest["cash_fallback"] is False
    assert manifest["provider_download"] is False
    assert manifest["broader_validation_or_robustness"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_authorized"] is False


def test_cache_feasibility_uses_existing_local_cache_only() -> None:
    rows = read_csv("cache_feasibility.csv")
    optimized = [row for row in rows if row["role"] == "optimized_universe"]
    assert [row["symbol"] for row in optimized] == list(screen.RISKY_ASSETS)
    assert all(row["cache_path"].startswith("data/cache/") for row in optimized)
    assert all(row["cache_ready"] == "true" for row in optimized)
    assert all((ROOT / row["cache_path"]).exists() for row in optimized)
    assert len({row["common_history_start"] for row in optimized}) == 1
    assert len({row["common_history_end"] for row in optimized}) == 1


def test_duplicate_and_material_distinction_gates_pass_without_reopening_closed_variants() -> None:
    duplicate = read_csv("duplicate_gate.csv")
    assert duplicate
    assert all(row["exact_duplicate"] == "false" for row in duplicate)
    assert any(row["prior_strategy"] == "rp_ivol_10m_trend_etf_wrapper_adaptation_v1" for row in duplicate)

    distinction = read_csv("material_distinction_review.csv")
    assert distinction
    assert all(row["materially_distinct"] == "true" for row in distinction)
    assert any(row["dimension"] == "optimizes_diversification_ratio" for row in distinction)
    assert any(row["dimension"] == "no_absolute_trend_filter" for row in distinction)


def test_diversification_ratio_formula_and_optimizer_constraints() -> None:
    corr = np.full((len(screen.RISKY_ASSETS), len(screen.RISKY_ASSETS)), 0.4)
    np.fill_diagonal(corr, 1.0)
    covariance = screen.covariance_from_vol_corr([0.1, 0.12, 0.14, 0.16, 0.18], corr)
    weights, diagnostics = screen.max_diversification_weights(covariance)

    sigma = np.sqrt(np.diag(covariance))
    expected = float(weights @ sigma) / float(np.sqrt(weights @ covariance @ weights))
    assert weights.sum() == pytest.approx(1.0)
    assert weights.min() >= -1e-10
    assert screen.diversification_ratio(weights, covariance) == pytest.approx(expected)
    assert diagnostics["constraints_satisfied"] is True
    assert diagnostics["repeat_max_abs_weight_difference"] <= 1e-8


def test_invalid_covariance_blocks_execution_without_repair() -> None:
    invalid = np.eye(len(screen.RISKY_ASSETS))
    invalid[0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        screen.max_diversification_weights(invalid)

    rows = read_csv("synthetic_optimizer_tests.csv")
    invalid_row = next(row for row in rows if row["case_id"] == "invalid_non_finite_covariance")
    assert invalid_row["expected_success"] == "false"
    assert invalid_row["actual_success"] == "false"
    assert invalid_row["test_passed"] == "true"


def test_optimizer_tests_include_zero_weight_case_and_no_hidden_caps() -> None:
    rows = read_csv("synthetic_optimizer_tests.csv")
    zero = next(row for row in rows if row["case_id"] == "valid_case_with_zero_weight_asset")
    assert zero["actual_success"] == "true"
    assert int(zero["zero_weight_count"]) >= 1

    prereg = (EVIDENCE / "preregistration.yaml").read_text(encoding="utf-8")
    assert "maximum_weight_cap_added: false" in prereg
    assert "regularization" in prereg
    assert "shrinkage" in prereg


def test_frozen_windows_are_exactly_the_preexisting_ten_windows() -> None:
    rows = read_csv("frozen_window_definitions.csv")
    assert len(rows) == 10
    assert [row["horizon_days"] for row in rows].count("90") == 5
    assert [row["horizon_days"] for row in rows].count("180") == 5
    assert all(row["performance_computed"] == "false" for row in rows)

    candidate_rows = [
        row for row in read_csv("window_level_results.csv")
        if row["strategy_id"] == screen.CANDIDATE_ID
    ]
    assert len(candidate_rows) == 10
    assert all(row["window_valid"] == "true" for row in candidate_rows)


def test_month_end_signal_next_session_execution_and_250_day_window() -> None:
    rows = read_csv("monthly_target_weights.csv")
    assert rows
    assert all(row["covariance_window_days"] == "250" for row in rows)
    assert all(pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["execution_date"]) for row in rows)
    assert all(float(row["weight_sum"]) == pytest.approx(1.0) for row in rows)
    assert all(float(row["min_weight"]) >= -1e-10 for row in rows)
    assert all(float(row["max_weight"]) <= 1.0 + 1e-10 for row in rows)


def test_actual_holdings_drift_and_turnover_uses_pre_trade_weights() -> None:
    rows = read_csv("daily_actual_weights.csv")
    assert rows
    assert max(abs(float(row["actual_weight_sum"]) - 1.0) for row in rows) <= 1e-8
    assert max(float(row["gross_exposure"]) for row in rows) <= 1.000001
    assert min(float(row[f"{symbol}_actual_weight"]) for row in rows for symbol in screen.RISKY_ASSETS) >= -1e-10
    assert any(
        abs(float(row[f"{symbol}_target_weight"]) - float(row[f"{symbol}_actual_weight"])) > 1e-6
        for row in rows
        for symbol in screen.RISKY_ASSETS
    )
    assert any(float(row["turnover"]) > 0.0 and abs(float(row["pre_trade_weight_sum"]) - 1.0) <= 1e-8 for row in rows)


def test_equal_weight_and_inverse_volatility_benchmarks_are_present_and_comparable() -> None:
    rows = read_csv("benchmark_metrics.csv")
    ids = {row["strategy_id"] for row in rows}
    assert "equal_weight_same_five_etf_monthly_rebalanced_benchmark" in ids
    assert "inverse_volatility_same_five_etf_monthly_benchmark" in ids
    assert "active_combo_vm_dsr_equal_weight_v1_reference_only" in ids
    assert "SPY_buy_and_hold" in ids
    assert "BIL_cash_proxy" in ids
    assert all(row["comparability_status"] == "comparable" for row in rows)
    assert all(int(row["valid_window_count"]) == 5 for row in rows)


def test_no_trend_or_bil_rule_in_candidate_and_outcome_is_non_promotional() -> None:
    daily = read_csv("daily_actual_weights.csv")
    assert all(not any(key.startswith("BIL_") for key in row) for row in daily[:10])

    outcome = read_json("screening_outcome.json")
    assert outcome["screening_outcome"] in screen.VALID_OUTCOMES
    assert outcome["screening_outcome"] == "risk_reduction_without_return_edge"
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["broader_validation_or_robustness_run"] is False


def test_registry_and_active_observations_remain_unchanged() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_byte_identical"] is True
    assert consistency["active_observations_unchanged"] is True
    assert consistency["no_provider_calls"] is True
    assert consistency["no_parameter_universe_solver_or_window_search"] is True
    assert consistency["no_promotion_or_paper_demo_activation"] is True
    assert consistency["consistency_passed"] is True


def test_generation_is_deterministic() -> None:
    first = {
        "outcome": (EVIDENCE / "screening_outcome.json").read_bytes(),
        "candidate": (EVIDENCE / "candidate_metrics.csv").read_bytes(),
        "relative": (EVIDENCE / "benchmark_relative_metrics.csv").read_bytes(),
    }
    rerun = screen.run()
    second = {
        "outcome": (EVIDENCE / "screening_outcome.json").read_bytes(),
        "candidate": (EVIDENCE / "candidate_metrics.csv").read_bytes(),
        "relative": (EVIDENCE / "benchmark_relative_metrics.csv").read_bytes(),
    }
    assert rerun["consistency_passed"] is True
    assert first == second
