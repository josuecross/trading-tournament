from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    implement_targeted_medium_frequency_breakout_candidate_v1 as task,
)


OUTPUT = ROOT / "evidence" / "research_recovery" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (OUTPUT / "consistency_check.json").exists()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_exact_scope_and_entity_separation() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text())
    assert manifest["strategy_ids"] == [task.STRATEGY_ID]
    assert manifest["source_library_record_count"] == 1
    assert manifest["strategy_configuration_count"] == 1
    assert manifest["canonical_experiment_trial_count"] == 1
    assert manifest["benchmark_reference_count"] == 6
    assert manifest["process_task_count"] == 1
    assert manifest["data_capability_task_count"] == 0
    assert manifest["paper_demo_observation_count"] == 0


def test_preregistration_freezes_rule_2_before_performance() -> None:
    source = rows("source_library_records.csv")
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(source) == len(strategy) == len(trial) == 1
    assert source[0]["source_record_id"] == task.SOURCE_RECORD_ID
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == ""
    assert trial[0]["adaptation_label"] == ""
    assert trial[0]["channel_contract_changed"] == "false"
    assert trial[0]["optimization_performed"] == "false"
    assert "i=0..40" in trial[0]["frozen_rule"]
    assert json_payload("consistency_check.json")[
        "preregistration_written_before_performance_calculation"
    ]


def test_regression_channel_formula_uses_40_closes_and_41_deviation_rows() -> None:
    index = pd.bdate_range("2020-01-01", periods=41)
    close = pd.Series(100.0 + 0.5 * np.arange(41), index=index)
    high = close + 2.0
    low = close - 3.0
    result = task.regression_channel_values(close, high, low).iloc[-1]
    assert result["fitted_regression_value"] == pytest.approx(close.iloc[-1])
    assert result["regression_slope"] == pytest.approx(0.5)
    assert result["upper_deviation"] == pytest.approx(2.0)
    assert result["lower_deviation"] == pytest.approx(3.0)
    assert result["projected_upper_band"] == pytest.approx(
        close.iloc[-1] + 2.5
    )
    assert result["projected_lower_band"] == pytest.approx(
        close.iloc[-1] - 2.5
    )


def test_preflight_uses_only_canonical_spy_and_bil_without_provider() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == {"SPY", "BIL"}
    assert {row["candidate_preflight_status"] for row in preflight} == {"pass"}
    assert {row["ordered_unique_dates"] for row in preflight} == {"true"}
    assert {row["finite_positive_adjusted_ohlc"] for row in preflight} == {
        "true"
    }
    assert {row["valid_adjusted_ohlc_relationships"] for row in preflight} == {
        "true"
    }
    assert {row["canonical_adjustment_compatible"] for row in preflight} == {
        "true"
    }
    assert {row["provider_accessed"] for row in preflight} == {"false"}
    assert {row["network_accessed"] for row in preflight} == {"false"}


def test_channel_diagnostics_preserve_strict_rule_2_contract() -> None:
    signals = rows("channel_signal_diagnostics.csv")
    eligible = [row for row in signals if row["regression_input_count"] == "40"]
    assert eligible
    assert {row["deviation_input_count"] for row in eligible} == {"41"}
    assert {row["rule_number"] for row in eligible} == {"2"}
    assert {row["channel_contract"] for row in eligible} == {
        "TradingView_Rule_2_only"
    }
    entries = [row for row in eligible if row["entry_signal"] == "true"]
    exits = [row for row in eligible if row["exit_signal"] == "true"]
    assert entries and exits
    for row in entries:
        assert float(row["adjusted_close"]) > float(row["projected_upper_band"])
        assert row["current_state"] == "BIL"
    for row in exits:
        assert float(row["adjusted_close"]) < float(row["projected_lower_band"])
        assert row["current_state"] == "SPY"


def test_every_candidate_trade_uses_following_open_accounting() -> None:
    execution = rows("open_execution_reconciliation.csv")
    events = [row for row in execution if row["event_type"] in {"entry", "exit"}]
    assert events
    for row in events:
        assert pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["date"])
        assert row["same_close_fill_used"] == "false"
        assert row["stale_open_forward_fill_used"] == "false"
        assert abs(float(row["decomposition_difference"])) <= 1e-9
        assert row["transaction_cost_charged_once"] == "true"
        assert float(row["one_way_turnover"]) == pytest.approx(1.0)


def test_trade_ledger_and_holding_diagnostics_are_complete() -> None:
    trades = rows("trade_ledger.csv")
    holdings = rows("holding_period_diagnostics.csv")
    assert trades
    assert holdings
    completed = [row for row in trades if row["terminal_open_status"] == "false"]
    assert completed
    assert all(
        row["exit_reason"] == "strict_projected_lower_band_break"
        for row in completed
    )
    assert all(int(row["holding_sessions"]) >= 1 for row in completed)
    summary = holdings[0]
    assert summary["whipsaw_definition"]
    assert int(summary["completed_trades"]) == len(completed)


def test_controls_costs_halves_and_portfolio_diagnostics_are_complete() -> None:
    candidate = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    portfolios = rows("portfolio_contribution_results.csv")
    assert len(candidate) == 3
    assert len(controls) == 18
    assert len(halves) == 14
    assert len(portfolios) == 12
    assert {row["benchmark_id"] for row in benchmarks} == set(task.CONTROL_IDS)
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_validation"
    }
    assert {row["daily_fixed_weight_return_blend_used"] for row in portfolios} == {
        "false"
    }
    nonreference = [
        row for row in portfolios if row["portfolio_id"] != task.PORTFOLIO_IDS["reference"]
    ]
    for row in nonreference:
        assert float(row["transaction_cost_drag"]) == pytest.approx(
            float(row["inner_sleeve_transaction_cost_drag"])
            + float(row["outer_transaction_cost_drag"])
        )


def test_exposure_match_is_frozen_and_not_optimized() -> None:
    exposure = rows("exposure_control_reconciliation.csv")
    assert len(exposure) == 3
    assert {row["optimized_or_rounded"] for row in exposure} == {"false"}
    assert {row["performance_selected"] for row in exposure} == {"false"}
    assert {row["matches_candidate_target_exposure"] for row in exposure} == {
        "true"
    }


def test_all_invariants_and_serial_determinism_pass() -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 21
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["no_signal_close_fill"] for row in invariants} == {"true"}
    assert {row["transaction_costs_charged_once"] for row in invariants} == {
        "true"
    }
    assert {row["no_stale_open_forward_fill"] for row in invariants} == {"true"}
    candidate = [
        row for row in invariants if row["row_id"] == task.STRATEGY_ID
    ]
    assert {row["serial_rerun_deterministic"] for row in candidate} == {"true"}


def test_outcome_and_protected_state_are_auditable() -> None:
    outcome = rows("outcome_summary.csv")[0]
    consistency = json_payload("consistency_check.json")
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_standalone",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["provider_access"] is False
    assert consistency["network_access"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert consistency["paper_demo_observations_created"] == 0
    assert consistency["parameter_search_performed"] is False
    assert consistency["broker_orders"] == 0
    assert consistency["real_money_actions"] == 0
