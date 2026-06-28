from __future__ import annotations

from pathlib import Path

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.execution.freeze_successful_strategies import update_registry
from execution_lab.alpaca_micro_live_v1.execution.runtime_orchestrator import run_orchestrator
from execution_lab.alpaca_micro_live_v1.execution.runtime_strategy_inventory import build_inventory, write_inventory
from execution_lab.alpaca_micro_live_v1.execution.weekly_demo_runner import EMERGENCY_STOP_FILE, STOP_FILE, run_weekly_demo
from execution_lab.alpaca_micro_live_v1.signals.generate_alpaca_signal import generate_signal


DEFAULT_CONFIG = MODULE_ROOT / "config" / "alpaca_paper.local.yaml"
DEFAULT_RISK = MODULE_ROOT / "config" / "risk_limits.local.yaml"
DEFAULT_REGISTRY = MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml"


def credential_summary() -> dict[str, str | bool]:
    creds = load_alpaca_credentials("paper")
    return {
        "present": creds.present,
        "api_key": creds.masked_api_key,
        "secret_key": creds.masked_secret_key,
        "source": creds.source,
        "live_detected_disabled": creds.live_credentials_detected,
    }


def generate_ui_signal(config: Path = DEFAULT_CONFIG, risk_limits: Path = DEFAULT_RISK) -> Path:
    output = MODULE_ROOT / "evidence" / "alpaca_signals" / "vm_quality_lowvol_proxy_v1.alpaca.target.yaml"
    generate_signal(
        strategy_id="vm_quality_lowvol_proxy_v1",
        config_path=config,
        risk_limits_path=risk_limits,
        output_path=output,
    )
    return output


def start_runtime_session(
    *,
    submit_paper_orders: bool,
    interval_seconds: int,
    max_loops: int,
    config: Path = DEFAULT_CONFIG,
    risk_limits: Path = DEFAULT_RISK,
    registry: Path = DEFAULT_REGISTRY,
) -> dict:
    return run_orchestrator(
        config_path=config,
        risk_limits_path=risk_limits,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=interval_seconds,
        max_loops=max_loops,
        submit_paper_orders=submit_paper_orders,
        dry_run=not submit_paper_orders,
    )


def run_strategy_inventory() -> dict:
    inventory = build_inventory()
    write_inventory(inventory)
    return inventory


def freeze_ready_strategies() -> dict:
    inventory = build_inventory()
    write_inventory(inventory)
    return update_registry(DEFAULT_REGISTRY, inventory)


def start_weekly_demo(
    *,
    strategies: list[str],
    submit_paper_orders: bool,
    interval_seconds: int,
    max_loops: int | None,
    run_until: str | None = None,
    resume: Path | None = None,
    config: Path = DEFAULT_CONFIG,
    risk_limits: Path = DEFAULT_RISK,
    registry: Path = DEFAULT_REGISTRY,
) -> dict:
    return run_weekly_demo(
        config_path=config,
        risk_limits_path=risk_limits,
        runtime_registry_path=registry,
        strategies=strategies,
        interval_seconds=interval_seconds,
        max_loops=max_loops,
        run_until=run_until,
        resume=resume,
        submit_paper_orders=submit_paper_orders,
        dry_run=not submit_paper_orders,
    )


def request_weekly_stop() -> Path:
    STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text("weekly demo stop requested\n", encoding="utf-8")
    return STOP_FILE


def request_weekly_emergency_stop() -> Path:
    EMERGENCY_STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    EMERGENCY_STOP_FILE.write_text("weekly demo emergency stop requested\n", encoding="utf-8")
    return EMERGENCY_STOP_FILE

