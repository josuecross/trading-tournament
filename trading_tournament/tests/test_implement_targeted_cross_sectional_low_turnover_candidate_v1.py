from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    implement_targeted_cross_sectional_low_turnover_candidate_v1 as task,
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


def test_preregistration_freezes_mdd_only_canonical_trial() -> None:
    source = rows("source_library_records.csv")
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    consistency = json_payload("consistency_check.json")
    assert len(source) == len(strategy) == len(trial) == 1
    assert source[0]["source_record_id"] == task.SOURCE_RECORD_ID
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == ""
    assert trial[0]["adaptation_label"] == ""
    assert trial[0]["selected_criterion"] == "MDD_only"
    assert trial[0]["composite_criterion_tested"] == "false"
    assert trial[0]["optimization_performed"] == "false"
    assert consistency["preregistration_written_before_performance_calculation"]
    assert consistency["MDD_only_criterion_preserved"]
    assert consistency["parameter_variants_tested"] == 0


def test_maximum_log_drawdown_uses_peak_before_subsequent_trough() -> None:
    values = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0])
    expected = np.log(120.0) - np.log(80.0)
    assert task.maximum_log_drawdown(values) == pytest.approx(expected)
    assert task.maximum_log_drawdown(
        pd.Series([100.0, 101.0, 102.0])
    ) == pytest.approx(0.0)


def test_rank_ties_resolve_lexically() -> None:
    values = {"XLY": 0.2, "XLB": 0.1, "XLE": 0.1}
    ranks = task.rank_values(values, ascending=True)
    assert ranks == {"XLB": 1, "XLE": 2, "XLY": 3}


def test_preflight_uses_exact_cache_without_provider_or_universe_reduction() -> None:
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
    assert {row["canonical_adjustment_compatible"] for row in preflight} == {
        "true"
    }
    assert {row["missing_common_session_count"] for row in preflight} == {"0"}
    assert {row["provider_accessed"] for row in preflight} == {"false"}
    assert {row["network_accessed"] for row in preflight} == {"false"}


def test_every_valid_formation_ranks_nine_and_selects_three() -> None:
    diagnostics = rows("formation_selection_diagnostics.csv")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in diagnostics:
        grouped.setdefault(row["formation_date"], []).append(row)
    valid = [
        formation_rows
        for formation_rows in grouped.values()
        if formation_rows[0]["signal_complete"] == "true"
    ]
    assert len(valid) >= 24
    for formation_rows in valid:
        assert len(formation_rows) == 9
        assert {int(row["mdd_rank"]) for row in formation_rows} == set(
            range(1, 10)
        )
        selected = [
            row for row in formation_rows if row["selected_by_candidate"] == "true"
        ]
        assert len(selected) == 3
        assert {int(row["mdd_rank"]) for row in selected} == {1, 2, 3}
        assert pd.Timestamp(formation_rows[0]["formation_date"]) < pd.Timestamp(
            formation_rows[0]["execution_date"]
        )


def test_synthetic_vintage_probe_trades_only_replaced_slot() -> None:
    index = pd.bdate_range("2020-01-02", periods=8)
    symbols = task.REQUIRED_SYMBOLS
    prices = pd.DataFrame(100.0, index=index, columns=symbols)
    prices["XLB"] = 100.0 * np.cumprod(np.full(len(index), 1.01))
    formation = task.Formation(
        sequence=0,
        formation_date=index[1],
        execution_date=index[2],
        expiration_date=None,
        window_start=index[0],
        window_end=index[1],
        complete=True,
        mdd={symbol: 0.0 for symbol in task.SECTORS},
        cumulative_log_return={symbol: 0.0 for symbol in task.SECTORS},
        realized_volatility={symbol: 0.0 for symbol in task.SECTORS},
        mdd_ranks={symbol: pos + 1 for pos, symbol in enumerate(task.SECTORS)},
        cumulative_ranks={
            symbol: pos + 1 for pos, symbol in enumerate(task.SECTORS)
        },
        volatility_ranks={
            symbol: pos + 1 for pos, symbol in enumerate(task.SECTORS)
        },
        candidate_selection=("XLB", "XLE", "XLF"),
        cumulative_selection=("XLB", "XLE", "XLF"),
        volatility_selection=("XLB", "XLE", "XLF"),
        missing_symbols=(),
    )
    path = task.simulate_vintage_path(
        prices,
        [formation],
        "candidate_selection",
        "synthetic",
        5.0,
    )
    event = path["events"][0]
    assert event["slot_id"] == 0
    assert event["portfolio_one_way_turnover"] <= 1.0 / 6.0 + 1e-12
    assert event["same_session_signal_return_used"] is False
    assert event["stale_execution_price_forward_fill_used"] is False
    post = path["held_weights"].loc[index[2]]
    assert post["BIL"] > 0.8
    assert post["XLB"] > 0.0
    assert path["held_weights"].loc[index[-1], "XLB"] > post["XLB"]


def test_vintage_ledger_preserves_six_slot_rotation_and_open_rows() -> None:
    ledger = [
        row
        for row in rows("vintage_ledger.csv")
        if row["path_id"] == task.STRATEGY_ID
    ]
    assert ledger
    assert {int(row["slot_id"]) for row in ledger} == set(range(6))
    formed = [row for row in ledger if row["formation_date"]]
    assert formed
    assert all(
        row["selection"] == '["BIL"]'
        or len(json.loads(row["selection"])) == 3
        or row["invalid_vintage_held_in_BIL"] == "true"
        for row in formed
    )
    assert any(row["completed"] == "false" for row in ledger)


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


def test_exposure_control_is_mechanical_and_not_optimized() -> None:
    exposure = rows("exposure_control_reconciliation.csv")
    assert len(exposure) == 3
    assert {row["matches_candidate_target_exposure"] for row in exposure} == {
        "true"
    }
    assert {row["optimized_or_rounded"] for row in exposure} == {"false"}
    assert {row["performance_selected"] for row in exposure} == {"false"}
    weights = {float(row["exposure_control_SPY_weight"]) for row in exposure}
    assert len(weights) == 1
    assert 0.0 <= next(iter(weights)) <= 1.0


def test_all_accounting_invariants_and_determinism_pass() -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 36
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["natural_drift_within_vintage"] for row in invariants} == {
        "true"
    }
    assert {
        row["existing_vintages_rebalanced_to_equal_weight"]
        for row in invariants
    } == {"false"}
    assert {row["same_session_signal_return_used"] for row in invariants} == {
        "false"
    }
    assert {
        row["stale_execution_price_forward_fill_used"] for row in invariants
    } == {"false"}
    assert {row["transaction_costs_charged_once"] for row in invariants} == {
        "true"
    }
    assert {row["serial_rerun_deterministic"] for row in invariants} == {
        "true"
    }


def test_outcome_is_closed_by_low_volatility_control_without_adaptation() -> None:
    outcome = rows("outcome_summary.csv")[0]
    candidate = next(
        row
        for row in rows("all_trial_results.csv")
        if row["cost_assumption_bps"] == "5"
    )
    low_vol = next(
        row
        for row in rows("control_results.csv")
        if row["cost_assumption_bps"] == "5"
        and row["row_id"]
        == "six_month_realized_volatility_bottom3_sector_v1"
    )
    assert outcome["outcome"] == "closed_exploration"
    assert outcome["failure_reason"] == "low_volatility_control_explanation"
    assert float(low_vol["cagr"]) >= float(candidate["cagr"])
    assert float(low_vol["sharpe_ratio"]) >= float(candidate["sharpe_ratio"])
    assert float(low_vol["maximum_drawdown"]) >= float(
        candidate["maximum_drawdown"]
    )
    assert outcome["exact_next_action"] == task.NEXT_CLOSE


def test_protected_state_prior_evidence_and_cache_are_unchanged() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["existing_choi_recovery_strategy_rerun"] is False
    assert consistency["provider_access"] is False
    assert consistency["network_access"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert consistency["paper_demo_observations_created"] == 0
    assert consistency["broker_orders"] == 0
    assert consistency["real_money_actions"] == 0
