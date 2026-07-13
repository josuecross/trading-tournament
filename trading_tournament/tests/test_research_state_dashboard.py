from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

import run_research_state_dashboard as dashboard


ROOT = Path(__file__).resolve().parents[1]
LATEST_DIR = ROOT / "evidence" / "research_state" / "latest"
DASHBOARD_ZIP = ROOT / "evidence" / "research_state" / "latest_research_state_packet.zip"
PHASE = "historical_research_expansion_parallel_to_paper_demo_observation"


def test_dashboard_script_exists_and_runs() -> None:
    assert (ROOT / "run_research_state_dashboard.py").exists()
    latest = dashboard.build_dashboard()
    assert latest == LATEST_DIR
    assert latest.exists()
    assert len([p for p in latest.iterdir() if p.is_file()]) <= 10


def test_dashboard_latest_files_and_zip_are_compact() -> None:
    dashboard.build_dashboard()
    expected = {
        "README_FOR_ADVISOR.md",
        "current_state_summary.md",
        "active_observations.csv",
        "historical_leaders.csv",
        "candidate_status_matrix.csv",
        "blocked_and_gated_items.csv",
        "next_allowed_actions.csv",
        "warnings_and_limitations.md",
        "research_state_manifest.json",
    }
    assert {p.name for p in LATEST_DIR.iterdir() if p.is_file()} == expected
    assert DASHBOARD_ZIP.exists()
    with zipfile.ZipFile(DASHBOARD_ZIP) as zf:
        assert set(zf.namelist()) == expected


def test_dashboard_manifest_confirms_no_forbidden_actions() -> None:
    dashboard.build_dashboard()
    manifest = json.loads((LATEST_DIR / "research_state_manifest.json").read_text(encoding="utf-8"))
    assert manifest["current_phase"] == PHASE
    assert manifest["combination_batch1_verdict_audit_decision"] == "verdict_labels_corrected_with_no_candidate_exhaustive_run"
    assert manifest["combination_batch1_candidate_exhaustive_review_decision"] == "more_diagnostics_required_before_candidate_exhaustive_decision"
    assert manifest["combination_batch1_diagnostics_completion_decision"] == "diagnostics_support_short_history_watchlist_only"
    assert manifest["combination_batch1_target_window_comovement_status"] == "available"
    assert manifest["attribution_diagnostics_available"] is True
    assert manifest["target_window_attribution_available"] is True
    assert manifest["component_drawdown_attribution_available"] is True
    assert manifest["recovery_attribution_available"] is True
    assert manifest["worst_n_drawdown_export_available"] is True
    assert manifest["dsr_historical_metric_evidence_status"] == "unverified_non_comparable"
    assert manifest["dsr_current_diagnostic_evidence_status"] == "reproducible_diagnostic_only"
    assert manifest["dsr_metric_comparability"] == "non_comparable"
    assert manifest["dsr_metric_eligible_for_e4"] is False
    assert manifest["dsr_highest_independent_sel_level"] == "E1"
    assert manifest["dsr_metric_evidence_status"]["canonical_lifecycle_status"] == "active"
    assert manifest["dsr_metric_evidence_status"]["evidence_warning"].endswith("lifecycle_active_state_unchanged")
    assert manifest["individual_stock_momentum_gate1b_decision"] == "conditional_pending_provider_cost_review"
    assert manifest["individual_stock_momentum_gate1b_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1b_implementation_status"] == "not_implemented"
    assert manifest["individual_stock_momentum_gate1c_decision"] == "conditional_choose_provider_before_data_acquisition"
    assert manifest["individual_stock_momentum_gate1c_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1c_implementation_status"] == "not_implemented"
    assert manifest["individual_stock_momentum_gate1c_data_downloaded"] is False
    assert manifest["individual_stock_momentum_gate1c_provider_api_called"] is False
    assert manifest["individual_stock_momentum_gate1d_decision"] == "choose_norgate_for_gate1e_acquisition_review"
    assert manifest["individual_stock_momentum_gate1d_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1d_implementation_status"] == "not_implemented"
    assert manifest["individual_stock_momentum_gate1d_data_downloaded"] is False
    assert manifest["individual_stock_momentum_gate1d_provider_api_called"] is False
    assert manifest["individual_stock_momentum_gate1d_preferred_provider"] == "Norgate Data"
    assert manifest["individual_stock_momentum_gate1e_decision"] == "blocked_no_local_norgate_access"
    assert manifest["individual_stock_momentum_gate1e_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1e_implementation_status"] == "not_implemented"
    assert manifest["individual_stock_momentum_gate1e_data_downloaded"] is False
    assert manifest["individual_stock_momentum_gate1e_full_stock_universe_downloaded"] is False
    assert manifest["individual_stock_momentum_gate1e_provider_api_called"] is False
    assert manifest["individual_stock_momentum_gate1e_local_access_status"] == "not_found"
    assert manifest["individual_stock_momentum_gate1e_terms_acceptance_status"] == "not_confirmed"
    assert manifest["individual_stock_momentum_gate1f_decision"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1f_status"] == "conditional_pending_package_and_terms_selection"
    assert manifest["individual_stock_momentum_gate1f_implementation_status"] == "not_implemented"
    assert manifest["individual_stock_momentum_gate1f_data_downloaded"] is False
    assert manifest["individual_stock_momentum_gate1f_provider_api_called"] is False
    assert manifest["individual_stock_momentum_gate1f_package_selected"] is False
    assert manifest["individual_stock_momentum_gate1f_provider_focus"] == "Nasdaq Data Link / Sharadar"
    assert manifest["research_queue_reprioritization_decision"] == "choose_commodity_basket_etf_momentum_review"
    assert manifest["research_queue_reprioritization_next_family"] == "commodity_basket_etf_momentum_v1"
    assert manifest["research_queue_reprioritization_next_allowed_action"] == "create_commodity_basket_etf_momentum_review"
    assert manifest["commodity_basket_etf_momentum_status"] == "fast_exploratory_screen_completed"
    assert manifest["commodity_basket_etf_momentum_implementation_status"] == "not_implemented"
    assert manifest["commodity_basket_etf_momentum_allowed_next_action"] == "issuer_methodology_review"
    assert manifest["commodity_basket_etf_review_decision"] == "approve_data_acquisition_review"
    assert manifest["commodity_basket_etf_review_data_acquisition_review_approved"] is True
    assert manifest["commodity_basket_etf_review_implementation_approved"] is False
    assert manifest["commodity_basket_etf_review_data_downloaded"] is False
    assert manifest["commodity_basket_etf_review_provider_api_called"] is False
    assert set(manifest["commodity_basket_etf_review_products_reviewed"]) == {"DBC", "PDBC", "COMT", "GSG", "USCI"}
    assert manifest["commodity_data_acquisition_review_decision"] == "conditional_pending_product_identity_terms_review"
    assert manifest["commodity_data_acquisition_future_download_prompt_approved"] is False
    assert manifest["commodity_data_acquisition_future_download_symbols_approved"] == []
    assert manifest["commodity_data_acquisition_stage1_preferred_symbols_after_terms_review"] == ["PDBC", "COMT"]
    assert manifest["commodity_data_acquisition_data_downloaded"] is False
    assert manifest["commodity_data_acquisition_provider_api_called"] is False
    assert manifest["commodity_data_acquisition_strategy_implemented"] is False
    assert manifest["fast_exploratory_data_policy_available"] is True
    assert set(manifest["commodity_fast_exploratory_downloaded_symbols"]).issubset({"DBC", "PDBC", "COMT", "GSG", "USCI"})
    assert manifest["commodity_fast_exploratory_raw_ohlcv_included"] is False
    assert manifest["commodity_exploratory_status"] in {"watchlist", "too_slow", "too_risky", "research_sample_candidate", "research_sample_candidate_risk_budget_breach", "incomplete_evidence", "reject_for_now", "duplicate_or_near_duplicate"}
    assert manifest["commodity_exploratory_implementation_status"] == "implemented_research_sample"
    assert manifest["commodity_exploratory_candidate_exhaustive_run"] is False
    assert manifest["commodity_exploratory_paper_forward_active"] is False
    assert manifest["commodity_exploratory_real_money_recommendation"] is False
    assert manifest["commodity_risk_control_batch1_completed"] is True
    assert manifest["commodity_risk_control_batch1_base_verdict_correction"] == "research_sample_candidate_risk_budget_breach"
    assert manifest["commodity_risk_control_batch1_best_candidate"] == "combo_plus_commodity_basket_80_20_v1"
    assert manifest["commodity_risk_control_batch1_candidate_exhaustive_recommended"] is False
    assert manifest["commodity_risk_control_batch1_candidate_exhaustive_run"] is False
    assert manifest["commodity_risk_control_batch1_data_downloaded"] is False
    assert manifest["commodity_risk_control_batch1_new_symbols_added"] is False
    assert manifest["crypto_fast_exploratory_policy_available"] is True
    assert set(manifest["crypto_spot_fast_cache_confirmed_symbols"]).issubset({"BTC-USD", "ETH-USD"})
    assert set(manifest["crypto_spot_fast_downloaded_symbols"]).issubset({"BTC-USD", "ETH-USD"})
    assert set(manifest["crypto_spot_fast_failed_symbols"]).issubset({"BTC-USD", "ETH-USD"})
    assert manifest["crypto_spot_fast_raw_ohlcv_included"] is False
    assert manifest["crypto_tier2_risk_control_batch1_completed"] is True
    assert manifest["crypto_tier2_risk_control_batch1_candidate_exhaustive_run"] is False
    assert manifest["crypto_tier2_risk_control_batch1_data_downloaded"] is False
    assert manifest["crypto_tier2_risk_control_batch1_paper_forward_active"] is False
    assert manifest["crypto_tier2_risk_control_batch1_real_money_recommendation"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_leverage"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_margin"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_shorting"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_futures_contracts"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_perpetuals"] is False
    assert manifest["crypto_tier2_risk_control_batch1_uses_options"] is False
    approved_global_symbols = {"SPY", "QQQ", "GLD", "IEF", "BIL", "DBC", "PDBC", "COMT", "GSG", "USCI", "IWM", "EFA", "EEM", "TLT"}
    assert manifest["global_multi_asset_fast_acquisition_data_downloaded"] is True
    assert set(manifest["global_multi_asset_fast_acquisition_downloaded_symbols"]).issubset(approved_global_symbols)
    assert set(manifest["global_multi_asset_fast_acquisition_cache_confirmed_symbols"]).issubset(approved_global_symbols)
    assert manifest["global_multi_asset_fast_acquisition_failed_symbols"] == []
    assert manifest["global_multi_asset_fast_acquisition_raw_ohlcv_included"] is False
    assert manifest["global_multi_asset_batch1_completed"] is True
    assert manifest["global_multi_asset_batch1_best_candidate"] == "global_multi_asset_tsmom_top2_v1"
    assert manifest["global_multi_asset_batch1_best_candidate_registry_status"] == "research_sample_candidate_risk_budget_breach"
    assert manifest["global_multi_asset_batch1_candidate_exhaustive_recommended"] is False
    assert manifest["global_multi_asset_batch1_candidate_exhaustive_run"] is False
    assert manifest["global_multi_asset_batch1_data_downloaded_in_profit_exploration"] is False
    assert manifest["global_multi_asset_batch1_paper_forward_active"] is False
    assert manifest["global_multi_asset_batch1_real_money_recommendation"] is False
    assert manifest["global_multi_asset_batch1_uses_leverage"] is False
    assert manifest["global_multi_asset_batch1_uses_margin"] is False
    assert manifest["global_multi_asset_batch1_uses_shorting"] is False
    assert manifest["global_multi_asset_batch1_uses_futures_contracts"] is False
    assert manifest["global_multi_asset_batch1_uses_options"] is False
    assert manifest["global_multi_asset_batch1_uses_forex"] is False
    assert manifest["global_multi_asset_batch1_uses_intraday"] is False
    assert manifest["commodity_risk_control_verdict_audit_decision"] == "commodity_risk_control_verdicts_audited_more_diagnostics_required"
    assert manifest["commodity_risk_control_verdict_audit_candidate_exhaustive_decision"] == "more_diagnostics_required_before_candidate_exhaustive_decision"
    assert manifest["commodity_risk_control_verdict_audit_candidate_exhaustive_run"] is False
    assert manifest["commodity_risk_control_verdict_audit_target_window_comovement_status"] == "unavailable_missing_window_ids"
    assert manifest["commodity_risk_control_verdict_audit_component_contribution_status"] == "partial_unavailable_exact_path_contribution"
    assert manifest["commodity_risk_control_diagnostics_completion_decision"] == "diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20"
    assert manifest["commodity_risk_control_diagnostics_completion_candidate_exhaustive_recommended"] is False
    assert manifest["commodity_risk_control_diagnostics_completion_candidate_exhaustive_run"] is False
    assert manifest["commodity_risk_control_diagnostics_completion_target_window_comovement_status"] == "available"
    assert manifest["commodity_risk_control_diagnostics_completion_component_contribution_status"] == "partial_available_final_equity_window_contribution"
    assert manifest["commodity_risk_control_diagnostics_completion_drawdown_overlap_status"] == "available"
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_current_state_summary_contains_phase_and_correction() -> None:
    dashboard.build_dashboard()
    summary = (LATEST_DIR / "current_state_summary.md").read_text(encoding="utf-8")
    assert f"current_phase: `{PHASE}`" in summary
    assert "combo active as paper/demo observation" in summary
    assert "SPY_200d frozen control" in summary
    assert "DSR active/frozen observation: `active`" in summary
    assert "historical_unverified_non_comparable" in summary
    assert "current_diagnostic_only" in summary
    assert "not_qualifying_e4" in summary
    assert "Forward checkpoint is not ready for judgment" in summary
    assert "does not block historical research" in summary
    assert "no recent research_sample candidate deserves candidate_exhaustive now" in summary
    assert "use attribution diagnostics before any future combination candidate_exhaustive review" in summary
    assert "Latest combination verdict audit" in summary
    assert "short_history_watchlist" in summary
    assert "more_diagnostics_required_before_candidate_exhaustive_decision" in summary
    assert "Latest combination diagnostics completion" in summary
    assert "diagnostics_support_short_history_watchlist_only" in summary
    assert "target-window co-movement=available" in summary
    assert "Attribution diagnostics available: `true`" in summary
    assert "Target-window attribution: `true`" in summary
    assert "Component drawdown attribution: `true`" in summary
    assert "Recovery attribution: `true`" in summary
    assert "Worst-N drawdown export: `true`" in summary
    assert "Individual stock momentum Gate 1B historical decision" in summary
    assert "Individual stock momentum Gate 1C historical decision" in summary
    assert "Individual stock momentum Gate 1D historical decision" in summary
    assert "Individual stock momentum Gate 1E Norgate blocker" in summary
    assert "Individual stock momentum Gate 1F status" in summary
    assert "blocked_no_local_norgate_access" in summary
    assert "conditional_pending_package_and_terms_selection" in summary
    assert "Provider focus: `Nasdaq Data Link / Sharadar`" in summary
    assert "Package selected: `false`" in summary
    assert "Local access: `not_found`" in summary
    assert "Terms: `not_confirmed`" in summary
    assert "data downloaded: `false`" in summary
    assert "provider API called: `false`" in summary
    assert "Historical research queue reprioritization" in summary
    assert "choose_commodity_basket_etf_momentum_review" in summary
    assert "commodity_basket_etf_momentum_v1" in summary
    assert "create_commodity_basket_etf_momentum_review" in summary
    assert "Commodity basket ETF product/data review" in summary
    assert "approve_data_acquisition_review" in summary
    assert "commodity_data_acquisition_review" in summary
    assert "Commodity basket ETF data acquisition review" in summary
    assert "conditional_pending_product_identity_terms_review" in summary
    assert "Future download symbols approved under the old strict lane" in summary
    assert "Provider API called in that review: `false`" in summary
    assert "Fast exploratory ETF/fund data policy available: `true`" in summary
    assert "Commodity fast exploratory acquisition downloaded symbols" in summary
    assert "Raw OHLCV in compact evidence: `false`" in summary
    assert "Commodity exploratory screen status" in summary
    assert "Candidate_exhaustive run: `false`" in summary
    assert "Paper-forward active: `false`" in summary
    assert "Commodity Risk-Control Batch 1 status: completed" in summary
    assert "research_sample_candidate_risk_budget_breach" in summary
    assert "combo_plus_commodity_basket_80_20_v1" in summary
    assert "Candidate_exhaustive recommended: `false`" in summary
    assert "Commodity Risk-Control Batch 1 verdict audit" in summary
    assert "more_diagnostics_required_before_candidate_exhaustive_decision" in summary
    assert "unavailable_missing_window_ids" in summary
    assert "partial_unavailable_exact_path_contribution" in summary
    assert "Commodity Risk-Control Batch 1 diagnostics completion" in summary
    assert "diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20" in summary
    assert "Drawdown overlap: `available`" in summary
    assert "Global multi-asset fast acquisition downloaded symbols" in summary
    assert "Global Multi-Asset ETF Fast Exploration Batch 1 status: `true`" in summary
    assert "Best multi-asset candidate: `global_multi_asset_tsmom_top2_v1`" in summary
    assert "no candidate_exhaustive is currently recommended" in summary
    assert "keep combo_plus_commodity_basket_80_20_v1 on watchlist only" in summary
    assert "product identity and wrapper/tax/roll-risk review" in summary
    assert "Data acquisition review approved: `true`" in summary
    assert "Implementation approved: `false`" in summary
    assert "Commodity data downloaded: `false`" in summary
    assert "Stock momentum remains provider-blocked/conditional" in summary
    assert "No paper-forward strategy was implemented" in summary


def test_dashboard_csvs_report_active_combo_and_queues() -> None:
    dashboard.build_dashboard()
    active = pd.read_csv(LATEST_DIR / "active_observations.csv")
    leaders = pd.read_csv(LATEST_DIR / "historical_leaders.csv")
    candidates = pd.read_csv(LATEST_DIR / "candidate_status_matrix.csv")
    blocked = pd.read_csv(LATEST_DIR / "blocked_and_gated_items.csv")
    actions = pd.read_csv(LATEST_DIR / "next_allowed_actions.csv")
    combo = active[active["strategy"].eq("combo_SPY200d_GLD_50_50_v1")].iloc[0]
    dsr = active[active["strategy"].eq("paper_forward_dsr_sector_equal_weight_defensive_filter_v1")].iloc[0]
    assert combo["status"] == "active_paper_demo_observation"
    assert round(float(combo["current_equity"]), 2) == 2998.50
    assert combo["decision_status"] == "inconclusive_too_early"
    assert "unverified_non_comparable" in dsr["notes"]
    assert "reproducible_diagnostic_only" in dsr["notes"]
    assert "E4 lineage incomplete" in dsr["notes"]
    assert "asset_class_tsmom_top2_v1" in set(leaders["strategy"])
    recent = candidates[candidates["candidate_id"].isin([
        "qqq_spy_gld_ief_dual_momentum_v1",
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
        "managed_futures_proxy_etf_trend_v1",
    ])]
    assert not recent.empty
    assert recent["deserves_candidate_exhaustive"].astype(str).str.lower().eq("false").all()
    assert "combo_plus_top2_50_50_review_v1" in set(blocked["item_id"])
    assert "create_combination_design_implementation_review" in set(actions["action"])
    assert "use_attribution_diagnostics_before_future_combination_candidate_exhaustive_review" in set(actions["action"])
    assert "select_sharadar_package_and_terms_review" in set(actions["action"])
    assert "create_commodity_basket_etf_momentum_review" in set(actions["action"])
    assert "commodity_data_acquisition_review" in set(actions["action"])
    assert "product_identity_terms_review" in set(actions["action"])
    assert "commodity_risk_control_research_sample_review" in set(actions["action"])
    assert "global_multi_asset_batch1_research_sample_review" in set(actions["action"])
    assert "commodity_risk_control_verdict_diagnostics_review" in set(actions["action"])
    assert "commodity_risk_control_watchlist_review" in set(actions["action"])
    assert "research_sample_review" in set(actions["action"])


def test_dashboard_source_does_not_call_backtests_profit_or_downloads() -> None:
    source = (ROOT / "run_research_state_dashboard.py").read_text(encoding="utf-8")
    assert "run_backtest.py" not in source
    assert "run_profit_exploration.py" not in source
    assert "run_paper_forward_observation.py" not in source
    assert "yfinance" not in source
    assert "subprocess" not in source
