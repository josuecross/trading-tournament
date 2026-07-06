from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import dotted_get, read_json, read_yaml


SOURCE_ID = "coppock_curve_monthly_equity_signal"
LANE_ID = "public_source_coppock_curve_bounded_bt_lane_v1"
FAMILY_ID = "long_term_equity_index_momentum_zero_cross"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_coppock_curve_bounded_bt_design"
    / "latest"
)
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "coppock_curve_monthly_equity_signal.yaml"
)
INTAKE_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
INTAKE_MANIFEST_PATH = INTAKE_EVIDENCE_DIR / "public_source_intake_validation_manifest.json"
BATCH_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
BATCH_ELIGIBILITY_PATH = BATCH_EVIDENCE_DIR / "eligibility_decisions.csv"
CONSISTENCY_EVIDENCE_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_coppock_intake_evidence_consistency"
    / "latest"
)
CONSISTENCY_MANIFEST_PATH = CONSISTENCY_EVIDENCE_DIR / "coppock_intake_evidence_consistency_manifest.json"
BT_CONTROL_MANIFEST_PATH = (
    Path("evidence") / "research_recovery" / "bt_adapter_control_poc" / "latest" / "bt_adapter_control_poc_manifest.json"
)
BT_MULTIASSET_MANIFEST_PATH = (
    Path("evidence")
    / "research_recovery"
    / "bt_adapter_multasset_control_poc"
    / "latest"
    / "bt_adapter_multasset_control_poc_manifest.json"
)

RUN_READY = "public_source_coppock_curve_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_coppock_curve_bounded_bt_design_blocked"
NEXT_ACTION_RUN = "run_public_source_coppock_curve_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "manual_input_required_for_coppock_curve_bounded_bt_design"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
SIMILARITY_CONTEXTS = (
    "spy200d_trend_control",
    "global_multi_asset",
    "macro_gld_duration_risk_off",
    "high_return_tactical_equity",
    "volatility_throttle_volatility_managed_equity",
    "turn_of_month_calendar_effect",
    "mean_reversion_rejected_or_existing_candidate",
    "price_band_money_flow_confirmation",
)
SOURCE_BACKED_PARAMS = {
    "parameter_status": "source_backed_parameters",
    "roc_period_1": 14,
    "roc_period_2": 11,
    "wma_smoothing_period": 10,
    "signal_threshold": 0,
    "signal_frequency": "completed_monthly_close_only",
    "tuned_parameters": False,
}

PLANNED_ROW_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "symbols",
    "formula",
    "roc_periods",
    "wma_smoothing_period",
    "threshold",
    "entry_rule",
    "exit_rule",
    "signal_timing",
    "source_backed_parameters",
    "baseline_or_control_role",
    "comparator_references",
    "similarity_context_carried_forward",
    "sparse_signal_risk_carried_forward",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)
CACHE_FIELDS = (
    "symbol",
    "required",
    "cache_status",
    "cache_path",
    "first_date",
    "last_date",
    "rows",
    "required_columns",
    "columns_present",
    "data_requirement_status",
    "notes",
)
PARAM_FIELDS = ("parameter", "value", "source_status", "tuned", "notes")

REQUIRED_FILES = (
    "public_source_coppock_curve_bounded_bt_design_manifest.json",
    "public_source_coppock_curve_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "source_backed_parameter_report.csv",
    "source_backed_parameter_report.md",
    "formula_monthly_signal_definition.md",
    "source_caveat_sell_exit_rule.md",
    "similarity_risk_report.md",
    "sparse_signal_risk_report.md",
    "planned_row_table.csv",
    "planned_row_table.md",
    "signal_timing_convention.md",
    "baseline_control_policy.md",
    "numeric_success_failure_criteria.md",
    "bt_adapter_readiness.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "run_readiness_decision.md",
    "public_source_coppock_curve_bounded_bt_design_next_action.md",
    "public_source_coppock_curve_bounded_bt_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def source_intake_review(root: Path) -> dict[str, Any]:
    intake = read_yaml(root / INTAKE_PATH)
    intake_manifest = read_json(root / INTAKE_MANIFEST_PATH)
    consistency_manifest = read_json(root / CONSISTENCY_MANIFEST_PATH)
    eligibility_rows = read_csv_rows(root / BATCH_ELIGIBILITY_PATH)
    batch_row = next((row for row in eligibility_rows if row.get("source_id") == SOURCE_ID), {})
    return {
        "candidate_exists": (root / INTAKE_PATH).exists(),
        "source_id": dotted_get(intake, "source.source_id") or "",
        "source_name": dotted_get(intake, "source.source_name") or "",
        "source_citation": dotted_get(intake, "source.source_url_or_citation") or "",
        "source_type": dotted_get(intake, "source.source_type") or "",
        "strategy_family": dotted_get(intake, "strategy_description.strategy_family") or "",
        "instruments": dotted_get(intake, "strategy_description.instruments") or [],
        "timeframe": dotted_get(intake, "strategy_description.timeframe") or "",
        "formula": dotted_get(intake, "rules.formula") or "",
        "roc_periods": dotted_get(intake, "rules.indicator_definitions.roc_periods") or [],
        "smoothing": dotted_get(intake, "rules.indicator_definitions.smoothing") or "",
        "signal_threshold": dotted_get(intake, "rules.indicator_definitions.signal_threshold") or "",
        "data_frequency": dotted_get(intake, "rules.indicator_definitions.data_frequency") or "",
        "source_backed_parameters": dotted_get(intake, "rules.indicator_definitions.source_backed_parameters"),
        "entry_rule": dotted_get(intake, "rules.entry_rule") or "",
        "exit_rule": dotted_get(intake, "rules.exit_rule") or "",
        "execution_assumptions": dotted_get(intake, "data_and_execution.execution_assumptions") or "",
        "source_uncertainty": dotted_get(intake, "project_notes.source_uncertainty") or "",
        "similarity_notes": dotted_get(intake, "project_notes.similarity_notes") or "",
        "similarity_contexts": dotted_get(intake, "project_screening.similar_already_tested_project_families") or [],
        "do_not_retest_match": dotted_get(intake, "project_screening.do_not_retest_match") or "",
        "intake_evidence_exists": bool(intake_manifest),
        "intake_evidence_path": str((root / INTAKE_EVIDENCE_DIR).resolve()),
        "intake_eligibility_decision": intake_manifest.get("eligibility_decision", ""),
        "intake_constraint_blockers": "|".join(intake_manifest.get("constraint_blockers", [])),
        "intake_missing_fields": "|".join(intake_manifest.get("exact_missing_fields", [])),
        "intake_similarity_hits": "|".join(intake_manifest.get("family_similarity_hits", [])),
        "batch_evidence_exists": (root / BATCH_ELIGIBILITY_PATH).exists(),
        "batch_evidence_path": str((root / BATCH_EVIDENCE_DIR).resolve()),
        "batch_eligibility_decision": batch_row.get("eligibility_decision", ""),
        "batch_next_action": batch_row.get("next_action", ""),
        "batch_constraint_blocks": batch_row.get("constraint_blocks", ""),
        "batch_similarity_hits": batch_row.get("family_similarity_hits", ""),
        "batch_missing_required_fields": batch_row.get("missing_required_fields", ""),
        "batch_local_cache_complete": str(batch_row.get("local_cache_complete", "")).lower() == "true",
        "consistency_evidence_exists": bool(consistency_manifest),
        "consistency_evidence_path": str((root / CONSISTENCY_EVIDENCE_DIR).resolve()),
        "candidate_specific_evidence_valid": consistency_manifest.get("candidate_specific_evidence_valid") is True,
        "coppock_yaml_valid": consistency_manifest.get("coppock_yaml_valid") is True,
        "verification_decision": consistency_manifest.get("verification_decision", ""),
        "duplicate_do_not_retest_decision": consistency_manifest.get("duplicate_do_not_retest_decision") is True,
        "larry_connors_yaml_current_diff_present": consistency_manifest.get("larry_connors_yaml_current_diff_present") is True,
        "source_intake": intake,
    }


def cache_rows(root: Path) -> list[dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    required_by_symbol = {
        "SPY": ("date", "adj_close", "close"),
        "BIL": ("date", "adj_close", "close"),
    }
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        info = inventory.get(symbol, {})
        cache_path = Path(str(info.get("path", "")))
        if cache_path and not cache_path.is_absolute():
            cache_path = root / cache_path
        columns = csv_header(cache_path) if cache_path else []
        required_columns = required_by_symbol[symbol]
        missing_columns = [column for column in required_columns if column not in columns]
        cache_ready = info.get("status") == "cache_ready" and not missing_columns
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_status": "cache_ready" if cache_ready else info.get("status", "missing"),
                "cache_path": info.get("path", ""),
                "first_date": info.get("first_date", ""),
                "last_date": info.get("last_date", ""),
                "rows": info.get("rows", 0),
                "required_columns": "|".join(required_columns),
                "columns_present": "|".join(columns),
                "data_requirement_status": "daily_adjusted_close_ready"
                if cache_ready
                else "missing_required_adjusted_close_cache",
                "notes": "local_raw_price_history_available_no_provider_download"
                if cache_ready
                else "required_local_price_history_not_ready",
            }
        )
    return rows


def parameter_rows() -> list[dict[str, Any]]:
    return [
        {
            "parameter": key,
            "value": value,
            "source_status": "source_backed_parameters",
            "tuned": False,
            "notes": "frozen_from_validated_coppock_public_source_intake_no_optimization",
        }
        for key, value in SOURCE_BACKED_PARAMS.items()
    ]


def parameter_text() -> str:
    return "|".join(f"{key}={value}" for key, value in SOURCE_BACKED_PARAMS.items())


def planned_rows() -> list[dict[str, Any]]:
    params = parameter_text()
    formula = "Coppock Curve = WMA10(ROC14 + ROC11), computed on completed monthly SPY adjusted closes"
    similarity = "|".join(SIMILARITY_CONTEXTS)
    sparse_risk = "monthly_low_event_count_must_be_reported_in_run"
    return [
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "coppock_spy_bil_monthly_zero_cross_primary_v1",
            "variant_role": "source_primary",
            "research_label": "public_source_coppock_curve_primary",
            "symbols": "SPY|BIL",
            "formula": formula,
            "roc_periods": "14|11",
            "wma_smoothing_period": 10,
            "threshold": 0,
            "entry_rule": "Enter or hold SPY after completed monthly Coppock crosses from negative to positive",
            "exit_rule": "Exit to BIL/cash after completed monthly Coppock crosses from positive to negative",
            "signal_timing": "completed_month_end_close_signal_then_next_available_trading_date_shifted_weight",
            "source_backed_parameters": params,
            "baseline_or_control_role": "primary_source_interpretation",
            "comparator_references": "SPY_buy_hold_control|BIL_cash_control|SPY_200d_frozen_control",
            "similarity_context_carried_forward": similarity,
            "sparse_signal_risk_carried_forward": sparse_risk,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "coppock_spy_bil_one_month_delayed_timing_sanity_v1",
            "variant_role": "timing_sanity",
            "research_label": "public_source_coppock_curve_timing_sanity",
            "symbols": "SPY|BIL",
            "formula": formula,
            "roc_periods": "14|11",
            "wma_smoothing_period": 10,
            "threshold": 0,
            "entry_rule": "Same source zero-cross entry applied one additional completed month later; timing sanity only",
            "exit_rule": "Same source zero-cross exit applied one additional completed month later; timing sanity only",
            "signal_timing": "one_additional_completed_month_delay_not_optimized",
            "source_backed_parameters": params,
            "baseline_or_control_role": "timing_sanity_context_only_not_parameter_sweep",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|BIL_cash_control|SPY_200d_frozen_control",
            "similarity_context_carried_forward": similarity,
            "sparse_signal_risk_carried_forward": sparse_risk,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "coppock_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "public_source_coppock_curve_control_only",
            "symbols": "SPY",
            "formula": "not_applicable_control",
            "roc_periods": "not_applicable_control",
            "wma_smoothing_period": "not_applicable_control",
            "threshold": "not_applicable_control",
            "entry_rule": "SPY buy-and-hold same-window control",
            "exit_rule": "not_applicable_control",
            "signal_timing": "control-only benchmark convention documented by future run",
            "source_backed_parameters": "not_applicable_control",
            "baseline_or_control_role": "buy_hold_control_only",
            "comparator_references": "primary_source_row|BIL_cash_control|SPY_200d_frozen_control",
            "similarity_context_carried_forward": similarity,
            "sparse_signal_risk_carried_forward": "control_only",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "coppock_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "public_source_coppock_curve_control_only",
            "symbols": "BIL",
            "formula": "not_applicable_control",
            "roc_periods": "not_applicable_control",
            "wma_smoothing_period": "not_applicable_control",
            "threshold": "not_applicable_control",
            "entry_rule": "BIL cash same-window control",
            "exit_rule": "not_applicable_control",
            "signal_timing": "control-only benchmark convention documented by future run",
            "source_backed_parameters": "not_applicable_control",
            "baseline_or_control_role": "cash_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|SPY_200d_frozen_control",
            "similarity_context_carried_forward": similarity,
            "sparse_signal_risk_carried_forward": "control_only",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "coppock_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "public_source_coppock_curve_control_only",
            "symbols": "SPY|BIL",
            "formula": "not_applicable_control",
            "roc_periods": "not_applicable_control",
            "wma_smoothing_period": "not_applicable_control",
            "threshold": "not_applicable_control",
            "entry_rule": "existing project SPY 200d frozen control where supported",
            "exit_rule": "existing project SPY 200d frozen control where supported",
            "signal_timing": "use already validated bt adapter SPY_200d control convention",
            "source_backed_parameters": "not_applicable_control",
            "baseline_or_control_role": "spy200d_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|BIL_cash_control",
            "similarity_context_carried_forward": similarity,
            "sparse_signal_risk_carried_forward": "control_only",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
    ]


def bt_readiness(root: Path) -> dict[str, Any]:
    control = read_json(root / BT_CONTROL_MANIFEST_PATH)
    multasset = read_json(root / BT_MULTIASSET_MANIFEST_PATH)
    return {
        "bt_control_manifest_exists": bool(control),
        "bt_control_poc_passed": control.get("final_adapter_decision") == "bt_adapter_control_poc_passed",
        "bt_control_exposure_invariant_passed": control.get("exposure_invariant_passed") is True,
        "bt_multasset_manifest_exists": bool(multasset),
        "bt_multasset_poc_passed": multasset.get("final_adapter_decision")
        == "bt_adapter_multasset_control_poc_passed",
        "bt_multasset_exposure_invariant_passed": multasset.get("exposure_invariant_passed") is True,
        "bt_adapter_ready_for_design": control.get("final_adapter_decision") == "bt_adapter_control_poc_passed"
        and multasset.get("final_adapter_decision") == "bt_adapter_multasset_control_poc_passed",
        "bt_package_version": multasset.get("bt_package_version") or control.get("bt_package_version") or "unknown",
    }


def source_parameters_complete(review: dict[str, Any]) -> bool:
    return (
        review["roc_periods"] == [14, 11]
        and "10-period" in str(review["smoothing"])
        and "weighted moving average" in str(review["smoothing"]).lower()
        and str(review["signal_threshold"]).lower() == "zero line"
        and str(review["data_frequency"]).lower() == "monthly"
        and review["source_backed_parameters"] is True
    )


def run_readiness(
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[str, str, str]:
    blockers: list[str] = []
    if review["source_id"] != SOURCE_ID:
        blockers.append("validated_coppock_curve_candidate_not_found")
    if review["strategy_family"] != FAMILY_ID:
        blockers.append("coppock_family_mismatch")
    if review["intake_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("single_intake_not_eligible_for_bounded_bt_design")
    if review["batch_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("batch_intake_not_eligible_for_bounded_bt_design")
    if review["intake_constraint_blockers"] or review["batch_constraint_blocks"]:
        blockers.append("constraint_blocks_present")
    if review["intake_missing_fields"] or review["batch_missing_required_fields"]:
        blockers.append("missing_required_intake_fields_present")
    if not review["candidate_specific_evidence_valid"] or review["verification_decision"] != "coppock_intake_evidence_consistent_ready_for_design":
        blockers.append("coppock_intake_consistency_not_ready_for_design")
    if review["duplicate_do_not_retest_decision"]:
        blockers.append("coppock_marked_duplicate_or_do_not_retest")
    if review["larry_connors_yaml_current_diff_present"]:
        blockers.append("larry_connors_yaml_contamination_still_present")
    if review["instruments"] != ["SPY", "BIL"]:
        blockers.append("coppock_instruments_not_limited_to_spy_bil")
    if tuple(review["similarity_contexts"]) != SIMILARITY_CONTEXTS:
        blockers.append("coppock_similarity_context_not_preserved_exactly")
    if not source_parameters_complete(review):
        blockers.append("coppock_source_backed_monthly_parameters_incomplete")
    if any(row["cache_status"] != "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache_or_adjusted_close_columns")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_prerequisites_not_ready")
    if not (4 <= len(rows) <= 5):
        blockers.append("planned_row_count_outside_declared_4_to_5_bounds")
    if SOURCE_BACKED_PARAMS["tuned_parameters"] is not False:
        blockers.append("source_parameters_not_marked_untuned")
    if blockers:
        return RUN_BLOCKED, ";".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


def source_intake_review_md(review: dict[str, Any]) -> str:
    return f"""# Source Intake Review

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Source citation: `{review['source_citation']}`

Source type: `{review['source_type']}`

Strategy family: `{review['strategy_family']}`

Timeframe: `{review['timeframe']}`

Single-source intake evidence path: `{review['intake_evidence_path']}`

Single-source intake decision: `{review['intake_eligibility_decision']}`

Batch intake evidence path: `{review['batch_evidence_path']}`

Batch intake decision: `{review['batch_eligibility_decision']}`

Consistency evidence path: `{review['consistency_evidence_path']}`

Consistency verification decision: `{review['verification_decision']}`

Candidate-specific evidence valid: `{review['candidate_specific_evidence_valid']}`

Constraint blockers: `{review['intake_constraint_blockers'] or review['batch_constraint_blocks'] or 'none'}`

Missing required fields: `{review['intake_missing_fields'] or review['batch_missing_required_fields'] or 'none'}`

Duplicate/do-not-retest decision: `{review['duplicate_do_not_retest_decision']}`

Larry Connors YAML current diff present: `{review['larry_connors_yaml_current_diff_present']}`

Entry rule: `{review['entry_rule']}`

Exit rule: `{review['exit_rule']}`

The source is manually supplied context only and is not proof of profitability.
"""


def local_cache_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    for row in rows:
        lines.append(
            f"- `{row['symbol']}`: `{row['cache_status']}`, first `{row['first_date']}`, "
            f"last `{row['last_date']}`, rows `{row['rows']}`, requirement `{row['data_requirement_status']}`"
        )
    lines.append("")
    lines.append("No provider download was used or authorized.")
    return "\n".join(lines) + "\n"


def source_backed_parameter_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Source-Backed Parameter Report", ""]
    lines.append("All frozen parameters come from the validated Coppock public-source intake.")
    lines.append("No daily or weekly variant, ROC-period sweep, smoothing-period sweep, signal line, filter, stop-loss, profit target, divergence rule, or alternate exit was added.")
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['parameter']}`: `{row['value']}`; tuned `{row['tuned']}`")
    return "\n".join(lines) + "\n"


def formula_definition_md(review: dict[str, Any]) -> str:
    return f"""# Formula And Monthly Signal Definition

Formula: `{review['formula']}`

ROC periods: `{review['roc_periods']}`

Smoothing: `{review['smoothing']}`

Threshold: `{review['signal_threshold']}`

Data frequency: `{review['data_frequency']}`

Signal source close: completed monthly close only.

Execution convention for a future run: compute the completed-month signal first, then apply target weights using the project no-lookahead shifted-weight convention on the next available trading date.

The design packet does not implement or run the formula.
"""


def source_caveat_md(review: dict[str, Any]) -> str:
    return f"""# Source Caveat For Sell / Exit Rule

Recorded caveat:

`{review['source_uncertainty']}`

Design treatment:

- The primary source row freezes the positive zero-cross entry and negative zero-cross exit exactly as validated.
- The negative zero-cross exit is carried forward as source-supported/common analyst use, with this caveat visible in run evidence.
- No additional exits, stop-losses, profit targets, moving-average filters, volatility filters, signal lines, or divergence rules were added.
"""


def similarity_risk_md(review: dict[str, Any]) -> str:
    lines = ["# Similarity Risk Report", ""]
    lines.append("Similarity context carried into this design:")
    lines.append("")
    for context in SIMILARITY_CONTEXTS:
        lines.append(f"- `{context}`")
    lines.append("")
    lines.append(f"Intake similarity hits: `{review['intake_similarity_hits'] or 'none'}`")
    lines.append("")
    lines.append("Duplicate/do-not-retest blocker in current verified state: `false`")
    lines.append("")
    lines.append("Run evidence must carry these contexts forward. This design does not treat similarity as a current blocker, and it does not reopen or retest Faber/TAA, Turn-of-the-Month, Percent B, Larry Connors, macro, commodity, high-return tactical, volatility-throttle, managed-futures, crypto, or regional momentum lanes.")
    return "\n".join(lines) + "\n"


def sparse_signal_md() -> str:
    return """# Sparse-Signal Risk Report

This is a monthly zero-cross signal and may have a low event count.

Any future bounded run must report:

- event count
- trade count
- holding duration
- subperiod coverage
- sample adequacy
- whether low event count forces a sparse/context-only interpretation

If event count is very low, the row must be labeled sparse/context-only even if return criteria pass. This packet does not compute any event count.
"""


def planned_rows_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Row Table", ""]
    for row in rows:
        lines.append(f"- `{row['variant_id']}`: role `{row['variant_role']}`, label `{row['research_label']}`")
    lines.append("")
    lines.append("All rows are diagnostic and non-promotable. Control rows are controls only.")
    return "\n".join(lines) + "\n"


def signal_timing_md() -> str:
    return """# Signal Timing Convention

Future Coppock Curve bounded `bt` runs must freeze timing before execution:

- Use local-cache daily adjusted close data only.
- Convert SPY adjusted daily closes into completed monthly closes.
- Compute ROC(14), ROC(11), and WMA(10) only after the completed month-end close.
- Primary row enters or holds SPY only after a completed monthly negative-to-positive zero-cross.
- Primary row exits to BIL/cash only after a completed monthly positive-to-negative zero-cross.
- Apply target weights using the project's no-lookahead shifted-weight convention on the next available trading date.
- One additional completed-month delay may be included only as a timing-sanity/context row, not as an optimized variant.
- No daily Coppock, weekly Coppock, alternate ROC periods, alternate smoothing periods, signal lines, filters, stops, profit targets, divergence rules, provider download, or intraday data may be used.
"""


def baseline_policy_md() -> str:
    return """# Baseline / Control Policy

Diagnostic controls for any future bounded run:

- SPY buy-and-hold same-window control.
- BIL cash same-window control.
- SPY_200d frozen control where existing project conventions support it without adding new strategy logic.

Controls are benchmark/control rows only. They cannot become promotion candidates, candidate_exhaustive rows, paper-forward candidates, broker/live rows, or real-money recommendations.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run criteria are research-only and not promotion gates.

The primary source row can be considered diagnostically useful only if all applicable criteria are true:

- Primary total return beats BIL by `> 0.0000`.
- If a standard project public-source cost model exists at run time, excess return versus BIL after that cost model remains `> 0.0000`.
- Max drawdown reduction versus SPY buy-and-hold is `>= 0.2000` relative improvement.
- Return/drawdown proxy beats SPY buy-and-hold by `> 0.0000`.
- Average SPY exposure share is `>= 0.0500` and `<= 0.9500`.
- Duplicate/reference correlation versus SPY buy-and-hold and SPY_200d control is `< 0.9500` where available.
- Event count is reported; if very low, label as sparse/context-only even if returns pass.
- Exposure invariants pass.

Timing-sanity row is context only and cannot supersede the source-primary row.

Allowed labels:

- `public_source_coppock_curve_primary`
- `public_source_coppock_curve_timing_sanity`
- `public_source_coppock_curve_control_only`
- `public_source_coppock_curve_sparse_context_only`
- `public_source_coppock_curve_design_blocked`
"""


def bt_readiness_md(bt: dict[str, Any]) -> str:
    return f"""# bt Adapter Readiness

Control POC passed: `{bt['bt_control_poc_passed']}`

Control POC exposure invariant passed: `{bt['bt_control_exposure_invariant_passed']}`

Multasset POC passed: `{bt['bt_multasset_poc_passed']}`

Multasset POC exposure invariant passed: `{bt['bt_multasset_exposure_invariant_passed']}`

bt adapter ready for design: `{bt['bt_adapter_ready_for_design']}`

bt package version: `{bt['bt_package_version']}`

No bt run is executed by this design packet.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_coppock_curve_bounded_bt_design_only",
        "bounded_bt_lane_run",
        "bounded_run_implementation_created",
        "strategy_backtest_run",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "additional_public_sources_ingested",
        "daily_coppock_variants_added",
        "weekly_coppock_variants_added",
        "alternate_roc_periods_added",
        "alternate_smoothing_periods_added",
        "signal_lines_added",
        "moving_average_filters_added",
        "volatility_filters_added",
        "stop_loss_or_profit_target_added",
        "divergence_rules_added",
        "additional_exits_added",
        "parameter_sweep_created",
        "optimization_run",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "current_backtester_replaced",
        "strategy_discovery_run",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return {key: manifest[key] for key in keys}


def exposure_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future Coppock Curve bounded `bt` run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    readiness, blocker, next_action = run_readiness(review, cache, bt, rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_coppock_curve_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_intake_reviewed": review["candidate_exists"],
        "single_source_intake_evidence_reviewed": review["intake_evidence_exists"],
        "batch_intake_evidence_reviewed": review["batch_evidence_exists"],
        "source_intake_eligibility_decision": review["intake_eligibility_decision"],
        "batch_intake_eligibility_decision": review["batch_eligibility_decision"],
        "coppock_intake_consistency_evidence_reviewed": review["consistency_evidence_exists"],
        "candidate_specific_evidence_valid": review["candidate_specific_evidence_valid"],
        "coppock_yaml_valid": review["coppock_yaml_valid"],
        "verification_decision": review["verification_decision"],
        "generic_bridge_blank_intake_not_used_as_eligibility_source": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "uses_only_validated_coppock_candidate": True,
        "planned_row_count": len(rows),
        "planned_row_count_target_4_to_5": 4 <= len(rows) <= 5,
        "planned_row_count_lte_5": len(rows) <= 5,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "source_backed_parameters": True,
        "parameter_status": SOURCE_BACKED_PARAMS["parameter_status"],
        "roc_periods": [SOURCE_BACKED_PARAMS["roc_period_1"], SOURCE_BACKED_PARAMS["roc_period_2"]],
        "wma_smoothing_period": SOURCE_BACKED_PARAMS["wma_smoothing_period"],
        "signal_threshold": SOURCE_BACKED_PARAMS["signal_threshold"],
        "signal_frequency": SOURCE_BACKED_PARAMS["signal_frequency"],
        "parameters_tuned": SOURCE_BACKED_PARAMS["tuned_parameters"],
        "daily_coppock_variants_added": False,
        "weekly_coppock_variants_added": False,
        "alternate_roc_periods_added": False,
        "alternate_smoothing_periods_added": False,
        "signal_lines_added": False,
        "moving_average_filters_added": False,
        "volatility_filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "divergence_rules_added": False,
        "additional_exits_added": False,
        "parameter_sweep_created": False,
        "optimization_run": False,
        "source_caveat_report_created": True,
        "sell_exit_caveat_preserved": bool(review["source_uncertainty"]),
        "similarity_contexts_preserved": list(review["similarity_contexts"]),
        "similarity_contexts_expected": list(SIMILARITY_CONTEXTS),
        "similarity_context_count": len(review["similarity_contexts"]),
        "similarity_not_current_duplicate_blocker": not review["duplicate_do_not_retest_decision"],
        "sparse_signal_risk_recorded": True,
        "future_run_must_report_event_count": True,
        "future_run_must_report_trade_count": True,
        "future_run_must_report_holding_duration": True,
        "future_run_must_report_subperiod_coverage": True,
        "future_run_must_report_sample_adequacy": True,
        "uses_only_spy_and_bil": True,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
        "formula_monthly_signal_definition_documented": True,
        "signal_timing_convention_documented": True,
        "no_lookahead_timing_documented": True,
        "bounded_bt_design_packet_created": True,
        "executable_bounded_bt_design_created": readiness == RUN_READY,
        "bounded_run_implementation_created": False,
        "bounded_bt_lane_run": False,
        "strategy_backtest_run": False,
        "strategy_implemented": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "additional_public_sources_ingested": False,
        "larry_connors_continued": False,
        "percent_b_continued": False,
        "turn_of_month_continued": False,
        "faber_taa_retested": False,
        "new_instruments_added": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
        "current_backtester_replaced": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "public_source_presence_is_profitability_proof": False,
        "outputs_non_promotable": True,
        "run_readiness_decision": readiness,
        "run_readiness_blocker": blocker,
        "next_action": next_action,
    }


def run_readiness_md(manifest: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Coppock Curve Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Coppock Curve Bounded bt Design

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake reviewed: `{manifest['source_intake_reviewed']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Coppock consistency evidence reviewed: `{manifest['coppock_intake_consistency_evidence_reviewed']}`

Candidate-specific evidence valid: `{manifest['candidate_specific_evidence_valid']}`

Source-backed parameters: `{manifest['source_backed_parameters']}`

ROC periods: `{manifest['roc_periods']}`

WMA smoothing period: `{manifest['wma_smoothing_period']}`

Signal threshold: `{manifest['signal_threshold']}`

Signal frequency: `{manifest['signal_frequency']}`

Parameters tuned: `{manifest['parameters_tuned']}`

Similarity context count: `{manifest['similarity_context_count']}`

Similarity is current duplicate blocker: `{not manifest['similarity_not_current_duplicate_blocker']}`

Sparse-signal risk recorded: `{manifest['sparse_signal_risk_recorded']}`

Planned rows: `{manifest['planned_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

bt adapter ready for design: `{manifest['bt_adapter_ready_for_design']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No Coppock backtest, bounded run implementation, source scraping, strategy discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live path, provider download, intraday data, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_coppock_curve_bounded_bt_design_consistency_check.json"] = True
    checks = {
        "design_only": manifest["public_source_coppock_curve_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "single_intake_reviewed": manifest["single_source_intake_evidence_reviewed"] is True,
        "batch_intake_reviewed": manifest["batch_intake_evidence_reviewed"] is True,
        "coppock_consistency_reviewed": manifest["coppock_intake_consistency_evidence_reviewed"] is True,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "batch_intake_eligible": manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "candidate_specific_evidence_valid": manifest["candidate_specific_evidence_valid"] is True,
        "verification_ready": manifest["verification_decision"] == "coppock_intake_evidence_consistent_ready_for_design",
        "uses_only_validated_candidate": manifest["uses_only_validated_coppock_candidate"] is True,
        "source_backed_not_tuned": manifest["source_backed_parameters"] is True
        and manifest["parameter_status"] == "source_backed_parameters"
        and manifest["parameters_tuned"] is False,
        "source_parameters_frozen": manifest["roc_periods"] == [14, 11]
        and manifest["wma_smoothing_period"] == 10
        and manifest["signal_threshold"] == 0
        and manifest["signal_frequency"] == "completed_monthly_close_only",
        "row_count_bounded": manifest["planned_row_count_target_4_to_5"] is True
        and manifest["planned_row_count_lte_5"] is True
        and len(rows) == manifest["planned_row_count"],
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] <= 1
        and manifest["control_row_count"] == 3,
        "no_coppock_expansion_or_extra_exits": manifest["daily_coppock_variants_added"] is False
        and manifest["weekly_coppock_variants_added"] is False
        and manifest["alternate_roc_periods_added"] is False
        and manifest["alternate_smoothing_periods_added"] is False
        and manifest["signal_lines_added"] is False
        and manifest["moving_average_filters_added"] is False
        and manifest["volatility_filters_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["divergence_rules_added"] is False
        and manifest["additional_exits_added"] is False
        and manifest["parameter_sweep_created"] is False,
        "source_caveat_preserved": manifest["source_caveat_report_created"] is True
        and manifest["sell_exit_caveat_preserved"] is True,
        "similarity_context_preserved_without_blocking": manifest["similarity_contexts_preserved"]
        == manifest["similarity_contexts_expected"]
        and manifest["similarity_not_current_duplicate_blocker"] is True,
        "sparse_signal_risk_preserved": manifest["sparse_signal_risk_recorded"] is True
        and manifest["future_run_must_report_event_count"] is True
        and manifest["future_run_must_report_sample_adequacy"] is True,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_control_poc_passed"] is True
        and manifest["bt_adapter_multasset_poc_passed"] is True
        and manifest["bt_adapter_ready_for_design"] is True,
        "timing_documented": manifest["formula_monthly_signal_definition_documented"] is True
        and manifest["signal_timing_convention_documented"] is True
        and manifest["no_lookahead_timing_documented"] is True,
        "no_run_or_backtest": manifest["bounded_run_implementation_created"] is False
        and manifest["bounded_bt_lane_run"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_implemented"] is False,
        "no_scrape_or_extra_sources": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["additional_public_sources_ingested"] is False,
        "other_public_sources_not_continued": manifest["larry_connors_continued"] is False
        and manifest["percent_b_continued"] is False
        and manifest["turn_of_month_continued"] is False
        and manifest["faber_taa_retested"] is False,
        "no_provider_intraday_packages": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["new_packages_installed"] is False,
        "no_backtester_replacement_or_discovery": manifest["current_backtester_replaced"] is False
        and manifest["strategy_discovery_run"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "not_profitability_proof": manifest["public_source_presence_is_profitability_proof"] is False,
        "outputs_non_promotable": manifest["outputs_non_promotable"] is True,
        "run_readiness_valid": manifest["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "run_ready_next_action": manifest["run_readiness_decision"] != RUN_READY
        or manifest["next_action"] == NEXT_ACTION_RUN,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    review = source_intake_review(root)
    cache = cache_rows(root)
    params = parameter_rows()
    rows = planned_rows()
    bt = bt_readiness(root)
    manifest = manifest_payload(
        created=created,
        output=output,
        review=review,
        cache=cache,
        bt=bt,
        rows=rows,
    )

    write_json(output / "public_source_coppock_curve_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_coppock_curve_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "source_backed_parameter_report.csv", params, list(PARAM_FIELDS))
    write_text(output / "source_backed_parameter_report.md", source_backed_parameter_md(params))
    write_text(output / "formula_monthly_signal_definition.md", formula_definition_md(review))
    write_text(output / "source_caveat_sell_exit_rule.md", source_caveat_md(review))
    write_text(output / "similarity_risk_report.md", similarity_risk_md(review))
    write_text(output / "sparse_signal_risk_report.md", sparse_signal_md())
    write_csv(output / "planned_row_table.csv", rows, list(PLANNED_ROW_FIELDS))
    write_text(output / "planned_row_table.md", planned_rows_md(rows))
    write_text(output / "signal_timing_convention.md", signal_timing_md())
    write_text(output / "baseline_control_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "bt_adapter_readiness.md", bt_readiness_md(bt))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "public_source_coppock_curve_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_coppock_curve_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
