from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_design import (
    LANE_ID,
    SOURCE_FAMILY,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    active_combo_returns,
    benchmark_delta,
    complete_rebalance_weight_frame,
    contribution_metrics,
    equity_curve,
    load_prices,
    load_price_series,
    max_drawdown,
    month_rebalance_mask,
    rolling_window_stats,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import (
    WEIGHT_TOLERANCE,
    available_symbols,
    reference_spy200d_returns,
)


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"
)
OUTPUT_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest"
EXPECTED_ROW_COUNT = 8

NEXT_ACTION_AUDIT = "audit_macro_gld_duration_risk_off_bounded_research_lane_results"
NEXT_ACTION_FIX = "fix_macro_gld_duration_risk_off_bounded_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

ALLOWED_LABELS = {
    "macro_gld_signal_interesting",
    "macro_gld_signal_diversifier",
    "macro_gld_signal_context_only",
    "macro_gld_signal_too_defensive",
    "macro_gld_signal_drawdown_not_fixed",
    "macro_gld_signal_duplicate_reference",
    "macro_gld_signal_data_blocked",
    "macro_gld_signal_weak",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "concept",
    "lookback_days",
    "top_n",
    "universe",
    "comparator_references",
    "data_availability_status",
    "missing_symbols",
    "start_date",
    "end_date",
    "cagr",
    "total_return",
    "max_drawdown",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "same_window_return_vs_bil",
    "spy_total_return_delta",
    "static_all_weather_total_return_delta",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "average_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "average_weight_sum",
    "correlation_to_spy200d",
    "correlation_to_static_all_weather",
    "correlation_to_active_combo",
    "duplicate_reference_correlation",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "active_vm_dsr_combo_total_return_drag",
    "trade_count",
    "turnover_proxy",
    "worst_180_day_window",
    "best_180_day_window",
    "positive_180_day_window_ratio",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "exposure_invariant_pass",
    "standalone_criteria_pass",
    "portfolio_diversifier_criteria_pass",
    "numeric_criteria_pass",
    "research_only_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "concept",
    "cagr",
    "cagr_pass",
    "max_drawdown",
    "drawdown_pass",
    "calmar_or_return_drawdown_proxy",
    "calmar_pass",
    "same_window_return_vs_bil",
    "bil_return_delta_pass",
    "average_bil_cash_share",
    "standalone_bil_share_pass",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "portfolio_drawdown_improvement_pass",
    "active_vm_dsr_combo_total_return_drag",
    "portfolio_return_drag_pass",
    "correlation_to_active_combo",
    "active_combo_correlation_pass",
    "portfolio_bil_share_pass",
    "duplicate_reference_correlation",
    "duplicate_reference_pass",
    "exposure_invariant_pass",
    "standalone_criteria_pass",
    "portfolio_diversifier_criteria_pass",
    "numeric_criteria_pass",
    "research_only_label",
)

REQUIRED_FILES = (
    "macro_gld_bounded_run_manifest.json",
    "macro_gld_bounded_run_consistency_check.json",
    "macro_gld_bounded_row_results.csv",
    "macro_gld_bounded_numeric_criteria_results.csv",
    "exposure_invariant_report.md",
    "baseline_comparator_report.md",
    "macro_gld_bounded_label_summary.md",
    "macro_gld_bounded_run_summary.md",
    "macro_gld_bounded_run_next_action.md",
    "do_not_promote_from_macro_gld_bounded_run.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(value: Any) -> bool:
    parsed = parse_float(value)
    return math.isfinite(parsed)


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1, sort=False).dropna()
    if len(aligned) < 252:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def target_template(symbols: list[str]) -> dict[str, float]:
    return {symbol: 0.0 for symbol in symbols}


def gate_pass(prior_returns: pd.Series, trend: pd.Series, symbol: str) -> bool:
    return bool(prior_returns.get(symbol, float("nan")) > 0 and trend.get(symbol, False))


def top_symbols(scores: pd.Series, symbols: list[str], count: int) -> list[str]:
    clean = scores.reindex(symbols).dropna()
    if clean.empty:
        return []
    return list(clean.sort_values(ascending=False).head(count).index)


def canary_target(
    *,
    symbols: list[str],
    scores: pd.Series,
    trend: pd.Series,
    spy_risk_on: bool,
    top_n: int,
) -> dict[str, float]:
    target = target_template(symbols)
    defensive = ["GLD", "TLT", "IEF"]
    if spy_risk_on:
        target["SPY"] = 0.5
        slot = 0.5 / top_n
        selected = top_symbols(scores, defensive, top_n)
        for symbol in selected:
            if bool(trend.get(symbol, False)):
                target[symbol] += slot
            else:
                target["BIL"] += slot
        target["BIL"] += slot * max(0, top_n - len(selected))
    else:
        candidates = defensive + ["BIL"]
        slot = 1.0 / top_n
        selected = top_symbols(scores, candidates, top_n)
        for symbol in selected:
            if symbol == "BIL":
                target["BIL"] += slot
            elif bool(trend.get(symbol, False)):
                target[symbol] += slot
            else:
                target["BIL"] += slot
        target["BIL"] += slot * max(0, top_n - len(selected))
    return target


def defensive_sleeve_target(*, symbols: list[str], scores: pd.Series, trend: pd.Series) -> dict[str, float]:
    target = target_template(symbols)
    selected = top_symbols(scores, ["GLD", "TLT", "IEF"], 1)
    if selected and bool(trend.get(selected[0], False)):
        target[selected[0]] = 1.0
    else:
        target["BIL"] = 1.0
    return target


def gated_barbell_target(*, symbols: list[str], prior_returns: pd.Series, trend: pd.Series) -> dict[str, float]:
    target = target_template(symbols)
    spy_gate = gate_pass(prior_returns, trend, "SPY")
    gld_gate = gate_pass(prior_returns, trend, "GLD")
    ief_gate = gate_pass(prior_returns, trend, "IEF")

    if spy_gate:
        target["SPY"] = 0.4
        gld_amount = 0.3
        ief_amount = 0.3
    else:
        gld_amount = 0.5
        ief_amount = 0.5

    if gld_gate:
        target["GLD"] += gld_amount
    else:
        target["BIL"] += gld_amount
    if ief_gate:
        target["IEF"] += ief_amount
    else:
        target["BIL"] += ief_amount
    return target


def normalize_target(target: dict[str, float], symbols: list[str]) -> dict[str, float]:
    clean = {symbol: max(0.0, float(target.get(symbol, 0.0))) for symbol in symbols}
    total = sum(clean.values())
    if total > 1.0 + WEIGHT_TOLERANCE:
        for symbol in clean:
            clean[symbol] /= total
    if "BIL" in clean and sum(value for symbol, value in clean.items() if symbol != "BIL") <= WEIGHT_TOLERANCE:
        clean = {symbol: 0.0 for symbol in clean}
        clean["BIL"] = 1.0
    return clean


def build_macro_weights(root: Path, row: dict[str, str]) -> tuple[pd.Series, pd.DataFrame]:
    symbols = [symbol for symbol in row["universe"].split("|") if symbol]
    prices = load_prices(root, tuple(symbols)).ffill()
    if prices.empty or len(prices.dropna(how="all")) < 252:
        return pd.Series(dtype=float), pd.DataFrame()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    lookback = int(float(row["lookback_days"]))
    top_n = int(float(row["top_n"]))
    scores = prices.pct_change(lookback, fill_method=None).shift(1)
    trend = prices.shift(1) > prices.shift(1).rolling(200, min_periods=100).mean()
    prior_returns = scores
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}

    for date in prices.index[month_rebalance_mask(prices.index)]:
        score_row = scores.loc[date]
        trend_row = trend.loc[date].reindex(symbols).fillna(False)
        returns_row = prior_returns.loc[date]
        concept = row["concept"]
        if concept in {"spy_canary_gold_duration_top1", "spy_canary_gold_duration_top2"}:
            target = canary_target(
                symbols=symbols,
                scores=score_row,
                trend=trend_row,
                spy_risk_on=bool(trend_row.get("SPY", False)),
                top_n=top_n,
            )
        elif concept == "gold_duration_trend_sleeve":
            target = defensive_sleeve_target(symbols=symbols, scores=score_row, trend=trend_row)
        elif concept == "equity_gold_duration_gated_barbell":
            target = gated_barbell_target(symbols=symbols, prior_returns=returns_row, trend=trend_row)
        else:
            target = target_template(symbols)
            target["BIL"] = 1.0
        rebalance_targets[pd.Timestamp(date)] = normalize_target(target, symbols)

    weights = complete_rebalance_weight_frame(prices.index, symbols, rebalance_targets)
    daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1).rename(row["variant_id"])
    return daily, weights


def metrics_for_returns(daily: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily.dropna()
    if daily.empty:
        return {}
    eq = equity_curve(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(daily.std() * np.sqrt(252.0))
    mdd = max_drawdown(eq)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    exposure_cols = [column for column in weights.columns if column != "BIL"]
    risky = weights[exposure_cols].sum(axis=1) if exposure_cols else pd.Series(0.0, index=weights.index)
    cash = weights["BIL"] if "BIL" in weights.columns else (1.0 - risky).clip(lower=0.0)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    rolling = rolling_window_stats(eq)
    return {
        "start_date": daily.index.min().date().isoformat(),
        "end_date": daily.index.max().date().isoformat(),
        "cagr": cagr,
        "total_return": total_return,
        "max_drawdown": mdd,
        "volatility": volatility,
        "calmar_or_return_drawdown_proxy": calmar,
        "trade_count": trades,
        "turnover_proxy": turnover,
        "average_exposure": float(risky.mean()) if len(risky) else 0.0,
        "average_bil_cash_share": float(cash.mean()) if len(cash) else 0.0,
        "max_bil_cash_share": float(cash.max()) if len(cash) else 0.0,
        **invariant,
        "worst_180_day_window": rolling["worst_180d_window"],
        "best_180_day_window": rolling["best_180d_window"],
        "positive_180_day_window_ratio": rolling["positive_180d_window_ratio"],
    }


def static_all_weather_returns(root: Path, index: pd.DatetimeIndex) -> pd.Series:
    symbols = ("SPY", "IEF", "GLD", "BIL")
    prices = load_prices(root, symbols).ffill()
    if prices.empty or not set(symbols).issubset(prices.columns):
        return pd.Series(dtype=float, name="static_all_weather")
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    weights = pd.DataFrame(0.0, index=prices.index, columns=list(symbols))
    weights["SPY"] = 0.3
    weights["IEF"] = 0.4
    weights["GLD"] = 0.2
    weights["BIL"] = 0.1
    daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1).rename("static_all_weather")
    return daily.reindex(index).dropna()


def data_blocked_row(row: dict[str, str], missing: list[str], reason: str) -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "variant_id": row.get("variant_id", ""),
        "variant_role": row.get("variant_role", ""),
        "concept": row.get("concept", ""),
        "lookback_days": row.get("lookback_days", ""),
        "top_n": row.get("top_n", ""),
        "universe": row.get("universe", ""),
        "comparator_references": row.get("comparator_references", ""),
        "data_availability_status": "data_blocked",
        "missing_symbols": "|".join(missing),
        "exposure_invariant_pass": False,
        "standalone_criteria_pass": False,
        "portfolio_diversifier_criteria_pass": False,
        "numeric_criteria_pass": False,
        "research_only_label": "macro_gld_signal_data_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": reason,
    }


def evaluate_row(root: Path, row: dict[str, str], local_symbols: set[str], active_returns: pd.Series) -> dict[str, Any]:
    symbols = [symbol for symbol in row["universe"].split("|") if symbol]
    missing = [symbol for symbol in symbols if symbol not in local_symbols]
    if missing:
        return data_blocked_row(row, missing, "required local cache symbols missing")
    daily, weights = build_macro_weights(root, row)
    if daily.empty or weights.empty or len(daily) < 252:
        return data_blocked_row(row, [], "insufficient local cache history")

    run_metrics = metrics_for_returns(daily, weights)
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
    static_delta = benchmark_delta(daily, static_returns) if not static_returns.empty else float("nan")
    exposure_pass = (
        run_metrics["max_daily_exposure"] <= 1.000001
        and run_metrics["max_daily_weight_sum"] <= 1.000001
        and int(run_metrics["weight_sum_violation_count"]) == 0
        and int(run_metrics["negative_weight_violation_count"]) == 0
        and int(run_metrics["nan_weight_count"]) == 0
        and int(run_metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )

    standalone_pass = (
        run_metrics["cagr"] >= 0.0600
        and run_metrics["max_drawdown"] >= -0.3000
        and run_metrics["calmar_or_return_drawdown_proxy"] >= 0.2500
        and same_window_vs_bil >= 0.5000
        and run_metrics["average_bil_cash_share"] <= 0.5500
    )
    portfolio_pass = (
        finite(contribution["active_combo_blend_drawdown_delta"])
        and contribution["active_combo_blend_drawdown_delta"] >= 0.0300
        and finite(contribution["active_combo_blend_total_return_delta"])
        and contribution["active_combo_blend_total_return_delta"] >= -0.0200
        and finite(corr_active)
        and corr_active < 0.7500
        and run_metrics["average_bil_cash_share"] <= 0.6500
    )
    duplicate_fail = finite(duplicate_reference) and duplicate_reference >= 0.9000
    if duplicate_fail:
        label = "macro_gld_signal_duplicate_reference"
    elif run_metrics["average_bil_cash_share"] > 0.6500 or run_metrics["cagr"] < 0.0400:
        label = "macro_gld_signal_too_defensive"
    elif run_metrics["max_drawdown"] < -0.3500:
        label = "macro_gld_signal_drawdown_not_fixed"
    elif standalone_pass:
        label = "macro_gld_signal_interesting"
    elif portfolio_pass:
        label = "macro_gld_signal_diversifier"
    elif run_metrics["cagr"] >= 0.0500 or finite(corr_active):
        label = "macro_gld_signal_context_only"
    else:
        label = "macro_gld_signal_weak"

    return {
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "concept": row["concept"],
        "lookback_days": int(float(row["lookback_days"])),
        "top_n": int(float(row["top_n"])),
        "universe": row["universe"],
        "comparator_references": row["comparator_references"],
        "data_availability_status": "cache_ready",
        "missing_symbols": "",
        **run_metrics,
        "same_window_return_vs_bil": same_window_vs_bil,
        "spy_total_return_delta": benchmark_delta(daily, spy_returns),
        "static_all_weather_total_return_delta": static_delta,
        "correlation_to_spy200d": corr_spy200d,
        "correlation_to_static_all_weather": corr_static,
        "correlation_to_active_combo": corr_active,
        "duplicate_reference_correlation": duplicate_reference,
        "active_vm_dsr_combo_max_drawdown_improvement": contribution["active_combo_blend_drawdown_delta"],
        "active_vm_dsr_combo_total_return_drag": contribution["active_combo_blend_total_return_delta"],
        "exposure_invariant_pass": exposure_pass,
        "standalone_criteria_pass": standalone_pass and exposure_pass and not duplicate_fail,
        "portfolio_diversifier_criteria_pass": portfolio_pass and exposure_pass and not duplicate_fail,
        "numeric_criteria_pass": (standalone_pass or portfolio_pass) and exposure_pass and not duplicate_fail,
        "research_only_label": label,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "approved 8-row Macro/GLD bounded lane; local cache only; diagnostic non-promotable evidence",
    }


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv")
    design_manifest = read_json(root / SOURCE_DESIGN_DIR / "macro_gld_bounded_design_manifest.json")
    local_symbols = available_symbols(root)
    active_returns = active_combo_returns(root)
    rows = [evaluate_row(root, row, local_symbols, active_returns) for row in design_rows]
    preflight = {
        "design_run_ready": design_manifest.get("run_readiness_decision") == "macro_gld_bounded_design_run_ready",
        "design_next_action_correct": design_manifest.get("next_action") == "run_macro_gld_duration_risk_off_bounded_research_lane",
        "planned_row_count": len(design_rows),
        "planned_row_count_exact_8": len(design_rows) == EXPECTED_ROW_COUNT,
        "design_variant_ids": [row["variant_id"] for row in design_rows],
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
        "available_symbols_used": sorted({symbol for row in design_rows for symbol in row["universe"].split("|") if symbol in local_symbols}),
        "provider_download_required": False,
        "intraday_data_required": False,
    }
    return rows, preflight


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for row in rows if row.get("research_only_label") == label) for label in ALLOWED_LABELS}


def pass_fail_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    out: list[dict[str, Any]] = []
    for value, subset in df.groupby(field):
        out.append(
            {
                field: value,
                "row_count": int(len(subset)),
                "numeric_pass_count": int(subset["numeric_criteria_pass"].astype(bool).sum()),
                "numeric_fail_count": int((~subset["numeric_criteria_pass"].astype(bool)).sum()),
                "median_cagr": float(pd.to_numeric(subset["cagr"], errors="coerce").median()),
                "median_max_drawdown": float(pd.to_numeric(subset["max_drawdown"], errors="coerce").median()),
                "median_average_bil_cash_share": float(
                    pd.to_numeric(subset["average_bil_cash_share"], errors="coerce").median()
                ),
            }
        )
    return out


def manifest_payload(created: str, output: Path, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    counts = label_counts(rows)
    max_exposure = max([parse_float(row.get("max_daily_exposure"), 0.0) for row in rows] or [0.0])
    max_weight = max([parse_float(row.get("max_daily_weight_sum"), 0.0) for row in rows] or [0.0])
    invariant_failures = [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]
    data_blocked = [row["variant_id"] for row in rows if row.get("data_availability_status") != "cache_ready"]
    row_count_ok = len(rows) == EXPECTED_ROW_COUNT
    interpretable = row_count_ok and not invariant_failures and preflight["design_run_ready"]
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "macro_gld_bounded_lane_run": True,
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "source_design_run_ready": preflight["design_run_ready"],
        "variant_count_planned": EXPECTED_ROW_COUNT,
        "variant_count_evaluated": len(rows),
        "new_rows_added": False,
        "new_concepts_added": False,
        "new_lookbacks_added": False,
        "new_universes_added": False,
        "hidden_parameter_grid_created": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_families_created": False,
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
        "alpaca_execution_module_delegated": True,
        "data_blocked_row_count": len(data_blocked),
        "rows_passed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is True),
        "rows_failed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is not True),
        "invariant_failure_count": len(invariant_failures),
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight,
        "exposure_invariant_passed": not invariant_failures and max_exposure <= 1.000001 and max_weight <= 1.000001,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        **{f"{label}_count": count for label, count in counts.items()},
        "next_action": next_action,
    }


def summary_md(manifest: dict[str, Any], concept_summary: list[dict[str, Any]], role_summary: list[dict[str, Any]]) -> str:
    label_lines = [f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)]
    concept_lines = [
        f"- `{row['concept']}`: pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in concept_summary
    ]
    role_lines = [
        f"- `{row['variant_role']}`: pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in role_summary
    ]
    return f"""# Macro / GLD Duration Risk-Off Bounded Run

Lane ID: `{manifest['lane_id']}`

Rows run: `{manifest['variant_count_evaluated']}`

Rows passed numeric criteria: `{manifest['rows_passed_numeric_criteria']}`

Rows failed numeric criteria: `{manifest['rows_failed_numeric_criteria']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Pass/fail by concept:

{chr(10).join(concept_lines)}

Pass/fail by role:

{chr(10).join(role_lines)}

Research-only label counts:

{chr(10).join(label_lines)}

No output is promotable or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def invariant_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]
    impossible = sum(int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) for row in rows)
    return f"""# Exposure Invariant Report

- Max daily exposure: `{manifest['max_daily_exposure']}`
- Max daily weight sum: `{manifest['max_daily_weight_sum']}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Invariant failure count: `{manifest['invariant_failure_count']}`
- Impossible BIL/cash plus risky exposure days: `{impossible}`
- Zero target policy: zero targets are explicit at each rebalance and are not stale-forward-filled into prior nonzero allocations.

Failures:

{chr(10).join(f'- `{variant}`' for variant in failures) if failures else '- None'}
"""


def comparator_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Comparator Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: BIL delta `{parse_float(row.get('same_window_return_vs_bil')):.6f}`, "
            f"SPY delta `{parse_float(row.get('spy_total_return_delta')):.6f}`, "
            f"static all-weather delta `{parse_float(row.get('static_all_weather_total_return_delta')):.6f}`, "
            f"active combo corr `{parse_float(row.get('correlation_to_active_combo')):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather is benchmark/control only and is not treated as a candidate.")
    return "\n".join(lines) + "\n"


def label_summary_md(manifest: dict[str, Any]) -> str:
    return "# Macro / GLD Bounded Label Summary\n\n" + "\n".join(
        f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)
    ) + "\n"


def next_action_md(next_action: str) -> str:
    return f"""# Macro / GLD Bounded Run Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Macro / GLD Bounded Run

This run is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["macro_gld_bounded_run_consistency_check.json"] = True
    labels = {row.get("research_only_label", "") for row in rows}
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == SOURCE_FAMILY,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "variant_count_exact_8": manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT,
        "no_design_expansion": manifest["new_rows_added"] is False
        and manifest["new_concepts_added"] is False
        and manifest["new_lookbacks_added"] is False
        and manifest["new_universes_added"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_discovery_or_broad_batch": manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family": manifest["new_families_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "all_rows_non_promotable": all(row.get("promotion_eligibility") is False for row in rows),
        "all_rows_not_paper": all(row.get("paper_forward_eligibility") is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row.get("candidate_exhaustive_eligibility") is False for row in rows),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "row_results_exist": (output / "macro_gld_bounded_row_results.csv").exists(),
        "criteria_results_exist": (output / "macro_gld_bounded_numeric_criteria_results.csv").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_macro_gld_bounded_run.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, rows, preflight)
    concept_summary = pass_fail_by(rows, "concept")
    role_summary = pass_fail_by(rows, "variant_role")
    write_json(output / "macro_gld_bounded_run_manifest.json", manifest)
    write_csv(output / "macro_gld_bounded_row_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "macro_gld_bounded_numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_csv(output / "macro_gld_bounded_concept_summary.csv", concept_summary, list(concept_summary[0].keys()) if concept_summary else [])
    write_csv(output / "macro_gld_bounded_role_summary.csv", role_summary, list(role_summary[0].keys()) if role_summary else [])
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest, rows))
    write_text(output / "baseline_comparator_report.md", comparator_report_md(rows))
    write_text(output / "macro_gld_bounded_label_summary.md", label_summary_md(manifest))
    write_text(output / "macro_gld_bounded_run_summary.md", summary_md(manifest, concept_summary, role_summary))
    write_text(output / "macro_gld_bounded_run_next_action.md", next_action_md(manifest["next_action"]))
    write_text(output / "do_not_promote_from_macro_gld_bounded_run.md", do_not_promote_md())
    check = consistency_check(manifest, rows, output)
    write_json(output / "macro_gld_bounded_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


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
                "rows_passed_numeric_criteria": result["rows_passed_numeric_criteria"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
