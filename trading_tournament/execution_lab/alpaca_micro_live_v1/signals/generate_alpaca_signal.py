from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import fetch_daily_bars
from execution_lab.alpaca_micro_live_v1.execution.models import RuntimeSignal
from execution_lab.alpaca_micro_live_v1.runtime_strategies.vm_quality_lowvol_proxy_v1 import (
    generate_signal_from_bars,
    load_strategy_spec,
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def signal_to_target_dict(signal: RuntimeSignal) -> dict[str, Any]:
    return {
        "strategy_id": signal.strategy_id,
        "as_of": signal.as_of,
        "target_source": "alpaca_runtime",
        "target_weights": signal.target_weights,
        "cash_weight": signal.cash_weight,
        "metadata": signal.metadata,
    }


def write_signal_report(signal: RuntimeSignal, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Alpaca Runtime Signal Report",
        "",
        f"- strategy_id: {signal.strategy_id}",
        f"- data_source: {signal.metadata.get('data_source')}",
        f"- target_source: alpaca_runtime",
        f"- adjustment: {signal.metadata.get('adjustment')}",
        f"- feed: {signal.metadata.get('feed')}",
        f"- latest_completed_bar_date: {signal.as_of}",
        f"- fallback_triggered: {str(signal.fallback_triggered).lower()}",
        f"- missing_data: {', '.join(signal.missing_data) if signal.missing_data else 'none'}",
        f"- approximations: {', '.join(signal.approximations) if signal.approximations else 'none'}",
        f"- strategy_logic_modified: false",
        "",
        "## Eligibility Table",
        "",
        "| symbol | eligible | close | sma_200 | reason |",
        "|---|---:|---:|---:|---|",
    ]
    for row in signal.eligibility_table:
        lines.append(
            f"| {row.get('symbol')} | {row.get('eligible')} | {row.get('close', '')} | {row.get('sma_200', '')} | {row.get('reason', '')} |"
        )
    lines.extend(["", "## Ranking Table", "", "| symbol | eligible | return_126d | realized_vol_60d | score |", "|---|---:|---:|---:|---:|"])
    for row in signal.ranking_table:
        lines.append(
            f"| {row.get('symbol')} | {row.get('eligible')} | {row.get('return_126d')} | {row.get('realized_vol_60d')} | {row.get('score')} |"
        )
    lines.extend(["", "## Selected Holdings", "", ", ".join(signal.selected_holdings), "", "## Target Weights", ""])
    for symbol, weight in signal.target_weights.items():
        lines.append(f"- {symbol}: {weight:.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_signal(
    *,
    strategy_id: str,
    config_path: Path,
    risk_limits_path: Path | None = None,
    output_path: Path,
) -> RuntimeSignal:
    if strategy_id != "vm_quality_lowvol_proxy_v1":
        raise ValueError("Only vm_quality_lowvol_proxy_v1 is registered in this runtime.")
    config = load_yaml(config_path)
    credentials = load_alpaca_credentials("paper")
    client_config = AlpacaClientConfig(
        paper_base_url=config.get("paper_base_url", "https://paper-api.alpaca.markets"),
        data_base_url=config.get("data_base_url", "https://data.alpaca.markets"),
        data_feed=config.get("data_feed", "iex"),
        data_adjustment=config.get("data_adjustment", "all"),
    )
    client = AlpacaClient(credentials, client_config)
    spec = load_strategy_spec()
    symbols = spec["universe"]["risk_assets"] + spec["universe"]["cash_or_fallback"]
    start = (date.today() - timedelta(days=420)).isoformat()
    bars = fetch_daily_bars(
        client,
        symbols=symbols,
        start=start,
        feed=client_config.data_feed,
        adjustment=client_config.data_adjustment,
    )
    signal = generate_signal_from_bars(
        bars,
        spec=spec,
        feed=client_config.data_feed,
        adjustment=client_config.data_adjustment,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(signal_to_target_dict(signal), sort_keys=False), encoding="utf-8")
    report_path = output_path.with_name(f"{strategy_id}.alpaca.target_signal_report.md")
    write_signal_report(signal, report_path)
    return signal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an Alpaca-runtime target signal.")
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--risk-limits", type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Target YAML output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generate_signal(
        strategy_id=args.strategy_id,
        config_path=args.config,
        risk_limits_path=args.risk_limits,
        output_path=args.output,
    )
    print(f"Wrote Alpaca runtime signal to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

