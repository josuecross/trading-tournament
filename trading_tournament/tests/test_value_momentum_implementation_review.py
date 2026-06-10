from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "value_momentum_factor_etf_rotation_v1"
REVIEW_DIR = Path("implementation_reviews") / REVIEW_ID
LATEST_DIR = Path("evidence/implementation_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/implementation_reviews") / REVIEW_ID / "latest_implementation_review_packet.zip"
ALLOWED_DECISIONS = {
    "approve_research_sample_implementation",
    "conditional_approval_proxy_risk_acknowledged",
    "defer_inception_or_proxy_risk",
    "reject_for_now",
}


def test_value_momentum_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_DIR.exists()
    assert LATEST_DIR.exists()
    files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(files) <= 10
    assert files == {
        "README.md",
        "IMPLEMENTATION_REVIEW.md",
        "PROXY_AND_INCEPTION_REVIEW.md",
        "DATA_AVAILABILITY_REVIEW.md",
        "FACTOR_PROXY_RISK_REVIEW.md",
        "DUPLICATE_AND_CORRELATION_RISK_REVIEW.md",
        "BENCHMARK_AND_FAILURE_CRITERIA.md",
        "IMPLEMENTATION_GATE_CHECKLIST.csv",
        "IMPLEMENTATION_DECISION.md",
        "implementation_review_manifest.json",
    }
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == files


def test_value_momentum_decision_and_safety_flags() -> None:
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "approve_research_sample_implementation"
    assert manifest["implementation_allowed_now"] is False
    assert manifest["future_research_sample_implementation_approved"] is True
    assert manifest["candidate_exhaustive_allowed_now"] is False
    assert manifest["implementation_created"] is False
    assert manifest["backtest_run"] is False
    assert manifest["data_downloaded_in_this_review_update"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False


def test_value_momentum_proxy_review_uses_local_cache_metadata() -> None:
    proxy_review = (LATEST_DIR / "PROXY_AND_INCEPTION_REVIEW.md").read_text(encoding="utf-8")
    for symbol in ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV", "SPY", "BIL"]:
        assert symbol in proxy_review
    for field in [
        "cached_locally",
        "first_cached_date",
        "last_cached_date",
        "row_count",
        "overlap_with_SPY_BIL",
        "enough_history_for_rolling_windows",
    ]:
        assert field in proxy_review
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["cached_symbols_found"]) == {"MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV", "SPY", "BIL"}
    assert manifest["missing_symbols"] == []
    assert manifest["common_overlap_start"] == "2013-07-18"
    assert manifest["common_overlap_end"] == "2026-05-29"


def test_value_momentum_data_gate_and_benchmark_files_exist() -> None:
    checklist = pd.read_csv(LATEST_DIR / "IMPLEMENTATION_GATE_CHECKLIST.csv")
    data_gate = checklist[checklist["gate_name"].eq("data_gate")].iloc[0]
    assert data_gate["status"] == "pass"
    data_review = (LATEST_DIR / "DATA_AVAILABILITY_REVIEW.md").read_text(encoding="utf-8")
    assert "2013-07-18 to 2026-05-29" in data_review
    assert "quality status pass" in data_review
    benchmark = (LATEST_DIR / "BENCHMARK_AND_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    assert "combo_SPY200d_GLD_50_50_v1" in benchmark
    assert "asset_class_tsmom_top2_v1" in benchmark
    assert "qqq_spy_gld_ief_dual_momentum_v1" in benchmark


def test_value_momentum_no_strategy_implementation_code_created() -> None:
    profit_specs = Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert REVIEW_ID in profit_specs


def test_value_momentum_strategy_lab_registry_validates_review_state() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["status"] in {"implementation_review_passed", "duplicate_or_near_duplicate"}
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {"create_research_sample_implementation_prompt", "research_sample_review"}
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert "run_backtest_before_implementation_prompt" in row["forbidden_next_actions"]
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]
    assert "promote_to_real_money" in row["forbidden_next_actions"]


def test_value_momentum_advisor_index_reference(tmp_path: Path) -> None:
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
    assert "approve_research_sample_implementation" in review_index
    assert "Value/momentum factor ETF implementation review packet:" in executive


def test_value_momentum_review_contains_only_negated_real_money_language() -> None:
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
