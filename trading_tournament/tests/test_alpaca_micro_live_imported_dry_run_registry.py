from __future__ import annotations

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution.imported_strategy_dry_run import write_dry_run_registry
from execution_lab.alpaca_micro_live_v1.execution.weekly_demo_runner import resolve_runtime_ready

pytestmark = pytest.mark.alpaca_micro_live


def _write_spec(root, strategy_id: str, package_id: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{strategy_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "strategy_id": strategy_id,
                "handoff_package_id": package_id,
                "enabled": False,
                "runtime_ready": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "conformance": {"status": "fixture_passed"},
            }
        ),
        encoding="utf-8",
    )


def test_first_batch_is_registered_dry_run_only(tmp_path) -> None:
    generated = tmp_path / "generated"
    _write_spec(generated, "ice_vaneck_us_fallen_angel_angl_v1", "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1")
    _write_spec(generated, "schwoerer_hyg_ema100_spy_bil_v1", "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1")
    _write_spec(generated, "barbara_decelerated_psar_spy_bil_v1", "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1")
    _write_spec(generated, "factory_v1_spy_trend_quality_state_d1", "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1")
    path = write_dry_run_registry(tmp_path / "dry_run_import_registry.yaml", generated)
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(registry["strategies"]) == 4
    assert registry["all_runtime_ready_member"] is False
    for row in registry["strategies"]:
        assert row["dry_run_enabled"] is True
        assert row["runtime_ready"] is False
        assert row["paper_trading_allowed"] is False
        assert row["live_trading_allowed"] is False
        assert row["paper_submit_allowed"] is False


def test_imported_strategies_are_not_in_all_runtime_ready() -> None:
    registry = {
        "strategies": {
            "vm_quality_lowvol_proxy_v1": {"enabled": True, "runtime_ready": True, "paper_trading_allowed": True, "live_trading_allowed": False},
            "ice_vaneck_us_fallen_angel_angl_v1": {"enabled": False, "runtime_ready": False, "paper_trading_allowed": False, "live_trading_allowed": False},
        }
    }
    assert resolve_runtime_ready(registry, ["all_runtime_ready"]) == ["vm_quality_lowvol_proxy_v1"]


def test_dry_run_registry_does_not_modify_active_vm_dsr_registry(tmp_path) -> None:
    active_registry = yaml.safe_load(open("execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml", encoding="utf-8"))
    write_dry_run_registry(tmp_path / "dry_run_import_registry.yaml", tmp_path / "generated")
    after = yaml.safe_load(open("execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml", encoding="utf-8"))
    assert after == active_registry
