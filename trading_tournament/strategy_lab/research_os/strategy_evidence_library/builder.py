from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from strategy_lab.research_os.research.dsr_evidence_status import DSR_ACTIVE_ID, load_dsr_evidence_status

from .fingerprint import fingerprint_payload, strategy_fingerprint


EVIDENCE_LEVELS = ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7"]
LIFECYCLE_STATUSES = {
    "backlog",
    "blocked",
    "rejected",
    "retest_only_on_new_evidence",
    "eligible",
    "active",
    "retired",
    "unmapped",
    "unknown",
}
FAILURE_CODES = {
    "SOURCE_NOT_REPRODUCED",
    "RULES_INCOMPLETE",
    "DATA_UNAVAILABLE",
    "LOOKAHEAD",
    "SURVIVORSHIP",
    "IMPLEMENTATION_MISMATCH",
    "EXECUTION_UNREALISTIC",
    "COST_SENSITIVE",
    "NO_OUT_OF_SAMPLE_EDGE",
    "PARAMETER_INSTABILITY",
    "STRUCTURAL_BREAK",
    "FAMILY_REDUNDANT",
    "ACCOUNT_INFEASIBLE",
    "HOLDOUT_FAILURE",
    "CODE_DEFECT",
    "PAPER_DEMO_DRIFT",
}

SOURCE_ORIGINS = {"external", "internal", "generated", "unknown"}
SOURCE_CLASSES = {
    "academic_primary",
    "academic_replication",
    "practitioner_research",
    "documented_strategy_archetype",
    "open_source_implementation_reference",
    "benchmark_or_dataset_reference",
    "book_or_long_form_reference",
    "community_lead_only",
    "unverified_external_claim",
    "internal_prompt_idea",
    "internal_project_evidence",
    "internal_registry",
    "internal_governance_record",
    "internal_implementation",
    "internal_benchmark_definition",
    "generated_report",
    "generated_manifest",
    "generated_reconciliation",
    "generated_dashboard",
    "unknown",
}
EXTERNAL_DISCOVERY_BACKLOG_CLASSES = {
    "academic_primary",
    "academic_replication",
    "practitioner_research",
    "documented_strategy_archetype",
    "book_or_long_form_reference",
    "unverified_external_claim",
}
IMPLEMENTATION_REFERENCE_CLASSES = {"open_source_implementation_reference"}
NON_EXTERNAL_LOCAL_PREFIXES = (
    "evidence/",
    "strategy_lab/",
    "paper_forward_observations/",
    "tests/",
    "run_",
)

OUTPUT_DIR = Path("evidence") / "strategy_evidence_library" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
PUBLIC_SOURCE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
FAMILY_STATUS_DIR = Path("strategy_lab") / "research_os" / "family_status"
SCHEMA_PATH = Path("strategy_lab") / "research_os" / "strategy_evidence_library" / "schema.yaml"

EXACT_LIFECYCLE_STATUS_MAP = {
    "blocked": ("blocked", "lifecycle_exact_blocked_v1"),
    "blocked_or_deferred": ("blocked", "lifecycle_exact_blocked_v1"),
    "data_gated": ("blocked", "lifecycle_exact_blocked_v1"),
    "evidence_missing": ("blocked", "lifecycle_exact_blocked_v1"),
    "incomplete_evidence": ("blocked", "lifecycle_exact_blocked_v1"),
    "paused_data_source_blocked": ("blocked", "lifecycle_exact_blocked_v1"),
    "discovery_reject": ("rejected", "lifecycle_exact_rejected_v1"),
    "duplicate_or_near_duplicate": ("rejected", "lifecycle_exact_rejected_v1"),
    "duplicate_or_do_not_retest": ("rejected", "lifecycle_exact_rejected_v1"),
    "duplicate_skipped": ("rejected", "lifecycle_exact_rejected_v1"),
    "mark_duplicate_or_near_duplicate": ("rejected", "lifecycle_exact_rejected_v1"),
    "reject_for_now": ("rejected", "lifecycle_exact_rejected_v1"),
    "rejected": ("rejected", "lifecycle_exact_rejected_v1"),
    "rejected_after_bugfix_rerun": ("rejected", "lifecycle_exact_rejected_v1"),
    "rejected_current_variants": ("rejected", "lifecycle_exact_rejected_v1"),
    "too_risky": ("rejected", "lifecycle_exact_rejected_v1"),
    "too_slow": ("rejected", "lifecycle_exact_rejected_v1"),
    "too_slow_for_profit_goal": ("rejected", "lifecycle_exact_rejected_v1"),
    "backlog": ("backlog", "lifecycle_exact_backlog_v1"),
    "exploratory_only": ("backlog", "lifecycle_exact_backlog_v1"),
    "research_queue": ("backlog", "lifecycle_exact_backlog_v1"),
    "research_sample_candidate": ("backlog", "lifecycle_exact_backlog_v1"),
    "watchlist": ("backlog", "lifecycle_exact_backlog_v1"),
    "watchlist_family": ("backlog", "lifecycle_exact_backlog_v1"),
    "retired": ("retired", "lifecycle_exact_retired_v1"),
}

EXACT_FAILURE_CODE_MAP = {
    ("status", "duplicate_or_near_duplicate"): ("FAMILY_REDUNDANT", "failure_status_duplicate_v1"),
    ("status", "duplicate_skipped"): ("FAMILY_REDUNDANT", "failure_status_duplicate_v1"),
    ("status", "mark_duplicate_or_near_duplicate"): ("FAMILY_REDUNDANT", "failure_status_duplicate_v1"),
    ("current_status", "duplicate_or_near_duplicate"): ("FAMILY_REDUNDANT", "failure_current_status_duplicate_v1"),
    ("current_status", "duplicate_skipped"): ("FAMILY_REDUNDANT", "failure_current_status_duplicate_v1"),
    ("current_status", "mark_duplicate_or_near_duplicate"): ("FAMILY_REDUNDANT", "failure_current_status_duplicate_v1"),
    ("primary_failure_mode", "duplicate_or_near_duplicate"): ("FAMILY_REDUNDANT", "failure_primary_mode_duplicate_v1"),
    ("status", "too_slow"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_status_too_slow_v1"),
    ("status", "too_slow_for_profit_goal"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_status_too_slow_v1"),
    ("current_status", "too_slow"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_current_status_too_slow_v1"),
    ("current_status", "too_slow_for_profit_goal"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_current_status_too_slow_v1"),
    ("primary_failure_mode", "too_slow_for_profit_goal"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_primary_mode_no_edge_v1"),
    ("primary_failure_mode", "target_rate_too_slow"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_primary_mode_no_edge_v1"),
    ("primary_failure_mode", "rejected_by_existing_evidence"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_primary_mode_no_edge_v1"),
    ("primary_failure_mode", "discovery_reject"): ("NO_OUT_OF_SAMPLE_EDGE", "failure_primary_mode_no_edge_v1"),
    ("status", "data_gated"): ("DATA_UNAVAILABLE", "failure_status_data_gated_v1"),
    ("current_status", "data_gated"): ("DATA_UNAVAILABLE", "failure_current_status_data_gated_v1"),
}

VERIFIED_PRE_PATCH_SEMANTIC_BASELINE = {
    "evidence_funnel": {"E1": 143, "E2": 197, "E4": 45, "E5": 5, "E6": 5, "E7": 2},
    "lifecycle_counts": {"active": 14, "backlog": 254, "blocked": 14, "eligible": 33, "rejected": 81, "retired": 1},
    "spec_count": 251,
    "migration_placeholder_spec_count": 211,
    "placeholder_linked_decision_count": 232,
    "placeholder_linked_e2_or_higher_decision_count": 212,
    "qualifying_preregistration_count": 0,
    "failure_code_assignment_count": 656,
    "failure_code_provenance_count": 0,
}

VERIFIED_PRE_CUMULATIVE_CHAIN_BASELINE = {
    "evidence_funnel": {"E1": 344, "E2": 23, "E3": 6, "E4": 20, "E5": 2, "E7": 2},
    "qualifying_preregistration_count": 23,
    "qualifying_implementation_count": 56,
}

MANDATORY_SPEC_FIELDS = {
    "strategy_universe": "Strategy universe or instruments",
    "entry_rule": "Signal or entry rule",
    "exit_rule": "Exit, deactivation, or cash-transition rule",
    "timeframe": "Timeframe",
    "rebalance_cadence": "Rebalance cadence",
    "parameters": "Parameters or explicit parameter-free statement",
    "required_data": "Required data and availability assumptions",
    "signal_timestamp": "Signal timestamp",
    "order_timestamp": "Order or execution timestamp",
    "benchmark_rule": "Benchmark or comparison basis",
    "success_criteria": "Success criteria",
    "failure_criteria": "Failure criteria",
}

UNRESOLVED_SPEC_VALUES = {
    "",
    "unknown",
    "see_artifact",
    "see artifact",
    "not_applicable_or_unknown",
    "unknown_migrated_from_registry_or_evidence",
}

BLOCKED_SPEC_STATUS_TOKENS = {
    "blocked",
    "patch_required",
    "needs_patch",
    "not_run_ready",
    "manual_review_required",
    "requires_another_patch",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or fallback).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def unknown_if_blank(value: Any) -> Any:
    if value is None:
        return "unknown"
    if isinstance(value, str) and not value.strip():
        return "unknown"
    return value


def read_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def hash_data(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hash_bytes(payload)


def hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "unknown"
    return "sha256:" + hash_bytes(path.read_bytes())


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def dependency_lock_hash(root: Path) -> str:
    candidates = ["requirements.txt", "pyproject.toml", "poetry.lock", "uv.lock"]
    existing = [root / name for name in candidates if (root / name).exists()]
    if not existing:
        return "unknown"
    return hash_data({p.name: hash_file(p) for p in existing})


def data_cache_metadata_hash(root: Path) -> str:
    cache = root / "data" / "cache"
    if not cache.exists():
        return "unknown"
    rows: list[dict[str, Any]] = []
    for path in sorted(cache.rglob("*")):
        if path.is_file():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
    return hash_data(rows)


def evidence_chain(level: str) -> list[str]:
    if level not in EVIDENCE_LEVELS:
        return ["E0"]
    return EVIDENCE_LEVELS[: EVIDENCE_LEVELS.index(level) + 1]


def level_rank(level: str) -> int:
    return EVIDENCE_LEVELS.index(level) if level in EVIDENCE_LEVELS else 0


def max_level(*levels: str) -> str:
    return max((level for level in levels if level in EVIDENCE_LEVELS), key=level_rank, default="E0")


def provenance(
    source_path: str,
    source_field: str,
    value: Any,
    mapping_rule_id: str,
    origin_type: str,
) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "source_field": source_field,
        "supporting_value": value,
        "mapping_rule_id": mapping_rule_id,
        "origin_type": origin_type,
    }


def normalize_lifecycle_status(value: Any, source_path: str, source_field: str) -> tuple[str, dict[str, Any]]:
    if value in (None, ""):
        return "unknown", provenance(source_path, source_field, "unknown", "lifecycle_unknown_v1", "unknown")
    exact = slug(value)
    if exact in EXACT_LIFECYCLE_STATUS_MAP:
        status, rule = EXACT_LIFECYCLE_STATUS_MAP[exact]
        return status, provenance(source_path, source_field, value, rule, "normalized_explicit")
    return "unmapped", provenance(source_path, source_field, value, "lifecycle_unmapped_no_exact_rule_v1", "unknown")


def failure_provenance_from_fields(source_path: str, fields: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for field, value in fields.items():
        exact = slug(value)
        mapped = EXACT_FAILURE_CODE_MAP.get((field, exact))
        if not mapped:
            continue
        code, rule = mapped
        key = (code, field, exact)
        if key in seen:
            continue
        seen.add(key)
        row = provenance(source_path, field, value, rule, "normalized_explicit")
        row["failure_code"] = code
        rows.append(row)
    return rows


def failure_codes_from_provenance(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({row["failure_code"] for row in rows})


def legacy_lifecycle_from_status(status: Any, paper_forward_active: bool = False) -> str:
    text = slug(status)
    if paper_forward_active or "active" in text:
        return "active"
    if any(token in text for token in ["blocked", "paused", "data_gated", "data_source"]):
        return "blocked"
    if any(token in text for token in ["reject", "too_risky", "too_slow", "duplicate", "weak", "failed"]):
        return "rejected"
    if any(token in text for token in ["closed", "archive", "retired"]):
        return "retired"
    if any(token in text for token in ["eligible", "pass", "accepted", "benchmark"]):
        return "eligible"
    if any(token in text for token in ["watchlist", "queue", "candidate", "exploratory", "review"]):
        return "backlog"
    return "backlog"


def legacy_failure_codes_from_text(*values: Any) -> list[str]:
    text = " ".join(str(v or "") for v in values).lower()
    found: set[str] = set()
    if any(token in text for token in ["duplicate", "redundant", "similar"]):
        found.add("FAMILY_REDUNDANT")
    if any(token in text for token in ["data unavailable", "data_blocked", "data source", "missing data", "cache"]):
        found.add("DATA_UNAVAILABLE")
    if any(token in text for token in ["lookahead", "same-day", "stale-weight", "stale weight"]):
        found.add("LOOKAHEAD")
    if any(token in text for token in ["implementation", "mismatch", "methodology", "formula"]):
        found.add("IMPLEMENTATION_MISMATCH")
    if any(token in text for token in ["code defect", "bug", "patch"]):
        found.add("CODE_DEFECT")
    if "cost" in text:
        found.add("COST_SENSITIVE")
    if any(token in text for token in ["parameter", "threshold", "tuning", "unstable"]):
        found.add("PARAMETER_INSTABILITY")
    if any(token in text for token in ["holdout", "out_of_sample", "out-of-sample"]):
        found.add("HOLDOUT_FAILURE")
    if any(token in text for token in ["account", "broker", "execution", "unrealistic"]):
        found.add("EXECUTION_UNREALISTIC")
    if any(token in text for token in ["weak", "too_slow", "no candidate", "underperform", "return destroyed"]):
        found.add("NO_OUT_OF_SAMPLE_EDGE")
    if "paper_demo_drift" in text or "paper demo drift" in text:
        found.add("PAPER_DEMO_DRIFT")
    return sorted(found)


def record_role_from_fields(status: Any, role: Any, source_path: str) -> tuple[str, dict[str, Any]]:
    role_text = slug(role)
    status_text = slug(status)
    if role_text in {"benchmark", "aggressive_benchmark", "defensive_benchmark", "benchmark_control_only"} or status_text == "benchmark":
        return "benchmark", provenance(source_path, "role/status", f"{role}|{status}", "record_role_benchmark_exact_v1", "normalized_explicit")
    if "control" in role_text or "control" in status_text:
        return "frozen_control", provenance(source_path, "role/status", f"{role}|{status}", "record_role_control_exact_v1", "normalized_explicit")
    if status_text == "active_paper_demo_observation":
        return "paper_demo_observation", provenance(source_path, "status", status, "record_role_active_observation_exact_v1", "normalized_explicit")
    if "paper_forward" in status_text or "paper_demo" in status_text:
        return "paper_demo_candidate", provenance(source_path, "status", status, "record_role_paper_demo_candidate_exact_v1", "normalized_explicit")
    return "research_candidate", provenance(source_path, "role/status", f"{role}|{status}", "record_role_default_research_candidate_v1", "derived")


def is_resolved_spec_value(value: Any, *, allow_parameter_free: bool = False) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in UNRESOLVED_SPEC_VALUES:
            return False
        return bool(normalized)
    if isinstance(value, dict):
        if not value:
            return allow_parameter_free is True
        if value.get("parameter_free") is True or value.get("parameters_required") is False:
            return True
        return any(is_resolved_spec_value(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and any(is_resolved_spec_value(item) for item in value)
    return True


def spec_has_field_provenance(spec: dict[str, Any], field: str) -> bool:
    provenance_row = spec.get("field_provenance", {}).get(field)
    if not isinstance(provenance_row, dict):
        return False
    required = {"source_path", "source_field", "supporting_value", "mapping_rule_id", "origin_type"}
    return required <= set(provenance_row)


def spec_blocking_reasons(spec: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    status_text = slug(
        " ".join(
            str(value)
            for value in [
                spec.get("source_run_readiness_decision"),
                spec.get("source_design_status"),
                spec.get("qualification_source_status"),
            ]
            if value not in (None, "", "unknown")
        )
    )
    for token in BLOCKED_SPEC_STATUS_TOKENS:
        if token in status_text:
            reasons.append(f"source_status_{token}")
    if spec.get("record_kind") == "migration_placeholder":
        reasons.append("migration_placeholder_not_preregistration")
    return sorted(set(reasons))


def evaluate_spec_qualification(spec: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    missing = [
        field
        for field in MANDATORY_SPEC_FIELDS
        if not is_resolved_spec_value(spec.get(field), allow_parameter_free=(field == "parameters"))
        or not spec_has_field_provenance(spec, field)
    ]
    blockers = spec_blocking_reasons(spec)
    if not is_resolved_spec_value(spec.get("specification_content_hash")):
        missing.append("specification_content_hash")
    if not is_resolved_spec_value(spec.get("frozen_specification_reference")):
        missing.append("frozen_specification_reference")
    qualifies = not missing and not blockers
    return qualifies, sorted(set(missing)), blockers


def first_manifest_value(manifest: dict[str, Any], keys: Iterable[str]) -> tuple[str, Any]:
    for key in keys:
        value = manifest.get(key)
        if is_resolved_spec_value(value, allow_parameter_free=(key == "parameters")):
            return key, value
    return "unknown", "unknown"


def add_spec_field(
    spec: dict[str, Any],
    field: str,
    value: Any,
    source_path: str,
    source_field: str,
    rule_id: str,
) -> None:
    spec[field] = value
    spec.setdefault("field_provenance", {})[field] = provenance(source_path, source_field, value, rule_id, "explicit")


def apply_spec_qualification(spec: dict[str, Any]) -> None:
    qualifies, missing, blockers = evaluate_spec_qualification(spec)
    spec["qualifies_as_preregistration"] = qualifies
    spec["qualification_missing_fields"] = missing
    spec["qualification_blocking_reasons"] = blockers
    spec["qualification_provenance"] = spec.get("qualification_provenance", []) + [
        provenance(
            ";".join(spec.get("original_source_paths", [])) or "unknown",
            "mandatory_specification_fields",
            {"missing": missing, "blocking": blockers},
            "complete_resolved_specification_fields_v1" if qualifies else "incomplete_or_blocked_specification_v1",
            "derived",
        )
    ]


def extract_manifest_spec_fields(spec: dict[str, Any], manifest: dict[str, Any], rel_manifest: str, manifest_path: Path) -> None:
    field_keys = {
        "strategy_universe": ["strategy_universe", "instrument_universe", "instruments", "required_symbols", "universe"],
        "entry_rule": ["entry_rule", "signal_rule", "entry_signal_rule"],
        "exit_rule": ["exit_rule", "deactivation_rule", "cash_transition_rule"],
        "timeframe": ["timeframe", "data_frequency", "timeframe_used"],
        "rebalance_cadence": ["rebalance_cadence", "rebalance_frequency"],
        "parameters": ["parameters", "indicator_definitions", "thresholds", "threshold_set"],
        "required_data": ["required_data", "data_requirements", "local_cache_required_symbols", "required_symbols"],
        "signal_timestamp": ["signal_timestamp", "signal_timing"],
        "order_timestamp": ["order_timestamp", "execution_timestamp", "execution_timing"],
        "benchmark_rule": ["benchmark_rule", "baseline_comparator_policy", "comparator_policy"],
        "success_criteria": ["success_criteria", "numeric_success_failure_criteria"],
        "failure_criteria": ["failure_criteria", "numeric_success_failure_criteria"],
    }
    for field, keys in field_keys.items():
        source_field, value = first_manifest_value(manifest, keys)
        if source_field != "unknown":
            add_spec_field(spec, field, value, rel_manifest, source_field, f"spec_field_from_manifest_{field}_v1")
    content_hash = hash_file(manifest_path)
    spec["specification_content_hash"] = content_hash
    spec["frozen_specification_reference"] = rel_manifest
    spec.setdefault("field_provenance", {})["specification_content_hash"] = provenance(
        rel_manifest,
        "manifest_file_hash",
        content_hash,
        "specification_content_hash_from_manifest_v1",
        "derived",
    )
    spec.setdefault("field_provenance", {})["frozen_specification_reference"] = provenance(
        rel_manifest,
        "manifest_path",
        rel_manifest,
        "frozen_specification_reference_from_manifest_v1",
        "derived",
    )


def qualifies_preregistration(spec: dict[str, Any]) -> bool:
    qualifies, missing, blockers = evaluate_spec_qualification(spec)
    return bool(spec.get("qualifies_as_preregistration")) and qualifies and not missing and not blockers


def qualifies_implementation(impl: dict[str, Any]) -> bool:
    return (
        bool(impl.get("qualifies_as_reproducible_implementation"))
        and impl.get("repository_path") != "unknown"
        and impl.get("code_content_hash") != "unknown"
        and impl.get("configuration_hash") != "unknown"
        and impl.get("dependency_lock_hash") != "unknown"
        and bool(impl.get("linked_qualifying_specification_ids"))
        and (
            bool(impl.get("linked_tests"))
            or bool(impl.get("implementation_review_artifacts"))
            or impl.get("unit_test_status") == "passed"
            or impl.get("implementation_review_status") == "completed"
        )
    )


def evaluate_implementation_qualification(impl: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    missing: list[str] = []
    if impl.get("repository_path") == "unknown":
        missing.append("repository_path")
    if impl.get("code_content_hash") == "unknown":
        missing.append("code_content_hash")
    if impl.get("configuration_hash") == "unknown":
        missing.append("configuration_hash")
    if impl.get("dependency_lock_hash") == "unknown":
        missing.append("dependency_lock_hash")
    if not impl.get("linked_qualifying_specification_ids"):
        missing.append("linked_qualifying_specification_ids")
    has_test = bool(impl.get("linked_tests")) or impl.get("unit_test_status") == "passed"
    has_review = bool(impl.get("implementation_review_artifacts")) or impl.get("implementation_review_status") == "completed"
    if not has_test and not has_review:
        missing.append("linked_passing_tests_or_completed_implementation_review")
    blockers: list[str] = []
    if impl.get("unit_test_status") == "unknown" and impl.get("implementation_review_status") == "unknown":
        blockers.append("unit_test_and_implementation_review_unknown")
    qualifies = not missing and not blockers
    return qualifies, sorted(set(missing)), blockers


def apply_implementation_qualification(impl: dict[str, Any]) -> None:
    qualifies, missing, blockers = evaluate_implementation_qualification(impl)
    impl["qualifies_as_reproducible_implementation"] = qualifies
    impl["qualification_missing_fields"] = missing
    impl["qualification_blocking_reasons"] = blockers
    impl["implementation_evidence_provenance"] = impl.get("implementation_evidence_provenance", []) + [
        provenance(
            ";".join(impl.get("original_source_paths", [])) or "unknown",
            "implementation_qualification",
            {"missing": missing, "blocking": blockers},
            "complete_reproducible_implementation_v1" if qualifies else "incomplete_implementation_evidence_v1",
            "derived",
        )
    ]


def qualifies_local_backtest(exp: dict[str, Any], impls_by_variant: dict[str, list[dict[str, Any]]]) -> bool:
    return bool(exp.get("qualifies_as_local_backtest")) and any(
        qualifies_implementation(impl) for impl in impls_by_variant.get(exp["variant_id"], [])
    )


def qualifies_robustness(exp: dict[str, Any], impls_by_variant: dict[str, list[dict[str, Any]]]) -> bool:
    return bool(exp.get("qualifies_as_robustness")) and qualifies_local_backtest(exp, impls_by_variant)


def source_template(source_id: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_name": "unknown",
        "source_type": "unknown",
        "raw_source_type": "unknown",
        "source_origin": "unknown",
        "source_class": "unknown",
        "source_role": "unknown",
        "external_public_source": False,
        "eligible_for_external_discovery_backlog": False,
        "primary_source_available": False,
        "source_url_or_citation_available": False,
        "implementation_reference_only": False,
        "internal_evidence_only": False,
        "classification_rule_id": "source_classification_unclassified_v1",
        "classification_provenance": "unknown",
        "classification_confidence": "low",
        "classification_unresolved_reason": "classification_not_yet_applied",
        "citation": "unknown",
        "source_url": "unknown",
        "authors": "unknown",
        "publication_date": "unknown",
        "peer_review_status": "unknown",
        "primary_or_secondary": "unknown",
        "commercial_conflict": "unknown",
        "rules_completeness": "unknown",
        "code_available": "unknown",
        "data_available": "unknown",
        "independent_replication_found": "unknown",
        "contradictory_evidence_found": "unknown",
        "source_claim_summary": "unknown",
        "source_claimed_metrics": {},
        "source_code_reference": "unknown",
        "source_data_reference": "unknown",
        "license": "unknown",
        "credibility_grade": "unknown",
        "review_notes": "unknown",
        "original_source_paths": [],
        "field_origins": {},
    }


def known_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        return "" if text.lower() in {"", "unknown", "not_available", "not_applicable"} else text
    if value in ({}, [], ()):
        return ""
    return str(value)


def source_text_blob(source: dict[str, Any]) -> str:
    values = [
        source.get("source_id"),
        source.get("source_name"),
        source.get("source_type"),
        source.get("raw_source_type"),
        source.get("citation"),
        source.get("source_url"),
        source.get("source_code_reference"),
        source.get("source_data_reference"),
        source.get("review_notes"),
        source.get("source_claim_summary"),
        " ".join(source.get("original_source_paths", []) or []),
    ]
    return " ".join(known_text(value) for value in values).lower()


def is_local_reference(value: Any) -> bool:
    text = known_text(value).replace("\\", "/").lower()
    return bool(text) and (
        any(text.startswith(prefix) for prefix in NON_EXTERNAL_LOCAL_PREFIXES)
        or "/evidence/" in text
        or text.endswith(".yaml")
        or text.endswith(".json")
        or text.endswith(".csv")
        or text.endswith(".py")
    )


def has_external_reference(source: dict[str, Any]) -> bool:
    citation = known_text(source.get("citation"))
    source_url = known_text(source.get("source_url"))
    authors = known_text(source.get("authors"))
    publication_date = known_text(source.get("publication_date"))
    source_code = known_text(source.get("source_code_reference"))
    license_text = known_text(source.get("license"))
    if source_url and not is_local_reference(source_url):
        return True
    if citation and not is_local_reference(citation):
        return True
    if source_code and not is_local_reference(source_code):
        return True
    if authors or publication_date or license_text:
        return True
    return False


def classify_source_record(source: dict[str, Any]) -> dict[str, Any]:
    """Classify one source record without using strategy performance or lifecycle state."""
    row = dict(source)
    raw_source_type = known_text(row.get("raw_source_type")) or known_text(row.get("source_type")) or "unknown"
    row["raw_source_type"] = raw_source_type
    source_id = str(row.get("source_id", "unknown"))
    blob = source_text_blob(row)
    external_ref = has_external_reference(row)

    origin = "unknown"
    source_class = "unknown"
    role = "unknown"
    rule_id = "source_classification_unknown_v1"
    confidence = "low"
    unresolved_reason = "classification_rule_not_matched"

    if "active_combo" in blob and "benchmark" in blob:
        origin = "internal"
        source_class = "internal_benchmark_definition"
        role = "benchmark_definition"
        rule_id = "source_classification_active_combo_internal_benchmark_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif source_id.startswith("project_evidence_") or raw_source_type == "project_evidence_manifest":
        origin = "internal"
        source_class = "internal_project_evidence"
        role = "project_evidence_manifest"
        rule_id = "source_classification_project_evidence_internal_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif source_id.startswith("internal_prompt") or raw_source_type == "internal_prompt":
        origin = "internal"
        source_class = "internal_prompt_idea"
        role = "project_originated_idea"
        rule_id = "source_classification_internal_prompt_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(path.startswith("strategy_lab/strategy_registry") for path in row.get("original_source_paths", []) or []):
        origin = "internal"
        source_class = "internal_registry"
        role = "registry_record"
        rule_id = "source_classification_internal_registry_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(token in blob for token in ["generated_dashboard", "dashboard"]):
        origin = "generated"
        source_class = "generated_dashboard"
        role = "generated_artifact"
        rule_id = "source_classification_generated_dashboard_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(token in blob for token in ["generated_reconciliation", "reconciliation"]):
        origin = "generated"
        source_class = "generated_reconciliation"
        role = "generated_artifact"
        rule_id = "source_classification_generated_reconciliation_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(token in blob for token in ["generated_manifest", "manifest"]):
        origin = "generated"
        source_class = "generated_manifest"
        role = "generated_artifact"
        rule_id = "source_classification_generated_manifest_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(path.startswith("evidence/") for path in row.get("original_source_paths", []) or []):
        origin = "internal"
        source_class = "internal_project_evidence"
        role = "project_evidence_manifest"
        rule_id = "source_classification_evidence_path_internal_v1"
        confidence = "high"
        unresolved_reason = "none"
    elif any(token in blob for token in ["github", "gitlab", "open source", "repository", "source code"]):
        origin = "external"
        source_class = "open_source_implementation_reference"
        role = "implementation_reference"
        rule_id = "source_classification_external_code_reference_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "external_reference_missing"
    elif any(token in blob for token in ["dataset", "benchmark", "index methodology", "data vendor"]):
        origin = "external" if external_ref else "unknown"
        source_class = "benchmark_or_dataset_reference" if external_ref else "unknown"
        role = "benchmark_or_dataset_reference" if external_ref else "unknown"
        rule_id = "source_classification_benchmark_dataset_reference_v1" if external_ref else "source_classification_unknown_benchmark_no_ref_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "source_url_or_citation_missing"
    elif any(token in blob for token in ["book", "long form", "isbn"]):
        origin = "external"
        source_class = "book_or_long_form_reference"
        role = "strategy_research_source"
        rule_id = "source_classification_external_book_reference_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "source_url_or_citation_missing"
    elif any(token in blob for token in ["reddit", "forum", "twitter", "x.com", "community"]):
        origin = "external"
        source_class = "community_lead_only"
        role = "lead_only"
        rule_id = "source_classification_community_lead_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "source_url_or_citation_missing"
    elif any(token in blob for token in ["academic", "paper", "journal", "ssrn", "arxiv"]):
        origin = "external"
        source_class = "academic_primary"
        role = "strategy_research_source"
        rule_id = "source_classification_external_academic_reference_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "source_url_or_citation_missing"
    elif any(token in blob for token in ["public practitioner", "quantpedia", "stockcharts", "investopedia", "fidelity", "wh selfinvest", "chartschool"]):
        origin = "external"
        source_class = "practitioner_research"
        role = "strategy_research_source"
        rule_id = "source_classification_external_practitioner_reference_v1"
        confidence = "medium" if external_ref else "low"
        unresolved_reason = "none" if external_ref else "source_url_or_citation_missing"
    elif external_ref:
        origin = "external"
        source_class = "unverified_external_claim"
        role = "strategy_research_source"
        rule_id = "source_classification_external_reference_uncategorized_v1"
        confidence = "low"
        unresolved_reason = "none"

    implementation_reference_only = source_class in IMPLEMENTATION_REFERENCE_CLASSES
    eligible = bool(
        origin == "external"
        and source_class in EXTERNAL_DISCOVERY_BACKLOG_CLASSES
        and external_ref
        and not implementation_reference_only
    )
    internal_evidence_only = origin in {"internal", "generated"}
    if origin == "external" and not external_ref:
        unresolved_reason = "source_url_or_citation_missing"
    if source_class in {"community_lead_only", "open_source_implementation_reference", "benchmark_or_dataset_reference"}:
        eligible = False

    row.update(
        {
            "source_origin": origin,
            "source_class": source_class,
            "source_role": role,
            "external_public_source": origin == "external",
            "eligible_for_external_discovery_backlog": eligible,
            "primary_source_available": bool(origin == "external" and external_ref and source_class != "community_lead_only"),
            "source_url_or_citation_available": external_ref,
            "implementation_reference_only": implementation_reference_only,
            "internal_evidence_only": internal_evidence_only,
            "classification_rule_id": rule_id,
            "classification_provenance": json.dumps(
                {
                    "source_id": source_id,
                    "raw_source_type": raw_source_type,
                    "citation": row.get("citation", "unknown"),
                    "source_url": row.get("source_url", "unknown"),
                    "original_source_paths": row.get("original_source_paths", []),
                },
                sort_keys=True,
                default=str,
            ),
            "classification_confidence": confidence,
            "classification_unresolved_reason": unresolved_reason,
        }
    )
    return row


def apply_source_classifications(sources: dict[str, dict[str, Any]]) -> None:
    for source_id, source in list(sources.items()):
        sources[source_id] = classify_source_record(source)


def add_or_merge_source(sources: dict[str, dict[str, Any]], source: dict[str, Any]) -> None:
    source_id = source["source_id"]
    if source_id not in sources:
        sources[source_id] = source
        return
    existing = sources[source_id]
    for key, value in source.items():
        if key == "original_source_paths":
            existing[key] = sorted(set(existing.get(key, []) + value))
        elif existing.get(key) in (None, "", "unknown", {}) and value not in (None, "", "unknown", {}):
            existing[key] = value


def source_from_public_candidate(path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = read_yaml(path)
    source_block = payload.get("source", {})
    desc = payload.get("strategy_description", {})
    notes = payload.get("project_notes", {})
    governance = payload.get("governance", {})
    source_id = slug(source_block.get("source_id") or path.stem)
    source = source_template(source_id)
    source.update(
        {
            "source_name": unknown_if_blank(source_block.get("source_name", path.stem)),
            "source_type": unknown_if_blank(source_block.get("source_type", "unknown")),
            "citation": unknown_if_blank(source_block.get("source_url_or_citation", "unknown")),
            "source_url": unknown_if_blank(source_block.get("source_url", "unknown")),
            "rules_completeness": unknown_if_blank(desc.get("rule_clarity", "unknown")),
            "code_available": "unknown",
            "data_available": "unknown",
            "source_claim_summary": unknown_if_blank(desc.get("claimed_hypothesis", "unknown")),
            "source_claimed_metrics": source_block.get("source_claimed_metrics", {}),
            "credibility_grade": unknown_if_blank(notes.get("source_evidence_status", "unknown")),
            "review_notes": unknown_if_blank(notes.get("similarity_notes", "unknown")),
            "original_source_paths": [str(path.relative_to(root)).replace("\\", "/")],
            "field_origins": {
                "source_name": "explicit",
                "source_type": "explicit",
                "citation": "explicit",
                "rules_completeness": "explicit",
                "source_claim_summary": "explicit",
                "source_claimed_metrics": "explicit_or_empty",
            },
        }
    )
    idea = idea_template(source_id)
    family = unknown_if_blank(desc.get("strategy_family", "unknown"))
    fp_values = {
        "family": family,
        "signal_direction": "long_only" if "long" in str(payload.get("rules", {})).lower() else "unknown",
        "universe_type": "|".join(desc.get("instruments", []) or ["unknown"]),
        "formation_horizon": "unknown",
        "holding_horizon": unknown_if_blank(desc.get("timeframe", "unknown")),
        "rebalance_frequency": payload.get("rules", {}).get("rebalance_frequency", "unknown"),
        "weighting_method": "single_asset_or_cash",
        "risk_overlay": payload.get("rules", {}).get("risk_controls", "unknown"),
        "execution_cadence": payload.get("data_and_execution", {}).get("execution_assumptions", "unknown"),
    }
    idea.update(
        {
            "source_id": source_id,
            "idea_id": f"idea_{source_id}",
            "canonical_family_id": slug(family),
            "variant_id": source_id,
            "parent_variant_id": "unknown",
            "title": unknown_if_blank(source_block.get("source_name", source_id)),
            "aliases": [],
            "strategy_fingerprint": strategy_fingerprint(fp_values),
            "strategy_fingerprint_components": fingerprint_payload(fp_values),
            "hypothesis": unknown_if_blank(desc.get("claimed_hypothesis", "unknown")),
            "family": family,
            "subfamily": "unknown",
            "signal_type": "public_source_rule",
            "instrument_universe": desc.get("instruments", ["unknown"]),
            "timeframe": unknown_if_blank(desc.get("timeframe", "unknown")),
            "formation_horizon": "unknown",
            "holding_horizon": unknown_if_blank(desc.get("timeframe", "unknown")),
            "rebalance_frequency": payload.get("rules", {}).get("rebalance_frequency", "unknown"),
            "similar_project_strategies": payload.get("project_screening", {}).get(
                "similar_already_tested_project_families", []
            ),
            "canonical_baseline_id": "unknown",
            "original_source_paths": [str(path.relative_to(root)).replace("\\", "/")],
            "field_origins": {
                "source_id": "explicit",
                "family": "explicit",
                "hypothesis": "explicit",
                "instrument_universe": "explicit",
                "fingerprint": "derived",
            },
        }
    )
    spec = spec_template(f"spec_{source_id}_intake", idea["idea_id"], source_id)
    rules = payload.get("rules", {})
    data_exec = payload.get("data_and_execution", {})
    spec.update(
        {
            "record_kind": "source_rule_spec",
            "qualifies_as_preregistration": False,
            "qualification_provenance": [
                provenance(
                    str(path.relative_to(root)).replace("\\", "/"),
                    "intake_candidate",
                    "public_source_intake_only",
                    "source_rule_spec_not_project_preregistration_v1",
                    "explicit",
                )
            ],
            "entry_rule": unknown_if_blank(rules.get("entry_rule", "unknown")),
            "exit_rule": unknown_if_blank(rules.get("exit_rule", "unknown")),
            "ranking_rule": unknown_if_blank(rules.get("ranking_selection_rule", "unknown")),
            "position_sizing": "unknown",
            "portfolio_weighting": "unknown",
            "risk_controls": unknown_if_blank(rules.get("risk_controls", "unknown")),
            "cash_or_defensive_asset_rule": "BIL/cash if specified by source, otherwise unknown",
            "benchmark_rule": "unknown",
            "parameters": payload.get("indicator_definitions", {}),
            "allowed_parameter_ranges": "not_applicable_or_unknown",
            "required_data": unknown_if_blank(data_exec.get("data_requirements", "unknown")),
            "signal_timestamp": "completed_bar_close_or_unknown",
            "order_timestamp": "project_shifted_weight_convention_or_unknown",
            "assumed_execution_price": unknown_if_blank(data_exec.get("execution_assumptions", "unknown")),
            "preregistration_version": str(payload.get("schema_version", 1)),
            "preregistration_timestamp": "unknown",
            "original_source_paths": [str(path.relative_to(root)).replace("\\", "/")],
        }
    )
    if governance.get("promotion_or_paper_forward_allowed") is False:
        spec["stop_conditions"] = "no promotion or paper/demo activation from intake"
    return source, idea, spec


def idea_template(variant_id: str) -> dict[str, Any]:
    return {
        "idea_id": f"idea_{slug(variant_id)}",
        "source_id": "unknown",
        "canonical_family_id": "unknown",
        "variant_id": variant_id,
        "parent_variant_id": "unknown",
        "title": "unknown",
        "aliases": [],
        "strategy_fingerprint": "unknown",
        "strategy_fingerprint_components": {},
        "hypothesis": "unknown",
        "family": "unknown",
        "subfamily": "unknown",
        "signal_type": "unknown",
        "instrument_universe": "unknown",
        "timeframe": "unknown",
        "formation_horizon": "unknown",
        "holding_horizon": "unknown",
        "rebalance_frequency": "unknown",
        "similar_project_strategies": [],
        "canonical_baseline_id": "unknown",
        "original_source_paths": [],
        "field_origins": {},
    }


def spec_template(spec_id: str, idea_id: str, variant_id: str) -> dict[str, Any]:
    return {
        "specification_id": spec_id,
        "idea_id": idea_id,
        "variant_id": variant_id,
        "record_kind": "unknown",
        "qualifies_as_preregistration": False,
        "qualification_provenance": [],
        "qualification_missing_fields": [],
        "qualification_blocking_reasons": [],
        "specification_content_hash": "unknown",
        "field_provenance": {},
        "strategy_universe": "unknown",
        "timeframe": "unknown",
        "rebalance_cadence": "unknown",
        "frozen_specification_reference": "unknown",
        "entry_rule": "unknown",
        "exit_rule": "unknown",
        "ranking_rule": "unknown",
        "position_sizing": "unknown",
        "portfolio_weighting": "unknown",
        "risk_controls": "unknown",
        "cash_or_defensive_asset_rule": "unknown",
        "benchmark_rule": "unknown",
        "parameters": {},
        "allowed_parameter_ranges": "unknown",
        "required_data": "unknown",
        "data_availability_lag": "unknown",
        "signal_timestamp": "unknown",
        "order_timestamp": "unknown",
        "assumed_execution_price": "unknown",
        "commission_model": "unknown",
        "spread_model": "unknown",
        "slippage_model": "unknown",
        "borrow_assumptions": "unknown",
        "financing_assumptions": "unknown",
        "futures_roll_assumptions": "unknown",
        "expected_weaknesses": "unknown",
        "success_criteria": "unknown",
        "failure_criteria": "unknown",
        "allowed_follow_up_tests": "unknown",
        "stop_conditions": "unknown",
        "preregistration_version": "unknown",
        "preregistration_timestamp": "unknown",
        "original_source_paths": [],
        "field_origins": {},
    }


def implementation_template(implementation_id: str, variant_id: str) -> dict[str, Any]:
    return {
        "implementation_id": implementation_id,
        "variant_id": variant_id,
        "qualifies_as_reproducible_implementation": False,
        "implementation_evidence_provenance": [],
        "qualification_missing_fields": [],
        "qualification_blocking_reasons": [],
        "linked_qualifying_specification_ids": [],
        "linked_tests": [],
        "implementation_review_artifacts": [],
        "repository_path": "unknown",
        "code_commit_hash": "unknown",
        "code_content_hash": "unknown",
        "configuration_hash": "unknown",
        "dependency_lock_hash": "unknown",
        "unit_test_status": "unknown",
        "source_replication_status": "unknown",
        "implementation_review_status": "unknown",
        "original_source_paths": [],
    }


def experiment_template(experiment_id: str, variant_id: str, implementation_id: str) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "run_id": "latest",
        "variant_id": variant_id,
        "implementation_id": implementation_id,
        "qualifies_as_local_backtest": False,
        "local_backtest_evidence_provenance": [],
        "qualifies_as_robustness": False,
        "robustness_evidence_provenance": [],
        "experiment_record_kind": "unknown",
        "underlying_run_key": "unknown",
        "qualification_missing_fields": [],
        "qualification_blocking_reasons": [],
        "linked_qualifying_specification_ids": [],
        "linked_qualifying_implementation_id": "unknown",
        "data_snapshot_hash": "unknown",
        "in_sample_period": "unknown",
        "validation_period": "unknown",
        "holdout_period": "unknown",
        "holdout_first_seen_timestamp": "unknown",
        "strategy_trial_number": "unknown",
        "family_trial_count": "unknown",
        "cost_scenario": "unknown",
        "locally_observed_metrics": {},
        "robustness_results": {},
        "pbo_fields": {},
        "dsr_fields": {},
        "artifact_references": [],
        "original_source_paths": [],
    }


def decision_template(decision_id: str, idea_id: str, variant_id: str) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "idea_id": idea_id,
        "variant_id": variant_id,
        "record_role": "unknown",
        "evidence_level": "E0",
        "evidence_chain": ["E0"],
        "verified_evidence_level": "E0",
        "evidence_level_provenance": [],
        "project_status": "backlog",
        "canonical_lifecycle_status": "unknown",
        "project_status_detail": "unknown",
        "source_project_status": "unknown",
        "source_status_detail": "unknown",
        "lifecycle_status_provenance": [],
        "record_role_provenance": [],
        "decision_date": "unknown",
        "reviewer": "unknown",
        "rejection_reason_code": [],
        "failure_code_provenance": [],
        "rejection_notes": "unknown",
        "retest_conditions": "unknown",
        "next_research_action": "unknown",
        "frozen_paper_demo_configuration_hash": "unknown",
        "active_observation_linkage": {},
        "legacy_active_observation_with_incomplete_evidence_chain": False,
        "missing_evidence_stages": [],
        "complete_linked_evidence_chain": [],
        "historical_recovered_metrics": {},
        "historical_metric_role": "not_applicable",
        "historical_metric_evidence_status": "not_applicable",
        "current_diagnostic_metrics": {},
        "current_diagnostic_role": "not_applicable",
        "current_diagnostic_scope": "not_applicable",
        "metric_comparability": "not_applicable",
        "metric_eligible_for_evidence_stage": {},
        "evidence_warning": "none",
        "source_artifact_provenance": [],
        "observation_dates": "unknown",
        "retirement_reason": "unknown",
        "original_source_paths": [],
    }


def registry_row_to_records(row: dict[str, Any], root: Path, active_records: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    variant_id = str(row.get("id") or row.get("strategy_id") or "unknown")
    family = row.get("family") or row.get("strategy_family") or "unknown"
    source_id = f"internal_prompt_{slug(family)}"
    source = source_template(source_id)
    source.update(
        {
            "source_name": f"Internal prompt / project registry: {family}",
            "source_type": "internal_prompt",
            "citation": str(REGISTRY_PATH).replace("\\", "/"),
            "rules_completeness": "unknown",
            "source_claim_summary": "Internal project-originated or prompt-originated strategy registry row.",
            "credibility_grade": row.get("credibility_tier", "unknown"),
            "review_notes": row.get("notes", "unknown"),
            "original_source_paths": [str(REGISTRY_PATH).replace("\\", "/")],
            "field_origins": {
                "source_type": "derived_from_missing_external_source",
                "citation": "derived",
                "credibility_grade": "explicit",
            },
        }
    )
    fp_values = {
        "family": family,
        "signal_direction": "long_only" if "short" not in str(row).lower() else "unknown",
        "universe_type": row.get("instrument_family") or row.get("instrument_lane") or "unknown",
        "formation_horizon": "unknown",
        "holding_horizon": "unknown",
        "rebalance_frequency": row.get("lane") or "unknown",
        "weighting_method": row.get("role") or "unknown",
        "risk_overlay": row.get("risk_budget_status") or row.get("risk_framework_status") or "unknown",
        "execution_cadence": row.get("data_source") or "unknown",
    }
    idea = idea_template(variant_id)
    idea.update(
        {
            "source_id": source_id,
            "canonical_family_id": slug(family),
            "parent_variant_id": unknown_if_blank(row.get("parent_id", "unknown")),
            "title": row.get("display_name", variant_id),
            "family": family,
            "instrument_universe": row.get("instrument_family") or row.get("instrument_lane") or "unknown",
            "timeframe": row.get("lane", "unknown"),
            "rebalance_frequency": row.get("lane", "unknown"),
            "signal_type": row.get("role", "unknown"),
            "strategy_fingerprint": strategy_fingerprint(fp_values),
            "strategy_fingerprint_components": fingerprint_payload(fp_values),
            "similar_project_strategies": [row.get("duplicate_of")] if row.get("duplicate_of") else [],
            "canonical_baseline_id": "unknown",
            "original_source_paths": [str(REGISTRY_PATH).replace("\\", "/")],
            "field_origins": {
                "variant_id": "explicit",
                "family": "explicit",
                "status": "explicit",
                "fingerprint": "derived",
                "source_id": "derived_internal_prompt",
            },
        }
    )
    decision = decision_template(f"decision_{slug(variant_id)}_registry", idea["idea_id"], variant_id)
    status = row.get("current_status") or row.get("status") or "unknown"
    source_path = str(REGISTRY_PATH).replace("\\", "/")
    project_status, lifecycle_prov = normalize_lifecycle_status(status, source_path, "current_status")
    record_role, role_prov = record_role_from_fields(status, row.get("role"), source_path)
    failure_prov = failure_provenance_from_fields(
        source_path,
        {
            "status": row.get("status"),
            "current_status": row.get("current_status"),
            "primary_failure_mode": row.get("primary_failure_mode"),
            "promotion_decision": row.get("promotion_decision"),
        },
    )
    explicit_active = variant_id in active_records
    if explicit_active:
        evidence_level = "E1"
        active_record = active_records[variant_id]
        frozen_hash = active_record["frozen_hash"]
        project_status = "active"
        lifecycle_prov = provenance(
            active_record["detail_path"],
            "status",
            active_record["detail_status"],
            "lifecycle_canonical_active_observation_v1",
            "explicit",
        )
        record_role = "paper_demo_observation"
        role_prov = provenance(
            active_record["detail_path"],
            "status",
            active_record["detail_status"],
            "record_role_canonical_active_observation_v1",
            "explicit",
        )
    else:
        evidence_level = "E1"
        frozen_hash = "unknown"
        active_record = {}
    decision.update(
        {
            "record_role": record_role,
            "evidence_level": evidence_level,
            "evidence_chain": evidence_chain(evidence_level),
            "verified_evidence_level": evidence_level,
            "evidence_level_provenance": [
                provenance(
                    source_path if not explicit_active else active_record["detail_path"],
                    "canonical_active_observation" if explicit_active else "strategy_registry_row",
                    status,
                    "active_lifecycle_not_sufficient_for_e7_v1" if explicit_active else "evidence_e1_registry_provenance_v1",
                    "explicit" if explicit_active else "derived",
                )
            ],
            "project_status": project_status,
            "canonical_lifecycle_status": project_status,
            "project_status_detail": status,
            "source_project_status": status,
            "source_status_detail": status,
            "lifecycle_status_provenance": [lifecycle_prov],
            "record_role_provenance": [role_prov],
            "rejection_reason_code": failure_codes_from_provenance(failure_prov),
            "failure_code_provenance": failure_prov,
            "rejection_notes": row.get("promotion_reason") or row.get("latest_known_result_summary") or "unknown",
            "retest_conditions": row.get("evidence_needed") or row.get("allowed_next_action") or "unknown",
            "next_research_action": row.get("allowed_next_action") or row.get("next_allowed_action") or "unknown",
            "frozen_paper_demo_configuration_hash": frozen_hash,
            "active_observation_linkage": active_record if explicit_active else {},
            "legacy_active_observation_with_incomplete_evidence_chain": explicit_active,
            "missing_evidence_stages": ["E2", "E3", "E4", "E5", "E6"] if explicit_active else [],
            "complete_linked_evidence_chain": [],
            "original_source_paths": [str(REGISTRY_PATH).replace("\\", "/")],
        }
    )
    if explicit_active and variant_id == DSR_ACTIVE_ID:
        dsr_status = load_dsr_evidence_status(root)
        decision.update(
            {
                "historical_recovered_metrics": dsr_status["historical_recovered_metrics"],
                "historical_metric_role": dsr_status["historical_metric_role"],
                "historical_metric_evidence_status": dsr_status["historical_metric_evidence_status"],
                "current_diagnostic_metrics": dsr_status["current_diagnostic_metrics"],
                "current_diagnostic_role": dsr_status["current_diagnostic_role"],
                "current_diagnostic_scope": dsr_status["current_diagnostic_scope"],
                "metric_comparability": dsr_status["metric_comparability"],
                "metric_eligible_for_evidence_stage": dsr_status["metric_eligible_for_evidence_stage"],
                "evidence_warning": dsr_status["evidence_warning"],
                "source_artifact_provenance": dsr_status["source_artifact_provenance"],
            }
        )
    return source, idea, decision


def related_python_paths(root: Path, tokens: Iterable[str]) -> list[Path]:
    token_set = {slug(t) for token in tokens for t in str(token).split("_") if len(t) > 2}
    if not token_set:
        return []
    paths = list(root.glob("run_*.py")) + list((root / "strategy_lab" / "research_os" / "research").glob("*.py"))
    scored: list[tuple[int, Path]] = []
    for path in paths:
        haystack = slug(path.as_posix())
        score = sum(1 for token in token_set if token in haystack)
        if score >= 2:
            scored.append((score, path))
    return [path for _, path in sorted(scored, key=lambda item: (-item[0], str(item[1])))[:4]]


def classify_evidence_dir(path: Path) -> str:
    name = path.parent.name.lower()
    if "robustness" in name:
        return "robustness"
    if "run" in name or "batch" in name or "rerun" in name:
        return "run"
    if "design" in name or "preregistration" in name:
        return "design"
    if "audit" in name:
        return "audit"
    if "intake" in name or "bridge" in name:
        return "source_intake"
    if "reconciliation" in name:
        return "reconciliation"
    return "evidence"


def manifest_to_records(
    manifest_path: Path,
    root: Path,
    sources: dict[str, dict[str, Any]],
    ideas: dict[str, dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    implementations: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    code_commit: str,
    dep_hash: str,
    data_hash: str,
) -> None:
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return
    evidence_dir = manifest_path.parent
    rel_manifest = str(manifest_path.relative_to(root)).replace("\\", "/")
    evidence_kind = classify_evidence_dir(evidence_dir)
    source_id = manifest.get("source_id")
    family = manifest.get("family_id") or manifest.get("family") or "unknown"
    variant_id = (
        manifest.get("lane_id")
        or manifest.get("batch_id")
        or manifest.get("source_id")
        or evidence_dir.parent.name
    )
    variant_id = str(variant_id)
    if source_id and source_id not in sources:
        source = source_template(slug(source_id))
        source.update(
            {
                "source_name": str(source_id),
                "source_type": "public_source_or_project_manifest",
                "citation": rel_manifest,
                "source_claim_summary": "Source referenced by project evidence manifest.",
                "original_source_paths": [rel_manifest],
            }
        )
        add_or_merge_source(sources, source)
    elif not source_id:
        source_id = f"project_evidence_{slug(family if family != 'unknown' else variant_id)}"
        if source_id not in sources:
            source = source_template(source_id)
            source.update(
                {
                    "source_name": f"Internal project evidence: {family if family != 'unknown' else variant_id}",
                    "source_type": "project_evidence_manifest",
                    "citation": rel_manifest,
                    "source_claim_summary": "Evidence manifest without an external source id.",
                    "original_source_paths": [rel_manifest],
                }
            )
            add_or_merge_source(sources, source)
    idea_id = f"idea_{slug(variant_id)}"
    if idea_id not in ideas:
        fp_values = {
            "family": family,
            "signal_direction": "unknown",
            "universe_type": "unknown",
            "formation_horizon": "unknown",
            "holding_horizon": "unknown",
            "rebalance_frequency": "unknown",
            "weighting_method": "unknown",
            "risk_overlay": "unknown",
            "execution_cadence": evidence_kind,
        }
        idea = idea_template(variant_id)
        idea.update(
            {
                "idea_id": idea_id,
                "source_id": slug(source_id),
                "canonical_family_id": slug(family),
                "title": variant_id,
                "family": family,
                "strategy_fingerprint": strategy_fingerprint(fp_values),
                "strategy_fingerprint_components": fingerprint_payload(fp_values),
                "original_source_paths": [rel_manifest],
                "field_origins": {
                    "variant_id": "derived_from_manifest",
                    "family": "explicit_or_unknown",
                    "source_id": "explicit_or_derived",
                    "fingerprint": "derived",
                },
            }
        )
        ideas[idea_id] = idea
    else:
        ideas[idea_id].setdefault("original_source_paths", []).append(rel_manifest)
        ideas[idea_id]["original_source_paths"] = sorted(set(ideas[idea_id]["original_source_paths"]))
    if evidence_kind in {"design", "source_intake"}:
        spec_id = f"spec_{slug(variant_id)}_{evidence_kind}"
        if spec_id not in specs:
            spec = spec_template(spec_id, idea_id, variant_id)
            is_design = evidence_kind == "design"
            spec.update(
                {
                    "record_kind": "design_evidence_reference" if is_design else "source_intake_reference",
                    "source_run_readiness_decision": manifest.get("run_readiness_decision", "unknown"),
                    "source_design_status": manifest.get("design_decision", manifest.get("status", "unknown")),
                    "qualification_source_status": manifest.get("run_readiness_decision", evidence_kind),
                    "parameters": {},
                    "preregistration_version": str(manifest.get("schema_version", 1)),
                    "preregistration_timestamp": manifest.get("created_utc", manifest.get("timestamp_utc", "unknown")),
                    "original_source_paths": [rel_manifest],
                    "field_origins": {"specification": "derived_from_design_or_intake_manifest"},
                }
            )
            extract_manifest_spec_fields(spec, manifest, rel_manifest, manifest_path)
            apply_spec_qualification(spec)
            specs[spec_id] = spec
    if evidence_kind in {"run", "robustness", "audit", "reconciliation"}:
        code_paths = related_python_paths(root, [variant_id, source_id, evidence_dir.parent.name])
        impl_id = f"impl_{slug(variant_id)}"
        rel_paths = [str(path.relative_to(root)).replace("\\", "/") for path in code_paths]
        qualifying_spec_ids = [
            spec["specification_id"]
            for spec in specs.values()
            if spec["idea_id"] == idea_id and qualifies_preregistration(spec)
        ]
        if impl_id not in implementations:
            impl = implementation_template(impl_id, variant_id)
            impl.update(
                {
                    "linked_qualifying_specification_ids": qualifying_spec_ids,
                    "linked_tests": manifest.get("linked_tests", []),
                    "implementation_review_artifacts": manifest.get("implementation_review_artifacts", []),
                    "implementation_evidence_provenance": [
                        provenance(
                            rel_manifest,
                            "related_python_paths",
                            rel_paths,
                            "implementation_path_hash_present_v1" if rel_paths else "implementation_path_missing_v1",
                            "derived",
                        )
                    ],
                    "repository_path": rel_paths[0] if rel_paths else "unknown",
                    "code_commit_hash": code_commit,
                    "code_content_hash": hash_data({p: hash_file(root / p) for p in rel_paths}) if rel_paths else "unknown",
                    "configuration_hash": hash_file(manifest_path),
                    "dependency_lock_hash": dep_hash,
                    "unit_test_status": "unknown",
                    "source_replication_status": "diagnostic_project_evidence",
                    "implementation_review_status": manifest.get("audit_decision")
                    or manifest.get("final_audit_decision")
                    or manifest.get("run_readiness_decision")
                    or "unknown",
                    "original_source_paths": [rel_manifest],
                }
            )
            apply_implementation_qualification(impl)
            implementations[impl_id] = impl
        impl_qualifies = qualifies_implementation(implementations[impl_id])
        exp_id = f"exp_{slug(evidence_dir.parent.name)}"
        if exp_id not in experiments:
            experiment_record_kind = (
                "local_backtest_run"
                if evidence_kind == "run"
                else "robustness_report"
                if evidence_kind == "robustness"
                else f"{evidence_kind}_reference"
            )
            qualifies_backtest = bool(
                evidence_kind == "run"
                and impl_qualifies
                and (manifest.get("variant_count_evaluated") is not None or manifest.get("rows_evaluated") is not None)
                and manifest.get("provider_download") is not True
            )
            qualifies_robust = bool(
                evidence_kind == "robustness"
                and impl_qualifies
                and manifest.get("robustness_evidence_usable") is True
                and (
                    (manifest.get("rows_remain_interesting_after_robustness") or 0) > 0
                    or (
                        manifest.get("primary_row_10bps_stress_pass") is True
                        and manifest.get("primary_row_25bps_stress_pass") is True
                        and manifest.get("primary_row_rolling_window_weakness") is not True
                    )
                )
            )
            observed_keys = [
                key
                for key in manifest
                if any(
                    token in key
                    for token in [
                        "count",
                        "cagr",
                        "return",
                        "drawdown",
                        "volatility",
                        "criteria",
                        "invariant",
                        "decision",
                        "evaluated",
                        "planned",
                        "passed",
                        "failed",
                    ]
                )
            ]
            exp = experiment_template(exp_id, variant_id, impl_id)
            exp_missing: list[str] = []
            exp_blockers: list[str] = []
            if evidence_kind in {"audit", "reconciliation"}:
                exp_blockers.append(f"{evidence_kind}_does_not_create_distinct_local_backtest")
            if not impl_qualifies:
                exp_missing.append("qualifying_e3_implementation")
            if evidence_kind == "run" and not observed_keys:
                exp_missing.append("locally_observed_metrics")
            exp.update(
                {
                    "qualifies_as_local_backtest": qualifies_backtest,
                    "experiment_record_kind": experiment_record_kind,
                    "underlying_run_key": manifest.get("run_id") or str(evidence_dir.parent.name),
                    "qualification_missing_fields": sorted(set(exp_missing)),
                    "qualification_blocking_reasons": sorted(set(exp_blockers)),
                    "linked_qualifying_specification_ids": qualifying_spec_ids,
                    "linked_qualifying_implementation_id": impl_id if impl_qualifies else "unknown",
                    "local_backtest_evidence_provenance": [
                        provenance(
                            rel_manifest,
                            "variant_count_evaluated/rows_evaluated",
                            manifest.get("variant_count_evaluated", manifest.get("rows_evaluated", "unknown")),
                            "local_backtest_manifest_with_implementation_v1" if qualifies_backtest else "local_backtest_not_qualified_v1",
                            "explicit" if qualifies_backtest else "derived",
                        )
                    ],
                    "qualifies_as_robustness": qualifies_robust,
                    "robustness_evidence_provenance": [
                        provenance(
                            rel_manifest,
                            "robustness_evidence_usable_and_pass_fields",
                            {
                                "robustness_evidence_usable": manifest.get("robustness_evidence_usable"),
                                "rows_remain_interesting_after_robustness": manifest.get("rows_remain_interesting_after_robustness"),
                                "primary_row_10bps_stress_pass": manifest.get("primary_row_10bps_stress_pass"),
                                "primary_row_25bps_stress_pass": manifest.get("primary_row_25bps_stress_pass"),
                            },
                            "robustness_explicit_survivor_or_clean_primary_v1" if qualifies_robust else "robustness_not_qualified_v1",
                            "explicit" if qualifies_robust else "derived",
                        )
                    ],
                    "run_id": manifest.get("run_id", "latest"),
                    "data_snapshot_hash": data_hash,
                    "cost_scenario": manifest.get("cost_scenario", "unknown"),
                    "locally_observed_metrics": {key: manifest.get(key) for key in observed_keys},
                    "robustness_results": {key: manifest.get(key) for key in observed_keys if "robust" in key},
                    "artifact_references": [str(evidence_dir.relative_to(root)).replace("\\", "/")],
                    "original_source_paths": [rel_manifest],
                }
            )
            experiments[exp_id] = exp
    decision_id = f"decision_{slug(variant_id)}_{evidence_kind}"
    if decision_id not in decisions:
        decision = decision_template(decision_id, idea_id, variant_id)
        status_detail = (
            manifest.get("final_audit_decision")
            or manifest.get("audit_decision")
            or manifest.get("run_readiness_decision")
            or manifest.get("next_action")
            or evidence_kind
        )
        project_status, lifecycle_prov = normalize_lifecycle_status(status_detail, rel_manifest, "decision_or_next_action")
        record_role, role_prov = record_role_from_fields(status_detail, manifest.get("variant_role", evidence_kind), rel_manifest)
        spec_qualifies = any(qualifies_preregistration(spec) for spec in specs.values() if spec["idea_id"] == idea_id)
        impl_qualifies_now = spec_qualifies and any(
            qualifies_implementation(impl) for impl in implementations.values() if impl["variant_id"] == variant_id
        )
        exp_rows = [exp for exp in experiments.values() if exp["variant_id"] == variant_id]
        backtest_qualifies = any(exp.get("qualifies_as_local_backtest") for exp in exp_rows) and impl_qualifies_now
        robust_qualifies = any(exp.get("qualifies_as_robustness") for exp in exp_rows) and backtest_qualifies
        if robust_qualifies:
            level = "E5"
            level_rule = "evidence_e5_explicit_robustness_qualified_v1"
        elif backtest_qualifies:
            level = "E4"
            level_rule = "evidence_e4_local_backtest_with_qualifying_implementation_v1"
        elif impl_qualifies_now:
            level = "E3"
            level_rule = "evidence_e3_qualifying_implementation_v1"
        elif spec_qualifies:
            level = "E2"
            level_rule = "evidence_e2_qualifying_preregistration_v1"
        else:
            level = "E1"
            level_rule = "evidence_e1_project_or_source_provenance_v1"
        failure_prov = failure_provenance_from_fields(
            rel_manifest,
            {
                "audit_decision": manifest.get("audit_decision"),
                "final_audit_decision": manifest.get("final_audit_decision"),
                "run_readiness_decision": manifest.get("run_readiness_decision"),
                "next_action": manifest.get("next_action"),
            },
        )
        decision.update(
            {
                "record_role": record_role,
                "evidence_level": level,
                "evidence_chain": evidence_chain(level),
                "verified_evidence_level": level,
                "evidence_level_provenance": [
                    provenance(rel_manifest, "qualifying_evidence", evidence_kind, level_rule, "derived")
                ],
                "project_status": project_status,
                "canonical_lifecycle_status": project_status,
                "project_status_detail": status_detail,
                "source_project_status": status_detail,
                "source_status_detail": status_detail,
                "lifecycle_status_provenance": [lifecycle_prov],
                "record_role_provenance": [role_prov],
                "decision_date": manifest.get("created_utc", manifest.get("timestamp_utc", "unknown")),
                "rejection_reason_code": failure_codes_from_provenance(failure_prov),
                "failure_code_provenance": failure_prov,
                "rejection_notes": str(status_detail),
                "next_research_action": manifest.get("next_action", "unknown"),
                "complete_linked_evidence_chain": evidence_chain(level),
                "original_source_paths": [rel_manifest],
            }
        )
        decisions[decision_id] = decision


def build_active_observation_records(root: Path) -> dict[str, dict[str, Any]]:
    active_records: dict[str, dict[str, Any]] = {}
    operations = read_yaml(root / ACTIVE_OBSERVATIONS_PATH)
    for row in operations.get("active_observations", []) if isinstance(operations, dict) else []:
        strategy_id = row.get("strategy_id")
        if not strategy_id or row.get("paper_forward_active") is not True:
            continue
        detail_path = root / "paper_forward_observations" / str(strategy_id) / "active_observation.yaml"
        detail = read_yaml(detail_path)
        detail_matches = (
            detail_path.exists()
            and detail.get("observation_id") == strategy_id
            and detail.get("status") == "active_paper_demo_observation"
            and detail.get("paper_forward_active") is True
            and detail.get("frozen") is True
            and detail.get("rules_frozen") is True
        )
        if not detail_matches:
            continue
        rel_detail = str(detail_path.relative_to(root)).replace("\\", "/")
        rel_index = str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/")
        active_records[str(strategy_id)] = {
            "strategy_id": str(strategy_id),
            "index_path": rel_index,
            "detail_path": rel_detail,
            "index_state": row.get("state", "unknown"),
            "detail_status": detail.get("status", "unknown"),
            "index_detail_agree": True,
            "frozen_hash": hash_data({"index_row": row, "detail_hash": hash_file(detail_path)}),
        }
    return active_records


def ensure_cumulative_records(
    root: Path,
    ideas: dict[str, dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    implementations: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    code_commit: str,
    dep_hash: str,
    data_hash: str,
) -> None:
    spec_by_idea = defaultdict(list)
    for spec in specs.values():
        spec_by_idea[spec["idea_id"]].append(spec)
    impl_by_variant = defaultdict(list)
    for impl in implementations.values():
        impl_by_variant[impl["variant_id"]].append(impl)
    exp_by_variant = defaultdict(list)
    for exp in experiments.values():
        exp_by_variant[exp["variant_id"]].append(exp)
    for decision in list(decisions.values()):
        level = decision["evidence_level"]
        idea = ideas.get(decision["idea_id"])
        if not idea:
            continue
        if level == "E7":
            continue
        variant_id = decision["variant_id"]
        if level_rank(level) >= level_rank("E2") and not spec_by_idea[idea["idea_id"]]:
            spec_id = f"spec_{slug(variant_id)}_migration_placeholder"
            spec = spec_template(spec_id, idea["idea_id"], variant_id)
            spec.update(
                {
                    "record_kind": "migration_placeholder",
                    "qualifies_as_preregistration": False,
                    "qualification_provenance": [
                        provenance(
                            ";".join(idea.get("original_source_paths", [])) or "unknown",
                            "migration_placeholder",
                            "placeholder_only",
                            "migration_placeholder_not_preregistration_v1",
                            "placeholder",
                        )
                    ],
                    "entry_rule": "unknown_migrated_from_registry_or_evidence",
                    "exit_rule": "unknown_migrated_from_registry_or_evidence",
                    "preregistration_version": "migration_placeholder",
                    "original_source_paths": idea.get("original_source_paths", []),
                    "field_origins": {"specification": "unknown_migration_placeholder"},
                }
            )
            specs[spec_id] = spec
            spec_by_idea[idea["idea_id"]].append(spec)
        if level_rank(level) >= level_rank("E3") and not impl_by_variant[variant_id]:
            impl_id = f"impl_{slug(variant_id)}_migration_reference"
            impl = implementation_template(impl_id, variant_id)
            impl.update(
                {
                    "repository_path": "strategy_lab/strategy_registry.yaml",
                    "code_commit_hash": code_commit,
                    "code_content_hash": hash_file(root / REGISTRY_PATH),
                    "configuration_hash": hash_data(idea),
                    "dependency_lock_hash": dep_hash,
                    "unit_test_status": "unknown",
                    "source_replication_status": "migration_reference_only",
                    "implementation_review_status": "unknown",
                    "original_source_paths": idea.get("original_source_paths", []),
                }
            )
            implementations[impl_id] = impl
            impl_by_variant[variant_id].append(impl)
        if level_rank(level) >= level_rank("E4") and not exp_by_variant[variant_id]:
            impl_id = impl_by_variant[variant_id][0]["implementation_id"]
            exp_id = f"exp_{slug(variant_id)}_migration_reference"
            exp = experiment_template(exp_id, variant_id, impl_id)
            exp.update(
                {
                    "data_snapshot_hash": data_hash,
                    "locally_observed_metrics": {"migration_reference": True},
                    "artifact_references": idea.get("original_source_paths", []),
                    "original_source_paths": idea.get("original_source_paths", []),
                }
            )
            experiments[exp_id] = exp
            exp_by_variant[variant_id].append(exp)


def list_tree(root: Path) -> dict[str, Any]:
    top = []
    for path in sorted(root.iterdir()):
        if path.name == ".git":
            continue
        if path.is_dir():
            if path.name in {".venv", ".pytest_cache"}:
                files = "ignored_generated_or_environment"
            else:
                try:
                    files = sum(1 for child in path.rglob("*") if child.is_file() and ".venv" not in child.parts)
                except Exception:
                    files = "unknown"
            top.append({"path": path.name, "type": "directory", "file_count": files})
        else:
            top.append({"path": path.name, "type": "file", "file_count": 1})
    return {"top_level": top}


def cleanup_generated_python_caches(root: Path) -> list[dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    for path in sorted(root.rglob("__pycache__")):
        if ".venv" in path.parts:
            continue
        resolved = path.resolve()
        if root.resolve() not in resolved.parents and resolved != root.resolve():
            continue
        if path.name != "__pycache__":
            continue
        pyc_count = len(list(path.glob("*.pyc")))
        shutil.rmtree(path)
        removed.append(
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "previous_purpose": "Python bytecode cache",
                "classification": "generated",
                "evidence_unused_or_regenerable": "__pycache__ is ignored by .gitignore and regenerated by Python imports",
                "information_migrated": False,
                "migration_destination": "not_applicable_generated_cache",
                "validation": "tests/imports regenerate bytecode as needed",
                "residual_risk": "none_expected; source .py files preserved",
                "pyc_file_count": pyc_count,
            }
        )
    return removed


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def stringify_csv(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=str)
    return "" if value is None else str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: stringify_csv(row.get(key, "")) for key in fieldnames})


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = [stringify_csv(row.get(col, "")).replace("|", "\\|").replace("\n", " ") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def write_md(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines.extend([f"## {heading}", "", body.rstrip(), ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def semantic_snapshot(decisions: list[dict[str, Any]], specs: list[dict[str, Any]]) -> dict[str, Any]:
    spec_by_idea = defaultdict(list)
    for spec in specs:
        spec_by_idea[spec["idea_id"]].append(spec)
    placeholder_specs = [
        spec
        for spec in specs
        if spec.get("record_kind") == "migration_placeholder"
        or spec.get("preregistration_version") == "migration_placeholder"
    ]
    placeholder_decisions = []
    placeholder_e2 = []
    for decision in decisions:
        placeholders = [
            spec
            for spec in spec_by_idea.get(decision["idea_id"], [])
            if spec.get("record_kind") == "migration_placeholder"
            or spec.get("preregistration_version") == "migration_placeholder"
        ]
        if placeholders:
            placeholder_decisions.append(decision)
            if level_rank(decision.get("evidence_level", "E0")) >= level_rank("E2"):
                placeholder_e2.append(decision)
    return {
        "evidence_funnel": dict(sorted(Counter(d.get("evidence_level", "unknown") for d in decisions).items())),
        "lifecycle_counts": dict(sorted(Counter(d.get("project_status", "unknown") for d in decisions).items())),
        "spec_count": len(specs),
        "migration_placeholder_spec_count": len(placeholder_specs),
        "placeholder_linked_decision_count": len(placeholder_decisions),
        "placeholder_linked_e2_or_higher_decision_count": len(placeholder_e2),
        "qualifying_preregistration_count": sum(1 for spec in specs if qualifies_preregistration(spec)),
        "failure_code_assignment_count": sum(len(d.get("rejection_reason_code", [])) for d in decisions),
        "failure_code_provenance_count": sum(len(d.get("failure_code_provenance", [])) for d in decisions),
    }


def load_previous_semantic_snapshot(output: Path) -> dict[str, Any]:
    decisions_path = output / "sel_decisions.json"
    specs_path = output / "sel_preregistrations.json"
    if not decisions_path.exists() or not specs_path.exists():
        return VERIFIED_PRE_PATCH_SEMANTIC_BASELINE
    try:
        snapshot = semantic_snapshot(read_json(decisions_path), read_json(specs_path))
        if snapshot.get("migration_placeholder_spec_count", 0) < 100 and snapshot.get("failure_code_assignment_count", 0) < 200:
            return VERIFIED_PRE_PATCH_SEMANTIC_BASELINE
        return snapshot
    except Exception:
        return VERIFIED_PRE_PATCH_SEMANTIC_BASELINE


def semantic_change_rows(
    previous_decisions: list[dict[str, Any]],
    current_decisions: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    previous = {row["decision_id"]: row for row in previous_decisions}
    rows: list[dict[str, Any]] = []
    for current in current_decisions:
        old = previous.get(current["decision_id"])
        if not old:
            continue
        if old.get(field) != current.get(field):
            rows.append(
                {
                    "decision_id": current["decision_id"],
                    "variant_id": current["variant_id"],
                    f"previous_{field}": old.get(field),
                    f"corrected_{field}": current.get(field),
                    "source_status_detail": current.get("source_status_detail", current.get("project_status_detail")),
                }
            )
    return rows


def cumulative_evidence_correction_tables(library: dict[str, Any], previous_snapshot: dict[str, Any]) -> dict[str, Any]:
    specs = library["specifications"]
    impls = library["implementations"]
    exps = library["experiments"]
    decisions = library["decisions"]
    e2_rows = []
    for spec in specs:
        qualifies, missing, blockers = evaluate_spec_qualification(spec)
        e2_rows.append(
            {
                "specification_id": spec["specification_id"],
                "variant_id": spec["variant_id"],
                "record_kind": spec.get("record_kind", "unknown"),
                "qualifies_as_preregistration": qualifies and bool(spec.get("qualifies_as_preregistration")),
                "missing_fields": ";".join(missing),
                "blocking_reasons": ";".join(blockers),
            }
        )
    e3_rows = []
    for impl in impls:
        qualifies, missing, blockers = evaluate_implementation_qualification(impl)
        e3_rows.append(
            {
                "implementation_id": impl["implementation_id"],
                "variant_id": impl["variant_id"],
                "repository_path": impl.get("repository_path", "unknown"),
                "linked_tests": ";".join(impl.get("linked_tests", [])),
                "implementation_review_artifacts": ";".join(impl.get("implementation_review_artifacts", [])),
                "qualifies_as_reproducible_implementation": qualifies and bool(impl.get("qualifies_as_reproducible_implementation")),
                "missing_fields": ";".join(missing),
                "blocking_reasons": ";".join(blockers),
            }
        )
    e4_reclassified_rows = [
        {
            "experiment_id": exp["experiment_id"],
            "variant_id": exp["variant_id"],
            "experiment_record_kind": exp.get("experiment_record_kind", "unknown"),
            "underlying_run_key": exp.get("underlying_run_key", "unknown"),
            "qualifies_as_local_backtest": exp.get("qualifies_as_local_backtest", False),
            "blocking_reasons": ";".join(exp.get("qualification_blocking_reasons", [])),
            "missing_fields": ";".join(exp.get("qualification_missing_fields", [])),
        }
        for exp in exps
        if exp.get("experiment_record_kind") in {"audit_reference", "reconciliation_reference"}
        or exp.get("qualification_blocking_reasons")
        or exp.get("qualification_missing_fields")
    ]
    chain_rows = [
        {
            "decision_id": decision["decision_id"],
            "variant_id": decision["variant_id"],
            "evidence_level": decision["evidence_level"],
            "verified_evidence_level": decision.get("verified_evidence_level", decision["evidence_level"]),
            "evidence_chain": ">".join(decision.get("evidence_chain", [])),
            "complete_linked_evidence_chain": ">".join(decision.get("complete_linked_evidence_chain", [])),
            "missing_evidence_stages": ";".join(decision.get("missing_evidence_stages", [])),
            "project_status": decision.get("project_status", "unknown"),
        }
        for decision in decisions
        if level_rank(decision.get("evidence_level", "E0")) >= level_rank("E4")
    ]
    active_incomplete_rows = [
        {
            "decision_id": decision["decision_id"],
            "variant_id": decision["variant_id"],
            "project_status": decision.get("project_status", "unknown"),
            "canonical_lifecycle_status": decision.get("canonical_lifecycle_status", "unknown"),
            "verified_evidence_level": decision.get("verified_evidence_level", decision.get("evidence_level", "unknown")),
            "missing_evidence_stages": ";".join(decision.get("missing_evidence_stages", [])),
            "frozen_hash_present": decision.get("frozen_paper_demo_configuration_hash") != "unknown",
        }
        for decision in decisions
        if decision.get("legacy_active_observation_with_incomplete_evidence_chain")
    ]
    impl_candidates = [impl for impl in impls if impl.get("repository_path") != "unknown"]
    summary = {
        "cumulative_evidence_correction": True,
        "previous_evidence_funnel": VERIFIED_PRE_CUMULATIVE_CHAIN_BASELINE["evidence_funnel"],
        "corrected_evidence_funnel": semantic_snapshot(decisions, specs).get("evidence_funnel", {}),
        "e2_candidates_reviewed": len(e2_rows),
        "e2_records_with_fully_resolved_mandatory_fields": sum(1 for row in e2_rows if row["qualifies_as_preregistration"]),
        "e2_downgraded_unresolved_or_blocked": VERIFIED_PRE_CUMULATIVE_CHAIN_BASELINE["qualifying_preregistration_count"]
        - sum(1 for row in e2_rows if row["qualifies_as_preregistration"]),
        "e3_implementation_candidates_reviewed": len(impl_candidates),
        "e3_with_linked_passing_tests": sum(1 for impl in impls if impl.get("linked_tests") or impl.get("unit_test_status") == "passed"),
        "e3_with_explicit_implementation_review": sum(
            1
            for impl in impls
            if impl.get("implementation_review_artifacts") or impl.get("implementation_review_status") == "completed"
        ),
        "e3_downgraded_from_reproducible_implementation": VERIFIED_PRE_CUMULATIVE_CHAIN_BASELINE[
            "qualifying_implementation_count"
        ]
        - sum(1 for impl in impls if qualifies_implementation(impl)),
        "e4_reconciliation_or_audit_records_reclassified": len(e4_reclassified_rows),
        "e4_e5_e6_e7_chain_record_count": len(chain_rows),
        "active_lifecycle_incomplete_evidence_chain_count": len(active_incomplete_rows),
        "canonical_lifecycle_status_changed": False,
        "paper_demo_state_changed": False,
        "unresolved_cases_left_unknown": True,
    }
    return {
        "summary": summary,
        "e2_rows": e2_rows,
        "e3_rows": e3_rows,
        "e4_reclassified_rows": e4_reclassified_rows,
        "chain_rows": chain_rows,
        "active_incomplete_rows": active_incomplete_rows,
    }


def removed_failure_code_rows(previous_decisions: list[dict[str, Any]], current_decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {row["decision_id"]: row for row in current_decisions}
    rows: list[dict[str, Any]] = []
    for old in previous_decisions:
        new = current.get(old["decision_id"], {})
        removed = sorted(set(old.get("rejection_reason_code", [])) - set(new.get("rejection_reason_code", [])))
        for code in removed:
            rows.append(
                {
                    "decision_id": old["decision_id"],
                    "variant_id": old["variant_id"],
                    "removed_failure_code": code,
                    "removal_reason": "no explicit supported source field/value provenance under semantic patch",
                }
            )
    return rows


def legacy_projected_decisions(root: Path, current_decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project current records through the retired broad mapping rules.

    The semantic patch report uses this for record-level before/after deltas.
    The aggregate before snapshot remains the verified pre-patch baseline.
    """
    registry = read_yaml(root / REGISTRY_PATH)
    registry_rows = registry.get("strategies", []) if isinstance(registry, dict) else []
    registry_by_id = {str(row.get("id", "")): row for row in registry_rows if row.get("id")}
    active_records = build_active_observation_records(root)

    projected: list[dict[str, Any]] = []
    for decision in current_decisions:
        old = dict(decision)
        row = registry_by_id.get(decision.get("variant_id", ""), {})
        source_text_values = [
            decision.get("source_status_detail"),
            decision.get("source_project_status"),
            decision.get("rejection_notes"),
        ]
        source_path = str((decision.get("original_source_paths") or [""])[0])

        if row:
            status_text = row.get("current_status") or row.get("status") or decision.get("source_status_detail")
            if decision["variant_id"] in active_records:
                level = "E7"
            elif row.get("paper_forward_active") and row.get("rules_frozen"):
                level = "E6"
            elif row.get("rules_frozen"):
                level = "E2"
            else:
                level = "E1"
            old["project_status"] = legacy_lifecycle_from_status(status_text, bool(row.get("paper_forward_active")))
            old["rejection_reason_code"] = legacy_failure_codes_from_text(
                row.get("status"),
                row.get("current_status"),
                row.get("primary_failure_mode"),
                row.get("promotion_reason"),
                row.get("blocked_reason"),
                row.get("latest_known_result_summary"),
            )
        else:
            source_lower = source_path.lower()
            status_text = decision.get("source_status_detail") or decision.get("source_project_status")
            if "robustness" in source_lower or decision["decision_id"].endswith("_robustness"):
                level = "E5"
            elif any(token in source_lower for token in ["run", "batch", "rerun", "results"]):
                level = "E4"
            elif any(token in source_lower for token in ["design", "preregistration"]):
                level = "E2"
            else:
                level = "E1"
            old["project_status"] = legacy_lifecycle_from_status(status_text)
            old["rejection_reason_code"] = legacy_failure_codes_from_text(*source_text_values)

        old["evidence_level"] = level
        old["evidence_chain"] = evidence_chain(level)
        projected.append(old)
    return projected


def linked_variants_for_source(source_id: str, ideas: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(idea["variant_id"] for idea in ideas.values() if idea.get("source_id") == source_id)


def source_has_local_implementation(source_id: str, ideas: dict[str, dict[str, Any]], implementations: dict[str, dict[str, Any]]) -> bool:
    impl_variants = {impl["variant_id"] for impl in implementations.values()}
    return any(variant_id in impl_variants for variant_id in linked_variants_for_source(source_id, ideas))


def external_source_key(source: dict[str, Any]) -> str:
    for field in ("source_url", "citation", "source_name"):
        value = known_text(source.get(field))
        if value and not is_local_reference(value):
            return slug(value)
    return "unknown"


def source_link_integrity_rows(
    sources: dict[str, dict[str, Any]],
    ideas: dict[str, dict[str, Any]],
    implementations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_ids = set(sources)
    variant_ids = {idea["variant_id"] for idea in ideas.values()}
    rows: list[dict[str, Any]] = []
    for idea in ideas.values():
        source_exists = idea.get("source_id") in source_ids
        rows.append(
            {
                "link_type": "idea_to_source",
                "source_id": idea.get("source_id", "unknown"),
                "idea_id": idea.get("idea_id", "unknown"),
                "variant_id": idea.get("variant_id", "unknown"),
                "source_exists": source_exists,
                "variant_exists": True,
                "link_status": "ok" if source_exists else "broken_missing_source",
            }
        )
    for impl in implementations.values():
        variant_exists = impl.get("variant_id") in variant_ids
        rows.append(
            {
                "link_type": "implementation_to_variant",
                "source_id": "not_applicable",
                "idea_id": "not_applicable",
                "variant_id": impl.get("variant_id", "unknown"),
                "implementation_id": impl.get("implementation_id", "unknown"),
                "source_exists": "not_applicable",
                "variant_exists": variant_exists,
                "link_status": "ok" if variant_exists else "broken_missing_variant",
            }
        )
    return rows


def duplicate_external_source_rows(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources.values():
        if source.get("source_origin") != "external":
            continue
        key = external_source_key(source)
        if key != "unknown":
            groups[key].append(source)
    rows: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        if len(group) <= 1:
            continue
        rows.append(
            {
                "duplicate_key": key,
                "source_count": len(group),
                "source_ids": [source["source_id"] for source in group],
                "source_names": [source.get("source_name", "unknown") for source in group],
                "review_note": "same_external_reference_requires_human_review_before_duplicate_strategy_intake",
            }
        )
    return rows


def source_classification_consistency(library: dict[str, Any]) -> dict[str, Any]:
    sources = {row["source_id"]: row for row in library["sources"]}
    ideas = {row["idea_id"]: row for row in library["ideas"]}
    implementations = {row["implementation_id"]: row for row in library["implementations"]}
    reports = library.get("reports", {})
    backlog = reports.get("external_public_source_backlog", [])
    link_rows = reports.get("source_link_integrity", source_link_integrity_rows(sources, ideas, implementations))
    duplicate_rows = reports.get("duplicate_external_sources", duplicate_external_source_rows(sources))
    internal_or_generated_in_backlog = [
        row
        for row in backlog
        if row.get("source_origin") in {"internal", "generated"}
        or row.get("internal_evidence_only") is True
        or str(row.get("source_id", "")).startswith("project_evidence_")
    ]
    backlog_missing_reference = [
        row for row in backlog if str(row.get("source_url_or_citation_available", "")).lower() != "true"
    ]
    broken_links = [row for row in link_rows if row.get("link_status") != "ok"]
    missing_raw_type = [row for row in sources.values() if not known_text(row.get("raw_source_type"))]
    invalid_origins = [row for row in sources.values() if row.get("source_origin") not in SOURCE_ORIGINS]
    invalid_classes = [row for row in sources.values() if row.get("source_class") not in SOURCE_CLASSES]
    return {
        "source_classification_consistency_passed": not (
            internal_or_generated_in_backlog
            or backlog_missing_reference
            or broken_links
            or missing_raw_type
            or invalid_origins
            or invalid_classes
        ),
        "external_backlog_count": len(backlog),
        "internal_or_generated_in_external_backlog_count": len(internal_or_generated_in_backlog),
        "external_backlog_missing_reference_count": len(backlog_missing_reference),
        "broken_source_link_count": len(broken_links),
        "duplicate_external_source_group_count": len(duplicate_rows),
        "source_records_missing_raw_type_count": len(missing_raw_type),
        "invalid_source_origin_count": len(invalid_origins),
        "invalid_source_class_count": len(invalid_classes),
        "project_evidence_sources_in_external_backlog": [
            row.get("source_id") for row in internal_or_generated_in_backlog if str(row.get("source_id", "")).startswith("project_evidence_")
        ],
        "generated_sources_in_external_backlog": [
            row.get("source_id") for row in internal_or_generated_in_backlog if row.get("source_origin") == "generated"
        ],
        "checked_at_utc": utc_now(),
    }


def build_reports(
    root: Path,
    sources: dict[str, dict[str, Any]],
    ideas: dict[str, dict[str, Any]],
    specs: dict[str, dict[str, Any]],
    implementations: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    removed: list[dict[str, Any]],
    tree_before: dict[str, Any],
    tree_after: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    decisions_by_variant = {d["variant_id"]: d for d in decisions.values()}
    experiments_by_variant = defaultdict(list)
    for exp in experiments.values():
        experiments_by_variant[exp["variant_id"]].append(exp)
    strategy_inventory: list[dict[str, Any]] = []
    for idea in ideas.values():
        decision = decisions_by_variant.get(idea["variant_id"], {})
        strategy_inventory.append(
            {
                "variant_id": idea["variant_id"],
                "current_status": decision.get("project_status", "unknown"),
                "status_detail": decision.get("project_status_detail", "unknown"),
                "evidence_level": decision.get("evidence_level", "E0"),
                "family": idea["family"],
                "instruments_or_universe": idea["instrument_universe"],
                "timeframe": idea["timeframe"],
                "source_type": sources.get(idea["source_id"], {}).get("source_type", "unknown"),
                "identifiable_backtest_runs": len(experiments_by_variant.get(idea["variant_id"], [])),
                "rejection_failure_codes": decision.get("rejection_reason_code", []),
                "missing_metadata_count": 0,
                "similar_project_strategies": idea.get("similar_project_strategies", []),
                "strategy_fingerprint": idea["strategy_fingerprint"],
            }
        )
    family_coverage_counter = Counter(idea["canonical_family_id"] for idea in ideas.values())
    family_coverage = [
        {"canonical_family_id": family, "strategy_or_lane_count": count}
        for family, count in sorted(family_coverage_counter.items())
    ]
    family_mapping = [
        {
            "variant_id": idea["variant_id"],
            "canonical_family_id": idea["canonical_family_id"],
            "family": idea["family"],
            "source_id": idea["source_id"],
            "original_source_paths": idea.get("original_source_paths", []),
        }
        for idea in ideas.values()
    ]
    fingerprint_groups = defaultdict(list)
    for idea in ideas.values():
        fingerprint_groups[idea["strategy_fingerprint"]].append(idea)
    duplicate_rows: list[dict[str, Any]] = []
    for fingerprint, group in fingerprint_groups.items():
        if fingerprint != "unknown" and len(group) > 1:
            duplicate_rows.append(
                {
                    "strategy_fingerprint": fingerprint,
                    "variant_count": len(group),
                    "variants": [idea["variant_id"] for idea in group],
                    "families": sorted({idea["canonical_family_id"] for idea in group}),
                    "review_note": "deterministic_fingerprint_match_requires_human_review_before_retest",
                }
            )
    unknown_provenance = [
        {
            "variant_id": idea["variant_id"],
            "family": idea["family"],
            "source_id": idea["source_id"],
            "source_type": sources.get(idea["source_id"], {}).get("source_type", "unknown"),
            "reason": "internal_prompt_or_unknown_external_source",
        }
        for idea in ideas.values()
        if sources.get(idea["source_id"], {}).get("source_type") in {"internal_prompt", "unknown", None}
    ]
    failure_by_family_counter: Counter[tuple[str, str]] = Counter()
    negative_results: list[dict[str, Any]] = []
    for decision in decisions.values():
        idea = ideas.get(decision["idea_id"], {})
        codes = decision.get("rejection_reason_code") or []
        for code in codes:
            failure_by_family_counter[(idea.get("canonical_family_id", "unknown"), code)] += 1
        if decision.get("project_status") in {"rejected", "retest_only_on_new_evidence", "blocked"}:
            negative_results.append(
                {
                    "variant_id": decision["variant_id"],
                    "family": idea.get("family", "unknown"),
                    "project_status": decision["project_status"],
                    "failure_codes": codes,
                    "rejection_notes": decision.get("rejection_notes", "unknown"),
                    "retest_conditions": decision.get("retest_conditions", "unknown"),
                }
            )
    failure_by_family = [
        {"canonical_family_id": family, "failure_code": code, "count": count}
        for (family, code), count in sorted(failure_by_family_counter.items())
    ]
    failure_code_provenance = [
        {
            "decision_id": decision["decision_id"],
            "variant_id": decision["variant_id"],
            "failure_code": item.get("failure_code", "unknown"),
            "source_path": item.get("source_path", "unknown"),
            "source_field": item.get("source_field", "unknown"),
            "supporting_value": item.get("supporting_value", "unknown"),
            "origin_type": item.get("origin_type", "unknown"),
            "mapping_rule_id": item.get("mapping_rule_id", "unknown"),
        }
        for decision in decisions.values()
        for item in decision.get("failure_code_provenance", [])
    ]
    funnel_counter = Counter(decision["evidence_level"] for decision in decisions.values())
    evidence_funnel = [{"evidence_level": level, "count": funnel_counter.get(level, 0)} for level in EVIDENCE_LEVELS]
    holdout_unknown = [
        {
            "experiment_id": exp["experiment_id"],
            "variant_id": exp["variant_id"],
            "holdout_period": exp.get("holdout_period", "unknown"),
            "holdout_first_seen_timestamp": exp.get("holdout_first_seen_timestamp", "unknown"),
            "reason": "holdout_exposure_unknown" if exp.get("holdout_first_seen_timestamp") == "unknown" else "",
        }
        for exp in experiments.values()
        if exp.get("holdout_period") == "unknown" or exp.get("holdout_first_seen_timestamp") == "unknown"
    ]
    missing_metadata: list[dict[str, Any]] = []
    required_idea = ["source_id", "canonical_family_id", "timeframe", "canonical_baseline_id", "hypothesis"]
    for idea in ideas.values():
        missing = [field for field in required_idea if idea.get(field) in (None, "", "unknown", [])]
        if missing:
            missing_metadata.append(
                {
                    "record_type": "idea",
                    "record_id": idea["idea_id"],
                    "variant_id": idea["variant_id"],
                    "missing_fields": missing,
                }
            )
    families_no_baseline = [
        {"canonical_family_id": family, "variant_count": count}
        for family, count in sorted(
            Counter(idea["canonical_family_id"] for idea in ideas.values() if idea.get("canonical_baseline_id") == "unknown").items()
        )
    ]
    robust_families = {
        ideas.get(decision["idea_id"], {}).get("canonical_family_id")
        for decision in decisions.values()
        if level_rank(decision["evidence_level"]) >= level_rank("E5")
    }
    many_tests_no_robust = [
        {
            "canonical_family_id": family,
            "strategy_or_lane_count": count,
            "robust_candidate_present": family in robust_families,
        }
        for family, count in sorted(family_coverage_counter.items())
        if count >= 5 and family not in robust_families
    ]
    external_public_backlog = [
        {
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_origin": source.get("source_origin", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "source_role": source.get("source_role", "unknown"),
            "citation": source.get("citation", "unknown"),
            "source_url": source.get("source_url", "unknown"),
            "source_url_or_citation_available": source.get("source_url_or_citation_available", False),
            "primary_source_available": source.get("primary_source_available", False),
            "eligible_for_external_discovery_backlog": source.get("eligible_for_external_discovery_backlog", False),
            "rules_completeness": source.get("rules_completeness", "unknown"),
            "code_available": source.get("code_available", "unknown"),
            "data_available": source.get("data_available", "unknown"),
            "linked_variants": linked_variants_for_source(source["source_id"], ideas),
            "linked_local_implementation_exists": source_has_local_implementation(source["source_id"], ideas, implementations),
            "classification_rule_id": source.get("classification_rule_id", "unknown"),
            "classification_confidence": source.get("classification_confidence", "unknown"),
        }
        for source in sources.values()
        if source.get("eligible_for_external_discovery_backlog") is True
    ]
    internal_project_evidence_sources = [
        {
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_origin": source.get("source_origin", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "source_role": source.get("source_role", "unknown"),
            "citation": source.get("citation", "unknown"),
            "linked_variants": linked_variants_for_source(source["source_id"], ideas),
            "classification_rule_id": source.get("classification_rule_id", "unknown"),
        }
        for source in sources.values()
        if source.get("source_class") in {"internal_project_evidence", "internal_benchmark_definition"}
    ]
    external_implementation_references = [
        {
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_origin": source.get("source_origin", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "citation": source.get("citation", "unknown"),
            "source_url": source.get("source_url", "unknown"),
            "implementation_reference_only": source.get("implementation_reference_only", False),
            "linked_variants": linked_variants_for_source(source["source_id"], ideas),
            "classification_rule_id": source.get("classification_rule_id", "unknown"),
        }
        for source in sources.values()
        if source.get("implementation_reference_only") is True
    ]
    external_no_impl = [
        {
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "citation": source.get("citation", "unknown"),
            "source_url": source.get("source_url", "unknown"),
            "linked_variants": linked_variants_for_source(source["source_id"], ideas),
            "report_basis": "eligible_external_public_source_without_linked_local_implementation",
        }
        for source in sources.values()
        if source.get("eligible_for_external_discovery_backlog") is True
        and not source_has_local_implementation(source["source_id"], ideas, implementations)
    ]
    legacy_external_rule_inclusion = {
        source["source_id"]
        for source in sources.values()
        if source.get("source_type") not in {"internal_prompt", "unknown"}
    }
    source_classification_changes = [
        {
            "source_id": source["source_id"],
            "source_name": source.get("source_name", "unknown"),
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_type": source.get("source_type", "unknown"),
            "source_origin": source.get("source_origin", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "external_public_source": source.get("external_public_source", False),
            "eligible_for_external_discovery_backlog": source.get("eligible_for_external_discovery_backlog", False),
            "legacy_would_have_counted_as_external": source["source_id"] in legacy_external_rule_inclusion,
            "classification_change": (
                "removed_from_external_backlog"
                if source["source_id"] in legacy_external_rule_inclusion
                and source.get("eligible_for_external_discovery_backlog") is not True
                else "retained_external_backlog"
                if source.get("eligible_for_external_discovery_backlog") is True
                else "classified_non_backlog"
            ),
            "classification_rule_id": source.get("classification_rule_id", "unknown"),
            "classification_confidence": source.get("classification_confidence", "unknown"),
            "classification_unresolved_reason": source.get("classification_unresolved_reason", "unknown"),
        }
        for source in sources.values()
    ]
    summary_counter = Counter(
        (
            source.get("source_origin", "unknown"),
            source.get("source_class", "unknown"),
            bool(source.get("eligible_for_external_discovery_backlog")),
        )
        for source in sources.values()
    )
    source_classification_summary = [
        {
            "source_origin": origin,
            "source_class": source_class,
            "eligible_for_external_discovery_backlog": eligible,
            "source_count": count,
        }
        for (origin, source_class, eligible), count in sorted(summary_counter.items())
    ]
    unresolved_source_classification = [
        {
            "source_id": source["source_id"],
            "source_name": source.get("source_name", "unknown"),
            "raw_source_type": source.get("raw_source_type", "unknown"),
            "source_origin": source.get("source_origin", "unknown"),
            "source_class": source.get("source_class", "unknown"),
            "classification_unresolved_reason": source.get("classification_unresolved_reason", "unknown"),
            "classification_confidence": source.get("classification_confidence", "unknown"),
        }
        for source in sources.values()
        if source.get("classification_unresolved_reason") not in {"none", "", None}
    ]
    source_link_integrity = source_link_integrity_rows(sources, ideas, implementations)
    duplicate_external_sources = duplicate_external_source_rows(sources)
    overlap_rows = [
        {
            "concept": "strategy_identity",
            "canonical": str(REGISTRY_PATH).replace("\\", "/"),
            "overlapping_structures": [
                "strategy_lab/research_os/family_status/*.yaml",
                "strategy_lab/research_os/family_lineage/family_ledger.yaml",
                "evidence/**/latest/*manifest*.json",
            ],
            "classification": "canonical_with_generated_and_historical_overlays",
        },
        {
            "concept": "source_provenance",
            "canonical": "strategy_lab/research_os/public_strategy_sources/intake_candidates/*.yaml for external sources; strategy registry internal_prompt source for internal rows",
            "overlapping_structures": ["public source bridge evidence", "batch intake evidence"],
            "classification": "canonical_plus_frozen_evidence",
        },
        {
            "concept": "active_observation",
            "canonical": str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/"),
            "overlapping_structures": ["paper_forward_observations/*/active_observation.yaml"],
            "classification": "canonical_index_with_detail_records",
        },
        {
            "concept": "experiment_run_record",
            "canonical": "evidence/**/latest/*manifest*.json plus row-level CSV artifacts",
            "overlapping_structures": ["run scripts", "dashboard summaries"],
            "classification": "historical_evidence",
        },
    ]
    cleanup_unknown = [
        {
            "path": "strategy_lab/research_os/family_status/*.yaml",
            "classification": "unknown_cleanup_candidate",
            "reason": "overlaps with strategy registry and family ledger, but current tests and similarity maps still reference individual family-status files",
            "safe_removal_blocker": "verified consumers still exist",
        },
        {
            "path": "root run_*.py scripts",
            "classification": "unknown_cleanup_candidate",
            "reason": "large number of workflow-specific entry points; many are historical, but tests and evidence reproduction still reference them",
            "safe_removal_blocker": "requires per-runner consumer audit before deletion",
        },
        {
            "path": "evidence/**/latest/",
            "classification": "historical_evidence",
            "reason": "ignored generated output, but used as frozen audit checkpoints and current state references",
            "safe_removal_blocker": "unique project decisions and manifests live there",
        },
    ]
    strategy_inventory_by_id = {row["variant_id"]: row for row in strategy_inventory}
    for row in strategy_inventory:
        missing = [item for item in missing_metadata if item.get("variant_id") == row["variant_id"]]
        row["missing_metadata_count"] = len(missing)
    return {
        "strategy_inventory": sorted(strategy_inventory_by_id.values(), key=lambda r: r["variant_id"]),
        "family_coverage": family_coverage,
        "family_mapping": sorted(family_mapping, key=lambda r: r["variant_id"]),
        "duplicate_near_duplicate_variants": duplicate_rows,
        "unknown_provenance": unknown_provenance,
        "failure_rejection_reasons_by_family": failure_by_family,
        "failure_code_provenance": failure_code_provenance,
        "negative_results_retest_conditions": negative_results,
        "evidence_level_funnel": evidence_funnel,
        "holdout_reuse_unknown": holdout_unknown,
        "missing_metadata": missing_metadata,
        "families_no_canonical_baseline": families_no_baseline,
        "many_tests_no_robust_candidate": many_tests_no_robust,
        "external_public_source_backlog": external_public_backlog,
        "internal_project_evidence_sources": internal_project_evidence_sources,
        "external_implementation_references": external_implementation_references,
        "source_classification_changes": source_classification_changes,
        "source_classification_summary": source_classification_summary,
        "unresolved_source_classification": unresolved_source_classification,
        "source_link_integrity": source_link_integrity,
        "duplicate_external_sources": duplicate_external_sources,
        "external_sources_no_implementation": external_no_impl,
        "overlapping_state_structures": overlap_rows,
        "removed_files_and_directories": removed,
        "remaining_cleanup_candidates": cleanup_unknown,
        "repository_tree_before": tree_before.get("top_level", []),
        "repository_tree_after": tree_after.get("top_level", []),
    }


def build_strategy_evidence_library(root: Path, cleanup_generated: bool = False) -> dict[str, Any]:
    tree_before = list_tree(root)
    sources: dict[str, dict[str, Any]] = {}
    ideas: dict[str, dict[str, Any]] = {}
    specs: dict[str, dict[str, Any]] = {}
    implementations: dict[str, dict[str, Any]] = {}
    experiments: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    code_commit = git_head(root)
    dep_hash = dependency_lock_hash(root)
    data_hash = data_cache_metadata_hash(root)
    active_records = build_active_observation_records(root)

    registry = read_yaml(root / REGISTRY_PATH)
    for row in registry.get("strategies", []) if isinstance(registry, dict) else []:
        source, idea, decision = registry_row_to_records(row, root, active_records)
        add_or_merge_source(sources, source)
        ideas[idea["idea_id"]] = idea
        decisions[decision["decision_id"]] = decision

    variants_seen = {idea["variant_id"] for idea in ideas.values()}
    for active_variant_id, active_record in sorted(active_records.items()):
        if active_variant_id in variants_seen:
            continue
        source_id = "internal_prompt_active_observation"
        source = source_template(source_id)
        source.update(
            {
                "source_name": "Internal active paper/demo observation record",
                "source_type": "internal_prompt",
                "citation": str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/"),
                "source_claim_summary": "Active observation exists in operations state or paper_forward_observations.",
                "original_source_paths": [str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/")],
            }
        )
        add_or_merge_source(sources, source)
        fp_values = {
            "family": "unknown",
            "signal_direction": "unknown",
            "universe_type": "unknown",
            "formation_horizon": "unknown",
            "holding_horizon": "paper_demo_observation",
            "rebalance_frequency": "unknown",
            "weighting_method": "unknown",
            "risk_overlay": "frozen_observation",
            "execution_cadence": "paper_demo_observation",
        }
        idea = idea_template(active_variant_id)
        idea.update(
            {
                "source_id": source_id,
                "canonical_family_id": "unknown",
                "title": active_variant_id,
                "family": "unknown",
                "timeframe": "paper_demo_observation",
                "strategy_fingerprint": strategy_fingerprint(fp_values),
                "strategy_fingerprint_components": fingerprint_payload(fp_values),
                "original_source_paths": [str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/")],
                "field_origins": {
                    "variant_id": "explicit_active_observation",
                    "source_id": "derived_internal_prompt",
                    "fingerprint": "derived",
                },
            }
        )
        ideas[idea["idea_id"]] = idea
        decision = decision_template(f"decision_{slug(active_variant_id)}_active_observation", idea["idea_id"], active_variant_id)
        decision.update(
            {
                "evidence_level": "E1",
                "evidence_chain": evidence_chain("E1"),
                "verified_evidence_level": "E1",
                "evidence_level_provenance": [
                    provenance(
                        active_record["detail_path"],
                        "status",
                        active_record["detail_status"],
                        "active_lifecycle_not_sufficient_for_e7_v1",
                        "explicit",
                    )
                ],
                "project_status": "active",
                "canonical_lifecycle_status": "active",
                "project_status_detail": "active_paper_demo_observation",
                "source_project_status": "active_paper_demo_observation",
                "source_status_detail": "active_paper_demo_observation",
                "lifecycle_status_provenance": [
                    provenance(
                        active_record["detail_path"],
                        "status",
                        active_record["detail_status"],
                        "lifecycle_canonical_active_observation_v1",
                        "explicit",
                    )
                ],
                "record_role": "paper_demo_observation",
                "record_role_provenance": [
                    provenance(
                        active_record["detail_path"],
                        "status",
                        active_record["detail_status"],
                        "record_role_canonical_active_observation_v1",
                        "explicit",
                    )
                ],
                "frozen_paper_demo_configuration_hash": active_record["frozen_hash"],
                "active_observation_linkage": active_record,
                "legacy_active_observation_with_incomplete_evidence_chain": True,
                "missing_evidence_stages": ["E2", "E3", "E4", "E5", "E6"],
                "next_research_action": "observe_only",
                "original_source_paths": [str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/")],
            }
        )
        decisions[decision["decision_id"]] = decision

    for path in sorted((root / PUBLIC_SOURCE_DIR).glob("*.yaml")):
        source, idea, spec = source_from_public_candidate(path, root)
        add_or_merge_source(sources, source)
        ideas.setdefault(idea["idea_id"], idea)
        specs[spec["specification_id"]] = spec
        decision_id = f"decision_{slug(idea['variant_id'])}_public_source_intake"
        if decision_id not in decisions:
            payload = read_yaml(path)
            status_detail = payload.get("project_notes", {}).get("expected_bridge_decision", "unknown")
            source_path = str(path.relative_to(root)).replace("\\", "/")
            project_status, lifecycle_prov = normalize_lifecycle_status(
                status_detail,
                source_path,
                "project_notes.expected_bridge_decision",
            )
            decision = decision_template(decision_id, idea["idea_id"], idea["variant_id"])
            decision.update(
                {
                    "record_role": "research_candidate",
                    "evidence_level": "E1",
                    "evidence_chain": evidence_chain("E1"),
                    "verified_evidence_level": "E1",
                    "evidence_level_provenance": [
                        provenance(source_path, "intake_candidate", "manual_source_supplied", "evidence_e1_public_source_intake_v1", "explicit")
                    ],
                    "project_status": project_status,
                    "canonical_lifecycle_status": project_status,
                    "project_status_detail": status_detail,
                    "source_project_status": status_detail,
                    "source_status_detail": status_detail,
                    "lifecycle_status_provenance": [lifecycle_prov],
                    "record_role_provenance": [
                        provenance(source_path, "intake_candidate", "public_source_intake", "record_role_public_source_research_candidate_v1", "derived")
                    ],
                    "next_research_action": payload.get("project_notes", {}).get("allowed_next_action", "unknown"),
                    "original_source_paths": [source_path],
                }
            )
            decisions[decision_id] = decision

    for manifest_path in sorted(root.glob("evidence/**/latest/*manifest*.json")):
        if "strategy_evidence_library" in manifest_path.parts:
            continue
        manifest_to_records(
            manifest_path,
            root,
            sources,
            ideas,
            specs,
            implementations,
            experiments,
            decisions,
            code_commit,
            dep_hash,
            data_hash,
        )

    ensure_cumulative_records(root, ideas, specs, implementations, experiments, decisions, code_commit, dep_hash, data_hash)
    apply_source_classifications(sources)

    removed = cleanup_generated_python_caches(root) if cleanup_generated else []
    tree_after = list_tree(root)
    reports = build_reports(root, sources, ideas, specs, implementations, experiments, decisions, removed, tree_before, tree_after)
    corrected_snapshot = semantic_snapshot(list(decisions.values()), list(specs.values()))
    manifest = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "strategy_evidence_library_generated": True,
        "strategy_selection_performed": False,
        "strategy_statuses_changed": False,
        "paper_demo_decisions_changed": False,
        "approval_thresholds_changed": False,
        "backtest_logic_changed": False,
        "runtime_network_calls": False,
        "source_records": len(sources),
        "idea_records": len(ideas),
        "preregistration_records": len(specs),
        "implementation_records": len(implementations),
        "experiment_records": len(experiments),
        "decision_records": len(decisions),
        "registry_entries_seen": len(registry.get("strategies", [])) if isinstance(registry, dict) else 0,
        "public_source_candidates_seen": len(list((root / PUBLIC_SOURCE_DIR).glob("*.yaml"))),
        "evidence_manifests_seen": len(list(root.glob("evidence/**/latest/*manifest*.json"))),
        "generated_cache_directories_removed": len(removed),
        "migration_placeholder_spec_count": corrected_snapshot["migration_placeholder_spec_count"],
        "placeholder_linked_e2_or_higher_decision_count": corrected_snapshot[
            "placeholder_linked_e2_or_higher_decision_count"
        ],
        "qualifying_preregistration_count": corrected_snapshot["qualifying_preregistration_count"],
        "failure_code_assignment_count": corrected_snapshot["failure_code_assignment_count"],
        "failure_code_provenance_count": corrected_snapshot["failure_code_provenance_count"],
        "canonical_strategy_identity_source": str(REGISTRY_PATH).replace("\\", "/"),
        "canonical_active_observation_source": str(ACTIVE_OBSERVATIONS_PATH).replace("\\", "/"),
        "output_path": str(OUTPUT_DIR).replace("\\", "/"),
    }
    return {
        "manifest": manifest,
        "sources": sorted(sources.values(), key=lambda row: row["source_id"]),
        "ideas": sorted(ideas.values(), key=lambda row: row["idea_id"]),
        "specifications": sorted(specs.values(), key=lambda row: row["specification_id"]),
        "implementations": sorted(implementations.values(), key=lambda row: row["implementation_id"]),
        "experiments": sorted(experiments.values(), key=lambda row: row["experiment_id"]),
        "decisions": sorted(decisions.values(), key=lambda row: row["decision_id"]),
        "reports": reports,
    }


def write_strategy_evidence_library(root: Path, cleanup_generated: bool = False) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    previous_snapshot = load_previous_semantic_snapshot(output)
    library = build_strategy_evidence_library(root, cleanup_generated=cleanup_generated)
    corrected_snapshot = semantic_snapshot(library["decisions"], library["specifications"])
    previous_decisions = legacy_projected_decisions(root, library["decisions"])
    evidence_level_changes = semantic_change_rows(previous_decisions, library["decisions"], "evidence_level")
    lifecycle_changes = semantic_change_rows(previous_decisions, library["decisions"], "project_status")
    removed_failure_codes = removed_failure_code_rows(previous_decisions, library["decisions"])
    cumulative_tables = cumulative_evidence_correction_tables(library, previous_snapshot)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "strategy_evidence_library_manifest.json", library["manifest"])
    write_json(output / "sel_sources.json", library["sources"])
    write_json(output / "sel_ideas.json", library["ideas"])
    write_json(output / "sel_preregistrations.json", library["specifications"])
    write_json(output / "sel_implementations.json", library["implementations"])
    write_json(output / "sel_experiments.json", library["experiments"])
    write_json(output / "sel_decisions.json", library["decisions"])
    semantic_report = {
        "semantic_correction_patch": True,
        "previous_snapshot_source": "verified_pre_patch_baseline",
        "record_level_change_baseline": "legacy_pre_patch_mapping_projection",
        "previous_snapshot": previous_snapshot,
        "corrected_snapshot": corrected_snapshot,
        "evidence_level_change_count": len(evidence_level_changes),
        "lifecycle_change_count": len(lifecycle_changes),
        "removed_failure_code_count": len(removed_failure_codes),
        "canonical_source_records_changed": False,
        "strategy_statuses_changed": False,
        "paper_demo_decisions_changed": False,
        "interpretation_note": "Lower corrected counts remove unsupported derived SEL classifications; canonical project state is unchanged.",
    }
    write_json(output / "semantic_correction_report.json", semantic_report)
    write_json(output / "cumulative_evidence_correction_report.json", cumulative_tables["summary"])
    write_csv(output / "semantic_evidence_level_changes.csv", evidence_level_changes)
    write_csv(output / "semantic_lifecycle_changes.csv", lifecycle_changes)
    write_csv(output / "removed_failure_codes.csv", removed_failure_codes)
    write_csv(output / "e2_qualification_review.csv", cumulative_tables["e2_rows"])
    write_csv(output / "e3_implementation_qualification_review.csv", cumulative_tables["e3_rows"])
    write_csv(output / "e4_reclassified_records.csv", cumulative_tables["e4_reclassified_rows"])
    write_csv(output / "e4_e5_e6_e7_chain_records.csv", cumulative_tables["chain_rows"])
    write_csv(output / "active_incomplete_evidence_chains.csv", cumulative_tables["active_incomplete_rows"])
    reports: dict[str, list[dict[str, Any]]] = library["reports"]
    for name, rows in reports.items():
        if name.startswith("repository_tree_"):
            write_csv(output / f"{name}.csv", rows)
        else:
            write_csv(output / f"{name}.csv", rows)
    write_md(
        output / "repository_architecture_findings.md",
        "Repository Architecture Findings",
        [
            (
                "Registry And State Inventory",
                "\n".join(
                    [
                        f"- Strategy registry entries: `{library['manifest']['registry_entries_seen']}`.",
                        f"- Public-source intake candidates: `{library['manifest']['public_source_candidates_seen']}`.",
                        f"- Evidence manifests found: `{library['manifest']['evidence_manifests_seen']}`.",
                        "- Main strategy identity and lifecycle state already live in `strategy_lab/strategy_registry.yaml`.",
                        "- Family-status files, family-lineage ledger, research queue, active observation records, and evidence manifests overlap with the registry but still have verified consumers.",
                    ]
                ),
            ),
            (
                "Canonical Source Decisions",
                markdown_table(
                    reports["overlapping_state_structures"],
                    ["concept", "canonical", "overlapping_structures", "classification"],
                ),
            ),
            (
                "Cleanup Summary",
                "\n".join(
                    [
                        f"- Generated Python cache directories removed: `{library['manifest']['generated_cache_directories_removed']}`.",
                        "- Cache cleanup was disabled for this semantic patch run; no unique strategy evidence, frozen manifests, active-observation files, registries, or strategy results were deleted.",
                        "- Remaining cleanup candidates are reported separately as inventory only.",
                    ]
                ),
            ),
        ],
    )
    write_md(
        output / "strategy_evidence_library_summary.md",
        "Strategy Evidence Library Summary",
        [
            (
                "Data Model",
                "The SEL is a generated overlay from existing canonical inputs. It links sources, ideas, preregistrations, implementations, experiments, and lifecycle decisions without replacing the current backtester or registry.",
            ),
            (
                "Evidence Funnel",
                markdown_table(reports["evidence_level_funnel"], ["evidence_level", "count"]),
            ),
            (
                "Family Coverage",
                markdown_table(reports["family_coverage"][:40], ["canonical_family_id", "strategy_or_lane_count"]),
            ),
            (
                "Duplicate Review",
                markdown_table(
                    reports["duplicate_near_duplicate_variants"][:30],
                    ["strategy_fingerprint", "variant_count", "variants", "families", "review_note"],
                ),
            ),
            (
                "Non-Mutation Guardrails",
                "\n".join(
                    [
                        "- Strategy selection performed: `false`.",
                        "- Strategy statuses changed: `false`.",
                        "- Paper/demo decisions changed: `false`.",
                        "- Approval thresholds, risk limits, backtest logic, execution assumptions, and reported results were not changed.",
                    ]
                ),
            ),
        ],
    )
    write_md(
        output / "semantic_correction_report.md",
        "SEL Semantic Correction Report",
        [
            (
                "Before And After",
                "\n".join(
                    [
                        f"- Previous evidence funnel: `{previous_snapshot.get('evidence_funnel', {})}`.",
                        f"- Corrected evidence funnel: `{corrected_snapshot.get('evidence_funnel', {})}`.",
                        "- Previous snapshot source: `verified_pre_patch_baseline`.",
                        "- Record-level change baseline: `legacy_pre_patch_mapping_projection`.",
                        f"- Previous lifecycle counts: `{previous_snapshot.get('lifecycle_counts', {})}`.",
                        f"- Corrected lifecycle counts: `{corrected_snapshot.get('lifecycle_counts', {})}`.",
                        f"- Migration placeholders: `{corrected_snapshot.get('migration_placeholder_spec_count', 0)}`.",
                        f"- Placeholder-linked decisions at E2 or higher after correction: `{corrected_snapshot.get('placeholder_linked_e2_or_higher_decision_count', 0)}`.",
                        f"- Qualifying preregistrations after correction: `{corrected_snapshot.get('qualifying_preregistration_count', 0)}`.",
                        f"- Failure-code assignments before: `{previous_snapshot.get('failure_code_assignment_count', 0)}`.",
                        f"- Failure-code assignments after: `{corrected_snapshot.get('failure_code_assignment_count', 0)}`.",
                    ]
                ),
            ),
            (
                "Interpretation",
                "Lower corrected counts are not research regressions. They remove unsupported generated SEL classifications while preserving canonical source state, strategy IDs, lifecycle text, and paper/demo observation records.",
            ),
            (
                "Change Files",
                "\n".join(
                    [
                        "- `semantic_evidence_level_changes.csv`",
                        "- `semantic_lifecycle_changes.csv`",
                        "- `removed_failure_codes.csv`",
                        "- `failure_code_provenance.csv`",
                    ]
                ),
            ),
        ],
    )
    cumulative_summary = cumulative_tables["summary"]
    write_md(
        output / "cumulative_evidence_correction_report.md",
        "SEL Cumulative Evidence Correction Report",
        [
            (
                "Evidence Funnel",
                "\n".join(
                    [
                        f"- Previous cumulative-chain funnel: `{cumulative_summary['previous_evidence_funnel']}`.",
                        f"- Corrected cumulative-chain funnel: `{cumulative_summary['corrected_evidence_funnel']}`.",
                        f"- Canonical lifecycle status changed: `{cumulative_summary['canonical_lifecycle_status_changed']}`.",
                        f"- Paper/demo state changed: `{cumulative_summary['paper_demo_state_changed']}`.",
                    ]
                ),
            ),
            (
                "E2 Field Resolution",
                "\n".join(
                    [
                        f"- E2 candidates reviewed: `{cumulative_summary['e2_candidates_reviewed']}`.",
                        f"- E2 records with fully resolved mandatory fields: `{cumulative_summary['e2_records_with_fully_resolved_mandatory_fields']}`.",
                        f"- E2 records downgraded because fields remained unresolved or blocked: `{cumulative_summary['e2_downgraded_unresolved_or_blocked']}`.",
                    ]
                ),
            ),
            (
                "E3 Implementation Evidence",
                "\n".join(
                    [
                        f"- E3 implementation candidates reviewed: `{cumulative_summary['e3_implementation_candidates_reviewed']}`.",
                        f"- Candidates with linked passing tests: `{cumulative_summary['e3_with_linked_passing_tests']}`.",
                        f"- Candidates with explicit implementation review: `{cumulative_summary['e3_with_explicit_implementation_review']}`.",
                        f"- Candidates downgraded from reproducible implementation: `{cumulative_summary['e3_downgraded_from_reproducible_implementation']}`.",
                    ]
                ),
            ),
            (
                "Later Stages And Active Lifecycle",
                "\n".join(
                    [
                        f"- E4 reconciliation/audit/reference records reclassified or blocked: `{cumulative_summary['e4_reconciliation_or_audit_records_reclassified']}`.",
                        f"- E4/E5/E6/E7 records with complete linked chain: `{cumulative_summary['e4_e5_e6_e7_chain_record_count']}`.",
                        f"- Active lifecycle records with incomplete reconstructed chain: `{cumulative_summary['active_lifecycle_incomplete_evidence_chain_count']}`.",
                        "- Unresolved cases were left unknown rather than guessed.",
                    ]
                ),
            ),
            (
                "Review Files",
                "\n".join(
                    [
                        "- `e2_qualification_review.csv`",
                        "- `e3_implementation_qualification_review.csv`",
                        "- `e4_reclassified_records.csv`",
                        "- `e4_e5_e6_e7_chain_records.csv`",
                        "- `active_incomplete_evidence_chains.csv`",
                    ]
                ),
            ),
        ],
    )
    report_titles = {
        "family_coverage": ("Strategy Family Coverage", ["canonical_family_id", "strategy_or_lane_count"]),
        "family_mapping": ("Existing Strategies Mapped To Canonical Families", ["variant_id", "canonical_family_id", "family", "source_id"]),
        "duplicate_near_duplicate_variants": (
            "Duplicate And Near-Duplicate Strategy Variants",
            ["strategy_fingerprint", "variant_count", "variants", "families", "review_note"],
        ),
        "unknown_provenance": ("Strategies With Unknown Or Internal Provenance", ["variant_id", "family", "source_id", "source_type", "reason"]),
        "failure_rejection_reasons_by_family": (
            "Failure And Rejection Reasons By Family",
            ["canonical_family_id", "failure_code", "count"],
        ),
        "failure_code_provenance": (
            "Failure Code Provenance",
            [
                "decision_id",
                "variant_id",
                "failure_code",
                "source_path",
                "source_field",
                "supporting_value",
                "origin_type",
                "mapping_rule_id",
            ],
        ),
        "negative_results_retest_conditions": (
            "Negative Results And Retest Conditions",
            ["variant_id", "family", "project_status", "failure_codes", "retest_conditions"],
        ),
        "evidence_level_funnel": ("Evidence-Level Funnel", ["evidence_level", "count"]),
        "holdout_reuse_unknown": (
            "Holdouts Reused Or Exposure Unknown",
            ["experiment_id", "variant_id", "holdout_period", "holdout_first_seen_timestamp", "reason"],
        ),
        "missing_metadata": ("Missing Metadata", ["record_type", "record_id", "variant_id", "missing_fields"]),
        "families_no_canonical_baseline": ("Families With No Canonical Baseline", ["canonical_family_id", "variant_count"]),
        "many_tests_no_robust_candidate": (
            "Families With Many Tests But No Robust Candidate",
            ["canonical_family_id", "strategy_or_lane_count", "robust_candidate_present"],
        ),
        "external_public_source_backlog": (
            "External Public Source Backlog",
            [
                "source_id",
                "source_name",
                "source_class",
                "citation",
                "source_url",
                "linked_variants",
                "linked_local_implementation_exists",
                "classification_confidence",
            ],
        ),
        "internal_project_evidence_sources": (
            "Internal Project Evidence Sources",
            ["source_id", "source_name", "source_class", "source_role", "citation", "linked_variants"],
        ),
        "external_implementation_references": (
            "External Implementation References",
            ["source_id", "source_name", "source_class", "citation", "source_url", "implementation_reference_only"],
        ),
        "source_classification_changes": (
            "Source Classification Changes",
            [
                "source_id",
                "raw_source_type",
                "source_origin",
                "source_class",
                "legacy_would_have_counted_as_external",
                "eligible_for_external_discovery_backlog",
                "classification_change",
            ],
        ),
        "source_classification_summary": (
            "Source Classification Summary",
            ["source_origin", "source_class", "eligible_for_external_discovery_backlog", "source_count"],
        ),
        "unresolved_source_classification": (
            "Unresolved Source Classification",
            ["source_id", "source_name", "raw_source_type", "source_origin", "source_class", "classification_unresolved_reason"],
        ),
        "source_link_integrity": (
            "Source Link Integrity",
            ["link_type", "source_id", "idea_id", "variant_id", "implementation_id", "link_status"],
        ),
        "duplicate_external_sources": (
            "Duplicate External Sources",
            ["duplicate_key", "source_count", "source_ids", "source_names", "review_note"],
        ),
        "external_sources_no_implementation": (
            "External Public Sources With No Project Implementation",
            ["source_id", "source_name", "source_class", "citation", "source_url", "linked_variants", "report_basis"],
        ),
        "removed_files_and_directories": (
            "Removed Files And Directories",
            [
                "path",
                "previous_purpose",
                "classification",
                "evidence_unused_or_regenerable",
                "information_migrated",
                "migration_destination",
                "validation",
                "residual_risk",
            ],
        ),
        "remaining_cleanup_candidates": (
            "Remaining Unknown Cleanup Candidates",
            ["path", "classification", "reason", "safe_removal_blocker"],
        ),
    }
    for name, (title, columns) in report_titles.items():
        write_md(output / f"{name}.md", title, [("Report", markdown_table(reports[name], columns))])
    write_json(output / "source_classification_consistency_check.json", source_classification_consistency(library))
    consistency = validate_library(library)
    write_json(output / "strategy_evidence_library_consistency_check.json", consistency)
    return library


def validate_library(library: dict[str, Any]) -> dict[str, Any]:
    sources = {row["source_id"] for row in library["sources"]}
    ideas = {row["idea_id"] for row in library["ideas"]}
    variants = {row["variant_id"] for row in library["ideas"]}
    specs_by_idea = defaultdict(list)
    for row in library["specifications"]:
        specs_by_idea[row["idea_id"]].append(row)
    qualified_specs_by_idea = defaultdict(list)
    for row in library["specifications"]:
        if qualifies_preregistration(row):
            qualified_specs_by_idea[row["idea_id"]].append(row)
    impls_by_variant = defaultdict(list)
    for row in library["implementations"]:
        impls_by_variant[row["variant_id"]].append(row)
    exps_by_variant = defaultdict(list)
    for row in library["experiments"]:
        exps_by_variant[row["variant_id"]].append(row)
    errors: list[str] = []
    for row in library["ideas"]:
        if row["source_id"] not in sources:
            errors.append(f"missing source for idea {row['idea_id']}")
    for row in library["specifications"]:
        if row["idea_id"] not in ideas:
            errors.append(f"missing idea for spec {row['specification_id']}")
    for row in library["implementations"]:
        if row["variant_id"] not in variants:
            errors.append(f"missing variant for implementation {row['implementation_id']}")
        qualifies, missing, blockers = evaluate_implementation_qualification(row)
        if row.get("qualifies_as_reproducible_implementation") and not qualifies:
            errors.append(
                f"implementation qualifies without complete E3 support: {row['implementation_id']} missing={missing} blockers={blockers}"
            )
    for row in library["experiments"]:
        if row["variant_id"] not in variants:
            errors.append(f"missing variant for experiment {row['experiment_id']}")
        if not any(impl["implementation_id"] == row["implementation_id"] for impl in library["implementations"]):
            errors.append(f"missing implementation for experiment {row['experiment_id']}")
        if row.get("qualifies_as_local_backtest") and row.get("experiment_record_kind") != "local_backtest_run":
            errors.append(f"non-run experiment qualifies as E4 local backtest: {row['experiment_id']}")
        if row.get("qualifies_as_local_backtest") and row.get("linked_qualifying_implementation_id") == "unknown":
            errors.append(f"E4 experiment without qualifying E3 implementation: {row['experiment_id']}")
    qualified_e4_keys = Counter(
        row.get("underlying_run_key")
        for row in library["experiments"]
        if row.get("qualifies_as_local_backtest") and row.get("underlying_run_key") != "unknown"
    )
    for key, count in qualified_e4_keys.items():
        if count > 1:
            errors.append(f"duplicate qualified E4 underlying run key: {key}")
    for row in library["decisions"]:
        if row["idea_id"] not in ideas:
            errors.append(f"missing idea for decision {row['decision_id']}")
        if row["project_status"] not in LIFECYCLE_STATUSES:
            errors.append(f"invalid lifecycle status {row['project_status']}")
        if row["evidence_level"] not in EVIDENCE_LEVELS:
            errors.append(f"invalid evidence level {row['evidence_level']}")
        if row["verified_evidence_level"] != row["evidence_level"]:
            errors.append(f"verified evidence level mismatch for {row['decision_id']}")
        if row["evidence_chain"] != evidence_chain(row["verified_evidence_level"]):
            errors.append(f"non-cumulative evidence chain for {row['decision_id']}")
        for code in row.get("rejection_reason_code", []):
            if code not in FAILURE_CODES:
                errors.append(f"invalid failure code {code}")
        provenance_codes = {item.get("failure_code") for item in row.get("failure_code_provenance", [])}
        for code in row.get("rejection_reason_code", []):
            if code not in provenance_codes:
                errors.append(f"failure code without provenance for {row['decision_id']}: {code}")
        for item in row.get("failure_code_provenance", []):
            required = {"failure_code", "source_path", "source_field", "supporting_value", "origin_type", "mapping_rule_id"}
            if not required <= set(item):
                errors.append(f"incomplete failure-code provenance for {row['decision_id']}")
        has_active_link = bool(row.get("active_observation_linkage", {}).get("index_detail_agree"))
        if level_rank(row["evidence_level"]) >= level_rank("E2"):
            if not qualified_specs_by_idea[row["idea_id"]]:
                errors.append(f"missing qualifying preregistration for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E3"):
            if not any(qualifies_implementation(impl) for impl in impls_by_variant[row["variant_id"]]):
                errors.append(f"missing qualifying implementation for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E4"):
            if not any(exp.get("qualifies_as_local_backtest") for exp in exps_by_variant[row["variant_id"]]):
                errors.append(f"missing qualifying local backtest for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E5"):
            if not any(exp.get("qualifies_as_robustness") for exp in exps_by_variant[row["variant_id"]]):
                errors.append(f"missing explicit robustness-qualified decision for {row['decision_id']}")
        if row["evidence_level"] == "E6":
            if row["frozen_paper_demo_configuration_hash"] == "unknown" or not any(
                item.get("mapping_rule_id", "").startswith("evidence_e6_") for item in row.get("evidence_level_provenance", [])
            ):
                errors.append(f"missing explicit E6 eligibility/control governance for {row['decision_id']}")
        if row["evidence_level"] == "E7":
            if row["project_status"] != "active" or row["record_role"] != "paper_demo_observation" or not has_active_link:
                errors.append(f"E7 without canonical active-observation linkage for {row['decision_id']}")
            if not any(item.get("mapping_rule_id", "").startswith("evidence_e7_") for item in row.get("evidence_level_provenance", [])):
                errors.append(f"E7 without explicit full-chain evidence provenance for {row['decision_id']}")
        if row["project_status"] in {"eligible", "active"}:
            allowed = {
                "lifecycle_canonical_active_observation_v1",
                "lifecycle_exact_eligible_v1",
            }
            if not any(item.get("mapping_rule_id") in allowed for item in row.get("lifecycle_status_provenance", [])):
                errors.append(f"unsupported {row['project_status']} lifecycle mapping for {row['decision_id']}")
    for source in library["sources"]:
        if source.get("source_origin") not in SOURCE_ORIGINS:
            errors.append(f"invalid source origin for {source['source_id']}: {source.get('source_origin')}")
        if source.get("source_class") not in SOURCE_CLASSES:
            errors.append(f"invalid source class for {source['source_id']}: {source.get('source_class')}")
        if not known_text(source.get("raw_source_type")):
            errors.append(f"missing raw source type for {source['source_id']}")
        if source.get("source_origin") in {"internal", "generated"} and source.get("eligible_for_external_discovery_backlog"):
            errors.append(f"internal/generated source eligible for external backlog: {source['source_id']}")
        if str(source.get("source_id", "")).startswith("project_evidence_") and source.get("external_public_source"):
            errors.append(f"project evidence source classified external: {source['source_id']}")
        if source.get("source_class") == "internal_prompt_idea" and source.get("eligible_for_external_discovery_backlog"):
            errors.append(f"internal prompt source eligible for external backlog: {source['source_id']}")
        if source.get("eligible_for_external_discovery_backlog") and not source.get("source_url_or_citation_available"):
            errors.append(f"external backlog source missing external citation/url: {source['source_id']}")
    for spec in library["specifications"]:
        qualifies, missing, blockers = evaluate_spec_qualification(spec)
        if spec.get("qualifies_as_preregistration") and not qualifies:
            errors.append(
                f"E2 preregistration qualifies with unresolved fields: {spec['specification_id']} missing={missing} blockers={blockers}"
            )
        if spec.get("record_kind") == "migration_placeholder" and spec.get("qualifies_as_preregistration"):
            errors.append(f"migration placeholder qualifies as preregistration: {spec['specification_id']}")
    return {
        "consistency_passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "checked_at_utc": utc_now(),
    }
