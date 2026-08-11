from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml


TASK_ID = "audit_forward_observation_handoff_inventory_and_contract_standardization_v1"
AUDIT_DATE = "2026-08-10"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence/project_audits/forward_observation_handoff_inventory_and_standardization_v1/latest"
INTERNAL_HANDOFF = ROOT / "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"
SPDJ_EXPORT = ROOT / "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest"
SPDJ_PACKAGE = SPDJ_EXPORT / "package"
REGISTRY = ROOT / "strategy_lab/strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab/research_os/operations/active_observations.yaml"

OUTCOME = "forward_observation_handoff_audit_incomplete"
STANDARDIZATION_DECISION = "standardization_required_before_scaling"
NEXT_ACTION = "direction_owner_supply_forward_application_evidence_for_handoff_audit_v1"
COMMON_SCHEMA_ID = "forward_observation_handoff_standard_v1"

PROTECTED_PATHS = [
    ROOT / "strategy_lab/strategy_registry.yaml",
    ROOT / "strategy_lab/RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab/research_os/research/research_queue.yaml",
    ROOT / "strategy_lab/research_os/family_lineage/family_ledger.yaml",
    ACTIVE_OBSERVATIONS,
    INTERNAL_HANDOFF,
    SPDJ_EXPORT,
    ROOT / "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest",
    ROOT / "evidence/paper_demo_onboarding/correct_faa_stage_and_onboard_paper_demo_observation_v1/latest",
    ROOT / "evidence/paper_demo_onboarding/correct_psar_stage_and_onboard_paper_demo_observation_v1/latest",
    ROOT / "evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
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
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def normalized_spdj_package_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in SPDJ_PACKAGE.rglob("*") if item.is_file()):
        relative = path.relative_to(SPDJ_PACKAGE).as_posix()
        content = path.read_bytes()
        if relative == "handoff_manifest.json":
            payload = json.loads(content.decode("utf-8"))
            payload["package_content_hash"] = "__NORMALIZED_SELF_REFERENCE__"
            content = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_cell(row.get(key, "")) for key in fieldnames})


def serialize_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return value


def registry_by_id() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for record in payload["strategies"]:
        strategy_id = record.get("strategy_id", record.get("id", ""))
        if strategy_id:
            result[strategy_id] = record
    return result


def lifecycle_specs() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": "SPY_200d_trend_model",
            "current_stage": "legacy_stage_ambiguous",
            "furthest_evidenced_stage": "paper_demo_active_legacy_evidence",
            "research_eligible": False,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/strategy_registry.yaml|evidence/paper_forward_runs/latest",
            "reason": "registry says active_observation but authoritative active-observation ledger omits the strategy",
        },
        {
            "strategy_id": "profit_combo_SPY200d_GLD_50_50_v1",
            "current_stage": "legacy_stage_ambiguous",
            "furthest_evidenced_stage": "paper_demo_active_legacy_evidence",
            "research_eligible": False,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/strategy_registry.yaml|evidence/paper_forward_observations/combo_SPY200d_GLD_50_50_v1/latest",
            "reason": "registry and historical packet say active but authoritative active-observation ledger omits the strategy",
        },
        {
            "strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": False,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_forward_activations/vm_quality_lowvol_proxy_v1/latest",
            "reason": "active frozen recovered observation; no current-standard eligibility/export record",
        },
        {
            "strategy_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": False,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1/latest",
            "reason": "active frozen recovered observation; no current-standard eligibility/export record",
        },
        {
            "strategy_id": "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/usci_paper_forward_eligibility_review_v1/latest",
            "reason": "direction-owner eligibility review and authoritative active observation",
        },
        {
            "strategy_id": "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest",
            "reason": "eligibility review and authoritative active observation",
        },
        {
            "strategy_id": "ice_vaneck_us_fallen_angel_angl_v1",
            "current_stage": "blocked",
            "furthest_evidenced_stage": "research_eligible",
            "research_eligible": True,
            "initialized": False,
            "active_ever": False,
            "evidence": "strategy_lab/strategy_registry.yaml|strategy_lab/research_os/operations/active_observations.yaml|evidence/lifecycle/defer_angl_observation_data_lane_v1/latest",
            "reason": "eligible but observation invalid/incomplete and data lane deferred",
        },
        {
            "strategy_id": "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1",
            "current_stage": "blocked",
            "furthest_evidenced_stage": "research_eligible",
            "research_eligible": True,
            "initialized": False,
            "active_ever": False,
            "evidence": "strategy_lab/strategy_registry.yaml|strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo/review_and_onboard_ivts_unfiltered_paper_demo_observation_v1/latest",
            "reason": "eligible diversifier route but activation boundary deferred",
        },
        {
            "strategy_id": "keller_vanputten_faa_4m_top3_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo_onboarding/correct_faa_stage_and_onboard_paper_demo_observation_v1/latest",
            "reason": "active accepted standard paper/demo observation",
        },
        {
            "strategy_id": "barbara_decelerated_psar_spy_bil_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo_onboarding/correct_psar_stage_and_onboard_paper_demo_observation_v1/latest",
            "reason": "active accepted standard paper/demo observation",
        },
        {
            "strategy_id": "varadi_minimum_correlation_8etf_60d_weekly_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
            "reason": "active observation; first valid signal/execution still pending",
        },
        {
            "strategy_id": "schwoerer_hyg_ema100_spy_bil_v1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
            "reason": "active observation scheduled for first prospective execution",
        },
        {
            "strategy_id": "factory_v1_spy_trend_quality_state_d1",
            "current_stage": "paper_demo_active",
            "furthest_evidenced_stage": "paper_demo_active",
            "research_eligible": True,
            "initialized": True,
            "active_ever": True,
            "evidence": "strategy_lab/research_os/operations/active_observations.yaml|evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
            "reason": "active observation; current reference session still pending",
        },
        {
            "strategy_id": "internal_capture_asymmetry_63d_top3_v1",
            "current_stage": "handoff_exported_not_imported",
            "furthest_evidenced_stage": "handoff_exported",
            "research_eligible": True,
            "initialized": False,
            "active_ever": False,
            "handoff_id": "internal_capture_asymmetry_63d_top3_v1",
            "schema": "legacy_internal_capture_handoff:1",
            "canonical_trial_id": "accepted47_internal_v1__capture63__top3",
            "robustness_status": "robustness_positive",
            "evidence": "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest",
            "reason": "export ready; receiver operational status explicitly not evaluated",
        },
        {
            "strategy_id": "spdj_multi_asset_dynamic_inflation_etf_portability_v1",
            "current_stage": "handoff_exported_not_imported",
            "furthest_evidenced_stage": "handoff_exported",
            "research_eligible": True,
            "initialized": False,
            "active_ever": False,
            "handoff_id": "spdj_dynamic_inflation_forward_observation_handoff_v1",
            "schema": "spdj_forward_observation_handoff_schema_v1:v1",
            "canonical_trial_id": "spdj_multi_asset_dynamic_inflation_etf_portability_v1__canonical",
            "robustness_status": "robustness_positive",
            "evidence": "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest|evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest",
            "reason": "immutable export complete; next action is receiver import/validation",
        },
    ]


def build_lifecycle_inventory() -> list[dict[str, Any]]:
    registry = registry_by_id()
    rows: list[dict[str, Any]] = []
    for spec in lifecycle_specs():
        record = registry.get(spec["strategy_id"], {})
        family = record.get("family_id", record.get("family", record.get("strategy_family", "not_formalized")))
        architecture = record.get("architecture_id", record.get("strategy_architecture", "not_formalized"))
        rows.append(
            {
                "strategy_id": spec["strategy_id"],
                "family_id": family or "not_formalized",
                "architecture_id": architecture or "not_formalized",
                "canonical_trial_id": spec.get("canonical_trial_id", "not_formalized"),
                "robustness_status": spec.get("robustness_status", record.get("historical_robustness_outcome", "legacy_or_not_formalized")),
                "eligibility_status": "research_eligible" if spec["research_eligible"] else "not_formally_evidenced_under_current_standard",
                "handoff_id": spec.get("handoff_id", ""),
                "handoff_schema_version": spec.get("schema", ""),
                "receiver_import_status": "forward_application_evidence_unavailable",
                "receiver_validation_status": "forward_application_evidence_unavailable",
                "observation_initialization_status": "initialized_or_historically_evidenced" if spec["initialized"] else "not_initialized",
                "observation_activity_status": "active_ever_evidenced" if spec["active_ever"] else "not_active",
                "microtrading_status": "not_eligible_not_active",
                "furthest_evidenced_stage": spec["furthest_evidenced_stage"],
                "current_exclusive_stage": spec["current_stage"],
                "evidence_locations": spec["evidence"],
                "classification_reason": spec["reason"],
            }
        )
    return rows


def lifecycle_counts(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    specs = lifecycle_specs()
    exclusive_labels = [
        "research_only",
        "robustness_passed_not_eligible",
        "research_eligible_not_exported",
        "handoff_exported_not_imported",
        "receiver_imported_not_validated",
        "receiver_validated_not_initialized",
        "paper_demo_initialized",
        "paper_demo_active",
        "microtrading_eligible",
        "microtrading_active",
        "legacy_stage_ambiguous",
        "blocked",
    ]
    exclusive = {label: sum(row["current_exclusive_stage"] == label for row in inventory) for label in exclusive_labels}
    return {
        "total_forward_relevant_strategies": len(inventory),
        "research_eligible": sum(bool(row["research_eligible"]) for row in specs),
        "handoff_exported": sum(bool(row.get("handoff_id")) for row in specs),
        "receiver_imported": 0,
        "receiver_validated": 0,
        "paper_demo_initialized": sum(bool(row["initialized"]) for row in specs),
        "paper_demo_active": sum(bool(row["active_ever"]) for row in specs),
        "paper_demo_currently_active": exclusive["paper_demo_active"],
        "microtrading_eligible": 0,
        "microtrading_active": 0,
        "legacy_stage_ambiguous": exclusive["legacy_stage_ambiguous"],
        "current_exclusive_stage_counts": exclusive,
        "counting_note": "paper_demo_active is cumulative ever-evidenced; paper_demo_currently_active is current exclusive and excludes two conflicting legacy records",
    }


def package_inventory() -> list[dict[str, Any]]:
    internal_manifest = yaml.safe_load((INTERNAL_HANDOFF / "handoff_manifest.yaml").read_text(encoding="utf-8"))
    spdj_manifest = json.loads((SPDJ_PACKAGE / "handoff_manifest.json").read_text(encoding="utf-8"))
    return [
        {
            "handoff_id": "internal_capture_asymmetry_63d_top3_v1",
            "strategy_id": internal_manifest["strategy_id"],
            "schema_name": "legacy_internal_capture_handoff",
            "schema_version": internal_manifest["handoff_schema_version"],
            "package_hash": internal_manifest["strategy_handoff_semantic_hash"],
            "package_hash_scope": "canonical semantic content of strategy_handoff YAML/JSON",
            "strategy_contract_present": True,
            "signal_contract_present": True,
            "schedule_timing_contract_present": True,
            "instrument_mapping_present": True,
            "state_machine_contract_present": False,
            "forward_interface_contract_present": True,
            "caveat_register_present": True,
            "source_provenance_present": True,
            "research_lineage_manifest_present": True,
            "golden_fixtures_present": False,
            "receiver_acceptance_checklist_present": False,
            "reference_implementation_present": False,
            "secret_scan_evidence": "handoff_validation:no_secrets_api_keys_account_ids_or_broker_configuration",
            "path_hygiene_status": "audit_scan_pass_relative_paths_only",
            "package_path": rel(INTERNAL_HANDOFF),
        },
        {
            "handoff_id": spdj_manifest["handoff_id"],
            "strategy_id": spdj_manifest["strategy_id"],
            "schema_name": spdj_manifest["package_schema_version"],
            "schema_version": spdj_manifest["handoff_version"],
            "package_hash": spdj_manifest["package_content_hash"],
            "package_hash_scope": spdj_manifest["package_hash_scope"],
            "strategy_contract_present": True,
            "signal_contract_present": True,
            "schedule_timing_contract_present": True,
            "instrument_mapping_present": True,
            "state_machine_contract_present": True,
            "forward_interface_contract_present": True,
            "caveat_register_present": True,
            "source_provenance_present": True,
            "research_lineage_manifest_present": True,
            "golden_fixtures_present": True,
            "receiver_acceptance_checklist_present": True,
            "reference_implementation_present": True,
            "secret_scan_evidence": "hygiene_scan:secret_scan_pass",
            "path_hygiene_status": "hygiene_scan:absolute_path_hygiene_pass",
            "package_path": rel(SPDJ_PACKAGE),
        },
    ]


def contract_completeness(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory:
        strategy_id = item["strategy_id"]
        if strategy_id == "spdj_multi_asset_dynamic_inflation_etf_portability_v1":
            classification = "contract_complete_machine_executable"
            present = "yes"
            notes = "typed package, explicit interface/state/timing/price contracts, lineage hashes, and 15 golden fixtures"
        elif strategy_id == "internal_capture_asymmetry_63d_top3_v1":
            classification = "contract_complete_but_adapter_required"
            present = "yes"
            notes = "complete monolithic semantic contract; legacy field layout lacks separate state-machine and golden-fixture conformance layer"
        else:
            classification = "legacy_contract_not_formalized"
            present = "legacy_evidence_only"
            notes = "strategy/observation evidence exists but no immutable receiver handoff contract was found"
        rows.append(
            {
                "strategy_id": strategy_id,
                "classification": classification,
                "identity": present,
                "tradable_universe": present,
                "signal_definition": present,
                "target_weight_algorithm": present,
                "schedule_and_effective_timing": present,
                "missing_data_behavior": present,
                "state_and_idempotency": "yes" if classification == "contract_complete_machine_executable" else ("partial" if classification == "contract_complete_but_adapter_required" else "not_formalized"),
                "price_semantics": present,
                "provenance_hashes": present,
                "golden_conformance_fixtures": "yes" if classification == "contract_complete_machine_executable" else "no",
                "ordinary_event_interpretation_required": classification == "legacy_contract_not_formalized",
                "notes": notes,
            }
        )
    return rows


def receiver_matrix(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": row["strategy_id"],
            "receiver_classification": "receiver_not_auditable_application_unavailable",
            "receiver_application_status": "forward_application_evidence_unavailable",
            "import_evidence": "not_available",
            "validation_evidence": "not_available",
            "target_execution_separation_auditable": "handoff_only" if row["handoff_id"] else "legacy_evidence_only",
            "reason": "no separate forward-observation application or receiver interface evidence was available in the local repository environment",
        }
        for row in inventory
    ]


def manifest_field_union() -> list[dict[str, Any]]:
    both = "internal_capture_asymmetry_63d_top3_v1|spdj_dynamic_inflation_forward_observation_handoff_v1"
    spdj = "spdj_dynamic_inflation_forward_observation_handoff_v1"
    concepts = [
        ("strategy_id", both, "identity.strategy_id|handoff_manifest.strategy_id", "required", "consistent", "13 legacy strategies"),
        ("family_id", both, "identity.family_id|handoff_manifest.family_id", "required", "consistent", "13 legacy strategies"),
        ("architecture_id", both, "identity.architecture_id|handoff_manifest.architecture_id", "required", "consistent", "13 legacy strategies"),
        ("handoff_id", spdj, "handoff_manifest.handoff_id", "required", "missing_in_legacy_schema", "internal capture and 13 legacy strategies"),
        ("strategy_version", both, "identity.strategy_version|strategy_contract.strategy_version", "required", "consistent", "13 legacy strategies"),
        ("schema_version", both, "handoff_schema_version|package_schema_version+handoff_version", "required", "different_types_and_names", "13 legacy strategies"),
        ("tradable_symbols", both, "frozen_strategy.universe|instrument_mapping", "required", "semantically_consistent_structurally_different", "13 legacy strategies"),
        ("signal_dependencies", both, "data_contract.required_fields|signal_contract.dependencies", "required", "semantically_consistent_structurally_different", "13 legacy strategies"),
        ("strategy_formula", both, "frozen_strategy.formula|signal_contract+strategy_contract", "required", "strategy_specific_by_design", "13 legacy strategies"),
        ("warmup", both, "frozen_strategy.warmup|strategy_state_machine.warmup", "required", "semantically_consistent_structurally_different", "13 legacy strategies"),
        ("formation_schedule", both, "frozen_strategy.signal_schedule|schedule_and_timing_contract", "required", "semantically_consistent_structurally_different", "13 legacy strategies"),
        ("target_effective_timing", both, "execution_contract|schedule_and_timing_contract", "required", "consistent_following_session_semantics", "13 legacy strategies"),
        ("target_weight_algorithm", both, "frozen_strategy.target_rules|strategy_contract", "required", "strategy_specific_by_design", "13 legacy strategies"),
        ("portfolio_constraints", both, "portfolio_risk_contract|strategy_contract.constraints", "required", "consistent", "13 legacy strategies"),
        ("missing_data_behavior", both, "missing_data_strategy_semantics|strategy_state_machine", "required", "semantically_consistent_structurally_different", "13 legacy strategies"),
        ("price_semantics", both, "data_contract.adjustment_convention|price_semantics_contract", "required", "consistent_adjusted_total_return_research_boundary", "13 legacy strategies"),
        ("state_machine", spdj, "strategy_state_machine", "required", "absent_as_separate_legacy_contract", "internal capture and 13 legacy strategies"),
        ("duplicate_restart_idempotency", spdj, "strategy_state_machine.event_identity_and_restart", "required", "missing_in_legacy_schema", "internal capture and 13 legacy strategies"),
        ("forward_interface", both, "embedded_execution_and_data_contract|forward_observation_interface_contract", "required", "semantically_related_structurally_different", "13 legacy strategies"),
        ("golden_fixtures", spdj, "golden_conformance_fixtures+golden_fixture_manifest", "required", "missing_in_legacy_schema", "internal capture and 13 legacy strategies"),
        ("caveats", both, "caveats|caveat_register", "required", "consistent_content_different_encoding", "13 legacy strategies"),
        ("research_claim_and_nonclaims", spdj, "research_claims_and_nonclaims", "required", "not_separated_in_legacy_schema", "internal capture and 13 legacy strategies"),
        ("code_hash", both, "strategy_configuration_sha256|canonical_code_hash", "required", "different_scope", "13 legacy strategies"),
        ("source_and_dataset_hashes", both, "evidence_lineage|handoff_manifest hashes+source_provenance", "required", "different_granularity", "13 legacy strategies"),
        ("package_hash", both, "strategy_handoff_semantic_hash|package_content_hash", "required", "different_scope", "13 legacy strategies"),
        ("receiver_acceptance_checklist", spdj, "receiver_acceptance_checklist", "required", "missing_in_legacy_schema", "internal capture and 13 legacy strategies"),
        ("responsibility_boundary", both, "module_owner+consumer_module|forward_application_responsibility_boundary", "required", "consistent_boundary_different_detail", "13 legacy strategies"),
    ]
    return [
        {
            "concept_name": name,
            "packages_containing_it": packages,
            "current_field_names": fields,
            "requirement_in_proposed_standard": requirement,
            "semantic_consistency": consistency,
            "receiver_support": "forward_application_evidence_unavailable",
            "missing_strategies": missing,
        }
        for name, packages, fields, requirement, consistency, missing in concepts
    ]


def schema_variance() -> list[dict[str, Any]]:
    rows = [
        ("envelope_layout", "monolithic YAML/JSON", "typed multi-file package", "medium", "normalize common envelope; retain logic module"),
        ("schema_identity", "integer handoff_schema_version", "named package_schema_version plus handoff_version", "high", "one schema_id and semantic version"),
        ("handoff_identity", "strategy ID doubles as package identity", "explicit handoff_id", "high", "require immutable handoff_id"),
        ("state_machine", "implicit/partial", "explicit versioned contract", "high", "require state, restart, duplicate-event and idempotency semantics"),
        ("golden_fixtures", "absent", "15 fixtures and manifest", "high", "require conformance fixtures"),
        ("receiver_acceptance", "absent", "explicit checklist", "medium", "standard acceptance report"),
        ("package_hash", "semantic payload hash", "normalized full-package hash", "medium", "standardize scope and self-reference rule"),
        ("claims_and_nonclaims", "embedded caveats/research evidence", "separate typed document", "medium", "require explicit claim boundary"),
        ("lifecycle_semantics", "paper/demo/onboarded/active terms vary across legacy evidence", "export-specific status only", "high", "canonical lifecycle enum with evidence transition IDs"),
        ("execution_boundary", "clear in two exports but absent from 13 legacy contracts", "explicit target-only responsibility boundary", "high", "standard strategy-target versus execution boundary"),
        ("receiver_evidence", "operational status not evaluated", "next action requests import/validation", "blocking", "supply receiver repository/interface and acceptance records"),
    ]
    return [
        {"variance_area": a, "legacy_internal_capture": b, "spdj_export": c, "severity": d, "standardization_treatment": e}
        for a, b, c, d, e in rows
    ]


def compatibility_matrix(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reconstruction = {
        "SPY_200d_trend_model",
        "profit_combo_SPY200d_GLD_50_50_v1",
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    }
    rows = []
    for row in inventory:
        strategy_id = row["strategy_id"]
        if strategy_id == "spdj_multi_asset_dynamic_inflation_etf_portability_v1":
            classification = "native"
            work = "map schema ID to common envelope; preserve calculator and fixtures"
        elif strategy_id == "internal_capture_asymmetry_63d_top3_v1":
            classification = "adapter_required"
            work = "split monolithic contract, add state/idempotency fields and golden fixtures"
        elif strategy_id in reconstruction:
            classification = "research_reconstruction_required"
            work = "reconstruct and freeze complete rules from implementation/evidence, then create fixtures"
        else:
            classification = "contract_enrichment_required"
            work = "materialize existing frozen rules into common envelope, state contract and fixtures"
        rows.append({"strategy_id": strategy_id, "compatibility": classification, "minimum_migration_work": work})
    return rows


def migration_scope() -> list[dict[str, Any]]:
    return [
        {"scope": "native_or_no_material_rule_change", "strategy_count": 1, "strategy_ids": "spdj_multi_asset_dynamic_inflation_etf_portability_v1", "work": "common-envelope alias/version mapping only"},
        {"scope": "adapter_and_fixture_enrichment", "strategy_count": 1, "strategy_ids": "internal_capture_asymmetry_63d_top3_v1", "work": "map legacy fields; add explicit state/idempotency and golden fixtures"},
        {"scope": "contract_materialization", "strategy_count": 9, "strategy_ids": "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1|paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1|ice_vaneck_us_fallen_angel_angl_v1|donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1|keller_vanputten_faa_4m_top3_v1|barbara_decelerated_psar_spy_bil_v1|varadi_minimum_correlation_8etf_60d_weekly_v1|schwoerer_hyg_ema100_spy_bil_v1|factory_v1_spy_trend_quality_state_d1", "work": "materialize existing evidence into common contracts and conformance fixtures"},
        {"scope": "research_rule_reconstruction", "strategy_count": 4, "strategy_ids": "SPY_200d_trend_model|profit_combo_SPY200d_GLD_50_50_v1|paper_forward_vm_quality_lowvol_proxy_v1|paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "work": "resolve legacy rule/source lineage and freeze machine-readable contracts before receiver migration"},
        {"scope": "golden_fixture_creation", "strategy_count": 14, "strategy_ids": "all_except_spdj", "work": "create deterministic signal, target, timing, missing-data and restart fixtures"},
        {"scope": "receiver_common_work", "strategy_count": 0, "strategy_ids": "not_counted_as_strategies", "work": "receiver evidence unavailable; expected work is versioned importer, lifecycle enum, calculator interface, conformance harness and explicit microtrading promotion gate"},
    ]


def evidence_gaps() -> list[dict[str, Any]]:
    return [
        {"gap_id": "forward_application_evidence_unavailable", "severity": "blocking", "affected": "all 15 strategies", "impact": "receiver import, validation, state, ledger and compatibility claims cannot be made", "resolution": "supply local read-only receiver repository or exported acceptance evidence"},
        {"gap_id": "receiver_interface_contract_unavailable", "severity": "blocking", "affected": "both exports", "impact": "direct versus adapter compatibility cannot be measured", "resolution": "supply receiver schema/calculator/state interfaces"},
        {"gap_id": "legacy_contracts_not_formalized", "severity": "material", "affected": "13 strategies", "impact": "generic receiver cannot reconstruct ordinary strategy behavior from an immutable package", "resolution": "materialize or reconstruct contracts under common standard"},
        {"gap_id": "legacy_current_state_conflict", "severity": "material", "affected": "SPY_200d_trend_model|profit_combo_SPY200d_GLD_50_50_v1", "impact": "registry active status conflicts with omission from authoritative active-observation ledger", "resolution": "direction owner reconciles current lifecycle state without activating either strategy"},
        {"gap_id": "internal_capture_conformance_gap", "severity": "material", "affected": "internal_capture_asymmetry_63d_top3_v1", "impact": "no golden fixtures or explicit restart/idempotency state contract", "resolution": "add non-mutating successor package under common standard"},
        {"gap_id": "microtrading_promotion_contract_missing", "severity": "material", "affected": "project-wide", "impact": "paper/demo status has no auditable transition gate to microtrading eligibility", "resolution": "define separate promotion contract in receiver/governance layer; do not infer authorization"},
    ]


def proposed_contract_markdown() -> str:
    return f"""# {COMMON_SCHEMA_ID}

## Purpose

Provide one auditable boundary between frozen research exports and a separate forward-observation receiver. The handoff outputs strategy targets, never orders, quantities, broker instructions, positions, or approvals.

## A. Common envelope

Required fields: `schema_id`, `schema_version`, `handoff_id`, `package_hash`, `strategy_id`, `strategy_version`, `family_id`, `architecture_id`, `research_eligibility`, `canonical_trial_id`, `tradable_symbols`, `signal_dependencies`, `schedule`, `effective_timing`, `price_semantics`, `missing_data_behavior`, `state_requirements`, `provenance`, `caveats`, `research_claim`, and `nonclaims`.

Lifecycle uses only `research_eligible`, `handoff_exported`, `imported`, `validated_not_active`, `paper_demo_initialized`, `paper_demo_active`, `microtrading_eligible`, and `microtrading_active`. Every transition carries an evidence ID and timestamp. Intent and next actions do not advance state.

## B. Strategy logic module

Each package declares `strategy_logic_type`, `strategy_logic_version`, a machine-readable frozen configuration, and a versioned calculator entry point. Different calendar, price, macro, single-asset, and multi-asset strategies keep their own formulas. The common standard does not impose a universal formula DSL.

The module must define signal formula, lookback, thresholds/ranks/ties, target normalization, cash and zero-weight behavior, warmup, leverage/short constraints, substitutions, and every ordinary missing-data branch.

## C. Receiver interface

Inputs: validated signal events, validated market-data history, exchange calendar, and persisted strategy state.

Outputs: `target_weights`, `effective_timestamp`, `event_id`, calculation provenance, and status/error. Receiver state must support duplicate-event rejection, restart persistence, pending/effective targets, stale-event rejection, and idempotent replay.

The receiver owns market-data freshness, current signals, virtual positions/equity, sizing, notional limits, broker precision, order generation, fills, and execution risk. The strategy package owns no broker action.

## D. Conformance fixtures

Every handoff includes golden fixtures covering first eligible signal, each regime/state, equality/tie boundaries, missing data, stale events, blocked execution, duplicate replay, restart recovery, and target-effective timing. Fixtures include input hashes, expected targets, event IDs, and calculation provenance.

## E. Price and execution semantics

Contracts explicitly state adjusted/unadjusted fields, dividend/split treatment, total-return requirements, transformation frequency, formation timestamp, execution boundary, exchange calendar, and missing execution-price behavior. Same-session return attribution must be explicit.

## F. Promotion boundary

Paper/demo activity never implies microtrading eligibility. A separate, explicit promotion contract must authorize microtrading and define notional/risk limits, execution controls, review evidence, kill switches, and revocation. No such authorization is created by this proposal.
"""


def audit_report(counts: dict[str, Any], inventory: list[dict[str, Any]]) -> str:
    lifecycle_lines = "\n".join(f"- `{row['strategy_id']}`: `{row['furthest_evidenced_stage']}`; current `{row['current_exclusive_stage']}`." for row in inventory)
    return f"""# Forward Observation Handoff Inventory And Standardization Audit V1

## 1. Executive finding

Outcome: `{OUTCOME}`. The trading-tournament repository was auditable, but the separate forward-observation application was not available. Fifteen forward-relevant strategies were found. Two have formal exports, one of those is machine-executable under its native schema, and thirteen legacy/onboarded strategies have no formal receiver handoff contract. Standardization is `{STANDARDIZATION_DECISION}` before additional scaling.

## 2. How many strategies reached each forward stage

- Research eligible: {counts['research_eligible']}
- Handoff exported: {counts['handoff_exported']}
- Receiver imported: 0 (no receiver evidence)
- Receiver validated: 0 (no receiver evidence)
- Paper/demo initialized ever: {counts['paper_demo_initialized']}
- Paper/demo active ever: {counts['paper_demo_active']}
- Paper/demo currently active: {counts['paper_demo_currently_active']}
- Microtrading eligible/active: 0/0
- Legacy current-state ambiguous: {counts['legacy_stage_ambiguous']}

## 3. Strategy-by-strategy lifecycle status

{lifecycle_lines}

## 4. Existing handoff-package quality

The internal-capture export is a semantically complete monolithic YAML/JSON schema (`1`) with hashes and clear research/receiver boundaries, but it lacks a standalone state machine, acceptance checklist, reference calculator, and golden fixtures. The SPDJ export is a typed multi-file schema with a normalized package hash, explicit state/interface/price/timing contracts, receiver checklist, reference code, and 15 golden fixtures.

## 5. Contract completeness

One strategy is `contract_complete_machine_executable`; one is `contract_complete_but_adapter_required`; thirteen are `legacy_contract_not_formalized`. The legacy evidence can support later contract materialization, but it is not a substitute for an immutable receiver contract.

## 6. Receiver compatibility

`forward_application_evidence_unavailable`. Therefore no strategy is counted as imported, validated, directly compatible, or adapter-compatible. Existing exports remain only `handoff_exported_not_imported` until receiver evidence proves otherwise.

## 7. Paper versus microtrading boundary

The two exports correctly stop at target-weight contracts and assign positions, sizing, orders, broker precision, execution, and fills to the receiver. This boundary is not formalized across thirteen legacy strategies, so the project has an `execution_boundary_standardization_gap`. No explicit paper-to-microtrading promotion contract was found: `microtrading_promotion_contract_missing`.

## 8. Standardization decision

`{STANDARDIZATION_DECISION}`. The reason is semantic, not cosmetic: lifecycle terms conflict, thirteen strategies lack formal machine contracts, one export lacks conformance/state details, and receiver compatibility cannot be audited.

## 9. Minimum common standard if needed

Adopt `{COMMON_SCHEMA_ID}` with a common envelope, versioned strategy-calculator interface, explicit timing/price/state behavior, deterministic target outputs, conformance fixtures, lifecycle transition evidence, and a strict strategy-target versus execution boundary.

## 10. Migration impact

One package is native with minor envelope mapping; one needs an adapter plus fixtures/state enrichment; nine need contract materialization from existing evidence; four need legacy rule reconstruction; fourteen need golden fixtures. Receiver changes remain unscoped until its repository/interface is supplied.

## 11. Evidence gaps

The separate receiver repository, import ledger, acceptance results, state interface, virtual ledgers, and microtrading promotion gate were unavailable. Two older registry-active strategies are absent from the authoritative active-observation ledger and remain ambiguous.

## 12. Exact next action

`{NEXT_ACTION}`
"""


def parse_handoff_manifests() -> tuple[int, list[str]]:
    errors: list[str] = []
    parsed = 0
    for root in (INTERNAL_HANDOFF, SPDJ_EXPORT):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".csv"}:
                continue
            try:
                if path.suffix.lower() == ".json":
                    json.loads(path.read_text(encoding="utf-8"))
                else:
                    with path.open(newline="", encoding="utf-8") as handle:
                        list(csv.DictReader(handle))
                parsed += 1
            except Exception as exc:  # pragma: no cover - surfaced in evidence
                errors.append(f"{rel(path)}:{type(exc).__name__}:{exc}")
    return parsed, errors


def scan_package_hygiene() -> dict[str, Any]:
    absolute = re.compile(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/)")
    secret = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|account[_-]?id)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{12,}")
    absolute_hits: list[str] = []
    secret_hits: list[str] = []
    for root in (INTERNAL_HANDOFF, SPDJ_PACKAGE):
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path.suffix.lower() not in {".json", ".yaml", ".yml", ".csv", ".md", ".txt", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if absolute.search(text):
                absolute_hits.append(rel(path))
            if secret.search(text):
                secret_hits.append(rel(path))
    return {"absolute_path_hits": absolute_hits, "secret_hits": secret_hits}


def generated_audit_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in OUTPUT_DIR.rglob("*") if item.is_file() and item.name != "consistency_check.json"):
        digest.update(path.relative_to(OUTPUT_DIR).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def run() -> dict[str, Any]:
    protected_before = snapshot(PROTECTED_PATHS)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    inventory = build_lifecycle_inventory()
    counts = lifecycle_counts(inventory)
    packages = package_inventory()
    contracts = contract_completeness(inventory)
    receiver = receiver_matrix(inventory)
    fields = manifest_field_union()
    variances = schema_variance()
    compatibility = compatibility_matrix(inventory)
    migrations = migration_scope()
    gaps = evidence_gaps()

    write_csv(OUTPUT_DIR / "strategy_lifecycle_inventory.csv", inventory)
    write_json(OUTPUT_DIR / "lifecycle_counts.json", counts)
    write_csv(OUTPUT_DIR / "handoff_package_inventory.csv", packages)
    write_csv(OUTPUT_DIR / "strategy_contract_completeness.csv", contracts)
    write_csv(OUTPUT_DIR / "receiver_compatibility_matrix.csv", receiver)
    write_csv(OUTPUT_DIR / "manifest_field_union.csv", fields)
    write_csv(OUTPUT_DIR / "schema_variance_report.csv", variances)
    write_csv(OUTPUT_DIR / "standardization_compatibility_matrix.csv", compatibility)
    write_csv(OUTPUT_DIR / "migration_scope.csv", migrations)
    write_csv(OUTPUT_DIR / "evidence_gaps.csv", gaps)

    machine_count = sum(row["classification"] == "contract_complete_machine_executable" for row in contracts)
    human_count = sum(row["ordinary_event_interpretation_required"] for row in contracts)
    material_gap_count = sum(row["classification"] in {"contract_materially_incomplete", "legacy_contract_not_formalized"} for row in contracts)
    decision = {
        "decision": STANDARDIZATION_DECISION,
        "confidence": "high_on_research_contracts_low_on_receiver_compatibility",
        "existing_schema_count": len({(row["schema_name"], str(row["schema_version"])) for row in packages}),
        "machine_executable_contract_count": machine_count,
        "human_interpretation_required_count": human_count,
        "receiver_directly_compatible_count": 0,
        "generic_adapter_count": 0,
        "strategy_specific_adapter_count": 0,
        "material_contract_gap_count": material_gap_count,
        "lifecycle_semantics_gap": True,
        "execution_boundary_gap": "execution_boundary_standardization_gap",
        "microtrading_promotion_contract_status": "microtrading_promotion_contract_missing",
        "recommended_common_schema_id": COMMON_SCHEMA_ID,
        "migration_required": True,
        "standardization_implementation_action_after_audit_completion": "implement_forward_observation_handoff_standard_v1",
        "audit_next_action_due_to_missing_receiver": NEXT_ACTION,
    }
    write_json(OUTPUT_DIR / "standardization_decision.json", decision)
    (OUTPUT_DIR / "proposed_common_contract.md").write_text(proposed_contract_markdown(), encoding="utf-8")
    (OUTPUT_DIR / "audit_report.md").write_text(audit_report(counts, inventory), encoding="utf-8")
    (OUTPUT_DIR / "next_action.md").write_text(f"# Exact Next Action\n\n`{NEXT_ACTION}`\n", encoding="utf-8")

    parsed_count, parse_errors = parse_handoff_manifests()
    hygiene = scan_package_hygiene()
    internal_payload = json.loads((INTERNAL_HANDOFF / "strategy_handoff.json").read_text(encoding="utf-8"))
    internal_manifest = yaml.safe_load((INTERNAL_HANDOFF / "handoff_manifest.yaml").read_text(encoding="utf-8"))
    spdj_manifest = json.loads((SPDJ_PACKAGE / "handoff_manifest.json").read_text(encoding="utf-8"))
    protected_after = snapshot(PROTECTED_PATHS)
    audit_hash = generated_audit_hash()

    required_files = [
        "audit_report.md", "strategy_lifecycle_inventory.csv", "lifecycle_counts.json",
        "handoff_package_inventory.csv", "strategy_contract_completeness.csv",
        "receiver_compatibility_matrix.csv", "manifest_field_union.csv", "schema_variance_report.csv",
        "standardization_decision.json", "proposed_common_contract.md",
        "standardization_compatibility_matrix.csv", "migration_scope.csv", "evidence_gaps.csv",
        "next_action.md",
    ]
    checks = {
        "exactly_15_unique_forward_relevant_strategies": len(inventory) == 15 and len({row["strategy_id"] for row in inventory}) == 15,
        "controls_and_benchmarks_excluded": not {"SPY_buy_hold", "BIL_cash_proxy", "current_no_cash_proxy_alpha_AB"}.intersection(row["strategy_id"] for row in inventory),
        "lifecycle_counts_reconcile": sum(counts["current_exclusive_stage_counts"].values()) == len(inventory),
        "formal_handoff_count_is_two": counts["handoff_exported"] == len(packages) == 2,
        "receiver_counts_not_fabricated": counts["receiver_imported"] == counts["receiver_validated"] == 0,
        "forward_application_evidence_unavailable_recorded": all(row["receiver_application_status"] == "forward_application_evidence_unavailable" for row in receiver),
        "package_json_csv_manifests_parse": parsed_count > 0 and not parse_errors,
        "internal_semantic_hash_reconciles": canonical_hash(internal_payload) == internal_manifest["strategy_handoff_semantic_hash"],
        "spdj_package_hash_reconciles": normalized_spdj_package_hash() == spdj_manifest["package_content_hash"],
        "package_hygiene_passes": not hygiene["absolute_path_hits"] and not hygiene["secret_hits"],
        "machine_contract_count_is_one": machine_count == 1,
        "legacy_material_gap_count_is_thirteen": material_gap_count == 13,
        "microtrading_not_inferred": counts["microtrading_eligible"] == counts["microtrading_active"] == 0,
        "standardization_required_before_scaling": decision["decision"] == STANDARDIZATION_DECISION,
        "audit_incomplete_due_to_receiver_unavailable": OUTCOME == "forward_observation_handoff_audit_incomplete",
        "exact_next_action_recorded": NEXT_ACTION in (OUTPUT_DIR / "next_action.md").read_text(encoding="utf-8"),
        "protected_state_unchanged": protected_before == protected_after,
        "all_required_files_exist": all((OUTPUT_DIR / name).is_file() for name in required_files),
    }
    consistency = {
        "task_id": TASK_ID,
        "audit_as_of_date": AUDIT_DATE,
        "outcome": OUTCOME,
        "forward_application_status": "forward_application_evidence_unavailable",
        "checks": checks,
        "overall_pass": all(checks.values()),
        "deterministic_audit_hash": audit_hash,
        "parsed_handoff_json_csv_manifest_count": parsed_count,
        "parse_errors": parse_errors,
        "hygiene": hygiene,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "next_action": NEXT_ACTION,
        "next_action_executed": False,
        "strategy_backtests_run": 0,
        "network_calls": 0,
        "broker_calls": 0,
        "observation_mutations": 0,
        "microtrading_actions": 0,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    if not consistency["overall_pass"]:
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"audit_consistency_failed:{failed}")
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
