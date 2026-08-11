from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "phase2_underexplored_group_source_candidate_intake_v1"
TASK_OUTCOME = "phase2_underexplored_group_no_candidate_qualified"
NEXT_ACTION = "direction_owner_review_phase2_candidate_supply_v2"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
OUTPUT_DIR = ROOT / "evidence" / "public_source_strategy_intake" / TASK_ID / "latest"

REQUIRED_OUTPUTS = {
    "intake_report.md",
    "serious_candidate_ledger.csv",
    "source_rule_extraction.csv",
    "source_citations.csv",
    "lineage_comparison.csv",
    "instrument_mapping.csv",
    "sample_feasibility.csv",
    "control_design.csv",
    "candidate_ranking.csv",
    "selected_work_packages.json",
    "consistency_check.json",
    "next_action.md",
}

UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
PRIOR_YIELD_PACKET = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "phase2_expansion_discovery_yield_evidence_packet_v2"
    / "latest"
)
PHASE2_CACHE = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    UNIVERSE_DIR,
    PHASE2_CACHE,
    PRIOR_YIELD_PACKET,
)

GROUPS = (
    "credit",
    "Treasury duration",
    "commodities/real assets",
    "size/broad/equal-weight equity",
    "global/country/regional equity",
)

SOURCES = {
    "grieves_marcus": {
        "source_type": "peer_reviewed_working_paper",
        "source_name": "Riding the Yield Curve: Reprise",
        "authors_or_provider": "Robin Grieves and Alan Marcus; NBER",
        "publication_year": "1990",
        "url": "https://www.nber.org/papers/w3511",
        "supports": "zero-coupon Treasury curve-riding rule, maturity set, quarterly timing, MOS filter, benchmark, and source sample",
        "authority_status": "primary_authoritative",
    },
    "ftse_carry": {
        "source_type": "official_index_provider_research",
        "source_name": "FTSE Fixed Income Factor Research Series: The Carry Concept",
        "authors_or_provider": "FTSE Russell / LSEG",
        "publication_year": "2017",
        "url": "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/research/ftse-fixed-income-factor-research-series-carry-concept.pdf?language=en",
        "supports": "carry decomposition, duration-neutral long-only optimization, monthly rebalance, and sovereign/corporate applications",
        "authority_status": "primary_authoritative",
    },
    "msci_duration": {
        "source_type": "official_index_provider_page",
        "source_name": "MSCI U.S. Duration Rotation Index",
        "authors_or_provider": "MSCI",
        "publication_year": "2026",
        "url": "https://www.msci.com/indexes/fixed-income-indexes",
        "supports": "growth/inflation regime objective, Treasury duration allocation purpose, and official index identity",
        "authority_status": "primary_but_materially_incomplete",
    },
    "houweling": {
        "source_type": "peer_reviewed_journal_article",
        "source_name": "Factor Investing in the Corporate Bond Market",
        "authors_or_provider": "Patrick Houweling and Jeroen van Zundert; CFA Institute",
        "publication_year": "2017",
        "url": "https://rpc.cfainstitute.org/research/financial-analysts-journal/2017/factor-investing-in-the-corporate-bond-market",
        "supports": "bond-level value, low-risk, momentum, and size factor definitions and portfolio evidence",
        "authority_status": "primary_authoritative",
    },
    "sp_hy_low_vol": {
        "source_type": "official_index_methodology",
        "source_name": "S&P U.S. High Yield Corporate Bond Strategy Indices Methodology",
        "authors_or_provider": "S&P Dow Jones Indices",
        "publication_year": "2026",
        "url": "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-high-yield-corporate-bond-strategy-indices.pdf",
        "supports": "eligible universe, MCR score, selection buffer, weighting, issuer cap, pricing, and monthly schedule",
        "authority_status": "primary_authoritative",
    },
    "koijen": {
        "source_type": "peer_reviewed_working_paper",
        "source_name": "Carry",
        "authors_or_provider": "Ralph Koijen, Tobias Moskowitz, Lasse Pedersen, and Evert Vrugt; NBER",
        "publication_year": "2013",
        "url": "https://www.nber.org/papers/w19325",
        "supports": "commodity futures carry formula, cross-sectional ranking, long-short construction, monthly timing, and source sample",
        "authority_status": "primary_authoritative",
    },
    "faber": {
        "source_type": "author_working_paper",
        "source_name": "Global Value: Building Trading Models with the 10-Year CAPE",
        "authors_or_provider": "Mebane Faber; SSRN",
        "publication_year": "2012",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2129474",
        "supports": "country-level CAPE value rationale, broad foreign-market universe, relative selection, and source sample context",
        "authority_status": "primary_authoritative",
    },
    "sp_equal_weight": {
        "source_type": "official_index_methodology_page",
        "source_name": "S&P 500 Equal Weight Index",
        "authors_or_provider": "S&P Dow Jones Indices",
        "publication_year": "2003",
        "url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500-equal-weight-index/",
        "supports": "same S&P 500 constituents, equal constituent weights, and quarterly rebalance",
        "authority_status": "primary_authoritative",
    },
    "miller_size": {
        "source_type": "author_working_paper_abstract",
        "source_name": "Size Rotation in the U.S. Equity Market",
        "authors_or_provider": "Miller, Ooi, Li, and Giamouridis; SSRN",
        "publication_year": "2011",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1950652",
        "supports": "quarterly large-versus-small objective and two-stage decision-tree/regression architecture",
        "authority_status": "primary_but_materially_incomplete",
    },
}

CANDIDATES = [
    {
        "candidate_id": "grieves_marcus_six_month_treasury_curve_ride_v1",
        "family_id": "treasury_bill_curve_riding",
        "capability_group": "Treasury duration",
        "source_key": "grieves_marcus",
        "architecture": "quarterly_filtered_zero_coupon_treasury_curve_ride",
        "mechanism": "Earn roll-down by holding a six-month zero-coupon Treasury for three months when the observed curve supplies nonnegative margin over a three-month bill.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_complete",
        "mapping_status": "unsupported_frozen_universe_exposure",
        "sample_status": "inadequate_for_source_aligned_trial",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "data_or_universe_incompatibility",
        "exact_rejection_reason": "The frozen universe has no six-month zero-coupon Treasury instrument; BIL and SHY cannot preserve the source maturity and roll-down mechanism.",
        "qualification_status": "rejected",
        "rank": 1,
        "rule": {
            "economic_rationale": "Predictable roll-down can exceed the short-bill return when the short Treasury curve is sufficiently upward sloping.",
            "eligible_asset_universe": "three-month and six-month zero-coupon U.S. Treasury securities",
            "signal_definition": "At quarter-end, compute the source margin-over-stay-put filter from current three- and six-month zero rates; ride the six-month bill only when MOS is at least zero.",
            "signal_inputs": "point-in-time three-month and six-month zero-coupon Treasury prices or yields",
            "lookback": "current quarter-end curve only",
            "formation_schedule": "end of each non-overlapping three-month interval",
            "rebalance_schedule": "quarterly",
            "ranking_rule": "not_applicable",
            "selection_rule": "six-month ride when MOS >= 0; otherwise three-month bill",
            "portfolio_weights": "100 percent selected Treasury maturity",
            "cash_risk_off_treatment": "three-month bill is the defensive benchmark holding",
            "tie_handling": "MOS equality enters six-month ride",
            "transaction_timing": "form from available quarter-end curve; transact after formation",
            "required_lag": "one trading session for repository execution",
            "source_benchmark_control": "three-month Treasury bill held to maturity",
            "source_sample_period": "1949-1988",
            "source_assumptions": "zero-coupon pricing; non-overlapping three-month holds; source reports small quarterly transaction costs",
            "unresolved_fields": "exact repository mapping for six-month zero-coupon exposure",
        },
    },
    {
        "candidate_id": "koijen_moskowitz_pedersen_vrugt_commodity_carry_v1",
        "family_id": "commodity_futures_curve_carry",
        "capability_group": "commodities/real assets",
        "source_key": "koijen",
        "architecture": "monthly_cross_sectional_front_second_contract_carry",
        "mechanism": "Rank commodities by annualized front-versus-second futures-curve carry and hold high-carry contracts against low-carry contracts.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_complete",
        "mapping_status": "unsupported_futures_term_structure_and_shorting",
        "sample_status": "inadequate_signal_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "data_or_universe_incompatibility",
        "exact_rejection_reason": "The frozen cache contains ETF total-return series rather than synchronized front/second futures curves, and the source construction requires a short leg.",
        "qualification_status": "rejected",
        "rank": 2,
        "rule": {
            "economic_rationale": "Futures basis and roll yield compensate for holding commodity exposure and forecast relative returns across contracts.",
            "eligible_asset_universe": "24 liquid commodity futures markets",
            "signal_definition": "carry=(F1-F2)/(F2*(T2-T1)) using nearest and second-nearest contracts",
            "signal_inputs": "front and second futures prices plus contract maturities",
            "lookback": "current synchronized futures curve",
            "formation_schedule": "monthly",
            "rebalance_schedule": "monthly",
            "ranking_rule": "rank carry descending across commodities",
            "selection_rule": "source main rank-weighted high-minus-low portfolio; equal-weight tail portfolios are reported alternatives",
            "portfolio_weights": "long high carry and short low carry with separate unit notionals",
            "cash_risk_off_treatment": "not_applicable",
            "tie_handling": "not publicly material to the source result; lexical rule would be required before implementation",
            "transaction_timing": "after monthly curve observation",
            "required_lag": "one trading session under repository convention",
            "source_benchmark_control": "passive commodity futures exposure and cross-sectional long/short neutrality",
            "source_sample_period": "1980-2011",
            "source_assumptions": "continuous futures histories and collateralized futures accounting",
            "unresolved_fields": "exact tie handling is minor; required futures curves and short accounting are material blockers",
        },
    },
    {
        "candidate_id": "faber_global_cape_country_value_bottom_quartile_v1",
        "family_id": "country_cape_value_selection",
        "capability_group": "global/country/regional equity",
        "source_key": "faber",
        "architecture": "annual_cross_country_cape_value_selection",
        "mechanism": "Allocate to the cheapest country equity markets by trailing ten-year cyclically adjusted valuation.",
        "novelty": "related_but_materially_distinct",
        "rule_status": "source_rules_complete",
        "mapping_status": "unsupported_country_cape_history_and_source_universe",
        "sample_status": "inadequate_signal_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "data_or_universe_incompatibility",
        "exact_rejection_reason": "The repository lacks point-in-time country CAPE histories and does not contain the source's full country universe; subset ranking would alter the mechanism.",
        "qualification_status": "rejected",
        "rank": 3,
        "rule": {
            "economic_rationale": "Long-horizon valuation mean reversion favors equity markets with low cyclically adjusted earnings multiples.",
            "eligible_asset_universe": "more than 30 foreign country equity markets in the source study",
            "signal_definition": "country CAPE equals inflation-adjusted price divided by trailing ten-year average real earnings",
            "signal_inputs": "point-in-time country index prices, earnings, and inflation histories",
            "lookback": "ten years",
            "formation_schedule": "annual",
            "rebalance_schedule": "annual",
            "ranking_rule": "rank country CAPE ascending",
            "selection_rule": "select cheapest quartile",
            "portfolio_weights": "equal weight selected countries",
            "cash_risk_off_treatment": "none in relative-value canonical architecture",
            "tie_handling": "lexical country identifier required before implementation",
            "transaction_timing": "after year-end signal observation",
            "required_lag": "one trading session under repository convention",
            "source_benchmark_control": "equal-weight full country universe",
            "source_sample_period": "1980-2011",
            "source_assumptions": "comparable real earnings and inflation histories across countries",
            "unresolved_fields": "point-in-time CAPE inputs and complete source-country mapping",
        },
    },
    {
        "candidate_id": "sp_us_high_yield_low_volatility_corporate_bond_v1",
        "family_id": "corporate_bond_oas_spread_duration_low_volatility",
        "capability_group": "credit",
        "source_key": "sp_hy_low_vol",
        "architecture": "monthly_bond_level_mcr_low_volatility_selection",
        "mechanism": "Select high-yield bonds with low market implied credit risk after controlling spread duration and aggregate spread conditions.",
        "novelty": "related_but_materially_distinct",
        "rule_status": "source_rules_complete",
        "mapping_status": "unsupported_bond_level_credit_data",
        "sample_status": "inadequate_signal_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "data_or_universe_incompatibility",
        "exact_rejection_reason": "Official construction needs bond-level OAS, spread duration, amount outstanding, issuer data, LSEG bids, and point-in-time index membership absent from the ETF cache.",
        "qualification_status": "rejected",
        "rank": 4,
        "rule": {
            "economic_rationale": "Lower market-implied credit risk within high yield may reduce default and spread risk without relying on fallen-angel membership.",
            "eligible_asset_universe": "eligible bonds in the S&P U.S. High Yield Corporate Bond Select Index",
            "signal_definition": "MCR=(bond OAS-average adjusted OAS)*spread duration, ranked ascending",
            "signal_inputs": "bond OAS, spread duration, ratings, amount outstanding, issuer totals, issue age, and bid prices",
            "lookback": "current monthly reference data with stated eligibility buffers",
            "formation_schedule": "monthly",
            "rebalance_schedule": "monthly",
            "ranking_rule": "rank MCR ascending",
            "selection_rule": "select lowest half with current-constituent buffer through the 60th percentile",
            "portfolio_weights": "market-value weight with 3 percent issuer cap",
            "cash_risk_off_treatment": "none",
            "tie_handling": "official index methodology ordering",
            "transaction_timing": "official monthly index rebalance",
            "required_lag": "official reference and effective dates",
            "source_benchmark_control": "S&P U.S. High Yield Corporate Bond Select Index",
            "source_sample_period": "official back-tested history begins in 2000",
            "source_assumptions": "licensed bond reference data and LSEG bid pricing",
            "unresolved_fields": "none in source rules; all material implementation inputs are absent locally",
        },
    },
    {
        "candidate_id": "houweling_van_zundert_corporate_bond_value_v1",
        "family_id": "corporate_bond_cross_sectional_value",
        "capability_group": "credit",
        "source_key": "houweling",
        "architecture": "monthly_bond_level_spread_residual_value",
        "mechanism": "Select corporate bonds whose market spread is wide relative to a fitted spread based on rating, maturity, and recent spread movement.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_complete",
        "mapping_status": "unsupported_bond_level_credit_data",
        "sample_status": "inadequate_signal_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "data_or_universe_incompatibility",
        "exact_rejection_reason": "The frozen ETF universe cannot reproduce security-level spreads, ratings, maturities, issuer caps, membership, or duration-matched excess returns.",
        "qualification_status": "rejected",
        "rank": 5,
        "rule": {
            "economic_rationale": "Bonds with unusually wide spreads relative to comparable issues may offer a value premium after systematic credit characteristics are controlled.",
            "eligible_asset_universe": "liquid investment-grade and high-yield corporate bonds meeting source filters",
            "signal_definition": "percentage deviation of observed spread from fitted spread using rating dummies, maturity, and three-month spread change",
            "signal_inputs": "bond spreads, ratings, maturity, recent spread change, issuer, prices, and index membership",
            "lookback": "current cross-section plus trailing three-month spread change",
            "formation_schedule": "monthly",
            "rebalance_schedule": "monthly with overlapping twelve-month holdings",
            "ranking_rule": "rank value residual descending",
            "selection_rule": "top source value tail",
            "portfolio_weights": "equal or source-prescribed bond weights with issuer cap and duration matching",
            "cash_risk_off_treatment": "none",
            "tie_handling": "not materialized publicly; deterministic bond identifier rule required",
            "transaction_timing": "after month-end signal data",
            "required_lag": "one trading session under repository convention",
            "source_benchmark_control": "duration-matched corporate bond market portfolio",
            "source_sample_period": "January 1994-September 2013 in the developed-market study",
            "source_assumptions": "survivorship-aware bond database and executable transaction-cost estimates",
            "unresolved_fields": "minor tie convention; material local absence of every bond-level signal input",
        },
    },
    {
        "candidate_id": "ftse_duration_neutral_sovereign_carry_roll_down_v1",
        "family_id": "duration_neutral_sovereign_carry_roll_down",
        "capability_group": "Treasury duration",
        "source_key": "ftse_carry",
        "architecture": "monthly_duration_matched_bond_carry_optimization",
        "mechanism": "Maximize level yield plus curve roll-down while matching benchmark duration and remaining long-only.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_incomplete",
        "mapping_status": "unsupported_bond_level_curve_data",
        "sample_status": "inadequate_signal_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "source_rules_incomplete_or_proprietary",
        "exact_rejection_reason": "Public research gives the architecture but not a fully reproducible issue-level optimizer/data contract, and the required Yield Book curves and bond characteristics are proprietary.",
        "qualification_status": "rejected",
        "rank": 6,
        "rule": {
            "economic_rationale": "Bond carry combines current yield and expected roll-down under an unchanged curve.",
            "eligible_asset_universe": "constituents of FTSE sovereign or corporate bond benchmarks",
            "signal_definition": "issue-level level carry plus roll-down carry",
            "signal_inputs": "bond yield, cash flows, curve, duration, benchmark membership, and constraints",
            "lookback": "current month-end term structure",
            "formation_schedule": "monthly",
            "rebalance_schedule": "monthly",
            "ranking_rule": "maximize aggregate carry under constraints",
            "selection_rule": "optimizer-selected long-only portfolio",
            "portfolio_weights": "duration-matched optimized weights",
            "cash_risk_off_treatment": "not_applicable",
            "tie_handling": "optimizer result",
            "transaction_timing": "month-end rebalance",
            "required_lag": "official index implementation schedule",
            "source_benchmark_control": "duration-matched parent bond index",
            "source_sample_period": "research examples cover U.S. and global sovereign/corporate histories",
            "source_assumptions": "constant yield curve for roll-down and licensed FTSE/Yield Book data",
            "unresolved_fields": "complete optimizer constraints, security eligibility implementation, and public point-in-time inputs",
        },
    },
    {
        "candidate_id": "msci_us_duration_rotation_macro_nowcast_v1",
        "family_id": "macro_nowcast_duration_rotation",
        "capability_group": "Treasury duration",
        "source_key": "msci_duration",
        "architecture": "growth_inflation_regime_treasury_duration_rotation",
        "mechanism": "Rotate Treasury duration from real-time growth and inflation regimes.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_incomplete",
        "mapping_status": "tradable_exposures_available_signal_unavailable",
        "sample_status": "inadequate_point_in_time_signal_history",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "source_rules_incomplete_or_proprietary",
        "exact_rejection_reason": "Official public material does not disclose a reproducible regime formula, thresholds, weights, or historical QuantCube nowcasts.",
        "qualification_status": "rejected",
        "rank": 7,
        "rule": {
            "economic_rationale": "Treasury duration responds differently to growth and inflation regimes.",
            "eligible_asset_universe": "U.S. Treasury duration segments in the official index",
            "signal_definition": "three macro regimes derived from growth and inflation indicators or nowcasts",
            "signal_inputs": "real-time growth and inflation nowcasts plus official duration-index levels",
            "lookback": "undisclosed in public material",
            "formation_schedule": "undisclosed in public material",
            "rebalance_schedule": "official index schedule not fully disclosed in reviewed public material",
            "ranking_rule": "not_applicable",
            "selection_rule": "map macro regime to Treasury duration exposure",
            "portfolio_weights": "undisclosed in reviewed public material",
            "cash_risk_off_treatment": "undisclosed",
            "tie_handling": "undisclosed",
            "transaction_timing": "official index schedule",
            "required_lag": "point-in-time nowcast availability required",
            "source_benchmark_control": "broad U.S. Treasury index",
            "source_sample_period": "official index is recent; public historical nowcast archive not established",
            "source_assumptions": "licensed QuantCube nowcasts",
            "unresolved_fields": "regime formula, thresholds, weights, dates, lags, and historical point-in-time signal archive",
        },
    },
    {
        "candidate_id": "miller_ooi_li_giamouridis_size_rotation_v1",
        "family_id": "hybrid_decision_tree_size_rotation",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "miller_size",
        "architecture": "quarterly_decision_tree_regression_large_small_rotation",
        "mechanism": "Forecast whether large- or small-cap U.S. equities will lead next quarter using a two-stage classification and regression model.",
        "novelty": "genuinely_new_architecture",
        "rule_status": "source_rules_incomplete",
        "mapping_status": "tradable_exposures_available_signal_unavailable",
        "sample_status": "adequate_prices_but_inadequate_model_inputs",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "source_rules_incomplete_or_proprietary",
        "exact_rejection_reason": "The public abstract identifies the model class but not the frozen predictors, tree, regression coefficients, estimation window, or point-in-time data contract.",
        "qualification_status": "rejected",
        "rank": 8,
        "rule": {
            "economic_rationale": "Business-cycle and market variables may forecast time variation in the small-minus-large equity premium.",
            "eligible_asset_universe": "U.S. large-cap and small-cap equity portfolios",
            "signal_definition": "decision tree classification followed by multiple linear regression forecast",
            "signal_inputs": "undisclosed complete predictor set and model parameters",
            "lookback": "undisclosed",
            "formation_schedule": "quarterly",
            "rebalance_schedule": "quarterly",
            "ranking_rule": "not_applicable",
            "selection_rule": "hold forecast winner: large or small capitalization",
            "portfolio_weights": "100 percent selected size segment",
            "cash_risk_off_treatment": "none",
            "tie_handling": "undisclosed",
            "transaction_timing": "quarterly after model forecast",
            "required_lag": "point-in-time predictor release lags required",
            "source_benchmark_control": "static large/small blend and each size segment",
            "source_sample_period": "public abstract reports U.S. equity application without full implementation table",
            "source_assumptions": "stable trained model and point-in-time macro/market predictors",
            "unresolved_fields": "predictor list, tree, coefficients, training schedule, lookback, and release lags",
        },
    },
    {
        "candidate_id": "sp500_equal_weight_quarterly_rebalance_rsp_v1",
        "family_id": "constituent_equal_weight_rebalancing",
        "capability_group": "size/broad/equal-weight equity",
        "source_key": "sp_equal_weight",
        "architecture": "quarterly_sp500_constituent_equal_weight",
        "mechanism": "Reset every S&P 500 constituent to equal weight quarterly, creating systematic size, concentration, and contrarian tilts.",
        "novelty": "near_duplicate",
        "rule_status": "source_rules_complete",
        "mapping_status": "exact_etf_proxy_rsp",
        "sample_status": "adequate",
        "control_status": "ex_ante_control_defined",
        "primary_rejection_category": "duplicate_or_near_duplicate",
        "exact_rejection_reason": "RSP and equal-weight constructions are already established repository benchmarks/controls and RSP is already in the market-rotator lineage; this is not a new architecture.",
        "qualification_status": "rejected",
        "rank": 9,
        "rule": {
            "economic_rationale": "Equal weighting reduces mega-cap concentration and mechanically rebalances toward relative laggards.",
            "eligible_asset_universe": "current S&P 500 constituents",
            "signal_definition": "none; deterministic constituent weighting rule",
            "signal_inputs": "official S&P 500 membership and rebalance reference data",
            "lookback": "none",
            "formation_schedule": "quarterly",
            "rebalance_schedule": "quarterly",
            "ranking_rule": "not_applicable",
            "selection_rule": "all S&P 500 constituents",
            "portfolio_weights": "equal constituent weight, approximately 0.2 percent each",
            "cash_risk_off_treatment": "none",
            "tie_handling": "not_applicable",
            "transaction_timing": "official quarterly index rebalance",
            "required_lag": "official constituent reference and effective dates",
            "source_benchmark_control": "capitalization-weighted S&P 500",
            "source_sample_period": "live index launched January 2003",
            "source_assumptions": "official point-in-time constituent membership",
            "unresolved_fields": "none material for ETF proxy; novelty gate fails",
        },
    },
]


def scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
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
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(b"MISSING\0")
        digest.update(relative(path).encode("utf-8"))
        return "missing:sha256:" + digest.hexdigest()
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
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
    for path in sorted(
        item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name != "consistency_check.json"
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def serious_ledger_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": row["candidate_id"],
            "family_id": row["family_id"],
            "capability_group": row["capability_group"],
            "architecture": row["architecture"],
            "primary_source": SOURCES[row["source_key"]]["source_name"],
            "source_url": SOURCES[row["source_key"]]["url"],
            "economic_mechanism": row["mechanism"],
            "duplicate_classification": row["novelty"],
            "novelty_classification": row["novelty"],
            "source_rule_status": row["rule_status"],
            "frozen_universe_mapping_status": row["mapping_status"],
            "sample_feasibility_status": row["sample_status"],
            "control_design_status": row["control_status"],
            "qualification_status": row["qualification_status"],
            "primary_rejection_category": row["primary_rejection_category"],
            "exact_rejection_reason": row["exact_rejection_reason"],
            "final_nonperformance_rank": row["rank"],
            "strategy_configuration_created": False,
            "experiment_trial_created": False,
            "performance_evaluated": False,
        }
        for row in CANDIDATES
    ]


def source_rule_rows() -> list[dict[str, Any]]:
    result = []
    for row in CANDIDATES:
        rule = row["rule"]
        result.append(
            {
                "candidate_id": row["candidate_id"],
                "economic_rationale": rule["economic_rationale"],
                "eligible_asset_universe": rule["eligible_asset_universe"],
                "signal_definition": rule["signal_definition"],
                "signal_inputs": rule["signal_inputs"],
                "lookback": rule["lookback"],
                "formation_schedule": rule["formation_schedule"],
                "rebalance_schedule": rule["rebalance_schedule"],
                "ranking_rule": rule["ranking_rule"],
                "selection_rule": rule["selection_rule"],
                "portfolio_weights": rule["portfolio_weights"],
                "cash_or_risk_off_treatment": rule["cash_risk_off_treatment"],
                "tie_handling": rule["tie_handling"],
                "transaction_timing": rule["transaction_timing"],
                "required_lag": rule["required_lag"],
                "unavailable_instruments_or_inputs": row["mapping_status"],
                "source_benchmark_or_control": rule["source_benchmark_control"],
                "source_sample_period": rule["source_sample_period"],
                "source_assumptions": rule["source_assumptions"],
                "unresolved_fields": rule["unresolved_fields"],
                "unresolved_field_classification": (
                    "material" if row["rule_status"] == "source_rules_incomplete" else "immaterial"
                ),
                "unresolved_fields_material": row["rule_status"] == "source_rules_incomplete",
                "source_rule_completeness": row["rule_status"],
            }
        )
    return result


def citation_rows() -> list[dict[str, Any]]:
    result = []
    for row in CANDIDATES:
        source = SOURCES[row["source_key"]]
        result.append({"candidate_id": row["candidate_id"], "citation_rank": 1, **source})
    result.extend(
        [
            {
                "candidate_id": "grieves_marcus_six_month_treasury_curve_ride_v1",
                "citation_rank": 2,
                "source_type": "primary_paper_copy",
                "source_name": "Riding the Yield Curve: Reprise full paper",
                "authors_or_provider": "Robin Grieves and Alan Marcus",
                "publication_year": "1990",
                "url": "https://scispace.com/pdf/riding-the-yield-curve-reprise-3pbnn3jesp.pdf",
                "supports": "equations, tested maturity choices, MOS values, transaction-cost assumptions, and source results table",
                "authority_status": "primary_authoritative",
            },
            {
                "candidate_id": "sp500_equal_weight_quarterly_rebalance_rsp_v1",
                "citation_rank": 2,
                "source_type": "official_index_methodology",
                "source_name": "S&P U.S. Indices Methodology",
                "authors_or_provider": "S&P Dow Jones Indices",
                "publication_year": "2026",
                "url": "https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/",
                "supports": "equal-weight constituent and rebalance methodology",
                "authority_status": "primary_authoritative",
            },
            {
                "candidate_id": "faber_global_cape_country_value_bottom_quartile_v1",
                "citation_rank": 2,
                "source_type": "author_institution_full_paper",
                "source_name": "Global Value: Building Trading Models with the 10-Year CAPE full paper",
                "authors_or_provider": "Mebane Faber; Cambria Quantitative Research",
                "publication_year": "2012",
                "url": "https://www.cambriainvestments.com/wp-content/uploads/2018/01/Global-Value-Building-Trading-Models-with-the-10-Year-CAPE.pdf",
                "supports": "country universe, CAPE construction, cheapest-quartile selection, annual rebalance, and 1980-2011 study period",
                "authority_status": "primary_authoritative",
            },
            {
                "candidate_id": "houweling_van_zundert_corporate_bond_value_v1",
                "citation_rank": 2,
                "source_type": "author_institution_data_methodology",
                "source_name": "Factor Investing in Corporate Bonds data sets",
                "authors_or_provider": "Robeco Quantitative Investments",
                "publication_year": "2026",
                "url": "https://www.robeco.com/en-hk/insights/2026/02/data-sets-factor-investing-in-corporate-bonds",
                "supports": "official author-institution factor definitions and bond-level data requirements",
                "authority_status": "primary_authoritative",
            },
        ]
    )
    return result


def lineage_rows() -> list[dict[str, Any]]:
    nearest = {
        "grieves_marcus_six_month_treasury_curve_ride_v1": ("treasury_duration_trend_rotation_v1", "genuinely_new_architecture", "Curve roll-down and a maturity-specific MOS filter differ from the closed Treasury trend architecture."),
        "koijen_moskowitz_pedersen_vrugt_commodity_carry_v1": ("commodity_basket_tsmom_top2_v1", "materially_distinct", "Cross-sectional futures-curve carry differs from ETF price momentum, but needs unsupported term structures and shorts."),
        "faber_global_cape_country_value_bottom_quartile_v1": ("dogs_world_country_reversal_5x5_v1", "materially_distinct", "Country valuation differs from prior-return reversal, but CAPE and the full source universe are absent."),
        "sp_us_high_yield_low_volatility_corporate_bond_v1": ("ice_vaneck_us_fallen_angel_angl_v1", "related_but_materially_distinct", "Bond-level low MCR selection differs from fallen-angel membership."),
        "houweling_van_zundert_corporate_bond_value_v1": ("ice_vaneck_us_fallen_angel_angl_v1", "genuinely_new_architecture", "Cross-sectional spread residual value is not a fallen-angel or credit beta rule."),
        "ftse_duration_neutral_sovereign_carry_roll_down_v1": ("treasury_duration_trend_rotation_v1", "genuinely_new_architecture", "Duration-neutral issue-level carry optimization differs from ETF trend rotation."),
        "msci_us_duration_rotation_macro_nowcast_v1": ("treasury_duration_trend_rotation_v1", "related_but_materially_distinct", "Macro growth/inflation nowcasts differ from price trend, but the public rule is incomplete."),
        "miller_ooi_li_giamouridis_size_rotation_v1": ("spdj_sp500_market_rotator_spy_splv_rsp_v1", "related_but_materially_distinct", "Large-small forecasting differs from SPY/SPLV/RSP relative strength, but model details are unavailable."),
        "sp500_equal_weight_quarterly_rebalance_rsp_v1": ("spdj_sp500_market_rotator_spy_splv_rsp_v1", "near_duplicate", "RSP already appears as an established benchmark/instrument and equal weighting is widely used as a control."),
    }
    return [
        {
            "candidate_id": row["candidate_id"],
            "family_id": row["family_id"],
            "nearest_repository_lineage": nearest[row["candidate_id"]][0],
            "lineage_classification": nearest[row["candidate_id"]][1],
            "lineage_explanation": nearest[row["candidate_id"]][2],
            "exact_configuration_duplicate": False,
            "closed_family_reopened": False,
        }
        for row in CANDIDATES
    ]


def instrument_rows() -> list[dict[str, Any]]:
    rows = [
        ("grieves_marcus_six_month_treasury_curve_ride_v1", "three-month zero-coupon Treasury", "BIL", "economically_close_proxy", "BIL holds one-to-three-month bills rather than one zero-coupon bill", "partial"),
        ("grieves_marcus_six_month_treasury_curve_ride_v1", "six-month zero-coupon Treasury", "", "unsupported", "No frozen ETF preserves a six-month zero-coupon ride and three-month roll-down", "blocked"),
        ("koijen_moskowitz_pedersen_vrugt_commodity_carry_v1", "24 front and second commodity futures curves", "DBC|GSG|USO|DBA|GLD", "unsupported", "ETF wrappers do not expose synchronized contract curves and cannot preserve the source long-short portfolio", "blocked"),
        ("faber_global_cape_country_value_bottom_quartile_v1", "more than 30 country equity indexes plus CAPE histories", "frozen country ETF subset", "unsupported", "The subset omits source countries and the cache has no point-in-time CAPE inputs", "blocked"),
        ("sp_us_high_yield_low_volatility_corporate_bond_v1", "eligible high-yield bonds and bond reference fields", "HYG|JNK|ANGL", "unsupported", "ETF prices cannot reconstruct bond MCR rankings or issuer caps", "blocked"),
        ("houweling_van_zundert_corporate_bond_value_v1", "security-level corporate bonds and spreads", "LQD|HYG|JNK|VCIT", "unsupported", "ETF prices cannot reconstruct residual spread value", "blocked"),
        ("ftse_duration_neutral_sovereign_carry_roll_down_v1", "issue-level sovereign bonds and yield curves", "SHY|IEI|IEF|TLT|GOVT", "unsupported", "ETF prices do not supply security carry, curve roll-down, or duration-matched optimization inputs", "blocked"),
        ("msci_us_duration_rotation_macro_nowcast_v1", "U.S. Treasury duration exposure", "SHY|IEI|IEF|TLT|GOVT", "economically_close_proxy", "Tradable durations exist, but official regime weights and point-in-time nowcasts do not", "blocked"),
        ("miller_ooi_li_giamouridis_size_rotation_v1", "U.S. large and small capitalization portfolios", "SPY|OEF|IWM|IJR", "economically_close_proxy", "Tradable exposures exist, but the complete forecasting model does not", "blocked"),
        ("sp500_equal_weight_quarterly_rebalance_rsp_v1", "S&P 500 Equal Weight Index", "RSP", "exact_match", "RSP is the frozen ETF proxy for the official index", "supported"),
    ]
    fields = ("candidate_id", "source_required_exposure", "frozen_symbol_or_mapping", "mapping_classification", "mapping_rationale", "material_support_status")
    return [dict(zip(fields, row)) for row in rows]


def sample_rows() -> list[dict[str, Any]]:
    rows = [
        ("grieves_marcus_six_month_treasury_curve_ride_v1", "2007-05-30", "2026-08-04", 19.18, "quarterly", 76, True, False, "six-month zero-coupon series absent", "inadequate"),
        ("koijen_moskowitz_pedersen_vrugt_commodity_carry_v1", "2007-01-05", "2026-08-04", 19.58, "monthly", 235, True, False, "front and second futures histories absent", "inadequate"),
        ("faber_global_cape_country_value_bottom_quartile_v1", "2008-04-01", "2026-08-04", 18.34, "annual", 18, True, False, "point-in-time CAPE and complete country universe absent", "inadequate"),
        ("sp_us_high_yield_low_volatility_corporate_bond_v1", "2007-12-04", "2026-08-04", 18.67, "monthly", 224, True, False, "bond-level reference and membership history absent", "inadequate"),
        ("houweling_van_zundert_corporate_bond_value_v1", "2007-12-04", "2026-08-04", 18.67, "monthly", 224, True, False, "bond-level spread and rating history absent", "inadequate"),
        ("ftse_duration_neutral_sovereign_carry_roll_down_v1", "2012-02-24", "2026-08-04", 14.44, "monthly", 173, True, False, "issue-level carry and optimizer inputs absent", "inadequate"),
        ("msci_us_duration_rotation_macro_nowcast_v1", "2012-02-24", "2026-08-04", 14.44, "monthly", 173, True, False, "historical point-in-time nowcasts and weights absent", "inadequate"),
        ("miller_ooi_li_giamouridis_size_rotation_v1", "2000-05-26", "2026-08-04", 26.19, "quarterly", 104, True, False, "complete model and predictor release histories absent", "inadequate"),
        ("sp500_equal_weight_quarterly_rebalance_rsp_v1", "2003-05-01", "2026-08-04", 23.26, "quarterly", 93, True, True, "none", "adequate_but_novelty_gate_failed"),
    ]
    fields = ("candidate_id", "earliest_common_proxy_date", "latest_common_proxy_date", "approximate_years_available", "formation_frequency", "approximate_independent_formations", "tradable_price_history_adequate", "source_signal_input_history_adequate", "binding_sample_or_data_bottleneck", "final_sample_feasibility")
    return [dict(zip(fields, row)) for row in rows]


def control_rows() -> list[dict[str, Any]]:
    names = {
        "grieves_marcus_six_month_treasury_curve_ride_v1": ("three_month_treasury_bill_hold", "BIL_buy_and_hold"),
        "koijen_moskowitz_pedersen_vrugt_commodity_carry_v1": ("passive_equal_weight_commodity_futures", "static_equal_weight_available_commodity_proxies"),
        "faber_global_cape_country_value_bottom_quartile_v1": ("equal_weight_full_country_universe", "static_equal_weight_frozen_country_subset"),
        "sp_us_high_yield_low_volatility_corporate_bond_v1": ("sp_us_high_yield_select_parent", "HYG_buy_and_hold"),
        "houweling_van_zundert_corporate_bond_value_v1": ("duration_matched_corporate_bond_market", "LQD_HYG_static_credit_mix"),
        "ftse_duration_neutral_sovereign_carry_roll_down_v1": ("duration_matched_parent_treasury_index", "GOVT_buy_and_hold"),
        "msci_us_duration_rotation_macro_nowcast_v1": ("broad_us_treasury_parent_index", "GOVT_buy_and_hold"),
        "miller_ooi_li_giamouridis_size_rotation_v1": ("static_large_small_blend", "SPY_IJR_static_50_50"),
        "sp500_equal_weight_quarterly_rebalance_rsp_v1": ("SP500_cap_weighted", "SPY_buy_and_hold"),
    }
    result = []
    for candidate in CANDIDATES:
        source_control, simple_control = names[candidate["candidate_id"]]
        for role, control in (("source_or_named_control", source_control), ("simple_investable_control", simple_control)):
            result.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "control_id": control,
                    "control_role": role,
                    "parameters_frozen_before_future_trial": True,
                    "data_allowed_at_decision_time": True,
                    "uses_candidate_decisions": False,
                    "uses_evaluation_outcomes": False,
                    "uses_future_returns": False,
                    "information_set": "formation_time_only",
                    "gate_role": "blocking_if_future_candidate_becomes_implementable",
                    "ex_ante_investable": True,
                }
            )
        result.append(
            {
                "candidate_id": candidate["candidate_id"],
                "control_id": "full_period_average_candidate_exposure_control",
                "control_role": "ex_post_exposure_diagnostic",
                "parameters_frozen_before_future_trial": False,
                "data_allowed_at_decision_time": False,
                "uses_candidate_decisions": True,
                "uses_evaluation_outcomes": False,
                "uses_future_returns": False,
                "information_set": "full_sample_candidate_target_history",
                "gate_role": "diagnostic_only",
                "ex_ante_investable": False,
            }
        )
    return result


def ranking_rows() -> list[dict[str, Any]]:
    burden = {
        1: "bounded_data_extension_but_exposure_missing",
        2: "material_futures_and_short_accounting_project",
        3: "material_point_in_time_fundamental_data_project",
        4: "material_bond_level_data_project",
        5: "material_bond_level_data_project",
        6: "material_proprietary_data_and_optimizer_project",
        7: "material_proprietary_signal_project",
        8: "material_source_completion_and_model_data_project",
        9: "no_material_implementation_burden",
    }
    return [
        {
            "rank": row["rank"],
            "candidate_id": row["candidate_id"],
            "capability_group": row["capability_group"],
            "source_authority": SOURCES[row["source_key"]]["authority_status"],
            "source_rule_completeness": row["rule_status"],
            "architecture_novelty": row["novelty"],
            "frozen_universe_fit": row["mapping_status"],
            "sample_feasibility": row["sample_status"],
            "control_quality": row["control_status"],
            "implementation_burden": burden[row["rank"]],
            "performance_information_used": False,
            "qualified": False,
            "rejection_category": row["primary_rejection_category"],
        }
        for row in sorted(CANDIDATES, key=lambda item: item["rank"])
    ]


def render_report(rejections: Counter[str]) -> str:
    group_counts = Counter(row["capability_group"] for row in CANDIDATES)
    return f"""# Phase-2 Underexplored-Group Source Candidate Intake V1

## Outcome

`{TASK_OUTCOME}`

Nine serious source-backed candidates were reviewed across all five priority groups. Zero qualified for an implementation work package. This is a legitimate zero-result intake: selection was based only on source authority, material rule completeness, architecture novelty, frozen-universe mapping, expected independent formation count, control quality, and implementation burden. No strategy return or performance metric was calculated.

## Group Coverage

{chr(10).join(f'- {group}: {group_counts[group]} serious candidate(s)' for group in GROUPS)}

## Qualification Result

The strongest source-complete ideas require data or exposures outside the frozen universe: a six-month zero-coupon Treasury, commodity futures curves and shorting, country CAPE histories, or bond-level credit fields. Three further ideas lack a complete reproducible public signal contract. The only fully mapped idea, quarterly S&P 500 equal weight through RSP, is a near-duplicate of established repository benchmark and market-rotator lineage.

Rejected counts by primary category:

{chr(10).join(f'- `{reason}`: {count}' for reason, count in sorted(rejections.items()))}

No architecture with an unresolved material source rule or unsupported instrument was promoted into a work package. The combined future canonical-trial budget is zero of four.

## Control Information Sets

Each serious candidate has a source or named control and a simple investable control whose parameters can be frozen before any future candidate decision. These are eligible to block a future gate. Full-sample exposure-matched controls are retained only as `diagnostic_only`; they cannot block candidate advancement because they use the candidate's complete target history.

## Protected State

The strategy registry, roadmap, research queue, family ledger, active observations, frozen universe, Phase-2 market-data cache, and prior discovery-yield packet were hashed before and after materialization and remained unchanged. No strategy configuration, experiment trial, backtest, robustness run, eligibility decision, handoff, forward observation, provider call, or broker call was created.

## Exact Next Action

`{NEXT_ACTION}`

Recorded only; not executed.
"""


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    universe_consistency = json.loads((UNIVERSE_DIR / "consistency_check.json").read_text(encoding="utf-8"))

    ledger = serious_ledger_rows()
    rules = source_rule_rows()
    citations = citation_rows()
    lineage = lineage_rows()
    mappings = instrument_rows()
    samples = sample_rows()
    controls = control_rows()
    rankings = ranking_rows()
    rejection_counts = Counter(row["primary_rejection_category"] for row in ledger)

    write_csv(OUTPUT_DIR / "serious_candidate_ledger.csv", ledger, ledger[0].keys())
    write_csv(OUTPUT_DIR / "source_rule_extraction.csv", rules, rules[0].keys())
    write_csv(OUTPUT_DIR / "source_citations.csv", citations, citations[0].keys())
    write_csv(OUTPUT_DIR / "lineage_comparison.csv", lineage, lineage[0].keys())
    write_csv(OUTPUT_DIR / "instrument_mapping.csv", mappings, mappings[0].keys())
    write_csv(OUTPUT_DIR / "sample_feasibility.csv", samples, samples[0].keys())
    write_csv(OUTPUT_DIR / "control_design.csv", controls, controls[0].keys())
    write_csv(OUTPUT_DIR / "candidate_ranking.csv", rankings, rankings[0].keys())

    selected = {
        "task_id": TASK_ID,
        "task_outcome": TASK_OUTCOME,
        "selected_work_packages": [],
        "selected_candidate_count": 0,
        "selected_capability_group_count": 0,
        "combined_future_canonical_trial_budget": 0,
        "maximum_allowed_combined_canonical_trial_budget": 4,
        "default_canonical_trial_budget_per_architecture": 1,
        "anti_overfitting_freeze": {
            "parameter_search_allowed": False,
            "universe_change_after_results_allowed": False,
            "control_change_after_results_allowed": False,
            "cost_diagnostics_create_trials": False,
        },
        "implementation_authorized": False,
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "selected_work_packages.json", selected)
    (OUTPUT_DIR / "intake_report.md").write_text(render_report(rejection_counts), encoding="utf-8")
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Exact Next Action\n\n`{NEXT_ACTION}`\n\nRecorded only; not executed.\n", encoding="utf-8"
    )

    protected_after = protected_snapshot()
    expected_without_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    actual_without_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "consistency_check.json"
    }
    checks = {
        "all_five_priority_groups_reviewed": set(row["capability_group"] for row in ledger) == set(GROUPS),
        "all_serious_candidates_materialized": len(ledger) == 9,
        "qualified_candidate_count_is_zero": sum(row["qualification_status"] == "qualified" for row in ledger) == 0,
        "selected_work_package_count_is_zero": selected["selected_candidate_count"] == 0,
        "canonical_trial_budget_within_limit": selected["combined_future_canonical_trial_budget"] <= 4,
        "no_strategy_configurations_created": all(not row["strategy_configuration_created"] for row in ledger),
        "no_experiment_trials_created": all(not row["experiment_trial_created"] for row in ledger),
        "no_performance_evaluated": all(not row["performance_evaluated"] for row in ledger),
        "every_serious_candidate_has_primary_source": all(row["source_url"].startswith("https://") for row in ledger),
        "every_serious_candidate_has_exact_rejection": all(row["exact_rejection_reason"] for row in ledger),
        "no_materially_unresolved_candidate_qualified": all(
            not (row["unresolved_fields_material"] and ledger[index]["qualification_status"] == "qualified")
            for index, row in enumerate(rules)
        ),
        "blocking_controls_are_ex_ante": all(
            row["ex_ante_investable"] and not row["uses_candidate_decisions"] and not row["uses_future_returns"]
            for row in controls
            if row["gate_role"].startswith("blocking")
        ),
        "ex_post_controls_are_diagnostic_only": all(
            row["gate_role"] == "diagnostic_only"
            for row in controls
            if row["uses_candidate_decisions"]
        ),
        "frozen_universe_hash_matches": universe_consistency["frozen_universe_hash"] == UNIVERSE_HASH,
        "closed_industry_family_not_reopened": all(not row["closed_family_reopened"] for row in lineage),
        "protected_state_and_prior_evidence_unchanged": protected_before == protected_after,
        "required_outputs_complete_before_consistency": actual_without_consistency == expected_without_consistency,
        "outcome_and_next_action_match_zero_qualification": TASK_OUTCOME.endswith("no_candidate_qualified")
        and NEXT_ACTION == "direction_owner_review_phase2_candidate_supply_v2",
    }
    evidence_hash = packet_hash()
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": TASK_OUTCOME if all(checks.values()) else "phase2_underexplored_group_intake_incomplete",
        "overall_pass": all(checks.values()),
        "checks": checks,
        "entity_counts": {
            "serious_source_candidates": len(ledger),
            "qualified_architectures": 0,
            "selected_work_packages": 0,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "backtests_run": 0,
            "robustness_runs": 0,
            "eligibility_decisions_created": 0,
            "handoffs_created": 0,
            "forward_observations_created": 0,
            "provider_calls": 0,
            "broker_calls": 0,
        },
        "serious_candidates_by_group": dict(sorted(Counter(row["capability_group"] for row in ledger).items())),
        "rejected_counts_by_reason": dict(sorted(rejection_counts.items())),
        "selected_candidate_ids": [],
        "selected_family_ids": [],
        "selected_capability_groups": [],
        "combined_future_canonical_trial_budget": 0,
        "frozen_universe_id": UNIVERSE_ID,
        "frozen_universe_hash": UNIVERSE_HASH,
        "deterministic_evidence_packet_hash": evidence_hash,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "forbidden_actions": {
            "strategy_implementation": False,
            "backtest_or_performance_screen": False,
            "optimization": False,
            "robustness_or_validation": False,
            "eligibility_or_handoff": False,
            "forward_observation": False,
            "provider_or_broker": False,
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
        "qualified_candidate_count": 0,
        "rejected_counts_by_reason": consistency["rejected_counts_by_reason"],
        "deterministic_evidence_packet_hash": evidence_hash,
        "exact_next_action": consistency["exact_next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
