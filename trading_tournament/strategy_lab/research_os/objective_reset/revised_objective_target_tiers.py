from __future__ import annotations

from .revised_objective_batch_config import (
    OLD_DOLLAR_TARGET_IS_HARD_GATE,
    STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
)


TARGET_TIER_MAPPING = {
    "core_diagnostics": (
        "positive_180_day_median_progress",
        "controlled_max_drawdown",
        "survives_slippage_stress_review",
        "not_dominated_by_active_references",
        "not_duplicate_of_active_combo",
        "stable_across_neighboring_parameters_or_related_concepts",
        "sufficient_data_history_quality",
        "simple_enough_rules_and_turnover",
    ),
    "realistic_expectation_bands": (
        "monthly_evidence_of_positive_expectancy_or_contribution",
        "180_day_median_final_equity_above_starting_capital",
        "meaningful_risk_adjusted_progress",
        "no_unacceptable_downside_concentration",
    ),
    "stretch_diagnostics": (
        "reaches_300_before_stop",
        "reaches_400_before_stop",
        "beats_active_combo",
        "improves_portfolio_level_risk_adjusted_return",
    ),
}


def target_tier_mapping_report() -> str:
    sections = [
        "# Target Tier Mapping",
        "",
        f"- `old_dollar_target_is_hard_gate`: `{OLD_DOLLAR_TARGET_IS_HARD_GATE}`",
        f"- `stretch_diagnostics_are_promotion_gates`: `{STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES}`",
        "",
    ]
    for tier, fields in TARGET_TIER_MAPPING.items():
        sections.append(f"## `{tier}`")
        sections.append("")
        sections.extend(f"- `{field}`" for field in fields)
        sections.append("")
    sections.append("Stretch diagnostics are recorded only as evidence, never gates.")
    return "\n".join(sections)
