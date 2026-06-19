from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import run_dual_momentum_paa_etf_wrapper_research_sample as sample


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
    normalized = sample.build_adjusted_ohlc(synthetic_raw(symbol, periods, drift), symbol)
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


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


def write_state(root: Path) -> None:
    review_dir = root / "evidence" / "lane_reviews" / sample.FAMILY_ID / "latest"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / f"{sample.FAMILY_ID}_manifest.json").write_text(
        json.dumps(
            {
                "lane_verdict": "approve_future_research_sample_prompt",
                "next_action": "create_dual_momentum_paa_etf_wrapper_research_sample_prompt",
            }
        ),
        encoding="utf-8",
    )
    rows = [
        base_row("current_no_cash_proxy_alpha_AB", "sector_momentum_plus_trend_following", "active_observation", "observe_only", True),
        base_row("paper_forward_vm_quality_lowvol_proxy_v1", "volatility_managed_equity_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "defensive_sector_rotation_etf", "active_paper_demo_observation", "observe_only", True),
        base_row("SPY_200d_trend_model", "absolute_trend", "active_observation", "observe_only", True),
        base_row("managed_futures_etf_wrapper", "managed_futures_etf_wrapper", "watchlist_family", "create_gtaa_faber_style_benchmark_lane_review_prompt"),
        base_row(sample.FAMILY_ID, sample.FAMILY_ID, "research_sample_candidate", "create_dual_momentum_paa_etf_wrapper_research_sample_prompt", False, 2),
    ]
    rows[4]["family_verdict"] = "watchlist_family"
    registry_path = root / "strategy_lab" / "strategy_registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def seed_data(root: Path, periods: int = 620, defensive_flat: bool = False) -> None:
    for symbol in sample.CORE_SYMBOLS + sample.CONDITIONAL_BENCHMARKS:
        drift = 0.00025
        if defensive_flat and symbol not in {"BIL", "GLD", "IEF"}:
            drift = -0.00005
        write_cache(root, symbol, periods, drift)


def test_fixed_variants_and_no_forbidden_flags(tmp_path: Path) -> None:
    write_state(tmp_path)
    seed_data(tmp_path)
    result = sample.run_research_sample(tmp_path, allow_download=False)
    latest = Path(result["output_dir"])
    verdicts = pd.read_csv(latest / "dual_momentum_paa_etf_wrapper_strategy_verdicts.csv")
    assert set(sample.VARIANT_IDS) == set(verdicts["strategy_id"])
    consistency = json.loads((latest / "dual_momentum_paa_etf_wrapper_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["no_direct_futures"] is True
    assert consistency["no_options"] is True
    assert consistency["no_forex"] is True
    assert consistency["no_crypto"] is True
    assert consistency["no_intraday"] is True
    assert consistency["no_leverage_added_by_system"] is True
    assert consistency["no_shorting"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_real_money_recommendation"] is True
    assert consistency["consistency_passed"] is True


def test_missing_symbols_are_recorded_and_every_row_gets_verdict(tmp_path: Path) -> None:
    write_state(tmp_path)
    for symbol in ["SPY", "EFA", "EEM", "BIL"]:
        write_cache(tmp_path, symbol, 620, 0.0002)
    result = sample.run_research_sample(tmp_path, allow_download=False)
    latest = Path(result["output_dir"])
    missing = pd.read_csv(latest / "dual_momentum_paa_etf_wrapper_missing_symbols.csv")
    assert {"QQQ", "IWM", "GLD", "IEF"}.issubset(set(missing["symbol"]))
    verdicts = pd.read_csv(latest / "dual_momentum_paa_etf_wrapper_strategy_verdicts.csv")
    assert set(sample.VARIANT_IDS) == set(verdicts["strategy_id"])


def test_active_observations_safe_and_bil_heavy_labeled(tmp_path: Path) -> None:
    write_state(tmp_path)
    seed_data(tmp_path, defensive_flat=True)
    before = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    before_rows = {row["id"]: row for row in before["strategies"]}
    sample.run_research_sample(tmp_path, allow_download=False)
    after = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    after_rows = {row["id"]: row for row in after["strategies"]}
    for row_id in sample.PROTECTED_IDS:
        assert after_rows[row_id] == before_rows[row_id]
    text = (tmp_path / sample.OUTPUT_DIR / "dual_momentum_paa_etf_wrapper_bil_heavy_behavior_review.md").read_text(encoding="utf-8")
    assert "BIL-Heavy Behavior" in text
    for row_id, row in after_rows.items():
        if row_id.startswith("dm_") or row_id == sample.FAMILY_ID:
            assert row["paper_forward_active"] is False
            assert row["real_money_recommendation"] is False
            assert row["candidate_exhaustive_run"] is False
