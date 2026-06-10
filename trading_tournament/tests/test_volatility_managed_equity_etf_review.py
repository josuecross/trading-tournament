from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import run_volatility_managed_equity_etf_review as review


def run_review_once(run_id: str) -> dict[str, object]:
    run_dir = Path("evidence/lane_reviews/volatility_managed_equity_etf/runs") / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    return review.run_review(run_id=run_id)


def test_volatility_review_outputs_are_created(tmp_path: Path) -> None:
    result = run_review_once("test_run")
    latest = Path(result["latest_dir"])
    assert latest.exists()
    for name in review.REQUIRED_OUTPUTS:
        assert (latest / name).exists(), name
    assert (latest / "volatility_managed_equity_etf_review_packet.zip").exists()


def test_next_action_is_explicit_and_research_sample_only() -> None:
    run_review_once("next_action_test")
    latest = Path("evidence/lane_reviews/volatility_managed_equity_etf/latest")
    text = (latest / "volatility_managed_equity_etf_next_action.md").read_text(encoding="utf-8")
    assert "Decision: `approve_future_research_sample_prompt`" in text
    assert "create_volatility_managed_equity_etf_research_sample_prompt" in text
    assert "candidate_exhaustive" in text
    assert "paper_forward_activation" in text


def test_consistency_check_blocks_forbidden_activity() -> None:
    run_review_once("consistency_test")
    latest = Path("evidence/lane_reviews/volatility_managed_equity_etf/latest")
    consistency = json.loads(
        (latest / "volatility_managed_equity_etf_consistency_check.json").read_text(encoding="utf-8")
    )
    assert consistency["consistency_passed"] is True
    assert consistency["no_backtest_run"] is True
    assert consistency["no_data_download"] is True
    assert consistency["no_provider_api_call"] is True
    assert consistency["no_profit_exploration_run"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_forward_activation"] is True
    assert consistency["no_active_observation_mutation"] is True
    assert consistency["no_frozen_control_mutation"] is True
    assert consistency["no_broker_integration"] is True
    assert consistency["no_live_orders"] is True
    assert consistency["no_real_money_recommendation"] is True


def test_fixed_variants_are_listed_and_forbid_unapproved_mechanics() -> None:
    run_review_once("variants_test")
    latest = Path("evidence/lane_reviews/volatility_managed_equity_etf/latest")
    rows = list(csv.DictReader((latest / "volatility_managed_equity_etf_candidate_variants.csv").open()))
    assert {row["strategy_id"] for row in rows} == {
        "vm_spy_realized_vol_target_v1",
        "vm_spy_drawdown_vol_filter_v1",
        "vm_quality_lowvol_proxy_v1",
        "vm_sector_vol_scaled_top2_v1",
        "vm_combo_overlay_v1",
    }
    for row in rows:
        forbidden = row["forbidden_next_actions"]
        assert "parameter_optimization" in forbidden
        assert "paper_forward_activation" in forbidden
        assert "active_combo_mutation" in forbidden
        assert "SPY_200d_replacement" in forbidden
        assert "broker_integration" in forbidden
        assert "live_orders" in forbidden
        assert "real_money_recommendation" in forbidden


def test_rejection_criteria_and_benchmark_plan_exist() -> None:
    run_review_once("criteria_test")
    latest = Path("evidence/lane_reviews/volatility_managed_equity_etf/latest")
    rejection = (latest / "volatility_managed_equity_etf_rejection_criteria.md").read_text(encoding="utf-8")
    assert "+$300 target-before-stop" in rejection
    assert "drawdown budget still breaches" in rejection.lower()
    assert "duplicates `SPY_200d_trend_model`" in rejection
    benchmarks = list(csv.DictReader((latest / "volatility_managed_equity_etf_benchmark_plan.csv").open()))
    assert {"SPY_200d_trend_model", "SPY_buy_hold", "BIL_cash_proxy"}.issubset(
        {row["benchmark_id"] for row in benchmarks}
    )


def test_review_command_does_not_contain_strategy_execution_hooks() -> None:
    source = Path("run_volatility_managed_equity_etf_review.py").read_text(encoding="utf-8")
    assert "run_backtest.py" not in source
    assert "run_profit_exploration.py" not in source
    assert "import yfinance" not in source.lower()
    assert "yf.download" not in source.lower()
    assert "requests." not in source
