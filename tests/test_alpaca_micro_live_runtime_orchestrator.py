from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
import yaml

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClientConfig
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.runtime_orchestrator import run_orchestrator


pytestmark = pytest.mark.alpaca_micro_live


class FakeClient:
    config = AlpacaClientConfig(data_feed="iex", data_adjustment="all")
    credentials = AlpacaCredentials("paper", "key", "secret", "fake")

    def __init__(self):
        self.submissions = []

    def get_market_clock(self):
        return {"is_open": True}

    def get_account(self):
        return {"cash": "1000", "equity": "1000"}

    def get_positions(self):
        return []

    def list_open_orders(self):
        return []

    def get_assets(self, symbols=None):
        return [{"symbol": symbol, "tradable": True, "fractionable": True} for symbol in (symbols or [])]

    def submit_order(self, **kwargs):
        self.submissions.append(kwargs)
        return {"id": f"order-{len(self.submissions)}", **kwargs}

    def get_historical_bars_page(self, *, symbols, start, **kwargs):
        bars = {}
        start_date = date(2025, 1, 1)
        for symbol in symbols:
            end = {"QUAL": 130, "SPY": 120, "USMV": 108, "SPLV": 104, "BIL": 101}.get(symbol, 100)
            prices = np.linspace(100, end, 230)
            bars[symbol] = [
                {
                    "t": (start_date + timedelta(days=i)).isoformat() + "T05:00:00Z",
                    "o": float(price),
                    "h": float(price),
                    "l": float(price),
                    "c": float(price),
                    "v": 1000,
                }
                for i, price in enumerate(prices)
            ]
        return {"bars": bars}


def write_configs(tmp_path):
    config = tmp_path / "alpaca.yaml"
    risk = tmp_path / "risk.yaml"
    registry = tmp_path / "registry.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "paper_base_url": "https://paper-api.alpaca.markets",
                "data_base_url": "https://data.alpaca.markets",
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
                "cash_buffer_pct": 0.05,
                "max_orders_per_loop": 10,
                "require_market_open": True,
                "allow_paper_reduce_only_sells": False,
                "allow_shorts": False,
                "allow_margin": False,
                "allow_options": False,
                "allow_crypto": False,
                "allow_futures": False,
                "broker_read_retry_max_attempts": 1,
                "broker_read_retry_backoff_seconds": [0],
            }
        ),
        encoding="utf-8",
    )
    registry.write_text(
        yaml.safe_dump(
            {
                "strategies": {
                    "vm_quality_lowvol_proxy_v1": {
                        "enabled": True,
                        "runtime_ready": True,
                        "live_trading_allowed": False,
                        "allowed_symbols": ["SPLV", "USMV", "QUAL", "SPY", "BIL"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return config, risk, registry


def test_runtime_dry_run_submits_nothing(tmp_path):
    config, risk, registry = write_configs(tmp_path)
    client = FakeClient()
    summary = run_orchestrator(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=0,
        max_loops=1,
        submit_paper_orders=False,
        dry_run=True,
        client=client,
    )
    assert summary["submitted_orders"] == 0
    assert client.submissions == []
    assert summary["live_orders_submitted"] is False


def test_runtime_submit_requires_flag_and_idempotency_prevents_duplicate(tmp_path):
    config, risk, registry = write_configs(tmp_path)
    client = FakeClient()
    summary = run_orchestrator(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=0,
        max_loops=2,
        submit_paper_orders=True,
        dry_run=False,
        client=client,
    )
    assert summary["submitted_orders"] == 2
    assert len(client.submissions) == 2
    assert summary["live_orders_submitted"] is False


def test_runtime_rejects_live_mode(tmp_path):
    config, risk, registry = write_configs(tmp_path)
    with pytest.raises(ValueError):
        run_orchestrator(
            config_path=config,
            risk_limits_path=risk,
            runtime_registry_path=registry,
            strategies=["vm_quality_lowvol_proxy_v1"],
            mode="live",
            interval_seconds=0,
            max_loops=1,
            client=FakeClient(),
        )
