from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "managed_futures_proxy_etf_trend_v1"
REVIEW_DIR = Path("implementation_reviews") / REVIEW_ID
LATEST_DIR = Path("evidence/implementation_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/implementation_reviews") / REVIEW_ID / "latest_implementation_review_packet.zip"
ALLOWED_DECISIONS = {
    "approve_research_sample_implementation",
    "conditional_approval_pending_data_review",
    "data_acquisition_required",
    "defer_proxy_inception_risk",
    "reject_for_now",
}
EXPECTED_FILES = {
    "README.md",
    "IMPLEMENTATION_REVIEW.md",
    "PROXY_AND_INCEPTION_REVIEW.md",
    "DATA_AVAILABILITY_REVIEW.md",
    "MANAGED_FUTURES_PROXY_RISK_REVIEW.md",
    "DUPLICATE_AND_CORRELATION_RISK_REVIEW.md",
    "BENCHMARK_AND_FAILURE_CRITERIA.md",
    "IMPLEMENTATION_GATE_CHECKLIST.csv",
    "IMPLEMENTATION_DECISION.md",
    "implementation_review_manifest.json",
}


def test_managed_futures_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_DIR.exists()
    assert LATEST_DIR.exists()
    latest_files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(latest_files) <= 10
    assert latest_files == EXPECTED_FILES
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == latest_files


def test_managed_futures_decision_and_safety_flags() -> None:
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "data_acquisition_required"
    assert manifest["future_research_sample_implementation_approved"] is False
    assert manifest["data_acquisition_review_needed"] is True
    assert manifest["implementation_allowed_now"] is False
    assert manifest["candidate_exhaustive_allowed_now"] is False
    assert manifest["implementation_created"] is False
    assert manifest["backtest_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["api_called"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["futures_contract_logic_added"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False


def test_managed_futures_proxy_review_uses_local_cache_metadata() -> None:
    proxy_review = (LATEST_DIR / "PROXY_AND_INCEPTION_REVIEW.md").read_text(encoding="utf-8")
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    for symbol in ["DBMF", "KMLM", "CTA", "FMF", "WTMF"]:
        assert symbol in proxy_review
    for field in [
        "cached_locally",
        "first_cached_date",
        "last_cached_date",
        "row_count",
        "enough_history_for_rolling_windows",
        "inception_or_history_risk",
        "proxy_quality",
    ]:
        assert field in proxy_review
    assert manifest["cached_proxy_symbols_found"] == []
    assert set(manifest["missing_proxy_symbols"]) == {"DBMF", "KMLM", "CTA", "FMF", "WTMF"}
    assert manifest["common_overlap_window"] == "not_calculable_no_proxy_cache"


def test_managed_futures_review_files_and_gate_statuses() -> None:
    assert (LATEST_DIR / "DATA_AVAILABILITY_REVIEW.md").exists()
    assert (LATEST_DIR / "MANAGED_FUTURES_PROXY_RISK_REVIEW.md").exists()
    assert (LATEST_DIR / "BENCHMARK_AND_FAILURE_CRITERIA.md").exists()
    checklist = pd.read_csv(LATEST_DIR / "IMPLEMENTATION_GATE_CHECKLIST.csv")
    statuses = dict(zip(checklist["gate_name"], checklist["status"], strict=True))
    assert statuses["data_gate"] == "fail"
    assert statuses["benchmark_gate"] == "pass"
    assert statuses["anti_overfitting_gate"] == "pass"


def test_managed_futures_no_strategy_implementation_code_created() -> None:
    run_profit = Path("run_profit_exploration.py").read_text(encoding="utf-8")
    specs = Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert REVIEW_ID in run_profit
    assert REVIEW_ID in specs
    assert "run_backtest.py" not in run_profit


def test_managed_futures_strategy_lab_registry_validates_review_state() -> None:
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
        "too_slow",
    }
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {
        "create_data_download_prompt",
        "provider_terms_review",
        "issuer_methodology_review",
        "create_research_sample_implementation_prompt",
        "research_sample_review",
    }
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert any("futures_contract_logic" in action for action in row["forbidden_next_actions"])
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]


def test_managed_futures_advisor_index_reference(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    assert len([path for path in latest.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        review_index = zf.read("PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert REVIEW_ID in review_index
    assert "data_acquisition_required" in review_index
    assert "Managed-futures proxy implementation review packet:" in executive


def test_managed_futures_review_contains_only_negated_real_money_language() -> None:
    for path in LATEST_DIR.iterdir():
        if path.suffix.lower() not in {".md", ".csv", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "real-money ready" not in text
        assert "recommended real trade" not in text
        assert "guaranteed" not in text
        assert "proven" not in text
        if "real-money recommendation" in text:
            assert (
                "no real-money recommendation" in text
                or "does not make a real-money recommendation" in text
                or "no paper-forward activation or real-money recommendation" in text
            )
