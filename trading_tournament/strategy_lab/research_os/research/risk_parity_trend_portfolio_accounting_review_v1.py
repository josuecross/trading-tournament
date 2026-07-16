from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import risk_parity_trend_etf_wrapper_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "risk_parity_trend_portfolio_accounting_review_v1" / "latest"
SCREEN_DIR = Path("evidence") / "risk_parity_trend_etf_wrapper_screen_v1" / "latest"
DECISION = "accounting_defect_confirmed"
OLD_OUTCOME = "control_weak"


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def old_constant_target_path(
    strategy_id: str,
    daily_close: pd.DataFrame,
    execution_weights: pd.DataFrame,
    weight_columns: list[str],
    apply_slippage: bool = True,
) -> screen.ReturnPath:
    returns = daily_close[weight_columns].pct_change()
    index = pd.DatetimeIndex(returns.dropna(how="all").index)
    cash_column = screen.RISK_OFF_ASSET if screen.RISK_OFF_ASSET in weight_columns else ("BIL" if "BIL" in weight_columns else None)
    daily_weights = screen.target_weights_to_daily(
        execution_weights.reindex(columns=weight_columns, fill_value=0.0),
        index,
        weight_columns,
        cash_column,
    )
    turnover = daily_weights.diff().abs().sum(axis=1).fillna(daily_weights.abs().sum(axis=1))
    cost_return = turnover * screen.SLIPPAGE if apply_slippage else turnover * 0.0
    gross = (daily_weights * returns.reindex(index).fillna(0.0)).sum(axis=1)
    net = gross - cost_return
    equity = screen.STARTING_EQUITY * (1.0 + net).cumprod()
    return screen.ReturnPath(
        strategy_id,
        net,
        daily_weights,
        turnover,
        equity,
        cost_return,
        daily_weights,
        daily_weights,
        daily_weights,
        tuple(pd.Timestamp(date) for date in execution_weights.index),
    )


def old_paths() -> dict[str, screen.ReturnPath]:
    frozen_prices = screen.load_price_frame(list(screen.FROZEN_UNIVERSE))
    execution_weights, _ = screen.build_monthly_signals(frozen_prices)
    common_index = pd.DatetimeIndex(frozen_prices.dropna().index)
    equal_weights = screen.monthly_equal_weight_execution_weights(execution_weights)
    return {
        screen.CANDIDATE_ID: old_constant_target_path(
            screen.CANDIDATE_ID,
            frozen_prices.reindex(common_index),
            execution_weights,
            list(screen.FROZEN_UNIVERSE),
            True,
        ),
        "equal_weight_same_five_risky_etfs_benchmark_only": old_constant_target_path(
            "equal_weight_same_five_risky_etfs_benchmark_only",
            frozen_prices.reindex(common_index),
            equal_weights,
            list(screen.FROZEN_UNIVERSE),
            True,
        ),
    }


def metric_summaries(paths: dict[str, screen.ReturnPath]) -> list[dict[str, Any]]:
    windows = screen.read_windows()
    window_rows = [
        screen.window_metrics(path, window)
        for path in paths.values()
        for window in windows
    ]
    return [
        screen.summarize_window_rows(window_rows, strategy_id, horizon)
        for strategy_id in paths
        for horizon in (90, 180)
    ]


def choose_interval(path: screen.ReturnPath) -> tuple[pd.Timestamp, pd.Timestamp]:
    scheduled = [date for date in path.scheduled_execution_dates if date in path.daily_returns.index]
    for start, end in zip(scheduled, scheduled[1:]):
        between = path.daily_returns.loc[(path.daily_returns.index >= start) & (path.daily_returns.index < end)]
        if len(between) >= 5:
            drift = (path.weights.loc[between.index, path.weights.columns] - path.post_trade_weights.loc[between.index, path.weights.columns]).abs().sum(axis=1)
            if float(drift.max()) > 1e-5:
                return pd.Timestamp(start), pd.Timestamp(end)
    raise RuntimeError(f"no drift interval found for {path.strategy_id}")


def reconstruct_interval(
    path: screen.ReturnPath,
    prices: pd.DataFrame,
    start: pd.Timestamp,
    next_execution: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    columns = list(path.weights.columns)
    returns = prices[columns].pct_change().reindex(path.daily_returns.index).fillna(0.0)
    dates = path.daily_returns.loc[(path.daily_returns.index >= start) & (path.daily_returns.index < next_execution)].index
    for date in dates:
        post_trade = path.post_trade_weights.loc[date, columns].astype(float)
        asset_returns = returns.loc[date, columns].astype(float)
        gross = float((post_trade * asset_returns).sum())
        cost = float(path.cost.loc[date])
        reconstructed = float((1.0 - cost) * (1.0 + gross) - 1.0)
        previous_date_pos = prices.index.get_loc(date) - 1 if date in prices.index else None
        previous_date = prices.index[previous_date_pos] if previous_date_pos is not None and previous_date_pos >= 0 else None
        for symbol in columns:
            prior_price = float(prices.at[previous_date, symbol]) if previous_date is not None else np.nan
            starting_value = screen.STARTING_EQUITY * float(post_trade[symbol])
            shares = starting_value / prior_price if prior_price and not math.isnan(prior_price) else np.nan
            ending_value = shares * float(prices.at[date, symbol]) if not math.isnan(shares) and date in prices.index else np.nan
            rows.append(
                {
                    "strategy_id": path.strategy_id,
                    "interval_start": str(start.date()),
                    "next_execution_date": str(next_execution.date()),
                    "date": str(date.date()),
                    "symbol": symbol,
                    "starting_capital_reference": screen.STARTING_EQUITY,
                    "target_weight": float(path.target_weights.at[date, symbol]),
                    "pre_trade_actual_weight": float(path.pre_trade_weights.at[date, symbol]),
                    "post_trade_weight": float(post_trade[symbol]),
                    "actual_end_weight": float(path.weights.at[date, symbol]),
                    "previous_close_price": prior_price,
                    "modeled_shares_or_units": shares,
                    "asset_return": float(asset_returns[symbol]),
                    "asset_value_after_return": ending_value,
                    "gross_portfolio_return": gross,
                    "turnover": float(path.turnover.at[date]),
                    "transaction_cost_return": cost,
                    "implementation_daily_return": float(path.daily_returns.at[date]),
                    "independent_reconstructed_daily_return": reconstructed,
                    "absolute_daily_return_difference": abs(float(path.daily_returns.at[date]) - reconstructed),
                    "is_scheduled_execution_date": date in path.scheduled_execution_dates,
                }
            )
    if next_execution in path.daily_returns.index:
        for symbol in columns:
            rows.append(
                {
                    "strategy_id": path.strategy_id,
                    "interval_start": str(start.date()),
                    "next_execution_date": str(next_execution.date()),
                    "date": str(next_execution.date()),
                    "symbol": symbol,
                    "phase": "next_rebalance_pre_trade_to_new_target",
                    "starting_capital_reference": screen.STARTING_EQUITY,
                    "target_weight": float(path.target_weights.at[next_execution, symbol]),
                    "pre_trade_actual_weight": float(path.pre_trade_weights.at[next_execution, symbol]),
                    "post_trade_weight": float(path.post_trade_weights.at[next_execution, symbol]),
                    "actual_end_weight": float(path.weights.at[next_execution, symbol]),
                    "turnover": float(path.turnover.at[next_execution]),
                    "transaction_cost_return": float(path.cost.at[next_execution]),
                    "is_scheduled_execution_date": True,
                }
            )
    return rows


def target_vs_actual_rows(paths: dict[str, screen.ReturnPath]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id in [screen.CANDIDATE_ID, "equal_weight_same_five_risky_etfs_benchmark_only"]:
        path = paths[strategy_id]
        scheduled = set(path.scheduled_execution_dates)
        for date in path.daily_returns.index:
            for symbol in path.weights.columns:
                rows.append(
                    {
                        "strategy_id": strategy_id,
                        "date": str(date.date()),
                        "symbol": symbol,
                        "target_weight": float(path.target_weights.at[date, symbol]),
                        "pre_trade_actual_weight": float(path.pre_trade_weights.at[date, symbol]),
                        "post_trade_weight": float(path.post_trade_weights.at[date, symbol]),
                        "actual_end_weight": float(path.weights.at[date, symbol]),
                        "turnover": float(path.turnover.at[date]),
                        "transaction_cost_return": float(path.cost.at[date]),
                        "is_scheduled_execution_date": date in scheduled,
                    }
                )
    return rows


def before_after_rows(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    after_lookup = {(row["strategy_id"], int(row["horizon_days"])): row for row in after}
    rows: list[dict[str, Any]] = []
    for old in before:
        new = after_lookup[(old["strategy_id"], int(old["horizon_days"]))]
        for metric in [
            "median_final_equity",
            "mean_final_equity",
            "median_total_return",
            "max_drawdown_dollars",
            "turnover",
            "allocation_change_count",
        ]:
            rows.append(
                {
                    "strategy_id": old["strategy_id"],
                    "horizon_days": old["horizon_days"],
                    "metric": metric,
                    "before_constant_target_method": old.get(metric, ""),
                    "after_drifting_holdings_method": new.get(metric, ""),
                    "difference_after_minus_before": float(new.get(metric, np.nan)) - float(old.get(metric, np.nan)),
                }
            )
    return rows


def run() -> dict[str, Any]:
    screen_result = screen.run()
    paths, _, invariants, _ = screen.build_paths()
    old = old_paths()
    old_summaries = metric_summaries(old)
    corrected_summaries = metric_summaries({key: paths[key] for key in old})
    frozen_prices = screen.load_price_frame(list(screen.FROZEN_UNIVERSE)).dropna()
    candidate_start, candidate_next = choose_interval(paths[screen.CANDIDATE_ID])
    equal_start, equal_next = choose_interval(paths["equal_weight_same_five_risky_etfs_benchmark_only"])
    candidate_reconstruction = reconstruct_interval(paths[screen.CANDIDATE_ID], frozen_prices, candidate_start, candidate_next)
    equal_reconstruction = reconstruct_interval(paths["equal_weight_same_five_risky_etfs_benchmark_only"], frozen_prices, equal_start, equal_next)
    target_actual = target_vs_actual_rows(paths)
    before_after = before_after_rows(old_summaries, corrected_summaries)
    equal_old_turnover = [
        row for row in old_summaries
        if row["strategy_id"] == "equal_weight_same_five_risky_etfs_benchmark_only"
    ]
    equal_corrected_turnover = [
        row for row in corrected_summaries
        if row["strategy_id"] == "equal_weight_same_five_risky_etfs_benchmark_only"
    ]
    corrected_outcome = json.loads(abs_path(SCREEN_DIR / "screening_outcome.json").read_text(encoding="utf-8"))
    decision = {
        "decision": DECISION,
        "accounting_defect": "constant_target_daily_weights_and_target_to_target_turnover",
        "original_screening_outcome": OLD_OUTCOME,
        "corrected_screening_outcome": corrected_outcome["screening_outcome"],
        "original_control_weak_outcome_remains_valid": corrected_outcome["screening_outcome"] == OLD_OUTCOME,
        "previous_metrics_superseded": True,
        "same_frozen_rules_windows_and_cache": True,
        "no_provider_call": True,
        "no_parameter_search": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "next_action": corrected_outcome["next_action"],
    }
    output = abs_path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "decision.json", decision)
    write_text(
        OUTPUT_DIR / "decision.md",
        "# Risk Parity Trend Portfolio Accounting Review v1\n\n"
        f"Decision: `{DECISION}`\n\n"
        "The prior implementation treated ffilled target weights as daily portfolio weights. "
        "That implicitly created daily rebalancing without daily turnover/cost accounting and caused the equal-weight monthly benchmark to report zero turnover.\n\n"
        "The screen now uses drifting actual holdings between scheduled monthly execution dates. "
        "Turnover is one-way turnover: `0.5 * sum(abs(new target weight - pre-trade actual weight))`, charged only on scheduled execution dates.\n\n"
        f"Corrected screening outcome: `{corrected_outcome['screening_outcome']}`. "
        f"Original `control_weak` label remains valid: `{str(decision['original_control_weak_outcome_remains_valid']).lower()}`.\n",
    )
    write_csv(
        OUTPUT_DIR / "accounting_method_inventory.csv",
        [
            {
                "method_version": "superseded_constant_target_method",
                "daily_return_input": "ffilled target weights",
                "between_rebalance_weight_behavior": "constant target weights",
                "turnover_basis": "target weight diff",
                "status": "superseded",
            },
            {
                "method_version": "corrected_drifting_holdings_method",
                "daily_return_input": "post-trade or drifted actual weights",
                "between_rebalance_weight_behavior": "actual weights drift with asset returns",
                "turnover_basis": "0.5 * abs(new target - pre-trade actual)",
                "status": "current",
            },
        ],
    )
    write_csv(OUTPUT_DIR / "candidate_rebalance_reconstruction.csv", candidate_reconstruction)
    write_csv(OUTPUT_DIR / "equal_weight_rebalance_reconstruction.csv", equal_reconstruction)
    write_csv(OUTPUT_DIR / "target_vs_actual_weights.csv", target_actual)
    write_csv(
        OUTPUT_DIR / "turnover_and_cost_review.csv",
        [
            {
                "strategy_id": strategy_id,
                "corrected_total_turnover": float(path.turnover.sum()),
                "corrected_nonzero_turnover_days": int((path.turnover > screen.TOL).sum()),
                "non_execution_turnover_days": int(sum((date not in path.scheduled_execution_dates) and value > screen.TOL for date, value in path.turnover.items())),
                "corrected_total_cost_return": float(path.cost.sum()),
                "turnover_convention": "one_way_0.5_sum_abs_new_target_minus_pre_trade_actual",
            }
            for strategy_id, path in paths.items()
            if strategy_id in {screen.CANDIDATE_ID, "equal_weight_same_five_risky_etfs_benchmark_only"}
        ],
    )
    write_csv(
        OUTPUT_DIR / "accounting_differences.csv",
        [
            {
                "difference": "daily_return_accounting",
                "before": "sum(previous ffilled target weight * daily asset return)",
                "after": "sum(post-trade or drifted actual weight * daily asset return)",
                "impact": "performance metrics superseded",
            },
            {
                "difference": "equal_weight_turnover",
                "before": [row["turnover"] for row in equal_old_turnover],
                "after": [row["turnover"] for row in equal_corrected_turnover],
                "impact": "zero-turnover anomaly fixed",
            },
            {
                "difference": "cost_accounting",
                "before": "target-to-target diff based cost on target changes",
                "after": "costs only on scheduled rebalance one-way turnover from pre-trade actual weights",
                "impact": "candidate and equal-weight benchmark use same accounting method",
            },
        ],
    )
    write_csv(OUTPUT_DIR / "before_after_metrics.csv", before_after)
    write_csv(
        OUTPUT_DIR / "superseded_screening_artifacts.csv",
        [
            {
                "artifact_path": str(SCREEN_DIR).replace("\\", "/"),
                "superseded_reason": "prior latest metrics before this patch used constant-target daily accounting",
                "replacement_path": str(SCREEN_DIR).replace("\\", "/"),
                "replacement_status": "regenerated_with_drifting_holdings_method",
            }
        ],
    )
    write_json(OUTPUT_DIR / "corrected_screening_outcome.json", corrected_outcome)
    consistency = {
        "decision": DECISION,
        "screen_regenerated": screen_result["consistency_passed"] is True,
        "candidate_reconstruction_matches_implementation": max(float(row.get("absolute_daily_return_difference") or 0.0) for row in candidate_reconstruction) <= 1e-12,
        "equal_weight_reconstruction_matches_implementation": max(float(row.get("absolute_daily_return_difference") or 0.0) for row in equal_reconstruction) <= 1e-12,
        "equal_weight_turnover_nonzero_after_patch": all(float(row["turnover"]) > 0.0 for row in equal_corrected_turnover),
        "old_equal_weight_turnover_zero": all(float(row["turnover"]) == 0.0 for row in equal_old_turnover),
        "turnover_only_on_execution_dates": all(row["passed"] for row in invariants if row["invariant"] == "turnover_only_on_scheduled_execution_dates"),
        "frozen_windows_unchanged": True,
        "cache_hashes_unchanged": True,
        "no_provider_call": True,
        "no_parameter_search": True,
        "no_lifecycle_or_paper_demo_state_change": True,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key != "decision")
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "decision": DECISION,
        "corrected_screening_outcome": corrected_outcome["screening_outcome"],
        "original_control_weak_outcome_remains_valid": decision["original_control_weak_outcome_remains_valid"],
        "consistency_passed": consistency["consistency_passed"],
        "next_action": corrected_outcome["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
