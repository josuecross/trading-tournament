from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "research_memos" / "gate1d" / "individual_stock_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "gate1d" / "individual_stock_momentum" / "latest"
GATE_ZIP = ROOT / "evidence" / "research_memos" / "gate1d" / "individual_stock_momentum" / "latest_gate1d_packet.zip"
ALLOWED_DECISIONS = {
    "choose_norgate_for_gate1e_acquisition_review",
    "choose_sharadar_for_gate1e_acquisition_review",
    "choose_crsp_if_access_available",
    "conditional_user_must_select_provider",
    "defer_until_provider_access_known",
    "reject_stock_momentum_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_gate1d_folder_evidence_and_zip_exist() -> None:
    assert GATE_DIR.exists()
    assert LATEST_DIR.exists()
    assert GATE_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(GATE_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "GATE1D_DECISION.md" in zf.namelist()
        assert "PROVIDER_FIELD_COVERAGE_REVIEW.md" in zf.namelist()


def test_required_gate1d_source_files_exist() -> None:
    expected = {
        "README.md",
        "GATE1D_PROVIDER_TERMS_SECURITY_REVIEW.md",
        "PROVIDER_FIELD_COVERAGE_REVIEW.md",
        "PROVIDER_TERMS_AND_CACHE_RIGHTS_REVIEW.md",
        "PROVIDER_SECURITY_AND_SECRET_HANDLING.md",
        "PROVIDER_RANKING_DECISION.md",
        "DATA_ACQUISITION_BOUNDARY.md",
        "NEXT_GATE_1E_REQUIREMENTS.md",
        "GATE1D_DECISION.md",
        "gate1d_manifest.json",
    }
    assert {path.name for path in GATE_DIR.iterdir() if path.is_file()} == expected


def test_required_gate1d_reviews_exist_and_name_provider_path() -> None:
    field_review = (GATE_DIR / "PROVIDER_FIELD_COVERAGE_REVIEW.md").read_text(encoding="utf-8")
    terms_review = (GATE_DIR / "PROVIDER_TERMS_AND_CACHE_RIGHTS_REVIEW.md").read_text(encoding="utf-8")
    security_review = (GATE_DIR / "PROVIDER_SECURITY_AND_SECRET_HANDLING.md").read_text(encoding="utf-8")
    ranking = (GATE_DIR / "PROVIDER_RANKING_DECISION.md").read_text(encoding="utf-8")
    boundary = (GATE_DIR / "DATA_ACQUISITION_BOUNDARY.md").read_text(encoding="utf-8")
    next_gate = (GATE_DIR / "NEXT_GATE_1E_REQUIREMENTS.md").read_text(encoding="utf-8")
    for provider in ["Norgate Data", "Nasdaq Data Link / Sharadar", "CRSP", "Polygon/Massive", "Tiingo", "EODHD"]:
        assert provider in field_review
    assert "raw data excluded" in terms_review
    assert "No API key was created" in security_review
    assert "Preferred: `Norgate Data`" in ranking
    assert "Gate 1D does not approve data acquisition" in boundary
    assert "tiny sample dataset only" in next_gate


def test_decision_and_manifest_are_research_only() -> None:
    decision = (GATE_DIR / "GATE1D_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "gate1d_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["preferred_provider"] == "Norgate Data"
    assert manifest["secondary_provider"] == "Nasdaq Data Link / Sharadar"
    assert manifest["gate1e_acquisition_review_approved"] is True
    assert manifest["data_acquisition_approved"] is False
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
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1d_provider_terms_security_review",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1c_provider_cost_access_review",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
        ROOT / ".env",
        ROOT / "secrets.env",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_gate1d_and_active_controls() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    gate = rows["individual_stock_momentum_gate1b_v1"]
    assert gate["status"] in {
        "choose_norgate_for_gate1e_acquisition_review",
        "blocked_no_local_norgate_access",
        "conditional_pending_package_and_terms_selection",
    }
    assert gate["implementation_status"] == "not_implemented"
    assert gate["paper_forward_active"] is False
    assert gate["real_money_recommendation"] is False
    assert gate["allowed_next_action"] in {
        "gate1e_controlled_acquisition_review",
        "configure_norgate_local_path",
        "user_select_sharadar_package",
    }
    assert "download_stock_data_without_gate1e" in gate["forbidden_next_actions"]
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
