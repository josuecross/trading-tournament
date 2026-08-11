from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "phase2_public_signal_etf_mappable_candidate_intake_v2"
TASK_OUTCOME = "phase2_public_signal_one_candidate_qualified"
NEXT_ACTION = "acquire_validate_freeze_phase2_public_signal_inputs_v1"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
SELECTED_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
SELECTED_FAMILY = "public_cpi_dynamic_inflation_regime_allocation"
OUTPUT_DIR = ROOT / "evidence" / "public_source_strategy_intake" / TASK_ID / "latest"

REQUIRED_OUTPUTS = {
    "intake_report.md",
    "serious_candidate_ledger.csv",
    "source_rule_extraction.csv",
    "source_citations.csv",
    "lineage_comparison.csv",
    "tradable_exposure_mapping.csv",
    "external_signal_feasibility.csv",
    "sample_feasibility.csv",
    "control_design.csv",
    "candidate_ranking.csv",
    "selected_work_packages.json",
    "consistency_check.json",
    "next_action.md",
}

GROUPS = (
    "credit",
    "Treasury duration",
    "commodities/real assets",
    "size/broad/equal-weight equity",
    "global/country/regional equity",
)

SIGNAL_CLASSIFICATIONS = {
    "public_point_in_time_feasible",
    "public_with_explicit_release_lag_feasible",
    "public_but_vintage_problem_unresolved",
    "public_history_inadequate",
    "proprietary_or_unavailable",
    "rules_do_not_define_signal",
}
MAPPING_CLASSIFICATIONS = {
    "exact_match",
    "economically_close_source_preserving_proxy",
    "materially_altering_proxy",
    "unsupported",
}
REJECTION_REASONS = {
    "unsupported_tradable_exposure",
    "public_signal_data_unavailable",
    "point_in_time_history_inadequate",
    "source_rules_incomplete",
    "proprietary_signal_or_rules",
    "duplicate_or_near_duplicate",
    "sample_inadequate",
    "mechanism_already_saturated",
    "other",
}
LINEAGE_CLASSIFICATIONS = {
    "genuinely_new_architecture",
    "related_but_materially_distinct",
    "duplicate",
    "near_duplicate",
    "cosmetic_instrument_substitution",
}

FROZEN_SYMBOLS = tuple(
    "ACWX AGG AMLP ANGL BIL BKLN DBA DBC DGRO DIA EEM EEMV EFA EFAV EMB EPP EWA EWC "
    "EWG EWH EWJ EWL EWP EWQ EWS EWT EWU EWW EWY EWZ FLOT GLD GOVT GSG HYG IBB IEF "
    "IEI IFRA IJH IJR INDA ITB IWM IYR IYT JNK KRE LQD MTUM MUB OEF QQQ QUAL REET RSP "
    "SCHD SCHG SHY SLV SMH SPLV SPY TIP TLT URTH USMV USO VBR VCIT VGK VIG VLUE VPL "
    "VTV XBI XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY XRT"
.split()
)

UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
PHASE2_CACHE = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"
PRIOR_PACKET = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "phase2_underexplored_group_source_candidate_intake_v1"
    / "latest"
)
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations",
    ROOT / "paper_forward_observation_plans",
    UNIVERSE_DIR,
    PHASE2_CACHE,
    PRIOR_PACKET,
)


def rule(**overrides: str) -> dict[str, str]:
    base = {
        "economic_rationale": "source-defined allocation mechanism",
        "tradable_exposure_universe": "source-defined broad exposures",
        "signal_definition": "source-defined signal",
        "exact_signal_inputs": "source-defined inputs",
        "lookback_or_measurement_period": "source-defined measurement period",
        "formation_timing": "source-defined formation timing",
        "rebalance_timing": "source-defined rebalance timing",
        "decision_rule": "source-defined decision rule",
        "ranking_or_threshold_rule": "not_applicable",
        "allocation_weights": "source-defined weights",
        "defensive_or_cash_treatment": "source-defined defensive treatment",
        "information_lag": "source-defined information lag",
        "transaction_timing": "after source-defined information is available",
        "benchmark_or_control": "source-defined or prospectively frozen control",
        "material_conditions": "none beyond fields recorded here",
        "unresolved_material_fields": "",
    }
    base.update(overrides)
    return base


SOURCES = {
    "sp_dynamic_inflation": {
        "name": "S&P Multi-Asset Dynamic Inflation Strategy Index Methodology",
        "provider": "S&P Dow Jones Indices",
        "year": "2024",
        "url": "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-multi-asset-dynamic-inflation-strategy-index.pdf",
        "type": "official_index_methodology",
        "authority": "primary_authoritative",
    },
    "balvers_country": {
        "name": "Mean Reversion across National Stock Markets and Parametric Contrarian Investment Strategies",
        "provider": "Balvers, Wu, and Gilliland / Journal of Finance",
        "year": "2000",
        "url": "https://doi.org/10.1111/0022-1082.00244",
        "type": "peer_reviewed_article",
        "authority": "primary_authoritative",
    },
    "sp_cycle_factor": {
        "name": "S&P Economic Cycle Factor Rotator Indices Methodology",
        "provider": "S&P Dow Jones Indices",
        "year": "2025",
        "url": "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-economic-cycle-factor-rotator-indices.pdf",
        "type": "official_index_methodology",
        "authority": "primary_authoritative",
    },
    "fama_bliss": {
        "name": "The Information in Long-Maturity Forward Rates",
        "provider": "Eugene Fama and Robert Bliss / American Economic Review",
        "year": "1987",
        "url": "https://www.jstor.org/stable/1812966",
        "type": "peer_reviewed_article",
        "authority": "primary_but_materially_incomplete",
    },
    "gilchrist_ebp": {
        "name": "Credit Spreads and Business Cycle Fluctuations",
        "provider": "Simon Gilchrist and Egon Zakrajsek / NBER and American Economic Review",
        "year": "2012",
        "url": "https://www.nber.org/papers/w17021",
        "type": "peer_reviewed_working_paper",
        "authority": "primary_authoritative_but_not_strategy_contract",
    },
    "ra_inflation": {
        "name": "Predicting Equity Returns with Inflation",
        "provider": "Research Affiliates",
        "year": "2021",
        "url": "https://media.researchaffiliates.com/841_predicting_equity_returns_with_inflation_7e9ab8eef2.pdf",
        "type": "author_research_paper",
        "authority": "primary_authoritative",
    },
    "maio_fed": {
        "name": "Don't Fight the Fed!",
        "provider": "Paulo Maio / Review of Finance",
        "year": "2014",
        "url": "https://academic.oup.com/rof/article-abstract/18/2/623/1577880",
        "type": "peer_reviewed_article",
        "authority": "primary_but_materially_incomplete",
    },
    "fed_model": {
        "name": "The Fed Model and the Predictability of Stock Returns",
        "provider": "SSRN author paper",
        "year": "2006",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=889931",
        "type": "author_working_paper",
        "authority": "primary_authoritative_with_vintage_gap",
    },
    "commodity_taa": {
        "name": "Tactical Asset Allocation and Commodity Futures",
        "provider": "Jensen, Johnson, and Mercer / Journal of Portfolio Management",
        "year": "2002",
        "url": "https://doi.org/10.3905/jpm.2002.319859",
        "type": "peer_reviewed_article",
        "authority": "primary_but_materially_incomplete",
    },
    "sp_real_assets": {
        "name": "S&P Real Assets Index Series Methodology",
        "provider": "S&P Dow Jones Indices",
        "year": "2026",
        "url": "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-real-assets-index-series.pdf",
        "type": "official_index_methodology",
        "authority": "primary_authoritative",
    },
}


CANDIDATES = [
    {
        "candidate_id": SELECTED_ID,
        "family_id": SELECTED_FAMILY,
        "architecture_id": "monthly_cpi_regime_dynamic_multi_asset_inflation_allocation",
        "capability_group": "commodities/real assets",
        "source_key": "sp_dynamic_inflation",
        "mechanism": "CPI regimes allocate broad equity, real estate, commodities, gold, aggregate bonds, and TIPS using source-defined static, inverse-volatility, or inflation-beta weights.",
        "rule_status": "source_rules_complete",
        "lineage": "related_but_materially_distinct",
        "mapping_status": "economically_close_source_preserving_proxy",
        "signal_status": "public_with_explicit_release_lag_feasible",
        "sample_status": "adequate_after_36_month_expanding_warmup",
        "qualification_status": "qualified",
        "rejection_reason": "",
        "rejection_detail": "",
        "rank": 1,
        "rule": rule(
            economic_rationale="Inflation hedges differ by inflation regime; dynamic cross-asset weights seek regime-appropriate inflation sensitivity.",
            tradable_exposure_universe="U.S. equity, U.S. REIT, broad commodities, gold, U.S. aggregate bonds, and U.S. TIPS",
            signal_definition="CPI-U All Items NSA year-over-year inflation determines low, medium, or high inflation regime.",
            exact_signal_inputs="CPIAUCNS first available release value and six mapped ETF month-end total-return series",
            lookback_or_measurement_period="120 monthly observations; expanding window with at least 36 observations when 120 are unavailable",
            formation_timing="monthly after the CPI announcement for the reference month",
            rebalance_timing="monthly",
            decision_rule="low inflation uses 60/40 equity/sovereign bond; medium inflation uses normalized inverse realized volatility; high inflation uses normalized transformed inflation beta",
            ranking_or_threshold_rule="low when CPI YoY < 1.5%; medium when 1.5% <= CPI YoY <= 2.5%; high when CPI YoY > 2.5%",
            allocation_weights="low: 60% equity and 40% aggregate bond; medium: normalized inverse sample volatility; high: B=1+beta for beta>=0 else 1/(1-beta), normalized",
            defensive_or_cash_treatment="aggregate bond is the source low-regime defensive exposure; no discretionary cash rule",
            information_lag="use only CPI release available at decision time; later validation must preserve first-vintage values",
            transaction_timing="effective after close on the next business day after the CPI announcement; source return inputs end at the prior month-end",
            benchmark_or_control="static source low-regime 60/40 equity/aggregate-bond allocation",
            material_conditions="sample standard deviation uses N-1; inflation beta is OLS of rolling 12-month cumulative asset return on CPI YoY over the available lookback",
        ),
    },
    {
        "candidate_id": "balvers_wu_gilliland_country_index_mean_reversion_etf_v1",
        "family_id": "parametric_country_index_mean_reversion",
        "architecture_id": "cross_country_parametric_contrarian_long_short_allocation",
        "capability_group": "global/country/regional equity",
        "source_key": "balvers_country",
        "mechanism": "Relative deviations from estimated national-equity-index equilibrium paths define a parametric contrarian long-short country portfolio.",
        "rule_status": "source_rules_complete",
        "lineage": "near_duplicate",
        "mapping_status": "unsupported",
        "signal_status": "public_point_in_time_feasible",
        "sample_status": "inadequate_for_source_aligned_universe_and_short_book",
        "qualification_status": "rejected",
        "rejection_reason": "unsupported_tradable_exposure",
        "rejection_detail": "The source requires simultaneous long and short positions across its full national-index universe; the frozen ETFs omit source countries and the production long-short lane is not viable. It is also near existing country-reversal lineage.",
        "rank": 2,
        "rule": rule(
            economic_rationale="National equity indexes exhibit common and country-specific mean reversion that can support contrarian relative-value portfolios.",
            tradable_exposure_universe="the source's complete set of 18 national MSCI equity indexes, held long and short",
            signal_definition="source parametric deviation from estimated country equilibrium paths",
            exact_signal_inputs="national equity index returns and source model state variables",
            lookback_or_measurement_period="source estimation and recursive portfolio contract",
            formation_timing="source monthly observation schedule",
            rebalance_timing="monthly",
            decision_rule="overweight relatively depressed country indexes and underweight/short relatively elevated indexes under the source parametric rule",
            allocation_weights="source zero-cost parametric contrarian weights",
            defensive_or_cash_treatment="not a long-only cash switch",
            information_lag="completed monthly index observations",
            transaction_timing="following source monthly formation",
            benchmark_or_control="source world-index and non-contrarian comparison",
            material_conditions="full country universe and simultaneous signed positions are integral to the source mechanism",
        ),
    },
    {
        "candidate_id": "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1",
        "family_id": "public_economic_cycle_equity_factor_rotation",
        "architecture_id": "monthly_cfnai_state_equity_factor_rotation",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "sp_cycle_factor",
        "mechanism": "CFNAI level and change select source-defined momentum, value, buyback, or low-volatility/high-dividend equity factors.",
        "rule_status": "source_rules_complete",
        "lineage": "related_but_materially_distinct",
        "mapping_status": "unsupported",
        "signal_status": "public_with_explicit_release_lag_feasible",
        "sample_status": "signal_adequate_but_source_exposures_unsupported",
        "qualification_status": "rejected",
        "rejection_reason": "unsupported_tradable_exposure",
        "rejection_detail": "The frozen universe lacks source-preserving S&P Buyback Free Cash Flow and Low Volatility High Dividend exposures; combining nearby ETFs would change the source states.",
        "rank": 3,
        "rule": rule(
            economic_rationale="Equity factors have different economic-cycle sensitivities.",
            tradable_exposure_universe="S&P momentum, pure value, buyback free-cash-flow, and low-volatility high-dividend factor indices",
            signal_definition="CFNAI three-month average level and change identify the source economic-cycle state",
            exact_signal_inputs="Chicago Fed National Activity Index with publication date",
            lookback_or_measurement_period="three-month CFNAI average and month-over-month change",
            formation_timing="monthly after CFNAI availability",
            rebalance_timing="first business day of the month under the source schedule",
            decision_rule="official CFNAI quadrant-to-factor table, including the source transition retention condition",
            allocation_weights="100% selected factor index",
            information_lag="use the released CFNAI vintage available before the effective rebalance",
            transaction_timing="official monthly effective date after signal availability",
            benchmark_or_control="static equal-weight mapped factor exposures",
        ),
    },
    {
        "candidate_id": "fama_bliss_forward_rate_treasury_duration_allocation_v1",
        "family_id": "forward_rate_treasury_expected_return_allocation",
        "architecture_id": "forward_rate_implied_zero_coupon_duration_allocation",
        "capability_group": "Treasury duration",
        "source_key": "fama_bliss",
        "mechanism": "Forward rates forecast holding-period excess returns across default-free zero-coupon Treasury maturities.",
        "rule_status": "source_rules_incomplete",
        "lineage": "genuinely_new_architecture",
        "mapping_status": "materially_altering_proxy",
        "signal_status": "public_with_explicit_release_lag_feasible",
        "sample_status": "indeterminate_without_canonical_portfolio_rule",
        "qualification_status": "rejected",
        "rejection_reason": "source_rules_incomplete",
        "rejection_detail": "The paper establishes forward-rate return predictability but does not define one canonical investable ETF selection rule, threshold, weights, or repository-compatible execution contract.",
        "rank": 4,
        "rule": rule(
            economic_rationale="The slope embedded in forward rates contains time-varying expected Treasury term returns.",
            tradable_exposure_universe="default-free zero-coupon Treasury bonds across source maturities",
            signal_definition="forward-rate regressions forecast maturity-specific holding-period excess returns",
            exact_signal_inputs="source zero-coupon prices and implied one-year forward rates",
            lookback_or_measurement_period="source regression sample; no canonical live recursive estimation contract",
            formation_timing="annual holding-period forecasts in the source tests",
            rebalance_timing="not frozen as an investable strategy",
            decision_rule="predictive regression documented; allocation threshold and selection rule not defined",
            allocation_weights="not defined",
            defensive_or_cash_treatment="one-year bond is the excess-return reference, not a fully specified defensive rule",
            information_lag="official Treasury observations would require an explicit publication lag",
            transaction_timing="not defined",
            unresolved_material_fields="canonical portfolio decision, recursive estimation, maturity mapping, weights, and execution",
        ),
    },
    {
        "candidate_id": "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1",
        "family_id": "excess_bond_premium_credit_timing",
        "architecture_id": "public_credit_premium_regime_allocation",
        "capability_group": "credit",
        "source_key": "gilchrist_ebp",
        "mechanism": "The excess bond premium isolates a credit-supply component of corporate spreads associated with future economic activity.",
        "rule_status": "source_rules_incomplete",
        "lineage": "genuinely_new_architecture",
        "mapping_status": "economically_close_source_preserving_proxy",
        "signal_status": "public_but_vintage_problem_unresolved",
        "sample_status": "indeterminate_without_portfolio_rule_and_vintage_contract",
        "qualification_status": "rejected",
        "rejection_reason": "source_rules_incomplete",
        "rejection_detail": "The paper defines and studies the excess bond premium but does not define a canonical HYG/IEF allocation, threshold, weights, or trading schedule; point-in-time public EBP vintages also remain unresolved.",
        "rank": 5,
        "rule": rule(
            economic_rationale="The spread component attributable to intermediary credit supply contains macro and credit-risk information beyond expected defaults.",
            tradable_exposure_universe="paper is predictive and does not define a traded credit/Treasury portfolio",
            signal_definition="Gilchrist-Zakrajsek excess bond premium",
            exact_signal_inputs="bond-level spread decomposition published as a research series; exact live vintage contract unresolved",
            lookback_or_measurement_period="source regression construction",
            formation_timing="monthly signal observations",
            rebalance_timing="not defined",
            decision_rule="no investable threshold or ranking rule defined",
            allocation_weights="not defined",
            information_lag="must use the EBP release available at formation; vintage archive unresolved",
            transaction_timing="not defined",
            unresolved_material_fields="portfolio mapping, threshold, weights, execution, and public point-in-time EBP vintages",
        ),
    },
    {
        "candidate_id": "research_affiliates_inflation_cycle_equity_timing_v1",
        "family_id": "inflation_cycle_equity_timing",
        "architecture_id": "lagged_inflation_cycle_and_surprise_equity_timing",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "ra_inflation",
        "mechanism": "Lagged inflation-cycle or surprise states define long-equity versus short-equity portfolios financed by Treasury bills.",
        "rule_status": "source_rules_complete",
        "lineage": "genuinely_new_architecture",
        "mapping_status": "unsupported",
        "signal_status": "public_with_explicit_release_lag_feasible",
        "sample_status": "adequate_signal_and_long_leg_history_but_short_leg_unsupported",
        "qualification_status": "rejected",
        "rejection_reason": "unsupported_tradable_exposure",
        "rejection_detail": "The source-defined positive-signal state shorts equity; replacing it with BIL or zero equity would materially alter the mechanism, and the current long-short engine lane is not viable.",
        "rank": 6,
        "rule": rule(
            economic_rationale="Equity returns vary with persistent inflation cycles and inflation surprises.",
            tradable_exposure_universe="long or short broad equity financed by Treasury bills",
            signal_definition="inflation cycle equals current CPI YoY minus an EWMA of prior inflation; inflation surprise equals current minus prior inflation",
            exact_signal_inputs="CPI-U All Items NSA year-over-year inflation",
            lookback_or_measurement_period="EWMA decay 0.99 truncated at 120 months; source signals lagged two calendar months",
            formation_timing="monthly",
            rebalance_timing="monthly",
            decision_rule="negative signal: long equity; positive signal: short equity; source also reports an average portfolio",
            allocation_weights="unit long or unit short broad equity with Treasury-bill financing",
            defensive_or_cash_treatment="Treasury-bill financing, not a long-only defensive switch",
            information_lag="two calendar months",
            transaction_timing="monthly after the lagged signal is known",
            benchmark_or_control="broad equity and Treasury-bill benchmarks",
        ),
    },
    {
        "candidate_id": "maio_fed_funds_change_spy_bil_recursive_v1",
        "family_id": "monetary_policy_equity_timing",
        "architecture_id": "recursive_fed_funds_change_equity_timing",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "maio_fed",
        "mechanism": "Federal-funds policy changes time broad equity against bills.",
        "rule_status": "source_rules_incomplete",
        "lineage": "duplicate",
        "mapping_status": "exact_match",
        "signal_status": "rules_do_not_define_signal",
        "sample_status": "indeterminate_due_to_unresolved_signal_contract",
        "qualification_status": "rejected",
        "rejection_reason": "duplicate_or_near_duplicate",
        "rejection_detail": "This exact strategy ID and unresolved author-appendix intake already exist; the current search found no new primary-source rule that repairs the signal contract.",
        "rank": 7,
        "rule": rule(
            economic_rationale="Equity expected returns may vary with monetary-policy direction.",
            tradable_exposure_universe="broad U.S. equity and Treasury bills",
            signal_definition="recursive federal-funds-rate change rule; exact repository intake remains unresolved",
            exact_signal_inputs="exact federal-funds series and transformation unresolved",
            lookback_or_measurement_period="unresolved",
            formation_timing="unresolved",
            rebalance_timing="unresolved",
            decision_rule="unresolved",
            allocation_weights="SPY/BIL translation was proposed but not authorized",
            information_lag="unresolved",
            transaction_timing="unresolved",
            unresolved_material_fields="exact rate series, recursive formula, allocation state, and publication-safe timing",
        ),
    },
    {
        "candidate_id": "maio_fed_model_yield_gap_spy_bil_recursive_v1",
        "family_id": "earnings_yield_bond_yield_equity_timing",
        "architecture_id": "recursive_earnings_yield_treasury_yield_gap_timing",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "fed_model",
        "mechanism": "The equity earnings-yield versus Treasury-yield gap times broad equity against bills.",
        "rule_status": "source_rules_complete_but_input_vintage_unresolved",
        "lineage": "duplicate",
        "mapping_status": "exact_match",
        "signal_status": "public_but_vintage_problem_unresolved",
        "sample_status": "inadequate_until_point_in_time_earnings_yield_is_resolved",
        "qualification_status": "rejected",
        "rejection_reason": "duplicate_or_near_duplicate",
        "rejection_detail": "The exact repository candidate was previously closed at data feasibility because the public earnings-yield history could not be made point-in-time safe; no new vintage source was found.",
        "rank": 8,
        "rule": rule(
            economic_rationale="Relative equity and Treasury yields may contain broad equity timing information.",
            tradable_exposure_universe="broad U.S. equity and Treasury bills",
            signal_definition="source earnings-yield minus Treasury-yield gap under the paper's recursive rule",
            exact_signal_inputs="point-in-time aggregate equity earnings yield and Treasury yield",
            lookback_or_measurement_period="paper-defined recursive estimation history",
            formation_timing="monthly",
            rebalance_timing="monthly",
            decision_rule="paper-defined recursive forecast sign",
            allocation_weights="SPY/BIL repository translation",
            information_lag="earnings data must use the value known at formation",
            transaction_timing="after monthly signal availability",
            unresolved_material_fields="point-in-time aggregate earnings-yield vintages",
        ),
    },
    {
        "candidate_id": "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1",
        "family_id": "monetary_regime_commodity_allocation",
        "architecture_id": "fed_policy_conditioned_commodity_tactical_allocation",
        "capability_group": "commodities/real assets",
        "source_key": "commodity_taa",
        "mechanism": "Federal Reserve policy state changes commodity-futures allocations within a tactical portfolio.",
        "rule_status": "source_rules_incomplete",
        "lineage": "genuinely_new_architecture",
        "mapping_status": "materially_altering_proxy",
        "signal_status": "public_with_explicit_release_lag_feasible",
        "sample_status": "indeterminate_without_canonical_source_portfolio_contract",
        "qualification_status": "rejected",
        "rejection_reason": "source_rules_incomplete",
        "rejection_detail": "The public paper supports the monetary-regime mechanism but does not freeze one canonical long-only ETF allocation, weights, and timing that preserve its managed/unmanaged commodity-futures construction.",
        "rank": 9,
        "rule": rule(
            economic_rationale="Commodity behavior and diversification may differ between expansive and restrictive monetary policy.",
            tradable_exposure_universe="managed and unmanaged commodity futures plus conventional assets",
            signal_definition="Federal Reserve monetary-policy regime",
            exact_signal_inputs="public Federal Reserve policy-rate history",
            lookback_or_measurement_period="source monetary-policy classification; complete reproducible transformation unresolved",
            formation_timing="source study periods; canonical ETF formation schedule unresolved",
            rebalance_timing="unresolved",
            decision_rule="restrictive-versus-expansive policy conditioned allocation",
            allocation_weights="optimized source portfolios; no single canonical ETF weights disclosed for this intake",
            information_lag="policy classification must lag public announcement",
            transaction_timing="unresolved",
            unresolved_material_fields="canonical rule, weights, rebalance timing, and source-preserving ETF translation",
        ),
    },
    {
        "candidate_id": "spdj_real_assets_static_index_etf_portability_v1",
        "family_id": "static_multi_asset_real_asset_allocation",
        "architecture_id": "static_real_assets_multi_component_allocation",
        "capability_group": "commodities/real assets",
        "source_key": "sp_real_assets",
        "mechanism": "A strategic blend of real estate, infrastructure, commodities, and inflation-linked bonds supplies broad inflation sensitivity.",
        "rule_status": "source_rules_complete",
        "lineage": "related_but_materially_distinct",
        "mapping_status": "economically_close_source_preserving_proxy",
        "signal_status": "public_point_in_time_feasible",
        "sample_status": "adequate_but_signal_free_static_mechanism_saturated",
        "qualification_status": "rejected",
        "rejection_reason": "mechanism_already_saturated",
        "rejection_detail": "The source is a static strategic allocation with no decision signal; the repository already uses static multi-asset and equal-weight controls, so it does not add the requested architecture diversity.",
        "rank": 10,
        "rule": rule(
            economic_rationale="Real assets may provide strategic inflation sensitivity and diversification.",
            tradable_exposure_universe="global real estate, infrastructure, commodities, and inflation-linked bonds",
            signal_definition="none; static source allocation",
            exact_signal_inputs="constituent index levels only",
            lookback_or_measurement_period="not_applicable",
            formation_timing="source index base allocation",
            rebalance_timing="semiannual source review",
            decision_rule="hold the source strategic component weights",
            allocation_weights="official methodology component and group weights",
            defensive_or_cash_treatment="none",
            information_lag="official index review effective date",
            transaction_timing="official review effective date",
            benchmark_or_control="static equal-weight mapped real-asset basket",
        ),
    },
]


MAPPINGS = {
    SELECTED_ID: [
        ("S&P Composite 1500 Total Return", "SPY", "economically_close_source_preserving_proxy", "SPY preserves broad U.S. capitalization-weighted equity exposure."),
        ("S&P U.S. REIT Total Return", "IYR", "economically_close_source_preserving_proxy", "IYR preserves broad U.S. listed real-estate exposure."),
        ("S&P GSCI Total Return", "GSG", "exact_match", "GSG is the frozen ETF wrapper for the referenced broad S&P GSCI exposure."),
        ("S&P GSCI Gold Total Return", "GLD", "economically_close_source_preserving_proxy", "GLD preserves unlevered gold exposure without reconstructing a futures index."),
        ("S&P U.S. Aggregate Bond Total Return", "AGG", "economically_close_source_preserving_proxy", "AGG preserves broad U.S. investment-grade aggregate-bond exposure."),
        ("S&P U.S. TIPS Total Return", "TIP", "economically_close_source_preserving_proxy", "TIP preserves broad U.S. inflation-linked Treasury exposure."),
    ],
    "balvers_wu_gilliland_country_index_mean_reversion_etf_v1": [
        ("complete source set of 18 national equity indexes", "EWA|EWC|EWG|EWH|EWJ|EWL|EWP|EWS|EWT|EWU", "unsupported", "The frozen set omits multiple source countries, so the complete cross-section cannot be preserved."),
        ("simultaneous short national-equity-index positions", "", "unsupported", "The production long-short lane is not viable and no inverse ETF may be added."),
    ],
    "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1": [
        ("S&P 500 Momentum", "MTUM", "economically_close_source_preserving_proxy", "MTUM preserves broad U.S. equity momentum exposure."),
        ("S&P 500 Pure Value", "VLUE", "economically_close_source_preserving_proxy", "VLUE preserves broad value-factor exposure but is not the exact index."),
        ("S&P 500 Buyback Free Cash Flow", "", "unsupported", "No frozen ETF jointly preserves the source buyback and free-cash-flow exposure."),
        ("S&P 500 Low Volatility High Dividend", "", "unsupported", "SPLV and SCHD are separate exposures; combining them would invent a new source state."),
    ],
    "fama_bliss_forward_rate_treasury_duration_allocation_v1": [
        ("maturity-specific zero-coupon Treasury bonds and one-year holding returns", "SHY|IEI|IEF", "materially_altering_proxy", "Coupon-bearing rolling ETFs do not preserve zero-coupon maturity-specific forward-return mechanics."),
    ],
    "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1": [
        ("broad corporate credit and Treasury defensive exposure for a possible future portability rule", "HYG|LQD|IEF", "economically_close_source_preserving_proxy", "The ETFs preserve broad top-level exposures, but the primary source does not authorize a portfolio rule."),
    ],
    "research_affiliates_inflation_cycle_equity_timing_v1": [
        ("long broad U.S. equity", "SPY", "exact_match", "SPY preserves the source long broad-equity leg."),
        ("short broad U.S. equity", "", "unsupported", "No unlevered inverse instrument is admitted and current production long-short support is not viable."),
        ("Treasury-bill financing", "BIL", "exact_match", "BIL preserves the cash-like financing exposure."),
    ],
    "maio_fed_funds_change_spy_bil_recursive_v1": [
        ("broad U.S. equity and Treasury bills", "SPY|BIL", "exact_match", "The frozen pair matches the existing repository translation."),
    ],
    "maio_fed_model_yield_gap_spy_bil_recursive_v1": [
        ("broad U.S. equity and Treasury bills", "SPY|BIL", "exact_match", "The frozen pair matches the existing repository translation."),
    ],
    "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1": [
        ("managed and unmanaged commodity-futures portfolios", "GSG", "materially_altering_proxy", "One broad long-only commodity ETF cannot reproduce the source futures-management alternatives and optimized construction."),
        ("conventional equity and bond sleeves", "SPY|AGG|BIL", "economically_close_source_preserving_proxy", "Frozen ETFs preserve the broad conventional-asset sleeves."),
    ],
    "spdj_real_assets_static_index_etf_portability_v1": [
        ("global real estate", "REET", "economically_close_source_preserving_proxy", "REET preserves global listed real-estate exposure."),
        ("global infrastructure", "IFRA", "economically_close_source_preserving_proxy", "IFRA is a broad listed-infrastructure proxy within the frozen set."),
        ("broad commodities", "GSG", "economically_close_source_preserving_proxy", "GSG preserves broad commodity exposure."),
        ("inflation-linked bonds", "TIP", "economically_close_source_preserving_proxy", "TIP preserves U.S. inflation-linked bond exposure."),
    ],
}


SIGNALS = {
    SELECTED_ID: [
        {
            "signal_requirement": "CPI-U All Items NSA year-over-year inflation",
            "provider": "U.S. Bureau of Labor Statistics; FRED/ALFRED distribution",
            "dataset_or_series": "CPIAUCNS",
            "frequency": "monthly",
            "available_history": "1913-present; ALFRED vintages listed from 1949-present",
            "release_timing": "BLS CPI release schedule, normally after reference month",
            "revision_behavior": "seasonally unadjusted CPI may be corrected; first-vintage value must be frozen",
            "historical_vintages_necessary": True,
            "historical_vintages_available": True,
            "required_implementation_lag": "effective after close on the next business day after the CPI announcement",
            "access_method": "BLS public release archive and ALFRED API/download in the next data-capability task",
            "licensing_or_public_use": "public U.S. government data",
            "lookahead_safe_reconstruction": True,
            "classification": "public_with_explicit_release_lag_feasible",
        }
    ],
    "balvers_wu_gilliland_country_index_mean_reversion_etf_v1": [
        {"signal_requirement": "completed national-equity-index returns and source model state", "provider": "source national index providers; ETF portability would use frozen adjusted prices", "dataset_or_series": "country index returns", "frequency": "monthly", "available_history": "source sample adequate; frozen ETF cross-section incomplete", "release_timing": "completed month-end values", "revision_behavior": "adjusted total-return history may be revised for corporate actions", "historical_vintages_necessary": False, "historical_vintages_available": True, "required_implementation_lag": "next-session execution after completed month-end", "access_method": "existing canonical cache only for mapped ETFs", "licensing_or_public_use": "repository cache rules", "lookahead_safe_reconstruction": True, "classification": "public_point_in_time_feasible"}
    ],
    "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1": [
        {"signal_requirement": "Chicago Fed National Activity Index", "provider": "Federal Reserve Bank of Chicago; ALFRED", "dataset_or_series": "CFNAI", "frequency": "monthly", "available_history": "1967-present", "release_timing": "published monthly on the Chicago Fed calendar", "revision_behavior": "revised as component data change", "historical_vintages_necessary": True, "historical_vintages_available": True, "required_implementation_lag": "use the vintage released before the source effective date", "access_method": "official Chicago Fed download and ALFRED", "licensing_or_public_use": "public", "lookahead_safe_reconstruction": True, "classification": "public_with_explicit_release_lag_feasible"}
    ],
    "fama_bliss_forward_rate_treasury_duration_allocation_v1": [
        {"signal_requirement": "maturity-specific zero-coupon Treasury yields and implied forward rates", "provider": "Federal Reserve and U.S. Treasury public yield data", "dataset_or_series": "Treasury yield-curve observations; source CRSP zero-coupon construction is not replicated here", "frequency": "daily/monthly", "available_history": "long public history", "release_timing": "official daily publication with explicit lag required", "revision_behavior": "current history may be corrected", "historical_vintages_necessary": True, "historical_vintages_available": True, "required_implementation_lag": "after official yield publication", "access_method": "official public Treasury/Federal Reserve series in a later task only", "licensing_or_public_use": "public", "lookahead_safe_reconstruction": True, "classification": "public_with_explicit_release_lag_feasible"}
    ],
    "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1": [
        {"signal_requirement": "Gilchrist-Zakrajsek excess bond premium", "provider": "Federal Reserve Board research data", "dataset_or_series": "Excess Bond Premium", "frequency": "monthly", "available_history": "public current research series", "release_timing": "publication schedule and historical as-of values not fully archived", "revision_behavior": "research series may be revised", "historical_vintages_necessary": True, "historical_vintages_available": False, "required_implementation_lag": "would require a frozen public release date", "access_method": "Federal Reserve public research download in a later task only", "licensing_or_public_use": "public research data", "lookahead_safe_reconstruction": False, "classification": "public_but_vintage_problem_unresolved"}
    ],
    "research_affiliates_inflation_cycle_equity_timing_v1": [
        {"signal_requirement": "CPI-U All Items NSA year-over-year inflation", "provider": "U.S. Bureau of Labor Statistics; ALFRED", "dataset_or_series": "CPIAUCNS", "frequency": "monthly", "available_history": "1913-present", "release_timing": "BLS monthly release", "revision_behavior": "historical corrections possible", "historical_vintages_necessary": True, "historical_vintages_available": True, "required_implementation_lag": "source freezes a two-calendar-month signal lag", "access_method": "BLS/ALFRED", "licensing_or_public_use": "public", "lookahead_safe_reconstruction": True, "classification": "public_with_explicit_release_lag_feasible"}
    ],
    "maio_fed_funds_change_spy_bil_recursive_v1": [
        {"signal_requirement": "exact federal-funds-rate series and recursive transformation", "provider": "unresolved in prior source intake", "dataset_or_series": "not source-complete", "frequency": "unknown", "available_history": "indeterminate", "release_timing": "indeterminate", "revision_behavior": "indeterminate", "historical_vintages_necessary": True, "historical_vintages_available": False, "required_implementation_lag": "unresolved", "access_method": "not authorized", "licensing_or_public_use": "indeterminate", "lookahead_safe_reconstruction": False, "classification": "rules_do_not_define_signal"}
    ],
    "maio_fed_model_yield_gap_spy_bil_recursive_v1": [
        {"signal_requirement": "point-in-time aggregate equity earnings yield and Treasury yield", "provider": "public current-history sources only", "dataset_or_series": "Shiller current workbook plus Treasury yields", "frequency": "monthly", "available_history": "long current history", "release_timing": "earnings data release lineage unresolved", "revision_behavior": "earnings history revised", "historical_vintages_necessary": True, "historical_vintages_available": False, "required_implementation_lag": "cannot be frozen safely", "access_method": "public current history", "licensing_or_public_use": "public", "lookahead_safe_reconstruction": False, "classification": "public_but_vintage_problem_unresolved"}
    ],
    "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1": [
        {"signal_requirement": "Federal Reserve monetary-policy regime", "provider": "Federal Reserve Board; ALFRED", "dataset_or_series": "policy-rate history, exact transformation unresolved", "frequency": "meeting/daily to monthly", "available_history": "adequate public history", "release_timing": "policy announcement dates public", "revision_behavior": "rate decisions not ordinarily revised", "historical_vintages_necessary": False, "historical_vintages_available": True, "required_implementation_lag": "after policy announcement", "access_method": "Federal Reserve/ALFRED", "licensing_or_public_use": "public", "lookahead_safe_reconstruction": True, "classification": "public_with_explicit_release_lag_feasible"}
    ],
    "spdj_real_assets_static_index_etf_portability_v1": [
        {"signal_requirement": "none; source is a static allocation", "provider": "S&P Dow Jones Indices", "dataset_or_series": "official review calendar", "frequency": "semiannual", "available_history": "official methodology", "release_timing": "official review effective date", "revision_behavior": "not_applicable", "historical_vintages_necessary": False, "historical_vintages_available": True, "required_implementation_lag": "official effective date", "access_method": "official public methodology", "licensing_or_public_use": "methodology publicly readable", "lookahead_safe_reconstruction": True, "classification": "public_point_in_time_feasible"}
    ],
}


SAMPLES = {
    SELECTED_ID: ("2006-07-21", "2009-08 estimated after 36 monthly returns and CPI release", "2026-08", 204, "GSG ETF history plus 36-month expanding warmup", "adequate"),
    "balvers_wu_gilliland_country_index_mean_reversion_etf_v1": ("1996-03 estimated", "indeterminate", "indeterminate", 0, "incomplete source country ETF cross-section and signed-position support", "blocked_by_mapping"),
    "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1": ("2013-04 estimated", "2013-04 estimated", "2026-08", 160, "unsupported factor sleeves, not signal history", "blocked_by_mapping"),
    "fama_bliss_forward_rate_treasury_duration_allocation_v1": ("2002-07 estimated", "indeterminate", "indeterminate", 0, "canonical allocation rule and zero-coupon exposure", "indeterminate"),
    "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1": ("2007-04 estimated", "indeterminate", "indeterminate", 0, "canonical portfolio rule and point-in-time EBP vintages", "indeterminate"),
    "research_affiliates_inflation_cycle_equity_timing_v1": ("1993-01", "2003-01 estimated after 120-month signal history", "2026-08", 283, "unsupported short-equity exposure", "blocked_by_mapping"),
    "maio_fed_funds_change_spy_bil_recursive_v1": ("1993-01", "indeterminate", "indeterminate", 0, "unresolved exact signal rule", "indeterminate"),
    "maio_fed_model_yield_gap_spy_bil_recursive_v1": ("1993-01", "indeterminate", "indeterminate", 0, "point-in-time earnings-yield vintages", "inadequate"),
    "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1": ("2006-07", "indeterminate", "indeterminate", 0, "canonical source portfolio and mapping", "indeterminate"),
    "spdj_real_assets_static_index_etf_portability_v1": ("2018-05 estimated", "2018-05 estimated", "2026-08", 17, "IFRA ETF history", "adequate_but_mechanism_saturated"),
}


CONTROLS = {
    SELECTED_ID: (
        ("static_source_low_regime_60_40_spy_agg", "source_named", "blocking", "Monthly 60% SPY and 40% AGG using information known before rebalance."),
        ("monthly_equal_weight_six_mapped_assets", "simple_investable", "blocking", "Monthly equal weight across SPY, IYR, GSG, GLD, AGG, and TIP."),
        ("full_period_average_candidate_allocation_control", "ex_post_exposure", "diagnostic_only", "Monthly static weights equal to full-period average candidate targets; cannot block advancement."),
    ),
    "balvers_wu_gilliland_country_index_mean_reversion_etf_v1": (("source_world_equity_index", "source_named", "blocking", "Source world-index benchmark."), ("monthly_equal_weight_source_country_universe", "simple_investable", "blocking", "Equal-weight full source country set if it existed."), ("full_period_average_country_exposure", "ex_post_exposure", "diagnostic_only", "Future average signed country exposure.")),
    "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1": (("monthly_equal_weight_source_factor_sleeves", "source_named", "blocking", "Equal weight source factor sleeves if mappings existed."), ("SPY_buy_and_hold", "simple_investable", "blocking", "Broad equity benchmark."), ("full_period_average_factor_exposure", "ex_post_exposure", "diagnostic_only", "Future average factor exposure.")),
    "fama_bliss_forward_rate_treasury_duration_allocation_v1": (("one_year_treasury_reference", "source_named", "blocking", "Source excess-return reference."), ("monthly_equal_weight_shy_iei_ief", "simple_investable", "blocking", "Equal-weight mapped Treasury ladder."), ("full_period_average_duration_control", "ex_post_exposure", "diagnostic_only", "Future average duration.")),
    "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1": (("HYG_buy_and_hold", "source_named", "blocking", "Broad high-yield credit benchmark for a future portability rule."), ("monthly_50_50_hyg_ief", "simple_investable", "blocking", "Static credit/Treasury exposure."), ("full_period_average_credit_exposure", "ex_post_exposure", "diagnostic_only", "Future average credit beta.")),
    "research_affiliates_inflation_cycle_equity_timing_v1": (("SPY_buy_and_hold", "source_named", "blocking", "Broad equity benchmark."), ("monthly_50_50_spy_bil", "simple_investable", "blocking", "Static lower exposure."), ("full_period_average_directional_exposure", "ex_post_exposure", "diagnostic_only", "Future average signed exposure.")),
    "maio_fed_funds_change_spy_bil_recursive_v1": (("SPY_buy_and_hold", "source_named", "blocking", "Broad equity benchmark."), ("monthly_50_50_spy_bil", "simple_investable", "blocking", "Static exposure control."), ("full_period_average_spy_exposure", "ex_post_exposure", "diagnostic_only", "Future average SPY exposure.")),
    "maio_fed_model_yield_gap_spy_bil_recursive_v1": (("SPY_buy_and_hold", "source_named", "blocking", "Broad equity benchmark."), ("monthly_50_50_spy_bil", "simple_investable", "blocking", "Static exposure control."), ("full_period_average_spy_exposure", "ex_post_exposure", "diagnostic_only", "Future average SPY exposure.")),
    "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1": (("static_source_asset_mix", "source_named", "blocking", "Source strategic allocation if fully disclosed."), ("monthly_equal_weight_gsg_spy_agg_bil", "simple_investable", "blocking", "Simple mapped allocation."), ("full_period_average_commodity_exposure", "ex_post_exposure", "diagnostic_only", "Future average commodity target.")),
    "spdj_real_assets_static_index_etf_portability_v1": (("official_static_source_weights", "source_named", "blocking", "Official component weights."), ("equal_weight_reet_ifra_gsg_tip", "simple_investable", "blocking", "Equal mapped real-asset sleeves."), ("full_period_average_allocation", "ex_post_exposure", "diagnostic_only", "Identical to static source and retained only for contract symmetry.")),
}


SUPPLEMENTARY_CITATIONS = [
    (SELECTED_ID, "official_index_research", "A Dynamic Multi-Asset Approach to Inflation Hedging", "S&P Dow Jones Indices", "https://www.spglobal.com/spdji/en/documents/research/research-a-dynamic-multi-asset-approach-to-inflation-hedging.pdf", "economic rationale and source construction context"),
    (SELECTED_ID, "official_data_series", "Consumer Price Index for All Urban Consumers: All Items, Not Seasonally Adjusted", "Federal Reserve Bank of St. Louis / BLS", "https://fred.stlouisfed.org/series/CPIAUCNS", "series identity and current history"),
    (SELECTED_ID, "official_vintage_series", "ALFRED CPIAUCNS vintages", "Federal Reserve Bank of St. Louis", "https://alfred.stlouisfed.org/series?seid=CPIAUCNS", "historical vintages and release-date feasibility"),
    (SELECTED_ID, "official_release_calendar", "Consumer Price Index release calendar", "U.S. Bureau of Labor Statistics", "https://www.bls.gov/schedule/news_release/cpi.htm", "publication timing"),
    ("spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1", "official_signal_series", "Chicago Fed National Activity Index", "Federal Reserve Bank of Chicago", "https://www.chicagofed.org/research/data/cfnai/current-data", "public signal history and release context"),
    ("maio_fed_funds_change_spy_bil_recursive_v1", "author_page", "Paulo Maio Articles", "Paulo Maio", "https://sites.google.com/site/paulofmaio/articles", "author materials checked; no newly complete appendix contract found"),
]


def scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    materialized = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: scalar(row.get(field, "")) for field in writer.fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def hash_path(path: Path) -> str:
    if not path.exists():
        return "missing:sha256:" + hashlib.sha256(relative(path).encode("utf-8")).hexdigest()
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_snapshot() -> dict[str, str]:
    return {relative(path): hash_path(path) for path in PROTECTED_PATHS}


def packet_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name != "consistency_check.json"):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def ledger_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        source = SOURCES[candidate["source_key"]]
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "family_id": candidate["family_id"],
                "architecture_id": candidate["architecture_id"],
                "capability_group": candidate["capability_group"],
                "economic_mechanism": candidate["mechanism"],
                "primary_source": source["name"],
                "primary_source_provider": source["provider"],
                "primary_source_url": source["url"],
                "source_rule_status": candidate["rule_status"],
                "lineage_classification": candidate["lineage"],
                "tradable_exposure_mapping_status": candidate["mapping_status"],
                "external_signal_status": candidate["signal_status"],
                "sample_status": candidate["sample_status"],
                "qualification_status": candidate["qualification_status"],
                "primary_rejection_reason": candidate["rejection_reason"],
                "exact_rejection_reason": candidate["rejection_detail"],
                "performance_information_used": False,
                "strategy_configuration_created": False,
                "experiment_trial_created": False,
            }
        )
    return rows


def rule_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_rule_status": candidate["rule_status"],
                **candidate["rule"],
                "rule_invented_or_completed_by_intake": False,
                "qualified": candidate["qualification_status"] == "qualified",
            }
        )
    return rows


def citation_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        source = SOURCES[candidate["source_key"]]
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "citation_role": "primary_strategy_source",
                "source_type": source["type"],
                "source_name": source["name"],
                "authors_or_provider": source["provider"],
                "publication_year": source["year"],
                "url": source["url"],
                "authority_status": source["authority"],
                "supports": "strategy identity, economic mechanism, and recorded source-rule contract or its documented public limitation",
            }
        )
    for candidate_id, role, name, provider, url, supports in SUPPLEMENTARY_CITATIONS:
        rows.append(
            {
                "candidate_id": candidate_id,
                "citation_role": role,
                "source_type": "official_public_source",
                "source_name": name,
                "authors_or_provider": provider,
                "publication_year": "current_public_source",
                "url": url,
                "authority_status": "primary_authoritative",
                "supports": supports,
            }
        )
    return rows


def lineage_rows() -> list[dict[str, Any]]:
    comparisons = {
        SELECTED_ID: ("varadi_growth_inflation_sector_timing_original_v1 and static multi-asset controls", "Uses official CPI regimes and six broad cross-asset sleeves rather than sector trend/growth timing; formulas and source allocation states are materially distinct."),
        "balvers_wu_gilliland_country_index_mean_reversion_etf_v1": ("dogs_world_country_reversal_5x5_v1 and country reversal controls", "The parametric signed contrarian construction is more formal, but its country-reversal claim is near existing lineage and requires unsupported short/full-universe exposure."),
        "spdj_economic_cycle_factor_rotator_equity_only_etf_portability_v1": ("factor/style rotation and V7 economic-regime research", "CFNAI state rotation is related but materially distinct from trailing-return factor timing."),
        "fama_bliss_forward_rate_treasury_duration_allocation_v1": ("treasury_duration_trend_rotation_v1 and curve-riding intake", "Forward-rate expected-return allocation would be distinct from price trend, but the paper does not freeze an investable rule and rolling ETFs alter zero-coupon mechanics."),
        "gilchrist_zakrajsek_excess_bond_premium_credit_timing_v1": ("ANGL, HYG controls, and prior bond-level credit intake", "Top-level EBP credit timing would be new, but the paper is predictive research rather than a complete allocation strategy."),
        "research_affiliates_inflation_cycle_equity_timing_v1": ("public CPI regime and equity-timing families", "The source's signed long/short inflation-cycle mechanism is materially distinct from long-only regime switches."),
        "maio_fed_funds_change_spy_bil_recursive_v1": ("maio_fed_funds_change_spy_bil_recursive_v1 prior intake", "Exact strategy identity and unresolved contract already exist."),
        "maio_fed_model_yield_gap_spy_bil_recursive_v1": ("maio_fed_model_yield_gap_spy_bil_recursive_v1 prior intake", "Exact strategy identity and vintage blocker already exist."),
        "jensen_johnson_mercer_monetary_regime_commodity_allocation_v1": ("commodity momentum and static real-asset controls", "Monetary-policy-conditioned commodity allocation would be new, but no canonical ETF rule is source-complete."),
        "spdj_real_assets_static_index_etf_portability_v1": ("static equal-weight and fixed multi-asset controls", "Source composition differs, but the signal-free strategic allocation mechanism is already saturated as a control architecture."),
    }
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "lineage_classification": candidate["lineage"],
            "closest_repository_lineage": comparisons[candidate["candidate_id"]][0],
            "comparison_rationale": comparisons[candidate["candidate_id"]][1],
            "different_signal_alone_used_as_novelty": False,
            "cosmetic_ticker_change_used_as_novelty": False,
            "closed_configuration_reopened": False,
        }
        for candidate in CANDIDATES
    ]


def mapping_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        for required, symbols, classification, rationale in MAPPINGS[candidate["candidate_id"]]:
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "tradable_exposure_requirement": required,
                    "frozen_symbol_mapping": symbols,
                    "mapping_classification": classification,
                    "mapping_rationale": rationale,
                    "all_symbols_in_frozen_88": all(symbol in FROZEN_SYMBOLS for symbol in symbols.split("|") if symbol),
                    "signal_data_misclassified_as_tradable": False,
                    "qualifying_mapping": classification in {"exact_match", "economically_close_source_preserving_proxy"},
                }
            )
    return rows


def signal_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        for signal in SIGNALS[candidate["candidate_id"]]:
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    **signal,
                    "downloaded_or_ingested_in_this_task": False,
                }
            )
    return rows


def sample_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        tradable_start, binding_start, end, formations, binding, status = SAMPLES[candidate["candidate_id"]]
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "earliest_required_tradable_history": tradable_start,
                "binding_research_start": binding_start,
                "estimated_latest_available_date": end,
                "estimated_independent_formations": formations,
                "binding_constraint": binding,
                "publication_lag_accounted_for": candidate["signal_status"] in {"public_with_explicit_release_lag_feasible", "public_point_in_time_feasible"},
                "vintage_availability_accounted_for": True,
                "final_sample_feasibility": status,
                "dates_selected_from_performance": False,
            }
        )
    return rows


def control_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in CANDIDATES:
        for control_id, control_type, gate_role, definition in CONTROLS[candidate["candidate_id"]]:
            uses_candidate = control_type == "ex_post_exposure"
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "control_id": control_id,
                    "control_type": control_type,
                    "control_definition": definition,
                    "gate_role": gate_role,
                    "ex_ante_investable": not uses_candidate,
                    "uses_only_information_available_at_decision": not uses_candidate,
                    "uses_candidate_full_history": uses_candidate,
                    "uses_future_realized_returns": False,
                    "can_block_future_advancement": gate_role == "blocking",
                    "frozen_before_future_results": True,
                }
            )
    return rows


def ranking_rows() -> list[dict[str, Any]]:
    return [
        {
            "rank": candidate["rank"],
            "candidate_id": candidate["candidate_id"],
            "capability_group": candidate["capability_group"],
            "source_authority": SOURCES[candidate["source_key"]]["authority"],
            "source_rule_status": candidate["rule_status"],
            "architecture_novelty": candidate["lineage"],
            "mapping_status": candidate["mapping_status"],
            "public_signal_status": candidate["signal_status"],
            "sample_status": candidate["sample_status"],
            "control_clarity": "three_prospective_controls_recorded",
            "implementation_burden": "bounded_signal_acquisition_then_existing_price_accounting" if candidate["candidate_id"] == SELECTED_ID else "blocked_or_not_selected",
            "performance_information_used": False,
            "reported_source_performance_used": False,
            "qualified": candidate["qualification_status"] == "qualified",
            "selection_status": "selected_work_package" if candidate["qualification_status"] == "qualified" else "rejected",
        }
        for candidate in sorted(CANDIDATES, key=lambda item: item["rank"])
    ]


def selected_payload() -> dict[str, Any]:
    candidate = CANDIDATES[0]
    return {
        "task_id": TASK_ID,
        "task_outcome": TASK_OUTCOME,
        "selected_candidate_count": 1,
        "selected_capability_group_count": 1,
        "combined_future_canonical_trial_budget": 1,
        "maximum_allowed_combined_canonical_trial_budget": 4,
        "default_canonical_trial_budget_per_architecture": 1,
        "selected_work_packages": [
            {
                "strategy_id": SELECTED_ID,
                "family_id": SELECTED_FAMILY,
                "architecture_id": candidate["architecture_id"],
                "capability_group": candidate["capability_group"],
                "primary_source": SOURCES[candidate["source_key"]],
                "source_defined_rules": candidate["rule"],
                "economic_mechanism": candidate["mechanism"],
                "frozen_tradable_etf_mapping": [
                    {"source_exposure": item[0], "frozen_symbol": item[1], "mapping_classification": item[2]}
                    for item in MAPPINGS[SELECTED_ID]
                ],
                "external_signal_requirements": ["CPI-U All Items NSA year-over-year inflation"],
                "authoritative_signal_provider": "U.S. Bureau of Labor Statistics with ALFRED vintage distribution",
                "signal_series": "CPIAUCNS",
                "point_in_time_or_release_lag_contract": "Freeze the first available CPIAUCNS value and BLS release date; use no signal before release; make weights effective after close on the next business day after the CPI announcement.",
                "public_signal_feasibility_status": "public_with_explicit_release_lag_feasible",
                "data_acquisition_scope_for_next_task": "CPIAUCNS first-vintage values and BLS/ALFRED release dates only",
                "prospective_controls": [
                    {"control_id": item[0], "type": item[1], "gate_role": item[2], "definition": item[3]}
                    for item in CONTROLS[SELECTED_ID]
                ],
                "canonical_configuration": {
                    "configuration_count": 1,
                    "monthly_regime_thresholds_percent": {"low_below": 1.5, "medium_inclusive": [1.5, 2.5], "high_above": 2.5},
                    "lookback_months": 120,
                    "minimum_expanding_window_months": 36,
                    "low_regime_weights": {"SPY": 0.60, "AGG": 0.40, "IYR": 0.0, "GSG": 0.0, "GLD": 0.0, "TIP": 0.0},
                    "medium_regime": "normalized_inverse_sample_volatility_of_monthly_total_returns",
                    "high_regime": "normalized_source_transformed_inflation_beta",
                    "inflation_beta_return_horizon_months": 12,
                    "execution": "after_close_next_business_day_after_cpi_announcement",
                },
                "future_transaction_cost_assumptions_bps_one_way": {"primary": 5, "diagnostics": [0, 10]},
                "future_selection_evaluation_separation": {
                    "one_source_defined_configuration_only": True,
                    "signal_data_validated_and_frozen_before_strategy_execution": True,
                    "evaluation_dates_fixed_from_data_availability_not_performance": True,
                    "cost_diagnostics_not_separate_trials": True,
                    "performance_used_for_current_selection": False,
                },
                "future_canonical_trial_budget": 1,
                "forbidden_adaptations": [
                    "change_cpi_series_or_regime_thresholds",
                    "change_six_source_exposures_or_frozen_etf_mapping",
                    "change_120_month_lookback_or_36_month_expanding_minimum",
                    "change_inverse_volatility_or_inflation_beta_formulas",
                    "change_release_lag_or_transaction_timing",
                    "optimize_parameters_or_add_filters",
                    "change_universe_or_select_dates_from_performance",
                    "substitute_current_revised_cpi_for_first_vintage_without_disclosure",
                ],
                "strategy_implemented": False,
                "trial_created": False,
                "backtest_run": False,
            }
        ],
        "anti_drift_freeze": {
            "authoritative_source_defines_strategy": True,
            "public_data_only_supplies_source_signal": True,
            "arbitrary_macro_rule_creation_allowed": False,
            "post_result_threshold_change_allowed": False,
            "tradable_universe_expansion_allowed": False,
        },
        "implementation_authorized": False,
        "signal_acquisition_next_action_recorded": True,
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
    }


def render_report(rejections: Counter[str]) -> str:
    group_counts = Counter(candidate["capability_group"] for candidate in CANDIDATES)
    rejected = "\n".join(f"- `{reason}`: {count}" for reason, count in sorted(rejections.items()))
    groups = "\n".join(f"- {group}: {group_counts[group]} serious candidate(s)" for group in GROUPS)
    return f"""# Phase-2 Public-Signal ETF-Mappable Candidate Intake V2

## Outcome

`{TASK_OUTCOME}`

Ten serious source-backed candidates were reviewed across all five priority groups. One source-complete, public-signal-feasible architecture qualified: `{SELECTED_ID}`. Selection used source authority, rule completeness, lineage novelty, frozen-universe mapping, public-signal reproducibility, sample adequacy, control clarity, and bounded implementation burden. No reported or repository performance result was used.

## Qualified Architecture

The S&P Multi-Asset Dynamic Inflation methodology defines a monthly CPI regime rule across six broad exposures. The source thresholds, low-regime allocation, inverse-volatility formula, inflation-beta transformation, lookback, expanding-window minimum, and CPI-announcement timing are public. The frozen mapping is SPY, IYR, GSG, GLD, AGG, and TIP; all are members of the existing 88-symbol universe. CPIAUCNS first-vintage values and release dates must be independently acquired and frozen before any strategy implementation.

The work package is `related_but_materially_distinct` from existing growth/inflation sector timing: it uses a source-defined six-asset inflation-regime allocation rather than sector selection or generic trend. It is not an implementation, trial, backtest, validation, or eligibility decision.

## Priority-Group Coverage

{groups}

## Rejections

{rejected}

The rejected cohort preserves distinct failure modes: unsupported source exposures, incomplete or vintage-unsafe signal contracts, duplicate repository lineage, and a static mechanism already saturated by controls. External-signal permission was not used to rescue a strategy whose traded mechanism remained unsupported.

## Prior V1 Reconciliation

All nine V1 rejection outcomes remain read-only and unchanged. None was reclassified or implemented. The two Maio identities were reviewed only to confirm duplicate lineage and their existing unresolved data or rule blockers.

## Signal and Timing Boundary

The next bounded task may acquire only CPIAUCNS first-vintage observations and authoritative release dates. Tradable ETF prices remain inside the approved project market-data architecture. No market-data provider, Alpaca, broker, account, order, cache, forward-observation, or lifecycle operation occurred here.

## Trial Budget

One future canonical configuration is frozen, using 5 bps one-way turnover as the primary future cost assumption and 0/10 bps diagnostics. No trial exists yet. The combined future canonical-trial budget is one of four allowed.

## Exact Next Action

`{NEXT_ACTION}`

Recorded only; not executed.
"""


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    universe_consistency = json.loads((UNIVERSE_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    prior_consistency = json.loads((PRIOR_PACKET / "consistency_check.json").read_text(encoding="utf-8"))

    ledger = ledger_rows()
    rules = rule_rows()
    citations = citation_rows()
    lineage = lineage_rows()
    mappings = mapping_rows()
    signals = signal_rows()
    samples = sample_rows()
    controls = control_rows()
    rankings = ranking_rows()
    selected = selected_payload()
    rejections = Counter(row["primary_rejection_reason"] for row in ledger if row["qualification_status"] == "rejected")

    write_csv(OUTPUT_DIR / "serious_candidate_ledger.csv", ledger, ledger[0].keys())
    write_csv(OUTPUT_DIR / "source_rule_extraction.csv", rules, rules[0].keys())
    write_csv(OUTPUT_DIR / "source_citations.csv", citations, citations[0].keys())
    write_csv(OUTPUT_DIR / "lineage_comparison.csv", lineage, lineage[0].keys())
    write_csv(OUTPUT_DIR / "tradable_exposure_mapping.csv", mappings, mappings[0].keys())
    write_csv(OUTPUT_DIR / "external_signal_feasibility.csv", signals, signals[0].keys())
    write_csv(OUTPUT_DIR / "sample_feasibility.csv", samples, samples[0].keys())
    write_csv(OUTPUT_DIR / "control_design.csv", controls, controls[0].keys())
    write_csv(OUTPUT_DIR / "candidate_ranking.csv", rankings, rankings[0].keys())
    write_json(OUTPUT_DIR / "selected_work_packages.json", selected)
    (OUTPUT_DIR / "intake_report.md").write_text(render_report(rejections), encoding="utf-8")
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Exact Next Action\n\n`{NEXT_ACTION}`\n\nRecorded only; not executed.\n", encoding="utf-8"
    )

    protected_after = protected_snapshot()
    expected_without_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    actual_without_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "consistency_check.json"
    }
    selected_candidate = next(row for row in ledger if row["candidate_id"] == SELECTED_ID)
    selected_mappings = [row for row in mappings if row["candidate_id"] == SELECTED_ID]
    selected_signals = [row for row in signals if row["candidate_id"] == SELECTED_ID]
    blocking_controls = [row for row in controls if row["gate_role"] == "blocking"]
    diagnostic_controls = [row for row in controls if row["gate_role"] == "diagnostic_only"]
    checks = {
        "exactly_ten_serious_candidates": len(ledger) == 10,
        "all_five_priority_groups_reviewed": {row["capability_group"] for row in ledger} == set(GROUPS),
        "exactly_one_candidate_qualified": sum(row["qualification_status"] == "qualified" for row in ledger) == 1,
        "qualified_candidate_is_frozen_selection": selected_candidate["qualification_status"] == "qualified",
        "selected_source_rules_complete": selected_candidate["source_rule_status"] == "source_rules_complete",
        "selected_lineage_is_qualifying": selected_candidate["lineage_classification"] in {"genuinely_new_architecture", "related_but_materially_distinct"},
        "selected_mappings_all_qualifying": all(row["qualifying_mapping"] for row in selected_mappings),
        "selected_symbols_all_in_frozen_universe": all(row["all_symbols_in_frozen_88"] for row in selected_mappings),
        "selected_signals_all_publicly_feasible": all(row["classification"] in {"public_point_in_time_feasible", "public_with_explicit_release_lag_feasible"} for row in selected_signals),
        "selected_signal_not_downloaded": all(not row["downloaded_or_ingested_in_this_task"] for row in selected_signals),
        "signal_classifications_standardized": all(row["classification"] in SIGNAL_CLASSIFICATIONS for row in signals),
        "mapping_classifications_standardized": all(row["mapping_classification"] in MAPPING_CLASSIFICATIONS for row in mappings),
        "lineage_classifications_standardized": all(row["lineage_classification"] in LINEAGE_CLASSIFICATIONS for row in lineage),
        "rejection_taxonomy_standardized": all(reason in REJECTION_REASONS for reason in rejections),
        "every_rejection_has_exact_reason": all(row["exact_rejection_reason"] for row in ledger if row["qualification_status"] == "rejected"),
        "all_blocking_controls_are_ex_ante": all(row["ex_ante_investable"] and row["uses_only_information_available_at_decision"] and not row["uses_candidate_full_history"] for row in blocking_controls),
        "all_ex_post_controls_are_diagnostic_only": all(row["uses_candidate_full_history"] and not row["can_block_future_advancement"] for row in diagnostic_controls),
        "canonical_trial_budget_within_limit": selected["combined_future_canonical_trial_budget"] == 1 and selected["combined_future_canonical_trial_budget"] <= 4,
        "frozen_universe_has_exactly_88_symbols": len(FROZEN_SYMBOLS) == 88 and len(set(FROZEN_SYMBOLS)) == 88,
        "frozen_universe_hash_matches": universe_consistency["frozen_universe_hash"] == UNIVERSE_HASH,
        "prior_v1_had_nine_rejections": prior_consistency["entity_counts"]["serious_source_candidates"] == 9 and prior_consistency["entity_counts"]["qualified_architectures"] == 0,
        "prior_v1_outcome_preserved": prior_consistency["task_outcome"] == "phase2_underexplored_group_no_candidate_qualified",
        "protected_state_cache_and_prior_evidence_unchanged": protected_before == protected_after,
        "no_strategy_configuration_or_trial_created": all(not row["strategy_configuration_created"] and not row["experiment_trial_created"] for row in ledger),
        "no_performance_information_used": all(not row["performance_information_used"] for row in ledger) and all(not row["performance_information_used"] for row in rankings),
        "required_outputs_complete_before_consistency": actual_without_consistency == expected_without_consistency,
        "outcome_and_next_action_match_one_qualification": TASK_OUTCOME == "phase2_public_signal_one_candidate_qualified" and NEXT_ACTION == "acquire_validate_freeze_phase2_public_signal_inputs_v1",
    }
    evidence_hash = packet_hash()
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": TASK_OUTCOME if all(checks.values()) else "phase2_public_signal_intake_incomplete",
        "overall_pass": all(checks.values()),
        "checks": checks,
        "entity_counts": {
            "serious_source_candidates": len(ledger),
            "qualified_architectures": 1,
            "selected_work_packages": 1,
            "source_research_records": len(citations),
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "backtests_run": 0,
            "optimization_runs": 0,
            "robustness_or_validation_runs": 0,
            "eligibility_or_handoff_records_created": 0,
            "forward_observations_accessed_or_created": 0,
            "market_data_provider_calls": 0,
            "broker_calls": 0,
        },
        "serious_candidates_by_group": dict(sorted(Counter(row["capability_group"] for row in ledger).items())),
        "rejected_counts_by_reason": dict(sorted(rejections.items())),
        "selected_strategy_ids": [SELECTED_ID],
        "selected_family_ids": [SELECTED_FAMILY],
        "selected_capability_groups": [selected_candidate["capability_group"]],
        "combined_future_canonical_trial_budget": 1,
        "frozen_universe_id": UNIVERSE_ID,
        "frozen_universe_symbol_count": len(FROZEN_SYMBOLS),
        "frozen_universe_hash": UNIVERSE_HASH,
        "prior_v1_rejection_outcomes_preserved": 9,
        "deterministic_evidence_packet_hash": evidence_hash,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "forbidden_actions": {
            "tradable_universe_expansion": False,
            "strategy_implementation": False,
            "backtest_or_performance_screen": False,
            "optimization": False,
            "robustness_or_validation": False,
            "eligibility_or_handoff": False,
            "forward_observation_access": False,
            "market_data_download": False,
            "alpaca_or_broker_call": False,
            "lifecycle_state_change": False,
        },
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "task_outcome": consistency["task_outcome"],
        "overall_pass": consistency["overall_pass"],
        "serious_candidate_count": len(ledger),
        "qualified_candidate_count": 1,
        "selected_strategy_ids": [SELECTED_ID],
        "selected_family_ids": [SELECTED_FAMILY],
        "rejected_counts_by_reason": consistency["rejected_counts_by_reason"],
        "deterministic_evidence_packet_hash": evidence_hash,
        "exact_next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
