from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.high_return_tactical_etf_equity_index_bounded_design import (
    FAMILY_ID,
    LANE_ID,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import (
    WEIGHT_TOLERANCE,
    active_combo_returns,
    available_symbols,
    benchmark_delta,
    build_baseline_weights,
    cached_price_series,
    calmar_improvement,
    contribution_metrics,
    metrics_for_returns,
    pct_reduction,
    reference_spy200d_returns,
    safe_ratio,
)
from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_run import (
    static_all_weather_returns,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    cache_inventory,
    write_csv,
)
from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_run import (
    run_volatility_throttle_variant,
)


SOURCE_DESIGN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "high_return_tactical_etf_equity_index_bounded_design"
    / "latest"
)
SOURCE_FOLLOWUP_RUN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_run"
    / "latest"
)
SOURCE_FOLLOWUP_AUDIT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_results_audit"
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "high_return_tactical_etf_equity_index_bounded_run"
    / "latest"
)

EXPECTED_ROW_COUNT = 6
THRESHOLD_SET_ID = "original_25_35_100_50_25"
SOURCE_METRIC_TOLERANCE = 1e-9

NEXT_ACTION_AUDIT = "audit_high_return_tactical_etf_equity_index_bounded_lane_results"
NEXT_ACTION_FIX = "fix_high_return_tactical_etf_equity_index_bounded_lane_methodology_issue"
NEXT_ACTION_MANUAL = "manual_review_required_after_high_return_tactical_bounded_run"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

ALLOWED_LABELS = {
    "high_return_tactical_signal_confirmed",
    "high_return_tactical_signal_high_risk",
    "high_return_tactical_signal_return_destroyed",
    "high_return_tactical_signal_duplicate_reference",
    "high_return_tactical_signal_too_defensive",
    "high_return_tactical_signal_data_blocked",
    "high_return_tactical_signal_source_mapping_blocked",
    "high_return_tactical_signal_weak",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_variant_id",
    "source_evidence_path",
    "source_mapping_status",
    "concept",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "effective_start_date",
    "effective_end_date",
    "cagr",
    "total_return",
    "max_drawdown",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "baseline_variant_id",
    "baseline_cagr",
    "baseline_total_return",
    "baseline_max_drawdown",
    "baseline_calmar_or_return_drawdown_proxy",
    "cagr_retention_vs_uncontrolled_baseline",
    "cagr_retention_vs_source_original_vol_throttle",
    "drawdown_reduction_vs_uncontrolled_baseline",
    "calmar_improvement_vs_uncontrolled_baseline",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "average_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "average_weight_sum",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "duplicate_reference_correlation",
    "correlation_to_spy200d",
    "correlation_to_static_all_weather",
    "correlation_to_active_combo",
    "spy_total_return_delta",
    "bil_cash_total_return_delta",
    "static_all_weather_total_return_delta",
    "active_vm_dsr_combo_total_return_delta",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "comparator_references",
    "trade_count",
    "turnover_proxy",
    "data_availability_status",
    "missing_symbols",
    "source_metric_mismatch_fields",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "research_only_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "source_variant_id",
    "cagr_retention_vs_uncontrolled_baseline",
    "cagr_retention_vs_uncontrolled_baseline_pass",
    "cagr_retention_vs_source_original_vol_throttle",
    "source_original_retention_pass",
    "drawdown_reduction_vs_uncontrolled_baseline",
    "drawdown_reduction_pass",
    "calmar_improvement_vs_uncontrolled_baseline",
    "calmar_improvement_pass",
    "average_bil_cash_share",
    "bil_cash_usage_pass",
    "duplicate_reference_correlation",
    "duplicate_reference_correlation_pass",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "research_only_label",
)

REQUIRED_OUTPUT_FILES = (
    "high_return_tactical_bounded_run_manifest.json",
    "high_return_tactical_bounded_run_consistency_check.json",
    "high_return_tactical_bounded_run_results.csv",
    "high_return_tactical_bounded_numeric_criteria_results.csv",
    "source_mapping_verification_report.md",
    "data_alignment_effective_window_report.md",
    "baseline_comparator_report.md",
    "exposure_invariant_report.md",
    "high_return_tactical_bounded_label_summary.md",
    "high_return_tactical_bounded_run_summary.md",
    "high_return_tactical_bounded_run_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(value: float) -> bool:
    return not math.isnan(float(value)) and not math.isinf(float(value))


def bool_pass(value: bool) -> bool:
    return bool(value) is True


def format_float(value: Any) -> str:
    parsed = parse_float(value)
    return "nan" if not finite(parsed) else f"{parsed:.6f}"


def load_sources(root: Path) -> dict[str, Any]:
    return {
        "design_manifest": read_json(root / SOURCE_DESIGN_DIR / "high_return_tactical_bounded_design_manifest.json"),
        "design_consistency": read_json(root / SOURCE_DESIGN_DIR / "high_return_tactical_bounded_design_consistency_check.json"),
        "design_rows": read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv"),
        "source_rows": {
            row["variant_id"]: row
            for row in read_csv_rows(root / SOURCE_FOLLOWUP_RUN_DIR / "vol_throttle_followup_results.csv")
        },
        "source_run_manifest": read_json(root / SOURCE_FOLLOWUP_RUN_DIR / "vol_throttle_followup_run_manifest.json"),
        "source_audit_manifest": read_json(root / SOURCE_FOLLOWUP_AUDIT_DIR / "vol_throttle_followup_results_audit_manifest.json"),
    }


def design_to_run_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "lane_id": LANE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "threshold_set_id": THRESHOLD_SET_ID,
        "source_variant_id": row["source_variant_id"],
        "baseline_variant_id": row["baseline_variant_id"],
        "baseline_comparator_variant_id": row["baseline_variant_id"],
        "source_evidence_path": row["source_evidence_path"],
        "universe_group": row["universe_group"],
        "universe": row["universe"],
        "lookback": row["lookback_days"],
        "top_n": row["top_n"],
        "volatility_window": row["volatility_window"],
        "normal_vol_threshold": row["normal_vol_threshold"],
        "high_vol_threshold": row["high_vol_threshold"],
        "normal_multiplier": row["normal_multiplier"],
        "high_vol_multiplier": row["high_vol_multiplier"],
        "extreme_vol_multiplier": row["extreme_vol_multiplier"],
        "concept": row["concept"],
        "comparator_references": row["comparator_references"],
    }


def design_to_baseline_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "universe": row["universe"],
        "baseline_variant_id": row["baseline_variant_id"],
        "momentum_lookback_days": row["lookback_days"],
        "top_n": row["top_n"],
        "universe_group": row["universe_group"],
    }


def metric_mismatches(design_row: dict[str, str], source_row: dict[str, str]) -> list[str]:
    comparisons = {
        "source_cagr": ("source_cagr", "cagr"),
        "source_max_drawdown": ("source_max_drawdown", "max_drawdown"),
        "source_drawdown_reduction_vs_baseline": (
            "source_drawdown_reduction_vs_baseline",
            "drawdown_reduction_vs_comparator",
        ),
        "source_cagr_retention_vs_baseline": (
            "source_cagr_retention_vs_baseline",
            "cagr_retention_vs_comparator",
        ),
        "source_average_bil_cash_share": ("source_average_bil_cash_share", "average_bil_cash_share"),
        "source_duplicate_reference_correlation": (
            "source_duplicate_reference_correlation",
            "duplicate_reference_correlation",
        ),
    }
    mismatches: list[str] = []
    for label, (design_field, source_field) in comparisons.items():
        left = parse_float(design_row.get(design_field))
        right = parse_float(source_row.get(source_field))
        if not finite(left) or not finite(right) or abs(left - right) > SOURCE_METRIC_TOLERANCE:
            mismatches.append(label)
    return mismatches


def run_metric_mismatches(row: dict[str, Any], source_row: dict[str, str]) -> list[str]:
    comparisons = {
        "run_cagr": ("cagr", "cagr"),
        "run_max_drawdown": ("max_drawdown", "max_drawdown"),
        "run_drawdown_reduction": ("drawdown_reduction_vs_uncontrolled_baseline", "drawdown_reduction_vs_comparator"),
        "run_cagr_retention": ("cagr_retention_vs_uncontrolled_baseline", "cagr_retention_vs_comparator"),
        "run_average_bil_cash_share": ("average_bil_cash_share", "average_bil_cash_share"),
        "run_duplicate_reference_correlation": ("duplicate_reference_correlation", "duplicate_reference_correlation"),
    }
    mismatches: list[str] = []
    for label, (row_field, source_field) in comparisons.items():
        left = parse_float(row.get(row_field))
        right = parse_float(source_row.get(source_field))
        if not finite(left) or not finite(right) or abs(left - right) > SOURCE_METRIC_TOLERANCE:
            mismatches.append(label)
    return mismatches


def verify_source_mapping(root: Path, row: dict[str, str], source_rows: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    source_path = Path(row.get("source_evidence_path", ""))
    if not source_path.exists():
        source_path = root / SOURCE_FOLLOWUP_RUN_DIR / "vol_throttle_followup_results.csv"
    source = source_rows.get(row.get("source_variant_id", ""))
    if source is None:
        return "source_mapping_missing_source_row", ["source_variant_id"]
    mismatches = metric_mismatches(row, source)
    if not source_path.exists():
        mismatches.append("source_evidence_path")
    if source.get("variant_role") != "confirmation_reference":
        mismatches.append("source_variant_role")
    if source.get("threshold_set_id") != THRESHOLD_SET_ID:
        mismatches.append("source_threshold_set_id")
    if source.get("universe_group") != row.get("universe_group"):
        mismatches.append("universe_group")
    if source.get("universe") != row.get("universe"):
        mismatches.append("universe")
    if str(source.get("lookback")) != str(row.get("lookback_days")):
        mismatches.append("lookback")
    if str(source.get("top_n")) != str(row.get("top_n")):
        mismatches.append("top_n")
    if source.get("baseline_comparator_variant_id") != row.get("baseline_variant_id"):
        mismatches.append("baseline_variant_id")
    if mismatches:
        return "source_mapping_metric_or_design_mismatch", mismatches
    return "source_mapping_verified_pre_run", []


def corr_to_reference(strategy: pd.Series, reference: pd.Series) -> float:
    aligned = pd.concat([strategy.rename("strategy"), reference.rename("reference")], axis=1).dropna()
    if len(aligned) < 252:
        return float("nan")
    return float(aligned["strategy"].corr(aligned["reference"]))


def baseline_metrics(source_row: dict[str, str]) -> dict[str, float]:
    return {
        "baseline_total_return": parse_float(source_row.get("baseline_total_return")),
        "baseline_cagr": parse_float(source_row.get("baseline_cagr")),
        "baseline_max_drawdown": parse_float(source_row.get("baseline_max_drawdown")),
        "baseline_calmar_or_return_drawdown_proxy": parse_float(
            source_row.get("baseline_calmar_or_return_drawdown_proxy")
        ),
    }


def data_blocked_row(
    row: dict[str, str],
    *,
    status: str,
    missing_symbols: list[str] | None = None,
    mismatches: list[str] | None = None,
    notes: str,
) -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row.get("variant_id", ""),
        "variant_role": row.get("variant_role", ""),
        "source_variant_id": row.get("source_variant_id", ""),
        "source_evidence_path": row.get("source_evidence_path", ""),
        "source_mapping_status": status,
        "concept": row.get("concept", ""),
        "universe_group": row.get("universe_group", ""),
        "universe": row.get("universe", ""),
        "lookback": row.get("lookback_days", ""),
        "top_n": row.get("top_n", ""),
        "baseline_variant_id": row.get("baseline_variant_id", ""),
        "comparator_references": row.get("comparator_references", ""),
        "data_availability_status": "data_blocked" if missing_symbols else "source_mapping_blocked",
        "missing_symbols": "|".join(missing_symbols or []),
        "source_metric_mismatch_fields": "|".join(mismatches or []),
        "exposure_invariant_pass": False,
        "numeric_criteria_pass": False,
        "research_only_label": "high_return_tactical_signal_data_blocked"
        if missing_symbols
        else "high_return_tactical_signal_source_mapping_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": notes,
    }


def exposure_pass(metrics: dict[str, Any]) -> bool:
    return (
        parse_float(metrics.get("max_daily_exposure"), 0.0) <= 1.000001
        and parse_float(metrics.get("max_daily_weight_sum"), 0.0) <= 1.000001
        and int(parse_float(metrics.get("weight_sum_violation_count"), 0.0)) == 0
        and int(parse_float(metrics.get("negative_weight_violation_count"), 0.0)) == 0
        and int(parse_float(metrics.get("nan_weight_count"), 0.0)) == 0
        and int(parse_float(metrics.get("impossible_cash_and_risky_exposure_days"), 0.0)) == 0
    )


def label_row(row: dict[str, Any]) -> str:
    if row.get("data_availability_status") == "data_blocked":
        return "high_return_tactical_signal_data_blocked"
    if row.get("source_mapping_status") != "source_mapping_verified":
        return "high_return_tactical_signal_source_mapping_blocked"
    if not row.get("exposure_invariant_pass"):
        return "high_return_tactical_signal_weak"
    if not row.get("duplicate_reference_correlation_pass"):
        return "high_return_tactical_signal_duplicate_reference"
    if not row.get("bil_cash_usage_pass"):
        return "high_return_tactical_signal_too_defensive"
    if parse_float(row.get("cagr_retention_vs_uncontrolled_baseline")) < 0.40 or parse_float(row.get("cagr")) < 0.05:
        return "high_return_tactical_signal_return_destroyed"
    if row.get("numeric_criteria_pass"):
        return "high_return_tactical_signal_confirmed"
    if parse_float(row.get("max_drawdown")) <= -0.35 or not row.get("drawdown_reduction_pass"):
        return "high_return_tactical_signal_high_risk"
    return "high_return_tactical_signal_weak"


def evaluate_design_row(
    root: Path,
    row: dict[str, str],
    source_rows: dict[str, dict[str, str]],
    local_symbols: set[str],
    active_returns: pd.Series,
) -> dict[str, Any]:
    universe = [symbol for symbol in row["universe"].split("|") if symbol]
    missing = [symbol for symbol in universe if symbol not in local_symbols]
    if missing:
        return data_blocked_row(
            row,
            status="cache_symbols_missing",
            missing_symbols=missing,
            notes="required local cached symbols missing; no provider download attempted",
        )
    pre_status, pre_mismatches = verify_source_mapping(root, row, source_rows)
    if pre_mismatches:
        return data_blocked_row(
            row,
            status=pre_status,
            mismatches=pre_mismatches,
            notes="approved row stopped before execution because source mapping did not verify",
        )
    source = source_rows[row["source_variant_id"]]
    run_row = design_to_run_row(row)
    baseline_daily, baseline_weights = build_baseline_weights(root, design_to_baseline_row(row))
    daily, weights = run_volatility_throttle_variant(root, run_row, baseline_daily, baseline_weights)
    if daily.empty or weights.empty or len(daily.dropna()) < 252:
        return data_blocked_row(
            row,
            status="insufficient_local_history",
            notes="insufficient local history after cache load; no provider download attempted",
        )

    metrics = metrics_for_returns(daily, weights)
    base_metrics = baseline_metrics(source)
    drawdown_reduction = pct_reduction(base_metrics["baseline_max_drawdown"], metrics["max_drawdown"])
    cagr_retention = safe_ratio(metrics["cagr"], base_metrics["baseline_cagr"])
    calmar_delta = calmar_improvement(
        base_metrics["baseline_calmar_or_return_drawdown_proxy"],
        metrics["calmar_or_return_drawdown_proxy"],
    )
    source_retention = safe_ratio(metrics["cagr"], parse_float(source.get("cagr")))

    spy_returns = cached_price_series(str(root), "SPY").pct_change(fill_method=None).dropna().rename("SPY")
    bil_returns = cached_price_series(str(root), "BIL").pct_change(fill_method=None).dropna().rename("BIL")
    spy_delta = benchmark_delta(daily, spy_returns)
    bil_delta = benchmark_delta(daily, bil_returns)
    spy200d_returns = reference_spy200d_returns(root, daily.index)
    spy200d_corr = corr_to_reference(daily, spy200d_returns)
    active = contribution_metrics(daily, active_returns)
    static_returns = static_all_weather_returns(root, daily.index)
    static_delta = benchmark_delta(daily, static_returns) if not static_returns.empty else float("nan")
    static_corr = corr_to_reference(daily, static_returns) if not static_returns.empty else float("nan")
    duplicate_corr = spy200d_corr
    exp_pass = exposure_pass(metrics)

    result: dict[str, Any] = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "source_variant_id": row["source_variant_id"],
        "source_evidence_path": row["source_evidence_path"],
        "source_mapping_status": "source_mapping_verified",
        "concept": row["concept"],
        "universe_group": row["universe_group"],
        "universe": row["universe"],
        "lookback": int(float(row["lookback_days"])),
        "top_n": int(float(row["top_n"])),
        "effective_start_date": metrics["start_date"],
        "effective_end_date": metrics["end_date"],
        **{key: value for key, value in metrics.items() if key not in {"start_date", "end_date"}},
        **base_metrics,
        "baseline_variant_id": row["baseline_variant_id"],
        "cagr_retention_vs_uncontrolled_baseline": cagr_retention,
        "cagr_retention_vs_source_original_vol_throttle": source_retention,
        "drawdown_reduction_vs_uncontrolled_baseline": drawdown_reduction,
        "calmar_improvement_vs_uncontrolled_baseline": calmar_delta,
        "duplicate_reference_correlation": duplicate_corr,
        "correlation_to_spy200d": spy200d_corr,
        "correlation_to_static_all_weather": static_corr,
        "correlation_to_active_combo": active["active_combo_correlation"],
        "spy_total_return_delta": spy_delta,
        "bil_cash_total_return_delta": bil_delta,
        "static_all_weather_total_return_delta": static_delta,
        "active_vm_dsr_combo_total_return_delta": active["active_combo_blend_total_return_delta"],
        "active_vm_dsr_combo_max_drawdown_improvement": active["active_combo_blend_drawdown_delta"],
        "comparator_references": row["comparator_references"],
        "data_availability_status": "cache_ready",
        "missing_symbols": "",
        "source_metric_mismatch_fields": "",
        "cagr_retention_vs_uncontrolled_baseline_pass": bool_pass(finite(cagr_retention) and cagr_retention >= 0.70),
        "source_original_retention_pass": bool_pass(finite(source_retention) and source_retention >= 0.85),
        "drawdown_reduction_pass": bool_pass(finite(drawdown_reduction) and drawdown_reduction >= 0.25),
        "calmar_improvement_pass": bool_pass(finite(calmar_delta) and calmar_delta > 0.0),
        "bil_cash_usage_pass": bool_pass(parse_float(metrics.get("average_bil_cash_share")) <= 0.35),
        "duplicate_reference_correlation_pass": bool_pass(finite(duplicate_corr) and duplicate_corr < 0.90),
        "exposure_invariant_pass": bool_pass(exp_pass),
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "approved six-row bounded high-return tactical original-volatility-throttle lane; local cache only; diagnostic non-promotable evidence",
    }
    run_mismatches = run_metric_mismatches(result, source)
    if run_mismatches:
        result["source_mapping_status"] = "source_run_metric_mismatch"
        result["source_metric_mismatch_fields"] = "|".join(run_mismatches)
    result["numeric_criteria_pass"] = bool_pass(
        result["source_mapping_status"] == "source_mapping_verified"
        and result["cagr_retention_vs_uncontrolled_baseline_pass"]
        and result["source_original_retention_pass"]
        and result["drawdown_reduction_pass"]
        and result["calmar_improvement_pass"]
        and result["bil_cash_usage_pass"]
        and result["duplicate_reference_correlation_pass"]
        and result["exposure_invariant_pass"]
    )
    result["research_only_label"] = label_row(result)
    return result


def evaluate_lane(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = load_sources(root)
    design_rows = source["design_rows"]
    local_symbols = available_symbols(root)
    active_returns = active_combo_returns(root)
    rows = [evaluate_design_row(root, row, source["source_rows"], local_symbols, active_returns) for row in design_rows]
    preflight = {
        "design_run_ready": source["design_manifest"].get("run_readiness_decision")
        == "high_return_tactical_bounded_design_run_ready",
        "design_next_action_correct": source["design_manifest"].get("next_action")
        == "run_high_return_tactical_etf_equity_index_bounded_lane",
        "design_consistency_passed": source["design_consistency"].get("consistency_passed") is True,
        "source_followup_audit_passed": source["source_audit_manifest"].get("final_audit_decision")
        == "followup_results_audit_passed",
        "source_followup_discrepancy_count": source["source_audit_manifest"].get("row_level_discrepancy_count"),
        "planned_row_count": len(design_rows),
        "planned_row_count_exact_6": len(design_rows) == EXPECTED_ROW_COUNT,
        "approved_variant_ids": [row.get("variant_id", "") for row in design_rows],
        "available_symbols_used": sorted({symbol for row in design_rows for symbol in row["universe"].split("|") if symbol in local_symbols}),
        "provider_download_required": False,
        "intraday_data_required": False,
        "cache_inventory_rows": len(cache_inventory(root)),
    }
    return rows, preflight


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for row in rows if row.get("research_only_label") == label) for label in ALLOWED_LABELS}


def numeric_pass_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("numeric_criteria_pass") is True)


def data_blocked_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("data_availability_status") == "data_blocked")


def source_mapping_failure_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("source_mapping_status") != "source_mapping_verified")


def invariant_failure_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]


def max_numeric(rows: list[dict[str, Any]], field: str) -> float:
    values = [parse_float(row.get(field), 0.0) for row in rows]
    return max(values) if values else 0.0


def summary_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    out: list[dict[str, Any]] = []
    for value, subset in df.groupby(field):
        out.append(
            {
                field: value,
                "row_count": len(subset),
                "numeric_pass_count": int(subset["numeric_criteria_pass"].astype(bool).sum()),
                "numeric_fail_count": int(len(subset) - subset["numeric_criteria_pass"].astype(bool).sum()),
                "confirmed_count": int((subset["research_only_label"] == "high_return_tactical_signal_confirmed").sum()),
                "median_cagr": float(pd.to_numeric(subset["cagr"], errors="coerce").median()),
                "median_max_drawdown": float(pd.to_numeric(subset["max_drawdown"], errors="coerce").median()),
                "median_drawdown_reduction": float(
                    pd.to_numeric(subset["drawdown_reduction_vs_uncontrolled_baseline"], errors="coerce").median()
                ),
                "median_cagr_retention": float(
                    pd.to_numeric(subset["cagr_retention_vs_uncontrolled_baseline"], errors="coerce").median()
                ),
            }
        )
    return out


def build_manifest(created: str, output: Path, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    exposure_invariant_passed = not invariant_failure_rows(rows)
    max_exposure = max_numeric(rows, "max_daily_exposure")
    max_weight_sum = max_numeric(rows, "max_daily_weight_sum")
    source_failures = source_mapping_failure_count(rows)
    data_blocked = data_blocked_count(rows)
    interpretable = (
        len(rows) == EXPECTED_ROW_COUNT
        and data_blocked == 0
        and source_failures == 0
        and exposure_invariant_passed
        and max_exposure <= 1.000001
        and max_weight_sum <= 1.000001
        and preflight["design_run_ready"]
        and preflight["design_consistency_passed"]
        and preflight["source_followup_audit_passed"]
    )
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    counts = label_counts(rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "high_return_tactical_bounded_run": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_design_run_ready": preflight["design_run_ready"],
        "source_followup_audit_passed": preflight["source_followup_audit_passed"],
        "variant_count_planned": EXPECTED_ROW_COUNT,
        "variant_count_evaluated": len(rows),
        "data_blocked_variant_count": data_blocked,
        "source_mapping_failure_count": source_failures,
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_families_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "threshold_tuning_added": False,
        "strategy_drawdown_guard_used": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_used": False,
        "shorting_used": False,
        "options_used": False,
        "direct_futures_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "candidate_exhaustive_run": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "outputs_promotable": False,
        "outputs_paper_forward_eligible": False,
        "outputs_candidate_exhaustive_ready": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_threshold_tuning_continued": False,
        "managed_futures_reopened": False,
        "pre_fix_stale_weight_results_used": False,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": exposure_invariant_passed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "cash_bil_replacement_remainder_only": all(
            int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) == 0 for row in rows
        ),
        "numeric_criteria_pass_count": numeric_pass_count(rows),
        "numeric_criteria_fail_count": len(rows) - numeric_pass_count(rows),
        "rows_passing_by_concept": {
            row["concept"]: sum(
                1 for item in rows if item.get("concept") == row["concept"] and item.get("numeric_criteria_pass") is True
            )
            for row in rows
        },
        "rows_passing_by_lookback": {
            str(row["lookback"]): sum(
                1
                for item in rows
                if str(item.get("lookback")) == str(row["lookback"]) and item.get("numeric_criteria_pass") is True
            )
            for row in rows
        },
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence_produced": interpretable,
        **{f"{label}_count": count for label, count in counts.items()},
        "next_action": next_action,
    }


def summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    label_lines = [
        f"- `{label}`: `{manifest[f'{label}_count']}`"
        for label in sorted(ALLOWED_LABELS)
    ]
    rows_lines = [
        f"- `{row['variant_id']}`: CAGR `{format_float(row.get('cagr'))}`, max DD `{format_float(row.get('max_drawdown'))}`, "
        f"DD reduction `{format_float(row.get('drawdown_reduction_vs_uncontrolled_baseline'))}`, "
        f"CAGR retention `{format_float(row.get('cagr_retention_vs_uncontrolled_baseline'))}`, "
        f"label `{row.get('research_only_label')}`"
        for row in rows
    ]
    return f"""# High-Return Tactical ETF Equity-Index Bounded Run

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Rows planned/evaluated: `{manifest['variant_count_planned']}` / `{manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_variant_count']}`

Source mapping failures: `{manifest['source_mapping_failure_count']}`

Numeric criteria pass/fail: `{manifest['numeric_criteria_pass_count']}` / `{manifest['numeric_criteria_fail_count']}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Cash/BIL replacement/remainder only: `{manifest['cash_bil_replacement_remainder_only']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence produced: `{manifest['usable_diagnostic_evidence_produced']}`

Label counts:

{chr(10).join(label_lines)}

Rows:

{chr(10).join(rows_lines)}

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def source_mapping_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = ["# Source Mapping Verification Report", ""]
    lines.append(f"Source mapping failures: `{manifest['source_mapping_failure_count']}`")
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}` maps to `{row.get('source_variant_id')}`: "
            f"`{row.get('source_mapping_status')}`; mismatches "
            f"`{row.get('source_metric_mismatch_fields') or 'none'}`"
        )
    lines.append("")
    lines.append("Every verified row used the post-fix volatility-throttle follow-up result table as source evidence.")
    return "\n".join(lines) + "\n"


def data_alignment_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Data Alignment / Effective Date Window Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: effective window `{row.get('effective_start_date', 'unknown')}` "
            f"to `{row.get('effective_end_date', 'unknown')}`, universe `{row.get('universe')}`, "
            f"data status `{row.get('data_availability_status')}`"
        )
    lines.append("")
    lines.append("Local cached daily data was used only. No provider download or intraday data was used.")
    return "\n".join(lines) + "\n"


def baseline_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Comparator Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}` baseline `{row.get('baseline_variant_id')}`: "
            f"CAGR retention `{format_float(row.get('cagr_retention_vs_uncontrolled_baseline'))}`, "
            f"DD reduction `{format_float(row.get('drawdown_reduction_vs_uncontrolled_baseline'))}`, "
            f"SPY delta `{format_float(row.get('spy_total_return_delta'))}`, "
            f"BIL delta `{format_float(row.get('bil_cash_total_return_delta'))}`, "
            f"static all-weather delta `{format_float(row.get('static_all_weather_total_return_delta'))}`, "
            f"active combo drawdown delta `{format_float(row.get('active_vm_dsr_combo_max_drawdown_improvement'))}`"
        )
    lines.append("")
    lines.append("Static all-weather is benchmark/control only, not candidate evidence.")
    return "\n".join(lines) + "\n"


def invariant_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = invariant_failure_rows(rows)
    return f"""# Exposure Invariant Report

- Max daily exposure: `{manifest['max_daily_exposure']}`
- Max daily weight sum: `{manifest['max_daily_weight_sum']}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Cash/BIL replacement/remainder only: `{manifest['cash_bil_replacement_remainder_only']}`
- Invariant failure rows: `{', '.join(failures) if failures else 'none'}`

Hard constraints checked:

- Max daily exposure `<= 1.0`
- Max daily weight sum `<= 1.0`
- BIL/cash replacement/remainder only
- No BIL/cash accumulation on top of risky exposure
- No negative weights, NaN weights, leverage, shorting, options, or direct futures
"""


def label_summary_md(manifest: dict[str, Any]) -> str:
    return "# Label Summary\n\n" + "\n".join(
        f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)
    ) + "\n"


def next_action_md(next_action: str) -> str:
    return f"""# High-Return Tactical Bounded Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["high_return_tactical_bounded_run_consistency_check.json"] = True
    labels = {row.get("research_only_label", "") for row in rows}
    variant_ids = [row.get("variant_id") for row in rows]
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "row_count_exact_6": manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT,
        "variant_ids_unique": len(set(variant_ids)) == len(variant_ids),
        "no_new_research_batch": manifest["new_research_batch_run"] is False,
        "no_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_family_or_variant_expansion": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_threshold_tuning": manifest["threshold_tuning_added"] is False,
        "drawdown_guard_not_used": manifest["strategy_drawdown_guard_used"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_leverage_short_options_futures": manifest["leverage_used"] is False
        and manifest["shorting_used"] is False
        and manifest["options_used"] is False
        and manifest["direct_futures_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["best_single_variant_promoted"] is False,
        "outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True
        and manifest["outputs_promotable"] is False
        and manifest["outputs_paper_forward_eligible"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "unrelated_work_not_continued": manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_threshold_tuning_continued"] is False
        and manifest["managed_futures_reopened"] is False,
        "post_fix_source_only": manifest["pre_fix_stale_weight_results_used"] is False,
        "source_mapping_verified": manifest["source_mapping_failure_count"] == 0,
        "data_not_blocked": manifest["data_blocked_variant_count"] == 0,
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "cash_bil_invariant_passed": manifest["cash_bil_replacement_remainder_only"] is True,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "promotion_false_rows": all(row.get("promotion_eligibility") is False for row in rows),
        "paper_false_rows": all(row.get("paper_forward_eligibility") is False for row in rows),
        "candidate_exhaustive_false_rows": all(row.get("candidate_exhaustive_eligibility") is False for row in rows),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(created, output, rows, preflight)
    write_json(output / "high_return_tactical_bounded_run_manifest.json", manifest)
    write_csv(output / "high_return_tactical_bounded_run_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "high_return_tactical_bounded_numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "source_mapping_verification_report.md", source_mapping_md(manifest, rows))
    write_text(output / "data_alignment_effective_window_report.md", data_alignment_md(rows))
    write_text(output / "baseline_comparator_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest, rows))
    write_text(output / "high_return_tactical_bounded_label_summary.md", label_summary_md(manifest))
    write_text(output / "high_return_tactical_bounded_run_summary.md", summary_md(manifest, rows))
    write_text(output / "high_return_tactical_bounded_run_next_action.md", next_action_md(manifest["next_action"]))
    consistency = consistency_check(manifest, output, rows)
    write_json(output / "high_return_tactical_bounded_run_consistency_check.json", consistency)
    write_csv(
        output / "high_return_tactical_bounded_summary_by_concept.csv",
        summary_by(rows, "concept"),
        ["concept", "row_count", "numeric_pass_count", "numeric_fail_count", "confirmed_count", "median_cagr", "median_max_drawdown", "median_drawdown_reduction", "median_cagr_retention"],
    )
    write_csv(
        output / "high_return_tactical_bounded_summary_by_lookback.csv",
        summary_by(rows, "lookback"),
        ["lookback", "row_count", "numeric_pass_count", "numeric_fail_count", "confirmed_count", "median_cagr", "median_max_drawdown", "median_drawdown_reduction", "median_cagr_retention"],
    )
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, preflight = evaluate_lane(root)
    return write_outputs(root, created, rows, preflight)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "numeric_criteria_pass_count": result["numeric_criteria_pass_count"],
                "data_blocked_variant_count": result["data_blocked_variant_count"],
                "source_mapping_failure_count": result["source_mapping_failure_count"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
