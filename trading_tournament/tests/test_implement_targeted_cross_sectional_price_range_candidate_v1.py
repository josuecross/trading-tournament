from __future__ import annotations

import csv
import json

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    implement_targeted_cross_sectional_price_range_candidate_v1 as task,
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


def test_preregistration_freezes_low_only_trial_and_translations() -> None:
    source = rows("source_library_records.csv")
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    consistency = json_payload("consistency_check.json")
    assert len(source) == len(strategy) == len(trial) == 1
    assert source[0]["source_record_id"] == task.SOURCE_RECORD_ID
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == ""
    assert trial[0]["adaptation_label"] == ""
    assert trial[0]["source_rule_changed"] == "false"
    assert trial[0]["stock_to_sector_translation"] == "true"
    assert trial[0]["bottom_10pct_to_one_of_nine_translation"] == "true"
    assert trial[0]["optimization_performed"] == "false"
    assert consistency["preregistration_written_before_performance_calculation"]
    assert consistency["LOW_only_candidate_score_preserved"]
    assert not consistency[
        "HIGH_momentum_volatility_or_drawdown_in_candidate_score"
    ]


def test_low_score_uses_close_and_trailing_minimum_only() -> None:
    index = pd.bdate_range("2019-01-02", "2020-01-31")
    prices = pd.DataFrame(
        {
            symbol: 100.0 + pd.Series(range(len(index)), index=index) * 0.01
            for symbol in task.SECTORS
        },
        index=index,
    )
    prices["XLB"] = 100.0
    prices.loc[index[-1], "XLB"] = 110.0
    result = task.formation_inputs(prices, index, index[-1])
    assert result is not None
    assert result["low_score"]["XLB"] == pytest.approx(1.1)
    assert result["trailing_minimum"]["XLB"] == pytest.approx(100.0)
    assert result["current_close"]["XLB"] == pytest.approx(110.0)


def test_rank_ties_resolve_lexically() -> None:
    ranks = task.rank_values({"XLY": 1.1, "XLB": 1.0, "XLE": 1.0}, True)
    assert ranks == {"XLB": 1, "XLE": 2, "XLY": 3}


def test_preflight_uses_exact_cache_without_provider_or_reduction() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == set(task.REQUIRED_SYMBOLS)
    assert {row["candidate_preflight_status"] for row in preflight} == {"pass"}
    assert {row["ordered_unique_dates"] for row in preflight} == {"true"}
    assert {row["finite_positive_adjusted_prices"] for row in preflight} == {
        "true"
    }
    assert {row["valid_adjusted_ohlc_relationships"] for row in preflight} == {
        "true"
    }
    assert {row["missing_common_session_count"] for row in preflight} == {"0"}
    assert {row["provider_access_allowed"] for row in preflight} == {"false"}
    assert {row["universe_reduction_allowed"] for row in preflight} == {
        "false"
    }


def test_every_valid_formation_ranks_nine_and_selects_one() -> None:
    diagnostics = rows("formation_signal_diagnostics.csv")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in diagnostics:
        grouped.setdefault(row["formation_date"], []).append(row)
    valid = [
        formation_rows
        for formation_rows in grouped.values()
        if formation_rows[0]["signal_complete"] == "true"
    ]
    assert len(valid) >= 48
    for formation_rows in valid:
        assert len(formation_rows) == 9
        assert {int(row["LOW_rank"]) for row in formation_rows} == set(
            range(1, 10)
        )
        selected = [
            row for row in formation_rows if row["selected_by_candidate"] == "true"
        ]
        assert len(selected) == 1
        assert selected[0]["LOW_rank"] == "1"
        assert pd.Timestamp(formation_rows[0]["formation_date"]) < pd.Timestamp(
            formation_rows[0]["execution_date"]
        )


def test_monthly_ledger_preserves_bil_warmup_and_no_stale_fill() -> None:
    ledger = rows("monthly_selection_ledger.csv")
    assert ledger
    assert ledger[0]["target_holding"] == "BIL"
    assert any(row["signal_complete"] == "true" for row in ledger)
    assert {row["same_session_signal_return_used"] for row in ledger} == {
        "false"
    }
    assert {
        row["stale_execution_price_forward_fill_used"] for row in ledger
    } == {"false"}


def test_results_controls_costs_halves_and_portfolios_are_complete() -> None:
    candidate = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    portfolios = rows("portfolio_contribution_results.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(candidate) == 3
    assert len(controls) == 18
    assert len(halves) == 14
    assert len(portfolios) == 15
    assert {row["benchmark_id"] for row in benchmarks} == set(task.CONTROL_IDS)
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_validation_or_sealed_holdout"
    }
    assert {row["daily_fixed_weight_return_blend_used"] for row in portfolios} == {
        "false"
    }
    for row in portfolios:
        assert float(row["transaction_cost_drag"]) == pytest.approx(
            float(row["inner_sleeve_transaction_cost_drag"])
            + float(row["outer_transaction_cost_drag"])
        )


def test_critical_controls_are_fixed_and_half_formations_are_sufficient() -> None:
    benchmarks = rows("benchmark_reference_log.csv")
    critical = {
        row["benchmark_id"] for row in benchmarks if row["critical_control"] == "true"
    }
    assert critical == set(task.CRITICAL_CONTROL_IDS)
    halves = [
        row
        for row in rows("chronological_half_results.csv")
        if row["row_id"] == task.STRATEGY_ID
    ]
    assert len(halves) == 2
    assert all(int(row["monthly_formation_count"]) >= 24 for row in halves)


def test_all_accounting_invariants_and_determinism_pass() -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 36
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["no_same_session_signal_return"] for row in invariants} == {
        "true"
    }
    assert {row["stale_execution_price_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert {row["transaction_costs_charged_once"] for row in invariants} == {
        "true"
    }
    assert {row["serial_rerun_deterministic"] for row in invariants} == {
        "true"
    }


def test_outcome_and_next_action_are_from_frozen_enums() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_standalone",
        "exploratory_followup_candidate_diversifier",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    expected = {
        "exploratory_followup_candidate_standalone": task.NEXT_ADVANCE,
        "closed_exploration": task.NEXT_CLOSE,
        "inconclusive_data_issue": task.NEXT_BLOCK,
        "blocked_feasibility": task.NEXT_BLOCK,
    }
    assert outcome["exact_next_action"] == expected[outcome["outcome"]]
    assert outcome["validation_claimed"] == "false"
    assert outcome["paper_demo_eligible"] == "false"


def test_protected_state_cache_and_prior_evidence_are_unchanged() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["closed_52week_high_strategy_reopened"] is False
    assert consistency["closed_low_volatility_adaptation_reopened"] is False
    assert consistency["provider_access"] is False
    assert consistency["network_access"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert consistency["paper_demo_observations_created"] == 0
    assert consistency["broker_orders"] == 0
    assert consistency["real_money_actions"] == 0
