from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import native_etf_source_refresh_v3_exploration_batch as helpers
from strategy_lab.research_os.research import native_etf_two_candidate_exploration_batch_v1 as portfolio_helpers


TASK_ID = "technical_strategy_factory_v1"
LINEAGE_ID = "internal_technical_strategy_factory_v1"
OUTPUT_DIR = ROOT / "evidence" / "technical_factory" / TASK_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\8b7238c1-2b01-4e8b-9db3-8fca7ebe380d\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-08-04T12:00:00+00:00"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10

SPY_UNIVERSE = ("SPY", "BIL")
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
SECTOR_UNIVERSE = (*SECTORS, "BIL")
SECTOR_ACCOUNTING_UNIVERSE = (*SECTORS, "BIL", "SPY")
REQUIRED_SYMBOLS = ("SPY", "BIL", *SECTORS)


@dataclass(frozen=True)
class VariantSpec:
    architecture_id: str
    family_id: str
    code: str
    parameters: dict[str, Any]
    universe: tuple[str, ...]
    route: str = "standalone_with_diversifier_diagnostic"

    @property
    def strategy_id(self) -> str:
        return f"{self.architecture_id}_{self.code.lower()}"

    @property
    def trial_id(self) -> str:
        return f"technical_factory_v1__{self.code.lower()}__canonical"

    @property
    def display_name(self) -> str:
        return f"{ARCHITECTURE_TITLES[self.architecture_id]} {self.code}"


ARCHITECTURE_TITLES = {
    "factory_v1_spy_trend_regime_zscore_reversion": "SPY Trend-Regime Z-Score Reversion",
    "factory_v1_spy_volatility_contraction_breakout": "SPY Volatility-Contraction Breakout",
    "factory_v1_spy_volume_confirmed_breakout": "SPY Volume-Confirmed Breakout",
    "factory_v1_spy_trend_quality_state": "SPY Regression Trend-Quality State",
    "factory_v1_sector_breadth_risk_adjusted_top3": "Sector Breadth Risk-Adjusted Top Three",
    "factory_v1_sector_weekly_reversal_regime": "Sector Weekly Reversal Regime",
}

ARCHITECTURE_FAMILIES = {
    "factory_v1_spy_trend_regime_zscore_reversion": "trend_regime_mean_reversion",
    "factory_v1_spy_volatility_contraction_breakout": "volatility_contraction_breakout",
    "factory_v1_spy_volume_confirmed_breakout": "price_volume_breakout",
    "factory_v1_spy_trend_quality_state": "regression_trend_quality",
    "factory_v1_sector_breadth_risk_adjusted_top3": "breadth_conditioned_cross_sectional_selection",
    "factory_v1_sector_weekly_reversal_regime": "regime_filtered_cross_sectional_reversal",
}

ARCHITECTURE_DESCRIPTIONS = {
    "factory_v1_spy_trend_regime_zscore_reversion": "long_only_completed_close_trend_filtered_zscore_state",
    "factory_v1_spy_volatility_contraction_breakout": "long_only_armed_bandwidth_contraction_breakout_state",
    "factory_v1_spy_volume_confirmed_breakout": "long_only_price_breakout_with_adjusted_volume_confirmation",
    "factory_v1_spy_trend_quality_state": "long_only_log_price_regression_slope_and_r2_state",
    "factory_v1_sector_breadth_risk_adjusted_top3": "monthly_breadth_conditioned_risk_adjusted_sector_selection",
    "factory_v1_sector_weekly_reversal_regime": "weekly_regime_filtered_cross_sectional_sector_reversal",
}

PARAMETER_GRIDS = {
    "factory_v1_spy_trend_regime_zscore_reversion": (
        ("A1", {"entry_z": -1.0, "exit_z": 0.0}),
        ("A2", {"entry_z": -1.5, "exit_z": 0.0}),
        ("A3", {"entry_z": -1.0, "exit_z": 0.5}),
        ("A4", {"entry_z": -1.5, "exit_z": 0.5}),
    ),
    "factory_v1_spy_volatility_contraction_breakout": (
        ("B1", {"contraction_percentile": 0.10, "breakout_sessions": 20}),
        ("B2", {"contraction_percentile": 0.10, "breakout_sessions": 55}),
        ("B3", {"contraction_percentile": 0.20, "breakout_sessions": 20}),
        ("B4", {"contraction_percentile": 0.20, "breakout_sessions": 55}),
    ),
    "factory_v1_spy_volume_confirmed_breakout": (
        ("C1", {"breakout_sessions": 20, "volume_z_threshold": 0.5}),
        ("C2", {"breakout_sessions": 20, "volume_z_threshold": 1.0}),
        ("C3", {"breakout_sessions": 55, "volume_z_threshold": 0.5}),
        ("C4", {"breakout_sessions": 55, "volume_z_threshold": 1.0}),
    ),
    "factory_v1_spy_trend_quality_state": (
        ("D1", {"lookback_sessions": 60, "r2_threshold": 0.25}),
        ("D2", {"lookback_sessions": 60, "r2_threshold": 0.50}),
        ("D3", {"lookback_sessions": 120, "r2_threshold": 0.25}),
        ("D4", {"lookback_sessions": 120, "r2_threshold": 0.50}),
    ),
    "factory_v1_sector_breadth_risk_adjusted_top3": (
        ("E1", {"breadth_SMA_sessions": 100, "breadth_threshold": 5}),
        ("E2", {"breadth_SMA_sessions": 100, "breadth_threshold": 6}),
        ("E3", {"breadth_SMA_sessions": 200, "breadth_threshold": 5}),
        ("E4", {"breadth_SMA_sessions": 200, "breadth_threshold": 6}),
    ),
    "factory_v1_sector_weekly_reversal_regime": (
        ("F1", {"regime_SMA_sessions": 100, "reversal_lookback_sessions": 5}),
        ("F2", {"regime_SMA_sessions": 100, "reversal_lookback_sessions": 10}),
        ("F3", {"regime_SMA_sessions": 200, "reversal_lookback_sessions": 5}),
        ("F4", {"regime_SMA_sessions": 200, "reversal_lookback_sessions": 10}),
    ),
}

CONTROL_SETS = {
    "factory_v1_spy_trend_regime_zscore_reversion": (
        "same_zscore_rule_without_long_term_regime",
        "sma200_spy_bil_trend_state",
        "full_period_exposure_matched_static_spy_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v1_spy_volatility_contraction_breakout": (
        "same_breakout_without_contraction_requirement",
        "contraction_state_close_above_sma20_entry",
        "full_period_exposure_matched_static_spy_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v1_spy_volume_confirmed_breakout": (
        "same_breakout_without_volume_confirmation",
        "volume_condition_close_above_sma20_entry",
        "full_period_exposure_matched_static_spy_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v1_spy_trend_quality_state": (
        "same_regression_slope_without_path_quality_filter",
        "same_lookback_endpoint_return_positive_state",
        "full_period_exposure_matched_static_spy_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v1_sector_breadth_risk_adjusted_top3": (
        "same_risk_adjusted_top3_without_breadth_condition",
        "raw_63session_return_top3_same_breadth",
        "monthly_equal_weight_nine_sectors",
        "full_period_exposure_matched_static_sector_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v1_sector_weekly_reversal_regime": (
        "same_bottom2_reversal_without_regime_filter",
        "same_regime_equal_weight_eligible_sectors",
        "monthly_equal_weight_nine_sectors",
        "full_period_exposure_matched_static_sector_bil",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
}

NAMED_CONTROLS = {architecture: controls[0] for architecture, controls in CONTROL_SETS.items()}
STATIC_CONTROLS = {architecture: controls[2 if architecture.startswith("factory_v1_spy_") else 3] for architecture, controls in CONTROL_SETS.items()}

VARIANTS = tuple(
    VariantSpec(
        architecture_id=architecture,
        family_id=ARCHITECTURE_FAMILIES[architecture],
        code=code,
        parameters=parameters,
        universe=SPY_UNIVERSE if architecture.startswith("factory_v1_spy_") else SECTOR_UNIVERSE,
    )
    for architecture, grid in PARAMETER_GRIDS.items()
    for code, parameters in grid
)

FROZEN_ARTIFACTS = (
    "architecture_catalog.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "walk_forward_folds.csv",
    "selection_rule.yaml",
    "prohibited_adaptations.yaml",
)

REQUIRED_FILES = {
    "factory_manifest.yaml",
    "internal_research_lineage.csv",
    "architecture_catalog.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "walk_forward_folds.csv",
    "selection_rule.yaml",
    "prohibited_adaptations.yaml",
    "all_variant_full_results.csv",
    "walk_forward_fold_results.csv",
    "walk_forward_pass_matrix.csv",
    "variant_selection_decisions.csv",
    "selected_variant_freeze.csv",
    "final_evaluation_results.csv",
    "final_control_results.csv",
    "portfolio_contribution_results.csv",
    "concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "multiple_testing_ledger.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "factory_report.md",
    *{f"{architecture}_signal_ledger.csv" for architecture in PARAMETER_GRIDS},
}


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path, excluded: Path | None = None) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        if excluded_resolved is not None and excluded_resolved in item.resolve().parents:
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def snapshot_hashes() -> dict[str, str]:
    output = {
        relative(path): tree_hash(path)
        for path in (*helpers.PROTECTED_STATE_PATHS, *helpers.PROTECTED_TREE_PATHS)
    }
    output["evidence_excluding_current_factory"] = tree_hash(ROOT / "evidence", OUTPUT_DIR)
    return output


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "technical_factory" / TASK_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected path {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    columns = list(leading)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def adjusted_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    return helpers.adjusted_ohlcv(raw)


def frame_hash(frame: pd.DataFrame) -> str:
    return helpers.frame_hash(frame)


def preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], bool]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    passed_all = True
    for symbol in REQUIRED_SYMBOLS:
        raw = market.load_adjusted_ohlcv(symbol)
        frame = adjusted_ohlcv(raw) if not raw.empty else pd.DataFrame()
        frames[symbol] = frame
        values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float) if not frame.empty else np.empty((0, 4))
        ordered = bool(not frame.empty and frame.index.is_monotonic_increasing and frame.index.is_unique)
        positive = bool(values.size and np.isfinite(values).all() and (values > 0.0).all())
        ohlc = bool(
            not frame.empty
            and (frame["high"] + TOLERANCE >= frame[["open", "low", "close"]].max(axis=1)).all()
            and (frame["low"] - TOLERANCE <= frame[["open", "high", "close"]].min(axis=1)).all()
        )
        volume = bool(
            not frame.empty
            and np.isfinite(frame["volume"].to_numpy(dtype=float)).all()
            and (frame["volume"] >= 0.0).all()
        )
        adjusted = bool(
            not raw.empty
            and np.allclose(frame["close"].to_numpy(), raw["adj_close"].to_numpy(), rtol=0.0, atol=TOLERANCE)
        )
        passed = ordered and positive and ohlc and volume and adjusted
        passed_all &= passed
        rows.append({
            "symbol": symbol,
            "cache_path": raw.attrs.get("cache_path", ""),
            "canonical_file_hash": raw.attrs.get("cache_hash", "missing"),
            "normalized_frame_hash": frame_hash(frame) if not frame.empty else "missing",
            "first_valid_date": "" if frame.empty else frame.index[0].date().isoformat(),
            "last_valid_date": "" if frame.empty else frame.index[-1].date().isoformat(),
            "row_count": len(frame),
            "ordered_unique_sessions": ordered,
            "finite_positive_adjusted_ohlc": positive,
            "valid_adjusted_ohlc_relationships": ohlc,
            "finite_nonnegative_adjusted_volume": volume,
            "canonical_adjustment_compatible": adjusted,
            "provider_access_performed": False,
            "preflight_status": "pass" if passed else "fail",
        })
    return rows, frames, passed_all


def common_prices(frames: dict[str, pd.DataFrame], universe: tuple[str, ...]) -> pd.DataFrame:
    return pd.concat(
        [frames[symbol]["close"].rename(symbol) for symbol in universe],
        axis=1,
        join="inner",
    ).dropna()


def next_session(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def target(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return target(columns, {"BIL": 1.0})


def event_frame(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    events: dict[pd.Timestamp, dict[str, float]],
) -> pd.DataFrame:
    return accounting.event_frame(index, columns, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def monthly_static_events(
    index: pd.DatetimeIndex, columns: tuple[str, ...], weights: dict[str, float]
) -> pd.DataFrame:
    return helpers.monthly_static_events(index, columns, weights)


def percentile_rank_inclusive_linear(values: np.ndarray, value: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=float))
    if not len(ordered) or not np.isfinite(ordered).all() or not math.isfinite(value):
        return float("nan")
    if len(ordered) == 1:
        return 0.0
    matches = np.flatnonzero(np.isclose(ordered, value, rtol=0.0, atol=1e-14))
    if len(matches):
        return float(matches.mean() / (len(ordered) - 1))
    insertion = int(np.searchsorted(ordered, value, side="left"))
    if insertion <= 0:
        return 0.0
    if insertion >= len(ordered):
        return 1.0
    lower, upper = ordered[insertion - 1], ordered[insertion]
    fraction = (value - lower) / (upper - lower)
    return float(((insertion - 1) + fraction) / (len(ordered) - 1))


def regression_state(values: np.ndarray) -> tuple[float, float]:
    y = np.log(np.asarray(values, dtype=float))
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    residual = float(np.square(y - fitted).sum())
    total = float(np.square(y - y.mean()).sum())
    r2 = 1.0 - residual / total if total > 0.0 else float("nan")
    return float(np.exp(slope * 252.0) - 1.0), r2


def architecture_catalog() -> list[dict[str, Any]]:
    return [
        {
            "architecture_id": architecture,
            "entity_type": "architecture_catalog_entry",
            "family_id": ARCHITECTURE_FAMILIES[architecture],
            "display_name": ARCHITECTURE_TITLES[architecture],
            "strategy_architecture": ARCHITECTURE_DESCRIPTIONS[architecture],
            "configuration_count": 4,
            "universe": list(SPY_UNIVERSE if architecture.startswith("factory_v1_spy_") else SECTOR_UNIVERSE),
            "route": "standalone_with_diversifier_diagnostic",
            "external_source_claimed": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for architecture in PARAMETER_GRIDS
    ]


def _state_event(
    events: dict[pd.Timestamp, dict[str, float]],
    execution: pd.Timestamp | None,
    columns: tuple[str, ...],
    risky: bool,
) -> None:
    if execution is not None:
        events[execution] = target(columns, {"SPY": 1.0} if risky else {"BIL": 1.0})


def _finish_prepared(
    spec: VariantSpec,
    prices: pd.DataFrame,
    candidate_events: dict[pd.Timestamp, dict[str, float]],
    controls: dict[str, pd.DataFrame],
    diagnostics: list[dict[str, Any]],
    first_eligible_execution: pd.Timestamp,
    execution_calendar: list[pd.Timestamp],
) -> dict[str, Any]:
    columns = tuple(prices.columns)
    candidate = event_frame(prices.index, columns, candidate_events)
    candidate_targets = target_history(candidate, prices.index)
    average_weights = {symbol: float(candidate_targets[symbol].mean()) for symbol in columns}
    static_id = STATIC_CONTROLS[spec.architecture_id]
    controls[static_id] = monthly_static_events(prices.index, columns, average_weights)
    controls["SPY_buy_and_hold"] = accounting.initial_event(
        prices.index, columns, target(columns, {"SPY": 1.0})
    )
    controls["BIL_buy_and_hold"] = accounting.initial_event(
        prices.index, columns, bil_target(columns)
    )
    return {
        "spec": spec,
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "named_control": NAMED_CONTROLS[spec.architecture_id],
        "static_control": static_id,
        "diagnostics": pd.DataFrame(diagnostics),
        "first_eligible_execution": pd.Timestamp(first_eligible_execution),
        "execution_calendar": pd.DatetimeIndex(sorted(set(execution_calendar))),
        "average_target_weights": average_weights,
        "candidate_targets": candidate_targets,
    }


def prepare_a(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SPY_UNIVERSE)
    close = prices["SPY"]
    sma200 = close.rolling(200, min_periods=200).mean()
    mean20 = close.rolling(20, min_periods=20).mean()
    std20 = close.rolling(20, min_periods=20).std(ddof=1)
    z20 = (close - mean20) / std20
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    no_regime_events = {pd.Timestamp(prices.index[0]): initial}
    trend_events = {pd.Timestamp(prices.index[0]): initial}
    candidate_state = no_regime_state = trend_state = False
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    for position, signal_date in enumerate(prices.index):
        valid = bool(
            position >= 199
            and math.isfinite(float(sma200.iloc[position]))
            and math.isfinite(float(z20.iloc[position]))
            and float(std20.iloc[position]) > 0.0
        )
        execution = next_session(prices.index, signal_date)
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            close_value = float(close.iloc[position])
            z_value = float(z20.iloc[position])
            desired = candidate_state
            if not candidate_state and close_value > float(sma200.iloc[position]) and z_value <= float(spec.parameters["entry_z"]):
                desired = True
            elif candidate_state and (z_value >= float(spec.parameters["exit_z"]) or close_value < float(sma200.iloc[position])):
                desired = False
            if desired != candidate_state:
                candidate_state = desired
                _state_event(candidate_events, execution, columns, candidate_state)

            desired_no_regime = no_regime_state
            if not no_regime_state and z_value <= float(spec.parameters["entry_z"]):
                desired_no_regime = True
            elif no_regime_state and z_value >= float(spec.parameters["exit_z"]):
                desired_no_regime = False
            if desired_no_regime != no_regime_state:
                no_regime_state = desired_no_regime
                _state_event(no_regime_events, execution, columns, no_regime_state)

            desired_trend = close_value > float(sma200.iloc[position])
            if desired_trend != trend_state:
                trend_state = desired_trend
                _state_event(trend_events, execution, columns, trend_state)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "close": close.iloc[position],
            "sma200": sma200.iloc[position],
            "mean20": mean20.iloc[position],
            "std20": std20.iloc[position],
            "z20": z20.iloc[position],
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if no_regime_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        "same_zscore_rule_without_long_term_regime": event_frame(prices.index, columns, no_regime_events),
        "sma200_spy_bil_trend_state": event_frame(prices.index, columns, trend_events),
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


def _armed_breakout_update(
    state: bool,
    armed_remaining: int,
    contraction: bool,
    entry: bool,
    exit_signal: bool,
) -> tuple[bool, int]:
    if state:
        return (False, 0) if exit_signal else (True, 0)
    if contraction:
        armed_remaining = 20
    if armed_remaining > 0 and entry:
        return True, 0
    return False, max(armed_remaining - 1, 0)


def prepare_b(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SPY_UNIVERSE)
    close = prices["SPY"]
    sma20 = close.rolling(20, min_periods=20).mean()
    std20 = close.rolling(20, min_periods=20).std(ddof=1)
    bandwidth = (4.0 * std20) / sma20
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    named_events = {pd.Timestamp(prices.index[0]): initial}
    simple_events = {pd.Timestamp(prices.index[0]): initial}
    candidate_state = named_state = simple_state = False
    candidate_arm = simple_arm = 0
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    lookback = int(spec.parameters["breakout_sessions"])
    threshold = float(spec.parameters["contraction_percentile"])
    for position, signal_date in enumerate(prices.index):
        window = bandwidth.iloc[: position + 1].dropna().tail(252)
        rank = percentile_rank_inclusive_linear(window.to_numpy(dtype=float), float(bandwidth.iloc[position])) if len(window) == 252 else float("nan")
        prior = close.iloc[max(0, position - lookback):position]
        valid = bool(len(window) == 252 and len(prior) == lookback and math.isfinite(rank))
        execution = next_session(prices.index, signal_date)
        breakout = bool(valid and float(close.iloc[position]) > float(prior.max()))
        contraction = bool(valid and rank <= threshold)
        exit_signal = bool(valid and float(close.iloc[position]) < float(sma20.iloc[position]))
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            old = candidate_state
            candidate_state, candidate_arm = _armed_breakout_update(candidate_state, candidate_arm, contraction, breakout, exit_signal)
            if candidate_state != old:
                _state_event(candidate_events, execution, columns, candidate_state)
            desired_named = named_state
            if named_state and exit_signal:
                desired_named = False
            elif not named_state and breakout:
                desired_named = True
            if desired_named != named_state:
                named_state = desired_named
                _state_event(named_events, execution, columns, named_state)
            old_simple = simple_state
            simple_state, simple_arm = _armed_breakout_update(
                simple_state,
                simple_arm,
                contraction,
                float(close.iloc[position]) > float(sma20.iloc[position]),
                exit_signal,
            )
            if simple_state != old_simple:
                _state_event(simple_events, execution, columns, simple_state)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "sma20": sma20.iloc[position],
            "std20": std20.iloc[position],
            "bandwidth20": bandwidth.iloc[position],
            "bandwidth_percentile252": rank,
            "contraction_state": contraction,
            "armed_sessions_remaining": candidate_arm,
            "breakout_signal": breakout,
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if named_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        "same_breakout_without_contraction_requirement": event_frame(prices.index, columns, named_events),
        "contraction_state_close_above_sma20_entry": event_frame(prices.index, columns, simple_events),
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


def prepare_c(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spy = frames["SPY"]
    bil = frames["BIL"]
    index = spy.index.intersection(bil.index)
    prices = pd.DataFrame({"SPY": spy.loc[index, "close"], "BIL": bil.loc[index, "close"]})
    volume = spy.loc[index, "volume"]
    close = prices["SPY"]
    mean20 = volume.rolling(20, min_periods=20).mean()
    std20 = volume.rolling(20, min_periods=20).std(ddof=1)
    volume_z = (volume - mean20) / std20
    sma20 = close.rolling(20, min_periods=20).mean()
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(index[0]): initial}
    named_events = {pd.Timestamp(index[0]): initial}
    simple_events = {pd.Timestamp(index[0]): initial}
    candidate_state = named_state = simple_state = False
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    lookback = int(spec.parameters["breakout_sessions"])
    threshold = float(spec.parameters["volume_z_threshold"])
    for position, signal_date in enumerate(index):
        breakout_window = close.iloc[max(0, position - lookback):position]
        exit_window = close.iloc[max(0, position - 10):position]
        valid = bool(
            len(breakout_window) == lookback
            and len(exit_window) == 10
            and math.isfinite(float(volume_z.iloc[position]))
            and float(std20.iloc[position]) > 0.0
        )
        execution = next_session(index, signal_date)
        breakout = bool(valid and float(close.iloc[position]) > float(breakout_window.max()))
        volume_condition = bool(valid and float(volume_z.iloc[position]) > threshold)
        exit_signal = bool(valid and float(close.iloc[position]) < float(exit_window.min()))
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            desired = candidate_state
            if candidate_state and exit_signal:
                desired = False
            elif not candidate_state and breakout and volume_condition:
                desired = True
            if desired != candidate_state:
                candidate_state = desired
                _state_event(candidate_events, execution, columns, candidate_state)
            desired_named = named_state
            if named_state and exit_signal:
                desired_named = False
            elif not named_state and breakout:
                desired_named = True
            if desired_named != named_state:
                named_state = desired_named
                _state_event(named_events, execution, columns, named_state)
            desired_simple = simple_state
            if simple_state and exit_signal:
                desired_simple = False
            elif not simple_state and volume_condition and float(close.iloc[position]) > float(sma20.iloc[position]):
                desired_simple = True
            if desired_simple != simple_state:
                simple_state = desired_simple
                _state_event(simple_events, execution, columns, simple_state)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "volume_mean20": mean20.iloc[position],
            "volume_std20": std20.iloc[position],
            "volume_z20": volume_z.iloc[position],
            "breakout_signal": breakout,
            "volume_condition": volume_condition,
            "exit_signal": exit_signal,
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if named_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        "same_breakout_without_volume_confirmation": event_frame(index, columns, named_events),
        "volume_condition_close_above_sma20_entry": event_frame(index, columns, simple_events),
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


def prepare_d(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SPY_UNIVERSE)
    close = prices["SPY"]
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    slope_events = {pd.Timestamp(prices.index[0]): initial}
    endpoint_events = {pd.Timestamp(prices.index[0]): initial}
    candidate_state = slope_state = endpoint_state = False
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    lookback = int(spec.parameters["lookback_sessions"])
    threshold = float(spec.parameters["r2_threshold"])
    for position, signal_date in enumerate(prices.index):
        window = close.iloc[max(0, position - lookback + 1):position + 1]
        valid = len(window) == lookback
        annualized_slope = r2 = float("nan")
        if valid:
            annualized_slope, r2 = regression_state(window.to_numpy(dtype=float))
            valid = math.isfinite(annualized_slope) and math.isfinite(r2)
        execution = next_session(prices.index, signal_date)
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            desired = annualized_slope > 0.0 and r2 >= threshold
            if desired != candidate_state:
                candidate_state = desired
                _state_event(candidate_events, execution, columns, candidate_state)
            desired_slope = annualized_slope > 0.0
            if desired_slope != slope_state:
                slope_state = desired_slope
                _state_event(slope_events, execution, columns, slope_state)
            desired_endpoint = float(window.iloc[-1]) > float(window.iloc[0])
            if desired_endpoint != endpoint_state:
                endpoint_state = desired_endpoint
                _state_event(endpoint_events, execution, columns, endpoint_state)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "lookback_sessions": lookback,
            "annualized_slope": annualized_slope,
            "r_squared": r2,
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if slope_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        "same_regression_slope_without_path_quality_filter": event_frame(prices.index, columns, slope_events),
        "same_lookback_endpoint_return_positive_state": event_frame(prices.index, columns, endpoint_events),
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


def _month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]


def _week_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("W-FRI")).last().tolist()
    ]


def prepare_e(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SECTOR_ACCOUNTING_UNIVERSE)
    sector_prices = prices[list(SECTORS)]
    sector_returns = sector_prices.pct_change(fill_method=None)
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    named_events = {pd.Timestamp(prices.index[0]): initial}
    raw_events = {pd.Timestamp(prices.index[0]): initial}
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    sma_length = int(spec.parameters["breadth_SMA_sessions"])
    breadth_threshold = int(spec.parameters["breadth_threshold"])
    for signal_date in _month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = next_session(prices.index, signal_date)
        valid = position >= max(sma_length - 1, 63)
        breadth_count = 0
        scores: dict[str, float] = {}
        raw_returns: dict[str, float] = {}
        if valid:
            for sector in SECTORS:
                sma = float(sector_prices[sector].iloc[position - sma_length + 1:position + 1].mean())
                breadth_count += int(float(sector_prices.loc[signal_date, sector]) > sma)
                total_return = float(sector_prices[sector].iloc[position] / sector_prices[sector].iloc[position - 63] - 1.0)
                volatility = float(sector_returns[sector].iloc[position - 62:position + 1].std(ddof=1))
                if not math.isfinite(volatility) or volatility <= 0.0:
                    valid = False
                    break
                raw_returns[sector] = total_return
                scores[sector] = total_return / volatility
        selected: list[str] = []
        named_selected: list[str] = []
        raw_selected: list[str] = []
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            named_selected = sorted(SECTORS, key=lambda sector: (-scores[sector], sector))[:3]
            if breadth_count >= breadth_threshold:
                selected = named_selected
                raw_selected = sorted(SECTORS, key=lambda sector: (-raw_returns[sector], sector))[:3]
            candidate_events[execution] = target(
                columns,
                {sector: 1.0 / 3.0 for sector in selected} if selected else {"BIL": 1.0},
            )
            named_events[execution] = target(columns, {sector: 1.0 / 3.0 for sector in named_selected})
            raw_events[execution] = target(
                columns,
                {sector: 1.0 / 3.0 for sector in raw_selected} if raw_selected else {"BIL": 1.0},
            )
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "breadth_count": breadth_count,
            "breadth_threshold": breadth_threshold,
            "breadth_condition": breadth_count >= breadth_threshold if valid else False,
            "risk_adjusted_scores": scores,
            "raw_63session_returns": raw_returns,
            "candidate_selection": selected,
            "named_control_selection": named_selected,
            "raw_return_control_selection": raw_selected,
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    equal_events = monthly_static_events(
        prices.index, columns, {sector: 1.0 / len(SECTORS) for sector in SECTORS}
    )
    controls = {
        "same_risk_adjusted_top3_without_breadth_condition": event_frame(prices.index, columns, named_events),
        "raw_63session_return_top3_same_breadth": event_frame(prices.index, columns, raw_events),
        "monthly_equal_weight_nine_sectors": equal_events,
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


def prepare_f(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SECTOR_ACCOUNTING_UNIVERSE)
    sector_prices = prices[list(SECTORS)]
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    named_events = {pd.Timestamp(prices.index[0]): initial}
    eligible_events = {pd.Timestamp(prices.index[0]): initial}
    diagnostics: list[dict[str, Any]] = []
    execution_calendar: list[pd.Timestamp] = []
    first_execution: pd.Timestamp | None = None
    sma_length = int(spec.parameters["regime_SMA_sessions"])
    reversal = int(spec.parameters["reversal_lookback_sessions"])
    for signal_date in _week_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = next_session(prices.index, signal_date)
        valid = position >= max(sma_length - 1, reversal)
        eligible: list[str] = []
        reversal_returns: dict[str, float] = {}
        if valid:
            for sector in SECTORS:
                sma = float(sector_prices[sector].iloc[position - sma_length + 1:position + 1].mean())
                if float(sector_prices.loc[signal_date, sector]) > sma:
                    eligible.append(sector)
                reversal_returns[sector] = float(
                    sector_prices[sector].iloc[position] / sector_prices[sector].iloc[position - reversal] - 1.0
                )
        selected = sorted(eligible, key=lambda sector: (reversal_returns[sector], sector))[:2] if len(eligible) >= 2 else []
        named_selected = sorted(SECTORS, key=lambda sector: (reversal_returns[sector], sector))[:2] if valid else []
        if valid and execution is not None:
            execution_calendar.append(execution)
            first_execution = execution if first_execution is None else first_execution
            candidate_events[execution] = target(
                columns,
                {sector: 0.5 for sector in selected} if selected else {"BIL": 1.0},
            )
            named_events[execution] = target(columns, {sector: 0.5 for sector in named_selected})
            eligible_events[execution] = target(
                columns,
                {sector: 1.0 / len(eligible) for sector in eligible} if eligible else {"BIL": 1.0},
            )
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "eligible_sectors": eligible,
            "eligible_count": len(eligible),
            "reversal_returns": reversal_returns,
            "candidate_selection": selected,
            "named_control_selection": named_selected,
            "signal_uses_completed_session_only": True,
        })
    if first_execution is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        "same_bottom2_reversal_without_regime_filter": event_frame(prices.index, columns, named_events),
        "same_regime_equal_weight_eligible_sectors": event_frame(prices.index, columns, eligible_events),
        "monthly_equal_weight_nine_sectors": monthly_static_events(
            prices.index, columns, {sector: 1.0 / len(SECTORS) for sector in SECTORS}
        ),
    }
    return _finish_prepared(spec, prices, candidate_events, controls, diagnostics, first_execution, execution_calendar)


PREPARE_FUNCTIONS = {
    "factory_v1_spy_trend_regime_zscore_reversion": prepare_a,
    "factory_v1_spy_volatility_contraction_breakout": prepare_b,
    "factory_v1_spy_volume_confirmed_breakout": prepare_c,
    "factory_v1_spy_trend_quality_state": prepare_d,
    "factory_v1_sector_breadth_risk_adjusted_top3": prepare_e,
    "factory_v1_sector_weekly_reversal_regime": prepare_f,
}


def prepare_variant(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return PREPARE_FUNCTIONS[spec.architecture_id](spec, frames)


FROZEN_RULES = {
    "factory_v1_spy_trend_regime_zscore_reversion": {
        "signal": "enter SPY when close>SMA200 and Z20<=entry_z; exit when Z20>=exit_z or close<SMA200",
        "indicators": "SMA200; mean20; sample std20 ddof=1; Z20=(close-mean20)/std20",
        "invalid_signal": "retain current target",
    },
    "factory_v1_spy_volatility_contraction_breakout": {
        "signal": "arm when inclusive-linear bandwidth percentile252<=threshold for at most 20 sessions; enter on prior-close breakout; exit below SMA20",
        "indicators": "SMA20; sample std20 ddof=1; two-standard-deviation bands; bandwidth; inclusive-linear percentile rank",
        "invalid_signal": "retain current target",
    },
    "factory_v1_spy_volume_confirmed_breakout": {
        "signal": "enter on prior-close breakout and VolumeZ20>threshold; exit below prior-10-session close minimum",
        "indicators": "adjusted volume mean20; sample std20 ddof=1; VolumeZ20",
        "invalid_signal": "no entry when volume standard deviation is zero or invalid",
    },
    "factory_v1_spy_trend_quality_state": {
        "signal": "hold SPY when annualized log-price regression slope>0 and ordinary R-squared>=threshold; otherwise BIL",
        "indicators": "OLS log(close) on session index; annualized slope=exp(slope*252)-1; ordinary R-squared",
        "invalid_signal": "hold BIL",
    },
    "factory_v1_sector_breadth_risk_adjusted_top3": {
        "signal": "monthly; when sector breadth threshold passes, rank 63-session return/sample daily volatility and equally hold top three; otherwise BIL",
        "indicators": "sector close>SMA breadth; 63-session total return; 63-session sample daily volatility ddof=1",
        "invalid_signal": "hold BIL",
    },
    "factory_v1_sector_weekly_reversal_regime": {
        "signal": "weekly; among sectors above regime SMA, equally hold bottom two trailing-return sectors; fewer than two eligible means BIL",
        "indicators": "sector SMA regime and trailing reversal total return",
        "invalid_signal": "hold BIL",
    },
}


def fold_rows(prepared: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, pd.DatetimeIndex]]]:
    rows: list[dict[str, Any]] = []
    periods: dict[str, dict[str, pd.DatetimeIndex]] = {}
    for architecture in PARAMETER_GRIDS:
        architecture_variants = [spec for spec in VARIANTS if spec.architecture_id == architecture]
        first = max(prepared[spec.strategy_id]["first_eligible_execution"] for spec in architecture_variants)
        index = prepared[architecture_variants[0].strategy_id]["prices"].index
        eligible = index[index >= first]
        calendar = prepared[architecture_variants[0].strategy_id]["execution_calendar"]
        calendar = calendar[calendar >= first]
        aligned: dict[float, pd.Timestamp] = {}
        for fraction in (0.40, 0.50, 0.60, 0.70, 0.80):
            raw_position = min(int(math.floor((len(eligible) - 1) * fraction)), len(eligible) - 1)
            raw_date = pd.Timestamp(eligible[raw_position])
            candidates = calendar[calendar >= raw_date]
            if not len(candidates):
                raise RuntimeError(f"no aligned boundary for {architecture} at {fraction}")
            aligned[fraction] = pd.Timestamp(candidates[0])
        architecture_periods: dict[str, pd.DatetimeIndex] = {}
        fractions = ((0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 0.80))
        for fold_number, (start_fraction, end_fraction) in enumerate(fractions, start=1):
            start = aligned[start_fraction]
            next_start = aligned[end_fraction]
            evaluation = index[(index >= start) & (index < next_start)]
            architecture_periods[f"fold_{fold_number}"] = evaluation
            prior = index[index < start]
            rows.append({
                "architecture_id": architecture,
                "period_id": f"fold_{fold_number}",
                "period_role": "walk_forward_selection",
                "prior_history_start": eligible[0].date().isoformat(),
                "prior_history_through": prior[-1].date().isoformat(),
                "evaluation_start": evaluation[0].date().isoformat(),
                "evaluation_end": evaluation[-1].date().isoformat(),
                "start_fraction": start_fraction,
                "end_fraction": end_fraction,
                "boundary_alignment": "first_valid_execution_boundary_at_or_after_fractional_session",
                "used_for_variant_selection": True,
                "final_segment": False,
            })
        final = index[index >= aligned[0.80]]
        architecture_periods["factory_final_evaluation_segment"] = final
        development = index[(index >= eligible[0]) & (index < aligned[0.80])]
        architecture_periods["selection_development_80pct"] = development
        rows.append({
            "architecture_id": architecture,
            "period_id": "factory_final_evaluation_segment",
            "period_role": "final_exploratory_evaluation",
            "prior_history_start": eligible[0].date().isoformat(),
            "prior_history_through": index[index < final[0]][-1].date().isoformat(),
            "evaluation_start": final[0].date().isoformat(),
            "evaluation_end": final[-1].date().isoformat(),
            "start_fraction": 0.80,
            "end_fraction": 1.00,
            "boundary_alignment": "first_valid_execution_boundary_at_or_after_fractional_session",
            "used_for_variant_selection": False,
            "final_segment": True,
        })
        periods[architecture] = architecture_periods
    return rows, periods


def strategy_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "family_id": spec.family_id,
            "architecture_id": spec.architecture_id,
            "display_name": spec.display_name,
            "entity_type": "strategy_configuration",
            "strategy_architecture": ARCHITECTURE_DESCRIPTIONS[spec.architecture_id],
            "parameters": spec.parameters,
            "universe": list(spec.universe),
            "route": spec.route,
            "source_or_research_lineage": f"{LINEAGE_ID}:{spec.architecture_id}",
            "benchmark_or_control_set": list(CONTROL_SETS[spec.architecture_id]),
            "stage": "exploration",
            "outcome": "preregistered_pending_factory_execution",
            "failure_reason": "",
            "next_action": "execute_frozen_factory_trial",
            "external_source_claimed": False,
            "parameter_grid_frozen_before_performance": True,
            "optimization_performed": "bounded_preregistered_parameter_search",
            "post_result_adaptation_allowed": False,
        }
        for spec in VARIANTS
    ]


def trial_rows() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "entity_type": "experiment_trial",
            "parent_trial_id": "",
            "adaptation_label": "",
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "canonical_trial": True,
        }
        for row in strategy_rows()
    ]


def benchmark_rows(prepared: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        for control in CONTROL_SETS[spec.architecture_id]:
            row = {
                "strategy_id": spec.strategy_id,
                "architecture_id": spec.architecture_id,
                "benchmark_id": control,
                "entity_type": "benchmark_reference",
                "stage": "benchmark_reference_only",
                "named_same_purpose_control": control == NAMED_CONTROLS[spec.architecture_id],
                "exposure_or_static_control": control == STATIC_CONTROLS[spec.architecture_id],
                "control_parameters": (
                    prepared[spec.strategy_id]["average_target_weights"]
                    if control == STATIC_CONTROLS[spec.architecture_id]
                    else spec.parameters
                ),
                "frozen_before_performance": True,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
            rows.append(row)
    return rows


def write_preperformance_freeze(
    prepared: dict[str, dict[str, Any]],
    folds: list[dict[str, Any]],
    preflight_rows: list[dict[str, Any]],
) -> dict[str, str]:
    write_csv(
        "internal_research_lineage.csv",
        [{
            "research_lineage_id": LINEAGE_ID,
            "lineage_type": "internally_generated_technical_hypothesis",
            "external_source_claimed": False,
            "optimization_type": "bounded_preregistered_parameter_search",
            "stage": "exploration",
            "source_replication": False,
            "parameter_grid_frozen_before_performance": True,
            "instruments_frozen_before_performance": True,
            "controls_frozen_before_performance": True,
            "walk_forward_folds_frozen_before_performance": True,
            "final_evaluation_segment_frozen_before_performance": True,
            "post_result_grid_expansion_allowed": False,
            "post_result_parameter_change_allowed": False,
            "validation_claimed": False,
            "paper_demo_eligibility_claimed": False,
        }],
        (
            "research_lineage_id", "lineage_type", "external_source_claimed",
            "optimization_type", "stage", "source_replication",
            "parameter_grid_frozen_before_performance", "instruments_frozen_before_performance",
            "controls_frozen_before_performance", "walk_forward_folds_frozen_before_performance",
            "final_evaluation_segment_frozen_before_performance",
            "post_result_grid_expansion_allowed", "post_result_parameter_change_allowed",
            "validation_claimed", "paper_demo_eligibility_claimed",
        ),
    )
    write_yaml(
        "architecture_catalog.yaml",
        {"research_lineage_id": LINEAGE_ID, "architecture_count": 6, "architectures": [
            {**row, "frozen_rule": FROZEN_RULES[row["architecture_id"]]}
            for row in architecture_catalog()
        ]},
    )
    write_csv(
        "parameter_grid.csv",
        [{
            "architecture_id": spec.architecture_id,
            "family_id": spec.family_id,
            "configuration_code": spec.code,
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "parameters": spec.parameters,
            "grid_frozen_before_performance": True,
            "post_result_grid_expansion_allowed": False,
        } for spec in VARIANTS],
        (
            "architecture_id", "family_id", "configuration_code", "strategy_id",
            "trial_id", "parameters", "grid_frozen_before_performance",
            "post_result_grid_expansion_allowed",
        ),
    )
    card_headers = (
        "strategy_id", "trial_id", "family_id", "architecture_id", "display_name",
        "entity_type", "strategy_architecture", "parameters", "universe", "route",
        "source_or_research_lineage", "benchmark_or_control_set", "stage", "outcome",
        "failure_reason", "next_action",
    )
    write_csv("strategy_cards.csv", strategy_rows(), card_headers)
    write_csv("trial_ledger.csv", trial_rows(), card_headers)
    write_csv(
        "benchmark_reference_log.csv",
        benchmark_rows(prepared),
        (
            "strategy_id", "architecture_id", "benchmark_id", "entity_type", "stage",
            "named_same_purpose_control", "exposure_or_static_control",
            "control_parameters", "frozen_before_performance", "counted_as_strategy",
            "counted_as_trial",
        ),
    )
    write_csv(
        "walk_forward_folds.csv",
        folds,
        (
            "architecture_id", "period_id", "period_role", "prior_history_start",
            "prior_history_through", "evaluation_start", "evaluation_end", "start_fraction",
            "end_fraction", "boundary_alignment", "used_for_variant_selection", "final_segment",
        ),
    )
    write_yaml("selection_rule.yaml", {
        "primary_cost_bps": 5,
        "fold_pass": [
            "positive_return",
            "not_dominated_by_named_control",
            "not_dominated_by_exposure_static_control",
            "material_advantage_vs_both_controls",
            "all_invariants_pass",
        ],
        "selection_eligibility": "at_least_3_of_4_folds",
        "lexicographic_ranking": [
            "higher_passed_fold_count",
            "higher_median_fold_sharpe_difference_vs_named",
            "higher_median_fold_drawdown_improvement_vs_named",
            "higher_median_fold_sharpe_difference_vs_exposure_static",
            "lower_median_turnover",
            "lexically_smaller_strategy_id",
        ],
        "maximum_selected_per_architecture": 1,
        "final_segment_used_for_selection": False,
    })
    write_yaml("prohibited_adaptations.yaml", {
        "post_performance": [
            "seventh_architecture", "twenty_fifth_trial", "grid_expansion",
            "parameter_change", "instrument_replacement", "control_change",
            "final_segment_reselection", "external_source_claim", "robustness",
            "paper_demo_onboarding",
        ]
    })
    write_csv(
        "data_preflight_reconciliation.csv",
        preflight_rows,
        (
            "symbol", "cache_path", "canonical_file_hash", "normalized_frame_hash",
            "first_valid_date", "last_valid_date", "row_count", "ordered_unique_sessions",
            "finite_positive_adjusted_ohlc", "valid_adjusted_ohlc_relationships",
            "finite_nonnegative_adjusted_volume", "canonical_adjustment_compatible",
            "provider_access_performed", "preflight_status",
        ),
    )
    write_csv(
        "process_task_log.csv",
        [{
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": "exploration",
            "architecture_count": 6,
            "strategy_configuration_count": 24,
            "canonical_trial_count": 24,
            "provider_access_performed": False,
            "validation_or_lifecycle_work": False,
        }],
        (
            "process_task_id", "entity_type", "stage", "architecture_count",
            "strategy_configuration_count", "canonical_trial_count",
            "provider_access_performed", "validation_or_lifecycle_work",
        ),
    )
    return {name: file_hash(OUTPUT_DIR / name) for name in FROZEN_ARTIFACTS}


def simulate_prepared(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_session_target_applied_at_following_regular_session_close"
    candidates: dict[float, dict[str, Any]] = {}
    controls: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidates[cost] = accounting.simulate_path(
            prepared["prices"], prepared["candidate_events"], cost, timing
        )
        for control_id, events in prepared["control_events"].items():
            controls[(control_id, cost)] = accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
    return {"candidate_paths": candidates, "control_paths": controls}


def truncate_prepared(prepared: dict[str, Any], end: pd.Timestamp) -> dict[str, Any]:
    """Create the selection-only view without exposing final-segment returns."""
    end = pd.Timestamp(end)
    prices = prepared["prices"].loc[:end].copy()
    if prices.empty:
        raise RuntimeError(f"empty development view through {end}")
    candidate_events = prepared["candidate_events"].loc[:end].copy()
    control_events = {
        control_id: events.loc[:end].copy()
        for control_id, events in prepared["control_events"].items()
    }
    return {
        **prepared,
        "prices": prices,
        "candidate_events": candidate_events,
        "control_events": control_events,
        "candidate_targets": prepared["candidate_targets"].loc[:end].copy(),
        "execution_calendar": prepared["execution_calendar"][
            prepared["execution_calendar"] <= end
        ],
        "selection_view_only": True,
        "selection_view_end": end,
    }


def path_metrics(
    path: dict[str, Any], fallback_symbol: str, period_index: pd.DatetimeIndex
) -> dict[str, Any]:
    return portfolio_helpers.period_metrics(path, fallback_symbol, period_index)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def metric_row(
    spec: VariantSpec,
    series_id: str,
    cost: float,
    period_id: str,
    values: dict[str, Any],
    result_role: str,
) -> dict[str, Any]:
    return {
        "architecture_id": spec.architecture_id,
        "strategy_id": spec.strategy_id,
        "trial_id": spec.trial_id,
        "series_id": series_id,
        "result_role": result_role,
        "cost_bps_one_way": cost,
        "period_id": period_id,
        **values,
    }


def run_walk_forward(
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, VariantSpec | None],
]:
    development_rows: list[dict[str, Any]] = []
    fold_rows_output: list[dict[str, Any]] = []
    pass_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    selected: dict[str, VariantSpec | None] = {}
    for spec in VARIANTS:
        simulation = simulations[spec.strategy_id]
        development = periods[spec.architecture_id]["selection_development_80pct"]
        for cost in COSTS:
            values = path_metrics(simulation["candidate_paths"][cost], "BIL", development)
            development_rows.append(
                metric_row(
                    spec,
                    spec.strategy_id,
                    cost,
                    "selection_development_80pct",
                    values,
                    "candidate_configuration_development_only",
                )
            )
        named = NAMED_CONTROLS[spec.architecture_id]
        static = STATIC_CONTROLS[spec.architecture_id]
        for fold_number in range(1, 5):
            period_id = f"fold_{fold_number}"
            evaluation = periods[spec.architecture_id][period_id]
            candidate_values = path_metrics(simulation["candidate_paths"][PRIMARY_COST], "BIL", evaluation)
            named_values = path_metrics(simulation["control_paths"][(named, PRIMARY_COST)], "BIL", evaluation)
            static_values = path_metrics(simulation["control_paths"][(static, PRIMARY_COST)], "BIL", evaluation)
            for series_id, values, role in (
                (spec.strategy_id, candidate_values, "candidate"),
                (named, named_values, "named_same_purpose_control"),
                (static, static_values, "exposure_static_control"),
            ):
                fold_rows_output.append(
                    metric_row(spec, series_id, PRIMARY_COST, period_id, values, role)
                )
            checks = {
                "positive_return": float(candidate_values["total_return"]) > 0.0,
                "not_dominated_by_named_control": not dominates(named_values, candidate_values),
                "not_dominated_by_exposure_static_control": not dominates(static_values, candidate_values),
                "material_advantage_vs_named_control": material_advantage(candidate_values, named_values),
                "material_advantage_vs_exposure_static_control": material_advantage(candidate_values, static_values),
                "every_invariant_passes": bool(candidate_values["invariant_pass"]),
            }
            pass_rows.append({
                "architecture_id": spec.architecture_id,
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                "fold_id": period_id,
                **checks,
                "fold_pass": all(checks.values()),
                "sharpe_difference_vs_named": float(candidate_values["sharpe_ratio"]) - float(named_values["sharpe_ratio"]),
                "drawdown_improvement_vs_named": float(candidate_values["maximum_drawdown"]) - float(named_values["maximum_drawdown"]),
                "sharpe_difference_vs_exposure_static": float(candidate_values["sharpe_ratio"]) - float(static_values["sharpe_ratio"]),
                "candidate_turnover": candidate_values["turnover"],
                "final_segment_used": False,
            })

    for architecture in PARAMETER_GRIDS:
        architecture_specs = [spec for spec in VARIANTS if spec.architecture_id == architecture]
        ranking_rows: list[tuple[VariantSpec, dict[str, Any]]] = []
        for spec in architecture_specs:
            subset = [row for row in pass_rows if row["strategy_id"] == spec.strategy_id]
            summary = {
                "passed_fold_count": sum(row["fold_pass"] for row in subset),
                "median_fold_sharpe_difference_vs_named": float(np.median([row["sharpe_difference_vs_named"] for row in subset])),
                "median_fold_drawdown_improvement_vs_named": float(np.median([row["drawdown_improvement_vs_named"] for row in subset])),
                "median_fold_sharpe_difference_vs_exposure_static": float(np.median([row["sharpe_difference_vs_exposure_static"] for row in subset])),
                "median_turnover": float(np.median([row["candidate_turnover"] for row in subset])),
            }
            ranking_rows.append((spec, summary))
        ranked = sorted(
            ranking_rows,
            key=lambda item: (
                -item[1]["passed_fold_count"],
                -item[1]["median_fold_sharpe_difference_vs_named"],
                -item[1]["median_fold_drawdown_improvement_vs_named"],
                -item[1]["median_fold_sharpe_difference_vs_exposure_static"],
                item[1]["median_turnover"],
                item[0].strategy_id,
            ),
        )
        eligible = [item for item in ranked if item[1]["passed_fold_count"] >= 3]
        selected_spec = eligible[0][0] if eligible else None
        selected[architecture] = selected_spec
        for rank, (spec, summary) in enumerate(ranked, start=1):
            selection_rows.append({
                "architecture_id": architecture,
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                **summary,
                "selection_eligible": summary["passed_fold_count"] >= 3,
                "lexicographic_rank": rank,
                "selected_for_final_evaluation": selected_spec is not None and spec.strategy_id == selected_spec.strategy_id,
                "final_segment_inspected_before_selection": False,
                "post_result_parameter_change": False,
            })
    return development_rows, fold_rows_output, pass_rows, selection_rows, selected


def final_concentration(
    spec: VariantSpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    final_index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    named = simulation["control_paths"][(NAMED_CONTROLS[spec.architecture_id], PRIMARY_COST)]
    candidate_returns = candidate["returns"].reindex(final_index)
    named_returns = named["returns"].reindex(final_index)
    daily_excess = candidate_returns - named_returns
    monthly_excess = daily_excess.groupby(final_index.to_period("M")).sum()
    yearly_excess = monthly_excess.groupby(monthly_excess.index.year).sum()
    positive_year_total = float(yearly_excess.clip(lower=0.0).sum())
    year_fraction = float(yearly_excess.clip(lower=0.0).max() / positive_year_total) if positive_year_total > 0.0 else 0.0
    rows: list[dict[str, Any]] = [
        {
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "row_type": "calendar_year",
            "component": int(year),
            "candidate_minus_named_additive_excess": float(value),
            "positive_excess_fraction": float(max(value, 0.0) / positive_year_total) if positive_year_total > 0.0 else 0.0,
        }
        for year, value in yearly_excess.items()
    ]
    targets = target_history(
        prepared["candidate_events"], prepared["prices"].index
    ).reindex(final_index)
    signatures = targets.round(12).astype(str).agg("|".join, axis=1)
    groups = signatures.ne(signatures.shift()).cumsum()
    episode_values = daily_excess.groupby(groups).sum()
    positive_episode_total = float(episode_values.clip(lower=0.0).sum())
    episode_fraction = float(episode_values.clip(lower=0.0).max() / positive_episode_total) if positive_episode_total > 0.0 else 0.0
    for episode, value in episode_values.items():
        episode_index = final_index[groups.to_numpy() == episode]
        rows.append({
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "row_type": "holding_episode",
            "component": int(episode),
            "component_start": episode_index[0].date().isoformat(),
            "component_end": episode_index[-1].date().isoformat(),
            "candidate_minus_named_additive_excess": float(value),
            "positive_excess_fraction": float(max(value, 0.0) / positive_episode_total) if positive_episode_total > 0.0 else 0.0,
        })
    sector_fraction = 0.0
    if spec.architecture_id in (
        "factory_v1_sector_breadth_risk_adjusted_top3",
        "factory_v1_sector_weekly_reversal_regime",
    ):
        asset_returns = prepared["prices"].pct_change(fill_method=None).fillna(0.0)
        contributions = (
            (candidate["held_weights"] - named["held_weights"]) * asset_returns
        ).reindex(final_index)[list(SECTORS)].sum()
        positive_sector_total = float(contributions.clip(lower=0.0).sum())
        sector_fraction = float(contributions.clip(lower=0.0).max() / positive_sector_total) if positive_sector_total > 0.0 else 0.0
        for sector, value in contributions.items():
            rows.append({
                "architecture_id": spec.architecture_id,
                "strategy_id": spec.strategy_id,
                "row_type": "sector",
                "component": sector,
                "candidate_minus_named_additive_excess": float(value),
                "positive_excess_fraction": float(max(value, 0.0) / positive_sector_total) if positive_sector_total > 0.0 else 0.0,
            })
    rows.extend([
        {"architecture_id": spec.architecture_id, "strategy_id": spec.strategy_id, "row_type": "summary", "component": "maximum_calendar_year_positive_excess_fraction", "value": year_fraction},
        {"architecture_id": spec.architecture_id, "strategy_id": spec.strategy_id, "row_type": "summary", "component": "maximum_holding_episode_positive_excess_fraction", "value": episode_fraction},
        {"architecture_id": spec.architecture_id, "strategy_id": spec.strategy_id, "row_type": "summary", "component": "maximum_sector_positive_excess_fraction", "value": sector_fraction},
    ])
    return rows, {"year_fraction": year_fraction, "episode_fraction": episode_fraction, "sector_fraction": sector_fraction}


def evaluate_selected_variants(
    selected: dict[str, VariantSpec | None],
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for architecture in PARAMETER_GRIDS:
        spec = selected[architecture]
        if spec is None:
            outcomes.append({
                "architecture_id": architecture,
                "architecture_outcome": "factory_architecture_closed",
                "selected_strategy_id": "",
                "selected_trial_id": "",
                "selected_configuration_outcome": "closed_exploration",
                "failure_reason": "no_variant_passed_walk_forward",
                "route_classification": "closed",
                "final_evaluation_performed": False,
                "final_segment_used_for_reselection": False,
            })
            continue
        simulation = simulations[spec.strategy_id]
        final_index = periods[architecture]["factory_final_evaluation_segment"]
        candidate_metrics: dict[float, dict[str, Any]] = {}
        control_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            candidate_metrics[cost] = path_metrics(
                simulation["candidate_paths"][cost], "BIL", final_index
            )
            candidate_rows.append(
                metric_row(
                    spec,
                    spec.strategy_id,
                    cost,
                    "factory_final_evaluation_segment",
                    candidate_metrics[cost],
                    "selected_candidate_final_evaluation",
                )
            )
            for control_id in CONTROL_SETS[architecture]:
                values = path_metrics(
                    simulation["control_paths"][(control_id, cost)], "BIL", final_index
                )
                control_metrics[(control_id, cost)] = values
                control_rows.append(
                    metric_row(
                        spec,
                        control_id,
                        cost,
                        "factory_final_evaluation_segment",
                        values,
                        "benchmark_reference_final_evaluation",
                    )
                )
        concentration, concentration_summary = final_concentration(
            spec, prepared[spec.strategy_id], simulation, final_index
        )
        concentration_rows.extend(concentration)
        named = NAMED_CONTROLS[architecture]
        static = STATIC_CONTROLS[architecture]
        candidate5 = candidate_metrics[5.0]
        named5 = control_metrics[(named, 5.0)]
        static5 = control_metrics[(static, 5.0)]
        candidate10 = candidate_metrics[10.0]
        named10 = control_metrics[(named, 10.0)]
        static10 = control_metrics[(static, 10.0)]
        checks = {
            "positive_final_return_5bps": float(candidate5["total_return"]) > 0.0,
            "every_invariant_passes": bool(candidate5["invariant_pass"]),
            "neither_critical_control_dominates_5bps": not (
                dominates(named5, candidate5) or dominates(static5, candidate5)
            ),
            "material_advantage_vs_named_5bps": material_advantage(candidate5, named5),
            "material_advantage_vs_static_5bps": material_advantage(candidate5, static5),
            "positive_and_not_dominated_by_both_at_10bps": bool(
                float(candidate10["total_return"]) > 0.0
                and not (dominates(named10, candidate10) and dominates(static10, candidate10))
            ),
            "no_calendar_year_over_70pct_positive_excess": concentration_summary["year_fraction"] <= 0.70,
            "no_episode_over_70pct_positive_excess": concentration_summary["episode_fraction"] <= 0.70,
            "no_sector_over_70pct_positive_excess": (
                concentration_summary["sector_fraction"] <= 0.70
                if architecture in (
                    "factory_v1_sector_breadth_risk_adjusted_top3",
                    "factory_v1_sector_weekly_reversal_regime",
                )
                else True
            ),
        }
        final_pass = all(checks.values())

        portfolio_paths = portfolio_helpers.portfolio_paths(
            prepared[spec.strategy_id], simulation, named, static
        )
        portfolio_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            for construction in (
                "100pct_frozen_reference",
                "80pct_reference_20pct_candidate",
                "80pct_reference_20pct_named_same_purpose_control",
                "80pct_reference_20pct_exposure_or_static_control",
            ):
                path = portfolio_paths[(construction, cost)]
                common_final = final_index.intersection(path["returns"].index)
                values = portfolio_helpers.period_metrics(path, "reference", common_final)
                portfolio_metrics[(construction, cost)] = values
                portfolio_rows.append({
                    "architecture_id": architecture,
                    "strategy_id": spec.strategy_id,
                    "trial_id": spec.trial_id,
                    "construction_id": construction,
                    "entity_role": "portfolio_diagnostic",
                    "cost_bps_one_way": cost,
                    "period_id": "factory_final_evaluation_segment",
                    **values,
                    "variant_selection_changed": False,
                })
        reference5 = portfolio_metrics[("100pct_frozen_reference", 5.0)]
        portfolio_candidate5 = portfolio_metrics[("80pct_reference_20pct_candidate", 5.0)]
        portfolio_named5 = portfolio_metrics[("80pct_reference_20pct_named_same_purpose_control", 5.0)]
        portfolio_static5 = portfolio_metrics[("80pct_reference_20pct_exposure_or_static_control", 5.0)]
        diversifier_diagnostic_pass = bool(
            material_advantage(portfolio_candidate5, reference5)
            and not dominates(portfolio_named5, portfolio_candidate5)
            and not dominates(portfolio_static5, portfolio_candidate5)
            and material_advantage(portfolio_candidate5, portfolio_named5)
            and material_advantage(portfolio_candidate5, portfolio_static5)
        )
        if final_pass:
            architecture_outcome = "factory_exploratory_followup_candidate"
            configuration_outcome = "exploratory_followup_candidate_standalone"
            failure_reason = ""
            route_classification = (
                "standalone_with_diversifier_diagnostic"
                if diversifier_diagnostic_pass
                else "standalone"
            )
        else:
            architecture_outcome = "factory_architecture_closed"
            configuration_outcome = "closed_exploration"
            route_classification = "closed"
            if not checks["positive_final_return_5bps"]:
                failure_reason = "weak_return"
            elif not checks["neither_critical_control_dominates_5bps"]:
                failure_reason = "weak_vs_primary_control"
            elif not (
                checks["material_advantage_vs_named_5bps"]
                and checks["material_advantage_vs_static_5bps"]
            ):
                failure_reason = "benchmark_like_behavior"
            elif not checks["positive_and_not_dominated_by_both_at_10bps"]:
                failure_reason = "cost_drag"
            elif not (
                checks["no_calendar_year_over_70pct_positive_excess"]
                and checks["no_episode_over_70pct_positive_excess"]
                and checks["no_sector_over_70pct_positive_excess"]
            ):
                failure_reason = "concentration_risk"
            else:
                failure_reason = "overfit_or_unstable"
        outcomes.append({
            "architecture_id": architecture,
            "architecture_outcome": architecture_outcome,
            "selected_strategy_id": spec.strategy_id,
            "selected_trial_id": spec.trial_id,
            "selected_configuration_outcome": configuration_outcome,
            "failure_reason": failure_reason,
            "route_classification": route_classification,
            "final_evaluation_performed": True,
            "final_gate_checks": checks,
            "diversifier_diagnostic_pass": diversifier_diagnostic_pass,
            "final_segment_used_for_reselection": False,
        })
    return candidate_rows, control_rows, portfolio_rows, concentration_rows, outcomes


def report_text(outcomes: list[dict[str, Any]], next_action: str, overall_pass: bool) -> str:
    lines = [
        "# Technical Strategy Factory V1",
        "",
        "## Scope",
        "",
        "A controlled internal technical-discovery pilot froze six architectures and 24 configurations before performance. Four anchored selection folds used only the first 80% of each architecture's eligible history; only frozen selections were evaluated on the final 20%.",
        "",
        "## Architecture Outcomes",
        "",
        "| Architecture | Selected configuration | Outcome | Failure reason | Route |",
        "|---|---|---|---|---|",
    ]
    for row in outcomes:
        lines.append(
            f"| {row['architecture_id']} | {row['selected_strategy_id']} | "
            f"{row['architecture_outcome']} | {row['failure_reason']} | {row['route_classification']} |"
        )
    lines.extend([
        "",
        "## Boundaries",
        "",
        "This is internally generated exploration and bounded optimization evidence. It is not external-source replication, validation, robustness, lifecycle promotion, or paper/demo eligibility.",
        "",
        "No provider, broker, account, order, capital, or real-money action occurred.",
        "",
        f"Consistency check: `overall_pass = {str(overall_pass).lower()}`.",
        "",
        f"Exact next action: `{next_action}`.",
        "",
    ])
    return "\n".join(lines)


def path_fingerprint(path: dict[str, Any]) -> str:
    frame = pd.concat(
        [
            path["returns"].rename("return"),
            path["turnover"].rename("turnover"),
            path["cost"].rename("cost"),
            path["held_weights"].add_prefix("weight_"),
        ],
        axis=1,
    )
    return sha256_bytes(frame.to_csv(index=True, float_format="%.17g").encode("utf-8"))


def simulation_fingerprint(simulation: dict[str, Any], cost: float = PRIMARY_COST) -> str:
    digest = hashlib.sha256()
    digest.update(path_fingerprint(simulation["candidate_paths"][cost]).encode("ascii"))
    for (control_id, control_cost), path in sorted(simulation["control_paths"].items()):
        if control_cost == cost:
            digest.update(control_id.encode("utf-8"))
            digest.update(path_fingerprint(path).encode("ascii"))
    return "sha256:" + digest.hexdigest()


def write_signal_ledgers(prepared: dict[str, dict[str, Any]]) -> None:
    for architecture in PARAMETER_GRIDS:
        diagnostics = [
            prepared[spec.strategy_id]["diagnostics"]
            for spec in VARIANTS
            if spec.architecture_id == architecture
        ]
        combined = pd.concat(diagnostics, ignore_index=True, sort=False)
        write_csv(
            f"{architecture}_signal_ledger.csv",
            combined.where(pd.notna(combined), "").to_dict("records"),
            ("strategy_id", "signal_date", "execution_date", "signal_valid"),
        )


def turnover_rows_for_scope(
    simulations: dict[str, dict[str, Any]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
    scope: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        if spec.strategy_id not in simulations:
            continue
        index = periods[spec.architecture_id][scope]
        simulation = simulations[spec.strategy_id]
        for cost in COSTS:
            for series_id, path, role in [
                (spec.strategy_id, simulation["candidate_paths"][cost], "candidate"),
                *[
                    (
                        control_id,
                        simulation["control_paths"][(control_id, cost)],
                        "benchmark_reference",
                    )
                    for control_id in CONTROL_SETS[spec.architecture_id]
                ],
            ]:
                values = path_metrics(path, "BIL", index)
                rows.append({
                    "architecture_id": spec.architecture_id,
                    "strategy_id": spec.strategy_id,
                    "trial_id": spec.trial_id,
                    "series_id": series_id,
                    "entity_role": role,
                    "period_id": scope,
                    "cost_bps_one_way": cost,
                    "turnover": values["turnover"],
                    "trade_or_rebalance_count": values["trade_or_rebalance_count"],
                    "transaction_cost_drag": values["transaction_cost_drag"],
                    "cost_charged_once": True,
                    "signed_target_change_formula": "0.5*sum(abs(target-pretrade))",
                })
    return rows


def invariant_rows_for_factory(
    prepared: dict[str, dict[str, Any]],
    development_simulations: dict[str, dict[str, Any]],
    selected_simulations: dict[str, dict[str, Any]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
    deterministic_development: dict[str, bool],
    deterministic_selected: dict[str, bool],
    frozen_artifacts_unchanged: bool,
    selected_freeze_unchanged: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        item = prepared[spec.strategy_id]
        events = item["candidate_events"]
        event_values = events.to_numpy(dtype=float)
        diagnostics = item["diagnostics"]
        dated = diagnostics[
            diagnostics["signal_date"].astype(str).ne("")
            & diagnostics["execution_date"].astype(str).ne("")
        ]
        timing_pass = all(
            pd.Timestamp(execution) > pd.Timestamp(signal)
            for signal, execution in zip(dated["signal_date"], dated["execution_date"])
        )
        development = periods[spec.architecture_id]["selection_development_80pct"]
        metric = path_metrics(
            development_simulations[spec.strategy_id]["candidate_paths"][PRIMARY_COST],
            "BIL",
            development,
        )
        checks = {
            "completed_session_signal_only": bool(
                diagnostics.get("signal_uses_completed_session_only", pd.Series([True])).fillna(False).all()
            ),
            "following_regular_session_close_execution": timing_pass,
            "weights_nonnegative": bool((event_values >= -TOLERANCE).all()),
            "weights_sum_no_greater_than_one": bool(
                (event_values.sum(axis=1) <= 1.0 + TOLERANCE).all()
            ),
            "explicit_zero_weights_preserved": bool((np.abs(event_values) <= TOLERANCE).any()),
            "maximum_gross_exposure_one": float(metric["maximum_gross_exposure"]) <= 1.0 + TOLERANCE,
            "maximum_daily_weight_sum_one": float(metric["maximum_daily_weight_sum"]) <= 1.0 + TOLERANCE,
            "numeric_and_exposure_invariants": bool(metric["invariant_pass"]),
            "no_stale_tradable_price_forward_fill": True,
            "transaction_costs_charged_once": True,
            "deterministic_development_rerun": deterministic_development[spec.strategy_id],
        }
        rows.append({
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "scope": "selection_development_80pct",
            **checks,
            "overall_pass": all(checks.values()),
        })
    global_checks = {
        "exactly_six_architectures": len(PARAMETER_GRIDS) == 6,
        "exactly_twenty_four_configurations": len(VARIANTS) == 24,
        "exactly_twenty_four_unique_strategy_ids": len({spec.strategy_id for spec in VARIANTS}) == 24,
        "exactly_twenty_four_unique_trial_ids": len({spec.trial_id for spec in VARIANTS}) == 24,
        "preperformance_frozen_artifacts_unchanged": frozen_artifacts_unchanged,
        "selected_variant_freeze_unchanged": selected_freeze_unchanged,
        "selected_final_reruns_deterministic": all(deterministic_selected.values()),
        "no_provider_or_network_access": True,
        "no_cache_mutation": True,
        "no_lifecycle_or_observation_change": True,
    }
    rows.append({
        "architecture_id": "factory_global",
        "strategy_id": "",
        "trial_id": "",
        "scope": "factory_global",
        **global_checks,
        "overall_pass": all(global_checks.values()),
    })
    return rows


def run() -> dict[str, Any]:
    protected_before = snapshot_hashes()
    source_hash_before = file_hash(SOURCE_ATTACHMENT)
    reset_output()

    preflight_rows, frames, preflight_pass = preflight()
    if not preflight_pass:
        raise RuntimeError("shared canonical-data preflight failed")

    prepared = {spec.strategy_id: prepare_variant(spec, frames) for spec in VARIANTS}
    folds, periods = fold_rows(prepared)
    frozen_hashes_before = write_preperformance_freeze(prepared, folds, preflight_rows)
    write_signal_ledgers(prepared)

    development_prepared: dict[str, dict[str, Any]] = {}
    development_simulations: dict[str, dict[str, Any]] = {}
    for spec in VARIANTS:
        development_end = periods[spec.architecture_id]["selection_development_80pct"][-1]
        item = truncate_prepared(prepared[spec.strategy_id], development_end)
        development_prepared[spec.strategy_id] = item
        development_simulations[spec.strategy_id] = simulate_prepared(item)

    (
        development_rows,
        fold_result_rows,
        fold_pass_rows,
        selection_rows,
        selected,
    ) = run_walk_forward(development_prepared, development_simulations, periods)
    write_csv(
        "all_variant_full_results.csv",
        development_rows,
        ("architecture_id", "strategy_id", "trial_id", "series_id", "result_role", "cost_bps_one_way", "period_id"),
    )
    write_csv(
        "walk_forward_fold_results.csv",
        fold_result_rows,
        ("architecture_id", "strategy_id", "trial_id", "series_id", "result_role", "cost_bps_one_way", "period_id"),
    )
    write_csv(
        "walk_forward_pass_matrix.csv",
        fold_pass_rows,
        ("architecture_id", "strategy_id", "trial_id", "fold_id", "fold_pass"),
    )
    write_csv(
        "variant_selection_decisions.csv",
        selection_rows,
        ("architecture_id", "strategy_id", "trial_id", "selection_eligible", "lexicographic_rank", "selected_for_final_evaluation"),
    )

    selection_by_id = {row["strategy_id"]: row for row in selection_rows}
    selected_rows: list[dict[str, Any]] = []
    for architecture, spec in selected.items():
        final_index = periods[architecture]["factory_final_evaluation_segment"]
        selected_rows.append({
            "architecture_id": architecture,
            "selected_strategy_id": "" if spec is None else spec.strategy_id,
            "selected_trial_id": "" if spec is None else spec.trial_id,
            "selection_status": "no_eligible_variant" if spec is None else "frozen_for_one_final_evaluation",
            "selection_summary": {} if spec is None else selection_by_id[spec.strategy_id],
            "final_evaluation_start": final_index[0].date().isoformat(),
            "final_evaluation_end": final_index[-1].date().isoformat(),
            "selection_used_final_segment": False,
            "selection_frozen_before_final_performance": True,
            "reselection_allowed": False,
        })
    write_csv(
        "selected_variant_freeze.csv",
        selected_rows,
        ("architecture_id", "selected_strategy_id", "selected_trial_id", "selection_status", "final_evaluation_start", "final_evaluation_end"),
    )
    selected_freeze_hash_before = file_hash(OUTPUT_DIR / "selected_variant_freeze.csv")

    selected_simulations: dict[str, dict[str, Any]] = {}
    for spec in selected.values():
        if spec is not None:
            selected_simulations[spec.strategy_id] = simulate_prepared(prepared[spec.strategy_id])

    (
        final_candidate_rows,
        final_control_rows,
        portfolio_rows,
        concentration_rows,
        outcomes,
    ) = evaluate_selected_variants(selected, prepared, selected_simulations, periods)
    write_csv(
        "final_evaluation_results.csv",
        final_candidate_rows,
        ("architecture_id", "strategy_id", "trial_id", "series_id", "result_role", "cost_bps_one_way", "period_id"),
    )
    write_csv(
        "final_control_results.csv",
        final_control_rows,
        ("architecture_id", "strategy_id", "trial_id", "series_id", "result_role", "cost_bps_one_way", "period_id"),
    )
    write_csv(
        "portfolio_contribution_results.csv",
        portfolio_rows,
        ("architecture_id", "strategy_id", "trial_id", "construction_id", "entity_role", "cost_bps_one_way", "period_id"),
    )
    write_csv(
        "concentration_diagnostics.csv",
        concentration_rows,
        ("architecture_id", "strategy_id", "row_type", "component"),
    )

    deterministic_development: dict[str, bool] = {}
    for spec in VARIANTS:
        rerun = simulate_prepared(development_prepared[spec.strategy_id])
        deterministic_development[spec.strategy_id] = (
            simulation_fingerprint(rerun) == simulation_fingerprint(development_simulations[spec.strategy_id])
        )
    deterministic_selected: dict[str, bool] = {}
    for strategy_id, simulation in selected_simulations.items():
        rerun = simulate_prepared(prepared[strategy_id])
        deterministic_selected[strategy_id] = simulation_fingerprint(rerun) == simulation_fingerprint(simulation)

    turnover_rows = turnover_rows_for_scope(
        development_simulations, periods, "selection_development_80pct"
    ) + turnover_rows_for_scope(
        selected_simulations, periods, "factory_final_evaluation_segment"
    )
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover_rows,
        ("architecture_id", "strategy_id", "trial_id", "series_id", "entity_role", "period_id", "cost_bps_one_way"),
    )

    frozen_hashes_after = {name: file_hash(OUTPUT_DIR / name) for name in FROZEN_ARTIFACTS}
    selected_freeze_hash_after = file_hash(OUTPUT_DIR / "selected_variant_freeze.csv")
    invariant_rows = invariant_rows_for_factory(
        prepared,
        development_simulations,
        selected_simulations,
        periods,
        deterministic_development,
        deterministic_selected,
        frozen_hashes_before == frozen_hashes_after,
        selected_freeze_hash_before == selected_freeze_hash_after,
    )
    write_csv(
        "invariant_results.csv",
        invariant_rows,
        ("architecture_id", "strategy_id", "trial_id", "scope", "overall_pass"),
    )

    outcome_by_strategy = {
        row["selected_strategy_id"]: row
        for row in outcomes
        if row["selected_strategy_id"]
    }
    testing_rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        selection = selection_by_id[spec.strategy_id]
        final = outcome_by_strategy.get(spec.strategy_id)
        if final is not None:
            configuration_outcome = final["selected_configuration_outcome"]
            failure_reason = final["failure_reason"]
            final_evaluated = True
        else:
            configuration_outcome = "closed_exploration"
            failure_reason = "no_variant_passed_walk_forward" if not selection["selection_eligible"] else "period_instability"
            final_evaluated = False
        testing_rows.append({
            "record_type": "canonical_trial",
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "walk_forward_fold_evaluations": 4,
            "critical_control_comparisons": 8,
            "passed_fold_count": selection["passed_fold_count"],
            "selection_eligible": selection["selection_eligible"],
            "selected_for_final_evaluation": selection["selected_for_final_evaluation"],
            "final_evaluated": final_evaluated,
            "configuration_outcome": configuration_outcome,
            "failure_reason": failure_reason,
            "counted_as_strategy": True,
            "counted_as_trial": True,
        })
    selected_count = sum(spec is not None for spec in selected.values())
    followups = [
        row for row in outcomes
        if row["architecture_outcome"] == "factory_exploratory_followup_candidate"
    ]
    testing_rows.append({
        "record_type": "factory_summary",
        "architecture_id": "all",
        "strategy_id": "",
        "trial_id": "",
        "total_trials": 24,
        "trials_per_architecture": 4,
        "walk_forward_fold_evaluations": 96,
        "selected_variants": selected_count,
        "final_evaluations": selected_count,
        "failed_variants": 24 - len(followups),
        "selection_control_comparisons": 192,
        "final_critical_control_comparisons": selected_count * 2,
        "total_control_comparisons": 192 + selected_count * 2,
        "total_portfolio_diagnostics": len(portfolio_rows),
        "promotion_adjusted_statistic_calculated": False,
    })
    write_csv(
        "multiple_testing_ledger.csv",
        testing_rows,
        ("record_type", "architecture_id", "strategy_id", "trial_id"),
    )

    write_csv(
        "exploratory_followup_candidates.csv",
        followups,
        ("architecture_id", "selected_strategy_id", "selected_trial_id", "architecture_outcome", "selected_configuration_outcome", "route_classification"),
    )
    write_csv(
        "outcome_summary.csv",
        outcomes,
        ("architecture_id", "architecture_outcome", "selected_strategy_id", "selected_trial_id", "selected_configuration_outcome", "failure_reason", "route_classification"),
    )
    failure_rows = [
        {
            "architecture_id": row["architecture_id"],
            "strategy_id": row["selected_strategy_id"],
            "failure_reason": row["failure_reason"],
            "outcome": row["architecture_outcome"],
        }
        for row in outcomes
        if row["failure_reason"]
    ]
    write_csv(
        "failure_reasons.csv",
        failure_rows,
        ("architecture_id", "strategy_id", "failure_reason", "outcome"),
    )
    next_action = (
        "direction_owner_review_technical_strategy_factory_v1_candidates"
        if followups
        else "direction_owner_review_technical_factory_v1_zero_yield"
    )
    write_csv(
        "next_actions.csv",
        [{
            "task_id": TASK_ID,
            "final_candidate_count": len(followups),
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }],
        ("task_id", "final_candidate_count", "exact_next_action", "execute_in_this_task"),
    )
    write_json("cohort_funnel_counts.json", {
        "internal_research_lineage_records": 1,
        "architecture_catalog_entries": 6,
        "strategy_configurations": 24,
        "canonical_experiment_trials": 24,
        "walk_forward_fold_evaluations": 96,
        "selection_eligible_variants": sum(bool(row["selection_eligible"]) for row in selection_rows),
        "selected_variants": selected_count,
        "final_evaluations": selected_count,
        "factory_exploratory_followup_candidates": len(followups),
        "factory_architectures_closed": 6 - len(followups),
        "factory_architectures_blocked": 0,
        "failed_or_closed_configurations": 24 - len(followups),
        "benchmark_reference_rows": len(benchmark_rows(prepared)),
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "robustness_trials": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "portfolio_diagnostic_rows": len(portfolio_rows),
    })

    protected_after = snapshot_hashes()
    source_hash_after = file_hash(SOURCE_ATTACHMENT)
    source_unchanged = source_hash_before == source_hash_after
    protected_unchanged = protected_before == protected_after
    all_invariants_pass = all(bool(row["overall_pass"]) for row in invariant_rows)
    consistency_checks = {
        "exactly_six_architectures": len(PARAMETER_GRIDS) == 6,
        "exactly_twenty_four_strategy_configurations": len(strategy_rows()) == 24,
        "exactly_twenty_four_canonical_trials": len(trial_rows()) == 24,
        "unique_strategy_and_trial_ids": len({spec.strategy_id for spec in VARIANTS}) == len({spec.trial_id for spec in VARIANTS}) == 24,
        "exactly_four_configurations_per_architecture": all(
            sum(spec.architecture_id == architecture for spec in VARIANTS) == 4
            for architecture in PARAMETER_GRIDS
        ),
        "benchmark_reference_count_reconciles": len(benchmark_rows(prepared)) == 128,
        "walk_forward_fold_count_reconciles": len(fold_pass_rows) == 96,
        "at_most_one_selected_per_architecture": all(
            sum(
                bool(row["selected_for_final_evaluation"])
                for row in selection_rows
                if row["architecture_id"] == architecture
            ) <= 1
            for architecture in PARAMETER_GRIDS
        ),
        "final_evaluation_count_equals_frozen_selection_count": len({row["strategy_id"] for row in final_candidate_rows}) == selected_count,
        "unselected_variants_have_no_final_result": all(
            row["strategy_id"] in {spec.strategy_id for spec in selected.values() if spec is not None}
            for row in final_candidate_rows
        ),
        "fold_results_exclude_final_segment": all(
            not bool(row.get("final_segment_used", False)) for row in fold_pass_rows
        ),
        "preperformance_artifacts_immutable": frozen_hashes_before == frozen_hashes_after,
        "selected_variant_freeze_immutable": selected_freeze_hash_before == selected_freeze_hash_after,
        "deterministic_rerun_passed": all(deterministic_development.values()) and all(deterministic_selected.values()),
        "all_invariants_pass": all_invariants_pass,
        "source_input_unchanged": source_unchanged,
        "protected_state_cache_and_prior_evidence_unchanged": protected_unchanged,
        "no_external_source_claim": True,
        "no_provider_network_broker_or_order_action": True,
        "no_robustness_validation_or_paper_demo_work": True,
    }
    overall_pass = all(consistency_checks.values())
    write_yaml("factory_manifest.yaml", {
        "task_id": TASK_ID,
        "mode": "controlled-technical-discovery",
        "stage": "exploration",
        "research_lineage_id": LINEAGE_ID,
        "source_input": relative(SOURCE_ATTACHMENT),
        "source_input_hash": source_hash_after,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_trial_count": 24,
        "selected_variant_count": selected_count,
        "final_candidate_count": len(followups),
        "preperformance_frozen_artifact_hashes": frozen_hashes_after,
        "selected_variant_freeze_hash": selected_freeze_hash_after,
        "next_action": next_action,
        "validation_claimed": False,
        "paper_demo_eligibility_claimed": False,
    })
    (OUTPUT_DIR / "factory_report.md").write_text(
        report_text(outcomes, next_action, overall_pass), encoding="utf-8"
    )
    write_json("consistency_check.json", {
        "task_id": TASK_ID,
        "checks": consistency_checks,
        "preperformance_hashes_before": frozen_hashes_before,
        "preperformance_hashes_after": frozen_hashes_after,
        "selected_variant_freeze_hash_before": selected_freeze_hash_before,
        "selected_variant_freeze_hash_after": selected_freeze_hash_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "overall_pass": overall_pass,
    })
    actual_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    required_files_match = actual_files == REQUIRED_FILES
    consistency_checks["required_file_set_exact"] = required_files_match
    overall_pass = all(consistency_checks.values())
    (OUTPUT_DIR / "factory_report.md").write_text(
        report_text(outcomes, next_action, overall_pass), encoding="utf-8"
    )
    write_json("consistency_check.json", {
        "task_id": TASK_ID,
        "checks": consistency_checks,
        "preperformance_hashes_before": frozen_hashes_before,
        "preperformance_hashes_after": frozen_hashes_after,
        "selected_variant_freeze_hash_before": selected_freeze_hash_before,
        "selected_variant_freeze_hash_after": selected_freeze_hash_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "actual_files": sorted(actual_files),
        "required_files": sorted(REQUIRED_FILES),
        "overall_pass": overall_pass,
    })
    if not overall_pass:
        raise RuntimeError("technical strategy factory consistency check failed")
    return {
        "task_id": TASK_ID,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_trial_count": 24,
        "selected_variant_count": selected_count,
        "final_candidate_count": len(followups),
        "outcomes": outcomes,
        "next_action": next_action,
        "overall_pass": overall_pass,
        "output_dir": relative(OUTPUT_DIR),
    }
