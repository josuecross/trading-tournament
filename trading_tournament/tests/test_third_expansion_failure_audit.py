from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "tournament_failure_synthesis" / "third_expansion_failure_audit" / "latest"


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))


def test_third_expansion_failure_audit_packet_exists() -> None:
    required = [
        "third_expansion_failure_audit_manifest.json",
        "third_expansion_failure_audit_summary.md",
        "failure_reason_taxonomy.csv",
        "rejected_variant_closure_table.csv",
        "family_status_after_failures.csv",
        "lane_failure_summary.csv",
        "high_return_high_drawdown_review.md",
        "defensive_macro_diversifier_review.md",
        "implementation_quality_review.md",
        "benchmark_control_usage_update.md",
        "recommended_next_research_policy.md",
        "third_expansion_failure_audit_next_action.md",
        "third_expansion_failure_audit_consistency_check.json",
    ]
    for name in required:
        assert (EVIDENCE_DIR / name).exists(), name


def test_third_expansion_failure_audit_strict_scope_flags() -> None:
    manifest = load_json("third_expansion_failure_audit_manifest.json")
    assert manifest["audit_only"] is True
    assert manifest["new_backtests_run"] is False
    assert manifest["new_discovery_run"] is False
    assert manifest["new_performance_metrics_computed"] is False
    assert manifest["provider_download"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_review"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_path_touched"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False


def test_third_expansion_failure_audit_consistency_passes() -> None:
    check = load_json("third_expansion_failure_audit_consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["next_action_valid"] is True
    assert check["manifest_flags_match_strict_scope"] is True


def test_third_expansion_failure_audit_decision_is_represented() -> None:
    manifest = load_json("third_expansion_failure_audit_manifest.json")
    assert manifest["promotion_candidates_current_count"] == 0
    assert manifest["daily_weekly_expansion_should_pause"] is True
    assert manifest["exact_rejected_variants_closed"] is True
    assert manifest["next_action"] == "pre_register_intraday_research_readiness_audit"
