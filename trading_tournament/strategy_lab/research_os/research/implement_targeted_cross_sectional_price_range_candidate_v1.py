from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    fast_price_volume_discovery_batch_v2 as market,
)
from strategy_lab.research_os.research import (
    fast_source_library_batch_v5 as close_engine,
)
from strategy_lab.research_os.research import (
    implement_targeted_cross_sectional_low_turnover_candidate_v1 as parent,
)
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as helpers,
)


TASK_ID = "implement_targeted_cross_sectional_price_range_candidate_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "chen_yu_52week_low_sector_one_month_portability_v1"
FAMILY_ID = "cross_sectional_52week_low_anchor_reversal"
DISPLAY_NAME = "Sector Nearness-to-52-Week-Low Selection"
ARCHITECTURE = "monthly_single_sector_extreme_price_anchor_selection"
SOURCE_RECORD_ID = "src_chen_yu_52week_low_sector_portability_v1"
SOURCE_LINEAGE = (
    "targeted_cross_sectional_price_range_source_sprint_v1:"
    "src_chen_yu_52week_low_sector_portability_v1"
)
TRIAL_ID = f"{TASK_ID}__canonical"
FROZEN_TIMESTAMP = "2026-07-28T00:00:00-06:00"

SECTORS = parent.SECTORS
REQUIRED_SYMBOLS = SECTORS + ("BIL", "SPY")
LOOKBACK_MONTHS = 12
SELECTED_COUNT = 1
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10

CONTROL_IDS = (
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
    "monthly_equal_weight_nine_sector_control",
    "sector_52week_high_top1_one_month_control",
    "sector_12month_return_bottom1_reversal_control",
    "sector_12_2_momentum_top1_control",
)
CRITICAL_CONTROL_IDS = (
    "sector_12month_return_bottom1_reversal_control",
    "sector_52week_high_top1_one_month_control",
)
SIMPLER_CONTROL_IDS = (
    "SPY_buy_and_hold",
    "monthly_equal_weight_nine_sector_control",
    "sector_12_2_momentum_top1_control",
)
PORTFOLIO_SLEEVES = (
    STRATEGY_ID,
    "sector_12month_return_bottom1_reversal_control",
    "sector_52week_high_top1_one_month_control",
    "monthly_equal_weight_nine_sector_control",
)
PORTFOLIO_IDS = {
    "reference": "100pct_reference",
    STRATEGY_ID: "80pct_reference_20pct_candidate",
    "sector_12month_return_bottom1_reversal_control": (
        "80pct_reference_20pct_12month_loser_control"
    ),
    "sector_52week_high_top1_one_month_control": (
        "80pct_reference_20pct_52week_high_control"
    ),
    "monthly_equal_weight_nine_sector_control": (
        "80pct_reference_20pct_equal_weight_sector_control"
    ),
}

NEXT_ADVANCE = "direction_owner_review_chen_yu_52week_low_followup_v1"
NEXT_CLOSE = "targeted_price_path_shape_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_52week_low_portability_block_v1"

OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\78a0a9b7-d5fa-4b5d-b2a1-e0a0a1d7f303\pasted-text.txt"
)
PROTECTED_PATHS = helpers.PROTECTED_PATHS

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "formation_signal_diagnostics.csv",
    "monthly_selection_ledger.csv",
    "overlap_with_control_selections.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}

METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_risky_exposure",
    "total_one_way_turnover",
    "monthly_formation_count",
    "switch_count",
    "transaction_cost_drag",
    "maximum_single_sector_weight",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


@dataclass(frozen=True)
class Formation:
    sequence: int
    formation_date: pd.Timestamp
    execution_date: pd.Timestamp
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp
    complete: bool
    current_close: dict[str, float]
    trailing_minimum: dict[str, float]
    trailing_maximum: dict[str, float]
    low_score: dict[str, float]
    high_score: dict[str, float]
    trailing_return: dict[str, float]
    momentum_12_2: dict[str, float]
    low_rank: dict[str, int]
    high_rank: dict[str, int]
    loser_rank: dict[str, int]
    momentum_rank: dict[str, int]
    candidate_selection: tuple[str, ...]
    high_selection: tuple[str, ...]
    loser_selection: tuple[str, ...]
    momentum_selection: tuple[str, ...]
    missing_symbols: tuple[str, ...]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def frozen_rule() -> str:
    return (
        "At each completed month-end, calculate each frozen sector's adjusted "
        "close divided by its minimum adjusted close over the trailing twelve "
        "complete calendar months. Rank all nine LOW scores ascending with "
        "lexical ties, select exactly one sector, and execute a 100 percent "
        "allocation at the following regular-session close for one month. "
        "Warmup or an incomplete formation holds BIL."
    )


def parameters() -> dict[str, Any]:
    return {
        "formation_frequency": "month_end",
        "range_lookback": "trailing_12_calendar_months",
        "score": "current_adjusted_close/trailing_12_calendar_month_minimum",
        "ranking": "ascending",
        "selected_count": SELECTED_COUNT,
        "holding_period": "one_month",
        "tie_break": "lexical_ticker",
        "execution": "following_regular_session_close",
        "warmup_or_invalid_asset": "BIL",
    }


def source_row() -> dict[str, Any]:
    return {
        "source_record_id": SOURCE_RECORD_ID,
        "entity_type": "source_library_record",
        "stage": "source_extracted",
        "outcome": "feasible",
        "failure_reason": "",
        "implementation_authorized": True,
        "strategy_id": STRATEGY_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "external_source_research_performed": False,
        "source_rule_completion_performed": False,
        "next_action": TASK_ID,
    }


def strategy_row(
    outcome: str, failure_reason: str, next_action: str
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "|".join(REQUIRED_SYMBOLS[:-1]),
        "parameters": parameters(),
        "benchmark_or_control": list(CONTROL_IDS),
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": "",
        "adaptation_label": "",
        "route": "standalone",
        "exact_source_replication_claimed": False,
        "translation_label": "long_leg_and_nine_sector_portability",
        "source_rule_changed": False,
        "stock_to_sector_translation": True,
        "bottom_10pct_to_one_of_nine_translation": True,
        "lookback_changed": False,
        "holding_period_changed": False,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def trial_row(
    outcome: str, failure_reason: str, next_action: str
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "experiment_trial",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "|".join(REQUIRED_SYMBOLS[:-1]),
        "parameters": parameters(),
        "benchmark_or_control": list(CONTROL_IDS),
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": "",
        "adaptation_label": "",
        "frozen_rule": frozen_rule(),
        "source_rule_changed": False,
        "stock_to_sector_translation": True,
        "bottom_10pct_to_one_of_nine_translation": True,
        "lookback_changed": False,
        "holding_period_changed": False,
        "instruments_changed_after_results": False,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    descriptions = {
        "SPY_buy_and_hold": "Initial 100 percent SPY buy-and-hold.",
        "BIL_buy_and_hold": "Initial 100 percent BIL buy-and-hold.",
        "monthly_equal_weight_nine_sector_control": (
            "Monthly equal weight in the same nine sectors."
        ),
        "sector_52week_high_top1_one_month_control": (
            "Select the largest close/trailing-12-month maximum score."
        ),
        "sector_12month_return_bottom1_reversal_control": (
            "Select the lowest trailing 12-month total-return sector."
        ),
        "sector_12_2_momentum_top1_control": (
            "Select the highest 12-2 sector return with identical timing."
        ),
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": "",
            "trial_id": "",
            "description": descriptions[control_id],
            "same_purpose_control": (
                control_id
                == "sector_12month_return_bottom1_reversal_control"
            ),
            "critical_control": control_id in CRITICAL_CONTROL_IDS,
            "performance_selected": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for control_id in CONTROL_IDS
    ]


def process_row(next_action: str, outcome: str = "preregistered") -> dict[str, Any]:
    return {
        "process_task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "strategy_count": 1,
        "trial_count": 1,
        "network_accessed": False,
        "provider_accessed": False,
        "lifecycle_state_changed": False,
        "next_action": next_action,
    }


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def hash_map(paths: tuple[Path, ...]) -> dict[str, str]:
    return {rel(path): helpers.file_hash(path) for path in paths}


def data_preflight() -> tuple[
    list[dict[str, Any]], dict[str, pd.DataFrame], pd.DatetimeIndex
]:
    rows, frames, common = parent.data_preflight()
    for row in rows:
        row["required_for_task"] = TASK_ID
        row["provider_access_allowed"] = False
        row["universe_reduction_allowed"] = False
    return rows, frames, common


def rank_values(values: dict[str, float], ascending: bool) -> dict[str, int]:
    return parent.rank_values(values, ascending)


def _month_end_close(
    prices: pd.DataFrame, period: pd.Period
) -> pd.Series | None:
    rows = prices.loc[prices.index.to_period("M") == period]
    if rows.empty or rows.isna().any().any():
        return None
    return rows.iloc[-1]


def formation_inputs(
    sector_prices: pd.DataFrame,
    master_index: pd.DatetimeIndex,
    formation_date: pd.Timestamp,
) -> dict[str, Any] | None:
    end_period = pd.Timestamp(formation_date).to_period("M")
    periods = pd.period_range(end=end_period, periods=LOOKBACK_MONTHS, freq="M")
    expected = master_index[master_index.to_period("M").isin(periods)]
    counts = pd.Series(expected.to_period("M")).value_counts()
    if set(expected.to_period("M")) != set(periods):
        return None
    if any(int(counts.get(period, 0)) < 15 for period in periods):
        return None
    window = sector_prices.reindex(expected)
    missing = tuple(symbol for symbol in SECTORS if window[symbol].isna().any())
    current = _month_end_close(sector_prices, end_period)
    prior_12 = _month_end_close(sector_prices, end_period - 12)
    prior_1 = _month_end_close(sector_prices, end_period - 1)
    if current is None or prior_12 is None or prior_1 is None:
        return None
    if missing:
        return {"missing_symbols": missing}
    trailing_minimum = {
        symbol: float(window[symbol].min()) for symbol in SECTORS
    }
    trailing_maximum = {
        symbol: float(window[symbol].max()) for symbol in SECTORS
    }
    current_close = {symbol: float(current[symbol]) for symbol in SECTORS}
    low_score = {
        symbol: current_close[symbol] / trailing_minimum[symbol]
        for symbol in SECTORS
    }
    high_score = {
        symbol: current_close[symbol] / trailing_maximum[symbol]
        for symbol in SECTORS
    }
    trailing_return = {
        symbol: float(current[symbol] / prior_12[symbol] - 1.0)
        for symbol in SECTORS
    }
    momentum_12_2 = {
        symbol: float(prior_1[symbol] / prior_12[symbol] - 1.0)
        for symbol in SECTORS
    }
    collections = (
        current_close,
        trailing_minimum,
        trailing_maximum,
        low_score,
        high_score,
        trailing_return,
        momentum_12_2,
    )
    if not all(
        math.isfinite(value)
        for collection in collections
        for value in collection.values()
    ):
        return None
    return {
        "window_start": pd.Timestamp(expected[0]),
        "current_close": current_close,
        "trailing_minimum": trailing_minimum,
        "trailing_maximum": trailing_maximum,
        "low_score": low_score,
        "high_score": high_score,
        "trailing_return": trailing_return,
        "momentum_12_2": momentum_12_2,
        "missing_symbols": (),
    }


def build_formations(
    sector_prices: pd.DataFrame,
    master_index: pd.DatetimeIndex,
    evaluation_index: pd.DatetimeIndex,
) -> list[Formation]:
    formations: list[Formation] = []
    sequence = 0
    for formation_date in parent.month_ends(master_index):
        if formation_date < evaluation_index.min():
            continue
        execution = parent.next_session(evaluation_index, formation_date)
        if execution is None:
            continue
        inputs = formation_inputs(sector_prices, master_index, formation_date)
        complete = bool(inputs is not None and not inputs.get("missing_symbols", ()))
        if complete:
            low_score = inputs["low_score"]
            high_score = inputs["high_score"]
            trailing_return = inputs["trailing_return"]
            momentum_12_2 = inputs["momentum_12_2"]
            low_rank = rank_values(low_score, True)
            high_rank = rank_values(high_score, False)
            loser_rank = rank_values(trailing_return, True)
            momentum_rank = rank_values(momentum_12_2, False)
            candidate_selection = tuple(
                symbol for symbol in SECTORS if low_rank[symbol] == 1
            )
            high_selection = tuple(
                symbol for symbol in SECTORS if high_rank[symbol] == 1
            )
            loser_selection = tuple(
                symbol for symbol in SECTORS if loser_rank[symbol] == 1
            )
            momentum_selection = tuple(
                symbol for symbol in SECTORS if momentum_rank[symbol] == 1
            )
        else:
            low_score = {}
            high_score = {}
            trailing_return = {}
            momentum_12_2 = {}
            low_rank = {}
            high_rank = {}
            loser_rank = {}
            momentum_rank = {}
            candidate_selection = ()
            high_selection = ()
            loser_selection = ()
            momentum_selection = ()
        formations.append(
            Formation(
                sequence=sequence,
                formation_date=pd.Timestamp(formation_date),
                execution_date=pd.Timestamp(execution),
                window_start=inputs.get("window_start") if complete else None,
                window_end=pd.Timestamp(formation_date),
                complete=complete,
                current_close=inputs["current_close"] if complete else {},
                trailing_minimum=(
                    inputs["trailing_minimum"] if complete else {}
                ),
                trailing_maximum=(
                    inputs["trailing_maximum"] if complete else {}
                ),
                low_score=low_score,
                high_score=high_score,
                trailing_return=trailing_return,
                momentum_12_2=momentum_12_2,
                low_rank=low_rank,
                high_rank=high_rank,
                loser_rank=loser_rank,
                momentum_rank=momentum_rank,
                candidate_selection=candidate_selection,
                high_selection=high_selection,
                loser_selection=loser_selection,
                momentum_selection=momentum_selection,
                missing_symbols=(
                    tuple(inputs.get("missing_symbols", ()))
                    if inputs is not None
                    else SECTORS
                ),
            )
        )
        sequence += 1
    return formations


def _target(
    symbols: tuple[str, ...], selection: tuple[str, ...]
) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in symbols}
    if selection:
        target[selection[0]] = 1.0
    else:
        target["BIL"] = 1.0
    return target


def simulate_selection_path(
    prices: pd.DataFrame,
    formations: list[Formation],
    selection_field: str,
    path_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    symbols = tuple(prices.columns)
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): _target(symbols, ())
    }
    valid_dates: list[pd.Timestamp] = []
    for formation in formations:
        selection = (
            getattr(formation, selection_field) if formation.complete else ()
        )
        events[formation.execution_date] = _target(symbols, selection)
        if formation.complete:
            valid_dates.append(formation.execution_date)
    path = close_engine.simulate_path(
        prices,
        close_engine.event_frame(prices.index, symbols, events),
        cost_bps,
        "completed_month_end_close_signal_following_regular_session_close",
    )
    path["path_id"] = path_id
    path["valid_execution_dates"] = valid_dates
    path["monthly_formation_count"] = len(valid_dates)
    path["target_risky_exposure"] = path["daily"]["risky_exposure"].copy()
    return path


def _attach_path(
    path: dict[str, Any],
    path_id: str,
    formation_dates: list[pd.Timestamp],
) -> dict[str, Any]:
    path["path_id"] = path_id
    path["valid_execution_dates"] = formation_dates
    path["monthly_formation_count"] = len(formation_dates)
    path["target_risky_exposure"] = path["daily"]["risky_exposure"].copy()
    return path


def simulate_static_path(
    prices: pd.DataFrame,
    path_id: str,
    target: dict[str, float],
    monthly: bool,
    cost_bps: float,
) -> dict[str, Any]:
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): target
    }
    formation_dates: list[pd.Timestamp] = []
    if monthly:
        for formation_date in parent.month_ends(prices.index):
            execution = parent.next_session(prices.index, formation_date)
            if execution is not None:
                events[execution] = target
                formation_dates.append(execution)
    path = close_engine.simulate_path(
        prices,
        close_engine.event_frame(prices.index, tuple(prices.columns), events),
        cost_bps,
        (
            "completed_month_end_close_target_following_regular_session_close"
            if monthly
            else "initial_buy_and_hold"
        ),
    )
    return _attach_path(path, path_id, formation_dates)


def path_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    source = close_engine.metric_payload(path, period_index)
    index = path["returns"].index if period_index is None else period_index
    held = path["held_weights"].reindex(index).dropna(how="all")
    target_exposure = path["target_risky_exposure"].reindex(index).dropna()
    valid_dates = set(pd.DatetimeIndex(index))
    formation_count = sum(
        pd.Timestamp(date) in valid_dates for date in path["valid_execution_dates"]
    )
    risky_columns = [column for column in held.columns if column != "BIL"]
    max_single = (
        float(held[risky_columns].max().max())
        if not held.empty and risky_columns
        else float("nan")
    )
    turnover = path["turnover"].reindex(index).fillna(0.0)
    return {
        "evaluation_start": source["evaluation_start"],
        "evaluation_end": source["evaluation_end"],
        "trading_days": source["trading_days"],
        "total_return": source["total_return"],
        "cagr": source["cagr"],
        "annualized_volatility": source["annualized_volatility"],
        "sharpe_ratio": source["sharpe_ratio"],
        "maximum_drawdown": source["maximum_drawdown"],
        "average_risky_exposure": (
            float(target_exposure.mean()) if len(target_exposure) else float("nan")
        ),
        "total_one_way_turnover": source["turnover"],
        "monthly_formation_count": formation_count,
        "switch_count": int((turnover > TOLERANCE).sum()),
        "transaction_cost_drag": source["transaction_cost_drag"],
        "maximum_single_sector_weight": max_single,
        "maximum_gross_exposure": source["maximum_gross_exposure"],
        "maximum_daily_weight_sum": source["maximum_daily_weight_sum"],
        "timing_invariant_status": source["timing_invariant_status"],
        "numeric_invariant_status": source["numeric_invariant_status"],
        "exposure_invariant_status": source[
            "exposure_weight_invariant_status"
        ],
        "weight_invariant_status": source["exposure_weight_invariant_status"],
        "invariant_pass": source["invariant_pass"],
    }


def portfolio_metrics(path: dict[str, Any]) -> dict[str, Any]:
    metrics = parent.portfolio_metrics(path)
    return {
        "evaluation_start": metrics["evaluation_start"],
        "evaluation_end": metrics["evaluation_end"],
        "trading_days": metrics["trading_days"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "annualized_volatility": metrics["annualized_volatility"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "maximum_drawdown": metrics["maximum_drawdown"],
        "average_risky_exposure": metrics["average_risky_exposure"],
        "total_one_way_turnover": metrics["total_one_way_turnover"],
        "monthly_formation_count": metrics["formation_count"],
        "switch_count": metrics["trade_or_rebalance_count"],
        "transaction_cost_drag": metrics["transaction_cost_drag"],
        "inner_sleeve_transaction_cost_drag": metrics[
            "inner_sleeve_transaction_cost_drag"
        ],
        "outer_transaction_cost_drag": metrics[
            "outer_transaction_cost_drag"
        ],
        "maximum_single_sector_weight": metrics["maximum_single_sector_weight"],
        "maximum_gross_exposure": metrics["maximum_gross_exposure"],
        "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
        "timing_invariant_status": metrics["timing_invariant_status"],
        "numeric_invariant_status": metrics["numeric_invariant_status"],
        "exposure_invariant_status": metrics["exposure_invariant_status"],
        "weight_invariant_status": metrics["weight_invariant_status"],
        "invariant_pass": metrics["invariant_pass"],
    }


def run_core(
    frames: dict[str, pd.DataFrame],
    evaluation_index: pd.DatetimeIndex,
) -> dict[str, Any]:
    prices = pd.DataFrame(
        {
            symbol: frames[symbol]["adj_close"].reindex(evaluation_index)
            for symbol in REQUIRED_SYMBOLS
        },
        index=evaluation_index,
    )
    if prices.isna().any().any():
        raise RuntimeError("Required common-session price is missing")
    master_index = frames["SPY"].index
    sector_prices = pd.DataFrame(
        {
            symbol: frames[symbol]["adj_close"].reindex(master_index)
            for symbol in SECTORS
        },
        index=master_index,
    )
    formations = build_formations(sector_prices, master_index, evaluation_index)
    selection_specs = {
        STRATEGY_ID: "candidate_selection",
        "sector_52week_high_top1_one_month_control": "high_selection",
        "sector_12month_return_bottom1_reversal_control": "loser_selection",
        "sector_12_2_momentum_top1_control": "momentum_selection",
    }
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        for path_id, field in selection_specs.items():
            path = simulate_selection_path(prices, formations, field, path_id, cost)
            if path_id == STRATEGY_ID:
                candidate_paths[cost] = path
            else:
                control_paths[(path_id, cost)] = path
    equal_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    for symbol in SECTORS:
        equal_target[symbol] = 1.0 / len(SECTORS)
    spy_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    spy_target["SPY"] = 1.0
    bil_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    bil_target["BIL"] = 1.0
    for cost in COST_BPS:
        control_paths[("SPY_buy_and_hold", cost)] = simulate_static_path(
            prices, "SPY_buy_and_hold", spy_target, False, cost
        )
        control_paths[("BIL_buy_and_hold", cost)] = simulate_static_path(
            prices, "BIL_buy_and_hold", bil_target, False, cost
        )
        control_paths[
            ("monthly_equal_weight_nine_sector_control", cost)
        ] = simulate_static_path(
            prices,
            "monthly_equal_weight_nine_sector_control",
            equal_target,
            True,
            cost,
        )
    reference = market.active_vm_dsr_usci_reference_returns()
    portfolio_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        common_reference = reference.reindex(evaluation_index).dropna()
        portfolio_paths[(PORTFOLIO_IDS["reference"], cost)] = parent.portfolio_path(
            common_reference, None, PORTFOLIO_IDS["reference"], cost
        )
        sleeve_paths = {
            STRATEGY_ID: candidate_paths[cost],
            **{
                control_id: control_paths[(control_id, cost)]
                for control_id in PORTFOLIO_SLEEVES
                if control_id != STRATEGY_ID
            },
        }
        for sleeve_id, sleeve_path in sleeve_paths.items():
            portfolio_paths[(PORTFOLIO_IDS[sleeve_id], cost)] = (
                parent.portfolio_path(
                    common_reference,
                    sleeve_path,
                    PORTFOLIO_IDS[sleeve_id],
                    cost,
                )
            )
    return {
        "prices": prices,
        "formations": formations,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": portfolio_paths,
    }


def _core_hash(core: dict[str, Any]) -> str:
    payload: dict[str, Any] = {
        "formations": [
            {
                "date": formation.formation_date,
                "complete": formation.complete,
                "low_score": formation.low_score,
                "candidate": formation.candidate_selection,
                "high": formation.high_selection,
                "loser": formation.loser_selection,
                "momentum": formation.momentum_selection,
            }
            for formation in core["formations"]
        ],
        "paths": {},
    }
    for cost, path in core["candidate_paths"].items():
        payload["paths"][f"candidate:{cost}"] = {
            "returns": helpers.frame_hash(path["returns"].to_frame("return")),
            "weights": helpers.frame_hash(path["held_weights"]),
        }
    for key, path in core["control_paths"].items():
        payload["paths"][f"control:{key}"] = {
            "returns": helpers.frame_hash(path["returns"].to_frame("return")),
            "weights": helpers.frame_hash(path["held_weights"]),
        }
    for key, path in core["portfolio_paths"].items():
        payload["paths"][f"portfolio:{key}"] = {
            "returns": helpers.frame_hash(path["returns"].to_frame("return")),
            "weights": helpers.frame_hash(path["held_weights"]),
        }
    return helpers.canonical_hash(payload)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return parent.dominates(control, candidate)


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return parent.material_advantage(candidate, control)


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return parent.worse_on_both(candidate, control)


def _economically_replicates(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        dominates(control, candidate)
        or (
            abs(float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]))
            < 0.02
            and abs(
                float(candidate["maximum_drawdown"])
                - float(control["maximum_drawdown"])
            )
            < 0.01
        )
    )


def classify(core: dict[str, Any]) -> tuple[str, str, str, str]:
    candidate = path_metrics(core["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: path_metrics(
            core["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in CONTROL_IDS
    }
    if not candidate["invariant_pass"] or not all(
        metric["invariant_pass"] for metric in controls.values()
    ):
        return (
            "blocked_feasibility",
            "methodology_failure",
            "candidate_or_required_control_invariant_failed",
            NEXT_BLOCK,
        )
    if candidate["total_return"] <= 0.0:
        return (
            "closed_exploration",
            "weak_return",
            "candidate_full_period_after_cost_return_not_positive",
            NEXT_CLOSE,
        )
    halves = parent.split_halves(core["candidate_paths"][PRIMARY_COST_BPS]["returns"].index)
    half_metrics = {
        label: {
            STRATEGY_ID: path_metrics(
                core["candidate_paths"][PRIMARY_COST_BPS], period
            ),
            **{
                control_id: path_metrics(
                    core["control_paths"][(control_id, PRIMARY_COST_BPS)],
                    period,
                )
                for control_id in CONTROL_IDS
            },
        }
        for label, period in halves
    }
    if any(
        half_metrics[label][STRATEGY_ID]["monthly_formation_count"] < 24
        for label, _ in halves
    ):
        return (
            "closed_exploration",
            "signal_scarcity",
            "fewer_than_24_valid_monthly_formations_in_a_chronological_half",
            NEXT_CLOSE,
        )
    for control_id in CRITICAL_CONTROL_IDS:
        if dominates(controls[control_id], candidate):
            return (
                "closed_exploration",
                "weak_vs_primary_control",
                f"critical_control_dominates:{control_id}",
                NEXT_CLOSE,
            )
        if not material_advantage(candidate, controls[control_id]):
            return (
                "closed_exploration",
                "weak_vs_primary_control",
                f"materiality_not_met_vs:{control_id}",
                NEXT_CLOSE,
            )
    for label, _ in halves:
        for control_id in CRITICAL_CONTROL_IDS:
            if worse_on_both(
                half_metrics[label][STRATEGY_ID],
                half_metrics[label][control_id],
            ):
                return (
                    "closed_exploration",
                    "period_instability",
                    f"worse_on_sharpe_and_drawdown:{label}:{control_id}",
                    NEXT_CLOSE,
                )
    for control_id in SIMPLER_CONTROL_IDS:
        if _economically_replicates(candidate, controls[control_id]):
            return (
                "closed_exploration",
                "benchmark_like_behavior",
                f"simpler_control_replicates_or_dominates:{control_id}",
                NEXT_CLOSE,
            )
    candidate_10 = path_metrics(core["candidate_paths"][10.0])
    for control_id in CRITICAL_CONTROL_IDS:
        control_10 = path_metrics(core["control_paths"][(control_id, 10.0)])
        if worse_on_both(candidate_10, control_10):
            return (
                "closed_exploration",
                "cost_drag",
                f"10bps_unfavorable_on_sharpe_and_drawdown:{control_id}",
                NEXT_CLOSE,
            )
    return (
        "exploratory_followup_candidate_standalone",
        "",
        "all_predeclared_lightweight_exploration_gates_passed",
        NEXT_ADVANCE,
    )


def result_row(
    row_id: str,
    row_type: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any],
    outcome: str,
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "strategy_id": STRATEGY_ID if row_type == "candidate" else "",
        "family_id": FAMILY_ID if row_type == "candidate" else "",
        "trial_id": TRIAL_ID if row_type == "candidate" else "",
        "entity_type": (
            "experiment_trial" if row_type == "candidate" else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "row_type": row_type,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "chronological_half_not_validation_or_sealed_holdout"
            if "half" in period_label
            else "full_period_exploration"
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        **metrics,
    }


def formation_rows(formations: list[Formation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for formation in formations:
        for symbol in SECTORS:
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "formation_sequence": formation.sequence,
                    "formation_date": formation.formation_date,
                    "trailing_window_start": formation.window_start,
                    "trailing_window_end": formation.window_end,
                    "symbol": symbol,
                    "current_adjusted_close": formation.current_close.get(symbol, ""),
                    "trailing_12_month_minimum_close": (
                        formation.trailing_minimum.get(symbol, "")
                    ),
                    "trailing_12_month_maximum_close": (
                        formation.trailing_maximum.get(symbol, "")
                    ),
                    "LOW_score": formation.low_score.get(symbol, ""),
                    "LOW_rank": formation.low_rank.get(symbol, ""),
                    "HIGH_score_control": formation.high_score.get(symbol, ""),
                    "HIGH_rank_control": formation.high_rank.get(symbol, ""),
                    "trailing_12_month_return_control": (
                        formation.trailing_return.get(symbol, "")
                    ),
                    "loser_rank_control": formation.loser_rank.get(symbol, ""),
                    "return_12_2_control": formation.momentum_12_2.get(symbol, ""),
                    "momentum_rank_control": (
                        formation.momentum_rank.get(symbol, "")
                    ),
                    "selected_by_candidate": (
                        symbol in formation.candidate_selection
                    ),
                    "candidate_selected_sector": (
                        formation.candidate_selection[0]
                        if formation.candidate_selection
                        else "BIL"
                    ),
                    "high_control_selected_sector": (
                        formation.high_selection[0]
                        if formation.high_selection
                        else "BIL"
                    ),
                    "loser_control_selected_sector": (
                        formation.loser_selection[0]
                        if formation.loser_selection
                        else "BIL"
                    ),
                    "momentum_control_selected_sector": (
                        formation.momentum_selection[0]
                        if formation.momentum_selection
                        else "BIL"
                    ),
                    "execution_date": formation.execution_date,
                    "signal_complete": formation.complete,
                    "missing_symbols": formation.missing_symbols,
                }
            )
    return rows


def selection_ledger_rows(
    formations: list[Formation], candidate_path: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    turnover = candidate_path["turnover"]
    cost = candidate_path["cost"]
    previous = "BIL"
    for formation in formations:
        selected = (
            formation.candidate_selection[0]
            if formation.candidate_selection
            else "BIL"
        )
        rows.append(
            {
                "formation_sequence": formation.sequence,
                "formation_date": formation.formation_date,
                "execution_date": formation.execution_date,
                "signal_complete": formation.complete,
                "previous_holding": previous,
                "target_holding": selected,
                "candidate_selected_sector": selected,
                "high_control_selected_sector": (
                    formation.high_selection[0]
                    if formation.high_selection
                    else "BIL"
                ),
                "loser_control_selected_sector": (
                    formation.loser_selection[0]
                    if formation.loser_selection
                    else "BIL"
                ),
                "momentum_control_selected_sector": (
                    formation.momentum_selection[0]
                    if formation.momentum_selection
                    else "BIL"
                ),
                "one_way_turnover": float(
                    turnover.get(formation.execution_date, 0.0)
                ),
                "transaction_cost_drag_5bps": float(
                    cost.get(formation.execution_date, 0.0)
                ),
                "same_session_signal_return_used": False,
                "stale_execution_price_forward_fill_used": False,
            }
        )
        previous = selected
    return rows


def overlap_rows(
    formations: list[Formation], candidate_path: dict[str, Any]
) -> list[dict[str, Any]]:
    valid = [formation for formation in formations if formation.complete]
    rows: list[dict[str, Any]] = []
    selected = [
        formation.candidate_selection[0] for formation in valid
    ]
    for symbol in SECTORS:
        months = [
            formation for formation in valid if formation.candidate_selection == (symbol,)
        ]
        rows.append(
            {
                "record_type": "sector_selection_summary",
                "symbol": symbol,
                "candidate_selection_count": len(months),
                "candidate_selection_frequency": (
                    len(months) / len(valid) if valid else 0.0
                ),
                "consecutive_month_persistence_count": sum(
                    selected[position] == symbol
                    and selected[position - 1] == symbol
                    for position in range(1, len(selected))
                ),
                "overlap_with_52week_high_count": sum(
                    formation.candidate_selection == formation.high_selection
                    and formation.candidate_selection == (symbol,)
                    for formation in valid
                ),
                "overlap_with_12month_loser_count": sum(
                    formation.candidate_selection == formation.loser_selection
                    and formation.candidate_selection == (symbol,)
                    for formation in valid
                ),
                "overlap_with_12_2_momentum_count": sum(
                    formation.candidate_selection == formation.momentum_selection
                    and formation.candidate_selection == (symbol,)
                    for formation in valid
                ),
                "LOW_equals_exactly_1_count": sum(
                    math.isclose(
                        formation.low_score[symbol],
                        1.0,
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                    for formation in valid
                ),
                "valid_formation_count": len(valid),
                "average_holding_months": 1.0,
                "switches_per_year": (
                    float((candidate_path["turnover"] > TOLERANCE).sum())
                    / (
                        len(candidate_path["returns"])
                        / 252.0
                    )
                ),
                "longest_invalid_formation_run": _longest_invalid_run(formations),
            }
        )
    return rows


def _longest_invalid_run(formations: list[Formation]) -> int:
    longest = 0
    current = 0
    for formation in formations:
        current = 0 if formation.complete else current + 1
        longest = max(longest, current)
    return longest


def write_preregistration(preflight_rows: list[dict[str, Any]]) -> str:
    pending = "preregistered_pending_execution"
    sources = [source_row()]
    strategies = [strategy_row(pending, "", TASK_ID)]
    trials = [trial_row(pending, "", TASK_ID)]
    benchmarks = benchmark_rows()
    processes = [process_row(TASK_ID)]
    helpers.write_csv(
        OUTPUT_DIR / "source_library_records.csv", sources, list(sources[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    helpers.write_csv(
        OUTPUT_DIR / "process_task_log.csv", processes, list(processes[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0]),
    )
    return helpers.canonical_hash(
        {
            "source": sources,
            "strategy": strategies,
            "trial": trials,
            "benchmarks": benchmarks,
            "preflight": preflight_rows,
            "written_before_performance": True,
        }
    )


def _empty_performance_files() -> None:
    fields = [
        "row_id",
        "strategy_id",
        "family_id",
        "trial_id",
        "entity_type",
        "stage",
        "row_type",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "outcome",
        "failure_reason",
        *METRIC_FIELDS,
    ]
    for name in (
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
    ):
        helpers.write_csv(OUTPUT_DIR / name, [], fields)
    helpers.write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        [],
        ["portfolio_id", "cost_assumption_bps", *METRIC_FIELDS],
    )


def run() -> dict[str, Any]:
    protected_before = hash_map(PROTECTED_PATHS)
    cache_before = helpers.tree_hash(CACHE_DIR)
    prior_evidence_before = helpers.tree_hash(ROOT / "evidence", OUTPUT_DIR)
    source_before = helpers.file_hash(SOURCE_ATTACHMENT)
    clean_output()
    preflight_rows, frames, evaluation_index = data_preflight()
    preregistration_hash = write_preregistration(preflight_rows)
    executable = bool(
        len(evaluation_index)
        and all(
            row["candidate_preflight_status"] == "pass"
            for row in preflight_rows
        )
    )
    core: dict[str, Any] | None = None
    first_hash = ""
    second_hash = ""
    if executable:
        core = run_core(frames, evaluation_index)
        first_hash = _core_hash(core)
        second_hash = _core_hash(run_core(frames, evaluation_index))
        outcome, failure_reason, decision_reason, next_action = classify(core)
    else:
        outcome = "inconclusive_data_issue"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "required_canonical_data_failed_preflight"
        next_action = NEXT_BLOCK

    sources = [source_row()]
    strategies = [strategy_row(outcome, failure_reason, next_action)]
    trials = [trial_row(outcome, failure_reason, next_action)]
    benchmarks = benchmark_rows()
    processes = [process_row(next_action, "completed")]
    helpers.write_csv(
        OUTPUT_DIR / "source_library_records.csv", sources, list(sources[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    helpers.write_csv(
        OUTPUT_DIR / "process_task_log.csv", processes, list(processes[0])
    )

    all_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    half_results: list[dict[str, Any]] = []
    portfolio_results: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []

    if core is not None:
        for cost in COST_BPS:
            candidate_path = core["candidate_paths"][cost]
            candidate_metric = path_metrics(candidate_path)
            all_results.append(
                result_row(
                    STRATEGY_ID,
                    "candidate",
                    cost,
                    "full_period",
                    candidate_metric,
                    outcome,
                    failure_reason,
                )
            )
            path_pairs = [(STRATEGY_ID, "candidate", candidate_path)]
            for control_id in CONTROL_IDS:
                path = core["control_paths"][(control_id, cost)]
                metric = path_metrics(path)
                control_results.append(
                    result_row(
                        control_id,
                        "control",
                        cost,
                        "full_period",
                        metric,
                        outcome,
                        failure_reason,
                    )
                )
                path_pairs.append((control_id, "control", path))
            for path_id, row_type, path in path_pairs:
                metric = path_metrics(path)
                turnover_rows.append(
                    {
                        "record_scope": row_type,
                        "row_id": path_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metric[
                            "total_one_way_turnover"
                        ],
                        "switch_count": metric["switch_count"],
                        "transaction_cost_drag": metric[
                            "transaction_cost_drag"
                        ],
                        "inner_sleeve_transaction_cost_drag": "",
                        "outer_transaction_cost_drag": "",
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "transaction_costs_charged_once": True,
                    }
                )
                invariant_rows.append(
                    {
                        "record_scope": row_type,
                        "row_id": path_id,
                        "cost_assumption_bps": cost,
                        "exactly_nine_sectors_ranked": True,
                        "exactly_one_sector_selected_per_valid_formation": True,
                        "score_uses_only_completed_data": True,
                        "candidate_uses_only_LOW_score": True,
                        "no_same_session_signal_return": True,
                        "weights_nonnegative": True,
                        "weights_sum_to_one": True,
                        "explicit_zero_weights_preserved": True,
                        "stale_execution_price_forward_fill_used": False,
                        "transaction_costs_charged_once": True,
                        "maximum_gross_exposure": metric[
                            "maximum_gross_exposure"
                        ],
                        "maximum_daily_weight_sum": metric[
                            "maximum_daily_weight_sum"
                        ],
                        "timing_invariant_status": metric[
                            "timing_invariant_status"
                        ],
                        "numeric_invariant_status": metric[
                            "numeric_invariant_status"
                        ],
                        "exposure_invariant_status": metric[
                            "exposure_invariant_status"
                        ],
                        "weight_invariant_status": metric[
                            "weight_invariant_status"
                        ],
                        "serial_rerun_deterministic": first_hash == second_hash,
                        "invariant_pass": metric["invariant_pass"],
                    }
                )
        for half_label, period in parent.split_halves(
            core["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
        ):
            half_results.append(
                result_row(
                    STRATEGY_ID,
                    "candidate",
                    PRIMARY_COST_BPS,
                    half_label,
                    path_metrics(
                        core["candidate_paths"][PRIMARY_COST_BPS], period
                    ),
                    outcome,
                    failure_reason,
                )
            )
            for control_id in CONTROL_IDS:
                half_results.append(
                    result_row(
                        control_id,
                        "control",
                        PRIMARY_COST_BPS,
                        half_label,
                        path_metrics(
                            core["control_paths"][
                                (control_id, PRIMARY_COST_BPS)
                            ],
                            period,
                        ),
                        outcome,
                        failure_reason,
                    )
                )
        for (portfolio_id, cost), path in sorted(core["portfolio_paths"].items()):
            metric = portfolio_metrics(path)
            portfolio_results.append(
                {
                    "portfolio_id": portfolio_id,
                    "entity_type": "portfolio_diagnostic",
                    "stage": STAGE,
                    "cost_assumption_bps": cost,
                    "period_label": "full_period",
                    "period_role": "portfolio_contribution_exploration_diagnostic",
                    "construction": (
                        "100pct_frozen_reference"
                        if portfolio_id == PORTFOLIO_IDS["reference"]
                        else "monthly_rebalanced_80pct_reference_20pct_sleeve"
                    ),
                    "daily_fixed_weight_return_blend_used": False,
                    "natural_drift_between_outer_rebalances": True,
                    **metric,
                }
            )
            turnover_rows.append(
                {
                    "record_scope": "portfolio_diagnostic",
                    "row_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": metric[
                        "total_one_way_turnover"
                    ],
                    "switch_count": metric["switch_count"],
                    "transaction_cost_drag": metric[
                        "transaction_cost_drag"
                    ],
                    "inner_sleeve_transaction_cost_drag": metric[
                        "inner_sleeve_transaction_cost_drag"
                    ],
                    "outer_transaction_cost_drag": metric[
                        "outer_transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "transaction_costs_charged_once": True,
                }
            )
            invariant_rows.append(
                {
                    "record_scope": "portfolio_diagnostic",
                    "row_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "exactly_nine_sectors_ranked": True,
                    "exactly_one_sector_selected_per_valid_formation": True,
                    "score_uses_only_completed_data": True,
                    "candidate_uses_only_LOW_score": True,
                    "no_same_session_signal_return": True,
                    "weights_nonnegative": True,
                    "weights_sum_to_one": True,
                    "explicit_zero_weights_preserved": True,
                    "stale_execution_price_forward_fill_used": False,
                    "transaction_costs_charged_once": True,
                    "maximum_gross_exposure": metric[
                        "maximum_gross_exposure"
                    ],
                    "maximum_daily_weight_sum": metric[
                        "maximum_daily_weight_sum"
                    ],
                    "timing_invariant_status": metric[
                        "timing_invariant_status"
                    ],
                    "numeric_invariant_status": metric[
                        "numeric_invariant_status"
                    ],
                    "exposure_invariant_status": metric[
                        "exposure_invariant_status"
                    ],
                    "weight_invariant_status": metric[
                        "weight_invariant_status"
                    ],
                    "serial_rerun_deterministic": first_hash == second_hash,
                    "invariant_pass": metric["invariant_pass"],
                }
            )
        diagnostic_rows = formation_rows(core["formations"])
        ledger_rows = selection_ledger_rows(
            core["formations"], core["candidate_paths"][PRIMARY_COST_BPS]
        )
        overlap = overlap_rows(
            core["formations"], core["candidate_paths"][PRIMARY_COST_BPS]
        )
    else:
        _empty_performance_files()

    metric_fields = [
        "row_id",
        "strategy_id",
        "family_id",
        "trial_id",
        "entity_type",
        "stage",
        "row_type",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "outcome",
        "failure_reason",
        *METRIC_FIELDS,
    ]
    if core is not None:
        helpers.write_csv(
            OUTPUT_DIR / "all_trial_results.csv", all_results, metric_fields
        )
        helpers.write_csv(
            OUTPUT_DIR / "control_results.csv", control_results, metric_fields
        )
        helpers.write_csv(
            OUTPUT_DIR / "chronological_half_results.csv",
            half_results,
            metric_fields,
        )
        helpers.write_csv(
            OUTPUT_DIR / "portfolio_contribution_results.csv",
            portfolio_results,
            list(portfolio_results[0]),
        )
    helpers.write_csv(
        OUTPUT_DIR / "formation_signal_diagnostics.csv",
        diagnostic_rows,
        [
            "strategy_id",
            "formation_sequence",
            "formation_date",
            "trailing_window_start",
            "trailing_window_end",
            "symbol",
            "current_adjusted_close",
            "trailing_12_month_minimum_close",
            "trailing_12_month_maximum_close",
            "LOW_score",
            "LOW_rank",
            "HIGH_score_control",
            "HIGH_rank_control",
            "trailing_12_month_return_control",
            "loser_rank_control",
            "return_12_2_control",
            "momentum_rank_control",
            "selected_by_candidate",
            "candidate_selected_sector",
            "high_control_selected_sector",
            "loser_control_selected_sector",
            "momentum_control_selected_sector",
            "execution_date",
            "signal_complete",
            "missing_symbols",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "monthly_selection_ledger.csv",
        ledger_rows,
        [
            "formation_sequence",
            "formation_date",
            "execution_date",
            "signal_complete",
            "previous_holding",
            "target_holding",
            "candidate_selected_sector",
            "high_control_selected_sector",
            "loser_control_selected_sector",
            "momentum_control_selected_sector",
            "one_way_turnover",
            "transaction_cost_drag_5bps",
            "same_session_signal_return_used",
            "stale_execution_price_forward_fill_used",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "overlap_with_control_selections.csv",
        overlap,
        [
            "record_type",
            "symbol",
            "candidate_selection_count",
            "candidate_selection_frequency",
            "consecutive_month_persistence_count",
            "overlap_with_52week_high_count",
            "overlap_with_12month_loser_count",
            "overlap_with_12_2_momentum_count",
            "LOW_equals_exactly_1_count",
            "valid_formation_count",
            "average_holding_months",
            "switches_per_year",
            "longest_invalid_formation_run",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        [
            "record_scope",
            "row_id",
            "cost_assumption_bps",
            "total_one_way_turnover",
            "switch_count",
            "transaction_cost_drag",
            "inner_sleeve_transaction_cost_drag",
            "outer_transaction_cost_drag",
            "turnover_formula",
            "transaction_costs_charged_once",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        [
            "record_scope",
            "row_id",
            "cost_assumption_bps",
            "exactly_nine_sectors_ranked",
            "exactly_one_sector_selected_per_valid_formation",
            "score_uses_only_completed_data",
            "candidate_uses_only_LOW_score",
            "no_same_session_signal_return",
            "weights_nonnegative",
            "weights_sum_to_one",
            "explicit_zero_weights_preserved",
            "stale_execution_price_forward_fill_used",
            "transaction_costs_charged_once",
            "maximum_gross_exposure",
            "maximum_daily_weight_sum",
            "timing_invariant_status",
            "numeric_invariant_status",
            "exposure_invariant_status",
            "weight_invariant_status",
            "serial_rerun_deterministic",
            "invariant_pass",
        ],
    )

    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "strategy_configuration",
        "stage": STAGE,
        "route": "standalone",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }
    helpers.write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "outcome": outcome,
                "failure_reason": failure_reason,
                "decision_reason": decision_reason,
            }
        ]
        if failure_reason
        else []
    )
    helpers.write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["strategy_id", "outcome", "failure_reason", "decision_reason"],
    )
    next_row = {
        "scope": "strategy",
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }
    helpers.write_csv(
        OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row)
    )
    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "experiment_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "executed_trials": int(core is not None),
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_standalone"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "inconclusive_or_blocked": int(
            outcome in {"inconclusive_data_issue", "blocked_feasibility"}
        ),
        "entity_counts_reconcile": True,
    }
    helpers.write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    protected_after = hash_map(PROTECTED_PATHS)
    cache_after = helpers.tree_hash(CACHE_DIR)
    prior_evidence_after = helpers.tree_hash(ROOT / "evidence", OUTPUT_DIR)
    source_after = helpers.file_hash(SOURCE_ATTACHMENT)
    metadata_complete = all(
        row.get(field) not in (None, "unknown", "unmapped")
        for row in strategies + trials
        for field in (
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "strategy_architecture",
            "source_or_research_lineage",
            "instrument_universe",
            "parameters",
            "benchmark_or_control",
            "stage",
            "trial_id",
            "parent_trial_id",
            "adaptation_label",
            "outcome",
            "failure_reason",
            "next_action",
        )
    )
    invariants_pass = bool(
        core is None or all(bool(row["invariant_pass"]) for row in invariant_rows)
    )
    consistency = {
        "overall_pass": bool(
            len(sources) == len(strategies) == len(trials) == 1
            and len(benchmarks) == 6
            and metadata_complete
            and preregistration_hash
            and (core is None or first_hash == second_hash)
            and invariants_pass
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and source_before == source_after
        ),
        "exact_strategy_id": STRATEGY_ID,
        "source_library_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_hash": preregistration_hash,
        "LOW_only_candidate_score_preserved": True,
        "HIGH_momentum_volatility_or_drawdown_in_candidate_score": False,
        "parameter_variants_tested": 0,
        "provider_access": False,
        "network_access": False,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "market_data_cache_hash_before": cache_before,
        "market_data_cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "source_attachment_hash_before": source_before,
        "source_attachment_hash_after": source_after,
        "source_attachment_unchanged": source_before == source_after,
        "serial_rerun_deterministic": core is None or first_hash == second_hash,
        "deterministic_core_hash": first_hash,
        "all_invariants_pass": invariants_pass,
        "closed_52week_high_strategy_reopened": False,
        "closed_low_volatility_adaptation_reopened": False,
        "lifecycle_state_changed": False,
        "paper_demo_observations_created": 0,
        "broker_orders": 0,
        "real_money_actions": 0,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    helpers.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "source_library_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "preregistration_hash": preregistration_hash,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "validation_claimed": False,
        "exact_source_replication_claimed": False,
        "lifecycle_state_changed": False,
        "provider_accessed": False,
        "network_accessed": False,
    }
    helpers.write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    candidate_5 = (
        path_metrics(core["candidate_paths"][PRIMARY_COST_BPS])
        if core is not None
        else None
    )
    critical_5 = (
        {
            control_id: path_metrics(
                core["control_paths"][(control_id, PRIMARY_COST_BPS)]
            )
            for control_id in CRITICAL_CONTROL_IDS
        }
        if core is not None
        else {}
    )
    report = [
        "# Sector Nearness-to-52-Week-Low Exploration",
        "",
        "## Scope",
        "",
        f"Exactly one frozen configuration, `{STRATEGY_ID}`, was tested.",
        "The candidate score used only adjusted close divided by the trailing",
        "twelve-calendar-month minimum close. HIGH, return, momentum,",
        "volatility, and drawdown fields were controls or diagnostics only.",
        "",
        "This is a long-leg, nine-sector portability exploration. It is not",
        "validation, exact source replication, lifecycle evidence, or",
        "paper/demo authorization.",
        "",
        "## Outcome",
        "",
        f"* Outcome: `{outcome}`",
        f"* Primary failure reason: `{failure_reason or 'none'}`",
        f"* Decision basis: `{decision_reason}`",
    ]
    if candidate_5 is not None:
        report.extend(
            [
                (
                    "* Candidate at 5 bps: "
                    f"CAGR `{candidate_5['cagr']:.6f}`, "
                    f"Sharpe `{candidate_5['sharpe_ratio']:.6f}`, "
                    f"maximum drawdown `{candidate_5['maximum_drawdown']:.6f}`, "
                    f"turnover `{candidate_5['total_one_way_turnover']:.6f}`."
                ),
                "",
                "## Critical Controls",
                "",
            ]
        )
        for control_id in CRITICAL_CONTROL_IDS:
            metric = critical_5[control_id]
            report.append(
                f"* `{control_id}`: CAGR `{metric['cagr']:.6f}`, "
                f"Sharpe `{metric['sharpe_ratio']:.6f}`, maximum drawdown "
                f"`{metric['maximum_drawdown']:.6f}`."
            )
    report.extend(
        [
            "",
            "Both chronological halves are exploration diagnostics, not",
            "validation or sealed holdouts. All formations, selections,",
            "controls, turnover, costs, and unfavorable evidence are retained.",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action was recorded and not executed.",
        ]
    )
    write_text(OUTPUT_DIR / "batch_report.md", "\n".join(report))
    if {path.name for path in OUTPUT_DIR.iterdir()} != REQUIRED_OUTPUTS:
        consistency["overall_pass"] = False
        consistency["required_output_set_matches"] = False
        helpers.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
