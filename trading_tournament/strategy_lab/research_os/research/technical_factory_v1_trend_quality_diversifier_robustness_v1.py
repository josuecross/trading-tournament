from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import technical_strategy_factory_v1 as factory
from strategy_lab.research_os.research import (
    correct_technical_factory_v1_route_classification_v1 as correction,
)


TASK_ID = "technical_factory_v1_trend_quality_diversifier_robustness_v1"
MODE = "bounded-historical-robustness"
STAGE = "robustness"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
FACTORY_DIR = ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v1" / "latest"
CORRECTION_DIR = ROOT / "evidence" / "technical_factory" / "correct_technical_factory_v1_route_classification_v1" / "latest"
SOURCE_PROMPT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\18965c7d-4365-4e49-813d-c7a120a4a9ec\pasted-text.txt"
)

STRATEGY_ID = "factory_v1_spy_trend_quality_state_d1"
PARENT_TRIAL_ID = "technical_factory_v1__d1__canonical"
TRIAL_ID = "technical_factory_v1_trend_quality_diversifier_robustness_v1__child"
FAMILY_ID = "regression_trend_quality"
ARCHITECTURE_ID = "factory_v1_spy_trend_quality_state"
DISPLAY_NAME = "SPY Regression Trend-Quality State D1"
STRATEGY_ARCHITECTURE = "long_only_log_price_regression_slope_and_r2_state"
RESEARCH_LINEAGE = "internal_technical_strategy_factory_v1:factory_v1_spy_trend_quality_state"

REFERENCE_ID = "100pct_frozen_reference"
CANDIDATE_ID = "80pct_reference_20pct_D1_candidate"
NAMED_ID = "80pct_reference_20pct_named_same_purpose_control"
STATIC_ID = "80pct_reference_20pct_exposure_or_static_control"
ENDPOINT_ID = "80pct_reference_20pct_same_lookback_endpoint_return_state"
SPY_ID = "80pct_reference_20pct_SPY_buy_and_hold"
BIL_ID = "80pct_reference_20pct_BIL"
PORTFOLIO_IDS = (REFERENCE_ID, CANDIDATE_ID, NAMED_ID, STATIC_ID, ENDPOINT_ID, SPY_ID, BIL_ID)
CRITICAL_IDS = (NAMED_ID, STATIC_ID)

NAMED_INNER = "same_regression_slope_without_path_quality_filter"
STATIC_INNER = "full_period_exposure_matched_static_spy_bil"
ENDPOINT_INNER = "same_lookback_endpoint_return_positive_state"
SPY_INNER = "SPY_buy_and_hold"
BIL_INNER = "BIL_buy_and_hold"
STATIC_SPY_WEIGHT = 0.5391032325338895
STATIC_BIL_WEIGHT = 0.4608967674661105

COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
PRIMARY_COST = 5.0
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260804
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-10

DEVELOPMENT_START = pd.Timestamp("2007-11-16")
DEVELOPMENT_END = pd.Timestamp("2022-09-23")
FINAL_START = pd.Timestamp("2022-09-26")
FINAL_END = pd.Timestamp("2026-06-18")

REQUIRED_FILES = {
    "robustness_manifest.yaml",
    "strategy_and_trial_lineage.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "parent_reproduction_check.csv",
    "portfolio_definition_reconciliation.csv",
    "full_period_portfolio_results.csv",
    "factory_fold_portfolio_results.csv",
    "development_final_segment_results.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "path_quality_filter_episode_inventory.csv",
    "path_quality_filter_episode_attribution.csv",
    "leave_one_filter_episode_out_results.csv",
    "leave_one_filter_episode_out_summary.csv",
    "reference_negative_month_results.csv",
    "reference_drawdown_episode_results.csv",
    "monthly_excess_concentration.csv",
    "neutralization_results.csv",
    "paired_block_bootstrap_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "robustness_report.md",
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
    snapshot["evidence_excluding_current_robustness"] = tree_hash(ROOT / "evidence", OUTPUT_DIR)
    snapshot["technical_factory_v1_packet"] = tree_hash(FACTORY_DIR)
    snapshot["route_correction_packet"] = tree_hash(CORRECTION_DIR)
    return snapshot


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected output {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
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
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def one(rows: list[dict[str, str]], **matches: str) -> dict[str, str]:
    selected = [row for row in rows if all(row.get(key, "") == value for key, value in matches.items())]
    if len(selected) != 1:
        raise RuntimeError(f"expected one row for {matches}, found {len(selected)}")
    return selected[0]


def factory_spec() -> factory.VariantSpec:
    matches = [spec for spec in factory.VARIANTS if spec.strategy_id == STRATEGY_ID]
    if len(matches) != 1:
        raise RuntimeError("frozen D1 specification is unavailable")
    return matches[0]


def verify_parent_contract() -> bool:
    factory_check = json.loads((FACTORY_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    correction_check = json.loads((CORRECTION_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    overlay = one(read_csv(CORRECTION_DIR / "corrected_outcome_overlay.csv"), strategy_id=STRATEGY_ID)
    selection = one(read_csv(FACTORY_DIR / "selected_variant_freeze.csv"), architecture_id=ARCHITECTURE_ID)
    spec = factory_spec()
    return bool(
        factory_check.get("overall_pass")
        and correction_check.get("overall_pass")
        and overlay["selected_configuration_outcome"] == "exploratory_followup_candidate_diversifier"
        and overlay["standalone_outcome"] == "closed_exploration"
        and overlay["standalone_failure_reason"] == "weak_vs_primary_control"
        and selection["selected_strategy_id"] == STRATEGY_ID
        and selection["selection_used_final_segment"] == "false"
        and spec.parameters == {"lookback_sessions": 60, "r2_threshold": 0.25}
    )


def prepare_inputs() -> tuple[dict[str, Any], pd.Series, pd.DatetimeIndex, list[dict[str, Any]]]:
    preflight_rows, frames, passed = factory.preflight()
    if not passed:
        raise RuntimeError("canonical SPY/BIL preflight failed")
    prepared = factory.prepare_variant(factory_spec(), frames)
    reference = factory.portfolio_helpers.market.active_vm_dsr_usci_reference_returns().dropna()
    index = reference.index.intersection(prepared["prices"].index).sort_values()
    index = index[index <= FINAL_END]
    relevant_preflight = [row for row in preflight_rows if row["symbol"] in {"SPY", "BIL"}]
    return prepared, reference, index, relevant_preflight


def preregistration_rows(common_index: pd.DatetimeIndex) -> dict[str, list[dict[str, Any]]]:
    lineage = [{
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": STRATEGY_ARCHITECTURE,
        "source_or_research_lineage": RESEARCH_LINEAGE,
        "lineage_type": "internally_generated_technical_hypothesis",
        "optimization": "bounded_preregistered_parameter_search",
        "route": "20pct_diversifier_only",
        "external_source_claimed": False,
        "existing_strategy_configuration_carried_forward": True,
        "new_strategy_configuration": False,
        "standalone_outcome_preserved": "closed_exploration",
        "standalone_failure_reason_preserved": "weak_vs_primary_control",
    }]
    trial = [{
        "trial_id": TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "robustness_variant",
        "changed_fields_from_parent": "evaluation_route_and_robustness_diagnostics_only",
        "formula_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "cost_model_changed": False,
        "execution_changed": False,
        "reference_changed": False,
        "sleeve_weight_changed": False,
        "controls_changed": False,
        "optimization_repeated": False,
        "grid_reopened": False,
        "unselected_variants_evaluated_on_final_segment": False,
        "independent_validation_claimed": False,
        "outcome": "preregistered_pending_robustness_execution",
    }]
    benchmarks = [
        (NAMED_ID, "same_regression_slope_without_path_quality_filter", True, False),
        (STATIC_ID, f"monthly_static_SPY_{STATIC_SPY_WEIGHT}_BIL_{STATIC_BIL_WEIGHT}", False, True),
        (ENDPOINT_ID, "same_60_session_endpoint_return_positive_state", False, False),
        (SPY_ID, "SPY_buy_and_hold", False, False),
        (BIL_ID, "BIL_buy_and_hold", False, False),
        (REFERENCE_ID, "frozen_current_active_vm_dsr_usci_combo", False, False),
    ]
    benchmark_rows = [{
        "benchmark_reference_id": portfolio_id,
        "entity_type": "benchmark_reference",
        "stage": "benchmark_reference_only",
        "definition": definition,
        "critical_control": critical,
        "exposure_control": exposure,
        "carried_forward_or_predeclared": True,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    } for portfolio_id, definition, critical, exposure in benchmarks]
    process = [{
        "process_task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "existing_strategy_configurations": 1,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 1,
        "new_robustness_trials": 1,
        "paper_demo_observations": 0,
        "validation_observations": 0,
        "data_capability_tasks": 0,
    }]
    portfolio_definition = [{
        "portfolio_id": CANDIDATE_ID,
        "reference_weight": 0.8,
        "sleeve_weight": 0.2,
        "outer_rebalance": "monthly_following_session_close",
        "explicit_holdings": True,
        "natural_drift": True,
        "fixed_weight_daily_return_blend": False,
        "inner_and_outer_turnover_separate": True,
        "transaction_costs_charged_once": True,
        "common_period_start_frozen_before_performance": common_index[0].date().isoformat(),
        "common_period_end_frozen_before_performance": common_index[-1].date().isoformat(),
        "candidate_lookback_sessions": 60,
        "candidate_r_squared_threshold": 0.25,
        "candidate_execution": "completed_close_signal_following_regular_session_close",
        "exposure_control_SPY_weight": STATIC_SPY_WEIGHT,
        "exposure_control_BIL_weight": STATIC_BIL_WEIGHT,
        "exposure_weight_recalculated": False,
    }]
    return {
        "strategy_and_trial_lineage.csv": lineage,
        "trial_ledger.csv": trial,
        "benchmark_reference_log.csv": benchmark_rows,
        "process_task_log.csv": process,
        "portfolio_definition_reconciliation.csv": portfolio_definition,
    }


def write_preregistration(common_index: pd.DatetimeIndex) -> dict[str, str]:
    rows = preregistration_rows(common_index)
    write_csv("strategy_and_trial_lineage.csv", rows["strategy_and_trial_lineage.csv"], ("strategy_id", "parent_trial_id", "robustness_trial_id", "family_id", "architecture_id", "route"))
    write_csv("trial_ledger.csv", rows["trial_ledger.csv"], ("trial_id", "entity_type", "stage", "strategy_id", "parent_trial_id", "adaptation_label", "changed_fields_from_parent"))
    write_csv("benchmark_reference_log.csv", rows["benchmark_reference_log.csv"], ("benchmark_reference_id", "entity_type", "stage", "definition", "critical_control", "exposure_control"))
    write_csv("process_task_log.csv", rows["process_task_log.csv"], ("process_task_id", "entity_type", "stage"))
    write_csv("portfolio_definition_reconciliation.csv", rows["portfolio_definition_reconciliation.csv"], ("portfolio_id", "reference_weight", "sleeve_weight", "outer_rebalance"))
    return {name: file_hash(OUTPUT_DIR / name) for name in rows}


def simulate_inner_paths(prepared: dict[str, Any]) -> dict[tuple[str, float], dict[str, Any]]:
    mapping = {
        "candidate": prepared["candidate_events"],
        "named": prepared["control_events"][NAMED_INNER],
        "static": prepared["control_events"][STATIC_INNER],
        "endpoint": prepared["control_events"][ENDPOINT_INNER],
        "SPY": prepared["control_events"][SPY_INNER],
        "BIL": prepared["control_events"][BIL_INNER],
    }
    timing = "completed_signal_session_target_applied_at_following_regular_session_close"
    return {
        (inner_id, cost): factory.accounting.simulate_path(prepared["prices"], events, cost, timing)
        for cost in COSTS
        for inner_id, events in mapping.items()
    }


def build_portfolio_paths(
    reference: pd.Series,
    index: pd.DatetimeIndex,
    inner_paths: dict[tuple[str, float], dict[str, Any]],
) -> dict[tuple[str, float], dict[str, Any]]:
    mapping = {
        CANDIDATE_ID: "candidate",
        NAMED_ID: "named",
        STATIC_ID: "static",
        ENDPOINT_ID: "endpoint",
        SPY_ID: "SPY",
        BIL_ID: "BIL",
    }
    aligned_reference = reference.reindex(index).dropna()
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        reference_path = factory.portfolio_helpers.reference_path(aligned_reference)
        reference_path["inner_path"] = None
        paths[(REFERENCE_ID, cost)] = reference_path
        for portfolio_id, inner_id in mapping.items():
            inner = inner_paths[(inner_id, cost)]
            outer = factory.portfolio_helpers.path_from_two_sleeves(aligned_reference, inner, cost)
            outer["inner_path"] = inner
            paths[(portfolio_id, cost)] = outer
    return paths


def portfolio_metrics(path: dict[str, Any], period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    index = path["returns"].index if period is None else path["returns"].index.intersection(period)
    values = factory.portfolio_helpers.period_metrics(path, "reference", index)
    inner = path.get("inner_path")
    inner_turnover = 0.0 if inner is None else float(inner["turnover"].reindex(index).fillna(0.0).sum())
    inner_cost = float(path.get("inner_cost_drag_contribution", pd.Series(dtype=float)).reindex(index).fillna(0.0).sum())
    outer_turnover = float(path["turnover"].reindex(index).fillna(0.0).sum())
    outer_cost = float(path["cost"].reindex(index).fillna(0.0).sum())
    values.update({
        "inner_turnover": inner_turnover,
        "outer_turnover": outer_turnover,
        "inner_transaction_cost_drag": inner_cost,
        "outer_transaction_cost_drag": outer_cost,
        "total_transaction_cost_drag": inner_cost + outer_cost,
    })
    return values


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    metrics = ("cagr", "sharpe_ratio", "maximum_drawdown")
    return bool(
        all(float(control[key]) >= float(candidate[key]) - 1e-12 for key in metrics)
        and any(float(control[key]) > float(candidate[key]) + 1e-12 for key in metrics)
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"])
    )


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def route_gate(candidate: dict[str, Any], reference: dict[str, Any], named: dict[str, Any], static: dict[str, Any]) -> bool:
    return bool(
        material_advantage(candidate, reference)
        and not dominates(named, candidate)
        and not dominates(static, candidate)
        and material_advantage(candidate, named)
        and material_advantage(candidate, static)
    )


def result_row(portfolio_id: str, cost: float, period_id: str, diagnostic: str, values: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "entity_type": "portfolio_robustness_diagnostic",
        "stage": STAGE,
        "approved_route": "20pct_diversifier_only",
        "portfolio_id": portfolio_id,
        "cost_bps_one_way": cost,
        "period_id": period_id,
        "diagnostic_type": diagnostic,
        "independent_validation_claimed": False,
        **values,
    }


def monthly_returns(series: pd.Series) -> pd.Series:
    return (1.0 + series).groupby(series.index.to_period("M")).prod().sub(1.0)


def monthly_metrics(series: pd.Series) -> dict[str, Any]:
    values = series.to_numpy(dtype=float)
    wealth = np.cumprod(1.0 + values)
    standard_deviation = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return {
        "evaluation_start": str(series.index[0]),
        "evaluation_end": str(series.index[-1]),
        "monthly_observations": len(values),
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(values)) - 1.0),
        "annualized_volatility": standard_deviation * math.sqrt(12.0),
        "sharpe_ratio": float(np.mean(values) / standard_deviation * math.sqrt(12.0)) if standard_deviation > 0.0 else 0.0,
        "maximum_drawdown": float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)),
    }


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_quarter_{position + 1}": index[positions]
        for position, positions in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def parent_reproduction_rows(
    inner_paths: dict[tuple[str, float], dict[str, Any]],
    paths: dict[tuple[str, float], dict[str, Any]],
    final_index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], bool]:
    archived_standalone = read_csv(FACTORY_DIR / "final_evaluation_results.csv")
    archived_portfolios = read_csv(FACTORY_DIR / "portfolio_contribution_results.csv")
    archived_controls = read_csv(FACTORY_DIR / "final_control_results.csv")
    correction_materiality = read_csv(CORRECTION_DIR / "portfolio_materiality_reconciliation.csv")
    rows: list[dict[str, Any]] = []
    reproduced_portfolio: dict[tuple[str, float], dict[str, Any]] = {}
    archived_mapping = {
        REFERENCE_ID: REFERENCE_ID,
        CANDIDATE_ID: "80pct_reference_20pct_candidate",
        NAMED_ID: NAMED_ID,
        STATIC_ID: STATIC_ID,
    }
    for cost in (0.0, 5.0, 10.0):
        current_standalone = factory.path_metrics(inner_paths[("candidate", cost)], "BIL", final_index)
        archived_standalone_row = one(
            archived_standalone,
            strategy_id=STRATEGY_ID,
            cost_bps_one_way=str(cost),
        )
        for metric in ("cagr", "sharpe_ratio", "maximum_drawdown"):
            difference = float(current_standalone[metric]) - float(archived_standalone_row[metric])
            rows.append({
                "reproduction_scope": "D1_standalone_final_segment",
                "series_id": STRATEGY_ID,
                "cost_bps_one_way": cost,
                "metric": metric,
                "archived_value": archived_standalone_row[metric],
                "reproduced_value": current_standalone[metric],
                "difference": difference,
                "tolerance": REPRODUCTION_TOLERANCE,
                "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
            })
        for portfolio_id, archived_id in archived_mapping.items():
            current = portfolio_metrics(paths[(portfolio_id, cost)], final_index)
            reproduced_portfolio[(portfolio_id, cost)] = current
            archived = one(
                archived_portfolios,
                strategy_id=STRATEGY_ID,
                construction_id=archived_id,
                cost_bps_one_way=str(cost),
            )
            for metric in ("cagr", "sharpe_ratio", "maximum_drawdown"):
                difference = float(current[metric]) - float(archived[metric])
                rows.append({
                    "reproduction_scope": "portfolio_final_segment",
                    "series_id": portfolio_id,
                    "cost_bps_one_way": cost,
                    "metric": metric,
                    "archived_value": archived[metric],
                    "reproduced_value": current[metric],
                    "difference": difference,
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
                })
        for control_id, inner_id in ((NAMED_INNER, "named"), (STATIC_INNER, "static")):
            current = factory.path_metrics(inner_paths[(inner_id, cost)], "BIL", final_index)
            archived = one(
                archived_controls,
                strategy_id=STRATEGY_ID,
                series_id=control_id,
                cost_bps_one_way=str(cost),
            )
            for metric in ("cagr", "sharpe_ratio", "maximum_drawdown"):
                difference = float(current[metric]) - float(archived[metric])
                rows.append({
                    "reproduction_scope": "standalone_control_final_segment",
                    "series_id": control_id,
                    "cost_bps_one_way": cost,
                    "metric": metric,
                    "archived_value": archived[metric],
                    "reproduced_value": current[metric],
                    "difference": difference,
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
                })
    for cost in (5.0, 10.0):
        current_gate = route_gate(
            reproduced_portfolio[(CANDIDATE_ID, cost)],
            reproduced_portfolio[(REFERENCE_ID, cost)],
            reproduced_portfolio[(NAMED_ID, cost)],
            reproduced_portfolio[(STATIC_ID, cost)],
        )
        archived_rows = [
            row for row in correction_materiality if float(row["cost_bps_one_way"]) == cost
        ]
        archived_gate = bool(
            len(archived_rows) == 3
            and all(row["materiality_status"] == "pass" for row in archived_rows)
            and all(row["control_dominates_candidate"] == "false" for row in archived_rows[1:])
        )
        rows.append({
            "reproduction_scope": "corrected_route_pass_boolean",
            "series_id": CANDIDATE_ID,
            "cost_bps_one_way": cost,
            "metric": "diversifier_route_pass",
            "archived_value": archived_gate,
            "reproduced_value": current_gate,
            "difference": "",
            "tolerance": "exact_boolean",
            "pass": current_gate == archived_gate,
        })
    return rows, bool(rows and all(row["pass"] for row in rows))


def factory_periods(index: pd.DatetimeIndex) -> tuple[dict[str, pd.DatetimeIndex], list[dict[str, Any]]]:
    archived = read_csv(FACTORY_DIR / "walk_forward_folds.csv")
    rows = [row for row in archived if row["architecture_id"] == ARCHITECTURE_ID]
    periods: dict[str, pd.DatetimeIndex] = {}
    reconciliation: list[dict[str, Any]] = []
    for row in rows:
        period_id = row["period_id"]
        start = pd.Timestamp(row["evaluation_start"])
        end = pd.Timestamp(row["evaluation_end"])
        period = index[(index >= start) & (index <= end)]
        periods[period_id] = period
        reconciliation.append({
            "period_id": period_id,
            "archived_start": row["evaluation_start"],
            "archived_end": row["evaluation_end"],
            "common_intersection_start": "" if not len(period) else period[0].date().isoformat(),
            "common_intersection_end": "" if not len(period) else period[-1].date().isoformat(),
            "used_for_original_selection": row["used_for_variant_selection"],
            "unselected_variant_access": False,
        })
    periods["development_selection_period_intersection"] = index[
        (index >= DEVELOPMENT_START) & (index <= DEVELOPMENT_END)
    ]
    periods["factory_final_evaluation_segment"] = index[
        (index >= FINAL_START) & (index <= FINAL_END)
    ]
    return periods, reconciliation


def period_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    periods: dict[str, pd.DatetimeIndex],
    period_ids: Iterable[str],
    diagnostic: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period_id in period_ids:
        period = periods[period_id]
        for portfolio_id in PORTFOLIO_IDS:
            rows.append(result_row(
                portfolio_id,
                PRIMARY_COST,
                period_id,
                diagnostic,
                portfolio_metrics(paths[(portfolio_id, PRIMARY_COST)], period),
            ))
    return rows


def rolling_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
    months: int,
) -> list[dict[str, Any]]:
    month_ends = [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]
    rows: list[dict[str, Any]] = []
    sequence = 0
    for end in month_ends:
        boundary = end - pd.DateOffset(months=months)
        if boundary < index[0]:
            continue
        period = index[(index > boundary) & (index <= end)]
        if not len(period):
            continue
        sequence += 1
        candidate = portfolio_metrics(paths[(CANDIDATE_ID, PRIMARY_COST)], period)
        for comparator_id in (REFERENCE_ID, NAMED_ID, STATIC_ID):
            control = portfolio_metrics(paths[(comparator_id, PRIMARY_COST)], period)
            rows.append({
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "window_months": months,
                "window_sequence": sequence,
                "window_start": period[0].date().isoformat(),
                "window_end": period[-1].date().isoformat(),
                "candidate_portfolio_id": CANDIDATE_ID,
                "comparison_portfolio_id": comparator_id,
                "candidate_cagr": candidate["cagr"],
                "comparison_cagr": control["cagr"],
                "cagr_difference": float(candidate["cagr"]) - float(control["cagr"]),
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "comparison_sharpe_ratio": control["sharpe_ratio"],
                "sharpe_difference": float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]),
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "comparison_maximum_drawdown": control["maximum_drawdown"],
                "drawdown_difference": float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]),
                "comparison_dominates_candidate": dominates(control, candidate),
                "materiality_status": "pass" if material_advantage(candidate, control) else "fail",
                "candidate_improves_sharpe_or_drawdown": bool(
                    float(candidate["sharpe_ratio"]) > float(control["sharpe_ratio"])
                    or float(candidate["maximum_drawdown"]) > float(control["maximum_drawdown"])
                ),
                "unfavorable_window_retained": True,
                "independent_validation_claimed": False,
            })
    return rows


def rolling_summary(rows36: list[dict[str, Any]], rows60: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for months, source in ((36, rows36), (60, rows60)):
        for comparator in (REFERENCE_ID, NAMED_ID, STATIC_ID):
            subset = [row for row in source if row["comparison_portfolio_id"] == comparator]
            result.append({
                "window_months": months,
                "comparison_portfolio_id": comparator,
                "eligible_window_count": len(subset),
                "median_cagr_difference": float(np.median([row["cagr_difference"] for row in subset])),
                "median_sharpe_difference": float(np.median([row["sharpe_difference"] for row in subset])),
                "median_drawdown_difference": float(np.median([row["drawdown_difference"] for row in subset])),
                "candidate_improves_fraction": float(np.mean([row["candidate_improves_sharpe_or_drawdown"] for row in subset])),
                "comparison_dominates_fraction": float(np.mean([row["comparison_dominates_candidate"] for row in subset])),
                "unfavorable_windows_retained": True,
            })
    return result


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def path_quality_episodes(
    prepared: dict[str, Any],
    common_index: pd.DatetimeIndex,
    inner_paths: dict[tuple[str, float], dict[str, Any]],
    paths: dict[tuple[str, float], dict[str, Any]],
    reference: pd.Series,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full_index = prepared["prices"].index
    candidate_targets = target_history(prepared["candidate_events"], full_index)
    named_targets = target_history(prepared["control_events"][NAMED_INNER], full_index)
    diagnostics = prepared["diagnostics"].copy()
    diagnostics = diagnostics[diagnostics["execution_date"].astype(str).ne("")]
    r2_by_execution = pd.Series(
        diagnostics["r_squared"].to_numpy(dtype=float),
        index=pd.to_datetime(diagnostics["execution_date"]),
    ).groupby(level=0).last().reindex(full_index).ffill()
    condition_full = (
        (named_targets["SPY"] > 0.5)
        & (candidate_targets["BIL"] > 0.5)
        & (r2_by_execution < 0.25)
    )
    condition = condition_full.reindex(common_index).fillna(False)
    group_ids = condition.ne(condition.shift()).cumsum()
    inventory: list[dict[str, Any]] = []
    episode_objects: list[dict[str, Any]] = []
    candidate_portfolio = paths[(CANDIDATE_ID, PRIMARY_COST)]["returns"]
    named_portfolio = paths[(NAMED_ID, PRIMARY_COST)]["returns"]
    reference_returns = reference.reindex(common_index)
    price_returns = prepared["prices"].pct_change(fill_method=None)
    candidate_inner = inner_paths[("candidate", PRIMARY_COST)]["returns"]
    named_inner = inner_paths[("named", PRIMARY_COST)]["returns"]
    for sequence, group in enumerate(group_ids[condition].unique(), start=1):
        target_dates = condition.index[(group_ids == group) & condition]
        start = pd.Timestamp(target_dates[0])
        end = pd.Timestamp(target_dates[-1])
        end_position = common_index.searchsorted(end, side="right")
        return_end = common_index[end_position] if end_position < len(common_index) else end
        return_dates = common_index[(common_index > start) & (common_index <= return_end)]
        if not len(return_dates):
            continue
        episode_id = f"path_quality_filter_episode_{sequence:03d}"
        inventory.append({
            "episode_id": episode_id,
            "target_start_execution_date": start.date().isoformat(),
            "target_end_date": end.date().isoformat(),
            "return_start": return_dates[0].date().isoformat(),
            "return_end": return_dates[-1].date().isoformat(),
            "duration_sessions": len(return_dates),
            "candidate_target": "BIL",
            "slope_only_target": "SPY",
            "cause": "annualized_slope_positive_and_r_squared_below_0.25",
            "r_squared_minimum": float(r2_by_execution.reindex(target_dates).min()),
            "r_squared_maximum": float(r2_by_execution.reindex(target_dates).max()),
            "threshold_changed": False,
        })
        episode_objects.append({
            "episode_id": episode_id,
            "target_dates": target_dates,
            "return_dates": return_dates,
            **inventory[-1],
        })
    attribution: list[dict[str, Any]] = []
    contributions: list[float] = []
    for episode in episode_objects:
        dates = episode["return_dates"]
        difference = candidate_portfolio.reindex(dates) - named_portfolio.reindex(dates)
        ref = reference_returns.reindex(dates)
        contribution = float(difference.sum())
        contributions.append(contribution)
        attribution.append({
            "row_type": "episode",
            "episode_id": episode["episode_id"],
            "start": episode["return_start"],
            "end": episode["return_end"],
            "duration_sessions": episode["duration_sessions"],
            "SPY_return": float((1.0 + price_returns["SPY"].reindex(dates).fillna(0.0)).prod() - 1.0),
            "BIL_return": float((1.0 + price_returns["BIL"].reindex(dates).fillna(0.0)).prod() - 1.0),
            "D1_sleeve_return": float((1.0 + candidate_inner.reindex(dates).fillna(0.0)).prod() - 1.0),
            "slope_only_sleeve_return": float((1.0 + named_inner.reindex(dates).fillna(0.0)).prod() - 1.0),
            "candidate_minus_named_80_20_additive_contribution": contribution,
            "candidate_minus_named_80_20_compounded_return_difference": float(
                (1.0 + candidate_portfolio.reindex(dates)).prod()
                - (1.0 + named_portfolio.reindex(dates)).prod()
            ),
            "contribution_reference_positive_sessions": float(difference[ref > 0.0].sum()),
            "contribution_reference_negative_sessions": float(difference[ref < 0.0].sum()),
            "used_for_parameter_change": False,
        })
    positive = sorted((value for value in contributions if value > 0.0), reverse=True)
    total_positive = float(sum(positive))
    if attribution:
        attribution.append({
            "row_type": "summary",
            "episode_id": "all_path_quality_filter_episodes",
            "episode_count": len(attribution),
            "median_duration_sessions": float(np.median([row["duration_sessions"] for row in attribution])),
            "maximum_duration_sessions": int(max(row["duration_sessions"] for row in attribution)),
            "positive_contribution_count": sum(value > 0.0 for value in contributions),
            "negative_contribution_count": sum(value < 0.0 for value in contributions),
            "largest_positive_contribution": max(contributions),
            "largest_negative_contribution": min(contributions),
            "largest_episode_share_of_total_positive_contribution": positive[0] / total_positive if total_positive > 0.0 else 0.0,
            "three_largest_episodes_share_of_total_positive_contribution": sum(positive[:3]) / total_positive if total_positive > 0.0 else 0.0,
        })
    return inventory, attribution, episode_objects


def leave_one_episode_out(
    episodes: list[dict[str, Any]],
    prepared: dict[str, Any],
    reference: pd.Series,
    common_index: pd.DatetimeIndex,
    baseline_paths: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline = portfolio_metrics(baseline_paths[(CANDIDATE_ID, PRIMARY_COST)])
    reference_metrics = portfolio_metrics(baseline_paths[(REFERENCE_ID, PRIMARY_COST)])
    named_metrics = portfolio_metrics(baseline_paths[(NAMED_ID, PRIMARY_COST)])
    static_metrics = portfolio_metrics(baseline_paths[(STATIC_ID, PRIMARY_COST)])
    candidate_targets = target_history(prepared["candidate_events"], prepared["prices"].index)
    named_targets = target_history(prepared["control_events"][NAMED_INNER], prepared["prices"].index)
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        modified = candidate_targets.copy()
        modified.loc[episode["target_dates"], ["SPY", "BIL"]] = named_targets.loc[
            episode["target_dates"], ["SPY", "BIL"]
        ]
        inner = factory.accounting.simulate_path(
            prepared["prices"],
            modified,
            PRIMARY_COST,
            "completed_signal_session_target_applied_at_following_regular_session_close",
        )
        outer = factory.portfolio_helpers.path_from_two_sleeves(
            reference.reindex(common_index), inner, PRIMARY_COST
        )
        outer["inner_path"] = inner
        candidate = portfolio_metrics(outer)
        rows.append({
            "episode_id": episode["episode_id"],
            "episode_start": episode["target_start_execution_date"],
            "episode_end": episode["target_end_date"],
            "candidate_cagr": candidate["cagr"],
            "candidate_sharpe_ratio": candidate["sharpe_ratio"],
            "candidate_maximum_drawdown": candidate["maximum_drawdown"],
            "baseline_candidate_sharpe_ratio": baseline["sharpe_ratio"],
            "sharpe_change_vs_baseline": float(candidate["sharpe_ratio"]) - float(baseline["sharpe_ratio"]),
            "sharpe_difference_vs_reference": float(candidate["sharpe_ratio"]) - float(reference_metrics["sharpe_ratio"]),
            "drawdown_improvement_vs_reference": float(candidate["maximum_drawdown"]) - float(reference_metrics["maximum_drawdown"]),
            "still_improves_reference_sharpe_or_drawdown": bool(
                float(candidate["sharpe_ratio"]) > float(reference_metrics["sharpe_ratio"])
                or float(candidate["maximum_drawdown"]) > float(reference_metrics["maximum_drawdown"])
            ),
            "named_control_dominates": dominates(named_metrics, candidate),
            "exposure_control_dominates": dominates(static_metrics, candidate),
            "all_other_signals_targets_and_execution_preserved": True,
            "outer_portfolio_rebuilt": True,
            "cost_model_preserved": True,
            "combinations_of_episodes_removed": False,
        })
    if not rows:
        return [], []
    sharpe = np.array([row["candidate_sharpe_ratio"] for row in rows], dtype=float)
    drawdown = np.array([row["drawdown_improvement_vs_reference"] for row in rows], dtype=float)
    greatest_loss = min(rows, key=lambda row: row["sharpe_change_vs_baseline"])
    summary = [{
        "episode_count": len(rows),
        "fraction_still_improving_reference_sharpe_or_drawdown": float(np.mean([row["still_improves_reference_sharpe_or_drawdown"] for row in rows])),
        "fraction_not_dominated_by_named_control": float(np.mean([not row["named_control_dominates"] for row in rows])),
        "fraction_not_dominated_by_exposure_control": float(np.mean([not row["exposure_control_dominates"] for row in rows])),
        "fraction_dominated_by_named_control": float(np.mean([row["named_control_dominates"] for row in rows])),
        "fraction_dominated_by_exposure_control": float(np.mean([row["exposure_control_dominates"] for row in rows])),
        "minimum_sharpe": float(sharpe.min()),
        "median_sharpe": float(np.median(sharpe)),
        "maximum_sharpe": float(sharpe.max()),
        "minimum_drawdown_improvement": float(drawdown.min()),
        "median_drawdown_improvement": float(np.median(drawdown)),
        "maximum_drawdown_improvement": float(drawdown.max()),
        "episode_causing_largest_loss_of_candidate_benefit": greatest_loss["episode_id"],
        "largest_sharpe_loss_vs_baseline": greatest_loss["sharpe_change_vs_baseline"],
        "combinations_of_episodes_removed": False,
    }]
    return rows, summary


def reference_negative_month_rows(
    paths: dict[tuple[str, float], dict[str, Any]]
) -> list[dict[str, Any]]:
    monthly = {
        portfolio_id: monthly_returns(paths[(portfolio_id, PRIMARY_COST)]["returns"])
        for portfolio_id in PORTFOLIO_IDS
    }
    reference = monthly[REFERENCE_ID]
    candidate = monthly[CANDIDATE_ID]
    negative_months = reference[reference < 0.0].index
    rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        values = monthly[portfolio_id].reindex(negative_months).dropna()
        aligned_reference = reference.reindex(values.index)
        candidate_aligned = candidate.reindex(values.index)
        rows.append({
            "portfolio_id": portfolio_id,
            "cost_bps_one_way": PRIMARY_COST,
            "reference_negative_month_count": len(values),
            "cumulative_return_in_reference_negative_months": float((1.0 + values).prod() - 1.0),
            "mean_monthly_return": float(values.mean()),
            "worst_month": float(values.min()),
            "percentage_negative_reference_months_outperforming_reference": float((values > aligned_reference).mean()),
            "average_portfolio_minus_reference_return": float((values - aligned_reference).mean()),
            "average_candidate_minus_control_return": (
                "" if portfolio_id == CANDIDATE_ID
                else float((candidate_aligned - values).mean())
            ),
            "diagnostic_only": True,
        })
    return rows


def maximum_drawdown_for_returns(returns: pd.Series) -> float:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def reference_drawdown_episodes(
    paths: dict[tuple[str, float], dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reference = paths[(REFERENCE_ID, PRIMARY_COST)]["returns"]
    wealth = (1.0 + reference).cumprod()
    running_peak = wealth.cummax()
    underwater = wealth < running_peak - 1e-14
    episodes: list[dict[str, Any]] = []
    active_start: pd.Timestamp | None = None
    peak_date: pd.Timestamp | None = None
    for position, date in enumerate(wealth.index):
        date = pd.Timestamp(date)
        if bool(underwater.iloc[position]) and active_start is None:
            peak_date = pd.Timestamp(wealth.index[position - 1]) if position > 0 else date
            active_start = date
        if active_start is not None and not bool(underwater.iloc[position]):
            period = wealth.index[(wealth.index >= active_start) & (wealth.index <= date)]
            trough_date = pd.Timestamp((wealth / running_peak - 1.0).reindex(period).idxmin())
            episodes.append({
                "episode_id": f"reference_drawdown_episode_{len(episodes) + 1:03d}",
                "peak_date": peak_date.date().isoformat() if peak_date is not None else "",
                "drawdown_start": active_start.date().isoformat(),
                "trough_date": trough_date.date().isoformat(),
                "recovery_date": date.date().isoformat(),
                "reference_recovery_duration_sessions": len(period),
                "period": period,
            })
            active_start = None
            peak_date = None
    rows: list[dict[str, Any]] = []
    reductions: list[float] = []
    for episode in episodes:
        period = episode["period"]
        values = {
            portfolio_id: maximum_drawdown_for_returns(
                paths[(portfolio_id, PRIMARY_COST)]["returns"].reindex(period)
            )
            for portfolio_id in (REFERENCE_ID, CANDIDATE_ID, NAMED_ID, STATIC_ID, ENDPOINT_ID, SPY_ID, BIL_ID)
        }
        reduction = values[CANDIDATE_ID] - values[REFERENCE_ID]
        reductions.append(reduction)
        rows.append({
            **{key: value for key, value in episode.items() if key != "period"},
            "reference_drawdown": values[REFERENCE_ID],
            "candidate_drawdown": values[CANDIDATE_ID],
            "named_control_drawdown": values[NAMED_ID],
            "exposure_control_drawdown": values[STATIC_ID],
            "endpoint_control_drawdown": values[ENDPOINT_ID],
            "SPY_control_drawdown": values[SPY_ID],
            "BIL_control_drawdown": values[BIL_ID],
            "candidate_drawdown_reduction_vs_reference": reduction,
            "candidate_drawdown_reduction_vs_named": values[CANDIDATE_ID] - values[NAMED_ID],
            "candidate_drawdown_reduction_vs_exposure": values[CANDIDATE_ID] - values[STATIC_ID],
            "candidate_recovery_duration_sessions": len(period),
            "completed_reference_drawdown_episode": True,
        })
    positive_total = sum(max(value, 0.0) for value in reductions)
    for row, reduction in zip(rows, reductions):
        row["contribution_to_total_positive_historical_drawdown_improvement"] = (
            max(reduction, 0.0) / positive_total if positive_total > 0.0 else 0.0
        )
    return rows, episodes


def concentration_and_neutralization(
    paths: dict[tuple[str, float], dict[str, Any]],
    drawdown_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = (CANDIDATE_ID, REFERENCE_ID, NAMED_ID, STATIC_ID)
    monthly = pd.concat(
        [monthly_returns(paths[(portfolio_id, PRIMARY_COST)]["returns"]).rename(portfolio_id) for portfolio_id in ids],
        axis=1,
        join="inner",
    ).dropna()
    excess = monthly[CANDIDATE_ID] - monthly[REFERENCE_ID]
    positive = excess[excess > 0.0].sort_values(ascending=False)
    strongest_months = list(positive.index[:3])
    strongest_month = strongest_months[0]
    annual = excess.groupby(excess.index.year).sum()
    strongest_year = int(annual.idxmax())
    strongest_drawdown = max(
        drawdown_rows,
        key=lambda row: float(row["candidate_drawdown_reduction_vs_reference"]),
    )
    drawdown_start = pd.Timestamp(strongest_drawdown["drawdown_start"]).to_period("M")
    drawdown_end = pd.Timestamp(strongest_drawdown["recovery_date"]).to_period("M")
    drawdown_months = [period for period in monthly.index if drawdown_start <= period <= drawdown_end]
    rank = {period: position + 1 for position, period in enumerate(positive.index)}
    concentration = [{
        "month": str(period),
        "candidate_return_5bps": monthly.loc[period, CANDIDATE_ID],
        "reference_return_5bps": monthly.loc[period, REFERENCE_ID],
        "candidate_minus_reference_excess": excess.loc[period],
        "positive_excess_rank": rank.get(period, ""),
        "strongest_candidate_minus_reference_month": period == strongest_month,
        "among_three_strongest_candidate_minus_reference_months": period in strongest_months,
        "strongest_candidate_minus_reference_calendar_year": period.year == strongest_year,
        "strongest_reference_drawdown_episode_benefit": period in drawdown_months,
        "frozen_before_neutralization": True,
        "observation_deleted": False,
    } for period in monthly.index]
    scenarios = {
        "neutralize_strongest_month": [strongest_month],
        "neutralize_three_strongest_months": strongest_months,
        "neutralize_strongest_year": [period for period in monthly.index if period.year == strongest_year],
        "neutralize_strongest_drawdown_episode": drawdown_months,
    }
    reference_metrics = monthly_metrics(monthly[REFERENCE_ID])
    named_metrics = monthly_metrics(monthly[NAMED_ID])
    static_metrics = monthly_metrics(monthly[STATIC_ID])
    neutralization: list[dict[str, Any]] = []
    for scenario, periods in scenarios.items():
        counterfactual = monthly[CANDIDATE_ID].copy()
        counterfactual.loc[periods] = monthly.loc[periods, REFERENCE_ID]
        metrics = monthly_metrics(counterfactual)
        neutralization.append({
            "scenario": scenario,
            "neutralized_months": [str(period) for period in periods],
            "neutralized_month_count": len(periods),
            "strongest_year": strongest_year,
            "strongest_drawdown_episode_id": strongest_drawdown["episode_id"],
            **metrics,
            "reference_cagr": reference_metrics["cagr"],
            "reference_sharpe_ratio": reference_metrics["sharpe_ratio"],
            "reference_maximum_drawdown": reference_metrics["maximum_drawdown"],
            "sharpe_difference_vs_reference": float(metrics["sharpe_ratio"]) - float(reference_metrics["sharpe_ratio"]),
            "drawdown_difference_vs_reference": float(metrics["maximum_drawdown"]) - float(reference_metrics["maximum_drawdown"]),
            "improves_reference_sharpe_or_drawdown": bool(
                float(metrics["sharpe_ratio"]) > float(reference_metrics["sharpe_ratio"])
                or float(metrics["maximum_drawdown"]) > float(reference_metrics["maximum_drawdown"])
            ),
            "materiality_vs_reference": material_advantage(metrics, reference_metrics),
            "named_control_dominates": dominates(named_metrics, metrics),
            "exposure_control_dominates": dominates(static_metrics, metrics),
            "observations_deleted": False,
            "canonical_return_series_modified": False,
            "used_for_strategy_change": False,
        })
    return concentration, neutralization


def monthly_path_metrics(values: np.ndarray) -> tuple[float, float]:
    standard_deviation = float(np.std(values, ddof=1))
    sharpe = float(np.mean(values) / standard_deviation * math.sqrt(12.0)) if standard_deviation > 0.0 else 0.0
    wealth = np.cumprod(1.0 + values)
    drawdown = float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))
    return sharpe, drawdown


def paired_bootstrap(paths: dict[tuple[str, float], dict[str, Any]]) -> list[dict[str, Any]]:
    ids = (CANDIDATE_ID, REFERENCE_ID, NAMED_ID, STATIC_ID)
    monthly = pd.concat(
        [monthly_returns(paths[(portfolio_id, PRIMARY_COST)]["returns"]).rename(portfolio_id) for portfolio_id in ids],
        axis=1,
        join="inner",
    ).dropna()
    values = monthly.to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    maximum_start = count - BOOTSTRAP_BLOCK_MONTHS
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = {portfolio_id: {"sharpe": 0, "drawdown": 0, "either": 0} for portfolio_id in ids[1:]}
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, maximum_start + 1, size=block_count)
        sampled = np.concatenate([
            np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts
        ])[:count]
        sample = values[sampled]
        candidate_sharpe, candidate_drawdown = monthly_path_metrics(sample[:, 0])
        for column, comparator in enumerate(ids[1:], start=1):
            control_sharpe, control_drawdown = monthly_path_metrics(sample[:, column])
            better_sharpe = candidate_sharpe > control_sharpe
            better_drawdown = candidate_drawdown > control_drawdown
            counts[comparator]["sharpe"] += int(better_sharpe)
            counts[comparator]["drawdown"] += int(better_drawdown)
            counts[comparator]["either"] += int(better_sharpe or better_drawdown)
    return [{
        "candidate_portfolio_id": CANDIDATE_ID,
        "comparison_portfolio_id": comparator,
        "monthly_observation_count": count,
        "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
        "resamples": BOOTSTRAP_RESAMPLES,
        "deterministic_seed": BOOTSTRAP_SEED,
        "paired_cross_portfolio_dependence_preserved": True,
        "probability_candidate_higher_sharpe": counts[comparator]["sharpe"] / BOOTSTRAP_RESAMPLES,
        "probability_candidate_less_severe_drawdown": counts[comparator]["drawdown"] / BOOTSTRAP_RESAMPLES,
        "probability_candidate_higher_sharpe_or_less_severe_drawdown": counts[comparator]["either"] / BOOTSTRAP_RESAMPLES,
        "used_for_route_change": False,
    } for comparator in ids[1:]]


def lookup_summary(rows: list[dict[str, Any]], months: int, comparator: str) -> dict[str, Any]:
    matches = [row for row in rows if row["window_months"] == months and row["comparison_portfolio_id"] == comparator]
    if len(matches) != 1:
        raise RuntimeError("rolling summary lookup failed")
    return matches[0]


def decide_outcome(
    reproduction_pass: bool,
    invariants_pass: bool,
    full: dict[tuple[str, float], dict[str, Any]],
    fold_metrics: dict[tuple[str, str], dict[str, Any]],
    final_metrics: dict[tuple[str, str], dict[str, Any]],
    quarter_metrics: dict[tuple[str, str], dict[str, Any]],
    rolling: list[dict[str, Any]],
    neutralization: list[dict[str, Any]],
    leave_summary: list[dict[str, Any]],
    episode_attribution: list[dict[str, Any]],
    downside: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> tuple[str, str, str, str, dict[str, Any]]:
    blocked_next = "direction_owner_review_technical_factory_v1_d1_robustness_block_v1"
    review_next = "direction_owner_review_technical_factory_v1_after_d1_robustness_v1"
    positive_next = "onboard_technical_factory_v1_trend_quality_diversifier_paper_demo_v1"
    if not reproduction_pass:
        return "robustness_blocked", "data_or_comparability_failure", blocked_next, "historical_robustness_not_established", {"parent_reproduction_and_invariants_pass": False}
    if not invariants_pass:
        return "robustness_blocked", "methodology_failure", blocked_next, "historical_robustness_not_established", {"parent_reproduction_and_invariants_pass": False}
    candidate = full[(CANDIDATE_ID, 5.0)]
    reference = full[(REFERENCE_ID, 5.0)]
    named = full[(NAMED_ID, 5.0)]
    static = full[(STATIC_ID, 5.0)]
    fold_ids = ("fold_1", "fold_2", "fold_3", "fold_4")
    fold_improves = sum(
        float(fold_metrics[(CANDIDATE_ID, fold)]["sharpe_ratio"]) > float(fold_metrics[(REFERENCE_ID, fold)]["sharpe_ratio"])
        or float(fold_metrics[(CANDIDATE_ID, fold)]["maximum_drawdown"]) > float(fold_metrics[(REFERENCE_ID, fold)]["maximum_drawdown"])
        for fold in fold_ids
    )
    fold_worse_named = sum(worse_on_both(fold_metrics[(CANDIDATE_ID, fold)], fold_metrics[(NAMED_ID, fold)]) for fold in fold_ids)
    fold_worse_static = sum(worse_on_both(fold_metrics[(CANDIDATE_ID, fold)], fold_metrics[(STATIC_ID, fold)]) for fold in fold_ids)
    quarter_ids = tuple(f"chronological_quarter_{number}" for number in range(1, 5))
    quarter_improves = sum(
        float(quarter_metrics[(CANDIDATE_ID, quarter)]["sharpe_ratio"]) > float(quarter_metrics[(REFERENCE_ID, quarter)]["sharpe_ratio"])
        or float(quarter_metrics[(CANDIDATE_ID, quarter)]["maximum_drawdown"]) > float(quarter_metrics[(REFERENCE_ID, quarter)]["maximum_drawdown"])
        for quarter in quarter_ids
    )
    rolling_ref = all(float(lookup_summary(rolling, months, REFERENCE_ID)["candidate_improves_fraction"]) > 0.50 for months in (36, 60))
    rolling_controls = all(
        float(lookup_summary(rolling, months, control)["comparison_dominates_fraction"]) <= 0.50
        for months in (36, 60) for control in CRITICAL_IDS
    )
    full10 = route_gate(full[(CANDIDATE_ID, 10.0)], full[(REFERENCE_ID, 10.0)], full[(NAMED_ID, 10.0)], full[(STATIC_ID, 10.0)])
    cost15 = bool(
        float(full[(CANDIDATE_ID, 15.0)]["sharpe_ratio"]) > float(full[(REFERENCE_ID, 15.0)]["sharpe_ratio"])
        or float(full[(CANDIDATE_ID, 15.0)]["maximum_drawdown"]) > float(full[(REFERENCE_ID, 15.0)]["maximum_drawdown"])
    )
    cost20 = not worse_on_both(full[(CANDIDATE_ID, 20.0)], full[(REFERENCE_ID, 20.0)])
    neutral = {row["scenario"]: row for row in neutralization}
    neutral_three = bool(
        neutral["neutralize_three_strongest_months"]["materiality_vs_reference"]
        and not neutral["neutralize_three_strongest_months"]["named_control_dominates"]
        and not neutral["neutralize_three_strongest_months"]["exposure_control_dominates"]
    )
    neutral_year = bool(
        neutral["neutralize_strongest_year"]["materiality_vs_reference"]
        and not neutral["neutralize_strongest_year"]["named_control_dominates"]
        and not neutral["neutralize_strongest_year"]["exposure_control_dominates"]
    )
    neutral_drawdown = bool(neutral["neutralize_strongest_drawdown_episode"]["improves_reference_sharpe_or_drawdown"])
    leave = leave_summary[0]
    leave_reference = float(leave["fraction_still_improving_reference_sharpe_or_drawdown"]) >= 0.75
    leave_controls = bool(
        float(leave["fraction_dominated_by_named_control"]) <= 0.50
        and float(leave["fraction_dominated_by_exposure_control"]) <= 0.50
    )
    episode_summary = next(row for row in episode_attribution if row["row_type"] == "summary")
    episode_concentration = float(episode_summary["largest_episode_share_of_total_positive_contribution"]) < 0.50
    candidate_downside = next(row for row in downside if row["portfolio_id"] == CANDIDATE_ID)
    downside_pass = bool(
        float(candidate_downside["average_portfolio_minus_reference_return"]) > 0.0
        and float(candidate_downside["percentage_negative_reference_months_outperforming_reference"]) > 0.50
    )
    bootstrap_map = {row["comparison_portfolio_id"]: row for row in bootstrap}
    bootstrap_reference = float(bootstrap_map[REFERENCE_ID]["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.75
    bootstrap_controls = all(
        float(bootstrap_map[control]["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60
        for control in CRITICAL_IDS
    )
    checks = {
        "parent_reproduction_and_every_invariant_pass": True,
        "positive_full_period_return": float(candidate["total_return"]) > 0.0,
        "material_improvement_vs_reference": material_advantage(candidate, reference),
        "does_not_worsen_both_vs_reference": not worse_on_both(candidate, reference),
        "neither_critical_control_dominates_full_period": not dominates(named, candidate) and not dominates(static, candidate),
        "material_advantage_vs_named_control": material_advantage(candidate, named),
        "material_advantage_vs_exposure_control": material_advantage(candidate, static),
        "original_folds_improving_reference_count": fold_improves,
        "at_least_three_original_folds_improve_reference": fold_improves >= 3,
        "folds_worse_both_vs_named_count": fold_worse_named,
        "folds_worse_both_vs_exposure_count": fold_worse_static,
        "worse_both_vs_each_critical_in_at_most_one_fold": fold_worse_named <= 1 and fold_worse_static <= 1,
        "original_final_segment_retains_corrected_route_pass": route_gate(
            final_metrics[(CANDIDATE_ID, "factory_final_evaluation_segment")],
            final_metrics[(REFERENCE_ID, "factory_final_evaluation_segment")],
            final_metrics[(NAMED_ID, "factory_final_evaluation_segment")],
            final_metrics[(STATIC_ID, "factory_final_evaluation_segment")],
        ),
        "chronological_quarters_improving_reference_count": quarter_improves,
        "at_least_three_chronological_quarters_improve_reference": quarter_improves >= 3,
        "rolling_36_and_60_improve_reference_more_than_half": rolling_ref,
        "critical_controls_dominate_at_most_half_rolling_windows": rolling_controls,
        "10bps_full_route_conditions_pass": full10,
        "15bps_improves_reference_sharpe_or_drawdown": cost15,
        "20bps_not_worse_both_vs_reference": cost20,
        "neutralize_three_strongest_months_pass": neutral_three,
        "neutralize_strongest_year_pass": neutral_year,
        "neutralize_strongest_drawdown_episode_pass": neutral_drawdown,
        "leave_one_episode_reference_fraction_pass": leave_reference,
        "leave_one_episode_control_dominance_pass": leave_controls,
        "largest_filter_episode_below_50pct_positive_contribution": episode_concentration,
        "reference_negative_month_conditions_pass": downside_pass,
        "bootstrap_reference_threshold_pass": bootstrap_reference,
        "bootstrap_critical_control_thresholds_pass": bootstrap_controls,
        "bootstrap_probabilities": bootstrap_map,
    }
    boolean_required = [value for value in checks.values() if isinstance(value, bool)]
    if all(boolean_required):
        return "robustness_positive", "", positive_next, "paper_demo_eligibility_candidate_20pct_diversifier", checks
    broad_improvement = bool(
        checks["positive_full_period_return"]
        and checks["material_improvement_vs_reference"]
        and checks["does_not_worsen_both_vs_reference"]
    )
    controls_explain = not bool(
        checks["neither_critical_control_dominates_full_period"]
        and checks["material_advantage_vs_named_control"]
        and checks["material_advantage_vs_exposure_control"]
    )
    broadly_unstable = bool(fold_improves < 2 and not rolling_ref)
    if not broad_improvement:
        return "robustness_failed", "benchmark_like_behavior", review_next, "historical_diversifier_claim_not_supported", checks
    if controls_explain:
        return "robustness_failed", "weak_vs_primary_control", review_next, "historical_diversifier_claim_not_supported", checks
    if broadly_unstable:
        return "robustness_failed", "period_instability", review_next, "historical_diversifier_claim_not_supported", checks
    if not (cost15 and cost20):
        reason = "cost_sensitivity"
    elif not (neutral_three and neutral_year and neutral_drawdown):
        reason = "concentration_risk"
    elif not (leave_reference and leave_controls and episode_concentration):
        reason = "weak_component_attribution"
    elif not (bootstrap_reference and bootstrap_controls):
        reason = "overfit_or_unstable"
    elif not (rolling_ref and quarter_improves >= 3 and fold_improves >= 3):
        reason = "period_instability"
    else:
        reason = "control_uncertainty"
    return "robustness_mixed", reason, review_next, "historically_promising_not_ready_for_paper_demo_eligibility", checks


def series_hash(series: pd.Series) -> str:
    payload = pd.util.hash_pandas_object(series, index=True).to_numpy(dtype=np.uint64).tobytes()
    return sha256_bytes(payload)


def invariant_and_turnover_rows(
    prepared: dict[str, Any],
    preflight: list[dict[str, Any]],
    common_index: pd.DatetimeIndex,
    paths: dict[tuple[str, float], dict[str, Any]],
    full: dict[tuple[str, float], dict[str, Any]],
    reproduction_pass: bool,
    parent_contract_pass: bool,
    deterministic_rerun_pass: bool,
    bootstrap_deterministic: bool,
    preregistration_unchanged: bool,
    protected_unchanged_midrun: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    turnover_rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        for cost in COSTS:
            metrics = full[(portfolio_id, cost)]
            turnover_rows.append({
                "portfolio_id": portfolio_id,
                "cost_bps_one_way": cost,
                "inner_turnover": metrics["inner_turnover"],
                "outer_turnover": metrics["outer_turnover"],
                "total_turnover": float(metrics["inner_turnover"]) + float(metrics["outer_turnover"]),
                "inner_transaction_cost_drag": metrics["inner_transaction_cost_drag"],
                "outer_transaction_cost_drag": metrics["outer_transaction_cost_drag"],
                "total_transaction_cost_drag": metrics["total_transaction_cost_drag"],
                "costs_charged_once": True,
                "inner_outer_turnover_separately_reported": True,
            })

    diagnostics = prepared["diagnostics"].copy()
    valid = diagnostics[diagnostics["signal_valid"].astype(bool)]
    expected_candidate = np.where(
        (valid["annualized_slope"].to_numpy(dtype=float) > 0.0)
        & (valid["r_squared"].to_numpy(dtype=float) >= 0.25),
        "SPY",
        "BIL",
    )
    expected_named = np.where(valid["annualized_slope"].to_numpy(dtype=float) > 0.0, "SPY", "BIL")
    formula_equivalent = bool(
        np.array_equal(valid["candidate_target"].to_numpy(), expected_candidate)
        and np.array_equal(valid["named_control_target"].to_numpy(), expected_named)
    )
    executable = valid[valid["execution_date"].astype(str).ne("")]
    execution_dates = pd.to_datetime(executable["execution_date"])
    signal_dates = pd.to_datetime(executable["signal_date"])
    execution_after_signal = bool((execution_dates > signal_dates).all())
    path_weights_pass = True
    path_numeric_pass = True
    cost_reconciliation_pass = True
    for path in paths.values():
        daily = path["daily"]
        held = path["held_weights"]
        path_weights_pass = path_weights_pass and bool(
            np.isfinite(held.to_numpy(dtype=float)).all()
            and (held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
            and (held.sum(axis=1).to_numpy(dtype=float) <= 1.0 + WEIGHT_TOLERANCE).all()
            and (held.abs().sum(axis=1).to_numpy(dtype=float) <= 1.0 + WEIGHT_TOLERANCE).all()
        )
        path_numeric_pass = path_numeric_pass and bool(
            np.isfinite(path["returns"].to_numpy(dtype=float)).all()
            and np.isfinite(path["turnover"].to_numpy(dtype=float)).all()
            and np.isfinite(path["cost"].to_numpy(dtype=float)).all()
        )
        cost_reconciliation_pass = cost_reconciliation_pass and bool(
            (path["turnover"].to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
            and (path["cost"].to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
            and np.allclose(
                daily["one_way_turnover"].to_numpy(dtype=float),
                path["turnover"].to_numpy(dtype=float),
                atol=1e-14,
                rtol=0.0,
            )
        )
    preflight_pass = bool(
        preflight
        and all(
            row.get("preflight_status") == "pass"
            and bool(row.get("ordered_unique_sessions"))
            and bool(row.get("finite_positive_adjusted_ohlc"))
            and bool(row.get("valid_adjusted_ohlc_relationships"))
            and bool(row.get("canonical_adjustment_compatible"))
            for row in preflight
        )
    )
    checks = [
        ("authoritative_parent_contract_reconciles", parent_contract_pass, "factory and correction packets"),
        ("canonical_SPY_BIL_preflight_passes", preflight_pass, "ordered unique finite adjusted canonical data"),
        ("common_period_is_nonempty_and_frozen_before_performance", len(common_index) > 0, f"{common_index[0].date()} through {common_index[-1].date()}"),
        ("D1_formula_and_named_control_state_equivalence", formula_equivalent, "60-session log OLS, annualized slope, R-squared threshold 0.25"),
        ("following_session_close_execution", execution_after_signal, "every eligible execution date follows its signal date"),
        ("portfolio_weights_and_exposure", path_weights_pass, "nonnegative, sum and gross exposure no greater than one"),
        ("portfolio_numeric_values", path_numeric_pass, "all path returns, turnover, and costs finite"),
        ("turnover_and_cost_reconciliation", cost_reconciliation_pass, "explicit path accounting fields reconcile"),
        ("parent_row_reproduction_within_1e-9", reproduction_pass, "0, 5, and 10 bps parent rows and route booleans"),
        ("unselected_variant_final_access_prohibited", True, "only D1 prepared and evaluated"),
        ("standalone_closure_preserved", True, "closed_exploration / weak_vs_primary_control"),
        ("sleeve_and_control_contract_frozen", factory_spec().parameters == {"lookback_sessions": 60, "r2_threshold": 0.25}, "20% route and archived static exposure retained"),
        ("preregistration_artifacts_unchanged_after_metrics", preregistration_unchanged, "lineage, trial, benchmarks, process, and portfolio definition"),
        ("protected_state_unchanged_midrun", protected_unchanged_midrun, "protected files, caches, and prior evidence"),
        ("serial_path_rerun_deterministic", deterministic_rerun_pass, "candidate inner and 80/20 portfolio path hashes"),
        ("paired_bootstrap_deterministic", bootstrap_deterministic, f"seed {BOOTSTRAP_SEED}"),
        ("independent_validation_not_claimed", True, "same-period historical robustness only"),
        ("paper_demo_or_lifecycle_action_not_executed", True, "zero observations and zero lifecycle changes"),
    ]
    invariant_rows = [{
        "invariant_name": name,
        "invariant_pass": bool(passed),
        "evidence": evidence,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
    } for name, passed, evidence in checks]
    return turnover_rows, invariant_rows, bool(all(row["invariant_pass"] for row in invariant_rows))


def build_report(
    outcome: str,
    failure_reason: str,
    interpretation: str,
    next_action: str,
    full: dict[tuple[str, float], dict[str, Any]],
    rolling: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    leave_summary: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> str:
    candidate = full[(CANDIDATE_ID, PRIMARY_COST)]
    reference = full[(REFERENCE_ID, PRIMARY_COST)]
    named = full[(NAMED_ID, PRIMARY_COST)]
    static = full[(STATIC_ID, PRIMARY_COST)]
    lines = [
        "# Technical Factory V1 Trend-Quality Diversifier Robustness V1",
        "",
        "## Outcome",
        "",
        f"- Outcome: `{outcome}`",
        f"- Failure reason: `{failure_reason or 'none'}`",
        f"- Interpretation: `{interpretation}`",
        "- Route tested: `20pct_diversifier_only`",
        "- D1 standalone result preserved: `closed_exploration / weak_vs_primary_control`",
        "- This is bounded historical robustness, not independent validation.",
        "",
        "## Full Period At 5 Bps",
        "",
        "| Portfolio | CAGR | Sharpe | Maximum drawdown |",
        "|---|---:|---:|---:|",
        f"| Frozen reference | {reference['cagr']:.6f} | {reference['sharpe_ratio']:.6f} | {reference['maximum_drawdown']:.6f} |",
        f"| 80/20 D1 | {candidate['cagr']:.6f} | {candidate['sharpe_ratio']:.6f} | {candidate['maximum_drawdown']:.6f} |",
        f"| 80/20 slope-only | {named['cagr']:.6f} | {named['sharpe_ratio']:.6f} | {named['maximum_drawdown']:.6f} |",
        f"| 80/20 static exposure | {static['cagr']:.6f} | {static['sharpe_ratio']:.6f} | {static['maximum_drawdown']:.6f} |",
        "",
        "## Stability",
        "",
    ]
    for months in (36, 60):
        row = lookup_summary(rolling, months, REFERENCE_ID)
        lines.append(
            f"- Rolling {months}-month windows improving reference Sharpe or drawdown: "
            f"{float(row['candidate_improves_fraction']):.1%}."
        )
    lines.extend([
        f"- Path-quality filter episodes: {len(episodes)}.",
        f"- Leave-one-episode cases: {0 if not leave_summary else leave_summary[0]['episode_count']}.",
        "- Every rolling window, episode, neutralization, and unfavorable result is retained in the packet.",
        "",
        "## Bootstrap",
        "",
    ])
    for row in bootstrap:
        lines.append(
            f"- Versus `{row['comparison_portfolio_id']}`: probability of higher Sharpe or less severe drawdown "
            f"{float(row['probability_candidate_higher_sharpe_or_less_severe_drawdown']):.1%}."
        )
    lines.extend([
        "",
        "## Boundaries",
        "",
        "D1 was not retuned. D2, D3, and D4 were not evaluated on the final segment. No provider, lifecycle, paper/demo, broker, account, order, capital, or real-money action occurred.",
        "",
        "## Next Action",
        "",
        f"`{next_action}`",
        "",
        "The next action is recorded only and was not executed.",
    ])
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    parent_contract_pass = verify_parent_contract()
    if not parent_contract_pass:
        raise RuntimeError("authoritative Technical Factory V1 packets do not reconcile")
    protected_before = protected_snapshot()
    source_before = file_hash(SOURCE_PROMPT)
    reset_output()

    prepared, reference, common_index, preflight = prepare_inputs()
    if not len(common_index):
        raise RuntimeError("no common D1/reference period")
    preregistration_hashes = write_preregistration(common_index)

    inner_paths = simulate_inner_paths(prepared)
    paths = build_portfolio_paths(reference, common_index, inner_paths)
    periods, period_reconciliation = factory_periods(common_index)
    final_index = periods["factory_final_evaluation_segment"]
    reproduction_rows, reproduction_pass = parent_reproduction_rows(inner_paths, paths, final_index)

    full: dict[tuple[str, float], dict[str, Any]] = {}
    cost_rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        for cost in COSTS:
            metrics = portfolio_metrics(paths[(portfolio_id, cost)])
            full[(portfolio_id, cost)] = metrics
            cost_rows.append(result_row(portfolio_id, cost, "full_common_period", "cost_stress", metrics))
    full_rows = [
        result_row(portfolio_id, PRIMARY_COST, "full_common_period", "full_period", full[(portfolio_id, PRIMARY_COST)])
        for portfolio_id in PORTFOLIO_IDS
    ]

    fold_ids = ("fold_1", "fold_2", "fold_3", "fold_4")
    fold_rows = period_rows(paths, periods, fold_ids, "original_factory_walk_forward_interval")
    fold_metrics = {(row["portfolio_id"], row["period_id"]): row for row in fold_rows}
    development_ids = ("development_selection_period_intersection", "factory_final_evaluation_segment")
    development_rows = period_rows(paths, periods, development_ids, "factory_optimization_boundary")
    for row in development_rows:
        row["unselected_variant_access"] = False
        row["period_selected_from_robustness_results"] = False
    final_metrics = {(row["portfolio_id"], row["period_id"]): row for row in development_rows}

    quarter_periods = split_quarters(common_index)
    periods.update(quarter_periods)
    quarter_rows = period_rows(paths, periods, quarter_periods.keys(), "equal_chronological_quarter")
    quarter_metrics = {(row["portfolio_id"], row["period_id"]): row for row in quarter_rows}

    calendar_rows: list[dict[str, Any]] = []
    for year in range(common_index[0].year + 1, common_index[-1].year):
        period = common_index[common_index.year == year]
        for portfolio_id in PORTFOLIO_IDS:
            row = result_row(
                portfolio_id,
                PRIMARY_COST,
                f"complete_calendar_year_{year}",
                "complete_calendar_year",
                portfolio_metrics(paths[(portfolio_id, PRIMARY_COST)], period),
            )
            row["calendar_year"] = year
            row["complete_calendar_year"] = True
            calendar_rows.append(row)

    rolling36 = rolling_rows(paths, common_index, 36)
    rolling60 = rolling_rows(paths, common_index, 60)
    rolling = rolling_summary(rolling36, rolling60)
    episode_inventory, episode_attribution, episode_objects = path_quality_episodes(
        prepared, common_index, inner_paths, paths, reference
    )
    leave_rows, leave_summary = leave_one_episode_out(
        episode_objects, prepared, reference, common_index, paths
    )
    downside_rows = reference_negative_month_rows(paths)
    drawdown_rows, _ = reference_drawdown_episodes(paths)
    concentration_rows, neutralization_rows = concentration_and_neutralization(paths, drawdown_rows)
    bootstrap_rows = paired_bootstrap(paths)
    bootstrap_repeat = paired_bootstrap(paths)
    bootstrap_deterministic = bootstrap_rows == bootstrap_repeat

    rerun_inner = simulate_inner_paths(prepared)
    rerun_paths = build_portfolio_paths(reference, common_index, rerun_inner)
    deterministic_rerun_pass = bool(
        series_hash(inner_paths[("candidate", PRIMARY_COST)]["returns"])
        == series_hash(rerun_inner[("candidate", PRIMARY_COST)]["returns"])
        and series_hash(paths[(CANDIDATE_ID, PRIMARY_COST)]["returns"])
        == series_hash(rerun_paths[(CANDIDATE_ID, PRIMARY_COST)]["returns"])
    )
    preregistration_unchanged = all(
        file_hash(OUTPUT_DIR / name) == value for name, value in preregistration_hashes.items()
    )
    protected_mid = protected_snapshot()
    turnover_rows, invariant_rows, invariants_pass = invariant_and_turnover_rows(
        prepared,
        preflight,
        common_index,
        paths,
        full,
        reproduction_pass,
        parent_contract_pass,
        deterministic_rerun_pass,
        bootstrap_deterministic,
        preregistration_unchanged,
        protected_before == protected_mid,
    )
    outcome, failure_reason, next_action, interpretation, gate = decide_outcome(
        reproduction_pass,
        invariants_pass,
        full,
        fold_metrics,
        final_metrics,
        quarter_metrics,
        rolling,
        neutralization_rows,
        leave_summary,
        episode_attribution,
        downside_rows,
        bootstrap_rows,
    )

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "common_period_start": common_index[0].date().isoformat(),
        "common_period_end": common_index[-1].date().isoformat(),
        "development_selection_period": [DEVELOPMENT_START.date().isoformat(), DEVELOPMENT_END.date().isoformat()],
        "final_exploratory_evaluation_segment": [FINAL_START.date().isoformat(), FINAL_END.date().isoformat()],
        "factory_period_reconciliation": period_reconciliation,
        "costs_bps_one_way": list(COSTS),
        "rolling_windows_months": [36, 60],
        "bootstrap": {"block_length_months": BOOTSTRAP_BLOCK_MONTHS, "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "preregistration_checkpoint_hashes": preregistration_hashes,
        "preregistration_written_before_performance": True,
        "current_task_source_hash": source_before,
        "existing_strategy_configurations_carried_forward": 1,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 1,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "validation_observations": 0,
        "data_capability_tasks": 0,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "interpretation": interpretation,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml("robustness_manifest.yaml", manifest)
    write_csv("parent_reproduction_check.csv", reproduction_rows, ("reproduction_scope", "series_id", "cost_bps_one_way", "metric"))
    write_csv("full_period_portfolio_results.csv", full_rows, ("portfolio_id", "cost_bps_one_way", "period_id"))
    write_csv("factory_fold_portfolio_results.csv", fold_rows, ("portfolio_id", "period_id"))
    write_csv("development_final_segment_results.csv", development_rows, ("portfolio_id", "period_id"))
    write_csv("cost_stress_results.csv", cost_rows, ("portfolio_id", "cost_bps_one_way"))
    write_csv("chronological_quarter_results.csv", quarter_rows, ("portfolio_id", "period_id"))
    write_csv("calendar_year_results.csv", calendar_rows, ("calendar_year", "portfolio_id"))
    write_csv("rolling_36_month_results.csv", rolling36, ("window_sequence", "comparison_portfolio_id"))
    write_csv("rolling_60_month_results.csv", rolling60, ("window_sequence", "comparison_portfolio_id"))
    write_csv("rolling_window_summary.csv", rolling, ("window_months", "comparison_portfolio_id"))
    write_csv("path_quality_filter_episode_inventory.csv", episode_inventory, ("episode_id", "target_start_execution_date", "target_end_date"))
    write_csv("path_quality_filter_episode_attribution.csv", episode_attribution, ("row_type", "episode_id"))
    write_csv("leave_one_filter_episode_out_results.csv", leave_rows, ("episode_id",))
    write_csv("leave_one_filter_episode_out_summary.csv", leave_summary, ("episode_count",))
    write_csv("reference_negative_month_results.csv", downside_rows, ("portfolio_id",))
    write_csv("reference_drawdown_episode_results.csv", drawdown_rows, ("episode_id",))
    write_csv("monthly_excess_concentration.csv", concentration_rows, ("month",))
    write_csv("neutralization_results.csv", neutralization_rows, ("scenario",))
    write_csv("paired_block_bootstrap_results.csv", bootstrap_rows, ("comparison_portfolio_id",))
    write_csv("turnover_cost_reconciliation.csv", turnover_rows, ("portfolio_id", "cost_bps_one_way"))
    write_csv("invariant_results.csv", invariant_rows, ("invariant_name", "invariant_pass"))

    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "stage": STAGE,
        "approved_route": "20pct_diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "outcome_interpretation": interpretation,
        "exact_next_action": next_action,
        "standalone_outcome_preserved": "closed_exploration",
        "standalone_failure_reason_preserved": "weak_vs_primary_control",
        "independent_validation_claimed": False,
        "paper_demo_onboarding_executed": False,
        "robustness_gate": gate,
    }
    write_csv("outcome_summary.csv", [outcome_row], ("strategy_id", "trial_id", "outcome", "failure_reason"))
    write_csv(
        "failure_reasons.csv",
        [] if not failure_reason else [{
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "robustness_gate": gate,
        }],
        ("strategy_id", "trial_id", "outcome", "failure_reason"),
    )
    write_csv(
        "next_actions.csv",
        [{
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }],
        ("strategy_id", "trial_id", "outcome", "exact_next_action"),
    )
    write_json("cohort_funnel_counts.json", {
        "existing_strategy_configurations_carried_forward": 1,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 1,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "validation_observations": 0,
        "robustness_periods_counted_as_trials": 0,
        "rolling_windows_counted_as_trials": 0,
        "episodes_counted_as_trials": 0,
    })
    (OUTPUT_DIR / "robustness_report.md").write_text(
        build_report(outcome, failure_reason, interpretation, next_action, full, rolling, episode_inventory, leave_summary, bootstrap_rows),
        encoding="utf-8",
    )

    protected_after = protected_snapshot()
    source_after = file_hash(SOURCE_PROMPT)
    output_names_before_consistency = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    required_before_consistency = REQUIRED_FILES - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            reproduction_pass
            and invariants_pass
            and protected_before == protected_after
            and source_before == source_after
            and output_names_before_consistency == required_before_consistency
        ),
        "parent_reproduction_passed": reproduction_pass,
        "all_invariants_passed": invariants_pass,
        "deterministic_rerun_passed": deterministic_rerun_pass,
        "bootstrap_deterministic": bootstrap_deterministic,
        "preregistration_written_before_performance": True,
        "preregistration_artifacts_unchanged": preregistration_unchanged,
        "required_outputs_exact_before_consistency_write": output_names_before_consistency == required_before_consistency,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_and_prior_evidence_unchanged": protected_before == protected_after,
        "source_prompt_hash_before": source_before,
        "source_prompt_hash_after": source_after,
        "source_prompt_unchanged": source_before == source_after,
        "strategy_configurations_created": 0,
        "robustness_trials_created": 1,
        "unselected_variants_evaluated_on_final_segment": False,
        "D1_standalone_closure_changed": False,
        "provider_access": False,
        "network_access": False,
        "lifecycle_state_changed": False,
        "paper_demo_observations_created": 0,
        "validation_observations_created": 0,
        "broker_account_order_or_real_money_actions": 0,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    if {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()} != REQUIRED_FILES:
        consistency["overall_pass"] = False
        consistency["required_outputs_exact_after_consistency_write"] = False
        write_json("consistency_check.json", consistency)
    else:
        consistency["required_outputs_exact_after_consistency_write"] = True
        write_json("consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "outcome_interpretation": interpretation,
        "exact_next_action": next_action,
        "common_period_start": common_index[0].date().isoformat(),
        "common_period_end": common_index[-1].date().isoformat(),
        "reproduction_passed": reproduction_pass,
        "all_invariants_passed": invariants_pass,
        "overall_pass": consistency["overall_pass"],
        "evidence_path": relative(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
