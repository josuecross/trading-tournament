from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "reconcile_and_close_kst_after_validation_v1"
OUTPUT_DIR = ROOT / "evidence" / "lifecycle" / TASK_ID / "latest"
STRATEGY_REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
FAMILY_LEDGER = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
RESEARCH_QUEUE = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ROADMAP = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"

VALIDATION_DIR = ROOT / "evidence" / "validation" / "pring_kst_incremental_standalone_validation_v1" / "latest"
EXPLORATION_DIR = ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v5" / "latest"

STRATEGY_ID = "pring_kst_default_centerline_spy_bil_v1"
FAMILY_ID = "multi_cycle_smoothed_roc_momentum"
DISPLAY_NAME = "Pring KST Multi-Cycle Centerline State"
ARCHITECTURE = "weighted_multi_horizon_smoothed_rate_of_change_filter"
SOURCE_LINEAGE = "strategy_source_library_refresh_v2:src_pring_kst_1992_v1"
UNIVERSE = ("SPY", "BIL")
UNIVERSE_TEXT = "SPY|BIL"
EXPLORATION_TRIAL_ID = "fast_source_v5__pring_kst_default_centerline_spy_bil_v1__canonical"
VALIDATION_TRIAL_ID = "pring_kst_incremental_standalone_validation_v1__validation_child"
ADAPTATION_LABEL = "validation_variant"
CHANGED_FIELDS_FROM_PARENT = "validation_diagnostics_and_predeclared_exposure_and_trend_controls_only"
DECISION_REASON = "rolling_control_dominance_and_negative_median_sharpe_differences"
STRATEGY_NEXT_ACTION = "do_not_retest_exact_kst_default_centerline_configuration"
PROJECT_NEXT_ACTION_SUCCESS = "evaluate_deferred_structural_source_records_v2"
PROJECT_NEXT_ACTION_BLOCKED = "direction_owner_review_kst_registry_reconciliation_block_v1"
PROCESS_OUTCOME_SUCCESS = "lifecycle_reconciliation_completed"
PROCESS_OUTCOME_BLOCKED = "lifecycle_reconciliation_blocked"
FAMILY_INTERPRETATION = "exact_configuration_closed_period_instability"
REGISTRATION_REASON = "retrospective_status_reconciliation"
FINGERPRINT_SCHEMA_VERSION = "kst_exact_config_fingerprint_v1"
FROZEN_PARAMETERS = {
    "roc_periods": [10, 15, 20, 30],
    "smoothing_periods": [10, 10, 10, 15],
    "component_weights": [1, 2, 3, 4],
    "centerline": 0,
    "signal_line": "unused",
    "spy_rule": "hold_SPY_when_KST_strictly_positive",
    "bil_rule": "hold_BIL_when_KST_nonpositive_or_before_warmup",
    "signal_timestamp": "completed_daily_close",
    "execution": "completed_close_signal_applied_to_following_session",
    "costs_tested_bps": [0, 5, 10],
}
BENCHMARKS_AND_CONTROLS = (
    "SPY_buy_and_hold",
    "SPY_30_session_ROC_sign_SPY_BIL",
    "SPY_200d_frozen_control",
    "static_6878_SPY_3122_BIL_monthly_rebalanced",
)
SOURCE_OF_TRUTH_PATHS = [STRATEGY_REGISTRY, FAMILY_LEDGER, RESEARCH_QUEUE, ACTIVE_OBSERVATIONS, ROADMAP]
CACHE_FILES = sorted(path for path in (ROOT / "data" / "cache").rglob("*") if path.is_file())
PROTECTED_PATHS = SOURCE_OF_TRUTH_PATHS + CACHE_FILES
INPUT_EVIDENCE_FILES = [
    VALIDATION_DIR / name
    for name in [
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "rolling_window_summary.csv",
        "consistency_check.json",
    ]
] + [
    EXPLORATION_DIR / name
    for name in [
        "strategy_cards.csv",
        "trial_ledger.csv",
    ]
]
FORBIDDEN_FLAGS = {
    "backtest_run": False,
    "kst_rerun": False,
    "tuning": False,
    "validation_or_robustness": False,
    "promotion": False,
    "paper_demo_activation": False,
    "provider_download": False,
    "broker_account_order_or_real_money_action": False,
    "strategy_discovery": False,
    "source_review": False,
    "broad_registry_cleanup": False,
}


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


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
        return "|".join(str(v) for v in value)
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "lifecycle" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(normalize_text(v) for v in value)
    if isinstance(value, dict):
        return "|".join(f"{normalize_text(k)}={normalize_text(v)}" for k, v in sorted(value.items()))
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def normalize_universe(value: Any) -> str:
    if isinstance(value, str):
        pieces = [piece.strip().upper() for piece in value.replace(",", "|").split("|") if piece.strip()]
    elif isinstance(value, (list, tuple, set)):
        pieces = [str(piece).strip().upper() for piece in value if str(piece).strip()]
    else:
        pieces = []
    return "|".join(pieces)


def normalize_parameters(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(value, dict):
        parsed = value
    else:
        parsed = {}
    nested = parsed.get("parameters", {}) if isinstance(parsed.get("parameters"), dict) else {}
    execution = parsed.get("execution", {})
    normalized: dict[str, Any] = {
        "roc_periods": parsed.get("roc_periods", nested.get("roc_periods", [])),
        "smoothing_periods": parsed.get(
            "smoothing_periods",
            parsed.get("smoothing_SMAs", nested.get("smoothing_periods", nested.get("smoothing_SMAs", []))),
        ),
        "component_weights": parsed.get("component_weights", nested.get("component_weights", [])),
        "centerline": parsed.get("centerline", nested.get("centerline")),
        "signal_line": parsed.get("signal_line", parsed.get("rule", {}).get("signal_line", ""))
        if isinstance(parsed.get("rule", {}), dict)
        else parsed.get("signal_line", ""),
        "spy_rule": parsed.get("spy_rule", ""),
        "bil_rule": parsed.get("bil_rule", ""),
        "signal_timestamp": parsed.get("signal_timestamp", ""),
        "execution": parsed.get("execution", ""),
        "costs_tested_bps": parsed.get("costs_tested_bps", []),
    }
    rule = parsed.get("rule", {}) if isinstance(parsed.get("rule"), dict) else {}
    if not normalized["spy_rule"] and rule.get("hold_SPY"):
        normalized["spy_rule"] = "hold_SPY_when_KST_strictly_positive"
    if not normalized["bil_rule"] and rule.get("hold_BIL"):
        normalized["bil_rule"] = "hold_BIL_when_KST_nonpositive_or_before_warmup"
    if isinstance(execution, dict):
        if not normalized["signal_timestamp"] and execution.get("signal"):
            normalized["signal_timestamp"] = "completed_daily_close"
        if execution.get("target_application"):
            normalized["execution"] = "completed_close_signal_applied_to_following_session"
    if normalized["signal_line"] in {"", None} and "signal line" in str(parsed).lower():
        normalized["signal_line"] = "unused"
    for field in ("roc_periods", "smoothing_periods", "component_weights", "costs_tested_bps"):
        normalized[field] = [int(float(item)) for item in normalized[field]] if isinstance(normalized[field], list) else []
    if normalized["centerline"] is not None:
        normalized["centerline"] = int(float(normalized["centerline"]))
    return normalized


def configuration_fingerprint_payload() -> dict[str, Any]:
    return {
        "family_id": FAMILY_ID,
        "instrument_universe": UNIVERSE_TEXT,
        "roc_periods": FROZEN_PARAMETERS["roc_periods"],
        "smoothing_periods": FROZEN_PARAMETERS["smoothing_periods"],
        "component_weights": FROZEN_PARAMETERS["component_weights"],
        "centerline": FROZEN_PARAMETERS["centerline"],
        "signal_line": FROZEN_PARAMETERS["signal_line"],
        "spy_rule": FROZEN_PARAMETERS["spy_rule"],
        "bil_rule": FROZEN_PARAMETERS["bil_rule"],
        "signal_timestamp": FROZEN_PARAMETERS["signal_timestamp"],
        "execution": FROZEN_PARAMETERS["execution"],
    }


def configuration_fingerprint(payload: dict[str, Any] | None = None) -> str:
    source = configuration_fingerprint_payload() if payload is None else payload
    text = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_fingerprint_payload(record: dict[str, Any]) -> dict[str, Any]:
    params = normalize_parameters(record.get("parameters", {}))
    return {
        "family_id": record.get("family_id") or record.get("family") or record.get("strategy_family") or "",
        "instrument_universe": normalize_universe(record.get("instrument_universe") or record.get("universe") or record.get("instruments")),
        **{field: params[field] for field in configuration_fingerprint_payload() if field not in {"family_id", "instrument_universe"}},
    }


def alias_score(record: dict[str, Any]) -> tuple[int, list[str]]:
    payload = record_fingerprint_payload(record)
    target = configuration_fingerprint_payload()
    matched: list[str] = []
    for field in [
        "family_id",
        "instrument_universe",
        "roc_periods",
        "smoothing_periods",
        "component_weights",
        "centerline",
        "signal_line",
        "spy_rule",
        "bil_rule",
        "signal_timestamp",
        "execution",
    ]:
        if payload.get(field) and payload.get(field) == target.get(field):
            matched.append(field)
    return len(matched), matched


def load_registry() -> dict[str, Any]:
    return read_yaml(STRATEGY_REGISTRY)


def target_registry_record_yaml() -> str:
    return yaml.safe_dump([target_registry_record()], sort_keys=False, width=120, allow_unicode=False)


def find_record_span(text: str, strategy_id: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    record_starts = [idx for idx, line in enumerate(lines) if line.startswith("- id: ")]
    for position, start in enumerate(record_starts):
        end = record_starts[position + 1] if position + 1 < len(record_starts) else len(lines)
        block = "".join(lines[start:end])
        if (
            f"- id: {strategy_id}\n" in block
            or f"  id: {strategy_id}\n" in block
            or f"strategy_id: {strategy_id}\n" in block
            or f"  strategy_id: {strategy_id}\n" in block
        ):
            return start, end
    return None


def atomic_write_registry_text(text: str) -> None:
    tmp = STRATEGY_REGISTRY.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, STRATEGY_REGISTRY)


def append_or_replace_target_record() -> None:
    text = STRATEGY_REGISTRY.read_text(encoding="utf-8")
    replacement = target_registry_record_yaml()
    lines = text.splitlines(keepends=True)
    span = find_record_span(text, STRATEGY_ID)
    if span is None:
        new_text = text.rstrip() + "\n" + replacement
    else:
        start, end = span
        lines[start:end] = replacement.splitlines(keepends=True)
        new_text = "".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    atomic_write_registry_text(new_text)


def target_registry_record() -> dict[str, Any]:
    return {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "family": FAMILY_ID,
        "strategy_family": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": UNIVERSE_TEXT,
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": list(BENCHMARKS_AND_CONTROLS),
        "stage": "closed",
        "lane": "archive",
        "instrument_family": "ETF",
        "version": "v1",
        "parent_id": EXPLORATION_TRIAL_ID,
        "credibility_tier": "blocked",
        "status": "rejected",
        "current_status": "closed",
        "outcome": "validation_failed",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": EXPLORATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "failure_reason": "period_instability",
        "primary_failure_reason": "period_instability",
        "decision_reason": DECISION_REASON,
        "next_action": STRATEGY_NEXT_ACTION,
        "allowed_next_action": "no_action",
        "allowed_next_actions": ["no_action"],
        "paper_demo_eligible": False,
        "paper_demo_active": False,
        "paper_forward_active": False,
        "paper_forward_allowed_by_risk_framework": False,
        "benchmark_reference_only": False,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "no_real_money_recommendation": True,
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "registration_reason": REGISTRATION_REASON,
        "closure_scope": "exact_kst_10_15_20_30_roc_10_10_10_15_smoothing_1_2_3_4_weights_zero_centerline_spy_bil_next_session_configuration_only",
        "data_source": "existing_adjusted_etf_cache",
        "implementation_status": "archived",
        "evidence_source": "pring_kst_incremental_standalone_validation_v1",
        "latest_evidence_path": rel(VALIDATION_DIR),
        "latest_known_result_summary": "Validation failed for period instability after rolling controls dominated in 66.3% of 36-month windows and 68.8% of 60-month windows.",
        "role": "closed_exact_configuration",
        "rules_frozen": True,
        "risk_framework_status": "not_paper_demo_eligible",
        "risk_budget_status": "closed_period_instability",
        "promotion_decision": "do_not_promote",
        "promotion_review_required": False,
        "promotion_reason": "Closed exact KST configuration after validation failed for period instability.",
        "promotion_blockers": "validation_failed;period_instability;not_paper_demo_eligible;no_real_money_authorization",
        "promotion_requirements": "A materially distinct KST configuration and direction-owner evidence would be required before any future review.",
        "demotion_or_kill_criteria": "Exact tested configuration is already closed after validation failure.",
        "notes": "Retrospective registry reconciliation for the exact tested KST default centerline SPY/BIL configuration only; all KST and multi-cycle momentum research is not universally closed by this record.",
        "instrument_lane": "ETF",
        "evidence_tier": "blocked",
        "primary_failure_mode": "period_instability",
        "duplication_risk": "exact_configuration_closed",
        "evidence_needed": "none_for_exact_closed_configuration",
        "duplicate_of": "",
        "blocked_reason": "period_instability",
        "forbidden_next_actions": [
            "retest_exact_configuration",
            "change_rules",
            "tune_parameters",
            "promote_to_paper_demo",
            "activate_paper_demo",
            "promote_to_real_money",
            "add_broker_integration",
            "place_orders",
        ],
        "configuration_fingerprint_schema": FINGERPRINT_SCHEMA_VERSION,
        "configuration_fingerprint": configuration_fingerprint(),
    }


def required_record_complete(record: dict[str, Any]) -> bool:
    required = [
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "stage",
        "outcome",
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "failure_reason",
        "decision_reason",
        "next_action",
        "family_level_interpretation",
        "registration_reason",
    ]
    for field in required:
        value = record.get(field)
        if value in (None, "", [], {}):
            return False
        if isinstance(value, str) and value.lower() in {"unknown", "unmapped"}:
            return False
    return True


def inspect_registry(registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact = []
    aliases = []
    target_fp = configuration_fingerprint()
    for index, record in enumerate(registry.get("strategies", [])):
        if not isinstance(record, dict):
            continue
        candidate_id = record.get("strategy_id") or record.get("id") or ""
        score, matched = alias_score(record)
        record_fp = configuration_fingerprint(record_fingerprint_payload(record))
        row = {
            "registry_index": index,
            "strategy_id": candidate_id,
            "display_name": record.get("display_name", ""),
            "family_id": record.get("family_id") or record.get("family") or record.get("strategy_family") or "",
            "configuration_fingerprint": record_fp,
            "target_fingerprint": target_fp,
            "match_type": "",
            "matched_fields": matched,
            "alias_score": score,
        }
        if candidate_id == STRATEGY_ID:
            row["match_type"] = "exact_strategy_id"
            exact.append(row)
        elif record_fp == target_fp:
            row["match_type"] = "exact_configuration_alias"
            aliases.append(row)
    return exact, aliases


def load_authoritative_inputs() -> dict[str, Any]:
    validation_outcome = next(
        row for row in read_csv_rows(VALIDATION_DIR / "outcome_summary.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    validation_card = next(
        row for row in read_csv_rows(VALIDATION_DIR / "strategy_cards.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    validation_trial = next(
        row for row in read_csv_rows(VALIDATION_DIR / "trial_ledger.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    exploration_card = next(
        row for row in read_csv_rows(EXPLORATION_DIR / "strategy_cards.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    exploration_trial = next(
        row for row in read_csv_rows(EXPLORATION_DIR / "trial_ledger.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    validation_failure = next(
        row for row in read_csv_rows(VALIDATION_DIR / "failure_reasons.csv") if row.get("strategy_id") == STRATEGY_ID
    )
    validation_next_action = next(
        row
        for row in read_csv_rows(VALIDATION_DIR / "next_actions.csv")
        if row.get("entity_id") == STRATEGY_ID and row.get("entity_type") == "strategy_configuration"
    )
    return {
        "validation_manifest": read_yaml(VALIDATION_DIR / "validation_manifest.yaml"),
        "validation_consistency": read_json(VALIDATION_DIR / "consistency_check.json"),
        "validation_outcome": validation_outcome,
        "validation_failure": validation_failure,
        "validation_next_action": validation_next_action,
        "rolling_summary": read_csv_rows(VALIDATION_DIR / "rolling_window_summary.csv"),
        "validation_card": validation_card,
        "validation_trial": validation_trial,
        "exploration_card": exploration_card,
        "exploration_trial": exploration_trial,
    }


def evidence_gate(inputs: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    manifest = inputs["validation_manifest"]
    if manifest.get("strategy_id") != STRATEGY_ID or manifest.get("family_id") != FAMILY_ID:
        blockers.append("validation_manifest_identity_mismatch")
    if manifest.get("trial_id") != VALIDATION_TRIAL_ID or manifest.get("parent_trial_id") != EXPLORATION_TRIAL_ID:
        blockers.append("validation_manifest_lineage_mismatch")
    if manifest.get("outcome") != "validation_failed":
        blockers.append("validation_manifest_outcome_not_failed")
    if manifest.get("failure_reason") != "period_instability":
        blockers.append("validation_manifest_failure_reason_mismatch")
    if inputs["validation_outcome"].get("primary_failure_reason") != "period_instability":
        blockers.append("validation_outcome_failure_reason_mismatch")
    if inputs["validation_failure"].get("primary_failure_reason") != "period_instability":
        blockers.append("validation_failure_record_mismatch")
    if inputs["validation_next_action"].get("exact_next_action") != "direction_owner_review_close_kst_after_validation_v1":
        blockers.append("validation_next_action_mismatch")
    if inputs["validation_consistency"].get("status") != "pass":
        blockers.append("validation_consistency_not_passed")
    if inputs["validation_consistency"].get("reproduction_pass") is not True:
        blockers.append("validation_reproduction_not_passed")
    if inputs["validation_consistency"].get("all_full_period_invariants_pass") is not True:
        blockers.append("validation_invariants_not_passed")
    decision_checks = json.loads(inputs["validation_outcome"].get("decision_checks", "{}"))
    if decision_checks.get("no_control_dominates_full_period") is not True:
        blockers.append("full_period_control_dominance_mismatch")
    validation_params = normalize_parameters(inputs["validation_card"].get("parameters", {}))
    for field in configuration_fingerprint_payload():
        if field in {"family_id", "instrument_universe"}:
            continue
        if validation_params.get(field) != FROZEN_PARAMETERS[field]:
            blockers.append(f"validation_parameter_mismatch:{field}")
    if inputs["validation_card"].get("instrument_universe") != UNIVERSE_TEXT:
        blockers.append("validation_universe_mismatch")
    if inputs["validation_card"].get("strategy_architecture") != ARCHITECTURE:
        blockers.append("validation_architecture_mismatch")
    validation_trial = inputs["validation_trial"]
    if validation_trial.get("trial_id") != VALIDATION_TRIAL_ID:
        blockers.append("validation_trial_id_mismatch")
    if validation_trial.get("parent_trial_id") != EXPLORATION_TRIAL_ID:
        blockers.append("validation_parent_trial_mismatch")
    if validation_trial.get("changed_fields_from_parent") != CHANGED_FIELDS_FROM_PARENT:
        blockers.append("validation_changed_fields_mismatch")
    if validation_trial.get("strategy_rule_changed") != "false":
        blockers.append("validation_strategy_rule_changed")
    if inputs["exploration_card"].get("outcome") != "exploratory_followup_candidate_standalone":
        blockers.append("exploration_outcome_not_followup_standalone")
    if inputs["exploration_trial"].get("trial_id") != EXPLORATION_TRIAL_ID:
        blockers.append("exploration_trial_mismatch")
    rolling = {
        (row.get("window_months"), row.get("cost_assumption_bps"), row.get("comparison_scope")): row
        for row in inputs["rolling_summary"]
    }
    rolling_36 = rolling.get(("36", "5", "best_non_buy_and_hold_control_per_window"), {})
    rolling_60 = rolling.get(("60", "5", "best_non_buy_and_hold_control_per_window"), {})
    domination_36 = float(rolling_36.get("control_dominated_window_fraction", "nan"))
    domination_60 = float(rolling_60.get("control_dominated_window_fraction", "nan"))
    median_sharpe_36 = float(rolling_36.get("median_sharpe_ratio_difference", "nan"))
    median_sharpe_60 = float(rolling_60.get("median_sharpe_ratio_difference", "nan"))
    if not math.isfinite(domination_36) or abs(domination_36 - 0.6632124352331606) > 1e-12:
        blockers.append("rolling_36_control_dominance_mismatch")
    if not math.isfinite(domination_60) or abs(domination_60 - 0.6882352941176471) > 1e-12:
        blockers.append("rolling_60_control_dominance_mismatch")
    if not math.isfinite(median_sharpe_36) or not median_sharpe_36 < 0:
        blockers.append("rolling_36_median_sharpe_not_negative")
    if not math.isfinite(median_sharpe_60) or not median_sharpe_60 < 0:
        blockers.append("rolling_60_median_sharpe_not_negative")
    return not blockers, blockers


def apply_reconciliation(registry: dict[str, Any], exact: list[dict[str, Any]], aliases: list[dict[str, Any]], evidence_ok: bool) -> tuple[str, str, int, int, list[str]]:
    if not evidence_ok:
        return PROCESS_OUTCOME_BLOCKED, "methodology_failure", 0, 0, []
    if aliases:
        return PROCESS_OUTCOME_BLOCKED, "status_reconciliation_required", 0, 0, []
    if exact:
        indices = [row["registry_index"] for row in exact]
        if len(indices) != 1:
            return PROCESS_OUTCOME_BLOCKED, "status_reconciliation_required", 0, 0, []
        append_or_replace_target_record()
        return PROCESS_OUTCOME_SUCCESS, "", 0, 1, [rel(STRATEGY_REGISTRY)]
    append_or_replace_target_record()
    return PROCESS_OUTCOME_SUCCESS, "", 1, 0, [rel(STRATEGY_REGISTRY)]


def duplicate_rows(exact: list[dict[str, Any]], aliases: list[dict[str, Any]], registry_count: int) -> list[dict[str, Any]]:
    rows = []
    for row in exact:
        rows.append({**row, "duplicate_check_result": "exact_record_exists"})
    for row in aliases:
        rows.append({**row, "duplicate_check_result": "alias_conflict"})
    if not rows:
        rows.append(
            {
                "registry_index": "",
                "strategy_id": "",
                "display_name": "",
                "family_id": "",
                "configuration_fingerprint": "",
                "target_fingerprint": configuration_fingerprint(),
                "match_type": "no_exact_record_no_equivalent_alias",
                "matched_fields": "",
                "alias_score": 0,
                "duplicate_check_result": "clear_to_create_one_closed_record",
                "registry_strategy_count_scanned": registry_count,
            }
        )
    else:
        for row in rows:
            row["registry_strategy_count_scanned"] = registry_count
    return rows


def fingerprint_rows() -> list[dict[str, Any]]:
    payload = configuration_fingerprint_payload()
    return [
        {
            "fingerprint_schema": FINGERPRINT_SCHEMA_VERSION,
            "fingerprint": configuration_fingerprint(payload),
            "field": key,
            "value": value,
        }
        for key, value in payload.items()
    ]


def strategy_card_row(record: dict[str, Any], process_outcome: str) -> dict[str, Any]:
    return {
        "strategy_id": record["strategy_id"],
        "family_id": record["family_id"],
        "display_name": record["display_name"],
        "entity_type": record["entity_type"],
        "strategy_architecture": record["strategy_architecture"],
        "source_or_research_lineage": record["source_or_research_lineage"],
        "instrument_universe": record["instrument_universe"],
        "parameters": record["parameters"],
        "benchmark_or_control": record["benchmark_or_control"],
        "stage": record["stage"] if process_outcome == PROCESS_OUTCOME_SUCCESS else "blocked",
        "outcome": record["outcome"] if process_outcome == PROCESS_OUTCOME_SUCCESS else PROCESS_OUTCOME_BLOCKED,
        "trial_id": record["trial_id"],
        "parent_trial_id": record["parent_trial_id"],
        "adaptation_label": record["adaptation_label"],
        "failure_reason": record["failure_reason"],
        "decision_reason": record["decision_reason"],
        "next_action": record["next_action"] if process_outcome == PROCESS_OUTCOME_SUCCESS else PROJECT_NEXT_ACTION_BLOCKED,
        "paper_demo_eligible": record["paper_demo_eligible"],
        "paper_demo_active": record["paper_demo_active"],
        "benchmark_reference_only": record["benchmark_reference_only"],
        "real_money_authorized": record["real_money_authorized"],
        "family_level_interpretation": record["family_level_interpretation"],
        "registration_reason": record["registration_reason"],
        "configuration_fingerprint": record["configuration_fingerprint"],
    }


def trial_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    exploration = inputs["exploration_trial"]
    validation = inputs["validation_trial"]
    return [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "entity_type": "experiment_trial",
            "trial_id": EXPLORATION_TRIAL_ID,
            "parent_trial_id": "",
            "stage": "exploration",
            "adaptation_label": "",
            "changed_fields_from_parent": "canonical_configuration",
            "outcome": "exploratory_followup_candidate_standalone",
            "failure_reason": "",
            "next_action": exploration.get("next_action", ""),
            "new_experiment_trial_created": False,
            "counted_as_new_trial": False,
        },
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "entity_type": "experiment_trial",
            "trial_id": VALIDATION_TRIAL_ID,
            "parent_trial_id": EXPLORATION_TRIAL_ID,
            "stage": "validation",
            "adaptation_label": ADAPTATION_LABEL,
            "changed_fields_from_parent": CHANGED_FIELDS_FROM_PARENT,
            "outcome": "validation_failed",
            "failure_reason": "period_instability",
            "next_action": STRATEGY_NEXT_ACTION,
            "new_experiment_trial_created": False,
            "counted_as_new_trial": False,
        },
    ]


def benchmark_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    roles = {
        "SPY_buy_and_hold": "primary_benchmark",
        "SPY_30_session_ROC_sign_SPY_BIL": "same_purpose_control",
        "SPY_200d_frozen_control": "generic_trend_control",
        "static_6878_SPY_3122_BIL_monthly_rebalanced": "post_exploration_exposure_matching_control",
    }
    return [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": VALIDATION_TRIAL_ID,
            "benchmark_or_control_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "reference_role": roles[control_id],
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "counted_as_observation": False,
        }
        for control_id in BENCHMARKS_AND_CONTROLS
    ]


def process_task_row(process_outcome: str, process_failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "correction",
        "outcome": process_outcome,
        "failure_reason": process_failure_reason,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "experiment_trial_counted": False,
    }


def registry_before_after_rows(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before_by_id = {row["strategy_id"]: row for row in before}
    after_by_id = {row["strategy_id"]: row for row in after}
    ids = sorted(set(before_by_id) | set(after_by_id) | {STRATEGY_ID})
    rows = []
    for strategy_id in ids:
        b = before_by_id.get(strategy_id, {})
        a = after_by_id.get(strategy_id, {})
        if strategy_id != STRATEGY_ID and not b and not a:
            continue
        rows.append(
            {
                "strategy_id": strategy_id,
                "record_existed_before": bool(b),
                "record_exists_after": bool(a),
                "stage_before": b.get("stage") or b.get("status") or b.get("current_status", ""),
                "stage_after": a.get("stage") or a.get("status") or a.get("current_status", ""),
                "outcome_before": b.get("outcome", ""),
                "outcome_after": a.get("outcome", ""),
                "failure_reason_before": b.get("failure_reason") or b.get("primary_failure_reason", ""),
                "failure_reason_after": a.get("failure_reason") or a.get("primary_failure_reason", ""),
                "next_action_before": b.get("next_action", ""),
                "next_action_after": a.get("next_action", ""),
                "fingerprint_before": b.get("configuration_fingerprint", ""),
                "fingerprint_after": a.get("configuration_fingerprint", ""),
            }
        )
    return rows


def source_state_rows(before: dict[str, str], after: dict[str, str], permitted: list[str]) -> list[dict[str, Any]]:
    permitted_set = set(permitted)
    return [
        {
            "path": path,
            "hash_before": before[path],
            "hash_after": after.get(path, "missing"),
            "changed": before[path] != after.get(path, "missing"),
            "change_permitted": path in permitted_set,
            "change_description": "kst_authoritative_closed_record_reconciled"
            if path in permitted_set and before[path] != after.get(path, "missing")
            else "unchanged",
        }
        for path in sorted(before)
    ]


def outcome_row(
    process_outcome: str,
    process_failure_reason: str,
    created: int,
    updated: int,
    exact_after: int,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "total_exact_kst_records_after_reconciliation": exact_after,
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "benchmark_references": len(BENCHMARKS_AND_CONTROLS),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "new_research_candidates_created": 0,
        "strategy_stage": "closed" if process_outcome == PROCESS_OUTCOME_SUCCESS else "blocked",
        "strategy_outcome": "validation_failed" if process_outcome == PROCESS_OUTCOME_SUCCESS else process_outcome,
        "strategy_failure_reason": "period_instability",
        "strategy_next_action": STRATEGY_NEXT_ACTION if process_outcome == PROCESS_OUTCOME_SUCCESS else "",
        "project_next_action": next_action,
    }


def failure_rows(process_failure_reason: str, process_outcome: str, decision_reason: str) -> list[dict[str, Any]]:
    rows = [
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "closed" if not process_failure_reason else "blocked",
            "outcome": "validation_failed",
            "failure_reason": "period_instability",
            "decision_reason": DECISION_REASON,
        }
    ]
    if process_failure_reason:
        rows.append(
            {
                "entity_type": "process_task",
                "entity_id": TASK_ID,
                "stage": "correction",
                "outcome": process_outcome,
                "failure_reason": process_failure_reason,
                "decision_reason": decision_reason,
            }
        )
    return rows


def next_action_rows(process_outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "scope": "strategy_configuration",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": STRATEGY_NEXT_ACTION if process_outcome == PROCESS_OUTCOME_SUCCESS else "",
            "execute_now": False,
        },
        {
            "scope": "project",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": next_action,
            "execute_now": False,
        },
    ]


def consistency_payload(
    process_outcome: str,
    process_failure_reason: str,
    decision_reason: str,
    created: int,
    updated: int,
    exact_after: int,
    source_before: dict[str, str],
    source_after: dict[str, str],
    input_before: dict[str, str],
    input_after: dict[str, str],
    permitted_paths: list[str],
    aliases: list[dict[str, Any]],
    final_record: dict[str, Any] | None,
) -> dict[str, Any]:
    changed_paths = [path for path, old_hash in source_before.items() if old_hash != source_after.get(path, "missing")]
    permitted = set(permitted_paths)
    success = process_outcome == PROCESS_OUTCOME_SUCCESS
    payload = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "total_exact_kst_records_after_reconciliation": exact_after,
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "benchmark_references": len(BENCHMARKS_AND_CONTROLS),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "new_research_candidates_created": 0,
        "source_of_truth_hashes_before": source_before,
        "source_of_truth_hashes_after": source_after,
        "source_of_truth_changed_paths": changed_paths,
        "all_source_of_truth_changes_permitted": all(path in permitted for path in changed_paths),
        "input_evidence_hashes_unchanged": input_before == input_after,
        "no_alias_conflict": len(aliases) == 0,
        "final_record_complete": bool(final_record and required_record_complete(final_record)),
        "final_record_closed_validation_failed": bool(
            final_record
            and final_record.get("stage") == "closed"
            and final_record.get("outcome") == "validation_failed"
            and final_record.get("failure_reason") == "period_instability"
        ),
        "strategy_not_benchmark_reference": bool(final_record and final_record.get("benchmark_reference_only") is False),
        "paper_demo_inactive": bool(final_record and final_record.get("paper_demo_active") is False and final_record.get("paper_demo_eligible") is False),
        "closure_scope_exact_configuration_only": bool(
            final_record
            and final_record.get("closure_scope")
            == "exact_kst_10_15_20_30_roc_10_10_10_15_smoothing_1_2_3_4_weights_zero_centerline_spy_bil_next_session_configuration_only"
        ),
        **FORBIDDEN_FLAGS,
    }
    payload["consistency_passed"] = bool(
        payload["input_evidence_hashes_unchanged"]
        and payload["all_source_of_truth_changes_permitted"]
        and payload["new_experiment_trials"] == 0
        and payload["paper_demo_observations_changed"] == 0
        and payload["new_research_candidates_created"] == 0
        and not any(payload[key] for key in FORBIDDEN_FLAGS)
        and (
            (
                success
                and exact_after == 1
                and (created, updated) in {(1, 0), (0, 1)}
                and payload["final_record_complete"]
                and payload["final_record_closed_validation_failed"]
                and payload["strategy_not_benchmark_reference"]
                and payload["paper_demo_inactive"]
                and payload["closure_scope_exact_configuration_only"]
            )
            or (
                not success
                and process_failure_reason in {"status_reconciliation_required", "methodology_failure"}
                and not changed_paths
            )
        )
    )
    return payload


def report_text(
    process_outcome: str,
    process_failure_reason: str,
    decision_reason: str,
    created: int,
    updated: int,
    exact_after: int,
    aliases: list[dict[str, Any]],
    next_action: str,
) -> str:
    lines = [
        "# Reconcile And Close KST After Validation V1",
        "",
        f"Process outcome: `{process_outcome}`",
        f"Strategy ID: `{STRATEGY_ID}`",
        f"Authoritative strategy records created: `{created}`",
        f"Authoritative strategy records updated: `{updated}`",
        f"Total exact KST records after reconciliation: `{exact_after}`",
        f"Alias conflicts found: `{len(aliases)}`",
        "",
        "The record is reconciled from the exploration and validation evidence only. No performance was recalculated.",
        "",
        "Final lifecycle basis:",
        "- Validation outcome: `validation_failed`",
        "- Primary failure reason: `period_instability`",
        f"- Decision reason: `{DECISION_REASON}`",
        "",
    ]
    if process_failure_reason:
        lines.extend(
            [
                f"Blocked failure reason: `{process_failure_reason}`",
                f"Blocked decision reason: `{decision_reason}`",
            ]
        )
    else:
        lines.extend(
            [
                "The exact tested KST configuration was recorded directly as closed.",
                f"Strategy next action: `{STRATEGY_NEXT_ACTION}`",
            ]
        )
    lines.extend(
        [
            f"Project next action: `{next_action}`",
            "",
            "The closure is limited to the frozen SPY/BIL default KST configuration with ROC periods 10/15/20/30, smoothing periods 10/10/10/15, component weights 1/2/3/4, zero centerline, no signal line, and following-session application.",
            "",
            "No backtest, tuning, validation, robustness, promotion, paper/demo activation, provider download, broker action, or real-money action occurred.",
        ]
    )
    return "\n".join(lines)


FIELDS = {
    "duplicate_and_alias_check.csv": [
        "registry_index",
        "strategy_id",
        "display_name",
        "family_id",
        "configuration_fingerprint",
        "target_fingerprint",
        "match_type",
        "matched_fields",
        "alias_score",
        "duplicate_check_result",
        "registry_strategy_count_scanned",
    ],
    "configuration_fingerprint.csv": ["fingerprint_schema", "fingerprint", "field", "value"],
    "strategy_cards.csv": [
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "stage",
        "outcome",
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "failure_reason",
        "decision_reason",
        "next_action",
        "paper_demo_eligible",
        "paper_demo_active",
        "benchmark_reference_only",
        "real_money_authorized",
        "family_level_interpretation",
        "registration_reason",
        "configuration_fingerprint",
    ],
    "trial_ledger.csv": [
        "strategy_id",
        "family_id",
        "entity_type",
        "trial_id",
        "parent_trial_id",
        "stage",
        "adaptation_label",
        "changed_fields_from_parent",
        "outcome",
        "failure_reason",
        "next_action",
        "new_experiment_trial_created",
        "counted_as_new_trial",
    ],
    "process_task_log.csv": [
        "task_id",
        "entity_type",
        "stage",
        "outcome",
        "failure_reason",
        "exact_next_action",
        "strategy_counted",
        "experiment_trial_counted",
    ],
    "benchmark_reference_log.csv": [
        "strategy_id",
        "family_id",
        "trial_id",
        "benchmark_or_control_id",
        "entity_type",
        "stage",
        "reference_role",
        "counted_as_strategy",
        "counted_as_trial",
        "counted_as_observation",
    ],
    "registry_record_before_after.csv": [
        "strategy_id",
        "record_existed_before",
        "record_exists_after",
        "stage_before",
        "stage_after",
        "outcome_before",
        "outcome_after",
        "failure_reason_before",
        "failure_reason_after",
        "next_action_before",
        "next_action_after",
        "fingerprint_before",
        "fingerprint_after",
    ],
    "state_change_manifest.csv": ["path", "hash_before", "hash_after", "changed", "change_permitted", "change_description"],
    "outcome_summary.csv": [
        "strategy_id",
        "family_id",
        "process_outcome",
        "process_failure_reason",
        "authoritative_strategy_records_created",
        "authoritative_strategy_records_updated",
        "total_exact_kst_records_after_reconciliation",
        "existing_experiment_trials_carried_forward",
        "new_experiment_trials",
        "benchmark_references",
        "process_tasks",
        "paper_demo_observations_changed",
        "new_research_candidates_created",
        "strategy_stage",
        "strategy_outcome",
        "strategy_failure_reason",
        "strategy_next_action",
        "project_next_action",
    ],
    "failure_reasons.csv": ["entity_type", "entity_id", "stage", "outcome", "failure_reason", "decision_reason"],
    "next_actions.csv": ["scope", "strategy_id", "exact_next_action", "execute_now"],
}


def run() -> dict[str, Any]:
    source_before = hash_paths(PROTECTED_PATHS)
    input_before = hash_paths(INPUT_EVIDENCE_FILES)
    clean_output_dir()
    inputs = load_authoritative_inputs()
    evidence_ok, evidence_blockers = evidence_gate(inputs)
    registry_before = load_registry()
    before_records = [row for row in registry_before.get("strategies", []) if isinstance(row, dict) and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID]
    exact, aliases = inspect_registry(registry_before)
    process_outcome, process_failure_reason, created, updated, permitted_paths = apply_reconciliation(
        registry_before,
        exact,
        aliases,
        evidence_ok,
    )
    if process_failure_reason == "methodology_failure" and evidence_blockers:
        decision_reason = "|".join(evidence_blockers)
    elif aliases:
        decision_reason = "targeted_equivalent_alias_conflict"
    else:
        decision_reason = "closed_record_reconciled_from_exploration_and_validation_evidence"
    registry_after = load_registry()
    after_records = [row for row in registry_after.get("strategies", []) if isinstance(row, dict) and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID]
    final_record = after_records[0] if len(after_records) == 1 else None
    exact_after, aliases_after = inspect_registry(registry_after)
    exact_after_count = len(exact_after)
    source_after = hash_paths(PROTECTED_PATHS)
    input_after = hash_paths(INPUT_EVIDENCE_FILES)
    next_action = PROJECT_NEXT_ACTION_SUCCESS if process_outcome == PROCESS_OUTCOME_SUCCESS else PROJECT_NEXT_ACTION_BLOCKED

    duplicate_check = duplicate_rows(exact, aliases, len(registry_before.get("strategies", [])))
    strategy_rows = [strategy_card_row(target_registry_record(), process_outcome)]
    trial_lineage = trial_rows(inputs)
    benchmark_refs = benchmark_rows(inputs)
    process_rows = [process_task_row(process_outcome, process_failure_reason, next_action)]
    before_after = registry_before_after_rows(before_records, after_records)
    state_rows = source_state_rows(source_before, source_after, permitted_paths)
    outcome = outcome_row(process_outcome, process_failure_reason, created, updated, exact_after_count, next_action)
    failures = failure_rows(process_failure_reason, process_outcome, decision_reason)
    next_rows = next_action_rows(process_outcome, next_action)
    consistency = consistency_payload(
        process_outcome,
        process_failure_reason,
        decision_reason,
        created,
        updated,
        exact_after_count,
        source_before,
        source_after,
        input_before,
        input_after,
        permitted_paths,
        aliases_after,
        final_record,
    )
    manifest = {
        "task_id": TASK_ID,
        "mode": "standardization-patch",
        "stage": "correction",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "total_exact_kst_records_after_reconciliation": exact_after_count,
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "benchmark_references": len(benchmark_refs),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "new_research_candidates_created": 0,
        "source_of_truth_changed_paths": consistency["source_of_truth_changed_paths"],
        "exact_next_action": next_action,
    }

    write_yaml(OUTPUT_DIR / "reconciliation_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "duplicate_and_alias_check.csv", duplicate_check, FIELDS["duplicate_and_alias_check.csv"])
    write_csv(OUTPUT_DIR / "configuration_fingerprint.csv", fingerprint_rows(), FIELDS["configuration_fingerprint.csv"])
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows, FIELDS["strategy_cards.csv"])
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_lineage, FIELDS["trial_ledger.csv"])
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, FIELDS["process_task_log.csv"])
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_refs, FIELDS["benchmark_reference_log.csv"])
    write_csv(OUTPUT_DIR / "registry_record_before_after.csv", before_after, FIELDS["registry_record_before_after.csv"])
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_rows, FIELDS["state_change_manifest.csv"])
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome], FIELDS["outcome_summary.csv"])
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failures, FIELDS["failure_reasons.csv"])
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, FIELDS["next_actions.csv"])
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "reconciliation_report.md",
        report_text(process_outcome, process_failure_reason, decision_reason, created, updated, exact_after_count, aliases_after, next_action),
    )
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "total_exact_kst_records_after_reconciliation": exact_after_count,
        "new_experiment_trials": 0,
        "paper_demo_observations_changed": 0,
        "new_research_candidates_created": 0,
        "consistency_passed": consistency["consistency_passed"],
        "exact_next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
