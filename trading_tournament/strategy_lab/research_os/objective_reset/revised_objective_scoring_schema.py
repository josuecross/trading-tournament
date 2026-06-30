from __future__ import annotations


SCORING_SCHEMAS: dict[str, tuple[str, ...]] = {
    "standalone_growth_score": (
        "180_day_median_progress",
        "risk_adjusted_growth",
        "benchmark_relevance",
        "active_reference_relevance",
        "drawdown_control",
        "slippage_stress_resilience",
        "duplicate_avoidance",
    ),
    "portfolio_contribution_score": (
        "active_vm_dsr_portfolio_return_risk_improvement",
        "active_combo_improvement",
        "correlation_reduction",
        "drawdown_contribution",
        "volatility_contribution",
        "return_drag_penalty",
        "contribution_vs_static_all_weather_control",
    ),
    "stretch_diagnostic_score": (
        "target_300_hit_rate",
        "target_400_hit_rate",
        "active_combo_beat_rate",
        "portfolio_level_risk_adjusted_improvement",
    ),
    "risk_integrity_score": (
        "max_drawdown",
        "worst_180_day_drawdown",
        "risk_buffer",
        "stress_slippage_result",
        "downside_concentration",
        "stop_risk_breach_flags",
    ),
    "overfit_risk_score": (
        "parameter_sensitivity",
        "single_symbol_dependence",
        "limited_history_warning",
        "family_robustness",
        "best_row_dependence",
    ),
    "practicality_score": (
        "turnover",
        "trade_count",
        "holding_period",
        "rule_simplicity",
        "data_quality",
        "implementation_simplicity",
    ),
}


def schema_markdown(score_name: str) -> str:
    fields = SCORING_SCHEMAS[score_name]
    bullets = "\n".join(f"- `{field}`" for field in fields)
    return f"""# {score_name}

Structure only. This implementation defines future inputs but does not compute performance metrics.

Inputs:

{bullets}
"""


def revised_scoring_schema_report() -> str:
    sections = ["# Revised Scoring Schema", ""]
    for score_name, fields in SCORING_SCHEMAS.items():
        sections.append(f"## `{score_name}`")
        sections.append("")
        sections.extend(f"- `{field}`" for field in fields)
        sections.append("")
    sections.append("`stretch_diagnostic_score` is diagnostic only and can never directly create a promotion candidate.")
    return "\n".join(sections)
