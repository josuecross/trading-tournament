from __future__ import annotations

import copy
import csv
import json
import math
import os
import shutil
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yaml
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3 as v3,
)
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import (
    validate_ivts_unfiltered_diversifier_project_untouched_preperiod_v1 as validation,
)


TASK_ID = "review_and_onboard_ivts_unfiltered_paper_demo_observation_v1"
MODE = "active-direction-execution"
STAGE = "paper-demo-eligibility"
STRATEGY_ID = validation.STRATEGY_ID
FAMILY_ID = validation.FAMILY_ID
DISPLAY_NAME = validation.DISPLAY_NAME
VALIDATION_TRIAL_ID = validation.TRIAL_ID
EXPLORATION_TRIAL_ID = validation.PARENT_TRIAL_ID
OBSERVATION_ID = "paper_forward_ivts_unfiltered_20pct_diversifier_v1"
PORTFOLIO_ID = "80pct_frozen_reference_20pct_unfiltered_ivts"
REFERENCE_ID = validation.REFERENCE_ID
OUTPUT_DIR = ROOT / "evidence" / "paper_demo" / TASK_ID / "latest"

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = (
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
)
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = (
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
)
CACHE_DIR = ROOT / "data" / "cache"
STATE_PATHS = (
    REGISTRY_PATH,
    ACTIVE_OBSERVATIONS_PATH,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
)

PRIMARY_COST_BPS = 5.0
DIAGNOSTIC_COST_BPS = (0.0, 10.0)
REFERENCE_WEIGHT = 0.8
CANDIDATE_WEIGHT = 0.2
EXPOSURE_CONTROL_SPY = validation.FROZEN_EXPOSURE_SPY_WEIGHT
EXPOSURE_CONTROL_IEF = validation.FROZEN_EXPOSURE_IEF_WEIGHT
DATA_PROVENANCE = "official_cboe_daily_history"
VINTAGE_STATUS = "official_current_history_non_vintage"
TIMING_POLICY = "official_daily_close_following_session_execution_v1"
EASTERN = ZoneInfo("America/New_York")
BUSINESS_DAY = CustomBusinessDay(calendar=USFederalHolidayCalendar())

OFFICIAL_URLS = v3.OFFICIAL_URLS
COMPARATORS = (
    "100pct_frozen_reference",
    "80pct_reference_20pct_sign_only_ivts_control",
    "80pct_reference_20pct_unfiltered_exposure_matched_control",
    "80pct_reference_20pct_IEF",
)

ACTIVATED_OUTCOME = "paper_demo_eligible_observation_activated"
DEFERRED_OUTCOME = "paper_demo_eligible_observation_deferred"
INELIGIBLE_OUTCOME = "paper_demo_ineligible"
BLOCKED_OUTCOME = "eligibility_review_blocked"
ACTIVATED_NEXT_ACTION = "observe_ivts_unfiltered_20pct_diversifier_forward_v1"
DEFERRED_NEXT_ACTION = "direction_owner_review_ivts_observation_deferment_v1"
INELIGIBLE_NEXT_ACTION = "direction_owner_review_ivts_eligibility_rejection_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_ivts_eligibility_state_block_v1"

REQUIRED_ARTIFACTS = (
    "eligibility_manifest.yaml",
    "duplicate_and_alias_check.csv",
    "configuration_fingerprint.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "eligibility_evidence_reconciliation.csv",
    "forward_data_operational_probe.csv",
    "forward_snapshot_schema.csv",
    "activation_boundary.csv",
    "paper_demo_observation_record.csv",
    "registry_record_before_after.csv",
    "active_observation_before_after.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "eligibility_report.md",
)

PRIOR_EVIDENCE = (
    *validation.PRIOR_EVIDENCE,
    (validation.TASK_ID, validation.OUTPUT_DIR),
)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def file_hash(path: Path) -> str:
    return validation.exploration.v1.file_hash(path)


def hash_paths(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.exists()}


def directory_hash(path: Path) -> str:
    return validation.directory_hash(path)


def canonical_hash(payload: Any) -> str:
    return validation.exploration.v1.canonical_hash(payload)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "paper_demo" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def all_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.rglob("*") if item.is_file())


def matching_strategy_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID)
    ]


def matching_observation_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("active_observations", [])
        if isinstance(row, dict) and row.get("observation_id") == OBSERVATION_ID
    ]


def validate_active_observation_document(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    records = payload.get("active_observations", [])
    if not isinstance(records, list):
        return {"passed": False, "errors": ["active_observations must be a list"]}
    ids = [
        row.get("observation_id")
        for row in records
        if isinstance(row, dict) and row.get("observation_id")
    ]
    if len(ids) != len(set(ids)):
        errors.append("duplicate observation_id")
    matches = matching_observation_records(payload)
    if len(matches) > 1:
        errors.append(f"duplicate exact IVTS observation count {len(matches)}")
    if len(matches) == 1:
        row = matches[0]
        expected = {
            "strategy_id": STRATEGY_ID,
            "entity_type": "paper_demo_observation",
            "observation_route": "diversifier_only",
            "portfolio_id": PORTFOLIO_ID,
            "historical_backfill": "prohibited",
            "broker_submission": False,
            "real_money_authorized": False,
        }
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(
                    f"IVTS observation {field} expected {value!r}, "
                    f"found {row.get(field)!r}"
                )
    return {"passed": not errors, "errors": errors}


def configuration_payload() -> dict[str, Any]:
    return {
        "ratio": "VIX_close/VIX3M_close",
        "thresholds": [0.96, 1.02],
        "target_states": {
            "ratio_lt_0_96": {"SPY": 1.0, "IEF": 0.0},
            "ratio_0_96_to_1_02_inclusive": {"SPY": 0.5, "IEF": 0.5},
            "ratio_gt_1_02": {"SPY": 0.0, "IEF": 1.0},
        },
        "missing_signal": "retain_previous_target",
        "no_previous_target": {"SPY": 0.5, "IEF": 0.5},
        "execution": "completed_official_close_following_regular_session_close",
        "instruments": ["SPY", "IEF"],
        "outer_sleeve_weight": CANDIDATE_WEIGHT,
        "reference_weight": REFERENCE_WEIGHT,
        "frozen_reference": REFERENCE_ID,
        "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        "data_provenance": DATA_PROVENANCE,
        "vintage_status": VINTAGE_STATUS,
    }


def duplicate_rows(
    registry: dict[str, Any], active: dict[str, Any], fingerprint: str
) -> tuple[list[dict[str, Any]], bool]:
    strategy_count = len(matching_strategy_records(registry))
    observation_count = len(matching_observation_records(active))
    stored_fingerprints = [
        row.get("configuration_fingerprint")
        for row in registry.get("strategies", [])
        if isinstance(row, dict) and row.get("configuration_fingerprint")
    ]
    rows = [
        {
            "check_id": "exact_strategy_id",
            "searched_identity": STRATEGY_ID,
            "match_count": strategy_count,
            "relationship": "exact_id",
            "blocks_new_record": strategy_count > 0,
            "detail": "no authoritative registry record expected before onboarding",
        },
        {
            "check_id": "exact_observation_id",
            "searched_identity": OBSERVATION_ID,
            "match_count": observation_count,
            "relationship": "exact_id",
            "blocks_new_record": observation_count > 0,
            "detail": "no authoritative observation record expected before onboarding",
        },
        {
            "check_id": "configuration_fingerprint",
            "searched_identity": fingerprint,
            "match_count": stored_fingerprints.count(fingerprint),
            "relationship": "economic_configuration",
            "blocks_new_record": fingerprint in stored_fingerprints,
            "detail": "ratio, thresholds, targets, timing, instruments, sleeve, reference, costs, and provenance",
        },
        {
            "check_id": "V4_unfiltered_benchmark_alias",
            "searched_identity": "unfiltered_vix_vix3m_three_state_spy_ief_v1",
            "match_count": 1,
            "relationship": "read_only_benchmark_lineage",
            "blocks_new_record": False,
            "detail": "predeclared benchmark became the explicit result-driven strategy only in the carried exploration trial",
        },
        {
            "check_id": "Median5_configuration",
            "searched_identity": validation.v4.STRATEGY_ID,
            "match_count": 1,
            "relationship": "distinct_closed_configuration",
            "blocks_new_record": False,
            "detail": "Median-5 filter remains closed and is not reopened",
        },
    ]
    clean = bool(
        strategy_count == 0
        and observation_count == 0
        and fingerprint not in stored_fingerprints
    )
    return rows, clean


def eligibility_reconciliation() -> tuple[list[dict[str, Any]], bool]:
    manifest = yaml.safe_load(
        (validation.OUTPUT_DIR / "validation_manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    outcome_rows = read_csv(validation.OUTPUT_DIR / "outcome_summary.csv")
    strategy_rows = read_csv(validation.OUTPUT_DIR / "strategy_cards.csv")
    trial_rows = read_csv(validation.OUTPUT_DIR / "trial_ledger.csv")
    consistency = json.loads(
        (validation.OUTPUT_DIR / "consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    outcome = outcome_rows[0] if len(outcome_rows) == 1 else {}
    strategy = strategy_rows[0] if len(strategy_rows) == 1 else {}
    child = [
        row for row in trial_rows if row.get("trial_id") == VALIDATION_TRIAL_ID
    ]
    checks = [
        (
            "validation_consistency",
            consistency.get("overall_pass") is True,
            "validation consistency_check overall_pass",
        ),
        (
            "validation_outcome",
            outcome.get("outcome") == "validation_positive",
            outcome.get("outcome", ""),
        ),
        (
            "validated_claim",
            outcome.get("validated_claim")
            == "20pct_diversifier_route_under_current_history_non_vintage_data",
            outcome.get("validated_claim", ""),
        ),
        (
            "route",
            manifest.get("route") == "diversifier_only"
            and strategy.get("route") == "diversifier_only",
            "diversifier_only",
        ),
        (
            "sleeve_weight",
            float(manifest.get("outer_sleeve_weight", -1.0)) == CANDIDATE_WEIGHT,
            manifest.get("outer_sleeve_weight", ""),
        ),
        (
            "validation_trial",
            len(child) == 1
            and child[0].get("parent_trial_id") == EXPLORATION_TRIAL_ID,
            VALIDATION_TRIAL_ID,
        ),
        (
            "historical_vintage_caveat",
            manifest.get("current_history_non_vintage_validation_caveat") is True
            and outcome.get("point_in_time_historical_data_safety_established")
            == "false",
            VINTAGE_STATUS,
        ),
        (
            "standalone_not_validated",
            outcome.get("standalone_validation_claimed") == "false",
            "standalone eligibility remains false",
        ),
        (
            "accounting_invariants",
            consistency.get("row_counts", {}).get("invariant_results") == 36,
            "36 validation invariant rows",
        ),
        (
            "development_and_validation_periods",
            manifest.get("development_period", {}).get("use")
            == "reproduction_and_context_only"
            and manifest.get("validation_period", {}).get("classification")
            == "project_untouched_not_source_untouched",
            "development context separate from fixed validation period",
        ),
    ]
    rows = [
        {
            "check_id": check_id,
            "status": "pass" if passed else "fail",
            "detail": detail,
            "validation_rerun_performed": False,
        }
        for check_id, passed, detail in checks
    ]
    return rows, all(passed for _, passed, _ in checks)


def retrieve_official_data_once() -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "trading-tournament-research-paper-demo-onboarding/1.0"}
    )
    captures: dict[str, list[dict[str, Any]]] = {"VIX": [], "VIX3M": []}
    for series in ("VIX", "VIX3M"):
        for attempt in (1, 2):
            retrieved_utc = datetime.now(timezone.utc)
            try:
                response = session.get(OFFICIAL_URLS[series], timeout=120)
                raw = response.content
                frame = (
                    v3.normalize_official_history(raw, series)
                    if response.status_code == 200
                    else pd.DataFrame()
                )
                normalized_hash = (
                    v3.normalized_frame_hash(frame) if not frame.empty else ""
                )
                latest = (
                    frame.dropna(subset=["CLOSE"]).iloc[-1].to_dict()
                    if not frame.empty
                    else {}
                )
                captures[series].append(
                    {
                        "series": series,
                        "attempt": attempt,
                        "retrieval_timestamp_utc": retrieved_utc.isoformat(),
                        "retrieval_timestamp_et": retrieved_utc.astimezone(
                            EASTERN
                        ).isoformat(),
                        "official_source": OFFICIAL_URLS[series],
                        "http_status": response.status_code,
                        "raw_bytes": raw,
                        "raw_hash": validation.exploration.v1.sha256_bytes(raw),
                        "normalized_hash": normalized_hash,
                        "frame": frame,
                        "latest_date": (
                            pd.Timestamp(latest["DATE"]) if latest else pd.NaT
                        ),
                        "latest_close": (
                            float(latest["CLOSE"]) if latest else float("nan")
                        ),
                    }
                )
            except requests.RequestException as exc:
                captures[series].append(
                    {
                        "series": series,
                        "attempt": attempt,
                        "retrieval_timestamp_utc": retrieved_utc.isoformat(),
                        "retrieval_timestamp_et": retrieved_utc.astimezone(
                            EASTERN
                        ).isoformat(),
                        "official_source": OFFICIAL_URLS[series],
                        "http_status": 0,
                        "raw_bytes": b"",
                        "raw_hash": "",
                        "normalized_hash": "",
                        "frame": pd.DataFrame(),
                        "latest_date": pd.NaT,
                        "latest_close": float("nan"),
                        "error": type(exc).__name__,
                    }
                )
    series_pass = {}
    for series, pair in captures.items():
        series_pass[series] = bool(
            len(pair) == 2
            and all(item["http_status"] == 200 for item in pair)
            and all(not item["frame"].empty for item in pair)
            and pair[0]["normalized_hash"] == pair[1]["normalized_hash"]
            and pair[0]["latest_date"] == pair[1]["latest_date"]
            and pair[0]["latest_close"] == pair[1]["latest_close"]
        )
    common_date = (
        min(captures["VIX"][0]["latest_date"], captures["VIX3M"][0]["latest_date"])
        if all(series_pass.values())
        else pd.NaT
    )
    records: dict[str, dict[str, Any]] = {}
    if not pd.isna(common_date):
        for series in ("VIX", "VIX3M"):
            frame = captures[series][0]["frame"]
            matching = frame.loc[frame["DATE"] == common_date, "CLOSE"]
            if matching.empty or not np.isfinite(float(matching.iloc[-1])):
                common_date = pd.NaT
                break
            records[series] = {
                "date": pd.Timestamp(common_date),
                "close": float(matching.iloc[-1]),
            }
    gate_passed = bool(all(series_pass.values()) and not pd.isna(common_date))
    return {
        "captures": captures,
        "series_pass": series_pass,
        "common_date": common_date,
        "records": records,
        "gate_passed": gate_passed,
        "bounded_official_retrieval_attempts": 1,
        "http_request_count": 4,
    }


def expected_latest_completed_session(now_et: datetime) -> pd.Timestamp:
    date = pd.Timestamp(now_et.date())
    is_business = bool(len(pd.date_range(date, date, freq=BUSINESS_DAY)))
    if is_business and now_et.time() >= time(16, 15):
        return date
    return pd.Timestamp(date - BUSINESS_DAY)


def proposed_execution_session(now_et: datetime, signal_date: pd.Timestamp) -> pd.Timestamp:
    today = pd.Timestamp(now_et.date())
    today_is_business = bool(len(pd.date_range(today, today, freq=BUSINESS_DAY)))
    session_close_still_future = today_is_business and now_et.time() < time(15, 45)
    candidate = today if session_close_still_future else pd.Timestamp(today + BUSINESS_DAY)
    if candidate <= signal_date:
        candidate = pd.Timestamp(signal_date + BUSINESS_DAY)
    return candidate.normalize()


def target_for_ratio(ratio: float) -> tuple[float, float, str]:
    if ratio < 0.96:
        return 1.0, 0.0, "risk_on"
    if ratio <= 1.02:
        return 0.5, 0.5, "middle"
    return 0.0, 1.0, "defensive"


def persist_immutable_snapshot(
    retrieval: dict[str, Any],
    now_et: datetime,
    execution_session: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    common_date = pd.Timestamp(retrieval["common_date"])
    snapshot_dir = (
        OUTPUT_DIR
        / "forward_snapshots"
        / common_date.date().isoformat()
        / "onboarding_capture"
    )
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    capture_rows: list[dict[str, Any]] = []
    raw_paths: dict[str, list[str]] = {}
    for series in ("VIX", "VIX3M"):
        raw_paths[series] = []
        for item in retrieval["captures"][series]:
            raw_path = snapshot_dir / f"{series}_official_history_attempt_{item['attempt']}.csv"
            with raw_path.open("xb") as handle:
                handle.write(item["raw_bytes"])
            raw_paths[series].append(rel(raw_path))
            capture_rows.append(
                {
                    "series": series,
                    "attempt": item["attempt"],
                    "retrieval_timestamp_utc": item["retrieval_timestamp_utc"],
                    "retrieval_timestamp_et": item["retrieval_timestamp_et"],
                    "official_source": item["official_source"],
                    "http_status": item["http_status"],
                    "raw_path": rel(raw_path),
                    "raw_hash": item["raw_hash"],
                    "normalized_hash": item["normalized_hash"],
                    "latest_date": pd.Timestamp(item["latest_date"]).date().isoformat(),
                    "latest_close": item["latest_close"],
                    "duplicate_retrieval_matches": retrieval["series_pass"][series],
                }
            )
    vix = retrieval["records"]["VIX"]["close"]
    vix3m = retrieval["records"]["VIX3M"]["close"]
    ratio = float(vix / vix3m)
    target_spy, target_ief, state = target_for_ratio(ratio)
    record = {
        "observation_id": OBSERVATION_ID,
        "snapshot_role": "onboarding_operational_probe_not_forward_observation",
        "observation_date": common_date.date().isoformat(),
        "retrieval_timestamp_utc": retrieval["captures"]["VIX"][0][
            "retrieval_timestamp_utc"
        ],
        "retrieval_timestamp_et": retrieval["captures"]["VIX"][0][
            "retrieval_timestamp_et"
        ],
        "official_cboe_source_identifiers": OFFICIAL_URLS,
        "raw_history_paths": raw_paths,
        "raw_hashes": {
            series: [item["raw_hash"] for item in retrieval["captures"][series]]
            for series in ("VIX", "VIX3M")
        },
        "normalized_hashes": {
            series: [
                item["normalized_hash"] for item in retrieval["captures"][series]
            ]
            for series in ("VIX", "VIX3M")
        },
        "VIX": vix,
        "VIX3M": vix3m,
        "ratio": ratio,
        "target_state": state,
        "target_SPY": target_spy,
        "target_IEF": target_ief,
        "intended_execution_session": execution_session.date().isoformat(),
        "data_freshness_status": (
            "latest_completed_session"
            if common_date == expected_latest_completed_session(now_et)
            else "stale_or_unexpected_latest_session"
        ),
        "signal_date_strictly_before_execution": bool(
            common_date < execution_session
        ),
        "immutable_original_snapshot": True,
        "later_revision_may_replace_original": False,
        "historical_backfill": False,
        "broker_submission": False,
    }
    record["snapshot_normalized_hash"] = canonical_hash(record)
    snapshot_path = snapshot_dir / "snapshot_record.json"
    write_json(snapshot_path, record)
    record["snapshot_path"] = rel(snapshot_path)
    record["snapshot_file_hash"] = file_hash(snapshot_path)
    return record, capture_rows


def adapter_probe(snapshot: dict[str, Any]) -> dict[str, Any]:
    prior_inner = np.array([0.5, 0.5], dtype=float)
    target_inner = np.array(
        [float(snapshot["target_SPY"]), float(snapshot["target_IEF"])], dtype=float
    )
    inner_turnover = 0.5 * float(np.abs(target_inner - prior_inner).sum())
    outer_target = np.array([REFERENCE_WEIGHT, CANDIDATE_WEIGHT], dtype=float)
    outer_initial_turnover = 0.5 * float(np.abs(outer_target).sum())
    inner_cost = CANDIDATE_WEIGHT * inner_turnover * (PRIMARY_COST_BPS / 10000.0)
    outer_cost = outer_initial_turnover * (PRIMARY_COST_BPS / 10000.0)
    validation_turnover = read_csv(
        validation.OUTPUT_DIR / "turnover_cost_reconciliation.csv"
    )
    validation_invariants = read_csv(validation.OUTPUT_DIR / "invariant_results.csv")
    prior_accounting_pass = bool(
        validation_turnover
        and all(row["inner_and_outer_costs_charged_once"] == "true" for row in validation_turnover)
        and all(row["invariant_pass"] == "true" for row in validation_invariants)
    )
    return {
        "adapter_check_count": 1,
        "outer_reference_weight": REFERENCE_WEIGHT,
        "outer_candidate_weight": CANDIDATE_WEIGHT,
        "outer_weight_sum": float(outer_target.sum()),
        "previous_inner_SPY": prior_inner[0],
        "previous_inner_IEF": prior_inner[1],
        "target_inner_SPY": target_inner[0],
        "target_inner_IEF": target_inner[1],
        "inner_weight_sum": float(target_inner.sum()),
        "inner_turnover": inner_turnover,
        "outer_initialization_turnover": outer_initial_turnover,
        "inner_cost_at_5bps": inner_cost,
        "outer_cost_at_5bps": outer_cost,
        "total_cost_at_5bps": inner_cost + outer_cost,
        "gross_exposure": float(outer_target.sum()),
        "daily_weight_sum": float(outer_target.sum()),
        "natural_drift_supported_by_validated_accounting": prior_accounting_pass,
        "separate_inner_outer_turnover_supported": True,
        "transaction_costs_charged_once": prior_accounting_pass,
        "broker_path_required": False,
        "status": "pass" if prior_accounting_pass else "fail",
    }


def current_market_readiness(signal_date: pd.Timestamp) -> dict[str, Any]:
    prices = market.load_price_frame(("SPY", "IEF", "BIL")).sort_index()
    reference = market.active_vm_dsr_usci_reference_returns().sort_index()
    spy_latest = pd.Timestamp(prices["SPY"].dropna().index.max())
    ief_latest = pd.Timestamp(prices["IEF"].dropna().index.max())
    reference_latest = pd.Timestamp(reference.dropna().index.max())
    same_latest = min(spy_latest, ief_latest, reference_latest)
    return {
        "SPY_latest": spy_latest,
        "IEF_latest": ief_latest,
        "reference_latest": reference_latest,
        "latest_common": same_latest,
        "tradables_current_for_signal": bool(
            spy_latest >= signal_date and ief_latest >= signal_date
        ),
        "reference_current_for_signal": bool(reference_latest >= signal_date),
    }


def operational_probe_rows(
    retrieval: dict[str, Any],
    snapshot: dict[str, Any],
    adapter: dict[str, Any],
    market_readiness: dict[str, Any],
    execution_session: pd.Timestamp,
) -> tuple[list[dict[str, Any]], bool]:
    signal_date = pd.Timestamp(snapshot["observation_date"])
    checks = [
        (
            "official_Cboe_sources_accessible",
            retrieval["gate_passed"],
            "one bounded official-data attempt; two retrievals per required series",
        ),
        (
            "two_consecutive_retrievals_match",
            all(retrieval["series_pass"].values()),
            "normalized histories and latest completed-session values match",
        ),
        (
            "immutable_raw_and_normalized_hash_storage",
            bool(
                snapshot.get("snapshot_file_hash")
                and all(
                    item["raw_hash"] and item["normalized_hash"]
                    for values in retrieval["captures"].values()
                    for item in values
                )
            ),
            snapshot.get("snapshot_path", ""),
        ),
        (
            "signal_date_before_proposed_execution",
            signal_date < execution_session,
            f"{signal_date.date()} < {execution_session.date()}",
        ),
        (
            "current_SPY_IEF_canonical_data",
            market_readiness["tradables_current_for_signal"],
            (
                f"SPY {market_readiness['SPY_latest'].date()} | "
                f"IEF {market_readiness['IEF_latest'].date()} | "
                f"signal {signal_date.date()}"
            ),
        ),
        (
            "frozen_reference_same_execution_session_ready",
            market_readiness["reference_current_for_signal"],
            (
                f"reference {market_readiness['reference_latest'].date()} | "
                f"signal {signal_date.date()}"
            ),
        ),
        (
            "observation_accounting_adapter",
            adapter["status"] == "pass",
            "80/20 outer, inner states, drift, separate turnover, and costs-once",
        ),
        (
            "no_historical_forward_backfill",
            True,
            "snapshot is an onboarding probe; forward observation row count remains zero before activation",
        ),
        (
            "broker_order_path_not_required",
            adapter["broker_path_required"] is False,
            "brokerless forward shadow simulation",
        ),
        (
            "deterministic_reconciliation_report",
            retrieval["gate_passed"] and adapter["status"] == "pass",
            "source hashes, normalized hashes, and accounting probe recorded",
        ),
    ]
    rows = [
        {
            "gate_number": index,
            "check_id": check_id,
            "status": "pass" if passed else "fail",
            "detail": detail,
            "required_for_activation": True,
        }
        for index, (check_id, passed, detail) in enumerate(checks, start=1)
    ]
    return rows, all(passed for _, passed, _ in checks)


def strategy_record(outcome: str, next_action: str, fingerprint: str) -> dict[str, Any]:
    active = outcome == ACTIVATED_OUTCOME
    return {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "family": FAMILY_ID,
        "strategy_family": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": "raw_implied_volatility_curve_three_state_allocation",
        "source_or_research_lineage": validation.SOURCE_LINEAGE,
        "instrument_universe": "SPY|IEF",
        "parameters": configuration_payload(),
        "benchmark_or_control": list(COMPARATORS),
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "lane": "paper_forward",
        "instrument_family": "ETF",
        "version": "v1",
        "parent_id": VALIDATION_TRIAL_ID,
        "credibility_tier": "tier4_paper_forward",
        "status": "active_paper_demo_observation" if active else "gated",
        "role": "20pct_diversifier_only",
        "route": "diversifier_only",
        "rules_frozen": True,
        "paper_forward_active": active,
        "paper_demo_eligible": True,
        "implementation_status": "implemented",
        "data_source": (
            "official_Cboe_daily_VIX_VIX3M_forward_snapshots_and_"
            "canonical_adjusted_SPY_IEF_plus_frozen_reference"
        ),
        "evidence_source": TASK_ID,
        "latest_evidence_path": rel(OUTPUT_DIR),
        "latest_known_result_summary": (
            "Positive project-untouched pre-period validation supports only the "
            "20% diversifier route; historical signal data remain current-history "
            "and non-vintage."
        ),
        "allowed_next_action": "observe_only" if active else "no_action",
        "forbidden_next_actions": [
            "standalone_observation",
            "historical_forward_backfill",
            "claim_point_in_time_historical_safety",
            "change_thresholds_targets_instruments_or_timing",
            "change_sleeve_weight",
            "add_broker_integration",
            "place_orders",
            "promote_to_real_money",
        ],
        "promotion_requirements": (
            "Prospective immutable-snapshot shadow observation and later "
            "direction-owner review; no automatic promotion."
        ),
        "demotion_or_kill_criteria": (
            "Stale or mismatched Cboe signal data, missing tradable or reference "
            "valuation, accounting defect, exposure breach, or direction-owner decision."
        ),
        "notes": (
            "Eligible only as 20% of the frozen 80/20 diversifier portfolio. "
            "Standalone, broker, real-money, exact-source, and historical "
            "point-in-time claims are prohibited."
        ),
        "instrument_lane": "ETF",
        "evidence_tier": "tier4_paper_forward",
        "current_status": "paper_demo_eligible",
        "allowed_next_actions": ["observe_only"] if active else ["no_action"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": (
            "paper_demo_eligible_validated_20pct_diversifier_only"
        ),
        "promotion_reason": "validation_positive_project_untouched_preperiod",
        "primary_failure_mode": (
            "" if active else "activation_boundary_not_ready"
        ),
        "duplication_risk": "V4_unfiltered_control_lineage_preserved_no_duplicate_trial",
        "risk_budget_status": (
            "active_forward_shadow_20pct_diversifier"
            if active
            else "20pct_diversifier_observation_deferred"
        ),
        "evidence_needed": (
            "prospective immutable forward observations"
            if active
            else "current canonical SPY_IEF_and_frozen_reference_session_alignment"
        ),
        "duplicate_of": "",
        "blocked_reason": "" if active else "activation_boundary_not_ready",
        "risk_framework_status": (
            "paper_demo_eligible_20pct_diversifier_only"
        ),
        "paper_forward_allowed_by_risk_framework": True,
        "promotion_blockers": (
            "diversifier_only;historical_signal_data_current_history_non_vintage;"
            "no_real_money_authorization"
        ),
        "standalone_eligible": False,
        "broker_eligible": False,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "historical_vintage_safety_established": False,
        "forward_immutable_snapshot_requirement": True,
        "principal_caveat": "historical_signal_data_current_history_non_vintage",
        "approved_sleeve_weight": CANDIDATE_WEIGHT,
        "approved_reference_weight": REFERENCE_WEIGHT,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "observation_id": OBSERVATION_ID,
        "configuration_fingerprint_schema": (
            "ivts_unfiltered_20pct_diversifier_observation_fingerprint_v1"
        ),
        "configuration_fingerprint": fingerprint,
        "frozen": True,
        "no_real_money_recommendation": True,
        "next_action": next_action,
    }


def observation_record(
    outcome: str,
    failure_reason: str,
    next_action: str,
    snapshot: dict[str, Any],
    execution_session: pd.Timestamp,
) -> dict[str, Any]:
    active = outcome == ACTIVATED_OUTCOME
    return {
        "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID,
        "entity_type": "paper_demo_observation",
        "stage": "paper_demo_observation" if active else "deferred",
        "outcome": outcome,
        "state": (
            "active_accepted_frozen_observation"
            if active
            else "deferred_activation_boundary_not_ready"
        ),
        "paper_forward_active": active,
        "protected": True,
        "parent_strategy_id": STRATEGY_ID,
        "parent_trial_id": VALIDATION_TRIAL_ID,
        "exploration_parent_trial_id": EXPLORATION_TRIAL_ID,
        "observation_route": "diversifier_only",
        "portfolio_id": PORTFOLIO_ID,
        "reference_portfolio_id": REFERENCE_ID,
        "candidate_sleeve_id": STRATEGY_ID,
        "target_weights": {
            "frozen_reference": REFERENCE_WEIGHT,
            "unfiltered_ivts_candidate": CANDIDATE_WEIGHT,
        },
        "inner_instruments": ["SPY", "IEF"],
        "inner_rule": configuration_payload(),
        "outer_rebalance_frequency": "monthly",
        "observation_mode": "forward_shadow_simulation",
        "broker_submission": False,
        "paper_orders": False,
        "live_orders": False,
        "real_money_authorized": False,
        "historical_backfill": "prohibited",
        "historical_forward_records_created": 0,
        "forward_records_created": 0,
        "activation_timestamp": "" if not active else datetime.now(timezone.utc).isoformat(),
        "first_forward_observation_date": "",
        "proposed_first_execution_session": execution_session.date().isoformat(),
        "initialization_status": (
            "pending_activation_boundary" if active else "not_initialized_deferred"
        ),
        "initialization_labeled_separately": True,
        "latest_captured_signal_date": snapshot["observation_date"],
        "latest_snapshot_path": snapshot["snapshot_path"],
        "latest_snapshot_hash": snapshot["snapshot_file_hash"],
        "snapshot_role": snapshot["snapshot_role"],
        "current_status": "active" if active else "deferred",
        "failure_reason": failure_reason,
        "next_action": next_action,
        "cost_assumption": "5_bps_per_one_way_turnover",
        "diagnostic_cost_ledgers_bps": list(DIAGNOSTIC_COST_BPS),
        "standalone_eligible": False,
        "broker_eligible": False,
        "historical_vintage_safety_established": False,
        "forward_immutable_snapshot_requirement": True,
        "principal_caveat": "historical_signal_data_current_history_non_vintage",
        "comparators": list(COMPARATORS),
    }


def append_yaml_list_record(text: str, record: dict[str, Any]) -> str:
    block = yaml.safe_dump(
        [record], sort_keys=False, width=120, allow_unicode=False
    ).rstrip()
    return text.rstrip() + "\n" + block + "\n"


def insert_observation_record(text: str, record: dict[str, Any]) -> str:
    marker = "\nbenchmark_controls:"
    if marker not in text:
        raise ValueError("active_observations.yaml lacks benchmark_controls marker")
    block = yaml.safe_dump(
        [record], sort_keys=False, width=120, allow_unicode=False
    ).rstrip()
    return text.replace(marker, "\n" + block + marker, 1)


def atomic_write_pair(registry_text: str, active_text: str) -> None:
    registry_before = REGISTRY_PATH.read_bytes()
    active_before = ACTIVE_OBSERVATIONS_PATH.read_bytes()
    registry_temp = REGISTRY_PATH.with_name(f".{REGISTRY_PATH.name}.{TASK_ID}.tmp")
    active_temp = ACTIVE_OBSERVATIONS_PATH.with_name(
        f".{ACTIVE_OBSERVATIONS_PATH.name}.{TASK_ID}.tmp"
    )
    try:
        for path, text in (
            (registry_temp, registry_text),
            (active_temp, active_text),
        ):
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(registry_temp, REGISTRY_PATH)
        os.replace(active_temp, ACTIVE_OBSERVATIONS_PATH)
    except BaseException:
        REGISTRY_PATH.write_bytes(registry_before)
        ACTIVE_OBSERVATIONS_PATH.write_bytes(active_before)
        registry_temp.unlink(missing_ok=True)
        active_temp.unlink(missing_ok=True)
        raise


def before_after_rows(
    entity_id: str, before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": entity_id,
            "field": field,
            "before_value": before.get(field, ""),
            "after_value": after.get(field, ""),
            "changed": before.get(field) != after.get(field),
        }
        for field in sorted(set(before) | set(after))
    ]


def snapshot_schema_rows() -> list[dict[str, Any]]:
    definitions = {
        "observation_date": "completed common Cboe signal date",
        "retrieval_timestamp_utc": "immutable initial retrieval time in UTC",
        "retrieval_timestamp_et": "same retrieval time in U.S. Eastern",
        "official_cboe_source_identifiers": "official VIX and VIX3M history URLs",
        "raw_history_paths": "immutable raw bytes for both bounded retrievals",
        "raw_hashes": "SHA-256 hashes of raw histories",
        "normalized_hashes": "SHA-256 hashes of normalized histories",
        "VIX": "official VIX close",
        "VIX3M": "official VIX3M close",
        "ratio": "VIX divided by VIX3M",
        "target_state": "risk_on, middle, or defensive",
        "target_SPY": "candidate sleeve SPY target",
        "target_IEF": "candidate sleeve IEF target",
        "intended_execution_session": "strictly later regular-session close",
        "data_freshness_status": "latest completed-session reconciliation",
        "signal_date_strictly_before_execution": "look-ahead guard",
        "snapshot_normalized_hash": "canonical normalized snapshot hash",
        "snapshot_file_hash": "serialized immutable snapshot hash",
        "previous_target": "carried prior candidate target",
        "candidate_sleeve_holdings": "explicit candidate sleeve holdings",
        "frozen_reference_holdings": "explicit reference holdings",
        "total_portfolio_holdings": "combined 80/20 holdings",
        "inner_turnover": "candidate state-change turnover",
        "outer_turnover": "monthly outer rebalance turnover",
        "costs": "inner and outer costs charged once",
        "gross_exposure": "sum of absolute portfolio weights",
        "daily_weight_sum": "sum of total portfolio weights",
        "comparator_values": "four frozen comparator values",
        "reconciliation_flags": "missing, stale, mismatch, and hash flags",
    }
    return [
        {
            "field": field,
            "required": True,
            "definition": definition,
            "immutable_original": True,
            "later_revision_may_overwrite": False,
        }
        for field, definition in definitions.items()
    ]


def state_change_rows(
    before: dict[str, str], after: dict[str, str], state_written: bool
) -> list[dict[str, Any]]:
    permitted = {rel(REGISTRY_PATH), rel(ACTIVE_OBSERVATIONS_PATH)}
    return [
        {
            "path": rel(path),
            "before_hash": before.get(rel(path), "missing"),
            "after_hash": after.get(rel(path), "missing"),
            "changed": before.get(rel(path), "missing")
            != after.get(rel(path), "missing"),
            "permitted_change": rel(path) in permitted,
            "action": (
                "created_exact_IVTS_record"
                if state_written and path == REGISTRY_PATH
                else "created_exact_IVTS_observation"
                if state_written and path == ACTIVE_OBSERVATIONS_PATH
                else "unchanged_required"
            ),
        }
        for path in STATE_PATHS
    ]


def run() -> dict[str, Any]:
    clean_output_dir()
    state_before = hash_paths(STATE_PATHS)
    prior_before = {task_id: directory_hash(path) for task_id, path in PRIOR_EVIDENCE}
    cache_before = directory_hash(CACHE_DIR)
    registry_text_before = REGISTRY_PATH.read_text(encoding="utf-8")
    active_text_before = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry_before = yaml.safe_load(registry_text_before) or {}
    active_before = yaml.safe_load(active_text_before) or {}
    registry_validation_before = validate_registry_data(registry_before)

    fingerprint_payload = configuration_payload()
    fingerprint = canonical_hash(fingerprint_payload)
    duplicates, duplicate_clean = duplicate_rows(
        registry_before, active_before, fingerprint
    )
    reconciliation_rows, evidence_valid = eligibility_reconciliation()

    retrieval = retrieve_official_data_once() if evidence_valid and duplicate_clean else {
        "captures": {"VIX": [], "VIX3M": []},
        "series_pass": {"VIX": False, "VIX3M": False},
        "common_date": pd.NaT,
        "records": {},
        "gate_passed": False,
        "bounded_official_retrieval_attempts": 0,
        "http_request_count": 0,
    }
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(EASTERN)
    snapshot: dict[str, Any] = {}
    capture_rows: list[dict[str, Any]] = []
    execution_session = pd.Timestamp(now_et.date()) + BUSINESS_DAY
    adapter: dict[str, Any] = {"status": "not_run", "adapter_check_count": 0}
    market_readiness: dict[str, Any] = {}
    probe_rows: list[dict[str, Any]] = []
    operational_pass = False

    if retrieval["gate_passed"]:
        execution_session = proposed_execution_session(
            now_et, pd.Timestamp(retrieval["common_date"])
        )
        snapshot, capture_rows = persist_immutable_snapshot(
            retrieval, now_et, execution_session
        )
        adapter = adapter_probe(snapshot)
        market_readiness = current_market_readiness(
            pd.Timestamp(snapshot["observation_date"])
        )
        probe_rows, operational_pass = operational_probe_rows(
            retrieval, snapshot, adapter, market_readiness, execution_session
        )
    else:
        probe_rows = [
            {
                "gate_number": index,
                "check_id": check_id,
                "status": "fail" if index <= 4 else "not_run",
                "detail": "official Cboe bounded retrieval did not pass",
                "required_for_activation": True,
            }
            for index, check_id in enumerate(
                (
                    "official_Cboe_sources_accessible",
                    "two_consecutive_retrievals_match",
                    "immutable_raw_and_normalized_hash_storage",
                    "signal_date_before_proposed_execution",
                    "current_SPY_IEF_canonical_data",
                    "frozen_reference_same_execution_session_ready",
                    "observation_accounting_adapter",
                    "no_historical_forward_backfill",
                    "broker_order_path_not_required",
                    "deterministic_reconciliation_report",
                ),
                start=1,
            )
        ]

    if not evidence_valid:
        outcome = INELIGIBLE_OUTCOME
        failure_reason = "validation_evidence_invalid"
        next_action = INELIGIBLE_NEXT_ACTION
    elif not duplicate_clean:
        outcome = BLOCKED_OUTCOME
        failure_reason = "status_reconciliation_required"
        next_action = BLOCKED_NEXT_ACTION
    elif operational_pass:
        outcome = ACTIVATED_OUTCOME
        failure_reason = ""
        next_action = ACTIVATED_NEXT_ACTION
    else:
        outcome = DEFERRED_OUTCOME
        if not retrieval["gate_passed"]:
            failure_reason = "forward_data_capture_unavailable"
        elif adapter.get("status") != "pass":
            failure_reason = "observation_accounting_capability_missing"
        else:
            failure_reason = "activation_boundary_not_ready"
        next_action = DEFERRED_NEXT_ACTION

    strategy_before_record = (
        matching_strategy_records(registry_before)[0]
        if len(matching_strategy_records(registry_before)) == 1
        else {}
    )
    observation_before_record = (
        matching_observation_records(active_before)[0]
        if len(matching_observation_records(active_before)) == 1
        else {}
    )
    strategy_after_record: dict[str, Any] = {}
    observation_after_record: dict[str, Any] = {}
    state_written = False
    proposal_registry_validation: dict[str, Any] = {
        "passed": False,
        "errors": ["not proposed"],
    }
    proposal_active_validation: dict[str, Any] = {
        "passed": False,
        "errors": ["not proposed"],
    }

    if outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}:
        strategy_after_record = strategy_record(outcome, next_action, fingerprint)
        observation_after_record = observation_record(
            outcome,
            failure_reason,
            next_action,
            snapshot,
            execution_session,
        )
        proposed_registry = copy.deepcopy(registry_before)
        proposed_registry.setdefault("strategies", []).append(strategy_after_record)
        proposed_active = copy.deepcopy(active_before)
        proposed_active.setdefault("active_observations", []).append(
            observation_after_record
        )
        proposal_registry_validation = validate_registry_data(proposed_registry)
        proposal_active_validation = validate_active_observation_document(
            proposed_active
        )
        if (
            proposal_registry_validation.get("passed") is not True
            or proposal_active_validation.get("passed") is not True
        ):
            outcome = BLOCKED_OUTCOME
            failure_reason = "status_reconciliation_required"
            next_action = BLOCKED_NEXT_ACTION
            strategy_after_record = {}
            observation_after_record = {}
        else:
            registry_text_after = append_yaml_list_record(
                registry_text_before, strategy_after_record
            )
            active_text_after = insert_observation_record(
                active_text_before, observation_after_record
            )
            parsed_registry = yaml.safe_load(registry_text_after)
            parsed_active = yaml.safe_load(active_text_after)
            if validate_registry_data(parsed_registry) != proposal_registry_validation:
                raise RuntimeError("serialized registry differs from validated proposal")
            if (
                validate_active_observation_document(parsed_active)
                != proposal_active_validation
            ):
                raise RuntimeError(
                    "serialized active observation differs from validated proposal"
                )
            atomic_write_pair(registry_text_after, active_text_after)
            state_written = True

    registry_after = yaml.safe_load(
        REGISTRY_PATH.read_text(encoding="utf-8")
    ) or {}
    active_after = yaml.safe_load(
        ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    ) or {}
    registry_validation_after = validate_registry_data(registry_after)
    active_validation_after = validate_active_observation_document(active_after)
    state_after = hash_paths(STATE_PATHS)
    prior_after = {task_id: directory_hash(path) for task_id, path in PRIOR_EVIDENCE}
    cache_after = directory_hash(CACHE_DIR)
    state_rows = state_change_rows(state_before, state_after, state_written)

    strategy_rows = (
        [strategy_after_record]
        if strategy_after_record
        else [
            {
                "strategy_id": STRATEGY_ID,
                "entity_type": "strategy_configuration",
                "stage": "not_updated",
                "outcome": outcome,
                "failure_reason": failure_reason,
            }
        ]
    )
    trial_rows = [
        {
            "trial_id": VALIDATION_TRIAL_ID,
            "entity_type": "experiment_trial",
            "stage": "validation",
            "strategy_id": STRATEGY_ID,
            "parent_trial_id": EXPLORATION_TRIAL_ID,
            "adaptation_label": "validation_variant",
            "lineage_role": "carried_forward_read_only",
            "read_only": True,
            "new_experiment_trial_created": False,
        }
    ]
    benchmark_rows = [
        {
            "benchmark_reference_id": comparator,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "active_strategy_or_observation": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for comparator in COMPARATORS
    ]
    data_task_rows = [
        {
            "data_capability_task_id": f"{TASK_ID}__official_cboe_forward_capture",
            "entity_type": "data_capability_task",
            "stage": "feasible" if retrieval["gate_passed"] else "blocked",
            "adaptation_label": "forward_data_capture",
            "bounded_attempt_count": retrieval[
                "bounded_official_retrieval_attempts"
            ],
            "http_request_count": retrieval["http_request_count"],
            "series": "VIX|VIX3M",
            "network_source_scope": "official_Cboe_only",
            "status": "pass" if retrieval["gate_passed"] else "fail",
            "counted_as_strategy_or_trial": False,
        }
    ]
    process_rows = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "counted_as_strategy_or_trial": False,
        }
    ]

    fingerprint_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "fingerprint_schema": (
                "ivts_unfiltered_20pct_diversifier_observation_fingerprint_v1"
            ),
            "ratio": fingerprint_payload["ratio"],
            "thresholds": fingerprint_payload["thresholds"],
            "target_states": fingerprint_payload["target_states"],
            "execution_timing": fingerprint_payload["execution"],
            "instruments": fingerprint_payload["instruments"],
            "outer_sleeve_weight": CANDIDATE_WEIGHT,
            "frozen_reference": REFERENCE_ID,
            "cost_model_bps": PRIMARY_COST_BPS,
            "data_provenance": DATA_PROVENANCE,
            "configuration_fingerprint": fingerprint,
        }
    ]
    activation_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "onboarding_completed_utc": now_utc.isoformat(),
            "onboarding_completed_et": now_et.isoformat(),
            "captured_signal_date": snapshot.get("observation_date", ""),
            "proposed_first_execution_session": (
                execution_session.date().isoformat() if snapshot else ""
            ),
            "signal_date_strictly_before_execution": snapshot.get(
                "signal_date_strictly_before_execution", False
            ),
            "activation_status": (
                "activated_prospectively"
                if outcome == ACTIVATED_OUTCOME
                else "deferred_no_initialization"
            ),
            "actual_activation_timestamp": (
                observation_after_record.get("activation_timestamp", "")
                if observation_after_record
                else ""
            ),
            "first_forward_observation_date": "",
            "historical_forward_rows_created": 0,
            "portfolio_initialization_created": False,
            "initialization_rule": (
                "initialize_frozen_80_20_at_activation_boundary"
            ),
            "initialization_labeled_separately": True,
            "historical_backfill": False,
        }
    ]
    observation_evidence_rows = [
        observation_after_record
        if observation_after_record
        else {
            "observation_id": OBSERVATION_ID,
            "strategy_id": STRATEGY_ID,
            "entity_type": "paper_demo_observation",
            "stage": "not_created",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]

    write_yaml(
        OUTPUT_DIR / "eligibility_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "validation_trial_id": VALIDATION_TRIAL_ID,
            "exploration_parent_trial_id": EXPLORATION_TRIAL_ID,
            "route": "20pct_diversifier_only",
            "strategy_stage": (
                "paper_demo_eligible"
                if outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
                else "unchanged"
            ),
            "strategy_outcome": (
                "paper_demo_eligible"
                if outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
                else outcome
            ),
            "observation_outcome": outcome,
            "failure_reason": failure_reason,
            "approved_sleeve_weight": CANDIDATE_WEIGHT,
            "approved_reference_weight": REFERENCE_WEIGHT,
            "standalone_eligible": False,
            "broker_eligible": False,
            "real_money_authorized": False,
            "historical_vintage_safety_established": False,
            "forward_immutable_snapshot_requirement": True,
            "promotion_basis": "validation_positive_project_untouched_preperiod",
            "principal_caveat": (
                "historical_signal_data_current_history_non_vintage"
            ),
            "official_data_attempt_count": retrieval[
                "bounded_official_retrieval_attempts"
            ],
            "observation_adapter_check_count": adapter.get(
                "adapter_check_count", 0
            ),
            "historical_backfill": False,
            "new_experiment_trials": 0,
            "broker_orders": 0,
            "exact_next_action": next_action,
            "required_artifacts": list(REQUIRED_ARTIFACTS),
        },
    )
    write_csv(
        OUTPUT_DIR / "duplicate_and_alias_check.csv",
        duplicates,
        list(duplicates[0]),
    )
    write_csv(
        OUTPUT_DIR / "configuration_fingerprint.csv",
        fingerprint_rows,
        list(fingerprint_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_rows,
        list(strategy_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial_rows,
        list(trial_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        list(benchmark_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_task_rows,
        list(data_task_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "eligibility_evidence_reconciliation.csv",
        reconciliation_rows,
        list(reconciliation_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "forward_data_operational_probe.csv",
        probe_rows,
        list(probe_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "forward_snapshot_schema.csv",
        snapshot_schema_rows(),
        list(snapshot_schema_rows()[0]),
    )
    if capture_rows:
        write_csv(
            OUTPUT_DIR / "official_forward_capture_reproducibility.csv",
            capture_rows,
            list(capture_rows[0]),
        )
    write_csv(
        OUTPUT_DIR / "activation_boundary.csv",
        activation_rows,
        list(activation_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observation_record.csv",
        observation_evidence_rows,
        list(observation_evidence_rows[0]),
    )
    registry_before_after = before_after_rows(
        STRATEGY_ID, strategy_before_record, strategy_after_record
    )
    active_before_after = before_after_rows(
        OBSERVATION_ID, observation_before_record, observation_after_record
    )
    write_csv(
        OUTPUT_DIR / "registry_record_before_after.csv",
        registry_before_after,
        list(registry_before_after[0]),
    )
    write_csv(
        OUTPUT_DIR / "active_observation_before_after.csv",
        active_before_after,
        list(active_before_after[0]),
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        list(state_rows[0]),
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "strategy_stage": (
            "paper_demo_eligible"
            if outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
            else "unchanged"
        ),
        "strategy_outcome": (
            "paper_demo_eligible"
            if outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
            else outcome
        ),
        "observation_stage": (
            observation_after_record.get("stage", "not_created")
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": (
            "validation supports eligibility; operational activation awaits "
            "current canonical SPY/IEF and frozen-reference session alignment"
            if outcome == DEFERRED_OUTCOME
            else "all eligibility and operational gates passed"
            if outcome == ACTIVATED_OUTCOME
            else "eligibility or authoritative-state reconciliation failed"
        ),
        "exact_next_action": next_action,
        "validated_route": "20pct_diversifier_only",
        "standalone_eligible": False,
        "historical_vintage_safety_established": False,
        "forward_records_created": 0,
        "broker_orders_created": 0,
    }
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "observation_id": OBSERVATION_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "exact_next_action": next_action,
            }
        ]
        if failure_reason
        else []
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "strategy_id",
            "observation_id",
            "outcome",
            "primary_failure_reason",
            "exact_next_action",
        ],
    )
    next_rows = [
        {
            "scope": "paper_demo_observation",
            "entity_id": OBSERVATION_ID,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }
    ]
    write_csv(
        OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0])
    )

    report = f"""# IVTS Unfiltered Paper/Demo Eligibility And Onboarding V1

## Eligibility

The validation packet reconciled without rerunning validation. Eligibility is
granted only to `{STRATEGY_ID}` as a 20% sleeve combined with 80%
`{REFERENCE_ID}` and monthly outer rebalancing. Standalone eligibility, exact
source replication, historical point-in-time safety, broker eligibility, and
real-money authorization remain false.

## Forward Safety

One bounded official Cboe data attempt retrieved VIX and VIX3M twice. The
original raw histories, hashes, normalized hashes, common close values, ratio,
target, and intended execution session are stored in an immutable onboarding
snapshot. It is an operational probe, not a backfilled forward observation.

The official signal capture status was
`{'pass' if retrieval['gate_passed'] else 'fail'}`. The local observation
adapter status was `{adapter.get('status', 'not_run')}`. Canonical SPY/IEF and
frozen-reference data currently share latest date
`{market_readiness.get('latest_common', '')}`.

## Decision

Outcome: `{outcome}`.

Failure reason: `{failure_reason or 'not_applicable'}`.

Exact next action: `{next_action}`.

No historical forward row, portfolio initialization, broker order, paper order,
live order, account action, or real-money action was created.
"""
    write_text(OUTPUT_DIR / "eligibility_report.md", report)

    required_present = all(
        (OUTPUT_DIR / name).exists()
        for name in REQUIRED_ARTIFACTS
        if name != "consistency_check.json"
    )
    changed_state_paths = [
        row["path"] for row in state_rows if row["changed"]
    ]
    only_permitted_state_changes = all(
        not row["changed"] or row["permitted_change"] for row in state_rows
    )
    exact_strategy_after = matching_strategy_records(registry_after)
    exact_observation_after = matching_observation_records(active_after)
    deterministic_names = [
        name for name in REQUIRED_ARTIFACTS if name != "consistency_check.json"
    ]
    core_hash = canonical_hash(
        [
            {"path": name, "hash": file_hash(OUTPUT_DIR / name)}
            for name in deterministic_names
        ]
    )
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": bool(
            required_present
            and evidence_valid
            and duplicate_clean
            and state_written
            and registry_validation_before.get("passed") is True
            and registry_validation_after.get("passed") is True
            and active_validation_after.get("passed") is True
            and len(exact_strategy_after) == 1
            and len(exact_observation_after) == 1
            and only_permitted_state_changes
            and prior_before == prior_after
            and cache_before == cache_after
            and len(trial_rows) == 1
            and len(benchmark_rows) == 4
            and outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "eligibility_evidence_reconciled": evidence_valid,
        "validation_rerun_performed": False,
        "duplicate_screen_clean": duplicate_clean,
        "configuration_fingerprint": fingerprint,
        "official_data_gate_passed": retrieval["gate_passed"],
        "operational_activation_gate_passed": operational_pass,
        "bounded_official_data_attempts": retrieval[
            "bounded_official_retrieval_attempts"
        ],
        "local_observation_adapter_checks": adapter.get(
            "adapter_check_count", 0
        ),
        "strategy_configurations_created_or_updated": int(state_written),
        "validation_trials_carried_forward": 1,
        "new_experiment_trials": 0,
        "benchmark_references": 4,
        "paper_demo_observations_created": int(state_written),
        "data_capability_tasks": len(data_task_rows),
        "process_tasks": 1,
        "broker_orders": 0,
        "forward_records_created": 0,
        "historical_backfill_performed": False,
        "standalone_eligibility_granted": False,
        "historical_vintage_safety_established": False,
        "registry_validation_before": registry_validation_before,
        "registry_validation_after": registry_validation_after,
        "active_observation_validation_after": active_validation_after,
        "proposal_registry_validation": proposal_registry_validation,
        "proposal_active_validation": proposal_active_validation,
        "state_hashes_before": state_before,
        "state_hashes_after": state_after,
        "changed_state_paths": changed_state_paths,
        "only_permitted_state_changes": only_permitted_state_changes,
        "roadmap_unchanged": state_before.get(rel(ROADMAP_PATH))
        == state_after.get(rel(ROADMAP_PATH)),
        "research_queue_unchanged": state_before.get(rel(QUEUE_PATH))
        == state_after.get(rel(QUEUE_PATH)),
        "family_ledger_unchanged": state_before.get(rel(FAMILY_LEDGER_PATH))
        == state_after.get(rel(FAMILY_LEDGER_PATH)),
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "cache_unchanged": cache_before == cache_after,
        "required_artifacts_present": required_present,
        "deterministic_reconciliation_hash": core_hash,
        "forbidden_actions": {
            "validation_rerun": False,
            "standalone_eligibility": False,
            "historical_forward_backfill": False,
            "historical_vintage_safety_claim": False,
            "threshold_target_instrument_timing_or_sleeve_change": False,
            "exposure_control_recalculated": False,
            "Median5_reopened": False,
            "broker_account_order_or_real_money_action": False,
            "unrelated_state_change": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "evidence_path": str(OUTPUT_DIR),
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "strategy_stage": (
            exact_strategy_after[0].get("stage") if exact_strategy_after else ""
        ),
        "observation_stage": (
            exact_observation_after[0].get("stage")
            if exact_observation_after
            else ""
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "official_data_gate_passed": retrieval["gate_passed"],
        "operational_activation_gate_passed": operational_pass,
        "captured_signal_date": snapshot.get("observation_date", ""),
        "proposed_execution_session": (
            execution_session.date().isoformat() if snapshot else ""
        ),
        "canonical_market_latest_common": (
            market_readiness.get("latest_common").date().isoformat()
            if market_readiness
            else ""
        ),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
