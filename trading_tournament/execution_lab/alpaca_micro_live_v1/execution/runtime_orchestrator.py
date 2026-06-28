from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.execution.logging_utils import append_jsonl, utc_timestamp, write_json

load_alpaca_credentials = None
fetch_daily_bars = None


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def target_version_id(strategy_id: str, as_of: str, target_weights: dict[str, float]) -> str:
    payload = json.dumps(target_weights, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{strategy_id}:{as_of}:{digest}"


def create_session_dir() -> Path:
    session_id = utc_timestamp().replace(":", "").replace("-", "").replace(".", "").replace("Z", "Z")
    path = MODULE_ROOT / "evidence" / "runtime_sessions" / f"runtime_session_{session_id}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _latest_prices_from_bars(bars: dict[str, Any]) -> dict[str, float]:
    prices = {}
    for symbol, frame in bars.items():
        if frame is not None and not frame.empty:
            prices[symbol] = float(frame.sort_values("date")["close"].iloc[-1])
    return prices


def run_orchestrator(
    *,
    config_path: Path,
    risk_limits_path: Path,
    runtime_registry_path: Path,
    strategies: list[str],
    mode: str,
    interval_seconds: int,
    max_loops: int | None,
    run_until_stopped: bool = False,
    submit_paper_orders: bool = False,
    dry_run: bool = True,
    client: Any | None = None,
) -> dict[str, Any]:
    from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
    from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials as imported_load_credentials
    from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import fetch_daily_bars as imported_fetch_daily_bars
    from execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError
    from execution_lab.alpaca_micro_live_v1.execution.order_sizing import build_delta_orders
    from execution_lab.alpaca_micro_live_v1.execution.risk_gate import evaluate_risk_gate
    from execution_lab.alpaca_micro_live_v1.runtime_strategies.vm_quality_lowvol_proxy_v1 import (
        generate_signal_from_bars,
        load_strategy_spec,
    )
    from execution_lab.alpaca_micro_live_v1.signals.generate_alpaca_signal import signal_to_target_dict

    credentials_loader = load_alpaca_credentials or imported_load_credentials
    bars_fetcher = fetch_daily_bars or imported_fetch_daily_bars

    if mode != "paper":
        raise ValueError("Live mode is out of scope and not supported.")
    if max_loops is None and not run_until_stopped:
        raise ValueError("--max-loops is required unless --run-until-stopped is explicit.")
    if submit_paper_orders and dry_run:
        dry_run = False

    config = load_yaml(config_path)
    risk_limits = load_yaml(risk_limits_path)
    registry = load_yaml(runtime_registry_path)
    credentials = credentials_loader("paper")
    client = client or AlpacaClient(
        credentials,
        AlpacaClientConfig(
            paper_base_url=config.get("paper_base_url", "https://paper-api.alpaca.markets"),
            data_base_url=config.get("data_base_url", "https://data.alpaca.markets"),
            data_feed=config.get("data_feed", "iex"),
            data_adjustment=config.get("data_adjustment", "all"),
            retry_attempts=int(risk_limits.get("broker_read_retry_max_attempts", 3)),
            retry_backoff_seconds=tuple(risk_limits.get("broker_read_retry_backoff_seconds", [1, 3])),
        ),
    )

    session_dir = create_session_dir()
    session_state = {
        "session_id": session_dir.name,
        "mode": mode,
        "dry_run": dry_run,
        "submit_paper_orders": submit_paper_orders,
        "selected_strategies": strategies,
        "handled_target_versions": [],
        "emergency_stop": False,
        "live_orders_submitted": False,
    }
    write_json(session_dir / "session_config.yaml", {"config": str(config_path), "risk_limits": str(risk_limits_path), "registry": str(runtime_registry_path)})
    loop_count = 0
    submitted_orders: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    target_versions: list[str] = []

    while run_until_stopped or loop_count < int(max_loops or 0):
        loop_count += 1
        append_jsonl(session_dir / "loop_events.jsonl", {"event": "loop_start", "loop": loop_count})
        try:
            clock = client.get_market_clock()
            account = client.get_account()
            positions = client.get_positions()
            open_orders = client.list_open_orders()
        except BrokerError as exc:
            append_jsonl(session_dir / "broker_errors.jsonl", {"category": exc.category, "message": exc.message})
            rejected.append({"loop": loop_count, "reason": "broker_read_failed", "category": exc.category})
            if not run_until_stopped and loop_count >= int(max_loops or 0):
                break
            time.sleep(interval_seconds)
            continue

        for strategy_id in strategies:
            if strategy_id != "vm_quality_lowvol_proxy_v1":
                rejected.append({"strategy_id": strategy_id, "reason": "unsupported_strategy"})
                append_jsonl(session_dir / "rejects.jsonl", rejected[-1])
                continue
            spec = load_strategy_spec()
            symbols = spec["universe"]["risk_assets"] + spec["universe"]["cash_or_fallback"]
            bars = bars_fetcher(
                client,
                symbols=symbols,
                approved_symbols=symbols,
                start=(date.today() - timedelta(days=420)).isoformat(),
                feed=config.get("data_feed", "iex"),
                adjustment=config.get("data_adjustment", "all"),
            )
            signal = generate_signal_from_bars(
                bars,
                spec=spec,
                feed=config.get("data_feed", "iex"),
                adjustment=config.get("data_adjustment", "all"),
            )
            append_jsonl(session_dir / "signals.jsonl", signal_to_target_dict(signal))
            version = target_version_id(strategy_id, signal.as_of, signal.target_weights)
            target_versions.append(version)
            already_handled = version in session_state["handled_target_versions"]
            proposed_orders, skipped = build_delta_orders(
                target_weights=signal.target_weights,
                account=account,
                positions=positions,
                latest_prices=_latest_prices_from_bars(bars),
                risk_limits=risk_limits,
            )
            for order in proposed_orders:
                order.client_order_id = f"amv1-{strategy_id[:12]}-{uuid.uuid4().hex[:14]}"
                append_jsonl(session_dir / "proposed_orders.jsonl", order.__dict__)
            for skip in skipped:
                append_jsonl(session_dir / "rejects.jsonl", {"strategy_id": strategy_id, **skip})

            assets_list = client.get_assets(symbols) if proposed_orders else []
            assets = {asset.get("symbol"): asset for asset in assets_list}
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
                proposed_orders=proposed_orders,
                assets=assets,
                target_version_already_handled=already_handled,
                emergency_stop=session_state["emergency_stop"],
            )
            if dry_run or not submit_paper_orders:
                append_jsonl(session_dir / "loop_events.jsonl", {"event": "dry_run_no_submit", "target_version": version, "risk_errors": gate.errors})
                if not already_handled:
                    session_state["handled_target_versions"].append(version)
                continue
            if not gate.allowed:
                rejected.append({"strategy_id": strategy_id, "target_version": version, "reason": "risk_gate_blocked", "errors": gate.errors})
                append_jsonl(session_dir / "rejects.jsonl", rejected[-1])
                continue

            for order in proposed_orders[: int(risk_limits.get("max_orders_per_loop", 10))]:
                try:
                    submitted = client.submit_order(
                        symbol=order.symbol,
                        side=order.side,
                        notional=order.notional if order.side == "buy" else None,
                        qty=order.qty if order.side == "sell" else None,
                        client_order_id=order.client_order_id,
                    )
                except BrokerError as exc:
                    append_jsonl(
                        session_dir / "broker_errors.jsonl",
                        {
                            "category": exc.category,
                            "message": exc.message,
                            "ambiguous_submission": exc.ambiguous_submission,
                            "client_order_id": exc.client_order_id,
                            "submission_attempt_id": exc.submission_attempt_id,
                        },
                    )
                    rejected.append({"strategy_id": strategy_id, "reason": "submit_failed_fail_closed", "client_order_id": exc.client_order_id})
                    append_jsonl(session_dir / "rejects.jsonl", rejected[-1])
                    break
                submitted_orders.append(submitted)
                append_jsonl(session_dir / "orders.jsonl", submitted)
            session_state["handled_target_versions"].append(version)

        write_json(session_dir / "session_state.json", session_state)
        if not run_until_stopped and loop_count >= int(max_loops or 0):
            break
        time.sleep(interval_seconds)

    summary = {
        "session_id": session_dir.name,
        "mode": mode,
        "dry_run": dry_run,
        "submit_paper_orders": submit_paper_orders,
        "selected_strategies": strategies,
        "loop_count": loop_count,
        "signals_generated": len(target_versions),
        "target_versions": target_versions,
        "submitted_orders": len(submitted_orders),
        "rejects": len(rejected),
        "live_orders_submitted": False,
        "session_dir": str(session_dir),
    }
    write_json(session_dir / "runtime_session_summary.json", summary)
    write_json(session_dir / "strategy_states.json", {"strategies": strategies, "target_versions": target_versions})
    for name in ["fills.jsonl", "orders.jsonl", "rejects.jsonl", "broker_errors.jsonl", "proposed_orders.jsonl", "signals.jsonl"]:
        (session_dir / name).touch(exist_ok=True)
    report = [
        "# Alpaca Runtime Session Report",
        "",
        f"- session_id: {summary['session_id']}",
        f"- mode: {mode}",
        f"- dry_run: {str(dry_run).lower()}",
        f"- submit_paper_orders: {str(submit_paper_orders).lower()}",
        f"- selected_strategies: {', '.join(strategies)}",
        f"- loop_count: {loop_count}",
        f"- signals_generated: {len(target_versions)}",
        f"- target_versions: {', '.join(target_versions) if target_versions else 'none'}",
        f"- proposed_orders: see proposed_orders.jsonl",
        f"- submitted_orders: {len(submitted_orders)}",
        f"- fills: see fills.jsonl",
        f"- rejects: {len(rejected)}",
        f"- open_orders: checked each loop",
        f"- broker_errors: see broker_errors.jsonl",
        f"- final_positions_summary: see broker/account evidence in loop logs",
        f"- stop_emergency_state: {str(session_state['emergency_stop']).lower()}",
        f"- live_orders_submitted: false",
    ]
    (session_dir / "session_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Alpaca micro paper runtime.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--risk-limits", required=True, type=Path)
    parser.add_argument("--runtime-registry", default=MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml", type=Path)
    parser.add_argument("--strategies", required=True, nargs="+")
    parser.add_argument("--mode", default="paper", choices=["paper"])
    parser.add_argument("--interval-seconds", default=60, type=int)
    parser.add_argument("--max-loops", type=int)
    parser.add_argument("--run-until-stopped", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--submit-paper-orders", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_orchestrator(
        config_path=args.config,
        risk_limits_path=args.risk_limits,
        runtime_registry_path=args.runtime_registry,
        strategies=args.strategies,
        mode=args.mode,
        interval_seconds=args.interval_seconds,
        max_loops=args.max_loops,
        run_until_stopped=args.run_until_stopped,
        submit_paper_orders=args.submit_paper_orders,
        dry_run=not args.submit_paper_orders,
    )
    print(f"Wrote runtime session evidence to {summary['session_dir']}")
    print(f"submitted_orders: {summary['submitted_orders']}")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

