from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Alpaca market clock.")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    client = AlpacaClient(
        load_alpaca_credentials("paper"),
        AlpacaClientConfig(
            paper_base_url=config.get("paper_base_url", "https://paper-api.alpaca.markets"),
            data_base_url=config.get("data_base_url", "https://data.alpaca.markets"),
        ),
    )
    clock = client.get_market_clock()
    print(f"is_open: {str(clock.get('is_open')).lower()}")
    print(f"next_open: {clock.get('next_open')}")
    print(f"next_close: {clock.get('next_close')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

