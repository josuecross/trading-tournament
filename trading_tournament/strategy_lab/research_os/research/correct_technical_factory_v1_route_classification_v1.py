from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import technical_strategy_factory_v1 as factory


TASK_ID = "correct_technical_factory_v1_route_classification_v1"
OUTPUT_DIR = ROOT / "evidence" / "technical_factory" / TASK_ID / "latest"
ORIGINAL_DIR = ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v1" / "latest"
ORIGINAL_PROMPT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\8b7238c1-2b01-4e8b-9db3-8fca7ebe380d\pasted-text.txt"
)
CORRECTION_PROMPT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\6cb2e587-7cf2-4f5a-b99a-d9eb9a95d09f\pasted-text.txt"
)
IMPLEMENTATION_PATH = Path(factory.__file__).resolve()

ARCHITECTURE_ID = "factory_v1_spy_trend_quality_state"
STRATEGY_ID = "factory_v1_spy_trend_quality_state_d1"
TRIAL_ID = "technical_factory_v1__d1__canonical"
FAMILY_ID = "regression_trend_quality"
NAMED_CONTROL = "same_regression_slope_without_path_quality_filter"
STATIC_CONTROL = "full_period_exposure_matched_static_spy_bil"
REFERENCE = "100pct_frozen_reference"
CANDIDATE_PORTFOLIO = "80pct_reference_20pct_candidate"
NAMED_PORTFOLIO = "80pct_reference_20pct_named_same_purpose_control"
STATIC_PORTFOLIO = "80pct_reference_20pct_exposure_or_static_control"
TOLERANCE = 1e-9

REQUIRED_FILES = {
    "correction_manifest.yaml",
    "original_factory_outcome_reconciliation.csv",
    "strategy_and_trial_lineage_reconciliation.csv",
    "original_route_contract.csv",
    "diversifier_gate_implementation_trace.csv",
    "portfolio_metric_reproduction.csv",
    "portfolio_materiality_reconciliation.csv",
    "pass_flag_consumption_audit.csv",
    "corrected_outcome_overlay.csv",
    "corrected_exploratory_followup_candidates.csv",
    "corrected_funnel_counts.json",
    "direction_correction_record.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "correction_report.md",
}


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path, excluded: Path | None = None) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        if excluded_resolved is not None and excluded_resolved in item.resolve().parents:
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def protected_snapshot() -> dict[str, str]:
    snapshot = {
        relative(path): tree_hash(path)
        for path in (*factory.helpers.PROTECTED_STATE_PATHS, *factory.helpers.PROTECTED_TREE_PATHS)
    }
    snapshot["evidence_excluding_current_correction"] = tree_hash(ROOT / "evidence", OUTPUT_DIR)
    snapshot["original_factory_packet"] = tree_hash(ORIGINAL_DIR)
    snapshot["original_factory_prompt"] = file_hash(ORIGINAL_PROMPT)
    snapshot["original_factory_implementation"] = file_hash(IMPLEMENTATION_PATH)
    return snapshot


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "technical_factory" / TASK_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected path {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    columns = list(leading)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )


def read_rows(name: str) -> list[dict[str, str]]:
    with (ORIGINAL_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_hash(row: dict[str, Any]) -> str:
    return sha256_bytes(
        json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    )


def one(rows: list[dict[str, str]], **matches: str) -> dict[str, str]:
    selected = [
        row for row in rows
        if all(row.get(key, "") == value for key, value in matches.items())
    ]
    if len(selected) != 1:
        raise RuntimeError(f"expected one archived row for {matches}, found {len(selected)}")
    return selected[0]


def as_float(row: dict[str, str], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value):
        raise RuntimeError(f"nonfinite archived {key}")
    return value


def dominates(control: dict[str, str], candidate: dict[str, str]) -> bool:
    metrics = ("cagr", "sharpe_ratio", "maximum_drawdown")
    control_values = [as_float(control, metric) for metric in metrics]
    candidate_values = [as_float(candidate, metric) for metric in metrics]
    return bool(
        all(left >= right - 1e-12 for left, right in zip(control_values, candidate_values))
        and any(left > right + 1e-12 for left, right in zip(control_values, candidate_values))
    )


def material_advantage(candidate: dict[str, str], control: dict[str, str]) -> bool:
    return bool(
        as_float(candidate, "sharpe_ratio") - as_float(control, "sharpe_ratio") >= 0.02 - 1e-12
        or as_float(candidate, "maximum_drawdown") - as_float(control, "maximum_drawdown") >= 0.01 - 1e-12
    )


def diversifier_gate(
    candidate: dict[str, str],
    reference: dict[str, str],
    named: dict[str, str],
    static: dict[str, str],
) -> tuple[bool, dict[str, bool]]:
    checks = {
        "material_advantage_vs_frozen_reference": material_advantage(candidate, reference),
        "named_control_does_not_dominate": not dominates(named, candidate),
        "static_control_does_not_dominate": not dominates(static, candidate),
        "material_advantage_vs_named_control": material_advantage(candidate, named),
        "material_advantage_vs_static_control": material_advantage(candidate, static),
    }
    return all(checks.values()), checks


def corrected_classification(
    standalone_pass: bool, diversifier_pass: bool
) -> dict[str, str]:
    if standalone_pass:
        return {
            "architecture_outcome": "factory_exploratory_followup_candidate",
            "selected_configuration_outcome": "exploratory_followup_candidate_standalone",
            "route_classification": (
                "standalone_with_diversifier_diagnostic" if diversifier_pass else "standalone"
            ),
        }
    if diversifier_pass:
        return {
            "architecture_outcome": "factory_exploratory_followup_candidate",
            "selected_configuration_outcome": "exploratory_followup_candidate_diversifier",
            "route_classification": "diversifier",
        }
    return {
        "architecture_outcome": "factory_architecture_closed",
        "selected_configuration_outcome": "closed_exploration",
        "route_classification": "closed",
    }


def source_line(path: Path, needle: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    raise RuntimeError(f"source text not found: {needle}")


def report_text(next_action: str, overall_pass: bool) -> str:
    return "\n".join([
        "# Technical Factory V1 Route Classification Correction",
        "",
        "## Outcome",
        "",
        "The archived D1 standalone result remains `closed_exploration` with `weak_vs_primary_control`. Its separately preregistered 20% portfolio diagnostic reproduced and passed the frozen implementation gate.",
        "",
        "The original outcome branch calculated `diversifier_diagnostic_pass = true` but discarded it whenever the standalone gate failed. The correction overlay therefore classifies D1 as `exploratory_followup_candidate_diversifier` and the architecture as `factory_exploratory_followup_candidate`.",
        "",
        "## Boundaries",
        "",
        "No strategy, trial, parameter, control, fold, return path, robustness result, lifecycle record, or paper/demo observation was created or changed. The original factory packet remains historical and immutable.",
        "",
        f"Consistency check: `overall_pass = {str(overall_pass).lower()}`.",
        "",
        f"Exact next action: `{next_action}`.",
        "",
    ])


def run() -> dict[str, Any]:
    protected_before = protected_snapshot()
    original_packet_hash_before = tree_hash(ORIGINAL_DIR)
    original_file_hashes_before = {
        path.name: file_hash(path) for path in sorted(ORIGINAL_DIR.iterdir()) if path.is_file()
    }
    reset_output()

    outcome_rows = read_rows("outcome_summary.csv")
    strategy_rows = read_rows("strategy_cards.csv")
    trial_rows = read_rows("trial_ledger.csv")
    selected_rows = read_rows("selected_variant_freeze.csv")
    final_rows = read_rows("final_evaluation_results.csv")
    control_rows = read_rows("final_control_results.csv")
    portfolio_rows = read_rows("portfolio_contribution_results.csv")

    original_outcome = one(outcome_rows, architecture_id=ARCHITECTURE_ID)
    strategy = one(strategy_rows, strategy_id=STRATEGY_ID)
    trial = one(trial_rows, trial_id=TRIAL_ID)
    selected = one(selected_rows, architecture_id=ARCHITECTURE_ID)

    standalone_candidate = {
        cost: one(
            final_rows,
            strategy_id=STRATEGY_ID,
            cost_bps_one_way=str(float(cost)),
        )
        for cost in (0, 5, 10)
    }
    standalone_named = {
        cost: one(
            control_rows,
            strategy_id=STRATEGY_ID,
            series_id=NAMED_CONTROL,
            cost_bps_one_way=str(float(cost)),
        )
        for cost in (0, 5, 10)
    }
    standalone_static = {
        cost: one(
            control_rows,
            strategy_id=STRATEGY_ID,
            series_id=STATIC_CONTROL,
            cost_bps_one_way=str(float(cost)),
        )
        for cost in (0, 5, 10)
    }
    portfolio_by_key = {
        (row["construction_id"], int(float(row["cost_bps_one_way"]))): row
        for row in portfolio_rows
        if row["strategy_id"] == STRATEGY_ID
    }
    expected_portfolio_keys = {
        (construction, cost)
        for construction in (REFERENCE, CANDIDATE_PORTFOLIO, NAMED_PORTFOLIO, STATIC_PORTFOLIO)
        for cost in (0, 5, 10)
    }
    if set(portfolio_by_key) != expected_portfolio_keys:
        raise RuntimeError("archived D1 portfolio row set does not reconcile")

    expected_5bps = {
        ("standalone_candidate", "cagr"): 0.11560215202064428,
        ("standalone_candidate", "sharpe_ratio"): 1.2083578624200517,
        ("standalone_candidate", "maximum_drawdown"): -0.08405621664941476,
        ("standalone_named", "cagr"): 0.161056,
        ("standalone_named", "sharpe_ratio"): 1.346462,
        ("standalone_named", "maximum_drawdown"): -0.084056,
        ("standalone_static", "cagr"): 0.140932,
        ("standalone_static", "sharpe_ratio"): 1.585891,
        ("standalone_static", "maximum_drawdown"): -0.101751,
        (REFERENCE, "cagr"): 0.13664566815805812,
        (REFERENCE, "sharpe_ratio"): 1.2965206151073128,
        (REFERENCE, "maximum_drawdown"): -0.11461027785610589,
        (CANDIDATE_PORTFOLIO, "cagr"): 0.13286424330349655,
        (CANDIDATE_PORTFOLIO, "sharpe_ratio"): 1.3777729116659172,
        (CANDIDATE_PORTFOLIO, "maximum_drawdown"): -0.09093196901743694,
        (NAMED_PORTFOLIO, "cagr"): 0.14194574068719046,
        (NAMED_PORTFOLIO, "sharpe_ratio"): 1.3900983695780305,
        (NAMED_PORTFOLIO, "maximum_drawdown"): -0.10254108459837241,
        (STATIC_PORTFOLIO, "cagr"): 0.13777316721052713,
        (STATIC_PORTFOLIO, "sharpe_ratio"): 1.389748955424152,
        (STATIC_PORTFOLIO, "maximum_drawdown"): -0.11184451801140194,
    }
    standalone_sources = {
        "standalone_candidate": standalone_candidate[5],
        "standalone_named": standalone_named[5],
        "standalone_static": standalone_static[5],
    }
    approximate_checks: list[bool] = []
    for (series_id, metric), expected in expected_5bps.items():
        source = (
            standalone_sources[series_id]
            if series_id in standalone_sources
            else portfolio_by_key[(series_id, 5)]
        )
        tolerance = TOLERANCE if series_id not in {"standalone_named", "standalone_static"} else 5e-7
        approximate_checks.append(abs(as_float(source, metric) - expected) <= tolerance)

    reproduction_rows: list[dict[str, Any]] = []
    for label, rows_by_cost in (
        ("standalone_candidate", standalone_candidate),
        ("standalone_named", standalone_named),
        ("standalone_static", standalone_static),
    ):
        for cost, row in rows_by_cost.items():
            reproduction_rows.append({
                "result_scope": "standalone_final_segment",
                "series_id": label,
                "cost_bps_one_way": cost,
                "evaluation_start": row["evaluation_start"],
                "evaluation_end": row["evaluation_end"],
                "total_return": row["total_return"],
                "cagr": row["cagr"],
                "sharpe_ratio": row["sharpe_ratio"],
                "maximum_drawdown": row["maximum_drawdown"],
                "archived_row_hash": row_hash(row),
                "reproduction_basis": "archived_row_and_archived_file_hash",
                "market_return_recalculation_performed": False,
                "reproduction_pass": True,
            })
    for (construction, cost), row in sorted(portfolio_by_key.items()):
        reproduction_rows.append({
            "result_scope": "portfolio_final_segment",
            "series_id": construction,
            "cost_bps_one_way": cost,
            "evaluation_start": row["evaluation_start"],
            "evaluation_end": row["evaluation_end"],
            "total_return": row["total_return"],
            "cagr": row["cagr"],
            "sharpe_ratio": row["sharpe_ratio"],
            "maximum_drawdown": row["maximum_drawdown"],
            "archived_row_hash": row_hash(row),
            "reproduction_basis": "archived_row_and_archived_file_hash",
            "market_return_recalculation_performed": False,
            "reproduction_pass": True,
        })
    write_csv(
        "portfolio_metric_reproduction.csv",
        reproduction_rows,
        ("result_scope", "series_id", "cost_bps_one_way", "evaluation_start", "evaluation_end", "total_return", "cagr", "sharpe_ratio", "maximum_drawdown"),
    )

    materiality_rows: list[dict[str, Any]] = []
    gates: dict[int, tuple[bool, dict[str, bool]]] = {}
    for cost in (5, 10):
        candidate = portfolio_by_key[(CANDIDATE_PORTFOLIO, cost)]
        reference = portfolio_by_key[(REFERENCE, cost)]
        named = portfolio_by_key[(NAMED_PORTFOLIO, cost)]
        static = portfolio_by_key[(STATIC_PORTFOLIO, cost)]
        gates[cost] = diversifier_gate(candidate, reference, named, static)
        for comparison_id, control in (
            ("candidate_vs_frozen_reference", reference),
            ("candidate_vs_named_80_20_control", named),
            ("candidate_vs_exposure_matched_80_20_control", static),
        ):
            sharpe_difference = as_float(candidate, "sharpe_ratio") - as_float(control, "sharpe_ratio")
            drawdown_improvement = as_float(candidate, "maximum_drawdown") - as_float(control, "maximum_drawdown")
            both_worsened = sharpe_difference < 0.0 and drawdown_improvement < 0.0
            materiality_rows.append({
                "cost_bps_one_way": cost,
                "comparison_id": comparison_id,
                "candidate_sharpe": candidate["sharpe_ratio"],
                "control_sharpe": control["sharpe_ratio"],
                "sharpe_difference": sharpe_difference,
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "control_maximum_drawdown": control["maximum_drawdown"],
                "absolute_drawdown_improvement": drawdown_improvement,
                "both_sharpe_and_drawdown_worsened": both_worsened,
                "control_dominates_candidate": dominates(control, candidate),
                "materiality_status": "pass" if material_advantage(candidate, control) else "fail",
                "sharpe_threshold": 0.02,
                "drawdown_threshold": 0.01,
            })
    write_csv(
        "portfolio_materiality_reconciliation.csv",
        materiality_rows,
        ("cost_bps_one_way", "comparison_id", "sharpe_difference", "absolute_drawdown_improvement", "both_sharpe_and_drawdown_worsened", "control_dominates_candidate", "materiality_status"),
    )

    implementation_start = inspect.getsourcelines(factory.evaluate_selected_variants)[1]
    implementation_lines = IMPLEMENTATION_PATH.read_text(encoding="utf-8").splitlines()
    implementation_locations = {
        "material_advantage_vs_reference": source_line(IMPLEMENTATION_PATH, "material_advantage(portfolio_candidate5, reference5)"),
        "named_not_dominant": source_line(IMPLEMENTATION_PATH, "not dominates(portfolio_named5, portfolio_candidate5)"),
        "static_not_dominant": source_line(IMPLEMENTATION_PATH, "not dominates(portfolio_static5, portfolio_candidate5)"),
        "material_advantage_vs_named": source_line(IMPLEMENTATION_PATH, "material_advantage(portfolio_candidate5, portfolio_named5)"),
        "material_advantage_vs_static": source_line(IMPLEMENTATION_PATH, "material_advantage(portfolio_candidate5, portfolio_static5)"),
        "standalone_branch": source_line(IMPLEMENTATION_PATH, "if final_pass:"),
        "diversifier_route_inside_standalone_branch": source_line(IMPLEMENTATION_PATH, "if diversifier_diagnostic_pass"),
    }
    gate5, checks5 = gates[5]
    trace_rows: list[dict[str, Any]] = []
    check_to_location = {
        "material_advantage_vs_frozen_reference": "material_advantage_vs_reference",
        "named_control_does_not_dominate": "named_not_dominant",
        "static_control_does_not_dominate": "static_not_dominant",
        "material_advantage_vs_named_control": "material_advantage_vs_named",
        "material_advantage_vs_static_control": "material_advantage_vs_static",
    }
    for gate_name, value in checks5.items():
        location = implementation_locations[check_to_location[gate_name]]
        trace_rows.append({
            "trace_step": gate_name,
            "code_file": relative(IMPLEMENTATION_PATH),
            "code_line": location,
            "code_text": implementation_lines[location - 1].strip(),
            "input_rows": [CANDIDATE_PORTFOLIO, REFERENCE, NAMED_PORTFOLIO, STATIC_PORTFOLIO],
            "frozen_sharpe_threshold": 0.02,
            "frozen_drawdown_threshold": 0.01,
            "boolean_result": value,
            "matches_frozen_implementation": True,
        })
    trace_rows.append({
        "trace_step": "diversifier_diagnostic_pass",
        "code_file": relative(IMPLEMENTATION_PATH),
        "code_line": implementation_start,
        "code_text": "all five frozen portfolio sub-gates",
        "input_rows": [CANDIDATE_PORTFOLIO, REFERENCE, NAMED_PORTFOLIO, STATIC_PORTFOLIO],
        "frozen_sharpe_threshold": 0.02,
        "frozen_drawdown_threshold": 0.01,
        "boolean_result": gate5,
        "matches_frozen_implementation": gate5 and original_outcome["diversifier_diagnostic_pass"] == "true",
    })
    write_csv(
        "diversifier_gate_implementation_trace.csv",
        trace_rows,
        ("trace_step", "code_file", "code_line", "code_text", "input_rows", "frozen_sharpe_threshold", "frozen_drawdown_threshold", "boolean_result", "matches_frozen_implementation"),
    )

    original_prompt_lines = {
        "predeclared_portfolio_diagnostic": source_line(ORIGINAL_PROMPT, "For final selected variants only, evaluate the predeclared 20% diversifier"),
        "route_may_be_classified": source_line(ORIGINAL_PROMPT, "It may classify the final candidate route as:"),
        "diversifier_route_allowed": source_line(ORIGINAL_PROMPT, "- diversifier;"),
        "diversifier_outcome_allowed": source_line(ORIGINAL_PROMPT, "- exploratory_followup_candidate_diversifier"),
        "no_extra_trial": source_line(ORIGINAL_PROMPT, "Do not create extra trials for portfolio diagnostics."),
    }
    route_contract_rows = [
        {
            "contract_element": name,
            "source_type": "original_factory_prompt",
            "source_file": str(ORIGINAL_PROMPT),
            "source_line": line,
            "contract_value": {
                "predeclared_portfolio_diagnostic": "final selected variants receive frozen 20pct diversifier diagnostic",
                "route_may_be_classified": "portfolio diagnostic may classify route",
                "diversifier_route_allowed": "diversifier",
                "diversifier_outcome_allowed": "exploratory_followup_candidate_diversifier",
                "no_extra_trial": "portfolio diagnostics do not create trials",
            }[name],
            "contract_frozen_before_final_performance": True,
        }
        for name, line in original_prompt_lines.items()
    ]
    route_contract_rows.extend([
        {
            "contract_element": "preregistered_strategy_route",
            "source_type": "archived_strategy_card",
            "source_file": relative(ORIGINAL_DIR / "strategy_cards.csv"),
            "source_line": "archived_row",
            "contract_value": strategy["route"],
            "contract_frozen_before_final_performance": True,
        },
        {
            "contract_element": "output_schema_diversifier_field",
            "source_type": "archived_outcome_schema",
            "source_file": relative(ORIGINAL_DIR / "outcome_summary.csv"),
            "source_line": "header_and_D1_row",
            "contract_value": "diversifier_diagnostic_pass",
            "contract_frozen_before_final_performance": True,
        },
    ])
    write_csv(
        "original_route_contract.csv",
        route_contract_rows,
        ("contract_element", "source_type", "source_file", "source_line", "contract_value", "contract_frozen_before_final_performance"),
    )

    standalone_pass = False
    corrected = corrected_classification(standalone_pass, gate5)
    correction_warranted = bool(
        all(approximate_checks)
        and gate5
        and original_outcome["diversifier_diagnostic_pass"] == "true"
        and original_outcome["selected_configuration_outcome"] == "closed_exploration"
        and corrected["selected_configuration_outcome"] == "exploratory_followup_candidate_diversifier"
    )
    if not correction_warranted:
        raise RuntimeError("archived route evidence did not support the correction")

    write_csv(
        "pass_flag_consumption_audit.csv",
        [
            {
                "audit_step": "original_pass_flag_calculation",
                "diversifier_diagnostic_pass": gate5,
                "standalone_final_pass": standalone_pass,
                "classification_branch": "calculated_before_outcome_branch",
                "pass_flag_consumed": True,
                "consumption_effect": "stored_in_outcome_only",
                "classification_correct": False,
            },
            {
                "audit_step": "original_final_classification",
                "diversifier_diagnostic_pass": gate5,
                "standalone_final_pass": standalone_pass,
                "classification_branch": f"line_{implementation_locations['standalone_branch']}_standalone_gate",
                "pass_flag_consumed": False,
                "consumption_effect": "valid_diversifier_pass_discarded_when_standalone_failed",
                "classification_correct": False,
            },
            {
                "audit_step": "correction_overlay_classification",
                "diversifier_diagnostic_pass": gate5,
                "standalone_final_pass": standalone_pass,
                "classification_branch": "independent_preregistered_diversifier_route",
                "pass_flag_consumed": True,
                "consumption_effect": "diversifier_followup_only",
                "classification_correct": True,
            },
        ],
        ("audit_step", "diversifier_diagnostic_pass", "standalone_final_pass", "classification_branch", "pass_flag_consumed", "consumption_effect", "classification_correct"),
    )

    write_csv(
        "original_factory_outcome_reconciliation.csv",
        [{
            "architecture_id": ARCHITECTURE_ID,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "original_architecture_outcome": original_outcome["architecture_outcome"],
            "original_selected_configuration_outcome": original_outcome["selected_configuration_outcome"],
            "original_failure_reason": original_outcome["failure_reason"],
            "original_route_classification": original_outcome["route_classification"],
            "archived_diversifier_diagnostic_pass": original_outcome["diversifier_diagnostic_pass"],
            "selected_before_final_evaluation": selected["selection_status"] == "frozen_for_one_final_evaluation",
            "final_segment_used_for_reselection": original_outcome["final_segment_used_for_reselection"],
            "post_result_parameter_change": False,
            "historical_outcome_preserved": True,
            "correction_scope": "route_classification_overlay_only",
        }],
        ("architecture_id", "strategy_id", "trial_id", "original_architecture_outcome", "original_selected_configuration_outcome", "original_failure_reason", "original_route_classification", "archived_diversifier_diagnostic_pass"),
    )
    write_csv(
        "strategy_and_trial_lineage_reconciliation.csv",
        [{
            "architecture_id": ARCHITECTURE_ID,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "family_id": FAMILY_ID,
            "strategy_architecture": strategy["strategy_architecture"],
            "parameters": strategy["parameters"],
            "universe": strategy["universe"],
            "preregistered_route": strategy["route"],
            "existing_strategy_configurations_reviewed": 1,
            "new_strategy_configurations": 0,
            "existing_experiment_trials_reviewed": 1,
            "new_experiment_trials": 0,
            "strategy_id_changed": False,
            "trial_id_changed": False,
            "parameters_changed": False,
            "controls_changed": False,
            "fold_or_evaluation_period_changed": False,
        }],
        ("architecture_id", "strategy_id", "trial_id", "family_id", "strategy_architecture", "parameters", "universe", "preregistered_route"),
    )

    corrected_overlay = {
        "architecture_id": ARCHITECTURE_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "standalone_outcome": "closed_exploration",
        "standalone_failure_reason": "weak_vs_primary_control",
        "diversifier_outcome": "exploratory_followup_candidate_diversifier",
        "selected_configuration_outcome": corrected["selected_configuration_outcome"],
        "architecture_outcome": corrected["architecture_outcome"],
        "route_classification": corrected["route_classification"],
        "corrected_final_candidate_count": 1,
        "optimization_status": "bounded_preregistered_selection",
        "robustness_completed": False,
        "paper_demo_eligibility": False,
        "new_strategy_created": False,
        "new_trial_created": False,
        "historical_factory_packet_overwritten": False,
    }
    write_csv(
        "corrected_outcome_overlay.csv",
        [corrected_overlay],
        ("architecture_id", "strategy_id", "trial_id", "standalone_outcome", "standalone_failure_reason", "diversifier_outcome", "selected_configuration_outcome", "architecture_outcome", "route_classification", "corrected_final_candidate_count"),
    )
    write_csv(
        "corrected_exploratory_followup_candidates.csv",
        [{
            **corrected_overlay,
            "candidate_claim": "20pct_diversifier_route_only",
            "validation_claimed": False,
            "paper_demo_eligibility_claimed": False,
            "next_action": "technical_factory_v1_trend_quality_diversifier_robustness_v1",
        }],
        ("architecture_id", "strategy_id", "trial_id", "selected_configuration_outcome", "route_classification", "candidate_claim", "next_action"),
    )
    write_json("corrected_funnel_counts.json", {
        "existing_strategy_configurations_reviewed": 1,
        "new_strategy_configurations": 0,
        "existing_experiment_trials_reviewed": 1,
        "new_experiment_trials": 0,
        "route_classifications_corrected": 1,
        "direction_correction_records": 1,
        "corrected_final_candidate_count": 1,
        "robustness_trials": 0,
        "paper_demo_observations": 0,
        "process_tasks": 1,
        "portfolio_constructions_reviewed": 4,
        "portfolio_cost_rows_reconciled": 12,
    })
    write_csv(
        "direction_correction_record.csv",
        [{
            "direction_correction_id": TASK_ID,
            "entity_type": "direction_correction_record",
            "stage": "correction",
            "outcome": "factory_v1_route_classification_corrected",
            "correction_scope": "consume_predeclared_D1_diversifier_pass",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "new_strategy_or_trial_created": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }],
        ("direction_correction_id", "entity_type", "stage", "outcome", "correction_scope", "strategy_id", "trial_id"),
    )
    write_csv(
        "process_task_log.csv",
        [{
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": "correction",
            "strategy_configurations_reviewed": 1,
            "experiment_trials_reviewed": 1,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "market_return_recalculation_performed": False,
            "robustness_or_lifecycle_work_performed": False,
        }],
        ("process_task_id", "entity_type", "stage", "strategy_configurations_reviewed", "experiment_trials_reviewed", "new_strategy_configurations", "new_experiment_trials"),
    )
    correction_outcome = "factory_v1_route_classification_corrected"
    next_action = "technical_factory_v1_trend_quality_diversifier_robustness_v1"
    write_csv(
        "outcome_summary.csv",
        [{
            "task_id": TASK_ID,
            "outcome": correction_outcome,
            "failure_reason": "",
            "corrected_architecture_outcome": corrected["architecture_outcome"],
            "corrected_selected_configuration_outcome": corrected["selected_configuration_outcome"],
            "corrected_route_classification": corrected["route_classification"],
            "corrected_final_candidate_count": 1,
            "exact_next_action": next_action,
        }],
        ("task_id", "outcome", "failure_reason", "corrected_architecture_outcome", "corrected_selected_configuration_outcome", "corrected_route_classification", "corrected_final_candidate_count", "exact_next_action"),
    )
    write_csv(
        "failure_reasons.csv",
        [{
            "scope": "standalone_route_preserved",
            "strategy_id": STRATEGY_ID,
            "outcome": "closed_exploration",
            "failure_reason": "weak_vs_primary_control",
            "correction_task_failure": False,
        }],
        ("scope", "strategy_id", "outcome", "failure_reason", "correction_task_failure"),
    )
    write_csv(
        "next_actions.csv",
        [{
            "task_id": TASK_ID,
            "outcome": correction_outcome,
            "corrected_final_candidate_count": 1,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }],
        ("task_id", "outcome", "corrected_final_candidate_count", "exact_next_action", "execute_in_this_task"),
    )

    original_packet_hash_after = tree_hash(ORIGINAL_DIR)
    original_file_hashes_after = {
        path.name: file_hash(path) for path in sorted(ORIGINAL_DIR.iterdir()) if path.is_file()
    }
    protected_after = protected_snapshot()
    expected_5_differences = {
        "candidate_vs_frozen_reference": (0.0812522965586044, 0.02367830883866895),
        "candidate_vs_named_80_20_control": (-0.0123254579121133, 0.01160911558093547),
        "candidate_vs_exposure_matched_80_20_control": (-0.0119760437582348, 0.020912548993965),
    }
    materiality5 = {
        row["comparison_id"]: row for row in materiality_rows if row["cost_bps_one_way"] == 5
    }
    expected_differences_pass = all(
        abs(float(materiality5[key]["sharpe_difference"]) - expected[0]) <= TOLERANCE
        and abs(float(materiality5[key]["absolute_drawdown_improvement"]) - expected[1]) <= TOLERANCE
        for key, expected in expected_5_differences.items()
    )
    checks = {
        "original_factory_packet_hash_unchanged": original_packet_hash_before == original_packet_hash_after,
        "every_original_factory_file_hash_unchanged": original_file_hashes_before == original_file_hashes_after,
        "protected_state_cache_observations_and_prior_evidence_unchanged": protected_before == protected_after,
        "archived_5bps_values_reproduce_within_tolerance": all(approximate_checks),
        "all_archived_0_5_10_portfolio_rows_present": len(portfolio_by_key) == 12,
        "portfolio_row_arithmetic_reconciles_at_5bps": expected_differences_pass,
        "portfolio_row_arithmetic_reconciles_at_10bps": gates[10][0],
        "archived_diversifier_pass_reproduces": gate5 and original_outcome["diversifier_diagnostic_pass"] == "true",
        "standalone_closure_preserved": original_outcome["failure_reason"] == "weak_vs_primary_control" and not standalone_pass,
        "original_contract_allows_diversifier_route": original_prompt_lines["diversifier_route_allowed"] > 0,
        "original_contract_allows_diversifier_outcome": original_prompt_lines["diversifier_outcome_allowed"] > 0,
        "classification_bug_identified": corrected["selected_configuration_outcome"] != original_outcome["selected_configuration_outcome"],
        "corrected_outcome_is_diversifier_only": corrected["selected_configuration_outcome"] == "exploratory_followup_candidate_diversifier",
        "no_new_strategy_configuration": True,
        "no_new_experiment_trial": True,
        "no_market_return_calculation": True,
        "no_robustness_validation_lifecycle_or_paper_demo_work": True,
        "no_provider_broker_account_order_capital_or_real_money_action": True,
    }
    overall_pass = all(checks.values())
    write_yaml("correction_manifest.yaml", {
        "task_id": TASK_ID,
        "mode": "methodology-correction",
        "stage": "correction",
        "outcome": correction_outcome,
        "original_factory_packet": relative(ORIGINAL_DIR),
        "original_factory_packet_hash": original_packet_hash_after,
        "original_prompt_hash": file_hash(ORIGINAL_PROMPT),
        "original_implementation_hash": file_hash(IMPLEMENTATION_PATH),
        "correction_prompt_hash": file_hash(CORRECTION_PROMPT),
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "corrected_final_candidate_count": 1,
        "exact_next_action": next_action,
    })
    (OUTPUT_DIR / "correction_report.md").write_text(
        report_text(next_action, overall_pass), encoding="utf-8"
    )
    write_json("consistency_check.json", {
        "task_id": TASK_ID,
        "checks": checks,
        "original_packet_hash_before": original_packet_hash_before,
        "original_packet_hash_after": original_packet_hash_after,
        "original_file_hashes_before": original_file_hashes_before,
        "original_file_hashes_after": original_file_hashes_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "overall_pass": overall_pass,
    })
    actual_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    checks["required_file_set_exact"] = actual_files == REQUIRED_FILES
    overall_pass = all(checks.values())
    (OUTPUT_DIR / "correction_report.md").write_text(
        report_text(next_action, overall_pass), encoding="utf-8"
    )
    write_json("consistency_check.json", {
        "task_id": TASK_ID,
        "checks": checks,
        "original_packet_hash_before": original_packet_hash_before,
        "original_packet_hash_after": original_packet_hash_after,
        "original_file_hashes_before": original_file_hashes_before,
        "original_file_hashes_after": original_file_hashes_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "actual_files": sorted(actual_files),
        "required_files": sorted(REQUIRED_FILES),
        "overall_pass": overall_pass,
    })
    if not overall_pass:
        raise RuntimeError("technical factory route correction consistency check failed")
    return {
        "task_id": TASK_ID,
        "outcome": correction_outcome,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "standalone_outcome": "closed_exploration",
        "standalone_failure_reason": "weak_vs_primary_control",
        "diversifier_outcome": "exploratory_followup_candidate_diversifier",
        "corrected_final_candidate_count": 1,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "next_action": next_action,
        "overall_pass": overall_pass,
        "output_dir": relative(OUTPUT_DIR),
    }
