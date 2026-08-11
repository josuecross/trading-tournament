from __future__ import annotations

import json

import pytest

from execution_lab.alpaca_micro_live_v1.execution.handoff_package_inventory import run_inventory
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def test_inventory_command_writes_csv_json_and_summary(tmp_path) -> None:
    write_fake_handoff_package(tmp_path / "handoffs")
    result = run_inventory(tmp_path / "handoffs", tmp_path / "audit", tmp_path / "out")
    assert result["packages_found"] == 1
    assert (tmp_path / "out" / "handoff_package_inventory.csv").exists()
    payload = json.loads((tmp_path / "out" / "handoff_package_inventory.json").read_text(encoding="utf-8"))
    assert payload[0]["package_id"] == "fake_standard_handoff_v1"
    assert "network_calls: false" in (tmp_path / "out" / "handoff_inventory_summary.md").read_text(encoding="utf-8")
