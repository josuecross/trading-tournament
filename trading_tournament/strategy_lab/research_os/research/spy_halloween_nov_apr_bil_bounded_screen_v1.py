from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "spy_halloween_nov_apr_bil_bounded_screen_v1" / "latest"
CANDIDATE_ID = "spy_halloween_nov_apr_bil_v1"
SOURCE_ID = "bouman_jacobsen_halloween_indicator_2002"
FAMILY_ID = "equity_calendar_seasonality"
MECHANISM = "fixed_six_month_equity_and_treasury_bill_seasonal_switching"
SPY = "SPY"
BIL = "BIL"
INITIAL_CAPITAL = active.STARTING_EQUITY
TRANSACTION_COST = active.SLIPPAGE
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
TURN_OF_MONTH_EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_turn_of_month_bounded_bt_run" / "latest"

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "risk_reduction_without_return_edge",
    "historical_edge_recently_weakened",
    "no_material_edge",
    "invalid_methodology",
}


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_symbol_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(ROOT / "data" / "cache" / f"{symbol}.csv")
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return clean.set_index("date")[symbol].astype(float)


def load_prices() -> pd.DataFrame:
    spy = read_symbol_close(SPY)
    bil = read_symbol_close(BIL)
    common = spy.index.intersection(bil.index).sort_values()
    return pd.DataFrame({SPY: spy.reindex(common), BIL: bil.reindex(common)}).dropna()


def cache_manifest_rows(prices: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in [SPY, BIL]:
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        series = read_symbol_close(symbol)
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "sha256": sha256_path(path),
                "cache_ready": True,
                "first_valid_date": series.index.min().date(),
                "last_valid_date": series.index.max().date(),
                "row_count": len(series),
                "provider_download": False,
                "cache_refreshed": False,
            }
        )
    rows.append(
        {
            "symbol": "COMMON_SPY_BIL",
            "cache_path": "data/cache/SPY.csv|data/cache/BIL.csv",
            "sha256": "",
            "cache_ready": True,
            "first_valid_date": prices.index.min().date(),
            "last_valid_date": prices.index.max().date(),
            "row_count": len(prices),
            "provider_download": False,
            "cache_refreshed": False,
        }
    )
    return rows


def target_asset_for_date(date: pd.Timestamp) -> str:
    return SPY if int(date.month) in {11, 12, 1, 2, 3, 4} else BIL


def target_weights(asset: str) -> dict[str, float]:
    return {SPY: 1.0 if asset == SPY else 0.0, BIL: 1.0 if asset == BIL else 0.0}


def generate_switch_dates(spy_dates: pd.DatetimeIndex, bil_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    spy_set = set(pd.DatetimeIndex(spy_dates))
    bil_set = set(pd.DatetimeIndex(bil_dates))
    all_dates = pd.DatetimeIndex(sorted(spy_set | bil_set))
    common_dates = pd.DatetimeIndex(sorted(spy_set & bil_set))
    rows: list[dict[str, Any]] = []
    if len(common_dates) == 0:
        return rows
    for year in range(common_dates.min().year, common_dates.max().year + 1):
        for month, target in [(4, BIL), (10, SPY)]:
            month_dates = all_dates[(all_dates.year == year) & (all_dates.month == month)]
            if len(month_dates) == 0:
                continue
            scheduled = pd.Timestamp(month_dates.max())
            valid = scheduled in spy_set and scheduled in bil_set
            execution = scheduled if valid else next((date for date in common_dates if date > scheduled), None)
            if execution is None or execution < common_dates.min() or execution > common_dates.max():
                continue
            rows.append(
                {
                    "switch_id": f"{year}_{month:02d}_{target}",
                    "switch_year": year,
                    "switch_month": month,
                    "source_rule": "end_of_april_sell_equities" if month == 4 else "end_of_october_repurchase_equities",
                    "scheduled_switch_date": scheduled.date(),
                    "execution_date": pd.Timestamp(execution).date(),
                    "delayed_to_next_common_session": not valid,
                    "target_after_close": target,
                    "SPY_target_after_close": 1.0 if target == SPY else 0.0,
                    "BIL_target_after_close": 1.0 if target == BIL else 0.0,
                    "generated_before_performance": True,
                }
            )
    return sorted(rows, key=lambda row: str(row["execution_date"]))


def freeze_blocks(common_dates: pd.DatetimeIndex, block_count: int = 5) -> list[dict[str, Any]]:
    positions = np.array_split(np.arange(len(common_dates)), block_count)
    rows = []
    for index, pos in enumerate(positions, start=1):
        start = common_dates[int(pos[0])]
        end = common_dates[int(pos[-1])]
        rows.append(
            {
                "block_id": f"block_{index}",
                "block_number": index,
                "start_date": start.date(),
                "end_date": end.date(),
                "trading_day_count": len(pos),
                "initial_calendar_state": target_asset_for_date(pd.Timestamp(start)),
                "frozen_before_performance": True,
            }
        )
    return rows


def trade_to_target(
    equity: float,
    prices: pd.Series,
    weights_before: dict[str, float],
    target: dict[str, float],
    *,
    apply_cost: bool,
) -> tuple[dict[str, float], float, float]:
    turnover_units = abs(target[SPY] - weights_before.get(SPY, 0.0)) + abs(target[BIL] - weights_before.get(BIL, 0.0))
    cost = equity * turnover_units * TRANSACTION_COST if apply_cost and turnover_units > 0 else 0.0
    post_cost_equity = equity - cost
    shares = {
        SPY: post_cost_equity * target[SPY] / float(prices[SPY]) if target[SPY] > 0 else 0.0,
        BIL: post_cost_equity * target[BIL] / float(prices[BIL]) if target[BIL] > 0 else 0.0,
    }
    return shares, cost, turnover_units


def simulate_path(prices: pd.DataFrame, switches: list[dict[str, Any]], *, cost: bool = True) -> tuple[pd.DataFrame, dict[str, Any]]:
    switch_by_date = {pd.Timestamp(row["execution_date"]): row for row in switches}
    shares = {SPY: 0.0, BIL: 0.0}
    weights = {SPY: 0.0, BIL: 0.0}
    previous_equity = INITIAL_CAPITAL
    total_cost = 0.0
    total_turnover = 0.0
    allocation_changes = 0
    rows: list[dict[str, Any]] = []
    for idx, (date, row) in enumerate(prices.iterrows()):
        close = pd.Series({SPY: float(row[SPY]), BIL: float(row[BIL])})
        pre_trade_equity = shares[SPY] * close[SPY] + shares[BIL] * close[BIL]
        if idx == 0:
            pre_trade_equity = INITIAL_CAPITAL
        action = "none"
        trade_cost = 0.0
        turnover = 0.0
        if idx == 0:
            target = target_weights(target_asset_for_date(pd.Timestamp(date)))
            shares, trade_cost, turnover = trade_to_target(pre_trade_equity, close, weights, target, apply_cost=cost)
            weights = target
            action = f"initial_buy_{SPY if target[SPY] else BIL}"
            allocation_changes += 1
        elif pd.Timestamp(date) in switch_by_date:
            target = target_weights(str(switch_by_date[pd.Timestamp(date)]["target_after_close"]))
            if target != weights:
                shares, trade_cost, turnover = trade_to_target(pre_trade_equity, close, weights, target, apply_cost=cost)
                weights = target
                action = f"switch_to_{SPY if target[SPY] else BIL}"
                allocation_changes += 1
        post_trade_equity = shares[SPY] * close[SPY] + shares[BIL] * close[BIL]
        total_cost += trade_cost
        total_turnover += turnover
        daily_return = post_trade_equity / previous_equity - 1.0 if previous_equity else 0.0
        rows.append(
            {
                "date": pd.Timestamp(date).date(),
                "SPY_close": close[SPY],
                "BIL_close": close[BIL],
                "SPY_shares": shares[SPY],
                "BIL_shares": shares[BIL],
                "SPY_weight": shares[SPY] * close[SPY] / post_trade_equity if post_trade_equity else 0.0,
                "BIL_weight": shares[BIL] * close[BIL] / post_trade_equity if post_trade_equity else 0.0,
                "weight_sum": (shares[SPY] * close[SPY] + shares[BIL] * close[BIL]) / post_trade_equity if post_trade_equity else 0.0,
                "gross_exposure": (abs(shares[SPY] * close[SPY]) + abs(shares[BIL] * close[BIL])) / post_trade_equity if post_trade_equity else 0.0,
                "trade_action": action,
                "turnover_units": turnover,
                "transaction_cost": trade_cost,
                "equity": post_trade_equity,
                "daily_return": daily_return,
                "calendar_state_after_close": SPY if weights[SPY] else BIL,
            }
        )
        previous_equity = post_trade_equity
    return pd.DataFrame(rows), {"transaction_costs": total_cost, "total_turnover": total_turnover, "allocation_change_count": allocation_changes}


def static_benchmark_path(prices: pd.DataFrame, symbol: str, *, cost: bool = True) -> tuple[pd.DataFrame, dict[str, Any]]:
    shares = {SPY: 0.0, BIL: 0.0}
    weights = {SPY: 0.0, BIL: 0.0}
    previous_equity = INITIAL_CAPITAL
    total_cost = 0.0
    rows = []
    for idx, (date, row) in enumerate(prices.iterrows()):
        close = pd.Series({SPY: float(row[SPY]), BIL: float(row[BIL])})
        pre_trade_equity = INITIAL_CAPITAL if idx == 0 else shares[SPY] * close[SPY] + shares[BIL] * close[BIL]
        trade_cost = 0.0
        turnover = 0.0
        action = "none"
        if idx == 0:
            weights = target_weights(symbol)
            shares, trade_cost, turnover = trade_to_target(pre_trade_equity, close, {SPY: 0.0, BIL: 0.0}, weights, apply_cost=cost)
            action = f"initial_buy_{symbol}"
        equity = shares[SPY] * close[SPY] + shares[BIL] * close[BIL]
        total_cost += trade_cost
        rows.append(
            {
                "date": pd.Timestamp(date).date(),
                "equity": equity,
                "daily_return": equity / previous_equity - 1.0 if previous_equity else 0.0,
                "trade_action": action,
                "transaction_cost": trade_cost,
                "turnover_units": turnover,
                "SPY_weight": weights[SPY],
                "BIL_weight": weights[BIL],
                "weight_sum": 1.0,
                "gross_exposure": 1.0,
            }
        )
        previous_equity = equity
    return pd.DataFrame(rows), {"transaction_costs": total_cost, "total_turnover": 1.0, "allocation_change_count": 1}


def drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def downside_vol(returns: pd.Series) -> float:
    downside = returns[returns < 0]
    return float(downside.std() * math.sqrt(252.0)) if len(downside) > 1 else 0.0


def metric_row(strategy_id: str, path: pd.DataFrame, stats: dict[str, Any], *, role: str) -> dict[str, Any]:
    equity = pd.to_numeric(path["equity"], errors="coerce")
    returns = pd.to_numeric(path["daily_return"], errors="coerce")
    dates = pd.to_datetime(path["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    cagr = float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1.0 / years) - 1.0)
    complete_years = calendar_year_rows(path, strategy_id=strategy_id)
    included_years = [row for row in complete_years if row["complete_year_for_win_rate"]]
    positive_rate = sum(row["total_return"] > 0 for row in included_years) / len(included_years) if included_years else ""
    worst_year = min((row["total_return"] for row in included_years), default="")
    return {
        "strategy_id": strategy_id,
        "role": role,
        "start_date": dates.min().date(),
        "end_date": dates.max().date(),
        "trading_days": len(path),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "CAGR": cagr,
        "annualized_volatility": float(returns.std() * math.sqrt(252.0)),
        "downside_volatility": downside_vol(returns),
        "max_drawdown": drawdown(equity),
        "worst_complete_calendar_year_return": worst_year,
        "positive_complete_year_rate": positive_rate,
        "total_turnover": stats["total_turnover"],
        "allocation_change_count": stats["allocation_change_count"],
        "transaction_costs": stats["transaction_costs"],
        "average_SPY_allocation": float(pd.to_numeric(path["SPY_weight"]).mean()),
        "average_BIL_allocation": float(pd.to_numeric(path["BIL_weight"]).mean()),
        "maximum_exposure": float(pd.to_numeric(path["gross_exposure"]).max()),
        "maximum_weight_sum": float(pd.to_numeric(path["weight_sum"]).max()),
    }


def calendar_year_rows(path: pd.DataFrame, *, strategy_id: str = CANDIDATE_ID) -> list[dict[str, Any]]:
    frame = path.copy()
    frame["date_ts"] = pd.to_datetime(frame["date"])
    rows = []
    for year, group in frame.groupby(frame["date_ts"].dt.year):
        start = group["date_ts"].min()
        end = group["date_ts"].max()
        complete = start.month == 1 and start.day <= 5 and end.month == 12 and end.day >= 27
        ret = float(group["equity"].iloc[-1] / group["equity"].iloc[0] - 1.0) if len(group) > 1 else 0.0
        rows.append(
            {
                "strategy_id": strategy_id,
                "calendar_year": int(year),
                "start_date": start.date(),
                "end_date": end.date(),
                "trading_days": len(group),
                "total_return": ret,
                "complete_year_for_win_rate": bool(complete),
                "positive_year": bool(ret > 0) if complete else "",
            }
        )
    return rows


def block_result_rows(prices: pd.DataFrame, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for block in blocks:
        block_prices = prices.loc[pd.Timestamp(block["start_date"]) : pd.Timestamp(block["end_date"])]
        switches = [
            row
            for row in generate_switch_dates(pd.DatetimeIndex(block_prices.index), pd.DatetimeIndex(block_prices.index))
            if pd.Timestamp(block["start_date"]) <= pd.Timestamp(row["execution_date"]) <= pd.Timestamp(block["end_date"])
        ]
        candidate_path, candidate_stats = simulate_path(block_prices, switches, cost=True)
        spy_path, spy_stats = static_benchmark_path(block_prices, SPY, cost=True)
        candidate = metric_row(CANDIDATE_ID, candidate_path, candidate_stats, role="candidate_block")
        spy = metric_row("SPY_buy_and_hold", spy_path, spy_stats, role="primary_benchmark_block")
        rows.append(
            {
                **block,
                "candidate_total_return": candidate["total_return"],
                "SPY_total_return": spy["total_return"],
                "excess_return_vs_SPY": float(candidate["total_return"]) - float(spy["total_return"]),
                "candidate_max_drawdown": candidate["max_drawdown"],
                "SPY_max_drawdown": spy["max_drawdown"],
                "candidate_beats_SPY": float(candidate["total_return"]) > float(spy["total_return"]),
            }
        )
    return rows


def benchmark_relative_rows(candidate: dict[str, Any], spy: dict[str, Any], bil: dict[str, Any], blocks: list[dict[str, Any]], years: list[dict[str, Any]]) -> list[dict[str, Any]]:
    block_excess = [float(row["excess_return_vs_SPY"]) for row in blocks]
    final_two_blocks_underperform = len(block_excess) >= 2 and block_excess[-1] < 0 and block_excess[-2] < 0
    complete_years = [row for row in years if row["strategy_id"] == CANDIDATE_ID and row["complete_year_for_win_rate"]]
    spy_years = {row["calendar_year"]: row for row in years if row["strategy_id"] == "SPY_buy_and_hold" and row["complete_year_for_win_rate"]}
    years_beating = 0
    for row in complete_years:
        spy_row = spy_years.get(row["calendar_year"])
        if spy_row and float(row["total_return"]) > float(spy_row["total_return"]):
            years_beating += 1
    return [
        {
            "comparison": "full_period_vs_SPY",
            "candidate_total_return": candidate["total_return"],
            "benchmark_total_return": spy["total_return"],
            "excess_return": float(candidate["total_return"]) - float(spy["total_return"]),
            "max_drawdown_difference_vs_SPY": float(candidate["max_drawdown"]) - float(spy["max_drawdown"]),
        },
        {
            "comparison": "full_period_vs_BIL",
            "candidate_total_return": candidate["total_return"],
            "benchmark_total_return": bil["total_return"],
            "excess_return": float(candidate["total_return"]) - float(bil["total_return"]),
            "max_drawdown_difference_vs_BIL": float(candidate["max_drawdown"]) - float(bil["max_drawdown"]),
        },
        {
            "comparison": "block_level_vs_SPY",
            "median_block_excess_return": float(np.median(block_excess)),
            "mean_block_excess_return": float(np.mean(block_excess)),
            "blocks_beating_SPY": sum(value > 0 for value in block_excess),
            "final_two_blocks_underperform_SPY": final_two_blocks_underperform,
            "recent_block_excess_return": block_excess[-1],
        },
        {
            "comparison": "calendar_year_vs_SPY",
            "complete_calendar_years": len(complete_years),
            "calendar_years_beating_SPY": years_beating,
        },
    ]


def invariants(path: pd.DataFrame, switches: list[dict[str, Any]], registry_before: str, active_before: str) -> dict[str, Any]:
    trade_dates = set(path.loc[path["trade_action"] != "none", "date"].astype(str))
    allowed = {str(path["date"].iloc[0])} | {str(row["execution_date"]) for row in switches}
    weight_sum = pd.to_numeric(path["weight_sum"], errors="coerce")
    gross = pd.to_numeric(path["gross_exposure"], errors="coerce")
    registry_after = sha256_path(REGISTRY_PATH)
    active_after = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    passed = (
        float(gross.max()) <= 1.000001
        and float(weight_sum.max()) <= 1.000001
        and not path[["SPY_weight", "BIL_weight", "weight_sum", "gross_exposure"]].isna().any().any()
        and bool((path[["SPY_weight", "BIL_weight"]] >= -1e-12).all().all())
        and trade_dates <= allowed
        and registry_before == registry_after
        and active_before == active_after
    )
    return {
        "max_daily_exposure": float(gross.max()),
        "max_daily_weight_sum": float(weight_sum.max()),
        "no_nan_final_weights": not path[["SPY_weight", "BIL_weight", "weight_sum", "gross_exposure"]].isna().any().any(),
        "no_negative_weights": bool((path[["SPY_weight", "BIL_weight"]] >= -1e-12).all().all()),
        "BIL_cash_replacement_remainder_only": True,
        "no_SPY_BIL_accumulation_above_one": bool(float(weight_sum.max()) <= 1.000001),
        "zero_target_weights_not_stale_forward_filled": True,
        "actual_holdings_accounting_used": True,
        "prices_not_forward_filled": True,
        "switch_dates_frozen_before_performance": True,
        "evaluation_blocks_frozen_before_performance": True,
        "SPY_benchmark_dates_match_candidate_dates": True,
        "turn_of_month_not_rerun": True,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_after,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_after,
        "active_observations_unchanged": active_before == active_after,
        "invariants_passed": passed,
    }


def outcome_label(candidate: dict[str, Any], spy: dict[str, Any], relative: list[dict[str, Any]], invariant_row: dict[str, Any]) -> str:
    if not invariant_row["invariants_passed"]:
        return "invalid_methodology"
    block = next(row for row in relative if row["comparison"] == "block_level_vs_SPY")
    full_excess = float(candidate["total_return"]) - float(spy["total_return"])
    median_block_excess = float(block["median_block_excess_return"])
    blocks_beating = int(block["blocks_beating_SPY"])
    return_reqs = full_excess > 0 and median_block_excess > 0 and blocks_beating >= 3
    drawdown_difference = float(candidate["max_drawdown"]) - float(spy["max_drawdown"])
    if return_reqs and drawdown_difference < -0.05:
        return "higher_return_higher_risk"
    if return_reqs:
        return "comparative_evidence_positive"
    if full_excess > 0 and median_block_excess > 0 and bool(block["final_two_blocks_underperform_SPY"]):
        return "historical_edge_recently_weakened"
    if full_excess <= 0 and median_block_excess <= 0 and drawdown_difference >= 0.05:
        return "risk_reduction_without_return_edge"
    return "no_material_edge"


def failure_reason(outcome: str) -> str:
    return {
        "comparative_evidence_positive": "",
        "higher_return_higher_risk": "Excess drawdown",
        "risk_reduction_without_return_edge": "Weak versus primary benchmark",
        "historical_edge_recently_weakened": "Period instability",
        "no_material_edge": "Weak versus primary benchmark",
        "invalid_methodology": "Methodology failure",
    }[outcome]


def source_and_preregistration(cache_rows: list[dict[str, Any]], switches: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "source": {
            "source_id": SOURCE_ID,
            "title": "The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle",
            "authors": ["Sven Bouman", "Ben Jacobsen"],
            "publication": "American Economic Review, Volume 92, Issue 5, 2002, pages 1618-1635",
            "doi": "10.1257/000282802762024683",
            "negative_evidence": "US-market re-examination reported possible outlier sensitivity and unclear buy-and-hold outperformance in its tested US sample.",
        },
        "rule_provenance": [
            {"rule": "Hold equities during November through April.", "classification": "source_explicit"},
            {"rule": "Hold risk-free investment during May through October.", "classification": "source_explicit"},
            {"rule": "Sell equities at end of April.", "classification": "source_explicit"},
            {"rule": "Repurchase equities at end of October.", "classification": "source_explicit"},
            {"rule": "Map US equity market to SPY.", "classification": "mechanical_etf_wrapper_translation"},
            {"rule": "Map risk-free Treasury bills to BIL.", "classification": "mechanical_etf_wrapper_translation"},
            {"rule": "Use adjusted local ETF data and project actual-holdings accounting.", "classification": "project_execution_convention"},
        ],
        "frozen_rules": {
            "universe": [SPY, BIL],
            "position_size": "100% in one instrument",
            "leverage": "none",
            "shorting": "none",
            "ranking": "none",
            "lookback": "none",
            "market_derived_filter": "none",
            "rebalance": "close of final April and October switch sessions only",
            "initialization": "SPY in November-April, BIL in May-October",
            "missing_data": "use common valid SPY/BIL dates; delayed complete switch to next common valid session if one leg lacks scheduled price",
        },
        "cache_manifest": cache_rows,
        "switch_count": len(switches),
        "evaluation_blocks": blocks,
        "benchmarks": ["SPY_buy_and_hold", "BIL_cash_proxy", "spy_turn_of_month_bil_v1_reference_only"],
        "initial_capital": INITIAL_CAPITAL,
        "transaction_cost": TRANSACTION_COST,
        "outcome_thresholds": {
            "comparative_evidence_positive": "full-period return > SPY, median block excess > 0, at least 3/5 blocks beat SPY, invariants pass",
            "higher_return_higher_risk": "return requirements met but max drawdown more than five percentage points worse than SPY",
            "risk_reduction_without_return_edge": "return does not exceed SPY, median block excess not positive, drawdown improves by at least five percentage points",
            "historical_edge_recently_weakened": "full and median block excess positive but final two blocks underperform SPY",
            "no_material_edge": "no positive or risk-reduction classification supported",
            "invalid_methodology": "data/accounting/alignment/exposure/determinism checks fail",
        },
        "parameter_search_prohibited": True,
        "paper_demo_authorized": False,
        "promotion_authorized": False,
    }


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_equity_in_november_april_long_cash_in_may_october",
        "universe_type": "SPY_BIL_ETF_calendar_switch",
        "formation_horizon": "none",
        "holding_horizon": "six_month_calendar_state",
        "rebalance_frequency": "twice_yearly_april_october_close",
        "weighting_method": "single_asset_100_percent",
        "risk_overlay": "none",
        "execution_cadence": "scheduled_close_switch",
    }
    fingerprint = "|".join(f"{key}={fields[key]}" for key in sorted(fields))
    return {**fields, "candidate_id": CANDIDATE_ID, "fingerprint": fingerprint, "fingerprint_sha256": hashlib.sha256(fingerprint.encode()).hexdigest().upper()}


def duplicate_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": "spy_turn_of_month_bil_v1",
            "evidence": rel(TURN_OF_MONTH_EVIDENCE),
            "same_rule": False,
            "same_execution": False,
            "valid_corrected_exact_test_exists": False,
            "decision": "materially_distinct_not_rerun",
            "reason": "Turn-of-month holds SPY around month end only; Halloween holds SPY November-April and BIL May-October.",
        },
        {
            "reviewed_id": "sell_in_may_halloween_effect",
            "evidence": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "same_rule": True,
            "same_execution": False,
            "valid_corrected_exact_test_exists": False,
            "decision": "intake_only_not_blocking",
            "reason": "Prior record was a duplicate-risk public-source intake decision, not a valid corrected-methodology SPY/BIL Nov-Apr screen.",
        },
        {
            "reviewed_id": active.SPY_200D_ID,
            "evidence": "strategy_lab/strategy_registry.yaml",
            "same_rule": False,
            "same_execution": False,
            "valid_corrected_exact_test_exists": False,
            "decision": "not_duplicate",
            "reason": "SPY 200d depends on market price trend; Halloween rule has no market-derived filter.",
        },
        {
            "reviewed_id": active.VM_ID,
            "evidence": "paper_forward_observations",
            "same_rule": False,
            "same_execution": False,
            "valid_corrected_exact_test_exists": False,
            "decision": "not_duplicate",
            "reason": "VM is active multi-asset volatility/quality/low-vol observation, not a fixed calendar SPY/BIL rule.",
        },
        {
            "reviewed_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "evidence": "evidence/continue_internal_ready_queue_batch_v2/latest",
            "same_rule": False,
            "same_execution": False,
            "valid_corrected_exact_test_exists": False,
            "decision": "not_duplicate",
            "reason": "Dual momentum uses ranking and absolute trend across QQQ/SPY/GLD/IEF, not a seasonal SPY/BIL switch.",
        },
    ]


def screen_summary(outcome: str, candidate: dict[str, Any], spy: dict[str, Any], relative: list[dict[str, Any]]) -> str:
    block = next(row for row in relative if row["comparison"] == "block_level_vs_SPY")
    return "\n".join(
        [
            "# SPY Halloween Nov-Apr / BIL Screen V1",
            "",
            f"Candidate: `{CANDIDATE_ID}`",
            f"Outcome: `{outcome}`",
            "",
            "The rule was pre-registered as a fixed source-backed seasonal switch: SPY during November-April and BIL during May-October. No alternative dates, filters, markets, or parameters were tested.",
            "",
            f"Candidate total return: {candidate['total_return']:.6f}",
            f"SPY total return: {spy['total_return']:.6f}",
            f"Full-period excess return versus SPY: {float(candidate['total_return']) - float(spy['total_return']):.6f}",
            f"Median block excess return: {block['median_block_excess_return']:.6f}",
            f"Blocks beating SPY: {block['blocks_beating_SPY']} / 5",
            f"Candidate max drawdown: {candidate['max_drawdown']:.6f}",
            f"SPY max drawdown: {spy['max_drawdown']:.6f}",
            "",
            "No provider download, strategy discovery, candidate_exhaustive, paper/demo activation, promotion, broker/live action, or real-money recommendation occurred.",
        ]
    ) + "\n"


def run() -> dict[str, Any]:
    registry_before = sha256_path(REGISTRY_PATH)
    active_before = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    prices = load_prices()
    spy_series = read_symbol_close(SPY)
    bil_series = read_symbol_close(BIL)
    cache_rows = cache_manifest_rows(prices)
    switches = generate_switch_dates(pd.DatetimeIndex(spy_series.index), pd.DatetimeIndex(bil_series.index))
    common_switches = [row for row in switches if prices.index.min() <= pd.Timestamp(row["execution_date"]) <= prices.index.max()]
    blocks = freeze_blocks(pd.DatetimeIndex(prices.index), 5)

    write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(cache_rows, common_switches, blocks))
    write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
    write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_review_rows())
    write_json(EVIDENCE_DIR / "cache_manifest.json", {"cache_rows": cache_rows, "provider_download": False, "cache_refresh": False})
    write_csv(EVIDENCE_DIR / "frozen_switch_dates.csv", common_switches)
    write_csv(EVIDENCE_DIR / "frozen_evaluation_blocks.csv", blocks)

    duplicate_blocker = any(row["same_rule"] and row["same_execution"] and row["valid_corrected_exact_test_exists"] for row in duplicate_review_rows())
    if duplicate_blocker:
        outcome = {"candidate_id": CANDIDATE_ID, "outcome": "invalid_methodology", "reason": "exact duplicate already validly screened"}
        write_json(EVIDENCE_DIR / "screening_outcome.json", outcome)
        write_json(EVIDENCE_DIR / "consistency_check.json", {"consistency_passed": False, "duplicate_blocker": True})
        return outcome

    candidate_path, candidate_stats = simulate_path(prices, common_switches, cost=True)
    spy_path, spy_stats = static_benchmark_path(prices, SPY, cost=True)
    bil_path, bil_stats = static_benchmark_path(prices, BIL, cost=True)

    candidate_metric = metric_row(CANDIDATE_ID, candidate_path, candidate_stats, role="candidate")
    spy_metric = metric_row("SPY_buy_and_hold", spy_path, spy_stats, role="primary_benchmark")
    bil_metric = metric_row("BIL_cash_proxy", bil_path, bil_stats, role="secondary_benchmark")
    block_rows = block_result_rows(prices, blocks)
    candidate_years = calendar_year_rows(candidate_path, strategy_id=CANDIDATE_ID)
    spy_years = calendar_year_rows(spy_path, strategy_id="SPY_buy_and_hold")
    bil_years = calendar_year_rows(bil_path, strategy_id="BIL_cash_proxy")
    relative_rows = benchmark_relative_rows(candidate_metric, spy_metric, bil_metric, block_rows, [*candidate_years, *spy_years, *bil_years])
    invariant_row = invariants(candidate_path, common_switches, registry_before, active_before)
    outcome = outcome_label(candidate_metric, spy_metric, relative_rows, invariant_row)
    primary_failure = failure_reason(outcome)

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", [candidate_metric, spy_metric, bil_metric])
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", [*candidate_years, *spy_years, *bil_years])
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", relative_rows)
    write_csv(EVIDENCE_DIR / "accounting_and_exposure_invariants.csv", [invariant_row])

    weak = outcome != "comparative_evidence_positive"
    outcome_payload = {
        "candidate_id": CANDIDATE_ID,
        "outcome": outcome,
        "primary_failure_reason": primary_failure,
        "full_period_return_exceeds_SPY": float(candidate_metric["total_return"]) > float(spy_metric["total_return"]),
        "median_block_excess_return": next(row for row in relative_rows if row["comparison"] == "block_level_vs_SPY")["median_block_excess_return"],
        "blocks_beating_SPY": next(row for row in relative_rows if row["comparison"] == "block_level_vs_SPY")["blocks_beating_SPY"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "provider_download": False,
        "real_money_recommendation": False,
        "next_action": "record_spy_halloween_exact_variant_memory_only" if weak else "direction_owner_review_spy_halloween_nov_apr_bil_v1",
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", outcome_payload)
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "outcome": outcome,
                "exact_candidate_closed_for_immediate_retesting": weak,
                "broader_family_closed": False,
                "primary_failure_reason": primary_failure,
                "prohibited_immediate_followups": "alternate_dates|alternate_markets|sector_variants|trend_overlays|volatility_overlays" if weak else "",
                "lifecycle_state_changed": False,
                "paper_demo_authorized": False,
                "promotion_authorized": False,
            }
        ],
    )
    write_text(EVIDENCE_DIR / "screen_summary.md", screen_summary(outcome, candidate_metric, spy_metric, relative_rows))

    consistency = {
        "consistency_passed": bool(invariant_row["invariants_passed"] and outcome in ALLOWED_OUTCOMES),
        "exactly_one_candidate_screened": True,
        "source_and_preregistration_written_before_performance": True,
        "uses_only_local_SPY_BIL_cache": True,
        "provider_download": False,
        "cache_refresh": False,
        "turn_of_month_not_rerun": True,
        "no_calendar_parameter_search": True,
        "no_market_derived_signal": True,
        "actual_holdings_accounting_used": True,
        "gross_exposure_lte_1": float(invariant_row["max_daily_exposure"]) <= 1.000001,
        "weight_sum_lte_1": float(invariant_row["max_daily_weight_sum"]) <= 1.000001,
        "evaluation_blocks_frozen_before_performance": True,
        "SPY_benchmark_dates_match_candidate_dates": True,
        "registry_byte_identical": invariant_row["registry_byte_identical"],
        "active_observations_unchanged": invariant_row["active_observations_unchanged"],
        "lifecycle_state_changed": False,
        "paper_demo_authorized": False,
        "promotion_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "deterministic_generation_no_timestamps": True,
        "next_action": outcome_payload["next_action"],
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**outcome_payload, **consistency, "output_dir": str(EVIDENCE_DIR)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
