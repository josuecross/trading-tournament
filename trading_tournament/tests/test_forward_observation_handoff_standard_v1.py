from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    InternalCaptureV1Adapter,
    SourceAdapterRegistry,
    SpdjV1Adapter,
    normalized_standard_handoff_hash,
    standard_package_hash,
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
    LifecycleTransition,
    validate_transition,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.liveness import reconcile_session_liveness
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    CalculationEvent,
    CalculationRequest,
    CalculationResult,
    DeploymentProfile,
    IdentityBinding,
    StandardHandoff,
    StrategyState,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.package import materialize_standard_package
from contracts.forward_observation.forward_observation_handoff_standard_v1.state import (
    JsonStrategyStateStore,
    apply_calculation_result,
    promote_pending_target,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.timing import resolve_effective_timestamp
from execution_lab.alpaca_micro_live_v1.standard_handoff.validate_handoff import main as validation_cli_main


ROOT = Path(__file__).resolve().parents[1]
SPDJ = ROOT / "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest/package"
INTERNAL = ROOT / "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"


def handoff_payload(package_hash: str = "sha256:" + "0" * 64) -> dict:
    return {
        "envelope": {
            "schema_id": "forward_observation_handoff_standard_v1",
            "schema_version": 1,
            "handoff_id": "synthetic_handoff_v1",
            "handoff_version": "v1",
            "strategy_id": "research_strategy_v1",
            "strategy_version": "v1",
            "family_id": "synthetic_family",
            "architecture_id": "synthetic_architecture",
            "canonical_trial_id": "synthetic_trial",
            "research_eligibility_status": "research_eligible",
            "research_eligibility_evidence_id": "eligibility_evidence_v1",
            "created_at": "2026-08-10T00:00:00Z",
            "package_content_hash": package_hash,
            "source_hashes": {"source": "sha256:" + "1" * 64},
            "research_claim": "Synthetic contract fixture only.",
            "explicit_nonclaims": ["not live"],
            "caveats": [],
        },
        "tradable_contract": {
            "instruments": [
                {
                    "symbol": "SPY",
                    "role": "risk",
                    "exposure": "US equity",
                    "substitution_policy": "exact_only",
                    "approved_mappings": [],
                    "price_semantics": "adjusted_total_return",
                    "history_frequency": "daily",
                    "minimum_history": 2,
                    "lookback": 2,
                },
                {
                    "symbol": "BIL",
                    "role": "cash_proxy",
                    "exposure": "cash proxy",
                    "substitution_policy": "forbidden",
                    "approved_mappings": [],
                    "price_semantics": "adjusted_total_return",
                    "history_frequency": "daily",
                    "minimum_history": 2,
                    "lookback": 2,
                },
            ],
            "shorting_allowed": False,
            "leverage_allowed": False,
            "cash_behavior": "BIL fallback",
            "target_normalization_rule": "fully_invested_long_only",
        },
        "signal_dependencies": [
            {
                "signal_id": "prices",
                "signal_type": "market_price_signal",
                "contract_version": "v1",
                "authority_provider_class": "validated_market_data",
                "series_dataset_id": "SPY|BIL",
                "point_in_time_required": False,
                "publication_timing_required": False,
                "frequency": "daily",
                "freshness_policy": {"max_age_seconds": 86400},
                "missing_release_behavior": "retain_current_target",
                "formula_configuration_reference": "calculator_configuration",
            }
        ],
        "calculator_contract": {
            "calculator_type": "synthetic_price_rule",
            "calculator_contract_version": "v1",
            "calculator_configuration": {"threshold": 1.0},
            "permitted_receiver_parameters": [],
        },
        "timing_contract": {
            "calendar_id": "XNYS",
            "calculation_information_cutoff": "completed_close",
            "signal_availability_cutoff": "completed_close",
            "effective_rule": {"kind": "next_valid_session", "boundary": "after_close"},
            "no_event_behavior": "preserve_current_target",
        },
        "required_fixture_types": ["target_weight_fixture", "timing_fixture", "duplicate_event_fixture"],
    }


def write_standard_package(path: Path) -> tuple[Path, StandardHandoff]:
    path.mkdir(parents=True)
    handoff_path = path / "handoff.json"
    payload = handoff_payload()
    handoff_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files = {"handoff.json": normalized_standard_handoff_hash(handoff_path)}
    package_hash = standard_package_hash(files)
    payload["envelope"]["package_content_hash"] = package_hash
    handoff_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (path / "package_manifest.json").write_text(
        json.dumps(
            {
                "schema_id": "forward_observation_handoff_standard_v1",
                "schema_version": 1,
                "hash_algorithm": "canonical_file_hash_map_with_normalized_handoff_self_reference",
                "files": files,
                "package_content_hash": package_hash,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path, StandardHandoff.from_dict(payload)


def calendar() -> StaticExchangeCalendar:
    return StaticExchangeCalendar(
        "XNYS",
        [
            MarketSession("2025-09-11", "2025-09-11T13:30:00Z", "2025-09-11T20:00:00Z"),
            MarketSession("2025-09-12", "2025-09-12T13:30:00Z", "2025-09-12T20:00:00Z"),
            MarketSession("2025-09-15", "2025-09-15T13:30:00Z", "2025-09-15T20:00:00Z"),
        ],
    )


def event() -> CalculationEvent:
    return CalculationEvent(
        event_id="event:cpi:2025-08",
        event_type="external_release_event",
        source_id="BLS:CPIAUCNS",
        source_event_id="release:2025-09-11",
        source_reference_period="2025-08",
        available_timestamp="2025-09-11T12:30:00Z",
        processing_timestamp="2025-09-11T12:31:00Z",
    )


def binding(handoff: StandardHandoff) -> IdentityBinding:
    return IdentityBinding.create(
        handoff=handoff,
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        binding_timestamp="2026-08-10T00:00:00Z",
        binding_provenance="focused_test_explicit_binding",
    )


def result(handoff: StandardHandoff, *, effective: str = "2025-09-12T20:00:00Z") -> CalculationResult:
    return CalculationResult.target(
        handoff=handoff,
        binding=binding(handoff),
        event=event(),
        calculation_run_id="run_v1",
        calculated_at="2025-09-11T12:32:00Z",
        calculation_reference_time="2025-09-11T12:30:00Z",
        effective_timestamp=effective,
        target_weights={"SPY": 3.0, "BIL": 1.0},
        cash_weight=0.0,
    )


def initial_state() -> StrategyState:
    return StrategyState(
        strategy_instance_id="instance_v1",
        handoff_id="synthetic_handoff_v1",
        receiver_strategy_id="receiver_strategy_v1",
        lifecycle_state="validated_not_active",
        current_effective_target_version="old_target",
        current_effective_target={"BIL": 1.0},
        current_effective_timestamp="2025-08-01T20:00:00Z",
    )


def test_valid_common_envelope_and_required_field_validation() -> None:
    assert StandardHandoff.from_dict(handoff_payload()).envelope.schema_version == 1
    broken = handoff_payload()
    del broken["envelope"]["family_id"]
    with pytest.raises(StandardContractError, match="family_id") as exc:
        StandardHandoff.from_dict(broken)
    assert exc.value.code == "missing_required_contract_field"


def test_unsupported_major_version_fails() -> None:
    broken = handoff_payload()
    broken["envelope"]["schema_version"] = 2
    with pytest.raises(StandardContractError) as exc:
        StandardHandoff.from_dict(broken)
    assert exc.value.code == "unsupported_schema"


def test_malformed_package_hash_fails() -> None:
    broken = handoff_payload()
    broken["envelope"]["package_content_hash"] = "sha256:not-a-valid-digest"
    with pytest.raises(StandardContractError) as exc:
        StandardHandoff.from_dict(broken)
    assert exc.value.code == "package_integrity_failure"


def test_explicit_identity_binding_passes_and_implicit_alias_fails() -> None:
    handoff = StandardHandoff.from_dict(handoff_payload())
    assert binding(handoff).research_strategy_id == "research_strategy_v1"
    with pytest.raises(StandardContractError) as exc:
        IdentityBinding.create(
            handoff=handoff,
            receiver_strategy_id="",
            strategy_instance_id="instance",
            binding_timestamp="2026-08-10T00:00:00Z",
            binding_provenance="looks_similar",
        )
    assert exc.value.code == "invalid_identity_binding"


def test_target_weights_normalize_and_target_version_survives_restart() -> None:
    handoff = StandardHandoff.from_dict(handoff_payload())
    first = result(handoff)
    second = result(handoff)
    assert first.target_weights == {"BIL": 0.25, "SPY": 0.75}
    assert first.target_version_id == second.target_version_id
    assert "orders" not in first.to_dict()
    assert "quantities" not in first.to_dict()


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ({"kind": "same_session", "boundary": "after_close"}, "2025-09-11T20:00:00Z"),
        ({"kind": "next_valid_session", "boundary": "open"}, "2025-09-12T13:30:00Z"),
        ({"kind": "next_valid_session", "boundary": "after_close"}, "2025-09-12T20:00:00Z"),
        ({"kind": "session_offset", "offset": 2, "boundary": "after_close"}, "2025-09-15T20:00:00Z"),
        ({"kind": "explicit_timestamp", "timestamp": "2025-09-15T20:00:00Z"}, "2025-09-15T20:00:00Z"),
    ],
)
def test_daily_weekly_monthly_external_timing_is_composable(rule: dict, expected: str) -> None:
    payload = handoff_payload()
    payload["timing_contract"]["effective_rule"] = rule
    contract = StandardHandoff.from_dict(payload).timing_contract
    required_calendar = None if rule["kind"] == "explicit_timestamp" else calendar()
    assert resolve_effective_timestamp(contract, event=event(), calendar=required_calendar) == expected


def test_spdj_release_to_next_session_after_close_and_no_event_are_representable() -> None:
    adaptation = SpdjV1Adapter().adapt(SPDJ)
    assert adaptation.status == "contract_validated"
    assert adaptation.semantics_changed is False
    handoff = adaptation.normalized_handoff
    assert handoff is not None
    assert handoff.signal_dependencies[0].signal_type == "external_release_signal"
    assert handoff.signal_dependencies[0].point_in_time_required is True
    assert resolve_effective_timestamp(handoff.timing_contract, event=event(), calendar=calendar()) == "2025-09-12T20:00:00Z"
    no_event = CalculationResult.no_event(
        strategy_id=handoff.envelope.strategy_id,
        receiver_strategy_id="spdj_receiver",
        strategy_instance_id="spdj_instance",
        calculation_run_id="october_2025_check",
        calculated_at="2025-11-01T00:00:00Z",
        calculation_reference_time="2025-10-31T00:00:00Z",
        diagnostics={"reference_period": "2025-10", "reason": "no_release_no_event"},
    )
    assert no_event.status == "no_event"
    assert no_event.event_id is None
    assert no_event.target_weights == {}


def test_state_persists_pending_current_restart_and_duplicate_across_sessions(tmp_path: Path) -> None:
    handoff = StandardHandoff.from_dict(handoff_payload())
    store_a = JsonStrategyStateStore(tmp_path / "state")
    pending = apply_calculation_result(initial_state(), result(handoff), now="2025-09-11T12:33:00Z")
    assert pending.pending_target_version is not None
    assert pending.current_effective_target == {"BIL": 1.0}
    store_a.save(pending)

    store_b = JsonStrategyStateStore(tmp_path / "state")
    restarted = store_b.load("instance_v1")
    assert restarted is not None
    assert restarted.pending_target == {"BIL": 0.25, "SPY": 0.75}
    with pytest.raises(StandardContractError) as exc:
        apply_calculation_result(restarted, result(handoff), now="2025-09-11T13:00:00Z")
    assert exc.value.code == "duplicate_event"
    effective = promote_pending_target(restarted, now="2025-09-12T20:00:00Z")
    assert effective.current_effective_target == {"BIL": 0.25, "SPY": 0.75}
    assert effective.pending_target == {}


def test_no_event_preserves_current_target_and_does_not_create_handled_event() -> None:
    no_event = CalculationResult.no_event(
        strategy_id="research_strategy_v1",
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        calculation_run_id="no_event_run",
        calculated_at="2025-11-01T00:00:00Z",
        calculation_reference_time="2025-10-31T00:00:00Z",
        diagnostics={"reason": "no_release"},
    )
    updated = apply_calculation_result(initial_state(), no_event, now="2025-11-01T00:00:01Z")
    assert updated.current_effective_target == {"BIL": 1.0}
    assert updated.handled_event_ids == []


def test_liveness_active_stale_and_terminal() -> None:
    active = reconcile_session_liveness(
        {"status": "running", "last_heartbeat_utc": "2026-08-10T11:59:30Z", "planned_end_at_utc": "2026-08-11T00:00:00Z"},
        evaluated_at="2026-08-10T12:00:00Z",
        heartbeat_ttl_seconds=60,
        planned_end_grace_seconds=60,
    )
    stale = reconcile_session_liveness(
        {"status": "running", "last_heartbeat_utc": "2026-06-26T14:59:33.187465Z", "planned_end_at_utc": "2026-07-02T19:44:19.939650Z"},
        evaluated_at="2026-08-10T00:00:00Z",
        heartbeat_ttl_seconds=600,
        planned_end_grace_seconds=3600,
    )
    terminal = reconcile_session_liveness(
        {"status": "completed"}, evaluated_at="2026-08-10T00:00:00Z", heartbeat_ttl_seconds=60, planned_end_grace_seconds=60
    )
    assert active.authoritative_current_liveness == "active"
    assert stale.authoritative_current_liveness == "stale"
    assert terminal.authoritative_current_liveness == "terminal"


def test_lifecycle_allows_paper_path_rejects_invalid_and_microtrading() -> None:
    allowed = LifecycleTransition("validated_not_active", "paper_demo_initialized", "2026-08-10T00:00:00Z", "evidence", "task", "initialize")
    assert validate_transition(allowed) == allowed
    with pytest.raises(StandardContractError) as invalid:
        validate_transition(replace(allowed, next_state="paper_demo_active"))
    assert invalid.value.code == "state_contract_failure"
    with pytest.raises(StandardContractError) as micro:
        validate_transition(replace(allowed, next_state="microtrading_eligible"))
    assert micro.value.code == "microtrading_promotion_not_authorized"


def test_deployment_profile_is_separate_and_cannot_override_strategy() -> None:
    handoff = StandardHandoff.from_dict(handoff_payload())
    profile = DeploymentProfile(
        deployment_profile_id="profile_v1",
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        handoff_id="synthetic_handoff_v1",
    )
    profile.validate(handoff)
    with pytest.raises(StandardContractError):
        replace(profile, receiver_parameters={"signal_thresholds": [1, 2]}).validate(handoff)
    with pytest.raises(StandardContractError) as live:
        replace(profile, live_submission_enabled=True).validate(handoff)
    assert live.value.code == "microtrading_promotion_not_authorized"


def test_synthetic_standard_package_validates_and_corruption_fails(tmp_path: Path) -> None:
    package, _ = write_standard_package(tmp_path / "package")
    importer = HandoffImporter(storage_root=tmp_path / "imports")
    validated = importer.process(package, mode="validate_only", timestamp="2026-08-10T00:00:00Z")
    assert validated.acceptance.acceptance_status == "contract_validated"
    assert validated.acceptance.activation_performed is False
    (package / "handoff.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(StandardContractError) as corrupt:
        importer.process(package, mode="validate_only", timestamp="2026-08-10T00:00:00Z")
    assert corrupt.value.code == "package_integrity_failure"


def test_unsupported_standard_package_version_fails(tmp_path: Path) -> None:
    package, _ = write_standard_package(tmp_path / "package")
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    manifest["schema_version"] = 2
    (package / "package_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StandardContractError) as exc:
        HandoffImporter(storage_root=tmp_path / "imports").process(package, mode="validate_only", timestamp="2026-08-10T00:00:00Z")
    assert exc.value.code == "unsupported_schema"


def test_import_inactive_uses_immutable_receiver_storage_without_activation(tmp_path: Path) -> None:
    package, handoff = write_standard_package(tmp_path / "package")
    profile = DeploymentProfile(
        deployment_profile_id="profile_v1",
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        handoff_id="synthetic_handoff_v1",
        deployment_status="inactive",
    )
    imported = HandoffImporter(storage_root=tmp_path / "imports").process(
        package,
        mode="import_inactive",
        timestamp="2026-08-10T00:00:00Z",
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        binding_provenance="focused_test",
        deployment_profile=profile,
    )
    assert imported.acceptance.acceptance_status == "validated_not_active"
    assert imported.acceptance.activation_performed is False
    assert imported.imported_path is not None
    assert Path(imported.imported_path, "normalized_handoff.json").exists()
    assert handoff.envelope.strategy_id == imported.acceptance.research_strategy_id


def test_spdj_adapter_validate_only_is_structurally_complete_without_activation(tmp_path: Path) -> None:
    result = HandoffImporter(storage_root=tmp_path / "imports").process(
        SPDJ, mode="validate_only", timestamp="2026-08-10T00:00:00Z"
    )
    assert result.adaptation.source_schema == "spdj_forward_observation_handoff_schema_v1:v1"
    assert result.adaptation.normalized_handoff is not None
    assert result.acceptance.contract_validation_status == "contract_validated"
    assert result.acceptance.activation_performed is False
    assert result.imported_path is None


def test_internal_capture_adapter_reports_exact_enrichment_gaps() -> None:
    adaptation = InternalCaptureV1Adapter().adapt(INTERNAL)
    assert adaptation.status == "standard_adapter_available_contract_enrichment_required"
    assert adaptation.normalized_handoff is None
    assert adaptation.semantics_changed is False
    assert {row["field"] for row in adaptation.enrichment_gaps} == {
        "created_at",
        "package_content_hash",
        "canonical_trial_id",
        "research_claim",
        "calendar_id",
        "effective_timestamp_model",
        "fixture_manifest",
    }


def test_adapter_registry_identifies_all_three_schema_families(tmp_path: Path) -> None:
    standard, _ = write_standard_package(tmp_path / "standard")
    registry = SourceAdapterRegistry()
    assert registry.identify(standard).source_schema == "forward_observation_handoff_standard_v1:1"
    assert registry.identify(SPDJ).source_schema == "spdj_forward_observation_handoff_schema_v1:v1"
    assert registry.identify(INTERNAL).source_schema == "legacy_internal_capture_handoff:1"


def test_fixture_runner_invokes_targets_without_execution_objects() -> None:
    handoff = StandardHandoff.from_dict(handoff_payload())
    request = CalculationRequest(
        handoff_id=handoff.envelope.handoff_id,
        receiver_strategy_id="receiver_strategy_v1",
        strategy_instance_id="instance_v1",
        event=event(),
        calculation_timestamp="2025-09-11T12:32:00Z",
        validated_signal_inputs={"signal": 1},
        validated_market_history_inputs={"prices": [1, 2]},
        calendar_id="XNYS",
        persisted_strategy_state={},
        calculator_configuration=handoff.calculator_contract.calculator_configuration,
    )
    registry = CalculatorRegistry()
    registry.register(handoff.calculator_contract.calculator_type, lambda _request: result(handoff))
    fixture = FixtureDefinition(
        fixture_id="target_fixture",
        fixture_type="target_weight_fixture",
        calculator_type=handoff.calculator_contract.calculator_type,
        request=request,
        expected_target_weights={"BIL": 0.25, "SPY": 0.75},
        expected_effective_timestamp="2025-09-12T20:00:00Z",
    )
    outcome = run_fixture(fixture, registry)
    assert outcome["passed"] is True
    assert "orders" not in outcome["result"]


def test_schema_artifacts_are_valid_json() -> None:
    contract_root = ROOT / "contracts/forward_observation/forward_observation_handoff_standard_v1"
    for name in ["handoff.schema.json", "deployment_profile.schema.json", "receiver_acceptance.schema.json", "strategy_state.schema.json", "lifecycle_event.schema.json"]:
        assert json.loads((contract_root / name).read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")


def test_standard_modules_have_no_broker_or_order_submission_dependency() -> None:
    contract_root = ROOT / "contracts/forward_observation/forward_observation_handoff_standard_v1"
    source = "\n".join(path.read_text(encoding="utf-8") for path in contract_root.glob("*.py"))
    for forbidden in ["alpaca_client", "submit_order", "get_account", "ProposedOrder"]:
        assert forbidden not in source


def test_receiver_validation_cli_validates_without_activation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package, _ = materialize_standard_package(handoff_payload(), tmp_path / "cli_package")
    assert validation_cli_main(["validate-package", "--package", str(package), "--timestamp", "2026-08-10T00:00:00Z"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["acceptance_status"] == "contract_validated"
    assert output["activation_performed"] is False
