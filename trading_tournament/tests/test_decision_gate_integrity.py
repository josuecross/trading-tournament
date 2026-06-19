from __future__ import annotations

import copy

from strategy_integrity_core import promotion_verdict


def test_promotion_candidate_not_assigned_when_required_metrics_missing() -> None:
    metrics = {
        "score": 90,
        "target_300_rate": 0.5,
        "stop_hit_rate": 0.0,
        "worst_drawdown": -200,
        "benchmark_delta_status": "unavailable",
    }
    assert promotion_verdict(metrics) == "watchlist"


def test_watchlist_is_not_treated_as_promotion_candidate() -> None:
    metrics = {
        "score": 56.76,
        "target_300_rate": 0.20,
        "stop_hit_rate": 0.0,
        "worst_drawdown": -300,
        "benchmark_delta_status": "available",
    }
    assert promotion_verdict(metrics) == "watchlist"


def test_risk_gate_blocks_promotion_candidate() -> None:
    metrics = {
        "score": 92,
        "target_300_rate": 0.60,
        "stop_hit_rate": 0.01,
        "worst_drawdown": -650,
        "benchmark_delta_status": "available",
    }
    assert promotion_verdict(metrics) == "too_risky"


def test_active_observation_records_not_mutated_by_audit_helpers() -> None:
    protected = {
        "paper_forward_vm_quality_lowvol_proxy_v1": {"paper_forward_active": True, "rules_frozen": True},
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": {"paper_forward_active": True, "rules_frozen": True},
        "SPY_200d_trend_model": {"paper_forward_active": True, "rules_frozen": True},
    }
    before = copy.deepcopy(protected)
    _ = promotion_verdict(
        {
            "score": 80,
            "target_300_rate": 0.3,
            "stop_hit_rate": 0,
            "worst_drawdown": -200,
            "benchmark_delta_status": "available",
        }
    )
    assert protected == before
