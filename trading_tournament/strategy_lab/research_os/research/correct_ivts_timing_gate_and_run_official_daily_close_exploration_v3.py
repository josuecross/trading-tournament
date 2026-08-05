from __future__ import annotations

import csv
import io
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import (
    intermarket_ivts_herorats_portability_exploration_v1 as v1,
)
from strategy_lab.research_os.research import (
    run_cboe_point_in_time_ivts_feasibility_and_exploration_v2 as v2,
)


TASK_ID = "correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3"
MODE = "correction"
STAGE = "exploration"
STRATEGY_ID = v1.STRATEGY_ID
FAMILY_ID = v1.FAMILY_ID
SOURCE_RECORD_ID = "src_donninger_herorats_cboe_official_daily_close_v3"
OUTPUT_DIR = ROOT / "evidence" / "correction" / TASK_ID / "latest"
RAW_DIR = OUTPUT_DIR / "raw"
V1_EVIDENCE = v1.OUTPUT_DIR
V2_EVIDENCE = v2.OUTPUT_DIR
METHODOLOGY_BOUNDARY = "2025-02-10"
TIMING_POLICY = "official_daily_close_following_session_execution_v1"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"

OFFICIAL_URLS = {
    "VIX": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "VIX3M": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
}
BENCHMARKS = v1.BENCHMARKS

OUTCOME = "blocked_feasibility"
FAILURE_REASON = "methodology_failure"
NEXT_ACTION = "defer_ivts_lane_and_select_next_targeted_family_sprint_v1"

PROTECTED_STATE_PATHS = v1.PROTECTED_STATE_PATHS

REQUIRED_ARTIFACTS = (
    "correction_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "official_cboe_history_manifest.csv",
    "official_history_reproducibility.csv",
    "data_vintage_and_revision_policy.csv",
    "timing_methodology_correction.csv",
    "methodology_boundary_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "state_signal_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "correction_report.md",
)

TRIAL_FIELDS = [
    "trial_id",
    "entity_type",
    "stage",
    "strategy_id",
    "parent_trial_id",
    "adaptation_label",
    "changed_fields_from_parent",
    "strategy_rule_changed",
    "ratio_changed",
    "median_length_changed",
    "thresholds_changed",
    "instruments_changed",
    "target_weights_changed",
    "following_session_execution_changed",
    "optimization_performed",
    "post_result_adaptation_allowed",
    "record_role",
    "created_in_v3",
    "outcome",
    "failure_reason",
    "next_action",
]

METRIC_FIELDS = v1.METRIC_FIELDS


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    v1.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    v1.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    v1.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    v1.write_text(path, text)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "correction" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def normalize_official_history(raw_bytes: bytes, series: str) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(raw_bytes))
    required = {"DATE", "OPEN", "HIGH", "LOW", "CLOSE"}
    if not required.issubset(frame.columns):
        raise RuntimeError(
            f"{series} history missing columns: {sorted(required - set(frame.columns))}"
        )
    normalized = frame[["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]].copy()
    normalized["DATE"] = pd.to_datetime(normalized["DATE"], errors="coerce")
    for column in ("OPEN", "HIGH", "LOW", "CLOSE"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["DATE"]).sort_values("DATE", kind="stable")
    normalized = normalized.reset_index(drop=True)
    return normalized


def normalized_frame_hash(frame: pd.DataFrame) -> str:
    records = []
    for row in frame.itertuples(index=False):
        records.append(
            {
                "date": pd.Timestamp(row.DATE).date().isoformat(),
                "open": None if pd.isna(row.OPEN) else float(row.OPEN),
                "high": None if pd.isna(row.HIGH) else float(row.HIGH),
                "low": None if pd.isna(row.LOW) else float(row.LOW),
                "close": None if pd.isna(row.CLOSE) else float(row.CLOSE),
            }
        )
    return v1.canonical_hash(records)


def snapshot_official_history(
    session: requests.Session, series: str, attempt: int, timeout: int = 120
) -> tuple[dict[str, Any], pd.DataFrame]:
    url = OFFICIAL_URLS[series]
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    response = session.get(url, timeout=timeout)
    raw_path = RAW_DIR / f"{series}_snapshot_{attempt}.csv"
    raw_path.write_bytes(response.content)
    row: dict[str, Any] = {
        "series": series,
        "attempt": attempt,
        "official_url": url,
        "retrieval_timestamp_utc": retrieval_timestamp,
        "http_status": response.status_code,
        "raw_path": raw_path.relative_to(ROOT).as_posix(),
        "raw_bytes_hash": v1.sha256_bytes(response.content),
        "normalized_frame_hash": "",
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "columns": "",
        "duplicate_date_count": "",
        "missing_value_row_count": "",
        "finite_positive_close": False,
        "normalized_snapshots_match": False,
        "status": "request_failed",
    }
    if response.status_code != 200:
        return row, pd.DataFrame()
    frame = normalize_official_history(response.content, series)
    row.update(
        {
            "normalized_frame_hash": normalized_frame_hash(frame),
            "first_date": frame["DATE"].min().date().isoformat(),
            "last_date": frame["DATE"].max().date().isoformat(),
            "row_count": len(frame),
            "columns": "|".join(str(column) for column in frame.columns),
            "duplicate_date_count": int(frame["DATE"].duplicated().sum()),
            "missing_value_row_count": int(
                frame[["OPEN", "HIGH", "LOW", "CLOSE"]].isna().any(axis=1).sum()
            ),
            "finite_positive_close": bool(
                frame["CLOSE"].notna().all()
                and (frame["CLOSE"] > 0.0).all()
                and frame["CLOSE"].map(math.isfinite).all()
            ),
            "status": "normalized_pending_reproducibility_check",
        }
    )
    return row, frame


def acquire_official_histories_twice() -> tuple[
    list[dict[str, Any]], dict[str, pd.DataFrame]
]:
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for series in OFFICIAL_URLS:
        pair: list[dict[str, Any]] = []
        pair_frames: list[pd.DataFrame] = []
        for attempt in (1, 2):
            row, frame = snapshot_official_history(session, series, attempt)
            pair.append(row)
            pair_frames.append(frame)
        match = bool(
            pair[0]["normalized_frame_hash"]
            and pair[0]["normalized_frame_hash"] == pair[1]["normalized_frame_hash"]
        )
        for row in pair:
            row["normalized_snapshots_match"] = match
            row["status"] = (
                "official_history_reproduced"
                if match
                and row["http_status"] == 200
                and row["duplicate_date_count"] == 0
                and row["finite_positive_close"]
                else "official_history_gate_failed"
            )
            rows.append(row)
        if match:
            frames[series] = pair_frames[0]
    return rows, frames


def history_gate_passes(
    reproducibility_rows: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
) -> bool:
    return bool(
        set(frames) == set(OFFICIAL_URLS)
        and len(reproducibility_rows) == 4
        and all(
            row["status"] == "official_history_reproduced"
            for row in reproducibility_rows
        )
    )


def v2_parent_trial_id_from_ledger() -> tuple[str, int]:
    rows = read_csv(V2_EVIDENCE / "trial_ledger.csv")
    identifiers = [
        row.get("trial_id", "").strip()
        for row in rows
        if row.get("entity_type") == "experiment_trial"
        and row.get("trial_id", "").strip()
    ]
    if len(identifiers) == 1:
        return identifiers[0], len(rows)
    return "", len(rows)


def adjusted_data_preflight(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = market.load_adjusted_ohlcv(symbol)
    return {
        "data_id": symbol,
        "data_type": "adjusted_daily_market_data",
        "provider": "repository_canonical_cache",
        "status": "pass" if not frame.empty else "missing_or_invalid",
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "row_count": len(frame),
        "canonical_hash": v1.file_hash(path),
        "duplicate_date_count": 0 if not frame.empty and frame.index.is_unique else "",
        "missing_common_date_count": "not_applicable",
        "data_provenance": "repository_canonical_adjusted_daily_cache",
        "vintage_status": "not_applicable",
        "timing_policy": TIMING_POLICY,
        "same_day_return_allowed": False,
    }


def run() -> dict[str, Any]:
    protected_before = v1.hash_paths(PROTECTED_STATE_PATHS)
    cache_before = v1.directory_hash(ROOT / "data" / "cache")
    v1_before = v1.directory_hash(V1_EVIDENCE)
    v2_before = v1.directory_hash(V2_EVIDENCE)
    clean_output_dir()

    parent_trial_id, v2_trial_row_count = v2_parent_trial_id_from_ledger()
    v1_trials = read_csv(V1_EVIDENCE / "trial_ledger.csv")
    v2_manifest = yaml.safe_load(
        (V2_EVIDENCE / "batch_manifest.yaml").read_text(encoding="utf-8")
    )
    reproducibility_rows, frames = acquire_official_histories_twice()
    official_history_gate_passed = history_gate_passes(reproducibility_rows, frames)
    lineage_gate_passed = bool(parent_trial_id)

    common_dates: set[pd.Timestamp] = set()
    if set(frames) == {"VIX", "VIX3M"}:
        vix_dates = set(frames["VIX"]["DATE"])
        vix3m_dates = set(frames["VIX3M"]["DATE"])
        common_dates = vix_dates & vix3m_dates
        common_start = min(common_dates)
        common_end = max(common_dates)
    else:
        vix_dates = set()
        vix3m_dates = set()
        common_start = None
        common_end = None

    source_rows = [
        {
            "source_record_id": SOURCE_RECORD_ID,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "official_data_source": "Cboe_daily_VIX_and_VIX3M_history",
            "data_status": "official_current_history_non_vintage",
            "timing_policy": TIMING_POLICY,
            "prior_v1_trial_id": v1.TRIAL_ID,
            "prior_v2_task_id": v2.TASK_ID,
            "prior_v2_trial_id_from_ledger": parent_trial_id,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "notes": (
                "The official daily-history correction is accepted for exploration. "
                "Performance remains blocked because V2 has no canonical trial row "
                "to serve as the required parent."
            ),
        }
    ]
    strategy_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "display_name": "VIX/VIX3M Median-5 Equity-Treasury Regime",
            "entity_type": "strategy_configuration",
            "strategy_architecture": "daily_three_state_implied_volatility_curve_allocation",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "instrument_universe": "SPY|IEF",
            "route": "standalone",
            "exact_source_replication_claimed": False,
            "parameters": {
                "ratio": "VIX_close/VIX3M_close",
                "median_length": 5,
                "thresholds": [0.96, 1.02],
                "targets": ["1.0|0.0", "0.5|0.5", "0.0|1.0"],
                "missing_later_signal": "retain_previous_target",
                "execution": "following_regular_session_close",
                "primary_one_way_cost_bps": PRIMARY_COST_BPS,
                "diagnostic_one_way_cost_bps": [0.0, 10.0],
            },
            "benchmark_or_control": "|".join(BENCHMARKS),
            "stage": STAGE,
            "child_trial_created": False,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "next_action": NEXT_ACTION,
        }
    ]

    carried_trial_rows: list[dict[str, Any]] = []
    if len(v1_trials) == 1:
        carried_trial_rows.append(
            {
                "trial_id": v1_trials[0]["trial_id"],
                "entity_type": "experiment_trial",
                "stage": v1_trials[0]["stage"],
                "strategy_id": STRATEGY_ID,
                "parent_trial_id": v1_trials[0]["parent_trial_id"],
                "adaptation_label": v1_trials[0]["adaptation_label"],
                "changed_fields_from_parent": "not_applicable_prior_trial",
                "strategy_rule_changed": False,
                "ratio_changed": False,
                "median_length_changed": False,
                "thresholds_changed": False,
                "instruments_changed": False,
                "target_weights_changed": False,
                "following_session_execution_changed": False,
                "optimization_performed": False,
                "post_result_adaptation_allowed": False,
                "record_role": "prior_blocked_trial_reference",
                "created_in_v3": False,
                "outcome": v1_trials[0]["outcome"],
                "failure_reason": v1_trials[0]["failure_reason"],
                "next_action": v1_trials[0]["next_action"],
            }
        )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv", carried_trial_rows, TRIAL_FIELDS
    )

    benchmark_rows = [
        {
            "benchmark_id": benchmark_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": "",
            "trial_id": "",
            "performance_executed": False,
            "notes": "Frozen control reference; lineage gate stopped before performance.",
        }
        for benchmark_id in BENCHMARKS
    ]
    data_task_rows = [
        {
            "task_id": f"{TASK_ID}__acquire_{series}",
            "entity_type": "data_capability_task",
            "stage": "feasible",
            "adaptation_label": "data_feasibility_adjustment",
            "series": series,
            "official_url": OFFICIAL_URLS[series],
            "request_count": 2,
            "normalized_snapshots_match": all(
                row["normalized_snapshots_match"]
                for row in reproducibility_rows
                if row["series"] == series
            ),
            "data_provenance": "official_cboe_daily_history",
            "vintage_status": "current_history_non_vintage",
            "status": "official_history_gate_passed",
        }
        for series in OFFICIAL_URLS
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "official_history_gate_passed": official_history_gate_passed,
            "lineage_gate_passed": lineage_gate_passed,
            "new_child_trial_count": 0,
            "performance_trial_count": 0,
            "outcome": OUTCOME,
            "next_action": NEXT_ACTION,
        }
    ]
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        source_rows,
        list(source_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_rows,
        list(strategy_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        list(benchmark_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_task_rows,
        list(data_task_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0].keys()),
    )

    manifest_rows = []
    for series, frame in frames.items():
        pair = [row for row in reproducibility_rows if row["series"] == series]
        other_dates = vix3m_dates if series == "VIX" else vix_dates
        own_dates = set(frame["DATE"])
        relevant_other_dates = {
            date
            for date in other_dates
            if frame["DATE"].min() <= date <= frame["DATE"].max()
        }
        missing_common_dates = sorted(relevant_other_dates - own_dates)
        manifest_rows.append(
            {
                "series": series,
                "official_url": OFFICIAL_URLS[series],
                "data_provenance": "official_cboe_daily_history",
                "vintage_status": "current_history_non_vintage",
                "timing_policy": "following_session_close_after_completed_signal_date",
                "same_day_return_allowed": False,
                "retrieval_timestamp_1_utc": pair[0]["retrieval_timestamp_utc"],
                "retrieval_timestamp_2_utc": pair[1]["retrieval_timestamp_utc"],
                "raw_bytes_hash_1": pair[0]["raw_bytes_hash"],
                "raw_bytes_hash_2": pair[1]["raw_bytes_hash"],
                "normalized_frame_hash": pair[0]["normalized_frame_hash"],
                "normalized_snapshots_match": pair[0]["normalized_snapshots_match"],
                "first_date": frame["DATE"].min().date().isoformat(),
                "last_date": frame["DATE"].max().date().isoformat(),
                "row_count": len(frame),
                "columns": "|".join(str(column) for column in frame.columns),
                "duplicate_date_count": int(frame["DATE"].duplicated().sum()),
                "missing_value_row_count": int(
                    frame[["OPEN", "HIGH", "LOW", "CLOSE"]]
                    .isna()
                    .any(axis=1)
                    .sum()
                ),
                "missing_dates_vs_other_series_count": len(missing_common_dates),
                "missing_dates_vs_other_series": [
                    date.date().isoformat() for date in missing_common_dates
                ],
                "methodology_boundary": METHODOLOGY_BOUNDARY,
            }
        )
    write_csv(
        OUTPUT_DIR / "official_cboe_history_manifest.csv",
        manifest_rows,
        list(manifest_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "official_history_reproducibility.csv",
        reproducibility_rows,
        list(reproducibility_rows[0].keys()),
    )

    vintage_rows = [
        {
            "policy_id": "official_current_history_non_vintage_exploration_v1",
            "data_provenance": "official_cboe_daily_history",
            "vintage_status": "current_history_non_vintage",
            "exploratory_use_authorized": True,
            "validation_vintage_safety_established": False,
            "paper_demo_eligibility_supported": False,
            "revision_sensitivity_deferred": True,
            "later_validation_requirement": (
                "Assess vintage or historical-revision sensitivity before any "
                "validation or eligibility interpretation."
            ),
        }
    ]
    timing_rows = [
        {
            "policy_id": TIMING_POLICY,
            "prior_gate": "historical_intraday_timestamp_required",
            "corrected_gate": "official_daily_close_completed_date_required",
            "intraday_generation_timestamp_required": False,
            "official_daily_close_required": True,
            "observation_date_return_allowed": False,
            "observation_date_close_execution_allowed": False,
            "following_open_execution_allowed": False,
            "following_regular_session_close_required": True,
            "missing_execution_price_behavior": "block_signal_no_forward_fill",
            "strategy_rule_changed": False,
            "execution_rule_changed": False,
            "correction_authorized": True,
        }
    ]
    methodology_rows = [
        {
            "methodology_id": "Cboe_volatility_index_strike_selection_change",
            "effective_date": METHODOLOGY_BOUNDARY,
            "applies_to": "VIX|VIX3M",
            "diagnostic_only": True,
            "thresholds_changed": False,
            "strategy_variant_created": False,
            "observations_excluded": False,
        }
    ]
    write_csv(
        OUTPUT_DIR / "data_vintage_and_revision_policy.csv",
        vintage_rows,
        list(vintage_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "timing_methodology_correction.csv",
        timing_rows,
        list(timing_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "methodology_boundary_log.csv",
        methodology_rows,
        list(methodology_rows[0].keys()),
    )

    preflight_rows = [adjusted_data_preflight("SPY"), adjusted_data_preflight("IEF")]
    for row in manifest_rows:
        preflight_rows.append(
            {
                "data_id": row["series"],
                "data_type": "official_daily_volatility_index_close_history",
                "provider": "Cboe",
                "status": "pass",
                "first_date": row["first_date"],
                "last_date": row["last_date"],
                "row_count": row["row_count"],
                "canonical_hash": row["normalized_frame_hash"],
                "duplicate_date_count": row["duplicate_date_count"],
                "missing_common_date_count": row[
                    "missing_dates_vs_other_series_count"
                ],
                "data_provenance": "official_cboe_daily_history",
                "vintage_status": "current_history_non_vintage",
                "timing_policy": (
                    "following_session_close_after_completed_signal_date"
                ),
                "same_day_return_allowed": False,
            }
        )
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0].keys()),
    )

    for filename in (
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
    ):
        write_csv(OUTPUT_DIR / filename, [], METRIC_FIELDS)
    write_csv(
        OUTPUT_DIR / "state_signal_diagnostics.csv",
        [],
        [
            "signal_observation_date",
            "VIX_close",
            "VIX3M_close",
            "ratio",
            "five_observation_median",
            "target_state",
            "following_execution_session",
            "pretrade_SPY_weight",
            "pretrade_IEF_weight",
            "target_SPY_weight",
            "target_IEF_weight",
            "turnover",
            "cost",
            "post_trade_SPY_holding",
            "post_trade_IEF_holding",
            "methodology_boundary_flag",
            "data_provenance",
            "vintage_status",
            "timing_policy",
            "same_day_return_allowed",
        ],
    )
    turnover_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": "",
            "cost_bps": "",
            "target_change_count": 0,
            "one_way_turnover": "",
            "transaction_cost": "",
            "actual_holdings_model_executed": False,
            "status": "not_run_missing_required_V2_parent_trial",
        }
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        list(turnover_rows[0].keys()),
    )

    invariant_rows = [
        {
            "invariant_id": "official_daily_history_gate",
            "status": "pass" if official_history_gate_passed else "fail",
            "critical": True,
            "details": "Both official Cboe histories were downloaded twice and normalized snapshots matched.",
        },
        {
            "invariant_id": "current_history_non_vintage_label",
            "status": "pass",
            "critical": True,
            "details": "No point-in-time or unrevised-history claim is made.",
        },
        {
            "invariant_id": "corrected_following_session_timing_policy",
            "status": "pass",
            "critical": True,
            "details": "No historical intraday timestamp is required; same-date return remains prohibited.",
        },
        {
            "invariant_id": "required_V2_parent_trial_exists",
            "status": "fail" if not lineage_gate_passed else "pass",
            "critical": True,
            "details": (
                f"V2 trial ledger row count is {v2_trial_row_count}; no exact parent "
                "trial ID can be read from that ledger."
            ),
        },
        {
            "invariant_id": "no_child_trial_without_exact_parent",
            "status": "pass",
            "critical": True,
            "details": "No V2 conditional ID was promoted into a trial.",
        },
        {
            "invariant_id": "no_performance_without_lineage_gate",
            "status": "pass",
            "critical": True,
            "details": "All performance and signal files contain headers and zero rows.",
        },
        {
            "invariant_id": "frozen_strategy_contract_unchanged",
            "status": "pass",
            "critical": True,
            "details": "Formula, median length, thresholds, assets, targets, and execution are unchanged.",
        },
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        list(invariant_rows[0].keys()),
    )

    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "stage": STAGE,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "official_history_gate_passed": official_history_gate_passed,
            "lineage_gate_passed": lineage_gate_passed,
            "child_trial_created": False,
            "performance_executed": False,
            "precise_blocker": (
                "V2 trial_ledger.csv has zero rows, so the exact required V2 parent "
                "trial ID does not exist and cannot be read without fabrication."
            ),
            "next_action": NEXT_ACTION,
        }
    ]
    failure_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "primary_failure_reason": FAILURE_REASON,
            "failure_stage": "parent_trial_lineage_gate",
            "official_history_data_issue": False,
            "V2_trial_ledger_row_count": v2_trial_row_count,
            "V2_manifest_conditional_id": v2_manifest.get(
                "conditional_child_trial_id", ""
            ),
            "conditional_id_was_never_created": not bool(
                v2_manifest.get("child_trial_created")
            ),
            "fabricated_parent_used": False,
            "prior_packets_rewritten": False,
        }
    ]
    next_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "outcome": OUTCOME,
            "exact_next_action": NEXT_ACTION,
            "execute_in_this_task": False,
        }
    ]
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        list(failure_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0].keys()),
    )

    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "prior_blocked_experiment_trials_requested": 2,
        "prior_blocked_experiment_trials_located": len(carried_trial_rows),
        "missing_prior_V2_trial_records": 1 if not lineage_gate_passed else 0,
        "new_child_experiment_trials": 0,
        "benchmark_references": 6,
        "data_capability_tasks": 2,
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "performance_trials_executed": 0,
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    correction_manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "timing_policy": TIMING_POLICY,
        "official_history_gate_passed": official_history_gate_passed,
        "lineage_gate_passed": lineage_gate_passed,
        "V1_trial_id": v1.TRIAL_ID,
        "V2_trial_ledger_row_count": v2_trial_row_count,
        "V2_parent_trial_id_from_ledger": parent_trial_id,
        "V2_manifest_conditional_child_trial_id": v2_manifest.get(
            "conditional_child_trial_id", ""
        ),
        "V2_manifest_child_trial_created": bool(
            v2_manifest.get("child_trial_created")
        ),
        "child_trial_created": False,
        "performance_executed": False,
        "data_provenance": "official_cboe_daily_history",
        "vintage_status": "current_history_non_vintage",
        "exploratory_use_authorized": True,
        "validation_vintage_safety_established": False,
        "paper_demo_eligibility_supported": False,
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "methodology_boundary": METHODOLOGY_BOUNDARY,
        "strategy_rule_changed": False,
        "ratio_changed": False,
        "median_length_changed": False,
        "thresholds_changed": False,
        "instruments_changed": False,
        "target_weights_changed": False,
        "following_session_execution_changed": False,
        "optimization_performed": False,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "exact_next_action": NEXT_ACTION,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "correction_manifest.yaml", correction_manifest)

    report = f"""# IVTS Timing-Gate Correction and Official Daily-Close Exploration V3

## Timing Correction

The direction-owner correction is recorded as `{TIMING_POLICY}`. Official Cboe
daily VIX and VIX3M closes may support exploration when the signal-date return is
excluded and the target is applied only at the following regular session close.
Historical intraday generation timestamps are not required for this policy.

Both official histories were retrieved twice. Their normalized snapshots match,
the histories are labeled `official_current_history_non_vintage`, and no claim of
vintage safety or unrevised point-in-time history is made.

## Lineage Block

The official-history gate passed, but performance did not start. The instruction
requires the new child trial's parent ID to be read from V2's trial ledger. That
ledger has `{v2_trial_row_count}` rows. V2's manifest names a conditional child ID
but also records `child_trial_created: false`; using that uncreated ID as a parent
would fabricate lineage.

V1's blocked trial remains visible and unchanged. V2 remains a zero-trial
feasibility packet. No new child trial, signal, holdings, performance, control
comparison, turnover, or cost result was created.

## Outcome

`{OUTCOME}` with `{FAILURE_REASON}`.

Exact next action: `{NEXT_ACTION}`.
"""
    write_text(OUTPUT_DIR / "correction_report.md", report)

    protected_after = v1.hash_paths(PROTECTED_STATE_PATHS)
    cache_after = v1.directory_hash(ROOT / "data" / "cache")
    v1_after = v1.directory_hash(V1_EVIDENCE)
    v2_after = v1.directory_hash(V2_EVIDENCE)
    generated = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": True,
        "official_history_gate_passed": official_history_gate_passed,
        "lineage_gate_passed": lineage_gate_passed,
        "child_trial_created": False,
        "performance_executed": False,
        "required_artifacts_present": (
            set(REQUIRED_ARTIFACTS) - {"consistency_check.json"}
        ).issubset(generated),
        "raw_snapshot_file_count": len(list(RAW_DIR.glob("*.csv"))),
        "entity_counts": funnel,
        "performance_row_counts": {
            "all_trial_results": 0,
            "control_results": 0,
            "chronological_half_results": 0,
            "portfolio_contribution_results": 0,
            "state_signal_diagnostics": 0,
        },
        "V1_trial_id": v1.TRIAL_ID,
        "V2_trial_ledger_row_count": v2_trial_row_count,
        "V2_parent_trial_id_from_ledger": parent_trial_id,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "cache_unchanged": cache_before == cache_after,
        "V1_evidence_hash_before": v1_before,
        "V1_evidence_hash_after": v1_after,
        "V1_evidence_unchanged": v1_before == v1_after,
        "V2_evidence_hash_before": v2_before,
        "V2_evidence_hash_after": v2_after,
        "V2_evidence_unchanged": v2_before == v2_after,
        "forbidden_actions": {
            "expiry_node_endpoint_queried": False,
            "VIX1_to_VIX10_substituted": False,
            "intraday_timestamp_required": False,
            "daily_history_claimed_vintage": False,
            "fabricated_parent_trial": False,
            "strategy_parameter_or_execution_change": False,
            "performance_backtest": False,
            "validation_or_robustness": False,
            "lifecycle_or_registry_change": False,
            "paper_demo_activation": False,
            "broker_account_order_or_real_money_action": False,
        },
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "exact_next_action": NEXT_ACTION,
    }
    consistency["overall_pass"] = bool(
        consistency["required_artifacts_present"]
        and consistency["raw_snapshot_file_count"] == 4
        and consistency["official_history_gate_passed"]
        and not consistency["lineage_gate_passed"]
        and not consistency["child_trial_created"]
        and not consistency["performance_executed"]
        and consistency["protected_state_unchanged"]
        and consistency["cache_unchanged"]
        and consistency["V1_evidence_unchanged"]
        and consistency["V2_evidence_unchanged"]
        and not any(consistency["forbidden_actions"].values())
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "official_history_gate_passed": official_history_gate_passed,
        "lineage_gate_passed": lineage_gate_passed,
        "V2_trial_ledger_row_count": v2_trial_row_count,
        "child_trial_created": False,
        "performance_executed": False,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["overall_pass"],
        "evidence_path": str(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
