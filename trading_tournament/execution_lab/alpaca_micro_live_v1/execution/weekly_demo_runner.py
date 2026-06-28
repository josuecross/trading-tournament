from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.execution.logging_utils import utc_timestamp, write_json
from execution_lab.alpaca_micro_live_v1.execution.runtime_orchestrator import target_version_id
from execution_lab.alpaca_micro_live_v1.execution.runtime_strategy_inventory import build_inventory


WEEKLY_ROOT = MODULE_ROOT / "evidence" / "weekly_demo_sessions"
CONTROL_ROOT = MODULE_ROOT / "evidence" / "control"
STOP_FILE = CONTROL_ROOT / "STOP_WEEKLY_DEMO"
EMERGENCY_STOP_FILE = CONTROL_ROOT / "EMERGENCY_STOP_WEEKLY_DEMO"
load_alpaca_credentials = None
fetch_daily_bars = None

EVENT_FILES = [
    "heartbeat.jsonl",
    "loop_events.jsonl",
    "signals.jsonl",
    "target_versions.jsonl",
    "eligibility_snapshots.jsonl",
    "ranking_snapshots.jsonl",
    "target_weights.jsonl",
    "position_snapshots.jsonl",
    "account_snapshots.jsonl",
    "proposed_orders.jsonl",
    "skipped_orders.jsonl",
    "runtime_blocks.jsonl",
    "submitted_orders.jsonl",
    "fills.jsonl",
    "open_orders.jsonl",
    "broker_rejects.jsonl",
    "broker_errors.jsonl",
    "risk_gate_decisions.jsonl",
    "allocation_drift.jsonl",
    "performance_snapshots.jsonl",
    "execution_quality.jsonl",
    "virtual_sleeves.jsonl",
    "order_statuses.jsonl",
    "position_derived_fills.jsonl",
    "observation_gaps.jsonl",
]

DEFAULT_SHARED_FALLBACK_SYMBOLS = {"BIL"}
READ_ERROR_CATEGORIES = {"network_error", "transient_server_error", "rate_limit_error", "unknown_broker_error", "unknown_read_error"}
DEFAULT_READ_ERROR_POLICY = {
    "fail_on_single_read_error": False,
    "max_consecutive_read_errors": 5,
    "read_error_backoff_seconds": 60,
    "mark_session_degraded_after_errors": 1,
}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": utc_timestamp(), **record}, sort_keys=True, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def count_jsonl(path: Path) -> int:
    return len(read_jsonl(path))


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def create_session_dir() -> Path:
    path = WEEKLY_ROOT / f"weekly_demo_{utc_timestamp().replace(':', '').replace('-', '').replace('.', '')}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def load_state(session_dir: Path) -> dict[str, Any]:
    path = session_dir / "weekly_session_state.json"
    if not path.exists():
        return {"handled_target_versions": [], "live_orders_submitted": False, "emergency_stop": False}
    return json.loads(path.read_text(encoding="utf-8"))


def max_recorded_loop(session_dir: Path) -> int:
    loops = [int(row.get("loop", 0) or 0) for row in read_jsonl(session_dir / "heartbeat.jsonl")]
    state_loop = int(load_state(session_dir).get("loop_count", 0) or 0)
    return max([state_loop, *loops], default=0)


def resolve_runtime_ready(registry: dict[str, Any], strategies: list[str]) -> list[str]:
    rows = registry.get("strategies") or {}
    if strategies == ["all_runtime_ready"]:
        return [
            strategy_id
            for strategy_id, row in rows.items()
            if row.get("enabled") is True
            and row.get("runtime_ready") is True
            and row.get("paper_trading_allowed") is True
            and row.get("live_trading_allowed") is False
        ]
    return strategies


def runtime_spec_symbols(spec: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    universe = spec.get("universe") or {}
    for value in universe.values():
        if isinstance(value, str):
            symbols.add(value)
        elif isinstance(value, list):
            symbols.update(item for item in value if isinstance(item, str))
    fallback = (spec.get("portfolio") or {}).get("fallback")
    if isinstance(fallback, str):
        symbols.add(fallback)
    return symbols


def runtime_spec_fallback_symbols(spec: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    cash_or_fallback = (spec.get("universe") or {}).get("cash_or_fallback", [])
    if isinstance(cash_or_fallback, str):
        symbols.add(cash_or_fallback)
    elif isinstance(cash_or_fallback, list):
        symbols.update(item for item in cash_or_fallback if isinstance(item, str))
    fallback = (spec.get("portfolio") or {}).get("fallback")
    if isinstance(fallback, str):
        symbols.add(fallback)
    return symbols


def approved_symbols_for_selected_strategies(registry: dict[str, Any], strategy_ids: list[str]) -> set[str]:
    rows = registry.get("strategies") or {}
    approved: set[str] = set()
    for strategy_id in strategy_ids:
        row = rows.get(strategy_id)
        if not row:
            raise ValueError(f"Strategy is missing from runtime registry: {strategy_id}")
        registry_symbols = set(row.get("allowed_symbols") or [])
        if not registry_symbols:
            raise ValueError(f"Strategy has no approved symbols: {strategy_id}")
        spec_path = MODULE_ROOT / str(row.get("runtime_spec", ""))
        if not spec_path.exists():
            raise ValueError(f"Runtime spec is missing for {strategy_id}: {spec_path}")
        spec_symbols = runtime_spec_symbols(read_yaml(spec_path))
        if registry_symbols != spec_symbols:
            registry_only = sorted(registry_symbols - spec_symbols)
            spec_only = sorted(spec_symbols - registry_symbols)
            raise ValueError(
                f"Registry/spec symbol mismatch for {strategy_id}: "
                f"registry_only={registry_only}, spec_only={spec_only}"
            )
        approved.update(registry_symbols)
    return approved


def _shared_symbol_config(risk_limits: dict[str, Any]) -> tuple[set[str], bool, bool, str]:
    policy = risk_limits.get("shared_symbol_policy") or {}
    configured_symbols = risk_limits.get("shared_fallback_symbols")
    if configured_symbols is None:
        shared_fallback_symbols = set(DEFAULT_SHARED_FALLBACK_SYMBOLS)
        source = "runtime_default_fallback_symbols"
    else:
        shared_fallback_symbols = {symbol for symbol in configured_symbols if isinstance(symbol, str)}
        source = "risk_limits"
    allow_fallback = bool(policy.get("allow_shared_fallback_symbols", True))
    block_risk_assets = bool(policy.get("block_shared_risk_assets", True))
    return shared_fallback_symbols, allow_fallback, block_risk_assets, source


def classify_symbol_overlaps(
    registry: dict[str, Any],
    strategy_ids: list[str],
    risk_limits: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = registry.get("strategies") or {}
    owners: dict[str, list[str]] = {}
    fallback_symbols_by_strategy: dict[str, set[str]] = {}
    shared_fallback_symbols, allow_fallback, block_risk_assets, policy_source = _shared_symbol_config(risk_limits)
    for strategy_id in strategy_ids:
        row = rows.get(strategy_id)
        if not row:
            continue
        for symbol in row.get("allowed_symbols", []) or []:
            owners.setdefault(symbol, []).append(strategy_id)
        spec_path = MODULE_ROOT / str(row.get("runtime_spec", ""))
        fallback_symbols_by_strategy[strategy_id] = runtime_spec_fallback_symbols(read_yaml(spec_path))

    classifications: list[dict[str, Any]] = []
    for symbol, symbol_owners in sorted(owners.items()):
        if len(symbol_owners) < 2:
            continue
        fallback_for_all_owners = all(symbol in fallback_symbols_by_strategy.get(strategy_id, set()) for strategy_id in symbol_owners)
        if allow_fallback and symbol in shared_fallback_symbols and fallback_for_all_owners:
            classification = "allowed_shared_fallback_symbol"
            block_submit = False
        else:
            classification = "blocked_shared_risk_symbol" if block_risk_assets else "unclassified_shared_symbol"
            block_submit = block_risk_assets
        classifications.append(
            {
                "symbol": symbol,
                "strategies": symbol_owners,
                "classification": classification,
                "block_submit": block_submit,
                "shared_fallback_symbols": sorted(shared_fallback_symbols),
                "fallback_for_all_owners": fallback_for_all_owners,
                "policy_source": policy_source,
                "allocation_policy": risk_limits.get("multi_strategy_allocation_policy", "independent_virtual_sleeves"),
            }
        )
    return classifications


def validate_runtime_registry(registry: dict[str, Any], strategies: list[str]) -> list[str]:
    errors: list[str] = []
    rows = registry.get("strategies") or {}
    seen: set[str] = set()
    for strategy_id in strategies:
        if strategy_id in seen:
            errors.append(f"duplicated_strategy_id:{strategy_id}")
        seen.add(strategy_id)
        row = rows.get(strategy_id)
        if not row:
            errors.append(f"strategy_missing_from_registry:{strategy_id}")
            continue
        spec = MODULE_ROOT / str(row.get("runtime_spec", ""))
        module = MODULE_ROOT / str(row.get("runtime_module", ""))
        if not spec.exists():
            errors.append(f"missing_runtime_spec:{strategy_id}")
        if not module.exists():
            errors.append(f"missing_runtime_module:{strategy_id}")
        for symbol in row.get("allowed_symbols", []):
            if not isinstance(symbol, str) or "-" in symbol:
                errors.append(f"unsupported_symbol:{strategy_id}:{symbol}")
    return errors


def load_strategy_callable(row: dict[str, Any]):
    module_path = str(row["runtime_module"]).replace("/", ".").removesuffix(".py")
    module = importlib.import_module(f"execution_lab.alpaca_micro_live_v1.{module_path}")
    if not hasattr(module, "generate_target_from_bars"):
        raise RuntimeError(f"runtime module missing generate_target_from_bars: {module_path}")
    return module.generate_target_from_bars


def latest_prices_from_bars(bars: dict[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for symbol, frame in bars.items():
        if frame is not None and not frame.empty:
            prices[symbol] = float(frame.sort_values("date")["close"].iloc[-1])
    return prices


def write_empty_event_files(session_dir: Path) -> None:
    for name in EVENT_FILES:
        (session_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (session_dir / name).touch(exist_ok=True)


def latest_snapshot_timestamp(session_dir: Path, filename: str) -> str | None:
    rows = read_jsonl(session_dir / filename)
    return rows[-1].get("timestamp") if rows else None


def refresh_session_counts(session_dir: Path, state: dict[str, Any]) -> None:
    state["submitted_orders"] = count_jsonl(session_dir / "submitted_orders.jsonl")
    state["fills"] = count_jsonl(session_dir / "fills.jsonl")
    state["position_derived_fills"] = count_jsonl(session_dir / "position_derived_fills.jsonl")
    state["broker_errors"] = count_jsonl(session_dir / "broker_errors.jsonl")
    state["skipped_orders"] = count_jsonl(session_dir / "skipped_orders.jsonl")
    state["runtime_blocks"] = count_jsonl(session_dir / "runtime_blocks.jsonl")


def write_session_state_and_summaries(session_dir: Path, state: dict[str, Any]) -> None:
    refresh_session_counts(session_dir, state)
    write_json(session_dir / "weekly_session_state.json", state)
    write_summaries(session_dir, state, stopped=state.get("status") in {"stopped", "emergency_stopped"})


def read_error_policy(risk_limits: dict[str, Any]) -> dict[str, Any]:
    configured = risk_limits.get("weekly_runner_read_error_policy") or {}
    return {**DEFAULT_READ_ERROR_POLICY, **configured}


def is_read_only_error(exc: Exception) -> bool:
    category = getattr(exc, "category", "unknown_read_error")
    return category in READ_ERROR_CATEGORIES


def unresolved_order_submit_ambiguity(session_dir: Path) -> bool:
    for row in read_jsonl(session_dir / "broker_errors.jsonl"):
        if row.get("ambiguous_submission") is True:
            return True
    return False


def read_only_safe_failure(state: dict[str, Any]) -> bool:
    return (
        state.get("status") == "failed"
        and bool(state.get("last_read_error_operation"))
        and int(state.get("submitted_orders", 0) or 0) == 0
        and int(state.get("open_orders", 0) or 0) == 0
        and state.get("live_orders_submitted") is False
    )


def resume_allowed(session_dir: Path, state: dict[str, Any]) -> bool:
    return not unresolved_order_submit_ambiguity(session_dir) and (
        state.get("status") != "failed" or read_only_safe_failure(state)
    )


def record_read_only_failure(
    session_dir: Path,
    state: dict[str, Any],
    *,
    operation: str,
    exc: Exception,
    risk_limits: dict[str, Any],
    paper_orders_submitted_this_loop: int = 0,
) -> bool:
    policy = read_error_policy(risk_limits)
    category = getattr(exc, "category", "unknown_read_error")
    if category not in READ_ERROR_CATEGORIES:
        category = "unknown_read_error"
    consecutive = int(state.get("consecutive_read_errors", 0) or 0) + 1
    threshold = int(policy.get("max_consecutive_read_errors", 5))
    fail_now = bool(policy.get("fail_on_single_read_error", False)) or consecutive >= threshold
    status = "failed" if fail_now else "degraded_running"
    now = utc_timestamp()
    state["consecutive_read_errors"] = consecutive
    state["last_read_error_operation"] = operation
    state["last_read_error_utc"] = now
    state.setdefault("degraded_since_utc", now)
    state["status"] = status
    append_jsonl(
        session_dir / "broker_errors.jsonl",
        {
            "category": category,
            "operation": operation,
            "safe_to_continue": not fail_now,
            "consecutive_read_errors": consecutive,
            "session_status_after_error": status,
            "message": str(exc),
        },
    )
    append_jsonl(
        session_dir / "runtime_blocks.jsonl",
        {
            "block_reason": "read_only_operation_failed_skip_loop",
            "operation": operation,
            "safe_to_continue": not fail_now,
            "paper_orders_submitted_this_loop": paper_orders_submitted_this_loop,
            "live_orders_submitted": False,
        },
    )
    write_session_state_and_summaries(session_dir, state)
    return fail_now


def mark_read_success(state: dict[str, Any]) -> None:
    state["consecutive_read_errors"] = 0
    state["last_read_error_operation"] = None
    state["last_read_error_utc"] = None
    state["degraded_since_utc"] = None


def write_summaries(session_dir: Path, state: dict[str, Any], *, stopped: bool = False) -> None:
    today = datetime.now().date().isoformat()
    daily = {
        "date": today,
        "session_id": session_dir.name,
        "status": state.get("status"),
        "signals": state.get("signals", 0),
        "submitted_orders": state.get("submitted_orders", 0),
        "fills": state.get("fills", 0),
        "position_derived_fills": state.get("position_derived_fills", 0),
        "broker_errors": state.get("broker_errors", 0),
        "runtime_blocks": state.get("runtime_blocks", 0),
        "consecutive_read_errors": state.get("consecutive_read_errors", 0),
        "last_read_error_operation": state.get("last_read_error_operation"),
        "last_read_error_utc": state.get("last_read_error_utc"),
        "degraded_since_utc": state.get("degraded_since_utc"),
        "live_orders_submitted": False,
        "stopped": stopped,
        "overlap_classifications": state.get("overlap_classifications", []),
    }
    weekly = {
        "session_id": session_dir.name,
        "status": state.get("status"),
        "active": state.get("status") in {"running", "degraded_running"},
        "last_heartbeat_utc": state.get("last_heartbeat_utc"),
        "loop_count": state.get("loop_count", 0),
        "selected_strategies": state.get("selected_strategies", []),
        "handled_target_versions": state.get("handled_target_versions", []),
        "latest_target_versions": state.get("latest_target_versions", []),
        "submitted_orders": state.get("submitted_orders", 0),
        "fills": state.get("fills", 0),
        "position_derived_fills": state.get("position_derived_fills", 0),
        "open_orders": state.get("open_orders", 0),
        "broker_errors": state.get("broker_errors", 0),
        "skipped_orders": state.get("skipped_orders", 0),
        "runtime_blocks": state.get("runtime_blocks", 0),
        "consecutive_read_errors": state.get("consecutive_read_errors", 0),
        "last_read_error_operation": state.get("last_read_error_operation"),
        "last_read_error_utc": state.get("last_read_error_utc"),
        "degraded_since_utc": state.get("degraded_since_utc"),
        "skipped_loops": state.get("skipped_loops", 0),
        "paper_pnl": state.get("paper_pnl", 0.0),
        "drawdown_estimate": state.get("drawdown_estimate", 0.0),
        "live_orders_submitted": False,
        "stopped": stopped,
        "overlap_classifications": state.get("overlap_classifications", []),
        "latest_account_snapshot_utc": latest_snapshot_timestamp(session_dir, "account_snapshots.jsonl"),
        "latest_position_snapshot_utc": latest_snapshot_timestamp(session_dir, "position_snapshots.jsonl"),
    }
    write_json(session_dir / f"daily_summary_{today}.json", daily)
    (session_dir / f"daily_summary_{today}.md").write_text(
        f"# Daily Summary {today}\n\n- submitted_orders: {daily['submitted_orders']}\n- live_orders_submitted: false\n",
        encoding="utf-8",
    )
    write_json(session_dir / "weekly_summary.json", weekly)
    (session_dir / "weekly_summary.md").write_text(
        "\n".join(
            [
                "# Weekly Summary",
                "",
                f"- session_id: {session_dir.name}",
                f"- status: {weekly['status']}",
                f"- active: {str(weekly['active']).lower()}",
                f"- last_heartbeat_utc: {weekly['last_heartbeat_utc']}",
                f"- loop_count: {weekly['loop_count']}",
                f"- selected_strategies: {', '.join(weekly['selected_strategies'])}",
                f"- latest_target_versions: {', '.join(weekly['latest_target_versions']) if weekly['latest_target_versions'] else 'none'}",
                f"- submitted_orders: {weekly['submitted_orders']}",
                f"- fills: {weekly['fills']}",
                f"- position_derived_fills: {weekly['position_derived_fills']}",
                f"- open_orders: {weekly['open_orders']}",
                f"- broker_errors: {weekly['broker_errors']}",
                f"- consecutive_read_errors: {weekly['consecutive_read_errors']}",
                f"- last_read_error_operation: {weekly['last_read_error_operation']}",
                f"- last_read_error_utc: {weekly['last_read_error_utc']}",
                f"- degraded_since_utc: {weekly['degraded_since_utc']}",
                f"- skipped_orders: {weekly['skipped_orders']}",
                f"- runtime_blocks: {weekly['runtime_blocks']}",
                "- live_orders_submitted: false",
                f"- latest_account_snapshot_utc: {weekly['latest_account_snapshot_utc']}",
                f"- latest_position_snapshot_utc: {weekly['latest_position_snapshot_utc']}",
                "- overlap_classifications:",
                *[
                    f"  - {item.get('symbol')}: {item.get('classification')} ({', '.join(item.get('strategies', []))})"
                    for item in weekly["overlap_classifications"]
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )


def account_position_for_symbol(positions: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    for position in positions:
        if position.get("symbol") == symbol:
            return position
    return {}


def record_virtual_sleeve(
    session_dir: Path,
    *,
    strategy_id: str,
    target_version_id: str,
    row: dict[str, Any],
    target_weights: dict[str, float],
    positions: list[dict[str, Any]],
    proposed_orders: list[Any],
) -> None:
    deltas = {order.symbol: {"side": order.side, "notional": order.notional, "qty": order.qty} for order in proposed_orders}
    symbols = sorted(set(target_weights) | set(deltas))
    for symbol in symbols:
        account_position = account_position_for_symbol(positions, symbol)
        position_value = account_position.get("market_value") or account_position.get("notional") or "0"
        attribution = "unattributed_existing_position" if account_position else "no_existing_position"
        append_jsonl(
            session_dir / "virtual_sleeves.jsonl",
            {
                "strategy_id": strategy_id,
                "target_version_id": target_version_id,
                "capital_sleeve_notional": row.get("capital_sleeve_notional"),
                "symbol": symbol,
                "target_weight": target_weights.get(symbol, 0.0),
                "virtual_target_notional": float(row.get("capital_sleeve_notional", 0.0) or 0.0) * float(target_weights.get(symbol, 0.0)),
                "current_account_position": account_position,
                "current_account_position_value": position_value,
                "virtual_strategy_owned_estimate": 0.0,
                "position_attribution": attribution,
                "proposed_delta": deltas.get(symbol, {"side": "none", "notional": 0.0, "qty": None}),
            },
        )


def _order_identity(row: dict[str, Any]) -> str:
    return str(row.get("broker_order_id") or row.get("id") or row.get("client_order_id") or "")


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _submitted_orders(session_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(session_dir / "submitted_orders.jsonl")


def _filled_order_ids(session_dir: Path) -> set[str]:
    return {_order_identity(row) for row in read_jsonl(session_dir / "fills.jsonl") if _order_identity(row)}


def _derived_fill_keys(session_dir: Path) -> set[tuple[str, str, str]]:
    return {
        (str(row.get("strategy_id")), str(row.get("target_version_id")), str(row.get("symbol")))
        for row in read_jsonl(session_dir / "position_derived_fills.jsonl")
    }


def reconcile_order_statuses(session_dir: Path, client: Any, state: dict[str, Any], risk_limits: dict[str, Any]) -> bool:
    filled_ids = _filled_order_ids(session_dir)
    for submitted in _submitted_orders(session_dir):
        broker_order_id = submitted.get("broker_order_id") or submitted.get("id")
        if not broker_order_id or not hasattr(client, "get_order_by_id"):
            continue
        try:
            status = client.get_order_by_id(str(broker_order_id))
        except Exception as exc:
            if record_read_only_failure(session_dir, state, operation="order_status", exc=exc, risk_limits=risk_limits):
                return True
            continue
        status_record = {
            "strategy_id": submitted.get("strategy_id"),
            "target_version_id": submitted.get("target_version_id"),
            "symbol": submitted.get("symbol") or status.get("symbol"),
            "client_order_id": submitted.get("client_order_id") or status.get("client_order_id"),
            "broker_order_id": broker_order_id,
            "status": status.get("status"),
            "submitted_at": submitted.get("submitted_at") or status.get("submitted_at"),
            "filled_at": status.get("filled_at"),
            "filled_qty": status.get("filled_qty"),
            "filled_avg_price": status.get("filled_avg_price"),
        }
        append_jsonl(session_dir / "order_statuses.jsonl", status_record)
        if status.get("status") == "filled" and str(broker_order_id) not in filled_ids:
            submitted_at = parse_utc(status_record.get("submitted_at"))
            filled_at = parse_utc(status_record.get("filled_at"))
            latency = (filled_at - submitted_at).total_seconds() if submitted_at and filled_at else None
            append_jsonl(
                session_dir / "fills.jsonl",
                {
                    **status_record,
                    "fill_latency_seconds": latency,
                    "broker_confirmed": True,
                    "derived_from_position_snapshot": False,
                },
            )
            filled_ids.add(str(broker_order_id))
    return False


def reconcile_position_derived_fills(session_dir: Path, positions: list[dict[str, Any]], open_orders: list[dict[str, Any]]) -> None:
    open_symbols = {str(order.get("symbol")) for order in open_orders}
    broker_error_order_ids = {
        str(row.get("client_order_id") or row.get("broker_order_id") or row.get("id"))
        for row in read_jsonl(session_dir / "broker_errors.jsonl")
    }
    filled_ids = _filled_order_ids(session_dir)
    derived_keys = _derived_fill_keys(session_dir)
    positions_by_symbol = {str(position.get("symbol")): position for position in positions}
    for submitted in _submitted_orders(session_dir):
        symbol = str(submitted.get("symbol"))
        key = (str(submitted.get("strategy_id")), str(submitted.get("target_version_id")), symbol)
        order_identity = _order_identity(submitted)
        if key in derived_keys or order_identity in filled_ids or submitted.get("client_order_id") in broker_error_order_ids:
            continue
        if symbol in open_symbols:
            continue
        position = positions_by_symbol.get(symbol)
        if not position:
            continue
        if _float(position.get("qty")) <= 0 and _float(position.get("market_value")) <= 0:
            continue
        append_jsonl(
            session_dir / "position_derived_fills.jsonl",
            {
                "strategy_id": submitted.get("strategy_id"),
                "target_version_id": submitted.get("target_version_id"),
                "symbol": symbol,
                "client_order_id": submitted.get("client_order_id"),
                "broker_order_id": submitted.get("broker_order_id") or submitted.get("id"),
                "position_qty": position.get("qty"),
                "position_market_value": position.get("market_value"),
                "broker_confirmed": False,
                "derived_from_position_snapshot": True,
                "reason": "derived_from_position_snapshot",
            },
        )
        derived_keys.add(key)


def record_observation_gap(
    session_dir: Path,
    *,
    previous_heartbeat_utc: str | None,
    current_heartbeat_utc: str,
    interval_seconds: int,
) -> None:
    previous = parse_utc(previous_heartbeat_utc)
    current = parse_utc(current_heartbeat_utc)
    if not previous or not current or interval_seconds <= 0:
        return
    actual_gap = (current - previous).total_seconds()
    if actual_gap > interval_seconds * 2:
        append_jsonl(
            session_dir / "observation_gaps.jsonl",
            {
                "previous_heartbeat_utc": previous_heartbeat_utc,
                "current_heartbeat_utc": current_heartbeat_utc,
                "expected_interval_seconds": interval_seconds,
                "actual_gap_seconds": actual_gap,
                "likely_reason": "pc_sleep_or_process_pause_or_network_delay",
                "live_orders_submitted": False,
            },
        )


def run_weekly_demo(
    *,
    config_path: Path,
    risk_limits_path: Path,
    runtime_registry_path: Path,
    strategies: list[str],
    mode: str = "paper",
    interval_seconds: int = 300,
    duration_days: int = 7,
    run_until: str | None = None,
    max_loops: int | None = None,
    resume: Path | None = None,
    submit_paper_orders: bool = False,
    dry_run: bool = True,
    client: Any | None = None,
    bars_fetcher: Any | None = None,
    credentials_loader: Any | None = None,
) -> dict[str, Any]:
    from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
    from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials as imported_credentials
    from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import fetch_daily_bars as imported_fetch_bars
    from execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError
    from execution_lab.alpaca_micro_live_v1.execution.order_sizing import build_delta_orders
    from execution_lab.alpaca_micro_live_v1.execution.risk_gate import evaluate_risk_gate

    if mode != "paper":
        raise ValueError("Live mode is unsupported.")
    if submit_paper_orders and dry_run:
        dry_run = False
    if resume and ("<" in str(resume) or ">" in str(resume)):
        raise ValueError("resume_path_contains_placeholder_timestamp")
    credential_fn = credentials_loader or load_alpaca_credentials or imported_credentials
    fetch_fn = bars_fetcher or fetch_daily_bars or imported_fetch_bars
    config = read_yaml(config_path)
    risk_limits = read_yaml(risk_limits_path)
    registry = read_yaml(runtime_registry_path)
    selected = resolve_runtime_ready(registry, strategies)
    if run_until:
        until = datetime.fromisoformat(run_until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
    else:
        until = datetime.now(timezone.utc) + timedelta(days=duration_days)
    session_dir = resume or create_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    write_empty_event_files(session_dir)
    state = load_state(session_dir)
    state.setdefault("session_id", session_dir.name)
    state.setdefault("started_at_utc", utc_timestamp())
    state["planned_end_at_utc"] = iso_utc(until)
    state["selected_strategies"] = selected
    state["submit_paper_orders"] = submit_paper_orders
    state.setdefault("status", "running")
    state.setdefault("handled_target_versions", [])
    state.setdefault("submitted_client_order_ids", [])
    state.setdefault("submitted_orders", 0)
    state.setdefault("fills", 0)
    state.setdefault("position_derived_fills", 0)
    state.setdefault("open_orders", 0)
    state.setdefault("signals", 0)
    state.setdefault("broker_errors", 0)
    state.setdefault("skipped_orders", 0)
    state.setdefault("runtime_blocks", 0)
    state.setdefault("skipped_loops", 0)
    state.setdefault("latest_target_versions", [])
    state.setdefault("latest_market_clock_open", None)
    state.setdefault("consecutive_read_errors", 0)
    state.setdefault("last_read_error_operation", None)
    state.setdefault("last_read_error_utc", None)
    state.setdefault("degraded_since_utc", None)
    state.setdefault("last_loop_duration_seconds", None)
    state.setdefault("next_loop_at_utc", None)
    state["loop_count"] = max_recorded_loop(session_dir)
    state.setdefault("overlap_classifications", [])
    state["live_orders_submitted"] = False

    if resume and unresolved_order_submit_ambiguity(session_dir):
        state["status"] = "failed"
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": "resume_blocked_unresolved_order_submit_ambiguity"})
        write_session_state_and_summaries(session_dir, state)
        return {
            "session_dir": str(session_dir),
            "runtime_blocked": True,
            "block_reasons": ["resume_blocked_unresolved_order_submit_ambiguity"],
            "submitted_orders": state["submitted_orders"],
            "live_orders_submitted": False,
            "message": "resume_blocked_unresolved_order_submit_ambiguity",
        }
    if resume and not resume_allowed(session_dir, state):
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": "resume_blocked_failed_session_not_read_only_safe"})
        write_session_state_and_summaries(session_dir, state)
        return {
            "session_dir": str(session_dir),
            "runtime_blocked": True,
            "block_reasons": ["resume_blocked_failed_session_not_read_only_safe"],
            "submitted_orders": state["submitted_orders"],
            "live_orders_submitted": False,
            "message": "resume_blocked_failed_session_not_read_only_safe",
        }

    inventory = build_inventory()
    write_json(session_dir / "runtime_strategy_inventory.json", inventory)
    write_json(
        session_dir / "weekly_session_config.yaml",
        {
            "session_id": session_dir.name,
            "git_commit_hash": "unavailable",
            "python_version": sys.version,
            "platform": platform.platform(),
            "config_hash": file_hash(config_path),
            "risk_limits_hash": file_hash(risk_limits_path),
            "registry_hash": file_hash(runtime_registry_path),
            "strategies": selected,
            "dry_run": dry_run,
            "submit_paper_orders": submit_paper_orders,
            "live_orders_submitted": False,
        },
    )

    if resume and STOP_FILE.exists():
        state["status"] = "stopped"
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": "resume_blocked_stop_file_present"})
        write_session_state_and_summaries(session_dir, state)
        return {
            "session_dir": str(session_dir),
            "runtime_blocked": True,
            "block_reasons": ["resume_blocked_stop_file_present"],
            "submitted_orders": state["submitted_orders"],
            "live_orders_submitted": False,
            "message": "resume_blocked_stop_file_present",
        }

    validation_errors = validate_runtime_registry(registry, selected)
    if validation_errors and submit_paper_orders:
        for error in validation_errors:
            append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": error})
        state["skipped_loops"] += 1
        state["status"] = "failed"
        write_session_state_and_summaries(session_dir, state)
        return {"session_dir": str(session_dir), "runtime_blocked": True, "block_reasons": validation_errors, "submitted_orders": 0, "live_orders_submitted": False}
    for error in validation_errors:
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": error, "dry_run_allowed": True})
    try:
        approved_symbols = approved_symbols_for_selected_strategies(registry, selected)
    except ValueError as exc:
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": str(exc)})
        state["skipped_loops"] += 1
        state["status"] = "failed"
        write_session_state_and_summaries(session_dir, state)
        return {"session_dir": str(session_dir), "runtime_blocked": True, "block_reasons": [str(exc)], "submitted_orders": 0, "live_orders_submitted": False}
    overlap_classifications = classify_symbol_overlaps(registry, selected, risk_limits)
    state["overlap_classifications"] = overlap_classifications
    blocked_overlaps = [item for item in overlap_classifications if item.get("block_submit")]
    for item in overlap_classifications:
        append_jsonl(session_dir / "runtime_blocks.jsonl", {"event": "symbol_overlap_classification", **item})
    if blocked_overlaps and submit_paper_orders:
        reasons = [f"{item['classification']}:{item['symbol']}:{':'.join(item['strategies'])}" for item in blocked_overlaps]
        for reason in reasons:
            append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": reason})
        state["skipped_loops"] += 1
        state["status"] = "failed"
        write_session_state_and_summaries(session_dir, state)
        return {"session_dir": str(session_dir), "runtime_blocked": True, "block_reasons": reasons, "submitted_orders": 0, "live_orders_submitted": False}

    credentials = credential_fn("paper")
    client = client or AlpacaClient(
        credentials,
        AlpacaClientConfig(
            paper_base_url=config.get("paper_base_url", "https://paper-api.alpaca.markets"),
            data_base_url=config.get("data_base_url", "https://data.alpaca.markets"),
            data_feed=config.get("data_feed", "iex"),
            data_adjustment=config.get("data_adjustment", "all"),
        ),
    )

    loop_count = int(state.get("loop_count", 0) or 0)
    write_session_state_and_summaries(session_dir, state)
    while (max_loops is None or loop_count < max_loops) and datetime.now(timezone.utc) <= until.astimezone(timezone.utc):
        loop_started = datetime.now(timezone.utc)
        previous_heartbeat = state.get("last_heartbeat_utc")
        heartbeat = iso_utc(loop_started)
        record_observation_gap(
            session_dir,
            previous_heartbeat_utc=previous_heartbeat,
            current_heartbeat_utc=heartbeat,
            interval_seconds=interval_seconds,
        )
        loop_count += 1
        state["status"] = "running"
        state["loop_count"] = loop_count
        state["last_heartbeat_utc"] = heartbeat
        state["next_loop_at_utc"] = iso_utc(loop_started + timedelta(seconds=interval_seconds)) if interval_seconds > 0 else None
        append_jsonl(session_dir / "heartbeat.jsonl", {"loop": loop_count, "live_orders_submitted": False})
        append_jsonl(session_dir / "loop_events.jsonl", {"event": "loop_start", "loop": loop_count})
        write_session_state_and_summaries(session_dir, state)
        read_error_this_loop = False
        if EMERGENCY_STOP_FILE.exists():
            state["emergency_stop"] = True
            state["status"] = "emergency_stopped"
            append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": "emergency_stop_file_present"})
            write_session_state_and_summaries(session_dir, state)
            break
        if STOP_FILE.exists():
            state["status"] = "stopped"
            append_jsonl(session_dir / "runtime_blocks.jsonl", {"block_reason": "stop_file_present"})
            write_session_state_and_summaries(session_dir, state)
            break
        skip_loop = False
        for operation, read_call in [
            ("market_clock", client.get_market_clock),
            ("account_snapshot", client.get_account),
            ("positions", client.get_positions),
            ("open_orders", client.list_open_orders),
        ]:
            try:
                value = read_call()
            except Exception as exc:
                read_error_this_loop = True
                failed = record_read_only_failure(session_dir, state, operation=operation, exc=exc, risk_limits=risk_limits)
                state["last_loop_duration_seconds"] = round((datetime.now(timezone.utc) - loop_started).total_seconds(), 3)
                state["next_loop_at_utc"] = None if failed else state.get("next_loop_at_utc")
                write_session_state_and_summaries(session_dir, state)
                if failed:
                    break
                skip_loop = True
                break
            if operation == "market_clock":
                clock = value
            elif operation == "account_snapshot":
                account = value
            elif operation == "positions":
                positions = value
            else:
                open_orders = value
        if state.get("status") == "failed":
            break
        if skip_loop:
            if interval_seconds > 0 and (max_loops is None or loop_count < max_loops):
                time.sleep(interval_seconds)
            continue
        if reconcile_order_statuses(session_dir, client, state, risk_limits):
            break
        if state.get("status") == "degraded_running" and state.get("last_read_error_operation") == "order_status":
            read_error_this_loop = True
            state["last_loop_duration_seconds"] = round((datetime.now(timezone.utc) - loop_started).total_seconds(), 3)
            write_session_state_and_summaries(session_dir, state)
            if interval_seconds > 0 and (max_loops is None or loop_count < max_loops):
                time.sleep(interval_seconds)
            continue
        reconcile_position_derived_fills(session_dir, positions, open_orders)
        state["latest_market_clock_open"] = bool(clock.get("is_open")) if isinstance(clock, dict) else None
        state["open_orders"] = len(open_orders)
        append_jsonl(session_dir / "account_snapshots.jsonl", {"account": account})
        append_jsonl(session_dir / "position_snapshots.jsonl", {"positions": positions})
        append_jsonl(session_dir / "open_orders.jsonl", {"open_orders": open_orders})
        state["latest_target_versions"] = []
        for strategy_id in selected:
            row = (registry.get("strategies") or {})[strategy_id]
            spec_path = MODULE_ROOT / row["runtime_spec"]
            spec = read_yaml(spec_path)
            symbols = list(row.get("allowed_symbols", []))
            try:
                bars = fetch_fn(
                    client,
                    symbols=symbols,
                    approved_symbols=approved_symbols,
                    start=(datetime.now().date() - timedelta(days=420)).isoformat(),
                )
            except Exception as exc:
                read_error_this_loop = True
                failed = record_read_only_failure(
                    session_dir,
                    state,
                    operation="historical_data",
                    exc=exc,
                    risk_limits=risk_limits,
                )
                append_jsonl(
                    session_dir / "runtime_blocks.jsonl",
                    {
                        "strategy_id": strategy_id,
                        "block_reason": "historical_data_failed_skip_strategy",
                        "safe_to_continue": not failed,
                        "live_orders_submitted": False,
                    },
                )
                if failed:
                    break
                continue
            target = load_strategy_callable(row)(bars, spec)
            version = target_version_id(strategy_id, target["as_of"], target["target_weights"])
            state["latest_target_versions"].append(version)
            state["signals"] += 1
            append_jsonl(session_dir / "signals.jsonl", target)
            append_jsonl(session_dir / "target_versions.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "target_weights_hash": hashlib.sha256(json.dumps(target["target_weights"], sort_keys=True).encode()).hexdigest()})
            append_jsonl(session_dir / "eligibility_snapshots.jsonl", {"strategy_id": strategy_id, "eligibility": target.get("metadata", {}).get("eligibility", [])})
            append_jsonl(session_dir / "ranking_snapshots.jsonl", {"strategy_id": strategy_id, "ranking": target.get("metadata", {}).get("ranking", [])})
            append_jsonl(session_dir / "target_weights.jsonl", {"strategy_id": strategy_id, "target_weights": target["target_weights"]})
            if version in state["handled_target_versions"]:
                append_jsonl(session_dir / "runtime_blocks.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "block_reason": "target_version_already_handled"})
                continue
            proposed, skipped = build_delta_orders(
                target_weights=target["target_weights"],
                account=account,
                positions=positions,
                latest_prices=latest_prices_from_bars(bars),
                risk_limits={**risk_limits, "capital_sleeve_notional": row.get("capital_sleeve_notional", risk_limits.get("capital_sleeve_notional", 25.0))},
            )
            for skip in skipped:
                append_jsonl(session_dir / "skipped_orders.jsonl", {"strategy_id": strategy_id, "target_version_id": version, **skip})
            for order in proposed:
                target_hash = hashlib.sha1(version.encode()).hexdigest()[:12]
                timestamp_token = utc_timestamp().replace("-", "").replace(":", "").replace(".", "").replace("Z", "")[-14:]
                order.client_order_id = f"alpaca_{strategy_id}_{target_hash}_{order.symbol}_{timestamp_token}"
                append_jsonl(session_dir / "proposed_orders.jsonl", {"strategy_id": strategy_id, "target_version_id": version, **order.__dict__})
            if not proposed:
                append_jsonl(session_dir / "skipped_orders.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "reason": "no_actionable_delta"})
            record_virtual_sleeve(
                session_dir,
                strategy_id=strategy_id,
                target_version_id=version,
                row=row,
                target_weights=target["target_weights"],
                positions=positions,
                proposed_orders=proposed,
            )
            gate = evaluate_risk_gate(
                mode=mode,
                submit_requested=submit_paper_orders,
                credentials=credentials,
                strategy_id=strategy_id,
                strategy_registry=registry,
                risk_limits=risk_limits,
                market_clock=clock,
                account=account,
                open_orders=open_orders,
                proposed_orders=proposed,
                assets={symbol: {"symbol": symbol, "tradable": True, "fractionable": True} for symbol in symbols},
                target_version_already_handled=False,
                emergency_stop=state.get("emergency_stop", False),
            )
            append_jsonl(session_dir / "risk_gate_decisions.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "allowed": gate.allowed, "errors": gate.errors, "warnings": gate.warnings})
            append_jsonl(
                session_dir / "allocation_drift.jsonl",
                {
                    "strategy_id": strategy_id,
                    "target_version_id": version,
                    "capital_sleeve_notional": row.get("capital_sleeve_notional"),
                    "virtual_sleeve_accounting": True,
                    "drift": [
                        {
                            "symbol": symbol,
                            "target_weight": weight,
                            "position_attribution": "unattributed_existing_position" if account_position_for_symbol(positions, symbol) else "no_existing_position",
                        }
                        for symbol, weight in sorted(target["target_weights"].items())
                    ],
                },
            )
            append_jsonl(session_dir / "performance_snapshots.jsonl", {"strategy_id": strategy_id, "beginning_equity": account.get("equity"), "ending_equity": account.get("equity"), "paper_pnl": 0.0, "drawdown_estimate": 0.0})
            if dry_run or not submit_paper_orders:
                state["handled_target_versions"].append(version)
                write_session_state_and_summaries(session_dir, state)
                continue
            if not gate.allowed:
                reason = "market_closed_submit_blocked" if "market_not_open" in gate.errors else "risk_gate_blocked"
                append_jsonl(session_dir / "runtime_blocks.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "block_reason": reason, "errors": gate.errors})
                continue
            for order in proposed:
                try:
                    submitted = client.submit_order(symbol=order.symbol, side=order.side, notional=order.notional if order.side == "buy" else None, qty=order.qty if order.side == "sell" else None, client_order_id=order.client_order_id)
                except BrokerError as exc:
                    state["broker_errors"] += 1
                    if exc.ambiguous_submission:
                        state["status"] = "failed"
                    append_jsonl(session_dir / "broker_errors.jsonl", {"strategy_id": strategy_id, "category": exc.category, "ambiguous_submission": exc.ambiguous_submission, "client_order_id": exc.client_order_id, "submission_attempt_id": exc.submission_attempt_id})
                    append_jsonl(session_dir / "broker_rejects.jsonl", {"strategy_id": strategy_id, "reason": "broker_submit_failed"})
                    break
                submitted_record = {
                    "strategy_id": strategy_id,
                    "target_version_id": version,
                    "client_order_id": order.client_order_id,
                    "broker_order_id": submitted.get("id"),
                    "symbol": order.symbol,
                    "side": order.side,
                    "notional": order.notional,
                    "qty": order.qty,
                    "submitted_at": submitted.get("submitted_at"),
                    **submitted,
                }
                append_jsonl(session_dir / "submitted_orders.jsonl", submitted_record)
                state["submitted_client_order_ids"].append(order.client_order_id)
                append_jsonl(session_dir / "execution_quality.jsonl", {"strategy_id": strategy_id, "target_version_id": version, "reject_count": 0, "open_order_count": len(open_orders), "broker_error_count": state["broker_errors"], "ambiguous_submit_count": 0})
            if state.get("status") == "failed":
                write_session_state_and_summaries(session_dir, state)
                break
            state["handled_target_versions"].append(version)
            write_session_state_and_summaries(session_dir, state)
        if state.get("status") == "failed":
            break
        if not read_error_this_loop:
            mark_read_success(state)
        state["last_loop_duration_seconds"] = round((datetime.now(timezone.utc) - loop_started).total_seconds(), 3)
        if read_error_this_loop:
            state["next_loop_at_utc"] = None if max_loops is not None and loop_count >= max_loops else state.get("next_loop_at_utc")
        elif max_loops is not None and loop_count >= max_loops:
            state["status"] = "completed"
            state["next_loop_at_utc"] = None
        elif datetime.now(timezone.utc) > until.astimezone(timezone.utc):
            state["status"] = "completed"
            state["next_loop_at_utc"] = None
        else:
            state["status"] = "running"
        write_session_state_and_summaries(session_dir, state)
        if interval_seconds > 0 and (max_loops is None or loop_count < max_loops):
            time.sleep(interval_seconds)

    if state.get("status") == "running":
        state["status"] = "completed"
    write_session_state_and_summaries(session_dir, state)
    return {"session_dir": str(session_dir), "runtime_blocked": False, "submitted_orders": state["submitted_orders"], "loops": loop_count, "live_orders_submitted": False}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a weekly Alpaca paper/demo session.")
    parser.add_argument("--config", type=Path, default=MODULE_ROOT / "config" / "alpaca_paper.local.yaml")
    parser.add_argument("--risk-limits", type=Path, default=MODULE_ROOT / "config" / "risk_limits.local.yaml")
    parser.add_argument("--runtime-registry", type=Path, default=MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml")
    parser.add_argument("--strategies", nargs="+", default=["all_runtime_ready"])
    parser.add_argument("--mode", default="paper", choices=["paper"])
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--duration-days", type=int, default=7)
    parser.add_argument("--run-until")
    parser.add_argument("--max-loops", type=int)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--submit-paper-orders", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_weekly_demo(
            config_path=args.config,
            risk_limits_path=args.risk_limits,
            runtime_registry_path=args.runtime_registry,
            strategies=args.strategies,
            mode=args.mode,
            interval_seconds=args.interval_seconds,
            duration_days=args.duration_days,
            run_until=args.run_until,
            max_loops=args.max_loops,
            resume=args.resume,
            submit_paper_orders=args.submit_paper_orders,
            dry_run=not args.submit_paper_orders,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    if result.get("message"):
        print(result["message"])
    print(f"weekly_session_dir={result['session_dir']}")
    print(f"submitted_orders={result['submitted_orders']}")
    print("live_orders_submitted=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
