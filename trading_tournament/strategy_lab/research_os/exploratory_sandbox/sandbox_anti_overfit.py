from __future__ import annotations

from .sandbox_schema import VariantSpec


ANTI_OVERFITTING_CONTROLS = (
    "Best single variant cannot be promoted.",
    "Parameter-grid winner cannot be promoted.",
    "Only family-level robustness can lead to future preregistration.",
    "Exact rejected variants cannot be reopened.",
    "Indicators cannot be added to rescue failed rows.",
    "Risk gates cannot be weakened because sandbox finds weak returns.",
    "Same-window benchmarks required for future sandbox execution.",
    "Costs/slippage stress required for future sandbox execution.",
    "Portfolio-combination results must distinguish contribution from standalone alpha.",
    "Leverage sensitivity cannot authorize leverage use.",
)


def assert_plan_non_promotable(plan: list[VariantSpec]) -> bool:
    for variant in plan:
        if variant.promotable or variant.paper_candidate_allowed:
            raise ValueError(f"variant is not sandbox-safe: {variant.variant_id}")
    return True


def anti_overfitting_report() -> str:
    lines = [
        "# Sandbox Anti-Overfitting Controls",
        "",
        "The sandbox builds an opportunity map only. It cannot promote a row by itself.",
        "",
    ]
    lines.extend(f"- {control}" for control in ANTI_OVERFITTING_CONTROLS)
    return "\n".join(lines)
