from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from run_promotion_review import Metrics, classify_strategy, load_thresholds


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "evidence" / "promotion_review" / "latest"


def base_row(**overrides):
    row = {
        "id": "test_strategy",
        "strategy_family": "test_family",
        "instrument_family": "ETF",
        "lane": "profit_exploration",
        "credibility_tier": "tier2_credible_prototype",
        "status": "research_sample_candidate",
        "implementation_status": "implemented_research_sample",
        "paper_forward_active": False,
        "real_money_recommendation": False,
        "latest_evidence_path": "evidence/test/latest/",
        "forbidden_next_actions": ["observe_as_paper_forward", "promote_to_real_money"],
        "promotion_blockers": "",
        "notes": "research only",
    }
    row.update(overrides)
    return row


def empty_sets():
    return {"active": set(), "leaders": set(), "blocked": set()}


def passing_metrics():
    return Metrics(
        p90_target_300=0.2,
        p90_target_400=0.08,
        p90_stop=0.0,
        worst_90d_drawdown=-350.0,
        p180_stop=0.0,
        worst_180d_drawdown=-500.0,
        stress_degradation=25.0,
        source="synthetic",
    )


def test_active_observation_is_protected() -> None:
    decision = classify_strategy(base_row(paper_forward_active=True, status="active_paper_demo_observation"), passing_metrics(), empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "keep_active_observation"
    assert decision["candidate_exhaustive_allowed"] is False


def test_frozen_control_is_protected() -> None:
    decision = classify_strategy(base_row(id="SPY_200d_trend_model", status="active_observation"), passing_metrics(), empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "keep_frozen_control"
    assert decision["recommended_next_action"] == "compare_only"


def test_research_sample_row_can_queue_when_thresholds_pass() -> None:
    decision = classify_strategy(base_row(), passing_metrics(), empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "promote_to_candidate_exhaustive_queue"
    assert decision["candidate_exhaustive_allowed"] is True
    assert decision["paper_forward_allowed"] is False


def test_drawdown_breach_is_too_risky_not_promoted() -> None:
    metrics = passing_metrics()
    metrics.worst_90d_drawdown = -650.0
    decision = classify_strategy(base_row(), metrics, empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "mark_too_risky"
    assert decision["candidate_exhaustive_allowed"] is False


def test_duplicate_is_not_promoted() -> None:
    metrics = passing_metrics()
    metrics.high_correlation_to_leader = True
    metrics.correlation_evidence = "combo correlation 0.910"
    decision = classify_strategy(base_row(), metrics, empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "mark_duplicate_or_near_duplicate"


def test_blocked_stock_row_remains_blocked() -> None:
    decision = classify_strategy(
        base_row(id="individual_stock_momentum_gate1b_v1", instrument_family="individual_stock_momentum", status="conditional_pending_package_and_terms_selection"),
        passing_metrics(),
        empty_sets(),
        load_thresholds(),
    )
    assert decision["promotion_decision"] == "blocked"
    assert "blocker" in decision["recommended_next_action"]


def test_crypto_execution_gate_requires_review_not_queue() -> None:
    row = base_row(
        id="combo_plus_crypto_spot_tsmom_90_10_v1",
        instrument_family="crypto_spot",
        lane="crypto_exploratory",
        credibility_tier="tier2_credible_prototype",
        promotion_blockers="exchange_cost_24_7_review_required",
    )
    decision = classify_strategy(row, passing_metrics(), empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "promotion_review_required"
    assert decision["candidate_exhaustive_allowed"] is False


def test_missing_candidate_evidence_requires_specific_review() -> None:
    decision = classify_strategy(base_row(), Metrics(verdict="research_sample_candidate"), empty_sets(), load_thresholds())
    assert decision["promotion_decision"] == "promotion_review_required"
    assert "missing" in decision["evidence_needed"]


def test_run_promotion_review_generates_required_outputs() -> None:
    result = subprocess.run([sys.executable, "run_promotion_review.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "candidate_exhaustive_run=false" in result.stdout
    required = [
        "promotion_review_summary.md",
        "promotion_decisions.csv",
        "promotion_candidates.csv",
        "protected_successful_strategies.csv",
        "historical_success_registry.csv",
        "rejected_or_blocked_rows.csv",
        "duplicate_or_near_duplicate_rows.csv",
        "promotion_thresholds_used.yaml",
        "promotion_review_manifest.json",
        "promotion_review_warnings.md",
        "next_candidate_exhaustive_queue.md",
        "next_paper_forward_review_queue.md",
        "promotion_review_consistency_check.json",
    ]
    for name in required:
        assert (LATEST / name).exists()
    check = json.loads((LATEST / "promotion_review_consistency_check.json").read_text(encoding="utf-8"))
    assert check["consistency_status"] == "passed"
    decisions = pd.read_csv(LATEST / "promotion_decisions.csv")
    assert decisions["promotion_reason"].fillna("").str.len().gt(0).all()
    assert not decisions["real_money_recommendation"].astype(bool).any()
    assert not decisions[decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")]["paper_forward_active"].astype(bool).any()
