from __future__ import annotations

from pathlib import Path

import pandas as pd

import run_challenge_audit as challenge_audit
from run_challenge_audit import (
    CHALLENGE_COLUMNS,
    REQUIRED_FILES,
    build_assumptions,
    build_challenge_row,
    build_challenge_summary,
    build_etf_benchmark_rolling_rows,
    build_rankings,
    etf_benchmark_data,
    load_etf_rows,
    stop_audit_from_equity,
    write_outputs,
)


def base_audit(**overrides):
    audit = {
        "unconditional_final_equity": 3350.0,
        "stop_enforced_final_equity": 3350.0,
        "total_return_unconditional": 3350.0 / 3000.0 - 1,
        "total_return_stop_enforced": 3350.0 / 3000.0 - 1,
        "max_equity": 3350.0,
        "min_equity": 3000.0,
        "max_drawdown_dollars": -50.0,
        "max_drawdown_pct": -0.016,
        "absolute_floor_stop_hit": False,
        "trailing_drawdown_stop_hit": False,
        "any_project_stop_hit": False,
        "first_project_stop_date": "",
        "first_project_stop_type": "",
        "equity_at_first_project_stop": float("nan"),
        "target_300_hit": True,
        "target_300_before_stop": True,
        "target_300_first_date": "2024-01-10",
        "target_400_hit": False,
        "target_400_before_stop": False,
        "target_400_first_date": "",
        "days_to_target_300": 9,
        "days_to_target_400": float("nan"),
        "days_to_first_stop": float("nan"),
    }
    audit.update(overrides)
    return audit


def sample_challenge_and_rolling():
    run_id = "test_run"
    rows = [
        build_challenge_row(
            run_id,
            "etf_validated_lane",
            "steady_strategy",
            "daily_etf",
            "ETF evidence lane",
            "synthetic",
            "2024-01-01",
            "2024-03-01",
            "standard",
            0.0005,
            "none",
            1.0,
            0.0,
            base_audit(),
            stop_enforced_metric_quality="exact",
            stop_enforced_metric_source="synthetic_curve",
        ),
        build_challenge_row(
            run_id,
            "crypto_spot_momentum",
            "huge_after_stop",
            "crypto_spot",
            "Tier 1 exploratory screen",
            "synthetic",
            "2024-01-01",
            "2024-03-01",
            "standard",
            0.001,
            "none",
            1.0,
            0.0,
            base_audit(
                unconditional_final_equity=100000.0,
                stop_enforced_final_equity=2400.0,
                total_return_unconditional=100000.0 / 3000.0 - 1,
                total_return_stop_enforced=2400.0 / 3000.0 - 1,
                absolute_floor_stop_hit=True,
                any_project_stop_hit=True,
                target_300_before_stop=False,
                target_400_before_stop=False,
                max_drawdown_dollars=-2500.0,
                max_drawdown_pct=-0.7,
            ),
            stop_enforced_metric_quality="exact",
            stop_enforced_metric_source="synthetic_curve",
        ),
        build_challenge_row(
            run_id,
            "simulated_leverage_scenario",
            "levered_crypto",
            "crypto_spot",
            "Tier 1 exploratory screen; approximate simulated leverage",
            "synthetic",
            "2024-01-01",
            "2024-03-01",
            "standard",
            0.002,
            "approximate_simulated_leverage",
            2.0,
            0.08,
            base_audit(),
            stop_enforced_metric_quality="exact",
            stop_enforced_metric_source="synthetic_curve",
        ),
        build_challenge_row(
            run_id,
            "etf_validated_lane",
            "approx_candidate",
            "daily_etf",
            "ETF evidence lane",
            "synthetic",
            "2024-01-01",
            "2024-03-01",
            "standard",
            0.0005,
            "none",
            1.0,
            0.0,
            base_audit(),
            stop_enforced_metric_quality="approximate",
            stop_enforced_metric_source="summary_drawdown",
        ),
    ]
    challenge = pd.DataFrame(rows)
    rolling = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "lane": "etf_validated_lane",
                "strategy": "steady_strategy",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.4,
                "pct_target_300_before_stop": 0.4,
                "pct_target_400_hit": 0.2,
                "pct_target_400_before_stop": 0.2,
                "pct_any_project_stop_hit": 0.05,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.05,
                "median_final_equity": 3200,
                "median_stop_enforced_final_equity": 3200,
                "mean_stop_enforced_final_equity": 3210,
                "median_max_drawdown": -80,
                "worst_max_drawdown": -200,
                "pct_positive_return": 0.6,
                "pct_loss": 0.4,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.3,
                "pct_above_3400": 0.2,
                "rolling_metric_quality": "exact",
                "rolling_notes": "test",
            },
            {
                "run_id": run_id,
                "lane": "etf_validated_lane",
                "strategy": "approx_candidate",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.7,
                "pct_target_300_before_stop": 0.7,
                "pct_target_400_hit": 0.5,
                "pct_target_400_before_stop": 0.5,
                "pct_any_project_stop_hit": 0.0,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.0,
                "median_final_equity": 3300,
                "median_stop_enforced_final_equity": 3300,
                "mean_stop_enforced_final_equity": 3310,
                "median_max_drawdown": -80,
                "worst_max_drawdown": -200,
                "pct_positive_return": 0.8,
                "pct_loss": 0.2,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.7,
                "pct_above_3400": 0.5,
                "rolling_metric_quality": "sampled",
                "rolling_notes": "test",
            },
            {
                "run_id": run_id,
                "lane": "crypto_spot_momentum",
                "strategy": "huge_after_stop",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.9,
                "pct_target_300_before_stop": 0.1,
                "pct_target_400_hit": 0.8,
                "pct_target_400_before_stop": 0.05,
                "pct_any_project_stop_hit": 0.9,
                "pct_absolute_floor_stop_hit": 0.5,
                "pct_trailing_drawdown_stop_hit": 0.9,
                "median_final_equity": 10000,
                "median_stop_enforced_final_equity": 2400,
                "mean_stop_enforced_final_equity": 2500,
                "median_max_drawdown": -900,
                "worst_max_drawdown": -2500,
                "pct_positive_return": 0.2,
                "pct_loss": 0.8,
                "pct_below_2400": 0.5,
                "pct_above_3300": 0.1,
                "pct_above_3400": 0.05,
                "rolling_metric_quality": "exact",
                "rolling_notes": "test",
            },
            {
                "run_id": run_id,
                "lane": "simulated_leverage_scenario",
                "strategy": "levered_crypto",
                "leverage_multiplier": 2.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.5,
                "pct_target_300_before_stop": 0.3,
                "pct_target_400_hit": 0.4,
                "pct_target_400_before_stop": 0.2,
                "pct_any_project_stop_hit": 0.5,
                "pct_absolute_floor_stop_hit": 0.2,
                "pct_trailing_drawdown_stop_hit": 0.5,
                "median_final_equity": 3300,
                "median_stop_enforced_final_equity": 3000,
                "mean_stop_enforced_final_equity": 3050,
                "median_max_drawdown": -300,
                "worst_max_drawdown": -900,
                "pct_positive_return": 0.5,
                "pct_loss": 0.5,
                "pct_below_2400": 0.2,
                "pct_above_3300": 0.3,
                "pct_above_3400": 0.2,
                "rolling_metric_quality": "exact",
                "rolling_notes": "test",
            },
            {
                "run_id": run_id,
                "lane": "etf_benchmark",
                "strategy": "SPY_buy_hold",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.2,
                "pct_target_300_before_stop": 0.2,
                "pct_target_400_hit": 0.1,
                "pct_target_400_before_stop": 0.1,
                "pct_any_project_stop_hit": 0.1,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.1,
                "median_final_equity": 3050,
                "median_stop_enforced_final_equity": 3050,
                "mean_stop_enforced_final_equity": 3060,
                "median_max_drawdown": -120,
                "worst_max_drawdown": -400,
                "pct_positive_return": 0.5,
                "pct_loss": 0.5,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.2,
                "pct_above_3400": 0.1,
                "rolling_metric_quality": "exact",
                "rolling_notes": "benchmark test",
            },
            {
                "run_id": run_id,
                "lane": "etf_benchmark",
                "strategy": "SPY_200d_trend_model",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.3,
                "pct_target_300_before_stop": 0.3,
                "pct_target_400_hit": 0.15,
                "pct_target_400_before_stop": 0.15,
                "pct_any_project_stop_hit": 0.05,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.05,
                "median_final_equity": 3100,
                "median_stop_enforced_final_equity": 3100,
                "mean_stop_enforced_final_equity": 3110,
                "median_max_drawdown": -90,
                "worst_max_drawdown": -300,
                "pct_positive_return": 0.55,
                "pct_loss": 0.45,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.3,
                "pct_above_3400": 0.15,
                "rolling_metric_quality": "exact",
                "rolling_notes": "benchmark test",
            },
            {
                "run_id": run_id,
                "lane": "etf_benchmark",
                "strategy": "BIL_cash_proxy",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
                "pct_target_300_hit": 0.0,
                "pct_target_300_before_stop": 0.0,
                "pct_target_400_hit": 0.0,
                "pct_target_400_before_stop": 0.0,
                "pct_any_project_stop_hit": 0.0,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.0,
                "median_final_equity": 3000,
                "median_stop_enforced_final_equity": 3000,
                "mean_stop_enforced_final_equity": 3000,
                "median_max_drawdown": -5,
                "worst_max_drawdown": -20,
                "pct_positive_return": 0.0,
                "pct_loss": 0.0,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.0,
                "pct_above_3400": 0.0,
                "rolling_metric_quality": "exact",
                "rolling_notes": "benchmark test",
            },
        ]
    )
    rolling["final_validation_completed"] = rolling.get("final_validation_completed", False)
    rolling["stop_enforced_metric_quality"] = rolling.get("stop_enforced_metric_quality", rolling["rolling_metric_quality"])
    rolling["notes"] = rolling.get("notes", rolling["rolling_notes"])
    return challenge, rolling


def synthetic_etf_prices(periods: int = 260) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2023-01-02", periods=periods, freq="B")
    spy = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.12, index=dates)
    spy.iloc[80:110] *= 0.94
    bil = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.005, index=dates)
    prices = pd.DataFrame({"SPY": spy, "BIL": bil}, index=dates)
    data = (
        prices.reset_index(names="date")
        .melt(id_vars="date", var_name="symbol", value_name="adj_close")
        .sort_values(["symbol", "date"])
    )
    return data, prices


def test_stop_enforced_final_equity_equals_first_stop_equity() -> None:
    dates = pd.date_range("2024-01-01", periods=5)
    audit = stop_audit_from_equity(pd.Series([3000, 3500, 2900, 5000, 6000]), dates)
    assert audit.trailing_drawdown_stop_hit is True
    assert audit.first_project_stop_date == "2024-01-03"
    assert audit.stop_enforced_final_equity == 2900
    assert audit.unconditional_final_equity == 6000


def test_target_before_stop_logic() -> None:
    dates = pd.date_range("2024-01-01", periods=4)
    stop_first = stop_audit_from_equity(pd.Series([3000, 2400, 3500, 3600]), dates)
    assert stop_first.target_300_hit is True
    assert stop_first.target_300_before_stop is False
    target_first = stop_audit_from_equity(pd.Series([3000, 3350, 2700, 2600]), dates)
    assert target_first.target_300_before_stop is True


def test_challenge_results_contains_required_columns() -> None:
    challenge, _ = sample_challenge_and_rolling()
    assert set(CHALLENGE_COLUMNS).issubset(challenge.columns)


def test_leverage_scenarios_are_labeled_approximate() -> None:
    challenge, _ = sample_challenge_and_rolling()
    levered = challenge[challenge["leverage_multiplier"].eq(2.0)].iloc[0]
    assert levered["leverage_model"] == "approximate_simulated_leverage"
    assert "Tier 1" in levered["credibility_tier"]


def test_tier1_crypto_rows_cannot_be_marked_validated() -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    crypto = rankings[rankings["lane"].str.contains("crypto|leverage", regex=True)]
    assert not crypto.empty
    assert not crypto["audit_verdict"].isin(["practical_candidate"]).any()


def test_rankings_do_not_rank_by_unconditional_final_equity_alone() -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    assert rankings.iloc[0]["strategy"] != "huge_after_stop"


def test_challenge_folder_has_required_10_files_and_no_raw_ohlcv(tmp_path: Path) -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    coverage = pd.DataFrame(
        [
            {
                "lane": "synthetic",
                "data_source": "synthetic",
                "symbols": "SYN",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "row_count": 10,
                "missing_data_notes": "",
                "adjusted_or_unadjusted": "synthetic",
                "raw_data_included_in_evidence": False,
                "major_limitations": "test",
            }
        ]
    )
    write_outputs("test_run", challenge, rolling, rankings, coverage, {"research_only": True}, tmp_path / "challenge_runs")
    latest = tmp_path / "challenge_runs" / "latest"
    files = [p.name for p in latest.iterdir() if p.is_file()]
    assert len(files) == 10
    assert sorted(files) == sorted(REQUIRED_FILES)
    assert not any("ohlcv" in name.lower() or "raw" in name.lower() for name in files)
    assert (tmp_path / "challenge_runs" / "latest_challenge_packet.zip").exists()


def test_output_csvs_include_new_quality_and_benchmark_fields(tmp_path: Path) -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    write_outputs("test_run", challenge, rolling, rankings, pd.DataFrame(), {"research_only": True}, tmp_path / "challenge_runs")
    latest = tmp_path / "challenge_runs" / "latest"
    challenge_csv = pd.read_csv(latest / "challenge_results.csv")
    risk_csv = pd.read_csv(latest / "risk_and_stop_audit.csv")
    rank_csv = pd.read_csv(latest / "strategy_rankings.csv")
    rolling_csv = pd.read_csv(latest / "rolling_window_summary.csv")
    assert "stop_enforced_metric_quality" in challenge_csv.columns
    assert "stop_enforced_metric_quality" in risk_csv.columns
    assert "benchmark_comparison_available" in rank_csv.columns
    assert "ranking_penalty_notes" in rank_csv.columns
    assert "stop_overshoot_dollars" in challenge_csv.columns
    assert "stop_overshoot_dollars" in risk_csv.columns
    assert "diagnostic_score" in rank_csv.columns
    assert "pct_90d_stop_overshoot_gt_50" in rank_csv.columns
    assert "worst_stop_enforced_loss" in rolling_csv.columns
    assert "risk_framework_name" in challenge_csv.columns
    assert "risk_framework_verdict" in rank_csv.columns
    assert "paper_forward_allowed_by_risk_framework" in rank_csv.columns
    assert "risk_framework_name" in rolling_csv.columns
    assert "risk_framework_verdict" in risk_csv.columns
    benchmark_90 = rolling_csv[(rolling_csv["lane"] == "etf_benchmark") & (rolling_csv["horizon"] == 90)]
    assert {"SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"}.issubset(set(benchmark_90["strategy"]))
    assert "sampled_results_are_final" in benchmark_90.columns


def test_approximate_stop_enforced_rows_cannot_be_practical_candidate() -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    approx = rankings[rankings["strategy"] == "approx_candidate"].iloc[0]
    assert approx["stop_enforced_metric_quality"] == "approximate"
    assert approx["audit_verdict"] != "practical_candidate"


def test_warnings_include_no_real_money_statement(tmp_path: Path) -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    coverage = pd.DataFrame()
    write_outputs("test_run", challenge, rolling, rankings, coverage, {"research_only": True}, tmp_path / "challenge_runs")
    warnings = (tmp_path / "challenge_runs" / "latest" / "warnings_and_limitations.md").read_text()
    assert "no real-money recommendation" in warnings.lower()


def test_etf_lane_files_are_not_modified_by_writer(tmp_path: Path) -> None:
    challenge, rolling = sample_challenge_and_rolling()
    rankings = build_rankings(challenge, rolling)
    etf_file = tmp_path / "evidence" / "latest" / "strategy_variant_results.csv"
    etf_file.parent.mkdir(parents=True)
    etf_file.write_text("sentinel\n")
    write_outputs("test_run", challenge, rolling, rankings, pd.DataFrame(), {"research_only": True}, tmp_path / "challenge_runs")
    assert etf_file.read_text() == "sentinel\n"


def test_candidate_exhaustive_with_finalists_does_not_load_all_etf_variants(monkeypatch) -> None:
    finalist_row = build_challenge_row(
        "test_run",
        "etf_validated_lane",
        "current_no_cash_proxy_alpha_AB",
        "daily_etf",
        "ETF exact focused finalist",
        "synthetic",
        "2024-01-01",
        "2024-03-01",
        "standard",
        0.0005,
        "none",
        1.0,
        0.0,
        base_audit(),
        stop_enforced_metric_quality="exact",
    )

    def fake_full_rows(*args, **kwargs):
        return [finalist_row], [], True

    def fake_rolling_rows(*args, **kwargs):
        return [
            {
                "run_id": "test_run",
                "lane": "etf_validated_lane",
                "strategy": "current_no_cash_proxy_alpha_AB",
                "leverage_multiplier": 1.0,
                "standard_or_stress": "standard",
                "horizon": 90,
                "rolling_method": "all_possible",
                "number_of_windows": 100,
                "possible_window_count": 100,
                "sampled_results_are_final": True,
                "final_validation_completed": True,
                "pct_target_300_hit": 0.1,
                "pct_target_300_before_stop": 0.1,
                "pct_target_400_hit": 0.02,
                "pct_target_400_before_stop": 0.02,
                "pct_any_project_stop_hit": 0.0,
                "pct_absolute_floor_stop_hit": 0.0,
                "pct_trailing_drawdown_stop_hit": 0.0,
                "median_final_equity": 3020,
                "median_stop_enforced_final_equity": 3020,
                "mean_stop_enforced_final_equity": 3025,
                "median_max_drawdown": -100,
                "worst_max_drawdown": -300,
                "pct_positive_return": 0.5,
                "pct_loss": 0.5,
                "pct_below_2400": 0.0,
                "pct_above_3300": 0.1,
                "pct_above_3400": 0.02,
                "stop_enforced_metric_quality": "exact",
                "notes": "synthetic exact",
                "rolling_metric_quality": "exact",
                "rolling_notes": "synthetic exact",
            }
        ], True, "synthetic"

    monkeypatch.setattr(challenge_audit, "load_exact_etf_context", lambda: {"dates": pd.date_range("2024-01-01", periods=120)})
    monkeypatch.setattr(challenge_audit, "run_exact_variant_full_rows", fake_full_rows)
    monkeypatch.setattr(challenge_audit, "build_exact_finalist_rolling_rows", fake_rolling_rows)
    rows, _, _, completed = load_etf_rows(
        "test_run",
        include_etf=True,
        include_benchmarks=False,
        mode="candidate_exhaustive",
        finalists={"current_no_cash_proxy_alpha_AB"},
    )
    strategies = {row["strategy"] for row in rows}
    assert "current_no_cash_proxy_alpha_AB" in strategies
    assert "current_core_only_AB" not in strategies
    assert completed is True


def test_simulated_etf_leverage_rows_are_opt_in(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_leverage_diagnostic=False,
    )
    assert not any(row["lane"] == "simulated_leverage_diagnostic" for row in rows)
    assert not any(row.get("lane") == "simulated_leverage_diagnostic" for row in rolling)

    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_leverage_diagnostic=True,
    )
    diagnostic_rows = [row for row in rows if row["lane"] == "simulated_leverage_diagnostic"]
    diagnostic_rolling = [row for row in rolling if row.get("lane") == "simulated_leverage_diagnostic"]
    assert {row["strategy"] for row in diagnostic_rows} == {
        "SPY_200d_trend_model_sim_1_25x",
        "SPY_200d_trend_model_sim_1_5x",
        "SPY_buy_hold_sim_1_25x",
        "SPY_buy_hold_sim_1_5x",
    }
    assert diagnostic_rolling
    assert all(row["credibility_tier"] == "tier1_exploratory" for row in diagnostic_rows)
    assert all(row["financing_cost_assumption"] > 0 for row in diagnostic_rows)
    assert all(row["cost_model_quality"] == "approximate" for row in diagnostic_rows)
    assert all(row["audit_verdict"] != "practical_candidate" for row in diagnostic_rows)


def test_simulated_etf_leverage_changes_return_stream(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_leverage_diagnostic=True,
    )
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    standard = challenge[challenge["standard_or_stress"].eq("standard")]
    base = float(standard.loc[standard["strategy"].eq("SPY_200d_trend_model"), "unconditional_final_equity"].iloc[0])
    levered = float(standard.loc[standard["strategy"].eq("SPY_200d_trend_model_sim_1_25x"), "unconditional_final_equity"].iloc[0])
    assert levered != base
    assert not challenge["lane"].str.contains("crypto", case=False, na=False).any()

    rankings = build_rankings(challenge, rolling_df)
    diagnostics = rankings[rankings["lane"].eq("simulated_leverage_diagnostic")]
    assert not diagnostics.empty
    assert not diagnostics["audit_verdict"].eq("practical_candidate").any()
    assert diagnostics["ranking_penalty_notes"].str.contains("approximate", case=False).any()


def test_simulated_etf_leverage_assumptions_are_exported() -> None:
    assumptions = build_assumptions(
        "candidate_exhaustive",
        True,
        False,
        False,
        True,
        {"SPY_200d_trend_model"},
        True,
        "",
        include_etf_leverage_diagnostic=True,
    )
    etf_leverage = assumptions["simulated_etf_leverage"]
    assert etf_leverage["enabled"] is True
    assert etf_leverage["model"] == "approximate_return_multiplier"
    assert etf_leverage["financing_cost_annualized"]["1.25"] == 0.05
    assert etf_leverage["real_money_recommendation"] is False


def test_etf_exposure_frontier_rows_are_opt_in(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_exposure_frontier=False,
    )
    assert not any(row["lane"] == "simulated_etf_exposure_frontier" for row in rows)
    assert not any(row.get("lane") == "simulated_etf_exposure_frontier" for row in rolling)

    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_exposure_frontier=True,
    )
    frontier_rows = [row for row in rows if row["lane"] == "simulated_etf_exposure_frontier"]
    frontier_rolling = [row for row in rolling if row.get("lane") == "simulated_etf_exposure_frontier"]
    assert {row["strategy"] for row in frontier_rows} == {
        "SPY_200d_exposure_frontier_1_00x",
        "SPY_200d_exposure_frontier_1_05x",
        "SPY_200d_exposure_frontier_1_10x",
        "SPY_200d_exposure_frontier_1_15x",
        "SPY_200d_exposure_frontier_1_20x",
        "SPY_200d_exposure_frontier_1_25x",
    }
    assert frontier_rolling
    assert all(row["credibility_tier"] == "tier1_exploratory" for row in frontier_rows)
    assert all(row["role"] == "risk_budget_diagnostic" for row in frontier_rows)
    assert all(row["audit_verdict"] != "practical_candidate" for row in frontier_rows)
    assert {float(row["annual_financing_rate"]) for row in frontier_rows if row["exposure_multiplier"] > 1.0} == {0.04, 0.05, 0.06, 0.07, 0.08}


def test_etf_exposure_frontier_rankings_and_overshoot_fields(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_exposure_frontier=True,
    )
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    frontier_roll = rolling_df[rolling_df["lane"].eq("simulated_etf_exposure_frontier")]
    assert {"pct_windows_stop_overshoot_gt_50", "pct_windows_stop_overshoot_gt_100", "worst_stop_enforced_loss"}.issubset(frontier_roll.columns)
    assert not challenge["lane"].str.contains("crypto", case=False, na=False).any()

    rankings = build_rankings(challenge, rolling_df)
    frontier_rankings = rankings[rankings["lane"].eq("simulated_etf_exposure_frontier")]
    assert not frontier_rankings.empty
    assert not frontier_rankings["audit_verdict"].eq("practical_candidate").any()
    assert {"target_300_gain_vs_1x", "stop_hit_increase_vs_1x", "worst_drawdown_worsening_vs_1x", "diagnostic_score"}.issubset(frontier_rankings.columns)
    assert "risk_framework_verdict" in frontier_rankings.columns
    assert not frontier_rankings["paper_forward_allowed_by_risk_framework"].astype(bool).any()
    assert set(frontier_rankings["risk_framework_verdict"]).issubset({"diagnostic_only", "too_risky"})


def test_etf_exposure_frontier_assumptions_are_exported() -> None:
    assumptions = build_assumptions(
        "candidate_exhaustive",
        True,
        False,
        False,
        True,
        {"SPY_200d_trend_model"},
        True,
        "",
        include_etf_exposure_frontier=True,
    )
    frontier = assumptions["simulated_etf_exposure_frontier"]
    assert frontier["enabled"] is True
    assert frontier["model"] == "approximate_return_multiplier"
    assert frontier["exposure_multipliers"] == [1.0, 1.05, 1.1, 1.15, 1.2, 1.25]
    assert frontier["financing_cost_annualized"]["1.10"] == 0.05
    assert frontier["real_money_recommendation"] is False


def test_etf_volatility_control_rows_are_opt_in(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_volatility_control_diagnostic=False,
    )
    assert not any(row["lane"] == "etf_volatility_control_diagnostic" for row in rows)
    assert not any(row.get("lane") == "etf_volatility_control_diagnostic" for row in rolling)

    rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_volatility_control_diagnostic=True,
    )
    vol_rows = [row for row in rows if row["lane"] == "etf_volatility_control_diagnostic"]
    vol_rolling = [row for row in rolling if row.get("lane") == "etf_volatility_control_diagnostic"]
    assert {row["strategy"] for row in vol_rows} == {
        "SPY_200d_vol_target_12_cap_1_00_v1",
        "SPY_200d_vol_target_12_cap_1_10_v1",
    }
    assert vol_rolling
    assert all(row["credibility_tier"] == "tier1_exploratory" for row in vol_rows)
    assert all(row["role"] == "risk_control_diagnostic" for row in vol_rows)
    assert all(row["audit_verdict"] != "practical_candidate" for row in vol_rows)
    assert {float(row["target_vol_annualized"]) for row in vol_rows} == {0.12}
    assert {int(row["realized_vol_window"]) for row in vol_rows} == {60}
    assert all("average_exposure" in row for row in vol_rows)
    assert all("percent_time_cash" in row for row in vol_rolling)
    cap_110 = next(row for row in vol_rows if row["strategy"] == "SPY_200d_vol_target_12_cap_1_10_v1")
    assert cap_110["financing_cost_assumption"] == 0.05
    assert cap_110["cost_model_quality"] == "approximate"


def test_etf_volatility_control_rows_do_not_change_spy_200d(monkeypatch) -> None:
    data, prices = synthetic_etf_prices()
    monkeypatch.setattr(challenge_audit, "etf_benchmark_data", lambda date_index=None: (data, prices))
    base_rows, _, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_volatility_control_diagnostic=False,
    )
    diag_rows, rolling, _, _ = challenge_audit.build_etf_benchmark_rows(
        "test_run",
        "smoke",
        True,
        include_etf_volatility_control_diagnostic=True,
    )
    base_spy = [row for row in base_rows if row["strategy"] == "SPY_200d_trend_model" and row["standard_or_stress"] == "standard"][0]
    diag_spy = [row for row in diag_rows if row["strategy"] == "SPY_200d_trend_model" and row["standard_or_stress"] == "standard"][0]
    assert base_spy["unconditional_final_equity"] == diag_spy["unconditional_final_equity"]
    assert base_spy["stop_enforced_final_equity"] == diag_spy["stop_enforced_final_equity"]

    challenge = pd.DataFrame(diag_rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    rankings = build_rankings(challenge, rolling_df)
    vol_rankings = rankings[rankings["lane"].eq("etf_volatility_control_diagnostic")]
    assert not vol_rankings.empty
    assert not vol_rankings["audit_verdict"].eq("practical_candidate").any()
    assert not vol_rankings["paper_forward_allowed_by_risk_framework"].astype(bool).any()
    assert {"average_exposure", "target_300_change_vs_spy_200d", "worst_drawdown_change_vs_spy_200d"}.issubset(vol_rankings.columns)


def test_etf_volatility_control_assumptions_are_exported() -> None:
    assumptions = build_assumptions(
        "candidate_exhaustive",
        True,
        False,
        False,
        True,
        {"SPY_200d_trend_model"},
        True,
        "",
        include_etf_volatility_control_diagnostic=True,
    )
    vol = assumptions["etf_volatility_control_diagnostic"]
    assert vol["enabled"] is True
    assert vol["target_vol_annualized"] == 0.12
    assert vol["realized_vol_window_trading_days"] == 60
    assert vol["exposure_caps"] == [1.0, 1.1]
    assert vol["parameter_optimization"] is False
    assert vol["grid_search"] is False
    assert vol["paper_forward_allowed"] is False


def test_candidate_exhaustive_completion_flag_only_when_completed() -> None:
    incomplete = build_assumptions("candidate_exhaustive", True, False, False, True, {"x"}, False, "incomplete")
    complete = build_assumptions("candidate_exhaustive", True, False, False, True, {"x"}, True, "")
    assert incomplete["validation"]["final_validation_completed"] is False
    assert incomplete["validation"]["sampled_results_are_final"] is False
    assert complete["validation"]["final_validation_completed"] is True


def test_runtime_budget_exceeded_marks_benchmark_rolling_incomplete() -> None:
    _, prices = etf_benchmark_data()
    if prices.empty:
        return
    rows, completed = build_etf_benchmark_rolling_rows(
        "test_run",
        prices,
        "SPY_buy_hold",
        "candidate_exhaustive",
        ["standard"],
        runtime_deadline=0.0001,
    )
    assert completed is False
    assert rows


def test_challenge_summary_reports_finalist_comparison_and_incomplete_validation() -> None:
    challenge, rolling = sample_challenge_and_rolling()
    current = rolling[rolling["strategy"] == "approx_candidate"].copy()
    current["strategy"] = "current_no_cash_proxy_alpha_AB"
    rolling = pd.concat([rolling, current], ignore_index=True)
    summary = build_challenge_summary(
        "test_run",
        challenge,
        rolling,
        build_rankings(challenge, rolling),
        build_assumptions(
            "candidate_exhaustive",
            include_etf=True,
            include_crypto=False,
            include_leverage=False,
            include_benchmarks=True,
            finalists={"current_no_cash_proxy_alpha_AB"},
            final_validation_completed=False,
            incomplete_reason="test incomplete",
        ),
    )
    assert "Finalist validation is incomplete/non-final" in summary
    assert "Focus beats +300=" in summary
    assert "median-stop-equity=" in summary
    assert "worst-drawdown=" in summary
    assert "long-only crypto spot exploratory strategies" not in summary


def test_family_columns_are_in_compact_challenge_schema() -> None:
    assert {
        "family_id",
        "family_group",
        "family_role",
        "independent_family_account",
        "shared_capital_with_other_families",
        "portfolio_mix",
        "implementation_status",
        "run_allowed",
        "run_status",
        "blocked_reason",
    }.issubset(challenge_audit.CHALLENGE_COLUMNS)
    assert {
        "family_id",
        "family_group",
        "family_role",
        "independent_family_account",
        "rolling_status",
    }.issubset(challenge_audit.ROLLING_COLUMNS)
