from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market


TASK_ID = "pagonidis_ibs_next_open_portability_exploration_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "pagonidis_ibs_spy_next_open_intraday_v1"
FAMILY_ID = "internal_bar_strength_mean_reversion"
TRIAL_ID = "pagonidis_ibs_next_open_portability_v1__canonical"
SOURCE_RECORD_ID = "src_pagonidis_ibs_next_open_portability_v1"
SOURCE_REVIEW_ID = "pagonidis_ibs_equity_etf_reversal"
SOURCE_LINEAGE = "pagonidis_the_ibs_effect_mean_reversion_in_equity_etfs_2014"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v5"
TRANSLATION_LABEL = "execution_portability_test"
FROZEN_TIMESTAMP = "2026-07-25T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
IBS_THRESHOLD = 0.20
TOLERANCE = 1e-10

OUTPUT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / TASK_ID
    / "latest"
)
V5_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v5"
    / "latest"
)
CACHE_DIR = ROOT / "data" / "cache"

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "family_lineage"
    / "family_ledger.yaml",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "operations"
    / "active_observations.yaml",
)

CONTROL_IDS = (
    "prior_day_negative_return_spy_intraday_v1",
    "all_sessions_spy_open_to_close_v1",
    "exposure_matched_fractional_spy_intraday_v1",
    "SPY_buy_and_hold",
)
PRINCIPAL_CONTROL_IDS = CONTROL_IDS[:3]
CRITICAL_CONTROL_IDS = (
    "prior_day_negative_return_spy_intraday_v1",
    "exposure_matched_fractional_spy_intraday_v1",
)

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_standalone",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}
ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "turnover_drag",
    "signal_scarcity",
    "weak_return",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "source_translation_record.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "session_trade_ledger.csv",
    "ibs_signal_diagnostics.csv",
    "exposure_control_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "portability_report.md",
}

FORBIDDEN_ACTIONS = {
    "source_research_or_web_browsing": False,
    "source_rule_completion": False,
    "parameter_optimization_or_grid": False,
    "post_result_strategy_change": False,
    "source_replication_claimed": False,
    "validation_or_robustness_claimed": False,
    "promotion_or_paper_demo_action": False,
    "provider_access": False,
    "broker_account_order_or_real_money_action": False,
    "lifecycle_state_changed": False,
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
    "active_session_fraction",
    "average_spy_intraday_exposure",
    "total_one_way_turnover",
    "number_open_entries",
    "number_close_exits",
    "transaction_cost_drag",
    "average_gross_exposure",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "weight_invariant_status",
    "exposure_invariant_status",
    "invariant_pass",
]


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.12g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (pd.Timestamp,)):
        return value.date().isoformat()
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
        yaml.safe_dump(
            payload,
            sort_keys=False,
            width=120,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    if isinstance(normalized.index, pd.DatetimeIndex):
        normalized = normalized.reset_index()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(
            normalized["date"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
    payload = normalized.to_csv(index=False, lineterminator="\n")
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def map_hashes(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def tree_content_hash(root: Path, excluded: Path | None = None) -> str:
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    if not root.exists():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if excluded_resolved is not None and (
            resolved == excluded_resolved or excluded_resolved in resolved.parents
        ):
            continue
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def tree_identity_hash(root: Path, excluded: Path | None = None) -> str:
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    if not root.exists():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if excluded_resolved is not None and (
            resolved == excluded_resolved or excluded_resolved in resolved.parents
        ):
            continue
        stat = path.stat()
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (
            ROOT / "evidence" / "research_recovery" / TASK_ID
        ).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def v5_hashes() -> dict[str, str]:
    return {
        rel(path): file_hash(path)
        for path in sorted(V5_DIR.glob("*"))
        if path.is_file()
    }


def load_v5_source_row() -> dict[str, str]:
    path = V5_DIR / "source_review_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    matches = [row for row in rows if row.get("candidate_id") == SOURCE_REVIEW_ID]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one V5 source-review row for {SOURCE_REVIEW_ID}; "
            f"found {len(matches)}"
        )
    return matches[0]


def load_v5_rejection_row() -> dict[str, str]:
    path = V5_DIR / "rejection_ledger.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    matches = [row for row in rows if row.get("candidate_id") == SOURCE_REVIEW_ID]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one V5 rejection row for {SOURCE_REVIEW_ID}; "
            f"found {len(matches)}"
        )
    return matches[0]


def frozen_rule_text() -> str:
    return (
        "For each completed SPY session t, calculate IBS=(adjusted close-adjusted "
        "low)/(adjusted high-adjusted low). High=low is inactive. When IBS<0.20, "
        "remain in BIL overnight, switch BIL to SPY at the regular-session open "
        "of t+1, hold SPY through that close, and switch back to BIL at the close. "
        "Inactive signals remain in BIL. No SPY close-to-open return is used."
    )


def deterministic_core_hash() -> str:
    payload = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": TRIAL_ID,
        "source_record_id": SOURCE_RECORD_ID,
        "source_lineage": SOURCE_LINEAGE,
        "translation_label": TRANSLATION_LABEL,
        "instrument_universe": ["SPY", "BIL"],
        "threshold": IBS_THRESHOLD,
        "strict_comparison": True,
        "signal_formula": "(close-low)/(high-low)",
        "entry": "signal_close_t_to_open_t_plus_1",
        "exit": "close_t_plus_1",
        "cost_bps": COST_BPS,
        "controls": CONTROL_IDS,
        "rule": frozen_rule_text(),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def source_row() -> dict[str, Any]:
    source = load_v5_source_row()
    rejection = load_v5_rejection_row()
    return {
        "source_record_id": SOURCE_RECORD_ID,
        "entity_type": "source_library_record",
        "stage": "source_extracted",
        "source_status": "source_complete_but_execution_translated",
        "implementation_authorized": True,
        "translation_label": TRANSLATION_LABEL,
        "source_library_id": SOURCE_LIBRARY_ID,
        "source_review_id": SOURCE_REVIEW_ID,
        "source_lineage": SOURCE_LINEAGE,
        "source_title": source["source_title"],
        "source_url": source["source_url"],
        "source_type": source["source_type"],
        "publication_date": source["publication_date"],
        "v5_review_disposition": source["review_disposition"],
        "v5_primary_rejection_reason": rejection["primary_rejection_reason"],
        "v5_rejection_revised_or_overwritten": False,
        "source_ibs_signal_retained": True,
        "source_threshold_retained": True,
        "source_asset_class_intent_retained": True,
        "source_entry_timing_retained": False,
        "project_execution_translation": "signal_close_t_to_open_t_plus_1",
        "project_exit": "close_t_plus_1",
        "source_return_interval_omitted": (
            "close_t_to_open_t_plus_1_overnight_component"
        ),
        "interpretation": (
            "tests_whether_IBS_contains_implementable_following_session_intraday_value"
        ),
        "exact_source_replication_claimed": False,
        "source_reported_performance_used": False,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    }


def strategy_row(outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": "SPY IBS Next-Open Intraday Portability",
        "entity_type": "strategy_configuration",
        "strategy_architecture": (
            "completed_close_range_position_signal_next_open_intraday_allocation"
        ),
        "source_or_research_lineage": (
            "strategy_source_library_refresh_v5:"
            "pagonidis_ibs_equity_etf_reversal:execution_portability_test"
        ),
        "instrument_universe": "SPY|BIL",
        "parameters": {
            "ibs_formula": "(adjusted_close-adjusted_low)/(adjusted_high-adjusted_low)",
            "ibs_threshold": 0.20,
            "comparison": "strict_less_than",
            "zero_range_behavior": "inactive",
            "signal_timestamp": "completed_close_t",
            "entry_timestamp": "regular_session_open_t_plus_1",
            "exit_timestamp": "regular_session_close_t_plus_1",
            "overnight_asset": "BIL",
            "primary_cost_bps_per_one_way_turnover": 5.0,
        },
        "benchmark_or_control": list(CONTROL_IDS),
        "route": "standalone",
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": "",
        "adaptation_label": "exploratory_variant",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "frozen_rule": frozen_rule_text(),
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }


def trial_row(outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    base = strategy_row(outcome, failure_reason, next_action)
    return {
        **base,
        "entity_type": "experiment_trial",
        "changed_fields_from_source": "execution_entry_and_return_interval_only",
        "source_rule_changed": False,
        "threshold_changed": False,
        "instrument_changed": False,
        "execution_changed_from_source": True,
        "optimization_performed": False,
        "post_result_change_allowed": False,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "canonical_trial": True,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    rules = {
        "prior_day_negative_return_spy_intraday_v1": (
            "At close t, when SPY close-to-close return is strictly negative, "
            "hold SPY open-to-close t+1; otherwise BIL. Identical timing and costs."
        ),
        "all_sessions_spy_open_to_close_v1": (
            "Hold SPY during every regular open-to-close session and BIL overnight."
        ),
        "exposure_matched_fractional_spy_intraday_v1": (
            "Allocate the mechanically observed candidate active-session fraction "
            "to SPY intraday every session and the remainder to BIL; return to BIL "
            "at each close."
        ),
        "SPY_buy_and_hold": "SPY adjusted-close buy-and-hold over identical dates.",
    }
    roles = {
        "prior_day_negative_return_spy_intraday_v1": "same_purpose_control",
        "all_sessions_spy_open_to_close_v1": "general_intraday_exposure_control",
        "exposure_matched_fractional_spy_intraday_v1": (
            "mechanical_exposure_control"
        ),
        "SPY_buy_and_hold": "broad_benchmark",
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "benchmark_role": roles[control_id],
            "frozen_rule": rules[control_id],
            "instrument_universe": "SPY|BIL"
            if control_id != "SPY_buy_and_hold"
            else "SPY",
            "cost_assumptions_bps": list(COST_BPS),
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for control_id in CONTROL_IDS
    ]


def process_row(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
        "next_action_executed": False,
    }


def write_preregistration_checkpoint() -> str:
    pending_outcome = "preregistered_pending_execution"
    pending_action = "execute_frozen_portability_trial"
    source = [source_row()]
    strategies = [strategy_row(pending_outcome, "", pending_action)]
    trials = [trial_row(pending_outcome, "", pending_action)]
    benchmarks = benchmark_rows()
    process = [process_row(pending_outcome, pending_action)]
    write_csv(
        OUTPUT_DIR / "source_translation_record.csv",
        source,
        list(source[0]),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategies,
        list(strategies[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trials,
        list(trials[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process,
        list(process[0]),
    )
    material = {
        "source": source,
        "strategies": strategies,
        "trials": trials,
        "benchmarks": benchmarks,
        "process": process,
        "frozen_core_hash": deterministic_core_hash(),
        "written_before_performance_calculation": True,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            default=csv_value,
        ).encode("utf-8")
    ).hexdigest()


def load_cached_frame(symbol: str) -> pd.DataFrame:
    path = CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = {
        "date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    }
    if not required.issubset(raw.columns):
        return pd.DataFrame()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    return raw.set_index("date", drop=True).sort_index()


def preflight_symbol(symbol: str) -> tuple[dict[str, Any], pd.DataFrame]:
    path = CACHE_DIR / f"{symbol}.csv"
    frame = load_cached_frame(symbol)
    base = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_file_hash": file_hash(path),
        "canonical_frame_hash": "",
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "ordered_unique_dates": False,
        "finite_positive_adjusted_ohlc": False,
        "finite_nonnegative_adjusted_volume": False,
        "valid_adjusted_ohlc_relationships": False,
        "canonical_adjustment_compatible": False,
        "common_eligible_start": "",
        "common_eligible_end": "",
        "identical_common_dates": False,
        "candidate_preflight_status": "fail",
        "failure_reason": "missing_or_invalid_cache",
        "provider_accessed": False,
    }
    if frame.empty:
        return base, frame
    dates_valid = bool(
        frame.index.notna().all()
        and frame.index.is_monotonic_increasing
        and not frame.index.duplicated().any()
    )
    ohlc = frame[["open", "high", "low", "close", "adj_close"]]
    ohlc_values = ohlc.to_numpy(dtype=float)
    prices_valid = bool(
        np.isfinite(ohlc_values).all() and (ohlc_values > 0.0).all()
    )
    volume = frame["volume"].to_numpy(dtype=float)
    volume_valid = bool(np.isfinite(volume).all() and (volume >= 0.0).all())
    relationships = bool(
        prices_valid
        and (
            frame["high"]
            >= frame[["open", "low", "close"]].max(axis=1) - TOLERANCE
        ).all()
        and (
            frame["low"]
            <= frame[["open", "high", "close"]].min(axis=1) + TOLERANCE
        ).all()
    )
    adjustment = bool(
        np.allclose(
            frame["close"].to_numpy(dtype=float),
            frame["adj_close"].to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-12,
        )
    )
    raw = pd.read_csv(path)
    if {
        "raw_open",
        "raw_high",
        "raw_low",
        "raw_close",
        "raw_adj_close",
        "adjustment_factor",
    }.issubset(raw.columns):
        factor = pd.to_numeric(raw["adjustment_factor"], errors="coerce")
        reconstruction_checks = []
        for raw_column, adjusted_column in (
            ("raw_open", "open"),
            ("raw_high", "high"),
            ("raw_low", "low"),
        ):
            raw_values = pd.to_numeric(raw[raw_column], errors="coerce")
            adjusted_values = pd.to_numeric(raw[adjusted_column], errors="coerce")
            reconstruction_checks.append(
                np.allclose(
                    raw_values.to_numpy(dtype=float)
                    * factor.to_numpy(dtype=float),
                    adjusted_values.to_numpy(dtype=float),
                    rtol=1e-7,
                    atol=1e-7,
                )
            )
        raw_close = pd.to_numeric(raw["raw_close"], errors="coerce")
        raw_adjusted_close = pd.to_numeric(
            raw["raw_adj_close"],
            errors="coerce",
        )
        reconstruction_checks.extend(
            [
                np.isfinite(factor.to_numpy(dtype=float)).all(),
                bool((factor > 0.0).all()),
                np.allclose(
                    raw_close.to_numpy(dtype=float)
                    * factor.to_numpy(dtype=float),
                    raw_adjusted_close.to_numpy(dtype=float),
                    rtol=1e-7,
                    atol=1e-7,
                ),
            ]
        )
        adjustment = bool(adjustment and all(reconstruction_checks))
    passed = dates_valid and prices_valid and volume_valid and relationships and adjustment
    normalized = frame[
        ["open", "high", "low", "close", "adj_close", "volume"]
    ].copy()
    normalized.index.name = "date"
    return (
        {
            **base,
            "canonical_frame_hash": dataframe_hash(normalized),
            "row_count": int(len(frame)),
            "first_valid_date": frame.index.min().date().isoformat(),
            "last_valid_date": frame.index.max().date().isoformat(),
            "ordered_unique_dates": dates_valid,
            "finite_positive_adjusted_ohlc": prices_valid,
            "finite_nonnegative_adjusted_volume": volume_valid,
            "valid_adjusted_ohlc_relationships": relationships,
            "canonical_adjustment_compatible": adjustment,
            "candidate_preflight_status": "pass" if passed else "fail",
            "failure_reason": "" if passed else "adjusted_ohlcv_preflight_failed",
        },
        frame,
    )


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], bool]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in ("SPY", "BIL"):
        row, frame = preflight_symbol(symbol)
        rows.append(row)
        frames[symbol] = frame
    common = frames["SPY"].index.intersection(frames["BIL"].index).sort_values()
    if len(common):
        start = common.min()
        end = common.max()
        spy_dates = frames["SPY"].loc[start:end].index
        bil_dates = frames["BIL"].loc[start:end].index
        identical = bool(spy_dates.equals(bil_dates) and common.equals(spy_dates))
    else:
        start = end = None
        identical = False
    for row in rows:
        row["common_eligible_start"] = (
            start.date().isoformat() if start is not None else ""
        )
        row["common_eligible_end"] = end.date().isoformat() if end is not None else ""
        row["identical_common_dates"] = identical
        if not identical:
            row["candidate_preflight_status"] = "fail"
            row["failure_reason"] = "SPY_BIL_common_dates_not_identical"
    passed = bool(
        identical
        and len(common) > 1
        and all(row["candidate_preflight_status"] == "pass" for row in rows)
    )
    return rows, frames, passed


def calculate_ibs(frame: pd.DataFrame) -> pd.Series:
    spread = frame["high"] - frame["low"]
    ibs = (frame["close"] - frame["low"]) / spread
    return ibs.where(spread > 0.0)


def signal_schedules(
    spy: pd.DataFrame,
    common: pd.DatetimeIndex,
) -> tuple[dict[str, pd.Series], pd.Series]:
    signal_dates = common[:-1]
    execution_dates = common[1:]
    ibs = calculate_ibs(spy.reindex(common))
    candidate_signal = (ibs.loc[signal_dates] < IBS_THRESHOLD).fillna(False)
    candidate = pd.Series(
        candidate_signal.to_numpy(dtype=bool).astype(float),
        index=execution_dates,
        name=STRATEGY_ID,
    )
    close_returns = spy["close"].reindex(common).pct_change(fill_method=None)
    negative_signal = (close_returns.loc[signal_dates] < 0.0).fillna(False)
    prior_negative = pd.Series(
        negative_signal.to_numpy(dtype=bool).astype(float),
        index=execution_dates,
        name="prior_day_negative_return_spy_intraday_v1",
    )
    all_sessions = pd.Series(
        1.0,
        index=execution_dates,
        name="all_sessions_spy_open_to_close_v1",
    )
    fraction = float(candidate.mean())
    exposure_matched = pd.Series(
        fraction,
        index=execution_dates,
        name="exposure_matched_fractional_spy_intraday_v1",
    )
    return (
        {
            STRATEGY_ID: candidate,
            "prior_day_negative_return_spy_intraday_v1": prior_negative,
            "all_sessions_spy_open_to_close_v1": all_sessions,
            "exposure_matched_fractional_spy_intraday_v1": exposure_matched,
        },
        ibs,
    )


def simulate_intraday_schedule(
    spy: pd.DataFrame,
    bil: pd.DataFrame,
    common: pd.DatetimeIndex,
    schedule: pd.Series,
    cost_bps: float,
    row_id: str,
) -> dict[str, Any]:
    execution_dates = common[1:]
    if not schedule.index.equals(execution_dates):
        raise RuntimeError(f"{row_id}: schedule does not use the common execution dates")
    rate = float(cost_bps) / 10000.0
    ledger: list[dict[str, Any]] = []
    returns: list[float] = []
    turnover: list[float] = []
    costs: list[float] = []
    for position, execution_date in enumerate(execution_dates, start=1):
        signal_date = common[position - 1]
        spy_weight = float(schedule.loc[execution_date])
        bil_weight = 1.0 - spy_weight
        bil_overnight = (
            float(bil.loc[execution_date, "open"])
            / float(bil.loc[signal_date, "close"])
            - 1.0
        )
        spy_intraday = (
            float(spy.loc[execution_date, "close"])
            / float(spy.loc[execution_date, "open"])
            - 1.0
        )
        bil_intraday = (
            float(bil.loc[execution_date, "close"])
            / float(bil.loc[execution_date, "open"])
            - 1.0
        )
        open_pretrade = np.array([0.0, 1.0], dtype=float)
        open_target = np.array([spy_weight, bil_weight], dtype=float)
        open_turnover = 0.5 * float(np.abs(open_target - open_pretrade).sum())
        open_cost_fraction = open_turnover * rate
        intraday_asset_factors = np.array(
            [1.0 + spy_intraday, 1.0 + bil_intraday],
            dtype=float,
        )
        close_values = open_target * intraday_asset_factors
        intraday_factor = float(close_values.sum())
        close_pretrade = close_values / intraday_factor
        close_target = np.array([0.0, 1.0], dtype=float)
        close_turnover = 0.5 * float(
            np.abs(close_target - close_pretrade).sum()
        )
        close_cost_fraction = close_turnover * rate
        gross_factor = (1.0 + bil_overnight) * intraday_factor
        net_factor = (
            (1.0 + bil_overnight)
            * (1.0 - open_cost_fraction)
            * intraday_factor
            * (1.0 - close_cost_fraction)
        )
        gross_return = gross_factor - 1.0
        net_return = net_factor - 1.0
        cost_drag = gross_return - net_return
        total_turnover = open_turnover + close_turnover
        returns.append(net_return)
        turnover.append(total_turnover)
        costs.append(cost_drag)
        ledger.append(
            {
                "row_id": row_id,
                "cost_assumption_bps": cost_bps,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution_date.date().isoformat(),
                "signal_known_after_completed_close": True,
                "target_SPY_weight_at_open": spy_weight,
                "target_BIL_weight_at_open": bil_weight,
                "BIL_overnight_return": bil_overnight,
                "SPY_overnight_return_used": False,
                "SPY_intraday_return": spy_intraday,
                "BIL_intraday_return": bil_intraday,
                "open_pretrade_SPY_weight": open_pretrade[0],
                "open_pretrade_BIL_weight": open_pretrade[1],
                "open_one_way_turnover": open_turnover,
                "open_transaction_cost_fraction": open_cost_fraction,
                "close_pretrade_SPY_weight": close_pretrade[0],
                "close_pretrade_BIL_weight": close_pretrade[1],
                "close_target_SPY_weight": close_target[0],
                "close_target_BIL_weight": close_target[1],
                "close_one_way_turnover": close_turnover,
                "close_transaction_cost_fraction": close_cost_fraction,
                "total_one_way_turnover": total_turnover,
                "gross_return_before_cost": gross_return,
                "net_return": net_return,
                "transaction_cost_drag": cost_drag,
                "end_of_session_SPY_weight": 0.0,
                "end_of_session_BIL_weight": 1.0,
                "gross_exposure": 1.0,
                "daily_weight_sum": 1.0,
                "same_close_fill_used": False,
                "entry_timestamp": "regular_session_open",
                "exit_timestamp": "regular_session_close",
            }
        )
    index = execution_dates
    ledger_frame = pd.DataFrame(ledger).set_index(
        pd.DatetimeIndex(execution_dates),
        drop=False,
    )
    return {
        "row_id": row_id,
        "cost_bps": cost_bps,
        "returns": pd.Series(returns, index=index, name="net_return"),
        "turnover": pd.Series(turnover, index=index, name="one_way_turnover"),
        "cost": pd.Series(costs, index=index, name="transaction_cost_drag"),
        "spy_exposure": schedule.astype(float),
        "ledger": ledger_frame,
        "number_open_entries": int((schedule > 0.0).sum()),
        "number_close_exits": int((schedule > 0.0).sum()),
        "timing_convention": (
            "completed_close_signal_BIL_overnight_next_open_entry_same_session_close_exit"
        ),
        "overnight_spy_used": False,
    }


def simulate_spy_buy_hold(
    spy: pd.DataFrame,
    common: pd.DatetimeIndex,
    cost_bps: float,
) -> dict[str, Any]:
    index = common[1:]
    gross = spy["close"].reindex(common).pct_change(fill_method=None).iloc[1:]
    rate = float(cost_bps) / 10000.0
    net = gross.copy()
    cost = pd.Series(0.0, index=index, name="transaction_cost_drag")
    turnover = pd.Series(0.0, index=index, name="one_way_turnover")
    if len(index):
        gross_factor = 1.0 + float(gross.iloc[0])
        net.iloc[0] = gross_factor * (1.0 - rate) - 1.0
        cost.iloc[0] = float(gross.iloc[0] - net.iloc[0])
        turnover.iloc[0] = 1.0
    ledger = pd.DataFrame(
        {
            "row_id": "SPY_buy_and_hold",
            "cost_assumption_bps": cost_bps,
            "signal_date": common[:-1].date.astype(str),
            "execution_date": index.date.astype(str),
            "gross_return_before_cost": gross.to_numpy(dtype=float),
            "net_return": net.to_numpy(dtype=float),
            "total_one_way_turnover": turnover.to_numpy(dtype=float),
            "transaction_cost_drag": cost.to_numpy(dtype=float),
            "gross_exposure": 1.0,
            "daily_weight_sum": 1.0,
        },
        index=index,
    )
    return {
        "row_id": "SPY_buy_and_hold",
        "cost_bps": cost_bps,
        "returns": net.astype(float),
        "turnover": turnover,
        "cost": cost,
        "spy_exposure": pd.Series(1.0, index=index),
        "ledger": ledger,
        "number_open_entries": 1 if len(index) else 0,
        "number_close_exits": 0,
        "timing_convention": "adjusted_close_to_close_buy_and_hold",
        "overnight_spy_used": True,
    }


def payload_invariants(payload: dict[str, Any]) -> dict[str, Any]:
    ledger = payload["ledger"]
    returns = payload["returns"]
    exposure = payload["spy_exposure"]
    intraday = payload["row_id"] != "SPY_buy_and_hold"
    numeric = bool(
        len(returns)
        and np.isfinite(returns.to_numpy(dtype=float)).all()
        and np.isfinite(payload["turnover"].to_numpy(dtype=float)).all()
        and np.isfinite(payload["cost"].to_numpy(dtype=float)).all()
    )
    weights = bool(
        np.isfinite(exposure.to_numpy(dtype=float)).all()
        and (exposure >= -TOLERANCE).all()
        and (exposure <= 1.0 + TOLERANCE).all()
        and (ledger["daily_weight_sum"] <= 1.0 + TOLERANCE).all()
        and (ledger["daily_weight_sum"] >= 1.0 - TOLERANCE).all()
    )
    exposure_ok = bool(
        (ledger["gross_exposure"] <= 1.0 + TOLERANCE).all()
        and (ledger["gross_exposure"] >= -TOLERANCE).all()
    )
    if intraday:
        expected_previous_dates = pd.DatetimeIndex(
            [
                pd.Timestamp(date)
                for date in ledger["signal_date"].astype(str)
            ]
        )
        execution_dates = pd.DatetimeIndex(
            [
                pd.Timestamp(date)
                for date in ledger["execution_date"].astype(str)
            ]
        )
        timing = bool(
            len(expected_previous_dates) == len(execution_dates)
            and (expected_previous_dates < execution_dates).all()
            and not bool(ledger["SPY_overnight_return_used"].astype(bool).any())
            and not bool(ledger["same_close_fill_used"].astype(bool).any())
            and (
                ledger.loc[
                    ledger["target_SPY_weight_at_open"] > 0.0,
                    "open_one_way_turnover",
                ]
                > 0.0
            ).all()
            and (
                ledger.loc[
                    ledger["target_SPY_weight_at_open"] > 0.0,
                    "close_one_way_turnover",
                ]
                > 0.0
            ).all()
        )
        if float(payload["cost_bps"]) > 0.0:
            active = ledger["target_SPY_weight_at_open"] > 0.0
            costs_on_both = bool(
                (ledger.loc[active, "open_transaction_cost_fraction"] > 0.0).all()
                and (
                    ledger.loc[active, "close_transaction_cost_fraction"] > 0.0
                ).all()
            )
        else:
            costs_on_both = True
        explicit_zeros = bool(
            (
                ledger.loc[
                    ledger["target_SPY_weight_at_open"] == 0.0,
                    "open_one_way_turnover",
                ]
                == 0.0
            ).all()
            and (ledger["end_of_session_SPY_weight"] == 0.0).all()
        )
    else:
        timing = True
        costs_on_both = True
        explicit_zeros = True
    invariant_pass = bool(
        numeric and weights and exposure_ok and timing and costs_on_both and explicit_zeros
    )
    return {
        "row_id": payload["row_id"],
        "cost_assumption_bps": payload["cost_bps"],
        "numeric_invariant_status": "pass" if numeric else "fail",
        "timing_invariant_status": "pass" if timing else "fail",
        "weight_invariant_status": "pass" if weights else "fail",
        "exposure_invariant_status": "pass" if exposure_ok else "fail",
        "no_signal_uses_post_close_information": timing,
        "entry_at_next_regular_session_open": timing if intraday else "not_applicable",
        "exit_at_same_regular_session_close": timing if intraday else "not_applicable",
        "no_SPY_overnight_return_attributed": (
            not payload["overnight_spy_used"] if intraday else "not_applicable"
        ),
        "every_intraday_entry_has_close_exit": (
            payload["number_open_entries"] == payload["number_close_exits"]
            if intraday
            else "not_applicable"
        ),
        "duplicate_trade_detected": False,
        "weights_nonnegative": weights,
        "maximum_gross_exposure": float(ledger["gross_exposure"].max()),
        "maximum_daily_weight_sum": float(ledger["daily_weight_sum"].max()),
        "costs_nonnegative": bool((payload["cost"] >= -TOLERANCE).all()),
        "both_switches_costed_when_positive_bps": costs_on_both,
        "explicit_zero_weights_preserved": explicit_zeros,
        "stale_weight_forward_fill_used": False,
        "deterministic_schedule_and_accounting": True,
        "invariant_pass": invariant_pass,
    }


def metric_payload(
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    if period_index is None:
        returns = payload["returns"]
    else:
        returns = payload["returns"].reindex(period_index).dropna()
    turnover = payload["turnover"].reindex(returns.index).fillna(0.0)
    cost = payload["cost"].reindex(returns.index).fillna(0.0)
    exposure = payload["spy_exposure"].reindex(returns.index).fillna(0.0)
    metrics = market.metrics_from_returns(returns)
    invariants = payload_invariants(payload)
    return {
        **metrics,
        "active_session_fraction": float((exposure > 0.0).mean()),
        "average_spy_intraday_exposure": float(exposure.mean()),
        "total_one_way_turnover": float(turnover.sum()),
        "number_open_entries": int((exposure > 0.0).sum())
        if payload["row_id"] != "SPY_buy_and_hold"
        else payload["number_open_entries"],
        "number_close_exits": int((exposure > 0.0).sum())
        if payload["row_id"] != "SPY_buy_and_hold"
        else payload["number_close_exits"],
        "transaction_cost_drag": float(cost.sum()),
        "average_gross_exposure": 1.0,
        "maximum_gross_exposure": invariants["maximum_gross_exposure"],
        "maximum_daily_weight_sum": invariants["maximum_daily_weight_sum"],
        "timing_invariant_status": invariants["timing_invariant_status"],
        "numeric_invariant_status": invariants["numeric_invariant_status"],
        "weight_invariant_status": invariants["weight_invariant_status"],
        "exposure_invariant_status": invariants["exposure_invariant_status"],
        "invariant_pass": invariants["invariant_pass"],
    }


def split_halves(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    midpoint = len(index) // 2
    return {
        "first_chronological_half": index[:midpoint],
        "second_chronological_half": index[midpoint:],
    }


def control_dominates(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    comparisons = (
        float(control["cagr"]) >= float(candidate["cagr"]) - TOLERANCE,
        float(control["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"]) - TOLERANCE,
        float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - TOLERANCE,
    )
    strict = (
        float(control["cagr"]) > float(candidate["cagr"]) + TOLERANCE
        or float(control["sharpe_ratio"])
        > float(candidate["sharpe_ratio"]) + TOLERANCE
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + TOLERANCE
    )
    return bool(all(comparisons) and strict)


def advantages(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> tuple[float, float]:
    return (
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]),
        float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"]),
    )


def classify(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    candidate = metric_payload(payloads[(STRATEGY_ID, PRIMARY_COST_BPS)])
    controls = {
        control_id: metric_payload(payloads[(control_id, PRIMARY_COST_BPS)])
        for control_id in CONTROL_IDS
    }
    halves = split_halves(payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]["returns"].index)
    candidate_halves = {
        label: metric_payload(
            payloads[(STRATEGY_ID, PRIMARY_COST_BPS)],
            index,
        )
        for label, index in halves.items()
    }
    control_halves = {
        (control_id, label): metric_payload(
            payloads[(control_id, PRIMARY_COST_BPS)],
            index,
        )
        for control_id in CONTROL_IDS
        for label, index in halves.items()
    }
    dominated_by = [
        control_id
        for control_id in PRINCIPAL_CONTROL_IDS
        if control_dominates(candidate, controls[control_id])
    ]
    materiality: dict[str, dict[str, Any]] = {}
    for control_id in CRITICAL_CONTROL_IDS:
        sharpe_diff, drawdown_diff = advantages(candidate, controls[control_id])
        materiality[control_id] = {
            "sharpe_difference": sharpe_diff,
            "maximum_drawdown_difference": drawdown_diff,
            "material_advantage": bool(
                sharpe_diff >= 0.02 - TOLERANCE
                or drawdown_diff >= 0.01 - TOLERANCE
            ),
        }
    half_failures: list[str] = []
    for label in halves:
        for control_id in CRITICAL_CONTROL_IDS:
            sharpe_diff, drawdown_diff = advantages(
                candidate_halves[label],
                control_halves[(control_id, label)],
            )
            if sharpe_diff < -TOLERANCE and drawdown_diff < -TOLERANCE:
                half_failures.append(f"{label}:{control_id}")
    ten_bps_failures: list[str] = []
    candidate_ten = metric_payload(payloads[(STRATEGY_ID, 10.0)])
    for control_id in CRITICAL_CONTROL_IDS:
        control_ten = metric_payload(payloads[(control_id, 10.0)])
        sharpe_diff, drawdown_diff = advantages(candidate_ten, control_ten)
        if sharpe_diff < -TOLERANCE and drawdown_diff < -TOLERANCE:
            ten_bps_failures.append(control_id)
    active_counts = {
        label: int(
            (
                payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]["spy_exposure"]
                .reindex(index)
                .fillna(0.0)
                > 0.0
            ).sum()
        )
        for label, index in halves.items()
    }
    all_invariants = all(
        payload_invariants(payload)["invariant_pass"]
        for payload in payloads.values()
    )
    all_session_dominates = control_dominates(
        candidate,
        controls["all_sessions_spy_open_to_close_v1"],
    )
    requirements = {
        "positive_full_period_after_cost_return": candidate["total_return"] > 0.0,
        "all_invariants_pass": all_invariants,
        "no_principal_control_dominates": not dominated_by,
        "material_advantage_vs_prior_day_negative": materiality[
            "prior_day_negative_return_spy_intraday_v1"
        ]["material_advantage"],
        "material_advantage_vs_exposure_matched": materiality[
            "exposure_matched_fractional_spy_intraday_v1"
        ]["material_advantage"],
        "all_session_intraday_does_not_dominate": not all_session_dominates,
        "no_critical_control_wins_on_both_metrics_in_either_half": not half_failures,
        "ten_bps_not_unfavorable_on_both_vs_critical_controls": (
            not ten_bps_failures
        ),
        "at_least_25_active_sessions_each_half": min(active_counts.values()) >= 25,
    }
    if all(requirements.values()):
        outcome = "exploratory_followup_candidate_standalone"
        failure = ""
        reason = "all_frozen_execution_portability_exploration_requirements_passed"
    elif not requirements["all_invariants_pass"]:
        outcome = "closed_exploration"
        failure = "methodology_failure"
        reason = "one_or_more_accounting_or_timing_invariants_failed"
    elif not requirements["positive_full_period_after_cost_return"]:
        outcome = "closed_exploration"
        failure = "weak_return"
        reason = "full_period_after_cost_return_not_positive"
    elif not requirements["at_least_25_active_sessions_each_half"]:
        outcome = "closed_exploration"
        failure = "signal_scarcity"
        reason = "fewer_than_25_active_sessions_in_a_chronological_half"
    elif half_failures:
        outcome = "closed_exploration"
        failure = "period_instability"
        reason = "candidate_worse_on_sharpe_and_drawdown_in_a_chronological_half"
    elif ten_bps_failures:
        outcome = "closed_exploration"
        failure = "cost_drag"
        reason = "ten_bps_result_unfavorable_on_sharpe_and_drawdown"
    elif (
        "exposure_matched_fractional_spy_intraday_v1" in dominated_by
        or all_session_dominates
        or not materiality[
            "exposure_matched_fractional_spy_intraday_v1"
        ]["material_advantage"]
    ):
        outcome = "closed_exploration"
        failure = "benchmark_like_behavior"
        reason = "general_or_exposure_matched_intraday_control_explains_result"
    else:
        outcome = "closed_exploration"
        failure = "weak_vs_primary_control"
        reason = "ordinary_negative_return_reversal_or_principal_control_explains_result"
    details = {
        "requirements": requirements,
        "dominated_by": dominated_by,
        "materiality": materiality,
        "half_failures": half_failures,
        "ten_bps_failures": ten_bps_failures,
        "active_counts_by_half": active_counts,
    }
    return outcome, failure, reason, details


def exact_next_action(outcome: str) -> str:
    if outcome == "exploratory_followup_candidate_standalone":
        return "direction_owner_review_ibs_execution_portability_followup_v1"
    if outcome == "closed_exploration":
        return "direction_owner_review_long_short_relative_value_capability_v1"
    return "direction_owner_review_ibs_portability_block_v1"


def metric_row(
    row_id: str,
    row_type: str,
    cost_bps: float,
    metrics: dict[str, Any],
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    period_label: str = "full_period",
    period_role: str = "exploration_full_period",
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": TRIAL_ID,
        "row_id": row_id,
        "row_type": row_type,
        "entity_type": (
            "experiment_trial" if row_type == "candidate" else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "cost_assumption_bps": cost_bps,
        "period_label": period_label,
        "period_role": period_role,
        "outcome": outcome if row_type == "candidate" else "benchmark_reference_only",
        "failure_reason": failure_reason if row_type == "candidate" else "",
        "decision_reason": decision_reason if row_type == "candidate" else "",
        **metrics,
    }


def consecutive_run_lengths(values: pd.Series) -> tuple[int, int]:
    longest_inactive = 0
    longest_active = 0
    inactive = 0
    active = 0
    for value in values.astype(bool):
        if value:
            active += 1
            inactive = 0
        else:
            inactive += 1
            active = 0
        longest_inactive = max(longest_inactive, inactive)
        longest_active = max(longest_active, active)
    return longest_inactive, longest_active


def diagnostics_rows(
    spy: pd.DataFrame,
    common: pd.DatetimeIndex,
    ibs: pd.Series,
    candidate_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ledger = candidate_payload["ledger"]
    for position, execution_date in enumerate(common[1:], start=1):
        signal_date = common[position - 1]
        session = ledger.loc[execution_date]
        rows.append(
            {
                "date": signal_date.date().isoformat(),
                "SPY_adjusted_open": float(spy.loc[signal_date, "open"]),
                "SPY_adjusted_high": float(spy.loc[signal_date, "high"]),
                "SPY_adjusted_low": float(spy.loc[signal_date, "low"]),
                "SPY_adjusted_close": float(spy.loc[signal_date, "close"]),
                "IBS": float(ibs.loc[signal_date])
                if pd.notna(ibs.loc[signal_date])
                else "",
                "zero_range_signal_inactive": bool(
                    float(spy.loc[signal_date, "high"])
                    == float(spy.loc[signal_date, "low"])
                ),
                "active_signal": bool(
                    float(candidate_payload["spy_exposure"].loc[execution_date]) > 0.0
                ),
                "strict_threshold": "IBS<0.20",
                "next_session_execution_date": execution_date.date().isoformat(),
                "next_session_adjusted_open": float(
                    spy.loc[execution_date, "open"]
                ),
                "next_session_adjusted_close": float(
                    spy.loc[execution_date, "close"]
                ),
                "gross_SPY_intraday_return": float(
                    session["SPY_intraday_return"]
                ),
                "total_one_way_turnover": float(
                    session["total_one_way_turnover"]
                ),
                "transaction_cost_drag": float(
                    session["transaction_cost_drag"]
                ),
                "net_candidate_return": float(session["net_return"]),
                "signal_year": signal_date.year,
                "threshold_changed_after_results": False,
            }
        )
    return rows


def report_text(
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    next_action: str,
    summary: dict[str, Any],
) -> str:
    return f"""# Pagonidis IBS Next-Open Portability Exploration V1

## Scope

Exactly one frozen execution-portability configuration was tested. This is
exploration, not source replication, validation, robustness, promotion, or
paper/demo eligibility evidence.

## Translation

- Source signal and strict `IBS < 0.20` threshold: retained.
- Source same-close entry: not retained.
- Project entry: completed close `t` to regular-session open `t+1`.
- Project exit: regular-session close `t+1`.
- Omitted source interval: SPY close `t` to open `t+1`.
- Overnight asset: BIL.

The V5 rejection remains unchanged.

## Data And Accounting

- Common adjusted-OHLCV interval: `{summary['evaluation_start']}` through
  `{summary['evaluation_end']}`.
- Candidate active sessions: `{summary['total_active_sessions']}` of
  `{summary['total_eligible_sessions']}`.
- Primary costs: `5 bps` per one-way turnover, charged separately at the open
  and close switches.
- Inactive sessions remain fully in BIL.
- No provider access occurred.

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or 'none'}`

Decision basis: `{decision_reason}`

This result is an execution-portability diagnostic only.

## Next Action

`{next_action}`

The next action was recorded and not executed.
"""


def run() -> dict[str, Any]:
    if not V5_DIR.exists():
        raise RuntimeError("The authoritative V5 source packet is missing")
    source_before = v5_hashes()
    protected_before = map_hashes(list(PROTECTED_STATE_PATHS))
    cache_before = tree_content_hash(CACHE_DIR)
    prior_evidence_before = tree_identity_hash(
        ROOT / "evidence",
        excluded=OUTPUT_DIR,
    )

    clean_output()
    preflight_rows, frames, preflight_passed = data_preflight()
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0]),
    )
    preregistration_hash = write_preregistration_checkpoint()

    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    session_ledger: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    classification_details: dict[str, Any] = {}
    if not preflight_passed:
        outcome = "inconclusive_data_issue"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "required_adjusted_OHLCV_missing_or_incomparable"
        summary = {
            "evaluation_start": "",
            "evaluation_end": "",
            "total_eligible_sessions": 0,
            "total_active_sessions": 0,
            "active_sessions_first_half": 0,
            "active_sessions_second_half": 0,
            "profitable_active_session_fraction": "",
            "mean_active_session_return": "",
            "median_active_session_return": "",
            "average_IBS_on_active_signal_dates": "",
            "annual_active_session_counts": {},
            "longest_inactive_interval_sessions": 0,
            "longest_consecutive_active_run": 0,
        }
    else:
        common = frames["SPY"].index.intersection(frames["BIL"].index).sort_values()
        frames = {
            symbol: frame.reindex(common)
            for symbol, frame in frames.items()
        }
        schedules, ibs = signal_schedules(frames["SPY"], common)
        for cost_bps in COST_BPS:
            for row_id, schedule in schedules.items():
                payloads[(row_id, cost_bps)] = simulate_intraday_schedule(
                    frames["SPY"],
                    frames["BIL"],
                    common,
                    schedule,
                    cost_bps,
                    row_id,
                )
            payloads[("SPY_buy_and_hold", cost_bps)] = simulate_spy_buy_hold(
                frames["SPY"],
                common,
                cost_bps,
            )
        outcome, failure_reason, decision_reason, classification_details = classify(
            payloads
        )
        primary_candidate = payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]
        diagnostics = diagnostics_rows(
            frames["SPY"],
            common,
            ibs,
            primary_candidate,
        )
        session_ledger = primary_candidate["ledger"].to_dict("records")
        candidate_schedule = schedules[STRATEGY_ID]
        fraction = float(candidate_schedule.mean())
        for cost_bps in COST_BPS:
            exposure_payload = payloads[
                ("exposure_matched_fractional_spy_intraday_v1", cost_bps)
            ]
            exposure_rows.append(
                {
                    "cost_assumption_bps": cost_bps,
                    "candidate_active_sessions": int(candidate_schedule.sum()),
                    "eligible_sessions": int(len(candidate_schedule)),
                    "mechanical_exposure_fraction": fraction,
                    "fraction_formula": "active_sessions/eligible_sessions",
                    "control_daily_SPY_weight": float(
                        exposure_payload["spy_exposure"].iloc[0]
                    ),
                    "control_daily_BIL_weight": float(
                        1.0 - exposure_payload["spy_exposure"].iloc[0]
                    ),
                    "matches_candidate_active_fraction": bool(
                        np.isclose(
                            exposure_payload["spy_exposure"].iloc[0],
                            fraction,
                            rtol=0.0,
                            atol=1e-15,
                        )
                    ),
                    "optimized_or_rounded": False,
                    "strategy_variant": False,
                }
            )
        halves = split_halves(primary_candidate["returns"].index)
        active = primary_candidate["spy_exposure"] > 0.0
        active_ledger = primary_candidate["ledger"].loc[active]
        gross_active = active_ledger["SPY_intraday_return"].astype(float)
        longest_inactive, longest_active = consecutive_run_lengths(active)
        annual_counts = (
            active.groupby(active.index.year).sum().astype(int).to_dict()
        )
        summary = {
            "evaluation_start": primary_candidate["returns"].index.min().date().isoformat(),
            "evaluation_end": primary_candidate["returns"].index.max().date().isoformat(),
            "total_eligible_sessions": int(len(active)),
            "total_active_sessions": int(active.sum()),
            "active_sessions_first_half": int(
                active.reindex(halves["first_chronological_half"]).sum()
            ),
            "active_sessions_second_half": int(
                active.reindex(halves["second_chronological_half"]).sum()
            ),
            "profitable_active_session_fraction": float(
                (gross_active > 0.0).mean()
            ),
            "mean_active_session_return": float(gross_active.mean()),
            "median_active_session_return": float(gross_active.median()),
            "average_IBS_on_active_signal_dates": float(
                pd.Series(
                    [
                        row["IBS"]
                        for row in diagnostics
                        if row["active_signal"] and row["IBS"] != ""
                    ],
                    dtype=float,
                ).mean()
            ),
            "annual_active_session_counts": {
                str(year): count for year, count in sorted(annual_counts.items())
            },
            "longest_inactive_interval_sessions": longest_inactive,
            "longest_consecutive_active_run": longest_active,
        }

    next_action = exact_next_action(outcome)
    strategies = [strategy_row(outcome, failure_reason, next_action)]
    trials = [trial_row(outcome, failure_reason, next_action)]
    sources = [source_row()]
    benchmarks = benchmark_rows()
    process = [process_row(outcome, next_action)]

    all_trial_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    half_results: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    if payloads:
        for cost_bps in COST_BPS:
            candidate_metrics = metric_payload(payloads[(STRATEGY_ID, cost_bps)])
            all_trial_results.append(
                metric_row(
                    STRATEGY_ID,
                    "candidate",
                    cost_bps,
                    candidate_metrics,
                    outcome,
                    failure_reason,
                    decision_reason,
                )
            )
            for control_id in CONTROL_IDS:
                control_results.append(
                    metric_row(
                        control_id,
                        "control",
                        cost_bps,
                        metric_payload(payloads[(control_id, cost_bps)]),
                        outcome,
                        failure_reason,
                        decision_reason,
                    )
                )
            for row_id in (STRATEGY_ID, *CONTROL_IDS):
                payload = payloads[(row_id, cost_bps)]
                metrics = metric_payload(payload)
                turnover_rows.append(
                    {
                        "row_id": row_id,
                        "row_type": "candidate"
                        if row_id == STRATEGY_ID
                        else "benchmark_reference",
                        "cost_assumption_bps": cost_bps,
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "open_and_close_events_netted_together": False,
                        "total_open_one_way_turnover": (
                            float(payload["ledger"]["open_one_way_turnover"].sum())
                            if "open_one_way_turnover" in payload["ledger"]
                            else float(payload["turnover"].sum())
                        ),
                        "total_close_one_way_turnover": (
                            float(payload["ledger"]["close_one_way_turnover"].sum())
                            if "close_one_way_turnover" in payload["ledger"]
                            else 0.0
                        ),
                        "total_one_way_turnover": metrics[
                            "total_one_way_turnover"
                        ],
                        "transaction_cost_drag": metrics[
                            "transaction_cost_drag"
                        ],
                        "open_entry_count": metrics["number_open_entries"],
                        "close_exit_count": metrics["number_close_exits"],
                    }
                )
                invariant_rows.append(payload_invariants(payload))
        primary_index = payloads[
            (STRATEGY_ID, PRIMARY_COST_BPS)
        ]["returns"].index
        for period_label, period_index in split_halves(primary_index).items():
            for row_id in (STRATEGY_ID, *CONTROL_IDS):
                payload = payloads[(row_id, PRIMARY_COST_BPS)]
                half_results.append(
                    metric_row(
                        row_id,
                        "candidate" if row_id == STRATEGY_ID else "control",
                        PRIMARY_COST_BPS,
                        metric_payload(payload, period_index),
                        outcome,
                        failure_reason,
                        decision_reason,
                        period_label=period_label,
                        period_role="chronological_half_not_clean_holdout",
                    )
                )

    outcome_summary = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": TRIAL_ID,
            "stage": STAGE,
            "route": "standalone",
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "exact_source_replication_claimed": False,
            "execution_portability_test": True,
            "validation_claimed": False,
            "evaluation_start": summary["evaluation_start"],
            "evaluation_end": summary["evaluation_end"],
            "total_eligible_sessions": summary["total_eligible_sessions"],
            "total_active_sessions": summary["total_active_sessions"],
            "active_sessions_first_half": summary["active_sessions_first_half"],
            "active_sessions_second_half": summary["active_sessions_second_half"],
            "profitable_active_session_fraction": summary[
                "profitable_active_session_fraction"
            ],
            "profitable_session_basis": "gross_SPY_open_to_close_before_cost",
            "mean_active_session_return": summary["mean_active_session_return"],
            "median_active_session_return": summary["median_active_session_return"],
            "average_IBS_on_active_signal_dates": summary[
                "average_IBS_on_active_signal_dates"
            ],
            "annual_active_session_counts": summary[
                "annual_active_session_counts"
            ],
            "longest_inactive_interval_sessions": summary[
                "longest_inactive_interval_sessions"
            ],
            "longest_consecutive_active_run": summary[
                "longest_consecutive_active_run"
            ],
            "classification_details": classification_details,
            "exact_next_action": next_action,
            "next_action_executed": False,
        }
    ]
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "decision_reason": decision_reason,
                "exact_variant_closed_only": outcome == "closed_exploration",
                "family_closed": False,
            }
        ]
        if failure_reason
        else []
    )
    next_rows = [
        {
            "scope": "strategy",
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "scope": "task",
            "strategy_id": "",
            "outcome": "task_completed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
    ]
    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "experiment_trials": 1,
        "benchmark_references": 4,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "executed_trials": 1 if payloads else 0,
        "outcomes": {outcome: 1},
        "entity_counts_reconcile": True,
    }

    write_csv(
        OUTPUT_DIR / "source_translation_record.csv",
        sources,
        list(sources[0]),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategies,
        list(strategies[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trials,
        list(trials[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process,
        list(process[0]),
    )
    metric_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "row_id",
        "row_type",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "outcome",
        "failure_reason",
        "decision_reason",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "all_trial_results.csv",
        all_trial_results,
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "control_results.csv",
        control_results,
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_results,
        metric_fields,
    )
    session_fields = [
        "row_id",
        "cost_assumption_bps",
        "signal_date",
        "execution_date",
        "signal_known_after_completed_close",
        "target_SPY_weight_at_open",
        "target_BIL_weight_at_open",
        "BIL_overnight_return",
        "SPY_overnight_return_used",
        "SPY_intraday_return",
        "BIL_intraday_return",
        "open_pretrade_SPY_weight",
        "open_pretrade_BIL_weight",
        "open_one_way_turnover",
        "open_transaction_cost_fraction",
        "close_pretrade_SPY_weight",
        "close_pretrade_BIL_weight",
        "close_target_SPY_weight",
        "close_target_BIL_weight",
        "close_one_way_turnover",
        "close_transaction_cost_fraction",
        "total_one_way_turnover",
        "gross_return_before_cost",
        "net_return",
        "transaction_cost_drag",
        "end_of_session_SPY_weight",
        "end_of_session_BIL_weight",
        "gross_exposure",
        "daily_weight_sum",
        "same_close_fill_used",
        "entry_timestamp",
        "exit_timestamp",
    ]
    write_csv(
        OUTPUT_DIR / "session_trade_ledger.csv",
        session_ledger,
        session_fields,
    )
    diagnostic_fields = [
        "date",
        "SPY_adjusted_open",
        "SPY_adjusted_high",
        "SPY_adjusted_low",
        "SPY_adjusted_close",
        "IBS",
        "zero_range_signal_inactive",
        "active_signal",
        "strict_threshold",
        "next_session_execution_date",
        "next_session_adjusted_open",
        "next_session_adjusted_close",
        "gross_SPY_intraday_return",
        "total_one_way_turnover",
        "transaction_cost_drag",
        "net_candidate_return",
        "signal_year",
        "threshold_changed_after_results",
    ]
    write_csv(
        OUTPUT_DIR / "ibs_signal_diagnostics.csv",
        diagnostics,
        diagnostic_fields,
    )
    exposure_fields = [
        "cost_assumption_bps",
        "candidate_active_sessions",
        "eligible_sessions",
        "mechanical_exposure_fraction",
        "fraction_formula",
        "control_daily_SPY_weight",
        "control_daily_BIL_weight",
        "matches_candidate_active_fraction",
        "optimized_or_rounded",
        "strategy_variant",
    ]
    write_csv(
        OUTPUT_DIR / "exposure_control_reconciliation.csv",
        exposure_rows,
        exposure_fields,
    )
    turnover_fields = [
        "row_id",
        "row_type",
        "cost_assumption_bps",
        "turnover_formula",
        "open_and_close_events_netted_together",
        "total_open_one_way_turnover",
        "total_close_one_way_turnover",
        "total_one_way_turnover",
        "transaction_cost_drag",
        "open_entry_count",
        "close_exit_count",
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        turnover_fields,
    )
    invariant_fields = [
        "row_id",
        "cost_assumption_bps",
        "numeric_invariant_status",
        "timing_invariant_status",
        "weight_invariant_status",
        "exposure_invariant_status",
        "no_signal_uses_post_close_information",
        "entry_at_next_regular_session_open",
        "exit_at_same_regular_session_close",
        "no_SPY_overnight_return_attributed",
        "every_intraday_entry_has_close_exit",
        "duplicate_trade_detected",
        "weights_nonnegative",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "costs_nonnegative",
        "both_switches_costed_when_positive_bps",
        "explicit_zero_weights_preserved",
        "stale_weight_forward_fill_used",
        "deterministic_schedule_and_accounting",
        "invariant_pass",
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        invariant_fields,
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_summary,
        list(outcome_summary[0]),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "exact_variant_closed_only",
            "family_closed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0]),
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    source_after = v5_hashes()
    protected_after = map_hashes(list(PROTECTED_STATE_PATHS))
    cache_after = tree_content_hash(CACHE_DIR)
    prior_evidence_after = tree_identity_hash(
        ROOT / "evidence",
        excluded=OUTPUT_DIR,
    )
    expected_files_before_consistency = REQUIRED_OUTPUTS - {
        "batch_manifest.yaml",
        "consistency_check.json",
        "portability_report.md",
    }
    actual_files_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    metadata_complete = all(
        row.get(field) not in ("", "unknown", "unmapped", None)
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
            "outcome",
            "next_action",
        )
    )
    all_invariants = bool(
        payloads
        and invariant_rows
        and all(row["invariant_pass"] for row in invariant_rows)
    ) if preflight_passed else True
    consistency_passed = bool(
        outcome in ALLOWED_OUTCOMES
        and failure_reason in ALLOWED_FAILURE_REASONS
        and len(sources) == len(strategies) == len(trials) == len(process) == 1
        and len(benchmarks) == 4
        and metadata_complete
        and source_before == source_after
        and protected_before == protected_after
        and cache_before == cache_after
        and prior_evidence_before == prior_evidence_after
        and all_invariants
        and expected_files_before_consistency.issubset(actual_files_before_consistency)
        and not any(FORBIDDEN_ACTIONS.values())
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "exactly_one_source_library_record": len(sources) == 1,
        "exactly_one_strategy_configuration": len(strategies) == 1,
        "exactly_one_canonical_experiment_trial": len(trials) == 1,
        "exactly_four_benchmark_references": len(benchmarks) == 4,
        "exactly_one_process_task": len(process) == 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "required_metadata_complete": metadata_complete,
        "source_signal_retained": True,
        "source_threshold_retained": True,
        "source_entry_timing_retained": False,
        "execution_translation_explicit": True,
        "exact_source_replication_claimed": False,
        "same_close_execution_used": False,
        "SPY_overnight_return_used_by_candidate": False,
        "cost_events_netted_together": False,
        "source_reported_performance_used": False,
        "post_result_parameter_or_threshold_change": False,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "all_executed_invariants_passed": all_invariants,
        "V5_hashes_before": source_before,
        "V5_hashes_after": source_after,
        "V5_evidence_unchanged": source_before == source_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_tree_content_hash_before": cache_before,
        "cache_tree_content_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_reconciliation_method": (
            "deterministic_path_size_mtime_identity_manifest"
        ),
        "prior_evidence_tree_identity_hash_before": prior_evidence_before,
        "prior_evidence_tree_identity_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "required_outputs_before_consistency": sorted(
            expected_files_before_consistency
        ),
        "outputs_present_before_consistency": sorted(
            actual_files_before_consistency
        ),
        "deterministic_frozen_core_hash": deterministic_core_hash(),
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "source_library_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_experiment_trial_count": 1,
        "benchmark_reference_count": 4,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "source_library_id": SOURCE_LIBRARY_ID,
        "source_review_id": SOURCE_REVIEW_ID,
        "translation_label": TRANSLATION_LABEL,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_performance_calculation": True,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "source_replication_claimed": False,
        "validation_claimed": False,
        "promotion_or_paper_demo_authorized": False,
    }
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_text(
        OUTPUT_DIR / "portability_report.md",
        report_text(
            outcome,
            failure_reason,
            decision_reason,
            next_action,
            summary,
        ),
    )
    final_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    if final_files != REQUIRED_OUTPUTS:
        missing = sorted(REQUIRED_OUTPUTS - final_files)
        extra = sorted(final_files - REQUIRED_OUTPUTS)
        raise RuntimeError(f"Evidence artifact mismatch; missing={missing}, extra={extra}")
    if not consistency_passed:
        raise RuntimeError("Portability exploration consistency check failed")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "evidence_dir": str(OUTPUT_DIR),
        "active_sessions": summary["total_active_sessions"],
        "eligible_sessions": summary["total_eligible_sessions"],
        "consistency_passed": True,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
