from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1.execution.weekly_demo_runner import (
    WEEKLY_ROOT,
    count_jsonl,
    read_only_safe_failure,
    resume_allowed,
    unresolved_order_submit_ambiguity,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_session_dir() -> Path:
    candidates = [path for path in WEEKLY_ROOT.glob("weekly_demo_*") if path.is_dir()]
    if not candidates:
        raise ValueError("no_weekly_sessions_found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def inspect_session(session_dir: Path) -> dict[str, Any]:
    state = read_json(session_dir / "weekly_session_state.json")
    summary = read_json(session_dir / "weekly_summary.json")
    latest_target_versions = state.get("latest_target_versions") or summary.get("latest_target_versions") or []
    unresolved_ambiguity = unresolved_order_submit_ambiguity(session_dir)
    return {
        "session_id": state.get("session_id") or summary.get("session_id") or session_dir.name,
        "status": state.get("status") or summary.get("status") or "unknown",
        "session_path": str(session_dir),
        "last_heartbeat": state.get("last_heartbeat_utc") or summary.get("last_heartbeat_utc"),
        "consecutive_read_errors": state.get("consecutive_read_errors", 0),
        "last_read_error_operation": state.get("last_read_error_operation"),
        "last_read_error_utc": state.get("last_read_error_utc"),
        "resume_allowed": resume_allowed(session_dir, state),
        "read_only_safe_failure": read_only_safe_failure(state),
        "unresolved_order_submit_ambiguity": unresolved_ambiguity,
        "loop_count": state.get("loop_count") or summary.get("loop_count") or 0,
        "selected_strategies": state.get("selected_strategies") or summary.get("selected_strategies") or [],
        "submitted_orders": state.get("submitted_orders", count_jsonl(session_dir / "submitted_orders.jsonl")),
        "fills": state.get("fills", count_jsonl(session_dir / "fills.jsonl")),
        "position_derived_fills": state.get("position_derived_fills", count_jsonl(session_dir / "position_derived_fills.jsonl")),
        "open_orders": state.get("open_orders", 0),
        "broker_errors": state.get("broker_errors", count_jsonl(session_dir / "broker_errors.jsonl")),
        "runtime_blocks": state.get("runtime_blocks", count_jsonl(session_dir / "runtime_blocks.jsonl")),
        "skipped_orders": state.get("skipped_orders", count_jsonl(session_dir / "skipped_orders.jsonl")),
        "latest_target_versions": latest_target_versions,
        "live_orders_submitted": False,
    }


def print_status(status: dict[str, Any]) -> None:
    for key, value in status.items():
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value) if value else "none"
        elif isinstance(value, bool):
            value = str(value).lower()
        print(f"{key}={value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect an Alpaca weekly demo session.")
    parser.add_argument("--session-dir", type=Path)
    parser.add_argument("--latest", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.latest:
        session_dir = latest_session_dir()
    elif args.session_dir:
        session_dir = args.session_dir
    else:
        raise SystemExit("--latest or --session-dir is required")
    print_status(inspect_session(session_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
