from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "audit_and_standardize_role_aware_robustness_gates_v1"
MODE = "bounded-methodology-audit"
STAGE = "verification"
OUTPUT_DIR = ROOT / "evidence" / "methodology" / TASK_ID / "latest"

OUTCOME = "robustness_gate_standardization_required"
NEXT_ACTION = "direction_owner_review_role_aware_robustness_standard_v1"

EVIDENCE_NOT_AVAILABLE = "evidence_not_available"

REQUIRED_OUTPUTS = (
    "audit_manifest.yaml",
    "robustness_packet_inventory.csv",
    "strategy_role_classification.csv",
    "gate_definition_inventory.csv",
    "numeric_threshold_inventory.csv",
    "candidate_gate_reconciliation.csv",
    "repeated_failure_pattern.csv",
    "universal_gate_assessment.csv",
    "role_specific_gate_assessment.csv",
    "neutralization_gate_assessment.csv",
    "alternative_concentration_tests.csv",
    "consistency_and_fairness_assessment.csv",
    "potential_future_reassessment_inventory.csv",
    "proposed_role_aware_standard.md",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "methodology_audit_report.md",
)

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "evidence" / "cache",
    ROOT / "evidence" / "paper_demo_observation",
    ROOT / "evidence" / "validation" / "faa_4m_top3_prospective_validation_v1" / "active",
    ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "native_etf_v3_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "native_etf_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "kaufman_breakout_diversifier_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "resolve_kaufman_diversifier_concentration_risk_v1" / "latest",
    ROOT / "evidence" / "robustness" / "decelerated_psar_diversifier_final_robustness_v1" / "latest",
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_tree(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(item.read_bytes()).digest())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): sha256_tree(path) for path in PROTECTED_PATHS}


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "methodology" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"refusing to replace unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(name: str, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    columns: list[str] = list(fields or [])
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column, "")) for column in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, nested in value.items():
            if isinstance(nested, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.extend(yaml_lines(nested, indent + 2))
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(nested)}")
        return lines
    if isinstance(value, list):
        lines = []
        for nested in value:
            if isinstance(nested, (dict, list)):
                lines.append(f"{pad}-")
                lines.extend(yaml_lines(nested, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_scalar(nested)}")
        return lines
    return [f"{pad}{yaml_scalar(value)}"]


def write_yaml(name: str, payload: dict[str, Any]) -> None:
    (OUTPUT_DIR / name).write_text("\n".join(yaml_lines(payload)) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def find_row(path: Path, strategy_id: str) -> dict[str, str]:
    for row in read_csv_rows(path):
        if row.get("strategy_id") == strategy_id:
            return row
    raise RuntimeError(f"missing {strategy_id} in {rel(path)}")


def normalize_failure(row: dict[str, str]) -> str:
    return row.get("failure_reason") or row.get("primary_failure_reason") or ""


def packet(path: str, file: str = "outcome_summary.csv") -> str:
    return f"{path}/{file}"


STRATEGIES: list[dict[str, Any]] = [
    {
        "strategy_id": "varadi_minimum_correlation_8etf_60d_weekly_v1",
        "family_id": "minimum_correlation_dynamic_diversification",
        "architecture": "weekly_long_only_correlation_transformation_inverse_volatility_allocation",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "dynamic_multi_asset_allocation_strategy",
        "role_classification_basis": "weekly allocation across SPY, QQQ, EEM, IWM, EFA, TLT, IYR, GLD, and BIL",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_mixed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historically_promising_not_ready_for_paper_demo_eligibility",
        "decisive_gate": "neutralize_strongest_positive_calendar_year_static_average_control_dominates",
        "relevant_control": "mca8_static_average_weight_control",
        "concentration_unit": "year;asset;month",
        "concentrated_contribution_consistent_with_mechanism": "partly_consistent_with_defensive_bond_gold_allocation",
        "packet_path": packet("evidence/robustness/accepted_47_source_backed_v2_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v2/latest", "strategy_cards.csv"),
        "chronological_quarters": "pass",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": EVIDENCE_NOT_AVAILABLE,
        "cost_stress": "pass",
        "exposure_static_controls": "static_average_control_not_full_period_dominant_but_dominates_after_strongest_year_neutralization",
        "candidate_specific_concentration": "TLT strongest positive-excess asset 0.276347; TLT+GLD 0.436960; strongest year 0.595894 <= 0.60",
    },
    {
        "strategy_id": "schwoerer_hyg_ema100_spy_bil_v1",
        "family_id": "high_yield_credit_signal_equity_state",
        "architecture": "daily_cross_asset_credit_trend_equity_cash_state",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "defensive_equity_timing_strategy",
        "role_classification_basis": "HYG credit-trend signal gates SPY/BIL exposure",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_mixed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historically_promising_not_ready_for_paper_demo_eligibility",
        "decisive_gate": "three_month_and_year_neutralization_loses_materiality_vs_spy_ema100",
        "relevant_control": "spy_ema100_self_trend_spy_bil_control",
        "concentration_unit": "month;year;episode",
        "concentrated_contribution_consistent_with_mechanism": "yes_credit_state_defense_is_expected_to_cluster_in_stress_or_recovery_windows",
        "packet_path": packet("evidence/robustness/accepted_47_source_backed_v2_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v2/latest", "strategy_cards.csv"),
        "chronological_quarters": "pass",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": "pass_84_episodes_fraction_material_1.0",
        "cost_stress": "pass",
        "exposure_static_controls": "pass_exposure_matching_does_not_dominate",
        "candidate_specific_concentration": "single episode <= 0.60; single year <= 0.60; leave-one-episode-out survives",
    },
    {
        "strategy_id": "gestaltu_tactical_permanent_portfolio_7pct_v1",
        "family_id": "trend_filtered_risk_parity_volatility_target",
        "architecture": "monthly_three_asset_trend_inverse_volatility_cash_scaling",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "dynamic_multi_asset_allocation_strategy",
        "role_classification_basis": "trend-filtered risk-parity allocation across SPY, IEF, GLD, and BIL",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_mixed",
        "primary_failure_reason": "period_instability",
        "interpretation": "historically_promising_not_ready_for_paper_demo_eligibility",
        "decisive_gate": "quarters_rolling_and_one_strongest_year_neutralization_failure",
        "relevant_control": "tpp_same_trend_equal_weight_no_risk_sizing_control;tpp_static_average_weight_control;tpp_always_long_risk_parity_7pct_control",
        "concentration_unit": "month;year;asset",
        "concentrated_contribution_consistent_with_mechanism": "yes_trend_filtered_bond_gold_cash_behavior_is_central_but_period_instability_remains",
        "packet_path": packet("evidence/robustness/gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v1/latest", "strategy_cards.csv"),
        "chronological_quarters": "fail",
        "rolling_36_month_windows": "fail",
        "rolling_60_month_windows": "fail",
        "bootstrap": "pass",
        "leave_one_episode_out": EVIDENCE_NOT_AVAILABLE,
        "cost_stress": "pass",
        "exposure_static_controls": "pass_full_period;static_dominates_one_strongest_year_neutralization_scenario",
        "candidate_specific_concentration": "asset/year concentration <= 0.60; three-month neutralization pass; strongest-year neutralization fail",
    },
    {
        "strategy_id": "factory_v1_spy_trend_quality_state_d1",
        "family_id": "regression_trend_quality",
        "architecture": "long_only_log_price_regression_slope_and_r2_state",
        "route": "20pct_diversifier_only",
        "intended_portfolio_role_from_packet": "20pct_diversifier_only",
        "audit_role_classification": "20pct_diversifier_sleeve",
        "role_classification_basis": "80pct reference plus 20pct SPY/BIL trend-quality sleeve",
        "role_declared_before_robustness": "approved_route_declared_before_robustness",
        "exploration_outcome": "closed_exploration;weak_vs_primary_control",
        "robustness_outcome": "robustness_mixed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historically_promising_not_ready_for_paper_demo_eligibility",
        "decisive_gate": "neutralize_three_strongest_months_exposure_control_dominates",
        "relevant_control": "80pct_reference_20pct_exposure_or_static_control",
        "concentration_unit": "month;episode;year",
        "concentrated_contribution_consistent_with_mechanism": "yes_defensive_sleeve_value_is_reference-drawdown_clustered",
        "packet_path": packet("evidence/robustness/technical_factory_v1_trend_quality_diversifier_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/technical_factory/technical_strategy_factory_v1/latest", "outcome_summary.csv"),
        "chronological_quarters": "pass_4_of_4_reference",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": "pass_61_filter_episodes_fraction_reference_1.0",
        "cost_stress": "pass",
        "exposure_static_controls": "pass_full_period_but_exposure_control_dominates_after_three_month_neutralization",
        "candidate_specific_concentration": "largest filter episode below 0.50; reference-negative-month conditions pass; strongest year pass",
    },
    {
        "strategy_id": "varadi_percentile_channels_4asset_v1",
        "family_id": "multi_horizon_percentile_channel_allocation",
        "architecture": "monthly_percentile_hysteresis_channel_score_risk_parity",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "cross_sectional_allocation_strategy",
        "role_classification_basis": "monthly channel-score allocation across SPY, VNQ, LQD, DBC, and SHY",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_failed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historically_failed",
        "decisive_gate": "single_asset_over_50pct_and_month_year_neutralization_fail",
        "relevant_control": "percentile_channels_equal_weight_signal_control;donchian_4horizon_same_universe_control",
        "concentration_unit": "asset;month;year",
        "concentrated_contribution_consistent_with_mechanism": "partly_consistent_with_commodity_channel_role_but_cross_sectional_claim_is_asset_concentrated",
        "packet_path": packet("evidence/robustness/native_etf_v3_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/native_etf_source_refresh_v3_exploration_batch/latest", "strategy_cards.csv"),
        "chronological_quarters": "pass",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": EVIDENCE_NOT_AVAILABLE,
        "cost_stress": "pass",
        "exposure_static_controls": "pass_static_average_holdings_do_not_dominate",
        "candidate_specific_concentration": "DBC strongest positive-excess asset 0.679923 > 0.50; strongest year 0.120654 <= 0.50",
    },
    {
        "strategy_id": "varadi_growth_inflation_sector_timing_original_v1",
        "family_id": "sector_implied_growth_inflation_regime_rotation",
        "architecture": "daily_two_axis_sector_regime_single_asset_rotation",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "cross_sectional_allocation_strategy",
        "role_classification_basis": "daily sector rotation by growth and inflation regime state",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_failed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historically_failed",
        "decisive_gate": "regime_concentration_plus_rolling_quarter_bootstrap_failures",
        "relevant_control": "growth_only_200sma_xlk_xlp_control;growth_inflation_static_average_weight_control",
        "concentration_unit": "regime;episode;year;month",
        "concentrated_contribution_consistent_with_mechanism": "yes_if_claim_is_inflation_shock_capture_but_not_if_claim_is_balanced_four-regime_rotation",
        "packet_path": packet("evidence/robustness/native_etf_v3_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/native_etf_source_refresh_v3_exploration_batch/latest", "strategy_cards.csv"),
        "chronological_quarters": "fail",
        "rolling_36_month_windows": "fail",
        "rolling_60_month_windows": "fail",
        "bootstrap": "fail",
        "leave_one_episode_out": EVIDENCE_NOT_AVAILABLE,
        "cost_stress": "pass",
        "exposure_static_controls": "pass_static_average_weights_do_not_dominate",
        "candidate_specific_concentration": "strongest regime fraction 1.0 > 0.50; strongest episode 0.206622 <= 0.50; strongest year 0.158747 <= 0.50",
    },
    {
        "strategy_id": "kaufman_pjk_lr_channel_breakout_spy_bil_v1",
        "family_id": "projected_linear_regression_channel_breakout",
        "architecture": "long_only_projected_linear_regression_envelope_breakout",
        "route": "20pct_diversifier_only",
        "intended_portfolio_role_from_packet": "20pct_diversifier_only",
        "audit_role_classification": "event_based_strategy",
        "role_classification_basis": "20pct breakout sleeve with discrete completed trades and reference drawdown episodes",
        "role_declared_before_robustness": "approved_route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_diversifier",
        "robustness_outcome": "robustness_failed",
        "primary_failure_reason": "concentration_risk",
        "interpretation": "historical_diversifier_claim_does_not_survive_concentration_gate",
        "decisive_gate": "single_completed_trade_fraction_1.133799_exceeds_50pct_total_additive_excess",
        "relevant_control": "100pct_frozen_reference;80pct_reference_20pct_donchian_control;80pct_reference_20pct_exposure_matched_control",
        "concentration_unit": "trade;month;year;drawdown_episode",
        "concentrated_contribution_consistent_with_mechanism": "partly_event_based_but_one_trade_exceeds_total_additive_excess",
        "packet_path": packet("evidence/robustness/resolve_kaufman_diversifier_concentration_risk_v1/latest"),
        "parent_packet_path": packet("evidence/robustness/kaufman_breakout_diversifier_robustness_v1/latest"),
        "chronological_quarters": "pass_in_parent_robustness",
        "rolling_36_month_windows": "pass_in_parent_robustness",
        "rolling_60_month_windows": "pass_in_parent_robustness",
        "bootstrap": "pass_in_parent_robustness",
        "leave_one_episode_out": "leave_one_trade_out_pass_20_completed_trades_fraction_1.0",
        "cost_stress": "pass_in_parent_robustness",
        "exposure_static_controls": "pass_full_period_and_resolution_neutralizations",
        "candidate_specific_concentration": "largest trade 1.133799 > 0.50; largest year parent 0.681071; resolution month/year neutralizations pass",
    },
    {
        "strategy_id": "hestla_barnhart_vix_fix20_spy_bil_v1",
        "family_id": "synthetic_downside_volatility_mean_reversion",
        "architecture": "daily_vix_fix_vs_sma_state_allocation",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "crisis_sensitive_or_convex_defensive_mechanism",
        "role_classification_basis": "VIX-fix state toggles SPY/BIL around downside volatility conditions",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_mixed",
        "primary_failure_reason": "period_instability",
        "interpretation": "historically_promising_not_ready_for_prospective_validation",
        "decisive_gate": "rolling_36_and_60_majority_improvement_false_and_static_worse_both_quarters",
        "relevant_control": "close_only_fix20_sma20_spy_bil_control;vix_fix20_exposure_matched_spy_bil_control",
        "concentration_unit": "episode;month;year",
        "concentrated_contribution_consistent_with_mechanism": "yes_crisis_sensitive_defensive_mechanism",
        "packet_path": packet("evidence/robustness/native_etf_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/native_etf_two_candidate_exploration_batch_v1/latest", "strategy_cards.csv"),
        "chronological_quarters": "mixed_named_pass_static_worse_both_two_quarters",
        "rolling_36_month_windows": "fail_vs_exposure_control_majority",
        "rolling_60_month_windows": "fail_vs_exposure_control_majority",
        "bootstrap": "pass",
        "leave_one_episode_out": "pass_408_episodes_fraction_material_0.997549",
        "cost_stress": "pass",
        "exposure_static_controls": "exposure_matching_period_stability_weak",
        "candidate_specific_concentration": "no single episode over 0.50; three-month/year neutralization pass",
    },
    {
        "strategy_id": "keller_vanputten_faa_4m_top3_v1",
        "family_id": "generalized_momentum_flexible_asset_allocation",
        "architecture": "monthly_return_volatility_correlation_rank_with_absolute_momentum",
        "route": "standalone_only",
        "intended_portfolio_role_from_packet": "standalone_only",
        "audit_role_classification": "cross_sectional_allocation_strategy",
        "role_classification_basis": "monthly top-three allocation with return, volatility, correlation, and SHY fallback",
        "role_declared_before_robustness": "route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_standalone",
        "robustness_outcome": "robustness_positive",
        "primary_failure_reason": "",
        "interpretation": "ready_for_prospective_validation_design_standalone_asset_allocation",
        "decisive_gate": "none_all_required_gates_passed",
        "relevant_control": "faa_4m_return_only_top3_control;faa_4m_return_volatility_top3_no_correlation_control;faa_full_period_average_weight_static_control",
        "concentration_unit": "asset;year;month",
        "concentrated_contribution_consistent_with_mechanism": "yes_broad_asset_allocation_and_no_single_asset_or_year_over_50pct",
        "packet_path": packet("evidence/robustness/native_etf_two_candidate_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/native_etf_two_candidate_exploration_batch_v1/latest", "strategy_cards.csv"),
        "chronological_quarters": "pass",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": EVIDENCE_NOT_AVAILABLE,
        "cost_stress": "pass",
        "exposure_static_controls": "pass_static_average_control_not_dominant",
        "candidate_specific_concentration": "largest positive asset fraction 0.294682; largest total-return asset fraction 0.158021; top two 0.553091",
    },
    {
        "strategy_id": "barbara_decelerated_psar_spy_bil_v1",
        "family_id": "decelerated_parabolic_trend_state",
        "architecture": "long_only_adaptive_parabolic_stop_and_reverse_state",
        "route": "20pct_diversifier_only",
        "intended_portfolio_role_from_packet": "20pct_diversifier_only",
        "audit_role_classification": "20pct_diversifier_sleeve",
        "role_classification_basis": "80pct reference plus 20pct decelerated PSAR SPY/BIL sleeve",
        "role_declared_before_robustness": "approved_route_declared_before_robustness",
        "exploration_outcome": "exploratory_followup_candidate_diversifier",
        "robustness_outcome": "robustness_positive",
        "primary_failure_reason": "",
        "interpretation": "ready_for_prospective_validation_design",
        "decisive_gate": "none_all_required_gates_passed",
        "relevant_control": "80pct_reference_20pct_original_psar_control;80pct_reference_20pct_exact_exposure_matched_control",
        "concentration_unit": "month;year;episode",
        "concentrated_contribution_consistent_with_mechanism": "yes_defensive_episode_benefits_are_repeated_and_leave-one-out_survives",
        "packet_path": packet("evidence/robustness/decelerated_psar_diversifier_final_robustness_v1/latest"),
        "parent_packet_path": packet("evidence/research_recovery/decelerated_psar_diversifier_incremental_value_followup_v1/latest", "strategy_cards.csv"),
        "chronological_quarters": "pass_4_of_4_reference",
        "rolling_36_month_windows": "pass",
        "rolling_60_month_windows": "pass",
        "bootstrap": "pass",
        "leave_one_episode_out": "pass_57_episodes_fraction_reference_1.0",
        "cost_stress": "pass",
        "exposure_static_controls": "pass_exact_exposure_control_retained_and_not_decisive",
        "candidate_specific_concentration": "three-month/year neutralization pass; leave-one-defensive-episode-out pass",
    },
]


PACKET_OUTCOME_FILES = {
    "varadi_minimum_correlation_8etf_60d_weekly_v1": ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "schwoerer_hyg_ema100_spy_bil_v1": ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "gestaltu_tactical_permanent_portfolio_7pct_v1": ROOT / "evidence" / "robustness" / "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "factory_v1_spy_trend_quality_state_d1": ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest" / "outcome_summary.csv",
    "varadi_percentile_channels_4asset_v1": ROOT / "evidence" / "robustness" / "native_etf_v3_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "varadi_growth_inflation_sector_timing_original_v1": ROOT / "evidence" / "robustness" / "native_etf_v3_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "kaufman_pjk_lr_channel_breakout_spy_bil_v1": ROOT / "evidence" / "robustness" / "resolve_kaufman_diversifier_concentration_risk_v1" / "latest" / "outcome_summary.csv",
    "hestla_barnhart_vix_fix20_spy_bil_v1": ROOT / "evidence" / "robustness" / "native_etf_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "keller_vanputten_faa_4m_top3_v1": ROOT / "evidence" / "robustness" / "native_etf_two_candidate_final_robustness_v1" / "latest" / "outcome_summary.csv",
    "barbara_decelerated_psar_spy_bil_v1": ROOT / "evidence" / "robustness" / "decelerated_psar_diversifier_final_robustness_v1" / "latest" / "outcome_summary.csv",
}


def strategy_id(short: str) -> str:
    mapping = {
        "mca": "varadi_minimum_correlation_8etf_60d_weekly_v1",
        "hyg": "schwoerer_hyg_ema100_spy_bil_v1",
        "tpp": "gestaltu_tactical_permanent_portfolio_7pct_v1",
        "d1": "factory_v1_spy_trend_quality_state_d1",
        "percentile": "varadi_percentile_channels_4asset_v1",
        "growth": "varadi_growth_inflation_sector_timing_original_v1",
        "kaufman": "kaufman_pjk_lr_channel_breakout_spy_bil_v1",
        "vix": "hestla_barnhart_vix_fix20_spy_bil_v1",
        "faa": "keller_vanputten_faa_4m_top3_v1",
        "psar": "barbara_decelerated_psar_spy_bil_v1",
    }
    return mapping[short]


def gate(
    short: str,
    gate_id: str,
    result: str,
    classification: str,
    hard_gate: bool,
    decisive: bool,
    concentration_unit: str,
    relevant_control: str,
    evidence_file: str,
    audit_reconciliation: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id(short),
        "gate_id": gate_id,
        "archived_gate_result": result,
        "recommended_gate_classification": classification,
        "archived_hard_gate": hard_gate,
        "decisive_gate": decisive,
        "concentration_unit": concentration_unit,
        "relevant_control": relevant_control,
        "evidence_file": evidence_file,
        "audit_reconciliation": audit_reconciliation,
    }


GATE_ROWS: list[dict[str, Any]] = [
    gate("mca", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("mca", "positive_after_cost_and_cost_stress", "pass", "universal_hard_gate", True, False, "none", "cost grid", "cost_stress_results.csv", "retain as route-required universal"),
    gate("mca", "no_full_period_decisive_control_domination", "pass", "universal_hard_gate", True, False, "none", "inverse_volatility;static_average", "outcome_summary.csv", "retain as universal"),
    gate("mca", "chronological_three_of_four_quarters", "pass", "role_specific_hard_gate", True, False, "quarter", "inverse_volatility;static_average", "chronological_quarter_results.csv", "appropriate but role threshold should be preregistered"),
    gate("mca", "rolling_36_and_60_majority", "pass", "role_specific_hard_gate", True, False, "window", "inverse_volatility;static_average", "rolling_window_summary.csv", "appropriate for dynamic allocation"),
    gate("mca", "paired_block_bootstrap_thresholds", "pass", "role_specific_hard_gate", True, False, "bootstrap", "inverse_volatility;static_average", "paired_block_bootstrap_results.csv", "appropriate but threshold rationale absent"),
    gate("mca", "single_asset_share_at_most_60pct", "pass", "role_specific_hard_gate", True, False, "asset", "inverse_volatility", "mca_asset_and_weight_concentration.csv", "role-specific dynamic allocation cap"),
    gate("mca", "single_year_share_at_most_60pct", "pass", "role_specific_hard_gate", True, False, "year", "inverse_volatility", "mca_asset_and_weight_concentration.csv", "role-specific concentration cap"),
    gate("mca", "three_month_and_year_neutralization", "fail", "misapplied_to_strategy_role", True, True, "month;year", "static_average", "neutralization_results.csv", "strongest-year neutralization erases central defensive allocation and should trigger role-specific review rather than universal hard block"),
    gate("hyg", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("hyg", "positive_after_cost_and_cost_stress", "pass", "universal_hard_gate", True, False, "none", "cost grid", "cost_stress_results.csv", "retain as route-required universal"),
    gate("hyg", "no_full_period_decisive_control_domination", "pass", "universal_hard_gate", True, False, "none", "SPY_EMA;exposure_matched", "outcome_summary.csv", "retain as universal"),
    gate("hyg", "rolling_36_and_60_majority", "pass", "role_specific_hard_gate", True, False, "window", "SPY_EMA;exposure_matched", "rolling_window_summary.csv", "appropriate for defensive timing"),
    gate("hyg", "leave_one_episode_out_75pct", "pass", "role_specific_hard_gate", True, False, "episode", "SPY_EMA;exposure_matched", "hyg_leave_one_episode_out_summary.csv", "better hard evidence than generic strongest-month deletion for defensive mechanism"),
    gate("hyg", "single_episode_and_year_share_at_most_60pct", "pass", "role_specific_hard_gate", True, False, "episode;year", "SPY_EMA", "hyg_defensive_episode_inventory.csv", "role-specific concentration cap passes"),
    gate("hyg", "three_month_and_year_neutralization", "fail", "misapplied_to_strategy_role", True, True, "month;year", "SPY_EMA", "neutralization_results.csv", "generic removal conflicts with credit-deterioration defensive mechanism despite episode survival"),
    gate("tpp", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("tpp", "no_full_period_decisive_control_domination", "pass", "universal_hard_gate", True, False, "none", "trend_equal_weight;always_long;static", "outcome_summary.csv", "retain as universal"),
    gate("tpp", "chronological_three_of_four_quarters", "fail", "role_specific_hard_gate", True, True, "quarter", "all decisive controls", "chronological_quarter_results.csv", "valid period stability hard gate for standalone allocation"),
    gate("tpp", "rolling_36_majority", "fail", "role_specific_hard_gate", True, True, "window", "all decisive controls", "rolling_window_summary.csv", "valid period stability hard gate for standalone allocation"),
    gate("tpp", "rolling_60_majority", "fail", "role_specific_hard_gate", True, True, "window", "all decisive controls", "rolling_window_summary.csv", "valid period stability hard gate for standalone allocation"),
    gate("tpp", "three_month_neutralization", "pass", "role_specific_hard_gate", True, False, "month", "trend_equal_weight", "neutralization_results.csv", "passes under archived contract"),
    gate("tpp", "strongest_year_neutralization", "fail", "diagnostic_only", True, True, "year", "trend_equal_weight;static", "neutralization_results.csv", "use as diagnostic alongside period failures, not sole universal block"),
    gate("tpp", "asset_and_year_concentration_at_most_60pct", "pass", "role_specific_hard_gate", True, False, "asset;year", "all decisive controls", "asset_component_attribution.csv", "dynamic allocation concentration cap passes"),
    gate("d1", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("d1", "20pct_route_cost_and_reference_conditions", "pass", "role_specific_hard_gate", True, False, "sleeve", "100pct_frozen_reference", "outcome_summary.csv", "appropriate for diversifier sleeve"),
    gate("d1", "chronological_and_original_fold_stability", "pass", "role_specific_hard_gate", True, False, "quarter;fold", "100pct_frozen_reference", "outcome_summary.csv", "appropriate for preregistered factory route"),
    gate("d1", "rolling_36_and_60_reference_improvement", "pass", "role_specific_hard_gate", True, False, "window", "100pct_frozen_reference;critical controls", "rolling_window_summary.csv", "appropriate for diversifier sleeve"),
    gate("d1", "reference_negative_month_conditions", "pass", "role_specific_hard_gate", True, False, "reference_negative_month", "100pct_frozen_reference", "reference_negative_month_results.csv", "better hard evidence for diversifier value"),
    gate("d1", "leave_one_filter_episode_out", "pass", "role_specific_hard_gate", True, False, "episode", "named;exposure controls", "leave_one_filter_episode_out_summary.csv", "better hard evidence for defensive sleeve"),
    gate("d1", "largest_filter_episode_below_50pct", "pass", "role_specific_hard_gate", True, False, "episode", "named control", "path_quality_filter_episode_attribution.csv", "role-specific concentration cap passes"),
    gate("d1", "neutralize_three_strongest_months", "fail", "misapplied_to_strategy_role", True, True, "month", "exposure_or_static_control", "neutralization_results.csv", "generic month deletion overblocks a diversifier with repeated episode evidence"),
    gate("percentile", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("percentile", "no_full_period_decisive_control_domination", "pass", "universal_hard_gate", True, False, "none", "donchian;always_long;equal_signal;static", "outcome_summary.csv", "retain as universal"),
    gate("percentile", "quarter_and_rolling_majority", "pass", "role_specific_hard_gate", True, False, "quarter;window", "decisive controls", "rolling_window_summary.csv", "valid for allocation strategy"),
    gate("percentile", "paired_block_bootstrap_thresholds", "pass", "role_specific_hard_gate", True, False, "bootstrap", "decisive controls", "paired_block_bootstrap_results.csv", "passes under archived contract"),
    gate("percentile", "single_asset_over_50pct", "fail", "role_specific_hard_gate", True, True, "asset", "donchian", "percentile_channel_component_attribution.csv", "valid concern for cross-sectional allocation claim"),
    gate("percentile", "single_year_over_50pct", "pass", "role_specific_hard_gate", True, False, "year", "donchian", "percentile_channel_component_attribution.csv", "passes"),
    gate("percentile", "three_month_and_year_neutralization", "fail", "role_specific_hard_gate", True, True, "month;year", "equal_weight_signal", "month_and_year_neutralization_results.csv", "valid only if preregistered for cross-sectional allocation role"),
    gate("growth", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("growth", "no_full_period_decisive_control_domination", "pass", "universal_hard_gate", True, False, "none", "growth_only;static", "outcome_summary.csv", "retain as universal"),
    gate("growth", "quarter_and_rolling_majority", "fail", "role_specific_hard_gate", True, True, "quarter;window", "growth_only;static", "rolling_window_summary.csv", "valid period stability failure"),
    gate("growth", "paired_block_bootstrap_thresholds", "fail", "role_specific_hard_gate", True, True, "bootstrap", "growth_only;static", "paired_block_bootstrap_results.csv", "valid independent uncertainty failure"),
    gate("growth", "single_regime_over_50pct", "fail", "role_specific_hard_gate", True, True, "regime", "growth_only", "growth_inflation_regime_attribution.csv", "valid if strategy claims balanced four-regime rotation"),
    gate("growth", "single_episode_over_50pct", "pass", "role_specific_hard_gate", True, False, "episode", "growth_only", "growth_inflation_episode_neutralization.csv", "passes"),
    gate("growth", "strongest_year_neutralization", "fail", "diagnostic_only", True, True, "year", "growth_only", "month_and_year_neutralization_results.csv", "diagnostic; not sole failure because rolling/bootstrap/regime also fail"),
    gate("kaufman", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent robustness", "invariant_results.csv", "retain as universal"),
    gate("kaufman", "quarter_rolling_bootstrap_parent", "pass", "role_specific_hard_gate", True, False, "quarter;window;bootstrap", "reference;donchian;exposure", "kaufman_breakout_diversifier_robustness_v1/outcome_summary.csv", "parent stability passed"),
    gate("kaufman", "parent_month_year_concentration", "fail_then_resolved", "definition_inconsistent", True, False, "month;year", "reference", "excess_return_concentration.csv;month_neutralization_results.csv;strongest_year_neutralization_results.csv", "initial additive concentration failed, later risk-adjusted neutralization survived"),
    gate("kaufman", "leave_one_trade_out_75pct", "pass", "role_specific_hard_gate", True, False, "trade", "reference;donchian;exposure", "leave_one_trade_out_summary.csv", "appropriate event/trade evidence"),
    gate("kaufman", "single_trade_above_50pct_total_additive_excess", "fail", "role_specific_hard_gate", True, True, "trade", "reference", "trade_contribution_concentration.csv", "valid final concentration gate for event/trade strategy"),
    gate("kaufman", "reference_drawdown_episode_improvement", "pass", "role_specific_hard_gate", True, False, "drawdown_episode", "100pct_frozen_reference", "reference_drawdown_episode_results.csv", "supports but does not overcome single-trade concentration"),
    gate("vix", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("vix", "neutralize_three_month_and_year", "pass", "role_specific_hard_gate", True, False, "month;year", "close_only;static", "month_and_year_neutralization_results.csv", "passes under archived defensive timing contract"),
    gate("vix", "leave_one_episode_out_75pct", "pass", "role_specific_hard_gate", True, False, "episode", "close_only;exposure", "vix_fix_leave_one_episode_out_summary.csv", "appropriate defensive mechanism evidence"),
    gate("vix", "single_episode_over_50pct", "pass", "role_specific_hard_gate", True, False, "episode", "close_only", "vix_fix_defensive_episode_inventory.csv", "passes"),
    gate("vix", "rolling_36_and_60_majority", "fail", "role_specific_hard_gate", True, True, "window", "exposure_matched", "rolling_window_summary.csv", "valid period-stability failure"),
    gate("vix", "static_worse_both_quarters", "fail", "role_specific_hard_gate", True, True, "quarter", "static/exposure", "outcome_summary.csv", "valid because exposure matching remains decisive"),
    gate("faa", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("faa", "quarter_rolling_bootstrap_controls", "pass", "role_specific_hard_gate", True, False, "quarter;window;bootstrap", "return_only;no_correlation;static", "outcome_summary.csv", "appropriate for cross-sectional allocation"),
    gate("faa", "three_month_and_year_neutralization", "pass", "role_specific_hard_gate", True, False, "month;year", "return_only;static", "month_and_year_neutralization_results.csv", "passes"),
    gate("faa", "single_asset_and_year_over_50pct", "pass", "role_specific_hard_gate", True, False, "asset;year", "return_only;static", "faa_asset_selection_and_contribution.csv", "passes and supports cross-sectional allocation role"),
    gate("faa", "static_average_control", "pass", "universal_hard_gate", True, False, "static_control", "faa_full_period_average_weight_static_control", "paired_block_bootstrap_results.csv", "static exposure remains decisive and does not reproduce result"),
    gate("psar", "parent_reproduction_and_invariants", "pass", "universal_hard_gate", True, False, "none", "parent_trial", "invariant_results.csv", "retain as universal"),
    gate("psar", "20pct_route_cost_and_reference_conditions", "pass", "role_specific_hard_gate", True, False, "sleeve", "100pct_frozen_reference", "outcome_summary.csv", "appropriate diversifier gate"),
    gate("psar", "quarter_and_rolling_reference_improvement", "pass", "role_specific_hard_gate", True, False, "quarter;window", "100pct_frozen_reference;controls", "rolling_window_summary.csv", "passes"),
    gate("psar", "three_month_and_year_neutralization", "pass", "role_specific_hard_gate", True, False, "month;year", "reference;original_psar;exact_exposure", "month_and_year_neutralization_results.csv", "passes"),
    gate("psar", "leave_one_defensive_episode_out", "pass", "role_specific_hard_gate", True, False, "episode", "reference;original_psar;exact_exposure", "leave_one_defensive_episode_out_summary.csv", "better hard evidence for diversifier sleeve"),
    gate("psar", "paired_block_bootstrap_thresholds", "pass", "role_specific_hard_gate", True, False, "bootstrap", "reference;original_psar;exact_exposure", "bootstrap_results.csv", "passes"),
]


GATE_DEFINITIONS: list[dict[str, Any]] = [
    {"test_id": "parent_reproduction", "test_description": "Archived parent result reproduces before interpretation", "current_use": "hard_gate", "recommended_classification": "universal_hard_gate", "applicable_roles": "all", "recommended_standard": "must pass for any robustness claim", "evidence_basis": "all audited invariant or reproduction files"},
    {"test_id": "accounting_timing_weight_exposure_invariants", "test_description": "No accounting, timing, weight, or exposure invariant failure", "current_use": "hard_gate", "recommended_classification": "universal_hard_gate", "applicable_roles": "all", "recommended_standard": "must pass", "evidence_basis": "all audited invariant_results.csv files"},
    {"test_id": "positive_after_cost_when_route_requires", "test_description": "Candidate remains positive or route-positive after required cost stress", "current_use": "hard_gate", "recommended_classification": "universal_hard_gate", "applicable_roles": "all return-bearing routes", "recommended_standard": "must pass at preregistered route cost", "evidence_basis": "cost_stress_results.csv and outcome_summary.csv"},
    {"test_id": "no_decisive_control_full_period_domination", "test_description": "No decisive control dominates the candidate full-period", "current_use": "hard_gate", "recommended_classification": "universal_hard_gate", "applicable_roles": "all with controls", "recommended_standard": "must remain hard; static and exposure controls are decisive", "evidence_basis": "outcome_summary.csv across packets"},
    {"test_id": "optimization_lineage_frozen", "test_description": "No post-result parameter, universe, timing, source, control, or route change", "current_use": "hard_gate", "recommended_classification": "universal_hard_gate", "applicable_roles": "all", "recommended_standard": "must pass and be recorded before robustness", "evidence_basis": "manifest and trial_ledger files"},
    {"test_id": "chronological_three_of_four_quarters", "test_description": "Improves reference or each decisive control in at least 3 of 4 chronological quarters", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "standalone, allocation, diversifier, defensive with route-specific comparator", "recommended_standard": "role-specific; comparator and improvement definition must be declared before robustness", "evidence_basis": "chronological_quarter_results.csv and outcome_summary.csv"},
    {"test_id": "rolling_36_and_60_majority", "test_description": "Improves in a majority of 36- and 60-month windows and controls dominate no more than half", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "most non-event roles; event roles need cohort alternatives if windows sparse", "recommended_standard": "retain as role-specific hard gate when enough windows exist", "evidence_basis": "rolling_window_summary.csv"},
    {"test_id": "paired_block_bootstrap_thresholds", "test_description": "Moving-block bootstrap probability thresholds versus reference and controls", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "all with enough monthly observations", "recommended_standard": "retain as role-specific with threshold rationale recorded", "evidence_basis": "paired_block_bootstrap_results.csv or bootstrap_results.csv"},
    {"test_id": "strongest_positive_month_neutralization", "test_description": "Replace strongest positive excess month with control return and require materiality", "current_use": "hard_gate_or_component", "recommended_classification": "diagnostic_only", "applicable_roles": "defensive, crisis, diversifier, and episode-sensitive mechanisms", "recommended_standard": "diagnostic unless role declares continuous return-seeking edge", "evidence_basis": "neutralization and month_and_year_neutralization files"},
    {"test_id": "three_strongest_months_neutralization", "test_description": "Replace three strongest positive excess months with control returns", "current_use": "hard_gate", "recommended_classification": "misapplied_to_strategy_role", "applicable_roles": "defensive, crisis, diversifier sleeves when used as sole blocker", "recommended_standard": "use episode or drawdown-cohort survival as hard gate for these roles", "evidence_basis": "D1 and HYG mixed despite episode survival"},
    {"test_id": "strongest_calendar_year_neutralization", "test_description": "Replace strongest positive excess calendar year with control returns", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "continuous standalone and cross-sectional allocation; diagnostic for crisis-specific roles unless static control reproduces result", "recommended_standard": "role-specific; static/exposure dominance remains decisive", "evidence_basis": "MCA, TPP, percentile, growth, PSAR, FAA"},
    {"test_id": "asset_contribution_cap", "test_description": "Largest asset share of positive contribution cannot exceed threshold", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "allocation and cross-sectional strategies", "recommended_standard": "role-specific cap; central defensive assets require alternative repeated-episode evidence", "evidence_basis": "MCA 60pct cap; FAA and percentile 50pct cap"},
    {"test_id": "regime_contribution_cap", "test_description": "Largest regime share of positive contribution cannot exceed threshold", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "regime allocation strategies", "recommended_standard": "hard only relative to the predeclared regime claim", "evidence_basis": "growth_inflation_regime_attribution.csv"},
    {"test_id": "trade_or_episode_contribution_cap", "test_description": "Largest completed trade or episode cannot explain excessive share of total benefit", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "event strategies, trade overlays, crisis mechanisms", "recommended_standard": "hard for event/trade roles; use multiple independent event cohorts", "evidence_basis": "Kaufman resolution and VIX/PSAR episode summaries"},
    {"test_id": "leave_one_episode_or_trade_out", "test_description": "Remove one episode or trade at a time and require survival fraction", "current_use": "hard_gate", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "defensive, crisis, event, diversifier, overlay", "recommended_standard": "preferred hard gate for lumpy mechanisms", "evidence_basis": "HYG, VIX, D1, PSAR, Kaufman"},
    {"test_id": "reference_negative_month_or_drawdown_episode_improvement", "test_description": "Improvement during reference-negative months or selected drawdown episodes", "current_use": "diagnostic_or_hard_by_packet", "recommended_classification": "role_specific_hard_gate", "applicable_roles": "defensive and diversifier sleeves", "recommended_standard": "hard when defensive/diversifier role is declared before robustness", "evidence_basis": "D1, PSAR, Kaufman reference-negative and drawdown episode files"},
]


THRESHOLD_ROWS: list[dict[str, Any]] = [
    {"threshold_id": "primary_cost_5bps", "value": "5 bps one-way", "unit": "cost", "gate_or_test": "primary archived cost result", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "mostly_consistent", "strategy_roles_received": "all audited roles", "explicit_methodological_rationale": "cost grid recorded; rationale beyond cost stress not recorded", "different_thresholds_for_similar_roles": "no", "evidence": "robustness manifests and reports"},
    {"threshold_id": "cost_stress_10_15_20bps", "value": "10;15;20 bps one-way", "unit": "cost", "gate_or_test": "positive or not-dominated cost stress", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "partly_consistent", "strategy_roles_received": "most audited roles; VIX also includes 25 bps", "explicit_methodological_rationale": "cost stress recorded; role-specific rationale not recorded", "different_thresholds_for_similar_roles": "yes_vix_has_25bps_extension", "evidence": "cost_stress_results.csv"},
    {"threshold_id": "single_contribution_cap_50pct", "value": "50%", "unit": "asset;year;episode;trade;regime", "gate_or_test": "no single concentration unit over half of positive or total excess", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "no", "strategy_roles_received": "event, diversifier, defensive, cross-sectional, regime allocation", "explicit_methodological_rationale": "not recorded as a general methodology rationale", "different_thresholds_for_similar_roles": "yes_60pct_caps_used_for_MCA_HYG_TPP", "evidence": "scripts and outcome_summary gate JSON"},
    {"threshold_id": "single_contribution_cap_60pct", "value": "60%", "unit": "asset;year;episode", "gate_or_test": "MCA/TPP/HYG concentration caps", "first_task_where_appeared": "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1 and accepted_47_source_backed_v2_two_candidate_final_robustness_v1 share 2026-08-06 evidence; exact order unavailable", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "no", "strategy_roles_received": "dynamic allocation and defensive timing", "explicit_methodological_rationale": "not recorded", "different_thresholds_for_similar_roles": "yes_50pct_caps_used_for_other_allocation_and_defensive_packets", "evidence": "MCA mca_asset_and_weight_concentration.csv; TPP asset_component_attribution.csv; HYG gate JSON"},
    {"threshold_id": "bootstrap_reference_70pct", "value": "70%", "unit": "probability", "gate_or_test": "candidate higher Sharpe or less severe drawdown versus named/reference threshold in standalone packets", "first_task_where_appeared": "native_etf_two_candidate_final_robustness_v1", "direction_owner_specified": "source_authority_path_recorded_but_threshold_specific_text_not_in_packet", "reused_consistently": "partly_consistent", "strategy_roles_received": "standalone allocation and source-backed standalone", "explicit_methodological_rationale": "not recorded beyond preregistered gate", "different_thresholds_for_similar_roles": "yes_diversifier_reference_uses_75pct_in_some packets", "evidence": "native_etf_two_candidate_final_robustness_v1.py and outcome_summary.csv"},
    {"threshold_id": "bootstrap_reference_or_leave_one_75pct", "value": "75%", "unit": "probability_or_fraction", "gate_or_test": "reference bootstrap threshold; leave-one episode/trade survival threshold", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "partly_consistent", "strategy_roles_received": "20pct diversifier, defensive timing, event/trade", "explicit_methodological_rationale": "not recorded as cross-role rationale", "different_thresholds_for_similar_roles": "yes_70pct_used_for_some standalone bootstrap gates", "evidence": "Kaufman, PSAR, D1, HYG, VIX summaries"},
    {"threshold_id": "bootstrap_critical_control_60pct", "value": "60%", "unit": "probability", "gate_or_test": "critical controls bootstrap probability threshold", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "mostly_consistent", "strategy_roles_received": "standalone, diversifier, allocation", "explicit_methodological_rationale": "not recorded", "different_thresholds_for_similar_roles": "no_material_difference_found", "evidence": "bootstrap_results.csv and paired_block_bootstrap_results.csv"},
    {"threshold_id": "faa_no_correlation_bootstrap_65pct", "value": "65%", "unit": "probability", "gate_or_test": "FAA bootstrap versus no-correlation control", "first_task_where_appeared": "native_etf_two_candidate_final_robustness_v1", "direction_owner_specified": "source_authority_path_recorded_but_threshold_specific_text_not_in_packet", "reused_consistently": "strategy_specific", "strategy_roles_received": "cross-sectional allocation", "explicit_methodological_rationale": "not recorded", "different_thresholds_for_similar_roles": "yes_strategy-specific_threshold", "evidence": "FAA candidate_specific_positive_checks"},
    {"threshold_id": "rolling_majority_threshold", "value": ">50% improve; <=50% control dominance", "unit": "rolling_window_fraction", "gate_or_test": "rolling 36- and 60-month majority", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "mostly_consistent", "strategy_roles_received": "all audited roles with rolling evidence", "explicit_methodological_rationale": "majority concept implicit; role rationale not recorded", "different_thresholds_for_similar_roles": "no", "evidence": "rolling_window_summary.csv"},
    {"threshold_id": "three_of_four_quarters", "value": "3 of 4", "unit": "chronological_quarters", "gate_or_test": "quarter stability", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "mostly_consistent", "strategy_roles_received": "standalone, allocation, diversifier", "explicit_methodological_rationale": "not recorded", "different_thresholds_for_similar_roles": "partly_comparator_definition_differs_by_role", "evidence": "chronological_quarter_results.csv and gate JSON"},
    {"threshold_id": "80_20_diversifier_route", "value": "80% reference / 20% candidate sleeve", "unit": "portfolio_weight", "gate_or_test": "approved diversifier route construction", "first_task_where_appeared": "kaufman_breakout_diversifier_robustness_v1", "direction_owner_specified": EVIDENCE_NOT_AVAILABLE, "reused_consistently": "consistent_for_20pct_diversifier_packets", "strategy_roles_received": "20pct diversifier sleeve; event sleeve", "explicit_methodological_rationale": "approved_route recorded; broader policy rationale not recorded", "different_thresholds_for_similar_roles": "no", "evidence": "Kaufman, D1, PSAR manifests and strategy cards"},
]


def inventory_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": item["strategy_id"],
            "family_id": item["family_id"],
            "architecture": item["architecture"],
            "route": item["route"],
            "intended_portfolio_role": item["intended_portfolio_role_from_packet"],
            "audit_role_classification": item["audit_role_classification"],
            "exploration_outcome": item["exploration_outcome"],
            "robustness_outcome": item["robustness_outcome"],
            "primary_failure_reason": item["primary_failure_reason"],
            "hard_robustness_gates": ";".join(row["gate_id"] for row in GATE_ROWS if row["strategy_id"] == item["strategy_id"] and row["archived_hard_gate"]),
            "passed_gates": ";".join(row["gate_id"] for row in GATE_ROWS if row["strategy_id"] == item["strategy_id"] and row["archived_gate_result"].startswith("pass")),
            "failed_gates": ";".join(row["gate_id"] for row in GATE_ROWS if row["strategy_id"] == item["strategy_id"] and "fail" in row["archived_gate_result"]),
            "exact_decisive_gate": item["decisive_gate"],
            "relevant_control": item["relevant_control"],
            "relevant_concentration_unit": item["concentration_unit"],
            "concentrated_contribution_consistent_with_stated_mechanism": item["concentrated_contribution_consistent_with_mechanism"],
            "chronological_quarters": item["chronological_quarters"],
            "rolling_36_month_windows": item["rolling_36_month_windows"],
            "rolling_60_month_windows": item["rolling_60_month_windows"],
            "bootstrap": item["bootstrap"],
            "leave_one_episode_out": item["leave_one_episode_out"],
            "cost_stress": item["cost_stress"],
            "exposure_static_controls": item["exposure_static_controls"],
            "packet_path": item["packet_path"],
            "parent_packet_path": item["parent_packet_path"],
            "evidence_note": item["candidate_specific_concentration"],
        }
        for item in STRATEGIES
    ]


def role_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": item["strategy_id"],
            "family_id": item["family_id"],
            "architecture": item["architecture"],
            "route_from_packet": item["route"],
            "intended_portfolio_role_from_packet": item["intended_portfolio_role_from_packet"],
            "audit_role_classification": item["audit_role_classification"],
            "role_classification_basis": item["role_classification_basis"],
            "role_declared_before_robustness": item["role_declared_before_robustness"],
            "role_change_made_by_audit": False,
            "classification_note": "methodology audit classification only; no strategy status changed",
        }
        for item in STRATEGIES
    ]


def repeated_failure_rows() -> list[dict[str, Any]]:
    return [
        {
            "pattern_id": "generic_neutralization_overblocks_lumpy_roles",
            "affected_strategies": "schwoerer_hyg_ema100_spy_bil_v1;factory_v1_spy_trend_quality_state_d1;varadi_minimum_correlation_8etf_60d_weekly_v1",
            "pattern_type": "role_conflict",
            "evidence": "HYG/D1 pass episode, rolling, cost, and control checks but fail strongest-month/year style neutralization; MCA passes asset and rolling checks but fails strongest-year static domination",
            "methodology_interpretation": "generic neutralization can mechanically remove the intended defensive allocation mechanism",
            "recommended_handling": "make neutralization role-specific and use leave-one-episode/drawdown/reference-negative tests as hard gates for defensive or diversifier roles",
        },
        {
            "pattern_id": "similar_concentration_units_received_50pct_and_60pct_caps",
            "affected_strategies": "varadi_minimum_correlation_8etf_60d_weekly_v1;gestaltu_tactical_permanent_portfolio_7pct_v1;keller_vanputten_faa_4m_top3_v1;varadi_percentile_channels_4asset_v1;varadi_growth_inflation_sector_timing_original_v1",
            "pattern_type": "definition_inconsistent",
            "evidence": "MCA/TPP/HYG use 60pct caps, while FAA/percentile/growth use 50pct caps for related asset/year/regime units",
            "methodology_interpretation": "thresholds are preregistered inside packets but cross-role rationale is not visible",
            "recommended_handling": "declare threshold by role before robustness and record rationale",
        },
        {
            "pattern_id": "static_exposure_controls_remain_decisive",
            "affected_strategies": "all audited strategies with static or exposure controls",
            "pattern_type": "confirmed_universal",
            "evidence": "Packets repeatedly treat static average, exposure-matched, same-purpose, and full-period controls as decisive",
            "methodology_interpretation": "role-aware concentration gates must not permit static or exposure controls to reproduce the result",
            "recommended_handling": "retain full-period static/exposure control non-domination as universal hard gate",
        },
        {
            "pattern_id": "trade_unit_resolves_event_strategy_counterfactual",
            "affected_strategies": "kaufman_pjk_lr_channel_breakout_spy_bil_v1",
            "pattern_type": "better_role_unit_identified",
            "evidence": "Kaufman month/year neutralizations later survived, but a single completed trade was 1.133799 of total additive excess",
            "methodology_interpretation": "event and trade overlays need trade/event concentration gates, not just month/year gates",
            "recommended_handling": "use sufficient event count, leave-one-event/trade-out, and single-event caps as hard gates",
        },
    ]


def universal_rows() -> list[dict[str, Any]]:
    return [
        {"gate_family": "parent reproduction", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "A robustness packet cannot be interpreted unless the archived parent result reproduces", "evidence_examples": "all audited packets report parent reproduction pass"},
        {"gate_family": "accounting and timing invariants", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "Invariant failure is a methodology failure independent of strategy role", "evidence_examples": "invariant_results.csv across packets"},
        {"gate_family": "positive after-cost return when route requires", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "A route that requires positive return must remain cost viable", "evidence_examples": "5/10/15/20 bps checks"},
        {"gate_family": "no decisive full-period control domination", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "Static, exposure, and same-purpose controls must remain decisive", "evidence_examples": "MCA static control, D1 exact exposure, PSAR exact exposure, FAA static average"},
        {"gate_family": "no hidden tuning or lineage break", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "Optimization lineage remains binding", "evidence_examples": "manifest no parameter/universe/source changes"},
        {"gate_family": "data and comparability integrity", "classification": "universal_hard_gate", "retain_universal": True, "rationale": "Data incomparability invalidates the audit independent of role", "evidence_examples": "data_preflight and benchmark reference files where present"},
        {"gate_family": "generic month/year neutralization", "classification": "misapplied_to_strategy_role", "retain_universal": False, "rationale": "It can remove the intended defensive or diversifier mechanism by construction", "evidence_examples": "HYG and D1 concentration_risk despite strong episode evidence"},
    ]


def role_specific_rows() -> list[dict[str, Any]]:
    return [
        {"strategy_role": "return_seeking_standalone_strategy", "gate_family": "strongest-month/year neutralization", "classification": "role_specific_hard_gate", "recommended_use": "hard when the edge is declared continuous and not crisis/event-specific", "minimum_evidence": "materiality survives and no decisive control dominates"},
        {"strategy_role": "defensive_equity_timing_strategy", "gate_family": "defensive episodes and leave-one-episode-out", "classification": "role_specific_hard_gate", "recommended_use": "hard replacement for generic strongest-month deletion", "minimum_evidence": "several distinct episodes, leave-one survival, no exposure control domination"},
        {"strategy_role": "dynamic_multi_asset_allocation_strategy", "gate_family": "asset/year concentration plus static control", "classification": "role_specific_hard_gate", "recommended_use": "assess concentration relative to intended diversification mechanism", "minimum_evidence": "static average does not dominate, rolling survival, no one asset/year explains nearly all benefit"},
        {"strategy_role": "20pct_diversifier_sleeve", "gate_family": "reference drawdown and reference-negative-month improvement", "classification": "role_specific_hard_gate", "recommended_use": "hard for sleeve role", "minimum_evidence": "rolling portfolio improvement, leave-one-drawdown survival, exposure control no full-period dominance"},
        {"strategy_role": "crisis_sensitive_or_convex_defensive_mechanism", "gate_family": "episode cohort concentration", "classification": "role_specific_hard_gate", "recommended_use": "hard; generic month/year neutralization diagnostic", "minimum_evidence": "multiple crisis episodes and no one episode explains excessive benefit"},
        {"strategy_role": "event_based_strategy", "gate_family": "event/trade count, leave-one-out, single-event cap", "classification": "role_specific_hard_gate", "recommended_use": "hard", "minimum_evidence": "sufficient events, independent cohorts, no one event/trade explains full result"},
        {"strategy_role": "cross_sectional_allocation_strategy", "gate_family": "asset concentration and static/correlation controls", "classification": "role_specific_hard_gate", "recommended_use": "hard", "minimum_evidence": "no single asset/year concentration beyond preregistered cap, return-only/no-correlation controls do not reproduce result"},
        {"strategy_role": "trade_management_overlay", "gate_family": "overlay effect by trade cohort", "classification": "role_specific_hard_gate", "recommended_use": "hard for overlay claim", "minimum_evidence": "benefit remains across trade cohorts and host strategy control"},
    ]


def neutralization_rows() -> list[dict[str, Any]]:
    return [
        {"neutralization_test": "strongest positive month", "recommended_classification": "diagnostic_only", "roles_where_hard": "continuous return-seeking standalone if declared before robustness", "roles_where_diagnostic": "defensive, crisis-sensitive, diversifier sleeve, event strategy", "better_hard_gate": "episode or drawdown-cohort leave-one-out", "evidence_examples": "HYG, D1, PSAR, FAA"},
        {"neutralization_test": "three strongest positive months", "recommended_classification": "misapplied_to_strategy_role", "roles_where_hard": "continuous return-seeking standalone and some cross-sectional allocation roles", "roles_where_diagnostic": "defensive and diversifier sleeves", "better_hard_gate": "multiple independent defensive episodes plus no single episode/trade cap", "evidence_examples": "D1 failed despite 61 episode survival; HYG failed despite 84 episode survival"},
        {"neutralization_test": "strongest calendar year", "recommended_classification": "role_specific_hard_gate", "roles_where_hard": "standalone allocation if static/exposure control dominates or year explains nearly all positive benefit", "roles_where_diagnostic": "crisis or inflation-shock mechanisms when the year is a reference event and repeated episodes pass", "better_hard_gate": "static/exposure control dominance, leave-one-episode, and drawdown cohort evidence", "evidence_examples": "MCA, TPP, percentile, growth, PSAR"},
        {"neutralization_test": "strongest defensive/drawdown episode", "recommended_classification": "role_specific_hard_gate", "roles_where_hard": "defensive timing, diversifier sleeve, crisis-sensitive mechanism", "roles_where_diagnostic": "standalone continuous allocation with no episode claim", "better_hard_gate": "leave-one-episode-out survival and episode count", "evidence_examples": "D1 and PSAR"},
        {"neutralization_test": "strongest trade/event", "recommended_classification": "role_specific_hard_gate", "roles_where_hard": "event strategy and trade overlay", "roles_where_diagnostic": "non-event allocation strategies", "better_hard_gate": "no one trade/event over preregistered cap plus leave-one-event-out", "evidence_examples": "Kaufman failed on single trade 1.133799"},
    ]


def alternative_rows() -> list[dict[str, Any]]:
    return [
        {"strategy_role": "defensive_or_crisis_sensitive_strategy", "candidate_replacement_test": "benefit across several distinct defensive episodes", "recommended_status": "adopt_as_role_specific_hard_gate", "rationale": "tests repetition without deleting the defining adverse-regime mechanism", "evidence_examples": "HYG 84 episodes; VIX 408 episodes; PSAR 57 episodes"},
        {"strategy_role": "defensive_or_crisis_sensitive_strategy", "candidate_replacement_test": "leave-one-episode-out survival >= preregistered threshold", "recommended_status": "adopt_as_role_specific_hard_gate", "rationale": "distinguishes one-off overfit from repeated mechanism", "evidence_examples": "HYG, VIX, PSAR pass"},
        {"strategy_role": "20pct_diversifier_sleeve", "candidate_replacement_test": "reference-negative month and reference drawdown episode improvement", "recommended_status": "adopt_as_role_specific_hard_gate", "rationale": "sleeve objective is portfolio path improvement, not standalone smoothness", "evidence_examples": "D1, PSAR, Kaufman reference-negative-month files"},
        {"strategy_role": "dynamic_multi_asset_allocation_strategy", "candidate_replacement_test": "static average control non-domination plus rolling control survival", "recommended_status": "already_universal_plus_role_specific", "rationale": "prevents static weights from reproducing the result while allowing economically central assets", "evidence_examples": "MCA, TPP, FAA"},
        {"strategy_role": "event_based_strategy", "candidate_replacement_test": "sufficient event count and no single event/trade over cap", "recommended_status": "adopt_as_role_specific_hard_gate", "rationale": "unit of concentration is the event/trade, not calendar month", "evidence_examples": "Kaufman resolution"},
        {"strategy_role": "cross_sectional_allocation_strategy", "candidate_replacement_test": "no single asset/year dominance plus return-only/no-correlation controls", "recommended_status": "retain_as_role_specific_hard_gate", "rationale": "cross-sectional claims should not collapse into one asset or one omitted component", "evidence_examples": "FAA passes; percentile fails asset cap"},
    ]


def consistency_rows() -> list[dict[str, Any]]:
    return [
        {"assessment_id": "role_declaration_before_robustness", "finding": "partly_satisfied", "evidence": "routes are declared, but role taxonomy is not consistently explicit before robustness", "fairness_impact": "generic gates are reused across mechanisms with different intended payoffs", "recommendation": "declare role taxonomy before robustness"},
        {"assessment_id": "neutralization_gate_uniformity", "finding": "overuniform", "evidence": "HYG and D1 are blocked by month/year neutralization despite repeated episode evidence", "fairness_impact": "defensive mechanisms can be penalized for working in adverse episodes", "recommendation": "make generic neutralization diagnostic for defensive/diversifier roles"},
        {"assessment_id": "concentration_threshold_consistency", "finding": "inconsistent", "evidence": "50pct and 60pct caps appear for related asset/year/episode units", "fairness_impact": "similar roles may face different hard thresholds", "recommendation": "standardize thresholds by role and rationale"},
        {"assessment_id": "static_exposure_control_integrity", "finding": "confirmed", "evidence": "static and exposure controls are retained and decisive across packets", "fairness_impact": "prevents role-aware exemptions from becoming result-driven waivers", "recommendation": "retain as universal hard gate"},
        {"assessment_id": "successful_control_examples", "finding": "FAA_and_PSAR_support_role_aware_standard", "evidence": "FAA passes cross-sectional asset/year/control gates; PSAR passes 20pct diversifier episode/rolling/control gates", "fairness_impact": "shows role-aware gates need not weaken standards", "recommendation": "use as calibration examples, not promotions"},
    ]


def reassessment_rows() -> list[dict[str, Any]]:
    label = "eligible_for_later_reassessment_if_direction_owner_approves_standard"
    return [
        {"strategy_id": strategy_id("mca"), "potential_future_status": label, "reason": "mixed outcome controlled by strongest-year/static neutralization pattern with other controls passing", "non_promotion_note": "not a promotion and current status unchanged"},
        {"strategy_id": strategy_id("hyg"), "potential_future_status": label, "reason": "defensive timing role passes leave-one-episode-out and controls but fails generic month/year neutralization", "non_promotion_note": "not a promotion and current status unchanged"},
        {"strategy_id": strategy_id("d1"), "potential_future_status": label, "reason": "20pct diversifier passes episode, reference, rolling, and bootstrap evidence but fails three-month neutralization", "non_promotion_note": "not a promotion and current status unchanged"},
        {"strategy_id": strategy_id("tpp"), "potential_future_status": label, "reason": "strongest-year neutralization is implicated, but rolling and quarter failures also remain", "non_promotion_note": "not a promotion and would require separate role-specific period stability review"},
        {"strategy_id": strategy_id("percentile"), "potential_future_status": label, "reason": "asset cap threshold may be role-standardized later, but current single-asset and neutralization failures remain", "non_promotion_note": "not a promotion"},
        {"strategy_id": strategy_id("growth"), "potential_future_status": "not_primary_reassessment_candidate_under_this_audit", "reason": "regime concentration is accompanied by rolling, quarter, and bootstrap failures", "non_promotion_note": "unchanged robustness_failed"},
        {"strategy_id": strategy_id("kaufman"), "potential_future_status": "not_primary_reassessment_candidate_under_this_audit", "reason": "role-specific trade concentration gate was applied and failed", "non_promotion_note": "unchanged robustness_failed"},
        {"strategy_id": strategy_id("vix"), "potential_future_status": "not_primary_reassessment_candidate_under_this_audit", "reason": "neutralization and episode gates pass; mixed outcome is period instability", "non_promotion_note": "unchanged robustness_mixed"},
        {"strategy_id": strategy_id("faa"), "potential_future_status": "not_applicable_already_robustness_positive", "reason": "used only as calibration example", "non_promotion_note": "audit creates no observation or promotion"},
        {"strategy_id": strategy_id("psar"), "potential_future_status": "not_applicable_already_robustness_positive", "reason": "used only as calibration example", "non_promotion_note": "audit creates no observation or promotion"},
    ]


def proposed_standard_md() -> str:
    return """# Proposed Role-Aware Robustness Standard V1

## Scope

This is a proposed methodology standard for direction-owner review. It does not reclassify, promote, or reopen any strategy by itself.

## Required Pre-Robustness Declaration

Every candidate must declare exactly one primary role before robustness:

- return_seeking_standalone_strategy
- defensive_equity_timing_strategy
- dynamic_multi_asset_allocation_strategy
- 20pct_diversifier_sleeve
- crisis_sensitive_or_convex_defensive_mechanism
- event_based_strategy
- cross_sectional_allocation_strategy
- trade_management_overlay

Secondary descriptors may be recorded, but the primary role controls the hard gate contract.

## Universal Hard Gates

These remain universal hard gates:

- parent reproduction;
- accounting, timing, weight, exposure, and cost invariants;
- positive after-cost return when the route requires it;
- no full-period domination by a decisive control;
- static-weight and exposure-matched controls remain decisive;
- no hidden tuning, post-result parameter changes, universe changes, or control changes;
- no data, source, comparability, or lineage failure.

## Role-Specific Concentration Rules

Generic strongest-month or strongest-year neutralization should not be universal. For defensive, crisis-sensitive, diversifier, event, and overlay roles, it is diagnostic unless preregistered as a role-specific hard gate with a mechanism-valid counterfactual.

For defensive and crisis-sensitive strategies, hard evidence should be:

- benefits across several distinct adverse episodes;
- leave-one-episode-out survival;
- improvement in a majority of reference drawdown or defensive episodes;
- no single episode accounting for an excessive preregistered share;
- no static, exposure-matched, or ordinary self-trend control reproduction.

For 20pct diversifier sleeves, hard evidence should be:

- rolling portfolio improvement versus the frozen reference;
- improvement in reference-negative months or reference drawdown episodes;
- leave-one-drawdown-episode-out survival;
- no exposure-matched control full-period domination;
- no single episode or trade explaining the result.

For dynamic multi-asset and cross-sectional allocation strategies, hard evidence should be:

- static average weights do not dominate;
- rolling control survival;
- concentration assessed relative to the intended diversification mechanism;
- no single asset, regime, or year explaining nearly all incremental value unless explicitly preregistered as the role and independently supported.

For event strategies and trade-management overlays, hard evidence should be:

- sufficient event or trade count;
- multiple independent cohorts;
- leave-one-event or leave-one-trade-out survival;
- no one event or trade explaining the full result;
- cost and timing viability.

## Threshold Policy

Every numeric threshold must be declared before robustness by role, including 50pct or 60pct concentration caps, 70pct or 75pct bootstrap thresholds, 60pct critical-control bootstrap thresholds, rolling-window majority tests, and three-of-four-quarter requirements. If the evidence packet does not record a threshold rationale, the audit record must say evidence_not_available.

## Reassessment Rule

No strategy receives an automatic promotion or status change from this standard. A candidate can only be listed as eligible_for_later_reassessment_if_direction_owner_approves_standard, and any reassessment must preserve source rules, parameters, universes, controls, and prior outcomes until a new authorized task runs.
"""


def report_md() -> str:
    return """# Methodology Audit Report

## Outcome

`robustness_gate_standardization_required`

Exact next action: `direction_owner_review_role_aware_robustness_standard_v1`

## Findings

The audited packets show that universal reproduction, invariant, lineage, cost, and full-period decisive-control gates are internally sound and should remain universal.

The concentration and neutralization gates are not equally well standardized. Generic strongest-month, three-strongest-month, and strongest-year neutralization act as hard blockers for defensive or diversifier mechanisms even when the archived packets also show repeated episode evidence, rolling survival, cost viability, and static/exposure controls that do not reproduce the result.

The clearest examples are HYG and D1. HYG has 84 defensive episodes and survives leave-one-episode-out, but fails month/year neutralization versus SPY EMA100. D1 has 61 filter episodes, strong reference and rolling evidence, and passes leave-one-episode-out, but fails after neutralizing the three strongest months. MCA similarly shows dynamic allocation evidence and passes asset/year concentration caps, but strongest-year neutralization allows the static average control to dominate.

The successful comparison cases support role-aware gating rather than looser gating. FAA passes cross-sectional allocation controls, asset/year concentration, neutralization, rolling, and bootstrap gates. Decelerated PSAR passes the 20pct diversifier sleeve gates, including exact exposure control, rolling windows, bootstrap, month/year neutralization, and 57-episode leave-one-out survival.

Kaufman shows the opposite lesson: a role-specific trade concentration gate can be stricter and more appropriate than month/year neutralization. Its month/year neutralizations later survived, but a single completed trade explained 1.133799 of total additive excess, so the final failed outcome remains appropriate.

## Recommendation

Adopt a role-aware robustness standard for direction-owner review. Keep universal gates hard. Move generic neutralization into role-specific use, and for defensive, crisis, diversifier, event, and overlay roles prefer episode, drawdown, event, or trade concentration gates as the hard blocker.

No audited strategy outcome is changed by this report.
"""


def validate_source_outcomes() -> list[str]:
    checked: list[str] = []
    for item in STRATEGIES:
        strategy = item["strategy_id"]
        row = find_row(PACKET_OUTCOME_FILES[strategy], strategy)
        actual_outcome = row.get("outcome", "")
        if actual_outcome != item["robustness_outcome"]:
            raise RuntimeError(f"outcome mismatch for {strategy}: {actual_outcome} != {item['robustness_outcome']}")
        actual_failure = normalize_failure(row)
        if actual_failure != item["primary_failure_reason"]:
            raise RuntimeError(f"failure mismatch for {strategy}: {actual_failure} != {item['primary_failure_reason']}")
        checked.append(strategy)
    return checked


def write_outputs(pre_hashes: dict[str, str], checked_strategies: list[str]) -> None:
    write_yaml(
        "audit_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "created_by": "deterministic_report_generation",
            "source_of_truth": "archived_authoritative_packets_only",
            "strategy_outcomes_preserved": True,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "new_robustness_trials": 0,
            "new_validation_observations": 0,
            "new_paper_demo_observations": 0,
            "methodology_audit_records": 1,
            "process_task_records": 1,
            "proposed_policy_records": 1,
            "outcome": OUTCOME,
            "exact_next_action": NEXT_ACTION,
            "next_action_executed": False,
            "audited_strategy_ids": [item["strategy_id"] for item in STRATEGIES],
            "protected_paths_reconciled": sorted(pre_hashes),
        },
    )
    write_csv("robustness_packet_inventory.csv", inventory_rows())
    write_csv("strategy_role_classification.csv", role_rows())
    write_csv("gate_definition_inventory.csv", GATE_DEFINITIONS)
    write_csv("numeric_threshold_inventory.csv", THRESHOLD_ROWS)
    write_csv("candidate_gate_reconciliation.csv", GATE_ROWS)
    write_csv("repeated_failure_pattern.csv", repeated_failure_rows())
    write_csv("universal_gate_assessment.csv", universal_rows())
    write_csv("role_specific_gate_assessment.csv", role_specific_rows())
    write_csv("neutralization_gate_assessment.csv", neutralization_rows())
    write_csv("alternative_concentration_tests.csv", alternative_rows())
    write_csv("consistency_and_fairness_assessment.csv", consistency_rows())
    write_csv("potential_future_reassessment_inventory.csv", reassessment_rows())
    (OUTPUT_DIR / "proposed_role_aware_standard.md").write_text(proposed_standard_md(), encoding="utf-8")
    write_csv(
        "process_task_log.csv",
        [
            {
                "task_id": TASK_ID,
                "process_task_record_count": 1,
                "mode": MODE,
                "stage": STAGE,
                "action": "methodology_audit_packet_generated",
                "strategy_search_run": False,
                "strategy_performance_generated": False,
                "strategy_outcomes_changed": False,
                "provider_broker_account_order_capital_action": False,
                "notes": "Only archived packets were read; reports were generated deterministically.",
            }
        ],
    )
    write_csv(
        "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "mode": MODE,
                "stage": STAGE,
                "outcome": OUTCOME,
                "primary_reason": "generic_concentration_and_neutralization_gates_are_not_role_standardized",
                "exact_next_action": NEXT_ACTION,
                "next_action_executed": False,
                "strategy_outcomes_preserved": True,
                "new_strategy_configurations": 0,
                "new_experiment_trials": 0,
                "new_robustness_trials": 0,
                "new_validation_observations": 0,
                "new_paper_demo_observations": 0,
            }
        ],
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": OUTCOME,
                "blocked": False,
                "failure_reason": "",
                "methodology_issue": "role_aware_standardization_required",
                "notes": "Audit completed; this is not a robustness_gate_audit_blocked outcome.",
            }
        ],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": OUTCOME,
                "exact_next_action": NEXT_ACTION,
                "next_action_executed": False,
            }
        ],
    )
    (OUTPUT_DIR / "methodology_audit_report.md").write_text(report_md(), encoding="utf-8")

    post_hashes = protected_hashes()
    output_hashes = {
        name: sha256_file(OUTPUT_DIR / name)
        for name in REQUIRED_OUTPUTS
        if name != "consistency_check.json" and (OUTPUT_DIR / name).exists()
    }
    missing_before_consistency = sorted(
        name
        for name in REQUIRED_OUTPUTS
        if name != "consistency_check.json" and not (OUTPUT_DIR / name).exists()
    )
    present_before_consistency = sorted(
        name
        for name in REQUIRED_OUTPUTS
        if name == "consistency_check.json" or (OUTPUT_DIR / name).exists()
    )
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": True,
        "outcome": OUTCOME,
        "exact_next_action": NEXT_ACTION,
        "audited_outcomes_checked": checked_strategies,
        "strategy_outcomes_preserved": True,
        "no_strategy_performance_generated": True,
        "strategy_search_run": False,
        "next_action_executed": False,
        "entity_count_reconciliation": {
            "methodology_audit_records": 1,
            "process_task_records": 1,
            "proposed_policy_records": 1,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "new_robustness_trials": 0,
            "new_validation_observations": 0,
            "new_paper_demo_observations": 0,
        },
        "protected_state_reconciliation": {
            "overall_pass": pre_hashes == post_hashes,
            "before": pre_hashes,
            "after": post_hashes,
        },
        "required_output_reconciliation": {
            "required_count": len(REQUIRED_OUTPUTS),
            "present": present_before_consistency,
            "missing": missing_before_consistency,
            "hashes_excluding_consistency_check": output_hashes,
        },
        "verification_scope": {
            "authoritative_packet_discovery": True,
            "trial_lineage_reconciliation": True,
            "archived_result_arithmetic_checks_needed": False,
            "gate_definition_consistency_checks": True,
            "numeric_threshold_reconciliation": True,
            "deterministic_report_generation": True,
            "protected_state_cache_observation_prior_evidence_reconciliation": True,
        },
    }
    if not consistency["protected_state_reconciliation"]["overall_pass"]:
        raise RuntimeError("protected evidence changed during audit generation")
    if missing_before_consistency:
        raise RuntimeError("required output missing")
    write_json("consistency_check.json", consistency)


def run() -> dict[str, Any]:
    pre_hashes = protected_hashes()
    checked_strategies = validate_source_outcomes()
    clean_output()
    write_outputs(pre_hashes, checked_strategies)
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "outcome": OUTCOME,
        "exact_next_action": NEXT_ACTION,
        "required_outputs": len(REQUIRED_OUTPUTS),
        "checked_strategies": checked_strategies,
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
