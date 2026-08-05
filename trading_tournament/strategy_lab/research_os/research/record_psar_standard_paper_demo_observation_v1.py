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

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import (
    AlpacaClient,
    AlpacaClientConfig,
)
from execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    load_alpaca_credentials,
)
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import (
    parse_bars_response,
)
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    correct_psar_stage_and_onboard_paper_demo_observation_v1 as onboarding,
)
from strategy_lab.research_os.research import (
    repair_and_retry_decelerated_psar_prospective_activation_v1 as repair,
)


TASK_ID = "record_psar_standard_paper_demo_observation_v1"
MODE = "standard-paper-demo-recording"
STAGE = "paper-demo-onboarding"

OUTCOME_TARGET_FROZEN = "psar_standard_target_frozen_pending_execution"
OUTCOME_INITIALIZED = "psar_standard_observation_initialized"
OUTCOME_UPDATED = "psar_standard_observation_recording_updated"
OUTCOME_NO_NEW_SESSION = "psar_standard_observation_recording_no_new_session"
OUTCOME_PENDING = "psar_standard_observation_recording_pending"
OUTCOME_BLOCKED = "psar_standard_observation_recording_blocked"

NEXT_RECORD = TASK_ID
NEXT_PENDING = "resume_strategy_discovery_with_psar_observation_pending_v1"
NEXT_BLOCKED = "direction_owner_review_psar_standard_recording_block_v1"

STRATEGY_ID = onboarding.STRATEGY_ID
OBSERVATION_ID = onboarding.OBSERVATION_ID
REFERENCE_ID = onboarding.REFERENCE_ID
REFERENCE_OBSERVATION_ID = onboarding.REFERENCE_OBSERVATION_ID
REFERENCE_WEIGHT = onboarding.REFERENCE_WEIGHT
PSAR_WEIGHT = onboarding.PSAR_WEIGHT
PRIMARY_COST_BPS = onboarding.PRIMARY_COST_BPS

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
VM_RISK_ASSETS = ("SPLV", "USMV", "QUAL", "SPY")
VM_SYMBOLS = (*VM_RISK_ASSETS, "BIL")
DSR_RISK_ASSETS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC")
DSR_SYMBOLS = (*DSR_RISK_ASSETS, "BIL")
USCI_SYMBOLS = ("USCI",)
REQUIRED_SYMBOLS = (
    "BIL",
    "QUAL",
    "SPY",
    "SPLV",
    "USCI",
    "USMV",
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)

RUN_ROOT = ROOT / "evidence" / "paper_demo_observation" / TASK_ID
OBSERVATION_DIR = onboarding.OBSERVATION_DIR
OBSERVATION_YAML = onboarding.OBSERVATION_YAML
COMPONENT_LEDGER = onboarding.COMPONENT_LEDGER
REGISTRY_PATH = onboarding.REGISTRY_PATH
ACTIVE_OBSERVATIONS_PATH = onboarding.ACTIVE_OBSERVATIONS_PATH
ROADMAP_PATH = onboarding.ROADMAP_PATH
QUEUE_PATH = onboarding.QUEUE_PATH
FAMILY_LEDGER_PATH = onboarding.FAMILY_LEDGER_PATH

SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\d1ffaf31-35d4-4940-913d-190c8fbdd957\pasted-text.txt"
)

PRESERVED_OBSERVATION_DIRS = tuple(
    ROOT / "paper_forward_observations" / observation_id
    for observation_id in (
        VM_ID,
        DSR_ID,
        USCI_ID,
        REFERENCE_OBSERVATION_ID,
        "paper_demo_faa_4m_top3_v1",
    )
)

PROTECTED_PATHS = (
    ROOT / "data" / "cache",
    onboarding.EXPLORATION_DIR,
    onboarding.FOLLOWUP_DIR,
    onboarding.ROBUSTNESS_DIR,
    onboarding.DESIGN_DIR,
    onboarding.ACTIVATION_DIR,
    onboarding.REPAIR_DIR,
    onboarding.FAA_ONBOARDING_DIR,
    onboarding.FAA_ACTIVE_VALIDATION_DIR,
    *PRESERVED_OBSERVATION_DIRS,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
)

PENDING_REASONS = (
    "reference_current_state_unavailable",
    "psar_current_state_unavailable",
    "required_standard_market_data_unavailable",
    "data_or_comparability_failure",
)

REQUIRED_TOP_LEVEL_OUTPUTS = {
    "recording_manifest.yaml",
    "observation_state_before_after.csv",
    "offline_gate_results.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "normalized_data_manifest.csv",
    "required_session_coverage.csv",
    "reference_component_current_states.csv",
    "reference_combined_current_target.csv",
    "psar_current_state.csv",
    "combined_target_reconciliation.csv",
    "target_freeze_record.csv",
    "virtual_initialization_record.csv",
    "execution_event_ledger.csv",
    "new_performance_rows.csv",
    "virtual_holdings_after.csv",
    "turnover_cost_reconciliation.csv",
    "missing_data_and_deviation_events.csv",
    "state_change_manifest.csv",
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


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_bytes(payload.encode("utf-8"))


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return value


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


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def run_id(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def latest_run_dir() -> Path | None:
    if not RUN_ROOT.exists():
        return None
    candidates = sorted(path for path in RUN_ROOT.iterdir() if path.is_dir())
    return candidates[-1] if candidates else None


def registry_payload() -> dict[str, Any]:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def active_payload() -> dict[str, Any]:
    return yaml.safe_load(ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")) or {}


def sanitize_error(exc: BaseException) -> str:
    value = str(exc).replace("\r", " ").replace("\n", " ")
    for token in (
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_SECRET_KEY",
    ):
        value = value.replace(token, token + "_REDACTED")
    return value[:500]


def latest_fully_completed_session(now: datetime) -> date:
    now_et = now.astimezone(repair.prior_activation.EASTERN)
    cursor = now_et.date()
    if not repair.prior_activation.is_regular_session(cursor) or now_et.time() < time(16, 0):
        cursor -= timedelta(days=1)
    while not repair.prior_activation.is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def next_initialization_close(now: datetime, state_date: date) -> date:
    now_et = now.astimezone(repair.prior_activation.EASTERN)
    if (
        repair.prior_activation.is_regular_session(now_et.date())
        and now_et.time() < time(16, 0)
        and state_date == repair.prior_activation.previous_regular_session(now_et.date())
    ):
        return now_et.date()
    candidate = repair.prior_activation.next_regular_session(state_date)
    close = datetime.combine(
        candidate,
        time(16, 0),
        tzinfo=repair.prior_activation.EASTERN,
    )
    if now_et >= close:
        candidate = repair.prior_activation.next_regular_session(now_et.date())
    return candidate


def sma(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    subset = series.loc[:signal_date].dropna().tail(window)
    if len(subset) < window:
        return float("nan")
    return float(subset.mean())


def trailing_return(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    subset = series.loc[:signal_date].dropna()
    if len(subset) <= window:
        return float("nan")
    return float(subset.iloc[-1] / subset.iloc[-window - 1] - 1.0)


def realized_vol(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    returns = series.loc[:signal_date].pct_change().dropna().tail(window)
    if len(returns) < window:
        return float("nan")
    return float(returns.std())


def close_frame(frames: dict[str, pd.DataFrame], symbols: Iterable[str]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        frame = frames[symbol]
        values = pd.Series(
            frame["close"].to_numpy(dtype=float),
            index=pd.to_datetime(frame["date"]),
            name=symbol,
        )
        series.append(values)
    return pd.concat(series, axis=1).sort_index()


def derive_vm_target(
    frames: dict[str, pd.DataFrame], signal_date: pd.Timestamp
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    prices = close_frame(frames, VM_SYMBOLS)
    rows: list[dict[str, Any]] = []
    scored: list[tuple[str, float]] = []
    for symbol in VM_RISK_ASSETS:
        series = prices[symbol]
        latest_close = float(series.loc[signal_date])
        average = sma(series, signal_date, 200)
        return_126 = trailing_return(series, signal_date, 126)
        vol_60 = realized_vol(series, signal_date, 60)
        eligible = bool(np.isfinite(average) and latest_close > average)
        score = (
            return_126 / vol_60
            if eligible and np.isfinite(return_126) and np.isfinite(vol_60) and vol_60 > 0
            else float("nan")
        )
        if np.isfinite(score):
            scored.append((symbol, score))
        rows.append(
            {
                "component_id": VM_ID,
                "symbol": symbol,
                "signal_date": signal_date.date().isoformat(),
                "close": latest_close,
                "sma200": average,
                "close_above_sma200": eligible,
                "return_126d": return_126,
                "realized_vol_60d": vol_60,
                "score": score,
                "selected": False,
                "target_weight": 0.0,
                "state_role": "current_state_initialization_not_observation_performance",
            }
        )
    selected = [symbol for symbol, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:2]]
    if len(selected) == 2:
        target = {selected[0]: 0.5, selected[1]: 0.5}
    elif len(selected) == 1:
        target = {selected[0]: 1.0}
    else:
        target = {"BIL": 1.0}
    for row in rows:
        row["selected"] = row["symbol"] in target
        row["target_weight"] = target.get(row["symbol"], 0.0)
    if "BIL" in target:
        rows.append(
            {
                "component_id": VM_ID,
                "symbol": "BIL",
                "signal_date": signal_date.date().isoformat(),
                "close": float(prices.loc[signal_date, "BIL"]),
                "selected": True,
                "target_weight": target["BIL"],
                "state_role": "current_state_initialization_not_observation_performance",
            }
        )
    return target, rows


def derive_dsr_target(
    frames: dict[str, pd.DataFrame], signal_date: pd.Timestamp
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    prices = close_frame(frames, DSR_SYMBOLS)
    rows: list[dict[str, Any]] = []
    qualifying: list[str] = []
    for symbol in DSR_RISK_ASSETS:
        series = prices[symbol]
        latest_close = float(series.loc[signal_date])
        average = sma(series, signal_date, 200)
        eligible = bool(np.isfinite(average) and latest_close > average)
        if eligible:
            qualifying.append(symbol)
        rows.append(
            {
                "component_id": DSR_ID,
                "symbol": symbol,
                "signal_date": signal_date.date().isoformat(),
                "close": latest_close,
                "sma200": average,
                "close_above_sma200": eligible,
                "qualifying_sector_count": 0,
                "selected": eligible,
                "target_weight": 0.0,
                "state_role": "current_state_initialization_not_observation_performance",
            }
        )
    if len(qualifying) >= 3:
        target = {symbol: 1.0 / len(qualifying) for symbol in qualifying}
    elif qualifying:
        target = {symbol: 1.0 / 3.0 for symbol in qualifying}
        target["BIL"] = 1.0 - len(qualifying) / 3.0
    else:
        target = {"BIL": 1.0}
    for row in rows:
        row["qualifying_sector_count"] = len(qualifying)
        row["target_weight"] = target.get(row["symbol"], 0.0)
    if "BIL" in target:
        rows.append(
            {
                "component_id": DSR_ID,
                "symbol": "BIL",
                "signal_date": signal_date.date().isoformat(),
                "close": float(prices.loc[signal_date, "BIL"]),
                "qualifying_sector_count": len(qualifying),
                "selected": True,
                "target_weight": target["BIL"],
                "state_role": "current_state_initialization_not_observation_performance",
            }
        )
    return target, rows


def reference_current_target(
    frames: dict[str, pd.DataFrame], signal_date: pd.Timestamp
) -> tuple[dict[str, float], list[dict[str, Any]], dict[str, dict[str, float]]]:
    vm_target, vm_rows = derive_vm_target(frames, signal_date)
    dsr_target, dsr_rows = derive_dsr_target(frames, signal_date)
    usci_target = {"USCI": 1.0}
    usci_rows = [
        {
            "component_id": USCI_ID,
            "symbol": "USCI",
            "signal_date": signal_date.date().isoformat(),
            "close": float(close_frame(frames, USCI_SYMBOLS).loc[signal_date, "USCI"]),
            "selected": True,
            "target_weight": 1.0,
            "state_role": "current_state_initialization_not_observation_performance",
        }
    ]
    component_targets = {VM_ID: vm_target, DSR_ID: dsr_target, USCI_ID: usci_target}
    combined: dict[str, float] = {}
    for target in component_targets.values():
        for symbol, weight in target.items():
            combined[symbol] = combined.get(symbol, 0.0) + float(weight) / 3.0
    if not math.isclose(sum(combined.values()), 1.0, abs_tol=1e-12):
        raise ValueError("current frozen reference target does not sum to one")
    return combined, vm_rows + dsr_rows + usci_rows, component_targets


def psar_current_state(frames: dict[str, pd.DataFrame], signal_date: date) -> dict[str, Any]:
    spy = frames["SPY"]
    normalized = pd.DataFrame(
        {
            "trading_date": pd.to_datetime(spy["date"]),
            "adjusted_high": pd.to_numeric(spy["high"]),
            "adjusted_low": pd.to_numeric(spy["low"]),
            "adjusted_close": pd.to_numeric(spy["close"]),
        }
    )
    state, _path = repair.prior_activation.psar_state(normalized, signal_date, True)
    return {
        "strategy_id": STRATEGY_ID,
        "signal_date": state["last_completed_signal_date"],
        "PSAR": state["PSAR"],
        "AF": state["AF"],
        "extreme_point": state["EP"],
        "trend_state": state["trend_state"],
        "change3": state["change3"],
        "target": state["target"],
        "state_before_latest_calculation": state["state_before_latest_calculation"],
        "state_role": "current_state_initialization_not_observation_performance",
        "provider": "alpaca_market_data",
        "adjustment": "all",
        "source_hash": canonical_hash(
            spy.loc[spy["date"] <= signal_date.isoformat()].to_dict(orient="records")
        ),
    }


def aggregate_target(
    reference_target: dict[str, float], psar_target: dict[str, float]
) -> dict[str, float]:
    symbols = sorted(set(reference_target) | set(psar_target) | {"SPY", "BIL"})
    target = {
        symbol: REFERENCE_WEIGHT * reference_target.get(symbol, 0.0)
        + PSAR_WEIGHT * psar_target.get(symbol, 0.0)
        for symbol in symbols
    }
    if not all(value >= -1e-15 for value in target.values()):
        raise ValueError("combined target contains a negative weight")
    if not math.isclose(sum(target.values()), 1.0, abs_tol=1e-12):
        raise ValueError("combined target does not sum to one")
    if sum(abs(value) for value in target.values()) > 1.0 + 1e-12:
        raise ValueError("combined target exceeds unit gross exposure")
    return target


def virtual_initialization_fixture() -> dict[str, Any]:
    reference = {"SPY": 0.5, "BIL": 0.5}
    sleeve = {"SPY": 1.0, "BIL": 0.0}
    target = aggregate_target(reference, sleeve)
    capital = 3000.0
    turnover = 1.0
    cost = capital * turnover * PRIMARY_COST_BPS / 10000.0
    post_cost = capital - cost
    prices = {"SPY": 100.0, "BIL": 50.0}
    holdings = {symbol: post_cost * weight for symbol, weight in target.items()}
    shares = {symbol: holdings[symbol] / prices[symbol] for symbol in target}
    return {
        "target": target,
        "turnover": turnover,
        "cost": cost,
        "post_cost_equity": post_cost,
        "holdings": holdings,
        "shares": shares,
        "cash": 0.0,
        "cost_charged_once": True,
        "weight_sum_pass": math.isclose(sum(target.values()), 1.0, abs_tol=1e-12),
        "equity_pass": math.isclose(sum(holdings.values()), post_cost, abs_tol=1e-12),
        "performance_rows": 0,
        "broker_calls": 0,
        "orders_created": 0,
    }


def offline_gate() -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    observation = read_yaml(OBSERVATION_YAML)
    registry = registry_payload()
    active = active_payload()
    ledger_rows = read_csv(COMPONENT_LEDGER)
    with COMPONENT_LEDGER.open("r", encoding="utf-8-sig", newline="") as handle:
        ledger_fields = tuple(next(csv.reader(handle)))
    strategy_rows = [
        row for row in registry.get("strategies", [])
        if row.get("strategy_id") == STRATEGY_ID
    ]
    observation_rows = [
        row for row in active.get("active_observations", [])
        if row.get("observation_id") == OBSERVATION_ID
    ]
    component_imports = all(
        read_yaml(ROOT / "paper_forward_observations" / item / "active_observation.yaml")
        for item in (VM_ID, DSR_ID, USCI_ID, REFERENCE_OBSERVATION_ID)
    )
    fixture = virtual_initialization_fixture()
    pending_initialization = (
        observation.get("initialization_status") == "pending_first_valid_signal_or_execution"
        and observation.get("current_target_allocation") == {}
        and observation.get("scheduled_first_execution_date") == ""
    )
    recorder_scheduled_initialization = (
        observation.get("initialization_status") == "scheduled_for_first_prospective_execution"
        and observation.get("current_target_allocation") == {}
        and bool(observation.get("scheduled_target_allocation"))
        and bool(observation.get("scheduled_first_execution_date"))
        and observation.get("target_freeze_event_label") == "standard_observation_current_target_initialization"
    )
    checks = (
        ("PSAR_observation_identity", observation.get("observation_id") == OBSERVATION_ID),
        ("PSAR_paper_demo_eligibility", len(strategy_rows) == 1 and strategy_rows[0].get("eligibility") == "paper_demo_eligible"),
        ("admitted_initialization_status", pending_initialization or recorder_scheduled_initialization),
        ("no_completed_virtual_execution", observation.get("current_target_allocation") == {}),
        ("standard_ledger_empty", len(ledger_rows) == 0),
        ("observation_not_duplicated", len(observation_rows) == 1),
        ("component_definitions_import", component_imports),
        ("standard_target_schema", "combined_target_weights" in ledger_fields),
        ("standard_virtual_position_schema", all(field in ledger_fields for field in ("holdings", "shares", "cash"))),
        ("standard_virtual_equity_schema", "post_cost_equity" in ledger_fields),
        ("standard_execution_event_schema", all(field in ledger_fields for field in ("intended_execution_date", "completed_execution_date", "status"))),
        ("standard_turnover_cost_schema", all(field in ledger_fields for field in ("inner_turnover", "outer_turnover", "total_turnover", "transaction_cost"))),
        ("standard_missing_data_schema", all(field in ledger_fields for field in ("missing_data_events", "blocked_execution_reason", "rule_deviations"))),
        ("offline_fixture_complete", fixture["weight_sum_pass"] and fixture["equity_pass"] and fixture["performance_rows"] == 0),
        ("offline_fixture_no_orders", fixture["broker_calls"] == 0 and fixture["orders_created"] == 0),
    )
    rows = [
        {
            "check_order": index,
            "check_id": check_id,
            "status": "pass" if passed else "fail",
            "provider_access_required": False,
        }
        for index, (check_id, passed) in enumerate(checks, start=1)
    ]
    return rows, all(passed for _check, passed in checks), fixture


def frozen_target_waiting_for_execution(
    observation: dict[str, Any], latest_completed: date
) -> bool:
    if observation.get("initialization_status") != "scheduled_for_first_prospective_execution":
        return False
    if observation.get("target_freeze_event_label") != "standard_observation_current_target_initialization":
        return False
    scheduled_text = str(observation.get("scheduled_first_execution_date", ""))
    try:
        scheduled = date.fromisoformat(scheduled_text)
    except ValueError:
        return False
    return (
        bool(observation.get("scheduled_target_allocation"))
        and observation.get("current_target_allocation") == {}
        and latest_completed < scheduled
    )


def retrieve_alpaca(
    output_dir: Path,
    symbols: tuple[str, ...],
    start: date,
    end_exclusive: date,
) -> dict[str, Any]:
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    attempt = {
        "provider": "alpaca_market_data",
        "provider_role": "existing_standard_read_only_paper_demo_data_path",
        "attempted": True,
        "bounded_cycles": 1,
        "symbols": list(symbols),
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "timeframe": "1Day",
        "feed": "iex",
        "adjustment": "all",
        "credentials_present": False,
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
    raw_rows: list[dict[str, Any]] = []
    normalized_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    try:
        credentials = load_alpaca_credentials("paper")
        attempt["credentials_present"] = bool(credentials.present)
        attempt["live_credentials_detected"] = bool(credentials.live_credentials_detected)
        if not credentials.present or credentials.live_credentials_detected:
            attempt["status"] = "auth_or_environment_not_admitted"
            attempt["error"] = "approved non-live paper market-data credentials unavailable"
            return {
                "attempt": attempt,
                "raw_rows": raw_rows,
                "normalized_rows": normalized_rows,
                "coverage_rows": coverage_rows,
                "frames": frames,
                "success": False,
            }
        client = AlpacaClient(
            credentials,
            AlpacaClientConfig(data_feed="iex", data_adjustment="all"),
        )
        merged: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
        page_token: str | None = None
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(symbols),
                start=f"{start.isoformat()}T00:00:00Z",
                end=f"{end_exclusive.isoformat()}T00:00:00Z",
                timeframe="1Day",
                feed="iex",
                adjustment="all",
                page_token=page_token,
            )
            attempt["page_count"] += 1
            page_path = raw_dir / f"page_{attempt['page_count']:04d}.json"
            write_json(page_path, payload)
            page_rows = sum(len(value) for value in payload.get("bars", {}).values())
            raw_rows.append(
                {
                    "page_number": attempt["page_count"],
                    "path": relative(page_path),
                    "hash": file_hash(page_path),
                    "row_count": page_rows,
                    "retrieval_timestamp_utc": retrieval_timestamp,
                    "persisted_before_strategy_calculation": True,
                }
            )
            for symbol in symbols:
                merged["bars"][symbol].extend(payload.get("bars", {}).get(symbol, []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
            if attempt["page_count"] >= 100:
                raise RuntimeError("bounded pagination limit exceeded")
        frames = parse_bars_response(merged, drop_incomplete_current_day=False)
        normalized_dir = output_dir / "normalized"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for symbol in symbols:
            frame = frames.get(symbol, pd.DataFrame()).copy()
            if not frame.empty:
                frame = frame[["date", "timestamp", "open", "high", "low", "close", "volume"]]
                frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
            normalized_path = normalized_dir / f"{symbol}.csv"
            frame.to_csv(normalized_path, index=False, lineterminator="\n")
            frames[symbol] = frame
            ordered = bool(frame.empty or pd.Series(frame["date"]).is_monotonic_increasing)
            unique = bool(frame.empty or not frame["date"].duplicated().any())
            finite_positive = bool(
                not frame.empty
                and np.isfinite(frame[["open", "high", "low", "close"]].to_numpy(dtype=float)).all()
                and (frame[["open", "high", "low", "close"]] > 0).all().all()
            )
            ohlc_valid = bool(
                not frame.empty
                and (frame["high"] >= frame[["open", "low", "close"]].max(axis=1)).all()
                and (frame["low"] <= frame[["open", "high", "close"]].min(axis=1)).all()
            )
            normalized_rows.append(
                {
                    "symbol": symbol,
                    "path": relative(normalized_path),
                    "normalized_hash": file_hash(normalized_path),
                    "row_count": len(frame),
                    "first_date": "" if frame.empty else frame.iloc[0]["date"],
                    "last_date": "" if frame.empty else frame.iloc[-1]["date"],
                    "columns": list(frame.columns),
                    "adjustment": "all",
                    "persisted_before_strategy_calculation": True,
                }
            )
            coverage_rows.append(
                {
                    "symbol": symbol,
                    "required_latest_session": (end_exclusive - timedelta(days=1)).isoformat(),
                    "first_date": "" if frame.empty else frame.iloc[0]["date"],
                    "last_date": "" if frame.empty else frame.iloc[-1]["date"],
                    "row_count": len(frame),
                    "ordered_unique_sessions": ordered and unique,
                    "finite_positive_adjusted_OHLC": finite_positive,
                    "valid_OHLC_relationships": ohlc_valid,
                    "latest_session_complete": bool(
                        not frame.empty
                        and frame.iloc[-1]["date"] == (end_exclusive - timedelta(days=1)).isoformat()
                    ),
                }
            )
        attempt["row_count"] = sum(len(frame) for frame in frames.values())
        success = bool(
            len(frames) == len(symbols)
            and all(
                row["ordered_unique_sessions"]
                and row["finite_positive_adjusted_OHLC"]
                and row["valid_OHLC_relationships"]
                and row["latest_session_complete"]
                for row in coverage_rows
            )
            and len(frames["SPY"]) >= 1000
            and all(len(frames[symbol]) >= 201 for symbol in set(VM_SYMBOLS + DSR_SYMBOLS))
        )
        attempt["status"] = "complete_current_adjusted_daily_batch" if success else "incomplete_or_invalid_batch"
        return {
            "attempt": attempt,
            "raw_rows": raw_rows,
            "normalized_rows": normalized_rows,
            "coverage_rows": coverage_rows,
            "frames": frames,
            "success": success,
        }
    except BaseException as exc:  # noqa: BLE001 - bounded provider failures become evidence.
        attempt["status"] = "provider_call_failed"
        attempt["error"] = sanitize_error(exc)
        return {
            "attempt": attempt,
            "raw_rows": raw_rows,
            "normalized_rows": normalized_rows,
            "coverage_rows": coverage_rows,
            "frames": frames,
            "success": False,
        }


def update_yaml_state(
    observation_before: dict[str, Any],
    target: dict[str, float],
    reference_target: dict[str, float],
    psar_state: dict[str, Any],
    freeze_timestamp: str,
    execution_date: date,
    first_performance_date: date,
    normalized_manifest_hash: str,
    run_dir: Path,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(observation_before))
    updated.update(
        {
            "initialization_status": "scheduled_for_first_prospective_execution",
            "current_checkpoint_status": "target_frozen_pending_execution",
            "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
            "target_freeze_timestamp": freeze_timestamp,
            "target_freeze_event_label": "standard_observation_current_target_initialization",
            "initial_partial_observation_interval": True,
            "current_target_allocation": {},
            "scheduled_target_allocation": target,
            "scheduled_reference_target": reference_target,
            "scheduled_psar_sleeve_target": psar_state["target"],
            "scheduled_first_execution_date": execution_date.isoformat(),
            "first_eligible_performance_date": first_performance_date.isoformat(),
            "latest_current_state_date": psar_state["signal_date"],
            "latest_psar_recursive_state": psar_state,
            "target_freeze_hash": canonical_hash(target),
            "normalized_data_manifest_hash": normalized_manifest_hash,
            "historical_backfill": False,
            "historical_performance_rows_imported": 0,
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": relative(run_dir),
            "next_action": NEXT_RECORD,
        }
    )
    return updated


def update_active_and_registry(
    active_before: dict[str, Any],
    registry_before: dict[str, Any],
    freeze_timestamp: str,
    execution_date: date,
    first_performance_date: date,
    run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    active_after = json.loads(json.dumps(active_before))
    matching_active = [
        row for row in active_after.get("active_observations", [])
        if row.get("observation_id") == OBSERVATION_ID
    ]
    if len(matching_active) != 1:
        raise ValueError("PSAR standard observation inventory identity changed")
    matching_active[0].update(
        {
            "initialization_status": "scheduled_for_first_prospective_execution",
            "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
            "target_freeze_timestamp": freeze_timestamp,
            "scheduled_first_execution_date": execution_date.isoformat(),
            "first_eligible_performance_date": first_performance_date.isoformat(),
            "next_action": NEXT_RECORD,
        }
    )
    active_after["latest_psar_standard_paper_demo_recording"] = {
        "created_utc": freeze_timestamp,
        "evidence_path": relative(run_dir),
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "outcome": OUTCOME_TARGET_FROZEN,
        "initialization_status": "scheduled_for_first_prospective_execution",
        "scheduled_first_execution_date": execution_date.isoformat(),
        "first_eligible_performance_date": first_performance_date.isoformat(),
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "real_money_authorization": False,
        "next_action": NEXT_RECORD,
    }

    registry_after = json.loads(json.dumps(registry_before))
    matching_registry = [
        row for row in registry_after.get("strategies", [])
        if row.get("strategy_id") == STRATEGY_ID
    ]
    if len(matching_registry) != 1:
        raise ValueError("PSAR lifecycle identity changed")
    matching_registry[0].update(
        {
            "initialization_status": "scheduled_for_first_prospective_execution",
            "latest_operational_update_utc": freeze_timestamp,
            "latest_evidence_path": relative(run_dir),
            "next_action": NEXT_RECORD,
            "allowed_next_action": NEXT_RECORD,
        }
    )
    return active_after, registry_after


def recording_report(manifest: dict[str, Any]) -> str:
    if manifest["outcome"] == OUTCOME_TARGET_FROZEN:
        detail = (
            f"A fresh current target was calculated through {manifest['state_date']} and frozen "
            f"before the {manifest['scheduled_execution_date']} regular-session close. No position "
            "or performance row was created."
        )
    elif manifest["outcome"] == OUTCOME_PENDING:
        detail = "The bounded standard-data cycle did not produce a complete current target. The observation remains pending."
    else:
        detail = "The local standard-framework gate blocked recording before provider use."
    return f"""# PSAR Standard Paper/Demo Observation Recording

## Outcome

**`{manifest['outcome']}`**

{detail}

The existing observation and frozen 80% reference / 20% Decelerated PSAR route
remain unchanged. The initialization convention is labeled
`standard_observation_current_target_initialization`; it is not the expired June
signal execution and creates no historical return. The first partial interval is
separate from a complete monthly outer-rebalance interval.

No validation trial, strategy, observation, broker call, or order was created.

Exact next action: `{manifest['next_action']}`.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    started = started.astimezone(timezone.utc)
    output_dir = RUN_ROOT / run_id(started)
    output_dir.mkdir(parents=True, exist_ok=False)

    protected_before = map_hashes(PROTECTED_PATHS)
    source_hash_before = file_hash(SOURCE_PACKET)
    observation_before = read_yaml(OBSERVATION_YAML)
    active_before = active_payload()
    registry_before = registry_payload()
    unrelated_active_before = [
        row for row in active_before.get("active_observations", [])
        if row.get("observation_id") != OBSERVATION_ID
    ]
    unrelated_registry_before = [
        row for row in registry_before.get("strategies", [])
        if row.get("strategy_id") != STRATEGY_ID
    ]
    offline_rows, offline_pass, fixture = offline_gate()

    latest_completed = latest_fully_completed_session(started)
    provider: dict[str, Any] = {
        "attempt": {
            "provider": "alpaca_market_data",
            "attempted": False,
            "status": "not_attempted_offline_gate_failed",
            "broker_calls": 0,
            "orders_created": 0,
        },
        "raw_rows": [],
        "normalized_rows": [],
        "coverage_rows": [],
        "frames": {},
        "success": False,
    }
    reference_rows: list[dict[str, Any]] = []
    reference_target_rows: list[dict[str, Any]] = []
    psar_rows: list[dict[str, Any]] = []
    combined_rows: list[dict[str, Any]] = []
    freeze_rows: list[dict[str, Any]] = []
    initialization_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    holdings_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    observation_after = observation_before
    active_after = active_before
    registry_after = registry_before
    target: dict[str, float] = {}
    reference_target: dict[str, float] = {}
    psar_state: dict[str, Any] = {}
    execution_date: date | None = None
    first_performance_date: date | None = None
    freeze_timestamp = ""
    failure_reason = ""

    if not offline_pass:
        outcome = OUTCOME_BLOCKED
        failure_reason = "local_methodology_failure"
        next_action = NEXT_BLOCKED
    elif frozen_target_waiting_for_execution(observation_before, latest_completed):
        outcome = OUTCOME_NO_NEW_SESSION
        next_action = NEXT_RECORD
        target = {
            str(symbol): float(weight)
            for symbol, weight in observation_before["scheduled_target_allocation"].items()
        }
        reference_target = {
            str(symbol): float(weight)
            for symbol, weight in observation_before.get("scheduled_reference_target", {}).items()
        }
        psar_state = dict(observation_before.get("latest_psar_recursive_state", {}))
        freeze_timestamp = str(observation_before.get("target_freeze_timestamp", ""))
        execution_date = date.fromisoformat(observation_before["scheduled_first_execution_date"])
        first_performance_date = date.fromisoformat(observation_before["first_eligible_performance_date"])
        holdings_rows = [
            {
                "observation_id": OBSERVATION_ID,
                "as_of": started.isoformat(),
                "symbol": "CASH",
                "market_value": observation_before["pre_execution_virtual_cash"],
                "shares": "",
                "weight": 1.0,
                "status": "unchanged_pre_execution_cash_no_new_completed_session",
            }
        ]
        turnover_rows = [
            {
                "observation_id": OBSERVATION_ID,
                "event_status": "existing_target_pending_execution_no_new_session",
                "inner_turnover": "pending_execution_measurement",
                "outer_turnover": "pending_execution_measurement",
                "initialization_turnover": 1.0,
                "actual_cost_deducted": 0.0,
                "primary_cost_bps": PRIMARY_COST_BPS,
                "projected_initialization_cost": (
                    float(observation_before["initial_virtual_capital"])
                    * PRIMARY_COST_BPS
                    / 10000.0
                ),
                "cost_charged_once": True,
            }
        ]
    else:
        provider = retrieve_alpaca(
            output_dir,
            REQUIRED_SYMBOLS,
            date(2007, 1, 3),
            latest_completed + timedelta(days=1),
        )
        if not provider["success"]:
            outcome = OUTCOME_PENDING
            failure_reason = "required_standard_market_data_unavailable"
            next_action = NEXT_PENDING
            event_rows.append(
                {
                    "event_timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "missing_data_or_reconciliation_event",
                    "status": "pending",
                    "failure_reason": failure_reason,
                    "detail": provider["attempt"].get("status", ""),
                    "virtual_position_created": False,
                    "performance_row_created": False,
                }
            )
        else:
            frames = provider["frames"]
            signal_date = pd.Timestamp(latest_completed)
            try:
                reference_target, reference_rows, component_targets = reference_current_target(
                    frames, signal_date
                )
                psar_state = psar_current_state(frames, latest_completed)
                target = aggregate_target(reference_target, psar_state["target"])
                freeze_now = datetime.now(timezone.utc)
                freeze_timestamp = freeze_now.isoformat()
                if latest_fully_completed_session(freeze_now) != latest_completed:
                    raise RuntimeError("latest completed session changed during bounded retrieval")
                execution_date = next_initialization_close(freeze_now, latest_completed)
                first_performance_date = repair.prior_activation.next_regular_session(execution_date)
                normalized_manifest_hash = canonical_hash(provider["normalized_rows"])
                observation_after = update_yaml_state(
                    observation_before,
                    target,
                    reference_target,
                    psar_state,
                    freeze_timestamp,
                    execution_date,
                    first_performance_date,
                    normalized_manifest_hash,
                    output_dir,
                )
                active_after, registry_after = update_active_and_registry(
                    active_before,
                    registry_before,
                    freeze_timestamp,
                    execution_date,
                    first_performance_date,
                    output_dir,
                )
                write_yaml(OBSERVATION_YAML, observation_after)
                atomic_write_text(
                    ACTIVE_OBSERVATIONS_PATH,
                    yaml.safe_dump(active_after, sort_keys=False, width=110, allow_unicode=False),
                )
                atomic_write_text(
                    REGISTRY_PATH,
                    yaml.safe_dump(registry_after, sort_keys=False, width=110, allow_unicode=False),
                )
                outcome = OUTCOME_TARGET_FROZEN
                next_action = NEXT_RECORD
                for component_id, component_target in component_targets.items():
                    for symbol, weight in component_target.items():
                        reference_target_rows.append(
                            {
                                "component_id": component_id,
                                "symbol": symbol,
                                "component_target_weight": weight,
                                "reference_component_weight": 1.0 / 3.0,
                                "combined_reference_weight": float(weight) / 3.0,
                                "signal_date": latest_completed.isoformat(),
                                "current": True,
                            }
                        )
                psar_rows = [psar_state]
                for symbol in sorted(target):
                    combined_rows.append(
                        {
                            "symbol": symbol,
                            "reference_target_weight": reference_target.get(symbol, 0.0),
                            "scaled_reference_weight": REFERENCE_WEIGHT * reference_target.get(symbol, 0.0),
                            "psar_sleeve_target_weight": psar_state["target"].get(symbol, 0.0),
                            "scaled_psar_sleeve_weight": PSAR_WEIGHT * psar_state["target"].get(symbol, 0.0),
                            "combined_target_weight": target[symbol],
                            "nonnegative": target[symbol] >= 0,
                            "target_frozen": True,
                        }
                    )
                freeze_rows = [
                    {
                        "observation_id": OBSERVATION_ID,
                        "event_label": "standard_observation_current_target_initialization",
                        "state_date": latest_completed.isoformat(),
                        "freeze_timestamp": freeze_timestamp,
                        "scheduled_execution_date": execution_date.isoformat(),
                        "first_eligible_performance_date": first_performance_date.isoformat(),
                        "combined_target": target,
                        "target_hash": canonical_hash(target),
                        "initial_partial_observation_interval": True,
                        "original_signal_execution_claimed": False,
                        "historical_backfill": False,
                    }
                ]
                execution_rows = [
                    {
                        "observation_id": OBSERVATION_ID,
                        "event_type": "scheduled_virtual_initialization",
                        "event_label": "standard_observation_current_target_initialization",
                        "target_freeze_timestamp": freeze_timestamp,
                        "intended_execution_date": execution_date.isoformat(),
                        "completed_execution_date": "",
                        "status": "target_frozen_pending_execution",
                        "actual_execution_event": False,
                        "positions_created": False,
                        "performance_row_created": False,
                        "broker_calls": 0,
                        "orders_created": 0,
                    }
                ]
                holdings_rows = [
                    {
                        "observation_id": OBSERVATION_ID,
                        "as_of": freeze_timestamp,
                        "symbol": "CASH",
                        "market_value": observation_before["pre_execution_virtual_cash"],
                        "shares": "",
                        "weight": 1.0,
                        "status": "unchanged_pre_execution_cash",
                    }
                ]
                projected_turnover = 1.0
                projected_cost = (
                    float(observation_before["initial_virtual_capital"])
                    * projected_turnover
                    * PRIMARY_COST_BPS
                    / 10000.0
                )
                turnover_rows = [
                    {
                        "observation_id": OBSERVATION_ID,
                        "event_status": "projected_pending_execution",
                        "inner_turnover": "pending_execution_measurement",
                        "outer_turnover": "pending_execution_measurement",
                        "initialization_turnover": projected_turnover,
                        "primary_cost_bps": PRIMARY_COST_BPS,
                        "projected_initialization_cost": projected_cost,
                        "actual_cost_deducted": 0.0,
                        "cost_charged_once": True,
                    }
                ]
            except BaseException as exc:  # noqa: BLE001 - methodology/data failures remain operational evidence.
                outcome = OUTCOME_PENDING
                failure_reason = (
                    "psar_current_state_unavailable"
                    if "PSAR" in str(exc) or "psar" in str(exc).lower()
                    else "data_or_comparability_failure"
                )
                next_action = NEXT_PENDING
                event_rows.append(
                    {
                        "event_timestamp": datetime.now(timezone.utc).isoformat(),
                        "event_type": "state_reconciliation_event",
                        "status": "pending",
                        "failure_reason": failure_reason,
                        "detail": sanitize_error(exc),
                        "virtual_position_created": False,
                        "performance_row_created": False,
                    }
                )

    protected_after = map_hashes(PROTECTED_PATHS)
    source_hash_after = file_hash(SOURCE_PACKET)
    active_final = active_payload()
    registry_final = registry_payload()
    unrelated_active_after = [
        row for row in active_final.get("active_observations", [])
        if row.get("observation_id") != OBSERVATION_ID
    ]
    unrelated_registry_after = [
        row for row in registry_final.get("strategies", [])
        if row.get("strategy_id") != STRATEGY_ID
    ]

    manifest = {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "mode": MODE,
        "stage": STAGE,
        "started_utc": started.isoformat(),
        "latest_fully_completed_session": latest_completed.isoformat(),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "state_date": psar_state.get("signal_date", ""),
        "scheduled_execution_date": execution_date.isoformat() if execution_date else "",
        "first_eligible_performance_date": first_performance_date.isoformat() if first_performance_date else "",
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_paper_demo_observations": 0,
        "existing_paper_demo_observations_updated": 1 if outcome == OUTCOME_TARGET_FROZEN else 0,
        "validation_observations": 0,
        "process_tasks": 1,
        "data_capability_tasks": 1 if provider["attempt"].get("attempted") else 0,
        "execution_events": 0,
        "scheduled_execution_events": len(execution_rows),
        "performance_rows": len(performance_rows),
        "broker_or_paper_orders": 0,
        "next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml(output_dir / "recording_manifest.yaml", manifest)
    write_csv(
        output_dir / "observation_state_before_after.csv",
        [
            {
                "observation_id": OBSERVATION_ID,
                "before_status": observation_before.get("status", ""),
                "before_initialization_status": observation_before.get("initialization_status", ""),
                "before_performance_rows": len(read_csv(COMPONENT_LEDGER)),
                "after_status": observation_after.get("status", ""),
                "after_initialization_status": observation_after.get("initialization_status", ""),
                "after_performance_rows": len(read_csv(COMPONENT_LEDGER)),
                "historical_backfill": False,
            }
        ],
        ["observation_id", "before_status", "before_initialization_status", "after_status", "after_initialization_status"],
    )
    write_csv(output_dir / "offline_gate_results.csv", offline_rows, ["check_order", "check_id", "status"])
    write_csv(output_dir / "provider_attempt_log.csv", [provider["attempt"]], ["provider", "attempted", "bounded_cycles", "status"])
    write_csv(output_dir / "raw_retrieval_manifest.csv", provider["raw_rows"], ["page_number", "path", "hash", "row_count"])
    write_csv(output_dir / "normalized_data_manifest.csv", provider["normalized_rows"], ["symbol", "path", "normalized_hash", "row_count"])
    write_csv(output_dir / "required_session_coverage.csv", provider["coverage_rows"], ["symbol", "required_latest_session", "first_date", "last_date", "row_count"])
    write_csv(output_dir / "reference_component_current_states.csv", reference_rows, ["component_id", "symbol", "signal_date", "target_weight"])
    write_csv(output_dir / "reference_combined_current_target.csv", reference_target_rows, ["component_id", "symbol", "component_target_weight", "combined_reference_weight"])
    write_csv(output_dir / "psar_current_state.csv", psar_rows, ["strategy_id", "signal_date", "PSAR", "AF", "extreme_point", "trend_state", "change3"])
    write_csv(output_dir / "combined_target_reconciliation.csv", combined_rows, ["symbol", "reference_target_weight", "scaled_reference_weight", "psar_sleeve_target_weight", "scaled_psar_sleeve_weight", "combined_target_weight"])
    write_csv(output_dir / "target_freeze_record.csv", freeze_rows, ["observation_id", "event_label", "state_date", "freeze_timestamp", "scheduled_execution_date"])
    write_csv(output_dir / "virtual_initialization_record.csv", initialization_rows, ["observation_id", "execution_date", "post_cost_equity"])
    write_csv(output_dir / "execution_event_ledger.csv", execution_rows, ["observation_id", "event_type", "event_label", "intended_execution_date", "completed_execution_date", "status"])
    write_csv(output_dir / "new_performance_rows.csv", performance_rows, ["observation_id", "date", "pre_cost_return", "post_cost_return", "post_cost_equity"])
    write_csv(output_dir / "virtual_holdings_after.csv", holdings_rows, ["observation_id", "as_of", "symbol", "market_value", "shares", "weight", "status"])
    write_csv(output_dir / "turnover_cost_reconciliation.csv", turnover_rows, ["observation_id", "event_status", "inner_turnover", "outer_turnover", "initialization_turnover", "actual_cost_deducted"])
    write_csv(output_dir / "missing_data_and_deviation_events.csv", event_rows, ["event_timestamp", "event_type", "status", "failure_reason", "detail"])

    state_rows = [
        {
            "scope": "PSAR_standard_observation",
            "path": relative(OBSERVATION_YAML),
            "change": "target_frozen_pending_execution" if outcome == OUTCOME_TARGET_FROZEN else "none",
            "authorized": outcome == OUTCOME_TARGET_FROZEN,
        },
        {
            "scope": "PSAR_active_inventory_state",
            "path": relative(ACTIVE_OBSERVATIONS_PATH),
            "change": "initialization_status_and_schedule_only" if outcome == OUTCOME_TARGET_FROZEN else "none",
            "authorized": outcome == OUTCOME_TARGET_FROZEN,
        },
        {
            "scope": "PSAR_registry_observation_state",
            "path": relative(REGISTRY_PATH),
            "change": "initialization_status_and_evidence_pointer_only" if outcome == OUTCOME_TARGET_FROZEN else "none",
            "authorized": outcome == OUTCOME_TARGET_FROZEN,
        },
    ]
    for path in PROTECTED_PATHS:
        state_rows.append(
            {
                "scope": "protected_state_or_evidence",
                "path": relative(path),
                "before_hash": protected_before[relative(path)],
                "after_hash": protected_after[relative(path)],
                "unchanged": protected_before[relative(path)] == protected_after[relative(path)],
                "change": "none",
                "authorized": False,
            }
        )
    write_csv(output_dir / "state_change_manifest.csv", state_rows, ["scope", "path", "change", "authorized"])
    write_csv(
        output_dir / "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "run_id": output_dir.name,
                "strategy_id": STRATEGY_ID,
                "observation_id": OBSERVATION_ID,
                "outcome": outcome,
                "failure_reason": failure_reason,
                "initialization_status": observation_after.get("initialization_status", ""),
                "state_date": psar_state.get("signal_date", ""),
                "scheduled_execution_date": execution_date.isoformat() if execution_date else "",
                "performance_rows_created": len(performance_rows),
                "broker_or_paper_orders": 0,
                "next_action": next_action,
            }
        ],
        ["task_id", "run_id", "strategy_id", "observation_id", "outcome", "failure_reason", "next_action"],
    )
    failure_rows = [
        {"outcome_scope": OUTCOME_BLOCKED, "failure_reason": "local_methodology_failure", "selected": failure_reason == "local_methodology_failure"}
    ] + [
        {"outcome_scope": OUTCOME_PENDING, "failure_reason": reason, "selected": failure_reason == reason}
        for reason in PENDING_REASONS
    ]
    write_csv(output_dir / "failure_reasons.csv", failure_rows, ["outcome_scope", "failure_reason", "selected"])
    next_action_rows = [
        {"outcome": item, "next_action": action, "selected": outcome == item, "executed": False}
        for item, action in (
            (OUTCOME_TARGET_FROZEN, NEXT_RECORD),
            (OUTCOME_INITIALIZED, NEXT_RECORD),
            (OUTCOME_UPDATED, NEXT_RECORD),
            (OUTCOME_NO_NEW_SESSION, NEXT_RECORD),
            (OUTCOME_PENDING, NEXT_PENDING),
            (OUTCOME_BLOCKED, NEXT_BLOCKED),
        )
    ]
    write_csv(output_dir / "next_actions.csv", next_action_rows, ["outcome", "next_action", "selected", "executed"])
    (output_dir / "recording_report.md").write_text(recording_report(manifest), encoding="utf-8")

    top_level_before_consistency = {path.name for path in output_dir.iterdir() if path.is_file()}
    expected_before_consistency = REQUIRED_TOP_LEVEL_OUTPUTS - {"consistency_check.json"}
    required_checks = {
        "offline_gate_pass": offline_pass,
        "single_bounded_provider_cycle": provider["attempt"].get("bounded_cycles") in (None, 1),
        "no_live_credentials": provider["attempt"].get("live_credentials_detected", False) is False,
        "raw_persisted_before_strategy_calculation": all(row["persisted_before_strategy_calculation"] for row in provider["raw_rows"]),
        "normalized_persisted_before_strategy_calculation": all(row["persisted_before_strategy_calculation"] for row in provider["normalized_rows"]),
        "current_state_through_latest_completed_session": outcome != OUTCOME_TARGET_FROZEN or psar_state.get("signal_date") == latest_completed.isoformat(),
        "combined_target_valid": outcome != OUTCOME_TARGET_FROZEN or (
            math.isclose(sum(target.values()), 1.0, abs_tol=1e-12)
            and all(value >= 0 for value in target.values())
            and sum(abs(value) for value in target.values()) <= 1.0 + 1e-12
        ),
        "future_execution_only": outcome != OUTCOME_TARGET_FROZEN or (
            execution_date is not None
            and datetime.now(timezone.utc).astimezone(repair.prior_activation.EASTERN)
            < datetime.combine(execution_date, time(16, 0), tzinfo=repair.prior_activation.EASTERN)
        ),
        "no_virtual_position_before_execution": initialization_rows == [] and observation_after.get("current_target_allocation") == {},
        "no_initialization_session_performance": len(performance_rows) == 0,
        "standard_ledger_remains_empty": len(read_csv(COMPONENT_LEDGER)) == 0,
        "historical_backfill_prohibited": observation_after.get("historical_backfill") is False,
        "unrelated_active_observations_unchanged": unrelated_active_before == unrelated_active_after,
        "unrelated_registry_records_unchanged": unrelated_registry_before == unrelated_registry_after,
        "protected_state_and_prior_evidence_unchanged": protected_before == protected_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "no_duplicate_strategy_trial_or_observation": manifest["new_strategy_configurations"] == 0
        and manifest["new_experiment_trials"] == 0
        and manifest["new_paper_demo_observations"] == 0,
        "entity_counts_reconcile": manifest["existing_paper_demo_observations_updated"] in (0, 1)
        and manifest["validation_observations"] == 0
        and manifest["process_tasks"] == 1,
        "no_broker_or_order_action": manifest["broker_or_paper_orders"] == 0,
        "required_outputs_exact_before_consistency": top_level_before_consistency == expected_before_consistency,
        "next_action_not_executed": manifest["next_action_executed"] is False,
    }
    consistency = {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        **required_checks,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_paper_demo_observations": 0,
        "existing_paper_demo_observations_updated": manifest["existing_paper_demo_observations_updated"],
        "validation_observations": 0,
        "process_tasks": 1,
        "data_capability_tasks": manifest["data_capability_tasks"],
        "execution_events": 0,
        "scheduled_execution_events": len(execution_rows),
        "performance_rows": len(performance_rows),
        "broker_calls": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_authorization": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "overall_pass": all(required_checks.values()),
    }
    write_json(output_dir / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "evidence_path": relative(output_dir),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "observation_id": OBSERVATION_ID,
        "initialization_status": observation_after.get("initialization_status", ""),
        "state_date": psar_state.get("signal_date", ""),
        "scheduled_execution_date": execution_date.isoformat() if execution_date else "",
        "first_eligible_performance_date": first_performance_date.isoformat() if first_performance_date else "",
        "performance_rows": len(performance_rows),
        "orders_created": 0,
        "broker_calls": 0,
        "next_action": next_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["outcome"] not in {OUTCOME_BLOCKED} else 1


if __name__ == "__main__":
    raise SystemExit(main())
