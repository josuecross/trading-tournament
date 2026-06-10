from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from research_diagnostics.attribution_diagnostics import (
    compute_target_window_attribution,
    extract_worst_n_drawdown_windows,
)
from run_challenge_audit import load_etf_price_cache, sample_etf_starts


REPO_ROOT = Path(__file__).resolve().parent
SPEC_PATH = REPO_ROOT / "profit_lab" / "profit_experiment_specs.yaml"
OBJECTIVE_PATH = REPO_ROOT / "profit_lab" / "profit_objective.yaml"
OUTPUT_ROOT = REPO_ROOT / "evidence" / "profit_exploration"
COMBINATION_OUTPUT_ROOT = REPO_ROOT / "evidence" / "combination_lab"
COMBINATION_DIAGNOSTICS_COMPLETION_ROOT = COMBINATION_OUTPUT_ROOT / "batch1_diagnostics_completion"
RESEARCH_DIAGNOSTICS_OUTPUT_ROOT = REPO_ROOT / "evidence" / "research_diagnostics"
COMMODITY_EXPLORATORY_OUTPUT_ROOT = REPO_ROOT / "evidence" / "commodity_exploratory"
COMMODITY_LAB_OUTPUT_ROOT = REPO_ROOT / "evidence" / "commodity_lab"
COMMODITY_RISK_CONTROL_OUTPUT_ROOT = COMMODITY_LAB_OUTPUT_ROOT / "risk_control_batch1"
COMMODITY_RISK_CONTROL_DIAGNOSTICS_COMPLETION_ROOT = COMMODITY_LAB_OUTPUT_ROOT / "risk_control_batch1_diagnostics_completion"
MULTI_ASSET_LAB_OUTPUT_ROOT = REPO_ROOT / "evidence" / "multi_asset_lab"
GLOBAL_MULTI_ASSET_BATCH1_OUTPUT_ROOT = MULTI_ASSET_LAB_OUTPUT_ROOT / "fast_exploration_batch1"
CRYPTO_LAB_OUTPUT_ROOT = REPO_ROOT / "evidence" / "crypto_lab"
CRYPTO_TIER2_RISK_CONTROL_OUTPUT_ROOT = CRYPTO_LAB_OUTPUT_ROOT / "tier2_risk_control_batch1"
STARTING_EQUITY = 3000.0
TARGETS = {
    "300": 3300.0,
    "400": 3400.0,
    "600": 3600.0,
    "900": 3900.0,
    "1200": 4200.0,
}
ABSOLUTE_STOP = 2400.0
TRAILING_DRAWDOWN = 600.0
HORIZONS = [30, 60, 90, 180]
LABEL_COSTS = {"standard": 0.0005, "stress": 0.001}
ACCOUNTING_TOLERANCE = 1e-6
REFERENCE_TOLERANCE = 1e-4
BUY_HOLD_SYMBOLS = {
    "SPY_buy_hold": "SPY",
    "GLD_buy_hold": "GLD",
    "IEF_buy_hold": "IEF",
    "BIL_cash_proxy": "BIL",
}
CORE_BUY_HOLD_BENCHMARKS = set(BUY_HOLD_SYMBOLS)
QQQ_EXPERIMENT_ID = "qqq_spy_gld_ief_dual_momentum_v1"
VALUE_MOMENTUM_EXPERIMENT_ID = "value_momentum_factor_etf_rotation_v1"
SECTOR_TOP2_EXPERIMENT_ID = "sector_top2_momentum_simple_v1"
MANAGED_FUTURES_EXPERIMENT_ID = "managed_futures_proxy_etf_trend_v1"
MANAGED_FUTURES_REQUIRED_LABEL = "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
COMMODITY_EXPLORATORY_EXPERIMENT_ID = "commodity_basket_tsmom_top2_v1"
COMMODITY_EXPLORATORY_SYMBOLS = ["DBC", "PDBC", "COMT", "GSG", "USCI"]
COMMODITY_EXPLORATORY_REQUIRED_LABEL = "commodity_wrapper_evidence_research_sample_only"
COMMODITY_RISK_CONTROL_BATCH1_IDS = [
    "commodity_basket_tsmom_top2_200d_filter_v1",
    "commodity_basket_tsmom_top2_half_bil_v1",
    "combo_plus_commodity_basket_80_20_v1",
]
COMMODITY_RISK_CONTROL_DEFINITIONS = {
    "commodity_basket_tsmom_top2_200d_filter_v1": {
        "rule_summary": "Monthly top-2 commodity wrapper TSMOM with 126-day positive return and close > 200-day SMA filter; unused weight to BIL.",
        "hypothesis": "A simple absolute trend filter may reduce drawdown-budget breaches.",
        "main_risk": "May become too slow and reduce target rates.",
    },
    "commodity_basket_tsmom_top2_half_bil_v1": {
        "rule_summary": "50% base commodity_basket_tsmom_top2_v1 sleeve and 50% BIL, fixed monthly rebalance.",
        "hypothesis": "Fixed defensive scaling may preserve some commodity upside while reducing drawdown.",
        "main_risk": "Target dilution and too-slow behavior.",
    },
    "combo_plus_commodity_basket_80_20_v1": {
        "rule_summary": "80% historical combo_SPY200d_GLD_50_50_v1 component and 20% base commodity_basket_tsmom_top2_v1 sleeve, fixed monthly rebalance.",
        "hypothesis": "Commodity basket exposure may add upside/regime diversification to the historical combo while keeping drawdown controlled.",
        "main_risk": "May duplicate GLD/commodity exposure, add wrapper risk, or fail to improve target windows.",
    },
}
CRYPTO_SPOT_SYMBOLS = ["BTC-USD", "ETH-USD"]
CRYPTO_TIER2_REQUIRED_LABEL = "crypto_spot_tier2_exploratory"
CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS = [
    "crypto_spot_tsmom_top1_cash_filter_v1",
    "crypto_spot_equal_weight_200d_filter_v1",
    "combo_plus_crypto_spot_tsmom_90_10_v1",
]
CRYPTO_TIER2_RISK_CONTROL_DEFINITIONS = {
    "crypto_spot_tsmom_top1_cash_filter_v1": {
        "rule_summary": "Monthly BTC/ETH top-1 TSMOM with 126-day positive return and close > 200-day SMA filters; 50% selected spot crypto and 50% BIL; 100% BIL if no crypto qualifies.",
        "hypothesis": "A single best crypto trend sleeve with 50% cash may capture upside while reducing stop risk.",
        "main_risk": "Still too volatile or too slow after cash scaling.",
    },
    "crypto_spot_equal_weight_200d_filter_v1": {
        "rule_summary": "Monthly BTC/ETH equal-weight eligibility screen; each qualifying asset receives 25%, unused weight goes to BIL, and max crypto exposure is 50%.",
        "hypothesis": "Diversified BTC/ETH half-exposure can reduce single-asset risk.",
        "main_risk": "Crypto beta may remain too high, or target power may dilute.",
    },
    "combo_plus_crypto_spot_tsmom_90_10_v1": {
        "rule_summary": "90% historical combo_SPY200d_GLD_50_50_v1 component and 10% crypto_spot_tsmom_top1_cash_filter_v1, fixed monthly rebalance.",
        "hypothesis": "A small crypto spot trend sleeve may create incremental target windows while keeping drawdown inside budget.",
        "main_risk": "The 10% sleeve may be too small to matter or may add sharp drawdown noise.",
    },
}
GLOBAL_MULTI_ASSET_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT"]
GLOBAL_MULTI_ASSET_ACQUISITION_SYMBOLS = [
    "SPY",
    "QQQ",
    "GLD",
    "IEF",
    "BIL",
    "DBC",
    "PDBC",
    "COMT",
    "GSG",
    "USCI",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
]
GLOBAL_MULTI_ASSET_REQUIRED_LABEL = "etf_fund_wrapper_evidence_research_sample_only"
GLOBAL_MULTI_ASSET_BATCH1_IDS = [
    "global_multi_asset_tsmom_top2_v1",
    "global_multi_asset_tsmom_top2_defensive_50_v1",
    "combo_plus_global_multi_asset_80_20_v1",
]
GLOBAL_MULTI_ASSET_BATCH1_DEFINITIONS = {
    "global_multi_asset_tsmom_top2_v1": {
        "rule_summary": "Monthly top-2 global ETF/fund wrapper TSMOM across SPY, QQQ, IWM, EFA, EEM, IEF, TLT, GLD, PDBC, and COMT; 126-day positive return filter; unused weight to BIL.",
        "hypothesis": "Broader global/equity/duration/real-asset universe may improve target probability and regime coverage.",
        "main_risk": "May become high-beta equity/commodity rotation or duplicate existing leaders.",
    },
    "global_multi_asset_tsmom_top2_defensive_50_v1": {
        "rule_summary": "50% global_multi_asset_tsmom_top2_v1 sleeve and 50% BIL, fixed monthly rebalance.",
        "hypothesis": "Scaling down global rotation may retain some target power while improving drawdown.",
        "main_risk": "May become too slow.",
    },
    "combo_plus_global_multi_asset_80_20_v1": {
        "rule_summary": "80% historical combo_SPY200d_GLD_50_50_v1 component and 20% global_multi_asset_tsmom_top2_v1 sleeve, fixed monthly rebalance.",
        "hypothesis": "Small global multi-asset sleeve may create incremental target windows beyond combo without breaching drawdown budget.",
        "main_risk": "Mostly combo behavior with small multi-asset tilt.",
    },
}
COMBINATION_BATCH1_IDS = [
    "combo_plus_top2_50_50_v1",
    "combo_plus_managed_futures_80_20_v1",
    "top2_plus_managed_futures_80_20_v1",
]
COMBINATION_BATCH1_MANAGED_FUTURES_IDS = {
    "combo_plus_managed_futures_80_20_v1",
    "top2_plus_managed_futures_80_20_v1",
}
COMBINATION_BATCH1_DEFINITIONS = {
    "combo_plus_top2_50_50_v1": {
        "components": ["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"],
        "weights": {"combo_SPY200d_GLD_50_50_v1": 0.50, "asset_class_tsmom_top2_v1": 0.50},
        "hypothesis": "Blend drawdown-aware combo with stronger asset-class momentum target potential.",
        "main_risk": "Duplicate SPY/GLD/trend exposure; may not improve stop-aware profit/risk.",
        "required_label": "",
    },
    "combo_plus_managed_futures_80_20_v1": {
        "components": ["combo_SPY200d_GLD_50_50_v1", MANAGED_FUTURES_EXPERIMENT_ID],
        "weights": {"combo_SPY200d_GLD_50_50_v1": 0.80, MANAGED_FUTURES_EXPERIMENT_ID: 0.20},
        "hypothesis": "Add a different fund-wrapper proxy return driver to reduce drawdown or improve stress behavior.",
        "main_risk": "Managed-futures proxy was too slow as standalone and has short-history fund-wrapper limitations.",
        "required_label": MANAGED_FUTURES_REQUIRED_LABEL,
    },
    "top2_plus_managed_futures_80_20_v1": {
        "components": ["asset_class_tsmom_top2_v1", MANAGED_FUTURES_EXPERIMENT_ID],
        "weights": {"asset_class_tsmom_top2_v1": 0.80, MANAGED_FUTURES_EXPERIMENT_ID: 0.20},
        "hypothesis": "Reduce top2 drawdown-budget usage while retaining target potential.",
        "main_risk": "Target dilution; short-history managed-futures proxy evidence.",
        "required_label": MANAGED_FUTURES_REQUIRED_LABEL,
    },
}
COMBINATION_BATCH1_REQUIRED_RUN_IDS = set(COMBINATION_BATCH1_IDS) | {
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "BIL_cash_proxy",
    "SPY_buy_hold",
    QQQ_EXPERIMENT_ID,
    VALUE_MOMENTUM_EXPERIMENT_ID,
    SECTOR_TOP2_EXPERIMENT_ID,
    MANAGED_FUTURES_EXPERIMENT_ID,
    "asset_class_tsmom_equal_weight_v1",
}
COMMODITY_EXPLORATORY_REQUIRED_RUN_IDS = {
    COMMODITY_EXPLORATORY_EXPERIMENT_ID,
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "BIL_cash_proxy",
}
COMMODITY_RISK_CONTROL_REQUIRED_RUN_IDS = set(COMMODITY_RISK_CONTROL_BATCH1_IDS) | {
    COMMODITY_EXPLORATORY_EXPERIMENT_ID,
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "BIL_cash_proxy",
}
CRYPTO_TIER2_RISK_CONTROL_REQUIRED_RUN_IDS = set(CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS) | {
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "BIL_cash_proxy",
}
GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_RUN_IDS = set(GLOBAL_MULTI_ASSET_BATCH1_IDS) | {
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "BIL_cash_proxy",
}
SECTOR_TOP2_SYMBOLS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
MANAGED_FUTURES_SYMBOLS = ["DBMF", "KMLM"]
QQQ_DIAGNOSTIC_COLUMNS = [
    "duplicate_status",
    "qqq_selection_frequency",
    "spy_selection_frequency",
    "gld_selection_frequency",
    "ief_selection_frequency",
    "bil_allocation_frequency",
    "max_single_asset_allocation",
    "qqq_allocation_share",
    "equity_asset_allocation_share",
    "defensive_asset_allocation_share",
    "concentration_warning",
    "equity_beta_duplicate_warning",
]
VALUE_MOMENTUM_DIAGNOSTIC_COLUMNS = [
    "mtum_selection_frequency",
    "vtv_selection_frequency",
    "qual_selection_frequency",
    "usmv_selection_frequency",
    "mtum_allocation_share",
    "vtv_allocation_share",
    "qual_allocation_share",
    "usmv_allocation_share",
    "spy_allocation_share",
    "bil_allocation_share",
    "max_single_etf_allocation",
    "equity_factor_allocation_share",
    "cash_treasury_allocation_share",
]
SECTOR_TOP2_DIAGNOSTIC_COLUMNS = [
    "xlb_selection_frequency",
    "xle_selection_frequency",
    "xlf_selection_frequency",
    "xli_selection_frequency",
    "xlk_selection_frequency",
    "xlp_selection_frequency",
    "xlu_selection_frequency",
    "xlv_selection_frequency",
    "xly_selection_frequency",
    "xlb_allocation_share",
    "xle_allocation_share",
    "xlf_allocation_share",
    "xli_allocation_share",
    "xlk_allocation_share",
    "xlp_allocation_share",
    "xlu_allocation_share",
    "xlv_allocation_share",
    "xly_allocation_share",
    "equity_sector_allocation_share",
    "max_single_sector_allocation",
    "top_sector_dominance",
    "sector_turnover",
]
MANAGED_FUTURES_DIAGNOSTIC_COLUMNS = [
    "required_label",
    "wrapper_proxy_warning",
    "short_history_warning",
    "dbmf_selection_frequency",
    "kmlm_selection_frequency",
    "dbmf_allocation_share",
    "kmlm_allocation_share",
    "max_single_proxy_allocation",
    "proxy_concentration_warning",
    "too_slow_warning",
    "wrapper_proxy_only_warning",
    "direct_futures_claim_disallowed",
    "correlation_to_combo_if_available",
    "correlation_to_top2_if_available",
    "correlation_to_spy200d_if_available",
    "drawdown_coincidence_warning_if_available",
]
COMBINATION_BATCH1_DIAGNOSTIC_COLUMNS = [
    "fixed_combination_batch_warning",
    "component_combo_allocation_share",
    "component_top2_allocation_share",
    "component_managed_futures_allocation_share",
    "max_single_sleeve_allocation",
    "duplicate_correlation_warning",
    "correlation_diagnostics_status",
    "drawdown_coincidence_diagnostics_status",
]
COMMODITY_EXPLORATORY_DIAGNOSTIC_COLUMNS = [
    "commodity_required_label",
    "commodity_wrapper_warning",
    "exploratory_public_data_warning",
    "not_paper_forward_warning",
    "commodity_risk_control_batch_warning",
    "commodity_risk_control_rule_type",
    "component_commodity_allocation_share",
    "component_bil_allocation_share",
    "dbc_selection_frequency",
    "pdbc_selection_frequency",
    "comt_selection_frequency",
    "gsg_selection_frequency",
    "usci_selection_frequency",
    "dbc_allocation_share",
    "pdbc_allocation_share",
    "comt_allocation_share",
    "gsg_allocation_share",
    "usci_allocation_share",
    "commodity_wrapper_allocation_share",
    "bil_fallback_frequency",
    "bil_fallback_allocation_share",
    "max_single_commodity_wrapper_allocation",
    "product_concentration_warning",
]
CRYPTO_TIER2_DIAGNOSTIC_COLUMNS = [
    "crypto_required_label",
    "crypto_spot_warning",
    "crypto_tier2_warning",
    "public_or_cached_crypto_data_warning",
    "crypto_not_paper_forward_warning",
    "crypto_no_exchange_execution_warning",
    "crypto_24_7_calendar_warning",
    "uses_perpetuals",
    "uses_options",
    "btc_selection_frequency",
    "eth_selection_frequency",
    "btc_allocation_share",
    "eth_allocation_share",
    "crypto_spot_allocation_share",
    "bil_cash_allocation_share",
    "max_crypto_exposure",
    "max_single_crypto_allocation",
    "component_crypto_allocation_share",
]
GLOBAL_MULTI_ASSET_DIAGNOSTIC_COLUMNS = [
    "global_multi_asset_required_label",
    "global_multi_asset_wrapper_warning",
    "global_multi_asset_batch_warning",
    "global_multi_asset_rule_type",
    "component_global_multi_asset_allocation_share",
    "global_spy_selection_frequency",
    "global_qqq_selection_frequency",
    "global_iwm_selection_frequency",
    "global_efa_selection_frequency",
    "global_eem_selection_frequency",
    "global_ief_selection_frequency",
    "global_tlt_selection_frequency",
    "global_gld_selection_frequency",
    "global_pdbc_selection_frequency",
    "global_comt_selection_frequency",
    "global_bil_allocation_frequency",
    "global_spy_allocation_share",
    "global_qqq_allocation_share",
    "global_iwm_allocation_share",
    "global_efa_allocation_share",
    "global_eem_allocation_share",
    "global_ief_allocation_share",
    "global_tlt_allocation_share",
    "global_gld_allocation_share",
    "global_pdbc_allocation_share",
    "global_comt_allocation_share",
    "global_bil_allocation_share",
    "global_equity_allocation_share",
    "global_international_allocation_share",
    "global_duration_allocation_share",
    "global_real_asset_allocation_share",
    "max_single_global_asset_allocation",
    "global_equity_beta_duplicate_warning",
    "global_wrapper_concentration_warning",
]
DIAGNOSTIC_COLUMNS = (
    QQQ_DIAGNOSTIC_COLUMNS
    + VALUE_MOMENTUM_DIAGNOSTIC_COLUMNS
    + SECTOR_TOP2_DIAGNOSTIC_COLUMNS
    + MANAGED_FUTURES_DIAGNOSTIC_COLUMNS
    + COMBINATION_BATCH1_DIAGNOSTIC_COLUMNS
    + COMMODITY_EXPLORATORY_DIAGNOSTIC_COLUMNS
    + CRYPTO_TIER2_DIAGNOSTIC_COLUMNS
    + GLOBAL_MULTI_ASSET_DIAGNOSTIC_COLUMNS
)
REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "profit_exploration_summary.md",
    "profit_exploration_results.csv",
    "rolling_profit_distribution.csv",
    "profit_rankings.csv",
    "risk_and_stop_summary.csv",
    "experiment_status.csv",
    "assumptions_and_costs.yaml",
    "warnings_and_limitations.md",
    "profit_charts.png",
]
COMBINATION_REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "combination_batch1_summary.md",
    "combination_batch1_results.csv",
    "combination_batch1_rankings.csv",
    "combination_batch1_risk_summary.csv",
    "combination_batch1_correlation_diagnostics.csv",
    "combination_batch1_status.csv",
    "warnings_and_limitations.md",
    "combination_batch1_manifest.json",
]
COMMODITY_EXPLORATORY_REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "commodity_exploratory_summary.md",
    "commodity_exploratory_results.csv",
    "commodity_exploratory_risk_summary.csv",
    "commodity_exploratory_rankings.csv",
    "commodity_exploratory_status.csv",
    "warnings_and_limitations.md",
    "commodity_exploratory_manifest.json",
]
COMMODITY_RISK_CONTROL_REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "risk_control_batch1_summary.md",
    "risk_control_batch1_results.csv",
    "risk_control_batch1_rankings.csv",
    "risk_control_batch1_risk_summary.csv",
    "risk_control_batch1_diagnostics.csv",
    "risk_control_batch1_status.csv",
    "warnings_and_limitations.md",
    "risk_control_batch1_manifest.json",
]
CRYPTO_TIER2_RISK_CONTROL_REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "tier2_risk_control_batch1_summary.md",
    "tier2_risk_control_batch1_results.csv",
    "tier2_risk_control_batch1_rankings.csv",
    "tier2_risk_control_batch1_risk_summary.csv",
    "tier2_risk_control_batch1_diagnostics.csv",
    "tier2_risk_control_batch1_status.csv",
    "warnings_and_limitations.md",
    "tier2_risk_control_batch1_manifest.json",
]
GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_LATEST_FILES = [
    "README_FOR_ADVISOR.md",
    "fast_exploration_batch1_summary.md",
    "fast_exploration_batch1_results.csv",
    "fast_exploration_batch1_rankings.csv",
    "fast_exploration_batch1_risk_summary.csv",
    "fast_exploration_batch1_diagnostics.csv",
    "fast_exploration_batch1_status.csv",
    "warnings_and_limitations.md",
    "fast_exploration_batch1_manifest.json",
]
COMBINATION_DIAGNOSTICS_DETAIL_FILE = "combination_diagnostics_detail.csv"
COMMODITY_RISK_CONTROL_DIAGNOSTICS_DETAIL_FILE = "commodity_risk_control_diagnostics_detail.csv"
RESULT_COLUMNS = [
    "run_id",
    "experiment_id",
    "display_name",
    "experiment_type",
    "family_group",
    "strategy_family",
    "evidence_tier",
    "run_status",
    "starting_equity",
    "independent_account",
    "shared_capital",
    "standard_or_stress",
    "final_validation_completed",
    "sampled_results_are_final",
    "unconditional_final_equity",
    "stop_enforced_final_equity",
    "total_return_unconditional",
    "total_return_stop_enforced",
    "max_equity",
    "min_equity",
    "max_drawdown_dollars",
    "max_drawdown_pct",
    "any_project_stop_hit",
    "first_project_stop_date",
    "target_300_before_stop",
    "target_400_before_stop",
    "target_600_before_stop",
    "target_900_before_stop",
    "target_1200_before_stop",
    "days_to_target_300",
    "days_to_target_400",
    "days_to_target_600",
    "days_to_target_900",
    "days_to_target_1200",
    "stress_degradation",
    "run_validation_scope",
    "selected_horizons",
    "omitted_horizons",
    "selected_horizons_completed",
    "full_horizon_validation_completed",
    "candidate_exhaustive_completed",
    "reduced_validation",
    "reduced_validation_reason",
    "evidence_finality",
    "risk_framework_verdict",
    "profit_verdict",
    "promotion_blockers",
    "notes",
    "accounting_integrity_status",
    "rolling_rebase_check_passed",
    "buy_hold_reference_check_passed",
    "combination_return_check_passed",
    "profit_results_usable",
    "integrity_error_count",
    "integrity_notes",
    "canonical_rule_hash",
    "duplicate_of",
    *DIAGNOSTIC_COLUMNS,
]
ROLLING_COLUMNS = [
    "experiment_id",
    "horizon",
    "standard_or_stress",
    "rolling_method",
    "number_of_windows",
    "possible_window_count",
    "p_target_300_before_stop",
    "p_target_400_before_stop",
    "p_target_600_before_stop",
    "p_target_900_before_stop",
    "p_target_1200_before_stop",
    "p_any_project_stop_hit",
    "median_stop_enforced_final_equity",
    "mean_stop_enforced_final_equity",
    "p25_stop_enforced_final_equity",
    "p75_stop_enforced_final_equity",
    "p90_stop_enforced_final_equity",
    "p95_stop_enforced_final_equity",
    "max_stop_enforced_final_equity",
    "median_max_drawdown",
    "worst_max_drawdown",
    "expected_profit_dollars",
    "expected_profit_pct",
    "run_validation_scope",
    "selected_horizons",
    "omitted_horizons",
    "selected_horizons_completed",
    "full_horizon_validation_completed",
    "candidate_exhaustive_completed",
    "reduced_validation",
    "reduced_validation_reason",
    "evidence_finality",
    "notes",
    "window_start_equity_min",
    "window_start_equity_max",
    "window_start_equity_violation_count",
    "high_water_start_violation_count",
    "target_state_start_violation_count",
    "stop_state_start_violation_count",
    "reference_check_available",
    "reference_median_abs_error",
    "reference_max_abs_error",
    "reference_error_status",
    "accounting_integrity_status",
]
RANKING_COLUMNS = [
    "rank_overall",
    "rank_profit_potential",
    "rank_risk_control",
    "rank_upside",
    "experiment_id",
    "display_name",
    "evidence_tier",
    "run_status",
    "p_90d_target_300_before_stop",
    "p_90d_target_400_before_stop",
    "p_90d_target_600_before_stop",
    "p_90d_target_900_before_stop",
    "p_90d_target_1200_before_stop",
    "p_90d_any_stop_hit",
    "median_90d_stop_enforced_final_equity",
    "p95_90d_stop_enforced_final_equity",
    "worst_90d_max_drawdown",
    "expected_profit_90d",
    "p_180d_target_300_before_stop",
    "p_180d_target_400_before_stop",
    "p_180d_target_600_before_stop",
    "p_180d_target_900_before_stop",
    "p_180d_target_1200_before_stop",
    "p_180d_any_stop_hit",
    "median_180d_stop_enforced_final_equity",
    "p95_180d_stop_enforced_final_equity",
    "worst_180d_max_drawdown",
    "expected_profit_180d",
    "stress_degradation",
    "run_validation_scope",
    "selected_horizons",
    "omitted_horizons",
    "selected_horizons_completed",
    "full_horizon_validation_completed",
    "candidate_exhaustive_completed",
    "reduced_validation",
    "reduced_validation_reason",
    "profit_score",
    "risk_penalty",
    "final_score",
    "score_target_300_component",
    "score_target_400_component",
    "score_target_600_component",
    "score_target_900_component",
    "score_target_1200_component",
    "score_median_equity_component",
    "score_p95_equity_component",
    "score_expected_profit_component",
    "score_stop_penalty_component",
    "score_drawdown_excess_penalty_component",
    "score_stress_penalty_component",
    "score_tier_penalty_component",
    "profit_seeking_score",
    "balanced_score",
    "drawdown_control_score",
    "rank_profit_seeking_score",
    "rank_balanced_score",
    "rank_drawdown_control_score",
    "score_audit_notes",
    "balanced_drawdown_aware_score_v2",
    "rank_balanced_drawdown_aware_v2",
    "risk_budget_used_90d",
    "risk_budget_used_180d",
    "target_score_component",
    "upside_score_component",
    "median_equity_score_component",
    "tail_equity_score_component",
    "stop_penalty_component",
    "drawdown_budget_penalty_component",
    "stress_penalty_component",
    "evidence_quality_penalty_component",
    "practical_verdict_v2",
    "practical_score_notes",
    "profit_verdict",
    "ranking_notes",
    "accounting_integrity_status",
    "profit_results_usable",
    "ranking_blocked_reason",
    "canonical_rule_hash",
    "duplicate_of",
    *DIAGNOSTIC_COLUMNS,
    "candidate_exhaustive_queue_rank",
    "deserves_candidate_exhaustive",
    "queue_reason",
]


@dataclass
class ExperimentModel:
    experiment_id: str
    kind: str
    prices: pd.DataFrame
    weights: pd.DataFrame | None = None
    note: str = ""
    reference_symbol: str | None = None
    sleeve_models: dict[str, "ExperimentModel"] | None = None
    sleeve_weights: dict[str, float] | None = None


def run_id_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def canonicalize_rule(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize_rule(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_rule(item) for item in value]
    return value


def canonical_rule_hash(spec: dict[str, Any]) -> str:
    rule = spec.get("canonical_rule")
    if not rule:
        return ""
    normalized = canonicalize_rule(rule)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_finalist_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_horizons(raw: str | None) -> list[int]:
    if not raw:
        return []
    horizons: list[int] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            horizon = int(text)
        except ValueError as exc:
            raise SystemExit(f"Invalid horizon value: {text}") from exc
        if horizon not in HORIZONS:
            raise SystemExit(f"Unsupported horizon {horizon}; supported horizons are {','.join(map(str, HORIZONS))}")
        horizons.append(horizon)
    deduped: list[int] = []
    for horizon in horizons:
        if horizon not in deduped:
            deduped.append(horizon)
    return deduped


def selected_horizons_for_args(args: argparse.Namespace) -> list[int]:
    parsed = parse_horizons(getattr(args, "horizons", None))
    if parsed:
        return parsed
    if getattr(args, "mode", "") == "smoke":
        return [90]
    return HORIZONS.copy()


def validation_metadata(args: argparse.Namespace) -> dict[str, Any]:
    selected = selected_horizons_for_args(args)
    omitted = [horizon for horizon in HORIZONS if horizon not in selected]
    reduced = bool(omitted)
    selected_text = ",".join(str(horizon) for horizon in selected)
    omitted_text = ",".join(str(horizon) for horizon in omitted)
    candidate_exhaustive_scope = bool(not reduced and getattr(args, "mode", "") == "candidate_exhaustive")
    return {
        "run_validation_scope": "finalist_reduced_90_180" if reduced and selected == [90, 180] else ("reduced_horizon_validation" if reduced else "all_horizons"),
        "selected_horizons": selected_text,
        "omitted_horizons": omitted_text,
        "full_horizon_validation_completed": False if reduced else getattr(args, "mode", "") == "candidate_exhaustive",
        "candidate_exhaustive_completed": candidate_exhaustive_scope,
        "reduced_validation": reduced,
        "reduced_validation_reason": "runtime_control_2_to_3_hours" if reduced else "",
    }


def selected_horizons_completed(rows: list[dict[str, Any]], selected_horizons: list[int], reduced: bool) -> bool:
    if not rows:
        return False
    by_horizon = {int(row.get("horizon")): row for row in rows if pd.notna(row.get("horizon"))}
    for horizon in selected_horizons:
        row = by_horizon.get(horizon)
        if not row:
            return False
        if str(row.get("rolling_method")) != "all_possible":
            return False
        if int(row.get("number_of_windows", -1)) != int(row.get("possible_window_count", -2)):
            return False
        expected_finality = "exact_selected_horizons" if reduced else "exact_all_possible"
        if str(row.get("evidence_finality")) != expected_finality:
            return False
    return True


def add_validation_metadata(frame: pd.DataFrame, meta: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    for key, value in meta.items():
        if key not in out.columns:
            out[key] = value
        else:
            out[key] = out[key].fillna(value)
    if "selected_horizons_completed" not in out.columns:
        out["selected_horizons_completed"] = False
    if "full_horizon_validation_completed" not in out.columns:
        out["full_horizon_validation_completed"] = bool(meta.get("full_horizon_validation_completed", False))
    if "candidate_exhaustive_completed" not in out.columns:
        out["candidate_exhaustive_completed"] = bool(meta.get("candidate_exhaustive_completed", False))
    return out


def filter_specs_to_finalists(specs: list[dict[str, Any]], finalist_ids: list[str]) -> list[dict[str, Any]]:
    if not finalist_ids:
        return specs
    spec_by_id = {str(spec["experiment_id"]): spec for spec in specs}
    missing = [exp_id for exp_id in finalist_ids if exp_id not in spec_by_id]
    if missing:
        raise SystemExit(f"Unknown profit exploration finalist(s): {', '.join(missing)}")
    return [spec_by_id[exp_id] for exp_id in finalist_ids]


def duplicate_map_for_specs(specs: list[dict[str, Any]]) -> dict[str, str]:
    first_by_hash: dict[str, str] = {}
    duplicates: dict[str, str] = {}
    for spec in specs:
        rule_hash = canonical_rule_hash(spec)
        if not rule_hash:
            continue
        exp_id = str(spec["experiment_id"])
        if rule_hash in first_by_hash:
            duplicates[exp_id] = first_by_hash[rule_hash]
        else:
            first_by_hash[rule_hash] = exp_id
    return duplicates


def load_specs(path: Path = SPEC_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    specs = data.get("experiments", [])
    required = {
        "experiment_id",
        "display_name",
        "experiment_type",
        "family_group",
        "strategy_family",
        "evidence_tier",
        "run_allowed",
        "implementation_status",
        "independent_account",
        "starting_equity",
        "underlying_components",
        "rule_source",
        "expected_profit_mechanism",
        "main_risk",
        "allowed_next_action",
        "forbidden_next_actions",
        "notes",
    }
    seen: set[str] = set()
    for spec in specs:
        missing = required - set(spec)
        if missing:
            raise ValueError(f"Profit experiment {spec.get('experiment_id', 'unknown')} missing {sorted(missing)}.")
        if spec["experiment_id"] in seen:
            raise ValueError(f"Duplicate profit experiment id {spec['experiment_id']}.")
        seen.add(str(spec["experiment_id"]))
        if spec.get("independent_account") is not True:
            raise ValueError(f"{spec['experiment_id']} must use an independent account.")
    return specs


def load_prices() -> pd.DataFrame:
    data = load_etf_price_cache(
        [
            "SPY",
            "BIL",
            "IEF",
            "GLD",
            "QQQ",
            "MTUM",
            "VTV",
            "QUAL",
            "USMV",
            *SECTOR_TOP2_SYMBOLS,
            *MANAGED_FUTURES_SYMBOLS,
            *COMMODITY_EXPLORATORY_SYMBOLS,
            "IWM",
            "EFA",
            "EEM",
            "TLT",
        ]
    )
    if data.empty:
        return pd.DataFrame()
    prices = data.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    last_loaded_date = data.groupby("symbol")["date"].max().min()
    if pd.notna(last_loaded_date):
        prices = prices.loc[prices.index <= last_loaded_date]
    crypto_prices = load_crypto_spot_price_cache()
    if not crypto_prices.empty:
        aligned_crypto = crypto_prices.reindex(prices.index).ffill()
        prices = prices.join(aligned_crypto, how="left")
    return prices.dropna(how="all")


def load_crypto_spot_price_cache() -> pd.DataFrame:
    cache_dir = REPO_ROOT / "data" / "exploratory" / "crypto_spot_momentum" / "cache"
    frames: list[pd.DataFrame] = []
    for symbol in CRYPTO_SPOT_SYMBOLS:
        path = cache_dir / f"yfinance_{symbol}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if "date" not in frame.columns:
            continue
        value_column = "adj_close" if "adj_close" in frame.columns else ("close" if "close" in frame.columns else "")
        if not value_column:
            continue
        parsed = pd.DataFrame(
            {
                "date": pd.to_datetime(frame["date"], errors="coerce"),
                symbol: pd.to_numeric(frame[value_column], errors="coerce"),
            }
        ).dropna(subset=["date"])
        parsed = parsed.groupby("date", as_index=False)[symbol].last().sort_values("date")
        frames.append(parsed.set_index("date"))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index().dropna(how="all")


def restrict_prices_to_common_history(prices: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    missing = [symbol for symbol in symbols if symbol not in prices.columns]
    if missing:
        raise KeyError(f"combination batch requires cached symbols: {', '.join(missing)}")
    common = prices[symbols].notna().all(axis=1)
    if not bool(common.any()):
        raise KeyError(f"combination batch has no common cached history for: {', '.join(symbols)}")
    first_common = common[common].index[0]
    last_common = common[common].index[-1]
    return prices.loc[first_common:last_common].copy()


def shifted_weights(weights: pd.DataFrame) -> pd.DataFrame:
    return weights.shift(1).ffill().fillna(0.0).clip(0.0, 1.0)


def buy_hold_weights(prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if symbol in weights:
        weights.loc[prices[symbol].notna(), symbol] = 1.0
    return weights.fillna(0.0).clip(0.0, 1.0)


def trend_200d_weights(prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if symbol not in prices:
        return weights
    sma = prices[symbol].rolling(200, min_periods=200).mean()
    risk_on = prices[symbol] > sma
    weights.loc[risk_on.fillna(False), symbol] = 1.0
    if "BIL" in weights:
        weights.loc[~risk_on.fillna(False) & prices["BIL"].notna(), "BIL"] = 1.0
    return shifted_weights(weights)


def monthly_signal_weights(prices: pd.DataFrame, decision: pd.DataFrame) -> pd.DataFrame:
    month = pd.Series(pd.to_datetime(prices.index).to_period("M"), index=prices.index)
    rebalance = month.ne(month.shift(1))
    weights = decision.where(rebalance, np.nan).ffill().fillna(0.0)
    return shifted_weights(weights)


def dual_momentum_weights(prices: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[universe].pct_change(126, fill_method=None)
    sma = prices[universe].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        row = rets.loc[dt].dropna()
        if row.empty:
            if "BIL" in decision:
                decision.at[dt, "BIL"] = 1.0
            continue
        best = str(row.idxmax())
        if row[best] > 0 and prices.at[dt, best] > sma.at[dt, best]:
            decision.at[dt, best] = 1.0
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def qqq_dual_momentum_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = ["QQQ", "SPY", "GLD", "IEF", "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"QQQ dual momentum requires cached symbols: {', '.join(missing)}")
    return dual_momentum_weights(prices, ["QQQ", "SPY", "GLD", "IEF"])


def value_momentum_factor_rotation_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = ["MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"value/momentum factor rotation requires cached symbols: {', '.join(missing)}")
    universe = ["MTUM", "VTV", "QUAL", "USMV", "SPY"]
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[universe].pct_change(126, fill_method=None)
    sma = prices[universe].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                selected.append(str(symbol))
        if selected:
            selected_weight = 1.0 / 2.0
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def sector_top2_momentum_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*SECTOR_TOP2_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"sector top2 momentum requires cached core-nine symbols: {', '.join(missing)}")
    disallowed = [symbol for symbol in ["XLC", "XLRE"] if symbol in prices.columns]
    if disallowed:
        # XLC/XLRE may exist elsewhere in project config/cache, but this fixed first rule excludes them.
        pass
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[SECTOR_TOP2_SYMBOLS].pct_change(126, fill_method=None)
    sma = prices[SECTOR_TOP2_SYMBOLS].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                selected.append(str(symbol))
        if selected:
            selected_weight = 1.0 / 2.0
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def managed_futures_proxy_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*MANAGED_FUTURES_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"managed-futures proxy requires cached wrapper symbols: {', '.join(missing)}")
    forbidden = [symbol for symbol in ["CTA", "FMF", "WTMF"] if symbol in prices.columns]
    if forbidden:
        # These symbols may be reviewed elsewhere later, but this fixed first rule excludes them.
        pass
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[MANAGED_FUTURES_SYMBOLS].pct_change(126, fill_method=None)
    sma = prices[MANAGED_FUTURES_SYMBOLS].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                selected.append(str(symbol))
        if selected:
            selected_weight = 0.5
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def commodity_basket_tsmom_top2_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"commodity basket exploratory requires cached wrapper symbols: {', '.join(missing)}")
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[COMMODITY_EXPLORATORY_SYMBOLS].pct_change(126, fill_method=None)
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if pd.notna(rets.at[dt, symbol]) and rets.at[dt, symbol] > 0:
                selected.append(str(symbol))
        if selected:
            selected_weight = 0.5
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def commodity_basket_tsmom_top2_200d_filter_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"commodity risk-control 200d filter requires cached wrapper symbols: {', '.join(missing)}")
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[COMMODITY_EXPLORATORY_SYMBOLS].pct_change(126, fill_method=None)
    sma = prices[COMMODITY_EXPLORATORY_SYMBOLS].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                selected.append(str(symbol))
        if selected:
            selected_weight = 0.5
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def global_multi_asset_tsmom_top2_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*GLOBAL_MULTI_ASSET_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"global multi-asset Batch 1 requires cached ETF/fund symbols: {', '.join(missing)}")
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[GLOBAL_MULTI_ASSET_SYMBOLS].pct_change(126, fill_method=None)
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if pd.notna(rets.at[dt, symbol]) and rets.at[dt, symbol] > 0:
                selected.append(str(symbol))
        if selected:
            selected_weight = 0.5
            for symbol in selected:
                decision.at[dt, symbol] = selected_weight
            unused_weight = 1.0 - selected_weight * len(selected)
            if unused_weight > 0 and "BIL" in decision:
                decision.at[dt, "BIL"] = unused_weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def crypto_spot_tsmom_top1_cash_filter_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*CRYPTO_SPOT_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"crypto Tier 2 top1 cash filter requires cached symbols: {', '.join(missing)}")
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[CRYPTO_SPOT_SYMBOLS].pct_change(126, fill_method=None)
    sma = prices[CRYPTO_SPOT_SYMBOLS].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        eligible: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                eligible.append(str(symbol))
        if eligible:
            decision.at[dt, eligible[0]] = 0.5
            decision.at[dt, "BIL"] = 0.5
        else:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def crypto_spot_equal_weight_200d_filter_weights(prices: pd.DataFrame) -> pd.DataFrame:
    required = [*CRYPTO_SPOT_SYMBOLS, "BIL"]
    missing = [symbol for symbol in required if symbol not in prices.columns]
    if missing:
        raise KeyError(f"crypto Tier 2 equal-weight 200d filter requires cached symbols: {', '.join(missing)}")
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[CRYPTO_SPOT_SYMBOLS].pct_change(126, fill_method=None)
    sma = prices[CRYPTO_SPOT_SYMBOLS].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        crypto_weight = 0.0
        for symbol in CRYPTO_SPOT_SYMBOLS:
            if (
                pd.notna(rets.at[dt, symbol])
                and rets.at[dt, symbol] > 0
                and pd.notna(sma.at[dt, symbol])
                and prices.at[dt, symbol] > sma.at[dt, symbol]
            ):
                decision.at[dt, symbol] = 0.25
                crypto_weight += 0.25
        decision.at[dt, "BIL"] = max(0.0, 1.0 - crypto_weight)
    return monthly_signal_weights(prices, decision)


def average_asset_exposure(model: ExperimentModel, assets: list[str]) -> pd.Series:
    if model.kind == "weighted" and model.weights is not None:
        return model.weights.reindex(columns=assets, fill_value=0.0).fillna(0.0).clip(0.0, 1.0).mean(axis=0)
    if model.kind == "combo" and model.sleeve_models and model.sleeve_weights:
        exposure = pd.Series(0.0, index=assets, dtype=float)
        for sleeve, weight in model.sleeve_weights.items():
            sleeve_model = model.sleeve_models.get(sleeve)
            if sleeve_model is None:
                continue
            exposure = exposure.add(float(weight) * average_asset_exposure(sleeve_model, assets), fill_value=0.0)
        return exposure.reindex(assets).fillna(0.0)
    return pd.Series(0.0, index=assets, dtype=float)


def allocation_diagnostics(model: ExperimentModel | None, spec: dict[str, Any], duplicate_status: str = "canonical_unique") -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "duplicate_status": duplicate_status,
        "qqq_selection_frequency": math.nan,
        "spy_selection_frequency": math.nan,
        "gld_selection_frequency": math.nan,
        "ief_selection_frequency": math.nan,
        "bil_allocation_frequency": math.nan,
        "max_single_asset_allocation": math.nan,
        "qqq_allocation_share": math.nan,
        "equity_asset_allocation_share": math.nan,
        "defensive_asset_allocation_share": math.nan,
        "concentration_warning": False,
        "equity_beta_duplicate_warning": False,
        "mtum_selection_frequency": math.nan,
        "vtv_selection_frequency": math.nan,
        "qual_selection_frequency": math.nan,
        "usmv_selection_frequency": math.nan,
        "mtum_allocation_share": math.nan,
        "vtv_allocation_share": math.nan,
        "qual_allocation_share": math.nan,
        "usmv_allocation_share": math.nan,
        "spy_allocation_share": math.nan,
        "bil_allocation_share": math.nan,
        "max_single_etf_allocation": math.nan,
        "equity_factor_allocation_share": math.nan,
        "cash_treasury_allocation_share": math.nan,
        "xlb_selection_frequency": math.nan,
        "xle_selection_frequency": math.nan,
        "xlf_selection_frequency": math.nan,
        "xli_selection_frequency": math.nan,
        "xlk_selection_frequency": math.nan,
        "xlp_selection_frequency": math.nan,
        "xlu_selection_frequency": math.nan,
        "xlv_selection_frequency": math.nan,
        "xly_selection_frequency": math.nan,
        "xlb_allocation_share": math.nan,
        "xle_allocation_share": math.nan,
        "xlf_allocation_share": math.nan,
        "xli_allocation_share": math.nan,
        "xlk_allocation_share": math.nan,
        "xlp_allocation_share": math.nan,
        "xlu_allocation_share": math.nan,
        "xlv_allocation_share": math.nan,
        "xly_allocation_share": math.nan,
        "equity_sector_allocation_share": math.nan,
        "max_single_sector_allocation": math.nan,
        "top_sector_dominance": math.nan,
        "sector_turnover": math.nan,
        "required_label": "",
        "wrapper_proxy_warning": False,
        "short_history_warning": False,
        "dbmf_selection_frequency": math.nan,
        "kmlm_selection_frequency": math.nan,
        "dbmf_allocation_share": math.nan,
        "kmlm_allocation_share": math.nan,
        "max_single_proxy_allocation": math.nan,
        "proxy_concentration_warning": False,
        "too_slow_warning": False,
        "wrapper_proxy_only_warning": False,
        "direct_futures_claim_disallowed": False,
        "correlation_to_combo_if_available": math.nan,
        "correlation_to_top2_if_available": math.nan,
        "correlation_to_spy200d_if_available": math.nan,
        "drawdown_coincidence_warning_if_available": False,
        "fixed_combination_batch_warning": False,
        "component_combo_allocation_share": math.nan,
        "component_top2_allocation_share": math.nan,
        "component_managed_futures_allocation_share": math.nan,
        "max_single_sleeve_allocation": math.nan,
        "duplicate_correlation_warning": False,
        "correlation_diagnostics_status": "not_applicable",
        "drawdown_coincidence_diagnostics_status": "not_applicable",
        "commodity_required_label": "",
        "commodity_wrapper_warning": False,
        "exploratory_public_data_warning": False,
        "not_paper_forward_warning": False,
        "commodity_risk_control_batch_warning": False,
        "commodity_risk_control_rule_type": "",
        "component_commodity_allocation_share": math.nan,
        "component_bil_allocation_share": math.nan,
        "dbc_selection_frequency": math.nan,
        "pdbc_selection_frequency": math.nan,
        "comt_selection_frequency": math.nan,
        "gsg_selection_frequency": math.nan,
        "usci_selection_frequency": math.nan,
        "dbc_allocation_share": math.nan,
        "pdbc_allocation_share": math.nan,
        "comt_allocation_share": math.nan,
        "gsg_allocation_share": math.nan,
        "usci_allocation_share": math.nan,
        "commodity_wrapper_allocation_share": math.nan,
        "bil_fallback_frequency": math.nan,
        "bil_fallback_allocation_share": math.nan,
        "max_single_commodity_wrapper_allocation": math.nan,
        "product_concentration_warning": False,
        "direct_futures_claim_disallowed": False,
        "crypto_required_label": "",
        "crypto_spot_warning": False,
        "crypto_tier2_warning": False,
        "public_or_cached_crypto_data_warning": False,
        "crypto_not_paper_forward_warning": False,
        "crypto_no_exchange_execution_warning": False,
        "crypto_24_7_calendar_warning": False,
        "uses_perpetuals": False,
        "uses_options": False,
        "btc_selection_frequency": math.nan,
        "eth_selection_frequency": math.nan,
        "btc_allocation_share": math.nan,
        "eth_allocation_share": math.nan,
        "crypto_spot_allocation_share": math.nan,
        "bil_cash_allocation_share": math.nan,
        "max_crypto_exposure": math.nan,
        "max_single_crypto_allocation": math.nan,
        "component_crypto_allocation_share": math.nan,
        "global_multi_asset_required_label": "",
        "global_multi_asset_wrapper_warning": False,
        "global_multi_asset_batch_warning": False,
        "global_multi_asset_rule_type": "",
        "component_global_multi_asset_allocation_share": math.nan,
        "global_spy_selection_frequency": math.nan,
        "global_qqq_selection_frequency": math.nan,
        "global_iwm_selection_frequency": math.nan,
        "global_efa_selection_frequency": math.nan,
        "global_eem_selection_frequency": math.nan,
        "global_ief_selection_frequency": math.nan,
        "global_tlt_selection_frequency": math.nan,
        "global_gld_selection_frequency": math.nan,
        "global_pdbc_selection_frequency": math.nan,
        "global_comt_selection_frequency": math.nan,
        "global_bil_allocation_frequency": math.nan,
        "global_spy_allocation_share": math.nan,
        "global_qqq_allocation_share": math.nan,
        "global_iwm_allocation_share": math.nan,
        "global_efa_allocation_share": math.nan,
        "global_eem_allocation_share": math.nan,
        "global_ief_allocation_share": math.nan,
        "global_tlt_allocation_share": math.nan,
        "global_gld_allocation_share": math.nan,
        "global_pdbc_allocation_share": math.nan,
        "global_comt_allocation_share": math.nan,
        "global_bil_allocation_share": math.nan,
        "global_equity_allocation_share": math.nan,
        "global_international_allocation_share": math.nan,
        "global_duration_allocation_share": math.nan,
        "global_real_asset_allocation_share": math.nan,
        "max_single_global_asset_allocation": math.nan,
        "global_equity_beta_duplicate_warning": False,
        "global_wrapper_concentration_warning": False,
    }
    exp_id = str(spec.get("experiment_id"))
    if exp_id in COMBINATION_BATCH1_IDS:
        definition = COMBINATION_BATCH1_DEFINITIONS[exp_id]
        sleeve_weights = definition["weights"]
        max_sleeve = float(max(sleeve_weights.values())) if sleeve_weights else math.nan
        diagnostics.update(
            {
                "fixed_combination_batch_warning": True,
                "component_combo_allocation_share": float(sleeve_weights.get("combo_SPY200d_GLD_50_50_v1", 0.0)),
                "component_top2_allocation_share": float(sleeve_weights.get("asset_class_tsmom_top2_v1", 0.0)),
                "component_managed_futures_allocation_share": float(sleeve_weights.get(MANAGED_FUTURES_EXPERIMENT_ID, 0.0)),
                "max_single_sleeve_allocation": max_sleeve,
                "duplicate_correlation_warning": exp_id == "combo_plus_top2_50_50_v1",
                "correlation_diagnostics_status": "available_after_combination_batch_output",
                "drawdown_coincidence_diagnostics_status": "available_after_combination_batch_output",
            }
        )
        if exp_id in COMBINATION_BATCH1_MANAGED_FUTURES_IDS:
            diagnostics.update(
                {
                    "required_label": MANAGED_FUTURES_REQUIRED_LABEL,
                    "wrapper_proxy_warning": True,
                    "short_history_warning": True,
                    "wrapper_proxy_only_warning": True,
                    "direct_futures_claim_disallowed": True,
                }
            )
        return diagnostics
    if exp_id in {COMMODITY_EXPLORATORY_EXPERIMENT_ID, *COMMODITY_RISK_CONTROL_BATCH1_IDS} and model is not None:
        assets = [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"]
        exposure = average_asset_exposure(model, assets)
        commodity_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in COMMODITY_EXPLORATORY_SYMBOLS))
        max_wrapper_share = float(exposure.reindex(COMMODITY_EXPLORATORY_SYMBOLS).fillna(0.0).max())
        selected = (
            model.weights.reindex(columns=assets, fill_value=0.0).fillna(0.0).gt(0.0).mean(axis=0)
            if model.kind == "weighted" and model.weights is not None and not model.weights.empty
            else pd.Series(math.nan, index=assets)
        )
        is_risk_batch = exp_id in COMMODITY_RISK_CONTROL_BATCH1_IDS
        rule_type = {
            COMMODITY_EXPLORATORY_EXPERIMENT_ID: "base_top2_positive_126d_return",
            "commodity_basket_tsmom_top2_200d_filter_v1": "top2_positive_126d_return_plus_200d_sma_filter",
            "commodity_basket_tsmom_top2_half_bil_v1": "fixed_half_base_commodity_half_bil",
            "combo_plus_commodity_basket_80_20_v1": "fixed_combo_80_base_commodity_20",
        }.get(exp_id, "")
        sleeve_weights = model.sleeve_weights or {}
        diagnostics.update(
            {
                "commodity_required_label": COMMODITY_EXPLORATORY_REQUIRED_LABEL,
                "commodity_wrapper_warning": True,
                "exploratory_public_data_warning": True,
                "not_paper_forward_warning": True,
                "commodity_risk_control_batch_warning": is_risk_batch,
                "commodity_risk_control_rule_type": rule_type,
                "component_combo_allocation_share": float(sleeve_weights.get("combo_SPY200d_GLD_50_50_v1", 0.0)),
                "component_commodity_allocation_share": float(sleeve_weights.get(COMMODITY_EXPLORATORY_EXPERIMENT_ID, 1.0 if exp_id in {COMMODITY_EXPLORATORY_EXPERIMENT_ID, "commodity_basket_tsmom_top2_200d_filter_v1"} else 0.0)),
                "component_bil_allocation_share": float(sleeve_weights.get("BIL_cash_proxy", 0.0)),
                "dbc_selection_frequency": float(selected.get("DBC", math.nan)),
                "pdbc_selection_frequency": float(selected.get("PDBC", math.nan)),
                "comt_selection_frequency": float(selected.get("COMT", math.nan)),
                "gsg_selection_frequency": float(selected.get("GSG", math.nan)),
                "usci_selection_frequency": float(selected.get("USCI", math.nan)),
                "dbc_allocation_share": float(exposure.get("DBC", 0.0)),
                "pdbc_allocation_share": float(exposure.get("PDBC", 0.0)),
                "comt_allocation_share": float(exposure.get("COMT", 0.0)),
                "gsg_allocation_share": float(exposure.get("GSG", 0.0)),
                "usci_allocation_share": float(exposure.get("USCI", 0.0)),
                "commodity_wrapper_allocation_share": commodity_share,
                "bil_fallback_frequency": float(selected.get("BIL", math.nan)),
                "bil_fallback_allocation_share": float(exposure.get("BIL", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", math.nan)),
                "bil_allocation_share": float(exposure.get("BIL", 0.0)),
                "max_single_commodity_wrapper_allocation": max_wrapper_share,
                "product_concentration_warning": bool(pd.notna(max_wrapper_share) and max_wrapper_share > 0.60),
                "direct_futures_claim_disallowed": True,
            }
        )
        return diagnostics
    if exp_id in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS and model is not None:
        assets = [*CRYPTO_SPOT_SYMBOLS, "BIL"]
        exposure = average_asset_exposure(model, assets)
        crypto_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in CRYPTO_SPOT_SYMBOLS))
        max_crypto = float(exposure.reindex(CRYPTO_SPOT_SYMBOLS).fillna(0.0).max())
        selected = (
            model.weights.reindex(columns=assets, fill_value=0.0).fillna(0.0).gt(0.0).mean(axis=0)
            if model.kind == "weighted" and model.weights is not None and not model.weights.empty
            else pd.Series(math.nan, index=assets)
        )
        sleeve_weights = model.sleeve_weights or {}
        diagnostics.update(
            {
                "crypto_required_label": CRYPTO_TIER2_REQUIRED_LABEL,
                "crypto_spot_warning": True,
                "crypto_tier2_warning": True,
                "public_or_cached_crypto_data_warning": True,
                "crypto_not_paper_forward_warning": True,
                "crypto_no_exchange_execution_warning": True,
                "crypto_24_7_calendar_warning": True,
                "direct_futures_claim_disallowed": True,
                "uses_perpetuals": False,
                "uses_options": False,
                "component_combo_allocation_share": float(sleeve_weights.get("combo_SPY200d_GLD_50_50_v1", 0.0)),
                "component_crypto_allocation_share": float(sleeve_weights.get("crypto_spot_tsmom_top1_cash_filter_v1", 1.0 if exp_id in {"crypto_spot_tsmom_top1_cash_filter_v1", "crypto_spot_equal_weight_200d_filter_v1"} else 0.0)),
                "btc_selection_frequency": float(selected.get("BTC-USD", math.nan)),
                "eth_selection_frequency": float(selected.get("ETH-USD", math.nan)),
                "btc_allocation_share": float(exposure.get("BTC-USD", 0.0)),
                "eth_allocation_share": float(exposure.get("ETH-USD", 0.0)),
                "crypto_spot_allocation_share": crypto_share,
                "bil_cash_allocation_share": float(exposure.get("BIL", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", math.nan)),
                "bil_allocation_share": float(exposure.get("BIL", 0.0)),
                "max_crypto_exposure": crypto_share,
                "max_single_crypto_allocation": max_crypto,
            }
        )
        return diagnostics
    if exp_id in GLOBAL_MULTI_ASSET_BATCH1_IDS and model is not None:
        assets = [*GLOBAL_MULTI_ASSET_SYMBOLS, "BIL"]
        exposure = average_asset_exposure(model, assets)
        selected = (
            model.weights.reindex(columns=assets, fill_value=0.0).fillna(0.0).gt(0.0).mean(axis=0)
            if model.kind == "weighted" and model.weights is not None and not model.weights.empty
            else pd.Series(math.nan, index=assets)
        )
        sleeve_weights = model.sleeve_weights or {}
        equity_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in ["SPY", "QQQ", "IWM", "EFA", "EEM"]))
        international_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in ["EFA", "EEM"]))
        duration_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in ["IEF", "TLT"]))
        real_asset_share = float(sum(float(exposure.get(symbol, 0.0)) for symbol in ["GLD", "PDBC", "COMT"]))
        max_asset_share = float(exposure.reindex(GLOBAL_MULTI_ASSET_SYMBOLS).fillna(0.0).max())
        rule_type = {
            "global_multi_asset_tsmom_top2_v1": "top2_positive_126d_return",
            "global_multi_asset_tsmom_top2_defensive_50_v1": "fixed_half_global_multi_asset_half_bil",
            "combo_plus_global_multi_asset_80_20_v1": "fixed_combo_80_global_multi_asset_20",
        }.get(exp_id, "")
        diagnostics.update(
            {
                "global_multi_asset_required_label": GLOBAL_MULTI_ASSET_REQUIRED_LABEL,
                "global_multi_asset_wrapper_warning": True,
                "global_multi_asset_batch_warning": True,
                "global_multi_asset_rule_type": rule_type,
                "component_combo_allocation_share": float(sleeve_weights.get("combo_SPY200d_GLD_50_50_v1", 0.0)),
                "component_global_multi_asset_allocation_share": float(sleeve_weights.get("global_multi_asset_tsmom_top2_v1", 1.0 if exp_id == "global_multi_asset_tsmom_top2_v1" else 0.0)),
                "component_bil_allocation_share": float(sleeve_weights.get("BIL_cash_proxy", 0.0)),
                "global_spy_selection_frequency": float(selected.get("SPY", math.nan)),
                "global_qqq_selection_frequency": float(selected.get("QQQ", math.nan)),
                "global_iwm_selection_frequency": float(selected.get("IWM", math.nan)),
                "global_efa_selection_frequency": float(selected.get("EFA", math.nan)),
                "global_eem_selection_frequency": float(selected.get("EEM", math.nan)),
                "global_ief_selection_frequency": float(selected.get("IEF", math.nan)),
                "global_tlt_selection_frequency": float(selected.get("TLT", math.nan)),
                "global_gld_selection_frequency": float(selected.get("GLD", math.nan)),
                "global_pdbc_selection_frequency": float(selected.get("PDBC", math.nan)),
                "global_comt_selection_frequency": float(selected.get("COMT", math.nan)),
                "global_bil_allocation_frequency": float(selected.get("BIL", math.nan)),
                "global_spy_allocation_share": float(exposure.get("SPY", 0.0)),
                "global_qqq_allocation_share": float(exposure.get("QQQ", 0.0)),
                "global_iwm_allocation_share": float(exposure.get("IWM", 0.0)),
                "global_efa_allocation_share": float(exposure.get("EFA", 0.0)),
                "global_eem_allocation_share": float(exposure.get("EEM", 0.0)),
                "global_ief_allocation_share": float(exposure.get("IEF", 0.0)),
                "global_tlt_allocation_share": float(exposure.get("TLT", 0.0)),
                "global_gld_allocation_share": float(exposure.get("GLD", 0.0)),
                "global_pdbc_allocation_share": float(exposure.get("PDBC", 0.0)),
                "global_comt_allocation_share": float(exposure.get("COMT", 0.0)),
                "global_bil_allocation_share": float(exposure.get("BIL", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", math.nan)),
                "bil_allocation_share": float(exposure.get("BIL", 0.0)),
                "global_equity_allocation_share": equity_share,
                "global_international_allocation_share": international_share,
                "global_duration_allocation_share": duration_share,
                "global_real_asset_allocation_share": real_asset_share,
                "max_single_global_asset_allocation": max_asset_share,
                "global_equity_beta_duplicate_warning": bool(equity_share > 0.60),
                "global_wrapper_concentration_warning": bool(pd.notna(max_asset_share) and max_asset_share > 0.60),
            }
        )
        return diagnostics
    if model is None or model.weights is None or model.weights.empty:
        return diagnostics
    if exp_id == VALUE_MOMENTUM_EXPERIMENT_ID:
        weights = model.weights.reindex(columns=["MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"], fill_value=0.0).fillna(0.0).clip(0.0, 1.0)
        share = weights.mean(axis=0)
        selected = weights.gt(0.0).mean(axis=0)
        equity_share = float(share.get("MTUM", 0.0) + share.get("VTV", 0.0) + share.get("QUAL", 0.0) + share.get("USMV", 0.0) + share.get("SPY", 0.0))
        cash_share = float(share.get("BIL", 0.0))
        max_share = float(share.max()) if not share.empty else math.nan
        diagnostics.update(
            {
                "mtum_selection_frequency": float(selected.get("MTUM", 0.0)),
                "vtv_selection_frequency": float(selected.get("VTV", 0.0)),
                "qual_selection_frequency": float(selected.get("QUAL", 0.0)),
                "usmv_selection_frequency": float(selected.get("USMV", 0.0)),
                "spy_selection_frequency": float(selected.get("SPY", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", 0.0)),
                "mtum_allocation_share": float(share.get("MTUM", 0.0)),
                "vtv_allocation_share": float(share.get("VTV", 0.0)),
                "qual_allocation_share": float(share.get("QUAL", 0.0)),
                "usmv_allocation_share": float(share.get("USMV", 0.0)),
                "spy_allocation_share": float(share.get("SPY", 0.0)),
                "bil_allocation_share": cash_share,
                "max_single_etf_allocation": max_share,
                "equity_factor_allocation_share": equity_share,
                "cash_treasury_allocation_share": cash_share,
                "concentration_warning": bool(pd.notna(max_share) and max_share > 0.60),
                "equity_beta_duplicate_warning": bool(equity_share > 0.60),
            }
        )
        return diagnostics
    if exp_id == SECTOR_TOP2_EXPERIMENT_ID:
        columns = [*SECTOR_TOP2_SYMBOLS, "BIL"]
        weights = model.weights.reindex(columns=columns, fill_value=0.0).fillna(0.0).clip(0.0, 1.0)
        share = weights.mean(axis=0)
        selected = weights.gt(0.0).mean(axis=0)
        sector_share = float(sum(float(share.get(symbol, 0.0)) for symbol in SECTOR_TOP2_SYMBOLS))
        cash_share = float(share.get("BIL", 0.0))
        sector_only_share = share.reindex(SECTOR_TOP2_SYMBOLS).fillna(0.0)
        max_sector_share = float(sector_only_share.max()) if not sector_only_share.empty else math.nan
        turnover = float(weights.diff().abs().sum(axis=1).fillna(0.0).mean()) if len(weights) else math.nan
        diagnostics.update(
            {
                "xlb_selection_frequency": float(selected.get("XLB", 0.0)),
                "xle_selection_frequency": float(selected.get("XLE", 0.0)),
                "xlf_selection_frequency": float(selected.get("XLF", 0.0)),
                "xli_selection_frequency": float(selected.get("XLI", 0.0)),
                "xlk_selection_frequency": float(selected.get("XLK", 0.0)),
                "xlp_selection_frequency": float(selected.get("XLP", 0.0)),
                "xlu_selection_frequency": float(selected.get("XLU", 0.0)),
                "xlv_selection_frequency": float(selected.get("XLV", 0.0)),
                "xly_selection_frequency": float(selected.get("XLY", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", 0.0)),
                "xlb_allocation_share": float(share.get("XLB", 0.0)),
                "xle_allocation_share": float(share.get("XLE", 0.0)),
                "xlf_allocation_share": float(share.get("XLF", 0.0)),
                "xli_allocation_share": float(share.get("XLI", 0.0)),
                "xlk_allocation_share": float(share.get("XLK", 0.0)),
                "xlp_allocation_share": float(share.get("XLP", 0.0)),
                "xlu_allocation_share": float(share.get("XLU", 0.0)),
                "xlv_allocation_share": float(share.get("XLV", 0.0)),
                "xly_allocation_share": float(share.get("XLY", 0.0)),
                "bil_allocation_share": cash_share,
                "equity_sector_allocation_share": sector_share,
                "cash_treasury_allocation_share": cash_share,
                "max_single_sector_allocation": max_sector_share,
                "top_sector_dominance": max_sector_share,
                "sector_turnover": turnover,
                "concentration_warning": bool(pd.notna(max_sector_share) and max_sector_share > 0.60),
                "equity_beta_duplicate_warning": bool(sector_share > 0.60),
            }
        )
        return diagnostics
    if exp_id == MANAGED_FUTURES_EXPERIMENT_ID:
        weights = model.weights.reindex(columns=[*MANAGED_FUTURES_SYMBOLS, "BIL"], fill_value=0.0).fillna(0.0).clip(0.0, 1.0)
        share = weights.mean(axis=0)
        selected = weights.gt(0.0).mean(axis=0)
        max_proxy_share = float(share.reindex(MANAGED_FUTURES_SYMBOLS).fillna(0.0).max())
        diagnostics.update(
            {
                "required_label": MANAGED_FUTURES_REQUIRED_LABEL,
                "wrapper_proxy_warning": True,
                "short_history_warning": True,
                "dbmf_selection_frequency": float(selected.get("DBMF", 0.0)),
                "kmlm_selection_frequency": float(selected.get("KMLM", 0.0)),
                "bil_allocation_frequency": float(selected.get("BIL", 0.0)),
                "dbmf_allocation_share": float(share.get("DBMF", 0.0)),
                "kmlm_allocation_share": float(share.get("KMLM", 0.0)),
                "bil_allocation_share": float(share.get("BIL", 0.0)),
                "max_single_proxy_allocation": max_proxy_share,
                "proxy_concentration_warning": bool(pd.notna(max_proxy_share) and max_proxy_share > 0.60),
                "too_slow_warning": False,
                "wrapper_proxy_only_warning": True,
                "direct_futures_claim_disallowed": True,
                "equity_beta_duplicate_warning": False,
            }
        )
        return diagnostics
    if exp_id != QQQ_EXPERIMENT_ID:
        return diagnostics
    weights = model.weights.reindex(columns=["QQQ", "SPY", "GLD", "IEF", "BIL"], fill_value=0.0).fillna(0.0).clip(0.0, 1.0)
    share = weights.mean(axis=0)
    selected = weights.gt(0.0).mean(axis=0)
    equity_share = float(share.get("QQQ", 0.0) + share.get("SPY", 0.0))
    defensive_share = float(share.get("GLD", 0.0) + share.get("IEF", 0.0) + share.get("BIL", 0.0))
    max_share = float(share.max()) if not share.empty else math.nan
    diagnostics.update(
        {
            "qqq_selection_frequency": float(selected.get("QQQ", 0.0)),
            "spy_selection_frequency": float(selected.get("SPY", 0.0)),
            "gld_selection_frequency": float(selected.get("GLD", 0.0)),
            "ief_selection_frequency": float(selected.get("IEF", 0.0)),
            "bil_allocation_frequency": float(selected.get("BIL", 0.0)),
            "max_single_asset_allocation": max_share,
            "qqq_allocation_share": float(share.get("QQQ", 0.0)),
            "equity_asset_allocation_share": equity_share,
            "defensive_asset_allocation_share": defensive_share,
            "concentration_warning": bool(pd.notna(max_share) and max_share > 0.60),
            "equity_beta_duplicate_warning": bool(equity_share > 0.60),
        }
    )
    return diagnostics


def asset_class_tsmom_weights(prices: pd.DataFrame, selection: str, top_n: int | None = None) -> pd.DataFrame:
    universe = ["SPY", "GLD", "IEF"]
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[universe].pct_change(126, fill_method=None)
    sma = prices[universe].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        eligible = [
            symbol
            for symbol in universe
            if pd.notna(rets.at[dt, symbol])
            and rets.at[dt, symbol] > 0
            and pd.notna(sma.at[dt, symbol])
            and prices.at[dt, symbol] > sma.at[dt, symbol]
        ]
        if selection == "all":
            selected = eligible
        else:
            ranked = sorted(eligible, key=lambda symbol: float(rets.at[dt, symbol]), reverse=True)
            selected = ranked[: int(top_n or 1)]
        if selected:
            weight = 1.0 / len(selected)
            for symbol in selected:
                decision.at[dt, symbol] = weight
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def top2_momentum_weights(prices: pd.DataFrame) -> pd.DataFrame:
    universe = ["SPY", "GLD", "IEF"]
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[universe].pct_change(126, fill_method=None)
    sma = prices[universe].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        selected: list[str] = []
        for symbol in rets.loc[dt].sort_values(ascending=False).index:
            if len(selected) >= 2:
                break
            if pd.notna(rets.at[dt, symbol]) and rets.at[dt, symbol] > 0 and prices.at[dt, symbol] > sma.at[dt, symbol]:
                selected.append(str(symbol))
        if selected:
            for symbol in selected:
                decision.at[dt, symbol] = 0.5
            if len(selected) == 1 and "BIL" in decision:
                decision.at[dt, "BIL"] = 0.5
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def gld_spy_rotation_weights(prices: pd.DataFrame) -> pd.DataFrame:
    decision = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    rets = prices[["GLD", "SPY"]].pct_change(126, fill_method=None)
    sma = prices[["GLD", "SPY"]].rolling(200, min_periods=200).mean()
    for dt in prices.index:
        if pd.isna(rets.at[dt, "GLD"]) or pd.isna(rets.at[dt, "SPY"]):
            if "BIL" in decision:
                decision.at[dt, "BIL"] = 1.0
            continue
        selected = "GLD" if rets.at[dt, "GLD"] > rets.at[dt, "SPY"] else "SPY"
        if prices.at[dt, selected] > sma.at[dt, selected]:
            decision.at[dt, selected] = 1.0
        elif "BIL" in decision:
            decision.at[dt, "BIL"] = 1.0
    return monthly_signal_weights(prices, decision)


def simulate_weighted(prices: pd.DataFrame, weights: pd.DataFrame, cost: float) -> pd.DataFrame:
    aligned = prices.reindex(index=weights.index, columns=weights.columns).ffill()
    returns = aligned.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    prev_equity = STARTING_EQUITY
    prev_weights = pd.Series(0.0, index=weights.columns)
    equities: list[float] = []
    for dt in weights.index:
        current = weights.loc[dt].fillna(0.0).clip(0.0, 1.0)
        total = float(current.sum())
        if total > 1.0:
            current = current / total
        turnover = float((current - prev_weights).abs().sum())
        equity = max(0.0, prev_equity * (1.0 + float((current * returns.loc[dt]).sum())) - prev_equity * turnover * cost)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    return pd.DataFrame({"date": weights.index, "equity": equities})


def sleeve_return_stream(prices: pd.DataFrame, weights: pd.DataFrame, cost: float) -> pd.Series:
    curve = simulate_weighted(prices, weights, cost)
    return curve.set_index("date")["equity"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def combo_curve(prices: pd.DataFrame, sleeve_returns: pd.DataFrame, sleeve_weights: dict[str, float], cost: float) -> pd.DataFrame:
    cols = sorted(sleeve_weights)
    targets = pd.DataFrame(0.0, index=prices.index, columns=cols)
    month = pd.Series(pd.to_datetime(prices.index).to_period("M"), index=prices.index)
    rebalance = month.ne(month.shift(1))
    for sleeve, weight in sleeve_weights.items():
        targets.loc[rebalance, sleeve] = float(weight)
    targets = targets.replace(0.0, np.nan).ffill().fillna(0.0)
    returns = sleeve_returns.reindex(index=prices.index, columns=cols).fillna(0.0)
    prev_equity = STARTING_EQUITY
    prev_weights = pd.Series(0.0, index=cols)
    equities: list[float] = []
    for dt in prices.index:
        current = targets.loc[dt].fillna(0.0).clip(0.0, 1.0)
        turnover = float((current - prev_weights).abs().sum())
        equity = max(0.0, prev_equity * (1.0 + float((current * returns.loc[dt]).sum())) - prev_equity * turnover * cost)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    return pd.DataFrame({"date": prices.index, "equity": equities})


def normalize_weights(row: pd.Series) -> pd.Series:
    current = row.fillna(0.0).clip(0.0, 1.0)
    total = float(current.sum())
    if total > 1.0:
        current = current / total
    return current


def accounting_start_check(curve: pd.DataFrame) -> dict[str, Any]:
    first_equity = float(curve["equity"].iloc[0]) if not curve.empty else math.nan
    first_high_water = STARTING_EQUITY
    target_state_start = any(first_equity >= target for target in TARGETS.values()) if pd.notna(first_equity) else True
    stop_state_start = first_equity <= ABSOLUTE_STOP or first_equity <= first_high_water - TRAILING_DRAWDOWN if pd.notna(first_equity) else True
    start_ok = pd.notna(first_equity) and abs(first_equity - STARTING_EQUITY) <= ACCOUNTING_TOLERANCE
    high_water_ok = abs(first_high_water - STARTING_EQUITY) <= ACCOUNTING_TOLERANCE
    return {
        "starting_equity_used": STARTING_EQUITY,
        "first_equity_value": first_equity,
        "first_high_water_mark": first_high_water,
        "first_stop_state": bool(stop_state_start),
        "first_target_state": bool(target_state_start),
        "window_rebased_correctly": bool(start_ok and high_water_ok and not target_state_start and not stop_state_start),
        "integrity_error": "" if start_ok and high_water_ok and not target_state_start and not stop_state_start else "rolling window did not reset equity/high-water/target/stop state",
    }


def simulate_weighted_window(model: ExperimentModel, start_idx: int, horizon: int, cost: float) -> dict[str, Any]:
    if model.weights is None:
        raise ValueError(f"{model.experiment_id} missing weights.")
    prices = model.prices.iloc[start_idx : start_idx + horizon].copy()
    weights = model.weights.reindex(index=prices.index, columns=model.prices.columns).fillna(0.0)
    asset_returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if prices.empty:
        return {"curve": pd.DataFrame(columns=["date", "equity"]), "daily_returns": pd.Series(dtype=float), "accounting": {"integrity_error": "empty window"}}
    prev_equity = STARTING_EQUITY
    prev_weights = normalize_weights(weights.iloc[0])
    equities = [STARTING_EQUITY]
    daily_returns = [0.0]
    for pos in range(1, len(prices)):
        current = normalize_weights(weights.iloc[pos])
        turnover = float((current - prev_weights).abs().sum())
        gross_return = float((current * asset_returns.iloc[pos]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross_return) - prev_equity * turnover * cost)
        daily_returns.append(0.0 if prev_equity <= 0 else equity / prev_equity - 1.0)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    curve = pd.DataFrame({"date": prices.index, "equity": equities})
    accounting = accounting_start_check(curve)
    return {
        "curve": curve,
        "daily_returns": pd.Series(daily_returns, index=prices.index),
        "accounting": accounting,
        "reference": buy_hold_reference_check(model, curve, prices),
        "combination_check_passed": True,
        "combination_error_count": 0,
    }


def combo_target_weights(index: pd.Index, sleeve_weights: dict[str, float]) -> pd.DataFrame:
    cols = sorted(sleeve_weights)
    targets = pd.DataFrame(0.0, index=index, columns=cols)
    month = pd.Series(pd.to_datetime(index).to_period("M"), index=index)
    rebalance = month.ne(month.shift(1))
    for sleeve, weight in sleeve_weights.items():
        targets.loc[rebalance, sleeve] = float(weight)
    targets = targets.replace(0.0, np.nan).ffill().fillna(0.0)
    if not targets.empty:
        first = pd.Series({sleeve: float(weight) for sleeve, weight in sleeve_weights.items()})
        targets.loc[targets.index[0], first.index] = first
        targets = targets.ffill().fillna(0.0)
    return targets


def simulate_combo_window(model: ExperimentModel, start_idx: int, horizon: int, cost: float) -> dict[str, Any]:
    if not model.sleeve_models or not model.sleeve_weights:
        raise ValueError(f"{model.experiment_id} missing sleeve models.")
    index = model.prices.iloc[start_idx : start_idx + horizon].index
    if len(index) == 0:
        return {"curve": pd.DataFrame(columns=["date", "equity"]), "daily_returns": pd.Series(dtype=float), "accounting": {"integrity_error": "empty window"}}
    sleeve_returns = pd.DataFrame(index=index)
    for sleeve, sleeve_model in model.sleeve_models.items():
        sleeve_run = simulate_model_window(sleeve_model, start_idx, horizon, cost)
        sleeve_returns[sleeve] = sleeve_run["daily_returns"].reindex(index).fillna(0.0)
    targets = combo_target_weights(index, model.sleeve_weights)
    prev_equity = STARTING_EQUITY
    prev_weights = normalize_weights(targets.iloc[0])
    equities = [STARTING_EQUITY]
    daily_returns = [0.0]
    bound_violations = 0
    for pos in range(1, len(index)):
        current = normalize_weights(targets.iloc[pos])
        turnover = float((current - prev_weights).abs().sum())
        component_row = sleeve_returns.iloc[pos].reindex(current.index).astype(float)
        gross_return = float((current * component_row).sum())
        active = component_row[current > 0]
        if not active.empty and (gross_return > float(active.max()) + REFERENCE_TOLERANCE or gross_return < float(active.min()) - REFERENCE_TOLERANCE):
            bound_violations += 1
        equity = max(0.0, prev_equity * (1.0 + gross_return) - prev_equity * turnover * cost)
        daily_returns.append(0.0 if prev_equity <= 0 else equity / prev_equity - 1.0)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    curve = pd.DataFrame({"date": index, "equity": equities})
    accounting = accounting_start_check(curve)
    return {
        "curve": curve,
        "daily_returns": pd.Series(daily_returns, index=index),
        "accounting": accounting,
        "reference": {
            "reference_check_available": False,
            "reference_median_abs_error": math.nan,
            "reference_max_abs_error": math.nan,
            "reference_error_status": "not_applicable",
        },
        "combination_check_passed": bound_violations == 0,
        "combination_error_count": bound_violations,
    }


def buy_hold_reference_check(model: ExperimentModel, curve: pd.DataFrame, prices: pd.DataFrame) -> dict[str, Any]:
    if not model.reference_symbol:
        return {
            "reference_check_available": False,
            "reference_median_abs_error": math.nan,
            "reference_max_abs_error": math.nan,
            "reference_error_status": "not_applicable",
        }
    symbol = model.reference_symbol
    if symbol not in prices or prices.empty or pd.isna(prices[symbol].iloc[0]) or prices[symbol].iloc[0] == 0:
        return {
            "reference_check_available": False,
            "reference_median_abs_error": math.nan,
            "reference_max_abs_error": math.nan,
            "reference_error_status": "unavailable_missing_reference_prices",
        }
    reference = STARTING_EQUITY * prices[symbol].astype(float) / float(prices[symbol].iloc[0])
    errors = pd.Series(curve["equity"].astype(float).to_numpy() - reference.to_numpy()).abs()
    median_error = float(pd.Series(errors).median())
    max_error = float(pd.Series(errors).max())
    return {
        "reference_check_available": True,
        "reference_median_abs_error": median_error,
        "reference_max_abs_error": max_error,
        "reference_error_status": "passed" if max_error <= REFERENCE_TOLERANCE else "failed",
    }


def simulate_model_window(model: ExperimentModel, start_idx: int, horizon: int, cost: float) -> dict[str, Any]:
    if model.kind == "weighted":
        return simulate_weighted_window(model, start_idx, horizon, cost)
    if model.kind == "combo":
        return simulate_combo_window(model, start_idx, horizon, cost)
    raise ValueError(f"Unknown model kind {model.kind}.")


def curve_for_model(model: ExperimentModel, cost: float) -> pd.DataFrame:
    return simulate_model_window(model, 0, len(model.prices), cost)["curve"]


def model_for_experiment(spec: dict[str, Any], prices: pd.DataFrame) -> ExperimentModel:
    experiment_id = str(spec["experiment_id"])
    if experiment_id == "SPY_200d_trend_model":
        return ExperimentModel(experiment_id, "weighted", prices, trend_200d_weights(prices, "SPY"), "computed from cached adjusted SPY/BIL prices")
    if experiment_id == "SPY_buy_hold":
        return ExperimentModel(experiment_id, "weighted", prices, buy_hold_weights(prices, "SPY"), "computed from cached adjusted SPY prices", "SPY")
    if experiment_id == "GLD_buy_hold":
        return ExperimentModel(experiment_id, "weighted", prices, buy_hold_weights(prices, "GLD"), "computed from cached adjusted GLD prices", "GLD")
    if experiment_id == "IEF_buy_hold":
        return ExperimentModel(experiment_id, "weighted", prices, buy_hold_weights(prices, "IEF"), "computed from cached adjusted IEF prices", "IEF")
    if experiment_id == "BIL_cash_proxy":
        return ExperimentModel(experiment_id, "weighted", prices, buy_hold_weights(prices, "BIL"), "computed from cached adjusted BIL prices", "BIL")
    if experiment_id == "GLD_200d_trend_model_v1":
        return ExperimentModel(experiment_id, "weighted", prices, trend_200d_weights(prices, "GLD"), "predeclared GLD 200-day trend model")
    if experiment_id == "asset_class_tsmom_equal_weight_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            asset_class_tsmom_weights(prices, "all"),
            "predeclared asset-class TSMOM equal-weight eligible SPY/GLD/IEF with BIL fallback",
        )
    if experiment_id == "asset_class_tsmom_top1_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            asset_class_tsmom_weights(prices, "top", top_n=1),
            "predeclared asset-class TSMOM top-1 SPY/GLD/IEF with BIL fallback",
        )
    if experiment_id == "asset_class_tsmom_top2_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            asset_class_tsmom_weights(prices, "top", top_n=2),
            "predeclared asset-class TSMOM top-2 SPY/GLD/IEF with BIL fallback",
        )
    if experiment_id == QQQ_EXPERIMENT_ID:
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            qqq_dual_momentum_weights(prices),
            "predeclared QQQ/SPY/GLD/IEF dual momentum top-1 with BIL fallback; cache-only research_sample row",
        )
    if experiment_id == VALUE_MOMENTUM_EXPERIMENT_ID:
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            value_momentum_factor_rotation_weights(prices),
            "predeclared value/momentum factor ETF top-2 rotation Option A with BIL fallback; cache-only research_sample row",
        )
    if experiment_id == SECTOR_TOP2_EXPERIMENT_ID:
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            sector_top2_momentum_weights(prices),
            "predeclared core-nine sector top-2 momentum with BIL fallback; XLC/XLRE excluded; cache-only research_sample row",
        )
    if experiment_id == MANAGED_FUTURES_EXPERIMENT_ID:
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            managed_futures_proxy_weights(prices),
            "predeclared DBMF/KMLM managed-futures fund-wrapper proxy trend rule with BIL fallback; short-history cache-only research_sample row",
        )
    if experiment_id == COMMODITY_EXPLORATORY_EXPERIMENT_ID:
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            commodity_basket_tsmom_top2_weights(prices),
            "predeclared commodity wrapper top-2 126-day return rule with BIL fallback; yfinance-compatible exploratory public data; research_sample only",
        )
    if experiment_id == "commodity_basket_tsmom_top2_200d_filter_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            commodity_basket_tsmom_top2_200d_filter_weights(prices),
            "predeclared commodity risk-control top-2 rule with 126-day positive return and 200-day SMA filters; research_sample only",
        )
    if experiment_id == "commodity_basket_tsmom_top2_half_bil_v1":
        sleeve_models = {
            COMMODITY_EXPLORATORY_EXPERIMENT_ID: model_for_experiment({"experiment_id": COMMODITY_EXPLORATORY_EXPERIMENT_ID}, prices),
            "BIL_cash_proxy": ExperimentModel("BIL_cash_proxy", "weighted", prices, buy_hold_weights(prices, "BIL"), "commodity half-BIL sleeve", "BIL"),
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            prices,
            note="predeclared commodity risk-control fixed 50% base commodity sleeve / 50% BIL blend; research_sample only",
            sleeve_models=sleeve_models,
            sleeve_weights={COMMODITY_EXPLORATORY_EXPERIMENT_ID: 0.50, "BIL_cash_proxy": 0.50},
        )
    if experiment_id == "combo_plus_commodity_basket_80_20_v1":
        sleeve_models = {
            "combo_SPY200d_GLD_50_50_v1": model_for_experiment({"experiment_id": "combo_SPY200d_GLD_50_50_v1"}, prices),
            COMMODITY_EXPLORATORY_EXPERIMENT_ID: model_for_experiment({"experiment_id": COMMODITY_EXPLORATORY_EXPERIMENT_ID}, prices),
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            prices,
            note="predeclared historical-only fixed 80% active combo component / 20% base commodity sleeve blend; research_sample only",
            sleeve_models=sleeve_models,
            sleeve_weights={"combo_SPY200d_GLD_50_50_v1": 0.80, COMMODITY_EXPLORATORY_EXPERIMENT_ID: 0.20},
        )
    if experiment_id == "global_multi_asset_tsmom_top2_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            global_multi_asset_tsmom_top2_weights(prices),
            "predeclared global multi-asset ETF/fund wrapper top-2 126-day return rule with BIL fallback; yfinance-compatible exploratory public data; research_sample only",
        )
    if experiment_id == "global_multi_asset_tsmom_top2_defensive_50_v1":
        sleeve_models = {
            "global_multi_asset_tsmom_top2_v1": model_for_experiment({"experiment_id": "global_multi_asset_tsmom_top2_v1"}, prices),
            "BIL_cash_proxy": ExperimentModel("BIL_cash_proxy", "weighted", prices, buy_hold_weights(prices, "BIL"), "global multi-asset defensive BIL sleeve", "BIL"),
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            prices,
            note="predeclared global multi-asset fixed 50% rotation sleeve / 50% BIL blend; research_sample only",
            sleeve_models=sleeve_models,
            sleeve_weights={"global_multi_asset_tsmom_top2_v1": 0.50, "BIL_cash_proxy": 0.50},
        )
    if experiment_id == "combo_plus_global_multi_asset_80_20_v1":
        sleeve_models = {
            "combo_SPY200d_GLD_50_50_v1": model_for_experiment({"experiment_id": "combo_SPY200d_GLD_50_50_v1"}, prices),
            "global_multi_asset_tsmom_top2_v1": model_for_experiment({"experiment_id": "global_multi_asset_tsmom_top2_v1"}, prices),
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            prices,
            note="predeclared historical-only fixed 80% active combo component / 20% global multi-asset sleeve blend; research_sample only",
            sleeve_models=sleeve_models,
            sleeve_weights={"combo_SPY200d_GLD_50_50_v1": 0.80, "global_multi_asset_tsmom_top2_v1": 0.20},
        )
    if experiment_id == "crypto_spot_tsmom_top1_cash_filter_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            crypto_spot_tsmom_top1_cash_filter_weights(prices),
            "predeclared crypto spot Tier 2 top-1 BTC/ETH trend rule with 50% BIL cash sleeve; research_sample only",
        )
    if experiment_id == "crypto_spot_equal_weight_200d_filter_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            crypto_spot_equal_weight_200d_filter_weights(prices),
            "predeclared crypto spot Tier 2 BTC/ETH equal-weight 200d filter with max 50% crypto exposure; research_sample only",
        )
    if experiment_id == "combo_plus_crypto_spot_tsmom_90_10_v1":
        sleeve_models = {
            "combo_SPY200d_GLD_50_50_v1": model_for_experiment({"experiment_id": "combo_SPY200d_GLD_50_50_v1"}, prices),
            "crypto_spot_tsmom_top1_cash_filter_v1": model_for_experiment({"experiment_id": "crypto_spot_tsmom_top1_cash_filter_v1"}, prices),
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            prices,
            note="predeclared historical-only fixed 90% active combo component / 10% crypto spot top-1 cash-filter sleeve; research_sample only",
            sleeve_models=sleeve_models,
            sleeve_weights={"combo_SPY200d_GLD_50_50_v1": 0.90, "crypto_spot_tsmom_top1_cash_filter_v1": 0.10},
        )
    if experiment_id == "dual_momentum_SPY_GLD_IEF_v1":
        return ExperimentModel(
            experiment_id,
            "weighted",
            prices,
            asset_class_tsmom_weights(prices, "top", top_n=1),
            "duplicate canonical rule of asset_class_tsmom_top1_v1",
        )
    if experiment_id == "IEF_200d_trend_model_v1":
        return ExperimentModel(experiment_id, "weighted", prices, trend_200d_weights(prices, "IEF"), "predeclared IEF 200-day trend model")
    if experiment_id == "SPY_GLD_dual_momentum_v1":
        return ExperimentModel(experiment_id, "weighted", prices, dual_momentum_weights(prices, ["SPY", "GLD"]), "predeclared SPY/GLD dual momentum")
    if experiment_id == "SPY_GLD_IEF_dual_momentum_v1":
        return ExperimentModel(experiment_id, "weighted", prices, dual_momentum_weights(prices, ["SPY", "GLD", "IEF"]), "predeclared SPY/GLD/IEF dual momentum")
    if experiment_id == "multi_asset_top2_momentum_v1":
        return ExperimentModel(experiment_id, "weighted", prices, top2_momentum_weights(prices), "predeclared multi-asset top-2 momentum")
    if experiment_id == "GLD_SPY_rotation_v1":
        return ExperimentModel(experiment_id, "weighted", prices, gld_spy_rotation_weights(prices), "predeclared GLD/SPY rotation")
    if experiment_id in COMBINATION_BATCH1_IDS:
        combination_prices = (
            restrict_prices_to_common_history(prices, [*MANAGED_FUTURES_SYMBOLS, "BIL"])
            if experiment_id in COMBINATION_BATCH1_MANAGED_FUTURES_IDS
            else prices
        )
        definition = COMBINATION_BATCH1_DEFINITIONS[experiment_id]
        sleeve_models = {
            component_id: model_for_experiment({"experiment_id": component_id}, combination_prices)
            for component_id in definition["components"]
        }
        return ExperimentModel(
            experiment_id,
            "combo",
            combination_prices,
            note=(
                "historical combination batch 1 fixed monthly sleeve blend using exact window-local component returns; "
                "research_sample only; no optimized weights"
            ),
            sleeve_models=sleeve_models,
            sleeve_weights=definition["weights"],
        )
    if experiment_id in {"combo_SPY200d_GLD_50_50_v1", "combo_SPY200d_GLD_BIL_60_30_10_v1"}:
        sleeve_models = {
            "SPY_200d_trend_model": ExperimentModel("SPY_200d_trend_model", "weighted", prices, trend_200d_weights(prices, "SPY"), "combo sleeve SPY 200d"),
            "GLD_buy_hold": ExperimentModel("GLD_buy_hold", "weighted", prices, buy_hold_weights(prices, "GLD"), "combo sleeve GLD buy hold", "GLD"),
            "BIL_cash_proxy": ExperimentModel("BIL_cash_proxy", "weighted", prices, buy_hold_weights(prices, "BIL"), "combo sleeve BIL cash proxy", "BIL"),
        }
        weights = (
            {"SPY_200d_trend_model": 0.5, "GLD_buy_hold": 0.5}
            if experiment_id == "combo_SPY200d_GLD_50_50_v1"
            else {"SPY_200d_trend_model": 0.6, "GLD_buy_hold": 0.3, "BIL_cash_proxy": 0.1}
        )
        return ExperimentModel(experiment_id, "combo", prices, note="predeclared fixed monthly combination account using window-local sleeve returns", sleeve_models=sleeve_models, sleeve_weights=weights)
    raise KeyError(f"No runnable exact ETF implementation for {experiment_id}")


def equity_for_experiment(spec: dict[str, Any], prices: pd.DataFrame, cost: float) -> tuple[pd.DataFrame, str]:
    model = model_for_experiment(spec, prices)
    return curve_for_model(model, cost), model.note


def legacy_equity_for_experiment(spec: dict[str, Any], prices: pd.DataFrame, cost: float) -> tuple[pd.DataFrame, str]:
    experiment_id = str(spec["experiment_id"])
    if experiment_id == "SPY_200d_trend_model":
        return simulate_weighted(prices, trend_200d_weights(prices, "SPY"), cost), "computed from cached adjusted SPY/BIL prices"
    if experiment_id == "SPY_buy_hold":
        return simulate_weighted(prices, buy_hold_weights(prices, "SPY"), cost), "computed from cached adjusted SPY prices"
    if experiment_id == "GLD_buy_hold":
        return simulate_weighted(prices, buy_hold_weights(prices, "GLD"), cost), "computed from cached adjusted GLD prices"
    if experiment_id == "IEF_buy_hold":
        return simulate_weighted(prices, buy_hold_weights(prices, "IEF"), cost), "computed from cached adjusted IEF prices"
    if experiment_id == "BIL_cash_proxy":
        return simulate_weighted(prices, buy_hold_weights(prices, "BIL"), cost), "computed from cached adjusted BIL prices"
    if experiment_id == "GLD_200d_trend_model_v1":
        return simulate_weighted(prices, trend_200d_weights(prices, "GLD"), cost), "predeclared GLD 200-day trend model"
    if experiment_id == "IEF_200d_trend_model_v1":
        return simulate_weighted(prices, trend_200d_weights(prices, "IEF"), cost), "predeclared IEF 200-day trend model"
    if experiment_id == "SPY_GLD_dual_momentum_v1":
        return simulate_weighted(prices, dual_momentum_weights(prices, ["SPY", "GLD"]), cost), "predeclared SPY/GLD dual momentum"
    if experiment_id == "SPY_GLD_IEF_dual_momentum_v1":
        return simulate_weighted(prices, dual_momentum_weights(prices, ["SPY", "GLD", "IEF"]), cost), "predeclared SPY/GLD/IEF dual momentum"
    if experiment_id == "multi_asset_top2_momentum_v1":
        return simulate_weighted(prices, top2_momentum_weights(prices), cost), "predeclared multi-asset top-2 momentum"
    if experiment_id == "GLD_SPY_rotation_v1":
        return simulate_weighted(prices, gld_spy_rotation_weights(prices), cost), "predeclared GLD/SPY rotation"
    if experiment_id in {"combo_SPY200d_GLD_50_50_v1", "combo_SPY200d_GLD_BIL_60_30_10_v1"}:
        sleeve_returns = pd.DataFrame(index=prices.index)
        sleeve_returns["SPY_200d_trend_model"] = sleeve_return_stream(prices, trend_200d_weights(prices, "SPY"), cost)
        sleeve_returns["GLD_buy_hold"] = sleeve_return_stream(prices, buy_hold_weights(prices, "GLD"), cost)
        sleeve_returns["BIL_cash_proxy"] = sleeve_return_stream(prices, buy_hold_weights(prices, "BIL"), cost)
        weights = (
            {"SPY_200d_trend_model": 0.5, "GLD_buy_hold": 0.5}
            if experiment_id == "combo_SPY200d_GLD_50_50_v1"
            else {"SPY_200d_trend_model": 0.6, "GLD_buy_hold": 0.3, "BIL_cash_proxy": 0.1}
        )
        return combo_curve(prices, sleeve_returns, weights, cost), "predeclared fixed monthly combination account"
    raise KeyError(f"No runnable exact ETF implementation for {experiment_id}")


def profit_audit(equity: pd.Series, dates: pd.Series | pd.Index) -> dict[str, Any]:
    series = pd.Series(equity, dtype=float).reset_index(drop=True)
    date_index = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    high_water = -math.inf
    first_stop_idx: int | None = None
    first_stop_type = ""
    max_dd = 0.0
    for idx, value in enumerate(series):
        high_water = max(high_water, float(value))
        dd = float(value) - high_water
        max_dd = min(max_dd, dd)
        absolute_hit = float(value) <= ABSOLUTE_STOP
        trailing_hit = float(value) <= high_water - TRAILING_DRAWDOWN
        if first_stop_idx is None and (absolute_hit or trailing_hit):
            first_stop_idx = idx
            first_stop_type = "absolute_floor" if absolute_hit else "trailing_drawdown"
    first_stop_date = "" if first_stop_idx is None else date_index.iloc[first_stop_idx].date().isoformat()
    stop_equity = float(series.iloc[-1]) if first_stop_idx is None else float(series.iloc[first_stop_idx])
    out: dict[str, Any] = {
        "unconditional_final_equity": float(series.iloc[-1]),
        "stop_enforced_final_equity": stop_equity,
        "total_return_unconditional": float(series.iloc[-1]) / STARTING_EQUITY - 1.0,
        "total_return_stop_enforced": stop_equity / STARTING_EQUITY - 1.0,
        "max_equity": float(series.max()),
        "min_equity": float(series.min()),
        "max_drawdown_dollars": max_dd,
        "max_drawdown_pct": abs(max_dd) / max(STARTING_EQUITY, float(series.max())),
        "any_project_stop_hit": first_stop_idx is not None,
        "first_project_stop_date": first_stop_date,
        "first_project_stop_type": first_stop_type,
    }
    for label, target in TARGETS.items():
        hit_indices = np.flatnonzero(series.to_numpy() >= target)
        if len(hit_indices):
            first_target_idx = int(hit_indices[0])
            before_stop = first_stop_idx is None or first_target_idx <= first_stop_idx
            days = first_target_idx
        else:
            before_stop = False
            days = math.nan
        out[f"target_{label}_before_stop"] = bool(before_stop)
        out[f"days_to_target_{label}"] = days
    return out


def rolling_metrics_for_model(model: ExperimentModel, horizon: int, mode: str, cost: float) -> tuple[dict[str, Any], int, str]:
    sample_size = 25 if mode == "smoke" else 40
    starts, possible_count, method = sample_etf_starts(model.prices[["SPY"]].rename(columns={"SPY": "value"}) if "SPY" in model.prices else model.prices.iloc[:, :1], horizon, mode, sample_size=sample_size)
    window_rows: list[dict[str, Any]] = []
    for idx in starts:
        simulation = simulate_model_window(model, idx, horizon, cost)
        window = simulation["curve"]
        audit = profit_audit(window["equity"], window["date"])
        accounting = simulation["accounting"]
        reference = simulation.get("reference", {})
        window_rows.append(
            {
                **{f"target_{label}_before_stop": audit[f"target_{label}_before_stop"] for label in TARGETS},
                "any_project_stop_hit": audit["any_project_stop_hit"],
                "unconditional_final_equity": audit["unconditional_final_equity"],
                "stop_enforced_final_equity": audit["stop_enforced_final_equity"],
                "max_drawdown_dollars": audit["max_drawdown_dollars"],
                "window_start_equity": accounting.get("first_equity_value", math.nan),
                "first_high_water_mark": accounting.get("first_high_water_mark", math.nan),
                "window_start_equity_violation": abs(float(accounting.get("first_equity_value", math.nan)) - STARTING_EQUITY) > ACCOUNTING_TOLERANCE if pd.notna(accounting.get("first_equity_value", math.nan)) else True,
                "high_water_start_violation": abs(float(accounting.get("first_high_water_mark", math.nan)) - STARTING_EQUITY) > ACCOUNTING_TOLERANCE if pd.notna(accounting.get("first_high_water_mark", math.nan)) else True,
                "target_state_start_violation": bool(accounting.get("first_target_state", True)),
                "stop_state_start_violation": bool(accounting.get("first_stop_state", True)),
                "reference_check_available": bool(reference.get("reference_check_available", False)),
                "reference_median_abs_error": reference.get("reference_median_abs_error", math.nan),
                "reference_max_abs_error": reference.get("reference_max_abs_error", math.nan),
                "reference_error_status": reference.get("reference_error_status", "not_applicable"),
                "combination_check_passed": bool(simulation.get("combination_check_passed", True)),
                "combination_error_count": int(simulation.get("combination_error_count", 0)),
                "integrity_error": accounting.get("integrity_error", ""),
            }
        )
    if not window_rows:
        return {}, possible_count, method
    df = pd.DataFrame(window_rows)
    values = df["stop_enforced_final_equity"].astype(float)
    start_violations = int(df["window_start_equity_violation"].sum())
    high_water_violations = int(df["high_water_start_violation"].sum())
    target_violations = int(df["target_state_start_violation"].sum())
    stop_violations = int(df["stop_state_start_violation"].sum())
    reference_statuses = df["reference_error_status"].dropna().astype(str)
    reference_failures = int(reference_statuses.eq("failed").sum())
    combination_failures = int((~df["combination_check_passed"].astype(bool)).sum())
    status = "failed" if start_violations or high_water_violations or target_violations or stop_violations or reference_failures or combination_failures else "passed"
    return {
        "number_of_windows": int(len(df)),
        "possible_window_count": int(possible_count),
        "p_target_300_before_stop": float(df["target_300_before_stop"].mean()),
        "p_target_400_before_stop": float(df["target_400_before_stop"].mean()),
        "p_target_600_before_stop": float(df["target_600_before_stop"].mean()),
        "p_target_900_before_stop": float(df["target_900_before_stop"].mean()),
        "p_target_1200_before_stop": float(df["target_1200_before_stop"].mean()),
        "p_any_project_stop_hit": float(df["any_project_stop_hit"].mean()),
        "median_stop_enforced_final_equity": float(values.median()),
        "mean_stop_enforced_final_equity": float(values.mean()),
        "p25_stop_enforced_final_equity": float(values.quantile(0.25)),
        "p75_stop_enforced_final_equity": float(values.quantile(0.75)),
        "p90_stop_enforced_final_equity": float(values.quantile(0.90)),
        "p95_stop_enforced_final_equity": float(values.quantile(0.95)),
        "max_stop_enforced_final_equity": float(values.max()),
        "median_max_drawdown": float(df["max_drawdown_dollars"].median()),
        "worst_max_drawdown": float(df["max_drawdown_dollars"].min()),
        "expected_profit_dollars": float(values.mean() - STARTING_EQUITY),
        "expected_profit_pct": float(values.mean() / STARTING_EQUITY - 1.0),
        "window_start_equity_min": float(df["window_start_equity"].min()),
        "window_start_equity_max": float(df["window_start_equity"].max()),
        "window_start_equity_violation_count": start_violations,
        "high_water_start_violation_count": high_water_violations,
        "target_state_start_violation_count": target_violations,
        "stop_state_start_violation_count": stop_violations,
        "reference_check_available": bool(df["reference_check_available"].any()),
        "reference_median_abs_error": float(pd.to_numeric(df["reference_median_abs_error"], errors="coerce").dropna().median()) if pd.to_numeric(df["reference_median_abs_error"], errors="coerce").notna().any() else math.nan,
        "reference_max_abs_error": float(pd.to_numeric(df["reference_max_abs_error"], errors="coerce").dropna().max()) if pd.to_numeric(df["reference_max_abs_error"], errors="coerce").notna().any() else math.nan,
        "reference_error_status": "failed" if reference_failures else ("passed" if bool(df["reference_check_available"].any()) else "not_applicable"),
        "accounting_integrity_status": status,
    }, possible_count, method


def blank_result(run_id: str, spec: dict[str, Any], run_status: str, reason: str) -> dict[str, Any]:
    row = {col: math.nan for col in RESULT_COLUMNS}
    diagnostics = allocation_diagnostics(None, spec, "duplicate_skipped" if run_status == "duplicate_skipped" else "not_applicable")
    row.update(
        {
            "run_id": run_id,
            "experiment_id": spec["experiment_id"],
            "display_name": spec["display_name"],
            "experiment_type": spec["experiment_type"],
            "family_group": spec["family_group"],
            "strategy_family": spec["strategy_family"],
            "evidence_tier": spec["evidence_tier"],
            "run_status": run_status,
            "starting_equity": STARTING_EQUITY,
            "independent_account": True,
            "shared_capital": False,
            "standard_or_stress": "standard",
            "final_validation_completed": False,
            "sampled_results_are_final": False,
            "evidence_finality": run_status,
            "risk_framework_verdict": run_status,
            "profit_verdict": run_status,
            "promotion_blockers": reason,
            "notes": reason,
            "accounting_integrity_status": "not_applicable",
            "rolling_rebase_check_passed": False,
            "buy_hold_reference_check_passed": False,
            "combination_return_check_passed": False,
            "profit_results_usable": False,
            "integrity_error_count": 0,
            "integrity_notes": reason,
            "canonical_rule_hash": canonical_rule_hash(spec),
            "duplicate_of": spec.get("duplicate_of", ""),
            **diagnostics,
        }
    )
    return row


def result_row(
    run_id: str,
    spec: dict[str, Any],
    label: str,
    audit: dict[str, Any],
    finality: str,
    note: str,
    integrity: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = diagnostics or allocation_diagnostics(None, spec)
    verdict = "exploratory_only" if spec["evidence_tier"] in {"tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"} else "watchlist"
    if integrity.get("accounting_integrity_status") == "failed":
        verdict = "invalid_accounting"
    elif audit["any_project_stop_hit"] and audit["max_drawdown_dollars"] < -900:
        verdict = "too_risky"
    elif not audit["target_300_before_stop"] and spec["evidence_tier"] == "benchmark":
        verdict = "benchmark_only"
    elif not audit["target_300_before_stop"]:
        verdict = "too_slow"
    row = {
        "run_id": run_id,
        "experiment_id": spec["experiment_id"],
        "display_name": spec["display_name"],
        "experiment_type": spec["experiment_type"],
        "family_group": spec["family_group"],
        "strategy_family": spec["strategy_family"],
        "evidence_tier": spec["evidence_tier"].replace("_if_exhaustive", ""),
        "run_status": "completed",
        "starting_equity": STARTING_EQUITY,
        "independent_account": True,
        "shared_capital": False,
        "standard_or_stress": label,
        "final_validation_completed": finality == "exact_all_possible",
        "sampled_results_are_final": finality == "exact_all_possible",
        "stress_degradation": math.nan,
        "evidence_finality": finality,
        "risk_framework_verdict": "diagnostic_only" if spec["experiment_type"] in {"strategy_variant", "fixed_combination", "fixed_strategy_combination"} else "watchlist",
        "profit_verdict": verdict,
        "promotion_blockers": "accounting_integrity_failed" if integrity.get("accounting_integrity_status") == "failed" else "research_only;no_real_money_recommendation",
        "notes": f"{note}; {integrity.get('integrity_notes', '')}".strip("; "),
        **audit,
        **integrity,
        "canonical_rule_hash": canonical_rule_hash(spec),
        "duplicate_of": spec.get("duplicate_of", ""),
        **diagnostics,
    }
    return {col: row.get(col, math.nan) for col in RESULT_COLUMNS}


def integrity_from_rolling(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "accounting_integrity_status": "failed",
            "rolling_rebase_check_passed": False,
            "buy_hold_reference_check_passed": False,
            "combination_return_check_passed": False,
            "profit_results_usable": False,
            "integrity_error_count": 1,
            "integrity_notes": "no rolling accounting rows generated",
        }
    frame = pd.DataFrame(rows)
    start_violations = int(pd.to_numeric(frame.get("window_start_equity_violation_count", 0), errors="coerce").fillna(0).sum())
    high_violations = int(pd.to_numeric(frame.get("high_water_start_violation_count", 0), errors="coerce").fillna(0).sum())
    target_violations = int(pd.to_numeric(frame.get("target_state_start_violation_count", 0), errors="coerce").fillna(0).sum())
    stop_violations = int(pd.to_numeric(frame.get("stop_state_start_violation_count", 0), errors="coerce").fillna(0).sum())
    statuses = frame.get("accounting_integrity_status", pd.Series(dtype=str)).astype(str)
    reference_statuses = frame.get("reference_error_status", pd.Series(dtype=str)).astype(str)
    reference_available = bool(frame.get("reference_check_available", pd.Series(dtype=bool)).astype(bool).any())
    reference_failed = bool(reference_statuses.isin(["failed", "failed_missing_reference_prices"]).any())
    comparable_reference_statuses = reference_statuses[~reference_statuses.isin(["not_applicable", "unavailable_missing_reference_prices"])]
    reference_passed = not reference_failed and (not reference_available or comparable_reference_statuses.eq("passed").all())
    combination_failed = bool(statuses.eq("failed").any()) and not reference_failed
    error_count = start_violations + high_violations + target_violations + stop_violations + int(reference_failed) + int(combination_failed)
    passed = error_count == 0 and not statuses.eq("failed").any()
    notes: list[str] = []
    if start_violations or high_violations or target_violations or stop_violations:
        notes.append("rolling windows did not rebase cleanly")
    if reference_failed:
        notes.append("buy-hold reference check failed")
    if combination_failed:
        notes.append("combination return check failed")
    if not notes:
        notes.append("all rolling windows rebased to $3,000; reference/combination checks passed where applicable")
    return {
        "accounting_integrity_status": "passed" if passed else "failed",
        "rolling_rebase_check_passed": start_violations == 0 and high_violations == 0 and target_violations == 0 and stop_violations == 0,
        "buy_hold_reference_check_passed": bool(reference_passed),
        "combination_return_check_passed": not combination_failed,
        "profit_results_usable": bool(passed),
        "integrity_error_count": int(error_count),
        "integrity_notes": "; ".join(notes),
    }


def run_experiments(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    run_id = run_id_now()
    specs = load_specs()
    finalist_ids = parse_finalist_ids(getattr(args, "finalists", None))
    specs = filter_specs_to_finalists(specs, finalist_ids)
    include_combination_batch1 = bool(getattr(args, "include_combination_batch1", False))
    include_commodity_exploratory = bool(getattr(args, "include_commodity_basket_exploratory", False))
    include_commodity_risk_control_batch1 = bool(getattr(args, "include_commodity_risk_control_batch1", False))
    include_crypto_tier2_risk_control_batch1 = bool(getattr(args, "include_crypto_tier2_risk_control_batch1", False))
    include_global_multi_asset_batch1 = bool(getattr(args, "include_global_multi_asset_batch1", False))
    if not include_combination_batch1:
        requested_batch_ids = [exp_id for exp_id in finalist_ids if exp_id in COMBINATION_BATCH1_IDS]
        if requested_batch_ids:
            raise SystemExit("--include-combination-batch1 is required to run Historical Combination Research Sample Batch 1 rows")
        specs = [spec for spec in specs if str(spec["experiment_id"]) not in COMBINATION_BATCH1_IDS]
    if not include_commodity_exploratory:
        requested_commodity_ids = [exp_id for exp_id in finalist_ids if exp_id == COMMODITY_EXPLORATORY_EXPERIMENT_ID]
        if requested_commodity_ids:
            raise SystemExit("--include-commodity-basket-exploratory is required to run the commodity basket exploratory row")
        specs = [spec for spec in specs if str(spec["experiment_id"]) != COMMODITY_EXPLORATORY_EXPERIMENT_ID]
    if not include_commodity_risk_control_batch1:
        requested_risk_control_ids = [exp_id for exp_id in finalist_ids if exp_id in COMMODITY_RISK_CONTROL_BATCH1_IDS]
        if requested_risk_control_ids:
            raise SystemExit("--include-commodity-risk-control-batch1 is required to run Commodity Risk-Control Batch 1 rows")
        specs = [spec for spec in specs if str(spec["experiment_id"]) not in COMMODITY_RISK_CONTROL_BATCH1_IDS]
    if not include_crypto_tier2_risk_control_batch1:
        requested_crypto_tier2_ids = [exp_id for exp_id in finalist_ids if exp_id in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS]
        if requested_crypto_tier2_ids:
            raise SystemExit("--include-crypto-tier2-risk-control-batch1 is required to run Crypto Spot Tier 2 Risk-Control Batch 1 rows")
        specs = [spec for spec in specs if str(spec["experiment_id"]) not in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS]
    if not include_global_multi_asset_batch1:
        requested_global_ids = [exp_id for exp_id in finalist_ids if exp_id in GLOBAL_MULTI_ASSET_BATCH1_IDS]
        if requested_global_ids:
            raise SystemExit("--include-global-multi-asset-batch1 is required to run Global Multi-Asset ETF Fast Exploration Batch 1 rows")
        specs = [spec for spec in specs if str(spec["experiment_id"]) not in GLOBAL_MULTI_ASSET_BATCH1_IDS]
    if not finalist_ids and (
        include_combination_batch1
        or include_commodity_exploratory
        or include_commodity_risk_control_batch1
        or include_crypto_tier2_risk_control_batch1
        or include_global_multi_asset_batch1
    ):
        required_ids: set[str] = set()
        if include_combination_batch1:
            required_ids |= COMBINATION_BATCH1_REQUIRED_RUN_IDS
        if include_commodity_exploratory:
            required_ids |= COMMODITY_EXPLORATORY_REQUIRED_RUN_IDS
        if include_commodity_risk_control_batch1:
            required_ids |= COMMODITY_RISK_CONTROL_REQUIRED_RUN_IDS
        if include_crypto_tier2_risk_control_batch1:
            required_ids |= CRYPTO_TIER2_RISK_CONTROL_REQUIRED_RUN_IDS
        if include_global_multi_asset_batch1:
            required_ids |= GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_RUN_IDS
        specs = [spec for spec in specs if str(spec["experiment_id"]) in required_ids]
    meta = validation_metadata(args)
    selected_horizons = selected_horizons_for_args(args)
    reduced = bool(meta["reduced_validation"])
    if args.mode == "smoke":
        smoke_ids = {
            "SPY_200d_trend_model",
            "SPY_buy_hold",
            "GLD_buy_hold",
            "IEF_buy_hold",
            "BIL_cash_proxy",
            "combo_SPY200d_GLD_50_50_v1",
            "asset_class_tsmom_equal_weight_v1",
            "asset_class_tsmom_top1_v1",
            "asset_class_tsmom_top2_v1",
            "dual_momentum_SPY_GLD_IEF_v1",
            "A_ETF_sector_momentum",
            "individual_stock_momentum",
        }
        if args.include_crypto_exploratory:
            smoke_ids.update({"crypto_time_series_momentum", "crypto_buy_hold_equal_weight", "combo_SPY200d_crypto_tsmom_90_10_v1"})
        specs = [spec for spec in specs if spec["experiment_id"] in smoke_ids]
    duplicate_of = duplicate_map_for_specs(specs)
    prices = load_prices()
    labels = ["standard", "stress"]
    finality = "exact_selected_horizons" if args.mode == "candidate_exhaustive" and reduced else ("exact_all_possible" if args.mode == "candidate_exhaustive" else "sampled_non_final")
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    curves: dict[str, pd.DataFrame] = {}
    runtime_deadline = time.monotonic() + args.max_runtime_minutes * 60 if args.max_runtime_minutes else None

    if prices.empty:
        for spec in specs:
            exp_id = str(spec["experiment_id"])
            if exp_id in duplicate_of:
                reason = f"duplicate canonical rule hash; duplicate_of={duplicate_of[exp_id]}"
                duplicate_spec = {**spec, "duplicate_of": duplicate_of[exp_id]}
                row = blank_result(run_id, duplicate_spec, "duplicate_skipped", reason)
                row["profit_verdict"] = "duplicate_skipped"
                rows.append(row)
                status_rows.append({**duplicate_spec, "run_id": run_id, "run_status": "duplicate_skipped", "status_notes": reason, "canonical_rule_hash": canonical_rule_hash(spec), "duplicate_of": duplicate_of[exp_id]})
                continue
            is_crypto = "crypto" in exp_id.lower() or "crypto" in str(spec.get("family_group", "")).lower()
            is_crypto_tier2_risk_control = exp_id in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS
            if spec["experiment_type"] == "blocked_family":
                row = blank_result(run_id, spec, "blocked_by_gate", str(spec.get("blocked_reason", "blocked by gate")))
                rows.append(row)
                status_rows.append({**spec, "run_id": run_id, "run_status": "blocked_by_gate", "status_notes": row["notes"]})
            elif is_crypto and not (args.include_crypto_exploratory or is_crypto_tier2_risk_control):
                status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "crypto excluded by default"})
            else:
                reason = "ETF adjusted price cache unavailable under no-network/reuse-cache; no download attempted"
                rows.append(blank_result(run_id, spec, "incomplete_evidence", reason))
                status_rows.append({**spec, "run_id": run_id, "run_status": "incomplete_evidence", "status_notes": reason})
        results = add_validation_metadata(pd.DataFrame(rows).reindex(columns=RESULT_COLUMNS), meta)
        rolling = add_validation_metadata(pd.DataFrame(rolling_rows).reindex(columns=ROLLING_COLUMNS), meta)
        status = add_validation_metadata(pd.DataFrame(status_rows), meta)
        rankings = build_rankings(results, rolling, specs)
        return results, rolling, rankings, status, curves, {"run_id": run_id, "finality": finality, "prices": prices, "finalist_ids": finalist_ids}

    for spec in specs:
        exp_id = str(spec["experiment_id"])
        if exp_id in duplicate_of:
            reason = f"duplicate canonical rule hash; duplicate_of={duplicate_of[exp_id]}"
            duplicate_spec = {**spec, "duplicate_of": duplicate_of[exp_id]}
            row = blank_result(run_id, duplicate_spec, "duplicate_skipped", reason)
            row["profit_verdict"] = "duplicate_skipped"
            row["risk_framework_verdict"] = "duplicate_skipped"
            row["evidence_finality"] = "duplicate_skipped"
            rows.append(row)
            status_rows.append({**duplicate_spec, "run_id": run_id, "run_status": "duplicate_skipped", "status_notes": reason, "canonical_rule_hash": canonical_rule_hash(spec), "duplicate_of": duplicate_of[exp_id]})
            continue
        is_crypto = "crypto" in exp_id.lower() or "crypto" in str(spec.get("family_group", "")).lower()
        is_crypto_tier2_risk_control = exp_id in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS
        is_commodity_exploratory = exp_id == COMMODITY_EXPLORATORY_EXPERIMENT_ID
        is_commodity_risk_control = exp_id in COMMODITY_RISK_CONTROL_BATCH1_IDS
        is_global_multi_asset = exp_id in GLOBAL_MULTI_ASSET_BATCH1_IDS
        run_allowed_value = str(spec["run_allowed"])
        allowed = spec["run_allowed"] is True or run_allowed_value.startswith("true_") or (run_allowed_value == "research_sample_only" and args.mode == "research_sample")
        if spec["experiment_type"] == "blocked_family":
            row = blank_result(run_id, spec, "blocked_by_gate", str(spec.get("blocked_reason", "blocked by gate")))
            rows.append(row)
            status_rows.append({**spec, "run_id": run_id, "run_status": "blocked_by_gate", "status_notes": row["notes"]})
            continue
        if is_crypto and not (args.include_crypto_exploratory or is_crypto_tier2_risk_control):
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "crypto excluded by default"})
            continue
        if is_crypto_tier2_risk_control and not include_crypto_tier2_risk_control_batch1:
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "crypto Tier 2 risk-control batch excluded by default"})
            continue
        if is_commodity_exploratory and not include_commodity_exploratory:
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "commodity basket exploratory excluded by default"})
            continue
        if is_commodity_risk_control and not include_commodity_risk_control_batch1:
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "commodity risk-control batch excluded by default"})
            continue
        if is_global_multi_asset and not include_global_multi_asset_batch1:
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "global multi-asset batch excluded by default"})
            continue
        if exp_id in {"A_ETF_sector_momentum", "current_no_cash_proxy_alpha_AB"}:
            reason = "exact fresh-window stream is not exposed in compact profit exploration; no summary-metric approximation used"
            rows.append(blank_result(run_id, spec, "incomplete_evidence", reason))
            status_rows.append({**spec, "run_id": run_id, "run_status": "incomplete_evidence", "status_notes": reason})
            continue
        if is_crypto and not is_crypto_tier2_risk_control:
            reason = "crypto optional row is Tier 1; profit exploration imports no raw crypto data and does not rerun crypto exploration"
            rows.append(blank_result(run_id, spec, "incomplete_evidence", reason))
            status_rows.append({**spec, "run_id": run_id, "run_status": "incomplete_evidence", "status_notes": reason})
            continue
        if not allowed:
            row = blank_result(run_id, spec, "blocked_by_gate", str(spec.get("blocked_reason", "run not allowed")))
            rows.append(row)
            status_rows.append({**spec, "run_id": run_id, "run_status": "blocked_by_gate", "status_notes": row["notes"]})
            continue
        if exp_id.startswith("combo_") and not args.include_fixed_combinations:
            status_rows.append({**spec, "run_id": run_id, "run_status": "excluded_by_flag", "status_notes": "fixed combinations excluded"})
            continue
        if run_allowed_value == "research_sample_only" and args.mode != "research_sample":
            reason = "research_sample_only row excluded outside research_sample; candidate_exhaustive not allowed in this task"
            rows.append(blank_result(run_id, spec, "incomplete_evidence", reason))
            status_rows.append({**spec, "run_id": run_id, "run_status": "incomplete_evidence", "status_notes": reason})
            continue
        completed_any = False
        try:
            model = model_for_experiment(spec, prices)
            diagnostics = allocation_diagnostics(model, spec)
        except KeyError as exc:
            reason = f"incomplete_evidence: {exc}"
            rows.append(blank_result(run_id, spec, "incomplete_evidence", reason))
            status_rows.append({**spec, "run_id": run_id, "run_status": "incomplete_evidence", "status_notes": reason, **allocation_diagnostics(None, spec)})
            continue
        for label in labels:
            if runtime_deadline and time.monotonic() > runtime_deadline:
                break
            curve = curve_for_model(model, LABEL_COSTS[label])
            note = model.note
            if label == "standard":
                curves[exp_id] = curve
            horizons = selected_horizons
            label_rolling_rows: list[dict[str, Any]] = []
            for horizon in horizons:
                metrics, possible_count, method = rolling_metrics_for_model(model, horizon, args.mode, LABEL_COSTS[label])
                if not metrics:
                    continue
                exact = finality == "exact_all_possible" and method == "all_possible" and metrics["number_of_windows"] == possible_count
                exact_selected = finality == "exact_selected_horizons" and method == "all_possible" and metrics["number_of_windows"] == possible_count
                rolling_row = {
                    "experiment_id": exp_id,
                    "horizon": horizon,
                    "standard_or_stress": label,
                    "rolling_method": method,
                    "evidence_finality": "exact_selected_horizons" if exact_selected else ("exact_all_possible" if exact else ("sampled_non_final" if args.mode != "candidate_exhaustive" else "incomplete_evidence")),
                    "selected_horizons_completed": bool(exact or exact_selected),
                    **meta,
                    "candidate_exhaustive_completed": bool(args.mode == "candidate_exhaustive" and not reduced and exact),
                    "notes": note,
                    **metrics,
                }
                rolling_rows.append(rolling_row)
                label_rolling_rows.append(rolling_row)
            audit = profit_audit(curve["equity"], curve["date"])
            selected_complete = selected_horizons_completed(label_rolling_rows, selected_horizons, reduced)
            result = result_row(run_id, spec, label, audit, finality, note, integrity_from_rolling(label_rolling_rows), diagnostics)
            result.update(meta)
            result["selected_horizons_completed"] = selected_complete
            result["full_horizon_validation_completed"] = False if reduced else args.mode == "candidate_exhaustive" and selected_complete
            result["candidate_exhaustive_completed"] = bool(args.mode == "candidate_exhaustive" and not reduced and selected_complete)
            result["final_validation_completed"] = bool(args.mode == "candidate_exhaustive" and not reduced and selected_complete)
            result["sampled_results_are_final"] = bool(args.mode == "candidate_exhaustive" and not reduced and selected_complete)
            if args.mode == "candidate_exhaustive" and not selected_complete:
                result["evidence_finality"] = "incomplete_evidence"
                result["profit_verdict"] = "incomplete_evidence"
                result["profit_results_usable"] = False
                result["promotion_blockers"] = f"{result.get('promotion_blockers', '')}; selected_horizons_incomplete".strip("; ")
            rows.append(result)
            completed_any = True
        if completed_any:
            status_rows.append({
                **spec,
                **meta,
                "run_id": run_id,
                "run_status": "completed",
                "status_notes": "completed from cached adjusted ETF prices",
                "selected_horizons_completed": True,
                "full_horizon_validation_completed": False if reduced else args.mode == "candidate_exhaustive",
                "candidate_exhaustive_completed": bool(args.mode == "candidate_exhaustive" and not reduced),
                "canonical_rule_hash": canonical_rule_hash(spec),
                "duplicate_of": spec.get("duplicate_of", ""),
                **diagnostics,
            })

    results = add_validation_metadata(pd.DataFrame(rows).reindex(columns=RESULT_COLUMNS), meta)
    rolling = add_validation_metadata(pd.DataFrame(rolling_rows).reindex(columns=ROLLING_COLUMNS), meta)
    status = add_validation_metadata(pd.DataFrame(status_rows), meta)
    results = add_stress_degradation(results)
    rankings = build_rankings(results, rolling, specs)
    return results, rolling, rankings, status, curves, {"run_id": run_id, "finality": finality, "prices": prices, "finalist_ids": finalist_ids}


def add_stress_degradation(results: pd.DataFrame) -> pd.DataFrame:
    out = results.copy()
    for exp_id, group in out.groupby("experiment_id"):
        std = group[group["standard_or_stress"].eq("standard")]
        stress = group[group["standard_or_stress"].eq("stress")]
        if std.empty or stress.empty:
            continue
        std_equity = pd.to_numeric(std["stop_enforced_final_equity"], errors="coerce").iloc[0]
        stress_equity = pd.to_numeric(stress["stop_enforced_final_equity"], errors="coerce").iloc[0]
        degradation = max(0.0, float(std_equity - stress_equity)) if pd.notna(std_equity) and pd.notna(stress_equity) else math.nan
        out.loc[out["experiment_id"].eq(exp_id), "stress_degradation"] = degradation
    return out


def drawdown_budget_penalty_for_usage(risk_budget_used: float) -> float:
    if not math.isfinite(risk_budget_used) or risk_budget_used <= 0.0:
        return 0.0
    if risk_budget_used <= 0.50:
        return 0.0
    if risk_budget_used <= 0.75:
        return 40.0 * (risk_budget_used - 0.50) / 0.25
    if risk_budget_used <= 1.00:
        return 40.0 + 100.0 * (risk_budget_used - 0.75) / 0.25
    return 140.0 + 220.0 * (risk_budget_used - 1.00)


def build_rankings(results: pd.DataFrame, rolling: pd.DataFrame, specs: list[dict[str, Any]]) -> pd.DataFrame:
    spec_by_id = {spec["experiment_id"]: spec for spec in specs}
    duplicates = duplicate_map_for_specs(specs)
    rows: list[dict[str, Any]] = []
    r90 = rolling[(rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq("standard"))].copy()
    r180 = rolling[(rolling["horizon"].eq(180)) & (rolling["standard_or_stress"].eq("standard"))].copy()

    def rolling_value(row: pd.DataFrame, column: str, default: float = 0.0) -> float:
        if row.empty or column not in row:
            return default
        value = pd.to_numeric(row[column], errors="coerce").iloc[0]
        return default if pd.isna(value) else float(value)

    core_failed = bool(
        results[
            results["experiment_id"].isin(CORE_BUY_HOLD_BENCHMARKS)
            & results["standard_or_stress"].eq("standard")
            & ~results["accounting_integrity_status"].eq("passed")
            & results["run_status"].eq("completed")
        ].shape[0]
    )
    for spec in specs:
        exp_id = spec["experiment_id"]
        result = results[results["experiment_id"].eq(exp_id)]
        std_result = result[result["standard_or_stress"].eq("standard")]
        row90 = r90[r90["experiment_id"].eq(exp_id)]
        run_status = str(std_result["run_status"].iloc[0]) if not std_result.empty else "excluded_by_flag"
        accounting_status = str(std_result["accounting_integrity_status"].iloc[0]) if not std_result.empty and "accounting_integrity_status" in std_result else "not_applicable"
        profit_usable = boolish(std_result["profit_results_usable"].iloc[0]) if not std_result.empty and "profit_results_usable" in std_result else False
        validation_fields = {
            "run_validation_scope": std_result["run_validation_scope"].iloc[0] if not std_result.empty and "run_validation_scope" in std_result else "",
            "selected_horizons": std_result["selected_horizons"].iloc[0] if not std_result.empty and "selected_horizons" in std_result else "",
            "omitted_horizons": std_result["omitted_horizons"].iloc[0] if not std_result.empty and "omitted_horizons" in std_result else "",
            "selected_horizons_completed": boolish(std_result["selected_horizons_completed"].iloc[0]) if not std_result.empty and "selected_horizons_completed" in std_result else False,
            "full_horizon_validation_completed": boolish(std_result["full_horizon_validation_completed"].iloc[0]) if not std_result.empty and "full_horizon_validation_completed" in std_result else False,
            "candidate_exhaustive_completed": boolish(std_result["candidate_exhaustive_completed"].iloc[0]) if not std_result.empty and "candidate_exhaustive_completed" in std_result else False,
            "reduced_validation": boolish(std_result["reduced_validation"].iloc[0]) if not std_result.empty and "reduced_validation" in std_result else False,
            "reduced_validation_reason": std_result["reduced_validation_reason"].iloc[0] if not std_result.empty and "reduced_validation_reason" in std_result else "",
        }
        default_diagnostics = allocation_diagnostics(None, spec, "duplicate_skipped" if exp_id in duplicates else "not_applicable")
        diagnostics = {
            column: std_result[column].iloc[0] if not std_result.empty and column in std_result else default_diagnostics.get(column, math.nan)
            for column in DIAGNOSTIC_COLUMNS
        }
        if row90.empty or run_status != "completed":
            base = {
                "experiment_id": exp_id,
                "display_name": spec["display_name"],
                "evidence_tier": spec["evidence_tier"],
                "run_status": run_status,
                "profit_score": 0.0,
                "risk_penalty": 1000.0 if run_status in {"blocked_by_gate", "incomplete_evidence", "duplicate_skipped"} else 500.0,
                "final_score": -1000.0,
                "profit_seeking_score": -1000.0,
                "balanced_score": -1000.0,
                "drawdown_control_score": -1000.0,
                "score_audit_notes": "not scored because row was not completed with usable rolling metrics",
                "balanced_drawdown_aware_score_v2": -1000.0,
                "risk_budget_used_90d": math.nan,
                "risk_budget_used_180d": math.nan,
                "target_score_component": 0.0,
                "upside_score_component": 0.0,
                "median_equity_score_component": 0.0,
                "tail_equity_score_component": 0.0,
                "stop_penalty_component": 0.0,
                "drawdown_budget_penalty_component": 0.0,
                "stress_penalty_component": 0.0,
                "evidence_quality_penalty_component": 1000.0,
                "practical_verdict_v2": run_status if run_status in {"blocked_by_gate", "incomplete_evidence", "duplicate_skipped"} else "incomplete_evidence",
                "practical_score_notes": "v2 not scored because row was not completed with usable rolling metrics",
                "profit_verdict": run_status if run_status in {"blocked_by_gate", "incomplete_evidence", "duplicate_skipped"} else "reject_for_now",
                "ranking_notes": "not runnable or excluded; no performance metrics used",
                "accounting_integrity_status": accounting_status,
                "profit_results_usable": False,
                "ranking_blocked_reason": run_status,
                "canonical_rule_hash": canonical_rule_hash(spec),
                "duplicate_of": spec.get("duplicate_of", duplicates.get(exp_id, "")),
                **diagnostics,
                "candidate_exhaustive_queue_rank": math.nan,
                "deserves_candidate_exhaustive": False,
                "queue_reason": "",
                **validation_fields,
            }
            rows.append(base)
            continue
        r = row90.iloc[0]
        row180 = r180[r180["experiment_id"].eq(exp_id)]
        p90_target_300 = float(r["p_target_300_before_stop"])
        p90_target_400 = float(r["p_target_400_before_stop"])
        p90_target_600 = float(r["p_target_600_before_stop"])
        p90_target_900 = float(r["p_target_900_before_stop"])
        p90_target_1200 = float(r["p_target_1200_before_stop"])
        p90_stop = float(r["p_any_project_stop_hit"])
        median_90 = float(r["median_stop_enforced_final_equity"])
        p95_90 = float(r["p95_stop_enforced_final_equity"])
        worst_90_drawdown = float(r["worst_max_drawdown"])
        expected_profit_90 = float(r["expected_profit_dollars"])
        p180_target_300 = rolling_value(row180, "p_target_300_before_stop")
        p180_target_400 = rolling_value(row180, "p_target_400_before_stop")
        p180_target_600 = rolling_value(row180, "p_target_600_before_stop")
        p180_target_900 = rolling_value(row180, "p_target_900_before_stop")
        p180_target_1200 = rolling_value(row180, "p_target_1200_before_stop")
        p180_stop = rolling_value(row180, "p_any_project_stop_hit")
        median_180 = rolling_value(row180, "median_stop_enforced_final_equity", STARTING_EQUITY)
        p95_180 = rolling_value(row180, "p95_stop_enforced_final_equity", STARTING_EQUITY)
        worst_180_drawdown = rolling_value(row180, "worst_max_drawdown")
        expected_profit_180 = rolling_value(row180, "expected_profit_dollars")
        stress_degradation = float(std_result["stress_degradation"].iloc[0]) if not std_result.empty and pd.notna(std_result["stress_degradation"].iloc[0]) else 0.0
        exploratory_tiers = {"tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"}
        tier_penalty = 300.0 if spec["evidence_tier"] in exploratory_tiers else 0.0
        score_target_300_component = 120.0 * p90_target_300
        score_target_400_component = 160.0 * p90_target_400
        score_target_600_component = 220.0 * p90_target_600
        score_target_900_component = 80.0 * p90_target_900
        score_target_1200_component = 60.0 * p90_target_1200
        score_median_equity_component = 0.06 * (median_90 - STARTING_EQUITY)
        score_p95_equity_component = 0.04 * (p95_90 - STARTING_EQUITY)
        score_expected_profit_component = 0.03 * expected_profit_90
        profit_score = (
            score_target_300_component
            + score_target_400_component
            + score_target_600_component
            + score_target_900_component
            + score_target_1200_component
            + score_median_equity_component
            + score_p95_equity_component
            + score_expected_profit_component
        )
        drawdown_excess = max(0.0, -600.0 - worst_90_drawdown)
        score_stop_penalty_component = 350.0 * p90_stop
        score_drawdown_excess_penalty_component = 0.35 * drawdown_excess
        score_stress_penalty_component = 0.08 * stress_degradation
        score_tier_penalty_component = tier_penalty
        risk_penalty = (
            score_stop_penalty_component
            + score_drawdown_excess_penalty_component
            + score_stress_penalty_component
            + score_tier_penalty_component
        )
        final_score = profit_score - risk_penalty
        dd90_abs = abs(min(0.0, worst_90_drawdown))
        dd180_abs = abs(min(0.0, worst_180_drawdown))
        profit_seeking_score = (
            90.0 * p90_target_300
            + 130.0 * p90_target_400
            + 190.0 * p90_target_600
            + 110.0 * p90_target_900
            + 80.0 * p90_target_1200
            + 60.0 * p180_target_300
            + 90.0 * p180_target_400
            + 140.0 * p180_target_600
            + 100.0 * p180_target_900
            + 80.0 * p180_target_1200
            + 0.035 * (median_90 - STARTING_EQUITY)
            + 0.05 * (p95_90 - STARTING_EQUITY)
            + 0.02 * expected_profit_90
            + 0.025 * (median_180 - STARTING_EQUITY)
            + 0.035 * (p95_180 - STARTING_EQUITY)
            + 0.015 * expected_profit_180
            - 200.0 * p90_stop
            - 180.0 * p180_stop
            - 0.08 * max(0.0, dd90_abs - 600.0)
            - 0.05 * max(0.0, dd180_abs - 600.0)
            - 0.04 * stress_degradation
            - tier_penalty
        )
        balanced_score = (
            100.0 * p90_target_300
            + 140.0 * p90_target_400
            + 170.0 * p90_target_600
            + 60.0 * p90_target_900
            + 40.0 * p90_target_1200
            + 80.0 * p180_target_300
            + 120.0 * p180_target_400
            + 150.0 * p180_target_600
            + 60.0 * p180_target_900
            + 40.0 * p180_target_1200
            + 0.03 * (median_90 - STARTING_EQUITY)
            + 0.035 * (p95_90 - STARTING_EQUITY)
            + 0.025 * expected_profit_90
            + 0.025 * (median_180 - STARTING_EQUITY)
            + 0.03 * (p95_180 - STARTING_EQUITY)
            + 0.02 * expected_profit_180
            - 450.0 * p90_stop
            - 350.0 * p180_stop
            - 0.35 * max(0.0, dd90_abs - 450.0)
            - 0.25 * max(0.0, dd180_abs - 500.0)
            - 0.12 * stress_degradation
            - tier_penalty
        )
        drawdown_control_score = (
            80.0 * (1.0 - p90_stop)
            + 70.0 * (1.0 - p180_stop)
            + 0.20 * max(0.0, 600.0 - dd90_abs)
            + 0.15 * max(0.0, 600.0 - dd180_abs)
            + 30.0 * p90_target_300
            + 40.0 * p90_target_400
            + 20.0 * p180_target_300
            + 30.0 * p180_target_400
            + 0.01 * (median_90 - STARTING_EQUITY)
            + 0.01 * (median_180 - STARTING_EQUITY)
            - 0.12 * stress_degradation
            - 0.25 * max(0.0, dd90_abs - 600.0)
            - 0.15 * max(0.0, dd180_abs - 600.0)
            - tier_penalty
        )
        risk_budget_used_90d = dd90_abs / TRAILING_DRAWDOWN if TRAILING_DRAWDOWN else math.nan
        risk_budget_used_180d = dd180_abs / TRAILING_DRAWDOWN if TRAILING_DRAWDOWN else math.nan
        target_score_component = (
            95.0 * p90_target_300
            + 135.0 * p90_target_400
            + 75.0 * p180_target_300
            + 115.0 * p180_target_400
        )
        upside_score_component = (
            150.0 * p90_target_600
            + 60.0 * p90_target_900
            + 35.0 * p90_target_1200
            + 140.0 * p180_target_600
            + 65.0 * p180_target_900
            + 40.0 * p180_target_1200
        )
        median_equity_score_component = 0.03 * (median_90 - STARTING_EQUITY) + 0.025 * (median_180 - STARTING_EQUITY)
        tail_equity_score_component = 0.035 * (p95_90 - STARTING_EQUITY) + 0.03 * (p95_180 - STARTING_EQUITY)
        stop_penalty_component = 500.0 * p90_stop + 400.0 * p180_stop
        drawdown_budget_penalty_component = (
            0.65 * drawdown_budget_penalty_for_usage(risk_budget_used_90d)
            + 0.45 * drawdown_budget_penalty_for_usage(risk_budget_used_180d)
        )
        stress_penalty_component = 0.15 * stress_degradation
        evidence_quality_penalty_component = tier_penalty
        if validation_fields["reduced_validation"]:
            evidence_quality_penalty_component += 20.0
        if not validation_fields["full_horizon_validation_completed"]:
            evidence_quality_penalty_component += 10.0
        balanced_drawdown_aware_score_v2 = (
            target_score_component
            + upside_score_component
            + median_equity_score_component
            + tail_equity_score_component
            - stop_penalty_component
            - drawdown_budget_penalty_component
            - stress_penalty_component
            - evidence_quality_penalty_component
        )
        verdict = "watchlist"
        practical_verdict_v2 = "watchlist"
        practical_score_notes = "v2 score penalizes drawdown budget usage before the -600 hard stop and preserves reduced-validation/non-final penalties"
        ranking_blocked_reason = ""
        if accounting_status != "passed" or not profit_usable:
            verdict = "invalid_accounting"
            final_score = -1000.0
            profit_seeking_score = -1000.0
            balanced_score = -1000.0
            drawdown_control_score = -1000.0
            balanced_drawdown_aware_score_v2 = -1000.0
            practical_verdict_v2 = "incomplete_evidence"
            practical_score_notes = "v2 blocked because accounting integrity or usable-results check failed"
            ranking_blocked_reason = "accounting_integrity_failed"
        elif core_failed:
            verdict = "invalid_accounting"
            final_score = -1000.0
            profit_seeking_score = -1000.0
            balanced_score = -1000.0
            drawdown_control_score = -1000.0
            balanced_drawdown_aware_score_v2 = -1000.0
            practical_verdict_v2 = "incomplete_evidence"
            practical_score_notes = "v2 blocked because a core buy-hold reference check failed"
            ranking_blocked_reason = "core_buy_hold_reference_failed"
        elif spec["evidence_tier"] in {"tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"}:
            verdict = "exploratory_only"
            practical_verdict_v2 = "incomplete_evidence"
            practical_score_notes = "Exploratory row cannot be practical under v2"
        elif p90_stop > 0.08 or worst_90_drawdown < -1000:
            verdict = "high_upside_high_risk" if p90_target_600 > 0.05 else "too_risky"
            practical_verdict_v2 = "high_upside_high_risk" if p90_target_600 > 0.05 else "too_risky"
            practical_score_notes = "v2 classifies row as high risk because stop/drawdown behavior dominates upside"
        elif p90_target_300 < 0.05:
            verdict = "benchmark_only" if spec["evidence_tier"] == "benchmark" else "too_slow"
            practical_verdict_v2 = "benchmark_only" if spec["evidence_tier"] == "benchmark" else "too_slow"
            practical_score_notes = "v2 classifies row as too slow or benchmark-only because target hurdle rates are low"
        elif risk_budget_used_90d > 1.0 or risk_budget_used_180d > 1.0:
            practical_verdict_v2 = "high_upside_high_risk" if p90_target_600 > 0.05 or p180_target_600 > 0.20 else "watchlist"
            practical_score_notes = "v2 flags drawdown budget usage above 100% in at least one selected horizon"
        elif spec["evidence_tier"] == "benchmark":
            practical_verdict_v2 = "benchmark_only"
            practical_score_notes = "benchmark row is useful for comparison but is not a practical profit candidate"
        rows.append(
            {
                "experiment_id": exp_id,
                "display_name": spec["display_name"],
                "evidence_tier": spec["evidence_tier"].replace("_if_exhaustive", ""),
                "run_status": run_status,
                "p_90d_target_300_before_stop": p90_target_300,
                "p_90d_target_400_before_stop": p90_target_400,
                "p_90d_target_600_before_stop": p90_target_600,
                "p_90d_target_900_before_stop": p90_target_900,
                "p_90d_target_1200_before_stop": p90_target_1200,
                "p_90d_any_stop_hit": p90_stop,
                "median_90d_stop_enforced_final_equity": median_90,
                "p95_90d_stop_enforced_final_equity": p95_90,
                "worst_90d_max_drawdown": worst_90_drawdown,
                "expected_profit_90d": expected_profit_90,
                "p_180d_target_300_before_stop": p180_target_300,
                "p_180d_target_400_before_stop": p180_target_400,
                "p_180d_target_600_before_stop": p180_target_600,
                "p_180d_target_900_before_stop": p180_target_900,
                "p_180d_target_1200_before_stop": p180_target_1200,
                "p_180d_any_stop_hit": p180_stop,
                "median_180d_stop_enforced_final_equity": median_180,
                "p95_180d_stop_enforced_final_equity": p95_180,
                "worst_180d_max_drawdown": worst_180_drawdown,
                "expected_profit_180d": expected_profit_180,
                "stress_degradation": stress_degradation,
                **validation_fields,
                "profit_score": profit_score,
                "risk_penalty": risk_penalty,
                "final_score": final_score,
                "score_target_300_component": score_target_300_component,
                "score_target_400_component": score_target_400_component,
                "score_target_600_component": score_target_600_component,
                "score_target_900_component": score_target_900_component,
                "score_target_1200_component": score_target_1200_component,
                "score_median_equity_component": score_median_equity_component,
                "score_p95_equity_component": score_p95_equity_component,
                "score_expected_profit_component": score_expected_profit_component,
                "score_stop_penalty_component": score_stop_penalty_component,
                "score_drawdown_excess_penalty_component": score_drawdown_excess_penalty_component,
                "score_stress_penalty_component": score_stress_penalty_component,
                "score_tier_penalty_component": score_tier_penalty_component,
                "profit_seeking_score": profit_seeking_score,
                "balanced_score": balanced_score,
                "drawdown_control_score": drawdown_control_score,
                "balanced_drawdown_aware_score_v2": balanced_drawdown_aware_score_v2,
                "risk_budget_used_90d": risk_budget_used_90d,
                "risk_budget_used_180d": risk_budget_used_180d,
                "target_score_component": target_score_component,
                "upside_score_component": upside_score_component,
                "median_equity_score_component": median_equity_score_component,
                "tail_equity_score_component": tail_equity_score_component,
                "stop_penalty_component": stop_penalty_component,
                "drawdown_budget_penalty_component": drawdown_budget_penalty_component,
                "stress_penalty_component": stress_penalty_component,
                "evidence_quality_penalty_component": evidence_quality_penalty_component,
                "score_audit_notes": (
                    "alternate score views include 90d and 180d metrics; original final_score penalizes drawdown only after the -600 risk budget is breached"
                ),
                "practical_verdict_v2": practical_verdict_v2,
                "practical_score_notes": practical_score_notes,
                "profit_verdict": verdict,
                "ranking_notes": "diagnostic score rewards target ladder and stop-enforced equity; penalizes stops, drawdown, stress degradation, and evidence tier",
                "accounting_integrity_status": accounting_status,
                "profit_results_usable": bool(profit_usable and not core_failed),
                "ranking_blocked_reason": ranking_blocked_reason,
                "canonical_rule_hash": canonical_rule_hash(spec),
                "duplicate_of": spec.get("duplicate_of", ""),
                **diagnostics,
                "candidate_exhaustive_queue_rank": math.nan,
                "deserves_candidate_exhaustive": False,
                "queue_reason": "",
            }
        )
    frame = pd.DataFrame(rows)
    for column in RANKING_COLUMNS:
        if column not in frame:
            frame[column] = math.nan
    research_sample_only_ids = {
        str(spec["experiment_id"])
        for spec in specs
        if str(spec.get("run_allowed")) == "research_sample_only"
    }
    eligible = frame[
        frame["run_status"].eq("completed")
        & ~frame["evidence_tier"].isin(["tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"])
        & ~frame["evidence_tier"].eq("benchmark")
        & ~frame["experiment_id"].isin(research_sample_only_ids)
        & frame["accounting_integrity_status"].eq("passed")
        & frame["profit_results_usable"].map(boolish)
    ].copy()
    if not eligible.empty:
        best_idx = eligible.sort_values("final_score", ascending=False).index[0]
        best_rolling = r90[r90["experiment_id"].eq(frame.loc[best_idx, "experiment_id"])]
        best_finality = str(best_rolling["evidence_finality"].iloc[0]) if not best_rolling.empty else ""
        exact_best = best_finality in {"exact_all_possible", "exact_selected_horizons"}
        reduced_best = boolish(frame.loc[best_idx, "reduced_validation"])
        frame.loc[best_idx, "profit_verdict"] = "reduced_validation_leader" if exact_best and reduced_best else ("promotion_review_candidate" if exact_best else "leading_profit_candidate")
    frame["rank_overall"] = frame["final_score"].rank(ascending=False, method="first").astype(int)
    frame["rank_profit_potential"] = frame["profit_score"].rank(ascending=False, method="first").astype(int)
    frame["rank_risk_control"] = frame["risk_penalty"].rank(ascending=True, method="first").astype(int)
    frame["rank_upside"] = frame["p_90d_target_600_before_stop"].fillna(0).rank(ascending=False, method="first").astype(int)
    frame["rank_profit_seeking_score"] = frame["profit_seeking_score"].rank(ascending=False, method="first").astype(int)
    frame["rank_balanced_score"] = frame["balanced_score"].rank(ascending=False, method="first").astype(int)
    frame["rank_drawdown_control_score"] = frame["drawdown_control_score"].rank(ascending=False, method="first").astype(int)
    frame["rank_balanced_drawdown_aware_v2"] = frame["balanced_drawdown_aware_score_v2"].rank(ascending=False, method="first").astype(int)
    v2_eligible = frame[
        frame["run_status"].eq("completed")
        & frame["accounting_integrity_status"].eq("passed")
        & frame["profit_results_usable"].map(boolish)
        & ~frame["evidence_tier"].isin(["tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory", "benchmark"])
        & ~frame["experiment_id"].isin(research_sample_only_ids)
        & ~frame["practical_verdict_v2"].isin(["too_risky", "high_upside_high_risk", "too_slow", "benchmark_only", "incomplete_evidence"])
    ].copy()
    if not v2_eligible.empty:
        ordered_v2 = v2_eligible.sort_values("balanced_drawdown_aware_score_v2", ascending=False)
        leader_idx = ordered_v2.index[0]
        frame.loc[leader_idx, "practical_verdict_v2"] = "practical_leader"
        frame.loc[leader_idx, "practical_score_notes"] = (
            "v2 practical leader among non-benchmark completed rows; candidate-exhaustive research validation completed but promotion review remains separate"
            if boolish(frame.loc[leader_idx, "candidate_exhaustive_completed"])
            else "v2 practical leader among non-benchmark completed rows; still reduced selected-horizon evidence only"
        )
        for idx in ordered_v2.index[1:]:
            if float(frame.loc[idx, "balanced_drawdown_aware_score_v2"]) > 0.0:
                frame.loc[idx, "practical_verdict_v2"] = "promotion_review_candidate"
                frame.loc[idx, "practical_score_notes"] = (
                    "v2 positive-score challenger; candidate-exhaustive research validation completed but promotion review remains separate"
                    if boolish(frame.loc[idx, "candidate_exhaustive_completed"])
                    else "v2 positive-score challenger; requires full 30/60/90/180 validation before promotion review"
                )
    frame = add_candidate_queue_fields(frame)
    for idx in frame[frame["experiment_id"].isin(research_sample_only_ids) & frame["run_status"].eq("completed")].index:
        if not boolish(frame.loc[idx, "profit_results_usable"]):
            frame.loc[idx, "profit_verdict"] = "incomplete_evidence"
            frame.loc[idx, "practical_verdict_v2"] = "incomplete_evidence"
        elif frame.loc[idx, "experiment_id"] == COMMODITY_EXPLORATORY_EXPERIMENT_ID:
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            risk_budget_90d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_90d"]]), errors="coerce").fillna(0.0).iloc[0])
            risk_budget_180d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_180d"]]), errors="coerce").fillna(0.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            concentration = boolish(frame.loc[idx, "product_concentration_warning"])
            frame.loc[idx, "commodity_required_label"] = COMMODITY_EXPLORATORY_REQUIRED_LABEL
            frame.loc[idx, "commodity_wrapper_warning"] = True
            frame.loc[idx, "exploratory_public_data_warning"] = True
            frame.loc[idx, "not_paper_forward_warning"] = True
            frame.loc[idx, "direct_futures_claim_disallowed"] = True
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            if p90_stop > 0.08 or worst_90_drawdown < -1000:
                frame.loc[idx, "profit_verdict"] = "too_risky"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "queue_reason"] = "commodity wrapper row has too much stop/drawdown risk for exploratory candidate_exhaustive gate"
                frame.loc[idx, "ranking_notes"] = "fast exploratory commodity wrapper row; too risky and not paper-forward ready"
            elif p90_target_300 < 0.05 and p90_target_400 < 0.03:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "queue_reason"] = "commodity wrapper row is too slow at the 90-day +300/+400 hurdles"
                frame.loc[idx, "ranking_notes"] = "fast exploratory commodity wrapper row; too slow and not candidate_exhaustive queued"
            elif concentration:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "commodity wrapper row remains exploratory because one product dominates allocation share"
                frame.loc[idx, "ranking_notes"] = "fast exploratory commodity wrapper row; product concentration and wrapper risks need review"
            elif risk_budget_90d > 1.0 or risk_budget_180d > 1.0 or worst_90_drawdown < -600.0:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate_risk_budget_breach"
                frame.loc[idx, "practical_verdict_v2"] = "high_upside_high_risk_watchlist"
                frame.loc[idx, "queue_reason"] = "base commodity row has strong target rates but breached the -600 drawdown budget at 90d or 180d"
                frame.loc[idx, "ranking_notes"] = "fast exploratory public-data row; target power exists but risk-control review is required before any stronger gate"
            else:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "commodity wrapper row is exploratory only; product identity and wrapper review required before stronger validation"
                frame.loc[idx, "ranking_notes"] = "fast exploratory public-data row; not validated, not candidate_exhaustive queued, and not paper-forward ready"
        elif frame.loc[idx, "experiment_id"] in COMMODITY_RISK_CONTROL_BATCH1_IDS:
            exp_id = str(frame.loc[idx, "experiment_id"])
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            p180_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            worst_180_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_180d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            risk_budget_90d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_90d"]]), errors="coerce").fillna(0.0).iloc[0])
            risk_budget_180d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_180d"]]), errors="coerce").fillna(0.0).iloc[0])
            own_score = float(pd.to_numeric(pd.Series([frame.loc[idx, "balanced_drawdown_aware_score_v2"]]), errors="coerce").fillna(-math.inf).iloc[0])
            base = frame[frame["experiment_id"].eq(COMMODITY_EXPLORATORY_EXPERIMENT_ID)]
            primary = frame[
                frame["experiment_id"].isin(["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"])
                & frame["run_status"].eq("completed")
            ]
            base_score = float(pd.to_numeric(base.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").fillna(-math.inf).iloc[0]) if not base.empty else -math.inf
            primary_scores = pd.to_numeric(primary.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").dropna()
            best_primary_score = float(primary_scores.max()) if not primary_scores.empty else -math.inf
            primary_stops = pd.to_numeric(primary.get("p_90d_any_stop_hit", pd.Series(dtype=float)), errors="coerce").dropna()
            max_allowed_stop = (float(primary_stops.min()) + 0.03) if not primary_stops.empty else 0.08
            inside_or_near_budget = bool(worst_90_drawdown >= -660.0 and worst_180_drawdown >= -660.0)
            meaningful_targets = bool((p90_target_300 >= 0.10 or p180_target_300 >= 0.35) and (p90_target_400 >= 0.05 or p180_target_400 >= 0.25))
            improves_base = bool(own_score > base_score)
            improves_primary = bool(own_score > best_primary_score)
            frame.loc[idx, "commodity_required_label"] = COMMODITY_EXPLORATORY_REQUIRED_LABEL
            frame.loc[idx, "commodity_wrapper_warning"] = True
            frame.loc[idx, "exploratory_public_data_warning"] = True
            frame.loc[idx, "not_paper_forward_warning"] = True
            frame.loc[idx, "commodity_risk_control_batch_warning"] = True
            frame.loc[idx, "direct_futures_claim_disallowed"] = True
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            if p90_stop > 0.10 or p180_stop > 0.10 or worst_90_drawdown < -900.0 or worst_180_drawdown < -900.0:
                frame.loc[idx, "profit_verdict"] = "too_risky"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "queue_reason"] = "commodity risk-control row still has excessive stop or drawdown risk"
                frame.loc[idx, "ranking_notes"] = "commodity risk-control row failed the stop/drawdown screen; not candidate_exhaustive queued"
            elif p90_target_300 < 0.05 and p180_target_300 < 0.25 and p90_target_400 < 0.03 and p180_target_400 < 0.15:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "queue_reason"] = "commodity risk-control row reduced risk by diluting target rates too much"
                frame.loc[idx, "ranking_notes"] = "commodity risk-control row is too slow after defensive changes"
            elif improves_base and improves_primary and inside_or_near_budget and p90_stop <= max_allowed_stop and meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "candidate_exhaustive_review_required"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "deserves_candidate_exhaustive"] = True
                frame.loc[idx, "queue_reason"] = "commodity risk-control row improved stop-aware score versus base commodity and a primary benchmark while staying near the drawdown budget"
                frame.loc[idx, "ranking_notes"] = "future candidate_exhaustive review required only; this task did not run candidate_exhaustive"
            elif risk_budget_90d > 1.0 or risk_budget_180d > 1.0:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate_risk_budget_breach" if meaningful_targets else "high_upside_high_risk_watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "high_upside_high_risk_watchlist"
                frame.loc[idx, "queue_reason"] = "commodity risk-control row retains upside but still breaches the -600 drawdown budget"
                frame.loc[idx, "ranking_notes"] = "commodity risk-control row remains high-upside/high-risk watchlist; no candidate_exhaustive queue"
            elif improves_base and meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "commodity risk-control row improved the base commodity score but did not clear the full candidate_exhaustive review gate"
                frame.loc[idx, "ranking_notes"] = "commodity risk-control row deserves research_sample review only"
            else:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "commodity risk-control row did not sufficiently improve base commodity and primary benchmark tradeoffs"
                frame.loc[idx, "ranking_notes"] = "commodity risk-control row is watchlist only; not validated and not paper-forward ready"
        elif frame.loc[idx, "experiment_id"] in GLOBAL_MULTI_ASSET_BATCH1_IDS:
            exp_id = str(frame.loc[idx, "experiment_id"])
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            p180_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            worst_180_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_180d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            risk_budget_90d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_90d"]]), errors="coerce").fillna(0.0).iloc[0])
            risk_budget_180d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_180d"]]), errors="coerce").fillna(0.0).iloc[0])
            own_score = float(pd.to_numeric(pd.Series([frame.loc[idx, "balanced_drawdown_aware_score_v2"]]), errors="coerce").fillna(-math.inf).iloc[0])
            primary = frame[
                frame["experiment_id"].isin(["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"])
                & frame["run_status"].eq("completed")
            ]
            combo = frame[frame["experiment_id"].eq("combo_SPY200d_GLD_50_50_v1") & frame["run_status"].eq("completed")]
            combo_score = float(pd.to_numeric(combo.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").dropna().iloc[0]) if not combo.empty and not pd.to_numeric(combo.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").dropna().empty else -math.inf
            primary_scores = pd.to_numeric(primary.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").dropna()
            best_primary_score = float(primary_scores.max()) if not primary_scores.empty else -math.inf
            primary_stops = pd.to_numeric(primary.get("p_90d_any_stop_hit", pd.Series(dtype=float)), errors="coerce").dropna()
            max_allowed_stop = (float(primary_stops.min()) + 0.03) if not primary_stops.empty else 0.08
            inside_or_near_budget = bool(worst_90_drawdown >= -660.0 and worst_180_drawdown >= -660.0)
            meaningful_targets = bool((p90_target_300 >= 0.10 or p180_target_300 >= 0.35) and (p90_target_400 >= 0.05 or p180_target_400 >= 0.25))
            improves_combo = bool(own_score > combo_score)
            improves_primary = bool(own_score > best_primary_score)
            frame.loc[idx, "global_multi_asset_required_label"] = GLOBAL_MULTI_ASSET_REQUIRED_LABEL
            frame.loc[idx, "global_multi_asset_wrapper_warning"] = True
            frame.loc[idx, "global_multi_asset_batch_warning"] = True
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            if p90_stop > 0.10 or p180_stop > 0.10 or worst_90_drawdown < -900.0 or worst_180_drawdown < -900.0:
                frame.loc[idx, "profit_verdict"] = "too_risky" if not meaningful_targets else "high_upside_high_risk_watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "queue_reason"] = "global multi-asset row still has excessive stop or drawdown risk"
                frame.loc[idx, "ranking_notes"] = "global multi-asset ETF/fund-wrapper exploratory row; too risky for candidate_exhaustive from this run"
            elif p90_target_300 < 0.05 and p180_target_300 < 0.25 and p90_target_400 < 0.03 and p180_target_400 < 0.15:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "queue_reason"] = "global multi-asset row diluted target rates too much"
                frame.loc[idx, "ranking_notes"] = "global multi-asset row is too slow after defensive scaling"
            elif improves_combo and improves_primary and inside_or_near_budget and p90_stop <= max_allowed_stop and meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "candidate_exhaustive_review_required"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "deserves_candidate_exhaustive"] = True
                frame.loc[idx, "queue_reason"] = "global multi-asset row improved stop-aware score versus combo and a primary benchmark while staying near the drawdown budget"
                frame.loc[idx, "ranking_notes"] = "future candidate_exhaustive review required only; this task did not run candidate_exhaustive"
            elif risk_budget_90d > 1.0 or risk_budget_180d > 1.0:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate_risk_budget_breach" if meaningful_targets else "high_upside_high_risk_watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "high_upside_high_risk_watchlist"
                frame.loc[idx, "queue_reason"] = "global multi-asset row retains upside but breaches the -600 drawdown budget"
                frame.loc[idx, "ranking_notes"] = "global multi-asset row remains high-upside/high-risk watchlist; no candidate_exhaustive queue"
            elif improves_combo and meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "global multi-asset row improved combo but did not clear the full candidate_exhaustive review gate"
                frame.loc[idx, "ranking_notes"] = "global multi-asset row deserves research_sample review only"
            else:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "global multi-asset row did not sufficiently improve primary benchmark tradeoffs"
                frame.loc[idx, "ranking_notes"] = "global multi-asset row is watchlist only; not validated and not paper-forward ready"
        elif frame.loc[idx, "experiment_id"] in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS:
            exp_id = str(frame.loc[idx, "experiment_id"])
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p180_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            p180_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_180d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            worst_180_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_180d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            risk_budget_90d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_90d"]]), errors="coerce").fillna(0.0).iloc[0])
            risk_budget_180d = float(pd.to_numeric(pd.Series([frame.loc[idx, "risk_budget_used_180d"]]), errors="coerce").fillna(0.0).iloc[0])
            own_score = float(pd.to_numeric(pd.Series([frame.loc[idx, "balanced_drawdown_aware_score_v2"]]), errors="coerce").fillna(-math.inf).iloc[0])
            primary = frame[
                frame["experiment_id"].isin(["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"])
                & frame["run_status"].eq("completed")
            ]
            primary_scores = pd.to_numeric(primary.get("balanced_drawdown_aware_score_v2", pd.Series(dtype=float)), errors="coerce").dropna()
            best_primary_score = float(primary_scores.max()) if not primary_scores.empty else -math.inf
            primary_stops = pd.to_numeric(primary.get("p_90d_any_stop_hit", pd.Series(dtype=float)), errors="coerce").dropna()
            max_allowed_stop = (float(primary_stops.min()) + 0.03) if not primary_stops.empty else 0.08
            inside_or_near_budget = bool(worst_90_drawdown >= -660.0 and worst_180_drawdown >= -660.0)
            meaningful_targets = bool((p90_target_300 >= 0.10 or p180_target_300 >= 0.35) and (p90_target_400 >= 0.05 or p180_target_400 >= 0.25))
            improves_primary = bool(own_score > best_primary_score)
            frame.loc[idx, "crypto_required_label"] = CRYPTO_TIER2_REQUIRED_LABEL
            frame.loc[idx, "crypto_spot_warning"] = True
            frame.loc[idx, "crypto_tier2_warning"] = True
            frame.loc[idx, "public_or_cached_crypto_data_warning"] = True
            frame.loc[idx, "crypto_not_paper_forward_warning"] = True
            frame.loc[idx, "crypto_no_exchange_execution_warning"] = True
            frame.loc[idx, "crypto_24_7_calendar_warning"] = True
            frame.loc[idx, "direct_futures_claim_disallowed"] = True
            frame.loc[idx, "uses_perpetuals"] = False
            frame.loc[idx, "uses_options"] = False
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            if p90_stop > 0.10 or p180_stop > 0.10 or worst_90_drawdown < -900.0 or worst_180_drawdown < -900.0:
                frame.loc[idx, "profit_verdict"] = "too_risky" if p90_target_300 < 0.10 and p180_target_300 < 0.35 else "high_upside_high_risk_watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 row still has excessive stop or drawdown risk for a strict candidate_exhaustive gate"
                frame.loc[idx, "ranking_notes"] = "crypto spot Tier 2 exploratory row; high-risk/non-final and not paper-forward ready"
            elif p90_target_300 < 0.05 and p180_target_300 < 0.25 and p90_target_400 < 0.03 and p180_target_400 < 0.15:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 risk-control row diluted target rates too much"
                frame.loc[idx, "ranking_notes"] = "crypto spot Tier 2 exploratory row became too slow after risk controls"
            elif improves_primary and inside_or_near_budget and p90_stop <= max_allowed_stop and meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "candidate_exhaustive_review_required"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "deserves_candidate_exhaustive"] = True
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 row improved stop-aware score versus a primary benchmark while staying near the drawdown budget; future review only"
                frame.loc[idx, "ranking_notes"] = "future candidate_exhaustive review required only; this task did not run candidate_exhaustive"
            elif risk_budget_90d > 1.0 or risk_budget_180d > 1.0:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate_risk_budget_breach" if meaningful_targets else "high_upside_high_risk_watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "high_upside_high_risk_watchlist"
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 row retained upside but breached the -600 drawdown budget"
                frame.loc[idx, "ranking_notes"] = "crypto spot Tier 2 exploratory row remains high-upside/high-risk watchlist; no candidate_exhaustive queue"
            elif meaningful_targets:
                frame.loc[idx, "profit_verdict"] = "research_sample_candidate" if exp_id.startswith("combo_plus_") else "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 row has exploratory target power but did not clear strict candidate_exhaustive review requirements"
                frame.loc[idx, "ranking_notes"] = "crypto spot Tier 2 row deserves research_sample review only"
            else:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "crypto Tier 2 row did not sufficiently improve target/risk tradeoffs"
                frame.loc[idx, "ranking_notes"] = "crypto spot Tier 2 exploratory row is watchlist only; not validated and not paper-forward ready"
        elif frame.loc[idx, "experiment_id"] == MANAGED_FUTURES_EXPERIMENT_ID:
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            benchmark_targets = frame[
                frame["experiment_id"].isin(["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"])
                & frame["run_status"].eq("completed")
            ]
            max_benchmark_300 = float(pd.to_numeric(benchmark_targets.get("p_90d_target_300_before_stop", pd.Series(dtype=float)), errors="coerce").fillna(0.0).max()) if not benchmark_targets.empty else 0.0
            max_benchmark_400 = float(pd.to_numeric(benchmark_targets.get("p_90d_target_400_before_stop", pd.Series(dtype=float)), errors="coerce").fillna(0.0).max()) if not benchmark_targets.empty else 0.0
            too_slow = bool(p90_target_300 < 0.05 or (p90_target_300 < max_benchmark_300 and p90_target_400 < max_benchmark_400))
            frame.loc[idx, "required_label"] = MANAGED_FUTURES_REQUIRED_LABEL
            frame.loc[idx, "wrapper_proxy_warning"] = True
            frame.loc[idx, "short_history_warning"] = True
            frame.loc[idx, "wrapper_proxy_only_warning"] = True
            frame.loc[idx, "direct_futures_claim_disallowed"] = True
            frame.loc[idx, "too_slow_warning"] = too_slow
            if p90_stop > 0.08 or worst_90_drawdown < -1000:
                frame.loc[idx, "profit_verdict"] = "too_risky"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "deserves_candidate_exhaustive"] = False
                frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
                frame.loc[idx, "queue_reason"] = "managed-futures proxy row has worse stop/drawdown behavior than allowed for short-history queue"
                frame.loc[idx, "ranking_notes"] = "research-sample-only wrapper proxy row; too risky for short-history candidate_exhaustive gate"
            elif too_slow:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "deserves_candidate_exhaustive"] = False
                frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
                frame.loc[idx, "queue_reason"] = "managed-futures proxy row is too slow versus combo/top2 target rates in this research_sample"
                frame.loc[idx, "ranking_notes"] = "research-sample-only wrapper proxy row; diversification may exist but target potential is too slow"
            elif boolish(frame.loc[idx, "deserves_candidate_exhaustive"]):
                frame.loc[idx, "profit_verdict"] = "candidate_exhaustive_queue_short_history_labeled"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "short-history-labeled research_sample row merits candidate_exhaustive_review_short_history_gate only"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fund-wrapper proxy row; eligible only for later short-history-labeled candidate_exhaustive gate"
            else:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "deserves_candidate_exhaustive"] = False
                frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
                frame.loc[idx, "queue_reason"] = "managed-futures proxy row remains watchlist after short-history research_sample review"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fund-wrapper proxy row; not validated and not paper-forward ready"
        elif frame.loc[idx, "experiment_id"] in COMBINATION_BATCH1_IDS:
            exp_id = str(frame.loc[idx, "experiment_id"])
            p90_target_300 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_300_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_target_400 = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_target_400_before_stop"]]), errors="coerce").fillna(0.0).iloc[0])
            p90_stop = float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(1.0).iloc[0])
            worst_90_drawdown = float(pd.to_numeric(pd.Series([frame.loc[idx, "worst_90d_max_drawdown"]]), errors="coerce").fillna(-math.inf).iloc[0])
            benchmark_targets = frame[
                frame["experiment_id"].isin(["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"])
                & frame["run_status"].eq("completed")
            ]
            max_benchmark_300 = float(pd.to_numeric(benchmark_targets.get("p_90d_target_300_before_stop", pd.Series(dtype=float)), errors="coerce").fillna(0.0).max()) if not benchmark_targets.empty else 0.0
            max_benchmark_400 = float(pd.to_numeric(benchmark_targets.get("p_90d_target_400_before_stop", pd.Series(dtype=float)), errors="coerce").fillna(0.0).max()) if not benchmark_targets.empty else 0.0
            min_benchmark_stop = float(pd.to_numeric(benchmark_targets.get("p_90d_any_stop_hit", pd.Series(dtype=float)), errors="coerce").fillna(1.0).min()) if not benchmark_targets.empty else 1.0
            best_benchmark_drawdown = float(pd.to_numeric(benchmark_targets.get("worst_90d_max_drawdown", pd.Series(dtype=float)), errors="coerce").fillna(-math.inf).max()) if not benchmark_targets.empty else -math.inf
            worse_risk = bool(p90_stop > min_benchmark_stop + 0.02 or worst_90_drawdown < best_benchmark_drawdown - 100.0)
            too_slow = bool(p90_target_300 < max_benchmark_300 and p90_target_400 < max_benchmark_400)
            frame.loc[idx, "fixed_combination_batch_warning"] = True
            if exp_id in COMBINATION_BATCH1_MANAGED_FUTURES_IDS:
                frame.loc[idx, "required_label"] = MANAGED_FUTURES_REQUIRED_LABEL
                frame.loc[idx, "wrapper_proxy_warning"] = True
                frame.loc[idx, "short_history_warning"] = True
                frame.loc[idx, "wrapper_proxy_only_warning"] = True
                frame.loc[idx, "direct_futures_claim_disallowed"] = True
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            if worse_risk:
                frame.loc[idx, "profit_verdict"] = "too_risky"
                frame.loc[idx, "practical_verdict_v2"] = "too_risky"
                frame.loc[idx, "queue_reason"] = "combination batch row worsened stop/drawdown behavior versus combo/top2 gate"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fixed combination; not queued because risk behavior worsened versus primary benchmarks"
            elif too_slow:
                frame.loc[idx, "profit_verdict"] = "too_slow"
                frame.loc[idx, "practical_verdict_v2"] = "too_slow"
                frame.loc[idx, "queue_reason"] = "combination batch row did not improve +300/+400 target rates versus combo/top2"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fixed combination; historical result is too slow or dilutive versus current leaders"
            elif boolish(frame.loc[idx, "duplicate_correlation_warning"]):
                frame.loc[idx, "profit_verdict"] = "duplicate_or_near_duplicate"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "combination batch row has predeclared duplicate/correlation warning and needs separate review"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fixed combination; possible duplicate exposure prevents candidate_exhaustive queue"
            else:
                frame.loc[idx, "profit_verdict"] = "watchlist"
                frame.loc[idx, "practical_verdict_v2"] = "watchlist"
                frame.loc[idx, "queue_reason"] = "combination batch row needs review before any candidate_exhaustive gate"
                frame.loc[idx, "ranking_notes"] = "research-sample-only fixed combination; not candidate_exhaustive queued from this batch"
        elif boolish(frame.loc[idx, "equity_beta_duplicate_warning"]):
            frame.loc[idx, "profit_verdict"] = "duplicate_or_near_duplicate"
            frame.loc[idx, "practical_verdict_v2"] = "watchlist"
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            frame.loc[idx, "queue_reason"] = "equity-beta duplicate warning prevents candidate_exhaustive queue from this research_sample"
            frame.loc[idx, "ranking_notes"] = "research-sample-only row; equity-beta duplicate warning prevents validation-style leader label"
        elif boolish(frame.loc[idx, "concentration_warning"]) or float(pd.to_numeric(pd.Series([frame.loc[idx, "p_90d_any_stop_hit"]]), errors="coerce").fillna(0.0).iloc[0]) > 0.08:
            frame.loc[idx, "profit_verdict"] = "high_upside_high_risk"
            frame.loc[idx, "practical_verdict_v2"] = "high_upside_high_risk"
            frame.loc[idx, "deserves_candidate_exhaustive"] = False
            frame.loc[idx, "candidate_exhaustive_queue_rank"] = math.nan
            frame.loc[idx, "queue_reason"] = "concentration or stop risk prevents candidate_exhaustive queue from this research_sample"
            frame.loc[idx, "ranking_notes"] = "research-sample-only row; concentration or stop risk requires caution"
        elif boolish(frame.loc[idx, "deserves_candidate_exhaustive"]):
            frame.loc[idx, "profit_verdict"] = "candidate_exhaustive_queue"
            frame.loc[idx, "practical_verdict_v2"] = "watchlist"
            frame.loc[idx, "ranking_notes"] = "research-sample-only row; eligible only for later candidate_exhaustive review"
        else:
            frame.loc[idx, "profit_verdict"] = "research_sample_candidate"
            frame.loc[idx, "practical_verdict_v2"] = "watchlist"
            frame.loc[idx, "ranking_notes"] = "research-sample-only row; not validated and not paper-forward ready"
    return frame.reindex(columns=RANKING_COLUMNS).sort_values("rank_overall")


def add_candidate_queue_fields(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["deserves_candidate_exhaustive"] = False
    out["candidate_exhaustive_queue_rank"] = math.nan
    out["queue_reason"] = ""
    if out.empty:
        return out
    spy = out[out["experiment_id"].eq("SPY_200d_trend_model")]
    combo = out[out["experiment_id"].eq("combo_SPY200d_GLD_50_50_v1")]
    spy_score = float(spy["final_score"].iloc[0]) if not spy.empty and pd.notna(spy["final_score"].iloc[0]) else -math.inf
    combo_score = float(combo["final_score"].iloc[0]) if not combo.empty and pd.notna(combo["final_score"].iloc[0]) else -math.inf
    reduced_mode = bool(out["reduced_validation"].map(boolish).any()) if "reduced_validation" in out else False
    queue_mask = (
        out["run_status"].eq("completed")
        & out["profit_results_usable"].map(boolish)
        & out["accounting_integrity_status"].eq("passed")
        & ~out["evidence_tier"].isin(["tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"])
        & ~out["evidence_tier"].eq("benchmark")
        & ~out["profit_verdict"].isin(["too_risky", "high_upside_high_risk", "invalid_accounting", "duplicate_skipped", "incomplete_evidence", "blocked_by_gate"])
        & (pd.to_numeric(out["p_90d_any_stop_hit"], errors="coerce").fillna(1.0) <= 0.08)
        & (pd.to_numeric(out["worst_90d_max_drawdown"], errors="coerce").fillna(-math.inf) >= -1000.0)
        & (
            (pd.to_numeric(out["final_score"], errors="coerce").fillna(-math.inf) > spy_score)
            | (pd.to_numeric(out["final_score"], errors="coerce").fillna(-math.inf) > combo_score)
            | (reduced_mode & out["profit_verdict"].isin(["reduced_validation_leader", "promotion_review_candidate", "leading_profit_candidate"]))
        )
    )
    queued = out[queue_mask].sort_values("final_score", ascending=False)
    for rank, idx in enumerate(queued.index, start=1):
        comparisons: list[str] = []
        score = float(out.at[idx, "final_score"])
        if score > spy_score:
            comparisons.append("SPY_200d")
        if score > combo_score:
            comparisons.append("combo_SPY200d_GLD_50_50")
        out.at[idx, "deserves_candidate_exhaustive"] = True
        out.at[idx, "candidate_exhaustive_queue_rank"] = rank
        if reduced_mode:
            out.at[idx, "queue_reason"] = "reduced 90/180 validation leader/watchlist requires full 30/60/90/180 candidate_exhaustive before any promotion review"
        else:
            out.at[idx, "queue_reason"] = "research_sample accounting-valid row improves diagnostic score versus " + "/".join(comparisons)
    return out


def risk_summary(results: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "experiment_id",
        "display_name",
        "standard_or_stress",
        "run_status",
        "stop_enforced_final_equity",
        "max_drawdown_dollars",
        "max_drawdown_pct",
        "any_project_stop_hit",
        "first_project_stop_date",
        "target_300_before_stop",
        "target_400_before_stop",
        "target_600_before_stop",
        "run_validation_scope",
        "selected_horizons",
        "omitted_horizons",
        "selected_horizons_completed",
        "full_horizon_validation_completed",
        "candidate_exhaustive_completed",
        "reduced_validation",
        "reduced_validation_reason",
        "risk_framework_verdict",
        "profit_verdict",
        "accounting_integrity_status",
        "profit_results_usable",
        "integrity_error_count",
        "integrity_notes",
        "notes",
    ]
    return results.reindex(columns=cols)


def pct_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return "unavailable"
    except (TypeError, ValueError):
        return "unavailable"
    return f"{float(value):.1%}"


def dollar_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return "unavailable"
    except (TypeError, ValueError):
        return "unavailable"
    return f"${float(value):,.2f}"


def compare_text(rankings: pd.DataFrame, left: str, right: str, column: str, label: str, higher_is_better: bool = True) -> str:
    left_row = rankings[rankings["experiment_id"].eq(left)]
    right_row = rankings[rankings["experiment_id"].eq(right)]
    if left_row.empty or right_row.empty or column not in rankings:
        return f"{label}: unavailable."
    left_value = pd.to_numeric(left_row[column], errors="coerce").iloc[0]
    right_value = pd.to_numeric(right_row[column], errors="coerce").iloc[0]
    if pd.isna(left_value) or pd.isna(right_value):
        return f"{label}: unavailable."
    if higher_is_better:
        result = "yes" if left_value > right_value else "no"
    else:
        result = "yes" if left_value < right_value else "no"
    formatter = pct_text if column.startswith("p_") else dollar_text if "equity" in column or "drawdown" in column else lambda x: f"{float(x):,.4f}"
    return f"{label}: {result} ({left} {formatter(left_value)} vs {right} {formatter(right_value)})."


def best_finalist_text(rankings: pd.DataFrame, finalists: list[str], column: str, label: str, higher_is_better: bool = True) -> str:
    if not finalists or column not in rankings:
        return f"{label}: unavailable."
    subset = rankings[rankings["experiment_id"].isin(finalists) & rankings["run_status"].eq("completed")].copy()
    if subset.empty:
        return f"{label}: unavailable."
    subset["_metric"] = pd.to_numeric(subset[column], errors="coerce")
    subset = subset.dropna(subset=["_metric"])
    if subset.empty:
        return f"{label}: unavailable."
    row = subset.sort_values("_metric", ascending=not higher_is_better).iloc[0]
    formatter = pct_text if column.startswith("p_") else dollar_text if "equity" in column or "drawdown" in column else lambda x: f"{float(x):,.4f}"
    return f"{label}: {row['experiment_id']} ({formatter(row['_metric'])})."


def build_finalist_comparison_section(rolling: pd.DataFrame, rankings: pd.DataFrame, finalist_ids: list[str], mode: str, args: argparse.Namespace | None = None) -> str:
    if not finalist_ids:
        return ""
    selected_horizons = selected_horizons_for_args(args) if args is not None else HORIZONS.copy()
    omitted_horizons = [horizon for horizon in HORIZONS if horizon not in selected_horizons]
    reduced = bool(omitted_horizons)
    completed = rankings[rankings["experiment_id"].isin(finalist_ids) & rankings["run_status"].eq("completed")]
    exact_rows = rolling[
        rolling["experiment_id"].isin(finalist_ids)
        & rolling["rolling_method"].eq("all_possible")
        & rolling["evidence_finality"].isin(["exact_all_possible", "exact_selected_horizons"])
    ]
    non_final = rolling[
        rolling["experiment_id"].isin(finalist_ids)
        & ~rolling["evidence_finality"].isin(["exact_all_possible", "exact_selected_horizons"])
    ]
    standard_90 = rolling[
        rolling["experiment_id"].isin(finalist_ids)
        & rolling["horizon"].eq(90)
        & rolling["standard_or_stress"].eq("standard")
    ]
    required_pairs = {(exp_id, horizon, label) for exp_id in finalist_ids for horizon in selected_horizons for label in LABEL_COSTS}
    observed_pairs = {
        (str(row["experiment_id"]), int(row["horizon"]), str(row["standard_or_stress"]))
        for _, row in exact_rows.iterrows()
    }
    selected_all_possible_completed = bool(required_pairs) and required_pairs.issubset(observed_pairs)
    full_horizon_completed = selected_all_possible_completed and not reduced
    candidate_exhaustive_completed = bool(mode == "candidate_exhaustive" and full_horizon_completed)
    incomplete_finalists = [
        exp_id
        for exp_id in finalist_ids
        if rankings[rankings["experiment_id"].eq(exp_id)].empty
        or not rankings[rankings["experiment_id"].eq(exp_id)]["run_status"].eq("completed").any()
    ]

    def rolling_metric_lines(horizon: int, label: str) -> str:
        subset = rolling[
            rolling["experiment_id"].isin(finalist_ids)
            & rolling["horizon"].eq(horizon)
            & rolling["standard_or_stress"].eq(label)
        ]
        if subset.empty:
            return f"### {horizon}-day {label}\n\nUnavailable."
        lines = [
            f"### {horizon}-day {label}",
            "",
        ]
        for _, row in subset.sort_values("experiment_id").iterrows():
            lines.append(
                f"- {row['experiment_id']}: +300 {pct_text(row['p_target_300_before_stop'])}; "
                f"+400 {pct_text(row['p_target_400_before_stop'])}; "
                f"+600 {pct_text(row['p_target_600_before_stop'])}; "
                f"+900 {pct_text(row['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(row['p_target_1200_before_stop'])}; "
                f"stop {pct_text(row['p_any_project_stop_hit'])}; "
                f"median {dollar_text(row['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(row['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(row['worst_max_drawdown'])}"
            )
        return "\n".join(lines)

    horizon_blocks = "\n\n".join(
        rolling_metric_lines(horizon, label)
        for horizon in selected_horizons
        for label in LABEL_COSTS
    )

    def compare_across_rolling(left: str, right: str, column: str, label: str, higher_is_better: bool = True) -> str:
        subset = rolling[
            rolling["experiment_id"].isin([left, right])
            & rolling["horizon"].isin(selected_horizons)
            & rolling["standard_or_stress"].isin(LABEL_COSTS)
        ]
        if subset.empty or column not in subset:
            return f"{label}: unavailable."
        left_rows = subset[subset["experiment_id"].eq(left)].set_index(["horizon", "standard_or_stress"])
        right_rows = subset[subset["experiment_id"].eq(right)].set_index(["horizon", "standard_or_stress"])
        shared = left_rows.index.intersection(right_rows.index)
        if len(shared) == 0:
            return f"{label}: unavailable."
        left_values = pd.to_numeric(left_rows.loc[shared, column], errors="coerce")
        right_values = pd.to_numeric(right_rows.loc[shared, column], errors="coerce")
        valid = ~(left_values.isna() | right_values.isna())
        if not valid.any():
            return f"{label}: unavailable."
        left_values = left_values[valid]
        right_values = right_values[valid]
        wins = (left_values > right_values) if higher_is_better else (left_values < right_values)
        win_count = int(wins.sum())
        total = int(valid.sum())
        if win_count == total:
            verdict = "yes"
        elif win_count == 0:
            verdict = "no"
        else:
            verdict = "mixed"
        formatter = pct_text if column.startswith("p_") else dollar_text if "equity" in column or "drawdown" in column else lambda x: f"{float(x):,.4f}"
        return (
            f"{label}: {verdict}; {left} better in {win_count}/{total} selected horizon/cost rows "
            f"(average {left} {formatter(left_values.mean())} vs {right} {formatter(right_values.mean())})."
        )

    if standard_90.empty:
        ladder_lines = "90-day finalist rolling rows were unavailable."
    else:
        ladder_lines = "\n".join(
            [
                f"- {row['experiment_id']}: +300 {pct_text(row['p_target_300_before_stop'])}; "
                f"+400 {pct_text(row['p_target_400_before_stop'])}; "
                f"+600 {pct_text(row['p_target_600_before_stop'])}; "
                f"+900 {pct_text(row['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(row['p_target_1200_before_stop'])}; "
                f"stop {pct_text(row['p_any_project_stop_hit'])}; "
                f"median {dollar_text(row['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(row['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(row['worst_max_drawdown'])}"
                for _, row in standard_90.sort_values("experiment_id").iterrows()
            ]
        )
    best_risk = "Best drawdown control: unavailable."
    if not completed.empty:
        risk_subset = completed.copy()
        risk_subset["_stop"] = pd.to_numeric(risk_subset["p_90d_any_stop_hit"], errors="coerce").fillna(999.0)
        risk_subset["_drawdown"] = pd.to_numeric(risk_subset["worst_90d_max_drawdown"], errors="coerce").fillna(-999999.0)
        risk_subset["_median"] = pd.to_numeric(risk_subset["median_90d_stop_enforced_final_equity"], errors="coerce").fillna(-999999.0)
        risk_row = risk_subset.sort_values(["_stop", "_drawdown", "_median"], ascending=[True, False, False]).iloc[0]
        best_risk = f"Best drawdown/risk control: {risk_row['experiment_id']} (stop {pct_text(risk_row['p_90d_any_stop_hit'])}; worst drawdown {dollar_text(risk_row['worst_90d_max_drawdown'])})."
    promotion_rows = rankings[
        rankings["experiment_id"].isin(finalist_ids)
        & rankings["profit_verdict"].isin(["reduced_validation_leader", "promotion_review_candidate", "leading_profit_candidate"])
    ]["experiment_id"].astype(str).tolist()
    full_queue_rows = rankings[
        rankings["experiment_id"].isin(finalist_ids)
        & rankings.get("deserves_candidate_exhaustive", pd.Series(dtype=bool)).map(boolish)
    ]["experiment_id"].astype(str).tolist()
    section_title = "Reduced Finalist Validation Comparison" if reduced else "Full Candidate-Exhaustive Finalist Validation Comparison"
    queue_label = "Full overnight 30/60/90/180 candidate_exhaustive queue"
    if full_horizon_completed:
        queue_label = "Promotion-review candidates after full 30/60/90/180 candidate_exhaustive"
    exact_scope_line = (
        "This run completed all requested 30/60/90/180 horizons with all_possible windows; no horizons are omitted."
        if full_horizon_completed
        else "This run is exact only for selected horizons if selected_horizons_completed is true; omitted horizons remain non-final."
    )
    return f"""
## {section_title}

- mode: {mode}
- run_validation_scope: {"finalist_reduced_90_180" if reduced and selected_horizons == [90, 180] else ("reduced_horizon_validation" if reduced else "all_horizons")}
- requested finalists: {', '.join(finalist_ids)}
- selected_horizons: {','.join(map(str, selected_horizons))}
- omitted_horizons: {','.join(map(str, omitted_horizons)) if omitted_horizons else 'none'}
- selected_horizons_completed: {str(selected_all_possible_completed).lower()}
- full_horizon_validation_completed: {str(full_horizon_completed).lower()}
- candidate_exhaustive_completed: {str(candidate_exhaustive_completed).lower()}
- all_possible_30_60_90_180_standard_and_stress_completed: {str(full_horizon_completed).lower()}
- incomplete_or_nonfinal_finalists: {', '.join(incomplete_finalists) if incomplete_finalists else ('non-final rolling rows present' if not non_final.empty else 'none')}

Full-horizon finalist metrics:

{horizon_blocks}

90-day standard finalist metrics:

{ladder_lines}

Direct full-horizon comparison answers:

- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_target_300_before_stop', 'combo beat SPY_200d on +300 across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_target_400_before_stop', 'combo beat SPY_200d on +400 across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_target_600_before_stop', 'combo beat SPY_200d on +600 across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_target_900_before_stop', 'combo beat SPY_200d on +900 across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_target_1200_before_stop', 'combo beat SPY_200d on +1200 across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_any_project_stop_hit', 'combo had lower stop-hit rate than SPY_200d across the full horizon set', higher_is_better=False)}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'worst_max_drawdown', 'combo had better worst drawdown than SPY_200d across the full horizon set')}
- {compare_across_rolling('combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'median_stop_enforced_final_equity', 'combo had higher median stop-enforced equity than SPY_200d across the full horizon set')}
- {compare_across_rolling('asset_class_tsmom_top2_v1', 'SPY_200d_trend_model', 'median_stop_enforced_final_equity', 'asset_class_tsmom_top2 beat SPY_200d on median stop-enforced equity across the full horizon set')}
- {compare_across_rolling('asset_class_tsmom_top2_v1', 'combo_SPY200d_GLD_50_50_v1', 'median_stop_enforced_final_equity', 'asset_class_tsmom_top2 beat combo on median stop-enforced equity across the full horizon set')}
- {compare_across_rolling('asset_class_tsmom_equal_weight_v1', 'SPY_200d_trend_model', 'median_stop_enforced_final_equity', 'asset_class_tsmom_equal_weight beat SPY_200d on median stop-enforced equity across the full horizon set')}
- {compare_across_rolling('asset_class_tsmom_equal_weight_v1', 'combo_SPY200d_GLD_50_50_v1', 'median_stop_enforced_final_equity', 'asset_class_tsmom_equal_weight beat combo on median stop-enforced equity across the full horizon set')}

90-day ranking comparison answers:

- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_target_300_before_stop', 'combo beat SPY_200d on +300')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_target_400_before_stop', 'combo beat SPY_200d on +400')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_target_600_before_stop', 'combo beat SPY_200d on +600')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_target_900_before_stop', 'combo beat SPY_200d on +900')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_target_1200_before_stop', 'combo beat SPY_200d on +1200')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'median_90d_stop_enforced_final_equity', 'combo had higher median stop-enforced equity')}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'p_90d_any_stop_hit', 'combo had lower stop-hit rate', higher_is_better=False)}
- {compare_text(rankings, 'combo_SPY200d_GLD_50_50_v1', 'SPY_200d_trend_model', 'worst_90d_max_drawdown', 'combo had better worst drawdown')}
- {compare_text(rankings, 'asset_class_tsmom_top2_v1', 'SPY_200d_trend_model', 'final_score', 'asset_class_tsmom_top2 beat SPY_200d on combined score')}
- {compare_text(rankings, 'asset_class_tsmom_top2_v1', 'combo_SPY200d_GLD_50_50_v1', 'final_score', 'asset_class_tsmom_top2 beat combo on combined score')}
- {compare_text(rankings, 'asset_class_tsmom_equal_weight_v1', 'SPY_200d_trend_model', 'final_score', 'asset_class_tsmom_equal_weight beat SPY_200d on combined score')}
- {compare_text(rankings, 'asset_class_tsmom_equal_weight_v1', 'combo_SPY200d_GLD_50_50_v1', 'final_score', 'asset_class_tsmom_equal_weight beat combo on combined score')}

Finalist leaders:

- {best_finalist_text(rankings, finalist_ids, 'p_90d_target_300_before_stop', 'Best +300 rate')}
- {best_finalist_text(rankings, finalist_ids, 'p_90d_target_400_before_stop', 'Best +400 rate')}
- {best_finalist_text(rankings, finalist_ids, 'p_90d_target_600_before_stop', 'Best +600 rate')}
- {best_finalist_text(rankings, finalist_ids, 'p_90d_target_900_before_stop', 'Best +900 rate')}
- {best_finalist_text(rankings, finalist_ids, 'p_90d_target_1200_before_stop', 'Best +1200 rate')}
- {best_finalist_text(rankings, finalist_ids, 'median_90d_stop_enforced_final_equity', 'Highest median stop-enforced equity')}
- {best_finalist_text(rankings, finalist_ids, 'p95_90d_stop_enforced_final_equity', 'Best p95 upside tail')}
- {best_risk}
- {best_finalist_text(rankings, finalist_ids, 'final_score', 'Best overall profit/risk tradeoff')}

Interpretation:

- GLD_buy_hold remains high-upside/high-risk if its stop-hit or drawdown penalty dominates the combined score.
- SPY_buy_hold remains too risky if its drawdown/stop behavior overwhelms target upside.
- BIL_cash_proxy remains the defensive benchmark and is too slow for the profit target ladder.
- Promotion-review rows: {', '.join(promotion_rows) if promotion_rows else 'none'}.
- {queue_label}: {', '.join(full_queue_rows) if full_queue_rows else 'none'}.
- {exact_scope_line}
- No finalist is automatically paper-forward ready, and SPY_200d_trend_model remains the frozen paper-forward observation unless a separate promotion process changes it.
- No real-money recommendation is made.
"""


def build_profit_score_audit_section(rankings: pd.DataFrame) -> str:
    required = {
        "experiment_id",
        "final_score",
        "profit_seeking_score",
        "balanced_score",
        "drawdown_control_score",
        "rank_profit_seeking_score",
        "rank_balanced_score",
        "rank_drawdown_control_score",
    }
    if rankings.empty or not required.issubset(rankings.columns):
        return ""

    def leader(column: str) -> str:
        subset = rankings[rankings["run_status"].eq("completed")].copy()
        if subset.empty or column not in subset:
            return "unavailable"
        subset["_metric"] = pd.to_numeric(subset[column], errors="coerce")
        subset = subset.dropna(subset=["_metric"])
        if subset.empty:
            return "unavailable"
        row = subset.sort_values("_metric", ascending=False).iloc[0]
        return f"{row['experiment_id']} ({float(row['_metric']):,.2f})"

    top2 = rankings[rankings["experiment_id"].eq("asset_class_tsmom_top2_v1")]
    combo = rankings[rankings["experiment_id"].eq("combo_SPY200d_GLD_50_50_v1")]
    if top2.empty or combo.empty:
        comparison = "Top2/combo comparison unavailable in this packet."
    else:
        top2_row = top2.iloc[0]
        combo_row = combo.iloc[0]
        comparison = (
            "The original final_score ranked asset_class_tsmom_top2_v1 above "
            "combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates "
            "and lower stress degradation. The combo had better median equity, p95 equity, expected profit, "
            "stop behavior, and worst drawdown, but the original drawdown penalty only applies after the "
            "-$600 budget is breached."
        )
        comparison += (
            f" Original final_score: top2 {float(top2_row['final_score']):,.4f}; "
            f"combo {float(combo_row['final_score']):,.4f}."
        )

    return f"""
## Profit Score Audit

{comparison}

Alternative diagnostic score leaders:

- profit_seeking_score leader: {leader('profit_seeking_score')}
- balanced_score leader: {leader('balanced_score')}
- drawdown_control_score leader: {leader('drawdown_control_score')}

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.
"""


def build_drawdown_aware_v2_section(rankings: pd.DataFrame) -> str:
    required = {
        "experiment_id",
        "final_score",
        "balanced_drawdown_aware_score_v2",
        "rank_balanced_drawdown_aware_v2",
        "practical_verdict_v2",
    }
    if rankings.empty or not required.issubset(rankings.columns):
        return ""

    def leader(column: str, include_benchmarks: bool = True) -> str:
        subset = rankings[rankings["run_status"].eq("completed")].copy()
        if not include_benchmarks:
            subset = subset[~subset["evidence_tier"].isin(["benchmark", "tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"])]
        if subset.empty or column not in subset:
            return "unavailable"
        subset["_metric"] = pd.to_numeric(subset[column], errors="coerce")
        subset = subset.dropna(subset=["_metric"])
        if subset.empty:
            return "unavailable"
        row = subset.sort_values("_metric", ascending=False).iloc[0]
        return f"{row['experiment_id']} ({float(row['_metric']):,.2f})"

    def verdict(exp_id: str) -> str:
        row = rankings[rankings["experiment_id"].eq(exp_id)]
        if row.empty:
            return "unavailable"
        return str(row["practical_verdict_v2"].iloc[0])

    original_leader = leader("final_score")
    v2_leader = leader("balanced_drawdown_aware_score_v2")
    practical_rows = rankings[rankings["practical_verdict_v2"].eq("practical_leader")]
    practical_leader = practical_rows["experiment_id"].iloc[0] if not practical_rows.empty else "unavailable"
    full_horizon_completed = bool(rankings["full_horizon_validation_completed"].map(boolish).all()) if "full_horizon_validation_completed" in rankings and not rankings.empty else False
    packet_phrase = "this full-horizon candidate-exhaustive packet" if full_horizon_completed else "this reduced packet"
    validation_next_step = (
        "Full 30/60/90/180 candidate_exhaustive completed for this finalist packet; a separate promotion review is still required before any paper-forward decision."
        if full_horizon_completed
        else "Full 30/60/90/180 candidate_exhaustive is still needed before any promotion or paper-forward decision."
    )
    top2_row = rankings[rankings["experiment_id"].eq("asset_class_tsmom_top2_v1")]
    combo_row = rankings[rankings["experiment_id"].eq("combo_SPY200d_GLD_50_50_v1")]
    if not top2_row.empty and not combo_row.empty:
        comparison = (
            f"combo v2 score {float(combo_row['balanced_drawdown_aware_score_v2'].iloc[0]):,.2f} "
            f"versus top2 {float(top2_row['balanced_drawdown_aware_score_v2'].iloc[0]):,.2f}; "
            f"combo risk budget used 90d/180d {float(combo_row['risk_budget_used_90d'].iloc[0]):.2f}/"
            f"{float(combo_row['risk_budget_used_180d'].iloc[0]):.2f} versus top2 "
            f"{float(top2_row['risk_budget_used_90d'].iloc[0]):.2f}/"
            f"{float(top2_row['risk_budget_used_180d'].iloc[0]):.2f}."
        )
    else:
        comparison = "combo/top2 comparison unavailable."

    return f"""
## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: {original_leader}.
- Drawdown-aware v2 leader: {v2_leader}.
- Practical leader after v2: {practical_leader}.
- Combo/top2 comparison: {comparison}
- combo_SPY200d_GLD_50_50_v1 verdict: {verdict('combo_SPY200d_GLD_50_50_v1')}; v2 confirms it as the robust practical challenger in {packet_phrase}.
- asset_class_tsmom_top2_v1 verdict: {verdict('asset_class_tsmom_top2_v1')}; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: {verdict('GLD_buy_hold')}; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: {verdict('SPY_buy_hold')}; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: {verdict('BIL_cash_proxy')}; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- {validation_next_step}
- No real-money recommendation is made.
"""


def build_qqq_research_sample_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    qqq_result = results[
        results["experiment_id"].eq(QQQ_EXPERIMENT_ID)
        & results["standard_or_stress"].eq("standard")
    ] if not results.empty and "experiment_id" in results else pd.DataFrame()
    qqq_rank = rankings[rankings["experiment_id"].eq(QQQ_EXPERIMENT_ID)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if qqq_result.empty and qqq_rank.empty:
        return ""

    row = qqq_result.iloc[0] if not qqq_result.empty else pd.Series(dtype=object)
    rank = qqq_rank.iloc[0] if not qqq_rank.empty else pd.Series(dtype=object)

    def value(column: str, default: Any = "unavailable") -> Any:
        if column in row and pd.notna(row[column]):
            return row[column]
        if column in rank and pd.notna(rank[column]):
            return rank[column]
        return default

    def qqq_rolling_lines() -> str:
        subset = rolling[
            rolling["experiment_id"].eq(QQQ_EXPERIMENT_ID)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "QQQ rolling rows are unavailable."
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"- {int(metric['horizon'])}d: +300 {pct_text(metric['p_target_300_before_stop'])}; "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}; "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}; "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}; "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}; "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "\n".join(lines)

    def compare_to(other: str, label: str) -> str:
        if qqq_rank.empty or other not in set(rankings.get("experiment_id", pd.Series(dtype=str)).astype(str)):
            return f"{label}: unavailable."
        parts = [
            compare_text(rankings, QQQ_EXPERIMENT_ID, other, "final_score", f"{label} on original final_score"),
            compare_text(rankings, QQQ_EXPERIMENT_ID, other, "balanced_drawdown_aware_score_v2", f"{label} on drawdown-aware v2 score"),
            compare_text(rankings, QQQ_EXPERIMENT_ID, other, "p_90d_target_300_before_stop", f"{label} on 90d +300"),
            compare_text(rankings, QQQ_EXPERIMENT_ID, other, "p_90d_target_400_before_stop", f"{label} on 90d +400"),
            compare_text(rankings, QQQ_EXPERIMENT_ID, other, "worst_90d_max_drawdown", f"{label} on 90d worst drawdown"),
        ]
        return "\n  - " + "\n  - ".join(parts)

    qqq_freq = pct_text(value("qqq_selection_frequency", math.nan))
    spy_freq = pct_text(value("spy_selection_frequency", math.nan))
    gld_freq = pct_text(value("gld_selection_frequency", math.nan))
    ief_freq = pct_text(value("ief_selection_frequency", math.nan))
    bil_freq = pct_text(value("bil_allocation_frequency", math.nan))
    equity_share = pct_text(value("equity_asset_allocation_share", math.nan))
    defensive_share = pct_text(value("defensive_asset_allocation_share", math.nan))
    concentration = boolish(value("concentration_warning", False))
    equity_beta = boolish(value("equity_beta_duplicate_warning", False))
    verdict = str(value("profit_verdict", "unavailable"))
    deserves = boolish(value("deserves_candidate_exhaustive", False))
    qqq_data_available = str(value("run_status", "")).lower() == "completed"
    downloaded = "false"
    diversification_text = (
        "QQQ mostly added equity-beta exposure because QQQ+SPY allocation share exceeded the concentration review threshold."
        if equity_beta
        else "QQQ did not trip the equity-beta duplicate warning in this research_sample packet."
    )

    return f"""
## QQQ Dual Momentum Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. QQQ data available from cache: {str(qqq_data_available).lower()}.
2. Data downloaded: {downloaded}. The run used existing local cache only.
3. Rule: monthly rebalance; rank QQQ, SPY, GLD, and IEF by 126-trading-day return; hold the top 1 asset only if return is positive and close is above its 200-day SMA; otherwise hold BIL. Weights become effective on the next trading day after the signal.
4. QQQ selected: {qqq_freq}.
5. SPY selected: {spy_freq}.
6. GLD/IEF/BIL selected: GLD {gld_freq}; IEF {ief_freq}; BIL {bil_freq}.
7. QQQ +300/+400 target rates: see target ladder below; compare against top2/combo/SPY_200d in the direct comparisons.
8. QQQ +600/+900/+1200 upside: see target ladder below.
9. QQQ drawdown/stop risk: see stop/worst-drawdown rows below; concentration_warning={str(concentration).lower()}.
10. Equity beta interpretation: {diversification_text} Equity allocation share={equity_share}; defensive allocation share={defensive_share}.
11. QQQ versus asset_class_tsmom_top2_v1:{compare_to('asset_class_tsmom_top2_v1', 'QQQ beat top2')}
12. QQQ versus combo_SPY200d_GLD_50_50_v1:{compare_to('combo_SPY200d_GLD_50_50_v1', 'QQQ beat combo')}
13. QQQ versus SPY_200d_trend_model:{compare_to('SPY_200d_trend_model', 'QQQ beat SPY_200d')}
14. Future candidate_exhaustive deserved: {str(deserves).lower()}. Current verdict: {verdict}.
15. No real-money recommendation is made.

QQQ target/risk ladder:

{qqq_rolling_lines()}
"""


def build_value_momentum_research_sample_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    value_result = results[
        results["experiment_id"].eq(VALUE_MOMENTUM_EXPERIMENT_ID)
        & results["standard_or_stress"].eq("standard")
    ] if not results.empty and "experiment_id" in results else pd.DataFrame()
    value_rank = rankings[rankings["experiment_id"].eq(VALUE_MOMENTUM_EXPERIMENT_ID)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if value_result.empty and value_rank.empty:
        return ""

    row = value_result.iloc[0] if not value_result.empty else pd.Series(dtype=object)
    rank = value_rank.iloc[0] if not value_rank.empty else pd.Series(dtype=object)

    def value(column: str, default: Any = "unavailable") -> Any:
        if column in row and pd.notna(row[column]):
            return row[column]
        if column in rank and pd.notna(rank[column]):
            return rank[column]
        return default

    def ladder_lines() -> str:
        subset = rolling[
            rolling["experiment_id"].eq(VALUE_MOMENTUM_EXPERIMENT_ID)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "Value/momentum rolling rows are unavailable."
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"- {int(metric['horizon'])}d: +300 {pct_text(metric['p_target_300_before_stop'])}; "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}; "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}; "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}; "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}; "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "\n".join(lines)

    def compare_to(other: str, label: str) -> str:
        if value_rank.empty or other not in set(rankings.get("experiment_id", pd.Series(dtype=str)).astype(str)):
            return f"{label}: unavailable."
        parts = [
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "balanced_drawdown_aware_score_v2", f"{label} on drawdown-aware v2 score"),
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "final_score", f"{label} on original final_score"),
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "p_90d_target_300_before_stop", f"{label} on 90d +300"),
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "p_90d_target_400_before_stop", f"{label} on 90d +400"),
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "p_90d_any_stop_hit", f"{label} on 90d stop-hit rate", higher_is_better=False),
            compare_text(rankings, VALUE_MOMENTUM_EXPERIMENT_ID, other, "worst_90d_max_drawdown", f"{label} on 90d worst drawdown"),
        ]
        return "\n  - " + "\n  - ".join(parts)

    data_available = str(value("run_status", "")).lower() == "completed"
    mtum_freq = pct_text(value("mtum_selection_frequency", math.nan))
    vtv_freq = pct_text(value("vtv_selection_frequency", math.nan))
    qual_freq = pct_text(value("qual_selection_frequency", math.nan))
    usmv_freq = pct_text(value("usmv_selection_frequency", math.nan))
    spy_freq = pct_text(value("spy_selection_frequency", math.nan))
    bil_freq = pct_text(value("bil_allocation_frequency", math.nan))
    mtum_share = pct_text(value("mtum_allocation_share", math.nan))
    vtv_share = pct_text(value("vtv_allocation_share", math.nan))
    qual_share = pct_text(value("qual_allocation_share", math.nan))
    usmv_share = pct_text(value("usmv_allocation_share", math.nan))
    spy_share = pct_text(value("spy_allocation_share", math.nan))
    bil_share = pct_text(value("bil_allocation_share", math.nan))
    equity_share = pct_text(value("equity_factor_allocation_share", math.nan))
    cash_share = pct_text(value("cash_treasury_allocation_share", math.nan))
    concentration = boolish(value("concentration_warning", False))
    equity_beta = boolish(value("equity_beta_duplicate_warning", False))
    verdict = str(value("profit_verdict", "unavailable"))
    deserves = boolish(value("deserves_candidate_exhaustive", False))
    equity_beta_text = (
        "The row tripped the equity-beta duplicate warning because equity-factor ETF exposure dominated allocations."
        if equity_beta
        else "The row did not trip the equity-beta duplicate warning in this research_sample packet."
    )

    return f"""
## Value/Momentum Factor ETF Rotation Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. Data available from cache: {str(data_available).lower()}. Cached implementation universe: MTUM, VTV, QUAL, USMV, SPY, BIL.
2. Data downloaded: false. The run used existing local cache only.
3. Rule: monthly rebalance; rank MTUM, VTV, QUAL, USMV, and SPY by 126-trading-day return; assets qualify only when return is positive and close is above the 200-day SMA; hold up to the top 2 qualifying assets at 50% each; unused weight goes to BIL; weights become effective on the next trading day after the signal.
4. Selection/allocation frequencies: MTUM selected {mtum_freq} / allocation {mtum_share}; VTV selected {vtv_freq} / allocation {vtv_share}; QUAL selected {qual_freq} / allocation {qual_share}; USMV selected {usmv_freq} / allocation {usmv_share}; SPY selected {spy_freq} / allocation {spy_share}; BIL fallback {bil_freq} / allocation {bil_share}.
5. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
6. +600/+900/+1200 upside: see target ladder below.
7. Drawdown/stop risk: see stop and worst-drawdown rows below; concentration_warning={str(concentration).lower()}.
8. Equity-beta duplication: {equity_beta_text} Equity-factor allocation share={equity_share}; cash/Treasury allocation share={cash_share}.
9. Value/momentum versus combo_SPY200d_GLD_50_50_v1:{compare_to('combo_SPY200d_GLD_50_50_v1', 'Value/momentum beat combo')}
10. Value/momentum versus asset_class_tsmom_top2_v1:{compare_to('asset_class_tsmom_top2_v1', 'Value/momentum beat top2')}
11. Value/momentum versus SPY_200d_trend_model:{compare_to('SPY_200d_trend_model', 'Value/momentum beat SPY_200d')}
12. Value/momentum versus QQQ dual momentum on stop-aware risk:{compare_to(QQQ_EXPERIMENT_ID, 'Value/momentum beat QQQ dual momentum')}
13. Future candidate_exhaustive deserved: {str(deserves).lower()}. Current verdict: {verdict}.
14. No real-money recommendation is made.

Value/momentum target/risk ladder:

{ladder_lines()}
"""


def build_sector_top2_research_sample_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    sector_result = results[
        results["experiment_id"].eq(SECTOR_TOP2_EXPERIMENT_ID)
        & results["standard_or_stress"].eq("standard")
    ] if not results.empty and "experiment_id" in results else pd.DataFrame()
    sector_rank = rankings[rankings["experiment_id"].eq(SECTOR_TOP2_EXPERIMENT_ID)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if sector_result.empty and sector_rank.empty:
        return ""

    row = sector_result.iloc[0] if not sector_result.empty else pd.Series(dtype=object)
    rank = sector_rank.iloc[0] if not sector_rank.empty else pd.Series(dtype=object)

    def value(column: str, default: Any = "unavailable") -> Any:
        if column in row and pd.notna(row[column]):
            return row[column]
        if column in rank and pd.notna(rank[column]):
            return rank[column]
        return default

    def ladder_lines() -> str:
        subset = rolling[
            rolling["experiment_id"].eq(SECTOR_TOP2_EXPERIMENT_ID)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "Sector top2 rolling rows are unavailable."
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"- {int(metric['horizon'])}d: +300 {pct_text(metric['p_target_300_before_stop'])}; "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}; "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}; "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}; "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}; "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "\n".join(lines)

    def compare_to(other: str, label: str) -> str:
        if sector_rank.empty or other not in set(rankings.get("experiment_id", pd.Series(dtype=str)).astype(str)):
            return f"{label}: unavailable."
        parts = [
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "balanced_drawdown_aware_score_v2", f"{label} on drawdown-aware v2 score"),
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "final_score", f"{label} on original final_score"),
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "p_90d_target_300_before_stop", f"{label} on 90d +300"),
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "p_90d_target_400_before_stop", f"{label} on 90d +400"),
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "p_90d_any_stop_hit", f"{label} on 90d stop-hit rate", higher_is_better=False),
            compare_text(rankings, SECTOR_TOP2_EXPERIMENT_ID, other, "worst_90d_max_drawdown", f"{label} on 90d worst drawdown"),
        ]
        return "\n  - " + "\n  - ".join(parts)

    sector_parts = []
    for symbol in SECTOR_TOP2_SYMBOLS:
        lower = symbol.lower()
        sector_parts.append(
            f"{symbol} selected {pct_text(value(f'{lower}_selection_frequency', math.nan))} / "
            f"allocation {pct_text(value(f'{lower}_allocation_share', math.nan))}"
        )
    data_available = str(value("run_status", "")).lower() == "completed"
    bil_freq = pct_text(value("bil_allocation_frequency", math.nan))
    bil_share = pct_text(value("bil_allocation_share", math.nan))
    sector_share = pct_text(value("equity_sector_allocation_share", math.nan))
    cash_share = pct_text(value("cash_treasury_allocation_share", math.nan))
    max_sector = pct_text(value("max_single_sector_allocation", math.nan))
    turnover = pct_text(value("sector_turnover", math.nan))
    concentration = boolish(value("concentration_warning", False))
    equity_beta = boolish(value("equity_beta_duplicate_warning", False))
    verdict = str(value("profit_verdict", "unavailable"))
    deserves = boolish(value("deserves_candidate_exhaustive", False))
    equity_beta_text = (
        "The row tripped the equity-beta duplicate warning because core sector exposure dominated allocations."
        if equity_beta
        else "The row did not trip the equity-beta duplicate warning in this research_sample packet."
    )

    return f"""
## Sector Top-2 Momentum Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. Data available from cache: {str(data_available).lower()}. Cached implementation universe: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, BIL.
2. Data downloaded: false. The run used existing local cache only.
3. Universe used: core_nine_fixed_universe = XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, with BIL fallback.
4. XLC and XLRE excluded: true. XLC is excluded for late-inception risk; XLRE is excluded because it is not cached.
5. Rule: monthly rebalance; rank core-nine sector ETFs by 126-trading-day return; a sector qualifies only when 126-day return is positive and close is above the 200-day SMA; hold up to the top 2 qualifying sectors at 50% each; unused weight goes to BIL; if no sector qualifies, hold 100% BIL; weights become effective on the next trading day after the signal.
6. Sector selection/allocation frequencies: {'; '.join(sector_parts)}.
7. BIL fallback/allocation frequency: BIL selected {bil_freq} / allocation {bil_share}.
8. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
9. +600/+900/+1200 upside: see target ladder below.
10. Drawdown/stop risk: see stop and worst-drawdown rows below; concentration_warning={str(concentration).lower()}.
11. Equity-beta duplication: {equity_beta_text} Equity-sector allocation share={sector_share}; cash/Treasury allocation share={cash_share}.
12. Sector dominance: max_single_sector_allocation={max_sector}; top_sector_dominance={max_sector}; sector_turnover={turnover}.
13. Sector top2 versus combo_SPY200d_GLD_50_50_v1:{compare_to('combo_SPY200d_GLD_50_50_v1', 'Sector top2 beat combo')}
14. Sector top2 versus asset_class_tsmom_top2_v1:{compare_to('asset_class_tsmom_top2_v1', 'Sector top2 beat top2')}
15. Sector top2 versus SPY_200d_trend_model:{compare_to('SPY_200d_trend_model', 'Sector top2 beat SPY_200d')}
16. Sector top2 versus QQQ dual momentum on stop-aware risk:{compare_to(QQQ_EXPERIMENT_ID, 'Sector top2 beat QQQ dual momentum')}
17. Sector top2 versus value/momentum factor rotation:{compare_to(VALUE_MOMENTUM_EXPERIMENT_ID, 'Sector top2 beat value/momentum factor rotation')}
18. Future candidate_exhaustive deserved: {str(deserves).lower()}. Current verdict: {verdict}.
19. No real-money recommendation is made.

Sector top2 target/risk ladder:

{ladder_lines()}
"""


def build_managed_futures_research_sample_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    managed_result = results[
        results["experiment_id"].eq(MANAGED_FUTURES_EXPERIMENT_ID)
        & results["standard_or_stress"].eq("standard")
    ] if not results.empty and "experiment_id" in results else pd.DataFrame()
    managed_rank = rankings[rankings["experiment_id"].eq(MANAGED_FUTURES_EXPERIMENT_ID)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if managed_result.empty and managed_rank.empty:
        return ""

    row = managed_result.iloc[0] if not managed_result.empty else pd.Series(dtype=object)
    rank = managed_rank.iloc[0] if not managed_rank.empty else pd.Series(dtype=object)

    def value(column: str, default: Any = "unavailable") -> Any:
        rank_preferred = {
            "profit_verdict",
            "practical_verdict_v2",
            "deserves_candidate_exhaustive",
            "candidate_exhaustive_queue_rank",
            "queue_reason",
            "too_slow_warning",
        }
        if column in rank_preferred and column in rank and pd.notna(rank[column]):
            return rank[column]
        if column in row and pd.notna(row[column]):
            return row[column]
        if column in rank and pd.notna(rank[column]):
            return rank[column]
        return default

    def ladder_lines() -> str:
        subset = rolling[
            rolling["experiment_id"].eq(MANAGED_FUTURES_EXPERIMENT_ID)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "Managed-futures proxy rolling rows are unavailable."
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"- {int(metric['horizon'])}d: +300 {pct_text(metric['p_target_300_before_stop'])}; "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}; "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}; "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}; "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}; "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}; "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}; "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}; "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "\n".join(lines)

    def compare_to(other: str, label: str) -> str:
        if managed_rank.empty or other not in set(rankings.get("experiment_id", pd.Series(dtype=str)).astype(str)):
            return f"{label}: unavailable."
        parts = [
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "balanced_drawdown_aware_score_v2", f"{label} on drawdown-aware v2 score"),
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "final_score", f"{label} on original final_score"),
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "p_90d_target_300_before_stop", f"{label} on 90d +300"),
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "p_90d_target_400_before_stop", f"{label} on 90d +400"),
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "p_90d_any_stop_hit", f"{label} on 90d stop-hit rate", higher_is_better=False),
            compare_text(rankings, MANAGED_FUTURES_EXPERIMENT_ID, other, "worst_90d_max_drawdown", f"{label} on 90d worst drawdown"),
        ]
        return "\n  - " + "\n  - ".join(parts)

    data_available = str(value("run_status", "")).lower() == "completed"
    dbmf_freq = pct_text(value("dbmf_selection_frequency", math.nan))
    kmlm_freq = pct_text(value("kmlm_selection_frequency", math.nan))
    bil_freq = pct_text(value("bil_allocation_frequency", math.nan))
    dbmf_share = pct_text(value("dbmf_allocation_share", math.nan))
    kmlm_share = pct_text(value("kmlm_allocation_share", math.nan))
    bil_share = pct_text(value("bil_allocation_share", math.nan))
    max_proxy = pct_text(value("max_single_proxy_allocation", math.nan))
    concentration = boolish(value("proxy_concentration_warning", False))
    too_slow = boolish(value("too_slow_warning", False))
    wrapper_warning = boolish(value("wrapper_proxy_warning", False))
    short_history = boolish(value("short_history_warning", False))
    direct_futures_disallowed = boolish(value("direct_futures_claim_disallowed", False))
    verdict = str(value("profit_verdict", "unavailable"))
    deserves = boolish(value("deserves_candidate_exhaustive", False))
    label = str(value("required_label", MANAGED_FUTURES_REQUIRED_LABEL))

    return f"""
## Managed-Futures Proxy Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, not a direct futures strategy test, and not a real-money recommendation.

1. Data available from cache: {str(data_available).lower()}. Cached implementation universe: DBMF, KMLM, BIL.
2. Data downloaded: false. The run used existing local cache only and did not refresh DBMF, KMLM, SPY, or BIL.
3. Universe used: DBMF and KMLM wrapper proxies, with BIL fallback.
4. CTA, FMF, and WTMF excluded: true. Those symbols remain outside this first fixed rule.
5. Rule: monthly rebalance; rank DBMF and KMLM by 126-trading-day return; a proxy qualifies only when 126-day return is positive and close is above the 200-day SMA; hold both qualifying proxies at 50% each, one qualifying proxy at 50% with unused 50% in BIL, or 100% BIL if neither qualifies; weights become effective on the next trading day after the signal.
6. DBMF/KMLM selected or allocated: DBMF selected {dbmf_freq} / allocation {dbmf_share}; KMLM selected {kmlm_freq} / allocation {kmlm_share}.
7. BIL fallback/allocation frequency: BIL selected {bil_freq} / allocation {bil_share}.
8. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
9. +600/+900/+1200 upside: see target ladder below.
10. Drawdown/stop risk: see stop and worst-drawdown rows below; proxy_concentration_warning={str(concentration).lower()}; max_single_proxy_allocation={max_proxy}.
11. Diversifier or too slow: too_slow_warning={str(too_slow).lower()}. Diversification cannot be accepted without enough target potential.
12. Dependence on one fund: proxy_concentration_warning={str(concentration).lower()}; max_single_proxy_allocation={max_proxy}.
13. Managed-futures proxy versus combo_SPY200d_GLD_50_50_v1:{compare_to('combo_SPY200d_GLD_50_50_v1', 'Managed-futures proxy beat combo')}
14. Managed-futures proxy versus asset_class_tsmom_top2_v1:{compare_to('asset_class_tsmom_top2_v1', 'Managed-futures proxy beat top2')}
15. Managed-futures proxy versus SPY_200d_trend_model:{compare_to('SPY_200d_trend_model', 'Managed-futures proxy beat SPY_200d')}
16. Managed-futures proxy versus GLD_buy_hold on risk-adjusted terms:{compare_to('GLD_buy_hold', 'Managed-futures proxy beat GLD_buy_hold')}
17. Managed-futures proxy versus BIL on target potential:{compare_to('BIL_cash_proxy', 'Managed-futures proxy beat BIL')}
18. Future candidate_exhaustive deserved: {str(deserves).lower()}. Current verdict: {verdict}.
19. Required short-history / fund-wrapper proxy warning: {label}; wrapper_proxy_warning={str(wrapper_warning).lower()}; short_history_warning={str(short_history).lower()}; direct_futures_claim_disallowed={str(direct_futures_disallowed).lower()}.
20. No real-money recommendation is made.

Managed-futures proxy target/risk ladder:

	{ladder_lines()}
	"""


def build_combination_batch1_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    batch_rankings = rankings[rankings["experiment_id"].isin(COMBINATION_BATCH1_IDS)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    batch_results = results[results["experiment_id"].isin(COMBINATION_BATCH1_IDS)] if not results.empty and "experiment_id" in results else pd.DataFrame()
    if batch_rankings.empty and batch_results.empty:
        return ""

    def row_for(exp_id: str) -> pd.Series:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        return row.iloc[0] if not row.empty else pd.Series(dtype=object)

    def ladder_lines(exp_id: str) -> str:
        subset = rolling[
            rolling["experiment_id"].eq(exp_id)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "standard rolling rows unavailable"
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"{int(metric['horizon'])}d +300 {pct_text(metric['p_target_300_before_stop'])}, "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}, "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}, "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}, "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}, "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}, "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}, "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}, "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "; ".join(lines)

    sections: list[str] = []
    for exp_id in COMBINATION_BATCH1_IDS:
        definition = COMBINATION_BATCH1_DEFINITIONS[exp_id]
        row = row_for(exp_id)
        if row.empty:
            sections.append(f"### {exp_id}\n\n- status: unavailable in this packet.")
            continue
        data_available = str(row.get("run_status", "")).lower() == "completed"
        exact_accounting = boolish(row.get("accounting_integrity_status", "")) or str(row.get("accounting_integrity_status", "")) == "passed"
        label = definition.get("required_label") or "not_applicable"
        sections.append(
            f"""### {exp_id}

- components: {', '.join(definition['components'])}
- fixed weights: {definition['weights']}
- data available from cache: {str(data_available).lower()}
- data downloaded: false
- exact fresh-window accounting used: {str(exact_accounting).lower()}
- hypothesis: {definition['hypothesis']}
- main risk: {definition['main_risk']}
- target/risk ladder: {ladder_lines(exp_id)}
- beat combo on stop-aware score: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'balanced_drawdown_aware_score_v2', 'combination beat combo')}
- beat top2 on stop-aware score: {compare_text(rankings, exp_id, 'asset_class_tsmom_top2_v1', 'balanced_drawdown_aware_score_v2', 'combination beat top2')}
- improve +300/+400 target rates: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'p_90d_target_300_before_stop', '+300 versus combo')} {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'p_90d_target_400_before_stop', '+400 versus combo')}
- reduce stop-hit rate: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'p_90d_any_stop_hit', 'stop-hit versus combo', higher_is_better=False)}
- reduce worst drawdown: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'worst_90d_max_drawdown', 'worst drawdown versus combo')}
- short-history label: {label}
- verdict: {row.get('profit_verdict', 'unavailable')}
- deserves candidate_exhaustive: {str(boolish(row.get('deserves_candidate_exhaustive', False))).lower()}
"""
        )

    return f"""
## Historical Combination Batch 1

This section reports exactly three predeclared fixed historical combination rows. It is research_sample only, uses existing local cache only, does not alter active paper-forward observations, and does not make a real-money recommendation.

{chr(10).join(sections)}
"""


def build_commodity_exploratory_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    row = rankings[rankings["experiment_id"].eq(COMMODITY_EXPLORATORY_EXPERIMENT_ID)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if row.empty:
        return ""
    item = row.iloc[0]
    subset = rolling[
        rolling["experiment_id"].eq(COMMODITY_EXPLORATORY_EXPERIMENT_ID)
        & rolling["standard_or_stress"].eq("standard")
    ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
    if subset.empty:
        ladder = "standard rolling rows unavailable"
    else:
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"{int(metric['horizon'])}d +300 {pct_text(metric['p_target_300_before_stop'])}, "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}, "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}, "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}, "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}, "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}, "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}, "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}, "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        ladder = "; ".join(lines)
    return f"""
## Commodity Basket Exploratory Screen

This section reports one fixed fast exploratory commodity wrapper row. It is research_sample only, uses local cache only, does not run candidate_exhaustive, does not activate paper-forward, and does not make a real-money recommendation.

- experiment_id: `{COMMODITY_EXPLORATORY_EXPERIMENT_ID}`
- data source/cache status: local adjusted ETF/fund wrapper cache populated by controlled fast exploratory acquisition; Profit Exploration itself used `--reuse-cache --no-network`
- symbols used: {', '.join(COMMODITY_EXPLORATORY_SYMBOLS)} plus BIL fallback
- symbols failed or excluded: see `evidence/data_acquisition_runs/commodity_basket_fast_exploratory/latest/`
- rule: monthly rebalance; rank DBC, PDBC, COMT, GSG, USCI by 126-trading-day return; hold top 2 wrappers with positive 126-day return equally; unused weight goes to BIL; if no wrapper qualifies, 100% BIL
- product labels: exploratory_public_data; {COMMODITY_EXPLORATORY_REQUIRED_LABEL}; not_validated; not_paper_forward; not_real_money
- target/risk ladder: {ladder}
- BIL/cash fallback frequency: selected {pct_text(item.get('bil_fallback_frequency'))}; allocation share {pct_text(item.get('bil_fallback_allocation_share'))}
- product concentration: max_single_commodity_wrapper_allocation={pct_text(item.get('max_single_commodity_wrapper_allocation'))}; product_concentration_warning={str(boolish(item.get('product_concentration_warning', False))).lower()}
- comparison versus combo: {compare_text(rankings, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'combo_SPY200d_GLD_50_50_v1', 'balanced_drawdown_aware_score_v2', 'commodity row beat combo')}
- comparison versus top2: {compare_text(rankings, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'asset_class_tsmom_top2_v1', 'balanced_drawdown_aware_score_v2', 'commodity row beat top2')}
- comparison versus SPY_200d: {compare_text(rankings, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'SPY_200d_trend_model', 'balanced_drawdown_aware_score_v2', 'commodity row beat SPY_200d')}
- comparison versus GLD: {compare_text(rankings, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'GLD_buy_hold', 'balanced_drawdown_aware_score_v2', 'commodity row beat GLD')}
- verdict: {item.get('profit_verdict', 'unavailable')}
- deserves candidate_exhaustive: {str(boolish(item.get('deserves_candidate_exhaustive', False))).lower()}
- direct futures claim disallowed: {str(boolish(item.get('direct_futures_claim_disallowed', False))).lower()}
"""


def build_commodity_risk_control_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    batch_rankings = rankings[rankings["experiment_id"].isin(COMMODITY_RISK_CONTROL_BATCH1_IDS)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if batch_rankings.empty:
        return ""

    def ladder_lines(exp_id: str) -> str:
        subset = rolling[
            rolling["experiment_id"].eq(exp_id)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "standard rolling rows unavailable"
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"{int(metric['horizon'])}d +300 {pct_text(metric['p_target_300_before_stop'])}, "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}, "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}, "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}, "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}, "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}, "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}, "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}, "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "; ".join(lines)

    sections: list[str] = []
    for exp_id in COMMODITY_RISK_CONTROL_BATCH1_IDS:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        if row.empty:
            sections.append(f"### {exp_id}\n\n- status: unavailable in this packet.")
            continue
        item = row.iloc[0]
        definition = COMMODITY_RISK_CONTROL_DEFINITIONS[exp_id]
        sections.append(
            f"""### {exp_id}

- rule summary: {definition['rule_summary']}
- data source/cache status: local cache only; Profit Exploration used `--reuse-cache --no-network`
- symbols used: {', '.join([*COMMODITY_EXPLORATORY_SYMBOLS, 'BIL'])}
- target/risk ladder: {ladder_lines(exp_id)}
- BIL/cash allocation share: {pct_text(item.get('bil_fallback_allocation_share'))}
- product/sleeve concentration: max wrapper {pct_text(item.get('max_single_commodity_wrapper_allocation'))}; combo sleeve {pct_text(item.get('component_combo_allocation_share'))}
- comparison versus base commodity: {compare_text(rankings, exp_id, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'balanced_drawdown_aware_score_v2', 'risk-control row beat base commodity')}
- comparison versus combo: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'balanced_drawdown_aware_score_v2', 'risk-control row beat combo')}
- comparison versus top2: {compare_text(rankings, exp_id, 'asset_class_tsmom_top2_v1', 'balanced_drawdown_aware_score_v2', 'risk-control row beat top2')}
- comparison versus SPY_200d: {compare_text(rankings, exp_id, 'SPY_200d_trend_model', 'balanced_drawdown_aware_score_v2', 'risk-control row beat SPY_200d')}
- comparison versus GLD: {compare_text(rankings, exp_id, 'GLD_buy_hold', 'balanced_drawdown_aware_score_v2', 'risk-control row beat GLD')}
- verdict: {item.get('profit_verdict', 'unavailable')}
- candidate_exhaustive recommendation: {str(boolish(item.get('deserves_candidate_exhaustive', False))).lower()}
- no real-money recommendation
"""
        )

    return f"""
## Commodity Risk-Control Batch 1

This section reports exactly three fixed predeclared commodity risk-control candidates. It is research_sample only, uses cached DBC/PDBC/COMT/GSG/USCI/BIL data only, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

{chr(10).join(sections)}
"""


def build_crypto_tier2_risk_control_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    batch_rankings = rankings[rankings["experiment_id"].isin(CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if batch_rankings.empty:
        return ""

    def ladder_lines(exp_id: str) -> str:
        subset = rolling[
            rolling["experiment_id"].eq(exp_id)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "standard rolling rows unavailable"
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"{int(metric['horizon'])}d +300 {pct_text(metric['p_target_300_before_stop'])}, "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}, "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}, "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}, "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}, "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}, "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}, "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}, "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "; ".join(lines)

    sections: list[str] = []
    for exp_id in CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        if row.empty:
            sections.append(f"### {exp_id}\n\n- status: unavailable in this packet.")
            continue
        item = row.iloc[0]
        definition = CRYPTO_TIER2_RISK_CONTROL_DEFINITIONS[exp_id]
        sections.append(
            f"""### {exp_id}

- rule summary: {definition['rule_summary']}
- data source/cache status: cached BTC-USD/ETH-USD spot series plus cached BIL; Profit Exploration used `--reuse-cache --no-network`
- symbols used: BTC-USD, ETH-USD, BIL
- target/risk ladder: {ladder_lines(exp_id)}
- BIL/cash allocation share: {pct_text(item.get('bil_cash_allocation_share'))}
- max crypto exposure: {pct_text(item.get('max_crypto_exposure'))}; BTC allocation share {pct_text(item.get('btc_allocation_share'))}; ETH allocation share {pct_text(item.get('eth_allocation_share'))}
- BTC/ETH allocation frequencies: BTC {pct_text(item.get('btc_selection_frequency'))}; ETH {pct_text(item.get('eth_selection_frequency'))}
- comparison versus combo: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'balanced_drawdown_aware_score_v2', 'crypto row beat combo')}
- comparison versus top2: {compare_text(rankings, exp_id, 'asset_class_tsmom_top2_v1', 'balanced_drawdown_aware_score_v2', 'crypto row beat top2')}
- comparison versus SPY_200d: {compare_text(rankings, exp_id, 'SPY_200d_trend_model', 'balanced_drawdown_aware_score_v2', 'crypto row beat SPY_200d')}
- comparison versus GLD: {compare_text(rankings, exp_id, 'GLD_buy_hold', 'balanced_drawdown_aware_score_v2', 'crypto row beat GLD')}
- verdict: {item.get('profit_verdict', 'unavailable')}
- candidate_exhaustive recommendation: {str(boolish(item.get('deserves_candidate_exhaustive', False))).lower()}
- no leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or real-money recommendation
"""
        )

    return f"""
## Crypto Spot Tier 2 Risk-Control Batch 1

This section reports exactly three fixed predeclared BTC/ETH spot-only risk-control candidates. It is research_sample only, uses cached/public daily data only, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

{chr(10).join(sections)}
"""


def build_global_multi_asset_batch1_section(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame) -> str:
    batch_rankings = rankings[rankings["experiment_id"].isin(GLOBAL_MULTI_ASSET_BATCH1_IDS)] if not rankings.empty and "experiment_id" in rankings else pd.DataFrame()
    if batch_rankings.empty:
        return ""

    def ladder_lines(exp_id: str) -> str:
        subset = rolling[
            rolling["experiment_id"].eq(exp_id)
            & rolling["standard_or_stress"].eq("standard")
        ] if not rolling.empty and "experiment_id" in rolling else pd.DataFrame()
        if subset.empty:
            return "standard rolling rows unavailable"
        lines = []
        for _, metric in subset.sort_values("horizon").iterrows():
            lines.append(
                f"{int(metric['horizon'])}d +300 {pct_text(metric['p_target_300_before_stop'])}, "
                f"+400 {pct_text(metric['p_target_400_before_stop'])}, "
                f"+600 {pct_text(metric['p_target_600_before_stop'])}, "
                f"+900 {pct_text(metric['p_target_900_before_stop'])}, "
                f"+1200 {pct_text(metric['p_target_1200_before_stop'])}, "
                f"stop {pct_text(metric['p_any_project_stop_hit'])}, "
                f"median {dollar_text(metric['median_stop_enforced_final_equity'])}, "
                f"p95 {dollar_text(metric['p95_stop_enforced_final_equity'])}, "
                f"worst drawdown {dollar_text(metric['worst_max_drawdown'])}"
            )
        return "; ".join(lines)

    sections: list[str] = []
    for exp_id in GLOBAL_MULTI_ASSET_BATCH1_IDS:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        if row.empty:
            sections.append(f"### {exp_id}\n\n- status: unavailable in this packet.")
            continue
        item = row.iloc[0]
        definition = GLOBAL_MULTI_ASSET_BATCH1_DEFINITIONS[exp_id]
        sections.append(
            f"""### {exp_id}

- rule summary: {definition['rule_summary']}
- data source/cache status: local cache only during Profit Exploration; approved symbols were populated or confirmed by the controlled global multi-asset fast acquisition lane
- symbols used: {', '.join([*GLOBAL_MULTI_ASSET_SYMBOLS, 'BIL'])}
- target/risk ladder: {ladder_lines(exp_id)}
- BIL/cash allocation share: {pct_text(item.get('global_bil_allocation_share'))}
- max asset/sleeve concentration: max asset {pct_text(item.get('max_single_global_asset_allocation'))}; combo sleeve {pct_text(item.get('component_combo_allocation_share'))}
- asset allocation shares: equity {pct_text(item.get('global_equity_allocation_share'))}; international {pct_text(item.get('global_international_allocation_share'))}; duration {pct_text(item.get('global_duration_allocation_share'))}; real asset {pct_text(item.get('global_real_asset_allocation_share'))}
- comparison versus combo: {compare_text(rankings, exp_id, 'combo_SPY200d_GLD_50_50_v1', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat combo')}
- comparison versus top2: {compare_text(rankings, exp_id, 'asset_class_tsmom_top2_v1', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat top2')}
- comparison versus SPY_200d: {compare_text(rankings, exp_id, 'SPY_200d_trend_model', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat SPY_200d')}
- comparison versus GLD: {compare_text(rankings, exp_id, 'GLD_buy_hold', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat GLD')}
- comparison versus commodity base if available: {compare_text(rankings, exp_id, COMMODITY_EXPLORATORY_EXPERIMENT_ID, 'balanced_drawdown_aware_score_v2', 'multi-asset row beat commodity base')}
- comparison versus commodity 80/20 if available: {compare_text(rankings, exp_id, 'combo_plus_commodity_basket_80_20_v1', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat commodity 80/20')}
- comparison versus crypto 90/10 if available: {compare_text(rankings, exp_id, 'combo_plus_crypto_spot_tsmom_90_10_v1', 'balanced_drawdown_aware_score_v2', 'multi-asset row beat crypto 90/10')}
- verdict: {item.get('profit_verdict', 'unavailable')}
- candidate_exhaustive recommendation: {str(boolish(item.get('deserves_candidate_exhaustive', False))).lower()}
- no real-money recommendation
"""
        )

    return f"""
## Global Multi-Asset ETF Fast Exploration Batch 1

This section reports exactly three fixed predeclared global multi-asset ETF/fund-wrapper candidates. It is research_sample only, uses cache-only Profit Exploration after controlled acquisition/cache QA, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

{chr(10).join(sections)}
"""


def build_summary(results: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame, status: pd.DataFrame, run_id: str, args: argparse.Namespace | None = None) -> str:
    completed = rankings[rankings["run_status"].eq("completed")]
    exact = completed[~completed["evidence_tier"].isin(["tier1_exploratory", "tier1_or_tier2_exploratory", "tier2_exploratory"])]
    mode = getattr(args, "mode", "research_sample")
    finalist_ids = parse_finalist_ids(getattr(args, "finalists", None) if args is not None else None)
    selected_horizons = selected_horizons_for_args(args) if args is not None else HORIZONS.copy()
    omitted_horizons = [horizon for horizon in HORIZONS if horizon not in selected_horizons]
    reduced = bool(omitted_horizons)

    def best_by(col: str) -> str:
        if completed.empty or col not in completed:
            return "unavailable"
        row = completed.sort_values(col, ascending=False).iloc[0]
        return f"{row['experiment_id']} ({float(row[col]):.1%})"

    def best_equity(col: str) -> str:
        if completed.empty or col not in completed:
            return "unavailable"
        row = completed.sort_values(col, ascending=False).iloc[0]
        return f"{row['experiment_id']} (${float(row[col]):,.2f})"

    best_overall = rankings.sort_values("rank_overall").iloc[0] if not rankings.empty else None
    best_risk = rankings.sort_values("rank_risk_control").iloc[0] if not rankings.empty else None
    high_risk = rankings[rankings["profit_verdict"].isin(["high_upside_high_risk", "too_risky"])]["experiment_id"].astype(str).tolist()
    duplicates = rankings[rankings["run_status"].eq("duplicate_skipped")]
    blocked = status[status["run_status"].eq("blocked_by_gate")]["experiment_id"].astype(str).tolist() if "run_status" in status else []
    incomplete = status[status["run_status"].eq("incomplete_evidence")]["experiment_id"].astype(str).tolist() if "run_status" in status else []
    combo_rows = rankings[rankings["experiment_id"].astype(str).str.startswith("combo_")]
    spy_row = rankings[rankings["experiment_id"].eq("SPY_200d_trend_model")]
    improved_combos: list[str] = []
    if not spy_row.empty:
        spy_score = float(spy_row["final_score"].iloc[0])
        improved_combos = combo_rows[combo_rows["final_score"].astype(float) > spy_score]["experiment_id"].astype(str).tolist()
    exact_best300 = exact.sort_values("p_90d_target_300_before_stop", ascending=False).iloc[0] if not exact.empty else None
    exact_best400 = exact.sort_values("p_90d_target_400_before_stop", ascending=False).iloc[0] if not exact.empty else None
    queued = rankings[rankings.get("deserves_candidate_exhaustive", pd.Series(dtype=bool)).map(boolish)].sort_values("candidate_exhaustive_queue_rank")
    if mode == "candidate_exhaustive":
        if rankings.empty:
            queue_text = "Candidate-exhaustive validation ran, but no ranking rows were available."
        else:
            queue_text = "Candidate-exhaustive validation ran for the requested finalist set. Use promotion_review outside this task for any future status decision; no row is paper-forward ready from this packet."
    elif queued.empty:
        queue_text = "No strategy met the conservative queue rule in this research_sample packet."
    else:
        queue_lines = []
        for _, row in queued.iterrows():
            queue_lines.append(
                f"- {row['experiment_id']}: reason_for_queue={row.get('queue_reason', '')}; "
                f"evidence_tier={row.get('evidence_tier', '')}; "
                f"research_sample_result_summary=+300 {float(row.get('p_90d_target_300_before_stop', 0)):.1%}, "
                f"+400 {float(row.get('p_90d_target_400_before_stop', 0)):.1%}, stop {float(row.get('p_90d_any_stop_hit', 0)):.1%}, "
                f"median ${float(row.get('median_90d_stop_enforced_final_equity', 0)):,.2f}; "
                f"main_risk={status.loc[status['experiment_id'].eq(row['experiment_id']), 'main_risk'].iloc[0] if 'main_risk' in status and status['experiment_id'].eq(row['experiment_id']).any() else 'see experiment specs'}; "
                f"comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; "
                f"recommended_finalist_set={row['experiment_id']}, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy"
            )
        queue_text = "\n".join(queue_lines)
    finalist_comparison_text = build_finalist_comparison_section(rolling, rankings, finalist_ids, mode, args)
    score_audit_text = build_profit_score_audit_section(rankings)
    v2_score_text = build_drawdown_aware_v2_section(rankings)
    qqq_text = build_qqq_research_sample_section(results, rolling, rankings)
    value_momentum_text = build_value_momentum_research_sample_section(results, rolling, rankings)
    sector_top2_text = build_sector_top2_research_sample_section(results, rolling, rankings)
    managed_futures_text = build_managed_futures_research_sample_section(results, rolling, rankings)
    combination_batch1_text = build_combination_batch1_section(results, rolling, rankings)
    commodity_exploratory_text = build_commodity_exploratory_section(results, rolling, rankings)
    commodity_risk_control_text = build_commodity_risk_control_section(results, rolling, rankings)
    crypto_tier2_risk_control_text = build_crypto_tier2_risk_control_section(results, rolling, rankings)
    global_multi_asset_batch1_text = build_global_multi_asset_batch1_section(results, rolling, rankings)
    completed_results = results[results["run_status"].eq("completed")]
    failed_integrity = completed_results[~completed_results["accounting_integrity_status"].eq("passed")]
    integrity_status = "failed" if not failed_integrity.empty else "passed"
    rolling_rebased = bool(completed_results["rolling_rebase_check_passed"].map(boolish).all()) if not completed_results.empty else False
    buy_hold_rows = completed_results[completed_results["experiment_id"].isin(CORE_BUY_HOLD_BENCHMARKS)]
    buy_hold_checks = bool(buy_hold_rows["buy_hold_reference_check_passed"].map(boolish).all()) if not buy_hold_rows.empty else False
    combo_rows_results = completed_results[completed_results["experiment_id"].astype(str).str.startswith("combo_")]
    combo_checks = bool(combo_rows_results["combination_return_check_passed"].map(boolish).all()) if not combo_rows_results.empty else True
    invalidated = rankings[~rankings["profit_results_usable"].map(boolish) & rankings["run_status"].eq("completed")]["experiment_id"].astype(str).tolist()
    usable_rankings = integrity_status == "passed" and not invalidated
    selected_finality_rows = rolling[rolling["horizon"].isin(selected_horizons)] if "horizon" in rolling else pd.DataFrame()
    selected_horizons_completed_summary = bool(
        not selected_finality_rows.empty
        and selected_finality_rows["evidence_finality"].isin(["exact_all_possible", "exact_selected_horizons"]).all()
    )
    full_horizon_completed_summary = bool(not reduced and mode == "candidate_exhaustive" and selected_horizons_completed_summary)
    candidate_exhaustive_completed_summary = bool(full_horizon_completed_summary)
    final_validation_completed_summary = bool(
        results["final_validation_completed"].map(boolish).all()
        if "final_validation_completed" in results and not results.empty
        else candidate_exhaustive_completed_summary
    )
    sampled_results_are_final_summary = bool(
        results["sampled_results_are_final"].map(boolish).all()
        if "sampled_results_are_final" in results and not results.empty
        else candidate_exhaustive_completed_summary
    )
    return f"""# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: {run_id}
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Run Validation Scope

- run_validation_scope: {"finalist_reduced_90_180" if reduced and selected_horizons == [90, 180] else ("reduced_horizon_validation" if reduced else "all_horizons")}
- reduced_validation: {str(reduced).lower()}
- reduced_validation_reason: {"runtime_control_2_to_3_hours" if reduced else "none"}
- selected_horizons: {','.join(map(str, selected_horizons))}
- omitted_horizons: {','.join(map(str, omitted_horizons)) if omitted_horizons else 'none'}
- selected_horizons_completed: {str(selected_horizons_completed_summary).lower()}
- full_horizon_validation_completed: {str(full_horizon_completed_summary).lower()}
- candidate_exhaustive_completed: {str(candidate_exhaustive_completed_summary).lower()}
- final_validation_completed: {str(final_validation_completed_summary).lower()}
- sampled_results_are_final: {str(sampled_results_are_final_summary).lower()}

## Experiments

Completed experiments: {', '.join(completed['experiment_id'].astype(str).tolist()) or 'none'}.

Blocked experiments: {', '.join(blocked) or 'none'}.

Incomplete experiments: {', '.join(incomplete) or 'none'}.

Duplicate-skipped experiments: {', '.join(duplicates['experiment_id'].astype(str).tolist()) if not duplicates.empty else 'none'}.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: {best_by('p_90d_target_300_before_stop')}
- Highest exact +$400 probability: {best_by('p_90d_target_400_before_stop')}
- Highest +$600 probability: {best_by('p_90d_target_600_before_stop')}
- Highest +$900 probability: {best_by('p_90d_target_900_before_stop')}
- Highest +$1200 probability: {best_by('p_90d_target_1200_before_stop')}

## Profit And Risk

- Highest median stop-enforced equity: {best_equity('median_90d_stop_enforced_final_equity')}
- Highest upside tail: {best_equity('p95_90d_stop_enforced_final_equity')}
- Best risk control: {best_risk['experiment_id'] if best_risk is not None else 'unavailable'}
- Best overall profit/risk tradeoff: {best_overall['experiment_id'] if best_overall is not None else 'unavailable'}
- Exact best +$300 family/experiment: {exact_best300['experiment_id'] if exact_best300 is not None else 'unavailable'}
- Exact best +$400 family/experiment: {exact_best400['experiment_id'] if exact_best400 is not None else 'unavailable'}

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: {', '.join(improved_combos) or 'none'}.

High-upside but too-risky rows: {', '.join(high_risk) or 'none'}.

{finalist_comparison_text}

{score_audit_text}

{v2_score_text}

{qqq_text}

{value_momentum_text}

{sector_top2_text}

	{managed_futures_text}

	{combination_batch1_text}

	{commodity_exploratory_text}

	{commodity_risk_control_text}

	{crypto_tier2_risk_control_text}

	{global_multi_asset_batch1_text}

	## Candidate Exhaustive Queue

{"Reduced selected-horizon candidate-exhaustive mode was run for this packet. The text below is a full-horizon overnight-validation queue, not a paper-forward promotion." if mode == "candidate_exhaustive" and reduced else ("Candidate-exhaustive mode was run for this packet. The text below is a promotion-review reminder, not a paper-forward promotion." if mode == "candidate_exhaustive" else "Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.")}

{queue_text}

## Accounting Integrity Audit

- accounting_integrity_status: {integrity_status}
- rolling_windows_rebased_to_3000: {str(rolling_rebased).lower()}
- buy_hold_reference_checks_passed: {str(buy_hold_checks).lower()}
- combination_return_checks_passed: {str(combo_checks).lower()}
- failed_experiments: {', '.join(failed_integrity['experiment_id'].astype(str).unique().tolist()) or 'none'}
- invalidated_rankings: {', '.join(invalidated) or 'none'}
- profit_rankings_decision_usable: {str(usable_rankings).lower()}

The previous pre-integrity profit league rankings are treated as invalidated because rolling windows had not yet proven fresh $3,000 rebasing. The current packet rebuilds every rolling window from window-local returns and blocks rankings if accounting integrity fails.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
"""


def build_assumptions(args: argparse.Namespace) -> dict[str, Any]:
    meta = validation_metadata(args)
    return {
        "research_only": True,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "mode": args.mode,
        "finalists": parse_finalist_ids(getattr(args, "finalists", None)),
        "run_validation_scope": meta["run_validation_scope"],
        "selected_horizons": meta["selected_horizons"],
        "omitted_horizons": meta["omitted_horizons"],
        "selected_horizons_completed": meta["candidate_exhaustive_completed"] if not meta["reduced_validation"] else None,
        "full_horizon_validation_completed": meta["full_horizon_validation_completed"],
        "candidate_exhaustive_completed": meta["candidate_exhaustive_completed"],
        "reduced_validation": meta["reduced_validation"],
        "reduced_validation_reason": meta["reduced_validation_reason"],
        "starting_equity": STARTING_EQUITY,
        "targets": TARGETS,
        "absolute_stop_equity": ABSOLUTE_STOP,
        "trailing_drawdown_dollars": TRAILING_DRAWDOWN,
        "project_stop_mode": "both",
        "standard_and_stress_costs": LABEL_COSTS,
        "include_fixed_combinations": args.include_fixed_combinations,
        "include_combination_batch1": bool(getattr(args, "include_combination_batch1", False)),
        "include_commodity_basket_exploratory": bool(getattr(args, "include_commodity_basket_exploratory", False)),
        "include_commodity_risk_control_batch1": bool(getattr(args, "include_commodity_risk_control_batch1", False)),
        "include_crypto_tier2_risk_control_batch1": bool(getattr(args, "include_crypto_tier2_risk_control_batch1", False)),
        "include_global_multi_asset_batch1": bool(getattr(args, "include_global_multi_asset_batch1", False)),
        "include_crypto_exploratory": args.include_crypto_exploratory,
        "include_blocked": args.include_blocked,
        "raw_data_in_evidence": False,
        "parameter_optimization": False,
        "grid_search": False,
        "rolling_window_accounting": {
            "fresh_starting_equity_required": STARTING_EQUITY,
            "fresh_high_water_mark_required": STARTING_EQUITY,
            "target_state_resets": True,
            "stop_state_resets": True,
            "full_period_equity_slices_for_rolling": False,
            "buy_hold_reference_checks": True,
            "fixed_combinations_use_component_daily_returns": True,
        },
        "scoring_v2": {
            "name": "balanced_drawdown_aware_score_v2",
            "purpose": "penalize drawdown budget usage before hard stop breach",
            "risk_budget_dollars": TRAILING_DRAWDOWN,
            "reduced_validation": meta["reduced_validation"],
            "final_validation_completed": meta["candidate_exhaustive_completed"],
            "no_strategy_rule_changes": True,
        },
        "qqq_dual_momentum_research_sample": {
            "experiment_id": QQQ_EXPERIMENT_ID,
            "research_sample_only": True,
            "required_symbols": ["QQQ", "SPY", "GLD", "IEF", "BIL"],
            "requires_network": False,
            "data_downloaded": False,
            "ranking_lookback_trading_days": 126,
            "trend_filter": "price_gt_200_day_sma",
            "selected_assets": 1,
            "reports_allocation_concentration": True,
            "reports_equity_beta_duplicate_warning": True,
        },
        "value_momentum_factor_etf_rotation_research_sample": {
            "experiment_id": VALUE_MOMENTUM_EXPERIMENT_ID,
            "implementation_rule_id": "value_momentum_factor_etf_rotation_top2_option_a_v1",
            "research_sample_only": True,
            "required_symbols": ["MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"],
            "reviewed_but_not_used_symbols": ["VLUE", "SPLV"],
            "requires_network": False,
            "data_downloaded": False,
            "ranking_lookback_trading_days": 126,
            "trend_filter": "price_gt_200_day_sma",
            "selected_assets": 2,
            "unused_weight_goes_to": "BIL",
            "reports_allocation_concentration": True,
            "reports_equity_beta_duplicate_warning": True,
        },
        "sector_top2_momentum_research_sample": {
            "experiment_id": SECTOR_TOP2_EXPERIMENT_ID,
            "implementation_rule_id": "sector_top2_core_nine_momentum_v1",
            "research_sample_only": True,
            "required_symbols": [*SECTOR_TOP2_SYMBOLS, "BIL"],
            "excluded_symbols_first_rule": ["XLC", "XLRE"],
            "requires_network": False,
            "data_downloaded": False,
            "ranking_lookback_trading_days": 126,
            "trend_filter": "price_gt_200_day_sma",
            "absolute_filter": "selected_sector_126d_return_gt_0",
            "selected_assets": 2,
            "unused_weight_goes_to": "BIL",
            "reports_allocation_concentration": True,
            "reports_equity_beta_duplicate_warning": True,
            "modifies_A_ETF_sector_momentum": False,
        },
        "managed_futures_proxy_research_sample": {
            "experiment_id": MANAGED_FUTURES_EXPERIMENT_ID,
            "implementation_rule_id": "managed_futures_proxy_dbmf_kmlm_trend_v1",
            "research_sample_only": True,
            "required_label": MANAGED_FUTURES_REQUIRED_LABEL,
            "required_symbols": [*MANAGED_FUTURES_SYMBOLS, "BIL"],
            "excluded_symbols_first_rule": ["CTA", "FMF", "WTMF"],
            "requires_network": False,
            "data_downloaded": False,
            "uses_futures_contracts": False,
            "adds_futures_contract_logic": False,
            "ranking_lookback_trading_days": 126,
            "trend_filter": "price_gt_200_day_sma",
            "absolute_filter": "selected_proxy_126d_return_gt_0",
            "selected_assets": 2,
            "unused_weight_goes_to": "BIL",
            "reports_allocation_concentration": True,
            "reports_wrapper_proxy_warning": True,
            "reports_short_history_warning": True,
            "direct_futures_claim_disallowed": True,
        },
        "historical_combination_batch1": {
            "included": bool(getattr(args, "include_combination_batch1", False)),
            "research_sample_only": True,
            "combination_ids": COMBINATION_BATCH1_IDS,
            "fixed_weights_only": True,
            "monthly_fixed_combination_rebalancing": True,
            "uses_exact_window_local_component_returns": True,
            "no_optimized_weights": True,
            "data_downloaded": False,
            "candidate_exhaustive_run": False,
            "active_combo_paper_forward_rule_changed": False,
            "spy200d_replaced": False,
            "managed_futures_required_label": MANAGED_FUTURES_REQUIRED_LABEL,
        },
        "commodity_basket_exploratory": {
            "included": bool(getattr(args, "include_commodity_basket_exploratory", False)),
            "experiment_id": COMMODITY_EXPLORATORY_EXPERIMENT_ID,
            "research_sample_only": True,
            "required_label": COMMODITY_EXPLORATORY_REQUIRED_LABEL,
            "required_symbols": [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"],
            "requires_network": False,
            "data_source": "local cache populated by controlled yfinance-compatible fast exploratory acquisition",
            "data_downloaded_in_profit_exploration": False,
            "uses_futures_contracts": False,
            "adds_futures_contract_logic": False,
            "ranking_lookback_trading_days": 126,
            "trend_filter": "none_first_fast_screen",
            "absolute_filter": "selected_wrapper_126d_return_gt_0",
            "selected_assets": 2,
            "unused_weight_goes_to": "BIL",
            "reports_bil_fallback_frequency": True,
            "reports_product_concentration": True,
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
        },
        "commodity_risk_control_batch1": {
            "included": bool(getattr(args, "include_commodity_risk_control_batch1", False)),
            "research_sample_only": True,
            "candidate_ids": COMMODITY_RISK_CONTROL_BATCH1_IDS,
            "base_experiment_id": COMMODITY_EXPLORATORY_EXPERIMENT_ID,
            "fixed_rules_only": True,
            "no_optimized_weights": True,
            "required_symbols": [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"],
            "new_symbols_added": False,
            "requires_network": False,
            "data_downloaded_in_profit_exploration": False,
            "uses_futures_contracts": False,
            "adds_futures_contract_logic": False,
            "uses_leverage": False,
            "uses_margin": False,
            "uses_shorting": False,
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
        },
        "global_multi_asset_fast_exploration_batch1": {
            "included": bool(getattr(args, "include_global_multi_asset_batch1", False)),
            "research_sample_only": True,
            "candidate_ids": GLOBAL_MULTI_ASSET_BATCH1_IDS,
            "required_label": GLOBAL_MULTI_ASSET_REQUIRED_LABEL,
            "required_symbols": [*GLOBAL_MULTI_ASSET_SYMBOLS, "BIL"],
            "new_symbols_allowed_in_acquisition_only": ["IWM", "EFA", "EEM", "TLT"],
            "requires_network": False,
            "data_source": "local cache populated by existing cache or controlled yfinance-compatible fast exploratory acquisition",
            "data_downloaded_in_profit_exploration": False,
            "uses_leverage": False,
            "uses_margin": False,
            "uses_shorting": False,
            "uses_futures_contracts": False,
            "uses_options": False,
            "uses_forex": False,
            "uses_intraday": False,
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
            "active_combo_paper_forward_rule_changed": False,
            "spy200d_replaced": False,
        },
        "crypto_tier2_risk_control_batch1": {
            "included": bool(getattr(args, "include_crypto_tier2_risk_control_batch1", False)),
            "research_sample_only": True,
            "candidate_ids": CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS,
            "required_label": CRYPTO_TIER2_REQUIRED_LABEL,
            "required_symbols": [*CRYPTO_SPOT_SYMBOLS, "BIL"],
            "new_crypto_assets_added": False,
            "requires_network": False,
            "data_source": "existing BTC-USD/ETH-USD crypto spot cache plus cached BIL",
            "data_downloaded_in_profit_exploration": False,
            "uses_leverage": False,
            "uses_margin": False,
            "uses_shorting": False,
            "uses_futures_contracts": False,
            "uses_perpetuals": False,
            "uses_options": False,
            "exchange_execution": False,
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
        },
        "notes": "Profit exploration uses fixed predeclared experiments with independent $3,000 paper/demo accounts.",
    }


def build_warnings_text() -> str:
    return """# Warnings And Limitations

- Research-only paper/demo evidence.
- No real-money recommendation.
- No broker integration, live orders, exchange trading, or order placement.
- Profit exploration is not paper-forward and does not alter frozen paper-forward rules.
- +$300/+400 are hurdles, not proof of reliability.
- Stop-aware profit matters more than raw final equity.
- Legacy crypto rows, if included, remain Tier 1 exploratory only.
- Crypto Spot Tier 2 Risk-Control Batch 1, when included, tests exactly three fixed BTC/ETH spot-only candidates.
- Crypto Spot Tier 2 Risk-Control Batch 1 is exploratory, non-final, not paper-forward, and not real-money evidence.
- Crypto Spot Tier 2 Risk-Control Batch 1 does not add leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or order placement.
- Crypto spot daily data has 24/7 calendar limitations when aligned to ETF/cash trading days for BIL fallback.
- Blocked families are reported but not run.
- Incomplete rows are not approximated from summary metrics.
- Fixed combinations are independent experiment accounts, not allocation advice.
- No raw OHLCV is copied into this compact evidence packet.
- Profit League rankings are invalid if accounting integrity fails.
- Fresh $3,000 rebasing is required for every rolling window.
- Full-period equity slices cannot be used as rolling-window equity.
- Duplicate canonical rule hashes are skipped and not counted as independent evidence.
- Candidate Exhaustive Queue entries are research leads or promotion-review reminders only, not paper-forward approval.
- Reduced validation packets can be exact for selected horizons while remaining non-final across omitted horizons.
- A 90/180 reduced validation packet is not full 30/60/90/180 candidate validation.
- Score v2 changes ranking interpretation only.
- Score v2 does not change strategy results.
- Full 30/60/90/180 candidate_exhaustive, when completed, is still research validation and not paper-forward approval.
- Separate promotion review is required before any paper-forward change.
- QQQ dual momentum is research_sample only; it is not candidate-exhaustive or paper-forward active from this packet.
- QQQ allocation concentration and equity-beta duplicate warnings must be reviewed before any future overnight validation.
- Value/momentum factor ETF rotation is research_sample only; it is not candidate-exhaustive or paper-forward active from this packet.
- Value/momentum factor ETF rotation uses only MTUM, VTV, QUAL, USMV, SPY, and BIL; VLUE and SPLV were reviewed but not used in the first rule.
- Value/momentum allocation concentration and equity-beta duplicate warnings must be reviewed before any future overnight validation.
- Sector top2 momentum is research_sample only; it is not candidate-exhaustive or paper-forward active from this packet.
- Sector top2 momentum uses only XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, and BIL; XLC and XLRE are excluded from the first rule.
- Sector top2 momentum does not modify or approximate A_ETF_sector_momentum.
- Sector top2 allocation concentration and equity-beta duplicate warnings must be reviewed before any future overnight validation.
- Managed-futures proxy is research_sample only; it is not candidate-exhaustive or paper-forward active from this packet.
- Managed-futures proxy uses only DBMF, KMLM, and BIL; CTA, FMF, and WTMF are excluded from the first rule.
- Managed-futures proxy uses ETF/fund wrapper adjusted price series only and does not add futures contract logic.
- Managed-futures proxy evidence must carry the fund_wrapper_proxy_short_history_limited_inception_research_sample_only label.
- Managed-futures proxy wrapper modeling hides internal futures, rolls, collateral, notional exposure, fees, and methodology mechanics.
- Historical Combination Batch 1, when included, tests exactly three fixed predeclared blends only.
- Historical Combination Batch 1 uses window-local component return streams and must not combine summary statistics.
- Managed-futures blend rows remain fund-wrapper proxy short-history evidence and must not be treated as direct futures strategy evidence.
- Combination batch rows are not paper-forward active and do not change the active combo paper/demo observation.
- Commodity basket exploratory screen, when included, uses ETF/fund wrapper adjusted price series from local cache only.
- Commodity basket exploratory screen must carry the commodity_wrapper_evidence_research_sample_only label.
- Commodity basket exploratory screen is exploratory public-data evidence only, not validated, not paper-forward, and not real-money evidence.
- Commodity wrapper adjusted-price modeling is not direct futures strategy evidence and does not add futures contract or roll logic.
- Commodity Risk-Control Batch 1, when included, tests exactly three fixed predeclared candidates and does not tune parameters or add symbols.
- Commodity Risk-Control Batch 1 uses cached ETF/fund wrapper data only and does not run candidate_exhaustive.
- Global Multi-Asset ETF Fast Exploration Batch 1, when included, tests exactly three fixed predeclared candidates and does not tune parameters or add symbols.
- Global Multi-Asset ETF Fast Exploration Batch 1 uses cached approved ETF/fund wrapper data only during Profit Exploration and does not run candidate_exhaustive.
- Global Multi-Asset ETF Fast Exploration Batch 1 does not add leverage, margin, shorting, futures contracts, options, forex, intraday logic, broker integration, live orders, order placement, or real-money recommendations.
- Global multi-asset rows are exploratory public-data ETF/fund wrapper evidence only, not validated, not paper-forward, and not real-money evidence.
- No paper-forward rule changes.
- No real-money recommendation.
"""


def curve_return_series(curve: pd.DataFrame) -> pd.Series:
    if curve is None or curve.empty or "date" not in curve or "equity" not in curve:
        return pd.Series(dtype=float)
    series = curve.copy()
    series["date"] = pd.to_datetime(series["date"])
    series = series.set_index("date")["equity"].astype(float).sort_index()
    return series.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()


def drawdown_series_from_curve(curve: pd.DataFrame) -> pd.Series:
    if curve is None or curve.empty or "date" not in curve or "equity" not in curve:
        return pd.Series(dtype=float)
    series = curve.copy()
    series["date"] = pd.to_datetime(series["date"])
    equity = series.set_index("date")["equity"].astype(float).sort_index()
    high_water = equity.cummax()
    return equity / high_water - 1.0


def metric_value(frame: pd.DataFrame, exp_id: str, column: str, default: Any = "unavailable") -> Any:
    if frame.empty or column not in frame:
        return default
    row = frame[frame["experiment_id"].astype(str).eq(exp_id)]
    if row.empty:
        return default
    value = row[column].iloc[0]
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def build_combination_correlation_diagnostics(curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    benchmarks = [
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
        "BIL_cash_proxy",
    ]
    for exp_id in COMBINATION_BATCH1_IDS:
        combo_returns = curve_return_series(curves.get(exp_id, pd.DataFrame()))
        combo_dd = drawdown_series_from_curve(curves.get(exp_id, pd.DataFrame()))
        for benchmark in benchmarks:
            benchmark_returns = curve_return_series(curves.get(benchmark, pd.DataFrame()))
            benchmark_dd = drawdown_series_from_curve(curves.get(benchmark, pd.DataFrame()))
            shared = combo_returns.index.intersection(benchmark_returns.index)
            status = "available" if len(shared) >= 30 else "unavailable"
            correlation = math.nan
            rolling_60 = math.nan
            rolling_90 = math.nan
            stress_corr = math.nan
            drawdown_coincidence = math.nan
            notes = ""
            if status == "available":
                left = combo_returns.loc[shared]
                right = benchmark_returns.loc[shared]
                correlation = float(left.corr(right))
                rolling_60 = float(left.rolling(60).corr(right).dropna().mean()) if len(shared) >= 60 else math.nan
                rolling_90 = float(left.rolling(90).corr(right).dropna().mean()) if len(shared) >= 90 else math.nan
                stress_mask = left <= left.quantile(0.10)
                stress_corr = float(left[stress_mask].corr(right[stress_mask])) if int(stress_mask.sum()) >= 10 else math.nan
                dd_shared = combo_dd.index.intersection(benchmark_dd.index)
                if len(dd_shared) >= 30:
                    combo_stress = combo_dd.loc[dd_shared] <= -0.05
                    benchmark_stress = benchmark_dd.loc[dd_shared] <= -0.05
                    drawdown_coincidence = float((combo_stress & benchmark_stress).sum() / max(1, int(combo_stress.sum())))
                notes = "calculated from full-period standard equity curve daily returns; not raw OHLCV"
            else:
                notes = "unavailable because aligned generated equity-curve returns were insufficient"
            rows.append(
                {
                    "combination_id": exp_id,
                    "benchmark_id": benchmark,
                    "correlation": correlation,
                    "rolling_60d_correlation_mean": rolling_60,
                    "rolling_90d_correlation_mean": rolling_90,
                    "stress_period_correlation": stress_corr,
                    "drawdown_coincidence_rate": drawdown_coincidence,
                    "target_window_co_movement_status": "unavailable",
                    "correlation_diagnostics_status": status,
                    "drawdown_coincidence_diagnostics_status": "available" if pd.notna(drawdown_coincidence) else "unavailable",
                    "notes": notes,
                }
            )
    return pd.DataFrame(rows)


def drawdown_pct_series(curve: pd.DataFrame) -> pd.Series:
    if curve.empty or "equity" not in curve:
        return pd.Series(dtype=float)
    series = pd.Series(curve["equity"].astype(float).to_numpy(), index=pd.to_datetime(curve["date"]))
    high_water = series.cummax()
    return series / high_water - 1.0


def simulate_weighted_window_on_index(model: ExperimentModel, index: pd.Index, cost: float) -> dict[str, Any]:
    if model.weights is None:
        raise ValueError(f"{model.experiment_id} missing weights.")
    index = pd.DatetimeIndex(index)
    prices = model.prices.reindex(index).dropna(how="all")
    if len(prices) != len(index):
        return {
            "curve": pd.DataFrame(columns=["date", "equity"]),
            "daily_returns": pd.Series(dtype=float),
            "accounting": {"integrity_error": "missing requested dates"},
            "component_contributions": {},
            "component_contribution_status": "unavailable_missing_requested_dates",
        }
    weights = model.weights.reindex(index=prices.index, columns=model.prices.columns).fillna(0.0)
    asset_returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if prices.empty:
        return {
            "curve": pd.DataFrame(columns=["date", "equity"]),
            "daily_returns": pd.Series(dtype=float),
            "accounting": {"integrity_error": "empty window"},
            "component_contributions": {},
            "component_contribution_status": "unavailable_empty_window",
        }
    prev_equity = STARTING_EQUITY
    prev_weights = normalize_weights(weights.iloc[0])
    equities = [STARTING_EQUITY]
    daily_returns = [0.0]
    for pos in range(1, len(prices)):
        current = normalize_weights(weights.iloc[pos])
        turnover = float((current - prev_weights).abs().sum())
        gross_return = float((current * asset_returns.iloc[pos]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross_return) - prev_equity * turnover * cost)
        daily_returns.append(0.0 if prev_equity <= 0 else equity / prev_equity - 1.0)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    curve = pd.DataFrame({"date": prices.index, "equity": equities})
    return {
        "curve": curve,
        "daily_returns": pd.Series(daily_returns, index=prices.index),
        "accounting": accounting_start_check(curve),
        "reference": buy_hold_reference_check(model, curve, prices),
        "combination_check_passed": True,
        "combination_error_count": 0,
        "component_contributions": {},
        "component_contribution_status": "not_applicable_weighted_model",
    }


def simulate_combo_window_on_index(model: ExperimentModel, index: pd.Index, cost: float) -> dict[str, Any]:
    if not model.sleeve_models or not model.sleeve_weights:
        raise ValueError(f"{model.experiment_id} missing sleeve models.")
    index = pd.DatetimeIndex(index)
    if len(index) == 0:
        return {
            "curve": pd.DataFrame(columns=["date", "equity"]),
            "daily_returns": pd.Series(dtype=float),
            "accounting": {"integrity_error": "empty window"},
            "component_contributions": {},
            "component_contribution_status": "unavailable_empty_window",
        }
    sleeve_returns = pd.DataFrame(index=index)
    for sleeve, sleeve_model in model.sleeve_models.items():
        sleeve_run = simulate_model_window_on_index(sleeve_model, index, cost)
        sleeve_returns[sleeve] = sleeve_run["daily_returns"].reindex(index).fillna(0.0)
    targets = combo_target_weights(index, model.sleeve_weights)
    prev_equity = STARTING_EQUITY
    prev_weights = normalize_weights(targets.iloc[0])
    equities = [STARTING_EQUITY]
    daily_returns = [0.0]
    component_contributions = {sleeve: 0.0 for sleeve in sorted(model.sleeve_weights)}
    turnover_cost_total = 0.0
    bound_violations = 0
    for pos in range(1, len(index)):
        current = normalize_weights(targets.iloc[pos])
        turnover = float((current - prev_weights).abs().sum())
        component_row = sleeve_returns.iloc[pos].reindex(current.index).astype(float)
        gross_return = float((current * component_row).sum())
        active = component_row[current > 0]
        if not active.empty and (gross_return > float(active.max()) + REFERENCE_TOLERANCE or gross_return < float(active.min()) - REFERENCE_TOLERANCE):
            bound_violations += 1
        for sleeve in component_contributions:
            component_contributions[sleeve] += prev_equity * float(current.get(sleeve, 0.0)) * float(component_row.get(sleeve, 0.0))
        turnover_cost = prev_equity * turnover * cost
        turnover_cost_total += turnover_cost
        equity = max(0.0, prev_equity * (1.0 + gross_return) - turnover_cost)
        daily_returns.append(0.0 if prev_equity <= 0 else equity / prev_equity - 1.0)
        equities.append(equity)
        prev_equity = equity
        prev_weights = current
    curve = pd.DataFrame({"date": index, "equity": equities})
    return {
        "curve": curve,
        "daily_returns": pd.Series(daily_returns, index=index),
        "accounting": accounting_start_check(curve),
        "reference": {
            "reference_check_available": False,
            "reference_median_abs_error": math.nan,
            "reference_max_abs_error": math.nan,
            "reference_error_status": "not_applicable",
        },
        "combination_check_passed": bound_violations == 0,
        "combination_error_count": bound_violations,
        "component_contributions": component_contributions,
        "turnover_cost_total": turnover_cost_total,
        "component_contribution_status": "available_final_equity_window_contribution",
    }


def simulate_model_window_on_index(model: ExperimentModel, index: pd.Index, cost: float) -> dict[str, Any]:
    if model.kind == "weighted":
        return simulate_weighted_window_on_index(model, index, cost)
    if model.kind == "combo":
        return simulate_combo_window_on_index(model, index, cost)
    raise ValueError(f"Unknown model kind {model.kind}.")


def drawdown_overlap_flag(left_curve: pd.DataFrame, right_curve: pd.DataFrame, threshold: float = -0.05) -> bool | float:
    left = drawdown_pct_series(left_curve)
    right = drawdown_pct_series(right_curve)
    shared = left.index.intersection(right.index)
    if len(shared) == 0:
        return math.nan
    return bool(((left.loc[shared] <= threshold) & (right.loc[shared] <= threshold)).any())


def drawdown_window_info(curve: pd.DataFrame) -> dict[str, Any]:
    if curve.empty or "equity" not in curve:
        return {
            "worst_drawdown": math.nan,
            "worst_drawdown_start": "",
            "worst_drawdown_end": "",
            "worst_drawdown_window_id": "",
        }
    series = pd.Series(curve["equity"].astype(float).to_numpy(), index=pd.to_datetime(curve["date"]))
    if series.empty:
        return {
            "worst_drawdown": math.nan,
            "worst_drawdown_start": "",
            "worst_drawdown_end": "",
            "worst_drawdown_window_id": "",
        }
    running_high = series.cummax()
    drawdown = series - running_high
    trough_date = drawdown.idxmin()
    peak_date = series.loc[:trough_date].idxmax()
    start = pd.to_datetime(peak_date).date().isoformat()
    end = pd.to_datetime(trough_date).date().isoformat()
    return {
        "worst_drawdown": float(drawdown.loc[trough_date]),
        "worst_drawdown_start": start,
        "worst_drawdown_end": end,
        "worst_drawdown_window_id": f"{start}_to_{end}",
    }


def date_ranges_overlap(left_start: str, left_end: str, right_start: str, right_end: str) -> bool | str:
    if not left_start or not left_end or not right_start or not right_end:
        return "unavailable"
    left_a = pd.to_datetime(left_start)
    left_b = pd.to_datetime(left_end)
    right_a = pd.to_datetime(right_start)
    right_b = pd.to_datetime(right_end)
    return bool(max(left_a, right_a) <= min(left_b, right_b))


def drawdown_overlap_rate(left_curve: pd.DataFrame, right_curve: pd.DataFrame, threshold: float = -0.05) -> float | str:
    left = drawdown_pct_series(left_curve)
    right = drawdown_pct_series(right_curve)
    shared = left.index.intersection(right.index)
    if len(shared) == 0:
        return "unavailable"
    left_stress = left.loc[shared] <= threshold
    if int(left_stress.sum()) == 0:
        return 0.0
    right_stress = right.loc[shared] <= threshold
    return float((left_stress & right_stress).sum() / int(left_stress.sum()))


def diagnostic_window_rows_for_combination(
    combination_id: str,
    models: dict[str, ExperimentModel],
    horizon: int,
    mode: str,
    cost: float,
) -> list[dict[str, Any]]:
    model = models[combination_id]
    starts, possible_count, method = sample_etf_starts(
        model.prices[["SPY"]].rename(columns={"SPY": "value"}) if "SPY" in model.prices else model.prices.iloc[:, :1],
        horizon,
        mode,
        sample_size=40,
    )
    rows: list[dict[str, Any]] = []
    definition = COMBINATION_BATCH1_DEFINITIONS[combination_id]
    components = definition["components"]
    primary_component = components[0]
    secondary_component = components[1]
    for start_idx in starts:
        index = model.prices.iloc[start_idx : start_idx + horizon].index
        if len(index) == 0:
            continue
        combo_run = simulate_model_window_on_index(model, index, cost)
        combo_curve = combo_run["curve"]
        combo_audit = profit_audit(combo_curve["equity"], combo_curve["date"])
        benchmark_runs: dict[str, dict[str, Any]] = {}
        benchmark_audits: dict[str, dict[str, Any]] = {}
        for benchmark_id in ["combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1", "SPY_200d_trend_model"]:
            benchmark_runs[benchmark_id] = simulate_model_window_on_index(models[benchmark_id], index, cost)
            benchmark_curve = benchmark_runs[benchmark_id]["curve"]
            benchmark_audits[benchmark_id] = profit_audit(benchmark_curve["equity"], benchmark_curve["date"]) if not benchmark_curve.empty else {}
        contributions = combo_run.get("component_contributions", {})
        primary_contribution = float(contributions.get(primary_component, math.nan))
        secondary_contribution = float(contributions.get(secondary_component, math.nan))
        final_profit = float(combo_audit["stop_enforced_final_equity"]) - STARTING_EQUITY
        rows.append(
            {
                "combination_id": combination_id,
                "horizon": horizon,
                "cost_mode": "standard",
                "rolling_method": method,
                "possible_window_count": possible_count,
                "window_start": pd.to_datetime(index[0]).date().isoformat(),
                "window_end": pd.to_datetime(index[-1]).date().isoformat(),
                "target_300_hit": bool(combo_audit["target_300_before_stop"]),
                "target_400_hit": bool(combo_audit["target_400_before_stop"]),
                "target_600_hit": bool(combo_audit["target_600_before_stop"]),
                "target_900_hit": bool(combo_audit["target_900_before_stop"]),
                "target_1200_hit": bool(combo_audit["target_1200_before_stop"]),
                "stop_hit": bool(combo_audit["any_project_stop_hit"]),
                "final_equity": combo_audit["stop_enforced_final_equity"],
                "worst_drawdown": combo_audit["max_drawdown_dollars"],
                "combo_benchmark_target_300_hit": bool(benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("target_300_before_stop", False)),
                "combo_benchmark_target_400_hit": bool(benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("target_400_before_stop", False)),
                "top2_benchmark_target_300_hit": bool(benchmark_audits["asset_class_tsmom_top2_v1"].get("target_300_before_stop", False)),
                "top2_benchmark_target_400_hit": bool(benchmark_audits["asset_class_tsmom_top2_v1"].get("target_400_before_stop", False)),
                "incremental_target_300_vs_combo": bool(combo_audit["target_300_before_stop"]) and not bool(benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("target_300_before_stop", False)),
                "incremental_target_400_vs_combo": bool(combo_audit["target_400_before_stop"]) and not bool(benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("target_400_before_stop", False)),
                "incremental_target_300_vs_top2": bool(combo_audit["target_300_before_stop"]) and not bool(benchmark_audits["asset_class_tsmom_top2_v1"].get("target_300_before_stop", False)),
                "incremental_target_400_vs_top2": bool(combo_audit["target_400_before_stop"]) and not bool(benchmark_audits["asset_class_tsmom_top2_v1"].get("target_400_before_stop", False)),
                "primary_component_id": primary_component,
                "secondary_component_id": secondary_component,
                "component_primary_return_contribution_if_available": primary_contribution,
                "component_secondary_return_contribution_if_available": secondary_contribution,
                "component_primary_share_of_profit_if_available": primary_contribution / final_profit if abs(final_profit) > ACCOUNTING_TOLERANCE else math.nan,
                "component_secondary_share_of_profit_if_available": secondary_contribution / final_profit if abs(final_profit) > ACCOUNTING_TOLERANCE else math.nan,
                "turnover_cost_total": float(combo_run.get("turnover_cost_total", math.nan)),
                "component_contribution_status": combo_run.get("component_contribution_status", "unavailable"),
                "combo_benchmark_final_equity": benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("stop_enforced_final_equity", math.nan),
                "top2_benchmark_final_equity": benchmark_audits["asset_class_tsmom_top2_v1"].get("stop_enforced_final_equity", math.nan),
                "spy200d_benchmark_final_equity": benchmark_audits["SPY_200d_trend_model"].get("stop_enforced_final_equity", math.nan),
                "combo_benchmark_worst_drawdown": benchmark_audits["combo_SPY200d_GLD_50_50_v1"].get("max_drawdown_dollars", math.nan),
                "top2_benchmark_worst_drawdown": benchmark_audits["asset_class_tsmom_top2_v1"].get("max_drawdown_dollars", math.nan),
                "spy200d_benchmark_worst_drawdown": benchmark_audits["SPY_200d_trend_model"].get("max_drawdown_dollars", math.nan),
                "combo_drawdown_overlap_flags_if_available": drawdown_overlap_flag(combo_curve, benchmark_runs["combo_SPY200d_GLD_50_50_v1"]["curve"]),
                "top2_drawdown_overlap_flags_if_available": drawdown_overlap_flag(combo_curve, benchmark_runs["asset_class_tsmom_top2_v1"]["curve"]),
                "spy200d_drawdown_overlap_flags_if_available": drawdown_overlap_flag(combo_curve, benchmark_runs["SPY_200d_trend_model"]["curve"]),
            }
        )
    return rows


def build_combination_diagnostics_detail(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    prices = load_prices()
    if prices.empty:
        raise SystemExit("diagnostics-only requires existing local price cache; no download attempted")
    model_ids = set(COMBINATION_BATCH1_IDS) | {
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
    }
    models = {experiment_id: model_for_experiment({"experiment_id": experiment_id}, prices) for experiment_id in model_ids}
    rows: list[dict[str, Any]] = []
    for combination_id in COMBINATION_BATCH1_IDS:
        for horizon in HORIZONS:
            rows.extend(diagnostic_window_rows_for_combination(combination_id, models, horizon, args.mode, LABEL_COSTS["standard"]))
    detail = pd.DataFrame(rows)
    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "diagnostics_only": True,
        "fixed_combination_batch": True,
        "latest_folder_file_count": 0,
        "live_orders": False,
        "new_combination_added": False,
        "order_placement": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": False,
        "real_money_recommendation": False,
        "research_sample_mode": args.mode == "research_sample",
        "row_count": int(len(detail)),
        "run_id": run_id_now(),
        "spy200d_replaced": False,
        "strategy_implemented": False,
        "target_window_comovement_status": "available" if not detail.empty else "unavailable_missing_window_ids",
    }
    return detail, manifest


def build_batch1_attribution_detail(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    normalized = detail.rename(
        columns={
            "combination_id": "experiment_id",
            "combo_benchmark_target_300_hit": "benchmark_combo_target_300_hit",
            "combo_benchmark_target_400_hit": "benchmark_combo_target_400_hit",
            "top2_benchmark_target_300_hit": "benchmark_top2_target_300_hit",
            "top2_benchmark_target_400_hit": "benchmark_top2_target_400_hit",
        }
    )
    target_attribution = compute_target_window_attribution(normalized)
    target_attribution.insert(0, "attribution_family", "target_window_attribution")

    component_rows: list[dict[str, Any]] = []
    for _, row in detail.iterrows():
        for role in ["primary", "secondary"]:
            component_id = row.get(f"{role}_component_id", "")
            if not component_id:
                continue
            component_rows.append(
                {
                    "attribution_family": "component_contribution",
                    "experiment_id": row.get("combination_id", ""),
                    "horizon": row.get("horizon", ""),
                    "cost_mode": row.get("cost_mode", ""),
                    "window_start": row.get("window_start", ""),
                    "window_end": row.get("window_end", ""),
                    "component_id": component_id,
                    "component_return_contribution": row.get(f"component_{role}_return_contribution_if_available", math.nan),
                    "component_final_equity_contribution": row.get(f"component_{role}_return_contribution_if_available", math.nan),
                    "component_drawdown_contribution": "unavailable_needs_component_daily_contribution_stream",
                    "component_recovery_contribution": "unavailable_needs_component_daily_contribution_stream",
                    "contribution_status": row.get("component_contribution_status", "unavailable"),
                }
            )
    component_attribution = pd.DataFrame(component_rows)

    worst_rows = []
    for experiment_id in COMBINATION_BATCH1_IDS:
        worst = extract_worst_n_drawdown_windows(normalized, n=5, experiment_id=experiment_id)
        if not worst.empty:
            worst = worst.copy()
            worst.insert(0, "attribution_family", "worst_n_drawdown_windows")
            worst_rows.append(worst)
    worst_attribution = pd.concat(worst_rows, ignore_index=True) if worst_rows else pd.DataFrame()

    frames = [frame for frame in [target_attribution, component_attribution, worst_attribution] if not frame.empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def write_batch1_attribution_diagnostics(detail: pd.DataFrame, run_id: str) -> Path:
    output_dir = RESEARCH_DIAGNOSTICS_OUTPUT_ROOT / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)
    attribution = build_batch1_attribution_detail(detail)
    output_path = output_dir / "batch1_attribution_detail.csv"
    attribution.to_csv(output_path, index=False)
    export_manifest = {
        "active_combo_rule_changed": False,
        "attribution_diagnostics_exported": True,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "live_orders": False,
        "new_combination_added": False,
        "order_placement": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_latest_rewritten": False,
        "real_money_recommendation": False,
        "row_count": int(len(attribution)),
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": False,
    }
    (output_dir / "attribution_diagnostics_export_manifest.json").write_text(
        json.dumps(export_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_combination_diagnostics_only_outputs(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    detail, manifest = build_combination_diagnostics_detail(args)
    run_id = str(manifest["run_id"])
    run_dir = COMBINATION_DIAGNOSTICS_COMPLETION_ROOT / "runs" / run_id
    latest_dir = COMBINATION_DIAGNOSTICS_COMPLETION_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    detail_csv = detail.to_csv(index=False)
    manifest["latest_folder_file_count"] = 2
    for output_dir in [run_dir, latest_dir]:
        (output_dir / COMBINATION_DIAGNOSTICS_DETAIL_FILE).write_text(detail_csv, encoding="utf-8")
        (output_dir / "diagnostics_only_export_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if getattr(args, "export_attribution_diagnostics", False):
        attribution_path = write_batch1_attribution_diagnostics(detail, run_id)
        manifest["attribution_diagnostics_exported"] = True
        manifest["attribution_diagnostics_path"] = str(attribution_path)
        for output_dir in [run_dir, latest_dir]:
            (output_dir / "diagnostics_only_export_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir, latest_dir, manifest


def commodity_component_ids(experiment_id: str) -> tuple[str, str, str]:
    if experiment_id == "commodity_basket_tsmom_top2_half_bil_v1":
        return COMMODITY_EXPLORATORY_EXPERIMENT_ID, "BIL_cash_proxy", "BIL_cash_proxy"
    if experiment_id == "combo_plus_commodity_basket_80_20_v1":
        return "combo_SPY200d_GLD_50_50_v1", COMMODITY_EXPLORATORY_EXPERIMENT_ID, ""
    return "", "", ""


def component_value(contributions: dict[str, Any], component_id: str) -> float | str:
    if not component_id:
        return "unavailable"
    value = contributions.get(component_id, math.nan)
    if pd.isna(value):
        return "unavailable"
    return float(value)


def commodity_filter_window_diagnostics(
    models: dict[str, ExperimentModel],
    index: pd.Index,
) -> dict[str, Any]:
    base = models.get(COMMODITY_EXPLORATORY_EXPERIMENT_ID)
    filtered = models.get("commodity_basket_tsmom_top2_200d_filter_v1")
    if base is None or filtered is None or base.weights is None or filtered.weights is None:
        return {
            "filter_binding_status": "unavailable_missing_weight_stream",
            "filter_weight_difference_days": "unavailable",
            "filter_weights_identical_to_base": "unavailable",
            "filter_window_total_abs_weight_difference": "unavailable",
        }
    columns = [*COMMODITY_EXPLORATORY_SYMBOLS, "BIL"]
    base_weights = base.weights.reindex(index=index, columns=columns, fill_value=0.0).fillna(0.0)
    filtered_weights = filtered.weights.reindex(index=index, columns=columns, fill_value=0.0).fillna(0.0)
    diffs = (base_weights - filtered_weights).abs().sum(axis=1)
    diff_days = int((diffs > ACCOUNTING_TOLERANCE).sum())
    return {
        "filter_binding_status": "available",
        "filter_weight_difference_days": diff_days,
        "filter_weights_identical_to_base": bool(diff_days == 0),
        "filter_window_total_abs_weight_difference": float(diffs.sum()),
    }


def diagnostic_window_rows_for_commodity_risk_control(
    experiment_id: str,
    models: dict[str, ExperimentModel],
    horizon: int,
    mode: str,
    cost: float,
) -> list[dict[str, Any]]:
    model = models[experiment_id]
    starts, possible_count, method = sample_etf_starts(
        model.prices[["SPY"]].rename(columns={"SPY": "value"}) if "SPY" in model.prices else model.prices.iloc[:, :1],
        horizon,
        mode,
        sample_size=40,
    )
    benchmark_ids = {
        "base_commodity": COMMODITY_EXPLORATORY_EXPERIMENT_ID,
        "combo": "combo_SPY200d_GLD_50_50_v1",
        "top2": "asset_class_tsmom_top2_v1",
        "spy200d": "SPY_200d_trend_model",
        "gld": "GLD_buy_hold",
    }
    primary_component, secondary_component, bil_component = commodity_component_ids(experiment_id)
    rows: list[dict[str, Any]] = []
    for start_idx in starts:
        index = model.prices.iloc[start_idx : start_idx + horizon].index
        if len(index) == 0:
            continue
        candidate_run = simulate_model_window_on_index(model, index, cost)
        candidate_curve = candidate_run["curve"]
        candidate_audit = profit_audit(candidate_curve["equity"], candidate_curve["date"]) if not candidate_curve.empty else {}
        candidate_dd = drawdown_window_info(candidate_curve)
        benchmark_runs: dict[str, dict[str, Any]] = {}
        benchmark_audits: dict[str, dict[str, Any]] = {}
        benchmark_dd: dict[str, dict[str, Any]] = {}
        for label, benchmark_id in benchmark_ids.items():
            benchmark_runs[label] = simulate_model_window_on_index(models[benchmark_id], index, cost)
            benchmark_curve = benchmark_runs[label]["curve"]
            benchmark_audits[label] = profit_audit(benchmark_curve["equity"], benchmark_curve["date"]) if not benchmark_curve.empty else {}
            benchmark_dd[label] = drawdown_window_info(benchmark_curve)
        contributions = candidate_run.get("component_contributions", {})
        filter_diagnostics = (
            commodity_filter_window_diagnostics(models, index)
            if experiment_id == "commodity_basket_tsmom_top2_200d_filter_v1"
            else {
                "filter_binding_status": "not_applicable",
                "filter_weight_difference_days": "",
                "filter_weights_identical_to_base": "",
                "filter_window_total_abs_weight_difference": "",
            }
        )
        row: dict[str, Any] = {
            "experiment_id": experiment_id,
            "horizon": horizon,
            "cost_mode": "standard",
            "rolling_method": method,
            "possible_window_count": possible_count,
            "window_start": pd.to_datetime(index[0]).date().isoformat(),
            "window_end": pd.to_datetime(index[-1]).date().isoformat(),
            "target_300_hit": bool(candidate_audit.get("target_300_before_stop", False)),
            "target_400_hit": bool(candidate_audit.get("target_400_before_stop", False)),
            "target_600_hit": bool(candidate_audit.get("target_600_before_stop", False)),
            "target_900_hit": bool(candidate_audit.get("target_900_before_stop", False)),
            "target_1200_hit": bool(candidate_audit.get("target_1200_before_stop", False)),
            "stop_hit": bool(candidate_audit.get("any_project_stop_hit", False)),
            "final_equity": candidate_audit.get("stop_enforced_final_equity", math.nan),
            "worst_drawdown": candidate_audit.get("max_drawdown_dollars", math.nan),
            "component_primary_id_if_available": primary_component,
            "component_secondary_id_if_available": secondary_component,
            "component_primary_contribution_if_available": component_value(contributions, primary_component),
            "component_secondary_contribution_if_available": component_value(contributions, secondary_component),
            "component_bil_contribution_if_available": component_value(contributions, bil_component),
            "component_contribution_status": candidate_run.get("component_contribution_status", "unavailable"),
            "worst_drawdown_start_if_available": candidate_dd["worst_drawdown_start"],
            "worst_drawdown_end_if_available": candidate_dd["worst_drawdown_end"],
            "worst_drawdown_window_id_if_available": candidate_dd["worst_drawdown_window_id"],
            **filter_diagnostics,
        }
        for label in benchmark_ids:
            for target in ["300", "400"]:
                row[f"{label}_target_{target}_hit"] = bool(benchmark_audits[label].get(f"target_{target}_before_stop", False))
                row[f"incremental_{target}_vs_{label}"] = bool(row[f"target_{target}_hit"]) and not bool(row[f"{label}_target_{target}_hit"])
            row[f"{label}_final_equity"] = benchmark_audits[label].get("stop_enforced_final_equity", math.nan)
            row[f"{label}_worst_drawdown"] = benchmark_audits[label].get("max_drawdown_dollars", math.nan)
            row[f"{label}_worst_drawdown_start"] = benchmark_dd[label]["worst_drawdown_start"]
            row[f"{label}_worst_drawdown_end"] = benchmark_dd[label]["worst_drawdown_end"]
            row[f"drawdown_overlap_vs_{label}_if_available"] = date_ranges_overlap(
                str(candidate_dd["worst_drawdown_start"]),
                str(candidate_dd["worst_drawdown_end"]),
                str(benchmark_dd[label]["worst_drawdown_start"]),
                str(benchmark_dd[label]["worst_drawdown_end"]),
            )
            row[f"drawdown_overlap_rate_vs_{label}_if_available"] = drawdown_overlap_rate(
                candidate_curve,
                benchmark_runs[label]["curve"],
            )
        rows.append(row)
    return rows


def build_commodity_risk_control_diagnostics_detail(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    prices = load_prices()
    if prices.empty:
        raise SystemExit("diagnostics-only requires existing local price cache; no download attempted")
    model_ids = set(COMMODITY_RISK_CONTROL_REQUIRED_RUN_IDS) | {"GLD_buy_hold"}
    models = {experiment_id: model_for_experiment({"experiment_id": experiment_id}, prices) for experiment_id in model_ids}
    rows: list[dict[str, Any]] = []
    for experiment_id in COMMODITY_RISK_CONTROL_BATCH1_IDS:
        for horizon in HORIZONS:
            rows.extend(diagnostic_window_rows_for_commodity_risk_control(experiment_id, models, horizon, args.mode, LABEL_COSTS["standard"]))
    detail = pd.DataFrame(rows)
    contribution_status = "available_final_equity_window_contribution" if "component_contribution_status" in detail and detail["component_contribution_status"].astype(str).str.contains("available").any() else "unavailable"
    manifest = {
        "active_combo_rule_changed": False,
        "attribution_diagnostics_exported": bool(getattr(args, "export_attribution_diagnostics", False)),
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "diagnostics_only": True,
        "direct_futures_contract_logic": False,
        "fixed_commodity_risk_control_batch": True,
        "latest_folder_file_count": 0,
        "live_orders": False,
        "new_commodity_variants_added": False,
        "new_symbols_added": False,
        "order_placement": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_latest_rewritten": False,
        "profit_exploration_run": False,
        "real_money_recommendation": False,
        "research_sample_mode": args.mode == "research_sample",
        "row_count": int(len(detail)),
        "run_id": run_id_now(),
        "spy200d_replaced": False,
        "strategy_implemented": False,
        "target_window_comovement_status": "available" if not detail.empty else "unavailable_missing_window_ids",
        "component_contribution_status": contribution_status,
        "drawdown_overlap_status": "available" if not detail.empty else "unavailable_missing_window_ids",
    }
    return detail, manifest


def write_commodity_risk_control_diagnostics_only_outputs(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    detail, manifest = build_commodity_risk_control_diagnostics_detail(args)
    run_id = str(manifest["run_id"])
    run_dir = COMMODITY_RISK_CONTROL_DIAGNOSTICS_COMPLETION_ROOT / "runs" / run_id
    latest_dir = COMMODITY_RISK_CONTROL_DIAGNOSTICS_COMPLETION_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    detail_csv = detail.to_csv(index=False)
    manifest["latest_folder_file_count"] = 2
    for output_dir in [run_dir, latest_dir]:
        (output_dir / COMMODITY_RISK_CONTROL_DIAGNOSTICS_DETAIL_FILE).write_text(detail_csv, encoding="utf-8")
        (output_dir / "diagnostics_only_export_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir, latest_dir, manifest


def build_combination_lab_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    batch_rankings = rankings[rankings["experiment_id"].isin(COMBINATION_BATCH1_IDS)].copy()
    batch_results = results[
        results["experiment_id"].isin(COMBINATION_BATCH1_IDS)
        & results["standard_or_stress"].eq("standard")
    ].copy()
    batch_status = status[status["experiment_id"].isin(COMBINATION_BATCH1_IDS)].copy() if "experiment_id" in status else pd.DataFrame()
    combo_benchmark = rankings[rankings["experiment_id"].eq("combo_SPY200d_GLD_50_50_v1")]
    top2_benchmark = rankings[rankings["experiment_id"].eq("asset_class_tsmom_top2_v1")]

    result_rows: list[dict[str, Any]] = []
    for exp_id in COMBINATION_BATCH1_IDS:
        definition = COMBINATION_BATCH1_DEFINITIONS[exp_id]
        rank_row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        status_row = batch_status[batch_status["experiment_id"].eq(exp_id)] if not batch_status.empty else pd.DataFrame()
        for benchmark_id, benchmark_frame in [
            ("combo_SPY200d_GLD_50_50_v1", combo_benchmark),
            ("asset_class_tsmom_top2_v1", top2_benchmark),
            ("SPY_200d_trend_model", rankings[rankings["experiment_id"].eq("SPY_200d_trend_model")]),
        ]:
            row = rank_row.iloc[0] if not rank_row.empty else pd.Series(dtype=object)
            benchmark = benchmark_frame.iloc[0] if not benchmark_frame.empty else pd.Series(dtype=object)
            result_rows.append(
                {
                    "combination_id": exp_id,
                    "benchmark_id": benchmark_id,
                    "components": ";".join(definition["components"]),
                    "fixed_weights": json.dumps(definition["weights"], sort_keys=True),
                    "run_status": row.get("run_status", "incomplete_evidence"),
                    "verdict": row.get("profit_verdict", "incomplete_evidence"),
                    "deserves_candidate_exhaustive": boolish(row.get("deserves_candidate_exhaustive", False)),
                    "p_90d_target_300_before_stop": row.get("p_90d_target_300_before_stop", math.nan),
                    "p_90d_target_400_before_stop": row.get("p_90d_target_400_before_stop", math.nan),
                    "p_180d_target_300_before_stop": row.get("p_180d_target_300_before_stop", math.nan),
                    "p_180d_target_400_before_stop": row.get("p_180d_target_400_before_stop", math.nan),
                    "p_90d_any_stop_hit": row.get("p_90d_any_stop_hit", math.nan),
                    "worst_90d_max_drawdown": row.get("worst_90d_max_drawdown", math.nan),
                    "median_90d_stop_enforced_final_equity": row.get("median_90d_stop_enforced_final_equity", math.nan),
                    "p95_90d_stop_enforced_final_equity": row.get("p95_90d_stop_enforced_final_equity", math.nan),
                    "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                    "benchmark_balanced_drawdown_aware_score_v2": benchmark.get("balanced_drawdown_aware_score_v2", math.nan),
                    "score_delta_vs_benchmark": (
                        float(row.get("balanced_drawdown_aware_score_v2")) - float(benchmark.get("balanced_drawdown_aware_score_v2"))
                        if pd.notna(row.get("balanced_drawdown_aware_score_v2", math.nan)) and pd.notna(benchmark.get("balanced_drawdown_aware_score_v2", math.nan))
                        else math.nan
                    ),
                    "required_label": definition.get("required_label", ""),
                    "status_notes": status_row["status_notes"].iloc[0] if not status_row.empty and "status_notes" in status_row else "",
                }
            )

    rankings_rows = []
    for _, row in batch_rankings.sort_values("rank_balanced_drawdown_aware_v2").iterrows():
        rankings_rows.append(
            {
                "rank_stop_aware_practical": row.get("rank_balanced_drawdown_aware_v2", math.nan),
                "rank_profit_seeking": row.get("rank_profit_seeking_score", math.nan),
                "rank_drawdown_control": row.get("rank_drawdown_control_score", math.nan),
                "combination_id": row.get("experiment_id", ""),
                "verdict": row.get("profit_verdict", ""),
                "run_status": row.get("run_status", ""),
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                "profit_seeking_score": row.get("profit_seeking_score", math.nan),
                "drawdown_control_score": row.get("drawdown_control_score", math.nan),
                "deserves_candidate_exhaustive": boolish(row.get("deserves_candidate_exhaustive", False)),
                "notes": row.get("ranking_notes", ""),
            }
        )

    risk_rows = []
    for exp_id in COMBINATION_BATCH1_IDS:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        item = row.iloc[0] if not row.empty else pd.Series(dtype=object)
        risk_rows.append(
            {
                "combination_id": exp_id,
                "stop_hit_rate_90d": item.get("p_90d_any_stop_hit", math.nan),
                "stop_hit_rate_180d": item.get("p_180d_any_stop_hit", math.nan),
                "worst_drawdown_90d": item.get("worst_90d_max_drawdown", math.nan),
                "worst_drawdown_180d": item.get("worst_180d_max_drawdown", math.nan),
                "risk_budget_usage_90d": item.get("risk_budget_used_90d", math.nan),
                "risk_budget_usage_180d": item.get("risk_budget_used_180d", math.nan),
                "stress_degradation": item.get("stress_degradation", math.nan),
                "short_history_warning": boolish(item.get("short_history_warning", False)),
                "duplicate_warning": boolish(item.get("duplicate_correlation_warning", False)),
            }
        )

    status_rows = []
    for exp_id in COMBINATION_BATCH1_IDS:
        row = batch_rankings[batch_rankings["experiment_id"].eq(exp_id)]
        item = row.iloc[0] if not row.empty else pd.Series(dtype=object)
        run_status = item.get("run_status", "incomplete_evidence")
        status_rows.append(
            {
                "combination_id": exp_id,
                "status": "completed" if run_status == "completed" else "incomplete_evidence",
                "verdict": item.get("profit_verdict", "incomplete_evidence"),
                "reason": item.get("queue_reason", item.get("ranking_notes", "")),
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
            }
        )

    correlation = build_combination_correlation_diagnostics(curves)
    completed_count = int(batch_rankings["run_status"].astype(str).eq("completed").sum()) if not batch_rankings.empty else 0
    queued = batch_rankings[batch_rankings.get("deserves_candidate_exhaustive", pd.Series(dtype=bool)).map(boolish)] if not batch_rankings.empty else pd.DataFrame()
    best_row = batch_rankings.sort_values("rank_balanced_drawdown_aware_v2").iloc[0] if not batch_rankings.empty else pd.Series(dtype=object)
    best_combination = best_row.get("experiment_id", "none")
    overall_verdict = "candidate_exhaustive_review_required" if not queued.empty else ("completed_no_candidate_exhaustive_queue" if completed_count else "incomplete_evidence")
    managed_helped = "review metrics; managed-futures blends remain short-history fund-wrapper evidence"
    if not batch_rankings.empty:
        managed_rows = batch_rankings[batch_rankings["experiment_id"].isin(COMBINATION_BATCH1_MANAGED_FUTURES_IDS)]
        if not managed_rows.empty:
            managed_helped = "; ".join(f"{row['experiment_id']}={row.get('profit_verdict', '')}" for _, row in managed_rows.iterrows())
    summary = f"""# Historical Combination Batch 1 Summary

overall_verdict: `{overall_verdict}`

Best combination by stop-aware practical rank: `{best_combination}`.

Any combination deserves candidate_exhaustive now: `{str(not queued.empty).lower()}`.

Managed-futures combination effect: {managed_helped}.

Combo+top2 improvement review: {metric_value(batch_rankings, 'combo_plus_top2_50_50_v1', 'profit_verdict')}.

Incomplete rows: {', '.join(status_rows_item['combination_id'] for status_rows_item in status_rows if status_rows_item['status'] != 'completed') or 'none'}.

The batch used exactly three fixed predeclared combinations. It did not run candidate_exhaustive, did not download data, did not change active combo paper-forward rules, did not replace SPY_200d, and did not make a real-money recommendation.
"""

    readme = """# README For Advisor

This is a compact Historical Combination Research Sample Batch 1 evidence packet.

It contains exactly three fixed predeclared historical combination rows. It is research-only, research_sample only, and contains no raw OHLCV, no broker integration, no live orders, no order placement, and no real-money recommendation.
"""

    warnings = f"""# Warnings And Limitations

- Research-only paper/demo evidence.
- No real-money recommendation.
- No broker integration, live orders, or order placement.
- Candidate_exhaustive was not run.
- Data was not downloaded or refreshed.
- Active combo paper/demo observation rules were not changed.
- SPY_200d remains frozen control and was not replaced.
- Fixed weights were predeclared; no optimization, grid search, leverage, margin, or shorting.
- Managed-futures combination rows carry `{MANAGED_FUTURES_REQUIRED_LABEL}`.
- Correlation diagnostics are calculated from generated equity-curve returns when available; unavailable fields must not be inferred from labels.
"""

    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "fixed_combination_batch": True,
        "latest_folder_file_count": len(COMBINATION_REQUIRED_LATEST_FILES),
        "live_orders": False,
        "new_strategy_family": False,
        "order_placement": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": True,
        "real_money_recommendation": False,
        "research_sample_run": True,
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": True,
        "combination_ids": COMBINATION_BATCH1_IDS,
        "overall_verdict": overall_verdict,
    }

    return {
        "README_FOR_ADVISOR.md": readme,
        "combination_batch1_summary.md": summary,
        "combination_batch1_results.csv": pd.DataFrame(result_rows).to_csv(index=False),
        "combination_batch1_rankings.csv": pd.DataFrame(rankings_rows).to_csv(index=False),
        "combination_batch1_risk_summary.csv": pd.DataFrame(risk_rows).to_csv(index=False),
        "combination_batch1_correlation_diagnostics.csv": correlation.to_csv(index=False),
        "combination_batch1_status.csv": pd.DataFrame(status_rows).to_csv(index=False),
        "warnings_and_limitations.md": warnings,
        "combination_batch1_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "_manifest": manifest,
    }


def write_combination_batch1_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> tuple[Path, Path, Path]:
    outputs = build_combination_lab_outputs(run_id, results, rolling, rankings, status, curves)
    run_dir = COMBINATION_OUTPUT_ROOT / "runs" / run_id
    latest_dir = COMBINATION_OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for name in COMBINATION_REQUIRED_LATEST_FILES:
        text = outputs[name]
        (run_dir / name).write_text(text, encoding="utf-8")
        (latest_dir / name).write_text(text, encoding="utf-8")
    files = sorted(path.name for path in latest_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(COMBINATION_REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Combination batch evidence contract failed: {files}")
    zip_path = COMBINATION_OUTPUT_ROOT / "latest_combination_batch1_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir, zip_path


def build_commodity_exploratory_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
) -> dict[str, Any]:
    exp_id = COMMODITY_EXPLORATORY_EXPERIMENT_ID
    commodity_rank = rankings[rankings["experiment_id"].eq(exp_id)].copy() if "experiment_id" in rankings else pd.DataFrame()
    commodity_status = status[status["experiment_id"].eq(exp_id)].copy() if "experiment_id" in status else pd.DataFrame()
    commodity_results = results[
        results["experiment_id"].eq(exp_id)
        & results["standard_or_stress"].eq("standard")
    ].copy() if "experiment_id" in results else pd.DataFrame()
    row = commodity_rank.iloc[0] if not commodity_rank.empty else pd.Series(dtype=object)
    run_status = str(row.get("run_status", "incomplete_evidence"))
    verdict = str(row.get("profit_verdict", "incomplete_evidence"))
    deserves = boolish(row.get("deserves_candidate_exhaustive", False))
    benchmark_ids = [
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
    ]

    result_rows: list[dict[str, Any]] = []
    standard_rolling = rolling[
        rolling["experiment_id"].eq(exp_id)
        & rolling["standard_or_stress"].eq("standard")
    ].copy() if "experiment_id" in rolling else pd.DataFrame()
    for _, metric in standard_rolling.sort_values("horizon").iterrows():
        result_rows.append(
            {
                "experiment_id": exp_id,
                "horizon": int(metric.get("horizon", 0)),
                "run_status": run_status,
                "verdict": verdict,
                "p_target_300_before_stop": metric.get("p_target_300_before_stop", math.nan),
                "p_target_400_before_stop": metric.get("p_target_400_before_stop", math.nan),
                "p_target_600_before_stop": metric.get("p_target_600_before_stop", math.nan),
                "p_target_900_before_stop": metric.get("p_target_900_before_stop", math.nan),
                "p_target_1200_before_stop": metric.get("p_target_1200_before_stop", math.nan),
                "p_any_project_stop_hit": metric.get("p_any_project_stop_hit", math.nan),
                "median_stop_enforced_final_equity": metric.get("median_stop_enforced_final_equity", math.nan),
                "p95_stop_enforced_final_equity": metric.get("p95_stop_enforced_final_equity", math.nan),
                "worst_max_drawdown": metric.get("worst_max_drawdown", math.nan),
                "risk_budget_usage": abs(min(0.0, float(metric.get("worst_max_drawdown", 0.0)))) / TRAILING_DRAWDOWN,
            }
        )
    for benchmark_id in benchmark_ids:
        benchmark = rankings[rankings["experiment_id"].eq(benchmark_id)] if "experiment_id" in rankings else pd.DataFrame()
        bench_row = benchmark.iloc[0] if not benchmark.empty else pd.Series(dtype=object)
        result_rows.append(
            {
                "experiment_id": exp_id,
                "horizon": "benchmark_comparison",
                "benchmark_id": benchmark_id,
                "run_status": run_status,
                "verdict": verdict,
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                "benchmark_balanced_drawdown_aware_score_v2": bench_row.get("balanced_drawdown_aware_score_v2", math.nan),
                "score_delta_vs_benchmark": (
                    float(row.get("balanced_drawdown_aware_score_v2")) - float(bench_row.get("balanced_drawdown_aware_score_v2"))
                    if pd.notna(row.get("balanced_drawdown_aware_score_v2", math.nan)) and pd.notna(bench_row.get("balanced_drawdown_aware_score_v2", math.nan))
                    else math.nan
                ),
            }
        )

    risk_rows = []
    for horizon in [90, 180]:
        metric = standard_rolling[standard_rolling["horizon"].eq(horizon)]
        item = metric.iloc[0] if not metric.empty else pd.Series(dtype=object)
        worst = float(item.get("worst_max_drawdown", math.nan)) if pd.notna(item.get("worst_max_drawdown", math.nan)) else math.nan
        risk_rows.append(
            {
                "experiment_id": exp_id,
                "horizon": horizon,
                "stop_hit_rate": item.get("p_any_project_stop_hit", math.nan),
                "worst_drawdown": worst,
                "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                "stress_degradation": row.get("stress_degradation", math.nan),
                "bil_fallback_frequency": row.get("bil_fallback_frequency", math.nan),
                "bil_fallback_allocation_share": row.get("bil_fallback_allocation_share", math.nan),
                "max_single_commodity_wrapper_allocation": row.get("max_single_commodity_wrapper_allocation", math.nan),
                "product_concentration_warning": boolish(row.get("product_concentration_warning", False)),
                "required_label": COMMODITY_EXPLORATORY_REQUIRED_LABEL,
            }
        )

    ranking_row = {
        "rank_overall": row.get("rank_overall", math.nan),
        "rank_stop_aware_practical": row.get("rank_balanced_drawdown_aware_v2", math.nan),
        "rank_profit_seeking": row.get("rank_profit_seeking_score", math.nan),
        "rank_drawdown_control": row.get("rank_drawdown_control_score", math.nan),
        "experiment_id": exp_id,
        "verdict": verdict,
        "run_status": run_status,
        "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
        "profit_seeking_score": row.get("profit_seeking_score", math.nan),
        "drawdown_control_score": row.get("drawdown_control_score", math.nan),
        "deserves_candidate_exhaustive": deserves,
        "notes": row.get("ranking_notes", ""),
    }
    status_row = {
        "experiment_id": exp_id,
        "status": "completed" if run_status == "completed" else "incomplete_evidence",
        "verdict": verdict,
        "candidate_exhaustive_review_justified": deserves,
        "paper_forward_active": False,
        "real_money_recommendation": False,
        "reason": row.get("queue_reason", row.get("ranking_notes", "")),
    }
    quality_manifest = {}
    acquisition_manifest_path = REPO_ROOT / "evidence" / "data_acquisition_runs" / "commodity_basket_fast_exploratory" / "latest" / "acquisition_manifest.json"
    if acquisition_manifest_path.exists():
        quality_manifest = json.loads(acquisition_manifest_path.read_text(encoding="utf-8"))
    summary = f"""# Commodity Exploratory Summary

overall_verdict: `{verdict}`

run_status: `{run_status}`

candidate_exhaustive_review_justified: `{str(deserves).lower()}`

symbols_used: {', '.join(COMMODITY_EXPLORATORY_SYMBOLS)} with BIL fallback.

data_source_cache_status: controlled fast exploratory yfinance-compatible acquisition; downloaded symbols: {', '.join(quality_manifest.get('downloaded_symbols', [])) if quality_manifest else 'unavailable'}; failed symbols: {', '.join(quality_manifest.get('failed_symbols', [])) if quality_manifest else 'unavailable'}.

BIL fallback frequency: `{pct_text(row.get('bil_fallback_frequency'))}`. BIL allocation share: `{pct_text(row.get('bil_fallback_allocation_share'))}`.

Product concentration: max wrapper allocation `{pct_text(row.get('max_single_commodity_wrapper_allocation'))}`; warning `{str(boolish(row.get('product_concentration_warning', False))).lower()}`.

Comparison versus combo/top2/SPY_200d/GLD is reported in `commodity_exploratory_results.csv` using balanced_drawdown_aware_score_v2 deltas when available.

This is exploratory public-data commodity wrapper evidence only. It is not candidate_exhaustive, not paper-forward, not direct futures strategy evidence, and not a real-money recommendation.
"""
    readme = """# README For Advisor

This is the compact commodity basket exploratory research_sample packet.

It contains metadata and result summaries only. It excludes raw OHLCV, does not run candidate_exhaustive, does not activate paper-forward, does not use direct futures contracts, does not connect to brokers, and does not make a real-money recommendation.
"""
    warnings = f"""# Warnings And Limitations

- Research-only paper/demo evidence.
- Fast exploratory public ETF/fund wrapper data only.
- Required label: `{COMMODITY_EXPLORATORY_REQUIRED_LABEL}`.
- yfinance-compatible data can have revisions, adjustment differences, missing actions, provider outages, and ticker mapping issues.
- Commodity wrapper returns may embed roll yield, collateral, fees, product methodology, product closure risk, tax/K-1 complexity, and liquidity/spread effects.
- Adjusted wrapper price modeling is not direct futures strategy evidence.
- No futures contracts, futures roll logic, leverage, margin, shorting, broker integration, live orders, order placement, or real-money recommendation.
- Candidate_exhaustive and paper-forward activation remain blocked unless a separate later gate approves them.
"""
    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "controlled_fast_exploratory_acquisition_used": bool(quality_manifest),
        "data_downloaded_by_acquisition_lane": bool(quality_manifest.get("data_downloaded", False)) if quality_manifest else False,
        "direct_futures_contract_logic": False,
        "experiment_id": exp_id,
        "latest_folder_file_count": len(COMMODITY_EXPLORATORY_REQUIRED_LATEST_FILES),
        "live_orders": False,
        "order_placement": False,
        "paper_forward_active": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": True,
        "real_money_recommendation": False,
        "research_sample_run": True,
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": True,
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "verdict": verdict,
        "candidate_exhaustive_review_justified": deserves,
        "required_label": COMMODITY_EXPLORATORY_REQUIRED_LABEL,
    }
    return {
        "README_FOR_ADVISOR.md": readme,
        "commodity_exploratory_summary.md": summary,
        "commodity_exploratory_results.csv": pd.DataFrame(result_rows).to_csv(index=False),
        "commodity_exploratory_risk_summary.csv": pd.DataFrame(risk_rows).to_csv(index=False),
        "commodity_exploratory_rankings.csv": pd.DataFrame([ranking_row]).to_csv(index=False),
        "commodity_exploratory_status.csv": pd.DataFrame([status_row]).to_csv(index=False),
        "warnings_and_limitations.md": warnings,
        "commodity_exploratory_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "_manifest": manifest,
    }


def write_commodity_exploratory_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    outputs = build_commodity_exploratory_outputs(run_id, results, rolling, rankings, status)
    run_dir = COMMODITY_EXPLORATORY_OUTPUT_ROOT / "runs" / run_id
    latest_dir = COMMODITY_EXPLORATORY_OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for name in COMMODITY_EXPLORATORY_REQUIRED_LATEST_FILES:
        text = outputs[name]
        (run_dir / name).write_text(text, encoding="utf-8")
        (latest_dir / name).write_text(text, encoding="utf-8")
    files = sorted(path.name for path in latest_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(COMMODITY_EXPLORATORY_REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Commodity exploratory evidence contract failed: {files}")
    zip_path = COMMODITY_EXPLORATORY_OUTPUT_ROOT / "latest_commodity_exploratory_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir, zip_path


def build_commodity_risk_control_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    batch_ids = COMMODITY_RISK_CONTROL_BATCH1_IDS
    benchmark_ids = [
        COMMODITY_EXPLORATORY_EXPERIMENT_ID,
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
        "BIL_cash_proxy",
    ]
    rank_by_id = {str(row["experiment_id"]): row for _, row in rankings.iterrows()} if "experiment_id" in rankings else {}
    standard_rolling = rolling[rolling["standard_or_stress"].eq("standard")].copy() if "standard_or_stress" in rolling else pd.DataFrame()

    result_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for exp_id in batch_ids:
        row = rank_by_id.get(exp_id, pd.Series(dtype=object))
        run_status = str(row.get("run_status", "incomplete_evidence"))
        verdict = str(row.get("profit_verdict", "incomplete_evidence"))
        deserves = boolish(row.get("deserves_candidate_exhaustive", False))
        rolling_subset = standard_rolling[standard_rolling["experiment_id"].eq(exp_id)] if "experiment_id" in standard_rolling else pd.DataFrame()
        for _, metric in rolling_subset.sort_values("horizon").iterrows():
            worst = float(metric.get("worst_max_drawdown", math.nan)) if pd.notna(metric.get("worst_max_drawdown", math.nan)) else math.nan
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "candidate_horizon",
                    "horizon": int(metric.get("horizon", 0)),
                    "run_status": run_status,
                    "verdict": verdict,
                    "p_target_300_before_stop": metric.get("p_target_300_before_stop", math.nan),
                    "p_target_400_before_stop": metric.get("p_target_400_before_stop", math.nan),
                    "p_target_600_before_stop": metric.get("p_target_600_before_stop", math.nan),
                    "p_target_900_before_stop": metric.get("p_target_900_before_stop", math.nan),
                    "p_target_1200_before_stop": metric.get("p_target_1200_before_stop", math.nan),
                    "p_any_project_stop_hit": metric.get("p_any_project_stop_hit", math.nan),
                    "median_stop_enforced_final_equity": metric.get("median_stop_enforced_final_equity", math.nan),
                    "p95_stop_enforced_final_equity": metric.get("p95_stop_enforced_final_equity", math.nan),
                    "worst_max_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                }
            )
        for benchmark_id in benchmark_ids:
            bench_row = rank_by_id.get(benchmark_id, pd.Series(dtype=object))
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "benchmark_comparison",
                    "benchmark_id": benchmark_id,
                    "run_status": run_status,
                    "verdict": verdict,
                    "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                    "benchmark_balanced_drawdown_aware_score_v2": bench_row.get("balanced_drawdown_aware_score_v2", math.nan),
                    "score_delta_vs_benchmark": (
                        float(row.get("balanced_drawdown_aware_score_v2")) - float(bench_row.get("balanced_drawdown_aware_score_v2"))
                        if pd.notna(row.get("balanced_drawdown_aware_score_v2", math.nan)) and pd.notna(bench_row.get("balanced_drawdown_aware_score_v2", math.nan))
                        else math.nan
                    ),
                }
            )
        for horizon in [90, 180]:
            metric = rolling_subset[rolling_subset["horizon"].eq(horizon)]
            item = metric.iloc[0] if not metric.empty else pd.Series(dtype=object)
            worst = float(item.get("worst_max_drawdown", math.nan)) if pd.notna(item.get("worst_max_drawdown", math.nan)) else math.nan
            risk_rows.append(
                {
                    "experiment_id": exp_id,
                    "horizon": horizon,
                    "stop_hit_rate": item.get("p_any_project_stop_hit", math.nan),
                    "worst_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                    "stress_degradation": row.get("stress_degradation", math.nan),
                    "bil_cash_allocation_share": row.get("bil_fallback_allocation_share", math.nan),
                    "commodity_wrapper_allocation_share": row.get("commodity_wrapper_allocation_share", math.nan),
                    "combo_sleeve_allocation_share": row.get("component_combo_allocation_share", math.nan),
                    "max_product_or_sleeve_concentration": max(
                        [
                            float(pd.to_numeric(pd.Series([row.get("max_single_commodity_wrapper_allocation", math.nan)]), errors="coerce").fillna(0.0).iloc[0]),
                            float(pd.to_numeric(pd.Series([row.get("max_single_sleeve_allocation", math.nan)]), errors="coerce").fillna(0.0).iloc[0]),
                            float(pd.to_numeric(pd.Series([row.get("component_combo_allocation_share", math.nan)]), errors="coerce").fillna(0.0).iloc[0]),
                        ]
                    ),
                    "wrapper_warning": True,
                    "required_label": COMMODITY_EXPLORATORY_REQUIRED_LABEL,
                }
            )
        ranking_rows.append(
            {
                "rank_overall": row.get("rank_overall", math.nan),
                "rank_stop_aware_practical": row.get("rank_balanced_drawdown_aware_v2", math.nan),
                "rank_profit_seeking": row.get("rank_profit_seeking_score", math.nan),
                "rank_drawdown_control": row.get("rank_drawdown_control_score", math.nan),
                "experiment_id": exp_id,
                "verdict": verdict,
                "run_status": run_status,
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                "profit_seeking_score": row.get("profit_seeking_score", math.nan),
                "drawdown_control_score": row.get("drawdown_control_score", math.nan),
                "deserves_candidate_exhaustive": deserves,
                "notes": row.get("ranking_notes", ""),
            }
        )
        status_rows.append(
            {
                "experiment_id": exp_id,
                "status": "completed" if run_status == "completed" else "incomplete_evidence",
                "verdict": verdict,
                "candidate_exhaustive_recommended": deserves,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "reason": row.get("queue_reason", row.get("ranking_notes", "")),
            }
        )
        candidate_returns = curve_return_series(curves.get(exp_id, pd.DataFrame()))
        for benchmark_id in benchmark_ids:
            benchmark_returns = curve_return_series(curves.get(benchmark_id, pd.DataFrame()))
            common = pd.concat([candidate_returns, benchmark_returns], axis=1, join="inner").dropna()
            correlation = float(common.iloc[:, 0].corr(common.iloc[:, 1])) if len(common) > 2 else math.nan
            diagnostic_rows.append(
                {
                    "experiment_id": exp_id,
                    "benchmark_id": benchmark_id,
                    "correlation_status": "available" if pd.notna(correlation) else "unavailable",
                    "daily_equity_return_correlation": correlation,
                    "target_window_incremental_status": "unavailable_not_exported_for_this_batch",
                    "drawdown_coincidence_status": "available_via_equity_return_correlation_only" if pd.notna(correlation) else "unavailable",
                    "diversification_claim": "possible_only_not_proven",
                }
            )

    completed_rankings = [row for row in ranking_rows if str(row.get("run_status")) == "completed"]
    best = max(completed_rankings, key=lambda item: float(pd.to_numeric(pd.Series([item.get("balanced_drawdown_aware_score_v2")]), errors="coerce").fillna(-math.inf).iloc[0])) if completed_rankings else {}
    any_candidate_exhaustive = any(boolish(row.get("deserves_candidate_exhaustive", False)) for row in ranking_rows)
    risk_frame = pd.DataFrame(risk_rows)
    inside_budget = False
    horizon_column = "horizon_days" if "horizon_days" in risk_frame.columns else "horizon"
    if not risk_frame.empty and {"experiment_id", horizon_column, "worst_drawdown"}.issubset(risk_frame.columns):
        horizon_frame = risk_frame[pd.to_numeric(risk_frame[horizon_column], errors="coerce").isin([90, 180])]
        for _, candidate_frame in horizon_frame.groupby("experiment_id"):
            drawdowns = pd.to_numeric(candidate_frame["worst_drawdown"], errors="coerce")
            if not drawdowns.empty and bool((drawdowns >= -600.0).all()):
                inside_budget = True
                break
    summary = f"""# Commodity Risk-Control Batch 1 Summary

overall_decision: `{'candidate_exhaustive_review_required' if any_candidate_exhaustive else 'no_candidate_exhaustive_review'}`

base_commodity_verdict_correction: `research_sample_candidate_risk_budget_breach`

best_risk_control_candidate: `{best.get('experiment_id', 'unavailable')}`

1. Did any risk-control candidate reduce drawdown below the -$600 budget? `{str(inside_budget).lower()}`.
2. Did any retain enough +300/+400 target power? See `risk_control_batch1_results.csv`; target power is judged by 30/60/90/180 +300/+400 rates.
3. Did any improve stop-aware score versus base commodity? See benchmark comparison rows against `{COMMODITY_EXPLORATORY_EXPERIMENT_ID}`.
4. Did any beat combo or top2 on stop-aware profit/risk? See comparison rows against combo and top2.
5. Did combo_plus_commodity_80_20 add incremental value? See the `combo_plus_commodity_basket_80_20_v1` comparison rows.
6. Did any candidate become too slow? Rows with verdict `too_slow` indicate target dilution.
7. Did any candidate deserve candidate_exhaustive review? `{str(any_candidate_exhaustive).lower()}`.
8. No real-money recommendation.

All rows are fast exploratory commodity wrapper research_sample evidence only. The active combo paper/demo observation was not changed.
"""
    readme = """# README For Advisor

This is the compact Commodity Risk-Control Batch 1 research_sample packet.

It contains result summaries and diagnostics only. It excludes raw OHLCV, does not run candidate_exhaustive, does not activate paper-forward, does not use direct futures contracts, does not connect to brokers, and does not make a real-money recommendation.
"""
    warnings = f"""# Warnings And Limitations

- Research-only paper/demo evidence.
- Fast exploratory public ETF/fund wrapper data only.
- Required label: `{COMMODITY_EXPLORATORY_REQUIRED_LABEL}`.
- No new data download occurred in this risk-control batch.
- Commodity wrapper adjusted-price modeling is not direct futures strategy evidence.
- No futures contracts, futures roll logic, leverage, margin, shorting, broker integration, live orders, order placement, or real-money recommendation.
- Candidate_exhaustive was not run; any review recommendation would require a separate future prompt.
- Active combo paper-forward rules and SPY_200d rules were not changed.
"""
    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_recommended": any_candidate_exhaustive,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "direct_futures_contract_logic": False,
        "experiment_ids": batch_ids,
        "latest_folder_file_count": len(COMMODITY_RISK_CONTROL_REQUIRED_LATEST_FILES),
        "live_orders": False,
        "new_symbols_added": False,
        "order_placement": False,
        "paper_forward_active": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": True,
        "real_money_recommendation": False,
        "research_sample_run": True,
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": True,
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "base_commodity_verdict_correction": "research_sample_candidate_risk_budget_breach",
        "best_risk_control_candidate": best.get("experiment_id", ""),
    }
    return {
        "README_FOR_ADVISOR.md": readme,
        "risk_control_batch1_summary.md": summary,
        "risk_control_batch1_results.csv": pd.DataFrame(result_rows).to_csv(index=False),
        "risk_control_batch1_rankings.csv": pd.DataFrame(ranking_rows).to_csv(index=False),
        "risk_control_batch1_risk_summary.csv": pd.DataFrame(risk_rows).to_csv(index=False),
        "risk_control_batch1_diagnostics.csv": pd.DataFrame(diagnostic_rows).to_csv(index=False),
        "risk_control_batch1_status.csv": pd.DataFrame(status_rows).to_csv(index=False),
        "warnings_and_limitations.md": warnings,
        "risk_control_batch1_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "_manifest": manifest,
    }


def write_commodity_risk_control_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> tuple[Path, Path, Path]:
    outputs = build_commodity_risk_control_outputs(run_id, results, rolling, rankings, status, curves)
    run_dir = COMMODITY_RISK_CONTROL_OUTPUT_ROOT / "runs" / run_id
    latest_dir = COMMODITY_RISK_CONTROL_OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for name in COMMODITY_RISK_CONTROL_REQUIRED_LATEST_FILES:
        text = outputs[name]
        (run_dir / name).write_text(text, encoding="utf-8")
        (latest_dir / name).write_text(text, encoding="utf-8")
    files = sorted(path.name for path in latest_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(COMMODITY_RISK_CONTROL_REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Commodity risk-control evidence contract failed: {files}")
    zip_path = COMMODITY_RISK_CONTROL_OUTPUT_ROOT / "latest_risk_control_batch1_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir, zip_path


def build_global_multi_asset_batch1_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    batch_ids = GLOBAL_MULTI_ASSET_BATCH1_IDS
    benchmark_ids = [
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
        "BIL_cash_proxy",
        COMMODITY_EXPLORATORY_EXPERIMENT_ID,
        "combo_plus_commodity_basket_80_20_v1",
        "combo_plus_crypto_spot_tsmom_90_10_v1",
    ]
    rank_by_id = {str(row["experiment_id"]): row for _, row in rankings.iterrows()} if "experiment_id" in rankings else {}
    standard_rolling = rolling[rolling["standard_or_stress"].eq("standard")].copy() if "standard_or_stress" in rolling else pd.DataFrame()

    result_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for exp_id in batch_ids:
        row = rank_by_id.get(exp_id, pd.Series(dtype=object))
        run_status = str(row.get("run_status", "incomplete_evidence"))
        verdict = str(row.get("profit_verdict", "incomplete_evidence"))
        deserves = boolish(row.get("deserves_candidate_exhaustive", False))
        rolling_subset = standard_rolling[standard_rolling["experiment_id"].eq(exp_id)] if "experiment_id" in standard_rolling else pd.DataFrame()
        for _, metric in rolling_subset.sort_values("horizon").iterrows():
            worst = float(metric.get("worst_max_drawdown", math.nan)) if pd.notna(metric.get("worst_max_drawdown", math.nan)) else math.nan
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "candidate_horizon",
                    "horizon": int(metric.get("horizon", 0)),
                    "run_status": run_status,
                    "verdict": verdict,
                    "p_target_300_before_stop": metric.get("p_target_300_before_stop", math.nan),
                    "p_target_400_before_stop": metric.get("p_target_400_before_stop", math.nan),
                    "p_target_600_before_stop": metric.get("p_target_600_before_stop", math.nan),
                    "p_target_900_before_stop": metric.get("p_target_900_before_stop", math.nan),
                    "p_target_1200_before_stop": metric.get("p_target_1200_before_stop", math.nan),
                    "p_any_project_stop_hit": metric.get("p_any_project_stop_hit", math.nan),
                    "median_stop_enforced_final_equity": metric.get("median_stop_enforced_final_equity", math.nan),
                    "p95_stop_enforced_final_equity": metric.get("p95_stop_enforced_final_equity", math.nan),
                    "worst_max_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                }
            )
        for benchmark_id in benchmark_ids:
            bench_row = rank_by_id.get(benchmark_id, pd.Series(dtype=object))
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "benchmark_comparison",
                    "benchmark_id": benchmark_id,
                    "run_status": run_status,
                    "verdict": verdict,
                    "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                    "benchmark_balanced_drawdown_aware_score_v2": bench_row.get("balanced_drawdown_aware_score_v2", math.nan),
                    "score_delta_vs_benchmark": (
                        float(row.get("balanced_drawdown_aware_score_v2")) - float(bench_row.get("balanced_drawdown_aware_score_v2"))
                        if pd.notna(row.get("balanced_drawdown_aware_score_v2", math.nan)) and pd.notna(bench_row.get("balanced_drawdown_aware_score_v2", math.nan))
                        else math.nan
                    ),
                }
            )
        for horizon in [90, 180]:
            metric = rolling_subset[rolling_subset["horizon"].eq(horizon)]
            item = metric.iloc[0] if not metric.empty else pd.Series(dtype=object)
            worst = float(item.get("worst_max_drawdown", math.nan)) if pd.notna(item.get("worst_max_drawdown", math.nan)) else math.nan
            risk_rows.append(
                {
                    "experiment_id": exp_id,
                    "horizon": horizon,
                    "stop_hit_rate": item.get("p_any_project_stop_hit", math.nan),
                    "worst_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                    "stress_degradation": row.get("stress_degradation", math.nan),
                    "bil_cash_allocation_share": row.get("global_bil_allocation_share", math.nan),
                    "global_equity_allocation_share": row.get("global_equity_allocation_share", math.nan),
                    "global_duration_allocation_share": row.get("global_duration_allocation_share", math.nan),
                    "global_real_asset_allocation_share": row.get("global_real_asset_allocation_share", math.nan),
                    "combo_sleeve_allocation_share": row.get("component_combo_allocation_share", math.nan),
                    "max_asset_or_sleeve_concentration": max(
                        [
                            float(pd.to_numeric(pd.Series([row.get("max_single_global_asset_allocation", math.nan)]), errors="coerce").fillna(0.0).iloc[0]),
                            float(pd.to_numeric(pd.Series([row.get("component_combo_allocation_share", math.nan)]), errors="coerce").fillna(0.0).iloc[0]),
                        ]
                    ),
                    "wrapper_warning": True,
                    "required_label": GLOBAL_MULTI_ASSET_REQUIRED_LABEL,
                }
            )
        ranking_rows.append(
            {
                "rank_overall": row.get("rank_overall", math.nan),
                "rank_stop_aware_practical": row.get("rank_balanced_drawdown_aware_v2", math.nan),
                "rank_profit_seeking": row.get("rank_profit_seeking_score", math.nan),
                "rank_drawdown_control": row.get("rank_drawdown_control_score", math.nan),
                "experiment_id": exp_id,
                "verdict": verdict,
                "run_status": run_status,
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                "profit_seeking_score": row.get("profit_seeking_score", math.nan),
                "drawdown_control_score": row.get("drawdown_control_score", math.nan),
                "deserves_candidate_exhaustive": deserves,
                "notes": row.get("ranking_notes", ""),
            }
        )
        status_rows.append(
            {
                "experiment_id": exp_id,
                "status": "completed" if run_status == "completed" else "incomplete_evidence",
                "verdict": verdict,
                "candidate_exhaustive_recommended": deserves,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "reason": row.get("queue_reason", row.get("ranking_notes", "")),
            }
        )
        candidate_returns = curve_return_series(curves.get(exp_id, pd.DataFrame()))
        for benchmark_id in benchmark_ids:
            benchmark_returns = curve_return_series(curves.get(benchmark_id, pd.DataFrame()))
            common = pd.concat([candidate_returns, benchmark_returns], axis=1, join="inner").dropna()
            correlation = float(common.iloc[:, 0].corr(common.iloc[:, 1])) if len(common) > 2 else math.nan
            diagnostic_rows.append(
                {
                    "experiment_id": exp_id,
                    "benchmark_id": benchmark_id,
                    "correlation_status": "available" if pd.notna(correlation) else "unavailable",
                    "daily_equity_return_correlation": correlation,
                    "target_window_incremental_status": "not_separately_exported_for_this_fast_batch",
                    "drawdown_coincidence_status": "available_via_equity_return_correlation_only" if pd.notna(correlation) else "unavailable",
                    "diversification_claim": "possible_only_not_proven",
                }
            )

    completed_rankings = [row for row in ranking_rows if str(row.get("run_status")) == "completed"]
    best = max(completed_rankings, key=lambda item: float(pd.to_numeric(pd.Series([item.get("balanced_drawdown_aware_score_v2")]), errors="coerce").fillna(-math.inf).iloc[0])) if completed_rankings else {}
    any_candidate_exhaustive = any(boolish(row.get("deserves_candidate_exhaustive", False)) for row in ranking_rows)
    risk_frame = pd.DataFrame(risk_rows)
    inside_budget = False
    if not risk_frame.empty and {"experiment_id", "horizon", "worst_drawdown"}.issubset(risk_frame.columns):
        horizon_frame = risk_frame[pd.to_numeric(risk_frame["horizon"], errors="coerce").isin([90, 180])]
        for _, candidate_frame in horizon_frame.groupby("experiment_id"):
            drawdowns = pd.to_numeric(candidate_frame["worst_drawdown"], errors="coerce")
            if not drawdowns.empty and bool((drawdowns >= -600.0).all()):
                inside_budget = True
                break
    summary = f"""# Global Multi-Asset ETF Fast Exploration Batch 1 Summary

overall_decision: `{'candidate_exhaustive_review_required' if any_candidate_exhaustive else 'no_candidate_exhaustive_review'}`

best_multi_asset_candidate: `{best.get('experiment_id', 'unavailable')}`

1. Did the broad multi-asset universe improve +300/+400 target rates? See `fast_exploration_batch1_results.csv`.
2. Did it remain within or near the -$600 risk budget? `{str(inside_budget).lower()}`.
3. Did it beat combo on stop-aware score? See benchmark comparison rows against `combo_SPY200d_GLD_50_50_v1`.
4. Did it beat top2, SPY_200d, or GLD? See benchmark comparison rows.
5. Did the defensive 50% BIL version become too slow? See `fast_exploration_batch1_status.csv`.
6. Did combo+global multi-asset 80/20 add incremental value? See comparison rows for `combo_plus_global_multi_asset_80_20_v1`.
7. Did any row mostly duplicate existing leaders? Correlation/co-movement diagnostics are preliminary only in `fast_exploration_batch1_diagnostics.csv`.
8. Did any row deserve candidate_exhaustive review? `{str(any_candidate_exhaustive).lower()}`.
9. No real-money recommendation.

All rows are fast exploratory ETF/fund-wrapper research_sample evidence only. The active combo paper/demo observation was not changed.
"""
    readme = """# README For Advisor

This is the compact Global Multi-Asset ETF Fast Exploration Batch 1 research_sample packet.

It contains result summaries and diagnostics only. It excludes raw OHLCV, does not run candidate_exhaustive, does not activate paper-forward, does not use leverage, margin, shorting, futures contracts, options, forex, intraday logic, brokers, live orders, or real-money recommendations.
"""
    warnings = f"""# Warnings And Limitations

- Research-only paper/demo evidence.
- Fast exploratory public ETF/fund wrapper data only.
- Required label: `{GLOBAL_MULTI_ASSET_REQUIRED_LABEL}`.
- Profit Exploration used cached approved ETF/fund symbols only.
- International ETF, emerging-market ETF, duration, gold, and commodity wrapper risks remain product-specific.
- Commodity wrapper adjusted-price modeling is not direct futures strategy evidence.
- No futures contracts, futures roll logic, leverage, margin, shorting, options, forex, intraday logic, broker integration, live orders, order placement, or real-money recommendation.
- Candidate_exhaustive was not run; any review recommendation would require a separate future prompt.
- Active combo paper-forward rules and SPY_200d rules were not changed.
"""
    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_recommended": any_candidate_exhaustive,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "direct_futures_contract_logic": False,
        "experiment_ids": batch_ids,
        "latest_folder_file_count": len(GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_LATEST_FILES),
        "live_orders": False,
        "order_placement": False,
        "paper_forward_active": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": True,
        "real_money_recommendation": False,
        "research_sample_run": True,
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": True,
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "uses_futures_contracts": False,
        "uses_options": False,
        "uses_forex": False,
        "uses_intraday": False,
        "best_multi_asset_candidate": best.get("experiment_id", ""),
        "approved_symbols": [*GLOBAL_MULTI_ASSET_SYMBOLS, "BIL"],
    }
    return {
        "README_FOR_ADVISOR.md": readme,
        "fast_exploration_batch1_summary.md": summary,
        "fast_exploration_batch1_results.csv": pd.DataFrame(result_rows).to_csv(index=False),
        "fast_exploration_batch1_rankings.csv": pd.DataFrame(ranking_rows).to_csv(index=False),
        "fast_exploration_batch1_risk_summary.csv": pd.DataFrame(risk_rows).to_csv(index=False),
        "fast_exploration_batch1_diagnostics.csv": pd.DataFrame(diagnostic_rows).to_csv(index=False),
        "fast_exploration_batch1_status.csv": pd.DataFrame(status_rows).to_csv(index=False),
        "warnings_and_limitations.md": warnings,
        "fast_exploration_batch1_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "_manifest": manifest,
    }


def write_global_multi_asset_batch1_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> tuple[Path, Path, Path]:
    outputs = build_global_multi_asset_batch1_outputs(run_id, results, rolling, rankings, status, curves)
    run_dir = GLOBAL_MULTI_ASSET_BATCH1_OUTPUT_ROOT / "runs" / run_id
    latest_dir = GLOBAL_MULTI_ASSET_BATCH1_OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for name in GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_LATEST_FILES:
        text = outputs[name]
        (run_dir / name).write_text(text, encoding="utf-8")
        (latest_dir / name).write_text(text, encoding="utf-8")
    files = sorted(path.name for path in latest_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(GLOBAL_MULTI_ASSET_BATCH1_REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Global multi-asset evidence contract failed: {files}")
    zip_path = GLOBAL_MULTI_ASSET_BATCH1_OUTPUT_ROOT / "latest_fast_exploration_batch1_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir, zip_path


def build_crypto_tier2_risk_control_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    batch_ids = CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS
    benchmark_ids = [
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
        "BIL_cash_proxy",
        "crypto_buy_hold_equal_weight",
        "crypto_time_series_momentum",
    ]
    rank_by_id = {str(row["experiment_id"]): row for _, row in rankings.iterrows()} if "experiment_id" in rankings else {}
    standard_rolling = rolling[rolling["standard_or_stress"].eq("standard")].copy() if "standard_or_stress" in rolling else pd.DataFrame()

    def numeric(value: Any, default: float = math.nan) -> float:
        parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return default if pd.isna(parsed) else float(parsed)

    result_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for exp_id in batch_ids:
        row = rank_by_id.get(exp_id, pd.Series(dtype=object))
        run_status = str(row.get("run_status", "incomplete_evidence"))
        verdict = str(row.get("profit_verdict", "incomplete_evidence"))
        deserves = boolish(row.get("deserves_candidate_exhaustive", False))
        rolling_subset = standard_rolling[standard_rolling["experiment_id"].eq(exp_id)] if "experiment_id" in standard_rolling else pd.DataFrame()
        for _, metric in rolling_subset.sort_values("horizon").iterrows():
            worst = numeric(metric.get("worst_max_drawdown", math.nan))
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "candidate_horizon",
                    "horizon": int(metric.get("horizon", 0)),
                    "run_status": run_status,
                    "verdict": verdict,
                    "p_target_300_before_stop": metric.get("p_target_300_before_stop", math.nan),
                    "p_target_400_before_stop": metric.get("p_target_400_before_stop", math.nan),
                    "p_target_600_before_stop": metric.get("p_target_600_before_stop", math.nan),
                    "p_target_900_before_stop": metric.get("p_target_900_before_stop", math.nan),
                    "p_target_1200_before_stop": metric.get("p_target_1200_before_stop", math.nan),
                    "p_any_project_stop_hit": metric.get("p_any_project_stop_hit", math.nan),
                    "median_stop_enforced_final_equity": metric.get("median_stop_enforced_final_equity", math.nan),
                    "p95_stop_enforced_final_equity": metric.get("p95_stop_enforced_final_equity", math.nan),
                    "worst_max_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                }
            )
        for benchmark_id in benchmark_ids:
            bench_row = rank_by_id.get(benchmark_id, pd.Series(dtype=object))
            candidate_score = numeric(row.get("balanced_drawdown_aware_score_v2", math.nan))
            benchmark_score = numeric(bench_row.get("balanced_drawdown_aware_score_v2", math.nan))
            result_rows.append(
                {
                    "experiment_id": exp_id,
                    "row_type": "benchmark_comparison",
                    "benchmark_id": benchmark_id,
                    "run_status": run_status,
                    "verdict": verdict,
                    "balanced_drawdown_aware_score_v2": candidate_score,
                    "benchmark_balanced_drawdown_aware_score_v2": benchmark_score,
                    "score_delta_vs_benchmark": candidate_score - benchmark_score if pd.notna(candidate_score) and pd.notna(benchmark_score) else math.nan,
                }
            )
        for horizon in [90, 180]:
            metric = rolling_subset[rolling_subset["horizon"].eq(horizon)]
            item = metric.iloc[0] if not metric.empty else pd.Series(dtype=object)
            worst = numeric(item.get("worst_max_drawdown", math.nan))
            risk_rows.append(
                {
                    "experiment_id": exp_id,
                    "horizon": horizon,
                    "stop_hit_rate": item.get("p_any_project_stop_hit", math.nan),
                    "worst_drawdown": worst,
                    "risk_budget_usage": abs(min(0.0, worst)) / TRAILING_DRAWDOWN if pd.notna(worst) else math.nan,
                    "stress_degradation": row.get("stress_degradation", math.nan),
                    "bil_cash_allocation_share": row.get("bil_cash_allocation_share", math.nan),
                    "crypto_spot_allocation_share": row.get("crypto_spot_allocation_share", math.nan),
                    "max_crypto_exposure": row.get("max_crypto_exposure", math.nan),
                    "btc_allocation_share": row.get("btc_allocation_share", math.nan),
                    "eth_allocation_share": row.get("eth_allocation_share", math.nan),
                    "component_combo_allocation_share": row.get("component_combo_allocation_share", math.nan),
                    "crypto_warning": True,
                    "required_label": CRYPTO_TIER2_REQUIRED_LABEL,
                }
            )
        ranking_rows.append(
            {
                "rank_overall": row.get("rank_overall", math.nan),
                "rank_stop_aware_practical": row.get("rank_balanced_drawdown_aware_v2", math.nan),
                "rank_profit_seeking": row.get("rank_profit_seeking_score", math.nan),
                "rank_drawdown_control": row.get("rank_drawdown_control_score", math.nan),
                "experiment_id": exp_id,
                "verdict": verdict,
                "run_status": run_status,
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", math.nan),
                "profit_seeking_score": row.get("profit_seeking_score", math.nan),
                "drawdown_control_score": row.get("drawdown_control_score", math.nan),
                "deserves_candidate_exhaustive": deserves,
                "notes": row.get("ranking_notes", ""),
            }
        )
        status_rows.append(
            {
                "experiment_id": exp_id,
                "status": "completed" if run_status == "completed" else "incomplete_evidence",
                "verdict": verdict,
                "candidate_exhaustive_recommended": deserves,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "reason": row.get("queue_reason", row.get("ranking_notes", "")),
            }
        )
        candidate_returns = curve_return_series(curves.get(exp_id, pd.DataFrame()))
        for benchmark_id in benchmark_ids:
            benchmark_returns = curve_return_series(curves.get(benchmark_id, pd.DataFrame()))
            common = pd.concat([candidate_returns, benchmark_returns], axis=1, join="inner").dropna()
            correlation = float(common.iloc[:, 0].corr(common.iloc[:, 1])) if len(common) > 2 else math.nan
            diagnostic_rows.append(
                {
                    "experiment_id": exp_id,
                    "benchmark_id": benchmark_id,
                    "correlation_status": "available" if pd.notna(correlation) else "unavailable",
                    "daily_equity_return_correlation": correlation,
                    "target_window_incremental_status": "unavailable_not_exported_for_this_batch",
                    "drawdown_coincidence_status": "available_via_equity_return_correlation_only" if pd.notna(correlation) else "unavailable",
                    "diversification_claim": "possible_only_not_proven",
                }
            )

    completed_rankings = [row for row in ranking_rows if str(row.get("run_status")) == "completed"]
    best = max(completed_rankings, key=lambda item: numeric(item.get("balanced_drawdown_aware_score_v2"), -math.inf)) if completed_rankings else {}
    any_candidate_exhaustive = any(boolish(row.get("deserves_candidate_exhaustive", False)) for row in ranking_rows)
    risk_frame = pd.DataFrame(risk_rows)
    inside_or_near_budget = False
    if not risk_frame.empty and {"experiment_id", "horizon", "worst_drawdown"}.issubset(risk_frame.columns):
        horizon_frame = risk_frame[pd.to_numeric(risk_frame["horizon"], errors="coerce").isin([90, 180])]
        for _, candidate_frame in horizon_frame.groupby("experiment_id"):
            drawdowns = pd.to_numeric(candidate_frame["worst_drawdown"], errors="coerce")
            if not drawdowns.empty and bool((drawdowns >= -660.0).all()):
                inside_or_near_budget = True
                break
    summary = f"""# Crypto Spot Tier 2 Risk-Control Batch 1 Summary

overall_decision: `{'candidate_exhaustive_review_required' if any_candidate_exhaustive else 'no_candidate_exhaustive_review'}`

best_risk_control_candidate: `{best.get('experiment_id', 'unavailable')}`

1. Did any crypto risk-control candidate reduce stop risk below prior crypto exploratory rows? `review_against_prior_crypto_rows_unavailable_in_this_packet`; see current stop-hit and drawdown rows for batch results.
2. Did any stay inside or near the -$600 risk budget? `{str(inside_or_near_budget).lower()}`.
3. Did any retain meaningful +300/+400 target power? See `tier2_risk_control_batch1_results.csv`.
4. Did any improve stop-aware score versus combo/top2/SPY_200d/GLD? See benchmark comparison rows in `tier2_risk_control_batch1_results.csv`.
5. Did combo_plus_crypto_90_10 add incremental target value? Co-movement is not separately exported in this batch; score and correlation diagnostics are provided.
6. Did any become too risky or too slow? See `tier2_risk_control_batch1_status.csv`.
7. Did any candidate deserve future candidate_exhaustive review? `{str(any_candidate_exhaustive).lower()}`.
8. No real-money recommendation.

All rows are crypto spot Tier 2 exploratory research_sample evidence only. The active combo paper/demo observation was not changed.
"""
    readme = """# README For Advisor

This is the compact Crypto Spot Tier 2 Risk-Control Batch 1 research_sample packet.

It contains result summaries and diagnostics only. It excludes raw OHLCV, does not run candidate_exhaustive, does not activate paper-forward, does not use leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or order placement, and does not make a real-money recommendation.
"""
    warnings = f"""# Warnings And Limitations

- Research-only paper/demo evidence.
- Crypto spot Tier 2 exploratory public/cached data only.
- Required label: `{CRYPTO_TIER2_REQUIRED_LABEL}`.
- BTC/ETH only for this first fixed risk-control batch.
- No new data download occurred in Profit Exploration.
- Crypto daily data trades 24/7; this run aligns crypto spot prices to the ETF/BIL trading-day matrix for the cash fallback comparison.
- No leverage, margin, shorting, futures, perpetuals, options, exchange execution, broker integration, live orders, order placement, or real-money recommendation.
- Candidate_exhaustive was not run; any review recommendation would require a separate future prompt.
- Active combo paper-forward rules and SPY_200d rules were not changed.
"""
    manifest = {
        "active_combo_rule_changed": False,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_recommended": any_candidate_exhaustive,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "direct_futures_contract_logic": False,
        "experiment_ids": batch_ids,
        "latest_folder_file_count": len(CRYPTO_TIER2_RISK_CONTROL_REQUIRED_LATEST_FILES),
        "live_orders": False,
        "new_symbols_added": [],
        "order_placement": False,
        "paper_forward_active": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": True,
        "real_money_recommendation": False,
        "research_sample_run": True,
        "run_id": run_id,
        "spy200d_replaced": False,
        "symbols_used": ["BTC-USD", "ETH-USD", "BIL"],
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "uses_futures_contracts": False,
        "uses_perpetuals": False,
        "uses_options": False,
        "exchange_execution": False,
        "best_risk_control_candidate": best.get("experiment_id", ""),
    }
    return {
        "README_FOR_ADVISOR.md": readme,
        "tier2_risk_control_batch1_summary.md": summary,
        "tier2_risk_control_batch1_results.csv": pd.DataFrame(result_rows).to_csv(index=False),
        "tier2_risk_control_batch1_rankings.csv": pd.DataFrame(ranking_rows).to_csv(index=False),
        "tier2_risk_control_batch1_risk_summary.csv": pd.DataFrame(risk_rows).to_csv(index=False),
        "tier2_risk_control_batch1_diagnostics.csv": pd.DataFrame(diagnostic_rows).to_csv(index=False),
        "tier2_risk_control_batch1_status.csv": pd.DataFrame(status_rows).to_csv(index=False),
        "warnings_and_limitations.md": warnings,
        "tier2_risk_control_batch1_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "_manifest": manifest,
    }


def write_crypto_tier2_risk_control_outputs(
    run_id: str,
    results: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    status: pd.DataFrame,
    curves: dict[str, pd.DataFrame],
) -> tuple[Path, Path, Path]:
    outputs = build_crypto_tier2_risk_control_outputs(run_id, results, rolling, rankings, status, curves)
    run_dir = CRYPTO_TIER2_RISK_CONTROL_OUTPUT_ROOT / "runs" / run_id
    latest_dir = CRYPTO_TIER2_RISK_CONTROL_OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for name in CRYPTO_TIER2_RISK_CONTROL_REQUIRED_LATEST_FILES:
        text = outputs[name]
        (run_dir / name).write_text(text, encoding="utf-8")
        (latest_dir / name).write_text(text, encoding="utf-8")
    files = sorted(path.name for path in latest_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(CRYPTO_TIER2_RISK_CONTROL_REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Crypto Tier 2 risk-control evidence contract failed: {files}")
    zip_path = CRYPTO_TIER2_RISK_CONTROL_OUTPUT_ROOT / "latest_tier2_risk_control_batch1_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir, zip_path


def write_outputs(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    results, rolling, rankings, status, curves, context = run_experiments(args)
    run_id = context["run_id"]
    run_dir = OUTPUT_ROOT / "runs" / run_id
    latest_dir = OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "README_FOR_ADVISOR.md").write_text(
        "# README For Advisor\n\nThis is a compact research-only profit exploration packet. It contains no real-money recommendation, no broker integration, no live orders, and no raw OHLCV.\n",
        encoding="utf-8",
    )
    (run_dir / "profit_exploration_summary.md").write_text(build_summary(results, rolling, rankings, status, run_id, args), encoding="utf-8")
    results.to_csv(run_dir / "profit_exploration_results.csv", index=False)
    rolling.to_csv(run_dir / "rolling_profit_distribution.csv", index=False)
    rankings.to_csv(run_dir / "profit_rankings.csv", index=False)
    risk_summary(results).to_csv(run_dir / "risk_and_stop_summary.csv", index=False)
    status.to_csv(run_dir / "experiment_status.csv", index=False)
    (run_dir / "assumptions_and_costs.yaml").write_text(yaml.safe_dump(build_assumptions(args), sort_keys=False), encoding="utf-8")
    warnings = build_warnings_text()
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")
    write_chart(run_dir / "profit_charts.png", curves, rankings)

    files = sorted(path.name for path in run_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(REQUIRED_LATEST_FILES) or len(files) > 10:
        raise RuntimeError(f"Profit exploration evidence contract failed: {files}")
    shutil.copytree(run_dir, latest_dir)
    zip_path = OUTPUT_ROOT / "latest_profit_exploration_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    combination_context: dict[str, Any] = {}
    if bool(getattr(args, "include_combination_batch1", False)):
        combo_run_dir, combo_latest_dir, combo_zip_path = write_combination_batch1_outputs(run_id, results, rolling, rankings, status, curves)
        combination_context = {
            "combination_run_dir": combo_run_dir,
            "combination_latest_dir": combo_latest_dir,
            "combination_zip_path": combo_zip_path,
        }
    commodity_context: dict[str, Any] = {}
    if bool(getattr(args, "include_commodity_basket_exploratory", False)):
        commodity_run_dir, commodity_latest_dir, commodity_zip_path = write_commodity_exploratory_outputs(run_id, results, rolling, rankings, status)
        commodity_context = {
            "commodity_exploratory_run_dir": commodity_run_dir,
            "commodity_exploratory_latest_dir": commodity_latest_dir,
            "commodity_exploratory_zip_path": commodity_zip_path,
        }
    commodity_risk_context: dict[str, Any] = {}
    if bool(getattr(args, "include_commodity_risk_control_batch1", False)):
        risk_run_dir, risk_latest_dir, risk_zip_path = write_commodity_risk_control_outputs(run_id, results, rolling, rankings, status, curves)
        commodity_risk_context = {
            "commodity_risk_control_run_dir": risk_run_dir,
            "commodity_risk_control_latest_dir": risk_latest_dir,
            "commodity_risk_control_zip_path": risk_zip_path,
        }
    crypto_tier2_context: dict[str, Any] = {}
    if bool(getattr(args, "include_crypto_tier2_risk_control_batch1", False)):
        crypto_run_dir, crypto_latest_dir, crypto_zip_path = write_crypto_tier2_risk_control_outputs(run_id, results, rolling, rankings, status, curves)
        crypto_tier2_context = {
            "crypto_tier2_risk_control_run_dir": crypto_run_dir,
            "crypto_tier2_risk_control_latest_dir": crypto_latest_dir,
            "crypto_tier2_risk_control_zip_path": crypto_zip_path,
        }
    global_multi_asset_context: dict[str, Any] = {}
    if bool(getattr(args, "include_global_multi_asset_batch1", False)):
        global_run_dir, global_latest_dir, global_zip_path = write_global_multi_asset_batch1_outputs(run_id, results, rolling, rankings, status, curves)
        global_multi_asset_context = {
            "global_multi_asset_batch1_run_dir": global_run_dir,
            "global_multi_asset_batch1_latest_dir": global_latest_dir,
            "global_multi_asset_batch1_zip_path": global_zip_path,
        }
    return run_dir, latest_dir, {
        "run_id": run_id,
        "results": results,
        "rankings": rankings,
        **combination_context,
        **commodity_context,
        **commodity_risk_context,
        **crypto_tier2_context,
        **global_multi_asset_context,
    }


def args_from_latest_evidence(args: argparse.Namespace, results: pd.DataFrame, rankings: pd.DataFrame, rolling: pd.DataFrame) -> argparse.Namespace:
    selected_horizons = getattr(args, "horizons", None)
    if not selected_horizons and "selected_horizons" in results and not results.empty:
        selected_horizons = str(results["selected_horizons"].dropna().iloc[0])
    finalists = getattr(args, "finalists", None) or ",".join(rankings["experiment_id"].astype(str).tolist())
    run_scope = str(results["run_validation_scope"].dropna().iloc[0]) if "run_validation_scope" in results and not results.empty else ""
    all_possible = bool(rolling["rolling_method"].astype(str).eq("all_possible").all()) if "rolling_method" in rolling and not rolling.empty else False
    mode = "candidate_exhaustive" if run_scope.startswith("finalist_") or all_possible else getattr(args, "mode", "research_sample")
    return argparse.Namespace(
        mode=mode,
        include_crypto_exploratory=getattr(args, "include_crypto_exploratory", False),
        include_fixed_combinations=getattr(args, "include_fixed_combinations", True),
        include_combination_batch1=getattr(args, "include_combination_batch1", False),
        include_commodity_basket_exploratory=getattr(args, "include_commodity_basket_exploratory", False),
        include_commodity_risk_control_batch1=getattr(args, "include_commodity_risk_control_batch1", False),
        include_crypto_tier2_risk_control_batch1=getattr(args, "include_crypto_tier2_risk_control_batch1", False),
        include_global_multi_asset_batch1=getattr(args, "include_global_multi_asset_batch1", False),
        include_blocked=getattr(args, "include_blocked", True),
        include_incomplete=getattr(args, "include_incomplete", True),
        no_network=getattr(args, "no_network", True),
        reuse_cache=getattr(args, "reuse_cache", True),
        reuse_latest=True,
        score_only=True,
        max_runtime_minutes=getattr(args, "max_runtime_minutes", 60),
        finalists=finalists,
        horizons=selected_horizons,
    )


def rebuild_latest_profit_zip(latest_dir: Path) -> Path:
    zip_path = OUTPUT_ROOT / "latest_profit_exploration_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return zip_path


def write_score_only_outputs(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    latest_dir = OUTPUT_ROOT / "latest"
    if not latest_dir.exists():
        raise SystemExit("score-only requires evidence/profit_exploration/latest to exist")
    results_path = latest_dir / "profit_exploration_results.csv"
    rolling_path = latest_dir / "rolling_profit_distribution.csv"
    status_path = latest_dir / "experiment_status.csv"
    if not results_path.exists() or not rolling_path.exists() or not status_path.exists():
        raise SystemExit("score-only requires latest profit results, rolling distribution, and experiment status CSVs")
    results = pd.read_csv(results_path)
    rolling = pd.read_csv(rolling_path)
    status = pd.read_csv(status_path)
    previous_rankings_path = latest_dir / "profit_rankings.csv"
    previous_rankings = pd.read_csv(previous_rankings_path) if previous_rankings_path.exists() else pd.DataFrame()
    ordered_ids = previous_rankings["experiment_id"].astype(str).tolist() if "experiment_id" in previous_rankings else results["experiment_id"].astype(str).drop_duplicates().tolist()
    spec_by_id = {spec["experiment_id"]: spec for spec in load_specs()}
    specs = [spec_by_id[exp_id] for exp_id in ordered_ids if exp_id in spec_by_id]
    if not specs:
        raise SystemExit("score-only could not resolve experiment specs for latest rankings")
    pre_score_args = args_from_latest_evidence(args, results, previous_rankings if not previous_rankings.empty else pd.DataFrame({"experiment_id": ordered_ids}), rolling)
    selected_horizons = selected_horizons_for_args(pre_score_args)
    omitted_horizons = [horizon for horizon in HORIZONS if horizon not in selected_horizons]
    reduced = bool(omitted_horizons)
    finalist_ids = parse_finalist_ids(getattr(pre_score_args, "finalists", None)) or ordered_ids
    exact_rows = rolling[
        rolling.get("experiment_id", pd.Series(dtype=str)).astype(str).isin(finalist_ids)
        & rolling.get("rolling_method", pd.Series(dtype=str)).astype(str).eq("all_possible")
        & rolling.get("evidence_finality", pd.Series(dtype=str)).astype(str).isin(["exact_all_possible", "exact_selected_horizons"])
    ] if not rolling.empty else pd.DataFrame()
    required_pairs = {(exp_id, horizon, label) for exp_id in finalist_ids for horizon in selected_horizons for label in LABEL_COSTS}
    observed_pairs = {
        (str(row["experiment_id"]), int(row["horizon"]), str(row["standard_or_stress"]))
        for _, row in exact_rows.iterrows()
    }
    selected_complete = bool(required_pairs) and required_pairs.issubset(observed_pairs)
    candidate_complete = bool(getattr(pre_score_args, "mode", "") == "candidate_exhaustive" and not reduced and selected_complete)
    for frame in (results, rolling, status):
        if "candidate_exhaustive_completed" not in frame.columns:
            frame["candidate_exhaustive_completed"] = candidate_complete
        else:
            frame["candidate_exhaustive_completed"] = frame["candidate_exhaustive_completed"].fillna(candidate_complete)
    if "run_status" in results:
        completed_mask = results["run_status"].astype(str).eq("completed")
        results.loc[completed_mask, "candidate_exhaustive_completed"] = candidate_complete
    if "run_status" in status:
        completed_mask = status["run_status"].astype(str).eq("completed")
        status.loc[completed_mask, "candidate_exhaustive_completed"] = candidate_complete
    if not rolling.empty:
        rolling["candidate_exhaustive_completed"] = candidate_complete
    results = results.reindex(columns=RESULT_COLUMNS)
    rolling = rolling.reindex(columns=ROLLING_COLUMNS)
    rankings = build_rankings(results, rolling, specs)
    score_args = args_from_latest_evidence(args, results, rankings, rolling)
    run_id = str(results["run_id"].dropna().iloc[0]) if "run_id" in results and not results.empty else utc_run_id()
    summary = build_summary(results, rolling, rankings, status, run_id, score_args)
    assumptions = yaml.safe_dump(build_assumptions(score_args), sort_keys=False)
    warnings = build_warnings_text()
    updates = {
        "profit_exploration_results.csv": results.to_csv(index=False),
        "rolling_profit_distribution.csv": rolling.to_csv(index=False),
        "risk_and_stop_summary.csv": risk_summary(results).to_csv(index=False),
        "experiment_status.csv": status.to_csv(index=False),
        "profit_rankings.csv": rankings.to_csv(index=False),
        "profit_exploration_summary.md": summary,
        "assumptions_and_costs.yaml": assumptions,
        "warnings_and_limitations.md": warnings,
    }
    output_dirs = [latest_dir]
    run_dir = OUTPUT_ROOT / "runs" / run_id
    if run_dir.exists():
        output_dirs.append(run_dir)
    for output_dir in output_dirs:
        for name, text in updates.items():
            (output_dir / name).write_text(text, encoding="utf-8")
    files = [path.name for path in latest_dir.iterdir() if path.is_file()]
    if len(files) > 10:
        raise RuntimeError(f"Profit exploration latest folder exceeded 10 files: {files}")
    zip_path = rebuild_latest_profit_zip(latest_dir)
    return latest_dir, {"run_id": run_id, "rankings": rankings, "zip_path": zip_path}


def write_chart(path: Path, curves: dict[str, pd.DataFrame], rankings: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 7))
    top_ids = rankings.sort_values("rank_overall").head(6)["experiment_id"].astype(str).tolist() if not rankings.empty else list(curves)[:6]
    for exp_id in top_ids:
        curve = curves.get(exp_id)
        if curve is None or curve.empty:
            continue
        plt.plot(pd.to_datetime(curve["date"]), curve["equity"], label=exp_id)
    for value, label in [(3300, "+300"), (3400, "+400"), (3600, "+600"), (2400, "stop")]:
        plt.axhline(value, linestyle="--", linewidth=0.8, label=label)
    plt.title("Profit Exploration Equity Curves")
    plt.ylabel("Equity ($)")
    plt.xlabel("Date")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research-only profit exploration league.")
    parser.add_argument("--mode", choices=["smoke", "research_sample", "candidate_exhaustive", "final_audit"], default="research_sample")
    parser.add_argument("--include-crypto-exploratory", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-fixed-combinations", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-combination-batch1", action="store_true", default=False, help="Include exactly the three predeclared Historical Combination Research Sample Batch 1 rows.")
    parser.add_argument("--include-commodity-basket-exploratory", action="store_true", default=False, help="Include exactly one fast exploratory commodity wrapper top-2 research_sample row.")
    parser.add_argument("--include-commodity-risk-control-batch1", action="store_true", default=False, help="Include exactly three fixed Commodity Risk-Control Batch 1 research_sample rows.")
    parser.add_argument("--include-crypto-tier2-risk-control-batch1", action="store_true", default=False, help="Include exactly three fixed Crypto Spot Tier 2 Risk-Control Batch 1 research_sample rows.")
    parser.add_argument("--include-global-multi-asset-batch1", action="store_true", default=False, help="Include exactly three fixed Global Multi-Asset ETF Fast Exploration Batch 1 research_sample rows.")
    parser.add_argument("--include-blocked", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-incomplete", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-network", action="store_true", default=True)
    parser.add_argument("--reuse-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--score-only", action="store_true", default=False, help="Rebuild scoring/reporting outputs from evidence/profit_exploration/latest without rerunning experiments.")
    parser.add_argument("--diagnostics-only", action="store_true", default=False, help="Export Batch 1 diagnostic detail only; does not rewrite profit_exploration/latest.")
    parser.add_argument("--export-attribution-diagnostics", action="store_true", default=False, help="With --diagnostics-only, export reusable attribution diagnostics detail.")
    parser.add_argument("--reuse-latest", action="store_true", default=False, help="Required with --score-only to use existing latest evidence.")
    parser.add_argument("--max-runtime-minutes", type=int, default=60)
    parser.add_argument(
        "--finalists",
        default=None,
        help="Comma-separated experiment ids to include; used for finalist-only candidate_exhaustive validation.",
    )
    parser.add_argument(
        "--horizons",
        default=None,
        help="Comma-separated rolling horizons to run, such as 90,180. Omitted supported horizons are reported as non-final.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "final_audit":
        raise SystemExit("final_audit is reserved and not implemented for heavy runs.")
    if args.include_combination_batch1 and args.mode != "research_sample":
        raise SystemExit("--include-combination-batch1 is allowed only with --mode research_sample")
    if args.include_commodity_basket_exploratory and args.mode != "research_sample":
        raise SystemExit("--include-commodity-basket-exploratory is allowed only with --mode research_sample")
    if args.include_commodity_risk_control_batch1 and args.mode != "research_sample":
        raise SystemExit("--include-commodity-risk-control-batch1 is allowed only with --mode research_sample")
    if args.include_commodity_risk_control_batch1 and not args.include_commodity_basket_exploratory:
        raise SystemExit("--include-commodity-risk-control-batch1 requires --include-commodity-basket-exploratory")
    if args.include_crypto_tier2_risk_control_batch1 and args.mode != "research_sample":
        raise SystemExit("--include-crypto-tier2-risk-control-batch1 is allowed only with --mode research_sample")
    if args.include_global_multi_asset_batch1 and args.mode != "research_sample":
        raise SystemExit("--include-global-multi-asset-batch1 is allowed only with --mode research_sample")
    if args.diagnostics_only:
        if args.include_combination_batch1 and args.include_commodity_risk_control_batch1:
            raise SystemExit("--diagnostics-only accepts one diagnostics batch at a time")
        if args.include_combination_batch1:
            run_dir, latest_dir, manifest = write_combination_diagnostics_only_outputs(args)
            print(f"combination_batch1_diagnostics_run_dir={run_dir}")
            print(f"combination_batch1_diagnostics_latest_dir={latest_dir}")
            print(f"combination_batch1_diagnostics_detail={latest_dir / COMBINATION_DIAGNOSTICS_DETAIL_FILE}")
            print(f"combination_batch1_diagnostics_rows={manifest['row_count']}")
            if manifest.get("attribution_diagnostics_exported"):
                print(f"attribution_diagnostics_detail={manifest.get('attribution_diagnostics_path')}")
        elif args.include_commodity_risk_control_batch1:
            run_dir, latest_dir, manifest = write_commodity_risk_control_diagnostics_only_outputs(args)
            print(f"commodity_risk_control_diagnostics_run_dir={run_dir}")
            print(f"commodity_risk_control_diagnostics_latest_dir={latest_dir}")
            print(f"commodity_risk_control_diagnostics_detail={latest_dir / COMMODITY_RISK_CONTROL_DIAGNOSTICS_DETAIL_FILE}")
            print(f"commodity_risk_control_diagnostics_rows={manifest['row_count']}")
        else:
            raise SystemExit("--diagnostics-only requires --include-combination-batch1 or --include-commodity-risk-control-batch1")
        print("candidate_exhaustive_run=false")
        print("profit_exploration_latest_rewritten=false")
        print("data_downloaded=false")
        print("real_money_recommendation=false")
        return 0
    if args.score_only:
        if not args.reuse_latest:
            raise SystemExit("--score-only requires --reuse-latest")
        latest_dir, context = write_score_only_outputs(args)
        rankings = context["rankings"]
        print(f"profit_exploration_score_only_latest_dir={latest_dir}")
        print(f"profit_exploration_latest_zip={context['zip_path']}")
        print(f"profit_exploration_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
        best = rankings.sort_values("rank_balanced_drawdown_aware_v2").iloc[0]
        print(f"best_balanced_drawdown_aware_v2={best['experiment_id']}")
        print("strategy_simulation_rerun=false")
        print("real_money_recommendation=false")
        return 0
    run_dir, latest_dir, context = write_outputs(args)
    print(f"profit_exploration_run_dir={run_dir}")
    print(f"profit_exploration_latest_dir={latest_dir}")
    print(f"profit_exploration_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    if "combination_latest_dir" in context:
        print(f"combination_batch1_latest_dir={context['combination_latest_dir']}")
        print(f"combination_batch1_latest_zip={context['combination_zip_path']}")
    if "commodity_exploratory_latest_dir" in context:
        print(f"commodity_exploratory_latest_dir={context['commodity_exploratory_latest_dir']}")
        print(f"commodity_exploratory_latest_zip={context['commodity_exploratory_zip_path']}")
    if "commodity_risk_control_latest_dir" in context:
        print(f"commodity_risk_control_latest_dir={context['commodity_risk_control_latest_dir']}")
        print(f"commodity_risk_control_latest_zip={context['commodity_risk_control_zip_path']}")
    if "crypto_tier2_risk_control_latest_dir" in context:
        print(f"crypto_tier2_risk_control_latest_dir={context['crypto_tier2_risk_control_latest_dir']}")
        print(f"crypto_tier2_risk_control_latest_zip={context['crypto_tier2_risk_control_zip_path']}")
    if "global_multi_asset_batch1_latest_dir" in context:
        print(f"global_multi_asset_batch1_latest_dir={context['global_multi_asset_batch1_latest_dir']}")
        print(f"global_multi_asset_batch1_latest_zip={context['global_multi_asset_batch1_zip_path']}")
    best = context["rankings"].sort_values("rank_overall").iloc[0]
    print(f"best_overall_profit_experiment={best['experiment_id']}")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
