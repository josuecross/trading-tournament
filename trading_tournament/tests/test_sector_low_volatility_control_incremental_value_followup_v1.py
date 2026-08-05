from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    sector_low_volatility_control_incremental_value_followup_v1 as task,
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
    manifest = yaml.safe_load((OUTPUT / "followup_manifest.yaml").read_text())
    assert manifest["strategy_ids"] == [task.STRATEGY_ID]
    assert manifest["route"] == "diversifier_only"
    assert manifest["source_library_records_created"] == 0
    assert manifest["source_research_lineage_records_carried_forward"] == 1
    assert manifest["strategy_configurations_created"] == 1
    assert manifest["parent_experiment_trials_carried_forward"] == 1
    assert manifest["new_experiment_trials"] == 1
    assert manifest["benchmark_reference_count"] == 5
    assert manifest["process_task_count"] == 1
    assert manifest["data_capability_task_count"] == 0
    assert manifest["paper_demo_observation_count"] == 0


def test_parent_and_child_trial_lineage_are_distinct_and_exact() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 2
    parent_row = next(
        row for row in trials if row["record_role"] == "carried_forward_parent_trial_read_only"
    )
    child = next(
        row for row in trials if row["record_role"] == "new_child_experiment_trial"
    )
    assert parent_row["strategy_id"] == task.PARENT_STRATEGY_ID
    assert parent_row["trial_id"] == task.PARENT_TRIAL_ID
    assert parent_row["family_id"] == task.parent.FAMILY_ID
    assert parent_row["strategy_architecture"] == task.parent.ARCHITECTURE
    assert parent_row["outcome"] == "closed_exploration"
    assert parent_row["failure_reason"] == "low_volatility_control_explanation"
    assert child["strategy_id"] == task.STRATEGY_ID
    assert child["trial_id"] == task.TRIAL_ID
    assert child["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert child["adaptation_label"] == "exploratory_variant"
    assert child["result_driven_adaptation"] == "true"
    assert child["new_signal_invented_after_results"] == "false"
    assert child["predeclared_benchmark_promoted_explicitly"] == "true"
    assert child["optimization_performed"] == "false"


def test_strategy_card_explicitly_records_result_driven_adaptation() -> None:
    strategy = rows("strategy_cards.csv")
    lineage = rows("source_and_adaptation_lineage.csv")
    assert len(strategy) == len(lineage) == 1
    row = strategy[0]
    assert row["strategy_id"] == task.STRATEGY_ID
    assert row["route"] == "diversifier_only"
    assert row["adaptation_label"] == "exploratory_variant"
    assert row["external_source_strategy_claimed"] == "false"
    assert row["rule_previously_preregistered_as_benchmark"] == "true"
    assert row["adaptation_selected_after_viewing_results"] == "true"
    assert row["validation_evidence_claimed"] == "false"
    assert row["authoritative_registry_record_created"] == "false"
    assert lineage[0]["new_source_library_record_created"] == "false"
    assert lineage[0]["benchmark_rule_predeclared_before_parent_performance"] == "true"


def test_parent_reproduction_gate_passes_every_check_within_1e_9() -> None:
    reproduction = rows("reproduction_check.csv")
    assert len(reproduction) >= 250
    assert {row["reproduction_pass"] for row in reproduction} == {"true"}
    numeric = [row for row in reproduction if row["difference"]]
    assert numeric
    assert max(abs(float(row["difference"])) for row in numeric) <= 1e-9
    assert any(row["metric"] == "deterministic_core_hash" for row in reproduction)
    assert any(row["metric"] == "selected_sectors" for row in reproduction)
    assert any(row["metric"] == "all_invariant_pass" for row in reproduction)


def test_static_control_is_frozen_from_first_valid_formation() -> None:
    static = rows("static_control_definition.csv")
    assert len(static) == 1
    row = static[0]
    assert json.loads(row["frozen_sectors"]) == ["XLP", "XLV", "XLI"]
    assert row["first_valid_formation_date"] == "2007-06-29"
    assert row["first_execution_date"] == "2007-07-02"
    assert row["preformation_holding"] == "BIL"
    assert row["definition_frozen_before_new_performance"] == "true"
    assert row["selected_from_full_period_performance"] == "false"
    assert row["optimization_performed"] == "false"


def test_standalone_results_costs_controls_and_halves_are_complete() -> None:
    full = rows("standalone_results.csv")
    halves = rows("standalone_chronological_half_results.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(full) == 18
    assert len(halves) == 12
    assert {row["benchmark_id"] for row in benchmarks} == set(task.CONTROL_IDS)
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    candidate_5 = next(
        row
        for row in full
        if row["row_id"] == task.STRATEGY_ID
        and row["cost_assumption_bps"] == "5"
    )
    assert float(candidate_5["total_return"]) > 0.0
    assert float(candidate_5["cagr"]) == pytest.approx(0.0977281841634)
    assert float(candidate_5["sharpe_ratio"]) == pytest.approx(0.698903936411)
    assert float(candidate_5["maximum_drawdown"]) == pytest.approx(
        -0.412592227947
    )
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_validation_or_untouched_holdout"
    }


def test_portfolio_period_construction_and_cost_rows_are_frozen() -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    halves = rows("portfolio_chronological_half_results.csv")
    assert len(portfolios) == 18
    assert len(halves) == 12
    assert {row["evaluation_start"] for row in portfolios} == {"2010-08-10"}
    assert {row["evaluation_end"] for row in portfolios} == {"2026-06-18"}
    assert {row["daily_fixed_weight_return_blend_used"] for row in portfolios} == {
        "false"
    }
    assert {
        row["natural_drift_between_outer_rebalances"] for row in portfolios
    } == {"true"}
    candidate = next(
        row
        for row in portfolios
        if row["portfolio_id"] == task.PORTFOLIO_IDS[task.STRATEGY_ID]
        and row["cost_assumption_bps"] == "5"
    )
    assert float(candidate["cagr"]) == pytest.approx(0.0963172445413)
    assert float(candidate["sharpe_ratio"]) == pytest.approx(0.906410511543)
    assert float(candidate["maximum_drawdown"]) == pytest.approx(
        -0.211696939693
    )


def test_dynamic_candidate_closes_below_static_materiality_thresholds() -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    candidate = next(
        row
        for row in portfolios
        if row["portfolio_id"] == task.PORTFOLIO_IDS[task.STRATEGY_ID]
        and row["cost_assumption_bps"] == "5"
    )
    static = next(
        row
        for row in portfolios
        if row["portfolio_id"]
        == task.PORTFOLIO_IDS[
            "static_first_valid_low_volatility_bottom3_sector_control"
        ]
        and row["cost_assumption_bps"] == "5"
    )
    sharpe_edge = float(candidate["sharpe_ratio"]) - float(static["sharpe_ratio"])
    drawdown_edge = float(candidate["maximum_drawdown"]) - float(
        static["maximum_drawdown"]
    )
    assert 0.0 < sharpe_edge < 0.02
    assert 0.0 < drawdown_edge < 0.01
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] == "closed_exploration"
    assert outcome["failure_reason"] == "benchmark_like_behavior"
    assert "static_first_valid" in outcome["decision_reason"]
    assert outcome["exact_next_action"] == task.NEXT_CLOSE


def test_all_rolling_windows_are_retained_and_summarized() -> None:
    rolling_36 = rows("rolling_36_month_portfolio_results.csv")
    rolling_60 = rows("rolling_60_month_portfolio_results.csv")
    summary = rows("rolling_window_summary.csv")
    assert len(rolling_36) == 156 * 3
    assert len(rolling_60) == 132 * 3
    assert len(summary) == 6
    assert {row["unfavorable_window_retained"] for row in rolling_36} == {"true"}
    assert {row["unfavorable_window_retained"] for row in rolling_60} == {"true"}
    assert {
        row["comparator_id"] for row in rolling_36
    } == set(task.ROLLING_COMPARATORS)
    assert {
        row["comparator_id"] for row in rolling_60
    } == set(task.ROLLING_COMPARATORS)
    assert any(row["comparator_dominates_candidate"] == "true" for row in rolling_36)
    assert any(row["comparator_dominates_candidate"] == "true" for row in rolling_60)


def test_formation_diagnostics_use_only_sample_volatility_and_nine_sectors() -> None:
    diagnostics = [
        row
        for row in rows("formation_selection_diagnostics.csv")
        if row["record_type"] == "formation_sector"
        and row["signal_complete"] == "true"
    ]
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in diagnostics:
        grouped.setdefault(row["formation_date"], []).append(row)
    assert len(grouped) >= 24
    for formation_rows in grouped.values():
        assert len(formation_rows) == 9
        assert {int(row["volatility_rank"]) for row in formation_rows} == set(
            range(1, 10)
        )
        selected = [row for row in formation_rows if row["selected"] == "true"]
        assert len(selected) == 3
        assert {int(row["volatility_rank"]) for row in selected} == {1, 2, 3}
        assert all(row["sample_daily_volatility_ddof1"] for row in formation_rows)
    summaries = [
        row
        for row in rows("formation_selection_diagnostics.csv")
        if row["record_type"] == "sector_summary"
    ]
    assert len(summaries) == 9
    streaks = [
        int(row["maximum_consecutive_selection_count"]) for row in summaries
    ]
    assert all(value >= 0 for value in streaks)
    assert any(value > 0 for value in streaks)


def test_vintage_ledger_preserves_six_slots_and_natural_drift() -> None:
    ledger = rows("vintage_ledger.csv")
    assert ledger
    assert {int(row["slot_id"]) for row in ledger} == set(range(6))
    assert any(row["completed"] == "true" for row in ledger)
    assert any(row["completed"] == "false" for row in ledger)
    valid = [row for row in ledger if row["signal_complete"] == "true"]
    assert valid
    assert all(len(json.loads(row["selection"])) == 3 for row in valid)


def test_turnover_costs_and_all_invariants_reconcile() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == 36
    assert len(invariants) == 36
    for row in turnover:
        assert float(row["total_transaction_cost_drag"]) == pytest.approx(
            float(row["inner_sleeve_transaction_cost_drag"])
            + float(row["outer_transaction_cost_drag"])
        )
        assert row["transaction_costs_charged_once"] == "true"
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["natural_drift"] for row in invariants} == {"true"}
    assert {row["negative_weights_present"] for row in invariants} == {"false"}
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert {row["serial_rerun_deterministic"] for row in invariants} == {"true"}


def test_protected_state_parent_evidence_and_cache_remain_unchanged() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["overall_pass"] is True
    assert consistency["parent_reproduction_pass"] is True
    assert consistency["parent_MDD_closure_preserved"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["parent_evidence_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["result_driven_adaptation_explicit"] is True
    assert consistency["inverse_volatility_weighting_used"] is False
    assert consistency["parameter_variants_tested"] == 0
    assert consistency["provider_access"] is False
    assert consistency["network_access"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert consistency["paper_demo_observations_created"] == 0
    assert consistency["broker_orders"] == 0
    assert consistency["real_money_actions"] == 0
