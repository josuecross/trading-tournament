from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import accepted_47_targeted_internal_technical_batch_v1 as base


TASK_ID = "accepted_47_targeted_internal_technical_batch_v2"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
PREREGISTRATION_TIMESTAMP = "2026-08-07T00:00:00+00:00"
SOURCE_LINEAGE = "internally_generated_technical_hypothesis"
MODE = "bounded_internal_hypothesis_optimization"
STAGE = "optimization"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-10
TIMING_CONVENTION = base.TIMING_CONVENTION

MULTI_ASSET_UNIVERSE = base.MULTI_ASSET_UNIVERSE
SECTOR_UNIVERSE = base.SECTOR_UNIVERSE
PROTECTED_CAPTURE_HANDOFF_FINGERPRINT = "sha256:9aaf8b08d53cc03a4cab9830f190347bca58364024e099f61773c5526fa2a19f"

FOLLOWUP_NEXT_ACTION = "direction_owner_review_targeted_internal_batch_v2_followups_for_robustness"
NO_FOLLOWUP_NEXT_ACTION = "direction_owner_review_discovery_model_after_targeted_internal_batch_v2"
BLOCK_NEXT_ACTION = "direction_owner_review_targeted_internal_batch_v2_block"

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1",
    ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v1" / "latest",
    ROOT / "evidence" / "robustness" / "role_aware_robustness_internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "evidence" / "paper_demo_eligibility" / "internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "evidence" / "handoff" / "internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml",
)

COMPLETED_RECORD_SCAN_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "evidence" / "technical_factory",
    ROOT / "evidence" / "research_recovery",
    ROOT / "evidence" / "robustness",
    ROOT / "evidence" / "benchmark_controls",
)

PERMITTED_FAILURE_REASONS = {
    "duplicate_or_redundant",
    "no_selection_eligible_configuration",
    "not_selected_by_frozen_rule",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "concentration_risk",
    "weak_return",
    "excess_drawdown",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}

FORBIDDEN_ACTION_FLAGS = {
    "provider_access": False,
    "network_access": False,
    "market_data_refresh": False,
    "accepted_47_membership_change": False,
    "forward_observation_data_used": False,
    "alpaca_or_broker_state_used": False,
    "robustness_run": False,
    "validation_run": False,
    "paper_demo_eligibility_record": False,
    "handoff_or_export_record": False,
    "observation_record": False,
    "real_money_action": False,
}


@dataclass(frozen=True)
class ArchitectureSpec:
    architecture_code: str
    architecture_id: str
    family_id: str
    display_name: str
    universe: tuple[str, ...]
    accounting_universe: tuple[str, ...]
    named_control_id: str
    equal_weight_control_id: str
    static_control_id: str
    primary_future_robustness_role: str
    incremental_hypothesis: str
    duplicate_check_summary: str
    distinct_characteristic: str


@dataclass(frozen=True)
class ConfigSpec:
    architecture_code: str
    configuration_code: str
    lookback_sessions: int
    selected_count: int
    strategy_id: str
    trial_id: str

    @property
    def parameters(self) -> dict[str, int]:
        return {"lookback_sessions": self.lookback_sessions, "selected_count": self.selected_count}


@dataclass(frozen=True)
class SplitDefinition:
    architecture_id: str
    prices: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame
    closes: pd.DataFrame
    signal_execution_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    selection_index: pd.DatetimeIndex
    evaluation_index: pd.DatetimeIndex
    full_index: pd.DatetimeIndex
    boundary_execution: pd.Timestamp


ARCHITECTURES = (
    ArchitectureSpec(
        architecture_code="A",
        architecture_id="positive_negative_return_path_quality",
        family_id="cross_asset_gain_to_pain_rotation",
        display_name="Gain-to-Pain Cross-Asset Rotation",
        universe=MULTI_ASSET_UNIVERSE,
        accounting_universe=(*MULTI_ASSET_UNIVERSE, "BIL"),
        named_control_id="close_to_close_momentum_same_universe_control",
        equal_weight_control_id="equal_weight_12_asset_universe_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis="Own-return positive-sum divided by negative-pain may add value beyond ordinary momentum.",
        duplicate_check_summary="Distinct from capture asymmetry, Kaufman work, ordinary momentum, risk-adjusted momentum, and Real Momentum.",
        distinct_characteristic="own_return_positive_sum_over_absolute_negative_return_pain",
    ),
    ArchitectureSpec(
        architecture_code="B",
        architecture_id="rolling_intraday_close_location_characteristic",
        family_id="sector_close_location_pressure_rotation",
        display_name="Close-Location Pressure Sector Rotation",
        universe=SECTOR_UNIVERSE,
        accounting_universe=(*SECTOR_UNIVERSE, "BIL", "SPY"),
        named_control_id="close_to_close_momentum_same_sector_universe_control",
        equal_weight_control_id="equal_weight_ten_sector_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis="Persistent close location inside the daily high-low range may add value beyond sector momentum.",
        duplicate_check_summary="Distinct from overnight/intraday decomposition, bearish range expansion, Percent-B, and price-volume pressure systems.",
        distinct_characteristic="mean_close_location_value_over_trailing_ohlc_window",
    ),
    ArchitectureSpec(
        architecture_code="C",
        architecture_id="standardized_downside_tail_event_selection",
        family_id="cross_asset_downside_tail_frequency_rotation",
        display_name="Downside-Tail-Frequency Rotation",
        universe=MULTI_ASSET_UNIVERSE,
        accounting_universe=(*MULTI_ASSET_UNIVERSE, "BIL"),
        named_control_id="realized_volatility_level_same_universe_control",
        equal_weight_control_id="equal_weight_12_asset_universe_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis="Standardized downside-tail event frequency may add value beyond realized volatility level.",
        duplicate_check_summary="Distinct from inverse volatility, low-volatility selection, Low MAX, VIX Fix, and volatility stability work.",
        distinct_characteristic="frequency_of_returns_below_mean_minus_1_5_standard_deviations",
    ),
)

CONFIGS = (
    ConfigSpec("A", "A1", 63, 3, "internal_gain_to_pain_63d_top3_v1", "accepted47_internal_v2__gainpain63__top3"),
    ConfigSpec("A", "A2", 63, 5, "internal_gain_to_pain_63d_top5_v1", "accepted47_internal_v2__gainpain63__top5"),
    ConfigSpec("A", "A3", 126, 3, "internal_gain_to_pain_126d_top3_v1", "accepted47_internal_v2__gainpain126__top3"),
    ConfigSpec("A", "A4", 126, 5, "internal_gain_to_pain_126d_top5_v1", "accepted47_internal_v2__gainpain126__top5"),
    ConfigSpec("B", "B1", 21, 3, "internal_sector_clv_pressure_21d_top3_v1", "accepted47_internal_v2__clv21__top3"),
    ConfigSpec("B", "B2", 21, 5, "internal_sector_clv_pressure_21d_top5_v1", "accepted47_internal_v2__clv21__top5"),
    ConfigSpec("B", "B3", 63, 3, "internal_sector_clv_pressure_63d_top3_v1", "accepted47_internal_v2__clv63__top3"),
    ConfigSpec("B", "B4", 63, 5, "internal_sector_clv_pressure_63d_top5_v1", "accepted47_internal_v2__clv63__top5"),
    ConfigSpec("C", "C1", 63, 3, "internal_tail_frequency_63d_top3_v1", "accepted47_internal_v2__tailfreq63__top3"),
    ConfigSpec("C", "C2", 63, 5, "internal_tail_frequency_63d_top5_v1", "accepted47_internal_v2__tailfreq63__top5"),
    ConfigSpec("C", "C3", 126, 3, "internal_tail_frequency_126d_top3_v1", "accepted47_internal_v2__tailfreq126__top3"),
    ConfigSpec("C", "C4", 126, 5, "internal_tail_frequency_126d_top5_v1", "accepted47_internal_v2__tailfreq126__top5"),
)

REQUIRED_OUTPUT_FILES = {
    "batch_manifest.yaml",
    "architecture_preregistration.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "duplicate_preflight.csv",
    "benchmark_reference_log.csv",
    "selection_segment_definition.csv",
    "selection_segment_results.csv",
    "architecture_winner_selection.csv",
    "evaluation_segment_results.csv",
    "evaluation_subhalf_results.csv",
    "post_selection_full_period_diagnostics.csv",
    "calendar_year_results.csv",
    "rebalance_contribution_results.csv",
    "lightweight_concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_vectors.csv",
    "failure_reasons.csv",
    "entity_count_reconciliation.json",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "batch_report.md",
}


def rel(path: str | Path) -> str:
    return base.rel(path)


def file_hash(path: Path) -> str:
    return base.file_hash(path)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    base.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    base.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    base.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    base.write_text(path, text)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to clean unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def architecture_by_code(code: str) -> ArchitectureSpec:
    return next(item for item in ARCHITECTURES if item.architecture_code == code)


def configs_for_architecture(code: str) -> tuple[ConfigSpec, ...]:
    return tuple(item for item in CONFIGS if item.architecture_code == code)


def unique_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    return base.unique_symbols(symbols)


def target(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return base.target(columns, weights)


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return base.bil_target(columns)


def ranked_target(columns: tuple[str, ...], ranked: list[str], selected_count: int) -> dict[str, float]:
    return base.ranked_target(columns, ranked, selected_count)


def event_frame(index: pd.DatetimeIndex, columns: tuple[str, ...], events: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    return base.event_frame(index, columns, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return base.target_history(events, index)


def monthly_rebalanced_static_events(
    index: pd.DatetimeIndex,
    execution_dates: tuple[pd.Timestamp, ...],
    columns: tuple[str, ...],
    weights: dict[str, float],
) -> pd.DataFrame:
    return base.monthly_rebalanced_static_events(index, execution_dates, columns, weights)


def buy_hold_events(index: pd.DatetimeIndex, columns: tuple[str, ...], symbol: str) -> pd.DataFrame:
    return base.buy_hold_events(index, columns, symbol)


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return base.month_ends(index)


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    return base.next_session(index, signal_date)


def sorted_desc(scores: dict[str, float]) -> list[str]:
    return base.sorted_desc(scores)


def sorted_asc(scores: dict[str, float]) -> list[str]:
    return base.sorted_asc(scores)


def finite_metric(value: Any) -> float:
    return base.finite_metric(value)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return base.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return base.material_advantage(candidate, control)


def compound_return(returns: pd.Series) -> float:
    return base.compound_return(returns)


def load_adjusted_ohlcv(symbol: str) -> pd.DataFrame:
    return base.load_adjusted_ohlcv(symbol)


def load_frames() -> dict[str, pd.DataFrame]:
    symbols = unique_symbols(tuple(symbol for arch in ARCHITECTURES for symbol in arch.accounting_universe))
    return {symbol: load_adjusted_ohlcv(symbol) for symbol in symbols}


def common_feature_frames(
    frames: dict[str, pd.DataFrame],
    symbols: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = pd.concat([frames[symbol]["adj_close"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    highs = pd.concat([frames[symbol]["high"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    lows = pd.concat([frames[symbol]["low"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    closes = pd.concat([frames[symbol]["close"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    common = prices.index.intersection(highs.index).intersection(lows.index).intersection(closes.index).sort_values()
    return (
        prices.reindex(common).dropna(),
        highs.reindex(common).dropna(),
        lows.reindex(common).dropna(),
        closes.reindex(common).dropna(),
    )


def cache_preflight_rows(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in sorted(frames):
        path = CACHE_DIR / f"{symbol}.csv"
        frame = frames[symbol]
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "cache_hash": file_hash(path),
                "row_count": len(frame),
                "first_date": frame.index.min().date().isoformat(),
                "last_date": frame.index.max().date().isoformat(),
                "preflight_status": "pass",
            }
        )
    return rows


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def scan_path_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return file_hash(path)
    excluded = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        if excluded in child.resolve().parents:
            continue
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(child.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def completed_record_scan_hash() -> str:
    digest = hashlib.sha256()
    for path in COMPLETED_RECORD_SCAN_PATHS:
        digest.update(rel(path).encode("utf-8"))
        digest.update(scan_path_hash(path).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def duplicate_preflight_rows() -> list[dict[str, Any]]:
    scanned_hash = completed_record_scan_hash()
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "architecture_code": arch.architecture_code,
                "preflight_status": "pass",
                "execute_architecture_trials": True,
                "executed_trial_count": len(configs_for_architecture(arch.architecture_code)),
                "matched_existing_project": "",
                "matched_existing_architecture_id": "",
                "matched_existing_path": "",
                "completed_record_scan_hash": scanned_hash,
                "protected_capture_asymmetry_variant_created": False,
                "formula_checked": True,
                "required_data_checked": True,
                "universe_checked": True,
                "formation_schedule_checked": True,
                "ranking_characteristic_checked": True,
                "target_construction_checked": True,
                "parameter_grid_checked": True,
                "formula_match": False,
                "universe_match": False,
                "formation_schedule_match": False,
                "ranking_characteristic_match": False,
                "target_construction_match": False,
                "parameter_grid_similarity_sufficient": False,
                "broad_family_similarity_only": False,
                "distinctive_characteristic": arch.distinct_characteristic,
                "decision_reason": arch.duplicate_check_summary,
                "preperformance_complete": True,
            }
        )
    return rows


def data_ready_for_architecture(frames: dict[str, pd.DataFrame], arch: ArchitectureSpec) -> tuple[bool, str]:
    missing = [symbol for symbol in arch.accounting_universe if symbol not in frames or frames[symbol].empty]
    if missing:
        return False, f"missing required cache symbols: {','.join(missing)}"
    prices, highs, lows, closes = common_feature_frames(frames, arch.accounting_universe)
    if prices.empty or highs.empty or lows.empty or closes.empty:
        return False, "empty common no-forward-fill accepted-47 OHLCV period"
    if not (prices.index.equals(highs.index) and prices.index.equals(lows.index) and prices.index.equals(closes.index)):
        return False, "feature/accounting index mismatch"
    return True, ""


def architecture_min_position(arch: ArchitectureSpec) -> int:
    return max(config.lookback_sessions for config in configs_for_architecture(arch.architecture_code))


def architecture_split(frames: dict[str, pd.DataFrame], arch: ArchitectureSpec) -> SplitDefinition:
    prices, highs, lows, closes = common_feature_frames(frames, arch.accounting_universe)
    min_position = architecture_min_position(arch)
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = next_session(prices.index, signal_date)
        if position >= min_position and execution is not None:
            pairs.append((pd.Timestamp(signal_date), pd.Timestamp(execution)))
    if len(pairs) < 3:
        raise RuntimeError(f"{arch.architecture_id} has insufficient valid rebalance observations")
    boundary_position = int(math.floor(0.6 * len(pairs)))
    if boundary_position <= 0 or boundary_position >= len(pairs):
        raise RuntimeError(f"{arch.architecture_id} has nonviable 60/40 split")
    first_execution = pairs[0][1]
    boundary_execution = pairs[boundary_position][1]
    selection_index = prices.index[(prices.index >= first_execution) & (prices.index < boundary_execution)]
    evaluation_index = prices.index[prices.index >= boundary_execution]
    full_index = prices.index[prices.index >= first_execution]
    return SplitDefinition(
        architecture_id=arch.architecture_id,
        prices=prices,
        highs=highs,
        lows=lows,
        closes=closes,
        signal_execution_pairs=tuple(pairs),
        selection_index=selection_index,
        evaluation_index=evaluation_index,
        full_index=full_index,
        boundary_execution=boundary_execution,
    )


def gain_to_pain_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    position = int(returns.index.get_loc(signal_date))
    window = returns[list(universe)].iloc[position - lookback + 1:position + 1]
    scores: dict[str, float] = {}
    positive_sums: dict[str, float] = {}
    negative_pains: dict[str, float] = {}
    eligible_counts = {"eligible_count": 0, "lookback_sessions": lookback}
    for symbol in universe:
        series = window[symbol].dropna()
        positive_count = int((series > 0.0).sum())
        negative_count = int((series < 0.0).sum())
        positive_sum = float(np.maximum(series.to_numpy(dtype=float), 0.0).sum())
        negative_pain = abs(float(np.minimum(series.to_numpy(dtype=float), 0.0).sum()))
        if len(series) >= lookback and positive_count >= 5 and negative_count >= 5 and negative_pain > 0.0:
            score = positive_sum / negative_pain
            if math.isfinite(score):
                scores[symbol] = score
                positive_sums[symbol] = positive_sum
                negative_pains[symbol] = negative_pain
    eligible_counts["eligible_count"] = len(scores)
    return scores, positive_sums, negative_pains, eligible_counts


def gain_to_pain_scores(
    prices: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    returns = prices[list(universe)].pct_change(fill_method=None)
    return gain_to_pain_scores_from_returns(returns, universe, signal_date, lookback)


def momentum_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> dict[str, float]:
    position = int(returns.index.get_loc(signal_date))
    window = returns[list(universe)].iloc[position - lookback + 1:position + 1]
    scores: dict[str, float] = {}
    for symbol in universe:
        series = window[symbol].dropna()
        if len(series) >= lookback:
            value = compound_return(series)
            if math.isfinite(value):
                scores[symbol] = value
    return scores


def clv_frame(highs: pd.DataFrame, lows: pd.DataFrame, closes: pd.DataFrame, universe: tuple[str, ...]) -> pd.DataFrame:
    high = highs[list(universe)].astype(float)
    low = lows[list(universe)].astype(float)
    close = closes[list(universe)].astype(float)
    valid = high.notna() & low.notna() & close.notna() & (high >= low)
    denominator = high - low
    clv = (2.0 * close - high - low) / denominator.replace(0.0, np.nan)
    clv = clv.where(denominator > 0.0, 0.0)
    return clv.where(valid)


def clv_pressure_scores(
    highs: pd.DataFrame,
    lows: pd.DataFrame,
    closes: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, int]]:
    clv = clv_frame(highs, lows, closes, universe)
    position = int(clv.index.get_loc(signal_date))
    window = clv[list(universe)].iloc[position - lookback + 1:position + 1]
    required = int(math.ceil(0.9 * lookback))
    scores: dict[str, float] = {}
    valid_counts: dict[str, int] = {}
    for symbol in universe:
        series = window[symbol].dropna()
        valid_counts[symbol] = len(series)
        if len(series) >= required:
            value = float(series.mean())
            if math.isfinite(value):
                scores[symbol] = value
    return scores, valid_counts


def tail_frequency_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    position = int(returns.index.get_loc(signal_date))
    window = returns[list(universe)].iloc[position - lookback + 1:position + 1]
    scores: dict[str, float] = {}
    tail_frequency: dict[str, float] = {}
    realized_vol: dict[str, float] = {}
    tail_counts: dict[str, int] = {}
    for symbol in universe:
        series = window[symbol].dropna()
        if len(series) < lookback:
            continue
        mean_value = float(series.mean())
        std_value = float(series.std(ddof=1))
        if not (math.isfinite(mean_value) and math.isfinite(std_value) and std_value > 0.0):
            continue
        threshold = mean_value - 1.5 * std_value
        count = int((series < threshold).sum())
        frequency = count / float(len(series))
        scores[symbol] = -frequency
        tail_frequency[symbol] = frequency
        realized_vol[symbol] = std_value
        tail_counts[symbol] = count
    return scores, tail_frequency, realized_vol, tail_counts


def tail_frequency_scores(
    prices: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    returns = prices[list(universe)].pct_change(fill_method=None)
    return tail_frequency_scores_from_returns(returns, universe, signal_date, lookback)


def realized_volatility_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> dict[str, float]:
    position = int(returns.index.get_loc(signal_date))
    window = returns[list(universe)].iloc[position - lookback + 1:position + 1]
    scores: dict[str, float] = {}
    for symbol in universe:
        series = window[symbol].dropna()
        if len(series) >= lookback:
            value = float(series.std(ddof=1))
            if math.isfinite(value) and value > 0.0:
                scores[symbol] = value
    return scores


def build_events_for_config(arch: ArchitectureSpec, config: ConfigSpec, split: SplitDefinition) -> dict[str, Any]:
    columns = tuple(split.prices.columns)
    initial = bil_target(columns)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(split.prices.index[0]): initial}
    named_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(split.prices.index[0]): initial}
    signal_rows: list[dict[str, Any]] = []
    returns = split.prices[list(arch.universe)].pct_change(fill_method=None)
    for signal_date, execution_date in split.signal_execution_pairs:
        if arch.architecture_code == "A":
            scores, pos_sum, neg_pain, counts = gain_to_pain_scores_from_returns(
                returns, arch.universe, signal_date, config.lookback_sessions
            )
            control_scores = momentum_scores_from_returns(returns, arch.universe, signal_date, config.lookback_sessions)
            candidate_ranked = sorted_desc(scores)
            named_ranked = sorted_desc(control_scores)
            sample_key = "gain_to_pain_sample"
            sample_payload = {symbol: scores[symbol] for symbol in candidate_ranked[:3]}
            extra = {
                "positive_sum_sample": {symbol: pos_sum[symbol] for symbol in candidate_ranked[:3]},
                "negative_pain_sample": {symbol: neg_pain[symbol] for symbol in candidate_ranked[:3]},
                **counts,
            }
        elif arch.architecture_code == "B":
            scores, valid_counts = clv_pressure_scores(
                split.highs, split.lows, split.closes, arch.universe, signal_date, config.lookback_sessions
            )
            control_scores = momentum_scores_from_returns(returns, arch.universe, signal_date, config.lookback_sessions)
            candidate_ranked = sorted_desc(scores)
            named_ranked = sorted_desc(control_scores)
            sample_key = "clv_pressure_sample"
            sample_payload = {symbol: scores[symbol] for symbol in candidate_ranked[:3]}
            extra = {
                "valid_ohlc_count_sample": {symbol: valid_counts.get(symbol, 0) for symbol in arch.universe[:3]},
                "required_valid_ohlc_count": int(math.ceil(0.9 * config.lookback_sessions)),
            }
        elif arch.architecture_code == "C":
            scores, frequency, realized_vol, tail_counts = tail_frequency_scores_from_returns(
                returns, arch.universe, signal_date, config.lookback_sessions
            )
            control_scores = realized_volatility_scores_from_returns(
                returns, arch.universe, signal_date, config.lookback_sessions
            )
            candidate_ranked = sorted_desc(scores)
            named_ranked = sorted_asc(control_scores)
            sample_key = "tail_stability_score_sample"
            sample_payload = {symbol: scores[symbol] for symbol in candidate_ranked[:3]}
            extra = {
                "tail_frequency_sample": {symbol: frequency[symbol] for symbol in candidate_ranked[:3]},
                "realized_volatility_control_sample": {symbol: realized_vol[symbol] for symbol in named_ranked[:3]},
                "tail_count_sample": {symbol: tail_counts[symbol] for symbol in candidate_ranked[:3]},
            }
        else:
            raise RuntimeError(f"Unknown architecture code {arch.architecture_code}")
        candidate_events[execution_date] = ranked_target(columns, candidate_ranked, config.selected_count)
        named_events[execution_date] = ranked_target(columns, named_ranked, config.selected_count)
        signal_rows.append(
            {
                "signal_date": signal_date,
                "execution_date": execution_date,
                "candidate_top": candidate_ranked[: config.selected_count],
                "named_top": named_ranked[: config.selected_count],
                "eligible_count": len(candidate_ranked),
                "named_eligible_count": len(named_ranked),
                sample_key: sample_payload,
                **extra,
            }
        )
    candidate_frame = event_frame(split.prices.index, columns, candidate_events)
    named_frame = event_frame(split.prices.index, columns, named_events)
    candidate_targets = target_history(candidate_frame, split.prices.index)
    selection_targets = candidate_targets.reindex(split.selection_index).dropna()
    static_weights = {symbol: float(selection_targets[symbol].mean()) for symbol in columns}
    static_total = float(sum(static_weights.values()))
    static_weights = {symbol: value / static_total for symbol, value in static_weights.items()}
    equal_weights = {symbol: (1.0 / len(arch.universe) if symbol in arch.universe else 0.0) for symbol in columns}
    execution_dates = tuple(execution for _, execution in split.signal_execution_pairs)
    control_events = {
        arch.named_control_id: named_frame,
        arch.equal_weight_control_id: monthly_rebalanced_static_events(split.prices.index, execution_dates, columns, equal_weights),
        arch.static_control_id: monthly_rebalanced_static_events(split.prices.index, execution_dates, columns, static_weights),
        "SPY_buy_and_hold": buy_hold_events(split.prices.index, columns, "SPY"),
        "BIL_buy_and_hold": buy_hold_events(split.prices.index, columns, "BIL"),
    }
    return {
        "candidate_events": candidate_frame,
        "control_events": control_events,
        "candidate_targets": candidate_targets,
        "average_target_weights_selection_segment": static_weights,
        "signal_rows": signal_rows,
    }


def simulate_prepared(split: SplitDefinition, prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidate_paths[cost] = base.accounting.simulate_path(split.prices, prepared["candidate_events"], cost, TIMING_CONVENTION)
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = base.accounting.simulate_path(split.prices, events, cost, TIMING_CONVENTION)
    return {"candidate_paths": candidate_paths, "control_paths": control_paths}


def metrics_for_path(path: dict[str, Any], period_index: pd.DatetimeIndex, scheduled_executions: tuple[pd.Timestamp, ...]) -> dict[str, Any]:
    return base.metrics_for_path(path, period_index, scheduled_executions)


def selection_gate_vector(
    candidate_5: dict[str, Any],
    named_5: dict[str, Any],
    static_5: dict[str, Any],
    equal_5: dict[str, Any],
    candidate_10: dict[str, Any],
) -> dict[str, Any]:
    vector = base.selection_gate_vector(candidate_5, named_5, static_5, equal_5, candidate_10)
    if not vector["selection_eligible"] and not vector["primary_failure_reason"]:
        vector["primary_failure_reason"] = "methodology_failure"
    return vector


def selection_results_for_config(
    arch: ArchitectureSpec,
    config: ConfigSpec,
    split: SplitDefinition,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> dict[str, Any]:
    scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        metrics[("candidate", cost)] = metrics_for_path(simulation["candidate_paths"][cost], split.selection_index, scheduled)
        for control_id in prepared["control_events"]:
            metrics[(control_id, cost)] = metrics_for_path(
                simulation["control_paths"][(control_id, cost)], split.selection_index, scheduled
            )
    vector = selection_gate_vector(
        metrics[("candidate", PRIMARY_COST)],
        metrics[(arch.named_control_id, PRIMARY_COST)],
        metrics[(arch.static_control_id, PRIMARY_COST)],
        metrics[(arch.equal_weight_control_id, PRIMARY_COST)],
        metrics[("candidate", 10.0)],
    )
    return {
        "arch": arch,
        "config": config,
        "split": split,
        "prepared": prepared,
        "simulation": simulation,
        "selection_metrics": metrics,
        "selection_vector": vector,
        "selected_winner": False,
        "evaluation": {},
        "outcome": "selection_eligible" if vector["selection_eligible"] else "closed_optimization",
        "failure_reason": "" if vector["selection_eligible"] else vector["primary_failure_reason"],
        "decision_reason": (
            "passed all preregistered selection-segment gates"
            if vector["selection_eligible"]
            else "failed preregistered selection-segment gate"
        ),
    }


def duplicate_result(arch: ArchitectureSpec, config: ConfigSpec) -> dict[str, Any]:
    return {
        "arch": arch,
        "config": config,
        "split": None,
        "prepared": {},
        "simulation": {},
        "selection_metrics": {},
        "selection_vector": {"selection_eligible": False, "primary_failure_reason": "duplicate_or_redundant"},
        "selected_winner": False,
        "evaluation": {},
        "outcome": "closed_optimization",
        "failure_reason": "duplicate_or_redundant",
        "decision_reason": "architecture duplicate preflight rejected before performance calculation",
    }


def blocked_result(arch: ArchitectureSpec, config: ConfigSpec, reason: str) -> dict[str, Any]:
    return {
        "arch": arch,
        "config": config,
        "split": None,
        "prepared": {},
        "simulation": {},
        "selection_metrics": {},
        "selection_vector": {"selection_eligible": False, "primary_failure_reason": "data_or_comparability_failure"},
        "selected_winner": False,
        "evaluation": {},
        "outcome": "closed_optimization",
        "failure_reason": "data_or_comparability_failure",
        "decision_reason": reason,
    }


def build_executed_results(
    frames: dict[str, pd.DataFrame],
    duplicate_rows: list[dict[str, Any]],
) -> tuple[dict[str, SplitDefinition], dict[str, dict[str, Any]]]:
    duplicate_by_code = {row["architecture_code"]: row["preflight_status"] == "duplicate_or_redundant" for row in duplicate_rows}
    splits: dict[str, SplitDefinition] = {}
    results: dict[str, dict[str, Any]] = {}
    for arch in ARCHITECTURES:
        if duplicate_by_code[arch.architecture_code]:
            for config in configs_for_architecture(arch.architecture_code):
                results[config.trial_id] = duplicate_result(arch, config)
            continue
        ready, reason = data_ready_for_architecture(frames, arch)
        if not ready:
            for config in configs_for_architecture(arch.architecture_code):
                results[config.trial_id] = blocked_result(arch, config, reason)
            continue
        split = architecture_split(frames, arch)
        splits[arch.architecture_id] = split
        for config in configs_for_architecture(arch.architecture_code):
            prepared = build_events_for_config(arch, config, split)
            simulation = simulate_prepared(split, prepared)
            results[config.trial_id] = selection_results_for_config(arch, config, split, prepared, simulation)
    freeze_architecture_winners(results)
    evaluate_frozen_winners(results)
    return splits, results


def freeze_architecture_winners(results: dict[str, dict[str, Any]]) -> None:
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        if any(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results):
            continue
        if not all(result["split"] is not None for result in arch_results):
            continue
        eligible = [result for result in arch_results if result["selection_vector"]["selection_eligible"]]
        if not eligible:
            for result in arch_results:
                result["failure_reason"] = "no_selection_eligible_configuration"
                result["decision_reason"] = "no configuration passed the preregistered selection eligibility gate"
            continue
        max_sharpe = max(finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"]) for result in eligible)
        tied = [
            result
            for result in eligible
            if finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"]) >= max_sharpe - 0.01 - 1e-12
        ]
        winner = sorted(
            tied,
            key=lambda result: (
                abs(finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["maximum_drawdown"])),
                finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["annualized_turnover"]),
                result["config"].trial_id,
            ),
        )[0]
        winner["selected_winner"] = True
        winner["outcome"] = "selection_winner_pending_evaluation"
        winner["failure_reason"] = ""
        winner["decision_reason"] = "frozen by preregistered selection rule before evaluation metrics"
        for result in arch_results:
            if result is winner:
                continue
            result["outcome"] = "closed_optimization"
            result["failure_reason"] = "not_selected_by_frozen_rule"
            result["decision_reason"] = "not selected by frozen one-winner-per-architecture rule"


def complete_calendar_years(full_index: pd.DatetimeIndex, period_index: pd.DatetimeIndex) -> list[int]:
    return base.complete_calendar_years(full_index, period_index)


def calendar_year_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arch: ArchitectureSpec = result["arch"]
    config: ConfigSpec = result["config"]
    split: SplitDefinition = result["split"]
    candidate = result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"]
    named = result["simulation"]["control_paths"][(arch.named_control_id, PRIMARY_COST)]["returns"]
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    for year in complete_calendar_years(split.prices.index, split.evaluation_index):
        year_index = split.evaluation_index[split.evaluation_index.year == year]
        candidate_return = compound_return(candidate.reindex(year_index))
        named_return = compound_return(named.reindex(year_index))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "period_year": year,
                "period_complete_calendar_year": True,
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "descriptive_only": False,
            }
        )
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if len(rows) >= 2 and max_share > 0.8 + 1e-12 else "pass"
    else:
        max_share = 0.0
        state = "not_applicable_no_positive_excess"
    return rows, {
        "complete_year_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def rebalance_contribution_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arch: ArchitectureSpec = result["arch"]
    config: ConfigSpec = result["config"]
    split: SplitDefinition = result["split"]
    candidate = result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"]
    named = result["simulation"]["control_paths"][(arch.named_control_id, PRIMARY_COST)]["returns"]
    eval_set = set(split.evaluation_index)
    eval_executions = [execution for _, execution in split.signal_execution_pairs if execution in eval_set]
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    for position, start in enumerate(eval_executions):
        end = eval_executions[position + 1] if position + 1 < len(eval_executions) else split.evaluation_index.max()
        if position + 1 < len(eval_executions):
            interval = split.evaluation_index[(split.evaluation_index >= start) & (split.evaluation_index < end)]
        else:
            interval = split.evaluation_index[split.evaluation_index >= start]
        interval_end = interval.max() if len(interval) else start
        candidate_return = compound_return(candidate.reindex(interval))
        named_return = compound_return(named.reindex(interval))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "rebalance_month": start.to_period("M").strftime("%Y-%m"),
                "interval_start": start.date().isoformat(),
                "interval_end": pd.Timestamp(interval_end).date().isoformat(),
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "nonwinner_evaluation_access": False,
            }
        )
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if max_share > 0.8 + 1e-12 else "pass"
    else:
        max_share = 0.0
        state = "not_applicable_no_positive_excess"
    return rows, {
        "rebalance_month_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def evaluation_subhalf_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arch: ArchitectureSpec = result["arch"]
    config: ConfigSpec = result["config"]
    split: SplitDefinition = result["split"]
    scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
    eval_executions = [date for date in scheduled if date in set(split.evaluation_index)]
    if len(eval_executions) < 4 or len(split.evaluation_index) < 126:
        return [
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "subhalf_id": "evaluation_subhalves",
                "period_start": split.evaluation_index.min().date().isoformat(),
                "period_end": split.evaluation_index.max().date().isoformat(),
                "formation_count": len(eval_executions),
                "diagnostic_state": "insufficient_evaluation_subhalf_sample",
                "candidate_sharpe": "",
                "named_control_sharpe": "",
                "candidate_maximum_drawdown": "",
                "named_control_maximum_drawdown": "",
                "worse_than_named_on_both_sharpe_and_drawdown": "",
                "pass": True,
            }
        ], {"state": "insufficient_evaluation_subhalf_sample", "pass": True}
    midpoint = len(eval_executions) // 2
    ranges = [
        ("first_evaluation_half", eval_executions[0], eval_executions[midpoint]),
        ("second_evaluation_half", eval_executions[midpoint], split.evaluation_index.max()),
    ]
    rows: list[dict[str, Any]] = []
    failures = 0
    for label, start, end in ranges:
        if label == "first_evaluation_half":
            period_index = split.evaluation_index[(split.evaluation_index >= start) & (split.evaluation_index < end)]
        else:
            period_index = split.evaluation_index[split.evaluation_index >= start]
        candidate = metrics_for_path(result["simulation"]["candidate_paths"][PRIMARY_COST], period_index, scheduled)
        named = metrics_for_path(result["simulation"]["control_paths"][(arch.named_control_id, PRIMARY_COST)], period_index, scheduled)
        worse = (
            finite_metric(candidate["sharpe_ratio"]) < finite_metric(named["sharpe_ratio"]) - 1e-12
            and finite_metric(candidate["maximum_drawdown"]) < finite_metric(named["maximum_drawdown"]) - 1e-12
        )
        failures += int(worse)
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "subhalf_id": label,
                "period_start": period_index.min().date().isoformat() if len(period_index) else "",
                "period_end": period_index.max().date().isoformat() if len(period_index) else "",
                "formation_count": len([date for date in eval_executions if date in set(period_index)]),
                "diagnostic_state": "pass" if not worse else "period_instability",
                "candidate_sharpe": candidate["sharpe_ratio"],
                "named_control_sharpe": named["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "named_control_maximum_drawdown": named["maximum_drawdown"],
                "worse_than_named_on_both_sharpe_and_drawdown": worse,
                "pass": not worse,
            }
        )
    return rows, {"state": "pass" if failures == 0 else "period_instability", "pass": failures == 0}


def evaluation_gate_vector(
    result: dict[str, Any],
    calendar_state: dict[str, Any],
    rebalance_state: dict[str, Any],
    subhalf_state: dict[str, Any],
) -> dict[str, Any]:
    arch: ArchitectureSpec = result["arch"]
    evaluation = result["evaluation"]["metrics"]
    candidate_5 = evaluation[("candidate", PRIMARY_COST)]
    named_5 = evaluation[(arch.named_control_id, PRIMARY_COST)]
    static_5 = evaluation[(arch.static_control_id, PRIMARY_COST)]
    equal_5 = evaluation[(arch.equal_weight_control_id, PRIMARY_COST)]
    candidate_10 = evaluation[("candidate", 10.0)]
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
        "evaluation_subhalf_stability_pass": bool(subhalf_state["pass"]),
        "calendar_year_concentration_pass": bool(calendar_state["pass"]),
        "rebalance_month_concentration_pass": bool(rebalance_state["pass"]),
    }
    vector["exploratory_followup_candidate"] = all(bool(value) for value in vector.values())
    if not vector["cagr_positive_5bps"]:
        reason = "weak_return"
    elif not vector["invariants_pass_5bps"]:
        reason = "methodology_failure"
    elif not vector["named_control_not_dominating_5bps"]:
        reason = "weak_vs_primary_control"
    elif not vector["material_vs_named_control_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["static_equal_control_not_dominating_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["cagr_positive_10bps"]:
        reason = "cost_drag"
    elif not vector["evaluation_subhalf_stability_pass"]:
        reason = "period_instability"
    elif not vector["calendar_year_concentration_pass"]:
        reason = "concentration_risk"
    elif not vector["rebalance_month_concentration_pass"]:
        reason = "concentration_risk"
    else:
        reason = ""
    vector["primary_failure_reason"] = reason
    return vector


def evaluate_frozen_winners(results: dict[str, dict[str, Any]]) -> None:
    for result in results.values():
        if not result.get("selected_winner"):
            continue
        arch: ArchitectureSpec = result["arch"]
        split: SplitDefinition = result["split"]
        scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
        metrics: dict[tuple[str, float], dict[str, Any]] = {}
        full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            metrics[("candidate", cost)] = metrics_for_path(result["simulation"]["candidate_paths"][cost], split.evaluation_index, scheduled)
            full_metrics[("candidate", cost)] = metrics_for_path(result["simulation"]["candidate_paths"][cost], split.full_index, scheduled)
            for control_id in result["prepared"]["control_events"]:
                metrics[(control_id, cost)] = metrics_for_path(
                    result["simulation"]["control_paths"][(control_id, cost)], split.evaluation_index, scheduled
                )
                full_metrics[(control_id, cost)] = metrics_for_path(
                    result["simulation"]["control_paths"][(control_id, cost)], split.full_index, scheduled
                )
        result["evaluation"] = {"metrics": metrics, "full_metrics": full_metrics}
        subhalf_rows, subhalf_state = evaluation_subhalf_diagnostics(result)
        calendar_rows, calendar_state = calendar_year_diagnostics(result)
        rebalance_rows, rebalance_state = rebalance_contribution_diagnostics(result)
        result["evaluation"].update(
            {
                "subhalf_rows": subhalf_rows,
                "subhalf_state": subhalf_state,
                "calendar_rows": calendar_rows,
                "calendar_state": calendar_state,
                "rebalance_rows": rebalance_rows,
                "rebalance_state": rebalance_state,
            }
        )
        vector = evaluation_gate_vector(result, calendar_state, rebalance_state, subhalf_state)
        result["evaluation"]["vector"] = vector
        if vector["exploratory_followup_candidate"]:
            result["outcome"] = "exploratory_followup_candidate"
            result["failure_reason"] = ""
            result["decision_reason"] = "winner passed exploratory evaluation gates at 5 bps with 10-bps viability"
        else:
            result["outcome"] = "closed_exploration"
            result["failure_reason"] = vector["primary_failure_reason"]
            result["decision_reason"] = "frozen winner failed exploratory evaluation gate"


def metric_prefix(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return base.metric_prefix(prefix, values)


def control_metric_columns(arch: ArchitectureSpec, metrics: dict[tuple[str, float], dict[str, Any]], cost: float) -> dict[str, Any]:
    return base.control_metric_columns(arch, metrics, cost)


def result_metric_row(
    arch: ArchitectureSpec,
    config: ConfigSpec,
    period_id: str,
    metrics: dict[str, Any],
    cost: float,
    controls: dict[str, Any] | None = None,
    outcome: str = "",
    failure_reason: str = "",
) -> dict[str, Any]:
    return base.result_metric_row(arch, config, period_id, metrics, cost, controls, outcome, failure_reason)


def empty_selection_placeholder(arch: ArchitectureSpec, config: ConfigSpec, cost: float, result: dict[str, Any]) -> dict[str, Any]:
    return base.empty_selection_placeholder(arch, config, cost, result)


def selection_segment_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        if result["split"] is None:
            for cost in COSTS:
                rows.append(empty_selection_placeholder(arch, config, cost, result))
            continue
        for cost in COSTS:
            metrics = result["selection_metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "selection_segment",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["selection_metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {
                    "performance_executed": True,
                    "selection_eligible_5bps": result["selection_vector"]["selection_eligible"],
                    "selection_gate_failures": "|".join(
                        key
                        for key, value in result["selection_vector"].items()
                        if key not in {"selection_eligible", "primary_failure_reason"} and value is False
                    ),
                }
            )
    return rows


def evaluation_segment_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result.get("selected_winner") or not result.get("evaluation"):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        for cost in COSTS:
            metrics = result["evaluation"]["metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "exploratory_evaluation_segment",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["evaluation"]["metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {"frozen_winner": True, "selection_frozen_before_evaluation_metrics": True}
            )
    return rows


def evaluation_subhalf_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result.get("selected_winner") and result.get("evaluation"):
            rows.extend(result["evaluation"]["subhalf_rows"])
    return rows


def post_selection_full_period_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result.get("selected_winner") or not result.get("evaluation"):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        for cost in COSTS:
            metrics = result["evaluation"]["full_metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "post_selection_full_period_diagnostic",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["evaluation"]["full_metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {"diagnostic_only": True, "can_rescue_or_reverse_decision": False}
            )
    return rows


def selection_definition_rows(splits: dict[str, SplitDefinition], duplicate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duplicate_by_arch = {row["architecture_id"]: row for row in duplicate_rows}
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        duplicate = duplicate_by_arch[arch.architecture_id]["preflight_status"] == "duplicate_or_redundant"
        if duplicate:
            segment_status = "duplicate_or_redundant"
            split = None
        else:
            split = splits.get(arch.architecture_id)
            segment_status = "executed" if split is not None else "data_or_comparability_failure"
        if split is None:
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "architecture_code": arch.architecture_code,
                    "segment_status": segment_status,
                    "common_universe": arch.accounting_universe,
                    "common_start": "",
                    "common_end": "",
                    "first_valid_signal_date": "",
                    "first_execution_date": "",
                    "last_execution_date": "",
                    "valid_rebalance_count": 0,
                    "selection_rebalance_count": 0,
                    "evaluation_rebalance_count": 0,
                    "selection_start": "",
                    "selection_end": "",
                    "evaluation_start": "",
                    "evaluation_end": "",
                    "boundary_execution_date": "",
                    "split_rule": "duplicate_preflight_zero_trials" if duplicate else "no_executable_common_period",
                    "segment_role": "optimization_split_not_validation_or_robustness",
                }
            )
            continue
        executions = tuple(execution for _, execution in split.signal_execution_pairs)
        selection_executions = [date for date in executions if date in set(split.selection_index)]
        evaluation_executions = [date for date in executions if date in set(split.evaluation_index)]
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "architecture_code": arch.architecture_code,
                "segment_status": "executed",
                "common_universe": arch.accounting_universe,
                "common_start": split.prices.index.min().date().isoformat(),
                "common_end": split.prices.index.max().date().isoformat(),
                "first_valid_signal_date": split.signal_execution_pairs[0][0].date().isoformat(),
                "first_execution_date": executions[0].date().isoformat(),
                "last_execution_date": executions[-1].date().isoformat(),
                "valid_rebalance_count": len(executions),
                "selection_rebalance_count": len(selection_executions),
                "evaluation_rebalance_count": len(evaluation_executions),
                "selection_start": split.selection_index.min().date().isoformat(),
                "selection_end": split.selection_index.max().date().isoformat(),
                "evaluation_start": split.evaluation_index.min().date().isoformat(),
                "evaluation_end": split.evaluation_index.max().date().isoformat(),
                "boundary_execution_date": split.boundary_execution.date().isoformat(),
                "split_rule": "floor_60_percent_valid_rebalance_observations_selection_final_40_percent_evaluation",
                "segment_role": "optimization_split_not_validation_or_robustness",
            }
        )
    return rows


def architecture_winner_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        eligible = [result for result in arch_results if result["selection_vector"].get("selection_eligible")]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        duplicate = all(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results)
        blocked = all(result["split"] is None for result in arch_results) and not duplicate
        if winner is not None:
            metrics = winner["selection_metrics"][("candidate", PRIMARY_COST)]
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "selection_status": "winner_frozen",
                    "eligible_configuration_count": len(eligible),
                    "selected_strategy_id": winner["config"].strategy_id,
                    "selected_trial_id": winner["config"].trial_id,
                    "selected_configuration_code": winner["config"].configuration_code,
                    "selection_rule": "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id",
                    "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
                    "selection_frozen_before_evaluation_metrics": True,
                    "selection_sharpe_5bps": metrics["sharpe_ratio"],
                    "selection_maximum_drawdown_5bps": metrics["maximum_drawdown"],
                    "selection_annualized_turnover_5bps": metrics["annualized_turnover"],
                    "winner_outcome": winner["outcome"],
                    "failure_reason": winner["failure_reason"],
                    "decision_reason": winner["decision_reason"],
                }
            )
        else:
            reason = "duplicate_or_redundant" if duplicate else ("data_or_comparability_failure" if blocked else "no_selection_eligible_configuration")
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "selection_status": reason,
                    "eligible_configuration_count": len(eligible),
                    "selected_strategy_id": "",
                    "selected_trial_id": "",
                    "selected_configuration_code": "",
                    "selection_rule": "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id",
                    "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
                    "selection_frozen_before_evaluation_metrics": True,
                    "selection_sharpe_5bps": "",
                    "selection_maximum_drawdown_5bps": "",
                    "selection_annualized_turnover_5bps": "",
                    "winner_outcome": "closed_optimization",
                    "failure_reason": reason,
                    "decision_reason": "architecture was rejected by duplicate/data preflight" if duplicate or blocked else "no configuration passed selection eligibility",
                }
            )
    return rows


def parameter_grid_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position, config in enumerate(CONFIGS, start=1):
        arch = architecture_by_code(config.architecture_code)
        rows.append(
            {
                "grid_position": position,
                "architecture_code": arch.architecture_code,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "configuration_code": config.configuration_code,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "lookback_sessions": config.lookback_sessions,
                "selected_count": config.selected_count,
                "universe": arch.universe,
                "named_control": arch.named_control_id,
                "static_equal_weight_controls": [arch.static_control_id, arch.equal_weight_control_id],
                "source_or_research_lineage": SOURCE_LINEAGE,
                "grid_frozen_before_performance": True,
                "post_result_grid_expansion_allowed": False,
                "protected_capture_asymmetry_variant": False,
            }
        )
    return rows


def strategy_next_action(result: dict[str, Any]) -> str:
    if result["outcome"] == "exploratory_followup_candidate":
        return FOLLOWUP_NEXT_ACTION
    return "retain_exact_configuration_as_logged_closed_trial_no_parameter_changes"


def strategy_card_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        rows.append(
            {
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "entity_type": "strategy_configuration",
                "stage": STAGE,
                "source_or_research_lineage": SOURCE_LINEAGE,
                "primary_future_robustness_role": arch.primary_future_robustness_role,
                "universe": arch.universe,
                "parameters": config.parameters,
                "named_control": arch.named_control_id,
                "static_equal_weight_control": [arch.static_control_id, arch.equal_weight_control_id],
                "strategy_result": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": strategy_next_action(result),
                "counted_as_strategy": True,
                "counted_as_trial": True,
                "paper_demo_eligible": False,
            }
        )
    return rows


def trial_ledger_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        rows.append(
            {
                "trial_id": config.trial_id,
                "entity_type": "canonical_experiment_trial",
                "strategy_id": config.strategy_id,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "configuration_code": config.configuration_code,
                "stage": STAGE,
                "source_or_research_lineage": SOURCE_LINEAGE,
                "route": "standalone_long_only_allocation",
                "execution_timing": TIMING_CONVENTION,
                "lookback_sessions": config.lookback_sessions,
                "selected_count": config.selected_count,
                "canonical_configuration": True,
                "executed": result["split"] is not None,
                "selection_evaluated": result["split"] is not None,
                "evaluation_evaluated": bool(result.get("selected_winner") and result.get("evaluation")),
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": strategy_next_action(result),
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        arch = architecture_by_code(config.architecture_code)
        controls = [
            (arch.named_control_id, "named_control_tests_distinctive_feature"),
            (arch.equal_weight_control_id, "static_equal_weight_control"),
            (arch.static_control_id, "static_average_candidate_weights_control"),
            ("SPY_buy_and_hold", "market_buy_and_hold_reference"),
            ("BIL_buy_and_hold", "cash_buy_and_hold_reference"),
        ]
        for control_id, role in controls:
            rows.append(
                {
                    "benchmark_reference_id": f"{config.trial_id}__{control_id}",
                    "entity_type": "benchmark_reference",
                    "architecture_id": arch.architecture_id,
                    "strategy_id_context": config.strategy_id,
                    "trial_id_context": config.trial_id,
                    "control_id": control_id,
                    "control_role": role,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "counted_as_observation": False,
                    "promotable": False,
                }
            )
    return rows


def failure_vector_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        vector = result["selection_vector"].copy()
        evaluation_vector = result.get("evaluation", {}).get("vector", {})
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "stage": STAGE,
                "duplicate_or_redundant": result["failure_reason"] == "duplicate_or_redundant",
                "selection_eligible": vector.get("selection_eligible", False),
                "selected_winner": result.get("selected_winner", False),
                "evaluation_access_allowed": bool(result.get("selected_winner")),
                "exploratory_followup_candidate": evaluation_vector.get("exploratory_followup_candidate", False),
                "selection_cagr_positive_5bps": vector.get("cagr_positive_5bps", ""),
                "selection_invariants_pass_5bps": vector.get("invariants_pass_5bps", ""),
                "selection_named_control_not_dominating_5bps": vector.get("named_control_not_dominating_5bps", ""),
                "selection_material_vs_named_control_5bps": vector.get("material_vs_named_control_5bps", ""),
                "selection_static_equal_control_not_dominating_5bps": vector.get("static_equal_control_not_dominating_5bps", ""),
                "selection_cagr_positive_10bps": vector.get("cagr_positive_10bps", ""),
                "evaluation_cagr_positive_5bps": evaluation_vector.get("cagr_positive_5bps", ""),
                "evaluation_invariants_pass_5bps": evaluation_vector.get("invariants_pass_5bps", ""),
                "evaluation_named_control_not_dominating_5bps": evaluation_vector.get("named_control_not_dominating_5bps", ""),
                "evaluation_material_vs_named_control_5bps": evaluation_vector.get("material_vs_named_control_5bps", ""),
                "evaluation_static_equal_control_not_dominating_5bps": evaluation_vector.get("static_equal_control_not_dominating_5bps", ""),
                "evaluation_cagr_positive_10bps": evaluation_vector.get("cagr_positive_10bps", ""),
                "evaluation_subhalf_stability_pass": evaluation_vector.get("evaluation_subhalf_stability_pass", ""),
                "calendar_year_concentration_pass": evaluation_vector.get("calendar_year_concentration_pass", ""),
                "rebalance_month_concentration_pass": evaluation_vector.get("rebalance_month_concentration_pass", ""),
                "primary_failure_reason": result["failure_reason"],
                "outcome": result["outcome"],
            }
        )
    return rows


def failure_reason_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        if not result["failure_reason"]:
            continue
        rows.append(
            {
                "architecture_id": result["arch"].architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "outcome": result["outcome"],
                "primary_failure_reason": result["failure_reason"],
                "failure_detail": result["decision_reason"],
                "exact_configuration_only": True,
                "family_closed": False,
                "parameter_change_authorized": False,
            }
        )
    return rows


def calendar_year_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result.get("selected_winner") and result.get("evaluation"):
            rows.extend(result["evaluation"]["calendar_rows"])
    return rows


def rebalance_contribution_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result.get("selected_winner") and result.get("evaluation"):
            rows.extend(result["evaluation"]["rebalance_rows"])
    return rows


def concentration_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not (result.get("selected_winner") and result.get("evaluation")):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        calendar_state = result["evaluation"]["calendar_state"]
        rebalance_state = result["evaluation"]["rebalance_state"]
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "cost_bps_one_way": PRIMARY_COST,
                "calendar_complete_year_count": calendar_state["complete_year_count"],
                "calendar_positive_excess_total": calendar_state["positive_excess_total"],
                "calendar_max_positive_excess_share": calendar_state["max_positive_excess_share"],
                "calendar_concentration_state": calendar_state["state"],
                "rebalance_month_count": rebalance_state["rebalance_month_count"],
                "rebalance_positive_excess_total": rebalance_state["positive_excess_total"],
                "rebalance_max_positive_excess_share": rebalance_state["max_positive_excess_share"],
                "rebalance_concentration_state": rebalance_state["state"],
                "concentration_pass": bool(calendar_state["pass"] and rebalance_state["pass"]),
            }
        )
    return rows


def turnover_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result["split"] is None:
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        periods = [("selection_segment", result["selection_metrics"])]
        if result.get("selected_winner") and result.get("evaluation"):
            periods.extend(
                [
                    ("exploratory_evaluation_segment", result["evaluation"]["metrics"]),
                    ("post_selection_full_period_diagnostic", result["evaluation"]["full_metrics"]),
                ]
            )
        for period_id, metric_map in periods:
            for cost in COSTS:
                metrics = metric_map[("candidate", cost)]
                rows.append(
                    {
                        "architecture_id": arch.architecture_id,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "period_id": period_id,
                        "cost_bps_one_way": cost,
                        "turnover": metrics["turnover"],
                        "annualized_turnover": metrics["annualized_turnover"],
                        "transaction_cost_drag": metrics["transaction_cost_drag"],
                        "zero_cost_has_zero_drag": cost != 0.0 or abs(float(metrics["transaction_cost_drag"])) <= 1e-14,
                        "cost_applied_once_to_one_way_turnover": True,
                        "turnover_is_drift_adjusted": True,
                    }
                )
    return rows


def invariant_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result["split"] is None:
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        periods = [("selection_segment", result["selection_metrics"])]
        if result.get("selected_winner") and result.get("evaluation"):
            periods.extend(
                [
                    ("exploratory_evaluation_segment", result["evaluation"]["metrics"]),
                    ("post_selection_full_period_diagnostic", result["evaluation"]["full_metrics"]),
                ]
            )
        for period_id, metric_map in periods:
            for cost in COSTS:
                metrics = metric_map[("candidate", cost)]
                rows.append(
                    {
                        "architecture_id": arch.architecture_id,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "period_id": period_id,
                        "cost_bps_one_way": cost,
                        "numeric_invariant_status": metrics["numeric_invariant_status"],
                        "timing_invariant_status": metrics["timing_invariant_status"],
                        "exposure_weight_invariant_status": metrics["exposure_weight_invariant_status"],
                        "daily_weight_sum_one": metrics["daily_weight_sum_one"],
                        "maximum_gross_exposure": metrics["maximum_gross_exposure"],
                        "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
                        "target_zero_weights_preserved": metrics["target_zero_weights_preserved"],
                        "explicit_holdings": metrics["explicit_holdings"],
                        "long_only": True,
                        "no_leverage": True,
                        "natural_drift": True,
                        "deterministic_turnover": True,
                        "no_tradable_price_forward_fill": True,
                        "same_period_price_signal_return_used": metrics["same_period_price_signal_return_used"],
                        "invariant_pass": metrics["invariant_pass"],
                    }
                )
    return rows


def followup_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "architecture_id": result["arch"].architecture_id,
            "strategy_id": result["config"].strategy_id,
            "trial_id": result["config"].trial_id,
            "stage": STAGE,
            "outcome": result["outcome"],
            "primary_future_robustness_role": result["arch"].primary_future_robustness_role,
            "decision_reason": result["decision_reason"],
            "next_action": FOLLOWUP_NEXT_ACTION,
            "execute_in_this_task": False,
        }
        for result in results.values()
        if result["outcome"] == "exploratory_followup_candidate"
    ]


def batch_outcome(results: dict[str, dict[str, Any]]) -> tuple[str, str]:
    blocked_architectures = 0
    executed_architectures = 0
    followups = 0
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        if all(result["split"] is None for result in arch_results):
            blocked_architectures += 1
        else:
            executed_architectures += 1
        followups += sum(result["outcome"] == "exploratory_followup_candidate" for result in arch_results)
    if executed_architectures == 0:
        return "targeted_internal_batch_v2_blocked", BLOCK_NEXT_ACTION
    if blocked_architectures:
        if followups:
            return "targeted_internal_batch_v2_partially_blocked", FOLLOWUP_NEXT_ACTION
        return "targeted_internal_batch_v2_partially_blocked", NO_FOLLOWUP_NEXT_ACTION
    if followups:
        return "targeted_internal_batch_v2_followup_found", FOLLOWUP_NEXT_ACTION
    return "targeted_internal_batch_v2_no_followup", NO_FOLLOWUP_NEXT_ACTION


def next_action_rows(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "entity_id": result["config"].strategy_id,
            "entity_type": "strategy_configuration",
            "outcome": result["outcome"],
            "next_action": strategy_next_action(result),
            "execute_in_this_task": False,
        }
        for result in results.values()
    ]
    rows.append(
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "outcome": outcome,
            "next_action": next_action,
            "execute_in_this_task": False,
        }
    )
    return rows


def outcome_summary_rows(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        followup = next((result for result in arch_results if result["outcome"] == "exploratory_followup_candidate"), None)
        blocked_reason = next((result["failure_reason"] for result in arch_results if result["split"] is None), "")
        architecture_failure = (
            blocked_reason
            if blocked_reason
            else (
                winner["failure_reason"]
                if winner is not None
                else arch_results[0]["failure_reason"]
            )
        )
        rows.append(
            {
                "entity_id": arch.architecture_id,
                "entity_type": "architecture",
                "stage": STAGE,
                "outcome": "exploratory_followup_candidate" if followup else ("closed_optimization" if winner is None else winner["outcome"]),
                "selected_strategy_id": "" if winner is None else winner["config"].strategy_id,
                "selected_trial_id": "" if winner is None else winner["config"].trial_id,
                "failure_reason": architecture_failure,
                "decision_reason": "winner passed evaluation" if followup else "no exploratory follow-up from this architecture",
                "batch_outcome": outcome,
                "batch_next_action": next_action,
                "validation_claimed": False,
                "robustness_claimed": False,
                "paper_demo_authorized": False,
            }
        )
    rows.append(
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": outcome,
            "selected_strategy_id": "",
            "selected_trial_id": "",
            "failure_reason": "duplicate_or_redundant" if outcome.endswith("partially_blocked") else "",
            "decision_reason": "bounded V2 batch completed; candidate-level follow-up routing takes precedence when present",
            "batch_outcome": outcome,
            "batch_next_action": next_action,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
        }
    )
    return rows


def process_task_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "mode": MODE,
            "stage": STAGE,
            "task_scope": "exactly_three_architectures_four_configs_each_twelve_canonical_configurations",
            "architecture_count": 3,
            "strategy_configuration_count": 12,
            "canonical_trial_count": 12,
            "batch_outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
        }
    ]


def entity_counts(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> dict[str, Any]:
    selected_count = sum(result.get("selected_winner", False) for result in results.values())
    followup_count = sum(result["outcome"] == "exploratory_followup_candidate" for result in results.values())
    executed_count = sum(result["split"] is not None for result in results.values())
    return {
        "architectures_preregistered": len(ARCHITECTURES),
        "strategy_configurations": len(CONFIGS),
        "canonical_experiment_trials": len(CONFIGS),
        "executed_trials": executed_count,
        "duplicate_or_blocked_trials": len(CONFIGS) - executed_count,
        "architecture_winners": selected_count,
        "exploratory_followup_candidates": followup_count,
        "benchmark_references": len(benchmark_rows()),
        "process_tasks": 1,
        "robustness_trials_created": 0,
        "validation_trials_created": 0,
        "paper_demo_eligibility_records_created": 0,
        "handoff_export_records_created": 0,
        "observations_created": 0,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }


def build_report(results: dict[str, dict[str, Any]], counts: dict[str, Any], outcome: str, next_action: str) -> str:
    lines = [
        "# Accepted-47 Targeted Internal Technical Batch V2",
        "",
        "## Scope",
        "",
        "Exactly three preregistered internally generated technical/chart-data architectures and twelve canonical configurations were processed. This is optimization evidence only.",
        "",
        "## Architecture Outcomes",
        "",
        "| Architecture | Status | Winner | Failure/next reason |",
        "|---|---|---|---|",
    ]
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        if winner is None:
            status = arch_results[0]["failure_reason"] or "closed_optimization"
            reason = arch_results[0]["decision_reason"]
        else:
            status = winner["outcome"]
            reason = winner["failure_reason"] or "follow-up candidate"
        lines.append(
            f"| `{arch.architecture_id}` | `{status}` | `{winner['config'].strategy_id if winner else ''}` | `{reason}` |"
        )
    lines.extend(
        [
            "",
            "## Entity Counts",
            "",
            f"* Architectures: {counts['architectures_preregistered']}",
            f"* Strategy configurations: {counts['strategy_configurations']}",
            f"* Canonical trials: {counts['canonical_experiment_trials']}",
            f"* Executed trials: {counts['executed_trials']}",
            f"* Selected architecture winners: {counts['architecture_winners']}",
            f"* Exploratory follow-up candidates: {counts['exploratory_followup_candidates']}",
            "",
            "## Guardrails",
            "",
            "* Existing accepted-47 pilot cache only; no provider or network access.",
            "* No capture-asymmetry variant was created or tested.",
            "* Nonselected variants have no evaluation-segment interpretation.",
            "* Controls are benchmark references only and cannot be promoted.",
            "* No robustness, validation, paper/demo, handoff, observation, broker, or real-money action was run.",
            "",
            "## Batch Outcome",
            "",
            f"`{outcome}`",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


METRIC_RESULT_FIELDS = base.METRIC_RESULT_FIELDS

CSV_FIELDS = dict(base.CSV_FIELDS)
CSV_FIELDS["parameter_grid.csv"] = base.CSV_FIELDS["parameter_grid.csv"] + ["protected_capture_asymmetry_variant"]
CSV_FIELDS["duplicate_preflight.csv"] = [
    "architecture_id", "family_id", "architecture_code", "preflight_status", "execute_architecture_trials",
    "executed_trial_count", "matched_existing_project", "matched_existing_architecture_id", "matched_existing_path",
    "completed_record_scan_hash", "protected_capture_asymmetry_variant_created", "formula_checked",
    "required_data_checked", "universe_checked", "formation_schedule_checked", "ranking_characteristic_checked",
    "target_construction_checked", "parameter_grid_checked", "formula_match", "universe_match",
    "formation_schedule_match", "ranking_characteristic_match", "target_construction_match",
    "parameter_grid_similarity_sufficient", "broad_family_similarity_only", "distinctive_characteristic",
    "decision_reason", "preperformance_complete",
]
CSV_FIELDS["evaluation_subhalf_results.csv"] = [
    "architecture_id", "strategy_id", "trial_id", "subhalf_id", "period_start", "period_end",
    "formation_count", "diagnostic_state", "candidate_sharpe", "named_control_sharpe",
    "candidate_maximum_drawdown", "named_control_maximum_drawdown",
    "worse_than_named_on_both_sharpe_and_drawdown", "pass",
]
CSV_FIELDS["failure_vectors.csv"] = [
    "architecture_id", "strategy_id", "trial_id", "stage", "duplicate_or_redundant",
    "selection_eligible", "selected_winner", "evaluation_access_allowed", "exploratory_followup_candidate",
    "selection_cagr_positive_5bps", "selection_invariants_pass_5bps",
    "selection_named_control_not_dominating_5bps", "selection_material_vs_named_control_5bps",
    "selection_static_equal_control_not_dominating_5bps", "selection_cagr_positive_10bps",
    "evaluation_cagr_positive_5bps", "evaluation_invariants_pass_5bps",
    "evaluation_named_control_not_dominating_5bps", "evaluation_material_vs_named_control_5bps",
    "evaluation_static_equal_control_not_dominating_5bps", "evaluation_cagr_positive_10bps",
    "evaluation_subhalf_stability_pass", "calendar_year_concentration_pass",
    "rebalance_month_concentration_pass", "primary_failure_reason", "outcome",
]


def required_files_will_be_present_after_consistency_write() -> bool:
    current = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    return (current | {"consistency_check.json"}) == REQUIRED_OUTPUT_FILES


def deterministic_core_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_OUTPUT_FILES - {"consistency_check.json"}):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def protected_capture_fingerprint_preserved() -> bool:
    path = ROOT / "evidence" / "handoff" / "internal_capture_asymmetry_63d_top3_v1" / "latest" / "strategy_configuration_fingerprint.txt"
    return path.exists() and path.read_text(encoding="utf-8").strip() == PROTECTED_CAPTURE_HANDOFF_FINGERPRINT


def run() -> dict[str, Any]:
    if len(ARCHITECTURES) != 3 or len(CONFIGS) != 12:
        raise RuntimeError("Frozen architecture/configuration scope drift")
    if len({config.strategy_id for config in CONFIGS}) != 12 or len({config.trial_id for config in CONFIGS}) != 12:
        raise RuntimeError("Strategy/trial identifiers are not unique")
    if any("capture_asymmetry" in config.strategy_id or "capture" in config.trial_id for config in CONFIGS):
        raise RuntimeError("Protected capture-asymmetry strategy family drift")

    before_protected = protected_hashes()
    duplicate_rows = duplicate_preflight_rows()
    frames = load_frames()
    cache_rows = cache_preflight_rows(frames)
    splits, results = build_executed_results(frames, duplicate_rows)
    outcome, next_action = batch_outcome(results)
    counts = entity_counts(results, outcome, next_action)

    clean_output_dir()
    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": TASK_ID,
            "module_owner": "trading_tournament",
            "mode": MODE,
            "stage": STAGE,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "source_or_research_lineage": SOURCE_LINEAGE,
            "architecture_count": 3,
            "configuration_count": 12,
            "primary_one_way_cost_bps": PRIMARY_COST,
            "diagnostic_one_way_cost_bps": [0.0, 10.0],
            "data_boundary": {
                "cache_dir": rel(CACHE_DIR),
                "provider_access": False,
                "network_access": False,
                "data_refresh": False,
                "accepted_47_membership_modified": False,
                "forward_observation_data_used": False,
            },
            "protected_successful_strategy": {
                "strategy_id": "internal_capture_asymmetry_63d_top3_v1",
                "fingerprint": PROTECTED_CAPTURE_HANDOFF_FINGERPRINT,
                "nearby_variant_created": False,
            },
            "optimization_split": "first_60pct_valid_rebalance_observations_selection_final_40pct_exploratory_evaluation",
            "batch_outcome": outcome,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
            "handoff_export_created": False,
            "forward_observation_operation": False,
        },
    )
    write_yaml(
        OUTPUT_DIR / "architecture_preregistration.yaml",
        {
            "batch_id": TASK_ID,
            "preregistered_architectures": [
                {
                    "architecture_code": arch.architecture_code,
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "display_name": arch.display_name,
                    "source_or_research_lineage": SOURCE_LINEAGE,
                    "universe": list(arch.universe),
                    "accounting_universe": list(arch.accounting_universe),
                    "named_control": arch.named_control_id,
                    "static_equal_weight_controls": [arch.static_control_id, arch.equal_weight_control_id],
                    "primary_future_robustness_role": arch.primary_future_robustness_role,
                    "incremental_hypothesis": arch.incremental_hypothesis,
                    "distinctive_characteristic": arch.distinct_characteristic,
                    "configuration_codes": [config.configuration_code for config in configs_for_architecture(arch.architecture_code)],
                }
                for arch in ARCHITECTURES
            ],
            "grid_expansion_after_results_allowed": False,
            "replacement_architecture_after_duplicate_allowed": False,
        },
    )

    artifact_rows = {
        "parameter_grid.csv": parameter_grid_rows(),
        "strategy_cards.csv": strategy_card_rows(results),
        "trial_ledger.csv": trial_ledger_rows(results),
        "duplicate_preflight.csv": duplicate_rows,
        "benchmark_reference_log.csv": benchmark_rows(),
        "selection_segment_definition.csv": selection_definition_rows(splits, duplicate_rows),
        "selection_segment_results.csv": selection_segment_rows(results),
        "architecture_winner_selection.csv": architecture_winner_rows(results),
        "evaluation_segment_results.csv": evaluation_segment_rows(results),
        "evaluation_subhalf_results.csv": evaluation_subhalf_rows(results),
        "post_selection_full_period_diagnostics.csv": post_selection_full_period_rows(results),
        "calendar_year_results.csv": calendar_year_rows(results),
        "rebalance_contribution_results.csv": rebalance_contribution_rows(results),
        "lightweight_concentration_diagnostics.csv": concentration_rows(results),
        "turnover_cost_reconciliation.csv": turnover_rows(results),
        "invariant_results.csv": invariant_rows(results),
        "exploratory_followup_candidates.csv": followup_rows(results),
        "failure_vectors.csv": failure_vector_rows(results),
        "failure_reasons.csv": failure_reason_rows(results),
        "process_task_log.csv": process_task_rows(outcome, next_action),
        "outcome_summary.csv": outcome_summary_rows(results, outcome, next_action),
        "next_actions.csv": next_action_rows(results, outcome, next_action),
    }
    for name, rows in artifact_rows.items():
        write_csv(OUTPUT_DIR / name, rows, CSV_FIELDS[name])
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, counts, outcome, next_action))

    after_protected = protected_hashes()
    selected_by_architecture = {
        arch.architecture_id: sum(results[config.trial_id].get("selected_winner", False) for config in configs_for_architecture(arch.architecture_code))
        for arch in ARCHITECTURES
    }
    evaluation_trial_ids = {row["trial_id"] for row in artifact_rows["evaluation_segment_results.csv"]}
    winner_trial_ids = {result["config"].trial_id for result in results.values() if result.get("selected_winner")}
    followup_count = counts["exploratory_followup_candidates"]
    blocked_architecture_count = sum(
        1
        for arch in ARCHITECTURES
        if all(results[config.trial_id]["split"] is None for config in configs_for_architecture(arch.architecture_code))
    )
    failed_reasons_allowed = all(
        not result["failure_reason"] or result["failure_reason"] in PERMITTED_FAILURE_REASONS
        for result in results.values()
    )
    checks = {
        "exact_three_architectures": len(ARCHITECTURES) == 3,
        "exact_twelve_configurations": len(CONFIGS) == 12,
        "four_configurations_per_architecture": all(len(configs_for_architecture(arch.architecture_code)) == 4 for arch in ARCHITECTURES),
        "unique_strategy_ids": len({config.strategy_id for config in CONFIGS}) == 12,
        "unique_trial_ids": len({config.trial_id for config in CONFIGS}) == 12,
        "no_capture_asymmetry_variant_created": all("capture" not in config.strategy_id for config in CONFIGS),
        "duplicate_preflight_before_performance_complete": all(row["preperformance_complete"] for row in duplicate_rows),
        "common_period_and_split_reproducible": len(splits) == 3 - blocked_architecture_count,
        "winner_count_at_most_one_per_architecture": all(value <= 1 for value in selected_by_architecture.values()),
        "nonwinner_evaluation_access_prohibited": evaluation_trial_ids <= winner_trial_ids,
        "routing_precedence_followup_over_partial_block": (
            followup_count == 0
            or next_action == FOLLOWUP_NEXT_ACTION
        ),
        "controls_are_benchmark_references_only": all(not row["counted_as_strategy"] and not row["counted_as_trial"] for row in benchmark_rows()),
        "all_executed_invariants_pass": all(row["invariant_pass"] for row in artifact_rows["invariant_results.csv"]),
        "no_forbidden_actions": not any(FORBIDDEN_ACTION_FLAGS.values()),
        "entity_count_reconciliation_pass": (
            counts["architectures_preregistered"] == 3
            and counts["strategy_configurations"] == 12
            and counts["canonical_experiment_trials"] == 12
            and counts["robustness_trials_created"] == 0
            and counts["validation_trials_created"] == 0
            and counts["paper_demo_eligibility_records_created"] == 0
            and counts["handoff_export_records_created"] == 0
            and counts["observations_created"] == 0
        ),
        "protected_capture_strategy_fingerprint_preserved": protected_capture_fingerprint_preserved(),
        "protected_state_cache_and_prior_evidence_unchanged": before_protected == after_protected,
        "failure_reasons_within_permitted_set": failed_reasons_allowed,
        "required_output_set_complete": required_files_will_be_present_after_consistency_write(),
    }
    consistency = {
        "batch_id": TASK_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "cache_preflight": cache_rows,
        "protected_state_hashes_before": before_protected,
        "protected_state_hashes_after": after_protected,
        "forbidden_actions": FORBIDDEN_ACTION_FLAGS,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "required_output_files_present": required_files_will_be_present_after_consistency_write(),
        "deterministic_core_hash": deterministic_core_hash(),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "batch_outcome": outcome,
        "next_action": next_action,
        "entity_counts": counts,
        "consistency_overall_pass": consistency["overall_pass"],
        "deterministic_core_hash": consistency["deterministic_core_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
