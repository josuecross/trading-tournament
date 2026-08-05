from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import (
    audit_long_short_relative_value_capability_v1 as audit,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "data_capability"
    / "audit_long_short_relative_value_capability_v1"
    / "latest"
)


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_packet_and_entity_counts() -> None:
    assert {path.name for path in EVIDENCE.iterdir() if path.is_file()} == (
        audit.REQUIRED_OUTPUTS
    )
    manifest = yaml.safe_load(
        (EVIDENCE / "capability_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["source_library_context_records"] == 1
    assert manifest["data_capability_tasks"] == 1
    assert manifest["process_tasks"] == 1
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["experiment_trials_created"] == 0
    assert manifest["benchmark_strategies_created"] == 0
    assert manifest["synthetic_probes"] == 7
    assert rows("strategy_cards.csv") == []
    assert rows("trial_ledger.csv") == []


def test_basic_and_adverse_signed_pnl_are_exact() -> None:
    probes = audit.run_synthetic_probes()
    by_id = {row["probe_id"]: row for row in probes["results"]}
    favorable = by_id["probe_1_basic_dollar_neutral_pair"]
    adverse = by_id["probe_2_adverse_pair_move"]
    assert favorable["observed"] == pytest.approx(110.0)
    assert adverse["observed"] == pytest.approx(90.0)
    assert favorable["reference_probe_passed"] is True
    assert adverse["reference_probe_passed"] is True
    assert favorable["production_math_when_manually_injected_passed"] is True
    assert adverse["production_math_when_manually_injected_passed"] is True
    assert favorable["production_supported_entry_path"] is False
    assert adverse["production_supported_entry_path"] is False


def test_production_short_entry_and_bt_adapter_are_not_misclassified() -> None:
    core = audit.core_short_entry_probe()
    assert core["position_created"] is False
    assert core["negative_shares_created"] is False
    assert core["skip_reason"] == "not_enough_cash_or_notional_cap"
    matrix = {
        row["capability"]: row for row in rows("capability_matrix.csv")
    }
    assert matrix["negative_short_weights"]["classification"] == "unsupported"
    assert matrix["simultaneous_long_and_short"]["classification"] == (
        "unsupported"
    )
    support = {
        row["support_id"]: row for row in rows("existing_support_inventory.csv")
    }
    assert support["candidate_local_pair_ledger"]["classification"] == (
        "partially_supported"
    )


def test_signed_turnover_and_both_leg_costs() -> None:
    turnover = audit.turnover_probe_rows()
    expected = {
        "opening_both_legs": 0.5,
        "resizing_both_legs": 0.1,
        "closing_both_legs": 0.4,
        "reversing_pair_direction": 1.0,
        "opening_second_pair_first_remains": 0.25,
    }
    assert {row["scenario_id"] for row in turnover} == set(expected)
    for row in turnover:
        assert row["observed_one_way_turnover"] == pytest.approx(
            expected[row["scenario_id"]]
        )
        assert row["passed"] is True
        assert row["long_and_short_trades_costed"] is True
        assert row["transaction_cost"] == pytest.approx(
            row["gross_traded_weight"]
            * 100.0
            * row["cost_rate_per_absolute_traded_notional"]
        )


def test_borrow_financing_and_adjusted_distribution_contract() -> None:
    probes = audit.run_synthetic_probes()
    borrow = {
        row["scenario_id"]: row for row in probes["borrow"]
    }
    daily = borrow["single_short_daily_borrow"]
    assert daily["daily_borrow_cost"] == pytest.approx(50.0 * 0.05 / 252.0)
    assert daily["passed"] is True
    assert daily["production_engine_support"] is False
    assert borrow["unavailable_to_borrow"]["passed"] is False
    assert borrow["collateral_yield_and_debit_financing"]["passed"] is False

    corporate = probes["corporate_actions"]
    assert all(row["passed"] for row in corporate)
    distribution = next(
        row
        for row in corporate
        if row["scenario_id"] == "distribution_embedded_in_adjusted_return"
    )
    assert distribution["long_leg_pnl"] > 0.0
    assert distribution["short_leg_pnl"] < 0.0
    assert distribution["long_leg_pnl"] == pytest.approx(
        -distribution["short_leg_pnl"]
    )
    assert distribution["explicit_dividend_cash_flow_added"] is False
    assert distribution["double_count_avoided"] is True


def test_multiple_pairs_and_missing_leg_protection_reference_contract() -> None:
    probes = audit.run_synthetic_probes()
    by_id = {row["probe_id"]: row for row in probes["results"]}
    assert by_id["probe_6_multiple_pairs"]["reference_probe_passed"] is True
    assert by_id["probe_6_multiple_pairs"]["observed"] == "C|D"
    assert by_id["probe_7_missing_short_leg_data"][
        "reference_probe_passed"
    ] is True
    for row in probes["missing_leg"]:
        assert row["passed"] is True
        assert row["one_legged_exposure_created"] is False
        assert row["price_forward_filled"] is False
    matrix = {
        row["capability"]: row for row in rows("capability_matrix.csv")
    }
    assert matrix["missing_leg_determinism"]["classification"] == "unsupported"
    assert matrix["simultaneous_pair_entry_and_exit"]["classification"] == (
        "unsupported"
    )


def test_data_universe_does_not_claim_etfs_are_source_equivalent() -> None:
    data = {row["universe_id"]: row for row in rows("data_universe_assessment.csv")}
    cache = data["canonical_adjusted_cache_all_etfs"]
    frozen = data["pre_frozen_liquid_primary_etf_universe"]
    stock = data["source_aligned_point_in_time_liquid_stock_universe"]
    prior_etf = data["prior_candidate_local_sector_etf_pairs_universe"]
    assert int(cache["symbol_count"]) >= 73
    assert int(cache["available_symbol_count"]) == int(cache["symbol_count"])
    assert int(frozen["symbol_count"]) == 47
    assert int(frozen["available_symbol_count"]) == (
        int(frozen["symbol_count"]) - len(frozen["missing_symbols"].split("|"))
    )
    assert int(stock["symbol_count"]) == 0
    assert int(stock["available_symbol_count"]) == 0
    assert stock["adjusted_daily_ohlcv_ready"] == "false"
    assert stock["point_in_time_membership"] == "false"
    assert stock["delisting_return_support"] == "false"
    assert prior_etf["source_fidelity"] == (
        "ETF_portability_not_Gatev_stock_source_equivalent"
    )


def test_outcome_and_next_action_are_exact() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] == "long_short_capability_not_currently_viable"
    assert outcome["remaining_work_classification"] == (
        "material_capability_project"
    )
    assert outcome["primary_failure_reason"] == "capability_missing"
    assert outcome["generic_production_short_entry_supported"] == "false"
    assert outcome["source_aligned_stock_universe_ready"] == "false"
    assert outcome["candidate_local_pair_ledger_exists"] == "true"
    assert outcome["candidate_local_ledger_is_core"] == "false"
    assert outcome["exact_next_action"] == (
        "defer_long_short_lane_and_refresh_strategy_source_library_v6"
    )
    assert outcome["next_action_executed"] == "false"


def test_capability_classifications_and_gap_scope_are_controlled() -> None:
    matrix = rows("capability_matrix.csv")
    assert matrix
    assert {
        row["classification"] for row in matrix
    } <= audit.CLASSIFICATIONS
    assert any(row["classification"] == "supported_and_verified" for row in matrix)
    assert any(row["classification"] == "partially_supported" for row in matrix)
    assert any(row["classification"] == "unsupported" for row in matrix)
    gaps = rows("gap_and_minimal_patch_scope.csv")
    required = [row for row in gaps if row["required_before_lane"] == "true"]
    assert required
    assert all(row["bounded_single_patch"] == "false" for row in required)
    assert {
        row["scope_judgment"] for row in required
    } >= {"architectural", "material_data_project"}


def test_protected_state_prior_evidence_and_forbidden_actions() -> None:
    check = payload("consistency_check.json")
    assert check["status"] == "pass"
    assert check["consistency_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["strategy_configurations_created"] == 0
    assert check["experiment_trials_created"] == 0
    assert check["paper_demo_observations_created_or_changed"] == 0
    assert check["production_code_patch"] is False
    assert check["strategy_backtest"] is False
    assert check["data_acquisition"] is False
    assert check["registry_or_lifecycle_change"] is False
    assert check["broker_account_order_or_real_money_action"] is False
    assert all(row["changed"] == "false" for row in rows("state_change_manifest.csv"))


def test_probe_generation_is_deterministic_in_memory() -> None:
    first = audit.run_synthetic_probes()
    second = audit.run_synthetic_probes()
    assert first == second
