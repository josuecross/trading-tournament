from __future__ import annotations

import csv
import json

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as task,
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


def test_preregistration_freezes_exact_rule_before_performance() -> None:
    sources = rows("source_library_records.csv")
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert len(sources) == len(strategies) == len(trials) == 1
    assert sources[0]["source_record_id"] == task.SOURCE_RECORD_ID
    assert trials[0]["trial_id"] == task.TRIAL_ID
    assert trials[0]["parent_trial_id"] == ""
    assert trials[0]["adaptation_label"] == ""
    assert trials[0]["source_rule_changed"] == "false"
    assert trials[0]["parameters_changed"] == "false"
    assert trials[0]["instruments_changed"] == "false"
    assert trials[0]["execution_changed"] == "false"
    assert trials[0]["optimization_performed"] == "false"
    assert "maximum holding period" in trials[0]["frozen_rule"]
    consistency = json_payload("consistency_check.json")
    assert consistency["preregistration_written_before_performance_calculation"]


def test_preflight_uses_only_complete_canonical_spy_and_bil() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == {"SPY", "BIL"}
    assert {row["candidate_preflight_status"] for row in preflight} == {"pass"}
    assert {row["ordered_unique_dates"] for row in preflight} == {"true"}
    assert {row["finite_positive_adjusted_ohlc"] for row in preflight} == {"true"}
    assert {row["finite_nonnegative_adjusted_volume"] for row in preflight} == {
        "true"
    }
    assert {row["valid_adjusted_ohlc_relationships"] for row in preflight} == {
        "true"
    }
    assert {row["canonical_adjustment_compatible"] for row in preflight} == {
        "true"
    }
    assert {row["identical_common_dates"] for row in preflight} == {"true"}
    assert {row["provider_accessed"] for row in preflight} == {"false"}


def test_inclusive_seven_session_signals_and_entry_only_trend_filter() -> None:
    signals = rows("signal_diagnostics.csv")
    assert len(signals) > 4000
    assert {row["channel_includes_current_close"] for row in signals} == {"true"}
    entries = [row for row in signals if row["entry_signal"] == "true"]
    exits = [row for row in signals if row["exit_signal"] == "true"]
    assert entries and exits
    for row in entries:
        assert float(row["adjusted_close"]) <= float(row["channel_low_7"]) + 1e-10
        assert float(row["adjusted_close"]) > float(row["SMA200"])
        assert row["holding_at_signal_close"] == "BIL"
    for row in exits:
        assert float(row["adjusted_close"]) >= float(row["channel_high_7"]) - 1e-10
        assert row["holding_at_signal_close"] == "SPY"
    assert all(row["maximum_holding_period"] == "" for row in signals)
    assert all(row["stop_loss"] == "" for row in signals)


def test_every_trade_executes_at_following_open_without_same_close_fill() -> None:
    execution = rows("open_execution_reconciliation.csv")
    events = [row for row in execution if row["event_type"] in {"entry", "exit"}]
    assert events
    for row in events:
        assert pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["date"])
        assert row["same_close_fill_used"] == "false"
        assert row["stale_open_forward_fill_used"] == "false"
        assert abs(float(row["decomposition_difference"])) <= 1e-9
        assert row["transaction_cost_charged_once"] == "true"


def test_open_accounting_assigns_returns_to_correct_holdings() -> None:
    execution = rows("open_execution_reconciliation.csv")
    entries = [row for row in execution if row["event_type"] == "entry"]
    exits = [row for row in execution if row["event_type"] == "exit"]
    assert entries and exits
    for row in entries:
        assert float(row["pretrade_BIL_weight"]) == pytest.approx(1.0)
        assert float(row["target_SPY_weight"]) == pytest.approx(1.0)
        assert float(row["target_BIL_weight"]) == pytest.approx(0.0)
        assert float(row["one_way_turnover"]) == pytest.approx(1.0)
    for row in exits:
        assert float(row["pretrade_SPY_weight"]) == pytest.approx(1.0)
        assert float(row["target_SPY_weight"]) == pytest.approx(0.0)
        assert float(row["target_BIL_weight"]) == pytest.approx(1.0)
        assert float(row["one_way_turnover"]) == pytest.approx(1.0)


def test_trade_ledger_has_no_added_stop_or_maximum_hold() -> None:
    trades = rows("trade_ledger.csv")
    assert trades
    assert all(
        row["exit_reason"]
        in {"inclusive_seven_session_closing_high", "open_at_evaluation_end"}
        for row in trades
    )
    assert all(int(row["holding_sessions"]) >= 1 for row in trades)
    completed = [
        row for row in trades if row["trade_open_at_evaluation_end"] == "false"
    ]
    assert completed
    assert all(row["exit_execution_date"] for row in completed)


def test_controls_costs_halves_and_exposure_match_are_complete() -> None:
    candidates = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    exposure = rows("exposure_control_reconciliation.csv")
    assert len(candidates) == 3
    assert len(controls) == 18
    assert len(halves) == 14
    assert {row["benchmark_id"] for row in benchmarks} == set(task.CONTROL_IDS)
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_validation"
    }
    assert len(exposure) == 3
    assert {row["optimized_or_rounded"] for row in exposure} == {"false"}
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


def test_outcome_is_exactly_derived_from_frozen_gate() -> None:
    outcome = rows("outcome_summary.csv")[0]
    consistency = json_payload("consistency_check.json")
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_standalone",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    gates = json.loads(outcome["followup_gate"])
    if outcome["outcome"] == "exploratory_followup_candidate_standalone":
        assert all(gates.values())
        assert outcome["failure_reason"] == ""
        assert outcome["exact_next_action"] == task.NEXT_ADVANCE
    else:
        assert not all(gates.values())
        assert outcome["failure_reason"]
    assert consistency["overall_pass"] is True


def test_protected_state_cache_and_prior_evidence_remain_unchanged() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["provider_access"] is False
    assert consistency["network_access"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert consistency["paper_demo_observations_created"] == 0
    assert consistency["parameter_search_performed"] is False
    assert consistency["broker_orders"] == 0
    assert consistency["paper_orders"] == 0
    assert consistency["live_orders"] == 0
    assert consistency["real_money_actions"] == 0
