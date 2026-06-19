from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import run_research_roadmap as roadmap


def base_row(row_id: str, family: str, status: str, action: str, active: bool = False) -> dict:
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": family,
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active else "tier2_exploratory",
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
        "evidence_tier": "tier4_paper_forward" if active else "tier2_exploratory",
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


def write_registry(root: Path) -> None:
    rows = [
        base_row("current_no_cash_proxy_alpha_AB", "sector_momentum_plus_trend_following", "active_observation", "observe_only", True),
        base_row("paper_forward_vm_quality_lowvol_proxy_v1", "volatility_managed_equity_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "defensive_sector_rotation_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("SPY_200d_trend_model", "absolute_trend", "active_observation", "observe_only", True),
        base_row("gror_balanced_momentum_60_40_v1", "global_risk_on_risk_off_etf", "candidate_exhaustive_completed", "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane"),
        base_row("quality_momentum_etf_proxy", "quality_momentum_etf_proxy", "watchlist_family", "research_sample_review"),
        base_row("dsr_sector_top2_momentum_200d_bil_v1", "defensive_sector_rotation_etf", "promotion_review_candidate", "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1"),
        base_row("dsr_sector_top3_momentum_defensive_cash_v1", "defensive_sector_rotation_etf", "deferred_candidate_queue", "candidate_exhaustive_review"),
        base_row("managed_futures_etf_wrapper", "managed_futures_etf_wrapper", "research_queue", "research_sample_review"),
    ]
    payload = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
        },
        "strategies": rows,
    }
    registry_path = root / "strategy_lab" / "strategy_registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_research_roadmap_outputs_and_priority_order(tmp_path: Path) -> None:
    write_registry(tmp_path)
    result = roadmap.run_research_roadmap(tmp_path)
    latest = Path(result["output_dir"])

    for name in [
        "research_roadmap_summary.md",
        "strategy_family_priority_backlog.csv",
        "strategy_family_status_matrix.csv",
        "next_investigation_sequence.md",
        "deferred_and_blocked_lanes.md",
        "roadmap_decision_log.md",
        "research_roadmap_manifest.json",
        "research_roadmap_consistency_check.json",
        "research_roadmap_packet.zip",
    ]:
        assert (latest / name).exists()
    assert (tmp_path / "strategy_lab" / "RESEARCH_ROADMAP.md").exists()

    backlog = pd.read_csv(latest / "strategy_family_priority_backlog.csv")
    assert backlog.iloc[0]["family_id"] == "managed_futures_etf_wrapper"
    assert backlog.iloc[0]["next_allowed_action"] == roadmap.NEXT_ACTION
    assert backlog.iloc[1]["family_id"] == "dual_momentum_paa_etf_wrapper"


def test_watchlists_are_not_next_and_backlog_rows_are_safe(tmp_path: Path) -> None:
    write_registry(tmp_path)
    result = roadmap.run_research_roadmap(tmp_path)
    latest = Path(result["output_dir"])
    backlog = pd.read_csv(latest / "strategy_family_priority_backlog.csv")
    registry = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in registry["strategies"]}

    assert int(backlog.loc[backlog["family_id"] == "quality_momentum_etf_proxy", "priority_rank"].iloc[0]) == 7
    assert rows["quality_momentum_etf_proxy"]["next_allowed_action"] == "keep_quality_momentum_on_watchlist"
    assert rows["gror_balanced_momentum_60_40_v1"]["next_allowed_action"] == "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane"
    for row in rows.values():
        if row.get("priority_rank"):
            assert row["paper_forward_active"] is False
            assert row["real_money_recommendation"] is False


def test_active_observations_remain_unchanged_and_consistency_passes(tmp_path: Path) -> None:
    write_registry(tmp_path)
    before = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    before_rows = {row["id"]: row for row in before["strategies"]}
    result = roadmap.run_research_roadmap(tmp_path)
    after = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    after_rows = {row["id"]: row for row in after["strategies"]}

    for row_id in roadmap.PROTECTED_IDS:
        assert after_rows[row_id] == before_rows[row_id]

    consistency = json.loads(
        (Path(result["output_dir"]) / "research_roadmap_consistency_check.json").read_text(encoding="utf-8")
    )
    assert consistency["next_action"] == roadmap.NEXT_ACTION
    assert consistency["consistency_passed"] is True
    assert consistency["no_strategy_implementation"] is True
    assert consistency["no_backtest_run"] is True
    assert consistency["no_data_download"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_real_money_recommendation"] is True
