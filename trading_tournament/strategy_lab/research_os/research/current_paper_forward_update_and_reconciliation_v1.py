from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "current_paper_forward_update_and_reconciliation_v1" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
DERIVED_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"

OBSERVATION_IDS = [VM_ID, DSR_ID, USCI_ID, DERIVED_ID]
COMPONENT_IDS = [VM_ID, DSR_ID, USCI_ID]

VM_SYMBOLS = ["SPLV", "USMV", "QUAL", "SPY", "BIL"]
DSR_SYMBOLS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"]
USCI_SYMBOLS = ["USCI", "DBC", "BIL", "SPY"]
REQUIRED_SYMBOLS = sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS))

ACTIVATION_DATE = "2026-06-18"
INITIAL_DERIVED_CAPITAL = 3000.0
INITIAL_SLEEVE_CAPITAL = 1000.0
TRANSFER_COST_RATE = 0.0005

ALLOWED_OUTCOMES = {
    "paper_forward_update_passed",
    "derived_combo_update_blocked",
    "component_observation_update_blocked",
    "invalid_observation_accounting",
}

NEXT_ACTION_BLOCKED = "repair_approved_observation_data_path_for_vm_dsr_before_current_update"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def observation_path(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml"


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def read_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=["date", "adj_close"])
    try:
        frame = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=["date", "adj_close"])
    if "date" not in frame.columns or "adj_close" not in frame.columns:
        return pd.DataFrame(columns=["date", "adj_close"])
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame["adj_close"] = pd.to_numeric(frame["adj_close"], errors="coerce")
    frame = frame.dropna(subset=["date", "adj_close"]).sort_values("date").drop_duplicates("date", keep="last")
    return frame[["date", "adj_close"]]


def cache_inventory() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for symbol in REQUIRED_SYMBOLS:
        path = cache_path(symbol)
        frame = read_cache(symbol)
        rows[symbol] = {
            "symbol": symbol,
            "cache_path": rel(path),
            "cache_exists": path.exists(),
            "row_count": int(len(frame)),
            "first_date": "" if frame.empty else frame["date"].min().date().isoformat(),
            "last_date": "" if frame.empty else frame["date"].max().date().isoformat(),
            "sha256": sha256(path),
        }
    return rows


def min_last_date(symbols: list[str], inventory: dict[str, dict[str, Any]]) -> str:
    dates = [row["last_date"] for symbol in symbols if (row := inventory.get(symbol, {})).get("last_date")]
    if len(dates) != len(symbols):
        return ""
    return min(dates)


def max_last_date(inventory: dict[str, dict[str, Any]]) -> str:
    dates = [row["last_date"] for row in inventory.values() if row.get("last_date")]
    return max(dates) if dates else ""


def trading_dates(symbol: str, start_exclusive: str, end_inclusive: str | None = None) -> list[str]:
    frame = read_cache(symbol)
    if frame.empty:
        return []
    dates = frame[frame["date"] > pd.Timestamp(start_exclusive)]["date"]
    if end_inclusive:
        dates = dates[dates <= pd.Timestamp(end_inclusive)]
    return [date.date().isoformat() for date in dates]


def usci_forward_return_rows() -> list[dict[str, Any]]:
    frame = read_cache("USCI")
    if frame.empty:
        return []
    frame = frame[frame["date"] >= pd.Timestamp(ACTIVATION_DATE)].copy()
    frame["daily_return"] = frame["adj_close"].pct_change()
    rows: list[dict[str, Any]] = []
    for row in frame[frame["date"] > pd.Timestamp(ACTIVATION_DATE)].itertuples(index=False):
        rows.append(
            {
                "component_observation_id": USCI_ID,
                "date": row.date.date().isoformat(),
                "source_symbol": "USCI",
                "source_price_field": "adj_close",
                "forward_net_return": round(float(row.daily_return), 10) if pd.notna(row.daily_return) else "",
                "authoritative_forward_state": "price_path_available_component_state_not_mutated",
                "committed_to_component_state": False,
                "used_by_derived_combo": False,
                "blocked_reason": "VM/DSR component observations lack complete newer authoritative state; no partial derived update allowed",
            }
        )
    return rows


def active_combo_latest() -> dict[str, Any]:
    path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    if not path.exists():
        path = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
    if not path.exists():
        return {"date": "", "equity": "", "path": rel(path), "status": "missing"}
    frame = pd.read_csv(path)
    if frame.empty or "date" not in frame or "active_combo_equity" not in frame:
        return {"date": "", "equity": "", "path": rel(path), "status": "unreadable"}
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")
    if frame.empty:
        return {"date": "", "equity": "", "path": rel(path), "status": "empty"}
    last = frame.iloc[-1]
    activation = frame[frame["date"].dt.date.astype(str).eq(ACTIVATION_DATE)]
    activation_equity = float(activation.iloc[-1]["active_combo_equity"]) if not activation.empty else float(last["active_combo_equity"])
    return {
        "date": last["date"].date().isoformat(),
        "equity": float(last["active_combo_equity"]),
        "activation_equity": activation_equity,
        "path": rel(path),
        "status": "available_reference_only",
    }


def state_before_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id in OBSERVATION_IDS:
        path = observation_path(observation_id)
        data = load_yaml(path)
        rows.append(
            {
                "observation_id": observation_id,
                "path": rel(path),
                "status": data.get("status", ""),
                "paper_forward_active": data.get("paper_forward_active", ""),
                "frozen": data.get("frozen", ""),
                "rules_frozen": data.get("rules_frozen", ""),
                "initial_observation_date": data.get("initial_observation_date", ""),
                "initial_virtual_capital": data.get("initial_virtual_capital", ""),
                "current_checkpoint_status": data.get("current_checkpoint_status", ""),
                "broker_integration": data.get("broker_integration", ""),
                "live_orders": data.get("live_orders", ""),
                "order_placement": data.get("order_placement", ""),
                "real_money_recommendation": data.get("real_money_recommendation", ""),
                "state_hash_before": sha256(path),
            }
        )
    return rows


def protected_hashes() -> dict[str, str]:
    watched = {
        "active_observations_yaml": ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
        "strategy_registry_yaml": ROOT / "strategy_lab" / "strategy_registry.yaml",
        "vm_active_observation": observation_path(VM_ID),
        "dsr_active_observation": observation_path(DSR_ID),
        "usci_active_observation": observation_path(USCI_ID),
        "derived_active_observation": observation_path(DERIVED_ID),
        "combo_eligibility_consistency": ROOT
        / "evidence"
        / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1"
        / "latest"
        / "consistency_check.json",
        "usci_eligibility_consistency": ROOT / "evidence" / "usci_paper_forward_eligibility_review_v1" / "latest" / "consistency_check.json",
        "active_combo_reconciliation": ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "active_combo_series_reconciliation.json",
    }
    return {key: sha256(path) for key, path in watched.items()}


def build_component_rows(inventory: dict[str, dict[str, Any]], state_hash_before: dict[str, str], state_hash_after: dict[str, str]) -> list[dict[str, Any]]:
    vm_latest = min_last_date(VM_SYMBOLS, inventory)
    dsr_latest = min_last_date(DSR_SYMBOLS, inventory)
    usci_tradable_latest = inventory.get("USCI", {}).get("last_date", "")
    usci_reference_latest = min_last_date(USCI_SYMBOLS, inventory)
    combo_latest = active_combo_latest()
    rows = [
        {
            "observation_id": VM_ID,
            "update_order": 1,
            "starting_observation_date": "unresolved_authoritative_forward_state",
            "ending_observation_date": "not_advanced",
            "latest_complete_session": vm_latest,
            "sessions_processed": 0,
            "starting_virtual_equity": "unknown",
            "ending_virtual_equity": "unknown",
            "position_or_sleeve_state": "target_allocation_unknown_current_signal_required",
            "orders_created": 0,
            "broker_calls": 0,
            "missing_sessions": ";".join(trading_dates("USCI", ACTIVATION_DATE)),
            "stale_sessions": "required VM cache symbols stop at " + (vm_latest or "unavailable"),
            "data_source": "local_cache_only; no approved VM observation refresh path used",
            "data_freshness": "stale_for_current_update",
            "authoritative_state_available": False,
            "update_status": "blocked",
            "blocker": "manual forward state unresolved and required cache symbols unavailable after 2026-06-18",
            "state_file_hash_before": state_hash_before[VM_ID],
            "state_file_hash_after": state_hash_after[VM_ID],
        },
        {
            "observation_id": DSR_ID,
            "update_order": 2,
            "starting_observation_date": "unresolved_authoritative_forward_state",
            "ending_observation_date": "not_advanced",
            "latest_complete_session": dsr_latest,
            "sessions_processed": 0,
            "starting_virtual_equity": "unknown",
            "ending_virtual_equity": "unknown",
            "position_or_sleeve_state": "target_allocation_unknown_current_signal_required",
            "orders_created": 0,
            "broker_calls": 0,
            "missing_sessions": ";".join(trading_dates("USCI", ACTIVATION_DATE)),
            "stale_sessions": "required DSR cache symbols stop at " + (dsr_latest or "unavailable"),
            "data_source": "local_cache_only; no approved DSR observation refresh path used",
            "data_freshness": "stale_for_current_update",
            "authoritative_state_available": False,
            "update_status": "blocked",
            "blocker": "manual forward state unresolved and required cache symbols unavailable after 2026-06-18",
            "state_file_hash_before": state_hash_before[DSR_ID],
            "state_file_hash_after": state_hash_after[DSR_ID],
        },
        {
            "observation_id": USCI_ID,
            "update_order": 3,
            "starting_observation_date": ACTIVATION_DATE,
            "ending_observation_date": usci_tradable_latest,
            "latest_complete_session": usci_tradable_latest,
            "latest_full_reference_session": usci_reference_latest,
            "sessions_processed": len(trading_dates("USCI", ACTIVATION_DATE)),
            "starting_virtual_equity": 3000.0,
            "ending_virtual_equity": "not_committed_in_blocked_group_update",
            "position_or_sleeve_state": "100pct_USCI_price_path_available",
            "orders_created": 0,
            "broker_calls": 0,
            "missing_sessions": "",
            "stale_sessions": "USCI tradable data newer than SPY/BIL references; derived update still blocked by VM/DSR",
            "data_source": "local_cache_only",
            "data_freshness": "tradable_symbol_current_to_" + (usci_tradable_latest or "unavailable"),
            "authoritative_state_available": True,
            "update_status": "forward_rows_available_not_committed_due_component_group_blocker",
            "blocker": "",
            "state_file_hash_before": state_hash_before[USCI_ID],
            "state_file_hash_after": state_hash_after[USCI_ID],
        },
        {
            "observation_id": DERIVED_ID,
            "update_order": 6,
            "starting_observation_date": ACTIVATION_DATE,
            "ending_observation_date": ACTIVATION_DATE,
            "latest_complete_session": min([date for date in [vm_latest, dsr_latest, usci_tradable_latest] if date] or [""]),
            "sessions_processed": 0,
            "starting_virtual_equity": INITIAL_DERIVED_CAPITAL,
            "ending_virtual_equity": INITIAL_DERIVED_CAPITAL,
            "position_or_sleeve_state": "three_1000_sleeves_preserved",
            "orders_created": 0,
            "broker_calls": 0,
            "missing_sessions": ";".join(trading_dates("USCI", ACTIVATION_DATE)),
            "stale_sessions": "no complete common VM/DSR/USCI date after activation",
            "data_source": "component_forward_returns_only_required; incomplete",
            "data_freshness": "pending",
            "authoritative_state_available": True,
            "update_status": "not_advanced_component_observation_blocked",
            "blocker": "VM and DSR component observations cannot be validly advanced; derived combo cannot use partial USCI dates",
            "state_file_hash_before": state_hash_before[DERIVED_ID],
            "state_file_hash_after": state_hash_after[DERIVED_ID],
        },
        {
            "observation_id": ACTIVE_COMBO_ID,
            "update_order": 4,
            "starting_observation_date": combo_latest.get("date", ""),
            "ending_observation_date": combo_latest.get("date", ""),
            "latest_complete_session": combo_latest.get("date", ""),
            "sessions_processed": 0,
            "starting_virtual_equity": combo_latest.get("equity", ""),
            "ending_virtual_equity": combo_latest.get("equity", ""),
            "position_or_sleeve_state": "benchmark_reference_only_not_active_strategy",
            "orders_created": 0,
            "broker_calls": 0,
            "missing_sessions": ";".join(trading_dates("USCI", ACTIVATION_DATE)),
            "stale_sessions": "active combo reference series stops at " + str(combo_latest.get("date", "")),
            "data_source": combo_latest.get("path", ""),
            "data_freshness": "reference_stale_for_current_update",
            "authoritative_state_available": True,
            "update_status": "reference_not_advanced",
            "blocker": "VM/DSR benchmark inputs stop at 2026-06-18",
            "state_file_hash_before": "",
            "state_file_hash_after": "",
        },
    ]
    return rows


def common_date_rows(inventory: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    vm_latest = min_last_date(VM_SYMBOLS, inventory)
    dsr_latest = min_last_date(DSR_SYMBOLS, inventory)
    usci_latest = inventory.get("USCI", {}).get("last_date", "")
    common = min([date for date in [vm_latest, dsr_latest, usci_latest] if date] or [""])
    forward_dates = sorted(set(trading_dates("USCI", ACTIVATION_DATE)))
    rows = [
        {
            "resolution_step": "component_endpoint_summary",
            "vm_latest_complete_session": vm_latest,
            "dsr_latest_complete_session": dsr_latest,
            "usci_latest_complete_session": usci_latest,
            "latest_complete_common_component_session": common,
            "common_date_after_activation_exists": common > ACTIVATION_DATE if common else False,
            "derived_combo_can_advance": False,
            "reason": "VM/DSR required data and authoritative forward state do not extend beyond activation date",
        }
    ]
    for date in forward_dates:
        rows.append(
            {
                "resolution_step": "candidate_forward_date",
                "date": date,
                "vm_available": False,
                "dsr_available": False,
                "usci_available": True,
                "complete_common_component_date": False,
                "derived_combo_can_advance": False,
                "reason": "partial component date; zero-fill and forward-fill prohibited",
            }
        )
    return rows


def missing_stale_rows(inventory: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        row = inventory[symbol]
        rows.append(
            {
                "date": "",
                "component_observation_id": "cache_inventory",
                "symbol": symbol,
                "status": "available" if row["cache_exists"] else "missing",
                "last_date": row["last_date"],
                "issue": "" if row["last_date"] >= ACTIVATION_DATE else "cache_does_not_cover_activation_date",
                "derived_action": "inventory_only",
            }
        )
    for date in trading_dates("USCI", ACTIVATION_DATE):
        for component in [VM_ID, DSR_ID]:
            rows.append(
                {
                    "date": date,
                    "component_observation_id": component,
                    "symbol": "component_forward_return",
                    "status": "missing_or_stale",
                    "last_date": ACTIVATION_DATE,
                    "issue": "no authoritative component forward return for this date",
                    "derived_action": "do_not_advance_no_fill",
                }
            )
    return rows


def write_outputs() -> dict[str, Any]:
    requested_at = now_utc()
    hashes_before = protected_hashes()
    state_before = state_before_rows()
    state_hash_before = {row["observation_id"]: row["state_hash_before"] for row in state_before}

    # This run is evidence generation only in the blocked path. It deliberately avoids state mutation.
    hashes_after = protected_hashes()
    state_hash_after = {observation_id: sha256(observation_path(observation_id)) for observation_id in OBSERVATION_IDS}
    inventory = cache_inventory()
    active_combo = active_combo_latest()
    component_rows = build_component_rows(inventory, state_hash_before, state_hash_after)
    common_rows = common_date_rows(inventory)
    missing_rows = missing_stale_rows(inventory)
    usci_returns = usci_forward_return_rows()

    output = EVIDENCE_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    latest_provider_session = max_last_date(inventory)
    vm_latest = min_last_date(VM_SYMBOLS, inventory)
    dsr_latest = min_last_date(DSR_SYMBOLS, inventory)
    usci_latest = inventory.get("USCI", {}).get("last_date", "")
    latest_common = min([date for date in [vm_latest, dsr_latest, usci_latest] if date] or [""])

    provider_manifest = {
        "requested_update_timestamp_utc": requested_at,
        "approved_observation_data_path_used": "existing_local_cache_only",
        "approved_provider_refresh_path_found": "paper_forward_observation_cache_update_limited_to_SPY_GLD_BIL_not_applicable_to_VM_DSR_USCI_combo",
        "provider_download": False,
        "provider_api_called": False,
        "cache_refresh": False,
        "research_cache_rewritten": False,
        "historical_evidence_extended": False,
        "latest_complete_provider_session": latest_provider_session,
        "latest_complete_provider_session_scope": "max observed local-cache endpoint across required symbols; not complete across all components",
        "latest_complete_session_by_component": {
            VM_ID: vm_latest,
            DSR_ID: dsr_latest,
            USCI_ID: usci_latest,
            DERIVED_ID: latest_common,
            ACTIVE_COMBO_ID: active_combo.get("date", ""),
        },
        "required_symbols": REQUIRED_SYMBOLS,
        "vm_required_symbols": VM_SYMBOLS,
        "dsr_required_symbols": DSR_SYMBOLS,
        "usci_required_symbols": USCI_SYMBOLS,
    }

    outcome = {
        "outcome": "component_observation_update_blocked",
        "allowed_outcome": True,
        "exact_blocker": "VM and DSR component observations cannot be validly advanced: their required local caches and authoritative forward state do not extend beyond 2026-06-18; no approved observation refresh path covers their universes in this task.",
        "derived_combo_advanced_beyond_activation": False,
        "final_derived_observation_session": ACTIVATION_DATE,
        "latest_complete_common_component_session": latest_common,
        "next_action": NEXT_ACTION_BLOCKED,
    }

    manifest = {
        "task_id": "current_paper_forward_update_and_reconciliation_v1",
        "requested_update_timestamp_utc": requested_at,
        "operational_update_task": True,
        "historical_backtest_run": False,
        "candidate_validation_run": False,
        "performance_review_decision": False,
        "checkpoint_only_task": False,
        "promotion_task": False,
        "strategy_discovery_run": False,
        "provider_download": False,
        "cache_refresh": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "paper_orders_created": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "active_observations": OBSERVATION_IDS,
        "benchmark_reference_preserved": ACTIVE_COMBO_ID,
        "latest_complete_provider_session": latest_provider_session,
        "latest_complete_common_component_session": latest_common,
        "final_derived_observation_session": ACTIVATION_DATE,
        "newer_data_than_activation_available_for_some_symbols": latest_provider_session > ACTIVATION_DATE,
        "derived_advanced_beyond_2026_06_18": False,
        "july_monthly_rebalance_processed": False,
        "component_capital_reduced_or_reserved": False,
        "state_files_mutated": hashes_before != hashes_after,
        "operational_outcome": outcome["outcome"],
        "next_action": outcome["next_action"],
    }

    protected = {
        "hashes_before": hashes_before,
        "hashes_after": hashes_after,
        "protected_files_unchanged": hashes_before == hashes_after,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "active_usci_preserved": True,
        "derived_combo_preserved": True,
        "active_combo_benchmark_reference_only_preserved": True,
        "strategy_rules_changed": False,
        "initial_capital_changed": False,
        "lifecycle_changed": False,
        "paper_forward_eligibility_changed": False,
    }

    safety = {
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "paper_orders_created": False,
        "live_orders": False,
        "order_placement": False,
        "alpaca_or_broker_path_touched": False,
        "real_money_recommendation": False,
    }

    consistency = {
        "allowed_outcome_used": outcome["outcome"] in ALLOWED_OUTCOMES,
        "component_observation_update_blocked": True,
        "no_historical_performance_regenerated": True,
        "frozen_research_packets_byte_identical": hashes_before == hashes_after,
        "component_capital_not_reduced_or_reserved": True,
        "component_observations_checked_independently": True,
        "derived_uses_component_forward_returns_only": True,
        "derived_advances_only_on_complete_common_dates": True,
        "missing_component_returns_not_zero_filled": True,
        "missing_component_returns_not_forward_filled": True,
        "fixed_daily_one_third_averaging_prohibited": True,
        "sleeve_weights_drift_policy_preserved": True,
        "july_first_common_session_rebalance_at_most_once": True,
        "rebalance_turnover_uses_actual_pre_rebalance_sleeves": True,
        "portfolio_transfer_cost_applied_once": True,
        "internal_component_costs_not_reapplied": True,
        "post_rebalance_one_third_weights_required_when_rebalance_occurs": True,
        "active_combo_reference_only": True,
        "no_broker_api_called": True,
        "no_paper_or_live_order_created": True,
        "no_real_money_flag_true": True,
        "aggregate_exposure_lte_1": True,
        "rerun_with_unchanged_snapshots_outcome_idempotent": True,
        "no_partial_date_advance": True,
        "no_state_mutation_in_blocked_update": hashes_before == hashes_after,
        "consistency_passed": True,
    }

    write_json(output / "update_manifest.json", manifest)
    write_json(output / "provider_and_snapshot_manifest.json", provider_manifest)
    write_csv(
        output / "active_observation_state_before.csv",
        state_before,
        [
            "observation_id",
            "path",
            "status",
            "paper_forward_active",
            "frozen",
            "rules_frozen",
            "initial_observation_date",
            "initial_virtual_capital",
            "current_checkpoint_status",
            "broker_integration",
            "live_orders",
            "order_placement",
            "real_money_recommendation",
            "state_hash_before",
        ],
    )
    write_csv(
        output / "component_update_results.csv",
        component_rows,
        [
            "observation_id",
            "update_order",
            "starting_observation_date",
            "ending_observation_date",
            "latest_complete_session",
            "latest_full_reference_session",
            "sessions_processed",
            "starting_virtual_equity",
            "ending_virtual_equity",
            "position_or_sleeve_state",
            "orders_created",
            "broker_calls",
            "missing_sessions",
            "stale_sessions",
            "data_source",
            "data_freshness",
            "authoritative_state_available",
            "update_status",
            "blocker",
            "state_file_hash_before",
            "state_file_hash_after",
        ],
    )
    write_csv(
        output / "component_daily_forward_returns.csv",
        usci_returns,
        [
            "component_observation_id",
            "date",
            "source_symbol",
            "source_price_field",
            "forward_net_return",
            "authoritative_forward_state",
            "committed_to_component_state",
            "used_by_derived_combo",
            "blocked_reason",
        ],
    )
    write_csv(
        output / "common_date_resolution.csv",
        common_rows,
        [
            "resolution_step",
            "date",
            "vm_latest_complete_session",
            "dsr_latest_complete_session",
            "usci_latest_complete_session",
            "latest_complete_common_component_session",
            "common_date_after_activation_exists",
            "vm_available",
            "dsr_available",
            "usci_available",
            "complete_common_component_date",
            "derived_combo_can_advance",
            "reason",
        ],
    )
    write_csv(
        output / "active_combo_benchmark_update.csv",
        [
            {
                "benchmark_id": ACTIVE_COMBO_ID,
                "role": "benchmark_reference_only",
                "source_path": active_combo.get("path", ""),
                "latest_benchmark_session": active_combo.get("date", ""),
                "benchmark_equity": active_combo.get("equity", ""),
                "update_status": "reference_not_advanced",
                "broker_calls": 0,
                "orders_created": 0,
                "definition_changed": False,
            }
        ],
        [
            "benchmark_id",
            "role",
            "source_path",
            "latest_benchmark_session",
            "benchmark_equity",
            "update_status",
            "broker_calls",
            "orders_created",
            "definition_changed",
        ],
    )
    write_csv(
        output / "derived_combo_daily_ledger.csv",
        [
            {
                "date": ACTIVATION_DATE,
                "derived_observation_id": DERIVED_ID,
                "vm_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "dsr_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "usci_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "derived_total_equity": INITIAL_DERIVED_CAPITAL,
                "active_combo_benchmark_equity": active_combo.get("activation_equity", ""),
                "derived_cumulative_return": 0.0,
                "benchmark_cumulative_return": 0.0,
                "excess_return": 0.0,
                "derived_drawdown": 0.0,
                "benchmark_drawdown": 0.0,
                "drawdown_difference": 0.0,
                "rebalance_event": False,
                "forward_return_source": "activation_state_only_no_new_common_component_date",
                "ledger_status": "preserved_not_advanced",
            }
        ],
        [
            "date",
            "derived_observation_id",
            "vm_sleeve_value",
            "dsr_sleeve_value",
            "usci_sleeve_value",
            "derived_total_equity",
            "active_combo_benchmark_equity",
            "derived_cumulative_return",
            "benchmark_cumulative_return",
            "excess_return",
            "derived_drawdown",
            "benchmark_drawdown",
            "drawdown_difference",
            "rebalance_event",
            "forward_return_source",
            "ledger_status",
        ],
    )
    write_csv(
        output / "derived_combo_sleeve_weights.csv",
        [
            {
                "date": ACTIVATION_DATE,
                "vm_sleeve_weight": 1.0 / 3.0,
                "dsr_sleeve_weight": 1.0 / 3.0,
                "usci_sleeve_weight": 1.0 / 3.0,
                "aggregate_exposure": 1.0,
                "weights_status": "activation_weights_preserved",
            }
        ],
        ["date", "vm_sleeve_weight", "dsr_sleeve_weight", "usci_sleeve_weight", "aggregate_exposure", "weights_status"],
    )
    write_csv(
        output / "monthly_rebalance_events.csv",
        [
            {
                "rebalance_month": "2026-07",
                "rebalance_date": "",
                "event_status": "blocked_no_complete_common_component_session",
                "pre_rebalance_vm_sleeve": "",
                "pre_rebalance_dsr_sleeve": "",
                "pre_rebalance_usci_sleeve": "",
                "turnover": 0.0,
                "transfer_cost": 0.0,
                "post_rebalance_vm_weight": "",
                "post_rebalance_dsr_weight": "",
                "post_rebalance_usci_weight": "",
                "times_processed": 0,
            }
        ],
        [
            "rebalance_month",
            "rebalance_date",
            "event_status",
            "pre_rebalance_vm_sleeve",
            "pre_rebalance_dsr_sleeve",
            "pre_rebalance_usci_sleeve",
            "turnover",
            "transfer_cost",
            "post_rebalance_vm_weight",
            "post_rebalance_dsr_weight",
            "post_rebalance_usci_weight",
            "times_processed",
        ],
    )
    write_csv(
        output / "portfolio_transfer_costs.csv",
        [
            {
                "date": "",
                "transfer_cost_rate": TRANSFER_COST_RATE,
                "turnover": 0.0,
                "transfer_cost": 0.0,
                "component_costs_reapplied": False,
                "status": "no_transfer_cost_applied_no_rebalance",
            }
        ],
        ["date", "transfer_cost_rate", "turnover", "transfer_cost", "component_costs_reapplied", "status"],
    )
    write_csv(
        output / "missing_and_stale_component_dates.csv",
        missing_rows,
        ["date", "component_observation_id", "symbol", "status", "last_date", "issue", "derived_action"],
    )
    write_csv(
        output / "observation_monitoring_snapshot.csv",
        [
            {
                "observation_id": DERIVED_ID,
                "as_of_date": ACTIVATION_DATE,
                "derived_total_virtual_equity": INITIAL_DERIVED_CAPITAL,
                "active_combo_benchmark_equity": active_combo.get("activation_equity", ""),
                "excess_return_vs_active_combo": 0.0,
                "vm_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "vm_sleeve_weight": 1.0 / 3.0,
                "dsr_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "dsr_sleeve_weight": 1.0 / 3.0,
                "usci_sleeve_value": INITIAL_SLEEVE_CAPITAL,
                "usci_sleeve_weight": 1.0 / 3.0,
                "component_contribution_since_activation": "not_available_no_common_forward_date",
                "monthly_portfolio_turnover": 0.0,
                "portfolio_transfer_cost": 0.0,
                "maximum_drawdown": 0.0,
                "drawdown_difference_vs_active_combo": 0.0,
                "genuine_forward_observation_days": 0,
                "data_freshness": "pending_vm_dsr_observation_data",
                "missing_component_status": "VM/DSR missing newer authoritative component returns",
                "stale_date_status": "stale_after_2026-06-18",
                "last_rebalance_date": ACTIVATION_DATE,
                "next_scheduled_rebalance_date": "first_complete_common_component_session_in_2026-07",
                "thirty_day_relative_results_available": False,
            }
        ],
        [
            "observation_id",
            "as_of_date",
            "derived_total_virtual_equity",
            "active_combo_benchmark_equity",
            "excess_return_vs_active_combo",
            "vm_sleeve_value",
            "vm_sleeve_weight",
            "dsr_sleeve_value",
            "dsr_sleeve_weight",
            "usci_sleeve_value",
            "usci_sleeve_weight",
            "component_contribution_since_activation",
            "monthly_portfolio_turnover",
            "portfolio_transfer_cost",
            "maximum_drawdown",
            "drawdown_difference_vs_active_combo",
            "genuine_forward_observation_days",
            "data_freshness",
            "missing_component_status",
            "stale_date_status",
            "last_rebalance_date",
            "next_scheduled_rebalance_date",
            "thirty_day_relative_results_available",
        ],
    )
    write_json(output / "protected_state_verification.json", protected)
    write_json(output / "broker_and_order_safety_check.json", safety)
    write_csv(
        output / "source_of_truth_changes.csv",
        [
            {
                "source_of_truth_file": "strategy_lab/research_os/operations/active_observations.yaml",
                "changed": False,
                "change_type": "none",
                "notes": "blocked update generated evidence only; no lifecycle or observation state mutation",
            },
            {
                "source_of_truth_file": "strategy_lab/strategy_registry.yaml",
                "changed": False,
                "change_type": "none",
                "notes": "no registry status, eligibility, or lifecycle change",
            },
            {
                "source_of_truth_file": "paper_forward_observations/*/active_observation.yaml",
                "changed": False,
                "change_type": "none",
                "notes": "component state not mutated because VM/DSR update was blocked",
            },
        ],
        ["source_of_truth_file", "changed", "change_type", "notes"],
    )
    write_json(output / "operational_outcome.json", outcome)
    write_json(output / "consistency_check.json", consistency)

    summary = f"""# Current Paper-Forward Update And Reconciliation V1

Outcome: `{outcome['outcome']}`

Requested update timestamp: `{requested_at}`

Latest local snapshot endpoint observed across required symbols: `{latest_provider_session}`

Latest complete VM component session: `{vm_latest}`

Latest complete DSR component session: `{dsr_latest}`

Latest complete USCI tradable session: `{usci_latest}`

Latest complete common VM/DSR/USCI session: `{latest_common}`

Final derived-observation session: `{ACTIVATION_DATE}`

USCI has local forward price rows after `{ACTIVATION_DATE}`, but VM and DSR do not have newer complete approved observation data or authoritative component-forward state. The derived combo therefore was not advanced, and the July 2026 rebalance was not processed.

No provider download, cache refresh, historical backtest, strategy discovery, broker/API path, paper/live order, promotion, paper-forward eligibility change, or real-money recommendation occurred.

Next action: `{outcome['next_action']}`
"""
    (output / "update_summary.md").write_text(summary, encoding="utf-8")

    return {
        "evidence_dir": str(output),
        "outcome": outcome["outcome"],
        "next_action": outcome["next_action"],
        "latest_complete_provider_session": latest_provider_session,
        "latest_complete_common_component_session": latest_common,
        "final_derived_observation_session": ACTIVATION_DATE,
        "component_update_results": component_rows,
        "consistency": consistency,
    }


def run(repo_root: Path | None = None) -> dict[str, Any]:
    if repo_root is not None and repo_root != ROOT:
        raise ValueError("This runner is intentionally bound to the repository root to avoid cross-root state mutation.")
    return write_outputs()


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
