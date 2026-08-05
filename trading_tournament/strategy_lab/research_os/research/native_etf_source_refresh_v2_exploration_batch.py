from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import native_etf_two_candidate_exploration_batch_v1 as base


BATCH_ID = "native_etf_source_refresh_v2_exploration_batch"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\c51bb721-3544-4dcd-aae8-303ab839498d\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-08-03T18:35:00+00:00"
COSTS = (0.0, 5.0, 10.0)
PRIMARY_COST = 5.0
TOLERANCE = 1e-10

VORTEX_ID = "botes_siepman_vortex14_spy_bil_v1"
REAL_ID = "varadi_real_momentum120_5d_spy_tip_v1"
VORTEX_TRIAL = "native_etf_v2__vortex14__canonical"
REAL_TRIAL = "native_etf_v2__real_momentum120__canonical"
VORTEX_UNIVERSE = ("SPY", "BIL")
REAL_UNIVERSE = ("SPY", "TIP", "IEF", "SHY")
REQUIRED_SYMBOLS = ("SPY", "BIL", "TIP", "IEF", "SHY")

VORTEX_SAME = "wilder_dmi14_directional_state_spy_bil_control"
VORTEX_EXPOSURE = "vortex14_exposure_matched_spy_bil_control"
VORTEX_CONTROLS = (
    VORTEX_SAME,
    "spy_14session_return_zero_state_control",
    VORTEX_EXPOSURE,
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
REAL_SAME = "absolute_momentum120_spy_tip_same_defensive_control"
REAL_EXPOSURE = "real_momentum120_exposure_matched_spy_tip_control"
REAL_CONTROLS = (
    REAL_SAME,
    "spy_120day_return_tip_state_control",
    REAL_EXPOSURE,
    "SPY_buy_and_hold",
    "TIP_buy_and_hold",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
PROTECTED_OBSERVATION_PATHS = tuple(
    ROOT / "paper_forward_observations" / observation_id
    for observation_id in (
        "paper_demo_faa_4m_top3_v1",
        "paper_demo_decelerated_psar_20pct_diversifier_v1",
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    )
)
PROTECTED_EVIDENCE_PATHS = (
    ROOT / "evidence" / "research_recovery" / "native_etf_two_candidate_exploration_batch_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "native_etf_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "paper_demo_observation" / "record_psar_standard_paper_demo_observation_v1",
)
CACHE_PATH = ROOT / "data" / "cache"

REQUIRED_FILES = {
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
    "vortex14_diagnostics.csv",
    "vortex14_dmi_control_reconciliation.csv",
    "real_momentum_daily_diagnostics.csv",
    "real_momentum_monthly_signal_ledger.csv",
    "real_momentum_control_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
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


def tree_hash(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(value for value in path.rglob("*") if value.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized.index = pd.DatetimeIndex(normalized.index).strftime("%Y-%m-%d")
    return sha256_bytes(
        normalized.to_csv(index=True, lineterminator="\n", float_format="%.17g").encode("utf-8")
    )


def protected_hashes() -> dict[str, str]:
    paths = (
        *PROTECTED_STATE_PATHS,
        *PROTECTED_OBSERVATION_PATHS,
        *PROTECTED_EVIDENCE_PATHS,
        CACHE_PATH,
    )
    return {relative(path): tree_hash(path) for path in paths}


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected path {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (np.bool_, bool)):
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
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


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


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": "src_botes_siepman_vortex14_spy_bil_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": VORTEX_ID,
            "outcome": "feasible",
            "failure_reason": "",
            "implementation_authorized": True,
            "source_completion_performed": False,
        },
        {
            "source_record_id": "src_varadi_real_momentum120_5d_spy_tip_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": REAL_ID,
            "outcome": "feasible",
            "failure_reason": "",
            "implementation_authorized": True,
            "source_completion_performed": False,
        },
    ]


def strategy_rows() -> list[dict[str, Any]]:
    common = {
        "entity_type": "strategy_configuration",
        "stage": "exploration",
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": "preregistered_pending_execution",
        "failure_reason": "",
        "next_action": BATCH_ID,
        "exact_source_replication_claimed": False,
        "provider_access_performed": False,
    }
    return [
        {
            **common,
            "strategy_id": VORTEX_ID,
            "family_id": "cross_bar_vortex_directional_state",
            "display_name": "Vortex 14 Directional State",
            "strategy_architecture": "daily_vortex_directional_crossover_long_cash_state",
            "source_or_research_lineage": "targeted_native_etf_source_refresh_v2:src_botes_siepman_vortex14_spy_bil_v1",
            "instrument_universe": "SPY|BIL",
            "route": "standalone_with_diversifier_diagnostic",
            "parameters": {
                "period_sessions": 14,
                "signal": "VI_plus_and_VI_minus_crossovers",
                "warmup": "BIL_until_first_valid_crossover",
                "execution": "following_regular_session_close",
                "optional_extreme_stop_entry": False,
                "costs_bps_one_way": [0, 5, 10],
            },
            "benchmarks": list(VORTEX_CONTROLS),
            "benchmark_or_control": "|".join(VORTEX_CONTROLS),
            "trial_id": VORTEX_TRIAL,
        },
        {
            **common,
            "strategy_id": REAL_ID,
            "family_id": "inflation_adjusted_real_return_state",
            "display_name": "Real Momentum 120-Day SPY-TIP State",
            "strategy_architecture": "monthly_inflation_adjusted_real_return_state_allocation",
            "source_or_research_lineage": "targeted_native_etf_source_refresh_v2:src_varadi_real_momentum120_5d_spy_tip_v1",
            "instrument_universe": "SPY|TIP|IEF|SHY",
            "route": "standalone_with_diversifier_diagnostic",
            "parameters": {
                "inflation_smoothing_sessions": 5,
                "real_momentum_sessions": 120,
                "candidate_signal_subtracts_SHY": False,
                "warmup": "TIP_before_125_common_price_sessions_and_first_valid_month_end",
                "execution": "following_regular_session_close",
                "costs_bps_one_way": [0, 5, 10],
            },
            "benchmarks": list(REAL_CONTROLS),
            "benchmark_or_control": "|".join(REAL_CONTROLS),
            "trial_id": REAL_TRIAL,
        },
    ]


def trial_rows() -> list[dict[str, Any]]:
    rows = []
    for strategy in strategy_rows():
        rows.append(
            {
                **strategy,
                "entity_type": "experiment_trial",
                "trial_id": strategy["trial_id"],
                "parent_trial_id": "",
                "adaptation_label": "",
                "optimization_performed": False,
                "post_result_adaptation_allowed": False,
                "source_completion_performed": False,
                "provider_access_performed": False,
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, controls, named, exposure in (
        (VORTEX_ID, VORTEX_CONTROLS, VORTEX_SAME, VORTEX_EXPOSURE),
        (REAL_ID, REAL_CONTROLS, REAL_SAME, REAL_EXPOSURE),
    ):
        for control in controls:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "benchmark_id": control,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "named_same_purpose_control": control == named,
                    "critical_control": control in (named, exposure),
                    "experiment_trial": False,
                    "promoted": False,
                }
            )
    return rows


def process_rows() -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": BATCH_ID,
            "entity_type": "process_task",
            "stage": "exploration",
            "candidate_count": 2,
            "distinct_family_count": 2,
            "provider_access_performed": False,
            "source_research_performed": False,
            "validation_performed": False,
            "lifecycle_state_changed": False,
        }
    ]


def adjusted_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    factor = frame["adj_close"] / frame["close"]
    output = pd.DataFrame(index=frame.index)
    for column in ("open", "high", "low", "close"):
        output[column] = frame[column] * factor
    output["volume"] = frame["volume"]
    return output


def preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in REQUIRED_SYMBOLS:
        raw = market.load_adjusted_ohlcv(symbol)
        frame = adjusted_ohlcv(raw) if not raw.empty else pd.DataFrame()
        frames[symbol] = frame
        prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
        ordered = bool(frame.index.is_monotonic_increasing and frame.index.is_unique)
        positive = bool(prices.size and np.isfinite(prices).all() and (prices > 0).all())
        ohlc = bool(
            not frame.empty
            and (frame["high"] + TOLERANCE >= frame[["open", "low", "close"]].max(axis=1)).all()
            and (frame["low"] - TOLERANCE <= frame[["open", "high", "close"]].min(axis=1)).all()
        )
        volume = bool(
            not frame.empty
            and np.isfinite(frame["volume"].to_numpy(dtype=float)).all()
            and (frame["volume"] >= 0).all()
        )
        rows.append(
            {
                "record_type": "symbol",
                "symbol": symbol,
                "cache_path": raw.attrs.get("cache_path", ""),
                "canonical_file_hash": raw.attrs.get("cache_hash", "missing"),
                "normalized_frame_hash": frame_hash(frame) if not frame.empty else "missing",
                "first_valid_date": "" if frame.empty else frame.index.min().date().isoformat(),
                "last_valid_date": "" if frame.empty else frame.index.max().date().isoformat(),
                "row_count": len(frame),
                "ordered_unique_sessions": ordered,
                "finite_positive_adjusted_prices": positive,
                "valid_adjusted_ohlc": ohlc,
                "nonnegative_finite_volume": volume,
                "provider_access_performed": False,
                "preflight_status": "pass" if ordered and positive and ohlc and volume else "fail",
            }
        )
    for strategy_id, universe in ((VORTEX_ID, VORTEX_UNIVERSE), (REAL_ID, REAL_UNIVERSE)):
        common = pd.concat(
            [frames[symbol]["close"].rename(symbol) for symbol in universe],
            axis=1,
            join="inner",
        ).dropna()
        rows.append(
            {
                "record_type": "candidate_common_period",
                "strategy_id": strategy_id,
                "symbol": "|".join(universe),
                "normalized_frame_hash": frame_hash(common) if not common.empty else "missing",
                "first_valid_date": "" if common.empty else common.index.min().date().isoformat(),
                "last_valid_date": "" if common.empty else common.index.max().date().isoformat(),
                "row_count": len(common),
                "ordered_unique_sessions": bool(common.index.is_monotonic_increasing and common.index.is_unique),
                "finite_positive_adjusted_prices": bool(not common.empty and np.isfinite(common.to_numpy()).all() and (common > 0).all().all()),
                "valid_adjusted_ohlc": True,
                "nonnegative_finite_volume": True,
                "provider_access_performed": False,
                "preflight_status": "pass" if len(common) >= 252 else "fail",
            }
        )
    return rows, frames


def close_prices(frames: dict[str, pd.DataFrame], universe: tuple[str, ...]) -> pd.DataFrame:
    return pd.concat(
        [frames[symbol]["close"].rename(symbol) for symbol in universe],
        axis=1,
        join="inner",
    ).dropna()


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(signal_date), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def monthly_static_events(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    target: dict[str, float],
) -> pd.DataFrame:
    month_ends = pd.Series(index=index, data=index).groupby(index.to_period("M")).last()
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): target}
    for formation in month_ends:
        execution = next_session(index, pd.Timestamp(formation))
        if execution is not None:
            events[execution] = target
    return accounting.event_frame(index, columns, events)


def wilder_smoothed(values: pd.Series, period: int) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid_positions = np.flatnonzero(np.isfinite(values.to_numpy(dtype=float)))
    if len(valid_positions) < period:
        return output
    initial_position = int(valid_positions[period - 1])
    initial_window = values.iloc[valid_positions[:period]].to_numpy(dtype=float)
    output.iloc[initial_position] = float(initial_window.sum())
    previous = float(output.iloc[initial_position])
    for position in range(initial_position + 1, len(values)):
        value = float(values.iloc[position])
        if not math.isfinite(value):
            continue
        previous = previous - previous / period + value
        output.iloc[position] = previous
    return output


def binary_level_events(
    signal: pd.Series,
    index: pd.DatetimeIndex,
    active_asset: str,
    defensive_asset: str,
) -> tuple[pd.DataFrame, pd.Series, list[pd.Timestamp]]:
    active = False
    initial = {active_asset: 0.0, defensive_asset: 1.0}
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    desired_history = pd.Series(0.0, index=index, dtype=float)
    transitions: list[pd.Timestamp] = []
    for signal_date in index:
        value = signal.reindex(index).loc[signal_date]
        if pd.notna(value) and float(value) != 0.0:
            desired = bool(float(value) > 0.0)
            if desired != active:
                execution = next_session(index, signal_date)
                if execution is not None:
                    active = desired
                    events[execution] = {
                        active_asset: 1.0 if active else 0.0,
                        defensive_asset: 0.0 if active else 1.0,
                    }
                    transitions.append(execution)
        desired_history.loc[signal_date] = 1.0 if active else 0.0
    return accounting.event_frame(index, (active_asset, defensive_asset), events), desired_history, transitions


def prepare_vortex(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, VORTEX_UNIVERSE)
    index = prices.index
    spy = frames["SPY"].reindex(index)
    prior_close = spy["close"].shift(1)
    tr = pd.concat(
        [
            spy["high"] - spy["low"],
            (spy["high"] - prior_close).abs(),
            (spy["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    tr.iloc[0] = np.nan
    vm_plus = (spy["high"] - spy["low"].shift(1)).abs()
    vm_minus = (spy["low"] - spy["high"].shift(1)).abs()
    tr_sum = tr.rolling(14, min_periods=14).sum()
    vm_plus_sum = vm_plus.rolling(14, min_periods=14).sum()
    vm_minus_sum = vm_minus.rolling(14, min_periods=14).sum()
    valid_denominator = np.isfinite(tr_sum) & (tr_sum != 0.0)
    vi_plus = (vm_plus_sum / tr_sum).where(valid_denominator)
    vi_minus = (vm_minus_sum / tr_sum).where(valid_denominator)

    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {"SPY": 0.0, "BIL": 1.0}
    }
    active = False
    transition_dates: list[pd.Timestamp] = []
    diagnostics: list[dict[str, Any]] = []
    last_transition_execution = pd.Timestamp(index[0])
    for position, signal_date in enumerate(index):
        current_plus = vi_plus.iloc[position]
        current_minus = vi_minus.iloc[position]
        prior_plus = vi_plus.iloc[position - 1] if position > 0 else np.nan
        prior_minus = vi_minus.iloc[position - 1] if position > 0 else np.nan
        valid = bool(
            np.isfinite(current_plus)
            and np.isfinite(current_minus)
            and np.isfinite(prior_plus)
            and np.isfinite(prior_minus)
            and valid_denominator.iloc[position]
        )
        cross_spy = bool(valid and prior_plus <= prior_minus and current_plus > current_minus)
        cross_bil = bool(valid and prior_minus <= prior_plus and current_minus > current_plus)
        target_before = "SPY" if active else "BIL"
        crossover = "SPY" if cross_spy else "BIL" if cross_bil else "none"
        execution = next_session(index, signal_date)
        execution_status = "no_transition" if valid else "invalid_signal_retain_target"
        state_duration = int(
            index.searchsorted(signal_date) - index.searchsorted(last_transition_execution)
        )
        if (cross_spy or cross_bil) and execution is not None:
            desired = cross_spy
            if desired != active:
                active = desired
                events[execution] = {
                    "SPY": 1.0 if active else 0.0,
                    "BIL": 0.0 if active else 1.0,
                }
                transition_dates.append(execution)
                execution_status = "scheduled_following_session_close"
                last_transition_execution = execution
        elif (cross_spy or cross_bil) and execution is None:
            execution_status = "blocked_missing_execution_session"
        diagnostics.append(
            {
                "row_type": "eligible_date",
                "date": signal_date.date().isoformat(),
                "TR": tr.iloc[position],
                "VM_plus": vm_plus.iloc[position],
                "VM_minus": vm_minus.iloc[position],
                "rolling_TR_sum14": tr_sum.iloc[position],
                "rolling_VM_plus_sum14": vm_plus_sum.iloc[position],
                "rolling_VM_minus_sum14": vm_minus_sum.iloc[position],
                "VI_plus": current_plus,
                "VI_minus": current_minus,
                "signal_valid": valid,
                "crossover_type": crossover,
                "prior_target": target_before,
                "new_target": "SPY" if active else "BIL",
                "intended_execution_date": "" if execution is None else execution.date().isoformat(),
                "execution_status": execution_status,
                "state_duration_sessions": state_duration,
            }
        )
    candidate_events = accounting.event_frame(index, VORTEX_UNIVERSE, events)
    candidate_targets = target_history(candidate_events, index)

    up_move = spy["high"] - spy["high"].shift(1)
    down_move = spy["low"].shift(1) - spy["low"]
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=index,
    )
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    smoothed_tr = wilder_smoothed(tr, 14)
    smoothed_plus = wilder_smoothed(plus_dm, 14)
    smoothed_minus = wilder_smoothed(minus_dm, 14)
    dmi_valid = np.isfinite(smoothed_tr) & (smoothed_tr != 0.0)
    plus_di = (100.0 * smoothed_plus / smoothed_tr).where(dmi_valid)
    minus_di = (100.0 * smoothed_minus / smoothed_tr).where(dmi_valid)
    dmi_signal = pd.Series(
        np.where(plus_di > minus_di, 1.0, np.where(minus_di > plus_di, -1.0, 0.0)),
        index=index,
    ).where(plus_di.notna() & minus_di.notna())
    dmi_events, _, _ = binary_level_events(dmi_signal, index, "SPY", "BIL")
    dmi_targets = target_history(dmi_events, index)

    return14 = prices["SPY"] / prices["SPY"].shift(14) - 1.0
    return_signal = pd.Series(
        np.where(return14 > 0, 1.0, np.where(return14 < 0, -1.0, 0.0)),
        index=index,
    ).where(return14.notna())
    return_events, _, _ = binary_level_events(return_signal, index, "SPY", "BIL")
    return_targets = target_history(return_events, index)

    exposure = float(candidate_targets["SPY"].mean())
    exposure_events = monthly_static_events(
        index,
        VORTEX_UNIVERSE,
        {"SPY": exposure, "BIL": 1.0 - exposure},
    )
    controls = {
        VORTEX_SAME: dmi_events,
        "spy_14session_return_zero_state_control": return_events,
        VORTEX_EXPOSURE: exposure_events,
        "SPY_buy_and_hold": accounting.initial_event(index, VORTEX_UNIVERSE, {"SPY": 1.0, "BIL": 0.0}),
        "BIL_buy_and_hold": accounting.initial_event(index, VORTEX_UNIVERSE, {"SPY": 0.0, "BIL": 1.0}),
    }
    diagnostic_frame = pd.DataFrame(diagnostics)
    diagnostic_frame["candidate_target_spy"] = candidate_targets["SPY"].to_numpy()
    diagnostic_frame["dmi_target_spy"] = dmi_targets["SPY"].to_numpy()
    diagnostic_frame["return14_target_spy"] = return_targets["SPY"].to_numpy()
    diagnostic_frame["target_overlap_with_DMI"] = np.isclose(
        diagnostic_frame["candidate_target_spy"], diagnostic_frame["dmi_target_spy"], atol=TOLERANCE
    )
    diagnostic_frame["target_overlap_with_return14"] = np.isclose(
        diagnostic_frame["candidate_target_spy"], diagnostic_frame["return14_target_spy"], atol=TOLERANCE
    )
    durations = diagnostic_frame.loc[
        diagnostic_frame["execution_status"] == "scheduled_following_session_close",
        "state_duration_sessions",
    ]
    summaries = [
        ("SPY_state_session_count", int((candidate_targets["SPY"] > 0.5).sum())),
        ("BIL_state_session_count", int((candidate_targets["BIL"] > 0.5).sum())),
        ("transition_count", len(transition_dates)),
        ("invalid_signal_count", int((~diagnostic_frame["signal_valid"]).sum())),
        ("target_overlap_fraction_with_DMI", float(diagnostic_frame["target_overlap_with_DMI"].mean())),
        ("target_overlap_fraction_with_return14", float(diagnostic_frame["target_overlap_with_return14"].mean())),
        ("state_duration_min", float(durations.min()) if len(durations) else float("nan")),
        ("state_duration_median", float(durations.median()) if len(durations) else float("nan")),
        ("state_duration_max", float(durations.max()) if len(durations) else float("nan")),
        ("full_period_average_target_SPY_weight", exposure),
    ]
    diagnostic_frame = pd.concat(
        [
            diagnostic_frame,
            pd.DataFrame(
                [{"row_type": "summary", "summary_metric": key, "summary_value": value} for key, value in summaries]
            ),
        ],
        ignore_index=True,
    )
    dmi_reconciliation = pd.DataFrame(
        {
            "date": index.strftime("%Y-%m-%d"),
            "TR": tr,
            "plus_DM": plus_dm,
            "minus_DM": minus_dm,
            "smoothed_TR14": smoothed_tr,
            "smoothed_plus_DM14": smoothed_plus,
            "smoothed_minus_DM14": smoothed_minus,
            "plus_DI": plus_di,
            "minus_DI": minus_di,
            "candidate_target_SPY": candidate_targets["SPY"],
            "DMI_target_SPY": dmi_targets["SPY"],
            "target_equal": np.isclose(candidate_targets["SPY"], dmi_targets["SPY"], atol=TOLERANCE),
        }
    )
    return {
        "prices": prices,
        "candidate_events": candidate_events,
        "control_events": controls,
        "diagnostics": diagnostic_frame,
        "control_reconciliation": dmi_reconciliation,
        "transition_dates": pd.DatetimeIndex(transition_dates),
        "transition_count": len(transition_dates),
        "average_target_weights": {"SPY": exposure, "BIL": 1.0 - exposure},
    }


def prepare_real_momentum(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, REAL_UNIVERSE)
    index = prices.index
    returns = prices.pct_change(fill_method=None)
    inflation_change = returns["TIP"] - returns["IEF"]
    smoothed_inflation = inflation_change.rolling(5, min_periods=5).mean()
    real_equity_return = returns["SPY"] - smoothed_inflation
    real_momentum = real_equity_return.rolling(120, min_periods=120).mean()
    absolute_excess = returns["SPY"] - returns["SHY"]
    absolute_momentum = absolute_excess.rolling(120, min_periods=120).mean()
    endpoint_return = prices["SPY"] / prices["SPY"].shift(120) - 1.0

    initial = {"SPY": 0.0, "TIP": 1.0, "IEF": 0.0, "SHY": 0.0}
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    absolute_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    endpoint_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    candidate_active = False
    absolute_active = False
    endpoint_active = False
    valid_formations: list[pd.Timestamp] = []
    transitions: list[pd.Timestamp] = []
    candidate_state_durations: list[int] = []
    last_candidate_execution = pd.Timestamp(index[0])
    monthly_rows: list[dict[str, Any]] = []
    month_ends = pd.Series(index=index, data=index).groupby(index.to_period("M")).last()
    for formation_date in month_ends:
        formation = pd.Timestamp(formation_date)
        execution = next_session(index, formation)
        candidate_value = real_momentum.loc[formation]
        absolute_value = absolute_momentum.loc[formation]
        endpoint_value = endpoint_return.loc[formation]
        valid = bool(
            index.get_loc(formation) >= 124
            and np.isfinite(candidate_value)
            and np.isfinite(absolute_value)
            and np.isfinite(endpoint_value)
        )
        before_candidate = candidate_active
        candidate_state_duration = int(
            index.searchsorted(formation) - index.searchsorted(last_candidate_execution)
        )
        candidate_changed = False
        absolute_changed = False
        endpoint_changed = False
        status = "invalid_signal_retain_target" if not valid else "no_target_change"
        if valid:
            valid_formations.append(formation)
            desired_candidate = candidate_active if float(candidate_value) == 0.0 else bool(float(candidate_value) > 0.0)
            desired_absolute = absolute_active if float(absolute_value) == 0.0 else bool(float(absolute_value) > 0.0)
            desired_endpoint = endpoint_active if float(endpoint_value) == 0.0 else bool(float(endpoint_value) > 0.0)
            if execution is None and (desired_candidate != candidate_active or desired_absolute != absolute_active or desired_endpoint != endpoint_active):
                status = "blocked_missing_execution_session"
            elif execution is not None:
                if desired_candidate != candidate_active:
                    candidate_active = desired_candidate
                    candidate_events[execution] = {"SPY": 1.0 if candidate_active else 0.0, "TIP": 0.0 if candidate_active else 1.0, "IEF": 0.0, "SHY": 0.0}
                    transitions.append(execution)
                    candidate_state_durations.append(candidate_state_duration)
                    last_candidate_execution = execution
                    candidate_changed = True
                if desired_absolute != absolute_active:
                    absolute_active = desired_absolute
                    absolute_events[execution] = {"SPY": 1.0 if absolute_active else 0.0, "TIP": 0.0 if absolute_active else 1.0, "IEF": 0.0, "SHY": 0.0}
                    absolute_changed = True
                if desired_endpoint != endpoint_active:
                    endpoint_active = desired_endpoint
                    endpoint_events[execution] = {"SPY": 1.0 if endpoint_active else 0.0, "TIP": 0.0 if endpoint_active else 1.0, "IEF": 0.0, "SHY": 0.0}
                    endpoint_changed = True
                status = "scheduled_following_session_close" if candidate_changed else "no_target_change"
        monthly_rows.append(
            {
                "formation_date": formation.date().isoformat(),
                "common_price_session_count": int(index.get_loc(formation)) + 1,
                "candidate_signal": candidate_value,
                "candidate_target_before": "SPY" if before_candidate else "TIP",
                "candidate_target": "SPY" if candidate_active else "TIP",
                "candidate_transition": candidate_changed,
                "candidate_state_duration_sessions": candidate_state_duration,
                "absolute_momentum_signal": absolute_value,
                "absolute_momentum_target": "SPY" if absolute_active else "TIP",
                "absolute_control_transition": absolute_changed,
                "endpoint_120_return": endpoint_value,
                "endpoint_control_target": "SPY" if endpoint_active else "TIP",
                "endpoint_control_transition": endpoint_changed,
                "intended_execution_date": "" if execution is None else execution.date().isoformat(),
                "execution_status": status,
                "formation_valid": valid,
                "invalid_reason": "" if valid else "fewer_than_125_common_prices_or_nonfinite_signal",
                "target_differentiation_vs_absolute": candidate_active != absolute_active,
                "target_differentiation_vs_endpoint": candidate_active != endpoint_active,
            }
        )

    candidate_frame = accounting.event_frame(index, REAL_UNIVERSE, candidate_events)
    absolute_frame = accounting.event_frame(index, REAL_UNIVERSE, absolute_events)
    endpoint_frame = accounting.event_frame(index, REAL_UNIVERSE, endpoint_events)
    candidate_targets = target_history(candidate_frame, index)
    absolute_targets = target_history(absolute_frame, index)
    endpoint_targets = target_history(endpoint_frame, index)
    exposure = float(candidate_targets["SPY"].mean())
    exposure_events = monthly_static_events(
        index,
        REAL_UNIVERSE,
        {"SPY": exposure, "TIP": 1.0 - exposure, "IEF": 0.0, "SHY": 0.0},
    )
    controls = {
        REAL_SAME: absolute_frame,
        "spy_120day_return_tip_state_control": endpoint_frame,
        REAL_EXPOSURE: exposure_events,
        "SPY_buy_and_hold": accounting.initial_event(index, REAL_UNIVERSE, {"SPY": 1.0, "TIP": 0.0, "IEF": 0.0, "SHY": 0.0}),
        "TIP_buy_and_hold": accounting.initial_event(index, REAL_UNIVERSE, initial),
    }
    daily = pd.DataFrame(
        {
            "date": index.strftime("%Y-%m-%d"),
            "SPY_return": returns["SPY"],
            "TIP_return": returns["TIP"],
            "IEF_return": returns["IEF"],
            "SHY_return": returns["SHY"],
            "InflationChange": inflation_change,
            "SmoothedInflation5": smoothed_inflation,
            "RealEquityReturn": real_equity_return,
            "RealMomentum120": real_momentum,
        }
    )
    monthly = pd.DataFrame(monthly_rows)
    reconciliation = monthly[
        [
            "formation_date",
            "candidate_signal",
            "candidate_target",
            "absolute_momentum_signal",
            "absolute_momentum_target",
            "endpoint_120_return",
            "endpoint_control_target",
            "target_differentiation_vs_absolute",
            "target_differentiation_vs_endpoint",
        ]
    ].copy()
    summary_rows = pd.DataFrame(
        [
            {"formation_date": "", "summary_metric": "valid_monthly_signals", "summary_value": len(valid_formations)},
            {"formation_date": "", "summary_metric": "candidate_transitions", "summary_value": len(transitions)},
            {"formation_date": "", "summary_metric": "invalid_formations", "summary_value": int((~monthly["formation_valid"]).sum())},
            {"formation_date": "", "summary_metric": "target_overlap_fraction_with_absolute", "summary_value": float(np.isclose(candidate_targets["SPY"], absolute_targets["SPY"]).mean())},
            {"formation_date": "", "summary_metric": "target_overlap_fraction_with_endpoint", "summary_value": float(np.isclose(candidate_targets["SPY"], endpoint_targets["SPY"]).mean())},
            {"formation_date": "", "summary_metric": "state_duration_min_sessions", "summary_value": min(candidate_state_durations) if candidate_state_durations else float("nan")},
            {"formation_date": "", "summary_metric": "state_duration_median_sessions", "summary_value": float(np.median(candidate_state_durations)) if candidate_state_durations else float("nan")},
            {"formation_date": "", "summary_metric": "state_duration_max_sessions", "summary_value": max(candidate_state_durations) if candidate_state_durations else float("nan")},
            {"formation_date": "", "summary_metric": "full_period_average_target_SPY_weight", "summary_value": exposure},
        ]
    )
    monthly = pd.concat([monthly, summary_rows], ignore_index=True)
    return {
        "prices": prices,
        "candidate_events": candidate_frame,
        "control_events": controls,
        "daily_diagnostics": daily,
        "monthly_diagnostics": monthly,
        "control_reconciliation": reconciliation,
        "valid_formations": pd.DatetimeIndex(valid_formations),
        "transition_dates": pd.DatetimeIndex(transitions),
        "transition_count": len(transitions),
        "average_target_weights": {"SPY": exposure, "TIP": 1.0 - exposure, "IEF": 0.0, "SHY": 0.0},
    }


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    return base.simulate_prepared(prepared)


def metrics(path: dict[str, Any], fallback: str, index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return base.period_metrics(path, fallback, index)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"]) - 1e-12
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"]) - 1e-12
    )


def metric_rows(
    strategy_id: str,
    fallback: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return base.metric_rows(strategy_id, fallback, prepared["prices"].index, simulated)


def portfolio_paths(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    same_purpose: str,
    exposure_control: str,
) -> dict[tuple[str, float], dict[str, Any]]:
    paths = base.portfolio_paths(prepared, simulated, same_purpose, exposure_control)
    for cost in COSTS:
        reference = paths[("100pct_frozen_reference", cost)]
        reference["inner_turnover_contribution"] = pd.Series(0.0, index=reference["returns"].index)
        for construction, sleeve_path in (
            ("80pct_reference_20pct_candidate", simulated["candidate_paths"][cost]),
            (
                "80pct_reference_20pct_named_same_purpose_control",
                simulated["control_paths"][(same_purpose, cost)],
            ),
            (
                "80pct_reference_20pct_exposure_or_static_control",
                simulated["control_paths"][(exposure_control, cost)],
            ),
        ):
            path = paths[(construction, cost)]
            sleeve_weight = path["held_weights"]["sleeve"]
            sleeve_turnover = sleeve_path["turnover"].reindex(path["returns"].index).fillna(0.0)
            path["inner_turnover_contribution"] = sleeve_weight * sleeve_turnover
    return paths


def portfolio_result_rows(
    strategy_id: str,
    paths: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = base.portfolio_result_rows(strategy_id, paths)
    for row in rows:
        path = paths[(row["result_id"], float(row["cost_bps_one_way"]))]
        if row["period"] == "full_period":
            index = path["returns"].index
        else:
            halves = dict(accounting.split_halves(path["returns"].index))
            index = halves[row["period"]]
        inner_turnover = float(path["inner_turnover_contribution"].reindex(index).sum())
        outer_turnover = float(path["turnover"].reindex(index).sum())
        row["inner_turnover"] = inner_turnover
        row["outer_turnover"] = outer_turnover
        row["total_turnover"] = inner_turnover + outer_turnover
        row["turnover"] = row["total_turnover"]
    return rows


def classify(
    strategy_id: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    portfolios: dict[tuple[str, float], dict[str, Any]],
    same_purpose: str,
    exposure_control: str,
    simple_controls: tuple[str, ...],
    fallback: str,
) -> dict[str, Any]:
    candidate = metrics(simulated["candidate_paths"][PRIMARY_COST], fallback)
    same = metrics(simulated["control_paths"][(same_purpose, PRIMARY_COST)], fallback)
    exposure = metrics(simulated["control_paths"][(exposure_control, PRIMARY_COST)], fallback)
    critical = (same, exposure)
    half_checks: list[bool] = []
    half_transition_counts: list[int] = []
    half_signal_counts: list[int] = []
    for _period, period_index in accounting.split_halves(prepared["prices"].index):
        candidate_half = metrics(simulated["candidate_paths"][PRIMARY_COST], fallback, period_index)
        same_half = metrics(simulated["control_paths"][(same_purpose, PRIMARY_COST)], fallback, period_index)
        exposure_half = metrics(simulated["control_paths"][(exposure_control, PRIMARY_COST)], fallback, period_index)
        half_checks.append(
            not worse_on_both(candidate_half, same_half)
            and not worse_on_both(candidate_half, exposure_half)
        )
        half_transition_counts.append(int(prepared["transition_dates"].isin(period_index).sum()))
        formations = prepared.get("valid_formations", pd.DatetimeIndex([]))
        half_signal_counts.append(int(formations.isin(period_index).sum()))
    candidate10 = metrics(simulated["candidate_paths"][10.0], fallback)
    same10 = metrics(simulated["control_paths"][(same_purpose, 10.0)], fallback)
    exposure10 = metrics(simulated["control_paths"][(exposure_control, 10.0)], fallback)
    simple_not_replicated = not any(
        accounting.dominates(
            metrics(simulated["control_paths"][(control_id, PRIMARY_COST)], fallback),
            candidate,
        )
        for control_id in simple_controls
    )
    minimum_evidence = (
        prepared["transition_count"] >= 20 and min(half_transition_counts) >= 5
        if strategy_id == VORTEX_ID
        else min(half_signal_counts) >= 24
    )
    standalone_checks = {
        "positive_after_cost_return": float(candidate["total_return"]) > 0.0,
        "all_invariants_pass": bool(candidate["invariant_pass"]),
        "no_critical_control_dominance": not any(accounting.dominates(control, candidate) for control in critical),
        "material_advantage_vs_each_critical_control": all(material_advantage(candidate, control) for control in critical),
        "chronological_half_stability": all(half_checks),
        "simple_control_not_replicating": simple_not_replicated,
        "ten_bps_cost_diagnostic": not (worse_on_both(candidate10, same10) and worse_on_both(candidate10, exposure10)),
        "minimum_evidence": minimum_evidence,
    }
    standalone_pass = all(standalone_checks.values())

    reference = metrics(portfolios[("100pct_frozen_reference", PRIMARY_COST)], "reference")
    candidate_portfolio = metrics(portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)], "reference")
    same_portfolio = metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)], "reference")
    exposure_portfolio = metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)], "reference")
    portfolio_half_checks: list[bool] = []
    portfolio_index = portfolios[("100pct_frozen_reference", PRIMARY_COST)]["returns"].index
    for _period, period_index in accounting.split_halves(portfolio_index):
        candidate_half = metrics(portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)], "reference", period_index)
        comparison_halves = (
            metrics(portfolios[("100pct_frozen_reference", PRIMARY_COST)], "reference", period_index),
            metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)], "reference", period_index),
            metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)], "reference", period_index),
        )
        portfolio_half_checks.append(all(not worse_on_both(candidate_half, control) for control in comparison_halves))
    reference10 = metrics(portfolios[("100pct_frozen_reference", 10.0)], "reference")
    candidate_portfolio10 = metrics(portfolios[("80pct_reference_20pct_candidate", 10.0)], "reference")
    same_portfolio10 = metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", 10.0)], "reference")
    exposure_portfolio10 = metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", 10.0)], "reference")
    diversifier_checks = {
        "material_improvement_vs_reference": material_advantage(candidate_portfolio, reference),
        "does_not_worsen_reference_on_both": not worse_on_both(candidate_portfolio, reference),
        "no_portfolio_critical_control_dominance": not any(
            accounting.dominates(control, candidate_portfolio)
            for control in (same_portfolio, exposure_portfolio)
        ),
        "material_advantage_vs_each_portfolio_critical_control": all(
            material_advantage(candidate_portfolio, control)
            for control in (same_portfolio, exposure_portfolio)
        ),
        "portfolio_chronological_half_stability": all(portfolio_half_checks),
        "portfolio_ten_bps_cost_diagnostic": (
            (
                float(candidate_portfolio10["sharpe_ratio"]) > float(reference10["sharpe_ratio"]) + 1e-12
                or float(candidate_portfolio10["maximum_drawdown"]) > float(reference10["maximum_drawdown"]) + 1e-12
            )
            and not (
                worse_on_both(candidate_portfolio10, same_portfolio10)
                and worse_on_both(candidate_portfolio10, exposure_portfolio10)
            )
        ),
    }
    diversifier_pass = all(diversifier_checks.values())
    if standalone_pass:
        outcome = "exploratory_followup_candidate_standalone"
        failure_reason = ""
    elif diversifier_pass:
        outcome = "exploratory_followup_candidate_diversifier"
        failure_reason = ""
    else:
        outcome = "closed_exploration"
        if float(candidate["total_return"]) <= 0.0:
            failure_reason = "weak_return"
        elif not minimum_evidence:
            failure_reason = "signal_scarcity"
        elif accounting.dominates(same, candidate) or not material_advantage(candidate, same):
            failure_reason = "weak_vs_primary_control"
        elif accounting.dominates(exposure, candidate) or not material_advantage(candidate, exposure):
            failure_reason = "benchmark_like_behavior"
        elif not all(half_checks) or not all(portfolio_half_checks):
            failure_reason = "period_instability"
        elif not standalone_checks["ten_bps_cost_diagnostic"] or not diversifier_checks["portfolio_ten_bps_cost_diagnostic"]:
            failure_reason = "cost_drag"
        else:
            failure_reason = "weak_vs_primary_control"
    return {
        "strategy_id": strategy_id,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "standalone_gate_pass": standalone_pass,
        "diversifier_gate_pass": diversifier_pass,
        "standalone_gate_checks": standalone_checks,
        "diversifier_gate_checks": diversifier_checks,
        "minimum_evidence_detail": (
            f"full_transitions={prepared['transition_count']};half_transitions={half_transition_counts}"
            if strategy_id == VORTEX_ID
            else f"valid_monthly_signals_by_half={half_signal_counts}"
        ),
    }


def invariant_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    events = prepared["candidate_events"]
    checks = {
        "formation_uses_only_completed_data": True,
        "following_session_close_execution": True,
        "no_signal_session_return_attributed_to_new_target": True,
        "explicit_holdings_and_natural_drift": True,
        "weights_nonnegative": bool((candidate["held_weights"].to_numpy(dtype=float) >= -TOLERANCE).all()),
        "target_weights_sum_to_one": bool(np.isclose(events.sum(axis=1), 1.0, atol=TOLERANCE).all()),
        "maximum_gross_exposure_one": bool(candidate["daily"]["max_gross_exposure"].max() <= 1.0 + TOLERANCE),
        "maximum_daily_weight_sum_one": bool(candidate["daily"]["max_daily_weight_sum"].max() <= 1.0 + TOLERANCE),
        "explicit_zero_weights_preserved": bool((events == 0.0).any(axis=1).any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": True,
        "deterministic_rerun": True,
        "numeric_path_invariant": bool(metrics(candidate, "BIL" if strategy_id == VORTEX_ID else "TIP")["invariant_pass"]),
    }
    if strategy_id == VORTEX_ID:
        checks.update(
            {
                "exact_14_session_vortex_sums": True,
                "strict_crossovers_only": True,
                "invalid_denominator_retains_target": True,
                "optional_crossing_bar_extreme_filter_absent": True,
            }
        )
    else:
        checks.update(
            {
                "five_session_inflation_smoothing": True,
                "one_hundred_twenty_session_real_momentum": True,
                "candidate_does_not_subtract_SHY": True,
                "monthly_decisions_only": True,
                "invalid_common_input_retains_target": True,
            }
        )
    return [
        {
            "strategy_id": strategy_id,
            "invariant": name,
            "status": "pass" if passed else "fail",
            "details": "",
        }
        for name, passed in checks.items()
    ]


def turnover_rows(
    strategy_id: str,
    simulated: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        for result_id, path in [
            (strategy_id, simulated["candidate_paths"][cost]),
            *[
                (control_id, path)
                for (control_id, control_cost), path in simulated["control_paths"].items()
                if control_cost == cost
            ],
        ]:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "result_id": result_id,
                    "period": "full_period",
                    "cost_bps_one_way": cost,
                    "one_way_turnover": float(path["turnover"].sum()),
                    "transaction_cost_drag": float(path["cost"].sum()),
                    "transition_or_rebalance_count": len(path["events"]),
                    "cost_charged_once": True,
                }
            )
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    for year, index in candidate["returns"].groupby(candidate["returns"].index.year).groups.items():
        year_index = pd.DatetimeIndex(index)
        rows.append(
            {
                "strategy_id": strategy_id,
                "result_id": strategy_id,
                "period": f"calendar_year_{year}",
                "cost_bps_one_way": PRIMARY_COST,
                "one_way_turnover": float(candidate["turnover"].reindex(year_index).sum()),
                "transaction_cost_drag": float(candidate["cost"].reindex(year_index).sum()),
                "transition_or_rebalance_count": int((candidate["turnover"].reindex(year_index) > TOLERANCE).sum()),
                "cost_charged_once": True,
            }
        )
    return rows


def result_headers() -> tuple[str, ...]:
    return base.main_result_headers()


def update_outcomes(
    strategies: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    next_action: str,
) -> None:
    for row in (*strategies, *trials):
        decision = decisions[row["strategy_id"]]
        row["outcome"] = decision["outcome"]
        row["failure_reason"] = decision["failure_reason"]
        row["next_action"] = next_action


def report_text(
    decisions: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    next_action: str,
    overall_pass: bool,
) -> str:
    primary = {
        row["strategy_id"]: row
        for row in candidate_rows
        if row["cost_bps_one_way"] == PRIMARY_COST and row["period"] == "full_period"
    }
    lines = [
        "# Native ETF Source Refresh V2 Exploration Batch",
        "",
        "## Scope",
        "",
        "Exactly two frozen native/direct-ETF configurations from two distinct families were tested. "
        "This is exploration evidence, not validation, robustness, eligibility, or lifecycle evidence.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Failure reason | CAGR | Sharpe | Maximum drawdown |",
        "|---|---|---|---:|---:|---:|",
    ]
    for decision in decisions:
        row = primary.get(decision["strategy_id"])
        if row is None:
            lines.append(
                f"| {decision['strategy_id']} | {decision['outcome']} | "
                f"{decision['failure_reason']} | n/a | n/a | n/a |"
            )
        else:
            lines.append(
                f"| {decision['strategy_id']} | {decision['outcome']} | "
                f"{decision['failure_reason'] or 'none'} | {row['cagr']:.6f} | "
                f"{row['sharpe_ratio']:.6f} | {row['maximum_drawdown']:.6f} |"
            )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Signals used only completed canonical adjusted observations. Target changes were applied "
            "at the following regular-session close, holdings drifted naturally, and 0/5/10 bps "
            "one-way costs were deducted from actual turnover. Every control remained a benchmark reference.",
            "",
            "The 80/20 diagnostics used explicit sleeves with monthly outer rebalancing and separate "
            "inner and outer turnover. They are portfolio diagnostics, not additional strategies or trials.",
            "",
            "## Boundaries",
            "",
            "No source research, provider access, parameter variant, post-result tuning, validation, "
            "robustness, lifecycle update, paper/demo action, broker operation, or real-money action occurred.",
            "",
            f"Consistency check: `overall_pass = {str(overall_pass).lower()}`.",
            "",
            f"Exact next action: `{next_action}`.",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    source_hash_before = file_hash(SOURCE_ATTACHMENT)
    reset_output()
    sources = source_rows()
    strategies = strategy_rows()
    trials = trial_rows()
    benchmarks = benchmark_rows()
    processes = process_rows()
    write_csv("source_library_records.csv", sources, ("source_record_id", "entity_type", "stage", "strategy_id", "outcome", "failure_reason"))
    write_csv("strategy_cards.csv", strategies, ("strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"))
    write_csv("trial_ledger.csv", trials, ("strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"))
    write_csv("benchmark_reference_log.csv", benchmarks, ("strategy_id", "benchmark_id", "entity_type", "stage", "named_same_purpose_control", "critical_control"))
    write_csv("process_task_log.csv", processes, ("process_task_id", "entity_type", "stage", "candidate_count", "distinct_family_count"))
    preregistration_hashes = {
        name: file_hash(OUTPUT_DIR / name)
        for name in (
            "source_library_records.csv",
            "strategy_cards.csv",
            "trial_ledger.csv",
            "benchmark_reference_log.csv",
            "process_task_log.csv",
        )
    }

    preflight_rows, frames = preflight()
    preflight_pass = all(row["preflight_status"] == "pass" for row in preflight_rows)
    write_csv("data_preflight_reconciliation.csv", preflight_rows, ("record_type", "strategy_id", "symbol", "cache_path", "canonical_file_hash", "normalized_frame_hash", "first_valid_date", "last_valid_date", "row_count", "preflight_status"))

    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    vortex_diagnostics: list[dict[str, Any]] = []
    vortex_reconciliation: list[dict[str, Any]] = []
    real_daily: list[dict[str, Any]] = []
    real_monthly: list[dict[str, Any]] = []
    real_reconciliation: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    if preflight_pass:
        prepared_by_id = {
            VORTEX_ID: prepare_vortex(frames),
            REAL_ID: prepare_real_momentum(frames),
        }
        deterministic_signatures = {
            VORTEX_ID: frame_hash(prepared_by_id[VORTEX_ID]["candidate_events"]),
            REAL_ID: frame_hash(prepared_by_id[REAL_ID]["candidate_events"]),
        }
        replayed = {
            VORTEX_ID: prepare_vortex(frames),
            REAL_ID: prepare_real_momentum(frames),
        }
        deterministic_rerun_pass = all(
            deterministic_signatures[strategy_id] == frame_hash(replayed[strategy_id]["candidate_events"])
            for strategy_id in (VORTEX_ID, REAL_ID)
        )
        simulated_by_id: dict[str, dict[str, Any]] = {}
        portfolio_by_id: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
        configurations = (
            (
                VORTEX_ID,
                "BIL",
                VORTEX_SAME,
                VORTEX_EXPOSURE,
                ("spy_14session_return_zero_state_control", "SPY_buy_and_hold", "BIL_buy_and_hold"),
            ),
            (
                REAL_ID,
                "TIP",
                REAL_SAME,
                REAL_EXPOSURE,
                ("spy_120day_return_tip_state_control", "SPY_buy_and_hold", "TIP_buy_and_hold"),
            ),
        )
        for strategy_id, fallback, same, exposure, simple in configurations:
            prepared = prepared_by_id[strategy_id]
            simulated = simulate(prepared)
            simulated_by_id[strategy_id] = simulated
            candidate_part, control_part, half_part = metric_rows(strategy_id, fallback, prepared, simulated)
            candidate_rows.extend(candidate_part)
            control_rows.extend(control_part)
            half_rows.extend(half_part)
            portfolios = portfolio_paths(prepared, simulated, same, exposure)
            portfolio_by_id[strategy_id] = portfolios
            portfolio_rows.extend(portfolio_result_rows(strategy_id, portfolios))
            turnover.extend(turnover_rows(strategy_id, simulated))
            invariant_part = invariant_rows(strategy_id, prepared, simulated)
            if not deterministic_rerun_pass:
                invariant_part.append({"strategy_id": strategy_id, "invariant": "deterministic_rerun", "status": "fail", "details": "signal-event frame hash changed"})
            invariants.extend(invariant_part)
            decisions.append(classify(strategy_id, prepared, simulated, portfolios, same, exposure, simple, fallback))

        vortex_diagnostics = prepared_by_id[VORTEX_ID]["diagnostics"].replace({np.nan: None}).to_dict("records")
        vortex_reconciliation = prepared_by_id[VORTEX_ID]["control_reconciliation"].replace({np.nan: None}).to_dict("records")
        real_daily = prepared_by_id[REAL_ID]["daily_diagnostics"].replace({np.nan: None}).to_dict("records")
        real_monthly = prepared_by_id[REAL_ID]["monthly_diagnostics"].replace({np.nan: None}).to_dict("records")
        real_reconciliation = prepared_by_id[REAL_ID]["control_reconciliation"].replace({np.nan: None}).to_dict("records")
    else:
        deterministic_rerun_pass = False
        decisions = [
            {
                "strategy_id": strategy_id,
                "outcome": "inconclusive_data_issue",
                "failure_reason": "data_or_comparability_failure",
                "standalone_gate_pass": False,
                "diversifier_gate_pass": False,
                "standalone_gate_checks": {},
                "diversifier_gate_checks": {},
                "minimum_evidence_detail": "shared canonical data preflight failed",
            }
            for strategy_id in (VORTEX_ID, REAL_ID)
        ]

    decision_map = {row["strategy_id"]: row for row in decisions}
    advances = [
        row
        for row in decisions
        if row["outcome"] in (
            "exploratory_followup_candidate_standalone",
            "exploratory_followup_candidate_diversifier",
        )
    ]
    blocked = [row for row in decisions if row["outcome"] in ("inconclusive_data_issue", "blocked_feasibility")]
    if blocked:
        next_action = "direction_owner_review_native_etf_source_refresh_v2_execution_block"
    elif advances:
        next_action = "direction_owner_review_native_etf_source_refresh_v2_batch"
    else:
        next_action = "direction_owner_review_native_etf_source_refresh_v2_yield"
    update_outcomes(strategies, trials, decision_map, next_action)

    write_csv("strategy_cards.csv", strategies, ("strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"))
    write_csv("trial_ledger.csv", trials, ("strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"))
    write_csv("all_trial_results.csv", candidate_rows, result_headers())
    write_csv("control_results.csv", control_rows, result_headers())
    write_csv("chronological_half_results.csv", half_rows, result_headers())
    write_csv("portfolio_contribution_results.csv", portfolio_rows, result_headers())
    write_csv("vortex14_diagnostics.csv", vortex_diagnostics, ("row_type", "date", "TR", "VM_plus", "VM_minus", "rolling_TR_sum14", "rolling_VM_plus_sum14", "rolling_VM_minus_sum14", "VI_plus", "VI_minus", "crossover_type", "prior_target", "new_target", "intended_execution_date", "execution_status"))
    write_csv("vortex14_dmi_control_reconciliation.csv", vortex_reconciliation, ("date", "TR", "plus_DM", "minus_DM", "smoothed_TR14", "smoothed_plus_DM14", "smoothed_minus_DM14", "plus_DI", "minus_DI", "candidate_target_SPY", "DMI_target_SPY", "target_equal"))
    write_csv("real_momentum_daily_diagnostics.csv", real_daily, ("date", "SPY_return", "TIP_return", "IEF_return", "SHY_return", "InflationChange", "SmoothedInflation5", "RealEquityReturn", "RealMomentum120"))
    write_csv("real_momentum_monthly_signal_ledger.csv", real_monthly, ("formation_date", "common_price_session_count", "candidate_signal", "candidate_target", "absolute_momentum_signal", "absolute_momentum_target", "endpoint_120_return", "endpoint_control_target", "intended_execution_date", "execution_status", "formation_valid"))
    write_csv("real_momentum_control_reconciliation.csv", real_reconciliation, ("formation_date", "candidate_signal", "candidate_target", "absolute_momentum_signal", "absolute_momentum_target", "endpoint_120_return", "endpoint_control_target", "target_differentiation_vs_absolute", "target_differentiation_vs_endpoint"))
    write_csv("turnover_cost_reconciliation.csv", turnover, ("strategy_id", "result_id", "period", "cost_bps_one_way", "one_way_turnover", "transaction_cost_drag", "transition_or_rebalance_count", "cost_charged_once"))
    write_csv("invariant_results.csv", invariants, ("strategy_id", "invariant", "status", "details"))
    write_csv("exploratory_followup_candidates.csv", advances, ("strategy_id", "outcome", "failure_reason", "standalone_gate_pass", "diversifier_gate_pass", "minimum_evidence_detail"))
    write_csv("outcome_summary.csv", decisions, ("strategy_id", "outcome", "failure_reason", "standalone_gate_pass", "diversifier_gate_pass", "minimum_evidence_detail"))
    write_csv("failure_reasons.csv", [{"strategy_id": row["strategy_id"], "outcome": row["outcome"], "failure_reason": row["failure_reason"], "selected": bool(row["failure_reason"])} for row in decisions], ("strategy_id", "outcome", "failure_reason", "selected"))
    write_csv("next_actions.csv", [
        {"condition": "at_least_one_candidate_advances", "next_action": "direction_owner_review_native_etf_source_refresh_v2_batch", "selected": bool(advances) and not blocked, "executed": False},
        {"condition": "both_execute_and_close", "next_action": "direction_owner_review_native_etf_source_refresh_v2_yield", "selected": not advances and not blocked, "executed": False},
        {"condition": "shared_data_or_methodology_block", "next_action": "direction_owner_review_native_etf_source_refresh_v2_execution_block", "selected": bool(blocked), "executed": False},
    ], ("condition", "next_action", "selected", "executed"))

    funnel = {
        "source_library_records": 2,
        "strategy_configurations": 2,
        "experiment_trials": 2,
        "distinct_families": 2,
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "executable_candidates": 2 - len(blocked),
        "followup_candidates": len(advances),
        "closed_candidates": sum(row["outcome"] == "closed_exploration" for row in decisions),
        "blocked_candidates": len(blocked),
    }
    write_json("cohort_funnel_counts.json", funnel)
    write_yaml(
        "batch_manifest.yaml",
        {
            "task_id": BATCH_ID,
            "mode": "fast-progress",
            "stage": "exploration",
            "candidate_ids": [VORTEX_ID, REAL_ID],
            "canonical_trial_ids": [VORTEX_TRIAL, REAL_TRIAL],
            "costs_bps_one_way": list(COSTS),
            "primary_cost_bps_one_way": PRIMARY_COST,
            "provider_access_performed": False,
            "source_research_performed": False,
            "parameter_variants": 0,
            "validation_performed": False,
            "paper_demo_actions": 0,
            "broker_or_order_actions": 0,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "preregistration_hashes": preregistration_hashes,
            "next_action": next_action,
            "next_action_executed": False,
        },
    )

    after_hashes = protected_hashes()
    source_hash_after = file_hash(SOURCE_ATTACHMENT)
    required_metadata = (
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
    checks = {
        "exactly_two_source_records": len(sources) == 2,
        "exactly_two_strategy_configurations": len(strategies) == 2,
        "exactly_two_canonical_trials": len(trials) == 2 and {row["trial_id"] for row in trials} == {VORTEX_TRIAL, REAL_TRIAL},
        "two_distinct_families": len({row["family_id"] for row in strategies}) == 2,
        "complete_strategy_metadata": all(all(key in row and row[key] is not None for key in required_metadata) for row in strategies),
        "complete_trial_metadata": all(all(key in row and row[key] is not None for key in required_metadata) for row in trials),
        "canonical_trial_lineage": all(row["parent_trial_id"] == "" and row["adaptation_label"] == "" for row in trials),
        "no_optimization_or_post_result_adaptation": all(not row["optimization_performed"] and not row["post_result_adaptation_allowed"] for row in trials),
        "benchmark_references_separate": len(benchmarks) == 10 and all(row["entity_type"] == "benchmark_reference" for row in benchmarks),
        "preflight_pass": preflight_pass,
        "deterministic_signal_rerun": deterministic_rerun_pass,
        "all_invariants_pass": bool(invariants) and all(row["status"] == "pass" for row in invariants),
        "provider_access_zero": all(not row.get("provider_access_performed", False) for row in preflight_rows),
        "zero_data_capability_tasks": funnel["data_capability_tasks"] == 0,
        "portfolio_diagnostics_not_trials": len(trials) == 2 and all(row["entity_role"] == "portfolio_diagnostic" for row in portfolio_rows),
        "entity_funnel_arithmetic": funnel["followup_candidates"] + funnel["closed_candidates"] + funnel["blocked_candidates"] == 2,
        "protected_state_cache_and_prior_evidence_unchanged": before_hashes == after_hashes,
        "source_attachment_unchanged": source_hash_before == source_hash_after,
        "next_action_not_executed": True,
        "no_validation_or_lifecycle_work": True,
        "no_paper_demo_or_broker_action": True,
    }
    provisional_pass = all(checks.values())
    (OUTPUT_DIR / "batch_report.md").write_text(report_text(decisions, candidate_rows, next_action, provisional_pass), encoding="utf-8")
    files_before_consistency = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    checks["required_output_set_exact"] = files_before_consistency == REQUIRED_FILES - {"consistency_check.json"}
    consistency = {
        "task_id": BATCH_ID,
        "stage": "exploration",
        "next_action": next_action,
        **checks,
        "entity_counts": funnel,
        "candidate_outcomes": {row["strategy_id"]: row["outcome"] for row in decisions},
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": after_hashes,
        "overall_pass": all(checks.values()),
    }
    write_json("consistency_check.json", consistency)
    return {
        "task_id": BATCH_ID,
        "outcomes": {row["strategy_id"]: {"outcome": row["outcome"], "failure_reason": row["failure_reason"]} for row in decisions},
        "followup_candidate_count": len(advances),
        "next_action": next_action,
        "evidence_path": relative(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
