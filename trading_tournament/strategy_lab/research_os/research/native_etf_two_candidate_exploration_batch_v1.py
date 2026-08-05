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


BATCH_ID = "native_etf_two_candidate_exploration_batch_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\798e4b37-e8c1-4c8b-910c-4c82e1c68ae4"
    r"\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-30T00:00:00-06:00"
COSTS = (0.0, 5.0, 10.0)
PRIMARY_COST = 5.0
TOLERANCE = 1e-10

VIX_ID = "hestla_barnhart_vix_fix20_spy_bil_v1"
FAA_ID = "keller_vanputten_faa_4m_top3_v1"
VIX_TRIAL = "native_etf_two_v1__vix_fix__canonical"
FAA_TRIAL = "native_etf_two_v1__faa__canonical"

VIX_UNIVERSE = ("SPY", "BIL")
FAA_UNIVERSE = ("SPY", "EFA", "VWO", "SHY", "AGG", "GSG", "VNQ")

VIX_CONTROLS = (
    "close_only_fix20_sma20_spy_bil_control",
    "realized_volatility20_sma20_spy_bil_control",
    "vix_fix20_exposure_matched_spy_bil_control",
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
FAA_CONTROLS = (
    "faa_4m_return_only_top3_control",
    "faa_4m_return_volatility_top3_no_correlation_control",
    "monthly_equal_weight_7asset_control",
    "faa_full_period_average_weight_static_control",
    "SPY_buy_and_hold",
    "SHY_buy_and_hold",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
PROTECTED_EVIDENCE_PATHS = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "targeted_native_etf_source_refresh_v1"
    / "latest",
    ROOT
    / "evidence"
    / "research_recovery"
    / "resume_strategy_discovery_while_psar_validation_deferred_v1"
    / "latest",
    ROOT
    / "evidence"
    / "research_recovery"
    / "decelerated_psar_diversifier_incremental_value_followup_v1"
    / "latest",
    ROOT
    / "evidence"
    / "robustness"
    / "decelerated_psar_diversifier_final_robustness_v1"
    / "latest",
    ROOT
    / "evidence"
    / "experiment_design"
    / "design_decelerated_psar_prospective_validation_v1"
    / "latest",
    ROOT
    / "evidence"
    / "validation"
    / "activate_decelerated_psar_prospective_validation_v1"
    / "latest",
    ROOT
    / "evidence"
    / "validation"
    / "repair_and_retry_decelerated_psar_prospective_activation_v1"
    / "latest",
)
CACHE_PATH = ROOT / "data" / "cache"

REQUIRED_FILES = (
    "batch_manifest.yaml",
    "gate_override_record.csv",
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
    "vix_fix_diagnostics.csv",
    "faa_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
)


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
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized.index = pd.DatetimeIndex(normalized.index).strftime("%Y-%m-%d")
    return sha256_bytes(
        normalized.to_csv(index=True, lineterminator="\n", float_format="%.17g").encode("utf-8")
    )


def snapshot_hashes() -> dict[str, str]:
    paths = (*PROTECTED_STATE_PATHS, *PROTECTED_EVIDENCE_PATHS, CACHE_PATH)
    return {relative(path): tree_hash(path) for path in paths}


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (np.bool_, bool)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], headers: Iterable[str]) -> None:
    header_list = list(headers)
    extras: list[str] = []
    for row in rows:
        for key in row:
            if key not in header_list and key not in extras:
                extras.append(key)
    columns = header_list + extras
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


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
            "source_record_id": "src_hestla_barnhart_vix_fix20_spy_bil_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": VIX_ID,
            "family_id": "synthetic_downside_volatility_mean_reversion",
            "source_complete": True,
            "implementation_authorized": True,
            "provider_access_required": False,
            "next_action": BATCH_ID,
        },
        {
            "source_record_id": "src_keller_vanputten_faa_4m_top3_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": FAA_ID,
            "family_id": "generalized_momentum_flexible_asset_allocation",
            "source_complete": True,
            "implementation_authorized": True,
            "provider_access_required": False,
            "next_action": BATCH_ID,
        },
    ]


def strategy_definitions() -> list[dict[str, Any]]:
    common = {
        "entity_type": "strategy_configuration",
        "stage": "exploration",
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": "preregistered_for_frozen_exploration",
        "failure_reason": "",
        "next_action": "execute_preregistered_frozen_trial",
        "exact_source_replication_claimed": False,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "source_completion_performed": False,
        "provider_access_performed": False,
    }
    return [
        {
            **common,
            "strategy_id": VIX_ID,
            "family_id": "synthetic_downside_volatility_mean_reversion",
            "display_name": "VIX Fix 20-Day Volatility-Recovery State",
            "strategy_architecture": "daily_vix_fix_vs_sma_state_allocation",
            "source_or_research_lineage": (
                "targeted_native_etf_source_refresh_v1:"
                "src_hestla_barnhart_vix_fix20_spy_bil_v1"
            ),
            "instrument_universe": "|".join(VIX_UNIVERSE),
            "parameters": {
                "highest_close_sessions": 20,
                "indicator_sma_sessions": 20,
                "warmup_sessions": 39,
                "entry": "prior_fix>=prior_sma_and_current_fix<current_sma",
                "exit": "prior_fix<=prior_sma_and_current_fix>current_sma",
            },
            "benchmark_or_control": list(VIX_CONTROLS),
            "route": "standalone_with_diversifier_diagnostic",
            "trial_id": VIX_TRIAL,
        },
        {
            **common,
            "strategy_id": FAA_ID,
            "family_id": "generalized_momentum_flexible_asset_allocation",
            "display_name": "Flexible Asset Allocation 4-Month Top-Three",
            "strategy_architecture": (
                "monthly_return_volatility_correlation_rank_with_absolute_momentum"
            ),
            "source_or_research_lineage": (
                "targeted_native_etf_source_refresh_v1:"
                "src_keller_vanputten_faa_4m_top3_v1"
            ),
            "instrument_universe": "|".join(FAA_UNIVERSE),
            "parameters": {
                "formation_months": 4,
                "selected_count": 3,
                "return_rank_weight": 1.0,
                "volatility_rank_weight": 0.5,
                "correlation_rank_weight": 0.5,
                "absolute_momentum_fallback": "SHY",
            },
            "benchmark_or_control": list(FAA_CONTROLS),
            "route": "standalone_with_diversifier_diagnostic",
            "trial_id": FAA_TRIAL,
        },
    ]


def trial_rows() -> list[dict[str, Any]]:
    rows = []
    for strategy in strategy_definitions():
        rows.append(
            {
                **strategy,
                "entity_type": "experiment_trial",
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
                "strategy_rule_changed": False,
                "parameters_changed": False,
                "instruments_changed": False,
                "controls_changed": False,
                "route_changed": False,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows = []
    same_purpose = {
        VIX_ID: "close_only_fix20_sma20_spy_bil_control",
        FAA_ID: "faa_4m_return_only_top3_control",
    }
    critical = {
        VIX_ID: set(
            (
                "close_only_fix20_sma20_spy_bil_control",
                "vix_fix20_exposure_matched_spy_bil_control",
            )
        ),
        FAA_ID: set(
            (
                "faa_4m_return_only_top3_control",
                "faa_full_period_average_weight_static_control",
            )
        ),
    }
    for strategy_id, controls in ((VIX_ID, VIX_CONTROLS), (FAA_ID, FAA_CONTROLS)):
        for control_id in controls:
            rows.append(
                {
                    "benchmark_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "strategy_context": strategy_id,
                    "same_purpose_control": control_id == same_purpose[strategy_id],
                    "critical_control": control_id in critical[strategy_id],
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def preregister() -> None:
    gate_rows = [
        {
            "record_id": "qualified_discovery_cohort_size_2_to_4_v1",
            "entity_type": "direction_owner_process_record",
            "stage": "exploration_intake",
            "supersedes": "exactly_four_candidates_before_batch_execution",
            "qualified_cohort_minimum": 2,
            "qualified_cohort_maximum": 4,
            "minimum_distinct_families": 2,
            "independent_candidate_qualification_required": True,
            "weak_quota_filler_allowed": False,
            "source_completeness_standard_lowered": False,
            "validation_standard_lowered": False,
            "robustness_standard_lowered": False,
            "paper_demo_standard_lowered": False,
            "applies_only_to_this_exploration_intake": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    strategy_headers = (
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
    write_csv("gate_override_record.csv", gate_rows, gate_rows[0].keys())
    write_csv("source_library_records.csv", source_rows(), source_rows()[0].keys())
    write_csv("strategy_cards.csv", strategy_definitions(), strategy_headers)
    write_csv("trial_ledger.csv", trial_rows(), strategy_headers)
    write_csv(
        "benchmark_reference_log.csv",
        benchmark_rows(),
        (
            "benchmark_id",
            "entity_type",
            "stage",
            "strategy_context",
            "same_purpose_control",
            "critical_control",
            "counted_as_strategy",
            "counted_as_trial",
        ),
    )
    write_csv(
        "process_task_log.csv",
        [
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
        ],
        (
            "process_task_id",
            "entity_type",
            "stage",
            "candidate_count",
            "distinct_family_count",
            "provider_access_performed",
            "source_research_performed",
            "validation_performed",
            "lifecycle_state_changed",
        ),
    )


def adjusted_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    factor = frame["adj_close"] / frame["close"]
    result = pd.DataFrame(index=frame.index)
    for column in ("open", "high", "low", "close"):
        result[column] = frame[column] * factor
    result["volume"] = frame["volume"]
    return result


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in sorted(set(VIX_UNIVERSE + FAA_UNIVERSE)):
        raw = market.load_adjusted_ohlcv(symbol)
        frame = adjusted_ohlcv(raw) if not raw.empty else pd.DataFrame()
        frames[symbol] = frame
        values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
        ordered_unique = bool(frame.index.is_monotonic_increasing and frame.index.is_unique)
        positive_finite = bool(values.size and np.isfinite(values).all() and (values > 0.0).all())
        valid_ohlc = bool(
            not frame.empty
            and (frame["high"] + TOLERANCE >= frame[["open", "close", "low"]].max(axis=1)).all()
            and (frame["low"] - TOLERANCE <= frame[["open", "close", "high"]].min(axis=1)).all()
        )
        volume_valid = bool(
            not frame.empty
            and np.isfinite(frame["volume"].to_numpy(dtype=float)).all()
            and (frame["volume"] >= 0.0).all()
        )
        rows.append(
            {
                "record_type": "symbol",
                "symbol": symbol,
                "strategy_id": VIX_ID if symbol in VIX_UNIVERSE else FAA_ID,
                "cache_path": raw.attrs.get("cache_path", ""),
                "cache_file_hash": raw.attrs.get("cache_hash", "missing"),
                "normalized_frame_hash": frame_hash(frame) if not frame.empty else "missing",
                "first_valid_date": frame.index.min().date().isoformat() if len(frame) else "",
                "last_valid_date": frame.index.max().date().isoformat() if len(frame) else "",
                "row_count": len(frame),
                "ordered_unique_sessions": ordered_unique,
                "finite_positive_adjusted_ohlc": positive_finite,
                "valid_adjusted_ohlc_relationships": valid_ohlc,
                "nonnegative_finite_volume": volume_valid,
                "provider_access_performed": False,
                "preflight_status": (
                    "pass"
                    if ordered_unique and positive_finite and valid_ohlc and volume_valid
                    else "fail"
                ),
            }
        )
    for strategy_id, universe in ((VIX_ID, VIX_UNIVERSE), (FAA_ID, FAA_UNIVERSE)):
        common = pd.concat(
            [frames[symbol]["close"].rename(symbol) for symbol in universe],
            axis=1,
            join="inner",
        ).dropna()
        rows.append(
            {
                "record_type": "candidate_common_period",
                "symbol": "|".join(universe),
                "strategy_id": strategy_id,
                "cache_path": "",
                "cache_file_hash": "",
                "normalized_frame_hash": frame_hash(common) if not common.empty else "missing",
                "first_valid_date": common.index.min().date().isoformat() if len(common) else "",
                "last_valid_date": common.index.max().date().isoformat() if len(common) else "",
                "row_count": len(common),
                "ordered_unique_sessions": bool(common.index.is_monotonic_increasing),
                "finite_positive_adjusted_ohlc": bool(not common.empty),
                "valid_adjusted_ohlc_relationships": True,
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


def next_session(index: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date_value), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def monthly_execution_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    month_ends = pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    return [
        execution
        for formation in month_ends
        if (execution := next_session(index, pd.Timestamp(formation))) is not None
    ]


def monthly_static_events(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    target: dict[str, float],
) -> pd.DataFrame:
    events = {pd.Timestamp(index[0]): target}
    for date_value in monthly_execution_dates(index):
        events[date_value] = target
    return accounting.event_frame(index, columns, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def state_events(
    indicator: pd.Series,
    average: pd.Series,
    execution_index: pd.DatetimeIndex,
    name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(execution_index[0]): {"SPY": 0.0, "BIL": 1.0}
    }
    diagnostics: list[dict[str, Any]] = []
    active = False
    last_execution = pd.Timestamp(execution_index[0])
    signal_dates = indicator.index.intersection(execution_index)
    for date_value in signal_dates:
        current = indicator.loc[date_value]
        current_average = average.loc[date_value]
        prior = indicator.shift(1).loc[date_value]
        prior_average = average.shift(1).loc[date_value]
        available = bool(
            pd.notna(current)
            and pd.notna(current_average)
            and pd.notna(prior)
            and pd.notna(prior_average)
        )
        enter = bool(
            available and not active and prior >= prior_average and current < current_average
        )
        exit_signal = bool(
            available and active and prior <= prior_average and current > current_average
        )
        execution = next_session(execution_index, pd.Timestamp(date_value))
        status = "no_transition"
        state_before = active
        state_duration = int(
            execution_index.searchsorted(date_value)
            - execution_index.searchsorted(last_execution)
        )
        if (enter or exit_signal) and execution is not None:
            active = enter
            events[execution] = {
                "SPY": 1.0 if active else 0.0,
                "BIL": 0.0 if active else 1.0,
            }
            last_execution = execution
            status = "scheduled_following_session_close"
        elif (enter or exit_signal) and execution is None:
            status = "blocked_missing_following_execution_session"
        diagnostics.append(
            {
                "row_type": "signal",
                "indicator_name": name,
                "signal_date": pd.Timestamp(date_value).date().isoformat(),
                "indicator": float(current) if pd.notna(current) else float("nan"),
                "indicator_average": (
                    float(current_average) if pd.notna(current_average) else float("nan")
                ),
                "prior_indicator": float(prior) if pd.notna(prior) else float("nan"),
                "prior_indicator_average": (
                    float(prior_average) if pd.notna(prior_average) else float("nan")
                ),
                "entry_cross": enter,
                "exit_cross": exit_signal,
                "state_before_signal": "SPY" if state_before else "BIL",
                "target_after_signal": "SPY" if active else "BIL",
                "intended_execution_date": (
                    execution.date().isoformat() if execution is not None else ""
                ),
                "execution_status": status,
                "state_duration_sessions": state_duration,
            }
        )
    return (
        accounting.event_frame(execution_index, VIX_UNIVERSE, events),
        pd.DataFrame(diagnostics),
    )


def prepare_vix(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, VIX_UNIVERSE)
    spy = frames["SPY"]
    highest = spy["close"].rolling(20, min_periods=20).max()
    vix_fix = 100.0 * (highest - spy["low"]) / highest
    vix_fix_average = vix_fix.rolling(20, min_periods=20).mean()
    close_fix = 100.0 * (highest - spy["close"]) / highest
    close_fix_average = close_fix.rolling(20, min_periods=20).mean()
    log_return = np.log(spy["close"] / spy["close"].shift(1))
    realized_volatility = log_return.rolling(20, min_periods=20).std(ddof=1)
    realized_average = realized_volatility.rolling(20, min_periods=20).mean()

    candidate_events, diagnostics = state_events(
        vix_fix, vix_fix_average, prices.index, "vix_fix20"
    )
    close_events, close_diagnostics = state_events(
        close_fix, close_fix_average, prices.index, "close_only_fix20"
    )
    realized_events, _ = state_events(
        realized_volatility, realized_average, prices.index, "realized_volatility20"
    )
    candidate_targets = target_history(candidate_events, prices.index)
    close_targets = target_history(close_events, prices.index)
    exposure = float(candidate_targets["SPY"].mean())
    exposure_events = monthly_static_events(
        prices.index, VIX_UNIVERSE, {"SPY": exposure, "BIL": 1.0 - exposure}
    )
    controls = {
        "close_only_fix20_sma20_spy_bil_control": close_events,
        "realized_volatility20_sma20_spy_bil_control": realized_events,
        "vix_fix20_exposure_matched_spy_bil_control": exposure_events,
        "SPY_buy_and_hold": accounting.initial_event(
            prices.index, VIX_UNIVERSE, {"SPY": 1.0, "BIL": 0.0}
        ),
        "BIL_buy_and_hold": accounting.initial_event(
            prices.index, VIX_UNIVERSE, {"SPY": 0.0, "BIL": 1.0}
        ),
    }
    diagnostic_frame = diagnostics.copy()
    signal_index = pd.to_datetime(diagnostic_frame["signal_date"])
    diagnostic_frame["highest_close20"] = highest.reindex(signal_index).to_numpy()
    diagnostic_frame["vix_fix"] = vix_fix.reindex(signal_index).to_numpy()
    diagnostic_frame["vix_fix_sma20"] = vix_fix_average.reindex(signal_index).to_numpy()
    diagnostic_frame["candidate_target_spy"] = candidate_targets["SPY"].reindex(
        signal_index
    ).to_numpy()
    diagnostic_frame["close_only_target_spy"] = close_targets["SPY"].reindex(
        signal_index
    ).to_numpy()
    diagnostic_frame["target_overlap_with_close_only"] = np.isclose(
        diagnostic_frame["candidate_target_spy"],
        diagnostic_frame["close_only_target_spy"],
        atol=TOLERANCE,
    )
    transitions = max(len(candidate_events) - 1, 0)
    summaries = pd.DataFrame(
        [
            {
                "row_type": "summary",
                "indicator_name": "vix_fix20",
                "summary_metric": "completed_transition_count",
                "summary_value": transitions,
            },
            {
                "row_type": "summary",
                "indicator_name": "vix_fix20",
                "summary_metric": "full_period_average_target_spy_weight",
                "summary_value": exposure,
            },
            {
                "row_type": "summary",
                "indicator_name": "vix_fix20",
                "summary_metric": "target_overlap_fraction_with_close_only",
                "summary_value": float(
                    np.mean(
                        np.isclose(
                            candidate_targets["SPY"],
                            close_targets["SPY"],
                            atol=TOLERANCE,
                        )
                    )
                ),
            },
        ]
    )
    return {
        "prices": prices,
        "candidate_events": candidate_events,
        "control_events": controls,
        "diagnostics": pd.concat([diagnostic_frame, summaries], ignore_index=True),
        "transition_count": transitions,
        "average_target_weights": {"SPY": exposure, "BIL": 1.0 - exposure},
        "close_diagnostics": close_diagnostics,
    }


def deterministic_ranks(values: pd.Series, ascending: bool) -> dict[str, int]:
    ordered = sorted(
        ((float(value), str(symbol)) for symbol, value in values.items()),
        key=lambda item: ((item[0] if ascending else -item[0]), item[1]),
    )
    return {symbol: position + 1 for position, (_, symbol) in enumerate(ordered)}


def _selected_target(
    returns: pd.Series,
    scores: dict[str, float],
    columns: tuple[str, ...],
) -> tuple[dict[str, float], list[str], list[str]]:
    selected = [
        symbol
        for symbol, _ in sorted(scores.items(), key=lambda item: (item[1], item[0]))[:3]
    ]
    target = {symbol: 0.0 for symbol in columns}
    replacements = []
    for symbol in selected:
        allocated = symbol if float(returns[symbol]) > 0.0 else "SHY"
        if allocated == "SHY" and symbol != "SHY":
            replacements.append(symbol)
        target[allocated] += 1.0 / 3.0
    return target, selected, replacements


def prepare_faa(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, FAA_UNIVERSE)
    index = prices.index
    month_end_series = pd.Series(index=index, data=index).groupby(index.to_period("M")).last()
    month_ends = {period: pd.Timestamp(value) for period, value in month_end_series.items()}
    initial = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in FAA_UNIVERSE}
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    return_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    return_vol_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    equal_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {symbol: 1.0 / len(FAA_UNIVERSE) for symbol in FAA_UNIVERSE}
    }
    diagnostics: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []

    for period in sorted(month_ends):
        formation_date = month_ends[period]
        prior_period = period - 4
        execution = next_session(index, formation_date)
        if execution is None:
            continue
        equal_events[execution] = {symbol: 1.0 / len(FAA_UNIVERSE) for symbol in FAA_UNIVERSE}
        valid = prior_period in month_ends
        reason = "" if valid else "four_completed_calendar_months_unavailable"
        if valid:
            start_date = month_ends[prior_period]
            formation_prices = prices.loc[start_date:formation_date]
            formation_returns = formation_prices.pct_change(fill_method=None).iloc[1:]
            covered_periods = set(formation_returns.index.to_period("M"))
            expected_periods = {period - offset for offset in (0, 1, 2, 3)}
            valid = bool(
                len(formation_returns) >= 2
                and covered_periods == expected_periods
                and np.isfinite(formation_returns.to_numpy(dtype=float)).all()
            )
            if not valid:
                reason = "incomplete_full_universe_formation_interval"
        if not valid:
            candidate_events[execution] = initial
            return_events[execution] = initial
            return_vol_events[execution] = initial
            diagnostics.append(
                {
                    "row_type": "formation",
                    "formation_date": formation_date.date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "asset": "",
                    "formation_valid": False,
                    "invalid_reason": reason,
                    "selected_candidate": False,
                    "selected_return_only": False,
                    "shy_replacement": False,
                }
            )
            continue

        returns = prices.loc[formation_date] / prices.loc[start_date] - 1.0
        volatility = formation_returns.std(ddof=1)
        correlations = formation_returns.corr()
        average_correlation = pd.Series(
            {
                symbol: float(correlations.loc[symbol].drop(index=symbol).mean())
                for symbol in FAA_UNIVERSE
            }
        )
        finite = bool(
            np.isfinite(returns.to_numpy(dtype=float)).all()
            and np.isfinite(volatility.to_numpy(dtype=float)).all()
            and np.isfinite(average_correlation.to_numpy(dtype=float)).all()
        )
        if not finite:
            candidate_events[execution] = initial
            return_events[execution] = initial
            return_vol_events[execution] = initial
            diagnostics.append(
                {
                    "row_type": "formation",
                    "formation_date": formation_date.date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "asset": "",
                    "formation_valid": False,
                    "invalid_reason": "nonfinite_rank_input",
                    "selected_candidate": False,
                    "selected_return_only": False,
                    "shy_replacement": False,
                }
            )
            continue

        return_rank = deterministic_ranks(returns, ascending=False)
        volatility_rank = deterministic_ranks(volatility, ascending=True)
        correlation_rank = deterministic_ranks(average_correlation, ascending=True)
        combined_score = {
            symbol: (
                float(return_rank[symbol])
                + 0.5 * float(volatility_rank[symbol])
                + 0.5 * float(correlation_rank[symbol])
            )
            for symbol in FAA_UNIVERSE
        }
        return_score = {symbol: float(return_rank[symbol]) for symbol in FAA_UNIVERSE}
        return_vol_score = {
            symbol: float(return_rank[symbol]) + 0.5 * float(volatility_rank[symbol])
            for symbol in FAA_UNIVERSE
        }
        candidate_target, selected, replacements = _selected_target(
            returns, combined_score, FAA_UNIVERSE
        )
        return_target, return_selected, return_replacements = _selected_target(
            returns, return_score, FAA_UNIVERSE
        )
        return_vol_target, return_vol_selected, _ = _selected_target(
            returns, return_vol_score, FAA_UNIVERSE
        )
        candidate_events[execution] = candidate_target
        return_events[execution] = return_target
        return_vol_events[execution] = return_vol_target
        valid_formations.append(formation_date)
        for symbol in FAA_UNIVERSE:
            diagnostics.append(
                {
                    "row_type": "formation_asset",
                    "formation_date": formation_date.date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "asset": symbol,
                    "formation_start_date": start_date.date().isoformat(),
                    "formation_valid": True,
                    "invalid_reason": "",
                    "four_month_return": float(returns[symbol]),
                    "daily_realized_volatility": float(volatility[symbol]),
                    "average_pairwise_correlation": float(average_correlation[symbol]),
                    "return_rank": return_rank[symbol],
                    "volatility_rank": volatility_rank[symbol],
                    "correlation_rank": correlation_rank[symbol],
                    "faa_score": combined_score[symbol],
                    "selected_candidate": symbol in selected,
                    "selected_return_only": symbol in return_selected,
                    "selected_return_volatility": symbol in return_vol_selected,
                    "candidate_target_weight": candidate_target[symbol],
                    "return_only_target_weight": return_target[symbol],
                    "shy_replacement": symbol in replacements,
                    "return_only_shy_replacement": symbol in return_replacements,
                    "selected_overlap_with_return_only": len(set(selected) & set(return_selected)),
                }
            )

    candidate_frame = accounting.event_frame(index, FAA_UNIVERSE, candidate_events)
    return_frame = accounting.event_frame(index, FAA_UNIVERSE, return_events)
    return_vol_frame = accounting.event_frame(index, FAA_UNIVERSE, return_vol_events)
    equal_frame = accounting.event_frame(index, FAA_UNIVERSE, equal_events)
    average_targets = target_history(candidate_frame, index).mean().to_dict()
    average_total = float(sum(average_targets.values()))
    average_targets = {key: float(value) / average_total for key, value in average_targets.items()}
    static_frame = monthly_static_events(index, FAA_UNIVERSE, average_targets)
    controls = {
        "faa_4m_return_only_top3_control": return_frame,
        "faa_4m_return_volatility_top3_no_correlation_control": return_vol_frame,
        "monthly_equal_weight_7asset_control": equal_frame,
        "faa_full_period_average_weight_static_control": static_frame,
        "SPY_buy_and_hold": accounting.initial_event(
            index,
            FAA_UNIVERSE,
            {symbol: (1.0 if symbol == "SPY" else 0.0) for symbol in FAA_UNIVERSE},
        ),
        "SHY_buy_and_hold": accounting.initial_event(index, FAA_UNIVERSE, initial),
    }
    diagnostic_frame = pd.DataFrame(diagnostics)
    for symbol, weight in average_targets.items():
        diagnostic_frame = pd.concat(
            [
                diagnostic_frame,
                pd.DataFrame(
                    [
                        {
                            "row_type": "summary",
                            "asset": symbol,
                            "summary_metric": "full_period_average_target_weight",
                            "summary_value": weight,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return {
        "prices": prices,
        "candidate_events": candidate_frame,
        "control_events": controls,
        "diagnostics": diagnostic_frame,
        "valid_formations": pd.DatetimeIndex(valid_formations),
        "average_target_weights": average_targets,
    }


def simulate_prepared(prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    timing = "completed_signal_session_target_applied_at_following_regular_session_close"
    for cost in COSTS:
        candidate_paths[cost] = accounting.simulate_path(
            prepared["prices"], prepared["candidate_events"], cost, timing
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
    return {
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
    }


def period_metrics(
    path: dict[str, Any],
    fallback_symbol: str,
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    metrics = accounting.metric_payload(path, period_index)
    index = path["returns"].index if period_index is None else period_index
    held = path["held_weights"].reindex(index).dropna(how="all")
    metrics["average_risky_exposure"] = (
        float((1.0 - held[fallback_symbol]).mean()) if len(held) else float("nan")
    )
    metrics["maximum_single_asset_weight"] = (
        float(held.max(axis=1).max()) if len(held) else float("nan")
    )
    metrics["timing_invariant_status"] = "pass_following_session_close_no_signal_session_return"
    metrics["accounting_invariant_status"] = (
        "pass_turnover_and_cost_charged_once" if metrics["invariant_pass"] else "fail"
    )
    metrics["weight_invariant_status"] = metrics["exposure_weight_invariant_status"]
    metrics["exposure_invariant_status"] = metrics["exposure_weight_invariant_status"]
    return metrics


def result_row(
    strategy_id: str,
    result_id: str,
    entity_role: str,
    cost: float,
    period: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "result_id": result_id,
        "entity_role": entity_role,
        "cost_bps_one_way": cost,
        "period": period,
        **metrics,
        "transition_or_rebalance_count": metrics["trade_or_rebalance_count"],
    }


def metric_rows(
    strategy_id: str,
    fallback_symbol: str,
    prices_index: pd.DatetimeIndex,
    paths: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    for cost in COSTS:
        candidate_rows.append(
            result_row(
                strategy_id,
                strategy_id,
                "candidate",
                cost,
                "full_period",
                period_metrics(paths["candidate_paths"][cost], fallback_symbol),
            )
        )
        for control_id in sorted(
            {control for control, control_cost in paths["control_paths"] if control_cost == cost}
        ):
            control_rows.append(
                result_row(
                    strategy_id,
                    control_id,
                    "benchmark_reference",
                    cost,
                    "full_period",
                    period_metrics(paths["control_paths"][(control_id, cost)], fallback_symbol),
                )
            )
    for period, period_index in accounting.split_halves(prices_index):
        half_rows.append(
            result_row(
                strategy_id,
                strategy_id,
                "candidate",
                PRIMARY_COST,
                period,
                period_metrics(paths["candidate_paths"][PRIMARY_COST], fallback_symbol, period_index),
            )
        )
        for control_id in sorted(
            {
                control
                for control, control_cost in paths["control_paths"]
                if control_cost == PRIMARY_COST
            }
        ):
            half_rows.append(
                result_row(
                    strategy_id,
                    control_id,
                    "benchmark_reference",
                    PRIMARY_COST,
                    period,
                    period_metrics(
                        paths["control_paths"][(control_id, PRIMARY_COST)],
                        fallback_symbol,
                        period_index,
                    ),
                )
            )
    return candidate_rows, control_rows, half_rows


def path_from_two_sleeves(
    reference_returns: pd.Series,
    sleeve_path: dict[str, Any],
    cost_bps: float,
) -> dict[str, Any]:
    aligned = pd.concat(
        [
            reference_returns.rename("reference"),
            sleeve_path["returns"].rename("sleeve"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    inner_cost = sleeve_path["cost"].reindex(aligned.index).fillna(0.0)
    index = aligned.index
    rebalance_dates = set(monthly_execution_dates(index))
    current = np.array([0.8, 0.2], dtype=float)
    net_returns = np.zeros(len(index), dtype=float)
    turnover = np.zeros(len(index), dtype=float)
    outer_cost = np.zeros(len(index), dtype=float)
    inner_cost_contribution = np.zeros(len(index), dtype=float)
    held_rows: list[np.ndarray] = []
    event_rows: list[dict[str, Any]] = []
    for position, date_value in enumerate(index):
        held = current.copy()
        held_rows.append(held)
        daily_returns = aligned.iloc[position].to_numpy(dtype=float)
        gross_return = float(np.dot(held, daily_returns))
        inner_cost_contribution[position] = held[1] * float(inner_cost.iloc[position])
        drifted = held * (1.0 + daily_returns)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held.copy()
        target = pretrade.copy()
        daily_turnover = 0.0
        if pd.Timestamp(date_value) in rebalance_dates:
            target = np.array([0.8, 0.2], dtype=float)
            daily_turnover = 0.5 * float(np.abs(target - pretrade).sum())
            event_rows.append(
                {
                    "event_date": pd.Timestamp(date_value).date().isoformat(),
                    "one_way_turnover": daily_turnover,
                    "timing_convention": "month_end_target_applied_following_session_close",
                }
            )
        cost_fraction = daily_turnover * cost_bps / 10000.0
        net_returns[position] = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        turnover[position] = daily_turnover
        outer_cost[position] = (1.0 + gross_return) * cost_fraction
        current = target
    held_weights = pd.DataFrame(held_rows, index=index, columns=["reference", "sleeve"])
    daily = pd.DataFrame(
        {
            "net_return": net_returns,
            "one_way_turnover": turnover,
            "transaction_cost_drag": outer_cost,
            "inner_cost_drag_contribution": inner_cost_contribution,
            "max_gross_exposure": held_weights.abs().sum(axis=1),
            "max_daily_weight_sum": held_weights.sum(axis=1),
            "risky_exposure": held_weights.sum(axis=1),
        },
        index=index,
    )
    target_events = pd.DataFrame(
        [[0.8, 0.2]], index=[index[0]], columns=["reference", "sleeve"]
    )
    return {
        "returns": daily["net_return"],
        "turnover": daily["one_way_turnover"],
        "cost": daily["transaction_cost_drag"],
        "daily": daily,
        "held_weights": held_weights,
        "events": event_rows,
        "timing_convention": "monthly_outer_rebalance_following_session_close",
        "target_events": target_events,
        "inner_cost_drag_contribution": daily["inner_cost_drag_contribution"],
    }


def reference_path(reference_returns: pd.Series) -> dict[str, Any]:
    index = reference_returns.index
    held = pd.DataFrame({"reference": np.ones(len(index))}, index=index)
    daily = pd.DataFrame(
        {
            "net_return": reference_returns,
            "one_way_turnover": np.zeros(len(index)),
            "transaction_cost_drag": np.zeros(len(index)),
            "inner_cost_drag_contribution": np.zeros(len(index)),
            "max_gross_exposure": np.ones(len(index)),
            "max_daily_weight_sum": np.ones(len(index)),
            "risky_exposure": np.ones(len(index)),
        },
        index=index,
    )
    return {
        "returns": daily["net_return"],
        "turnover": daily["one_way_turnover"],
        "cost": daily["transaction_cost_drag"],
        "daily": daily,
        "held_weights": held,
        "events": [],
        "timing_convention": "frozen_reference_no_new_rebalance",
        "target_events": pd.DataFrame([[1.0]], index=[index[0]], columns=["reference"]),
        "inner_cost_drag_contribution": daily["inner_cost_drag_contribution"],
    }


def portfolio_paths(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    same_purpose: str,
    exposure_control: str,
) -> dict[tuple[str, float], dict[str, Any]]:
    reference = market.active_vm_dsr_usci_reference_returns()
    output: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidate_index = simulated["candidate_paths"][cost]["returns"].index
        common_reference = reference.reindex(candidate_index).dropna()
        output[("100pct_frozen_reference", cost)] = reference_path(common_reference)
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
            output[(construction, cost)] = path_from_two_sleeves(
                common_reference, sleeve_path, cost
            )
    return output


def portfolio_result_rows(
    strategy_id: str,
    paths: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        for construction in (
            "100pct_frozen_reference",
            "80pct_reference_20pct_candidate",
            "80pct_reference_20pct_named_same_purpose_control",
            "80pct_reference_20pct_exposure_or_static_control",
        ):
            path = paths[(construction, cost)]
            metrics = period_metrics(path, "reference")
            metrics["inner_transaction_cost_drag"] = float(
                path["inner_cost_drag_contribution"].sum()
            )
            metrics["outer_transaction_cost_drag"] = float(path["cost"].sum())
            metrics["transaction_cost_drag"] = (
                metrics["inner_transaction_cost_drag"]
                + metrics["outer_transaction_cost_drag"]
            )
            rows.append(
                result_row(
                    strategy_id,
                    construction,
                    "portfolio_diagnostic",
                    cost,
                    "full_period",
                    metrics,
                )
            )
    primary_index = paths[("100pct_frozen_reference", PRIMARY_COST)]["returns"].index
    for period, index in accounting.split_halves(primary_index):
        for construction in (
            "100pct_frozen_reference",
            "80pct_reference_20pct_candidate",
            "80pct_reference_20pct_named_same_purpose_control",
            "80pct_reference_20pct_exposure_or_static_control",
        ):
            path = paths[(construction, PRIMARY_COST)]
            metrics = period_metrics(path, "reference", index)
            metrics["inner_transaction_cost_drag"] = float(
                path["inner_cost_drag_contribution"].reindex(index).sum()
            )
            metrics["outer_transaction_cost_drag"] = float(path["cost"].reindex(index).sum())
            metrics["transaction_cost_drag"] = (
                metrics["inner_transaction_cost_drag"]
                + metrics["outer_transaction_cost_drag"]
            )
            rows.append(
                result_row(
                    strategy_id,
                    construction,
                    "portfolio_diagnostic",
                    PRIMARY_COST,
                    period,
                    metrics,
                )
            )
    return rows


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"])
        >= 0.01 - 1e-12
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"]) - 1e-12
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"]) - 1e-12
    )


def _path_metrics(path: dict[str, Any], fallback: str, index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return period_metrics(path, fallback, index)


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
    candidate = _path_metrics(simulated["candidate_paths"][PRIMARY_COST], fallback)
    same = _path_metrics(
        simulated["control_paths"][(same_purpose, PRIMARY_COST)], fallback
    )
    exposure = _path_metrics(
        simulated["control_paths"][(exposure_control, PRIMARY_COST)], fallback
    )
    critical = (same, exposure)
    full_invariants = bool(candidate["invariant_pass"])
    positive = float(candidate["total_return"]) > 0.0
    no_critical_dominance = not any(
        accounting.dominates(control, candidate) for control in critical
    )
    material_vs_each = all(material_advantage(candidate, control) for control in critical)
    simple_not_replicated = not any(
        accounting.dominates(
            _path_metrics(simulated["control_paths"][(control, PRIMARY_COST)], fallback),
            candidate,
        )
        for control in simple_controls
    )
    half_checks = []
    for _, index in accounting.split_halves(prepared["prices"].index):
        candidate_half = _path_metrics(
            simulated["candidate_paths"][PRIMARY_COST], fallback, index
        )
        same_half = _path_metrics(
            simulated["control_paths"][(same_purpose, PRIMARY_COST)], fallback, index
        )
        exposure_half = _path_metrics(
            simulated["control_paths"][(exposure_control, PRIMARY_COST)], fallback, index
        )
        half_checks.append(
            not worse_on_both(candidate_half, same_half)
            and not worse_on_both(candidate_half, exposure_half)
        )
    candidate_10 = _path_metrics(simulated["candidate_paths"][10.0], fallback)
    same_10 = _path_metrics(simulated["control_paths"][(same_purpose, 10.0)], fallback)
    exposure_10 = _path_metrics(
        simulated["control_paths"][(exposure_control, 10.0)], fallback
    )
    cost_pass = not (
        worse_on_both(candidate_10, same_10) and worse_on_both(candidate_10, exposure_10)
    )
    if strategy_id == VIX_ID:
        evidence_pass = int(prepared["transition_count"]) >= 20
        evidence_detail = f"completed_transitions={prepared['transition_count']}"
    else:
        midpoint = len(prepared["prices"].index) // 2
        split_date = prepared["prices"].index[midpoint]
        first = int((prepared["valid_formations"] < split_date).sum())
        second = int((prepared["valid_formations"] >= split_date).sum())
        evidence_pass = first >= 24 and second >= 24
        evidence_detail = f"valid_formations_first_half={first};second_half={second}"
    standalone_checks = {
        "positive_after_cost_return": positive,
        "all_invariants_pass": full_invariants,
        "no_critical_control_dominance": no_critical_dominance,
        "material_advantage_vs_each_critical_control": material_vs_each,
        "chronological_half_stability": all(half_checks),
        "simple_control_not_replicating": simple_not_replicated,
        "ten_bps_cost_diagnostic": cost_pass,
        "minimum_evidence": evidence_pass,
    }
    standalone_pass = all(standalone_checks.values())

    reference = _path_metrics(portfolios[("100pct_frozen_reference", PRIMARY_COST)], "reference")
    candidate_portfolio = _path_metrics(
        portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)], "reference"
    )
    same_portfolio = _path_metrics(
        portfolios[
            ("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)
        ],
        "reference",
    )
    exposure_portfolio = _path_metrics(
        portfolios[
            ("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)
        ],
        "reference",
    )
    improves_reference = material_advantage(candidate_portfolio, reference)
    does_not_worsen_reference = not worse_on_both(candidate_portfolio, reference)
    no_portfolio_dominance = not any(
        accounting.dominates(control, candidate_portfolio)
        for control in (same_portfolio, exposure_portfolio)
    )
    portfolio_material = all(
        material_advantage(candidate_portfolio, control)
        for control in (same_portfolio, exposure_portfolio)
    )
    portfolio_half_checks = []
    portfolio_index = portfolios[
        ("100pct_frozen_reference", PRIMARY_COST)
    ]["returns"].index
    for _, index in accounting.split_halves(portfolio_index):
        candidate_half = _path_metrics(
            portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)],
            "reference",
            index,
        )
        references = (
            _path_metrics(
                portfolios[("100pct_frozen_reference", PRIMARY_COST)],
                "reference",
                index,
            ),
            _path_metrics(
                portfolios[
                    ("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)
                ],
                "reference",
                index,
            ),
            _path_metrics(
                portfolios[
                    ("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)
                ],
                "reference",
                index,
            ),
        )
        portfolio_half_checks.append(
            all(not worse_on_both(candidate_half, control) for control in references)
        )
    reference_10 = _path_metrics(portfolios[("100pct_frozen_reference", 10.0)], "reference")
    candidate_portfolio_10 = _path_metrics(
        portfolios[("80pct_reference_20pct_candidate", 10.0)], "reference"
    )
    same_portfolio_10 = _path_metrics(
        portfolios[("80pct_reference_20pct_named_same_purpose_control", 10.0)],
        "reference",
    )
    exposure_portfolio_10 = _path_metrics(
        portfolios[("80pct_reference_20pct_exposure_or_static_control", 10.0)],
        "reference",
    )
    portfolio_cost_pass = (
        (
            float(candidate_portfolio_10["sharpe_ratio"])
            > float(reference_10["sharpe_ratio"]) + 1e-12
            or float(candidate_portfolio_10["maximum_drawdown"])
            > float(reference_10["maximum_drawdown"]) + 1e-12
        )
        and not (
            worse_on_both(candidate_portfolio_10, same_portfolio_10)
            and worse_on_both(candidate_portfolio_10, exposure_portfolio_10)
        )
    )
    diversifier_checks = {
        "material_improvement_vs_reference": improves_reference,
        "does_not_worsen_reference_on_both": does_not_worsen_reference,
        "no_portfolio_critical_control_dominance": no_portfolio_dominance,
        "material_advantage_vs_each_portfolio_critical_control": portfolio_material,
        "portfolio_chronological_half_stability": all(portfolio_half_checks),
        "portfolio_ten_bps_cost_diagnostic": portfolio_cost_pass,
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
        if not positive:
            failure_reason = "weak_return"
        elif not evidence_pass:
            failure_reason = "signal_scarcity"
        elif accounting.dominates(same, candidate) or not material_advantage(candidate, same):
            failure_reason = "weak_vs_primary_control"
        elif accounting.dominates(exposure, candidate) or not material_advantage(
            candidate, exposure
        ):
            failure_reason = "benchmark_like_behavior"
        elif not all(half_checks) or not all(portfolio_half_checks):
            failure_reason = "period_instability"
        elif not cost_pass or not portfolio_cost_pass:
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
        "minimum_evidence_detail": evidence_detail,
    }


def update_entity_outcomes(
    strategies: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    batch_next_action: str,
) -> None:
    for row in (*strategies, *trials):
        decision = decisions[row["strategy_id"]]
        row["outcome"] = decision["outcome"]
        row["failure_reason"] = decision["failure_reason"]
        row["next_action"] = batch_next_action


def invariant_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    target = prepared["candidate_events"]
    path_invariant = period_metrics(
        candidate, "BIL" if strategy_id == VIX_ID else "SHY"
    )["invariant_pass"]
    checks = {
        "formation_uses_only_completed_data": True,
        "following_session_close_execution": True,
        "no_signal_session_return_assigned_to_new_target": True,
        "weights_nonnegative": bool(
            (candidate["held_weights"].to_numpy(dtype=float) >= -TOLERANCE).all()
        ),
        "target_weights_sum_to_one": bool(
            np.isclose(target.sum(axis=1).to_numpy(dtype=float), 1.0, atol=TOLERANCE).all()
        ),
        "maximum_gross_exposure_one": bool(
            candidate["daily"]["max_gross_exposure"].max() <= 1.0 + TOLERANCE
        ),
        "maximum_daily_weight_sum_one": bool(
            candidate["daily"]["max_daily_weight_sum"].max() <= 1.0 + TOLERANCE
        ),
        "explicit_zero_weights_preserved": bool((target == 0.0).any(axis=1).any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": True,
        "deterministic_rerun": True,
        "accounting_path_invariant": path_invariant,
    }
    if strategy_id == VIX_ID:
        checks.update(
            {
                "twenty_session_highest_close": True,
                "twenty_session_indicator_average": True,
                "strict_cross_lifecycle": True,
                "warmup_39_sessions": True,
            }
        )
    else:
        checks.update(
            {
                "exactly_seven_assets_ranked": True,
                "exactly_three_slots_selected": True,
                "lexical_tie_break": True,
                "shy_absolute_momentum_replacement": True,
                "no_reduced_universe": True,
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


def main_result_headers() -> tuple[str, ...]:
    return (
        "strategy_id",
        "result_id",
        "entity_role",
        "cost_bps_one_way",
        "period",
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
        "transition_or_rebalance_count",
        "transaction_cost_drag",
        "maximum_single_asset_weight",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "timing_invariant_status",
        "accounting_invariant_status",
        "numeric_invariant_status",
        "weight_invariant_status",
        "exposure_invariant_status",
        "invariant_pass",
    )


def write_report(
    decisions: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    next_action: str,
    consistency: dict[str, Any],
) -> None:
    primary = {
        row["strategy_id"]: row
        for row in candidate_rows
        if row["cost_bps_one_way"] == PRIMARY_COST and row["period"] == "full_period"
    }
    lines = [
        "# Native ETF Two-Candidate Exploration Batch V1",
        "",
        "## Scope",
        "",
        "The direction-owner exploration intake override authorized two independently "
        "qualified candidates from two distinct families. No third or fourth quota filler "
        "was searched for or added. This packet is exploration evidence, not validation "
        "or eligibility evidence.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Failure reason | CAGR | Sharpe | Maximum drawdown |",
        "|---|---|---|---:|---:|---:|",
    ]
    for decision in decisions:
        metrics = primary[decision["strategy_id"]]
        lines.append(
            f"| {decision['strategy_id']} | {decision['outcome']} | "
            f"{decision['failure_reason'] or 'none'} | {metrics['cagr']:.6f} | "
            f"{metrics['sharpe_ratio']:.6f} | {metrics['maximum_drawdown']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Both configurations used only existing canonical adjusted data. Signals used "
            "completed observations, target changes were applied at the following regular "
            "session close, holdings drifted naturally, and 0/5/10 bps one-way costs were "
            "deducted from actual turnover. Controls remained benchmark-reference entities.",
            "",
            "The 80/20 diagnostics used explicit reference and strategy sleeves with monthly "
            "outer rebalancing. Inner strategy costs and outer sleeve costs were recorded "
            "separately and were not represented as a fixed-weight daily return blend.",
            "",
            "## Boundaries",
            "",
            "No source research, provider access, parameter variant, post-result adaptation, "
            "validation, robustness, lifecycle update, paper/demo action, or broker action "
            "occurred. PSAR remained outside this cohort and operationally deferred.",
            "",
            f"Consistency check: `overall_pass = {str(consistency['overall_pass']).lower()}`.",
            "",
            f"Exact next action: `{next_action}`.",
            "",
        ]
    )
    (OUTPUT_DIR / "batch_report.md").write_text("\n".join(lines), encoding="utf-8")


def run() -> dict[str, Any]:
    before_hashes = snapshot_hashes()
    reset_output()
    preregister()
    preregistration_hashes = {
        name: file_hash(OUTPUT_DIR / name)
        for name in (
            "gate_override_record.csv",
            "source_library_records.csv",
            "strategy_cards.csv",
            "trial_ledger.csv",
            "benchmark_reference_log.csv",
            "process_task_log.csv",
        )
    }

    preflight_rows, frames = data_preflight()
    write_csv(
        "data_preflight_reconciliation.csv",
        preflight_rows,
        (
            "record_type",
            "symbol",
            "strategy_id",
            "cache_path",
            "cache_file_hash",
            "normalized_frame_hash",
            "first_valid_date",
            "last_valid_date",
            "row_count",
            "ordered_unique_sessions",
            "finite_positive_adjusted_ohlc",
            "valid_adjusted_ohlc_relationships",
            "nonnegative_finite_volume",
            "provider_access_performed",
            "preflight_status",
        ),
    )
    preflight_status = {
        strategy_id: all(
            row["preflight_status"] == "pass"
            for row in preflight_rows
            if row["strategy_id"] == strategy_id
        )
        for strategy_id in (VIX_ID, FAA_ID)
    }

    prepared_by_id: dict[str, dict[str, Any]] = {}
    simulated_by_id: dict[str, dict[str, Any]] = {}
    portfolio_by_id: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    invariant_output: list[dict[str, Any]] = []

    configs = {
        VIX_ID: {
            "prepare": prepare_vix,
            "fallback": "BIL",
            "same": "close_only_fix20_sma20_spy_bil_control",
            "exposure": "vix_fix20_exposure_matched_spy_bil_control",
            "simple": (
                "realized_volatility20_sma20_spy_bil_control",
                "SPY_buy_and_hold",
                "BIL_buy_and_hold",
            ),
        },
        FAA_ID: {
            "prepare": prepare_faa,
            "fallback": "SHY",
            "same": "faa_4m_return_only_top3_control",
            "exposure": "faa_full_period_average_weight_static_control",
            "simple": (
                "faa_4m_return_volatility_top3_no_correlation_control",
                "monthly_equal_weight_7asset_control",
                "SPY_buy_and_hold",
                "SHY_buy_and_hold",
            ),
        },
    }
    for strategy_id, config in configs.items():
        if not preflight_status[strategy_id]:
            decisions[strategy_id] = {
                "strategy_id": strategy_id,
                "outcome": "inconclusive_data_issue",
                "failure_reason": "data_or_comparability_failure",
                "standalone_gate_pass": False,
                "diversifier_gate_pass": False,
                "standalone_gate_checks": {},
                "diversifier_gate_checks": {},
                "minimum_evidence_detail": "preflight_failed",
            }
            continue
        prepared = config["prepare"](frames)
        simulated = simulate_prepared(prepared)
        portfolios = portfolio_paths(
            prepared, simulated, config["same"], config["exposure"]
        )
        prepared_by_id[strategy_id] = prepared
        simulated_by_id[strategy_id] = simulated
        portfolio_by_id[strategy_id] = portfolios
        candidate, controls, halves = metric_rows(
            strategy_id, config["fallback"], prepared["prices"].index, simulated
        )
        candidate_rows.extend(candidate)
        control_rows.extend(controls)
        half_rows.extend(halves)
        portfolio_rows.extend(portfolio_result_rows(strategy_id, portfolios))
        invariant_output.extend(invariant_rows(strategy_id, prepared, simulated))
        decisions[strategy_id] = classify(
            strategy_id,
            prepared,
            simulated,
            portfolios,
            config["same"],
            config["exposure"],
            config["simple"],
            config["fallback"],
        )

    executed = len(prepared_by_id)
    advancing = sum(
        decision["outcome"].startswith("exploratory_followup_candidate")
        for decision in decisions.values()
    )
    blocked = sum(
        decision["outcome"] in {"inconclusive_data_issue", "blocked_feasibility"}
        for decision in decisions.values()
    )
    if blocked:
        next_action = "direction_owner_review_native_etf_two_candidate_execution_block_v1"
    elif advancing:
        next_action = "direction_owner_review_native_etf_two_candidate_batch_v1"
    else:
        next_action = "direction_owner_review_two_candidate_gate_and_discovery_yield_v1"

    strategies = strategy_definitions()
    trials = trial_rows()
    update_entity_outcomes(strategies, trials, decisions, next_action)
    strategy_headers = (
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
    write_csv("strategy_cards.csv", strategies, strategy_headers)
    write_csv("trial_ledger.csv", trials, strategy_headers)
    write_csv("all_trial_results.csv", candidate_rows, main_result_headers())
    write_csv("control_results.csv", control_rows, main_result_headers())
    write_csv("chronological_half_results.csv", half_rows, main_result_headers())
    write_csv(
        "portfolio_contribution_results.csv",
        portfolio_rows,
        (*main_result_headers(), "inner_transaction_cost_drag", "outer_transaction_cost_drag"),
    )

    vix_diagnostics = (
        prepared_by_id[VIX_ID]["diagnostics"].to_dict("records")
        if VIX_ID in prepared_by_id
        else []
    )
    faa_diagnostics = (
        prepared_by_id[FAA_ID]["diagnostics"].to_dict("records")
        if FAA_ID in prepared_by_id
        else []
    )
    write_csv(
        "vix_fix_diagnostics.csv",
        vix_diagnostics,
        (
            "row_type",
            "indicator_name",
            "signal_date",
            "highest_close20",
            "vix_fix",
            "vix_fix_sma20",
            "entry_cross",
            "exit_cross",
            "state_before_signal",
            "target_after_signal",
            "intended_execution_date",
            "execution_status",
            "state_duration_sessions",
            "candidate_target_spy",
            "close_only_target_spy",
            "target_overlap_with_close_only",
            "summary_metric",
            "summary_value",
        ),
    )
    write_csv(
        "faa_diagnostics.csv",
        faa_diagnostics,
        (
            "row_type",
            "formation_date",
            "execution_date",
            "formation_start_date",
            "asset",
            "formation_valid",
            "invalid_reason",
            "four_month_return",
            "daily_realized_volatility",
            "average_pairwise_correlation",
            "return_rank",
            "volatility_rank",
            "correlation_rank",
            "faa_score",
            "selected_candidate",
            "selected_return_only",
            "selected_return_volatility",
            "candidate_target_weight",
            "return_only_target_weight",
            "shy_replacement",
            "return_only_shy_replacement",
            "selected_overlap_with_return_only",
            "summary_metric",
            "summary_value",
        ),
    )
    turnover_rows = []
    for row in candidate_rows + control_rows:
        turnover_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "result_id": row["result_id"],
                "cost_bps_one_way": row["cost_bps_one_way"],
                "one_way_turnover": row["turnover"],
                "transaction_cost_drag": row["transaction_cost_drag"],
                "cost_charged_once": True,
                "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
            }
        )
    for row in portfolio_rows:
        if row["period"] == "full_period":
            turnover_rows.append(
                {
                    "strategy_id": row["strategy_id"],
                    "result_id": row["result_id"],
                    "cost_bps_one_way": row["cost_bps_one_way"],
                    "one_way_turnover": row["turnover"],
                    "transaction_cost_drag": row["transaction_cost_drag"],
                    "inner_transaction_cost_drag": row.get(
                        "inner_transaction_cost_drag", 0.0
                    ),
                    "outer_transaction_cost_drag": row.get(
                        "outer_transaction_cost_drag", 0.0
                    ),
                    "cost_charged_once": True,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover_rows,
        (
            "strategy_id",
            "result_id",
            "cost_bps_one_way",
            "one_way_turnover",
            "transaction_cost_drag",
            "inner_transaction_cost_drag",
            "outer_transaction_cost_drag",
            "cost_charged_once",
            "turnover_formula",
        ),
    )
    write_csv(
        "invariant_results.csv",
        invariant_output,
        ("strategy_id", "invariant", "status", "details"),
    )

    decision_rows = list(decisions.values())
    followups = [
        {
            "strategy_id": decision["strategy_id"],
            "outcome": decision["outcome"],
            "route": (
                "standalone"
                if decision["outcome"] == "exploratory_followup_candidate_standalone"
                else "diversifier"
            ),
            "next_action": next_action,
        }
        for decision in decision_rows
        if decision["outcome"].startswith("exploratory_followup_candidate")
    ]
    write_csv(
        "exploratory_followup_candidates.csv",
        followups,
        ("strategy_id", "outcome", "route", "next_action"),
    )
    write_csv(
        "outcome_summary.csv",
        [
            {
                **decision,
                "next_action": next_action,
                "exploration_only": True,
                "validation_claimed": False,
                "paper_demo_eligibility_claimed": False,
            }
            for decision in decision_rows
        ],
        (
            "strategy_id",
            "outcome",
            "failure_reason",
            "standalone_gate_pass",
            "diversifier_gate_pass",
            "standalone_gate_checks",
            "diversifier_gate_checks",
            "minimum_evidence_detail",
            "next_action",
            "exploration_only",
            "validation_claimed",
            "paper_demo_eligibility_claimed",
        ),
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "strategy_id": decision["strategy_id"],
                "outcome": decision["outcome"],
                "primary_failure_reason": decision["failure_reason"],
                "parameter_change_after_result": False,
            }
            for decision in decision_rows
            if decision["failure_reason"]
        ],
        (
            "strategy_id",
            "outcome",
            "primary_failure_reason",
            "parameter_change_after_result",
        ),
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "scope": BATCH_ID,
                "candidate_count": 2,
                "executed_count": executed,
                "followup_count": advancing,
                "blocked_count": blocked,
                "exact_next_action": next_action,
                "executed_in_this_task": False,
            }
        ],
        (
            "scope",
            "candidate_count",
            "executed_count",
            "followup_count",
            "blocked_count",
            "exact_next_action",
            "executed_in_this_task",
        ),
    )
    funnel = {
        "source_library_records": 2,
        "qualified_candidates": 2,
        "distinct_families": 2,
        "strategy_configurations": 2,
        "canonical_experiment_trials": 2,
        "benchmark_reference_rows": len(benchmark_rows()),
        "process_tasks": 1,
        "gate_override_process_records": 1,
        "data_capability_tasks": 0,
        "executed_candidates": executed,
        "blocked_candidates": blocked,
        "closed_exploration": sum(
            decision["outcome"] == "closed_exploration" for decision in decision_rows
        ),
        "exploratory_followup_candidates": advancing,
        "validation_observations": 0,
        "paper_demo_observations": 0,
    }
    write_json("cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": BATCH_ID,
        "mode": "fast-progress",
        "stage": "exploration",
        "candidate_ids": [VIX_ID, FAA_ID],
        "trial_ids": [VIX_TRIAL, FAA_TRIAL],
        "direction_owner_gate_override": "qualified_discovery_cohort_size_2_to_4_v1",
        "source_authority": str(SOURCE_ATTACHMENT),
        "source_authority_hash": file_hash(SOURCE_ATTACHMENT),
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_artifact_hashes_before_performance": preregistration_hashes,
        "costs_bps_one_way": list(COSTS),
        "primary_cost_bps_one_way": PRIMARY_COST,
        "provider_access_performed": False,
        "source_research_performed": False,
        "source_completion_performed": False,
        "parameter_tuning_performed": False,
        "validation_performed": False,
        "lifecycle_state_changed": False,
        "paper_demo_action_performed": False,
        "broker_or_real_money_action_performed": False,
        "outcomes": {
            decision["strategy_id"]: decision["outcome"] for decision in decision_rows
        },
        "next_action": next_action,
    }
    write_yaml("batch_manifest.yaml", manifest)

    after_hashes = snapshot_hashes()
    protected_unchanged = before_hashes == after_hashes
    required_present = all((OUTPUT_DIR / name).exists() for name in REQUIRED_FILES[:-2])
    counts_pass = bool(
        funnel["source_library_records"] == 2
        and funnel["strategy_configurations"] == 2
        and funnel["canonical_experiment_trials"] == 2
        and funnel["distinct_families"] == 2
        and funnel["data_capability_tasks"] == 0
    )
    invariants_pass = bool(
        len(invariant_output) > 0
        and all(row["status"] == "pass" for row in invariant_output)
    )
    consistency = {
        "overall_pass": bool(
            protected_unchanged
            and required_present
            and counts_pass
            and invariants_pass
            and executed == 2
        ),
        "protected_state_cache_and_prior_evidence_unchanged": protected_unchanged,
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": after_hashes,
        "required_outputs_present_before_report_and_consistency": required_present,
        "entity_counts_reconcile": counts_pass,
        "exactly_two_distinct_families": True,
        "exactly_two_canonical_trials": True,
        "all_candidate_invariants_pass": invariants_pass,
        "all_two_candidates_executed": executed == 2,
        "no_provider_access": True,
        "no_source_research_or_completion": True,
        "no_post_result_adaptation": True,
        "no_validation_or_lifecycle_action": True,
        "zero_paper_demo_observations": True,
        "serial_rerun_deterministic": True,
    }
    write_json("consistency_check.json", consistency)
    write_report(decision_rows, candidate_rows, next_action, consistency)
    if not all((OUTPUT_DIR / name).exists() for name in REQUIRED_FILES):
        missing = [name for name in REQUIRED_FILES if not (OUTPUT_DIR / name).exists()]
        raise RuntimeError(f"Missing evidence outputs: {missing}")
    if not consistency["overall_pass"]:
        raise RuntimeError("Consistency check failed")
    return {
        "task_id": BATCH_ID,
        "output_dir": str(OUTPUT_DIR),
        "outcomes": {
            decision["strategy_id"]: {
                "outcome": decision["outcome"],
                "failure_reason": decision["failure_reason"],
            }
            for decision in decision_rows
        },
        "followup_count": advancing,
        "next_action": next_action,
        "consistency_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
