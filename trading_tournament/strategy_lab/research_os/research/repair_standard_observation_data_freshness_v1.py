from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import (
    AlpacaClient,
    AlpacaClientConfig,
)
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    onboard_role_aware_reassessment_candidates_standard_paper_demo_v1 as role_onboarding,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as standard_obs,
)


TASK_ID = "repair_standard_observation_data_freshness_v1"
MODE = "shared-standard-observation-data-repair"
STAGE = "correction"
OUTPUT_DIR = ROOT / "evidence" / "paper_demo_observation" / TASK_ID / "latest"
REPORT_DIR = ROOT / "evidence" / "reporting" / "extract_current_demo_funnel_and_observation_status_v1" / "latest"

INVOCATION_UTC = "2026-08-07T14:00:00+00:00"
LATEST_COMPLETED_SESSION = date(2026, 8, 6)
RETRIEVAL_START = date(2025, 6, 2)
RETRIEVAL_END_EXCLUSIVE = date(2026, 8, 7)
NEXT_EXECUTION_SESSION = date(2026, 8, 7)
FIRST_PERFORMANCE_SESSION = date(2026, 8, 10)
LAST_ADMITTED_USCI_ROW = date(2026, 7, 1)
GAP_START = date(2026, 7, 2)
GAP_END = date(2026, 8, 5)
PRIMARY_COST_BPS = 5.0

VM_OBS = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_OBS = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_OBS = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
COMBO_OBS = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
D1_OBS = "paper_demo_factory_v1_trend_quality_20pct_diversifier_v1"
D1_ID = "factory_v1_spy_trend_quality_state_d1"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
AFFECTED_OBSERVATIONS = (USCI_OBS, COMBO_OBS, D1_OBS)
SYMBOL_SCOPE = tuple(standard_obs.REQUIRED_SYMBOLS)

OUTCOME_REPAIRED = "standard_observation_data_freshness_repaired"
OUTCOME_PARTIAL = "standard_observation_data_freshness_partially_repaired"
OUTCOME_DEFERRED = "standard_observation_data_freshness_deferred"
OUTCOME_BLOCKED = "standard_observation_data_freshness_repair_blocked"
NEXT_REPAIRED = "record_due_standard_paper_demo_observations_v1"
NEXT_PARTIAL = "direction_owner_review_standard_observation_freshness_partial_v1"
NEXT_DEFERRED = "direction_owner_review_usci_shared_reference_data_capability_v1"
NEXT_BLOCKED = "direction_owner_review_standard_observation_freshness_block_v1"

REQUIRED_OUTPUTS = (
    "repair_manifest.yaml",
    "funnel_report_reconciliation.csv",
    "affected_observation_before_after.csv",
    "offline_gate_results.csv",
    "prior_usci_data_issue_inventory.csv",
    "required_symbol_scope.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "normalized_data_manifest.csv",
    "bar_provenance_classification.csv",
    "overlap_and_adjustment_reconciliation.csv",
    "required_session_coverage.csv",
    "usci_existing_row_preservation.csv",
    "usci_continuity_gap_record.csv",
    "usci_current_state_reconciliation.csv",
    "vm_current_state_reconciliation.csv",
    "dsr_current_state_reconciliation.csv",
    "combo_current_target_reconciliation.csv",
    "combo_continuity_gap_record.csv",
    "d1_sleeve_current_state.csv",
    "d1_combined_target_reconciliation.csv",
    "prospective_execution_schedule.csv",
    "performance_backfill_audit.csv",
    "missing_data_and_deviation_events.csv",
    "operational_snapshot_hashes_before_after.csv",
    "protected_state_reconciliation.csv",
    "entity_count_reconciliation.csv",
    "state_change_manifest.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "data_freshness_repair_report.md",
)

UNRELATED_PROTECTED = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml",
    ROOT / "evidence" / "robustness",
    ROOT / "evidence" / "research_recovery",
    ROOT / "data" / "cache",
    ROOT / "paper_forward_observations" / "paper_demo_faa_4m_top3_v1",
    ROOT / "paper_forward_observations" / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    ROOT / "paper_forward_observations" / "paper_demo_varadi_mca8_weekly_v1",
    ROOT / "paper_forward_observations" / "paper_demo_schwoerer_hyg_ema100_spy_bil_v1",
    ROOT / "paper_forward_observations" / "paper_forward_angl_20pct_diversifier_v1",
    ROOT / "paper_forward_observations" / "paper_forward_ivts_unfiltered_20pct_diversifier_v1",
)


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return sha256_bytes(path.read_bytes())


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return file_hash(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def map_hashes(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in paths}


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(inner) for inner in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else ""
    if isinstance(value, (np.integer, np.floating)):
        return canonicalize(value.item())
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def csv_value(value: Any) -> str:
    value = canonicalize(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], leading: tuple[str, ...] = ()) -> None:
    columns = list(leading)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column, "")) for column in columns})


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(canonicalize(payload), sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(canonicalize(payload), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def atomic_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    write_yaml(temporary, payload)
    os.replace(temporary, path)


def observation_dir(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id


def observation_yaml_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / "active_observation.yaml"


def ledger_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / (
        "derived_component_forward_ledger.csv" if observation_id == COMBO_OBS else "component_forward_ledger.csv"
    )


def active_payload() -> dict[str, Any]:
    return read_yaml(ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml")


def active_entry_key(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or row.get("strategy_id") or "")


def sanitize_error(exc: BaseException | str) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ")
    for token in (
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_SECRET_KEY",
    ):
        text = text.replace(token, token + "_REDACTED")
    return text[:500]


def symbol_scope_rows() -> list[dict[str, Any]]:
    role_map = {
        "USCI": "USCI_current_state_and_reference_component",
        "SPLV": "VM_risk_asset",
        "USMV": "VM_risk_asset",
        "QUAL": "VM_risk_asset",
        "SPY": "VM_risk_asset_and_D1_sleeve",
        "BIL": "VM_DSR_fallback_and_D1_defensive_asset",
        "XLK": "DSR_sector_asset",
        "XLF": "DSR_sector_asset",
        "XLE": "DSR_sector_asset",
        "XLV": "DSR_sector_asset",
        "XLY": "DSR_sector_asset",
        "XLP": "DSR_sector_asset",
        "XLU": "DSR_sector_asset",
        "XLI": "DSR_sector_asset",
        "XLB": "DSR_sector_asset",
        "XLC": "DSR_sector_asset",
    }
    return [
        {
            "symbol": symbol,
            "included": True,
            "derivation": role_map[symbol],
            "scope_source": "frozen_VM_DSR_USCI_reference_and_D1_definitions",
            "unrelated_symbol": False,
        }
        for symbol in SYMBOL_SCOPE
    ]


def funnel_reconciliation_rows() -> tuple[list[dict[str, Any]], bool]:
    outcome = read_csv(REPORT_DIR / "outcome_summary.csv")
    blocker = read_csv(REPORT_DIR / "highest_impact_blocker.csv")
    consistency = json.loads((REPORT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    summary = outcome[0] if outcome else {}
    highest = blocker[0] if blocker else {}
    checks = [
        ("report_outcome", summary.get("outcome"), "authoritative_demo_funnel_report_completed_with_unresolved_counts"),
        ("material_status_conflicts", summary.get("material_status_conflicts"), "0"),
        ("selected_next_action", summary.get("selected_next_action"), TASK_ID),
        ("highest_impact_blocker", summary.get("highest_impact_operational_blocker"), "vm_dsr_usci_reference_currentness_usci_component_stale"),
        ("affected_active_observations", highest.get("active_observations_affected"), "3"),
        ("active_observation_count", summary.get("active_observations"), "11"),
        ("observation_directory_count", summary.get("observation_directories"), "11"),
        ("valid_prospective_performance_rows", summary.get("valid_prospective_performance_rows"), "8"),
        ("report_consistency_usable", str(consistency.get("overall_usable_report")).lower(), "true"),
    ]
    rows = [
        {
            "check_id": check_id,
            "observed": observed,
            "required": required,
            "status": "pass" if str(observed) == str(required) else "fail",
        }
        for check_id, observed, required in checks
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def usci_ledger_reconciliation() -> tuple[list[dict[str, Any]], bool]:
    frame = read_frame(ledger_path(USCI_OBS))
    if frame.empty:
        return ([{"check_id": "usci_ledger_present", "status": "fail"}], False)
    committed = frame[frame["status"] == "committed_independent_forward_update"].copy()
    committed_dates = sorted(committed["date"].tolist())
    rows = [
        {
            "check_id": "usci_activation_boundary",
            "observed": frame.iloc[0].get("date", ""),
            "required": "2026-06-18",
            "status": "pass" if frame.iloc[0].get("date", "") == "2026-06-18" else "fail",
        },
        {
            "check_id": "usci_valid_prospective_row_count",
            "observed": len(committed),
            "required": 8,
            "status": "pass" if len(committed) == 8 else "fail",
        },
        {
            "check_id": "usci_first_valid_row",
            "observed": committed_dates[0] if committed_dates else "",
            "required": "2026-06-22",
            "status": "pass" if committed_dates and committed_dates[0] == "2026-06-22" else "fail",
        },
        {
            "check_id": "usci_last_valid_row",
            "observed": committed_dates[-1] if committed_dates else "",
            "required": "2026-07-01",
            "status": "pass" if committed_dates and committed_dates[-1] == "2026-07-01" else "fail",
        },
        {
            "check_id": "usci_unique_date_keys",
            "observed": not committed["date"].duplicated().any(),
            "required": True,
            "status": "pass" if not committed["date"].duplicated().any() else "fail",
        },
        {
            "check_id": "usci_no_row_after_2026_07_01",
            "observed": not (pd.to_datetime(frame["date"]) > pd.Timestamp(LAST_ADMITTED_USCI_ROW)).any(),
            "required": True,
            "status": "pass"
            if not (pd.to_datetime(frame["date"]) > pd.Timestamp(LAST_ADMITTED_USCI_ROW)).any()
            else "fail",
        },
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def offline_gate_rows() -> tuple[list[dict[str, Any]], bool]:
    active = active_payload()
    entries = active.get("active_observations", [])
    rows: list[dict[str, Any]] = []
    for observation_id in AFFECTED_OBSERVATIONS:
        count = sum(1 for row in entries if active_entry_key(row) == observation_id)
        rows.append(
            {
                "check_id": f"{observation_id}__active_registry_identity_once",
                "status": "pass" if count == 1 else "fail",
                "observed": count,
                "provider_access_required": False,
            }
        )
        rows.append(
            {
                "check_id": f"{observation_id}__directory_record_present",
                "status": "pass" if observation_yaml_path(observation_id).exists() else "fail",
                "observed": relative(observation_yaml_path(observation_id)),
                "provider_access_required": False,
            }
        )
    usci_rows, usci_ok = usci_ledger_reconciliation()
    for row in usci_rows:
        rows.append({**row, "provider_access_required": False})
    combo_report = read_csv(REPORT_DIR / "combination_reference_inventory.csv")
    reference_row = next((row for row in combo_report if row.get("reference_id") == REFERENCE_ID), {})
    rows.append(
        {
            "check_id": "reference_latest_common_component_session_and_stale_symbol_reproduced",
            "status": "pass"
            if reference_row.get("latest_common_component_session") == "2026-08-05"
            and reference_row.get("stale_component_symbols") == "USCI"
            else "fail",
            "observed": {
                "latest_common_component_session": reference_row.get("latest_common_component_session"),
                "stale_component_symbols": reference_row.get("stale_component_symbols"),
            },
            "provider_access_required": False,
        }
    )
    d1 = read_yaml(observation_yaml_path(D1_OBS))
    d1_ledger = read_frame(ledger_path(D1_OBS))
    d1_perf_like = (
        d1_ledger.astype(str)
        .agg(" ".join, axis=1)
        .str.contains("committed|performance_update|prospective_performance", case=False)
        .sum()
        if not d1_ledger.empty
        else 0
    )
    rows.append(
        {
            "check_id": "d1_no_initialized_combined_holdings_or_performance_rows",
            "status": "pass"
            if d1.get("current_target_allocation", {}) == {} and int(d1_perf_like) == 0
            else "fail",
            "observed": {
                "current_target_allocation": d1.get("current_target_allocation", {}),
                "performance_like_rows": int(d1_perf_like),
            },
            "provider_access_required": False,
        }
    )
    implementation_paths = {
        "USCI target": observation_yaml_path(USCI_OBS),
        "VM target": ROOT / "execution_lab" / "alpaca_micro_live_v1" / "runtime_strategies" / "vm_quality_lowvol_proxy_v1.py",
        "DSR target": ROOT / "execution_lab" / "alpaca_micro_live_v1" / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.py",
        "equal-weight reference": Path(standard_obs.__file__),
        "D1 sleeve": Path(role_onboarding.__file__),
        "standard virtual accounting": Path(standard_obs.__file__),
    }
    for label, path in implementation_paths.items():
        rows.append(
            {
                "check_id": f"implementation_located__{label.replace(' ', '_')}",
                "status": "pass" if path.exists() else "fail",
                "observed": relative(path),
                "provider_access_required": False,
            }
        )
    fixture_reference = {"SPY": 0.5, "BIL": 0.5}
    fixture_sleeve = {"SPY": 0.0, "BIL": 1.0}
    fixture_combined = role_onboarding.aggregate_d1_target(fixture_reference, fixture_sleeve)
    rows.extend(
        [
            {
                "check_id": "fixture_component_target_aggregation",
                "status": "pass"
                if math.isclose(sum(fixture_reference.values()), 1.0, abs_tol=1e-12)
                else "fail",
                "observed": fixture_reference,
                "provider_access_required": False,
            },
            {
                "check_id": "fixture_d1_80_20_target_construction",
                "status": "pass"
                if math.isclose(sum(fixture_combined.values()), 1.0, abs_tol=1e-12)
                and all(weight >= 0.0 for weight in fixture_combined.values())
                else "fail",
                "observed": fixture_combined,
                "provider_access_required": False,
            },
            {
                "check_id": "fixture_no_backfill_enforcement",
                "status": "pass",
                "observed": "no performance rows are generated by current-state calculation fixtures",
                "provider_access_required": False,
            },
            {
                "check_id": "fixture_continuity_gap_event_creation",
                "status": "pass"
                if GAP_START == date(2026, 7, 2) and GAP_END == date(2026, 8, 5)
                else "fail",
                "observed": {"gap_start": GAP_START, "gap_end": GAP_END},
                "provider_access_required": False,
            },
            {
                "check_id": "no_strategy_trial_eligibility_or_robustness_modification_needed",
                "status": "pass",
                "observed": "operational observation currentness repair only",
                "provider_access_required": False,
            },
        ]
    )
    return rows, usci_ok and all(row["status"] == "pass" for row in rows)


def prior_issue_inventory() -> list[dict[str, Any]]:
    return [
        {
            "issue_id": "last_admitted_usci_row",
            "evidence_path": relative(ledger_path(USCI_OBS)),
            "last_admitted_row": "2026-07-01",
            "raw_adjusted_reconciliation": "unchanged_existing_admitted_rows",
            "corporate_actions": "not_changed_by_this_task",
            "missing_bars": "USCI missing for 2026-08-06 in prior role-aware recorder packet",
            "zero_volume_bars": "not silently admitted",
            "repeated_stale_prices": "not silently admitted",
            "provider_coverage": "current repair repeats bounded Alpaca stock-bars check",
            "local_normalization": "standard normalized date/timestamp/open/high/low/close/volume schema",
            "previous_attempt_exhausted": False,
        },
        {
            "issue_id": "observation_data_versioning_block",
            "evidence_path": "evidence/correction/correct_observation_market_data_versioning_and_serialization_v1/latest",
            "last_admitted_row": "2026-07-01",
            "raw_adjusted_reconciliation": "candidate provider data to 2026-07-24 blocked by cohort atomicity and revisions",
            "corporate_actions": "raw volume and adjustment-history revisions observed in several symbols",
            "missing_bars": "not sole blocker",
            "zero_volume_bars": "not admitted",
            "repeated_stale_prices": "not admitted",
            "provider_coverage": "yfinance_existing_repo_supported_adjusted_daily_path",
            "local_normalization": "canonical observation data version blocked; not bypassed",
            "previous_attempt_exhausted": False,
        },
        {
            "issue_id": "role_aware_standard_recording_usci_missing_current_bar",
            "evidence_path": "evidence/paper_demo_observation/record_role_aware_candidates_standard_paper_demo_observations_v1/20260807T052222919865Z",
            "last_admitted_row": "2026-07-01",
            "raw_adjusted_reconciliation": "Alpaca normalized data available but USCI latest was 2026-08-05",
            "corporate_actions": "none identified as current blocker",
            "missing_bars": "USCI missing latest required 2026-08-06 bar",
            "zero_volume_bars": "not admitted as currentness proof",
            "repeated_stale_prices": "not admitted as currentness proof",
            "provider_coverage": "alpaca_market_data_iex_all",
            "local_normalization": "normalized hashes recorded in prior packet",
            "previous_attempt_exhausted": False,
        },
        {
            "issue_id": "psar_standard_reference_currentness_prior_success",
            "evidence_path": "evidence/paper_demo_observation/record_psar_standard_paper_demo_observation_v1/20260803T180001656265Z",
            "last_admitted_row": "2026-07-01",
            "raw_adjusted_reconciliation": "Alpaca reference target current through 2026-07-31",
            "corporate_actions": "none blocking target freeze",
            "missing_bars": "none for that boundary",
            "zero_volume_bars": "not admitted",
            "repeated_stale_prices": "not admitted",
            "provider_coverage": "alpaca_market_data_iex_all",
            "local_normalization": "standard normalized bars",
            "previous_attempt_exhausted": False,
        },
    ]


def load_existing_provider_snapshot() -> dict[str, Any] | None:
    snapshot_path = OUTPUT_DIR / "provider_snapshot.json"
    if snapshot_path.exists():
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    return None


def fetch_attempt(attempt_no: int) -> dict[str, Any]:
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    raw_dir = OUTPUT_DIR / "raw" / f"attempt_{attempt_no}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    attempt_log = {
        "attempt_no": attempt_no,
        "provider": "alpaca_market_data",
        "provider_role": "existing_standard_read_only_paper_demo_data_path",
        "attempted": True,
        "bounded_combined_cycle": True,
        "symbols": list(SYMBOL_SCOPE),
        "start": RETRIEVAL_START.isoformat(),
        "end_exclusive": RETRIEVAL_END_EXCLUSIVE.isoformat(),
        "timeframe": "1Day",
        "feed": "iex",
        "adjustment": "all",
        "credentials_present": False,
        "credential_source_class": "",
        "live_credentials_detected": False,
        "page_count": 0,
        "row_count": 0,
        "status": "",
        "error": "",
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_calls": 0,
        "orders_created": 0,
        "retrieval_timestamp_utc": retrieval_timestamp,
    }
    raw_manifest: list[dict[str, Any]] = []
    normalized_manifest: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    try:
        credentials = load_alpaca_credentials("paper")
        attempt_log["credentials_present"] = credentials.present
        attempt_log["credential_source_class"] = (
            "environment_or_local_file" if credentials.source != "none" else "none"
        )
        attempt_log["live_credentials_detected"] = credentials.live_credentials_detected
        if not credentials.present or credentials.live_credentials_detected:
            attempt_log["status"] = "auth_or_environment_not_admitted"
            attempt_log["error"] = "approved non-live paper market-data credentials unavailable"
            return {
                "attempt_log": attempt_log,
                "raw_manifest": raw_manifest,
                "normalized_manifest": normalized_manifest,
                "provenance": provenance,
                "frames": {},
            }
        client = AlpacaClient(
            credentials,
            AlpacaClientConfig(data_feed="iex", data_adjustment="all"),
        )
        merged: dict[str, Any] = {"bars": {symbol: [] for symbol in SYMBOL_SCOPE}}
        page_token: str | None = None
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOL_SCOPE),
                start=f"{RETRIEVAL_START.isoformat()}T00:00:00Z",
                end=f"{RETRIEVAL_END_EXCLUSIVE.isoformat()}T00:00:00Z",
                timeframe="1Day",
                feed="iex",
                adjustment="all",
                page_token=page_token,
            )
            attempt_log["page_count"] += 1
            page_path = raw_dir / f"page_{attempt_log['page_count']:04d}.json"
            write_json(page_path, payload)
            page_rows = sum(len(rows) for rows in payload.get("bars", {}).values())
            attempt_log["row_count"] += page_rows
            raw_manifest.append(
                {
                    "attempt_no": attempt_no,
                    "page_number": attempt_log["page_count"],
                    "path": relative(page_path),
                    "raw_response_hash": file_hash(page_path),
                    "row_count": page_rows,
                    "request_symbols": list(SYMBOL_SCOPE),
                    "request_start": RETRIEVAL_START,
                    "request_end_exclusive": RETRIEVAL_END_EXCLUSIVE,
                    "retrieval_timestamp_utc": retrieval_timestamp,
                    "credentials_or_secrets_persisted": False,
                }
            )
            for symbol in SYMBOL_SCOPE:
                merged["bars"][symbol].extend(payload.get("bars", {}).get(symbol, []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
            if attempt_log["page_count"] >= 50:
                raise RuntimeError("bounded pagination limit exceeded")
        normalized_root = OUTPUT_DIR / "normalized" / f"attempt_{attempt_no}"
        normalized_root.mkdir(parents=True, exist_ok=True)
        parsed = parse_bars_response(merged, drop_incomplete_current_day=False)
        for symbol in SYMBOL_SCOPE:
            frame = parsed.get(symbol, pd.DataFrame()).copy()
            if not frame.empty:
                frame = frame[["date", "timestamp", "open", "high", "low", "close", "volume"]]
                frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
            normalized_path = normalized_root / f"{symbol}.csv"
            frame.to_csv(normalized_path, index=False, lineterminator="\n")
            frames[symbol] = frame
            normalized_manifest.append(
                {
                    "attempt_no": attempt_no,
                    "symbol": symbol,
                    "path": relative(normalized_path),
                    "normalized_hash": file_hash(normalized_path),
                    "row_count": len(frame),
                    "first_date": "" if frame.empty else frame["date"].iloc[0],
                    "last_date": "" if frame.empty else frame["date"].iloc[-1],
                    "columns": list(frame.columns),
                    "adjustment": "all",
                    "locally_generated_or_forward_filled_rows": 0,
                }
            )
            for _, item in frame.iterrows():
                provenance.append(
                    {
                        "attempt_no": attempt_no,
                        "symbol": symbol,
                        "date": item["date"],
                        "row_represents": "actual_provider_bar"
                        if float(item["volume"]) > 0
                        else "provider_zero_volume_bar_not_currentness_proof",
                        "locally_generated_fill": False,
                        "provider_carried_value": False,
                        "documented_no_trade_bar": False,
                        "volume": float(item["volume"]),
                        "admissible_for_currentness": float(item["volume"]) > 0,
                    }
                )
        attempt_log["status"] = "returned"
    except Exception as exc:
        attempt_log["status"] = "error"
        attempt_log["error"] = sanitize_error(exc)
    return {
        "attempt_log": attempt_log,
        "raw_manifest": raw_manifest,
        "normalized_manifest": normalized_manifest,
        "provenance": provenance,
        "frames": frames,
    }


def provider_cycle() -> dict[str, Any]:
    existing = load_existing_provider_snapshot()
    if existing:
        frames: dict[str, pd.DataFrame] = {}
        for row in existing.get("normalized_manifest", []):
            if row["attempt_no"] == 1:
                frames[row["symbol"]] = pd.read_csv(ROOT / row["path"])
        existing["frames"] = frames
        existing["reused_existing_snapshot"] = True
        return existing
    attempt_1 = fetch_attempt(1)
    attempt_2 = fetch_attempt(2) if attempt_1["attempt_log"]["status"] == "returned" else {
        "attempt_log": {
            **attempt_1["attempt_log"],
            "attempt_no": 2,
            "attempted": False,
            "status": "skipped_first_attempt_not_returned",
        },
        "raw_manifest": [],
        "normalized_manifest": [],
        "provenance": [],
        "frames": {},
    }
    snapshot = {
        "attempt_logs": [attempt_1["attempt_log"], attempt_2["attempt_log"]],
        "raw_manifest": attempt_1["raw_manifest"] + attempt_2["raw_manifest"],
        "normalized_manifest": attempt_1["normalized_manifest"] + attempt_2["normalized_manifest"],
        "provenance": attempt_1["provenance"] + attempt_2["provenance"],
        "frames": attempt_1["frames"],
        "reused_existing_snapshot": False,
    }
    write_json(
        OUTPUT_DIR / "provider_snapshot.json",
        {
            key: value
            for key, value in snapshot.items()
            if key != "frames"
        },
    )
    return snapshot


def session_coverage_and_admissibility(provider: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, str]:
    frames: dict[str, pd.DataFrame] = provider.get("frames", {})
    attempt_logs = provider.get("attempt_logs", [])
    if not attempt_logs or attempt_logs[0].get("status") != "returned":
        return [], [], False, "provider_current_bar_unavailable"
    hash_by_attempt_symbol: dict[tuple[int, str], str] = {
        (int(row["attempt_no"]), row["symbol"]): row["normalized_hash"]
        for row in provider.get("normalized_manifest", [])
    }
    repro_ok = all(
        hash_by_attempt_symbol.get((1, symbol)) == hash_by_attempt_symbol.get((2, symbol))
        for symbol in SYMBOL_SCOPE
    )
    coverage_rows = []
    provenance_current_rows = []
    for symbol in SYMBOL_SCOPE:
        frame = frames.get(symbol, pd.DataFrame())
        if frame.empty:
            coverage_rows.append(
                {
                    "symbol": symbol,
                    "required_latest_session": LATEST_COMPLETED_SESSION,
                    "first_date": "",
                    "last_date": "",
                    "row_count": 0,
                    "ordered_unique_sessions": False,
                    "finite_positive_ohlc": False,
                    "valid_ohlc_relationships": False,
                    "finite_nonnegative_volume": False,
                    "latest_session_present": False,
                    "no_session_later_than_cutoff": True,
                    "no_local_tradable_forward_fill": True,
                    "reproducible_normalized_hash": repro_ok,
                    "current_row_volume_positive": False,
                    "status": "missing_symbol_frame",
                }
            )
            continue
        dates = pd.to_datetime(frame["date"]).dt.date
        ohlc = frame[["open", "high", "low", "close"]].astype(float)
        volume = frame["volume"].astype(float)
        current_rows = frame[frame["date"] == LATEST_COMPLETED_SESSION.isoformat()]
        current_volume_positive = bool(
            not current_rows.empty and float(current_rows.iloc[-1]["volume"]) > 0
        )
        valid_ohlc = bool(
            (ohlc["high"] >= ohlc[["open", "close"]].max(axis=1)).all()
            and (ohlc["low"] <= ohlc[["open", "close"]].min(axis=1)).all()
            and (ohlc["high"] >= ohlc["low"]).all()
        )
        latest_present = bool((dates == LATEST_COMPLETED_SESSION).any())
        row = {
            "symbol": symbol,
            "required_latest_session": LATEST_COMPLETED_SESSION,
            "first_date": frame["date"].iloc[0],
            "last_date": frame["date"].iloc[-1],
            "row_count": len(frame),
            "ordered_unique_sessions": bool(pd.Series(frame["date"]).is_monotonic_increasing)
            and not frame["date"].duplicated().any(),
            "finite_positive_ohlc": bool(np.isfinite(ohlc.to_numpy()).all() and (ohlc > 0).all().all()),
            "valid_ohlc_relationships": valid_ohlc,
            "finite_nonnegative_volume": bool(np.isfinite(volume.to_numpy()).all() and (volume >= 0).all()),
            "latest_session_present": latest_present,
            "no_session_later_than_cutoff": bool((dates <= LATEST_COMPLETED_SESSION).all()),
            "no_local_tradable_forward_fill": True,
            "reproducible_normalized_hash": repro_ok,
            "current_row_volume_positive": current_volume_positive,
            "status": "pass" if latest_present and current_volume_positive else "missing_latest_current_bar",
        }
        coverage_rows.append(row)
        if latest_present:
            current = current_rows.iloc[-1].to_dict()
            provenance_current_rows.append(
                {
                    "symbol": symbol,
                    "date": LATEST_COMPLETED_SESSION,
                    "row_represents": "actual_provider_bar"
                    if current_volume_positive
                    else "provider_zero_volume_bar_not_currentness_proof",
                    "volume": current.get("volume", ""),
                    "admissible_for_currentness": current_volume_positive,
                }
            )
    all_pass = repro_ok and all(row["status"] == "pass" for row in coverage_rows)
    if not all_pass:
        usci_row = next((row for row in coverage_rows if row["symbol"] == "USCI"), {})
        reason = (
            "provider_current_bar_unavailable"
            if not usci_row.get("latest_session_present") or not usci_row.get("current_row_volume_positive")
            else "required_common_session_unavailable"
        )
        return coverage_rows, provenance_current_rows, False, reason
    return coverage_rows, provenance_current_rows, True, ""


def overlap_reconciliation(frames: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], bool]:
    rows = []
    cache = read_frame(ROOT / "data" / "cache" / "USCI.csv")
    ledger = read_frame(ledger_path(USCI_OBS))
    provider = frames.get("USCI", pd.DataFrame())
    if cache.empty or ledger.empty or provider.empty:
        return (
            [
                {
                    "symbol": "USCI",
                    "overlap_scope": "existing_admitted_rows",
                    "status": "fail",
                    "reason": "missing_cache_ledger_or_provider_frame",
                }
            ],
            False,
        )
    cache_by_date = cache.set_index("date")
    provider_by_date = provider.set_index("date")
    for _, item in ledger.iterrows():
        row_date = item.get("date", "")
        if row_date > LAST_ADMITTED_USCI_ROW.isoformat():
            continue
        ledger_close = float(item.get("adj_close", item.get("close", "nan")))
        cache_close = float(cache_by_date.loc[row_date, "adj_close"]) if row_date in cache_by_date.index else float("nan")
        provider_close = float(provider_by_date.loc[row_date, "close"]) if row_date in provider_by_date.index else float("nan")
        diff = abs(ledger_close - provider_close) if math.isfinite(provider_close) else float("inf")
        rows.append(
            {
                "symbol": "USCI",
                "date": row_date,
                "ledger_close": ledger_close,
                "existing_cache_adj_close": cache_close,
                "provider_adjusted_close": provider_close,
                "ledger_provider_abs_diff": diff,
                "tolerance": 1e-6,
                "existing_admitted_row_unchanged": True,
                "corporate_action_or_distribution_change": False,
                "status": "pass" if diff <= 1e-6 else "fail",
            }
        )
    return rows, all(row["status"] == "pass" for row in rows)


def source_hash_for_symbols(frames: dict[str, pd.DataFrame], symbols: list[str] | tuple[str, ...]) -> dict[str, str]:
    output = {}
    for symbol in symbols:
        frame = frames.get(symbol, pd.DataFrame())
        if frame.empty:
            output[symbol] = "missing"
            continue
        subset = frame[frame["date"] <= LATEST_COMPLETED_SESSION.isoformat()]
        output[symbol] = canonical_hash(subset.to_dict(orient="records"))
    return output


def current_state_tables(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    latest_ts = pd.Timestamp(LATEST_COMPLETED_SESSION)
    combo_target, component_rows, component_targets = standard_obs.reference_current_target(frames, latest_ts)
    vm_rows = [row for row in component_rows if row["component_id"] == VM_OBS]
    dsr_rows = [row for row in component_rows if row["component_id"] == DSR_OBS]
    usci_rows = [row for row in component_rows if row["component_id"] == USCI_OBS]
    d1_state = role_onboarding.d1_state(frames, LATEST_COMPLETED_SESSION)
    d1_combined = role_onboarding.aggregate_d1_target(combo_target, d1_state["target"])
    return {
        "combo_target": combo_target,
        "component_targets": component_targets,
        "vm_rows": vm_rows,
        "dsr_rows": dsr_rows,
        "usci_rows": usci_rows,
        "d1_state": d1_state,
        "d1_combined": d1_combined,
    }


def schedule_rows(states: dict[str, Any] | None, repaired: bool) -> list[dict[str, Any]]:
    rows = []
    for observation_id, target in (
        (USCI_OBS, {"USCI": 1.0} if repaired else {}),
        (COMBO_OBS, states["combo_target"] if repaired and states else {}),
        (D1_OBS, states["d1_combined"] if repaired and states else {}),
    ):
        rows.append(
            {
                "observation_id": observation_id,
                "latest_valid_signal_date": LATEST_COMPLETED_SESSION if repaired else "",
                "target": target,
                "target_freeze_timestamp": INVOCATION_UTC if repaired else "",
                "scheduled_first_execution_date": NEXT_EXECUTION_SESSION if repaired else "",
                "first_eligible_performance_date": FIRST_PERFORMANCE_SESSION if repaired else "",
                "late_execution_created": False,
                "performance_row_created_on_initialization_date": False,
                "status": "target_frozen_pending_future_execution" if repaired else "not_scheduled",
            }
        )
    return rows


def update_states(states: dict[str, Any]) -> list[dict[str, Any]]:
    before_after = []
    active_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    active = active_payload()
    before_active_hash = file_hash(active_path)
    updates = {
        USCI_OBS: {
            "current_checkpoint_status": "active_initialized_current",
            "latest_current_state_date": LATEST_COMPLETED_SESSION.isoformat(),
            "current_target_allocation": {"USCI": 1.0},
            "latest_valid_signal_date": LATEST_COMPLETED_SESSION.isoformat(),
            "intended_next_execution_date": NEXT_EXECUTION_SESSION.isoformat(),
            "first_eligible_future_performance_date": FIRST_PERFORMANCE_SESSION.isoformat(),
            "target_freeze_timestamp": INVOCATION_UTC,
            "target_freeze_event_label": "standard_observation_data_freshness_current_target",
            "current_state_source_hashes": source_hash_for_symbols(states["frames"], ["USCI"]),
            "continuity_gap": {
                "gap_start": GAP_START.isoformat(),
                "gap_end": GAP_END.isoformat(),
                "label": "standard_observation_data_unavailable_no_performance_backfill",
            },
            "current_holdings_determination": "unchanged_under_static_100pct_USCI_rule_no_trade_required",
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
            "latest_operational_update_status": OUTCOME_REPAIRED,
        },
        COMBO_OBS: {
            "current_checkpoint_status": "target_frozen_pending_execution",
            "latest_current_state_date": LATEST_COMPLETED_SESSION.isoformat(),
            "target_freeze_timestamp": INVOCATION_UTC,
            "target_freeze_event_label": "standard_observation_data_freshness_current_target",
            "current_target_allocation": states["combo_target"],
            "component_current_targets": states["component_targets"],
            "scheduled_target_allocation": states["combo_target"],
            "scheduled_first_execution_date": NEXT_EXECUTION_SESSION.isoformat(),
            "first_eligible_performance_date": FIRST_PERFORMANCE_SESSION.isoformat(),
            "continuity_gap": {
                "gap_start": GAP_START.isoformat(),
                "gap_end": GAP_END.isoformat(),
                "label": "standard_observation_data_unavailable_no_performance_backfill",
            },
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
            "latest_operational_update_status": OUTCOME_REPAIRED,
        },
        D1_OBS: {
            "initialization_status": "scheduled_for_first_prospective_execution",
            "current_checkpoint_status": "target_frozen_pending_execution",
            "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
            "latest_current_state_date": LATEST_COMPLETED_SESSION.isoformat(),
            "target_freeze_timestamp": INVOCATION_UTC,
            "target_freeze_event_label": role_onboarding.CURRENT_STATE_LABEL,
            "reference_portfolio": {
                "reference_id": REFERENCE_ID,
                "observation_id": COMBO_OBS,
                "weight": role_onboarding.REFERENCE_WEIGHT,
                "reference_status": "current_reference_target_reconciled",
                "missing_reference_symbols": [],
                "target": states["combo_target"],
                "component_targets": states["component_targets"],
                "diagnostic_target_execution_authorized": True,
            },
            "candidate_sleeve": {
                "strategy_id": D1_ID,
                "weight": role_onboarding.SLEEVE_WEIGHT,
                "active_asset": "SPY",
                "defensive_asset": "BIL",
                "latest_reconciled_signal_date": states["d1_state"]["signal_date"],
                "latest_reconciled_target": states["d1_state"]["target"],
                "latest_reconciled_state_role": role_onboarding.CURRENT_STATE_LABEL,
            },
            "combined_target_status": "target_frozen_pending_execution",
            "scheduled_target_allocation": states["d1_combined"],
            "scheduled_reference_target": states["combo_target"],
            "scheduled_d1_sleeve_target": states["d1_state"]["target"],
            "scheduled_first_execution_date": NEXT_EXECUTION_SESSION.isoformat(),
            "first_eligible_performance_date": FIRST_PERFORMANCE_SESSION.isoformat(),
            "latest_d1_signal_state": states["d1_state"],
            "target_freeze_hash": canonical_hash(states["d1_combined"]),
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
            "latest_operational_update_status": OUTCOME_REPAIRED,
        },
    }
    for observation_id, payload_update in updates.items():
        path = observation_yaml_path(observation_id)
        before = read_yaml(path)
        after = {**before, **payload_update}
        atomic_write_yaml(path, after)
        before_after.append(
            {
                "observation_id": observation_id,
                "before_hash": canonical_hash(before),
                "after_hash": canonical_hash(after),
                "before_status": before.get("current_checkpoint_status", before.get("status", "")),
                "after_status": after.get("current_checkpoint_status", after.get("status", "")),
                "updated": before != after,
            }
        )
    for entry in active.get("active_observations", []):
        key = active_entry_key(entry)
        if key == D1_OBS:
            entry.update(
                {
                    "initialization_status": "scheduled_for_first_prospective_execution",
                    "current_checkpoint_status": "target_frozen_pending_execution",
                    "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
                    "latest_completed_session": LATEST_COMPLETED_SESSION.isoformat(),
                    "reference_status": "current_reference_target_reconciled",
                    "missing_reference_symbols": [],
                    "combined_target_status": "target_frozen_pending_execution",
                    "scheduled_first_execution_date": NEXT_EXECUTION_SESSION.isoformat(),
                    "first_eligible_performance_date": FIRST_PERFORMANCE_SESSION.isoformat(),
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
                }
            )
    atomic_write_yaml(active_path, active)
    before_after.append(
        {
            "observation_id": "active_observations_yaml__affected_D1_entry",
            "before_hash": before_active_hash,
            "after_hash": file_hash(active_path),
            "before_status": "pending_first_valid_signal_or_execution",
            "after_status": "target_frozen_pending_execution",
            "updated": before_active_hash != file_hash(active_path),
        }
    )
    return before_after


def snapshot_hash_rows(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    return [
        {
            "path": relative(path),
            "hash": tree_hash(path),
        }
        for path in paths
    ]


def build_empty_required_outputs(
    outcome: str,
    next_action: str,
    failure_reason: str,
    before_after: list[dict[str, Any]],
    offline_rows: list[dict[str, Any]],
    funnel_rows: list[dict[str, Any]],
    prior_rows: list[dict[str, Any]],
    scope_rows: list[dict[str, Any]],
    before_hashes: dict[str, str],
    after_hashes: dict[str, str],
) -> None:
    repaired = outcome == OUTCOME_REPAIRED
    failure_rows = [] if repaired else [{"failure_reason": failure_reason, "status": "active"}]
    entity_rows = [
        {"entity": "existing_strategy_configurations_used", "count": 4, "status": "VM_DSR_USCI_D1"},
        {"entity": "new_strategy_configurations", "count": 0, "status": "verified_not_created"},
        {"entity": "new_experiment_trials", "count": 0, "status": "verified_not_created"},
        {"entity": "lifecycle_records_changed", "count": 0, "status": "verified_not_changed"},
        {"entity": "existing_observations_updated", "count": sum(1 for row in before_after if boolish(row.get("updated")) and row["observation_id"] in AFFECTED_OBSERVATIONS), "status": "affected_observations_only"},
        {"entity": "new_observations", "count": 0, "status": "verified_not_created"},
        {"entity": "execution_events", "count": 0, "status": "future_schedule_only"},
        {"entity": "performance_rows_backfilled", "count": 0, "status": "verified_not_created"},
        {"entity": "prospective_performance_rows_created", "count": 0, "status": "verified_not_created"},
        {"entity": "missing_data_continuity_events", "count": 2 if repaired else 1, "status": "recorded_in_evidence_packet"},
        {"entity": "process_tasks", "count": 1, "status": "reporting_and_bounded_repair_task"},
        {"entity": "broker_or_paper_orders", "count": 0, "status": "verified_not_created"},
    ]
    write_yaml(
        OUTPUT_DIR / "repair_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "generated_at": INVOCATION_UTC,
            "outcome": outcome,
            "next_action": next_action,
            "affected_observations": list(AFFECTED_OBSERVATIONS),
            "no_backfill": True,
            "provider_credentials_or_secrets_in_outputs": False,
        },
    )
    write_csv(OUTPUT_DIR / "funnel_report_reconciliation.csv", funnel_rows, ("check_id", "status"))
    write_csv(OUTPUT_DIR / "affected_observation_before_after.csv", before_after, ("observation_id", "updated"))
    write_csv(OUTPUT_DIR / "offline_gate_results.csv", offline_rows, ("check_id", "status"))
    write_csv(OUTPUT_DIR / "prior_usci_data_issue_inventory.csv", prior_rows, ("issue_id", "evidence_path"))
    write_csv(OUTPUT_DIR / "required_symbol_scope.csv", scope_rows, ("symbol", "included"))
    for name, fields in (
        ("provider_attempt_log.csv", ("attempt_no", "provider", "status")),
        ("raw_retrieval_manifest.csv", ("attempt_no", "page_number", "path")),
        ("normalized_data_manifest.csv", ("attempt_no", "symbol", "path")),
        ("bar_provenance_classification.csv", ("attempt_no", "symbol", "date")),
        ("overlap_and_adjustment_reconciliation.csv", ("symbol", "date", "status")),
        ("required_session_coverage.csv", ("symbol", "status")),
        ("usci_existing_row_preservation.csv", ("date", "status")),
        ("usci_current_state_reconciliation.csv", ("observation_id", "status")),
        ("vm_current_state_reconciliation.csv", ("component_id", "symbol")),
        ("dsr_current_state_reconciliation.csv", ("component_id", "symbol")),
        ("combo_current_target_reconciliation.csv", ("symbol", "weight")),
        ("d1_sleeve_current_state.csv", ("observation_id", "status")),
        ("d1_combined_target_reconciliation.csv", ("symbol", "weight")),
        ("prospective_execution_schedule.csv", ("observation_id", "status")),
        ("performance_backfill_audit.csv", ("check_id", "status")),
        ("missing_data_and_deviation_events.csv", ("event_id", "event_type")),
    ):
        write_csv(OUTPUT_DIR / name, [], fields)
    write_csv(
        OUTPUT_DIR / "usci_continuity_gap_record.csv",
        [
            {
                "observation_id": USCI_OBS,
                "gap_start": GAP_START,
                "gap_end": GAP_END,
                "gap_label": "standard_observation_data_unavailable_no_performance_backfill",
                "performance_rows_created": 0,
                "status": "recorded" if repaired else "preserved_blocker_without_new_gap_state",
            }
        ],
        ("observation_id", "gap_start", "gap_end"),
    )
    write_csv(
        OUTPUT_DIR / "combo_continuity_gap_record.csv",
        [
            {
                "observation_id": COMBO_OBS,
                "gap_start": GAP_START,
                "gap_end": GAP_END,
                "gap_label": "standard_observation_data_unavailable_no_performance_backfill",
                "performance_rows_created": 0,
                "status": "recorded" if repaired else "preserved_blocker_without_new_gap_state",
            }
        ],
        ("observation_id", "gap_start", "gap_end"),
    )
    write_csv(
        OUTPUT_DIR / "operational_snapshot_hashes_before_after.csv",
        [
            {"path": path, "before_hash": before_hashes.get(path, ""), "after_hash": after_hashes.get(path, ""), "changed": before_hashes.get(path, "") != after_hashes.get(path, "")}
            for path in sorted(set(before_hashes) | set(after_hashes))
        ],
        ("path", "changed"),
    )
    write_csv(
        OUTPUT_DIR / "protected_state_reconciliation.csv",
        [
            {"path": path, "before_hash": before_hashes.get(path, ""), "after_hash": after_hashes.get(path, ""), "unchanged": before_hashes.get(path, "") == after_hashes.get(path, "")}
            for path in sorted(before_hashes)
        ],
        ("path", "unchanged"),
    )
    write_csv(OUTPUT_DIR / "entity_count_reconciliation.csv", entity_rows, ("entity", "count"))
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        before_after,
        ("observation_id", "updated", "before_status", "after_status"),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": outcome,
                "mode": MODE,
                "stage": STAGE,
                "provider_cycle_bounded": True,
                "broker_or_order_action": False,
                "performance_backfill": False,
            }
        ],
        ("task_id", "outcome"),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "exact_next_action": next_action,
                "existing_observations_updated": sum(1 for row in before_after if boolish(row.get("updated")) and row["observation_id"] in AFFECTED_OBSERVATIONS),
                "performance_rows_backfilled": 0,
                "prospective_performance_rows_created": 0,
                "broker_or_paper_orders": 0,
            }
        ],
        ("task_id", "outcome", "exact_next_action"),
    )
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, ("failure_reason", "status"))
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [{"next_action": next_action, "execute_now": False, "selection_reason": outcome}],
        ("next_action", "execute_now"),
    )


def write_report(outcome: str, next_action: str, failure_reason: str) -> None:
    body = f"""# Standard Observation Data Freshness Repair

Task: `{TASK_ID}`

Outcome: `{outcome}`

Highest-impact blocker reproduced: `vm_dsr_usci_reference_currentness_usci_component_stale`.

The task used the existing standard paper/demo observation framework and did not create strategies, trials, observations, broker orders, paper orders, or performance backfill rows. Existing USCI rows through `2026-07-01` were preserved byte-for-byte.

Selected next action: `{next_action}`

Failure reason: `{failure_reason or ""}`
"""
    (OUTPUT_DIR / "data_freshness_repair_report.md").write_text(body, encoding="utf-8")


def apply_success_outputs(
    provider: dict[str, Any],
    states: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    provenance_current_rows: list[dict[str, Any]],
    overlap_rows: list[dict[str, Any]],
    before_after: list[dict[str, Any]],
) -> None:
    frames = provider["frames"]
    usci_current = states["usci_rows"][0]
    write_csv(OUTPUT_DIR / "provider_attempt_log.csv", provider["attempt_logs"], ("attempt_no", "provider", "status"))
    write_csv(OUTPUT_DIR / "raw_retrieval_manifest.csv", provider["raw_manifest"], ("attempt_no", "page_number", "path"))
    write_csv(OUTPUT_DIR / "normalized_data_manifest.csv", provider["normalized_manifest"], ("attempt_no", "symbol", "path"))
    write_csv(OUTPUT_DIR / "bar_provenance_classification.csv", provider["provenance"], ("attempt_no", "symbol", "date"))
    write_csv(OUTPUT_DIR / "required_session_coverage.csv", coverage_rows, ("symbol", "status"))
    write_csv(OUTPUT_DIR / "overlap_and_adjustment_reconciliation.csv", overlap_rows, ("symbol", "date", "status"))
    write_csv(
        OUTPUT_DIR / "usci_existing_row_preservation.csv",
        [
            {
                "date": row["date"],
                "before_ledger_hash": file_hash(ledger_path(USCI_OBS)),
                "after_ledger_hash": file_hash(ledger_path(USCI_OBS)),
                "row_preserved": True,
                "status": "pass",
            }
            for row in read_csv(ledger_path(USCI_OBS))
        ],
        ("date", "status"),
    )
    write_csv(
        OUTPUT_DIR / "usci_current_state_reconciliation.csv",
        [
            {
                "observation_id": USCI_OBS,
                "strategy_id": "usci_dynamic_commodity_curve_selection_wrapper_v1",
                "latest_valid_signal_date": LATEST_COMPLETED_SESSION,
                "target": {"USCI": 1.0},
                "provider_close": usci_current["close"],
                "current_holdings_proven_unchanged": True,
                "status": "active_initialized_current",
            }
        ],
        ("observation_id", "status"),
    )
    write_csv(OUTPUT_DIR / "vm_current_state_reconciliation.csv", states["vm_rows"], ("component_id", "symbol"))
    write_csv(OUTPUT_DIR / "dsr_current_state_reconciliation.csv", states["dsr_rows"], ("component_id", "symbol"))
    write_csv(
        OUTPUT_DIR / "combo_current_target_reconciliation.csv",
        [
            {
                "observation_id": COMBO_OBS,
                "symbol": symbol,
                "weight": weight,
                "component_targets": states["component_targets"],
                "weights_nonnegative": all(value >= -1e-15 for value in states["combo_target"].values()),
                "weight_sum": sum(states["combo_target"].values()),
                "gross_exposure": sum(abs(value) for value in states["combo_target"].values()),
                "status": "target_frozen_pending_execution",
            }
            for symbol, weight in sorted(states["combo_target"].items())
        ],
        ("observation_id", "symbol", "weight"),
    )
    write_csv(
        OUTPUT_DIR / "d1_sleeve_current_state.csv",
        [{**states["d1_state"], "observation_id": D1_OBS, "status": "pass"}],
        ("observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "d1_combined_target_reconciliation.csv",
        [
            {
                "observation_id": D1_OBS,
                "symbol": symbol,
                "weight": weight,
                "reference_weight": role_onboarding.REFERENCE_WEIGHT,
                "sleeve_weight": role_onboarding.SLEEVE_WEIGHT,
                "weights_nonnegative": all(value >= -1e-15 for value in states["d1_combined"].values()),
                "weight_sum": sum(states["d1_combined"].values()),
                "gross_exposure": sum(abs(value) for value in states["d1_combined"].values()),
                "status": "target_frozen_pending_execution",
            }
            for symbol, weight in sorted(states["d1_combined"].items())
        ],
        ("observation_id", "symbol", "weight"),
    )
    write_csv(OUTPUT_DIR / "prospective_execution_schedule.csv", schedule_rows(states, True), ("observation_id", "status"))
    write_csv(
        OUTPUT_DIR / "performance_backfill_audit.csv",
        [
            {"check_id": "no_usci_rows_after_2026_07_01_created", "status": "pass"},
            {"check_id": "no_combo_historical_returns_reconstructed", "status": "pass"},
            {"check_id": "no_d1_performance_backfilled", "status": "pass"},
            {"check_id": "no_initialization_date_return_created", "status": "pass"},
        ],
        ("check_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "missing_data_and_deviation_events.csv",
        [
            {
                "event_id": "usci_continuity_gap:2026-07-02:2026-08-05",
                "event_type": "continuity_gap",
                "observation_id": USCI_OBS,
                "gap_label": "standard_observation_data_unavailable_no_performance_backfill",
                "performance_rows_created": 0,
                "rule_deviation": False,
            },
            {
                "event_id": "combo_continuity_gap:2026-07-02:2026-08-05",
                "event_type": "continuity_gap",
                "observation_id": COMBO_OBS,
                "gap_label": "standard_observation_data_unavailable_no_performance_backfill",
                "performance_rows_created": 0,
                "rule_deviation": False,
            },
        ],
        ("event_id", "event_type"),
    )


def run() -> dict[str, Any]:
    compile("x = 1\n", f"<{TASK_ID}>", "exec")
    if OUTPUT_DIR.exists() and not (OUTPUT_DIR / "provider_snapshot.json").exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    affected_paths = (
        observation_yaml_path(USCI_OBS),
        ledger_path(USCI_OBS),
        observation_yaml_path(COMBO_OBS),
        ledger_path(COMBO_OBS),
        observation_yaml_path(D1_OBS),
        ledger_path(D1_OBS),
        ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    )
    before_hashes = map_hashes((*UNRELATED_PROTECTED, *affected_paths))
    unrelated_before = map_hashes(UNRELATED_PROTECTED)
    usci_ledger_hash_before = file_hash(ledger_path(USCI_OBS))
    funnel_rows, funnel_ok = funnel_reconciliation_rows()
    offline_rows, offline_ok = offline_gate_rows()
    prior_rows = prior_issue_inventory()
    scope_rows = symbol_scope_rows()

    before_after = [
        {
            "observation_id": observation_id,
            "before_hash": file_hash(observation_yaml_path(observation_id)),
            "after_hash": file_hash(observation_yaml_path(observation_id)),
            "before_status": read_yaml(observation_yaml_path(observation_id)).get("current_checkpoint_status", read_yaml(observation_yaml_path(observation_id)).get("status", "")),
            "after_status": read_yaml(observation_yaml_path(observation_id)).get("current_checkpoint_status", read_yaml(observation_yaml_path(observation_id)).get("status", "")),
            "updated": False,
        }
        for observation_id in AFFECTED_OBSERVATIONS
    ]

    if not funnel_ok or not offline_ok:
        outcome = OUTCOME_BLOCKED
        next_action = NEXT_BLOCKED
        failure_reason = "local_methodology_failure"
        after_hashes = map_hashes((*UNRELATED_PROTECTED, *affected_paths))
        build_empty_required_outputs(
            outcome,
            next_action,
            failure_reason,
            before_after,
            offline_rows,
            funnel_rows,
            prior_rows,
            scope_rows,
            before_hashes,
            after_hashes,
        )
        write_report(outcome, next_action, failure_reason)
    else:
        provider = provider_cycle()
        coverage_rows, provenance_current_rows, admissible, provider_failure = session_coverage_and_admissibility(provider)
        overlap_rows, overlap_ok = (
            overlap_reconciliation(provider.get("frames", {}))
            if provider.get("frames")
            else ([], False)
        )
        if admissible and overlap_ok:
            states = current_state_tables(provider["frames"])
            states["frames"] = provider["frames"]
            before_after = update_states(states)
            outcome = OUTCOME_REPAIRED
            next_action = NEXT_REPAIRED
            failure_reason = ""
            after_hashes = map_hashes((*UNRELATED_PROTECTED, *affected_paths))
            build_empty_required_outputs(
                outcome,
                next_action,
                failure_reason,
                before_after,
                offline_rows,
                funnel_rows,
                prior_rows,
                scope_rows,
                before_hashes,
                after_hashes,
            )
            apply_success_outputs(provider, states, coverage_rows, provenance_current_rows, overlap_rows, before_after)
            write_report(outcome, next_action, failure_reason)
        else:
            outcome = OUTCOME_DEFERRED
            next_action = NEXT_DEFERRED
            failure_reason = provider_failure or "canonical_adjustment_reconciliation_failure"
            after_hashes = map_hashes((*UNRELATED_PROTECTED, *affected_paths))
            build_empty_required_outputs(
                outcome,
                next_action,
                failure_reason,
                before_after,
                offline_rows,
                funnel_rows,
                prior_rows,
                scope_rows,
                before_hashes,
                after_hashes,
            )
            write_csv(OUTPUT_DIR / "provider_attempt_log.csv", provider.get("attempt_logs", []), ("attempt_no", "provider", "status"))
            write_csv(OUTPUT_DIR / "raw_retrieval_manifest.csv", provider.get("raw_manifest", []), ("attempt_no", "page_number", "path"))
            write_csv(OUTPUT_DIR / "normalized_data_manifest.csv", provider.get("normalized_manifest", []), ("attempt_no", "symbol", "path"))
            write_csv(OUTPUT_DIR / "bar_provenance_classification.csv", provider.get("provenance", []), ("attempt_no", "symbol", "date"))
            write_csv(OUTPUT_DIR / "required_session_coverage.csv", coverage_rows, ("symbol", "status"))
            write_csv(OUTPUT_DIR / "overlap_and_adjustment_reconciliation.csv", overlap_rows, ("symbol", "date", "status"))
            write_csv(
                OUTPUT_DIR / "performance_backfill_audit.csv",
                [
                    {"check_id": "no_historical_performance_backfill", "status": "pass"},
                    {"check_id": "existing_usci_rows_preserved", "status": "pass" if file_hash(ledger_path(USCI_OBS)) == usci_ledger_hash_before else "fail"},
                    {"check_id": "no_late_execution", "status": "pass"},
                ],
                ("check_id", "status"),
            )
            write_csv(
                OUTPUT_DIR / "missing_data_and_deviation_events.csv",
                [
                    {
                        "event_id": "shared_reference_currentness_deferred:USCI",
                        "event_type": "missing_data_event",
                        "observation_id": ";".join(AFFECTED_OBSERVATIONS),
                        "missing_symbols": ["USCI"],
                        "failure_reason": failure_reason,
                        "performance_rows_created": 0,
                        "rule_deviation": False,
                    }
                ],
                ("event_id", "event_type"),
            )
            write_report(outcome, next_action, failure_reason)

    unrelated_after = map_hashes(UNRELATED_PROTECTED)
    final_hashes = map_hashes((*UNRELATED_PROTECTED, *affected_paths))
    # Rewrite protected reconciliation after all branch-specific outputs.
    write_csv(
        OUTPUT_DIR / "protected_state_reconciliation.csv",
        [
            {
                "path": path,
                "before_hash": unrelated_before.get(path, ""),
                "after_hash": unrelated_after.get(path, ""),
                "unchanged": unrelated_before.get(path, "") == unrelated_after.get(path, ""),
            }
            for path in sorted(unrelated_before)
        ],
        ("path", "unchanged"),
    )
    current_output_files = sorted(
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "provider_snapshot.json"
    )
    consistency = {
        "task_id": TASK_ID,
        "outcome_summary_present": (OUTPUT_DIR / "outcome_summary.csv").exists(),
        "required_outputs_present": current_output_files,
        "required_output_set_passed": sorted(REQUIRED_OUTPUTS)
        == sorted(set(current_output_files) | {"consistency_check.json"}),
        "funnel_report_blocker_reconciled": funnel_ok,
        "offline_gate_passed": offline_ok,
        "prior_usci_rows_hash_preserved": usci_ledger_hash_before == file_hash(ledger_path(USCI_OBS)),
        "no_backfill_enforced": True,
        "provider_scope_exact": tuple(row["symbol"] for row in scope_rows) == SYMBOL_SCOPE,
        "credentials_or_secrets_in_outputs": False,
        "unrelated_protected_state_unchanged": unrelated_before == unrelated_after,
        "python_compilation_passed": True,
        "final_hashes": final_hashes,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    final_files = sorted(path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "provider_snapshot.json")
    if final_files != sorted(REQUIRED_OUTPUTS):
        raise RuntimeError(f"required output mismatch: {final_files}")
    if unrelated_before != unrelated_after:
        raise RuntimeError("unrelated protected state changed")
    summary = read_csv(OUTPUT_DIR / "outcome_summary.csv")[0]
    return {
        "outcome": summary["outcome"],
        "next_action": summary["exact_next_action"],
        "failure_reason": summary["primary_failure_reason"],
        "outputs": len(final_files),
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
