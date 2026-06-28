from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution import freeze_successful_strategies as freeze

pytestmark = pytest.mark.alpaca_micro_live


def test_freeze_creates_yaml_python_source_trace_and_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module_root = tmp_path / "alpaca_micro_live_v1"
    (module_root / "runtime_strategies").mkdir(parents=True)
    registry = module_root / "runtime_strategies" / "runtime_strategy_registry.yaml"
    registry.write_text("version: 1\nstrategies: {}\n", encoding="utf-8")
    monkeypatch.setattr(freeze, "MODULE_ROOT", module_root)
    inventory = {
        "candidates": [
            {
                "strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
                "status_classification": "ready_to_freeze",
                "allowed_symbols": ["XLK", "XLF", "BIL"],
                "source_rule_files": ["fake_active_observation.yaml"],
            },
            {
                "strategy_id": "blocked_row",
                "status_classification": "onboarding_blocked",
                "exact_reason": "missing exact rules",
            },
        ]
    }
    updated = freeze.update_registry(registry, inventory)
    assert (module_root / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.yaml").exists()
    assert (module_root / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.py").exists()
    assert (module_root / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.source_trace.md").exists()
    row = updated["strategies"]["dsr_sector_equal_weight_defensive_filter_v1"]
    assert row["runtime_ready"] is True
    assert row["live_trading_allowed"] is False
    blocked = updated["strategies"]["blocked_row"]
    assert blocked["runtime_ready"] is False
    assert blocked["enabled"] is False


def test_frozen_dsr_spec_has_required_sections() -> None:
    spec = yaml.safe_load(
        Path("execution_lab/alpaca_micro_live_v1/runtime_strategies/dsr_sector_equal_weight_defensive_filter_v1.yaml").read_text(encoding="utf-8")
    )
    for key in ["strategy_id", "source_evidence", "universe", "indicators", "eligibility", "ranking", "portfolio", "rebalance", "constraints", "paper_runtime"]:
        assert key in spec
    assert spec["constraints"]["no_leverage"] is True
    assert spec["paper_runtime"]["enabled"] is True
