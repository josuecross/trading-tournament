from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.package_hashing import sha256_file


def write_fake_handoff_package(
    root: Path,
    *,
    package_id: str = "fake_standard_handoff_v1",
    strategy_id: str = "fake_strategy_v1",
    calculator_type: str = "fake_static_calculator_v1",
    instruments: list[str] | None = None,
    expected_weights: dict[str, float] | None = None,
    include_fixture: bool = True,
    omit_manifest_package_id: bool = False,
) -> Path:
    package = root / package_id / "latest" / "package"
    package.mkdir(parents=True, exist_ok=True)
    expected_weights = expected_weights or {"SPY": 1.0}
    instruments = instruments or list(expected_weights)
    contract: dict[str, Any] = {
        "identity": {"strategy_id": strategy_id, "family_id": "fake_family_v1", "version": "v1"},
        "calculator_type": calculator_type,
        "target_output": "target_weights",
        "tradable_instruments": {"symbols": instruments},
        "data_semantics": {"fields": ["adjusted_close"], "frequency": "daily"},
        "schedule": {"signal": "completed_regular_session"},
    }
    fixture = {
        "calculator_contract_version": calculator_type,
        "strategy_id": strategy_id,
        "fixture_count": 1,
        "fixtures": [
            {
                "fixture_id": "fixture_1",
                "inputs": {"target_weights": expected_weights},
                "prior_state": {},
                "absolute_tolerance": 1e-12,
                "expected": {"status": "target_calculated", "target_weights": expected_weights},
            }
        ],
    }
    (package / "strategy_rule_contract.json").write_text(json.dumps(contract, sort_keys=True), encoding="utf-8")
    if include_fixture:
        (package / "golden_conformance_fixtures.json").write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
    files = {"strategy_rule_contract.json": sha256_file(package / "strategy_rule_contract.json")}
    if include_fixture:
        files["golden_conformance_fixtures.json"] = sha256_file(package / "golden_conformance_fixtures.json")
    manifest = {
        "files": files,
        "schema_id": "forward_observation_handoff_standard_v1",
        "schema_version": 1,
        "package_content_hash": "sha256:fake",
        "strategy_id": strategy_id,
        "family_id": "fake_family_v1",
    }
    if not omit_manifest_package_id:
        manifest["package_id"] = package_id
    (package / "package_manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return package


def fake_calculator(inputs: dict[str, Any], _prior_state: dict[str, Any]) -> dict[str, Any]:
    return {"status": "target_calculated", "target_weights": inputs["target_weights"]}
