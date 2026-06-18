from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from run_strategy_lab import load_registry, validate_registry_data
from strategy_lab.recovered_strategy_rules import (
    FORBIDDEN_MECHANICS,
    dsr_sector_equal_weight_defensive_filter_allocation,
    gror_balanced_momentum_60_40_allocation,
    vm_quality_lowvol_proxy_allocation,
)


VM_OBS = Path("paper_forward_observations/paper_forward_vm_quality_lowvol_proxy_v1/active_observation.yaml")
DSR_OBS = Path("paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1/active_observation.yaml")
VM_ACTIVATION = Path("evidence/paper_forward_activations/vm_quality_lowvol_proxy_v1/latest")
DSR_ACTIVATION = Path("evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1/latest")


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_recovered_active_observations_exist_and_are_frozen() -> None:
    for path in [VM_OBS, DSR_OBS]:
        assert path.exists()
        payload = read_yaml(path)
        assert payload["paper_forward_active"] is True
        assert payload["frozen"] is True
        assert payload["rules_frozen"] is True
        assert payload["evidence_source"] == "conversation_recovered"
        assert payload["real_money_recommendation"] is False
        assert payload["broker_integration"] is False
        assert payload["live_orders"] is False
        assert payload["order_placement"] is False


def test_recovered_activation_packets_have_manifest_and_consistency_check() -> None:
    for directory in [VM_ACTIVATION, DSR_ACTIVATION]:
        assert (directory / "manifest.json").exists()
        assert (directory / "consistency_check.json").exists()
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        consistency = json.loads((directory / "consistency_check.json").read_text(encoding="utf-8"))
        assert manifest["evidence_source"] == "conversation_recovered"
        assert manifest["candidate_exhaustive_run_during_recovery"] is False
        assert manifest["paper_forward_checkpoint_run_during_recovery"] is False
        assert manifest["real_money_recommendation"] is False
        assert consistency["consistency_passed"] is True
        assert consistency["checkpoint_conclusion_generated"] is False
        assert any(path.suffix == ".zip" for path in directory.iterdir())


def test_vm_quality_allocation_rule() -> None:
    allocation = vm_quality_lowvol_proxy_allocation(
        closes={"SPLV": 105, "USMV": 99, "QUAL": 120, "SPY": 101, "BIL": 1},
        sma_200={"SPLV": 100, "USMV": 100, "QUAL": 100, "SPY": 100},
        returns_126d={"SPLV": 0.08, "QUAL": 0.10, "SPY": 0.05},
        realized_vol_60d={"SPLV": 0.10, "QUAL": 0.20, "SPY": 0.08},
    )
    assert allocation == {"SPLV": 0.5, "SPY": 0.5}
    assert vm_quality_lowvol_proxy_allocation({"SPY": 90}, {"SPY": 100}, {"SPY": 0.1}, {"SPY": 0.2}) == {"BIL": 1.0}


def test_dsr_equal_weight_defensive_filter_allocation_rule() -> None:
    allocation = dsr_sector_equal_weight_defensive_filter_allocation(
        closes={"XLK": 110, "XLF": 105, "XLE": 90},
        sma_200={"XLK": 100, "XLF": 100, "XLE": 100},
    )
    assert allocation == {"XLK": pytest.approx(1 / 3), "XLF": pytest.approx(1 / 3), "BIL": pytest.approx(1 / 3)}
    full = dsr_sector_equal_weight_defensive_filter_allocation(
        closes={"XLK": 110, "XLF": 105, "XLV": 103},
        sma_200={"XLK": 100, "XLF": 100, "XLV": 100},
    )
    assert full == {"XLK": 1 / 3, "XLF": 1 / 3, "XLV": 1 / 3}


def test_gror_balanced_allocation_rule_and_no_candidate_run() -> None:
    allocation = gror_balanced_momentum_60_40_allocation(
        closes={"SPY": 105, "QQQ": 110, "IWM": 90, "IEF": 100, "TLT": 100, "BIL": 100},
        sma_200={"SPY": 100, "QQQ": 100, "IWM": 100},
        returns_63d={"SPY": 0.05, "QQQ": 0.10, "IEF": 0.01, "TLT": 0.03, "BIL": 0.02},
    )
    assert allocation == {"QQQ": 0.3, "SPY": 0.3, "TLT": 0.4}
    manifest = json.loads(
        Path("evidence/promotion_reviews/gror_balanced_momentum_60_40_v1/latest/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["candidate_exhaustive_run"] is False


def test_recovered_registry_status_matrix() -> None:
    data = load_registry()
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    rows = {row["id"]: row for row in data["strategies"]}
    for row_id in ["paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"]:
        row = rows[row_id]
        assert row["paper_forward_active"] is True
        assert row["rules_frozen"] is True
        assert row["real_money_recommendation"] is False
    assert rows["dsr_sector_top3_momentum_defensive_cash_v1"]["status"] == "deferred_candidate_queue"
    assert rows["dsr_sector_top3_momentum_defensive_cash_v1"]["candidate_exhaustive_run"] is False
    assert rows["gror_balanced_momentum_60_40_v1"]["status"] == "candidate_exhaustive_queue"
    assert rows["gror_balanced_momentum_60_40_v1"]["candidate_exhaustive_run"] is False
    assert rows["quality_momentum_etf_proxy"]["status"] == "watchlist_family"
    assert rows["quality_momentum_etf_proxy"]["paper_forward_active"] is False


def test_no_forbidden_mechanics_in_recovered_rules() -> None:
    assert all(value is False for value in FORBIDDEN_MECHANICS.values())
    for path in [VM_OBS, DSR_OBS]:
        payload = read_yaml(path)
        for key in FORBIDDEN_MECHANICS:
            assert payload[key] is False


def test_recovery_note_and_profit_family_audit_exist() -> None:
    note = Path("RECOVERY_FROM_LOST_UPDATES.md").read_text(encoding="utf-8")
    assert "conversation-recovered" in note
    assert "Recomputed evidence:" in note
    latest = Path("evidence/profit_family_discovery_audit/profit_family_discovery_audit/latest")
    assert (latest / "manifest.json").exists()
    assert (latest / "consistency_check.json").exists()
    rows = (latest / "recovered_rows.csv").read_text(encoding="utf-8")
    assert "global_risk_on_risk_off_etf" in rows
