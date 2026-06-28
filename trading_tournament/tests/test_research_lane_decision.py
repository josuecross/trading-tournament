from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_research_lane_decision as lane


ACTIVE_VM = "paper_forward_vm_quality_lowvol_proxy_v1"
ACTIVE_DSR = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"


def registry_row(row_id: str, active: bool, status: str, decision: str, family: str = "test_family") -> dict[str, object]:
    return {
        "id": row_id,
        "strategy_id": row_id,
        "strategy_family": family,
        "family": family,
        "status": status,
        "current_status": status,
        "promotion_decision": decision,
        "paper_forward_active": active,
        "rules_frozen": active,
        "latest_known_result_summary": "synthetic evidence",
        "duplication_risk": "not_flagged",
        "real_money_recommendation": False,
        "candidate_exhaustive_recommended": False,
    }


def write_registry(root: Path) -> None:
    rows = [
        registry_row(ACTIVE_VM, True, "active_paper_demo_observation", "keep_active", "volatility_managed_equity_etf"),
        registry_row(ACTIVE_DSR, True, "active_paper_demo_observation", "keep_active", "defensive_sector_rotation_etf"),
        registry_row("dsr_sector_top2_momentum_200d_bil_v1", False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row("dsr_sector_top3_momentum_defensive_cash_v1", False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row("qvm_quality_value_momentum_risk_adjusted_top2_v1", False, "mark_too_risky", "mark_too_risky"),
        registry_row("qvm_quality_value_momentum_top2_v1", False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row("lvq_lowvol_quality_spy_regime_v1", False, "keep_watchlist", "keep_watchlist"),
        registry_row("gror_balanced_momentum_60_40_v1", False, "watchlist", "keep_watchlist", "global_risk_on_risk_off_etf"),
        registry_row("managed_futures_proxy_etf_trend_v1", False, "too_slow", "too_slow_for_profit_goal", "managed_futures_etf_wrapper"),
        registry_row("managed_futures_etf_wrapper", False, "watchlist_family", "keep_watchlist", "managed_futures_etf_wrapper"),
        registry_row("dm_paa_breadth_protection_v1", False, "watchlist", "keep_watchlist", "dual_momentum_paa_etf_wrapper"),
        registry_row("dual_momentum_paa_etf_wrapper", False, "watchlist_family", "keep_watchlist", "dual_momentum_paa_etf_wrapper"),
        registry_row("gtaa_faber_style_benchmark_lane", False, "watchlist_family", "benchmark_watchlist", "gtaa_faber_style_benchmark_lane"),
        registry_row("static_all_weather_or_permanent_portfolio_benchmark", False, "watchlist_family", "benchmark_watchlist", "static_all_weather_or_permanent_portfolio_benchmark"),
        registry_row("yield_credit_trend_filter_v1", False, "too_slow_for_profit_goal", "too_slow_for_profit_goal", "carry_yield_etf_proxy"),
    ]
    path = root / "strategy_lab" / "strategy_registry.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def write_symbol_map(root: Path) -> None:
    path = root / "strategy_lab" / "approved_etf_symbol_map.yaml"
    rows = [{"symbol": symbol, "allowed_for_strategy": True, "allowed_for_benchmark": True} for symbol in ["SPY", "QQQ", "BIL", "EFA", "EEM"]]
    path.write_text(yaml.safe_dump({"symbols": rows}, sort_keys=False), encoding="utf-8")


def write_required_dirs(root: Path) -> None:
    required = [
        "evidence/promotion_reviews/qvm_quality_value_momentum_risk_adjusted_top2_v1/latest",
        "evidence/promotion_reviews/qvm_quality_value_momentum_top2_v1/latest",
        "evidence/promotion_reviews/lvq_lowvol_quality_spy_regime_v1/latest",
        "evidence/promotion_reviews/dsr_sector_top2_momentum_200d_bil_v1/latest",
        "evidence/promotion_reviews/dsr_sector_top3_momentum_defensive_cash_v1/latest",
        "evidence/active_strategy_evidence_recompute/latest",
        "evidence/research_state/latest",
        "evidence/strategy_lab/latest",
    ]
    for item in required:
        (root / item).mkdir(parents=True, exist_ok=True)


def write_readiness(root: Path) -> None:
    path = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"missing_symbols": []}), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def write_discovery(root: Path) -> None:
    result_cols = ["strategy_id", "family_group", "180d_median_final_equity", "180d_worst_drawdown", "risk_buffer_vs_minus_600", "decision"]
    write_csv(
        root / "evidence" / "parallel_research_discovery" / "new_batch_approved_cache" / "latest" / "parallel_discovery_approved_cache_results.csv",
        [
            {"strategy_id": "qvm_quality_value_momentum_risk_adjusted_top2_v1", "family_group": "quality_value_momentum_blend", "180d_median_final_equity": 3512.0, "180d_worst_drawdown": -581.0, "risk_buffer_vs_minus_600": 19.0, "decision": "promotion_review_candidate"},
            {"strategy_id": "qvm_quality_value_momentum_top2_v1", "family_group": "quality_value_momentum_blend", "180d_median_final_equity": 3470.0, "180d_worst_drawdown": -581.0, "risk_buffer_vs_minus_600": 19.0, "decision": "promotion_review_candidate"},
            {"strategy_id": "lvq_lowvol_quality_spy_regime_v1", "family_group": "lowvol_quality_hybrid", "180d_median_final_equity": 3350.0, "180d_worst_drawdown": -221.0, "risk_buffer_vs_minus_600": 379.0, "decision": "promotion_review_candidate"},
        ],
        result_cols,
    )
    write_csv(
        root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_results.csv",
        [{"strategy_id": "benchmark_quality_lowvol_equal_weight_v1", "family_group": "benchmark_sanity_rows", "180d_median_final_equity": 3280.0, "180d_worst_drawdown": -217.0, "risk_buffer_vs_minus_600": 383.0, "decision": "benchmark_watchlist"}],
        result_cols,
    )
    write_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_promotion_candidates.csv", [], result_cols)
    write_csv(
        root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_results.csv",
        [{"strategy_id": "gwcb_qvm_70_30_cash_brake_v1", "family_group": "growth_with_cash_brake", "180d_median_final_equity": 3353.0, "180d_worst_drawdown": -197.0, "risk_buffer_vs_minus_600": 403.0, "decision": "duplicate_or_near_duplicate"}],
        result_cols,
    )
    write_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_promotion_candidates.csv", [], result_cols)


def prepared_root(tmp_path: Path) -> Path:
    write_registry(tmp_path)
    write_symbol_map(tmp_path)
    write_required_dirs(tmp_path)
    write_readiness(tmp_path)
    write_discovery(tmp_path)
    return tmp_path


@pytest.fixture()
def audited_fixture(tmp_path: Path) -> dict[str, object]:
    root = prepared_root(tmp_path)
    result = lane.run_lane_decision(root, strict_state=True)
    return {"root": root, "result": result}


def test_no_strategy_runner_is_called(audited_fixture: dict[str, object]) -> None:
    manifest = json.loads((Path(audited_fixture["result"]["output_dir"]) / "research_lane_decision_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_run"] is False
    assert audited_fixture["result"]["consistency"]["no_strategy_run"] is True


def test_no_provider_download_is_called(audited_fixture: dict[str, object]) -> None:
    manifest = json.loads((Path(audited_fixture["result"]["output_dir"]) / "research_lane_decision_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_api_called"] is False
    assert manifest["data_downloaded"] is False


def test_no_candidate_exhaustive_flag_is_created(audited_fixture: dict[str, object]) -> None:
    consistency = audited_fixture["result"]["consistency"]
    assert consistency["no_candidate_exhaustive_run"] is True


def test_no_paper_forward_active_flag_is_set(audited_fixture: dict[str, object]) -> None:
    registry = yaml.safe_load((Path(audited_fixture["root"]) / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    failed_ids = {
        "qvm_quality_value_momentum_risk_adjusted_top2_v1",
        "qvm_quality_value_momentum_top2_v1",
        "lvq_lowvol_quality_spy_regime_v1",
        "dsr_sector_top2_momentum_200d_bil_v1",
        "dsr_sector_top3_momentum_defensive_cash_v1",
    }
    assert all(row["paper_forward_active"] is False for row in registry["strategies"] if row["id"] in failed_ids)
    assert audited_fixture["result"]["consistency"]["no_paper_forward_activation"] is True


def test_current_failed_candidates_are_represented(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    audit = pd.read_csv(output / "research_lane_failure_pattern_audit.csv")
    represented = set(audit["strategy_or_family"])
    assert {"DSR Top2", "DSR Top3", "QVM risk-adjusted top2", "QVM top2", "LVQ SPY-regime"} <= represented


def test_next_lane_recommendation_is_explicit(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    text = (output / "recommended_next_lane.md").read_text(encoding="utf-8")
    assert lane.RECOMMENDED_NEXT_ACTION in text
    assert audited_fixture["result"]["recommended_next_action"] == lane.RECOMMENDED_NEXT_ACTION


def test_symbol_expansion_proposal_is_proposed_only_not_approved(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    proposal = yaml.safe_load((output / "proposed_symbol_expansion_if_any.yaml").read_text(encoding="utf-8"))
    assert proposal["status"] == "proposed_only_not_approved"
    assert proposal["rules"]["approve_automatically"] is False
    assert proposal["rules"]["download_now"] is False
    assert proposal["symbols"]


def test_consistency_check_passes(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    consistency = json.loads((output / "research_lane_decision_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
