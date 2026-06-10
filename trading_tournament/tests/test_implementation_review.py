from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml


REVIEW_ROOT = Path("implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1")
LATEST_ROOT = Path("evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest")
ZIP_PATH = Path("evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest_implementation_review_packet.zip")
ALLOWED_DECISIONS = {
    "approve_research_sample_implementation",
    "conditional_approval_pending_data_check",
    "defer_duplicate_risk",
    "defer_data_gated",
    "reject_for_now",
}


def load_registry() -> dict:
    return yaml.safe_load(Path("strategy_lab/strategy_registry.yaml").read_text(encoding="utf-8"))


def test_implementation_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_ROOT.exists()
    assert LATEST_ROOT.exists()
    latest_files = [path.name for path in LATEST_ROOT.iterdir() if path.is_file()]
    assert len(latest_files) <= 10
    for name in [
        "README.md",
        "IMPLEMENTATION_REVIEW.md",
        "DATA_AVAILABILITY_REVIEW.md",
        "DUPLICATE_RISK_REVIEW.md",
        "EQUITY_BETA_RISK_REVIEW.md",
        "BENCHMARK_AND_FAILURE_CRITERIA.md",
        "IMPLEMENTATION_GATE_CHECKLIST.csv",
        "IMPLEMENTATION_DECISION.md",
        "implementation_review_manifest.json",
    ]:
        assert (REVIEW_ROOT / name).exists()
        assert (LATEST_ROOT / name).exists()
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert "IMPLEMENTATION_DECISION.md" in zf.namelist()
        assert "implementation_review_manifest.json" in zf.namelist()


def test_implementation_decision_is_allowed_and_does_not_activate_anything() -> None:
    manifest = json.loads((LATEST_ROOT / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "approve_research_sample_implementation"
    assert manifest["implementation_created"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    decision = (LATEST_ROOT / "IMPLEMENTATION_DECISION.md").read_text(encoding="utf-8")
    assert "Decision: `approve_research_sample_implementation`" in decision
    assert "It does not implement the strategy in this task" in decision


def test_implementation_review_checks_qqq_data_availability() -> None:
    manifest = json.loads((LATEST_ROOT / "implementation_review_manifest.json").read_text(encoding="utf-8"))
    data_review = (LATEST_ROOT / "DATA_AVAILABILITY_REVIEW.md").read_text(encoding="utf-8")
    assert manifest["qqq_cached"] is True
    assert "QQQ appears in the existing local cache" in data_review
    assert "4,882" in data_review
    assert "4,781 rows" in data_review
    assert "no-network implementation appears possible" in data_review.lower()


def test_implementation_review_includes_duplicate_and_benchmark_criteria() -> None:
    duplicate = (LATEST_ROOT / "DUPLICATE_RISK_REVIEW.md").read_text(encoding="utf-8")
    beta = (LATEST_ROOT / "EQUITY_BETA_RISK_REVIEW.md").read_text(encoding="utf-8")
    benchmarks = (LATEST_ROOT / "BENCHMARK_AND_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    checklist = (LATEST_ROOT / "IMPLEMENTATION_GATE_CHECKLIST.csv").read_text(encoding="utf-8")
    assert "asset_class_tsmom_top2_v1" in duplicate
    assert "higher-beta SPY trend sleeve" in duplicate
    assert "QQQ increases growth-equity concentration" in beta
    assert "Primary Benchmark" in benchmarks
    assert "asset_class_tsmom_top2_v1" in benchmarks
    assert "diversification_gate" in checklist
    assert "anti_overfitting_gate" in checklist


def test_implementation_review_only_approved_research_sample_code() -> None:
    profit_engine = Path("run_profit_exploration.py").read_text(encoding="utf-8")
    strategy_files = "".join(path.read_text(encoding="utf-8", errors="ignore") for path in Path("src").glob("*.py"))
    assert "qqq_spy_gld_ief_dual_momentum_v1" in profit_engine
    assert "candidate_exhaustive_in_this_task" in Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert "qqq_spy_gld_ief_dual_momentum_v1" not in strategy_files


def test_implementation_review_registry_row_remains_research_sample_only() -> None:
    rows = load_registry()["strategies"]
    row = next(item for item in rows if item["id"] == "qqq_spy_gld_ief_dual_momentum_v1")
    assert row["lane"] == "profit_exploration"
    assert row["status"] in {"research_sample_candidate", "watchlist", "candidate_exhaustive_queue", "duplicate_or_near_duplicate", "too_risky"}
    assert row["implementation_status"] == "implemented_research_sample"
    assert row["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review"}
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]
    assert "change_paper_forward_rules" in row["forbidden_next_actions"]
