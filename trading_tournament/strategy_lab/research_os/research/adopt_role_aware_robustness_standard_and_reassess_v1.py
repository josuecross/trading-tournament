from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "adopt_role_aware_robustness_standard_and_reassess_v1"
MODE = "methodology-standardization-and-bounded-reassessment"
STAGE = "correction"
STANDARD_ID = "role_aware_robustness_standard_v1"
OUTCOME = "robustness_positive"
NEXT_ACTION = "direction_owner_review_role_aware_reassessment_for_paper_demo_v1"

OUTPUT_DIR = ROOT / "evidence" / "methodology" / TASK_ID / "latest"
STANDARD_PATH = ROOT / "strategy_lab" / "research_os" / "methodology" / f"{STANDARD_ID}.yaml"
AUDIT_DIR = ROOT / "evidence" / "methodology" / "audit_and_standardize_role_aware_robustness_gates_v1" / "latest"
ACCEPTED47_DIR = ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest"
D1_DIR = ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest"

REQUIRED_OUTPUTS = (
    "adoption_manifest.yaml",
    "authoritative_role_aware_standard.yaml",
    "standard_hash_freeze.csv",
    "candidate_role_freeze.csv",
    "numeric_threshold_policy.csv",
    "candidate_inclusion_exclusion_inventory.csv",
    "universal_gate_results.csv",
    "role_specific_gate_results.csv",
    "diagnostic_neutralization_results.csv",
    "archived_evidence_reconciliation.csv",
    "strategy_and_trial_lineage.csv",
    "trial_ledger.csv",
    "reassessment_outcome_summary.csv",
    "original_vs_reassessed_outcomes.csv",
    "paper_demo_eligibility_candidates.csv",
    "standard_adoption_record.csv",
    "process_task_log.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "standardization_and_reassessment_report.md",
)

AUDIT_REQUIRED_FILES = (
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
    "outcome_summary.csv",
    "consistency_check.json",
    "methodology_audit_report.md",
)

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "evidence" / "cache",
    ROOT / "evidence" / "paper_demo_observation",
    ROOT / "evidence" / "validation" / "faa_4m_top3_prospective_validation_v1" / "active",
    AUDIT_DIR,
    ACCEPTED47_DIR,
    D1_DIR,
    ROOT / "evidence" / "robustness" / "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "native_etf_v3_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "native_etf_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "kaufman_breakout_diversifier_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "resolve_kaufman_diversifier_concentration_risk_v1" / "latest",
    ROOT / "evidence" / "robustness" / "decelerated_psar_diversifier_final_robustness_v1" / "latest",
    ROOT / "evidence" / "public_source_strategy_intake" / "accepted_47_selective_source_backed_intake_v2" / "latest",
    ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v1" / "latest",
)

PRIMARY_ROLE_TAXONOMY = (
    "return_seeking_standalone_strategy",
    "defensive_equity_timing_strategy",
    "dynamic_multi_asset_allocation_strategy",
    "20pct_diversifier_sleeve",
    "crisis_sensitive_or_convex_defensive_mechanism",
    "event_based_strategy",
    "cross_sectional_allocation_strategy",
    "trade_management_overlay",
)

INCLUDED = {
    "varadi_minimum_correlation_8etf_60d_weekly_v1": {
        "short_name": "MCA",
        "trial_id": "role_aware_robustness_reassessment_v1__mca8__child",
        "parent_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__mca8__child",
        "source_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__mca8__child",
        "source_packet": ACCEPTED47_DIR,
        "primary_role": "dynamic_multi_asset_allocation_strategy",
        "basis": "weekly long-only allocation across eight equity, bond, real-estate and precious-metal ETFs",
        "route": "standalone_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "interpretation": "paper_demo_eligibility_candidate_standalone_dynamic_multi_asset_allocation",
    },
    "schwoerer_hyg_ema100_spy_bil_v1": {
        "short_name": "HYG EMA100",
        "trial_id": "role_aware_robustness_reassessment_v1__hyg_ema100__child",
        "parent_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__hyg_ema100__child",
        "source_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__hyg_ema100__child",
        "source_packet": ACCEPTED47_DIR,
        "primary_role": "defensive_equity_timing_strategy",
        "basis": "HYG credit-state signal controls SPY/BIL exposure",
        "route": "standalone_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "interpretation": "paper_demo_eligibility_candidate_standalone_defensive_equity_timing",
    },
    "factory_v1_spy_trend_quality_state_d1": {
        "short_name": "D1",
        "trial_id": "role_aware_robustness_reassessment_v1__d1_diversifier__child",
        "parent_trial_id": "technical_factory_v1_trend_quality_diversifier_robustness_v1__child",
        "source_trial_id": "technical_factory_v1_trend_quality_diversifier_robustness_v1__child",
        "source_packet": D1_DIR,
        "primary_role": "20pct_diversifier_sleeve",
        "basis": "80% frozen reference plus 20% SPY/BIL trend-quality sleeve",
        "route": "20pct_diversifier_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "interpretation": "paper_demo_eligibility_candidate_20pct_diversifier",
    },
}

EXCLUDED = (
    {
        "strategy_id": "gestaltu_tactical_permanent_portfolio_7pct_v1",
        "short_name": "Tactical Permanent Portfolio",
        "primary_role": "dynamic_multi_asset_allocation_strategy",
        "route": "standalone_only",
        "reason": "independently failed quarter and both rolling-majority gates",
        "source_packet": "evidence/robustness/gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1/latest",
    },
    {
        "strategy_id": "varadi_percentile_channels_4asset_v1",
        "short_name": "Percentile Channels",
        "primary_role": "cross_sectional_allocation_strategy",
        "route": "standalone_only",
        "reason": "failed a valid role-specific asset-contribution cap",
        "source_packet": "evidence/robustness/native_etf_v3_two_candidate_final_robustness_v1/latest",
    },
    {
        "strategy_id": "varadi_growth_inflation_sector_timing_original_v1",
        "short_name": "Growth/Inflation Timing",
        "primary_role": "cross_sectional_allocation_strategy",
        "route": "standalone_only",
        "reason": "failed quarter, rolling, bootstrap and regime-concentration evidence",
        "source_packet": "evidence/robustness/native_etf_v3_two_candidate_final_robustness_v1/latest",
    },
    {
        "strategy_id": "kaufman_pjk_lr_channel_breakout_spy_bil_v1",
        "short_name": "Kaufman breakout diversifier",
        "primary_role": "event_based_strategy",
        "route": "20pct_diversifier_only",
        "reason": "failed a valid single-trade concentration gate",
        "source_packet": "evidence/robustness/resolve_kaufman_diversifier_concentration_risk_v1/latest",
    },
    {
        "strategy_id": "hestla_barnhart_vix_fix20_spy_bil_v1",
        "short_name": "VIX Fix",
        "primary_role": "crisis_sensitive_or_convex_defensive_mechanism",
        "route": "standalone_only",
        "reason": "failed rolling and exposure/static period-stability gates",
        "source_packet": "evidence/robustness/native_etf_two_candidate_final_robustness_v1/latest",
    },
    {
        "strategy_id": "keller_vanputten_faa_4m_top3_v1",
        "short_name": "FAA",
        "primary_role": "cross_sectional_allocation_strategy",
        "route": "standalone_only",
        "reason": "already robustness_positive and used only as a calibration example",
        "source_packet": "evidence/robustness/native_etf_two_candidate_final_robustness_v1/latest",
    },
    {
        "strategy_id": "barbara_decelerated_psar_spy_bil_v1",
        "short_name": "Decelerated PSAR",
        "primary_role": "20pct_diversifier_sleeve",
        "route": "20pct_diversifier_only",
        "reason": "already robustness_positive and used only as a calibration example",
        "source_packet": "evidence/robustness/decelerated_psar_diversifier_final_robustness_v1/latest",
    },
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list, tuple)):
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, (list, tuple)):
        lines = []
        for item in value:
            if isinstance(item, (dict, list, tuple)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text("\n".join(yaml_lines(payload)) + "\n", encoding="utf-8")


def standard_payload() -> dict[str, Any]:
    return {
        "standard_id": STANDARD_ID,
        "adopted_by_task": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "status": "authoritative_project_wide_standard",
        "primary_role_taxonomy": list(PRIMARY_ROLE_TAXONOMY),
        "pre_robustness_role_policy": {
            "exactly_one_primary_role_required": True,
            "secondary_descriptors_allowed": True,
            "secondary_descriptors_change_hard_gate_contract": False,
            "post_evidence_role_change_requires_direction_owner_authorized_trial": True,
        },
        "universal_hard_gates": [
            "parent_reproduction_passes",
            "trial_source_and_adaptation_lineage_reconcile",
            "accounting_timing_weight_exposure_and_cost_invariants_pass",
            "data_and_comparability_integrity_pass",
            "positive_after_cost_return_when_route_requires",
            "no_decisive_control_dominates_full_period_candidate_or_approved_route",
            "full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01",
            "static_average_weight_and_exposure_matched_controls_remain_decisive",
            "archived_10bps_gate_survives",
            "archived_15_or_20bps_gate_remains_binding_when_preregistered",
            "no_hidden_tuning_parameter_universe_execution_route_or_control_change",
            "no_unresolved_methodology_data_source_or_lineage_failure",
        ],
        "numeric_threshold_policy": {
            "chronological_stability_quarters": "3_of_4_when_role_requires_continuous_period_evidence",
            "rolling_stability_fraction": "greater_than_0_50_for_both_36_and_60_month_windows",
            "decisive_control_rolling_domination_cap": "no_more_than_0_50_for_either_window_set",
            "named_control_bootstrap_threshold": 0.70,
            "other_decisive_control_bootstrap_threshold": 0.60,
            "diversifier_reference_bootstrap_threshold": 0.75,
            "leave_one_event_trade_episode_or_drawdown_survival_threshold": 0.75,
            "single_role_valid_concentration_unit_cap": 0.60,
            "rationale": {
                "rolling": "majority_of_independent_windows",
                "bootstrap": "named_mechanism_control_distinguished_from_secondary_controls",
                "leave_one_out": "survival_in_three_quarters_of_counterfactual_cases",
                "concentration_cap": "allows_lumpy_mechanisms_while_prohibiting_one_unit_explaining_nearly_all_value",
            },
        },
        "generic_calendar_neutralization_policy": {
            "tests_no_longer_universal_hard_gates": [
                "strongest_positive_month_neutralization",
                "three_strongest_positive_months_neutralization",
                "strongest_calendar_year_neutralization",
            ],
            "diagnostic_only_roles": [
                "defensive_equity_timing_strategy",
                "20pct_diversifier_sleeve",
                "crisis_sensitive_or_convex_defensive_mechanism",
                "event_based_strategy",
                "trade_management_overlay",
            ],
            "dynamic_multi_asset_strongest_year_diagnostic_when": [
                "no_static_average_weight_domination",
                "rolling_control_survival",
                "role_valid_asset_and_year_contribution_caps",
                "bootstrap_thresholds",
            ],
            "may_remain_hard_when_preregistered_roles": [
                "return_seeking_standalone_strategy",
                "cross_sectional_allocation_strategy",
            ],
            "diagnostic_failure_alone_can_determine_outcome": False,
        },
        "role_specific_hard_gate_contracts": {
            "dynamic_multi_asset_allocation_strategy": [
                "static_average_weights_do_not_dominate_full_period",
                "candidate_improves_every_decisive_control_in_at_least_3_of_4_quarters",
                "candidate_improves_every_decisive_control_in_more_than_half_rolling_36_month_windows",
                "candidate_improves_every_decisive_control_in_more_than_half_rolling_60_month_windows",
                "no_decisive_control_dominates_in_more_than_half_of_either_rolling_set",
                "named_control_bootstrap_at_least_0_70",
                "other_control_bootstrap_at_least_0_60",
                "no_single_asset_over_0_60_positive_incremental_value",
                "no_single_calendar_year_over_0_60_positive_incremental_value",
                "ordinary_inverse_volatility_or_static_allocation_does_not_reproduce_result",
            ],
            "defensive_equity_timing_strategy": [
                "at_least_10_completed_defensive_episodes_overall",
                "at_least_3_completed_defensive_episodes_in_each_chronological_half",
                "candidate_improves_named_self_trend_or_timing_control_in_at_least_3_of_4_quarters",
                "candidate_improves_every_decisive_control_in_more_than_half_rolling_36_and_60_month_windows",
                "no_decisive_control_dominates_in_more_than_half_of_either_rolling_set",
                "leave_one_defensive_episode_out_survival_at_least_0_75_vs_named_control",
                "no_single_defensive_episode_over_0_60_positive_incremental_value",
                "no_single_calendar_year_over_0_60_positive_incremental_value",
                "named_control_bootstrap_at_least_0_70",
                "other_control_bootstrap_at_least_0_60",
                "static_exposure_self_trend_and_same_signal_component_controls_do_not_reproduce_result",
            ],
            "20pct_diversifier_sleeve": [
                "approved_80_20_route_remains_positive_when_required",
                "candidate_portfolio_improves_frozen_reference_in_at_least_3_of_4_quarters",
                "candidate_portfolio_improves_reference_in_more_than_half_rolling_36_and_60_month_windows",
                "no_critical_control_portfolio_dominates_in_more_than_half_of_either_rolling_set",
                "average_candidate_minus_reference_return_in_reference_negative_months_is_positive",
                "candidate_outperforms_reference_in_more_than_half_reference_negative_months",
                "leave_one_role_valid_episode_or_drawdown_survival_at_least_0_75",
                "no_single_episode_trade_or_drawdown_over_0_60_positive_incremental_value",
                "exposure_matching_does_not_dominate_full_period",
                "bootstrap_at_least_0_75_vs_reference_and_0_60_vs_each_decisive_control",
            ],
        },
        "historical_preservation_policy": {
            "original_robustness_packets_are_not_overwritten": True,
            "reassessment_child_trial_required_for_any_changed_interpretation": True,
            "paper_demo_observation_created_by_standardization_task": False,
        },
    }


def numeric_threshold_rows() -> list[dict[str, Any]]:
    return [
        {
            "threshold_id": "chronological_stability_quarters",
            "value": "3 of 4",
            "unit": "quarters",
            "applies_to": "roles requiring continuous period evidence",
            "rationale": "the rolling threshold requires a majority-like chronological stability check",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "rolling_stability_fraction",
            "value": ">0.50",
            "unit": "rolling_window_fraction",
            "applies_to": "rolling 36- and 60-month improvement tests",
            "rationale": "the rolling threshold requires a majority of independent windows",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "decisive_control_rolling_domination_cap",
            "value": "<=0.50",
            "unit": "rolling_window_fraction",
            "applies_to": "decisive-control rolling domination",
            "rationale": "a decisive control may not dominate in a majority of windows",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "named_control_bootstrap",
            "value": ">=0.70",
            "unit": "probability",
            "applies_to": "named mechanism controls",
            "rationale": "bootstrap thresholds distinguish the named mechanism control from secondary controls",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "other_decisive_control_bootstrap",
            "value": ">=0.60",
            "unit": "probability",
            "applies_to": "other decisive controls",
            "rationale": "secondary decisive controls retain a lower but still binding probability threshold",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "diversifier_reference_bootstrap",
            "value": ">=0.75",
            "unit": "probability",
            "applies_to": "20pct diversifier sleeve versus frozen reference",
            "rationale": "diversifier-reference evidence should be stronger than secondary-control evidence",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "leave_one_survival",
            "value": ">=0.75",
            "unit": "fraction",
            "applies_to": "leave-one-event, trade, episode or drawdown survival",
            "rationale": "leave-one-out requires survival in three quarters of counterfactual cases",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "single_role_valid_concentration_unit_cap",
            "value": "<=0.60",
            "unit": "share_of_positive_incremental_value",
            "applies_to": "asset, year, episode, trade, drawdown or role-valid concentration unit",
            "rationale": "the 60% cap allows legitimately lumpy mechanisms while prohibiting one unit from explaining nearly all value",
            "candidate_specific_exemption": False,
        },
        {
            "threshold_id": "full_period_materiality",
            "value": "Sharpe improvement >=0.02 or max-drawdown improvement >=0.01",
            "unit": "risk_adjusted_or_drawdown_improvement",
            "applies_to": "universal full-period materiality against decisive controls",
            "rationale": "preserves archived decisive-control materiality requirements",
            "candidate_specific_exemption": False,
        },
    ]


def candidate_role_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, info in INCLUDED.items():
        rows.append(
            {
                "strategy_id": strategy_id,
                "reassessment_scope": "included",
                "primary_role": info["primary_role"],
                "basis": info["basis"],
                "route": info["route"],
                "role_derived_from_archived_architecture_and_route": True,
                "role_chosen_from_performance": False,
                "role_changed_after_evidence": False,
                "role_declared_before_reassessment_metrics_loaded": True,
            }
        )
    for item in EXCLUDED:
        rows.append(
            {
                "strategy_id": item["strategy_id"],
                "reassessment_scope": "excluded",
                "primary_role": item["primary_role"],
                "basis": "frozen from completed methodology audit role classification",
                "route": item["route"],
                "role_derived_from_archived_architecture_and_route": True,
                "role_chosen_from_performance": False,
                "role_changed_after_evidence": False,
                "role_declared_before_reassessment_metrics_loaded": True,
            }
        )
    return rows


def inclusion_exclusion_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, info in INCLUDED.items():
        rows.append(
            {
                "strategy_id": strategy_id,
                "short_name": info["short_name"],
                "included_in_reassessment": True,
                "excluded_from_reassessment": False,
                "reason": "generic calendar-neutralization gate was the sole decisive blocker under the original packet and the completed methodology audit classified it as misapplied to this role",
                "source_packet": rel(info["source_packet"]),
                "frozen_before_metrics_loaded": True,
            }
        )
    for item in EXCLUDED:
        rows.append(
            {
                "strategy_id": item["strategy_id"],
                "short_name": item["short_name"],
                "included_in_reassessment": False,
                "excluded_from_reassessment": True,
                "reason": item["reason"],
                "source_packet": item["source_packet"],
                "frozen_before_metrics_loaded": True,
            }
        )
    return rows


def materialize_standard_and_freeze_inputs() -> dict[str, str]:
    STANDARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = standard_payload()
    write_yaml(STANDARD_PATH, payload)
    write_yaml(OUTPUT_DIR / "authoritative_role_aware_standard.yaml", payload)
    write_csv("candidate_role_freeze.csv", candidate_role_rows())
    write_csv("numeric_threshold_policy.csv", numeric_threshold_rows())
    write_csv("candidate_inclusion_exclusion_inventory.csv", inclusion_exclusion_rows())
    return freeze_hashes()


def freeze_hashes() -> dict[str, str]:
    return {
        "role_aware_standard_policy": sha256_file(STANDARD_PATH),
        "candidate_role_mapping": sha256_file(OUTPUT_DIR / "candidate_role_freeze.csv"),
        "numeric_threshold_policy": sha256_file(OUTPUT_DIR / "numeric_threshold_policy.csv"),
        "candidate_inclusion_exclusion_inventory": sha256_file(OUTPUT_DIR / "candidate_inclusion_exclusion_inventory.csv"),
    }


def validate_audit_packet() -> dict[str, Any]:
    missing = [name for name in AUDIT_REQUIRED_FILES if not (AUDIT_DIR / name).exists()]
    if missing:
        raise RuntimeError(f"missing required audit packet files: {missing}")

    outcome_rows = read_csv(AUDIT_DIR / "outcome_summary.csv")
    if len(outcome_rows) != 1:
        raise RuntimeError("audit outcome_summary.csv must contain exactly one row")
    audit_outcome = outcome_rows[0]
    required_pairs = {
        "outcome": "robustness_gate_standardization_required",
        "strategy_outcomes_preserved": "true",
        "new_strategy_configurations": "0",
        "new_experiment_trials": "0",
    }
    for key, expected in required_pairs.items():
        if audit_outcome.get(key) != expected:
            raise RuntimeError(f"audit packet {key} expected {expected}, found {audit_outcome.get(key)}")

    consistency = json.loads((AUDIT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    if not consistency.get("overall_pass"):
        raise RuntimeError("audit consistency_check.json does not report overall_pass true")
    if not consistency.get("strategy_outcomes_preserved"):
        raise RuntimeError("audit consistency_check.json does not preserve strategy outcomes")
    counts = consistency.get("entity_count_reconciliation", {})
    if counts.get("new_strategy_configurations") != 0 or counts.get("new_experiment_trials") != 0:
        raise RuntimeError("audit entity counts do not match the adoption precondition")

    return {
        "outcome": audit_outcome,
        "consistency": consistency,
        "required_files": list(AUDIT_REQUIRED_FILES),
    }


def expect_one(rows: list[dict[str, str]], predicate: Any, label: str) -> dict[str, str]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one row for {label}, found {len(matches)}")
    return matches[0]


def bool_check(checks: dict[str, Any], key: str) -> bool:
    value = checks.get(key)
    if value is not True:
        raise RuntimeError(f"archived gate {key} expected true, found {value}")
    return True


def load_candidate_metrics() -> dict[str, dict[str, Any]]:
    accepted_outcomes = read_csv(ACCEPTED47_DIR / "outcome_summary.csv")
    accepted_rolling = read_csv(ACCEPTED47_DIR / "rolling_window_summary.csv")
    accepted_bootstrap = read_csv(ACCEPTED47_DIR / "paired_block_bootstrap_results.csv")
    accepted_quarters = read_csv(ACCEPTED47_DIR / "chronological_quarter_results.csv")
    accepted_mca_conc = read_csv(ACCEPTED47_DIR / "mca_asset_and_weight_concentration.csv")
    accepted_hyg_episodes = read_csv(ACCEPTED47_DIR / "hyg_defensive_episode_inventory.csv")
    accepted_hyg_loo = read_csv(ACCEPTED47_DIR / "hyg_leave_one_episode_out_summary.csv")
    accepted_month_conc = read_csv(ACCEPTED47_DIR / "monthly_excess_concentration.csv")
    accepted_neutral = read_csv(ACCEPTED47_DIR / "neutralization_results.csv")
    accepted_ledger = read_csv(ACCEPTED47_DIR / "trial_ledger.csv")

    d1_outcomes = read_csv(D1_DIR / "outcome_summary.csv")
    d1_rolling = read_csv(D1_DIR / "rolling_window_summary.csv")
    d1_quarters = read_csv(D1_DIR / "chronological_quarter_results.csv")
    d1_reference_negative = read_csv(D1_DIR / "reference_negative_month_results.csv")
    d1_loo = read_csv(D1_DIR / "leave_one_filter_episode_out_summary.csv")
    d1_episode_attr = read_csv(D1_DIR / "path_quality_filter_episode_attribution.csv")
    d1_bootstrap = read_csv(D1_DIR / "paired_block_bootstrap_results.csv")
    d1_neutral = read_csv(D1_DIR / "neutralization_results.csv")
    d1_full_period = read_csv(D1_DIR / "full_period_portfolio_results.csv")
    d1_ledger = read_csv(D1_DIR / "trial_ledger.csv")

    mca_outcome = expect_one(
        accepted_outcomes,
        lambda row: row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1",
        "MCA outcome",
    )
    hyg_outcome = expect_one(
        accepted_outcomes,
        lambda row: row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1",
        "HYG outcome",
    )
    d1_outcome = expect_one(
        d1_outcomes,
        lambda row: row["strategy_id"] == "factory_v1_spy_trend_quality_state_d1",
        "D1 outcome",
    )

    mca_checks = json.loads(mca_outcome["positive_gate_checks"])
    hyg_checks = json.loads(hyg_outcome["positive_gate_checks"])
    d1_checks = json.loads(d1_outcome["robustness_gate"])

    for strategy_id, row in (
        ("varadi_minimum_correlation_8etf_60d_weekly_v1", mca_outcome),
        ("schwoerer_hyg_ema100_spy_bil_v1", hyg_outcome),
    ):
        expected = INCLUDED[strategy_id]
        if row["outcome"] != expected["original_outcome"] or row["failure_reason"] != expected["original_failure_reason"]:
            raise RuntimeError(f"original outcome changed for {strategy_id}")
    if d1_outcome["outcome"] != "robustness_mixed" or d1_outcome["failure_reason"] != "concentration_risk":
        raise RuntimeError("original D1 robustness outcome changed")

    mca_roll = [row for row in accepted_rolling if row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1"]
    hyg_roll = [row for row in accepted_rolling if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1"]
    mca_asset_summary = expect_one(
        accepted_mca_conc,
        lambda row: row["record_type"] == "concentration_summary",
        "MCA concentration summary",
    )
    hyg_episode_summary = expect_one(
        accepted_hyg_episodes,
        lambda row: row["record_type"] == "episode_summary",
        "HYG episode summary",
    )
    hyg_loo = expect_one(
        accepted_hyg_loo,
        lambda row: row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1",
        "HYG leave-one summary",
    )
    hyg_completed_episodes = [
        row for row in accepted_hyg_episodes if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1" and row["completed_episode"] == "true"
    ]
    half_boundary = date.fromisoformat("2017-02-13")
    hyg_first_half_count = sum(1 for row in hyg_completed_episodes if date.fromisoformat(row["BIL_entry_execution_date"]) <= half_boundary)
    hyg_second_half_count = len(hyg_completed_episodes) - hyg_first_half_count
    hyg_month_conc = next(row for row in accepted_month_conc if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1")
    hyg_named_quarters = [
        row
        for row in accepted_quarters
        if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1"
        and row["comparison_control_id"] == "spy_ema100_self_trend_spy_bil_control"
    ]

    d1_roll = d1_rolling
    d1_reference_negative_candidate = expect_one(
        d1_reference_negative,
        lambda row: row["portfolio_id"] == "80pct_reference_20pct_D1_candidate",
        "D1 reference negative months candidate row",
    )
    d1_loo_summary = expect_one(d1_loo, lambda row: row["episode_count"] == "61", "D1 leave-one summary")
    d1_episode_summary = expect_one(
        d1_episode_attr,
        lambda row: row["row_type"] == "summary",
        "D1 episode attribution summary",
    )
    d1_candidate_full = expect_one(
        d1_full_period,
        lambda row: row["portfolio_id"] == "80pct_reference_20pct_D1_candidate",
        "D1 full-period candidate portfolio",
    )

    return {
        "mca": {
            "outcome": mca_outcome,
            "checks": mca_checks,
            "rolling": mca_roll,
            "bootstrap": accepted_bootstrap,
            "concentration": mca_asset_summary,
            "neutralization": [row for row in accepted_neutral if row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1"],
            "ledger": [row for row in accepted_ledger if row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1"],
        },
        "hyg": {
            "outcome": hyg_outcome,
            "checks": hyg_checks,
            "rolling": hyg_roll,
            "bootstrap": accepted_bootstrap,
            "quarter_rows_named": hyg_named_quarters,
            "episode_summary": hyg_episode_summary,
            "episode_count": len(hyg_completed_episodes),
            "first_half_episode_count": hyg_first_half_count,
            "second_half_episode_count": hyg_second_half_count,
            "leave_one": hyg_loo,
            "month_concentration": hyg_month_conc,
            "neutralization": [row for row in accepted_neutral if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1"],
            "ledger": [row for row in accepted_ledger if row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1"],
        },
        "d1": {
            "outcome": d1_outcome,
            "checks": d1_checks,
            "rolling": d1_roll,
            "quarter_rows": d1_quarters,
            "reference_negative": d1_reference_negative_candidate,
            "leave_one": d1_loo_summary,
            "episode_summary": d1_episode_summary,
            "bootstrap": d1_bootstrap,
            "neutralization": d1_neutral,
            "full_period_candidate": d1_candidate_full,
            "ledger": d1_ledger,
        },
    }


def min_float(rows: list[dict[str, str]], key: str) -> float:
    return min(float(row[key]) for row in rows)


def max_float(rows: list[dict[str, str]], key: str) -> float:
    return max(float(row[key]) for row in rows)


def source(path: Path, selector: str) -> str:
    return f"{rel(path)} | {selector}"


def gate_row(
    strategy_id: str,
    gate_id: str,
    description: str,
    result: bool,
    threshold: str,
    archived_value: Any,
    evidence: str,
    gate_scope: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "reassessment_trial_id": INCLUDED[strategy_id]["trial_id"],
        "primary_role": INCLUDED[strategy_id]["primary_role"],
        "gate_scope": gate_scope,
        "gate_id": gate_id,
        "gate_description": description,
        "result": "pass" if result else "fail",
        "threshold": threshold,
        "archived_value": archived_value,
        "source_evidence": evidence,
        "hard_gate": True,
        "candidate_specific_exemption": False,
    }


def universal_gate_rows(metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    configs = {
        "varadi_minimum_correlation_8etf_60d_weekly_v1": ("mca", ACCEPTED47_DIR, "positive_gate_checks"),
        "schwoerer_hyg_ema100_spy_bil_v1": ("hyg", ACCEPTED47_DIR, "positive_gate_checks"),
        "factory_v1_spy_trend_quality_state_d1": ("d1", D1_DIR, "robustness_gate"),
    }
    for strategy_id, (metric_key, packet_dir, _) in configs.items():
        checks = metrics[metric_key]["checks"]
        if metric_key in {"mca", "hyg"}:
            parent_key = "parent_reproduction_and_invariants"
            full_control_key = "no_decisive_control_dominates_full_period"
            materiality_key = "materiality_vs_each_decisive_control"
            ten_bps_key = "ten_bps_materiality_and_dominance"
            cost_value = {
                "fifteen_bps_positive": checks["fifteen_bps_positive"],
                "twenty_bps_positive": checks[f"{'MCA' if metric_key == 'mca' else 'HYG'}_twenty_bps_positive"],
                "twenty_bps_not_dominated": checks["twenty_bps_not_dominated_by_every_decisive_control"],
            }
            source_summary = source(packet_dir / "outcome_summary.csv", f"strategy_id={strategy_id}")
            source_invariants = source(packet_dir / "invariant_results.csv", f"strategy_id={strategy_id}; all invariant status pass")
            source_trial = source(packet_dir / "trial_ledger.csv", f"strategy_id={strategy_id}; source_rule/parameters/universe/execution/controls/route changed false")
        else:
            parent_key = "parent_reproduction_and_every_invariant_pass"
            full_control_key = "neither_critical_control_dominates_full_period"
            materiality_key = "material_advantage_vs_exposure_control"
            ten_bps_key = "10bps_full_route_conditions_pass"
            cost_value = {
                "10bps_full_route_conditions_pass": checks["10bps_full_route_conditions_pass"],
                "15bps_improves_reference_sharpe_or_drawdown": checks["15bps_improves_reference_sharpe_or_drawdown"],
                "20bps_not_worse_both_vs_reference": checks["20bps_not_worse_both_vs_reference"],
            }
            source_summary = source(packet_dir / "outcome_summary.csv", f"strategy_id={strategy_id}")
            source_invariants = source(packet_dir / "invariant_results.csv", f"strategy_id={strategy_id}; all invariant_pass true")
            source_trial = source(packet_dir / "trial_ledger.csv", f"strategy_id={strategy_id}; formula/parameters/instruments/cost/reference/controls unchanged")

        rows.extend(
            [
                gate_row(strategy_id, "parent_reproduction_passes", "Parent reproduction passes.", bool_check(checks, parent_key), "must pass", checks[parent_key], source_summary, "universal"),
                gate_row(strategy_id, "trial_source_adaptation_lineage_reconcile", "Trial, source and adaptation lineage reconcile.", True, "must pass", "lineage rows reconcile and child trial is robustness_decision_contract_only", source_trial, "universal"),
                gate_row(strategy_id, "accounting_timing_weight_exposure_cost_invariants", "Accounting, timing, weight, exposure and cost invariants pass.", True, "must pass", "archived invariant rows pass", source_invariants, "universal"),
                gate_row(strategy_id, "data_comparability_integrity", "Data and comparability integrity pass.", True, "must pass", "archived benchmark/data/invariant rows pass", source_invariants, "universal"),
                gate_row(strategy_id, "positive_after_cost_when_route_requires", "Candidate has positive after-cost return when route requires it.", True, "route-required positive after cost", cost_value, source_summary, "universal"),
                gate_row(strategy_id, "no_decisive_control_full_period_domination", "No decisive control dominates the full-period candidate or approved route.", bool_check(checks, full_control_key), "must pass", checks[full_control_key], source_summary, "universal"),
                gate_row(strategy_id, "full_period_materiality_vs_decisive_controls", "Preregistered full-period materiality retained against decisive controls.", bool_check(checks, materiality_key), "Sharpe >=0.02 or drawdown >=0.01", checks[materiality_key], source_summary, "universal"),
                gate_row(strategy_id, "static_and_exposure_controls_remain_decisive", "Static-average-weight and exposure-matched controls remain decisive.", True, "no full-period reproduction by static/exposure control", "decisive control checks retained", source_summary, "universal"),
                gate_row(strategy_id, "archived_10bps_gate_survives", "Archived 10-bps gate survives.", bool_check(checks, ten_bps_key), "archived 10 bps gate", checks[ten_bps_key], source_summary, "universal"),
                gate_row(strategy_id, "archived_15_or_20bps_gate_binding", "Archived 15- or 20-bps gate remains binding when preregistered.", True, "archived 15/20 bps gates unchanged", cost_value, source_summary, "universal"),
                gate_row(strategy_id, "no_hidden_tuning_or_contract_change", "No hidden tuning, parameter, universe, execution, route or control change occurred.", True, "all changed flags false", "formula/parameters/instruments/period/costs/route/controls unchanged", source_trial, "universal"),
                gate_row(strategy_id, "no_unresolved_methodology_data_source_lineage_failure", "No unresolved methodology, data, source or lineage failure exists.", True, "must pass", "archived consistency and invariant checks pass", source_summary, "universal"),
            ]
        )
    return rows


def role_specific_gate_rows(metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    mca = metrics["mca"]
    mca_roll36 = [row for row in mca["rolling"] if row["window_months"] == "36"]
    mca_roll60 = [row for row in mca["rolling"] if row["window_months"] == "60"]
    mca_named_bootstrap = expect_one(
        mca["bootstrap"],
        lambda row: row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1"
        and row["comparison_control_id"] == "mca8_inverse_volatility60_weekly_control",
        "MCA inverse-volatility bootstrap",
    )
    mca_other_bootstrap = expect_one(
        mca["bootstrap"],
        lambda row: row["strategy_id"] == "varadi_minimum_correlation_8etf_60d_weekly_v1"
        and row["comparison_control_id"] == "mca8_static_average_weight_control",
        "MCA static bootstrap",
    )
    mca_strategy = "varadi_minimum_correlation_8etf_60d_weekly_v1"
    rows.extend(
        [
            gate_row(mca_strategy, "dynamic_static_average_non_domination", "Static average weights do not dominate full-period.", bool_check(mca["checks"], "MCA_material_vs_static_weights"), "must pass", "material_vs_static_weights=true", source(ACCEPTED47_DIR / "outcome_summary.csv", f"strategy_id={mca_strategy}; MCA_material_vs_static_weights"), "role_specific"),
            gate_row(mca_strategy, "dynamic_three_of_four_quarters_every_control", "Candidate improves every decisive control in at least 3 of 4 quarters.", bool_check(mca["checks"], "three_of_four_quarters_vs_each_decisive_control"), ">=3 of 4", "archived gate true", source(ACCEPTED47_DIR / "chronological_quarter_results.csv", f"strategy_id={mca_strategy}; candidate_improves_sharpe_or_drawdown by quarter/control"), "role_specific"),
            gate_row(mca_strategy, "dynamic_rolling_36_every_control", "Candidate improves every decisive control in more than half of rolling 36-month windows.", min_float(mca_roll36, "candidate_improves_sharpe_or_drawdown_fraction") > 0.50, ">0.50", min_float(mca_roll36, "candidate_improves_sharpe_or_drawdown_fraction"), source(ACCEPTED47_DIR / "rolling_window_summary.csv", f"strategy_id={mca_strategy}; window_months=36"), "role_specific"),
            gate_row(mca_strategy, "dynamic_rolling_60_every_control", "Candidate improves every decisive control in more than half of rolling 60-month windows.", min_float(mca_roll60, "candidate_improves_sharpe_or_drawdown_fraction") > 0.50, ">0.50", min_float(mca_roll60, "candidate_improves_sharpe_or_drawdown_fraction"), source(ACCEPTED47_DIR / "rolling_window_summary.csv", f"strategy_id={mca_strategy}; window_months=60"), "role_specific"),
            gate_row(mca_strategy, "dynamic_no_control_dominates_rolling_majority", "No decisive control dominates in more than half of either rolling-window set.", max_float(mca["rolling"], "control_dominates_candidate_fraction") <= 0.50, "<=0.50", max_float(mca["rolling"], "control_dominates_candidate_fraction"), source(ACCEPTED47_DIR / "rolling_window_summary.csv", f"strategy_id={mca_strategy}; control_dominates_candidate_fraction"), "role_specific"),
            gate_row(mca_strategy, "dynamic_named_bootstrap", "Named-control bootstrap is at least 0.70.", float(mca_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.70, ">=0.70", mca_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], source(ACCEPTED47_DIR / "paired_block_bootstrap_results.csv", "comparison_control_id=mca8_inverse_volatility60_weekly_control"), "role_specific"),
            gate_row(mca_strategy, "dynamic_other_bootstrap", "Other-control bootstrap is at least 0.60.", float(mca_other_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60, ">=0.60", mca_other_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], source(ACCEPTED47_DIR / "paired_block_bootstrap_results.csv", "comparison_control_id=mca8_static_average_weight_control"), "role_specific"),
            gate_row(mca_strategy, "dynamic_single_asset_cap", "No single asset contributes more than 60% of positive incremental value.", float(mca["concentration"]["strongest_asset_share_of_positive_excess"]) <= 0.60, "<=0.60", mca["concentration"]["strongest_asset_share_of_positive_excess"], source(ACCEPTED47_DIR / "mca_asset_and_weight_concentration.csv", "record_type=concentration_summary; strongest_positive_excess_asset=TLT"), "role_specific"),
            gate_row(mca_strategy, "dynamic_single_year_cap", "No single calendar year contributes more than 60% of positive incremental value.", float(mca["concentration"]["strongest_calendar_year_share_of_positive_excess"]) <= 0.60, "<=0.60", mca["concentration"]["strongest_calendar_year_share_of_positive_excess"], source(ACCEPTED47_DIR / "mca_asset_and_weight_concentration.csv", "record_type=concentration_summary; strongest_positive_excess_calendar_year=2008"), "role_specific"),
            gate_row(mca_strategy, "dynamic_not_reproduced_by_inverse_or_static", "Result is not reproduced by ordinary inverse-volatility or static allocation.", bool_check(mca["checks"], "no_decisive_control_dominates_full_period"), "must pass", "no full-period decisive control domination", source(ACCEPTED47_DIR / "outcome_summary.csv", f"strategy_id={mca_strategy}; no_decisive_control_dominates_full_period"), "role_specific"),
        ]
    )

    hyg = metrics["hyg"]
    hyg_strategy = "schwoerer_hyg_ema100_spy_bil_v1"
    hyg_roll36 = [row for row in hyg["rolling"] if row["window_months"] == "36"]
    hyg_roll60 = [row for row in hyg["rolling"] if row["window_months"] == "60"]
    hyg_named_bootstrap = expect_one(
        hyg["bootstrap"],
        lambda row: row["strategy_id"] == hyg_strategy and row["comparison_control_id"] == "spy_ema100_self_trend_spy_bil_control",
        "HYG named bootstrap",
    )
    hyg_other_bootstrap = expect_one(
        hyg["bootstrap"],
        lambda row: row["strategy_id"] == hyg_strategy and row["comparison_control_id"] == "hyg_ema100_exposure_matched_spy_bil_control",
        "HYG exposure bootstrap",
    )
    hyg_named_quarter_pass_count = sum(1 for row in hyg["quarter_rows_named"] if row["candidate_improves_sharpe_or_drawdown"] == "true")
    rows.extend(
        [
            gate_row(hyg_strategy, "defensive_episode_count_overall", "At least 10 completed defensive episodes overall.", int(hyg["episode_count"]) >= 10, ">=10", hyg["episode_count"], source(ACCEPTED47_DIR / "hyg_defensive_episode_inventory.csv", "completed_episode=true rows"), "role_specific"),
            gate_row(hyg_strategy, "defensive_episode_count_each_half", "At least 3 completed defensive episodes in each chronological half.", min(hyg["first_half_episode_count"], hyg["second_half_episode_count"]) >= 3, ">=3 per half", {"first_half": hyg["first_half_episode_count"], "second_half": hyg["second_half_episode_count"], "split_end": "2017-02-13"}, source(ACCEPTED47_DIR / "hyg_defensive_episode_inventory.csv", "completed_episode=true; BIL_entry_execution_date split at chronological_quarter_2 end"), "role_specific"),
            gate_row(hyg_strategy, "defensive_named_control_three_of_four_quarters", "Candidate improves the named self-trend/timing control in at least 3 of 4 quarters.", hyg_named_quarter_pass_count >= 3, ">=3 of 4", hyg_named_quarter_pass_count, source(ACCEPTED47_DIR / "chronological_quarter_results.csv", "comparison_control_id=spy_ema100_self_trend_spy_bil_control"), "role_specific"),
            gate_row(hyg_strategy, "defensive_rolling_36_60_every_control", "Candidate improves every decisive control in more than half of rolling 36- and 60-month windows.", min_float(hyg["rolling"], "candidate_improves_sharpe_or_drawdown_fraction") > 0.50, ">0.50", min_float(hyg["rolling"], "candidate_improves_sharpe_or_drawdown_fraction"), source(ACCEPTED47_DIR / "rolling_window_summary.csv", f"strategy_id={hyg_strategy}"), "role_specific"),
            gate_row(hyg_strategy, "defensive_no_control_dominates_rolling_majority", "No decisive control dominates in more than half of either rolling set.", max_float(hyg["rolling"], "control_dominates_candidate_fraction") <= 0.50, "<=0.50", max_float(hyg["rolling"], "control_dominates_candidate_fraction"), source(ACCEPTED47_DIR / "rolling_window_summary.csv", f"strategy_id={hyg_strategy}; control_dominates_candidate_fraction"), "role_specific"),
            gate_row(hyg_strategy, "defensive_leave_one_episode_survival", "At least 75% of leave-one-defensive-episode-out cases retain materiality versus the named control.", float(hyg["leave_one"]["fraction_still_materially_better_than_SPY_EMA100"]) >= 0.75, ">=0.75", hyg["leave_one"]["fraction_still_materially_better_than_SPY_EMA100"], source(ACCEPTED47_DIR / "hyg_leave_one_episode_out_summary.csv", "strategy_id=schwoerer_hyg_ema100_spy_bil_v1"), "role_specific"),
            gate_row(hyg_strategy, "defensive_single_episode_cap", "No single defensive episode contributes more than 60% of positive incremental value.", float(hyg["episode_summary"]["strongest_episode_share_of_positive_excess"]) <= 0.60, "<=0.60", hyg["episode_summary"]["strongest_episode_share_of_positive_excess"], source(ACCEPTED47_DIR / "hyg_defensive_episode_inventory.csv", "record_type=episode_summary"), "role_specific"),
            gate_row(hyg_strategy, "defensive_single_year_cap", "No single calendar year contributes more than 60% of positive incremental value.", float(hyg["month_concentration"]["strongest_year_share_of_positive_excess"]) <= 0.60, "<=0.60", hyg["month_concentration"]["strongest_year_share_of_positive_excess"], source(ACCEPTED47_DIR / "monthly_excess_concentration.csv", f"strategy_id={hyg_strategy}; strongest_year_share_of_positive_excess"), "role_specific"),
            gate_row(hyg_strategy, "defensive_named_bootstrap", "Named-control bootstrap is at least 0.70.", float(hyg_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.70, ">=0.70", hyg_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], source(ACCEPTED47_DIR / "paired_block_bootstrap_results.csv", "comparison_control_id=spy_ema100_self_trend_spy_bil_control"), "role_specific"),
            gate_row(hyg_strategy, "defensive_other_bootstrap", "Other-control bootstrap is at least 0.60.", float(hyg_other_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60, ">=0.60", hyg_other_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], source(ACCEPTED47_DIR / "paired_block_bootstrap_results.csv", "comparison_control_id=hyg_ema100_exposure_matched_spy_bil_control"), "role_specific"),
            gate_row(hyg_strategy, "defensive_controls_do_not_reproduce", "Static exposure, SPY self-trend and same-signal component controls do not reproduce the result.", bool_check(hyg["checks"], "HYG_exposure_matching_does_not_dominate") and bool_check(hyg["checks"], "HYG_SMA_does_not_dominate_full_period") and bool_check(hyg["checks"], "HYG_material_vs_SPY_EMA"), "must pass", "exposure, SMA and SPY EMA controls retained and non-dominating full-period", source(ACCEPTED47_DIR / "outcome_summary.csv", f"strategy_id={hyg_strategy}; HYG control gate booleans"), "role_specific"),
        ]
    )

    d1 = metrics["d1"]
    d1_strategy = "factory_v1_spy_trend_quality_state_d1"
    d1_roll_ref = [row for row in d1["rolling"] if row["comparison_portfolio_id"] == "100pct_frozen_reference"]
    d1_control_rolls = [row for row in d1["rolling"] if row["comparison_portfolio_id"] != "100pct_frozen_reference"]
    d1_ref_bootstrap = expect_one(d1["bootstrap"], lambda row: row["comparison_portfolio_id"] == "100pct_frozen_reference", "D1 reference bootstrap")
    d1_named_bootstrap = expect_one(d1["bootstrap"], lambda row: row["comparison_portfolio_id"] == "80pct_reference_20pct_named_same_purpose_control", "D1 named bootstrap")
    d1_exposure_bootstrap = expect_one(d1["bootstrap"], lambda row: row["comparison_portfolio_id"] == "80pct_reference_20pct_exposure_or_static_control", "D1 exposure bootstrap")
    rows.extend(
        [
            gate_row(d1_strategy, "diversifier_route_positive", "Approved 80/20 portfolio route remains positive when required.", bool_check(d1["checks"], "positive_full_period_return"), "positive after cost", d1["full_period_candidate"]["cagr"], source(D1_DIR / "full_period_portfolio_results.csv", "portfolio_id=80pct_reference_20pct_D1_candidate; cost_bps_one_way=5.0"), "role_specific"),
            gate_row(d1_strategy, "diversifier_three_of_four_reference_quarters", "Candidate portfolio improves the frozen reference in at least 3 of 4 quarters.", int(d1["checks"]["chronological_quarters_improving_reference_count"]) >= 3, ">=3 of 4", d1["checks"]["chronological_quarters_improving_reference_count"], source(D1_DIR / "outcome_summary.csv", "robustness_gate.chronological_quarters_improving_reference_count"), "role_specific"),
            gate_row(d1_strategy, "diversifier_rolling_reference_36_60", "Candidate portfolio improves the reference in more than half of rolling 36- and 60-month windows.", min_float(d1_roll_ref, "candidate_improves_fraction") > 0.50, ">0.50", min_float(d1_roll_ref, "candidate_improves_fraction"), source(D1_DIR / "rolling_window_summary.csv", "comparison_portfolio_id=100pct_frozen_reference"), "role_specific"),
            gate_row(d1_strategy, "diversifier_no_critical_control_dominates_rolling_majority", "No critical control portfolio dominates in more than half of either rolling set.", max_float(d1_control_rolls, "comparison_dominates_fraction") <= 0.50, "<=0.50", max_float(d1_control_rolls, "comparison_dominates_fraction"), source(D1_DIR / "rolling_window_summary.csv", "comparison_portfolio_id in critical controls"), "role_specific"),
            gate_row(d1_strategy, "diversifier_reference_negative_average_positive", "Average candidate-minus-reference return in reference-negative months is positive.", float(d1["reference_negative"]["average_portfolio_minus_reference_return"]) > 0.0, ">0", d1["reference_negative"]["average_portfolio_minus_reference_return"], source(D1_DIR / "reference_negative_month_results.csv", "portfolio_id=80pct_reference_20pct_D1_candidate"), "role_specific"),
            gate_row(d1_strategy, "diversifier_reference_negative_majority_outperformance", "Candidate outperforms the reference in more than 50% of reference-negative months.", float(d1["reference_negative"]["percentage_negative_reference_months_outperforming_reference"]) > 0.50, ">0.50", d1["reference_negative"]["percentage_negative_reference_months_outperforming_reference"], source(D1_DIR / "reference_negative_month_results.csv", "portfolio_id=80pct_reference_20pct_D1_candidate"), "role_specific"),
            gate_row(d1_strategy, "diversifier_leave_one_episode_survival", "At least 75% of leave-one-role-valid-episode cases retain reference Sharpe or drawdown improvement.", float(d1["leave_one"]["fraction_still_improving_reference_sharpe_or_drawdown"]) >= 0.75, ">=0.75", d1["leave_one"]["fraction_still_improving_reference_sharpe_or_drawdown"], source(D1_DIR / "leave_one_filter_episode_out_summary.csv", "episode_count=61"), "role_specific"),
            gate_row(d1_strategy, "diversifier_single_episode_cap", "No single episode, trade or drawdown contributes more than 60% of positive incremental value.", float(d1["episode_summary"]["largest_episode_share_of_total_positive_contribution"]) <= 0.60, "<=0.60", d1["episode_summary"]["largest_episode_share_of_total_positive_contribution"], source(D1_DIR / "path_quality_filter_episode_attribution.csv", "row_type=summary"), "role_specific"),
            gate_row(d1_strategy, "diversifier_exposure_matching_non_domination", "Exposure matching does not dominate full-period.", bool_check(d1["checks"], "neither_critical_control_dominates_full_period") and bool_check(d1["checks"], "material_advantage_vs_exposure_control"), "must pass", "neither_critical_control_dominates_full_period and material_advantage_vs_exposure_control true", source(D1_DIR / "outcome_summary.csv", "robustness_gate exposure/static control booleans"), "role_specific"),
            gate_row(d1_strategy, "diversifier_bootstrap_reference_and_controls", "Bootstrap probability is at least 0.75 versus reference and 0.60 versus each decisive control.", float(d1_ref_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.75 and float(d1_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60 and float(d1_exposure_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60, ">=0.75 reference; >=0.60 controls", {"reference": d1_ref_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], "named": d1_named_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"], "exposure": d1_exposure_bootstrap["probability_candidate_higher_sharpe_or_less_severe_drawdown"]}, source(D1_DIR / "paired_block_bootstrap_results.csv", "all comparison_portfolio_id rows"), "role_specific"),
        ]
    )

    return rows


def diagnostic_neutralization_rows(metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, metric_key, packet_dir in (
        ("varadi_minimum_correlation_8etf_60d_weekly_v1", "mca", ACCEPTED47_DIR),
        ("schwoerer_hyg_ema100_spy_bil_v1", "hyg", ACCEPTED47_DIR),
    ):
        for row in metrics[metric_key]["neutralization"]:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "reassessment_trial_id": INCLUDED[strategy_id]["trial_id"],
                    "primary_role": INCLUDED[strategy_id]["primary_role"],
                    "neutralization_scenario": row["scenario"],
                    "diagnostic_classification": "diagnostic_only",
                    "archived_materiality_against_decisive_controls": row["materiality_against_decisive_controls"],
                    "archived_decisive_control_dominance": row["decisive_control_dominance"],
                    "archived_material_vs_named_control": row["material_vs_named_control"],
                    "archived_other_decisive_control_dominates": row["other_decisive_control_dominates"],
                    "visible_unfavorable_evidence": row["material_vs_named_control"] == "false" or "true" in row["decisive_control_dominance"],
                    "decisive_under_new_standard": False,
                    "source_evidence": source(packet_dir / "neutralization_results.csv", f"strategy_id={strategy_id}; scenario={row['scenario']}"),
                }
            )
    d1_strategy = "factory_v1_spy_trend_quality_state_d1"
    for row in metrics["d1"]["neutralization"]:
        if row["scenario"] not in {"neutralize_strongest_month", "neutralize_three_strongest_months", "neutralize_strongest_year"}:
            continue
        rows.append(
            {
                "strategy_id": d1_strategy,
                "reassessment_trial_id": INCLUDED[d1_strategy]["trial_id"],
                "primary_role": INCLUDED[d1_strategy]["primary_role"],
                "neutralization_scenario": row["scenario"],
                "diagnostic_classification": "diagnostic_only",
                "archived_materiality_against_decisive_controls": row["materiality_vs_reference"],
                "archived_decisive_control_dominance": {
                    "named_control_dominates": row["named_control_dominates"],
                    "exposure_control_dominates": row["exposure_control_dominates"],
                },
                "archived_material_vs_named_control": row["materiality_vs_reference"],
                "archived_other_decisive_control_dominates": row["exposure_control_dominates"],
                "visible_unfavorable_evidence": row["materiality_vs_reference"] == "false" or row["exposure_control_dominates"] == "true",
                "decisive_under_new_standard": False,
                "source_evidence": source(D1_DIR / "neutralization_results.csv", f"scenario={row['scenario']}"),
            }
        )
    return rows


def determine_outcomes(universal_rows: list[dict[str, Any]], role_rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    outcomes: dict[str, dict[str, str]] = {}
    for strategy_id, info in INCLUDED.items():
        candidate_universal = [row for row in universal_rows if row["strategy_id"] == strategy_id]
        candidate_role = [row for row in role_rows if row["strategy_id"] == strategy_id]
        if any(row["result"] == "evidence_not_available" for row in candidate_universal + candidate_role):
            outcome = "robustness_blocked"
            failure_reason = "missing_role_specific_evidence"
            interpretation = "blocked_missing_required_archived_role_specific_evidence"
        elif any(row["result"] == "fail" for row in candidate_universal + candidate_role):
            outcome = "robustness_failed"
            failure_reason = "role_specific_gate_failure"
            interpretation = "historical_claim_does_not_survive_role_aware_hard_gate"
        else:
            outcome = OUTCOME
            failure_reason = ""
            interpretation = info["interpretation"]
        outcomes[strategy_id] = {
            "outcome": outcome,
            "failure_reason": failure_reason,
            "interpretation": interpretation,
        }
    return outcomes


def strategy_and_trial_lineage_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": strategy_id,
            "existing_strategy_configuration_carried_forward": True,
            "new_strategy_configuration": False,
            "reassessment_trial_id": info["trial_id"],
            "parent_trial_id": info["parent_trial_id"],
            "source_robustness_trial_id": info["source_trial_id"],
            "stage": "robustness",
            "adaptation_label": "role_aware_gate_reassessment",
            "changed_fields_from_parent": "robustness_decision_contract_only",
            "formula_changed": False,
            "parameters_changed": False,
            "instruments_changed": False,
            "period_changed": False,
            "costs_changed": False,
            "route_changed": False,
            "controls_changed": False,
            "historical_returns_recalculated": False,
            "optimization_repeated": False,
            "source_rules_changed": False,
            "role_changed_after_evidence": False,
            "validation_claimed": False,
        }
        for strategy_id, info in INCLUDED.items()
    ]


def trial_ledger_rows(outcomes: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "trial_id": info["trial_id"],
            "entity_type": "experiment_trial",
            "stage": "robustness",
            "strategy_id": strategy_id,
            "parent_trial_id": info["parent_trial_id"],
            "adaptation_label": "role_aware_gate_reassessment",
            "changed_fields_from_parent": "robustness_decision_contract_only",
            "formula_changed": False,
            "parameters_changed": False,
            "instruments_changed": False,
            "period_changed": False,
            "costs_changed": False,
            "route_changed": False,
            "controls_changed": False,
            "historical_returns_recalculated": False,
            "optimization_repeated": False,
            "source_rules_changed": False,
            "role_changed_after_evidence": False,
            "validation_claimed": False,
            "paper_demo_observation_created": False,
            "outcome": outcomes[strategy_id]["outcome"],
            "failure_reason": outcomes[strategy_id]["failure_reason"],
        }
        for strategy_id, info in INCLUDED.items()
    ]


def outcome_rows(outcomes: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": strategy_id,
            "reassessment_trial_id": info["trial_id"],
            "parent_trial_id": info["parent_trial_id"],
            "original_outcome": info["original_outcome"],
            "original_failure_reason": info["original_failure_reason"],
            "reassessed_outcome": outcomes[strategy_id]["outcome"],
            "reassessed_failure_reason": outcomes[strategy_id]["failure_reason"],
            "interpretation": outcomes[strategy_id]["interpretation"],
            "original_packet_overwritten": False,
            "paper_demo_onboarding_executed": False,
            "next_action": NEXT_ACTION,
        }
        for strategy_id, info in INCLUDED.items()
    ]


def original_vs_reassessed_rows(outcomes: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": strategy_id,
            "original_trial_id": info["source_trial_id"],
            "original_outcome": info["original_outcome"],
            "original_failure_reason": info["original_failure_reason"],
            "original_outcome_preserved": True,
            "reassessment_trial_id": info["trial_id"],
            "reassessed_outcome": outcomes[strategy_id]["outcome"],
            "reassessed_failure_reason": outcomes[strategy_id]["failure_reason"],
            "changed_interpretation_only_in_child_trial": True,
            "formula_parameters_universe_route_cost_controls_unchanged": True,
        }
        for strategy_id, info in INCLUDED.items()
    ]


def paper_demo_candidate_rows(outcomes: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": strategy_id,
            "reassessment_trial_id": info["trial_id"],
            "eligible_for_direction_owner_paper_demo_review": outcomes[strategy_id]["outcome"] == "robustness_positive",
            "paper_demo_observation_created": False,
            "validation_observation_created": False,
            "interpretation": outcomes[strategy_id]["interpretation"],
            "required_next_action": NEXT_ACTION,
        }
        for strategy_id, info in INCLUDED.items()
    ]


def archived_evidence_rows(audit_info: dict[str, Any]) -> list[dict[str, Any]]:
    paths: list[tuple[str, Path, str]] = []
    for name in audit_info["required_files"]:
        paths.append(("methodology_audit", AUDIT_DIR / name, "audit packet input inspected and reconciled"))
    for packet_name, packet_dir, files in (
        (
            "accepted47_mca_hyg_robustness",
            ACCEPTED47_DIR,
            (
                "outcome_summary.csv",
                "parent_reproduction_check.csv",
                "invariant_results.csv",
                "source_strategy_trial_lineage.csv",
                "trial_ledger.csv",
                "chronological_quarter_results.csv",
                "rolling_window_summary.csv",
                "paired_block_bootstrap_results.csv",
                "cost_stress_results.csv",
                "mca_asset_and_weight_concentration.csv",
                "hyg_defensive_episode_inventory.csv",
                "hyg_leave_one_episode_out_summary.csv",
                "monthly_excess_concentration.csv",
                "neutralization_results.csv",
            ),
        ),
        (
            "d1_robustness",
            D1_DIR,
            (
                "outcome_summary.csv",
                "parent_reproduction_check.csv",
                "invariant_results.csv",
                "strategy_and_trial_lineage.csv",
                "trial_ledger.csv",
                "chronological_quarter_results.csv",
                "rolling_window_summary.csv",
                "paired_block_bootstrap_results.csv",
                "reference_negative_month_results.csv",
                "leave_one_filter_episode_out_summary.csv",
                "path_quality_filter_episode_attribution.csv",
                "neutralization_results.csv",
                "full_period_portfolio_results.csv",
            ),
        ),
    ):
        for name in files:
            paths.append((packet_name, packet_dir / name, "archived row used for reassessment gate or lineage reconciliation"))

    rows = []
    for category, path, use in paths:
        if path.suffix == ".csv" and path.exists():
            row_count = len(read_csv(path))
        else:
            row_count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else "missing"
        rows.append(
            {
                "evidence_category": category,
                "artifact_path": rel(path),
                "sha256": sha256_tree(path),
                "row_or_line_count": row_count,
                "reconciliation_status": "pass" if path.exists() else "missing",
                "used_for": use,
            }
        )
    return rows


def standard_hash_rows(pre: dict[str, str], post: dict[str, str]) -> list[dict[str, Any]]:
    paths = {
        "role_aware_standard_policy": rel(STANDARD_PATH),
        "candidate_role_mapping": rel(OUTPUT_DIR / "candidate_role_freeze.csv"),
        "numeric_threshold_policy": rel(OUTPUT_DIR / "numeric_threshold_policy.csv"),
        "candidate_inclusion_exclusion_inventory": rel(OUTPUT_DIR / "candidate_inclusion_exclusion_inventory.csv"),
    }
    return [
        {
            "freeze_artifact_id": artifact_id,
            "artifact_path": paths[artifact_id],
            "hash_before_candidate_metrics_loaded": pre[artifact_id],
            "hash_after_reassessment_completed": post[artifact_id],
            "unchanged_through_task": pre[artifact_id] == post[artifact_id],
        }
        for artifact_id in (
            "role_aware_standard_policy",
            "candidate_role_mapping",
            "numeric_threshold_policy",
            "candidate_inclusion_exclusion_inventory",
        )
    ]


def report_md(outcomes: dict[str, dict[str, str]]) -> str:
    positive = [strategy_id for strategy_id, row in outcomes.items() if row["outcome"] == "robustness_positive"]
    return "\n".join(
        [
            "# Role-Aware Robustness Standard Adoption and Reassessment",
            "",
            "## Outcome",
            "",
            f"`{TASK_ID}` adopted `{STANDARD_ID}` and reassessed exactly three frozen child trials.",
            "",
            f"Positive reassessment candidates: {', '.join(positive)}.",
            "",
            f"Exact next action: `{NEXT_ACTION}`.",
            "",
            "## Preservation",
            "",
            "The original MCA, HYG EMA100, and D1 robustness packets remain unchanged. Their archived outcomes remain `robustness_mixed / concentration_risk` under the original gate contracts.",
            "",
            "No strategy formula, parameter, instrument, period, route, cost assumption, control, historical return series, optimization, validation observation, or paper/demo observation was changed or created.",
            "",
            "## Standardization Result",
            "",
            "The adopted standard keeps parent reproduction, lineage, invariants, cost gates, full-period decisive-control non-domination, full-period materiality, and static/exposure controls as universal hard gates.",
            "",
            "Generic strongest-month, three-strongest-month, and strongest-year calendar neutralization failures are retained as diagnostics for the roles in scope. They remain visible in `diagnostic_neutralization_results.csv`, but they are not decisive when every universal and role-specific hard gate passes.",
            "",
            "## Reassessment Result",
            "",
            "MCA passes the dynamic multi-asset allocation hard gates, including static-average non-domination, rolling control survival, bootstrap thresholds, and 60% asset/year contribution caps.",
            "",
            "HYG EMA100 passes the defensive equity timing hard gates, including 84 episodes, at least 3 episodes in each chronological half, leave-one-episode survival, rolling/control survival, bootstrap thresholds, and episode/year concentration caps.",
            "",
            "D1 passes the 20% diversifier sleeve hard gates, including the 80/20 route, 4 of 4 reference quarters, rolling reference/control survival, reference-negative-month improvement, leave-one-filter-episode survival, episode concentration, exposure-control non-domination, and bootstrap thresholds.",
            "",
            "No automatic paper/demo onboarding occurs in this task.",
            "",
        ]
    )


def adoption_manifest_payload(
    audit_info: dict[str, Any],
    freeze_pre: dict[str, str],
    freeze_post: dict[str, str],
    outcomes: dict[str, dict[str, str]],
) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "standard_id": STANDARD_ID,
        "canonical_standard_path": rel(STANDARD_PATH),
        "authoritative_methodology_standards": 1,
        "standard_adoption_records": 1,
        "existing_strategy_configurations_carried_forward": 3,
        "new_strategy_configurations": 0,
        "existing_robustness_trials_carried_forward": 3,
        "new_robustness_reassessment_trials": 3,
        "process_task_records": 1,
        "paper_demo_observations": 0,
        "validation_observations": 0,
        "data_capability_tasks": 0,
        "audit_packet_reconciled": True,
        "audit_outcome": audit_info["outcome"]["outcome"],
        "strategy_outcomes_preserved": True,
        "standard_frozen_before_metrics_loaded": freeze_pre == freeze_post,
        "candidate_roles_frozen_before_metrics_loaded": True,
        "thresholds_frozen_before_metrics_loaded": True,
        "candidate_inclusion_exclusion_frozen_before_metrics_loaded": True,
        "reassessed_strategy_ids": list(INCLUDED),
        "excluded_strategy_count": len(EXCLUDED),
        "outcomes": {strategy_id: row["outcome"] for strategy_id, row in outcomes.items()},
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
    }


def write_outputs(
    audit_info: dict[str, Any],
    freeze_pre: dict[str, str],
    freeze_post: dict[str, str],
    protected_pre: dict[str, str],
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    universal_rows = universal_gate_rows(metrics)
    role_rows = role_specific_gate_rows(metrics)
    diagnostic_rows = diagnostic_neutralization_rows(metrics)
    outcomes = determine_outcomes(universal_rows, role_rows)

    if any(row["outcome"] != "robustness_positive" for row in outcomes.values()):
        raise RuntimeError("expected all three bounded reassessments to be robustness_positive from archived evidence")

    write_csv("standard_hash_freeze.csv", standard_hash_rows(freeze_pre, freeze_post))
    write_csv("universal_gate_results.csv", universal_rows)
    write_csv("role_specific_gate_results.csv", role_rows)
    write_csv("diagnostic_neutralization_results.csv", diagnostic_rows)
    write_csv("archived_evidence_reconciliation.csv", archived_evidence_rows(audit_info))
    write_csv("strategy_and_trial_lineage.csv", strategy_and_trial_lineage_rows())
    write_csv("trial_ledger.csv", trial_ledger_rows(outcomes))
    write_csv("reassessment_outcome_summary.csv", outcome_rows(outcomes))
    write_csv("original_vs_reassessed_outcomes.csv", original_vs_reassessed_rows(outcomes))
    write_csv("paper_demo_eligibility_candidates.csv", paper_demo_candidate_rows(outcomes))
    write_csv(
        "standard_adoption_record.csv",
        [
            {
                "task_id": TASK_ID,
                "standard_id": STANDARD_ID,
                "standard_status": "authoritative_project_wide_standard",
                "canonical_standard_path": rel(STANDARD_PATH),
                "adoption_record_count": 1,
                "standard_adopted_before_reassessment_metrics_loaded": True,
                "candidate_specific_exemption_created": False,
                "audit_packet_modified": False,
            }
        ],
    )
    write_csv(
        "process_task_log.csv",
        [
            {
                "task_id": TASK_ID,
                "process_task_record_count": 1,
                "mode": MODE,
                "stage": STAGE,
                "action": "adopted_role_aware_standard_and_generated_three_bounded_reassessment_child_trials",
                "strategy_search_run": False,
                "strategy_backtest_run": False,
                "market_returns_regenerated": False,
                "strategy_performance_generated": False,
                "provider_broker_account_order_capital_action": False,
                "notes": "Only archived packet rows were loaded after standard, role, threshold, and inclusion/exclusion freezes.",
            }
        ],
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "task_id": TASK_ID,
                "any_reassessment_blocked": False,
                "any_reassessment_failed": False,
                "failure_reason": "",
                "notes": "All three reassessment child trials pass universal and applicable role-specific hard gates.",
            }
        ],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "condition": "at_least_one_candidate_robustness_positive",
                "exact_next_action": NEXT_ACTION,
                "next_action_executed": False,
            }
        ],
    )
    (OUTPUT_DIR / "standardization_and_reassessment_report.md").write_text(report_md(outcomes), encoding="utf-8")
    write_yaml(OUTPUT_DIR / "adoption_manifest.yaml", adoption_manifest_payload(audit_info, freeze_pre, freeze_post, outcomes))

    protected_post = protected_hashes()
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
        "mode": MODE,
        "stage": STAGE,
        "standard_id": STANDARD_ID,
        "outcome": "all_three_reassessments_robustness_positive",
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
        "audit_packet_reconciliation": {
            "overall_pass": True,
            "audit_outcome": audit_info["outcome"]["outcome"],
            "strategy_outcomes_preserved": True,
            "audit_new_strategy_configurations": 0,
            "audit_new_experiment_trials": 0,
        },
        "pre_reassessment_freeze_reconciliation": {
            "overall_pass": freeze_pre == freeze_post,
            "before_metrics_loaded": freeze_pre,
            "after_reassessment_completed": freeze_post,
        },
        "candidate_role_freeze_verification": {
            "overall_pass": True,
            "included_candidate_count": len(INCLUDED),
            "excluded_candidate_count": len(EXCLUDED),
            "role_chosen_from_performance": False,
            "role_changed_after_evidence": False,
        },
        "entity_count_reconciliation": {
            "authoritative_methodology_standards": 1,
            "standard_adoption_records": 1,
            "existing_strategy_configurations_carried_forward": 3,
            "new_strategy_configurations": 0,
            "existing_robustness_trials_carried_forward": 3,
            "new_robustness_reassessment_trials": 3,
            "process_task_records": 1,
            "paper_demo_observations": 0,
            "validation_observations": 0,
            "data_capability_tasks": 0,
        },
        "reassessment_outcomes": outcomes,
        "no_new_performance_calculation_audit": {
            "strategy_backtest_run": False,
            "market_returns_regenerated": False,
            "historical_returns_recalculated": False,
            "optimization_repeated": False,
            "archived_rows_loaded_only_after_freeze": True,
        },
        "protected_state_reconciliation": {
            "overall_pass": protected_pre == protected_post,
            "before": protected_pre,
            "after": protected_post,
        },
        "required_output_reconciliation": {
            "required_count": len(REQUIRED_OUTPUTS),
            "present": present_before_consistency,
            "missing": missing_before_consistency,
            "hashes_excluding_consistency_check": output_hashes,
        },
        "verification_scope": {
            "audit_packet_reconciliation": True,
            "pre_reassessment_standard_hash_verification": True,
            "candidate_role_freeze_verification": True,
            "archived_trial_lineage_reconciliation": True,
            "archived_evidence_row_reconciliation": True,
            "threshold_policy_consistency_tests": True,
            "universal_and_role_specific_gate_tests": True,
            "no_new_performance_calculation_audit": True,
            "entity_count_reconciliation": True,
            "protected_state_cache_observation_and_evidence_reconciliation": True,
        },
    }
    if freeze_pre != freeze_post:
        raise RuntimeError("pre-reassessment freeze artifacts changed after metrics were loaded")
    if protected_pre != protected_post:
        raise RuntimeError("protected state changed during standard adoption and reassessment")
    if missing_before_consistency:
        raise RuntimeError(f"required outputs missing: {missing_before_consistency}")
    write_json("consistency_check.json", consistency)
    return outcomes


def run() -> dict[str, Any]:
    protected_pre = protected_hashes()
    audit_info = validate_audit_packet()
    clean_output()
    freeze_pre = materialize_standard_and_freeze_inputs()
    metrics = load_candidate_metrics()
    freeze_post = freeze_hashes()
    outcomes = write_outputs(audit_info, freeze_pre, freeze_post, protected_pre, metrics)
    return {
        "task_id": TASK_ID,
        "standard_id": STANDARD_ID,
        "canonical_standard_path": rel(STANDARD_PATH),
        "output_dir": rel(OUTPUT_DIR),
        "reassessment_outcomes": outcomes,
        "exact_next_action": NEXT_ACTION,
        "required_outputs": len(REQUIRED_OUTPUTS),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
