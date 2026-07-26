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
from typing import Any, Iterable

import yaml

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "defer_angl_observation_data_lane_v1"
MODE = "active-direction-execution"
STAGE = "correction"
OUTPUT_DIR = ROOT / "evidence" / "lifecycle" / TASK_ID / "latest"

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PROCESS_OUTCOME_SUCCESS = "observation_data_lane_deferred"
PROCESS_OUTCOME_BLOCKED = "observation_data_lane_deferral_blocked"
PRIMARY_FAILURE_REASON = "data_or_comparability_failure"
BLOCKED_FAILURE_STATUS = "status_reconciliation_required"
OBSERVATION_NEXT_ACTION = (
    "revisit_angl_observation_only_after_material_data_capability_change_v1"
)
PROJECT_NEXT_ACTION = "refresh_strategy_source_library_v3"
BLOCKED_NEXT_ACTION = "direction_owner_review_angl_deferral_state_block_v1"
FINAL_DATA_OUTCOME = "canonical_observation_data_version_blocked"
LAST_ATTEMPTED_SESSION = "2026-07-24"
DEFERRED_REASON = "deterministic_canonical_common_session_data_not_available"
EVIDENCE_RELATIVE_PATH = f"evidence/lifecycle/{TASK_ID}/latest"

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = (
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
)
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = (
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
)

FINAL_CORRECTION_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / "correct_observation_market_data_versioning_and_serialization_v1"
    / "latest"
)
METHODOLOGY_CORRECTION_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / "angl_80_20_portfolio_construction_methodology_correction_v1"
    / "latest"
)
FORWARD_CORRECTION_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / "correct_angl_forward_boundary_and_data_freshness_v1"
    / "latest"
)
INITIALIZATION_DIR = (
    ROOT
    / "evidence"
    / "paper_demo"
    / "initialize_angl_after_next_completed_common_session_v1"
    / "latest"
)
VALIDATION_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / "angl_fallen_angel_diversifier_validation_v1"
    / "latest"
)
EXPLORATION_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "rerun_fast_source_library_blocked_candidates_v3"
    / "latest"
)
OPERATIONAL_DIR = ROOT / "paper_forward_observations" / OBSERVATION_ID
TRIAL_LEDGER_PATHS = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "rerun_fast_source_library_blocked_candidates_v3"
    / "latest"
    / "trial_ledger.csv",
    ROOT
    / "evidence"
    / "validation"
    / "angl_fallen_angel_diversifier_validation_v1"
    / "latest"
    / "trial_ledger.csv",
    ROOT
    / "evidence"
    / "correction"
    / "angl_80_20_portfolio_construction_methodology_correction_v1"
    / "latest"
    / "trial_ledger.csv",
)

AUTHORITATIVE_CORRECTION_FILES = (
    FINAL_CORRECTION_DIR / "correction_manifest.yaml",
    FINAL_CORRECTION_DIR / "correction_report.md",
    FINAL_CORRECTION_DIR / "cohort_commit_decision.csv",
    FINAL_CORRECTION_DIR / "provider_fetch_reproducibility.csv",
    FINAL_CORRECTION_DIR / "xlc_ohlc_violation_analysis.csv",
    FINAL_CORRECTION_DIR / "reference_input_sufficiency.csv",
    FINAL_CORRECTION_DIR / "common_session_sufficiency.csv",
    FINAL_CORRECTION_DIR / "failure_reasons.csv",
    FINAL_CORRECTION_DIR / "next_actions.csv",
    FINAL_CORRECTION_DIR / "consistency_check.json",
    FINAL_CORRECTION_DIR / "serialization_hash_reconciliation.csv",
    FINAL_CORRECTION_DIR / "outcome_summary.csv",
)
SOURCE_OF_TRUTH_PATHS = (
    REGISTRY_PATH,
    ACTIVE_OBSERVATIONS_PATH,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
)
PERMITTED_PATHS = {REGISTRY_PATH.resolve(), ACTIVE_OBSERVATIONS_PATH.resolve()}

STRATEGY_ALLOWED_CHANGES = {
    "next_action",
    "allowed_next_action",
    "latest_known_result_summary",
    "risk_framework_status",
    "promotion_blockers",
    "notes",
    "primary_failure_mode",
    "risk_budget_status",
    "evidence_needed",
    "blocked_reason",
    "observation_stage",
    "observation_failure_reason",
    "observation_next_action",
    "observation_evidence_path",
    "promotion_reason",
    "observation_semantic_stage",
    "observation_deferred_reason",
    "observation_automatic_remediation_attempts_exhausted",
    "observation_last_attempted_session",
    "observation_last_data_outcome",
}
OBSERVATION_ALLOWED_CHANGES = {
    "stage",
    "semantic_stage",
    "state",
    "current_status",
    "failure_reason",
    "defect_type",
    "next_action",
    "paper_demo_active",
    "forward_records_created",
    "valid_forward_record_count",
    "deferred_reason",
    "automatic_remediation_attempts_exhausted",
    "last_attempted_session",
    "last_data_outcome",
    "reopen_conditions",
    "elapsed_time_alone_reopen_condition",
    "june_18_record_classification",
    "latest_operational_update_id",
    "latest_operational_update_evidence_path",
}

REOPEN_CONDITIONS = (
    (
        "authorized_provider_deterministic_full_cohort",
        "An existing authorized provider produces deterministic canonical adjusted data "
        "and provenance for the full required cohort.",
    ),
    (
        "canonical_pipeline_materially_corrected_and_verified",
        "The existing canonical data pipeline is materially corrected and independently verified.",
    ),
    (
        "separately_approved_observation_methodology_change",
        "A separately approved auditable observation design changes the required data cohort.",
    ),
)


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: csv_value(row.get(field, "")) for field in fields}
            )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            width=120,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def all_files(directory: Path) -> list[Path]:
    return [path for path in sorted(directory.rglob("*")) if path.is_file()]


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "lifecycle" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output directory: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_yaml_text(path: Path) -> tuple[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(text) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{rel(path)} must contain a YAML mapping")
    return text, payload


def strategy_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID)
    ]


def observation_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in payload.get("active_observations", [])
        if isinstance(row, dict) and row.get("observation_id") == OBSERVATION_ID
    ]


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    return {
        field
        for field in set(before) | set(after)
        if before.get(field) != after.get(field)
    }


def find_list_record_span(text: str, first_line: str, next_pattern: str) -> tuple[int, int]:
    start_match = re.search(rf"(?m)^{re.escape(first_line)}\s*$", text)
    if not start_match:
        raise ValueError(f"Cannot find record start: {first_line}")
    next_match = re.search(next_pattern, text[start_match.end() :], flags=re.MULTILINE)
    end = len(text) if not next_match else start_match.end() + next_match.start()
    return start_match.start(), end


def replace_record_block(
    text: str,
    first_line: str,
    next_pattern: str,
    record: dict[str, Any],
) -> str:
    start, end = find_list_record_span(text, first_line, next_pattern)
    dumped = yaml.safe_dump(
        [record],
        sort_keys=False,
        allow_unicode=False,
        width=120,
        default_flow_style=False,
    )
    if not dumped.endswith("\n"):
        dumped += "\n"
    return text[:start] + dumped + text[end:]


def proposed_strategy_record(before: dict[str, Any]) -> dict[str, Any]:
    record = copy.deepcopy(before)
    record.update(
        {
            "next_action": OBSERVATION_NEXT_ACTION,
            "allowed_next_action": "no_action",
            "latest_known_result_summary": (
                "ANGL remains paper/demo eligible only as the validated 20% diversifier "
                "sleeve; its separate observation data lane is deferred after the final "
                "canonical cohort correction failed."
            ),
            "risk_framework_status": (
                "paper_demo_eligible_diversifier_only_observation_deferred"
            ),
            "promotion_blockers": (
                "diversifier_only;observation_deferred;no_real_money_authorization"
            ),
            "notes": (
                "Strategy validation remains positive and paper/demo eligible only as the "
                "20% ANGL sleeve in the validated monthly 80/20 construction. The separate "
                "observation is deferred, has no forward evidence, and may be revisited only "
                "after a material data capability or separately approved methodology change. "
                "No standalone or real-money approval exists."
            ),
            "primary_failure_mode": (
                "observation_data_or_comparability_failure_separate_from_validation_positive"
            ),
            "risk_budget_status": "diversifier_only_observation_deferred",
            "evidence_needed": (
                "material_data_capability_or_separately_approved_observation_methodology_change"
            ),
            "blocked_reason": (
                "separate_observation_deferred_data_or_comparability_failure"
            ),
            "observation_stage": "deferred",
            "observation_failure_reason": PRIMARY_FAILURE_REASON,
            "observation_next_action": OBSERVATION_NEXT_ACTION,
            "observation_evidence_path": EVIDENCE_RELATIVE_PATH,
            "promotion_reason": (
                "Direction-owner paper/demo eligibility remains limited to the validated "
                "20% ANGL diversifier sleeve; its separate observation data lane is deferred."
            ),
            "observation_semantic_stage": "deferred",
            "observation_deferred_reason": DEFERRED_REASON,
            "observation_automatic_remediation_attempts_exhausted": True,
            "observation_last_attempted_session": LAST_ATTEMPTED_SESSION,
            "observation_last_data_outcome": FINAL_DATA_OUTCOME,
        }
    )
    return record


def proposed_observation_record(before: dict[str, Any]) -> dict[str, Any]:
    record = copy.deepcopy(before)
    record.update(
        {
            "stage": "deferred",
            "semantic_stage": "deferred",
            "state": "deferred_observation_invalid_or_incomplete",
            "current_status": "deferred",
            "failure_reason": PRIMARY_FAILURE_REASON,
            "defect_type": "canonical_common_session_data_comparability_failure",
            "next_action": OBSERVATION_NEXT_ACTION,
            "paper_demo_active": False,
            "forward_records_created": 0,
            "valid_forward_record_count": 0,
            "deferred_reason": DEFERRED_REASON,
            "automatic_remediation_attempts_exhausted": True,
            "last_attempted_session": LAST_ATTEMPTED_SESSION,
            "last_data_outcome": FINAL_DATA_OUTCOME,
            "reopen_conditions": [condition_id for condition_id, _ in REOPEN_CONDITIONS],
            "elapsed_time_alone_reopen_condition": False,
            "june_18_record_classification": "historical_reconciliation_only",
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": EVIDENCE_RELATIVE_PATH,
        }
    )
    return record


def validate_strategy_semantics(record: dict[str, Any]) -> list[str]:
    expected = {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "strategy_configuration",
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "route": "diversifier_only",
        "validated_portfolio_use": "80pct_frozen_reference_20pct_ANGL_monthly_rebalanced",
        "standalone_100pct_angl_observation_approved": False,
        "paper_demo_active": False,
        "real_money_authorized": False,
        "next_action": OBSERVATION_NEXT_ACTION,
        "allowed_next_action": "no_action",
        "observation_stage": "deferred",
        "observation_outcome": "observation_invalid_or_incomplete",
        "observation_failure_reason": PRIMARY_FAILURE_REASON,
        "observation_next_action": OBSERVATION_NEXT_ACTION,
    }
    errors = [
        f"strategy {field} expected {value!r}, found {record.get(field)!r}"
        for field, value in expected.items()
        if record.get(field) != value
    ]
    parameters = record.get("parameters", {})
    if parameters.get("assigned_portfolio_sleeve_weight") != 0.2:
        errors.append("strategy assigned portfolio sleeve weight changed")
    if parameters.get("portfolio_rebalance_frequency") != "monthly":
        errors.append("strategy monthly rebalance changed")
    if record.get("paper_orders") is not False or record.get("live_orders") is not False:
        errors.append("strategy order guardrails changed")
    return errors


def validate_observation_semantics(record: dict[str, Any]) -> list[str]:
    expected = {
        "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID,
        "entity_type": "paper_demo_observation",
        "stage": "deferred",
        "semantic_stage": "deferred",
        "outcome": "observation_invalid_or_incomplete",
        "failure_reason": PRIMARY_FAILURE_REASON,
        "adaptation_label": "paper_demo_observation_fix",
        "observation_route": "diversifier_only",
        "paper_forward_active": False,
        "paper_demo_active": False,
        "first_forward_observation_date": "",
        "forward_records_created": 0,
        "valid_forward_record_count": 0,
        "next_action": OBSERVATION_NEXT_ACTION,
        "deferred_reason": DEFERRED_REASON,
        "automatic_remediation_attempts_exhausted": True,
        "last_attempted_session": LAST_ATTEMPTED_SESSION,
        "last_data_outcome": FINAL_DATA_OUTCOME,
        "elapsed_time_alone_reopen_condition": False,
        "june_18_record_classification": "historical_reconciliation_only",
    }
    errors = [
        f"observation {field} expected {value!r}, found {record.get(field)!r}"
        for field, value in expected.items()
        if record.get(field) != value
    ]
    if record.get("target_weights") != {"frozen_reference": 0.8, "ANGL": 0.2}:
        errors.append("observation target weights changed")
    if record.get("rebalance_frequency") != "monthly":
        errors.append("observation monthly rebalance changed")
    if record.get("cost_assumption") != "5_bps_per_one_way_turnover":
        errors.append("observation cost assumption changed")
    if record.get("reopen_conditions") != [
        condition_id for condition_id, _ in REOPEN_CONDITIONS
    ]:
        errors.append("observation reopen conditions incomplete")
    return errors


def validate_active_observation_document(payload: dict[str, Any]) -> dict[str, Any]:
    records = observation_records(payload)
    errors: list[str] = []
    if len(records) != 1:
        errors.append(f"expected one ANGL observation, found {len(records)}")
    elif records:
        errors.extend(validate_observation_semantics(records[0]))
    ids = [
        row.get("observation_id")
        for row in payload.get("active_observations", [])
        if isinstance(row, dict) and row.get("observation_id")
    ]
    if len(ids) != len(set(ids)):
        errors.append("duplicate observation_id in active observation document")
    return {"passed": not errors, "errors": errors}


def read_authoritative_inputs() -> dict[str, Any]:
    missing = [rel(path) for path in AUTHORITATIVE_CORRECTION_FILES if not path.exists()]
    if missing:
        raise ValueError("missing authoritative correction files: " + "|".join(missing))
    manifest = yaml.safe_load(
        (FINAL_CORRECTION_DIR / "correction_manifest.yaml").read_text(encoding="utf-8")
    )
    outcome = read_csv(FINAL_CORRECTION_DIR / "outcome_summary.csv")
    commit = read_csv(FINAL_CORRECTION_DIR / "cohort_commit_decision.csv")
    fetches = read_csv(FINAL_CORRECTION_DIR / "provider_fetch_reproducibility.csv")
    xlc = read_csv(FINAL_CORRECTION_DIR / "xlc_ohlc_violation_analysis.csv")
    serialization = read_csv(
        FINAL_CORRECTION_DIR / "serialization_hash_reconciliation.csv"
    )
    consistency = json.loads(
        (FINAL_CORRECTION_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    if manifest.get("outcome") != FINAL_DATA_OUTCOME:
        raise ValueError("final correction manifest outcome mismatch")
    if len(outcome) != 1 or outcome[0].get("symbols_individually_passed") != "7":
        raise ValueError("final correction individual-pass count mismatch")
    deterministic = sum(
        row.get("normalized_provider_frames_identical") == "true" for row in fetches
    )
    if len(fetches) != 20 or deterministic != 7:
        raise ValueError("final correction provider reproducibility count mismatch")
    if len(commit) != 1 or commit[0].get("cohort_committed") != "false":
        raise ValueError("final correction cohort decision mismatch")
    if any(row.get("hashes_match") != "true" for row in serialization):
        raise ValueError("serialization correction did not pass for all symbols")
    if not xlc or any(row.get("numerically_immaterial") != "false" for row in xlc):
        raise ValueError("XLC material raw-OHLC blocker not established")
    if consistency.get("consistency_passed") is not True:
        raise ValueError("final correction consistency check did not pass")
    return {
        "manifest": manifest,
        "outcome": outcome[0],
        "commit": commit[0],
        "fetches": fetches,
        "xlc": xlc,
        "serialization": serialization,
        "consistency": consistency,
    }


def carried_trial_rows() -> list[dict[str, Any]]:
    carried: dict[str, dict[str, Any]] = {}
    for source in TRIAL_LEDGER_PATHS:
        for row in read_csv(source):
            if row.get("strategy_id") != STRATEGY_ID or not row.get("trial_id"):
                continue
            carried[row["trial_id"]] = {
                "trial_id": row["trial_id"],
                "parent_trial_id": row.get("parent_trial_id", ""),
                "strategy_id": STRATEGY_ID,
                "entity_type": "experiment_trial",
                "stage": row.get("stage", ""),
                "adaptation_label": row.get("adaptation_label", ""),
                "outcome": row.get("outcome", ""),
                "read_only": True,
                "source_path": rel(source),
                "new_trial_created": False,
            }
    return [carried[key] for key in sorted(carried)]


def atomic_write_pair(registry_text: str, active_text: str) -> None:
    registry_before = REGISTRY_PATH.read_bytes()
    active_before = ACTIVE_OBSERVATIONS_PATH.read_bytes()
    registry_temp = REGISTRY_PATH.with_name(f".{REGISTRY_PATH.name}.{TASK_ID}.tmp")
    active_temp = ACTIVE_OBSERVATIONS_PATH.with_name(
        f".{ACTIVE_OBSERVATIONS_PATH.name}.{TASK_ID}.tmp"
    )
    try:
        with registry_temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(registry_text)
            handle.flush()
            os.fsync(handle.fileno())
        with active_temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(active_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(registry_temp, REGISTRY_PATH)
        os.replace(active_temp, ACTIVE_OBSERVATIONS_PATH)
    except BaseException:  # noqa: BLE001 - pair must be restored after any partial replacement.
        REGISTRY_PATH.write_bytes(registry_before)
        ACTIVE_OBSERVATIONS_PATH.write_bytes(active_before)
        registry_temp.unlink(missing_ok=True)
        active_temp.unlink(missing_ok=True)
        raise


def run() -> dict[str, Any]:
    clean_output()
    authoritative = read_authoritative_inputs()

    prior_dirs = (
        FINAL_CORRECTION_DIR,
        METHODOLOGY_CORRECTION_DIR,
        FORWARD_CORRECTION_DIR,
        INITIALIZATION_DIR,
        VALIDATION_DIR,
        EXPLORATION_DIR,
    )
    prior_evidence_paths = [
        path for directory in prior_dirs for path in all_files(directory)
    ]
    operational_paths = all_files(OPERATIONAL_DIR) if OPERATIONAL_DIR.exists() else []
    cache_paths = [
        path for path in sorted((ROOT / "data" / "cache").glob("*")) if path.is_file()
    ]
    protected_paths = (
        list(SOURCE_OF_TRUTH_PATHS)
        + prior_evidence_paths
        + operational_paths
        + cache_paths
    )
    hashes_before = hash_map(protected_paths)

    registry_text_before, registry_before = load_yaml_text(REGISTRY_PATH)
    active_text_before, active_before = load_yaml_text(ACTIVE_OBSERVATIONS_PATH)
    registry_records_before = strategy_records(registry_before)
    observation_records_before = observation_records(active_before)
    validation_before = validate_registry_data(registry_before)

    process_outcome = PROCESS_OUTCOME_BLOCKED
    process_failure_reason = BLOCKED_FAILURE_STATUS
    exact_next_action = BLOCKED_NEXT_ACTION
    strategy_updated = 0
    observation_updated = 0
    stage_mapping = "not_applied"
    proposal_registry_validation: dict[str, Any] = {
        "passed": False,
        "errors": ["proposal not built"],
    }
    proposal_active_validation: dict[str, Any] = {
        "passed": False,
        "errors": ["proposal not built"],
    }
    strategy_before: dict[str, Any] = (
        registry_records_before[0] if len(registry_records_before) == 1 else {}
    )
    observation_before: dict[str, Any] = (
        observation_records_before[0] if len(observation_records_before) == 1 else {}
    )
    strategy_after_proposed = copy.deepcopy(strategy_before)
    observation_after_proposed = copy.deepcopy(observation_before)
    error_detail = ""

    try:
        if len(registry_records_before) != 1:
            raise ValueError(
                f"expected exactly one ANGL strategy record, found {len(registry_records_before)}"
            )
        if len(observation_records_before) != 1:
            raise ValueError(
                f"expected exactly one ANGL observation, found {len(observation_records_before)}"
            )
        if strategy_before.get("stage") != "paper_demo_eligible":
            raise ValueError("ANGL strategy is not paper_demo_eligible before deferral")
        if strategy_before.get("outcome") != "paper_demo_eligible":
            raise ValueError("ANGL strategy outcome is not paper_demo_eligible before deferral")
        if observation_before.get("stage") != "blocked":
            raise ValueError("ANGL observation is not in the expected blocked pre-state")
        if observation_before.get("paper_forward_active") is not False:
            raise ValueError("ANGL observation unexpectedly active before deferral")

        strategy_after_proposed = proposed_strategy_record(strategy_before)
        observation_after_proposed = proposed_observation_record(observation_before)
        strategy_change_set = changed_fields(strategy_before, strategy_after_proposed)
        observation_change_set = changed_fields(
            observation_before, observation_after_proposed
        )
        if not strategy_change_set.issubset(STRATEGY_ALLOWED_CHANGES):
            raise ValueError(
                "unauthorized strategy fields changed: "
                + "|".join(sorted(strategy_change_set - STRATEGY_ALLOWED_CHANGES))
            )
        if not observation_change_set.issubset(OBSERVATION_ALLOWED_CHANGES):
            raise ValueError(
                "unauthorized observation fields changed: "
                + "|".join(
                    sorted(observation_change_set - OBSERVATION_ALLOWED_CHANGES)
                )
            )
        strategy_semantic_errors = validate_strategy_semantics(strategy_after_proposed)
        observation_semantic_errors = validate_observation_semantics(
            observation_after_proposed
        )
        if strategy_semantic_errors or observation_semantic_errors:
            raise ValueError(
                "proposed semantic validation failed: "
                + "|".join(strategy_semantic_errors + observation_semantic_errors)
            )

        proposed_registry = copy.deepcopy(registry_before)
        proposed_registry["strategies"] = [
            strategy_after_proposed
            if isinstance(row, dict)
            and (
                row.get("id") == STRATEGY_ID
                or row.get("strategy_id") == STRATEGY_ID
            )
            else row
            for row in proposed_registry.get("strategies", [])
        ]
        proposed_active = copy.deepcopy(active_before)
        proposed_active["active_observations"] = [
            observation_after_proposed
            if isinstance(row, dict) and row.get("observation_id") == OBSERVATION_ID
            else row
            for row in proposed_active.get("active_observations", [])
        ]
        proposal_registry_validation = validate_registry_data(proposed_registry)
        proposal_active_validation = validate_active_observation_document(proposed_active)
        if proposal_registry_validation.get("passed") is not True:
            raise ValueError(
                "proposed registry validation failed: "
                + "|".join(proposal_registry_validation.get("errors", []))
            )
        if proposal_active_validation.get("passed") is not True:
            raise ValueError(
                "proposed observation validation failed: "
                + "|".join(proposal_active_validation.get("errors", []))
            )
        stage_mapping = "literal_deferred_accepted"

        registry_text_proposed = replace_record_block(
            registry_text_before,
            f"- id: {STRATEGY_ID}",
            r"^- id:\s",
            strategy_after_proposed,
        )
        active_text_proposed = replace_record_block(
            active_text_before,
            f"- observation_id: {OBSERVATION_ID}",
            r"^benchmark_controls:\s*$",
            observation_after_proposed,
        )
        parsed_registry_proposed = yaml.safe_load(registry_text_proposed)
        parsed_active_proposed = yaml.safe_load(active_text_proposed)
        if validate_registry_data(parsed_registry_proposed) != proposal_registry_validation:
            raise ValueError("serialized registry proposal differs from validated proposal")
        if validate_active_observation_document(parsed_active_proposed) != proposal_active_validation:
            raise ValueError("serialized observation proposal differs from validated proposal")

        atomic_write_pair(registry_text_proposed, active_text_proposed)
        written_registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        written_active = yaml.safe_load(
            ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
        )
        written_registry_validation = validate_registry_data(written_registry)
        written_active_validation = validate_active_observation_document(written_active)
        if written_registry_validation.get("passed") is not True:
            raise ValueError("written registry failed validation")
        if written_active_validation.get("passed") is not True:
            raise ValueError("written active observation failed validation")
        if len(strategy_records(written_registry)) != 1:
            raise ValueError("written registry changed ANGL strategy cardinality")
        if len(observation_records(written_active)) != 1:
            raise ValueError("written active state changed observation cardinality")

        strategy_updated = int(registry_text_proposed != registry_text_before)
        observation_updated = int(active_text_proposed != active_text_before)
        process_outcome = PROCESS_OUTCOME_SUCCESS
        process_failure_reason = PRIMARY_FAILURE_REASON
        exact_next_action = PROJECT_NEXT_ACTION
    except (ValueError, OSError, yaml.YAMLError) as exc:
        error_detail = str(exc)
        process_failure_reason = (
            "methodology_failure"
            if "methodology" in error_detail.lower()
            else BLOCKED_FAILURE_STATUS
        )
        if (
            REGISTRY_PATH.read_text(encoding="utf-8") != registry_text_before
            or ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
            != active_text_before
        ):
            atomic_write_pair(registry_text_before, active_text_before)
        strategy_updated = 0
        observation_updated = 0

    registry_after = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    active_after = yaml.safe_load(
        ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    )
    validation_after = validate_registry_data(registry_after)
    active_validation_after = validate_active_observation_document(active_after)
    strategy_records_after = strategy_records(registry_after)
    observation_records_after = observation_records(active_after)
    strategy_final = (
        strategy_records_after[0] if len(strategy_records_after) == 1 else {}
    )
    observation_final = (
        observation_records_after[0] if len(observation_records_after) == 1 else {}
    )
    hashes_after = hash_map(protected_paths)

    registry_other_before = [
        row
        for row in registry_before.get("strategies", [])
        if not (
            isinstance(row, dict)
            and (
                row.get("id") == STRATEGY_ID
                or row.get("strategy_id") == STRATEGY_ID
            )
        )
    ]
    registry_other_after = [
        row
        for row in registry_after.get("strategies", [])
        if not (
            isinstance(row, dict)
            and (
                row.get("id") == STRATEGY_ID
                or row.get("strategy_id") == STRATEGY_ID
            )
        )
    ]
    observation_other_before = [
        row
        for row in active_before.get("active_observations", [])
        if not (
            isinstance(row, dict) and row.get("observation_id") == OBSERVATION_ID
        )
    ]
    observation_other_after = [
        row
        for row in active_after.get("active_observations", [])
        if not (
            isinstance(row, dict) and row.get("observation_id") == OBSERVATION_ID
        )
    ]

    state_rows: list[dict[str, Any]] = []
    prior_evidence_set = {rel(path) for path in prior_evidence_paths}
    operational_set = {rel(path) for path in operational_paths}
    cache_set = {rel(path) for path in cache_paths}
    for path_text, before_hash in hashes_before.items():
        resolved = (ROOT / path_text).resolve()
        if resolved == REGISTRY_PATH.resolve():
            path_type = "authorized_strategy_registry"
        elif resolved == ACTIVE_OBSERVATIONS_PATH.resolve():
            path_type = "authorized_active_observation_state"
        elif path_text in prior_evidence_set:
            path_type = "protected_prior_evidence"
        elif path_text in operational_set:
            path_type = "protected_operational_forward_file"
        elif path_text in cache_set:
            path_type = "protected_market_data_cache_or_metadata"
        else:
            path_type = "protected_source_of_truth"
        changed = before_hash != hashes_after[path_text]
        state_rows.append(
            {
                "path": path_text,
                "path_type": path_type,
                "hash_before": before_hash,
                "hash_after": hashes_after[path_text],
                "changed": changed,
                "change_permitted": (
                    resolved in PERMITTED_PATHS
                    and process_outcome == PROCESS_OUTCOME_SUCCESS
                ),
                "action": (
                    "updated_in_place"
                    if changed and resolved in PERMITTED_PATHS
                    else "preserved"
                ),
            }
        )
    unexpected_changes = [
        row["path"]
        for row in state_rows
        if row["changed"] and not row["change_permitted"]
    ]
    changed_paths = [row["path"] for row in state_rows if row["changed"]]

    trial_rows = carried_trial_rows()
    final_data_tasks = read_csv(
        FINAL_CORRECTION_DIR / "data_capability_task_log.csv"
    )
    data_task_rows = [
        {
            **row,
            "read_only": True,
            "new_data_capability_task_created": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for row in final_data_tasks
    ]
    process_row = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "outcome": process_outcome,
        "failure_reason": process_failure_reason,
        "next_action": exact_next_action,
        "counted_as_strategy": False,
        "counted_as_trial": False,
        "provider_called": False,
        "cache_modified": False,
    }
    reopen_rows = [
        {
            "condition_id": condition_id,
            "condition_description": description,
            "material_change_required": True,
            "approved_or_implemented_in_this_task": False,
        }
        for condition_id, description in REOPEN_CONDITIONS
    ]
    reopen_rows.append(
        {
            "condition_id": "elapsed_time_alone",
            "condition_description": "Elapsed time alone is not a reopen condition.",
            "material_change_required": False,
            "approved_or_implemented_in_this_task": False,
        }
    )
    decision_row = {
        "observation_id": OBSERVATION_ID,
        "decision": (
            "deferred" if process_outcome == PROCESS_OUTCOME_SUCCESS else "not_changed"
        ),
        "semantic_stage": (
            observation_final.get("semantic_stage", "")
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else ""
        ),
        "stored_stage": observation_final.get("stage", ""),
        "stage_schema_mapping": stage_mapping,
        "outcome": observation_final.get("outcome", ""),
        "failure_reason": (
            observation_final.get("failure_reason", "")
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else process_failure_reason
        ),
        "automatic_remediation_attempts_exhausted": observation_final.get(
            "automatic_remediation_attempts_exhausted", False
        ),
        "last_attempted_session": observation_final.get(
            "last_attempted_session", ""
        ),
        "last_data_outcome": observation_final.get("last_data_outcome", ""),
        "next_action": (
            observation_final.get("next_action", "")
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else BLOCKED_NEXT_ACTION
        ),
        "observation_activated": False,
        "forward_records_created": 0,
    }
    strategy_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "strategy_configuration",
        "stage": strategy_final.get("stage", ""),
        "outcome": strategy_final.get("outcome", ""),
        "route": strategy_final.get("route", ""),
        "validated_portfolio_use": strategy_final.get(
            "validated_portfolio_use", ""
        ),
        "standalone_eligibility": strategy_final.get(
            "standalone_100pct_angl_observation_approved", ""
        ),
        "real_money_authorized": strategy_final.get("real_money_authorized", ""),
        "operational_next_action": strategy_final.get("next_action", ""),
        "read_only_strategy_rules": True,
        "strategy_configuration_created": False,
        "strategy_configuration_updated": bool(strategy_updated),
    }
    observation_row = {
        **observation_final,
        "created_in_this_task": False,
        "updated_in_this_task": bool(observation_updated),
        "activated_in_this_task": False,
    }
    outcome_row = {
        "task_id": TASK_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "strategy_stage": strategy_final.get("stage", ""),
        "strategy_outcome": strategy_final.get("outcome", ""),
        "observation_semantic_stage": observation_final.get(
            "semantic_stage", ""
        ),
        "observation_stored_stage": observation_final.get("stage", ""),
        "observation_outcome": observation_final.get("outcome", ""),
        "observation_failure_reason": observation_final.get("failure_reason", ""),
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": strategy_updated,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": len(trial_rows),
        "observations_created": 0,
        "observations_updated": observation_updated,
        "observations_activated": 0,
        "forward_records_created": 0,
        "new_data_capability_tasks": 0,
        "process_tasks": 1,
        "observation_next_action": (
            observation_final.get("next_action", "")
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else BLOCKED_NEXT_ACTION
        ),
        "project_next_action": exact_next_action,
    }
    failure_rows = [
        {
            "entity_id": OBSERVATION_ID,
            "entity_type": "paper_demo_observation",
            "primary_failure_reason": (
                PRIMARY_FAILURE_REASON
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else process_failure_reason
            ),
            "failure_detail": (
                "Final 20-symbol canonical cohort could not be admitted: 13 "
                "provider-fetch pairs differed and XLC had a reproducible material "
                "raw-OHLC violation."
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else error_detail
            ),
            "next_action": (
                OBSERVATION_NEXT_ACTION
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else BLOCKED_NEXT_ACTION
            ),
        }
    ]
    next_rows = [
        {
            "action_scope": "ANGL_observation",
            "exact_next_action": (
                OBSERVATION_NEXT_ACTION
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else BLOCKED_NEXT_ACTION
            ),
            "execute_in_this_task": False,
        },
        {
            "action_scope": "project",
            "exact_next_action": exact_next_action,
            "execute_in_this_task": False,
        },
    ]

    strategy_semantic_errors = validate_strategy_semantics(strategy_final)
    observation_semantic_errors = (
        validate_observation_semantics(observation_final)
        if process_outcome == PROCESS_OUTCOME_SUCCESS
        else []
    )
    consistency = {
        "consistency_passed": bool(
            process_outcome == PROCESS_OUTCOME_SUCCESS
            and validation_after.get("passed") is True
            and active_validation_after.get("passed") is True
            and len(strategy_records_after) == 1
            and len(observation_records_after) == 1
            and not strategy_semantic_errors
            and not observation_semantic_errors
            and changed_fields(strategy_before, strategy_final).issubset(
                STRATEGY_ALLOWED_CHANGES
            )
            and changed_fields(observation_before, observation_final).issubset(
                OBSERVATION_ALLOWED_CHANGES
            )
            and registry_other_before == registry_other_after
            and observation_other_before == observation_other_after
            and not unexpected_changes
            and len(trial_rows) == 3
            and len(data_task_rows) == 20
        ),
        "authoritative_final_data_outcome": authoritative["manifest"]["outcome"],
        "authoritative_individual_symbol_passes": 7,
        "authoritative_deterministic_provider_pairs": 7,
        "authoritative_cohort_committed": False,
        "registry_validation_before_passed": validation_before.get("passed"),
        "registry_validation_before_errors": validation_before.get("errors", []),
        "registry_validation_after_passed": validation_after.get("passed"),
        "registry_validation_after_errors": validation_after.get("errors", []),
        "active_observation_validation_passed": active_validation_after.get("passed"),
        "active_observation_validation_errors": active_validation_after.get(
            "errors", []
        ),
        "literal_deferred_stage_accepted": stage_mapping == "literal_deferred_accepted",
        "strategy_semantics_preserved": not strategy_semantic_errors,
        "strategy_semantic_errors": strategy_semantic_errors,
        "observation_semantics_deferred": not observation_semantic_errors,
        "observation_semantic_errors": observation_semantic_errors,
        "other_registry_records_unchanged": registry_other_before
        == registry_other_after,
        "other_observation_records_unchanged": observation_other_before
        == observation_other_after,
        "changed_paths": changed_paths,
        "only_permitted_paths_changed": not unexpected_changes,
        "unexpected_changes": unexpected_changes,
        "prior_evidence_unchanged": all(
            hashes_before[rel(path)] == hashes_after[rel(path)]
            for path in prior_evidence_paths
        ),
        "market_data_cache_and_metadata_unchanged": all(
            hashes_before[rel(path)] == hashes_after[rel(path)]
            for path in cache_paths
        ),
        "operational_forward_files_unchanged": all(
            hashes_before[rel(path)] == hashes_after[rel(path)]
            for path in operational_paths
        ),
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
        "forward_records_created": 0,
        "new_data_capability_tasks": 0,
        "provider_called": False,
        "cache_modified": False,
        "backtest_or_validation_run": False,
        "broker_account_position_order_endpoint_called": False,
        "paper_or_live_order_submitted": False,
        "real_money_action": False,
        "process_outcome": process_outcome,
        "observation_next_action": (
            OBSERVATION_NEXT_ACTION
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else BLOCKED_NEXT_ACTION
        ),
        "project_next_action": exact_next_action,
    }

    write_yaml(
        OUTPUT_DIR / "deferral_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "process_outcome": process_outcome,
            "failure_reason": process_failure_reason,
            "strategy_configurations_created": 0,
            "strategy_configurations_updated": strategy_updated,
            "experiment_trials_created": 0,
            "existing_trials_carried_forward": len(trial_rows),
            "observations_created": 0,
            "observations_updated": observation_updated,
            "observations_activated": 0,
            "forward_records_created": 0,
            "new_data_capability_tasks": 0,
            "process_tasks": 1,
            "observation_next_action": (
                OBSERVATION_NEXT_ACTION
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else BLOCKED_NEXT_ACTION
            ),
            "project_next_action": exact_next_action,
        },
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [strategy_row], list(strategy_row))
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial_rows,
        [
            "trial_id",
            "parent_trial_id",
            "strategy_id",
            "entity_type",
            "stage",
            "adaptation_label",
            "outcome",
            "read_only",
            "source_path",
            "new_trial_created",
        ],
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observations.csv",
        [observation_row],
        list(observation_row),
    )
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_task_rows,
        list(data_task_rows[0]),
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", [process_row], list(process_row))
    write_csv(OUTPUT_DIR / "deferral_decision.csv", [decision_row], list(decision_row))
    write_csv(
        OUTPUT_DIR / "reopen_conditions.csv",
        reopen_rows,
        list(reopen_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        list(state_rows[0]),
    )
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        list(failure_rows[0]),
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "deferral_report.md",
        f"""# ANGL Observation Data-Lane Deferral v1

## Decision

- Process outcome: `{process_outcome}`
- Strategy remains: `{strategy_final.get('stage', '')}` / `{strategy_final.get('outcome', '')}`
- Observation semantic stage: `{observation_final.get('semantic_stage', '')}`
- Observation stored stage: `{observation_final.get('stage', '')}`
- Failure reason: `{observation_final.get('failure_reason', process_failure_reason)}`
- Automatic remediation exhausted: `{str(observation_final.get('automatic_remediation_attempts_exhausted', False)).lower()}`
- Last attempted session: `{observation_final.get('last_attempted_session', '')}`
- Forward records created: `0`

The existing observation was updated in place. The strategy's validated 80% frozen
VM/DSR/USCI reference plus 20% ANGL construction, monthly rebalance, natural drift,
and 5 bps one-way turnover assumption remain unchanged. June 18 remains historical
reconciliation only.

No provider, cache, backtest, validation, observation initialization, activation,
virtual forward record, broker endpoint, or order path was used.

## Next Actions

- Observation reopen gate: `{OBSERVATION_NEXT_ACTION}` (not executed)
- Project: `{exact_next_action}` (not executed)
""",
    )
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "process_outcome": process_outcome,
        "strategy_stage": strategy_final.get("stage", ""),
        "observation_stage": observation_final.get("stage", ""),
        "observation_failure_reason": observation_final.get("failure_reason", ""),
        "observation_next_action": (
            OBSERVATION_NEXT_ACTION
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else BLOCKED_NEXT_ACTION
        ),
        "project_next_action": exact_next_action,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
