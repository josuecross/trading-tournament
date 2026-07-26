from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


BATCH_ID = "fast_source_library_batch_v6"
MODE = "fast-progress"
STAGE = "exploration"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v3"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_PACKET_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / SOURCE_LIBRARY_ID
    / "latest"
)
SOURCE_PACKET_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\610a14bd-9271-4fd7-a886-c4334e04e773\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9

NEXT_REVIEW = "direction_owner_review_fast_source_library_batch_v6"
NEXT_ALL_CLOSED = "evaluate_deferred_v3_online_portfolio_candidates_v1"
NEXT_BLOCKED = "direction_owner_review_fast_source_library_batch_v6_block_v1"

SECTOR_UNIVERSE = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
COUNTRY_UNIVERSE = (
    "EWA",
    "EWC",
    "EWG",
    "EWH",
    "EWI",
    "EWJ",
    "EWL",
    "EWM",
    "EWN",
    "EWP",
    "EWS",
    "EWT",
    "EWU",
    "EWW",
    "EWY",
    "EWZ",
)

EXPECTED_STRATEGY_IDS = (
    "choi_recovery_sector_contrarian_6x6_v1",
    "li_hoi_olmar5_sector_etf_v1",
    "dogs_world_country_reversal_5x5_v1",
    "george_hwang_52week_high_sector_v1",
)

EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS = {
    "george_hwang_52week_high_sector_v1": (
        "six_month_total_return_top3_overlapping"
    ),
}

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)

FORBIDDEN_FLAGS = {
    "external_source_research": False,
    "source_rule_completion": False,
    "parameter_tuning_or_grid": False,
    "result_driven_universe_change": False,
    "validation_or_robustness": False,
    "promotion_or_paper_demo_review": False,
    "lifecycle_state_change": False,
    "paper_demo_activation": False,
    "broker_account_order_or_real_money_action": False,
    "PAMR_or_ANTICOR_candidate_created": False,
    "ANGL_data_lane_reopened": False,
}

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_standalone",
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}

ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "weak_return",
    "excess_drawdown",
    "cost_drag",
    "turnover_drag",
    "signal_scarcity",
    "period_instability",
    "benchmark_like_behavior",
    "data_or_comparability_failure",
    "methodology_failure",
    "data_unavailable",
    "capability_missing",
    "duplicate_or_redundant",
    "too_risky",
    "overfit_or_unstable",
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    family_id: str
    display_name: str
    strategy_architecture: str
    source_record_id: str
    route: str
    universe: tuple[str, ...]
    required_symbols: tuple[str, ...]
    controls: tuple[str, ...]
    portfolio_controls: tuple[str, ...]
    parameters: dict[str, Any]
    frozen_rule: str

    @property
    def trial_id(self) -> str:
        return f"fast_source_v6__{self.strategy_id}__canonical"

    @property
    def source_or_research_lineage(self) -> str:
        return f"{SOURCE_LIBRARY_ID}:{self.source_record_id}"


CARDS = (
    CandidateCard(
        strategy_id="choi_recovery_sector_contrarian_6x6_v1",
        family_id="cross_sectional_recovery_mean_reversion",
        display_name="Six-Week Sector Recovery Contrarian",
        strategy_architecture="cross_sectional_overlapping_vintage_sector_reversal",
        source_record_id="src_choi_recovery_sector_contrarian_6x6_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE + ("BIL", "SPY"),
        controls=(
            "six_week_cumulative_return_bottom3_overlapping",
            "weekly_equal_weight_nine_sector",
            "SPY_buy_and_hold",
        ),
        portfolio_controls=(
            "six_week_cumulative_return_bottom3_overlapping",
            "weekly_equal_weight_nine_sector",
        ),
        parameters={
            "formation_horizon_complete_trading_weeks": 6,
            "selected_count": 3,
            "holding_weeks": 6,
            "vintage_weight": 1.0 / 6.0,
            "tie_break": "lexical_ticker_order",
            "missing_signal_asset": "BIL",
            "short_leg": False,
        },
        frozen_rule=(
            "At each weekly formation close use the preceding six complete trading weeks; "
            "rank the log recovery from each asset's maximum-drawdown trough to period end "
            "ascending; put one sixth of capital into an equal-weight vintage of the bottom "
            "three for six weeks; maintain six overlapping vintages; use BIL for an "
            "uncalculable vintage; execute at the following session close."
        ),
    ),
    CandidateCard(
        strategy_id="li_hoi_olmar5_sector_etf_v1",
        family_id="online_moving_average_reversion",
        display_name="OLMAR-5 Sector ETF Allocation",
        strategy_architecture="daily_online_moving_average_reversion_portfolio",
        source_record_id="src_li_hoi_olmar5_sector_v1",
        route="diversifier",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE,
        controls=(
            "daily_uniform_constant_rebalanced_nine_sector",
            "initial_equal_weight_buy_and_hold_nine_sector",
            "simple_MA5_distance_nine_sector",
        ),
        portfolio_controls=(
            "daily_uniform_constant_rebalanced_nine_sector",
            "initial_equal_weight_buy_and_hold_nine_sector",
            "simple_MA5_distance_nine_sector",
        ),
        parameters={
            "moving_average_window": 5,
            "epsilon": 10.0,
            "initial_weights": "one_ninth_each",
            "projection": "nonnegative_fully_invested_simplex",
        },
        frozen_rule=(
            "Initialize one ninth per sector; predict each next price relative as MA5/P; "
            "apply the OLMAR closed-form epsilon-10 update and project to the nonnegative "
            "fully invested simplex; retain weights when the denominator is zero; use "
            "equal weights before warmup; execute at the following session close."
        ),
    ),
    CandidateCard(
        strategy_id="dogs_world_country_reversal_5x5_v1",
        family_id="country_long_horizon_reversal",
        display_name="Dogs of the World Country Reversal",
        strategy_architecture="annual_country_loser_selection_overlapping_vintages",
        source_record_id="src_dogs_world_country_reversal_5x5_v1",
        route="diversifier",
        universe=COUNTRY_UNIVERSE,
        required_symbols=COUNTRY_UNIVERSE + ("ACWI",),
        controls=(
            "annual_equal_weight_frozen_country_universe",
            "ACWI_buy_and_hold",
            "prior_year_bottom5_one_year_nonoverlapping",
        ),
        portfolio_controls=(
            "annual_equal_weight_frozen_country_universe",
            "prior_year_bottom5_one_year_nonoverlapping",
        ),
        parameters={
            "formation_frequency": "calendar_year_end",
            "selected_count": 5,
            "holding_years": 5,
            "maximum_vintages": 5,
            "initial_ramp": "equal_capital_among_active_vintages",
            "tie_break": "lexical_ticker_order",
        },
        frozen_rule=(
            "At each calendar year-end rank the sixteen frozen country ETFs by completed "
            "calendar-year total return ascending; select five; hold each equal-weight "
            "vintage for five calendar years with up to five annual vintages and equal "
            "capital across active vintages during ramp-up; execute at the first following "
            "session close; missing universe data blocks the candidate."
        ),
    ),
    CandidateCard(
        strategy_id="george_hwang_52week_high_sector_v1",
        family_id="industry_anchor_momentum",
        display_name="Sector Nearness-to-52-Week-High Rotation",
        strategy_architecture="monthly_sector_anchor_momentum_overlapping_vintages",
        source_record_id="src_george_hwang_sector_52week_high_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE + ("BIL", "SPY"),
        controls=(
            "six_month_total_return_top3_overlapping",
            "monthly_equal_weight_nine_sector",
            "SPY_buy_and_hold",
        ),
        portfolio_controls=(
            "six_month_total_return_top3_overlapping",
            "monthly_equal_weight_nine_sector",
        ),
        parameters={
            "high_lookback_sessions": 252,
            "selected_count": 3,
            "holding_months": 6,
            "maximum_vintages": 6,
            "vintage_weight": 1.0 / 6.0,
            "warmup_asset": "BIL",
            "tie_break": "lexical_ticker_order",
        },
        frozen_rule=(
            "At every month-end rank sectors by current close divided by the maximum close "
            "over the inclusive trailing 252 sessions; select the top three; put one sixth "
            "of capital into an equal-weight vintage held six months; maintain six "
            "overlapping vintages; hold BIL before warmup; execute at next session close."
        ),
    ),
)


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def cache_files() -> list[Path]:
    return [path for path in sorted((ROOT / "data" / "cache").glob("*")) if path.is_file()]


def prior_evidence_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted((ROOT / "evidence").rglob("*")):
        if not path.is_file():
            continue
        if OUTPUT_DIR.resolve() in path.resolve().parents:
            continue
        files.append(path)
    return files


def aggregate_hash(hashes: dict[str, str]) -> str:
    material = "\n".join(f"{path}|{value}" for path, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_cards() -> None:
    if tuple(card.strategy_id for card in CARDS) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Frozen candidate scope drift")
    if len({card.family_id for card in CARDS}) != 4:
        raise RuntimeError("Expected four distinct frozen families")
    if any("PAMR" in card.frozen_rule or "ANTICOR" in card.frozen_rule for card in CARDS):
        raise RuntimeError("Deferred online candidates entered V6 scope")
    for card in CARDS:
        required = (
            card.strategy_id,
            card.family_id,
            card.display_name,
            card.strategy_architecture,
            card.source_record_id,
            card.route,
            card.universe,
            card.controls,
            card.parameters,
            card.frozen_rule,
        )
        if any(value in ("", None, (), {}) for value in required):
            raise RuntimeError(f"Incomplete frozen metadata for {card.strategy_id}")


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def raw_cache_validation(symbol: str) -> dict[str, Any]:
    path = cache_path(symbol)
    base = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_exists": path.exists(),
        "canonical_hash": file_hash(path),
        "normal_backtester_interface": (
            "fast_price_volume_discovery_batch_v2.load_adjusted_ohlcv"
        ),
    }
    if not path.exists():
        return {
            **base,
            "row_count": 0,
            "first_valid_date": "",
            "last_valid_date": "",
            "ordered_unique_dates": False,
            "finite_positive_prices": False,
            "valid_ohlc_relationships": False,
            "canonical_adjustment_compatible": False,
            "preflight_status": "fail",
            "failure_reason": "data_unavailable",
        }
    raw = pd.read_csv(path)
    required = {
        "date",
        "raw_open",
        "raw_high",
        "raw_low",
        "raw_close",
        "raw_adj_close",
        "raw_volume",
        "adjustment_factor",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    }
    missing = sorted(required - set(raw.columns))
    dates = pd.to_datetime(raw.get("date"), errors="coerce")
    ordered = bool(
        dates.notna().all()
        and dates.is_monotonic_increasing
        and not dates.duplicated().any()
    )
    numeric = (
        raw[["open", "high", "low", "close", "adj_close", "volume"]].apply(
            pd.to_numeric, errors="coerce"
        )
        if not missing
        else pd.DataFrame()
    )
    finite_positive = bool(
        not numeric.empty
        and np.isfinite(numeric.to_numpy(dtype=float)).all()
        and (numeric[["open", "high", "low", "close", "adj_close"]] > 0.0)
        .all()
        .all()
        and (numeric["volume"] >= 0.0).all()
    )
    valid_ohlc = bool(
        not numeric.empty
        and (
            numeric["high"] + 1e-10
            >= numeric[["open", "close", "low"]].max(axis=1)
        ).all()
        and (
            numeric["low"] - 1e-10
            <= numeric[["open", "close", "high"]].min(axis=1)
        ).all()
    )
    adjustment_ok = False
    if not missing:
        factor = pd.to_numeric(raw["adjustment_factor"], errors="coerce")
        checks = []
        for field in ("open", "high", "low", "close"):
            expected = pd.to_numeric(raw[f"raw_{field}"], errors="coerce") * factor
            actual = pd.to_numeric(raw[field], errors="coerce")
            checks.append(np.isclose(actual, expected, rtol=1e-8, atol=1e-8).all())
        checks.append(
            np.isclose(
                pd.to_numeric(raw["adj_close"], errors="coerce"),
                pd.to_numeric(raw["raw_adj_close"], errors="coerce"),
                rtol=1e-8,
                atol=1e-8,
            ).all()
        )
        adjustment_ok = bool(all(checks))
    loaded = market.load_adjusted_ohlcv(symbol)
    loader_ok = bool(not loaded.empty and len(loaded) == len(raw))
    passed = bool(
        not missing
        and ordered
        and finite_positive
        and valid_ohlc
        and adjustment_ok
        and loader_ok
    )
    return {
        **base,
        "row_count": int(len(raw)),
        "first_valid_date": (
            dates.min().date().isoformat() if dates.notna().any() else ""
        ),
        "last_valid_date": (
            dates.max().date().isoformat() if dates.notna().any() else ""
        ),
        "ordered_unique_dates": ordered,
        "finite_positive_prices": finite_positive,
        "valid_ohlc_relationships": valid_ohlc,
        "canonical_adjustment_compatible": bool(adjustment_ok and loader_ok),
        "missing_required_fields": missing,
        "preflight_status": "pass" if passed else "fail",
        "failure_reason": "" if passed else "data_or_comparability_failure",
    }


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    required = tuple(dict.fromkeys(symbol for card in CARDS for symbol in card.required_symbols))
    symbol_rows = {symbol: raw_cache_validation(symbol) for symbol in required}
    missing_country = [
        symbol
        for symbol in COUNTRY_UNIVERSE
        if symbol_rows[symbol]["preflight_status"] != "pass"
    ]
    acwi_blocked = symbol_rows["ACWI"]["preflight_status"] != "pass"
    data_tasks: list[dict[str, Any]] = []
    if missing_country and acwi_blocked:
        # ACWI is a required control and is not a country ETF. The source-frozen
        # comparison therefore cannot be made executable by the narrow country-ETF
        # acquisition exception, so no low-information provider call is made.
        pass

    rows: list[dict[str, Any]] = []
    for card in CARDS:
        failed = [
            symbol
            for symbol in card.required_symbols
            if symbol_rows[symbol]["preflight_status"] != "pass"
        ]
        frames = {
            symbol: market.load_adjusted_ohlcv(symbol)
            for symbol in card.required_symbols
            if symbol_rows[symbol]["preflight_status"] == "pass"
        }
        common_start = (
            max(frame.index.min() for frame in frames.values())
            if len(frames) == len(card.required_symbols)
            else None
        )
        common_end = (
            min(frame.index.max() for frame in frames.values())
            if len(frames) == len(card.required_symbols)
            else None
        )
        common_count = 0
        if common_start is not None and common_end is not None:
            common = None
            for frame in frames.values():
                dates = set(frame.loc[common_start:common_end].index)
                common = dates if common is None else common & dates
            common_count = len(common or set())
        for symbol in card.required_symbols:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    **symbol_rows[symbol],
                    "candidate_common_start": (
                        common_start.date().isoformat() if common_start is not None else ""
                    ),
                    "candidate_common_end": (
                        common_end.date().isoformat() if common_end is not None else ""
                    ),
                    "candidate_common_session_count": common_count,
                    "candidate_missing_symbols": failed,
                    "candidate_preflight_status": "pass" if not failed else "fail",
                    "bounded_provider_attempt_authorized": symbol in COUNTRY_UNIVERSE,
                    "bounded_provider_attempt_count": 0,
                    "provider_attempt_skip_reason": (
                        "required_ACWI_control_missing_and_not_within_country_ETF_exception"
                        if failed and acwi_blocked
                        else ""
                    ),
                }
            )
    return rows, symbol_rows, data_tasks


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(signal_date), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def last_dates_by_period(index: pd.DatetimeIndex, frequency: str) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period(frequency), index=index)
    mask = periods.ne(periods.shift(-1)).fillna(True)
    return [pd.Timestamp(value) for value in index[mask]]


def equal_target(symbols: tuple[str, ...]) -> dict[str, float]:
    return {symbol: 1.0 / len(symbols) for symbol in symbols}


def target_from_vintages(
    vintages: Iterable[dict[str, Any]],
    symbols: tuple[str, ...],
    slot_count: int,
) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in symbols}
    vintage_list = list(vintages)
    if not vintage_list:
        return target
    for vintage in vintage_list:
        for symbol, weight in vintage["weights"].items():
            target[symbol] += float(weight) / float(slot_count)
    return target


def events_for_evaluation(
    all_events: dict[pd.Timestamp, dict[str, float]],
    evaluation_index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    default_target: dict[str, float],
) -> pd.DataFrame:
    start = pd.Timestamp(evaluation_index[0])
    prior = [date for date in all_events if pd.Timestamp(date) <= start]
    initial = all_events[max(prior)] if prior else default_target
    selected: dict[pd.Timestamp, dict[str, float]] = {start: initial}
    valid = set(evaluation_index)
    for date, target in sorted(all_events.items()):
        date_value = pd.Timestamp(date)
        if date_value > start and date_value in valid:
            selected[date_value] = target
    return accounting.event_frame(evaluation_index, symbols, selected)


def weekly_recovery_inputs(
    prices: pd.DataFrame,
    formation_date: pd.Timestamp,
) -> tuple[dict[str, float], dict[str, str], dict[str, float]] | None:
    periods = prices.index.to_period("W-FRI")
    formation_period = pd.Timestamp(formation_date).to_period("W-FRI")
    prior_periods = sorted(set(periods[periods <= formation_period]))
    if len(prior_periods) < 6:
        return None
    selected_periods = set(prior_periods[-6:])
    window = prices.loc[[period in selected_periods for period in periods]]
    if window.empty or window.isna().any().any():
        return None
    recovery: dict[str, float] = {}
    trough_dates: dict[str, str] = {}
    cumulative: dict[str, float] = {}
    for symbol in prices.columns:
        log_prices = np.log(window[symbol].astype(float))
        drawdown = log_prices - log_prices.cummax()
        trough = pd.Timestamp(drawdown.idxmin())
        recovery[symbol] = float(log_prices.iloc[-1] - log_prices.loc[trough])
        trough_dates[symbol] = trough.date().isoformat()
        cumulative[symbol] = float(log_prices.iloc[-1] - log_prices.iloc[0])
    return recovery, trough_dates, cumulative


def _selection_weights(selection: tuple[str, ...]) -> dict[str, float]:
    if not selection:
        return {"BIL": 1.0}
    return {symbol: 1.0 / len(selection) for symbol in selection}


def _basket_holding_return(
    prices: pd.DataFrame,
    selection: tuple[str, ...],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> float:
    if not selection or start not in prices.index or end not in prices.index:
        return float("nan")
    start_values = prices.loc[start, list(selection)].astype(float)
    end_values = prices.loc[end, list(selection)].astype(float)
    return float((end_values / start_values - 1.0).mean())


def recovery_vintage_events(
    sector_prices: pd.DataFrame,
    evaluation_index: pd.DatetimeIndex,
    evaluation_symbols: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    formation_dates = last_dates_by_period(sector_prices.index, "W-FRI")
    candidate_slots: deque[dict[str, Any]] = deque(
        (
            {
                "vintage_id": f"initial_BIL_{position}",
                "weights": {"BIL": 1.0},
                "selection": (),
                "execution_date": None,
            }
            for position in range(6)
        ),
        maxlen=6,
    )
    control_slots: deque[dict[str, Any]] = deque(
        (
            {
                "vintage_id": f"initial_control_BIL_{position}",
                "weights": {"BIL": 1.0},
                "selection": (),
                "execution_date": None,
            }
            for position in range(6)
        ),
        maxlen=6,
    )
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {}
    control_events: dict[pd.Timestamp, dict[str, float]] = {}
    diagnostics: list[dict[str, Any]] = []
    diagnostic_by_vintage: dict[str, dict[str, Any]] = {}
    for sequence, formation in enumerate(formation_dates):
        execution = next_session(sector_prices.index, formation)
        if execution is None:
            continue
        inputs = weekly_recovery_inputs(sector_prices, formation)
        if inputs is None:
            recovery: dict[str, float] = {}
            troughs: dict[str, str] = {}
            cumulative: dict[str, float] = {}
            candidate_selection: tuple[str, ...] = ()
            control_selection: tuple[str, ...] = ()
        else:
            recovery, troughs, cumulative = inputs
            candidate_selection = tuple(
                sorted(SECTOR_UNIVERSE, key=lambda symbol: (recovery[symbol], symbol))[:3]
            )
            control_selection = tuple(
                sorted(SECTOR_UNIVERSE, key=lambda symbol: (cumulative[symbol], symbol))[:3]
            )
        vintage_id = f"recovery_{formation.date().isoformat()}"
        control_vintage_id = f"loser_control_{formation.date().isoformat()}"
        dropped = candidate_slots[0]
        dropped_control = control_slots[0]
        candidate_slots.append(
            {
                "vintage_id": vintage_id,
                "weights": _selection_weights(candidate_selection),
                "selection": candidate_selection,
                "execution_date": execution,
            }
        )
        control_slots.append(
            {
                "vintage_id": control_vintage_id,
                "weights": _selection_weights(control_selection),
                "selection": control_selection,
                "execution_date": execution,
            }
        )
        candidate_events[execution] = target_from_vintages(
            candidate_slots, evaluation_symbols, 6
        )
        control_events[execution] = target_from_vintages(
            control_slots, evaluation_symbols, 6
        )
        if dropped["vintage_id"] in diagnostic_by_vintage:
            prior = diagnostic_by_vintage[dropped["vintage_id"]]
            prior["vintage_expiration_execution_date"] = execution.date().isoformat()
            prior["vintage_holding_return"] = _basket_holding_return(
                sector_prices,
                tuple(dropped["selection"]),
                pd.Timestamp(dropped["execution_date"]),
                execution,
            )
        row = {
            "strategy_id": EXPECTED_STRATEGY_IDS[0],
            "formation_sequence": sequence,
            "formation_date": formation.date().isoformat(),
            "execution_date": execution.date().isoformat(),
            "window_start": (
                min(troughs.values()) if troughs else ""
            ),
            "selected_sectors": candidate_selection,
            "ordinary_loser_selected_sectors": control_selection,
            "selection_overlap_count": len(set(candidate_selection) & set(control_selection)),
            "recovery_scores": recovery,
            "maximum_drawdown_trough_dates": troughs,
            "six_week_cumulative_log_returns": cumulative,
            "vintage_id": vintage_id,
            "vintage_composition": _selection_weights(candidate_selection),
            "active_vintage_count": 6,
            "vintage_expiration_execution_date": "",
            "vintage_holding_return": float("nan"),
            "signal_complete": inputs is not None,
        }
        diagnostics.append(row)
        diagnostic_by_vintage[vintage_id] = row
        if dropped_control["vintage_id"].startswith("loser_control_"):
            pass
    default = {symbol: 0.0 for symbol in evaluation_symbols}
    default["BIL"] = 1.0
    candidate = events_for_evaluation(
        candidate_events, evaluation_index, evaluation_symbols, default
    )
    control = events_for_evaluation(
        control_events, evaluation_index, evaluation_symbols, default
    )
    return candidate, control, diagnostics


def scheduled_equal_weight_events(
    signal_index: pd.DatetimeIndex,
    evaluation_index: pd.DatetimeIndex,
    evaluation_symbols: tuple[str, ...],
    target_symbols: tuple[str, ...],
    frequency: str,
) -> pd.DataFrame:
    target = {symbol: 0.0 for symbol in evaluation_symbols}
    for symbol in target_symbols:
        target[symbol] = 1.0 / len(target_symbols)
    all_events: dict[pd.Timestamp, dict[str, float]] = {}
    for formation in last_dates_by_period(signal_index, frequency):
        execution = next_session(signal_index, formation)
        if execution is not None:
            all_events[execution] = target
    return events_for_evaluation(all_events, evaluation_index, evaluation_symbols, target)


def initial_buy_hold(
    evaluation_index: pd.DatetimeIndex,
    evaluation_symbols: tuple[str, ...],
    symbol: str,
) -> pd.DataFrame:
    target = {item: 0.0 for item in evaluation_symbols}
    target[symbol] = 1.0
    return accounting.initial_event(evaluation_index, evaluation_symbols, target)


def project_simplex(values: np.ndarray) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ValueError("Simplex projection requires a finite one-dimensional vector")
    ordered = np.sort(vector)[::-1]
    cumulative = np.cumsum(ordered) - 1.0
    support = np.flatnonzero(ordered - cumulative / (np.arange(len(vector)) + 1) > 0.0)
    if not len(support):
        return np.full(len(vector), 1.0 / len(vector))
    rho = int(support[-1])
    theta = cumulative[rho] / float(rho + 1)
    projected = np.maximum(vector - theta, 0.0)
    return projected / float(projected.sum())


def olmar_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    equal = np.full(len(symbols), 1.0 / len(symbols), dtype=float)
    current = equal.copy()
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): dict(zip(symbols, equal))
    }
    equal_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): dict(zip(symbols, equal))
    }
    distance_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): dict(zip(symbols, equal))
    }
    diagnostics: list[dict[str, Any]] = []
    moving_average = prices.rolling(5, min_periods=5).mean()
    for position, signal_date in enumerate(prices.index):
        execution = next_session(prices.index, signal_date)
        if execution is None:
            continue
        complete = position >= 4
        denominator = 0.0
        lambda_value = 0.0
        predicted = equal.copy()
        if complete:
            predicted = (
                moving_average.loc[signal_date, list(symbols)].to_numpy(dtype=float)
                / prices.loc[signal_date, list(symbols)].to_numpy(dtype=float)
            )
            centered = predicted - float(predicted.mean())
            denominator = float(np.dot(centered, centered))
            if denominator > 0.0:
                lambda_value = max(
                    0.0,
                    (10.0 - float(np.dot(current, predicted))) / denominator,
                )
                current = project_simplex(current + lambda_value * centered)
            distance = np.maximum(predicted - 1.0, 0.0)
            distance_target = (
                distance / float(distance.sum()) if float(distance.sum()) > 0.0 else equal
            )
        else:
            current = equal.copy()
            distance_target = equal.copy()
        candidate_events[execution] = dict(zip(symbols, current))
        equal_events[execution] = dict(zip(symbols, equal))
        distance_events[execution] = dict(zip(symbols, distance_target))
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[1],
                "signal_date": pd.Timestamp(signal_date).date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "warmup_complete": complete,
                "predicted_price_relatives": dict(zip(symbols, predicted)),
                "denominator": denominator,
                "lambda": lambda_value,
                "target_weights": dict(zip(symbols, current)),
                "minimum_asset_weight": float(current.min()),
                "maximum_asset_weight": float(current.max()),
                "effective_holdings": float(1.0 / np.square(current).sum()),
                "any_weight_exceeds_50pct": bool((current > 0.5).any()),
            }
        )
    candidate = accounting.event_frame(prices.index, symbols, candidate_events)
    controls = {
        "daily_uniform_constant_rebalanced_nine_sector": accounting.event_frame(
            prices.index, symbols, equal_events
        ),
        "initial_equal_weight_buy_and_hold_nine_sector": accounting.initial_event(
            prices.index, symbols, dict(zip(symbols, equal))
        ),
        "simple_MA5_distance_nine_sector": accounting.event_frame(
            prices.index, symbols, distance_events
        ),
    }
    return candidate, controls, diagnostics


def high52_vintage_events(
    sector_prices: pd.DataFrame,
    evaluation_index: pd.DatetimeIndex,
    evaluation_symbols: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    candidate_slots: deque[dict[str, Any]] = deque(
        (
            {"weights": {"BIL": 1.0}, "selection": (), "execution_date": None}
            for _ in range(6)
        ),
        maxlen=6,
    )
    control_slots: deque[dict[str, Any]] = deque(
        (
            {"weights": {"BIL": 1.0}, "selection": (), "execution_date": None}
            for _ in range(6)
        ),
        maxlen=6,
    )
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {}
    control_events: dict[pd.Timestamp, dict[str, float]] = {}
    diagnostics: list[dict[str, Any]] = []
    for sequence, formation in enumerate(last_dates_by_period(sector_prices.index, "M")):
        execution = next_session(sector_prices.index, formation)
        if execution is None:
            continue
        location = int(sector_prices.index.get_loc(formation))
        high_ratios: dict[str, float] = {}
        momentum: dict[str, float] = {}
        candidate_selection: tuple[str, ...] = ()
        control_selection: tuple[str, ...] = ()
        if location >= 251:
            window = sector_prices.iloc[location - 251 : location + 1]
            high_ratios = {
                symbol: float(
                    sector_prices.loc[formation, symbol] / window[symbol].max()
                )
                for symbol in SECTOR_UNIVERSE
            }
            candidate_selection = tuple(
                sorted(
                    SECTOR_UNIVERSE,
                    key=lambda symbol: (-high_ratios[symbol], symbol),
                )[:3]
            )
        if location >= 126:
            momentum = {
                symbol: float(
                    sector_prices.loc[formation, symbol]
                    / sector_prices.iloc[location - 126][symbol]
                    - 1.0
                )
                for symbol in SECTOR_UNIVERSE
            }
            control_selection = tuple(
                sorted(
                    SECTOR_UNIVERSE,
                    key=lambda symbol: (-momentum[symbol], symbol),
                )[:3]
            )
        candidate_slots.append(
            {
                "weights": _selection_weights(candidate_selection),
                "selection": candidate_selection,
                "execution_date": execution,
            }
        )
        control_slots.append(
            {
                "weights": _selection_weights(control_selection),
                "selection": control_selection,
                "execution_date": execution,
            }
        )
        candidate_events[execution] = target_from_vintages(
            candidate_slots, evaluation_symbols, 6
        )
        control_events[execution] = target_from_vintages(
            control_slots, evaluation_symbols, 6
        )
        holding_end = (
            next_session(
                sector_prices.index,
                last_dates_by_period(sector_prices.index, "M")[sequence + 6],
            )
            if sequence + 6 < len(last_dates_by_period(sector_prices.index, "M"))
            else None
        )
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[3],
                "formation_sequence": sequence,
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "high52_ratios": high_ratios,
                "selected_sectors": candidate_selection,
                "six_month_momentum_scores": momentum,
                "momentum_selected_sectors": control_selection,
                "selection_overlap_count": len(
                    set(candidate_selection) & set(control_selection)
                ),
                "vintage_composition": _selection_weights(candidate_selection),
                "vintage_expiration_execution_date": (
                    holding_end.date().isoformat() if holding_end is not None else ""
                ),
                "holding_period_return": (
                    _basket_holding_return(
                        sector_prices,
                        candidate_selection,
                        execution,
                        holding_end,
                    )
                    if holding_end is not None
                    else float("nan")
                ),
                "warmup_complete": bool(high_ratios),
            }
        )
    default = {symbol: 0.0 for symbol in evaluation_symbols}
    default["BIL"] = 1.0
    return (
        events_for_evaluation(
            candidate_events, evaluation_index, evaluation_symbols, default
        ),
        events_for_evaluation(
            control_events, evaluation_index, evaluation_symbols, default
        ),
        diagnostics,
    )


def country_vintage_events(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    risky = COUNTRY_UNIVERSE
    annual_dates = last_dates_by_period(prices.index, "Y")
    annual_close = prices.loc[annual_dates, list(risky)]
    annual_returns = annual_close.pct_change(fill_method=None)
    active: list[dict[str, Any]] = []
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {}
    one_year_events: dict[pd.Timestamp, dict[str, float]] = {}
    equal_events: dict[pd.Timestamp, dict[str, float]] = {}
    diagnostics: list[dict[str, Any]] = []
    equal = {symbol: 0.0 for symbol in symbols}
    for symbol in risky:
        equal[symbol] = 1.0 / len(risky)
    for formation in annual_dates:
        execution = next_session(prices.index, formation)
        if execution is None:
            continue
        scores = annual_returns.loc[formation]
        year_rows = prices.loc[prices.index.year == formation.year, list(risky)]
        complete = bool(
            not year_rows.empty
            and set(year_rows.index.month) == set(range(1, 13))
            and scores.notna().all()
        )
        if not complete:
            continue
        selection = tuple(
            sorted(risky, key=lambda symbol: (float(scores[symbol]), symbol))[:5]
        )
        active = [
            vintage
            for vintage in active
            if formation.year - int(vintage["formation_year"]) < 5
        ]
        active.append(
            {
                "formation_year": formation.year,
                "selection": selection,
                "execution_date": execution,
            }
        )
        candidate_target = {symbol: 0.0 for symbol in symbols}
        for vintage in active:
            for symbol in vintage["selection"]:
                candidate_target[symbol] += 1.0 / len(active) / 5.0
        one_year_target = {symbol: 0.0 for symbol in symbols}
        for symbol in selection:
            one_year_target[symbol] = 1.0 / 5.0
        candidate_events[execution] = candidate_target
        one_year_events[execution] = one_year_target
        equal_events[execution] = equal
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[2],
                "formation_year": formation.year,
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "annual_country_returns": {
                    symbol: float(scores[symbol]) for symbol in risky
                },
                "country_rank_order": tuple(
                    sorted(risky, key=lambda symbol: (float(scores[symbol]), symbol))
                ),
                "selected_countries": selection,
                "vintage_start_date": execution.date().isoformat(),
                "vintage_expiration_year": formation.year + 5,
                "active_vintage_count": len(active),
                "independent_formation_year_count": len(diagnostics) + 1,
            }
        )
    if not candidate_events:
        return pd.DataFrame(), {}, diagnostics
    first = min(candidate_events)
    candidate = accounting.event_frame(
        prices.index,
        symbols,
        {first: candidate_events[first], **candidate_events},
    )
    controls = {
        "annual_equal_weight_frozen_country_universe": accounting.event_frame(
            prices.index, symbols, {first: equal, **equal_events}
        ),
        "ACWI_buy_and_hold": initial_buy_hold(prices.index, symbols, "ACWI"),
        "prior_year_bottom5_one_year_nonoverlapping": accounting.event_frame(
            prices.index, symbols, {first: one_year_events[first], **one_year_events}
        ),
    }
    return candidate, controls, diagnostics


def prepare_candidate(card: CandidateCard) -> dict[str, Any]:
    if card.strategy_id == EXPECTED_STRATEGY_IDS[0]:
        sector_prices = market.load_price_frame(SECTOR_UNIVERSE)
        prices = market.load_price_frame(card.required_symbols)
        candidate, loser, diagnostics = recovery_vintage_events(
            sector_prices, prices.index, tuple(prices.columns)
        )
        controls = {
            card.controls[0]: loser,
            card.controls[1]: scheduled_equal_weight_events(
                sector_prices.index,
                prices.index,
                tuple(prices.columns),
                SECTOR_UNIVERSE,
                "W-FRI",
            ),
            card.controls[2]: initial_buy_hold(
                prices.index, tuple(prices.columns), "SPY"
            ),
        }
        return {
            "prices": prices,
            "candidate_events": candidate,
            "control_events": controls,
            "recovery_diagnostics": diagnostics,
            "olmar_diagnostics": [],
            "dogs_diagnostics": [],
            "high52_diagnostics": [],
            "timing_convention": (
                "weekly_completed_close_signal_execution_at_following_session_close"
            ),
        }
    if card.strategy_id == EXPECTED_STRATEGY_IDS[1]:
        prices = market.load_price_frame(SECTOR_UNIVERSE)
        candidate, controls, diagnostics = olmar_event_sets(prices)
        return {
            "prices": prices,
            "candidate_events": candidate,
            "control_events": controls,
            "recovery_diagnostics": [],
            "olmar_diagnostics": diagnostics,
            "dogs_diagnostics": [],
            "high52_diagnostics": [],
            "timing_convention": (
                "daily_completed_close_signal_execution_at_following_session_close"
            ),
        }
    if card.strategy_id == EXPECTED_STRATEGY_IDS[2]:
        prices = market.load_price_frame(card.required_symbols)
        candidate, controls, diagnostics = country_vintage_events(prices)
        return {
            "prices": prices,
            "candidate_events": candidate,
            "control_events": controls,
            "recovery_diagnostics": [],
            "olmar_diagnostics": [],
            "dogs_diagnostics": diagnostics,
            "high52_diagnostics": [],
            "timing_convention": (
                "calendar_year_end_close_signal_execution_at_first_following_session_close"
            ),
        }
    if card.strategy_id == EXPECTED_STRATEGY_IDS[3]:
        sector_prices = market.load_price_frame(SECTOR_UNIVERSE)
        prices = market.load_price_frame(card.required_symbols)
        candidate, momentum, diagnostics = high52_vintage_events(
            sector_prices, prices.index, tuple(prices.columns)
        )
        controls = {
            card.controls[0]: momentum,
            card.controls[1]: scheduled_equal_weight_events(
                sector_prices.index,
                prices.index,
                tuple(prices.columns),
                SECTOR_UNIVERSE,
                "M",
            ),
            card.controls[2]: initial_buy_hold(
                prices.index, tuple(prices.columns), "SPY"
            ),
        }
        return {
            "prices": prices,
            "candidate_events": candidate,
            "control_events": controls,
            "recovery_diagnostics": [],
            "olmar_diagnostics": [],
            "dogs_diagnostics": [],
            "high52_diagnostics": diagnostics,
            "timing_convention": (
                "month_end_completed_close_signal_execution_at_following_session_close"
            ),
        }
    raise RuntimeError(f"Unsupported V6 candidate {card.strategy_id}")


def run_candidate(
    card: CandidateCard,
    preflight_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant = [
        row for row in preflight_rows if row["strategy_id"] == card.strategy_id
    ]
    missing = sorted(
        {
            row["symbol"]
            for row in relevant
            if row["preflight_status"] != "pass"
        }
    )
    if missing:
        return {
            "card": card,
            "executed": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_unavailable",
            "decision_reason": (
                "frozen candidate or required control lacks canonical local data"
            ),
            "missing_symbols": missing,
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": {
                "recovery_diagnostics": [],
                "olmar_diagnostics": [],
                "dogs_diagnostics": [],
                "high52_diagnostics": [],
            },
        }
    prepared = prepare_candidate(card)
    prices = prepared["prices"]
    candidate_events = prepared["candidate_events"]
    controls = prepared["control_events"]
    if prices.empty or candidate_events.empty or tuple(controls) != card.controls:
        return {
            "card": card,
            "executed": False,
            "outcome": "blocked_feasibility",
            "failure_reason": "methodology_failure",
            "decision_reason": "frozen signal or required control could not be constructed",
            "missing_symbols": [],
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": prepared,
        }
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate_paths[cost] = accounting.simulate_path(
            prices,
            candidate_events,
            cost,
            prepared["timing_convention"],
        )
        for control_id, events in controls.items():
            control_paths[(control_id, cost)] = accounting.simulate_path(
                prices,
                events,
                cost,
                prepared["timing_convention"],
            )
    return {
        "card": card,
        "executed": True,
        "outcome": "",
        "failure_reason": "",
        "decision_reason": "",
        "missing_symbols": [],
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": {},
        "prepared": prepared,
    }


def strategy_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    source = accounting.metric_payload(path, period_index)
    return {
        "evaluation_start": source["evaluation_start"],
        "evaluation_end": source["evaluation_end"],
        "trading_days": source["trading_days"],
        "total_return": source["total_return"],
        "cagr": source["cagr"],
        "annualized_volatility": source["annualized_volatility"],
        "sharpe_ratio": source["sharpe_ratio"],
        "maximum_drawdown": source["maximum_drawdown"],
        "average_risky_exposure": source["average_risky_exposure"],
        "turnover": source["turnover"],
        "trade_or_rebalance_count": source["trade_or_rebalance_count"],
        "transaction_cost_drag": source["transaction_cost_drag"],
        "maximum_gross_exposure": source["maximum_gross_exposure"],
        "maximum_daily_weight_sum": source["maximum_daily_weight_sum"],
        "numeric_invariant_status": source["numeric_invariant_status"],
        "timing_invariant_status": source["timing_invariant_status"],
        "exposure_invariant_status": source["exposure_weight_invariant_status"],
        "weight_invariant_status": source["exposure_weight_invariant_status"],
        "invariant_pass": source["invariant_pass"],
    }


def portfolio_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    source = portfolio_accounting.metric_payload(path, period_index)
    return {
        "evaluation_start": source["evaluation_start"],
        "evaluation_end": source["evaluation_end"],
        "trading_days": source["trading_days"],
        "total_return": source["total_return"],
        "cagr": source["cagr"],
        "annualized_volatility": source["annualized_volatility"],
        "sharpe_ratio": source["sharpe_ratio"],
        "maximum_drawdown": source["maximum_drawdown"],
        "average_risky_exposure": source["average_gross_exposure"],
        "turnover": source["turnover"],
        "trade_or_rebalance_count": source["trade_or_rebalance_count"],
        "transaction_cost_drag": source["transaction_cost_drag"],
        "maximum_gross_exposure": source["max_daily_exposure"],
        "maximum_daily_weight_sum": source["max_daily_weight_sum"],
        "numeric_invariant_status": source["numeric_invariant_status"],
        "timing_invariant_status": source["timing_invariant_status"],
        "exposure_invariant_status": source["exposure_invariant_status"],
        "weight_invariant_status": source["exposure_invariant_status"],
        "invariant_pass": source["invariant_pass"],
    }


def split_periods(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def build_portfolio_paths(
    result: dict[str, Any],
    reference_returns: pd.Series,
) -> dict[tuple[str, float], dict[str, Any]]:
    if not result["executed"]:
        return {}
    card: CandidateCard = result["card"]
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate = result["candidate_paths"][cost]["returns"]
        controls = {
            control_id: result["control_paths"][(control_id, cost)]["returns"]
            for control_id in card.portfolio_controls
        }
        common = candidate.index.intersection(reference_returns.index)
        for series in controls.values():
            common = common.intersection(series.index)
        common = common.sort_values()
        reference = reference_returns.reindex(common).dropna()
        candidate = candidate.reindex(reference.index).dropna()
        reference = reference.reindex(candidate.index)
        payloads[("frozen_reference_100pct", cost)] = (
            portfolio_accounting.reference_payload(reference, cost)
        )
        candidate_id = f"{card.strategy_id}_candidate_20pct"
        payloads[(candidate_id, cost)] = (
            portfolio_accounting.simulate_two_component_portfolio(
                reference, candidate, candidate_id, cost
            )
        )
        for control_id, series in controls.items():
            aligned = series.reindex(reference.index).dropna()
            ref_aligned = reference.reindex(aligned.index)
            portfolio_id = f"{control_id}_20pct_control"
            payloads[(portfolio_id, cost)] = (
                portfolio_accounting.simulate_two_component_portfolio(
                    ref_aligned, aligned, portfolio_id, cost
                )
            )
    return payloads


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def best_by_sharpe(
    controls: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    return max(
        controls.items(),
        key=lambda item: (
            float(item[1]["sharpe_ratio"]),
            float(item[1]["maximum_drawdown"]),
            item[0],
        ),
    )


def followup_gate_control(
    card: CandidateCard,
    controls: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    control_id = EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS.get(card.strategy_id)
    if control_id is None:
        return best_by_sharpe(controls)
    if control_id not in controls:
        raise RuntimeError(
            f"Frozen follow-up gate control {control_id} is unavailable for "
            f"{card.strategy_id}"
        )
    return control_id, controls[control_id]


def worse_on_both_sharpe_and_drawdown(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"])
    )


def has_material_sharpe_or_drawdown_advantage(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
        >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def classify(result: dict[str, Any]) -> None:
    if not result["executed"]:
        return
    card: CandidateCard = result["card"]
    candidate = strategy_metrics(result["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: strategy_metrics(
            result["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in card.portfolio_controls
    }
    if not candidate["invariant_pass"] or not all(
        control["invariant_pass"] for control in controls.values()
    ):
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="candidate or principal-control invariant failed",
        )
        return
    if float(candidate["total_return"]) <= 0.0:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_return",
            decision_reason="full-period after-cost return is not positive",
        )
        return
    dominating = [
        control_id
        for control_id, control in controls.items()
        if dominates(control, candidate)
    ]
    if dominating:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason=(
                "principal control dominates CAGR, Sharpe, and drawdown: "
                + ",".join(dominating)
            ),
        )
        return
    gate_control_id, gate_control = followup_gate_control(card, controls)
    if not has_material_sharpe_or_drawdown_advantage(candidate, gate_control):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=(
                "advantage below materiality versus frozen same-purpose control "
                f"{gate_control_id}"
            ),
        )
        return
    for label, period in split_periods(
        result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
    ):
        candidate_half = strategy_metrics(
            result["candidate_paths"][PRIMARY_COST_BPS], period
        )
        control_half = strategy_metrics(
            result["control_paths"][(gate_control_id, PRIMARY_COST_BPS)], period
        )
        if worse_on_both_sharpe_and_drawdown(candidate_half, control_half):
            result.update(
                outcome="closed_exploration",
                failure_reason="period_instability",
                decision_reason=(
                    f"candidate worse on Sharpe and drawdown in {label}"
                ),
            )
            return
    candidate_10 = strategy_metrics(result["candidate_paths"][10.0])
    controls_10 = {
        control_id: strategy_metrics(result["control_paths"][(control_id, 10.0)])
        for control_id in card.portfolio_controls
    }
    gate_control_10_id, gate_control_10 = followup_gate_control(card, controls_10)
    if worse_on_both_sharpe_and_drawdown(candidate_10, gate_control_10):
        result.update(
            outcome="closed_exploration",
            failure_reason="cost_drag",
            decision_reason=(
                "10-bps result unfavorable on Sharpe and drawdown versus "
                f"{gate_control_10_id}"
            ),
        )
        return

    if card.route == "diversifier":
        portfolios = result["portfolio_paths"]
        reference = portfolio_metrics(
            portfolios[("frozen_reference_100pct", PRIMARY_COST_BPS)]
        )
        candidate_id = f"{card.strategy_id}_candidate_20pct"
        candidate_portfolio = portfolio_metrics(
            portfolios[(candidate_id, PRIMARY_COST_BPS)]
        )
        control_portfolios = {
            f"{control_id}_20pct_control": portfolio_metrics(
                portfolios[(f"{control_id}_20pct_control", PRIMARY_COST_BPS)]
            )
            for control_id in card.portfolio_controls
        }
        improves_sharpe = (
            float(candidate_portfolio["sharpe_ratio"])
            > float(reference["sharpe_ratio"])
        )
        improves_drawdown = (
            float(candidate_portfolio["maximum_drawdown"])
            > float(reference["maximum_drawdown"])
        )
        worsens_both = (
            float(candidate_portfolio["sharpe_ratio"])
            < float(reference["sharpe_ratio"])
            and float(candidate_portfolio["maximum_drawdown"])
            < float(reference["maximum_drawdown"])
        )
        if not ((improves_sharpe or improves_drawdown) and not worsens_both):
            result.update(
                outcome="closed_exploration",
                failure_reason="weak_vs_primary_control",
                decision_reason=(
                    "80/20 candidate did not improve reference Sharpe or drawdown "
                    "without worsening both"
                ),
            )
            return
        if any(
            dominates(control, candidate_portfolio)
            for control in control_portfolios.values()
        ):
            result.update(
                outcome="closed_exploration",
                failure_reason="weak_vs_primary_control",
                decision_reason="an 80/20 principal control dominates the candidate",
            )
            return
        best_portfolio_id, best_portfolio = best_by_sharpe(control_portfolios)
        if not has_material_sharpe_or_drawdown_advantage(
            candidate_portfolio, best_portfolio
        ):
            result.update(
                outcome="closed_exploration",
                failure_reason="benchmark_like_behavior",
                decision_reason=(
                    f"80/20 advantage below materiality versus {best_portfolio_id}"
                ),
            )
            return
        result.update(
            outcome="exploratory_followup_candidate_diversifier",
            failure_reason="",
            decision_reason="all preregistered diversifier exploration gates passed",
        )
        return
    result.update(
        outcome="exploratory_followup_candidate_standalone",
        failure_reason="",
        decision_reason="all preregistered standalone exploration gates passed",
    )


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
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": card.source_record_id,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "display_name": card.display_name,
            "strategy_architecture": card.strategy_architecture,
            "route": card.route,
            "source_library_id": SOURCE_LIBRARY_ID,
            "source_packet_location": rel(SOURCE_PACKET_ATTACHMENT),
            "source_packet_hash": file_hash(SOURCE_PACKET_ATTACHMENT),
            "repository_source_packet_present": SOURCE_PACKET_DIR.exists(),
            "frozen_rule": card.frozen_rule,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in CARDS
    ]


def candidate_next_action(result: dict[str, Any]) -> str:
    outcome = result["outcome"]
    card: CandidateCard = result["card"]
    if outcome.startswith("exploratory_followup_candidate_"):
        return f"direction_owner_review_{card.strategy_id}_exploratory_followup"
    if outcome == "closed_exploration":
        return "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
    if outcome == "inconclusive_data_issue":
        return f"direction_owner_review_{card.strategy_id}_data_issue"
    return f"direction_owner_review_{card.strategy_id}_feasibility_block"


def strategy_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": card.strategy_architecture,
                "source_or_research_lineage": card.source_or_research_lineage,
                "instrument_universe": card.universe,
                "parameters": card.parameters,
                "benchmark_or_control": card.controls,
                "stage": STAGE,
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "route": card.route,
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": candidate_next_action(result),
                "complete_frozen_rule": card.frozen_rule,
                "created_in_source_of_truth": False,
            }
        )
    return rows


def trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "experiment_trial",
                "strategy_architecture": card.strategy_architecture,
                "source_or_research_lineage": card.source_or_research_lineage,
                "instrument_universe": card.universe,
                "parameters": card.parameters,
                "benchmark_or_control": card.controls,
                "stage": STAGE,
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "route": card.route,
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": candidate_next_action(result),
                "complete_frozen_rule": card.frozen_rule,
                "transaction_cost_assumptions": (
                    "0|5|10 bps per one-way turnover; 5 bps primary"
                ),
                "execution_timing": (
                    "completed signal close; target applied at following session close"
                ),
                "changed_fields_from_parent": "canonical_configuration",
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
                "results_viewed_before_preregistration": False,
                "executed": result["executed"],
                "counted_as_trial": True,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "strategy_id": "",
            "family_id": "",
            "trial_id": "",
            "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "reference_role": "portfolio_contribution_reference_only",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    for card in CARDS:
        for control_id in card.controls:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": (
                        "same_purpose_or_static_control"
                        if control_id in card.portfolio_controls
                        else "broad_market_control"
                    ),
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def result_row(
    result: dict[str, Any],
    row_type: str,
    control_id: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    card: CandidateCard = result["card"]
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": card.trial_id,
        "entity_type": (
            "experiment_trial"
            if row_type == "candidate"
            else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "row_type": row_type,
        "control_id": control_id,
        "route": card.route,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "chronological_split_diagnostic_not_clean_sealed_or_validation"
        ),
        "outcome": result["outcome"],
        "failure_reason": result["failure_reason"],
        "decision_reason": result["decision_reason"],
        "missing_symbols": result["missing_symbols"],
        **({field: "" for field in METRIC_FIELDS} if metrics is None else metrics),
    }


def result_tables(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        if not result["executed"]:
            candidates.append(
                result_row(
                    result, "candidate", "", PRIMARY_COST_BPS, "full_period", None
                )
            )
            for control_id in card.controls:
                controls.append(
                    result_row(
                        result,
                        "control",
                        control_id,
                        PRIMARY_COST_BPS,
                        "full_period",
                        None,
                    )
                )
            for row_type, control_id in [
                ("candidate", ""),
                *(("control", control_id) for control_id in card.controls),
            ]:
                for half_label in (
                    "first_chronological_half",
                    "second_chronological_half",
                ):
                    halves.append(
                        result_row(
                            result,
                            row_type,
                            control_id,
                            PRIMARY_COST_BPS,
                            half_label,
                            None,
                        )
                    )
            continue
        for cost in COST_BPS:
            candidate_metrics = strategy_metrics(result["candidate_paths"][cost])
            candidates.append(
                result_row(
                    result,
                    "candidate",
                    "",
                    cost,
                    "full_period",
                    candidate_metrics,
                )
            )
            turnover.append(
                {
                    "record_scope": "strategy_candidate",
                    "strategy_id": card.strategy_id,
                    "control_or_portfolio_id": "",
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": candidate_metrics["turnover"],
                    "trade_or_rebalance_count": candidate_metrics[
                        "trade_or_rebalance_count"
                    ],
                    "transaction_cost_drag": candidate_metrics[
                        "transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "natural_drift_between_rebalances": True,
                }
            )
            invariants.append(
                {
                    "strategy_id": card.strategy_id,
                    "record_type": "candidate",
                    "control_or_portfolio_id": "",
                    "cost_assumption_bps": cost,
                    "explicit_zero_weights": True,
                    "natural_drift_between_rebalances": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "same_period_price_signal_return_used": False,
                    **{
                        field: candidate_metrics[field]
                        for field in (
                            "maximum_gross_exposure",
                            "maximum_daily_weight_sum",
                            "numeric_invariant_status",
                            "timing_invariant_status",
                            "exposure_invariant_status",
                            "weight_invariant_status",
                            "invariant_pass",
                        )
                    },
                }
            )
            for half_label, period in split_periods(
                result["candidate_paths"][cost]["returns"].index
            ):
                halves.append(
                    result_row(
                        result,
                        "candidate",
                        "",
                        cost,
                        half_label,
                        strategy_metrics(result["candidate_paths"][cost], period),
                    )
                )
            for control_id in card.controls:
                metrics = strategy_metrics(
                    result["control_paths"][(control_id, cost)]
                )
                controls.append(
                    result_row(
                        result,
                        "control",
                        control_id,
                        cost,
                        "full_period",
                        metrics,
                    )
                )
                turnover.append(
                    {
                        "record_scope": "benchmark_control",
                        "strategy_id": card.strategy_id,
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metrics["turnover"],
                        "trade_or_rebalance_count": metrics[
                            "trade_or_rebalance_count"
                        ],
                        "transaction_cost_drag": metrics[
                            "transaction_cost_drag"
                        ],
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "natural_drift_between_rebalances": True,
                    }
                )
                invariants.append(
                    {
                        "strategy_id": card.strategy_id,
                        "record_type": "benchmark_control",
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "explicit_zero_weights": True,
                        "natural_drift_between_rebalances": True,
                        "stale_weight_forward_fill_used": False,
                        "negative_weights_present": False,
                        "same_period_price_signal_return_used": False,
                        **{
                            field: metrics[field]
                            for field in (
                                "maximum_gross_exposure",
                                "maximum_daily_weight_sum",
                                "numeric_invariant_status",
                                "timing_invariant_status",
                                "exposure_invariant_status",
                                "weight_invariant_status",
                                "invariant_pass",
                            )
                        },
                    }
                )
                for half_label, period in split_periods(
                    result["control_paths"][(control_id, cost)]["returns"].index
                ):
                    halves.append(
                        result_row(
                            result,
                            "control",
                            control_id,
                            cost,
                            half_label,
                            strategy_metrics(
                                result["control_paths"][(control_id, cost)],
                                period,
                            ),
                        )
                    )
    return {
        "all_trial_results": candidates,
        "control_results": controls,
        "chronological_half_results": halves,
        "turnover_cost_reconciliation": turnover,
        "invariant_results": invariants,
    }


def portfolio_rows(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        for (portfolio_id, cost), path in sorted(result["portfolio_paths"].items()):
            for period_label, period in [
                ("full_period", None),
                *split_periods(path["returns"].index),
            ]:
                metrics = portfolio_metrics(path, period)
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": card.trial_id,
                        "route": card.route,
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": (
                            "100pct_frozen_reference"
                            if portfolio_id == "frozen_reference_100pct"
                            else (
                                "monthly_rebalanced_80pct_reference_plus_20pct_"
                                "candidate_or_principal_control_with_natural_drift"
                            )
                        ),
                        "period_label": period_label,
                        "period_role": (
                            "full_period_exploration"
                            if period_label == "full_period"
                            else (
                                "chronological_split_diagnostic_not_clean_"
                                "sealed_or_validation"
                            )
                        ),
                        "cost_assumption_bps": cost,
                        **metrics,
                    }
                )
            full = portfolio_metrics(path)
            turnover_rows.append(
                {
                    "record_scope": "portfolio_contribution",
                    "strategy_id": card.strategy_id,
                    "control_or_portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": full["turnover"],
                    "trade_or_rebalance_count": full["trade_or_rebalance_count"],
                    "transaction_cost_drag": full["transaction_cost_drag"],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "natural_drift_between_rebalances": True,
                }
            )
            invariant_rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "record_type": "portfolio_contribution",
                    "control_or_portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "explicit_zero_weights": True,
                    "natural_drift_between_rebalances": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "same_period_price_signal_return_used": False,
                    **{
                        field: full[field]
                        for field in (
                            "maximum_gross_exposure",
                            "maximum_daily_weight_sum",
                            "numeric_invariant_status",
                            "timing_invariant_status",
                            "exposure_invariant_status",
                            "weight_invariant_status",
                            "invariant_pass",
                        )
                    },
                }
            )
    return rows, turnover_rows, invariant_rows


def diagnostic_tables(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    recovery: list[dict[str, Any]] = []
    olmar: list[dict[str, Any]] = []
    dogs: list[dict[str, Any]] = []
    high52: list[dict[str, Any]] = []
    for result in results:
        prepared = result["prepared"]
        recovery.extend(prepared.get("recovery_diagnostics", []))
        dogs.extend(prepared.get("dogs_diagnostics", []))
        high52.extend(prepared.get("high52_diagnostics", []))
        olmar_rows = [dict(row) for row in prepared.get("olmar_diagnostics", [])]
        if olmar_rows and result["executed"]:
            turnover = result["candidate_paths"][PRIMARY_COST_BPS]["turnover"]
            for row in olmar_rows:
                execution = pd.Timestamp(row["execution_date"])
                row["realized_one_way_turnover_5bps"] = float(
                    turnover.get(execution, 0.0)
                )
                row["record_type"] = "daily_target"
            high_weight_share = float(
                np.mean([bool(row["any_weight_exceeds_50pct"]) for row in olmar_rows])
            )
            olmar_rows.append(
                {
                    "strategy_id": EXPECTED_STRATEGY_IDS[1],
                    "record_type": "summary",
                    "signal_date": "",
                    "execution_date": "",
                    "warmup_complete": "",
                    "predicted_price_relatives": {},
                    "denominator": "",
                    "lambda": "",
                    "target_weights": {},
                    "minimum_asset_weight": min(
                        float(row["minimum_asset_weight"])
                        for row in olmar_rows
                        if row["record_type"] == "daily_target"
                    ),
                    "maximum_asset_weight": max(
                        float(row["maximum_asset_weight"])
                        for row in olmar_rows
                        if row["record_type"] == "daily_target"
                    ),
                    "effective_holdings": float(
                        np.mean(
                            [
                                float(row["effective_holdings"])
                                for row in olmar_rows
                                if row["record_type"] == "daily_target"
                            ]
                        )
                    ),
                    "any_weight_exceeds_50pct": "",
                    "percentage_days_any_weight_exceeds_50pct": high_weight_share,
                    "realized_one_way_turnover_5bps": float(turnover.sum()),
                }
            )
        olmar.extend(olmar_rows)
    return {
        "recovery_signal_diagnostics": recovery,
        "olmar_weight_diagnostics": olmar,
        "dogs_vintage_diagnostics": dogs,
        "high52_vintage_diagnostics": high52,
    }


def outcome_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "entity_type": "strategy_configuration",
            "stage": STAGE,
            "route": result["card"].route,
            "executed": result["executed"],
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "missing_symbols": result["missing_symbols"],
            "next_action": candidate_next_action(result),
            "validation_claimed": False,
            "promotion_authorized": False,
        }
        for result in results
    ]


def batch_next_action(results: list[dict[str, Any]]) -> str:
    if any(
        result["outcome"].startswith("exploratory_followup_candidate_")
        for result in results
    ):
        return NEXT_REVIEW
    if sum(bool(result["executed"]) for result in results) < 2:
        return NEXT_BLOCKED
    return NEXT_ALL_CLOSED


def funnel_counts(
    results: list[dict[str, Any]],
    benchmarks: list[dict[str, Any]],
    data_tasks: list[dict[str, Any]],
    next_action: str,
) -> dict[str, Any]:
    outcomes = [result["outcome"] for result in results]
    return {
        "source_library_records_referenced": 4,
        "strategy_configurations_considered": 4,
        "experiment_trials_recorded": 4,
        "experiment_trials_executed": sum(
            bool(result["executed"]) for result in results
        ),
        "benchmark_references": len(benchmarks),
        "data_capability_tasks": len(data_tasks),
        "process_tasks": 1,
        "standalone_followup_candidates": outcomes.count(
            "exploratory_followup_candidate_standalone"
        ),
        "diversifier_followup_candidates": outcomes.count(
            "exploratory_followup_candidate_diversifier"
        ),
        "closed_exploration": outcomes.count("closed_exploration"),
        "inconclusive_data_issue": outcomes.count("inconclusive_data_issue"),
        "blocked_feasibility": outcomes.count("blocked_feasibility"),
        "outcome_count_reconciles": len(outcomes) == 4,
        "exact_next_action": next_action,
    }


def build_report(
    results: list[dict[str, Any]],
    funnel: dict[str, Any],
    next_action: str,
) -> str:
    lines = [
        "# Fast Source Library Batch V6",
        "",
        "## Scope",
        "",
        "Exactly four source-frozen exploration configurations were considered. "
        "No source research, parameter variation, validation, promotion, lifecycle, "
        "paper/demo, broker, or real-money action occurred.",
        "",
        "The repository-side V3 packet directory was absent. The direction-owner-supplied "
        "V3 attachment was present and was used as the controlling frozen packet; no rule "
        "was inferred or completed.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        card: CandidateCard = result["card"]
        lines.append(
            f"- `{card.strategy_id}`: `{result['outcome']}`"
            + (
                f" (`{result['failure_reason']}`; {result['decision_reason']})"
                if result["failure_reason"]
                else f" ({result['decision_reason']})"
            )
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "- Primary cost: `5 bps` per one-way turnover.",
            "- Diagnostics: `0 bps` and `10 bps`.",
            "- Turnover uses actual drifted pretrade holdings.",
            "- Strategy and 80/20 portfolio targets execute after the completed signal close.",
            "- Portfolio contribution uses monthly rebalanced 80/20 holdings with natural drift.",
            "- Chronological halves are descriptive exploration diagnostics, not validation or holdouts.",
            "",
            "## Entity Counts",
            "",
            f"- Source records: `{funnel['source_library_records_referenced']}`",
            f"- Strategy configurations: `{funnel['strategy_configurations_considered']}`",
            f"- Canonical trials: `{funnel['experiment_trials_recorded']}`",
            f"- Executed trials: `{funnel['experiment_trials_executed']}`",
            f"- Benchmark references: `{funnel['benchmark_references']}`",
            f"- Data-capability tasks: `{funnel['data_capability_tasks']}`",
            f"- Process tasks: `{funnel['process_tasks']}`",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    payload = [
        {
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "source_record_id": card.source_record_id,
            "route": card.route,
            "universe": card.universe,
            "required_symbols": card.required_symbols,
            "controls": card.controls,
            "portfolio_controls": card.portfolio_controls,
            "parameters": card.parameters,
            "frozen_rule": card.frozen_rule,
        }
        for card in CARDS
    ]
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_preregistration_checkpoint() -> str:
    pending = [
        {
            "card": card,
            "executed": False,
            "outcome": "preregistered_pending_execution",
            "failure_reason": "",
            "decision_reason": "frozen_before_performance_calculation",
            "missing_symbols": [],
        }
        for card in CARDS
    ]
    pending_strategies = strategy_rows(pending)
    pending_trials = trial_rows(pending)
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        pending_strategies,
        list(pending_strategies[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        pending_trials,
        list(pending_trials[0]),
    )
    material = {
        "strategy_cards": pending_strategies,
        "trial_ledger": pending_trials,
        "frozen_core_hash": deterministic_core_hash(),
        "written_before_performance_calculation": True,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(material, sort_keys=True, default=csv_value).encode("utf-8")
    ).hexdigest()


def run() -> dict[str, Any]:
    validate_cards()
    source_attachment_hash_before = file_hash(SOURCE_PACKET_ATTACHMENT)
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_before = map_hashes(cache_files())
    prior_files_before = prior_evidence_files()
    prior_before = map_hashes(prior_files_before)
    prior_aggregate_before = aggregate_hash(prior_before)

    clean_output()
    preflight_rows, _, data_tasks = data_preflight()
    preregistration_checkpoint_hash = write_preregistration_checkpoint()
    results = [run_candidate(card, preflight_rows) for card in CARDS]
    reference = market.active_vm_dsr_usci_reference_returns()
    for result in results:
        result["portfolio_paths"] = build_portfolio_paths(result, reference)
        classify(result)
    next_action = batch_next_action(results)

    sources = source_rows()
    strategies = strategy_rows(results)
    trials = trial_rows(results)
    benchmarks = benchmark_rows()
    tables = result_tables(results)
    portfolio_result_rows, portfolio_turnover, portfolio_invariants = portfolio_rows(
        results
    )
    tables["turnover_cost_reconciliation"].extend(portfolio_turnover)
    tables["invariant_results"].extend(portfolio_invariants)
    diagnostics = diagnostic_tables(results)
    outcomes = outcome_rows(results)
    failures = [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "missing_symbols": result["missing_symbols"],
        }
        for result in results
        if result["failure_reason"]
    ]
    next_rows = [
        {
            "scope": "strategy",
            "strategy_id": result["card"].strategy_id,
            "outcome": result["outcome"],
            "exact_next_action": candidate_next_action(result),
            "execute_in_this_task": False,
        }
        for result in results
    ]
    next_rows.append(
        {
            "scope": "batch",
            "strategy_id": "",
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }
    )
    process = [
        {
            "task_id": BATCH_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "strategy_counted": False,
            "trial_counted": False,
            "execute_next_action_now": False,
        }
    ]
    funnel = funnel_counts(results, benchmarks, data_tasks, next_action)

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_after = map_hashes(cache_files())
    prior_after = map_hashes(prior_files_before)
    prior_aggregate_after = aggregate_hash(prior_after)
    source_attachment_hash_after = file_hash(SOURCE_PACKET_ATTACHMENT)
    cache_changed = sorted(
        {
            path
            for path in set(cache_before) | set(cache_after)
            if cache_before.get(path, "missing") != cache_after.get(path, "missing")
        }
    )
    allowed_cache_changes = {
        row["cache_path"]
        for row in data_tasks
        if row.get("stage") == "feasible"
    }
    all_executed_invariants = all(
        row["invariant_pass"]
        for row in tables["invariant_results"]
        if row["strategy_id"]
    )
    metadata_complete = all(
        all(
            row[field] not in ("unknown", "unmapped", None)
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
                "outcome",
                "next_action",
            )
        )
        for row in strategies + trials
    )
    consistency = {
        "status": "pass",
        "consistency_passed": bool(
            tuple(result["card"].strategy_id for result in results)
            == EXPECTED_STRATEGY_IDS
            and len(sources) == len(strategies) == len(trials) == 4
            and len({row["trial_id"] for row in trials}) == 4
            and all(row["parent_trial_id"] == "" for row in trials)
            and all(row["adaptation_label"] == "" for row in trials)
            and metadata_complete
            and all(result["outcome"] in ALLOWED_OUTCOMES for result in results)
            and all(
                result["failure_reason"] in ALLOWED_FAILURE_REASONS
                for result in results
            )
            and protected_before == protected_after
            and prior_aggregate_before == prior_aggregate_after
            and set(cache_changed).issubset(allowed_cache_changes)
            and source_attachment_hash_before == source_attachment_hash_after
            and all_executed_invariants
            and funnel["outcome_count_reconciles"]
            and not any(FORBIDDEN_FLAGS.values())
        ),
        "exact_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "exactly_four_strategy_configurations": len(strategies) == 4,
        "exactly_four_canonical_trials": len(trials) == 4,
        "unique_trial_ids": len({row["trial_id"] for row in trials}) == 4,
        "canonical_trials_have_blank_parent_and_adaptation": all(
            row["parent_trial_id"] == "" and row["adaptation_label"] == ""
            for row in trials
        ),
        "required_metadata_complete": metadata_complete,
        "source_packet_repository_directory_present": SOURCE_PACKET_DIR.exists(),
        "source_packet_attachment_present": SOURCE_PACKET_ATTACHMENT.exists(),
        "source_packet_attachment_hash": source_attachment_hash_after,
        "source_packet_unchanged": (
            source_attachment_hash_before == source_attachment_hash_after
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_file_count": len(prior_files_before),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_aggregate_before == prior_aggregate_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "cache_changed_paths": cache_changed,
        "cache_changes_authorized_and_logged": set(cache_changed).issubset(
            allowed_cache_changes
        ),
        "bounded_provider_attempt_count": len(data_tasks),
        "all_executed_invariants_passed": all_executed_invariants,
        "portfolio_contribution_uses_monthly_rebalanced_80_20_natural_drift": True,
        "daily_fixed_weight_return_blend_used": False,
        "source_or_parameter_research_performed": False,
        "cost_diagnostics_counted_as_trials": False,
        "benchmark_references_counted_as_strategies_or_trials": False,
        "preregistration_checkpoint_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_checkpoint_hash,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "deterministic_frozen_core_hash": deterministic_core_hash(),
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    if not consistency["consistency_passed"]:
        consistency["status"] = "fail"

    manifest = {
        "batch_id": BATCH_ID,
        "mode": MODE,
        "stage": STAGE,
        "source_library_id": SOURCE_LIBRARY_ID,
        "source_packet_repository_status": (
            "present" if SOURCE_PACKET_DIR.exists() else "missing_attachment_used"
        ),
        "strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "strategy_configuration_count": 4,
        "canonical_experiment_trial_count": 4,
        "executed_trial_count": funnel["experiment_trials_executed"],
        "benchmark_reference_count": len(benchmarks),
        "data_capability_task_count": len(data_tasks),
        "process_task_count": 1,
        "preregistration_checkpoint_hash": preregistration_checkpoint_hash,
        "preregistration_written_before_performance_calculation": True,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "validation_claimed": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "lifecycle_state_changed": False,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        sources,
        list(sources[0]),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategies,
        list(strategies[0]),
    )
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    data_task_fields = [
        "task_id",
        "entity_type",
        "stage",
        "adaptation_label",
        "symbol",
        "provider",
        "attempted",
        "attempt_count",
        "status",
        "cache_path",
        "cache_hash",
        "failure_reason",
        "counted_as_strategy",
        "counted_as_trial",
    ]
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_tasks,
        data_task_fields,
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", process, list(process[0]))
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0]),
    )
    metric_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "entity_type",
        "stage",
        "row_type",
        "control_id",
        "route",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "outcome",
        "failure_reason",
        "decision_reason",
        "missing_symbols",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "all_trial_results.csv",
        tables["all_trial_results"],
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "control_results.csv",
        tables["control_results"],
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        tables["chronological_half_results"],
        metric_fields,
    )
    portfolio_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "route",
        "portfolio_id",
        "portfolio_construction",
        "period_label",
        "period_role",
        "cost_assumption_bps",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_result_rows,
        portfolio_fields,
    )
    turnover_fields = [
        "record_scope",
        "strategy_id",
        "control_or_portfolio_id",
        "cost_assumption_bps",
        "total_one_way_turnover",
        "trade_or_rebalance_count",
        "transaction_cost_drag",
        "turnover_formula",
        "natural_drift_between_rebalances",
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        tables["turnover_cost_reconciliation"],
        turnover_fields,
    )
    diagnostic_fields = {
        "recovery_signal_diagnostics": [
            "strategy_id",
            "formation_sequence",
            "formation_date",
            "execution_date",
            "window_start",
            "selected_sectors",
            "ordinary_loser_selected_sectors",
            "selection_overlap_count",
            "recovery_scores",
            "maximum_drawdown_trough_dates",
            "six_week_cumulative_log_returns",
            "vintage_id",
            "vintage_composition",
            "active_vintage_count",
            "vintage_expiration_execution_date",
            "vintage_holding_return",
            "signal_complete",
        ],
        "olmar_weight_diagnostics": [
            "strategy_id",
            "record_type",
            "signal_date",
            "execution_date",
            "warmup_complete",
            "predicted_price_relatives",
            "denominator",
            "lambda",
            "target_weights",
            "minimum_asset_weight",
            "maximum_asset_weight",
            "effective_holdings",
            "any_weight_exceeds_50pct",
            "percentage_days_any_weight_exceeds_50pct",
            "realized_one_way_turnover_5bps",
        ],
        "dogs_vintage_diagnostics": [
            "strategy_id",
            "formation_year",
            "formation_date",
            "execution_date",
            "annual_country_returns",
            "country_rank_order",
            "selected_countries",
            "vintage_start_date",
            "vintage_expiration_year",
            "active_vintage_count",
            "independent_formation_year_count",
        ],
        "high52_vintage_diagnostics": [
            "strategy_id",
            "formation_sequence",
            "formation_date",
            "execution_date",
            "high52_ratios",
            "selected_sectors",
            "six_month_momentum_scores",
            "momentum_selected_sectors",
            "selection_overlap_count",
            "vintage_composition",
            "vintage_expiration_execution_date",
            "holding_period_return",
            "warmup_complete",
        ],
    }
    for name, rows in diagnostics.items():
        write_csv(OUTPUT_DIR / f"{name}.csv", rows, diagnostic_fields[name])
    invariant_fields = [
        "strategy_id",
        "record_type",
        "control_or_portfolio_id",
        "cost_assumption_bps",
        "explicit_zero_weights",
        "natural_drift_between_rebalances",
        "stale_weight_forward_fill_used",
        "negative_weights_present",
        "same_period_price_signal_return_used",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_invariant_status",
        "weight_invariant_status",
        "invariant_pass",
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        tables["invariant_results"],
        invariant_fields,
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        outcomes,
        list(outcomes[0]),
    )
    failure_fields = [
        "strategy_id",
        "family_id",
        "outcome",
        "failure_reason",
        "decision_reason",
        "missing_symbols",
    ]
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failures, failure_fields)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcomes, list(outcomes[0]))
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, funnel, next_action))

    return {
        "batch_id": BATCH_ID,
        "output_dir": rel(OUTPUT_DIR),
        "executed_trial_count": funnel["experiment_trials_executed"],
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "followup_candidate_count": (
            funnel["standalone_followup_candidates"]
            + funnel["diversifier_followup_candidates"]
        ),
        "exact_next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
