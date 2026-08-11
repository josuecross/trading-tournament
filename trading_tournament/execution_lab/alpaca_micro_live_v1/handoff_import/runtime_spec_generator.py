from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.handoff_import.contract_models import CompatibilityReport, HandoffPackage

GENERATED_SPEC_ROOT = MODULE_ROOT / "runtime_strategies" / "generated"


def spec_payload(package: HandoffPackage, compatibility: CompatibilityReport) -> dict[str, Any]:
    blocked = compatibility.blocked_reasons or ["pending_conformance_gate"]
    return {
        "strategy_id": package.strategy_id,
        "handoff_package_id": package.package_id,
        "source": "standard_v1_handoff_import",
        "runtime_version": "alpaca_runtime_v1",
        "enabled": False,
        "runtime_ready": False,
        "paper_trading_allowed": False,
        "live_trading_allowed": False,
        "import_status": compatibility.import_status,
        "calculator_binding": compatibility.calculator_status,
        "provider_requirements": package.provider_requirements,
        "required_instruments": package.required_instruments,
        "required_data_fields": package.required_data_fields,
        "schedule": package.schedule,
        "target_output": package.target_output,
        "source_hashes": package.source_hashes,
        "conformance": {"status": compatibility.conformance_status},
        "blocked_reason": ";".join(blocked),
    }


def write_disabled_spec(package: HandoffPackage, compatibility: CompatibilityReport, output_root: Path = GENERATED_SPEC_ROOT) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{package.strategy_id}.yaml"
    path.write_text(yaml.safe_dump(spec_payload(package, compatibility), sort_keys=False), encoding="utf-8")
    return path


def write_import_registry(rows: list[dict[str, Any]], output_root: Path = GENERATED_SPEC_ROOT) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "import_registry.yaml"
    payload = {
        "source": "standard_v1_handoff_import",
        "enabled": False,
        "runtime_ready": False,
        "strategies": rows,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
