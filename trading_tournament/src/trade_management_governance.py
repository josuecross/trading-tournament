from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .overlays import stable_hash


PURPOSE_IDS = {
    "execution_efficiency",
    "position_sizing",
    "position_loss_control",
    "winner_exit_management",
    "portfolio_risk_control",
    "lifecycle_management",
    "complete_portfolio_insurance",
    "mechanical_control",
}

ATOMIC_OR_HOLISTIC_VALUES = {
    "atomic_primitive",
    "holistic_source_system",
    "mechanical_control",
    "legacy_composite",
}

SOURCE_STATUS_VALUES = {
    "source_defined",
    "project_defined",
    "mechanical_control",
    "legacy_only",
}

MANAGEMENT_ROLE_SOURCE_DEFINED_BASE = "source_defined_base_management"
MANAGEMENT_ROLE_OPTIONAL_OVERLAY = "optional_management_overlay"
MANAGEMENT_ROLE_ATTRIBUTION_CONTROL = "attribution_control"
MANAGEMENT_ROLE_VALUES = {
    MANAGEMENT_ROLE_SOURCE_DEFINED_BASE,
    MANAGEMENT_ROLE_OPTIONAL_OVERLAY,
    MANAGEMENT_ROLE_ATTRIBUTION_CONTROL,
}

DIAGNOSED_WEAKNESS_CODES = {
    "EXCESS_SMALL_ORDERS",
    "REDUNDANT_REALLOCATION",
    "EXCESS_ASSET_CONCENTRATION",
    "EXCESS_GROSS_EXPOSURE",
    "UNSTABLE_POSITION_SIZE",
    "LARGE_POSITION_TAIL_LOSS",
    "STALE_POSITION_BEYOND_SOURCE_HORIZON",
    "WINNER_EXIT_PROBLEM",
    "REENTRY_CHURN",
    "CORRELATED_GROUP_CONCENTRATION",
    "SOURCE_DEFINED_MANAGEMENT_REPLICATION",
}

FAILURE_CODES = {
    "NO_DIAGNOSED_MANAGEMENT_NEED",
    "OVERLAY_PURPOSE_MISMATCH",
    "UNSUPPORTED_INTENT_KIND",
    "CONFLICTING_BASE_LIFECYCLE",
    "MISSING_REQUIRED_DATA",
    "MULTIPLE_OPTIONAL_OVERLAYS_NOT_AUTHORIZED",
    "HOLISTIC_SYSTEM_COMBINATION_NOT_AUTHORIZED",
    "LEGACY_COMPOSITE_NEW_RESEARCH_FORBIDDEN",
}

WEAKNESS_PURPOSE_MAP: dict[str, set[str]] = {
    "EXCESS_SMALL_ORDERS": {"execution_efficiency"},
    "REDUNDANT_REALLOCATION": {"execution_efficiency"},
    "EXCESS_ASSET_CONCENTRATION": {"portfolio_risk_control"},
    "EXCESS_GROSS_EXPOSURE": {"portfolio_risk_control"},
    "UNSTABLE_POSITION_SIZE": {"position_sizing"},
    "LARGE_POSITION_TAIL_LOSS": {"position_loss_control", "portfolio_risk_control"},
    "STALE_POSITION_BEYOND_SOURCE_HORIZON": {"lifecycle_management"},
    "WINNER_EXIT_PROBLEM": {"winner_exit_management"},
    "REENTRY_CHURN": {"execution_efficiency", "lifecycle_management"},
    "CORRELATED_GROUP_CONCENTRATION": {"portfolio_risk_control"},
    "SOURCE_DEFINED_MANAGEMENT_REPLICATION": {"complete_portfolio_insurance"},
}

REQUIRED_PLAN_FIELDS = (
    "experiment_id",
    "base_strategy_id",
    "base_strategy_hash",
    "base_stage",
    "source_management_included",
    "diagnosed_weakness",
    "weakness_evidence_reference",
    "selected_overlay_id",
    "overlay_purpose_id",
    "compatibility_reason",
    "negative_or_attribution_control",
    "parameters",
    "adaptation_label",
    "research_stage",
    "authorized_overlay_count",
)

STRUCTURAL_COMPATIBILITY_FIELDS = (
    "strategy_id",
    "strategy_family",
    "intent_kind",
    "source_defined_lifecycle_features",
    "overlay_id",
    "purpose",
    "intent_compatibility",
    "lifecycle_compatibility",
    "data_compatibility",
    "final_applicability",
    "reason_code",
)

PERFORMANCE_FIELD_NAMES = {
    "return",
    "total_return",
    "annualized_return",
    "annualized_volatility",
    "max_drawdown",
    "max_drawdown_pct",
    "drawdown",
    "sharpe",
    "sortino",
    "cagr",
    "final_equity",
    "equity",
    "promotion_status",
    "registry_score",
    "score",
}

CAP_BINDING_REASON_CODES = {
    "exposure_cap",
    "gross_exposure_cap",
    "asset_exposure_cap",
    "group_exposure_cap",
}


@dataclass(frozen=True)
class OverlayTaxonomyRecord:
    overlay_id: str
    overlay_version: str
    purpose_id: str
    atomic_or_holistic: str
    source_status: str
    supported_intent_kinds: tuple[str, ...]
    required_data: tuple[str, ...] = ()
    required_lifecycle_state: tuple[str, ...] = ()
    incompatible_base_features: tuple[str, ...] = ()
    parameter_mapping: Mapping[str, Any] = field(default_factory=dict)
    parameter_hash: str = ""
    default_research_status: str = ""
    applicability_reason_codes: tuple[str, ...] = ()
    management_role: str = MANAGEMENT_ROLE_OPTIONAL_OVERLAY

    def __post_init__(self) -> None:
        if self.purpose_id not in PURPOSE_IDS:
            raise ValueError(f"unknown purpose_id: {self.purpose_id}")
        if self.atomic_or_holistic not in ATOMIC_OR_HOLISTIC_VALUES:
            raise ValueError(f"unknown atomic_or_holistic: {self.atomic_or_holistic}")
        if self.source_status not in SOURCE_STATUS_VALUES:
            raise ValueError(f"unknown source_status: {self.source_status}")
        if self.management_role not in MANAGEMENT_ROLE_VALUES:
            raise ValueError(f"unknown management_role: {self.management_role}")
        if not self.parameter_hash:
            object.__setattr__(self, "parameter_hash", stable_hash(dict(self.parameter_mapping)))

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "overlay_id": self.overlay_id,
            "overlay_version": self.overlay_version,
            "purpose_id": self.purpose_id,
            "atomic_or_holistic": self.atomic_or_holistic,
            "source_status": self.source_status,
            "supported_intent_kinds": "|".join(self.supported_intent_kinds),
            "required_data": "|".join(self.required_data),
            "required_lifecycle_state": "|".join(self.required_lifecycle_state),
            "incompatible_base_features": "|".join(self.incompatible_base_features),
            "parameter_mapping": json.dumps(dict(self.parameter_mapping), sort_keys=True),
            "parameter_hash": self.parameter_hash,
            "default_research_status": self.default_research_status,
            "applicability_reason_codes": "|".join(self.applicability_reason_codes),
            "management_role": self.management_role,
        }


@dataclass(frozen=True)
class ManagementExperimentPlan:
    experiment_id: str
    base_strategy_id: str
    base_strategy_hash: str
    base_stage: str
    source_management_included: bool
    diagnosed_weakness: str
    weakness_evidence_reference: str
    selected_overlay_id: str
    overlay_purpose_id: str
    compatibility_reason: str
    negative_or_attribution_control: str
    parameters: Mapping[str, Any]
    adaptation_label: str
    research_stage: str
    authorized_overlay_count: int
    base_intent_kind: str = ""
    available_data: tuple[str, ...] = ()
    base_lifecycle_features: tuple[str, ...] = ()
    optional_overlay_ids: tuple[str, ...] = ()
    combination_experiment_id: str = ""
    combination_authorized: bool = False
    management_role: str = MANAGEMENT_ROLE_OPTIONAL_OVERLAY

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "base_strategy_id": self.base_strategy_id,
            "base_strategy_hash": self.base_strategy_hash,
            "base_stage": self.base_stage,
            "source_management_included": self.source_management_included,
            "diagnosed_weakness": self.diagnosed_weakness,
            "weakness_evidence_reference": self.weakness_evidence_reference,
            "selected_overlay_id": self.selected_overlay_id,
            "overlay_purpose_id": self.overlay_purpose_id,
            "compatibility_reason": self.compatibility_reason,
            "negative_or_attribution_control": self.negative_or_attribution_control,
            "parameters": dict(self.parameters),
            "adaptation_label": self.adaptation_label,
            "research_stage": self.research_stage,
            "authorized_overlay_count": self.authorized_overlay_count,
            "base_intent_kind": self.base_intent_kind,
            "available_data": list(self.available_data),
            "base_lifecycle_features": list(self.base_lifecycle_features),
            "optional_overlay_ids": list(self.optional_overlay_ids),
            "combination_experiment_id": self.combination_experiment_id,
            "combination_authorized": self.combination_authorized,
            "management_role": self.management_role,
        }


@dataclass(frozen=True)
class ManagementValidationIssue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


@dataclass(frozen=True)
class ManagementPlanValidation:
    authorized: bool
    failure_codes: tuple[str, ...]
    issues: tuple[ManagementValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "failure_codes": list(self.failure_codes),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _tuple(values: Iterable[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _record(
    overlay_id: str,
    purpose_id: str,
    atomic_or_holistic: str,
    source_status: str,
    supported_intent_kinds: Iterable[str],
    *,
    parameter_mapping: Mapping[str, Any] | None = None,
    required_data: Iterable[str] = (),
    required_lifecycle_state: Iterable[str] = (),
    incompatible_base_features: Iterable[str] = (),
    default_research_status: str,
    applicability_reason_codes: Iterable[str],
    management_role: str = MANAGEMENT_ROLE_OPTIONAL_OVERLAY,
) -> OverlayTaxonomyRecord:
    return OverlayTaxonomyRecord(
        overlay_id=overlay_id,
        overlay_version="v1",
        purpose_id=purpose_id,
        atomic_or_holistic=atomic_or_holistic,
        source_status=source_status,
        supported_intent_kinds=tuple(supported_intent_kinds),
        required_data=tuple(required_data),
        required_lifecycle_state=tuple(required_lifecycle_state),
        incompatible_base_features=tuple(incompatible_base_features),
        parameter_mapping=dict(parameter_mapping or {}),
        default_research_status=default_research_status,
        applicability_reason_codes=tuple(applicability_reason_codes),
        management_role=management_role,
    )


OVERLAY_TAXONOMY: tuple[OverlayTaxonomyRecord, ...] = (
    _record(
        "IDENTITY",
        "mechanical_control",
        "mechanical_control",
        "mechanical_control",
        ("target_weight", "risk_amount_dollars", "position_lifecycle"),
        default_research_status="identity_control",
        applicability_reason_codes=("MECHANICAL_IDENTITY_CONTROL",),
        management_role=MANAGEMENT_ROLE_ATTRIBUTION_CONTROL,
    ),
    _record(
        "OVL-ORD-WEIGHT-BAND-V1",
        "execution_efficiency",
        "atomic_primitive",
        "project_defined",
        ("target_weight",),
        parameter_mapping={"min_weight_delta": 0.01},
        required_data=("target_weights", "current_positions", "close"),
        required_lifecycle_state=("monthly_rebalance_exit",),
        incompatible_base_features=("source_defined_rebalance_band",),
        default_research_status="available_for_diagnosed_purpose_only",
        applicability_reason_codes=("ADDRESSES_REDUNDANT_REALLOCATION", "TARGET_WEIGHT_ONLY"),
    ),
    _record(
        "OVL-ORD-MIN-NOTIONAL-V1",
        "execution_efficiency",
        "atomic_primitive",
        "project_defined",
        ("target_weight",),
        parameter_mapping={"min_nav_order_pct": 0.001},
        required_data=("target_weights", "portfolio_nav", "current_positions", "close"),
        incompatible_base_features=("source_defined_min_notional_filter",),
        default_research_status="available_for_diagnosed_purpose_only",
        applicability_reason_codes=("ADDRESSES_EXCESS_SMALL_ORDERS", "TARGET_WEIGHT_ONLY"),
    ),
    _record(
        "OVL-ORD-001",
        "execution_efficiency",
        "legacy_composite",
        "legacy_only",
        ("target_weight",),
        parameter_mapping={"min_weight_delta": 0.01, "min_nav_order_pct": 0.001},
        required_data=("target_weights", "portfolio_nav", "current_positions", "close"),
        default_research_status="legacy_reproduction_only",
        applicability_reason_codes=("LEGACY_WEIGHT_BAND_AND_MIN_NOTIONAL_COMPOSITE",),
    ),
    _record(
        "OVL-RISK-GROSS-CAP-V1",
        "portfolio_risk_control",
        "atomic_primitive",
        "project_defined",
        ("target_weight",),
        parameter_mapping={"max_gross_exposure": 1.0},
        required_data=("target_weights",),
        incompatible_base_features=("source_defined_gross_cap",),
        default_research_status="available_for_diagnosed_purpose_only",
        applicability_reason_codes=("ADDRESSES_EXCESS_GROSS_EXPOSURE", "TARGET_WEIGHT_ONLY"),
    ),
    _record(
        "OVL-RISK-ASSET-CAP-V1",
        "portfolio_risk_control",
        "atomic_primitive",
        "project_defined",
        ("target_weight",),
        parameter_mapping={"per_asset_cap": 0.35},
        required_data=("target_weights",),
        incompatible_base_features=("source_defined_asset_cap",),
        default_research_status="available_for_diagnosed_purpose_only",
        applicability_reason_codes=("ADDRESSES_EXCESS_ASSET_CONCENTRATION", "TARGET_WEIGHT_ONLY"),
    ),
    _record(
        "OVL-RISK-GROUP-CAP-V1",
        "portfolio_risk_control",
        "atomic_primitive",
        "project_defined",
        ("target_weight",),
        parameter_mapping={"group_caps": {}},
        required_data=("target_weights", "group_mapping"),
        incompatible_base_features=("source_defined_group_cap",),
        default_research_status="available_for_diagnosed_purpose_only",
        applicability_reason_codes=("ADDRESSES_CORRELATED_GROUP_CONCENTRATION", "TARGET_WEIGHT_ONLY"),
    ),
    _record(
        "OVL-RSK-001",
        "portfolio_risk_control",
        "legacy_composite",
        "legacy_only",
        ("target_weight",),
        parameter_mapping={"max_gross_exposure": 1.0, "per_asset_cap": None, "group_caps": {}},
        required_data=("target_weights", "group_mapping"),
        default_research_status="legacy_reproduction_only",
        applicability_reason_codes=("LEGACY_COMBINED_EXPOSURE_CAP_WRAPPER",),
    ),
    _record(
        "OVL-SIZ-001",
        "position_sizing",
        "atomic_primitive",
        "project_defined",
        ("target_weight", "risk_amount_dollars"),
        parameter_mapping={"lookback": 63, "scale_floor": 0.25, "scale_cap": 1.0},
        required_data=("lagged_close_history",),
        default_research_status="historical_invalid_calibration_retained",
        applicability_reason_codes=("ADDRESSES_UNSTABLE_POSITION_SIZE",),
    ),
    _record(
        "STATIC-LOWER-EXPOSURE-CONTROL",
        "position_sizing",
        "mechanical_control",
        "mechanical_control",
        ("target_weight", "risk_amount_dollars"),
        parameter_mapping={"scale": "calibration_or_attribution_defined"},
        default_research_status="attribution_control_only",
        applicability_reason_codes=("STATIC_EXPOSURE_ATTRIBUTION_CONTROL",),
        management_role=MANAGEMENT_ROLE_ATTRIBUTION_CONTROL,
    ),
    _record(
        "OVL-STP-001",
        "position_loss_control",
        "atomic_primitive",
        "project_defined",
        ("position_lifecycle",),
        parameter_mapping={"atr_lookback": 20, "atr_multiple": 4.0, "trailing": False},
        required_data=("ohlc", "atr_20"),
        incompatible_base_features=("base_stop_same_bar_precedence",),
        default_research_status="historical_no_advancement_retained",
        applicability_reason_codes=("ADDRESSES_LARGE_POSITION_TAIL_LOSS",),
    ),
    _record(
        "OVL-EXT-001",
        "lifecycle_management",
        "atomic_primitive",
        "project_defined",
        ("position_lifecycle",),
        parameter_mapping={"max_completed_bars": 5},
        required_data=("bars_held",),
        incompatible_base_features=("source_defined_time_exit",),
        default_research_status="historical_no_advancement_retained",
        applicability_reason_codes=("ADDRESSES_STALE_POSITION_BEYOND_SOURCE_HORIZON",),
    ),
    _record(
        "OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",
        "complete_portfolio_insurance",
        "holistic_source_system",
        "source_defined",
        ("target_weight",),
        parameter_mapping={
            "multiplier": 3.0,
            "horizon_years": 5.0,
            "guarantee_fraction": 1.0,
            "risk_free_rate": 0.05,
            "rebalance_frequency": "month_end",
            "cash_lock_after_floor_breach": True,
        },
        required_data=("target_weights", "portfolio_nav", "month_end_calendar", "safe_asset_mapping"),
        default_research_status="closed_exact_combination_mixed_across_episodes_concentrated_no_advancement",
        applicability_reason_codes=("SOURCE_DEFINED_COMPLETE_PORTFOLIO_INSURANCE_SYSTEM",),
        management_role=MANAGEMENT_ROLE_SOURCE_DEFINED_BASE,
    ),
)

OVERLAY_TAXONOMY_BY_ID = {record.overlay_id: record for record in OVERLAY_TAXONOMY}


def default_optional_management_count() -> int:
    return 0


def default_optional_overlay_candidate_ids() -> tuple[str, ...]:
    return ()


def taxonomy_rows() -> list[dict[str, Any]]:
    return [record.to_csv_row() for record in OVERLAY_TAXONOMY]


def overlay_migration_rows() -> list[dict[str, Any]]:
    return [
        {
            "legacy_overlay_id": "OVL-ORD-001",
            "replacement_overlay_ids": "OVL-ORD-WEIGHT-BAND-V1|OVL-ORD-MIN-NOTIONAL-V1",
            "migration_type": "split_legacy_composite",
            "auto_combine_future_experiments": False,
            "notes": "Historical OR behavior is reproducible only through the legacy wrapper; future experiments select one primitive.",
        },
        {
            "legacy_overlay_id": "OVL-RSK-001",
            "replacement_overlay_ids": "OVL-RISK-GROSS-CAP-V1|OVL-RISK-ASSET-CAP-V1|OVL-RISK-GROUP-CAP-V1",
            "migration_type": "split_legacy_combined_cap_wrapper",
            "auto_combine_future_experiments": False,
            "notes": "Legacy combined cap wrapper remains for lineage; future experiments select one supported cap primitive.",
        },
    ]


def legacy_status_rows() -> list[dict[str, Any]]:
    return [
        {
            "overlay_id": "OVL-ORD-001",
            "status": "legacy_composite_reproduction_only",
            "lineage_note": "Mixed rebalance-band evidence combined weight-band and min-notional effects.",
        },
        {
            "overlay_id": "OVL-RSK-001",
            "status": "legacy_combined_cap_reproduction_only",
            "lineage_note": "Combined gross, asset, and group cap mechanics are preserved as a wrapper only.",
        },
        {
            "overlay_id": "OVL-SIZ-001",
            "status": "historical_invalid_calibration_retained",
            "lineage_note": "Lagged volatility target failed closed under the tested calibration.",
        },
        {
            "overlay_id": "OVL-STP-001",
            "status": "historical_no_advancement_retained",
            "lineage_note": "Wide ATR stop was dominated by existing base lifecycle rules.",
        },
        {
            "overlay_id": "OVL-EXT-001",
            "status": "historical_no_advancement_retained",
            "lineage_note": "Five-bar time stop was cost-sensitive and winner-truncating.",
        },
        {
            "overlay_id": "OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",
            "status": "MIXED_ACROSS_EPISODES_CONCENTRATED_NO_ADVANCEMENT",
            "lineage_note": "CPPI remains a holistic source-defined complete portfolio-insurance lane.",
        },
    ]


def management_need_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ManagementExperimentPlan",
        "type": "object",
        "required": list(REQUIRED_PLAN_FIELDS),
        "properties": {
            "experiment_id": {"type": "string"},
            "base_strategy_id": {"type": "string"},
            "base_strategy_hash": {"type": "string"},
            "base_stage": {"type": "string"},
            "source_management_included": {"type": "boolean"},
            "diagnosed_weakness": {"type": "string", "enum": sorted(DIAGNOSED_WEAKNESS_CODES)},
            "weakness_evidence_reference": {"type": "string"},
            "selected_overlay_id": {"type": "string"},
            "overlay_purpose_id": {"type": "string", "enum": sorted(PURPOSE_IDS)},
            "compatibility_reason": {"type": "string"},
            "negative_or_attribution_control": {"type": "string"},
            "parameters": {"type": "object"},
            "adaptation_label": {"type": "string"},
            "research_stage": {"type": "string"},
            "authorized_overlay_count": {"type": "integer", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": True,
        "policy": {
            "default_optional_management_count": default_optional_management_count(),
            "one_optional_overlay_per_experiment": True,
            "compatibility_is_not_authorization": True,
        },
    }


def _plan_dict(plan: ManagementExperimentPlan | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(plan, ManagementExperimentPlan):
        return plan.to_dict()
    return dict(plan)


def _issue(issues: list[ManagementValidationIssue], code: str, field: str, message: str) -> None:
    issues.append(ManagementValidationIssue(code=code, field=field, message=message))


def validate_management_experiment_plan(
    plan: ManagementExperimentPlan | Mapping[str, Any],
    taxonomy: Mapping[str, OverlayTaxonomyRecord] | None = None,
) -> ManagementPlanValidation:
    payload = _plan_dict(plan)
    records = taxonomy or OVERLAY_TAXONOMY_BY_ID
    issues: list[ManagementValidationIssue] = []
    overlay_id = str(payload.get("selected_overlay_id", ""))
    record = records.get(overlay_id)
    diagnosed_weakness = str(payload.get("diagnosed_weakness", ""))
    purpose = str(payload.get("overlay_purpose_id", ""))

    if not diagnosed_weakness or diagnosed_weakness not in DIAGNOSED_WEAKNESS_CODES:
        _issue(
            issues,
            "NO_DIAGNOSED_MANAGEMENT_NEED",
            "diagnosed_weakness",
            "Optional management requires one stable diagnosed weakness code.",
        )

    if record is None:
        _issue(
            issues,
            "OVERLAY_PURPOSE_MISMATCH",
            "selected_overlay_id",
            "Selected overlay is not declared in the purpose taxonomy.",
        )
    else:
        if purpose != record.purpose_id:
            _issue(
                issues,
                "OVERLAY_PURPOSE_MISMATCH",
                "overlay_purpose_id",
                "Plan purpose does not match the selected overlay taxonomy record.",
            )
        if diagnosed_weakness in WEAKNESS_PURPOSE_MAP and record.purpose_id not in WEAKNESS_PURPOSE_MAP[diagnosed_weakness]:
            _issue(
                issues,
                "OVERLAY_PURPOSE_MISMATCH",
                "diagnosed_weakness",
                "Selected overlay purpose does not address the diagnosed weakness.",
            )
        if record.atomic_or_holistic == "legacy_composite" and str(payload.get("research_stage", "")) not in {
            "historical_reproduction",
            "lineage_verification",
            "hash_reproduction",
        }:
            _issue(
                issues,
                "LEGACY_COMPOSITE_NEW_RESEARCH_FORBIDDEN",
                "selected_overlay_id",
                "Legacy composites are not future optional-management candidates.",
            )

    authorized_count = int(payload.get("authorized_overlay_count", default_optional_management_count()) or 0)
    overlay_ids = _tuple(payload.get("optional_overlay_ids")) or ((overlay_id,) if overlay_id else ())
    if authorized_count > 1:
        _issue(
            issues,
            "MULTIPLE_OPTIONAL_OVERLAYS_NOT_AUTHORIZED",
            "authorized_overlay_count",
            "Combination research is outside this workflow even when a combination ID is supplied.",
        )

    selected_records = [records[item] for item in overlay_ids if item in records]
    if authorized_count > 1 and any(item.atomic_or_holistic == "holistic_source_system" for item in selected_records):
        _issue(
            issues,
            "HOLISTIC_SYSTEM_COMBINATION_NOT_AUTHORIZED",
            "optional_overlay_ids",
            "Holistic source-defined systems cannot be combined with another overlay in this workflow.",
        )
    if record is not None and record.atomic_or_holistic == "holistic_source_system" and len(overlay_ids) > 1:
        _issue(
            issues,
            "HOLISTIC_SYSTEM_COMBINATION_NOT_AUTHORIZED",
            "selected_overlay_id",
            "Holistic source-defined systems stay in separate research lanes.",
        )

    if record is not None:
        base_intent = str(payload.get("base_intent_kind") or payload.get("intent_kind") or "")
        if base_intent and base_intent not in record.supported_intent_kinds:
            _issue(
                issues,
                "UNSUPPORTED_INTENT_KIND",
                "base_intent_kind",
                "Selected overlay does not support the base strategy intent kind.",
            )

        available_data = set(_tuple(payload.get("available_data")))
        if available_data:
            missing = set(record.required_data) - available_data
            if missing:
                _issue(
                    issues,
                    "MISSING_REQUIRED_DATA",
                    "available_data",
                    "Selected overlay requires unavailable data: " + ",".join(sorted(missing)),
                )

        base_features = set(_tuple(payload.get("base_lifecycle_features")))
        conflicts = base_features & set(record.incompatible_base_features)
        if conflicts:
            _issue(
                issues,
                "CONFLICTING_BASE_LIFECYCLE",
                "base_lifecycle_features",
                "Base strategy already contains conflicting management features: " + ",".join(sorted(conflicts)),
            )

        source_management_included = bool(payload.get("source_management_included", False))
        requested_role = str(payload.get("management_role", MANAGEMENT_ROLE_OPTIONAL_OVERLAY))
        if source_management_included and requested_role == MANAGEMENT_ROLE_OPTIONAL_OVERLAY and record.source_status == "source_defined":
            _issue(
                issues,
                "CONFLICTING_BASE_LIFECYCLE",
                "source_management_included",
                "Source-defined management belongs in the source-exact base, not an optional overlay slot.",
            )

    failure_codes = tuple(dict.fromkeys(issue.code for issue in issues))
    return ManagementPlanValidation(authorized=not issues and authorized_count == 1, failure_codes=failure_codes, issues=tuple(issues))


def classify_cap_effect(events: Any) -> str:
    if events is None or len(events) == 0:
        return "APPLICABLE_NO_EFFECT"
    reason_values = set(str(value) for value in events.get("reason_code", []))
    if "unsupported_intent_unit" in reason_values:
        return "NOT_APPLICABLE_INTENT_UNIT"
    if reason_values & CAP_BINDING_REASON_CODES:
        return "APPLICABLE_EFFECTIVE"
    return "APPLICABLE_NO_EFFECT"


def _strategy_family(strategy_id: str) -> str:
    if strategy_id.startswith("N"):
        return "monthly_or_periodic_asset_allocation"
    if strategy_id.startswith("A"):
        return "sector_momentum"
    if strategy_id.startswith("B"):
        return "trend_following"
    if strategy_id.startswith("C"):
        return "swing_trend_pullback"
    if strategy_id.startswith("D"):
        return "mean_reversion"
    if strategy_id.startswith("E"):
        return "breakout"
    return "unknown"


def _strategy_intent_kind(strategy_id: str) -> str:
    return "target_weight" if strategy_id.startswith("N") else "risk_amount_dollars"


def _strategy_lifecycle_features(strategy_id: str, strategy_cfg: Mapping[str, Any]) -> tuple[str, ...]:
    features: list[str] = []
    if "initial_atr_multiple" in strategy_cfg:
        features.append("base_initial_atr_stop")
    if "trailing_atr_multiple" in strategy_cfg:
        features.append("base_trailing_stop")
    if "max_holding_days" in strategy_cfg:
        features.append("source_defined_time_exit")
    if "max_asset_weight" in strategy_cfg:
        features.append("source_defined_asset_cap")
    if "high_vol_risk_asset_scale" in strategy_cfg:
        features.append("source_defined_position_sizing")
    if strategy_id.startswith("N"):
        features.append("monthly_rebalance_lifecycle")
    return tuple(features)


def _strategy_available_data(strategy_id: str, intent_kind: str) -> tuple[str, ...]:
    data = {
        "ohlc",
        "close",
        "atr_20",
        "bars_held",
        "current_positions",
        "portfolio_nav",
        "lagged_close_history",
        "group_mapping",
    }
    if intent_kind == "target_weight":
        data.update({"target_weights", "month_end_calendar", "safe_asset_mapping"})
    return tuple(sorted(data))


def implemented_strategy_records(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    strategies = config.get("strategies", {})
    order = config.get("strategy_order") or list(strategies)
    for strategy_id in order:
        strategy_cfg = dict(strategies.get(strategy_id, {}))
        if strategy_cfg.get("shadow_only", False):
            continue
        intent_kind = _strategy_intent_kind(str(strategy_id))
        rows.append(
            {
                "strategy_id": str(strategy_id),
                "strategy_family": _strategy_family(str(strategy_id)),
                "intent_kind": intent_kind,
                "source_defined_lifecycle_features": _strategy_lifecycle_features(str(strategy_id), strategy_cfg),
                "available_data": _strategy_available_data(str(strategy_id), intent_kind),
            }
        )
    return rows


def generate_compatibility_matrix(
    strategies: Iterable[Mapping[str, Any]],
    overlays: Iterable[OverlayTaxonomyRecord] = OVERLAY_TAXONOMY,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy in strategies:
        strategy_id = str(strategy["strategy_id"])
        family = str(strategy.get("strategy_family", _strategy_family(strategy_id)))
        intent_kind = str(strategy.get("intent_kind", _strategy_intent_kind(strategy_id)))
        lifecycle_features = set(_tuple(strategy.get("source_defined_lifecycle_features")))
        available_data = set(_tuple(strategy.get("available_data")))
        for overlay in overlays:
            intent_ok = intent_kind in overlay.supported_intent_kinds or overlay.management_role == MANAGEMENT_ROLE_ATTRIBUTION_CONTROL
            lifecycle_ok = not (lifecycle_features & set(overlay.incompatible_base_features))
            data_ok = not set(overlay.required_data) - available_data
            future_candidate_ok = overlay.atomic_or_holistic != "legacy_composite"
            final_ok = intent_ok and lifecycle_ok and data_ok and future_candidate_ok
            if not intent_ok:
                reason = "UNSUPPORTED_INTENT_KIND"
            elif not lifecycle_ok:
                reason = "CONFLICTING_BASE_LIFECYCLE"
            elif not data_ok:
                reason = "MISSING_REQUIRED_DATA"
            elif not future_candidate_ok:
                reason = "LEGACY_COMPOSITE_NEW_RESEARCH_FORBIDDEN"
            else:
                reason = "STRUCTURALLY_COMPATIBLE_NOT_AUTHORIZED"
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_family": family,
                    "intent_kind": intent_kind,
                    "source_defined_lifecycle_features": "|".join(sorted(lifecycle_features)),
                    "overlay_id": overlay.overlay_id,
                    "purpose": overlay.purpose_id,
                    "intent_compatibility": intent_ok,
                    "lifecycle_compatibility": lifecycle_ok,
                    "data_compatibility": data_ok,
                    "final_applicability": final_ok,
                    "reason_code": reason,
                }
            )
    return rows


def compatibility_contains_performance_fields(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        normalized = {str(key).lower() for key in row}
        if normalized & PERFORMANCE_FIELD_NAMES:
            return True
    return False
