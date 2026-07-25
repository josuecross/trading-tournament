from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from run_strategy_lab import (
    ALLOWED_IMPLEMENTATION,
    ALLOWED_LANES,
    ALLOWED_NEXT,
    ALLOWED_STATUSES,
    ALLOWED_TIERS,
    validate_registry_data,
)
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "reconcile_angl_registry_schema_validation_v1"
MODE = "standardization-patch"
STAGE = "correction"
OUTPUT_DIR = ROOT / "evidence" / "standardization" / TASK_ID / "latest"

STRATEGY_REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
ROADMAP = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"

VALIDATION_DIR = ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest"
METHODOLOGY_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / "angl_80_20_portfolio_construction_methodology_correction_v1"
    / "latest"
)
ONBOARDING_DIR = (
    ROOT
    / "evidence"
    / "paper_demo"
    / "onboard_angl_diversifier_paper_demo_observation_v1"
    / "latest"
)
FORWARD_CORRECTION_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / "correct_angl_forward_boundary_and_data_freshness_v1"
    / "latest"
)
EXPLORATION_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "rerun_fast_source_library_blocked_candidates_v3"
    / "latest"
)

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
DISPLAY_NAME = "ICE/VanEck US Fallen Angel ANGL"
ARCHITECTURE = "structural_fallen_angel_credit_sleeve"
SOURCE_LINEAGE = "strategy_source_library_refresh_v1"
INSTRUMENT_UNIVERSE = "ANGL"
VALIDATED_PORTFOLIO_USE = "80pct_frozen_reference_20pct_ANGL_monthly_rebalanced"
EXPLORATION_TRIAL_ID = (
    "rerun_fast_source_v3__ice_vaneck_us_fallen_angel_angl_v1__data_feasibility_adjustment_child"
)
EXPLORATION_PARENT_TRIAL_ID = "fast_source_v3__ice_vaneck_us_fallen_angel_angl_v1__canonical"
VALIDATION_TRIAL_ID = "validation_angl__ice_vaneck_us_fallen_angel_angl_v1__validation_variant_child"
METHODOLOGY_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
OBSERVATION_NEXT_ACTION = "initialize_angl_after_next_completed_common_session_v1"
PROCESS_OUTCOME_SUCCESS = "registry_schema_reconciliation_completed"
PROCESS_OUTCOME_BLOCKED = "registry_schema_reconciliation_blocked"
PROJECT_NEXT_ACTION_SUCCESS = "refresh_strategy_source_library_v2"
PROJECT_NEXT_ACTION_BLOCKED = "direction_owner_review_angl_registry_schema_block_v1"
FROZEN_PARAMETERS = {
    "allocation_within_assigned_diversifier_sleeve": {"ANGL": 1.0},
    "assigned_portfolio_sleeve_weight": 0.2,
    "timing_rule": "none",
    "portfolio_rebalance_frequency": "monthly",
}
BENCHMARKS = (
    "frozen_current_active_vm_dsr_usci_combo",
    "HYG_buy_hold",
    "monthly_rebalanced_50_50_HYG_JNK",
)

SOURCE_OF_TRUTH_PATHS = [
    STRATEGY_REGISTRY,
    ACTIVE_OBSERVATIONS,
    RESEARCH_QUEUE,
    FAMILY_LEDGER,
    ROADMAP,
]
INPUT_EVIDENCE_FILES = [
    VALIDATION_DIR / "strategy_cards.csv",
    VALIDATION_DIR / "trial_ledger.csv",
    VALIDATION_DIR / "outcome_summary.csv",
    METHODOLOGY_DIR / "strategy_cards.csv",
    METHODOLOGY_DIR / "trial_ledger.csv",
    METHODOLOGY_DIR / "outcome_summary.csv",
    ONBOARDING_DIR / "strategy_cards.csv",
    ONBOARDING_DIR / "paper_demo_observations.csv",
    FORWARD_CORRECTION_DIR / "strategy_cards.csv",
    FORWARD_CORRECTION_DIR / "paper_demo_observations.csv",
    FORWARD_CORRECTION_DIR / "outcome_summary.csv",
    FORWARD_CORRECTION_DIR / "consistency_check.json",
    EXPLORATION_DIR / "trial_ledger.csv",
]
FORBIDDEN_FLAGS = {
    "backtest_run": False,
    "angl_validation_rerun": False,
    "robustness_run": False,
    "strategy_discovery": False,
    "parameter_or_instrument_change": False,
    "promotion_or_eligibility_decision": False,
    "paper_demo_activation": False,
    "observation_initialization": False,
    "provider_download": False,
    "broker_account_order_or_real_money_action": False,
    "registry_schema_redesign": False,
    "broad_registry_cleanup": False,
    "source_library_refresh_started": False,
}


def rel(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_registry_text() -> str:
    with STRATEGY_REGISTRY.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "standardization" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_record_span(text: str, strategy_id: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith("- id: ")]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "".join(lines[start:end])
        identifiers = (
            f"- id: {strategy_id}\r\n",
            f"- id: {strategy_id}\n",
            f"  strategy_id: {strategy_id}\r\n",
            f"  strategy_id: {strategy_id}\n",
        )
        if any(identifier in block for identifier in identifiers):
            return start, end
    return None


def replace_record_text(text: str, strategy_id: str, record: dict[str, Any]) -> str:
    lines = text.splitlines(keepends=True)
    span = find_record_span(text, strategy_id)
    if span is None:
        raise ValueError(f"Missing existing registry record for {strategy_id}")
    newline = "\r\n" if "\r\n" in text else "\n"
    replacement = yaml.safe_dump([record], sort_keys=False, width=120, allow_unicode=False)
    if newline == "\r\n":
        replacement = replacement.replace("\n", "\r\n")
    start, end = span
    lines[start:end] = replacement.splitlines(keepends=True)
    result = "".join(lines)
    if not result.endswith(newline):
        result += newline
    return result


def atomic_write_registry_text(text: str) -> None:
    temporary = STRATEGY_REGISTRY.with_suffix(".yaml.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, STRATEGY_REGISTRY)


def matching_strategy_records(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in registry.get("strategies", [])
        if isinstance(row, dict) and (row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID)
    ]


def matching_observations(active: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in active.get("active_observations", [])
        if isinstance(row, dict)
        and (
            row.get("observation_id") == OBSERVATION_ID
            or (
                row.get("strategy_id") == STRATEGY_ID
                and row.get("entity_type") == "paper_demo_observation"
            )
        )
    ]


def validate_authoritative_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    missing = [rel(path) for path in INPUT_EVIDENCE_FILES if not path.exists()]
    if missing:
        raise ValueError(f"Missing required authoritative evidence: {missing}")

    validation_outcome = read_csv_rows(VALIDATION_DIR / "outcome_summary.csv")
    methodology_outcome = read_csv_rows(METHODOLOGY_DIR / "outcome_summary.csv")
    corrected_outcome = read_csv_rows(FORWARD_CORRECTION_DIR / "outcome_summary.csv")
    if len(validation_outcome) != 1 or validation_outcome[0].get("outcome") != "validation_positive":
        raise ValueError("ANGL validation_positive evidence is absent or ambiguous")
    if len(methodology_outcome) != 1 or methodology_outcome[0].get("outcome") != "validation_positive":
        raise ValueError("ANGL methodology-correction validation_positive evidence is absent or ambiguous")
    if len(corrected_outcome) != 1:
        raise ValueError("ANGL forward-boundary correction outcome is absent or ambiguous")
    corrected = corrected_outcome[0]
    expected = {
        "strategy_stage": "paper_demo_eligible",
        "strategy_outcome": "paper_demo_eligible",
        "observation_stage": "blocked",
        "observation_outcome": "observation_invalid_or_incomplete",
        "primary_failure_reason": "methodology_failure",
        "next_action": OBSERVATION_NEXT_ACTION,
    }
    mismatches = {field: (corrected.get(field), value) for field, value in expected.items() if corrected.get(field) != value}
    if mismatches:
        raise ValueError(f"ANGL forward-boundary correction evidence mismatch: {mismatches}")
    return validation_outcome[0], corrected


def corrected_registry_record(current: dict[str, Any]) -> dict[str, Any]:
    record = copy.deepcopy(current)
    record.update(
        {
            "id": STRATEGY_ID,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "family": FAMILY_ID,
            "strategy_family": FAMILY_ID,
            "display_name": DISPLAY_NAME,
            "entity_type": "strategy_configuration",
            "strategy_architecture": ARCHITECTURE,
            "source_or_research_lineage": SOURCE_LINEAGE,
            "instrument_universe": INSTRUMENT_UNIVERSE,
            "parameters": FROZEN_PARAMETERS,
            "benchmark_or_control": list(BENCHMARKS),
            "lane": "paper_forward",
            "stage": "paper_demo_eligible",
            "outcome": "paper_demo_eligible",
            "instrument_family": "ETF",
            "version": "v1",
            "parent_id": METHODOLOGY_TRIAL_ID,
            "credibility_tier": "tier4_paper_forward",
            "evidence_tier": "tier4_paper_forward",
            "status": "gated",
            "current_status": "paper_demo_eligible",
            "route": "diversifier_only",
            "role": "diversifier_only",
            "rules_frozen": True,
            "paper_forward_active": False,
            "paper_demo_active": False,
            "paper_demo_eligible": True,
            "implementation_status": "implemented",
            "data_source": "existing_adjusted_etf_cache_and_frozen_reference_virtual_nav",
            "evidence_source": "correct_angl_forward_boundary_and_data_freshness_v1",
            "latest_evidence_path": rel(FORWARD_CORRECTION_DIR),
            "latest_known_result_summary": (
                "ANGL remains paper/demo eligible only as the validated 20% diversifier sleeve; "
                "the separate observation is blocked after the forward-boundary methodology correction."
            ),
            "validation_trial_id": VALIDATION_TRIAL_ID,
            "parent_validation_trial_id": EXPLORATION_TRIAL_ID,
            "methodology_correction_trial_id": METHODOLOGY_TRIAL_ID,
            "methodology_correction_parent_trial_id": VALIDATION_TRIAL_ID,
            "validation_lineage": f"{EXPLORATION_TRIAL_ID}|{VALIDATION_TRIAL_ID}|{METHODOLOGY_TRIAL_ID}",
            "allocation_rule": "100% ANGL within assigned 20% diversifier sleeve",
            "timing_rule": "none",
            "validated_portfolio_use": VALIDATED_PORTFOLIO_USE,
            "standalone_100pct_angl_observation_approved": False,
            "no_independent_strategy_created": True,
            "observation_id": OBSERVATION_ID,
            "observation_entity_type": "paper_demo_observation",
            "observation_stage": "blocked",
            "observation_outcome": "observation_invalid_or_incomplete",
            "observation_failure_reason": "methodology_failure",
            "observation_adaptation_label": "paper_demo_observation_fix",
            "observation_next_action": OBSERVATION_NEXT_ACTION,
            "observation_evidence_path": rel(FORWARD_CORRECTION_DIR),
            "broker_integration": False,
            "paper_orders": False,
            "live_orders": False,
            "real_money_authorized": False,
            "real_money_recommendation": False,
            "no_real_money_recommendation": True,
            "allowed_next_action": "no_action",
            "allowed_next_actions": ["no_action"],
            "risk_framework_status": "paper_demo_eligible_diversifier_only_observation_blocked",
            "paper_forward_allowed_by_risk_framework": True,
            "promotion_decision": "paper_demo_eligible_direction_owner_approved_diversifier_only",
            "promotion_review_required": False,
            "promotion_reason": (
                "Direction-owner paper/demo eligibility is preserved only for the validated 20% ANGL diversifier sleeve; "
                "the separate observation remains blocked."
            ),
            "promotion_blockers": "diversifier_only;observation_blocked;no_real_money_authorization",
            "promotion_requirements": (
                "A valid separately initialized paper/demo observation is required before any later operational review; "
                "no automatic promotion is authorized."
            ),
            "demotion_or_kill_criteria": (
                "Missing data, reconciliation failure, duplicate virtual trade, invalid weight, stale signal, "
                "unexplained NAV discrepancy, or direction-owner decision."
            ),
            "primary_failure_mode": "observation_methodology_failure_separate_from_validation_positive",
            "duplication_risk": "not_an_independent_family",
            "risk_budget_status": "diversifier_only_observation_blocked",
            "evidence_needed": "valid_forward_observation_after_next_completed_common_session",
            "duplicate_of": "",
            "blocked_reason": "separate_observation_blocked_forward_boundary_methodology_failure",
            "notes": (
                "Strategy validation remains positive and paper/demo eligible only as the 20% ANGL sleeve in the "
                "validated monthly 80/20 construction. The separate observation is blocked, has no forward evidence, "
                f"and retains next_action={OBSERVATION_NEXT_ACTION}. No standalone or real-money approval exists."
            ),
            "instrument_lane": "ETF",
            "candidate_exhaustive_run": False,
            "candidate_exhaustive_recommended": False,
            "frozen": True,
        }
    )
    record.pop("next_action", None)
    return record


def required_semantics_complete(record: dict[str, Any]) -> bool:
    expected = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": INSTRUMENT_UNIVERSE,
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "route": "diversifier_only",
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "methodology_correction_trial_id": METHODOLOGY_TRIAL_ID,
        "observation_id": OBSERVATION_ID,
        "observation_stage": "blocked",
        "observation_outcome": "observation_invalid_or_incomplete",
        "observation_next_action": OBSERVATION_NEXT_ACTION,
    }
    if any(record.get(field) != value for field, value in expected.items()):
        return False
    if record.get("parameters") != FROZEN_PARAMETERS:
        return False
    if set(record.get("benchmark_or_control", [])) != set(BENCHMARKS):
        return False
    if record.get("standalone_100pct_angl_observation_approved") is not False:
        return False
    if record.get("real_money_authorized") is not False:
        return False
    rendered = yaml.safe_dump(record, sort_keys=True).lower()
    return "unknown" not in rendered and "unmapped" not in rendered


def angl_errors(validation: dict[str, Any]) -> list[str]:
    return [error for error in validation.get("errors", []) if STRATEGY_ID in str(error)]


def hrp_errors(validation: dict[str, Any]) -> list[str]:
    return [error for error in validation.get("errors", []) if "lopez_de_prado_hrp_five_asset_v1" in str(error)]


def field_mapping_rows(before_record: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    mappings = {
        "allowed_next_actions": {
            "current_value": before_record.get("allowed_next_actions", ""),
            "accepted_schema_or_enum": "required non-empty list; values must use allowed strategy actions",
            "minimum_compliant_correction": ["no_action"],
            "evidence": "strategy_lab registry schema plus blocked observation entity separation",
        },
        "promotion_reason": {
            "current_value": before_record.get("promotion_reason", ""),
            "accepted_schema_or_enum": "required non-empty string",
            "minimum_compliant_correction": (
                "preserve diversifier-only eligibility and disclose the separately blocked observation"
            ),
            "evidence": rel(ONBOARDING_DIR / "strategy_cards.csv"),
        },
        "primary_failure_mode": {
            "current_value": before_record.get("primary_failure_mode", ""),
            "accepted_schema_or_enum": "required non-empty string",
            "minimum_compliant_correction": "observation_methodology_failure_separate_from_validation_positive",
            "evidence": rel(FORWARD_CORRECTION_DIR / "outcome_summary.csv"),
        },
        "lane": {
            "current_value": before_record.get("lane", ""),
            "accepted_schema_or_enum": "|".join(sorted(ALLOWED_LANES)),
            "minimum_compliant_correction": "paper_forward",
            "evidence": "strategy registry schema; ANGL paper/demo eligibility evidence",
        },
        "credibility_tier": {
            "current_value": before_record.get("credibility_tier", ""),
            "accepted_schema_or_enum": "|".join(sorted(ALLOWED_TIERS)),
            "minimum_compliant_correction": "tier4_paper_forward",
            "evidence": "strategy registry schema; ANGL paper/demo eligibility evidence",
        },
        "status": {
            "current_value": before_record.get("status", ""),
            "accepted_schema_or_enum": "|".join(sorted(ALLOWED_STATUSES)),
            "minimum_compliant_correction": "gated",
            "evidence": "strategy registry schema; observation remains blocked and inactive",
        },
        "implementation_status": {
            "current_value": before_record.get("implementation_status", ""),
            "accepted_schema_or_enum": "|".join(sorted(ALLOWED_IMPLEMENTATION)),
            "minimum_compliant_correction": "implemented",
            "evidence": "strategy registry schema; existing validated brokerless implementation",
        },
        "allowed_next_action": {
            "current_value": before_record.get("allowed_next_action", ""),
            "accepted_schema_or_enum": "|".join(sorted(ALLOWED_NEXT)),
            "minimum_compliant_correction": "no_action",
            "evidence": (
                "strategy action uses schema enum; observation action remains "
                f"{OBSERVATION_NEXT_ACTION} on the observation entity"
            ),
        },
    }
    rows: list[dict[str, Any]] = []
    for error in errors:
        match = re.search(r"(?:missing required field|invalid) ([a-zA-Z0-9_]+)", error)
        field = match.group(1) if match else ""
        mapping = mappings.get(field, {})
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "field": field,
                "current_value": mapping.get("current_value", ""),
                "accepted_schema_or_enum": mapping.get("accepted_schema_or_enum", ""),
                "reason_invalid": error,
                "minimum_compliant_correction": mapping.get("minimum_compliant_correction", ""),
                "authoritative_evidence": mapping.get("evidence", ""),
            }
        )
    return rows


def load_trial_lineage() -> list[dict[str, Any]]:
    exploration_rows = [
        row
        for row in read_csv_rows(EXPLORATION_DIR / "trial_ledger.csv")
        if row.get("strategy_id") == STRATEGY_ID and row.get("trial_id") == EXPLORATION_TRIAL_ID
    ]
    validation_rows = read_csv_rows(VALIDATION_DIR / "trial_ledger.csv")
    methodology_rows = read_csv_rows(METHODOLOGY_DIR / "trial_ledger.csv")
    if len(exploration_rows) != 1 or len(validation_rows) != 1 or len(methodology_rows) != 1:
        raise ValueError("ANGL exploratory, validation, or methodology trial lineage is missing or ambiguous")
    rows = []
    for source in (exploration_rows[0], validation_rows[0], methodology_rows[0]):
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "family_id": FAMILY_ID,
                "entity_type": "experiment_trial",
                "trial_id": source.get("trial_id", ""),
                "parent_trial_id": source.get("parent_trial_id", ""),
                "stage": source.get("stage", ""),
                "adaptation_label": source.get("adaptation_label", ""),
                "changed_fields": source.get("changed_fields_from_parent", ""),
                "outcome": source.get("outcome", ""),
                "failure_reason": source.get("primary_failure_reason", source.get("failure_reason", "")),
                "next_action": source.get("next_action", ""),
                "read_only": True,
                "new_experiment_trial_created": False,
            }
        )
    return rows


def before_after_rows(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    fields = sorted(set(before) | set(after))
    return [
        {
            "strategy_id": STRATEGY_ID,
            "field": field,
            "before_value": before.get(field, ""),
            "after_value": after.get(field, ""),
            "changed": before.get(field) != after.get(field),
        }
        for field in fields
    ]


def run() -> dict[str, Any]:
    source_hashes_before = hash_paths(SOURCE_OF_TRUTH_PATHS)
    evidence_hashes_before = hash_paths(INPUT_EVIDENCE_FILES)
    registry_text_before = read_registry_text()
    registry_before = yaml.safe_load(registry_text_before) or {}
    active_before = read_yaml(ACTIVE_OBSERVATIONS)
    validation_before = validate_registry_data(registry_before)
    before_errors = angl_errors(validation_before)
    before_hrp_errors = hrp_errors(validation_before)
    records_before = matching_strategy_records(registry_before)
    observations_before = matching_observations(active_before)

    process_outcome = PROCESS_OUTCOME_BLOCKED
    process_failure_reason = "status_reconciliation_required"
    project_next_action = PROJECT_NEXT_ACTION_BLOCKED
    strategy_records_updated = 0
    observation_records_updated = 0
    corrected_record: dict[str, Any] = records_before[0] if len(records_before) == 1 else {}
    authoritative_inputs_valid = False
    proposed_validation: dict[str, Any] = {"passed": False, "errors": ["proposal not built"], "warnings": []}

    try:
        validate_authoritative_inputs()
        authoritative_inputs_valid = True
        if len(records_before) != 1:
            raise ValueError(f"Expected exactly one ANGL registry record, found {len(records_before)}")
        if len(observations_before) != 1:
            raise ValueError(f"Expected exactly one ANGL observation record, found {len(observations_before)}")
        observation = observations_before[0]
        expected_observation = {
            "stage": "blocked",
            "outcome": "observation_invalid_or_incomplete",
            "failure_reason": "methodology_failure",
            "adaptation_label": "paper_demo_observation_fix",
            "next_action": OBSERVATION_NEXT_ACTION,
            "paper_forward_active": False,
        }
        mismatches = {
            field: (observation.get(field), value)
            for field, value in expected_observation.items()
            if observation.get(field) != value
        }
        if mismatches:
            raise ValueError(f"Authoritative ANGL observation mismatch: {mismatches}")

        corrected_record = corrected_registry_record(records_before[0])
        proposed_registry = copy.deepcopy(registry_before)
        proposed_registry["strategies"] = [
            corrected_record
            if isinstance(row, dict) and (row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID)
            else row
            for row in proposed_registry.get("strategies", [])
        ]
        proposed_validation = validate_registry_data(proposed_registry)
        if angl_errors(proposed_validation):
            raise ValueError(f"Proposed ANGL record remains invalid: {angl_errors(proposed_validation)}")
        if hrp_errors(proposed_validation):
            raise ValueError(f"Proposed registry introduces or retains HRP errors: {hrp_errors(proposed_validation)}")
        unrelated_before = [error for error in validation_before.get("errors", []) if STRATEGY_ID not in error]
        unrelated_after = [error for error in proposed_validation.get("errors", []) if STRATEGY_ID not in error]
        if unrelated_after != unrelated_before:
            raise ValueError("Proposed ANGL patch changes unrelated validator errors")
        if not required_semantics_complete(corrected_record):
            raise ValueError("Corrected ANGL record does not preserve all required semantic decisions")

        registry_text_after = replace_record_text(registry_text_before, STRATEGY_ID, corrected_record)
        atomic_write_registry_text(registry_text_after)
        written_registry = read_yaml(STRATEGY_REGISTRY)
        written_validation = validate_registry_data(written_registry)
        if written_validation != proposed_validation:
            atomic_write_registry_text(registry_text_before)
            raise ValueError("Written registry does not match the validated in-memory proposal")

        strategy_records_updated = int(registry_text_after != registry_text_before)
        process_outcome = PROCESS_OUTCOME_SUCCESS
        process_failure_reason = ""
        project_next_action = PROJECT_NEXT_ACTION_SUCCESS
    except (ValueError, OSError, yaml.YAMLError) as exc:
        process_failure_reason = (
            "methodology_failure" if "methodology" in str(exc).lower() else "status_reconciliation_required"
        )
        proposed_validation = {
            "passed": False,
            "errors": [str(exc)],
            "warnings": [],
        }

    registry_after = read_yaml(STRATEGY_REGISTRY)
    active_after = read_yaml(ACTIVE_OBSERVATIONS)
    validation_after = validate_registry_data(registry_after)
    records_after = matching_strategy_records(registry_after)
    observations_after = matching_observations(active_after)
    source_hashes_after = hash_paths(SOURCE_OF_TRUTH_PATHS)
    evidence_hashes_after = hash_paths(INPUT_EVIDENCE_FILES)

    trial_rows = load_trial_lineage()
    mapping_rows = field_mapping_rows(records_before[0] if records_before else {}, before_errors)
    final_record = records_after[0] if len(records_after) == 1 else corrected_record
    observation_row = observations_after[0] if len(observations_after) == 1 else {}
    source_changes = [
        {
            "path": path,
            "before_sha256": source_hashes_before[path],
            "after_sha256": source_hashes_after[path],
            "changed": source_hashes_before[path] != source_hashes_after[path],
            "change_permitted": (
                path == rel(STRATEGY_REGISTRY)
                and source_hashes_before[path] != source_hashes_after[path]
                and process_outcome == PROCESS_OUTCOME_SUCCESS
            ),
        }
        for path in source_hashes_before
    ]
    changed_paths = [row["path"] for row in source_changes if row["changed"]]
    all_changes_permitted = all(not row["changed"] or row["change_permitted"] for row in source_changes)
    evidence_unchanged = evidence_hashes_before == evidence_hashes_after
    final_angl_errors = angl_errors(validation_after)
    final_hrp_errors = hrp_errors(validation_after)
    observation_unchanged = source_hashes_before[rel(ACTIVE_OBSERVATIONS)] == source_hashes_after[rel(ACTIVE_OBSERVATIONS)]
    no_new_errors = [
        error for error in validation_after.get("errors", []) if error not in validation_before.get("errors", [])
    ] == []
    consistency_passed = bool(
        process_outcome == PROCESS_OUTCOME_SUCCESS
        and authoritative_inputs_valid
        and len(before_errors) == 8
        and len(records_after) == 1
        and len(observations_after) == 1
        and not final_angl_errors
        and not final_hrp_errors
        and validation_after.get("passed") is True
        and no_new_errors
        and required_semantics_complete(final_record)
        and observation_row.get("stage") == "blocked"
        and observation_row.get("outcome") == "observation_invalid_or_incomplete"
        and observation_row.get("failure_reason") == "methodology_failure"
        and observation_row.get("next_action") == OBSERVATION_NEXT_ACTION
        and observation_row.get("paper_forward_active") is False
        and observation_unchanged
        and all_changes_permitted
        and evidence_unchanged
    )

    clean_output_dir()
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "strategy_stage": final_record.get("stage", ""),
        "strategy_outcome": final_record.get("outcome", ""),
        "observation_id": OBSERVATION_ID,
        "observation_stage": observation_row.get("stage", ""),
        "observation_outcome": observation_row.get("outcome", ""),
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": strategy_records_updated,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": len(trial_rows),
        "paper_demo_observations_created": 0,
        "paper_demo_observations_updated": observation_records_updated,
        "benchmark_references": len(BENCHMARKS),
        "process_tasks": 1,
        "new_research_candidates": 0,
        "exact_project_next_action": project_next_action,
        "consistency_passed": consistency_passed,
    }
    write_yaml(OUTPUT_DIR / "patch_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "validator_errors_before.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "field": row["field"],
                "current_value": row["current_value"],
                "validator_error": row["reason_invalid"],
            }
            for row in mapping_rows
        ],
        ["strategy_id", "field", "current_value", "validator_error"],
    )
    write_csv(
        OUTPUT_DIR / "field_mapping_decisions.csv",
        mapping_rows,
        [
            "strategy_id",
            "field",
            "current_value",
            "accepted_schema_or_enum",
            "reason_invalid",
            "minimum_compliant_correction",
            "authoritative_evidence",
        ],
    )
    strategy_card = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": INSTRUMENT_UNIVERSE,
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": BENCHMARKS,
        "stage": final_record.get("stage", ""),
        "outcome": final_record.get("outcome", ""),
        "route": final_record.get("route", ""),
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "methodology_correction_trial_id": METHODOLOGY_TRIAL_ID,
        "observation_id": OBSERVATION_ID,
        "observation_stage": observation_row.get("stage", ""),
        "observation_next_action": observation_row.get("next_action", ""),
        "standalone_paper_demo_approved": False,
        "real_money_authorized": False,
    }
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        [strategy_card],
        list(strategy_card),
    )
    trial_fields = [
        "strategy_id",
        "family_id",
        "entity_type",
        "trial_id",
        "parent_trial_id",
        "stage",
        "adaptation_label",
        "changed_fields",
        "outcome",
        "failure_reason",
        "next_action",
        "read_only",
        "new_experiment_trial_created",
    ]
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows, trial_fields)
    observation_output = {
        "observation_id": observation_row.get("observation_id", ""),
        "strategy_id": observation_row.get("strategy_id", ""),
        "entity_type": observation_row.get("entity_type", ""),
        "stage": observation_row.get("stage", ""),
        "outcome": observation_row.get("outcome", ""),
        "failure_reason": observation_row.get("failure_reason", ""),
        "adaptation_label": observation_row.get("adaptation_label", ""),
        "next_action": observation_row.get("next_action", ""),
        "paper_forward_active": observation_row.get("paper_forward_active", ""),
        "target_weights": observation_row.get("target_weights", {}),
        "created": False,
        "updated": False,
    }
    write_csv(OUTPUT_DIR / "paper_demo_observations.csv", [observation_output], list(observation_output))
    process_row = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "outcome": process_outcome,
        "failure_reason": process_failure_reason,
        "exact_next_action": project_next_action,
        "counted_as_strategy": False,
        "counted_as_trial": False,
        "counted_as_observation": False,
    }
    write_csv(OUTPUT_DIR / "process_task_log.csv", [process_row], list(process_row))
    benchmark_rows = [
        {
            "benchmark_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "counted_as_observation": False,
        }
        for benchmark in BENCHMARKS
    ]
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        [
            "benchmark_id",
            "entity_type",
            "stage",
            "counted_as_strategy",
            "counted_as_trial",
            "counted_as_observation",
        ],
    )
    write_csv(
        OUTPUT_DIR / "registry_record_before_after.csv",
        before_after_rows(records_before[0] if records_before else {}, final_record),
        ["strategy_id", "field", "before_value", "after_value", "changed"],
    )
    after_result_rows = [
        {
            "validator_passed": validation_after.get("passed", False),
            "total_errors": len(validation_after.get("errors", [])),
            "angl_errors": len(final_angl_errors),
            "hrp_errors": len(final_hrp_errors),
            "new_errors_caused_by_patch": not no_new_errors,
            "errors": validation_after.get("errors", []),
        }
    ]
    write_csv(
        OUTPUT_DIR / "validator_results_after.csv",
        after_result_rows,
        [
            "validator_passed",
            "total_errors",
            "angl_errors",
            "hrp_errors",
            "new_errors_caused_by_patch",
            "errors",
        ],
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        source_changes,
        ["path", "before_sha256", "after_sha256", "changed", "change_permitted"],
    )
    outcome_row = {
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": strategy_records_updated,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": len(trial_rows),
        "paper_demo_observations_created": 0,
        "paper_demo_observations_updated": observation_records_updated,
        "benchmark_references": len(BENCHMARKS),
        "process_tasks": 1,
        "new_research_candidates": 0,
        "strategy_stage": final_record.get("stage", ""),
        "strategy_outcome": final_record.get("outcome", ""),
        "observation_stage": observation_row.get("stage", ""),
        "observation_outcome": observation_row.get("outcome", ""),
        "observation_failure_reason": observation_row.get("failure_reason", ""),
        "project_next_action": project_next_action,
    }
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    failure_row = {
        "entity_type": "paper_demo_observation",
        "entity_id": OBSERVATION_ID,
        "stage": observation_row.get("stage", ""),
        "outcome": observation_row.get("outcome", ""),
        "failure_reason": observation_row.get("failure_reason", ""),
        "strategy_validation_failure": False,
    }
    write_csv(OUTPUT_DIR / "failure_reasons.csv", [failure_row], list(failure_row))
    next_action_rows = [
        {
            "entity_type": "paper_demo_observation",
            "entity_id": OBSERVATION_ID,
            "exact_next_action": OBSERVATION_NEXT_ACTION,
            "execute_now": False,
        },
        {
            "entity_type": "process_task",
            "entity_id": TASK_ID,
            "exact_next_action": project_next_action,
            "execute_now": False,
        },
    ]
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_action_rows,
        ["entity_type", "entity_id", "exact_next_action", "execute_now"],
    )
    consistency = {
        **FORBIDDEN_FLAGS,
        "task_id": TASK_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "consistency_passed": consistency_passed,
        "pre_patch_angl_validator_error_count": len(before_errors),
        "pre_patch_angl_validator_errors": before_errors,
        "pre_patch_hrp_validator_error_count": len(before_hrp_errors),
        "post_patch_registry_passed": validation_after.get("passed", False),
        "post_patch_angl_validator_error_count": len(final_angl_errors),
        "post_patch_hrp_validator_error_count": len(final_hrp_errors),
        "no_new_validator_errors_caused_by_patch": no_new_errors,
        "exactly_one_angl_strategy_record": len(records_after) == 1,
        "exactly_one_angl_observation_record": len(observations_after) == 1,
        "required_strategy_semantics_complete": required_semantics_complete(final_record),
        "strategy_remains_paper_demo_eligible": final_record.get("stage") == "paper_demo_eligible"
        and final_record.get("outcome") == "paper_demo_eligible",
        "strategy_remains_diversifier_only": final_record.get("route") == "diversifier_only",
        "observation_remains_blocked": observation_row.get("stage") == "blocked",
        "observation_remains_inactive": observation_row.get("paper_forward_active") is False,
        "observation_next_action_preserved": observation_row.get("next_action") == OBSERVATION_NEXT_ACTION,
        "active_observations_unchanged": observation_unchanged,
        "source_of_truth_hashes_before": source_hashes_before,
        "source_of_truth_hashes_after": source_hashes_after,
        "source_of_truth_changed_paths": changed_paths,
        "all_source_of_truth_changes_permitted": all_changes_permitted,
        "input_evidence_hashes_before": evidence_hashes_before,
        "input_evidence_hashes_after": evidence_hashes_after,
        "input_evidence_hashes_unchanged": evidence_unchanged,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": strategy_records_updated,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": len(trial_rows),
        "paper_demo_observations_created": 0,
        "paper_demo_observations_updated": observation_records_updated,
        "benchmark_references": len(BENCHMARKS),
        "process_tasks": 1,
        "new_research_candidates": 0,
        "exact_project_next_action": project_next_action,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    report = f"""# ANGL Registry Schema Reconciliation

## Outcome

`{process_outcome}`

The existing `{STRATEGY_ID}` registry record was mapped to the accepted registry schema without changing
the validated strategy rule, 20% diversifier-only approval, trial lineage, or paper/demo eligibility decision.

## Validator

- Pre-patch ANGL errors: `{len(before_errors)}`
- Post-patch ANGL errors: `{len(final_angl_errors)}`
- Post-patch HRP errors: `{len(final_hrp_errors)}`
- Entire registry passed: `{str(validation_after.get("passed", False)).lower()}`

The schema-facing representation is `lane=paper_forward`, `credibility_tier=tier4_paper_forward`,
`status=gated`, `implementation_status=implemented`, and `allowed_next_action=no_action`.
The semantic strategy fields remain `stage=paper_demo_eligible` and `outcome=paper_demo_eligible`.

## Observation

The existing `{OBSERVATION_ID}` record was not modified. It remains blocked with
`outcome=observation_invalid_or_incomplete`, `failure_reason=methodology_failure`, and
`next_action={OBSERVATION_NEXT_ACTION}`. No observation was initialized or activated.

## State Change

Only the existing ANGL block in `{rel(STRATEGY_REGISTRY)}` was eligible for modification.
No strategy, trial, observation, benchmark, or research candidate was created.

## Next Action

`{project_next_action}` was recorded but not executed.
"""
    write_text(OUTPUT_DIR / "patch_report.md", report)

    return {
        "task_id": TASK_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "pre_patch_angl_validator_errors": len(before_errors),
        "post_patch_angl_validator_errors": len(final_angl_errors),
        "post_patch_hrp_validator_errors": len(final_hrp_errors),
        "registry_validation_passed": validation_after.get("passed", False),
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": strategy_records_updated,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": len(trial_rows),
        "paper_demo_observations_created": 0,
        "paper_demo_observations_updated": observation_records_updated,
        "benchmark_references": len(BENCHMARKS),
        "process_tasks": 1,
        "new_research_candidates": 0,
        "exact_project_next_action": project_next_action,
        "consistency_passed": consistency_passed,
        "evidence_path": rel(OUTPUT_DIR),
    }
