from __future__ import annotations

from pathlib import Path

import pytest

from execution_lab.alpaca_micro_live_v1.execution import runtime_orchestrator
from tests.alpaca_micro_live_fakes import FakeRuntimeClient, fake_credentials, make_bars_by_symbol, write_runtime_files

pytestmark = pytest.mark.alpaca_micro_live


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime_orchestrator, "load_alpaca_credentials", lambda environment="paper": fake_credentials())
    monkeypatch.setattr(runtime_orchestrator, "fetch_daily_bars", lambda *args, **kwargs: make_bars_by_symbol())
    counter = {"value": 0}

    def create_session_dir() -> Path:
        counter["value"] += 1
        path = tmp_path / f"session_{counter['value']}"
        path.mkdir()
        return path

    monkeypatch.setattr(runtime_orchestrator, "create_session_dir", create_session_dir)


def test_runtime_dry_run_submits_no_orders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    summary = runtime_orchestrator.run_orchestrator(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        submit_paper_orders=False,
        client=client,
    )
    assert summary["submitted_orders"] == 0
    assert client.submitted_orders == []
    assert summary["live_orders_submitted"] is False


def test_runtime_submit_only_allowed_with_explicit_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    summary = runtime_orchestrator.run_orchestrator(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=0,
        max_loops=1,
        dry_run=False,
        submit_paper_orders=False,
        client=client,
    )
    assert summary["submitted_orders"] == 0
    assert client.submitted_orders == []


def test_target_version_idempotency_prevents_duplicate_orders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    summary = runtime_orchestrator.run_orchestrator(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        mode="paper",
        interval_seconds=0,
        max_loops=2,
        dry_run=False,
        submit_paper_orders=True,
        client=client,
    )
    assert summary["signals_generated"] == 2
    assert summary["submitted_orders"] == len(client.submitted_orders)
    assert len(client.submitted_orders) == 2
    assert summary["live_orders_submitted"] is False


def test_runtime_has_no_dependency_on_tournament_cache_runners_or_target_export() -> None:
    source = Path(runtime_orchestrator.__file__).read_text(encoding="utf-8")
    forbidden = ["run_backtest", "run_strategy_lab", "run_profit_exploration", "evidence/cache", "target export"]
    for text in forbidden:
        assert text not in source
    assert "trading_tournament." not in source
