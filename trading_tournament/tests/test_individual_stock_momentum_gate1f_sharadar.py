from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "research_memos" / "gate1f" / "individual_stock_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "gate1f" / "individual_stock_momentum" / "latest"
GATE_ZIP = ROOT / "evidence" / "research_memos" / "gate1f" / "individual_stock_momentum" / "latest_gate1f_packet.zip"
ALLOWED_DECISIONS = {
    "choose_sharadar_for_gate1g_terms_and_tiny_sample_review",
    "conditional_pending_package_and_terms_selection",
    "defer_to_norgate_access_setup",
    "defer_until_provider_access_known",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_gate1f_folder_evidence_and_zip_exist() -> None:
    assert GATE_DIR.exists()
    assert LATEST_DIR.exists()
    assert GATE_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(GATE_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "GATE1F_DECISION.md" in zf.namelist()
        assert "SHARADAR_FIELD_COVERAGE_REVIEW.md" in zf.namelist()


def test_required_gate1f_source_files_exist() -> None:
    expected = {
        "README.md",
        "GATE1F_SHARADAR_FALLBACK_REVIEW.md",
        "SHARADAR_FIELD_COVERAGE_REVIEW.md",
        "SHARADAR_PACKAGE_AND_TABLE_REVIEW.md",
        "SHARADAR_TERMS_SECURITY_REVIEW.md",
        "MINIMUM_DATA_CONTRACT_MAPPING_SHARADAR.md",
        "SHARADAR_TINY_SAMPLE_PLAN.md",
        "BLOCKERS_AND_DECISION.md",
        "GATE1F_DECISION.md",
        "gate1f_manifest.json",
    }
    assert {path.name for path in GATE_DIR.iterdir() if path.is_file()} == expected


def test_sharadar_reviews_include_required_sections() -> None:
    field_review = (GATE_DIR / "SHARADAR_FIELD_COVERAGE_REVIEW.md").read_text(encoding="utf-8")
    package_review = (GATE_DIR / "SHARADAR_PACKAGE_AND_TABLE_REVIEW.md").read_text(encoding="utf-8")
    terms_review = (GATE_DIR / "SHARADAR_TERMS_SECURITY_REVIEW.md").read_text(encoding="utf-8")
    mapping = (GATE_DIR / "MINIMUM_DATA_CONTRACT_MAPPING_SHARADAR.md").read_text(encoding="utf-8")
    tiny_plan = (GATE_DIR / "SHARADAR_TINY_SAMPLE_PLAN.md").read_text(encoding="utf-8")
    for token in ["delisted stocks", "adjusted OHLCV", "point-in-time", "local cache feasibility"]:
        assert token in field_review
    for token in ["SEP / Equity Prices", "TICKERS / metadata", "ACTIONS / corporate actions"]:
        assert token in package_review
    assert "No API keys in repo" in terms_review
    assert "delisting return or delisting price treatment" in mapping
    assert "maximum symbols: 5 to 20" in tiny_plan


def test_decision_and_manifest_are_research_only() -> None:
    decision = (GATE_DIR / "GATE1F_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "gate1f_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "conditional_pending_package_and_terms_selection"
    assert manifest["provider_focus"] == "Nasdaq Data Link / Sharadar"
    assert manifest["norgate_status"] == "blocked_no_local_norgate_access"
    assert manifest["gate1g_terms_tiny_sample_review_approved"] is False
    assert manifest["package_selected"] is False
    assert manifest["stock_strategy_implemented"] is False
    assert manifest["stock_data_loader_created"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_no_stock_strategy_loader_download_or_secret_artifact_created() -> None:
    forbidden_paths = [
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1f_sharadar_fallback_review",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
        ROOT / ".env",
        ROOT / "secrets.env",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_gate1f_and_active_controls() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    gate = rows["individual_stock_momentum_gate1b_v1"]
    assert gate["status"] == "conditional_pending_package_and_terms_selection"
    assert gate["implementation_status"] == "not_implemented"
    assert gate["paper_forward_active"] is False
    assert gate["real_money_recommendation"] is False
    assert gate["allowed_next_action"] == "user_select_sharadar_package"
    assert "download_stock_data_without_tiny_sample_gate" in gate["forbidden_next_actions"]
    assert "call_provider_api_without_terms_security" in gate["forbidden_next_actions"]
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
