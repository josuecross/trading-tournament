from __future__ import annotations

from pathlib import Path

import yaml

from run_strategy_lab import (
    DEFAULT_REGISTRY,
    REQUIRED_EVIDENCE_FILES,
    REQUIRED_FIELDS,
    export_evidence,
    load_registry,
    validate_registry_data,
)


def test_registry_yaml_exists_and_loads() -> None:
    assert DEFAULT_REGISTRY.exists()
    data = load_registry(DEFAULT_REGISTRY)
    assert "registry" in data
    assert "strategies" in data


def test_required_top_level_metadata_exists() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    meta = data["registry"]
    for field in ["schema_version", "project", "research_only", "real_money_recommendation", "broker_integration", "live_orders"]:
        assert field in meta
    assert meta["research_only"] is True
    assert meta["real_money_recommendation"] is False
    assert data["risk_framework"]["active_framework"] == "balanced_speculative_research_v1"
    assert data["risk_framework"]["framework_path"] == "risk_framework/risk_framework.yaml"


def test_all_entries_have_required_fields() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    for row in data["strategies"]:
        for field in REQUIRED_FIELDS:
            assert field in row, row.get("id")


def test_no_duplicate_id_version() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    keys = [(row["id"], row["version"]) for row in data["strategies"]]
    assert len(keys) == len(set(keys))


def test_paper_forward_rows_are_frozen_and_observe_or_compare_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    rows = [row for row in data["strategies"] if row["paper_forward_active"]]
    assert rows
    for row in rows:
        assert row["rules_frozen"] is True
        assert row["allowed_next_action"] in {"observe_only", "compare_only", "run_monthly_paper_forward_checkpoint"}
        assert row["paper_forward_allowed_by_risk_framework"] is True


def test_crypto_rows_are_tier1_and_not_practical_candidate() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    rows = [row for row in data["strategies"] if row["lane"] == "crypto_exploratory"]
    assert rows
    for row in rows:
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["paper_forward_active"] is False
        assert row.get("paper_forward_allowed_by_risk_framework", False) is not True
        assert row["status"] != "practical_candidate"


def test_leverage_rows_are_too_risky_or_exploratory_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    rows = [row for row in data["strategies"] if "leverage" in row["id"]]
    assert rows
    for row in rows:
        assert row["status"] in {"too_risky", "exploratory_only"}
        assert row["paper_forward_active"] is False


def test_etf_leverage_diagnostic_rows_are_tier1_and_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "SPY_200d_trend_model_sim_1_25x_v1",
        "SPY_200d_trend_model_sim_1_5x_v1",
        "SPY_buy_hold_sim_1_25x_v1",
        "SPY_buy_hold_sim_1_5x_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "compact_challenge"
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["role"] == "simulated_leverage_diagnostic"
        assert row["paper_forward_active"] is False
        assert row.get("paper_forward_allowed_by_risk_framework", False) is not True
        assert row["status"] != "practical_candidate"
        assert "observe_as_paper_forward" in row["forbidden_next_actions"]


def test_etf_exposure_frontier_rows_are_tier1_and_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "SPY_200d_exposure_frontier_1_05x_v1",
        "SPY_200d_exposure_frontier_1_10x_v1",
        "SPY_200d_exposure_frontier_1_15x_v1",
        "SPY_200d_exposure_frontier_1_20x_v1",
        "SPY_200d_exposure_frontier_1_25x_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "compact_challenge"
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["role"] == "risk_budget_diagnostic"
        assert row["paper_forward_active"] is False
        assert row.get("paper_forward_allowed_by_risk_framework", False) is not True
        assert row["status"] != "practical_candidate"
        assert "tune_exposure_multiplier" in row["forbidden_next_actions"]


def test_etf_volatility_control_rows_are_tier1_and_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "SPY_200d_vol_target_12_cap_1_00_v1",
        "SPY_200d_vol_target_12_cap_1_10_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "compact_challenge"
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["role"] == "risk_control_diagnostic"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row["status"] != "practical_candidate"
        assert "tune_target_vol" in row["forbidden_next_actions"]
        assert "tune_vol_window" in row["forbidden_next_actions"]


def test_diversified_portfolio_rows_validate_and_are_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "portfolio_spy200d_100_v1",
        "portfolio_spy200d_80_bil_20_v1",
        "portfolio_spy200d_70_bil_30_v1",
        "portfolio_spy200d_60_ief_20_bil_20_v1",
        "portfolio_spy200d_70_gld_15_bil_15_v1",
        "portfolio_spy200d_60_ief_20_gld_10_bil_10_v1",
        "portfolio_spy200d_80_ab_20_v1",
        "portfolio_spy200d_70_ab_20_bil_10_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "compact_challenge"
        assert row["role"] == "diversified_portfolio_diagnostic"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        assert "tune_weights" in row["forbidden_next_actions"]


def test_crypto_portfolio_rows_are_tier1_and_not_practical_candidate() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "portfolio_spy200d_80_crypto_tsmom_10_bil_10_v1",
        "portfolio_spy200d_70_crypto_tsmom_10_ief_10_bil_10_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["status"] != "practical_candidate"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False


def test_independent_family_rows_validate_and_are_not_real_money_recommendations() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "family_broad_etf_spy200d_v1",
        "family_broad_etf_spy_buy_hold_v1",
        "family_cash_treasury_bil_v1",
        "family_bond_treasury_ief_v1",
        "family_gold_gld_v1",
        "family_etf_sector_momentum_A_v1",
        "family_etf_ab_no_cash_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "compact_challenge"
        assert row["role"] == "independent_family_diagnostic"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        assert "treat_as_portfolio_allocation" in row["forbidden_next_actions"]


def test_crypto_family_rows_remain_tier1() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "family_crypto_spot_time_series_momentum_v1",
        "family_crypto_spot_buy_hold_equal_weight_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["credibility_tier"] == "tier1_exploratory"
        assert row["status"] != "practical_candidate"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False


def test_crypto_tier2_risk_control_rows_are_exploratory_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "crypto_spot_tsmom_top1_cash_filter_v1",
        "crypto_spot_equal_weight_200d_filter_v1",
        "combo_plus_crypto_spot_tsmom_90_10_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "profit_exploration"
        assert row["credibility_tier"] == "tier2_exploratory"
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert "use_perpetuals" in row["forbidden_next_actions"]
        assert "use_margin" in row["forbidden_next_actions"]
        assert "use_leverage" in row["forbidden_next_actions"]
        assert "place_live_orders" in row["forbidden_next_actions"]


def test_global_multi_asset_rows_are_exploratory_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "global_multi_asset_tsmom_top2_v1",
        "global_multi_asset_tsmom_top2_defensive_50_v1",
        "combo_plus_global_multi_asset_80_20_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    statuses = {row["id"]: row["status"] for row in rows}
    assert statuses["global_multi_asset_tsmom_top2_v1"] == "research_sample_candidate_risk_budget_breach"
    assert statuses["global_multi_asset_tsmom_top2_defensive_50_v1"] == "watchlist"
    assert statuses["combo_plus_global_multi_asset_80_20_v1"] == "watchlist"
    for row in rows:
        assert row["lane"] == "profit_exploration"
        assert row["credibility_tier"] == "tier1_or_tier2_exploratory"
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        assert row["allowed_next_action"] == "research_sample_review"
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert "use_margin" in row["forbidden_next_actions"]
        assert "use_leverage" in row["forbidden_next_actions"]
        assert "place_live_orders" in row["forbidden_next_actions"]
        assert "promote_to_real_money" in row["forbidden_next_actions"]
    combo = next(row for row in rows if row["id"] == "combo_plus_global_multi_asset_80_20_v1")
    assert "change_active_combo_rules" in combo["forbidden_next_actions"]
    assert "replace_spy200d" in combo["forbidden_next_actions"]


def test_blocked_family_rows_remain_blocked_by_gate() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    rows = [row for row in data["strategies"] if row["id"].startswith("family_") and row["role"] == "blocked_research_family"]
    assert rows
    for row in rows:
        assert row["credibility_tier"] == "blocked"
        assert row["implementation_status"] == "blocked_by_gate"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert "run_backtest" in row["forbidden_next_actions"]


def test_profit_exploration_rows_validate_and_are_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "profit_GLD_200d_trend_model_v1",
        "profit_IEF_200d_trend_model_v1",
        "profit_SPY_GLD_dual_momentum_v1",
        "profit_SPY_GLD_IEF_dual_momentum_v1",
        "profit_multi_asset_top2_momentum_v1",
        "profit_GLD_SPY_rotation_v1",
        "profit_combo_SPY200d_GLD_50_50_v1",
        "profit_combo_SPY200d_GLD_BIL_60_30_10_v1",
        "profit_combo_SPY200d_crypto_tsmom_90_10_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "profit_exploration"
        assert row.get("real_money_recommendation", False) is not True
        assert "promote_to_real_money" in row["forbidden_next_actions"]
        if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1":
            assert row["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
            if row["status"] == "active_paper_demo_observation":
                assert row["paper_forward_active"] is True
                assert row["paper_forward_allowed_by_risk_framework"] is True
                assert row["allowed_next_action"] == "run_monthly_paper_forward_checkpoint"
            else:
                assert row["paper_forward_active"] is False
                assert row["paper_forward_allowed_by_risk_framework"] is False
                assert row["allowed_next_action"] == "controlled_cache_update_or_next_cached_observation_date"
            assert row["implementation_status"] == "implemented_research_candidate"
            assert "replace_spy200d_without_governance" in row["forbidden_next_actions"]
            assert "observe_as_paper_forward_without_observation_plan" in row["forbidden_next_actions"]
            assert "change_paper_forward_rules" in row["forbidden_next_actions"]
            assert "fabricate_missing_data" in row["forbidden_next_actions"]
        else:
            assert row["paper_forward_active"] is False
            assert row["paper_forward_allowed_by_risk_framework"] is False
            assert row["allowed_next_action"] == "run_profit_exploration"
            assert "modify_paper_forward_rules" in row["forbidden_next_actions"]
    crypto = next(row for row in rows if row["id"] == "profit_combo_SPY200d_crypto_tsmom_90_10_v1")
    assert crypto["credibility_tier"] == "tier1_exploratory"
    assert crypto["status"] != "practical_candidate"


def test_new_profit_asset_class_rows_validate_and_are_not_paper_forward() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    ids = {
        "asset_class_tsmom_equal_weight_v1",
        "asset_class_tsmom_top1_v1",
        "asset_class_tsmom_top2_v1",
        "qqq_spy_gld_ief_dual_momentum_v1",
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
        "managed_futures_proxy_etf_trend_v1",
        "dual_momentum_SPY_GLD_IEF_v1",
        "GLD_200d_trend_model_v1",
    }
    rows = [row for row in data["strategies"] if row["id"] in ids]
    assert {row["id"] for row in rows} == ids
    for row in rows:
        assert row["lane"] == "profit_exploration"
        assert row["role"] == "profit_exploration_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        assert "observe_as_paper_forward" in row["forbidden_next_actions"]
        assert "promote_to_real_money" in row["forbidden_next_actions"]
        assert "change_paper_forward_rules" in row["forbidden_next_actions"]
        if row["id"] in {"qqq_spy_gld_ief_dual_momentum_v1", "value_momentum_factor_etf_rotation_v1", "sector_top2_momentum_simple_v1", "managed_futures_proxy_etf_trend_v1"}:
            assert row["implementation_status"] == "implemented_research_sample"
            assert row["status"] in {
                "research_sample_candidate",
                "watchlist",
                "candidate_exhaustive_queue",
                "candidate_exhaustive_queue_short_history_labeled",
                "duplicate_or_near_duplicate",
                "too_slow",
                "high_upside_high_risk",
                "too_risky",
                "reject_proxy_not_useful",
            }
            assert row["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review", "candidate_exhaustive_review_short_history_gate"}
    duplicate = next(row for row in rows if row["id"] == "dual_momentum_SPY_GLD_IEF_v1")
    assert duplicate["status"] == "duplicate_skipped"
    assert duplicate["implementation_status"] == "duplicate_skipped"
    assert duplicate["parent_id"] == "asset_class_tsmom_top1_v1"


def test_stock_momentum_row_is_deferred_and_blocked_by_gate() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    row = next(row for row in data["strategies"] if row["id"] == "individual_stock_momentum_gate1a")
    assert row["status"] in {"deferred", "blocked"}
    assert row["implementation_status"] == "blocked_by_gate"
    assert row["allowed_next_action"] == "continue_vendor_review"
    assert row.get("paper_forward_allowed_by_risk_framework", False) is not True
    gate1b = next(row for row in data["strategies"] if row["id"] == "individual_stock_momentum_gate1b_v1")
    assert gate1b["status"] in {
        "conditional_pending_provider_cost_review",
        "conditional_choose_provider_before_data_acquisition",
        "choose_norgate_for_gate1e_acquisition_review",
        "blocked_no_local_norgate_access",
        "conditional_pending_package_and_terms_selection",
    }
    assert gate1b["implementation_status"] == "not_implemented"
    assert gate1b["paper_forward_active"] is False
    assert gate1b["real_money_recommendation"] is False
    assert gate1b["allowed_next_action"] in {
        "provider_cost_review",
        "choose_provider_for_terms_review",
        "gate1e_controlled_acquisition_review",
        "configure_norgate_local_path",
        "user_select_sharadar_package",
    }


def test_commodity_basket_rows_reflect_fast_exploratory_screen() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    row = next(row for row in data["strategies"] if row["id"] == "commodity_basket_etf_momentum_v1")
    assert row["status"] == "fast_exploratory_screen_completed"
    assert row["implementation_status"] == "not_implemented"
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert row["allowed_next_action"] == "issuer_methodology_review"
    assert "implement_without_data_quality" in row["forbidden_next_actions"]
    assert "run_backtest_before_data_gate" in row["forbidden_next_actions"]
    assert "download_data_without_approved_prompt" in row["forbidden_next_actions"]
    assert "observe_as_paper_forward" in row["forbidden_next_actions"]
    screen = next(row for row in data["strategies"] if row["id"] == "commodity_basket_tsmom_top2_v1")
    assert screen["status"] == "research_sample_candidate_risk_budget_breach"
    assert screen["implementation_status"] == "implemented_research_sample"
    assert screen["paper_forward_active"] is False
    assert screen["real_money_recommendation"] is False
    assert screen["credibility_tier"] == "tier1_or_tier2_exploratory"
    assert screen["allowed_next_action"] == "research_sample_review"
    assert "use_futures_contract_logic" in screen["forbidden_next_actions"]


def test_commodity_risk_control_batch1_registry_rows_are_research_sample_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    by_id = {row["id"]: row for row in data["strategies"]}
    expected = {
        "commodity_basket_tsmom_top2_200d_filter_v1": "filter_ineffective_or_bug_review",
        "commodity_basket_tsmom_top2_half_bil_v1": "too_slow_defensive_watchlist",
        "combo_plus_commodity_basket_80_20_v1": "watchlist",
    }
    for row_id, status in expected.items():
        row = by_id[row_id]
        assert row["lane"] == "profit_exploration"
        assert row["status"] == status
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row["real_money_recommendation"] is False
        assert row["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review", "archive_or_watchlist"}
        assert "observe_as_paper_forward" in row["forbidden_next_actions"]
        assert "promote_to_real_money" in row["forbidden_next_actions"]
        assert "add_broker_integration" in row["forbidden_next_actions"]
        assert "place_live_orders" in row["forbidden_next_actions"]
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert "tune_parameters" in row["forbidden_next_actions"]
        assert "add_symbols_without_review" in row["forbidden_next_actions"]
    combo_plus = by_id["combo_plus_commodity_basket_80_20_v1"]
    assert combo_plus["evidence_source"] == "commodity_risk_control_batch1_diagnostics_completion"
    assert combo_plus["latest_evidence_path"] == "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest/"
    assert "change_active_combo_rules" in combo_plus["forbidden_next_actions"]
    assert "replace_spy200d" in combo_plus["forbidden_next_actions"]


def test_cde_rows_are_not_active_observation() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    rows = [row for row in data["strategies"] if row["id"].startswith(("C_", "D_", "E_"))]
    assert rows
    for row in rows:
        assert row["status"] != "active_observation"
        assert row["paper_forward_active"] is False


def test_validation_script_logic_passes() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation


def test_review_registry_rows_remain_non_active_and_non_real_money() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    qqq = next(row for row in data["strategies"] if row["id"] == "qqq_spy_gld_ief_dual_momentum_v1")
    sector = next(row for row in data["strategies"] if row["id"] == "sector_top2_momentum_simple_v1")
    managed = next(row for row in data["strategies"] if row["id"] == "managed_futures_proxy_etf_trend_v1")
    assert combo["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    if combo["status"] == "active_paper_demo_observation":
        assert combo["allowed_next_action"] == "run_monthly_paper_forward_checkpoint"
        assert combo["paper_forward_active"] is True
        assert combo["paper_forward_allowed_by_risk_framework"] is True
    else:
        assert combo["allowed_next_action"] == "controlled_cache_update_or_next_cached_observation_date"
        assert combo["paper_forward_active"] is False
        assert combo["paper_forward_allowed_by_risk_framework"] is False
    assert combo["canonical_rule_hash"] == "6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67"
    assert combo["hash_source_type"] == "source_spec_reconstructed_hash"
    assert combo.get("real_money_recommendation", False) is not True
    assert "replace_spy200d_without_governance" in combo["forbidden_next_actions"]
    assert "replace_spy200d_without_explicit_decision" in combo["forbidden_next_actions"]
    assert "fabricate_missing_data" in combo["forbidden_next_actions"]

    assert qqq["lane"] == "profit_exploration"
    assert qqq["status"] in {"research_sample_candidate", "watchlist", "candidate_exhaustive_queue", "duplicate_or_near_duplicate", "too_risky"}
    assert qqq["implementation_status"] == "implemented_research_sample"
    assert qqq["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review"}
    assert qqq["paper_forward_active"] is False
    assert qqq["paper_forward_allowed_by_risk_framework"] is False
    assert qqq["real_money_recommendation"] is False
    assert "observe_as_paper_forward" in qqq["forbidden_next_actions"]
    assert "change_paper_forward_rules" in qqq["forbidden_next_actions"]

    assert sector["lane"] == "profit_exploration"
    assert sector["status"] in {"research_sample_candidate", "watchlist", "candidate_exhaustive_queue", "duplicate_or_near_duplicate", "too_slow", "too_risky"}
    assert sector["implementation_status"] == "implemented_research_sample"
    assert sector["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review"}
    assert sector["paper_forward_active"] is False
    assert sector["paper_forward_allowed_by_risk_framework"] is False
    assert sector["real_money_recommendation"] is False
    assert "observe_as_paper_forward" in sector["forbidden_next_actions"]
    assert "change_paper_forward_rules" in sector["forbidden_next_actions"]
    assert "modify_A_ETF_sector_momentum" in sector["forbidden_next_actions"]
    assert "add_xlc_or_xlre_without_review" in sector["forbidden_next_actions"]

    assert managed["lane"] == "profit_exploration"
    assert managed["status"] in {
        "research_sample_candidate",
        "watchlist",
        "candidate_exhaustive_queue_short_history_labeled",
        "too_slow",
        "high_upside_high_risk",
        "too_risky",
        "duplicate_or_near_duplicate",
        "reject_proxy_not_useful",
    }
    assert managed["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
    assert managed["implementation_status"] == "implemented_research_sample"
    assert managed["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review_short_history_gate"}
    assert managed["paper_forward_active"] is False
    assert managed["paper_forward_allowed_by_risk_framework"] is False
    assert managed["real_money_recommendation"] is False
    assert "observe_as_paper_forward" in managed["forbidden_next_actions"]
    assert "change_paper_forward_rules" in managed["forbidden_next_actions"]
    assert "add_futures_contract_logic" in managed["forbidden_next_actions"]
    assert "treat_as_direct_futures_strategy" in managed["forbidden_next_actions"]
    assert "add_CTA_FMF_WTMF_without_review" in managed["forbidden_next_actions"]


def test_combination_batch1_registry_rows_are_research_sample_only() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    by_id = {row["id"]: row for row in data["strategies"]}
    for row_id in {
        "combo_plus_top2_50_50_v1",
        "combo_plus_managed_futures_80_20_v1",
        "top2_plus_managed_futures_80_20_v1",
    }:
        row = by_id[row_id]
        assert row["lane"] == "profit_exploration"
        assert row["status"] in {
            "candidate_exhaustive_queue",
            "research_sample_candidate",
            "watchlist",
            "too_slow",
            "short_horizon_too_slow",
            "short_history_watchlist",
            "candidate_exhaustive_review_required_short_history_labeled",
            "too_risky",
            "duplicate_or_near_duplicate",
            "incomplete_evidence",
            "reject_for_now",
        }
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row["real_money_recommendation"] is False
        assert row["allowed_next_action"] in {"research_sample_review", "candidate_exhaustive_review"}
        assert "observe_as_paper_forward" in row["forbidden_next_actions"]
        assert "promote_to_real_money" in row["forbidden_next_actions"]
        assert "add_broker_integration" in row["forbidden_next_actions"]
        assert "place_live_orders" in row["forbidden_next_actions"]
        assert "tune_weights" in row["forbidden_next_actions"]
        assert "change_active_combo_rules" in row["forbidden_next_actions"]
        assert "replace_spy200d" in row["forbidden_next_actions"]
    for row_id in {"combo_plus_managed_futures_80_20_v1", "top2_plus_managed_futures_80_20_v1"}:
        row = by_id[row_id]
        assert row["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
        assert "add_futures_contract_logic" in row["forbidden_next_actions"]
        assert "treat_as_direct_futures_strategy" in row["forbidden_next_actions"]


def test_evidence_latest_folder_has_required_files(tmp_path: Path) -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    _run_dir, latest = export_evidence(data, validation, tmp_path / "strategy_lab")
    files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert sorted(files) == sorted(REQUIRED_EVIDENCE_FILES)


def test_registry_evidence_contains_no_raw_ohlcv(tmp_path: Path) -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    _run_dir, latest = export_evidence(data, validation, tmp_path / "strategy_lab")
    names = [path.name.lower() for path in latest.iterdir() if path.is_file()]
    assert not any("ohlcv" in name or "raw" in name for name in names)


def test_strategy_modules_not_modified_by_export(tmp_path: Path) -> None:
    watched = [Path("src/strategies.py"), Path("src/backtester.py"), Path("src/data.py")]
    before = {path: path.read_bytes() for path in watched}
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    export_evidence(data, validation, tmp_path / "strategy_lab")
    after = {path: path.read_bytes() for path in watched}
    assert before == after


def test_registry_yaml_is_valid_yaml() -> None:
    with DEFAULT_REGISTRY.open("r", encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)
    assert parsed["registry"]["project"] == "trading_tournament"
