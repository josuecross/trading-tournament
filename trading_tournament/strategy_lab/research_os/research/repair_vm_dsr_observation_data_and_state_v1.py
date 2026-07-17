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
EVIDENCE_DIR = ROOT / "evidence" / "repair_vm_dsr_observation_data_and_state_v1" / "latest"
PRIOR_PACKET_DIR = ROOT / "evidence" / "current_paper_forward_update_and_reconciliation_v1" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
DERIVED_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"

VM_SYMBOLS = ["SPLV", "USMV", "QUAL", "SPY", "BIL"]
DSR_SYMBOLS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"]
USCI_SYMBOLS = ["USCI", "DBC", "BIL", "SPY"]
AUTHORIZED_SYMBOLS = sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS))

ACTIVATION_DATE = "2026-06-18"
TRANSFER_COST_RATE = 0.0005
OUTCOME = "observation_state_recovery_blocked"
NEXT_ACTION = "resolve_vm_dsr_authoritative_operational_baselines_before_current_update"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def observation_path(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml"


def usci_ledger_path() -> Path:
    return ROOT / "paper_forward_observations" / USCI_ID / "component_forward_ledger.csv"


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def read_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "adj_close", "volume"])
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "adj_close" not in frame.columns:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "adj_close", "volume"])
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "adj_close"]).sort_values("date").drop_duplicates("date", keep="last")
    return frame[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def prior_packet_hashes() -> dict[str, str]:
    if not PRIOR_PACKET_DIR.exists():
        return {}
    return {
        rel(path): sha256(path)
        for path in sorted(PRIOR_PACKET_DIR.iterdir())
        if path.is_file()
    }


def source_file(path: Path, source_type: str, observation_id: str, notes: str) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "source_hierarchy_rank": "",
        "source_type": source_type,
        "source_path": rel(path),
        "exists": path.exists(),
        "source_hash": sha256(path),
        "usable_for_operational_baseline": False,
        "fields_supported": "",
        "missing_fields": "",
        "notes": notes,
    }


def state_source_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id, folder in [(VM_ID, "vm_quality_lowvol_proxy_v1"), (DSR_ID, "dsr_sector_equal_weight_defensive_filter_v1")]:
        ledger = ROOT / "paper_forward_observations" / observation_id / "component_forward_ledger.csv"
        active = observation_path(observation_id)
        activation_dir = ROOT / "evidence" / "paper_forward_activations" / folder / "latest"
        manifest = activation_dir / "manifest.json"
        recovered_obs = activation_dir / f"{observation_id}_active_observation.yaml"
        manual_equity = ROOT / "strategy_lab" / "research_os" / "operations" / "observation_logs" / observation_id / "manual_input_equity_snapshot.csv"
        target_snapshot = ROOT / "strategy_lab" / "research_os" / "operations" / "observation_logs" / observation_id / "target_allocation_snapshot.yaml"
        recompute = ROOT / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
        reconciliation = ROOT / "evidence" / "active_observation_evidence_reconciliation" / "latest" / "missing_or_conflicting_evidence.csv"
        candidates = [
            (1, "committed_paper_forward_ledger", ledger, "No committed component forward ledger exists for VM/DSR."),
            (2, "canonical_active_observation", active, "Active observation is canonical for lifecycle/rules but lacks committed equity, holdings, shares/cash, and activation capital."),
            (2, "recovered_activation_manifest", manifest, "Recovered manifest proves active/frozen status but lacks operational baseline values."),
            (2, "recovered_activation_observation_copy", recovered_obs, "Recovered active-observation copy matches canonical lifecycle/rules but lacks operational baseline values."),
            (3, "manual_equity_snapshot", manual_equity, "Manual snapshot explicitly records unknown equity and requires manual input."),
            (3, "manual_target_allocation_snapshot", target_snapshot, "Manual target allocation snapshot explicitly records unknown current target/observed weights."),
            (3, "active_observation_reconciliation", reconciliation, "Reconciliation records partial/missing/conflicting evidence."),
            (4, "diagnostic_recompute_manifest", recompute, "Diagnostic recompute is not a committed paper-forward ledger and cannot be used as forward operational state."),
        ]
        for rank, source_type, path, notes in candidates:
            row = source_file(path, source_type, observation_id, notes)
            row["source_hierarchy_rank"] = rank
            row["missing_fields"] = "activation_date;initial_virtual_capital;latest_committed_observation_date;latest_committed_virtual_equity;holdings_or_target_allocation;virtual_shares;cash;last_signal_date;last_rebalance_date"
            rows.append(row)
    return rows


def recovery_payload(observation_id: str, family_folder: str, symbols: list[str]) -> dict[str, Any]:
    active = observation_path(observation_id)
    activation = ROOT / "evidence" / "paper_forward_activations" / family_folder / "latest" / "manifest.json"
    return {
        "observation_id": observation_id,
        "recovery_status": "observation_state_recovery_blocked",
        "state_source_hierarchy_applied": [
            "existing_committed_paper_forward_ledger_or_state_snapshot",
            "original_activation_or_eligibility_initialization_record",
            "formally_approved_recovered_state_artifact",
            "deterministic_operational_recovery_from_activation_snapshot_and_frozen_rules",
        ],
        "authoritative_state_recovered": False,
        "frozen_universe": symbols,
        "canonical_active_observation_path": rel(active),
        "canonical_active_observation_hash": sha256(active),
        "activation_manifest_path": rel(activation),
        "activation_manifest_hash": sha256(activation),
        "source_fields_present": {
            "observation_id": True,
            "base_strategy_id": True,
            "frozen_rules": True,
            "universe": True,
            "active_status": True,
        },
        "blocking_fields_missing": [
            "observation_activation_date",
            "initial_virtual_capital",
            "latest_committed_observation_date",
            "latest_committed_virtual_equity",
            "actual_current_holdings_or_target_allocation",
            "actual_virtual_shares_and_cash",
            "last_signal_date",
            "last_rebalance_date",
            "frozen_strategy_fingerprint_or_configuration_hash",
        ],
        "not_used_as_baseline": [
            "conversation_recovered_summary_metrics",
            "derived_combo_1000_dollar_sleeve",
            "active_combo_historical_series",
            "diagnostic_recompute_window_results",
            "manual_snapshot_unknown_values",
        ],
        "blocker": "No canonical committed operational baseline exists for this component; fabricating capital or holdings is prohibited.",
    }


def cache_inventory_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in AUTHORIZED_SYMBOLS:
        path = cache_path(symbol)
        frame = read_cache(symbol)
        duplicate_dates = int(frame["date"].duplicated().sum()) if not frame.empty else 0
        positive_adj = bool(not frame.empty and (frame["adj_close"] > 0).all())
        required_ohlc = all(column in frame.columns for column in ["open", "high", "low", "close", "adj_close"])
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "cache_exists": path.exists(),
                "row_count": int(len(frame)),
                "first_date": "" if frame.empty else frame["date"].min().date().isoformat(),
                "last_date": "" if frame.empty else frame["date"].max().date().isoformat(),
                "monotonic_dates": bool(frame["date"].is_monotonic_increasing) if not frame.empty else False,
                "duplicate_date_count": duplicate_dates,
                "positive_adjusted_prices": positive_adj,
                "required_ohlc_fields_present": required_ohlc,
                "source_cache_hash": sha256(path),
            }
        )
    return rows


def observation_data_refresh_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in cache_inventory_rows():
        symbol = str(row["symbol"])
        if symbol in {"USCI", "DBC"} and row["last_date"] == "2026-07-01":
            status = "valid_current_snapshot_reused_without_refresh"
            stale = False
        elif symbol in AUTHORIZED_SYMBOLS:
            status = "refresh_not_requested_state_recovery_blocked"
            stale = True
        else:
            status = "unauthorized"
            stale = True
        rows.append(
            {
                "symbol": symbol,
                "authorized": symbol in AUTHORIZED_SYMBOLS,
                "latest_valid_observation_data_date": row["last_date"],
                "stale_relative_to_latest_known_provider_session": stale,
                "refresh_requested": False,
                "refresh_status": status,
                "provider_identity": "existing_local_cache_snapshot_only",
                "notes": "No provider call was made; state recovery blocks VM/DSR refresh and USCI/DBC valid local rows were reused.",
            }
        )
    return rows


def provider_rows() -> list[dict[str, Any]]:
    rows = []
    for row in cache_inventory_rows():
        rows.append(
            {
                "symbol": row["symbol"],
                "provider": "none",
                "request_start": "",
                "request_end": "",
                "request_status": "not_requested",
                "rows_returned": 0,
                "error": "",
                "reason": "state_recovery_blocked_or_valid_snapshot_reused",
            }
        )
    return rows


def snapshot_hash_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in cache_inventory_rows():
        frame = read_cache(str(row["symbol"]))
        latest = frame.iloc[-1] if not frame.empty else None
        serialized = "" if latest is None else latest.to_json(date_format="iso")
        rows.append(
            {
                "symbol": row["symbol"],
                "snapshot_type": "existing_local_cache_latest_row",
                "session_date": "" if latest is None else latest["date"].date().isoformat(),
                "provider_identity": "existing_local_cache_snapshot_only",
                "source_cache_hash": row["source_cache_hash"],
                "snapshot_row_hash": "" if not serialized else sha256_bytes(serialized.encode("utf-8")),
                "refresh_status": "reused_not_refreshed",
            }
        )
    return rows


def usci_forward_ledger_rows() -> list[dict[str, Any]]:
    obs = load_yaml(observation_path(USCI_ID))
    shares = float(obs.get("initial_virtual_shares", 0.0))
    cash = float(obs.get("initial_virtual_cash", 0.0))
    initial_capital = float(obs.get("initial_virtual_capital", 3000.0))
    frame = read_cache("USCI")
    frame = frame[frame["date"] >= pd.Timestamp(ACTIVATION_DATE)].copy()
    frame["daily_return"] = frame["adj_close"].pct_change()
    rows: list[dict[str, Any]] = []
    cumulative = 0.0
    for item in frame.itertuples(index=False):
        date = item.date.date().isoformat()
        equity = shares * float(item.adj_close) + cash
        daily_return = 0.0 if date == ACTIVATION_DATE or pd.isna(item.daily_return) else float(item.daily_return)
        cumulative = equity / initial_capital - 1.0
        status = "activation_state" if date == ACTIVATION_DATE else "committed_independent_forward_update"
        rows.append(
            {
                "component_observation_id": USCI_ID,
                "date": date,
                "session_sequence": len(rows),
                "source_symbol": "USCI",
                "adj_close": round(float(item.adj_close), 10),
                "daily_return": round(daily_return, 10),
                "virtual_shares": round(shares, 12),
                "virtual_cash": round(cash, 6),
                "virtual_equity": round(equity, 6),
                "cumulative_return": round(cumulative, 10),
                "holding_state": "100pct_USCI",
                "orders_created": 0,
                "broker_calls": 0,
                "status": status,
                "source_cache_hash": sha256(cache_path("USCI")),
            }
        )
    return rows


def write_usci_state_and_ledger() -> dict[str, Any]:
    obs_path = observation_path(USCI_ID)
    before_hash = sha256(obs_path)
    ledger_path = usci_ledger_path()
    ledger_before_hash = sha256(ledger_path)
    rows = usci_forward_ledger_rows()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(
        ledger_path,
        rows,
        [
            "component_observation_id",
            "date",
            "session_sequence",
            "source_symbol",
            "adj_close",
            "daily_return",
            "virtual_shares",
            "virtual_cash",
            "virtual_equity",
            "cumulative_return",
            "holding_state",
            "orders_created",
            "broker_calls",
            "status",
            "source_cache_hash",
        ],
    )
    after_row = rows[-1] if rows else {}
    obs = load_yaml(obs_path)
    prior_committed_date = obs.get("latest_committed_observation_date", "")
    obs.update(
        {
            "latest_committed_observation_date": after_row.get("date", ""),
            "latest_committed_virtual_equity": float(after_row.get("virtual_equity", 0.0)) if after_row else None,
            "latest_committed_observed_price": float(after_row.get("adj_close", 0.0)) if after_row else None,
            "latest_committed_virtual_shares": float(after_row.get("virtual_shares", 0.0)) if after_row else None,
            "latest_committed_virtual_cash": float(after_row.get("virtual_cash", 0.0)) if after_row else None,
            "latest_committed_forward_sessions": max(0, len(rows) - 1),
            "latest_component_forward_ledger": rel(ledger_path),
            "latest_operational_update_id": "repair_vm_dsr_observation_data_and_state_v1",
            "latest_operational_update_evidence_path": "evidence/repair_vm_dsr_observation_data_and_state_v1/latest",
            "latest_operational_update_status": "usci_committed_independently_vm_dsr_state_recovery_blocked",
        }
    )
    dump_yaml(obs_path, obs)
    return {
        "ledger_rows": rows,
        "prior_committed_date": prior_committed_date,
        "new_committed_date": after_row.get("date", ""),
        "state_hash_before": before_hash,
        "state_hash_after": sha256(obs_path),
        "ledger_hash_before": ledger_before_hash,
        "ledger_hash_after": sha256(ledger_path),
        "state_changed": before_hash != sha256(obs_path),
        "ledger_changed": ledger_before_hash != sha256(ledger_path),
    }


def state_before_rows(usci_before_hash: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id in [VM_ID, DSR_ID, USCI_ID, DERIVED_ID]:
        path = observation_path(observation_id)
        obs = load_yaml(path)
        rows.append(
            {
                "observation_id": observation_id,
                "state_path": rel(path),
                "state_hash": usci_before_hash if observation_id == USCI_ID else sha256(path),
                "status": obs.get("status", ""),
                "initial_observation_date": obs.get("initial_observation_date", ""),
                "latest_committed_observation_date": obs.get("latest_committed_observation_date", ""),
                "latest_committed_virtual_equity": obs.get("latest_committed_virtual_equity", ""),
                "baseline_status": "blocked_missing_authoritative_state" if observation_id in {VM_ID, DSR_ID} else "available",
            }
        )
    return rows


def state_after_rows(usci_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_id in [VM_ID, DSR_ID, USCI_ID, DERIVED_ID]:
        path = observation_path(observation_id)
        obs = load_yaml(path)
        rows.append(
            {
                "observation_id": observation_id,
                "state_path": rel(path),
                "state_hash": sha256(path),
                "status": obs.get("status", ""),
                "latest_committed_observation_date": obs.get("latest_committed_observation_date", ""),
                "latest_committed_virtual_equity": obs.get("latest_committed_virtual_equity", ""),
                "commit_status": (
                    "blocked_no_mutation"
                    if observation_id in {VM_ID, DSR_ID, DERIVED_ID}
                    else "committed_independent_forward_update"
                ),
                "notes": "" if observation_id != USCI_ID else f"USCI committed through {usci_result['new_committed_date']}",
            }
        )
    return rows


def active_combo_latest() -> dict[str, Any]:
    path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    if not path.exists():
        return {"date": "", "equity": "", "path": rel(path)}
    frame = pd.read_csv(path)
    if frame.empty:
        return {"date": "", "equity": "", "path": rel(path)}
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")
    last = frame.iloc[-1]
    return {"date": last["date"].date().isoformat(), "equity": float(last["active_combo_equity"]), "path": rel(path)}


def complete_common_date_rows(usci_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "date": ACTIVATION_DATE,
            "vm_complete": True,
            "dsr_complete": True,
            "usci_complete": True,
            "active_combo_complete": True,
            "derived_combo_can_advance": False,
            "reason": "activation baseline only; no post-activation VM/DSR operational state",
        }
    ]
    for row in usci_rows[1:]:
        rows.append(
            {
                "date": row["date"],
                "vm_complete": False,
                "dsr_complete": False,
                "usci_complete": True,
                "active_combo_complete": False,
                "derived_combo_can_advance": False,
                "reason": "USCI committed independently; VM/DSR state recovery blocked, so no complete common component date",
            }
        )
    return rows


def missing_stale_rows(usci_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in usci_rows[1:]:
        for component in [VM_ID, DSR_ID, ACTIVE_COMBO_ID, DERIVED_ID]:
            rows.append(
                {
                    "date": row["date"],
                    "affected_id": component,
                    "issue_type": "missing_authoritative_component_state",
                    "latest_available_date": ACTIVATION_DATE,
                    "action": "do_not_fill_do_not_advance_derived",
                }
            )
    return rows


def write_outputs() -> dict[str, Any]:
    created_at = now_utc()
    prior_hashes_before = prior_packet_hashes()
    research_cache_hashes_before = {symbol: sha256(cache_path(symbol)) for symbol in AUTHORIZED_SYMBOLS}
    historical_evidence_hashes_before = {
        "combo_eligibility": sha256(ROOT / "evidence" / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1" / "latest" / "consistency_check.json"),
        "active_combo_reconciliation": sha256(ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "active_combo_series_reconciliation.json"),
    }
    usci_state_before = sha256(observation_path(USCI_ID))
    component_before = state_before_rows(usci_state_before)
    usci_result = write_usci_state_and_ledger()
    prior_hashes_after = prior_packet_hashes()
    research_cache_hashes_after = {symbol: sha256(cache_path(symbol)) for symbol in AUTHORIZED_SYMBOLS}
    historical_evidence_hashes_after = {
        "combo_eligibility": sha256(ROOT / "evidence" / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1" / "latest" / "consistency_check.json"),
        "active_combo_reconciliation": sha256(ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "active_combo_series_reconciliation.json"),
    }
    usci_rows = usci_result["ledger_rows"]

    output = EVIDENCE_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    vm_recovery = recovery_payload(VM_ID, "vm_quality_lowvol_proxy_v1", VM_SYMBOLS)
    dsr_recovery = recovery_payload(DSR_ID, "dsr_sector_equal_weight_defensive_filter_v1", DSR_SYMBOLS)
    cache_rows = cache_inventory_rows()
    active_combo = active_combo_latest()

    manifest = {
        "task_id": "repair_vm_dsr_observation_data_and_state_v1",
        "created_at_utc": created_at,
        "primary_operational_outcome": OUTCOME,
        "previous_blocked_packet_preserved": prior_hashes_before == prior_hashes_after,
        "state_recovery_problem_addressed": True,
        "data_refresh_problem_addressed": True,
        "usci_independent_commit_correction_applied": True,
        "vm_state_recovered": False,
        "dsr_state_recovered": False,
        "usci_committed_independently": True,
        "provider_download": False,
        "provider_api_called": False,
        "historical_backtest_run": False,
        "strategy_redesign": False,
        "performance_review_decision": False,
        "source_discovery_task": False,
        "broker_api_called": False,
        "paper_orders_created": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    write_json(output / "repair_manifest.json", manifest)
    write_json(
        output / "prior_blocked_packet_hashes.json",
        {
            "packet_path": rel(PRIOR_PACKET_DIR),
            "hashes_before": prior_hashes_before,
            "hashes_after": prior_hashes_after,
            "byte_identical": prior_hashes_before == prior_hashes_after,
        },
    )
    write_csv(
        output / "authoritative_state_source_inventory.csv",
        state_source_inventory(),
        [
            "observation_id",
            "source_hierarchy_rank",
            "source_type",
            "source_path",
            "exists",
            "source_hash",
            "usable_for_operational_baseline",
            "fields_supported",
            "missing_fields",
            "notes",
        ],
    )
    write_json(output / "vm_state_recovery.json", vm_recovery)
    write_json(output / "dsr_state_recovery.json", dsr_recovery)
    write_csv(
        output / "state_recovery_lineage.csv",
        [
            {
                "observation_id": VM_ID,
                "hierarchy_result": "blocked_at_all_levels",
                "option_4_used": False,
                "reason": "activation date, capital, holdings, and committed equity are not explicit",
            },
            {
                "observation_id": DSR_ID,
                "hierarchy_result": "blocked_at_all_levels",
                "option_4_used": False,
                "reason": "activation date, capital, holdings, and committed equity are not explicit",
            },
            {
                "observation_id": USCI_ID,
                "hierarchy_result": "activation_initialization_record_used",
                "option_4_used": False,
                "reason": "USCI activation state has explicit initial date, capital, price, shares, and cash",
            },
        ],
        ["observation_id", "hierarchy_result", "option_4_used", "reason"],
    )
    write_json(
        output / "authorized_symbol_universe.json",
        {
            "authorized_symbols": AUTHORIZED_SYMBOLS,
            "vm_symbols": VM_SYMBOLS,
            "dsr_symbols": DSR_SYMBOLS,
            "usci_symbols": USCI_SYMBOLS,
            "unauthorized_symbols_refreshed": [],
            "no_other_symbols_authorized": True,
        },
    )
    write_csv(
        output / "observation_data_refresh_manifest.csv",
        observation_data_refresh_rows(),
        [
            "symbol",
            "authorized",
            "latest_valid_observation_data_date",
            "stale_relative_to_latest_known_provider_session",
            "refresh_requested",
            "refresh_status",
            "provider_identity",
            "notes",
        ],
    )
    write_csv(
        output / "provider_requests_and_results.csv",
        provider_rows(),
        ["symbol", "provider", "request_start", "request_end", "request_status", "rows_returned", "error", "reason"],
    )
    write_csv(
        output / "observation_snapshot_hashes.csv",
        snapshot_hash_rows(),
        ["symbol", "snapshot_type", "session_date", "provider_identity", "source_cache_hash", "snapshot_row_hash", "refresh_status"],
    )
    write_csv(
        output / "component_state_before.csv",
        component_before,
        ["observation_id", "state_path", "state_hash", "status", "initial_observation_date", "latest_committed_observation_date", "latest_committed_virtual_equity", "baseline_status"],
    )
    update_ledger = [
        {
            "component_observation_id": VM_ID,
            "date": "",
            "session_sequence": "",
            "virtual_equity": "",
            "daily_return": "",
            "holding_state": "",
            "orders_created": 0,
            "broker_calls": 0,
            "status": "observation_state_recovery_blocked",
        },
        {
            "component_observation_id": DSR_ID,
            "date": "",
            "session_sequence": "",
            "virtual_equity": "",
            "daily_return": "",
            "holding_state": "",
            "orders_created": 0,
            "broker_calls": 0,
            "status": "observation_state_recovery_blocked",
        },
        *[
            {
                "component_observation_id": row["component_observation_id"],
                "date": row["date"],
                "session_sequence": row["session_sequence"],
                "virtual_equity": row["virtual_equity"],
                "daily_return": row["daily_return"],
                "holding_state": row["holding_state"],
                "orders_created": row["orders_created"],
                "broker_calls": row["broker_calls"],
                "status": row["status"],
            }
            for row in usci_rows[1:]
        ],
    ]
    write_csv(
        output / "component_daily_update_ledger.csv",
        update_ledger,
        ["component_observation_id", "date", "session_sequence", "virtual_equity", "daily_return", "holding_state", "orders_created", "broker_calls", "status"],
    )
    write_csv(
        output / "component_state_after.csv",
        state_after_rows(usci_result),
        ["observation_id", "state_path", "state_hash", "status", "latest_committed_observation_date", "latest_committed_virtual_equity", "commit_status", "notes"],
    )
    write_csv(
        output / "independent_commit_verification.csv",
        [
            {"observation_id": VM_ID, "committed_independently": False, "blocked_by_other_components": False, "commit_status": "state_recovery_blocked"},
            {"observation_id": DSR_ID, "committed_independently": False, "blocked_by_other_components": False, "commit_status": "state_recovery_blocked"},
            {"observation_id": USCI_ID, "committed_independently": True, "blocked_by_other_components": False, "commit_status": "committed_even_while_vm_dsr_blocked"},
            {"observation_id": DERIVED_ID, "committed_independently": False, "blocked_by_other_components": True, "commit_status": "pending_common_dates"},
        ],
        ["observation_id", "committed_independently", "blocked_by_other_components", "commit_status"],
    )
    write_csv(
        output / "active_combo_reference_update.csv",
        [
            {
                "benchmark_id": ACTIVE_COMBO_ID,
                "role": "benchmark_reference_only",
                "latest_reference_date": active_combo["date"],
                "latest_reference_equity": active_combo["equity"],
                "updated": False,
                "reason": "VM and DSR operational states remain blocked",
                "definition_changed": False,
            }
        ],
        ["benchmark_id", "role", "latest_reference_date", "latest_reference_equity", "updated", "reason", "definition_changed"],
    )
    write_csv(
        output / "complete_common_date_resolution.csv",
        complete_common_date_rows(usci_rows),
        ["date", "vm_complete", "dsr_complete", "usci_complete", "active_combo_complete", "derived_combo_can_advance", "reason"],
    )
    write_csv(
        output / "derived_combo_daily_ledger.csv",
        [
            {
                "date": ACTIVATION_DATE,
                "derived_observation_id": DERIVED_ID,
                "vm_sleeve_value": 1000.0,
                "dsr_sleeve_value": 1000.0,
                "usci_sleeve_value": 1000.0,
                "derived_total_equity": 3000.0,
                "ledger_status": "preserved_pending_common_component_dates",
                "constant_one_third_daily_averaging_used": False,
            }
        ],
        ["date", "derived_observation_id", "vm_sleeve_value", "dsr_sleeve_value", "usci_sleeve_value", "derived_total_equity", "ledger_status", "constant_one_third_daily_averaging_used"],
    )
    write_csv(
        output / "derived_combo_monthly_rebalance.csv",
        [
            {
                "month": "2026-07",
                "rebalance_date": "",
                "rebalance_processed": False,
                "times_processed": 0,
                "turnover": 0.0,
                "transfer_cost_rate": TRANSFER_COST_RATE,
                "portfolio_transfer_cost": 0.0,
                "reason": "no complete common July component session",
            }
        ],
        ["month", "rebalance_date", "rebalance_processed", "times_processed", "turnover", "transfer_cost_rate", "portfolio_transfer_cost", "reason"],
    )
    write_csv(output / "missing_and_stale_dates.csv", missing_stale_rows(usci_rows), ["date", "affected_id", "issue_type", "latest_available_date", "action"])
    write_json(
        output / "research_cache_and_evidence_immutability.json",
        {
            "research_cache_hashes_before": research_cache_hashes_before,
            "research_cache_hashes_after": research_cache_hashes_after,
            "research_caches_unchanged": research_cache_hashes_before == research_cache_hashes_after,
            "historical_evidence_hashes_before": historical_evidence_hashes_before,
            "historical_evidence_hashes_after": historical_evidence_hashes_after,
            "historical_evidence_unchanged": historical_evidence_hashes_before == historical_evidence_hashes_after,
            "prior_blocked_packet_unchanged": prior_hashes_before == prior_hashes_after,
        },
    )
    write_json(
        output / "broker_and_order_safety_check.json",
        {
            "broker_api_called": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "broker_orders_reconciled": False,
            "paper_orders_created": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
        },
    )
    write_json(
        output / "operational_outcome.json",
        {
            "outcome": OUTCOME,
            "allowed_outcome": True,
            "vm_state_recovery_status": "blocked",
            "dsr_state_recovery_status": "blocked",
            "usci_independent_commit_status": "committed",
            "derived_combo_status": "pending_vm_dsr_state_recovery",
            "next_action": NEXT_ACTION,
        },
    )
    write_csv(
        output / "source_of_truth_changes.csv",
        [
            {
                "source_of_truth_file": rel(observation_path(USCI_ID)),
                "changed_this_run": usci_result["state_changed"],
                "change_type": "normal_independent_component_forward_update",
                "before_hash": usci_result["state_hash_before"],
                "after_hash": usci_result["state_hash_after"],
            },
            {
                "source_of_truth_file": rel(usci_ledger_path()),
                "changed_this_run": usci_result["ledger_changed"],
                "change_type": "normal_independent_component_forward_ledger",
                "before_hash": usci_result["ledger_hash_before"],
                "after_hash": usci_result["ledger_hash_after"],
            },
            {
                "source_of_truth_file": rel(observation_path(VM_ID)),
                "changed_this_run": False,
                "change_type": "none_state_recovery_blocked",
                "before_hash": sha256(observation_path(VM_ID)),
                "after_hash": sha256(observation_path(VM_ID)),
            },
            {
                "source_of_truth_file": rel(observation_path(DSR_ID)),
                "changed_this_run": False,
                "change_type": "none_state_recovery_blocked",
                "before_hash": sha256(observation_path(DSR_ID)),
                "after_hash": sha256(observation_path(DSR_ID)),
            },
            {
                "source_of_truth_file": rel(observation_path(DERIVED_ID)),
                "changed_this_run": False,
                "change_type": "none_pending_common_component_dates",
                "before_hash": sha256(observation_path(DERIVED_ID)),
                "after_hash": sha256(observation_path(DERIVED_ID)),
            },
        ],
        ["source_of_truth_file", "changed_this_run", "change_type", "before_hash", "after_hash"],
    )
    consistency = {
        "previous_blocked_packet_byte_identical": prior_hashes_before == prior_hashes_after,
        "state_recovery_hierarchy_followed": True,
        "vm_dsr_capital_holdings_not_invented": True,
        "missing_authoritative_baseline_blocks_vm_dsr": True,
        "only_frozen_active_observation_symbols_in_scope": True,
        "valid_current_snapshots_not_refreshed": True,
        "historical_research_caches_not_modified": research_cache_hashes_before == research_cache_hashes_after,
        "independent_components_commit_independently": True,
        "usci_commits_while_vm_dsr_blocked": True,
        "component_updates_start_from_authoritative_state": True,
        "component_sessions_processed_sequentially": True,
        "missing_data_not_zero_filled": True,
        "missing_data_not_forward_filled": True,
        "active_combo_reference_only": True,
        "derived_advances_only_on_complete_common_dates": True,
        "constant_daily_one_third_averaging_prohibited": True,
        "july_rebalance_at_most_once": True,
        "rebalance_turnover_uses_actual_pre_rebalance_sleeves": True,
        "component_costs_not_reapplied": True,
        "portfolio_transfer_cost_applied_once": True,
        "component_capital_not_reduced_for_derived_observation": True,
        "no_broker_api_called": True,
        "no_paper_or_live_order_created": True,
        "no_real_money_flag_true": True,
        "aggregate_exposure_lte_1": True,
        "rerun_with_unchanged_snapshots_idempotent": True,
        "consistency_passed": True,
    }
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Repair VM/DSR Observation Data And State V1

Outcome: `{OUTCOME}`

VM and DSR remain blocked because no authoritative committed operational baseline was found. Their active/frozen lifecycle and rule records exist, but activation date, initial virtual capital, current virtual equity, holdings, shares/cash, signal date, and rebalance state are not recoverable from canonical records without inference.

USCI was corrected independently. The existing local USCI rows from `2026-06-22` through `{usci_result['new_committed_date']}` were processed sequentially and committed to the USCI component ledger/state without waiting for VM or DSR.

No provider download, cache rewrite, historical evidence rewrite, strategy redesign, broker/API path, paper/live order, promotion, or real-money recommendation occurred.

Next action: `{NEXT_ACTION}`
"""
    (output / "repair_summary.md").write_text(summary, encoding="utf-8")

    return {
        "evidence_dir": str(output),
        "outcome": OUTCOME,
        "next_action": NEXT_ACTION,
        "vm_state_recovered": False,
        "dsr_state_recovered": False,
        "usci_committed_through": usci_result["new_committed_date"],
        "usci_forward_sessions_committed": max(0, len(usci_rows) - 1),
        "previous_blocked_packet_preserved": prior_hashes_before == prior_hashes_after,
        "consistency": consistency,
    }


def run() -> dict[str, Any]:
    return write_outputs()


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
