from __future__ import annotations

import run_parallel_research_discovery as discovery
import run_strategy_lab


def test_new_exploratory_labels_are_registry_accepted() -> None:
    expected = {
        "diversifier_watchlist_candidate",
        "short_history_watchlist",
        "benchmark_watchlist",
        "defensive_watchlist",
        "too_slow_for_profit_goal",
        "duplicate_watchlist",
        "needs_benchmark_delta_review",
    }
    assert expected <= discovery.EXPLORATORY_LABELS
    assert expected <= run_strategy_lab.ALLOWED_STATUSES


def test_new_labels_do_not_promote_or_unlock_validation() -> None:
    for label in discovery.EXPLORATORY_LABELS:
        assert discovery.is_promotion_candidate(label) is False
        next_action = discovery.next_action_for_verdict(label)
        assert next_action != discovery.NEXT_PROMOTION
        assert next_action != "run_candidate_exhaustive"
        assert "candidate_exhaustive" not in next_action
        assert "paper_forward" not in next_action


def test_promotion_thresholds_are_unchanged() -> None:
    assert discovery.PROMOTION_SCORE_THRESHOLD == 70
    assert discovery.PROMOTION_TARGET300_THRESHOLD == 0.25


def test_refined_watchlist_label_stays_non_promotion() -> None:
    summary = {
        "final_equity_median": 3060.0,
        "target_300_rate": 0.05,
        "target_400_rate": 0.02,
        "worst_drawdown": -180.0,
        "absolute_600_stop_hit_rate": 0.0,
        "median_profit_dollars": 60.0,
    }
    label, verdict = discovery.refine_exploratory_verdict(
        "carry_yield_etf_proxy",
        "carry_yield_defensive_filter_v1",
        summary,
        "weak",
        "too_slow",
        0.42,
        0,
        True,
    )
    assert label == "too_slow_for_profit_goal"
    assert verdict == "too_slow_for_profit_goal"
    assert discovery.is_promotion_candidate(verdict) is False
    assert discovery.next_action_for_verdict(verdict) == discovery.NEXT_CONTINUE
