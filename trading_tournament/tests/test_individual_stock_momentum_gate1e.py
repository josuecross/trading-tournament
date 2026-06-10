from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "research_memos" / "gate1e" / "individual_stock_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "gate1e" / "individual_stock_momentum" / "latest"
GATE_ZIP = ROOT / "evidence" / "research_memos" / "gate1e" / "individual_stock_momentum" / "latest_gate1e_packet.zip"
ALLOWED_DECISIONS = {
    "approve_future_norgate_tiny_sample_acquisition_prompt",
    "blocked_pending_user_terms_acceptance",
    "blocked_no_local_norgate_access",
    "blocked_field_mapping_unclear",
    "defer_to_sharadar_provider_review",
    "defer_until_provider_available",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_gate1e_folder_evidence_and_zip_exist() -> None:
    assert GATE_DIR.exists()
    assert LATEST_DIR.exists()
    assert GATE_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(GATE_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "GATE1E_DECISION.md" in zf.namelist()
        assert "LOCAL_ACCESS_CHECK.md" in zf.namelist()


def test_required_gate1e_source_files_exist() -> None:
    expected = {
        "README.md",
        "GATE1E_NORGATE_PREFLIGHT_REVIEW.md",
        "LOCAL_ACCESS_CHECK.md",
        "USER_TERMS_ACCEPTANCE_CHECK.md",
        "MINIMUM_DATA_CONTRACT_FIELD_MAPPING.md",
        "TINY_SAMPLE_ACQUISITION_PLAN.md",
        "RAW_DATA_EXCLUSION_POLICY.md",
        "BLOCKERS_AND_FALLBACKS.md",
        "GATE1E_DECISION.md",
        "gate1e_manifest.json",
    }
    assert {path.name for path in GATE_DIR.iterdir() if path.is_file()} == expected


def test_required_gate1e_reviews_exist_and_are_blocked_safely() -> None:
    local_access = (GATE_DIR / "LOCAL_ACCESS_CHECK.md").read_text(encoding="utf-8")
    terms = (GATE_DIR / "USER_TERMS_ACCEPTANCE_CHECK.md").read_text(encoding="utf-8")
    field_map = (GATE_DIR / "MINIMUM_DATA_CONTRACT_FIELD_MAPPING.md").read_text(encoding="utf-8")
    tiny_plan = (GATE_DIR / "TINY_SAMPLE_ACQUISITION_PLAN.md").read_text(encoding="utf-8")
    raw_policy = (GATE_DIR / "RAW_DATA_EXCLUSION_POLICY.md").read_text(encoding="utf-8")
    blockers = (GATE_DIR / "BLOCKERS_AND_FALLBACKS.md").read_text(encoding="utf-8")
    assert "local_access_status: `not_found`" in local_access
    assert "Terms acceptance status: `not_confirmed`" in terms
    assert "delisting return or delisting price treatment" in field_map
    assert "maximum symbols: 5 to 20" in tiny_plan
    assert "no Norgate database files in zip packets" in raw_policy
    assert "no local Norgate access found" in blockers


def test_decision_and_manifest_are_research_only() -> None:
    decision = (GATE_DIR / "GATE1E_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "gate1e_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "blocked_no_local_norgate_access"
    assert manifest["local_access_status"] == "not_found"
    assert manifest["terms_acceptance_status"] == "not_confirmed"
    assert manifest["future_tiny_sample_acquisition_prompt_approved"] is False
    assert manifest["stock_strategy_implemented"] is False
    assert manifest["production_stock_data_loader_created"] is False
    assert manifest["full_stock_universe_downloaded"] is False
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
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1e_norgate_acquisition_preflight",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
        ROOT / ".env",
        ROOT / "secrets.env",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_gate1e_and_active_controls() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    gate = rows["individual_stock_momentum_gate1b_v1"]
    assert gate["status"] in {
        "blocked_no_local_norgate_access",
        "conditional_pending_package_and_terms_selection",
    }
    assert gate["implementation_status"] == "not_implemented"
    assert gate["paper_forward_active"] is False
    assert gate["real_money_recommendation"] is False
    assert gate["allowed_next_action"] in {"configure_norgate_local_path", "user_select_sharadar_package"}
    assert "download_full_stock_universe" in gate["forbidden_next_actions"]
    assert "run_stock_backtest_before_tiny_sample_quality" in gate["forbidden_next_actions"]
    assert "call_provider_without_terms_acceptance" in gate["forbidden_next_actions"]
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
