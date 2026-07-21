from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from run_trade_management_rebalance_band_robustness_v1 import (
    classify_combination,
    cost_path_decomposition,
    economic_family_mapping,
    prior_status_corrections,
    requested_periods,
    result_key,
)


def test_requested_periods_are_chronological_and_not_replaced() -> None:
    periods = requested_periods("2007-05-30", "2026-06-18")
    by_id = {row["period_id"]: row for row in periods}

    assert by_id["PRE_ORIGINAL_WINDOW"]["requested_start"] == "2007-05-30"
    assert by_id["PRE_ORIGINAL_WINDOW"]["requested_end"] == "2017-12-31"
    assert by_id["ORIGINAL_EXPLORATORY_WINDOW"]["requested_start"] == "2017-01-01"
    assert by_id["ORIGINAL_EXPLORATORY_WINDOW"]["requested_end"] == "2020-12-31"
    assert by_id["POST_ORIGINAL_WINDOW"]["requested_start"] == "2021-01-01"
    assert by_id["POST_ORIGINAL_WINDOW"]["requested_end"] == "2026-06-18"
    assert by_id["FULL_AVAILABLE_RANGE"]["chronological_role"] == "full_available_not_independent"


def test_economic_family_mapping_groups_n1_n3_without_counting_independent_confirmations() -> None:
    mapping = economic_family_mapping().set_index("strategy_id")

    assert mapping.loc["N1_dual_momentum_taa", "economic_family_id"] == "dual_momentum_taa"
    assert mapping.loc["N3_dual_momentum_vol_scaled", "economic_family_id"] == "dual_momentum_taa"
    assert not bool(mapping.loc["N1_dual_momentum_taa", "independent_economic_family_confirmation_unit"])
    assert not bool(mapping.loc["N3_dual_momentum_vol_scaled", "independent_economic_family_confirmation_unit"])


def test_prior_status_corrections_are_exact_combination_scoped() -> None:
    corrections = prior_status_corrections().set_index(["strategy_id", "overlay_id"])

    n4 = corrections.loc[("N4_inverse_vol_defensive_allocation", "OVL-ORD-001")]
    assert n4["corrected_status"] == "EXACT_COMBINATION_CANDIDATE_FOR_ROBUSTNESS"
    assert n4["scope"] == "exact_strategy_overlay_combination_only"

    c = corrections.loc[("C_swing_trend_pullback", "OVL-EXT-001")]
    assert c["corrected_status"] == "MIXED_NO_MATERIAL_EDGE_WINNER_TRUNCATION"
    assert c["scope"] == "exact_strategy_overlay_combination_closed_only"
    assert c["do_not_infer"] == "time_stop_overlay_family_closed"


def test_zero_cost_decomposition_forces_direct_cost_component_to_zero() -> None:
    metrics = pd.DataFrame(
        [
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "period_id": "PRE_ORIGINAL_WINDOW",
                "trial_name": "base",
                "slippage_bps_per_side": 0.0,
                "corrected_modeled_transaction_cost": 10.0,
                "total_return": 0.10,
                "annualized_return": 0.05,
                "max_drawdown_pct": -0.10,
                "average_gross_exposure": 0.50,
                "average_cash_weight": 0.50,
                "turnover": 2.0,
            },
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "period_id": "PRE_ORIGINAL_WINDOW",
                "trial_name": "rebalance_band",
                "slippage_bps_per_side": 0.0,
                "corrected_modeled_transaction_cost": 5.0,
                "total_return": 0.12,
                "annualized_return": 0.06,
                "max_drawdown_pct": -0.09,
                "average_gross_exposure": 0.55,
                "average_cash_weight": 0.45,
                "turnover": 1.5,
            },
        ]
    )
    audit = pd.DataFrame(columns=["strategy_id", "period_id", "cost_assumption_bps_per_side"])
    ranges = pd.DataFrame(
        [
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "period_id": "PRE_ORIGINAL_WINDOW",
                "availability_status": "available",
                "effective_start": "2008-05-29",
            }
        ]
    )
    result = SimpleNamespace(
        equity_curve=pd.DataFrame({"gross_exposure": [0.0, 0.5, 0.6]}),
        trades=pd.DataFrame(columns=["entry_date", "exit_date", "symbol"]),
    )
    decomp = cost_path_decomposition(
        metrics=metrics,
        audit=audit,
        results={
            result_key("N4_inverse_vol_defensive_allocation", "PRE_ORIGINAL_WINDOW", "base", 0.0): result,
            result_key("N4_inverse_vol_defensive_allocation", "PRE_ORIGINAL_WINDOW", "rebalance_band", 0.0): result,
        },
        range_coverage=ranges,
        config={"project": {"starting_equity": 3000.0}},
    )

    row = decomp.iloc[0]
    assert row["modeled_transaction_cost_avoided"] == 5.0
    assert row["direct_cost_return_component"] == 0.0
    assert row["residual_path_return_difference"] == row["total_return_difference"]
    assert row["zero_cost_difference_component_rule"] == "cost_component_forced_zero"


def test_classification_requires_two_active_independent_periods() -> None:
    decomp = pd.DataFrame(
        [
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "period_id": "PRE_ORIGINAL_WINDOW",
                "suppressed_decision_count": 2,
                "total_return_difference": 0.01,
                "turnover_change": -0.2,
                "drawdown_difference": 0.01,
                "direct_cost_return_component": 0.0,
                "residual_path_return_difference": 0.01,
                "continuous_stop_or_trailing_state_positions": 1,
                "average_gross_exposure_change": 0.02,
                "cost_assumption_bps_per_side": 0.0,
            },
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "period_id": "ORIGINAL_EXPLORATORY_WINDOW",
                "suppressed_decision_count": 0,
                "total_return_difference": 0.0,
                "turnover_change": 0.0,
                "drawdown_difference": 0.0,
                "direct_cost_return_component": 0.0,
                "residual_path_return_difference": 0.0,
                "continuous_stop_or_trailing_state_positions": 0,
                "average_gross_exposure_change": 0.0,
                "cost_assumption_bps_per_side": 0.0,
            },
        ]
    )

    labels = classify_combination(decomp)["N4_inverse_vol_defensive_allocation"]["exact_combination_classification"]
    assert "INSUFFICIENT_ACTIVITY" in labels
