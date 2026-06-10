from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "research_memos" / "commodity_basket_etf_momentum"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "commodity_basket_etf_momentum" / "latest"
REVIEW_ZIP = ROOT / "evidence" / "research_memos" / "commodity_basket_etf_momentum" / "latest_commodity_review_packet.zip"
SYMBOLS = {"DBC", "PDBC", "COMT", "GSG", "USCI"}
ALLOWED_DECISIONS = {
    "approve_data_acquisition_review",
    "approve_research_sample_implementation_prompt",
    "conditional_pending_product_data_review",
    "defer_product_risk",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_commodity_review_folder_evidence_and_zip_exist() -> None:
    assert REVIEW_DIR.exists()
    assert LATEST_DIR.exists()
    assert REVIEW_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(REVIEW_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "COMMODITY_PRODUCT_REVIEW.md" in zf.namelist()
        assert "COMMODITY_REVIEW_DECISION.md" in zf.namelist()
        assert "commodity_review_manifest.json" in zf.namelist()


def test_required_source_files_exist() -> None:
    expected = {
        "README.md",
        "COMMODITY_PRODUCT_REVIEW.md",
        "PRODUCT_STRUCTURE_AND_WRAPPER_RISK.md",
        "DATA_AVAILABILITY_REVIEW.md",
        "INCEPTION_AND_COMMON_OVERLAP_REVIEW.md",
        "ROLL_YIELD_AND_TRACKING_RISK_REVIEW.md",
        "COST_TAX_AND_PRODUCT_RISK_REVIEW.md",
        "DUPLICATE_AND_DIVERSIFICATION_RISK_REVIEW.md",
        "BENCHMARK_AND_FAILURE_CRITERIA.md",
        "COMMODITY_REVIEW_DECISION.md",
        "commodity_review_manifest.json",
    }
    assert {path.name for path in REVIEW_DIR.iterdir() if path.is_file()} == expected


def test_product_review_includes_required_symbols_and_cache_status() -> None:
    text = (REVIEW_DIR / "COMMODITY_PRODUCT_REVIEW.md").read_text(encoding="utf-8")
    for symbol in SYMBOLS:
        assert symbol in text
        assert f"| {symbol} " in text
    assert "None of DBC, PDBC, COMT, GSG, or USCI exists in `data/cache/`" in text
    # This product/data review predates the later approved fast exploratory
    # acquisition lane. Current cache files may now exist, but the review packet
    # itself still must report that it did not download data.
    manifest = json.loads((LATEST_DIR / "commodity_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_downloaded"] is False


def test_required_review_docs_exist_and_cover_risks() -> None:
    structure = (REVIEW_DIR / "PRODUCT_STRUCTURE_AND_WRAPPER_RISK.md").read_text(encoding="utf-8")
    data = (REVIEW_DIR / "DATA_AVAILABILITY_REVIEW.md").read_text(encoding="utf-8")
    inception = (REVIEW_DIR / "INCEPTION_AND_COMMON_OVERLAP_REVIEW.md").read_text(encoding="utf-8")
    roll = (REVIEW_DIR / "ROLL_YIELD_AND_TRACKING_RISK_REVIEW.md").read_text(encoding="utf-8")
    cost = (REVIEW_DIR / "COST_TAX_AND_PRODUCT_RISK_REVIEW.md").read_text(encoding="utf-8")
    duplicate = (REVIEW_DIR / "DUPLICATE_AND_DIVERSIFICATION_RISK_REVIEW.md").read_text(encoding="utf-8")
    benchmarks = (REVIEW_DIR / "BENCHMARK_AND_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    assert "must not claim direct futures strategy evidence" in structure
    assert "missing_data_acquisition_review_required" in data
    assert "SPY_200d_trend_model" in inception
    assert "Futures roll yield can dominate returns" in roll
    assert "K-1" in cost
    assert "Could commodity basket products add real diversification beyond GLD" in duplicate
    assert "combo_SPY200d_GLD_50_50_v1" in benchmarks
    assert "asset_class_tsmom_top2_v1" in benchmarks


def test_decision_and_manifest_are_research_only() -> None:
    decision = (REVIEW_DIR / "COMMODITY_REVIEW_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "commodity_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "approve_data_acquisition_review"
    assert set(manifest["products_reviewed"]) == SYMBOLS
    assert manifest["data_acquisition_review_approved"] is True
    assert manifest["implementation_approved"] is False
    assert manifest["commodity_strategy_implemented"] is False
    assert manifest["data_loader_created"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_no_commodity_strategy_loader_download_or_secret_artifact_created() -> None:
    forbidden_paths = [
        ROOT / "src" / "commodity_basket_etf_momentum.py",
        ROOT / "src" / "commodity_momentum.py",
        ROOT / "src" / "commodity_data_loader.py",
        ROOT / "data_acquisition_runs" / "commodity_basket_etf_momentum_v1",
        ROOT / ".env",
        ROOT / "secrets.env",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_reflects_review_without_activation() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    commodity = rows["commodity_basket_etf_momentum_v1"]
    assert commodity["status"] in {
        "conditional_pending_product_identity_terms_review",
        "fast_exploratory_screen_completed",
    }
    assert commodity["implementation_status"] == "not_implemented"
    assert commodity["paper_forward_active"] is False
    assert commodity["paper_forward_allowed_by_risk_framework"] is False
    assert commodity["real_money_recommendation"] is False
    assert commodity["allowed_next_action"] in {"product_identity_terms_review", "issuer_methodology_review"}
    assert "implement_without_data_quality" in commodity["forbidden_next_actions"]
    assert "run_backtest_before_data_gate" in commodity["forbidden_next_actions"]
    assert "download_data_without_approved_prompt" in commodity["forbidden_next_actions"]
    assert "use_futures_contract_logic_without_review" in commodity["forbidden_next_actions"]
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
