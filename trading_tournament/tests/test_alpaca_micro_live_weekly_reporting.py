from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution import inspect_weekly_session
from execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError
from execution_lab.alpaca_micro_live_v1.execution import weekly_demo_runner as weekly
from tests.alpaca_micro_live_fakes import FakeRuntimeClient, fake_credentials, make_bars_by_symbol, write_runtime_files

pytestmark = pytest.mark.alpaca_micro_live


def _patch_weekly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(weekly, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(inspect_weekly_session, "WEEKLY_ROOT", tmp_path / "weekly")
    monkeypatch.setattr(weekly, "load_alpaca_credentials", lambda environment="paper": fake_credentials())
    weekly.STOP_FILE.unlink(missing_ok=True)
    weekly.EMERGENCY_STOP_FILE.unlink(missing_ok=True)


class ReconcileFillClient(FakeRuntimeClient):
    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        submitted = super().submit_order(**kwargs)
        return {**submitted, "id": "broker-fill-1", "status": "pending_new", "submitted_at": "2026-06-23T15:00:00Z"}

    def get_order_by_id(self, order_id: str) -> dict[str, Any]:
        return {
            "id": order_id,
            "status": "filled",
            "symbol": "BIL",
            "client_order_id": self.submitted_orders[0]["client_order_id"],
            "submitted_at": "2026-06-23T15:00:00Z",
            "filled_at": "2026-06-23T15:00:05Z",
            "filled_qty": "0.05",
            "filled_avg_price": "100.00",
        }


class DerivedFillClient(FakeRuntimeClient):
    def __init__(self) -> None:
        super().__init__(market_open=True)
        self.position_calls = 0

    def get_positions(self) -> list[dict[str, Any]]:
        self.position_calls += 1
        if self.position_calls == 1:
            return []
        return [{"symbol": "BIL", "qty": "0.05", "market_value": "5.00", "current_price": "100.00"}]

    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        submitted = super().submit_order(**kwargs)
        return {**submitted, "id": "broker-derived-1", "status": "pending_new", "submitted_at": "2026-06-23T15:00:00Z"}


class OpenOrderClient(FakeRuntimeClient):
    def list_open_orders(self) -> list[dict[str, Any]]:
        return [{"id": "open-1", "symbol": "BIL", "status": "accepted"}]


class MarketClockReadErrorClient(FakeRuntimeClient):
    def __init__(self, *, failures: int = 1) -> None:
        super().__init__(market_open=True)
        self.failures = failures
        self.clock_calls = 0

    def get_market_clock(self) -> dict[str, Any]:
        self.clock_calls += 1
        if self.clock_calls <= self.failures:
            raise BrokerError("network_error", "clock timeout")
        return super().get_market_clock()


class OrderStatusReadErrorClient(FakeRuntimeClient):
    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        submitted = super().submit_order(**kwargs)
        return {**submitted, "id": "broker-status-error-1", "status": "pending_new", "submitted_at": "2026-06-23T15:00:00Z"}

    def get_order_by_id(self, order_id: str) -> dict[str, Any]:
        raise BrokerError("network_error", "order status timeout")


class AmbiguousSubmitClient(FakeRuntimeClient):
    def submit_order(self, **kwargs: Any) -> dict[str, Any]:
        exc = BrokerError("network_error", "submit timeout", ambiguous_submission=True)
        exc.client_order_id = kwargs.get("client_order_id")
        exc.submission_attempt_id = "attempt-1"
        raise exc


def _set_read_policy(risk_path: Path, *, max_errors: int = 5) -> None:
    payload = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
    payload["weekly_runner_read_error_policy"] = {
        "fail_on_single_read_error": False,
        "max_consecutive_read_errors": max_errors,
        "read_error_backoff_seconds": 0,
        "mark_session_degraded_after_errors": 1,
    }
    risk_path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_daily_and_weekly_summary_write_expected_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    session_dir = Path(result["session_dir"])
    weekly_summary = json.loads((session_dir / "weekly_summary.json").read_text(encoding="utf-8"))
    daily_jsons = list(session_dir.glob("daily_summary_*.json"))
    assert daily_jsons
    daily = json.loads(daily_jsons[0].read_text(encoding="utf-8"))
    for payload in [weekly_summary, daily]:
        assert payload["session_id"] == session_dir.name
        assert payload["live_orders_submitted"] is False
    assert "submitted_orders" in weekly_summary
    assert "signals" in daily
    for name in weekly.EVENT_FILES:
        assert (session_dir / name).exists(), name


def test_weekly_state_is_running_during_active_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    seen_status: list[str] = []

    def bars_fetcher(_client: Any, *, symbols, **_kwargs):
        session_dir = next((tmp_path / "weekly").glob("weekly_demo_*"))
        state = json.loads((session_dir / "weekly_session_state.json").read_text(encoding="utf-8"))
        seen_status.append(state["status"])
        return make_bars_by_symbol(symbols=symbols)

    weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=bars_fetcher,
    )
    assert "running" in seen_status


def test_order_status_reconciliation_writes_broker_confirmed_fills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    client = ReconcileFillClient()
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=False,
        submit_paper_orders=True,
        client=client,
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )
    session_dir = Path(result["session_dir"])
    fills = (session_dir / "fills.jsonl").read_text(encoding="utf-8")
    assert "broker_confirmed" in fills
    assert "fill_latency_seconds" in fills
    assert "broker-fill-1" in (session_dir / "order_statuses.jsonl").read_text(encoding="utf-8")


def test_open_orders_are_tracked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=OpenOrderClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["open_orders"] == 1


def test_position_derived_fill_is_marked_derived_not_broker_confirmed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=False,
        submit_paper_orders=True,
        client=DerivedFillClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )
    derived = Path(result["session_dir"], "position_derived_fills.jsonl").read_text(encoding="utf-8")
    assert "derived_from_position_snapshot" in derived
    assert '"broker_confirmed": false' in derived


def test_heartbeat_gap_is_recorded_on_resume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    session_dir = tmp_path / "weekly" / "weekly_demo_gap"
    session_dir.mkdir(parents=True)
    weekly.write_empty_event_files(session_dir)
    old_heartbeat = "2026-06-23T15:00:00Z"
    weekly.append_jsonl(session_dir / "heartbeat.jsonl", {"loop": 1, "live_orders_submitted": False})
    weekly.write_json(
        session_dir / "weekly_session_state.json",
        {"session_id": session_dir.name, "loop_count": 1, "last_heartbeat_utc": old_heartbeat, "handled_target_versions": []},
    )
    weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=30,
        max_loops=2,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
        resume=session_dir,
    )
    assert "pc_sleep_or_process_pause_or_network_delay" in (session_dir / "observation_gaps.jsonl").read_text(encoding="utf-8")


def test_resume_stop_file_blocks_cleanly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    session_dir = tmp_path / "weekly" / "weekly_demo_stop"
    session_dir.mkdir(parents=True)
    weekly.STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    weekly.STOP_FILE.write_text("stop\n", encoding="utf-8")
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        max_loops=1,
        submit_paper_orders=True,
        dry_run=False,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
        resume=session_dir,
    )
    assert result["message"] == "resume_blocked_stop_file_present"
    assert result["submitted_orders"] == 0
    weekly.STOP_FILE.unlink(missing_ok=True)


def test_resume_placeholder_path_fails_clearly(tmp_path: Path) -> None:
    config, risk, registry = write_runtime_files(tmp_path)
    with pytest.raises(ValueError, match="resume_path_contains_placeholder_timestamp"):
        weekly.run_weekly_demo(
            config_path=config,
            risk_limits_path=risk,
            runtime_registry_path=registry,
            strategies=["vm_quality_lowvol_proxy_v1"],
            max_loops=1,
            dry_run=True,
            client=FakeRuntimeClient(),
            bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
            resume=Path("weekly_demo_<timestamp>"),
        )


def test_inspect_weekly_session_latest_prints_compact_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    inspect_weekly_session.main(["--latest"])
    output = capsys.readouterr().out
    assert "session_id=" in output
    assert "live_orders_submitted=false" in output
    assert "submitted_orders=0" in output


def test_single_market_clock_timeout_degrades_not_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk)
    client = MarketClockReadErrorClient(failures=1)
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
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "degraded_running"
    assert state["consecutive_read_errors"] == 1
    assert state["last_read_error_operation"] == "market_clock"
    assert client.submitted_orders == []


def test_successful_next_loop_clears_degraded_read_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=MarketClockReadErrorClient(failures=1),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["consecutive_read_errors"] == 0
    assert state["last_read_error_operation"] is None


def test_consecutive_read_errors_below_threshold_do_not_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk, max_errors=3)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=MarketClockReadErrorClient(failures=2),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "degraded_running"
    assert state["consecutive_read_errors"] == 2


def test_consecutive_read_errors_at_threshold_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk, max_errors=2)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=MarketClockReadErrorClient(failures=2),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["consecutive_read_errors"] == 2


def test_historical_data_failure_skips_affected_strategy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, _registry = write_runtime_files(tmp_path)
    _set_read_policy(risk)

    def bars_fetcher(_client: Any, *, symbols, **_kwargs):
        if "XLK" in symbols:
            raise BrokerError("network_error", "historical timeout")
        return make_bars_by_symbol(symbols=symbols)

    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=weekly.MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml",
        strategies=["all_runtime_ready"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=bars_fetcher,
    )
    session_dir = Path(result["session_dir"])
    state = json.loads((session_dir / "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "degraded_running"
    assert state["last_read_error_operation"] == "historical_data"
    assert "historical_data_failed_skip_strategy" in (session_dir / "runtime_blocks.jsonl").read_text(encoding="utf-8")
    assert len(state["handled_target_versions"]) == 1


def test_order_status_read_failure_does_not_resubmit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk)
    client = OrderStatusReadErrorClient()
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=False,
        submit_paper_orders=True,
        client=client,
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )
    state = json.loads(Path(result["session_dir"], "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["last_read_error_operation"] == "order_status"
    assert len(client.submitted_orders) == 1


def test_order_submit_network_failure_still_fails_closed_ambiguous(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    result = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=False,
        submit_paper_orders=True,
        client=AmbiguousSubmitClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )
    session_dir = Path(result["session_dir"])
    state = json.loads((session_dir / "weekly_session_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert "ambiguous_submission" in (session_dir / "broker_errors.jsonl").read_text(encoding="utf-8")


def test_resume_allowed_after_read_only_safe_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk, max_errors=1)
    first = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=MarketClockReadErrorClient(failures=1),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    session_dir = Path(first["session_dir"])
    assert inspect_weekly_session.inspect_session(session_dir)["resume_allowed"] is True
    second = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
        resume=session_dir,
    )
    assert second["runtime_blocked"] is False


def test_resume_blocked_after_unresolved_submit_ambiguity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    first = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=False,
        submit_paper_orders=True,
        client=AmbiguousSubmitClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(eligible=False, symbols=symbols),
    )
    session_dir = Path(first["session_dir"])
    status = inspect_weekly_session.inspect_session(session_dir)
    assert status["unresolved_order_submit_ambiguity"] is True
    assert status["resume_allowed"] is False
    second = weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=2,
        dry_run=True,
        client=FakeRuntimeClient(),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
        resume=session_dir,
    )
    assert second["message"] == "resume_blocked_unresolved_order_submit_ambiguity"


def test_inspect_reports_read_error_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _patch_weekly(monkeypatch, tmp_path)
    config, risk, registry = write_runtime_files(tmp_path)
    _set_read_policy(risk)
    weekly.run_weekly_demo(
        config_path=config,
        risk_limits_path=risk,
        runtime_registry_path=registry,
        strategies=["vm_quality_lowvol_proxy_v1"],
        interval_seconds=0,
        max_loops=1,
        dry_run=True,
        client=MarketClockReadErrorClient(failures=1),
        bars_fetcher=lambda _client, *, symbols, **_kwargs: make_bars_by_symbol(symbols=symbols),
    )
    inspect_weekly_session.main(["--latest"])
    output = capsys.readouterr().out
    assert "consecutive_read_errors=1" in output
    assert "last_read_error_operation=market_clock" in output
    assert "resume_allowed=True" not in output
    assert "resume_allowed=true" in output
