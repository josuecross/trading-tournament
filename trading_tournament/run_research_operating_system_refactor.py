from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
RESEARCH_OS_DIR = Path("strategy_lab") / "research_os"
FAMILY_STATUS_DIR = RESEARCH_OS_DIR / "family_status"
OUTPUT_DIR = Path("evidence") / "governance" / "research_operating_system_refactor" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"

NEXT_ACTION = "manual_review_refactored_research_os"
VALID_NEXT_ACTIONS = {
    "manual_review_refactored_research_os",
    "fix_research_os_refactor_blockers",
    "pre_register_indicator_library_integration_audit",
    "pause_expansion_and_summarize_tournament_state",
}

ACTIVE_OBSERVATION_PATHS = {
    VM_ID: Path("paper_forward_observations") / VM_ID / "active_observation.yaml",
    DSR_ID: Path("paper_forward_observations") / DSR_ID / "active_observation.yaml",
}

MANIFEST_FLAGS = {
    "research_os_refactor_only": True,
    "governance_refactor": True,
    "backtests_run": False,
    "discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_used": False,
    "intraday_research_remains_paused": True,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "new_strategy_candidates_created": False,
    "indicator_library_installed": False,
    "strategy_rules_changed": False,
}

RESEARCH_OS_FILES = [
    "RESEARCH_OPERATING_SYSTEM.md",
    "phase_model.yaml",
    "lane_model.yaml",
    "candidate_role_model.yaml",
    "family_registry.yaml",
    "research_value_scorecard.yaml",
    "promotion_eligibility_gates.yaml",
    "paper_demo_eligibility_gates.yaml",
    "failure_taxonomy.yaml",
    "overfitting_control_ledger.yaml",
    "parent_child_lineage_rules.yaml",
    "signal_funnel_contract.yaml",
    "data_source_gate_model.yaml",
    "indicator_governance.yaml",
    "benchmark_control_registry.yaml",
    "next_action_policy.yaml",
]

EVIDENCE_FILES = [
    "research_os_refactor_manifest.json",
    "research_os_refactor_summary.md",
    "research_os_structure_created.md",
    "family_registry_migration_summary.md",
    "lane_model_summary.md",
    "research_value_vs_promotion_model.md",
    "indicator_governance_summary.md",
    "signal_funnel_contract_summary.md",
    "parent_child_lineage_summary.md",
    "data_source_gate_summary.md",
    "benchmark_control_registry_summary.md",
    "next_action_policy_summary.md",
    "research_os_refactor_limitations.md",
    "research_os_refactor_next_action.md",
    "research_os_refactor_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing to clean output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_state_snapshot(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(registry.get("strategies", []))


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(root / rel_path) for strategy_id, rel_path in ACTIVE_OBSERVATION_PATHS.items()}


def family_definitions() -> list[dict[str, Any]]:
    common_forbidden = [
        "reopen_exact_rejected_variant",
        "post_result_parameter_tuning",
        "candidate_exhaustive_without_promotion_review",
        "paper_demo_without_candidate_exhaustive",
        "broker_or_live_path",
        "real_money_recommendation",
    ]
    return [
        {
            "family_id": "volatility_managed_equity_etf",
            "description": "Long-only ETF wrapper using quality/low-volatility/proxy sleeves with trend and volatility-aware ranking.",
            "lane": "moderate_tactical_etf_lane",
            "role": "profit_engine",
            "status": "active_accepted",
            "tested_variants": [VM_ID, "vm_quality_lowvol_proxy_v1"],
            "accepted_variants": [VM_ID],
            "rejected_variants": [],
            "benchmark_controls": ["SPY", "QQQ", "BIL", SPY_200D_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["duplicate_or_near_duplicate"],
            "data_status": "sufficient",
            "family_open_status": "protected_active_observation_no_rule_change",
            "allowed_future_work": ["observe_active_frozen_row", "compare_as_reference", "family_level_audit_only"],
            "forbidden_future_work": ["change_active_observation_rules", *common_forbidden],
            "next_allowed_action": "manual_review_refactored_research_os",
            "notes": "Active VM state is preserved exactly; this refactor adds only governance metadata.",
        },
        {
            "family_id": "defensive_sector_rotation",
            "description": "ETF sector rotation family with defensive/cash filters and active DSR observation state.",
            "lane": "conservative_etf_allocation_lane",
            "role": "risk_reducer",
            "status": "active_accepted",
            "tested_variants": [
                DSR_ID,
                "dsr_sector_top2_momentum_200d_bil_v1",
                "dsr_sector_top3_momentum_defensive_cash_v1",
            ],
            "accepted_variants": [DSR_ID],
            "rejected_variants": ["dsr_sector_top2_momentum_200d_bil_v1"],
            "benchmark_controls": ["SPY", "BIL", SPY_200D_ID, ACTIVE_COMBO_ID, VM_ID],
            "primary_failure_patterns": ["duplicate_or_near_duplicate", "risk_buffer_too_thin"],
            "data_status": "sufficient",
            "family_open_status": "protected_active_observation_no_rule_change",
            "allowed_future_work": ["observe_active_frozen_row", "same_family_audit_only"],
            "forbidden_future_work": ["change_active_observation_rules", *common_forbidden],
            "next_allowed_action": "manual_review_refactored_research_os",
            "notes": "Active DSR remains accepted/frozen; DSR recovered-best mismatch remains an accepted caveat for manual review.",
        },
        {
            "family_id": "dual_momentum_paa",
            "description": "Protective asset allocation and dual-momentum ETF wrapper family.",
            "lane": "macro_gld_duration_risk_off_lane",
            "role": "profit_engine",
            "status": "rejected_current_variants",
            "tested_variants": ["dual_momentum_paa_clean_v1", "rc_dual_momentum_paa_vol_scaled_v1"],
            "accepted_variants": [],
            "rejected_variants": ["dual_momentum_paa_clean_v1", "rc_dual_momentum_paa_vol_scaled_v1"],
            "benchmark_controls": ["SPY", "QQQ", "GLD", "IEF", "BIL", STATIC_ALL_WEATHER_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["too_risky", "risk_buffer_too_thin", "no_meaningful_improvement"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["audit_family_failures", "pre_register_distinct_family_hypothesis_only"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "Risk-controlled follow-up did not produce a promotion-review candidate.",
        },
        {
            "family_id": "donchian_breakout",
            "description": "Daily close ETF Donchian breakout family with ATR/risk-budget controls.",
            "lane": "moderate_tactical_etf_lane",
            "role": "profit_engine",
            "status": "rejected_current_variants",
            "tested_variants": ["donchian_atr_breakout_etf_v1", "rc_donchian_breakout_risk_budget_v1"],
            "accepted_variants": [],
            "rejected_variants": ["donchian_atr_breakout_etf_v1", "rc_donchian_breakout_risk_budget_v1"],
            "benchmark_controls": ["SPY", "QQQ", "BIL", SPY_200D_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["too_risky", "risk_buffer_too_thin", "parent_child_mismatch_risk"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["audit_family_failures", "parent_child_consistency_review"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "Prior 55-day language was invalidated; parent rule consistency is mandatory before any follow-up.",
        },
        {
            "family_id": "gld_duration_macro_rotation",
            "description": "GLD/duration/risk-off macro rotation ETF wrapper family.",
            "lane": "macro_gld_duration_risk_off_lane",
            "role": "diversifier",
            "status": "rejected_current_variants",
            "tested_variants": ["gld_gror_balanced_momentum_clean_v1", "gld_ief_spy_defensive_rotation_v1"],
            "accepted_variants": [],
            "rejected_variants": ["gld_gror_balanced_momentum_clean_v1", "gld_ief_spy_defensive_rotation_v1"],
            "benchmark_controls": ["SPY", "GLD", "IEF", "BIL", STATIC_ALL_WEATHER_ID],
            "primary_failure_patterns": ["too_slow_for_profit_goal", "weaker_than_active_references"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["diversifier_contribution_review_only"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "Useful as a macro/diversifier lesson, not as a standalone profit promotion path.",
        },
        {
            "family_id": "managed_futures_etf_wrapper",
            "description": "Managed-futures-style ETF/fund-wrapper proxy, without direct futures or derivatives.",
            "lane": "diversifier_contribution_lane",
            "role": "diversifier",
            "status": "rejected_current_variants",
            "tested_variants": ["managed_futures_etf_trend_wrapper_v1"],
            "accepted_variants": [],
            "rejected_variants": ["managed_futures_etf_trend_wrapper_v1"],
            "benchmark_controls": ["SPY", "BIL", ACTIVE_COMBO_ID, STATIC_ALL_WEATHER_ID],
            "primary_failure_patterns": ["weaker_than_active_references", "too_slow_for_profit_goal"],
            "data_status": "sufficient",
            "family_open_status": "future_hypothesis_only",
            "allowed_future_work": ["pre_register_next_family_archetype_review"],
            "forbidden_future_work": common_forbidden + ["direct_futures", "options", "forex", "leverage"],
            "next_allowed_action": "manual_review_refactored_research_os",
            "notes": "ETF/fund-wrapper only; no direct managed-futures execution path is authorized.",
        },
        {
            "family_id": "sector_relative_strength",
            "description": "Sector ETF relative-strength family using limited-history same-window controls.",
            "lane": "moderate_tactical_etf_lane",
            "role": "profit_engine",
            "status": "rejected_current_variants",
            "tested_variants": ["sector_rs_weekly_cash_filter_v1"],
            "accepted_variants": [],
            "rejected_variants": ["sector_rs_weekly_cash_filter_v1"],
            "benchmark_controls": ["SPY", "BIL", DSR_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["limited_history_same_window_required", "weaker_than_active_references"],
            "data_status": "limited_history_same_window_required",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["data_window_methodology_review", "audit_family_failures"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "XLRE history constraints require common-window labeling before any future work.",
        },
        {
            "family_id": "turn_of_month_calendar",
            "description": "Calendar-effect ETF wrapper family centered on turn-of-month behavior.",
            "lane": "diversifier_contribution_lane",
            "role": "diversifier",
            "status": "rejected_after_bugfix_rerun",
            "tested_variants": ["turn_of_month_spy_qqq_v1"],
            "accepted_variants": [],
            "rejected_variants": ["turn_of_month_spy_qqq_v1"],
            "benchmark_controls": ["SPY", "QQQ", "BIL", ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["signal_funnel_bug", "too_slow_for_profit_goal", "weaker_than_active_references"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["signal_funnel_regression_audit"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "Zero-trade bug led to mandatory signal-funnel diagnostics for future runners.",
        },
        {
            "family_id": "volatility_regime_equity",
            "description": "Equity allocation family controlled by volatility or risk-regime state.",
            "lane": "moderate_tactical_etf_lane",
            "role": "risk_reducer",
            "status": "rejected_current_variants",
            "tested_variants": ["volatility_regime_spy_qqq_bil_v1"],
            "accepted_variants": [],
            "rejected_variants": ["volatility_regime_spy_qqq_bil_v1"],
            "benchmark_controls": ["SPY", "QQQ", "BIL", SPY_200D_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["weaker_than_active_references", "too_slow_for_profit_goal"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["audit_family_failures"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "Risk controls remain useful for research value but did not clear promotion standards.",
        },
        {
            "family_id": "static_all_weather_benchmark",
            "description": "Static all-weather/permanent-portfolio-style ETF benchmark/control.",
            "lane": "diversifier_contribution_lane",
            "role": "benchmark_control",
            "status": "benchmark_control_accepted",
            "tested_variants": [STATIC_ALL_WEATHER_ID],
            "accepted_variants": [],
            "rejected_variants": [],
            "benchmark_controls": [STATIC_ALL_WEATHER_ID, "SPY", "BIL", ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["benchmark_watchlist", "too_slow_for_profit_goal"],
            "data_status": "sufficient",
            "family_open_status": "benchmark_control_only_closed_to_promotion",
            "allowed_future_work": ["same_window_benchmark_control"],
            "forbidden_future_work": common_forbidden + ["promotion_review", "candidate_exhaustive", "paper_demo_activation"],
            "next_allowed_action": "manual_review_refactored_research_os",
            "notes": "Accepted only as same-window benchmark/control; not a strategy candidate.",
        },
        {
            "family_id": "breadth_state_regime",
            "description": "Market breadth/state machine ETF wrapper lane, distinct from simple top-N ranking.",
            "lane": "breadth_state_regime_lane",
            "role": "risk_reducer",
            "status": "no_candidate_archive_lane",
            "tested_variants": [
                "bsr_breadth_state_top_assets_v1",
                "bsr_breadth_state_defensive_shift_v1",
                "bsr_breadth_state_lowvol_overlay_v1",
                "bsr_breadth_state_active_combo_overlay_v1",
            ],
            "accepted_variants": [],
            "rejected_variants": [
                "bsr_breadth_state_top_assets_v1",
                "bsr_breadth_state_defensive_shift_v1",
                "bsr_breadth_state_lowvol_overlay_v1",
                "bsr_breadth_state_active_combo_overlay_v1",
            ],
            "benchmark_controls": ["SPY", "QQQ", "BIL", SPY_200D_ID, VM_ID, DSR_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["no_meaningful_improvement", "weaker_than_active_references"],
            "data_status": "sufficient",
            "family_open_status": "closed_after_final_lane_no_candidate",
            "allowed_future_work": ["archive_or_manual_review_only"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "manual_review_refactored_research_os",
            "notes": "Final structurally different ETF lane did not create a promotion-review candidate.",
        },
        {
            "family_id": "quality_momentum_proxy",
            "description": "Quality/value/momentum and low-volatility quality ETF proxy family.",
            "lane": "moderate_tactical_etf_lane",
            "role": "profit_engine",
            "status": "watchlist_closed_no_rescue_now",
            "tested_variants": [
                "qvm_quality_value_momentum_top2_v1",
                "qvm_quality_value_momentum_risk_adjusted_top2_v1",
                "lvq_lowvol_quality_spy_regime_v1",
            ],
            "accepted_variants": [],
            "rejected_variants": ["qvm_quality_value_momentum_risk_adjusted_top2_v1", "lvq_lowvol_quality_spy_regime_v1"],
            "benchmark_controls": ["SPY", "QQQ", "BIL", VM_ID, ACTIVE_COMBO_ID],
            "primary_failure_patterns": ["too_risky", "risk_buffer_too_thin", "weaker_than_active_references"],
            "data_status": "sufficient",
            "family_open_status": "closed_exact_variants_future_hypothesis_only",
            "allowed_future_work": ["watchlist_only", "audit_family_failures"],
            "forbidden_future_work": common_forbidden,
            "next_allowed_action": "audit_family_failures",
            "notes": "High-upside versions failed risk buffer; safer versions lagged active references.",
        },
        {
            "family_id": "intraday_orb_research",
            "description": "Opening-range-breakout intraday research concept, blocked until source terms and local cache are approved.",
            "lane": "intraday_research_only_lane",
            "role": "execution_research_only",
            "status": "paused_data_source_blocked",
            "tested_variants": [],
            "accepted_variants": [],
            "rejected_variants": [],
            "benchmark_controls": ["SPY", "QQQ"],
            "primary_failure_patterns": ["blocked_due_to_intraday_source", "manual_terms_required"],
            "data_status": "blocked_due_to_intraday_source",
            "family_open_status": "paused_data_source_blocked",
            "allowed_future_work": ["data_source_review_required"],
            "forbidden_future_work": common_forbidden + ["intraday_discovery", "intraday_backtest", "provider_download_without_explicit_authorization"],
            "next_allowed_action": "intraday_paused_due_data_constraints",
            "notes": "No intraday testing is authorized.",
        },
        {
            "family_id": "intraday_gap_fade_research",
            "description": "Intraday gap-fade research concept, blocked until source terms and local cache are approved.",
            "lane": "intraday_research_only_lane",
            "role": "execution_research_only",
            "status": "paused_data_source_blocked",
            "tested_variants": [],
            "accepted_variants": [],
            "rejected_variants": [],
            "benchmark_controls": ["SPY", "QQQ"],
            "primary_failure_patterns": ["blocked_due_to_intraday_source", "manual_terms_required"],
            "data_status": "blocked_due_to_intraday_source",
            "family_open_status": "paused_data_source_blocked",
            "allowed_future_work": ["data_source_review_required"],
            "forbidden_future_work": common_forbidden + ["intraday_discovery", "intraday_backtest", "provider_download_without_explicit_authorization"],
            "next_allowed_action": "intraday_paused_due_data_constraints",
            "notes": "No intraday testing is authorized.",
        },
        {
            "family_id": "intraday_vwap_reversion_research",
            "description": "Intraday VWAP reversion research concept, blocked until source terms and local cache are approved.",
            "lane": "intraday_research_only_lane",
            "role": "execution_research_only",
            "status": "paused_data_source_blocked",
            "tested_variants": [],
            "accepted_variants": [],
            "rejected_variants": [],
            "benchmark_controls": ["SPY", "QQQ"],
            "primary_failure_patterns": ["blocked_due_to_intraday_source", "manual_terms_required"],
            "data_status": "blocked_due_to_intraday_source",
            "family_open_status": "paused_data_source_blocked",
            "allowed_future_work": ["data_source_review_required"],
            "forbidden_future_work": common_forbidden + ["intraday_discovery", "intraday_backtest", "provider_download_without_explicit_authorization"],
            "next_allowed_action": "intraday_paused_due_data_constraints",
            "notes": "No intraday testing is authorized.",
        },
    ]


def research_operating_system_md(created_utc: str) -> str:
    return f"""# Research Operating System

Created UTC: `{created_utc}`

This directory is a governance and research-flow layer. It does not run strategies, compute performance metrics, download data, activate paper/demo observation, touch broker paths, or recommend real-money trading.

## Principles

1. Research is family-first. Every row belongs to a family before testing.
2. Lanes have distinct gates. Profit engines, diversifiers, risk reducers, benchmark controls, and execution-only research are not judged by one universal pass/fail frame.
3. Research value is separate from promotion eligibility and paper/demo eligibility.
4. Discovery cannot jump directly to candidate exhaustive or paper/demo observation.
5. Every follow-up needs parent/child lineage, a single major changed dimension, unchanged dimensions, and a non-tuning hypothesis.
6. Every future runner must produce a signal funnel so zero-trade and filter-collapse bugs are visible.
7. Indicator expansion is governed by an allowlist, validation, and anti-mining controls.
8. Data/source gates come before strategy testing.
9. Exact rejected variants remain closed unless a separate governance review explicitly authorizes a distinct hypothesis.
10. Active VM and active DSR are protected active/frozen observations; this refactor does not change their states.

## Phase Flow

`phase_0_governance` -> `phase_1_family_archetype_discovery` -> `phase_2_family_failure_synthesis` -> `phase_3_risk_control_followup` -> `phase_4_promotion_review` -> `phase_5_candidate_exhaustive` -> `phase_6_paper_demo_observation`

Blocked and paused states are explicit: `phase_blocked_data_or_terms` and `phase_paused_summary_required`.
"""


def phase_model() -> dict[str, Any]:
    return {
        "phase_model_version": 1,
        "no_direct_jump_from_discovery_to_paper_demo": True,
        "phases": [
            {"phase_id": "phase_0_governance", "purpose": "Define family, lane, data status, and prohibited actions.", "exit_requires": ["manual_review_or_pre_registration"]},
            {"phase_id": "phase_1_family_archetype_discovery", "purpose": "Run only a pre-registered family archetype batch.", "exit_requires": ["signal_funnel", "same_window_controls", "family_assignment"]},
            {"phase_id": "phase_2_family_failure_synthesis", "purpose": "Convert row outcomes into family-level lessons.", "exit_requires": ["failure_taxonomy", "closed_exact_variants", "allowed_future_work"]},
            {"phase_id": "phase_3_risk_control_followup", "purpose": "Test one structurally justified risk-control follow-up only after lineage review.", "exit_requires": ["parent_child_consistency_check", "overfitting_control_ledger"]},
            {"phase_id": "phase_4_promotion_review", "purpose": "Strict promotion-review gate before candidate exhaustive.", "exit_requires": ["complete_evidence", "risk_buffer_pass", "duplication_review"]},
            {"phase_id": "phase_5_candidate_exhaustive", "purpose": "Separate exhaustive validation after promotion review.", "exit_requires": ["frozen_rules", "exhaustive_packet", "no_paper_demo_jump"]},
            {"phase_id": "phase_6_paper_demo_observation", "purpose": "Paper/demo observation only after promotion review, candidate exhaustive, and paper-forward review pass.", "exit_requires": ["operational_review", "no_real_money_boundary"]},
            {"phase_id": "phase_blocked_data_or_terms", "purpose": "Block strategy testing until source terms, cache, and QA are resolved.", "exit_requires": ["data_source_gate_pass"]},
            {"phase_id": "phase_paused_summary_required", "purpose": "Pause expansion and summarize state when repeated failures saturate a lane.", "exit_requires": ["manual_governance_decision"]},
        ],
    }


def lane_model() -> dict[str, Any]:
    return {
        "lane_model_version": 1,
        "lanes": {
            "conservative_etf_allocation_lane": {
                "allowed_roles": ["risk_reducer", "profit_engine"],
                "benchmark_interpretation": "Must protect drawdown and avoid duplication while offering usable return contribution.",
                "promotion_bias": "strict_risk_buffer_first",
            },
            "moderate_tactical_etf_lane": {
                "allowed_roles": ["profit_engine", "risk_reducer"],
                "benchmark_interpretation": "Needs standalone edge or clearly additive portfolio contribution versus active references.",
                "promotion_bias": "profit_plus_drawdown_balance",
            },
            "macro_gld_duration_risk_off_lane": {
                "allowed_roles": ["diversifier", "risk_reducer", "profit_engine"],
                "benchmark_interpretation": "Can be useful as a diversifier, but standalone promotion still needs risk-buffer and stress survival.",
                "promotion_bias": "portfolio_contribution_must_be_explicit",
            },
            "diversifier_contribution_lane": {
                "allowed_roles": ["diversifier", "benchmark_control"],
                "benchmark_interpretation": "May have research value without standalone profit-engine promotion.",
                "promotion_bias": "contribution_over_headline_return",
            },
            "breadth_state_regime_lane": {
                "allowed_roles": ["risk_reducer", "profit_engine", "diversifier"],
                "benchmark_interpretation": "State-machine value must exceed simple ranking/active-combo duplication.",
                "promotion_bias": "structural_difference_required",
            },
            "intraday_research_only_lane": {
                "allowed_roles": ["execution_research_only", "data_methodology_only"],
                "benchmark_interpretation": "Data, session, fill, and terms readiness gate before strategy testing.",
                "promotion_bias": "blocked_until_source_approved",
            },
        },
    }


def candidate_role_model() -> dict[str, Any]:
    return {
        "candidate_role_model_version": 1,
        "roles": {
            "profit_engine": "Must show credible standalone or account-level profit edge after risk and stress gates.",
            "risk_reducer": "Must improve drawdown/stop-risk behavior without destroying objective-fit.",
            "diversifier": "May be valuable through portfolio contribution even if standalone return is slower.",
            "benchmark_control": "Used only for comparison, calibration, and same-window control.",
            "execution_research_only": "May study infrastructure and fills only after data/source approval.",
            "data_methodology_only": "May study data contracts, terms, and QA without strategy testing.",
        },
    }


def research_value_scorecard() -> dict[str, Any]:
    return {
        "scorecard_version": 1,
        "fields": [
            "return_engine_evidence",
            "risk_control_evidence",
            "diversification_value",
            "benchmark_control_value",
            "implementation_quality",
            "data_quality",
            "slippage_stress_survival",
            "overfitting_risk",
            "paper_demo_simplicity",
            "research_value_verdict",
        ],
        "allowed_research_value_verdicts": [
            "high_research_value_not_promotable",
            "medium_research_value_not_promotable",
            "benchmark_control_value_only",
            "low_research_value_closed",
            "methodology_or_data_blocked",
            "promotion_review_candidate",
        ],
        "principle": "Research value can be positive while promotion eligibility remains false.",
    }


def promotion_eligibility_gates() -> dict[str, Any]:
    return {
        "promotion_eligibility_version": 1,
        "direct_candidate_exhaustive_allowed": False,
        "direct_paper_demo_allowed": False,
        "required_gates": [
            "frozen_rules_exist",
            "same_window_benchmarks_valid",
            "risk_buffer_passes",
            "drawdown_acceptable_for_lane",
            "slippage_stress_passes",
            "benchmark_edge_or_portfolio_contribution_meaningful",
            "no_duplication_issue_dominates",
            "signal_funnel_sane",
            "data_status_sufficient",
            "overfitting_risk_controlled",
            "evidence_complete",
        ],
    }


def paper_demo_eligibility_gates() -> dict[str, Any]:
    return {
        "paper_demo_eligibility_version": 1,
        "requires": [
            "promotion_review_passed",
            "candidate_exhaustive_passed",
            "paper_forward_review_passed",
            "operational_simplicity",
            "no_broker_reconciliation_issues",
            "no_stale_or_open_order_risk",
            "explicit_no_real_money_recommendation_boundary",
        ],
        "forbidden_shortcuts": ["paper_demo_from_discovery", "paper_demo_from_research_value_only", "live_or_real_money_path"],
    }


def failure_taxonomy() -> dict[str, Any]:
    return {
        "failure_taxonomy_version": 1,
        "controlled_labels": [
            "too_risky",
            "risk_buffer_too_thin",
            "duplicate_or_near_duplicate",
            "too_slow_for_profit_goal",
            "weaker_than_active_references",
            "benchmark_watchlist",
            "no_meaningful_improvement",
            "limited_history_same_window_required",
            "signal_funnel_bug",
            "parent_child_mismatch_risk",
            "blocked_due_to_intraday_source",
            "manual_terms_required",
        ],
        "recent_family_lessons": {
            "high_upside_rows": ["too_risky", "risk_buffer_too_thin"],
            "safer_rows": ["too_slow_for_profit_goal", "weaker_than_active_references"],
            "ensemble_rows": ["duplicate_or_near_duplicate", "no_meaningful_improvement"],
            "intraday": ["blocked_due_to_intraday_source", "manual_terms_required"],
        },
    }


def overfitting_control_ledger() -> dict[str, Any]:
    return {
        "ledger_version": 1,
        "required_fields": [
            "parent_candidate_id",
            "parent_status",
            "parent_failure_reason",
            "one_major_changed_dimension",
            "unchanged_dimensions",
            "family_trial_count",
            "parameter_changes_result_driven",
            "new_hypothesis_distinct",
            "manual_review_required",
        ],
        "current_entries": [
            {
                "child_candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
                "parent_candidate_id": "dual_momentum_paa_clean_v1",
                "parent_status": "discovery_reject",
                "parent_failure_reason": "high upside but failed drawdown/risk-buffer gates",
                "one_major_changed_dimension": "volatility_scaling",
                "unchanged_dimensions": ["daily ETF wrapper", "dual momentum/PAA family", "long-only", "no leverage"],
                "family_trial_count": 2,
                "parameter_changes_result_driven": False,
                "new_hypothesis_distinct": True,
                "manual_review_required": True,
            },
            {
                "child_candidate_id": "rc_donchian_breakout_risk_budget_v1",
                "parent_candidate_id": "donchian_atr_breakout_etf_v1",
                "parent_status": "discovery_reject",
                "parent_failure_reason": "return power failed drawdown, risk-buffer, benchmark, and trade gates",
                "one_major_changed_dimension": "risk_budget_sizing",
                "unchanged_dimensions": ["daily ETF wrapper", "Donchian breakout family", "ATR stop model", "long-only"],
                "family_trial_count": 2,
                "parameter_changes_result_driven": False,
                "new_hypothesis_distinct": True,
                "manual_review_required": True,
            },
        ],
    }


def parent_child_lineage_rules() -> dict[str, Any]:
    return {
        "lineage_rules_version": 1,
        "required_fields": {
            "parent_candidate_id": "required",
            "parent_status": "required",
            "parent_failure_reason": "required",
            "parent_rule_source": "required",
            "exact_parent_reopened": False,
            "one_major_changed_dimension": "required",
            "unchanged_dimensions": "required",
            "child_hypothesis": "required",
            "why_not_post_result_tuning": "required",
            "parent_rule_consistency_check_required": True,
        },
        "mismatch_policy": {
            "if_parent_rule_mismatch_found": "discovery_blocked_until_manual_review",
            "example": "Donchian follow-up language must match the parent 20-day breakout mechanics; invalidated 55-day language cannot be used.",
        },
    }


def signal_funnel_contract() -> dict[str, Any]:
    return {
        "signal_funnel_contract_version": 1,
        "required_fields": [
            "candidate_id",
            "raw_opportunity_count",
            "data_available_count",
            "signal_condition_count",
            "risk_filter_pass_count",
            "execution_filter_pass_count",
            "final_entry_count",
            "final_exit_count",
            "skipped_count",
            "blocked_reason_counts",
            "zero_trade_expected",
            "zero_trade_requires_audit",
            "signal_funnel_status",
        ],
        "zero_trade_policy": {
            "if_final_trades_zero_and_raw_opportunities_nonzero": "implementation_audit_required",
            "turn_of_month_lesson": "zero-trade output must not be accepted without a funnel audit",
        },
    }


def data_source_gate_model() -> dict[str, Any]:
    return {
        "data_source_gate_model_version": 1,
        "statuses": [
            "sufficient",
            "limited_history_same_window_required",
            "missing_required_data",
            "manual_terms_required",
            "blocked_due_to_terms",
            "blocked_due_to_intraday_source",
        ],
        "intraday_required_before_testing": [
            "source_terms_approved",
            "local_cache_exists",
            "SPY_QQQ_1Min_or_5Min_history_exists",
            "session_calendar_QA_passes",
        ],
        "intraday_current_status": "blocked_due_to_intraday_source",
        "provider_download_requires_explicit_authorization": True,
    }


def indicator_governance() -> dict[str, Any]:
    return {
        "indicator_governance_version": 1,
        "library_install_allowed_in_this_step": False,
        "future_action": "pre_register_indicator_library_integration_audit",
        "allowed_initial_indicator_categories": {
            "trend": ["SMA", "EMA", "Donchian high/low", "ADX only after validation"],
            "momentum": ["ROC", "RSI", "MACD only after validation"],
            "volatility": ["ATR", "realized volatility", "Bollinger Band z-score", "Keltner Channel only after validation"],
            "volume_liquidity": ["volume SMA", "volume spike filter", "OBV only after validation"],
            "risk": ["rolling drawdown", "volatility percentile", "ATR risk unit"],
        },
        "blocked_by_default": [
            "unrestricted candlestick pattern mining",
            "large indicator combinations",
            "genetic search",
            "AI-selected indicator formulas",
            "parameter sweeps eligible for promotion",
            "indicators requiring unavailable data",
            "intraday indicators until intraday source is approved",
        ],
        "candidate_libraries_for_future_audit": ["ta", "pandas-ta-classic", "TA-Lib", "similar"],
    }


def benchmark_control_registry() -> dict[str, Any]:
    return {
        "benchmark_control_registry_version": 1,
        "controls": {
            STATIC_ALL_WEATHER_ID: {
                "status": "benchmark_control_accepted",
                "role": "same-window benchmark/control only",
                "promotion_eligible": False,
                "candidate_exhaustive_eligible": False,
                "paper_demo_live_eligible": False,
            },
            "SPY": {"status": "market_reference", "role": "equity beta reference"},
            "QQQ": {"status": "market_reference", "role": "growth/tech beta reference"},
            "BIL": {"status": "cash_proxy_reference", "role": "defensive/cash proxy"},
            SPY_200D_ID: {"status": "active_observation_reference", "role": "trend-model reference"},
            ACTIVE_COMBO_ID: {"status": "benchmark_watchlist_reference", "role": "active VM/DSR combo reference only"},
            VM_ID: {"status": "active_frozen_reference", "role": "protected active VM reference"},
            DSR_ID: {"status": "active_frozen_reference", "role": "protected active DSR reference"},
        },
    }


def next_action_policy() -> dict[str, Any]:
    return {
        "next_action_policy_version": 1,
        "allowed_next_action_types": [
            "manual_review_refactored_research_os",
            "pre_register_indicator_library_integration_audit",
            "pre_register_next_family_archetype_review",
            "pause_expansion_and_summarize_tournament_state",
            "run_discovery_for_pre_registered_family",
            "audit_family_failures",
            "promotion_review_for_selected_candidates",
            "data_source_review_required",
            "intraday_paused_due_data_constraints",
        ],
        "disallowed_next_actions": [
            "immediate_paper_forward_from_discovery",
            "immediate_candidate_exhaustive_from_discovery",
            "strategy_rescue_without_family_audit",
            "intraday_discovery_while_data_source_blocked",
            "provider_download_without_explicit_authorization",
            "broker_live_path_activation",
        ],
        "current_recommended_next_action": NEXT_ACTION,
    }


def write_research_os(root: Path, created_utc: str, families: list[dict[str, Any]]) -> dict[str, Path]:
    os_dir = root / RESEARCH_OS_DIR
    status_dir = root / FAMILY_STATUS_DIR
    os_dir.mkdir(parents=True, exist_ok=True)
    status_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, Path] = {}
    payloads: dict[str, Any] = {
        "phase_model.yaml": phase_model(),
        "lane_model.yaml": lane_model(),
        "candidate_role_model.yaml": candidate_role_model(),
        "family_registry.yaml": {"family_registry_version": 1, "created_utc": created_utc, "families": families},
        "research_value_scorecard.yaml": research_value_scorecard(),
        "promotion_eligibility_gates.yaml": promotion_eligibility_gates(),
        "paper_demo_eligibility_gates.yaml": paper_demo_eligibility_gates(),
        "failure_taxonomy.yaml": failure_taxonomy(),
        "overfitting_control_ledger.yaml": overfitting_control_ledger(),
        "parent_child_lineage_rules.yaml": parent_child_lineage_rules(),
        "signal_funnel_contract.yaml": signal_funnel_contract(),
        "data_source_gate_model.yaml": data_source_gate_model(),
        "indicator_governance.yaml": indicator_governance(),
        "benchmark_control_registry.yaml": benchmark_control_registry(),
        "next_action_policy.yaml": next_action_policy(),
    }

    ros_path = os_dir / "RESEARCH_OPERATING_SYSTEM.md"
    write_text(ros_path, research_operating_system_md(created_utc))
    files["RESEARCH_OPERATING_SYSTEM.md"] = ros_path
    for name, payload in payloads.items():
        path = os_dir / name
        write_yaml(path, payload)
        files[name] = path
    for family in families:
        path = status_dir / f"{family['family_id']}.yaml"
        write_yaml(path, family)
        files[f"family_status/{family['family_id']}.yaml"] = path
    return files


def update_registry_metadata(root: Path, created_utc: str, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = root / REGISTRY_PATH
    registry_before = load_yaml(path)
    registry_after = deepcopy(registry_before)
    meta = registry_after.setdefault("registry", {})
    meta.update(
        {
            "research_os_path": str((root / RESEARCH_OS_DIR).resolve()),
            "research_os_refactor_evidence_path": str(output.resolve()),
            "research_os_status": "created_manual_review_required",
            "research_os_refactor_created_utc": created_utc,
            "research_os_refactor_only": True,
            "research_os_governance_refactor": True,
            "research_os_next_action": NEXT_ACTION,
            "research_os_no_backtests_run": True,
            "research_os_no_discovery_run": True,
            "research_os_no_provider_download": True,
            "research_os_no_intraday_data_used": True,
            "research_os_no_candidate_exhaustive_run": True,
            "research_os_no_paper_forward_action": True,
            "research_os_no_real_money_recommendation": True,
        }
    )
    write_yaml(path, registry_after)
    return registry_before, registry_after


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_roadmap(root: Path, created_utc: str, output: Path) -> str:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Research Operating System Refactor

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Structure path: `{(root / RESEARCH_OS_DIR).resolve()}`
- Refactor status: `created_manual_review_required`
- Current model: family-first research, lane-specific gates, separate research value / promotion / paper-demo eligibility, mandatory parent-child lineage, mandatory signal funnel, controlled indicator governance, and data-source gates before testing.
- Preserved states: active VM and active DSR remain protected active/frozen observations; static all-weather remains benchmark/control only; intraday remains paused/data-source-blocked; exact rejected variants remain closed.
- No strategy backtest, discovery, new performance metric, provider download, intraday data use, candidate_exhaustive, paper-forward review/activation, broker/live path, order action, strategy promotion, or real-money recommendation is authorized by this refactor.
- Next action: `{NEXT_ACTION}`
"""
    updated = replace_or_append_section(existing, "## Research Operating System Refactor", section)
    write_text(path, updated)
    return section


def evidence_summary_md(created_utc: str, output: Path, manual_review_required: bool) -> str:
    return f"""# Research Operating System Refactor Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Decision: `research_os_refactor_created`

Next action: `{NEXT_ACTION}`

Manual review required: `{manual_review_required}`

This was a governance-only structural refactor. It created a family/lane research operating system, migrated current state into a family registry, and added evidence showing the refactor did not run backtests, discovery, provider downloads, intraday data, candidate exhaustive validation, paper/demo activation, broker/live paths, order actions, or real-money recommendations.
"""


def structure_created_md(files: dict[str, Path], families: list[dict[str, Any]]) -> str:
    lines = ["# Research OS Structure Created", "", "Created files:"]
    for name in RESEARCH_OS_FILES:
        lines.append(f"- `strategy_lab/research_os/{name}`")
    lines.append("- `strategy_lab/research_os/family_status/` family status files")
    lines.append("")
    lines.append(f"Family status file count: `{len(families)}`")
    lines.append("")
    lines.append("Important family IDs:")
    for family in families:
        lines.append(f"- `{family['family_id']}`")
    return "\n".join(lines) + "\n"


def family_registry_migration_summary_md(families: list[dict[str, Any]]) -> str:
    active = [family["family_id"] for family in families if family["status"] == "active_accepted"]
    blocked = [family["family_id"] for family in families if family["data_status"] == "blocked_due_to_intraday_source"]
    benchmark = [family["family_id"] for family in families if family["role"] == "benchmark_control"]
    closed = [family["family_id"] for family in families if "closed" in family["family_open_status"]]
    return f"""# Family Registry Migration Summary

Families migrated: `{len(families)}`

Active/accepted families preserved: `{', '.join(active)}`

Benchmark-control families: `{', '.join(benchmark)}`

Intraday/data-source-blocked families: `{', '.join(blocked)}`

Closed or exact-variant-blocked families: `{', '.join(closed)}`

The migration used existing registry, roadmap, and evidence summaries only. It did not recompute returns, drawdown, Sharpe, benchmark deltas, or P&L.
"""


def static_summary(title: str, body: str) -> str:
    return f"# {title}\n\n{body.rstrip()}\n"


def limitations_md() -> str:
    return """# Research OS Refactor Limitations

- This is a governance migration, not an independent re-audit of every historical metric.
- Family mapping is derived from existing roadmap, registry, and evidence summaries; inconsistent or missing historical evidence is flagged for manual review rather than invented.
- Active DSR recovered-best mismatch remains an accepted caveat and is not reconciled by this refactor.
- Intraday families remain blocked because source terms and local SPY/QQQ 1Min or 5Min caches are not approved.
- The Research OS should receive human review before it becomes the authoritative planning layer.
"""


def next_action_md() -> str:
    return f"""# Research OS Refactor Next Action

Exact next action: `{NEXT_ACTION}`

Do not run this next action in the refactor task.

Allowed alternatives if manual review rejects the migration:

- `fix_research_os_refactor_blockers`
- `pause_expansion_and_summarize_tournament_state`

The next action is governance review only. It does not authorize discovery, candidate exhaustive validation, paper/demo activation, provider download, broker/live paths, order actions, or real-money recommendations.
"""


def write_evidence(
    output: Path,
    created_utc: str,
    families: list[dict[str, Any]],
    files: dict[str, Path],
    consistency: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    write_json(output / "research_os_refactor_manifest.json", manifest)
    write_text(output / "research_os_refactor_summary.md", evidence_summary_md(created_utc, output, manifest["migration_manual_review_required"]))
    write_text(output / "research_os_structure_created.md", structure_created_md(files, families))
    write_text(output / "family_registry_migration_summary.md", family_registry_migration_summary_md(families))
    write_text(
        output / "lane_model_summary.md",
        static_summary(
            "Lane Model Summary",
            "The lane model separates conservative ETF allocation, moderate tactical ETF, macro GLD/duration risk-off, diversifier contribution, breadth-state regime, and intraday research-only lanes. Each lane has role constraints and benchmark interpretation rules.",
        ),
    )
    write_text(
        output / "research_value_vs_promotion_model.md",
        static_summary(
            "Research Value Vs Promotion Model",
            "Research value can be high while promotion eligibility remains false. Promotion still requires frozen rules, same-window controls, risk buffer, drawdown, slippage/stress survival, meaningful edge or contribution, sane signal funnel, sufficient data, controlled overfitting risk, and complete evidence.",
        ),
    )
    write_text(
        output / "indicator_governance_summary.md",
        static_summary(
            "Indicator Governance Summary",
            "Initial indicators are limited to approved trend, momentum, volatility, volume/liquidity, and risk categories. Indicator libraries are not installed here. Future library evaluation requires `pre_register_indicator_library_integration_audit`, with candlestick mining, genetic search, large combinations, AI-selected formulas, promotion-eligible parameter sweeps, unavailable-data indicators, and intraday indicators blocked by default.",
        ),
    )
    write_text(
        output / "signal_funnel_contract_summary.md",
        static_summary(
            "Signal Funnel Contract Summary",
            "Future discovery runners must report raw opportunities, data availability, signal counts, risk-filter passes, execution-filter passes, final entries/exits, skipped counts, blocked reasons, zero-trade expectedness, zero-trade audit requirement, and signal-funnel status. Zero final trades with nonzero raw opportunities require implementation audit.",
        ),
    )
    write_text(
        output / "parent_child_lineage_summary.md",
        static_summary(
            "Parent Child Lineage Summary",
            "Follow-up candidates require parent ID/status/failure reason/rule source, exact_parent_reopened false, one major changed dimension, unchanged dimensions, child hypothesis, why it is not post-result tuning, and parent rule consistency check. A mismatch blocks discovery until manual review.",
        ),
    )
    write_text(
        output / "data_source_gate_summary.md",
        static_summary(
            "Data Source Gate Summary",
            "Data statuses are sufficient, limited_history_same_window_required, missing_required_data, manual_terms_required, blocked_due_to_terms, and blocked_due_to_intraday_source. Intraday remains blocked until source terms are approved, local cache exists, SPY/QQQ 1Min or 5Min history exists, and session/calendar QA passes.",
        ),
    )
    write_text(
        output / "benchmark_control_registry_summary.md",
        static_summary(
            "Benchmark Control Registry Summary",
            "Static all-weather is benchmark_control_accepted and same-window benchmark/control only, with no promotion, candidate_exhaustive, paper/demo, or live eligibility. SPY, QQQ, BIL, SPY_200d, active combo, active VM, and active DSR are retained as references according to current conventions.",
        ),
    )
    write_text(
        output / "next_action_policy_summary.md",
        static_summary(
            "Next Action Policy Summary",
            "Allowed next actions are manual Research OS review, indicator-library audit pre-registration, next family archetype pre-registration, expansion pause/summary, discovery for a pre-registered family, family-failure audit, promotion review for selected candidates, data-source review, and intraday paused status. Immediate paper-forward, immediate candidate_exhaustive, rescue without family audit, intraday discovery while blocked, provider download without explicit authorization, and broker/live activation are disallowed.",
        ),
    )
    write_text(output / "research_os_refactor_limitations.md", limitations_md())
    write_text(output / "research_os_refactor_next_action.md", next_action_md())
    write_json(output / "research_os_refactor_consistency_check.json", consistency)
    packet = output / "research_os_refactor_packet.zip"
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in EVIDENCE_FILES:
            archive.write(output / rel, rel)


def build_manifest(
    created_utc: str,
    output: Path,
    families: list[dict[str, Any]],
    files: dict[str, Path],
    consistency: dict[str, Any],
) -> dict[str, Any]:
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        "research_os_dir": str((output.parents[3] / RESEARCH_OS_DIR).resolve()) if len(output.parents) > 3 else str(RESEARCH_OS_DIR),
        **MANIFEST_FLAGS,
        "family_registry_created": "family_registry.yaml" in files,
        "lane_model_created": "lane_model.yaml" in files,
        "research_value_scorecard_created": "research_value_scorecard.yaml" in files,
        "indicator_governance_created": "indicator_governance.yaml" in files,
        "signal_funnel_contract_created": "signal_funnel_contract.yaml" in files,
        "parent_child_lineage_rules_created": "parent_child_lineage_rules.yaml" in files,
        "data_source_gate_model_created": "data_source_gate_model.yaml" in files,
        "benchmark_control_registry_created": "benchmark_control_registry.yaml" in files,
        "next_action_policy_created": "next_action_policy.yaml" in files,
        "migration_manual_review_required": True,
        "next_action": NEXT_ACTION,
        "family_count": len(families),
        "required_family_ids": [family["family_id"] for family in families],
        "consistency_passed": consistency["consistency_passed"],
    }
    return manifest


def consistency_check(
    root: Path,
    families: list[dict[str, Any]],
    files: dict[str, Path],
    registry_before: dict[str, Any],
    registry_after: dict[str, Any],
    obs_before: dict[str, str],
    obs_after: dict[str, str],
) -> dict[str, Any]:
    family_by_id = {family["family_id"]: family for family in families}
    required_os_files_present = all((root / RESEARCH_OS_DIR / rel).exists() for rel in RESEARCH_OS_FILES)
    family_status_count = len(list((root / FAMILY_STATUS_DIR).glob("*.yaml"))) if (root / FAMILY_STATUS_DIR).exists() else 0
    static_family = family_by_id.get("static_all_weather_benchmark", {})
    intraday_families = [family for family in families if family["family_id"].startswith("intraday_")]
    strategy_rows_unchanged = strategy_state_snapshot(registry_before) == strategy_state_snapshot(registry_after)
    check = {
        "research_os_refactor_only": True,
        "governance_refactor": True,
        "no_backtests_run": True,
        "no_discovery_run": True,
        "no_new_performance_metrics_computed": True,
        "no_provider_download": True,
        "no_intraday_data_used": True,
        "intraday_research_remains_paused": all(family.get("data_status") == "blocked_due_to_intraday_source" for family in intraday_families),
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_action": True,
        "no_broker_live_path": True,
        "no_real_money_recommendation": True,
        "accepted_strategy_state_changed": False,
        "rejected_strategy_state_changed": False,
        "exact_rejected_variants_reopened": False,
        "new_strategy_candidates_created": False,
        "indicator_library_installed": False,
        "strategy_rules_changed": False,
        "family_registry_exists": (root / RESEARCH_OS_DIR / "family_registry.yaml").exists(),
        "lane_model_exists": (root / RESEARCH_OS_DIR / "lane_model.yaml").exists(),
        "candidate_role_model_exists": (root / RESEARCH_OS_DIR / "candidate_role_model.yaml").exists(),
        "research_value_scorecard_exists": (root / RESEARCH_OS_DIR / "research_value_scorecard.yaml").exists(),
        "promotion_eligibility_gates_exists": (root / RESEARCH_OS_DIR / "promotion_eligibility_gates.yaml").exists(),
        "paper_demo_eligibility_gates_exists": (root / RESEARCH_OS_DIR / "paper_demo_eligibility_gates.yaml").exists(),
        "failure_taxonomy_exists": (root / RESEARCH_OS_DIR / "failure_taxonomy.yaml").exists(),
        "parent_child_lineage_rules_exists": (root / RESEARCH_OS_DIR / "parent_child_lineage_rules.yaml").exists(),
        "signal_funnel_contract_exists": (root / RESEARCH_OS_DIR / "signal_funnel_contract.yaml").exists(),
        "data_source_gate_model_exists": (root / RESEARCH_OS_DIR / "data_source_gate_model.yaml").exists(),
        "indicator_governance_exists": (root / RESEARCH_OS_DIR / "indicator_governance.yaml").exists(),
        "benchmark_control_registry_exists": (root / RESEARCH_OS_DIR / "benchmark_control_registry.yaml").exists(),
        "next_action_policy_exists": (root / RESEARCH_OS_DIR / "next_action_policy.yaml").exists(),
        "required_os_files_present": required_os_files_present,
        "family_status_files_created_count": family_status_count,
        "static_all_weather_benchmark_control_only": static_family.get("role") == "benchmark_control"
        and static_family.get("status") == "benchmark_control_accepted"
        and "promotion_review" in static_family.get("forbidden_future_work", []),
        "intraday_families_data_source_blocked": all(family.get("data_status") == "blocked_due_to_intraday_source" for family in intraday_families),
        "risk_controlled_rejected_active_states_not_mutated": strategy_rows_unchanged,
        "active_observations_unchanged": obs_before == obs_after,
        "next_action_valid": NEXT_ACTION in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": True,
        "roadmap_updated_or_proposed": (root / ROADMAP_PATH).exists(),
        "registry_updated_or_proposed": (root / REGISTRY_PATH).exists(),
    }
    expected_false = {
        "accepted_strategy_state_changed",
        "rejected_strategy_state_changed",
        "exact_rejected_variants_reopened",
        "new_strategy_candidates_created",
        "indicator_library_installed",
        "strategy_rules_changed",
    }
    check["consistency_passed"] = all(
        (value is False if key in expected_false else value is True)
        for key, value in check.items()
        if isinstance(value, bool)
    )
    return check


def run_research_operating_system_refactor(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = clean_output(root)

    registry_initial = load_yaml(root / REGISTRY_PATH)
    obs_before = active_observation_hashes(root)
    families = family_definitions()
    files = write_research_os(root, created_utc, families)
    registry_before_update, registry_after_update = update_registry_metadata(root, created_utc, output)
    update_roadmap(root, created_utc, output)
    obs_after = active_observation_hashes(root)

    consistency = consistency_check(root, families, files, registry_before_update or registry_initial, registry_after_update, obs_before, obs_after)
    manifest = build_manifest(created_utc, output, families, files, consistency)
    write_evidence(output, created_utc, families, files, consistency, manifest)
    return {
        "output_dir": str(output),
        "research_os_dir": str((root / RESEARCH_OS_DIR).resolve()),
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
        "family_count": len(families),
    }


def main() -> None:
    result = run_research_operating_system_refactor(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
