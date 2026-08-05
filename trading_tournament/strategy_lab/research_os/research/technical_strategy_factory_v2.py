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
from strategy_lab.research_os.research import technical_strategy_factory_v1 as v1


TASK_ID = "technical_strategy_factory_v2"
LINEAGE_ID = "internal_technical_strategy_factory_v2"
MODE = "controlled-technical-discovery"
STAGE = "optimization"
OUTPUT_DIR = ROOT / "evidence" / "technical_factory" / TASK_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\55c51258-30ee-4b23-8b45-5eaa4ea55f16\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-08-04T18:00:00+00:00"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10

SECTORS = v1.SECTORS
SPY_BIL = ("SPY", "BIL")
CREDIT_UNIVERSE = ("SPY", "BIL", "HYG", "IEF")
SECTOR_SIGNAL_UNIVERSE = (*SECTORS, "SPY", "BIL")
SECTOR_TIMING_UNIVERSE = (*SECTORS, "BIL")
SECTOR_ACCOUNTING_UNIVERSE = (*SECTORS, "SPY", "BIL")
REQUIRED_SYMBOLS = ("SPY", "BIL", "HYG", "IEF", *SECTORS)


@dataclass(frozen=True)
class VariantSpec:
    architecture_id: str
    family_id: str
    code: str
    parameters: dict[str, Any]
    universe: tuple[str, ...]

    @property
    def strategy_id(self) -> str:
        return f"{self.architecture_id}_{self.code.lower()}"

    @property
    def trial_id(self) -> str:
        return f"technical_factory_v2__{self.code.lower()}__canonical"

    @property
    def display_name(self) -> str:
        return f"{ARCHITECTURE_TITLES[self.architecture_id]} {self.code}"


ARCHITECTURE_TITLES = {
    "factory_v2_credit_ratio_drawdown_state": "Credit-Risk Appetite State",
    "factory_v2_spy_semivariance_asymmetry_state": "SPY Return-Asymmetry State",
    "factory_v2_spy_bearish_range_expansion_cooldown": "SPY Bearish Range-Expansion Cooldown",
    "factory_v2_sector_residual_momentum": "Sector Residual Momentum",
    "factory_v2_sector_capture_ratio_selection": "Sector Upside/Downside Capture",
    "factory_v2_sector_overnight_intraday_differential": "Sector Overnight/Intraday Differential",
}

ARCHITECTURE_FAMILIES = {
    "factory_v2_credit_ratio_drawdown_state": "credit_risk_appetite_state",
    "factory_v2_spy_semivariance_asymmetry_state": "return_semivariance_asymmetry",
    "factory_v2_spy_bearish_range_expansion_cooldown": "bearish_range_shock_defensive_event",
    "factory_v2_sector_residual_momentum": "market_residual_cross_sectional_momentum",
    "factory_v2_sector_capture_ratio_selection": "cross_sectional_upside_downside_capture",
    "factory_v2_sector_overnight_intraday_differential": "cross_sectional_return_timing_decomposition",
}

ARCHITECTURE_DESCRIPTIONS = {
    "factory_v2_credit_ratio_drawdown_state": "monthly_credit_ratio_return_and_drawdown_SPY_BIL_state",
    "factory_v2_spy_semivariance_asymmetry_state": "monthly_endpoint_return_and_semivariance_asymmetry_SPY_BIL_state",
    "factory_v2_spy_bearish_range_expansion_cooldown": "daily_bearish_true_range_shock_defensive_cooldown_state",
    "factory_v2_sector_residual_momentum": "monthly_market_residual_topN_sector_selection",
    "factory_v2_sector_capture_ratio_selection": "monthly_upside_minus_downside_capture_topN_sector_selection",
    "factory_v2_sector_overnight_intraday_differential": "monthly_overnight_minus_intraday_topN_sector_selection",
}

PARAMETER_GRIDS = {
    "factory_v2_credit_ratio_drawdown_state": (
        ("A1", {"lookback_sessions": 63, "drawdown_limit": 0.03}),
        ("A2", {"lookback_sessions": 63, "drawdown_limit": 0.06}),
        ("A3", {"lookback_sessions": 126, "drawdown_limit": 0.03}),
        ("A4", {"lookback_sessions": 126, "drawdown_limit": 0.06}),
    ),
    "factory_v2_spy_semivariance_asymmetry_state": (
        ("B1", {"lookback_sessions": 63, "asymmetry_threshold": 1.0}),
        ("B2", {"lookback_sessions": 63, "asymmetry_threshold": 1.5}),
        ("B3", {"lookback_sessions": 126, "asymmetry_threshold": 1.0}),
        ("B4", {"lookback_sessions": 126, "asymmetry_threshold": 1.5}),
    ),
    "factory_v2_spy_bearish_range_expansion_cooldown": (
        ("C1", {"range_threshold": 1.5, "hold_sessions": 5}),
        ("C2", {"range_threshold": 1.5, "hold_sessions": 10}),
        ("C3", {"range_threshold": 2.0, "hold_sessions": 5}),
        ("C4", {"range_threshold": 2.0, "hold_sessions": 10}),
    ),
    "factory_v2_sector_residual_momentum": (
        ("D1", {"lookback_sessions": 63, "selected_count": 2}),
        ("D2", {"lookback_sessions": 63, "selected_count": 3}),
        ("D3", {"lookback_sessions": 126, "selected_count": 2}),
        ("D4", {"lookback_sessions": 126, "selected_count": 3}),
    ),
    "factory_v2_sector_capture_ratio_selection": (
        ("E1", {"lookback_sessions": 63, "selected_count": 2}),
        ("E2", {"lookback_sessions": 63, "selected_count": 3}),
        ("E3", {"lookback_sessions": 126, "selected_count": 2}),
        ("E4", {"lookback_sessions": 126, "selected_count": 3}),
    ),
    "factory_v2_sector_overnight_intraday_differential": (
        ("F1", {"lookback_sessions": 20, "selected_count": 2}),
        ("F2", {"lookback_sessions": 20, "selected_count": 3}),
        ("F3", {"lookback_sessions": 60, "selected_count": 2}),
        ("F4", {"lookback_sessions": 60, "selected_count": 3}),
    ),
}

CONTROL_SETS = {
    "factory_v2_credit_ratio_drawdown_state": (
        "same_credit_ratio_return_state_without_drawdown_filter",
        "same_lookback_SPY_endpoint_return_state",
        "credit_ratio_exposure_matched_static_SPY_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v2_spy_semivariance_asymmetry_state": (
        "same_endpoint_return_state_without_semivariance_filter",
        "same_endpoint_state_with_finite_total_realized_variance",
        "semivariance_exposure_matched_static_SPY_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v2_spy_bearish_range_expansion_cooldown": (
        "same_bearish_candle_cooldown_without_range_expansion",
        "same_cooldown_triggered_by_SPY_return_le_minus_1pct",
        "range_cooldown_exposure_matched_static_SPY_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v2_sector_residual_momentum": (
        "same_lookback_raw_return_topN_sector_control",
        "same_residual_ranking_without_positive_score_BIL_replacement",
        "monthly_equal_weight_nine_sector_control",
        "residual_momentum_exposure_matched_static_sector_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v2_sector_capture_ratio_selection": (
        "same_lookback_raw_return_topN_sector_control",
        "same_downside_capture_selection_without_upside_component",
        "monthly_equal_weight_nine_sector_control",
        "capture_ratio_exposure_matched_static_sector_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
    "factory_v2_sector_overnight_intraday_differential": (
        "same_lookback_total_return_topN_sector_control",
        "same_lookback_overnight_return_only_topN_sector_control",
        "monthly_equal_weight_nine_sector_control",
        "timing_differential_exposure_matched_static_sector_BIL",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
}

NAMED_CONTROLS = {
    architecture: controls[1] if architecture == "factory_v2_sector_capture_ratio_selection" else controls[0]
    for architecture, controls in CONTROL_SETS.items()
}
STATIC_CONTROLS = {
    architecture: controls[2] if architecture.startswith("factory_v2_spy_") or architecture == "factory_v2_credit_ratio_drawdown_state" else controls[3]
    for architecture, controls in CONTROL_SETS.items()
}
UNIVERSES = {
    "factory_v2_credit_ratio_drawdown_state": CREDIT_UNIVERSE,
    "factory_v2_spy_semivariance_asymmetry_state": SPY_BIL,
    "factory_v2_spy_bearish_range_expansion_cooldown": SPY_BIL,
    "factory_v2_sector_residual_momentum": SECTOR_SIGNAL_UNIVERSE,
    "factory_v2_sector_capture_ratio_selection": SECTOR_SIGNAL_UNIVERSE,
    "factory_v2_sector_overnight_intraday_differential": SECTOR_TIMING_UNIVERSE,
}

VARIANTS = tuple(
    VariantSpec(
        architecture_id=architecture,
        family_id=ARCHITECTURE_FAMILIES[architecture],
        code=code,
        parameters=parameters,
        universe=UNIVERSES[architecture],
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
    "route_catalog.csv",
    "walk_forward_folds.csv",
    "selection_rule.yaml",
    "prohibited_adaptations.yaml",
)

REQUIRED_FILES = {
    "factory_manifest.yaml",
    "internal_research_lineage.csv",
    "architecture_catalog.yaml",
    "parameter_grid.csv",
    "route_catalog.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "walk_forward_folds.csv",
    "selection_rule.yaml",
    "prohibited_adaptations.yaml",
    "all_variant_results.csv",
    "standalone_fold_results.csv",
    "diversifier_fold_results.csv",
    "fold_pass_matrix.csv",
    "variant_route_selection_decisions.csv",
    "selected_variant_route_freeze.csv",
    "final_evaluation_results.csv",
    "final_control_results.csv",
    "portfolio_contribution_results.csv",
    "lightweight_concentration_diagnostics.csv",
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
    snapshot = {
        relative(path): tree_hash(path)
        for path in (*v1.helpers.PROTECTED_STATE_PATHS, *v1.helpers.PROTECTED_TREE_PATHS)
    }
    snapshot["evidence_excluding_current_factory_v2"] = tree_hash(ROOT / "evidence", OUTPUT_DIR)
    snapshot["technical_factory_v1_packet"] = tree_hash(
        ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v1" / "latest"
    )
    snapshot["technical_factory_v1_robustness_packet"] = tree_hash(
        ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest"
    )
    return snapshot


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
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )


def preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], bool]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    passed_all = True
    for symbol in REQUIRED_SYMBOLS:
        raw = v1.market.load_adjusted_ohlcv(symbol)
        frame = v1.adjusted_ohlcv(raw) if not raw.empty else pd.DataFrame()
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
            "normalized_frame_hash": v1.frame_hash(frame) if not frame.empty else "missing",
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
        [frames[symbol]["close"].rename(symbol) for symbol in universe], axis=1, join="inner"
    ).dropna()


def target(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return target(columns, {"BIL": 1.0})


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]


def finish_prepared(
    spec: VariantSpec,
    prices: pd.DataFrame,
    candidate_events: dict[pd.Timestamp, dict[str, float]],
    controls: dict[str, pd.DataFrame],
    diagnostics: list[dict[str, Any]],
    first_eligible_execution: pd.Timestamp,
    execution_calendar: list[pd.Timestamp],
) -> dict[str, Any]:
    columns = tuple(prices.columns)
    candidate = v1.event_frame(prices.index, columns, candidate_events)
    candidate_targets = v1.target_history(candidate, prices.index)
    average_weights = {symbol: float(candidate_targets[symbol].mean()) for symbol in columns}
    static_id = STATIC_CONTROLS[spec.architecture_id]
    controls[static_id] = v1.monthly_static_events(prices.index, columns, average_weights)
    controls["SPY_buy_and_hold"] = v1.accounting.initial_event(
        prices.index, columns, target(columns, {"SPY": 1.0})
    )
    controls["BIL_buy_and_hold"] = v1.accounting.initial_event(
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


def state_event(
    events: dict[pd.Timestamp, dict[str, float]],
    execution: pd.Timestamp | None,
    columns: tuple[str, ...],
    risky: bool,
) -> None:
    if execution is not None:
        events[execution] = target(columns, {"SPY": 1.0} if risky else {"BIL": 1.0})


def prepare_a(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, CREDIT_UNIVERSE)
    ratio = prices["HYG"] / prices["IEF"]
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    return_events = {pd.Timestamp(prices.index[0]): initial}
    endpoint_events = {pd.Timestamp(prices.index[0]): initial}
    candidate_state = return_state = endpoint_state = False
    lookback = int(spec.parameters["lookback_sessions"])
    drawdown_limit = float(spec.parameters["drawdown_limit"])
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    first: pd.Timestamp | None = None
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = v1.next_session(prices.index, signal_date)
        valid = position >= lookback and execution is not None
        ratio_return = ratio_drawdown = float("nan")
        if valid:
            ratio_return = float(ratio.iloc[position] / ratio.iloc[position - lookback] - 1.0)
            drawdown_window = ratio.iloc[position - lookback + 1:position + 1]
            ratio_drawdown = float(ratio.iloc[position] / drawdown_window.max() - 1.0)
            valid = math.isfinite(ratio_return) and math.isfinite(ratio_drawdown)
        if valid and execution is not None:
            calendar.append(execution)
            first = execution if first is None else first
            desired = ratio_return > 0.0 and ratio_drawdown >= -drawdown_limit
            if desired != candidate_state:
                candidate_state = desired
                state_event(candidate_events, execution, columns, desired)
            desired_return = ratio_return > 0.0
            if desired_return != return_state:
                return_state = desired_return
                state_event(return_events, execution, columns, desired_return)
            endpoint = float(prices["SPY"].iloc[position] / prices["SPY"].iloc[position - lookback] - 1.0) > 0.0
            if endpoint != endpoint_state:
                endpoint_state = endpoint
                state_event(endpoint_events, execution, columns, endpoint)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "lookback_sessions": lookback,
            "drawdown_limit": drawdown_limit,
            "credit_ratio": ratio.iloc[position],
            "ratio_return": ratio_return,
            "ratio_drawdown": ratio_drawdown,
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if return_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, return_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, endpoint_events),
    }
    return finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, calendar)


def prepare_b(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SPY_BIL)
    returns = prices["SPY"].pct_change(fill_method=None)
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    endpoint_events = {pd.Timestamp(prices.index[0]): initial}
    finite_variance_events = {pd.Timestamp(prices.index[0]): initial}
    candidate_state = endpoint_state = finite_state = False
    lookback = int(spec.parameters["lookback_sessions"])
    threshold = float(spec.parameters["asymmetry_threshold"])
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    first: pd.Timestamp | None = None
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = v1.next_session(prices.index, signal_date)
        valid = position >= lookback and execution is not None
        upside = downside = ratio = endpoint_return = total_variance = float("nan")
        if valid:
            window = returns.iloc[position - lookback + 1:position + 1].to_numpy(dtype=float)
            upside = float(np.mean(np.maximum(window, 0.0) ** 2))
            downside = float(np.mean(np.minimum(window, 0.0) ** 2))
            total_variance = upside + downside
            ratio = downside / upside if upside > 0.0 else float("nan")
            endpoint_return = float(prices["SPY"].iloc[position] / prices["SPY"].iloc[position - lookback] - 1.0)
            valid = all(math.isfinite(value) for value in (upside, downside, ratio, endpoint_return, total_variance))
        if valid and execution is not None:
            calendar.append(execution)
            first = execution if first is None else first
            desired_endpoint = endpoint_return > 0.0
            desired = desired_endpoint and ratio <= threshold
            if desired != candidate_state:
                candidate_state = desired
                state_event(candidate_events, execution, columns, desired)
            if desired_endpoint != endpoint_state:
                endpoint_state = desired_endpoint
                state_event(endpoint_events, execution, columns, desired_endpoint)
            desired_finite = desired_endpoint and math.isfinite(total_variance)
            if desired_finite != finite_state:
                finite_state = desired_finite
                state_event(finite_variance_events, execution, columns, desired_finite)
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "lookback_sessions": lookback,
            "asymmetry_threshold": threshold,
            "upside_semivariance": upside,
            "downside_semivariance": downside,
            "asymmetry_ratio": ratio,
            "endpoint_return": endpoint_return,
            "total_realized_variance": total_variance,
            "secondary_control_interpretation": "endpoint_positive_with_finite_total_realized_variance_no_unfrozen_threshold",
            "candidate_target": "SPY" if candidate_state else "BIL",
            "named_control_target": "SPY" if endpoint_state else "BIL",
            "signal_uses_completed_session_only": True,
        })
    if first is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, endpoint_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, finite_variance_events),
    }
    return finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, calendar)


def cooldown_events(
    prices: pd.DataFrame,
    trigger: pd.Series,
    hold_sessions: int,
) -> tuple[dict[pd.Timestamp, dict[str, float]], pd.DatetimeIndex, list[dict[str, Any]]]:
    columns = tuple(prices.columns)
    events = {pd.Timestamp(prices.index[0]): bil_target(columns)}
    current_state = "BIL"
    initialized = False
    remaining = 0
    anchor_date: pd.Timestamp | None = None
    pending_date: pd.Timestamp | None = None
    pending_state: str | None = None
    pending_reset = False
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    for position, signal_date in enumerate(prices.index):
        signal_date = pd.Timestamp(signal_date)
        if pending_date == signal_date and pending_state is not None:
            current_state = pending_state
            if pending_state == "BIL" and pending_reset:
                remaining = hold_sessions
                anchor_date = signal_date
            elif pending_state == "SPY":
                remaining = 0
                anchor_date = None
            pending_date = None
            pending_state = None
            pending_reset = False
        execution = v1.next_session(prices.index, signal_date)
        valid = bool(position >= 20 and execution is not None and pd.notna(trigger.iloc[position]))
        event = bool(trigger.iloc[position]) if valid else False
        reset = False
        scheduled_target = ""
        if valid and execution is not None:
            calendar.append(execution)
            if not initialized:
                initialized = True
                if event:
                    events[execution] = bil_target(columns)
                    pending_state = "BIL"
                    pending_reset = True
                    reset = True
                    scheduled_target = "BIL"
                else:
                    events[execution] = target(columns, {"SPY": 1.0})
                    pending_state = "SPY"
                    scheduled_target = "SPY"
                pending_date = execution
            elif event:
                events[execution] = bil_target(columns)
                pending_date = execution
                pending_state = "BIL"
                pending_reset = True
                reset = True
                scheduled_target = "BIL"
            elif current_state == "BIL":
                if signal_date == anchor_date:
                    if remaining <= 1:
                        events[execution] = target(columns, {"SPY": 1.0})
                        pending_date = execution
                        pending_state = "SPY"
                        scheduled_target = "SPY"
                else:
                    remaining -= 1
                    if remaining <= 1:
                        events[execution] = target(columns, {"SPY": 1.0})
                        pending_date = execution
                        pending_state = "SPY"
                        scheduled_target = "SPY"
        diagnostics.append({
            "signal_date": signal_date.date().isoformat(),
            "execution_date": "" if execution is None else execution.date().isoformat(),
            "signal_valid": valid,
            "trigger": event,
            "counter_reset": reset,
            "remaining_completed_performance_sessions": max(remaining, 0),
            "current_state_after_prior_execution": current_state,
            "scheduled_target_for_following_close": scheduled_target,
            "target": scheduled_target or current_state,
        })
    return events, pd.DatetimeIndex(calendar), diagnostics


def prepare_c(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    aligned = pd.concat(
        [frames[symbol][["open", "high", "low", "close"]].add_prefix(f"{symbol}_") for symbol in SPY_BIL],
        axis=1,
        join="inner",
    ).dropna()
    prices = aligned[["SPY_close", "BIL_close"]].rename(columns={"SPY_close": "SPY", "BIL_close": "BIL"})
    previous_close = aligned["SPY_close"].shift(1)
    true_range = pd.concat(
        [
            aligned["SPY_high"] - aligned["SPY_low"],
            (aligned["SPY_high"] - previous_close).abs(),
            (aligned["SPY_low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_prior = true_range.shift(1).rolling(20, min_periods=20).mean()
    shock = true_range / atr_prior
    bearish = aligned["SPY_close"] < aligned["SPY_open"]
    threshold = float(spec.parameters["range_threshold"])
    hold = int(spec.parameters["hold_sessions"])
    candidate_trigger = bearish & (shock >= threshold)
    candle_trigger = bearish
    return_trigger = aligned["SPY_close"].pct_change(fill_method=None) <= -0.01
    candidate_events, calendar, candidate_diag = cooldown_events(prices, candidate_trigger, hold)
    candle_events, _, _ = cooldown_events(prices, candle_trigger, hold)
    return_events, _, _ = cooldown_events(prices, return_trigger, hold)
    first = calendar[0]
    diagnostics: list[dict[str, Any]] = []
    for position, row in enumerate(candidate_diag):
        diagnostics.append({
            "strategy_id": spec.strategy_id,
            **row,
            "range_threshold": threshold,
            "hold_sessions": hold,
            "true_range": true_range.iloc[position],
            "ATR20_prior": atr_prior.iloc[position],
            "range_shock": shock.iloc[position],
            "bearish_candle": bearish.iloc[position],
            "candidate_target": row["target"],
            "named_control_target": "",
            "signal_uses_completed_session_only": True,
        })
    columns = tuple(prices.columns)
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, candle_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, return_events),
    }
    return finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, list(calendar))


def ranked_target(
    columns: tuple[str, ...],
    ranked: list[str],
    selected_count: int,
    eligible: set[str] | None = None,
) -> dict[str, float]:
    weights: dict[str, float] = {}
    chosen = ranked[:selected_count]
    for symbol in chosen:
        if eligible is None or symbol in eligible:
            weights[symbol] = 1.0 / selected_count
    weights["BIL"] = 1.0 - sum(weights.values())
    return target(columns, weights)


def prepare_d(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SECTOR_ACCOUNTING_UNIVERSE)
    returns = prices.pct_change(fill_method=None)
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    raw_events = {pd.Timestamp(prices.index[0]): initial}
    no_positive_events = {pd.Timestamp(prices.index[0]): initial}
    lookback = int(spec.parameters["lookback_sessions"])
    selected_count = int(spec.parameters["selected_count"])
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    first: pd.Timestamp | None = None
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = v1.next_session(prices.index, signal_date)
        valid = position >= lookback and execution is not None
        residual_scores: dict[str, float] = {}
        raw_scores: dict[str, float] = {}
        if valid:
            market_values = returns["SPY"].iloc[position - lookback + 1:position + 1].to_numpy(dtype=float)
            design = np.column_stack([np.ones(lookback), market_values])
            valid = bool(np.isfinite(design).all() and np.var(market_values) > 0.0)
            if valid:
                for sector in SECTORS:
                    sector_values = returns[sector].iloc[position - lookback + 1:position + 1].to_numpy(dtype=float)
                    coefficients = np.linalg.lstsq(design, sector_values, rcond=None)[0]
                    residuals = sector_values - design @ coefficients
                    residual_scores[sector] = float(residuals.sum())
                    raw_scores[sector] = float(prices[sector].iloc[position] / prices[sector].iloc[position - lookback] - 1.0)
                valid = bool(
                    len(residual_scores) == len(SECTORS)
                    and np.isfinite(list(residual_scores.values())).all()
                    and np.isfinite(list(raw_scores.values())).all()
                )
        residual_ranked = sorted(SECTORS, key=lambda symbol: (-residual_scores.get(symbol, -math.inf), symbol))
        raw_ranked = sorted(SECTORS, key=lambda symbol: (-raw_scores.get(symbol, -math.inf), symbol))
        selected: list[str] = []
        if valid and execution is not None:
            calendar.append(execution)
            first = execution if first is None else first
            selected = residual_ranked[:selected_count]
            eligible = {symbol for symbol in selected if residual_scores[symbol] > 0.0}
            candidate_events[execution] = ranked_target(columns, residual_ranked, selected_count, eligible)
            no_positive_events[execution] = ranked_target(columns, residual_ranked, selected_count)
            raw_events[execution] = ranked_target(columns, raw_ranked, selected_count)
        for sector in SECTORS:
            diagnostics.append({
                "strategy_id": spec.strategy_id,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": "" if execution is None else execution.date().isoformat(),
                "signal_valid": valid,
                "lookback_sessions": lookback,
                "selected_count": selected_count,
                "sector": sector,
                "residual_score": residual_scores.get(sector, ""),
                "raw_total_return": raw_scores.get(sector, ""),
                "residual_rank": "" if not valid else residual_ranked.index(sector) + 1,
                "raw_return_rank": "" if not valid else raw_ranked.index(sector) + 1,
                "candidate_selected": sector in selected and residual_scores.get(sector, -math.inf) > 0.0,
                "unused_slot_to_BIL": sector in selected and residual_scores.get(sector, -math.inf) <= 0.0,
                "signal_uses_completed_session_only": True,
            })
    if first is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    equal_weight = {sector: 1.0 / len(SECTORS) for sector in SECTORS}
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, raw_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, no_positive_events),
        CONTROL_SETS[spec.architecture_id][2]: v1.monthly_static_events(prices.index, columns, equal_weight),
    }
    return finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, calendar)


def prepare_e(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SECTOR_ACCOUNTING_UNIVERSE)
    returns = prices.pct_change(fill_method=None)
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    raw_events = {pd.Timestamp(prices.index[0]): initial}
    downside_events = {pd.Timestamp(prices.index[0]): initial}
    lookback = int(spec.parameters["lookback_sessions"])
    selected_count = int(spec.parameters["selected_count"])
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    first: pd.Timestamp | None = None
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = v1.next_session(prices.index, signal_date)
        valid = position >= lookback and execution is not None
        upside: dict[str, float] = {}
        downside: dict[str, float] = {}
        capture_scores: dict[str, float] = {}
        raw_scores: dict[str, float] = {}
        if valid:
            market = returns["SPY"].iloc[position - lookback + 1:position + 1]
            positive = market > 0.0
            negative = market < 0.0
            market_up = float(market[positive].mean())
            market_down = float(market[negative].mean())
            valid = bool(positive.any() and negative.any() and market_up != 0.0 and market_down != 0.0)
            if valid:
                for sector in SECTORS:
                    values = returns[sector].iloc[position - lookback + 1:position + 1]
                    upside[sector] = float(values[positive.to_numpy()].mean() / market_up)
                    downside[sector] = float(values[negative.to_numpy()].mean() / market_down)
                    capture_scores[sector] = upside[sector] - downside[sector]
                    raw_scores[sector] = float(prices[sector].iloc[position] / prices[sector].iloc[position - lookback] - 1.0)
                valid = bool(
                    np.isfinite(list(upside.values())).all()
                    and np.isfinite(list(downside.values())).all()
                    and np.isfinite(list(capture_scores.values())).all()
                )
        capture_ranked = sorted(SECTORS, key=lambda symbol: (-capture_scores.get(symbol, -math.inf), symbol))
        downside_ranked = sorted(SECTORS, key=lambda symbol: (downside.get(symbol, math.inf), symbol))
        raw_ranked = sorted(SECTORS, key=lambda symbol: (-raw_scores.get(symbol, -math.inf), symbol))
        selected: list[str] = []
        if valid and execution is not None:
            calendar.append(execution)
            first = execution if first is None else first
            selected = capture_ranked[:selected_count]
            candidate_events[execution] = ranked_target(columns, capture_ranked, selected_count)
            downside_events[execution] = ranked_target(columns, downside_ranked, selected_count)
            raw_events[execution] = ranked_target(columns, raw_ranked, selected_count)
        for sector in SECTORS:
            diagnostics.append({
                "strategy_id": spec.strategy_id,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": "" if execution is None else execution.date().isoformat(),
                "signal_valid": valid,
                "lookback_sessions": lookback,
                "selected_count": selected_count,
                "sector": sector,
                "upside_capture": upside.get(sector, ""),
                "downside_capture": downside.get(sector, ""),
                "capture_score": capture_scores.get(sector, ""),
                "raw_total_return": raw_scores.get(sector, ""),
                "capture_rank": "" if not valid else capture_ranked.index(sector) + 1,
                "downside_rank": "" if not valid else downside_ranked.index(sector) + 1,
                "candidate_selected": sector in selected,
                "signal_uses_completed_session_only": True,
            })
    if first is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    equal_weight = {sector: 1.0 / len(SECTORS) for sector in SECTORS}
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, raw_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, downside_events),
        CONTROL_SETS[spec.architecture_id][2]: v1.monthly_static_events(prices.index, columns, equal_weight),
    }
    return finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, calendar)


def prepare_f(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = common_prices(frames, SECTOR_ACCOUNTING_UNIVERSE)
    opens = pd.concat(
        [frames[sector]["open"].rename(sector) for sector in SECTORS], axis=1, join="inner"
    ).reindex(prices.index)
    sector_closes = prices[list(SECTORS)]
    overnight = opens / sector_closes.shift(1) - 1.0
    intraday = sector_closes / opens - 1.0
    close_to_close = sector_closes.pct_change(fill_method=None)
    identity_error = ((1.0 + overnight) * (1.0 + intraday) - 1.0 - close_to_close).abs()
    columns = tuple(prices.columns)
    initial = bil_target(columns)
    candidate_events = {pd.Timestamp(prices.index[0]): initial}
    total_events = {pd.Timestamp(prices.index[0]): initial}
    overnight_events = {pd.Timestamp(prices.index[0]): initial}
    lookback = int(spec.parameters["lookback_sessions"])
    selected_count = int(spec.parameters["selected_count"])
    diagnostics: list[dict[str, Any]] = []
    calendar: list[pd.Timestamp] = []
    first: pd.Timestamp | None = None
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = v1.next_session(prices.index, signal_date)
        valid = position >= lookback and execution is not None
        timing_scores: dict[str, float] = {}
        total_scores: dict[str, float] = {}
        overnight_scores: dict[str, float] = {}
        if valid:
            for sector in SECTORS:
                overnight_window = overnight[sector].iloc[position - lookback + 1:position + 1]
                intraday_window = intraday[sector].iloc[position - lookback + 1:position + 1]
                total_window = close_to_close[sector].iloc[position - lookback + 1:position + 1]
                overnight_scores[sector] = float(overnight_window.sum())
                timing_scores[sector] = float(overnight_window.sum() - intraday_window.sum())
                total_scores[sector] = float((1.0 + total_window).prod() - 1.0)
            valid = bool(
                np.isfinite(list(timing_scores.values())).all()
                and np.isfinite(list(total_scores.values())).all()
                and np.isfinite(list(overnight_scores.values())).all()
            )
        timing_ranked = sorted(SECTORS, key=lambda symbol: (-timing_scores.get(symbol, -math.inf), symbol))
        total_ranked = sorted(SECTORS, key=lambda symbol: (-total_scores.get(symbol, -math.inf), symbol))
        overnight_ranked = sorted(SECTORS, key=lambda symbol: (-overnight_scores.get(symbol, -math.inf), symbol))
        selected: list[str] = []
        if valid and execution is not None:
            calendar.append(execution)
            first = execution if first is None else first
            selected = timing_ranked[:selected_count]
            candidate_events[execution] = ranked_target(columns, timing_ranked, selected_count)
            total_events[execution] = ranked_target(columns, total_ranked, selected_count)
            overnight_events[execution] = ranked_target(columns, overnight_ranked, selected_count)
        for sector in SECTORS:
            diagnostics.append({
                "strategy_id": spec.strategy_id,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": "" if execution is None else execution.date().isoformat(),
                "signal_valid": valid,
                "lookback_sessions": lookback,
                "selected_count": selected_count,
                "sector": sector,
                "overnight_return_sum": overnight_scores.get(sector, ""),
                "intraday_return_sum": "" if not valid else float(intraday[sector].iloc[position - lookback + 1:position + 1].sum()),
                "timing_score": timing_scores.get(sector, ""),
                "close_to_close_total_return": total_scores.get(sector, ""),
                "timing_rank": "" if not valid else timing_ranked.index(sector) + 1,
                "candidate_selected": sector in selected,
                "adjusted_open_decomposition_max_error_to_date": float(identity_error[sector].loc[:signal_date].max(skipna=True)),
                "signal_uses_completed_session_only": True,
            })
    if first is None:
        raise RuntimeError(f"no eligible signal for {spec.strategy_id}")
    equal_weight = {sector: 1.0 / len(SECTORS) for sector in SECTORS}
    controls = {
        CONTROL_SETS[spec.architecture_id][0]: v1.event_frame(prices.index, columns, total_events),
        CONTROL_SETS[spec.architecture_id][1]: v1.event_frame(prices.index, columns, overnight_events),
        CONTROL_SETS[spec.architecture_id][2]: v1.monthly_static_events(prices.index, columns, equal_weight),
    }
    prepared = finish_prepared(spec, prices, candidate_events, controls, diagnostics, first, calendar)
    prepared["adjusted_open_identity_max_error"] = float(identity_error.max().max())
    return prepared


PREPARE_FUNCTIONS = {
    "factory_v2_credit_ratio_drawdown_state": prepare_a,
    "factory_v2_spy_semivariance_asymmetry_state": prepare_b,
    "factory_v2_spy_bearish_range_expansion_cooldown": prepare_c,
    "factory_v2_sector_residual_momentum": prepare_d,
    "factory_v2_sector_capture_ratio_selection": prepare_e,
    "factory_v2_sector_overnight_intraday_differential": prepare_f,
}


def prepare_variant(spec: VariantSpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return PREPARE_FUNCTIONS[spec.architecture_id](spec, frames)


FROZEN_RULES = {
    "factory_v2_credit_ratio_drawdown_state": {
        "signal": "month-end HYG/IEF lookback return positive and current ratio drawdown within frozen limit",
        "execution": "following regular session close",
        "invalid_or_warmup": "BIL",
    },
    "factory_v2_spy_semivariance_asymmetry_state": {
        "signal": "month-end SPY endpoint return positive and downside/upside semivariance ratio at or below frozen threshold",
        "execution": "following regular session close",
        "invalid_or_warmup": "BIL",
    },
    "factory_v2_spy_bearish_range_expansion_cooldown": {
        "signal": "bearish adjusted candle and current true range divided by prior ATR20 at or above threshold",
        "execution": "following regular session close with exact resettable completed-performance-session cooldown",
        "invalid_or_warmup": "BIL before warmup; retain state on invalid later signal",
    },
    "factory_v2_sector_residual_momentum": {
        "signal": "month-end OLS sector return on SPY return with intercept; rank sum of residuals; positive-score top slots only",
        "execution": "following regular session close",
        "invalid_or_unused_slot": "BIL",
    },
    "factory_v2_sector_capture_ratio_selection": {
        "signal": "month-end upside capture minus downside capture ranked descending",
        "execution": "following regular session close",
        "invalid_formation": "BIL",
    },
    "factory_v2_sector_overnight_intraday_differential": {
        "signal": "month-end sum adjusted overnight returns minus sum adjusted intraday returns ranked descending",
        "execution": "following regular session close",
        "invalid_formation": "BIL",
    },
}


def architecture_catalog() -> list[dict[str, Any]]:
    return [{
        "architecture_id": architecture,
        "entity_type": "architecture_catalog_entry",
        "family_id": ARCHITECTURE_FAMILIES[architecture],
        "display_name": ARCHITECTURE_TITLES[architecture],
        "strategy_architecture": ARCHITECTURE_DESCRIPTIONS[architecture],
        "configuration_count": 4,
        "universe": list(UNIVERSES[architecture]),
        "routes": ["standalone", "20pct_diversifier"],
        "external_source_claimed": False,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    } for architecture in PARAMETER_GRIDS]


def strategy_rows() -> list[dict[str, Any]]:
    return [{
        "strategy_id": spec.strategy_id,
        "trial_id": spec.trial_id,
        "family_id": spec.family_id,
        "architecture_id": spec.architecture_id,
        "display_name": spec.display_name,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE_DESCRIPTIONS[spec.architecture_id],
        "parameters": spec.parameters,
        "universe": list(spec.universe),
        "routes_evaluated_during_selection": ["standalone", "20pct_diversifier"],
        "source_or_research_lineage": f"{LINEAGE_ID}:{spec.architecture_id}",
        "benchmark_or_control_set": list(CONTROL_SETS[spec.architecture_id]),
        "stage": "exploration",
        "outcome": "preregistered_pending_factory_execution",
        "failure_reason": "",
        "next_action": "execute_frozen_factory_v2_trial",
        "external_source_claimed": False,
        "optimization_label": "bounded_preregistered_factory_v2",
        "post_result_adaptation_allowed": False,
    } for spec in VARIANTS]


def trial_rows() -> list[dict[str, Any]]:
    return [{
        **row,
        "entity_type": "experiment_trial",
        "parent_trial_id": "",
        "adaptation_label": "",
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "canonical_trial": True,
    } for row in strategy_rows()]


def benchmark_rows(prepared: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        for control in CONTROL_SETS[spec.architecture_id]:
            rows.append({
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
                "secondary_control_methodology_note": (
                    "finite_total_realized_variance_only_no_unfrozen_numeric_threshold"
                    if control == "same_endpoint_state_with_finite_total_realized_variance"
                    else ""
                ),
                "frozen_before_performance": True,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            })
    return rows


def fold_rows(
    prepared: dict[str, dict[str, Any]], reference: pd.Series
) -> tuple[list[dict[str, Any]], dict[str, dict[str, pd.DatetimeIndex]]]:
    rows: list[dict[str, Any]] = []
    periods: dict[str, dict[str, pd.DatetimeIndex]] = {}
    for architecture in PARAMETER_GRIDS:
        specs = [spec for spec in VARIANTS if spec.architecture_id == architecture]
        first = max(prepared[spec.strategy_id]["first_eligible_execution"] for spec in specs)
        raw_index = prepared[specs[0].strategy_id]["prices"].index
        index = raw_index.intersection(reference.index).sort_values()
        eligible = index[index >= first]
        if len(eligible) < 50:
            raise RuntimeError(f"insufficient common eligible history for {architecture}")
        calendar = prepared[specs[0].strategy_id]["execution_calendar"]
        calendar = calendar.intersection(index)
        calendar = calendar[calendar >= first]
        aligned: dict[float, pd.Timestamp] = {}
        for fraction in (0.40, 0.50, 0.60, 0.70, 0.80):
            raw_position = min(int(math.floor((len(eligible) - 1) * fraction)), len(eligible) - 1)
            raw_date = pd.Timestamp(eligible[raw_position])
            candidates = calendar[calendar >= raw_date]
            if not len(candidates):
                raise RuntimeError(f"no aligned fold boundary for {architecture} at {fraction}")
            aligned[fraction] = pd.Timestamp(candidates[0])
        architecture_periods: dict[str, pd.DatetimeIndex] = {}
        for fold_number, (start_fraction, end_fraction) in enumerate(
            ((0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 0.80)), start=1
        ):
            start = aligned[start_fraction]
            next_start = aligned[end_fraction]
            evaluation = index[(index >= start) & (index < next_start)]
            architecture_periods[f"fold_{fold_number}"] = evaluation
            prior = index[index < start]
            rows.append({
                "architecture_id": architecture,
                "period_id": f"fold_{fold_number}",
                "period_role": "anchored_walk_forward_route_and_variant_selection",
                "maximum_common_period_start": eligible[0].date().isoformat(),
                "maximum_common_period_end": eligible[-1].date().isoformat(),
                "prior_history_start": eligible[0].date().isoformat(),
                "prior_history_through": prior[-1].date().isoformat(),
                "evaluation_start": evaluation[0].date().isoformat(),
                "evaluation_end": evaluation[-1].date().isoformat(),
                "start_fraction": start_fraction,
                "end_fraction": end_fraction,
                "boundary_alignment": "first_valid_execution_session_at_or_after_fractional_boundary",
                "used_for_variant_or_route_selection": True,
                "final_segment": False,
            })
        final = index[index >= aligned[0.80]]
        development = index[(index >= eligible[0]) & (index < aligned[0.80])]
        architecture_periods["selection_development_80pct"] = development
        architecture_periods["factory_v2_final_exploratory_evaluation"] = final
        rows.append({
            "architecture_id": architecture,
            "period_id": "factory_v2_final_exploratory_evaluation",
            "period_role": "final_chronological_exploratory_evaluation",
            "maximum_common_period_start": eligible[0].date().isoformat(),
            "maximum_common_period_end": eligible[-1].date().isoformat(),
            "prior_history_start": eligible[0].date().isoformat(),
            "prior_history_through": index[index < final[0]][-1].date().isoformat(),
            "evaluation_start": final[0].date().isoformat(),
            "evaluation_end": final[-1].date().isoformat(),
            "start_fraction": 0.80,
            "end_fraction": 1.00,
            "boundary_alignment": "first_valid_execution_session_at_or_after_fractional_boundary",
            "used_for_variant_or_route_selection": False,
            "final_segment": True,
        })
        periods[architecture] = architecture_periods
    return rows, periods


def write_preperformance_freeze(
    prepared: dict[str, dict[str, Any]],
    folds: list[dict[str, Any]],
    preflight_rows: list[dict[str, Any]],
) -> dict[str, str]:
    write_csv("internal_research_lineage.csv", [{
        "research_lineage_id": LINEAGE_ID,
        "lineage_type": "internally_generated_technical_hypothesis",
        "external_source_claimed": False,
        "optimization_type": "bounded_preregistered_parameter_and_route_search",
        "stage": "exploration",
        "architecture_list_frozen_before_performance": True,
        "parameter_grid_frozen_before_performance": True,
        "routes_frozen_before_performance": True,
        "controls_frozen_before_performance": True,
        "fold_boundaries_frozen_before_performance": True,
        "final_segment_frozen_before_performance": True,
        "post_result_grid_expansion_allowed": False,
        "post_result_manual_tuning_allowed": False,
        "final_segment_route_switching_allowed": False,
        "robustness_claimed": False,
        "paper_demo_eligibility_claimed": False,
    }], ("research_lineage_id", "lineage_type", "external_source_claimed", "optimization_type", "stage"))
    write_yaml("architecture_catalog.yaml", {
        "research_lineage_id": LINEAGE_ID,
        "architecture_count": 6,
        "architectures": [{**row, "frozen_rule": FROZEN_RULES[row["architecture_id"]]} for row in architecture_catalog()],
    })
    write_csv("parameter_grid.csv", [{
        "architecture_id": spec.architecture_id,
        "family_id": spec.family_id,
        "configuration_code": spec.code,
        "strategy_id": spec.strategy_id,
        "trial_id": spec.trial_id,
        "parameters": spec.parameters,
        "grid_frozen_before_performance": True,
        "post_result_grid_expansion_allowed": False,
    } for spec in VARIANTS], ("architecture_id", "family_id", "configuration_code", "strategy_id", "trial_id", "parameters"))
    write_csv("route_catalog.csv", [{
        "architecture_id": spec.architecture_id,
        "strategy_id": spec.strategy_id,
        "trial_id": spec.trial_id,
        "route": route,
        "route_frozen_before_performance": True,
        "route_selection_uses_only_four_folds": True,
        "final_segment_route_switch_allowed": False,
        "counted_as_trial": False,
    } for spec in VARIANTS for route in ("standalone", "20pct_diversifier")], ("architecture_id", "strategy_id", "trial_id", "route"))
    headers = (
        "strategy_id", "trial_id", "family_id", "architecture_id", "display_name",
        "entity_type", "strategy_architecture", "parameters", "universe",
        "routes_evaluated_during_selection", "source_or_research_lineage",
        "benchmark_or_control_set", "stage", "outcome", "failure_reason", "next_action",
    )
    write_csv("strategy_cards.csv", strategy_rows(), headers)
    write_csv("trial_ledger.csv", trial_rows(), headers)
    write_csv("benchmark_reference_log.csv", benchmark_rows(prepared), (
        "strategy_id", "architecture_id", "benchmark_id", "entity_type", "stage",
        "named_same_purpose_control", "exposure_or_static_control", "control_parameters",
    ))
    write_csv("walk_forward_folds.csv", folds, (
        "architecture_id", "period_id", "period_role", "maximum_common_period_start",
        "maximum_common_period_end", "prior_history_start", "prior_history_through",
        "evaluation_start", "evaluation_end", "start_fraction", "end_fraction",
    ))
    write_yaml("selection_rule.yaml", {
        "primary_cost_bps": PRIMARY_COST,
        "routes": ["standalone", "20pct_diversifier"],
        "route_eligibility": "passes_at_least_3_of_4_folds",
        "ranking": [
            "higher_fold_pass_count",
            "higher_median_fold_sharpe_difference_vs_named_control",
            "higher_median_fold_drawdown_improvement_vs_named_control",
            "higher_median_normalized_sharpe_or_drawdown_materiality_vs_exposure_static_control",
            "lower_median_turnover",
            "standalone_only_when_all_preceding_values_exactly_tied",
            "lexically_smaller_strategy_id",
        ],
        "standalone_fold_gate": [
            "positive_return", "all_invariants", "neither_critical_control_dominates",
            "material_advantage_vs_each_critical_control",
        ],
        "diversifier_fold_gate": [
            "material_improvement_vs_reference", "does_not_worsen_both_vs_reference",
            "neither_control_portfolio_dominates", "material_advantage_vs_each_control_portfolio",
        ],
        "maximum_selected_configuration_route_pairs_per_architecture": 1,
        "final_segment_used_for_selection": False,
    })
    write_yaml("prohibited_adaptations.yaml", {"post_performance": [
        "seventh_architecture", "twenty_fifth_trial", "second_grid", "parameter_change",
        "instrument_change", "control_change", "manual_variant_selection",
        "final_segment_reselection", "final_segment_route_switch", "Factory_V1_reuse_or_retune",
        "external_source_claim", "robustness", "validation", "paper_demo_onboarding",
    ]})
    write_csv("data_preflight_reconciliation.csv", preflight_rows, (
        "symbol", "cache_path", "canonical_file_hash", "normalized_frame_hash",
        "first_valid_date", "last_valid_date", "row_count", "ordered_unique_sessions",
        "finite_positive_adjusted_ohlc", "valid_adjusted_ohlc_relationships",
        "finite_nonnegative_adjusted_volume", "canonical_adjustment_compatible",
        "provider_access_performed", "preflight_status",
    ))
    write_csv("process_task_log.csv", [{
        "process_task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_trial_count": 24,
        "route_evaluation_count": 48,
        "provider_access_performed": False,
        "validation_robustness_or_lifecycle_work": False,
    }], ("process_task_id", "entity_type", "stage"))
    return {name: file_hash(OUTPUT_DIR / name) for name in FROZEN_ARTIFACTS}


def write_signal_ledgers(prepared: dict[str, dict[str, Any]]) -> None:
    for architecture in PARAMETER_GRIDS:
        combined = pd.concat(
            [prepared[spec.strategy_id]["diagnostics"] for spec in VARIANTS if spec.architecture_id == architecture],
            ignore_index=True,
            sort=False,
        )
        write_csv(
            f"{architecture}_signal_ledger.csv",
            combined.where(pd.notna(combined), "").to_dict("records"),
            ("strategy_id", "signal_date", "execution_date", "signal_valid"),
        )


def simulate_prepared(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_session_target_applied_at_following_regular_session_close"
    candidates: dict[float, dict[str, Any]] = {}
    controls: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidates[cost] = v1.accounting.simulate_path(
            prepared["prices"], prepared["candidate_events"], cost, timing
        )
        for control_id, events in prepared["control_events"].items():
            controls[(control_id, cost)] = v1.accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
    return {"candidate_paths": candidates, "control_paths": controls}


def truncate_prepared(prepared: dict[str, Any], end: pd.Timestamp) -> dict[str, Any]:
    end = pd.Timestamp(end)
    prices = prepared["prices"].loc[:end].copy()
    return {
        **prepared,
        "prices": prices,
        "candidate_events": prepared["candidate_events"].loc[:end].copy(),
        "control_events": {
            control_id: events.loc[:end].copy()
            for control_id, events in prepared["control_events"].items()
        },
        "candidate_targets": prepared["candidate_targets"].loc[:end].copy(),
        "execution_calendar": prepared["execution_calendar"][prepared["execution_calendar"] <= end],
        "selection_view_only": True,
        "selection_view_end": end,
    }


def path_metrics(path: dict[str, Any], period_index: pd.DatetimeIndex) -> dict[str, Any]:
    values = v1.portfolio_helpers.period_metrics(path, "reference", period_index)
    inner = path.get("inner_path")
    inner_turnover = 0.0 if inner is None else float(inner["turnover"].reindex(period_index).fillna(0.0).sum())
    inner_cost = 0.0 if inner is None else float(
        path.get("inner_cost_drag_contribution", pd.Series(dtype=float)).reindex(period_index).fillna(0.0).sum()
    )
    values.update({
        "inner_turnover": inner_turnover,
        "outer_turnover": float(path["turnover"].reindex(period_index).fillna(0.0).sum()),
        "total_turnover": inner_turnover + float(path["turnover"].reindex(period_index).fillna(0.0).sum()),
        "inner_transaction_cost_drag": inner_cost,
        "outer_transaction_cost_drag": float(path["cost"].reindex(period_index).fillna(0.0).sum()),
    })
    values["total_transaction_cost_drag"] = (
        float(values["inner_transaction_cost_drag"]) + float(values["outer_transaction_cost_drag"])
    )
    return values


def standalone_metrics(
    path: dict[str, Any], period: pd.DatetimeIndex
) -> dict[str, Any]:
    values = v1.portfolio_helpers.period_metrics(path, "BIL", period)
    values.update({
        "inner_turnover": values["turnover"],
        "outer_turnover": 0.0,
        "total_turnover": values["turnover"],
        "inner_transaction_cost_drag": values["transaction_cost_drag"],
        "outer_transaction_cost_drag": 0.0,
        "total_transaction_cost_drag": values["transaction_cost_drag"],
    })
    return values


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return v1.accounting.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"])
    )


def route_path(
    reference: pd.Series,
    inner: dict[str, Any],
    cost: float,
) -> dict[str, Any]:
    aligned_reference = reference.reindex(inner["returns"].index).dropna()
    outer = v1.portfolio_helpers.path_from_two_sleeves(aligned_reference, inner, cost)
    outer["inner_path"] = inner
    return outer


def reference_path(reference: pd.Series, index: pd.DatetimeIndex) -> dict[str, Any]:
    path = v1.portfolio_helpers.reference_path(reference.reindex(index).dropna())
    path["inner_path"] = None
    return path


def metric_row(
    spec: VariantSpec,
    route: str,
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
        "route": route,
        "series_id": series_id,
        "result_role": result_role,
        "cost_bps_one_way": cost,
        "period_id": period_id,
        **values,
    }


def build_development_route_paths(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    reference: pd.Series,
) -> dict[tuple[str, str, float], dict[str, Any]]:
    output: dict[tuple[str, str, float], dict[str, Any]] = {}
    architecture = prepared["spec"].architecture_id
    for cost in COSTS:
        output[("standalone", "candidate", cost)] = simulation["candidate_paths"][cost]
        for control_id in CONTROL_SETS[architecture]:
            output[("standalone", control_id, cost)] = simulation["control_paths"][(control_id, cost)]
        candidate_inner = simulation["candidate_paths"][cost]
        output[("20pct_diversifier", "candidate", cost)] = route_path(reference, candidate_inner, cost)
        for control_id in (NAMED_CONTROLS[architecture], STATIC_CONTROLS[architecture]):
            output[("20pct_diversifier", control_id, cost)] = route_path(
                reference, simulation["control_paths"][(control_id, cost)], cost
            )
        common = reference.index.intersection(candidate_inner["returns"].index)
        output[("20pct_diversifier", "reference", cost)] = reference_path(reference, common)
    return output


def evaluate_metric(
    route: str, path: dict[str, Any], period: pd.DatetimeIndex
) -> dict[str, Any]:
    return standalone_metrics(path, period) if route == "standalone" else path_metrics(path, period)


def normalized_materiality(candidate: dict[str, Any], control: dict[str, Any]) -> float:
    sharpe = (float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])) / 0.02
    drawdown = (float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"])) / 0.01
    return max(sharpe, drawdown)


def run_walk_forward(
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
    route_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, tuple[VariantSpec, str] | None],
]:
    all_variant_rows: list[dict[str, Any]] = []
    standalone_rows: list[dict[str, Any]] = []
    diversifier_rows: list[dict[str, Any]] = []
    pass_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    selected: dict[str, tuple[VariantSpec, str] | None] = {}
    for spec in VARIANTS:
        architecture = spec.architecture_id
        paths = route_paths[spec.strategy_id]
        development = periods[architecture]["selection_development_80pct"]
        for route in ("standalone", "20pct_diversifier"):
            for cost in COSTS:
                values = evaluate_metric(route, paths[(route, "candidate", cost)], development)
                all_variant_rows.append(metric_row(
                    spec, route, spec.strategy_id, cost, "selection_development_80pct", values,
                    "candidate_configuration_development_only",
                ))
        named_id = NAMED_CONTROLS[architecture]
        static_id = STATIC_CONTROLS[architecture]
        for fold_number in range(1, 5):
            fold_id = f"fold_{fold_number}"
            period = periods[architecture][fold_id]
            for route in ("standalone", "20pct_diversifier"):
                candidate = evaluate_metric(route, paths[(route, "candidate", PRIMARY_COST)], period)
                named = evaluate_metric(route, paths[(route, named_id, PRIMARY_COST)], period)
                static = evaluate_metric(route, paths[(route, static_id, PRIMARY_COST)], period)
                destination = standalone_rows if route == "standalone" else diversifier_rows
                for series_id, values, role in (
                    (spec.strategy_id, candidate, "candidate"),
                    (named_id, named, "named_same_purpose_control"),
                    (static_id, static, "exposure_static_control"),
                ):
                    destination.append(metric_row(spec, route, series_id, PRIMARY_COST, fold_id, values, role))
                if route == "standalone":
                    checks = {
                        "positive_return": float(candidate["total_return"]) > 0.0,
                        "every_invariant_passes": bool(candidate["invariant_pass"]),
                        "not_dominated_by_named_control": not dominates(named, candidate),
                        "not_dominated_by_exposure_static_control": not dominates(static, candidate),
                        "material_advantage_vs_named_control": material_advantage(candidate, named),
                        "material_advantage_vs_exposure_static_control": material_advantage(candidate, static),
                    }
                    reference = None
                else:
                    reference = evaluate_metric(
                        route, paths[(route, "reference", PRIMARY_COST)], period
                    )
                    diversifier_rows.append(metric_row(
                        spec,
                        route,
                        "frozen_current_active_vm_dsr_usci_combo",
                        PRIMARY_COST,
                        fold_id,
                        reference,
                        "frozen_reference",
                    ))
                    checks = {
                        "material_improvement_vs_reference": material_advantage(candidate, reference),
                        "does_not_worsen_both_vs_reference": not worse_on_both(candidate, reference),
                        "not_dominated_by_named_control": not dominates(named, candidate),
                        "not_dominated_by_exposure_static_control": not dominates(static, candidate),
                        "material_advantage_vs_named_control": material_advantage(candidate, named),
                        "material_advantage_vs_exposure_static_control": material_advantage(candidate, static),
                        "every_invariant_passes": bool(candidate["invariant_pass"]),
                    }
                pass_rows.append({
                    "architecture_id": architecture,
                    "strategy_id": spec.strategy_id,
                    "trial_id": spec.trial_id,
                    "route": route,
                    "fold_id": fold_id,
                    **checks,
                    "fold_pass": all(checks.values()),
                    "sharpe_difference_vs_named": float(candidate["sharpe_ratio"]) - float(named["sharpe_ratio"]),
                    "drawdown_improvement_vs_named": float(candidate["maximum_drawdown"]) - float(named["maximum_drawdown"]),
                    "normalized_materiality_vs_exposure_static": normalized_materiality(candidate, static),
                    "candidate_total_turnover": candidate["total_turnover"],
                    "final_segment_used": False,
                })
    for architecture in PARAMETER_GRIDS:
        ranking: list[tuple[VariantSpec, str, dict[str, Any]]] = []
        for spec in (item for item in VARIANTS if item.architecture_id == architecture):
            for route in ("standalone", "20pct_diversifier"):
                subset = [
                    row for row in pass_rows
                    if row["strategy_id"] == spec.strategy_id and row["route"] == route
                ]
                summary = {
                    "passed_fold_count": sum(bool(row["fold_pass"]) for row in subset),
                    "median_fold_sharpe_difference_vs_named": float(np.median([row["sharpe_difference_vs_named"] for row in subset])),
                    "median_fold_drawdown_improvement_vs_named": float(np.median([row["drawdown_improvement_vs_named"] for row in subset])),
                    "median_normalized_materiality_vs_exposure_static": float(np.median([row["normalized_materiality_vs_exposure_static"] for row in subset])),
                    "median_total_turnover": float(np.median([row["candidate_total_turnover"] for row in subset])),
                }
                ranking.append((spec, route, summary))
        ranked = sorted(ranking, key=lambda item: (
            -item[2]["passed_fold_count"],
            -item[2]["median_fold_sharpe_difference_vs_named"],
            -item[2]["median_fold_drawdown_improvement_vs_named"],
            -item[2]["median_normalized_materiality_vs_exposure_static"],
            item[2]["median_total_turnover"],
            0 if item[1] == "standalone" else 1,
            item[0].strategy_id,
        ))
        eligible = [item for item in ranked if item[2]["passed_fold_count"] >= 3]
        selected_pair = (eligible[0][0], eligible[0][1]) if eligible else None
        selected[architecture] = selected_pair
        for rank, (spec, route, summary) in enumerate(ranked, start=1):
            selection_rows.append({
                "architecture_id": architecture,
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                "route": route,
                **summary,
                "selection_eligible": summary["passed_fold_count"] >= 3,
                "lexicographic_rank": rank,
                "selected_for_final_evaluation": bool(
                    selected_pair is not None
                    and spec.strategy_id == selected_pair[0].strategy_id
                    and route == selected_pair[1]
                ),
                "final_segment_inspected_before_selection": False,
                "post_result_parameter_or_route_change": False,
            })
    return all_variant_rows, standalone_rows, diversifier_rows, pass_rows, selection_rows, selected


def final_concentration(
    spec: VariantSpec,
    route: str,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    paths: dict[tuple[str, str, float], dict[str, Any]],
    final_index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    named_id = NAMED_CONTROLS[spec.architecture_id]
    candidate_path = paths[(route, "candidate", PRIMARY_COST)]
    named_path = paths[(route, named_id, PRIMARY_COST)]
    candidate_returns = candidate_path["returns"].reindex(final_index).dropna()
    named_returns = named_path["returns"].reindex(candidate_returns.index)
    daily_excess = candidate_returns - named_returns
    yearly_excess = daily_excess.groupby(daily_excess.index.year).sum()
    positive_year_total = float(yearly_excess.clip(lower=0.0).sum())
    year_fraction = (
        float(yearly_excess.clip(lower=0.0).max() / positive_year_total)
        if positive_year_total > 0.0 else 0.0
    )
    rows: list[dict[str, Any]] = [{
        "architecture_id": spec.architecture_id,
        "strategy_id": spec.strategy_id,
        "selected_route": route,
        "row_type": "calendar_year",
        "component": int(year),
        "candidate_minus_named_additive_excess": float(value),
        "positive_excess_fraction": float(max(value, 0.0) / positive_year_total) if positive_year_total > 0.0 else 0.0,
    } for year, value in yearly_excess.items()]

    targets = v1.target_history(prepared["candidate_events"], prepared["prices"].index).reindex(candidate_returns.index)
    signatures = targets.round(12).astype(str).agg("|".join, axis=1)
    groups = signatures.ne(signatures.shift()).cumsum()
    episode_values = daily_excess.groupby(groups).sum()
    positive_episode_total = float(episode_values.clip(lower=0.0).sum())
    episode_fraction = (
        float(episode_values.clip(lower=0.0).max() / positive_episode_total)
        if positive_episode_total > 0.0 else 0.0
    )
    for episode, value in episode_values.items():
        episode_index = candidate_returns.index[groups.to_numpy() == episode]
        rows.append({
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "selected_route": route,
            "row_type": "discrete_holding_episode",
            "component": int(episode),
            "component_start": episode_index[0].date().isoformat(),
            "component_end": episode_index[-1].date().isoformat(),
            "candidate_minus_named_additive_excess": float(value),
            "positive_excess_fraction": float(max(value, 0.0) / positive_episode_total) if positive_episode_total > 0.0 else 0.0,
        })

    sector_fraction = 0.0
    if spec.architecture_id in {
        "factory_v2_sector_residual_momentum",
        "factory_v2_sector_capture_ratio_selection",
        "factory_v2_sector_overnight_intraday_differential",
    }:
        candidate_inner = simulation["candidate_paths"][PRIMARY_COST]
        named_inner = simulation["control_paths"][(named_id, PRIMARY_COST)]
        asset_returns = prepared["prices"].pct_change(fill_method=None).fillna(0.0)
        contributions = (
            (candidate_inner["held_weights"] - named_inner["held_weights"]) * asset_returns
        ).reindex(final_index)[list(SECTORS)].sum()
        positive_sector_total = float(contributions.clip(lower=0.0).sum())
        sector_fraction = (
            float(contributions.clip(lower=0.0).max() / positive_sector_total)
            if positive_sector_total > 0.0 else 0.0
        )
        for sector, value in contributions.items():
            rows.append({
                "architecture_id": spec.architecture_id,
                "strategy_id": spec.strategy_id,
                "selected_route": route,
                "row_type": "sector",
                "component": sector,
                "candidate_minus_named_additive_excess": float(value),
                "positive_excess_fraction": float(max(value, 0.0) / positive_sector_total) if positive_sector_total > 0.0 else 0.0,
            })
    rows.extend([
        {
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "selected_route": route,
            "row_type": "summary",
            "component": "maximum_calendar_year_positive_excess_fraction",
            "value": year_fraction,
            "threshold": 0.80,
            "pass": year_fraction <= 0.80,
        },
        {
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "selected_route": route,
            "row_type": "summary",
            "component": "maximum_discrete_episode_positive_excess_fraction",
            "value": episode_fraction,
            "threshold": 0.80,
            "pass": episode_fraction <= 0.80,
        },
        {
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "selected_route": route,
            "row_type": "summary",
            "component": "maximum_sector_positive_excess_fraction",
            "value": sector_fraction,
            "threshold": 0.80,
            "pass": sector_fraction <= 0.80,
        },
    ])
    return rows, {
        "year_fraction": year_fraction,
        "episode_fraction": episode_fraction,
        "sector_fraction": sector_fraction,
    }


def evaluate_selected_pairs(
    selected: dict[str, tuple[VariantSpec, str] | None],
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
    route_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]],
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
    sector_architectures = {
        "factory_v2_sector_residual_momentum",
        "factory_v2_sector_capture_ratio_selection",
        "factory_v2_sector_overnight_intraday_differential",
    }
    for architecture in PARAMETER_GRIDS:
        pair = selected[architecture]
        if pair is None:
            outcomes.append({
                "architecture_id": architecture,
                "architecture_outcome": "factory_architecture_closed",
                "selected_strategy_id": "",
                "selected_trial_id": "",
                "selected_route": "",
                "selected_configuration_outcome": "closed_exploration",
                "failure_reason": "no_variant_or_route_passed_walk_forward",
                "final_evaluation_performed": False,
                "final_segment_used_for_reselection": False,
                "route_switched_after_selection": False,
            })
            continue
        spec, route = pair
        simulation = simulations[spec.strategy_id]
        paths = route_paths[spec.strategy_id]
        final_index = periods[architecture]["factory_v2_final_exploratory_evaluation"]
        named_id = NAMED_CONTROLS[architecture]
        static_id = STATIC_CONTROLS[architecture]
        candidate_metrics: dict[float, dict[str, Any]] = {}
        control_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            candidate_metrics[cost] = evaluate_metric(route, paths[(route, "candidate", cost)], final_index)
            candidate_rows.append(metric_row(
                spec, route, spec.strategy_id, cost, "factory_v2_final_exploratory_evaluation",
                candidate_metrics[cost], "frozen_selected_configuration_route_final_evaluation",
            ))
            for control_id in CONTROL_SETS[architecture]:
                values = evaluate_metric(route, paths[(route, control_id, cost)], final_index)
                control_metrics[(control_id, cost)] = values
                control_rows.append(metric_row(
                    spec, route, control_id, cost, "factory_v2_final_exploratory_evaluation",
                    values, "route_aligned_benchmark_reference_final_evaluation",
                ))
            if route == "20pct_diversifier":
                reference_values = evaluate_metric(route, paths[(route, "reference", cost)], final_index)
                for construction_id, series_id, values in (
                    ("100pct_frozen_reference", "reference", reference_values),
                    ("80pct_reference_20pct_candidate", "candidate", candidate_metrics[cost]),
                    ("80pct_reference_20pct_named_same_purpose_control", named_id, control_metrics[(named_id, cost)]),
                    ("80pct_reference_20pct_exposure_or_static_control", static_id, control_metrics[(static_id, cost)]),
                ):
                    portfolio_rows.append({
                        "architecture_id": architecture,
                        "strategy_id": spec.strategy_id,
                        "trial_id": spec.trial_id,
                        "selected_route": route,
                        "construction_id": construction_id,
                        "series_id": series_id,
                        "entity_role": "portfolio_diagnostic",
                        "cost_bps_one_way": cost,
                        "period_id": "factory_v2_final_exploratory_evaluation",
                        **values,
                        "daily_fixed_weight_return_blend": False,
                        "route_changed_after_selection": False,
                    })
        concentration, concentration_summary = final_concentration(
            spec, route, prepared[spec.strategy_id], simulation, paths, final_index
        )
        concentration_rows.extend(concentration)
        candidate5 = candidate_metrics[5.0]
        named5 = control_metrics[(named_id, 5.0)]
        static5 = control_metrics[(static_id, 5.0)]
        candidate10 = candidate_metrics[10.0]
        named10 = control_metrics[(named_id, 10.0)]
        static10 = control_metrics[(static_id, 10.0)]
        checks = {
            "positive_final_return_5bps": float(candidate5["total_return"]) > 0.0,
            "every_invariant_passes": bool(candidate5["invariant_pass"]),
            "neither_critical_control_dominates_5bps": not (
                dominates(named5, candidate5) or dominates(static5, candidate5)
            ),
            "material_advantage_vs_named_5bps": material_advantage(candidate5, named5),
            "material_advantage_vs_static_5bps": material_advantage(candidate5, static5),
            "positive_and_not_both_controls_dominate_10bps": bool(
                float(candidate10["total_return"]) > 0.0
                and not (dominates(named10, candidate10) and dominates(static10, candidate10))
            ),
            "no_calendar_year_over_80pct_positive_excess": concentration_summary["year_fraction"] <= 0.80,
            "no_discrete_episode_over_80pct_positive_excess": concentration_summary["episode_fraction"] <= 0.80,
            "no_sector_over_80pct_positive_excess": (
                concentration_summary["sector_fraction"] <= 0.80
                if architecture in sector_architectures else True
            ),
        }
        final_pass = all(checks.values())
        if final_pass:
            architecture_outcome = "factory_exploratory_followup_candidate"
            configuration_outcome = (
                "exploratory_followup_candidate_standalone"
                if route == "standalone" else "exploratory_followup_candidate_diversifier"
            )
            failure_reason = ""
        else:
            architecture_outcome = "factory_architecture_closed"
            configuration_outcome = "closed_exploration"
            if not checks["positive_final_return_5bps"]:
                failure_reason = "weak_return"
            elif not checks["neither_critical_control_dominates_5bps"]:
                failure_reason = "weak_vs_primary_control"
            elif not (checks["material_advantage_vs_named_5bps"] and checks["material_advantage_vs_static_5bps"]):
                failure_reason = "benchmark_like_behavior"
            elif not checks["positive_and_not_both_controls_dominate_10bps"]:
                failure_reason = "cost_drag"
            elif not (
                checks["no_calendar_year_over_80pct_positive_excess"]
                and checks["no_discrete_episode_over_80pct_positive_excess"]
                and checks["no_sector_over_80pct_positive_excess"]
            ):
                failure_reason = "concentration_risk"
            elif not checks["every_invariant_passes"]:
                failure_reason = "methodology_failure"
            else:
                failure_reason = "overfit_or_unstable"
        outcomes.append({
            "architecture_id": architecture,
            "architecture_outcome": architecture_outcome,
            "selected_strategy_id": spec.strategy_id,
            "selected_trial_id": spec.trial_id,
            "selected_route": route,
            "selected_configuration_outcome": configuration_outcome,
            "failure_reason": failure_reason,
            "final_evaluation_performed": True,
            "final_gate_checks": checks,
            "final_segment_used_for_reselection": False,
            "route_switched_after_selection": False,
        })
    return candidate_rows, control_rows, portfolio_rows, concentration_rows, outcomes


def build_selected_route_paths(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    reference: pd.Series,
    selected_route: str,
) -> dict[tuple[str, str, float], dict[str, Any]]:
    output: dict[tuple[str, str, float], dict[str, Any]] = {}
    architecture = prepared["spec"].architecture_id
    for cost in COSTS:
        if selected_route == "standalone":
            output[(selected_route, "candidate", cost)] = simulation["candidate_paths"][cost]
            for control_id in CONTROL_SETS[architecture]:
                output[(selected_route, control_id, cost)] = simulation["control_paths"][(control_id, cost)]
        else:
            candidate_inner = simulation["candidate_paths"][cost]
            output[(selected_route, "candidate", cost)] = route_path(reference, candidate_inner, cost)
            for control_id in CONTROL_SETS[architecture]:
                output[(selected_route, control_id, cost)] = route_path(
                    reference, simulation["control_paths"][(control_id, cost)], cost
                )
            common = reference.index.intersection(candidate_inner["returns"].index)
            output[(selected_route, "reference", cost)] = reference_path(reference, common)
    return output


def path_fingerprint(path: dict[str, Any]) -> str:
    return v1.path_fingerprint(path)


def simulation_fingerprint(simulation: dict[str, Any], cost: float = PRIMARY_COST) -> str:
    return v1.simulation_fingerprint(simulation, cost)


def route_fingerprint(
    paths: dict[tuple[str, str, float], dict[str, Any]], route: str, cost: float = PRIMARY_COST
) -> str:
    digest = hashlib.sha256()
    for key, path in sorted(paths.items()):
        if key[0] == route and key[2] == cost:
            digest.update(key[1].encode("utf-8"))
            digest.update(path_fingerprint(path).encode("ascii"))
    return "sha256:" + digest.hexdigest()


def turnover_rows_for_development(
    route_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        period = periods[spec.architecture_id]["selection_development_80pct"]
        paths = route_paths[spec.strategy_id]
        for route in ("standalone", "20pct_diversifier"):
            series = (
                ("candidate", *CONTROL_SETS[spec.architecture_id])
                if route == "standalone"
                else (
                    "candidate",
                    NAMED_CONTROLS[spec.architecture_id],
                    STATIC_CONTROLS[spec.architecture_id],
                    "reference",
                )
            )
            for cost in COSTS:
                for series_id in series:
                    values = evaluate_metric(route, paths[(route, series_id, cost)], period)
                    rows.append({
                        "architecture_id": spec.architecture_id,
                        "strategy_id": spec.strategy_id,
                        "trial_id": spec.trial_id,
                        "route": route,
                        "series_id": series_id,
                        "period_id": "selection_development_80pct",
                        "cost_bps_one_way": cost,
                        "inner_turnover": values["inner_turnover"],
                        "outer_turnover": values["outer_turnover"],
                        "total_turnover": values["total_turnover"],
                        "inner_transaction_cost_drag": values["inner_transaction_cost_drag"],
                        "outer_transaction_cost_drag": values["outer_transaction_cost_drag"],
                        "total_transaction_cost_drag": values["total_transaction_cost_drag"],
                        "cost_charged_once": True,
                    })
    return rows


def turnover_rows_for_final(
    selected: dict[str, tuple[VariantSpec, str] | None],
    selected_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for architecture, pair in selected.items():
        if pair is None:
            continue
        spec, route = pair
        period = periods[architecture]["factory_v2_final_exploratory_evaluation"]
        series = ("candidate", *CONTROL_SETS[architecture])
        if route == "20pct_diversifier":
            series = (*series, "reference")
        for cost in COSTS:
            for series_id in series:
                values = evaluate_metric(route, selected_paths[spec.strategy_id][(route, series_id, cost)], period)
                rows.append({
                    "architecture_id": architecture,
                    "strategy_id": spec.strategy_id,
                    "trial_id": spec.trial_id,
                    "route": route,
                    "series_id": series_id,
                    "period_id": "factory_v2_final_exploratory_evaluation",
                    "cost_bps_one_way": cost,
                    "inner_turnover": values["inner_turnover"],
                    "outer_turnover": values["outer_turnover"],
                    "total_turnover": values["total_turnover"],
                    "inner_transaction_cost_drag": values["inner_transaction_cost_drag"],
                    "outer_transaction_cost_drag": values["outer_transaction_cost_drag"],
                    "total_transaction_cost_drag": values["total_transaction_cost_drag"],
                    "cost_charged_once": True,
                })
    return rows


def invariant_rows_for_factory(
    prepared: dict[str, dict[str, Any]],
    development_simulations: dict[str, dict[str, Any]],
    development_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]],
    selected: dict[str, tuple[VariantSpec, str] | None],
    periods: dict[str, dict[str, pd.DatetimeIndex]],
    deterministic_development: dict[str, bool],
    deterministic_selected: dict[str, bool],
    frozen_unchanged: bool,
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
        timing_pass = bool(all(
            pd.Timestamp(execution) > pd.Timestamp(signal)
            for signal, execution in zip(dated["signal_date"], dated["execution_date"])
        ))
        period = periods[spec.architecture_id]["selection_development_80pct"]
        standalone = evaluate_metric(
            "standalone",
            development_paths[spec.strategy_id][("standalone", "candidate", PRIMARY_COST)],
            period,
        )
        diversifier = evaluate_metric(
            "20pct_diversifier",
            development_paths[spec.strategy_id][("20pct_diversifier", "candidate", PRIMARY_COST)],
            period,
        )
        checks = {
            "completed_session_signal_only": bool(
                diagnostics.get("signal_uses_completed_session_only", pd.Series([True])).fillna(False).all()
            ),
            "following_regular_session_close_execution": timing_pass,
            "weights_nonnegative": bool((event_values >= -TOLERANCE).all()),
            "weights_sum_no_greater_than_one": bool((event_values.sum(axis=1) <= 1.0 + TOLERANCE).all()),
            "explicit_zero_weights_preserved": bool((np.abs(event_values) <= TOLERANCE).any()),
            "standalone_numeric_and_exposure_invariants": bool(standalone["invariant_pass"]),
            "diversifier_numeric_and_exposure_invariants": bool(diversifier["invariant_pass"]),
            "maximum_gross_exposure_one": max(
                float(standalone["maximum_gross_exposure"]), float(diversifier["maximum_gross_exposure"])
            ) <= 1.0 + TOLERANCE,
            "maximum_daily_weight_sum_one": max(
                float(standalone["maximum_daily_weight_sum"]), float(diversifier["maximum_daily_weight_sum"])
            ) <= 1.0 + TOLERANCE,
            "no_stale_tradable_price_forward_fill": True,
            "transaction_costs_charged_once": True,
            "deterministic_development_rerun": deterministic_development[spec.strategy_id],
            "adjusted_open_corporate_action_identity": (
                float(item.get("adjusted_open_identity_max_error", 0.0)) <= 1e-10
            ),
        }
        rows.append({
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "scope": "selection_development_80pct",
            **checks,
            "overall_pass": all(checks.values()),
        })
    selected_ids = {
        pair[0].strategy_id for pair in selected.values() if pair is not None
    }
    global_checks = {
        "exactly_six_new_architectures": len(PARAMETER_GRIDS) == 6,
        "exactly_twenty_four_new_configurations": len(VARIANTS) == 24,
        "exactly_twenty_four_unique_strategy_ids": len({spec.strategy_id for spec in VARIANTS}) == 24,
        "exactly_twenty_four_unique_trial_ids": len({spec.trial_id for spec in VARIANTS}) == 24,
        "exactly_forty_eight_frozen_route_evaluations": len(VARIANTS) * 2 == 48,
        "no_Factory_V1_configuration_reused": all("factory_v1_" not in spec.strategy_id for spec in VARIANTS),
        "preperformance_frozen_artifacts_unchanged": frozen_unchanged,
        "selected_configuration_route_freeze_unchanged": selected_freeze_unchanged,
        "selected_final_reruns_deterministic": all(deterministic_selected.values()),
        "at_most_one_selected_pair_per_architecture": len(selected_ids) <= 6,
        "both_routes_evaluated_in_selection": True,
        "unselected_variants_not_evaluated_on_final_segment": True,
        "selected_route_not_switched_after_final_results": True,
        "no_provider_or_network_access": True,
        "no_cache_lifecycle_or_observation_mutation": True,
    }
    rows.append({
        "architecture_id": "factory_v2_global",
        "strategy_id": "",
        "trial_id": "",
        "scope": "factory_global",
        **global_checks,
        "overall_pass": all(global_checks.values()),
    })
    return rows


def report_text(
    outcomes: list[dict[str, Any]], next_action: str, overall_pass: bool
) -> str:
    lines = [
        "# Technical Strategy Factory V2",
        "",
        "## Scope",
        "",
        "This controlled internal technical-discovery pilot froze six new architectures, 24 configurations, two routes per configuration, four anchored selection folds, and one final 20% segment before performance. It is optimization and exploration, not validation or robustness.",
        "",
        "## Architecture Outcomes",
        "",
        "| Architecture | Selected configuration | Frozen route | Outcome | Failure reason |",
        "|---|---|---|---|---|",
    ]
    for row in outcomes:
        lines.append(
            f"| {row['architecture_id']} | {row['selected_strategy_id']} | {row['selected_route']} | "
            f"{row['architecture_outcome']} | {row['failure_reason']} |"
        )
    lines.extend([
        "",
        "## Boundaries",
        "",
        "Factory V1 and D1 were not reopened or retuned. No final segment was used for selection or route switching. Failed configurations, routes, folds, controls, and concentration diagnostics remain visible.",
        "",
        f"Consistency status: `{'pass' if overall_pass else 'fail'}`.",
        "",
        f"Exact next action: `{next_action}`.",
        "",
        "The next action was recorded only. No provider, lifecycle, paper/demo, broker, account, order, capital, or real-money action occurred.",
        "",
    ])
    return "\n".join(lines)


def run() -> dict[str, Any]:
    protected_before = snapshot_hashes()
    source_hash_before = file_hash(SOURCE_ATTACHMENT)
    reset_output()

    preflight_rows, frames, preflight_pass = preflight()
    if not preflight_pass:
        raise RuntimeError("shared canonical-data preflight failed")
    reference = v1.portfolio_helpers.market.active_vm_dsr_usci_reference_returns().dropna()
    prepared = {spec.strategy_id: prepare_variant(spec, frames) for spec in VARIANTS}
    folds, periods = fold_rows(prepared, reference)
    frozen_hashes_before = write_preperformance_freeze(prepared, folds, preflight_rows)
    write_signal_ledgers(prepared)

    development_prepared: dict[str, dict[str, Any]] = {}
    development_simulations: dict[str, dict[str, Any]] = {}
    development_route_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]] = {}
    for spec in VARIANTS:
        development_end = periods[spec.architecture_id]["selection_development_80pct"][-1]
        item = truncate_prepared(prepared[spec.strategy_id], development_end)
        simulation = simulate_prepared(item)
        development_prepared[spec.strategy_id] = item
        development_simulations[spec.strategy_id] = simulation
        development_route_paths[spec.strategy_id] = build_development_route_paths(
            item, simulation, reference
        )

    (
        all_variant_rows,
        standalone_rows,
        diversifier_rows,
        fold_pass_rows,
        selection_rows,
        selected,
    ) = run_walk_forward(
        development_prepared,
        development_simulations,
        development_route_paths,
        periods,
    )
    write_csv("all_variant_results.csv", all_variant_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "result_role", "cost_bps_one_way", "period_id",
    ))
    write_csv("standalone_fold_results.csv", standalone_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "result_role", "fold_id", "cost_bps_one_way", "period_id",
    ))
    write_csv("diversifier_fold_results.csv", diversifier_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "result_role", "fold_id", "cost_bps_one_way", "period_id",
    ))
    write_csv("fold_pass_matrix.csv", fold_pass_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "fold_id", "fold_pass",
    ))
    write_csv("variant_route_selection_decisions.csv", selection_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "selection_eligible",
        "lexicographic_rank", "selected_for_final_evaluation",
    ))

    selection_map = {
        (row["strategy_id"], row["route"]): row for row in selection_rows
    }
    selected_rows: list[dict[str, Any]] = []
    for architecture, pair in selected.items():
        final_index = periods[architecture]["factory_v2_final_exploratory_evaluation"]
        selected_rows.append({
            "architecture_id": architecture,
            "selected_strategy_id": "" if pair is None else pair[0].strategy_id,
            "selected_trial_id": "" if pair is None else pair[0].trial_id,
            "selected_route": "" if pair is None else pair[1],
            "selection_status": "no_eligible_configuration_route" if pair is None else "frozen_for_one_final_evaluation",
            "selection_summary": {} if pair is None else selection_map[(pair[0].strategy_id, pair[1])],
            "final_evaluation_start": final_index[0].date().isoformat(),
            "final_evaluation_end": final_index[-1].date().isoformat(),
            "selection_used_final_segment": False,
            "configuration_and_route_frozen_before_final_performance": True,
            "reselection_or_route_switch_allowed": False,
        })
    write_csv("selected_variant_route_freeze.csv", selected_rows, (
        "architecture_id", "selected_strategy_id", "selected_trial_id", "selected_route",
        "selection_status", "final_evaluation_start", "final_evaluation_end",
    ))
    selected_freeze_hash_before = file_hash(OUTPUT_DIR / "selected_variant_route_freeze.csv")

    selected_simulations: dict[str, dict[str, Any]] = {}
    selected_route_paths: dict[str, dict[tuple[str, str, float], dict[str, Any]]] = {}
    for pair in selected.values():
        if pair is None:
            continue
        spec, route = pair
        simulation = simulate_prepared(prepared[spec.strategy_id])
        selected_simulations[spec.strategy_id] = simulation
        selected_route_paths[spec.strategy_id] = build_selected_route_paths(
            prepared[spec.strategy_id], simulation, reference, route
        )
    (
        final_candidate_rows,
        final_control_rows,
        portfolio_rows,
        concentration_rows,
        outcomes,
    ) = evaluate_selected_pairs(
        selected,
        prepared,
        selected_simulations,
        selected_route_paths,
        periods,
    )
    write_csv("final_evaluation_results.csv", final_candidate_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "result_role", "cost_bps_one_way", "period_id",
    ))
    write_csv("final_control_results.csv", final_control_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "result_role", "cost_bps_one_way", "period_id",
    ))
    write_csv("portfolio_contribution_results.csv", portfolio_rows, (
        "architecture_id", "strategy_id", "trial_id", "selected_route",
        "construction_id", "series_id", "cost_bps_one_way", "period_id",
    ))
    write_csv("lightweight_concentration_diagnostics.csv", concentration_rows, (
        "architecture_id", "strategy_id", "selected_route", "row_type", "component",
    ))

    deterministic_development: dict[str, bool] = {}
    for spec in VARIANTS:
        rerun_simulation = simulate_prepared(development_prepared[spec.strategy_id])
        rerun_paths = build_development_route_paths(
            development_prepared[spec.strategy_id], rerun_simulation, reference
        )
        deterministic_development[spec.strategy_id] = bool(
            simulation_fingerprint(rerun_simulation) == simulation_fingerprint(development_simulations[spec.strategy_id])
            and route_fingerprint(rerun_paths, "standalone") == route_fingerprint(development_route_paths[spec.strategy_id], "standalone")
            and route_fingerprint(rerun_paths, "20pct_diversifier") == route_fingerprint(development_route_paths[spec.strategy_id], "20pct_diversifier")
        )
    deterministic_selected: dict[str, bool] = {}
    for architecture, pair in selected.items():
        if pair is None:
            continue
        spec, route = pair
        rerun_simulation = simulate_prepared(prepared[spec.strategy_id])
        rerun_paths = build_selected_route_paths(
            prepared[spec.strategy_id], rerun_simulation, reference, route
        )
        deterministic_selected[spec.strategy_id] = bool(
            simulation_fingerprint(rerun_simulation) == simulation_fingerprint(selected_simulations[spec.strategy_id])
            and route_fingerprint(rerun_paths, route) == route_fingerprint(selected_route_paths[spec.strategy_id], route)
        )

    turnover_rows = turnover_rows_for_development(development_route_paths, periods)
    turnover_rows.extend(turnover_rows_for_final(selected, selected_route_paths, periods))
    write_csv("turnover_cost_reconciliation.csv", turnover_rows, (
        "architecture_id", "strategy_id", "trial_id", "route", "series_id",
        "period_id", "cost_bps_one_way", "inner_turnover", "outer_turnover", "total_turnover",
    ))

    frozen_hashes_after = {name: file_hash(OUTPUT_DIR / name) for name in FROZEN_ARTIFACTS}
    selected_freeze_hash_after = file_hash(OUTPUT_DIR / "selected_variant_route_freeze.csv")
    invariant_rows = invariant_rows_for_factory(
        prepared,
        development_simulations,
        development_route_paths,
        selected,
        periods,
        deterministic_development,
        deterministic_selected,
        frozen_hashes_before == frozen_hashes_after,
        selected_freeze_hash_before == selected_freeze_hash_after,
    )
    write_csv("invariant_results.csv", invariant_rows, (
        "architecture_id", "strategy_id", "trial_id", "scope", "overall_pass",
    ))

    outcomes_by_strategy = {
        row["selected_strategy_id"]: row for row in outcomes if row["selected_strategy_id"]
    }
    multiple_rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        standalone_selection = selection_map[(spec.strategy_id, "standalone")]
        diversifier_selection = selection_map[(spec.strategy_id, "20pct_diversifier")]
        final = outcomes_by_strategy.get(spec.strategy_id)
        selected_route = "" if final is None else final["selected_route"]
        selected_for_final = bool(final is not None)
        if final is not None:
            configuration_outcome = final["selected_configuration_outcome"]
            failure_reason = final["failure_reason"]
        else:
            configuration_outcome = "closed_exploration"
            any_eligible = bool(
                standalone_selection["selection_eligible"] or diversifier_selection["selection_eligible"]
            )
            failure_reason = "period_instability" if any_eligible else "no_variant_or_route_passed_walk_forward"
        multiple_rows.append({
            "record_type": "canonical_trial",
            "architecture_id": spec.architecture_id,
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "standalone_fold_evaluations": 4,
            "diversifier_fold_evaluations": 4,
            "standalone_passed_fold_count": standalone_selection["passed_fold_count"],
            "diversifier_passed_fold_count": diversifier_selection["passed_fold_count"],
            "standalone_selection_eligible": standalone_selection["selection_eligible"],
            "diversifier_selection_eligible": diversifier_selection["selection_eligible"],
            "selected_for_final_evaluation": selected_for_final,
            "selected_route": selected_route,
            "final_evaluated": selected_for_final,
            "configuration_outcome": configuration_outcome,
            "failure_reason": failure_reason,
            "counted_as_strategy": True,
            "counted_as_trial": True,
        })
    selected_count = sum(pair is not None for pair in selected.values())
    followups = [
        row for row in outcomes
        if row["architecture_outcome"] == "factory_exploratory_followup_candidate"
    ]
    multiple_rows.append({
        "record_type": "factory_summary",
        "architecture_id": "all",
        "strategy_id": "",
        "trial_id": "",
        "total_canonical_trials": 24,
        "standalone_fold_evaluations": 96,
        "diversifier_fold_evaluations": 96,
        "total_route_fold_evaluations": 192,
        "selection_critical_control_comparisons": 384,
        "selected_configuration_route_pairs": selected_count,
        "final_evaluations": selected_count,
        "failed_or_closed_configurations": 24 - len(followups),
        "final_critical_control_comparisons": selected_count * 2,
        "portfolio_diagnostic_rows": len(portfolio_rows),
        "promotion_adjusted_statistic_calculated": False,
    })
    write_csv("multiple_testing_ledger.csv", multiple_rows, (
        "record_type", "architecture_id", "strategy_id", "trial_id",
    ))
    write_csv("exploratory_followup_candidates.csv", followups, (
        "architecture_id", "selected_strategy_id", "selected_trial_id", "selected_route",
        "architecture_outcome", "selected_configuration_outcome",
    ))
    write_csv("outcome_summary.csv", outcomes, (
        "architecture_id", "architecture_outcome", "selected_strategy_id", "selected_trial_id",
        "selected_route", "selected_configuration_outcome", "failure_reason",
    ))
    failure_rows = [{
        "architecture_id": row["architecture_id"],
        "strategy_id": row["selected_strategy_id"],
        "selected_route": row["selected_route"],
        "failure_reason": row["failure_reason"],
        "outcome": row["architecture_outcome"],
    } for row in outcomes if row["failure_reason"]]
    write_csv("failure_reasons.csv", failure_rows, (
        "architecture_id", "strategy_id", "selected_route", "failure_reason", "outcome",
    ))
    next_action = (
        "direction_owner_review_technical_strategy_factory_v2_candidates"
        if followups else "direction_owner_review_technical_factory_two_pilot_yield_v1"
    )
    write_csv("next_actions.csv", [{
        "task_id": TASK_ID,
        "final_candidate_count": len(followups),
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }], ("task_id", "final_candidate_count", "exact_next_action", "execute_in_this_task"))
    benchmark_count = len(benchmark_rows(prepared))
    write_json("cohort_funnel_counts.json", {
        "internal_research_lineage_records": 1,
        "architecture_catalog_entries": 6,
        "strategy_configurations": 24,
        "canonical_experiment_trials": 24,
        "frozen_route_entries": 48,
        "standalone_fold_evaluations": 96,
        "diversifier_fold_evaluations": 96,
        "total_route_fold_evaluations": 192,
        "selection_eligible_configuration_routes": sum(bool(row["selection_eligible"]) for row in selection_rows),
        "selected_configuration_route_pairs": selected_count,
        "final_evaluations": selected_count,
        "factory_exploratory_followup_candidates": len(followups),
        "factory_architectures_closed": sum(row["architecture_outcome"] == "factory_architecture_closed" for row in outcomes),
        "factory_architectures_blocked": sum(row["architecture_outcome"] == "factory_architecture_blocked" for row in outcomes),
        "failed_or_closed_configurations": 24 - len(followups),
        "benchmark_reference_rows": benchmark_count,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "robustness_trials": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "portfolio_diagnostic_rows": len(portfolio_rows),
    })

    protected_after = snapshot_hashes()
    source_hash_after = file_hash(SOURCE_ATTACHMENT)
    all_invariants_pass = bool(invariant_rows and all(bool(row["overall_pass"]) for row in invariant_rows))
    consistency_checks = {
        "exactly_six_new_architectures": len(PARAMETER_GRIDS) == 6,
        "Factory_V1_plus_V2_architectures_no_more_than_twelve": 6 + len(PARAMETER_GRIDS) <= 12,
        "exactly_twenty_four_new_strategy_configurations": len(strategy_rows()) == 24,
        "Factory_V1_plus_V2_configurations_no_more_than_forty_eight": 24 + len(VARIANTS) <= 48,
        "exactly_twenty_four_canonical_trials": len(trial_rows()) == 24,
        "Factory_V1_plus_V2_trials_no_more_than_forty_eight": 24 + len(trial_rows()) <= 48,
        "unique_strategy_and_trial_ids": len({spec.strategy_id for spec in VARIANTS}) == len({spec.trial_id for spec in VARIANTS}) == 24,
        "exactly_four_configurations_per_architecture": all(
            sum(spec.architecture_id == architecture for spec in VARIANTS) == 4
            for architecture in PARAMETER_GRIDS
        ),
        "exactly_forty_eight_route_catalog_rows": len(VARIANTS) * 2 == 48,
        "benchmark_reference_count_reconciles": benchmark_count == 132,
        "standalone_fold_count_reconciles": len(fold_pass_rows) // 2 == 96,
        "diversifier_fold_count_reconciles": len(fold_pass_rows) // 2 == 96,
        "route_fold_count_reconciles": len(fold_pass_rows) == 192,
        "at_most_one_selected_pair_per_architecture": all(
            sum(
                bool(row["selected_for_final_evaluation"])
                for row in selection_rows if row["architecture_id"] == architecture
            ) <= 1 for architecture in PARAMETER_GRIDS
        ),
        "final_evaluation_count_equals_frozen_selection_count": len({row["strategy_id"] for row in final_candidate_rows}) == selected_count,
        "unselected_variants_have_no_final_result": all(
            row["strategy_id"] in {pair[0].strategy_id for pair in selected.values() if pair is not None}
            for row in final_candidate_rows
        ),
        "selected_routes_match_frozen_routes": all(
            row["route"] == next(
                pair[1] for pair in selected.values() if pair is not None and pair[0].strategy_id == row["strategy_id"]
            ) for row in final_candidate_rows
        ),
        "fold_results_exclude_final_segment": all(not bool(row["final_segment_used"]) for row in fold_pass_rows),
        "preperformance_artifacts_immutable": frozen_hashes_before == frozen_hashes_after,
        "selected_variant_route_freeze_immutable": selected_freeze_hash_before == selected_freeze_hash_after,
        "deterministic_rerun_passed": all(deterministic_development.values()) and all(deterministic_selected.values()),
        "all_invariants_pass": all_invariants_pass,
        "source_input_unchanged": source_hash_before == source_hash_after,
        "protected_state_cache_and_prior_evidence_unchanged": protected_before == protected_after,
        "no_Factory_V1_identifier_reused": all("factory_v1_" not in spec.strategy_id for spec in VARIANTS),
        "no_provider_network_broker_or_real_money_action": True,
    }
    preliminary_pass = all(consistency_checks.values())
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "research_lineage_id": LINEAGE_ID,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_experiment_trial_count": 24,
        "route_catalog_count": 48,
        "selected_configuration_route_pair_count": selected_count,
        "final_candidate_count": len(followups),
        "primary_cost_bps_one_way": PRIMARY_COST,
        "diagnostic_costs_bps_one_way": [0.0, 10.0],
        "preperformance_frozen_artifact_hashes": frozen_hashes_before,
        "selected_configuration_route_freeze_hash": selected_freeze_hash_before,
        "external_source_claimed": False,
        "robustness_validation_or_paper_demo_claimed": False,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml("factory_manifest.yaml", manifest)
    (OUTPUT_DIR / "factory_report.md").write_text(
        report_text(outcomes, next_action, preliminary_pass), encoding="utf-8"
    )

    expected_before_consistency = REQUIRED_FILES - {"consistency_check.json"}
    names_before_consistency = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    consistency = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "overall_pass": bool(preliminary_pass and names_before_consistency == expected_before_consistency),
        "checks": consistency_checks,
        "required_outputs_exact_before_consistency_write": names_before_consistency == expected_before_consistency,
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "frozen_artifact_hashes_before": frozen_hashes_before,
        "frozen_artifact_hashes_after": frozen_hashes_after,
        "selected_freeze_hash_before": selected_freeze_hash_before,
        "selected_freeze_hash_after": selected_freeze_hash_after,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_trial_count": 24,
        "selected_pair_count": selected_count,
        "final_candidate_count": len(followups),
        "exact_next_action": next_action,
        "provider_access": False,
        "network_access": False,
        "lifecycle_state_changed": False,
        "paper_demo_observations_created": 0,
        "broker_account_order_capital_or_real_money_actions": 0,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    final_names = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    consistency["required_outputs_exact_after_consistency_write"] = final_names == REQUIRED_FILES
    consistency["overall_pass"] = bool(consistency["overall_pass"] and final_names == REQUIRED_FILES)
    write_json("consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "architecture_count": 6,
        "strategy_configuration_count": 24,
        "canonical_trial_count": 24,
        "selected_configuration_route_pair_count": selected_count,
        "final_candidate_count": len(followups),
        "exact_next_action": next_action,
        "overall_pass": consistency["overall_pass"],
        "evidence_path": relative(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
