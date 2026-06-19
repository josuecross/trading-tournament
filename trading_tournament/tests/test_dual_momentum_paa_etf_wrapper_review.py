from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import run_dual_momentum_paa_etf_wrapper_review as review


def base_row(row_id: str, family: str, status: str, action: str, active: bool = False, priority: int | None = None) -> dict:
    row = {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": family,
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active else "tier1_research_queue",
        "status": status,
        "role": "test_row",
        "rules_frozen": True,
        "paper_forward_active": active,
        "implementation_status": "implemented" if active else "not_implemented",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "conversation_recovered",
        "latest_evidence_path": "evidence/test/latest/",
        "latest_known_result_summary": "test",
        "allowed_next_action": action,
        "next_allowed_action": action,
        "forbidden_next_actions": ["promote_to_real_money", "add_broker_integration", "place_live_orders"],
        "risk_framework_status": "paper_forward_allowed" if active else "research_only",
        "paper_forward_allowed_by_risk_framework": active,
        "real_money_recommendation": False,
        "promotion_blockers": "none" if active else "planning_only",
        "promotion_requirements": "test",
        "demotion_or_kill_criteria": "test",
        "notes": "test",
        "strategy_id": row_id,
        "family": family,
        "instrument_lane": "ETF",
        "evidence_tier": "tier4_paper_forward" if active else "tier1_research_queue",
        "current_status": status,
        "allowed_next_actions": [action],
        "candidate_exhaustive_run": row_id == "gror_balanced_momentum_60_40_v1",
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "test",
        "promotion_reason": "test",
        "primary_failure_mode": "not_tested",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "test",
        "evidence_needed": "test",
        "duplicate_of": "",
        "blocked_reason": "",
    }
    if priority is not None:
        row["priority_rank"] = priority
    return row


def write_fixture(root: Path) -> None:
    sample_dir = root / "evidence" / "research_samples" / "managed_futures_etf_wrapper" / "latest"
    sample_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "managed_futures_etf_wrapper_manifest.json").write_text(
        json.dumps(
            {
                "family_verdict": "watchlist_family",
                "next_action": "create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt",
            }
        ),
        encoding="utf-8",
    )
    rows = [
        base_row("current_no_cash_proxy_alpha_AB", "sector_momentum_plus_trend_following", "active_observation", "observe_only", True),
        base_row("paper_forward_vm_quality_lowvol_proxy_v1", "volatility_managed_equity_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "defensive_sector_rotation_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("SPY_200d_trend_model", "absolute_trend", "active_observation", "observe_only", True),
        base_row("gror_balanced_momentum_60_40_v1", "global_risk_on_risk_off_etf", "watchlist", "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane"),
        base_row("quality_momentum_etf_proxy", "quality_momentum_etf_proxy", "watchlist_no_more_rescue_now", "keep_quality_momentum_on_watchlist"),
        base_row("managed_futures_etf_wrapper", "managed_futures_etf_wrapper", "watchlist_family", "create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt", False, 1),
        base_row(review.LANE_ID, review.LANE_ID, "future_family_review", "create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt", False, 2),
    ]
    registry_path = root / "strategy_lab" / "strategy_registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump({"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": rows}, sort_keys=False),
        encoding="utf-8",
    )


def test_review_outputs_variants_and_boundaries_exist(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    result = review.run_review(tmp_path)
    latest = Path(result["output_dir"])
    required = [
        "dual_momentum_paa_etf_wrapper_review.md",
        "dual_momentum_paa_etf_wrapper_family_thesis.md",
        "dual_momentum_paa_etf_wrapper_data_policy.md",
        "dual_momentum_paa_etf_wrapper_fixed_rules.md",
        "dual_momentum_paa_etf_wrapper_candidate_variants.csv",
        "dual_momentum_paa_etf_wrapper_risk_policy.md",
        "dual_momentum_paa_etf_wrapper_duplicate_risk_plan.md",
        "dual_momentum_paa_etf_wrapper_benchmark_plan.csv",
        "dual_momentum_paa_etf_wrapper_rejection_criteria.md",
        "dual_momentum_paa_etf_wrapper_next_action.md",
        "dual_momentum_paa_etf_wrapper_manifest.json",
        "dual_momentum_paa_etf_wrapper_consistency_check.json",
        "dual_momentum_paa_etf_wrapper_review_packet.zip",
    ]
    for name in required:
        assert (latest / name).exists()
    variants = pd.read_csv(latest / "dual_momentum_paa_etf_wrapper_candidate_variants.csv")
    assert set(variants["strategy_id"]) == set(result["approved_variants"])
    text = (latest / "dual_momentum_paa_etf_wrapper_data_policy.md").read_text(encoding="utf-8")
    assert "ETF/fund-wrapper" in text
    assert "direct futures" in text


def test_no_run_flags_and_next_action_are_explicit(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    result = review.run_review(tmp_path)
    latest = Path(result["output_dir"])
    manifest = json.loads((latest / "dual_momentum_paa_etf_wrapper_manifest.json").read_text(encoding="utf-8"))
    consistency = json.loads((latest / "dual_momentum_paa_etf_wrapper_consistency_check.json").read_text(encoding="utf-8"))
    assert manifest["next_action"] == "create_dual_momentum_paa_etf_wrapper_research_sample_prompt"
    assert manifest["backtest_run"] is False
    assert manifest["research_sample_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False
    assert manifest["real_money_recommendation"] is False
    assert consistency["no_options"] is True
    assert consistency["no_forex"] is True
    assert consistency["no_crypto"] is True
    assert consistency["no_intraday"] is True
    assert consistency["no_leverage_added_by_system"] is True
    assert consistency["no_shorting"] is True
    assert consistency["consistency_passed"] is True


def test_active_observations_are_unchanged_and_registry_row_safe(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    before = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    before_rows = {row["id"]: row for row in before["strategies"]}
    review.run_review(tmp_path)
    after = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    after_rows = {row["id"]: row for row in after["strategies"]}
    for row_id in review.PROTECTED_IDS:
        assert after_rows[row_id] == before_rows[row_id]
    dual = after_rows[review.LANE_ID]
    assert dual["paper_forward_active"] is False
    assert dual["real_money_recommendation"] is False
    assert dual["candidate_exhaustive_run"] is False
    assert dual["allowed_next_action"] == "create_dual_momentum_paa_etf_wrapper_research_sample_prompt"
