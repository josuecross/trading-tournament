from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "close_hrp_after_validation_v1"
DISPLAY_NAME = "Close HRP After Failed Validation"
OUTPUT_DIR = ROOT / "evidence" / "lifecycle" / TASK_ID / "latest"
VALIDATION_DIR = ROOT / "evidence" / "validation" / "hrp_incremental_diversifier_validation_v1" / "latest"

STRATEGY_ID = "lopez_de_prado_hrp_five_asset_v1"
FAMILY_ID = "hierarchical_risk_parity_allocation"
STRATEGY_DISPLAY_NAME = "Five-Asset Hierarchical Risk Parity"
PARENT_TRIAL_ID = "fast_source_v4__lopez_de_prado_hrp_five_asset_v1__canonical"
VALIDATION_TRIAL_ID = "validation_hrp__lopez_de_prado_hrp_five_asset_v1__validation_variant_child"
ADAPTATION_LABEL = "validation_variant"
SUCCESS_NEXT_ACTION = "refresh_strategy_source_library_v2"
BLOCKED_NEXT_ACTION = "direction_owner_review_hrp_closure_block_v1"
EXACT_CLOSURE_NEXT_ACTION = "do_not_retest_exact_hrp_five_asset_configuration"
SUCCESS_OUTCOME = "lifecycle_recording_successful"
BLOCKED_OUTCOME = "lifecycle_recording_blocked"
FAMILY_INTERPRETATION = "exact_configuration_closed_no_incremental_value"
FROZEN_PARAMETERS = {
    "lookback_trading_days": 252,
    "return_type": "daily_log_return",
    "covariance_estimator": "sample_covariance",
    "distance_formula": "sqrt((1-rho)/2)",
    "linkage_method": "single",
    "tie_break": "lexical_ticker_order",
    "rebalance_frequency": "monthly",
    "warmup_rule": "equal_weights_before_252_observations",
}
BENCHMARKS_AND_CONTROLS = (
    "frozen_current_active_vm_dsr_usci_combo",
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "static_initial_hrp_weight_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
)
PROTECTED_SOURCE_OF_TRUTH_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
VALIDATION_EVIDENCE_FILES = [
    VALIDATION_DIR / name
    for name in [
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "rolling_window_summary.csv",
        "hrp_weight_concentration_summary.csv",
        "consistency_check.json",
        "validation_report.md",
    ]
]
FORBIDDEN_FLAGS = {
    "hrp_rerun": False,
    "alternative_lookbacks": False,
    "alternative_covariance_estimators": False,
    "alternative_clustering_or_linkage": False,
    "universe_changes": False,
    "parameter_tuning": False,
    "static_weight_optimization": False,
    "overlays": False,
    "benchmark_changes": False,
    "validation_or_robustness": False,
    "paper_demo_eligibility_or_activation": False,
    "broad_registry_cleanup": False,
    "dashboard_rebuilding": False,
    "source_research": False,
    "provider_downloads": False,
    "broker_account_order_paper_live_or_real_money_action": False,
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def load_validation_state() -> dict[str, Any]:
    manifest = read_yaml(VALIDATION_DIR / "validation_manifest.yaml")
    outcome_rows = read_csv_rows(VALIDATION_DIR / "outcome_summary.csv")
    failure_rows = read_csv_rows(VALIDATION_DIR / "failure_reasons.csv")
    rolling_rows = read_csv_rows(VALIDATION_DIR / "rolling_window_summary.csv")
    weight_rows = read_csv_rows(VALIDATION_DIR / "hrp_weight_concentration_summary.csv")
    consistency = read_json(VALIDATION_DIR / "consistency_check.json")
    strategy_rows = read_csv_rows(VALIDATION_DIR / "strategy_cards.csv")
    trial_rows = read_csv_rows(VALIDATION_DIR / "trial_ledger.csv")
    benchmark_rows = read_csv_rows(VALIDATION_DIR / "benchmark_reference_log.csv")
    return {
        "manifest": manifest,
        "outcome": next((row for row in outcome_rows if row.get("strategy_id") == STRATEGY_ID), {}),
        "failure": next((row for row in failure_rows if row.get("strategy_id") == STRATEGY_ID), {}),
        "rolling": rolling_rows,
        "weights": weight_rows,
        "consistency": consistency,
        "strategy_card": next((row for row in strategy_rows if row.get("strategy_id") == STRATEGY_ID), {}),
        "trial": next((row for row in trial_rows if row.get("strategy_id") == STRATEGY_ID), {}),
        "benchmarks": benchmark_rows,
    }


def validation_gate(validation: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    manifest = validation["manifest"]
    outcome = validation["outcome"]
    consistency = validation["consistency"]
    if manifest.get("strategy_id") != STRATEGY_ID:
        blockers.append("validation_manifest_strategy_id_mismatch")
    if manifest.get("outcome") != "validation_failed":
        blockers.append("validation_manifest_outcome_not_failed")
    if manifest.get("primary_failure_reason") != "benchmark_like_behavior":
        blockers.append("validation_manifest_failure_reason_mismatch")
    if outcome.get("outcome") != "validation_failed":
        blockers.append("outcome_summary_not_validation_failed")
    if outcome.get("primary_failure_reason") != "benchmark_like_behavior":
        blockers.append("outcome_summary_failure_reason_mismatch")
    if outcome.get("decision_reason") != "IEF_or_BIL_economically_replicates_HRP_contribution":
        blockers.append("decision_reason_mismatch")
    if consistency.get("consistency_passed") is not True:
        blockers.append("validation_consistency_check_not_passed")
    if consistency.get("reproduction_passed") is not True:
        blockers.append("validation_reproduction_not_passed")
    return not blockers, blockers


def load_registry() -> dict[str, Any]:
    path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    return read_yaml(path)


def find_registry_records(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in registry.get("strategies", [])
        if isinstance(row, dict) and row.get("strategy_id") == STRATEGY_ID
    ]


def closure_supported(validation: dict[str, Any], registry_records: list[dict[str, Any]]) -> tuple[bool, str, str, list[str]]:
    validation_ok, validation_blockers = validation_gate(validation)
    if not validation_ok:
        return False, "methodology_failure", "authoritative_validation_evidence_failed_closure_gate", validation_blockers
    if len(registry_records) != 1:
        return (
            False,
            "status_reconciliation_required",
            "exact_hrp_strategy_record_absent_from_strategy_registry" if not registry_records else "multiple_hrp_strategy_records_in_strategy_registry",
            [f"registry_record_count={len(registry_records)}"],
        )
    return True, "", "closure_supported_by_exact_registry_record_and_failed_validation", []


def update_registry_record_if_supported(registry: dict[str, Any], supported: bool) -> list[str]:
    if not supported:
        return []
    paths_changed = [rel(ROOT / "strategy_lab" / "strategy_registry.yaml")]
    for row in registry.get("strategies", []):
        if isinstance(row, dict) and row.get("strategy_id") == STRATEGY_ID:
            row.update(
                {
                    "family_id": FAMILY_ID,
                    "display_name": STRATEGY_DISPLAY_NAME,
                    "entity_type": "strategy_configuration",
                    "strategy_architecture": "hierarchical_risk_based_multi_asset_allocation",
                    "source_or_research_lineage": "strategy_source_library_refresh_v1__lopez_de_prado_hrp",
                    "instrument_universe": "SPY|EEM|IEF|DBC|VNQ",
                    "parameters": FROZEN_PARAMETERS,
                    "benchmark_or_control": "|".join(BENCHMARKS_AND_CONTROLS),
                    "stage": "closed",
                    "outcome": "validation_failed",
                    "trial_id": VALIDATION_TRIAL_ID,
                    "parent_trial_id": PARENT_TRIAL_ID,
                    "adaptation_label": ADAPTATION_LABEL,
                    "failure_reason": "benchmark_like_behavior",
                    "next_action": EXACT_CLOSURE_NEXT_ACTION,
                    "family_level_interpretation": FAMILY_INTERPRETATION,
                    "closure_scope": "exact_five_etf_252d_sample_cov_single_linkage_monthly_execution_configuration_only",
                }
            )
            break
    path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    return paths_changed


def rolling_facts(validation: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for row in validation["rolling"]:
        if row.get("cost_assumption_bps") == "5" and row.get("window_months") in {"36", "60"}:
            prefix = f"rolling_{row['window_months']}"
            facts[f"{prefix}_median_sharpe_difference_vs_best_control"] = row.get("median_sharpe_difference_vs_best_control", "")
            facts[f"{prefix}_positive_sharpe_difference_count"] = row.get("positive_sharpe_difference_count", "")
            facts[f"{prefix}_control_dominated_window_pct"] = row.get("control_dominated_window_pct", "")
    return facts


def weight_facts(validation: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for row in validation["weights"]:
        if row.get("summary_scope") == "instrument_weight" and row.get("instrument") == "IEF":
            facts["average_IEF_weight"] = row.get("average_weight", "")
            facts["percentage_months_IEF_largest_allocation"] = row.get("percentage_months_largest_allocation", "")
        if row.get("summary_scope") == "portfolio_concentration":
            facts["percentage_months_any_asset_exceeds_50pct"] = row.get("percentage_months_any_asset_exceeds_50pct", "")
            facts["median_effective_number_of_holdings"] = row.get("median_effective_number_of_holdings", "")
    return facts


def strategy_card_row(supported: bool, outcome: str, process_failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": STRATEGY_DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": "hierarchical_risk_based_multi_asset_allocation",
        "source_or_research_lineage": "strategy_source_library_refresh_v1__lopez_de_prado_hrp",
        "instrument_universe": "SPY|EEM|IEF|DBC|VNQ",
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": BENCHMARKS_AND_CONTROLS,
        "stage": "closed" if supported else "validation",
        "outcome": "validation_failed",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "failure_reason": "benchmark_like_behavior",
        "next_action": EXACT_CLOSURE_NEXT_ACTION if supported else next_action,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "lifecycle_recording_status": "strategy_configuration_closed" if supported else "blocked_no_source_of_truth_update",
        "process_failure_reason": process_failure_reason,
        "counted_as_strategy_configuration_update": supported,
    }


def trial_ledger_row(next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": STRATEGY_DISPLAY_NAME,
        "entity_type": "experiment_trial",
        "stage": "validation",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "changed_fields_from_parent": "validation_diagnostics_and_predeclared_simple_controls_only",
        "outcome": "validation_failed",
        "failure_reason": "benchmark_like_behavior",
        "next_action": EXACT_CLOSURE_NEXT_ACTION,
        "new_experiment_trial_created": False,
        "counted_as_new_trial": False,
    }


def benchmark_reference_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in validation["benchmarks"]:
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "family_id": FAMILY_ID,
                "trial_id": VALIDATION_TRIAL_ID,
                "benchmark_or_control_id": row.get("benchmark_or_control_id", ""),
                "entity_type": "benchmark_reference",
                "stage": "benchmark_reference_only",
                "reference_role": row.get("reference_role", ""),
                "counted_as_strategy": False,
                "counted_as_trial": False,
                "counted_as_observation": False,
                "approved_by_this_task": False,
            }
        )
    return rows


def process_task_row(process_outcome: str, process_failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "process_task",
        "stage": "correction",
        "outcome": process_outcome,
        "failure_reason": process_failure_reason,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
    }


def closure_decision_row(
    supported: bool,
    process_failure_reason: str,
    decision_reason: str,
    next_action: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    facts = {**rolling_facts(validation), **weight_facts(validation)}
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "closure_decision": "closed" if supported else "blocked",
        "closure_scope": "exact_five_etf_252d_sample_cov_single_linkage_monthly_execution_configuration_only",
        "strategy_stage": "closed" if supported else "validation",
        "strategy_outcome": "validation_failed",
        "strategy_failure_reason": "benchmark_like_behavior",
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "exact_strategy_next_action": EXACT_CLOSURE_NEXT_ACTION if supported else "",
        "process_next_action": next_action,
        "validation_evidence_path": rel(VALIDATION_DIR),
        **facts,
    }


def state_change_rows(
    before: dict[str, str],
    after: dict[str, str],
    changed_paths: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(before):
        rows.append(
            {
                "path": path,
                "hash_before": before[path],
                "hash_after": after.get(path, "missing"),
                "changed": before[path] != after.get(path, "missing"),
                "change_permitted": path in set(changed_paths),
                "change_description": "existing_hrp_strategy_record_closed" if path in set(changed_paths) else "unchanged",
            }
        )
    return rows


def outcome_summary_row(
    supported: bool,
    process_outcome: str,
    process_failure_reason: str,
    decision_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "strategy_configurations_updated": 1 if supported else 0,
        "existing_experiment_trials_carried_forward": 1,
        "new_experiment_trials": 0,
        "benchmark_references": len(BENCHMARKS_AND_CONTROLS),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "strategy_stage": "closed" if supported else "validation",
        "strategy_outcome": "validation_failed",
        "strategy_failure_reason": "benchmark_like_behavior",
        "process_stage": "correction",
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "next_action": next_action,
    }


def failure_reason_rows(process_failure_reason: str, decision_reason: str) -> list[dict[str, Any]]:
    rows = [
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "validation",
            "outcome": "validation_failed",
            "failure_reason": "benchmark_like_behavior",
            "decision_reason": "IEF_or_BIL_economically_replicates_HRP_contribution",
        }
    ]
    if process_failure_reason:
        rows.append(
            {
                "entity_type": "process_task",
                "entity_id": TASK_ID,
                "stage": "correction",
                "outcome": BLOCKED_OUTCOME,
                "failure_reason": process_failure_reason,
                "decision_reason": decision_reason,
            }
        )
    return rows


def next_action_rows(supported: bool, next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": "strategy_configuration",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": EXACT_CLOSURE_NEXT_ACTION if supported else "",
            "execute_now": False,
        },
        {
            "scope": "process_task",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": next_action,
            "execute_now": False,
        },
    ]
    return rows


def consistency_payload(
    supported: bool,
    process_outcome: str,
    process_failure_reason: str,
    decision_reason: str,
    next_action: str,
    registry_record_count_before: int,
    registry_record_count_after: int,
    source_before: dict[str, str],
    source_after: dict[str, str],
    validation_before: dict[str, str],
    validation_after: dict[str, str],
    changed_paths: list[str],
    blocker_details: list[str],
) -> dict[str, Any]:
    permitted_changes = set(changed_paths)
    changed_source_paths = [path for path, before_hash in source_before.items() if before_hash != source_after.get(path, "missing")]
    consistency = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "closure_supported": supported,
        "registry_record_count_before": registry_record_count_before,
        "registry_record_count_after": registry_record_count_after,
        "exactly_one_existing_hrp_strategy_record_found": registry_record_count_before == 1,
        "strategy_configurations_updated": 1 if supported else 0,
        "existing_experiment_trials_carried_forward": 1,
        "new_experiment_trials": 0,
        "benchmark_references": len(BENCHMARKS_AND_CONTROLS),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "source_of_truth_hashes_before": source_before,
        "source_of_truth_hashes_after": source_after,
        "source_of_truth_changed_paths": changed_source_paths,
        "all_source_of_truth_changes_permitted": all(path in permitted_changes for path in changed_source_paths),
        "validation_evidence_hashes_unchanged": validation_before == validation_after,
        "no_partial_state_update_when_blocked": (supported or not changed_source_paths),
        "closure_scope_exact_configuration_only": True,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "hrp_not_converted_to_benchmark": True,
        "benchmark_references_separate": True,
        "process_task_not_counted_as_strategy_or_trial": True,
        "blocker_details": blocker_details,
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["validation_evidence_hashes_unchanged"]
        and consistency["all_source_of_truth_changes_permitted"]
        and consistency["no_partial_state_update_when_blocked"]
        and consistency["new_experiment_trials"] == 0
        and consistency["paper_demo_observations_changed"] == 0
        and consistency["process_task_not_counted_as_strategy_or_trial"]
        and not any(consistency[key] for key in FORBIDDEN_FLAGS)
        and (
            (supported and registry_record_count_after == 1 and process_outcome == SUCCESS_OUTCOME and next_action == SUCCESS_NEXT_ACTION)
            or (
                not supported
                and registry_record_count_before != 1
                and process_failure_reason == "status_reconciliation_required"
                and process_outcome == BLOCKED_OUTCOME
                and next_action == BLOCKED_NEXT_ACTION
            )
            or (
                not supported
                and process_failure_reason == "methodology_failure"
                and process_outcome == BLOCKED_OUTCOME
                and next_action == BLOCKED_NEXT_ACTION
            )
        )
    )
    return consistency


def build_report(
    supported: bool,
    process_failure_reason: str,
    decision_reason: str,
    next_action: str,
    validation: dict[str, Any],
    registry_record_count: int,
) -> str:
    facts = {**rolling_facts(validation), **weight_facts(validation)}
    lines = [
        "# Close HRP After Failed Validation V1",
        "",
        f"Task outcome: `{SUCCESS_OUTCOME if supported else BLOCKED_OUTCOME}`",
        f"Strategy ID: `{STRATEGY_ID}`",
        f"Validation trial carried forward: `{VALIDATION_TRIAL_ID}`",
        f"Registry records found for exact strategy ID: `{registry_record_count}`",
        "",
        "Direction-owner evidence used:",
        "- Validation outcome was `validation_failed`.",
        "- Primary failure reason was `benchmark_like_behavior`.",
        "- Decision reason was `IEF_or_BIL_economically_replicates_HRP_contribution`.",
        f"- Rolling 36-month median Sharpe difference vs best control: `{facts.get('rolling_36_median_sharpe_difference_vs_best_control', '')}`.",
        f"- Rolling 60-month median Sharpe difference vs best control: `{facts.get('rolling_60_median_sharpe_difference_vs_best_control', '')}`.",
        f"- 36-month dominated-window pct: `{facts.get('rolling_36_control_dominated_window_pct', '')}`.",
        f"- 60-month dominated-window pct: `{facts.get('rolling_60_control_dominated_window_pct', '')}`.",
        f"- Average IEF weight: `{facts.get('average_IEF_weight', '')}`.",
        f"- IEF largest-allocation pct: `{facts.get('percentage_months_IEF_largest_allocation', '')}`.",
        "",
    ]
    if supported:
        lines.extend(
            [
                "The exact HRP strategy configuration was closed in the existing source-of-truth record.",
                f"Exact strategy next action: `{EXACT_CLOSURE_NEXT_ACTION}`.",
                f"Process next action: `{next_action}`.",
            ]
        )
    else:
        lines.extend(
            [
                "Lifecycle recording was blocked before modifying source-of-truth state.",
                f"Process failure reason: `{process_failure_reason}`.",
                f"Blocker: `{decision_reason}`.",
                "No new strategy record was created because the task permits updating an existing HRP record only.",
                f"Exact next action: `{next_action}`.",
            ]
        )
    lines.extend(
        [
            "",
            "No performance was recalculated. No HRP rerun, tuning, robustness, source review, paper/demo activation, provider download, broker action, or real-money action occurred.",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    validation: dict[str, Any],
    supported: bool,
    process_failure_reason: str,
    decision_reason: str,
    next_action: str,
    source_before: dict[str, str],
    source_after: dict[str, str],
    validation_before: dict[str, str],
    validation_after: dict[str, str],
    changed_paths: list[str],
    registry_record_count_before: int,
    registry_record_count_after: int,
    blocker_details: list[str],
) -> dict[str, Any]:
    process_outcome = SUCCESS_OUTCOME if supported else BLOCKED_OUTCOME
    strategy_rows = [strategy_card_row(supported, process_outcome, process_failure_reason, next_action)]
    trial_rows = [trial_ledger_row(next_action)]
    process_rows = [process_task_row(process_outcome, process_failure_reason, next_action)]
    benchmark_rows = benchmark_reference_rows(validation)
    decision_rows = [closure_decision_row(supported, process_failure_reason, decision_reason, next_action, validation)]
    state_rows = state_change_rows(source_before, source_after, changed_paths)
    outcome_rows = [outcome_summary_row(supported, process_outcome, process_failure_reason, decision_reason, next_action)]
    failure_rows = failure_reason_rows(process_failure_reason, decision_reason)
    next_rows = next_action_rows(supported, next_action)
    consistency = consistency_payload(
        supported,
        process_outcome,
        process_failure_reason,
        decision_reason,
        next_action,
        registry_record_count_before,
        registry_record_count_after,
        source_before,
        source_after,
        validation_before,
        validation_after,
        changed_paths,
        blocker_details,
    )
    manifest = {
        "task_id": TASK_ID,
        "display_name": DISPLAY_NAME,
        "mode": "active-direction-execution",
        "lane": "targeted_lifecycle_closure",
        "task_stage": "correction",
        "scope": "research_and_paper_demo_only",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "strategy_configurations_updated": 1 if supported else 0,
        "existing_experiment_trials_carried_forward": 1,
        "new_experiment_trials": 0,
        "benchmark_references": len(benchmark_rows),
        "process_tasks": 1,
        "paper_demo_observations_changed": 0,
        "validation_evidence_path": rel(VALIDATION_DIR),
        "source_of_truth_changed_paths": consistency["source_of_truth_changed_paths"],
        "exact_next_action": next_action,
        "closure_scope": "exact_five_etf_252d_sample_cov_single_linkage_monthly_execution_configuration_only",
        "family_level_interpretation": FAMILY_INTERPRETATION,
    }

    write_yaml(OUTPUT_DIR / "closure_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows, STRATEGY_CARD_FIELDS)
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows, TRIAL_LEDGER_FIELDS)
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, PROCESS_TASK_FIELDS)
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_rows, BENCHMARK_FIELDS)
    write_csv(OUTPUT_DIR / "closure_decision.csv", decision_rows, CLOSURE_DECISION_FIELDS)
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_rows, STATE_CHANGE_FIELDS)
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows, OUTCOME_FIELDS)
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, FAILURE_FIELDS)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, NEXT_ACTION_FIELDS)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "closure_report.md",
        build_report(supported, process_failure_reason, decision_reason, next_action, validation, registry_record_count_before),
    )
    return consistency


STRATEGY_CARD_FIELDS = [
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
    "next_action",
    "family_level_interpretation",
    "lifecycle_recording_status",
    "process_failure_reason",
    "counted_as_strategy_configuration_update",
]
TRIAL_LEDGER_FIELDS = [
    "strategy_id",
    "family_id",
    "display_name",
    "entity_type",
    "stage",
    "trial_id",
    "parent_trial_id",
    "adaptation_label",
    "changed_fields_from_parent",
    "outcome",
    "failure_reason",
    "next_action",
    "new_experiment_trial_created",
    "counted_as_new_trial",
]
PROCESS_TASK_FIELDS = [
    "task_id",
    "display_name",
    "entity_type",
    "stage",
    "outcome",
    "failure_reason",
    "exact_next_action",
    "strategy_counted",
    "trial_counted",
]
BENCHMARK_FIELDS = [
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
    "approved_by_this_task",
]
CLOSURE_DECISION_FIELDS = [
    "strategy_id",
    "family_id",
    "closure_decision",
    "closure_scope",
    "strategy_stage",
    "strategy_outcome",
    "strategy_failure_reason",
    "process_failure_reason",
    "decision_reason",
    "family_level_interpretation",
    "exact_strategy_next_action",
    "process_next_action",
    "validation_evidence_path",
    "rolling_36_median_sharpe_difference_vs_best_control",
    "rolling_60_median_sharpe_difference_vs_best_control",
    "rolling_36_positive_sharpe_difference_count",
    "rolling_60_positive_sharpe_difference_count",
    "rolling_36_control_dominated_window_pct",
    "rolling_60_control_dominated_window_pct",
    "average_IEF_weight",
    "percentage_months_IEF_largest_allocation",
    "percentage_months_any_asset_exceeds_50pct",
    "median_effective_number_of_holdings",
]
STATE_CHANGE_FIELDS = ["path", "hash_before", "hash_after", "changed", "change_permitted", "change_description"]
OUTCOME_FIELDS = [
    "strategy_id",
    "family_id",
    "strategy_configurations_updated",
    "existing_experiment_trials_carried_forward",
    "new_experiment_trials",
    "benchmark_references",
    "process_tasks",
    "paper_demo_observations_changed",
    "strategy_stage",
    "strategy_outcome",
    "strategy_failure_reason",
    "process_stage",
    "process_outcome",
    "process_failure_reason",
    "decision_reason",
    "next_action",
]
FAILURE_FIELDS = ["entity_type", "entity_id", "stage", "outcome", "failure_reason", "decision_reason"]
NEXT_ACTION_FIELDS = ["scope", "strategy_id", "exact_next_action", "execute_now"]


def run() -> dict[str, Any]:
    source_before = hash_paths(PROTECTED_SOURCE_OF_TRUTH_PATHS)
    validation_before = hash_paths(VALIDATION_EVIDENCE_FILES)
    clean_output_dir()
    validation = load_validation_state()
    registry = load_registry()
    registry_records = find_registry_records(registry)
    registry_count_before = len(registry_records)
    supported, process_failure_reason, decision_reason, blocker_details = closure_supported(validation, registry_records)
    changed_paths = update_registry_record_if_supported(registry, supported)
    registry_after = load_registry()
    registry_count_after = len(find_registry_records(registry_after))
    source_after = hash_paths(PROTECTED_SOURCE_OF_TRUTH_PATHS)
    validation_after = hash_paths(VALIDATION_EVIDENCE_FILES)
    next_action = SUCCESS_NEXT_ACTION if supported else BLOCKED_NEXT_ACTION
    consistency = write_artifacts(
        validation,
        supported,
        process_failure_reason,
        decision_reason,
        next_action,
        source_before,
        source_after,
        validation_before,
        validation_after,
        changed_paths,
        registry_count_before,
        registry_count_after,
        blocker_details,
    )
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": SUCCESS_OUTCOME if supported else BLOCKED_OUTCOME,
        "process_failure_reason": process_failure_reason,
        "decision_reason": decision_reason,
        "strategy_configurations_updated": 1 if supported else 0,
        "new_experiment_trials": 0,
        "paper_demo_observations_changed": 0,
        "registry_record_count": registry_count_before,
        "consistency_passed": consistency["consistency_passed"],
        "exact_next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
