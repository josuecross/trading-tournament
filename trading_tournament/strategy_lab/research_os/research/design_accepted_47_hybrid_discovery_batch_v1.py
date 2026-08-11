from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yaml


TASK_ID = "design_accepted_47_hybrid_discovery_batch_v1"
MODE = "bounded-hybrid-experiment-design"
STAGE = "feasibility"
OUTCOME = "hybrid_batch_design_ready"
NEXT_ACTION = "accepted_47_hybrid_discovery_batch_v1"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "experiment_design" / TASK_ID / "latest"

ACCEPTED_UNIVERSE = (
    "SPY", "QQQ", "IWM", "DIA", "VTV", "SCHG", "QUAL", "USMV",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC",
    "EFA", "EEM", "URTH", "VGK", "VPL", "EWJ", "EWU", "EWG", "EWC", "EWA", "EWY", "INDA",
    "BIL", "SHY", "IEF", "TLT", "AGG", "TIP", "LQD", "HYG", "EMB", "MUB",
    "GLD", "SLV", "DBC", "DBA", "IYR", "XLRE", "IFRA",
)
GROUPS = (
    "us_broad_size_style_factors",
    "us_sectors_liquid_industries",
    "developed_emerging_regions_countries",
    "government_bonds_and_credit",
    "commodities_and_precious_metals",
    "real_estate_and_infrastructure",
)

PAIR_ARCHITECTURE = "accepted47_economic_pair_zscore_reversion_portfolio"
CORRELATION_ARCHITECTURE = "accepted47_cross_group_correlation_transition_top4"
VOLUME_ARCHITECTURE = "accepted47_directional_volume_pressure_breadth_state"

PAIR_UNIVERSE = ("IEF", "TLT", "LQD", "HYG", "GLD", "SLV", "IYR", "XLRE")
CORRELATION_UNIVERSE = ("SPY", "IWM", "EFA", "EEM", "IEF", "TLT", "LQD", "HYG", "GLD", "DBC", "IYR", "IFRA", "BIL")
CORRELATION_SELECTABLE = tuple(symbol for symbol in CORRELATION_UNIVERSE if symbol not in {"SPY", "BIL"})
VOLUME_RISK_BASKET = ("SPY", "IWM", "EFA", "EEM", "HYG", "DBC", "IYR", "IFRA")
VOLUME_DEFENSIVE_BASKET = ("BIL", "IEF", "TLT", "AGG")
VOLUME_UNIVERSE = VOLUME_RISK_BASKET + VOLUME_DEFENSIVE_BASKET

REQUIRED_OUTPUTS = {
    "design_manifest.yaml",
    "source_evidence_manifest.csv",
    "architecture_review.csv",
    "duplicate_feasibility_screen.csv",
    "selected_architecture_specifications.yaml",
    "configuration_trial_catalog.csv",
    "control_catalog.csv",
    "frozen_batch_spec.yaml",
    "rejection_ledger.csv",
    "conditional_codex_prompt.md",
    "process_task_log.csv",
    "protected_state_reconciliation.csv",
    "next_actions.csv",
    "consistency_check.json",
    "design_report.md",
}

SOURCE_PATHS = (
    Path("evidence/data_capability/activate_accepted_47_pilot_data_readiness_v1/latest"),
    Path("evidence/technical_factory/technical_strategy_factory_v1/latest"),
    Path("evidence/technical_factory/technical_strategy_factory_v2/latest"),
    Path("evidence/robustness/technical_factory_v1_trend_quality_diversifier_robustness_v1/latest"),
    Path("evidence/etf_pairs_distance_screen_v1/latest"),
    Path("evidence/data_capability/audit_long_short_relative_value_capability_v1/latest"),
    Path("evidence/strategy_family_coverage_and_next_discovery_v1/latest"),
    Path("evidence/trade_management/faa_psar_trade_management_overlay_batch_v1/latest"),
)

PROTECTED_PATHS = (
    Path("strategy_lab/strategy_registry.yaml"),
    Path("strategy_lab/RESEARCH_ROADMAP.md"),
    Path("strategy_lab/research_os/research/research_queue.yaml"),
    Path("strategy_lab/research_os/family_lineage/family_ledger.yaml"),
    Path("strategy_lab/research_os/operations/active_observations.yaml"),
    Path("data/cache"),
    Path("data/universe_expansion/pilot_etf_market_data_v1"),
    Path("paper_forward_observations"),
    Path("evidence/validation/faa_4m_top3_prospective_validation_v1/active"),
    Path("evidence/validation/repair_and_retry_decelerated_psar_prospective_activation_v1/latest"),
) + SOURCE_PATHS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def hash_target(relative: Path) -> str:
    target = ROOT / relative
    if not target.exists():
        return "missing"
    if target.is_file():
        return sha256_file(target)
    rows = [
        (path.relative_to(target).as_posix(), sha256_file(path))
        for path in sorted(item for item in target.rglob("*") if item.is_file())
    ]
    return stable_hash(rows)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in writer.fieldnames})


def write_yaml(path: Path, payload: Any) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pair_spec() -> dict[str, Any]:
    return {
        "architecture_id": PAIR_ARCHITECTURE,
        "family_id": "economically_grouped_long_only_pair_reversion",
        "display_name": "Economic Pair Z-Score Reversion Portfolio",
        "lineage_type": "internally_generated_economic_hypothesis",
        "source_or_research_lineage": "internally_generated_economic_hypothesis:accepted_47_frozen_group_metadata",
        "strategy_type": "long_only_multi_pair_relative_value_state_portfolio",
        "optimization_mode": "bounded_optimization",
        "route": "standalone_with_diversifier_diagnostic",
        "configuration_count": 4,
        "instrument_universe": list(PAIR_UNIVERSE),
        "economic_pairs": [
            {"pair_id": "treasury_maturity", "A": "IEF", "B": "TLT", "rationale": "same issuer and Treasury role with different duration"},
            {"pair_id": "corporate_credit_quality", "A": "LQD", "B": "HYG", "rationale": "US corporate credit with investment-grade versus high-yield risk"},
            {"pair_id": "precious_metals", "A": "GLD", "B": "SLV", "rationale": "physically backed precious-metal exposures"},
            {"pair_id": "listed_real_estate", "A": "IYR", "B": "XLRE", "rationale": "overlapping broad US listed-real-estate product roles"},
        ],
        "formula": {
            "pair_log_ratio": "x_t=ln(adjusted_close_A_t/adjusted_close_B_t)",
            "mean": "arithmetic mean of x over the inclusive trailing lookback_sessions",
            "standard_deviation": "sample standard deviation of x over the same window; ddof=1",
            "z_score": "z_t=(x_t-mean_t)/standard_deviation_t",
        },
        "state_machine": {
            "initial_and_warmup_state": "neutral",
            "neutral_to_A": "z_t<=-entry_z",
            "neutral_to_B": "z_t>=entry_z",
            "A_to_neutral": "z_t>=-exit_z",
            "B_to_neutral": "z_t<=exit_z",
            "otherwise": "retain prior pair state",
            "direct_A_to_B_or_B_to_A": False,
            "equality_behavior": "entry and exit inequalities are inclusive exactly as written",
        },
        "allocation": {
            "pair_sleeve_weight": 0.25,
            "A_state": "25% A and 0% B",
            "B_state": "0% A and 25% B",
            "neutral_state": "12.5% A and 12.5% B",
            "portfolio_rebalance": "at every valid month-end transition, restore all four sleeves to 25%; otherwise no trade",
            "maximum_single_asset_weight": 0.25,
        },
        "signal_frequency": "completed calendar month-end",
        "formation_interval": "inclusive trailing daily common sessions ending at completed month-end",
        "execution": "following regular common session close",
        "warmup": "use neutral pair states until all pairs have 252 common completed observations",
        "missing_data": "missing signal input retains that pair state; a missing required execution price blocks the complete target change and retains all pretrade holdings; no stale fill",
        "controls": {
            "primary_broad_benchmark": "SPY_buy_and_hold",
            "named_same_purpose_control": "economic_pair_zscore_momentum_mirror_control",
            "named_control_rule": "same pairs, z-scores, thresholds, hysteresis, weights and timing, but z>=entry_z holds A and z<=-entry_z holds B",
            "static_or_exposure_control": "monthly_equal_weight_eight_pair_assets_control",
            "no_filter_control": "monthly_equal_weight_eight_pair_assets_control",
        },
        "incremental_value_hypothesis": "economically constrained relative-price dislocations revert and add value beyond the momentum mirror and static ownership of the same eight assets",
        "concentration_hypothesis": "value is distributed across at least three pair sleeves rather than one maturity, credit, metal or real-estate episode",
        "principal_failure_risk": "structural ratio drift overwhelms mean reversion or one pair supplies nearly all gains",
        "common_history_constraint": "common pair-portfolio history starts 2015-10-08; first comparable 252-session month-end is 2016-10-31",
        "configuration_grid": {"lookback_sessions": [126, 252], "entry_z": [1.0, 1.5], "exit_z": [0.25], "varying_parameters": 2},
    }


def correlation_spec() -> dict[str, Any]:
    return {
        "architecture_id": CORRELATION_ARCHITECTURE,
        "family_id": "cross_group_correlation_transition",
        "display_name": "Cross-Group Correlation-Transition Top Four",
        "lineage_type": "internally_generated_cross_group_hypothesis",
        "source_or_research_lineage": "internally_generated_cross_group_hypothesis:accepted_47_structural_representatives",
        "strategy_type": "monthly_cross_group_correlation_change_selection",
        "optimization_mode": "bounded_optimization",
        "route": "standalone_with_diversifier_diagnostic",
        "configuration_count": 4,
        "instrument_universe": list(CORRELATION_UNIVERSE),
        "anchor": "SPY",
        "selectable_universe": list(CORRELATION_SELECTABLE),
        "selection_basis": "two structurally representative assets from US/international/real assets and four fixed-income roles; selected before performance",
        "formula": {
            "daily_return": "simple adjusted-close return",
            "short_correlation": "Pearson correlation of asset and SPY daily returns over short_window_sessions",
            "long_correlation": "Pearson correlation of asset and SPY daily returns over long_window_sessions",
            "score": "short_correlation-long_correlation",
            "ranking": "ascending score; most negative transition ranks first",
        },
        "selection_and_allocation": {
            "selected_count": 4,
            "weight_per_selected_asset": 0.25,
            "tie_break": "lexical ticker ascending",
            "unselected_weights": 0.0,
            "fallback": "BIL 100%",
        },
        "signal_frequency": "completed calendar month-end",
        "formation_interval": "inclusive trailing common daily returns ending at completed month-end",
        "execution": "following regular common session close",
        "rebalance_logic": "restore equal 25% weights at every valid month-end; allow natural drift between executions",
        "equality_behavior": "ties in score use lexical ticker order; no threshold equality exists",
        "warmup": "BIL until every selectable asset and SPY has long_window_sessions valid common returns; all configurations share the 252-session comparability start",
        "missing_data": "any invalid or nonfinite required correlation invalidates the complete formation and targets BIL; missing execution price blocks the trade and retains pretrade holdings; no stale fill",
        "controls": {
            "primary_broad_benchmark": "SPY_buy_and_hold",
            "named_same_purpose_control": "lowest_static_long_window_correlation_top4_control",
            "named_control_rule": "same selectable universe, long window, selected count, weights and timing; rank the long-window correlation level ascending and omit the short-minus-long transition",
            "static_or_exposure_control": "monthly_equal_weight_11_selectable_assets_control",
            "no_filter_control": "monthly_equal_weight_12_structural_assets_including_SPY_control",
        },
        "incremental_value_hypothesis": "assets becoming less equity-correlated add more incremental value than assets that merely have a low static correlation level",
        "concentration_hypothesis": "selection frequency and P&L are not dominated by one bond, commodity or real-estate instrument or one economic group",
        "principal_failure_risk": "noisy short-window correlations create turnover while the static-correlation control explains the allocation",
        "common_history_constraint": "common history starts 2018-04-05; first comparable 252-return month-end is 2019-04-30",
        "configuration_grid": {"short_window_sessions": [20, 60], "long_window_sessions": [126, 252], "selected_count": [4], "varying_parameters": 2},
    }


def volume_spec() -> dict[str, Any]:
    return {
        "architecture_id": VOLUME_ARCHITECTURE,
        "family_id": "multi_asset_directional_volume_breadth",
        "display_name": "Multi-Asset Directional-Volume Pressure State",
        "lineage_type": "internally_generated_technical_hypothesis",
        "source_or_research_lineage": "internally_generated_technical_hypothesis",
        "strategy_type": "weekly_cross_group_directional_volume_breadth_state",
        "optimization_mode": "bounded_optimization",
        "route": "standalone_with_diversifier_diagnostic",
        "instrument_universe": list(VOLUME_UNIVERSE),
        "risk_basket": list(VOLUME_RISK_BASKET),
        "defensive_basket": list(VOLUME_DEFENSIVE_BASKET),
        "configuration_count": 4,
        "formula": {
            "daily_return": "simple adjusted-close return for each risk-basket asset",
            "directional_volume_ratio": "sum(raw_volume_s where return_s<0)/sum(raw_volume_s where return_s!=0) over lookback_sessions",
            "zero_return_behavior": "zero-return sessions remain observed but their volume is excluded from numerator and denominator",
            "aggregate_pressure": "cross-sectional median of the eight valid directional_volume_ratio values",
        },
        "state_machine": {
            "risk_state": "aggregate_pressure<threshold",
            "defensive_state": "aggregate_pressure>threshold",
            "equality": "retain prior target",
            "initial_and_warmup_state": "defensive",
        },
        "allocation": {
            "risk_state": "12.5% in each of the eight risk-basket assets",
            "defensive_state": "25% in each of BIL, IEF, TLT and AGG",
            "rebalance": "trade only when state changes; no periodic reset while state is unchanged",
        },
        "signal_frequency": "final completed regular session of each week",
        "formation_interval": "inclusive trailing completed daily sessions ending at weekly formation close",
        "execution": "following regular common session close",
        "warmup": "defensive basket until all eight risk assets have lookback_sessions valid returns and nonnegative finite volume",
        "missing_data": "missing or nonfinite required price/volume or zero directional-volume denominator retains prior target; missing execution price blocks the complete transition and retains pretrade holdings; no stale fill",
        "controls": {
            "primary_broad_benchmark": "SPY_buy_and_hold",
            "named_same_purpose_control": "price_only_negative_session_breadth_state_control",
            "named_control_rule": "replace each directional-volume ratio with count(return<0)/count(return!=0); preserve lookback, cross-sectional median, threshold, baskets, state machine and timing",
            "static_or_exposure_control": "monthly_exposure_matched_risk_defensive_baskets_control",
            "exposure_rule": "risk-basket weight equals the candidate full-period average target risk-state weight; defensive basket receives the remainder; value is mechanically derived and not optimized",
            "no_filter_control": "monthly_50_50_risk_defensive_baskets_control",
        },
        "incremental_value_hypothesis": "cross-asset downside volume participation identifies defensive transitions not reproduced by negative-day counts or static risk exposure",
        "concentration_hypothesis": "the state result is not supplied by one risky asset, one defensive bond or one calendar episode",
        "principal_failure_risk": "unadjusted volume regime changes or ETF growth create a noisy state that the price-only control reproduces",
        "common_history_constraint": "common history starts 2018-04-05; first comparable 60-return weekly formation is 2018-06-29",
        "configuration_grid": {"lookback_sessions": [20, 60], "pressure_threshold": [0.50, 0.55], "varying_parameters": 2},
    }


def architecture_specs() -> list[dict[str, Any]]:
    return [pair_spec(), correlation_spec(), volume_spec()]


def configuration_catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pair_parameters = ((126, 1.0, "l126_e100"), (126, 1.5, "l126_e150"), (252, 1.0, "l252_e100"), (252, 1.5, "l252_e150"))
    for lookback, entry, code in pair_parameters:
        rows.append({
            "architecture_id": PAIR_ARCHITECTURE,
            "family_id": "economically_grouped_long_only_pair_reversion",
            "configuration_code": code,
            "strategy_id": f"accepted47_pair_reversion_{code}_v1",
            "trial_id": f"accepted_47_hybrid_v1__pair_{code}__canonical",
            "parameters": json.dumps({"lookback_sessions": lookback, "entry_z": entry, "exit_z": 0.25, "ddof": 1}, sort_keys=True, separators=(",", ":")),
            "source_or_research_lineage": "internally_generated_economic_hypothesis:accepted_47_frozen_group_metadata",
            "route": "standalone_with_diversifier_diagnostic",
            "optimization_mode": "bounded_optimization",
            "parent_trial_id": "",
            "adaptation_label": "",
        })
    correlation_parameters = ((20, 126, "s20_l126"), (20, 252, "s20_l252"), (60, 126, "s60_l126"), (60, 252, "s60_l252"))
    for short, long, code in correlation_parameters:
        rows.append({
            "architecture_id": CORRELATION_ARCHITECTURE,
            "family_id": "cross_group_correlation_transition",
            "configuration_code": code,
            "strategy_id": f"accepted47_corr_transition_{code}_top4_v1",
            "trial_id": f"accepted_47_hybrid_v1__corr_{code}__canonical",
            "parameters": json.dumps({"short_window_sessions": short, "long_window_sessions": long, "selected_count": 4}, sort_keys=True, separators=(",", ":")),
            "source_or_research_lineage": "internally_generated_cross_group_hypothesis:accepted_47_structural_representatives",
            "route": "standalone_with_diversifier_diagnostic",
            "optimization_mode": "bounded_optimization",
            "parent_trial_id": "",
            "adaptation_label": "",
        })
    volume_parameters = ((20, 0.50, "l20_t050"), (20, 0.55, "l20_t055"), (60, 0.50, "l60_t050"), (60, 0.55, "l60_t055"))
    for lookback, threshold, code in volume_parameters:
        rows.append({
            "architecture_id": VOLUME_ARCHITECTURE,
            "family_id": "multi_asset_directional_volume_breadth",
            "configuration_code": code,
            "strategy_id": f"accepted47_volume_pressure_{code}_v1",
            "trial_id": f"accepted_47_hybrid_v1__volume_{code}__canonical",
            "parameters": json.dumps({"lookback_sessions": lookback, "pressure_threshold": threshold}, sort_keys=True, separators=(",", ":")),
            "source_or_research_lineage": "internally_generated_technical_hypothesis",
            "route": "standalone_with_diversifier_diagnostic",
            "optimization_mode": "bounded_optimization",
            "parent_trial_id": "",
            "adaptation_label": "",
        })
    return rows


def controls() -> list[dict[str, Any]]:
    return [
        {"architecture_id": PAIR_ARCHITECTURE, "control_id": "SPY_buy_and_hold", "control_role": "primary_broad_benchmark", "rule": "100% SPY buy and hold on identical eligible dates", "parameterized_by_candidate": False},
        {"architecture_id": PAIR_ARCHITECTURE, "control_id": "economic_pair_zscore_momentum_mirror_control", "control_role": "named_same_purpose_control", "rule": "same pair z-score state machine but hold the rich leg at entry extremes", "parameterized_by_candidate": True},
        {"architecture_id": PAIR_ARCHITECTURE, "control_id": "monthly_equal_weight_eight_pair_assets_control", "control_role": "static_and_no_filter_control", "rule": "monthly 12.5% in each of IEF,TLT,LQD,HYG,GLD,SLV,IYR,XLRE", "parameterized_by_candidate": False},
        {"architecture_id": CORRELATION_ARCHITECTURE, "control_id": "SPY_buy_and_hold", "control_role": "primary_broad_benchmark", "rule": "100% SPY buy and hold on identical eligible dates", "parameterized_by_candidate": False},
        {"architecture_id": CORRELATION_ARCHITECTURE, "control_id": "lowest_static_long_window_correlation_top4_control", "control_role": "named_same_purpose_control", "rule": "rank long-window correlation to SPY ascending; same top four, weights and timing; omit transition", "parameterized_by_candidate": True},
        {"architecture_id": CORRELATION_ARCHITECTURE, "control_id": "monthly_equal_weight_11_selectable_assets_control", "control_role": "static_control", "rule": "monthly equal weight in the 11 selectable non-SPY, non-BIL assets", "parameterized_by_candidate": False},
        {"architecture_id": CORRELATION_ARCHITECTURE, "control_id": "monthly_equal_weight_12_structural_assets_including_SPY_control", "control_role": "no_filter_control", "rule": "monthly equal weight in SPY plus all 11 selectable assets", "parameterized_by_candidate": False},
        {"architecture_id": VOLUME_ARCHITECTURE, "control_id": "SPY_buy_and_hold", "control_role": "primary_broad_benchmark", "rule": "100% SPY buy and hold on identical eligible dates", "parameterized_by_candidate": False},
        {"architecture_id": VOLUME_ARCHITECTURE, "control_id": "price_only_negative_session_breadth_state_control", "control_role": "named_same_purpose_control", "rule": "replace volume-weighted downside participation with negative-session frequency; preserve all else", "parameterized_by_candidate": True},
        {"architecture_id": VOLUME_ARCHITECTURE, "control_id": "monthly_exposure_matched_risk_defensive_baskets_control", "control_role": "exposure_matched_control", "rule": "monthly fixed mix using mechanically observed full-period candidate risk-state target fraction", "parameterized_by_candidate": True},
        {"architecture_id": VOLUME_ARCHITECTURE, "control_id": "monthly_50_50_risk_defensive_baskets_control", "control_role": "static_no_filter_control", "rule": "monthly 50% equal-weight risk basket and 50% equal-weight defensive basket", "parameterized_by_candidate": False},
    ]


def architecture_reviews() -> list[dict[str, Any]]:
    return [
        {"architecture": PAIR_ARCHITECTURE, "lineage_type": "internal_economic", "family": "economically_grouped_long_only_pair_reversion", "instruments_or_groups": "Treasury maturity|credit quality|precious metals|listed real estate", "mechanism": "fixed-pair ratio z-score reversion with long-only leg rotation", "nearest_duplicate": "etf_pairs_distance_12m_6m_2sd_v1", "distinctive_component": "pairs fixed economically; no distance selection, short leg or formation-cycle spread; four equal sleeves", "controls": "momentum mirror|static equal weight|SPY", "configuration_count": 4, "route": "standalone_with_diversifier_diagnostic", "decision": "selected"},
        {"architecture": CORRELATION_ARCHITECTURE, "lineage_type": "internal_cross_group", "family": "cross_group_correlation_transition", "instruments_or_groups": "US|international|Treasury|credit|commodity|real assets", "mechanism": "rank change in SPY correlation rather than return", "nearest_duplicate": "FAA correlation rank and Factory V1 sector breadth", "distinctive_component": "cross-group short-minus-long correlation transition; no momentum score or breadth gate", "controls": "static-correlation top4|equal weight|SPY", "configuration_count": 4, "route": "standalone_with_diversifier_diagnostic", "decision": "selected"},
        {"architecture": VOLUME_ARCHITECTURE, "lineage_type": "internally_generated_technical_hypothesis", "family": "multi_asset_directional_volume_breadth", "instruments_or_groups": "US|international|credit|commodity|real assets|Treasuries", "mechanism": "cross-asset share of volume occurring on negative-return days", "nearest_duplicate": "Factory V1 SPY volume-confirmed breakout", "distinctive_component": "cross-group directional-volume breadth state with fixed risk/defensive baskets; no breakout", "controls": "price-only negative-day breadth|exposure match|50/50|SPY", "configuration_count": 4, "route": "standalone_with_diversifier_diagnostic", "decision": "selected"},
        {"architecture": "all47_raw_return_top5_rotation", "lineage_type": "internal", "family": "ordinary_cross_sectional_momentum", "instruments_or_groups": "all accepted groups", "mechanism": "ordinary trailing-return top five", "nearest_duplicate": "tested dual momentum, VAA/PAA, FAA and multiple top-N rotations", "distinctive_component": "only a larger universe", "controls": "not frozen", "configuration_count": 0, "route": "not_applicable", "decision": "rejected_not_economically_distinct"},
        {"architecture": "credit_ratio_drawdown_spy_bil_extension", "lineage_type": "internal", "family": "credit_risk_appetite_state", "instruments_or_groups": "HYG|IEF|SPY|BIL", "mechanism": "credit-ratio return and drawdown state", "nearest_duplicate": "factory_v2_credit_ratio_drawdown_state", "distinctive_component": "parameter-only extension", "controls": "not frozen", "configuration_count": 0, "route": "not_applicable", "decision": "rejected_already_tested"},
        {"architecture": "gatev_distance_pairs_short_spread_retest", "lineage_type": "source_derived", "family": "relative_value_or_spread_etf_pairs", "instruments_or_groups": "ETF pairs", "mechanism": "distance-selected long-short convergence spreads", "nearest_duplicate": "etf_pairs_distance_12m_6m_2sd_v1", "distinctive_component": "none sufficient", "controls": "not frozen", "configuration_count": 0, "route": "not_applicable", "decision": "rejected_capability_missing"},
        {"architecture": "single_asset_spy_volume_breakout_extension", "lineage_type": "internal", "family": "price_volume_breakout", "instruments_or_groups": "SPY|BIL", "mechanism": "breakout plus volume threshold", "nearest_duplicate": "factory_v1_spy_volume_confirmed_breakout", "distinctive_component": "parameter-only extension", "controls": "not frozen", "configuration_count": 0, "route": "not_applicable", "decision": "rejected_duplicate_or_redundant"},
    ]


def rejection_rows() -> list[dict[str, Any]]:
    return [
        {"architecture": "all47_raw_return_top5_rotation", "reason": "not_economically_distinct", "explanation": "universe breadth alone does not distinguish an ordinary top-N return rule from tested momentum and rotation families", "reconsideration_condition": "a non-return distinctive component and ablation control are independently frozen"},
        {"architecture": "credit_ratio_drawdown_spy_bil_extension", "reason": "already_tested", "explanation": "the exact HYG/IEF return-plus-drawdown SPY/BIL mechanism was closed in Factory V2", "reconsideration_condition": "a different economic claim, holdings lifecycle and control question are defined"},
        {"architecture": "gatev_distance_pairs_short_spread_retest", "reason": "capability_missing", "explanation": "the exact ETF distance screen is closed and production signed atomic pair accounting remains a material capability project", "reconsideration_condition": "long-short capability is separately implemented and a materially different source-aligned stock universe is frozen"},
        {"architecture": "single_asset_spy_volume_breakout_extension", "reason": "duplicate_or_redundant", "explanation": "changing breakout or volume thresholds would reopen the closed Factory V1 grid", "reconsideration_condition": "a non-breakout, multi-asset economic mechanism is specified"},
    ]


def frozen_batch_spec(specs: list[dict[str, Any]], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task_id": "accepted_47_hybrid_discovery_batch_v1",
        "mode": "fast-progress",
        "stage": "exploration",
        "source_design_task": TASK_ID,
        "operational_universe_id": "phase1_bounded_multi_asset_pilot",
        "data_endpoint": "2026-08-04",
        "provider_access_allowed": False,
        "accepted_membership": list(ACCEPTED_UNIVERSE),
        "excluded_symbols": ["EEMV", "EFAV"],
        "architecture_count": len(specs),
        "configuration_and_trial_count": len(catalog),
        "families": [spec["family_id"] for spec in specs],
        "costs": {"one_way_turnover_primary_bps": 5, "diagnostic_bps": [0, 10], "costs_are_not_trials": True},
        "accounting": {
            "signals": "completed sessions only",
            "execution": "following regular common session close",
            "one_way_turnover": "0.5*sum(abs(target_weight_i-pretrade_weight_i))",
            "holdings": "explicit",
            "drift": "natural between scheduled trades",
            "negative_weights": False,
            "leverage": False,
            "maximum_gross_exposure": 1.0,
            "maximum_daily_weight_sum": 1.0,
            "stale_execution_price_forward_fill": False,
        },
        "bounded_optimization": {
            "grid_frozen_before_performance": True,
            "post_result_expansion_allowed": False,
            "eligible_period": "first executable session after architecture maximum-grid warmup through 2026-08-04",
            "development_final_split": "floor(80% of eligible sessions) development; remaining 20% final exploratory segment",
            "anchored_folds": "split development sessions into five contiguous blocks using floor(k*N/5); four folds evaluate blocks 2-5 after state is run from the architecture anchor",
            "fold_pass": "positive 5-bps return, all invariants pass, and neither named nor static/exposure control dominates",
            "selection": "highest fold-pass count; then highest median Sharpe delta versus named control; then highest median absolute drawdown improvement; then lowest median turnover; then lexical strategy_id",
            "no_selection": "if no configuration passes at least two of four folds, close architecture without final evaluation",
            "final_segment": "evaluate only the frozen selected configuration; final segment is exploration, not validation",
        },
        "routes": {
            "frozen_route": "standalone_with_diversifier_diagnostic",
            "reference": "frozen_current_active_vm_dsr_usci_combo",
            "portfolio_diagnostics": [
                "100pct_frozen_reference",
                "80pct_reference_20pct_candidate",
                "80pct_reference_20pct_named_control",
                "80pct_reference_20pct_static_or_exposure_control",
            ],
            "outer_rebalance": "monthly completed month-end signal, following-session-close execution, explicit holdings and actual turnover",
            "portfolio_diagnostics_are_trials": False,
        },
        "exploration_gate": {
            "outcomes": ["exploratory_followup_candidate_standalone", "exploratory_followup_candidate_diversifier", "closed_exploration", "inconclusive_data_issue", "blocked_feasibility"],
            "requirements": [
                "selected final-segment return is positive at 5 bps",
                "all data, timing, numeric, exposure and weight invariants pass",
                "neither named nor static/exposure control dominates on CAGR, Sharpe and maximum drawdown",
                "versus each critical control, Sharpe improvement>=0.02 or absolute maximum-drawdown improvement>=0.01",
                "candidate is not worse on both Sharpe and drawdown versus each critical control in either deterministic chronological half",
                "at 10 bps the advantage versus each critical control is not unfavorable on both Sharpe and drawdown",
                "lightweight asset, group, year and episode concentration diagnostics pass",
            ],
            "failure_reasons": ["weak_vs_primary_control", "benchmark_like_behavior", "period_instability", "cost_drag", "turnover_drag", "signal_scarcity", "concentration_risk", "weak_return", "data_or_comparability_failure", "methodology_failure", "overfit_or_unstable"],
        },
        "concentration_diagnostics": {
            PAIR_ARCHITECTURE: "each pair absolute P&L contribution <=60% of total absolute pair contributions; largest positive calendar-year contribution <=60% of summed positive years",
            CORRELATION_ARCHITECTURE: "maximum selected-asset frequency <=60%; maximum target economic-group weight <=75%; largest positive calendar-year contribution <=60% of summed positive years",
            VOLUME_ARCHITECTURE: "each asset absolute P&L contribution <=40% of total absolute asset contributions; largest positive calendar-year contribution <=60% of summed positive years",
        },
        "next_actions": {
            "one_or_more_followups": "direction_owner_review_accepted_47_hybrid_discovery_batch_v1",
            "all_executable_close": "direction_owner_select_next_hybrid_discovery_direction_v1",
            "fewer_than_two_architectures_execute": "direction_owner_review_accepted_47_hybrid_execution_block_v1",
        },
        "prohibited": [
            "provider or network access", "symbol additions removals or substitutions", "Technical Factory V3",
            "post-result parameter expansion or retuning", "control promotion", "robustness or validation",
            "lifecycle or registry changes", "paper/demo activation", "broker account order position or real-money actions",
        ],
    }


def implementation_prompt(specs: list[dict[str, Any]], catalog: list[dict[str, Any]]) -> str:
    catalog_lines = "\n".join(
        f"- `{row['strategy_id']}` / `{row['trial_id']}` / `{row['architecture_id']}` / `{row['parameters']}` / route `{row['route']}`"
        for row in catalog
    )
    return f"""Act as a bounded hybrid quantitative exploration implementer, optimization-lineage auditor, control-first reviewer, and auditable evidence generator.

Perform one task only:

`accepted_47_hybrid_discovery_batch_v1`

## Mode and stage

- Mode: `fast-progress`
- Stage: `exploration`
- Design authority: `evidence/experiment_design/{TASK_ID}/latest`

Read and treat these files as frozen authority:

- `frozen_batch_spec.yaml`
- `selected_architecture_specifications.yaml`
- `configuration_trial_catalog.csv`
- `control_catalog.csv`
- `duplicate_feasibility_screen.csv`
- `consistency_check.json`

Do not make a strategic or material methodological choice. Reject execution if those artifacts do not reconcile to exactly three architectures, three families and twelve unique configurations/trials.

## Absolute boundary

This is exploration only. Use only the existing canonical caches under `data/universe_expansion/pilot_etf_market_data_v1`, ending `2026-08-04`. Do not access a provider or network. Do not add, remove or substitute symbols. EEMV and EFAV remain excluded. Do not launch Technical Factory V3, reopen a protected configuration, conduct source research, run robustness or validation, modify lifecycle/registry/observation state, activate paper/demo work, or call broker/account/order/position/transfer/real-money paths.

## Exact catalog

{catalog_lines}

Create exactly one `strategy_configuration` record and one canonical `experiment_trial` record for each row. Use blank `parent_trial_id` and blank `adaptation_label`. Preserve every configuration and failure. Controls are `benchmark_reference` records only; portfolio diagnostics, folds, reports, runners and tests are not strategies or trials.

## Architecture A: economic pair z-score reversion

Use pairs IEF/TLT, LQD/HYG, GLD/SLV and IYR/XLRE for the economic rationales in the frozen specification. Each pair is a 25% sleeve. At completed month-end compute `x=ln(A/B)`, its trailing mean and sample standard deviation (`ddof=1`), and `z=(x-mean)/sd`. Neutral enters A at `z<=-entry_z` and B at `z>=entry_z`; A exits to neutral at `z>=-0.25`; B exits to neutral at `z<=0.25`; otherwise retain state. Neutral is 12.5%/12.5%; active is 25%/0%. Rebalance all sleeves to 25% only on a valid pair-state transition. Execute following common-session close. Use the exact four lookback/entry rows in the catalog. Named control: identical z-score momentum mirror. Static control: monthly equal-weight eight assets. Broad benchmark: SPY buy-and-hold.

## Architecture B: cross-group correlation transition

Anchor SPY. Selectable universe is IWM, EFA, EEM, IEF, TLT, LQD, HYG, GLD, DBC, IYR and IFRA. At completed month-end calculate simple daily returns, short- and long-window Pearson correlations with SPY, and score `corr_short-corr_long`. Rank ascending, lexical ties, select four at 25% each, and execute following common-session close. Any invalid required correlation targets BIL. Use the exact four short/long rows in the catalog and a shared 252-return comparability start. Named control: rank the long-window correlation level ascending with everything else unchanged. Static control: monthly equal-weight eleven selectable assets. No-filter control: monthly equal-weight SPY plus the eleven selectable assets.

## Architecture C: directional-volume pressure breadth

Risk basket: SPY, IWM, EFA, EEM, HYG, DBC, IYR, IFRA. Defensive basket: BIL, IEF, TLT, AGG. On the final completed session of each week, for each risk asset calculate `sum(volume where return<0)/sum(volume where return!=0)` over the frozen lookback; zero-return volume enters neither numerator nor denominator. Aggregate by cross-sectional median. Risk state when median is below threshold, defensive when above, equality retains state. Risk state is 12.5% per risk asset; defensive is 25% per defensive asset. Trade only on state transitions at following common-session close. Use the exact four lookback/threshold rows. Named control: negative-session frequency with identical threshold, baskets and timing. Static control: monthly 50/50 risk/defensive baskets. Exposure control: monthly fixed mix using mechanically observed full-period candidate target risk-state fraction; do not optimize it.

## Bounded optimization and final segment

For each architecture use the maximum-grid warmup and identical dates for its four configurations and controls. Split eligible sessions at `floor(0.80*N)`: first 80% development, last 20% final exploratory evaluation. Split development into five contiguous blocks at `floor(k*N_dev/5)`. Run four anchored folds by evaluating blocks 2-5 after carrying state from the architecture anchor. A fold passes only with positive 5-bps return, all invariants, and no dominance by named or static/exposure controls. Select by highest pass count, then median Sharpe delta versus named control, then median absolute drawdown improvement, then lower median turnover, then lexical strategy ID. If no row passes at least two folds, close the architecture and do not evaluate its final segment. Freeze selection before opening final data. Evaluate only the frozen selected row on the final segment. Do not call the final segment validation or a clean holdout.

## Accounting, costs and routes

Use completed signals and following-session-close execution, explicit holdings, natural drift, explicit zero weights, and one-way turnover `0.5*sum(abs(target-pretrade))`. Charge costs once. Use 5 bps primary and 0/10 bps diagnostics; diagnostics are not trials. No negative weights, leverage, inverse products or stale execution-price forward fill. Maximum gross exposure and daily weight sum are 1.0.

Every configuration route is `standalone_with_diversifier_diagnostic`. With `frozen_current_active_vm_dsr_usci_combo`, construct 100% reference, 80/20 candidate, 80/20 named control and 80/20 static/exposure control using monthly outer rebalancing, following-session-close execution, explicit holdings, drift, inner plus outer turnover, and costs once. Never use a daily fixed-weight return blend. Do not promote a control.

## Required results and gates

For each configuration and control at 0, 5 and 10 bps report dates, total return, CAGR, annualized volatility, Sharpe, maximum drawdown, average risky exposure, turnover, rebalance count, cost drag, maximum single-asset weight, gross exposure, weight sum and all timing/numeric/exposure/weight invariants. At 5 bps report development, four anchored folds, selected final segment, full eligible period, and deterministic chronological halves. The halves and final segment are exploration only.

Retain signal and holdings diagnostics specific to each architecture. Run the exact concentration diagnostics in `frozen_batch_spec.yaml`; include unfavorable rows. A follow-up requires positive selected final return at 5 bps, all invariants, no named/static control dominance, materiality versus each critical control (`Sharpe>=0.02` or absolute drawdown improvement `>=0.01`), no both-metric failure in either chronological half, viability at 10 bps, and the frozen lightweight concentration limits. Use only the outcome and failure vocabularies in the frozen specification. Do not tune to escape closure.

## Required evidence packet

Write under `evidence/research_recovery/accepted_47_hybrid_discovery_batch_v1/latest`:

- `batch_manifest.yaml`
- `architecture_catalog.yaml`
- `strategy_cards.csv`
- `trial_ledger.csv`
- `benchmark_reference_log.csv`
- `process_task_log.csv`
- `data_preflight_reconciliation.csv`
- `walk_forward_folds.csv`
- `walk_forward_fold_results.csv`
- `selection_decisions.csv`
- `selected_configuration_freeze.csv`
- `all_configuration_results.csv`
- `final_evaluation_results.csv`
- `chronological_half_results.csv`
- `portfolio_contribution_results.csv`
- `pair_state_diagnostics.csv`
- `correlation_transition_diagnostics.csv`
- `directional_volume_breadth_diagnostics.csv`
- `turnover_cost_reconciliation.csv`
- `invariant_results.csv`
- `concentration_diagnostics.csv`
- `exploratory_followup_candidates.csv`
- `outcome_summary.csv`
- `failure_reasons.csv`
- `next_actions.csv`
- `cohort_funnel_counts.json`
- `consistency_check.json`
- `batch_report.md`

If at least one genuine follow-up exists, next action is `direction_owner_review_accepted_47_hybrid_discovery_batch_v1`. If all executable architectures close, use `direction_owner_select_next_hybrid_discovery_direction_v1`. If fewer than two architectures execute because of data or methodology blocks, use `direction_owner_review_accepted_47_hybrid_execution_block_v1`. Do not execute the next action.

Run only the dedicated serial runner, focused tests, Python compilation, `git diff --check`, and protected-state/cache/design-source reconciliation. No broad dashboards or lifecycle work.
"""


def report_text(reviews: list[dict[str, Any]], specs: list[dict[str, Any]], catalog: list[dict[str, Any]], rejections: list[dict[str, Any]]) -> str:
    review_table = "\n".join(
        f"| {row['architecture']} | {row['lineage_type']} | {row['family']} | {row['mechanism']} | {row['nearest_duplicate']} | {row['configuration_count']} | {row['route']} | {row['decision']} |"
        for row in reviews
    )
    config_table = "\n".join(
        f"| {row['strategy_id']} | {row['trial_id']} | {row['architecture_id']} | `{row['parameters']}` | {row['route']} |"
        for row in catalog
    )
    rejection_table = "\n".join(
        f"| {row['architecture']} | {row['reason']} | {row['explanation']} | {row['reconsideration_condition']} |"
        for row in rejections
    )
    architecture_sections = "\n\n".join(
        f"### {index}. {spec['display_name']}\n\n"
        f"- Identity: `{spec['architecture_id']}` / `{spec['family_id']}`.\n"
        f"- Lineage: `{spec['source_or_research_lineage']}`.\n"
        f"- Universe: `{','.join(spec['instrument_universe'])}`.\n"
        f"- Mode: `{spec['optimization_mode']}` with {spec['configuration_count']} frozen rows.\n"
        f"- Route: `{spec['route']}`.\n"
        f"- Incremental hypothesis: {spec['incremental_value_hypothesis']}\n"
        f"- Concentration hypothesis: {spec['concentration_hypothesis']}\n"
        f"- Principal risk: {spec['principal_failure_risk']}\n"
        f"- Common history: {spec['common_history_constraint']}\n"
        for index, spec in enumerate(specs, start=1)
    )
    return f"""# Accepted 47 Hybrid Discovery Batch V1 Design

## 1. Outcome

`{OUTCOME}`

| Measure | Count or status |
|---|---:|
| Architectures considered | {len(reviews)} |
| Architectures selected | {len(specs)} |
| Distinct families | {len({spec['family_id'] for spec in specs})} |
| Proposed configurations/trials | {len(catalog)} |
| Internally generated architectures | {len(specs)} |
| Source-derived architectures | 0 |
| Economic groups used | 6 |
| Provider requirements | 0 |

Exact next action: `{NEXT_ACTION}`.

## 2. Evidence-Driven Design Decision

- The selected mechanisms use Treasury, credit, international, commodity and real-asset instruments rather than another narrow SPY/sector threshold grid.
- None repeats Factory V1/V2: fixed economic pair reversion differs from distance-selected short spreads, correlation transition differs from momentum/breadth ranking, and directional-volume breadth differs from a SPY breakout confirmation.
- All three hypotheses are internally complete, so the batch does not depend on another source search or source-rule completion cycle.
- Each architecture has exactly four rows across two intrinsic parameters, deterministic anchored selection and no post-result expansion.
- The gate uses one final exploratory segment, halves and lightweight concentration diagnostics, while reserving rolling, bootstrap, robustness and prospective work for later stages.

## 3. Architecture Review

| Architecture | Lineage | Family | Mechanism | Nearest duplicate | Configurations | Route | Decision |
|---|---|---|---|---|---:|---|---|
{review_table}

## 4. Selected Architecture Specifications

{architecture_sections}

The complete formulas, pair rationales, state machines, weights, equality behavior, warmups, missing-data rules, controls, grids and outcome vocabularies are frozen in `selected_architecture_specifications.yaml` and `frozen_batch_spec.yaml`.

## 5. Exact Configuration And Trial Catalog

| Strategy ID | Trial ID | Architecture | Parameters | Route |
|---|---|---|---|---|
{config_table}

Count reconciliation: 4 pair + 4 correlation-transition + 4 directional-volume = **12** proposed strategy configurations and **12** proposed canonical trials. No strategy or trial record is created in this design task.

## 6. Frozen YAML

`selected_architecture_specifications.yaml` freezes complete architecture rules. `frozen_batch_spec.yaml` freezes the universe, cost/accounting contract, bounded optimization, routes, gates, concentration limits, prohibitions and later next actions. Codex has no remaining strategic or material methodological choice.

## 7. Rejection Ledger

| Architecture | Reason | Explanation | Reconsideration condition |
|---|---|---|---|
{rejection_table}

## 8. Conditional Codex Prompt

The batch satisfies the 3-architecture, 3-family and 12-trial conditions. Exactly one execution prompt is provided in `conditional_codex_prompt.md`. It authorizes only the frozen exploration batch and explicitly prohibits provider, robustness, lifecycle, observation and broker work.
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = {path.as_posix(): hash_target(path) for path in PROTECTED_PATHS}
    specs = architecture_specs()
    catalog = configuration_catalog()
    control_rows = controls()
    reviews = architecture_reviews()
    rejections = rejection_rows()
    batch = frozen_batch_spec(specs, catalog)

    source_rows = [
        {"path": path.as_posix(), "role": "design_evidence", "exists": (ROOT / path).exists(), "sha256": hash_target(path)}
        for path in SOURCE_PATHS
    ]
    write_yaml(OUTPUT_DIR / "design_manifest.yaml", {
        "task_id": TASK_ID, "mode": MODE, "stage": STAGE, "outcome": OUTCOME, "next_action": NEXT_ACTION,
        "architectures_considered": len(reviews), "architectures_selected": len(specs), "distinct_families": 3,
        "proposed_strategy_configurations": len(catalog), "proposed_experiment_trials": len(catalog),
        "strategy_records_created": 0, "trial_records_created": 0, "benchmark_records_created": 0,
        "internally_generated_architectures": 3, "source_derived_architectures": 0,
        "external_source_packages_reviewed": 0, "serious_external_candidates_reviewed": 0,
        "economic_groups_used": 6, "provider_requirements": 0,
        "provider_or_network_access": False, "data_modified": False, "performance_calculated": False,
        "backtest_run": False, "lifecycle_or_observation_change": False, "broker_or_real_money_action": False,
    })
    write_csv(OUTPUT_DIR / "source_evidence_manifest.csv", source_rows, source_rows[0].keys())
    write_csv(OUTPUT_DIR / "architecture_review.csv", reviews, reviews[0].keys())
    duplicate_rows = [
        {
            "architecture": row["architecture"], "nearest_completed_strategy": row["nearest_duplicate"],
            "nearest_prior_control": row["controls"], "exact_difference": row["distinctive_component"],
            "economically_meaningful_difference": row["decision"] == "selected",
            "required_symbols": next(("|".join(spec["instrument_universe"]) for spec in specs if spec["architecture_id"] == row["architecture"]), "not_applicable"),
            "common_history_constraint": next((spec["common_history_constraint"] for spec in specs if spec["architecture_id"] == row["architecture"]), "not_applicable"),
            "engine_capability": "supported_by_existing_long_only_explicit_holdings_backtester" if row["decision"] == "selected" else "not_required_or_blocked",
            "provider_requirement": "none",
            "decision": row["decision"],
        }
        for row in reviews
    ]
    write_csv(OUTPUT_DIR / "duplicate_feasibility_screen.csv", duplicate_rows, duplicate_rows[0].keys())
    write_yaml(OUTPUT_DIR / "selected_architecture_specifications.yaml", {"design_task": TASK_ID, "architectures": specs})
    write_csv(OUTPUT_DIR / "configuration_trial_catalog.csv", catalog, catalog[0].keys())
    write_csv(OUTPUT_DIR / "control_catalog.csv", control_rows, control_rows[0].keys())
    write_yaml(OUTPUT_DIR / "frozen_batch_spec.yaml", batch)
    write_csv(OUTPUT_DIR / "rejection_ledger.csv", rejections, rejections[0].keys())
    (OUTPUT_DIR / "conditional_codex_prompt.md").write_text(implementation_prompt(specs, catalog), encoding="utf-8")
    process_row = {"task_id": TASK_ID, "entity_type": "process_task", "mode": MODE, "stage": STAGE, "outcome": OUTCOME, "strategy_or_trial_record_created": False, "performance_calculated": False, "next_action": NEXT_ACTION}
    write_csv(OUTPUT_DIR / "process_task_log.csv", [process_row], process_row.keys())
    next_row = {"outcome": OUTCOME, "next_action": NEXT_ACTION, "next_action_executed": False}
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], next_row.keys())
    (OUTPUT_DIR / "design_report.md").write_text(report_text(reviews, specs, catalog, rejections), encoding="utf-8")

    protected_after = {path.as_posix(): hash_target(path) for path in PROTECTED_PATHS}
    protected_rows = [
        {"path": path, "sha256_before": before, "sha256_after": protected_after[path], "unchanged": before == protected_after[path]}
        for path, before in protected_before.items()
    ]
    write_csv(OUTPUT_DIR / "protected_state_reconciliation.csv", protected_rows, protected_rows[0].keys())
    unique_ids = len({row["strategy_id"] for row in catalog}) == len(catalog) and len({row["trial_id"] for row in catalog}) == len(catalog)
    architecture_counts = {architecture: sum(row["architecture_id"] == architecture for row in catalog) for architecture in {row["architecture_id"] for row in catalog}}
    prompt = (OUTPUT_DIR / "conditional_codex_prompt.md").read_text(encoding="utf-8")
    write_json(OUTPUT_DIR / "consistency_check.json", {})
    checks = {
        "outcome": OUTCOME,
        "architecture_count": len(specs), "distinct_family_count": len({spec["family_id"] for spec in specs}),
        "configuration_count": len(catalog), "trial_count": len(catalog), "unique_strategy_and_trial_ids": unique_ids,
        "maximum_configurations_per_architecture": max(architecture_counts.values()),
        "at_least_two_architectures_use_non_sector_non_SPY_instruments": sum(any(symbol not in {"SPY", "BIL", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"} for symbol in spec["instrument_universe"]) for spec in specs) >= 2,
        "bond_or_credit_architecture_present": any(any(symbol in {"IEF", "TLT", "LQD", "HYG", "AGG"} for symbol in spec["instrument_universe"]) for spec in specs),
        "international_commodity_real_asset_architecture_present": any(any(symbol in {"EFA", "EEM", "GLD", "SLV", "DBC", "IYR", "XLRE", "IFRA"} for symbol in spec["instrument_universe"]) for spec in specs),
        "internally_generated_technical_hypothesis_present": any(spec["source_or_research_lineage"] == "internally_generated_technical_hypothesis" for spec in specs),
        "economic_pair_lane_present": any(spec["architecture_id"] == PAIR_ARCHITECTURE for spec in specs),
        "broad_cross_group_lane_present": any(spec["architecture_id"] == CORRELATION_ARCHITECTURE for spec in specs),
        "twenty_percent_diversifier_diagnostic_present": all(spec["route"] == "standalone_with_diversifier_diagnostic" for spec in specs),
        "external_source_completion_required": False, "provider_requirement_count": 0,
        "accepted_membership_unchanged": len(ACCEPTED_UNIVERSE) == 47 and "EEMV" not in ACCEPTED_UNIVERSE and "EFAV" not in ACCEPTED_UNIVERSE,
        "strategy_records_created": 0, "trial_records_created": 0, "performance_calculated": False, "backtest_run": False,
        "conditional_prompt_count": 1, "conditional_prompt_names_exact_task": "`accepted_47_hybrid_discovery_batch_v1`" in prompt,
        "prompt_prohibits_provider_and_lifecycle_work": "Do not access a provider or network" in prompt and "modify lifecycle/registry/observation state" in prompt,
        "all_protected_state_unchanged": all(row["unchanged"] for row in protected_rows),
        "required_output_set_exact": {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()} == REQUIRED_OUTPUTS,
    }
    checks["overall_pass"] = bool(
        3 <= checks["architecture_count"] <= 4 and checks["distinct_family_count"] >= 3
        and 12 <= checks["configuration_count"] <= 20 and checks["maximum_configurations_per_architecture"] <= 8
        and unique_ids and checks["at_least_two_architectures_use_non_sector_non_SPY_instruments"]
        and checks["bond_or_credit_architecture_present"] and checks["international_commodity_real_asset_architecture_present"]
        and checks["economic_pair_lane_present"] and checks["broad_cross_group_lane_present"]
        and checks["internally_generated_technical_hypothesis_present"] and checks["all_protected_state_unchanged"]
        and checks["required_output_set_exact"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", checks)
    print(json.dumps({"task_id": TASK_ID, "outcome": OUTCOME, "architectures": len(specs), "configurations": len(catalog), "next_action": NEXT_ACTION, "overall_pass": checks["overall_pass"]}, indent=2, sort_keys=True))
    return 0 if checks["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
