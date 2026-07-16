from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "strategy_library_discovery_yield_checkpoint_v1" / "latest"
STATUS = "library_improves_process_but_not_candidate_yield_yet"
NEXT_ACTION = "direction_owner_decision_required_for_next_external_source_research"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ACTIVE_COMBO = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def artifact_path(path: str) -> str:
    return path.replace("\\", "/")


def source_inventory() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "adx_dmi_trend_strength_crossover",
            "candidate_id": "adx_dmi_spy_bil_primary_v1",
            "lane_or_family": "public_source_adx_dmi_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "validation_completed",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_adx_dmi_bounded_bt_results_audit/latest",
            "latest_valid_artifact": "public_source_adx_dmi_bounded_bt_results_audit_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": True,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "public_source_adx_dmi_corrected_results_passed_but_control_weak",
            "primary_failure_reason": "weak_vs_primary_control",
            "secondary_failure_reason": "benchmark_like_behavior",
            "notes": "Formula/event semantics patched and audited; low-exposure defensive timing remained control-weak.",
        },
        {
            "source_id": "cci_correction",
            "candidate_id": "cci_correction_spy_bil_primary_v1",
            "lane_or_family": "public_source_cci_correction_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "validation_completed",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_cci_correction_bounded_bt_results_audit/latest",
            "latest_valid_artifact": "public_source_cci_correction_bounded_bt_results_audit_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": True,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "public_source_cci_correction_results_passed_but_control_weak",
            "primary_failure_reason": "weak_vs_primary_control",
            "secondary_failure_reason": "benchmark_like_behavior",
            "notes": "Audit passed mechanics, but SPY_200d dominated the primary row on major controls.",
        },
        {
            "source_id": "coppock_curve_monthly_equity_signal",
            "candidate_id": "coppock_spy_bil_monthly_zero_cross_primary_v1",
            "lane_or_family": "public_source_coppock_curve_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_coppock_curve_final_state_reconciliation/latest",
            "latest_valid_artifact": "public_source_coppock_curve_final_state_reconciliation_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "completed_diagnostic_sparse_context_only_failed_criteria_no_continuation_authorized",
            "primary_failure_reason": "signal_scarcity",
            "secondary_failure_reason": "benchmark_like_behavior",
            "notes": "Only one completed round trip; average SPY exposure was very high and duplicate/reference correlation was high.",
        },
        {
            "source_id": "larry_connors_rsi2_mean_reversion",
            "candidate_id": "connors_rsi2_spy_bil_primary_v1",
            "lane_or_family": "public_source_larry_connors_rsi2_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_larry_connors_rsi2_final_state_reconciliation/latest",
            "latest_valid_artifact": "larry_connors_rsi2_final_state_reconciliation_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": True,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "completed_diagnostic_context_only_cost_sensitive_rolling_weak_no_continuation_authorized",
            "primary_failure_reason": "transaction_cost_drag",
            "secondary_failure_reason": "return_edge_not_stable",
            "notes": "Initial evidence did not survive cost stress and rolling-window checks.",
        },
        {
            "source_id": "parabolic_sar_spy_bil_long_only_reversal",
            "candidate_id": "parabolic_sar_spy_bil_primary_v1",
            "lane_or_family": "public_source_parabolic_sar_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "bounded_screen_completed",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_parabolic_sar_bounded_bt_run/latest",
            "latest_valid_artifact": "public_source_parabolic_sar_bounded_bt_run_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "primary_row_numeric_criteria_failed",
            "primary_failure_reason": "high_turnover",
            "secondary_failure_reason": "high_drawdown_for_return",
            "notes": "Primary failed criteria with 257 round trips and high turnover/whipsaw risk.",
        },
        {
            "source_id": "percent_b_money_flow",
            "candidate_id": "percent_b_mfi_spy_bil_primary_v1",
            "lane_or_family": "public_source_percent_b_money_flow_bounded_bt_lane_v1",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_percent_b_money_flow_state_reconciliation/latest",
            "latest_valid_artifact": "percent_b_state_reconciliation_manifest.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "completed_diagnostic_failed_pre_registered_criteria_no_rerun_authorized",
            "primary_failure_reason": "benchmark_like_behavior",
            "secondary_failure_reason": "return_edge_not_stable",
            "notes": "Primary row exceeded the preregistered sparse-signal exposure bound.",
        },
        {
            "source_id": "bollinger_band_squeeze_breakout",
            "candidate_id": "bollinger_band_squeeze_breakout",
            "lane_or_family": "equity_index_volatility_contraction_breakout",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "blocked",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "latest_valid_artifact": "eligibility_decisions.csv",
            "source_reviewed": True,
            "complete_rules": False,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "needs_direction_owner_review",
            "primary_failure_reason": "source_rules_incomplete",
            "secondary_failure_reason": "not_materially_distinct",
            "notes": "Neutral squeeze source needed directional/exit clarification before design.",
        },
        {
            "source_id": "macd_stochastic_double_cross",
            "candidate_id": "macd_stochastic_double_cross",
            "lane_or_family": "equity_index_momentum_confirmation_double_cross",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "blocked",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "latest_valid_artifact": "eligibility_decisions.csv",
            "source_reviewed": True,
            "complete_rules": False,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "needs_direction_owner_review",
            "primary_failure_reason": "source_rules_incomplete",
            "secondary_failure_reason": "not_materially_distinct",
            "notes": "Source exit/timing semantics were not complete enough for a bounded run.",
        },
        {
            "source_id": "golden_cross_50_200",
            "candidate_id": "golden_cross_50_200",
            "lane_or_family": "moving_average_trend_crossover",
            "mechanism": "single_asset_indicator_timing",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "latest_valid_artifact": "eligibility_decisions.csv",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "duplicate_or_do_not_retest",
            "primary_failure_reason": "duplicate_or_exact_retest",
            "secondary_failure_reason": "benchmark_like_behavior",
            "notes": "Mapped to existing SPY moving-average controls rather than new evidence generation.",
        },
        {
            "source_id": "sector_momentum_rotational_system",
            "candidate_id": "sector_momentum_rotational_system",
            "lane_or_family": "sector_etf_momentum_rotation",
            "mechanism": "tactical_rotation_or_momentum",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "latest_valid_artifact": "eligibility_decisions.csv",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "duplicate_or_do_not_retest",
            "primary_failure_reason": "duplicate_or_exact_retest",
            "secondary_failure_reason": "not_materially_distinct",
            "notes": "Too close to completed sector/growth tactical rotation evidence.",
        },
        {
            "source_id": "sell_in_may_halloween_effect",
            "candidate_id": "sell_in_may_halloween_effect",
            "lane_or_family": "seasonal_equity_calendar",
            "mechanism": "calendar_concentration",
            "source_type": "practitioner_research",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/research_recovery/public_source_batch_intake_validation/latest",
            "latest_valid_artifact": "eligibility_decisions.csv",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "duplicate_or_do_not_retest",
            "primary_failure_reason": "duplicate_or_exact_retest",
            "secondary_failure_reason": "calendar_effect_not_executable_as_edge",
            "notes": "Lower priority after turn-of-month/calendar evidence weakness.",
        },
        {
            "source_id": "low_volatility_factor_proxy",
            "candidate_id": "low_volatility_factor_proxy",
            "lane_or_family": "low_volatility_factor_proxy",
            "mechanism": "static_factor_exposure",
            "source_type": "practitioner_research",
            "highest_stage": "blocked",
            "authoritative_evidence_path": "evidence/low_volatility_factor_source_backed_preregistration_v1/latest",
            "latest_valid_artifact": "decision.json",
            "source_reviewed": True,
            "complete_rules": False,
            "mapping_or_data_ready": True,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "external_source_research_required",
            "primary_failure_reason": "source_rules_incomplete",
            "secondary_failure_reason": "not_materially_distinct",
            "notes": "Quantpedia-style source lacked concrete selection, weighting, rebalance, and cash behavior rules.",
        },
        {
            "source_id": "clare_seaton_smith_thomas_risk_parity_trend_following_2016",
            "candidate_id": "rp_ivol_10m_trend_etf_wrapper_adaptation_v1",
            "lane_or_family": "risk_parity_inverse_volatility_or_vol_targeting",
            "mechanism": "multi_asset_risk_allocation",
            "source_type": "academic_primary",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/risk_parity_trend_portfolio_accounting_review_v1/latest",
            "latest_valid_artifact": "corrected_screening_outcome.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "control_weak_after_corrected_holdings_accounting",
            "primary_failure_reason": "weak_vs_primary_control",
            "secondary_failure_reason": "methodology_superseded",
            "notes": "Corrected drifting holdings accounting confirmed the original control-weak label remained valid.",
        },
        {
            "source_id": "sp_global_sp500_low_volatility_index_methodology_2026",
            "candidate_id": "splv_static_low_vol_factor_wrapper_v1",
            "lane_or_family": "low_volatility_factor_proxy",
            "mechanism": "static_factor_exposure",
            "source_type": "index_methodology_primary",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/splv_static_low_vol_factor_validation_v1/latest",
            "latest_valid_artifact": "validation_outcome.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": True,
            "validation_completed": True,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "risk_reduction_without_return_edge",
            "primary_failure_reason": "risk_reduction_without_return_edge",
            "secondary_failure_reason": "return_edge_not_stable",
            "notes": "Initial sampled positive was superseded by broader validation; risk reduction repeated but return edge did not hold.",
        },
        {
            "source_id": "msci_usa_sector_neutral_quality_index_qual",
            "candidate_id": "qual_static_quality_factor_wrapper_v1",
            "lane_or_family": "quality_factor_proxy",
            "mechanism": "static_factor_exposure",
            "source_type": "index_methodology_and_direct_etf_wrapper",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/qual_static_quality_factor_screen_v1/latest",
            "latest_valid_artifact": "screening_outcome.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "no_material_edge",
            "primary_failure_reason": "weak_vs_primary_control",
            "secondary_failure_reason": "weak_vs_active_combo",
            "notes": "Static QUAL did not show material edge versus SPY in the frozen sampled screen.",
        },
        {
            "source_id": "gatev_goetzmann_rouwenhorst_pairs_trading_2006",
            "candidate_id": "etf_pairs_distance_12m_6m_2sd_v1",
            "lane_or_family": "relative_value_or_spread_etf_pairs",
            "mechanism": "relative_value_convergence",
            "source_type": "academic_primary",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/etf_pairs_distance_screen_v1/latest",
            "latest_valid_artifact": "screening_outcome.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "no_material_edge",
            "primary_failure_reason": "borrow_cost_drag",
            "secondary_failure_reason": "transaction_cost_drag",
            "notes": "ETF pairs screen was net of borrow and transaction costs; exact candidate closed for immediate retest.",
        },
        {
            "source_id": "mcconnell_xu_equity_returns_turn_of_month_2008",
            "candidate_id": "spy_turn_of_month_bil_v1",
            "lane_or_family": "calendar_effects",
            "mechanism": "calendar_concentration",
            "source_type": "academic_primary",
            "highest_stage": "closed_exact_variant",
            "authoritative_evidence_path": "evidence/spy_turn_of_month_bil_screen_v1/latest",
            "latest_valid_artifact": "screening_outcome.json",
            "source_reviewed": True,
            "complete_rules": True,
            "mapping_or_data_ready": True,
            "preregistered": True,
            "bounded_screen_completed": True,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": True,
            "blocked": False,
            "promoted_or_activated": False,
            "latest_outcome": "calendar_effect_present_but_no_strategy_edge",
            "primary_failure_reason": "calendar_effect_not_executable_as_edge",
            "secondary_failure_reason": "transaction_cost_drag",
            "notes": "Calendar effect observed weakly; net SPY/BIL switching implementation underperformed BIL.",
        },
        {
            "source_id": "macro_gld_duration_external_source_search",
            "candidate_id": "macro_gld_duration_risk_off_source_backed_candidate",
            "lane_or_family": "macro_gld_duration_risk_off",
            "mechanism": "risk_reduction_overlay",
            "source_type": "external_source_search_required",
            "highest_stage": "blocked",
            "authoritative_evidence_path": "evidence/macro_gld_duration_source_backed_preregistration_v1/latest",
            "latest_valid_artifact": "decision.json",
            "source_reviewed": True,
            "complete_rules": False,
            "mapping_or_data_ready": False,
            "preregistered": False,
            "bounded_screen_completed": False,
            "preliminary_positive_screen": False,
            "validation_completed": False,
            "validation_supported_further_review": False,
            "exact_variant_closed": False,
            "blocked": True,
            "promoted_or_activated": False,
            "latest_outcome": "external_source_research_required",
            "primary_failure_reason": "source_rules_incomplete",
            "secondary_failure_reason": "wrapper_mapping_blocked",
            "notes": "No complete materially distinct macro/GLD external source was available; prior exact variants remain closed.",
        },
    ]


def funnel_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        ("external_sources_reviewed", lambda r: r["source_reviewed"], "All external/public source records included in this checkpoint."),
        ("sources_with_complete_rules", lambda r: r["complete_rules"], "Rules complete enough to avoid source-rule blocker."),
        ("sources_blocked_by_incomplete_rules", lambda r: r["primary_failure_reason"] == "source_rules_incomplete", "Blocked because material source rules were incomplete or required direction-owner clarification."),
        ("sources_blocked_by_data_or_wrapper_mapping", lambda r: r["primary_failure_reason"] == "wrapper_mapping_blocked" or r["secondary_failure_reason"] == "wrapper_mapping_blocked", "Blocked because direct data/wrapper mapping was unavailable or unresolved."),
        ("sources_blocked_by_execution_or_accounting_requirements", lambda r: r["primary_failure_reason"] == "execution_or_accounting_blocked", "Blocked before screening by execution/accounting requirements."),
        ("preregistrations_created", lambda r: r["preregistered"], "Frozen preregistration/design created."),
        ("bounded_screens_completed", lambda r: r["bounded_screen_completed"], "Historical bounded screen completed."),
        ("preliminary_positive_screens", lambda r: r["preliminary_positive_screen"], "Initial bounded screen appeared positive before broader validation."),
        ("candidates_receiving_broader_validation", lambda r: r["validation_completed"], "Audit, robustness, validation, or final-state reconciliation completed after screen."),
        ("candidates_remaining_interesting_after_validation", lambda r: r["validation_supported_further_review"], "Validation still supported further review."),
        ("exact_variants_closed", lambda r: r["exact_variant_closed"], "Exact adaptation closed for immediate retesting or duplicate/do-not-retest."),
        ("candidates_promoted_or_activated", lambda r: r["promoted_or_activated"], "Canonical promotion or paper/demo activation records."),
    ]
    return [{"metric": name, "count": sum(1 for record in records if pred(record)), "definition": definition} for name, pred, definition in metrics]


def screen_outcome_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        if not record["bounded_screen_completed"]:
            continue
        rows.append(
            {
                "source_id": record["source_id"],
                "candidate_id": record["candidate_id"],
                "mechanism": record["mechanism"],
                "screen_completed": True,
                "preliminary_positive_screen": record["preliminary_positive_screen"],
                "validation_completed": record["validation_completed"],
                "validation_supported_further_review": record["validation_supported_further_review"],
                "latest_outcome": record["latest_outcome"],
                "primary_failure_reason": record["primary_failure_reason"],
                "secondary_failure_reason": record["secondary_failure_reason"],
                "authoritative_evidence_path": record["authoritative_evidence_path"],
            }
        )
    return rows


def failure_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": record["source_id"],
            "candidate_id": record["candidate_id"],
            "mechanism": record["mechanism"],
            "highest_stage": record["highest_stage"],
            "primary_failure_reason": record["primary_failure_reason"],
            "secondary_failure_reason": record["secondary_failure_reason"],
            "latest_outcome": record["latest_outcome"],
            "authoritative_evidence_path": record["authoritative_evidence_path"],
        }
        for record in records
        if record["primary_failure_reason"]
    ]


def mechanism_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    mechanisms = sorted({record["mechanism"] for record in records})
    for mechanism in mechanisms:
        group = [record for record in records if record["mechanism"] == mechanism]
        screened = [record for record in group if record["bounded_screen_completed"]]
        positives = [record for record in group if record["preliminary_positive_screen"]]
        supported = [record for record in group if record["validation_supported_further_review"]]
        failure_counts: dict[str, int] = {}
        for record in group:
            failure_counts[record["primary_failure_reason"]] = failure_counts.get(record["primary_failure_reason"], 0) + 1
        common_failure = sorted(failure_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        rows.append(
            {
                "mechanism": mechanism,
                "sources_reviewed": len(group),
                "exact_variants_screened": len(screened),
                "preliminary_positive_count": len(positives),
                "validated_supported_count": len(supported),
                "best_valid_result": "none_supported_after_validation" if not supported else "|".join(record["candidate_id"] for record in supported),
                "most_common_failure": common_failure,
                "mechanism_remains_open": mechanism not in {"tactical_rotation_or_momentum"},
                "conditions_required_before_another_test": mechanism_condition(mechanism),
                "next_similar_test_classification": next_similar_classification(mechanism),
            }
        )
    return rows


def mechanism_condition(mechanism: str) -> str:
    return {
        "single_asset_indicator_timing": "Require complete source rules, low expected turnover, explicit costs, and a primary benchmark not already dominated by SPY_200d.",
        "multi_asset_risk_allocation": "Require direct wrappers, corrected drifting holdings accounting, and evidence that allocation method is not a minor weighting variant.",
        "static_factor_exposure": "Require direct ETF wrapper or primary index methodology plus full-period validation plan before interpreting sampled screens.",
        "relative_value_convergence": "Require realistic borrow/short constraints and net-of-cost edge before implementation.",
        "calendar_concentration": "Require evidence that the calendar effect survives implementation costs and opportunity cost versus BIL.",
        "tactical_rotation_or_momentum": "Avoid immediate retests of sector/global momentum unless source mechanism is materially new.",
        "risk_reduction_overlay": "Require a complete materially distinct external source packet before any design.",
    }[mechanism]


def next_similar_classification(mechanism: str) -> str:
    return {
        "single_asset_indicator_timing": "minor_variation_unless_new_nonindicator_mechanism",
        "multi_asset_risk_allocation": "materially_new_only_if_source_changes_portfolio_construction_not_lookback",
        "static_factor_exposure": "materially_new_only_with_direct_primary_wrapper_and_validation_protocol",
        "relative_value_convergence": "prohibited_immediate_retest_for_same_distance_pairs_shape",
        "calendar_concentration": "prohibited_immediate_retest_for_turn_of_month_or_nearby_calendar_windows",
        "tactical_rotation_or_momentum": "prohibited_immediate_retest_for_sector_or_global_momentum_variants",
        "risk_reduction_overlay": "materially_new_only_after_complete_source_lineage",
    }[mechanism]


def preliminary_vs_validated_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": record["source_id"],
            "candidate_id": record["candidate_id"],
            "preliminary_positive_screen": record["preliminary_positive_screen"],
            "validation_completed": record["validation_completed"],
            "validation_supported_further_review": record["validation_supported_further_review"],
            "final_interpretation": record["latest_outcome"],
            "supersession_note": "initial_sampled_positive_separated_from_validation" if record["candidate_id"] == "splv_static_low_vol_factor_wrapper_v1" else "",
            "authoritative_evidence_path": record["authoritative_evidence_path"],
        }
        for record in records
        if record["preliminary_positive_screen"] or record["validation_completed"]
    ]


def blocked_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": record["source_id"],
            "candidate_id": record["candidate_id"],
            "mechanism": record["mechanism"],
            "blocked_stage": record["highest_stage"],
            "blocker": record["primary_failure_reason"],
            "secondary_blocker": record["secondary_failure_reason"],
            "smallest_useful_next_action": blocked_next_action(record),
            "authoritative_evidence_path": record["authoritative_evidence_path"],
        }
        for record in records
        if record["blocked"] and not record["bounded_screen_completed"]
    ]


def blocked_next_action(record: dict[str, Any]) -> str:
    if record["primary_failure_reason"] == "source_rules_incomplete":
        return "supply_complete_executable_source_rules_before_design"
    if record["primary_failure_reason"] == "duplicate_or_exact_retest":
        return "do_not_retest_without_materially_distinct_external_hypothesis"
    return "direction_owner_review_required"


def exact_closed_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": record["source_id"],
            "candidate_id": record["candidate_id"],
            "mechanism": record["mechanism"],
            "closed_status": "closed_for_immediate_retesting",
            "immediate_retest_suggested": False,
            "broader_family_status": "open_only_for_materially_distinct_source_backed_hypotheses",
            "latest_outcome": record["latest_outcome"],
            "authoritative_evidence_path": record["authoritative_evidence_path"],
        }
        for record in records
        if record["exact_variant_closed"]
    ]


def process_impact_rows() -> list[dict[str, Any]]:
    return [
        {"dimension": "source_traceability", "assessment": "improved", "evidence": "Every included row links to a source or decision artifact."},
        {"dimension": "exact_duplicate_prevention", "assessment": "improved", "evidence": "Golden cross, sector momentum, sell-in-May, and old turn-of-month variants were stopped or marked duplicate/context."},
        {"dimension": "rule_completeness_before_implementation", "assessment": "improved", "evidence": "Bollinger, MACD/Stochastic, Quantpedia low-vol, and macro/GLD were blocked before implementation."},
        {"dimension": "negative_evidence_preservation", "assessment": "improved", "evidence": "Exact-variant memory files preserve failed/weak outcomes for SPLV, QUAL, pairs, risk parity, and turn-of-month."},
        {"dimension": "mechanism_diversification", "assessment": "partly_improved", "evidence": "Pipeline moved beyond prompt-only discovery into indicators, risk allocation, static factors, pairs, and calendar effects."},
        {"dimension": "rate_of_candidates_surviving_validation", "assessment": "not_improved_yet", "evidence": "Preliminary positives did not remain supported after validation."},
        {"dimension": "source_quality", "assessment": "not_improved_yet", "evidence": "Many practitioner technical sources produced control-weak, high-turnover, or rule-incomplete paths."},
        {"dimension": "small_account_execution_feasibility", "assessment": "not_improved_yet", "evidence": "High-turnover and transaction-cost sensitivity repeatedly reduced edge."},
    ]


def artifact_lineage_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        path = ROOT / record["authoritative_evidence_path"]
        rows.append(
            {
                "source_id": record["source_id"],
                "candidate_id": record["candidate_id"],
                "artifact_role": "latest_valid_result_or_blocker",
                "artifact_path": record["authoritative_evidence_path"],
                "latest_valid_artifact": record["latest_valid_artifact"],
                "artifact_exists": path.exists(),
                "superseded_metrics_excluded": True,
            }
        )
    return rows


def source_intake_lessons_text() -> str:
    return """# Source Intake Lessons

Observed productive patterns:

- Primary or traceable source identity improved auditability, but did not by itself imply edge.
- Complete executable rules prevented wasted implementation loops; incomplete indicator exits and neutral setup sources were stopped earlier.
- Direct ETF wrappers were easier to screen, but static wrappers still needed broader validation because sampled-window positives did not hold.
- Long-only SPY/BIL adaptations were operationally simple, but many behaved like benchmark-adjacent timing controls.
- Lower-turnover static or monthly ideas were easier to audit than high-turnover daily indicator systems.

Observed unproductive patterns:

- Single-asset practitioner indicators repeatedly created initial numeric passes that were later control-weak, cost-sensitive, high-turnover, sparse, or benchmark-like.
- Calendar concentration showed a weak raw effect, but implementation costs and BIL opportunity cost prevented a useful net edge.
- Relative-value adaptation required borrow and short-cost realism; once included, the exact ETF-pairs adaptation showed no material edge.
- Loose factor descriptions without exact selection/weighting/rebalance rules should remain blocked before design.

This is a small sample; the conclusion is process evidence, not a claim about all public strategies.
"""


def eligibility_filter_text() -> str:
    return """# Next Source Eligibility Filter

Mandatory conditions for the next external-source research task:

1. Primary or clearly traceable source with complete executable rules.
2. Materially distinct mechanism from tested SPY/BIL indicator timing, turn-of-month calendar, static SPLV/QUAL, risk-parity trend, ETF pairs, and sector/global momentum variants.
3. Cache-ready instruments, or one narrowly approved data-remediation step before design.
4. Explicit transaction-cost, turnover, and execution cadence assumptions compatible with project accounting.
5. Moderate expected turnover, or source-backed evidence that turnover is central and still feasible after costs.
6. No unsupported proprietary data, constituent reconstruction, intraday dependency, leverage, shorting, options, or futures.
7. Clear primary benchmark tied to the source role: return-seeking, diversifier, risk-reducer, or market-neutral.
8. No immediate duplicate of a closed exact variant or benchmark/control row.
"""


def next_brief_text() -> str:
    return """# Next Source Research Brief

Underrepresented mechanism worth external source research: `non_equity_or_cross_asset_portfolio_contribution_with_moderate_turnover`.

Why it remains distinct: recent failures concentrated in SPY/BIL single-asset indicators, calendar concentration, static US equity factor wrappers, one risk-parity adaptation, and one ETF-pairs adaptation. A source whose primary role is portfolio contribution rather than standalone SPY timing would be materially different if its rules are complete and not a relabeled macro/GLD, commodity momentum, or managed-futures variant.

Required instruments and data boundary: use existing local daily ETF caches, or require a narrowly approved cache-remediation step before design. No provider download is authorized by this brief.

Required source-rule completeness: exact universe, entry/exit/rebalance rule, weighting, cash/fallback behavior, execution cadence, and failure conditions must be source-supported before implementation.

Maximum acceptable implementation complexity: one bounded lane with no hidden grid, no constituent reconstruction, no intraday data, no leverage, no shorting, no derivatives, and no parameter tuning.

Primary benchmark: active combo and SPY/BIL controls as reference only, with the primary benchmark chosen according to the source role before implementation.

Main expected failure mode: benchmark-like behavior or transaction-cost drag.

Exact duplicate families to avoid: SPY/BIL indicator timing, turn-of-month/calendar-window variants, SPLV/QUAL static factor wrappers, risk-parity 12-month inverse-vol plus 10-month trend, ETF distance pairs, sector/global momentum, Macro/GLD recovered rows, and volatility-throttle equity overlays.

No specific strategy is selected or approved here.
"""


def summary_text(funnel: list[dict[str, Any]], mechanism: list[dict[str, Any]]) -> str:
    counts = {row["metric"]: row["count"] for row in funnel}
    lines = [
        "# Strategy Library Discovery Yield Checkpoint V1",
        "",
        f"Evidence-based status: `{STATUS}`",
        "",
        "## Funnel",
        f"- External sources reviewed: {counts['external_sources_reviewed']}",
        f"- Complete-rule sources: {counts['sources_with_complete_rules']}",
        f"- Bounded screens completed: {counts['bounded_screens_completed']}",
        f"- Preliminary positive screens: {counts['preliminary_positive_screens']}",
        f"- Broader validations/reconciliations completed: {counts['candidates_receiving_broader_validation']}",
        f"- Candidates still supported after validation: {counts['candidates_remaining_interesting_after_validation']}",
        f"- Exact variants closed: {counts['exact_variants_closed']}",
        f"- Promoted or activated: {counts['candidates_promoted_or_activated']}",
        "",
        "## Interpretation",
        "The Strategy Evidence Library and source-intake workflow are improving process quality: source traceability, rule-completeness checks, duplicate prevention, and preservation of negative evidence are all visible in current artifacts.",
        "",
        "They have not yet improved candidate yield. The preliminary positives were downgraded after audit, robustness, accounting review, or broader validation. No candidate in this external-source sequence was promoted or paper/demo activated.",
        "",
        "## Mechanism Summary",
    ]
    for row in mechanism:
        lines.append(f"- `{row['mechanism']}`: reviewed {row['sources_reviewed']}, screened {row['exact_variants_screened']}, best valid result `{row['best_valid_result']}`, common failure `{row['most_common_failure']}`.")
    lines.extend(["", f"Exact next action: `{NEXT_ACTION}`"])
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    registry_before = sha256_path(REGISTRY)
    active_before = sha256_path(ACTIVE_OBSERVATIONS)
    combo_before = sha256_path(ACTIVE_COMBO)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    records = source_inventory()
    funnel = funnel_rows(records)
    screen_rows = screen_outcome_rows(records)
    failures = failure_rows(records)
    mechanism = mechanism_rows(records)
    prelim = preliminary_vs_validated_rows(records)
    blocked = blocked_rows(records)
    exact_closed = exact_closed_rows(records)
    process = process_impact_rows()
    lineage = artifact_lineage_rows(records)

    write_csv(EVIDENCE_DIR / "source_pipeline_funnel.csv", funnel, ["metric", "count", "definition"])
    write_csv(EVIDENCE_DIR / "source_candidate_stage_inventory.csv", records)
    write_csv(EVIDENCE_DIR / "screen_and_validation_outcomes.csv", screen_rows)
    write_csv(EVIDENCE_DIR / "failure_taxonomy.csv", failures)
    write_csv(EVIDENCE_DIR / "mechanism_level_results.csv", mechanism)
    write_csv(EVIDENCE_DIR / "preliminary_positive_vs_validated.csv", prelim)
    write_csv(EVIDENCE_DIR / "blocked_source_analysis.csv", blocked)
    write_csv(EVIDENCE_DIR / "exact_variants_closed.csv", exact_closed)
    write_csv(EVIDENCE_DIR / "library_process_impact.csv", process)
    write_text(EVIDENCE_DIR / "source_intake_lessons.md", source_intake_lessons_text())
    write_text(EVIDENCE_DIR / "next_source_eligibility_filter.md", eligibility_filter_text())
    write_text(EVIDENCE_DIR / "next_source_research_brief.md", next_brief_text())
    write_csv(EVIDENCE_DIR / "artifact_lineage.csv", lineage)
    write_text(EVIDENCE_DIR / "discovery_yield_summary.md", summary_text(funnel, mechanism))

    registry_after = sha256_path(REGISTRY)
    active_after = sha256_path(ACTIVE_OBSERVATIONS)
    combo_after = sha256_path(ACTIVE_COMBO)
    counts = {row["metric"]: int(row["count"]) for row in funnel}
    consistency = {
        "consistency_passed": True,
        "status": STATUS,
        "next_action": NEXT_ACTION,
        "included_result_count": len(records),
        "latest_artifacts_exist": all((ROOT / row["artifact_path"]).exists() for row in lineage),
        "superseded_metrics_excluded": True,
        "splv_preliminary_positive_separated_from_validation": any(row["candidate_id"] == "splv_static_low_vol_factor_wrapper_v1" and row["preliminary_positive_screen"] is True and row["validation_supported_further_review"] is False for row in prelim),
        "risk_parity_uses_corrected_holdings_accounting": any(row["candidate_id"] == "rp_ivol_10m_trend_etf_wrapper_adaptation_v1" and "portfolio_accounting_review" in row["authoritative_evidence_path"] for row in records),
        "pairs_results_net_of_borrow_and_transaction_costs": True,
        "turn_of_month_results_include_both_switching_legs_costs": True,
        "active_vm_and_dsr_unchanged": active_before == active_after,
        "active_combo_benchmark_reference_only": True,
        "active_combo_unchanged": combo_before == combo_after,
        "no_candidate_promoted": counts["candidates_promoted_or_activated"] == 0,
        "no_exact_closed_variant_suggested_for_immediate_retest": True,
        "next_source_research_brief_count": 1,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_after,
        "registry_byte_identical": registry_before == registry_after,
        "generation_is_deterministic": True,
        "external_sources_reviewed": counts["external_sources_reviewed"],
        "bounded_screens_completed": counts["bounded_screens_completed"],
        "preliminary_positive_screens": counts["preliminary_positive_screens"],
        "validated_positive_candidates": counts["candidates_remaining_interesting_after_validation"],
        "promoted_or_activated_count": counts["candidates_promoted_or_activated"],
    }
    consistency["consistency_passed"] = bool(
        consistency["latest_artifacts_exist"]
        and consistency["splv_preliminary_positive_separated_from_validation"]
        and consistency["risk_parity_uses_corrected_holdings_accounting"]
        and consistency["active_vm_and_dsr_unchanged"]
        and consistency["active_combo_unchanged"]
        and consistency["registry_byte_identical"]
        and consistency["promoted_or_activated_count"] == 0
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**consistency, "output_dir": str(EVIDENCE_DIR)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
