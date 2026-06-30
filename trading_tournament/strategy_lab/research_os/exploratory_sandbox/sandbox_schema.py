from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .sandbox_config import EXACT_REJECTED_VARIANT_IDS, INITIAL_SANDBOX_STATUS
from .sandbox_families import ALLOWED_FAMILIES
from .sandbox_indicators import validate_indicator_concept
from .sandbox_leverage_policy import validate_leverage_policy
from .sandbox_status_taxonomy import assert_status_allowed
from .sandbox_universes import UNIVERSE_GROUPS


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    family_id: str
    universe_group: str
    symbols: tuple[str, ...]
    indicator_concept: str
    parameter_set: dict[str, Any]
    holding_period_type: str
    rebalance_frequency: str
    leverage_policy: str = "1.0x_research_only_non_promotable"
    notes: str = "dry-run specification only; no strategy result"
    sandbox_status_initial: str = INITIAL_SANDBOX_STATUS
    status: str = INITIAL_SANDBOX_STATUS
    promotable: bool = False
    paper_candidate_allowed: bool = False
    uses_intraday_data: bool = False
    provider_download_required: bool = False
    broker_live_path_required: bool = False
    direct_futures_options_forex_crypto: bool = False
    leverage_as_promotion_mechanism: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, str]:
        return {
            "variant_id": self.variant_id,
            "family_id": self.family_id,
            "universe_group": self.universe_group,
            "symbols": ",".join(self.symbols),
            "indicator_concept": self.indicator_concept,
            "parameter_set": json.dumps(self.parameter_set, sort_keys=True),
            "holding_period_type": self.holding_period_type,
            "rebalance_frequency": self.rebalance_frequency,
            "sandbox_status_initial": self.sandbox_status_initial,
            "status": self.status,
            "promotable": str(self.promotable).lower(),
            "paper_candidate_allowed": str(self.paper_candidate_allowed).lower(),
            "leverage_policy": self.leverage_policy,
            "notes": self.notes,
        }


def validate_variant_spec(
    spec: VariantSpec,
    *,
    exact_rejected_variant_ids: tuple[str, ...] = EXACT_REJECTED_VARIANT_IDS,
) -> VariantSpec:
    if spec.variant_id in exact_rejected_variant_ids:
        raise ValueError(f"exact rejected variant cannot be reopened: {spec.variant_id}")
    if spec.family_id not in ALLOWED_FAMILIES:
        raise ValueError(f"unknown sandbox family: {spec.family_id}")
    if spec.universe_group not in UNIVERSE_GROUPS:
        raise ValueError(f"unknown sandbox universe group: {spec.universe_group}")
    if not spec.symbols:
        raise ValueError(f"variant has no locally available symbols: {spec.variant_id}")
    validate_indicator_concept(spec.indicator_concept)
    assert_status_allowed(spec.sandbox_status_initial)
    assert_status_allowed(spec.status)
    validate_leverage_policy(spec.leverage_policy)
    if spec.promotable:
        raise ValueError(f"sandbox variant cannot be promotable: {spec.variant_id}")
    if spec.paper_candidate_allowed:
        raise ValueError(f"sandbox variant cannot create paper candidates: {spec.variant_id}")
    if spec.uses_intraday_data:
        raise ValueError(f"intraday data is blocked for sandbox variant: {spec.variant_id}")
    if spec.provider_download_required:
        raise ValueError(f"provider download is blocked for sandbox variant: {spec.variant_id}")
    if spec.broker_live_path_required:
        raise ValueError(f"broker/live path is blocked for sandbox variant: {spec.variant_id}")
    if spec.direct_futures_options_forex_crypto:
        raise ValueError(f"direct futures/options/forex/crypto are blocked: {spec.variant_id}")
    if spec.leverage_as_promotion_mechanism:
        raise ValueError(f"leverage cannot be a promotion mechanism: {spec.variant_id}")
    return spec


def variant_schema_report() -> str:
    return """# Sandbox Variant Schema

Required dry-run fields:

- `variant_id`
- `family_id`
- `universe_group`
- `symbols`
- `indicator_concept`
- `parameter_set`
- `holding_period_type`
- `rebalance_frequency`
- `sandbox_status_initial`
- `status`
- `promotable`
- `paper_candidate_allowed`
- `leverage_policy`
- `notes`

Required values for every generated variant:

- `sandbox_status_initial`: `non_promotable_exploration`
- `status`: `non_promotable_exploration`
- `promotable`: `false`
- `paper_candidate_allowed`: `false`

The schema rejects forbidden statuses, forbidden indicators, provider-download requirements, intraday data, broker/live paths, exact rejected variant IDs, and leverage as a promotion mechanism.
"""
