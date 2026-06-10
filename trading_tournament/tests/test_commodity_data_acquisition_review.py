from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "data_acquisition_reviews" / "commodity_basket_etf_momentum_v1"
LATEST_DIR = ROOT / "evidence" / "data_acquisition_reviews" / "commodity_basket_etf_momentum_v1" / "latest"
REVIEW_ZIP = ROOT / "evidence" / "data_acquisition_reviews" / "commodity_basket_etf_momentum_v1" / "latest_data_acquisition_review_packet.zip"
SYMBOLS = {"DBC", "PDBC", "COMT", "GSG", "USCI"}
ALLOWED_DECISIONS = {
    "approve_future_yfinance_download_prompt_pdbc_comt_only",
    "approve_future_yfinance_download_prompt_all_reviewed_symbols",
    "conditional_pending_product_identity_terms_review",
    "defer_high_wrapper_risk",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_data_acquisition_review_folder_evidence_and_zip_exist() -> None:
    assert REVIEW_DIR.exists()
    assert LATEST_DIR.exists()
    assert REVIEW_ZIP.exists()
    expected = {
        "README.md",
        "REQUIRED_SYMBOLS_REVIEW.md",
        "PROVIDER_CANDIDATE_REVIEW.md",
        "PRODUCT_IDENTITY_AND_TERMS_REVIEW.md",
        "DATA_QUALITY_REQUIREMENTS.md",
        "WRAPPER_RISK_LABEL_REQUIREMENTS.md",
        "DATA_DOWNLOAD_PLAN.md",
        "DATA_ACQUISITION_DECISION.md",
        "commodity_data_acquisition_manifest.json",
    }
    assert {path.name for path in REVIEW_DIR.iterdir() if path.is_file()} == expected
    assert {path.name for path in LATEST_DIR.iterdir() if path.is_file()} == expected
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(REVIEW_ZIP) as zf:
        assert set(zf.namelist()) == expected
        assert len(zf.namelist()) <= 10


def test_required_symbols_review_includes_all_symbols_without_approval() -> None:
    text = (REVIEW_DIR / "REQUIRED_SYMBOLS_REVIEW.md").read_text(encoding="utf-8")
    for symbol in SYMBOLS:
        assert symbol in text
        assert f"| {symbol} " in text
    assert "No symbol is approved for download" in text
    assert "PDBC and COMT may be preferred first-review candidates" in text
    assert "DBC, GSG, and USCI should remain higher product-risk candidates" in text


def test_provider_identity_quality_wrapper_and_plan_docs_exist() -> None:
    provider = (REVIEW_DIR / "PROVIDER_CANDIDATE_REVIEW.md").read_text(encoding="utf-8")
    identity = (REVIEW_DIR / "PRODUCT_IDENTITY_AND_TERMS_REVIEW.md").read_text(encoding="utf-8")
    quality = (REVIEW_DIR / "DATA_QUALITY_REQUIREMENTS.md").read_text(encoding="utf-8")
    labels = (REVIEW_DIR / "WRAPPER_RISK_LABEL_REQUIREMENTS.md").read_text(encoding="utf-8")
    plan = (REVIEW_DIR / "DATA_DOWNLOAD_PLAN.md").read_text(encoding="utf-8")
    for provider_id in [
        "existing_local_cache",
        "yfinance_compatible_path",
        "Tiingo",
        "Alpha Vantage",
        "Nasdaq Data Link",
        "Polygon/Massive",
        "issuer_fund_pages_metadata_only",
        "public_csv_sources",
    ]:
        assert provider_id in provider
    assert "No provider API was called" in provider
    assert "official product name" in identity
    assert "whether raw OHLCV can remain in local cache only" in identity
    assert "no raw OHLCV in advisor packets" in quality
    assert "commodity_wrapper_evidence_research_sample_only" in labels
    assert "Adjusted wrapper price modeling is not direct futures strategy evidence" in labels
    assert "Recommendation: `Option C - staged acquisition`" in plan


def test_decision_and_manifest_are_research_only_and_no_download() -> None:
    decision = (REVIEW_DIR / "DATA_ACQUISITION_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{value}`" in decision for value in ALLOWED_DECISIONS)
    assert "Future Download Symbols Approved" in decision
    assert "None in this task" in decision
    manifest = json.loads((LATEST_DIR / "commodity_data_acquisition_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "conditional_pending_product_identity_terms_review"
    assert set(manifest["reviewed_symbols"]) == SYMBOLS
    assert manifest["future_download_prompt_approved"] is False
    assert manifest["future_download_symbols_approved"] == []
    assert manifest["stage1_preferred_symbols_after_terms_review"] == ["PDBC", "COMT"]
    assert set(manifest["symbols_deferred"]) == SYMBOLS
    assert manifest["strategy_implemented"] is False
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


def test_no_commodity_strategy_loader_download_provider_or_secret_artifact_created() -> None:
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


def test_strategy_lab_registry_reflects_conditional_terms_gate() -> None:
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
