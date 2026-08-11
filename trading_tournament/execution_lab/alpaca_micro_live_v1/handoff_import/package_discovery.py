from __future__ import annotations

from pathlib import Path

MANIFEST_NAMES = (
    "package_manifest.json",
    "handoff_manifest.json",
    "handoff.json",
    "forward_observation_interface_contract.json",
)


def looks_like_package_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((path / name).exists() for name in MANIFEST_NAMES)


def discover_package_dirs(handoff_root: Path) -> list[Path]:
    if not handoff_root.exists():
        return []
    candidates: set[Path] = set()
    for child in handoff_root.iterdir():
        if not child.is_dir():
            continue
        for path in (child / "latest" / "package", child / "package", child):
            if looks_like_package_dir(path):
                candidates.add(path.resolve())
    for manifest_name in MANIFEST_NAMES:
        for manifest in handoff_root.rglob(manifest_name):
            if looks_like_package_dir(manifest.parent):
                candidates.add(manifest.parent.resolve())
    return sorted(candidates)
