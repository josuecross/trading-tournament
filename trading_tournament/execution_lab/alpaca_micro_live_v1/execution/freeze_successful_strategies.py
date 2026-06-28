from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.execution.runtime_strategy_inventory import DEFAULT_JSON, build_inventory, write_inventory


DEFAULT_REGISTRY = MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml"


DSR_SPEC = {
    "strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
    "source": "trading_tournament_successful_strategy_copy",
    "runtime_version": "alpaca_runtime_v1",
    "source_evidence": [
        {
            "path": "paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1/active_observation.yaml",
            "reason": "Recovered active/frozen paper-demo observation with fixed rules.",
        }
    ],
    "universe": {
        "sector_assets": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"],
        "cash_or_fallback": ["BIL"],
    },
    "indicators": {"sma_window": 200},
    "eligibility": {"rule": "close_above_sma_200", "sma_window": 200},
    "ranking": {"method": "none_equal_weight_all_qualifying"},
    "portfolio": {
        "weighting": "equal_weight_qualifying_sectors",
        "fallback": "BIL",
        "one_or_two_qualify_policy": "one_third_each_qualifying_remainder_bil",
    },
    "rebalance": {"signal_cadence": "daily_completed_bar", "execution_cadence": "operator_controlled_loop", "rebalance_policy": "monthly_rebalance_target_change_or_drift"},
    "constraints": {
        "long_only": True,
        "no_leverage": True,
        "no_shorting": True,
        "no_options": True,
        "no_crypto": True,
        "no_futures": True,
        "no_forex": True,
        "no_intraday": True,
    },
    "paper_runtime": {
        "enabled": True,
        "capital_sleeve_notional": 25.00,
        "max_order_notional": 5.00,
        "rebalance_tolerance_notional": 1.00,
    },
}


DSR_MODULE = '''from __future__ import annotations

from typing import Any

import pandas as pd


def _metrics(frame: pd.DataFrame, sma_window: int) -> dict[str, Any]:
    ordered = frame.copy()
    ordered["date"] = ordered["date"].astype(str)
    ordered = ordered.sort_values("date")
    close = ordered["close"].astype(float)
    if len(ordered) < sma_window:
        return {"eligible": False, "reason": "insufficient_history", "rows": len(ordered)}
    latest_close = float(close.iloc[-1])
    sma = float(close.rolling(sma_window).mean().iloc[-1])
    return {
        "eligible": latest_close > sma,
        "latest_date": ordered["date"].iloc[-1],
        "close": latest_close,
        "sma_200": sma,
    }


def generate_target_from_bars(bars_by_symbol: dict, spec: dict) -> dict:
    sector_assets = spec["universe"]["sector_assets"]
    fallback = spec["portfolio"]["fallback"]
    sma_window = int(spec["eligibility"]["sma_window"])
    eligibility = []
    qualifying = []
    latest_dates = []
    for symbol in sector_assets:
        frame = bars_by_symbol.get(symbol)
        if frame is None or frame.empty:
            eligibility.append({"symbol": symbol, "eligible": False, "reason": "missing_data"})
            continue
        metrics = _metrics(frame, sma_window)
        row = {"symbol": symbol, **metrics}
        eligibility.append(row)
        if metrics.get("latest_date"):
            latest_dates.append(str(metrics["latest_date"]))
        if metrics.get("eligible"):
            qualifying.append(symbol)
    if not qualifying:
        target_weights = {fallback: 1.0}
        fallback_triggered = True
    elif len(qualifying) <= 2:
        target_weights = {symbol: 1.0 / 3.0 for symbol in qualifying}
        target_weights[fallback] = 1.0 - sum(target_weights.values())
        fallback_triggered = False
    else:
        weight = 1.0 / len(qualifying)
        target_weights = {symbol: weight for symbol in qualifying}
        fallback_triggered = False
    return {
        "strategy_id": spec["strategy_id"],
        "as_of": min(latest_dates) if latest_dates else "",
        "target_source": "alpaca_runtime",
        "target_weights": target_weights,
        "cash_weight": 0.0,
        "metadata": {
            "strategy_logic_modified": False,
            "selected_holdings": list(target_weights),
            "eligibility": eligibility,
            "ranking": [],
            "fallback_triggered": fallback_triggered,
        },
    }
'''


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_dsr_strategy(row: dict[str, Any]) -> None:
    root = MODULE_ROOT / "runtime_strategies"
    spec_path = root / "dsr_sector_equal_weight_defensive_filter_v1.yaml"
    module_path = root / "dsr_sector_equal_weight_defensive_filter_v1.py"
    trace_path = root / "dsr_sector_equal_weight_defensive_filter_v1.source_trace.md"
    spec_path.write_text(yaml.safe_dump(DSR_SPEC, sort_keys=False), encoding="utf-8")
    module_path.write_text(DSR_MODULE, encoding="utf-8")
    trace_path.write_text(
        "# Source Trace\n\n"
        "Copied from local recovered active/frozen paper-demo observation evidence.\n\n"
        + "\n".join(f"- {path}" for path in row.get("source_rule_files", []))
        + "\n",
        encoding="utf-8",
    )


def update_registry(output_registry: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    registry = read_yaml(output_registry)
    registry.setdefault("version", 1)
    strategies = registry.setdefault("strategies", {})
    for row in inventory["candidates"]:
        strategy_id = row["strategy_id"]
        if row["status_classification"] == "ready_to_freeze" and strategy_id == "dsr_sector_equal_weight_defensive_filter_v1":
            write_dsr_strategy(row)
            strategies[strategy_id] = {
                "enabled": True,
                "runtime_ready": True,
                "runtime_spec": f"runtime_strategies/{strategy_id}.yaml",
                "runtime_module": f"runtime_strategies/{strategy_id}.py",
                "target_source": "alpaca_runtime",
                "data_timeframe": "1Day",
                "signal_cadence": "daily_completed_bar",
                "paper_trading_allowed": True,
                "live_trading_allowed": False,
                "capital_sleeve_notional": 25.00,
                "max_order_notional": 5.00,
                "rebalance_tolerance_notional": 1.00,
                "allowed_symbols": row["allowed_symbols"],
            }
        elif row["status_classification"] in {"onboarding_blocked", "unsupported_asset_class"} and strategy_id not in strategies:
            strategies[strategy_id] = {
                "enabled": False,
                "runtime_ready": False,
                "blocked_reason": row["exact_reason"],
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
            }
    output_registry.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze ready successful strategies into Alpaca runtime specs.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-registry", type=Path, default=DEFAULT_REGISTRY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.inventory.exists():
        inventory = build_inventory()
        write_inventory(inventory, args.inventory, args.inventory.with_suffix(".md"))
    else:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    registry = update_registry(args.output_registry, inventory)
    frozen = [
        row["strategy_id"]
        for row in inventory["candidates"]
        if row["status_classification"] == "ready_to_freeze"
    ]
    blocked = [
        row["strategy_id"]
        for row in inventory["candidates"]
        if row["status_classification"] in {"onboarding_blocked", "unsupported_asset_class"}
    ]
    print(f"frozen_strategies={frozen}")
    print(f"blocked_strategies={blocked}")
    print(f"runtime_registry_entries={list((registry.get('strategies') or {}).keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
