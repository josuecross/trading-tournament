from __future__ import annotations

import json

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.providers.frozen_reference_virtual_sleeve import load_frozen_reference

pytestmark = pytest.mark.alpaca_micro_live


def test_frozen_reference_provider_loads_valid_fake_immutable_reference_data(tmp_path) -> None:
    package = tmp_path / "pkg"
    package.mkdir(parents=True)
    (package / "hash_report.json").write_text(json.dumps({"source_hashes": {"manifest": "sha256:abc"}}), encoding="utf-8")
    (package / "frozen_reference_virtual_sleeve.json").write_text(
        json.dumps({"schema_id": "frozen_reference_virtual_sleeve_v1", "target_weights": {"SPY": 0.5, "BIL": 0.5}}),
        encoding="utf-8",
    )
    result = load_frozen_reference("pkg", tmp_path)
    assert result.status == "provider_data_available"
    assert result.target_weights == {"SPY": 0.5, "BIL": 0.5}
    assert result.lineage_hashes["manifest"] == "sha256:abc"


def test_missing_frozen_reference_source_remains_blocked(tmp_path) -> None:
    result = load_frozen_reference("pkg", tmp_path)
    assert result.status == "provider_data_missing"
    assert result.blocked_reason == "frozen_reference_source_missing"


def test_unsupported_frozen_reference_schema_remains_blocked(tmp_path) -> None:
    package = tmp_path / "pkg"
    package.mkdir(parents=True)
    (package / "frozen_reference_virtual_sleeve.json").write_text(json.dumps({"schema_id": "other", "target_weights": {"SPY": 1.0}}), encoding="utf-8")
    result = load_frozen_reference("pkg", tmp_path)
    assert result.status == "provider_data_manual_review_required"
    assert result.blocked_reason == "frozen_reference_schema_unsupported"


def test_frozen_reference_provider_does_not_import_tournament_modules() -> None:
    import execution_lab.alpaca_micro_live_v1.handoff_import.providers.frozen_reference_virtual_sleeve as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "from trading_tournament" not in source
    assert "import trading_tournament" not in source
    assert "target_export" not in source
