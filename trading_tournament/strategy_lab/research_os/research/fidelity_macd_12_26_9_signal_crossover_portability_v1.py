from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    COST_RATE,
    FROZEN_UNIVERSE_PATH,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    data_hash,
    load_adjusted_ohlcv,
    metrics_from_returns,
    price_frame,
    turnover_series,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


TASK_ID = "fidelity_macd_12_26_9_signal_crossover_portability_v1"
STRATEGY_ID = "fidelity_macd_12_26_9_signal_crossover_etf_bil_v1"
FAMILY_ID = "macd_signal_line_trend_timing"
SOURCE_ID = "fidelity_macd_12_26_9_signal_crossover"
OUTPUT_DIR = Path("evidence") / "fast_progress" / TASK_ID / "latest"
NEXT_ACTION = "direction_owner_review_fidelity_macd_fast_lane_v1"
COMPATIBILITY_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_instrument_strategy_compatibility_v1"
    / "instrument_family_compatibility.csv"
)
UNIVERSE_MARKET_DATA_MANIFEST = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_market_data_freeze_v1"
    / "market_data_freeze_manifest.yaml"
)
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
SELECTED_COMPATIBILITY_FAMILY = "own_return_trend_long_cash"
FAST_EMA_PERIOD = 12
SLOW_EMA_PERIOD = 26
SIGNAL_EMA_PERIOD = 9
MAX_TRIALS = 6
MIN_HISTORY_DAYS = 504
WEIGHT_TOLERANCE = 1e-6

VALID_ROW_OUTCOMES = {
    "row_control_strong",
    "row_timeframe_fragile",
    "row_control_weak",
    "row_cost_fragile",
    "insufficient_history",
    "implementation_or_accounting_defect",
}
VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "family_implementation_defect",
}
VALID_TASK_OUTCOMES = {
    "macd_fast_lane_batch_complete",
    "frozen_universe_or_compatibility_missing",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
CORE_FILES = [
    "source_packet_used.yaml",
    "repository_fit_check.json",
    "frozen_universe_reference.json",
    "frozen_trial_manifest.csv",
    "canonical_family_representative.json",
    "trial_registry.csv",
    "data_coverage.csv",
    "ema_initialization_audit.csv",
    "signal_calculation_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "control_metrics.csv",
    "baseline_vs_controls.csv",
    "timeframe_diagnostics.csv",
    "accounting_invariants.csv",
    "row_outcomes.csv",
    "family_outcome.json",
    "family_followup_queue.csv",
]


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def deterministic_core_hash(evidence_dir: Path) -> str:
    return data_hash(
        {name: (evidence_dir / name).read_text(encoding="utf-8") if (evidence_dir / name).exists() else "missing" for name in CORE_FILES}
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def compound_return(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float((1.0 + series.fillna(0.0)).prod() - 1.0)


def source_packet() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_name": "Fidelity MACD 12/26/9 signal crossover",
        "source_type": "direction_owner_supplied_public_source_rule_packet",
        "research_status": "exploratory_non_promotable",
        "parameters": {"fast_ema_period": FAST_EMA_PERIOD, "slow_ema_period": SLOW_EMA_PERIOD, "signal_ema_period": SIGNAL_EMA_PERIOD},
        "rules": {
            "macd": "ema_12_adjusted_close - ema_26_adjusted_close",
            "signal": "ema_9_of_macd",
            "bullish_crossover": "macd_t_minus_1 <= signal_t_minus_1 and macd_t > signal_t",
            "bearish_crossover": "macd_t_minus_1 >= signal_t_minus_1 and macd_t < signal_t",
            "otherwise": "retain previously established state",
            "pre_initialization": "no position before first valid bullish or bearish crossover after signal line exists",
        },
        "ema_initialization": {
            "fast_ema_seed": "simple average of first 12 valid adjusted closes",
            "slow_ema_seed": "simple average of first 26 valid adjusted closes",
            "signal_seed": "simple average of first 9 valid MACD observations",
        },
        "forbidden_rules": [
            "macd_histogram_sign",
            "macd_zero_line_crossing",
            "divergence",
            "alternative_ema_periods",
            "confirmation_filters",
            "stops",
            "volatility_conditions",
            "momentum_ranking",
        ],
    }


def frozen_universe(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / FROZEN_UNIVERSE_PATH)


def compatibility_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / COMPATIBILITY_PATH)


def choose_instruments(root: Path, universe_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    compatible_symbols = {
        row["symbol"]
        for row in compatibility_rows(root)
        if row.get("family_id") == SELECTED_COMPATIBILITY_FAMILY
        and row.get("compatibility_label") == "compatible_with_frozen_cash_proxy"
    }
    ordered = [
        row
        for row in universe_rows
        if row.get("symbol")
        and row["symbol"] != "BIL"
        and row["symbol"] in compatible_symbols
        and row.get("product_structure", "").lower() not in {"inverse_etf", "leveraged_etf"}
    ]
    selected: list[dict[str, str]] = []
    seen_groups: set[str] = set()
    group_counts: dict[str, int] = {}
    for row in ordered:
        group = row.get("candidate_group", "")
        if group in seen_groups:
            continue
        selected.append(row)
        seen_groups.add(group)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(selected) >= MAX_TRIALS:
            return selected
    for row in ordered:
        if row in selected:
            continue
        group = row.get("candidate_group", "")
        if group_counts.get(group, 0) >= 2:
            continue
        selected.append(row)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(selected) >= MAX_TRIALS:
            break
    return selected


def sma_seeded_ema(series: pd.Series, period: int) -> pd.Series:
    values = series.astype(float).dropna()
    out = pd.Series(float("nan"), index=series.index, dtype=float)
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    seed_index = values.index[period - 1]
    previous = float(values.iloc[:period].mean())
    out.loc[seed_index] = previous
    for date, value in values.iloc[period:].items():
        previous = alpha * float(value) + (1.0 - alpha) * previous
        out.loc[date] = previous
    return out


def macd_components(close: pd.Series) -> pd.DataFrame:
    fast = sma_seeded_ema(close, FAST_EMA_PERIOD)
    slow = sma_seeded_ema(close, SLOW_EMA_PERIOD)
    macd = (fast - slow).where(fast.notna() & slow.notna())
    signal = sma_seeded_ema(macd.dropna(), SIGNAL_EMA_PERIOD).reindex(close.index)
    return pd.DataFrame({"ema_fast": fast, "ema_slow": slow, "macd": macd, "signal": signal}, index=close.index)


def crossover_events(macd: pd.Series, signal: pd.Series) -> pd.DataFrame:
    previous_valid = macd.shift(1).notna() & signal.shift(1).notna()
    current_valid = macd.notna() & signal.notna()
    bullish = previous_valid & current_valid & (macd.shift(1) <= signal.shift(1)) & (macd > signal)
    bearish = previous_valid & current_valid & (macd.shift(1) >= signal.shift(1)) & (macd < signal)
    both = bullish & bearish
    bullish = bullish & ~both
    bearish = bearish & ~both
    return pd.DataFrame({"bullish_cross": bullish.fillna(False), "bearish_cross": bearish.fillna(False)}, index=macd.index)


def targets_from_events(symbol: str, events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    state = "uninitialized"
    for date, row in events.iterrows():
        if bool(row.get("bullish_cross", False)):
            state = "risky"
        elif bool(row.get("bearish_cross", False)):
            state = "bil"
        if state == "risky":
            risky_weight, bil_weight = 1.0, 0.0
        elif state == "bil":
            risky_weight, bil_weight = 0.0, 1.0
        else:
            risky_weight, bil_weight = 0.0, 0.0
        rows.append({"date": date, symbol: risky_weight, "BIL": bil_weight, "state": state})
    return pd.DataFrame(rows).set_index("date")


def macd_targets(symbol: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    components = macd_components(frame["adj_close"])
    events = crossover_events(components["macd"], components["signal"])
    targets = targets_from_events(symbol, events)
    weights = targets[[symbol, "BIL"]].astype(float)
    initialized = targets["state"] != "uninitialized"
    active = weights[symbol] > 0.5
    bil = weights["BIL"] > 0.5
    previous_active = active.shift(1, fill_value=False)
    previous_bil = bil.shift(1, fill_value=False)
    first_target_date = initialized[initialized].index.min() if bool(initialized.any()) else pd.NaT
    audit = pd.concat([components, events, targets[["state"]]], axis=1)
    return weights, audit, {
        "first_fast_ema_date": components["ema_fast"].first_valid_index(),
        "first_slow_ema_date": components["ema_slow"].first_valid_index(),
        "first_macd_date": components["macd"].first_valid_index(),
        "first_signal_date": components["signal"].first_valid_index(),
        "first_target_date": first_target_date,
        "bullish_cross_count": int(events["bullish_cross"].sum()),
        "bearish_cross_count": int(events["bearish_cross"].sum()),
        "entry_count": int((active & ~previous_active).sum()),
        "exit_count": int((bil & ~previous_bil).sum()),
        "pre_target_position_count": int((~initialized & (weights.sum(axis=1).abs() > WEIGHT_TOLERANCE)).sum()),
        "valid_signal_rows": int(components["signal"].notna().sum()),
        "audit": audit,
    }


def split_timeframe(baseline: pd.Series, control: pd.Series) -> dict[str, Any]:
    aligned = pd.concat([baseline.rename("baseline"), control.rename("control")], axis=1).dropna()
    if len(aligned) < 60:
        return {
            "first_half_valid": False,
            "second_half_valid": False,
            "first_half_start_date": "",
            "first_half_end_date": "",
            "second_half_start_date": "",
            "second_half_end_date": "",
            "first_half_excess_vs_primary_control": float("nan"),
            "second_half_excess_vs_primary_control": float("nan"),
        }
    midpoint = len(aligned) // 2
    first = aligned.iloc[:midpoint]
    second = aligned.iloc[midpoint:]
    return {
        "first_half_valid": len(first) >= 30,
        "second_half_valid": len(second) >= 30,
        "first_half_start_date": first.index.min().date().isoformat(),
        "first_half_end_date": first.index.max().date().isoformat(),
        "second_half_start_date": second.index.min().date().isoformat(),
        "second_half_end_date": second.index.max().date().isoformat(),
        "first_half_excess_vs_primary_control": compound_return(first["baseline"]) - compound_return(first["control"]),
        "second_half_excess_vs_primary_control": compound_return(second["baseline"]) - compound_return(second["control"]),
    }


def coverage_row(root: Path, symbol: str, row: dict[str, str]) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    path = "" if frame.empty else str(frame["source_cache_path"].iloc[0])
    return {
        "symbol": symbol,
        "candidate_group": row.get("candidate_group", ""),
        "primary_economic_exposure": row.get("primary_economic_exposure", ""),
        "cache_ready": not frame.empty and len(frame) >= MIN_HISTORY_DAYS,
        "rows": int(len(frame)),
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "has_adjusted_ohlcv": not frame.empty,
        "cache_path": path,
        "cache_file_hash": file_hash(root / path) if path else "missing",
    }


def transaction_rows(trial_id: str, strategy_id: str, symbol: str, weights: pd.DataFrame) -> list[dict[str, Any]]:
    turnover = turnover_series(weights)
    rows = []
    for date, value in turnover[turnover > WEIGHT_TOLERANCE].items():
        rows.append(
            {
                "trial_id": trial_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "signal_date": pd.Timestamp(date).date().isoformat(),
                "execution_convention": "next_eligible_session_via_shifted_weights",
                "turnover_proxy": float(value),
                "cost_rate": COST_RATE,
                "cost_return_deduction": float(value) * COST_RATE,
                "cost_applied_once_for_state_change": True,
            }
        )
    return rows


def evaluate_trial(
    root: Path,
    instrument: dict[str, str],
    bil_frame: pd.DataFrame,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    symbol = instrument["symbol"]
    trial_id = f"{STRATEGY_ID}__{symbol}"
    frame = load_adjusted_ohlcv(root, symbol)
    if frame.empty or len(frame) < MIN_HISTORY_DAYS:
        row = {
            "trial_id": trial_id,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "row_outcome_allowed": True,
            "failure_reason": "missing_or_short_adjusted_ohlcv_cache",
            "numeric_result_interpretable": False,
            "instrument_rows_counted_as_independent_strategies": False,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        return row, [], [], {}, {}, {}, row, [], [], []

    prices = price_frame(frame, bil_frame, symbol)
    frame = frame.reindex(prices.index).dropna(subset=["open", "high", "low", "close", "adj_close", "volume"])
    prices = prices.reindex(frame.index).dropna()
    if len(prices) < MIN_HISTORY_DAYS:
        row = {
            "trial_id": trial_id,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "row_outcome_allowed": True,
            "failure_reason": "missing_common_symbol_bil_history",
            "numeric_result_interpretable": False,
            "instrument_rows_counted_as_independent_strategies": False,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        return row, [], [], {}, {}, {}, row, [], [], []

    weights, signal_audit, signal_meta = macd_targets(symbol, frame)
    weights = weights.reindex(prices.index).fillna(0.0).reindex(columns=[symbol, "BIL"], fill_value=0.0)
    zero_cost = returns_from_weights(prices, weights).rename("zero_cost_return")
    costs = turnover_series(weights).reindex(zero_cost.index).fillna(0.0) * COST_RATE
    baseline = (zero_cost - costs).rename("baseline_return_after_cost")
    risky_returns = prices[symbol].pct_change(fill_method=None).fillna(0.0).rename("risky_buy_hold")
    bil_returns = prices["BIL"].pct_change(fill_method=None).fillna(0.0).rename("BIL_cash")
    avg_exposure = float(weights[symbol].mean())
    static_weights = pd.DataFrame({symbol: avg_exposure, "BIL": 1.0 - avg_exposure}, index=prices.index)
    static_returns = returns_from_weights(prices, static_weights).rename("static_average_exposure_control")

    base_metrics = metrics_from_returns(baseline)
    zero_metrics = metrics_from_returns(zero_cost)
    risky_metrics = metrics_from_returns(risky_returns)
    bil_metrics = metrics_from_returns(bil_returns)
    static_metrics = metrics_from_returns(static_returns)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    initialized = weights.sum(axis=1) > WEIGHT_TOLERANCE
    post = weights.loc[initialized]
    post_sum_ok = bool(post.empty) or bool(((post.sum(axis=1) - 1.0).abs() <= WEIGHT_TOLERANCE).all())
    exclusive_ok = bool(((weights[symbol] > WEIGHT_TOLERANCE) & (weights["BIL"] > WEIGHT_TOLERANCE)).sum() == 0)
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and int(invariant["impossible_cash_and_risky_exposure_days"]) == 0
        and post_sum_ok
        and exclusive_ok
        and int(signal_meta["pre_target_position_count"]) == 0
    )
    timeframe = split_timeframe(baseline, risky_returns)
    after_cost_pass_controls = base_metrics["total_return"] > risky_metrics["total_return"] and base_metrics["total_return"] > static_metrics["total_return"]
    zero_cost_pass_controls = zero_metrics["total_return"] > risky_metrics["total_return"] and zero_metrics["total_return"] > static_metrics["total_return"]
    halves_pass = (
        bool(timeframe["first_half_valid"])
        and bool(timeframe["second_half_valid"])
        and as_float(timeframe["first_half_excess_vs_primary_control"]) >= 0.0
        and as_float(timeframe["second_half_excess_vs_primary_control"]) >= 0.0
    )
    if not invariant_pass:
        row_outcome = "implementation_or_accounting_defect"
        failure_reason = "exposure_or_signal_invariant_failure"
    elif zero_cost_pass_controls and not after_cost_pass_controls:
        row_outcome = "row_cost_fragile"
        failure_reason = "standard_cost_erases_control_edge"
    elif after_cost_pass_controls and halves_pass:
        row_outcome = "row_control_strong"
        failure_reason = "none"
    elif after_cost_pass_controls:
        row_outcome = "row_timeframe_fragile"
        failure_reason = "full_period_controls_pass_but_existing_half_negative"
    else:
        row_outcome = "row_control_weak"
        failure_reason = "after_cost_baseline_fails_required_full_period_control"

    trades, turnover_proxy = trade_count_and_turnover(weights)
    baseline_row = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "symbol": symbol,
        "candidate_group": instrument.get("candidate_group", ""),
        "primary_economic_exposure": instrument.get("primary_economic_exposure", ""),
        "fast_ema_period": FAST_EMA_PERIOD,
        "slow_ema_period": SLOW_EMA_PERIOD,
        "signal_ema_period": SIGNAL_EMA_PERIOD,
        "start_date": base_metrics["start_date"],
        "end_date": base_metrics["end_date"],
        "trading_days": base_metrics["trading_days"],
        "total_return": base_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "cagr": base_metrics["cagr"],
        "max_drawdown": base_metrics["max_drawdown"],
        "volatility": base_metrics["volatility"],
        "return_drawdown_proxy": base_metrics["return_drawdown_proxy"],
        "average_risky_exposure": avg_exposure,
        "average_bil_exposure": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover_proxy,
        "bullish_cross_count": signal_meta["bullish_cross_count"],
        "bearish_cross_count": signal_meta["bearish_cross_count"],
        "entry_count": signal_meta["entry_count"],
        "exit_count": signal_meta["exit_count"],
        "valid_signal_rows": signal_meta["valid_signal_rows"],
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "primary_control_total_return": risky_metrics["total_return"],
        "static_exposure_control_total_return": static_metrics["total_return"],
        "excess_return_vs_primary_control_after_cost": base_metrics["total_return"] - risky_metrics["total_return"],
        "excess_return_vs_static_exposure_control_after_cost": base_metrics["total_return"] - static_metrics["total_return"],
        "row_outcome": row_outcome,
        "failure_reason": failure_reason,
        "numeric_result_interpretable": True,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    controls = []
    for control_id, metrics in [
        ("risky_buy_hold", risky_metrics),
        ("BIL_buy_hold", bil_metrics),
        ("static_average_exposure_control", static_metrics),
        ("macd_zero_cost_accounting_diagnostic", zero_metrics),
    ]:
        controls.append(
            {
                "trial_id": trial_id,
                "strategy_id": STRATEGY_ID,
                "symbol": symbol,
                "control_id": control_id,
                **metrics,
                "performance_selected_control": False,
            }
        )
    invariant_row = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "symbol": symbol,
        **invariant,
        "post_initialization_weight_sum_exact_1": post_sum_ok,
        "only_risky_or_bil_held": exclusive_ok,
        "pre_first_crossover_no_position": int(signal_meta["pre_target_position_count"]) == 0,
        "exposure_invariant_pass": invariant_pass,
        "same_bar_execution_impossible": True,
        "no_lookahead_status": "shifted_weight_returns_from_completed_daily_bars",
        "cost_accounting_status": "5bps_turnover_cost_once_per_state_change",
        "static_control_same_calendar": True,
    }
    vs_row = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "symbol": symbol,
        "baseline_total_return_after_cost": base_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "risky_buy_hold_total_return": risky_metrics["total_return"],
        "BIL_buy_hold_total_return": bil_metrics["total_return"],
        "static_average_exposure_control_total_return": static_metrics["total_return"],
        "after_cost_beats_primary_control": base_metrics["total_return"] > risky_metrics["total_return"],
        "after_cost_beats_static_control": base_metrics["total_return"] > static_metrics["total_return"],
        "zero_cost_beats_primary_control": zero_metrics["total_return"] > risky_metrics["total_return"],
        "zero_cost_beats_static_control": zero_metrics["total_return"] > static_metrics["total_return"],
    }
    timeframe_row = {"trial_id": trial_id, "strategy_id": STRATEGY_ID, "symbol": symbol, **timeframe, "timeframe_diagnostic_not_holdout": True}
    outcome_row = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "symbol": symbol,
        "candidate_group": instrument.get("candidate_group", ""),
        "row_outcome": row_outcome,
        "row_outcome_allowed": row_outcome in VALID_ROW_OUTCOMES,
        "failure_reason": failure_reason,
        "instrument_rows_counted_as_independent_strategies": False,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    first_fast = signal_meta["first_fast_ema_date"]
    first_slow = signal_meta["first_slow_ema_date"]
    first_macd = signal_meta["first_macd_date"]
    first_signal = signal_meta["first_signal_date"]
    first_target = signal_meta["first_target_date"]
    close = frame["adj_close"]
    ema_audit = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "symbol": symbol,
        "fast_ema_period": FAST_EMA_PERIOD,
        "slow_ema_period": SLOW_EMA_PERIOD,
        "signal_ema_period": SIGNAL_EMA_PERIOD,
        "first_fast_ema_date": first_fast.date().isoformat() if pd.notna(first_fast) else "",
        "first_slow_ema_date": first_slow.date().isoformat() if pd.notna(first_slow) else "",
        "first_macd_date": first_macd.date().isoformat() if pd.notna(first_macd) else "",
        "first_signal_date": first_signal.date().isoformat() if pd.notna(first_signal) else "",
        "first_target_date": first_target.date().isoformat() if pd.notna(first_target) else "",
        "fast_seed_value": float(signal_audit.loc[first_fast, "ema_fast"]) if pd.notna(first_fast) else float("nan"),
        "fast_seed_sma": float(close.iloc[:FAST_EMA_PERIOD].mean()) if len(close) >= FAST_EMA_PERIOD else float("nan"),
        "slow_seed_value": float(signal_audit.loc[first_slow, "ema_slow"]) if pd.notna(first_slow) else float("nan"),
        "slow_seed_sma": float(close.iloc[:SLOW_EMA_PERIOD].mean()) if len(close) >= SLOW_EMA_PERIOD else float("nan"),
        "fast_seed_matches_sma": bool(pd.notna(first_fast)) and abs(float(signal_audit.loc[first_fast, "ema_fast"]) - float(close.iloc[:FAST_EMA_PERIOD].mean())) <= 1e-12,
        "slow_seed_matches_sma": bool(pd.notna(first_slow)) and abs(float(signal_audit.loc[first_slow, "ema_slow"]) - float(close.iloc[:SLOW_EMA_PERIOD].mean())) <= 1e-12,
        "pre_first_crossover_target_weight_sum": float(weights.loc[:first_target].iloc[:-1].sum(axis=1).abs().sum()) if pd.notna(first_target) else 0.0,
    }
    signal_row = {
        "trial_id": trial_id,
        "strategy_id": STRATEGY_ID,
        "symbol": symbol,
        "bullish_cross_count": signal_meta["bullish_cross_count"],
        "bearish_cross_count": signal_meta["bearish_cross_count"],
        "crossovers_are_transition_events": True,
        "histogram_zero_line_divergence_or_filter_used": False,
        "state_persists_without_crossover": True,
        "valid_signal_rows": signal_meta["valid_signal_rows"],
        "first_target_date": first_target.date().isoformat() if pd.notna(first_target) else "",
    }
    target_rows = []
    for date, weight_row in weights.iterrows():
        audit = signal_audit.loc[date]
        target_rows.append(
            {
                "trial_id": trial_id,
                "strategy_id": STRATEGY_ID,
                "symbol": symbol,
                "date": pd.Timestamp(date).date().isoformat(),
                "risky_weight": float(weight_row[symbol]),
                "bil_weight": float(weight_row["BIL"]),
                "weight_sum": float(weight_row[symbol] + weight_row["BIL"]),
                "state": audit["state"],
                "macd": audit["macd"],
                "signal": audit["signal"],
                "bullish_cross": bool(audit["bullish_cross"]),
                "bearish_cross": bool(audit["bearish_cross"]),
            }
        )
    return (
        baseline_row,
        controls,
        transaction_rows(trial_id, STRATEGY_ID, symbol, weights),
        invariant_row,
        vs_row,
        timeframe_row,
        outcome_row,
        [ema_audit],
        [signal_row],
        target_rows,
    )


def family_outcome(instruments: list[dict[str, str]], row_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    canonical_symbol = instruments[0]["symbol"] if instruments else ""
    by_symbol = {row["symbol"]: row for row in row_outcomes}
    canonical = by_symbol.get(canonical_symbol, {})
    portability = [row for row in row_outcomes if row["symbol"] != canonical_symbol]
    strong_portability = [row for row in portability if row["row_outcome"] == "row_control_strong" and row["candidate_group"] != instruments[0].get("candidate_group", "")]
    canonical_outcome = canonical.get("row_outcome", "")
    if canonical_outcome == "row_control_strong" and strong_portability:
        outcome = "family_exploratory_followup_candidate"
        reason = "canonical_and_distinct_portability_rows_control_strong"
    elif canonical_outcome == "row_timeframe_fragile":
        outcome = "family_timeframe_fragile"
        reason = "canonical_full_period_success_not_preserved_across_existing_halves"
    elif canonical_outcome == "row_cost_fragile":
        outcome = "family_cost_fragile"
        reason = "canonical_zero_cost_pass_not_preserved_after_5bps_cost"
    elif canonical_outcome == "implementation_or_accounting_defect":
        outcome = "family_implementation_defect"
        reason = "canonical_implementation_or_accounting_defect"
    else:
        outcome = "family_control_weak"
        reason = "canonical_control_weak_or_no_distinct_control_strong_portability_corroboration"
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "canonical_representative_symbol": canonical_symbol,
        "canonical_representative_selection_rule": "first compatible instrument in frozen universe order; performance independent",
        "canonical_row_outcome": canonical_outcome,
        "portability_trial_count": max(0, len(instruments) - 1),
        "portability_control_strong_count": len(strong_portability),
        "family_outcome": outcome,
        "family_outcome_allowed": outcome in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": reason,
        "instrument_rows_counted_as_independent_strategies": False,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    registry_hash_before = file_hash(root / REGISTRY_PATH)
    active_hash_before = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    universe_rows = frozen_universe(root)
    compat = compatibility_rows(root)
    instruments = choose_instruments(root, universe_rows)
    bil = load_adjusted_ohlcv(root, "BIL")
    task_outcome = "macd_fast_lane_batch_complete"
    blocker = ""
    if not universe_rows or not compat:
        task_outcome = "frozen_universe_or_compatibility_missing"
        blocker = "Frozen universe or compatibility map missing."
    elif bil.empty:
        task_outcome = "existing_data_coverage_insufficient"
        blocker = "BIL cash proxy adjusted OHLCV cache missing."
    elif not instruments:
        task_outcome = "existing_data_coverage_insufficient"
        blocker = "No compatible risky ETFs selected from frozen universe."

    coverage_rows = [coverage_row(root, "BIL", {"candidate_group": "cash_proxy"})]
    coverage_rows.extend(coverage_row(root, row["symbol"], row) for row in instruments)
    manifest_rows = []
    trial_registry = []
    for row in instruments:
        trial_id = f"{STRATEGY_ID}__{row['symbol']}"
        manifest_rows.append(
            {
                "task_id": TASK_ID,
                "trial_id": trial_id,
                "strategy_id": STRATEGY_ID,
                "family_id": FAMILY_ID,
                "source_id": SOURCE_ID,
                "symbol": row["symbol"],
                "candidate_group": row.get("candidate_group", ""),
                "primary_economic_exposure": row.get("primary_economic_exposure", ""),
                "fast_ema_period": FAST_EMA_PERIOD,
                "slow_ema_period": SLOW_EMA_PERIOD,
                "signal_ema_period": SIGNAL_EMA_PERIOD,
                "canonical_representative_symbol": instruments[0]["symbol"] if instruments else "",
                "cost_bps_per_state_change_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
                "benchmarks": "risky_buy_hold|BIL_buy_hold|static_average_exposure_control|zero_cost_accounting_diagnostic",
                "expected_trial_count": len(instruments),
                "frozen_before_return_calculation": True,
                "performance_used_for_selection": False,
            }
        )
        trial_registry.append(
            {
                "trial_id": trial_id,
                "strategy_id": STRATEGY_ID,
                "family_id": FAMILY_ID,
                "source_id": SOURCE_ID,
                "symbol": row["symbol"],
                "candidate_group": row.get("candidate_group", ""),
                "attempted_trial": True,
                "trial_registered_before_returns": True,
                "instrument_rows_counted_as_independent_strategies": False,
                "adaptation_label": "family_portability_test",
            }
        )

    baseline_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    transaction_rows_all: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    vs_rows: list[dict[str, Any]] = []
    timeframe_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    ema_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    if task_outcome == "macd_fast_lane_batch_complete":
        try:
            for instrument in instruments:
                baseline, controls, transactions, invariant, vs, timeframe, outcome, ema, signal, targets = evaluate_trial(root, instrument, bil)
                baseline_rows.append(baseline)
                control_rows.extend(controls)
                transaction_rows_all.extend(transactions)
                if invariant:
                    invariant_rows.append(invariant)
                if vs:
                    vs_rows.append(vs)
                if timeframe:
                    timeframe_rows.append(timeframe)
                outcome_rows.append(outcome)
                ema_rows.extend(ema)
                signal_rows.extend(signal)
                target_rows.extend(targets)
        except Exception as exc:  # pragma: no cover - defensive evidence.
            task_outcome = "implementation_or_accounting_defect"
            blocker = f"batch_exception:{type(exc).__name__}"
    fam = family_outcome(instruments, outcome_rows) if outcome_rows else {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "family_outcome": "family_implementation_defect" if task_outcome == "implementation_or_accounting_defect" else "family_control_weak",
        "family_outcome_allowed": True,
        "family_outcome_reason": blocker or "no_evaluated_rows",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    if any(row.get("row_outcome") == "implementation_or_accounting_defect" for row in outcome_rows):
        task_outcome = "implementation_or_accounting_defect"
        blocker = "One or more rows reported implementation/accounting defects."
    registry_hash_after = file_hash(root / REGISTRY_PATH)
    active_hash_after = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    group_counts: dict[str, int] = {}
    for row in instruments:
        group_counts[row.get("candidate_group", "")] = group_counts.get(row.get("candidate_group", ""), 0) + 1

    fit_check = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_rule_complete": True,
        "uses_adjusted_daily_ohlcv_only": True,
        "selected_compatibility_family": SELECTED_COMPATIBILITY_FAMILY,
        "requires_macro_or_fundamental_data": False,
        "requires_new_credential": False,
        "requires_provider_download": False,
        "requires_intraday_data": False,
        "long_cash_only": True,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_or_futures_allowed": False,
        "parameter_search": False,
        "overlay_experiment": False,
        "paper_demo_activation": False,
    }
    universe_reference = {
        "task_id": TASK_ID,
        "frozen_universe_path": str(FROZEN_UNIVERSE_PATH).replace("\\", "/"),
        "frozen_universe_hash": file_hash(root / FROZEN_UNIVERSE_PATH),
        "compatibility_map_path": str(COMPATIBILITY_PATH).replace("\\", "/"),
        "compatibility_map_hash": file_hash(root / COMPATIBILITY_PATH),
        "market_data_manifest_path": str(UNIVERSE_MARKET_DATA_MANIFEST).replace("\\", "/"),
        "market_data_manifest": read_yaml(root / UNIVERSE_MARKET_DATA_MANIFEST),
        "selected_compatibility_family": SELECTED_COMPATIBILITY_FAMILY,
        "selected_symbols": [row["symbol"] for row in instruments],
        "instrument_selection_rule": "canonical first compatible frozen symbol, then first symbol from each subsequent distinct group in frozen order",
    }
    representative = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "canonical_representative_symbol": instruments[0]["symbol"] if instruments else "",
        "canonical_candidate_group": instruments[0].get("candidate_group", "") if instruments else "",
        "selection_rule": "first compatible instrument in frozen universe order",
        "performance_used_for_selection": False,
    }
    followups = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "family_outcome": fam["family_outcome"],
            "next_review_status": "direction_owner_review_required_before_any_followup",
        }
    ] if fam.get("family_outcome") == "family_exploratory_followup_candidate" else []
    consistency = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "task_outcome": task_outcome,
        "task_outcome_allowed": task_outcome in VALID_TASK_OUTCOMES,
        "parameters_exact_12_26_9": FAST_EMA_PERIOD == 12 and SLOW_EMA_PERIOD == 26 and SIGNAL_EMA_PERIOD == 9,
        "ema_seeding_sma_convention": all(row.get("fast_seed_matches_sma") is True and row.get("slow_seed_matches_sma") is True for row in ema_rows),
        "no_state_before_first_valid_crossover": all(abs(as_float(row.get("pre_first_crossover_target_weight_sum"))) <= 1e-12 for row in ema_rows),
        "crossovers_detected_once": all(row.get("crossovers_are_transition_events") is True for row in signal_rows),
        "same_bar_execution_impossible": all(row.get("same_bar_execution_impossible") is True for row in invariant_rows),
        "post_initialization_weights_sum_to_one": all(row.get("post_initialization_weight_sum_exact_1") is True for row in invariant_rows),
        "only_risky_etf_or_bil_held": all(row.get("only_risky_or_bil_held") is True for row in invariant_rows),
        "costs_apply_once_per_state_change": len(transaction_rows_all) == int(sum(row.get("trade_count", 0) for row in baseline_rows)),
        "trial_selection_performance_independent": all(row.get("performance_used_for_selection") is False for row in manifest_rows),
        "trial_count_lte_6": len(trial_registry) <= MAX_TRIALS,
        "max_two_instruments_per_group_when_other_groups_exist": all(count <= 2 for count in group_counts.values()),
        "trial_manifest_frozen_before_returns": all(row.get("frozen_before_return_calculation") is True for row in manifest_rows),
        "every_attempted_trial_registered_once": len({row["trial_id"] for row in trial_registry}) == len(trial_registry) == len(outcome_rows),
        "static_controls_same_calendar": all(row.get("static_control_same_calendar") is True for row in invariant_rows),
        "row_outcomes_allowed": all(row.get("row_outcome_allowed") is True for row in outcome_rows),
        "family_outcome_allowed": fam.get("family_outcome_allowed") is True,
        "no_alternative_parameters_generated": True,
        "no_overlay_output_produced": True,
        "registry_lifecycle_unchanged": registry_hash_before == registry_hash_after,
        "active_paper_demo_state_unchanged": active_hash_before == active_hash_after,
        "broker_or_order_path_touched": False,
        "provider_download": False,
        "intraday_data_used": False,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "invariant_failure_count": sum(1 for row in invariant_rows if str(row.get("exposure_invariant_pass")) != "True"),
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["task_outcome_allowed"]
        and consistency["parameters_exact_12_26_9"]
        and consistency["ema_seeding_sma_convention"]
        and consistency["no_state_before_first_valid_crossover"]
        and consistency["crossovers_detected_once"]
        and consistency["same_bar_execution_impossible"]
        and consistency["post_initialization_weights_sum_to_one"]
        and consistency["only_risky_etf_or_bil_held"]
        and consistency["costs_apply_once_per_state_change"]
        and consistency["trial_selection_performance_independent"]
        and consistency["trial_count_lte_6"]
        and consistency["max_two_instruments_per_group_when_other_groups_exist"]
        and consistency["trial_manifest_frozen_before_returns"]
        and consistency["every_attempted_trial_registered_once"]
        and consistency["static_controls_same_calendar"]
        and consistency["row_outcomes_allowed"]
        and consistency["family_outcome_allowed"]
        and consistency["no_alternative_parameters_generated"]
        and consistency["no_overlay_output_produced"]
        and consistency["registry_lifecycle_unchanged"]
        and consistency["active_paper_demo_state_unchanged"]
        and not consistency["broker_or_order_path_touched"]
        and not consistency["provider_download"]
        and not consistency["intraday_data_used"]
        and not consistency["paper_forward_activation"]
        and not consistency["promotion_candidates_created"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["real_money_recommendation"]
        and consistency["invariant_failure_count"] == 0
    )

    write_yaml(output / "source_packet_used.yaml", source_packet())
    write_json(output / "repository_fit_check.json", fit_check)
    write_json(output / "frozen_universe_reference.json", universe_reference)
    write_csv(
        output / "frozen_trial_manifest.csv",
        manifest_rows,
        [
            "task_id",
            "trial_id",
            "strategy_id",
            "family_id",
            "source_id",
            "symbol",
            "candidate_group",
            "primary_economic_exposure",
            "fast_ema_period",
            "slow_ema_period",
            "signal_ema_period",
            "canonical_representative_symbol",
            "cost_bps_per_state_change_turnover",
            "benchmarks",
            "expected_trial_count",
            "frozen_before_return_calculation",
            "performance_used_for_selection",
        ],
    )
    write_json(output / "canonical_family_representative.json", representative)
    write_csv(
        output / "trial_registry.csv",
        trial_registry,
        ["trial_id", "strategy_id", "family_id", "source_id", "symbol", "candidate_group", "attempted_trial", "trial_registered_before_returns", "instrument_rows_counted_as_independent_strategies", "adaptation_label"],
    )
    write_csv(output / "data_coverage.csv", coverage_rows, ["symbol", "candidate_group", "primary_economic_exposure", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"])
    write_csv(
        output / "ema_initialization_audit.csv",
        ema_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "fast_ema_period",
            "slow_ema_period",
            "signal_ema_period",
            "first_fast_ema_date",
            "first_slow_ema_date",
            "first_macd_date",
            "first_signal_date",
            "first_target_date",
            "fast_seed_value",
            "fast_seed_sma",
            "slow_seed_value",
            "slow_seed_sma",
            "fast_seed_matches_sma",
            "slow_seed_matches_sma",
            "pre_first_crossover_target_weight_sum",
        ],
    )
    write_csv(
        output / "signal_calculation_audit.csv",
        signal_rows,
        ["trial_id", "strategy_id", "symbol", "bullish_cross_count", "bearish_cross_count", "crossovers_are_transition_events", "histogram_zero_line_divergence_or_filter_used", "state_persists_without_crossover", "valid_signal_rows", "first_target_date"],
    )
    write_csv(output / "target_weights.csv", target_rows, ["trial_id", "strategy_id", "symbol", "date", "risky_weight", "bil_weight", "weight_sum", "state", "macd", "signal", "bullish_cross", "bearish_cross"])
    write_csv(output / "transactions.csv", transaction_rows_all, ["trial_id", "strategy_id", "symbol", "signal_date", "execution_convention", "turnover_proxy", "cost_rate", "cost_return_deduction", "cost_applied_once_for_state_change"])
    write_csv(
        output / "baseline_metrics.csv",
        baseline_rows,
        [
            "trial_id",
            "strategy_id",
            "family_id",
            "source_id",
            "symbol",
            "candidate_group",
            "primary_economic_exposure",
            "fast_ema_period",
            "slow_ema_period",
            "signal_ema_period",
            "start_date",
            "end_date",
            "trading_days",
            "total_return",
            "zero_cost_total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
            "average_risky_exposure",
            "average_bil_exposure",
            "trade_count",
            "turnover_proxy",
            "bullish_cross_count",
            "bearish_cross_count",
            "entry_count",
            "exit_count",
            "valid_signal_rows",
            "standard_cost_bps_per_turnover",
            "primary_control_total_return",
            "static_exposure_control_total_return",
            "excess_return_vs_primary_control_after_cost",
            "excess_return_vs_static_exposure_control_after_cost",
            "row_outcome",
            "failure_reason",
            "numeric_result_interpretable",
            "promotion_eligibility",
            "paper_forward_eligibility",
            "candidate_exhaustive_eligibility",
        ],
    )
    write_csv(output / "control_metrics.csv", control_rows, ["trial_id", "strategy_id", "symbol", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "performance_selected_control"])
    write_csv(
        output / "baseline_vs_controls.csv",
        vs_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "baseline_total_return_after_cost",
            "zero_cost_total_return",
            "risky_buy_hold_total_return",
            "BIL_buy_hold_total_return",
            "static_average_exposure_control_total_return",
            "after_cost_beats_primary_control",
            "after_cost_beats_static_control",
            "zero_cost_beats_primary_control",
            "zero_cost_beats_static_control",
        ],
    )
    write_csv(output / "timeframe_diagnostics.csv", timeframe_rows, ["trial_id", "strategy_id", "symbol", "first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_excess_vs_primary_control", "second_half_excess_vs_primary_control", "timeframe_diagnostic_not_holdout"])
    write_csv(
        output / "accounting_invariants.csv",
        invariant_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "max_daily_exposure",
            "max_daily_weight_sum",
            "average_weight_sum",
            "weight_sum_violation_count",
            "negative_weight_violation_count",
            "nan_weight_count",
            "impossible_cash_and_risky_exposure_days",
            "post_initialization_weight_sum_exact_1",
            "only_risky_or_bil_held",
            "pre_first_crossover_no_position",
            "exposure_invariant_pass",
            "same_bar_execution_impossible",
            "no_lookahead_status",
            "cost_accounting_status",
            "static_control_same_calendar",
        ],
    )
    write_csv(
        output / "row_outcomes.csv",
        outcome_rows,
        ["trial_id", "strategy_id", "family_id", "source_id", "symbol", "candidate_group", "row_outcome", "row_outcome_allowed", "failure_reason", "instrument_rows_counted_as_independent_strategies", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"],
    )
    write_json(output / "family_outcome.json", fam)
    write_csv(output / "family_followup_queue.csv", followups, ["strategy_id", "family_id", "source_id", "family_outcome", "next_review_status"])
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_csv(
        output / "command_validation_log.csv",
        [
            {
                "command": ".venv\\Scripts\\python.exe run_fidelity_macd_12_26_9_signal_crossover_portability_v1.py",
                "status": "generated_by_runner",
                "notes": "dedicated MACD fast-lane runner",
            },
            {
                "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_fidelity_macd_12_26_9_signal_crossover_portability_v1.py -q",
                "status": "external_validation_required",
                "notes": "focused tests",
            },
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    outcome_counts = {label: sum(1 for row in outcome_rows if row.get("row_outcome") == label) for label in sorted(VALID_ROW_OUTCOMES)}
    outcome_counts = {key: value for key, value in outcome_counts.items() if value}
    summary = f"""# Fidelity MACD 12/26/9 Signal Crossover Portability v1

Task outcome: `{task_outcome}`

- Strategy ID: `{STRATEGY_ID}`
- Family: `{FAMILY_ID}`
- Selected instruments: `{', '.join(row['symbol'] for row in instruments) if instruments else 'none'}`
- Trials registered/evaluated: `{len(trial_registry)} / {len(outcome_rows)}`
- Row outcomes: `{json.dumps(outcome_counts, sort_keys=True)}`
- Family outcome: `{fam.get('family_outcome')}`
- Invariant failures: `{consistency['invariant_failure_count']}`
- Provider download: `false`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Blocker: `{blocker or 'none'}`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "implementation_summary.md", summary)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "registered_trial_count": len(trial_registry),
        "evaluated_trial_count": len(outcome_rows),
        "selected_symbols": [row["symbol"] for row in instruments],
        "row_outcomes": outcome_counts,
        "family_outcome": fam.get("family_outcome"),
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
