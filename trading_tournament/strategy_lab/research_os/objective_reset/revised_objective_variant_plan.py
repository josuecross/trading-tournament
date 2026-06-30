from __future__ import annotations

from collections import Counter, defaultdict
from itertools import cycle
from typing import Any

from .revised_objective_batch_config import (
    BATCH_ID,
    FAMILY_DEFINITIONS,
    INCLUDED_FAMILIES,
    INITIAL_STATUS,
    MAX_FAMILIES,
    MAX_PARAMETER_CHOICES_PER_INDICATOR,
    MAX_PORTFOLIO_COMBINATION_VARIANTS,
    MAX_TOTAL_VARIANTS,
    MAX_VARIANTS_PER_FAMILY,
    OLD_DOLLAR_TARGET_IS_HARD_GATE,
    PAPER_CANDIDATES_CAN_BE_CREATED,
    SANDBOX_RESULTS_CAN_PROMOTE,
    STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
    assert_status_allowed,
)


def generate_dry_run_variant_plan(*, batch_id: str = BATCH_ID, max_variants: int = MAX_TOTAL_VARIANTS) -> list[dict[str, Any]]:
    if batch_id != BATCH_ID:
        raise ValueError(f"unexpected revised-objective batch id: {batch_id}")
    if max_variants <= 0 or max_variants > MAX_TOTAL_VARIANTS:
        raise ValueError("max_variants must be between 1 and the preregistered total limit")

    rows: list[dict[str, Any]] = []
    for family_id in INCLUDED_FAMILIES:
        family = FAMILY_DEFINITIONS[family_id]
        universe_cycle = cycle(family.universe_groups)
        indicator_cycle = cycle(family.indicator_concepts)
        role_cycle = cycle(family.variant_roles)
        for index in range(1, family.planned_variant_cap + 1):
            indicator = next(indicator_cycle)
            row = {
                "variant_id": f"ro_{family_id}_{index:02d}",
                "batch_id": batch_id,
                "family_id": family_id,
                "objective_lane": family.objective_lane,
                "variant_role": next(role_cycle),
                "universe_group": next(universe_cycle),
                "indicator_concepts": indicator,
                "parameter_profile": f"{indicator}_profile_{((index - 1) % MAX_PARAMETER_CHOICES_PER_INDICATOR) + 1}",
                "research_question": family.purpose,
                "batch_001_lesson": family.batch_001_lesson,
                "implementation_requirement": family.implementation_requirement,
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "status": INITIAL_STATUS,
                "old_dollar_target_is_hard_gate": str(OLD_DOLLAR_TARGET_IS_HARD_GATE).lower(),
                "stretch_diagnostics_are_promotion_gates": str(STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES).lower(),
                "standalone_growth_score_enabled": str(family.objective_lane == "standalone_growth").lower(),
                "portfolio_contribution_score_enabled": str(family.objective_lane == "portfolio_contribution_sleeve").lower(),
                "stretch_diagnostic_score_enabled": "true",
                "risk_integrity_score_enabled": "true",
                "overfit_risk_score_enabled": "true",
                "practicality_score_enabled": "true",
                "sandbox_results_can_promote": str(SANDBOX_RESULTS_CAN_PROMOTE).lower(),
                "paper_candidates_can_be_created": str(PAPER_CANDIDATES_CAN_BE_CREATED).lower(),
            }
            rows.append(row)
    validate_variant_plan(rows, batch_id=batch_id, max_variants=max_variants)
    return rows


def validate_variant_plan(rows: list[dict[str, Any]], *, batch_id: str = BATCH_ID, max_variants: int = MAX_TOTAL_VARIANTS) -> bool:
    if len(rows) > max_variants or len(rows) > MAX_TOTAL_VARIANTS:
        raise ValueError("revised-objective variant plan exceeds total variant limit")
    family_counts = Counter(str(row.get("family_id", "")) for row in rows)
    if len(family_counts) > MAX_FAMILIES:
        raise ValueError("revised-objective variant plan exceeds family-count limit")
    if any(count > MAX_VARIANTS_PER_FAMILY for count in family_counts.values()):
        raise ValueError("revised-objective variant plan exceeds per-family variant limit")
    if family_counts.get("portfolio_combination_sleeve_ensemble", 0) > MAX_PORTFOLIO_COMBINATION_VARIANTS:
        raise ValueError("portfolio-combination variants exceed revised-objective limit")

    parameter_profiles_by_indicator: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("batch_id") != batch_id:
            raise ValueError("variant row has wrong revised-objective batch id")
        if row.get("family_id") not in INCLUDED_FAMILIES:
            raise ValueError(f"variant row uses non-preregistered family: {row.get('family_id')}")
        if row.get("promotable") != "false":
            raise ValueError(f"variant row is promotable: {row.get('variant_id')}")
        if row.get("paper_candidate_allowed") != "false":
            raise ValueError(f"variant row can create paper candidate: {row.get('variant_id')}")
        assert_status_allowed(str(row.get("status", "")))
        if row.get("status") != INITIAL_STATUS:
            raise ValueError(f"variant row is not initial non-promotable status: {row.get('variant_id')}")
        if row.get("old_dollar_target_is_hard_gate") != "false":
            raise ValueError("old dollar target was incorrectly encoded as a hard gate")
        if row.get("stretch_diagnostics_are_promotion_gates") != "false":
            raise ValueError("stretch diagnostics were incorrectly encoded as promotion gates")
        indicator = str(row.get("indicator_concepts", ""))
        parameter_profiles_by_indicator[indicator].add(str(row.get("parameter_profile", "")))

    if any(len(values) > MAX_PARAMETER_CHOICES_PER_INDICATOR for values in parameter_profiles_by_indicator.values()):
        raise ValueError("variant plan exceeds parameter-choice limit")
    return True


def fieldnames() -> list[str]:
    return [
        "variant_id",
        "batch_id",
        "family_id",
        "objective_lane",
        "variant_role",
        "universe_group",
        "indicator_concepts",
        "parameter_profile",
        "research_question",
        "batch_001_lesson",
        "implementation_requirement",
        "promotable",
        "paper_candidate_allowed",
        "status",
        "old_dollar_target_is_hard_gate",
        "stretch_diagnostics_are_promotion_gates",
        "standalone_growth_score_enabled",
        "portfolio_contribution_score_enabled",
        "stretch_diagnostic_score_enabled",
        "risk_integrity_score_enabled",
        "overfit_risk_score_enabled",
        "practicality_score_enabled",
        "sandbox_results_can_promote",
        "paper_candidates_can_be_created",
    ]
