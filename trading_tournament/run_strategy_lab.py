from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY = REPO_ROOT / "strategy_lab" / "strategy_registry.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evidence" / "strategy_lab"
REQUIRED_EVIDENCE_FILES = [
    "README_FOR_AUDITOR.md",
    "strategy_lab_summary.md",
    "strategy_registry_snapshot.csv",
    "strategy_versions.csv",
    "active_paper_forward_freeze.csv",
    "experiment_queue.csv",
    "promotion_status.csv",
    "blocked_items.csv",
    "registry_validation.json",
    "warnings_and_limitations.md",
]
REQUIRED_FIELDS = [
    "id",
    "display_name",
    "lane",
    "instrument_family",
    "strategy_family",
    "version",
    "parent_id",
    "credibility_tier",
    "status",
    "role",
    "rules_frozen",
    "paper_forward_active",
    "implementation_status",
    "data_source",
    "evidence_source",
    "latest_evidence_path",
    "latest_known_result_summary",
    "allowed_next_action",
    "forbidden_next_actions",
    "promotion_requirements",
    "demotion_or_kill_criteria",
    "notes",
]
PROMOTION_CONTROL_FIELDS = [
    "strategy_id",
    "family",
    "instrument_lane",
    "evidence_tier",
    "current_status",
    "allowed_next_actions",
    "candidate_exhaustive_run",
    "candidate_exhaustive_recommended",
    "promotion_review_required",
    "promotion_decision",
    "promotion_reason",
    "primary_failure_mode",
    "duplication_risk",
    "risk_budget_status",
    "evidence_needed",
    "duplicate_of",
    "blocked_reason",
]
RISK_FRAMEWORK_FIELDS = [
    "risk_framework_status",
    "paper_forward_allowed_by_risk_framework",
    "promotion_blockers",
]
ALLOWED_LANES = {
    "paper_forward",
    "compact_challenge",
    "etf_research",
    "crypto_exploratory",
    "stock_memo",
    "options_memo",
    "futures_memo",
    "forex_memo",
    "volatility_memo",
    "intraday_memo",
    "profit_exploration",
    "strategy_candidate_queue",
    "archive",
}
ALLOWED_TIERS = {
    "tier0_research_map",
    "tier0_research_idea",
    "tier1_research_queue",
    "tier1_exploratory",
    "tier1_or_tier2_exploratory",
    "tier2_exploratory",
    "tier2_credible_prototype",
    "tier2_credible_prototype_candidate",
    "tier3_candidate_validation",
    "tier3_candidate_validation_candidate",
    "tier4_paper_forward",
    "benchmark",
    "blocked",
    "blocked_by_gate",
}
ALLOWED_STATUSES = {
    "active_observation",
    "active_paper_demo_observation",
    "active_observation_running",
    "candidate_exhaustive_completed",
    "implement_next_after_current_validation",
    "implemented_research_sample",
    "frozen_control",
    "gated",
    "historical_leader",
    "research_queue",
    "data_acquisition_required",
    "data_acquisition_review_required",
    "data_acquisition_review_complete",
    "provider_terms_review_required",
    "conditional_pending_product_identity_terms_review",
    "fast_exploratory_screen_completed",
    "approve_future_yfinance_download_prompt_pdbc_comt_only",
    "approve_future_yfinance_download_prompt_all_reviewed_symbols",
    "defer_high_wrapper_risk",
    "data_acquisition_review_approved",
    "provider_terms_review_passed",
    "conditional_terms_review_required",
    "conditional_pending_provider_cost_review",
    "gate1c_provider_cost_review_complete",
    "conditional_choose_provider_before_data_acquisition",
    "pursue_serious_provider_review",
    "gate1d_provider_terms_review_complete",
    "conditional_user_must_select_provider",
    "choose_norgate_for_gate1e_acquisition_review",
    "choose_sharadar_for_gate1e_acquisition_review",
    "choose_crsp_if_access_available",
    "defer_until_provider_access_known",
    "gate1e_preflight_complete",
    "approve_future_norgate_tiny_sample_acquisition_prompt",
    "blocked_pending_user_terms_acceptance",
    "blocked_no_local_norgate_access",
    "blocked_field_mapping_unclear",
    "defer_to_sharadar_provider_review",
    "gate1f_sharadar_review_complete",
    "choose_sharadar_for_gate1g_terms_and_tiny_sample_review",
    "conditional_pending_package_and_terms_selection",
    "defer_to_norgate_access_setup",
    "provider_review_required",
    "conditional_pending_data_acquisition",
    "data_acquired_pending_quality_check",
    "data_quality_review_passed",
    "data_acquired_pending_methodology_review",
    "data_quality_review_passed_methodology_review_required",
    "methodology_review_passed_data_limited",
    "conditional_approval_short_history_label_required",
    "methodology_review_required",
    "methodology_or_identity_risk",
    "reject_proxy_not_suitable",
    "gate1b_review_complete",
    "tier1_toy_only",
    "defer_until_survivorship_free_provider",
    "partial_data_acquired_quality_review_required",
    "data_acquisition_failed",
    "data_gated",
    "execution_gated",
    "complexity_gated",
    "duplicate_or_near_duplicate",
    "defer",
    "reject_for_now",
    "promotion_review_passed",
    "paper_forward_observation_plan_approved",
    "paper_forward_candidate",
    "paper_forward_review_required",
    "observation_plan_review",
    "reject_observation_plan_for_now",
    "activation_blocked_rule_hash_missing",
    "activation_waiting_for_data",
    "active_waiting_for_next_cached_trading_day",
    "promotion_review_candidate",
    "watchlist_more_evidence",
    "keep_as_research_candidate",
    "implementation_review_passed",
    "conditional_implementation_review",
    "universe_policy_passed",
    "duplicate_risk_review",
    "research_sample_candidate",
    "candidate_exhaustive_review_required",
    "candidate_diagnostics_review_required",
    "filter_ineffective_or_bug_review",
    "high_upside_high_risk_watchlist",
    "research_sample_candidate_risk_budget_breach",
    "too_slow_defensive_watchlist",
    "watchlist_high_upside_high_drawdown",
    "candidate_exhaustive_queue",
    "deferred_candidate_queue",
    "promotion_candidate_found",
    "watchlist_family",
    "candidate_exhaustive_queue_short_history_labeled",
    "watchlist",
    "watchlist_diagnostic",
    "practical_candidate",
    "benchmark",
    "benchmark_candidate",
    "exploratory_only",
    "too_slow",
    "short_horizon_too_slow",
    "short_history_watchlist",
    "candidate_exhaustive_review_required_short_history_labeled",
    "memo_only",
    "deferred",
    "blocked",
    "shadow_only",
    "archived",
    "rejected",
    "too_risky",
    "reject_proxy_not_useful",
    "incomplete_evidence",
    "duplicate_skipped",
}
ALLOWED_IMPLEMENTATION = {
    "implemented",
    "implemented_exploratory",
    "implemented_research_sample",
    "implemented_research_candidate",
    "duplicate_skipped",
    "incomplete_evidence",
    "memo_only",
    "blocked_by_gate",
    "archived",
    "benchmark_only",
    "not_implemented",
}
ALLOWED_NEXT = {
    "observe_only",
    "compare_only",
    "run_challenge_audit",
    "run_candidate_exhaustive",
    "improve_as_new_version",
    "create_gate0_memo",
    "create_gate1_review",
    "continue_vendor_review",
    "audit_harden",
    "run_profit_exploration",
    "reject_or_archive",
    "no_action",
    "research_memo",
    "data_availability_review",
    "data_acquisition_review",
    "commodity_data_acquisition_review",
    "product_identity_terms_review",
    "create_commodity_data_download_prompt",
    "commodity_product_followup",
    "defer_or_reject",
    "create_commodity_basket_etf_momentum_review",
    "create_treasury_duration_trend_review",
    "create_crypto_tier2_review",
    "create_volatility_proxy_review",
    "create_macro_regime_filter_review",
    "create_factor_sector_extension_review",
    "provider_cost_review",
    "choose_provider_for_terms_review",
    "provider_terms_security_review",
    "gate1e_controlled_acquisition_review",
    "create_norgate_tiny_sample_acquisition_prompt",
    "user_confirm_terms_access",
    "configure_norgate_local_path",
    "defer_to_sharadar_review",
    "sharadar_package_terms_review",
    "user_select_sharadar_package",
    "user_select_provider",
    "provider_access_followup",
    "tier1_toy_exploratory_prompt",
    "tier1_toy_prompt_only",
    "defer_until_provider_available",
    "create_data_download_prompt",
    "provider_terms_review",
    "terms_review_followup",
    "keyed_provider_review",
    "data_quality_review",
    "update_implementation_review_after_data_quality",
    "data_quality_followup",
    "provider_fallback_review",
    "issuer_methodology_review",
    "methodology_followup",
    "defer_until_more_history",
    "reject_for_now",
    "gate1b_review",
    "implementation_review_after_current_validation",
    "universe_review",
    "exact_stream_review",
    "defer_until_data_available",
    "create_new_paper_forward_observation_plan",
    "create_paper_forward_observation_activation_prompt",
    "run_monthly_paper_forward_checkpoint",
    "resolve_activation_blocker",
    "controlled_cache_update_or_next_cached_observation_date",
    "resolve_rule_hash_blocker",
    "create_research_sample_implementation_prompt",
    "duplicate_risk_review",
    "research_sample_review",
    "candidate_exhaustive_review",
    "candidate_exhaustive_review_short_history_gate",
    "create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1",
    "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1",
    "create_paper_forward_review_prompt_for_gror_balanced_momentum_60_40_v1",
    "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
    "archive_gror_balanced_momentum_60_40_v1_as_duplicate_diagnostic",
    "reject_gror_balanced_momentum_60_40_v1_choose_next_lane",
    "create_managed_futures_etf_wrapper_fast_exploration_review_prompt",
}
QUEUE_ACTIONS = {
    "improve_as_new_version",
    "create_gate0_memo",
    "create_gate1_review",
    "continue_vendor_review",
    "audit_harden",
    "run_profit_exploration",
    "run_challenge_audit",
    "research_memo",
    "data_availability_review",
    "data_acquisition_review",
    "commodity_data_acquisition_review",
    "product_identity_terms_review",
    "create_commodity_data_download_prompt",
    "commodity_product_followup",
    "defer_or_reject",
    "create_commodity_basket_etf_momentum_review",
    "create_treasury_duration_trend_review",
    "create_crypto_tier2_review",
    "create_volatility_proxy_review",
    "create_macro_regime_filter_review",
    "create_factor_sector_extension_review",
    "provider_cost_review",
    "choose_provider_for_terms_review",
    "provider_terms_security_review",
    "gate1e_controlled_acquisition_review",
    "create_norgate_tiny_sample_acquisition_prompt",
    "user_confirm_terms_access",
    "configure_norgate_local_path",
    "defer_to_sharadar_review",
    "sharadar_package_terms_review",
    "user_select_sharadar_package",
    "user_select_provider",
    "provider_access_followup",
    "tier1_toy_exploratory_prompt",
    "tier1_toy_prompt_only",
    "defer_until_provider_available",
    "create_data_download_prompt",
    "provider_terms_review",
    "terms_review_followup",
    "keyed_provider_review",
    "data_quality_review",
    "update_implementation_review_after_data_quality",
    "data_quality_followup",
    "provider_fallback_review",
    "issuer_methodology_review",
    "methodology_followup",
    "defer_until_more_history",
    "reject_for_now",
    "gate1b_review",
    "implementation_review_after_current_validation",
    "universe_review",
    "exact_stream_review",
    "defer_until_data_available",
    "run_monthly_paper_forward_checkpoint",
    "resolve_activation_blocker",
    "controlled_cache_update_or_next_cached_observation_date",
    "resolve_rule_hash_blocker",
    "create_research_sample_implementation_prompt",
    "duplicate_risk_review",
    "research_sample_review",
    "candidate_exhaustive_review",
    "candidate_exhaustive_review_short_history_gate",
    "create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1",
    "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1",
    "create_paper_forward_review_prompt_for_gror_balanced_momentum_60_40_v1",
    "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
    "archive_gror_balanced_momentum_60_40_v1_as_duplicate_diagnostic",
    "reject_gror_balanced_momentum_60_40_v1_choose_next_lane",
    "create_managed_futures_etf_wrapper_fast_exploration_review_prompt",
}


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def list_value(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def entries_frame(registry_data: dict[str, Any]) -> pd.DataFrame:
    entries = registry_data.get("strategies", [])
    frame = pd.DataFrame(entries)
    if frame.empty:
        return pd.DataFrame(columns=REQUIRED_FIELDS + PROMOTION_CONTROL_FIELDS)
    for field in REQUIRED_FIELDS + PROMOTION_CONTROL_FIELDS:
        if field not in frame:
            frame[field] = ""
    for field in RISK_FRAMEWORK_FIELDS:
        if field not in frame:
            frame[field] = False if field == "paper_forward_allowed_by_risk_framework" else ""
    for col in ["forbidden_next_actions", "allowed_next_actions"]:
        frame[col] = frame[col].map(list_value)
    return frame[REQUIRED_FIELDS + PROMOTION_CONTROL_FIELDS + RISK_FRAMEWORK_FIELDS]


def validate_registry_data(registry_data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    meta = registry_data.get("registry", {})
    risk_meta = registry_data.get("risk_framework", {})
    entries = registry_data.get("strategies", [])

    for field in ["schema_version", "project", "research_only", "real_money_recommendation", "broker_integration", "live_orders"]:
        if field not in meta:
            errors.append(f"registry metadata missing {field}")
    if meta.get("research_only") is not True:
        errors.append("registry.research_only must be true")
    for field in ["real_money_recommendation", "broker_integration", "live_orders"]:
        if meta.get(field) is not False:
            errors.append(f"registry.{field} must be false")
    if risk_meta.get("active_framework") != "balanced_speculative_research_v1":
        errors.append("risk_framework.active_framework must be balanced_speculative_research_v1")
    if risk_meta.get("framework_path") != "risk_framework/risk_framework.yaml":
        errors.append("risk_framework.framework_path must be risk_framework/risk_framework.yaml")

    seen: set[tuple[str, str]] = set()
    for idx, row in enumerate(entries):
        label = f"row {idx} ({row.get('id', 'missing_id')})"
        for field in REQUIRED_FIELDS + PROMOTION_CONTROL_FIELDS:
            value = row.get(field)
            missing_value = value is None or (isinstance(value, str) and value == "")
            if field not in row or (missing_value and field not in {"parent_id", "duplicate_of", "blocked_reason", "evidence_needed"}):
                errors.append(f"{label} missing required field {field}")
        key = (str(row.get("id", "")), str(row.get("version", "")))
        if key in seen:
            errors.append(f"duplicate id+version: {key[0]} {key[1]}")
        seen.add(key)
        if row.get("lane") not in ALLOWED_LANES:
            errors.append(f"{label} invalid lane {row.get('lane')}")
        if row.get("credibility_tier") not in ALLOWED_TIERS:
            errors.append(f"{label} invalid credibility_tier {row.get('credibility_tier')}")
        if row.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{label} invalid status {row.get('status')}")
        if row.get("implementation_status") not in ALLOWED_IMPLEMENTATION:
            errors.append(f"{label} invalid implementation_status {row.get('implementation_status')}")
        if row.get("allowed_next_action") not in ALLOWED_NEXT:
            errors.append(f"{label} invalid allowed_next_action {row.get('allowed_next_action')}")
        if row.get("real_money_recommendation") not in {None, False}:
            errors.append(f"{label} real_money_recommendation must be false if present")

        if row.get("paper_forward_active"):
            if row.get("paper_forward_allowed_by_risk_framework") is not True:
                errors.append(f"{label} paper-forward active row must be allowed by risk framework")
            if row.get("rules_frozen") is not True:
                errors.append(f"{label} paper-forward active row must have rules_frozen=true")
            if row.get("allowed_next_action") not in {"observe_only", "compare_only", "run_monthly_paper_forward_checkpoint"}:
                errors.append(f"{label} paper-forward active row must be observe_only, compare_only, or run_monthly_paper_forward_checkpoint")
            if row.get("implementation_status") == "blocked_by_gate":
                errors.append(f"{label} paper-forward row cannot be blocked_by_gate")
            if row.get("credibility_tier") == "tier1_exploratory":
                errors.append(f"{label} paper-forward row cannot be tier1_exploratory")

        if row.get("lane") == "crypto_exploratory":
            if row.get("paper_forward_allowed_by_risk_framework") is True:
                errors.append(f"{label} crypto row cannot be paper-forward allowed by risk framework")
            if row.get("credibility_tier") != "tier1_exploratory":
                errors.append(f"{label} crypto row must be tier1_exploratory")
            if row.get("paper_forward_active") is not False:
                errors.append(f"{label} crypto row cannot be paper_forward_active")
            if row.get("status") == "practical_candidate":
                errors.append(f"{label} crypto row cannot be practical_candidate")
            if "leverage" in str(row.get("id", "")).lower() and row.get("status") in {"watchlist", "practical_candidate"}:
                errors.append(f"{label} leverage row cannot be watchlist or practical_candidate")

        if row.get("lane") == "strategy_candidate_queue":
            if row.get("paper_forward_active") is not False:
                errors.append(f"{label} candidate queue row cannot be paper_forward_active")
            if row.get("paper_forward_allowed_by_risk_framework") is True:
                errors.append(f"{label} candidate queue row cannot be paper-forward allowed by risk framework")
            if row.get("implementation_status") != "not_implemented":
                errors.append(f"{label} candidate queue row must be not_implemented")
            if row.get("real_money_recommendation") not in {None, False}:
                errors.append(f"{label} candidate queue row cannot be a real-money recommendation")
            if row.get("allowed_next_action") not in {
                "research_memo",
                "data_availability_review",
                "data_acquisition_review",
                "commodity_data_acquisition_review",
                "product_identity_terms_review",
                "create_commodity_data_download_prompt",
                "commodity_product_followup",
                "defer_or_reject",
                "create_commodity_basket_etf_momentum_review",
                "create_treasury_duration_trend_review",
                "create_crypto_tier2_review",
                "create_volatility_proxy_review",
                "create_macro_regime_filter_review",
                "create_factor_sector_extension_review",
                "provider_cost_review",
                "choose_provider_for_terms_review",
                "provider_terms_security_review",
                "gate1e_controlled_acquisition_review",
                "create_norgate_tiny_sample_acquisition_prompt",
                "user_confirm_terms_access",
                "configure_norgate_local_path",
                "defer_to_sharadar_review",
                "sharadar_package_terms_review",
                "user_select_sharadar_package",
                "user_select_provider",
                "provider_access_followup",
                "tier1_toy_exploratory_prompt",
                "tier1_toy_prompt_only",
                "defer_until_provider_available",
                "create_data_download_prompt",
                "provider_terms_review",
                "terms_review_followup",
                "keyed_provider_review",
                "data_quality_review",
                "update_implementation_review_after_data_quality",
                "data_quality_followup",
                "provider_fallback_review",
                "issuer_methodology_review",
                "methodology_followup",
                "defer_until_more_history",
                "reject_for_now",
                "gate1b_review",
                "implementation_review_after_current_validation",
                "universe_review",
                "exact_stream_review",
                "defer_until_data_available",
                "create_research_sample_implementation_prompt",
                "duplicate_risk_review",
            }:
                errors.append(f"{label} candidate queue allowed_next_action must stay gate/review only")
            forbidden = set(row.get("forbidden_next_actions", []))
            for blocked_action in {"run_backtest", "observe_as_paper_forward", "promote_to_real_money", "add_broker_integration", "tune_parameters", "skip_gates"}:
                if blocked_action not in forbidden:
                    errors.append(f"{label} candidate queue missing forbidden action {blocked_action}")

        if row.get("id") == "individual_stock_momentum_gate1a":
            if row.get("paper_forward_allowed_by_risk_framework") is True:
                errors.append(f"{label} stock memo cannot be paper-forward allowed by risk framework")
            if row.get("status") not in {"deferred", "blocked"}:
                errors.append(f"{label} stock memo must remain deferred or blocked")
            if row.get("implementation_status") != "blocked_by_gate":
                errors.append(f"{label} stock memo must be blocked_by_gate")
            if row.get("allowed_next_action") not in {"continue_vendor_review", "no_action"}:
                errors.append(f"{label} stock memo allowed_next_action must be continue_vendor_review or no_action")
            if row.get("paper_forward_active") is not False:
                errors.append(f"{label} stock memo cannot be paper_forward_active")

        if row.get("id", "").startswith(("C_", "D_", "E_")):
            if row.get("status") == "active_observation":
                errors.append(f"{label} C/D/E row cannot be active_observation")
            if row.get("paper_forward_active") is not False:
                errors.append(f"{label} C/D/E row cannot be paper_forward_active")
            if row.get("status") not in {"shadow_only", "archived", "rejected", "exploratory_only"}:
                errors.append(f"{label} C/D/E row must be shadow_only, archived, rejected, or exploratory_only")

        if row.get("status") == "practical_candidate" and row.get("credibility_tier") in {"tier0_research_map", "tier1_exploratory", "blocked"}:
            errors.append(f"{label} low-tier or blocked row cannot be practical_candidate")
        row_id = str(row.get("id", "")).lower()
        role = str(row.get("role", "")).lower()
        if (row.get("credibility_tier") == "tier1_exploratory" or "leverage" in row_id or "exposure" in row_id or "diagnostic" in role) and row.get("paper_forward_allowed_by_risk_framework") is True:
            errors.append(f"{label} Tier 1/diagnostic row cannot be paper-forward allowed by risk framework")
        if ("leverage" in row_id or "exposure" in row_id or "diagnostic" in role) and row.get("paper_forward_active") is True:
            errors.append(f"{label} exposure/leverage diagnostic row cannot be paper_forward_active")
        if not row.get("notes"):
            warnings.append(f"{label} has empty notes")

    frame = entries_frame(registry_data)
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "row_count": int(len(frame)),
        "active_paper_forward_count": int(frame["paper_forward_active"].astype(bool).sum()) if not frame.empty else 0,
        "exploratory_count": int((frame["credibility_tier"] == "tier1_exploratory").sum()) if not frame.empty else 0,
        "blocked_count": int(frame["status"].isin(["blocked", "deferred", "rejected", "too_risky"]).sum()) if not frame.empty else 0,
    }


def next_possible_tier(row: pd.Series) -> str:
    tier = row["credibility_tier"]
    if tier == "tier0_research_map":
        return "tier1_exploratory_after_gate_review"
    if tier == "tier1_exploratory":
        return "tier2_credible_prototype_after_review"
    if tier == "tier2_credible_prototype":
        return "tier3_candidate_validation"
    if tier == "tier3_candidate_validation":
        return "tier4_paper_forward_if_frozen"
    if tier == "tier4_paper_forward":
        return "observe_only"
    return "none"


def current_blockers(row: pd.Series) -> str:
    blockers: list[str] = []
    if row["status"] in {"blocked", "deferred", "rejected", "too_risky"}:
        blockers.append(str(row["status"]))
    if row["implementation_status"] in {"blocked_by_gate", "not_implemented"}:
        blockers.append(str(row["implementation_status"]))
    if row["credibility_tier"] in {"tier0_research_map", "tier1_exploratory", "blocked"}:
        blockers.append(str(row["credibility_tier"]))
    if row.get("promotion_blockers") and str(row.get("promotion_blockers")) not in {"none", "False"}:
        blockers.extend(str(row.get("promotion_blockers")).split(";"))
    return ";".join(dict.fromkeys(blockers)) or "none"


def build_summary(frame: pd.DataFrame, validation: dict[str, Any], run_id: str) -> str:
    active = frame[frame["paper_forward_active"].astype(bool)]
    frozen = ", ".join(active["id"].tolist()) or "none"
    queue = frame[frame["allowed_next_action"].isin(QUEUE_ACTIONS)]
    blocked = frame[frame["status"].isin(["blocked", "deferred", "rejected", "too_risky"])]
    next_action = "continue_vendor_review for individual_stock_momentum_gate1a" if "individual_stock_momentum_gate1a" in set(queue["id"]) else "audit_harden ETF/crypto exploratory rows"
    return f"""# Strategy Lab Summary

## Research-Only Statement

This registry is a project-control layer only. It does not validate strategies, place trades, connect to brokers, or recommend real-money trading.

## Run Identity

- run_id: {run_id}
- registry rows: {len(frame)}
- validation_passed: {validation['passed']}

## Active Paper-Forward Candidate

`SPY_200d_trend_model` is the leading ETF paper-forward watchlist candidate. It is frozen and may only be observed or compared.

## Active Risk Framework

`balanced_speculative_research_v1` is active. Paper-forward rows must be allowed by the framework; Tier 1, simulated exposure/leverage, crypto exploratory, and gate-blocked rows are not paper-forward eligible.

## Frozen Paper-Forward Rows

{frozen}

## Parallel Development Allowed

Parallel work is allowed only for rows in `experiment_queue.csv`, and only as isolated new versions, audit hardening, or memo/gate work. Frozen paper-forward rows must not be changed.

## Blocked Or Deferred Work

Blocked/deferred/rejected/too-risky rows are listed in `blocked_items.csv`. Individual stock momentum remains deferred after Gate 1A vendor verification. Crypto remains Tier 1 exploratory. C/D/E remain rejected or archived.

## Next Recommended Action

{next_action}

## No Real-Money Recommendation

Nothing in this registry is a real-money recommendation. No broker integration, live orders, or order placement are allowed.
"""


def write_text_files(run_dir: Path, frame: pd.DataFrame, validation: dict[str, Any], run_id: str) -> None:
    readme = """# README For Auditor

This folder is the compact Strategy Lab Registry evidence packet.

Inspect in this order:

1. `strategy_lab_summary.md`
2. `strategy_registry_snapshot.csv`
3. `active_paper_forward_freeze.csv`
4. `blocked_items.csv`
5. `registry_validation.json`

This is research-only scope control. It does not recommend real-money trading and does not place orders.
"""
    warnings = """# Warnings And Limitations

- Registry evidence is not strategy validation.
- Registry evidence does not recommend real-money trading.
- The registry does not place trades.
- Parallel work is allowed only if isolated.
- Paper-forward candidates are frozen.
- Exploratory results are non-final.
- Gate-blocked instruments cannot be implemented.
- Risk Framework v1 blocks Tier 1, simulated exposure/leverage, crypto exploratory, and gate-blocked rows from paper-forward eligibility.
- No broker integration, live orders, or order placement are allowed.
"""
    (run_dir / "README_FOR_AUDITOR.md").write_text(readme, encoding="utf-8")
    (run_dir / "strategy_lab_summary.md").write_text(build_summary(frame, validation, run_id), encoding="utf-8")
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")


def export_evidence(registry_data: dict[str, Any], validation: dict[str, Any], output_root: Path = DEFAULT_OUTPUT_ROOT) -> tuple[Path, Path]:
    run_id = utc_run_id()
    run_dir = output_root / "runs" / run_id
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    frame = entries_frame(registry_data)

    write_text_files(run_dir, frame, validation, run_id)
    frame.to_csv(run_dir / "strategy_registry_snapshot.csv", index=False)
    frame[["id", "version", "parent_id", "lane", "strategy_family", "status", "rules_frozen", "notes"]].to_csv(
        run_dir / "strategy_versions.csv", index=False
    )
    frame[frame["paper_forward_active"].astype(bool)][
        [
            "id",
            "version",
            "role",
            "rules_frozen",
            "allowed_next_action",
            "forbidden_next_actions",
            "risk_framework_status",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
            "latest_evidence_path",
            "notes",
        ]
    ].to_csv(run_dir / "active_paper_forward_freeze.csv", index=False)
    frame[frame["allowed_next_action"].isin(QUEUE_ACTIONS)].to_csv(run_dir / "experiment_queue.csv", index=False)
    promotion = frame[
        [
            "id",
            "version",
            "credibility_tier",
            "status",
            "promotion_requirements",
            "risk_framework_status",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
        ]
    ].copy()
    promotion = promotion.rename(columns={"credibility_tier": "current_tier"})
    promotion["next_possible_tier"] = frame.apply(next_possible_tier, axis=1)
    promotion["current_blockers"] = frame.apply(current_blockers, axis=1)
    promotion.to_csv(run_dir / "promotion_status.csv", index=False)
    frame[frame["status"].isin(["blocked", "deferred", "rejected", "too_risky"])].to_csv(run_dir / "blocked_items.csv", index=False)
    (run_dir / "registry_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")

    files = [p.name for p in run_dir.iterdir() if p.is_file()]
    extra = sorted(set(files) - set(REQUIRED_EVIDENCE_FILES))
    missing = sorted(set(REQUIRED_EVIDENCE_FILES) - set(files))
    if extra or missing or len(files) > 10:
        raise RuntimeError(f"Strategy Lab evidence contract failed. extra={extra} missing={missing} file_count={len(files)}")

    shutil.copytree(run_dir, latest_dir)
    zip_path = output_root / "latest_strategy_lab_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and export the Strategy Lab Registry.")
    parser.add_argument("--validate-registry", action="store_true")
    parser.add_argument("--export-evidence", action="store_true")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.validate_registry and not args.export_evidence:
        args.validate_registry = True
    registry_path = Path(args.registry)
    data = load_registry(registry_path)
    validation = validate_registry_data(data)
    if args.validate_registry:
        print(json.dumps(validation, indent=2, sort_keys=True))
    if args.export_evidence:
        run_dir, latest_dir = export_evidence(data, validation, Path(args.output_root))
        print(f"strategy_lab_run_dir={run_dir}")
        print(f"strategy_lab_latest_dir={latest_dir}")
        print(f"strategy_lab_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
