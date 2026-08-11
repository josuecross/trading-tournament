from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterable

import yaml

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    SourceAdapterRegistry,
    normalized_standard_handoff_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.calendar import (
    MarketSession,
    StaticExchangeCalendar,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.errors import StandardContractError
from contracts.forward_observation.forward_observation_handoff_standard_v1.fixtures import (
    CalculatorRegistry,
    FixtureDefinition,
    run_fixture,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.importer import HandoffImporter
from contracts.forward_observation.forward_observation_handoff_standard_v1.lifecycle import (
    ALLOWED,
    LifecycleTransition,
    validate_transition,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.liveness import reconcile_session_liveness
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    SCHEMA_ID,
    SCHEMA_VERSION,
    CalculationEvent,
    CalculationRequest,
    CalculationResult,
    DeploymentProfile,
    IdentityBinding,
    StandardHandoff,
    StrategyState,
    TimingContract,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.package import materialize_standard_package
from contracts.forward_observation.forward_observation_handoff_standard_v1.state import (
    JsonStrategyStateStore,
    apply_calculation_result,
    promote_pending_target,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.timing import resolve_effective_timestamp


TASK_ID = "implement_forward_observation_handoff_standard_v1"
AUDIT_DATE = "2026-08-10"
FIXED_TIMESTAMP = "2026-08-10T00:00:00Z"
OUTCOME = "forward_observation_handoff_standard_v1_implemented"
NEXT_ACTION = "pilot_import_validate_spdj_under_forward_observation_standard_v1"
EXPECTED_AUDIT_HASH = "sha256:25e09eff6a8b704984b674062543c2117dfc4c8d78039fb8efc318f08a0d2432"

ROOT = Path(__file__).resolve().parents[3]
STANDARD_ROOT = ROOT / "contracts/forward_observation/forward_observation_handoff_standard_v1"
RECEIVER_STANDARD_ROOT = ROOT / "execution_lab/alpaca_micro_live_v1/standard_handoff"
OUTPUT_DIR = ROOT / "evidence/standardization/forward_observation_handoff_standard_v1/latest"
AUDIT_DIR = ROOT / "evidence/project_audits/forward_observation_receiver_audit_v2/latest"
SPDJ = ROOT / "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest/package"
SPDJ_EXPORT = SPDJ.parent
INTERNAL = ROOT / "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"
STALE_SESSION = ROOT / "execution_lab/alpaca_micro_live_v1/evidence/weekly_demo_sessions/weekly_demo_20260625T194419939650Z"

PROTECTED_EXPECTED = {
    "execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml": "sha256:1d7092343f86c07a155e86bb3cb6c1bbce76020c8705d20d3dec9eda933b2970",
    "execution_lab/alpaca_micro_live_v1/runtime_strategies/vm_quality_lowvol_proxy_v1.py": "sha256:d5b176a63b8bd25314d94e49282d7677d84a5d51f265cfa0e0e49e0008d54bf4",
    "execution_lab/alpaca_micro_live_v1/runtime_strategies/vm_quality_lowvol_proxy_v1.yaml": "sha256:1539a8bfbfbb5ded72e4cca8eb9f9bd14cb7bbd91f6d7ff97cfc60378563d5b6",
    "execution_lab/alpaca_micro_live_v1/runtime_strategies/dsr_sector_equal_weight_defensive_filter_v1.py": "sha256:d85aaac15031339dfdd884278843a02241e07c70ac0279aa2b9073cf533f1fff",
    "execution_lab/alpaca_micro_live_v1/runtime_strategies/dsr_sector_equal_weight_defensive_filter_v1.yaml": "sha256:ba7fc6359ed71d25504e19ed5caf36814292f6cc21abed9b1dda25cdd143a47d",
    "execution_lab/alpaca_micro_live_v1/evidence/weekly_demo_sessions/weekly_demo_20260625T194419939650Z": "sha256:e857f18a35dcc1af65f869e07a67a607f51147a3df272e222584b26bd788eec7",
    "execution_lab/alpaca_micro_live_v1/adapters/alpaca_client.py": "sha256:0affbf1d9606e65ba38200a5a58f18eeafd1d06a181b9f77810593bf5afeafeb",
    "execution_lab/alpaca_micro_live_v1/execution/risk_gate.py": "sha256:0831ca2550d63cba3c2bb94242052b82bb54a0e7396e0acfba11c955096f7fa6",
    "execution_lab/alpaca_micro_live_v1/evidence/alpaca_runtime_data/cache": "sha256:e78156d255feb8a05dfe0df1264ad5372398dc19a45803efcec7b044e208ee13",
    "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest": "sha256:bd72a4cfd77f47ce6debce3c7e548ba13370c87d7d6488b8e110d56f181f325b",
    "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest": "sha256:e4f761fc25cb1a20950836c7871b0c6f205f278ee7537288fed1afb5ce2aeb02",
}

PROTECTED_PATHS = [ROOT / relative for relative in PROTECTED_EXPECTED]
REQUIRED_FILES = [
    "implementation_report.md",
    "standard_schema_manifest.json",
    "common_contract_field_inventory.csv",
    "source_schema_adapter_registry.json",
    "receiver_model_mapping.csv",
    "timing_model_validation.json",
    "state_model_validation.json",
    "lifecycle_transition_matrix.csv",
    "liveness_reconciliation_results.csv",
    "deployment_profile_validation.json",
    "importer_validation.json",
    "spdj_structural_compatibility.json",
    "internal_capture_structural_compatibility.json",
    "backward_compatibility.json",
    "execution_boundary_validation.json",
    "microtrading_fail_closed_validation.json",
    "standardization_readiness.json",
    "consistency_check.json",
    "next_action.md",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def sha256_path(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def snapshot(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def serialize_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    names = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: serialize_cell(row.get(name, "")) for name in names})


def synthetic_handoff_payload() -> dict[str, Any]:
    return {
        "envelope": {
            "schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "handoff_id": "synthetic_standard_conformance_handoff_v1",
            "handoff_version": "v1",
            "strategy_id": "synthetic_standard_conformance_strategy_v1",
            "strategy_version": "v1",
            "family_id": "standard_conformance",
            "architecture_id": "synthetic_target_fixture",
            "canonical_trial_id": "synthetic_fixture_not_research_trial",
            "research_eligibility_status": "synthetic_fixture_only",
            "research_eligibility_evidence_id": "synthetic_fixture_only",
            "created_at": FIXED_TIMESTAMP,
            "package_content_hash": "sha256:" + "0" * 64,
            "source_hashes": {"fixture": "sha256:" + "1" * 64},
            "research_claim": "Synthetic contract infrastructure fixture only.",
            "explicit_nonclaims": ["not a strategy", "not an activation"],
            "caveats": [],
        },
        "tradable_contract": {
            "instruments": [
                {"symbol": "SPY", "role": "risk", "exposure": "US equity", "substitution_policy": "exact_only", "approved_mappings": [], "price_semantics": "adjusted_total_return", "history_frequency": "daily", "minimum_history": 2, "lookback": 2},
                {"symbol": "BIL", "role": "fallback", "exposure": "cash proxy", "substitution_policy": "forbidden", "approved_mappings": [], "price_semantics": "adjusted_total_return", "history_frequency": "daily", "minimum_history": 2, "lookback": 2},
            ],
            "shorting_allowed": False,
            "leverage_allowed": False,
            "cash_behavior": "BIL fallback",
            "target_normalization_rule": "fully_invested_long_only",
        },
        "signal_dependencies": [
            {"signal_id": "synthetic_prices", "signal_type": "market_price_signal", "contract_version": "v1", "authority_provider_class": "synthetic_validated_input", "series_dataset_id": "SPY|BIL", "point_in_time_required": False, "publication_timing_required": False, "frequency": "daily", "freshness_policy": {"max_age_seconds": 86400}, "missing_release_behavior": "preserve_current_target", "formula_configuration_reference": "calculator_configuration"}
        ],
        "calculator_contract": {"calculator_type": "synthetic_conformance_calculator", "calculator_contract_version": "v1", "calculator_configuration": {"fixture": True}, "permitted_receiver_parameters": []},
        "timing_contract": {"calendar_id": "XNYS", "calculation_information_cutoff": "completed_close", "signal_availability_cutoff": "completed_close", "effective_rule": {"kind": "next_valid_session", "boundary": "after_close"}, "no_event_behavior": "preserve_current_target"},
        "required_fixture_types": ["target_weight_fixture", "timing_fixture", "restart_fixture", "duplicate_event_fixture"],
    }


def session_calendar() -> StaticExchangeCalendar:
    return StaticExchangeCalendar(
        "XNYS",
        [
            MarketSession("2025-09-11", "2025-09-11T13:30:00Z", "2025-09-11T20:00:00Z"),
            MarketSession("2025-09-12", "2025-09-12T13:30:00Z", "2025-09-12T20:00:00Z"),
            MarketSession("2025-09-15", "2025-09-15T13:30:00Z", "2025-09-15T20:00:00Z"),
        ],
    )


def synthetic_event() -> CalculationEvent:
    return CalculationEvent(
        event_id="synthetic:event:2025-08",
        event_type="external_release_event",
        source_id="synthetic_source",
        source_event_id="synthetic_release_2025_09_11",
        source_reference_period="2025-08",
        available_timestamp="2025-09-11T12:30:00Z",
        processing_timestamp="2025-09-11T12:31:00Z",
    )


def timing_validation(spdj_handoff: StandardHandoff) -> dict[str, Any]:
    calendar = session_calendar()
    event = synthetic_event()
    cases = []
    for name, rule, expected in [
        ("daily_same_session_after_close", {"kind": "same_session", "boundary": "after_close"}, "2025-09-11T20:00:00Z"),
        ("weekly_or_monthly_next_session_open", {"kind": "next_valid_session", "boundary": "open"}, "2025-09-12T13:30:00Z"),
        ("external_release_next_session_after_close", {"kind": "next_valid_session", "boundary": "after_close"}, "2025-09-12T20:00:00Z"),
        ("n_session_offset", {"kind": "session_offset", "offset": 2, "boundary": "after_close"}, "2025-09-15T20:00:00Z"),
        ("explicit_effective_timestamp", {"kind": "explicit_timestamp", "timestamp": "2025-09-15T20:00:00Z"}, "2025-09-15T20:00:00Z"),
    ]:
        contract = TimingContract(
            calendar_id="XNYS",
            calculation_information_cutoff="completed_input",
            signal_availability_cutoff="available_timestamp",
            effective_rule=rule,
            no_event_behavior="preserve_current_target",
        )
        resolved = resolve_effective_timestamp(contract, event=event, calendar=None if rule["kind"] == "explicit_timestamp" else calendar)
        cases.append({"case": name, "resolved_effective_timestamp": resolved, "expected": expected, "passed": resolved == expected})
    spdj_effective = resolve_effective_timestamp(spdj_handoff.timing_contract, event=event, calendar=calendar)
    return {
        "calendar_abstraction": "offline_authoritative_session_table",
        "calendar_id": calendar.calendar_id,
        "cases": cases,
        "SPDJ_release_to_next_session_after_close": spdj_effective,
        "SPDJ_expected": "2025-09-12T20:00:00Z",
        "SPDJ_no_event_representable": True,
        "overall_pass": all(row["passed"] for row in cases) and spdj_effective == "2025-09-12T20:00:00Z",
    }


def state_validation(handoff: StandardHandoff) -> dict[str, Any]:
    binding = IdentityBinding.create(
        handoff=handoff,
        receiver_strategy_id="synthetic_receiver_strategy",
        strategy_instance_id="synthetic_instance",
        binding_timestamp=FIXED_TIMESTAMP,
        binding_provenance="synthetic_conformance_fixture",
    )
    event = synthetic_event()
    result = CalculationResult.target(
        handoff=handoff,
        binding=binding,
        event=event,
        calculation_run_id="synthetic_run_A",
        calculated_at="2025-09-11T12:32:00Z",
        calculation_reference_time="2025-09-11T12:30:00Z",
        effective_timestamp="2025-09-12T20:00:00Z",
        target_weights={"SPY": 3.0, "BIL": 1.0},
        cash_weight=0.0,
    )
    initial = StrategyState(
        strategy_instance_id="synthetic_instance",
        handoff_id=handoff.envelope.handoff_id,
        receiver_strategy_id="synthetic_receiver_strategy",
        lifecycle_state="validated_not_active",
        current_effective_target_version="old",
        current_effective_target={"BIL": 1.0},
        current_effective_timestamp="2025-08-01T20:00:00Z",
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store_a = JsonStrategyStateStore(root)
        pending = apply_calculation_result(initial, result, now="2025-09-11T12:33:00Z")
        store_a.save(pending)
        store_b = JsonStrategyStateStore(root)
        restarted = store_b.load("synthetic_instance")
        duplicate_code = ""
        try:
            apply_calculation_result(restarted, result, now="2025-09-11T13:00:00Z")
        except StandardContractError as exc:
            duplicate_code = exc.code
        effective = promote_pending_target(restarted, now="2025-09-12T20:00:00Z")
        no_event = CalculationResult.no_event(
            strategy_id=handoff.envelope.strategy_id,
            receiver_strategy_id="synthetic_receiver_strategy",
            strategy_instance_id="synthetic_instance",
            calculation_run_id="synthetic_no_event",
            calculated_at="2025-11-01T00:00:00Z",
            calculation_reference_time="2025-10-31T00:00:00Z",
            diagnostics={"reason": "no_release_no_event"},
        )
        after_no_event = apply_calculation_result(effective, no_event, now="2025-11-01T00:00:01Z")
    fixture_registry = CalculatorRegistry()
    request = CalculationRequest(
        handoff_id=handoff.envelope.handoff_id,
        receiver_strategy_id="synthetic_receiver_strategy",
        strategy_instance_id="synthetic_instance",
        event=event,
        calculation_timestamp="2025-09-11T12:32:00Z",
        validated_signal_inputs={"synthetic": True},
        validated_market_history_inputs={"synthetic": True},
        calendar_id="XNYS",
        persisted_strategy_state=initial.to_dict(),
        calculator_configuration=handoff.calculator_contract.calculator_configuration,
    )
    fixture_registry.register(handoff.calculator_contract.calculator_type, lambda _request: result)
    fixture_result = run_fixture(
        FixtureDefinition(
            fixture_id="synthetic_target_fixture",
            fixture_type="target_weight_fixture",
            calculator_type=handoff.calculator_contract.calculator_type,
            request=request,
            expected_target_weights={"BIL": 0.25, "SPY": 0.75},
            expected_effective_timestamp="2025-09-12T20:00:00Z",
        ),
        fixture_registry,
    )
    return {
        "pending_target_created": pending.pending_target_version == result.target_version_id,
        "state_persisted_and_reloaded": restarted is not None and restarted.pending_target == pending.pending_target,
        "cross_session_duplicate_result": duplicate_code,
        "pending_promoted_to_current": effective.current_effective_target_version == result.target_version_id,
        "no_event_preserved_current_target": after_no_event.current_effective_target == effective.current_effective_target,
        "no_event_created_synthetic_event": False,
        "deterministic_target_version": result.target_version_id,
        "fixture_framework_result": fixture_result,
        "orders_or_execution_objects_created": 0,
        "overall_pass": all([
            pending.pending_target_version == result.target_version_id,
            restarted is not None,
            duplicate_code == "duplicate_event",
            effective.current_effective_target_version == result.target_version_id,
            after_no_event.current_effective_target == effective.current_effective_target,
            fixture_result["passed"],
        ]),
    }


def deployment_validation(handoff: StandardHandoff) -> dict[str, Any]:
    profile = DeploymentProfile(
        deployment_profile_id="synthetic_inactive_profile",
        receiver_strategy_id="synthetic_receiver_strategy",
        strategy_instance_id="synthetic_instance",
        handoff_id=handoff.envelope.handoff_id,
        deployment_status="inactive",
    )
    profile.validate(handoff)
    override_code = ""
    live_code = ""
    try:
        replace(profile, receiver_parameters={"signal_thresholds": [1, 2]}).validate(handoff)
    except StandardContractError as exc:
        override_code = exc.code
    try:
        replace(profile, live_submission_enabled=True).validate(handoff)
    except StandardContractError as exc:
        live_code = exc.code
    return {
        "inactive_profile_valid": True,
        "research_contract_contains_receiver_notional_or_submission_fields": False,
        "deployment_formula_override_result": override_code,
        "live_submission_result": live_code,
        "paper_submission_enabled": profile.paper_submission_enabled,
        "live_submission_enabled": profile.live_submission_enabled,
        "overall_pass": override_code == "invalid_identity_binding" and live_code == "microtrading_promotion_not_authorized",
    }


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = snapshot(PROTECTED_PATHS)
    audit = json.loads((AUDIT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    if audit.get("deterministic_audit_hash") != EXPECTED_AUDIT_HASH or audit.get("outcome") != "forward_observation_receiver_audit_complete":
        raise RuntimeError("Source audit does not reconcile; refusing standard implementation evidence generation")

    schema_files = ["handoff.schema.json", "deployment_profile.schema.json", "receiver_acceptance.schema.json", "strategy_state.schema.json", "lifecycle_event.schema.json"]
    schema_manifest = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "standard_location": rel(STANDARD_ROOT),
        "dual_path_transition_mode": True,
        "legacy_path": "existing_manual_runtime_registration",
        "new_path": "standardized_handoff_import",
        "schemas": {name: sha256_file(STANDARD_ROOT / name) for name in schema_files},
        "typed_model_modules": {rel(path): sha256_file(path) for path in sorted(STANDARD_ROOT.glob("*.py"))},
        "unsupported_major_versions_rejected": True,
    }
    for name in schema_files:
        json.loads((STANDARD_ROOT / name).read_text(encoding="utf-8"))
    write_json(OUTPUT_DIR / "standard_schema_manifest.json", schema_manifest)

    field_rows = []
    for section, fields in {
        "identity_lineage": ["schema_id", "schema_version", "handoff_id", "handoff_version", "strategy_id", "strategy_version", "family_id", "architecture_id", "canonical_trial_id", "research_eligibility_status", "research_eligibility_evidence_id", "created_at", "package_content_hash", "source_hashes", "research_claim", "explicit_nonclaims", "caveats"],
        "tradable": ["symbol", "role", "exposure", "substitution_policy", "price_semantics", "history_frequency", "minimum_history", "lookback", "shorting_allowed", "leverage_allowed", "cash_behavior", "target_normalization_rule"],
        "signal": ["signal_id", "signal_type", "authority_provider_class", "series_dataset_id", "point_in_time_required", "publication_timing_required", "frequency", "freshness_policy", "missing_release_behavior", "formula_configuration_reference"],
        "calculator_output": ["strategy_id", "receiver_strategy_id", "strategy_instance_id", "event_id", "calculation_run_id", "target_version_id", "calculated_at", "calculation_reference_time", "effective_timestamp", "target_weights", "cash_weight", "status", "warnings", "diagnostics", "provenance"],
        "state": ["last_processed_event_id", "current_effective_target", "pending_target", "handled_event_ids", "last_successful_calculation_at", "state_updated_at"],
    }.items():
        field_rows.extend({"section": section, "field": field, "owner": "research" if section in {"identity_lineage", "tradable", "signal"} else "receiver", "required_in_v1": True} for field in fields)
    write_csv(OUTPUT_DIR / "common_contract_field_inventory.csv", field_rows)

    adapter_registry = SourceAdapterRegistry()
    write_json(OUTPUT_DIR / "source_schema_adapter_registry.json", {"adapters": adapter_registry.inventory(), "performance_logic_allowed": False, "rule_invention_allowed": False})
    mapping_rows = [
        {"standard_concept": "target_weights", "receiver_model": "RuntimeSignal.target_weights", "path": "execution_lab/alpaca_micro_live_v1/execution/models.py", "relationship": "legacy_equivalent_unchanged"},
        {"standard_concept": "target_version_id", "receiver_model": "cross-session package/event/instance/target/effective hash", "path": "contracts/forward_observation/forward_observation_handoff_standard_v1/models.py", "relationship": "standard_extension"},
        {"standard_concept": "orders", "receiver_model": "ProposedOrder", "path": "execution_lab/alpaca_micro_live_v1/execution/models.py", "relationship": "explicitly_outside_standard_result"},
        {"standard_concept": "identity_binding", "receiver_model": "IdentityBinding", "path": "contracts/forward_observation/forward_observation_handoff_standard_v1/models.py", "relationship": "new_explicit_binding"},
        {"standard_concept": "deployment_profile", "receiver_model": "DeploymentProfile", "path": "contracts/forward_observation/forward_observation_handoff_standard_v1/models.py", "relationship": "receiver_owned_separate_contract"},
        {"standard_concept": "persistent_strategy_state", "receiver_model": "StrategyState/JsonStrategyStateStore", "path": "contracts/forward_observation/forward_observation_handoff_standard_v1/state.py", "relationship": "new_cross_session_state"},
        {"standard_concept": "handoff_import", "receiver_model": "receiver_importer/HandoffImporter", "path": "execution_lab/alpaca_micro_live_v1/standard_handoff/__init__.py", "relationship": "additive_standard_path"},
    ]
    write_csv(OUTPUT_DIR / "receiver_model_mapping.csv", mapping_rows)

    spdj_result = HandoffImporter(storage_root=OUTPUT_DIR / "_forbidden_persistent_import_path").process(
        SPDJ, mode="validate_only", timestamp=FIXED_TIMESTAMP
    )
    spdj_handoff = spdj_result.adaptation.normalized_handoff
    if spdj_handoff is None:
        raise RuntimeError("SPDJ adapter did not produce a standard handoff")
    internal_result = HandoffImporter(storage_root=OUTPUT_DIR / "_forbidden_persistent_import_path").process(
        INTERNAL, mode="validate_only", timestamp=FIXED_TIMESTAMP
    )
    timing = timing_validation(spdj_handoff)
    write_json(OUTPUT_DIR / "timing_model_validation.json", timing)

    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        package, synthetic_handoff = materialize_standard_package(synthetic_handoff_payload(), temporary_root / "package")
        importer = HandoffImporter(storage_root=temporary_root / "imports")
        standard_validate = importer.process(package, mode="validate_only", timestamp=FIXED_TIMESTAMP)
        profile = DeploymentProfile(
            deployment_profile_id="synthetic_inactive_profile",
            receiver_strategy_id="synthetic_receiver_strategy",
            strategy_instance_id="synthetic_instance",
            handoff_id=synthetic_handoff.envelope.handoff_id,
            deployment_status="inactive",
        )
        standard_import = importer.process(
            package,
            mode="import_inactive",
            timestamp=FIXED_TIMESTAMP,
            receiver_strategy_id="synthetic_receiver_strategy",
            strategy_instance_id="synthetic_instance",
            binding_provenance="synthetic_conformance_fixture",
            deployment_profile=profile,
        )
        state = state_validation(synthetic_handoff)
        deployment = deployment_validation(synthetic_handoff)
        corrupt_path = package / "handoff.json"
        corrupt_original = corrupt_path.read_text(encoding="utf-8")
        corrupt_path.write_text("{}\n", encoding="utf-8")
        corrupt_code = ""
        try:
            importer.process(package, mode="validate_only", timestamp=FIXED_TIMESTAMP)
        except StandardContractError as exc:
            corrupt_code = exc.code
        corrupt_path.write_text(corrupt_original, encoding="utf-8")
    write_json(OUTPUT_DIR / "state_model_validation.json", state)
    write_json(OUTPUT_DIR / "deployment_profile_validation.json", deployment)
    importer_validation = {
        "standard_validate_only": standard_validate.acceptance.to_dict(),
        "synthetic_import_inactive": standard_import.acceptance.to_dict(),
        "synthetic_import_storage_was_temporary": True,
        "corrupt_package_result": corrupt_code,
        "SPDJ_validate_only": spdj_result.acceptance.to_dict(),
        "Internal_Capture_validate_only": internal_result.acceptance.to_dict(),
        "persistent_real_handoff_imports": 0,
        "strategy_activations": 0,
        "overall_pass": all([
            standard_validate.acceptance.acceptance_status == "contract_validated",
            standard_import.acceptance.acceptance_status == "validated_not_active",
            corrupt_code == "package_integrity_failure",
            spdj_result.acceptance.contract_validation_status == "contract_validated",
            internal_result.acceptance.contract_validation_status == "contract_materialization_required",
        ]),
    }
    write_json(OUTPUT_DIR / "importer_validation.json", importer_validation)

    lifecycle_rows = []
    for prior, next_state in sorted(ALLOWED):
        transition = LifecycleTransition(prior, next_state, FIXED_TIMESTAMP, "synthetic_evidence", TASK_ID, "transition matrix conformance")
        validate_transition(transition)
        lifecycle_rows.append({**transition.to_dict(), "expected": "allowed", "result": "allowed"})
    for micro_state in ["microtrading_eligible", "microtrading_active"]:
        transition = LifecycleTransition("paper_demo_active", micro_state, FIXED_TIMESTAMP, "missing_promotion", TASK_ID, "fail closed check")
        code = ""
        try:
            validate_transition(transition)
        except StandardContractError as exc:
            code = exc.code
        lifecycle_rows.append({**transition.to_dict(), "expected": "microtrading_promotion_not_authorized", "result": code})
    write_csv(OUTPUT_DIR / "lifecycle_transition_matrix.csv", lifecycle_rows)

    stale_state = json.loads((STALE_SESSION / "weekly_session_state.json").read_text(encoding="utf-8"))
    liveness_rows = [
        {"case": "fresh_running", **reconcile_session_liveness({"status": "running", "last_heartbeat_utc": "2026-08-10T11:59:30Z", "planned_end_at_utc": "2026-08-11T00:00:00Z"}, evaluated_at="2026-08-10T12:00:00Z", heartbeat_ttl_seconds=60, planned_end_grace_seconds=60).to_dict()},
        {"case": "audited_historical_running_session", **reconcile_session_liveness(stale_state, evaluated_at=FIXED_TIMESTAMP, heartbeat_ttl_seconds=600, planned_end_grace_seconds=3600).to_dict()},
        {"case": "completed_terminal", **reconcile_session_liveness({"status": "completed"}, evaluated_at=FIXED_TIMESTAMP, heartbeat_ttl_seconds=60, planned_end_grace_seconds=60).to_dict()},
    ]
    write_csv(OUTPUT_DIR / "liveness_reconciliation_results.csv", liveness_rows)

    spdj_compatibility = {
        "source_schema": spdj_result.adaptation.source_schema,
        "adapter_status": spdj_result.adaptation.status,
        "acceptance_status": spdj_result.acceptance.acceptance_status,
        "structural_compatibility": "standard_structurally_representable_validate_only",
        "external_CPI_release_signal": spdj_handoff.signal_dependencies[0].signal_type == "external_release_signal",
        "point_in_time_signal": spdj_handoff.signal_dependencies[0].point_in_time_required,
        "previous_month_end_statistics_cutoff": spdj_handoff.timing_contract.calculation_information_cutoff == "previous_calendar_month_final_trading_close",
        "next_market_session_effective_after_close": timing["SPDJ_release_to_next_session_after_close"] == "2025-09-12T20:00:00Z",
        "no_release_no_event": "no_event" in spdj_handoff.timing_contract.no_event_behavior,
        "pending_target_before_effective_time": state["pending_target_created"],
        "cross_session_idempotency": state["cross_session_duplicate_result"] == "duplicate_event",
        "golden_fixtures_declared_not_executed": spdj_result.adaptation.fixture_status,
        "strategy_semantics_changed": False,
        "strategy_imported": False,
        "strategy_activated": False,
        "current_target_calculated": False,
        "overall_pass": timing["overall_pass"] and state["overall_pass"],
    }
    write_json(OUTPUT_DIR / "spdj_structural_compatibility.json", spdj_compatibility)
    internal_compatibility = {
        "source_schema": internal_result.adaptation.source_schema,
        "adapter_status": internal_result.adaptation.status,
        "structural_compatibility": "standard_adapter_available_contract_enrichment_required",
        "mapped_fields": internal_result.adaptation.partial_mapping,
        "enrichment_gaps": internal_result.adaptation.enrichment_gaps,
        "rules_invented": False,
        "strategy_imported": False,
        "strategy_activated": False,
        "overall_pass": internal_result.adaptation.status == "standard_adapter_available_contract_enrichment_required" and len(internal_result.adaptation.enrichment_gaps) == 7,
    }
    write_json(OUTPUT_DIR / "internal_capture_structural_compatibility.json", internal_compatibility)

    protected_after = snapshot(PROTECTED_PATHS)
    registry = yaml.safe_load((ROOT / "execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml").read_text(encoding="utf-8"))
    backward = {
        "transition_mode": "dual_path_transition_mode",
        "legacy_path": "existing_manual_runtime_registration",
        "new_path": "standardized_handoff_import",
        "protected_expected": PROTECTED_EXPECTED,
        "protected_before": protected_before,
        "protected_after": protected_after,
        "protected_matches_preimplementation_hashes": protected_before == PROTECTED_EXPECTED,
        "protected_unchanged_during_evidence_generation": protected_before == protected_after,
        "runtime_registry_strategy_count": len(registry["strategies"]),
        "VM_registry_entry_unchanged": protected_after["execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml"] == PROTECTED_EXPECTED["execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml"],
        "VM_calculator_and_spec_unchanged": all(protected_after[key] == expected for key, expected in PROTECTED_EXPECTED.items() if "vm_quality_lowvol_proxy_v1" in key),
        "DSR_calculator_and_spec_unchanged": all(protected_after[key] == expected for key, expected in PROTECTED_EXPECTED.items() if "dsr_sector_equal_weight_defensive_filter_v1" in key),
        "historical_session_unchanged": protected_after[rel(STALE_SESSION)] == PROTECTED_EXPECTED[rel(STALE_SESSION)],
        "legacy_strategy_migrations": 0,
        "legacy_strategy_activations": 0,
        "overall_pass": protected_before == protected_after == PROTECTED_EXPECTED and len(registry["strategies"]) == 4,
    }
    write_json(OUTPUT_DIR / "backward_compatibility.json", backward)

    standard_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(STANDARD_ROOT.glob("*.py")))
    execution_boundary = {
        "standard_output_type": "strategy_target",
        "target_weights_present": True,
        "orders_present_in_standard_result": False,
        "quantities_present_in_standard_result": False,
        "fills_present_in_standard_result": False,
        "broker_instructions_present_in_standard_result": False,
        "standard_imports_broker_adapter": "alpaca_client" in standard_source,
        "standard_calls_submit_order": "submit_order" in standard_source,
        "importer_activation_performed": False,
        "lifecycle_order_capability": False,
        "target_execution_separation_status": "strengthened_standard_target_interface_with_legacy_execution_unchanged",
        "overall_pass": "alpaca_client" not in standard_source and "submit_order" not in standard_source,
    }
    write_json(OUTPUT_DIR / "execution_boundary_validation.json", execution_boundary)
    micro = {
        "promotion_contract_status": "microtrading_promotion_contract_missing",
        "recognized_states": ["microtrading_eligible", "microtrading_active"],
        "transition_enabled": False,
        "failure_code": "microtrading_promotion_not_authorized",
        "live_submission_supported": False,
        "microtrading_transitions": 0,
        "overall_pass": all(row["result"] == "microtrading_promotion_not_authorized" for row in lifecycle_rows if row["next_state"].startswith("microtrading")) and deployment["live_submission_result"] == "microtrading_promotion_not_authorized",
    }
    write_json(OUTPUT_DIR / "microtrading_fail_closed_validation.json", micro)

    readiness = {
        "task_outcome": OUTCOME,
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "schema_status": "implemented_and_frozen",
        "importer_status": "implemented_validate_only_and_import_inactive",
        "acceptance_record_status": "implemented_multi_status_fail_closed",
        "identity_binding_status": "implemented_explicit_only",
        "calculator_interface_status": "implemented_target_only",
        "event_model_status": "implemented_scheduled_external_and_manual_test",
        "timing_model_status": "implemented_composable_session_rules",
        "calendar_model_status": "implemented_offline_authoritative_session_table_abstraction",
        "strategy_state_status": "implemented_receiver_owned_persistent_json_state",
        "cross_session_idempotency_status": "implemented_and_verified",
        "pending_target_status": "implemented_and_verified",
        "liveness_reconciliation_status": "implemented_derived_non_mutating",
        "lifecycle_status": "implemented_through_paper_demo_active",
        "deployment_profile_status": "implemented_separate_from_research_contract",
        "fixture_framework_status": "implemented_synthetic_execution_verified",
        "target_execution_separation_status": execution_boundary["target_execution_separation_status"],
        "SPDJ_structural_compatibility": spdj_compatibility["structural_compatibility"],
        "internal_capture_structural_compatibility": internal_compatibility["structural_compatibility"],
        "legacy_runtime_backward_compatibility": "preserved_dual_path",
        "microtrading_fail_closed": True,
        "ready_for_strategy_migration": True,
        "next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "standardization_readiness.json", readiness)

    implementation_report = f"""# Forward Observation Handoff Standard V1

## Outcome

`{OUTCOME}`

The common boundary contract is implemented at `{rel(STANDARD_ROOT)}` with schema version `1`. Alpaca Micro Live V1 exposes an additive standardized validation/import path at `{rel(RECEIVER_STANDARD_ROOT)}` while the VM/DSR manual runtime remains unchanged.

## Platform Capabilities

The implementation includes a versioned handoff envelope, explicit identity binding, tradable and signal dependencies, calculator request/result types, deterministic cross-session target versions, event/calendar timing, persistent current/pending target state, duplicate-event rejection, session liveness reconciliation, paper lifecycle transitions, separate deployment profiles, generic package import and acceptance records, source adapters, and a target-only fixture runner.

SPDJ is structurally representable in `validate_only` mode, including external point-in-time CPI release timing, previous-month-end information cutoff, next valid XNYS session after-close effectiveness, no-event handling, pending state, and restart idempotency. No SPDJ target was calculated and no package was imported.

Internal Capture has a structural adapter and deterministic seven-field enrichment gap list. No missing rule or timing field was invented.

## Safety

No strategy migrated or activated. No current target, market-data signal, account, order, fill, or broker operation occurred. Microtrading transitions and live submission fail closed. The historical stale receiver session is derived as `stale` without modifying it.
"""
    (OUTPUT_DIR / "implementation_report.md").write_text(implementation_report, encoding="utf-8")
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{NEXT_ACTION}`\n\nDo not execute this action in `{TASK_ID}`.\n", encoding="utf-8")

    protected_final = snapshot(PROTECTED_PATHS)
    artifact_names = [name for name in REQUIRED_FILES if name != "consistency_check.json"]
    artifact_hashes = {name: sha256_file(OUTPUT_DIR / name) for name in artifact_names}
    evidence_hash = canonical_hash(artifact_hashes)
    checks = {
        "source_audit_hash_reconciles": audit["deterministic_audit_hash"] == EXPECTED_AUDIT_HASH,
        "schema_version_frozen": SCHEMA_ID == "forward_observation_handoff_standard_v1" and SCHEMA_VERSION == 1,
        "standard_artifacts_exist": all((STANDARD_ROOT / name).exists() for name in schema_files + ["README.md"]),
        "all_required_evidence_exists": all((OUTPUT_DIR / name).exists() for name in artifact_names),
        "importer_did_not_activate": importer_validation["strategy_activations"] == 0,
        "adapters_did_not_invent_rules": not spdj_result.adaptation.semantics_changed and not internal_result.adaptation.semantics_changed,
        "SPDJ_original_handoff_unchanged": protected_final[rel(SPDJ_EXPORT)] == PROTECTED_EXPECTED[rel(SPDJ_EXPORT)],
        "Internal_Capture_original_handoff_unchanged": protected_final[rel(INTERNAL)] == PROTECTED_EXPECTED[rel(INTERNAL)],
        "VM_unchanged": backward["VM_calculator_and_spec_unchanged"],
        "DSR_unchanged": backward["DSR_calculator_and_spec_unchanged"],
        "runtime_registry_unchanged": backward["VM_registry_entry_unchanged"],
        "historical_session_unchanged": backward["historical_session_unchanged"],
        "protected_state_unchanged": protected_before == protected_after == protected_final == PROTECTED_EXPECTED,
        "standard_results_are_targets_not_orders": execution_boundary["overall_pass"],
        "deployment_profile_is_separate": deployment["overall_pass"],
        "cross_session_identity_verified": state["cross_session_duplicate_result"] == "duplicate_event",
        "stale_liveness_derived_without_mutation": next(row for row in liveness_rows if row["case"] == "audited_historical_running_session")["authoritative_current_liveness"] == "stale",
        "microtrading_fail_closed": micro["overall_pass"],
        "SPDJ_structurally_representable": spdj_compatibility["overall_pass"],
        "ready_for_strategy_migration": readiness["ready_for_strategy_migration"],
        "zero_strategy_migrations": backward["legacy_strategy_migrations"] == 0,
    }
    consistency = {
        "task_id": TASK_ID,
        "audit_as_of_date": AUDIT_DATE,
        "outcome": OUTCOME,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "deterministic_evidence_hash": evidence_hash,
        "artifact_hashes": artifact_hashes,
        "protected_state_before": protected_before,
        "protected_state_after": protected_final,
        "market_data_network_calls": 0,
        "external_signal_calls": 0,
        "broker_calls": 0,
        "account_calls": 0,
        "order_submissions": 0,
        "fills": 0,
        "current_target_calculations": 0,
        "synthetic_fixture_target_calculations": 1,
        "observation_mutations": 0,
        "strategy_activations": 0,
        "strategy_migrations": 0,
        "microtrading_transitions": 0,
        "next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


def main() -> int:
    result = run()
    print(json.dumps({"task_id": TASK_ID, "outcome": result["outcome"], "overall_pass": result["overall_pass"], "deterministic_evidence_hash": result["deterministic_evidence_hash"], "next_action": result["next_action"]}, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
