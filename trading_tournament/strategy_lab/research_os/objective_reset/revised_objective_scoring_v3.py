from __future__ import annotations

import math
from typing import Any


STARTING_EQUITY = 3000.0
SATURATION_SCORE_THRESHOLD = 98.0
FLOOR_SCORE_THRESHOLD = 5.0
STANDALONE_SATURATION_FAIL_RATIO = 0.20
STANDALONE_FLOOR_FAIL_RATIO = 0.50
RISK_FLOOR_WARNING_RATIO = 0.75

INTERPRETATION_STATUSES_V3 = (
    "diagnostic_only",
    "usable_for_future_sandbox",
    "needs_manual_review",
    "invalid_for_actionability",
)

RISK_GATE_STATUSES_V3 = (
    "pass",
    "soft_warn",
    "hard_warn",
    "fail",
    "insufficient_evidence",
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


def risk_gate_status_v3(row: dict[str, Any]) -> str:
    history = to_float(row.get("data_window_length"))
    if 0.0 < history < 180.0:
        return "insufficient_evidence"
    max_drawdown = to_float(row.get("max_drawdown"))
    rolling_drawdown = to_float(row.get("180d_worst_drawdown"))
    risk_buffer = to_float(row.get("risk_buffer_vs_minus_600"))
    stop_hit_rate = to_float(row.get("stop_hit_rate"))
    stop_breach = bool_value(row.get("stop_risk_breach_flag"))
    if stop_breach or stop_hit_rate >= 0.20 or max_drawdown <= -950.0 or rolling_drawdown <= -800.0:
        return "fail"
    if risk_buffer < -150.0 or max_drawdown <= -700.0 or rolling_drawdown <= -575.0:
        return "hard_warn"
    if risk_buffer < 150.0 or max_drawdown <= -420.0 or rolling_drawdown <= -375.0:
        return "soft_warn"
    return "pass"


def cash_allocation_penalty_v3(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    objective_lane = str(row.get("objective_lane", ""))
    threshold = 0.45 if objective_lane == "standalone_growth" else 0.72
    return clamp((cash - threshold) / max(1.0 - threshold, 1e-9) * 22.0, upper=22.0)


def underinvestment_penalty_v3(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    symbols = to_float(row.get("avg_symbols_held"))
    trades = to_float(row.get("trade_count"))
    max_weight = to_float(row.get("max_symbol_weight"))
    penalty = 0.0
    if symbols < 0.35:
        penalty += (0.35 - symbols) / 0.35 * 12.0
    if trades < 3:
        penalty += 10.0
    if cash > 0.88 and trades < 15:
        penalty += 8.0
    if max_weight == 0.0 and cash > 0.90:
        penalty += 6.0
    return clamp(penalty, upper=22.0)


def benchmark_lag_penalty_v3(row: dict[str, Any]) -> float:
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    active_vm_delta = to_float(row.get("active_vm_delta_180d_median"), active_combo_delta)
    active_dsr_delta = to_float(row.get("active_dsr_delta_180d_median"), active_combo_delta)
    penalty = 0.0
    for delta, scale, cap in ((active_combo_delta, 14.0, 14.0), (active_vm_delta, 22.0, 6.0), (active_dsr_delta, 22.0, 6.0)):
        if delta < 0:
            penalty += min(cap, abs(delta) / scale)
    return clamp(penalty, upper=24.0)


def return_drag_penalty_v3(row: dict[str, Any]) -> float:
    drag = max(0.0, to_float(row.get("return_drag_penalty")))
    return clamp(drag * 15.0, upper=22.0)


def duplicate_penalty_v3(row: dict[str, Any]) -> float:
    explicit = max(0.0, to_float(row.get("duplicate_penalty")))
    corr = abs(to_float(row.get("corr_vs_active_combo")))
    corr_penalty = max(0.0, corr - 0.78) / 0.22 * 28.0
    return clamp(max(explicit * 0.85, corr_penalty), upper=38.0)


def risk_integrity_score_v3(row: dict[str, Any]) -> float:
    max_drawdown = to_float(row.get("max_drawdown"))
    rolling_drawdown = to_float(row.get("180d_worst_drawdown"))
    risk_buffer = to_float(row.get("risk_buffer_vs_minus_600"))
    stop_hit_rate = to_float(row.get("stop_hit_rate"))
    gate = risk_gate_status_v3(row)
    buffer_component = logistic_score(risk_buffer, midpoint=-80.0, scale=360.0) * 0.34
    maxdd_component = logistic_score(max_drawdown, midpoint=-680.0, scale=260.0) * 0.24
    rolling_component = logistic_score(rolling_drawdown, midpoint=-500.0, scale=220.0) * 0.20
    stop_component = clamp(100.0 - stop_hit_rate * 100.0) * 0.12
    stability_component = logistic_score(to_float(row.get("sharpe")), midpoint=0.25, scale=0.85) * 0.10
    score = buffer_component + maxdd_component + rolling_component + stop_component + stability_component
    if bool_value(row.get("stop_risk_breach_flag")):
        score -= 12.0
    if gate == "fail":
        score = min(score, 34.0)
    elif gate == "hard_warn":
        score = min(score, 55.0)
    elif gate == "insufficient_evidence":
        score = min(score, 45.0)
    return clamp(score)


def practicality_score_v3(row: dict[str, Any]) -> float:
    turnover = to_float(row.get("avg_turnover"))
    trades = to_float(row.get("trade_count"))
    cash = to_float(row.get("avg_cash_allocation"))
    history = to_float(row.get("data_window_length"))
    score = 82.0
    score -= min(24.0, turnover * 70.0)
    score -= min(22.0, max(0.0, trades - 340.0) / 28.0)
    if trades < 3:
        score -= 15.0
    if cash > 0.92 and trades < 15:
        score -= 10.0
    if 0.0 < history < 500.0:
        score -= 12.0
    return clamp(score)


def overfit_risk_score_v3(row: dict[str, Any]) -> float:
    max_weight = to_float(row.get("max_symbol_weight"))
    history = to_float(row.get("data_window_length"))
    corr = abs(to_float(row.get("corr_vs_active_combo")))
    trades = to_float(row.get("trade_count"))
    family_id = str(row.get("family_id", ""))
    risk = 16.0
    risk += max(0.0, max_weight - 0.60) * 42.0
    risk += max(0.0, corr - 0.84) / 0.16 * 22.0
    if 0.0 < history < 500.0:
        risk += 14.0
    if trades < 3:
        risk += 8.0
    if family_id in {"trend_momentum", "volatility_regime"}:
        risk += 8.0
    return clamp(risk)


def stretch_diagnostic_score_v3(row: dict[str, Any]) -> float:
    target_300 = to_float(row.get("target_300_before_stop_rate"))
    target_400 = to_float(row.get("target_400_before_stop_rate"))
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    portfolio_improvement = to_float(row.get("portfolio_level_risk_adjusted_improvement"))
    return clamp(
        target_300 * 18.0
        + target_400 * 14.0
        + (10.0 if active_combo_delta > 0 else 0.0)
        + (10.0 if portfolio_improvement > 0 else 0.0)
    )


def exposure_quality_score_v3(row: dict[str, Any]) -> float:
    cash = to_float(row.get("avg_cash_allocation"))
    symbols = to_float(row.get("avg_symbols_held"))
    trades = to_float(row.get("trade_count"))
    exposure = 100.0 - cash * 65.0
    if symbols < 0.35:
        exposure -= 12.0
    if trades < 3:
        exposure -= 10.0
    return clamp(exposure)


def standalone_growth_score_v3(row: dict[str, Any]) -> float:
    median_progress = to_float(row.get("180d_median_final_equity"), STARTING_EQUITY) - STARTING_EQUITY
    ending_return = to_float(row.get("total_return"))
    sharpe = to_float(row.get("sharpe"))
    active_combo_delta = to_float(row.get("delta_vs_active_combo_180d_median"))
    risk = risk_integrity_score_v3(row)
    practical = practicality_score_v3(row)
    overfit = overfit_risk_score_v3(row)
    raw = (
        logistic_score(median_progress, midpoint=10.0, scale=125.0) * 0.24
        + logistic_score(ending_return, midpoint=0.02, scale=0.18) * 0.16
        + logistic_score(sharpe, midpoint=0.25, scale=0.85) * 0.14
        + logistic_score(active_combo_delta, midpoint=-65.0, scale=145.0) * 0.14
        + risk * 0.19
        + practical * 0.09
        + exposure_quality_score_v3(row) * 0.04
    )
    penalty = (
        cash_allocation_penalty_v3(row)
        + underinvestment_penalty_v3(row)
        + benchmark_lag_penalty_v3(row)
        + return_drag_penalty_v3(row) * 0.75
        + duplicate_penalty_v3(row) * 0.20
        + overfit * 0.07
    )
    score = raw - penalty
    gate = risk_gate_status_v3(row)
    if gate == "fail":
        score = min(score, 58.0)
    elif gate == "hard_warn":
        score = min(score, 68.0)
    elif gate == "insufficient_evidence":
        score = min(score, 55.0)
    if cash_allocation_penalty_v3(row) + underinvestment_penalty_v3(row) > 28.0:
        score = min(score, 66.0)
    if benchmark_lag_penalty_v3(row) > 20.0:
        score = min(score, 72.0)
    return clamp(score)


def portfolio_contribution_score_v3(row: dict[str, Any]) -> float:
    active_combo_improvement = to_float(row.get("active_combo_improvement"))
    active_pair_improvement = to_float(row.get("active_vm_dsr_pair_improvement"))
    return_risk_improvement = to_float(row.get("portfolio_return_risk_improvement"))
    drawdown_contribution = to_float(row.get("drawdown_contribution"))
    volatility_contribution = to_float(row.get("volatility_contribution"))
    corr_reduction = clamp(to_float(row.get("correlation_reduction")) * 100.0)
    risk = risk_integrity_score_v3(row)
    raw = (
        logistic_score(active_combo_improvement, midpoint=-8.0, scale=70.0) * 0.23
        + logistic_score(active_pair_improvement, midpoint=-8.0, scale=80.0) * 0.13
        + logistic_score(return_risk_improvement, midpoint=-0.02, scale=0.13) * 0.16
        + logistic_score(drawdown_contribution, midpoint=-50.0, scale=260.0) * 0.12
        + logistic_score(volatility_contribution, midpoint=-0.004, scale=0.018) * 0.08
        + corr_reduction * 0.13
        + risk * 0.10
        + practicality_score_v3(row) * 0.05
    )
    score = raw - return_drag_penalty_v3(row) * 0.75 - duplicate_penalty_v3(row) * 0.58 - overfit_risk_score_v3(row) * 0.05
    if duplicate_penalty_v3(row) > 25.0 and active_combo_improvement <= 0.0:
        score = min(score, 55.0)
    if return_drag_penalty_v3(row) > 16.0 and active_combo_improvement <= 0.0:
        score = min(score, 62.0)
    return clamp(score)


def score_row_v3(row: dict[str, Any], *, interpretation_status: str = "diagnostic_only") -> dict[str, Any]:
    if interpretation_status not in INTERPRETATION_STATUSES_V3:
        raise ValueError(f"invalid score interpretation status v3: {interpretation_status}")
    standalone = standalone_growth_score_v3(row)
    contribution = portfolio_contribution_score_v3(row)
    stretch = stretch_diagnostic_score_v3(row)
    risk = risk_integrity_score_v3(row)
    overfit = overfit_risk_score_v3(row)
    practicality = practicality_score_v3(row)
    return {
        "standalone_growth_score_v3": standalone,
        "portfolio_contribution_score_v3": contribution,
        "stretch_diagnostic_score_v3": stretch,
        "risk_integrity_score_v3": risk,
        "overfit_risk_score_v3": overfit,
        "practicality_score_v3": practicality,
        "cash_allocation_penalty_v3": cash_allocation_penalty_v3(row),
        "underinvestment_penalty_v3": underinvestment_penalty_v3(row),
        "benchmark_lag_penalty_v3": benchmark_lag_penalty_v3(row),
        "return_drag_penalty_v3": return_drag_penalty_v3(row),
        "duplicate_penalty_v3": duplicate_penalty_v3(row),
        "risk_gate_status_v3": risk_gate_status_v3(row),
        "score_saturation_flag_v3": standalone >= SATURATION_SCORE_THRESHOLD,
        "score_floor_collapse_flag_v3": standalone <= FLOOR_SCORE_THRESHOLD,
        "score_interpretation_status_v3": interpretation_status,
    }


def score_rows_v3(rows: list[dict[str, Any]], *, interpretation_status: str = "diagnostic_only") -> list[dict[str, Any]]:
    return [{**row, **score_row_v3(row, interpretation_status=interpretation_status)} for row in rows]


def calibration_report_v3(rows: list[dict[str, Any]], score_field: str = "standalone_growth_score_v3") -> dict[str, Any]:
    total = len(rows)
    standalone_scores = [to_float(row.get(score_field)) for row in rows]
    risk_scores = [to_float(row.get("risk_integrity_score_v3")) for row in rows]
    saturated = sum(1 for value in standalone_scores if value >= SATURATION_SCORE_THRESHOLD)
    floor = sum(1 for value in standalone_scores if value <= FLOOR_SCORE_THRESHOLD)
    risk_floor = sum(1 for value in risk_scores if value <= FLOOR_SCORE_THRESHOLD)
    median_standalone = sorted(standalone_scores)[total // 2] if total else 0.0
    median_risk = sorted(risk_scores)[total // 2] if total else 0.0
    max_standalone = max(standalone_scores, default=0.0)
    families = sorted({str(row.get("family_id", "")) for row in rows})
    family_median_risk_zero_count = 0
    for family_id in families:
        group = sorted(to_float(row.get("risk_integrity_score_v3")) for row in rows if row.get("family_id") == family_id)
        if group and group[len(group) // 2] == 0.0:
            family_median_risk_zero_count += 1
    return {
        "score_field": score_field,
        "row_count": total,
        "saturation_threshold": SATURATION_SCORE_THRESHOLD,
        "floor_threshold": FLOOR_SCORE_THRESHOLD,
        "standalone_saturated_count": saturated,
        "standalone_saturated_ratio": saturated / total if total else 0.0,
        "standalone_floor_count": floor,
        "standalone_floor_ratio": floor / total if total else 0.0,
        "standalone_saturation_failed": (saturated / total if total else 1.0) > STANDALONE_SATURATION_FAIL_RATIO,
        "standalone_floor_collapse_failed": (floor / total if total else 1.0) > STANDALONE_FLOOR_FAIL_RATIO,
        "standalone_max_warning": max_standalone < 45.0,
        "standalone_median_low_warning": median_standalone < 10.0,
        "standalone_median_high_warning": median_standalone > 80.0,
        "standalone_max": max_standalone,
        "standalone_median": median_standalone,
        "risk_floor_count": risk_floor,
        "risk_floor_ratio": risk_floor / total if total else 0.0,
        "risk_floor_collapse_warning": (risk_floor / total if total else 1.0) > RISK_FLOOR_WARNING_RATIO,
        "risk_median": median_risk,
        "risk_median_zero_warning": median_risk == 0.0,
        "all_family_median_risk_zero_failed": bool(families) and family_median_risk_zero_count == len(families),
    }
