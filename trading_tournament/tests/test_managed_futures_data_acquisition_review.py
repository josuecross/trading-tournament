from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "managed_futures_proxy_etf_trend_v1"
ROOT = Path("data_acquisition_reviews") / REVIEW_ID
LATEST_DIR = Path("evidence/data_acquisition_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/data_acquisition_reviews") / REVIEW_ID / "latest_data_acquisition_review_packet.zip"
SYMBOLS = {"DBMF", "KMLM", "CTA", "FMF", "WTMF"}
PROVIDERS = {
    "existing_local_cache",
    "yfinance",
    "tiingo",
    "alpha_vantage",
    "nasdaq_data_link_sharadar",
    "polygon_or_massive",
    "issuer_fund_pages_metadata",
    "public_csv_sources",
}


def test_managed_futures_data_acquisition_review_packet_exists() -> None:
    assert ROOT.exists()
    assert LATEST_DIR.exists()
    latest_files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(latest_files) <= 10
    assert latest_files == {
        "README.md",
        "REQUIRED_SYMBOLS.md",
        "PROVIDER_CANDIDATE_REVIEW.md",
        "DATA_ACQUISITION_DECISION.md",
        "DATA_QUALITY_REQUIREMENTS.md",
        "DATA_DOWNLOAD_PLAN.md",
        "PROXY_METHODOLOGY_REVIEW_REQUIREMENTS.md",
        "data_acquisition_manifest.json",
    }
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == latest_files


def test_required_symbols_and_missing_cache_semantics() -> None:
    required = (LATEST_DIR / "REQUIRED_SYMBOLS.md").read_text(encoding="utf-8")
    manifest = json.loads((LATEST_DIR / "data_acquisition_manifest.json").read_text(encoding="utf-8"))
    for symbol in SYMBOLS:
        assert symbol in required
    assert "data_acquisition_required" in required
    assert "provider_review_required" in required
    assert "It does not mean the symbol is permanently unavailable" in required
    assert set(manifest["required_proxy_symbols_reviewed"]) == SYMBOLS
    assert manifest["symbols_currently_cached"] == []
    assert set(manifest["symbols_missing_from_cache"]) == SYMBOLS
    assert manifest["missing_cache_interpretation"] == "data_acquisition_required_or_provider_review_required_not_data_unavailable"


def test_provider_quality_methodology_and_download_plan_are_review_only() -> None:
    provider_review = (LATEST_DIR / "PROVIDER_CANDIDATE_REVIEW.md").read_text(encoding="utf-8")
    quality = (LATEST_DIR / "DATA_QUALITY_REQUIREMENTS.md").read_text(encoding="utf-8")
    methodology = (LATEST_DIR / "PROXY_METHODOLOGY_REVIEW_REQUIREMENTS.md").read_text(encoding="utf-8")
    plan = (LATEST_DIR / "DATA_DOWNLOAD_PLAN.md").read_text(encoding="utf-8")
    for provider in PROVIDERS:
        assert provider in provider_review or provider in plan
    assert "This review does not call APIs and does not download data" in provider_review
    assert "No download is performed by this packet" in plan
    assert "no backtest" in plan.lower()
    assert "no raw OHLCV in advisor packets" in quality
    assert "Fund inception date" in methodology
    assert "wrapper-level ETF/fund price modeling" in methodology


def test_data_acquisition_decision_and_safety_manifest() -> None:
    decision = (LATEST_DIR / "DATA_ACQUISITION_DECISION.md").read_text(encoding="utf-8")
    manifest = json.loads((LATEST_DIR / "data_acquisition_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in {
        "acquisition_review_passed_create_provider_terms_review",
        "conditional_pending_provider_lookup",
        "defer_ticker_ambiguity_or_proxy_risk",
        "reject_no_acceptable_provider",
    }
    assert manifest["decision"] == "acquisition_review_passed_create_provider_terms_review"
    assert "Decision: `acquisition_review_passed_create_provider_terms_review`" in decision
    assert manifest["future_provider_terms_security_review_approved"] is True
    assert manifest["actual_data_download_approved_now"] is False
    assert manifest["data_downloaded"] is True
    assert manifest["api_called"] is True
    assert manifest["yfinance_compatible_provider_call"] is True
    assert manifest["keyed_provider_used"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["futures_contract_logic_added"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False


def test_strategy_lab_managed_futures_status_is_provider_gate_not_implemented() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["status"] in {
        "data_acquisition_required",
        "provider_review_required",
        "provider_terms_review_passed",
        "data_quality_review_passed_methodology_review_required",
        "conditional_approval_short_history_label_required",
        "data_gated",
        "reject_for_now",
        "too_slow",
    }
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {
        "issuer_methodology_review",
        "create_research_sample_implementation_prompt",
        "research_sample_review",
    }
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert any("futures_contract_logic" in action for action in row["forbidden_next_actions"])
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]


def test_no_api_keys_raw_data_strategy_backtest_or_futures_logic() -> None:
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{12,}"),
        re.compile(r"api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]", re.IGNORECASE),
        re.compile(r"token\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]", re.IGNORECASE),
    ]
    for path in list(ROOT.rglob("*")) + list(LATEST_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        assert "raw ohlcv rows" not in lower
        assert "real-money ready" not in lower
        assert "recommended real trade" not in lower
        assert "futures contract logic added" not in lower
        assert not any(pattern.search(text) for pattern in secret_patterns)
    run_profit = Path("run_profit_exploration.py").read_text(encoding="utf-8")
    specs = Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert REVIEW_ID in run_profit
    assert REVIEW_ID in specs
    assert "run_backtest.py" not in run_profit


def test_advisor_upload_references_managed_futures_data_acquisition_review(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "09_DATA_ACQUISITION_REVIEW.zip" not in top_files
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        index = zf.read("DATA_ACQUISITION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert REVIEW_ID in index
    assert "acquisition_review_passed_create_provider_terms_review" in index
    assert "Managed-futures proxy data acquisition review packet:" in executive
