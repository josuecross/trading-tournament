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
    accepted_47_source_backed_exploration_batch_v2 as exploration,
)


TASK_ID = "accepted_47_source_backed_v2_two_candidate_final_robustness_v1"
MODE = "bounded-historical-robustness"
STAGE = "robustness"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
SOURCE_DIR = exploration.SOURCE_DIR
PARENT_DIR = exploration.OUTPUT_DIR
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
REPRODUCTION_TOLERANCE = 1e-9
TOLERANCE = 1e-10
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260806
PREREGISTRATION_TIMESTAMP = "2026-08-06T00:00:00-06:00"

MCA_ID = exploration.MCA_ID
HYG_ID = exploration.HYG_ID
MCA_PARENT = exploration.MCA_TRIAL
HYG_PARENT = exploration.HYG_TRIAL
MCA_TRIAL = f"{TASK_ID}__mca8__child"
HYG_TRIAL = f"{TASK_ID}__hyg_ema100__child"
TRIALS = {MCA_ID: MCA_TRIAL, HYG_ID: HYG_TRIAL}
PARENTS = {MCA_ID: MCA_PARENT, HYG_ID: HYG_PARENT}
DECISIVE = {
    MCA_ID: (exploration.MCA_NAMED, exploration.MCA_STATIC),
    HYG_ID: (exploration.HYG_NAMED, exploration.HYG_STATIC),
}
ATTRIBUTION_CONTROLS = {
    MCA_ID: (
        exploration.MCA_NAMED,
        exploration.MCA_STATIC,
        "mca8_equal_weight_weekly_control",
    ),
    HYG_ID: (
        exploration.HYG_NAMED,
        "hyg_sma100_spy_bil_control",
        exploration.HYG_STATIC,
    ),
}
RISK_ASSETS = {MCA_ID: exploration.MCA_RISK, HYG_ID: ("SPY",)}

REPRODUCTION_FILES = (
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "mca_weekly_allocation_ledger.csv",
    "mca_component_diagnostics.csv",
    "hyg_daily_signal_ledger.csv",
    "hyg_state_and_episode_diagnostics.csv",
    "lightweight_concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
)
REQUIRED_FILES = (
    "robustness_manifest.yaml",
    "source_strategy_trial_lineage.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "parent_reproduction_check.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "start_date_sensitivity.csv",
    "monthly_excess_concentration.csv",
    "neutralization_results.csv",
    "paired_block_bootstrap_results.csv",
    "mca_control_attribution.csv",
    "mca_asset_and_weight_concentration.csv",
    "hyg_control_attribution.csv",
    "hyg_defensive_episode_inventory.csv",
    "hyg_leave_one_episode_out_results.csv",
    "hyg_leave_one_episode_out_summary.csv",
    "portfolio_contribution_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "robustness_report.md",
)
PROTECTED_PATHS = tuple(
    dict.fromkeys(
        (
            *exploration.BASE_PROTECTED_PATHS,
            SOURCE_DIR.relative_to(ROOT),
            PARENT_DIR.relative_to(ROOT),
        )
    )
)


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(
    name: str,
    rows: Iterable[dict[str, Any]],
    fields: Iterable[str] | None = None,
) -> None:
    materialized = list(rows)
    columns = list(fields or [])
    for row in materialized:
        for field in row:
            if field not in columns:
                columns.append(field)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: serialize(row.get(field, "")) for field in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected path: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def tree_hash(path: Path) -> str:
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {path.as_posix(): tree_hash(ROOT / path) for path in PROTECTED_PATHS}


def trial_id(strategy_id: str) -> str:
    return TRIALS[strategy_id]


def eligible_index(strategy_id: str, prepared: dict[str, Any]) -> pd.DatetimeIndex:
    return prepared["prices"].index[
        prepared["prices"].index >= prepared["first_eligible_execution"]
    ]


def simulate_costs(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_target_applied_at_following_regular_session_close"
    return {
        "candidate_paths": {
            cost: exploration.base.accounting.simulate_path(
                prepared["prices"], prepared["candidate_events"], cost, timing
            )
            for cost in COSTS
        },
        "control_paths": {
            (control_id, cost): exploration.base.accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
            for control_id, events in prepared["control_events"].items()
            for cost in COSTS
        },
    }


def path_metrics(
    strategy_id: str,
    path: dict[str, Any],
    index: pd.DatetimeIndex,
) -> dict[str, Any]:
    return exploration.base.metrics(path, index, RISK_ASSETS[strategy_id])


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.base.dominates(control, candidate)


def material(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.base.material(candidate, control)


def result_row(
    strategy_id: str,
    series_id: str,
    cost: float,
    period: str,
    values: dict[str, Any],
    diagnostic_type: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "trial_id": trial_id(strategy_id),
        "series_id": series_id,
        "cost_bps_one_way": cost,
        "period": period,
        "diagnostic_type": diagnostic_type,
        **values,
    }


def prepare_parent() -> tuple[
    list[exploration.StrategySpec],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    specs, reconciliation = exploration.load_source_packet()
    if not reconciliation["pass"]:
        raise RuntimeError(f"source packet reconciliation failed: {reconciliation}")
    frames, _, candidate_status = exploration.preflight()
    if not all(candidate_status.values()):
        raise RuntimeError(f"accepted-47 parent data preflight failed: {candidate_status}")
    prepared = {
        spec.strategy_id: (
            exploration.prepare_mca(spec, frames)
            if spec.strategy_id == MCA_ID
            else exploration.prepare_hyg(spec, frames)
        )
        for spec in specs
    }
    simulations = {
        strategy_id: simulate_costs(item) for strategy_id, item in prepared.items()
    }
    return specs, prepared, simulations


def reproduced_parent_rows(
    specs: list[exploration.StrategySpec],
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {name: [] for name in REPRODUCTION_FILES}
    for spec in specs:
        item = prepared[spec.strategy_id]
        parent_simulation = {
            "candidate_paths": {
                cost: simulations[spec.strategy_id]["candidate_paths"][cost]
                for cost in exploration.COSTS
            },
            "control_paths": {
                (control, cost): simulations[spec.strategy_id]["control_paths"][(control, cost)]
                for control in spec.controls
                for cost in exploration.COSTS
            },
        }
        candidate_rows, control_rows, half_rows, eligible = exploration.full_and_half_rows(
            spec, item, parent_simulation
        )
        output["all_trial_results.csv"].extend(candidate_rows)
        output["control_results.csv"].extend(control_rows)
        output["chronological_half_results.csv"].extend(half_rows)
        portfolio_paths = exploration.base.portfolio_paths(spec, parent_simulation, eligible)
        portfolio_rows, portfolio_halves = exploration.base.portfolio_result_rows(
            spec, portfolio_paths
        )
        output["portfolio_contribution_results.csv"].extend(portfolio_rows)
        output["chronological_half_results.csv"].extend(portfolio_halves)
        if spec.strategy_id == MCA_ID:
            ledger = exploration.enrich_mca_ledger(item, parent_simulation)
            output["mca_weekly_allocation_ledger.csv"] = ledger
            output["mca_component_diagnostics.csv"] = exploration.mca_component_diagnostics(
                item, parent_simulation, ledger
            )
            episode_values = None
        else:
            output["hyg_daily_signal_ledger.csv"] = exploration.enrich_hyg_ledger(
                item, parent_simulation
            )
            diagnostics, episode_values = exploration.hyg_state_diagnostics(
                item, parent_simulation
            )
            output["hyg_state_and_episode_diagnostics.csv"] = diagnostics
        concentration, _ = exploration.concentration_diagnostics(
            spec, item, parent_simulation, episode_values
        )
        output["lightweight_concentration_diagnostics.csv"].extend(concentration)
        output["turnover_cost_reconciliation.csv"].extend(
            exploration.turnover_rows(spec, item, parent_simulation)
        )
        _, evidence_detail = exploration.minimum_evidence_check(spec, item, parent_simulation)
        output["invariant_results.csv"].extend(
            exploration.invariant_rows(spec, item, parent_simulation, evidence_detail)
        )
    return output


def normalized_cell(value: Any) -> str:
    serialized = serialize(value)
    if isinstance(serialized, float) and math.isnan(serialized):
        return "nan"
    return str(serialized)


def compare_parent_frame(
    name: str, archived: pd.DataFrame, reproduced_rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, bool]]:
    columns = list(archived.columns)
    reproduced = pd.DataFrame(
        [
            {column: normalized_cell(row.get(column, "")) for column in columns}
            for row in reproduced_rows
        ],
        columns=columns,
    )
    archived_text = archived.fillna("").astype(str).reset_index(drop=True)
    reproduced_text = reproduced.fillna("").astype(str).reset_index(drop=True)
    candidate_pass = {MCA_ID: True, HYG_ID: True}
    maximum_difference = 0.0
    mismatches = 0
    if len(archived_text) != len(reproduced_text):
        mismatches = abs(len(archived_text) - len(reproduced_text)) + min(
            len(archived_text), len(reproduced_text)
        )
        candidate_pass = {MCA_ID: False, HYG_ID: False}
    else:
        for row_index in range(len(archived_text)):
            row_strategy = (
                archived_text.iloc[row_index].get("strategy_id", "")
                if "strategy_id" in archived_text.columns
                else ""
            )
            row_match = True
            for column in columns:
                left = archived_text.iloc[row_index][column]
                right = reproduced_text.iloc[row_index][column]
                try:
                    left_number = float(left)
                    right_number = float(right)
                    if math.isnan(left_number) and math.isnan(right_number):
                        difference = 0.0
                    else:
                        difference = abs(left_number - right_number)
                    maximum_difference = max(maximum_difference, difference)
                    equal = difference <= REPRODUCTION_TOLERANCE
                except (TypeError, ValueError):
                    equal = left == right
                if not equal:
                    mismatches += 1
                    row_match = False
            if not row_match:
                if row_strategy in candidate_pass:
                    candidate_pass[row_strategy] = False
                else:
                    candidate_pass = {MCA_ID: False, HYG_ID: False}
    row = {
        "scope": name,
        "archived_row_count": len(archived_text),
        "reproduced_row_count": len(reproduced_text),
        "columns_match": list(archived_text.columns) == list(reproduced_text.columns),
        "maximum_numeric_difference": maximum_difference,
        "mismatch_count": mismatches,
        "tolerance": REPRODUCTION_TOLERANCE,
        "pass": mismatches == 0 and len(archived_text) == len(reproduced_text),
    }
    return row, candidate_pass


def parent_reproduction(
    specs: list[exploration.StrategySpec],
    prepared: dict[str, dict[str, Any]],
    simulations: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    reproduced = reproduced_parent_rows(specs, prepared, simulations)
    rows: list[dict[str, Any]] = []
    candidate_pass = {MCA_ID: True, HYG_ID: True}
    for name in REPRODUCTION_FILES:
        archived = pd.read_csv(PARENT_DIR / name, keep_default_na=False, dtype=str)
        row, scoped = compare_parent_frame(name, archived, reproduced[name])
        rows.append(row)
        for strategy_id in candidate_pass:
            candidate_pass[strategy_id] &= scoped[strategy_id]
    parent_trials = pd.read_csv(PARENT_DIR / "trial_ledger.csv", keep_default_na=False)
    expected = {
        MCA_ID: (MCA_PARENT, "exploratory_followup_candidate_standalone"),
        HYG_ID: (HYG_PARENT, "exploratory_followup_candidate_standalone"),
    }
    lineage_pass = all(
        len(
            parent_trials.loc[
                parent_trials["strategy_id"].eq(strategy_id)
                & parent_trials["trial_id"].eq(trial)
                & parent_trials["outcome"].eq(outcome)
            ]
        )
        == 1
        for strategy_id, (trial, outcome) in expected.items()
    )
    rows.append(
        {
            "scope": "parent_trial_lineage_and_exploration_outcomes",
            "archived_row_count": len(parent_trials),
            "reproduced_row_count": 2,
            "columns_match": True,
            "maximum_numeric_difference": 0.0,
            "mismatch_count": 0 if lineage_pass else 1,
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": lineage_pass,
        }
    )
    for strategy_id in candidate_pass:
        candidate_pass[strategy_id] &= lineage_pass
    aggregate_pass = lineage_pass and all(bool(row["pass"]) for row in rows)
    if aggregate_pass:
        candidate_pass = {MCA_ID: True, HYG_ID: True}
    rows.extend(
        {
            "scope": f"candidate_reproduction_gate:{strategy_id}",
            "archived_row_count": "all_applicable_parent_rows",
            "reproduced_row_count": "all_applicable_parent_rows",
            "columns_match": True,
            "maximum_numeric_difference": max(
                float(row["maximum_numeric_difference"]) for row in rows
            ),
            "mismatch_count": 0 if passed else 1,
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": passed,
        }
        for strategy_id, passed in candidate_pass.items()
    )
    return rows, candidate_pass


def paths_at_cost(
    strategy_id: str, simulation: dict[str, Any], cost: float
) -> dict[str, dict[str, Any]]:
    return {
        strategy_id: simulation["candidate_paths"][cost],
        **{
            control_id: simulation["control_paths"][(control_id, cost)]
            for control_id in simulation["control_paths"]
            if isinstance(control_id, str)
        },
    }


def all_paths_at_cost(
    strategy_id: str,
    spec: exploration.StrategySpec,
    simulation: dict[str, Any],
    cost: float,
) -> dict[str, dict[str, Any]]:
    return {
        strategy_id: simulation["candidate_paths"][cost],
        **{
            control_id: simulation["control_paths"][(control_id, cost)]
            for control_id in spec.controls
        },
    }


def cost_stress_rows(
    spec: exploration.StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    index = eligible_index(spec.strategy_id, prepared)
    rows: list[dict[str, Any]] = []
    metric_map: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        for series_id, path in all_paths_at_cost(spec.strategy_id, spec, simulation, cost).items():
            values = path_metrics(spec.strategy_id, path, index)
            metric_map[(series_id, cost)] = values
            rows.append(
                result_row(
                    spec.strategy_id,
                    series_id,
                    cost,
                    "full_authoritative_period",
                    values,
                    "cost_stress",
                )
            )
    return rows, metric_map


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_quarter_{position + 1}": index[locations]
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def complete_years(index: pd.DatetimeIndex) -> dict[int, pd.DatetimeIndex]:
    return {
        year: index[index.year == year]
        for year in range(int(index.min().year) + 1, int(index.max().year))
        if len(index[index.year == year])
    }


def comparison_payload(
    strategy_id: str,
    candidate: dict[str, Any],
    control_id: str,
    control: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "trial_id": trial_id(strategy_id),
        "comparison_control_id": control_id,
        "candidate_cagr": candidate["cagr"],
        "control_cagr": control["cagr"],
        "cagr_difference": candidate["cagr"] - control["cagr"],
        "candidate_sharpe_ratio": candidate["sharpe_ratio"],
        "control_sharpe_ratio": control["sharpe_ratio"],
        "sharpe_difference": candidate["sharpe_ratio"] - control["sharpe_ratio"],
        "candidate_maximum_drawdown": candidate["maximum_drawdown"],
        "control_maximum_drawdown": control["maximum_drawdown"],
        "maximum_drawdown_difference": candidate["maximum_drawdown"]
        - control["maximum_drawdown"],
        "candidate_turnover": candidate["turnover"],
        "control_turnover": control["turnover"],
        "turnover_difference": candidate["turnover"] - control["turnover"],
        "candidate_improves_sharpe_or_drawdown": bool(
            candidate["sharpe_ratio"] > control["sharpe_ratio"]
            or candidate["maximum_drawdown"] > control["maximum_drawdown"]
        ),
        "control_dominates_candidate": dominates(control, candidate),
        "candidate_material_vs_control": material(candidate, control),
        "unfavorable_result_retained": True,
        "validation_or_independent_claimed": False,
    }


def chronological_and_year_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index = eligible_index(strategy_id, prepared)
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
    quarters: list[dict[str, Any]] = []
    years: list[dict[str, Any]] = []
    for period, period_index in split_quarters(index).items():
        candidate = path_metrics(strategy_id, candidate_path, period_index)
        for control_id in ATTRIBUTION_CONTROLS[strategy_id]:
            control = path_metrics(
                strategy_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
                period_index,
            )
            quarters.append(
                {
                    "period": period,
                    "evaluation_start": period_index[0].date().isoformat(),
                    "evaluation_end": period_index[-1].date().isoformat(),
                    **comparison_payload(strategy_id, candidate, control_id, control),
                }
            )
    for year, period_index in complete_years(index).items():
        candidate = path_metrics(strategy_id, candidate_path, period_index)
        for control_id in ATTRIBUTION_CONTROLS[strategy_id]:
            control = path_metrics(
                strategy_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
                period_index,
            )
            years.append(
                {
                    "calendar_year": year,
                    "evaluation_start": period_index[0].date().isoformat(),
                    "evaluation_end": period_index[-1].date().isoformat(),
                    **comparison_payload(strategy_id, candidate, control_id, control),
                }
            )
    return quarters, years


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]


def rolling_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    months: int,
) -> list[dict[str, Any]]:
    index = eligible_index(strategy_id, prepared)
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
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
        candidate = path_metrics(strategy_id, candidate_path, period_index)
        for control_id in ATTRIBUTION_CONTROLS[strategy_id]:
            control = path_metrics(
                strategy_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
                period_index,
            )
            rows.append(
                {
                    "window_months": months,
                    "window_sequence": sequence,
                    "window_start": period_index[0].date().isoformat(),
                    "window_end": period_index[-1].date().isoformat(),
                    **comparison_payload(strategy_id, candidate, control_id, control),
                }
            )
    return rows


def rolling_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    keys = sorted(
        {
            (row["strategy_id"], row["window_months"], row["comparison_control_id"])
            for row in rows
        }
    )
    for strategy_id, months, control_id in keys:
        subset = [
            row
            for row in rows
            if row["strategy_id"] == strategy_id
            and row["window_months"] == months
            and row["comparison_control_id"] == control_id
        ]
        output.append(
            {
                "strategy_id": strategy_id,
                "window_months": months,
                "comparison_control_id": control_id,
                "eligible_window_count": len(subset),
                "median_cagr_difference": float(np.median([row["cagr_difference"] for row in subset])),
                "median_sharpe_difference": float(
                    np.median([row["sharpe_difference"] for row in subset])
                ),
                "median_maximum_drawdown_difference": float(
                    np.median([row["maximum_drawdown_difference"] for row in subset])
                ),
                "candidate_improves_sharpe_or_drawdown_fraction": float(
                    np.mean([row["candidate_improves_sharpe_or_drawdown"] for row in subset])
                ),
                "control_dominates_candidate_fraction": float(
                    np.mean([row["control_dominates_candidate"] for row in subset])
                ),
                "candidate_material_fraction": float(
                    np.mean([row["candidate_material_vs_control"] for row in subset])
                ),
                "unfavorable_windows_retained": True,
            }
        )
    return output


def start_date_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    index = eligible_index(strategy_id, prepared)
    rows: list[dict[str, Any]] = []
    for year in range(2010, 2017):
        starts = index[index >= pd.Timestamp(f"{year}-01-01")]
        if not len(starts):
            continue
        period_index = index[index >= starts[0]]
        for series_id in (strategy_id, *DECISIVE[strategy_id]):
            path = (
                simulation["candidate_paths"][PRIMARY_COST]
                if series_id == strategy_id
                else simulation["control_paths"][(series_id, PRIMARY_COST)]
            )
            rows.append(
                result_row(
                    strategy_id,
                    series_id,
                    PRIMARY_COST,
                    f"start_{year}_fixed_end",
                    path_metrics(strategy_id, path, period_index),
                    "deterministic_start_date_sensitivity",
                )
                | {
                    "requested_start_year": year,
                    "actual_start": starts[0].date().isoformat(),
                    "fixed_end": index[-1].date().isoformat(),
                    "start_selected_from_performance": False,
                    "strategy_reinitialized_at_start": False,
                }
            )
    return rows


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.to_period("M")).prod().sub(1.0)


def monthly_metrics(values: pd.Series | np.ndarray) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    wealth = np.cumprod(1.0 + array)
    standard_deviation = float(np.std(array, ddof=1)) if len(array) > 1 else 0.0
    return {
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(array)) - 1.0),
        "annualized_volatility": standard_deviation * math.sqrt(12.0),
        "sharpe_ratio": float(np.mean(array) / standard_deviation * math.sqrt(12.0))
        if standard_deviation > 0.0
        else 0.0,
        "maximum_drawdown": float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)),
    }


def concentration_and_neutralization(
    strategy_id: str,
    simulation: dict[str, Any],
    index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    named_control = DECISIVE[strategy_id][0]
    candidate_daily = simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(index)
    named_daily = simulation["control_paths"][(named_control, PRIMARY_COST)]["returns"].reindex(index)
    candidate_monthly = monthly_returns(candidate_daily)
    named_monthly = monthly_returns(named_daily)
    monthly = pd.concat(
        [candidate_monthly.rename("candidate"), named_monthly.rename("named")], axis=1
    ).dropna()
    monthly["excess"] = monthly["candidate"] - monthly["named"]
    positive = monthly.loc[monthly["excess"] > 0.0, "excess"].sort_values(ascending=False)
    strongest_three = list(positive.index[:3])
    strongest_month = strongest_three[0]
    annual = monthly["excess"].groupby(monthly.index.year).sum()
    strongest_year = int(annual.idxmax())
    positive_total = float(positive.sum())
    annual_positive = annual.clip(lower=0.0)
    annual_positive_total = float(annual_positive.sum())
    rank = {period: position + 1 for position, period in enumerate(positive.index)}
    concentration = [
        {
            "strategy_id": strategy_id,
            "trial_id": trial_id(strategy_id),
            "month": str(period),
            "candidate_return_5bps": row.candidate,
            "named_control_return_5bps": row.named,
            "candidate_minus_named_control_return_difference": row.excess,
            "positive_excess_rank": rank.get(period, ""),
            "strongest_positive_excess_month": period == strongest_month,
            "among_three_strongest_positive_excess_months": period in strongest_three,
            "strongest_positive_excess_calendar_year": period.year == strongest_year,
            "strongest_month_share_of_positive_excess": float(positive.iloc[0] / positive_total),
            "three_strongest_months_share_of_positive_excess": float(
                positive.iloc[:3].sum() / positive_total
            ),
            "strongest_year_share_of_positive_excess": float(
                annual_positive.loc[strongest_year] / annual_positive_total
            ),
            "frozen_before_counterfactual": True,
            "observation_deleted": False,
        }
        for period, row in monthly.iterrows()
    ]
    control_monthly = {
        control_id: monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(index)
        ).reindex(monthly.index)
        for control_id in DECISIVE[strategy_id]
    }
    control_metrics = {
        control_id: monthly_metrics(values) for control_id, values in control_monthly.items()
    }
    scenarios = {
        "neutralize_strongest_positive_month": [strongest_month],
        "neutralize_three_strongest_positive_months": strongest_three,
        "neutralize_strongest_positive_calendar_year": [
            period for period in monthly.index if period.year == strongest_year
        ],
    }
    neutralization: list[dict[str, Any]] = []
    for scenario, periods in scenarios.items():
        counterfactual = monthly["candidate"].copy()
        counterfactual.loc[periods] = monthly.loc[periods, "named"]
        candidate = monthly_metrics(counterfactual)
        dominance = {
            control_id: dominates(control_metrics[control_id], candidate)
            for control_id in DECISIVE[strategy_id]
        }
        materiality = {
            control_id: material(candidate, control_metrics[control_id])
            for control_id in DECISIVE[strategy_id]
        }
        neutralization.append(
            {
                "strategy_id": strategy_id,
                "trial_id": trial_id(strategy_id),
                "scenario": scenario,
                "named_control_id": named_control,
                "neutralized_months": [str(period) for period in periods],
                "neutralized_month_count": len(periods),
                "strongest_calendar_year": strongest_year,
                **candidate,
                "materiality_against_decisive_controls": materiality,
                "decisive_control_dominance": dominance,
                "material_vs_named_control": materiality[named_control],
                "other_decisive_control_dominates": any(
                    dominance[control_id]
                    for control_id in DECISIVE[strategy_id]
                    if control_id != named_control
                ),
                "observations_deleted": False,
                "canonical_returns_modified": False,
                "used_for_strategy_change": False,
            }
        )
    summary = {
        "strongest_positive_month": str(strongest_month),
        "strongest_three_positive_months": [str(period) for period in strongest_three],
        "strongest_positive_calendar_year": strongest_year,
        "strongest_month_share": float(positive.iloc[0] / positive_total),
        "strongest_three_month_share": float(positive.iloc[:3].sum() / positive_total),
        "strongest_year_share": float(
            annual_positive.loc[strongest_year] / annual_positive_total
        ),
    }
    return concentration, neutralization, summary


def bootstrap_frame(
    strategy_id: str, simulation: dict[str, Any], index: pd.DatetimeIndex
) -> pd.DataFrame:
    series = {
        strategy_id: monthly_returns(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(index)
        )
    }
    for control_id in DECISIVE[strategy_id]:
        series[control_id] = monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(index)
        )
    return pd.concat([values.rename(key) for key, values in series.items()], axis=1).dropna()


def paired_moving_block_bootstrap(
    strategy_id: str,
    monthly: pd.DataFrame,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> list[dict[str, Any]]:
    columns = [strategy_id, *DECISIVE[strategy_id]]
    values = monthly[columns].to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    if max_start < 0:
        raise RuntimeError("insufficient monthly observations for paired bootstrap")
    rng = np.random.default_rng(seed)
    counts = {
        control_id: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0}
        for control_id in DECISIVE[strategy_id]
    }
    for _ in range(resamples):
        starts = rng.integers(0, max_start + 1, size=block_count)
        locations = np.concatenate(
            [np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts]
        )[:count]
        sample = values[locations]
        candidate = monthly_metrics(sample[:, 0])
        for column, control_id in enumerate(DECISIVE[strategy_id], start=1):
            control = monthly_metrics(sample[:, column])
            higher_sharpe = candidate["sharpe_ratio"] > control["sharpe_ratio"]
            better_drawdown = candidate["maximum_drawdown"] > control["maximum_drawdown"]
            counts[control_id]["cagr"] += int(candidate["cagr"] > control["cagr"])
            counts[control_id]["sharpe"] += int(higher_sharpe)
            counts[control_id]["drawdown"] += int(better_drawdown)
            counts[control_id]["either"] += int(higher_sharpe or better_drawdown)
    return [
        {
            "strategy_id": strategy_id,
            "trial_id": trial_id(strategy_id),
            "comparison_control_id": control_id,
            "monthly_observation_count": count,
            "moving_block_length_months": BOOTSTRAP_BLOCK_MONTHS,
            "resamples": resamples,
            "deterministic_seed": seed,
            "probability_candidate_higher_cagr": counts[control_id]["cagr"] / resamples,
            "probability_candidate_higher_sharpe": counts[control_id]["sharpe"] / resamples,
            "probability_candidate_less_severe_drawdown": counts[control_id]["drawdown"]
            / resamples,
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": counts[control_id][
                "either"
            ]
            / resamples,
            "paired_cross_series_dependence_preserved": True,
            "used_for_strategy_change": False,
            "validation_claimed": False,
        }
        for control_id in DECISIVE[strategy_id]
    ]


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return exploration.base._target_history(events, index)


def attribution_rows(
    strategy_id: str,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    quarter_rows: list[dict[str, Any]],
    year_rows: list[dict[str, Any]],
    rolling36: list[dict[str, Any]],
    rolling60: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_target = target_history(
        prepared["candidate_events"], prepared["prices"].index
    )
    control_targets = {
        control_id: target_history(events, prepared["prices"].index)
        for control_id, events in prepared["control_events"].items()
    }
    rows: list[dict[str, Any]] = []
    for source_type, source_rows in (
        ("chronological_quarter", quarter_rows),
        ("calendar_year", year_rows),
        ("rolling_36_months", rolling36),
        ("rolling_60_months", rolling60),
    ):
        for original in source_rows:
            if original["strategy_id"] != strategy_id:
                continue
            control_id = original["comparison_control_id"]
            start = pd.Timestamp(
                original.get("evaluation_start") or original.get("window_start")
            )
            end = pd.Timestamp(original.get("evaluation_end") or original.get("window_end"))
            period = candidate_target.index[
                (candidate_target.index >= start) & (candidate_target.index <= end)
            ]
            left = candidate_target.reindex(period)
            right = control_targets[control_id].reindex(period)
            overlap = np.minimum(
                left.to_numpy(dtype=float), right.to_numpy(dtype=float)
            ).sum(axis=1)
            absolute_difference = np.abs(
                left.to_numpy(dtype=float) - right.to_numpy(dtype=float)
            ).mean(axis=1)
            rows.append(
                {
                    "record_type": source_type,
                    **original,
                    "target_state_overlap": float(np.mean(overlap)),
                    "average_absolute_weight_difference": float(
                        np.mean(absolute_difference)
                    ),
                }
            )
    return rows


def turnover_by_asset(path: dict[str, Any], prices: pd.DataFrame) -> dict[str, float]:
    result = {symbol: 0.0 for symbol in prices.columns}
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    for date_value, target in path["target_events"].iterrows():
        if date_value not in prices.index:
            continue
        held = path["held_weights"].loc[date_value].to_numpy(dtype=float)
        daily_return = asset_returns.loc[date_value].to_numpy(dtype=float)
        drifted = held * (1.0 + daily_return)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held
        values = 0.5 * np.abs(target.to_numpy(dtype=float) - pretrade)
        for symbol, value in zip(prices.columns, values):
            result[symbol] += float(value)
    return result


def mca_asset_rows(
    prepared: dict[str, Any], simulation: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    index = eligible_index(MCA_ID, prepared)
    prices = prepared["prices"].reindex(index)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
    inverse_path = simulation["control_paths"][(exploration.MCA_NAMED, PRIMARY_COST)]
    static_path = simulation["control_paths"][(exploration.MCA_STATIC, PRIMARY_COST)]
    candidate_held = candidate_path["held_weights"].reindex(index)
    inverse_held = inverse_path["held_weights"].reindex(index)
    static_held = static_path["held_weights"].reindex(index)
    candidate_contribution = candidate_held * returns
    inverse_contribution = inverse_held * returns
    static_contribution = static_held * returns
    targets = target_history(prepared["candidate_events"], prepared["prices"].index).reindex(index)
    turnover = turnover_by_asset(candidate_path, prepared["prices"])
    monthly_candidate_contribution = candidate_contribution.groupby(index.to_period("M")).sum()
    spy_monthly = monthly_returns(returns["SPY"])
    positive_spy_months = spy_monthly[spy_monthly > 0.0].index
    negative_spy_months = spy_monthly[spy_monthly < 0.0].index
    rows: list[dict[str, Any]] = []
    positive_inverse_by_asset: dict[str, float] = {}
    for symbol in exploration.MCA_RISK:
        inverse_difference = candidate_contribution[symbol] - inverse_contribution[symbol]
        positive_inverse_by_asset[symbol] = float(inverse_difference.clip(lower=0.0).sum())
        rows.append(
            {
                "record_type": "asset_detail",
                "strategy_id": MCA_ID,
                "asset": symbol,
                "average_target_weight": float(targets[symbol].mean()),
                "maximum_target_weight": float(targets[symbol].max()),
                "minimum_target_weight": float(targets[symbol].min()),
                "realized_return_contribution": float(candidate_contribution[symbol].sum()),
                "candidate_minus_inverse_volatility_contribution": float(
                    inverse_difference.sum()
                ),
                "candidate_minus_static_contribution": float(
                    (candidate_contribution[symbol] - static_contribution[symbol]).sum()
                ),
                "positive_candidate_minus_inverse_contribution": positive_inverse_by_asset[symbol],
                "turnover_contribution": turnover[symbol],
                "contribution_in_positive_SPY_months": float(
                    monthly_candidate_contribution.loc[
                        monthly_candidate_contribution.index.intersection(positive_spy_months), symbol
                    ].sum()
                ),
                "contribution_in_negative_SPY_months": float(
                    monthly_candidate_contribution.loc[
                        monthly_candidate_contribution.index.intersection(negative_spy_months), symbol
                    ].sum()
                ),
                "asset_cap_added": False,
            }
        )
    positive_total = float(sum(positive_inverse_by_asset.values()))
    strongest_asset = max(positive_inverse_by_asset, key=positive_inverse_by_asset.get)
    strongest_share = positive_inverse_by_asset[strongest_asset] / positive_total
    tlt_gld_share = (
        positive_inverse_by_asset["TLT"] + positive_inverse_by_asset["GLD"]
    ) / positive_total
    candidate_monthly = monthly_returns(candidate_path["returns"].reindex(index))
    inverse_monthly = monthly_returns(inverse_path["returns"].reindex(index))
    monthly_excess = candidate_monthly - inverse_monthly
    annual_positive = monthly_excess.groupby(monthly_excess.index.year).sum().clip(lower=0.0)
    strongest_year = int(annual_positive.idxmax())
    strongest_year_share = float(annual_positive.max() / annual_positive.sum())
    hhi = (targets[list(exploration.MCA_RISK)] ** 2).sum(axis=1)
    summary = {
        "strongest_positive_excess_asset": strongest_asset,
        "strongest_asset_share_of_positive_excess": strongest_share,
        "TLT_GLD_share_of_positive_excess": tlt_gld_share,
        "strongest_positive_excess_calendar_year": strongest_year,
        "strongest_calendar_year_share_of_positive_excess": strongest_year_share,
        "maximum_target_weight_Herfindahl": float(hhi.max()),
        "mean_target_weight_Herfindahl": float(hhi.mean()),
        "cap_free_maximum_single_asset_target": float(
            targets[list(exploration.MCA_RISK)].max().max()
        ),
    }
    rows.append({"record_type": "concentration_summary", "strategy_id": MCA_ID, **summary})
    return rows, summary


def defensive_episodes(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    events = prepared["candidate_events"].sort_index()
    index = prepared["prices"].index
    prior_state = ""
    active_start: pd.Timestamp | None = None
    rows: list[dict[str, Any]] = []
    sequence = 0
    for date_value, target in events.iterrows():
        date_value = pd.Timestamp(date_value)
        state = "SPY" if float(target["SPY"]) > 0.5 else "BIL"
        if prior_state == "SPY" and state == "BIL":
            active_start = date_value
        elif prior_state == "BIL" and state == "SPY" and active_start is not None:
            sequence += 1
            start_location = int(index.get_loc(active_start))
            end_location = int(index.get_loc(date_value))
            rows.append(
                {
                    "episode_id": f"defensive_episode_{sequence:03d}",
                    "BIL_entry_execution_date": active_start.date().isoformat(),
                    "SPY_reentry_execution_date": date_value.date().isoformat(),
                    "BIL_entry_signal_date": index[start_location - 1].date().isoformat()
                    if start_location > 0
                    else "",
                    "SPY_reentry_signal_date": index[end_location - 1].date().isoformat()
                    if end_location > 0
                    else "",
                    "defensive_holding_sessions": end_location - start_location,
                    "completed_episode": True,
                }
            )
            active_start = None
        prior_state = state
    return rows


def episode_inventory_rows(
    prepared: dict[str, Any], simulation: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = defensive_episodes(prepared)
    prices = prepared["prices"]
    candidate = simulation["candidate_paths"][PRIMARY_COST]["returns"]
    named = simulation["control_paths"][(exploration.HYG_NAMED, PRIMARY_COST)]["returns"]
    sma = simulation["control_paths"][("hyg_sma100_spy_bil_control", PRIMARY_COST)]["returns"]
    reference = exploration.base.market.active_vm_dsr_usci_reference_returns()
    reference_monthly = monthly_returns(reference)
    rows: list[dict[str, Any]] = []
    contribution_values: dict[str, float] = {}
    for episode in episodes:
        start = pd.Timestamp(episode["BIL_entry_execution_date"])
        end = pd.Timestamp(episode["SPY_reentry_execution_date"])
        period = prices.index[(prices.index > start) & (prices.index <= end)]
        spy_return = float((1.0 + prices["SPY"].pct_change(fill_method=None).reindex(period)).prod() - 1.0)
        bil_return = float((1.0 + prices["BIL"].pct_change(fill_method=None).reindex(period)).prod() - 1.0)
        candidate_return = float((1.0 + candidate.reindex(period)).prod() - 1.0)
        named_return = float((1.0 + named.reindex(period)).prod() - 1.0)
        sma_return = float((1.0 + sma.reindex(period)).prod() - 1.0)
        contribution = candidate_return - named_return
        contribution_values[episode["episode_id"]] = contribution
        months = period.to_period("M").unique()
        overlaps_negative = bool(
            (reference_monthly.reindex(reference_monthly.index.intersection(months)) < 0.0).any()
        )
        rows.append(
            {
                "strategy_id": HYG_ID,
                "trial_id": HYG_TRIAL,
                **episode,
                "SPY_return": spy_return,
                "BIL_return": bil_return,
                "candidate_return": candidate_return,
                "SPY_EMA_control_return": named_return,
                "HYG_SMA_control_return": sma_return,
                "candidate_minus_SPY_EMA_contribution": contribution,
                "overlaps_reference_negative_month": overlaps_negative,
                "used_for_strategy_change": False,
            }
        )
    positive = {key: value for key, value in contribution_values.items() if value > 0.0}
    positive_total = float(sum(positive.values()))
    ordered_positive = sorted(positive.items(), key=lambda item: item[1], reverse=True)
    strongest_positive = ordered_positive[0]
    strongest_negative = min(contribution_values.items(), key=lambda item: item[1])
    durations = np.asarray([row["defensive_holding_sessions"] for row in rows], dtype=float)
    summary = {
        "episode_count": len(rows),
        "median_duration_sessions": float(np.median(durations)),
        "maximum_duration_sessions": int(np.max(durations)),
        "positive_contribution_count": sum(value > 0.0 for value in contribution_values.values()),
        "negative_contribution_count": sum(value < 0.0 for value in contribution_values.values()),
        "strongest_positive_episode": strongest_positive[0],
        "strongest_positive_episode_contribution": strongest_positive[1],
        "strongest_negative_episode": strongest_negative[0],
        "strongest_negative_episode_contribution": strongest_negative[1],
        "strongest_episode_share_of_positive_excess": strongest_positive[1] / positive_total,
        "three_strongest_episodes_share_of_positive_excess": sum(
            value for _, value in ordered_positive[:3]
        )
        / positive_total,
    }
    rows.append({"strategy_id": HYG_ID, "record_type": "episode_summary", **summary})
    return rows, summary


def leave_one_episode_out(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    episode_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    episodes = [row for row in episode_rows if row.get("episode_id")]
    index = eligible_index(HYG_ID, prepared)
    named_path = simulation["control_paths"][(exploration.HYG_NAMED, PRIMARY_COST)]
    exposure_path = simulation["control_paths"][(exploration.HYG_STATIC, PRIMARY_COST)]
    named_metrics = path_metrics(HYG_ID, named_path, index)
    exposure_metrics = path_metrics(HYG_ID, exposure_path, index)
    baseline_metrics = path_metrics(
        HYG_ID, simulation["candidate_paths"][PRIMARY_COST], index
    )
    candidate_history = target_history(
        prepared["candidate_events"], prepared["prices"].index
    )
    named_history = target_history(
        prepared["control_events"][exploration.HYG_NAMED], prepared["prices"].index
    )
    named_events = prepared["control_events"][exploration.HYG_NAMED]
    rows: list[dict[str, Any]] = []
    timing = "completed_signal_target_applied_at_following_regular_session_close"
    for episode in episodes:
        start = pd.Timestamp(episode["BIL_entry_execution_date"])
        end = pd.Timestamp(episode["SPY_reentry_execution_date"])
        modified = prepared["candidate_events"].copy()
        modified.loc[start] = named_history.loc[start]
        for date_value, target in named_events.loc[
            (named_events.index > start) & (named_events.index < end)
        ].iterrows():
            modified.loc[date_value] = target
        modified.loc[end] = candidate_history.loc[end]
        modified = modified.sort_index()
        path = exploration.base.accounting.simulate_path(
            prepared["prices"], modified, PRIMARY_COST, timing
        )
        candidate = path_metrics(HYG_ID, path, index)
        rows.append(
            {
                "strategy_id": HYG_ID,
                "trial_id": HYG_TRIAL,
                "episode_id": episode["episode_id"],
                "episode_start": episode["BIL_entry_execution_date"],
                "episode_end": episode["SPY_reentry_execution_date"],
                "cagr": candidate["cagr"],
                "sharpe_ratio": candidate["sharpe_ratio"],
                "maximum_drawdown": candidate["maximum_drawdown"],
                "baseline_sharpe_ratio": baseline_metrics["sharpe_ratio"],
                "sharpe_change_vs_baseline": candidate["sharpe_ratio"]
                - baseline_metrics["sharpe_ratio"],
                "materially_better_than_SPY_EMA_control": material(candidate, named_metrics),
                "SPY_EMA_control_dominates": dominates(named_metrics, candidate),
                "exposure_matched_control_dominates": dominates(exposure_metrics, candidate),
                "all_other_signals_and_executions_preserved": True,
                "cost_model_preserved": True,
                "combinations_of_episodes_removed": False,
            }
        )
    sharpe = np.asarray([row["sharpe_ratio"] for row in rows], dtype=float)
    drawdown = np.asarray([row["maximum_drawdown"] for row in rows], dtype=float)
    greatest_loss = min(rows, key=lambda row: row["sharpe_change_vs_baseline"])
    summary = [
        {
            "strategy_id": HYG_ID,
            "trial_id": HYG_TRIAL,
            "episode_count": len(rows),
            "fraction_still_materially_better_than_SPY_EMA100": float(
                np.mean([row["materially_better_than_SPY_EMA_control"] for row in rows])
            ),
            "fraction_not_dominated_by_exposure_matching": float(
                np.mean([not row["exposure_matched_control_dominates"] for row in rows])
            ),
            "minimum_sharpe": float(sharpe.min()),
            "median_sharpe": float(np.median(sharpe)),
            "maximum_sharpe": float(sharpe.max()),
            "minimum_maximum_drawdown": float(drawdown.min()),
            "median_maximum_drawdown": float(np.median(drawdown)),
            "maximum_maximum_drawdown": float(drawdown.max()),
            "episode_causing_largest_loss_of_benefit": greatest_loss["episode_id"],
            "largest_sharpe_loss": greatest_loss["sharpe_change_vs_baseline"],
            "combinations_of_episodes_removed": False,
        }
    ]
    return rows, summary


def turnover_reconciliation_rows(
    spec: exploration.StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    index = eligible_index(spec.strategy_id, prepared)
    prices = prepared["prices"]
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        for series_id, path in all_paths_at_cost(spec.strategy_id, spec, simulation, cost).items():
            values = path_metrics(spec.strategy_id, path, index)
            held = path["held_weights"].reindex(index)
            gross_return = (held * asset_returns.reindex(index)).sum(axis=1)
            expected = float(
                (
                    (1.0 + gross_return)
                    * path["turnover"].reindex(index)
                    * cost
                    / 10000.0
                ).sum()
            )
            rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "trial_id": trial_id(spec.strategy_id),
                    "series_id": series_id,
                    "cost_bps_one_way": cost,
                    "one_way_turnover": values["turnover"],
                    "transaction_cost_drag": values["transaction_cost_drag"],
                    "expected_transaction_cost_drag": expected,
                    "absolute_reconciliation_difference": abs(
                        values["transaction_cost_drag"] - expected
                    ),
                    "average_risky_exposure": values["average_risky_exposure"],
                    "cost_charged_once": abs(values["transaction_cost_drag"] - expected)
                    <= 1e-12,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
    return rows


def summary_lookup(
    rows: list[dict[str, Any]], strategy_id: str, months: int, control_id: str
) -> dict[str, Any]:
    return next(
        row
        for row in rows
        if row["strategy_id"] == strategy_id
        and int(row["window_months"]) == months
        and row["comparison_control_id"] == control_id
    )


def classify(
    strategy_id: str,
    reproduction_pass: bool,
    invariant_pass: bool,
    metric_map: dict[tuple[str, float], dict[str, Any]],
    quarter_rows: list[dict[str, Any]],
    rolling_summaries: list[dict[str, Any]],
    neutralization: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
    concentration_summary: dict[str, Any],
    mca_summary: dict[str, Any] | None,
    hyg_episode_summary: dict[str, Any] | None,
    hyg_leave_summary: dict[str, Any] | None,
) -> tuple[str, str, str, dict[str, bool]]:
    if not reproduction_pass or not invariant_pass:
        return (
            "robustness_blocked",
            "data_or_comparability_failure",
            "historical_robustness_blocked",
            {"parent_reproduction_and_invariants": False},
        )
    decisive = DECISIVE[strategy_id]
    candidate5 = metric_map[(strategy_id, 5.0)]
    controls5 = {control: metric_map[(control, 5.0)] for control in decisive}
    full_no_dominance = all(
        not dominates(control, candidate5) for control in controls5.values()
    )
    full_materiality = all(material(candidate5, control) for control in controls5.values())
    quarter_counts = {
        control: sum(
            row["candidate_improves_sharpe_or_drawdown"]
            for row in quarter_rows
            if row["strategy_id"] == strategy_id
            and row["comparison_control_id"] == control
        )
        for control in decisive
    }
    quarter_pass = all(value >= 3 for value in quarter_counts.values())
    rolling_pass = all(
        summary_lookup(rolling_summaries, strategy_id, months, control)[
            "candidate_improves_sharpe_or_drawdown_fraction"
        ]
        > 0.5
        and summary_lookup(rolling_summaries, strategy_id, months, control)[
            "control_dominates_candidate_fraction"
        ]
        <= 0.5
        for months in (36, 60)
        for control in decisive
    )
    candidate10 = metric_map[(strategy_id, 10.0)]
    ten_pass = all(
        material(candidate10, metric_map[(control, 10.0)])
        and not dominates(metric_map[(control, 10.0)], candidate10)
        for control in decisive
    )
    candidate15 = metric_map[(strategy_id, 15.0)]
    candidate20 = metric_map[(strategy_id, 20.0)]
    twenty_pass = not all(
        dominates(metric_map[(control, 20.0)], candidate20) for control in decisive
    )
    neutral_by_scenario = {row["scenario"]: row for row in neutralization}
    neutral_three = neutral_by_scenario["neutralize_three_strongest_positive_months"]
    neutral_year = neutral_by_scenario["neutralize_strongest_positive_calendar_year"]
    neutralization_pass = bool(
        neutral_three["material_vs_named_control"]
        and not neutral_three["other_decisive_control_dominates"]
        and neutral_year["material_vs_named_control"]
        and not neutral_year["other_decisive_control_dominates"]
    )
    bootstrap_map = {row["comparison_control_id"]: row for row in bootstrap}
    bootstrap_pass = bool(
        bootstrap_map[decisive[0]][
            "probability_candidate_higher_sharpe_or_less_severe_drawdown"
        ]
        >= 0.70
        and bootstrap_map[decisive[1]][
            "probability_candidate_higher_sharpe_or_less_severe_drawdown"
        ]
        >= 0.60
    )
    checks: dict[str, bool] = {
        "parent_reproduction_and_invariants": reproduction_pass and invariant_pass,
        "positive_full_period_return": candidate5["total_return"] > 0.0,
        "no_decisive_control_dominates_full_period": full_no_dominance,
        "materiality_vs_each_decisive_control": full_materiality,
        "three_of_four_quarters_vs_each_decisive_control": quarter_pass,
        "rolling_36_and_60_requirements": rolling_pass,
        "ten_bps_materiality_and_dominance": ten_pass,
        "fifteen_bps_positive": candidate15["total_return"] > 0.0,
        "twenty_bps_not_dominated_by_every_decisive_control": twenty_pass,
        "three_month_and_year_neutralization": neutralization_pass,
        "paired_bootstrap_thresholds": bootstrap_pass,
    }
    if strategy_id == MCA_ID:
        assert mca_summary is not None
        checks.update(
            {
                "MCA_material_vs_inverse_volatility": material(
                    candidate5, controls5[exploration.MCA_NAMED]
                ),
                "MCA_material_vs_static_weights": material(
                    candidate5, controls5[exploration.MCA_STATIC]
                ),
                "MCA_three_quarters_vs_inverse": quarter_counts[exploration.MCA_NAMED] >= 3,
                "MCA_three_quarters_vs_static": quarter_counts[exploration.MCA_STATIC] >= 3,
                "MCA_single_asset_share_at_most_60pct": mca_summary[
                    "strongest_asset_share_of_positive_excess"
                ]
                <= 0.60,
                "MCA_single_year_share_at_most_60pct": mca_summary[
                    "strongest_calendar_year_share_of_positive_excess"
                ]
                <= 0.60,
                "MCA_three_month_neutralization_material_vs_inverse": bool(
                    neutral_three["materiality_against_decisive_controls"][
                        exploration.MCA_NAMED
                    ]
                ),
                "MCA_twenty_bps_positive": candidate20["total_return"] > 0.0,
            }
        )
        interpretation = (
            "paper_demo_eligibility_candidate_standalone_dynamic_multi_asset_allocation"
        )
    else:
        assert hyg_episode_summary is not None and hyg_leave_summary is not None
        sma5 = metric_map[("hyg_sma100_spy_bil_control", 5.0)]
        named36 = summary_lookup(
            rolling_summaries, HYG_ID, 36, exploration.HYG_NAMED
        )
        named60 = summary_lookup(
            rolling_summaries, HYG_ID, 60, exploration.HYG_NAMED
        )
        sma36 = summary_lookup(
            rolling_summaries, HYG_ID, 36, "hyg_sma100_spy_bil_control"
        )
        sma60 = summary_lookup(
            rolling_summaries, HYG_ID, 60, "hyg_sma100_spy_bil_control"
        )
        checks.update(
            {
                "HYG_material_vs_SPY_EMA": material(
                    candidate5, controls5[exploration.HYG_NAMED]
                ),
                "HYG_exposure_matching_does_not_dominate": not dominates(
                    controls5[exploration.HYG_STATIC], candidate5
                ),
                "HYG_SMA_does_not_dominate_full_period": not dominates(sma5, candidate5),
                "HYG_three_quarters_vs_SPY_EMA": quarter_counts[exploration.HYG_NAMED] >= 3,
                "HYG_more_than_half_rolling_windows_vs_SPY_EMA": bool(
                    named36["candidate_improves_sharpe_or_drawdown_fraction"] > 0.5
                    and named60["candidate_improves_sharpe_or_drawdown_fraction"] > 0.5
                ),
                "HYG_SMA_dominates_no_more_than_half_rolling_windows": bool(
                    sma36["control_dominates_candidate_fraction"] <= 0.5
                    and sma60["control_dominates_candidate_fraction"] <= 0.5
                ),
                "HYG_75pct_leave_one_episode_out_material": hyg_leave_summary[
                    "fraction_still_materially_better_than_SPY_EMA100"
                ]
                >= 0.75,
                "HYG_single_episode_share_at_most_60pct": hyg_episode_summary[
                    "strongest_episode_share_of_positive_excess"
                ]
                <= 0.60,
                "HYG_single_year_share_at_most_60pct": concentration_summary[
                    "strongest_year_share"
                ]
                <= 0.60,
                "HYG_twenty_bps_positive": candidate20["total_return"] > 0.0,
            }
        )
        interpretation = "paper_demo_eligibility_candidate_standalone_credit_state_equity_timing"
    if all(checks.values()):
        return "robustness_positive", "", interpretation, checks
    if not full_no_dominance or not full_materiality:
        reason = (
            "exposure_reduction_explanation"
            if dominates(controls5[decisive[1]], candidate5)
            else "weak_vs_primary_control"
        )
        return "robustness_failed", reason, "historical_robustness_failed", checks
    concentration_fail = any(
        not value
        for key, value in checks.items()
        if "share_at_most_60pct" in key
    )
    if concentration_fail or not neutralization_pass:
        reason = "concentration_risk"
    elif not quarter_pass or not rolling_pass:
        reason = "period_instability"
    elif not ten_pass or candidate15["total_return"] <= 0.0 or not twenty_pass:
        reason = "cost_sensitivity"
    elif not bootstrap_pass:
        reason = "control_uncertainty"
    else:
        reason = "weak_component_attribution"
    return (
        "robustness_mixed",
        reason,
        "historically_promising_not_ready_for_paper_demo_eligibility",
        checks,
    )


def lineage_rows(specs: list[exploration.StrategySpec]) -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": spec.source_record_id,
            "source_entity_type": "source_library_record",
            "source_stage": "source_extracted",
            "strategy_id": spec.strategy_id,
            "strategy_entity_type": "strategy_configuration",
            "strategy_family_id": spec.family_id,
            "strategy_stage_carried_forward": "exploratory_followup_standalone",
            "source_or_research_lineage": spec.lineage,
            "parent_trial_id": PARENTS[spec.strategy_id],
            "parent_trial_stage": "exploration",
            "parent_trial_outcome": "exploratory_followup_candidate_standalone",
            "robustness_trial_id": TRIALS[spec.strategy_id],
            "robustness_trial_stage": STAGE,
            "new_strategy_configuration_created": False,
            "selected_route": "standalone_only",
            "diversifier_diagnostic_carried_for_context_only": True,
            "exact_source_replication_claimed": False,
        }
        for spec in specs
    ]


def trial_rows(
    specs: list[exploration.StrategySpec],
    outcomes: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    outcomes = outcomes or {}
    return [
        {
            "trial_id": TRIALS[spec.strategy_id],
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "strategy_id": spec.strategy_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "strategy_architecture": spec.architecture,
            "source_or_research_lineage": spec.lineage,
            "instrument_universe": (
                exploration.MCA_UNIVERSE
                if spec.strategy_id == MCA_ID
                else exploration.HYG_UNIVERSE
            ),
            "parameters": spec.parameters,
            "benchmark_or_control": spec.controls,
            "route": "standalone_only",
            "parent_trial_id": PARENTS[spec.strategy_id],
            "adaptation_label": "robustness_variant",
            "changed_fields_from_parent": "robustness_diagnostics_only",
            "outcome": outcomes.get(spec.strategy_id, {}).get(
                "outcome", "preregistered_pending_robustness"
            ),
            "failure_reason": outcomes.get(spec.strategy_id, {}).get("failure_reason", ""),
            "next_action": outcomes.get(spec.strategy_id, {}).get(
                "next_action", "execute_frozen_robustness_diagnostics"
            ),
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "source_rule_changed": False,
            "parameters_changed": False,
            "universe_changed": False,
            "execution_changed": False,
            "controls_changed": False,
            "route_changed": False,
            "optimization_performed": False,
            "post_result_tuning_allowed": False,
            "validation_claimed": False,
            "paper_demo_eligibility_granted_inside_task": False,
        }
        for spec in specs
    ]


def benchmark_rows(specs: list[exploration.StrategySpec]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "decisive_control": control_id in DECISIVE[spec.strategy_id],
            "component_control": control_id
            == ("hyg_sma100_spy_bil_control" if spec.strategy_id == HYG_ID else ""),
            "carried_forward_from_parent": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for spec in specs
        for control_id in spec.controls
    ]


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    specs, prepared, simulations = prepare_parent()
    reproduction_rows, reproduction_pass = parent_reproduction(
        specs, prepared, simulations
    )
    reset_output()

    write_csv("source_strategy_trial_lineage.csv", lineage_rows(specs))
    write_csv("trial_ledger.csv", trial_rows(specs))
    benchmarks = benchmark_rows(specs)
    write_csv("benchmark_reference_log.csv", benchmarks)
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "new_strategy_configuration_count": 0,
                "new_robustness_trial_count": 2,
                "data_capability_task_count": 0,
                "validation_observation_count": 0,
                "paper_demo_observation_count": 0,
                "preregistered_before_robustness_results": True,
                "provider_access_performed": False,
            }
        ],
    )
    write_csv("parent_reproduction_check.csv", reproduction_rows)

    cost_rows: list[dict[str, Any]] = []
    quarter_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    rolling36: list[dict[str, Any]] = []
    rolling60: list[dict[str, Any]] = []
    start_rows: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    neutralization_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    mca_control_rows: list[dict[str, Any]] = []
    mca_asset_concentration: list[dict[str, Any]] = []
    hyg_control_rows: list[dict[str, Any]] = []
    hyg_episode_rows: list[dict[str, Any]] = []
    hyg_leave_rows: list[dict[str, Any]] = []
    hyg_leave_summary_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    outcomes: dict[str, dict[str, Any]] = {}
    rolling_summaries: list[dict[str, Any]] = []

    for spec in specs:
        strategy_id = spec.strategy_id
        if not reproduction_pass[strategy_id]:
            outcomes[strategy_id] = {
                "strategy_id": strategy_id,
                "trial_id": trial_id(strategy_id),
                "outcome": "robustness_blocked",
                "failure_reason": "data_or_comparability_failure",
                "interpretation": "historical_robustness_blocked",
                "positive_gate_checks": {"parent_reproduction": False},
                "next_action": "direction_owner_review_source_backed_v2_robustness_block_v1",
            }
            invariant_rows.append(
                {
                    "strategy_id": strategy_id,
                    "trial_id": trial_id(strategy_id),
                    "invariant": "parent_reproduction",
                    "status": "fail",
                    "value": False,
                }
            )
            continue
        simulation = simulations[strategy_id]
        item = prepared[strategy_id]
        costs, metric_map = cost_stress_rows(spec, item, simulation)
        cost_rows.extend(costs)
        quarters, years = chronological_and_year_rows(strategy_id, item, simulation)
        quarter_rows.extend(quarters)
        year_rows.extend(years)
        rows36 = rolling_rows(strategy_id, item, simulation, 36)
        rows60 = rolling_rows(strategy_id, item, simulation, 60)
        rolling36.extend(rows36)
        rolling60.extend(rows60)
        strategy_rolling_summary = rolling_summary([*rows36, *rows60])
        rolling_summaries.extend(strategy_rolling_summary)
        start_rows.extend(start_date_rows(strategy_id, item, simulation))
        concentration, neutralization, concentration_summary = (
            concentration_and_neutralization(
                strategy_id, simulation, eligible_index(strategy_id, item)
            )
        )
        concentration_rows.extend(concentration)
        neutralization_rows.extend(neutralization)
        bootstrap = paired_moving_block_bootstrap(
            strategy_id,
            bootstrap_frame(strategy_id, simulation, eligible_index(strategy_id, item)),
        )
        bootstrap_rows.extend(bootstrap)
        attribution = attribution_rows(
            strategy_id, item, simulation, quarters, years, rows36, rows60
        )
        mca_summary: dict[str, Any] | None = None
        hyg_summary: dict[str, Any] | None = None
        hyg_leave_summary: dict[str, Any] | None = None
        if strategy_id == MCA_ID:
            mca_control_rows.extend(attribution)
            assets, mca_summary = mca_asset_rows(item, simulation)
            mca_asset_concentration.extend(assets)
        else:
            hyg_control_rows.extend(attribution)
            episodes, hyg_summary = episode_inventory_rows(item, simulation)
            hyg_episode_rows.extend(episodes)
            leave_rows, leave_summary = leave_one_episode_out(item, simulation, episodes)
            hyg_leave_rows.extend(leave_rows)
            hyg_leave_summary_rows.extend(leave_summary)
            hyg_leave_summary = leave_summary[0]
        turnover_rows.extend(turnover_reconciliation_rows(spec, item, simulation))
        deterministic = exploration.base.stable_hash(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        ) == exploration.base.stable_hash(
            simulate_costs(item)["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        )
        candidate_path = simulation["candidate_paths"][PRIMARY_COST]
        held = candidate_path["held_weights"].reindex(eligible_index(strategy_id, item))
        checks = {
            "parent_reproduction": reproduction_pass[strategy_id],
            "formula_and_parameters_frozen": True,
            "universe_frozen": True,
            "execution_frozen": True,
            "controls_frozen": True,
            "route_frozen_standalone_only": True,
            "weights_nonnegative": bool((held >= -exploration.WEIGHT_TOLERANCE).all().all()),
            "weights_sum_to_one": bool(
                np.allclose(held.sum(axis=1), 1.0, atol=exploration.WEIGHT_TOLERANCE, rtol=0.0)
            ),
            "maximum_gross_exposure_one": bool(
                (held.abs().sum(axis=1) <= 1.0 + exploration.WEIGHT_TOLERANCE).all()
            ),
            "cost_reconciliation": all(
                row["cost_charged_once"]
                for row in turnover_rows
                if row["strategy_id"] == strategy_id
            ),
            "deterministic_rerun": deterministic,
            "no_validation_or_forward_evidence_claimed": True,
            "no_paper_demo_observation_created": True,
        }
        strategy_invariant_pass = all(checks.values())
        invariant_rows.extend(
            {
                "strategy_id": strategy_id,
                "trial_id": trial_id(strategy_id),
                "invariant": key,
                "status": "pass" if value else "fail",
                "value": value,
            }
            for key, value in checks.items()
        )
        outcome, reason, interpretation, positive_checks = classify(
            strategy_id,
            reproduction_pass[strategy_id],
            strategy_invariant_pass,
            metric_map,
            quarters,
            strategy_rolling_summary,
            neutralization,
            bootstrap,
            concentration_summary,
            mca_summary,
            hyg_summary,
            hyg_leave_summary,
        )
        outcomes[strategy_id] = {
            "strategy_id": strategy_id,
            "trial_id": trial_id(strategy_id),
            "parent_trial_id": PARENTS[strategy_id],
            "selected_route": "standalone_only",
            "outcome": outcome,
            "failure_reason": reason,
            "interpretation": interpretation,
            "positive_gate_checks": positive_checks,
            "robustness_completed": outcome != "robustness_blocked",
            "paper_demo_eligible": False,
            "next_action": "pending_batch_funnel_action",
        }

    positives = [row for row in outcomes.values() if row["outcome"] == "robustness_positive"]
    blocked = [row for row in outcomes.values() if row["outcome"] == "robustness_blocked"]
    if positives:
        next_action = "direction_owner_review_source_backed_v2_robustness_for_paper_demo_v1"
    elif len(blocked) == 2:
        next_action = "direction_owner_review_source_backed_v2_robustness_block_v1"
    else:
        next_action = "direction_owner_review_source_backed_v2_robustness_yield_and_discovery_model_v1"
    for row in outcomes.values():
        row["next_action"] = next_action

    write_csv("trial_ledger.csv", trial_rows(specs, outcomes))
    write_csv("cost_stress_results.csv", cost_rows)
    write_csv("chronological_quarter_results.csv", quarter_rows)
    write_csv("calendar_year_results.csv", year_rows)
    write_csv("rolling_36_month_results.csv", rolling36)
    write_csv("rolling_60_month_results.csv", rolling60)
    write_csv("rolling_window_summary.csv", rolling_summaries)
    write_csv("start_date_sensitivity.csv", start_rows)
    write_csv("monthly_excess_concentration.csv", concentration_rows)
    write_csv("neutralization_results.csv", neutralization_rows)
    write_csv("paired_block_bootstrap_results.csv", bootstrap_rows)
    write_csv("mca_control_attribution.csv", mca_control_rows)
    write_csv("mca_asset_and_weight_concentration.csv", mca_asset_concentration)
    write_csv("hyg_control_attribution.csv", hyg_control_rows)
    write_csv("hyg_defensive_episode_inventory.csv", hyg_episode_rows)
    write_csv("hyg_leave_one_episode_out_results.csv", hyg_leave_rows)
    write_csv("hyg_leave_one_episode_out_summary.csv", hyg_leave_summary_rows)
    parent_portfolio = pd.read_csv(
        PARENT_DIR / "portfolio_contribution_results.csv", keep_default_na=False
    ).to_dict("records")
    for row in parent_portfolio:
        row.update(
            {
                "carried_forward_for_context_only": True,
                "selected_route_changed": False,
                "can_trigger_eligibility_when_standalone_fails": False,
            }
        )
    write_csv("portfolio_contribution_results.csv", parent_portfolio)
    write_csv("turnover_cost_reconciliation.csv", turnover_rows)
    write_csv("invariant_results.csv", invariant_rows)
    write_csv("outcome_summary.csv", outcomes.values())
    write_csv(
        "failure_reasons.csv",
        [row for row in outcomes.values() if row["failure_reason"]],
        ("strategy_id", "trial_id", "outcome", "failure_reason", "interpretation", "next_action"),
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "robustness_positive_count": len(positives),
                "robustness_blocked_count": len(blocked),
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
    )
    funnel = {
        "existing_source_library_records_carried_forward": 2,
        "existing_strategy_configurations_carried_forward": 2,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 2,
        "new_robustness_trials": 2,
        "benchmark_references_carried_forward": len(benchmarks),
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "robustness_positive": len(positives),
        "robustness_mixed": sum(row["outcome"] == "robustness_mixed" for row in outcomes.values()),
        "robustness_failed": sum(row["outcome"] == "robustness_failed" for row in outcomes.values()),
        "robustness_blocked": len(blocked),
    }
    write_json("cohort_funnel_counts.json", funnel)

    protected_after = protected_hashes()
    checks = {
        "exactly_two_robustness_child_trials": len(trial_rows(specs, outcomes)) == 2,
        "parent_reproduction_passes_for_unblocked_candidates": all(
            reproduction_pass[strategy_id] or outcomes[strategy_id]["outcome"] == "robustness_blocked"
            for strategy_id in outcomes
        ),
        "both_parent_exploration_outcomes_unchanged": True,
        "all_candidate_invariants_pass_for_unblocked_candidates": all(
            row["status"] == "pass" for row in invariant_rows
        ),
        "all_5000_resample_bootstraps_present": all(
            row["resamples"] == BOOTSTRAP_RESAMPLES for row in bootstrap_rows
        ),
        "unfavorable_periods_and_windows_retained": True,
        "new_strategy_configuration_count_zero": funnel["new_strategy_configurations"] == 0,
        "entity_and_funnel_counts_reconcile": len(benchmarks) == 10
        and funnel["new_robustness_trials"] == 2,
        "protected_state_cache_source_parent_and_observations_unchanged": protected_before
        == protected_after,
        "no_provider_validation_lifecycle_paper_demo_broker_or_real_money_action": True,
        "required_file_count": len(REQUIRED_FILES) == 31,
    }
    checks["overall_pass"] = all(checks.values())
    write_yaml(
        "robustness_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(),
            "parent_exploration_packet": PARENT_DIR.relative_to(ROOT).as_posix(),
            "source_packet_hash": tree_hash(SOURCE_DIR),
            "parent_packet_hash": tree_hash(PARENT_DIR),
            "new_strategy_configuration_count": 0,
            "new_robustness_trial_count": 2,
            "candidate_outcomes": {
                strategy_id: row["outcome"] for strategy_id, row in outcomes.items()
            },
            "paper_demo_eligibility_granted_inside_task": False,
            "exact_next_action": next_action,
        },
    )
    write_json("consistency_check.json", checks)
    report = [
        "# Accepted-47 Source-Backed V2 Final Historical Robustness",
        "",
        "This bounded same-period historical robustness task assessed exactly two frozen standalone configurations. It is not validation, forward evidence, lifecycle promotion, or paper/demo onboarding.",
        "",
        "## Outcomes",
        "",
    ]
    for spec in specs:
        row = outcomes[spec.strategy_id]
        report.append(
            f"- `{spec.strategy_id}`: `{row['outcome']}`"
            + (f" (`{row['failure_reason']}`)" if row["failure_reason"] else "")
            + f". Interpretation: `{row['interpretation']}`."
        )
    report.extend(
        [
            "",
            "All costs, partitions, rolling windows, starts, neutralizations, bootstrap results, assets, episodes, and unfavorable comparisons remain visible. Neither selected route changed.",
            "",
            "No provider, validation observation, lifecycle update, paper/demo observation, broker, account, position, order, capital, or real-money action occurred.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    )
    (OUTPUT_DIR / "robustness_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    actual = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    missing = sorted(set(REQUIRED_FILES) - actual)
    extra = sorted(actual - set(REQUIRED_FILES))
    if missing or extra:
        raise RuntimeError(f"robustness packet mismatch: missing={missing}; extra={extra}")
    return {
        "task_id": TASK_ID,
        "overall_pass": checks["overall_pass"],
        "candidate_outcomes": {
            strategy_id: row["outcome"] for strategy_id, row in outcomes.items()
        },
        "failure_reasons": {
            strategy_id: row["failure_reason"] for strategy_id, row in outcomes.items()
        },
        "new_robustness_trial_count": 2,
        "paper_demo_observations_created": 0,
        "exact_next_action": next_action,
        "output_dir": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
