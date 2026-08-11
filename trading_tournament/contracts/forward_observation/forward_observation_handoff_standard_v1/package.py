from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import normalized_standard_handoff_hash, sha256_file, standard_package_hash
from .models import SCHEMA_ID, SCHEMA_VERSION, StandardHandoff


def materialize_standard_package(
    handoff_payload: dict[str, Any],
    destination: Path,
    *,
    attachment_files: dict[str, bytes] | None = None,
) -> tuple[Path, StandardHandoff]:
    """Build a deterministic immutable package without receiver deployment data."""

    destination.mkdir(parents=True, exist_ok=False)
    payload = json.loads(json.dumps(handoff_payload))
    payload["envelope"]["package_content_hash"] = "sha256:" + "0" * 64
    handoff_path = destination / "handoff.json"
    handoff_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for relative, content in sorted((attachment_files or {}).items()):
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    files = {"handoff.json": normalized_standard_handoff_hash(handoff_path)}
    for path in sorted(candidate for candidate in destination.rglob("*") if candidate.is_file() and candidate != handoff_path):
        files[path.relative_to(destination).as_posix()] = sha256_file(path)
    package_hash = standard_package_hash(files)
    payload["envelope"]["package_content_hash"] = package_hash
    handoff_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "hash_algorithm": "canonical_file_hash_map_with_normalized_handoff_self_reference",
        "files": files,
        "package_content_hash": package_hash,
    }
    (destination / "package_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination, StandardHandoff.from_dict(payload)
