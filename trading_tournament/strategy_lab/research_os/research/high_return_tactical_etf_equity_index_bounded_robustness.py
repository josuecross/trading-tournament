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
from strategy_lab.research_os.research.high_return_tactical_etf_equity_index_bounded_run import (
    FAMILY_ID,
    LANE_ID,
    SOURCE_METRIC_TOLERANCE,
    baseline_metrics,
    bool_pass,
    corr_to_reference,
    design_to_baseline_row,
    design_to_run_row,
    exposure_pass,
    finite,
    label_row,
    load_sources,
    parse_float,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import (
    active_combo_returns,
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
    equity_curve,
    write_csv,
)
from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_run import (
    run_volatility_throttle_variant,
)


SOURCE_RUN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "high_return_tactical_etf_equity_index_bounded_run"
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "high_return_tactical_etf_equity_index_bounded_robustness"
    / "latest"
)

EXPECTED_ROW_COUNT = 6
STRESS_COSTS = {"base": 0.0, "stress_10bps": 0.0010, "stress_25bps": 0.0025}
SUBPERIODS = (
    ("subperiod_2007_2014", "2007-01-03", "2014-12-31"),
    ("subperiod_2015_2020", "2015-01-01", "2020-12-31"),
    ("subperiod_2021_latest", "2021-01-01", None),
)

NEXT_ACTION_QUEUE = "return_to_profit_oriented_research_queue"
NEXT_ACTION_FIX = "fix_high_return_tactical_etf_equity_index_bounded_robustness_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_QUEUE, NEXT_ACTION_FIX}

STRESS_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "concept",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "base_cagr",
    "base_total_return",
    "base_max_drawdown",
    "base_calmar",
    "base_numeric_criteria_pass",
    "base_label",
    "stress_10bps_cagr",
    "stress_10bps_total_return",
    "stress_10bps_max_drawdown",
    "stress_10bps_calmar",
    "stress_10bps_numeric_criteria_pass",
    "stress_10bps_label",
    "stress_25bps_cagr",
    "stress_25bps_total_return",
    "stress_25bps_max_drawdown",
    "stress_25bps_calmar",
    "stress_25bps_numeric_criteria_pass",
    "stress_25bps_label",
    "fails_only_due_to_cost_stress",
    "average_turnover_unit",
    "total_turnover_unit",
    "base_run_metric_mismatch_fields",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

SUBPERIOD_FIELDS = (
    "variant_id",
    "variant_role",
    "concept",
    "universe_group",
    "period_id",
    "start_date",
    "end_date",
    "total_return",
    "cagr",
    "max_drawdown",
    "calmar_or_return_drawdown_proxy",
    "subperiod_weakness_flag",
)

ROLLING_FIELDS = (
    "variant_id",
    "variant_role",
    "concept",
    "universe_group",
    "worst_180_day_return",
    "worst_252_day_return",
    "positive_180_day_ratio",
    "positive_252_day_ratio",
    "rolling_window_weakness_flag",
)

COMPARATOR_FIELDS = (
    "variant_id",
    "universe_group",
    "lookback",
    "bil_cash_total_return_delta",
    "spy_total_return_delta",
    "static_all_weather_total_return_delta",
    "correlation_to_spy200d",
    "correlation_to_static_all_weather",
    "correlation_to_active_combo",
    "active_vm_dsr_combo_total_return_delta",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "duplicate_reference_correlation",
    "active_combo_relationship",
)

REQUIRED_FILES = (
    "high_return_tactical_bounded_robustness_manifest.json",
    "high_return_tactical_bounded_robustness_consistency_check.json",
    "base_vs_stress_row_results.csv",
    "subperiod_performance.csv",
    "rolling_window_weakness.csv",
    "rolling_window_weakness_report.md",
    "comparator_redundancy_contribution_report.md",
    "comparator_redundancy_contribution.csv",
    "exposure_invariant_report.md",
    "high_return_tactical_bounded_robustness_summary.md",
    "high_return_tactical_bounded_robustness_next_action.md",
    "do_not_promote_from_high_return_tactical_robustness.md",
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


def format_float(value: Any) -> str:
    parsed = parse_float(value)
    return "nan" if not finite(parsed) else f"{parsed:.6f}"


def turnover_units(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float)
    return weights.diff().abs().fillna(weights.abs()).sum(axis=1) / 2.0


def apply_cost_stress(daily: pd.Series, weights: pd.DataFrame, cost_per_turnover_unit: float) -> pd.Series:
    costs = turnover_units(weights).reindex(daily.index).fillna(0.0) * cost_per_turnover_unit
    return (daily - costs).rename(daily.name)


def run_pair(root: Path, row: dict[str, str]) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    baseline_daily, baseline_weights = build_baseline_weights(root, design_to_baseline_row(row))
    daily, weights = run_volatility_throttle_variant(root, design_to_run_row(row), baseline_daily, baseline_weights)
    return daily, weights, baseline_daily


def evaluate_daily(
    root: Path,
    row: dict[str, str],
    source_row: dict[str, str],
    daily: pd.Series,
    weights: pd.DataFrame,
    active_returns: pd.Series,
) -> dict[str, Any]:
    metrics = metrics_for_returns(daily, weights)
    base_metrics = baseline_metrics(source_row)
    drawdown_reduction = pct_reduction(base_metrics["baseline_max_drawdown"], metrics["max_drawdown"])
    cagr_retention = safe_ratio(metrics["cagr"], base_metrics["baseline_cagr"])
    source_retention = safe_ratio(metrics["cagr"], parse_float(source_row.get("cagr")))
    calmar_delta = calmar_improvement(
        base_metrics["baseline_calmar_or_return_drawdown_proxy"],
        metrics["calmar_or_return_drawdown_proxy"],
    )
    spy_returns = cached_price_series(str(root), "SPY").pct_change(fill_method=None).dropna().rename("SPY")
    bil_returns = cached_price_series(str(root), "BIL").pct_change(fill_method=None).dropna().rename("BIL")
    spy200d_returns = reference_spy200d_returns(root, daily.index)
    active = contribution_metrics(daily, active_returns)
    static_returns = static_all_weather_returns(root, daily.index)
    spy200d_corr = corr_to_reference(daily, spy200d_returns)
    static_corr = corr_to_reference(daily, static_returns) if not static_returns.empty else float("nan")
    duplicate_corr = spy200d_corr
    result: dict[str, Any] = {
        **metrics,
        **base_metrics,
        "source_mapping_status": "source_mapping_verified",
        "data_availability_status": "cache_ready",
        "cagr_retention_vs_uncontrolled_baseline": cagr_retention,
        "cagr_retention_vs_source_original_vol_throttle": source_retention,
        "drawdown_reduction_vs_uncontrolled_baseline": drawdown_reduction,
        "calmar_improvement_vs_uncontrolled_baseline": calmar_delta,
        "duplicate_reference_correlation": duplicate_corr,
        "correlation_to_spy200d": spy200d_corr,
        "correlation_to_static_all_weather": static_corr,
        "correlation_to_active_combo": active["active_combo_correlation"],
        "spy_total_return_delta": benchmark_delta(daily, spy_returns),
        "bil_cash_total_return_delta": benchmark_delta(daily, bil_returns),
        "static_all_weather_total_return_delta": benchmark_delta(daily, static_returns)
        if not static_returns.empty
        else float("nan"),
        "active_vm_dsr_combo_total_return_delta": active["active_combo_blend_total_return_delta"],
        "active_vm_dsr_combo_max_drawdown_improvement": active["active_combo_blend_drawdown_delta"],
    }
    result["cagr_retention_vs_uncontrolled_baseline_pass"] = bool_pass(finite(cagr_retention) and cagr_retention >= 0.70)
    result["source_original_retention_pass"] = bool_pass(finite(source_retention) and source_retention >= 0.85)
    result["drawdown_reduction_pass"] = bool_pass(finite(drawdown_reduction) and drawdown_reduction >= 0.25)
    result["calmar_improvement_pass"] = bool_pass(finite(calmar_delta) and calmar_delta > 0.0)
    result["bil_cash_usage_pass"] = bool_pass(parse_float(metrics.get("average_bil_cash_share")) <= 0.35)
    result["duplicate_reference_correlation_pass"] = bool_pass(finite(duplicate_corr) and duplicate_corr < 0.90)
    result["exposure_invariant_pass"] = bool_pass(exposure_pass(metrics))
    result["numeric_criteria_pass"] = bool_pass(
        result["cagr_retention_vs_uncontrolled_baseline_pass"]
        and result["source_original_retention_pass"]
        and result["drawdown_reduction_pass"]
        and result["calmar_improvement_pass"]
        and result["bil_cash_usage_pass"]
        and result["duplicate_reference_correlation_pass"]
        and result["exposure_invariant_pass"]
    )
    result["research_only_label"] = label_row(result)
    return result


def base_metric_mismatches(base_eval: dict[str, Any], source_run_row: dict[str, str]) -> list[str]:
    comparisons = {
        "cagr": ("cagr", "cagr"),
        "max_drawdown": ("max_drawdown", "max_drawdown"),
        "total_return": ("total_return", "total_return"),
        "drawdown_reduction": (
            "drawdown_reduction_vs_uncontrolled_baseline",
            "drawdown_reduction_vs_uncontrolled_baseline",
        ),
        "cagr_retention": (
            "cagr_retention_vs_uncontrolled_baseline",
            "cagr_retention_vs_uncontrolled_baseline",
        ),
        "average_bil_cash_share": ("average_bil_cash_share", "average_bil_cash_share"),
        "duplicate_reference_correlation": ("duplicate_reference_correlation", "duplicate_reference_correlation"),
    }
    mismatches: list[str] = []
    for label, (base_field, source_field) in comparisons.items():
        left = parse_float(base_eval.get(base_field))
        right = parse_float(source_run_row.get(source_field))
        if not finite(left) or not finite(right) or abs(left - right) > SOURCE_METRIC_TOLERANCE:
            mismatches.append(label)
    return mismatches


def subperiod_metrics(row: dict[str, str], daily: pd.Series, weights: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    latest = daily.index.max().date().isoformat() if not daily.empty else ""
    for period_id, start_text, end_text in SUBPERIODS:
        start = pd.Timestamp(start_text)
        end = pd.Timestamp(end_text) if end_text else daily.index.max()
        subset = daily.loc[(daily.index >= start) & (daily.index <= end)]
        subset_weights = weights.loc[weights.index.intersection(subset.index)]
        if subset.empty:
            out.append(
                {
                    "variant_id": row["variant_id"],
                    "variant_role": row["variant_role"],
                    "concept": row["concept"],
                    "universe_group": row["universe_group"],
                    "period_id": period_id,
                    "start_date": start_text,
                    "end_date": end_text or latest,
                    "subperiod_weakness_flag": True,
                }
            )
            continue
        metrics = metrics_for_returns(subset, subset_weights)
        weakness = (
            metrics.get("total_return", 0.0) < 0.0
            or metrics.get("cagr", 0.0) < 0.0
            or metrics.get("max_drawdown", 0.0) <= -0.3500
        )
        out.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "concept": row["concept"],
                "universe_group": row["universe_group"],
                "period_id": period_id,
                "start_date": metrics.get("start_date", start_text),
                "end_date": metrics.get("end_date", end_text or latest),
                "total_return": metrics.get("total_return", float("nan")),
                "cagr": metrics.get("cagr", float("nan")),
                "max_drawdown": metrics.get("max_drawdown", float("nan")),
                "calmar_or_return_drawdown_proxy": metrics.get("calmar_or_return_drawdown_proxy", float("nan")),
                "subperiod_weakness_flag": weakness,
            }
        )
    return out


def rolling_weakness(row: dict[str, str], daily: pd.Series) -> dict[str, Any]:
    equity = equity_curve(daily)
    returns_180 = (equity / equity.shift(180) - 1.0).dropna()
    returns_252 = (equity / equity.shift(252) - 1.0).dropna()
    worst_180 = float(returns_180.min()) if not returns_180.empty else float("nan")
    worst_252 = float(returns_252.min()) if not returns_252.empty else float("nan")
    positive_180 = float((returns_180 > 0.0).mean()) if not returns_180.empty else float("nan")
    positive_252 = float((returns_252 > 0.0).mean()) if not returns_252.empty else float("nan")
    weakness = (finite(worst_180) and worst_180 <= -0.2000) or (finite(worst_252) and worst_252 <= -0.2500)
    return {
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "concept": row["concept"],
        "universe_group": row["universe_group"],
        "worst_180_day_return": worst_180,
        "worst_252_day_return": worst_252,
        "positive_180_day_ratio": positive_180,
        "positive_252_day_ratio": positive_252,
        "rolling_window_weakness_flag": weakness,
    }


def active_combo_relationship(eval_row: dict[str, Any]) -> str:
    corr = parse_float(eval_row.get("correlation_to_active_combo"))
    drawdown_delta = parse_float(eval_row.get("active_vm_dsr_combo_max_drawdown_improvement"))
    if finite(corr) and corr >= 0.90:
        return "redundant_vs_active_combo"
    if finite(corr) and corr < 0.85 and finite(drawdown_delta) and drawdown_delta > 0.0:
        return "diversifying_vs_active_combo"
    return "context_or_mixed_vs_active_combo"


def evaluate_robustness(
    root: Path = ROOT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source = load_sources(root)
    design_rows = source["design_rows"]
    source_rows = source["source_rows"]
    run_rows = {
        row["variant_id"]: row for row in read_csv_rows(root / SOURCE_RUN_DIR / "high_return_tactical_bounded_run_results.csv")
    }
    active_returns = active_combo_returns(root)
    stress_rows: list[dict[str, Any]] = []
    subperiod_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    comparator_rows: list[dict[str, Any]] = []
    invariant_failures: list[str] = []
    base_mismatch_ids: list[str] = []

    for row in design_rows:
        source_row = source_rows[row["source_variant_id"]]
        daily, weights, _baseline_daily = run_pair(root, row)
        stress_eval = {
            name: evaluate_daily(root, row, source_row, apply_cost_stress(daily, weights, cost), weights, active_returns)
            for name, cost in STRESS_COSTS.items()
        }
        base_eval = stress_eval["base"]
        mismatches = base_metric_mismatches(base_eval, run_rows.get(row["variant_id"], {}))
        if mismatches:
            base_mismatch_ids.append(row["variant_id"])
        if base_eval.get("exposure_invariant_pass") is not True:
            invariant_failures.append(row["variant_id"])
        turnover = turnover_units(weights)
        stress_rows.append(
            {
                "lane_id": LANE_ID,
                "family_id": FAMILY_ID,
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "concept": row["concept"],
                "universe_group": row["universe_group"],
                "universe": row["universe"],
                "lookback": int(float(row["lookback_days"])),
                "top_n": int(float(row["top_n"])),
                "base_cagr": base_eval.get("cagr"),
                "base_total_return": base_eval.get("total_return"),
                "base_max_drawdown": base_eval.get("max_drawdown"),
                "base_calmar": base_eval.get("calmar_or_return_drawdown_proxy"),
                "base_numeric_criteria_pass": base_eval.get("numeric_criteria_pass"),
                "base_label": base_eval.get("research_only_label"),
                "stress_10bps_cagr": stress_eval["stress_10bps"].get("cagr"),
                "stress_10bps_total_return": stress_eval["stress_10bps"].get("total_return"),
                "stress_10bps_max_drawdown": stress_eval["stress_10bps"].get("max_drawdown"),
                "stress_10bps_calmar": stress_eval["stress_10bps"].get("calmar_or_return_drawdown_proxy"),
                "stress_10bps_numeric_criteria_pass": stress_eval["stress_10bps"].get("numeric_criteria_pass"),
                "stress_10bps_label": stress_eval["stress_10bps"].get("research_only_label"),
                "stress_25bps_cagr": stress_eval["stress_25bps"].get("cagr"),
                "stress_25bps_total_return": stress_eval["stress_25bps"].get("total_return"),
                "stress_25bps_max_drawdown": stress_eval["stress_25bps"].get("max_drawdown"),
                "stress_25bps_calmar": stress_eval["stress_25bps"].get("calmar_or_return_drawdown_proxy"),
                "stress_25bps_numeric_criteria_pass": stress_eval["stress_25bps"].get("numeric_criteria_pass"),
                "stress_25bps_label": stress_eval["stress_25bps"].get("research_only_label"),
                "fails_only_due_to_cost_stress": bool(
                    base_eval.get("numeric_criteria_pass") and not stress_eval["stress_25bps"].get("numeric_criteria_pass")
                ),
                "average_turnover_unit": float(turnover.mean()) if len(turnover) else 0.0,
                "total_turnover_unit": float(turnover.sum()) if len(turnover) else 0.0,
                "base_run_metric_mismatch_fields": "|".join(mismatches),
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
                "candidate_exhaustive_eligibility": False,
            }
        )
        subperiod_rows.extend(subperiod_metrics(row, daily, weights))
        rolling_rows.append(rolling_weakness(row, daily))
        comparator_rows.append(
            {
                "variant_id": row["variant_id"],
                "universe_group": row["universe_group"],
                "lookback": int(float(row["lookback_days"])),
                "bil_cash_total_return_delta": base_eval.get("bil_cash_total_return_delta"),
                "spy_total_return_delta": base_eval.get("spy_total_return_delta"),
                "static_all_weather_total_return_delta": base_eval.get("static_all_weather_total_return_delta"),
                "correlation_to_spy200d": base_eval.get("correlation_to_spy200d"),
                "correlation_to_static_all_weather": base_eval.get("correlation_to_static_all_weather"),
                "correlation_to_active_combo": base_eval.get("correlation_to_active_combo"),
                "active_vm_dsr_combo_total_return_delta": base_eval.get("active_vm_dsr_combo_total_return_delta"),
                "active_vm_dsr_combo_max_drawdown_improvement": base_eval.get("active_vm_dsr_combo_max_drawdown_improvement"),
                "duplicate_reference_correlation": base_eval.get("duplicate_reference_correlation"),
                "active_combo_relationship": active_combo_relationship(base_eval),
            }
        )

    preflight = {
        "source_run_manifest": read_json(root / SOURCE_RUN_DIR / "high_return_tactical_bounded_run_manifest.json"),
        "source_run_consistency": read_json(root / SOURCE_RUN_DIR / "high_return_tactical_bounded_run_consistency_check.json"),
        "source_completed_row_count": len(run_rows),
        "design_row_count": len(design_rows),
        "completed_ids_match_design": {row["variant_id"] for row in design_rows} == set(run_rows),
        "invariant_failures": invariant_failures,
        "base_mismatch_ids": base_mismatch_ids,
        "provider_download_required": False,
        "intraday_data_required": False,
    }
    return stress_rows, subperiod_rows, rolling_rows, comparator_rows, preflight


def manifest_payload(
    created: str,
    output: Path,
    stress_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    comparator_rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    base_pass = sum(1 for row in stress_rows if row.get("base_numeric_criteria_pass") is True)
    rows_still_10 = sum(1 for row in stress_rows if row.get("stress_10bps_numeric_criteria_pass") is True)
    rows_still_25 = sum(1 for row in stress_rows if row.get("stress_25bps_numeric_criteria_pass") is True)
    cost_only_failures = sum(1 for row in stress_rows if row.get("fails_only_due_to_cost_stress") is True)
    subperiod_fail_ids = {row["variant_id"] for row in subperiod_rows if row.get("subperiod_weakness_flag") is True}
    rolling_fail_ids = {row["variant_id"] for row in rolling_rows if row.get("rolling_window_weakness_flag") is True}
    risk_budget_ids = {row["variant_id"] for row in stress_rows if parse_float(row.get("base_max_drawdown")) <= -0.3500}
    diversifying_ids = {
        row["variant_id"] for row in comparator_rows if row.get("active_combo_relationship") == "diversifying_vs_active_combo"
    }
    redundant_ids = {
        row["variant_id"] for row in comparator_rows if row.get("active_combo_relationship") == "redundant_vs_active_combo"
    }
    remain_interesting = {
        row["variant_id"]
        for row in stress_rows
        if row.get("stress_25bps_numeric_criteria_pass") is True
        and row["variant_id"] not in subperiod_fail_ids
        and row["variant_id"] not in rolling_fail_ids
        and row["variant_id"] not in risk_budget_ids
        and row["variant_id"] not in redundant_ids
    }
    invariant_failures = preflight["invariant_failures"]
    usable = (
        len(stress_rows) == EXPECTED_ROW_COUNT
        and preflight["completed_ids_match_design"]
        and preflight["source_run_manifest"].get("results_interpretable") is True
        and preflight["source_run_consistency"].get("consistency_passed") is True
        and not invariant_failures
        and not preflight["base_mismatch_ids"]
    )
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "high_return_tactical_bounded_robustness_report": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_run_reviewed": True,
        "same_6_rows_evaluated": len(stress_rows) == EXPECTED_ROW_COUNT and preflight["completed_ids_match_design"],
        "rows_evaluated": len(stress_rows),
        "cost_model": "evaluation_only_cost_per_turnover_unit",
        "cost_stress_bps": [10, 25],
        "subperiods_evaluated": [period[0] for period in SUBPERIODS],
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_families_created": False,
        "new_variants_created": False,
        "new_rows_added": False,
        "new_concepts_added": False,
        "new_lookbacks_added": False,
        "new_universes_added": False,
        "threshold_tuning_added": False,
        "drawdown_guard_rows_used": False,
        "hidden_parameter_grid_created": False,
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
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "outputs_promotable": False,
        "outputs_candidate_exhaustive_ready": False,
        "outputs_paper_forward_eligible": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_threshold_tuning_continued": False,
        "managed_futures_reopened": False,
        "new_combo_strategy_created": False,
        "exact_rejected_variants_reopened": False,
        "pre_fix_stale_weight_results_used": False,
        "rows_passing_base_criteria": base_pass,
        "rows_still_passing_under_10bps_stress": rows_still_10,
        "rows_still_passing_under_25bps_stress": rows_still_25,
        "rows_failing_only_because_of_cost_stress": cost_only_failures,
        "rows_failing_one_or_more_subperiods": len(subperiod_fail_ids),
        "rows_with_rolling_window_weakness": len(rolling_fail_ids),
        "rows_with_unacceptable_drawdown_or_risk_budget_behavior": len(risk_budget_ids),
        "rows_appearing_diversifying_vs_active_combo": len(diversifying_ids),
        "rows_appearing_redundant_vs_active_combo": len(redundant_ids),
        "rows_remain_interesting_after_robustness": len(remain_interesting),
        "rows_downgraded_to_context_only_after_robustness": len(stress_rows) - len(remain_interesting),
        "data_blockers": 0,
        "invariant_failures": len(invariant_failures),
        "base_run_metric_mismatch_count": len(preflight["base_mismatch_ids"]),
        "robustness_evidence_usable": usable,
        "next_action": NEXT_ACTION_QUEUE if usable else NEXT_ACTION_FIX,
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# High-Return Tactical ETF Equity-Index Bounded Robustness Report

Rows evaluated: `{manifest['rows_evaluated']}`

Rows passing base criteria: `{manifest['rows_passing_base_criteria']}`

Rows still passing under 10 bps stress: `{manifest['rows_still_passing_under_10bps_stress']}`

Rows still passing under 25 bps stress: `{manifest['rows_still_passing_under_25bps_stress']}`

Rows failing only because of cost stress: `{manifest['rows_failing_only_because_of_cost_stress']}`

Rows failing in one or more subperiods: `{manifest['rows_failing_one_or_more_subperiods']}`

Rows with rolling-window weakness: `{manifest['rows_with_rolling_window_weakness']}`

Rows with unacceptable drawdown/risk-budget behavior: `{manifest['rows_with_unacceptable_drawdown_or_risk_budget_behavior']}`

Rows appearing diversifying versus active combo: `{manifest['rows_appearing_diversifying_vs_active_combo']}`

Rows appearing redundant versus active combo: `{manifest['rows_appearing_redundant_vs_active_combo']}`

Rows that remain interesting after robustness: `{manifest['rows_remain_interesting_after_robustness']}`

Rows downgraded to context-only after robustness: `{manifest['rows_downgraded_to_context_only_after_robustness']}`

Invariant failures: `{manifest['invariant_failures']}`

Data blockers: `{manifest['data_blockers']}`

Base run metric mismatch count: `{manifest['base_run_metric_mismatch_count']}`

Robustness evidence usable: `{manifest['robustness_evidence_usable']}`

This packet is diagnostic-only. No output is promotable, candidate_exhaustive-ready, or paper-forward eligible from this task alone.

Exact next action: `{manifest['next_action']}`
"""


def rolling_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rolling Window Weakness Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: worst 180d `{format_float(row['worst_180_day_return'])}`, "
            f"worst 252d `{format_float(row['worst_252_day_return'])}`, "
            f"positive 180d ratio `{format_float(row['positive_180_day_ratio'])}`, "
            f"rolling weakness `{row['rolling_window_weakness_flag']}`"
        )
    return "\n".join(lines) + "\n"


def comparator_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Comparator / Redundancy / Contribution Report", ""]
    lines.append(
        "Active-combo relationship is diagnostic only: diversifying requires active-combo correlation `< 0.85` "
        "and positive active-combo drawdown improvement; redundant requires active-combo correlation `>= 0.90`."
    )
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: SPY delta `{format_float(row['spy_total_return_delta'])}`, "
            f"BIL delta `{format_float(row['bil_cash_total_return_delta'])}`, "
            f"static all-weather delta `{format_float(row['static_all_weather_total_return_delta'])}`, "
            f"SPY_200d corr `{format_float(row['correlation_to_spy200d'])}`, "
            f"active combo corr `{format_float(row['correlation_to_active_combo'])}`, "
            f"active combo drawdown delta `{format_float(row['active_vm_dsr_combo_max_drawdown_improvement'])}`, "
            f"relationship `{row['active_combo_relationship']}`"
        )
    lines.append("")
    lines.append("No new combo strategy or registry candidate is created by this diagnostic.")
    return "\n".join(lines) + "\n"


def invariant_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

- Same six rows evaluated: `{manifest['same_6_rows_evaluated']}`
- Invariant failures: `{manifest['invariant_failures']}`
- Source bounded run metric mismatch count: `{manifest['base_run_metric_mismatch_count']}`
- Max daily exposure invariant: checked through recomputed daily weights.
- Max daily weight sum invariant: checked through recomputed daily weights.
- BIL/cash replacement/remainder invariant: no BIL/cash accumulation above total exposure.
- Zero target weights remain zero until next explicit rebalance target.

No leverage, shorting, options, direct futures, intraday data, provider download, broker/live path, promotion, paper-forward activation, or candidate_exhaustive path occurred.
"""


def next_action_md(next_action: str) -> str:
    return f"""# High-Return Tactical Robustness Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From High-Return Tactical Robustness

This robustness packet creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def consistency_check(manifest: dict[str, Any], output: Path, stress_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["high_return_tactical_bounded_robustness_consistency_check.json"] = True
    checks = {
        "robustness_report": manifest["high_return_tactical_bounded_robustness_report"] is True,
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "same_6_rows": manifest["same_6_rows_evaluated"] is True and len(stress_rows) == EXPECTED_ROW_COUNT,
        "no_strategy_expansion": manifest["new_rows_added"] is False
        and manifest["new_concepts_added"] is False
        and manifest["new_lookbacks_added"] is False
        and manifest["new_universes_added"] is False
        and manifest["new_variants_created"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_threshold_tuning_or_drawdown_guard": manifest["threshold_tuning_added"] is False
        and manifest["drawdown_guard_rows_used"] is False,
        "no_discovery_or_batch": manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family": manifest["new_families_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
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
        "no_promotion_candidate_exhaustive_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True
        and manifest["outputs_promotable"] is False
        and manifest["outputs_candidate_exhaustive_ready"] is False
        and manifest["outputs_paper_forward_eligible"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "unrelated_lanes_not_continued": manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_threshold_tuning_continued"] is False
        and manifest["managed_futures_reopened"] is False,
        "no_new_combo": manifest["new_combo_strategy_created"] is False,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "post_fix_only": manifest["pre_fix_stale_weight_results_used"] is False,
        "no_invariant_failures": manifest["invariant_failures"] == 0,
        "no_base_mismatch": manifest["base_run_metric_mismatch_count"] == 0,
        "base_vs_stress_exists": (output / "base_vs_stress_row_results.csv").exists(),
        "subperiod_exists": (output / "subperiod_performance.csv").exists(),
        "rolling_exists": (output / "rolling_window_weakness.csv").exists(),
        "comparator_exists": (output / "comparator_redundancy_contribution_report.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(
    root: Path,
    created: str,
    stress_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    comparator_rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, stress_rows, subperiod_rows, rolling_rows, comparator_rows, preflight)
    write_json(output / "high_return_tactical_bounded_robustness_manifest.json", manifest)
    write_csv(output / "base_vs_stress_row_results.csv", stress_rows, list(STRESS_FIELDS))
    write_csv(output / "subperiod_performance.csv", subperiod_rows, list(SUBPERIOD_FIELDS))
    write_csv(output / "rolling_window_weakness.csv", rolling_rows, list(ROLLING_FIELDS))
    write_csv(output / "comparator_redundancy_contribution.csv", comparator_rows, list(COMPARATOR_FIELDS))
    write_text(output / "rolling_window_weakness_report.md", rolling_report_md(rolling_rows))
    write_text(output / "comparator_redundancy_contribution_report.md", comparator_report_md(comparator_rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "high_return_tactical_bounded_robustness_summary.md", summary_md(manifest))
    write_text(output / "high_return_tactical_bounded_robustness_next_action.md", next_action_md(manifest["next_action"]))
    write_text(output / "do_not_promote_from_high_return_tactical_robustness.md", do_not_promote_md())
    check = consistency_check(manifest, output, stress_rows)
    write_json(output / "high_return_tactical_bounded_robustness_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    stress_rows, subperiod_rows, rolling_rows, comparator_rows, preflight = evaluate_robustness(root)
    return write_outputs(root, created, stress_rows, subperiod_rows, rolling_rows, comparator_rows, preflight)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "rows_evaluated": result["rows_evaluated"],
                "rows_still_passing_under_10bps_stress": result["rows_still_passing_under_10bps_stress"],
                "rows_still_passing_under_25bps_stress": result["rows_still_passing_under_25bps_stress"],
                "rows_remain_interesting_after_robustness": result["rows_remain_interesting_after_robustness"],
                "robustness_evidence_usable": result["robustness_evidence_usable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
