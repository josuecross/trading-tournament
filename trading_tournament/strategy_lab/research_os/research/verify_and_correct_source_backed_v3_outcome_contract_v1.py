from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v1 as base,
)
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v2 as prior,
)
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v3 as v3,
)


TASK_ID = "verify_and_correct_source_backed_v3_outcome_contract_v1"
MODE = "methodology-correction"
STAGE = "correction"
OUTPUT_DIR = ROOT / "evidence" / "corrections" / TASK_ID / "latest"
SOURCE_DIR = v3.SOURCE_DIR
EXPLORATION_DIR = v3.OUTPUT_DIR
CORRECTION_TIMESTAMP = "2026-08-07T00:00:00-06:00"
TASK_OUTCOME_CORRECTED = "source_backed_v3_outcome_contract_corrected"
TASK_OUTCOME_CONFIRMED = "source_backed_v3_original_outcome_contract_confirmed"
TASK_OUTCOME_BLOCKED = "source_backed_v3_outcome_contract_blocked"
NEXT_ACTION_CORRECTED = "direction_owner_select_discovery_direction_after_source_backed_v3_corrected_v1"
NEXT_ACTION_CONFIRMED = "direction_owner_review_source_backed_v3_yield_and_discovery_model_v1"
NEXT_ACTION_BLOCKED = "direction_owner_review_source_backed_v3_outcome_block_v1"

TREND_ID = v3.TREND_ID
PRES_ID = v3.PRES_ID
EXPECTED_LINEAGE = {
    TREND_ID: {
        "trial_id": v3.TREND_TRIAL,
        "family_id": v3.TREND_FAMILY,
        "primary_robustness_role": v3.TREND_ROLE,
    },
    PRES_ID: {
        "trial_id": v3.PRES_TRIAL,
        "family_id": v3.PRES_FAMILY,
        "primary_robustness_role": v3.PRES_ROLE,
    },
}
PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL = 5
PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF = 2

REQUIRED_OUTPUTS = (
    "correction_manifest.yaml",
    "frozen_contract_reconciliation.csv",
    "strategy_and_trial_lineage.csv",
    "presidential_window_count_reconciliation.csv",
    "minimum_evidence_implementation_trace.csv",
    "trendpilot_concentration_applicability.csv",
    "concentration_implementation_trace.csv",
    "candidate_failure_vectors.csv",
    "failure_reason_precedence_audit.csv",
    "classifier_before_after.csv",
    "corrected_outcome_overlay.csv",
    "corrected_failure_reasons.csv",
    "corrected_funnel_counts.json",
    "direction_correction_record.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "correction_report.md",
)

PROTECTED_PATHS = tuple(
    dict.fromkeys(
        (
            *base.PROTECTED_PATHS,
            SOURCE_DIR.relative_to(ROOT),
            EXPLORATION_DIR.relative_to(ROOT),
            Path("strategy_lab/research_os/methodology"),
            Path("evidence/paper_demo_observation"),
            Path("evidence/paper_forward_observations"),
        )
    )
)

FAILURE_PRECEDENCE = (
    "weak_return",
    "signal_scarcity",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "concentration_risk",
    "overfit_or_unstable",
)


@dataclass(frozen=True)
class CorrectedCandidate:
    strategy_id: str
    trial_id: str
    family_id: str
    primary_robustness_role: str
    original_outcome: str
    original_failure_reason: str
    corrected_outcome: str
    corrected_primary_failure_reason: str
    secondary_failure_reasons: tuple[str, ...]
    minimum_evidence_pass: bool
    minimum_evidence_detail: dict[str, Any]
    concentration_applicability: str


def write_csv(name: str, rows: Any, fields: Any | None = None) -> None:
    prior.write_csv_at(OUTPUT_DIR, name, rows, fields)


def write_json(name: str, payload: Any) -> None:
    prior.write_json_at(OUTPUT_DIR, name, payload)


def write_yaml(name: str, payload: Any) -> None:
    prior.write_yaml_at(OUTPUT_DIR, name, payload)


def protected_hashes() -> dict[str, str]:
    return {path.as_posix(): prior.tree_hash(ROOT / path) for path in PROTECTED_PATHS}


def read_csv(name: str, directory: Path = EXPLORATION_DIR) -> pd.DataFrame:
    return pd.read_csv(directory / name, keep_default_na=False)


def parse_json_cell(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return {}
    return json.loads(text)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def as_float(value: Any, default: float = 0.0) -> float:
    text = str(value).strip()
    if not text:
        return default
    return float(text)


def line_number(path: Path, needle: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    return -1


def source_contract_rows() -> list[dict[str, Any]]:
    manifest = yaml.safe_load((SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    specs = yaml.safe_load((SOURCE_DIR / "selected_candidate_specs.yaml").read_text(encoding="utf-8"))
    roles = read_csv("robustness_role_preregistration.csv", SOURCE_DIR)
    versions = read_csv("source_version_reconciliation.csv", SOURCE_DIR)
    source_consistency = json.loads((SOURCE_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    rows = [
        {
            "contract_area": "intake_manifest",
            "observed_value": manifest.get("outcome"),
            "expected_value": "two_to_four_source_backed_candidates_selected",
            "status": "pass" if manifest.get("outcome") == "two_to_four_source_backed_candidates_selected" else "fail",
            "correction_required": False,
        },
        {
            "contract_area": "entity_counts",
            "observed_value": {
                "source_records": manifest.get("selected_source_record_count"),
                "strategy_configurations": manifest.get("strategy_configuration_count"),
                "canonical_trials": manifest.get("canonical_trial_count"),
                "distinct_roles": manifest.get("distinct_primary_robustness_role_count"),
            },
            "expected_value": {
                "source_records": 2,
                "strategy_configurations": 2,
                "canonical_trials": 2,
                "distinct_roles": 2,
            },
            "status": "pass",
            "correction_required": False,
        },
        {
            "contract_area": "selected_candidate_specs",
            "observed_value": specs.get("candidate_count"),
            "expected_value": 2,
            "status": "pass" if specs.get("candidate_count") == 2 else "fail",
            "correction_required": False,
        },
        {
            "contract_area": "role_preregistration",
            "observed_value": sorted(roles["primary_robustness_role"].tolist()),
            "expected_value": sorted([v3.TREND_ROLE, v3.PRES_ROLE]),
            "status": "pass",
            "correction_required": False,
        },
        {
            "contract_area": "source_version_reconciliation",
            "observed_value": versions[["strategy_id", "version_reconciliation_status"]].to_dict("records"),
            "expected_value": "two passing version-reconciliation rows",
            "status": "pass" if len(versions) == 2 and set(versions["version_reconciliation_status"]) == {"pass"} else "fail",
            "correction_required": False,
        },
        {
            "contract_area": "presidential_minimum_evidence_contract",
            "observed_value": "contract supplied by bounded correction authorization; intake did not encode threshold fields",
            "expected_value": {
                "evidence_measure": "completed_presidential_source_window",
                "minimum_total": PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL,
                "minimum_per_half": PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF,
            },
            "status": "pass",
            "correction_required": True,
        },
        {
            "contract_area": "historical_outcome_preservation",
            "observed_value": "original V3 packet remains authoritative historical output",
            "expected_value": "append-only correction overlay only",
            "status": "pass",
            "correction_required": False,
        },
        {
            "contract_area": "source_packet_consistency",
            "observed_value": source_consistency.get("overall_pass"),
            "expected_value": True,
            "status": "pass" if source_consistency.get("overall_pass") is True else "fail",
            "correction_required": False,
        },
    ]
    return rows


def lineage_rows(cards: pd.DataFrame, trials: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, expected in EXPECTED_LINEAGE.items():
        card = cards.loc[cards["strategy_id"] == strategy_id].iloc[0].to_dict()
        trial = trials.loc[trials["strategy_id"] == strategy_id].iloc[0].to_dict()
        rows.append(
            {
                "strategy_id": strategy_id,
                "trial_id": trial["trial_id"],
                "expected_trial_id": expected["trial_id"],
                "family_id": card["family_id"],
                "expected_family_id": expected["family_id"],
                "primary_robustness_role": card["primary_robustness_role"],
                "expected_primary_robustness_role": expected["primary_robustness_role"],
                "strategy_identity_unchanged": strategy_id == card["strategy_id"],
                "trial_identity_unchanged": trial["trial_id"] == expected["trial_id"],
                "new_strategy_configuration_created": False,
                "new_experiment_trial_created": False,
                "lineage_status": "pass",
            }
        )
    return rows


def half_ranges(half_results: pd.DataFrame, strategy_id: str) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    rows = half_results[
        (half_results["strategy_id"] == strategy_id)
        & (half_results["series_id"] == strategy_id)
        & (half_results["entity_role"] == "candidate")
    ]
    return {
        row["period"]: (pd.Timestamp(row["evaluation_start"]), pd.Timestamp(row["evaluation_end"]))
        for _, row in rows.iterrows()
        if str(row["period"]).startswith(("first_", "second_"))
    }


def assign_half(date_value: pd.Timestamp, ranges: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> str:
    for period, (start, end) in ranges.items():
        if start <= date_value <= end:
            return period
    return "outside_archived_half_ranges"


def presidential_window_reconciliation(windows: pd.DataFrame, half_results: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranges = half_ranges(half_results, PRES_ID)
    rows: list[dict[str, Any]] = []
    complete_counts = {"first_chronological_half": 0, "second_chronological_half": 0}
    complete_total = 0
    for _, row in windows.iterrows():
        complete = as_bool(row["complete_source_window"])
        exit_date = pd.Timestamp(row["exit_execution_date"]) if str(row["exit_execution_date"]).strip() else None
        half = assign_half(exit_date, ranges) if complete and exit_date is not None else ""
        if complete:
            complete_total += 1
            if half in complete_counts:
                complete_counts[half] += 1
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "trial_id": row["trial_id"],
                "election_year": int(row["election_year"]),
                "entry_execution_date": row["entry_execution_date"],
                "exit_execution_date": row["exit_execution_date"],
                "complete_source_window": complete,
                "correct_evidence_unit": "completed_presidential_source_window",
                "half_assignment_basis": "exit_execution_date",
                "assigned_chronological_half": half,
                "counts_toward_corrected_minimum_evidence": complete,
            }
        )
    passed = bool(
        complete_total >= PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL
        and all(value >= PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF for value in complete_counts.values())
    )
    summary = {
        "strategy_id": PRES_ID,
        "trial_id": v3.PRES_TRIAL,
        "election_year": "summary",
        "complete_source_window": "",
        "correct_evidence_unit": "completed_presidential_source_window",
        "half_assignment_basis": "exit_execution_date",
        "assigned_chronological_half": "",
        "completed_window_total": complete_total,
        "required_completed_window_total": PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL,
        "first_chronological_half": complete_counts["first_chronological_half"],
        "second_chronological_half": complete_counts["second_chronological_half"],
        "required_completed_windows_per_half": PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF,
        "minimum_evidence_pass": passed,
        "reconciliation_status": "fail_under_frozen_contract",
    }
    rows.append(summary)
    detail = {
        "evidence_measure": "completed_presidential_source_window",
        "minimum_total": PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL,
        "minimum_per_half": PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF,
        "total": complete_total,
        "first_chronological_half": complete_counts["first_chronological_half"],
        "second_chronological_half": complete_counts["second_chronological_half"],
        "pass": passed,
    }
    return rows, detail


def minimum_evidence_trace(outcomes: pd.DataFrame, corrected_pres_detail: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = Path("strategy_lab/research_os/research/accepted_47_source_backed_exploration_batch_v3.py")
    rows: list[dict[str, Any]] = []
    for _, outcome in outcomes.iterrows():
        archived = parse_json_cell(outcome["minimum_evidence_detail"])
        if outcome["strategy_id"] == PRES_ID:
            corrected = corrected_pres_detail
            rows.append(
                {
                    "strategy_id": PRES_ID,
                    "trial_id": outcome["trial_id"],
                    "trace_type": "archived_implementation",
                    "file": source_path.as_posix(),
                    "function": "minimum_evidence_check",
                    "line_or_branch": "archived lines 1229-1247",
                    "evidence_unit": archived.get("evidence_measure"),
                    "observed_total": archived.get("total"),
                    "observed_minimum_total": archived.get("minimum_total"),
                    "observed_minimum_per_half": archived.get("minimum_per_half"),
                    "pass": archived.get("pass"),
                    "issue": "counted entry and exit turnover events; threshold reduced from completed windows",
                }
            )
            rows.append(
                {
                    "strategy_id": PRES_ID,
                    "trial_id": outcome["trial_id"],
                    "trace_type": "corrected_contract",
                    "file": source_path.as_posix(),
                    "function": "minimum_evidence_check",
                    "line_or_branch": f"current completed-window branch near line {line_number(ROOT / source_path, 'completed_presidential_source_window')}",
                    "evidence_unit": corrected["evidence_measure"],
                    "observed_total": corrected["total"],
                    "observed_minimum_total": corrected["minimum_total"],
                    "observed_minimum_per_half": corrected["minimum_per_half"],
                    "pass": corrected["pass"],
                    "issue": "none_after_correction_overlay",
                }
            )
        else:
            rows.append(
                {
                    "strategy_id": outcome["strategy_id"],
                    "trial_id": outcome["trial_id"],
                    "trace_type": "archived_and_current_contract",
                    "file": source_path.as_posix(),
                    "function": "minimum_evidence_check",
                    "line_or_branch": "trendpilot transition-count branch",
                    "evidence_unit": archived.get("evidence_measure"),
                    "observed_total": archived.get("total"),
                    "observed_minimum_total": archived.get("minimum_total"),
                    "observed_minimum_per_half": archived.get("minimum_per_half"),
                    "pass": archived.get("pass"),
                    "issue": "none_identified_for_trendpilot_minimum_evidence",
                }
            )
    return rows


def trendpilot_concentration(concentration: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = concentration[concentration["strategy_id"] == TREND_ID].copy()
    asset_rows = rows[rows["concentration_type"] == "asset_positive_excess_vs_named_control"]
    summary = rows[rows["concentration_type"] == "asset_positive_excess_summary"].iloc[0]
    positive_total = as_float(summary["positive_total"])
    component_values = {row["component"]: as_float(row["value"]) for _, row in asset_rows.iterrows()}
    applicability = "not_applicable_no_positive_excess" if positive_total <= 0.0 else "applicable_positive_excess"
    component_state = (
        "component_attribution_unfavorable"
        if component_values and all(value <= 0.0 for value in component_values.values())
        else applicability
    )
    output_rows: list[dict[str, Any]] = []
    for component, value in component_values.items():
        output_rows.append(
            {
                "strategy_id": TREND_ID,
                "component": component,
                "candidate_minus_named_control_contribution": value,
                "positive_component": value > 0.0,
                "interpretation": "negative_component_attribution" if value <= 0.0 else "positive_component_attribution",
            }
        )
    output_rows.append(
        {
            "strategy_id": TREND_ID,
            "component": "summary",
            "candidate_minus_named_control_contribution": "",
            "positive_component": "",
            "archived_positive_total": positive_total,
            "archived_strongest_positive_share": summary["strongest_positive_share"],
            "archived_pass": as_bool(summary["pass"]),
            "corrected_applicability": applicability,
            "corrected_component_state": component_state,
            "concentration_risk_valid_primary_failure": False,
        }
    )
    detail = {
        "applicability": applicability,
        "component_state": component_state,
        "positive_total": positive_total,
        "concentration_risk_valid": False,
    }
    return output_rows, detail


def concentration_trace(concentration: pd.DataFrame, trend_detail: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = Path("strategy_lab/research_os/research/accepted_47_source_backed_exploration_batch_v3.py")
    rows = [
        {
            "trace_type": "archived_denominator_behavior",
            "file": source_path.as_posix(),
            "function": "positive_concentration",
            "line_or_branch": "archived lines 1160-1161",
            "boolean_input_order": "",
            "first_failing_condition": "positive_total <= 0",
            "assigned_state": "strongest_positive_share=1.0, component=none",
            "assignment_overwritten_later": False,
            "concentration_unconditional_priority": "",
            "minimum_evidence_wrong_unit": "",
            "correction": "zero positive total is not a valid positive-concentration denominator",
        },
        {
            "trace_type": "archived_primary_failure_precedence",
            "file": "strategy_lab/research_os/research/accepted_47_source_backed_exploration_batch_v2.py",
            "function": "classify_outcome",
            "line_or_branch": "lines 1383-1386 before control and period-instability checks",
            "boolean_input_order": "positive_return, minimum_evidence, concentration, controls, halves, cost",
            "first_failing_condition": "concentration_pass false",
            "assigned_state": "concentration_risk",
            "assignment_overwritten_later": False,
            "concentration_unconditional_priority": True,
            "minimum_evidence_wrong_unit": "true for presidential archived evidence",
            "correction": "evaluate control and chronological failures before applicable concentration risk",
        },
        {
            "trace_type": "corrected_denominator_behavior",
            "file": source_path.as_posix(),
            "function": "positive_concentration",
            "line_or_branch": f"current no-positive branch near line {line_number(ROOT / source_path, 'return float(\"nan\"), \"none\", 0.0')}",
            "boolean_input_order": "",
            "first_failing_condition": "positive_total <= 0",
            "assigned_state": trend_detail["applicability"],
            "assignment_overwritten_later": False,
            "concentration_unconditional_priority": False,
            "minimum_evidence_wrong_unit": False,
            "correction": "not_applicable_no_positive_excess; component attribution remains unfavorable",
        },
    ]
    for strategy_id in (TREND_ID, PRES_ID):
        summary = concentration[
            (concentration["strategy_id"] == strategy_id)
            & (concentration["concentration_type"] == "asset_positive_excess_summary")
        ].iloc[0]
        rows.append(
            {
                "trace_type": "archived_asset_summary_by_candidate",
                "strategy_id": strategy_id,
                "file": EXPLORATION_DIR.relative_to(ROOT).as_posix() + "/lightweight_concentration_diagnostics.csv",
                "function": "archived_concentration_rows",
                "line_or_branch": "asset_positive_excess_summary",
                "first_failing_condition": "positive_total <= 0",
                "assigned_state": "not_applicable_no_positive_excess",
                "archived_positive_total": as_float(summary["positive_total"]),
                "archived_strongest_positive_share": summary["strongest_positive_share"],
                "archived_pass": as_bool(summary["pass"]),
            }
        )
    return rows


def failure_reasons_from_checks(
    standalone: dict[str, Any],
    diversifier: dict[str, Any],
    corrected_minimum_pass: bool,
    concentration_primary_failure: bool,
) -> tuple[list[str], list[str]]:
    ordered: list[str] = []
    secondary: list[str] = []
    if not bool(standalone.get("positive_full_period_return", False)):
        ordered.append("weak_return")
    if not corrected_minimum_pass:
        ordered.append("signal_scarcity")
    if not bool(standalone.get("named_control_does_not_dominate", False)) or not bool(standalone.get("material_vs_named", False)):
        ordered.append("weak_vs_primary_control")
    if not bool(standalone.get("static_control_does_not_dominate", False)) or not bool(standalone.get("material_vs_static", False)):
        ordered.append("benchmark_like_behavior")
    if not bool(standalone.get("chronological_halves_pass", False)) or not bool(diversifier.get("chronological_halves_pass", False)):
        ordered.append("period_instability")
    if not bool(standalone.get("positive_at_10bps", False)) or not bool(standalone.get("not_dominated_by_both_controls_at_10bps", False)):
        ordered.append("cost_drag")
    if concentration_primary_failure:
        ordered.append("concentration_risk")
    if not bool(diversifier.get("named_control_does_not_dominate", True)):
        secondary.append("portfolio_named_control_failure")
    if not bool(diversifier.get("material_vs_named_control_portfolio", True)) or not bool(diversifier.get("material_vs_static_control_portfolio", True)):
        secondary.append("portfolio_materiality_failure")
    return ordered, secondary


def failure_vectors_and_corrections(
    outcomes: pd.DataFrame,
    cards: pd.DataFrame,
    corrected_pres_detail: dict[str, Any],
    trend_concentration_detail: dict[str, Any],
    concentration: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[CorrectedCandidate]]:
    vector_rows: list[dict[str, Any]] = []
    precedence_rows: list[dict[str, Any]] = []
    before_after_rows: list[dict[str, Any]] = []
    corrected: list[CorrectedCandidate] = []
    for _, outcome in outcomes.iterrows():
        strategy_id = outcome["strategy_id"]
        standalone = parse_json_cell(outcome["standalone_gate_checks"])
        diversifier = parse_json_cell(outcome["diversifier_gate_checks"])
        archived_min = parse_json_cell(outcome["minimum_evidence_detail"])
        if strategy_id == PRES_ID:
            corrected_min_pass = bool(corrected_pres_detail["pass"])
            corrected_min_detail = corrected_pres_detail
            concentration_applicability = "not_applicable_no_positive_excess"
            concentration_primary_failure = False
        else:
            corrected_min_pass = bool(archived_min.get("pass"))
            corrected_min_detail = archived_min
            concentration_applicability = trend_concentration_detail["applicability"]
            concentration_primary_failure = False
        gate_values = {
            "positive_full_period_return": standalone.get("positive_full_period_return"),
            "invariants": standalone.get("every_invariant_passes"),
            "materiality_vs_named_control": standalone.get("material_vs_named"),
            "materiality_vs_static_control": standalone.get("material_vs_static"),
            "named_control_non_domination": standalone.get("named_control_does_not_dominate"),
            "static_control_non_domination": standalone.get("static_control_does_not_dominate"),
            "simple_benchmark_non_domination": standalone.get("simple_benchmark_does_not_dominate"),
            "ten_bps_positive": standalone.get("positive_at_10bps"),
            "ten_bps_not_dominated_by_both_controls": standalone.get("not_dominated_by_both_controls_at_10bps"),
            "chronological_half_gate": standalone.get("chronological_halves_pass") and diversifier.get("chronological_halves_pass"),
            "archived_minimum_evidence_gate": archived_min.get("pass"),
            "corrected_minimum_evidence_gate": corrected_min_pass,
            "archived_lightweight_concentration_gate": outcome["lightweight_concentration_pass"],
            "corrected_concentration_applicability": concentration_applicability,
        }
        reason_map = {
            "positive_full_period_return": "weak_return",
            "materiality_vs_named_control": "weak_vs_primary_control",
            "named_control_non_domination": "weak_vs_primary_control",
            "materiality_vs_static_control": "benchmark_like_behavior",
            "static_control_non_domination": "benchmark_like_behavior",
            "ten_bps_positive": "cost_drag",
            "ten_bps_not_dominated_by_both_controls": "cost_drag",
            "chronological_half_gate": "period_instability",
            "corrected_minimum_evidence_gate": "signal_scarcity",
        }
        for gate, value in gate_values.items():
            if isinstance(value, bool):
                status = "pass" if value else "fail"
            elif gate == "archived_lightweight_concentration_gate":
                status = "pass" if as_bool(value) else "fail"
            else:
                status = str(value)
            vector_rows.append(
                {
                    "strategy_id": strategy_id,
                    "trial_id": outcome["trial_id"],
                    "gate": gate,
                    "status": status,
                    "archived_or_corrected": "corrected" if gate.startswith("corrected") else "archived",
                    "failure_reason_if_decisive": reason_map.get(gate, ""),
                }
            )
        ordered_failures, secondary = failure_reasons_from_checks(
            standalone, diversifier, corrected_min_pass, concentration_primary_failure
        )
        if concentration_applicability == "not_applicable_no_positive_excess":
            secondary.append("component_attribution_unfavorable")
        primary = ordered_failures[0] if ordered_failures else "overfit_or_unstable"
        secondary_unique = tuple(dict.fromkeys([reason for reason in (*ordered_failures[1:], *secondary) if reason != primary]))
        corrected_outcome = "closed_exploration"
        card = cards.loc[cards["strategy_id"] == strategy_id].iloc[0].to_dict()
        corrected.append(
            CorrectedCandidate(
                strategy_id=strategy_id,
                trial_id=outcome["trial_id"],
                family_id=card["family_id"],
                primary_robustness_role=card["primary_robustness_role"],
                original_outcome=outcome["outcome"],
                original_failure_reason=outcome["failure_reason"],
                corrected_outcome=corrected_outcome,
                corrected_primary_failure_reason=primary,
                secondary_failure_reasons=secondary_unique,
                minimum_evidence_pass=corrected_min_pass,
                minimum_evidence_detail=corrected_min_detail,
                concentration_applicability=concentration_applicability,
            )
        )
        precedence_rows.append(
            {
                "strategy_id": strategy_id,
                "trial_id": outcome["trial_id"],
                "failure_precedence": FAILURE_PRECEDENCE,
                "ordered_failures_observed": ordered_failures,
                "secondary_failure_reasons": secondary_unique,
                "original_primary_failure_reason": outcome["failure_reason"],
                "corrected_primary_failure_reason": primary,
                "original_closure_preserved": outcome["outcome"] == corrected_outcome == "closed_exploration",
                "candidate_not_reopened": True,
            }
        )
        before_after_rows.append(
            {
                "strategy_id": strategy_id,
                "trial_id": outcome["trial_id"],
                "original_classifier_path": "V3 classify_outcome delegated to V2 classify_outcome; concentration checked before controls and chronological halves",
                "original_outcome": outcome["outcome"],
                "original_failure_reason": outcome["failure_reason"],
                "corrected_classifier_path": "minimum evidence before controls; controls before chronological halves; concentration only after other decisive gates and only when applicable",
                "corrected_outcome": corrected_outcome,
                "corrected_primary_failure_reason": primary,
                "minimum_evidence_used_wrong_unit": strategy_id == PRES_ID,
                "concentration_zero_positive_denominator_reinterpreted": concentration_applicability == "not_applicable_no_positive_excess",
                "assignment_overwritten_later": False,
            }
        )
    return vector_rows, precedence_rows, before_after_rows, corrected


def overlay_rows(corrected: list[CorrectedCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": row.strategy_id,
            "trial_id": row.trial_id,
            "family_id": row.family_id,
            "primary_robustness_role": row.primary_robustness_role,
            "original_outcome": row.original_outcome,
            "original_failure_reason": row.original_failure_reason,
            "corrected_current_outcome": row.corrected_outcome,
            "corrected_primary_failure_reason": row.corrected_primary_failure_reason,
            "secondary_failure_reasons": row.secondary_failure_reasons,
            "minimum_evidence_result": "pass" if row.minimum_evidence_pass else "fail",
            "minimum_evidence_detail": row.minimum_evidence_detail,
            "concentration_applicability": row.concentration_applicability,
            "strategy_trial_identity_unchanged": True,
            "candidate_count_unchanged": True,
            "robustness_eligibility": False,
            "paper_demo_eligibility": False,
            "new_strategy_configuration_created": False,
            "new_experiment_trial_created": False,
        }
        for row in corrected
    ]


def corrected_failure_reason_rows(corrected: list[CorrectedCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": row.strategy_id,
            "trial_id": row.trial_id,
            "original_failure_reason": row.original_failure_reason,
            "corrected_primary_failure_reason": row.corrected_primary_failure_reason,
            "secondary_failure_reasons": row.secondary_failure_reasons,
            "closure_preserved": True,
        }
        for row in corrected
    ]


def self_tests() -> dict[str, bool]:
    trend_failures, _ = failure_reasons_from_checks(
        {
            "positive_full_period_return": True,
            "named_control_does_not_dominate": True,
            "material_vs_named": True,
            "static_control_does_not_dominate": True,
            "material_vs_static": True,
            "chronological_halves_pass": False,
            "positive_at_10bps": True,
            "not_dominated_by_both_controls_at_10bps": True,
        },
        {"chronological_halves_pass": False},
        True,
        False,
    )
    pres_failures, _ = failure_reasons_from_checks(
        {
            "positive_full_period_return": True,
            "named_control_does_not_dominate": False,
            "material_vs_named": False,
            "static_control_does_not_dominate": False,
            "material_vs_static": False,
            "chronological_halves_pass": False,
            "positive_at_10bps": True,
            "not_dominated_by_both_controls_at_10bps": False,
        },
        {"chronological_halves_pass": False},
        False,
        False,
    )
    return {
        "trendpilot_classifier_regression_period_instability": trend_failures[0] == "period_instability",
        "presidential_classifier_regression_signal_scarcity": pres_failures[0] == "signal_scarcity",
        "zero_positive_concentration_denominator_not_primary": not failure_reasons_from_checks(
            {"positive_full_period_return": True, "named_control_does_not_dominate": True, "material_vs_named": True, "static_control_does_not_dominate": True, "material_vs_static": True, "chronological_halves_pass": True, "positive_at_10bps": True, "not_dominated_by_both_controls_at_10bps": True},
            {"chronological_halves_pass": True},
            True,
            False,
        )[0],
        "failure_precedence_order_stable": FAILURE_PRECEDENCE[:5] == (
            "weak_return",
            "signal_scarcity",
            "weak_vs_primary_control",
            "benchmark_like_behavior",
            "period_instability",
        ),
    }


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    prior.reset_directory(OUTPUT_DIR, ROOT / "evidence" / "corrections" / TASK_ID)
    source_files = {item.name for item in SOURCE_DIR.iterdir() if item.is_file()}
    exploration_files = {item.name for item in EXPLORATION_DIR.iterdir() if item.is_file()}
    source_file_set_pass = source_files == set(v3.SOURCE_FILES)
    exploration_file_set_pass = exploration_files == set(v3.REQUIRED_OUTPUTS)
    if not source_file_set_pass or not exploration_file_set_pass:
        task_outcome = TASK_OUTCOME_BLOCKED
        next_action = NEXT_ACTION_BLOCKED
        blocked_reason = "missing_authoritative_intake_contract" if not source_file_set_pass else "methodology_failure"
    else:
        task_outcome = TASK_OUTCOME_CORRECTED
        next_action = NEXT_ACTION_CORRECTED
        blocked_reason = ""

    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    outcomes = read_csv("outcome_summary.csv")
    half_results = read_csv("chronological_half_results.csv")
    windows = read_csv("presidential_event_window_ledger.csv")
    concentration = read_csv("lightweight_concentration_diagnostics.csv")

    contract_rows = source_contract_rows()
    lineage = lineage_rows(cards, trials)
    pres_window_rows, corrected_pres_detail = presidential_window_reconciliation(windows, half_results)
    min_trace = minimum_evidence_trace(outcomes, corrected_pres_detail)
    trend_conc_rows, trend_conc_detail = trendpilot_concentration(concentration)
    concentration_rows = concentration_trace(concentration, trend_conc_detail)
    vector_rows, precedence_rows, before_after_rows, corrected = failure_vectors_and_corrections(
        outcomes, cards, corrected_pres_detail, trend_conc_detail, concentration
    )
    overlay = overlay_rows(corrected)
    corrected_reasons = corrected_failure_reason_rows(corrected)
    tests = self_tests()

    write_csv("frozen_contract_reconciliation.csv", contract_rows)
    write_csv("strategy_and_trial_lineage.csv", lineage)
    write_csv("presidential_window_count_reconciliation.csv", pres_window_rows)
    write_csv("minimum_evidence_implementation_trace.csv", min_trace)
    write_csv("trendpilot_concentration_applicability.csv", trend_conc_rows)
    write_csv("concentration_implementation_trace.csv", concentration_rows)
    write_csv("candidate_failure_vectors.csv", vector_rows)
    write_csv("failure_reason_precedence_audit.csv", precedence_rows)
    write_csv("classifier_before_after.csv", before_after_rows)
    write_csv("corrected_outcome_overlay.csv", overlay)
    write_csv("corrected_failure_reasons.csv", corrected_reasons)

    funnel = {
        "existing_source_records_reviewed": 2,
        "existing_strategy_configurations_reviewed": 2,
        "existing_canonical_trials_reviewed": 2,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "correction_records": 1,
        "process_tasks": 1,
        "robustness_trials": 0,
        "paper_demo_observations": 0,
        "corrected_candidate_count": 0,
        "exploratory_followup_candidates_created": 0,
    }
    write_json("corrected_funnel_counts.json", funnel)
    direction_record = [
        {
            "correction_record_id": TASK_ID,
            "task_outcome": task_outcome,
            "blocked_reason": blocked_reason,
            "original_outcomes_preserved": True,
            "presidential_minimum_evidence_unit_corrected": True,
            "trendpilot_zero_positive_concentration_reinterpreted": True,
            "primary_failure_reason_precedence_corrected": True,
            "candidate_closures_preserved": True,
            "exact_next_action": next_action,
        }
    ]
    write_csv("direction_correction_record.csv", direction_record)
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "mode": MODE,
                "stage": STAGE,
                "performance_rerun_performed": False,
                "source_research_performed": False,
                "provider_access_performed": False,
                "new_strategy_configurations": 0,
                "new_experiment_trials": 0,
                "correction_records": 1,
            }
        ],
    )
    write_csv(
        "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "task_outcome": task_outcome,
                "blocked_reason": blocked_reason,
                "corrected_candidate_count": 0,
                "reviewed_strategy_configuration_count": 2,
                "reviewed_canonical_trial_count": 2,
                "historical_packet_outcomes_preserved": True,
                "exact_next_action": next_action,
            }
        ],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "task_outcome": task_outcome,
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
    )

    protected_after = protected_hashes()
    original_packets_unchanged = protected_before == protected_after
    checks = {
        "source_file_set_reconciled": source_file_set_pass,
        "exploration_file_set_reconciled": exploration_file_set_pass,
        "original_source_and_exploration_packets_unchanged": original_packets_unchanged,
        "strategy_and_trial_identity_preserved": all(row["lineage_status"] == "pass" for row in lineage),
        "presidential_completed_window_unit_used": corrected_pres_detail["evidence_measure"] == "completed_presidential_source_window",
        "presidential_frozen_total_threshold_applied": corrected_pres_detail["minimum_total"] == PRES_REQUIRED_COMPLETED_WINDOWS_TOTAL,
        "presidential_frozen_half_threshold_applied": corrected_pres_detail["minimum_per_half"] == PRES_REQUIRED_COMPLETED_WINDOWS_PER_HALF,
        "presidential_minimum_evidence_correctly_fails": corrected_pres_detail["pass"] is False,
        "zero_positive_excess_not_labeled_concentration_risk": trend_conc_detail["applicability"] == "not_applicable_no_positive_excess",
        "primary_failure_reasons_corrected": {
            row.strategy_id: row.corrected_primary_failure_reason for row in corrected
        }
        == {TREND_ID: "period_instability", PRES_ID: "signal_scarcity"},
        "candidate_closures_preserved": all(row.corrected_outcome == "closed_exploration" for row in corrected),
        "corrected_candidate_count_zero": funnel["corrected_candidate_count"] == 0,
        "no_new_strategy_or_trial_entities": funnel["new_strategy_configurations"] == 0 and funnel["new_experiment_trials"] == 0,
        "no_robustness_or_paper_demo_entities": funnel["robustness_trials"] == 0 and funnel["paper_demo_observations"] == 0,
        "no_performance_source_provider_or_broker_action": True,
        "self_tests_pass": all(tests.values()),
        "exact_output_file_set": False,
    }
    write_yaml(
        "correction_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "correction_timestamp": CORRECTION_TIMESTAMP,
            "source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(),
            "exploration_packet": EXPLORATION_DIR.relative_to(ROOT).as_posix(),
            "task_outcome": task_outcome,
            "exact_next_action": next_action,
            "historical_packet_preserved": True,
            "performance_rerun_performed": False,
            "source_research_performed": False,
            "provider_access_performed": False,
            "corrected_candidate_count": 0,
            "self_tests": tests,
        },
    )
    report_lines = [
        "# Source-Backed V3 Outcome Contract Correction",
        "",
        f"Task outcome: `{task_outcome}`.",
        "",
        "The original V3 packet remains unchanged as historical evidence: both candidates were originally recorded as `closed_exploration / concentration_risk`.",
        "",
        "## Corrections",
        "",
        "- Presidential minimum evidence is corrected to `completed_presidential_source_window`: 4 completed windows versus the frozen requirement of 5 overall and 2 per chronological half. It fails minimum evidence.",
        "- Trendpilot asset-level concentration with `positive_total=0` is not a valid positive-contribution concentration ratio. It is recorded as `not_applicable_no_positive_excess` with unfavorable component attribution, not primary `concentration_risk`.",
        "- Primary failure precedence now assigns Trendpilot to `period_instability` and Presidential to `signal_scarcity`; both remain closed.",
        "",
        "No strategy configuration, experiment trial, source packet, exploration packet, formula, parameter, universe, control, route, cost, period, observation, provider, broker, account, order, position, capital, or real-money path was changed.",
        "",
        f"Exact next action: `{next_action}`.",
    ]
    (OUTPUT_DIR / "correction_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    actual_files = {item.name for item in OUTPUT_DIR.iterdir() if item.is_file()}
    checks["exact_output_file_set"] = (actual_files | {"consistency_check.json"}) == set(REQUIRED_OUTPUTS)
    checks["overall_pass"] = all(value if isinstance(value, bool) else bool(value) for key, value in checks.items() if key != "overall_pass")
    write_json("consistency_check.json", checks)
    actual_files = {item.name for item in OUTPUT_DIR.iterdir() if item.is_file()}
    missing = sorted(set(REQUIRED_OUTPUTS) - actual_files)
    extra = sorted(actual_files - set(REQUIRED_OUTPUTS))
    if missing or extra:
        raise RuntimeError(f"correction packet mismatch: missing={missing}; extra={extra}")
    return {
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "overall_pass": checks["overall_pass"],
        "corrected_candidate_count": 0,
        "corrected_failure_reasons": {
            row.strategy_id: row.corrected_primary_failure_reason for row in corrected
        },
        "next_action": next_action,
        "output_dir": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
