from __future__ import annotations

import json
from pathlib import Path

import yaml

import run_risk_framework_audit as audit


def load_framework() -> dict:
    path = Path("risk_framework/risk_framework.yaml")
    assert path.exists()
    return yaml.safe_load(path.read_text()) or {}


def test_risk_framework_yaml_exists_and_loads() -> None:
    data = load_framework()
    assert data["framework"]["name"] == "balanced_speculative_research_v1"
    assert data["framework"]["research_only"] is True
    assert data["framework"]["real_money_recommendation"] is False


def test_required_sections_exist() -> None:
    data = load_framework()
    for section in [
        "framework",
        "account",
        "targets",
        "risk_bands",
        "success_metrics",
        "exposure_policy",
        "instrument_risk_budgets",
        "promotion_rules",
    ]:
        assert section in data


def test_targets_are_defined_correctly() -> None:
    data = load_framework()
    assert data["account"]["target_300_equity"] == 3300
    assert data["account"]["target_400_equity"] == 3400
    assert data["targets"]["target_300"]["label"] == "primary_challenge_target"
    assert data["targets"]["target_400"]["label"] == "aggressive_challenge_target"


def test_risk_bands_are_defined() -> None:
    data = load_framework()
    assert data["risk_bands"]["warning"]["drawdown_dollars_gte"] == 300
    assert data["risk_bands"]["review"]["drawdown_dollars_gte"] == 450
    assert data["risk_bands"]["hard_stop"]["drawdown_dollars_gte"] == 600


def test_exposure_policy_marks_only_1x_as_eligible() -> None:
    data = load_framework()
    assert data["exposure_policy"]["1.00"]["status"] == "paper_forward_eligible_if_candidate_validated"
    for key in ["1.05", "1.10", "1.15", "1.20", "1.25", "1.50"]:
        assert data["exposure_policy"][key]["status"] != "paper_forward_eligible_if_candidate_validated"


def test_instrument_risk_budgets_exist() -> None:
    data = load_framework()
    for key in ["broad_etf", "cash_treasury_proxy", "crypto_spot", "simulated_leverage", "individual_stocks", "options", "futures", "forex", "intraday"]:
        assert key in data["instrument_risk_budgets"]
    assert data["instrument_risk_budgets"]["simulated_leverage"]["paper_forward_allowed"] is False


def test_promotion_rules_block_tier1_and_exposure_rows() -> None:
    data = load_framework()
    disallowed = set(data["promotion_rules"]["practical_candidate"]["disallowed_if"])
    assert "tier1_exploratory" in disallowed
    assert "exposure_multiplier_gt_1" in disallowed
    assert "final_validation_completed_false" in disallowed
    paper_disallowed = set(data["promotion_rules"]["paper_forward"]["disallowed_if"])
    assert "leverage_or_exposure_diagnostic" in paper_disallowed
    assert "crypto_tier1" in paper_disallowed


def test_risk_framework_audit_writes_compact_packet() -> None:
    data = audit.load_framework()
    validation = audit.validate_framework(data)
    run_dir, latest_dir = audit.export_evidence(data, validation)
    files = [p.name for p in latest_dir.iterdir() if p.is_file()]
    assert validation["passed"] is True
    assert len(files) <= 10
    assert sorted(files) == sorted(audit.REQUIRED_FILES)
    validation_file = json.loads((latest_dir / "risk_framework_validation.json").read_text())
    assert validation_file["passed"] is True
    assert run_dir.exists()


def test_no_real_money_recommendation_appears_in_validation() -> None:
    data = load_framework()
    validation = audit.validate_framework(data)
    assert validation["real_money_recommendation"] is False
