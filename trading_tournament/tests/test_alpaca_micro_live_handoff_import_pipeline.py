from __future__ import annotations

import yaml
import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import run_import_pipeline
from execution_lab.alpaca_micro_live_v1.handoff_import.runtime_spec_generator import write_disabled_spec
from execution_lab.alpaca_micro_live_v1.handoff_import.compatibility import classify_package
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import load_handoff_package
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def test_runtime_spec_generator_writes_disabled_specs_only(tmp_path) -> None:
    package = load_handoff_package(write_fake_handoff_package(tmp_path))
    spec_path = write_disabled_spec(package, classify_package(package), output_root=tmp_path / "generated")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert spec["enabled"] is False
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False
    assert spec["live_trading_allowed"] is False


def test_import_command_dry_run_writes_reports_only(tmp_path) -> None:
    write_fake_handoff_package(tmp_path / "handoffs")
    results = run_import_pipeline(
        handoff_root=tmp_path / "handoffs",
        output_dir=tmp_path / "imports",
        evidence_root=tmp_path / "evidence",
        generated_spec_root=tmp_path / "generated",
        all_found=True,
        dry_run=True,
    )
    assert len(results) == 1
    assert results[0].generated_spec_path is None
    assert not (tmp_path / "generated").exists()


def test_write_disabled_specs_writes_disabled_generated_specs(tmp_path) -> None:
    write_fake_handoff_package(tmp_path / "handoffs")
    results = run_import_pipeline(
        handoff_root=tmp_path / "handoffs",
        output_dir=tmp_path / "imports",
        evidence_root=tmp_path / "evidence",
        generated_spec_root=tmp_path / "generated",
        all_found=True,
        write_disabled_specs=True,
        dry_run=False,
    )
    spec = yaml.safe_load(results[0].generated_spec_path.read_text(encoding="utf-8"))
    assert spec["enabled"] is False
    assert spec["runtime_ready"] is False
    assert (tmp_path / "generated" / "import_registry.yaml").exists()
    assert (tmp_path / "evidence" / "immutable_packages" / "fake_standard_handoff_v1").exists()


def test_no_tournament_runtime_dependency_in_handoff_import_sources() -> None:
    import execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline as pipeline

    source = pipeline.__file__
    assert "trading_tournament" not in open(source, encoding="utf-8").read()
