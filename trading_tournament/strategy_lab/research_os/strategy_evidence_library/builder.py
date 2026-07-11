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


def qualifies_preregistration(spec: dict[str, Any]) -> bool:
    return bool(spec.get("qualifies_as_preregistration")) and spec.get("record_kind") != "migration_placeholder"


def qualifies_implementation(impl: dict[str, Any]) -> bool:
    return (
        bool(impl.get("qualifies_as_reproducible_implementation"))
        and impl.get("repository_path") != "unknown"
        and impl.get("code_content_hash") != "unknown"
        and impl.get("configuration_hash") != "unknown"
        and impl.get("dependency_lock_hash") != "unknown"
    )


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
        "evidence_level_provenance": [],
        "project_status": "backlog",
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
        evidence_level = "E7"
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
            "evidence_level_provenance": [
                provenance(
                    source_path if not explicit_active else active_record["detail_path"],
                    "canonical_active_observation" if explicit_active else "strategy_registry_row",
                    status,
                    "evidence_e7_canonical_active_observation_v1" if explicit_active else "evidence_e1_registry_provenance_v1",
                    "explicit" if explicit_active else "derived",
                )
            ],
            "project_status": project_status,
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
            "original_source_paths": [str(REGISTRY_PATH).replace("\\", "/")],
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
        source_id = f"internal_prompt_{slug(family if family != 'unknown' else variant_id)}"
        if source_id not in sources:
            source = source_template(source_id)
            source.update(
                {
                    "source_name": f"Internal project evidence: {family if family != 'unknown' else variant_id}",
                    "source_type": "internal_prompt",
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
            spec.update(
                {
                    "entry_rule": "see_artifact",
                    "exit_rule": "see_artifact",
                    "parameters": {"source_manifest": rel_manifest},
                    "success_criteria": "see_artifact",
                    "failure_criteria": "see_artifact",
                    "preregistration_version": str(manifest.get("schema_version", 1)),
                    "preregistration_timestamp": manifest.get("created_utc", manifest.get("timestamp_utc", "unknown")),
                    "original_source_paths": [rel_manifest],
                    "field_origins": {"specification": "derived_from_design_or_intake_manifest"},
                }
            )
            specs[spec_id] = spec
    if evidence_kind in {"run", "robustness", "audit", "reconciliation"}:
        code_paths = related_python_paths(root, [variant_id, source_id, evidence_dir.parent.name])
        impl_id = f"impl_{slug(variant_id)}"
        if impl_id not in implementations:
            impl = implementation_template(impl_id, variant_id)
            rel_paths = [str(path.relative_to(root)).replace("\\", "/") for path in code_paths]
            impl.update(
                {
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
            implementations[impl_id] = impl
        exp_id = f"exp_{slug(evidence_dir.parent.name)}"
        if exp_id not in experiments:
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
            exp.update(
                {
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
        if evidence_kind == "robustness":
            level = "E5"
        elif evidence_kind == "run":
            level = "E4"
        elif evidence_kind == "design":
            level = "E2"
        elif evidence_kind == "source_intake":
            level = "E1"
        else:
            level = "E1"
        decision = decision_template(decision_id, idea_id, variant_id)
        status_detail = (
            manifest.get("final_audit_decision")
            or manifest.get("audit_decision")
            or manifest.get("run_readiness_decision")
            or manifest.get("next_action")
            or evidence_kind
        )
        decision.update(
            {
                "evidence_level": level,
                "evidence_chain": evidence_chain(level),
                "project_status": lifecycle_from_status(status_detail),
                "project_status_detail": status_detail,
                "decision_date": manifest.get("created_utc", manifest.get("timestamp_utc", "unknown")),
                "rejection_reason_code": failure_codes_from_text(status_detail, manifest),
                "rejection_notes": str(status_detail),
                "next_research_action": manifest.get("next_action", "unknown"),
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
        variant_id = decision["variant_id"]
        if level_rank(level) >= level_rank("E2") and not spec_by_idea[idea["idea_id"]]:
            spec_id = f"spec_{slug(variant_id)}_migration_placeholder"
            spec = spec_template(spec_id, idea["idea_id"], variant_id)
            spec.update(
                {
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
    impl_variants = {impl["variant_id"] for impl in implementations.values()}
    external_no_impl = [
        {
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "source_type": source["source_type"],
            "linked_variants": [idea["variant_id"] for idea in ideas.values() if idea["source_id"] == source["source_id"]],
        }
        for source in sources.values()
        if source.get("source_type") not in {"internal_prompt", "unknown"}
        and not any(idea["variant_id"] in impl_variants for idea in ideas.values() if idea["source_id"] == source["source_id"])
    ]
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
        "negative_results_retest_conditions": negative_results,
        "evidence_level_funnel": evidence_funnel,
        "holdout_reuse_unknown": holdout_unknown,
        "missing_metadata": missing_metadata,
        "families_no_canonical_baseline": families_no_baseline,
        "many_tests_no_robust_candidate": many_tests_no_robust,
        "external_sources_no_implementation": external_no_impl,
        "overlapping_state_structures": overlap_rows,
        "removed_files_and_directories": removed,
        "remaining_cleanup_candidates": cleanup_unknown,
        "repository_tree_before": tree_before.get("top_level", []),
        "repository_tree_after": tree_after.get("top_level", []),
    }


def build_strategy_evidence_library(root: Path, cleanup_generated: bool = True) -> dict[str, Any]:
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
                "evidence_level": "E7",
                "evidence_chain": evidence_chain("E7"),
                "evidence_level_provenance": [
                    provenance(
                        active_record["detail_path"],
                        "status",
                        active_record["detail_status"],
                        "evidence_e7_canonical_active_observation_v1",
                        "explicit",
                    )
                ],
                "project_status": "active",
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
                    "evidence_level_provenance": [
                        provenance(source_path, "intake_candidate", "manual_source_supplied", "evidence_e1_public_source_intake_v1", "explicit")
                    ],
                    "project_status": project_status,
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

    removed = cleanup_generated_python_caches(root) if cleanup_generated else []
    tree_after = list_tree(root)
    reports = build_reports(root, sources, ideas, specs, implementations, experiments, decisions, removed, tree_before, tree_after)
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


def write_strategy_evidence_library(root: Path, cleanup_generated: bool = True) -> dict[str, Any]:
    library = build_strategy_evidence_library(root, cleanup_generated=cleanup_generated)
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "strategy_evidence_library_manifest.json", library["manifest"])
    write_json(output / "sel_sources.json", library["sources"])
    write_json(output / "sel_ideas.json", library["ideas"])
    write_json(output / "sel_preregistrations.json", library["specifications"])
    write_json(output / "sel_implementations.json", library["implementations"])
    write_json(output / "sel_experiments.json", library["experiments"])
    write_json(output / "sel_decisions.json", library["decisions"])
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
                        "- No unique strategy evidence, frozen manifests, active-observation files, registries, or strategy results were deleted.",
                        "- Remaining cleanup candidates are reported separately because current tests or source files still reference them.",
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
        "external_sources_no_implementation": (
            "Families With Source Records But No Project Implementation",
            ["source_id", "source_name", "source_type", "linked_variants"],
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
    for row in library["experiments"]:
        if row["variant_id"] not in variants:
            errors.append(f"missing variant for experiment {row['experiment_id']}")
        if not any(impl["implementation_id"] == row["implementation_id"] for impl in library["implementations"]):
            errors.append(f"missing implementation for experiment {row['experiment_id']}")
    for row in library["decisions"]:
        if row["idea_id"] not in ideas:
            errors.append(f"missing idea for decision {row['decision_id']}")
        if row["project_status"] not in LIFECYCLE_STATUSES:
            errors.append(f"invalid lifecycle status {row['project_status']}")
        if row["evidence_level"] not in EVIDENCE_LEVELS:
            errors.append(f"invalid evidence level {row['evidence_level']}")
        if row["evidence_chain"] != evidence_chain(row["evidence_level"]):
            errors.append(f"non-cumulative evidence chain for {row['decision_id']}")
        for code in row.get("rejection_reason_code", []):
            if code not in FAILURE_CODES:
                errors.append(f"invalid failure code {code}")
        if level_rank(row["evidence_level"]) >= level_rank("E2") and not specs_by_idea[row["idea_id"]]:
            errors.append(f"missing preregistration for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E3") and not impls_by_variant[row["variant_id"]]:
            errors.append(f"missing implementation for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E4") and not exps_by_variant[row["variant_id"]]:
            errors.append(f"missing experiment for {row['decision_id']}")
        if level_rank(row["evidence_level"]) >= level_rank("E6") and row["frozen_paper_demo_configuration_hash"] == "unknown":
            errors.append(f"missing frozen paper/demo hash for {row['decision_id']}")
    return {
        "consistency_passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "checked_at_utc": utc_now(),
    }
