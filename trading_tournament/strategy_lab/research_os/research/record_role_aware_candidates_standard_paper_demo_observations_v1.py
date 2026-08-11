from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    onboard_role_aware_reassessment_candidates_standard_paper_demo_v1 as onboarding,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as standard_obs,
)


TASK_ID = "record_role_aware_candidates_standard_paper_demo_observations_v1"
MODE = "standard-paper-demo-recording"
STAGE = "paper-demo-onboarding"

OUTCOME_UPDATED = "role_aware_standard_observations_recording_updated"
OUTCOME_PARTIAL = "role_aware_standard_observations_recording_partial"
OUTCOME_PENDING = "role_aware_standard_observations_recording_pending"
OUTCOME_BLOCKED = "role_aware_standard_observations_recording_blocked"

NEXT_RECORD = TASK_ID
NEXT_BLOCKED = "direction_owner_review_role_aware_observation_recording_block_v1"

MCA_ID = onboarding.MCA_ID
HYG_ID = onboarding.HYG_ID
D1_ID = onboarding.D1_ID
MCA_OBSERVATION_ID = onboarding.MCA_OBSERVATION_ID
HYG_OBSERVATION_ID = onboarding.HYG_OBSERVATION_ID
D1_OBSERVATION_ID = onboarding.D1_OBSERVATION_ID
OBSERVATION_IDS = (MCA_OBSERVATION_ID, HYG_OBSERVATION_ID, D1_OBSERVATION_ID)
STRATEGY_IDS = (MCA_ID, HYG_ID, D1_ID)

INITIAL_CAPITAL = onboarding.INITIAL_CAPITAL
PRIMARY_COST_BPS = onboarding.PRIMARY_COST_BPS
REFERENCE_ID = onboarding.REFERENCE_ID
REFERENCE_OBSERVATION_ID = onboarding.REFERENCE_OBSERVATION_ID
REFERENCE_WEIGHT = onboarding.REFERENCE_WEIGHT
SLEEVE_WEIGHT = onboarding.SLEEVE_WEIGHT
CURRENT_STATE_LABEL = onboarding.CURRENT_STATE_LABEL

RUN_ROOT = ROOT / "evidence" / "paper_demo_observation" / TASK_ID
ONBOARDING_DIR = (
    ROOT
    / "evidence"
    / "paper_demo_onboarding"
    / "onboard_role_aware_reassessment_candidates_standard_paper_demo_v1"
    / "latest"
)
ROLE_STANDARD_PATH = onboarding.ROLE_STANDARD_PATH
REASSESSMENT_DIR = onboarding.REASSESSMENT_DIR
ACTIVE_OBSERVATIONS_PATH = onboarding.ACTIVE_OBSERVATIONS_PATH
REGISTRY_PATH = onboarding.REGISTRY_PATH

PROTECTED_PATHS = (
    ROLE_STANDARD_PATH,
    REASSESSMENT_DIR,
    ONBOARDING_DIR,
    ROOT / "evidence" / "public_source_strategy_intake" / "accepted_47_selective_source_backed_intake_v2" / "latest",
    ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest",
    ROOT / "paper_forward_observations" / "paper_forward_vm_quality_lowvol_proxy_v1",
    ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    ROOT / "paper_forward_observations" / REFERENCE_OBSERVATION_ID,
    ROOT / "paper_forward_observations" / "paper_demo_faa_4m_top3_v1",
    ROOT / "paper_forward_observations" / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    ROOT / "data" / "cache",
    ROOT / "evidence" / "cache",
    ROOT / ".env.local",
    ROOT / "config.yaml",
)

REQUIRED_OUTPUTS = {
    "recording_manifest.yaml",
    "observation_state_before_after.csv",
    "offline_gate_results.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "normalized_data_manifest.csv",
    "required_session_coverage.csv",
    "mca_signal_and_target_record.csv",
    "mca_execution_and_performance_rows.csv",
    "hyg_frozen_target_reconciliation.csv",
    "hyg_execution_and_performance_rows.csv",
    "d1_reference_state_reconciliation.csv",
    "d1_sleeve_state_reconciliation.csv",
    "d1_combined_target_reconciliation.csv",
    "d1_execution_and_performance_rows.csv",
    "virtual_holdings_after.csv",
    "turnover_cost_reconciliation.csv",
    "missing_data_and_deviation_events.csv",
    "state_change_manifest.csv",
    "entity_count_reconciliation.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "recording_report.md",
}


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


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


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in paths}


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(inner) for inner in value]
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return value
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


def fields_for(rows: list[dict[str, Any]], leading: Iterable[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(rows, leading)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(canonicalize(payload), sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(canonicalize(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def atomic_write_yaml(path: Path, payload: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    write_yaml(temporary, payload)
    os.replace(temporary, path)


def run_id(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def observation_dir(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id


def observation_yaml_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / "active_observation.yaml"


def ledger_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / "component_forward_ledger.csv"


def active_entries() -> list[dict[str, Any]]:
    payload = read_yaml(ACTIVE_OBSERVATIONS_PATH)
    return list(payload.get("active_observations", []))


def registry_entries() -> list[dict[str, Any]]:
    payload = read_yaml(REGISTRY_PATH)
    return list(payload.get("strategies", []))


def ledger_fields(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return tuple(next(csv.reader(handle)))


def ledger_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def append_ledger_row(path: Path, row: dict[str, Any]) -> None:
    fields = ledger_fields(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writerow({key: csv_value(row.get(key)) for key in fields})


def regular_close_completed(session: date, now: datetime) -> bool:
    now_et = now.astimezone(standard_obs.repair.prior_activation.EASTERN)
    close = datetime.combine(session, time(16, 0), tzinfo=standard_obs.repair.prior_activation.EASTERN)
    return now_et >= close


def execution_close_not_yet_completed(session: date, now: datetime) -> bool:
    return not regular_close_completed(session, now)


def next_regular_session(session: date) -> date:
    return standard_obs.repair.prior_activation.next_regular_session(session)


def latest_symbol_session(frames: dict[str, pd.DataFrame], symbol: str) -> date | None:
    frame = frames.get(symbol, pd.DataFrame())
    if frame.empty:
        return None
    return date.fromisoformat(str(frame.iloc[-1]["date"]))


def has_symbol_session(frames: dict[str, pd.DataFrame], symbol: str, session: date) -> bool:
    frame = frames.get(symbol, pd.DataFrame())
    return not frame.empty and bool((frame["date"] == session.isoformat()).any())


def close_price(frames: dict[str, pd.DataFrame], symbol: str, session: date) -> float:
    frame = frames[symbol]
    rows = frame.loc[frame["date"] == session.isoformat()]
    if rows.empty:
        raise ValueError(f"{symbol} lacks required close for {session.isoformat()}")
    return float(rows.iloc[-1]["close"])


def ordered_union(*groups: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for item in group:
            if item not in result:
                result.append(item)
    return tuple(result)


def source_hash_for_symbols(
    frames: dict[str, pd.DataFrame], symbols: Iterable[str], through_date: date
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    cutoff = through_date.isoformat()
    for symbol in symbols:
        frame = frames.get(symbol, pd.DataFrame())
        subset = frame.loc[frame["date"] <= cutoff].to_dict(orient="records") if not frame.empty else []
        hashes[symbol] = canonical_hash(subset)
    return hashes


def offline_fixture_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mca_weights = {"SPY": 0.25, "QQQ": 0.25, "EEM": 0.125, "IWM": 0.125, "EFA": 0.125, "TLT": 0.05, "IYR": 0.05, "GLD": 0.025}
    rows.append(
        {
            "check_id": "mca_weekly_target_fixture",
            "status": "pass"
            if math.isclose(sum(mca_weights.values()), 1.0, abs_tol=1e-12)
            else "fail",
            "detail": "fixture verifies weekly target weight normalization without provider access",
        }
    )
    target = {"SPY": 1.0, "BIL": 0.0}
    capital = INITIAL_CAPITAL
    cost = capital * PRIMARY_COST_BPS / 10000.0
    post_cost = capital - cost
    prices = {"SPY": 100.0, "BIL": 50.0}
    holdings = {symbol: post_cost * weight for symbol, weight in target.items()}
    shares = {symbol: holdings[symbol] / prices[symbol] for symbol in target}
    rows.append(
        {
            "check_id": "hyg_frozen_target_execution_fixture",
            "status": "pass"
            if (
                math.isclose(sum(holdings.values()), post_cost, abs_tol=1e-12)
                and math.isclose(shares["SPY"], 29.985, abs_tol=1e-12)
            )
            else "fail",
            "detail": "fixture verifies 5 bps cost charged once and no performance row",
        }
    )
    reference = {"SPY": 0.5, "QUAL": 0.5}
    sleeve = {"SPY": 0.0, "BIL": 1.0}
    combined = onboarding.aggregate_d1_target(reference, sleeve)
    rows.append(
        {
            "check_id": "d1_reference_sleeve_aggregation_fixture",
            "status": "pass"
            if (
                math.isclose(sum(combined.values()), 1.0, abs_tol=1e-12)
                and math.isclose(combined["SPY"], 0.4, abs_tol=1e-12)
                and math.isclose(combined["BIL"], 0.2, abs_tol=1e-12)
            )
            else "fail",
            "detail": combined,
        }
    )
    return rows


def offline_gate() -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    active = active_entries()
    registry = registry_entries()
    onboarding_check = read_yaml(ONBOARDING_DIR / "onboarding_manifest.yaml")
    onboarding_consistency = json.loads((ONBOARDING_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    standard = read_yaml(ROLE_STANDARD_PATH)

    rows.append(
        {
            "check_id": "authoritative_standard_present",
            "status": "pass" if standard.get("status") == "authoritative_project_wide_standard" else "fail",
            "detail": relative(ROLE_STANDARD_PATH),
        }
    )
    rows.append(
        {
            "check_id": "onboarding_outcome_reconciled",
            "status": "pass"
            if (
                onboarding_check.get("outcome")
                == "role_aware_candidates_standard_paper_demo_onboarded"
                and onboarding_consistency.get("overall_pass") is True
            )
            else "fail",
            "detail": relative(ONBOARDING_DIR),
        }
    )
    for strategy_id, observation_id in zip(STRATEGY_IDS, OBSERVATION_IDS):
        active_count = sum(row.get("observation_id") == observation_id for row in active)
        registry_rows = [row for row in registry if row.get("strategy_id") == strategy_id]
        observation_path = observation_yaml_path(observation_id)
        ledger = ledger_path(observation_id)
        observation = read_yaml(observation_path)
        ledger_existing_rows = ledger_rows(ledger)
        keys = [
            (
                row.get("observation_id", ""),
                row.get("date", ""),
                row.get("row_type", ""),
                row.get("intended_execution_date", ""),
                row.get("completed_execution_date", ""),
                row.get("blocked_execution_reason", ""),
            )
            for row in ledger_existing_rows
        ]
        rows.append(
            {
                "check_id": f"{observation_id}_identity_and_eligibility",
                "strategy_id": strategy_id,
                "observation_id": observation_id,
                "status": "pass"
                if (
                    active_count == 1
                    and len(registry_rows) == 1
                    and registry_rows[0].get("eligibility") == "paper_demo_eligible"
                    and observation.get("status") == "active_paper_demo_observation"
                    and observation.get("historical_backfill") is False
                    and observation.get("real_money_authorization") is False
                )
                else "fail",
                "detail": {
                    "active_count": active_count,
                    "registry_count": len(registry_rows),
                    "ledger_rows": len(ledger_existing_rows),
                },
            }
        )
        rows.append(
            {
                "check_id": f"{observation_id}_ledger_unique_keys",
                "strategy_id": strategy_id,
                "observation_id": observation_id,
                "status": "pass" if len(keys) == len(set(keys)) else "fail",
                "detail": {"ledger_rows": len(ledger_existing_rows)},
            }
        )
    hyg = read_yaml(observation_yaml_path(HYG_OBSERVATION_ID))
    hyg_target = hyg.get("scheduled_target_allocation", {})
    rows.append(
        {
            "check_id": "hyg_august6_frozen_target_reconciled",
            "strategy_id": HYG_ID,
            "observation_id": HYG_OBSERVATION_ID,
            "status": "pass"
            if (
                hyg.get("latest_hyg_ema100_state", {}).get("signal_date") == "2026-08-06"
                and hyg_target == {"SPY": 1.0, "BIL": 0.0}
                and hyg.get("scheduled_first_execution_date") == "2026-08-07"
                and hyg.get("target_freeze_hash") == canonical_hash(hyg_target)
            )
            else "fail",
            "detail": {
                "signal_date": hyg.get("latest_hyg_ema100_state", {}).get("signal_date", ""),
                "target": hyg_target,
                "scheduled_first_execution_date": hyg.get("scheduled_first_execution_date", ""),
            },
        }
    )
    mca = read_yaml(observation_yaml_path(MCA_OBSERVATION_ID))
    rows.append(
        {
            "check_id": "mca_expired_july31_signal_not_executable",
            "strategy_id": MCA_ID,
            "observation_id": MCA_OBSERVATION_ID,
            "status": "pass"
            if (
                mca.get("initialization_status") == "pending_first_valid_signal_or_execution"
                and mca.get("latest_expired_weekly_signal_date") == "2026-07-31"
                and mca.get("expired_signal_execution_authorized") is False
            )
            else "fail",
            "detail": {
                "latest_expired_weekly_signal_date": mca.get("latest_expired_weekly_signal_date", ""),
                "latest_expired_weekly_execution_date": mca.get("latest_expired_weekly_execution_date", ""),
            },
        }
    )
    d1 = read_yaml(observation_yaml_path(D1_OBSERVATION_ID))
    rows.append(
        {
            "check_id": "d1_no_executable_combined_target_without_reference",
            "strategy_id": D1_ID,
            "observation_id": D1_OBSERVATION_ID,
            "status": "pass"
            if (
                d1.get("reference_portfolio", {}).get("reference_id") == REFERENCE_ID
                and d1.get("reference_portfolio", {}).get("weight") == REFERENCE_WEIGHT
                and (
                    d1.get("initialization_status") != "pending_first_valid_signal_or_execution"
                    or d1.get("scheduled_target_allocation", {}) == {}
                )
            )
            else "fail",
            "detail": {
                "initialization_status": d1.get("initialization_status", ""),
                "reference_status": d1.get("reference_portfolio", {}).get("reference_status", ""),
            },
        }
    )
    required_standalone_fields = {
        "target_weights",
        "holdings",
        "shares",
        "cash",
        "post_cost_equity",
        "transaction_cost",
        "intended_execution_date",
        "missing_data_events",
        "rule_deviations",
    }
    required_composite_fields = required_standalone_fields | {
        "reference_component_values",
        "d1_sleeve_target",
        "combined_target_weights",
        "inner_turnover",
        "outer_turnover",
    }
    rows.append(
        {
            "check_id": "standard_virtual_position_equity_execution_schema",
            "status": "pass"
            if (
                required_standalone_fields.issubset(set(ledger_fields(ledger_path(HYG_OBSERVATION_ID))))
                and required_standalone_fields.issubset(set(ledger_fields(ledger_path(MCA_OBSERVATION_ID))))
                and required_composite_fields.issubset(set(ledger_fields(ledger_path(D1_OBSERVATION_ID))))
            )
            else "fail",
            "detail": "standalone and composite ledger headers",
        }
    )
    rows.extend(offline_fixture_rows())
    rows.append(
        {
            "check_id": "no_historical_performance_row_present",
            "status": "pass"
            if all(
                not row.get("row_type", "").startswith("performance")
                for observation_id in OBSERVATION_IDS
                for row in ledger_rows(ledger_path(observation_id))
            )
            else "fail",
            "detail": "no ledger performance rows before provider access",
        }
    )
    return rows, all(row["status"] == "pass" for row in rows)


def provider_rows(market_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    attempt = dict(market_data.get("attempt", {}))
    provider = [attempt]
    raw = list(market_data.get("raw_rows", []))
    normalized = list(market_data.get("normalized_rows", []))
    coverage = list(market_data.get("coverage_rows", []))
    return provider, raw, normalized, coverage


def coverage_rows_with_requirements(
    market_data: dict[str, Any], latest_completed: date
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    coverage_by_symbol = {row["symbol"]: row for row in market_data.get("coverage_rows", [])}
    for symbol in ordered_union(standard_obs.REQUIRED_SYMBOLS, onboarding.MCA_SYMBOLS, onboarding.HYG_SYMBOLS):
        row = dict(coverage_by_symbol.get(symbol, {"symbol": symbol}))
        row["required_latest_session"] = latest_completed.isoformat()
        row["candidate_direct_required"] = symbol in ordered_union(
            onboarding.MCA_SYMBOLS, onboarding.HYG_SYMBOLS, onboarding.D1_SYMBOLS
        )
        row["reference_combo_required"] = symbol in standard_obs.REQUIRED_SYMBOLS
        row["latest_required_session_present"] = row.get("last_date") == latest_completed.isoformat()
        rows.append(row)
    return rows


def target_execution_row(
    observation_id: str,
    execution_date: date,
    target: dict[str, float],
    prices: dict[str, float],
    strategy_fingerprint: str,
    source_hashes: dict[str, str],
    row_status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    turnover = 1.0
    cost = INITIAL_CAPITAL * turnover * PRIMARY_COST_BPS / 10000.0
    post_cost = INITIAL_CAPITAL - cost
    holdings = {symbol: post_cost * float(weight) for symbol, weight in target.items()}
    shares = {
        symbol: 0.0 if holdings[symbol] == 0 else holdings[symbol] / prices[symbol]
        for symbol in target
    }
    row = {
        "observation_id": observation_id,
        "date": execution_date.isoformat(),
        "row_type": "virtual_initialization",
        "continuity_from_original_activation": False,
        "prior_interval_status": "unobserved_before_standard_current_target_initialization",
        "initial_virtual_capital": INITIAL_CAPITAL,
        "post_cost_equity": post_cost,
        "initialization_cost": cost,
        "target_weights": target,
        "holdings": holdings,
        "shares": shares,
        "cash": 0.0,
        "signal_date": "",
        "rebalance_reference_date": execution_date.isoformat(),
        "data_snapshot_hashes": source_hashes,
        "strategy_fingerprint": strategy_fingerprint,
        "orders_created": 0,
        "broker_calls": 0,
        "status": row_status,
        "target_turnover": turnover,
        "transaction_cost": cost,
        "intended_execution_date": execution_date.isoformat(),
        "completed_execution_date": execution_date.isoformat(),
        "missing_data_events": [],
        "blocked_execution_reason": "",
        "rule_deviations": [],
    }
    if extra:
        row.update(extra)
    return row


def update_observation_yaml(observation_id: str, updates: dict[str, Any]) -> None:
    path = observation_yaml_path(observation_id)
    payload = read_yaml(path)
    payload.update(updates)
    atomic_write_yaml(path, payload)


def d1_missing_event_row(
    current: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    run_dir: Path,
) -> dict[str, Any]:
    event = {
        "event_id": f"d1_reference_missing:{current['latest_completed_session'].isoformat()}:{'|'.join(current['missing_reference_symbols'])}",
        "event_type": "missing_data_event",
        "observation_id": D1_OBSERVATION_ID,
        "strategy_id": D1_ID,
        "event_date": current["latest_completed_session"].isoformat(),
        "missing_symbols": current["missing_reference_symbols"],
        "reference_status": current["reference_status"],
        "provider_role": "existing_standard_read_only_paper_demo_data_path",
        "remediation_chain_started": False,
        "execution_created": False,
        "performance_rows_created": 0,
        "evidence_path": relative(run_dir),
    }
    return {
        "observation_id": D1_OBSERVATION_ID,
        "date": current["latest_completed_session"].isoformat(),
        "row_type": "missing_data_event",
        "continuity_from_original_activation": False,
        "prior_interval_status": "pending_first_valid_signal_or_execution",
        "initial_virtual_capital": INITIAL_CAPITAL,
        "post_cost_equity": INITIAL_CAPITAL,
        "initialization_cost": 0.0,
        "target_weights": {},
        "holdings": {},
        "shares": {},
        "cash": INITIAL_CAPITAL,
        "signal_date": current["latest_completed_session"].isoformat(),
        "rebalance_reference_date": "",
        "data_snapshot_hashes": source_hash_for_symbols(
            frames, ("SPY", "BIL", *standard_obs.REQUIRED_SYMBOLS), current["latest_completed_session"]
        ),
        "strategy_fingerprint": read_yaml(observation_yaml_path(D1_OBSERVATION_ID)).get(
            "strategy_fingerprint", ""
        ),
        "orders_created": 0,
        "broker_calls": 0,
        "status": "pending_first_valid_signal_or_execution",
        "reference_component_values": current["reference_diagnostic_target"],
        "reference_component_weights": {"reference": REFERENCE_WEIGHT, "d1_sleeve": SLEEVE_WEIGHT},
        "d1_signal_state": current["d1"],
        "d1_sleeve_target": current["d1"]["target"],
        "combined_target_weights": {},
        "inner_turnover": 0.0,
        "outer_turnover": 0.0,
        "total_turnover": 0.0,
        "transaction_cost": 0.0,
        "intended_execution_date": "",
        "completed_execution_date": "",
        "missing_data_events": [event],
        "blocked_execution_reason": "reference_current_state_unavailable",
        "rule_deviations": [],
    }


def missing_event_exists(observation_id: str, event_date: date, reason: str) -> bool:
    for row in ledger_rows(ledger_path(observation_id)):
        if (
            row.get("row_type") == "missing_data_event"
            and row.get("date") == event_date.isoformat()
            and row.get("blocked_execution_reason") == reason
        ):
            return True
    return False


def initialization_exists(observation_id: str) -> bool:
    return any(
        row.get("row_type") == "virtual_initialization"
        for row in ledger_rows(ledger_path(observation_id))
    )


def record_mca(
    now: datetime, latest_completed: date, frames: dict[str, pd.DataFrame], run_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    observation = read_yaml(observation_yaml_path(MCA_OBSERVATION_ID))
    signal_rows: list[dict[str, Any]] = []
    exec_rows: list[dict[str, Any]] = []
    holdings_rows: list[dict[str, Any]] = []
    updates = 0

    scheduled_date_text = observation.get("scheduled_first_execution_date", "")
    if scheduled_date_text and not initialization_exists(MCA_OBSERVATION_ID):
        scheduled_date = date.fromisoformat(scheduled_date_text)
        if regular_close_completed(scheduled_date, now):
            target = observation.get("scheduled_target_allocation", {})
            prices = {symbol: close_price(frames, symbol, scheduled_date) for symbol in target}
            row = target_execution_row(
                MCA_OBSERVATION_ID,
                scheduled_date,
                target,
                prices,
                observation.get("strategy_fingerprint", ""),
                source_hash_for_symbols(frames, target.keys(), scheduled_date),
                "initialized_active_recording",
            )
            append_ledger_row(ledger_path(MCA_OBSERVATION_ID), row)
            update_observation_yaml(
                MCA_OBSERVATION_ID,
                {
                    "initialization_status": "initialized_active_recording",
                    "current_checkpoint_status": "active_recording_no_performance_rows",
                    "current_target_allocation": target,
                    "current_virtual_positions": row["holdings"],
                    "current_virtual_shares": row["shares"],
                    "virtual_cash": row["cash"],
                    "current_virtual_equity": row["post_cost_equity"],
                    "initialization_execution_date": scheduled_date.isoformat(),
                    "latest_committed_observation_date": scheduled_date.isoformat(),
                    "performance_rows": 0,
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(run_dir),
                },
            )
            exec_rows.append(row)
            updates += 1
        else:
            exec_rows.append(
                {
                    "observation_id": MCA_OBSERVATION_ID,
                    "status": "scheduled_execution_not_yet_due",
                    "scheduled_first_execution_date": scheduled_date.isoformat(),
                    "execution_created": False,
                    "performance_rows_created": 0,
                }
            )
    elif onboarding.is_final_regular_session_of_week(latest_completed):
        execution_date = next_regular_session(latest_completed)
        if execution_close_not_yet_completed(execution_date, now):
            target, state = onboarding.mca_target(frames, latest_completed)
            update_observation_yaml(
                MCA_OBSERVATION_ID,
                {
                    "initialization_status": "scheduled_for_first_prospective_execution",
                    "current_checkpoint_status": "target_frozen_pending_execution",
                    "pending_reason": "weekly_target_frozen_before_next_regular_session_close",
                    "latest_current_state_date": latest_completed.isoformat(),
                    "target_freeze_timestamp": now.isoformat(),
                    "target_freeze_event_label": CURRENT_STATE_LABEL,
                    "scheduled_target_allocation": target,
                    "scheduled_first_execution_date": execution_date.isoformat(),
                    "first_eligible_performance_date": next_regular_session(execution_date).isoformat(),
                    "latest_mca_signal_state": state,
                    "target_freeze_hash": canonical_hash(target),
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(run_dir),
                },
            )
            signal_rows.append(
                {
                    "observation_id": MCA_OBSERVATION_ID,
                    "signal_date": latest_completed.isoformat(),
                    "target": target,
                    "scheduled_first_execution_date": execution_date.isoformat(),
                    "status": "target_frozen_pending_execution",
                }
            )
            updates += 1
        else:
            signal_rows.append(
                {
                    "observation_id": MCA_OBSERVATION_ID,
                    "signal_date": latest_completed.isoformat(),
                    "status": "weekly_signal_execution_boundary_passed_no_late_reconstruction",
                    "execution_created": False,
                }
            )
    else:
        next_signal = onboarding.next_weekly_signal_after(latest_completed)
        signal_rows.append(
            {
                "observation_id": MCA_OBSERVATION_ID,
                "latest_completed_session": latest_completed.isoformat(),
                "latest_completed_session_is_weekly_signal": False,
                "next_valid_weekly_signal_date": next_signal.isoformat(),
                "next_valid_weekly_execution_date": next_regular_session(next_signal).isoformat(),
                "status": "pending_first_valid_signal_or_execution",
                "expired_signal_execution_authorized": False,
            }
        )
        exec_rows.append(
            {
                "observation_id": MCA_OBSERVATION_ID,
                "status": "no_execution_due",
                "execution_created": False,
                "performance_rows_created": 0,
            }
        )
    return signal_rows, exec_rows, holdings_rows, updates


def record_hyg(
    now: datetime, latest_completed: date, frames: dict[str, pd.DataFrame], run_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    observation = read_yaml(observation_yaml_path(HYG_OBSERVATION_ID))
    target = observation.get("scheduled_target_allocation", {})
    scheduled_date = date.fromisoformat(observation.get("scheduled_first_execution_date"))
    freeze_rows = [
        {
            "observation_id": HYG_OBSERVATION_ID,
            "strategy_id": HYG_ID,
            "stored_signal_date": observation.get("latest_hyg_ema100_state", {}).get("signal_date", ""),
            "stored_target": target,
            "stored_target_hash": observation.get("target_freeze_hash", ""),
            "recomputed_target_hash": canonical_hash(target),
            "target_changed": False,
            "scheduled_first_execution_date": scheduled_date.isoformat(),
            "status": "pass"
            if (
                target == {"SPY": 1.0, "BIL": 0.0}
                and observation.get("target_freeze_hash") == canonical_hash(target)
            )
            else "fail",
        }
    ]
    execution_rows: list[dict[str, Any]] = []
    holdings_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    updates = 0
    if initialization_exists(HYG_OBSERVATION_ID):
        execution_rows.append(
            {
                "observation_id": HYG_OBSERVATION_ID,
                "status": "initialization_already_recorded_no_duplicate",
                "execution_created": False,
                "performance_rows_created": 0,
            }
        )
    elif regular_close_completed(scheduled_date, now):
        prices = {symbol: close_price(frames, symbol, scheduled_date) for symbol in target}
        row = target_execution_row(
            HYG_OBSERVATION_ID,
            scheduled_date,
            target,
            prices,
            observation.get("strategy_fingerprint", ""),
            source_hash_for_symbols(frames, target.keys(), scheduled_date),
            "initialized_active_recording",
        )
        row["signal_date"] = "2026-08-06"
        append_ledger_row(ledger_path(HYG_OBSERVATION_ID), row)
        update_observation_yaml(
            HYG_OBSERVATION_ID,
            {
                "initialization_status": "initialized_active_recording",
                "current_checkpoint_status": "active_recording_no_performance_rows",
                "pending_reason": "",
                "current_target_allocation": target,
                "current_virtual_positions": row["holdings"],
                "current_virtual_shares": row["shares"],
                "virtual_cash": row["cash"],
                "current_virtual_equity": row["post_cost_equity"],
                "initialization_execution_date": scheduled_date.isoformat(),
                "latest_committed_observation_date": scheduled_date.isoformat(),
                "performance_rows": 0,
                "latest_operational_update_id": TASK_ID,
                "latest_operational_update_evidence_path": relative(run_dir),
            },
        )
        execution_rows.append(row)
        holdings_rows.append(
            {
                "observation_id": HYG_OBSERVATION_ID,
                "date": scheduled_date.isoformat(),
                "target": target,
                "holdings": row["holdings"],
                "shares": row["shares"],
                "cash": row["cash"],
                "post_cost_equity": row["post_cost_equity"],
            }
        )
        turnover_rows.append(
            {
                "observation_id": HYG_OBSERVATION_ID,
                "date": scheduled_date.isoformat(),
                "event": "virtual_initialization",
                "turnover": 1.0,
                "transaction_cost": row["transaction_cost"],
                "cost_bps": PRIMARY_COST_BPS,
                "cost_charged_once": True,
                "status": "pass",
            }
        )
        updates += 1
    else:
        execution_rows.append(
            {
                "observation_id": HYG_OBSERVATION_ID,
                "status": "scheduled_execution_not_yet_due",
                "scheduled_first_execution_date": scheduled_date.isoformat(),
                "latest_completed_session": latest_completed.isoformat(),
                "execution_created": False,
                "performance_rows_created": 0,
            }
        )
    return freeze_rows, execution_rows, holdings_rows, turnover_rows, updates


def reference_state(
    frames: dict[str, pd.DataFrame], latest_completed: date
) -> dict[str, Any]:
    missing = [
        symbol
        for symbol in standard_obs.REQUIRED_SYMBOLS
        if not has_symbol_session(frames, symbol, latest_completed)
    ]
    if not missing:
        target, rows, components = standard_obs.reference_current_target(
            frames, pd.Timestamp(latest_completed)
        )
        return {
            "current": True,
            "missing": [],
            "date": latest_completed,
            "target": target,
            "rows": rows,
            "components": components,
            "status": "current_reference_target_reconciled",
        }
    latest_dates = [
        latest_symbol_session(frames, symbol)
        for symbol in standard_obs.REQUIRED_SYMBOLS
        if latest_symbol_session(frames, symbol) is not None
    ]
    if not latest_dates:
        return {
            "current": False,
            "missing": missing,
            "date": None,
            "target": {},
            "rows": [],
            "components": {},
            "status": "reference_market_data_unavailable",
        }
    diagnostic_date = min(latest_dates)
    target, rows, components = standard_obs.reference_current_target(
        frames, pd.Timestamp(diagnostic_date)
    )
    return {
        "current": False,
        "missing": missing,
        "date": diagnostic_date,
        "target": target,
        "rows": rows,
        "components": components,
        "status": "pending_latest_reference_common_session",
    }


def record_d1(
    now: datetime, latest_completed: date, frames: dict[str, pd.DataFrame], run_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int, int]:
    observation = read_yaml(observation_yaml_path(D1_OBSERVATION_ID))
    ref = reference_state(frames, latest_completed)
    sleeve = onboarding.d1_state(frames, latest_completed)
    combined = onboarding.aggregate_d1_target(ref["target"], sleeve["target"]) if ref["current"] else {}
    diagnostic_combined = (
        onboarding.aggregate_d1_target(ref["target"], sleeve["target"]) if ref["target"] else {}
    )
    reference_rows = [
        {
            "observation_id": D1_OBSERVATION_ID,
            "strategy_id": D1_ID,
            "reference_id": REFERENCE_ID,
            "reference_observation_id": REFERENCE_OBSERVATION_ID,
            "latest_completed_session": latest_completed.isoformat(),
            "reference_state_date": "" if ref["date"] is None else ref["date"].isoformat(),
            "reference_current": ref["current"],
            "missing_reference_symbols": ref["missing"],
            "reference_target": ref["target"],
            "component_targets": ref["components"],
            "execution_authorized": ref["current"],
            "status": ref["status"],
        }
    ]
    sleeve_rows = [
        {
            "observation_id": D1_OBSERVATION_ID,
            "strategy_id": D1_ID,
            "signal_date": sleeve["signal_date"],
            "annualized_slope": sleeve["annualized_slope"],
            "r_squared": sleeve["r_squared"],
            "sleeve_target": sleeve["target"],
            "state_role": CURRENT_STATE_LABEL,
            "status": "pass",
        }
    ]
    combined_rows = [
        {
            "observation_id": D1_OBSERVATION_ID,
            "strategy_id": D1_ID,
            "reference_weight": REFERENCE_WEIGHT,
            "sleeve_weight": SLEEVE_WEIGHT,
            "combined_target": combined,
            "diagnostic_combined_target": diagnostic_combined,
            "weights_nonnegative": all(value >= -1e-15 for value in combined.values()) if combined else "",
            "weight_sum": sum(combined.values()) if combined else "",
            "gross_exposure": sum(abs(value) for value in combined.values()) if combined else "",
            "execution_authorized": bool(combined),
            "status": "pass" if combined else "pending_reference_current_state",
        }
    ]
    execution_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    updates = 0
    missing_events = 0

    scheduled_text = observation.get("scheduled_first_execution_date", "")
    if scheduled_text and not initialization_exists(D1_OBSERVATION_ID):
        scheduled_date = date.fromisoformat(scheduled_text)
        if regular_close_completed(scheduled_date, now):
            target = observation.get("scheduled_target_allocation", {})
            prices = {symbol: close_price(frames, symbol, scheduled_date) for symbol in target}
            row = target_execution_row(
                D1_OBSERVATION_ID,
                scheduled_date,
                target,
                prices,
                observation.get("strategy_fingerprint", ""),
                source_hash_for_symbols(frames, target.keys(), scheduled_date),
                "initialized_active_recording",
                {
                    "reference_component_values": observation.get("scheduled_reference_target", {}),
                    "reference_component_weights": {"reference": REFERENCE_WEIGHT, "d1_sleeve": SLEEVE_WEIGHT},
                    "d1_signal_state": observation.get("latest_d1_signal_state", {}),
                    "d1_sleeve_target": observation.get("scheduled_d1_sleeve_target", {}),
                    "combined_target_weights": target,
                    "inner_turnover": 0.0,
                    "outer_turnover": 0.0,
                    "total_turnover": 1.0,
                },
            )
            append_ledger_row(ledger_path(D1_OBSERVATION_ID), row)
            update_observation_yaml(
                D1_OBSERVATION_ID,
                {
                    "initialization_status": "initialized_active_recording",
                    "current_checkpoint_status": "active_recording_no_performance_rows",
                    "pending_reason": "",
                    "current_target_allocation": target,
                    "current_virtual_positions": row["holdings"],
                    "current_virtual_shares": row["shares"],
                    "virtual_cash": row["cash"],
                    "current_virtual_equity": row["post_cost_equity"],
                    "initialization_execution_date": scheduled_date.isoformat(),
                    "latest_committed_observation_date": scheduled_date.isoformat(),
                    "performance_rows": 0,
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(run_dir),
                },
            )
            execution_rows.append(row)
            updates += 1
        else:
            execution_rows.append(
                {
                    "observation_id": D1_OBSERVATION_ID,
                    "status": "scheduled_execution_not_yet_due",
                    "scheduled_first_execution_date": scheduled_date.isoformat(),
                    "execution_created": False,
                    "performance_rows_created": 0,
                }
            )
    elif ref["current"]:
        execution_date = standard_obs.next_initialization_close(now, latest_completed)
        if execution_close_not_yet_completed(execution_date, now):
            update_observation_yaml(
                D1_OBSERVATION_ID,
                {
                    "initialization_status": "scheduled_for_first_prospective_execution",
                    "current_checkpoint_status": "target_frozen_pending_execution",
                    "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
                    "target_freeze_timestamp": now.isoformat(),
                    "target_freeze_event_label": CURRENT_STATE_LABEL,
                    "reference_portfolio": {
                        "reference_id": REFERENCE_ID,
                        "observation_id": REFERENCE_OBSERVATION_ID,
                        "weight": REFERENCE_WEIGHT,
                        "reference_status": ref["status"],
                        "missing_reference_symbols": [],
                        "target": ref["target"],
                        "component_targets": ref["components"],
                        "diagnostic_target_execution_authorized": True,
                    },
                    "candidate_sleeve": {
                        "strategy_id": D1_ID,
                        "weight": SLEEVE_WEIGHT,
                        "active_asset": "SPY",
                        "defensive_asset": "BIL",
                        "latest_reconciled_signal_date": sleeve["signal_date"],
                        "latest_reconciled_target": sleeve["target"],
                        "latest_reconciled_state_role": CURRENT_STATE_LABEL,
                    },
                    "combined_target_status": "target_frozen_pending_execution",
                    "scheduled_target_allocation": combined,
                    "scheduled_reference_target": ref["target"],
                    "scheduled_d1_sleeve_target": sleeve["target"],
                    "scheduled_first_execution_date": execution_date.isoformat(),
                    "first_eligible_performance_date": next_regular_session(execution_date).isoformat(),
                    "latest_d1_signal_state": sleeve,
                    "target_freeze_hash": canonical_hash(combined),
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(run_dir),
                },
            )
            combined_rows[0]["scheduled_first_execution_date"] = execution_date.isoformat()
            combined_rows[0]["status"] = "target_frozen_pending_execution"
            updates += 1
        else:
            combined_rows[0]["status"] = "current_target_available_but_execution_boundary_passed_no_late_freeze"
    else:
        if not missing_event_exists(
            D1_OBSERVATION_ID, latest_completed, "reference_current_state_unavailable"
        ):
            current = {
                "latest_completed_session": latest_completed,
                "missing_reference_symbols": ref["missing"],
                "reference_status": ref["status"],
                "reference_diagnostic_target": ref["target"],
                "d1": sleeve,
            }
            row = d1_missing_event_row(current, frames, run_dir)
            append_ledger_row(ledger_path(D1_OBSERVATION_ID), row)
            update_observation_yaml(
                D1_OBSERVATION_ID,
                {
                    "initialization_status": "pending_first_valid_signal_or_execution",
                    "current_checkpoint_status": "onboarded_pending_first_valid_reference_or_execution",
                    "pending_reason": "reference_current_state_unavailable_for_latest_completed_session_no_late_execution",
                    "latest_current_state_date": latest_completed.isoformat(),
                    "reference_portfolio": {
                        "reference_id": REFERENCE_ID,
                        "observation_id": REFERENCE_OBSERVATION_ID,
                        "weight": REFERENCE_WEIGHT,
                        "reference_status": ref["status"],
                        "missing_reference_symbols": ref["missing"],
                        "target": {},
                        "component_targets": {},
                        "last_stale_diagnostic_reference_date": ""
                        if ref["date"] is None
                        else ref["date"].isoformat(),
                        "last_stale_diagnostic_reference_target": ref["target"],
                        "last_stale_diagnostic_component_targets": ref["components"],
                        "diagnostic_target_execution_authorized": False,
                    },
                    "candidate_sleeve": {
                        "strategy_id": D1_ID,
                        "weight": SLEEVE_WEIGHT,
                        "active_asset": "SPY",
                        "defensive_asset": "BIL",
                        "latest_reconciled_signal_date": sleeve["signal_date"],
                        "latest_reconciled_target": sleeve["target"],
                        "latest_reconciled_state_role": CURRENT_STATE_LABEL,
                    },
                    "combined_target_status": "pending_current_reference_state_no_late_execution",
                    "scheduled_target_allocation": {},
                    "scheduled_reference_target": {},
                    "scheduled_d1_sleeve_target": {},
                    "scheduled_first_execution_date": "",
                    "first_eligible_performance_date": "",
                    "last_stale_diagnostic_combined_target": diagnostic_combined,
                    "last_stale_diagnostic_target_execution_authorized": False,
                    "latest_d1_signal_state": sleeve,
                    "target_freeze_timestamp": "",
                    "target_freeze_event_label": "",
                    "target_freeze_hash": "",
                    "latest_missing_data_event": row["missing_data_events"][0],
                    "latest_operational_update_id": TASK_ID,
                    "latest_operational_update_evidence_path": relative(run_dir),
                },
            )
            missing_rows.append(row["missing_data_events"][0])
            updates += 1
            missing_events += 1
        else:
            missing_rows.append(
                {
                    "event_type": "missing_data_event",
                    "observation_id": D1_OBSERVATION_ID,
                    "event_date": latest_completed.isoformat(),
                    "missing_symbols": ref["missing"],
                    "status": "already_recorded_no_duplicate",
                }
            )
        execution_rows.append(
            {
                "observation_id": D1_OBSERVATION_ID,
                "status": "pending_reference_current_state",
                "execution_created": False,
                "performance_rows_created": 0,
            }
        )
    return reference_rows, sleeve_rows, combined_rows, execution_rows, missing_rows, updates, missing_events


def observation_state_rows(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id, strategy_id in zip(OBSERVATION_IDS, STRATEGY_IDS):
        before_obs = before["observations"][observation_id]
        after_obs = after["observations"][observation_id]
        rows.append(
            {
                "strategy_id": strategy_id,
                "observation_id": observation_id,
                "before_initialization_status": before_obs.get("initialization_status", ""),
                "after_initialization_status": after_obs.get("initialization_status", ""),
                "before_checkpoint_status": before_obs.get("current_checkpoint_status", ""),
                "after_checkpoint_status": after_obs.get("current_checkpoint_status", ""),
                "before_ledger_rows": before["ledger_rows"][observation_id],
                "after_ledger_rows": after["ledger_rows"][observation_id],
                "before_performance_rows": before_obs.get("performance_rows", 0),
                "after_performance_rows": after_obs.get("performance_rows", 0),
                "historical_backfill": after_obs.get("historical_backfill", ""),
                "broker_orders": after_obs.get("paper_orders", ""),
                "real_money_authorization": after_obs.get("real_money_authorization", ""),
                "status": "pass",
            }
        )
    return rows


def snapshot_state() -> dict[str, Any]:
    return {
        "observations": {
            observation_id: read_yaml(observation_yaml_path(observation_id))
            for observation_id in OBSERVATION_IDS
        },
        "ledger_rows": {
            observation_id: len(ledger_rows(ledger_path(observation_id)))
            for observation_id in OBSERVATION_IDS
        },
        "hashes": {
            observation_id: tree_hash(observation_dir(observation_id))
            for observation_id in OBSERVATION_IDS
        },
    }


def state_change_rows(
    before: dict[str, Any],
    after: dict[str, Any],
    protected_before: dict[str, str],
    protected_after: dict[str, str],
    run_dir: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id in OBSERVATION_IDS:
        rows.append(
            {
                "path": relative(observation_dir(observation_id)),
                "change_class": "standard_observation_directory",
                "before_hash": before["hashes"][observation_id],
                "after_hash": after["hashes"][observation_id],
                "changed": before["hashes"][observation_id] != after["hashes"][observation_id],
                "status": "pass",
            }
        )
    for path_text, before_hash in protected_before.items():
        after_hash = protected_after.get(path_text, "missing")
        rows.append(
            {
                "path": path_text,
                "change_class": "protected_state_hash_reconciliation",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "changed": before_hash != after_hash,
                "status": "pass" if before_hash == after_hash else "fail",
            }
        )
    rows.append(
        {
            "path": relative(run_dir),
            "change_class": "immutable_recording_packet",
            "before_hash": "missing",
            "after_hash": tree_hash(run_dir),
            "changed": True,
            "status": "pass",
        }
    )
    return rows


def entity_rows(
    updated_observations: int,
    execution_events: int,
    performance_rows: int,
    missing_events: int,
    outcome: str,
) -> list[dict[str, Any]]:
    return [
        {
            "task_id": TASK_ID,
            "outcome": outcome,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "new_paper_demo_observations": 0,
            "existing_paper_demo_observations_updated": updated_observations,
            "execution_events": execution_events,
            "performance_rows": performance_rows,
            "missing_data_deviation_events": missing_events,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
        }
    ]


def outcome_for(updates: int, execution_events: int, performance_rows: int, failures: list[str]) -> str:
    if failures:
        return OUTCOME_BLOCKED
    if updates > 0 or execution_events > 0 or performance_rows > 0:
        return OUTCOME_UPDATED
    return OUTCOME_PENDING


def write_common_outputs(
    run_dir: Path,
    started: datetime,
    ended: datetime,
    outcome: str,
    latest_completed: date | None,
    offline_rows: list[dict[str, Any]],
    provider: list[dict[str, Any]],
    raw: list[dict[str, Any]],
    normalized: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    mca_signal_rows: list[dict[str, Any]],
    mca_execution_rows: list[dict[str, Any]],
    hyg_reconciliation_rows: list[dict[str, Any]],
    hyg_execution_rows: list[dict[str, Any]],
    d1_reference_rows: list[dict[str, Any]],
    d1_sleeve_rows: list[dict[str, Any]],
    d1_combined_rows: list[dict[str, Any]],
    d1_execution_rows: list[dict[str, Any]],
    holdings_rows: list[dict[str, Any]],
    turnover_rows: list[dict[str, Any]],
    missing_rows: list[dict[str, Any]],
    state_change: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    failures: list[str],
) -> dict[str, Any]:
    next_action = NEXT_BLOCKED if outcome == OUTCOME_BLOCKED else NEXT_RECORD
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "run_id": run_dir.name,
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "outcome": outcome,
        "next_action": next_action,
        "latest_fully_completed_session": "" if latest_completed is None else latest_completed.isoformat(),
        "observation_ids": list(OBSERVATION_IDS),
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_paper_demo_observations": 0,
        "broker_or_paper_orders": 0,
        "real_money_actions": 0,
    }
    write_yaml(run_dir / "recording_manifest.yaml", manifest)
    write_csv(run_dir / "observation_state_before_after.csv", state_rows, ("strategy_id", "observation_id", "status"))
    write_csv(run_dir / "offline_gate_results.csv", offline_rows, ("check_id", "strategy_id", "observation_id", "status"))
    write_csv(run_dir / "provider_attempt_log.csv", provider, ("provider", "provider_role", "status"))
    write_csv(run_dir / "raw_retrieval_manifest.csv", raw, ("page_number", "path", "hash"))
    write_csv(run_dir / "normalized_data_manifest.csv", normalized, ("symbol", "path", "normalized_hash"))
    write_csv(run_dir / "required_session_coverage.csv", coverage, ("symbol", "required_latest_session"))
    write_csv(run_dir / "mca_signal_and_target_record.csv", mca_signal_rows, ("observation_id", "status"))
    write_csv(run_dir / "mca_execution_and_performance_rows.csv", mca_execution_rows, ("observation_id", "status"))
    write_csv(run_dir / "hyg_frozen_target_reconciliation.csv", hyg_reconciliation_rows, ("observation_id", "status"))
    write_csv(run_dir / "hyg_execution_and_performance_rows.csv", hyg_execution_rows, ("observation_id", "status"))
    write_csv(run_dir / "d1_reference_state_reconciliation.csv", d1_reference_rows, ("observation_id", "status"))
    write_csv(run_dir / "d1_sleeve_state_reconciliation.csv", d1_sleeve_rows, ("observation_id", "status"))
    write_csv(run_dir / "d1_combined_target_reconciliation.csv", d1_combined_rows, ("observation_id", "status"))
    write_csv(run_dir / "d1_execution_and_performance_rows.csv", d1_execution_rows, ("observation_id", "status"))
    write_csv(run_dir / "virtual_holdings_after.csv", holdings_rows, ("observation_id", "date"))
    write_csv(run_dir / "turnover_cost_reconciliation.csv", turnover_rows, ("observation_id", "date", "status"))
    write_csv(run_dir / "missing_data_and_deviation_events.csv", missing_rows, ("observation_id", "event_date", "event_type"))
    write_csv(run_dir / "state_change_manifest.csv", state_change, ("path", "change_class", "status"))
    write_csv(run_dir / "entity_count_reconciliation.csv", entities, ("task_id", "outcome"))
    write_csv(
        run_dir / "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "mode": MODE,
                "stage": STAGE,
                "outcome": outcome,
                "primary_reason": "" if not failures else failures[0],
                "exact_next_action": next_action,
                "next_action_executed": False,
            }
        ],
        ("task_id", "outcome", "exact_next_action"),
    )
    write_csv(
        run_dir / "failure_reasons.csv",
        [{"task_id": TASK_ID, "failure_reason": "", "status": "none"}]
        if not failures
        else [
            {"task_id": TASK_ID, "failure_reason": failure, "status": "active_failure"}
            for failure in failures
        ],
        ("task_id", "failure_reason", "status"),
    )
    write_csv(
        run_dir / "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": outcome,
                "next_action": next_action,
                "next_action_executed": False,
            }
        ],
        ("task_id", "next_action"),
    )
    report = f"""# Role-Aware Standard Paper/Demo Observation Recording

## Outcome

**`{outcome}`**

The recorder reused the three existing standard paper/demo observations and created no strategy,
trial, observation, validation workflow, broker order, paper order, or real-money action.

Latest fully completed session: `{'' if latest_completed is None else latest_completed.isoformat()}`.

Exact next action: `{next_action}`.
"""
    (run_dir / "recording_report.md").write_text(report, encoding="utf-8")
    required_present = sorted(name for name in REQUIRED_OUTPUTS if (run_dir / name).exists() or name == "consistency_check.json")
    missing_required = sorted(REQUIRED_OUTPUTS - set(required_present))
    check = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "overall_pass": (
            not failures
            and not missing_required
            and all(row.get("status") == "pass" for row in offline_rows)
            and all(row.get("status") == "pass" for row in state_change if row.get("change_class") == "protected_state_hash_reconciliation")
            and entities[0]["new_strategy_configurations"] == 0
            and entities[0]["new_experiment_trials"] == 0
            and entities[0]["new_paper_demo_observations"] == 0
            and entities[0]["broker_or_paper_orders"] == 0
        ),
        "required_output_reconciliation": {
            "required_count": len(REQUIRED_OUTPUTS),
            "present": required_present,
            "missing": missing_required,
        },
        "entity_count_reconciliation": entities[0],
        "broker_account_order_guard": {
            "account_endpoint_called": bool(provider and provider[0].get("account_endpoint_called", False)),
            "position_endpoint_called": bool(provider and provider[0].get("position_endpoint_called", False)),
            "order_endpoint_called": bool(provider and provider[0].get("order_endpoint_called", False)),
            "broker_calls": 0 if not provider else provider[0].get("broker_calls", 0),
            "orders_created": 0 if not provider else provider[0].get("orders_created", 0),
        },
        "no_backfill": {
            "mca_performance_rows": sum(1 for row in ledger_rows(ledger_path(MCA_OBSERVATION_ID)) if row.get("row_type", "").startswith("performance")),
            "hyg_performance_rows": sum(1 for row in ledger_rows(ledger_path(HYG_OBSERVATION_ID)) if row.get("row_type", "").startswith("performance")),
            "d1_performance_rows": sum(1 for row in ledger_rows(ledger_path(D1_OBSERVATION_ID)) if row.get("row_type", "").startswith("performance")),
        },
        "failures": failures,
    }
    write_json(run_dir / "consistency_check.json", check)
    return check


def run(now: datetime | None = None) -> dict[str, Any]:
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    started = started.astimezone(timezone.utc)
    run_dir = RUN_ROOT / run_id(started)
    run_dir.mkdir(parents=True, exist_ok=False)

    protected_before = map_hashes(PROTECTED_PATHS)
    before = snapshot_state()
    offline_rows, offline_pass = offline_gate()
    failures: list[str] = []
    latest_completed: date | None = None
    provider: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    mca_signal_rows: list[dict[str, Any]] = []
    mca_execution_rows: list[dict[str, Any]] = []
    hyg_reconciliation_rows: list[dict[str, Any]] = []
    hyg_execution_rows: list[dict[str, Any]] = []
    d1_reference_rows: list[dict[str, Any]] = []
    d1_sleeve_rows: list[dict[str, Any]] = []
    d1_combined_rows: list[dict[str, Any]] = []
    d1_execution_rows: list[dict[str, Any]] = []
    holdings_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    updates = 0
    execution_events = 0
    performance_rows = 0
    missing_events = 0

    if not offline_pass:
        failures.append("local_methodology_failure")
        outcome = OUTCOME_BLOCKED
    else:
        latest_completed = standard_obs.latest_fully_completed_session(started)
        symbols = ordered_union(standard_obs.REQUIRED_SYMBOLS, onboarding.MCA_SYMBOLS, onboarding.HYG_SYMBOLS)
        market_data = standard_obs.retrieve_alpaca(
            run_dir,
            symbols,
            date(2018, 1, 1),
            latest_completed + timedelta(days=1),
        )
        provider, raw, normalized, _coverage = provider_rows(market_data)
        coverage = coverage_rows_with_requirements(market_data, latest_completed)
        frames = market_data.get("frames", {})
        try:
            mca_signal_rows, mca_execution_rows, mca_holdings, mca_updates = record_mca(
                started, latest_completed, frames, run_dir
            )
            updates += mca_updates
            holdings_rows.extend(mca_holdings)
            (
                hyg_reconciliation_rows,
                hyg_execution_rows,
                hyg_holdings,
                hyg_turnover,
                hyg_updates,
            ) = record_hyg(started, latest_completed, frames, run_dir)
            updates += hyg_updates
            holdings_rows.extend(hyg_holdings)
            turnover_rows.extend(hyg_turnover)
            (
                d1_reference_rows,
                d1_sleeve_rows,
                d1_combined_rows,
                d1_execution_rows,
                d1_missing,
                d1_updates,
                d1_missing_events,
            ) = record_d1(started, latest_completed, frames, run_dir)
            updates += d1_updates
            missing_events += d1_missing_events
            missing_rows.extend(d1_missing)
        except BaseException as exc:  # noqa: BLE001 - operational failures become evidence.
            failures.append("local_methodology_failure:" + standard_obs.sanitize_error(exc))
        execution_events = sum(
            1
            for row in (*mca_execution_rows, *hyg_execution_rows, *d1_execution_rows)
            if row.get("row_type") == "virtual_initialization"
        )
        performance_rows = sum(
            1
            for observation_id in OBSERVATION_IDS
            for row in ledger_rows(ledger_path(observation_id))
            if row.get("row_type", "").startswith("performance")
        )
        outcome = outcome_for(updates, execution_events, performance_rows, failures)

    after = snapshot_state()
    protected_after = map_hashes(PROTECTED_PATHS)
    state_rows = observation_state_rows(before, after)
    state_change = state_change_rows(before, after, protected_before, protected_after, run_dir)
    updated_observations = sum(
        1
        for observation_id in OBSERVATION_IDS
        if before["hashes"][observation_id] != after["hashes"][observation_id]
    )
    entities = entity_rows(
        updated_observations, execution_events, performance_rows, missing_events, outcome
    )
    ended = datetime.now(timezone.utc)
    check = write_common_outputs(
        run_dir,
        started,
        ended,
        outcome,
        latest_completed,
        offline_rows,
        provider,
        raw,
        normalized,
        coverage,
        state_rows,
        mca_signal_rows,
        mca_execution_rows,
        hyg_reconciliation_rows,
        hyg_execution_rows,
        d1_reference_rows,
        d1_sleeve_rows,
        d1_combined_rows,
        d1_execution_rows,
        holdings_rows,
        turnover_rows,
        missing_rows,
        state_change,
        entities,
        failures,
    )
    return {
        "outcome": outcome,
        "next_action": NEXT_BLOCKED if outcome == OUTCOME_BLOCKED else NEXT_RECORD,
        "run_dir": relative(run_dir),
        "overall_pass": check["overall_pass"],
        "latest_completed_session": "" if latest_completed is None else latest_completed.isoformat(),
        "execution_events": execution_events,
        "performance_rows": performance_rows,
        "missing_events": missing_events,
        "updated_observations": updated_observations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now-utc", default="")
    args = parser.parse_args(argv)
    now = None
    if args.now_utc:
        now = datetime.fromisoformat(args.now_utc.replace("Z", "+00:00"))
    result = run(now)
    print(json.dumps(canonicalize(result), indent=2, sort_keys=True))
    return 0 if result.get("outcome") != OUTCOME_BLOCKED else 1


if __name__ == "__main__":
    raise SystemExit(main())
