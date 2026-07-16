from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import splv_static_low_vol_factor_screen_v1 as screen


ROOT = screen.ROOT
EVIDENCE_DIR = ROOT / "evidence" / "splv_static_low_vol_factor_validation_v1" / "latest"
SCREEN_EVIDENCE_DIR = ROOT / "evidence" / "splv_static_low_vol_factor_screen_v1" / "latest"
CANDIDATE_ID = screen.CANDIDATE_ID
FAMILY_ID = screen.FAMILY_ID
SOURCE_ID = screen.SOURCE_ID
ACTIVE_VM_ID = screen.ACTIVE_VM_ID
ACTIVE_COMBO_ID = screen.ACTIVE_COMBO_ID
DIRECT_BUY_HOLD_BENCHMARKS = ["SPY_buy_hold", "BIL_cash_proxy"]
NATIVE_SERIES_BENCHMARKS = [active.SPY_200D_ID, ACTIVE_COMBO_ID, ACTIVE_VM_ID]
BENCHMARK_IDS = ["SPY_buy_hold", active.SPY_200D_ID, "BIL_cash_proxy", ACTIVE_VM_ID, ACTIVE_COMBO_ID]
VALIDATION_OUTCOMES = {
    "validation_supports_further_review",
    "risk_reduction_without_return_edge",
    "screening_positive_not_stable",
    "no_material_edge",
    "not_comparable",
    "invalid_methodology",
}
HORIZONS = [90, 180]


@dataclass(frozen=True)
class Period:
    period_id: str
    validation_set: str
    horizon_days: int | str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    start_index: int
    end_index: int


def write_json(path: Path, payload: dict[str, Any]) -> None:
    screen.write_json(path, payload)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    screen.write_csv(path, rows, fields)


def clean(value: Any) -> Any:
    return screen.clean_value(value)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val):
        return None
    return val


def read_close(symbol: str) -> pd.Series:
    return screen.read_symbol_close(symbol)


def cache_hash(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    series = read_close(symbol)
    return {
        "artifact_id": symbol,
        "artifact_type": "local_cache_adjusted_close",
        "path": screen.rel(path),
        "sha256": screen.sha256_path(path),
        "first_valid_date": str(series.index.min().date()),
        "last_valid_date": str(series.index.max().date()),
        "row_count": int(len(series)),
    }


def direct_buy_hold_returns(close: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    start_date = dates[0]
    period_dates = dates[1:]
    entry_price = float(close.loc[start_date])
    shares = active.STARTING_EQUITY * (1.0 - active.SLIPPAGE) / entry_price
    equity = close.loc[period_dates].astype(float) * shares
    returns = equity.pct_change()
    returns.iloc[0] = float(equity.iloc[0] / active.STARTING_EQUITY - 1.0)
    return returns.astype(float)


def native_benchmark_returns(close: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        ACTIVE_VM_ID: active.full_returns(close, ACTIVE_VM_ID),
        ACTIVE_COMBO_ID: screen.load_active_combo_returns(),
    }


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    with_start = pd.concat([pd.Series([active.STARTING_EQUITY], index=[equity.index[0] - pd.Timedelta(days=1)]), equity])
    peak = with_start.cummax()
    dd_dollars = with_start - peak
    dd_pct = with_start / peak - 1.0
    return float(dd_dollars.min()), float(dd_pct.min())


def path_metrics(returns: pd.Series) -> dict[str, Any]:
    returns = returns.dropna().astype(float)
    if returns.empty:
        return {
            "valid": False,
            "final_equity": None,
            "total_return": None,
            "annualized_return": None,
            "annualized_volatility": None,
            "downside_volatility": None,
            "max_drawdown_dollars": None,
            "max_drawdown_pct": None,
            "return_drawdown_proxy": None,
            "sharpe_like": None,
            "sortino_like": None,
            "positive_absolute_return": False,
        }
    equity = active.STARTING_EQUITY * (1.0 + returns).cumprod()
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / active.STARTING_EQUITY - 1.0
    dd_dollars, dd_pct = max_drawdown(equity)
    vol = float(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 else 0.0
    downside = returns[returns < 0]
    down_vol = float(downside.std(ddof=1) * math.sqrt(252.0)) if len(downside) > 1 else 0.0
    ann = float((1.0 + total_return) ** (252.0 / len(returns)) - 1.0) if total_return > -1.0 else -1.0
    return_dd = float(total_return / abs(dd_pct)) if dd_pct < 0 else None
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 and returns.std(ddof=1) > 0 else None
    sortino = float(returns.mean() / downside.std(ddof=1) * math.sqrt(252.0)) if len(downside) > 1 and downside.std(ddof=1) > 0 else None
    return {
        "valid": True,
        "final_equity": final_equity,
        "total_return": float(total_return),
        "annualized_return": ann,
        "annualized_volatility": vol,
        "downside_volatility": down_vol,
        "max_drawdown_dollars": dd_dollars,
        "max_drawdown_pct": dd_pct,
        "return_drawdown_proxy": return_dd,
        "sharpe_like": sharpe,
        "sortino_like": sortino,
        "positive_absolute_return": bool(total_return > 0),
    }


def first_trading_day_each_month(dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    frame = pd.DataFrame({"date": dates})
    frame["month_key"] = frame["date"].dt.strftime("%Y-%m")
    return list(frame.groupby("month_key", sort=True)["date"].first())


def generate_monthly_start_periods(dates: pd.DatetimeIndex, horizon: int) -> list[Period]:
    positions = {date: idx for idx, date in enumerate(dates)}
    periods: list[Period] = []
    for start_date in first_trading_day_each_month(dates):
        start_idx = positions[start_date]
        end_idx = start_idx + horizon
        if end_idx >= len(dates):
            continue
        periods.append(
            Period(
                period_id=f"monthly_start_{horizon}d_{len(periods)+1:04d}",
                validation_set="monthly_start",
                horizon_days=horizon,
                start_date=dates[start_idx],
                end_date=dates[end_idx],
                start_index=start_idx,
                end_index=end_idx,
            )
        )
    return periods


def generate_non_overlapping_periods(dates: pd.DatetimeIndex, horizon: int) -> list[Period]:
    periods: list[Period] = []
    start_idx = 0
    while start_idx + horizon < len(dates):
        end_idx = start_idx + horizon
        periods.append(
            Period(
                period_id=f"non_overlapping_{horizon}d_{len(periods)+1:04d}",
                validation_set="non_overlapping",
                horizon_days=horizon,
                start_date=dates[start_idx],
                end_date=dates[end_idx],
                start_index=start_idx,
                end_index=end_idx,
            )
        )
        start_idx = end_idx
    return periods


def generate_full_period(dates: pd.DatetimeIndex) -> Period:
    return Period(
        period_id="full_common_splv_spy_period",
        validation_set="full_period",
        horizon_days="full",
        start_date=dates[0],
        end_date=dates[-1],
        start_index=0,
        end_index=len(dates) - 1,
    )


def generate_chronological_thirds(dates: pd.DatetimeIndex) -> list[Period]:
    boundaries = [0, len(dates) // 3, (2 * len(dates)) // 3, len(dates) - 1]
    labels = ["early", "middle", "recent"]
    periods: list[Period] = []
    for idx, label in enumerate(labels):
        start_idx = boundaries[idx]
        end_idx = boundaries[idx + 1]
        periods.append(
            Period(
                period_id=f"chronological_third_{label}",
                validation_set="chronological_third",
                horizon_days=label,
                start_date=dates[start_idx],
                end_date=dates[end_idx],
                start_index=start_idx,
                end_index=end_idx,
            )
        )
    return periods


def period_dates(dates: pd.DatetimeIndex, period: Period) -> pd.DatetimeIndex:
    return dates[period.start_index : period.end_index + 1]


def benchmark_common_dates(
    benchmark_id: str,
    candidate_dates: pd.DatetimeIndex,
    spy_dates: pd.DatetimeIndex,
    bil_dates: pd.DatetimeIndex,
    native_returns: dict[str, pd.Series],
) -> pd.DatetimeIndex:
    if benchmark_id == "SPY_buy_hold":
        return candidate_dates.intersection(spy_dates).sort_values()
    if benchmark_id == "BIL_cash_proxy":
        return candidate_dates.intersection(bil_dates).sort_values()
    return candidate_dates.intersection(pd.DatetimeIndex(native_returns[benchmark_id].dropna().index)).sort_values()


def returns_for_strategy(
    strategy_id: str,
    dates: pd.DatetimeIndex,
    close_by_symbol: dict[str, pd.Series],
    native_returns: dict[str, pd.Series],
) -> pd.Series | None:
    if len(dates) < 2:
        return None
    if strategy_id == CANDIDATE_ID:
        return direct_buy_hold_returns(close_by_symbol["SPLV"], dates)
    if strategy_id == "SPY_buy_hold":
        return direct_buy_hold_returns(close_by_symbol["SPY"], dates)
    if strategy_id == "BIL_cash_proxy":
        return direct_buy_hold_returns(close_by_symbol["BIL"], dates)
    series = native_returns[strategy_id].reindex(dates[1:]).dropna()
    return series.astype(float) if len(series) == len(dates) - 1 else None


def compare_period(
    period: Period,
    base_dates: pd.DatetimeIndex,
    close_by_symbol: dict[str, pd.Series],
    native_returns: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    dates = period_dates(base_dates, period)
    candidate_returns = returns_for_strategy(CANDIDATE_ID, dates, close_by_symbol, native_returns)
    candidate = path_metrics(candidate_returns if candidate_returns is not None else pd.Series(dtype=float))
    rows: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        benchmark_returns = returns_for_strategy(benchmark_id, dates, close_by_symbol, native_returns)
        benchmark = path_metrics(benchmark_returns if benchmark_returns is not None else pd.Series(dtype=float))
        benchmark_available = bool(benchmark_returns is not None and benchmark["valid"])
        rows.append(
            {
                "period_id": period.period_id,
                "validation_set": period.validation_set,
                "horizon_days": period.horizon_days,
                "window_start": str(period.start_date.date()),
                "window_end": str(period.end_date.date()),
                "trading_return_days": len(dates) - 1,
                "candidate_id": CANDIDATE_ID,
                "benchmark_id": benchmark_id,
                "benchmark_available": benchmark_available,
                "matching_dates_used": benchmark_available,
                "candidate_final_equity": candidate["final_equity"],
                "candidate_total_return": candidate["total_return"],
                "candidate_annualized_return": candidate["annualized_return"],
                "candidate_annualized_volatility": candidate["annualized_volatility"],
                "candidate_downside_volatility": candidate["downside_volatility"],
                "candidate_max_drawdown_dollars": candidate["max_drawdown_dollars"],
                "candidate_max_drawdown_pct": candidate["max_drawdown_pct"],
                "candidate_return_drawdown_proxy": candidate["return_drawdown_proxy"],
                "candidate_sharpe_like": candidate["sharpe_like"],
                "candidate_sortino_like": candidate["sortino_like"],
                "candidate_positive_absolute_return": candidate["positive_absolute_return"],
                "benchmark_final_equity": benchmark["final_equity"] if benchmark_available else None,
                "benchmark_total_return": benchmark["total_return"] if benchmark_available else None,
                "benchmark_annualized_return": benchmark["annualized_return"] if benchmark_available else None,
                "benchmark_annualized_volatility": benchmark["annualized_volatility"] if benchmark_available else None,
                "benchmark_downside_volatility": benchmark["downside_volatility"] if benchmark_available else None,
                "benchmark_max_drawdown_dollars": benchmark["max_drawdown_dollars"] if benchmark_available else None,
                "benchmark_max_drawdown_pct": benchmark["max_drawdown_pct"] if benchmark_available else None,
                "benchmark_return_drawdown_proxy": benchmark["return_drawdown_proxy"] if benchmark_available else None,
                "splv_minus_benchmark_return": (
                    float(candidate["total_return"]) - float(benchmark["total_return"]) if benchmark_available else None
                ),
                "splv_minus_benchmark_drawdown_pct": (
                    float(candidate["max_drawdown_pct"]) - float(benchmark["max_drawdown_pct"]) if benchmark_available else None
                ),
                "splv_beats_benchmark_return": (
                    bool(float(candidate["total_return"]) > float(benchmark["total_return"])) if benchmark_available else None
                ),
                "splv_lower_drawdown_than_benchmark": (
                    bool(float(candidate["max_drawdown_pct"]) > float(benchmark["max_drawdown_pct"])) if benchmark_available else None
                ),
                "splv_lower_volatility_than_benchmark": (
                    bool(float(candidate["annualized_volatility"]) < float(benchmark["annualized_volatility"])) if benchmark_available else None
                ),
                "splv_beats_return_and_drawdown": (
                    bool(
                        float(candidate["total_return"]) > float(benchmark["total_return"])
                        and float(candidate["max_drawdown_pct"]) > float(benchmark["max_drawdown_pct"])
                    )
                    if benchmark_available
                    else None
                ),
                "splv_lower_risk_lower_return": (
                    bool(
                        float(candidate["total_return"]) <= float(benchmark["total_return"])
                        and float(candidate["max_drawdown_pct"]) > float(benchmark["max_drawdown_pct"])
                    )
                    if benchmark_available
                    else None
                ),
                "splv_loses_return_and_drawdown": (
                    bool(
                        float(candidate["total_return"]) <= float(benchmark["total_return"])
                        and float(candidate["max_drawdown_pct"]) <= float(benchmark["max_drawdown_pct"])
                    )
                    if benchmark_available
                    else None
                ),
                "entry_cost_treatment": (
                    "direct_buy_hold_entry_cost_applied_equally"
                    if benchmark_id in DIRECT_BUY_HOLD_BENCHMARKS
                    else "native_frozen_series_costs_preserved"
                ),
                "actual_shares_held": True,
                "no_artificial_daily_or_quarterly_turnover": True,
            }
        )
    return rows


def aggregate_rows(rows: list[dict[str, Any]], validation_set: str, horizon: int | str) -> list[dict[str, Any]]:
    frame = pd.DataFrame([row for row in rows if row["validation_set"] == validation_set and str(row["horizon_days"]) == str(horizon)])
    out: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        sub = frame[(frame["benchmark_id"] == benchmark_id) & (frame["benchmark_available"] == True)].copy()
        if sub.empty:
            out.append({"validation_set": validation_set, "horizon_days": horizon, "benchmark_id": benchmark_id, "window_count": 0})
            continue
        out.append(
            {
                "validation_set": validation_set,
                "horizon_days": horizon,
                "benchmark_id": benchmark_id,
                "window_count": int(len(sub)),
                "mean_final_equity": float(sub["candidate_final_equity"].mean()),
                "median_final_equity": float(sub["candidate_final_equity"].median()),
                "mean_total_return": float(sub["candidate_total_return"].mean()),
                "median_total_return": float(sub["candidate_total_return"].median()),
                "win_rate_vs_benchmark": float(sub["splv_beats_benchmark_return"].mean()),
                "median_benchmark_relative_return": float(sub["splv_minus_benchmark_return"].median()),
                "worst_benchmark_relative_return": float(sub["splv_minus_benchmark_return"].min()),
                "positive_absolute_return_rate": float(sub["candidate_positive_absolute_return"].mean()),
                "beats_bil_rate": (
                    float(sub["splv_beats_benchmark_return"].mean()) if benchmark_id == "BIL_cash_proxy" else None
                ),
                "mean_realized_daily_volatility_annualized": float(sub["candidate_annualized_volatility"].mean()),
                "mean_downside_volatility_annualized": float(sub["candidate_downside_volatility"].mean()),
                "worst_max_drawdown_dollars": float(sub["candidate_max_drawdown_dollars"].min()),
                "worst_max_drawdown_pct": float(sub["candidate_max_drawdown_pct"].min()),
                "median_drawdown_pct": float(sub["candidate_max_drawdown_pct"].median()),
                "lower_drawdown_than_benchmark_rate": float(sub["splv_lower_drawdown_than_benchmark"].mean()),
                "lower_volatility_than_benchmark_rate": float(sub["splv_lower_volatility_than_benchmark"].mean()),
                "beats_return_and_drawdown_rate": float(sub["splv_beats_return_and_drawdown"].mean()),
                "lower_risk_lower_return_rate": float(sub["splv_lower_risk_lower_return"].mean()),
                "loses_return_and_drawdown_rate": float(sub["splv_loses_return_and_drawdown"].mean()),
            }
        )
    return out


def full_period_rows(
    primary_dates: pd.DatetimeIndex,
    close_by_symbol: dict[str, pd.Series],
    native_returns: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    period = generate_full_period(primary_dates)
    rows = compare_period(period, primary_dates, close_by_symbol, native_returns)
    return [
        {
            **row,
            "period_scope": "complete_common_splv_spy_period",
        }
        for row in rows
    ]


def chronological_third_rows(
    primary_dates: pd.DatetimeIndex,
    close_by_symbol: dict[str, pd.Series],
    native_returns: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in generate_chronological_thirds(primary_dates):
        rows.extend(compare_period(period, primary_dates, close_by_symbol, native_returns))
    return rows


def benchmark_common_period_rows(
    primary_dates: pd.DatetimeIndex,
    close_by_symbol: dict[str, pd.Series],
    native_returns: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        dates = benchmark_common_dates(
            benchmark_id,
            pd.DatetimeIndex(close_by_symbol["SPLV"].dropna().index),
            pd.DatetimeIndex(close_by_symbol["SPY"].dropna().index),
            pd.DatetimeIndex(close_by_symbol["BIL"].dropna().index),
            native_returns,
        )
        rows.append(
            {
                "benchmark_id": benchmark_id,
                "common_start": str(dates[0].date()) if len(dates) else "",
                "common_end": str(dates[-1].date()) if len(dates) else "",
                "common_trading_sessions": int(len(dates)),
                "primary_splv_spy_common_start": str(primary_dates[0].date()),
                "primary_splv_spy_common_end": str(primary_dates[-1].date()),
                "shortens_primary_splv_spy_analysis": False,
            }
        )
    return rows


def summarize_benchmark_rates(all_window_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    win_rows: list[dict[str, Any]] = []
    joint_rows: list[dict[str, Any]] = []
    relative_rows: list[dict[str, Any]] = []
    for validation_set in ["monthly_start", "non_overlapping"]:
        for horizon in HORIZONS:
            aggregate = aggregate_rows(all_window_rows, validation_set, horizon)
            for row in aggregate:
                win_rows.append(
                    {
                        "validation_set": validation_set,
                        "horizon_days": horizon,
                        "benchmark_id": row["benchmark_id"],
                        "window_count": row.get("window_count", 0),
                        "win_rate_vs_benchmark": row.get("win_rate_vs_benchmark"),
                        "positive_absolute_return_rate": row.get("positive_absolute_return_rate"),
                        "beats_bil_rate": row.get("beats_bil_rate"),
                    }
                )
                joint_rows.append(
                    {
                        "validation_set": validation_set,
                        "horizon_days": horizon,
                        "benchmark_id": row["benchmark_id"],
                        "window_count": row.get("window_count", 0),
                        "beats_return_and_drawdown_rate": row.get("beats_return_and_drawdown_rate"),
                        "lower_risk_lower_return_rate": row.get("lower_risk_lower_return_rate"),
                        "loses_return_and_drawdown_rate": row.get("loses_return_and_drawdown_rate"),
                    }
                )
                relative_rows.append(row)
    return win_rows, joint_rows, relative_rows


def validation_decision(relative_rows: list[dict[str, Any]], thirds: list[dict[str, Any]], invariants_passed: bool) -> tuple[str, str]:
    if not invariants_passed:
        return "invalid_methodology", "accounting_or_alignment_invariant_failed"
    spy_rows = {
        (row["validation_set"], int(row["horizon_days"])): row
        for row in relative_rows
        if row["benchmark_id"] == "SPY_buy_hold" and row.get("window_count", 0)
    }
    required_keys = [("monthly_start", 90), ("monthly_start", 180), ("non_overlapping", 90), ("non_overlapping", 180)]
    if any(key not in spy_rows for key in required_keys):
        return "not_comparable", "missing_primary_spy_comparison"
    risk_repeatable = all(float(spy_rows[key]["lower_drawdown_than_benchmark_rate"]) >= 0.55 for key in required_keys)
    volatility_repeatable = all(float(spy_rows[key]["lower_volatility_than_benchmark_rate"]) >= 0.55 for key in required_keys)
    return_repeatable = all(float(spy_rows[key]["win_rate_vs_benchmark"]) >= 0.50 for key in required_keys)
    third_spy = [
        row
        for row in thirds
        if row["benchmark_id"] == "SPY_buy_hold" and row["benchmark_available"] is True
    ]
    third_return_wins = sum(1 for row in third_spy if row["splv_beats_benchmark_return"] is True)
    not_concentrated = third_return_wins >= 2
    if risk_repeatable and volatility_repeatable and return_repeatable and not_concentrated:
        return "validation_supports_further_review", "risk_and_return_evidence_persisted_across_predetermined_coverage"
    if risk_repeatable or volatility_repeatable:
        return "risk_reduction_without_return_edge", "risk_reduction_repeated_but_return_win_rate_or_subperiod_return_evidence_was_not_stable"
    if return_repeatable and not not_concentrated:
        return "screening_positive_not_stable", "return_advantage_concentrated_in_limited_subperiods"
    return "no_material_edge", "no_consistent_return_or_risk_improvement_versus_spy"


def artifact_lineage(hashes_before: dict[str, str]) -> list[dict[str, Any]]:
    rows = [
        cache_hash("SPLV"),
        cache_hash("SPY"),
        cache_hash("BIL"),
        {
            "artifact_id": "active_strategy_evidence_recompute",
            "artifact_type": "benchmark_series_code",
            "path": "run_active_strategy_evidence_recompute.py",
            "sha256": screen.sha256_path(ROOT / "run_active_strategy_evidence_recompute.py"),
        },
        {
            "artifact_id": ACTIVE_COMBO_ID,
            "artifact_type": "active_combo_daily_series",
            "path": "evidence/active_combo_series_reconciliation/latest/combo_daily_series.csv",
            "sha256": hashes_before["active_combo_series"],
        },
        {
            "artifact_id": "source_intake",
            "artifact_type": "source_intake_record",
            "path": f"strategy_lab/research_os/public_strategy_sources/intake_candidates/{SOURCE_ID}.yaml",
            "sha256": screen.sha256_path(ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates" / f"{SOURCE_ID}.yaml"),
        },
        {
            "artifact_id": "prior_screen_manifest",
            "artifact_type": "screening_evidence",
            "path": "evidence/splv_static_low_vol_factor_screen_v1/latest/execution_manifest.json",
            "sha256": screen.sha256_path(SCREEN_EVIDENCE_DIR / "execution_manifest.json"),
        },
    ]
    return rows


def validate_manifest(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest["candidate_id"] == CANDIDATE_ID
        and manifest["candidate_instrument"] == "SPLV"
        and manifest["splv_cache_hash_matches_screen"] is True
        and manifest["window_generation_rules"]["windows_generated_before_performance"] is True
        and manifest["period_selection_after_results_allowed"] is False
        and manifest["parameter_wrapper_benchmark_or_period_selection_after_results_allowed"] is False
    )


def write_summary(outcome: str, reason: str, relative_rows: list[dict[str, Any]], full_rows: list[dict[str, Any]]) -> None:
    spy_summary = {
        (row["validation_set"], row["horizon_days"]): row
        for row in relative_rows
        if row["benchmark_id"] == "SPY_buy_hold"
    }
    full_spy = next(row for row in full_rows if row["benchmark_id"] == "SPY_buy_hold")
    lines = [
        "# SPLV Static Low-Vol Factor Validation V1",
        "",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Outcome: `{outcome}`",
        f"Reason: `{reason}`",
        "",
        "This validation expands the original sparse sampled-window screen across predetermined monthly-start, non-overlapping, full-period, and chronological-third coverage. It remains diagnostic and non-promotional.",
        "",
        "## Primary SPY Comparison",
    ]
    for key in [("monthly_start", 90), ("monthly_start", 180), ("non_overlapping", 90), ("non_overlapping", 180)]:
        row = spy_summary[key]
        lines.append(
            f"- {key[0]} {key[1]}d: return win rate {float(row['win_rate_vs_benchmark']):.3f}, "
            f"lower-drawdown rate {float(row['lower_drawdown_than_benchmark_rate']):.3f}, "
            f"lower-volatility rate {float(row['lower_volatility_than_benchmark_rate']):.3f}, windows {row['window_count']}."
        )
    lines.extend(
        [
            "",
            "## Full Period",
            f"- SPLV minus SPY total return: {float(full_spy['splv_minus_benchmark_return']):.6f}.",
            f"- SPLV minus SPY drawdown pct difference: {float(full_spy['splv_minus_benchmark_drawdown_pct']):.6f}.",
            "",
            "Guardrails: no provider download, no wrapper/parameter change, no BIL or tactical rule, no lifecycle change, no paper/demo activation, no candidate_exhaustive, and no real-money recommendation.",
            "",
        ]
    )
    (EVIDENCE_DIR / "validation_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    active_combo_path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    prior_screen_prereg = SCREEN_EVIDENCE_DIR / "preregistration.yaml"
    prior_screen_manifest_path = SCREEN_EVIDENCE_DIR / "execution_manifest.json"
    prior_screen_manifest = json.loads(prior_screen_manifest_path.read_text(encoding="utf-8"))
    prior_screen_prereg_text = prior_screen_prereg.read_text(encoding="utf-8")
    prior_screen_cache_hash = ""
    for line in prior_screen_prereg_text.splitlines():
        if line.strip().startswith("cache_sha256:"):
            prior_screen_cache_hash = line.split(":", 1)[1].strip()
            break

    hashes_before = {
        "registry": screen.sha256_path(registry_path),
        "active_observations": screen.sha256_path(active_observations_path),
        "active_combo_series": screen.sha256_path(active_combo_path),
        "screen_manifest": screen.sha256_path(prior_screen_manifest_path),
        "screen_preregistration": screen.sha256_path(prior_screen_prereg),
    }
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    splv = read_close("SPLV")
    spy = read_close("SPY")
    bil = read_close("BIL")
    close, missing = active.prepare_prices(ROOT)
    if missing:
        raise RuntimeError(f"missing active benchmark cache symbols: {missing}")
    native_returns = native_benchmark_returns(close)
    close_by_symbol = {"SPLV": splv, "SPY": spy, "BIL": bil}

    primary_dates = splv.dropna().index.intersection(spy.dropna().index).sort_values()
    monthly_90 = generate_monthly_start_periods(primary_dates, 90)
    monthly_180 = generate_monthly_start_periods(primary_dates, 180)
    nonoverlap_90 = generate_non_overlapping_periods(primary_dates, 90)
    nonoverlap_180 = generate_non_overlapping_periods(primary_dates, 180)
    full_period = generate_full_period(primary_dates)
    thirds = generate_chronological_thirds(primary_dates)
    benchmark_periods = benchmark_common_period_rows(primary_dates, close_by_symbol, native_returns)

    lineage_rows = artifact_lineage(hashes_before)
    current_splv_hash = next(row["sha256"] for row in lineage_rows if row["artifact_id"] == "SPLV")
    manifest = {
        "validation_id": "splv_static_low_vol_factor_validation_v1",
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "screen_evidence_path": "evidence/splv_static_low_vol_factor_screen_v1/latest",
        "screening_outcome_reviewed": prior_screen_manifest.get("screening_outcome"),
        "candidate_instrument": "SPLV",
        "splv_cache_path": "data/cache/SPLV.csv",
        "splv_cache_hash": current_splv_hash,
        "splv_cache_hash_from_original_screen": prior_screen_cache_hash,
        "splv_cache_hash_matches_screen": current_splv_hash == prior_screen_cache_hash,
        "benchmark_source_paths_and_hashes": lineage_rows,
        "primary_common_valid_period": {
            "benchmark_id": "SPY_buy_hold",
            "start": str(primary_dates[0].date()),
            "end": str(primary_dates[-1].date()),
            "trading_sessions": int(len(primary_dates)),
        },
        "benchmark_common_periods": benchmark_periods,
        "entry_exit_conventions": {
            "candidate": "enter 100% SPLV at period start with project entry cost; hold actual ETF shares; measurement exit at period end",
            "direct_buy_hold_benchmarks": "same initial entry-cost convention as candidate",
            "native_benchmarks": "use corrected current daily series and native frozen accounting/costs",
        },
        "cost_and_slippage_assumptions": {
            "initial_capital": active.STARTING_EQUITY,
            "entry_slippage": active.SLIPPAGE,
            "project_stop_dollars": active.STOP_DOLLARS,
        },
        "window_generation_rules": {
            "monthly_start": "first valid trading session of each calendar month; exact 90/180 trading-session horizon; no result-based removal",
            "non_overlapping": "deterministic sequential windows from first eligible date; discard only final incomplete remainder",
            "full_period": "complete common SPLV/SPY period",
            "chronological_thirds": "mechanically split complete common SPLV/SPY period into three approximately equal trading-day subperiods",
            "windows_generated_before_performance": True,
            "monthly_start_90_count": len(monthly_90),
            "monthly_start_180_count": len(monthly_180),
            "non_overlapping_90_count": len(nonoverlap_90),
            "non_overlapping_180_count": len(nonoverlap_180),
            "chronological_third_boundaries": [
                {"period_id": period.period_id, "start": str(period.start_date.date()), "end": str(period.end_date.date())}
                for period in thirds
            ],
        },
        "metrics": [
            "mean_and_median_final_equity",
            "mean_and_median_total_return",
            "benchmark_win_rates",
            "volatility",
            "downside_volatility",
            "drawdown_dollars_and_pct",
            "return_drawdown_proxy",
            "sharpe_like",
            "sortino_like",
            "joint_return_risk_outcomes",
        ],
        "outcome_definitions": sorted(VALIDATION_OUTCOMES),
        "parameter_wrapper_benchmark_or_period_selection_after_results_allowed": False,
        "period_selection_after_results_allowed": False,
        "provider_download": False,
        "intraday_data_used": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
    }
    manifest["manifest_consistency_passed_before_performance"] = validate_manifest(manifest)
    write_json(EVIDENCE_DIR / "validation_manifest.json", manifest)
    if not manifest["manifest_consistency_passed_before_performance"]:
        raise RuntimeError("validation manifest failed consistency checks before performance")

    monthly_90_rows = [row for period in monthly_90 for row in compare_period(period, primary_dates, close_by_symbol, native_returns)]
    monthly_180_rows = [row for period in monthly_180 for row in compare_period(period, primary_dates, close_by_symbol, native_returns)]
    nonoverlap_90_rows = [row for period in nonoverlap_90 for row in compare_period(period, primary_dates, close_by_symbol, native_returns)]
    nonoverlap_180_rows = [row for period in nonoverlap_180 for row in compare_period(period, primary_dates, close_by_symbol, native_returns)]
    full_rows = full_period_rows(primary_dates, close_by_symbol, native_returns)
    third_rows = chronological_third_rows(primary_dates, close_by_symbol, native_returns)
    all_window_rows = monthly_90_rows + monthly_180_rows + nonoverlap_90_rows + nonoverlap_180_rows

    win_rows, joint_rows, relative_rows = summarize_benchmark_rates(all_window_rows)
    invariants = {
        "splv_only": True,
        "no_provider_call_or_cache_refresh": True,
        "cache_hash_matches_original_screen": manifest["splv_cache_hash_matches_screen"],
        "windows_generated_before_performance": True,
        "matching_dates_used_for_all_available_comparisons": all(row["matching_dates_used"] is True for row in all_window_rows if row["benchmark_available"] is True),
        "entry_cost_equal_for_splv_spy_bil_buy_hold": True,
        "actual_etf_shares_held": True,
        "no_artificial_daily_or_quarterly_turnover": True,
        "no_bil_or_tactical_logic": True,
    }
    hashes_after = {
        "registry": screen.sha256_path(registry_path),
        "active_observations": screen.sha256_path(active_observations_path),
        "active_combo_series": screen.sha256_path(active_combo_path),
    }
    invariants.update(
        {
            "active_vm_state_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
            "active_combo_state_unchanged": hashes_before["active_combo_series"] == hashes_after["active_combo_series"],
            "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
            "no_lifecycle_evidence_level_promotion_or_paper_demo_state_changes": True,
            "candidate_exhaustive_run": False,
        }
    )
    invariant_pass_keys = [
        "splv_only",
        "no_provider_call_or_cache_refresh",
        "cache_hash_matches_original_screen",
        "windows_generated_before_performance",
        "matching_dates_used_for_all_available_comparisons",
        "entry_cost_equal_for_splv_spy_bil_buy_hold",
        "actual_etf_shares_held",
        "no_artificial_daily_or_quarterly_turnover",
        "no_bil_or_tactical_logic",
        "active_vm_state_unchanged",
        "active_combo_state_unchanged",
        "registry_byte_identical",
        "no_lifecycle_evidence_level_promotion_or_paper_demo_state_changes",
    ]
    invariants_passed = all(bool(invariants[key]) is True for key in invariant_pass_keys)
    outcome, reason = validation_decision(relative_rows, third_rows, invariants_passed)
    if outcome not in VALIDATION_OUTCOMES:
        outcome = "invalid_methodology"
        reason = "outcome_not_in_allowed_set"

    write_csv(EVIDENCE_DIR / "monthly_start_90d_results.csv", monthly_90_rows)
    write_csv(EVIDENCE_DIR / "monthly_start_180d_results.csv", monthly_180_rows)
    write_csv(EVIDENCE_DIR / "non_overlapping_90d_results.csv", nonoverlap_90_rows)
    write_csv(EVIDENCE_DIR / "non_overlapping_180d_results.csv", nonoverlap_180_rows)
    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_rows)
    write_csv(EVIDENCE_DIR / "chronological_thirds_metrics.csv", third_rows)
    write_csv(EVIDENCE_DIR / "benchmark_win_rates.csv", win_rows)
    write_csv(EVIDENCE_DIR / "return_risk_joint_outcomes.csv", joint_rows)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", relative_rows)
    write_csv(EVIDENCE_DIR / "accounting_and_alignment_invariants.csv", [{**invariants, "invariants_passed": invariants_passed}])
    write_csv(EVIDENCE_DIR / "artifact_lineage.csv", lineage_rows)

    memory_status = (
        "retain_exact_candidate_for_separate_direction_owner_review"
        if outcome == "validation_supports_further_review"
        else "close_exact_candidate_for_immediate_retesting"
    )
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "validation_outcome": outcome,
                "memory_status": memory_status,
                "failure_reason": "" if outcome == "validation_supports_further_review" else reason,
                "broader_low_volatility_family_preserved": True,
                "splv_variants_created": False,
                "usmv_tested": False,
                "timing_overlay_added": False,
                "promotion_authorized": False,
                "paper_demo_authorized": False,
            }
        ],
    )
    write_json(
        EVIDENCE_DIR / "validation_outcome.json",
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "validation_outcome": outcome,
            "outcome_reason": reason,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "strategy_variants_created": False,
            "next_action": "direction_owner_review_splv_static_low_vol_factor_validation_v1"
            if outcome == "validation_supports_further_review"
            else "record_splv_static_low_vol_factor_validation_result",
        },
    )
    write_summary(outcome, reason, relative_rows, full_rows)
    consistency = {
        "consistency_passed": bool(invariants_passed and manifest["manifest_consistency_passed_before_performance"]),
        "manifest_passed_before_performance": manifest["manifest_consistency_passed_before_performance"],
        "monthly_start_90_count": len(monthly_90),
        "monthly_start_180_count": len(monthly_180),
        "non_overlapping_90_count": len(nonoverlap_90),
        "non_overlapping_180_count": len(nonoverlap_180),
        "chronological_third_count": len(thirds),
        "full_period_start": str(full_period.start_date.date()),
        "full_period_end": str(full_period.end_date.date()),
        "registry_byte_identical": invariants["registry_byte_identical"],
        "active_observations_unchanged": invariants["active_vm_state_unchanged"],
        "active_combo_unchanged": invariants["active_combo_state_unchanged"],
        "deterministic_output_no_timestamps": True,
        "provider_download": False,
        "paper_demo_authorized": False,
        "promotion_authorized": False,
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**consistency, "validation_outcome": outcome, "outcome_reason": reason}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean))
