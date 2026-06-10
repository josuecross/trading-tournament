from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "value_momentum_factor_etf_rotation_v1"
ROOT = Path("data_acquisition_reviews") / REVIEW_ID / "provider_terms_security_review"
LATEST = Path("evidence/data_acquisition_reviews") / REVIEW_ID / "provider_terms_security_review" / "latest"
ZIP_PATH = (
    Path("evidence/data_acquisition_reviews")
    / REVIEW_ID
    / "provider_terms_security_review"
    / "latest_provider_terms_security_review_packet.zip"
)
ALLOWED_SYMBOLS = ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV"]


def test_provider_terms_review_packet_exists_and_is_compact() -> None:
    assert ROOT.exists()
    assert LATEST.exists()
    files = {path.name for path in LATEST.iterdir() if path.is_file()}
    assert len(files) <= 10
    assert files == {
        "README.md",
        "PROVIDER_TERMS_SECURITY_REVIEW.md",
        "YFINANCE_PATH_REVIEW.md",
        "KEYED_PROVIDER_REVIEW.md",
        "SECURITY_AND_SECRET_HANDLING.md",
        "ALLOWED_DOWNLOAD_BOUNDARY.md",
        "PROVIDER_REVIEW_DECISION.md",
        "provider_terms_review_manifest.json",
    }
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == files


def test_provider_decision_and_safety_flags() -> None:
    manifest = json.loads((LATEST / "provider_terms_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in {
        "approve_future_yfinance_download_prompt",
        "conditional_terms_review_required",
        "use_keyed_provider_review_first",
        "defer_provider_decision",
        "reject_data_acquisition_for_now",
    }
    assert manifest["decision"] == "approve_future_yfinance_download_prompt"
    assert manifest["yfinance_path_decision"] == "approve_future_download_prompt_with_metadata"
    assert manifest["keyed_provider_decision"] == "fallback_review_only"
    assert manifest["data_downloaded"] is False
    assert manifest["api_called"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["credentials_stored"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["real_money_recommendation"] is False


def test_allowed_download_boundary_is_only_missing_factor_etfs() -> None:
    manifest = json.loads((LATEST / "provider_terms_review_manifest.json").read_text(encoding="utf-8"))
    boundary = (LATEST / "ALLOWED_DOWNLOAD_BOUNDARY.md").read_text(encoding="utf-8")
    assert manifest["allowed_future_download_symbols"] == ALLOWED_SYMBOLS
    for symbol in ALLOWED_SYMBOLS:
        assert symbol in boundary
    assert "SPY and BIL are already cached" in boundary
    assert "Do not refresh or overwrite them by default" in boundary
    assert "use no backtest trigger" in boundary


def test_security_and_keyed_provider_reviews_exist() -> None:
    security = (LATEST / "SECURITY_AND_SECRET_HANDLING.md").read_text(encoding="utf-8")
    keyed = (LATEST / "KEYED_PROVIDER_REVIEW.md").read_text(encoding="utf-8")
    for phrase in [
        "API keys must never be committed",
        "API keys must not appear in evidence",
        "Advisor packets must not include secrets",
    ]:
        assert phrase in security
    for provider in ["Alpha Vantage", "Tiingo", "Nasdaq Data Link / Sharadar", "Polygon/Massive"]:
        assert provider in keyed
    assert "Keyed providers are not approved for immediate use" in keyed


def test_strategy_lab_status_after_provider_terms_review() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["status"] in {
        "provider_terms_review_passed",
        "data_acquired_pending_quality_check",
        "data_quality_review_passed",
        "partial_data_acquired_quality_review_required",
        "data_acquisition_failed",
        "duplicate_or_near_duplicate",
    }
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {
        "create_data_download_prompt",
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
    assert any("run_backtest" in action for action in row["forbidden_next_actions"])


def test_advisor_upload_references_provider_terms_review_without_extra_zip(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "09_PROVIDER_TERMS_SECURITY_REVIEW.zip" not in top_files
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        index = zf.read("DATA_ACQUISITION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "value_momentum_factor_etf_provider_terms_security_review" in index
    assert "approve_future_yfinance_download_prompt" in index
    assert "Value/momentum factor ETF provider terms/security review packet:" in executive


def test_provider_terms_review_has_no_secrets_raw_data_or_real_money_claims() -> None:
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{12,}"),
        re.compile(r"api[_-]?key\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
        re.compile(r"token\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
    ]
    for path in list(ROOT.rglob("*")) + list(LATEST.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        assert "raw ohlcv rows" not in lower
        assert "recommended real trade" not in lower
        assert "real-money ready" not in lower
        assert not any(pattern.search(text) for pattern in secret_patterns)
    assert "run_backtest.py" not in Path("run_profit_exploration.py").read_text(encoding="utf-8")
