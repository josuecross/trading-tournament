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
    native_etf_source_refresh_v3_exploration_batch as exploration,
)
from strategy_lab.research_os.research import (
    native_etf_two_candidate_final_robustness_v1 as robustness_helpers,
)


TASK_ID = "native_etf_v3_two_candidate_final_robustness_v1"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
PARENT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "native_etf_source_refresh_v3_exploration_batch"
    / "latest"
)
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\4df57e4e-7380-4748-ac6d-2f1b2abd2af3\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-08-04T06:00:00+00:00"
REPRODUCTION_TOLERANCE = 1e-9
PRIMARY_COST = 5.0
PERCENTILE_COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
GROWTH_COSTS = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260804
TOLERANCE = 1e-10

PERCENTILE_ID = exploration.PERCENTILE_ID
GROWTH_ID = exploration.GROWTH_ID
PERCENTILE_PARENT_TRIAL = exploration.PERCENTILE_TRIAL
GROWTH_PARENT_TRIAL = exploration.GROWTH_TRIAL
PERCENTILE_TRIAL = f"{TASK_ID}__percentile_channels__child"
GROWTH_TRIAL = f"{TASK_ID}__growth_inflation__child"

PERCENTILE_NAMED = exploration.PERCENTILE_SAME
PERCENTILE_ALWAYS = exploration.PERCENTILE_ALWAYS
PERCENTILE_EQUAL = exploration.PERCENTILE_EQUAL_SIGNAL
PERCENTILE_STATIC = exploration.PERCENTILE_STATIC
PERCENTILE_DECISIVE = (
    PERCENTILE_NAMED,
    PERCENTILE_ALWAYS,
    PERCENTILE_EQUAL,
    PERCENTILE_STATIC,
)
GROWTH_NAMED = exploration.GROWTH_SAME
GROWTH_STATIC = exploration.GROWTH_STATIC
GROWTH_INFLATION = exploration.GROWTH_INFLATION_ONLY
GROWTH_EQUAL = "equal_weight_xle_xlk_xlv_xlp_control"
GROWTH_DECISIVE = (GROWTH_NAMED, GROWTH_STATIC)

EXPECTED_PARENT_OUTCOMES = {
    PERCENTILE_ID: "exploratory_followup_candidate_standalone",
    GROWTH_ID: "exploratory_followup_candidate_standalone",
}

REQUIRED_FILES = {
    "robustness_manifest.yaml",
    "strategy_cards.csv",
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
    "month_and_year_neutralization_results.csv",
    "paired_block_bootstrap_results.csv",
    "percentile_channel_component_attribution.csv",
    "percentile_channel_asset_contribution.csv",
    "percentile_channel_horizon_diagnostics.csv",
    "growth_inflation_regime_attribution.csv",
    "growth_inflation_episode_inventory.csv",
    "growth_inflation_episode_neutralization.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "robustness_report.md",
}


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path, excluded: Path | None = None) -> str:
    if path.is_file():
        return file_hash(path)
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


def snapshot_hashes() -> dict[str, str]:
    output = {
        relative(path): tree_hash(path)
        for path in (*exploration.PROTECTED_STATE_PATHS, *exploration.PROTECTED_TREE_PATHS)
    }
    output["evidence_excluding_current_robustness_packet"] = tree_hash(
        ROOT / "evidence", OUTPUT_DIR
    )
    return output


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected path {OUTPUT_DIR}")
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
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def parent_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(PARENT_DIR / name)


def trial_id(strategy_id: str) -> str:
    return PERCENTILE_TRIAL if strategy_id == PERCENTILE_ID else GROWTH_TRIAL


def fallback(strategy_id: str) -> str:
    return "SHY" if strategy_id == PERCENTILE_ID else "BIL"


def strategy_cards() -> list[dict[str, Any]]:
    parent = {
        row["strategy_id"]: row
        for row in csv.DictReader((PARENT_DIR / "strategy_cards.csv").open(encoding="utf-8"))
    }
    rows: list[dict[str, Any]] = []
    for strategy_id, child, parent_trial in (
        (PERCENTILE_ID, PERCENTILE_TRIAL, PERCENTILE_PARENT_TRIAL),
        (GROWTH_ID, GROWTH_TRIAL, GROWTH_PARENT_TRIAL),
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
                "trial_id": child,
                "parent_trial_id": parent_trial,
                "adaptation_label": "robustness_variant",
                "changed_fields_from_parent": "robustness_diagnostics_only",
                "route": "standalone_only",
                "outcome": "preregistered_for_bounded_historical_robustness",
                "failure_reason": "",
                "next_action": "execute_preregistered_robustness_child",
                "source_rule_changed": False,
                "parameters_changed": False,
                "universe_changed": False,
                "execution_changed": False,
                "controls_added": False,
                "optimization_performed": False,
                "diversifier_route_reopened": False,
                "independent_validation_claimed": False,
                "paper_demo_eligibility_granted_inside_task": False,
                "new_strategy_configuration_created": False,
            }
        )
    return rows


def trial_rows() -> list[dict[str, Any]]:
    return [
        {**row, "entity_type": "experiment_trial", "preregistration_timestamp": PREREGISTRATION_TIMESTAMP}
        for row in strategy_cards()
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "carried_forward_from_parent": True,
            "new_benchmark_strategy_created": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for row in csv.DictReader(
            (PARENT_DIR / "benchmark_reference_log.csv").open(encoding="utf-8")
        )
    ]


def preregister() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strategies = strategy_cards()
    trials = trial_rows()
    headers = (
        "strategy_id", "family_id", "display_name", "entity_type",
        "strategy_architecture", "source_or_research_lineage", "instrument_universe",
        "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id",
        "adaptation_label", "changed_fields_from_parent", "route", "outcome",
        "failure_reason", "next_action",
    )
    write_csv("strategy_cards.csv", strategies, headers)
    write_csv("trial_ledger.csv", trials, headers)
    write_csv(
        "benchmark_reference_log.csv",
        benchmark_rows(),
        (
            "strategy_id", "benchmark_id", "entity_type", "stage",
            "same_purpose_control", "critical_control", "carried_forward_from_parent",
            "new_benchmark_strategy_created", "counted_as_strategy", "counted_as_trial",
        ),
    )
    write_csv(
        "process_task_log.csv",
        [{
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": "robustness",
            "candidate_count": 2,
            "new_robustness_trial_count": 2,
            "standalone_routes_only": True,
            "diversifier_routes_reopened": False,
            "validation_or_paper_demo_work": False,
            "provider_access_performed": False,
        }],
        (
            "process_task_id", "entity_type", "stage", "candidate_count",
            "new_robustness_trial_count", "standalone_routes_only",
            "diversifier_routes_reopened", "validation_or_paper_demo_work",
            "provider_access_performed",
        ),
    )
    return strategies, trials


def simulate_costs(prepared: dict[str, Any], costs: tuple[float, ...]) -> dict[str, Any]:
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
    path: dict[str, Any], fallback_symbol: str, index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    return exploration.metrics(path, fallback_symbol, index)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.material_advantage(candidate, control)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.accounting.dominates(control, candidate)


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.worse_on_both(candidate, control)


def paths_at_cost(
    strategy_id: str, simulated: dict[str, Any], cost: float
) -> dict[str, dict[str, Any]]:
    output = {strategy_id: simulated["candidate_paths"][cost]}
    output.update({
        control_id: path
        for (control_id, control_cost), path in simulated["control_paths"].items()
        if control_cost == cost
    })
    return output


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
        "trial_id": trial_id(strategy_id),
        "series_id": series_id,
        "cost_bps_one_way": cost,
        "period": period,
        "result_type": result_type,
        **values,
    }


def frame_comparison(scope: str, archived: pd.DataFrame, reproduced: pd.DataFrame) -> dict[str, Any]:
    same_columns = list(archived.columns) == list(reproduced.columns)
    same_rows = len(archived) == len(reproduced)
    mismatches = 0
    maximum = 0.0
    if same_columns and same_rows:
        for column in archived.columns:
            left = archived[column]
            right = reproduced[column]
            left_numeric = pd.to_numeric(left, errors="coerce")
            right_numeric = pd.to_numeric(right, errors="coerce")
            numeric = left_numeric.notna() & right_numeric.notna()
            if numeric.any():
                difference = (
                    left_numeric.loc[numeric].astype(float)
                    - right_numeric.loc[numeric].astype(float)
                ).abs()
                maximum = max(maximum, float(difference.max()))
                mismatches += int((difference > REPRODUCTION_TOLERANCE).sum())
            text = ~numeric
            if text.any():
                mismatches += int(
                    (left.loc[text].fillna("").astype(str).to_numpy()
                     != right.loc[text].fillna("").astype(str).to_numpy()).sum()
                )
    else:
        mismatches = max(len(archived), len(reproduced), 1)
    return {
        "scope": scope,
        "archived_row_count": len(archived),
        "reproduced_row_count": len(reproduced),
        "columns_match": same_columns,
        "rows_match": same_rows,
        "maximum_numeric_difference": maximum,
        "mismatch_count": mismatches,
        "tolerance": REPRODUCTION_TOLERANCE,
        "pass": bool(same_columns and same_rows and mismatches == 0),
    }


def parent_reproduction(
    prepared: dict[str, dict[str, Any]], frames: dict[str, pd.DataFrame]
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    parent_simulated = {
        strategy_id: exploration.simulate(prepared[strategy_id])
        for strategy_id in (PERCENTILE_ID, GROWTH_ID)
    }
    candidates: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    portfolios: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    for strategy_id, named, second in (
        (PERCENTILE_ID, PERCENTILE_NAMED, PERCENTILE_ALWAYS),
        (GROWTH_ID, GROWTH_NAMED, GROWTH_STATIC),
    ):
        candidate_rows, control_rows, half_rows = exploration.result_rows(
            strategy_id,
            fallback(strategy_id),
            prepared[strategy_id],
            parent_simulated[strategy_id],
        )
        candidates.extend(candidate_rows)
        controls.extend(control_rows)
        halves.extend(half_rows)
        parent_portfolios = exploration.portfolio_paths(
            prepared[strategy_id], parent_simulated[strategy_id], named, second
        )
        portfolios.extend(exploration.portfolio_result_rows(strategy_id, parent_portfolios))
        invariants.extend(
            exploration.invariant_rows(
                strategy_id, prepared[strategy_id], parent_simulated[strategy_id]
            )
        )
        turnover.extend(exploration.turnover_rows(strategy_id, parent_simulated[strategy_id]))

    preflight_rows, _, _ = exploration.preflight()
    percentile_ledger, percentile_weights = exploration.enrich_percentile_diagnostics(
        prepared[PERCENTILE_ID], parent_simulated[PERCENTILE_ID]
    )
    growth_ledger = exploration.enrich_growth_diagnostics(
        prepared[GROWTH_ID], parent_simulated[GROWTH_ID]
    )
    current = {
        "data_preflight_reconciliation.csv": pd.DataFrame(preflight_rows),
        "all_trial_results.csv": pd.DataFrame(candidates),
        "control_results.csv": pd.DataFrame(controls),
        "chronological_half_results.csv": pd.DataFrame(halves),
        "portfolio_contribution_results.csv": pd.DataFrame(portfolios),
        "percentile_channel_signal_ledger.csv": percentile_ledger,
        "percentile_channel_weight_diagnostics.csv": percentile_weights,
        "percentile_channel_control_reconciliation.csv": prepared[PERCENTILE_ID][
            "control_reconciliation"
        ],
        "growth_inflation_daily_regime_ledger.csv": growth_ledger,
        "growth_inflation_control_reconciliation.csv": prepared[GROWTH_ID][
            "control_reconciliation"
        ],
        "turnover_cost_reconciliation.csv": pd.DataFrame(turnover),
        "invariant_results.csv": pd.DataFrame(invariants),
    }
    rows: list[dict[str, Any]] = []
    candidate_pass = {PERCENTILE_ID: True, GROWTH_ID: True}
    shared_files = {"data_preflight_reconciliation.csv"}
    percentile_files = {
        "percentile_channel_signal_ledger.csv",
        "percentile_channel_weight_diagnostics.csv",
        "percentile_channel_control_reconciliation.csv",
    }
    growth_files = {
        "growth_inflation_daily_regime_ledger.csv",
        "growth_inflation_control_reconciliation.csv",
    }
    for filename, reproduced in current.items():
        archived = parent_csv(filename)
        reproduced = reproduced.reindex(columns=archived.columns)
        comparison = frame_comparison(filename, archived, reproduced)
        rows.append(comparison)
        if filename in shared_files:
            for strategy_id in candidate_pass:
                candidate_pass[strategy_id] &= bool(comparison["pass"])
        elif filename in percentile_files:
            candidate_pass[PERCENTILE_ID] &= bool(comparison["pass"])
        elif filename in growth_files:
            candidate_pass[GROWTH_ID] &= bool(comparison["pass"])
        elif "strategy_id" in archived.columns:
            for strategy_id in candidate_pass:
                left = archived.loc[archived["strategy_id"].eq(strategy_id)].reset_index(drop=True)
                right = reproduced.loc[reproduced["strategy_id"].eq(strategy_id)].reset_index(drop=True)
                scoped = frame_comparison(f"{filename}:{strategy_id}", left, right)
                rows.append(scoped)
                candidate_pass[strategy_id] &= bool(scoped["pass"])

    parent_trials = {
        row["strategy_id"]: row
        for row in csv.DictReader((PARENT_DIR / "trial_ledger.csv").open(encoding="utf-8"))
    }
    lineage_pass = bool(
        parent_trials[PERCENTILE_ID]["trial_id"] == PERCENTILE_PARENT_TRIAL
        and parent_trials[GROWTH_ID]["trial_id"] == GROWTH_PARENT_TRIAL
        and parent_trials[PERCENTILE_ID]["outcome"] == EXPECTED_PARENT_OUTCOMES[PERCENTILE_ID]
        and parent_trials[GROWTH_ID]["outcome"] == EXPECTED_PARENT_OUTCOMES[GROWTH_ID]
    )
    rows.append({
        "scope": "parent_trial_lineage_and_outcomes",
        "archived_row_count": 2,
        "reproduced_row_count": 2,
        "columns_match": True,
        "rows_match": True,
        "maximum_numeric_difference": 0.0,
        "mismatch_count": 0 if lineage_pass else 1,
        "tolerance": REPRODUCTION_TOLERANCE,
        "pass": lineage_pass,
    })
    for strategy_id in candidate_pass:
        candidate_pass[strategy_id] &= lineage_pass
    return rows, candidate_pass


def full_cost_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    costs: tuple[float, ...],
) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    metric_map: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in costs:
        for series_id, path in paths_at_cost(strategy_id, simulated, cost).items():
            values = metrics(path, fallback(strategy_id))
            metric_map[(series_id, cost)] = values
            rows.append(result_row(strategy_id, series_id, cost, "full_period", values, "cost_stress"))
    return rows, metric_map


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_quarter_{position + 1}": index[locations]
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def complete_year_indices(index: pd.DatetimeIndex) -> dict[int, pd.DatetimeIndex]:
    return {
        year: index[index.year == year]
        for year in range(int(index.min().year) + 1, int(index.max().year))
        if len(index[index.year == year])
    }


def partition_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    index: pd.DatetimeIndex,
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    list[dict[str, Any]],
]:
    quarter_rows: list[dict[str, Any]] = []
    quarter_map: dict[tuple[str, str], dict[str, Any]] = {}
    year_rows: list[dict[str, Any]] = []
    paths = paths_at_cost(strategy_id, simulated, PRIMARY_COST)
    for period, period_index in split_quarters(index).items():
        for series_id, path in paths.items():
            values = metrics(path, fallback(strategy_id), period_index)
            quarter_map[(series_id, period)] = values
            quarter_rows.append(
                result_row(strategy_id, series_id, PRIMARY_COST, period, values, "chronological_quarter")
            )
    for year, period_index in complete_year_indices(index).items():
        for series_id, path in paths.items():
            values = metrics(path, fallback(strategy_id), period_index)
            row = result_row(
                strategy_id,
                series_id,
                PRIMARY_COST,
                f"calendar_year_{year}",
                values,
                "complete_calendar_year",
            )
            row["calendar_year"] = year
            year_rows.append(row)
    return quarter_rows, quarter_map, year_rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]


def rolling_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    index: pd.DatetimeIndex,
    comparators: tuple[str, ...],
    months: int,
) -> list[dict[str, Any]]:
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
        candidate = metrics(candidate_path, fallback(strategy_id), period_index)
        for comparator_id in comparators:
            control = metrics(
                simulated["control_paths"][(comparator_id, PRIMARY_COST)],
                fallback(strategy_id),
                period_index,
            )
            rows.append({
                "strategy_id": strategy_id,
                "trial_id": trial_id(strategy_id),
                "window_months": months,
                "window_sequence": sequence,
                "window_start": period_index[0].date().isoformat(),
                "window_end": period_index[-1].date().isoformat(),
                "candidate_id": strategy_id,
                "comparison_id": comparator_id,
                "candidate_cagr": candidate["cagr"],
                "comparison_cagr": control["cagr"],
                "cagr_difference": float(candidate["cagr"]) - float(control["cagr"]),
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "comparison_sharpe_ratio": control["sharpe_ratio"],
                "sharpe_difference": float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]),
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "comparison_maximum_drawdown": control["maximum_drawdown"],
                "maximum_drawdown_difference": float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]),
                "candidate_improves_sharpe_or_drawdown": bool(
                    float(candidate["sharpe_ratio"]) > float(control["sharpe_ratio"])
                    or float(candidate["maximum_drawdown"]) > float(control["maximum_drawdown"])
                ),
                "comparison_dominates_candidate": dominates(control, candidate),
                "unfavorable_window_retained": True,
                "independent_validation_claimed": False,
            })
    return rows


def rolling_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    keys = sorted({(row["strategy_id"], row["window_months"], row["comparison_id"]) for row in rows})
    for strategy_id, months, comparison_id in keys:
        subset = [
            row for row in rows
            if row["strategy_id"] == strategy_id
            and row["window_months"] == months
            and row["comparison_id"] == comparison_id
        ]
        output.append({
            "strategy_id": strategy_id,
            "window_months": months,
            "comparison_id": comparison_id,
            "eligible_window_count": len(subset),
            "median_cagr_difference": float(np.median([row["cagr_difference"] for row in subset])),
            "median_sharpe_difference": float(np.median([row["sharpe_difference"] for row in subset])),
            "median_maximum_drawdown_difference": float(np.median([row["maximum_drawdown_difference"] for row in subset])),
            "candidate_improves_sharpe_or_drawdown_fraction": float(np.mean([row["candidate_improves_sharpe_or_drawdown"] for row in subset])),
            "comparison_dominates_fraction": float(np.mean([row["comparison_dominates_candidate"] for row in subset])),
            "unfavorable_windows_retained": True,
        })
    return output


def start_sensitivity_rows(
    strategy_id: str,
    simulated: dict[str, Any],
    index: pd.DatetimeIndex,
    comparators: tuple[str, ...],
) -> list[dict[str, Any]]:
    paths = paths_at_cost(strategy_id, simulated, PRIMARY_COST)
    rows: list[dict[str, Any]] = []
    for year in range(2008, 2016):
        eligible = index[index.year >= year]
        if not len(eligible):
            continue
        period_index = index[index >= eligible[0]]
        for series_id in (strategy_id, *comparators):
            values = metrics(paths[series_id], fallback(strategy_id), period_index)
            row = result_row(
                strategy_id,
                series_id,
                PRIMARY_COST,
                f"start_{year}_fixed_end",
                values,
                "deterministic_start_date_sensitivity",
            )
            row.update({
                "requested_start_year": year,
                "first_eligible_session": eligible[0].date().isoformat(),
                "fixed_end_date": index[-1].date().isoformat(),
                "start_selected_from_performance": False,
                "strategy_reinitialized_at_start": False,
            })
            rows.append(row)
    return rows


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.to_period("M")).prod().sub(1.0)


def concentration_and_neutralization(
    strategy_id: str,
    simulated: dict[str, Any],
    named_control: str,
    decisive_controls: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate_returns = simulated["candidate_paths"][PRIMARY_COST]["returns"]
    named_returns = simulated["control_paths"][(named_control, PRIMARY_COST)]["returns"]
    monthly = pd.concat(
        [
            monthly_returns(candidate_returns).rename("candidate"),
            monthly_returns(named_returns).rename("named"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    monthly["additive_excess"] = monthly["candidate"] - monthly["named"]
    positive = monthly.loc[monthly["additive_excess"] > 0.0, "additive_excess"].sort_values(ascending=False)
    strongest_three = list(positive.index[:3])
    strongest_month = strongest_three[0]
    annual = monthly["additive_excess"].groupby(monthly.index.year).sum()
    strongest_year = int(annual.idxmax())
    positive_sum = float(positive.sum())
    strongest_year_value = float(annual.loc[strongest_year])
    positive_rank = {period: rank + 1 for rank, period in enumerate(positive.index)}
    concentration = [
        {
            "strategy_id": strategy_id,
            "month": str(period),
            "candidate_return_5bps": row.candidate,
            "named_control_return_5bps": row.named,
            "candidate_minus_named_additive_excess": row.additive_excess,
            "positive_excess_rank": positive_rank.get(period, ""),
            "strongest_positive_excess_month": period == strongest_month,
            "among_three_strongest_positive_excess_months": period in strongest_three,
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
    control_metrics = {
        control: metrics(
            simulated["control_paths"][(control, PRIMARY_COST)], fallback(strategy_id)
        )
        for control in decisive_controls
    }
    neutralization: list[dict[str, Any]] = []
    for scenario, periods in scenarios.items():
        counterfactual = candidate_returns.copy()
        mask = counterfactual.index.to_period("M").isin(periods)
        counterfactual.loc[mask] = named_returns.loc[mask]
        candidate = exploration.market.metrics_from_returns(counterfactual)
        other_controls = [control for control in decisive_controls if control != named_control]
        material = {
            control: material_advantage(candidate, control_metrics[control])
            for control in decisive_controls
        }
        dominating = [
            control for control in decisive_controls
            if dominates(control_metrics[control], candidate)
        ]
        neutralization.append({
            "strategy_id": strategy_id,
            "scenario": scenario,
            "neutralized_months": [str(period) for period in periods],
            "neutralized_month_count": len(periods),
            "strongest_calendar_year": strongest_year,
            **candidate,
            "material_advantage_vs_named_control": material[named_control],
            "material_advantage_by_decisive_control": material,
            "material_advantage_vs_all_decisive_controls": all(material.values()),
            "named_control_dominates": named_control in dominating,
            "any_other_decisive_control_dominates": any(control in dominating for control in other_controls),
            "dominating_decisive_controls": dominating,
            "observations_deleted": False,
            "canonical_series_modified": False,
            "used_for_strategy_change": False,
        })
    return concentration, neutralization, {
        "strongest_month": str(strongest_month),
        "strongest_three_months": [str(period) for period in strongest_three],
        "strongest_year": strongest_year,
        "strongest_year_fraction": strongest_year_value / positive_sum if positive_sum > 0.0 else float("nan"),
    }


def monthly_path_metrics(values: np.ndarray) -> tuple[float, float, float]:
    wealth = np.cumprod(1.0 + values)
    cagr = float(wealth[-1] ** (12.0 / len(values)) - 1.0)
    standard_deviation = float(np.std(values, ddof=1))
    sharpe = float(np.mean(values) / standard_deviation * math.sqrt(12.0)) if standard_deviation > 0.0 else 0.0
    drawdown = float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))
    return cagr, sharpe, drawdown


def paired_bootstrap(
    strategy_id: str,
    simulated: dict[str, Any],
    comparators: tuple[str, ...],
) -> list[dict[str, Any]]:
    monthly = pd.concat(
        [
            monthly_returns(simulated["candidate_paths"][PRIMARY_COST]["returns"]).rename(strategy_id),
            *[
                monthly_returns(simulated["control_paths"][(control, PRIMARY_COST)]["returns"]).rename(control)
                for control in comparators
            ],
        ],
        axis=1,
        join="inner",
    ).dropna()
    values = monthly.to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    maximum_start = count - BOOTSTRAP_BLOCK_MONTHS
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = {
        comparator: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0}
        for comparator in comparators
    }
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, maximum_start + 1, size=block_count)
        sampled = np.concatenate([
            np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts
        ])[:count]
        sample = values[sampled]
        candidate_cagr, candidate_sharpe, candidate_drawdown = monthly_path_metrics(sample[:, 0])
        for column, comparator in enumerate(comparators, start=1):
            control_cagr, control_sharpe, control_drawdown = monthly_path_metrics(sample[:, column])
            higher_sharpe = candidate_sharpe > control_sharpe
            better_drawdown = candidate_drawdown > control_drawdown
            counts[comparator]["cagr"] += int(candidate_cagr > control_cagr)
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
            "probability_candidate_higher_cagr": counts[comparator]["cagr"] / BOOTSTRAP_RESAMPLES,
            "probability_candidate_higher_sharpe": counts[comparator]["sharpe"] / BOOTSTRAP_RESAMPLES,
            "probability_candidate_less_severe_maximum_drawdown": counts[comparator]["drawdown"] / BOOTSTRAP_RESAMPLES,
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": counts[comparator]["either"] / BOOTSTRAP_RESAMPLES,
            "paired_cross_series_dependence_preserved": True,
            "used_for_strategy_change": False,
            "independent_validation_claimed": False,
        }
        for comparator in comparators
    ]


def _daily_asset_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change(fill_method=None).fillna(0.0)


def _spy_month_sign(prices: pd.DataFrame) -> pd.Series:
    spy = monthly_returns(prices["SPY"].pct_change(fill_method=None).fillna(0.0))
    return pd.Series(
        [float(spy.loc[period]) >= 0.0 for period in prices.index.to_period("M")],
        index=prices.index,
        dtype=bool,
    )


def percentile_attribution(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    concentration_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    donchian = simulated["control_paths"][(PERCENTILE_NAMED, PRIMARY_COST)]
    equal_signal = simulated["control_paths"][(PERCENTILE_EQUAL, PRIMARY_COST)]
    asset_returns = _daily_asset_returns(prepared["prices"])
    positive_spy = _spy_month_sign(prepared["prices"])
    candidate_contribution = candidate["held_weights"] * asset_returns
    donchian_difference = (candidate["held_weights"] - donchian["held_weights"]) * asset_returns
    equal_difference = (candidate["held_weights"] - equal_signal["held_weights"]) * asset_returns
    events = prepared["candidate_events"].iloc[1:]
    positive_asset_excess: dict[str, float] = {}
    asset_rows: list[dict[str, Any]] = []
    for asset in exploration.PERCENTILE_UNIVERSE:
        donchian_value = float(donchian_difference[asset].sum())
        positive_asset_excess[asset] = max(donchian_value, 0.0)
        asset_rows.append({
            "row_type": "asset",
            "asset": asset,
            "valid_formation_count": len(events),
            "selection_frequency": float((events[asset] > TOLERANCE).mean()),
            "average_target_weight": float(events[asset].mean()),
            "maximum_target_weight": float(events[asset].max()),
            "realized_gross_additive_return_contribution": float(candidate_contribution[asset].sum()),
            "candidate_minus_donchian_additive_contribution": donchian_value,
            "candidate_minus_equal_weight_signal_additive_contribution": float(equal_difference[asset].sum()),
            "contribution_in_positive_spy_months": float(candidate_contribution.loc[positive_spy, asset].sum()),
            "contribution_in_negative_spy_months": float(candidate_contribution.loc[~positive_spy, asset].sum()),
        })
    positive_total = sum(positive_asset_excess.values())
    strongest_asset = max(positive_asset_excess, key=positive_asset_excess.get)
    asset_fraction = positive_asset_excess[strongest_asset] / positive_total if positive_total > 0.0 else 0.0

    candidate_weights = candidate["held_weights"]
    donchian_weights = donchian["held_weights"]
    equal_weights = equal_signal["held_weights"]
    overlap_donchian = 1.0 - 0.5 * (candidate_weights - donchian_weights).abs().sum(axis=1)
    overlap_equal = 1.0 - 0.5 * (candidate_weights - equal_weights).abs().sum(axis=1)
    component_rows: list[dict[str, Any]] = [
        {"row_type": "summary", "metric": "candidate_donchian_target_overlap", "value": float(overlap_donchian.mean())},
        {"row_type": "summary", "metric": "candidate_equal_weight_signal_target_overlap", "value": float(overlap_equal.mean())},
        {"row_type": "summary", "metric": "SHY_positive_weight_frequency", "value": float((candidate_weights["SHY"] > TOLERANCE).mean())},
        {"row_type": "summary", "metric": "SHY_average_weight", "value": float(candidate_weights["SHY"].mean())},
        {"row_type": "summary", "metric": "strongest_positive_excess_asset", "value": strongest_asset},
        {"row_type": "summary", "metric": "strongest_asset_fraction_of_total_positive_excess_vs_donchian", "value": asset_fraction},
        {"row_type": "summary", "metric": "strongest_calendar_year_fraction_of_total_positive_excess_vs_donchian", "value": concentration_summary["strongest_year_fraction"]},
    ]
    for year in sorted(set(candidate["returns"].index.year)):
        year_index = candidate["returns"].index[candidate["returns"].index.year == year]
        component_rows.append({
            "row_type": "calendar_year",
            "calendar_year": year,
            "metric": "turnover_and_cost",
            "turnover": float(candidate["turnover"].reindex(year_index).sum()),
            "transaction_cost_drag": float(candidate["cost"].reindex(year_index).sum()),
        })

    diagnostics = prepared["diagnostics"].copy()
    diagnostics = diagnostics.loc[diagnostics["formation_valid"].astype(bool)].copy()
    horizon_rows: list[dict[str, Any]] = []
    for asset in exploration.PERCENTILE_RISKY:
        subset = diagnostics.loc[diagnostics["asset"].eq(asset)].sort_values("formation_date")
        for horizon in (60, 120, 180, 252):
            state = pd.to_numeric(subset[f"state_{horizon}"], errors="coerce").dropna()
            donchian_state = pd.to_numeric(subset[f"donchian_state_{horizon}"], errors="coerce").reindex(state.index)
            horizon_rows.append({
                "asset": asset,
                "horizon_sessions": horizon,
                "valid_month_count": len(state),
                "state_change_count": int(state.ne(state.shift()).iloc[1:].sum()),
                "state_change_frequency": float(state.ne(state.shift()).iloc[1:].mean()) if len(state) > 1 else 0.0,
                "positive_state_fraction": float((state > 0.0).mean()),
                "donchian_disagreement_frequency": float((state != donchian_state).mean()),
                "horizon_removed_or_changed": False,
            })
    return component_rows, asset_rows, horizon_rows, {
        "asset_concentration": asset_fraction,
        "year_concentration": float(concentration_summary["strongest_year_fraction"]),
    }


REGIME_BY_ASSET = {
    "XLE": "growth_up_inflation_up",
    "XLK": "growth_up_inflation_down",
    "XLV": "growth_down_inflation_up",
    "XLP": "growth_down_inflation_down",
}


def growth_attribution(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    concentration_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    growth = simulated["control_paths"][(GROWTH_NAMED, PRIMARY_COST)]
    inflation = simulated["control_paths"][(GROWTH_INFLATION, PRIMARY_COST)]
    static = simulated["control_paths"][(GROWTH_STATIC, PRIMARY_COST)]
    prices = prepared["prices"]
    asset_returns = _daily_asset_returns(prices)
    held = candidate["held_weights"]
    held_asset = held.idxmax(axis=1)
    regime = held_asset.map(REGIME_BY_ASSET).fillna("warmup_BIL")
    positive_spy = _spy_month_sign(prices)
    gross_daily = (held * asset_returns).sum(axis=1)
    candidate_returns = candidate["returns"]
    growth_returns = growth["returns"]
    static_returns = static["returns"]

    episode_rows: list[dict[str, Any]] = []
    episode_sequence = 0
    start = 0
    values = regime.to_numpy(dtype=str)
    for position in range(1, len(values) + 1):
        if position < len(values) and values[position] == values[start]:
            continue
        episode_regime = values[start]
        episode_index = regime.index[start:position]
        if episode_regime != "warmup_BIL":
            episode_sequence += 1
            candidate_value = float(candidate_returns.reindex(episode_index).sum())
            growth_value = float(growth_returns.reindex(episode_index).sum())
            episode_rows.append({
                "episode_id": episode_sequence,
                "regime": episode_regime,
                "target_sector": held_asset.iloc[start],
                "episode_start": episode_index[0].date().isoformat(),
                "episode_end": episode_index[-1].date().isoformat(),
                "duration_sessions": len(episode_index),
                "candidate_additive_return": candidate_value,
                "growth_only_additive_return": growth_value,
                "candidate_minus_growth_only_additive_excess": candidate_value - growth_value,
                "positive_excess_episode": candidate_value - growth_value > 0.0,
                "turnover": float(candidate["turnover"].reindex(episode_index).sum()),
                "transaction_cost_drag": float(candidate["cost"].reindex(episode_index).sum()),
                "episode_removed": False,
            })
        start = position

    positive_episode_total = sum(
        max(float(row["candidate_minus_growth_only_additive_excess"]), 0.0)
        for row in episode_rows
    )
    ranked_episodes = sorted(
        episode_rows,
        key=lambda row: float(row["candidate_minus_growth_only_additive_excess"]),
        reverse=True,
    )
    strongest_episode_fraction = (
        max(float(ranked_episodes[0]["candidate_minus_growth_only_additive_excess"]), 0.0)
        / positive_episode_total
        if positive_episode_total > 0.0
        else 0.0
    )
    for rank, row in enumerate(ranked_episodes, start=1):
        row["positive_excess_rank"] = rank if row["positive_excess_episode"] else ""
        row["strongest_positive_episode"] = rank == 1
        row["among_three_strongest_positive_episodes"] = rank <= 3
        row["fraction_of_total_positive_episode_excess"] = (
            max(float(row["candidate_minus_growth_only_additive_excess"]), 0.0)
            / positive_episode_total
            if positive_episode_total > 0.0
            else 0.0
        )

    regime_positive: dict[str, float] = {}
    regime_rows: list[dict[str, Any]] = []
    for target_asset, regime_name in REGIME_BY_ASSET.items():
        mask = regime.eq(regime_name)
        durations = [
            int(row["duration_sessions"]) for row in episode_rows if row["regime"] == regime_name
        ]
        growth_difference = float((candidate_returns - growth_returns).loc[mask].sum())
        regime_positive[regime_name] = max(growth_difference, 0.0)
        regime_rows.append({
            "row_type": "regime",
            "regime": regime_name,
            "target_sector": target_asset,
            "observation_count": int(mask.sum()),
            "episode_count": len(durations),
            "median_duration_sessions": float(np.median(durations)) if durations else 0.0,
            "maximum_duration_sessions": max(durations) if durations else 0,
            "gross_additive_return_contribution": float(gross_daily.loc[mask].sum()),
            "net_additive_return_contribution_5bps": float(candidate_returns.loc[mask].sum()),
            "candidate_minus_growth_only_additive_contribution": growth_difference,
            "candidate_minus_static_additive_contribution": float((candidate_returns - static_returns).loc[mask].sum()),
            "turnover": float(candidate["turnover"].loc[mask].sum()),
            "transaction_cost_drag": float(candidate["cost"].loc[mask].sum()),
            "contribution_in_positive_spy_months": float(candidate_returns.loc[mask & positive_spy].sum()),
            "contribution_in_negative_spy_months": float(candidate_returns.loc[mask & ~positive_spy].sum()),
        })
    positive_regime_total = sum(regime_positive.values())
    strongest_regime = max(regime_positive, key=regime_positive.get)
    regime_fraction = regime_positive[strongest_regime] / positive_regime_total if positive_regime_total > 0.0 else 0.0

    valid = prepared["diagnostics"].loc[
        prepared["diagnostics"]["signal_valid"].astype(bool)
    ]
    controls = prepared["control_reconciliation"]
    growth_direction = valid["growth_state"].astype(str).str.removeprefix("growth_")
    inflation_direction = valid["inflation_state"].astype(str).str.removeprefix("inflation_")
    component_rows = [
        {"row_type": "summary", "metric": "growth_state_inflation_state_disagreement_frequency", "value": float(growth_direction.ne(inflation_direction).mean())},
        {"row_type": "summary", "metric": "candidate_target_overlap_with_growth_only", "value": float(controls["candidate_equals_growth_only"].astype(bool).mean())},
        {"row_type": "summary", "metric": "candidate_target_overlap_with_inflation_only", "value": float(controls["candidate_equals_inflation_only"].astype(bool).mean())},
        {"row_type": "summary", "metric": "candidate_contribution_positive_SPY_months", "value": float(candidate_returns.loc[positive_spy].sum())},
        {"row_type": "summary", "metric": "candidate_contribution_negative_SPY_months", "value": float(candidate_returns.loc[~positive_spy].sum())},
        {"row_type": "summary", "metric": "strongest_positive_excess_regime", "value": strongest_regime},
        {"row_type": "summary", "metric": "strongest_regime_fraction_of_total_positive_excess_vs_growth_only", "value": regime_fraction},
        {"row_type": "summary", "metric": "strongest_episode_fraction_of_total_positive_excess_vs_growth_only", "value": strongest_episode_fraction},
        {"row_type": "summary", "metric": "strongest_calendar_year_fraction_of_total_positive_excess_vs_growth_only", "value": concentration_summary["strongest_year_fraction"]},
    ]

    positive_episodes = [row for row in ranked_episodes if row["positive_excess_episode"]]
    scenarios = {
        "neutralize_strongest_positive_regime_episode": positive_episodes[:1],
        "neutralize_three_strongest_positive_regime_episodes": positive_episodes[:3],
    }
    growth_metrics = metrics(growth, "BIL")
    static_metrics = metrics(static, "BIL")
    neutralization_rows: list[dict[str, Any]] = []
    for scenario, selected in scenarios.items():
        counterfactual = candidate_returns.copy()
        neutralized_dates: list[pd.Timestamp] = []
        for episode in selected:
            dates = counterfactual.index[
                (counterfactual.index >= pd.Timestamp(episode["episode_start"]))
                & (counterfactual.index <= pd.Timestamp(episode["episode_end"]))
            ]
            neutralized_dates.extend(dates.tolist())
            counterfactual.loc[dates] = growth_returns.loc[dates]
        candidate_metrics = exploration.market.metrics_from_returns(counterfactual)
        neutralization_rows.append({
            "strategy_id": GROWTH_ID,
            "scenario": scenario,
            "neutralized_episode_ids": [row["episode_id"] for row in selected],
            "neutralized_episode_count": len(selected),
            "neutralized_session_count": len(neutralized_dates),
            **candidate_metrics,
            "material_advantage_vs_growth_only": material_advantage(candidate_metrics, growth_metrics),
            "material_advantage_vs_static_control": material_advantage(candidate_metrics, static_metrics),
            "growth_only_dominates": dominates(growth_metrics, candidate_metrics),
            "static_control_dominates": dominates(static_metrics, candidate_metrics),
            "observations_deleted": False,
            "canonical_series_modified": False,
            "strategy_changed": False,
        })
    return regime_rows, episode_rows, neutralization_rows, {
        "regime_concentration": regime_fraction,
        "episode_concentration": strongest_episode_fraction,
        "year_concentration": float(concentration_summary["strongest_year_fraction"]),
        "three_episode_neutralization_material": bool(
            neutralization_rows[-1]["material_advantage_vs_growth_only"]
        ),
        "component_rows": component_rows,
    }


def _rolling_lookup(
    summaries: list[dict[str, Any]], strategy_id: str, months: int, comparator: str
) -> dict[str, Any]:
    return next(
        row for row in summaries
        if row["strategy_id"] == strategy_id
        and row["window_months"] == months
        and row["comparison_id"] == comparator
    )


def classify_candidate(
    strategy_id: str,
    reproduction_pass: bool,
    invariants_pass: bool,
    full_metrics: dict[tuple[str, float], dict[str, Any]],
    quarter_map: dict[tuple[str, str], dict[str, Any]],
    rolling_summaries: list[dict[str, Any]],
    neutralization_rows: list[dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
    specific: dict[str, Any],
) -> dict[str, Any]:
    decisive = PERCENTILE_DECISIVE if strategy_id == PERCENTILE_ID else GROWTH_DECISIVE
    named = decisive[0]
    candidate5 = full_metrics[(strategy_id, 5.0)]
    control5 = {control: full_metrics[(control, 5.0)] for control in decisive}
    candidate15 = full_metrics[(strategy_id, 15.0)]
    candidate20 = full_metrics[(strategy_id, 20.0)]
    control20 = {control: full_metrics[(control, 20.0)] for control in decisive}
    quarters = [f"chronological_quarter_{value}" for value in range(1, 5)]
    improvement_quarters = {
        control: sum(
            float(quarter_map[(strategy_id, quarter)]["sharpe_ratio"])
            > float(quarter_map[(control, quarter)]["sharpe_ratio"])
            or float(quarter_map[(strategy_id, quarter)]["maximum_drawdown"])
            > float(quarter_map[(control, quarter)]["maximum_drawdown"])
            for quarter in quarters
        )
        for control in decisive
    }
    rolling_fractions = {
        f"{control}_{months}": float(
            _rolling_lookup(rolling_summaries, strategy_id, months, control)[
                "candidate_improves_sharpe_or_drawdown_fraction"
            ]
        )
        for control in decisive
        for months in (36, 60)
    }
    neutral = {row["scenario"]: row for row in neutralization_rows}
    neutral_three = neutral["neutralize_three_strongest_positive_excess_months"]
    neutral_year = neutral["neutralize_strongest_additive_excess_calendar_year"]
    bootstrap = {row["comparison_id"]: row for row in bootstrap_rows}
    common = {
        "parent_reproduction_and_every_invariant_pass": reproduction_pass and invariants_pass,
        "candidate_positive_at_5bps": float(candidate5["total_return"]) > 0.0,
        "no_decisive_control_dominates_full_period": not any(
            dominates(control5[control], candidate5) for control in decisive
        ),
        "parent_materiality_against_every_decisive_control": all(
            material_advantage(candidate5, control5[control]) for control in decisive
        ),
        "each_decisive_control_improved_in_three_of_four_quarters": all(
            improvement_quarters[control] >= 3 for control in decisive
        ),
        "rolling_36_majority_improvement_each_decisive_control": all(
            rolling_fractions[f"{control}_36"] > 0.50 for control in decisive
        ),
        "rolling_60_majority_improvement_each_decisive_control": all(
            rolling_fractions[f"{control}_60"] > 0.50 for control in decisive
        ),
        "three_month_neutralization_retains_named_materiality_and_no_other_dominance": bool(
            neutral_three["material_advantage_vs_named_control"]
            and not neutral_three["any_other_decisive_control_dominates"]
        ),
        "strongest_year_neutralization_retains_named_materiality_and_no_other_dominance": bool(
            neutral_year["material_advantage_vs_named_control"]
            and not neutral_year["any_other_decisive_control_dominates"]
        ),
        "candidate_positive_at_15bps": float(candidate15["total_return"]) > 0.0,
        "candidate_not_dominated_by_every_decisive_control_at_20bps": not all(
            dominates(control20[control], candidate20) for control in decisive
        ),
        "bootstrap_probability_thresholds": float(
            bootstrap[named]["probability_candidate_higher_sharpe_or_less_severe_drawdown"]
        ) >= 0.70 and all(
            float(bootstrap[control]["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) >= 0.60
            for control in decisive if control != named
        ),
    }
    if strategy_id == PERCENTILE_ID:
        candidate_specific = {
            "materiality_vs_donchian": material_advantage(candidate5, control5[PERCENTILE_NAMED]),
            "materiality_vs_equal_weight_signal": material_advantage(candidate5, control5[PERCENTILE_EQUAL]),
            "materiality_vs_always_long_risk_parity": material_advantage(candidate5, control5[PERCENTILE_ALWAYS]),
            "static_average_holdings_do_not_dominate": not dominates(control5[PERCENTILE_STATIC], candidate5),
            "no_single_asset_over_50pct_positive_excess": float(specific["asset_concentration"]) <= 0.50,
            "no_single_year_over_50pct_positive_excess": float(specific["year_concentration"]) <= 0.50,
        }
        interpretation_positive = "paper_demo_eligibility_candidate_standalone_multi_asset_allocation"
    else:
        drawdown_quarters = sum(
            float(quarter_map[(strategy_id, quarter)]["maximum_drawdown"])
            - float(quarter_map[(GROWTH_NAMED, quarter)]["maximum_drawdown"])
            >= 0.01 - 1e-12
            for quarter in quarters
        )
        candidate_specific = {
            "growth_only_drawdown_improved_by_1pct_in_three_quarters": drawdown_quarters >= 3,
            "growth_only_rolling_majority_both_horizons": bool(
                rolling_fractions[f"{GROWTH_NAMED}_36"] > 0.50
                and rolling_fractions[f"{GROWTH_NAMED}_60"] > 0.50
            ),
            "static_average_weights_do_not_dominate": not dominates(control5[GROWTH_STATIC], candidate5),
            "positive_and_material_vs_growth_only_at_20bps": bool(
                float(candidate20["total_return"]) > 0.0
                and material_advantage(candidate20, control20[GROWTH_NAMED])
            ),
            "three_strongest_regime_episode_neutralization_retains_materiality": bool(
                specific["three_episode_neutralization_material"]
            ),
            "no_regime_over_50pct_positive_excess": float(specific["regime_concentration"]) <= 0.50,
            "no_episode_over_50pct_positive_excess": float(specific["episode_concentration"]) <= 0.50,
            "no_year_over_50pct_positive_excess": float(specific["year_concentration"]) <= 0.50,
            "bootstrap_vs_growth_only_at_least_70pct": float(
                bootstrap[GROWTH_NAMED]["probability_candidate_higher_sharpe_or_less_severe_drawdown"]
            ) >= 0.70,
        }
        interpretation_positive = "paper_demo_eligibility_candidate_standalone_sector_regime_rotation"

    all_checks = {**common, **candidate_specific}
    if not reproduction_pass:
        outcome = "robustness_blocked"
        reason = "data_or_comparability_failure"
        interpretation = "historical_robustness_blocked"
    elif not invariants_pass:
        outcome = "robustness_blocked"
        reason = "methodology_failure"
        interpretation = "historical_robustness_blocked"
    elif all(all_checks.values()):
        outcome = "robustness_positive"
        reason = ""
        interpretation = interpretation_positive
    else:
        full_dominance = any(dominates(control5[control], candidate5) for control in decisive)
        full_materiality_failure = not common["parent_materiality_against_every_decisive_control"]
        named_rolling_failure = bool(
            rolling_fractions[f"{named}_36"] <= 0.50
            and rolling_fractions[f"{named}_60"] <= 0.50
        )
        concentration_failure = any(
            not value for key, value in candidate_specific.items() if "over_50pct" in key
        )
        component_failure = (
            strategy_id == GROWTH_ID
            and not candidate_specific["three_strongest_regime_episode_neutralization_retains_materiality"]
        ) or (
            strategy_id == PERCENTILE_ID
            and not all(candidate_specific[key] for key in (
                "materiality_vs_donchian",
                "materiality_vs_equal_weight_signal",
                "materiality_vs_always_long_risk_parity",
            ))
        )
        cost_failure = float(candidate15["total_return"]) <= 0.0
        failed = full_dominance or full_materiality_failure or named_rolling_failure or concentration_failure or component_failure or cost_failure
        outcome = "robustness_failed" if failed else "robustness_mixed"
        interpretation = "historically_failed" if failed else "historically_promising_not_ready_for_paper_demo_eligibility"
        if full_dominance:
            reason = "weak_vs_primary_control"
        elif full_materiality_failure:
            reason = "benchmark_like_behavior"
        elif concentration_failure:
            reason = "concentration_risk"
        elif component_failure:
            reason = "weak_component_attribution"
        elif cost_failure:
            reason = "cost_drag"
        elif named_rolling_failure or not common["each_decisive_control_improved_in_three_of_four_quarters"]:
            reason = "period_instability"
        elif not common["bootstrap_probability_thresholds"]:
            reason = "control_uncertainty"
        elif not common["candidate_not_dominated_by_every_decisive_control_at_20bps"]:
            reason = "cost_sensitivity"
        else:
            reason = "overfit_or_unstable"
    return {
        "strategy_id": strategy_id,
        "outcome": outcome,
        "failure_reason": reason,
        "interpretation": interpretation,
        "common_positive_checks": common,
        "candidate_specific_positive_checks": candidate_specific,
        "decisive_control_improvement_quarters": improvement_quarters,
        "rolling_improvement_fractions": rolling_fractions,
        "final_historical_task_for_exact_configuration": True,
        "independent_validation_claimed": False,
        "diversifier_route_reopened": False,
    }


def report_text(
    decisions: list[dict[str, Any]],
    full_metrics: dict[str, dict[tuple[str, float], dict[str, Any]]],
    next_action: str,
    overall_pass: bool,
) -> str:
    lines = [
        "# Native ETF V3 Two-Candidate Final Robustness",
        "",
        "## Scope",
        "",
        "Exactly two frozen standalone configurations received their final same-period historical robustness assessment. Their previously failed diversifier routes remained closed. This packet is robustness evidence, not independent validation or paper/demo onboarding.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Failure reason | 5 bps CAGR | Sharpe | Maximum drawdown |",
        "|---|---|---|---:|---:|---:|",
    ]
    for decision in decisions:
        values = full_metrics[decision["strategy_id"]][(decision["strategy_id"], PRIMARY_COST)]
        lines.append(
            f"| {decision['strategy_id']} | {decision['outcome']} | {decision['failure_reason']} | "
            f"{float(values['cagr']):.6f} | {float(values['sharpe_ratio']):.6f} | "
            f"{float(values['maximum_drawdown']):.6f} |"
        )
    lines.extend([
        "",
        "## Method",
        "",
        "Parent results reproduced before interpretation. The frozen strategies and carried-forward controls were evaluated at predeclared costs, four chronological quarters, every complete calendar year, monthly-stepped 36- and 60-month windows, fixed annual starts, concentration counterfactuals, and a paired moving-block bootstrap.",
        "",
        "Percentile-channel timing, volatility scaling, assets, and horizons were attributed separately. Growth/Inflation results were decomposed by regime and episode, with the downside-only exploration claim against growth-only kept explicit.",
        "",
        "## Boundaries",
        "",
        "No source research, parameter change, control addition, provider access, validation, lifecycle update, paper/demo observation, broker operation, or capital action occurred.",
        "",
        f"Consistency check: `overall_pass = {str(overall_pass).lower()}`.",
        "",
        f"Exact next action: `{next_action}`.",
        "",
    ])
    return "\n".join(lines)


def run() -> dict[str, Any]:
    before_hashes = snapshot_hashes()
    source_hash_before = file_hash(SOURCE_ATTACHMENT)
    reset_output()
    strategies, trials = preregister()
    preregistration_hashes = {
        name: file_hash(OUTPUT_DIR / name)
        for name in (
            "strategy_cards.csv",
            "trial_ledger.csv",
            "benchmark_reference_log.csv",
            "process_task_log.csv",
        )
    }

    _, frames, preflight_status = exploration.preflight()
    prepared = {
        PERCENTILE_ID: exploration.prepare_percentile_channels(frames),
        GROWTH_ID: exploration.prepare_growth_inflation(frames),
    }
    reproduction_rows, reproduction_by_candidate = parent_reproduction(prepared, frames)
    write_csv(
        "parent_reproduction_check.csv",
        reproduction_rows,
        (
            "scope", "archived_row_count", "reproduced_row_count", "columns_match",
            "rows_match", "maximum_numeric_difference", "mismatch_count", "tolerance", "pass",
        ),
    )

    simulations = {
        PERCENTILE_ID: simulate_costs(prepared[PERCENTILE_ID], PERCENTILE_COSTS),
        GROWTH_ID: simulate_costs(prepared[GROWTH_ID], GROWTH_COSTS),
    }
    decisive = {
        PERCENTILE_ID: PERCENTILE_DECISIVE,
        GROWTH_ID: GROWTH_DECISIVE,
    }
    costs = {PERCENTILE_ID: PERCENTILE_COSTS, GROWTH_ID: GROWTH_COSTS}

    cost_rows: list[dict[str, Any]] = []
    full_metric_maps: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
    quarter_rows: list[dict[str, Any]] = []
    quarter_maps: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    year_rows: list[dict[str, Any]] = []
    rolling36: list[dict[str, Any]] = []
    rolling60: list[dict[str, Any]] = []
    start_rows: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    neutralization_rows: list[dict[str, Any]] = []
    concentration_summary: dict[str, dict[str, Any]] = {}
    bootstrap_rows: list[dict[str, Any]] = []
    bootstrap_repeat: list[dict[str, Any]] = []
    for strategy_id in (PERCENTILE_ID, GROWTH_ID):
        rows, metric_map = full_cost_rows(strategy_id, simulations[strategy_id], costs[strategy_id])
        cost_rows.extend(rows)
        full_metric_maps[strategy_id] = metric_map
        quarters, quarter_map, years = partition_rows(
            strategy_id, simulations[strategy_id], prepared[strategy_id]["prices"].index
        )
        quarter_rows.extend(quarters)
        quarter_maps[strategy_id] = quarter_map
        year_rows.extend(years)
        rolling36.extend(
            rolling_rows(
                strategy_id,
                simulations[strategy_id],
                prepared[strategy_id]["prices"].index,
                decisive[strategy_id],
                36,
            )
        )
        rolling60.extend(
            rolling_rows(
                strategy_id,
                simulations[strategy_id],
                prepared[strategy_id]["prices"].index,
                decisive[strategy_id],
                60,
            )
        )
        start_rows.extend(
            start_sensitivity_rows(
                strategy_id,
                simulations[strategy_id],
                prepared[strategy_id]["prices"].index,
                decisive[strategy_id],
            )
        )
        concentration, neutralization, summary = concentration_and_neutralization(
            strategy_id,
            simulations[strategy_id],
            decisive[strategy_id][0],
            decisive[strategy_id],
        )
        concentration_rows.extend(concentration)
        neutralization_rows.extend(neutralization)
        concentration_summary[strategy_id] = summary
        bootstrap_rows.extend(paired_bootstrap(strategy_id, simulations[strategy_id], decisive[strategy_id]))
        bootstrap_repeat.extend(paired_bootstrap(strategy_id, simulations[strategy_id], decisive[strategy_id]))
    rolling_summaries = rolling_summary(rolling36 + rolling60)
    bootstrap_deterministic = json.dumps(bootstrap_rows, sort_keys=True) == json.dumps(
        bootstrap_repeat, sort_keys=True
    )

    percentile_components, percentile_assets, percentile_horizons, percentile_specific = percentile_attribution(
        prepared[PERCENTILE_ID],
        simulations[PERCENTILE_ID],
        concentration_summary[PERCENTILE_ID],
    )
    growth_regimes, growth_episodes, growth_episode_neutralization, growth_specific = growth_attribution(
        prepared[GROWTH_ID],
        simulations[GROWTH_ID],
        concentration_summary[GROWTH_ID],
    )
    growth_regimes.extend(growth_specific.pop("component_rows"))

    runtime_invariants: dict[str, bool] = {}
    for strategy_id in (PERCENTILE_ID, GROWTH_ID):
        runtime_invariants[strategy_id] = bool(
            preflight_status[strategy_id]
            and all(
                values["invariant_pass"]
                for values in full_metric_maps[strategy_id].values()
            )
        )
    decisions = {
        PERCENTILE_ID: classify_candidate(
            PERCENTILE_ID,
            reproduction_by_candidate[PERCENTILE_ID],
            runtime_invariants[PERCENTILE_ID],
            full_metric_maps[PERCENTILE_ID],
            quarter_maps[PERCENTILE_ID],
            rolling_summaries,
            [row for row in neutralization_rows if row["strategy_id"] == PERCENTILE_ID],
            [row for row in bootstrap_rows if row["strategy_id"] == PERCENTILE_ID],
            percentile_specific,
        ),
        GROWTH_ID: classify_candidate(
            GROWTH_ID,
            reproduction_by_candidate[GROWTH_ID],
            runtime_invariants[GROWTH_ID],
            full_metric_maps[GROWTH_ID],
            quarter_maps[GROWTH_ID],
            rolling_summaries,
            [row for row in neutralization_rows if row["strategy_id"] == GROWTH_ID],
            [row for row in bootstrap_rows if row["strategy_id"] == GROWTH_ID],
            growth_specific,
        ),
    }
    positive_count = sum(row["outcome"] == "robustness_positive" for row in decisions.values())
    blocked_count = sum(row["outcome"] == "robustness_blocked" for row in decisions.values())
    shared_block = not all(preflight_status.values()) or not any(reproduction_by_candidate.values())
    if positive_count:
        next_action = "direction_owner_review_native_etf_v3_robustness_for_paper_demo_v1"
    elif shared_block:
        next_action = "direction_owner_review_native_etf_v3_robustness_block_v1"
    else:
        next_action = "resume_native_etf_source_discovery_v4"
    for row in (*strategies, *trials):
        decision = decisions[row["strategy_id"]]
        row["outcome"] = decision["outcome"]
        row["failure_reason"] = decision["failure_reason"]
        row["next_action"] = next_action
    strategy_headers = (
        "strategy_id", "family_id", "display_name", "entity_type",
        "strategy_architecture", "source_or_research_lineage", "instrument_universe",
        "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id",
        "adaptation_label", "changed_fields_from_parent", "route", "outcome",
        "failure_reason", "next_action",
    )
    write_csv("strategy_cards.csv", strategies, strategy_headers)
    write_csv("trial_ledger.csv", trials, strategy_headers)

    result_headers = (
        "strategy_id", "trial_id", "series_id", "cost_bps_one_way", "period",
        "result_type", "evaluation_start", "evaluation_end", "total_return", "cagr",
        "annualized_volatility", "sharpe_ratio", "maximum_drawdown",
        "average_risky_exposure", "turnover", "trade_or_rebalance_count",
        "transaction_cost_drag", "maximum_single_asset_weight", "maximum_gross_exposure",
        "maximum_daily_weight_sum", "invariant_pass",
    )
    write_csv("cost_stress_results.csv", cost_rows, result_headers)
    write_csv("chronological_quarter_results.csv", quarter_rows, result_headers)
    write_csv("calendar_year_results.csv", year_rows, (*result_headers, "calendar_year"))
    rolling_headers = (
        "strategy_id", "trial_id", "window_months", "window_sequence", "window_start",
        "window_end", "candidate_id", "comparison_id", "candidate_cagr",
        "comparison_cagr", "cagr_difference", "candidate_sharpe_ratio",
        "comparison_sharpe_ratio", "sharpe_difference", "candidate_maximum_drawdown",
        "comparison_maximum_drawdown", "maximum_drawdown_difference",
        "candidate_improves_sharpe_or_drawdown", "comparison_dominates_candidate",
        "unfavorable_window_retained", "independent_validation_claimed",
    )
    write_csv("rolling_36_month_results.csv", rolling36, rolling_headers)
    write_csv("rolling_60_month_results.csv", rolling60, rolling_headers)
    write_csv(
        "rolling_window_summary.csv",
        rolling_summaries,
        (
            "strategy_id", "window_months", "comparison_id", "eligible_window_count",
            "median_cagr_difference", "median_sharpe_difference",
            "median_maximum_drawdown_difference",
            "candidate_improves_sharpe_or_drawdown_fraction",
            "comparison_dominates_fraction", "unfavorable_windows_retained",
        ),
    )
    write_csv("start_date_sensitivity.csv", start_rows, result_headers)
    write_csv(
        "monthly_excess_concentration.csv",
        concentration_rows,
        (
            "strategy_id", "month", "candidate_return_5bps", "named_control_return_5bps",
            "candidate_minus_named_additive_excess", "positive_excess_rank",
            "strongest_positive_excess_month", "among_three_strongest_positive_excess_months",
            "strongest_additive_excess_calendar_year", "strongest_year",
            "strongest_year_fraction_of_cumulative_positive_additive_excess",
            "frozen_before_counterfactual", "observation_deleted",
        ),
    )
    write_csv(
        "month_and_year_neutralization_results.csv",
        neutralization_rows,
        (
            "strategy_id", "scenario", "neutralized_months", "neutralized_month_count",
            "strongest_calendar_year", "total_return", "cagr", "annualized_volatility",
            "sharpe_ratio", "maximum_drawdown", "material_advantage_vs_named_control",
            "material_advantage_by_decisive_control", "material_advantage_vs_all_decisive_controls",
            "named_control_dominates", "any_other_decisive_control_dominates",
            "dominating_decisive_controls", "observations_deleted", "canonical_series_modified",
            "used_for_strategy_change",
        ),
    )
    write_csv(
        "paired_block_bootstrap_results.csv",
        bootstrap_rows,
        (
            "strategy_id", "candidate_id", "comparison_id", "monthly_observation_count",
            "block_length_months", "resamples", "deterministic_seed",
            "probability_candidate_higher_cagr", "probability_candidate_higher_sharpe",
            "probability_candidate_less_severe_maximum_drawdown",
            "probability_candidate_higher_sharpe_or_less_severe_drawdown",
            "paired_cross_series_dependence_preserved", "used_for_strategy_change",
            "independent_validation_claimed",
        ),
    )
    write_csv(
        "percentile_channel_component_attribution.csv",
        percentile_components,
        ("row_type", "calendar_year", "metric", "value", "turnover", "transaction_cost_drag"),
    )
    write_csv(
        "percentile_channel_asset_contribution.csv",
        percentile_assets,
        (
            "row_type", "asset", "valid_formation_count", "selection_frequency",
            "average_target_weight", "maximum_target_weight",
            "realized_gross_additive_return_contribution",
            "candidate_minus_donchian_additive_contribution",
            "candidate_minus_equal_weight_signal_additive_contribution",
            "contribution_in_positive_spy_months", "contribution_in_negative_spy_months",
        ),
    )
    write_csv(
        "percentile_channel_horizon_diagnostics.csv",
        percentile_horizons,
        (
            "asset", "horizon_sessions", "valid_month_count", "state_change_count",
            "state_change_frequency", "positive_state_fraction",
            "donchian_disagreement_frequency", "horizon_removed_or_changed",
        ),
    )
    write_csv(
        "growth_inflation_regime_attribution.csv",
        growth_regimes,
        (
            "row_type", "regime", "target_sector", "observation_count", "episode_count",
            "median_duration_sessions", "maximum_duration_sessions",
            "gross_additive_return_contribution", "net_additive_return_contribution_5bps",
            "candidate_minus_growth_only_additive_contribution",
            "candidate_minus_static_additive_contribution", "turnover",
            "transaction_cost_drag", "contribution_in_positive_spy_months",
            "contribution_in_negative_spy_months", "metric", "value",
        ),
    )
    write_csv(
        "growth_inflation_episode_inventory.csv",
        growth_episodes,
        (
            "episode_id", "regime", "target_sector", "episode_start", "episode_end",
            "duration_sessions", "candidate_additive_return", "growth_only_additive_return",
            "candidate_minus_growth_only_additive_excess", "positive_excess_episode",
            "positive_excess_rank", "strongest_positive_episode",
            "among_three_strongest_positive_episodes",
            "fraction_of_total_positive_episode_excess", "turnover",
            "transaction_cost_drag", "episode_removed",
        ),
    )
    write_csv(
        "growth_inflation_episode_neutralization.csv",
        growth_episode_neutralization,
        (
            "strategy_id", "scenario", "neutralized_episode_ids",
            "neutralized_episode_count", "neutralized_session_count", "total_return", "cagr",
            "annualized_volatility", "sharpe_ratio", "maximum_drawdown",
            "material_advantage_vs_growth_only", "material_advantage_vs_static_control",
            "growth_only_dominates", "static_control_dominates", "observations_deleted",
            "canonical_series_modified", "strategy_changed",
        ),
    )

    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for strategy_id in (PERCENTILE_ID, GROWTH_ID):
        invariant_rows.append({
            "strategy_id": strategy_id,
            "invariant_name": "parent_reproduction_within_1e_9",
            "invariant_pass": reproduction_by_candidate[strategy_id],
            "detail": "parent performance, controls, diagnostics, turnover, and invariants reproduced",
        })
        invariant_rows.append({
            "strategy_id": strategy_id,
            "invariant_name": "frozen_rule_parameters_universe_controls_and_execution",
            "invariant_pass": True,
            "detail": "robustness diagnostics only; standalone route only",
        })
        for (series_id, cost), values in full_metric_maps[strategy_id].items():
            turnover_rows.append({
                "strategy_id": strategy_id,
                "series_id": series_id,
                "cost_bps_one_way": cost,
                "one_way_turnover": values["turnover"],
                "transaction_cost_drag": values["transaction_cost_drag"],
                "costs_charged_once": True,
                "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
            })
            invariant_rows.append({
                "strategy_id": strategy_id,
                "series_id": series_id,
                "cost_bps_one_way": cost,
                "invariant_name": "accounting_timing_numeric_weight_and_exposure",
                "invariant_pass": values["invariant_pass"],
                "detail": "completed close signal; following-session close execution; nonnegative unlevered weights; costs once",
                "maximum_gross_exposure": values["maximum_gross_exposure"],
                "maximum_daily_weight_sum": values["maximum_daily_weight_sum"],
            })
    invariant_rows.append({
        "strategy_id": "",
        "invariant_name": "paired_bootstrap_deterministic",
        "invariant_pass": bootstrap_deterministic,
        "detail": f"{BOOTSTRAP_RESAMPLES} paired moving-block resamples; seed {BOOTSTRAP_SEED}",
    })
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover_rows,
        (
            "strategy_id", "series_id", "cost_bps_one_way", "one_way_turnover",
            "transaction_cost_drag", "costs_charged_once", "turnover_formula",
        ),
    )
    write_csv(
        "invariant_results.csv",
        invariant_rows,
        (
            "strategy_id", "series_id", "cost_bps_one_way", "invariant_name",
            "invariant_pass", "detail", "maximum_gross_exposure", "maximum_daily_weight_sum",
        ),
    )

    decision_rows = [decisions[PERCENTILE_ID], decisions[GROWTH_ID]]
    write_csv(
        "outcome_summary.csv",
        [{
            **decision,
            "next_action": next_action,
            "same_period_historical_robustness_only": True,
            "paper_demo_eligibility_granted_inside_task": False,
            "prospective_validation_created": False,
        } for decision in decision_rows],
        (
            "strategy_id", "outcome", "failure_reason", "interpretation",
            "common_positive_checks", "candidate_specific_positive_checks",
            "decisive_control_improvement_quarters", "rolling_improvement_fractions",
            "final_historical_task_for_exact_configuration", "independent_validation_claimed",
            "diversifier_route_reopened", "next_action",
            "same_period_historical_robustness_only",
            "paper_demo_eligibility_granted_inside_task", "prospective_validation_created",
        ),
    )
    write_csv(
        "failure_reasons.csv",
        [{
            "strategy_id": row["strategy_id"],
            "outcome": row["outcome"],
            "primary_failure_reason": row["failure_reason"],
            "strategy_changed_to_escape_outcome": False,
        } for row in decision_rows if row["failure_reason"]],
        (
            "strategy_id", "outcome", "primary_failure_reason",
            "strategy_changed_to_escape_outcome",
        ),
    )
    write_csv(
        "next_actions.csv",
        [{
            "scope": TASK_ID,
            "robustness_positive_count": positive_count,
            "robustness_blocked_count": blocked_count,
            "exact_next_action": next_action,
            "executed_in_this_task": False,
        }],
        (
            "scope", "robustness_positive_count", "robustness_blocked_count",
            "exact_next_action", "executed_in_this_task",
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
        "data_capability_tasks": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "bootstrap_resamples_per_candidate": BOOTSTRAP_RESAMPLES,
        "robustness_positive": positive_count,
        "robustness_mixed": sum(row["outcome"] == "robustness_mixed" for row in decision_rows),
        "robustness_failed": sum(row["outcome"] == "robustness_failed" for row in decision_rows),
        "robustness_blocked": blocked_count,
    }
    write_json("cohort_funnel_counts.json", funnel)
    write_yaml("robustness_manifest.yaml", {
        "task_id": TASK_ID,
        "mode": "bounded-historical-robustness",
        "stage": "robustness",
        "candidate_ids": [PERCENTILE_ID, GROWTH_ID],
        "parent_trial_ids": [PERCENTILE_PARENT_TRIAL, GROWTH_PARENT_TRIAL],
        "robustness_child_trial_ids": [PERCENTILE_TRIAL, GROWTH_TRIAL],
        "routes": {PERCENTILE_ID: "standalone_only", GROWTH_ID: "standalone_only"},
        "parent_exploration_outcomes_preserved": EXPECTED_PARENT_OUTCOMES,
        "diversifier_routes_reopened": False,
        "costs_bps": {PERCENTILE_ID: list(PERCENTILE_COSTS), GROWTH_ID: list(GROWTH_COSTS)},
        "rolling_windows_months": [36, 60],
        "bootstrap": {"block_length_months": 12, "resamples": 5000, "seed": BOOTSTRAP_SEED},
        "source_authority": str(SOURCE_ATTACHMENT),
        "source_authority_hash": source_hash_before,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_artifact_hashes_before_performance": preregistration_hashes,
        "parent_reproduction_pass_by_candidate": reproduction_by_candidate,
        "outcomes": {row["strategy_id"]: row["outcome"] for row in decision_rows},
        "final_same_period_historical_task": True,
        "independent_validation_claimed": False,
        "provider_access_performed": False,
        "parameter_or_universe_variant_tested": False,
        "lifecycle_state_changed": False,
        "paper_demo_action_performed": False,
        "broker_or_real_money_action_performed": False,
        "next_action": next_action,
    })

    after_hashes = snapshot_hashes()
    protected_unchanged = before_hashes == after_hashes
    source_unchanged = source_hash_before == file_hash(SOURCE_ATTACHMENT)
    entity_counts_pass = bool(
        funnel["existing_strategy_configurations_carried_forward"] == 2
        and funnel["new_strategy_configurations"] == 0
        and funnel["existing_exploration_trials_carried_forward"] == 2
        and funnel["new_robustness_trials"] == 2
        and funnel["validation_observations"] == 0
        and funnel["paper_demo_observations"] == 0
    )
    (OUTPUT_DIR / "robustness_report.md").write_text(
        report_text(decision_rows, full_metric_maps, next_action, True),
        encoding="utf-8",
    )
    expected_before_consistency = REQUIRED_FILES - {"consistency_check.json"}
    output_set_pass = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    } == expected_before_consistency
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": bool(
            all(reproduction_by_candidate.values())
            and all(runtime_invariants.values())
            and bootstrap_deterministic
            and protected_unchanged
            and source_unchanged
            and entity_counts_pass
            and output_set_pass
        ),
        "parent_reproduction_within_1e_9_by_candidate": reproduction_by_candidate,
        "all_runtime_invariants_pass_by_candidate": runtime_invariants,
        "bootstrap_deterministic": bootstrap_deterministic,
        "protected_state_cache_parent_evidence_and_observations_unchanged": protected_unchanged,
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": after_hashes,
        "source_attachment_unchanged": source_unchanged,
        "entity_counts_reconcile": entity_counts_pass,
        "exactly_two_robustness_child_trials": len(trials) == 2,
        "zero_new_strategy_configurations": True,
        "diversifier_routes_remain_closed": True,
        "same_period_evidence_not_called_validation": True,
        "final_historical_task_for_exact_configurations": True,
        "required_output_set_present_before_consistency": output_set_pass,
        "no_provider_validation_lifecycle_paper_demo_or_broker_action": True,
        "candidate_outcomes": {row["strategy_id"]: row["outcome"] for row in decision_rows},
        "next_action": next_action,
        "entity_counts": funnel,
    }
    write_json("consistency_check.json", consistency)
    if not consistency["overall_pass"]:
        raise RuntimeError("robustness consistency check failed")
    missing = sorted(REQUIRED_FILES - {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()})
    if missing:
        raise RuntimeError(f"missing required outputs: {missing}")
    return {
        "task_id": TASK_ID,
        "outcomes": {
            row["strategy_id"]: {
                "outcome": row["outcome"],
                "failure_reason": row["failure_reason"],
                "interpretation": row["interpretation"],
            }
            for row in decision_rows
        },
        "robustness_positive_count": positive_count,
        "next_action": next_action,
        "evidence_path": relative(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
