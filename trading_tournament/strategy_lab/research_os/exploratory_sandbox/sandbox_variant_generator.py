from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .sandbox_config import (
    MAX_FAMILIES_PER_RUN,
    MAX_PARAMETER_CHOICES_PER_INDICATOR,
    MAX_PORTFOLIO_COMBINATION_VARIANTS,
    MAX_TOTAL_FUTURE_VARIANTS,
    MAX_UNIVERSE_GROUPS_PER_RUN,
    MAX_VARIANTS_PER_FAMILY,
)
from .sandbox_data_preflight import preflight_universe_availability
from .sandbox_families import ALLOWED_FAMILIES
from .sandbox_indicators import validate_indicator_concept
from .sandbox_schema import VariantSpec, validate_variant_spec


PARAMETER_SETS_BY_INDICATOR: dict[str, tuple[dict[str, Any], ...]] = {
    "sma": ({"lookback": 50}, {"lookback": 100}),
    "ema": ({"lookback": 34}, {"lookback": 89}),
    "atr": ({"lookback": 14, "state": "normal"}, {"lookback": 21, "state": "elevated"}),
    "rsi": ({"lookback": 7, "band": "low"}, {"lookback": 14, "band": "low"}),
    "bollinger_bands": ({"lookback": 20, "band_width": 2.0}, {"lookback": 40, "band_width": 2.0}),
    "realized_volatility": ({"lookback": 20}, {"lookback": 63}),
    "roc_rolling_return": ({"lookback": 63}, {"lookback": 126}),
    "donchian_prior_high": ({"lookback": 55}, {"lookback": 100}),
    "volume_sma_filter_alignment": ({"lookback": 20}, {"lookback": 50}),
    "rolling_percentile_rank": ({"lookback": 63}, {"lookback": 126}),
    "moving_average_regime": ({"fast": 50, "slow": 200}, {"fast": 100, "slow": 200}),
    "spy_regime_features": ({"regime": "spy_200d"}, {"regime": "spy_drawdown_state"}),
}


def parameter_sets_for_indicator(indicator_id: str) -> tuple[dict[str, Any], ...]:
    validate_indicator_concept(indicator_id)
    values = PARAMETER_SETS_BY_INDICATOR[indicator_id]
    if len(values) > MAX_PARAMETER_CHOICES_PER_INDICATOR:
        raise ValueError(f"too many parameter choices for indicator: {indicator_id}")
    return values


def available_symbols_by_group(root: Path) -> dict[str, tuple[str, ...]]:
    rows = preflight_universe_availability(root)
    return {
        str(row["universe_group"]): tuple(row["symbols_found"])
        for row in rows
        if row["eligible_for_future_sandbox_run"]
    }


def _selected_family_ids(selected_families: tuple[str, ...] | None) -> tuple[str, ...]:
    family_ids = selected_families or tuple(ALLOWED_FAMILIES)
    if len(family_ids) > MAX_FAMILIES_PER_RUN:
        raise ValueError("selected family count exceeds sandbox limit")
    unknown = [family_id for family_id in family_ids if family_id not in ALLOWED_FAMILIES]
    if unknown:
        raise ValueError(f"unknown sandbox families: {unknown}")
    return family_ids


def _selected_universe_ids(selected_universe_groups: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if selected_universe_groups and len(selected_universe_groups) > MAX_UNIVERSE_GROUPS_PER_RUN:
        raise ValueError("selected universe-group count exceeds sandbox limit")
    return selected_universe_groups


def generate_variant_plan(
    root: Path,
    *,
    max_variants: int = MAX_TOTAL_FUTURE_VARIANTS,
    selected_families: tuple[str, ...] | None = None,
    selected_universe_groups: tuple[str, ...] | None = None,
    dry_run: bool = True,
) -> list[VariantSpec]:
    if not dry_run:
        raise ValueError("only dry-run variant planning is implemented; sandbox search is not authorized")
    if max_variants <= 0 or max_variants > MAX_TOTAL_FUTURE_VARIANTS:
        raise ValueError("max_variants must be between 1 and the preregistered total limit")

    family_ids = _selected_family_ids(selected_families)
    requested_universe_ids = _selected_universe_ids(selected_universe_groups)
    symbols_by_group = available_symbols_by_group(root)
    plan: list[VariantSpec] = []

    for family_id in family_ids:
        family = ALLOWED_FAMILIES[family_id]
        family_rows = 0
        candidate_universes = [
            group_id
            for group_id in family.allowed_universe_groups
            if group_id in symbols_by_group and (requested_universe_ids is None or group_id in requested_universe_ids)
        ]
        for universe_group in candidate_universes[:3]:
            for indicator_id in family.allowed_indicators[:2]:
                for index, parameter_set in enumerate(parameter_sets_for_indicator(indicator_id)[:2], start=1):
                    if len(plan) >= max_variants:
                        validate_plan_limits(plan, max_variants=max_variants)
                        return plan
                    if family_rows >= MAX_VARIANTS_PER_FAMILY:
                        break
                    variant = VariantSpec(
                        variant_id=f"es_{family_id}_{universe_group}_{indicator_id}_{index:02d}",
                        family_id=family_id,
                        universe_group=universe_group,
                        symbols=symbols_by_group[universe_group][:4],
                        indicator_concept=indicator_id,
                        parameter_set=parameter_set,
                        holding_period_type="daily_close_to_daily_close",
                        rebalance_frequency="predefined_weekly_or_monthly",
                    )
                    plan.append(validate_variant_spec(variant))
                    family_rows += 1
    validate_plan_limits(plan, max_variants=max_variants)
    return plan


def validate_plan_limits(plan: list[VariantSpec], *, max_variants: int = MAX_TOTAL_FUTURE_VARIANTS) -> bool:
    if len(plan) > max_variants or len(plan) > MAX_TOTAL_FUTURE_VARIANTS:
        raise ValueError("variant plan exceeds total variant limit")
    family_counts = Counter(item.family_id for item in plan)
    if len(family_counts) > MAX_FAMILIES_PER_RUN:
        raise ValueError("variant plan exceeds family-count limit")
    if any(count > MAX_VARIANTS_PER_FAMILY for count in family_counts.values()):
        raise ValueError("variant plan exceeds per-family variant limit")
    universe_count = len({item.universe_group for item in plan})
    if universe_count > MAX_UNIVERSE_GROUPS_PER_RUN:
        raise ValueError("variant plan exceeds universe-group limit")
    portfolio_count = family_counts.get("portfolio_combination_sleeve_ensemble", 0)
    if portfolio_count > MAX_PORTFOLIO_COMBINATION_VARIANTS:
        raise ValueError("portfolio-combination variants exceed sandbox limit")
    parameter_sets_by_indicator: dict[str, set[str]] = defaultdict(set)
    for item in plan:
        validate_variant_spec(item)
        parameter_sets_by_indicator[item.indicator_concept].add(repr(sorted(item.parameter_set.items())))
    if any(len(values) > MAX_PARAMETER_CHOICES_PER_INDICATOR for values in parameter_sets_by_indicator.values()):
        raise ValueError("variant plan exceeds parameter-choice limit")
    return True
