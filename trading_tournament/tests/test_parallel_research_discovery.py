from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_parallel_research_discovery as discovery


def synthetic_raw(symbol: str, periods: int = 620, drift: float = 0.0002) -> pd.DataFrame:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.001 * ((idx % 11) - 5) / 10.0))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": [100000] * periods,
            "Dividends": [0.0] * periods,
            "Stock Splits": [0.0] * periods,
        }
    )


def write_cache(root: Path, symbol: str, periods: int = 620, drift: float = 0.0002) -> None:
    normalized = discovery.build_adjusted_ohlc(synthetic_raw(symbol, periods, drift), symbol)
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


def write_registry(root: Path) -> None:
    rows = []
    for row_id, family, active in [
        ("current_no_cash_proxy_alpha_AB", "sector_momentum_plus_trend_following", True),
        ("paper_forward_vm_quality_lowvol_proxy_v1", "volatility_managed_equity_etf", True),
        ("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "defensive_sector_rotation_etf", True),
        ("SPY_200d_trend_model", "absolute_trend", True),
        ("gtaa_faber_style_benchmark_lane", "gtaa_faber_style_benchmark_lane", False),
        ("static_all_weather_or_permanent_portfolio_benchmark", "static_all_weather_or_permanent_portfolio_benchmark", False),
    ]:
        rows.append(
            {
                "id": row_id,
                "display_name": row_id,
                "lane": "paper_forward" if active else "profit_exploration",
                "instrument_family": "ETF",
                "strategy_family": family,
                "version": "v1",
                "parent_id": "",
                "credibility_tier": "tier4_paper_forward" if active else "tier1_research_queue",
                "status": "active_observation" if active else "research_queue",
                "role": "test_row",
                "rules_frozen": True,
                "paper_forward_active": active,
                "implementation_status": "implemented" if active else "not_implemented",
                "data_source": "existing_adjusted_etf_cache",
                "evidence_source": "test",
                "latest_evidence_path": "evidence/test/latest/",
                "latest_known_result_summary": "test",
                "allowed_next_action": "observe_only" if active else "research_sample_review",
                "next_allowed_action": "observe_only" if active else "research_sample_review",
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
                "current_status": "active_observation" if active else "research_queue",
                "allowed_next_actions": ["observe_only" if active else "research_sample_review"],
                "candidate_exhaustive_run": False,
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
        )
    path = root / "strategy_lab" / "strategy_registry.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def minimal_queue() -> dict:
    return {
        "approved_symbols": ["SPY", "EFA", "EEM", "GLD", "IEF", "BIL"],
        "families": [
            {
                "family_id": "gtaa_faber_style_benchmark_lane",
                "priority_rank": 1,
                "run_enabled": True,
                "stage": "research_sample",
                "evidence_tier": "exploratory",
                "approved_symbols": ["SPY", "EFA", "EEM", "GLD", "IEF", "BIL"],
                "max_variants": 1,
                "variants": [{"strategy_id": "gtaa_equal_weight_trend_filter_v1", "rule_type": "gtaa_equal_weight_trend_filter", "universe": ["SPY", "EFA", "EEM", "GLD", "IEF", "BIL"]}],
            },
            {
                "family_id": "static_all_weather_or_permanent_portfolio_benchmark",
                "priority_rank": 2,
                "run_enabled": True,
                "stage": "research_sample",
                "evidence_tier": "exploratory",
                "approved_symbols": ["SPY", "GLD", "IEF", "BIL"],
                "max_variants": 1,
                "variants": [{"strategy_id": "static_all_weather_equal_weight_v1", "rule_type": "static_equal_weight", "universe": ["SPY", "GLD", "IEF", "BIL"]}],
            },
        ],
    }


def seed(root: Path) -> None:
    for symbol in ["SPY", "EFA", "EEM", "GLD", "IEF", "BIL"]:
        write_cache(root, symbol, drift=0.0002)


def test_queue_yaml_loads() -> None:
    queue = yaml.safe_load((Path.cwd() / "strategy_lab" / "parallel_research_discovery_queue.yaml").read_text(encoding="utf-8"))
    discovery.validate_queue(queue)
    assert len([fam for fam in queue["families"] if fam["run_enabled"]]) == 5


def test_forbidden_symbols_rejected() -> None:
    queue = minimal_queue()
    queue["families"][0]["approved_symbols"].append("AAPL")
    with pytest.raises(ValueError):
        discovery.validate_queue(queue)


def test_multiple_families_processed_and_outputs_isolated(tmp_path: Path) -> None:
    write_registry(tmp_path)
    seed(tmp_path)
    queue_path = tmp_path / discovery.QUEUE_PATH
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(yaml.safe_dump(minimal_queue(), sort_keys=False), encoding="utf-8")
    result = discovery.run_parallel_discovery(tmp_path, allow_download=False)
    latest = Path(result["output_dir"])
    assert (latest / "strategy_leaderboard.csv").exists()
    assert (latest / "family_leaderboard.csv").exists()
    assert set(result["families_tested"]) == {"gtaa_faber_style_benchmark_lane", "static_all_weather_or_permanent_portfolio_benchmark"}
    for family in result["families_tested"]:
        assert (tmp_path / "evidence" / "research_samples" / family / "latest").exists()
    leaderboard = pd.read_csv(latest / "strategy_leaderboard.csv")
    assert leaderboard["strategy_verdict"].notna().all()
    consistency = json.loads((latest / "parallel_research_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_forward_activation"] is True
    assert consistency["no_real_money_recommendation"] is True
    assert consistency["consistency_passed"] is True
