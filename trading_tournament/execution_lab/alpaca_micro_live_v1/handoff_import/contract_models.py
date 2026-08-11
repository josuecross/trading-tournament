from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HandoffPackage:
    package_id: str
    strategy_id: str
    family_id: str
    package_version: str
    schema_id: str
    package_root: Path
    manifest_path: Path | None
    contract_path: Path | None
    fixture_path: Path | None
    required_instruments: list[str] = field(default_factory=list)
    required_data_fields: list[str] = field(default_factory=list)
    schedule: str = ""
    target_output: str = ""
    calculator_type: str = ""
    provider_requirements: list[str] = field(default_factory=list)
    package_hash: str = ""
    source_hashes: dict[str, str] = field(default_factory=dict)
    source_evidence_references: list[str] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    contract: dict[str, Any] = field(default_factory=dict)
    fixtures: dict[str, Any] = field(default_factory=dict)
    classifications: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompatibilityReport:
    package_id: str
    strategy_id: str
    import_status: str
    calculator_status: str
    provider_status: str
    conformance_status: str
    blocked_reasons: list[str]
    unsupported_reasons: list[str]
    manual_review_reasons: list[str]


@dataclass(frozen=True)
class ImportResult:
    package: HandoffPackage
    compatibility: CompatibilityReport
    generated_spec_path: Path | None = None
    immutable_cache_path: Path | None = None
    conformance_report_path: Path | None = None
