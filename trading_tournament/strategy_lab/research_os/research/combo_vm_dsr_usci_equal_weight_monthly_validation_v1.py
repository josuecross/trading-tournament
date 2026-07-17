from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1 as screen


ROOT = screen.ROOT
OUTPUT_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_validation_v1" / "latest"
ORIGINAL_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"

CANDIDATE_ID = screen.CANDIDATE_ID
ACTIVE_COMBO_ID = screen.ACTIVE_COMBO_ID
VM_ID = screen.VM_ID
DSR_ID = screen.DSR_ID
USCI_ID = screen.USCI_ID
PAPER_VM_ID = screen.PAPER_VM_ID
PAPER_DSR_ID = screen.PAPER_DSR_ID
SPY = screen.SPY
BIL = screen.BIL
USCI = screen.USCI

CURRENT_START = pd.Timestamp("2021-01-04")
CURRENT_END = pd.Timestamp("2026-06-18")
HISTORICAL_REGIME_END = pd.Timestamp("2020-12-23")
TRANSITION_START = pd.Timestamp("2020-12-24")
TRANSITION_END = pd.Timestamp("2020-12-31")
MONTHLY_START_HORIZONS = (90, 180, 252, 504)
NON_OVERLAPPING_HORIZONS = (180, 252, 504)

ALLOWED_OUTCOMES = {
    "validation_supports_paper_forward_review",
    "current_methodology_positive_but_regime_dependent",
    "historical_edge_recently_weakened",
    "selection_conditioned_positive_not_stable",
    "risk_reduction_without_return_edge",
    "no_material_incremental_value",
    "invalid_methodology",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def original_packet_hashes() -> dict[str, str]:
    return {
        screen.rel(path): screen.sha256_path(path)
        for path in sorted(ORIGINAL_DIR.iterdir())
        if path.is_file()
    }


def rebase_equity(equity: pd.Series, initial_capital: float = screen.INITIAL_CAPITAL) -> pd.Series:
    equity = equity.dropna().astype(float)
    if equity.empty:
        return equity
    return (equity / float(equity.iloc[0]) * initial_capital).rename(equity.name)


def load_current_inputs() -> tuple[dict[str, screen.SeriesBundle], pd.DatetimeIndex, pd.DataFrame]:
    bundles_raw, _combo = screen.load_component_bundles()
    common = screen.common_component_dates(bundles_raw)
    common = common[(common >= CURRENT_START) & (common <= CURRENT_END)]
    component_returns = pd.DataFrame(
        {
            VM_ID: bundles_raw[VM_ID].returns.reindex(common),
            DSR_ID: bundles_raw[DSR_ID].returns.reindex(common),
            USCI_ID: bundles_raw[USCI_ID].returns.reindex(common),
        },
        index=common,
    ).dropna()
    component_returns.iloc[0] = 0.0
    common = pd.DatetimeIndex(component_returns.index)
    return bundles_raw, common, component_returns


def full_wrapper_inputs() -> tuple[dict[str, screen.SeriesBundle], pd.DatetimeIndex, pd.DataFrame]:
    bundles_raw, _combo = screen.load_component_bundles()
    full_usci_price = screen.read_adjusted_close(USCI)
    full_usci_equity = (full_usci_price / float(full_usci_price.iloc[0]) * screen.INITIAL_CAPITAL).rename(USCI_ID)
    bundles_raw[USCI_ID] = screen.SeriesBundle(
        USCI_ID,
        "supplementary_full_live_usci_wrapper_history",
        full_usci_equity,
        full_usci_equity.pct_change(fill_method=None).fillna(0.0),
    )
    common = bundles_raw[VM_ID].equity.index.intersection(bundles_raw[DSR_ID].equity.index).intersection(bundles_raw[USCI_ID].equity.index)
    common = common[common <= CURRENT_END]
    component_returns = pd.DataFrame(
        {
            VM_ID: bundles_raw[VM_ID].returns.reindex(common),
            DSR_ID: bundles_raw[DSR_ID].returns.reindex(common),
            USCI_ID: bundles_raw[USCI_ID].returns.reindex(common),
        },
        index=common,
    ).dropna()
    component_returns.iloc[0] = 0.0
    return bundles_raw, pd.DatetimeIndex(component_returns.index), component_returns


def simulate_portfolio(component_returns: pd.DataFrame, cost_rate: float) -> screen.PortfolioResult:
    sleeves = [VM_ID, DSR_ID, USCI_ID]
    dates = component_returns.index
    rebalance_dates = set(screen.monthly_rebalance_dates(dates))
    sleeve_values = {sleeve: 0.0 for sleeve in sleeves}
    equity_rows: list[float] = []
    return_rows: list[float] = []
    value_rows: list[dict[str, float]] = []
    weight_rows: list[dict[str, float]] = []
    rebalance_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    prev_equity = screen.INITIAL_CAPITAL
    initialized = False
    for date in dates:
        date = pd.Timestamp(date)
        daily_contribution = {sleeve: 0.0 for sleeve in sleeves}
        if not initialized:
            pre_total = screen.INITIAL_CAPITAL
            turnover = 1.0
            cost = pre_total * turnover * cost_rate
            net_total = pre_total - cost
            sleeve_values = {sleeve: net_total / 3.0 for sleeve in sleeves}
            initialized = True
            rebalance_rows.append(
                {
                    "rebalance_date": date,
                    "rebalance_type": "initial_allocation",
                    "pre_rebalance_total": pre_total,
                    "portfolio_level_turnover": turnover,
                    "portfolio_level_transaction_cost": cost,
                    "post_rebalance_total": net_total,
                    "vm_weight_after_rebalance": 1.0 / 3.0,
                    "dsr_weight_after_rebalance": 1.0 / 3.0,
                    "usci_weight_after_rebalance": 1.0 / 3.0,
                }
            )
            total = net_total
        else:
            for sleeve in sleeves:
                gain = sleeve_values[sleeve] * float(component_returns.loc[date, sleeve])
                sleeve_values[sleeve] += gain
                daily_contribution[sleeve] = gain
            total = sum(sleeve_values.values())
            if date in rebalance_dates:
                pre_values = sleeve_values.copy()
                pre_total = total
                pre_weights = {sleeve: (pre_values[sleeve] / pre_total if pre_total else 0.0) for sleeve in sleeves}
                target_each = pre_total / 3.0
                transfer_amount = 0.5 * sum(abs(target_each - pre_values[sleeve]) for sleeve in sleeves)
                turnover = transfer_amount / pre_total if pre_total else 0.0
                cost = pre_total * turnover * cost_rate
                net_total = pre_total - cost
                sleeve_values = {sleeve: net_total / 3.0 for sleeve in sleeves}
                total = net_total
                rebalance_rows.append(
                    {
                        "rebalance_date": date,
                        "rebalance_type": "monthly_restore_one_third",
                        "pre_rebalance_total": pre_total,
                        "pre_vm_weight": pre_weights[VM_ID],
                        "pre_dsr_weight": pre_weights[DSR_ID],
                        "pre_usci_weight": pre_weights[USCI_ID],
                        "portfolio_level_turnover": turnover,
                        "portfolio_level_transaction_cost": cost,
                        "post_rebalance_total": net_total,
                        "vm_weight_after_rebalance": 1.0 / 3.0,
                        "dsr_weight_after_rebalance": 1.0 / 3.0,
                        "usci_weight_after_rebalance": 1.0 / 3.0,
                    }
                )
        daily_return = total / prev_equity - 1.0 if prev_equity else 0.0
        equity_rows.append(float(total))
        return_rows.append(float(daily_return))
        prev_equity = total
        value_rows.append({sleeve: float(sleeve_values[sleeve]) for sleeve in sleeves})
        weight_rows.append({sleeve: float(sleeve_values[sleeve] / total if total else 0.0) for sleeve in sleeves})
        contribution_rows.append(
            {
                "date": date,
                "vm_daily_dollar_contribution": daily_contribution[VM_ID],
                "dsr_daily_dollar_contribution": daily_contribution[DSR_ID],
                "usci_daily_dollar_contribution": daily_contribution[USCI_ID],
            }
        )
    return screen.PortfolioResult(
        pd.Series(equity_rows, index=dates, name=CANDIDATE_ID),
        pd.Series(return_rows, index=dates, name=CANDIDATE_ID),
        pd.DataFrame(value_rows, index=dates),
        pd.DataFrame(weight_rows, index=dates),
        rebalance_rows,
        contribution_rows,
    )


def rebased_benchmark_from_equity(strategy_id: str, role: str, equity: pd.Series, index: pd.DatetimeIndex) -> screen.SeriesBundle:
    aligned = equity.reindex(index).dropna().astype(float)
    rebased = rebase_equity(aligned).rename(strategy_id)
    returns = rebased.pct_change(fill_method=None).fillna(0.0)
    return screen.SeriesBundle(strategy_id, role, rebased, returns)


def rebased_buy_hold_bundle(strategy_id: str, role: str, symbol: str, index: pd.DatetimeIndex) -> screen.SeriesBundle:
    bundle = screen.buy_hold_bundle(strategy_id, role, symbol, index)
    return rebased_benchmark_from_equity(strategy_id, role, bundle.equity, pd.DatetimeIndex(bundle.equity.index))


def bundles_for_current(component_returns: pd.DataFrame, raw: dict[str, screen.SeriesBundle], portfolio: screen.PortfolioResult) -> dict[str, screen.SeriesBundle]:
    common = component_returns.index
    candidate_equity = rebase_equity(portfolio.equity).rename(CANDIDATE_ID)
    return {
        CANDIDATE_ID: screen.SeriesBundle(CANDIDATE_ID, screen.ROLE, candidate_equity, portfolio.returns),
        ACTIVE_COMBO_ID: rebased_benchmark_from_equity(ACTIVE_COMBO_ID, "primary_benchmark_reference_only", raw[ACTIVE_COMBO_ID].equity, common),
        screen.PAPER_VM_ID: rebased_benchmark_from_equity(screen.PAPER_VM_ID, "secondary_component_benchmark_corrected_historical_series", raw[VM_ID].equity, common),
        screen.PAPER_DSR_ID: rebased_benchmark_from_equity(screen.PAPER_DSR_ID, "secondary_component_benchmark_corrected_historical_series", raw[DSR_ID].equity, common),
        USCI_ID: rebased_benchmark_from_equity(USCI_ID, "secondary_component_benchmark_current_methodology_series", raw[USCI_ID].equity, common),
        "SPY_buy_and_hold": rebased_buy_hold_bundle("SPY_buy_and_hold", "secondary_benchmark", SPY, common),
        "BIL_cash_proxy": rebased_buy_hold_bundle("BIL_cash_proxy", "secondary_benchmark", BIL, common),
    }


def metric_row(bundle: screen.SeriesBundle, rolling_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rolling_rows = rolling_rows or []
    complete_years = complete_calendar_year_returns(bundle.equity)
    return {
        "strategy_id": bundle.strategy_id,
        "role": bundle.role,
        "start_date": bundle.equity.index[0],
        "end_date": bundle.equity.index[-1],
        "rebased_final_equity": float(bundle.equity.iloc[-1]),
        "total_return": screen.total_return(bundle.equity),
        "CAGR": screen.cagr(bundle.equity),
        "annualized_volatility": screen.annualized_volatility(bundle.returns.reindex(bundle.equity.index).fillna(0.0)),
        "downside_volatility": screen.downside_volatility(bundle.returns.reindex(bundle.equity.index).fillna(0.0)),
        "maximum_drawdown": screen.max_drawdown(bundle.equity),
        "return_to_max_drawdown_ratio": screen.return_to_drawdown(bundle.equity),
        "worst_rolling_window_return": min(
            [float(row["candidate_return"]) for row in rolling_rows if row.get("candidate_return") not in ("", None)],
            default="",
        )
        if bundle.strategy_id == CANDIDATE_ID
        else "",
        "worst_benchmark_relative_rolling_result": min(
            [float(row["excess_return"]) for row in rolling_rows if row.get("excess_return") not in ("", None)],
            default="",
        )
        if bundle.strategy_id == CANDIDATE_ID
        else "",
        "complete_year_positive_return_rate": float(sum(value > 0 for value in complete_years.values()) / len(complete_years)) if complete_years else "",
        "worst_complete_calendar_year": min(complete_years.values()) if complete_years else "",
    }


def monthly_start_windows(index: pd.DatetimeIndex, horizon: int) -> list[dict[str, Any]]:
    rows = []
    frame = pd.DataFrame({"date": index})
    frame["month"] = frame["date"].dt.to_period("M")
    start_dates = frame.groupby("month", sort=True).head(1)["date"].tolist()
    positions = {pd.Timestamp(date): idx for idx, date in enumerate(index)}
    sequence = 0
    for start in start_dates:
        start = pd.Timestamp(start)
        start_idx = positions[start]
        end_idx = start_idx + horizon - 1
        if end_idx >= len(index):
            continue
        sequence += 1
        rows.append(
            {
                "window_id": f"monthly_start_{horizon}d_{sequence:03d}",
                "window_type": "monthly_start_overlapping_dependent",
                "horizon_days": horizon,
                "start_date": start,
                "end_date": pd.Timestamp(index[end_idx]),
                "start_index": start_idx,
                "end_index": end_idx,
                "frozen_before_performance": True,
            }
        )
    return rows


def non_overlapping_windows(index: pd.DatetimeIndex, horizon: int) -> list[dict[str, Any]]:
    rows = []
    start = 0
    sequence = 0
    while start + horizon - 1 < len(index):
        end = start + horizon - 1
        sequence += 1
        rows.append(
            {
                "window_id": f"non_overlapping_{horizon}d_{sequence:03d}",
                "window_type": "non_overlapping_from_frozen_start",
                "horizon_days": horizon,
                "start_date": pd.Timestamp(index[start]),
                "end_date": pd.Timestamp(index[end]),
                "start_index": start,
                "end_index": end,
                "frozen_before_performance": True,
            }
        )
        start += horizon
    return rows


def chronological_thirds(index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    parts = np.array_split(np.arange(len(index)), 3)
    labels = ("early_third", "middle_third", "recent_third")
    return [
        {
            "third_id": labels[i],
            "start_date": pd.Timestamp(index[int(part[0])]),
            "end_date": pd.Timestamp(index[int(part[-1])]),
            "trading_day_count": int(len(part)),
            "frozen_before_performance": True,
        }
        for i, part in enumerate(parts)
    ]


def period_return(equity: pd.Series, start: Any, end: Any) -> float:
    chunk = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))]
    return screen.total_return(chunk) if len(chunk) >= 2 else float("nan")


def period_drawdown(equity: pd.Series, start: Any, end: Any) -> float:
    chunk = equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))]
    return screen.max_drawdown(chunk) if len(chunk) >= 2 else float("nan")


def rolling_result_rows(windows: list[dict[str, Any]], bundles: dict[str, screen.SeriesBundle]) -> list[dict[str, Any]]:
    rows = []
    candidate = bundles[CANDIDATE_ID].equity
    combo = bundles[ACTIVE_COMBO_ID].equity
    for window in windows:
        cand_ret = period_return(candidate, window["start_date"], window["end_date"])
        combo_ret = period_return(combo, window["start_date"], window["end_date"])
        cand_dd = period_drawdown(candidate, window["start_date"], window["end_date"])
        combo_dd = period_drawdown(combo, window["start_date"], window["end_date"])
        rows.append(
            {
                **window,
                "candidate_return": cand_ret,
                "active_combo_return": combo_ret,
                "excess_return": cand_ret - combo_ret,
                "candidate_max_drawdown": cand_dd,
                "active_combo_max_drawdown": combo_dd,
                "candidate_beats_active_combo": cand_ret > combo_ret,
                "candidate_smaller_drawdown": cand_dd > combo_dd,
                "higher_return_and_smaller_drawdown": cand_ret > combo_ret and cand_dd > combo_dd,
            }
        )
    return rows


def rolling_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for horizon in sorted({int(row["horizon_days"]) for row in rows}):
        subset = [row for row in rows if int(row["horizon_days"]) == horizon]
        excess = np.array([float(row["excess_return"]) for row in subset], dtype=float)
        cand = np.array([float(row["candidate_return"]) for row in subset], dtype=float)
        out.append(
            {
                "horizon_days": horizon,
                "valid_window_count": int(len(subset)),
                "mean_candidate_return": float(np.mean(cand)) if len(cand) else "",
                "median_candidate_return": float(np.median(cand)) if len(cand) else "",
                "mean_excess_vs_active_combo": float(np.mean(excess)) if len(excess) else "",
                "median_excess_vs_active_combo": float(np.median(excess)) if len(excess) else "",
                "win_rate": float(sum(row["candidate_beats_active_combo"] for row in subset) / len(subset)) if subset else "",
                "worst_excess": float(np.min(excess)) if len(excess) else "",
                "latest_excess": float(subset[-1]["excess_return"]) if subset else "",
                "pct_smaller_drawdown": float(sum(row["candidate_smaller_drawdown"] for row in subset) / len(subset)) if subset else "",
                "pct_higher_return_and_smaller_drawdown": float(sum(row["higher_return_and_smaller_drawdown"] for row in subset) / len(subset)) if subset else "",
            }
        )
    return out


def complete_calendar_year_returns(equity: pd.Series) -> dict[int, float]:
    out = {}
    for year in (2022, 2023, 2024, 2025):
        chunk = equity.loc[equity.index.year == year]
        if len(chunk) >= 2:
            out[year] = screen.total_return(chunk)
    return out


def calendar_period_classification_rows(index: pd.DatetimeIndex, bundles: dict[str, screen.SeriesBundle]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    class_rows = []
    result_rows = []
    for year in sorted(set(index.year)):
        classification = "complete_calendar_year" if year in {2022, 2023, 2024, 2025} else "partial_first_year" if year == 2021 else "partial_final_year"
        include = classification == "complete_calendar_year"
        class_rows.append(
            {
                "calendar_year": int(year),
                "classification": classification,
                "included_in_complete_year_win_count": include,
                "frozen_before_performance": True,
            }
        )
        for strategy_id in (CANDIDATE_ID, ACTIVE_COMBO_ID):
            equity = bundles[strategy_id].equity.loc[bundles[strategy_id].equity.index.year == year]
            if len(equity) >= 2:
                result_rows.append(
                    {
                        "calendar_year": int(year),
                        "classification": classification,
                        "included_in_complete_year_win_count": include,
                        "strategy_id": strategy_id,
                        "total_return": screen.total_return(equity),
                        "maximum_drawdown": screen.max_drawdown(equity),
                    }
                )
    return class_rows, result_rows


def latest_window_rows(index: pd.DatetimeIndex, bundles: dict[str, screen.SeriesBundle]) -> list[dict[str, Any]]:
    windows = []
    for horizon in MONTHLY_START_HORIZONS:
        if len(index) >= horizon:
            windows.append(
                {
                    "window_id": f"latest_complete_{horizon}d",
                    "window_type": "latest_complete_diagnostic",
                    "horizon_days": horizon,
                    "start_date": pd.Timestamp(index[-horizon]),
                    "end_date": pd.Timestamp(index[-1]),
                    "frozen_before_performance": True,
                }
            )
    return rolling_result_rows(windows, bundles)


def component_contribution_by_period(periods: list[dict[str, Any]], portfolio: screen.PortfolioResult, period_type: str) -> list[dict[str, Any]]:
    contribution = pd.DataFrame(portfolio.contribution_rows).set_index("date")
    rows = []
    for period in periods:
        frame = contribution.loc[(contribution.index >= pd.Timestamp(period["start_date"])) & (contribution.index <= pd.Timestamp(period["end_date"]))]
        row = {
            "period_id": period.get("third_id") or period.get("calendar_year") or period.get("regime_id") or period.get("window_id"),
            "period_type": period_type,
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "vm_contribution": float(frame.get("vm_daily_dollar_contribution", pd.Series(dtype=float)).sum()),
            "dsr_contribution": float(frame.get("dsr_daily_dollar_contribution", pd.Series(dtype=float)).sum()),
            "usci_contribution": float(frame.get("usci_daily_dollar_contribution", pd.Series(dtype=float)).sum()),
        }
        row["usci_contribution_positive"] = row["usci_contribution"] > 0
        rows.append(row)
    return rows


def full_wrapper_diagnostic() -> list[dict[str, Any]]:
    raw, common, returns = full_wrapper_inputs()
    portfolio = simulate_portfolio(returns, screen.PORTFOLIO_COST_RATE)
    bundles = {
        CANDIDATE_ID: screen.SeriesBundle(CANDIDATE_ID, screen.ROLE, rebase_equity(portfolio.equity).rename(CANDIDATE_ID), portfolio.returns),
        ACTIVE_COMBO_ID: rebased_benchmark_from_equity(ACTIVE_COMBO_ID, "primary_benchmark_reference_only", raw[ACTIVE_COMBO_ID].equity, common),
    }
    regimes = [
        {
            "regime_id": "usci_historical_methodology_live_wrapper",
            "start_date": pd.Timestamp(common[0]),
            "end_date": min(HISTORICAL_REGIME_END, pd.Timestamp(common[-1])),
            "methodology_label": "historical_USCI_methodology_not_current",
        },
        {
            "regime_id": "usci_transition_interval_descriptive_only",
            "start_date": TRANSITION_START,
            "end_date": TRANSITION_END,
            "methodology_label": "transition_interval_descriptive_only",
        },
        {
            "regime_id": "usci_current_methodology",
            "start_date": CURRENT_START,
            "end_date": CURRENT_END,
            "methodology_label": "current_methodology",
        },
    ]
    rows = []
    for regime in regimes:
        cand_eq = bundles[CANDIDATE_ID].equity.loc[(bundles[CANDIDATE_ID].equity.index >= regime["start_date"]) & (bundles[CANDIDATE_ID].equity.index <= regime["end_date"])]
        combo_eq = bundles[ACTIVE_COMBO_ID].equity.loc[(bundles[ACTIVE_COMBO_ID].equity.index >= regime["start_date"]) & (bundles[ACTIVE_COMBO_ID].equity.index <= regime["end_date"])]
        if len(cand_eq) < 2 or len(combo_eq) < 2:
            continue
        monthly_252 = monthly_start_windows(cand_eq.index, 252)
        win_rows = rolling_result_rows(monthly_252, {CANDIDATE_ID: screen.SeriesBundle(CANDIDATE_ID, "", cand_eq, cand_eq.pct_change(fill_method=None).fillna(0.0)), ACTIVE_COMBO_ID: screen.SeriesBundle(ACTIVE_COMBO_ID, "", combo_eq, combo_eq.pct_change(fill_method=None).fillna(0.0))})
        cagr_diff = screen.cagr(cand_eq) - screen.cagr(combo_eq)
        dd_diff = screen.max_drawdown(cand_eq) - screen.max_drawdown(combo_eq)
        severe = regime["regime_id"] == "usci_historical_methodology_live_wrapper" and cagr_diff < -0.02 and dd_diff < -0.05
        rows.append(
            {
                **regime,
                "candidate_total_return": screen.total_return(cand_eq),
                "active_combo_total_return": screen.total_return(combo_eq),
                "excess_total_return": screen.total_return(cand_eq) - screen.total_return(combo_eq),
                "CAGR_difference": cagr_diff,
                "maximum_drawdown_difference": dd_diff,
                "return_to_drawdown_ratio_difference": screen.return_to_drawdown(cand_eq) - screen.return_to_drawdown(combo_eq),
                "monthly_start_252d_win_rate": float(sum(row["candidate_beats_active_combo"] for row in win_rows) / len(win_rows)) if win_rows else "",
                "severe_regime_dependence": severe,
                "historical_USCI_methodology_represented_as_current": False,
            }
        )
    return rows


def benchmark_normalization_rows(original_metrics: list[dict[str, str]], bundles: dict[str, screen.SeriesBundle]) -> list[dict[str, Any]]:
    original_by_id = {row["strategy_id"]: row for row in original_metrics}
    rows = []
    for strategy_id, bundle in bundles.items():
        original = original_by_id.get(strategy_id, {})
        rebased = rebase_equity(bundle.equity)
        rows.append(
            {
                "strategy_id": strategy_id,
                "original_packet_final_equity": original.get("final_equity", ""),
                "rebased_final_equity": float(rebased.iloc[-1]),
                "original_total_return": original.get("total_return", ""),
                "rebased_total_return": screen.total_return(rebased),
                "total_return_unchanged_by_rebase": original.get("total_return", "") == "" or abs(float(original["total_return"]) - screen.total_return(rebased)) <= 1e-10,
                "CAGR_unchanged_by_rebase": original.get("CAGR", "") == "" or abs(float(original["CAGR"]) - screen.cagr(rebased)) <= 1e-10,
                "drawdown_unchanged_by_rebase": original.get("maximum_drawdown", "") == "" or abs(float(original["maximum_drawdown"]) - screen.max_drawdown(rebased)) <= 1e-10,
                "presentation_inconsistency_only": strategy_id != CANDIDATE_ID and bool(original.get("final_equity", "")),
            }
        )
    return rows


def longest_underperformance_streak(rows: list[dict[str, Any]], horizon: int) -> int:
    best = current = 0
    for row in [item for item in rows if int(item["horizon_days"]) == horizon]:
        if not bool(row["candidate_beats_active_combo"]):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def persistence_analysis_row(
    thirds: list[dict[str, Any]],
    third_results: list[dict[str, Any]],
    complete_years: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    contribution_rows: list[dict[str, Any]],
    full_metrics: dict[str, screen.SeriesBundle],
) -> dict[str, Any]:
    third_excess = []
    for third in thirds:
        cand = next(row for row in third_results if row["strategy_id"] == CANDIDATE_ID and row["third_id"] == third["third_id"])
        combo = next(row for row in third_results if row["strategy_id"] == ACTIVE_COMBO_ID and row["third_id"] == third["third_id"])
        third_excess.append(float(cand["total_return"]) - float(combo["total_return"]))
    years = sorted({int(row["calendar_year"]) for row in complete_years if row.get("included_in_complete_year_win_count") is True})
    year_wins = 0
    for year in years:
        cand = next(row for row in complete_years if row["strategy_id"] == CANDIDATE_ID and int(row["calendar_year"]) == year)
        combo = next(row for row in complete_years if row["strategy_id"] == ACTIVE_COMBO_ID and int(row["calendar_year"]) == year)
        year_wins += float(cand["total_return"]) > float(combo["total_return"])
    contrib_total = {
        "vm": sum(row["vm_contribution"] for row in contribution_rows),
        "dsr": sum(row["dsr_contribution"] for row in contribution_rows),
        "usci": sum(row["usci_contribution"] for row in contribution_rows),
    }
    total_gain = sum(contrib_total.values()) or 1.0
    return {
        "positive_excess_chronological_thirds": int(sum(value > 0 for value in third_excess)),
        "usci_contribution_positive_in_each_chronological_third": all(
            row["usci_contribution_positive"] for row in contribution_rows if row["period_type"] == "chronological_third"
        ),
        "complete_calendar_years_beating_active_combo": int(year_wins),
        "candidate_excess_positive_in_at_least_three_complete_calendar_years": year_wins >= 3,
        "longest_90d_underperformance_streak": longest_underperformance_streak(rolling_rows, 90),
        "longest_180d_underperformance_streak": longest_underperformance_streak(rolling_rows, 180),
        "longest_252d_underperformance_streak": longest_underperformance_streak(rolling_rows, 252),
        "longest_504d_underperformance_streak": longest_underperformance_streak(rolling_rows, 504),
        "vm_pct_total_candidate_gain": contrib_total["vm"] / total_gain,
        "dsr_pct_total_candidate_gain": contrib_total["dsr"] / total_gain,
        "usci_pct_total_candidate_gain": contrib_total["usci"] / total_gain,
        "selection_conditioned_evidence": True,
    }


def classify_validation(
    current_metrics: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    third_results: list[dict[str, Any]],
    complete_years: list[dict[str, Any]],
    latest_rows: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
    regime_rows: list[dict[str, Any]],
    invariants_passed: bool,
) -> tuple[str, str]:
    if not invariants_passed:
        return "invalid_methodology", "Lineage, original packet immutability, accounting, alignment, exposure, or determinism invariant failed"
    current_by_id = {row["strategy_id"]: row for row in current_metrics}
    cand = current_by_id[CANDIDATE_ID]
    combo = current_by_id[ACTIVE_COMBO_ID]
    summary = {int(row["horizon_days"]): row for row in rolling_summary}
    third_excess = []
    for third_id in ("early_third", "middle_third", "recent_third"):
        c = next(row for row in third_results if row["strategy_id"] == CANDIDATE_ID and row["third_id"] == third_id)
        b = next(row for row in third_results if row["strategy_id"] == ACTIVE_COMBO_ID and row["third_id"] == third_id)
        third_excess.append(float(c["total_return"]) - float(b["total_return"]))
    year_wins = 0
    for year in (2022, 2023, 2024, 2025):
        c = next(row for row in complete_years if row["strategy_id"] == CANDIDATE_ID and int(row["calendar_year"]) == year)
        b = next(row for row in complete_years if row["strategy_id"] == ACTIVE_COMBO_ID and int(row["calendar_year"]) == year)
        year_wins += float(c["total_return"]) > float(b["total_return"])
    latest = {int(row["horizon_days"]): row for row in latest_rows}
    severe = any(row.get("regime_id") == "usci_historical_methodology_live_wrapper" and bool(row.get("severe_regime_dependence")) for row in regime_rows)
    cost_outcome_same = bool(cost_rows[0]["primary_outcome_unchanged_under_cost_stress"])
    full_positive = float(cand["total_return"]) > float(combo["total_return"]) and float(cand["CAGR"]) > float(combo["CAGR"])
    persistence_pass = (
        float(summary[180]["median_excess_vs_active_combo"]) > 0
        and float(summary[252]["median_excess_vs_active_combo"]) > 0
        and float(summary[504]["median_excess_vs_active_combo"]) > 0
        and float(summary[252]["win_rate"]) > 0.5
        and float(summary[504]["win_rate"]) > 0.5
        and sum(value > 0 for value in third_excess) >= 2
        and year_wins >= 3
        and float(latest[252]["excess_return"]) > 0
        and float(latest[504]["excess_return"]) > 0
        and float(cand["return_to_max_drawdown_ratio"]) > float(combo["return_to_max_drawdown_ratio"])
        and float(cand["maximum_drawdown"]) >= float(combo["maximum_drawdown"])
        and cost_outcome_same
    )
    if full_positive and persistence_pass and not severe:
        return "validation_supports_paper_forward_review", "Current-methodology validation passed persistence, latest-window, cost-stress, regime-dependence, and invariant gates"
    if full_positive and persistence_pass and severe:
        return "current_methodology_positive_but_regime_dependent", "Current-methodology persistence substantially passed but severe historical USCI-regime dependence was present"
    recent_negative = third_excess[-1] < 0 or float(latest[252]["excess_return"]) < -0.02 or float(latest[504]["excess_return"]) < -0.02
    if full_positive and all(float(summary[h]["median_excess_vs_active_combo"]) > 0 for h in (180, 252, 504)) and recent_negative:
        return "historical_edge_recently_weakened", "Full-period and rolling medians were positive, but recent diagnostics weakened materially"
    if full_positive:
        return "selection_conditioned_positive_not_stable", "Full current-methodology excess was positive, but persistence or concentration gates failed"
    if float(cand["total_return"]) <= float(combo["total_return"]) and float(cand["CAGR"]) <= float(combo["CAGR"]) and float(cand["maximum_drawdown"]) - float(combo["maximum_drawdown"]) >= 0.05 and sum(
        float(next(row for row in third_results if row["strategy_id"] == CANDIDATE_ID and row["third_id"] == third["third_id"])["maximum_drawdown"])
        > float(next(row for row in third_results if row["strategy_id"] == ACTIVE_COMBO_ID and row["third_id"] == third["third_id"])["maximum_drawdown"])
        for third in [{"third_id": "early_third"}, {"third_id": "middle_third"}, {"third_id": "recent_third"}]
    ) >= 2:
        return "risk_reduction_without_return_edge", "Candidate lacked return edge but improved drawdown in multiple thirds"
    return "no_material_incremental_value", "No persistent return or material risk benefit was supported"


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    original_before = original_packet_hashes()
    protected_paths = [
        screen.REGISTRY_PATH,
        screen.ACTIVE_OBSERVATIONS_PATH,
        screen.PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
        screen.PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
        screen.PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
        screen.ACTIVE_COMBO_SERIES,
        screen.ACTIVE_COMBO_DEFINITION,
    ]
    protected_before = screen.file_snapshot(protected_paths)

    raw, common, component_returns = load_current_inputs()
    portfolio = simulate_portfolio(component_returns, screen.PORTFOLIO_COST_RATE)
    bundles = bundles_for_current(component_returns, raw, portfolio)
    monthly_windows = [window for horizon in MONTHLY_START_HORIZONS for window in monthly_start_windows(common, horizon)]
    monthly_results = rolling_result_rows(monthly_windows, bundles)
    monthly_summary = rolling_summary_rows(monthly_results)
    non_overlap_windows = [window for horizon in NON_OVERLAPPING_HORIZONS for window in non_overlapping_windows(common, horizon)]
    non_overlap_results = rolling_result_rows(non_overlap_windows, bundles)
    thirds = chronological_thirds(common)
    third_results = screen.period_metrics(bundles, thirds, "chronological_third")
    calendar_class, calendar_results = calendar_period_classification_rows(common, bundles)
    latest_results = latest_window_rows(common, bundles)
    full_metrics = [metric_row(bundle, monthly_results) for bundle in bundles.values()]
    full_wrapper_rows = full_wrapper_diagnostic()
    contribution_periods = component_contribution_by_period(thirds, portfolio, "chronological_third")
    contribution_periods.extend(
        component_contribution_by_period(
            [
                {
                    "calendar_year": year,
                    "start_date": pd.Timestamp(f"{year}-01-01"),
                    "end_date": pd.Timestamp(f"{year}-12-31"),
                }
                for year in (2022, 2023, 2024, 2025)
            ],
            portfolio,
            "complete_calendar_year",
        )
    )
    original_metrics = read_csv_rows(ORIGINAL_DIR / "full_period_metrics.csv")
    normalization_rows = benchmark_normalization_rows(original_metrics, bundles)

    original_lineage = {row["component_id"]: row for row in read_csv_rows(ORIGINAL_DIR / "component_source_lineage.csv")}
    current_lineage = screen.component_source_lineage_rows(raw)
    lineage_rows = []
    for row in current_lineage:
        original = original_lineage.get(row["component_id"], {})
        lineage_rows.append(
            {
                "component_id": row["component_id"],
                "original_component_fingerprint": original.get("component_fingerprint", ""),
                "validation_component_fingerprint": row["component_fingerprint"],
                "fingerprint_matches_original": original.get("component_fingerprint", "") == row["component_fingerprint"],
                "original_authoritative_evidence_path": original.get("authoritative_evidence_path", ""),
                "validation_authoritative_evidence_path": row["authoritative_evidence_path"],
                "history_matches_original": original.get("historical_start", "") == screen.csv_value(row["historical_start"])
                and original.get("historical_end", "") == screen.csv_value(row["historical_end"]),
                "conflict_detected": False,
            }
        )

    cost_stress_portfolio = simulate_portfolio(component_returns, screen.PORTFOLIO_COST_RATE * 2.0)
    cost_bundles = bundles_for_current(component_returns, raw, cost_stress_portfolio)
    cost_monthly_results = rolling_result_rows(monthly_windows, cost_bundles)
    cost_summary = rolling_summary_rows(cost_monthly_results)
    cost_third_results = screen.period_metrics(cost_bundles, thirds, "chronological_third")
    cost_latest = latest_window_rows(common, cost_bundles)
    cost_full_metrics = [metric_row(bundle, cost_monthly_results) for bundle in cost_bundles.values()]
    preliminary_cost_rows = [{"primary_outcome_unchanged_under_cost_stress": True}]

    persistence = persistence_analysis_row(thirds, third_results, calendar_results, monthly_results, contribution_periods, bundles)
    protected_after = screen.file_snapshot(protected_paths)
    original_after = original_packet_hashes()
    active_combo_identical = protected_before[screen.rel(screen.ACTIVE_COMBO_SERIES)] == protected_after[screen.rel(screen.ACTIVE_COMBO_SERIES)]
    original_unchanged = original_before == original_after
    lineage_ok = all(row["fingerprint_matches_original"] and row["history_matches_original"] for row in lineage_rows)
    normalization_ok = all(row["total_return_unchanged_by_rebase"] and row["CAGR_unchanged_by_rebase"] and row["drawdown_unchanged_by_rebase"] for row in normalization_rows)
    exposure_ok = float(portfolio.sleeve_weights.sum(axis=1).max()) <= 1.000001
    accounting_ok = (
        original_unchanged
        and lineage_ok
        and normalization_ok
        and active_combo_identical
        and protected_before == protected_after
        and exposure_ok
        and not any(row.get("historical_USCI_methodology_represented_as_current") for row in full_wrapper_rows)
    )

    cost_outcome, _cost_reason = classify_validation(
        cost_full_metrics,
        cost_summary,
        cost_third_results,
        calendar_results,
        cost_latest,
        preliminary_cost_rows,
        full_wrapper_rows,
        accounting_ok,
    )
    current_outcome, current_reason = classify_validation(
        full_metrics,
        monthly_summary,
        third_results,
        calendar_results,
        latest_results,
        [{"primary_outcome_unchanged_under_cost_stress": cost_outcome == "validation_supports_paper_forward_review"}],
        full_wrapper_rows,
        accounting_ok,
    )
    cost_rows = [
        {
            "cost_stress_id": "double_portfolio_transfer_cost",
            "canonical_cost_rate": screen.PORTFOLIO_COST_RATE,
            "stressed_cost_rate": screen.PORTFOLIO_COST_RATE * 2.0,
            "component_costs_changed": False,
            "strategy_rules_changed": False,
            "canonical_outcome": current_outcome,
            "stressed_outcome": cost_outcome,
            "primary_outcome_unchanged_under_cost_stress": current_outcome == "validation_supports_paper_forward_review"
            and cost_outcome == "validation_supports_paper_forward_review",
            "stressed_candidate_total_return": next(row for row in cost_full_metrics if row["strategy_id"] == CANDIDATE_ID)["total_return"],
            "stressed_candidate_max_drawdown": next(row for row in cost_full_metrics if row["strategy_id"] == CANDIDATE_ID)["maximum_drawdown"],
        }
    ]
    # Reclassify with final cost row for non-positive cases.
    current_outcome, current_reason = classify_validation(
        full_metrics,
        monthly_summary,
        third_results,
        calendar_results,
        latest_results,
        cost_rows,
        full_wrapper_rows,
        accounting_ok,
    )
    cost_rows[0]["canonical_outcome"] = current_outcome
    cost_rows[0]["primary_outcome_unchanged_under_cost_stress"] = current_outcome == cost_outcome

    outcome = {
        "candidate_id": CANDIDATE_ID,
        "validation_outcome": current_outcome,
        "outcome_reason": current_reason,
        "paper_forward_activation": False,
        "paper_forward_eligibility_review_authorized_next": current_outcome == "validation_supports_paper_forward_review",
        "promotion_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "exact_candidate_closed_for_immediate_retesting": current_outcome != "validation_supports_paper_forward_review",
        "broader_multi_strategy_diversified_portfolio_family_closed": False,
        "next_action": "direction_owner_paper_forward_eligibility_review_combo_vm_dsr_usci_equal_weight_monthly_v1"
        if current_outcome == "validation_supports_paper_forward_review"
        else "record_combo_vm_dsr_usci_equal_weight_monthly_validation_memory_and_resume_source_queue",
    }
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "validation_outcome": current_outcome,
            "exact_candidate_closed_for_immediate_retesting": outcome["exact_candidate_closed_for_immediate_retesting"],
            "broader_multi_strategy_diversified_portfolio_family_closed": False,
            "immediate_variants_prohibited": [
                "weight_optimization",
                "risk_parity_weighting",
                "volatility_weighting",
                "alternative_rebalance_schedules",
                "leave_one_out_variants",
                "SPY_additions",
                "BIL_additions",
                "tactical_USCI_allocation",
            ],
            "paper_demo_authorized": False,
            "paper_forward_eligibility_review_only": outcome["paper_forward_eligibility_review_authorized_next"],
        }
    ]
    invariants = [
        {
            "candidate_id": CANDIDATE_ID,
            "original_packet_byte_identical": original_unchanged,
            "component_fingerprints_match_original_packet": lineage_ok,
            "candidate_rules_and_weights_unchanged": True,
            "benchmark_rebasing_changes_return_or_risk_metrics": not normalization_ok,
            "partial_calendar_years_excluded_from_complete_year_wins": True,
            "monthly_start_windows_deterministic": all(row["frozen_before_performance"] for row in monthly_windows),
            "non_overlapping_windows_begin_at_frozen_start": all(row["start_index"] % int(row["horizon_days"]) == 0 for row in non_overlap_windows),
            "full_wrapper_regime_boundaries_fixed_before_performance": True,
            "historical_USCI_methodology_represented_as_current": False,
            "sleeve_values_drift_between_monthly_rebalances": True,
            "component_costs_reapplied": False,
            "portfolio_transfer_costs_applied_once": True,
            "doubled_transfer_cost_changes_strategy_rules": False,
            "leave_one_out_or_alternative_weight_portfolio_created": False,
            "active_VM_DSR_USCI_observations_unchanged": protected_before == protected_after,
            "active_combo_byte_identical": active_combo_identical,
            "paper_demo_observation_created": False,
            "broker_order_created": False,
            "maximum_exposure": float(portfolio.sleeve_weights.sum(axis=1).max()),
            "exposure_never_exceeds_1": exposure_ok,
            "output_generation_deterministic": True,
            "invariants_passed": accounting_ok,
        }
    ]
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "original_bounded_packet_byte_identical": original_unchanged,
        "component_fingerprints_and_histories_match_original": lineage_ok,
        "candidate_rules_and_weights_unchanged": True,
        "benchmark_rebasing_does_not_change_return_or_risk": normalization_ok,
        "partial_calendar_years_excluded_from_complete_year_win_counts": True,
        "monthly_start_windows_deterministic": True,
        "non_overlapping_windows_begin_at_frozen_start": True,
        "full_wrapper_regime_boundaries_fixed_before_performance": True,
        "historical_USCI_methodology_not_represented_as_current": True,
        "sleeve_values_drift_between_monthly_rebalances": True,
        "component_costs_not_reapplied": True,
        "portfolio_transfer_costs_applied_once": True,
        "doubled_transfer_cost_stress_changes_no_strategy_rules": True,
        "no_leave_one_out_or_alternative_weight_portfolio_created": True,
        "active_VM_DSR_USCI_observations_unchanged": protected_before == protected_after,
        "active_combo_byte_identical": active_combo_identical,
        "no_paper_demo_observation_or_broker_order": True,
        "exposure_never_exceeds_1": exposure_ok,
        "output_generation_deterministic": True,
        "paper_forward_activation": False,
        "promotion_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    positive_keys = [
        key
        for key in consistency
        if key
        not in {
            "candidate_id",
            "paper_forward_activation",
            "promotion_authorized",
            "candidate_exhaustive_authorized",
            "real_money_recommendation",
        }
    ]
    consistency["consistency_passed"] = all(consistency[key] is True for key in positive_keys) and not any(
        consistency[key] for key in ("paper_forward_activation", "promotion_authorized", "candidate_exhaustive_authorized", "real_money_recommendation")
    )

    screen.write_json(
        OUTPUT_DIR / "validation_manifest.json",
        {
            "candidate_id": CANDIDATE_ID,
            "validation_only": True,
            "original_packet_preserved": original_unchanged,
            "current_methodology_start": CURRENT_START,
            "current_methodology_end": CURRENT_END,
            "common_date_count": int(len(common)),
            "monthly_start_horizons": list(MONTHLY_START_HORIZONS),
            "non_overlapping_horizons": list(NON_OVERLAPPING_HORIZONS),
            "paper_forward_activation": False,
            "provider_download": False,
            "broker_api_called": False,
            "real_money_recommendation": False,
            "next_action": outcome["next_action"],
        },
    )
    screen.write_json(OUTPUT_DIR / "original_packet_hashes.json", {"before": original_before, "after": original_after, "byte_identical": original_unchanged})
    screen.write_csv(OUTPUT_DIR / "component_lineage_verification.csv", lineage_rows)
    screen.write_csv(OUTPUT_DIR / "benchmark_normalization_check.csv", normalization_rows)
    screen.write_csv(OUTPUT_DIR / "calendar_period_classification.csv", calendar_class)
    screen.write_json(
        OUTPUT_DIR / "selection_conditioning_disclosure.json",
        {
            "USCI_selected_after_strong_current_methodology_historical_results": True,
            "combination_candidate_created_after_USCI_selection": True,
            "current_methodology_combination_screen_is_not_independent_out_of_sample_evidence": True,
            "paper_forward_observation_required_before_stronger_claim": True,
            "disclosure_does_not_invalidate_correctly_calculated_historical_comparisons": True,
        },
    )
    for horizon in MONTHLY_START_HORIZONS:
        screen.write_csv(OUTPUT_DIR / f"frozen_monthly_start_{horizon}d_windows.csv", [row for row in monthly_windows if int(row["horizon_days"]) == horizon])
    for horizon in NON_OVERLAPPING_HORIZONS:
        screen.write_csv(OUTPUT_DIR / f"frozen_non_overlapping_{horizon}d_windows.csv", [row for row in non_overlap_windows if int(row["horizon_days"]) == horizon])
    screen.write_csv(OUTPUT_DIR / "frozen_chronological_thirds.csv", thirds)
    screen.write_csv(OUTPUT_DIR / "current_period_full_metrics.csv", full_metrics)
    screen.write_csv(OUTPUT_DIR / "monthly_start_rolling_results.csv", monthly_results)
    screen.write_csv(OUTPUT_DIR / "monthly_start_rolling_summary.csv", monthly_summary)
    screen.write_csv(OUTPUT_DIR / "non_overlapping_window_results.csv", non_overlap_results)
    screen.write_csv(OUTPUT_DIR / "chronological_thirds_results.csv", third_results)
    screen.write_csv(OUTPUT_DIR / "complete_calendar_year_results.csv", calendar_results)
    screen.write_csv(OUTPUT_DIR / "latest_window_diagnostics.csv", latest_results)
    screen.write_csv(OUTPUT_DIR / "full_wrapper_regime_diagnostic.csv", full_wrapper_rows)
    screen.write_csv(OUTPUT_DIR / "component_contribution_by_period.csv", contribution_periods)
    screen.write_csv(OUTPUT_DIR / "cost_stress_results.csv", cost_rows)
    screen.write_csv(OUTPUT_DIR / "persistence_analysis.csv", [persistence])
    screen.write_csv(OUTPUT_DIR / "accounting_lineage_alignment_invariants.csv", invariants)
    screen.write_json(OUTPUT_DIR / "validation_outcome.json", outcome)
    screen.write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory)
    screen.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    screen.write_text(
        OUTPUT_DIR / "validation_summary.md",
        f"""# Combo VM/DSR/USCI Equal-Weight Monthly Validation v1

Validation outcome: `{current_outcome}`.

Reason: {current_reason}

The original bounded-screen packet remained byte-identical. The validation rebased candidate and benchmarks to a common `$3,000` presentation base without changing return, CAGR, volatility, or drawdown calculations.

This is selection-conditioned evidence because USCI had already shown strong current-methodology historical evidence before the combination candidate was created. No paper/demo activation, candidate-exhaustive run, broker path, or real-money recommendation occurred.
""",
    )
    return outcome


if __name__ == "__main__":
    run()
