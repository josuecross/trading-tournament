from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .errors import StandardContractError


SCHEMA_ID = "forward_observation_handoff_standard_v1"
SCHEMA_VERSION = 1
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SIGNAL_TYPES = {"market_price_signal", "calendar_signal", "external_release_signal"}
EVENT_TYPES = {"scheduled_market_event", "external_release_event", "manual_test_event"}
SUBSTITUTION_POLICIES = {"forbidden", "exact_only", "approved_explicit_mapping"}
CALCULATION_STATUSES = {"target_calculated", "no_event", "blocked", "error"}


def _require(mapping: dict[str, Any], fields: list[str], *, context: str) -> None:
    missing = [name for name in fields if name not in mapping or mapping[name] in (None, "")]
    if missing:
        raise StandardContractError(
            "missing_required_contract_field",
            f"{context} is missing required fields: {', '.join(missing)}",
            details={"context": context, "missing_fields": missing},
        )


def _iso(value: str, *, field_name: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise StandardContractError(
            "missing_required_contract_field",
            f"{field_name} must be an ISO-8601 timestamp",
            details={"field": field_name},
        ) from exc
    return value


def _sha256(value: str, *, field_name: str) -> str:
    if not SHA256_PATTERN.fullmatch(value or ""):
        raise StandardContractError(
            "package_integrity_failure",
            f"{field_name} must be a lowercase sha256 digest",
            details={"field": field_name},
        )
    return value


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class HandoffEnvelope:
    schema_id: str
    schema_version: int
    handoff_id: str
    handoff_version: str
    strategy_id: str
    strategy_version: str
    family_id: str
    architecture_id: str
    canonical_trial_id: str
    research_eligibility_status: str
    research_eligibility_evidence_id: str
    created_at: str
    package_content_hash: str
    source_hashes: dict[str, str]
    research_claim: str
    explicit_nonclaims: list[str]
    caveats: list[Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HandoffEnvelope":
        required = [
            "schema_id", "schema_version", "handoff_id", "handoff_version", "strategy_id",
            "strategy_version", "family_id", "architecture_id", "canonical_trial_id",
            "research_eligibility_status", "research_eligibility_evidence_id", "created_at",
            "package_content_hash", "source_hashes", "research_claim", "explicit_nonclaims", "caveats",
        ]
        _require(value, required, context="handoff envelope")
        if value["schema_id"] != SCHEMA_ID or int(value["schema_version"]) != SCHEMA_VERSION:
            raise StandardContractError(
                "unsupported_schema",
                f"Only {SCHEMA_ID} schema version {SCHEMA_VERSION} is supported",
                details={"schema_id": value["schema_id"], "schema_version": value["schema_version"]},
            )
        if not isinstance(value["source_hashes"], dict):
            raise StandardContractError("missing_required_contract_field", "source_hashes must be an object")
        for key, digest in value["source_hashes"].items():
            _sha256(str(digest), field_name=f"source_hashes.{key}")
        _iso(str(value["created_at"]), field_name="created_at")
        _sha256(str(value["package_content_hash"]), field_name="package_content_hash")
        return cls(**{name: value[name] for name in required})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradableInstrument:
    symbol: str
    role: str
    exposure: str
    substitution_policy: str
    approved_mappings: list[str]
    price_semantics: str
    history_frequency: str
    minimum_history: int
    lookback: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TradableInstrument":
        required = ["symbol", "role", "exposure", "substitution_policy", "approved_mappings", "price_semantics", "history_frequency", "minimum_history", "lookback"]
        _require(value, required, context="tradable instrument")
        if value["substitution_policy"] not in SUBSTITUTION_POLICIES:
            raise StandardContractError("missing_required_contract_field", "Unsupported substitution policy")
        if value["substitution_policy"] != "approved_explicit_mapping" and value["approved_mappings"]:
            raise StandardContractError("missing_required_contract_field", "Mappings require approved_explicit_mapping")
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True)
class SignalDependency:
    signal_id: str
    signal_type: str
    contract_version: str
    authority_provider_class: str
    series_dataset_id: str
    point_in_time_required: bool
    publication_timing_required: bool
    frequency: str
    freshness_policy: dict[str, Any]
    missing_release_behavior: str
    formula_configuration_reference: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SignalDependency":
        required = ["signal_id", "signal_type", "contract_version", "authority_provider_class", "series_dataset_id", "point_in_time_required", "publication_timing_required", "frequency", "freshness_policy", "missing_release_behavior", "formula_configuration_reference"]
        _require(value, required, context="signal dependency")
        signal_type = str(value["signal_type"])
        if signal_type not in SIGNAL_TYPES and not signal_type.startswith("extension:"):
            raise StandardContractError("signal_dependency_not_supported", f"Unsupported signal type: {signal_type}")
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True)
class CalculatorContract:
    calculator_type: str
    calculator_contract_version: str
    calculator_configuration: dict[str, Any]
    permitted_receiver_parameters: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CalculatorContract":
        _require(value, ["calculator_type", "calculator_contract_version", "calculator_configuration"], context="calculator contract")
        return cls(
            calculator_type=str(value["calculator_type"]),
            calculator_contract_version=str(value["calculator_contract_version"]),
            calculator_configuration=dict(value["calculator_configuration"]),
            permitted_receiver_parameters=list(value.get("permitted_receiver_parameters") or []),
        )


@dataclass(frozen=True)
class TimingContract:
    calendar_id: str
    calculation_information_cutoff: str
    signal_availability_cutoff: str
    effective_rule: dict[str, Any]
    no_event_behavior: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TimingContract":
        required = ["calendar_id", "calculation_information_cutoff", "signal_availability_cutoff", "effective_rule", "no_event_behavior"]
        _require(value, required, context="timing contract")
        rule = value["effective_rule"]
        if not isinstance(rule, dict) or not rule.get("kind"):
            raise StandardContractError("timing_contract_not_supported", "effective_rule.kind is required")
        if rule["kind"] not in {"same_session", "next_valid_session", "session_offset", "explicit_timestamp"}:
            raise StandardContractError("timing_contract_not_supported", f"Unsupported effective rule: {rule['kind']}")
        if rule["kind"] != "explicit_timestamp" and not value["calendar_id"]:
            raise StandardContractError("calendar_binding_missing", "calendar_id is required")
        return cls(**{name: value[name] for name in required})


@dataclass(frozen=True)
class StandardHandoff:
    envelope: HandoffEnvelope
    tradable_instruments: list[TradableInstrument]
    shorting_allowed: bool
    leverage_allowed: bool
    cash_behavior: str
    target_normalization_rule: str
    signal_dependencies: list[SignalDependency]
    calculator_contract: CalculatorContract
    timing_contract: TimingContract
    required_fixture_types: list[str]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StandardHandoff":
        required = ["envelope", "tradable_contract", "signal_dependencies", "calculator_contract", "timing_contract", "required_fixture_types"]
        _require(value, required, context="standard handoff")
        tradable = value["tradable_contract"]
        _require(tradable, ["instruments", "shorting_allowed", "leverage_allowed", "cash_behavior", "target_normalization_rule"], context="tradable contract")
        instruments = [TradableInstrument.from_dict(row) for row in tradable["instruments"]]
        if not instruments:
            raise StandardContractError("missing_required_contract_field", "At least one tradable instrument is required")
        symbols = [row.symbol for row in instruments]
        if len(symbols) != len(set(symbols)):
            raise StandardContractError("missing_required_contract_field", "Tradable symbols must be unique")
        return cls(
            envelope=HandoffEnvelope.from_dict(value["envelope"]),
            tradable_instruments=instruments,
            shorting_allowed=bool(tradable["shorting_allowed"]),
            leverage_allowed=bool(tradable["leverage_allowed"]),
            cash_behavior=str(tradable["cash_behavior"]),
            target_normalization_rule=str(tradable["target_normalization_rule"]),
            signal_dependencies=[SignalDependency.from_dict(row) for row in value["signal_dependencies"]],
            calculator_contract=CalculatorContract.from_dict(value["calculator_contract"]),
            timing_contract=TimingContract.from_dict(value["timing_contract"]),
            required_fixture_types=list(value["required_fixture_types"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope": self.envelope.to_dict(),
            "tradable_contract": {
                "instruments": [asdict(row) for row in self.tradable_instruments],
                "shorting_allowed": self.shorting_allowed,
                "leverage_allowed": self.leverage_allowed,
                "cash_behavior": self.cash_behavior,
                "target_normalization_rule": self.target_normalization_rule,
            },
            "signal_dependencies": [asdict(row) for row in self.signal_dependencies],
            "calculator_contract": asdict(self.calculator_contract),
            "timing_contract": asdict(self.timing_contract),
            "required_fixture_types": self.required_fixture_types,
        }


@dataclass(frozen=True)
class IdentityBinding:
    handoff_id: str
    research_strategy_id: str
    receiver_strategy_id: str
    strategy_instance_id: str
    binding_timestamp: str
    binding_provenance: str

    @classmethod
    def create(
        cls,
        *,
        handoff: StandardHandoff,
        receiver_strategy_id: str,
        strategy_instance_id: str,
        binding_timestamp: str,
        binding_provenance: str,
    ) -> "IdentityBinding":
        if not receiver_strategy_id or not strategy_instance_id or not binding_provenance:
            raise StandardContractError(
                "invalid_identity_binding",
                "Receiver identity and provenance must be supplied explicitly; string similarity is never an alias rule",
            )
        _iso(binding_timestamp, field_name="binding_timestamp")
        return cls(
            handoff_id=handoff.envelope.handoff_id,
            research_strategy_id=handoff.envelope.strategy_id,
            receiver_strategy_id=receiver_strategy_id,
            strategy_instance_id=strategy_instance_id,
            binding_timestamp=binding_timestamp,
            binding_provenance=binding_provenance,
        )


@dataclass(frozen=True)
class CalculationEvent:
    event_id: str
    event_type: str
    source_id: str
    source_event_id: str
    source_reference_period: str
    available_timestamp: str
    processing_timestamp: str

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise StandardContractError("timing_contract_not_supported", f"Unsupported event type: {self.event_type}")
        _iso(self.available_timestamp, field_name="available_timestamp")
        _iso(self.processing_timestamp, field_name="processing_timestamp")


@dataclass(frozen=True)
class CalculationRequest:
    handoff_id: str
    receiver_strategy_id: str
    strategy_instance_id: str
    event: CalculationEvent
    calculation_timestamp: str
    validated_signal_inputs: dict[str, Any]
    validated_market_history_inputs: dict[str, Any]
    calendar_id: str
    persisted_strategy_state: dict[str, Any]
    calculator_configuration: dict[str, Any]

    def __post_init__(self) -> None:
        _iso(self.calculation_timestamp, field_name="calculation_timestamp")
        forbidden = {"orders", "fills", "broker_instructions", "account_positions", "proposed_orders"}
        present = forbidden.intersection(asdict(self))
        if present:
            raise StandardContractError("state_contract_failure", f"Execution fields are forbidden: {sorted(present)}")


def normalize_target_weights(weights: dict[str, float], *, cash_weight: float, normalization_rule: str) -> tuple[dict[str, float], float]:
    normalized = {str(symbol): float(weight) for symbol, weight in sorted(weights.items())}
    values = [*normalized.values(), float(cash_weight)]
    if not all(math.isfinite(value) for value in values):
        raise StandardContractError("state_contract_failure", "Target weights must be finite")
    if normalization_rule == "fully_invested_long_only":
        if any(value < -1e-12 for value in values):
            raise StandardContractError("state_contract_failure", "Long-only target contains a negative weight")
        total = sum(values)
        if total <= 0:
            raise StandardContractError("state_contract_failure", "Target weight total must be positive")
        normalized = {symbol: weight / total for symbol, weight in normalized.items()}
        cash_weight = float(cash_weight) / total
    return ({symbol: round(weight, 15) for symbol, weight in normalized.items()}, round(float(cash_weight), 15))


def deterministic_target_version_id(
    *,
    package_content_hash: str,
    handoff_id: str,
    strategy_instance_id: str,
    event_id: str,
    target_weights: dict[str, float],
    cash_weight: float,
    effective_timestamp: str,
) -> str:
    payload = {
        "package_content_hash": package_content_hash,
        "handoff_id": handoff_id,
        "strategy_instance_id": strategy_instance_id,
        "event_id": event_id,
        "target_weights": {key: target_weights[key] for key in sorted(target_weights)},
        "cash_weight": cash_weight,
        "effective_timestamp": effective_timestamp,
    }
    return canonical_json_hash(payload)


@dataclass(frozen=True)
class CalculationResult:
    strategy_id: str
    receiver_strategy_id: str
    strategy_instance_id: str
    event_id: str | None
    calculation_run_id: str
    target_version_id: str | None
    calculated_at: str
    calculation_reference_time: str
    effective_timestamp: str | None
    target_weights: dict[str, float]
    cash_weight: float
    status: str
    warnings: list[str]
    diagnostics: dict[str, Any]
    provenance: dict[str, Any]

    @classmethod
    def target(
        cls,
        *,
        handoff: StandardHandoff,
        binding: IdentityBinding,
        event: CalculationEvent,
        calculation_run_id: str,
        calculated_at: str,
        calculation_reference_time: str,
        effective_timestamp: str,
        target_weights: dict[str, float],
        cash_weight: float,
        warnings: list[str] | None = None,
        diagnostics: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> "CalculationResult":
        weights, cash = normalize_target_weights(
            target_weights,
            cash_weight=cash_weight,
            normalization_rule=handoff.target_normalization_rule,
        )
        version = deterministic_target_version_id(
            package_content_hash=handoff.envelope.package_content_hash,
            handoff_id=handoff.envelope.handoff_id,
            strategy_instance_id=binding.strategy_instance_id,
            event_id=event.event_id,
            target_weights=weights,
            cash_weight=cash,
            effective_timestamp=effective_timestamp,
        )
        return cls(
            strategy_id=handoff.envelope.strategy_id,
            receiver_strategy_id=binding.receiver_strategy_id,
            strategy_instance_id=binding.strategy_instance_id,
            event_id=event.event_id,
            calculation_run_id=calculation_run_id,
            target_version_id=version,
            calculated_at=_iso(calculated_at, field_name="calculated_at"),
            calculation_reference_time=_iso(calculation_reference_time, field_name="calculation_reference_time"),
            effective_timestamp=_iso(effective_timestamp, field_name="effective_timestamp"),
            target_weights=weights,
            cash_weight=cash,
            status="target_calculated",
            warnings=warnings or [],
            diagnostics=diagnostics or {},
            provenance=provenance or {},
        )

    @classmethod
    def no_event(
        cls,
        *,
        strategy_id: str,
        receiver_strategy_id: str,
        strategy_instance_id: str,
        calculation_run_id: str,
        calculated_at: str,
        calculation_reference_time: str,
        diagnostics: dict[str, Any],
    ) -> "CalculationResult":
        return cls(
            strategy_id=strategy_id,
            receiver_strategy_id=receiver_strategy_id,
            strategy_instance_id=strategy_instance_id,
            event_id=None,
            calculation_run_id=calculation_run_id,
            target_version_id=None,
            calculated_at=_iso(calculated_at, field_name="calculated_at"),
            calculation_reference_time=_iso(calculation_reference_time, field_name="calculation_reference_time"),
            effective_timestamp=None,
            target_weights={},
            cash_weight=0.0,
            status="no_event",
            warnings=[],
            diagnostics=diagnostics,
            provenance={},
        )

    def __post_init__(self) -> None:
        if self.status not in CALCULATION_STATUSES:
            raise StandardContractError("state_contract_failure", f"Unsupported calculation status: {self.status}")
        if self.status == "target_calculated" and (not self.event_id or not self.target_version_id or not self.effective_timestamp):
            raise StandardContractError("state_contract_failure", "Calculated targets require event, target version, and effective time")
        if self.status == "no_event" and any([self.event_id, self.target_version_id, self.target_weights, self.effective_timestamp]):
            raise StandardContractError("state_contract_failure", "no_event cannot synthesize an event or target")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyState:
    strategy_instance_id: str
    handoff_id: str
    receiver_strategy_id: str
    lifecycle_state: str
    last_processed_event_id: str | None = None
    last_processed_event_timestamp: str | None = None
    current_effective_target_version: str | None = None
    current_effective_target: dict[str, float] = field(default_factory=dict)
    current_effective_cash_weight: float = 0.0
    current_effective_timestamp: str | None = None
    pending_target_version: str | None = None
    pending_target: dict[str, float] = field(default_factory=dict)
    pending_cash_weight: float = 0.0
    pending_effective_timestamp: str | None = None
    handled_event_ids: list[str] = field(default_factory=list)
    last_successful_calculation_at: str | None = None
    state_updated_at: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StrategyState":
        _require(value, ["strategy_instance_id", "handoff_id", "receiver_strategy_id", "lifecycle_state"], context="strategy state")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentProfile:
    deployment_profile_id: str
    receiver_strategy_id: str
    strategy_instance_id: str
    handoff_id: str
    observation_mode: str = "inactive"
    sleeve_id: str | None = None
    allocation_policy: str | None = None
    shared_symbol_policy: dict[str, Any] | None = None
    market_data_capability_binding: str | None = None
    calendar_binding: str | None = None
    notional_limit: float | None = None
    max_order_notional: float | None = None
    rebalance_tolerance: float | None = None
    cash_buffer: float | None = None
    paper_submission_enabled: bool = False
    live_submission_enabled: bool = False
    risk_profile_id: str | None = None
    deployment_status: str = "inactive"
    receiver_parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self, handoff: StandardHandoff | None = None) -> None:
        if self.live_submission_enabled:
            raise StandardContractError("microtrading_promotion_not_authorized", "Live submission is unsupported in standard v1")
        forbidden = {"signal_thresholds", "ranking_rules", "target_weight_formula", "strategy_instruments", "calculator_configuration"}
        changed = sorted(forbidden.intersection(self.receiver_parameters))
        if changed:
            raise StandardContractError(
                "invalid_identity_binding",
                "Deployment profiles cannot override research strategy rules",
                details={"forbidden_parameters": changed},
            )
        if handoff:
            allowed = set(handoff.calculator_contract.permitted_receiver_parameters)
            unexpected = sorted(set(self.receiver_parameters) - allowed)
            if unexpected:
                raise StandardContractError(
                    "invalid_identity_binding",
                    "Receiver parameter is not explicitly permitted by research contract",
                    details={"unexpected_parameters": unexpected},
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AcceptanceRecord:
    handoff_id: str
    package_hash: str
    source_schema: str
    normalized_standard_schema: str
    research_strategy_id: str
    receiver_strategy_id: str | None
    import_mode: str
    integrity_status: str
    contract_validation_status: str
    fixture_validation_status: str
    deployment_profile_status: str
    acceptance_status: str
    blocking_reasons: list[dict[str, Any]]
    timestamp: str
    importer_version: str
    importer_hash: str
    activation_performed: bool = False

    def __post_init__(self) -> None:
        _sha256(self.package_hash, field_name="package_hash")
        _sha256(self.importer_hash, field_name="importer_hash")
        _iso(self.timestamp, field_name="timestamp")
        if self.import_mode not in {"validate_only", "import_inactive"}:
            raise StandardContractError("missing_required_contract_field", "Unsupported import mode")
        if self.activation_performed:
            raise StandardContractError("state_contract_failure", "Importer must not activate strategies")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
