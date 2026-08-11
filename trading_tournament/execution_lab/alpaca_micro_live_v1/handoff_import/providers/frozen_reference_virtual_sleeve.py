from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT

DEFAULT_IMMUTABLE_ROOT = MODULE_ROOT / "evidence" / "handoff_imports" / "immutable_packages"
SUPPORTED_SCHEMA = "frozen_reference_virtual_sleeve_v1"


@dataclass(frozen=True)
class FrozenReferenceResult:
    status: str
    package_id: str
    source_path: str
    target_weights: dict[str, float]
    lineage_hashes: dict[str, str]
    blocked_reason: str


def load_frozen_reference(package_id: str, immutable_root: Path = DEFAULT_IMMUTABLE_ROOT) -> FrozenReferenceResult:
    package_root = immutable_root / package_id
    source = package_root / "frozen_reference_virtual_sleeve.json"
    hash_report = package_root / "hash_report.json"
    if not source.exists():
        return FrozenReferenceResult(
            status="provider_data_missing",
            package_id=package_id,
            source_path=str(source),
            target_weights={},
            lineage_hashes=_load_hashes(hash_report),
            blocked_reason="frozen_reference_source_missing",
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_id") != SUPPORTED_SCHEMA:
        return FrozenReferenceResult(
            status="provider_data_manual_review_required",
            package_id=package_id,
            source_path=str(source),
            target_weights={},
            lineage_hashes=_load_hashes(hash_report),
            blocked_reason="frozen_reference_schema_unsupported",
        )
    target_weights = payload.get("target_weights")
    if not isinstance(target_weights, dict):
        return FrozenReferenceResult(
            status="provider_data_missing",
            package_id=package_id,
            source_path=str(source),
            target_weights={},
            lineage_hashes=_load_hashes(hash_report),
            blocked_reason="frozen_reference_source_missing",
        )
    return FrozenReferenceResult(
        status="provider_data_available",
        package_id=package_id,
        source_path=str(source),
        target_weights={str(symbol): float(weight) for symbol, weight in target_weights.items()},
        lineage_hashes=_load_hashes(hash_report),
        blocked_reason="",
    )


def _load_hashes(hash_report: Path) -> dict[str, str]:
    if not hash_report.exists():
        return {}
    try:
        payload: dict[str, Any] = json.loads(hash_report.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    hashes = payload.get("source_hashes")
    return hashes if isinstance(hashes, dict) else {}
