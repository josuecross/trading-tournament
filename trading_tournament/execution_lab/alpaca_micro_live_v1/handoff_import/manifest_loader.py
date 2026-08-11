from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.contract_models import HandoffPackage
from execution_lab.alpaca_micro_live_v1.handoff_import.package_hashing import hash_existing_files, sha256_file

MANIFEST_CANDIDATES = ("package_manifest.json", "handoff_manifest.json", "handoff.json")
CONTRACT_CANDIDATES = (
    "strategy_rule_contract.json",
    "forward_observation_interface_contract.json",
    "strategy_contract.json",
    "signal_contract.json",
)
FIXTURE_CANDIDATES = ("golden_conformance_fixtures.json", "golden_fixture_manifest.json", "golden_conformance_fixtures.csv")

MANIFEST_REQUIRED = ("package_id", "strategy_id")
CONTRACT_REQUIRED = ("calculator_type", "target_output")


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists() or path.suffix.lower() != ".json":
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    if path.suffix.lower() == ".json":
        return load_json(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return {"fixtures": list(csv.DictReader(handle)), "fixture_count": sum(1 for _ in path.open(encoding="utf-8")) - 1}
    return {}


def find_first(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = root / name
        if path.exists():
            return path
    for name in names:
        matches = sorted(root.rglob(name))
        if matches:
            return matches[0]
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (str, int, float)):
            text = str(value)
            if text:
                return text
    return ""


def _unique_strings(values: Any) -> list[str]:
    found: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            if value and value not in found:
                found.append(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                if isinstance(key, str) and key.isupper() and key not in found:
                    found.append(key)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(values)
    return found


def _required_data_fields(contract: dict[str, Any]) -> list[str]:
    text = json.dumps(contract, sort_keys=True).lower()
    fields = []
    for token in ("close", "adjusted_close", "total_return", "vix", "vix3m", "curve", "cpi", "returns"):
        if token in text:
            fields.append(token)
    return fields


def _calculator_type(contract: dict[str, Any], fixtures: dict[str, Any]) -> str:
    signal = contract.get("signal_calculation", {})
    return _first_text(
        fixtures.get("calculator_contract_version"),
        contract.get("calculator_type"),
        signal.get("calculator_type") if isinstance(signal, dict) else "",
        signal.get("type") if isinstance(signal, dict) else "",
        contract.get("calculator_contract_version"),
    )


def _target_output(contract: dict[str, Any], fixtures: dict[str, Any]) -> str:
    if "target_weights" in json.dumps(fixtures):
        return "target_weights"
    if "target_weights" in json.dumps(contract):
        return "target_weights"
    return _first_text(contract.get("target_output"), contract.get("target_output_type"))


def _schedule(contract: dict[str, Any]) -> str:
    schedule = contract.get("schedule") or contract.get("calculation_schedule") or contract.get("schedule_and_timing")
    if isinstance(schedule, dict):
        return ";".join(f"{key}={value}" for key, value in sorted(schedule.items()))
    return _first_text(schedule)


def _provider_requirements(contract: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    text = json.dumps({"manifest": manifest, "contract": contract}, sort_keys=True).lower()
    text = text.replace("frozen_current_active_vm_dsr_usci_combo", "frozen_reference_virtual_sleeve")
    providers = []
    for token in ("alpaca", "vix", "vix3m", "commodity", "usci", "curve", "cpi", "inflation", "frozen_reference"):
        if token in text:
            providers.append(token)
    if not providers:
        providers.append("alpaca_equity_etf_daily_bars")
    return providers


def load_handoff_package(package_root: Path) -> HandoffPackage:
    manifest_path = find_first(package_root, MANIFEST_CANDIDATES)
    contract_path = find_first(package_root, CONTRACT_CANDIDATES)
    fixture_path = find_first(package_root, FIXTURE_CANDIDATES)
    manifest = load_json(manifest_path)
    handoff_document = load_json(package_root / "handoff.json")
    envelope = handoff_document.get("envelope", {}) if isinstance(handoff_document.get("envelope"), dict) else {}
    contract = load_json(contract_path)
    fixtures = load_fixture(fixture_path)

    identity = contract.get("identity", {}) if isinstance(contract.get("identity"), dict) else {}
    package_id = _first_text(
        manifest.get("package_id"),
        manifest.get("handoff_id"),
        envelope.get("package_id"),
        envelope.get("handoff_id"),
        fixtures.get("fixture_set_id", "").replace("__golden_fixtures_v1", ""),
        package_root.parents[1].name if package_root.parent.name == "latest" else package_root.name,
    )
    strategy_id = _first_text(manifest.get("strategy_id"), envelope.get("strategy_id"), identity.get("strategy_id"), fixtures.get("strategy_id"), package_id.replace("_standard_handoff_v1", ""))
    family_id = _first_text(manifest.get("family_id"), envelope.get("family_id"), identity.get("family_id"), identity.get("architecture_id"))
    version = _first_text(manifest.get("package_version"), manifest.get("handoff_version"), envelope.get("handoff_version"), manifest.get("schema_version"), identity.get("version"), "v1")
    schema_id = _first_text(manifest.get("schema_id"), manifest.get("package_schema_version"), envelope.get("schema_id"), contract.get("schema_id"))
    source_hashes = hash_existing_files({"manifest": manifest_path, "contract": contract_path, "fixture": fixture_path})

    classifications = []
    if not manifest_path:
        classifications.append("manifest_missing")
    if not contract_path:
        classifications.append("contract_missing")
    if not fixture_path:
        classifications.append("fixture_missing")
    if not manifest.get("package_content_hash"):
        classifications.append("hash_unavailable")
    if not manifest.get("package_id") and not manifest.get("handoff_id") and not envelope.get("package_id") and not envelope.get("handoff_id"):
        classifications.append("manifest_missing_required_field")
    if not manifest.get("strategy_id") and not envelope.get("strategy_id") and not identity.get("strategy_id") and not fixtures.get("strategy_id"):
        classifications.append("manifest_missing_required_field")

    calculator_type = _calculator_type(contract, fixtures)
    target_output = _target_output(contract, fixtures)
    if not calculator_type:
        classifications.append("contract_missing_required_field")
    if not target_output:
        classifications.append("contract_missing_required_field")
    if contract_path and not any(key in contract for key in ("calculator_type", "target_output", "portfolio_construction", "signal_calculation", "tradable_instruments")):
        classifications.append("contract_missing_required_field")

    return HandoffPackage(
        package_id=package_id,
        strategy_id=strategy_id,
        family_id=family_id,
        package_version=version,
        schema_id=schema_id,
        package_root=package_root,
        manifest_path=manifest_path,
        contract_path=contract_path,
        fixture_path=fixture_path,
        required_instruments=_unique_strings(contract.get("tradable_instruments") or contract.get("required_instruments") or contract.get("portfolio_construction") or contract),
        required_data_fields=_required_data_fields(contract),
        schedule=_schedule(contract),
        target_output=target_output,
        calculator_type=calculator_type,
        provider_requirements=_provider_requirements(contract, manifest),
        package_hash=_first_text(manifest.get("package_content_hash"), manifest.get("package_hash")),
        source_hashes=source_hashes,
        source_evidence_references=_unique_strings(manifest.get("source_evidence_references") or manifest.get("research_evidence_hash") or []),
        manifest=manifest,
        contract=contract,
        fixtures=fixtures,
        classifications=classifications,
    )


def validate_manifest_hashes(package: HandoffPackage) -> list[str]:
    problems = []
    files = package.manifest.get("files", {}) if isinstance(package.manifest.get("files"), dict) else {}
    for name, expected_hash in files.items():
        if name == "handoff.json" and "normalized_handoff_self_reference" in package.manifest.get("hash_algorithm", ""):
            continue
        path = package.package_root / name
        if not path.exists():
            problems.append(f"missing_manifest_file:{name}")
            continue
        actual = sha256_file(path)
        if expected_hash and actual != expected_hash:
            problems.append(f"hash_mismatch:{name}")
    if not package.package_hash:
        problems.append("hash_unavailable")
    return problems


def write_immutable_cache(package: HandoffPackage, cache_root: Path) -> Path:
    target = cache_root / package.package_id
    target.mkdir(parents=True, exist_ok=True)
    copies = {
        "source_manifest_copy": package.manifest_path,
        "source_contract_copy": package.contract_path,
        "source_fixture_copy": package.fixture_path,
    }
    copied = {}
    for stem, source in copies.items():
        if source and source.exists():
            dest = target / f"{stem}{source.suffix}"
            shutil.copy2(_fs_path(source), _fs_path(dest))
            copied[stem] = {"source_path": str(source), "copy_path": str(dest), "source_hash": sha256_file(source)}
    hash_report = {"package_id": package.package_id, "package_hash": package.package_hash, "source_hashes": package.source_hashes, "copied_files": copied}
    _write_text(target / "hash_report.json", json.dumps(hash_report, indent=2, sort_keys=True) + "\n")
    lines = [
        f"package_id: {package.package_id}",
        f"strategy_id: {package.strategy_id}",
        f"source_package_path: {package.package_root}",
        f"package_hash: {package.package_hash}",
        "source_hashes:",
    ]
    for key, value in package.source_hashes.items():
        lines.append(f"  {key}: {value}")
    _write_text(target / "import_manifest.yaml", "\n".join(lines) + "\n")
    return target


def _fs_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def _write_text(path: Path, text: str) -> None:
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)
