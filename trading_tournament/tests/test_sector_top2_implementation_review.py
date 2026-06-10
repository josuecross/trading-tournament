from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "sector_top2_momentum_simple_v1"
REVIEW_DIR = Path("implementation_reviews") / REVIEW_ID
LATEST_DIR = Path("evidence/implementation_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/implementation_reviews") / REVIEW_ID / "latest_implementation_review_packet.zip"
ALLOWED_DECISIONS = {
    "approve_research_sample_implementation",
    "approve_research_sample_implementation_core_nine",
    "conditional_approval_pending_universe_review",
    "defer_data_gated",
    "defer_duplicate_risk",
    "reject_for_now",
}
EXPECTED_FILES = {
    "README.md",
    "IMPLEMENTATION_REVIEW.md",
    "SECTOR_UNIVERSE_REVIEW.md",
    "DATA_AVAILABILITY_REVIEW.md",
    "A_STRATEGY_STREAM_REVIEW.md",
    "DUPLICATE_AND_CORRELATION_RISK_REVIEW.md",
    "BENCHMARK_AND_FAILURE_CRITERIA.md",
    "IMPLEMENTATION_GATE_CHECKLIST.csv",
    "IMPLEMENTATION_DECISION.md",
    "implementation_review_manifest.json",
}


def test_sector_top2_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_DIR.exists()
    assert (REVIEW_DIR / "SECTOR_UNIVERSE_POLICY.md").exists()
    assert LATEST_DIR.exists()
    latest_files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(latest_files) <= 10
    assert latest_files == EXPECTED_FILES
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == latest_files


def test_sector_top2_decision_and_safety_flags() -> None:
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "approve_research_sample_implementation_core_nine"
    assert manifest["universe_policy_decision"] == "core_nine_fixed_universe"
    assert manifest["implementation_allowed_now"] is False
    assert manifest["future_research_sample_implementation_approved"] is True
    assert manifest["candidate_exhaustive_allowed_now"] is False
    assert manifest["implementation_created"] is False
    assert manifest["backtest_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["a_strategy_modified"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False


def test_sector_universe_policy_core_nine_rule() -> None:
    policy = (REVIEW_DIR / "SECTOR_UNIVERSE_POLICY.md").read_text(encoding="utf-8")
    implementation_review = (LATEST_DIR / "IMPLEMENTATION_REVIEW.md").read_text(encoding="utf-8")
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    expected_core = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    assert "Decision: `core_nine_fixed_universe`" in policy
    assert "Policy chosen: `core_nine_fixed_universe`" in implementation_review
    assert manifest["future_allowed_sector_universe"] == expected_core
    assert manifest["future_fallback_symbol"] == "BIL"
    assert manifest["excluded_from_first_rule"] == ["XLC", "XLRE"]
    assert manifest["xlc_excluded_from_first_rule"] is True
    assert manifest["xlre_excluded_from_first_rule"] is True
    assert "No XLC" in policy
    assert "No XLRE" in policy
    assert "No variants" in policy


def test_sector_universe_and_data_review_use_local_cache_metadata() -> None:
    universe = (LATEST_DIR / "SECTOR_UNIVERSE_REVIEW.md").read_text(encoding="utf-8")
    data_review = (LATEST_DIR / "DATA_AVAILABILITY_REVIEW.md").read_text(encoding="utf-8")
    for symbol in ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]:
        assert symbol in universe
    for field in [
        "cached_locally",
        "first_cached_date",
        "last_cached_date",
        "row_count",
        "enough_history_for_rolling_windows",
    ]:
        assert field in universe
    assert "2007-01-03 to 2026-05-29" in data_review
    assert "2018-06-19 to 2026-05-29" in data_review
    assert "XLRE is missing" in data_review
    manifest = json.loads((LATEST_DIR / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["core_cached_sector_symbols"]) == {"XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
    assert manifest["missing_symbols"] == ["XLRE"]


def test_sector_top2_a_stream_duplicate_and_benchmark_reviews_exist() -> None:
    stream = (LATEST_DIR / "A_STRATEGY_STREAM_REVIEW.md").read_text(encoding="utf-8")
    duplicate = (LATEST_DIR / "DUPLICATE_AND_CORRELATION_RISK_REVIEW.md").read_text(encoding="utf-8")
    benchmark = (LATEST_DIR / "BENCHMARK_AND_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    assert "A_ETF_sector_momentum" in stream
    assert "not be modified" in stream
    assert "clean new minimal implementation" in stream
    assert "qqq_spy_gld_ief_dual_momentum_v1" in duplicate
    assert "value_momentum_factor_etf_rotation_v1" in duplicate
    assert "combo_SPY200d_GLD_50_50_v1" in benchmark
    assert "asset_class_tsmom_top2_v1" in benchmark
    assert "A_ETF_sector_momentum" in benchmark


def test_sector_top2_gate_checklist_statuses() -> None:
    checklist = pd.read_csv(LATEST_DIR / "IMPLEMENTATION_GATE_CHECKLIST.csv")
    statuses = dict(zip(checklist["gate_name"], checklist["status"], strict=True))
    assert statuses["data_gate"] == "pass"
    assert statuses["execution_realism_gate"] == "pass"
    assert statuses["risk_model_gate"] == "pass"
    assert statuses["benchmark_gate"] == "pass"
    assert statuses["diversification_gate"] == "conditional"
    assert statuses["anti_overfitting_gate"] == "pass"


def test_sector_top2_no_strategy_implementation_code_created() -> None:
    run_profit = Path("run_profit_exploration.py").read_text(encoding="utf-8")
    specs = Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert REVIEW_ID in run_profit
    assert REVIEW_ID in specs
    assert "run_backtest.py" not in run_profit
    assert "sector_top2_momentum_simple_v1" not in "".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in Path("src").glob("*.py")
    )


def test_sector_top2_strategy_lab_registry_validates_review_state() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["lane"] in {"strategy_candidate_queue", "profit_exploration"}
    assert row["status"] in {"implementation_review_passed", "watchlist"}
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {"create_research_sample_implementation_prompt", "research_sample_review"}
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert any("run_backtest" in action for action in row["forbidden_next_actions"])
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]
    assert "promote_to_real_money" in row["forbidden_next_actions"]


def test_sector_top2_advisor_index_reference(tmp_path: Path) -> None:
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
    assert "approve_research_sample_implementation_core_nine" in review_index
    assert "Sector top2 ETF implementation review packet:" in executive


def test_sector_top2_review_contains_only_negated_real_money_language() -> None:
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
                or "make a real-money recommendation" in text
            )
