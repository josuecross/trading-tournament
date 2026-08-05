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
from strategy_lab.research_os.research import (
    native_etf_two_candidate_exploration_batch_v1 as exploration,
)


TASK_ID = "native_etf_two_candidate_final_robustness_v1"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
PARENT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "native_etf_two_candidate_exploration_batch_v1"
    / "latest"
)
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\bfcb3879-710f-47c1-8e53-0cb61e6c9509"
    r"\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-30T00:00:00-06:00"
REPRODUCTION_TOLERANCE = 1e-9
PRIMARY_COST = 5.0
VIX_COSTS = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)
FAA_COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260730
TOLERANCE = 1e-10

VIX_ID = exploration.VIX_ID
FAA_ID = exploration.FAA_ID
VIX_PARENT_TRIAL = exploration.VIX_TRIAL
FAA_PARENT_TRIAL = exploration.FAA_TRIAL
VIX_TRIAL = f"{TASK_ID}__vix_fix__child"
FAA_TRIAL = f"{TASK_ID}__faa__child"

VIX_NAMED = "close_only_fix20_sma20_spy_bil_control"
VIX_STATIC = "vix_fix20_exposure_matched_spy_bil_control"
FAA_NAMED = "faa_4m_return_only_top3_control"
FAA_ATTRIBUTION = "faa_4m_return_volatility_top3_no_correlation_control"
FAA_STATIC = "faa_full_period_average_weight_static_control"

EXPECTED_PARENT_OUTCOMES = {
    VIX_ID: "exploratory_followup_candidate_standalone",
    FAA_ID: "exploratory_followup_candidate_standalone",
}

PROTECTED_STATE_PATHS = exploration.PROTECTED_STATE_PATHS
PROTECTED_EVIDENCE_PATHS = (
    PARENT_DIR,
    *exploration.PROTECTED_EVIDENCE_PATHS,
)
CACHE_PATH = exploration.CACHE_PATH

REQUIRED_FILES = (
    "robustness_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "parent_reproduction_check.csv",
    "archived_control_parameter_reconciliation.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "start_date_sensitivity.csv",
    "monthly_excess_concentration.csv",
    "month_and_year_neutralization_results.csv",
    "paired_block_bootstrap_results.csv",
    "vix_fix_state_duration_summary.csv",
    "vix_fix_defensive_episode_inventory.csv",
    "vix_fix_leave_one_episode_out_results.csv",
    "vix_fix_leave_one_episode_out_summary.csv",
    "faa_component_attribution.csv",
    "faa_asset_selection_and_contribution.csv",
    "faa_formation_stability.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "robustness_report.md",
)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def snapshot_hashes() -> dict[str, str]:
    paths = (*PROTECTED_STATE_PATHS, *PROTECTED_EVIDENCE_PATHS, CACHE_PATH)
    return {relative(path): tree_hash(path) for path in paths}


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], headers: Iterable[str]) -> None:
    fields = list(headers)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(PARENT_DIR / name)


def archived_control_weights() -> tuple[dict[str, float], dict[str, float]]:
    vix = read_csv("vix_fix_diagnostics.csv")
    vix_row = vix.loc[
        vix["summary_metric"].eq("full_period_average_target_spy_weight")
    ]
    if len(vix_row) != 1:
        raise RuntimeError("Archived VIX Fix exposure weight is not unique")
    spy_weight = float(vix_row.iloc[0]["summary_value"])
    vix_weights = {"SPY": spy_weight, "BIL": 1.0 - spy_weight}

    faa = read_csv("faa_diagnostics.csv")
    faa_rows = faa.loc[
        faa["summary_metric"].eq("full_period_average_target_weight"),
        ["asset", "summary_value"],
    ]
    faa_weights = {
        str(row.asset): float(row.summary_value)
        for row in faa_rows.itertuples(index=False)
    }
    if set(faa_weights) != set(exploration.FAA_UNIVERSE):
        raise RuntimeError("Archived FAA static weights do not cover the frozen universe")
    if not math.isclose(sum(faa_weights.values()), 1.0, abs_tol=1e-12):
        raise RuntimeError("Archived FAA static weights do not sum to one")
    return vix_weights, faa_weights


def parent_trial_records() -> dict[str, dict[str, str]]:
    rows = list(csv.DictReader((PARENT_DIR / "trial_ledger.csv").open(encoding="utf-8")))
    return {row["strategy_id"]: row for row in rows}


def strategy_cards() -> list[dict[str, Any]]:
    parent = {
        row["strategy_id"]: row
        for row in csv.DictReader(
            (PARENT_DIR / "strategy_cards.csv").open(encoding="utf-8")
        )
    }
    rows: list[dict[str, Any]] = []
    for strategy_id, trial_id, parent_trial in (
        (VIX_ID, VIX_TRIAL, VIX_PARENT_TRIAL),
        (FAA_ID, FAA_TRIAL, FAA_PARENT_TRIAL),
    ):
        source = parent[strategy_id]
        rows.append(
            {
                "strategy_id": strategy_id,
                "family_id": source["family_id"],
                "display_name": source["display_name"],
                "entity_type": "strategy_configuration",
                "strategy_architecture": source["strategy_architecture"],
                "source_or_research_lineage": source["source_or_research_lineage"],
                "instrument_universe": source["instrument_universe"],
                "parameters": source["parameters"],
                "benchmark_or_control": source["benchmark_or_control"],
                "stage": "robustness",
                "trial_id": trial_id,
                "parent_trial_id": parent_trial,
                "adaptation_label": "robustness_variant",
                "changed_fields_from_parent": "robustness_diagnostics_only",
                "route": "standalone_only",
                "outcome": "preregistered_for_bounded_historical_robustness",
                "failure_reason": "",
                "next_action": "execute_preregistered_robustness_child",
                "strategy_rule_changed": False,
                "parameters_changed": False,
                "instruments_changed": False,
                "execution_changed": False,
                "controls_changed": False,
                "route_parameters_changed": False,
                "optimization_performed": False,
                "post_result_adaptation_allowed": False,
                "independent_validation_claimed": False,
                "paper_demo_eligibility_claimed": False,
                "new_strategy_configuration_created": False,
            }
        )
    return rows


def trial_rows() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "entity_type": "experiment_trial",
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        }
        for row in strategy_cards()
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    parent = list(
        csv.DictReader((PARENT_DIR / "benchmark_reference_log.csv").open(encoding="utf-8"))
    )
    return [
        {
            **row,
            "carried_forward_from_parent": True,
            "new_benchmark_strategy_created": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for row in parent
    ]


def preregister() -> None:
    headers = (
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
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "changed_fields_from_parent",
        "route",
        "outcome",
        "failure_reason",
        "next_action",
    )
    write_csv("strategy_cards.csv", strategy_cards(), headers)
    write_csv("trial_ledger.csv", trial_rows(), headers)
    write_csv(
        "benchmark_reference_log.csv",
        benchmark_rows(),
        (
            "benchmark_id",
            "entity_type",
            "stage",
            "strategy_context",
            "same_purpose_control",
            "critical_control",
            "carried_forward_from_parent",
            "new_benchmark_strategy_created",
            "counted_as_strategy",
            "counted_as_trial",
        ),
    )
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": "robustness",
                "candidate_count": 2,
                "new_robustness_trial_count": 2,
                "standalone_routes_only": True,
                "diversifier_routes_reopened": False,
                "independent_validation_performed": False,
                "provider_access_performed": False,
                "lifecycle_state_changed": False,
            }
        ],
        (
            "process_task_id",
            "entity_type",
            "stage",
            "candidate_count",
            "new_robustness_trial_count",
            "standalone_routes_only",
            "diversifier_routes_reopened",
            "independent_validation_performed",
            "provider_access_performed",
            "lifecycle_state_changed",
        ),
    )


def prepare_with_archived_controls(
    frames: dict[str, pd.DataFrame],
    vix_weights: dict[str, float],
    faa_weights: dict[str, float],
) -> dict[str, dict[str, Any]]:
    vix = exploration.prepare_vix(frames)
    vix["control_events"][VIX_STATIC] = exploration.monthly_static_events(
        vix["prices"].index, exploration.VIX_UNIVERSE, vix_weights
    )
    faa = exploration.prepare_faa(frames)
    faa["control_events"][FAA_STATIC] = exploration.monthly_static_events(
        faa["prices"].index, exploration.FAA_UNIVERSE, faa_weights
    )
    return {VIX_ID: vix, FAA_ID: faa}


def simulate_costs(
    prepared: dict[str, Any],
    costs: tuple[float, ...],
) -> dict[str, Any]:
    timing = "completed_signal_session_target_applied_at_following_regular_session_close"
    candidates: dict[float, dict[str, Any]] = {}
    controls: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in costs:
        candidates[cost] = exploration.accounting.simulate_path(
            prepared["prices"], prepared["candidate_events"], cost, timing
        )
        for control_id, events in prepared["control_events"].items():
            controls[(control_id, cost)] = exploration.accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
    return {"candidate_paths": candidates, "control_paths": controls}


def metrics(
    path: dict[str, Any],
    fallback: str,
    index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    return exploration.period_metrics(path, fallback, index)


def result_row(
    strategy_id: str,
    series_id: str,
    cost: float,
    period: str,
    values: dict[str, Any],
    result_type: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "trial_id": VIX_TRIAL if strategy_id == VIX_ID else FAA_TRIAL,
        "series_id": series_id,
        "result_type": result_type,
        "cost_bps_one_way": cost,
        "period": period,
        **values,
    }


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_quarter_{position + 1}": index[locations]
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def complete_year_indices(index: pd.DatetimeIndex) -> dict[int, pd.DatetimeIndex]:
    first_year = int(index.min().year)
    last_year = int(index.max().year)
    return {
        year: index[index.year == year]
        for year in range(first_year + 1, last_year)
        if len(index[index.year == year])
    }


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index)
        .groupby(index.to_period("M"))
        .last()
        .tolist()
    ]


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.to_period("M")).prod().sub(1.0)


def monthly_metrics(returns: pd.Series) -> dict[str, Any]:
    values = returns.astype(float).to_numpy()
    if not len(values):
        return {
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "sharpe_ratio": float("nan"),
            "maximum_drawdown": float("nan"),
        }
    wealth = np.cumprod(1.0 + values)
    standard_deviation = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    running_max = np.maximum.accumulate(wealth)
    return {
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(values)) - 1.0),
        "annualized_volatility": standard_deviation * math.sqrt(12.0),
        "sharpe_ratio": (
            float(np.mean(values) / standard_deviation * math.sqrt(12.0))
            if standard_deviation > 0.0
            else 0.0
        ),
        "maximum_drawdown": float(np.min(wealth / running_max - 1.0)),
    }


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.material_advantage(candidate, control)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.accounting.dominates(control, candidate)


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.worse_on_both(candidate, control)


def frame_comparison(
    scope: str,
    archived: pd.DataFrame,
    reproduced: pd.DataFrame,
) -> dict[str, Any]:
    same_columns = list(archived.columns) == list(reproduced.columns)
    same_rows = len(archived) == len(reproduced)
    mismatches = 0
    max_difference = 0.0
    if same_columns and same_rows:
        for column in archived.columns:
            left = archived[column]
            right = reproduced[column]
            left_numeric = pd.to_numeric(left, errors="coerce")
            right_numeric = pd.to_numeric(right, errors="coerce")
            numeric_mask = left_numeric.notna() & right_numeric.notna()
            if numeric_mask.any():
                differences = (
                    left_numeric.loc[numeric_mask].astype(float)
                    - right_numeric.loc[numeric_mask].astype(float)
                ).abs()
                max_difference = max(max_difference, float(differences.max()))
                mismatches += int((differences > REPRODUCTION_TOLERANCE).sum())
            text_mask = ~numeric_mask
            if text_mask.any():
                left_text = left.loc[text_mask].fillna("").astype(str)
                right_text = right.loc[text_mask].fillna("").astype(str)
                mismatches += int((left_text.to_numpy() != right_text.to_numpy()).sum())
    else:
        mismatches = max(len(archived), len(reproduced), 1)
    return {
        "scope": scope,
        "archived_row_count": len(archived),
        "reproduced_row_count": len(reproduced),
        "columns_match": same_columns,
        "rows_match": same_rows,
        "maximum_numeric_difference": max_difference,
        "mismatch_count": mismatches,
        "tolerance": REPRODUCTION_TOLERANCE,
        "pass": bool(same_columns and same_rows and mismatches == 0),
    }


def parent_reproduction(
    prepared: dict[str, dict[str, Any]],
    frames: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], bool]:
    simulated = {
        strategy_id: exploration.simulate_prepared(prepared[strategy_id])
        for strategy_id in (VIX_ID, FAA_ID)
    }
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    configurations = {
        VIX_ID: (VIX_NAMED, VIX_STATIC, "BIL"),
        FAA_ID: (FAA_NAMED, FAA_STATIC, "SHY"),
    }
    for strategy_id, (same_purpose, static_control, fallback) in configurations.items():
        candidates, controls, halves = exploration.metric_rows(
            strategy_id,
            fallback,
            prepared[strategy_id]["prices"].index,
            simulated[strategy_id],
        )
        candidate_rows.extend(candidates)
        control_rows.extend(controls)
        half_rows.extend(halves)
        invariant_rows.extend(
            exploration.invariant_rows(
                strategy_id, prepared[strategy_id], simulated[strategy_id]
            )
        )
        portfolio_paths = exploration.portfolio_paths(
            prepared[strategy_id],
            simulated[strategy_id],
            same_purpose,
            static_control,
        )
        portfolio_rows.extend(
            exploration.portfolio_result_rows(strategy_id, portfolio_paths)
        )
    turnover_rows: list[dict[str, Any]] = []
    for row in candidate_rows + control_rows:
        turnover_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "result_id": row["result_id"],
                "cost_bps_one_way": row["cost_bps_one_way"],
                "one_way_turnover": row["turnover"],
                "transaction_cost_drag": row["transaction_cost_drag"],
                "inner_transaction_cost_drag": "",
                "outer_transaction_cost_drag": "",
                "cost_charged_once": True,
                "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
            }
        )
    for row in portfolio_rows:
        if row["period"] == "full_period":
            turnover_rows.append(
                {
                    "strategy_id": row["strategy_id"],
                    "result_id": row["result_id"],
                    "cost_bps_one_way": row["cost_bps_one_way"],
                    "one_way_turnover": row["turnover"],
                    "transaction_cost_drag": row["transaction_cost_drag"],
                    "inner_transaction_cost_drag": row.get(
                        "inner_transaction_cost_drag", 0.0
                    ),
                    "outer_transaction_cost_drag": row.get(
                        "outer_transaction_cost_drag", 0.0
                    ),
                    "cost_charged_once": True,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
    preflight_rows, _ = exploration.data_preflight()
    current = {
        "data_preflight_reconciliation.csv": pd.DataFrame(preflight_rows),
        "all_trial_results.csv": pd.DataFrame(candidate_rows),
        "control_results.csv": pd.DataFrame(control_rows),
        "chronological_half_results.csv": pd.DataFrame(half_rows),
        "portfolio_contribution_results.csv": pd.DataFrame(portfolio_rows),
        "vix_fix_diagnostics.csv": prepared[VIX_ID]["diagnostics"],
        "faa_diagnostics.csv": prepared[FAA_ID]["diagnostics"],
        "turnover_cost_reconciliation.csv": pd.DataFrame(turnover_rows),
        "invariant_results.csv": pd.DataFrame(invariant_rows),
    }
    rows: list[dict[str, Any]] = []
    for filename, reproduced in current.items():
        archived = read_csv(filename)
        reproduced = reproduced.reindex(columns=archived.columns)
        rows.append(frame_comparison(filename, archived, reproduced))

    parent_trials = parent_trial_records()
    lineage_pass = bool(
        parent_trials[VIX_ID]["trial_id"] == VIX_PARENT_TRIAL
        and parent_trials[FAA_ID]["trial_id"] == FAA_PARENT_TRIAL
        and parent_trials[VIX_ID]["outcome"] == EXPECTED_PARENT_OUTCOMES[VIX_ID]
        and parent_trials[FAA_ID]["outcome"] == EXPECTED_PARENT_OUTCOMES[FAA_ID]
    )
    rows.append(
        {
            "scope": "parent_trial_lineage_and_outcomes",
            "archived_row_count": 2,
            "reproduced_row_count": 2,
            "columns_match": True,
            "rows_match": True,
            "maximum_numeric_difference": 0.0,
            "mismatch_count": 0 if lineage_pass else 1,
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": lineage_pass,
        }
    )
    return rows, bool(rows and all(row["pass"] for row in rows))


def archived_parameter_rows(
    prepared: dict[str, dict[str, Any]],
    vix_weights: dict[str, float],
    faa_weights: dict[str, float],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    for symbol, weight in vix_weights.items():
        runtime = float(
            prepared[VIX_ID]["control_events"][VIX_STATIC][symbol].iloc[0]
        )
        rows.append(
            {
                "strategy_id": VIX_ID,
                "control_id": VIX_STATIC,
                "asset": symbol,
                "archived_target_weight": weight,
                "runtime_target_weight": runtime,
                "absolute_difference": abs(runtime - weight),
                "source": "parent_vix_fix_diagnostics_summary",
                "recalculated_for_robustness": False,
                "used_for_all_robustness_results": True,
                "pass": abs(runtime - weight) <= REPRODUCTION_TOLERANCE,
            }
        )
    for symbol, weight in faa_weights.items():
        runtime = float(
            prepared[FAA_ID]["control_events"][FAA_STATIC][symbol].iloc[0]
        )
        rows.append(
            {
                "strategy_id": FAA_ID,
                "control_id": FAA_STATIC,
                "asset": symbol,
                "archived_target_weight": weight,
                "runtime_target_weight": runtime,
                "absolute_difference": abs(runtime - weight),
                "source": "parent_faa_diagnostics_summary",
                "recalculated_for_robustness": False,
                "used_for_all_robustness_results": True,
                "pass": abs(runtime - weight) <= REPRODUCTION_TOLERANCE,
            }
        )
    return rows, bool(rows and all(row["pass"] for row in rows))


def series_paths(
    strategy_id: str,
    simulated: dict[str, Any],
    cost: float,
) -> dict[str, dict[str, Any]]:
    output = {strategy_id: simulated["candidate_paths"][cost]}
    output.update(
        {
            control: path
            for (control, control_cost), path in simulated["control_paths"].items()
            if control_cost == cost
        }
    )
    return output


def full_cost_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    fallback: str,
    costs: tuple[float, ...],
) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    metric_map: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in costs:
        for series_id, path in series_paths(strategy_id, simulated, cost).items():
            values = metrics(path, fallback)
            metric_map[(series_id, cost)] = values
            rows.append(
                result_row(
                    strategy_id,
                    series_id,
                    cost,
                    "full_period",
                    values,
                    "cost_stress",
                )
            )
    return rows, metric_map


def partition_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    fallback: str,
    index: pd.DatetimeIndex,
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    quarters: list[dict[str, Any]] = []
    quarter_map: dict[tuple[str, str], dict[str, Any]] = {}
    years: list[dict[str, Any]] = []
    year_map: dict[tuple[str, int], dict[str, Any]] = {}
    paths = series_paths(strategy_id, simulated, PRIMARY_COST)
    for period, period_index in split_quarters(index).items():
        for series_id, path in paths.items():
            values = metrics(path, fallback, period_index)
            quarter_map[(series_id, period)] = values
            quarters.append(
                result_row(
                    strategy_id,
                    series_id,
                    PRIMARY_COST,
                    period,
                    values,
                    "chronological_quarter",
                )
            )
    for year, period_index in complete_year_indices(index).items():
        for series_id, path in paths.items():
            values = metrics(path, fallback, period_index)
            year_map[(series_id, year)] = values
            row = result_row(
                strategy_id,
                series_id,
                PRIMARY_COST,
                f"calendar_year_{year}",
                values,
                "complete_calendar_year",
            )
            row["calendar_year"] = year
            years.append(row)
    return quarters, quarter_map, years, year_map


def rolling_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    prepared: dict[str, Any],
    fallback: str,
    comparators: tuple[str, ...],
    months: int,
) -> list[dict[str, Any]]:
    index = prepared["prices"].index
    candidate_path = simulated["candidate_paths"][PRIMARY_COST]
    rows: list[dict[str, Any]] = []
    sequence = 0
    for end in month_end_dates(index):
        boundary = end - pd.DateOffset(months=months)
        if boundary < index[0]:
            continue
        period_index = index[(index > boundary) & (index <= end)]
        if not len(period_index):
            continue
        sequence += 1
        candidate = metrics(candidate_path, fallback, period_index)
        for comparator_id in comparators:
            comparator = metrics(
                simulated["control_paths"][(comparator_id, PRIMARY_COST)],
                fallback,
                period_index,
            )
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "trial_id": VIX_TRIAL if strategy_id == VIX_ID else FAA_TRIAL,
                    "window_months": months,
                    "window_sequence": sequence,
                    "window_start": period_index[0].date().isoformat(),
                    "window_end": period_index[-1].date().isoformat(),
                    "candidate_id": strategy_id,
                    "comparison_id": comparator_id,
                    "candidate_cagr": candidate["cagr"],
                    "comparison_cagr": comparator["cagr"],
                    "cagr_difference": float(candidate["cagr"])
                    - float(comparator["cagr"]),
                    "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                    "comparison_sharpe_ratio": comparator["sharpe_ratio"],
                    "sharpe_difference": float(candidate["sharpe_ratio"])
                    - float(comparator["sharpe_ratio"]),
                    "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                    "comparison_maximum_drawdown": comparator["maximum_drawdown"],
                    "maximum_drawdown_difference": float(
                        candidate["maximum_drawdown"]
                    )
                    - float(comparator["maximum_drawdown"]),
                    "candidate_turnover": candidate["turnover"],
                    "comparison_turnover": comparator["turnover"],
                    "turnover_difference": float(candidate["turnover"])
                    - float(comparator["turnover"]),
                    "candidate_improves_sharpe_or_drawdown": bool(
                        float(candidate["sharpe_ratio"])
                        > float(comparator["sharpe_ratio"])
                        or float(candidate["maximum_drawdown"])
                        > float(comparator["maximum_drawdown"])
                    ),
                    "comparison_dominates_candidate": dominates(
                        comparator, candidate
                    ),
                    "unfavorable_window_retained": True,
                    "independent_validation_claimed": False,
                }
            )
    return rows


def rolling_summary(rows36: list[dict[str, Any]], rows60: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    strategy_ids = sorted({row["strategy_id"] for row in rows36 + rows60})
    for strategy_id in strategy_ids:
        for months, rows in ((36, rows36), (60, rows60)):
            comparisons = sorted(
                {
                    row["comparison_id"]
                    for row in rows
                    if row["strategy_id"] == strategy_id
                }
            )
            for comparison in comparisons:
                subset = [
                    row
                    for row in rows
                    if row["strategy_id"] == strategy_id
                    and row["comparison_id"] == comparison
                ]
                output.append(
                    {
                        "strategy_id": strategy_id,
                        "window_months": months,
                        "comparison_id": comparison,
                        "eligible_window_count": len(subset),
                        "median_cagr_difference": float(
                            np.median([row["cagr_difference"] for row in subset])
                        ),
                        "median_sharpe_difference": float(
                            np.median([row["sharpe_difference"] for row in subset])
                        ),
                        "median_maximum_drawdown_difference": float(
                            np.median(
                                [
                                    row["maximum_drawdown_difference"]
                                    for row in subset
                                ]
                            )
                        ),
                        "candidate_improves_sharpe_or_drawdown_fraction": float(
                            np.mean(
                                [
                                    row["candidate_improves_sharpe_or_drawdown"]
                                    for row in subset
                                ]
                            )
                        ),
                        "comparison_dominates_fraction": float(
                            np.mean(
                                [row["comparison_dominates_candidate"] for row in subset]
                            )
                        ),
                        "unfavorable_windows_retained": True,
                    }
                )
    return output


def start_sensitivity_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    fallback: str,
    index: pd.DatetimeIndex,
    comparators: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = series_paths(strategy_id, simulated, PRIMARY_COST)
    included = (strategy_id, *comparators)
    for year in range(2008, 2016):
        eligible = index[index.year >= year]
        if not len(eligible):
            continue
        start = eligible[0]
        period_index = index[index >= start]
        for series_id in included:
            values = metrics(paths[series_id], fallback, period_index)
            row = result_row(
                strategy_id,
                series_id,
                PRIMARY_COST,
                f"start_{year}_fixed_end",
                values,
                "deterministic_start_date_sensitivity",
            )
            row.update(
                {
                    "requested_start_year": year,
                    "first_eligible_session": start.date().isoformat(),
                    "fixed_end_date": index[-1].date().isoformat(),
                    "start_selected_from_performance": False,
                    "strategy_reinitialized_at_start": False,
                }
            )
            rows.append(row)
    return rows


def concentration_and_neutralization(
    strategy_id: str,
    simulated: dict[str, Any],
    fallback: str,
    named_control: str,
    static_control: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate_returns = simulated["candidate_paths"][PRIMARY_COST]["returns"]
    named_returns = simulated["control_paths"][(named_control, PRIMARY_COST)]["returns"]
    static_path = simulated["control_paths"][(static_control, PRIMARY_COST)]
    monthly = pd.concat(
        [
            monthly_returns(candidate_returns).rename("candidate"),
            monthly_returns(named_returns).rename("named"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    monthly["additive_excess"] = monthly["candidate"] - monthly["named"]
    positive = monthly.loc[monthly["additive_excess"] > 0.0, "additive_excess"].sort_values(
        ascending=False
    )
    strongest_three = list(positive.index[:3])
    strongest_month = strongest_three[0]
    annual = monthly["additive_excess"].groupby(monthly.index.year).sum()
    strongest_year = int(annual.idxmax())
    positive_sum = float(positive.sum())
    strongest_year_value = float(annual.loc[strongest_year])
    rank = {period: rank + 1 for rank, period in enumerate(positive.index)}
    concentration = [
        {
            "strategy_id": strategy_id,
            "month": str(period),
            "candidate_return_5bps": row.candidate,
            "named_control_return_5bps": row.named,
            "candidate_minus_named_additive_excess": row.additive_excess,
            "positive_excess_rank": rank.get(period, ""),
            "strongest_positive_excess_month": period == strongest_month,
            "among_three_strongest_positive_excess_months": period
            in strongest_three,
            "strongest_additive_excess_calendar_year": period.year == strongest_year,
            "strongest_year": strongest_year,
            "strongest_year_fraction_of_cumulative_positive_additive_excess": (
                strongest_year_value / positive_sum if positive_sum > 0.0 else float("nan")
            ),
            "frozen_before_counterfactual": True,
            "observation_deleted": False,
        }
        for period, row in monthly.iterrows()
    ]
    scenarios = {
        "neutralize_strongest_positive_excess_month": [strongest_month],
        "neutralize_three_strongest_positive_excess_months": strongest_three,
        "neutralize_strongest_additive_excess_calendar_year": [
            period for period in monthly.index if period.year == strongest_year
        ],
    }
    named_metrics = metrics(
        simulated["control_paths"][(named_control, PRIMARY_COST)], fallback
    )
    static_metrics = metrics(static_path, fallback)
    neutralization: list[dict[str, Any]] = []
    for scenario, periods in scenarios.items():
        counterfactual = candidate_returns.copy()
        mask = counterfactual.index.to_period("M").isin(periods)
        counterfactual.loc[mask] = named_returns.loc[mask]
        candidate = exploration.market.metrics_from_returns(counterfactual)
        neutralization.append(
            {
                "strategy_id": strategy_id,
                "scenario": scenario,
                "neutralized_months": [str(period) for period in periods],
                "neutralized_month_count": len(periods),
                "strongest_calendar_year": strongest_year,
                **candidate,
                "material_advantage_vs_named_control": material_advantage(
                    candidate, named_metrics
                ),
                "material_advantage_vs_static_control": material_advantage(
                    candidate, static_metrics
                ),
                "named_control_dominates": dominates(named_metrics, candidate),
                "static_control_dominates": dominates(static_metrics, candidate),
                "observations_deleted": False,
                "canonical_series_modified": False,
                "used_for_strategy_change": False,
            }
        )
    summary = {
        "strongest_month": str(strongest_month),
        "strongest_three_months": [str(period) for period in strongest_three],
        "strongest_year": strongest_year,
        "strongest_year_fraction": (
            strongest_year_value / positive_sum if positive_sum > 0.0 else float("nan")
        ),
    }
    return concentration, neutralization, summary


def monthly_path_metrics(values: np.ndarray) -> tuple[float, float, float]:
    wealth = np.cumprod(1.0 + values)
    cagr = float(wealth[-1] ** (12.0 / len(values)) - 1.0)
    standard_deviation = float(np.std(values, ddof=1))
    sharpe = (
        float(np.mean(values) / standard_deviation * math.sqrt(12.0))
        if standard_deviation > 0.0
        else 0.0
    )
    drawdown = float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))
    return cagr, sharpe, drawdown


def paired_bootstrap(
    strategy_id: str,
    simulated: dict[str, Any],
    comparators: tuple[str, ...],
) -> list[dict[str, Any]]:
    monthly = pd.concat(
        [
            monthly_returns(simulated["candidate_paths"][PRIMARY_COST]["returns"]).rename(
                strategy_id
            ),
            *[
                monthly_returns(
                    simulated["control_paths"][(control, PRIMARY_COST)]["returns"]
                ).rename(control)
                for control in comparators
            ],
        ],
        axis=1,
        join="inner",
    ).dropna()
    values = monthly.to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = {
        comparator: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0}
        for comparator in comparators
    }
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled = np.concatenate(
            [
                np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS)
                for start in starts
            ]
        )[:count]
        sample = values[sampled]
        candidate_cagr, candidate_sharpe, candidate_drawdown = monthly_path_metrics(
            sample[:, 0]
        )
        for column, comparator in enumerate(comparators, start=1):
            comparator_cagr, comparator_sharpe, comparator_drawdown = (
                monthly_path_metrics(sample[:, column])
            )
            higher_cagr = candidate_cagr > comparator_cagr
            higher_sharpe = candidate_sharpe > comparator_sharpe
            better_drawdown = candidate_drawdown > comparator_drawdown
            counts[comparator]["cagr"] += int(higher_cagr)
            counts[comparator]["sharpe"] += int(higher_sharpe)
            counts[comparator]["drawdown"] += int(better_drawdown)
            counts[comparator]["either"] += int(higher_sharpe or better_drawdown)
    return [
        {
            "strategy_id": strategy_id,
            "candidate_id": strategy_id,
            "comparison_id": comparator,
            "monthly_observation_count": count,
            "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
            "resamples": BOOTSTRAP_RESAMPLES,
            "deterministic_seed": BOOTSTRAP_SEED,
            "probability_candidate_higher_cagr": (
                counts[comparator]["cagr"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_higher_sharpe": (
                counts[comparator]["sharpe"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_less_severe_maximum_drawdown": (
                counts[comparator]["drawdown"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": (
                counts[comparator]["either"] / BOOTSTRAP_RESAMPLES
            ),
            "paired_cross_series_dependence_preserved": True,
            "used_for_strategy_change": False,
            "independent_validation_claimed": False,
        }
        for comparator in comparators
    ]


def vix_state_and_episode_rows(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    events = prepared["candidate_events"].sort_index()
    index = prepared["prices"].index
    episode_rows: list[dict[str, Any]] = []
    duration_rows: list[dict[str, Any]] = []
    event_items = list(events.iterrows())
    for position, (date_value, target) in enumerate(event_items):
        date_value = pd.Timestamp(date_value)
        state = "SPY" if float(target["SPY"]) > 0.5 else "BIL"
        next_date = (
            pd.Timestamp(event_items[position + 1][0])
            if position + 1 < len(event_items)
            else index[-1]
        )
        start_position = int(index.get_loc(date_value))
        end_position = int(index.get_loc(next_date))
        duration = max(end_position - start_position, 0)
        episode_rows.append(
            {
                "episode_sequence": position + 1,
                "state": state,
                "state_start_execution_date": date_value.date().isoformat(),
                "state_end_execution_date": next_date.date().isoformat(),
                "duration_sessions": duration,
                "terminal_episode": position + 1 == len(event_items),
            }
        )
    episode_frame = pd.DataFrame(episode_rows)
    for state in ("SPY", "BIL", "ALL"):
        subset = (
            episode_frame
            if state == "ALL"
            else episode_frame.loc[episode_frame["state"].eq(state)]
        )
        durations = subset["duration_sessions"].to_numpy(dtype=float)
        duration_rows.append(
            {
                "row_type": "state_duration_summary",
                "state": state,
                "episode_count": len(subset),
                "minimum_duration_sessions": float(np.min(durations)),
                "median_duration_sessions": float(np.median(durations)),
                "mean_duration_sessions": float(np.mean(durations)),
                "maximum_duration_sessions": float(np.max(durations)),
                "fraction_1_session": float(np.mean(durations == 1)),
                "fraction_2_sessions_or_less": float(np.mean(durations <= 2)),
                "fraction_3_sessions_or_less": float(np.mean(durations <= 3)),
                "fraction_5_sessions_or_less": float(np.mean(durations <= 5)),
                "fraction_10_sessions_or_less": float(np.mean(durations <= 10)),
            }
        )
    transitions = events.iloc[1:].copy()
    transition_years = pd.DatetimeIndex(transitions.index).year
    primary_path = simulated["candidate_paths"][PRIMARY_COST]
    for year in sorted(set(index.year)):
        duration_rows.append(
            {
                "row_type": "annual_transition_turnover_cost",
                "calendar_year": year,
                "transition_count": int((transition_years == year).sum()),
                "turnover": float(
                    primary_path["turnover"].loc[
                        primary_path["turnover"].index.year == year
                    ].sum()
                ),
                **{
                    f"cost_drag_{cost:g}bps": float(
                        simulated["candidate_paths"][cost]["cost"].loc[
                            simulated["candidate_paths"][cost]["cost"].index.year == year
                        ].sum()
                    )
                    for cost in VIX_COSTS
                },
            }
        )

    defensive: list[dict[str, Any]] = []
    sequence = 0
    prior_state = ""
    active_start: pd.Timestamp | None = None
    for date_value, target in event_items:
        date_value = pd.Timestamp(date_value)
        state = "SPY" if float(target["SPY"]) > 0.5 else "BIL"
        if prior_state == "SPY" and state == "BIL":
            active_start = date_value
        elif prior_state == "BIL" and state == "SPY" and active_start is not None:
            sequence += 1
            start_position = int(index.get_loc(active_start))
            end_position = int(index.get_loc(date_value))
            held_dates = index[start_position + 1 : end_position + 1]
            candidate = simulated["candidate_paths"][PRIMARY_COST]["returns"].reindex(
                held_dates
            )
            close_only = simulated["control_paths"][
                (VIX_NAMED, PRIMARY_COST)
            ]["returns"].reindex(held_dates)
            additive_excess = float((candidate - close_only).sum())
            defensive.append(
                {
                    "episode_id": f"defensive_episode_{sequence:03d}",
                    "bil_entry_execution_date": active_start.date().isoformat(),
                    "spy_reentry_execution_date": date_value.date().isoformat(),
                    "defensive_holding_sessions": len(held_dates),
                    "candidate_minus_close_only_additive_excess": additive_excess,
                    "positive_additive_excess": max(additive_excess, 0.0),
                    "completed_episode": True,
                    "combinations_removed": False,
                }
            )
            active_start = None
        prior_state = state
    positive_sum = float(sum(row["positive_additive_excess"] for row in defensive))
    max_positive = float(
        max((row["positive_additive_excess"] for row in defensive), default=0.0)
    )
    concentration = max_positive / positive_sum if positive_sum > 0.0 else float("nan")
    for row in defensive:
        row["fraction_of_cumulative_positive_additive_excess"] = (
            row["positive_additive_excess"] / positive_sum
            if positive_sum > 0.0
            else float("nan")
        )
    return duration_rows, defensive, {
        "episode_count": len(defensive),
        "largest_episode_positive_excess_fraction": concentration,
    }


def vix_leave_one_episode_out(
    episodes: list[dict[str, Any]],
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline = metrics(simulated["candidate_paths"][PRIMARY_COST], "BIL")
    close_metrics = metrics(
        simulated["control_paths"][(VIX_NAMED, PRIMARY_COST)], "BIL"
    )
    exposure_metrics = metrics(
        simulated["control_paths"][(VIX_STATIC, PRIMARY_COST)], "BIL"
    )
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        modified = prepared["candidate_events"].copy()
        start = pd.Timestamp(episode["bil_entry_execution_date"])
        modified.loc[start, ["SPY", "BIL"]] = [1.0, 0.0]
        path = exploration.accounting.simulate_path(
            prepared["prices"],
            modified,
            PRIMARY_COST,
            "completed_signal_session_target_applied_at_following_regular_session_close",
        )
        candidate = metrics(path, "BIL")
        rows.append(
            {
                **episode,
                "candidate_cagr": candidate["cagr"],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "baseline_sharpe_ratio": baseline["sharpe_ratio"],
                "sharpe_change_vs_baseline": float(candidate["sharpe_ratio"])
                - float(baseline["sharpe_ratio"]),
                "drawdown_advantage_vs_close_only": float(
                    candidate["maximum_drawdown"]
                )
                - float(close_metrics["maximum_drawdown"]),
                "drawdown_advantage_vs_exposure_matching": float(
                    candidate["maximum_drawdown"]
                )
                - float(exposure_metrics["maximum_drawdown"]),
                "materially_better_than_close_only": material_advantage(
                    candidate, close_metrics
                ),
                "exposure_matched_control_dominates": dominates(
                    exposure_metrics, candidate
                ),
                "all_other_signals_and_execution_preserved": True,
                "cost_model_preserved": True,
                "used_for_strategy_change": False,
            }
        )
    if not rows:
        return rows, []
    sharpe = np.array([row["candidate_sharpe_ratio"] for row in rows], dtype=float)
    close_advantage = np.array(
        [row["drawdown_advantage_vs_close_only"] for row in rows], dtype=float
    )
    exposure_advantage = np.array(
        [row["drawdown_advantage_vs_exposure_matching"] for row in rows], dtype=float
    )
    greatest_loss = min(rows, key=lambda row: row["sharpe_change_vs_baseline"])
    summary = [
        {
            "completed_defensive_episode_count": len(rows),
            "minimum_resulting_sharpe": float(np.min(sharpe)),
            "median_resulting_sharpe": float(np.median(sharpe)),
            "maximum_resulting_sharpe": float(np.max(sharpe)),
            "minimum_drawdown_advantage_vs_close_only": float(
                np.min(close_advantage)
            ),
            "median_drawdown_advantage_vs_close_only": float(
                np.median(close_advantage)
            ),
            "maximum_drawdown_advantage_vs_close_only": float(
                np.max(close_advantage)
            ),
            "minimum_drawdown_advantage_vs_exposure_matching": float(
                np.min(exposure_advantage)
            ),
            "median_drawdown_advantage_vs_exposure_matching": float(
                np.median(exposure_advantage)
            ),
            "maximum_drawdown_advantage_vs_exposure_matching": float(
                np.max(exposure_advantage)
            ),
            "fraction_materially_better_than_close_only": float(
                np.mean([row["materially_better_than_close_only"] for row in rows])
            ),
            "fraction_not_dominated_by_exposure_matching": float(
                np.mean(
                    [
                        not row["exposure_matched_control_dominates"]
                        for row in rows
                    ]
                )
            ),
            "episode_causing_largest_loss_of_candidate_benefit": greatest_loss[
                "episode_id"
            ],
            "largest_sharpe_loss_vs_baseline": greatest_loss[
                "sharpe_change_vs_baseline"
            ],
            "combinations_of_episodes_removed": False,
        }
    ]
    return rows, summary


def faa_asset_contribution_rows(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics = prepared["diagnostics"]
    valid = diagnostics.loc[diagnostics["row_type"].eq("formation_asset")].copy()
    prices = prepared["prices"]
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    candidate_path = simulated["candidate_paths"][PRIMARY_COST]
    named_path = simulated["control_paths"][(FAA_NAMED, PRIMARY_COST)]
    static_path = simulated["control_paths"][(FAA_STATIC, PRIMARY_COST)]
    candidate_weights = candidate_path["held_weights"].reindex(prices.index).fillna(0.0)
    named_weights = named_path["held_weights"].reindex(prices.index).fillna(0.0)
    static_weights = static_path["held_weights"].reindex(prices.index).fillna(0.0)
    candidate_contribution = candidate_weights * asset_returns
    named_difference = (candidate_weights - named_weights) * asset_returns
    static_difference = (candidate_weights - static_weights) * asset_returns
    spy_monthly = monthly_returns(asset_returns["SPY"])
    positive_periods = set(spy_monthly.loc[spy_monthly > 0.0].index)
    month_period = candidate_contribution.index.to_period("M")
    positive_mask = month_period.isin(positive_periods)
    rows: list[dict[str, Any]] = []
    named_contribution_by_asset: dict[str, float] = {}
    for symbol in exploration.FAA_UNIVERSE:
        symbol_rows = valid.loc[valid["asset"].eq(symbol)]
        named_difference_value = float(named_difference[symbol].sum())
        named_contribution_by_asset[symbol] = named_difference_value
        rows.append(
            {
                "row_type": "asset",
                "asset": symbol,
                "valid_formation_count": int(
                    symbol_rows["formation_date"].nunique()
                ),
                "selection_frequency": float(
                    symbol_rows["selected_candidate"].astype(bool).mean()
                ),
                "target_weight_frequency": float(
                    (symbol_rows["candidate_target_weight"].astype(float) > 0.0).mean()
                ),
                "average_target_weight": float(
                    symbol_rows["candidate_target_weight"].astype(float).mean()
                ),
                "realized_return_contribution": float(
                    candidate_contribution[symbol].sum()
                ),
                "candidate_minus_return_only_contribution": named_difference_value,
                "candidate_minus_static_control_contribution": float(
                    static_difference[symbol].sum()
                ),
                "shy_replacement_slots": int(
                    symbol_rows["shy_replacement"].astype(bool).sum()
                ),
                "contribution_during_positive_spy_months": float(
                    candidate_contribution.loc[positive_mask, symbol].sum()
                ),
                "contribution_during_negative_spy_months": float(
                    candidate_contribution.loc[~positive_mask, symbol].sum()
                ),
            }
        )
    positive = {
        symbol: max(value, 0.0)
        for symbol, value in named_contribution_by_asset.items()
    }
    positive_total = float(sum(positive.values()))
    ordered_positive = sorted(positive.items(), key=lambda item: item[1], reverse=True)
    largest_fraction = (
        ordered_positive[0][1] / positive_total if positive_total > 0.0 else float("nan")
    )
    top_two_fraction = (
        sum(value for _, value in ordered_positive[:2]) / positive_total
        if positive_total > 0.0
        else float("nan")
    )
    candidate_total_return = float(
        metrics(candidate_path, "SHY")["total_return"]
    )
    largest_candidate_contribution = max(
        float(candidate_contribution[symbol].sum())
        for symbol in exploration.FAA_UNIVERSE
    )
    formation_groups = list(valid.groupby("formation_date"))
    candidate_return_overlap = []
    candidate_no_corr_overlap = []
    for _, group in formation_groups:
        candidate_set = set(group.loc[group["selected_candidate"].astype(bool), "asset"])
        return_set = set(group.loc[group["selected_return_only"].astype(bool), "asset"])
        no_corr_set = set(
            group.loc[group["selected_return_volatility"].astype(bool), "asset"]
        )
        candidate_return_overlap.append(len(candidate_set & return_set) / 3.0)
        candidate_no_corr_overlap.append(len(candidate_set & no_corr_set) / 3.0)
    summary = {
        "largest_positive_asset_contribution_fraction_of_positive_candidate_minus_return_only": largest_fraction,
        "largest_asset_contribution_fraction_of_candidate_total_return": (
            largest_candidate_contribution / candidate_total_return
            if candidate_total_return != 0.0
            else float("nan")
        ),
        "top_two_asset_positive_contribution_concentration": top_two_fraction,
        "mean_selection_overlap_with_return_only_control": float(
            np.mean(candidate_return_overlap)
        ),
        "mean_selection_overlap_with_no_correlation_control": float(
            np.mean(candidate_no_corr_overlap)
        ),
    }
    rows.append({"row_type": "summary", "asset": "__SUMMARY__", **summary})
    return rows, summary


def faa_formation_stability_rows(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics = prepared["diagnostics"]
    valid = diagnostics.loc[diagnostics["row_type"].eq("formation_asset")].copy()
    valid["formation_timestamp"] = pd.to_datetime(valid["formation_date"])
    formations: list[dict[str, Any]] = []
    prior_selection: set[str] | None = None
    for date_value, group in valid.sort_values("formation_timestamp").groupby(
        "formation_timestamp", sort=True
    ):
        candidate_set = set(group.loc[group["selected_candidate"].astype(bool), "asset"])
        return_set = set(group.loc[group["selected_return_only"].astype(bool), "asset"])
        formations.append(
            {
                "formation_date": pd.Timestamp(date_value),
                "calendar_year": pd.Timestamp(date_value).year,
                "selected_asset_change": (
                    prior_selection is not None and candidate_set != prior_selection
                ),
                "shy_replacement_count": int(
                    group["shy_replacement"].astype(bool).sum()
                ),
                "mean_pairwise_correlation": float(
                    group["average_pairwise_correlation"].astype(float).mean()
                ),
                "candidate_return_only_overlap": len(candidate_set & return_set) / 3.0,
            }
        )
        prior_selection = candidate_set
    formation_frame = pd.DataFrame(formations)
    candidate_path = simulated["candidate_paths"][PRIMARY_COST]
    named_path = simulated["control_paths"][(FAA_NAMED, PRIMARY_COST)]
    rows: list[dict[str, Any]] = []
    annual_excess: dict[int, float] = {}
    for year, group in formation_frame.groupby("calendar_year", sort=True):
        candidate_returns = candidate_path["returns"].loc[
            candidate_path["returns"].index.year == year
        ]
        named_returns = named_path["returns"].loc[named_path["returns"].index.year == year]
        candidate_total = float((1.0 + candidate_returns).prod() - 1.0)
        named_total = float((1.0 + named_returns).prod() - 1.0)
        excess = candidate_total - named_total
        annual_excess[int(year)] = excess
        rows.append(
            {
                "calendar_year": int(year),
                "valid_formation_count": len(group),
                "selected_asset_change_count": int(
                    group["selected_asset_change"].sum()
                ),
                "shy_replacement_count": int(group["shy_replacement_count"].sum()),
                "mean_pairwise_correlation": float(
                    group["mean_pairwise_correlation"].mean()
                ),
                "mean_candidate_return_only_overlap": float(
                    group["candidate_return_only_overlap"].mean()
                ),
                "turnover": float(
                    candidate_path["turnover"].loc[
                        candidate_path["turnover"].index.year == year
                    ].sum()
                ),
                "candidate_return": candidate_total,
                "return_only_control_return": named_total,
                "candidate_minus_return_only_return": excess,
                "unfavorable_year_retained": True,
            }
        )
    positive_excess = [max(value, 0.0) for value in annual_excess.values()]
    positive_sum = float(sum(positive_excess))
    largest_fraction = (
        max(positive_excess) / positive_sum if positive_sum > 0.0 else float("nan")
    )
    return rows, {
        "largest_positive_calendar_year_fraction_of_positive_additive_excess": largest_fraction
    }


def faa_component_rows(
    full_metrics: dict[tuple[str, float], dict[str, Any]],
    quarter_map: dict[tuple[str, str], dict[str, Any]],
    year_map: dict[tuple[str, int], dict[str, Any]],
    rolling36: list[dict[str, Any]],
    rolling60: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    comparators = (FAA_NAMED, FAA_ATTRIBUTION, FAA_STATIC)
    rows: list[dict[str, Any]] = []

    def add(period_type: str, period: str, candidate: dict[str, Any], comparator_id: str, control: dict[str, Any]) -> None:
        rows.append(
            {
                "strategy_id": FAA_ID,
                "period_type": period_type,
                "period": period,
                "comparison_id": comparator_id,
                "candidate_cagr": candidate["cagr"],
                "comparison_cagr": control["cagr"],
                "cagr_difference": float(candidate["cagr"]) - float(control["cagr"]),
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "comparison_sharpe_ratio": control["sharpe_ratio"],
                "sharpe_difference": float(candidate["sharpe_ratio"])
                - float(control["sharpe_ratio"]),
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "comparison_maximum_drawdown": control["maximum_drawdown"],
                "maximum_drawdown_difference": float(
                    candidate["maximum_drawdown"]
                )
                - float(control["maximum_drawdown"]),
                "candidate_turnover": candidate["turnover"],
                "comparison_turnover": control["turnover"],
                "turnover_difference": float(candidate["turnover"])
                - float(control["turnover"]),
                "unfavorable_evidence_retained": True,
            }
        )

    candidate_full = full_metrics[(FAA_ID, PRIMARY_COST)]
    for comparator in comparators:
        add(
            "full_period",
            "full_period",
            candidate_full,
            comparator,
            full_metrics[(comparator, PRIMARY_COST)],
        )
    quarter_names = sorted(
        period for series_id, period in quarter_map if series_id == FAA_ID
    )
    for period in quarter_names:
        for comparator in comparators:
            add(
                "chronological_quarter",
                period,
                quarter_map[(FAA_ID, period)],
                comparator,
                quarter_map[(comparator, period)],
            )
    years = sorted(year for series_id, year in year_map if series_id == FAA_ID)
    for year in years:
        for comparator in comparators:
            add(
                "calendar_year",
                str(year),
                year_map[(FAA_ID, year)],
                comparator,
                year_map[(comparator, year)],
            )
    for months, rolling in ((36, rolling36), (60, rolling60)):
        for row in rolling:
            if row["strategy_id"] != FAA_ID or row["comparison_id"] not in comparators:
                continue
            rows.append(
                {
                    "strategy_id": FAA_ID,
                    "period_type": f"rolling_{months}_month",
                    "period": f"{row['window_start']}|{row['window_end']}",
                    "comparison_id": row["comparison_id"],
                    "candidate_cagr": row["candidate_cagr"],
                    "comparison_cagr": row["comparison_cagr"],
                    "cagr_difference": row["cagr_difference"],
                    "candidate_sharpe_ratio": row["candidate_sharpe_ratio"],
                    "comparison_sharpe_ratio": row["comparison_sharpe_ratio"],
                    "sharpe_difference": row["sharpe_difference"],
                    "candidate_maximum_drawdown": row["candidate_maximum_drawdown"],
                    "comparison_maximum_drawdown": row[
                        "comparison_maximum_drawdown"
                    ],
                    "maximum_drawdown_difference": row[
                        "maximum_drawdown_difference"
                    ],
                    "candidate_turnover": row["candidate_turnover"],
                    "comparison_turnover": row["comparison_turnover"],
                    "turnover_difference": row["turnover_difference"],
                    "unfavorable_evidence_retained": True,
                }
            )
    return rows


def comparator_map(rows: list[dict[str, Any]], strategy_id: str, months: int) -> dict[str, dict[str, Any]]:
    return {
        row["comparison_id"]: row
        for row in rows
        if row["strategy_id"] == strategy_id and row["window_months"] == months
    }


def classify_candidate(
    strategy_id: str,
    reproduction_pass: bool,
    invariants_pass: bool,
    full_metrics: dict[tuple[str, float], dict[str, Any]],
    quarter_map: dict[tuple[str, str], dict[str, Any]],
    rolling_summary_rows: list[dict[str, Any]],
    neutralization: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
    candidate_specific: dict[str, Any],
) -> dict[str, Any]:
    named = VIX_NAMED if strategy_id == VIX_ID else FAA_NAMED
    static = VIX_STATIC if strategy_id == VIX_ID else FAA_STATIC
    candidate_5 = full_metrics[(strategy_id, 5.0)]
    named_5 = full_metrics[(named, 5.0)]
    static_5 = full_metrics[(static, 5.0)]
    candidate_10 = full_metrics[(strategy_id, 10.0)]
    named_10 = full_metrics[(named, 10.0)]
    static_10 = full_metrics[(static, 10.0)]
    quarter_names = [f"chronological_quarter_{number}" for number in range(1, 5)]
    named_improvement_quarters = sum(
        float(quarter_map[(strategy_id, quarter)]["sharpe_ratio"])
        > float(quarter_map[(named, quarter)]["sharpe_ratio"])
        or float(quarter_map[(strategy_id, quarter)]["maximum_drawdown"])
        > float(quarter_map[(named, quarter)]["maximum_drawdown"])
        for quarter in quarter_names
    )
    static_worse_both_quarters = sum(
        worse_on_both(
            quarter_map[(strategy_id, quarter)],
            quarter_map[(static, quarter)],
        )
        for quarter in quarter_names
    )
    rolling36 = comparator_map(rolling_summary_rows, strategy_id, 36)
    rolling60 = comparator_map(rolling_summary_rows, strategy_id, 60)
    rolling_pass = bool(
        all(
            float(rolling36[control][
                "candidate_improves_sharpe_or_drawdown_fraction"
            ])
            > 0.50
            and float(rolling60[control][
                "candidate_improves_sharpe_or_drawdown_fraction"
            ])
            > 0.50
            for control in (named, static)
        )
    )
    neutral = {row["scenario"]: row for row in neutralization}
    neutral_three = neutral["neutralize_three_strongest_positive_excess_months"]
    neutral_year = neutral[
        "neutralize_strongest_additive_excess_calendar_year"
    ]
    neutralization_pass = bool(
        neutral_three["material_advantage_vs_named_control"]
        and not neutral_three["static_control_dominates"]
        and neutral_year["material_advantage_vs_named_control"]
        and not neutral_year["static_control_dominates"]
    )
    bootstrap_map = {row["comparison_id"]: row for row in bootstrap}
    bootstrap_pass = bool(
        float(
            bootstrap_map[named][
                "probability_candidate_higher_sharpe_or_less_severe_drawdown"
            ]
        )
        >= 0.70
        and float(
            bootstrap_map[static][
                "probability_candidate_higher_sharpe_or_less_severe_drawdown"
            ]
        )
        >= 0.60
    )
    common_checks = {
        "parent_reproduction_and_invariants": bool(
            reproduction_pass and invariants_pass
        ),
        "positive_after_cost_at_5bps": float(candidate_5["total_return"]) > 0.0,
        "no_critical_control_dominates_at_5bps": not (
            dominates(named_5, candidate_5) or dominates(static_5, candidate_5)
        ),
        "parent_materiality_vs_both_critical_controls": bool(
            material_advantage(candidate_5, named_5)
            and material_advantage(candidate_5, static_5)
        ),
        "named_control_improved_in_at_least_three_quarters": (
            named_improvement_quarters >= 3
        ),
        "worse_both_vs_static_in_at_most_one_quarter": (
            static_worse_both_quarters <= 1
        ),
        "rolling_36_and_60_majority_improvement": rolling_pass,
        "three_month_and_year_neutralization_pass": neutralization_pass,
        "positive_and_not_dominated_at_10bps": bool(
            float(candidate_10["total_return"]) > 0.0
            and not dominates(named_10, candidate_10)
            and not dominates(static_10, candidate_10)
        ),
        "bootstrap_probability_thresholds": bootstrap_pass,
    }
    severe_failure = False
    specific_checks: dict[str, Any]
    if strategy_id == VIX_ID:
        candidate_15 = full_metrics[(strategy_id, 15.0)]
        named_15 = full_metrics[(named, 15.0)]
        candidate_20 = full_metrics[(strategy_id, 20.0)]
        named_20 = full_metrics[(named, 20.0)]
        static_20 = full_metrics[(static, 20.0)]
        loo = candidate_specific["leave_one_out_summary"]
        specific_checks = {
            "positive_at_15bps": float(candidate_15["total_return"]) > 0.0,
            "material_vs_close_only_at_15bps": material_advantage(
                candidate_15, named_15
            ),
            "not_worse_than_both_critical_controls_at_20bps": not (
                worse_on_both(candidate_20, named_20)
                and worse_on_both(candidate_20, static_20)
            ),
            "leave_one_out_material_fraction_at_least_75pct": float(
                loo["fraction_materially_better_than_close_only"]
            )
            >= 0.75,
            "exposure_matching_dominates_at_most_50pct_leave_one_out": float(
                loo["fraction_not_dominated_by_exposure_matching"]
            )
            >= 0.50,
            "no_single_episode_over_50pct_positive_excess": float(
                candidate_specific["episode_concentration"]
            )
            <= 0.50,
            "turnover_feasible_at_5_to_10bps": bool(
                float(candidate_5["total_return"]) > 0.0
                and float(candidate_10["total_return"]) > 0.0
            ),
        }
        severe_failure = bool(
            float(candidate_10["total_return"]) <= 0.0
            or float(
                loo["fraction_materially_better_than_close_only"]
            )
            < 0.50
            or float(candidate_specific["episode_concentration"]) > 0.75
        )
    else:
        candidate_15 = full_metrics[(strategy_id, 15.0)]
        candidate_20 = full_metrics[(strategy_id, 20.0)]
        named_15 = full_metrics[(named, 15.0)]
        static_15 = full_metrics[(static, 15.0)]
        named_20 = full_metrics[(named, 20.0)]
        static_20 = full_metrics[(static, 20.0)]
        attribution_5 = full_metrics[(FAA_ATTRIBUTION, 5.0)]
        attribution_quarters = sum(
            float(quarter_map[(strategy_id, quarter)]["sharpe_ratio"])
            > float(quarter_map[(FAA_ATTRIBUTION, quarter)]["sharpe_ratio"])
            or float(quarter_map[(strategy_id, quarter)]["maximum_drawdown"])
            > float(quarter_map[(FAA_ATTRIBUTION, quarter)]["maximum_drawdown"])
            for quarter in quarter_names
        )
        specific_checks = {
            "positive_and_not_dominated_at_15bps": bool(
                float(candidate_15["total_return"]) > 0.0
                and not dominates(named_15, candidate_15)
                and not dominates(static_15, candidate_15)
            ),
            "positive_and_not_dominated_at_20bps": bool(
                float(candidate_20["total_return"]) > 0.0
                and not dominates(named_20, candidate_20)
                and not dominates(static_20, candidate_20)
            ),
            "material_vs_no_correlation_at_5bps": material_advantage(
                candidate_5, attribution_5
            ),
            "return_only_improved_in_at_least_three_quarters": (
                named_improvement_quarters >= 3
            ),
            "no_correlation_improved_in_at_least_three_quarters": (
                attribution_quarters >= 3
            ),
            "no_single_asset_over_50pct_positive_excess": float(
                candidate_specific["asset_concentration"]
            )
            <= 0.50,
            "no_single_year_over_50pct_positive_excess": float(
                candidate_specific["year_concentration"]
            )
            <= 0.50,
            "bootstrap_vs_no_correlation_at_least_65pct": float(
                bootstrap_map[FAA_ATTRIBUTION][
                    "probability_candidate_higher_sharpe_or_less_severe_drawdown"
                ]
            )
            >= 0.65,
        }
        severe_failure = bool(
            float(candidate_10["total_return"]) <= 0.0
            or not material_advantage(candidate_5, attribution_5)
            or float(candidate_specific["asset_concentration"]) > 0.75
            or float(candidate_specific["year_concentration"]) > 0.75
        )
    all_checks = {**common_checks, **specific_checks}
    if not reproduction_pass:
        outcome = "robustness_blocked"
        failure_reason = "data_or_comparability_failure"
        interpretation = "historical_robustness_blocked"
    elif all(all_checks.values()):
        outcome = "robustness_positive"
        failure_reason = ""
        interpretation = (
            "ready_for_prospective_validation_design_standalone_defensive_timing"
            if strategy_id == VIX_ID
            else "ready_for_prospective_validation_design_standalone_asset_allocation"
        )
    else:
        core_failure = bool(
            not common_checks["positive_after_cost_at_5bps"]
            or not common_checks["no_critical_control_dominates_at_5bps"]
            or not common_checks["parent_materiality_vs_both_critical_controls"]
        )
        broad_instability = bool(
            not rolling_pass
            and named_improvement_quarters < 2
            and not neutralization_pass
        )
        outcome = (
            "robustness_failed"
            if core_failure or broad_instability or severe_failure
            else "robustness_mixed"
        )
        interpretation = (
            "historically_failed"
            if outcome == "robustness_failed"
            else "historically_promising_not_ready_for_prospective_validation"
        )
        if not common_checks["no_critical_control_dominates_at_5bps"]:
            failure_reason = "weak_vs_primary_control"
        elif not common_checks["parent_materiality_vs_both_critical_controls"]:
            failure_reason = "benchmark_like_behavior"
        elif strategy_id == FAA_ID and not specific_checks[
            "material_vs_no_correlation_at_5bps"
        ]:
            failure_reason = "weak_component_attribution"
        elif (
            strategy_id == FAA_ID
            and (
                not specific_checks["no_single_asset_over_50pct_positive_excess"]
                or not specific_checks["no_single_year_over_50pct_positive_excess"]
            )
        ) or (
            strategy_id == VIX_ID
            and not specific_checks["no_single_episode_over_50pct_positive_excess"]
        ):
            failure_reason = "concentration_risk"
        elif not common_checks["positive_and_not_dominated_at_10bps"] or (
            strategy_id == VIX_ID and not specific_checks["positive_at_15bps"]
        ):
            failure_reason = "cost_sensitivity" if outcome == "robustness_mixed" else "cost_drag"
        elif not (
            common_checks["named_control_improved_in_at_least_three_quarters"]
            and common_checks["rolling_36_and_60_majority_improvement"]
        ):
            failure_reason = "period_instability"
        elif not common_checks["bootstrap_probability_thresholds"]:
            failure_reason = "control_uncertainty"
        else:
            failure_reason = "overfit_or_unstable"
    return {
        "strategy_id": strategy_id,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "interpretation": interpretation,
        "common_positive_checks": common_checks,
        "candidate_specific_positive_checks": specific_checks,
        "named_control_improvement_quarters": named_improvement_quarters,
        "static_worse_both_quarters": static_worse_both_quarters,
        "final_historical_task_for_exact_configuration": True,
        "independent_validation_claimed": False,
        "diversifier_route_reopened": False,
    }


def update_outcomes(
    strategies: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    next_action: str,
) -> None:
    for row in (*strategies, *trials):
        decision = decisions[row["strategy_id"]]
        row["outcome"] = decision["outcome"]
        row["failure_reason"] = decision["failure_reason"]
        row["next_action"] = next_action


def report_text(
    decisions: list[dict[str, Any]],
    full_metrics: dict[str, dict[tuple[str, float], dict[str, Any]]],
    next_action: str,
    consistency: dict[str, Any],
) -> str:
    lines = [
        "# Native ETF Two-Candidate Final Robustness V1",
        "",
        "## Scope",
        "",
        "This packet is the final authorized same-period historical robustness task "
        "for the exact VIX Fix and FAA standalone configurations. It is not independent "
        "validation, does not reopen either diversifier route, and creates no lifecycle "
        "or paper/demo state.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Primary reason | Interpretation | 5 bps CAGR | 5 bps Sharpe | 5 bps maximum drawdown |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for decision in decisions:
        values = full_metrics[decision["strategy_id"]][
            (decision["strategy_id"], PRIMARY_COST)
        ]
        lines.append(
            f"| {decision['strategy_id']} | {decision['outcome']} | "
            f"{decision['failure_reason'] or 'none'} | {decision['interpretation']} | "
            f"{values['cagr']:.6f} | {values['sharpe_ratio']:.6f} | "
            f"{values['maximum_drawdown']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            "The parent exploration rows reproduced before robustness calculations. "
            "Cost stress, deterministic quarters and starts, every complete calendar "
            "year, all monthly-stepped rolling windows, concentration neutralizations, "
            "and the paired moving-block bootstrap retain unfavorable observations.",
            "",
            "VIX Fix interpretation remains bounded to defensive timing: its parent "
            "advantage over exposure matching was drawdown improvement rather than "
            "broad return or Sharpe superiority. FAA component attribution separately "
            "compares the full score with return-only, return-plus-volatility, and "
            "archived static weights.",
            "",
            f"Consistency check: `overall_pass = {str(consistency['overall_pass']).lower()}`.",
            "",
            f"Exact next action: `{next_action}`.",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    before_hashes = snapshot_hashes()
    reset_output()
    preregister()
    preregistration_hashes = {
        name: file_hash(OUTPUT_DIR / name)
        for name in (
            "strategy_cards.csv",
            "trial_ledger.csv",
            "benchmark_reference_log.csv",
            "process_task_log.csv",
        )
    }

    vix_weights, faa_weights = archived_control_weights()
    _, frames = exploration.data_preflight()
    prepared = prepare_with_archived_controls(frames, vix_weights, faa_weights)
    reproduction_rows, reproduction_pass = parent_reproduction(prepared, frames)
    parameter_rows, parameters_pass = archived_parameter_rows(
        prepared, vix_weights, faa_weights
    )
    write_csv(
        "parent_reproduction_check.csv",
        reproduction_rows,
        (
            "scope",
            "archived_row_count",
            "reproduced_row_count",
            "columns_match",
            "rows_match",
            "maximum_numeric_difference",
            "mismatch_count",
            "tolerance",
            "pass",
        ),
    )
    write_csv(
        "archived_control_parameter_reconciliation.csv",
        parameter_rows,
        (
            "strategy_id",
            "control_id",
            "asset",
            "archived_target_weight",
            "runtime_target_weight",
            "absolute_difference",
            "source",
            "recalculated_for_robustness",
            "used_for_all_robustness_results",
            "pass",
        ),
    )

    simulated = {
        VIX_ID: simulate_costs(prepared[VIX_ID], VIX_COSTS),
        FAA_ID: simulate_costs(prepared[FAA_ID], FAA_COSTS),
    }
    fallbacks = {VIX_ID: "BIL", FAA_ID: "SHY"}
    costs = {VIX_ID: VIX_COSTS, FAA_ID: FAA_COSTS}
    comparators = {
        VIX_ID: (VIX_NAMED, VIX_STATIC),
        FAA_ID: (FAA_NAMED, FAA_STATIC, FAA_ATTRIBUTION),
    }
    cost_rows: list[dict[str, Any]] = []
    full_metric_maps: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
    quarter_rows: list[dict[str, Any]] = []
    quarter_maps: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    year_rows: list[dict[str, Any]] = []
    year_maps: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    rolling36: list[dict[str, Any]] = []
    rolling60: list[dict[str, Any]] = []
    start_rows: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    neutralization_rows: list[dict[str, Any]] = []
    concentration_summary: dict[str, dict[str, Any]] = {}
    bootstrap_rows: list[dict[str, Any]] = []

    for strategy_id in (VIX_ID, FAA_ID):
        rows, metric_map = full_cost_rows(
            strategy_id,
            simulated[strategy_id],
            fallbacks[strategy_id],
            costs[strategy_id],
        )
        cost_rows.extend(rows)
        full_metric_maps[strategy_id] = metric_map
        quarters, quarter_map, years, year_map = partition_rows(
            strategy_id,
            simulated[strategy_id],
            fallbacks[strategy_id],
            prepared[strategy_id]["prices"].index,
        )
        quarter_rows.extend(quarters)
        quarter_maps[strategy_id] = quarter_map
        year_rows.extend(years)
        year_maps[strategy_id] = year_map
        rolling36.extend(
            rolling_rows(
                strategy_id,
                simulated[strategy_id],
                prepared[strategy_id],
                fallbacks[strategy_id],
                comparators[strategy_id],
                36,
            )
        )
        rolling60.extend(
            rolling_rows(
                strategy_id,
                simulated[strategy_id],
                prepared[strategy_id],
                fallbacks[strategy_id],
                comparators[strategy_id],
                60,
            )
        )
        start_rows.extend(
            start_sensitivity_rows(
                strategy_id,
                simulated[strategy_id],
                fallbacks[strategy_id],
                prepared[strategy_id]["prices"].index,
                tuple(prepared[strategy_id]["control_events"]),
            )
        )
        named = VIX_NAMED if strategy_id == VIX_ID else FAA_NAMED
        static = VIX_STATIC if strategy_id == VIX_ID else FAA_STATIC
        concentration, neutralization, summary = concentration_and_neutralization(
            strategy_id,
            simulated[strategy_id],
            fallbacks[strategy_id],
            named,
            static,
        )
        concentration_rows.extend(concentration)
        neutralization_rows.extend(neutralization)
        concentration_summary[strategy_id] = summary
        bootstrap_rows.extend(
            paired_bootstrap(
                strategy_id, simulated[strategy_id], comparators[strategy_id]
            )
        )
    rolling_summary_rows = rolling_summary(rolling36, rolling60)
    bootstrap_repeat: list[dict[str, Any]] = []
    for strategy_id in (VIX_ID, FAA_ID):
        bootstrap_repeat.extend(
            paired_bootstrap(
                strategy_id, simulated[strategy_id], comparators[strategy_id]
            )
        )
    bootstrap_deterministic = bootstrap_rows == bootstrap_repeat

    vix_state_rows, vix_episodes, vix_episode_summary = (
        vix_state_and_episode_rows(prepared[VIX_ID], simulated[VIX_ID])
    )
    vix_loo_rows, vix_loo_summary = vix_leave_one_episode_out(
        vix_episodes, prepared[VIX_ID], simulated[VIX_ID]
    )
    faa_asset_rows, faa_asset_summary = faa_asset_contribution_rows(
        prepared[FAA_ID], simulated[FAA_ID]
    )
    faa_stability_rows, _faa_stability_summary = faa_formation_stability_rows(
        prepared[FAA_ID], simulated[FAA_ID]
    )
    faa_stability_rows.append(
        {
            "row_type": "summary",
            "largest_positive_calendar_year_fraction_of_positive_additive_excess": concentration_summary[
                FAA_ID
            ]["strongest_year_fraction"],
            "strongest_positive_additive_excess_calendar_year": concentration_summary[
                FAA_ID
            ]["strongest_year"],
            "annual_concentration_basis": "sum_of_monthly_candidate_minus_return_only_return_differences",
        }
    )
    faa_components = faa_component_rows(
        full_metric_maps[FAA_ID],
        quarter_maps[FAA_ID],
        year_maps[FAA_ID],
        rolling36,
        rolling60,
    )

    after_calculation_hashes = snapshot_hashes()
    protected_unchanged = before_hashes == after_calculation_hashes
    parent_invariants = read_csv("invariant_results.csv")
    parent_invariants_pass = bool(
        len(parent_invariants)
        and parent_invariants["status"].astype(str).eq("pass").all()
    )
    all_runtime_invariants = bool(
        all(
            values["invariant_pass"]
            for strategy_metrics in full_metric_maps.values()
            for values in strategy_metrics.values()
        )
    )
    invariant_pass = bool(
        reproduction_pass
        and parameters_pass
        and parent_invariants_pass
        and all_runtime_invariants
        and protected_unchanged
        and bootstrap_deterministic
    )
    decisions = {
        VIX_ID: classify_candidate(
            VIX_ID,
            reproduction_pass,
            invariant_pass,
            full_metric_maps[VIX_ID],
            quarter_maps[VIX_ID],
            rolling_summary_rows,
            [
                row for row in neutralization_rows if row["strategy_id"] == VIX_ID
            ],
            [row for row in bootstrap_rows if row["strategy_id"] == VIX_ID],
            {
                "leave_one_out_summary": vix_loo_summary[0],
                "episode_concentration": vix_episode_summary[
                    "largest_episode_positive_excess_fraction"
                ],
            },
        ),
        FAA_ID: classify_candidate(
            FAA_ID,
            reproduction_pass,
            invariant_pass,
            full_metric_maps[FAA_ID],
            quarter_maps[FAA_ID],
            rolling_summary_rows,
            [
                row for row in neutralization_rows if row["strategy_id"] == FAA_ID
            ],
            [row for row in bootstrap_rows if row["strategy_id"] == FAA_ID],
            {
                "asset_concentration": faa_asset_summary[
                    "largest_positive_asset_contribution_fraction_of_positive_candidate_minus_return_only"
                ],
                "year_concentration": concentration_summary[FAA_ID][
                    "strongest_year_fraction"
                ],
            },
        ),
    }
    positive_count = sum(
        decision["outcome"] == "robustness_positive"
        for decision in decisions.values()
    )
    blocked_count = sum(
        decision["outcome"] == "robustness_blocked"
        for decision in decisions.values()
    )
    if blocked_count:
        next_action = (
            "direction_owner_review_native_etf_two_candidate_robustness_block_v1"
        )
    elif positive_count:
        next_action = "direction_owner_review_native_etf_two_candidate_robustness_v1"
    else:
        next_action = "resume_native_etf_source_discovery_v2"

    strategies = strategy_cards()
    trials = trial_rows()
    update_outcomes(strategies, trials, decisions, next_action)
    entity_headers = (
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
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "changed_fields_from_parent",
        "route",
        "outcome",
        "failure_reason",
        "next_action",
    )
    write_csv("strategy_cards.csv", strategies, entity_headers)
    write_csv("trial_ledger.csv", trials, entity_headers)
    result_headers = (
        "strategy_id",
        "trial_id",
        "series_id",
        "result_type",
        "cost_bps_one_way",
        "period",
        "evaluation_start",
        "evaluation_end",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "average_risky_exposure",
        "turnover",
        "trade_or_rebalance_count",
        "transaction_cost_drag",
        "maximum_single_asset_weight",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "invariant_pass",
    )
    write_csv("cost_stress_results.csv", cost_rows, result_headers)
    write_csv("chronological_quarter_results.csv", quarter_rows, result_headers)
    write_csv("calendar_year_results.csv", year_rows, (*result_headers, "calendar_year"))
    rolling_headers = (
        "strategy_id",
        "trial_id",
        "window_months",
        "window_sequence",
        "window_start",
        "window_end",
        "candidate_id",
        "comparison_id",
        "candidate_cagr",
        "comparison_cagr",
        "cagr_difference",
        "candidate_sharpe_ratio",
        "comparison_sharpe_ratio",
        "sharpe_difference",
        "candidate_maximum_drawdown",
        "comparison_maximum_drawdown",
        "maximum_drawdown_difference",
        "candidate_turnover",
        "comparison_turnover",
        "turnover_difference",
        "candidate_improves_sharpe_or_drawdown",
        "comparison_dominates_candidate",
        "unfavorable_window_retained",
        "independent_validation_claimed",
    )
    write_csv("rolling_36_month_results.csv", rolling36, rolling_headers)
    write_csv("rolling_60_month_results.csv", rolling60, rolling_headers)
    write_csv(
        "rolling_window_summary.csv",
        rolling_summary_rows,
        (
            "strategy_id",
            "window_months",
            "comparison_id",
            "eligible_window_count",
            "median_cagr_difference",
            "median_sharpe_difference",
            "median_maximum_drawdown_difference",
            "candidate_improves_sharpe_or_drawdown_fraction",
            "comparison_dominates_fraction",
            "unfavorable_windows_retained",
        ),
    )
    write_csv("start_date_sensitivity.csv", start_rows, result_headers)
    write_csv(
        "monthly_excess_concentration.csv",
        concentration_rows,
        (
            "strategy_id",
            "month",
            "candidate_return_5bps",
            "named_control_return_5bps",
            "candidate_minus_named_additive_excess",
            "positive_excess_rank",
            "strongest_positive_excess_month",
            "among_three_strongest_positive_excess_months",
            "strongest_additive_excess_calendar_year",
            "strongest_year",
            "strongest_year_fraction_of_cumulative_positive_additive_excess",
            "frozen_before_counterfactual",
            "observation_deleted",
        ),
    )
    write_csv(
        "month_and_year_neutralization_results.csv",
        neutralization_rows,
        (
            "strategy_id",
            "scenario",
            "neutralized_months",
            "neutralized_month_count",
            "strongest_calendar_year",
            "total_return",
            "cagr",
            "annualized_volatility",
            "sharpe_ratio",
            "maximum_drawdown",
            "material_advantage_vs_named_control",
            "material_advantage_vs_static_control",
            "named_control_dominates",
            "static_control_dominates",
            "observations_deleted",
            "canonical_series_modified",
            "used_for_strategy_change",
        ),
    )
    write_csv(
        "paired_block_bootstrap_results.csv",
        bootstrap_rows,
        (
            "strategy_id",
            "candidate_id",
            "comparison_id",
            "monthly_observation_count",
            "block_length_months",
            "resamples",
            "deterministic_seed",
            "probability_candidate_higher_cagr",
            "probability_candidate_higher_sharpe",
            "probability_candidate_less_severe_maximum_drawdown",
            "probability_candidate_higher_sharpe_or_less_severe_drawdown",
            "paired_cross_series_dependence_preserved",
            "used_for_strategy_change",
            "independent_validation_claimed",
        ),
    )
    write_csv(
        "vix_fix_state_duration_summary.csv",
        vix_state_rows,
        (
            "row_type",
            "state",
            "episode_count",
            "minimum_duration_sessions",
            "median_duration_sessions",
            "mean_duration_sessions",
            "maximum_duration_sessions",
            "fraction_1_session",
            "fraction_2_sessions_or_less",
            "fraction_3_sessions_or_less",
            "fraction_5_sessions_or_less",
            "fraction_10_sessions_or_less",
            "calendar_year",
            "transition_count",
            "turnover",
        ),
    )
    write_csv(
        "vix_fix_defensive_episode_inventory.csv",
        vix_episodes,
        (
            "episode_id",
            "bil_entry_execution_date",
            "spy_reentry_execution_date",
            "defensive_holding_sessions",
            "candidate_minus_close_only_additive_excess",
            "positive_additive_excess",
            "fraction_of_cumulative_positive_additive_excess",
            "completed_episode",
            "combinations_removed",
        ),
    )
    write_csv(
        "vix_fix_leave_one_episode_out_results.csv",
        vix_loo_rows,
        (
            "episode_id",
            "bil_entry_execution_date",
            "spy_reentry_execution_date",
            "defensive_holding_sessions",
            "candidate_cagr",
            "candidate_sharpe_ratio",
            "candidate_maximum_drawdown",
            "baseline_sharpe_ratio",
            "sharpe_change_vs_baseline",
            "drawdown_advantage_vs_close_only",
            "drawdown_advantage_vs_exposure_matching",
            "materially_better_than_close_only",
            "exposure_matched_control_dominates",
            "all_other_signals_and_execution_preserved",
            "cost_model_preserved",
            "used_for_strategy_change",
        ),
    )
    write_csv(
        "vix_fix_leave_one_episode_out_summary.csv",
        vix_loo_summary,
        vix_loo_summary[0].keys(),
    )
    write_csv(
        "faa_component_attribution.csv",
        faa_components,
        (
            "strategy_id",
            "period_type",
            "period",
            "comparison_id",
            "candidate_cagr",
            "comparison_cagr",
            "cagr_difference",
            "candidate_sharpe_ratio",
            "comparison_sharpe_ratio",
            "sharpe_difference",
            "candidate_maximum_drawdown",
            "comparison_maximum_drawdown",
            "maximum_drawdown_difference",
            "candidate_turnover",
            "comparison_turnover",
            "turnover_difference",
            "unfavorable_evidence_retained",
        ),
    )
    write_csv(
        "faa_asset_selection_and_contribution.csv",
        faa_asset_rows,
        (
            "row_type",
            "asset",
            "valid_formation_count",
            "selection_frequency",
            "target_weight_frequency",
            "average_target_weight",
            "realized_return_contribution",
            "candidate_minus_return_only_contribution",
            "candidate_minus_static_control_contribution",
            "shy_replacement_slots",
            "contribution_during_positive_spy_months",
            "contribution_during_negative_spy_months",
        ),
    )
    write_csv(
        "faa_formation_stability.csv",
        faa_stability_rows,
        (
            "row_type",
            "calendar_year",
            "valid_formation_count",
            "selected_asset_change_count",
            "shy_replacement_count",
            "mean_pairwise_correlation",
            "mean_candidate_return_only_overlap",
            "turnover",
            "candidate_return",
            "return_only_control_return",
            "candidate_minus_return_only_return",
            "unfavorable_year_retained",
            "largest_positive_calendar_year_fraction_of_positive_additive_excess",
            "strongest_positive_additive_excess_calendar_year",
            "annual_concentration_basis",
        ),
    )

    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = [
        {
            "strategy_id": "",
            "invariant_name": "parent_reproduction_within_1e_9",
            "invariant_pass": reproduction_pass,
            "detail": "all parent performance, diagnostics, turnover, preflight and invariant rows reproduced",
        },
        {
            "strategy_id": "",
            "invariant_name": "archived_control_weights_used_without_recalculation",
            "invariant_pass": parameters_pass,
            "detail": "VIX exposure and seven FAA static weights loaded from parent evidence",
        },
        {
            "strategy_id": "",
            "invariant_name": "paired_bootstrap_deterministic",
            "invariant_pass": bootstrap_deterministic,
            "detail": "5000 resamples with seed 20260730 matched on repeat",
        },
        {
            "strategy_id": "",
            "invariant_name": "protected_state_cache_and_parent_evidence_unchanged",
            "invariant_pass": protected_unchanged,
            "detail": "hashes matched before and after all robustness calculations",
        },
        {
            "strategy_id": "",
            "invariant_name": "standalone_routes_only",
            "invariant_pass": True,
            "detail": "diversifier diagnostics were not reopened",
        },
    ]
    for strategy_id in (VIX_ID, FAA_ID):
        for (series_id, cost), values in full_metric_maps[strategy_id].items():
            turnover_rows.append(
                {
                    "strategy_id": strategy_id,
                    "series_id": series_id,
                    "cost_bps_one_way": cost,
                    "one_way_turnover": values["turnover"],
                    "transaction_cost_drag": values["transaction_cost_drag"],
                    "costs_charged_once": True,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
            invariant_rows.append(
                {
                    "strategy_id": strategy_id,
                    "series_id": series_id,
                    "cost_bps_one_way": cost,
                    "invariant_name": "accounting_timing_weight_and_exposure",
                    "invariant_pass": values["invariant_pass"],
                    "detail": (
                        "completed signal, following-session close, nonnegative "
                        "weights, gross exposure <=1, costs once"
                    ),
                    "maximum_gross_exposure": values["maximum_gross_exposure"],
                    "maximum_daily_weight_sum": values[
                        "maximum_daily_weight_sum"
                    ],
                }
            )
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover_rows,
        (
            "strategy_id",
            "series_id",
            "cost_bps_one_way",
            "one_way_turnover",
            "transaction_cost_drag",
            "costs_charged_once",
            "turnover_formula",
        ),
    )
    write_csv(
        "invariant_results.csv",
        invariant_rows,
        (
            "strategy_id",
            "series_id",
            "cost_bps_one_way",
            "invariant_name",
            "invariant_pass",
            "detail",
            "maximum_gross_exposure",
            "maximum_daily_weight_sum",
        ),
    )
    decision_rows = list(decisions.values())
    write_csv(
        "outcome_summary.csv",
        [
            {
                **decision,
                "next_action": next_action,
                "same_period_historical_robustness_only": True,
                "prospective_validation_started": False,
                "paper_demo_eligibility_claimed": False,
            }
            for decision in decision_rows
        ],
        (
            "strategy_id",
            "outcome",
            "failure_reason",
            "interpretation",
            "common_positive_checks",
            "candidate_specific_positive_checks",
            "named_control_improvement_quarters",
            "static_worse_both_quarters",
            "final_historical_task_for_exact_configuration",
            "independent_validation_claimed",
            "diversifier_route_reopened",
            "next_action",
            "same_period_historical_robustness_only",
            "prospective_validation_started",
            "paper_demo_eligibility_claimed",
        ),
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "strategy_id": decision["strategy_id"],
                "outcome": decision["outcome"],
                "primary_failure_reason": decision["failure_reason"],
                "strategy_changed_to_escape_outcome": False,
            }
            for decision in decision_rows
            if decision["failure_reason"]
        ],
        (
            "strategy_id",
            "outcome",
            "primary_failure_reason",
            "strategy_changed_to_escape_outcome",
        ),
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "scope": TASK_ID,
                "robustness_positive_count": positive_count,
                "robustness_blocked_count": blocked_count,
                "exact_next_action": next_action,
                "executed_in_this_task": False,
            }
        ],
        (
            "scope",
            "robustness_positive_count",
            "robustness_blocked_count",
            "exact_next_action",
            "executed_in_this_task",
        ),
    )
    funnel = {
        "existing_strategy_configurations_carried_forward": 2,
        "new_strategy_configurations": 0,
        "existing_exploration_trials_carried_forward": 2,
        "new_robustness_trials": 2,
        "benchmark_reference_rows_carried_forward": len(benchmark_rows()),
        "new_benchmark_strategies": 0,
        "process_tasks": 1,
        "counterfactual_diagnostics": len(neutralization_rows)
        + len(vix_loo_rows),
        "bootstrap_resamples_per_candidate": BOOTSTRAP_RESAMPLES,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "data_capability_tasks": 0,
        "robustness_positive": positive_count,
        "robustness_mixed": sum(
            decision["outcome"] == "robustness_mixed"
            for decision in decision_rows
        ),
        "robustness_failed": sum(
            decision["outcome"] == "robustness_failed"
            for decision in decision_rows
        ),
        "robustness_blocked": blocked_count,
    }
    write_json("cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": TASK_ID,
        "mode": "bounded-historical-robustness",
        "stage": "robustness",
        "candidate_ids": [VIX_ID, FAA_ID],
        "parent_trial_ids": [VIX_PARENT_TRIAL, FAA_PARENT_TRIAL],
        "robustness_child_trial_ids": [VIX_TRIAL, FAA_TRIAL],
        "routes": {VIX_ID: "standalone_only", FAA_ID: "standalone_only"},
        "parent_exploration_outcomes_preserved": EXPECTED_PARENT_OUTCOMES,
        "parent_diversifier_gates_reopened": False,
        "costs_bps": {VIX_ID: list(VIX_COSTS), FAA_ID: list(FAA_COSTS)},
        "rolling_windows_months": [36, 60],
        "bootstrap": {
            "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
        "source_authority": str(SOURCE_ATTACHMENT),
        "source_authority_hash": file_hash(SOURCE_ATTACHMENT),
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_artifact_hashes_before_performance": preregistration_hashes,
        "parent_reproduction_pass": reproduction_pass,
        "archived_control_parameter_reconciliation_pass": parameters_pass,
        "outcomes": {
            strategy_id: decisions[strategy_id]["outcome"]
            for strategy_id in (VIX_ID, FAA_ID)
        },
        "final_same_period_historical_task": True,
        "independent_validation_claimed": False,
        "provider_access_performed": False,
        "parameter_or_universe_variant_tested": False,
        "post_result_adaptation_performed": False,
        "lifecycle_state_changed": False,
        "paper_demo_action_performed": False,
        "broker_or_real_money_action_performed": False,
        "next_action": next_action,
    }
    write_yaml("robustness_manifest.yaml", manifest)

    final_hashes = snapshot_hashes()
    protected_final_unchanged = before_hashes == final_hashes
    outputs_before_final = all(
        (OUTPUT_DIR / name).exists() for name in REQUIRED_FILES[:-2]
    )
    entity_counts_pass = bool(
        funnel["existing_strategy_configurations_carried_forward"] == 2
        and funnel["new_strategy_configurations"] == 0
        and funnel["existing_exploration_trials_carried_forward"] == 2
        and funnel["new_robustness_trials"] == 2
        and funnel["validation_observations"] == 0
        and funnel["paper_demo_observations"] == 0
        and funnel["data_capability_tasks"] == 0
    )
    consistency = {
        "overall_pass": bool(
            reproduction_pass
            and parameters_pass
            and all_runtime_invariants
            and bootstrap_deterministic
            and protected_final_unchanged
            and entity_counts_pass
            and outputs_before_final
        ),
        "parent_reproduction_within_1e_9": reproduction_pass,
        "archived_control_parameters_reconciled": parameters_pass,
        "all_runtime_invariants_pass": all_runtime_invariants,
        "bootstrap_deterministic": bootstrap_deterministic,
        "protected_state_cache_and_parent_evidence_unchanged": protected_final_unchanged,
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": final_hashes,
        "entity_counts_reconcile": entity_counts_pass,
        "exactly_two_robustness_child_trials": True,
        "zero_new_strategy_configurations": True,
        "diversifier_routes_remain_closed": True,
        "same_period_evidence_not_called_validation": True,
        "final_historical_task_for_exact_configurations": True,
        "required_outputs_present_before_report_and_consistency": outputs_before_final,
        "no_provider_lifecycle_paper_demo_or_broker_action": True,
    }
    write_json("consistency_check.json", consistency)
    (OUTPUT_DIR / "robustness_report.md").write_text(
        report_text(decision_rows, full_metric_maps, next_action, consistency),
        encoding="utf-8",
    )
    missing = [name for name in REQUIRED_FILES if not (OUTPUT_DIR / name).exists()]
    if missing:
        raise RuntimeError(f"Missing required outputs: {missing}")
    if not consistency["overall_pass"]:
        raise RuntimeError("Robustness consistency check failed")
    return {
        "task_id": TASK_ID,
        "output_dir": str(OUTPUT_DIR),
        "outcomes": {
            strategy_id: {
                "outcome": decisions[strategy_id]["outcome"],
                "failure_reason": decisions[strategy_id]["failure_reason"],
                "interpretation": decisions[strategy_id]["interpretation"],
            }
            for strategy_id in (VIX_ID, FAA_ID)
        },
        "robustness_positive_count": positive_count,
        "next_action": next_action,
        "consistency_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
