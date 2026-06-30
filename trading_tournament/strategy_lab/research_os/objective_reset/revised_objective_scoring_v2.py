from __future__ import annotations

import math
from typing import Any


STARTING_EQUITY = 3000.0
SATURATION_SCORE_THRESHOLD = 98.0
SATURATION_WARNING_RATIO = 0.10
SATURATION_FAIL_RATIO = 0.20

INTERPRETATION_STATUSES = (
    "diagnostic_only",
    "usable_for_future_sandbox",
    "needs_manual_review",
    "invalid_for_actionability",
)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return float(max(lower, min(upper, value)))


def logistic_score(value: float, midpoint: float, scale: float) -> float:
    scale = max(scale, 1e-9)
    exponent = max(-60.0, min(60.0, -(value - midpoint) / scale))
    return clamp(100.0 / (1.0 + math.exp(exponent)))


def cash_allocation_penalty(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    objective_lane = str(row.get("objective_lane", ""))
    threshold = 0.35 if objective_lane == "standalone_growth" else 0.55
    return clamp((cash - threshold) / max(1.0 - threshold, 1e-9) * 42.0)


def underinvestment_penalty(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    symbols = to_float(row.get("avg_symbols_held"))
    trades = to_float(row.get("trade_count"))
    max_weight = to_float(row.get("max_symbol_weight"))
    penalty = 0.0
    if symbols < 0.50:
        penalty += (0.50 - symbols) / 0.50 * 22.0
    if trades < 3:
        penalty += 18.0
    if cash > 0.80 and trades < 20:
        penalty += 18.0
    if max_weight == 0.0 and cash > 0.85:
        penalty += 12.0
    return clamp(penalty)


def benchmark_lag_penalty(row: dict[str, Any]) -> float:
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    active_vm_delta = to_float(row.get("active_vm_delta_180d_median"), active_combo_delta)
    active_dsr_delta = to_float(row.get("active_dsr_delta_180d_median"), active_combo_delta)
    penalty = 0.0
    for delta, scale in ((active_combo_delta, 7.0), (active_vm_delta, 11.0), (active_dsr_delta, 11.0)):
        if delta < 0:
            penalty += min(18.0, abs(delta) / scale)
    return clamp(penalty, upper=38.0)


def return_drag_penalty_v2(row: dict[str, Any]) -> float:
    drag = max(0.0, to_float(row.get("return_drag_penalty")))
    return clamp(drag * 28.0, upper=35.0)


def duplicate_penalty_v2(row: dict[str, Any]) -> float:
    explicit = max(0.0, to_float(row.get("duplicate_penalty")))
    corr = abs(to_float(row.get("corr_vs_active_combo")))
    corr_penalty = max(0.0, corr - 0.72) / 0.28 * 40.0
    return clamp(max(explicit, corr_penalty), upper=55.0)


def risk_integrity_score_v2(row: dict[str, Any]) -> float:
    max_drawdown = to_float(row.get("max_drawdown"))
    rolling_drawdown = to_float(row.get("180d_worst_drawdown"))
    risk_buffer = to_float(row.get("risk_buffer_vs_minus_600"))
    stop_hit_rate = to_float(row.get("stop_hit_rate"))
    cash = to_float(row.get("avg_cash_allocation"))
    trades = to_float(row.get("trade_count"))
    score = 48.0 + risk_buffer / 10.0
    score -= max(0.0, -max_drawdown - 320.0) / 7.0
    score -= max(0.0, -rolling_drawdown - 260.0) / 8.0
    score -= stop_hit_rate * 35.0
    if bool_value(row.get("stop_risk_breach_flag")):
        score -= 22.0
    if cash > 0.85 and trades < 20:
        score -= 18.0
    return clamp(score)


def practicality_score_v2(row: dict[str, Any]) -> float:
    turnover = to_float(row.get("avg_turnover"))
    trades = to_float(row.get("trade_count"))
    cash = to_float(row.get("avg_cash_allocation"))
    history = to_float(row.get("data_window_length"))
    score = 84.0
    score -= min(32.0, turnover * 95.0)
    score -= min(28.0, max(0.0, trades - 260.0) / 18.0)
    if trades < 3:
        score -= 25.0
    if cash > 0.90 and trades < 20:
        score -= 18.0
    if history and history < 500:
        score -= 18.0
    return clamp(score)


def overfit_risk_score_v2(row: dict[str, Any]) -> float:
    max_weight = to_float(row.get("max_symbol_weight"))
    history = to_float(row.get("data_window_length"))
    corr = abs(to_float(row.get("corr_vs_active_combo")))
    trades = to_float(row.get("trade_count"))
    family_id = str(row.get("family_id", ""))
    risk = 18.0
    risk += max(0.0, max_weight - 0.55) * 55.0
    risk += max(0.0, corr - 0.80) / 0.20 * 30.0
    if history and history < 500:
        risk += 18.0
    if trades < 3:
        risk += 12.0
    if family_id in {"trend_momentum", "volatility_regime"}:
        risk += 10.0
    return clamp(risk)


def stretch_diagnostic_score_v2(row: dict[str, Any]) -> float:
    target_300 = to_float(row.get("target_300_before_stop_rate"))
    target_400 = to_float(row.get("target_400_before_stop_rate"))
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    portfolio_improvement = to_float(row.get("portfolio_level_risk_adjusted_improvement"))
    return clamp(
        target_300 * 22.0
        + target_400 * 18.0
        + (12.0 if active_combo_delta > 0 else 0.0)
        + (12.0 if portfolio_improvement > 0 else 0.0)
    )


def exposure_quality_score(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    symbols = to_float(row.get("avg_symbols_held"))
    trades = to_float(row.get("trade_count"))
    exposure = 100.0 - cash * 85.0
    if symbols < 0.50:
        exposure -= 20.0
    if trades < 3:
        exposure -= 18.0
    return clamp(exposure)


def standalone_growth_score_v2(row: dict[str, Any]) -> float:
    median_progress = to_float(row.get("180d_median_final_equity"), STARTING_EQUITY) - STARTING_EQUITY
    ending_return = to_float(row.get("total_return"))
    sharpe = to_float(row.get("sharpe"))
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    risk = risk_integrity_score_v2(row)
    practical = practicality_score_v2(row)
    overfit = overfit_risk_score_v2(row)
    growth_evidence = (
        logistic_score(median_progress, midpoint=45.0, scale=85.0) * 0.28
        + logistic_score(ending_return, midpoint=0.04, scale=0.12) * 0.18
        + logistic_score(sharpe, midpoint=0.45, scale=0.70) * 0.16
        + logistic_score(active_combo_delta, midpoint=0.0, scale=95.0) * 0.18
        + risk * 0.12
        + practical * 0.08
    )
    penalty = (
        cash_allocation_penalty(row)
        + underinvestment_penalty(row)
        + benchmark_lag_penalty(row)
        + return_drag_penalty_v2(row)
        + duplicate_penalty_v2(row) * 0.35
        + overfit * 0.16
    )
    score = clamp(growth_evidence - penalty)
    if risk < 30.0:
        score = min(score, 45.0)
    if risk == 0.0:
        score = min(score, 35.0)
    if benchmark_lag_penalty(row) > 25.0:
        score = min(score, 62.0)
    if cash_allocation_penalty(row) + underinvestment_penalty(row) > 42.0:
        score = min(score, 58.0)
    return clamp(score)


def portfolio_contribution_score_v2(row: dict[str, Any]) -> float:
    active_combo_improvement = to_float(row.get("active_combo_improvement"))
    active_pair_improvement = to_float(row.get("active_vm_dsr_pair_improvement"))
    return_risk_improvement = to_float(row.get("portfolio_return_risk_improvement"))
    drawdown_contribution = to_float(row.get("drawdown_contribution"))
    volatility_contribution = to_float(row.get("volatility_contribution"))
    corr_reduction = clamp(to_float(row.get("correlation_reduction")) * 100.0)
    risk = risk_integrity_score_v2(row)
    raw = (
        logistic_score(active_combo_improvement, midpoint=0.0, scale=55.0) * 0.24
        + logistic_score(active_pair_improvement, midpoint=0.0, scale=65.0) * 0.14
        + logistic_score(return_risk_improvement, midpoint=0.0, scale=0.10) * 0.16
        + logistic_score(drawdown_contribution, midpoint=0.0, scale=220.0) * 0.14
        + logistic_score(volatility_contribution, midpoint=0.0, scale=0.015) * 0.08
        + corr_reduction * 0.14
        + risk * 0.10
    )
    drag = return_drag_penalty_v2(row)
    duplicate = duplicate_penalty_v2(row)
    score = clamp(raw - drag - duplicate * 0.70 - overfit_risk_score_v2(row) * 0.08)
    if duplicate > 30.0 and active_combo_improvement <= 0:
        score = min(score, 52.0)
    if drag > 18.0 and active_combo_improvement <= 0:
        score = min(score, 58.0)
    return clamp(score)


def contribution_net_of_drag_score(row: dict[str, Any]) -> float:
    return clamp(portfolio_contribution_score_v2(row) - return_drag_penalty_v2(row) * 0.50)


def score_row_v2(row: dict[str, Any], *, interpretation_status: str = "diagnostic_only") -> dict[str, Any]:
    if interpretation_status not in INTERPRETATION_STATUSES:
        raise ValueError(f"invalid score interpretation status: {interpretation_status}")
    standalone = standalone_growth_score_v2(row)
    contribution = portfolio_contribution_score_v2(row)
    stretch = stretch_diagnostic_score_v2(row)
    risk = risk_integrity_score_v2(row)
    overfit = overfit_risk_score_v2(row)
    practical = practicality_score_v2(row)
    return {
        "standalone_growth_score_v2": standalone,
        "portfolio_contribution_score_v2": contribution,
        "stretch_diagnostic_score_v2": stretch,
        "risk_integrity_score_v2": risk,
        "overfit_risk_score_v2": overfit,
        "practicality_score_v2": practical,
        "cash_allocation_penalty": cash_allocation_penalty(row),
        "underinvestment_penalty": underinvestment_penalty(row),
        "exposure_quality_score": exposure_quality_score(row),
        "active_combo_delta_penalty": benchmark_lag_penalty(row),
        "active_reference_lag_penalty": benchmark_lag_penalty(row),
        "benchmark_lag_penalty": benchmark_lag_penalty(row),
        "return_drag_penalty_v2": return_drag_penalty_v2(row),
        "contribution_net_of_drag_score": contribution_net_of_drag_score(row),
        "risk_integrity_gate": risk / 100.0,
        "risk_adjusted_growth_score": clamp(standalone * (risk / 100.0)),
        "drawdown_quality_score": risk,
        "duplicate_penalty_v2": duplicate_penalty_v2(row),
        "active_combo_duplicate_penalty": duplicate_penalty_v2(row),
        "correlation_adjusted_contribution_score": clamp(contribution - duplicate_penalty_v2(row) * 0.35),
        "turnover_penalty": clamp(to_float(row.get("avg_turnover")) * 95.0, upper=32.0),
        "trade_count_penalty": clamp(max(0.0, to_float(row.get("trade_count")) - 260.0) / 18.0, upper=28.0),
        "inactivity_penalty": 25.0 if to_float(row.get("trade_count")) < 3 else 0.0,
        "limited_history_penalty": 18.0
        if 0.0 < to_float(row.get("data_window_length")) < 500.0
        else 0.0,
        "data_quality_score": 82.0
        if to_float(row.get("data_window_length")) >= 500.0
        else 55.0,
        "score_saturation_flag": standalone >= SATURATION_SCORE_THRESHOLD,
        "score_interpretation_status": interpretation_status,
    }


def score_rows_v2(rows: list[dict[str, Any]], *, interpretation_status: str = "diagnostic_only") -> list[dict[str, Any]]:
    return [{**row, **score_row_v2(row, interpretation_status=interpretation_status)} for row in rows]


def saturation_report(rows: list[dict[str, Any]], score_field: str = "standalone_growth_score_v2") -> dict[str, Any]:
    total = len(rows)
    saturated = sum(1 for row in rows if to_float(row.get(score_field)) >= SATURATION_SCORE_THRESHOLD)
    ratio = saturated / total if total else 0.0
    return {
        "score_field": score_field,
        "saturation_threshold": SATURATION_SCORE_THRESHOLD,
        "saturated_count": saturated,
        "row_count": total,
        "saturated_ratio": ratio,
        "saturation_warning": ratio > SATURATION_WARNING_RATIO,
        "saturation_failed": ratio > SATURATION_FAIL_RATIO,
    }
