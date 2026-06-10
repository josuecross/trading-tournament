from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import yaml

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path("data_acquisition_reviews")
REVIEW_ID = "value_momentum_factor_etf_rotation_v1"
REVIEW_DIR = ROOT / REVIEW_ID
LATEST_DIR = Path("evidence/data_acquisition_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/data_acquisition_reviews") / REVIEW_ID / "latest_data_acquisition_review_packet.zip"
SYMBOLS = {"MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV", "SPY", "BIL"}
PROVIDERS = {
    "existing_local_cache",
    "yfinance",
    "alpha_vantage",
    "tiingo",
    "nasdaq_data_link_sharadar",
    "polygon_or_massive",
    "stooq_or_other_public_csv",
}


def test_data_acquisition_review_structure_exists() -> None:
    assert ROOT.exists()
    assert (ROOT / "README.md").exists()
    assert (ROOT / "approved_provider_registry.yaml").exists()
    assert (ROOT / "provider_evaluation_policy.md").exists()
    assert REVIEW_DIR.exists()
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
        "data_acquisition_manifest.json",
    }
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == latest_files


def test_approved_provider_registry_has_required_candidates_and_flags() -> None:
    data = yaml.safe_load((ROOT / "approved_provider_registry.yaml").read_text(encoding="utf-8"))
    rows = data["providers"]
    assert {row["provider_id"] for row in rows} == PROVIDERS
    required_fields = {
        "provider_id",
        "provider_name",
        "provider_type",
        "supports_etf_daily_history",
        "supports_adjusted_close",
        "supports_dividends_splits",
        "supports_bulk_download",
        "requires_api_key",
        "cost_unknown_or_paid",
        "rate_limit_risk",
        "terms_review_required",
        "allowed_for_research_cache",
        "allowed_for_compact_evidence",
        "raw_data_allowed_in_advisor_packet",
        "current_status",
        "notes",
    }
    for row in rows:
        assert required_fields.issubset(row.keys())
        assert row["raw_data_allowed_in_advisor_packet"] is False
    assert all(row["current_status"] != "approved_for_download_now" for row in rows)


def test_required_symbols_and_missing_cache_semantics() -> None:
    required = (LATEST_DIR / "REQUIRED_SYMBOLS.md").read_text(encoding="utf-8")
    for symbol in SYMBOLS:
        assert symbol in required
    assert "data_acquisition_required" in required
    assert "provider_review_required" in required
    assert "It does not mean the symbol is unavailable" in required
    manifest = json.loads((LATEST_DIR / "data_acquisition_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["required_symbols_reviewed"]) == SYMBOLS
    assert manifest["symbols_currently_cached"] == ["SPY", "BIL"]
    assert set(manifest["symbols_missing_from_cache"]) == {"MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV"}
    assert manifest["missing_cache_interpretation"] == "data_acquisition_required_or_provider_review_required_not_data_unavailable"


def test_provider_review_quality_requirements_and_download_plan_are_review_only() -> None:
    provider_review = (LATEST_DIR / "PROVIDER_CANDIDATE_REVIEW.md").read_text(encoding="utf-8")
    quality = (LATEST_DIR / "DATA_QUALITY_REQUIREMENTS.md").read_text(encoding="utf-8")
    plan = (LATEST_DIR / "DATA_DOWNLOAD_PLAN.md").read_text(encoding="utf-8")
    for provider in PROVIDERS:
        assert provider in provider_review or provider in plan
    assert "This review does not call APIs and does not download data" in provider_review
    assert "No download is performed by this packet" in plan
    assert "Raw OHLCV must not be included" in quality
    assert "No secrets in the repo" in plan


def test_data_acquisition_decision_and_safety_manifest() -> None:
    decision = (LATEST_DIR / "DATA_ACQUISITION_DECISION.md").read_text(encoding="utf-8")
    manifest = json.loads((LATEST_DIR / "data_acquisition_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in {
        "acquisition_review_passed_create_download_prompt",
        "conditional_pending_terms_or_api_key",
        "defer_provider_review_required",
        "reject_no_acceptable_provider",
    }
    assert manifest["decision"] == "conditional_pending_terms_or_api_key"
    assert "Decision: `conditional_pending_terms_or_api_key`" in decision
    assert manifest["data_downloaded"] in {False, True}
    assert manifest["api_called"] in {False, True}
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["raw_ohlcv_included"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False


def test_strategy_lab_value_momentum_status_is_acquisition_gate_not_reject() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["status"] in {
        "provider_review_required",
        "data_acquisition_required",
        "conditional_pending_data_acquisition",
        "provider_terms_review_passed",
        "conditional_terms_review_required",
        "data_acquired_pending_quality_check",
        "data_quality_review_passed",
        "partial_data_acquired_quality_review_required",
        "data_acquisition_failed",
        "duplicate_or_near_duplicate",
    }
    assert row["status"] != "reject_for_now"
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {
        "create_data_download_prompt",
        "provider_terms_review",
        "data_quality_review",
        "terms_review_followup",
        "keyed_provider_review",
        "update_implementation_review_after_data_quality",
        "data_quality_followup",
        "provider_fallback_review",
        "research_sample_review",
    }
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]
    assert "promote_to_real_money" in row["forbidden_next_actions"]


def test_no_api_keys_raw_data_strategy_or_backtest_artifacts() -> None:
    forbidden_secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{12,}"),
        re.compile(r"api[_-]?key\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
        re.compile(r"token\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
    ]
    for path in list(ROOT.rglob("*")) + list(LATEST_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".json", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        assert "raw ohlcv rows" not in lower
        assert "real-money ready" not in lower
        assert "recommended real trade" not in lower
        assert not any(pattern.search(text) for pattern in forbidden_secret_patterns)
    assert "run_backtest.py" not in Path("run_profit_exploration.py").read_text(encoding="utf-8")


def test_advisor_upload_references_data_acquisition_review_without_extra_top_level_zip(tmp_path: Path) -> None:
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
        names = zf.namelist()
        assert "DATA_ACQUISITION_REVIEW_INDEX.csv" in names
        index = zf.read("DATA_ACQUISITION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert REVIEW_ID in index
    assert "conditional_pending_terms_or_api_key" in index
    assert "Value/momentum factor ETF data acquisition review packet:" in executive
