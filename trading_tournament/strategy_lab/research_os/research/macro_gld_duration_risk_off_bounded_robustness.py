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
from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_run import (
    LANE_ID,
    SOURCE_FAMILY,
    build_macro_weights,
    finite,
    metrics_for_returns,
    parse_float,
    safe_corr,
    static_all_weather_returns,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    active_combo_returns,
    benchmark_delta,
    contribution_metrics,
    equity_curve,
    load_price_series,
    max_drawdown,
    write_csv,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import reference_spy200d_returns


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"
)
SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_robustness" / "latest"

EXPECTED_ROW_COUNT = 8
STRESS_COSTS = {"base": 0.0, "stress_10bps": 0.0010, "stress_25bps": 0.0025}
SUBPERIODS = (
    ("subperiod_2007_2014", "2007-01-03", "2014-12-31"),
    ("subperiod_2015_2020", "2015-01-01", "2020-12-31"),
    ("subperiod_2021_latest", "2021-01-01", None),
)
NEXT_ACTION_DESIGN = "design_macro_gld_duration_risk_off_confirmation_lane"
NEXT_ACTION_QUEUE = "return_to_profit_oriented_research_queue"
NEXT_ACTION_FIX = "fix_macro_gld_duration_risk_off_bounded_robustness_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_DESIGN, NEXT_ACTION_QUEUE, NEXT_ACTION_FIX}

REQUIRED_FILES = (
    "macro_gld_bounded_robustness_manifest.json",
    "macro_gld_bounded_robustness_consistency_check.json",
    "base_vs_stress_row_results.csv",
    "subperiod_performance.csv",
    "rolling_window_weakness.csv",
    "rolling_window_weakness_report.md",
    "comparator_robustness_report.md",
    "exposure_invariant_report.md",
    "macro_gld_bounded_robustness_summary.md",
    "macro_gld_bounded_robustness_next_action.md",
    "do_not_promote_from_macro_gld_robustness.md",
)

STRESS_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "concept",
    "lookback_days",
    "top_n",
    "universe",
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
    "promotion_eligibility",
    "paper_forward_eligibility",
)

SUBPERIOD_FIELDS = (
    "variant_id",
    "variant_role",
    "concept",
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
    "worst_180_day_return",
    "worst_252_day_return",
    "positive_180_day_ratio",
    "positive_252_day_ratio",
    "unacceptable_rolling_weakness",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def turnover_units(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float)
    return weights.diff().abs().fillna(weights.abs()).sum(axis=1) / 2.0


def apply_cost_stress(daily: pd.Series, weights: pd.DataFrame, cost_per_turnover_unit: float) -> pd.Series:
    costs = turnover_units(weights).reindex(daily.index).fillna(0.0) * cost_per_turnover_unit
    return (daily - costs).rename(daily.name)


def standalone_and_portfolio_criteria(
    root: Path,
    daily: pd.Series,
    weights: pd.DataFrame,
    active_returns: pd.Series,
) -> dict[str, Any]:
    metrics = metrics_for_returns(daily, weights)
    bil_returns = load_price_series(root, "BIL").pct_change(fill_method=None).dropna().rename("BIL")
    spy_returns = load_price_series(root, "SPY").pct_change(fill_method=None).dropna().rename("SPY")
    spy200d = reference_spy200d_returns(root, daily.index)
    static_returns = static_all_weather_returns(root, daily.index)
    contribution = contribution_metrics(daily, active_returns)
    corr_spy200d = safe_corr(daily, spy200d)
    corr_static = safe_corr(daily, static_returns)
    corr_active = contribution["active_combo_correlation"]
    duplicate_values = [value for value in (corr_spy200d, corr_static, corr_active) if finite(value)]
    duplicate_reference = max(duplicate_values) if duplicate_values else float("nan")
    same_window_vs_bil = benchmark_delta(daily, bil_returns)
    standalone_pass = (
        metrics.get("cagr", float("nan")) >= 0.0600
        and metrics.get("max_drawdown", float("nan")) >= -0.3000
        and metrics.get("calmar_or_return_drawdown_proxy", float("nan")) >= 0.2500
        and same_window_vs_bil >= 0.5000
        and metrics.get("average_bil_cash_share", float("nan")) <= 0.5500
    )
    portfolio_pass = (
        finite(contribution["active_combo_blend_drawdown_delta"])
        and contribution["active_combo_blend_drawdown_delta"] >= 0.0300
        and finite(contribution["active_combo_blend_total_return_delta"])
        and contribution["active_combo_blend_total_return_delta"] >= -0.0200
        and finite(corr_active)
        and corr_active < 0.7500
        and metrics.get("average_bil_cash_share", float("nan")) <= 0.6500
    )
    duplicate_fail = finite(duplicate_reference) and duplicate_reference >= 0.9000
    exposure_pass = (
        metrics.get("max_daily_exposure", 99.0) <= 1.000001
        and metrics.get("max_daily_weight_sum", 99.0) <= 1.000001
        and int(metrics.get("weight_sum_violation_count", 1)) == 0
        and int(metrics.get("negative_weight_violation_count", 1)) == 0
        and int(metrics.get("nan_weight_count", 1)) == 0
        and int(metrics.get("impossible_cash_and_risky_exposure_days", 1)) == 0
    )
    if duplicate_fail:
        label = "macro_gld_signal_duplicate_reference"
    elif metrics.get("average_bil_cash_share", 99.0) > 0.6500 or metrics.get("cagr", -99.0) < 0.0400:
        label = "macro_gld_signal_too_defensive"
    elif metrics.get("max_drawdown", -99.0) < -0.3500:
        label = "macro_gld_signal_drawdown_not_fixed"
    elif standalone_pass and exposure_pass:
        label = "macro_gld_signal_interesting"
    elif portfolio_pass and exposure_pass:
        label = "macro_gld_signal_diversifier"
    elif metrics.get("cagr", -99.0) >= 0.0500 or finite(corr_active):
        label = "macro_gld_signal_context_only"
    else:
        label = "macro_gld_signal_weak"
    return {
        **metrics,
        "same_window_return_vs_bil": same_window_vs_bil,
        "spy_total_return_delta": benchmark_delta(daily, spy_returns),
        "static_all_weather_total_return_delta": benchmark_delta(daily, static_returns)
        if not static_returns.empty
        else float("nan"),
        "correlation_to_spy200d": corr_spy200d,
        "correlation_to_static_all_weather": corr_static,
        "correlation_to_active_combo": corr_active,
        "duplicate_reference_correlation": duplicate_reference,
        "active_vm_dsr_combo_max_drawdown_improvement": contribution["active_combo_blend_drawdown_delta"],
        "active_vm_dsr_combo_total_return_drag": contribution["active_combo_blend_total_return_delta"],
        "standalone_criteria_pass": standalone_pass and exposure_pass and not duplicate_fail,
        "portfolio_diversifier_criteria_pass": portfolio_pass and exposure_pass and not duplicate_fail,
        "numeric_criteria_pass": (standalone_pass or portfolio_pass) and exposure_pass and not duplicate_fail,
        "research_only_label": label,
        "exposure_invariant_pass": exposure_pass,
    }


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
            or metrics.get("max_drawdown", 0.0) < -0.2500
        )
        out.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "concept": row["concept"],
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
    positive_180 = float((returns_180 > 0).mean()) if not returns_180.empty else float("nan")
    positive_252 = float((returns_252 > 0).mean()) if not returns_252.empty else float("nan")
    unacceptable = (finite(worst_180) and worst_180 < -0.2000) or (finite(worst_252) and worst_252 < -0.2500)
    return {
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "concept": row["concept"],
        "worst_180_day_return": worst_180,
        "worst_252_day_return": worst_252,
        "positive_180_day_ratio": positive_180,
        "positive_252_day_ratio": positive_252,
        "unacceptable_rolling_weakness": unacceptable,
    }


def evaluate_robustness(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv")
    completed_rows = read_csv_rows(root / SOURCE_RUN_DIR / "macro_gld_bounded_row_results.csv")
    completed_ids = {row["variant_id"] for row in completed_rows}
    active_returns = active_combo_returns(root)
    stress_rows: list[dict[str, Any]] = []
    subperiod_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    invariant_failures: list[str] = []
    comparator_rows: list[dict[str, Any]] = []
    for row in design_rows:
        daily, weights = build_macro_weights(root, row)
        base_eval = standalone_and_portfolio_criteria(root, daily, weights, active_returns)
        stress_eval: dict[str, dict[str, Any]] = {}
        for stress_name, cost in STRESS_COSTS.items():
            stressed_daily = apply_cost_stress(daily, weights, cost)
            stress_eval[stress_name] = standalone_and_portfolio_criteria(root, stressed_daily, weights, active_returns)
        turnover = turnover_units(weights)
        if base_eval.get("exposure_invariant_pass") is not True:
            invariant_failures.append(row["variant_id"])
        stress_rows.append(
            {
                "lane_id": LANE_ID,
                "family_id": SOURCE_FAMILY,
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "concept": row["concept"],
                "lookback_days": row["lookback_days"],
                "top_n": row["top_n"],
                "universe": row["universe"],
                "base_cagr": stress_eval["base"].get("cagr"),
                "base_total_return": stress_eval["base"].get("total_return"),
                "base_max_drawdown": stress_eval["base"].get("max_drawdown"),
                "base_calmar": stress_eval["base"].get("calmar_or_return_drawdown_proxy"),
                "base_numeric_criteria_pass": stress_eval["base"].get("numeric_criteria_pass"),
                "base_label": stress_eval["base"].get("research_only_label"),
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
                    stress_eval["base"].get("numeric_criteria_pass")
                    and not stress_eval["stress_25bps"].get("numeric_criteria_pass")
                ),
                "average_turnover_unit": float(turnover.mean()) if len(turnover) else 0.0,
                "total_turnover_unit": float(turnover.sum()) if len(turnover) else 0.0,
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
            }
        )
        subperiod_rows.extend(subperiod_metrics(row, daily, weights))
        rolling_rows.append(rolling_weakness(row, daily))
        comparator_rows.append(
            {
                "variant_id": row["variant_id"],
                "bil_delta": base_eval.get("same_window_return_vs_bil"),
                "spy_delta": base_eval.get("spy_total_return_delta"),
                "static_all_weather_delta": base_eval.get("static_all_weather_total_return_delta"),
                "spy200d_correlation": base_eval.get("correlation_to_spy200d"),
                "static_all_weather_correlation": base_eval.get("correlation_to_static_all_weather"),
                "active_combo_correlation": base_eval.get("correlation_to_active_combo"),
                "active_combo_total_return_drag": base_eval.get("active_vm_dsr_combo_total_return_drag"),
                "active_combo_drawdown_improvement": base_eval.get("active_vm_dsr_combo_max_drawdown_improvement"),
            }
        )
    preflight = {
        "source_run_manifest": read_json(root / SOURCE_RUN_DIR / "macro_gld_bounded_run_manifest.json"),
        "source_completed_row_count": len(completed_rows),
        "design_row_count": len(design_rows),
        "completed_ids_match_design": {row["variant_id"] for row in design_rows} == completed_ids,
        "invariant_failures": invariant_failures,
        "provider_download_required": False,
        "intraday_data_required": False,
        "comparator_rows": comparator_rows,
    }
    return stress_rows, subperiod_rows, rolling_rows, preflight


def manifest_payload(
    created: str,
    output: Path,
    stress_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    rows_still_10 = sum(1 for row in stress_rows if row.get("stress_10bps_numeric_criteria_pass") is True)
    rows_still_25 = sum(1 for row in stress_rows if row.get("stress_25bps_numeric_criteria_pass") is True)
    cost_only_failures = sum(1 for row in stress_rows if row.get("fails_only_due_to_cost_stress") is True)
    subperiod_fail_ids = {
        row["variant_id"] for row in subperiod_rows if row.get("subperiod_weakness_flag") is True
    }
    rolling_fail_ids = {
        row["variant_id"] for row in rolling_rows if row.get("unacceptable_rolling_weakness") is True
    }
    robust_ids = {
        row["variant_id"]
        for row in stress_rows
        if row.get("stress_25bps_numeric_criteria_pass") is True
        and row["variant_id"] not in subperiod_fail_ids
        and row["variant_id"] not in rolling_fail_ids
    }
    invariant_failures = preflight["invariant_failures"]
    usable = (
        len(stress_rows) == EXPECTED_ROW_COUNT
        and preflight["completed_ids_match_design"]
        and not invariant_failures
        and preflight["source_run_manifest"].get("results_interpretable") is True
    )
    next_action = NEXT_ACTION_FIX if not usable else (NEXT_ACTION_DESIGN if robust_ids else NEXT_ACTION_QUEUE)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "macro_gld_bounded_robustness_report": True,
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "source_run_reviewed": True,
        "same_8_rows_evaluated": len(stress_rows) == EXPECTED_ROW_COUNT and preflight["completed_ids_match_design"],
        "rows_evaluated": len(stress_rows),
        "cost_model": "evaluation_only_cost_per_turnover_unit",
        "cost_stress_bps": [10, 25],
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_families_created": False,
        "new_rows_added": False,
        "new_concepts_added": False,
        "new_lookbacks_added": False,
        "new_universes_added": False,
        "hidden_parameter_grid_created": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
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
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "rows_still_passing_under_10bps_stress": rows_still_10,
        "rows_still_passing_under_25bps_stress": rows_still_25,
        "rows_failing_only_because_of_cost_stress": cost_only_failures,
        "rows_failing_one_or_more_subperiods": len(subperiod_fail_ids),
        "rows_with_unacceptable_rolling_window_weakness": len(rolling_fail_ids),
        "rows_remain_interesting_after_robustness": len(robust_ids),
        "rows_context_only_after_robustness": len(stress_rows) - len(robust_ids),
        "data_blockers": 0,
        "invariant_failures": len(invariant_failures),
        "robustness_evidence_usable": usable,
        "next_action": next_action,
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Macro / GLD Bounded Robustness Report

Rows evaluated: `{manifest['rows_evaluated']}`

Rows still passing under 10 bps stress: `{manifest['rows_still_passing_under_10bps_stress']}`

Rows still passing under 25 bps stress: `{manifest['rows_still_passing_under_25bps_stress']}`

Rows failing only because of cost stress: `{manifest['rows_failing_only_because_of_cost_stress']}`

Rows failing in one or more subperiods: `{manifest['rows_failing_one_or_more_subperiods']}`

Rows with unacceptable rolling-window weakness: `{manifest['rows_with_unacceptable_rolling_window_weakness']}`

Rows that remain interesting after robustness views: `{manifest['rows_remain_interesting_after_robustness']}`

Rows that should remain context-only after robustness views: `{manifest['rows_context_only_after_robustness']}`

Data blockers: `{manifest['data_blockers']}`

Invariant failures: `{manifest['invariant_failures']}`

Robustness evidence usable: `{manifest['robustness_evidence_usable']}`

This packet is diagnostic-only. No output is promotable or paper-forward eligible from this task alone.

Exact next action: `{manifest['next_action']}`
"""


def rolling_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rolling Window Weakness Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: worst 180d `{parse_float(row['worst_180_day_return']):.6f}`, "
            f"worst 252d `{parse_float(row['worst_252_day_return']):.6f}`, "
            f"unacceptable `{row['unacceptable_rolling_weakness']}`"
        )
    return "\n".join(lines) + "\n"


def comparator_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Comparator Robustness Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: BIL delta `{parse_float(row['bil_delta']):.6f}`, "
            f"SPY delta `{parse_float(row['spy_delta']):.6f}`, static all-weather delta "
            f"`{parse_float(row['static_all_weather_delta']):.6f}`, active combo corr "
            f"`{parse_float(row['active_combo_correlation']):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather remains benchmark/control only.")
    return "\n".join(lines) + "\n"


def invariant_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

- Same 8 rows evaluated: `{manifest['same_8_rows_evaluated']}`
- Invariant failures: `{manifest['invariant_failures']}`
- Max daily exposure invariant: checked in source run and recomputed daily weights for this report.
- Max daily weight sum invariant: checked in source run and recomputed daily weights for this report.
- BIL/cash replacement/remainder invariant: no BIL/cash accumulation on top of full risky exposure was allowed by the shared weight builder.
- Zero target weights remain zero until next explicit rebalance target.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Macro / GLD Robustness Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Macro / GLD Robustness

This robustness packet creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def consistency_check(manifest: dict[str, Any], output: Path, stress_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["macro_gld_bounded_robustness_consistency_check.json"] = True
    checks = {
        "robustness_report": manifest["macro_gld_bounded_robustness_report"] is True,
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == SOURCE_FAMILY,
        "same_8_rows": manifest["same_8_rows_evaluated"] is True and len(stress_rows) == EXPECTED_ROW_COUNT,
        "no_strategy_expansion": manifest["new_rows_added"] is False
        and manifest["new_concepts_added"] is False
        and manifest["new_lookbacks_added"] is False
        and manifest["new_universes_added"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_discovery_or_batch": manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family": manifest["new_families_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
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
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "no_invariant_failures": manifest["invariant_failures"] == 0,
        "base_vs_stress_exists": (output / "base_vs_stress_row_results.csv").exists(),
        "subperiod_exists": (output / "subperiod_performance.csv").exists(),
        "rolling_exists": (output / "rolling_window_weakness.csv").exists(),
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
    preflight: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, stress_rows, subperiod_rows, rolling_rows, preflight)
    write_json(output / "macro_gld_bounded_robustness_manifest.json", manifest)
    write_csv(output / "base_vs_stress_row_results.csv", stress_rows, list(STRESS_FIELDS))
    write_csv(output / "subperiod_performance.csv", subperiod_rows, list(SUBPERIOD_FIELDS))
    write_csv(output / "rolling_window_weakness.csv", rolling_rows, list(ROLLING_FIELDS))
    write_text(output / "rolling_window_weakness_report.md", rolling_report_md(rolling_rows))
    write_text(output / "comparator_robustness_report.md", comparator_report_md(preflight["comparator_rows"]))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "macro_gld_bounded_robustness_summary.md", summary_md(manifest))
    write_text(output / "macro_gld_bounded_robustness_next_action.md", next_action_md(manifest["next_action"]))
    write_text(output / "do_not_promote_from_macro_gld_robustness.md", do_not_promote_md())
    check = consistency_check(manifest, output, stress_rows)
    write_json(output / "macro_gld_bounded_robustness_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    stress_rows, subperiod_rows, rolling_rows, preflight = evaluate_robustness(root)
    return write_outputs(root, created, stress_rows, subperiod_rows, rolling_rows, preflight)


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
        )
    )
