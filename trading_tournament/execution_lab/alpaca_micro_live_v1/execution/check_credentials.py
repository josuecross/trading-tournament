from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Alpaca paper credentials without printing secrets.")
    parser.add_argument("--environment", default="paper", choices=["paper"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--no-network", action="store_true", help="Only verify local credential presence.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    credentials = load_alpaca_credentials(args.environment)
    print(f"environment: {credentials.environment}")
    print(f"paper_credentials_present: {str(credentials.present).lower()}")
    print(f"paper_api_key: {credentials.masked_api_key}")
    print(f"paper_secret_key: {credentials.masked_secret_key}")
    print(f"source: {credentials.source}")
    print(f"live_credentials_detected_but_disabled: {str(credentials.live_credentials_detected).lower()}")
    if args.no_network or not credentials.present:
        return 0 if credentials.present else 2
    config_data = {}
    if args.config and args.config.exists():
        config_data = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    client = AlpacaClient(
        credentials,
        AlpacaClientConfig(
            paper_base_url=config_data.get("paper_base_url", "https://paper-api.alpaca.markets"),
            data_base_url=config_data.get("data_base_url", "https://data.alpaca.markets"),
        ),
    )
    try:
        account = client.get_account()
    except BrokerError as exc:
        print(f"paper_connection_ok: false")
        print(f"broker_error_category: {exc.category}")
        return 3
    print("paper_connection_ok: true")
    print(f"account_status: {account.get('status', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
