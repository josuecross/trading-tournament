from __future__ import annotations


PORTFOLIO_CONTRIBUTION_FIELDS = (
    "portfolio_final_equity_impact_vs_active_vm_dsr_pair",
    "portfolio_drawdown_impact",
    "portfolio_volatility_impact",
    "correlation_to_active_combo",
    "return_drag_vs_active_combo",
    "risk_adjusted_outcome_delta",
    "contribution_vs_static_all_weather_control",
    "duplicate_penalty_for_high_active_combo_correlation",
)

STRETCH_DIAGNOSTIC_FIELDS = (
    "target_300_hit_rate_before_stop",
    "target_400_hit_rate_before_stop",
    "active_combo_beat_rate_same_window",
    "portfolio_level_risk_adjusted_return_improvement",
)


def portfolio_contribution_schema_report() -> str:
    fields = "\n".join(f"- `{field}`" for field in PORTFOLIO_CONTRIBUTION_FIELDS)
    return f"""# Portfolio Contribution Schema

Structure only. Future execution may populate these fields, but this implementation does not compute them.

{fields}

High active-combo correlation is a duplicate-risk penalty, not diversification evidence.
"""


def stretch_diagnostic_schema_report() -> str:
    fields = "\n".join(f"- `{field}`" for field in STRETCH_DIAGNOSTIC_FIELDS)
    return f"""# Stretch Diagnostic Schema

Structure only. These fields are evidence diagnostics, never direct promotion gates.

{fields}

`$300` and `$400` hits cannot override risk, overfit, benchmark, duplicate, or governance gates.
"""
