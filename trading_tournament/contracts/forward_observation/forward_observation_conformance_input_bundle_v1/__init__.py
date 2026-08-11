from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_ID = "forward_observation_conformance_input_bundle_v1"
SCHEMA_VERSION = 1
SELF_REFERENCE = "__NORMALIZED_SELF_REFERENCE__"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def normalized_bundle_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = item.relative_to(root).as_posix()
        content = item.read_bytes()
        if relative == "conformance_bundle_manifest.json":
            payload = json.loads(content.decode("utf-8"))
            payload["conformance_bundle_hash"] = SELF_REFERENCE
            content = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def validate_bundle(root: Path) -> dict[str, Any]:
    manifest_path = root / "conformance_bundle_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema_id", "schema_version", "bundle_id", "parent_handoff_id", "parent_package_hash",
        "strategy_id", "source_price_bundle_hash", "CPI_dataset_hash", "fixture_manifest_hash",
        "source_research_evidence_hash",
        "input_representation", "files", "fixture_count", "conformance_bundle_hash",
        "software_conformance_reference", "operational_market_data",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Conformance bundle manifest fields missing: {missing}")
    if payload["schema_id"] != SCHEMA_ID or int(payload["schema_version"]) != SCHEMA_VERSION:
        raise ValueError("Unsupported conformance bundle schema")
    if payload["software_conformance_reference"] is not True or payload["operational_market_data"] is not False:
        raise ValueError("Conformance inputs cannot be labeled operational market data")
    file_checks = {}
    for relative, expected in sorted(payload["files"].items()):
        path = root / relative
        actual = sha256_file(path) if path.is_file() else "missing"
        file_checks[relative] = {"expected": expected, "actual": actual, "match": actual == expected}
    observed_hash = normalized_bundle_hash(root)
    if not all(row["match"] for row in file_checks.values()) or observed_hash != payload["conformance_bundle_hash"]:
        raise ValueError("Conformance bundle integrity failure")
    for field in ("parent_package_hash", "source_price_bundle_hash", "CPI_dataset_hash", "fixture_manifest_hash", "source_research_evidence_hash", "conformance_bundle_hash"):
        if not SHA256.fullmatch(str(payload[field])):
            raise ValueError(f"Invalid hash field: {field}")
    return {"status": "pass", "manifest": payload, "file_checks": file_checks, "observed_bundle_hash": observed_hash}


__all__ = ["SCHEMA_ID", "SCHEMA_VERSION", "normalized_bundle_hash", "sha256_file", "validate_bundle"]
