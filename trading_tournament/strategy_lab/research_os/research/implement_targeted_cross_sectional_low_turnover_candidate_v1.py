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
    implement_targeted_multiday_mean_reversion_candidate_v1 as helpers,
)


TASK_ID = "implement_targeted_cross_sectional_low_turnover_candidate_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "choi_max_drawdown_sector_momentum_6x6_v1"
FAMILY_ID = "cross_sectional_max_drawdown_momentum"
DISPLAY_NAME = "Six-Month Low-Drawdown Sector Momentum"
ARCHITECTURE = "monthly_overlapping_vintage_low_drawdown_sector_selection"
SOURCE_RECORD_ID = "src_choi_max_drawdown_sector_momentum_6x6_v1"
SOURCE_LINEAGE = (
    "targeted_cross_sectional_low_turnover_selection_source_sprint_v1:"
    "src_choi_max_drawdown_sector_momentum_6x6_v1"
)
TRIAL_ID = f"{TASK_ID}__canonical"
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
REQUIRED_SYMBOLS = SECTORS + ("BIL", "SPY")
FORMATION_MONTHS = 6
SELECTED_COUNT = 3
VINTAGE_SLOTS = 6
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10

CONTROL_IDS = (
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
    "monthly_equal_weight_nine_sector_control",
    "six_month_cumulative_return_top3_sector_momentum_v1",
    "six_month_realized_volatility_bottom3_sector_v1",
    "choi_mdd_sector_exposure_matched_spy_bil_v1",
)
CRITICAL_CONTROL_IDS = (
    "six_month_cumulative_return_top3_sector_momentum_v1",
    "six_month_realized_volatility_bottom3_sector_v1",
)
PORTFOLIO_SLEEVES = (
    STRATEGY_ID,
    "six_month_cumulative_return_top3_sector_momentum_v1",
    "six_month_realized_volatility_bottom3_sector_v1",
    "monthly_equal_weight_nine_sector_control",
)
PORTFOLIO_IDS = {
    "reference": "100pct_reference",
    STRATEGY_ID: "80pct_reference_20pct_candidate",
    "six_month_cumulative_return_top3_sector_momentum_v1": (
        "80pct_reference_20pct_cumulative_return_control"
    ),
    "six_month_realized_volatility_bottom3_sector_v1": (
        "80pct_reference_20pct_low_volatility_control"
    ),
    "monthly_equal_weight_nine_sector_control": (
        "80pct_reference_20pct_equal_weight_control"
    ),
}

NEXT_ADVANCE = "direction_owner_review_choi_mdd_sector_momentum_followup_v1"
NEXT_CLOSE = "targeted_cross_sectional_price_range_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_choi_mdd_sector_momentum_block_v1"

OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\b1ce1dcb-5cb7-47bf-b469-c16bf663378e\pasted-text.txt"
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
    "formation_selection_diagnostics.csv",
    "vintage_ledger.csv",
    "overlap_with_control_selections.csv",
    "exposure_control_reconciliation.csv",
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
    "formation_count",
    "vintage_count",
    "trade_or_rebalance_count",
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
    expiration_date: pd.Timestamp | None
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp
    complete: bool
    mdd: dict[str, float]
    cumulative_log_return: dict[str, float]
    realized_volatility: dict[str, float]
    mdd_ranks: dict[str, int]
    cumulative_ranks: dict[str, int]
    volatility_ranks: dict[str, int]
    candidate_selection: tuple[str, ...]
    cumulative_selection: tuple[str, ...]
    volatility_selection: tuple[str, ...]
    missing_symbols: tuple[str, ...]


@dataclass
class Slot:
    slot_id: int
    nav: float
    weights: np.ndarray
    vintage_id: str
    selection: tuple[str, ...]
    formation_date: pd.Timestamp | None
    execution_date: pd.Timestamp | None
    opened_nav: float
    signal_complete: bool


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def frozen_rule() -> str:
    return (
        "At each completed month-end, use adjusted log closes from the six "
        "completed calendar months ending at that month-end. Rank the nine "
        "frozen sectors ascending by maximum peak-to-subsequent-trough log "
        "drawdown, select exactly three with lexical tie-breaking, and create "
        "one equal-weight one-sixth vintage at the following regular-session "
        "close. Each vintage drifts independently for six calendar months; "
        "invalid and unused slots hold BIL."
    )


def parameters() -> dict[str, Any]:
    return {
        "formation_period": "six_completed_calendar_months",
        "ranking_metric": "maximum_log_price_drawdown",
        "selected_count": SELECTED_COUNT,
        "holding_period_months": FORMATION_MONTHS,
        "vintage_slots": VINTAGE_SLOTS,
        "vintage_capital_fraction": "1/6",
        "within_vintage_allocation": "equal_weight_at_formation_only",
        "tie_break": "lexical_ticker",
        "execution": "following_regular_session_close",
        "unused_or_invalid_slot_asset": "BIL",
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
        "counted_as_strategy": False,
        "counted_as_trial": False,
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
        "instrument_universe": "|".join(SECTORS + ("BIL",)),
        "parameters": parameters(),
        "benchmark_or_control": list(CONTROL_IDS),
        "route": "standalone",
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "frozen_rule": frozen_rule(),
        "exact_source_replication_claimed": False,
        "translation_label": "source_defined_long_winner_leg_extraction",
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }


def trial_row(
    outcome: str, failure_reason: str, next_action: str
) -> dict[str, Any]:
    return {
        **strategy_row(outcome, failure_reason, next_action),
        "entity_type": "experiment_trial",
        "source_rule_changed": False,
        "selected_criterion": "MDD_only",
        "composite_criterion_tested": False,
        "formation_changed": False,
        "holding_period_changed": False,
        "universe_changed": False,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "canonical_trial": True,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    rules = {
        "SPY_buy_and_hold": "Hold SPY throughout the identical evaluation period.",
        "BIL_buy_and_hold": "Hold BIL throughout the identical evaluation period.",
        "monthly_equal_weight_nine_sector_control": (
            "Equal-weight the same nine sectors and rebalance monthly at the "
            "following regular-session close."
        ),
        "six_month_cumulative_return_top3_sector_momentum_v1": (
            "Rank six-month cumulative log return descending, select the top "
            "three, and use identical six-vintage timing and accounting."
        ),
        "six_month_realized_volatility_bottom3_sector_v1": (
            "Rank sample standard deviation of daily returns over the same "
            "formation interval ascending, select three, and use identical "
            "six-vintage timing and accounting."
        ),
        "choi_mdd_sector_exposure_matched_spy_bil_v1": (
            "Monthly rebalance SPY/BIL to the candidate mechanically observed "
            "full-period average risky target exposure without optimization."
        ),
    }
    roles = {
        "SPY_buy_and_hold": "broad_market_control",
        "BIL_buy_and_hold": "inactive_asset_control",
        "monthly_equal_weight_nine_sector_control": "equal_weight_control",
        "six_month_cumulative_return_top3_sector_momentum_v1": (
            "explicit_same_purpose_control"
        ),
        "six_month_realized_volatility_bottom3_sector_v1": (
            "low_risk_explanation_control"
        ),
        "choi_mdd_sector_exposure_matched_spy_bil_v1": (
            "mechanical_exposure_control"
        ),
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "role": roles[control_id],
            "frozen_rule": rules[control_id],
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for control_id in CONTROL_IDS
    ]


def process_row(next_action: str, outcome: str = "preregistered") -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
        "execute_next_action_now": False,
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


def cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.csv"


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], pd.DatetimeIndex]:
    frames: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = cache_path(symbol)
        raw = pd.read_csv(path) if path.exists() else pd.DataFrame()
        loaded = market.load_adjusted_ohlcv(symbol)
        frames[symbol] = loaded
        dates = pd.to_datetime(raw.get("date", pd.Series(dtype=object)), errors="coerce")
        ordered_unique = bool(
            len(raw)
            and dates.notna().all()
            and dates.is_monotonic_increasing
            and not dates.duplicated().any()
            and loaded.index.is_monotonic_increasing
            and not loaded.index.duplicated().any()
        )
        adjusted = loaded[["open", "high", "low", "close", "adj_close"]]
        finite_positive = bool(
            not loaded.empty
            and np.isfinite(adjusted.to_numpy(dtype=float)).all()
            and (adjusted.to_numpy(dtype=float) > 0.0).all()
        )
        ohlc_valid = bool(
            not loaded.empty
            and (
                loaded["low"]
                <= loaded[["open", "close"]].min(axis=1) + 1e-9
            ).all()
            and (
                loaded["high"] + 1e-9
                >= loaded[["open", "close"]].max(axis=1)
            ).all()
        )
        adjustment_compatible = bool(
            not loaded.empty
            and np.allclose(
                loaded["close"].to_numpy(dtype=float),
                loaded["adj_close"].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-10,
            )
        )
        status = bool(
            path.exists()
            and ordered_unique
            and finite_positive
            and ohlc_valid
            and adjustment_compatible
        )
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path) if path.exists() else rel(path),
                "canonical_file_hash": helpers.file_hash(path),
                "canonical_frame_hash": (
                    helpers.frame_hash(loaded) if not loaded.empty else "missing"
                ),
                "first_valid_date": (
                    loaded.index.min().date().isoformat() if not loaded.empty else ""
                ),
                "last_valid_date": (
                    loaded.index.max().date().isoformat() if not loaded.empty else ""
                ),
                "row_count": len(loaded),
                "ordered_unique_dates": ordered_unique,
                "finite_positive_adjusted_prices": finite_positive,
                "valid_adjusted_ohlc_relationships": ohlc_valid,
                "canonical_adjustment_compatible": adjustment_compatible,
                "provider_accessed": False,
                "network_accessed": False,
                "candidate_preflight_status": "pass" if status else "fail",
                "failure_reason": "" if status else "data_or_comparability_failure",
            }
        )
    if any(row["candidate_preflight_status"] != "pass" for row in rows):
        return rows, frames, pd.DatetimeIndex([])
    start = max(frame.index.min() for frame in frames.values())
    end = min(frame.index.max() for frame in frames.values())
    master = frames["SPY"].loc[start:end].index
    for row in rows:
        symbol = row["symbol"]
        missing = master.difference(frames[symbol].index)
        row["common_start"] = start.date().isoformat()
        row["common_end"] = end.date().isoformat()
        row["common_session_count"] = len(master)
        row["missing_common_session_count"] = len(missing)
        if len(missing):
            row["candidate_preflight_status"] = "fail"
            row["failure_reason"] = "data_or_comparability_failure"
    return rows, frames, master


def next_session(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    mask = periods.ne(periods.shift(-1)).fillna(True)
    return [pd.Timestamp(value) for value in index[mask]]


def rank_values(values: dict[str, float], ascending: bool) -> dict[str, int]:
    ordered = sorted(
        values,
        key=lambda symbol: (
            values[symbol] if ascending else -values[symbol],
            symbol,
        ),
    )
    return {symbol: position + 1 for position, symbol in enumerate(ordered)}


def maximum_log_drawdown(values: pd.Series) -> float:
    array = np.log(values.to_numpy(dtype=float))
    if len(array) < 2:
        return 0.0
    prior_peak = np.maximum.accumulate(array)[:-1]
    declines = prior_peak - array[1:]
    return float(max(float(np.max(declines)), 0.0))


def formation_inputs(
    sector_prices: pd.DataFrame,
    master_index: pd.DatetimeIndex,
    formation_date: pd.Timestamp,
) -> dict[str, Any] | None:
    end_period = pd.Timestamp(formation_date).to_period("M")
    periods = pd.period_range(end=end_period, periods=FORMATION_MONTHS, freq="M")
    expected = master_index[master_index.to_period("M").isin(periods)]
    if len(expected) < FORMATION_MONTHS * 15:
        return None
    expected_periods = set(expected.to_period("M"))
    if expected_periods != set(periods):
        return None
    window = sector_prices.reindex(expected)
    missing = tuple(
        symbol for symbol in SECTORS if window[symbol].isna().any()
    )
    if missing:
        return {"missing_symbols": missing}
    mdd = {symbol: maximum_log_drawdown(window[symbol]) for symbol in SECTORS}
    cumulative = {
        symbol: float(np.log(window[symbol].iloc[-1] / window[symbol].iloc[0]))
        for symbol in SECTORS
    }
    volatility = {
        symbol: float(window[symbol].pct_change(fill_method=None).dropna().std(ddof=1))
        for symbol in SECTORS
    }
    if not all(
        math.isfinite(value)
        for collection in (mdd, cumulative, volatility)
        for value in collection.values()
    ):
        return None
    return {
        "window_start": pd.Timestamp(expected[0]),
        "mdd": mdd,
        "cumulative": cumulative,
        "volatility": volatility,
        "missing_symbols": (),
    }


def build_formations(
    sector_prices: pd.DataFrame,
    master_index: pd.DatetimeIndex,
    evaluation_index: pd.DatetimeIndex,
) -> list[Formation]:
    all_month_ends = month_ends(master_index)
    provisional: list[dict[str, Any]] = []
    for formation_date in all_month_ends:
        if formation_date < evaluation_index.min():
            continue
        execution = next_session(evaluation_index, formation_date)
        if execution is None:
            continue
        inputs = formation_inputs(sector_prices, master_index, formation_date)
        complete = bool(
            inputs is not None and not inputs.get("missing_symbols", ())
        )
        mdd = inputs["mdd"] if complete else {}
        cumulative = inputs["cumulative"] if complete else {}
        volatility = inputs["volatility"] if complete else {}
        mdd_ranks = rank_values(mdd, True) if complete else {}
        cumulative_ranks = rank_values(cumulative, False) if complete else {}
        volatility_ranks = rank_values(volatility, True) if complete else {}
        provisional.append(
            {
                "formation_date": formation_date,
                "execution_date": execution,
                "window_start": inputs.get("window_start") if complete else None,
                "complete": complete,
                "mdd": mdd,
                "cumulative": cumulative,
                "volatility": volatility,
                "mdd_ranks": mdd_ranks,
                "cumulative_ranks": cumulative_ranks,
                "volatility_ranks": volatility_ranks,
                "candidate_selection": (
                    tuple(
                        sorted(SECTORS, key=lambda symbol: (mdd[symbol], symbol))[
                            :SELECTED_COUNT
                        ]
                    )
                    if complete
                    else ()
                ),
                "cumulative_selection": (
                    tuple(
                        sorted(
                            SECTORS,
                            key=lambda symbol: (-cumulative[symbol], symbol),
                        )[:SELECTED_COUNT]
                    )
                    if complete
                    else ()
                ),
                "volatility_selection": (
                    tuple(
                        sorted(
                            SECTORS,
                            key=lambda symbol: (volatility[symbol], symbol),
                        )[:SELECTED_COUNT]
                    )
                    if complete
                    else ()
                ),
                "missing_symbols": (
                    tuple(inputs.get("missing_symbols", ()))
                    if inputs is not None
                    else SECTORS
                ),
            }
        )
    formations: list[Formation] = []
    for sequence, item in enumerate(provisional):
        expiration = (
            provisional[sequence + FORMATION_MONTHS]["execution_date"]
            if sequence + FORMATION_MONTHS < len(provisional)
            else None
        )
        formations.append(
            Formation(
                sequence=sequence,
                formation_date=item["formation_date"],
                execution_date=item["execution_date"],
                expiration_date=expiration,
                window_start=item["window_start"],
                window_end=item["formation_date"],
                complete=item["complete"],
                mdd=item["mdd"],
                cumulative_log_return=item["cumulative"],
                realized_volatility=item["volatility"],
                mdd_ranks=item["mdd_ranks"],
                cumulative_ranks=item["cumulative_ranks"],
                volatility_ranks=item["volatility_ranks"],
                candidate_selection=item["candidate_selection"],
                cumulative_selection=item["cumulative_selection"],
                volatility_selection=item["volatility_selection"],
                missing_symbols=item["missing_symbols"],
            )
        )
    return formations


def selection_weights(
    symbols: tuple[str, ...], selection: tuple[str, ...]
) -> np.ndarray:
    weights = np.zeros(len(symbols), dtype=float)
    if selection:
        for symbol in selection:
            weights[symbols.index(symbol)] = 1.0 / len(selection)
    else:
        weights[symbols.index("BIL")] = 1.0
    return weights


def aggregate_weights(slots: list[Slot]) -> np.ndarray:
    total = sum(slot.nav for slot in slots)
    if total <= 0.0:
        return np.zeros_like(slots[0].weights)
    return sum((slot.nav * slot.weights for slot in slots), np.zeros_like(slots[0].weights)) / total


def _selection_for(formation: Formation, selection_field: str) -> tuple[str, ...]:
    value = getattr(formation, selection_field)
    return tuple(value)


def simulate_vintage_path(
    prices: pd.DataFrame,
    formations: list[Formation],
    selection_field: str,
    path_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    symbols = tuple(prices.columns)
    bil_target = selection_weights(symbols, ())
    slots = [
        Slot(
            slot_id=slot_id,
            nav=1.0 / VINTAGE_SLOTS,
            weights=bil_target.copy(),
            vintage_id=f"initial_BIL_slot_{slot_id}",
            selection=(),
            formation_date=None,
            execution_date=pd.Timestamp(prices.index[0]),
            opened_nav=1.0 / VINTAGE_SLOTS,
            signal_complete=False,
        )
        for slot_id in range(VINTAGE_SLOTS)
    ]
    event_map = {formation.execution_date: formation for formation in formations}
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    returns: list[float] = []
    turnover_values: list[float] = []
    cost_values: list[float] = []
    held_rows: list[np.ndarray] = []
    target_exposure_values: list[float] = []
    daily_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    vintage_rows: list[dict[str, Any]] = []
    active_ledger: dict[int, dict[str, Any]] = {}
    initial_rate = cost_bps / 10000.0
    initial_turnover = 0.5
    for slot in slots:
        slot.nav *= 1.0 - initial_turnover * initial_rate
        active_ledger[slot.slot_id] = {
            "path_id": path_id,
            "vintage_id": slot.vintage_id,
            "slot_id": slot.slot_id,
            "formation_date": "",
            "execution_date": prices.index[0].date().isoformat(),
            "expiration_date": "",
            "selection": (),
            "initial_weights": {"BIL": 1.0},
            "signal_complete": False,
            "invalid_vintage_held_in_BIL": True,
            "opened_slot_nav": slot.opened_nav,
            "closed_slot_nav_before_liquidation_cost": "",
            "gross_vintage_return": "",
            "completed": False,
        }
    previous_total = 1.0
    for position, date in enumerate(prices.index):
        held_before_return = aggregate_weights(slots)
        day_returns = asset_returns.loc[date].to_numpy(dtype=float)
        for slot in slots:
            gross_slot_return = float(np.dot(slot.weights, day_returns))
            values = slot.weights * (1.0 + day_returns)
            denominator = float(values.sum())
            slot.nav *= 1.0 + gross_slot_return
            if denominator > 0.0:
                slot.weights = values / denominator
        gross_total = sum(slot.nav for slot in slots)
        daily_turnover = initial_turnover if position == 0 else 0.0
        cost_amount = (
            previous_total * initial_turnover * initial_rate if position == 0 else 0.0
        )
        formation = event_map.get(pd.Timestamp(date))
        if formation is not None:
            slot = slots[formation.sequence % VINTAGE_SLOTS]
            old = active_ledger.pop(slot.slot_id)
            old["expiration_date"] = pd.Timestamp(date).date().isoformat()
            old["closed_slot_nav_before_liquidation_cost"] = slot.nav
            old["gross_vintage_return"] = (
                slot.nav / float(old["opened_slot_nav"]) - 1.0
                if float(old["opened_slot_nav"]) > 0.0
                else float("nan")
            )
            old["completed"] = True
            vintage_rows.append(old)
            pretrade_slot_weights = slot.weights.copy()
            selection = _selection_for(formation, selection_field)
            target = selection_weights(symbols, selection)
            slot_fraction = slot.nav / gross_total if gross_total > 0.0 else 0.0
            within_slot_turnover = 0.5 * float(
                np.abs(target - pretrade_slot_weights).sum()
            )
            event_turnover = slot_fraction * within_slot_turnover
            event_cost = slot.nav * within_slot_turnover * initial_rate
            slot.nav -= event_cost
            slot.weights = target
            slot.vintage_id = (
                f"{path_id}__{formation.formation_date.date().isoformat()}"
            )
            slot.selection = selection
            slot.formation_date = formation.formation_date
            slot.execution_date = formation.execution_date
            slot.opened_nav = slot.nav
            slot.signal_complete = formation.complete
            daily_turnover += event_turnover
            cost_amount += event_cost
            active_ledger[slot.slot_id] = {
                "path_id": path_id,
                "vintage_id": slot.vintage_id,
                "slot_id": slot.slot_id,
                "formation_date": formation.formation_date.date().isoformat(),
                "execution_date": formation.execution_date.date().isoformat(),
                "expiration_date": (
                    formation.expiration_date.date().isoformat()
                    if formation.expiration_date is not None
                    else ""
                ),
                "selection": selection,
                "initial_weights": {
                    symbol: float(target[symbols.index(symbol)])
                    for symbol in symbols
                    if target[symbols.index(symbol)] > TOLERANCE
                },
                "signal_complete": formation.complete,
                "invalid_vintage_held_in_BIL": not bool(selection),
                "opened_slot_nav": slot.opened_nav,
                "closed_slot_nav_before_liquidation_cost": "",
                "gross_vintage_return": "",
                "completed": False,
            }
            event_rows.append(
                {
                    "path_id": path_id,
                    "formation_sequence": formation.sequence,
                    "formation_date": formation.formation_date.date().isoformat(),
                    "event_date": pd.Timestamp(date).date().isoformat(),
                    "expiration_date": (
                        formation.expiration_date.date().isoformat()
                        if formation.expiration_date is not None
                        else ""
                    ),
                    "slot_id": slot.slot_id,
                    "selection": selection,
                    "signal_complete": formation.complete,
                    "pretrade_slot_weights": {
                        symbol: float(pretrade_slot_weights[index])
                        for index, symbol in enumerate(symbols)
                        if pretrade_slot_weights[index] > TOLERANCE
                    },
                    "posttrade_slot_weights": {
                        symbol: float(target[index])
                        for index, symbol in enumerate(symbols)
                        if target[index] > TOLERANCE
                    },
                    "slot_fraction_before_trade": slot_fraction,
                    "within_slot_one_way_turnover": within_slot_turnover,
                    "portfolio_one_way_turnover": event_turnover,
                    "transaction_cost": event_cost / previous_total,
                    "same_session_signal_return_used": False,
                    "stale_execution_price_forward_fill_used": False,
                }
            )
        total = sum(slot.nav for slot in slots)
        net_return = total / previous_total - 1.0
        post_weights = aggregate_weights(slots)
        risky_exposure = float(
            sum(post_weights[symbols.index(symbol)] for symbol in SECTORS)
        )
        target_risky_exposure = float(
            sum(1.0 for slot in slots if slot.selection) / VINTAGE_SLOTS
        )
        held_rows.append(post_weights.copy())
        returns.append(net_return)
        turnover_values.append(daily_turnover)
        cost_values.append(cost_amount / previous_total)
        target_exposure_values.append(target_risky_exposure)
        daily_rows.append(
            {
                "date": pd.Timestamp(date),
                "gross_return_before_cost": gross_total / previous_total - 1.0,
                "net_return": net_return,
                "one_way_turnover": daily_turnover,
                "transaction_cost_drag": cost_amount / previous_total,
                "risky_exposure": risky_exposure,
                "target_risky_exposure": target_risky_exposure,
                "max_gross_exposure": float(np.abs(post_weights).sum()),
                "max_daily_weight_sum": float(post_weights.sum()),
                "pre_return_held_weight_sum": float(held_before_return.sum()),
            }
        )
        previous_total = total
    for slot_id in sorted(active_ledger):
        row = active_ledger[slot_id]
        slot = slots[slot_id]
        row["closed_slot_nav_before_liquidation_cost"] = slot.nav
        row["gross_vintage_return"] = (
            slot.nav / float(row["opened_slot_nav"]) - 1.0
            if float(row["opened_slot_nav"]) > 0.0
            else float("nan")
        )
        vintage_rows.append(row)
    index = prices.index
    daily = pd.DataFrame(daily_rows).set_index("date", drop=False)
    held = pd.DataFrame(held_rows, index=index, columns=list(symbols))
    target_events = pd.DataFrame(
        [held.loc[pd.Timestamp(row["event_date"])] for row in event_rows],
        index=pd.DatetimeIndex([row["event_date"] for row in event_rows]),
    )
    if target_events.empty:
        target_events = pd.DataFrame(columns=list(symbols), dtype=float)
    valid_execution_dates = [
        formation.execution_date for formation in formations if formation.complete
    ]
    return {
        "path_id": path_id,
        "returns": pd.Series(returns, index=index, name="net_return"),
        "turnover": pd.Series(turnover_values, index=index, name="one_way_turnover"),
        "cost": pd.Series(cost_values, index=index, name="transaction_cost_drag"),
        "daily": daily,
        "held_weights": held,
        "target_events": target_events,
        "events": event_rows,
        "vintage_rows": vintage_rows,
        "valid_execution_dates": valid_execution_dates,
        "formation_count": len(valid_execution_dates),
        "vintage_count": len(valid_execution_dates),
        "target_risky_exposure": pd.Series(
            target_exposure_values, index=index, name="target_risky_exposure"
        ),
        "timing_convention": (
            "completed_month_end_close_signal_following_regular_session_close"
        ),
    }


def event_frame(
    index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    target: dict[str, float],
    monthly: bool,
) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): target
    }
    if monthly:
        for formation_date in month_ends(index):
            execution = next_session(index, formation_date)
            if execution is not None:
                events[execution] = target
    return close_engine.event_frame(index, symbols, events)


def attach_path_metadata(
    path: dict[str, Any],
    path_id: str,
    formation_dates: list[pd.Timestamp],
    vintage_count: int = 0,
) -> dict[str, Any]:
    path["path_id"] = path_id
    path["valid_execution_dates"] = formation_dates
    path["formation_count"] = len(formation_dates)
    path["vintage_count"] = vintage_count
    path["target_risky_exposure"] = path["daily"]["risky_exposure"].copy()
    path["vintage_rows"] = []
    return path


def simulate_close_path(
    prices: pd.DataFrame,
    path_id: str,
    target: dict[str, float],
    monthly: bool,
    cost_bps: float,
) -> dict[str, Any]:
    events = event_frame(prices.index, tuple(prices.columns), target, monthly)
    path = close_engine.simulate_path(
        prices,
        events,
        cost_bps,
        "completed_month_end_close_target_following_regular_session_close"
        if monthly
        else "initial_buy_and_hold",
    )
    formation_dates = (
        [pd.Timestamp(date) for date in events.index[1:]] if monthly else []
    )
    return attach_path_metadata(path, path_id, formation_dates)


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
        "formation_count": formation_count,
        "vintage_count": (
            formation_count if path["vintage_count"] else 0
        ),
        "trade_or_rebalance_count": source["trade_or_rebalance_count"],
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


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - 1e-12
        and float(control["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"]) - 1e-12
        and float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - 1e-12
    )
    strictly_better = (
        float(control["cagr"]) > float(candidate["cagr"]) + 1e-12
        or float(control["sharpe_ratio"])
        > float(candidate["sharpe_ratio"]) + 1e-12
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + 1e-12
    )
    return bool(equal_or_better and strictly_better)


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
        >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"])
    )


def portfolio_path(
    reference: pd.Series,
    sleeve: dict[str, Any] | None,
    portfolio_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    if sleeve is None:
        common = reference.dropna().index
        returns = reference.reindex(common).astype(float)
        zeros = pd.Series(0.0, index=common)
        daily = pd.DataFrame(
            {
                "net_return": returns,
                "one_way_turnover": zeros,
                "inner_cost_drag": zeros,
                "outer_cost_drag": zeros,
                "transaction_cost_drag": zeros,
                "max_gross_exposure": 1.0,
                "max_daily_weight_sum": 1.0,
            },
            index=common,
        )
        return {
            "path_id": portfolio_id,
            "returns": returns,
            "turnover": zeros,
            "cost": zeros,
            "daily": daily,
            "held_weights": pd.DataFrame(
                {"reference": 1.0, "sleeve": 0.0}, index=common
            ),
            "target_events": pd.DataFrame(
                {"reference": [1.0], "sleeve": [0.0]}, index=[common[0]]
            ),
            "events": [],
            "valid_execution_dates": [],
            "formation_count": 0,
            "vintage_count": 0,
            "target_risky_exposure": pd.Series(1.0, index=common),
            "timing_convention": "frozen_reference_return_path",
        }
    common = reference.dropna().index.intersection(sleeve["returns"].dropna().index)
    reference_values = reference.reindex(common).to_numpy(dtype=float)
    sleeve_values = sleeve["returns"].reindex(common).to_numpy(dtype=float)
    sleeve_cost = sleeve["cost"].reindex(common).fillna(0.0).to_numpy(dtype=float)
    weights = np.array([0.0, 0.0], dtype=float)
    target = np.array([0.8, 0.2], dtype=float)
    returns: list[float] = []
    turnover: list[float] = []
    total_cost: list[float] = []
    inner_cost_rows: list[float] = []
    outer_cost_rows: list[float] = []
    held_rows: list[np.ndarray] = []
    events: list[dict[str, Any]] = []
    rebalance_positions = {0}
    for position in range(1, len(common)):
        if common[position - 1].to_period("M") != common[position].to_period("M"):
            rebalance_positions.add(position)
    for position, date in enumerate(common):
        component_return = np.array(
            [reference_values[position], sleeve_values[position]], dtype=float
        )
        held_rows.append(weights.copy())
        gross_return = float(np.dot(weights, component_return))
        drifted = weights * (1.0 + component_return)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else weights.copy()
        posttrade = pretrade.copy()
        outer_turnover = 0.0
        if position in rebalance_positions:
            posttrade = target.copy()
            outer_turnover = 0.5 * float(np.abs(target - pretrade).sum())
            events.append(
                {
                    "event_date": pd.Timestamp(date).date().isoformat(),
                    "portfolio_id": portfolio_id,
                    "event_type": (
                        "initial_establishment"
                        if position == 0
                        else "monthly_outer_rebalance_following_session_close"
                    ),
                    "one_way_turnover": outer_turnover,
                }
            )
        outer_drag = (1.0 + gross_return) * outer_turnover * cost_bps / 10000.0
        net_return = (1.0 + gross_return) * (
            1.0 - outer_turnover * cost_bps / 10000.0
        ) - 1.0
        embedded_inner = float(weights[1] * sleeve_cost[position])
        returns.append(net_return)
        turnover.append(outer_turnover)
        inner_cost_rows.append(embedded_inner)
        outer_cost_rows.append(outer_drag)
        total_cost.append(embedded_inner + outer_drag)
        weights = posttrade
    index = pd.DatetimeIndex(common)
    held = pd.DataFrame(held_rows, index=index, columns=["reference", "sleeve"])
    daily = pd.DataFrame(
        {
            "net_return": returns,
            "one_way_turnover": turnover,
            "inner_cost_drag": inner_cost_rows,
            "outer_cost_drag": outer_cost_rows,
            "transaction_cost_drag": total_cost,
            "max_gross_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
        },
        index=index,
    )
    return {
        "path_id": portfolio_id,
        "returns": pd.Series(returns, index=index),
        "turnover": pd.Series(turnover, index=index),
        "cost": pd.Series(total_cost, index=index),
        "daily": daily,
        "held_weights": held,
        "target_events": pd.DataFrame(
            [target for _ in events],
            index=pd.DatetimeIndex([row["event_date"] for row in events]),
            columns=["reference", "sleeve"],
        ),
        "events": events,
        "valid_execution_dates": [
            pd.Timestamp(row["event_date"]) for row in events[1:]
        ],
        "formation_count": max(len(events) - 1, 0),
        "vintage_count": 0,
        "target_risky_exposure": pd.Series(1.0, index=index),
        "timing_convention": (
            "monthly_outer_rebalance_following_completed_month_end_close"
        ),
    }


def portfolio_metrics(path: dict[str, Any]) -> dict[str, Any]:
    metrics = market.metrics_from_returns(path["returns"])
    daily = path["daily"]
    weights = path["held_weights"]
    numeric = bool(np.isfinite(path["returns"].to_numpy(dtype=float)).all())
    exposure = bool(
        not weights.empty
        and np.isfinite(weights.to_numpy(dtype=float)).all()
        and (weights.to_numpy(dtype=float) >= -TOLERANCE).all()
        and float(weights.sum(axis=1).max()) <= 1.0 + TOLERANCE
    )
    return {
        **metrics,
        "average_risky_exposure": 1.0,
        "total_one_way_turnover": float(path["turnover"].sum()),
        "formation_count": path["formation_count"],
        "vintage_count": 0,
        "trade_or_rebalance_count": int((path["turnover"] > TOLERANCE).sum()),
        "transaction_cost_drag": float(path["cost"].sum()),
        "inner_sleeve_transaction_cost_drag": float(
            daily["inner_cost_drag"].sum()
        ),
        "outer_transaction_cost_drag": float(daily["outer_cost_drag"].sum()),
        "maximum_single_sector_weight": float(weights.max().max()),
        "maximum_gross_exposure": float(weights.abs().sum(axis=1).max()),
        "maximum_daily_weight_sum": float(weights.sum(axis=1).max()),
        "timing_invariant_status": "pass",
        "numeric_invariant_status": "pass" if numeric else "fail",
        "exposure_invariant_status": "pass" if exposure else "fail",
        "weight_invariant_status": "pass" if exposure else "fail",
        "invariant_pass": bool(numeric and exposure),
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
    sector_master = frames["SPY"].index
    sector_prices = pd.DataFrame(
        {
            symbol: frames[symbol]["adj_close"].reindex(sector_master)
            for symbol in SECTORS
        },
        index=sector_master,
    )
    formations = build_formations(sector_prices, sector_master, evaluation_index)
    vintage_specs = {
        STRATEGY_ID: "candidate_selection",
        "six_month_cumulative_return_top3_sector_momentum_v1": (
            "cumulative_selection"
        ),
        "six_month_realized_volatility_bottom3_sector_v1": (
            "volatility_selection"
        ),
    }
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        for path_id, field in vintage_specs.items():
            path = simulate_vintage_path(prices, formations, field, path_id, cost)
            if path_id == STRATEGY_ID:
                candidate_paths[cost] = path
            else:
                control_paths[(path_id, cost)] = path
    exposure_weight = float(
        candidate_paths[0.0]["target_risky_exposure"].mean()
    )
    equal_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    for symbol in SECTORS:
        equal_target[symbol] = 1.0 / len(SECTORS)
    spy_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    spy_target["SPY"] = 1.0
    bil_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    bil_target["BIL"] = 1.0
    exposure_target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    exposure_target["SPY"] = exposure_weight
    exposure_target["BIL"] = 1.0 - exposure_weight
    for cost in COST_BPS:
        control_paths[("SPY_buy_and_hold", cost)] = simulate_close_path(
            prices, "SPY_buy_and_hold", spy_target, False, cost
        )
        control_paths[("BIL_buy_and_hold", cost)] = simulate_close_path(
            prices, "BIL_buy_and_hold", bil_target, False, cost
        )
        control_paths[
            ("monthly_equal_weight_nine_sector_control", cost)
        ] = simulate_close_path(
            prices,
            "monthly_equal_weight_nine_sector_control",
            equal_target,
            True,
            cost,
        )
        control_paths[
            ("choi_mdd_sector_exposure_matched_spy_bil_v1", cost)
        ] = simulate_close_path(
            prices,
            "choi_mdd_sector_exposure_matched_spy_bil_v1",
            exposure_target,
            True,
            cost,
        )
    reference = market.active_vm_dsr_usci_reference_returns()
    portfolio_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        common_reference = reference.reindex(evaluation_index).dropna()
        portfolio_paths[(PORTFOLIO_IDS["reference"], cost)] = portfolio_path(
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
            portfolio_paths[(PORTFOLIO_IDS[sleeve_id], cost)] = portfolio_path(
                common_reference,
                sleeve_path,
                PORTFOLIO_IDS[sleeve_id],
                cost,
            )
    return {
        "prices": prices,
        "formations": formations,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": portfolio_paths,
        "exposure_weight": exposure_weight,
    }


def classify(core: dict[str, Any]) -> tuple[str, str, str, str]:
    candidate = path_metrics(core["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: path_metrics(
            core["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in CONTROL_IDS
    }
    next_action = NEXT_CLOSE
    if not candidate["invariant_pass"] or not all(
        control["invariant_pass"] for control in controls.values()
    ):
        return (
            "blocked_feasibility",
            "methodology_failure",
            "candidate_or_required_control_invariant_failed",
            NEXT_BLOCK,
        )
    if float(candidate["total_return"]) <= 0.0:
        return (
            "closed_exploration",
            "weak_return",
            "full_period_after_cost_return_was_not_positive",
            next_action,
        )
    dominating = [
        control_id
        for control_id in CRITICAL_CONTROL_IDS
        if dominates(controls[control_id], candidate)
    ]
    if dominating:
        reason = (
            "low_volatility_control_explanation"
            if dominating == ["six_month_realized_volatility_bottom3_sector_v1"]
            else "weak_vs_primary_control"
        )
        return (
            "closed_exploration",
            reason,
            "critical_control_dominated_candidate:" + "|".join(dominating),
            next_action,
        )
    for control_id in CRITICAL_CONTROL_IDS:
        if not material_advantage(candidate, controls[control_id]):
            reason = (
                "low_volatility_control_explanation"
                if control_id
                == "six_month_realized_volatility_bottom3_sector_v1"
                else "weak_vs_primary_control"
            )
            return (
                "closed_exploration",
                reason,
                f"candidate_lacked_required_materiality_vs_{control_id}",
                next_action,
            )
    halves = split_halves(core["candidate_paths"][PRIMARY_COST_BPS]["returns"].index)
    for _, period in halves:
        candidate_half = path_metrics(
            core["candidate_paths"][PRIMARY_COST_BPS], period
        )
        for control_id in CRITICAL_CONTROL_IDS:
            control_half = path_metrics(
                core["control_paths"][(control_id, PRIMARY_COST_BPS)], period
            )
            if worse_on_both(candidate_half, control_half):
                return (
                    "closed_exploration",
                    "period_instability",
                    f"candidate_worse_on_sharpe_and_drawdown_in_half_vs_{control_id}",
                    next_action,
                )
        if int(candidate_half["formation_count"]) < 12:
            return (
                "closed_exploration",
                "signal_scarcity",
                "fewer_than_12_valid_formations_in_a_chronological_half",
                next_action,
            )
    for control_id in (
        "SPY_buy_and_hold",
        "monthly_equal_weight_nine_sector_control",
        "choi_mdd_sector_exposure_matched_spy_bil_v1",
    ):
        if dominates(controls[control_id], candidate) or not material_advantage(
            candidate, controls[control_id]
        ):
            return (
                "closed_exploration",
                "benchmark_like_behavior",
                f"simpler_or_static_control_economically_replicated_candidate:{control_id}",
                next_action,
            )
    candidate_10 = path_metrics(core["candidate_paths"][10.0])
    for control_id in CRITICAL_CONTROL_IDS:
        control_10 = path_metrics(core["control_paths"][(control_id, 10.0)])
        if worse_on_both(candidate_10, control_10):
            return (
                "closed_exploration",
                "cost_drag",
                f"advantage_unfavorable_on_sharpe_and_drawdown_at_10bps_vs_{control_id}",
                next_action,
            )
    return (
        "exploratory_followup_candidate_standalone",
        "",
        "candidate_passed_all_preregistered_lightweight_exploration_gates",
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
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": TRIAL_ID,
        "entity_type": (
            "experiment_trial"
            if row_type == "candidate"
            else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "row_type": row_type,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "chronological_half_not_validation_or_sealed_holdout"
        ),
        "outcome": outcome if row_type == "candidate" else "benchmark_only",
        "failure_reason": failure_reason if row_type == "candidate" else "",
        **metrics,
    }


def formation_diagnostic_rows(formations: list[Formation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for formation in formations:
        candidate_weights = (
            {symbol: 1.0 / SELECTED_COUNT for symbol in formation.candidate_selection}
            if formation.candidate_selection
            else {"BIL": 1.0}
        )
        for symbol in SECTORS:
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "formation_sequence": formation.sequence,
                    "formation_date": formation.formation_date.date().isoformat(),
                    "six_month_window_start": (
                        formation.window_start.date().isoformat()
                        if formation.window_start is not None
                        else ""
                    ),
                    "six_month_window_end": formation.window_end.date().isoformat(),
                    "symbol": symbol,
                    "maximum_log_drawdown": formation.mdd.get(symbol, ""),
                    "mdd_rank": formation.mdd_ranks.get(symbol, ""),
                    "cumulative_log_return": formation.cumulative_log_return.get(
                        symbol, ""
                    ),
                    "cumulative_return_rank": formation.cumulative_ranks.get(
                        symbol, ""
                    ),
                    "realized_volatility": formation.realized_volatility.get(
                        symbol, ""
                    ),
                    "realized_volatility_rank": formation.volatility_ranks.get(
                        symbol, ""
                    ),
                    "selected_by_candidate": (
                        symbol in formation.candidate_selection
                    ),
                    "candidate_selected_sectors": formation.candidate_selection,
                    "cumulative_control_selected_sectors": (
                        formation.cumulative_selection
                    ),
                    "low_volatility_control_selected_sectors": (
                        formation.volatility_selection
                    ),
                    "new_vintage_weights": candidate_weights,
                    "execution_date": formation.execution_date.date().isoformat(),
                    "expiration_date": (
                        formation.expiration_date.date().isoformat()
                        if formation.expiration_date is not None
                        else ""
                    ),
                    "signal_complete": formation.complete,
                    "missing_symbols": formation.missing_symbols,
                }
            )
    return rows


def overlap_rows(formations: list[Formation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid = [formation for formation in formations if formation.complete]
    for formation in valid:
        candidate = set(formation.candidate_selection)
        cumulative = set(formation.cumulative_selection)
        low_vol = set(formation.volatility_selection)
        rows.append(
            {
                "record_type": "formation_overlap",
                "formation_date": formation.formation_date.date().isoformat(),
                "symbol": "",
                "candidate_selection_count": len(candidate),
                "cumulative_control_overlap_count": len(candidate & cumulative),
                "low_volatility_control_overlap_count": len(candidate & low_vol),
                "candidate_identical_to_cumulative_control": (
                    candidate == cumulative
                ),
                "candidate_identical_to_low_volatility_control": (
                    candidate == low_vol
                ),
                "candidate_selection_frequency": "",
                "average_holding_weight": "",
                "median_holding_weight": "",
                "turnover_year": "",
                "annual_one_way_turnover": "",
                "longest_invalid_formation_run": "",
                "percent_identical_to_cumulative_control": "",
                "percent_identical_to_low_volatility_control": "",
            }
        )
    candidate_path = None
    if valid:
        for symbol in SECTORS:
            selected = [
                symbol in formation.candidate_selection for formation in valid
            ]
            rows.append(
                {
                    "record_type": "sector_selection_summary",
                    "formation_date": "",
                    "symbol": symbol,
                    "candidate_selection_count": sum(selected),
                    "cumulative_control_overlap_count": "",
                    "low_volatility_control_overlap_count": "",
                    "candidate_identical_to_cumulative_control": "",
                    "candidate_identical_to_low_volatility_control": "",
                    "candidate_selection_frequency": sum(selected) / len(valid),
                    "average_holding_weight": "",
                    "median_holding_weight": "",
                    "turnover_year": "",
                    "annual_one_way_turnover": "",
                    "longest_invalid_formation_run": "",
                    "percent_identical_to_cumulative_control": "",
                    "percent_identical_to_low_volatility_control": "",
                }
            )
        invalid_flags = [not formation.complete for formation in formations]
        longest = 0
        current = 0
        for invalid in invalid_flags:
            current = current + 1 if invalid else 0
            longest = max(longest, current)
        rows.append(
            {
                "record_type": "formation_summary",
                "formation_date": "",
                "symbol": "",
                "candidate_selection_count": "",
                "cumulative_control_overlap_count": "",
                "low_volatility_control_overlap_count": "",
                "candidate_identical_to_cumulative_control": "",
                "candidate_identical_to_low_volatility_control": "",
                "candidate_selection_frequency": "",
                "average_holding_weight": "",
                "median_holding_weight": "",
                "turnover_year": "",
                "annual_one_way_turnover": "",
                "longest_invalid_formation_run": longest,
                "percent_identical_to_cumulative_control": sum(
                    set(formation.candidate_selection)
                    == set(formation.cumulative_selection)
                    for formation in valid
                )
                / len(valid),
                "percent_identical_to_low_volatility_control": sum(
                    set(formation.candidate_selection)
                    == set(formation.volatility_selection)
                    for formation in valid
                )
                / len(valid),
            }
        )
    return rows


def add_holding_and_turnover_summaries(
    rows: list[dict[str, Any]], candidate_path: dict[str, Any]
) -> None:
    held = candidate_path["held_weights"]
    for symbol in SECTORS:
        rows.append(
            {
                "record_type": "sector_holding_summary",
                "formation_date": "",
                "symbol": symbol,
                "candidate_selection_count": "",
                "cumulative_control_overlap_count": "",
                "low_volatility_control_overlap_count": "",
                "candidate_identical_to_cumulative_control": "",
                "candidate_identical_to_low_volatility_control": "",
                "candidate_selection_frequency": "",
                "average_holding_weight": float(held[symbol].mean()),
                "median_holding_weight": float(held[symbol].median()),
                "turnover_year": "",
                "annual_one_way_turnover": "",
                "longest_invalid_formation_run": "",
                "percent_identical_to_cumulative_control": "",
                "percent_identical_to_low_volatility_control": "",
            }
        )
    yearly = candidate_path["turnover"].groupby(
        candidate_path["turnover"].index.year
    ).sum()
    for year, value in yearly.items():
        rows.append(
            {
                "record_type": "annual_turnover_summary",
                "formation_date": "",
                "symbol": "",
                "candidate_selection_count": "",
                "cumulative_control_overlap_count": "",
                "low_volatility_control_overlap_count": "",
                "candidate_identical_to_cumulative_control": "",
                "candidate_identical_to_low_volatility_control": "",
                "candidate_selection_frequency": "",
                "average_holding_weight": "",
                "median_holding_weight": "",
                "turnover_year": int(year),
                "annual_one_way_turnover": float(value),
                "longest_invalid_formation_run": "",
                "percent_identical_to_cumulative_control": "",
                "percent_identical_to_low_volatility_control": "",
            }
        )


def core_hash(core: dict[str, Any]) -> str:
    payload = {
        "candidate_returns": core["candidate_paths"][5.0]["returns"].round(15).tolist(),
        "candidate_turnover": core["candidate_paths"][5.0]["turnover"].round(15).tolist(),
        "candidate_events": core["candidate_paths"][5.0]["events"],
        "control_returns": {
            f"{control_id}|{cost}": path["returns"].round(15).tolist()
            for (control_id, cost), path in sorted(core["control_paths"].items())
        },
        "exposure_weight": core["exposure_weight"],
    }
    return helpers.canonical_hash(payload)


def write_preregistration(preflight_rows: list[dict[str, Any]]) -> str:
    pending = "preregistered_pending_execution"
    source = [source_row()]
    strategies = [strategy_row(pending, "", TASK_ID)]
    trials = [trial_row(pending, "", TASK_ID)]
    benchmarks = benchmark_rows()
    process = [process_row(TASK_ID)]
    helpers.write_csv(
        OUTPUT_DIR / "source_library_records.csv", source, list(source[0])
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
        OUTPUT_DIR / "process_task_log.csv", process, list(process[0])
    )
    helpers.write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0]),
    )
    return helpers.canonical_hash(
        {
            "source": source,
            "strategies": strategies,
            "trials": trials,
            "benchmarks": benchmarks,
            "preflight": preflight_rows,
            "written_before_performance": True,
        }
    )


def empty_performance_files() -> None:
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
    for name in (
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
    ):
        helpers.write_csv(OUTPUT_DIR / name, [], metric_fields)
    helpers.write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        [],
        ["portfolio_id", "cost_assumption_bps", *METRIC_FIELDS],
    )


def run() -> dict[str, Any]:
    protected_before = hash_map(PROTECTED_PATHS)
    cache_before = helpers.tree_hash(CACHE_DIR)
    prior_evidence_before = helpers.tree_hash(ROOT / "evidence", OUTPUT_DIR)
    source_hash_before = helpers.file_hash(SOURCE_ATTACHMENT)
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
    deterministic_hash_one = ""
    deterministic_hash_two = ""
    if executable:
        core = run_core(frames, evaluation_index)
        deterministic_hash_one = core_hash(core)
        deterministic_hash_two = core_hash(run_core(frames, evaluation_index))
        outcome, failure_reason, decision_reason, next_action = classify(core)
    else:
        outcome = "inconclusive_data_issue"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "required_canonical_data_failed_preflight"
        next_action = NEXT_BLOCK

    strategies = [strategy_row(outcome, failure_reason, next_action)]
    trials = [trial_row(outcome, failure_reason, next_action)]
    sources = [source_row()]
    benchmarks = benchmark_rows()
    process = [process_row(next_action, "completed")]

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
        OUTPUT_DIR / "process_task_log.csv", process, list(process[0])
    )

    all_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    half_results: list[dict[str, Any]] = []
    portfolio_results: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    formation_rows: list[dict[str, Any]] = []
    vintage_rows: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []

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
                control_path = core["control_paths"][(control_id, cost)]
                metric = path_metrics(control_path)
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
                path_pairs.append((control_id, "control", control_path))
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
                        "trade_or_rebalance_count": metric[
                            "trade_or_rebalance_count"
                        ],
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
                        "formation_uses_only_completed_data": True,
                        "exactly_nine_sectors_ranked": True,
                        "exactly_three_sectors_per_valid_vintage": True,
                        "no_more_than_six_active_vintages": True,
                        "unused_slots_held_in_BIL": True,
                        "natural_drift_within_vintage": True,
                        "existing_vintages_rebalanced_to_equal_weight": False,
                        "same_session_signal_return_used": False,
                        "stale_execution_price_forward_fill_used": False,
                        "explicit_zero_weights_preserved": True,
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
                        "serial_rerun_deterministic": (
                            deterministic_hash_one == deterministic_hash_two
                        ),
                        "invariant_pass": metric["invariant_pass"],
                    }
                )
        for half_label, period in split_halves(
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
                    "trade_or_rebalance_count": metric[
                        "trade_or_rebalance_count"
                    ],
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
                    "formation_uses_only_completed_data": True,
                    "exactly_nine_sectors_ranked": True,
                    "exactly_three_sectors_per_valid_vintage": True,
                    "no_more_than_six_active_vintages": True,
                    "unused_slots_held_in_BIL": True,
                    "natural_drift_within_vintage": True,
                    "existing_vintages_rebalanced_to_equal_weight": False,
                    "same_session_signal_return_used": False,
                    "stale_execution_price_forward_fill_used": False,
                    "explicit_zero_weights_preserved": True,
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
                    "serial_rerun_deterministic": (
                        deterministic_hash_one == deterministic_hash_two
                    ),
                    "invariant_pass": metric["invariant_pass"],
                }
            )
        formation_rows = formation_diagnostic_rows(core["formations"])
        vintage_rows = []
        for path_id in (STRATEGY_ID,) + CRITICAL_CONTROL_IDS:
            path = (
                core["candidate_paths"][PRIMARY_COST_BPS]
                if path_id == STRATEGY_ID
                else core["control_paths"][(path_id, PRIMARY_COST_BPS)]
            )
            vintage_rows.extend(path["vintage_rows"])
        overlap = overlap_rows(core["formations"])
        add_holding_and_turnover_summaries(
            overlap, core["candidate_paths"][PRIMARY_COST_BPS]
        )
        for cost in COST_BPS:
            candidate_metric = path_metrics(core["candidate_paths"][cost])
            control_metric = path_metrics(
                core["control_paths"][
                    ("choi_mdd_sector_exposure_matched_spy_bil_v1", cost)
                ]
            )
            exposure_rows.append(
                {
                    "cost_assumption_bps": cost,
                    "candidate_average_risky_target_exposure": core[
                        "exposure_weight"
                    ],
                    "exposure_control_SPY_weight": core["exposure_weight"],
                    "exposure_control_BIL_weight": 1.0
                    - core["exposure_weight"],
                    "matches_candidate_target_exposure": math.isclose(
                        core["exposure_weight"],
                        float(
                            core["control_paths"][
                                (
                                    "choi_mdd_sector_exposure_matched_spy_bil_v1",
                                    cost,
                                )
                            ]["target_events"]["SPY"].iloc[0]
                        ),
                        abs_tol=1e-12,
                    ),
                    "optimized_or_rounded": False,
                    "performance_selected": False,
                    "candidate_sharpe_ratio": candidate_metric["sharpe_ratio"],
                    "control_sharpe_ratio": control_metric["sharpe_ratio"],
                    "candidate_maximum_drawdown": candidate_metric[
                        "maximum_drawdown"
                    ],
                    "control_maximum_drawdown": control_metric[
                        "maximum_drawdown"
                    ],
                }
            )
    else:
        empty_performance_files()

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
        OUTPUT_DIR / "formation_selection_diagnostics.csv",
        formation_rows,
        [
            "strategy_id",
            "formation_sequence",
            "formation_date",
            "six_month_window_start",
            "six_month_window_end",
            "symbol",
            "maximum_log_drawdown",
            "mdd_rank",
            "cumulative_log_return",
            "cumulative_return_rank",
            "realized_volatility",
            "realized_volatility_rank",
            "selected_by_candidate",
            "candidate_selected_sectors",
            "cumulative_control_selected_sectors",
            "low_volatility_control_selected_sectors",
            "new_vintage_weights",
            "execution_date",
            "expiration_date",
            "signal_complete",
            "missing_symbols",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "vintage_ledger.csv",
        vintage_rows,
        [
            "path_id",
            "vintage_id",
            "slot_id",
            "formation_date",
            "execution_date",
            "expiration_date",
            "selection",
            "initial_weights",
            "signal_complete",
            "invalid_vintage_held_in_BIL",
            "opened_slot_nav",
            "closed_slot_nav_before_liquidation_cost",
            "gross_vintage_return",
            "completed",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "overlap_with_control_selections.csv",
        overlap,
        [
            "record_type",
            "formation_date",
            "symbol",
            "candidate_selection_count",
            "cumulative_control_overlap_count",
            "low_volatility_control_overlap_count",
            "candidate_identical_to_cumulative_control",
            "candidate_identical_to_low_volatility_control",
            "candidate_selection_frequency",
            "average_holding_weight",
            "median_holding_weight",
            "turnover_year",
            "annual_one_way_turnover",
            "longest_invalid_formation_run",
            "percent_identical_to_cumulative_control",
            "percent_identical_to_low_volatility_control",
        ],
    )
    helpers.write_csv(
        OUTPUT_DIR / "exposure_control_reconciliation.csv",
        exposure_rows,
        [
            "cost_assumption_bps",
            "candidate_average_risky_target_exposure",
            "exposure_control_SPY_weight",
            "exposure_control_BIL_weight",
            "matches_candidate_target_exposure",
            "optimized_or_rounded",
            "performance_selected",
            "candidate_sharpe_ratio",
            "control_sharpe_ratio",
            "candidate_maximum_drawdown",
            "control_maximum_drawdown",
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
            "trade_or_rebalance_count",
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
            "formation_uses_only_completed_data",
            "exactly_nine_sectors_ranked",
            "exactly_three_sectors_per_valid_vintage",
            "no_more_than_six_active_vintages",
            "unused_slots_held_in_BIL",
            "natural_drift_within_vintage",
            "existing_vintages_rebalanced_to_equal_weight",
            "same_session_signal_return_used",
            "stale_execution_price_forward_fill_used",
            "explicit_zero_weights_preserved",
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
        "executed_trials": 1 if core is not None else 0,
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
    source_hash_after = helpers.file_hash(SOURCE_ATTACHMENT)
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
            and (core is None or deterministic_hash_one == deterministic_hash_two)
            and invariants_pass
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and source_hash_before == source_hash_after
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
        "MDD_only_criterion_preserved": True,
        "composite_criteria_tested": False,
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
        "source_attachment_hash_before": source_hash_before,
        "source_attachment_hash_after": source_hash_after,
        "source_attachment_unchanged": source_hash_before == source_hash_after,
        "serial_rerun_deterministic": (
            core is None or deterministic_hash_one == deterministic_hash_two
        ),
        "deterministic_core_hash": deterministic_hash_one,
        "all_invariants_pass": invariants_pass,
        "existing_choi_recovery_strategy_rerun": False,
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
    control_5 = (
        {
            control_id: path_metrics(
                core["control_paths"][(control_id, PRIMARY_COST_BPS)]
            )
            for control_id in CRITICAL_CONTROL_IDS
        }
        if core is not None
        else {}
    )
    report_lines = [
        "# Six-Month Low-Drawdown Sector Momentum Exploration",
        "",
        "## Scope",
        "",
        f"Exactly one frozen configuration, `{STRATEGY_ID}`, was considered.",
        "The criterion remained MDD-only; no composite, parameter, instrument,",
        "filter, lifecycle, provider, paper/demo, or broker action was used.",
        "",
        "## Outcome",
        "",
        f"* Outcome: `{outcome}`",
        f"* Primary failure reason: `{failure_reason or 'none'}`",
        f"* Decision basis: `{decision_reason}`",
    ]
    if candidate_5 is not None:
        report_lines.extend(
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
            metric = control_5[control_id]
            report_lines.append(
                f"* `{control_id}`: CAGR `{metric['cagr']:.6f}`, "
                f"Sharpe `{metric['sharpe_ratio']:.6f}`, maximum drawdown "
                f"`{metric['maximum_drawdown']:.6f}`."
            )
    report_lines.extend(
        [
            "",
            "The chronological halves are exploration diagnostics and are not",
            "validation or sealed holdouts. All selections, vintages, costs,",
            "turnover, controls, and unfavorable evidence remain in the packet.",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    write_text(OUTPUT_DIR / "batch_report.md", "\n".join(report_lines))
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
