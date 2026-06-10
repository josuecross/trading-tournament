from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = ROOT / "research_memos" / "queue_reprioritization"
LATEST_DIR = ROOT / "evidence" / "research_memos" / "queue_reprioritization" / "latest"
QUEUE_ZIP = ROOT / "evidence" / "research_memos" / "queue_reprioritization" / "latest_queue_reprioritization_packet.zip"
ALLOWED_DECISIONS = {
    "choose_commodity_basket_etf_momentum_review",
    "choose_treasury_duration_trend_rotation_review",
    "choose_crypto_spot_tsmom_tier2_review",
    "choose_volatility_risk_proxy_review",
    "choose_macro_regime_filter_review",
    "choose_factor_or_sector_extension_review",
    "pause_new_families_focus_on_reporting",
    "defer_until_user_selects_provider",
}
EXPECTED_FILES = {
    "README.md",
    "STOCK_MOMENTUM_BLOCKER_SUMMARY.md",
    "NEXT_FAMILY_CANDIDATE_REVIEW.md",
    "DATA_AVAILABILITY_AND_GATE_REVIEW.md",
    "RESEARCH_PRIORITY_DECISION.md",
    "NEXT_ACTION_PLAN.md",
    "queue_reprioritization_manifest.json",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_queue_reprioritization_folder_evidence_and_zip_exist() -> None:
    assert QUEUE_DIR.exists()
    assert LATEST_DIR.exists()
    assert QUEUE_ZIP.exists()
    assert {path.name for path in QUEUE_DIR.iterdir() if path.is_file()} == EXPECTED_FILES
    assert {path.name for path in LATEST_DIR.iterdir() if path.is_file()} == EXPECTED_FILES
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(QUEUE_ZIP) as zf:
        assert set(zf.namelist()) == EXPECTED_FILES
        assert len(zf.namelist()) <= 10


def test_stock_momentum_blocker_summary_preserves_non_approval() -> None:
    text = (QUEUE_DIR / "STOCK_MOMENTUM_BLOCKER_SUMMARY.md").read_text(encoding="utf-8")
    for token in [
        "Gate 1B result",
        "Gate 1C result",
        "Gate 1D result",
        "Gate 1E result",
        "Gate 1F result",
        "individual stock momentum deferred",
        "No stock implementation is approved.",
        "No stock data loader is approved.",
        "No stock data download is approved.",
        "No stock backtest is approved.",
        "No current-ticker-only serious evidence is allowed.",
    ]:
        assert token in text


def test_next_family_review_and_data_gate_review_cover_required_families() -> None:
    family_review = (QUEUE_DIR / "NEXT_FAMILY_CANDIDATE_REVIEW.md").read_text(encoding="utf-8")
    data_review = (QUEUE_DIR / "DATA_AVAILABILITY_AND_GATE_REVIEW.md").read_text(encoding="utf-8")
    for family_id in [
        "commodity_basket_etf_momentum_v1",
        "treasury_duration_trend_rotation_v1",
        "crypto_spot_tsmom_tier2_review_v1",
        "volatility_risk_proxy_review_v1",
        "macro_regime_filter_review_v1",
        "factor_or_sector_extension_review_v1",
    ]:
        assert family_id in family_review
        assert family_id in data_review
    assert "Do not approve implementation" in family_review
    assert "No family should run immediately from this review" in data_review


def test_research_priority_decision_and_manifest_are_allowed_and_research_only() -> None:
    decision = (QUEUE_DIR / "RESEARCH_PRIORITY_DECISION.md").read_text(encoding="utf-8")
    assert "Decision: `choose_commodity_basket_etf_momentum_review`" in decision
    assert "better than continuing stock-provider review loops" in decision
    manifest = json.loads((LATEST_DIR / "queue_reprioritization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "choose_commodity_basket_etf_momentum_review"
    assert manifest["next_family"] == "commodity_basket_etf_momentum_v1"
    assert manifest["next_allowed_action"] == "create_commodity_basket_etf_momentum_review"
    assert manifest["individual_stock_momentum_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["strategy_implemented"] is False
    assert manifest["stock_data_loader_created"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_next_action_plan_is_review_only() -> None:
    text = (QUEUE_DIR / "NEXT_ACTION_PLAN.md").read_text(encoding="utf-8")
    assert "`commodity_basket_etf_momentum_v1`" in text
    for symbol in ["DBC", "PDBC", "COMT", "GSG", "USCI"]:
        assert symbol in text
    assert "These are not approved symbols yet." in text
    assert "no data download" in text
    assert "no implementation" in text
    assert "no backtest" in text
    assert "no Profit Exploration" in text


def test_no_strategy_loader_download_or_provider_artifact_created() -> None:
    forbidden_paths = [
        ROOT / "src" / "commodity_basket_etf_momentum.py",
        ROOT / "src" / "stock_data_loader.py",
        ROOT / "src" / "individual_stock_momentum.py",
        ROOT / "src" / "stock_momentum.py",
        ROOT / "data_acquisition_runs" / "commodity_basket_etf_momentum_v1",
        ROOT / "data_acquisition_runs" / "individual_stock_momentum",
        ROOT / ".env",
        ROOT / "secrets.env",
    ]
    for path in forbidden_paths:
        assert not path.exists()


def test_strategy_lab_registry_reflects_next_family_without_activation() -> None:
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
    stock = rows["individual_stock_momentum_gate1b_v1"]
    assert stock["status"] == "conditional_pending_package_and_terms_selection"
    assert stock["implementation_status"] == "not_implemented"
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
