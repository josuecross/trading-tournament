from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials


def fake_credentials() -> AlpacaCredentials:
    return AlpacaCredentials(
        environment="paper",
        api_key="PKFAKE1234567890",
        secret_key="SKFAKE1234567890",
        source="test",
    )


def write_runtime_files(tmp_path: Path, *, require_market_open: bool = True) -> tuple[Path, Path, Path]:
    config = tmp_path / "alpaca_paper.local.yaml"
    risk = tmp_path / "risk_limits.local.yaml"
    registry = tmp_path / "runtime_strategy_registry.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "paper_base_url": "https://paper.invalid",
                "data_base_url": "https://data.invalid",
                "data_feed": "iex",
                "data_adjustment": "all",
            }
        ),
        encoding="utf-8",
    )
    risk.write_text(
        yaml.safe_dump(
            {
                "paper_trading_allowed": True,
                "live_trading_allowed": False,
                "capital_sleeve_notional": 25.0,
                "max_total_notional_per_run": 25.0,
                "max_order_notional": 5.0,
                "min_order_notional": 1.0,
                "rebalance_tolerance_notional": 1.0,
                "cash_buffer_pct": 0.0,
                "max_orders_per_loop": 10,
                "require_market_open": require_market_open,
                "allow_shorts": False,
                "allow_margin": False,
                "allow_options": False,
                "allow_crypto": False,
                "allow_futures": False,
                "allow_paper_reduce_only_sells": True,
                "broker_read_retry_max_attempts": 1,
                "broker_read_retry_backoff_seconds": [0],
            }
        ),
        encoding="utf-8",
    )
    registry.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "strategies": {
                    "vm_quality_lowvol_proxy_v1": {
                        "enabled": True,
                        "runtime_ready": True,
                        "runtime_spec": "runtime_strategies/vm_quality_lowvol_proxy_v1.yaml",
                        "runtime_module": "runtime_strategies/vm_quality_lowvol_proxy_v1.py",
                        "target_source": "alpaca_runtime",
                        "data_timeframe": "1Day",
                        "live_trading_allowed": False,
                        "paper_trading_allowed": True,
                        "allowed_symbols": ["SPLV", "USMV", "QUAL", "SPY", "BIL"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return config, risk, registry


def make_bars_by_symbol(eligible: bool = True, symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    symbols = symbols or ["SPLV", "USMV", "QUAL", "SPY", "BIL"]
    start = date(2025, 1, 1)
    bars: dict[str, pd.DataFrame] = {}
    default_slopes = {
        "SPLV": 0.30,
        "USMV": 0.15,
        "QUAL": 0.45,
        "SPY": 0.10,
        "BIL": 0.01,
        "XLK": 0.32,
        "XLF": 0.25,
        "XLE": 0.20,
        "XLV": 0.18,
        "XLY": 0.16,
        "XLP": 0.14,
        "XLU": 0.12,
        "XLI": 0.11,
        "XLB": 0.10,
        "XLC": 0.09,
    }
    for symbol in symbols:
        records: list[dict[str, Any]] = []
        for day in range(260):
            value = 100.0 + default_slopes.get(symbol, 0.10) * day
            if not eligible and symbol != "BIL" and day == 259:
                value = 50.0
            records.append(
                {
                    "date": (start + timedelta(days=day)).isoformat(),
                    "open": value,
                    "high": value,
                    "low": value,
                    "close": value,
                    "volume": 1000,
                }
            )
        bars[symbol] = pd.DataFrame(records)
    return bars


class FakeRuntimeClient:
    def __init__(self, *, market_open: bool = True, cash: float = 1000.0) -> None:
        self.market_open = market_open
        self.cash = cash
        self.submitted_orders: list[dict[str, Any]] = []

    def get_market_clock(self) -> dict[str, Any]:
        return {"is_open": self.market_open}

    def get_account(self) -> dict[str, Any]:
        return {"cash": str(self.cash), "equity": "1000"}

    def get_positions(self) -> list[dict[str, Any]]:
        return []

    def list_open_orders(self) -> list[dict[str, Any]]:
        return []

    def get_assets(self, symbols: list[str]) -> list[dict[str, Any]]:
        return [{"symbol": symbol, "tradable": True, "fractionable": True} for symbol in symbols]

    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        self.submitted_orders.append(kwargs)
        return {"id": f"order-{len(self.submitted_orders)}", **kwargs}
