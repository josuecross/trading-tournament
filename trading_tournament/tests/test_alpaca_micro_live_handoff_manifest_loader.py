from __future__ import annotations

import json

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import (
    load_handoff_package,
    validate_manifest_hashes,
    write_immutable_cache,
)
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def test_manifest_loader_reads_valid_fake_standard_v1_package(tmp_path) -> None:
    package_root = write_fake_handoff_package(tmp_path)
    package = load_handoff_package(package_root)
    assert package.package_id == "fake_standard_handoff_v1"
    assert package.strategy_id == "fake_strategy_v1"
    assert package.calculator_type == "fake_static_calculator_v1"
    assert package.target_output == "target_weights"
    assert package.source_hashes["manifest"].startswith("sha256:")
    assert validate_manifest_hashes(package) == []


def test_missing_required_manifest_field_is_classified(tmp_path) -> None:
    package_root = write_fake_handoff_package(tmp_path, omit_manifest_package_id=True)
    package = load_handoff_package(package_root)
    assert "manifest_missing_required_field" in package.classifications


def test_immutable_package_copy_preserves_source_hash(tmp_path) -> None:
    package = load_handoff_package(write_fake_handoff_package(tmp_path / "source"))
    cache_path = write_immutable_cache(package, tmp_path / "cache")
    report = json.loads((cache_path / "hash_report.json").read_text(encoding="utf-8"))
    assert report["source_hashes"]["manifest"] == package.source_hashes["manifest"]
    assert (cache_path / "source_manifest_copy.json").exists()
