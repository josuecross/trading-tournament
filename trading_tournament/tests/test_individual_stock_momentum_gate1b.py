from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "research_memos" / "gate1b" / "individual_stock_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "gate1b" / "individual_stock_momentum" / "latest"
GATE_ZIP = ROOT / "evidence" / "research_memos" / "gate1b" / "individual_stock_momentum" / "latest_gate1b_packet.zip"
ALLOWED_DECISIONS = {
    "approve_data_acquisition_review",
    "approve_tier1_toy_exploratory_prompt_only",
    "conditional_pending_provider_cost_review",
    "defer_until_survivorship_free_provider",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_gate1b_folder_evidence_and_zip_exist() -> None:
    assert GATE_DIR.exists()
    assert LATEST_DIR.exists()
    assert GATE_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(GATE_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "GATE1B_DECISION.md" in zf.namelist()
        assert "DATA_SOURCE_OPTIONS.md" in zf.namelist()


def test_required_gate1b_source_files_exist() -> None:
    expected = {
        "README.md",
        "GATE1B_REVIEW.md",
        "DATA_SOURCE_OPTIONS.md",
        "SURVIVORSHIP_AND_DELISTING_REVIEW.md",
        "POINT_IN_TIME_UNIVERSE_REVIEW.md",
        "CORPORATE_ACTIONS_AND_ADJUSTMENTS_REVIEW.md",
        "LIQUIDITY_AND_EXECUTION_COST_REVIEW.md",
        "RUNTIME_AND_STORAGE_REVIEW.md",
        "EXPLORATORY_TIER_POLICY.md",
        "GATE1B_DECISION.md",
        "gate1b_manifest.json",
    }
    assert {path.name for path in GATE_DIR.iterdir() if path.is_file()} == expected


def test_provider_options_include_required_sources() -> None:
    text = (GATE_DIR / "DATA_SOURCE_OPTIONS.md").read_text(encoding="utf-8")
    required = [
        "CRSP",
        "Norgate",
        "Nasdaq Data Link",
        "Sharadar",
        "Polygon/Massive",
        "Tiingo",
        "EODHD",
        "Alpaca",
        "Interactive Brokers",
        "IBKR",
        "yfinance",
    ]
    for token in required:
        assert token in text


def test_survivorship_point_in_time_and_tier_policy_exist() -> None:
    survivorship = (GATE_DIR / "SURVIVORSHIP_AND_DELISTING_REVIEW.md").read_text(encoding="utf-8")
    point_in_time = (GATE_DIR / "POINT_IN_TIME_UNIVERSE_REVIEW.md").read_text(encoding="utf-8")
    tier_policy = (GATE_DIR / "EXPLORATORY_TIER_POLICY.md").read_text(encoding="utf-8")
    assert "current-ticker-only" in survivorship
    assert "delisting returns" in survivorship
    assert "serious_survivorship_free" in survivorship
    assert "today's S&P 500" in point_in_time
    assert "current-ticker-only toy universe" in point_in_time
    assert "Tier 1" in tier_policy
    assert "Tier 4" in tier_policy


def test_decision_and_manifest_are_allowed_and_research_only() -> None:
    decision = (GATE_DIR / "GATE1B_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "gate1b_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["stock_strategy_implemented"] is False
    assert manifest["stock_data_loader_created"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["backtest_run"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_no_stock_strategy_or_loader_created() -> None:
    forbidden_paths = [
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1b_v1",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
    ]
    for path in forbidden_paths:
        assert not path.exists()
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "run_research_state_dashboard.py",
            ROOT / "run_advisor_audit_packet.py",
        ]
    )
    assert "run_backtest.py" not in source
    assert "run_profit_exploration.py" not in source
    assert "run_paper_forward_observation.py" not in source


def test_strategy_lab_registry_gate1b_and_active_controls() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    gate = rows["individual_stock_momentum_gate1b_v1"]
    assert gate["status"] in {
        "conditional_pending_provider_cost_review",
        "conditional_choose_provider_before_data_acquisition",
        "conditional_pending_package_and_terms_selection",
    }
    assert gate["implementation_status"] == "not_implemented"
    assert gate["paper_forward_active"] is False
    assert gate["real_money_recommendation"] is False
    assert gate["allowed_next_action"] in {
        "provider_cost_review",
        "choose_provider_for_terms_review",
        "user_select_sharadar_package",
    }
    assert "use_current_ticker_only_as_serious_evidence" in gate["forbidden_next_actions"]
    combo = rows["profit_combo_SPY200d_GLD_50_50_v1"]
    assert combo["status"] == "active_paper_demo_observation"
    assert combo["paper_forward_active"] is True
    spy = rows["SPY_200d_trend_model"]
    assert spy["rules_frozen"] is True
    assert "replaced" not in str(spy).lower()


def test_advisor_upload_top_level_remains_capped_if_present() -> None:
    latest = ROOT / "evidence" / "advisor_upload" / "latest"
    if latest.exists():
        assert len([path for path in latest.iterdir() if path.is_file()]) <= 10
