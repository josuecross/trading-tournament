from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution.implement_first_batch_calculators import run_first_batch
from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.conformance import run_conformance
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import load_handoff_package
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def _write_ice_fake(root: Path, *, expected_weights: dict[str, float] | None = None, include_fixture: bool = True) -> Path:
    expected_weights = expected_weights or {"ANGL": 0.2, "FROZEN_REFERENCE": 0.8}
    package_root = write_fake_handoff_package(
        root,
        package_id="ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1",
        strategy_id="ice_vaneck_us_fallen_angel_angl_v1",
        calculator_type="angl_80_20_monthly_calculator_v1",
        instruments=["ANGL", "FROZEN_REFERENCE"],
        expected_weights=expected_weights,
        include_fixture=include_fixture,
    )
    (package_root / "strategy_rule_contract.json").write_text(
        json.dumps(
            {
                "identity": {"strategy_id": "ice_vaneck_us_fallen_angel_angl_v1", "family_id": "fallen_angel_credit_anomaly"},
                "calculator_type": "angl_80_20_monthly_calculator_v1",
                "target_output": "target_weights",
                "portfolio_construction": {"outer_targets": {"ANGL": 0.2, "FROZEN_REFERENCE": 0.8}},
                "tradable_instruments": {"candidate": "ANGL", "outer_reference": "FROZEN_REFERENCE"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    if include_fixture:
        fixture = json.loads((package_root / "golden_conformance_fixtures.json").read_text(encoding="utf-8"))
        fixture["fixtures"][0]["expected"] = {
            "effective_timestamp": "2000-02-01T16:00:00-05:00",
            "intermediate_calculations": {},
            "status": "target_calculated",
            "target_weights": expected_weights,
        }
        (package_root / "golden_conformance_fixtures.json").write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
    return package_root


def test_missing_fixture_blocks_conformance(tmp_path) -> None:
    package = load_handoff_package(_write_ice_fake(tmp_path, include_fixture=False))
    result = run_conformance(package, CalculatorRegistry())
    assert result["status"] == "fixture_missing"


def test_fixture_pass_updates_generated_spec_only_to_disabled_conformance_passed(tmp_path) -> None:
    _write_ice_fake(tmp_path / "handoffs")
    result = run_first_batch(
        handoff_root=tmp_path / "handoffs",
        evidence_dir=tmp_path / "evidence",
        conformance_dir=tmp_path / "conformance",
        generated_spec_dir=tmp_path / "generated",
        dry_run=False,
        write_bindings=True,
        run_conformance_gate=True,
    )
    spec = yaml.safe_load((tmp_path / "generated" / "ice_vaneck_us_fallen_angel_angl_v1.yaml").read_text(encoding="utf-8"))
    assert result["fixture_passed"] == 1
    assert spec["import_status"] == "conformance_passed_disabled"
    assert spec["enabled"] is False
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False


def test_fixture_failure_leaves_generated_spec_disabled_and_blocked(tmp_path) -> None:
    _write_ice_fake(tmp_path / "handoffs", expected_weights={"ANGL": 0.1, "FROZEN_REFERENCE": 0.9})
    result = run_first_batch(
        handoff_root=tmp_path / "handoffs",
        evidence_dir=tmp_path / "evidence",
        conformance_dir=tmp_path / "conformance",
        generated_spec_dir=tmp_path / "generated",
        dry_run=False,
        write_bindings=True,
        run_conformance_gate=True,
    )
    spec = yaml.safe_load((tmp_path / "generated" / "ice_vaneck_us_fallen_angel_angl_v1.yaml").read_text(encoding="utf-8"))
    assert result["blocked_calculators"] == 1
    assert spec["import_status"] == "blocked"
    assert spec["enabled"] is False
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False
