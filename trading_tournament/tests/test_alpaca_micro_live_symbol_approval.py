from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import fetch_daily_bars
from execution_lab.alpaca_micro_live_v1.execution import weekly_demo_runner as weekly
from tests.alpaca_micro_live_fakes import FakeRuntimeClient, fake_credentials, make_bars_by_symbol, write_runtime_files

pytestmark = pytest.mark.alpaca_micro_live


VM_SYMBOLS = {"SPLV", "USMV", "QUAL", "SPY", "BIL"}
DSR_SYMBOLS = {"XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"}


class FakeBarsClient:
    def __init__(self) -> None:
        self.calls = 0

    def get_historical_bars_page(self, *, symbols: list[str], **_kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "bars": {
                symbol: [
                    {
                        "t": "2025-01-02T00:00:00Z",
                        "o": 100.0,
                        "h": 101.0,
                        "l": 99.0,
                        "c": 100.0,
                        "v": 1000,
                    }
                ]
                for symbol in symbols
            }
        }


def _registry() -> dict[str, Any]:
    return yaml.safe_load((MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml").read_text(encoding="utf-8"))


def _clean_stops() -> None:
    weekly.STOP_FILE.unlink(missing_ok=True)
    weekly.EMERGENCY_STOP_FILE.unlink(missing_ok=True)


def _with_shared_bil_policy(risk_path: Path) -> None:
    risk = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
    risk["multi_strategy_allocation_policy"] = "independent_virtual_sleeves"
    risk["shared_fallback_symbols"] = ["BIL"]
    risk["shared_symbol_policy"] = {
        "allow_shared_fallback_symbols": True,
        "block_shared_risk_assets": True,
    }
    risk_path.write_text(yaml.safe_dump(risk), encoding="utf-8")


def test_vm_only_selected_strategy_approves_only_vm_symbols() -> None:
    approved = weekly.approved_symbols_for_selected_strategies(_registry(), ["vm_quality_lowvol_proxy_v1"])
    assert approved == VM_SYMBOLS
    assert "XLB" not in approved


def test_dsr_only_selected_strategy_approves_sector_etfs() -> None:
    approved = weekly.approved_symbols_for_selected_strategies(_registry(), ["dsr_sector_equal_weight_defensive_filter_v1"])
    assert approved == DSR_SYMBOLS
    assert {"XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}.issubset(approved)


def test_all_runtime_ready_approves_union_of_vm_and_dsr_symbols() -> None:
    registry = _registry()
    selected = weekly.resolve_runtime_ready(registry, ["all_runtime_ready"])
    approved = weekly.approved_symbols_for_selected_strategies(registry, selected)
    assert approved == VM_SYMBOLS | DSR_SYMBOLS


def test_vm_and_dsr_shared_bil_is_allowed_when_configured() -> None:
    registry = _registry()
    selected = weekly.resolve_runtime_ready(registry, ["all_runtime_ready"])
    risk_limits = {
        "multi_strategy_allocation_policy": "independent_virtual_sleeves",
        "shared_fallback_symbols": ["BIL"],
        "shared_symbol_policy": {"allow_shared_fallback_symbols": True, "block_shared_risk_assets": True},
    }
    classifications = weekly.classify_symbol_overlaps(registry, selected, risk_limits)
    assert classifications == [
        {
            "symbol": "BIL",
            "strategies": ["vm_quality_lowvol_proxy_v1", "dsr_sector_equal_weight_defensive_filter_v1"],
            "classification": "allowed_shared_fallback_symbol",
            "block_submit": False,
            "shared_fallback_symbols": ["BIL"],
            "fallback_for_all_owners": True,
            "policy_source": "risk_limits",
            "allocation_policy": "independent_virtual_sleeves",
        }
    ]


def test_shared_risk_asset_not_in_fallback_list_blocks() -> None:
    registry = _registry()
    registry["strategies"]["mirror_vm"] = {
        **registry["strategies"]["vm_quality_lowvol_proxy_v1"],
        "enabled": True,
        "runtime_ready": True,
    }
    classifications = weekly.classify_symbol_overlaps(
        registry,
        ["vm_quality_lowvol_proxy_v1", "mirror_vm"],
        {
            "multi_strategy_allocation_policy": "independent_virtual_sleeves",
            "shared_fallback_symbols": ["BIL"],
            "shared_symbol_policy": {"allow_shared_fallback_symbols": True, "block_shared_risk_assets": True},
        },
    )
    blocked = [item for item in classifications if item["classification"] == "blocked_shared_risk_symbol"]
    assert {item["symbol"] for item in blocked} == {"QUAL", "SPLV", "SPY", "USMV"}
    assert all(item["block_submit"] is True for item in blocked)


def test_unknown_symbol_fails_closed_before_bar_request() -> None:
    client = FakeBarsClient()
    with pytest.raises(ValueError, match="Symbols are not approved"):
        fetch_daily_bars(
            client,
            symbols=["AAPL"],
            approved_symbols=VM_SYMBOLS,
            start="2025-01-01",
            min_history_days=0,
        )
    assert client.calls == 0


def test_registry_spec_symbol_mismatch_fails_closed() -> None:
    registry = _registry()
    registry["strategies"]["dsr_sector_equal_weight_defensive_filter_v1"]["allowed_symbols"] = ["XLK", "XLF", "BIL"]
    with pytest.raises(ValueError, match="Registry/spec symbol mismatch"):
        weekly.approved_symbols_for_selected_strategies(registry, ["dsr_sector_equal_weight_defensive_filter_v1"])


def test_weekly_dry_run_vm_and_dsr_allows_sector_etfs_without_orders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_stops()
    monkeypatch.setattr(weekly, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(weekly, "load_alpaca_credentials", lambda environment="paper": fake_credentials())
    config, risk, _registry_path = write_runtime_files(tmp_path)
    _with_shared_bil_policy(risk)
    client = FakeRuntimeClient(market_open=True)
    calls: list[dict[str, Any]] = []

    def bars_fetcher(_client: Any, *, symbols: list[str], approved_symbols: set[str], **_kwargs: Any):
        calls.append({"symbols": list(symbols), "approved_symbols": set(approved_symbols)})
        assert set(symbols).issubset(set(approved_symbols))
        return make_bars_by_symbol(symbols=symbols)

    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml",
        strategies=["all_runtime_ready"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        submit_paper_orders=False,
        client=client,
        bars_fetcher=bars_fetcher,
    )
    assert result["runtime_blocked"] is False
    assert result["submitted_orders"] == 0
    assert client.submitted_orders == []
    assert any({"XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}.issubset(set(call["symbols"])) for call in calls)
    assert all(call["approved_symbols"] == VM_SYMBOLS | DSR_SYMBOLS for call in calls)
    summary = yaml.safe_load(Path(result["session_dir"], "weekly_summary.json").read_text(encoding="utf-8"))
    state = yaml.safe_load(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert summary["overlap_classifications"][0]["classification"] == "allowed_shared_fallback_symbol"
    assert state["overlap_classifications"][0]["symbol"] == "BIL"
    assert "allowed_shared_fallback_symbol" in Path(result["session_dir"], "runtime_blocks.jsonl").read_text(encoding="utf-8")
    _clean_stops()


def test_shared_bil_submit_uses_separate_strategy_client_order_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_stops()
    monkeypatch.setattr(weekly, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(weekly, "load_alpaca_credentials", lambda environment="paper": fake_credentials())
    config, risk, _registry_path = write_runtime_files(tmp_path, require_market_open=True)
    _with_shared_bil_policy(risk)
    client = FakeRuntimeClient(market_open=True)

    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml",
        strategies=["all_runtime_ready"],
        interval_seconds=0,
        max_loops=1,
        dry_run=False,
        submit_paper_orders=True,
        client=client,
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )

    bil_orders = [order for order in client.submitted_orders if order["symbol"] == "BIL"]
    assert result["live_orders_submitted"] is False
    assert len(bil_orders) == 2
    assert len({order["client_order_id"] for order in bil_orders}) == 2
    assert any("vm_quality_lowvol_proxy_v1" in order["client_order_id"] for order in bil_orders)
    assert any("dsr_sector_equal_weight_defensive_filter_v1" in order["client_order_id"] for order in bil_orders)
    submitted_text = Path(result["session_dir"], "submitted_orders.jsonl").read_text(encoding="utf-8")
    assert "vm_quality_lowvol_proxy_v1" in submitted_text
    assert "dsr_sector_equal_weight_defensive_filter_v1" in submitted_text
    _clean_stops()


def test_existing_aggregate_bil_position_is_unattributed_in_virtual_sleeves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_stops()
    monkeypatch.setattr(weekly, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(weekly, "load_alpaca_credentials", lambda environment="paper": fake_credentials())
    config, risk, _registry_path = write_runtime_files(tmp_path)
    _with_shared_bil_policy(risk)
    client = FakeRuntimeClient(market_open=True)
    client.get_positions = lambda: [{"symbol": "BIL", "market_value": "7.00", "current_price": "100.00"}]

    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml",
        strategies=["all_runtime_ready"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        submit_paper_orders=False,
        client=client,
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )

    sleeves = Path(result["session_dir"], "virtual_sleeves.jsonl").read_text(encoding="utf-8")
    assert '"symbol": "BIL"' in sleeves
    assert "unattributed_existing_position" in sleeves
    assert "vm_quality_lowvol_proxy_v1" in sleeves
    assert "dsr_sector_equal_weight_defensive_filter_v1" in sleeves
    _clean_stops()
