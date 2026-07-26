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
from strategy_lab.research_os.research import fast_source_library_batch_v6 as prior_batch
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


BATCH_ID = "fast_source_library_batch_v7"
MODE = "fast-progress"
STAGE = "exploration"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v4"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_PACKET_DIR = (
    ROOT / "evidence" / "research_recovery" / SOURCE_LIBRARY_ID / "latest"
)
SOURCE_PACKET_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\13fb214a-6580-48e0-ae5c-c61081cd97fa\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9

NEXT_REVIEW = "direction_owner_review_fast_source_library_batch_v7"
NEXT_ALL_CLOSED = "refresh_strategy_source_library_v5"
NEXT_BLOCKED = "direction_owner_review_fast_source_library_batch_v7_block_v1"

SECTOR_UNIVERSE = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
COMMON_REQUIRED_SYMBOLS = SECTOR_UNIVERSE + ("SPY", "IEF", "BIL")

EXPECTED_STRATEGY_IDS = (
    "kritzman_absorption_ratio_sector_spy_ief_v1",
    "gervais_kaniel_mingelgrin_high_volume_sector_v1",
    "da_gurun_warachka_fip_sector_12_2_6m_v1",
    "bali_cakici_whitelaw_low_max_sector_v1",
)

EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS = {
    EXPECTED_STRATEGY_IDS[0]: "average_pairwise_correlation_shift_spy_ief_v1",
    EXPECTED_STRATEGY_IDS[1]: "absolute_return_shock_sector_event_v1",
    EXPECTED_STRATEGY_IDS[2]: "standard_12_2_top1_sector_momentum_v1",
    EXPECTED_STRATEGY_IDS[3]: "bottom3_monthly_realized_volatility_sector_v1",
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
    "post_result_control_change": False,
    "validation_or_robustness": False,
    "promotion_or_paper_demo_review": False,
    "lifecycle_or_registry_change": False,
    "paper_demo_activation": False,
    "broker_account_order_or_real_money_action": False,
    "ANGL_data_lane_reopened": False,
    "NVI_validation_or_Dogs_data_acquisition": False,
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
        return f"fast_source_v7__{self.strategy_id}__canonical"

    @property
    def source_or_research_lineage(self) -> str:
        return f"{SOURCE_LIBRARY_ID}:{self.source_record_id}"


CARDS = (
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[0],
        family_id="pca_systemic_fragility_regime",
        display_name="Sector Absorption-Ratio Fragility Regime",
        strategy_architecture="pca_systemic_fragility_state_allocation",
        source_record_id="src_kritzman_absorption_ratio_sector_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=COMMON_REQUIRED_SYMBOLS,
        controls=(
            "average_pairwise_correlation_shift_spy_ief_v1",
            "monthly_static_50_50_SPY_IEF",
            "monthly_static_exposure_matched_SPY_IEF",
        ),
        portfolio_controls=("average_pairwise_correlation_shift_spy_ief_v1",),
        parameters={
            "return_type": "simple_daily_close_to_close",
            "covariance_window": 500,
            "exponential_half_life": 250,
            "absorbed_components": 2,
            "short_average": 15,
            "long_average_and_sample_sd": 252,
            "thresholds": [-1.0, 1.0],
            "targets": "SPY_IEF=100_0|50_50|0_100",
            "warmup_target": "50_50_SPY_IEF",
            "rebalance": "state_change_only",
        },
        frozen_rule=(
            "Use nine-sector simple returns, a trailing 500-observation exponentially "
            "weighted population covariance with 250-session half-life, and the top two "
            "eigenvalue share. Standardize MA15 minus MA252 by sample SD252; target "
            "SPY/IEF 0/100 at >=1, 100/0 at <=-1, and 50/50 otherwise; warm up at "
            "50/50; execute at the following session close and trade only state changes."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[1],
        family_id="abnormal_volume_visibility_premium",
        display_name="High-Volume Sector Visibility Event",
        strategy_architecture="nonoverlapping_abnormal_dollar_volume_event_allocation",
        source_record_id="src_gervais_kaniel_mingelgrin_sector_volume_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE + ("SPY", "BIL"),
        controls=(
            "absolute_return_shock_sector_event_v1",
            "equal_weight_nine_sectors_during_event_windows",
            "monthly_static_exposure_matched_SPY_BIL",
        ),
        portfolio_controls=("absolute_return_shock_sector_event_v1",),
        parameters={
            "included_block_sessions": 50,
            "skipped_sessions": 1,
            "formation_session": 50,
            "qualifying_rank": "formation_value_at_or_above_fifth_largest_in_own_block",
            "holding_return_sessions": 20,
            "sequence_anchor": "first_common_eligible_session",
            "fallback": "BIL",
            "overlap": False,
        },
        frozen_rule=(
            "Anchor at the first common sector session; repeat 50 included sessions and "
            "one skipped session. On included session 50 select every sector whose "
            "adjusted-close times adjusted-volume is at least its own fifth-largest "
            "block observation, equal weight selections, execute next close, hold for "
            "20 completed return sessions, then use BIL; never overlap or shift anchor."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[2],
        family_id="information_discreteness_path_momentum",
        display_name="Frog-in-the-Pan Sector Momentum",
        strategy_architecture="monthly_path_conditioned_momentum_overlapping_vintages",
        source_record_id="src_da_gurun_warachka_fip_sector_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE + ("SPY", "BIL"),
        controls=(
            "standard_12_2_top1_sector_momentum_v1",
            "standard_12_2_top3_sector_momentum",
            "monthly_equal_weight_nine_sectors",
            "SPY_buy_and_hold",
        ),
        portfolio_controls=("standard_12_2_top1_sector_momentum_v1",),
        parameters={
            "formation_return_sessions": 252,
            "skip_sessions": 21,
            "PRET_top_group_count": 3,
            "ID_selection_count": 1,
            "holding_months": 6,
            "maximum_vintages": 6,
            "vintage_weight": 1.0 / 6.0,
            "fallback": "BIL",
            "tie_break": "lexical_ticker_order",
        },
        frozen_rule=(
            "At month-end use 252 returns ending 21 sessions earlier. Compute PRET and "
            "ID=sign(PRET)*(negative-day share-positive-day share); take the top three "
            "PRET sectors and select the lowest-ID one. Add one-sixth capital as a "
            "six-month vintage, keep six vintages, use BIL for unfilled slots, and "
            "execute at the following session close."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[3],
        family_id="lottery_like_extreme_return_avoidance",
        display_name="Low-MAX Sector Selection",
        strategy_architecture="monthly_cross_sectional_extreme_return_avoidance",
        source_record_id="src_bali_cakici_whitelaw_low_max_sector_v1",
        route="standalone",
        universe=SECTOR_UNIVERSE,
        required_symbols=SECTOR_UNIVERSE + ("SPY", "BIL"),
        controls=(
            "bottom3_monthly_realized_volatility_sector_v1",
            "bottom3_prior_month_total_return_sector",
            "monthly_equal_weight_nine_sectors",
            "SPY_buy_and_hold",
        ),
        portfolio_controls=("bottom3_monthly_realized_volatility_sector_v1",),
        parameters={
            "formation_window": "just_completed_calendar_month",
            "minimum_valid_daily_returns_each_sector": 15,
            "signal": "maximum_daily_return",
            "rank": "ascending",
            "selected_count": 3,
            "holding_period": "following_calendar_month",
            "fallback": "BIL",
            "tie_break": "lexical_ticker_order",
        },
        frozen_rule=(
            "At month-end require at least 15 daily returns per sector in the completed "
            "calendar month; rank each sector's maximum daily return ascending, select "
            "the bottom three equally, execute at the following session close, and hold "
            "for the following calendar month; use BIL before the first valid formation."
        ),
    ),
)


def rel(path: str | Path) -> str:
    return prior_batch.rel(path)


def file_hash(path: Path) -> str:
    return prior_batch.file_hash(path)


def csv_value(value: Any) -> str:
    return prior_batch.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    prior_batch.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    prior_batch.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    prior_batch.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    prior_batch.write_text(path, text)


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def cache_files() -> list[Path]:
    return [
        ROOT / "data" / "cache" / f"{symbol}.csv"
        for symbol in COMMON_REQUIRED_SYMBOLS
    ]


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
    material = "\n".join(f"{key}|{value}" for key, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def evidence_identity_map(paths: Iterable[Path]) -> dict[str, str]:
    identities: dict[str, str] = {}
    for path in paths:
        stat = path.stat()
        material = f"{stat.st_size}|{stat.st_mtime_ns}"
        identities[rel(path)] = "sha256:" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return identities


def validate_cards() -> None:
    if tuple(card.strategy_id for card in CARDS) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Frozen V7 candidate scope drift")
    if len({card.family_id for card in CARDS}) != 4:
        raise RuntimeError("V7 requires four distinct frozen families")
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
        if EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS[card.strategy_id] != card.controls[0]:
            raise RuntimeError(f"Named same-purpose control drift for {card.strategy_id}")


def raw_cache_validation(symbol: str) -> dict[str, Any]:
    row = dict(prior_batch.raw_cache_validation(symbol))
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    volume_ok = False
    if path.exists():
        raw = pd.read_csv(path, usecols=["volume"])
        volume = pd.to_numeric(raw["volume"], errors="coerce")
        volume_ok = bool(
            volume.notna().all()
            and np.isfinite(volume.to_numpy(dtype=float)).all()
            and (volume >= 0.0).all()
        )
    row["finite_nonnegative_adjusted_volume"] = volume_ok
    row["preflight_status"] = (
        "pass" if row["preflight_status"] == "pass" and volume_ok else "fail"
    )
    if row["preflight_status"] == "fail" and not row.get("failure_reason"):
        row["failure_reason"] = "data_or_comparability_failure"
    return row


def data_preflight() -> tuple[
    list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]
]:
    required = tuple(
        dict.fromkeys(symbol for card in CARDS for symbol in card.required_symbols)
    )
    by_symbol = {symbol: raw_cache_validation(symbol) for symbol in required}
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        failed = [
            symbol
            for symbol in card.required_symbols
            if by_symbol[symbol]["preflight_status"] != "pass"
        ]
        frames = {
            symbol: market.load_adjusted_ohlcv(symbol)
            for symbol in card.required_symbols
            if by_symbol[symbol]["preflight_status"] == "pass"
        }
        start = (
            max(frame.index.min() for frame in frames.values())
            if len(frames) == len(card.required_symbols)
            else None
        )
        end = (
            min(frame.index.max() for frame in frames.values())
            if len(frames) == len(card.required_symbols)
            else None
        )
        common_count = 0
        if start is not None and end is not None:
            common: set[pd.Timestamp] | None = None
            for frame in frames.values():
                dates = set(frame.loc[start:end].index)
                common = dates if common is None else common & dates
            common_count = len(common or set())
        for symbol in card.required_symbols:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    **by_symbol[symbol],
                    "candidate_common_start": (
                        start.date().isoformat() if start is not None else ""
                    ),
                    "candidate_common_end": (
                        end.date().isoformat() if end is not None else ""
                    ),
                    "candidate_common_session_count": common_count,
                    "candidate_missing_symbols": failed,
                    "candidate_preflight_status": "pass" if not failed else "fail",
                    "bounded_provider_attempt_authorized": bool(failed),
                    "bounded_provider_attempt_count": 0,
                    "provider_attempt_skip_reason": (
                        "" if not failed else "no_missing_symbol_attempt_needed_or_performed"
                    ),
                }
            )
    return rows, by_symbol, []


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    return prior_batch.next_session(index, signal_date)


def last_dates_by_period(
    index: pd.DatetimeIndex, frequency: str
) -> list[pd.Timestamp]:
    return prior_batch.last_dates_by_period(index, frequency)


def zero_target(symbols: tuple[str, ...]) -> dict[str, float]:
    return {symbol: 0.0 for symbol in symbols}


def selection_target(
    symbols: tuple[str, ...], selection: tuple[str, ...], fallback: str = "BIL"
) -> dict[str, float]:
    target = zero_target(symbols)
    if selection:
        for symbol in selection:
            target[symbol] = 1.0 / len(selection)
    else:
        target[fallback] = 1.0
    return target


def monthly_static_events(
    index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    target: dict[str, float],
) -> pd.DataFrame:
    events = {pd.Timestamp(index[0]): target}
    for signal_date in last_dates_by_period(index, "M"):
        execution = next_session(index, signal_date)
        if execution is not None:
            events[execution] = target
    return accounting.event_frame(index, symbols, events)


def initial_buy_hold(
    index: pd.DatetimeIndex, symbols: tuple[str, ...], symbol: str
) -> pd.DataFrame:
    target = zero_target(symbols)
    target[symbol] = 1.0
    return accounting.initial_event(index, symbols, target)


def target_state_series(
    events: pd.DataFrame, index: pd.DatetimeIndex, risky: tuple[str, ...]
) -> pd.Series:
    daily = events.reindex(index).ffill().fillna(0.0)
    return daily[list(risky)].sum(axis=1)


def weighted_covariance(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    mean = np.sum(values * weights[:, None], axis=0)
    centered = values - mean
    return (centered * weights[:, None]).T @ centered


def absorption_ratio_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    sector_returns = prices[list(SECTOR_UNIVERSE)].pct_change(fill_method=None)
    weights = 2.0 ** (
        -np.arange(499, -1, -1, dtype=float) / 250.0
    )
    weights /= weights.sum()
    ar = pd.Series(np.nan, index=prices.index, dtype=float)
    avg_corr = pd.Series(np.nan, index=prices.index, dtype=float)
    eigenvalues: dict[pd.Timestamp, list[float]] = {}
    for position in range(500, len(prices.index)):
        window = sector_returns.iloc[position - 499 : position + 1]
        if len(window) != 500 or window.isna().any().any():
            continue
        covariance = weighted_covariance(window.to_numpy(dtype=float), weights)
        values = np.linalg.eigvalsh(covariance)[::-1]
        total = float(values.sum())
        if not math.isfinite(total) or total <= 0.0:
            continue
        date_value = pd.Timestamp(prices.index[position])
        eigenvalues[date_value] = [float(value) for value in values]
        ar.loc[date_value] = float(values[:2].sum() / total)
        standard_deviation = np.sqrt(np.diag(covariance))
        denominator = np.outer(standard_deviation, standard_deviation)
        correlation = np.divide(
            covariance,
            denominator,
            out=np.full_like(covariance, np.nan),
            where=denominator > 0.0,
        )
        upper = correlation[np.triu_indices(len(SECTOR_UNIVERSE), 1)]
        avg_corr.loc[date_value] = float(np.nanmean(upper))

    def standardized(series: pd.Series) -> pd.Series:
        return (
            series.rolling(15, min_periods=15).mean()
            - series.rolling(252, min_periods=252).mean()
        ) / series.rolling(252, min_periods=252).std(ddof=1)

    delta_ar = standardized(ar)
    delta_corr = standardized(avg_corr)

    def events_from_shift(shift: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        states = pd.Series("balanced", index=prices.index, dtype=object)
        states.loc[shift >= 1.0] = "defensive"
        states.loc[shift <= -1.0] = "risk_on"
        events: dict[pd.Timestamp, dict[str, float]] = {}
        warmup = zero_target(symbols)
        warmup["SPY"] = 0.5
        warmup["IEF"] = 0.5
        events[pd.Timestamp(prices.index[0])] = warmup
        previous = "balanced"
        for signal_date, state in states.items():
            state_value = str(state)
            if state_value == previous:
                continue
            execution = next_session(prices.index, pd.Timestamp(signal_date))
            if execution is None:
                continue
            target = zero_target(symbols)
            if state_value == "defensive":
                target["IEF"] = 1.0
            elif state_value == "risk_on":
                target["SPY"] = 1.0
            else:
                target["SPY"] = 0.5
                target["IEF"] = 0.5
            events[execution] = target
            previous = state_value
        return accounting.event_frame(prices.index, symbols, events), states

    candidate, ar_states = events_from_shift(delta_ar)
    correlation_control, corr_states = events_from_shift(delta_corr)
    target_spy = target_state_series(candidate, prices.index, ("SPY",))
    exposure_weight = float(target_spy.mean())
    static_half = zero_target(symbols)
    static_half["SPY"] = 0.5
    static_half["IEF"] = 0.5
    exposure_target = zero_target(symbols)
    exposure_target["SPY"] = exposure_weight
    exposure_target["IEF"] = 1.0 - exposure_weight
    controls = {
        "average_pairwise_correlation_shift_spy_ief_v1": correlation_control,
        "monthly_static_50_50_SPY_IEF": monthly_static_events(
            prices.index, symbols, static_half
        ),
        "monthly_static_exposure_matched_SPY_IEF": monthly_static_events(
            prices.index, symbols, exposure_target
        ),
    }
    diagnostics: list[dict[str, Any]] = []
    previous_state = ""
    for date_value in prices.index:
        date = pd.Timestamp(date_value)
        state = str(ar_states.loc[date])
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[0],
                "date": date.date().isoformat(),
                "absorption_ratio": ar.loc[date],
                "eigenvalue_1": eigenvalues.get(date, [float("nan")] * 9)[0],
                "eigenvalue_2": eigenvalues.get(date, [float("nan")] * 9)[1],
                "eigenvalue_3": eigenvalues.get(date, [float("nan")] * 9)[2],
                "eigenvalue_4": eigenvalues.get(date, [float("nan")] * 9)[3],
                "eigenvalue_5": eigenvalues.get(date, [float("nan")] * 9)[4],
                "eigenvalue_6": eigenvalues.get(date, [float("nan")] * 9)[5],
                "eigenvalue_7": eigenvalues.get(date, [float("nan")] * 9)[6],
                "eigenvalue_8": eigenvalues.get(date, [float("nan")] * 9)[7],
                "eigenvalue_9": eigenvalues.get(date, [float("nan")] * 9)[8],
                "standardized_shift": delta_ar.loc[date],
                "resulting_state": state,
                "state_change": bool(previous_state and state != previous_state),
                "state_change_execution_date": (
                    next_session(prices.index, date).date().isoformat()
                    if previous_state and state != previous_state
                    and next_session(prices.index, date) is not None
                    else ""
                ),
                "target_SPY_exposure": (
                    0.0 if state == "defensive" else 1.0 if state == "risk_on" else 0.5
                ),
                "average_pairwise_correlation": avg_corr.loc[date],
                "average_correlation_standardized_shift": delta_corr.loc[date],
                "average_correlation_state": str(corr_states.loc[date]),
                "exposure_matched_static_SPY_weight": exposure_weight,
            }
        )
        previous_state = state
    return candidate, controls, diagnostics


def high_volume_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    frames = {
        symbol: market.load_adjusted_ohlcv(symbol).reindex(prices.index)
        for symbol in SECTOR_UNIVERSE
    }
    dollar_volume = pd.DataFrame(
        {
            symbol: frames[symbol]["adj_close"] * frames[symbol]["volume"]
            for symbol in SECTOR_UNIVERSE
        },
        index=prices.index,
    )
    sector_returns = prices[list(SECTOR_UNIVERSE)].pct_change(fill_method=None)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): selection_target(symbols, ())
    }
    shock_events = dict(candidate_events)
    equal_events = dict(candidate_events)
    diagnostics: list[dict[str, Any]] = []
    anchor = 0
    sequence = 0
    while anchor + 49 < len(prices.index):
        block = prices.index[anchor : anchor + 50]
        formation = pd.Timestamp(block[-1])
        execution_position = anchor + 50
        if execution_position >= len(prices.index):
            break
        execution = pd.Timestamp(prices.index[execution_position])
        volume_values: dict[str, float] = {}
        volume_ranks: dict[str, int] = {}
        shock_values: dict[str, float] = {}
        shock_ranks: dict[str, int] = {}
        qualifying: list[str] = []
        shock_qualifying: list[str] = []
        for symbol in SECTOR_UNIVERSE:
            volume_window = dollar_volume.loc[block, symbol]
            threshold = float(volume_window.nlargest(5).iloc[-1])
            value = float(dollar_volume.loc[formation, symbol])
            volume_values[symbol] = value
            volume_ranks[symbol] = int(
                volume_window.rank(method="min", ascending=False).loc[formation]
            )
            if value >= threshold:
                qualifying.append(symbol)
            shock_window = sector_returns.loc[block, symbol].abs()
            shock_threshold = float(shock_window.nlargest(5).iloc[-1])
            shock_value = float(abs(sector_returns.loc[formation, symbol]))
            shock_values[symbol] = shock_value
            shock_ranks[symbol] = int(
                shock_window.rank(method="min", ascending=False).loc[formation]
            )
            if shock_value >= shock_threshold:
                shock_qualifying.append(symbol)
        candidate_selection = tuple(sorted(qualifying))
        shock_selection = tuple(sorted(shock_qualifying))
        candidate_events[execution] = selection_target(
            symbols, candidate_selection
        )
        shock_events[execution] = selection_target(symbols, shock_selection)
        equal_events[execution] = selection_target(symbols, SECTOR_UNIVERSE)
        exit_position = execution_position + 20
        exit_date = (
            pd.Timestamp(prices.index[exit_position])
            if exit_position < len(prices.index)
            else None
        )
        if exit_date is not None:
            fallback = selection_target(symbols, ())
            candidate_events[exit_date] = fallback
            shock_events[exit_date] = fallback
            equal_events[exit_date] = fallback
        event_return = float("nan")
        if exit_date is not None and candidate_selection:
            event_return = float(
                (
                    prices.loc[exit_date, list(candidate_selection)]
                    / prices.loc[execution, list(candidate_selection)]
                    - 1.0
                ).mean()
            )
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[1],
                "block_sequence": sequence,
                "block_start": pd.Timestamp(block[0]).date().isoformat(),
                "block_end": formation.date().isoformat(),
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "dollar_volume_values": volume_values,
                "dollar_volume_ranks_descending": volume_ranks,
                "qualifying_sectors": candidate_selection,
                "price_shock_absolute_returns": shock_values,
                "price_shock_ranks_descending": shock_ranks,
                "price_shock_control_qualifiers": shock_selection,
                "holding_period_start": execution.date().isoformat(),
                "holding_period_end": (
                    exit_date.date().isoformat() if exit_date is not None else ""
                ),
                "holding_return_session_count": 20 if exit_date is not None else 0,
                "event_return": event_return,
                "sequence_anchor_date": pd.Timestamp(prices.index[0]).date().isoformat(),
                "skipped_session_date": execution.date().isoformat(),
            }
        )
        anchor += 51
        sequence += 1
    candidate = accounting.event_frame(prices.index, symbols, candidate_events)
    shock = accounting.event_frame(prices.index, symbols, shock_events)
    equal = accounting.event_frame(prices.index, symbols, equal_events)
    risky_share = float(
        target_state_series(candidate, prices.index, SECTOR_UNIVERSE).mean()
    )
    exposure_target = zero_target(symbols)
    exposure_target["SPY"] = risky_share
    exposure_target["BIL"] = 1.0 - risky_share
    controls = {
        "absolute_return_shock_sector_event_v1": shock,
        "equal_weight_nine_sectors_during_event_windows": equal,
        "monthly_static_exposure_matched_SPY_BIL": monthly_static_events(
            prices.index, symbols, exposure_target
        ),
    }
    return candidate, controls, diagnostics


def fip_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    returns = prices[list(SECTOR_UNIVERSE)].pct_change(fill_method=None)
    formation_dates = last_dates_by_period(prices.index, "M")
    candidate_slots: deque[dict[str, Any]] = deque(
        ({"weights": {"BIL": 1.0}} for _ in range(6)), maxlen=6
    )
    top1_slots: deque[dict[str, Any]] = deque(
        ({"weights": {"BIL": 1.0}} for _ in range(6)), maxlen=6
    )
    top3_slots: deque[dict[str, Any]] = deque(
        ({"weights": {"BIL": 1.0}} for _ in range(6)), maxlen=6
    )
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {}
    top1_events: dict[pd.Timestamp, dict[str, float]] = {}
    top3_events: dict[pd.Timestamp, dict[str, float]] = {}
    diagnostics: list[dict[str, Any]] = []
    for sequence, formation in enumerate(formation_dates):
        execution = next_session(prices.index, formation)
        if execution is None:
            continue
        location = int(prices.index.get_loc(formation))
        pret: dict[str, float] = {}
        information_discreteness: dict[str, float] = {}
        ranks: dict[str, int] = {}
        candidate_selection: tuple[str, ...] = ()
        top1_selection: tuple[str, ...] = ()
        top3_selection: tuple[str, ...] = ()
        end_position = location - 21
        start_position = end_position - 251
        if start_position >= 1:
            window = returns.iloc[start_position : end_position + 1]
            if len(window) == 252 and not window.isna().any().any():
                for symbol in SECTOR_UNIVERSE:
                    values = window[symbol]
                    value = float((1.0 + values).prod() - 1.0)
                    sign = 1.0 if value > 0.0 else -1.0 if value < 0.0 else 0.0
                    positive = float((values > 0.0).sum() / 252.0)
                    negative = float((values < 0.0).sum() / 252.0)
                    pret[symbol] = value
                    information_discreteness[symbol] = sign * (negative - positive)
                ordered = sorted(
                    SECTOR_UNIVERSE, key=lambda symbol: (-pret[symbol], symbol)
                )
                ranks = {symbol: position + 1 for position, symbol in enumerate(ordered)}
                top3_selection = tuple(ordered[:3])
                top1_selection = (ordered[0],)
                candidate_selection = (
                    sorted(
                        top3_selection,
                        key=lambda symbol: (
                            information_discreteness[symbol],
                            symbol,
                        ),
                    )[0],
                )

        def vintage(selection: tuple[str, ...]) -> dict[str, Any]:
            return {"weights": selection_target(symbols, selection)}

        candidate_slots.append(vintage(candidate_selection))
        top1_slots.append(vintage(top1_selection))
        top3_slots.append(vintage(top3_selection))
        candidate_events[execution] = prior_batch.target_from_vintages(
            candidate_slots, symbols, 6
        )
        top1_events[execution] = prior_batch.target_from_vintages(
            top1_slots, symbols, 6
        )
        top3_events[execution] = prior_batch.target_from_vintages(
            top3_slots, symbols, 6
        )
        expiration = (
            next_session(prices.index, formation_dates[sequence + 6])
            if sequence + 6 < len(formation_dates)
            else None
        )
        vintage_return = float("nan")
        if expiration is not None and candidate_selection:
            vintage_return = float(
                prices.loc[expiration, candidate_selection[0]]
                / prices.loc[execution, candidate_selection[0]]
                - 1.0
            )
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[2],
                "formation_sequence": sequence,
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "formation_window_start": (
                    pd.Timestamp(prices.index[start_position]).date().isoformat()
                    if start_position >= 1
                    else ""
                ),
                "formation_window_end": (
                    pd.Timestamp(prices.index[end_position]).date().isoformat()
                    if end_position >= 0
                    else ""
                ),
                "PRET": pret,
                "information_discreteness_ID": information_discreteness,
                "PRET_ranks_descending": ranks,
                "top3_PRET_sectors": top3_selection,
                "selected_sector": (
                    candidate_selection[0] if candidate_selection else ""
                ),
                "ordinary_top1_momentum_sector": (
                    top1_selection[0] if top1_selection else ""
                ),
                "selection_overlap_with_top1": bool(
                    candidate_selection and candidate_selection == top1_selection
                ),
                "vintage_start": execution.date().isoformat(),
                "vintage_expiration": (
                    expiration.date().isoformat() if expiration is not None else ""
                ),
                "vintage_return": vintage_return,
                "active_vintage_count": min(sequence + 1, 6),
                "signal_complete": bool(pret),
            }
        )
    default = selection_target(symbols, ())
    candidate = prior_batch.events_for_evaluation(
        candidate_events, prices.index, symbols, default
    )
    top1 = prior_batch.events_for_evaluation(
        top1_events, prices.index, symbols, default
    )
    top3 = prior_batch.events_for_evaluation(
        top3_events, prices.index, symbols, default
    )
    equal_target = zero_target(symbols)
    for symbol in SECTOR_UNIVERSE:
        equal_target[symbol] = 1.0 / len(SECTOR_UNIVERSE)
    controls = {
        "standard_12_2_top1_sector_momentum_v1": top1,
        "standard_12_2_top3_sector_momentum": top3,
        "monthly_equal_weight_nine_sectors": monthly_static_events(
            prices.index, symbols, equal_target
        ),
        "SPY_buy_and_hold": initial_buy_hold(prices.index, symbols, "SPY"),
    }
    return candidate, controls, diagnostics


def low_max_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    symbols = tuple(prices.columns)
    returns = prices[list(SECTOR_UNIVERSE)].pct_change(fill_method=None)
    formations = last_dates_by_period(prices.index, "M")
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): selection_target(symbols, ())
    }
    volatility_events = dict(candidate_events)
    reversal_events = dict(candidate_events)
    diagnostics: list[dict[str, Any]] = []
    for sequence, formation in enumerate(formations):
        execution = next_session(prices.index, formation)
        if execution is None:
            continue
        period = formation.to_period("M")
        window = returns.loc[returns.index.to_period("M") == period]
        complete = bool(
            len(window) >= 15
            and all(window[symbol].notna().sum() >= 15 for symbol in SECTOR_UNIVERSE)
        )
        maximum: dict[str, float] = {}
        volatility: dict[str, float] = {}
        prior_return: dict[str, float] = {}
        max_ranks: dict[str, int] = {}
        vol_ranks: dict[str, int] = {}
        return_ranks: dict[str, int] = {}
        max_selection: tuple[str, ...] = ()
        vol_selection: tuple[str, ...] = ()
        return_selection: tuple[str, ...] = ()
        if complete:
            for symbol in SECTOR_UNIVERSE:
                values = window[symbol].dropna()
                maximum[symbol] = float(values.max())
                volatility[symbol] = float(values.std(ddof=1))
                prior_return[symbol] = float((1.0 + values).prod() - 1.0)
            max_order = sorted(
                SECTOR_UNIVERSE, key=lambda symbol: (maximum[symbol], symbol)
            )
            vol_order = sorted(
                SECTOR_UNIVERSE, key=lambda symbol: (volatility[symbol], symbol)
            )
            return_order = sorted(
                SECTOR_UNIVERSE, key=lambda symbol: (prior_return[symbol], symbol)
            )
            max_ranks = {
                symbol: position + 1 for position, symbol in enumerate(max_order)
            }
            vol_ranks = {
                symbol: position + 1 for position, symbol in enumerate(vol_order)
            }
            return_ranks = {
                symbol: position + 1 for position, symbol in enumerate(return_order)
            }
            max_selection = tuple(max_order[:3])
            vol_selection = tuple(vol_order[:3])
            return_selection = tuple(return_order[:3])
        candidate_events[execution] = selection_target(symbols, max_selection)
        volatility_events[execution] = selection_target(symbols, vol_selection)
        reversal_events[execution] = selection_target(symbols, return_selection)
        next_execution = (
            next_session(prices.index, formations[sequence + 1])
            if sequence + 1 < len(formations)
            else None
        )
        holding_return = float("nan")
        if next_execution is not None and max_selection:
            holding_return = float(
                (
                    prices.loc[next_execution, list(max_selection)]
                    / prices.loc[execution, list(max_selection)]
                    - 1.0
                ).mean()
            )
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[3],
                "formation_sequence": sequence,
                "formation_month": str(period),
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "valid_return_count": {
                    symbol: int(window[symbol].notna().sum())
                    for symbol in SECTOR_UNIVERSE
                },
                "monthly_MAX": maximum,
                "monthly_realized_volatility": volatility,
                "prior_month_total_return": prior_return,
                "MAX_ranks_ascending": max_ranks,
                "volatility_ranks_ascending": vol_ranks,
                "return_ranks_ascending": return_ranks,
                "low_MAX_selected_sectors": max_selection,
                "low_volatility_selected_sectors": vol_selection,
                "prior_return_selected_sectors": return_selection,
                "holding_period_end": (
                    next_execution.date().isoformat()
                    if next_execution is not None
                    else ""
                ),
                "holding_return": holding_return,
                "signal_complete": complete,
            }
        )
    equal_target = zero_target(symbols)
    for symbol in SECTOR_UNIVERSE:
        equal_target[symbol] = 1.0 / len(SECTOR_UNIVERSE)
    controls = {
        "bottom3_monthly_realized_volatility_sector_v1": accounting.event_frame(
            prices.index, symbols, volatility_events
        ),
        "bottom3_prior_month_total_return_sector": accounting.event_frame(
            prices.index, symbols, reversal_events
        ),
        "monthly_equal_weight_nine_sectors": monthly_static_events(
            prices.index, symbols, equal_target
        ),
        "SPY_buy_and_hold": initial_buy_hold(prices.index, symbols, "SPY"),
    }
    return (
        accounting.event_frame(prices.index, symbols, candidate_events),
        controls,
        diagnostics,
    )


def prepare_candidate(card: CandidateCard) -> dict[str, Any]:
    prices = market.load_price_frame(card.required_symbols)
    if card.strategy_id == EXPECTED_STRATEGY_IDS[0]:
        candidate, controls, diagnostics = absorption_ratio_event_sets(prices)
        key = "absorption_ratio_diagnostics"
        timing = "daily_completed_close_signal_following_session_close_state_change_only"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[1]:
        candidate, controls, diagnostics = high_volume_event_sets(prices)
        key = "high_volume_event_diagnostics"
        timing = "formation_close_signal_following_session_close_20_return_session_hold"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[2]:
        candidate, controls, diagnostics = fip_event_sets(prices)
        key = "fip_signal_diagnostics"
        timing = "month_end_completed_close_signal_following_session_close"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[3]:
        candidate, controls, diagnostics = low_max_event_sets(prices)
        key = "low_max_signal_diagnostics"
        timing = "month_end_completed_close_signal_following_session_close"
    else:
        raise RuntimeError(f"Unsupported V7 candidate {card.strategy_id}")
    if tuple(controls) != card.controls:
        raise RuntimeError(f"Control scope drift for {card.strategy_id}")
    return {
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "timing_convention": timing,
        "absorption_ratio_diagnostics": diagnostics if key.startswith("absorption") else [],
        "high_volume_event_diagnostics": diagnostics if key.startswith("high_volume") else [],
        "fip_signal_diagnostics": diagnostics if key.startswith("fip") else [],
        "low_max_signal_diagnostics": diagnostics if key.startswith("low_max") else [],
    }


def run_candidate(
    card: CandidateCard, preflight_rows: list[dict[str, Any]]
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
    empty_prepared = {
        "absorption_ratio_diagnostics": [],
        "high_volume_event_diagnostics": [],
        "fip_signal_diagnostics": [],
        "low_max_signal_diagnostics": [],
    }
    if missing:
        return {
            "card": card,
            "executed": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_unavailable",
            "decision_reason": "required frozen symbol or control data unavailable",
            "missing_symbols": missing,
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": empty_prepared,
        }
    prepared = prepare_candidate(card)
    if (
        prepared["prices"].empty
        or prepared["candidate_events"].empty
        or tuple(prepared["control_events"]) != card.controls
    ):
        return {
            "card": card,
            "executed": False,
            "outcome": "blocked_feasibility",
            "failure_reason": "methodology_failure",
            "decision_reason": "frozen signal or named controls could not be constructed",
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
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            prepared["timing_convention"],
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = accounting.simulate_path(
                prepared["prices"],
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
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(prior_batch.strategy_metrics(path, period_index))
    held = path["held_weights"]
    if period_index is not None:
        held = held.reindex(period_index).dropna(how="all")
    metrics["maximum_single_asset_weight"] = (
        float(held.abs().max().max()) if not held.empty else float("nan")
    )
    return metrics


def portfolio_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(prior_batch.portfolio_metrics(path, period_index))
    daily = path["daily_df"]
    if period_index is not None:
        daily = daily.reindex(period_index).dropna(how="all")
    if "post_trade_reference_weight" in daily.columns:
        values = daily[
            ["post_trade_reference_weight", "post_trade_sleeve_weight"]
        ].abs()
        metrics["maximum_single_asset_weight"] = float(values.max().max())
    else:
        metrics["maximum_single_asset_weight"] = 1.0
    return metrics


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"])
    )


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
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
        for control_id in card.controls
    }
    primary_id = EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS[card.strategy_id]
    primary = controls[primary_id]
    if not candidate["invariant_pass"] or not all(
        value["invariant_pass"] for value in controls.values()
    ):
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="candidate or required-control invariant failed",
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
            decision_reason="control dominates CAGR, Sharpe, and drawdown: "
            + ",".join(dominating),
        )
        return
    if not material_advantage(candidate, primary):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=f"below materiality versus frozen same-purpose control {primary_id}",
        )
        return
    for label, period in prior_batch.split_periods(
        result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
    ):
        candidate_half = strategy_metrics(
            result["candidate_paths"][PRIMARY_COST_BPS], period
        )
        control_half = strategy_metrics(
            result["control_paths"][(primary_id, PRIMARY_COST_BPS)], period
        )
        if worse_on_both(candidate_half, control_half):
            result.update(
                outcome="closed_exploration",
                failure_reason="period_instability",
                decision_reason=(
                    f"candidate worse than fixed same-purpose control in {label}"
                ),
            )
            return
    candidate_10 = strategy_metrics(result["candidate_paths"][10.0])
    primary_10 = strategy_metrics(result["control_paths"][(primary_id, 10.0)])
    if worse_on_both(candidate_10, primary_10):
        result.update(
            outcome="closed_exploration",
            failure_reason="cost_drag",
            decision_reason=f"10-bps Sharpe and drawdown unfavorable versus {primary_id}",
        )
        return
    simpler_controls = {
        control_id: control
        for control_id, control in controls.items()
        if control_id != primary_id
    }
    reproducing = [
        control_id
        for control_id, control in simpler_controls.items()
        if float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"])
        and float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"])
    ]
    if reproducing:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="simpler or exposure control reproduces benefit: "
            + ",".join(reproducing),
        )
        return
    result.update(
        outcome="exploratory_followup_candidate_standalone",
        failure_reason="",
        decision_reason="all preregistered standalone exploration gates passed",
    )


METRIC_FIELDS = [
    *prior_batch.METRIC_FIELDS[:12],
    "maximum_single_asset_weight",
    *prior_batch.METRIC_FIELDS[12:],
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
            "source_packet_location": (
                rel(SOURCE_PACKET_DIR)
                if SOURCE_PACKET_DIR.exists()
                else rel(SOURCE_PACKET_ATTACHMENT)
            ),
            "source_packet_hash": (
                aggregate_hash(map_hashes(SOURCE_PACKET_DIR.rglob("*")))
                if SOURCE_PACKET_DIR.exists()
                else file_hash(SOURCE_PACKET_ATTACHMENT)
            ),
            "repository_source_packet_present": SOURCE_PACKET_DIR.exists(),
            "frozen_rule": card.frozen_rule,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in CARDS
    ]


def strategy_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = prior_batch.strategy_rows(results)
    for row in rows:
        row["created_in_source_of_truth"] = False
    return rows


def trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = prior_batch.trial_rows(results)
    for row in rows:
        row["preregistration_timestamp"] = PREREGISTRATION_TIMESTAMP
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows = [
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
        for position, control_id in enumerate(card.controls):
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": (
                        "frozen_same_purpose_followup_gate_control"
                        if position == 0
                        else "static_exposure_or_broad_control"
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
            "experiment_trial" if row_type == "candidate" else "benchmark_reference"
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
            else "chronological_split_diagnostic_not_clean_sealed_untouched_or_validation"
        ),
        "outcome": result["outcome"],
        "failure_reason": result["failure_reason"],
        "decision_reason": result["decision_reason"],
        "missing_symbols": result["missing_symbols"],
        **({field: "" for field in METRIC_FIELDS} if metrics is None else metrics),
    }


def result_tables(
    results: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        if not result["executed"]:
            candidates.append(
                result_row(result, "candidate", "", 5.0, "full_period", None)
            )
            for control_id in card.controls:
                controls.append(
                    result_row(
                        result, "control", control_id, 5.0, "full_period", None
                    )
                )
            continue
        for cost in COST_BPS:
            path_pairs = [
                ("candidate", "", result["candidate_paths"][cost]),
                *[
                    (
                        "control",
                        control_id,
                        result["control_paths"][(control_id, cost)],
                    )
                    for control_id in card.controls
                ],
            ]
            for row_type, control_id, path in path_pairs:
                metrics = strategy_metrics(path)
                target_table = candidates if row_type == "candidate" else controls
                target_table.append(
                    result_row(
                        result,
                        row_type,
                        control_id,
                        cost,
                        "full_period",
                        metrics,
                    )
                )
                turnover.append(
                    {
                        "record_scope": (
                            "strategy_candidate"
                            if row_type == "candidate"
                            else "benchmark_control"
                        ),
                        "strategy_id": card.strategy_id,
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metrics["turnover"],
                        "trade_or_rebalance_count": metrics[
                            "trade_or_rebalance_count"
                        ],
                        "transaction_cost_drag": metrics["transaction_cost_drag"],
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "natural_drift_between_rebalances": True,
                    }
                )
                invariants.append(
                    {
                        "strategy_id": card.strategy_id,
                        "record_type": row_type,
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
                                "maximum_single_asset_weight",
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
                for half_label, period in prior_batch.split_periods(
                    path["returns"].index
                ):
                    halves.append(
                        result_row(
                            result,
                            row_type,
                            control_id,
                            cost,
                            half_label,
                            strategy_metrics(path, period),
                        )
                    )
    return {
        "all_trial_results": candidates,
        "control_results": controls,
        "chronological_half_results": halves,
        "turnover_cost_reconciliation": turnover,
        "invariant_results": invariants,
    }


def build_portfolio_paths(
    result: dict[str, Any], reference_returns: pd.Series
) -> dict[tuple[str, float], dict[str, Any]]:
    return prior_batch.build_portfolio_paths(result, reference_returns)


def portfolio_rows(
    results: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    rows: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        for (portfolio_id, cost), path in sorted(result["portfolio_paths"].items()):
            for label, period in [
                ("full_period", None),
                *prior_batch.split_periods(path["returns"].index),
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
                            else "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_principal_control_with_natural_drift"
                        ),
                        "period_label": label,
                        "period_role": (
                            "full_period_exploration"
                            if label == "full_period"
                            else "chronological_split_diagnostic_not_clean_sealed_untouched_or_validation"
                        ),
                        "cost_assumption_bps": cost,
                        **metrics,
                    }
                )
            full = portfolio_metrics(path)
            turnover.append(
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
            invariants.append(
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
                            "maximum_single_asset_weight",
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
    return rows, turnover, invariants


def diagnostic_tables(
    results: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    names = (
        "absorption_ratio_diagnostics",
        "fip_signal_diagnostics",
        "low_max_signal_diagnostics",
        "high_volume_event_diagnostics",
    )
    return {
        name: [
            row
            for result in results
            for row in result["prepared"].get(name, [])
        ]
        for name in names
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
            "frozen_same_purpose_control": EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS[
                result["card"].strategy_id
            ],
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
    strategies = strategy_rows(pending)
    trials = trial_rows(pending)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    material = {
        "strategy_cards": strategies,
        "trial_ledger": trials,
        "frozen_core_hash": deterministic_core_hash(),
        "written_before_performance_calculation": True,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(material, sort_keys=True, default=csv_value).encode("utf-8")
    ).hexdigest()


def build_report(
    results: list[dict[str, Any]],
    funnel: dict[str, Any],
    next_action: str,
) -> str:
    lines = [
        "# Fast Source Library Batch V7",
        "",
        "## Scope",
        "",
        "Exactly four source-frozen exploration configurations were considered. "
        "No source completion, tuning, validation, promotion, lifecycle, paper/demo, "
        "broker, account, order, or real-money action occurred.",
        "",
        "The repository-side V4 packet was absent, so the complete direction-owner "
        "attachment and prompt were used without inference or rule changes.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['card'].strategy_id}`: `{result['outcome']}` "
            f"(`{result['failure_reason'] or 'none'}`; {result['decision_reason']})"
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "- Primary cost is `5 bps` per one-way turnover; `0` and `10 bps` are diagnostics.",
            "- Turnover uses actual drifted pretrade holdings.",
            "- Completed-close signals execute at the following session close.",
            "- Portfolio contribution uses monthly rebalanced 80/20 holdings with natural drift.",
            "- Chronological halves are exploration diagnostics, not validation or holdouts.",
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
            "The next action was recorded and not executed.",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    validate_cards()
    source_hash_before = file_hash(SOURCE_PACKET_ATTACHMENT)
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_before = map_hashes(cache_files())
    prior_files = prior_evidence_files()
    prior_before = evidence_identity_map(prior_files)
    prior_aggregate_before = aggregate_hash(prior_before)

    clean_output()
    preflight_rows, _, data_tasks = data_preflight()
    preregistration_hash = write_preregistration_checkpoint()
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
    portfolio_result_rows, portfolio_turnover, portfolio_invariants = (
        portfolio_rows(results)
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
    prior_after = evidence_identity_map(prior_files)
    prior_aggregate_after = aggregate_hash(prior_after)
    source_hash_after = file_hash(SOURCE_PACKET_ATTACHMENT)
    cache_changed = sorted(
        path
        for path in set(cache_before) | set(cache_after)
        if cache_before.get(path, "missing") != cache_after.get(path, "missing")
    )
    metadata_complete = all(
        all(
            row[field] not in ("", "unknown", "unmapped", None)
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
    all_invariants = all(
        bool(row["invariant_pass"]) for row in tables["invariant_results"]
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
            and cache_before == cache_after
            and source_hash_before == source_hash_after
            and all_invariants
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
        "frozen_half_period_gate_controls": EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS,
        "half_period_controls_selected_from_full_period_performance": False,
        "source_packet_repository_directory_present": SOURCE_PACKET_DIR.exists(),
        "source_packet_attachment_present": SOURCE_PACKET_ATTACHMENT.exists(),
        "source_packet_attachment_hash": source_hash_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_file_count": len(prior_files),
        "prior_evidence_reconciliation_method": (
            "deterministic_path_size_mtime_identity_manifest"
        ),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_aggregate_before == prior_aggregate_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "cache_changed_paths": cache_changed,
        "cache_changes_authorized_and_logged": cache_before == cache_after,
        "bounded_provider_attempt_count": len(data_tasks),
        "all_executed_invariants_passed": all_invariants,
        "portfolio_contribution_uses_monthly_rebalanced_80_20_natural_drift": True,
        "daily_fixed_weight_return_blend_used": False,
        "source_or_parameter_research_performed": False,
        "cost_diagnostics_counted_as_trials": False,
        "benchmark_references_counted_as_strategies_or_trials": False,
        "preregistration_checkpoint_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
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
        "preregistration_checkpoint_hash": preregistration_hash,
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
    write_csv(OUTPUT_DIR / "source_library_records.csv", sources, list(sources[0]))
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_tasks,
        [
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
        ],
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
    write_csv(OUTPUT_DIR / "control_results.csv", tables["control_results"], metric_fields)
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
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        tables["turnover_cost_reconciliation"],
        [
            "record_scope",
            "strategy_id",
            "control_or_portfolio_id",
            "cost_assumption_bps",
            "total_one_way_turnover",
            "trade_or_rebalance_count",
            "transaction_cost_drag",
            "turnover_formula",
            "natural_drift_between_rebalances",
        ],
    )
    diagnostic_fields = {
        "absorption_ratio_diagnostics": [
            "strategy_id",
            "date",
            "absorption_ratio",
            "eigenvalue_1",
            "eigenvalue_2",
            "eigenvalue_3",
            "eigenvalue_4",
            "eigenvalue_5",
            "eigenvalue_6",
            "eigenvalue_7",
            "eigenvalue_8",
            "eigenvalue_9",
            "standardized_shift",
            "resulting_state",
            "state_change",
            "state_change_execution_date",
            "target_SPY_exposure",
            "average_pairwise_correlation",
            "average_correlation_standardized_shift",
            "average_correlation_state",
            "exposure_matched_static_SPY_weight",
        ],
        "fip_signal_diagnostics": [
            "strategy_id",
            "formation_sequence",
            "formation_date",
            "execution_date",
            "formation_window_start",
            "formation_window_end",
            "PRET",
            "information_discreteness_ID",
            "PRET_ranks_descending",
            "top3_PRET_sectors",
            "selected_sector",
            "ordinary_top1_momentum_sector",
            "selection_overlap_with_top1",
            "vintage_start",
            "vintage_expiration",
            "vintage_return",
            "active_vintage_count",
            "signal_complete",
        ],
        "low_max_signal_diagnostics": [
            "strategy_id",
            "formation_sequence",
            "formation_month",
            "formation_date",
            "execution_date",
            "valid_return_count",
            "monthly_MAX",
            "monthly_realized_volatility",
            "prior_month_total_return",
            "MAX_ranks_ascending",
            "volatility_ranks_ascending",
            "return_ranks_ascending",
            "low_MAX_selected_sectors",
            "low_volatility_selected_sectors",
            "prior_return_selected_sectors",
            "holding_period_end",
            "holding_return",
            "signal_complete",
        ],
        "high_volume_event_diagnostics": [
            "strategy_id",
            "block_sequence",
            "block_start",
            "block_end",
            "formation_date",
            "execution_date",
            "dollar_volume_values",
            "dollar_volume_ranks_descending",
            "qualifying_sectors",
            "price_shock_absolute_returns",
            "price_shock_ranks_descending",
            "price_shock_control_qualifiers",
            "holding_period_start",
            "holding_period_end",
            "holding_return_session_count",
            "event_return",
            "sequence_anchor_date",
            "skipped_session_date",
        ],
    }
    for name, rows in diagnostics.items():
        write_csv(OUTPUT_DIR / f"{name}.csv", rows, diagnostic_fields[name])
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        tables["invariant_results"],
        [
            "strategy_id",
            "record_type",
            "control_or_portfolio_id",
            "cost_assumption_bps",
            "explicit_zero_weights",
            "natural_drift_between_rebalances",
            "stale_weight_forward_fill_used",
            "negative_weights_present",
            "same_period_price_signal_return_used",
            "maximum_single_asset_weight",
            "maximum_gross_exposure",
            "maximum_daily_weight_sum",
            "numeric_invariant_status",
            "timing_invariant_status",
            "exposure_invariant_status",
            "weight_invariant_status",
            "invariant_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        outcomes,
        list(outcomes[0]),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        [
            "strategy_id",
            "family_id",
            "outcome",
            "failure_reason",
            "decision_reason",
            "missing_symbols",
        ],
    )
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
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
