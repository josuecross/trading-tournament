from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import run_paper_forward_observation as pfo
from run_paper_forward_observation import (
    ABSOLUTE_STOP,
    REQUIRED_FILES,
    TARGET_300,
    benchmark_comparison,
    benchmark_weights,
    build_assumptions,
    build_benchmark_outputs,
    risk_status,
    risk_framework_status,
    signal_for_spy_200d,
    stop_state,
    write_outputs,
)


@pytest.fixture(autouse=True)
def isolated_paper_forward_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_root = tmp_path / "paper_forward_runs"
    monkeypatch.setattr(pfo, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(pfo, "LATEST_ZIP", output_root / "latest_paper_forward_packet.zip")


def synthetic_prices(close_values: list[float], bil_values: list[float] | None = None) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=len(close_values))
    bil_values = bil_values or [100.0] * len(close_values)
    return pd.DataFrame({"SPY": close_values, "BIL": bil_values}, index=dates)


def synthetic_packet_frames():
    prices = synthetic_prices([100 + i * 0.2 for i in range(260)])
    obs = prices.iloc[-30:]
    run_id = "test_run"
    status_rows = []
    daily_rows = []
    signals = []
    for strategy, role in [
        ("SPY_200d_trend_model", "primary_watchlist_candidate"),
        ("SPY_buy_hold", "aggressive_benchmark"),
        ("BIL_cash_proxy", "defensive_benchmark"),
    ]:
        row, daily, snapshot, _turnover, _rebalances = build_benchmark_outputs(
            run_id,
            prices,
            obs,
            strategy,
            role,
            obs.index.min().date().isoformat(),
            obs.index.max().date().isoformat(),
            "ok",
        )
        status_rows.append(row)
        daily_rows.append(daily)
        signals.extend(snapshot)
    current = status_rows[0].copy()
    current["strategy"] = "current_no_cash_proxy_alpha_AB"
    current["role"] = "strategy_control"
    current["signal_state"] = "unavailable"
    status_rows.append(current)
    daily_current = daily_rows[0].copy()
    daily_current["strategy"] = "current_no_cash_proxy_alpha_AB"
    daily_current["role"] = "strategy_control"
    daily_rows.append(daily_current)
    signals.append(
        {
            "as_of_date": obs.index.max().date().isoformat(),
            "strategy": "current_no_cash_proxy_alpha_AB",
            "role": "strategy_control",
            "symbol": "",
            "close": float("nan"),
            "sma_200": float("nan"),
            "above_sma_200": "",
            "signal": "unavailable",
            "target_weight": float("nan"),
            "reason": "test unavailable",
            "data_quality_flag": "signal_snapshot_unavailable",
        }
    )
    status = pd.DataFrame(status_rows)
    daily = pd.concat(daily_rows, ignore_index=True)
    signal_frame = pd.DataFrame(signals)
    comparison = benchmark_comparison(status)
    risk = risk_status(status)
    assumptions = build_assumptions(
        obs.index.min().date().isoformat(),
        obs.index.max().date().isoformat(),
        "test cache",
        True,
    )
    return status, daily, signal_frame, comparison, assumptions, risk


def test_paper_forward_latest_folder_has_required_10_files(tmp_path: Path) -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    latest = pfo.OUTPUT_ROOT / "latest"
    files = [p.name for p in latest.iterdir() if p.is_file()]
    assert len(files) <= 10
    assert sorted(files) == sorted(REQUIRED_FILES)


def test_no_raw_ohlcv_is_copied_into_paper_forward_evidence() -> None:
    latest = pfo.OUTPUT_ROOT / "latest"
    if not latest.exists():
        status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
        write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    names = [p.name.lower() for p in latest.iterdir() if p.is_file()]
    assert not any("ohlcv" in name or "raw" in name or "cache" in name for name in names)


def test_paper_forward_status_has_all_required_strategies() -> None:
    status, *_ = synthetic_packet_frames()
    assert set(status["strategy"]) == {
        "SPY_200d_trend_model",
        "current_no_cash_proxy_alpha_AB",
        "SPY_buy_hold",
        "BIL_cash_proxy",
    }


def test_spy_200d_signal_risk_on_and_cash() -> None:
    risk_on_prices = synthetic_prices([100.0] * 200 + [120.0])
    signal, _close, _sma, above, _reason = signal_for_spy_200d(risk_on_prices, risk_on_prices.index[-1])
    assert above is True
    assert signal == "risk_on"
    cash_prices = synthetic_prices([100.0] * 200 + [80.0])
    signal, _close, _sma, above, _reason = signal_for_spy_200d(cash_prices, cash_prices.index[-1])
    assert above is False
    assert signal == "cash"


def test_target_before_stop_and_trailing_stop_logic() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    target_first = stop_state(pd.Series([3000, 3350, 3100, 3200]), dates)
    assert target_first.target_300_hit is True
    assert target_first.any_project_stop_hit is False
    stop_state_first = stop_state(pd.Series([3000, 3500, 2800, 3600]), dates)
    assert stop_state_first.trailing_drawdown_stop_hit is True
    assert stop_state_first.stop_enforced_current_equity == 2800


def test_risk_status_computes_distance_to_targets_and_stops() -> None:
    status, *_ = synthetic_packet_frames()
    risk = risk_status(status)
    assert {"target_300_distance", "distance_to_absolute_stop", "distance_to_trailing_stop"}.issubset(risk.columns)
    assert {"distance_to_target_300", "distance_to_target_400", "risk_reward_position"}.issubset(risk.columns)
    assert {"risk_framework_name", "risk_band", "risk_framework_status", "target_300_progress_pct"}.issubset(risk.columns)
    assert (risk["distance_to_absolute_stop"] > ABSOLUTE_STOP * -1).all()
    assert (risk["target_300_distance"] <= TARGET_300).all()


def test_risk_framework_warning_and_review_logic() -> None:
    warning = pd.Series(
        {
            "current_equity": 2700.0,
            "max_drawdown_dollars": -320.0,
            "any_project_stop_hit": False,
            "target_300_hit": False,
            "target_400_hit": False,
        }
    )
    review = warning.copy()
    review["max_drawdown_dollars"] = -470.0
    stopped = warning.copy()
    stopped["any_project_stop_hit"] = True
    assert risk_framework_status(warning) == "active_warning"
    assert risk_framework_status(review) == "active_review"
    assert risk_framework_status(stopped) == "stopped"


def test_benchmark_comparison_includes_historical_90d_rates() -> None:
    status, *_ = synthetic_packet_frames()
    comparison = benchmark_comparison(status)
    assert "historical_90d_pct_target_300_before_stop" in comparison.columns
    assert "risk_framework_name" in comparison.columns
    assert comparison["historical_90d_pct_target_300_before_stop"].notna().all()


def test_checkpoint_history_created_outside_latest_and_deduplicated() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    checkpoint_path = pfo.OUTPUT_ROOT / pfo.CHECKPOINT_HISTORY_NAME
    monthly_path = pfo.OUTPUT_ROOT / pfo.MONTHLY_DECISION_NAME
    assert checkpoint_path.exists()
    assert monthly_path.exists()
    assert (pfo.OUTPUT_ROOT / "latest" / pfo.CHECKPOINT_HISTORY_NAME).exists()
    assert (pfo.OUTPUT_ROOT / "latest" / pfo.MONTHLY_DECISION_NAME).exists()
    checkpoints = pd.read_csv(checkpoint_path)
    assert len(checkpoints[checkpoints["run_id"].eq("test_run")]) == 4
    assert not checkpoints.duplicated(subset=["run_id", "strategy"]).any()


def test_monthly_decision_row_exists_for_observation_month() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    monthly = pd.read_csv(pfo.OUTPUT_ROOT / pfo.MONTHLY_DECISION_NAME)
    expected_month = pd.Timestamp(status["observation_end_date"].iloc[0]).strftime("%Y-%m")
    assert expected_month in set(monthly["checkpoint_month"].astype(str))


def test_monthly_decision_inconclusive_when_elapsed_under_30_days() -> None:
    status, *_ = synthetic_packet_frames()
    status = pfo.enrich_status_for_decisions(status)
    decision = pfo.build_monthly_decision(status, benchmark_comparison(status), "test_run")
    assert decision.iloc[0]["decision"] == "inconclusive_too_early"


def test_monthly_decision_stopped_if_project_stop_hit() -> None:
    status, *_ = synthetic_packet_frames()
    status.loc[status["strategy"].eq("SPY_200d_trend_model"), ["any_project_stop_hit", "status"]] = [True, "stopped"]
    status = pfo.enrich_status_for_decisions(status)
    decision = pfo.build_monthly_decision(status, benchmark_comparison(status), "test_run")
    assert decision.iloc[0]["decision"] == "stopped"


def test_monthly_decision_target_reached_if_target_hit_before_stop() -> None:
    status, *_ = synthetic_packet_frames()
    primary = status["strategy"].eq("SPY_200d_trend_model")
    status.loc[primary, ["target_300_hit", "target_300_date", "current_equity", "current_return", "status"]] = [
        True,
        "2024-12-31",
        3310.0,
        3310.0 / 3000.0 - 1.0,
        "target_300_reached",
    ]
    status = pfo.enrich_status_for_decisions(status)
    decision = pfo.build_monthly_decision(status, benchmark_comparison(status), "test_run")
    assert decision.iloc[0]["decision"] == "target_reached"


def test_paper_forward_summary_includes_monthly_decision_checkpoint() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    text = (pfo.OUTPUT_ROOT / "latest" / "paper_forward_summary.md").read_text()
    assert "Monthly Decision Checkpoint" in text
    assert "Historical Expectation Comparison" in text


def test_status_csv_includes_historical_expectation_fields() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    written = pd.read_csv(pfo.OUTPUT_ROOT / "latest" / "paper_forward_status.csv")
    assert {
        "distance_to_target_300",
        "distance_to_target_400",
        "historical_90d_target_300_before_stop",
        "historical_90d_target_400_before_stop",
        "historical_90d_any_stop_hit",
        "current_vs_historical_status",
        "decision_status",
        "risk_framework_name",
        "risk_band",
        "risk_budget_used_pct",
        "target_300_progress_pct",
        "target_400_progress_pct",
    }.issubset(written.columns)


def test_risk_status_csv_includes_risk_budget_and_target_progress_fields() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    written = pd.read_csv(pfo.OUTPUT_ROOT / "latest" / "risk_status.csv")
    assert {
        "distance_to_target_300",
        "distance_to_target_400",
        "risk_budget_used_pct",
        "target_300_progress_pct",
        "target_400_progress_pct",
        "risk_reward_position",
    }.issubset(written.columns)


def test_warnings_include_no_real_money_statement() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    text = (pfo.OUTPUT_ROOT / "latest" / "warnings_and_limitations.md").read_text()
    assert "no real-money recommendation" in text.lower()


def test_paper_forward_manifest_records_no_live_or_real_money_behavior() -> None:
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    manifest = pd.read_json(pfo.OUTPUT_ROOT / "latest" / "paper_forward_manifest.json", typ="series")
    assert bool(manifest["data_downloaded"]) is False
    assert bool(manifest["backtest_run"]) is False
    assert bool(manifest["profit_exploration_run"]) is False
    assert bool(manifest["broker_integration"]) is False
    assert bool(manifest["live_orders"]) is False
    assert bool(manifest["real_money_recommendation"]) is False


def test_benchmark_weights_never_lever() -> None:
    prices = synthetic_prices([100 + i for i in range(260)])
    weights = benchmark_weights(prices, "SPY_200d_trend_model")
    assert (weights.sum(axis=1) <= 1.0 + 1e-12).all()


def test_strategy_module_files_not_modified_by_output_writer(tmp_path: Path) -> None:
    watched = Path("src/strategies.py")
    before = watched.read_bytes()
    status, daily, signals, comparison, assumptions, risk = synthetic_packet_frames()
    write_outputs("test_run", status, daily, signals, comparison, assumptions, risk)
    assert watched.read_bytes() == before
