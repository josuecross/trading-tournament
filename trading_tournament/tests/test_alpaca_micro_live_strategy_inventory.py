from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.execution import runtime_strategy_inventory as inventory

pytestmark = pytest.mark.alpaca_micro_live


def test_inventory_finds_successful_and_blocks_incomplete() -> None:
    result = inventory.build_inventory()
    rows = {row["strategy_id"]: row for row in result["candidates"]}
    assert rows["vm_quality_lowvol_proxy_v1"]["status_classification"] == "runtime_ready"
    assert rows["dsr_sector_equal_weight_defensive_filter_v1"]["status_classification"] in {"ready_to_freeze", "runtime_ready"}
    assert rows["gror_balanced_momentum_60_40_v1"]["status_classification"] == "onboarding_blocked"
    assert rows["gror_balanced_momentum_60_40_v1"]["missing_rule_fields"]


def test_inventory_does_not_treat_future_research_only_as_successful() -> None:
    rows = {row["strategy_id"]: row for row in inventory.build_inventory()["candidates"]}
    assert rows["vm_spy_realized_vol_target_v1"]["status_classification"] == "not_successful_enough"
    assert rows["vm_spy_realized_vol_target_v1"]["already_copied_into_alpaca_runtime"] is False


def test_inventory_marks_unsupported_asset_class() -> None:
    rows = {row["strategy_id"]: row for row in inventory.build_inventory()["candidates"]}
    assert rows["crypto_spot"]["status_classification"] == "unsupported_asset_class"
    assert rows["crypto_spot"]["alpaca_paper_compatible"] is False
