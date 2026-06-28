from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution import weekly_demo_runner as weekly
from tests.alpaca_micro_live_fakes import FakeRuntimeClient, fake_credentials, make_bars_by_symbol, write_runtime_files

pytestmark = pytest.mark.alpaca_micro_live


def _clean_stops() -> None:
    weekly.STOP_FILE.unlink(missing_ok=True)
    weekly.EMERGENCY_STOP_FILE.unlink(missing_ok=True)


def _patch_weekly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_stops()
    monkeypatch.setattr(weekly, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(weekly, "load_alpaca_credentials", lambda environment="paper": fake_credentials())


def _bars_fetcher(_client, *, symbols, **_kwargs):
    return make_bars_by_symbol(symbols=symbols)


def test_all_runtime_ready_resolves_only_enabled_ready_paper_allowed() -> None:
    registry = {
        "strategies": {
            "ready": {"enabled": True, "runtime_ready": True, "paper_trading_allowed": True, "live_trading_allowed": False},
            "blocked": {"enabled": False, "runtime_ready": False, "paper_trading_allowed": False, "live_trading_allowed": False},
            "live": {"enabled": True, "runtime_ready": True, "paper_trading_allowed": True, "live_trading_allowed": True},
        }
    }
    assert weekly.resolve_runtime_ready(registry, ["all_runtime_ready"]) == ["ready"]


def test_weekly_dry_run_submits_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["all_runtime_ready"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        submit_paper_orders=False,
        client=client,
        bars_fetcher=_bars_fetcher,
    )
    assert result["submitted_orders"] == 0
    assert client.submitted_orders == []
    assert Path(result["session_dir"], "weekly_summary.json").exists()


def test_weekly_submit_respects_market_closed_risk_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path, require_market_open=True)
    client = FakeRuntimeClient(market_open=False)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=False,
        submit_paper_orders=True,
        client=client,
        bars_fetcher=_bars_fetcher,
    )
    assert result["submitted_orders"] == 0
    assert "market_closed_submit_blocked" in Path(result["session_dir"], "runtime_blocks.jsonl").read_text(encoding="utf-8")


def test_shared_risk_symbols_fail_closed_for_submit(tmp_path: Path) -> None:
    config, risk, registry = write_runtime_files(tmp_path)
    registry.write_text(
        yaml.safe_dump(
            {
                "strategies": {
                    "a": {"enabled": True, "runtime_ready": True, "paper_trading_allowed": True, "live_trading_allowed": False, "runtime_spec": "runtime_strategies/vm_quality_lowvol_proxy_v1.yaml", "runtime_module": "runtime_strategies/vm_quality_lowvol_proxy_v1.py", "allowed_symbols": ["SPLV", "USMV", "QUAL", "SPY", "BIL"]},
                    "b": {"enabled": True, "runtime_ready": True, "paper_trading_allowed": True, "live_trading_allowed": False, "runtime_spec": "runtime_strategies/vm_quality_lowvol_proxy_v1.yaml", "runtime_module": "runtime_strategies/vm_quality_lowvol_proxy_v1.py", "allowed_symbols": ["SPLV", "USMV", "QUAL", "SPY", "BIL"]},
                }
            }
        ),
        encoding="utf-8",
    )
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["all_runtime_ready"],
        max_loops=1,
        submit_paper_orders=True,
        dry_run=False,
        client=FakeRuntimeClient(),
        bars_fetcher=_bars_fetcher,
    )
    assert result["runtime_blocked"] is True
    assert any("blocked_shared_risk_symbol" in reason for reason in result["block_reasons"])


def test_within_tolerance_goes_to_skipped_orders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    client.get_positions = lambda: [{"symbol": "SPY", "market_value": "12.50"}, {"symbol": "USMV", "market_value": "12.50"}]
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=client,
        bars_fetcher=_bars_fetcher,
    )
    assert "within_tolerance" in Path(result["session_dir"], "skipped_orders.jsonl").read_text(encoding="utf-8")


def test_target_version_already_handled_goes_to_runtime_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = FakeRuntimeClient(market_open=True)
    first = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=client,
        bars_fetcher=_bars_fetcher,
    )
    second = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=client,
        bars_fetcher=_bars_fetcher,
        resume=Path(first["session_dir"]),
    )
    assert first["session_dir"] == second["session_dir"]
    assert "target_version_already_handled" in Path(second["session_dir"], "runtime_blocks.jsonl").read_text(encoding="utf-8")


def test_stop_and_emergency_stop_files_stop_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    weekly.STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    weekly.STOP_FILE.write_text("stop\n", encoding="utf-8")
    stopped = weekly.run_weekly_demo(config_path=config, risk_limits_path=risk, runtime_registry_path=registry, strategies=["vm_quality_lowvol_proxy_v1"], max_loops=1, client=FakeRuntimeClient(), bars_fetcher=_bars_fetcher)
    assert "stop_file_present" in Path(stopped["session_dir"], "runtime_blocks.jsonl").read_text(encoding="utf-8")
    _clean_stops()
    weekly.EMERGENCY_STOP_FILE.write_text("emergency\n", encoding="utf-8")
    emergency = weekly.run_weekly_demo(config_path=config, risk_limits_path=risk, runtime_registry_path=registry, strategies=["vm_quality_lowvol_proxy_v1"], max_loops=1, submit_paper_orders=True, dry_run=False, client=FakeRuntimeClient(), bars_fetcher=_bars_fetcher)
    assert emergency["submitted_orders"] == 0
    assert "emergency_stop_file_present" in Path(emergency["session_dir"], "runtime_blocks.jsonl").read_text(encoding="utf-8")
    _clean_stops()


def test_weekly_runner_has_no_tournament_runtime_dependency() -> None:
    source = Path(weekly.__file__).read_text(encoding="utf-8")
    for forbidden in ["run_backtest", "run_strategy_lab", "run_profit_exploration", "evidence/cache", "target_export"]:
        assert forbidden not in source
