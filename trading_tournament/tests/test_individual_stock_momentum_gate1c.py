from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "research_memos" / "gate1c" / "individual_stock_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "gate1c" / "individual_stock_momentum" / "latest"
GATE_ZIP = ROOT / "evidence" / "research_memos" / "gate1c" / "individual_stock_momentum" / "latest_gate1c_packet.zip"
ALLOWED_DECISIONS = {
    "pursue_serious_provider_review",
    "approve_tier1_toy_current_ticker_prompt_only",
    "conditional_choose_provider_before_data_acquisition",
    "defer_until_paid_or_survivorship_free_provider_available",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_gate1c_folder_evidence_and_zip_exist() -> None:
    assert GATE_DIR.exists()
    assert LATEST_DIR.exists()
    assert GATE_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(GATE_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "GATE1C_DECISION.md" in zf.namelist()
        assert "PROVIDER_COMPARISON_MATRIX.csv" in zf.namelist()


def test_required_gate1c_source_files_exist() -> None:
    expected = {
        "README.md",
        "GATE1C_PROVIDER_COST_ACCESS_REVIEW.md",
        "PROVIDER_COMPARISON_MATRIX.csv",
        "PROVIDER_FEASIBILITY_NOTES.md",
        "COST_AND_ACCESS_REVIEW.md",
        "DATA_RIGHTS_AND_SECURITY_REVIEW.md",
        "SERIOUS_VS_TOY_PATH_DECISION.md",
        "MINIMUM_DATA_CONTRACT_SPEC.md",
        "NEXT_GATE_REQUIREMENTS.md",
        "GATE1C_DECISION.md",
        "gate1c_manifest.json",
    }
    assert {path.name for path in GATE_DIR.iterdir() if path.is_file()} == expected


def test_provider_matrix_includes_required_providers() -> None:
    with (GATE_DIR / "PROVIDER_COMPARISON_MATRIX.csv").open("r", encoding="utf-8", newline="") as handle:
        providers = {row["provider"] for row in csv.DictReader(handle)}
    required = {
        "CRSP",
        "Norgate Data",
        "Nasdaq Data Link / Sharadar",
        "Polygon/Massive",
        "Tiingo",
        "EODHD",
        "Alpaca",
        "Interactive Brokers",
        "yfinance/current ticker lists",
        "Stooq/public CSV",
    }
    assert required <= providers


def test_decision_files_and_manifest_are_research_only() -> None:
    decision = (GATE_DIR / "GATE1C_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    assert (GATE_DIR / "SERIOUS_VS_TOY_PATH_DECISION.md").exists()
    assert (GATE_DIR / "MINIMUM_DATA_CONTRACT_SPEC.md").exists()
    manifest = json.loads((LATEST_DIR / "gate1c_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["stock_strategy_implemented"] is False
    assert manifest["stock_data_loader_created"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["data_acquisition_approved"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_no_stock_strategy_loader_or_download_artifact_created() -> None:
    forbidden_paths = [
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1c_provider_cost_access_review",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum_gate1b_v1",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_gate1c_and_active_controls() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    gate = rows["individual_stock_momentum_gate1b_v1"]
    assert gate["status"] in {
        "conditional_choose_provider_before_data_acquisition",
        "choose_norgate_for_gate1e_acquisition_review",
        "conditional_pending_package_and_terms_selection",
    }
    assert gate["implementation_status"] == "not_implemented"
    assert gate["paper_forward_active"] is False
    assert gate["real_money_recommendation"] is False
    assert gate["allowed_next_action"] in {
        "choose_provider_for_terms_review",
        "gate1e_controlled_acquisition_review",
        "user_select_sharadar_package",
    }
    assert "download_stock_data_without_provider_terms_review" in gate["forbidden_next_actions"]
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
