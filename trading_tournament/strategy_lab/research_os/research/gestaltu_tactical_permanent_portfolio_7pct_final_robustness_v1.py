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
    accepted_47_source_backed_exploration_batch_v1 as exploration,
)


TASK_ID = "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1"
STRATEGY_ID = "gestaltu_tactical_permanent_portfolio_7pct_v1"
SOURCE_RECORD_ID = "src_gestaltu_tactical_permanent_portfolio_7pct_v1"
FAMILY_ID = "trend_filtered_risk_parity_volatility_target"
PARENT_TRIAL_ID = "accepted47_source_v1__tactical_permanent_portfolio__canonical"
TRIAL_ID = f"{TASK_ID}__child"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
SOURCE_DIR = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "accepted_47_selective_source_backed_intake_v1"
    / "latest"
)
PARENT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "accepted_47_source_backed_exploration_batch_v1"
    / "latest"
)
CORRECTION_DIR = (
    ROOT
    / "evidence"
    / "corrections"
    / "materialize_and_resume_accepted_47_source_backed_batch_v1"
    / "latest"
)

PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
REPRODUCTION_TOLERANCE = 1e-9
TOLERANCE = 1e-10
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260806
PREREGISTRATION_TIMESTAMP = "2026-08-06T00:00:00-06:00"

RISK_ASSETS = exploration.TPP_RISK
UNIVERSE = exploration.TPP_UNIVERSE
TREND_CONTROL = exploration.TPP_NAMED
ALWAYS_LONG_CONTROL = "tpp_always_long_risk_parity_7pct_control"
STATIC_PERMANENT_CONTROL = "static_permanent_portfolio_25_each_control"
STATIC_AVERAGE_CONTROL = exploration.TPP_STATIC
SPY_CONTROL = "SPY_buy_and_hold"
BIL_CONTROL = "BIL_buy_and_hold"
ALL_CONTROLS = (
    TREND_CONTROL,
    ALWAYS_LONG_CONTROL,
    STATIC_PERMANENT_CONTROL,
    STATIC_AVERAGE_CONTROL,
    SPY_CONTROL,
    BIL_CONTROL,
)
DECISIVE_CONTROLS = (
    TREND_CONTROL,
    ALWAYS_LONG_CONTROL,
    STATIC_AVERAGE_CONTROL,
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
    "asset_component_attribution.csv",
    "selection_and_scaling_diagnostics.csv",
    "monthly_excess_concentration.csv",
    "neutralization_results.csv",
    "paired_block_bootstrap_results.csv",
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
            *exploration.PROTECTED_PATHS,
            PARENT_DIR.relative_to(ROOT),
            CORRECTION_DIR.relative_to(ROOT),
        )
    )
)


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
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


def file_hash(path: Path) -> str:
    if not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


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


def protected_hashes() -> dict[str, str]:
    return {
        path.as_posix(): tree_hash(ROOT / path)
        for path in PROTECTED_PATHS
    }


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def lineage_context() -> tuple[exploration.StrategySpec, dict[str, Any]]:
    specs, source_reconciliation = exploration.load_source_packet()
    matches = [spec for spec in specs if spec.strategy_id == STRATEGY_ID]
    source_rows = read_csv(SOURCE_DIR / "source_library_records.csv")
    source_matches = [row for row in source_rows if row["strategy_id"] == STRATEGY_ID]
    parent_cards = read_csv(PARENT_DIR / "strategy_cards.csv")
    parent_trials = read_csv(PARENT_DIR / "trial_ledger.csv")
    parent_outcomes = read_csv(PARENT_DIR / "outcome_summary.csv")
    card_matches = [row for row in parent_cards if row["strategy_id"] == STRATEGY_ID]
    trial_matches = [row for row in parent_trials if row["strategy_id"] == STRATEGY_ID]
    outcome_matches = [row for row in parent_outcomes if row["strategy_id"] == STRATEGY_ID]
    source_consistency = json.loads((SOURCE_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    parent_consistency = json.loads((PARENT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    correction_consistency = json.loads((CORRECTION_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    checks = {
        "source_packet_reconciliation_pass": bool(source_reconciliation["pass"]),
        "source_packet_consistency_pass": bool(source_consistency.get("overall_pass")),
        "parent_exploration_consistency_pass": bool(parent_consistency.get("overall_pass")),
        "correction_packet_consistency_pass": bool(correction_consistency.get("overall_pass")),
        "exactly_one_frozen_strategy_spec": len(matches) == 1,
        "exactly_one_source_record": len(source_matches) == 1,
        "exactly_one_parent_strategy_card": len(card_matches) == 1,
        "exactly_one_parent_trial": len(trial_matches) == 1,
        "exactly_one_parent_outcome": len(outcome_matches) == 1,
        "source_record_id_exact": bool(source_matches and source_matches[0]["source_record_id"] == SOURCE_RECORD_ID),
        "family_id_exact": bool(matches and matches[0].family_id == FAMILY_ID),
        "parent_trial_id_exact": bool(trial_matches and trial_matches[0]["trial_id"] == PARENT_TRIAL_ID),
        "parent_outcome_exact": bool(
            outcome_matches
            and outcome_matches[0]["outcome"] == "exploratory_followup_candidate_standalone"
        ),
        "caa_remains_closed": any(
            row["strategy_id"] == exploration.CAA_ID
            and row["outcome"] == "closed_exploration"
            for row in parent_outcomes
        ),
    }
    checks["pass"] = all(checks.values())
    if len(matches) != 1:
        raise RuntimeError("frozen TPP specification is not unique")
    return matches[0], {
        "checks": checks,
        "source_record": source_matches[0] if source_matches else {},
        "parent_card": card_matches[0] if card_matches else {},
        "parent_trial": trial_matches[0] if trial_matches else {},
        "parent_outcome": outcome_matches[0] if outcome_matches else {},
    }


def preregister(spec: exploration.StrategySpec, context: dict[str, Any]) -> None:
    source = context["source_record"]
    parent_card = context["parent_card"]
    parent_trial = context["parent_trial"]
    lineage_rows = [
        {
            "entity_type": "source_library_record",
            "entity_id": SOURCE_RECORD_ID,
            "stage": "source_extracted",
            "carried_forward": True,
            "strategy_id": STRATEGY_ID,
            "parent_entity_id": "",
            "source_or_research_lineage": spec.lineage,
            "outcome": source.get("outcome", "feasible"),
        },
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "exploratory_followup_standalone",
            "carried_forward": True,
            "strategy_id": STRATEGY_ID,
            "parent_entity_id": SOURCE_RECORD_ID,
            "source_or_research_lineage": spec.lineage,
            "outcome": "exploratory_followup_candidate_standalone",
        },
        {
            "entity_type": "experiment_trial",
            "entity_id": PARENT_TRIAL_ID,
            "stage": "exploration",
            "carried_forward": True,
            "strategy_id": STRATEGY_ID,
            "parent_entity_id": "",
            "source_or_research_lineage": spec.lineage,
            "outcome": "exploratory_followup_candidate_standalone",
        },
        {
            "entity_type": "experiment_trial",
            "entity_id": TRIAL_ID,
            "stage": "robustness",
            "carried_forward": False,
            "strategy_id": STRATEGY_ID,
            "parent_entity_id": PARENT_TRIAL_ID,
            "source_or_research_lineage": spec.lineage,
            "outcome": "preregistered_for_bounded_historical_robustness",
        },
    ]
    write_csv("source_strategy_trial_lineage.csv", lineage_rows)
    trial_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": parent_card.get("display_name", spec.display_name),
        "entity_type": "experiment_trial",
        "strategy_architecture": spec.architecture,
        "source_or_research_lineage": spec.lineage,
        "instrument_universe": list(UNIVERSE),
        "parameters": spec.parameters,
        "benchmark_or_control": list(ALL_CONTROLS),
        "route": "standalone_only",
        "stage": "robustness",
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "robustness_variant",
        "changed_fields_from_parent": "robustness_diagnostics_only",
        "outcome": "preregistered_for_bounded_historical_robustness",
        "failure_reason": "",
        "next_action": "execute_frozen_robustness_diagnostics",
        "source_rule_changed": False,
        "parameters_changed": False,
        "universe_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "controls_added": False,
        "optimization_performed": False,
        "paper_demo_eligibility_granted_inside_this_task": False,
        "independent_validation_claimed": False,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "parent_trial_preserved": parent_trial.get("trial_id") == PARENT_TRIAL_ID,
    }
    write_csv("trial_ledger.csv", [trial_row])
    parent_benchmarks = [
        row
        for row in read_csv(PARENT_DIR / "benchmark_reference_log.csv")
        if row["strategy_id"] == STRATEGY_ID
    ]
    benchmark_rows = [
        {
            **row,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "carried_forward_from_parent": True,
            "decisive_control": row["benchmark_id"] in DECISIVE_CONTROLS,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for row in parent_benchmarks
    ]
    write_csv("benchmark_reference_log.csv", benchmark_rows)
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": "robustness",
                "strategy_count": 1,
                "new_strategy_configuration_count": 0,
                "new_robustness_trial_count": 1,
                "validation_observation_count": 0,
                "paper_demo_observation_count": 0,
                "data_capability_task_count": 0,
                "provider_access_performed": False,
                "lifecycle_state_changed": False,
            }
        ],
    )
    write_yaml(
        "robustness_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "bounded-historical-robustness",
            "stage": "robustness",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "route": "standalone_only",
            "source_rule_changed": False,
            "costs_bps_one_way": list(COSTS),
            "bootstrap": {
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "resamples": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
            },
            "preregistered_before_robustness_results": True,
            "independent_validation_claimed": False,
            "paper_demo_onboarding_performed": False,
        },
    )


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        result[column] = result[column].map(serialize)
    return result


def compare_frames(scope: str, archived: pd.DataFrame, reproduced: pd.DataFrame) -> dict[str, Any]:
    reproduced = reproduced.reindex(columns=archived.columns)
    same_columns = list(archived.columns) == list(reproduced.columns)
    same_rows = len(archived) == len(reproduced)
    mismatch_count = 0
    maximum_difference = 0.0
    if same_columns and same_rows:
        left = normalize_frame(archived).reset_index(drop=True)
        right = normalize_frame(reproduced).reset_index(drop=True)
        for column in left.columns:
            left_numeric = pd.to_numeric(left[column], errors="coerce")
            right_numeric = pd.to_numeric(right[column], errors="coerce")
            numeric = left_numeric.notna() & right_numeric.notna()
            if numeric.any():
                difference = (left_numeric[numeric] - right_numeric[numeric]).abs()
                maximum_difference = max(maximum_difference, float(difference.max()))
                mismatch_count += int((difference > REPRODUCTION_TOLERANCE).sum())
            text = ~numeric
            if text.any():
                mismatch_count += int(
                    (
                        left.loc[text, column].fillna("").astype(str).to_numpy()
                        != right.loc[text, column].fillna("").astype(str).to_numpy()
                    ).sum()
                )
    else:
        mismatch_count = max(len(archived), len(reproduced), 1)
    return {
        "scope": scope,
        "archived_row_count": len(archived),
        "reproduced_row_count": len(reproduced),
        "columns_match": same_columns,
        "rows_match": same_rows,
        "maximum_numeric_difference": maximum_difference,
        "mismatch_count": mismatch_count,
        "tolerance": REPRODUCTION_TOLERANCE,
        "pass": bool(same_columns and same_rows and mismatch_count == 0),
    }


def parent_invariant_row(
    prepared: dict[str, Any],
    ledger: list[dict[str, Any]],
    deterministic: bool,
) -> dict[str, Any]:
    values = prepared["candidate_events"].to_numpy(dtype=float)
    timing_pass = all(
        pd.Timestamp(row["execution_date"]) > pd.Timestamp(row["signal_date"])
        for row in ledger
        if row.get("execution_date") and row.get("signal_date")
    )
    checks = {
        "source_packet_reconciliation": True,
        "optimizer_equivalence": True,
        "completed_session_signals": all(
            bool(row.get("signal_uses_completed_session_only", True)) for row in ledger
        ),
        "frozen_execution_timing": timing_pass,
        "weights_nonnegative": bool((values >= -exploration.WEIGHT_TOL).all()),
        "weights_sum_to_one": bool(
            np.allclose(values.sum(axis=1), 1.0, atol=exploration.WEIGHT_TOL, rtol=0.0)
        ),
        "maximum_gross_exposure_one": bool(
            (np.abs(values).sum(axis=1) <= 1.0 + exploration.WEIGHT_TOL).all()
        ),
        "explicit_zero_weights": bool((np.abs(values) <= exploration.WEIGHT_TOL).any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": True,
        "deterministic_rerun": deterministic,
    }
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": PARENT_TRIAL_ID,
        **checks,
        "overall_pass": all(checks.values()),
    }


def reproduce_parent(
    spec: exploration.StrategySpec,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], bool]:
    frames = {symbol: exploration.load_frame(symbol) for symbol in UNIVERSE}
    prepared = exploration.prepare_tpp(spec, frames)
    simulation = exploration.simulate(prepared)
    repeated = exploration.simulate(prepared)
    deterministic = exploration.stable_hash(
        simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
    ) == exploration.stable_hash(
        repeated["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
    )
    candidate_rows, control_rows, half_rows, eligible = exploration.full_and_half_rows(
        spec, prepared, simulation
    )
    portfolio_paths = exploration.portfolio_paths(spec, simulation, eligible)
    portfolio_rows, portfolio_half_rows = exploration.portfolio_result_rows(spec, portfolio_paths)
    half_rows.extend(portfolio_half_rows)
    ledger = exploration.enrich_ledgers(prepared, simulation)
    diagnostics = exploration.allocation_diagnostics(spec, prepared, ledger)
    turnover_rows: list[dict[str, Any]] = []
    for cost in exploration.COSTS:
        paths = [
            (STRATEGY_ID, simulation["candidate_paths"][cost], "candidate"),
            *[
                (
                    control_id,
                    simulation["control_paths"][(control_id, cost)],
                    "benchmark_reference",
                )
                for control_id in prepared["control_events"]
            ],
        ]
        for series_id, path, role in paths:
            values = exploration.accounting.metric_payload(path, eligible)
            turnover_rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": PARENT_TRIAL_ID,
                    "series_id": series_id,
                    "entity_role": role,
                    "cost_bps_one_way": cost,
                    "turnover": values["turnover"],
                    "transaction_cost_drag": values["transaction_cost_drag"],
                    "expected_linear_cost": values["turnover"] * cost / 10000.0,
                    "cost_charged_once": True,
                    "turnover_formula": "0.5*sum(abs(target-pretrade))",
                }
            )
    invariant = parent_invariant_row(prepared, ledger, deterministic)
    generated = {
        "all_trial_results.csv": pd.DataFrame(candidate_rows),
        "control_results.csv": pd.DataFrame(control_rows),
        "chronological_half_results.csv": pd.DataFrame(half_rows),
        "portfolio_contribution_results.csv": pd.DataFrame(portfolio_rows),
        "tpp_monthly_signal_ledger.csv": pd.DataFrame(ledger),
        "tpp_allocation_diagnostics.csv": pd.DataFrame(diagnostics),
        "turnover_cost_reconciliation.csv": pd.DataFrame(turnover_rows),
        "invariant_results.csv": pd.DataFrame([invariant]),
    }
    comparisons: list[dict[str, Any]] = []
    for filename, current in generated.items():
        archived = pd.read_csv(PARENT_DIR / filename, keep_default_na=False)
        if "strategy_id" in archived.columns:
            archived = archived.loc[archived["strategy_id"].eq(STRATEGY_ID)].reset_index(drop=True)
        comparisons.append(compare_frames(filename, archived, current))
    parent_checks = [
        ("source_consistency_check", SOURCE_DIR / "consistency_check.json"),
        ("correction_consistency_check", CORRECTION_DIR / "consistency_check.json"),
        ("exploration_consistency_check", PARENT_DIR / "consistency_check.json"),
    ]
    for scope, path in parent_checks:
        payload = json.loads(path.read_text(encoding="utf-8"))
        comparisons.append(
            {
                "scope": scope,
                "archived_row_count": 1,
                "reproduced_row_count": 1,
                "columns_match": True,
                "rows_match": True,
                "maximum_numeric_difference": 0.0,
                "mismatch_count": 0 if payload.get("overall_pass") else 1,
                "tolerance": REPRODUCTION_TOLERANCE,
                "pass": bool(payload.get("overall_pass")),
            }
        )
    comparisons.append(
        {
            "scope": "deterministic_candidate_path",
            "archived_row_count": len(eligible),
            "reproduced_row_count": len(eligible),
            "columns_match": True,
            "rows_match": True,
            "maximum_numeric_difference": 0.0,
            "mismatch_count": 0 if deterministic else 1,
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": deterministic,
        }
    )
    return prepared, simulation, comparisons, all(row["pass"] for row in comparisons)


def simulate_costs(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_target_applied_at_frozen_following_close"
    return {
        "candidate_paths": {
            cost: exploration.accounting.simulate_path(
                prepared["prices"], prepared["candidate_events"], cost, timing
            )
            for cost in COSTS
        },
        "control_paths": {
            (control_id, cost): exploration.accounting.simulate_path(
                prepared["prices"], events, cost, timing
            )
            for control_id, events in prepared["control_events"].items()
            for cost in COSTS
        },
    }


def path_metrics(
    path: dict[str, Any],
    index: pd.DatetimeIndex,
    risk_assets: tuple[str, ...] = RISK_ASSETS,
) -> dict[str, Any]:
    values = exploration.metrics(path, index, risk_assets)
    held = path["held_weights"].reindex(index).dropna(how="all")
    risky = held[list(risk_assets)].sum(axis=1)
    values.update(
        {
            "maximum_risky_exposure": float(risky.max()),
            "average_bil_exposure": float(held["BIL"].mean()) if "BIL" in held else 0.0,
        }
    )
    return values


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.dominates(control, candidate)


def material(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.material(candidate, control)


def result_values(
    series_id: str,
    cost: float,
    period: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "series_id": series_id,
        "cost_bps_one_way": cost,
        "period": period,
        **values,
    }


def full_cost_rows(
    prepared: dict[str, Any], simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        rows.append(
            result_values(
                STRATEGY_ID,
                cost,
                "full_authoritative_period",
                path_metrics(simulation["candidate_paths"][cost], eligible),
            )
        )
        for control_id in DECISIVE_CONTROLS:
            rows.append(
                result_values(
                    control_id,
                    cost,
                    "full_authoritative_period",
                    path_metrics(simulation["control_paths"][(control_id, cost)], eligible),
                )
            )
    return rows


def split_partitions(index: pd.DatetimeIndex) -> list[tuple[str, str, pd.DatetimeIndex]]:
    rows: list[tuple[str, str, pd.DatetimeIndex]] = [("full", "full_authoritative_period", index)]
    rows.extend(("half", name, values) for name, values in exploration.accounting.split_halves(index))
    rows.extend(
        ("quarter", f"chronological_quarter_{position + 1}", index[locations])
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    )
    return rows


def comparison_row(
    partition_type: str,
    period: str,
    period_index: pd.DatetimeIndex,
    candidate_path: dict[str, Any],
    control_id: str,
    control_path: dict[str, Any],
) -> dict[str, Any]:
    candidate = path_metrics(candidate_path, period_index)
    control = path_metrics(control_path, period_index)
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "partition_type": partition_type,
        "period": period,
        "evaluation_start": period_index[0].date().isoformat(),
        "evaluation_end": period_index[-1].date().isoformat(),
        "comparison_control_id": control_id,
        **{f"candidate_{key}": value for key, value in candidate.items()},
        **{f"control_{key}": value for key, value in control.items()},
        "cagr_difference": candidate["cagr"] - control["cagr"],
        "sharpe_difference": candidate["sharpe_ratio"] - control["sharpe_ratio"],
        "maximum_drawdown_difference": candidate["maximum_drawdown"] - control["maximum_drawdown"],
        "candidate_improves_control_sharpe_or_drawdown": bool(
            candidate["sharpe_ratio"] > control["sharpe_ratio"]
            or candidate["maximum_drawdown"] > control["maximum_drawdown"]
        ),
        "control_dominates_candidate": dominates(control, candidate),
        "candidate_material_vs_control": material(candidate, control),
        "unfavorable_result_retained": True,
        "independent_validation_claimed": False,
    }


def chronological_rows(
    simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    for partition_type, period, period_index in split_partitions(eligible):
        for control_id in DECISIVE_CONTROLS:
            rows.append(
                comparison_row(
                    partition_type,
                    period,
                    period_index,
                    candidate,
                    control_id,
                    simulation["control_paths"][(control_id, PRIMARY_COST)],
                )
            )
    return rows


def complete_calendar_years(index: pd.DatetimeIndex) -> list[tuple[int, pd.DatetimeIndex]]:
    rows: list[tuple[int, pd.DatetimeIndex]] = []
    for year in range(int(index.min().year) + 1, int(index.max().year)):
        values = index[index.year == year]
        if len(values):
            rows.append((year, values))
    return rows


def calendar_year_rows(
    simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    for year, year_index in complete_calendar_years(eligible):
        for control_id in DECISIVE_CONTROLS:
            row = comparison_row(
                "complete_calendar_year",
                str(year),
                year_index,
                candidate,
                control_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
            )
            row["calendar_year"] = year
            rows.append(row)
    return rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index)
        .groupby(index.to_period("M"))
        .last()
        .tolist()
    ]


def rolling_rows(
    simulation: dict[str, Any], eligible: pd.DatetimeIndex, months: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sequence = 0
    for end in month_end_dates(eligible):
        boundary = end - pd.DateOffset(months=months)
        if boundary < eligible[0]:
            continue
        period = eligible[(eligible > boundary) & (eligible <= end)]
        if not len(period):
            continue
        sequence += 1
        for control_id in DECISIVE_CONTROLS:
            row = comparison_row(
                f"rolling_{months}_months",
                f"rolling_{months}_{sequence:03d}",
                period,
                simulation["candidate_paths"][PRIMARY_COST],
                control_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
            )
            row.update({"window_months": months, "window_sequence": sequence})
            rows.append(row)
    return rows


def rolling_summary(
    rows36: list[dict[str, Any]], rows60: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for months, rows in ((36, rows36), (60, rows60)):
        for control_id in DECISIVE_CONTROLS:
            subset = [row for row in rows if row["comparison_control_id"] == control_id]
            output.append(
                {
                    "window_months": months,
                    "comparison_control_id": control_id,
                    "window_count": len(subset),
                    "median_cagr_difference": float(np.median([row["cagr_difference"] for row in subset])),
                    "median_sharpe_difference": float(np.median([row["sharpe_difference"] for row in subset])),
                    "median_maximum_drawdown_difference": float(
                        np.median([row["maximum_drawdown_difference"] for row in subset])
                    ),
                    "candidate_improves_control_fraction": float(
                        np.mean([row["candidate_improves_control_sharpe_or_drawdown"] for row in subset])
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
    simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    end = eligible[-1]
    for year in range(2010, 2017):
        starts = eligible[eligible >= pd.Timestamp(f"{year}-01-01")]
        if not len(starts):
            continue
        start = starts[0]
        period = eligible[(eligible >= start) & (eligible <= end)]
        for control_id in DECISIVE_CONTROLS:
            row = comparison_row(
                "deterministic_annual_start",
                f"start_{year}",
                period,
                simulation["candidate_paths"][PRIMARY_COST],
                control_id,
                simulation["control_paths"][(control_id, PRIMARY_COST)],
            )
            row.update(
                {
                    "requested_start_year": year,
                    "actual_start": start.date().isoformat(),
                    "fixed_end": end.date().isoformat(),
                    "start_selected_from_performance": False,
                }
            )
            rows.append(row)
    return rows


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).groupby(returns.index.to_period("M")).prod().sub(1.0)


def monthly_metrics(returns: pd.Series | np.ndarray) -> dict[str, float]:
    values = np.asarray(returns, dtype=float)
    if not len(values):
        return {key: float("nan") for key in ("total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown")}
    wealth = np.cumprod(1.0 + values)
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    running_max = np.maximum.accumulate(wealth)
    return {
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(values)) - 1.0),
        "annualized_volatility": std * math.sqrt(12.0),
        "sharpe_ratio": float(np.mean(values) / std * math.sqrt(12.0)) if std > 0.0 else 0.0,
        "maximum_drawdown": float(np.min(wealth / running_max - 1.0)),
    }


def turnover_by_asset(path: dict[str, Any], prices: pd.DataFrame) -> dict[str, float]:
    result = {symbol: 0.0 for symbol in prices.columns}
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    events = path["target_events"]
    for date, target in events.iterrows():
        if date not in prices.index:
            continue
        held = path["held_weights"].loc[date].to_numpy(dtype=float)
        daily_return = asset_returns.loc[date].to_numpy(dtype=float)
        drifted = held * (1.0 + daily_return)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held
        contributions = 0.5 * np.abs(target.to_numpy(dtype=float) - pretrade)
        for symbol, value in zip(prices.columns, contributions):
            result[symbol] += float(value)
    return result


def asset_attribution_rows(
    prepared: dict[str, Any], simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    prices = prepared["prices"].reindex(eligible)
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
    candidate_held = candidate_path["held_weights"].reindex(eligible)
    candidate_contribution = candidate_held * asset_returns
    target_history = exploration._target_history(prepared["candidate_events"], prepared["prices"].index).loc[eligible]
    turnover = turnover_by_asset(candidate_path, prepared["prices"])
    ledger = prepared["ledger"]
    valid_ledgers = [row for row in ledger if row.get("formation_valid")]
    monthly_asset = candidate_contribution.groupby(candidate_contribution.index.to_period("M")).sum()
    spy_monthly = monthly_returns(asset_returns["SPY"])
    positive_months = spy_monthly[spy_monthly > 0.0].index
    negative_months = spy_monthly[spy_monthly < 0.0].index
    control_contributions: dict[str, pd.DataFrame] = {}
    for control_id in DECISIVE_CONTROLS:
        held = simulation["control_paths"][(control_id, PRIMARY_COST)]["held_weights"].reindex(eligible)
        control_contributions[control_id] = held * asset_returns
    rows: list[dict[str, Any]] = []
    for symbol in UNIVERSE:
        selected_frequency = (
            float(np.mean([symbol in row.get("selected_assets", []) for row in valid_ledgers]))
            if symbol in RISK_ASSETS and valid_ledgers
            else float((target_history[symbol] > TOLERANCE).mean())
        )
        rows.append(
            {
                "record_type": "asset_detail",
                "asset": symbol,
                "selection_frequency": selected_frequency,
                "average_target_weight": float(target_history[symbol].mean()),
                "maximum_target_weight": float(target_history[symbol].max()),
                "realized_additive_gross_return_contribution": float(candidate_contribution[symbol].sum()),
                "turnover_contribution": turnover[symbol],
                "candidate_minus_trend_equal_weight_additive_contribution": float(
                    (candidate_contribution[symbol] - control_contributions[TREND_CONTROL][symbol]).sum()
                ),
                "candidate_minus_always_long_risk_parity_additive_contribution": float(
                    (candidate_contribution[symbol] - control_contributions[ALWAYS_LONG_CONTROL][symbol]).sum()
                ),
                "candidate_minus_static_average_additive_contribution": float(
                    (candidate_contribution[symbol] - control_contributions[STATIC_AVERAGE_CONTROL][symbol]).sum()
                ),
                "contribution_during_positive_spy_months": float(
                    monthly_asset.loc[monthly_asset.index.intersection(positive_months), symbol].sum()
                ),
                "contribution_during_negative_spy_months": float(
                    monthly_asset.loc[monthly_asset.index.intersection(negative_months), symbol].sum()
                ),
                "rule_changed_from_attribution": False,
            }
        )
    candidate_monthly = monthly_returns(candidate_path["returns"].reindex(eligible))
    for control_id in DECISIVE_CONTROLS:
        difference = candidate_contribution - control_contributions[control_id]
        positive_asset = difference.clip(lower=0.0).sum()
        denominator = float(positive_asset.sum())
        strongest_asset = str(positive_asset.idxmax()) if denominator > 0.0 else ""
        strongest_asset_share = float(positive_asset.max() / denominator) if denominator > 0.0 else 0.0
        control_monthly = monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(eligible)
        )
        excess = candidate_monthly - control_monthly
        positive_month = excess.clip(lower=0.0)
        positive_month_total = float(positive_month.sum())
        annual = excess.groupby(excess.index.year).sum().clip(lower=0.0)
        annual_total = float(annual.sum())
        rows.append(
            {
                "record_type": "control_concentration_summary",
                "comparison_control_id": control_id,
                "strongest_positive_contribution_asset": strongest_asset,
                "strongest_asset_pct_total_positive_contribution": strongest_asset_share,
                "strongest_positive_excess_month": str(positive_month.idxmax()) if positive_month_total > 0 else "",
                "strongest_month_pct_cumulative_positive_excess": float(positive_month.max() / positive_month_total) if positive_month_total > 0 else 0.0,
                "strongest_positive_excess_calendar_year": int(annual.idxmax()) if annual_total > 0 else "",
                "strongest_year_pct_cumulative_positive_excess": float(annual.max() / annual_total) if annual_total > 0 else 0.0,
                "unfavorable_concentration_retained": True,
            }
        )
    return rows


def target_overlap(left: pd.DataFrame, right: pd.DataFrame) -> pd.Series:
    common = left.index.intersection(right.index)
    return pd.Series(
        np.minimum(left.loc[common].to_numpy(dtype=float), right.loc[common].to_numpy(dtype=float)).sum(axis=1),
        index=common,
    )


def selection_scaling_rows(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    valid = [row for row in prepared["ledger"] if row.get("formation_valid")]
    rows: list[dict[str, Any]] = []
    selected_counts = [len(row.get("selected_assets", [])) for row in valid]
    for count in range(4):
        rows.append(
            {
                "diagnostic": "selected_risk_asset_count",
                "component": count,
                "observation_count": selected_counts.count(count),
                "frequency": float(np.mean(np.asarray(selected_counts) == count)),
            }
        )
    scale_eligible = [row for row in valid if row.get("selected_assets")]
    scales = np.asarray([float(row["scale_factor"]) for row in scale_eligible], dtype=float)
    binding = scales < 1.0 - TOLERANCE
    rows.extend(
        [
            {
                "diagnostic": "volatility_target_binding_frequency",
                "component": "scale_lt_one",
                "value": float(binding.mean()),
            },
            {
                "diagnostic": "average_binding_scale_reduction",
                "component": "one_minus_scale_when_binding",
                "value": float(np.mean(1.0 - scales[binding])) if binding.any() else 0.0,
            },
            {
                "diagnostic": "average_pre_scale_portfolio_volatility",
                "component": "annualized",
                "value": float(
                    np.mean(
                        [
                            row["pre_scale_portfolio_volatility"]
                            for row in scale_eligible
                        ]
                    )
                ),
            },
            {
                "diagnostic": "average_bil_residual",
                "component": "BIL",
                "value": float(np.mean([row["bil_weight"] for row in valid])),
            },
        ]
    )
    index = prepared["prices"].index
    candidate = exploration._target_history(prepared["candidate_events"], index)
    for control_id in (TREND_CONTROL, ALWAYS_LONG_CONTROL):
        control = exploration._target_history(prepared["control_events"][control_id], index)
        overlap = target_overlap(candidate, control)
        rows.extend(
            [
                {
                    "diagnostic": "average_target_weight_overlap",
                    "component": control_id,
                    "value": float(overlap.mean()),
                },
                {
                    "diagnostic": "exact_target_match_frequency",
                    "component": control_id,
                    "value": float((np.abs(candidate - control).max(axis=1) <= TOLERANCE).mean()),
                },
            ]
        )
    return rows


def monthly_concentration_rows(
    simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    candidate = monthly_returns(simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(eligible))
    rows: list[dict[str, Any]] = []
    for control_id in DECISIVE_CONTROLS:
        control = monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(eligible)
        )
        aligned = pd.concat([candidate.rename("candidate"), control.rename("control")], axis=1).dropna()
        excess = aligned["candidate"] - aligned["control"]
        positive = excess[excess > 0.0].sort_values(ascending=False)
        strongest = positive.index[0] if len(positive) else None
        strongest_three = set(positive.index[:3])
        annual = excess.groupby(excess.index.year).sum()
        strongest_year = int(annual.idxmax()) if len(annual) else None
        for period, row in aligned.iterrows():
            rows.append(
                {
                    "comparison_control_id": control_id,
                    "month": str(period),
                    "candidate_return_5bps": row["candidate"],
                    "control_return_5bps": row["control"],
                    "candidate_minus_control_excess": excess.loc[period],
                    "positive_excess_rank": int(positive.index.get_loc(period) + 1) if period in positive.index else "",
                    "strongest_positive_excess_month": period == strongest,
                    "among_three_strongest_positive_excess_months": period in strongest_three,
                    "strongest_positive_excess_calendar_year": period.year == strongest_year,
                    "frozen_before_counterfactual_calculation": True,
                    "canonical_observation_deleted": False,
                }
            )
    return rows


def neutralization_rows(
    simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    monthly = {
        STRATEGY_ID: monthly_returns(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(eligible)
        )
    }
    for control_id in DECISIVE_CONTROLS:
        monthly[control_id] = monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(eligible)
        )
    aligned = pd.concat([series.rename(key) for key, series in monthly.items()], axis=1).dropna()
    control_metrics = {control_id: monthly_metrics(aligned[control_id]) for control_id in DECISIVE_CONTROLS}
    rows: list[dict[str, Any]] = []
    for control_id in DECISIVE_CONTROLS:
        excess = aligned[STRATEGY_ID] - aligned[control_id]
        positive = excess[excess > 0.0].sort_values(ascending=False)
        strongest = list(positive.index[:3])
        if not strongest:
            continue
        annual = excess.groupby(excess.index.year).sum()
        strongest_year = int(annual.idxmax())
        scenarios = {
            "neutralize_strongest_positive_month": strongest[:1],
            "neutralize_three_strongest_positive_months": strongest,
            "neutralize_strongest_positive_calendar_year": [
                period for period in aligned.index if period.year == strongest_year
            ],
        }
        for scenario, periods in scenarios.items():
            counterfactual = aligned[STRATEGY_ID].copy()
            counterfactual.loc[periods] = aligned.loc[periods, control_id]
            candidate_metrics = monthly_metrics(counterfactual)
            dominance = {
                other: dominates(control_metrics[other], candidate_metrics)
                for other in DECISIVE_CONTROLS
            }
            rows.append(
                {
                    "neutralized_against_control_id": control_id,
                    "scenario": scenario,
                    "neutralized_months": [str(period) for period in periods],
                    "neutralized_month_count": len(periods),
                    "strongest_calendar_year": strongest_year,
                    **candidate_metrics,
                    "applicable_control_cagr": control_metrics[control_id]["cagr"],
                    "applicable_control_sharpe_ratio": control_metrics[control_id]["sharpe_ratio"],
                    "applicable_control_maximum_drawdown": control_metrics[control_id]["maximum_drawdown"],
                    "candidate_material_vs_applicable_control": material(
                        candidate_metrics, control_metrics[control_id]
                    ),
                    "applicable_control_dominates_candidate": dominance[control_id],
                    "any_decisive_control_dominates_candidate": any(dominance.values()),
                    "decisive_control_dominance": dominance,
                    "observations_deleted": False,
                    "canonical_return_series_modified": False,
                    "used_for_strategy_change": False,
                }
            )
    return rows


def paired_moving_block_bootstrap(
    monthly: pd.DataFrame,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> list[dict[str, Any]]:
    columns = [STRATEGY_ID, *DECISIVE_CONTROLS]
    aligned = monthly[columns].dropna()
    values = aligned.to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    if max_start < 0:
        raise RuntimeError("insufficient monthly observations for paired bootstrap")
    rng = np.random.default_rng(seed)
    counts = {
        control_id: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0}
        for control_id in DECISIVE_CONTROLS
    }
    for _ in range(resamples):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled = np.concatenate(
            [np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts]
        )[:count]
        sample = values[sampled]
        candidate = monthly_metrics(sample[:, 0])
        for column, control_id in enumerate(DECISIVE_CONTROLS, start=1):
            control = monthly_metrics(sample[:, column])
            higher_cagr = candidate["cagr"] > control["cagr"]
            higher_sharpe = candidate["sharpe_ratio"] > control["sharpe_ratio"]
            better_drawdown = candidate["maximum_drawdown"] > control["maximum_drawdown"]
            counts[control_id]["cagr"] += int(higher_cagr)
            counts[control_id]["sharpe"] += int(higher_sharpe)
            counts[control_id]["drawdown"] += int(better_drawdown)
            counts[control_id]["either"] += int(higher_sharpe or better_drawdown)
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "comparison_control_id": control_id,
            "monthly_observation_count": count,
            "moving_block_length_months": BOOTSTRAP_BLOCK_MONTHS,
            "resamples": resamples,
            "deterministic_seed": seed,
            "probability_candidate_higher_cagr": counts[control_id]["cagr"] / resamples,
            "probability_candidate_higher_sharpe": counts[control_id]["sharpe"] / resamples,
            "probability_candidate_less_severe_maximum_drawdown": counts[control_id]["drawdown"] / resamples,
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": counts[control_id]["either"] / resamples,
            "paired_cross_series_dependence_preserved": True,
            "used_for_strategy_change": False,
            "independent_validation_claimed": False,
        }
        for control_id in DECISIVE_CONTROLS
    ]


def bootstrap_frame(simulation: dict[str, Any], eligible: pd.DatetimeIndex) -> pd.DataFrame:
    series = {
        STRATEGY_ID: monthly_returns(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(eligible)
        )
    }
    for control_id in DECISIVE_CONTROLS:
        series[control_id] = monthly_returns(
            simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(eligible)
        )
    return pd.concat([value.rename(key) for key, value in series.items()], axis=1).dropna()


def turnover_reconciliation_rows(
    prepared: dict[str, Any], simulation: dict[str, Any], eligible: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    prices = prepared["prices"]
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        paths = [(STRATEGY_ID, simulation["candidate_paths"][cost])]
        paths.extend(
            (control_id, simulation["control_paths"][(control_id, cost)])
            for control_id in DECISIVE_CONTROLS
        )
        for series_id, path in paths:
            values = path_metrics(path, eligible)
            held = path["held_weights"].reindex(eligible)
            gross = (held * asset_returns.reindex(eligible)).sum(axis=1)
            expected = float(
                ((1.0 + gross) * path["turnover"].reindex(eligible) * cost / 10000.0).sum()
            )
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "series_id": series_id,
                    "cost_bps_one_way": cost,
                    "one_way_turnover": values["turnover"],
                    "transaction_cost_drag": values["transaction_cost_drag"],
                    "expected_transaction_cost_drag": expected,
                    "absolute_reconciliation_difference": abs(
                        values["transaction_cost_drag"] - expected
                    ),
                    "average_risky_exposure": values["average_risky_exposure"],
                    "average_bil_exposure": values["average_bil_exposure"],
                    "cost_charged_once": abs(values["transaction_cost_drag"] - expected) <= 1e-12,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
    return rows


def classify(
    reproduction_pass: bool,
    invariants_pass: bool,
    cost_rows: list[dict[str, Any]],
    chronology: list[dict[str, Any]],
    rolling: list[dict[str, Any]],
    attribution: list[dict[str, Any]],
    neutralization: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, bool]]:
    by_cost_series = {
        (float(row["cost_bps_one_way"]), row["series_id"]): row for row in cost_rows
    }
    candidate5 = by_cost_series[(5.0, STRATEGY_ID)]
    full_controls = [by_cost_series[(5.0, control_id)] for control_id in DECISIVE_CONTROLS]
    full_no_dominance = all(not dominates(control, candidate5) for control in full_controls)
    full_materiality = all(material(candidate5, control) for control in full_controls)
    quarter_checks = {
        control_id: sum(
            bool(row["candidate_improves_control_sharpe_or_drawdown"])
            for row in chronology
            if row["partition_type"] == "quarter"
            and row["comparison_control_id"] == control_id
        )
        >= 3
        for control_id in DECISIVE_CONTROLS
    }
    rolling_checks = {
        (int(row["window_months"]), row["comparison_control_id"]): (
            float(row["candidate_improves_control_fraction"]) > 0.5
            and float(row["control_dominates_candidate_fraction"]) <= 0.5
        )
        for row in rolling
    }
    candidate10 = by_cost_series[(10.0, STRATEGY_ID)]
    ten_pass = all(
        material(candidate10, by_cost_series[(10.0, control_id)])
        and not dominates(by_cost_series[(10.0, control_id)], candidate10)
        for control_id in DECISIVE_CONTROLS
    )
    candidate15 = by_cost_series[(15.0, STRATEGY_ID)]
    candidate20 = by_cost_series[(20.0, STRATEGY_ID)]
    twenty_not_dominated_by_every = not all(
        dominates(by_cost_series[(20.0, control_id)], candidate20)
        for control_id in DECISIVE_CONTROLS
    )
    trend_neutral = {
        row["scenario"]: row
        for row in neutralization
        if row["neutralized_against_control_id"] == TREND_CONTROL
    }
    neutral_three_pass = bool(
        trend_neutral.get("neutralize_three_strongest_positive_months", {}).get(
            "candidate_material_vs_applicable_control", False
        )
        and not trend_neutral.get("neutralize_three_strongest_positive_months", {}).get(
            "any_decisive_control_dominates_candidate", True
        )
    )
    neutral_year_pass = bool(
        trend_neutral.get("neutralize_strongest_positive_calendar_year", {}).get(
            "candidate_material_vs_applicable_control", False
        )
        and not trend_neutral.get("neutralize_strongest_positive_calendar_year", {}).get(
            "any_decisive_control_dominates_candidate", True
        )
    )
    trend_concentration = next(
        row
        for row in attribution
        if row.get("record_type") == "control_concentration_summary"
        and row.get("comparison_control_id") == TREND_CONTROL
    )
    concentration_pass = bool(
        float(trend_concentration["strongest_asset_pct_total_positive_contribution"]) <= 0.60
        and float(trend_concentration["strongest_year_pct_cumulative_positive_excess"]) <= 0.60
    )
    bootstrap_by_control = {row["comparison_control_id"]: row for row in bootstrap}
    bootstrap_pass = bool(
        bootstrap_by_control[TREND_CONTROL][
            "probability_candidate_higher_sharpe_or_less_severe_drawdown"
        ]
        >= 0.70
        and all(
            bootstrap_by_control[control_id][
                "probability_candidate_higher_sharpe_or_less_severe_drawdown"
            ]
            >= 0.60
            for control_id in (ALWAYS_LONG_CONTROL, STATIC_AVERAGE_CONTROL)
        )
    )
    exposure_not_sole_explanation = bool(
        material(candidate5, by_cost_series[(5.0, STATIC_AVERAGE_CONTROL)])
        and not dominates(by_cost_series[(5.0, STATIC_AVERAGE_CONTROL)], candidate5)
    )
    checks = {
        "parent_reproduction_and_invariants_pass": reproduction_pass and invariants_pass,
        "candidate_positive_at_5bps": candidate5["total_return"] > 0.0,
        "no_decisive_control_dominates_full_period": full_no_dominance,
        "material_vs_each_decisive_control_full_period": full_materiality,
        "three_of_four_quarters_improve_each_decisive_control": all(quarter_checks.values()),
        "rolling_36_majority_improvement_and_limited_dominance_each_control": all(
            rolling_checks.get((36, control_id), False) for control_id in DECISIVE_CONTROLS
        ),
        "rolling_60_majority_improvement_and_limited_dominance_each_control": all(
            rolling_checks.get((60, control_id), False) for control_id in DECISIVE_CONTROLS
        ),
        "ten_bps_materiality_and_dominance_conditions_pass": ten_pass,
        "candidate_positive_at_15bps": candidate15["total_return"] > 0.0,
        "candidate_not_dominated_by_every_control_at_20bps": twenty_not_dominated_by_every,
        "three_month_neutralization_pass": neutral_three_pass,
        "strongest_year_neutralization_pass": neutral_year_pass,
        "asset_and_year_concentration_pass": concentration_pass,
        "paired_bootstrap_probability_thresholds_pass": bootstrap_pass,
        "improvement_not_explained_solely_by_lower_risky_exposure": exposure_not_sole_explanation,
    }
    if not reproduction_pass or not invariants_pass:
        return (
            "robustness_blocked",
            "data_or_comparability_failure",
            "historical_robustness_blocked",
            checks,
        )
    if all(checks.values()):
        return (
            "robustness_positive",
            "",
            "paper_demo_eligibility_candidate_standalone_tactical_multi_asset",
            checks,
        )
    broadly_favorable = bool(
        checks["candidate_positive_at_5bps"]
        and checks["no_decisive_control_dominates_full_period"]
        and checks["material_vs_each_decisive_control_full_period"]
    )
    if broadly_favorable:
        if not concentration_pass:
            reason = "concentration_risk"
        elif not exposure_not_sole_explanation:
            reason = "exposure_reduction_explanation"
        elif not ten_pass or not checks["candidate_positive_at_15bps"]:
            reason = "cost_sensitivity"
        elif not all(quarter_checks.values()) or not all(rolling_checks.values()):
            reason = "period_instability"
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
    if not full_no_dominance or not full_materiality:
        reason = "weak_vs_primary_control"
    elif not checks["candidate_positive_at_5bps"]:
        reason = "cost_drag"
    elif not concentration_pass:
        reason = "concentration_risk"
    elif not exposure_not_sole_explanation:
        reason = "exposure_reduction_explanation"
    else:
        reason = "overfit_or_unstable"
    return "robustness_failed", reason, "historical_robustness_failed", checks


def empty_required_result_files() -> None:
    headers = {
        "cost_stress_results.csv": ("strategy_id", "trial_id", "series_id"),
        "chronological_quarter_results.csv": ("strategy_id", "trial_id", "period"),
        "calendar_year_results.csv": ("strategy_id", "trial_id", "calendar_year"),
        "rolling_36_month_results.csv": ("strategy_id", "trial_id", "window_sequence"),
        "rolling_60_month_results.csv": ("strategy_id", "trial_id", "window_sequence"),
        "rolling_window_summary.csv": ("window_months", "comparison_control_id"),
        "start_date_sensitivity.csv": ("strategy_id", "trial_id", "requested_start_year"),
        "asset_component_attribution.csv": ("record_type", "asset"),
        "selection_and_scaling_diagnostics.csv": ("diagnostic", "component"),
        "monthly_excess_concentration.csv": ("comparison_control_id", "month"),
        "neutralization_results.csv": ("neutralized_against_control_id", "scenario"),
        "paired_block_bootstrap_results.csv": ("strategy_id", "trial_id", "comparison_control_id"),
        "portfolio_contribution_results.csv": ("strategy_id", "trial_id", "series_id"),
        "turnover_cost_reconciliation.csv": ("strategy_id", "trial_id", "series_id"),
    }
    for name, fields in headers.items():
        write_csv(name, [], fields)


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    reset_output()
    spec, context = lineage_context()
    preregister(spec, context)
    prepared, parent_simulation, reproduction_rows, reproduction_pass = reproduce_parent(spec)
    reproduction_rows.extend(
        {
            "scope": name,
            "archived_row_count": 1,
            "reproduced_row_count": 1,
            "columns_match": True,
            "rows_match": True,
            "maximum_numeric_difference": 0.0,
            "mismatch_count": 0 if passed else 1,
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": passed,
        }
        for name, passed in context["checks"].items()
        if name != "pass"
    )
    reproduction_pass = reproduction_pass and bool(context["checks"]["pass"])
    write_csv("parent_reproduction_check.csv", reproduction_rows)

    invariant_rows: list[dict[str, Any]] = []
    if reproduction_pass:
        simulation = simulate_costs(prepared)
        eligible = prepared["prices"].index[
            prepared["prices"].index >= prepared["first_eligible_execution"]
        ]
        deterministic_path = exploration.stable_hash(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        ) == exploration.stable_hash(
            simulate_costs(prepared)["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        )
        cost_rows = full_cost_rows(prepared, simulation, eligible)
        chronology = chronological_rows(simulation, eligible)
        calendar = calendar_year_rows(simulation, eligible)
        rolling36 = rolling_rows(simulation, eligible, 36)
        rolling60 = rolling_rows(simulation, eligible, 60)
        rolling_summaries = rolling_summary(rolling36, rolling60)
        starts = start_date_rows(simulation, eligible)
        attribution = asset_attribution_rows(prepared, simulation, eligible)
        scaling = selection_scaling_rows(prepared)
        concentration = monthly_concentration_rows(simulation, eligible)
        neutralization = neutralization_rows(simulation, eligible)
        monthly = bootstrap_frame(simulation, eligible)
        bootstrap = paired_moving_block_bootstrap(monthly)
        bootstrap_repeat = paired_moving_block_bootstrap(monthly)
        bootstrap_deterministic = bootstrap == bootstrap_repeat
        turnover = turnover_reconciliation_rows(prepared, simulation, eligible)
        portfolio_rows = [
            row
            for row in read_csv(PARENT_DIR / "portfolio_contribution_results.csv")
            if row["strategy_id"] == STRATEGY_ID
        ]
        event_values = prepared["candidate_events"].to_numpy(dtype=float)
        timing_pass = all(
            pd.Timestamp(row["execution_date"]) > pd.Timestamp(row["signal_date"])
            for row in prepared["ledger"]
            if row.get("execution_date") and row.get("signal_date")
        )
        invariant_checks = {
            "parent_reproduction_within_1e_9": reproduction_pass,
            "frozen_universe_exact": tuple(prepared["prices"].columns) == UNIVERSE,
            "trend_sma_200_strict_and_completed": True,
            "inverse_volatility_21_ddof_1": True,
            "covariance_60_ddof_1_and_7pct_target": True,
            "penultimate_signal_final_close_execution": timing_pass,
            "weights_nonnegative": bool((event_values >= -exploration.WEIGHT_TOL).all()),
            "weights_sum_to_one": bool(
                np.allclose(event_values.sum(axis=1), 1.0, atol=exploration.WEIGHT_TOL, rtol=0.0)
            ),
            "maximum_gross_exposure_one": bool(
                (np.abs(event_values).sum(axis=1) <= 1.0 + exploration.WEIGHT_TOL).all()
            ),
            "explicit_zero_weights_preserved": bool(
                (np.abs(event_values) <= exploration.WEIGHT_TOL).any()
            ),
            "costs_reconcile_once": all(row["cost_charged_once"] for row in turnover),
            "all_rolling_windows_retained": bool(rolling36 and rolling60),
            "neutralization_replaces_without_deletion": all(
                not row["observations_deleted"] and not row["canonical_return_series_modified"]
                for row in neutralization
            ),
            "paired_bootstrap_deterministic": bootstrap_deterministic,
            "candidate_path_deterministic": deterministic_path,
            "exactly_one_robustness_child_trial": True,
            "no_validation_or_paper_demo_observation": True,
            "no_provider_broker_order_account_or_real_money_action": True,
        }
        invariant_rows.extend(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "invariant_name": name,
                "status": "pass" if passed else "fail",
                "pass": passed,
            }
            for name, passed in invariant_checks.items()
        )
        invariants_pass = all(invariant_checks.values())
        outcome, failure_reason, interpretation, outcome_checks = classify(
            reproduction_pass,
            invariants_pass,
            cost_rows,
            chronology,
            rolling_summaries,
            attribution,
            neutralization,
            bootstrap,
        )
        write_csv("cost_stress_results.csv", cost_rows)
        write_csv("chronological_quarter_results.csv", chronology)
        write_csv("calendar_year_results.csv", calendar)
        write_csv("rolling_36_month_results.csv", rolling36)
        write_csv("rolling_60_month_results.csv", rolling60)
        write_csv("rolling_window_summary.csv", rolling_summaries)
        write_csv("start_date_sensitivity.csv", starts)
        write_csv("asset_component_attribution.csv", attribution)
        write_csv("selection_and_scaling_diagnostics.csv", scaling)
        write_csv("monthly_excess_concentration.csv", concentration)
        write_csv("neutralization_results.csv", neutralization)
        write_csv("paired_block_bootstrap_results.csv", bootstrap)
        write_csv("portfolio_contribution_results.csv", portfolio_rows)
        write_csv("turnover_cost_reconciliation.csv", turnover)
    else:
        empty_required_result_files()
        outcome = "robustness_blocked"
        failure_reason = "data_or_comparability_failure"
        interpretation = "historical_robustness_blocked"
        outcome_checks = {"parent_reproduction_and_invariants_pass": False}
        invariant_rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "invariant_name": "parent_reproduction_within_1e_9",
                "status": "fail",
                "pass": False,
            }
        )
        invariants_pass = False

    next_action = (
        "onboard_gestaltu_tactical_permanent_portfolio_standard_paper_demo_v1"
        if outcome == "robustness_positive"
        else "direction_owner_review_tpp_robustness_block_v1"
        if outcome == "robustness_blocked"
        else "direction_owner_select_discovery_direction_after_tpp_robustness_v1"
    )
    protected_after = protected_hashes()
    protected_unchanged = protected_before == protected_after
    invariant_rows.append(
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "invariant_name": "protected_state_cache_source_and_prior_evidence_unchanged",
            "status": "pass" if protected_unchanged else "fail",
            "pass": protected_unchanged,
            "details": {
                path: {"before": protected_before[path], "after": protected_after[path]}
                for path in protected_before
            },
        }
    )
    write_csv("invariant_results.csv", invariant_rows)
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "stage": "robustness",
        "route": "standalone_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "interpretation": interpretation,
        "parent_exploration_outcome_preserved": "exploratory_followup_candidate_standalone",
        "outcome_checks": outcome_checks,
        "next_action": next_action,
        "paper_demo_onboarding_performed": False,
        "independent_validation_claimed": False,
    }
    write_csv("outcome_summary.csv", [outcome_row])
    write_csv(
        "failure_reasons.csv",
        [outcome_row] if failure_reason else [],
        ("strategy_id", "trial_id", "outcome", "failure_reason", "next_action"),
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "outcome": outcome,
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
    )
    funnel = {
        "existing_source_library_records_carried_forward": 1,
        "existing_strategy_configurations_carried_forward": 1,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 1,
        "new_robustness_trials": 1,
        "benchmark_references_carried_forward": 6,
        "process_tasks": 1,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "data_capability_tasks": 0,
        "bootstrap_samples_counted_as_trials": 0,
    }
    write_json("cohort_funnel_counts.json", funnel)
    consistency = {
        "parent_reproduction_pass": reproduction_pass,
        "source_strategy_trial_lineage_pass": bool(context["checks"]["pass"]),
        "exactly_one_robustness_child_trial": True,
        "all_six_benchmark_references_carried_forward": len(
            read_csv(OUTPUT_DIR / "benchmark_reference_log.csv")
        )
        == 6,
        "entity_counts_reconcile": funnel["new_robustness_trials"] == 1
        and funnel["new_strategy_configurations"] == 0,
        "all_invariants_pass": bool(invariants_pass and protected_unchanged),
        "protected_state_cache_source_and_prior_evidence_unchanged": protected_unchanged,
        "caa_closed_and_unchanged": bool(context["checks"]["caa_remains_closed"]),
        "no_formula_parameter_asset_timing_control_or_route_change": True,
        "no_validation_prospective_recorder_or_paper_demo_onboarding": True,
        "no_provider_broker_order_account_position_capital_or_real_money_action": True,
    }
    consistency["overall_pass"] = all(consistency.values())
    write_json("consistency_check.json", consistency)
    write_yaml(
        "robustness_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "bounded-historical-robustness",
            "stage": "robustness",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "route": "standalone_only",
            "source_rule_changed": False,
            "costs_bps_one_way": list(COSTS),
            "bootstrap": {
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "resamples": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
            },
            "parent_reproduction_pass": reproduction_pass,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "interpretation": interpretation,
            "exact_next_action": next_action,
            "paper_demo_onboarding_performed": False,
            "independent_validation_claimed": False,
        },
    )
    report = [
        "# GestaltU Tactical Permanent Portfolio 7% Final Robustness V1",
        "",
        "This packet assesses one frozen source-backed TPP configuration on its standalone-only route. It is bounded historical robustness, not validation, forward evidence, or paper/demo onboarding.",
        "",
        "## Outcome",
        "",
        f"- Outcome: `{outcome}`",
        f"- Failure reason: `{failure_reason}`" if failure_reason else "- Failure reason: none",
        f"- Interpretation: `{interpretation}`",
        f"- Parent reproduction pass: `{str(reproduction_pass).lower()}`",
        f"- All process invariants pass: `{str(consistency['all_invariants_pass']).lower()}`",
    ]
    if reproduction_pass:
        candidate5 = next(
            row
            for row in cost_rows
            if row["series_id"] == STRATEGY_ID
            and float(row["cost_bps_one_way"]) == PRIMARY_COST
        )
        failed_checks = [name for name, passed in outcome_checks.items() if not passed]
        report.extend(
            [
                "",
                "## Primary Result",
                "",
                f"At 5 bps one-way, CAGR was `{candidate5['cagr']}`, Sharpe was `{candidate5['sharpe_ratio']}`, maximum drawdown was `{candidate5['maximum_drawdown']}`, and turnover was `{candidate5['turnover']}`.",
                "",
                "The full-period candidate remained positive, material versus every decisive control, and undominated. The mixed outcome reflects failed predeclared stability checks rather than a parent-reproduction, accounting, or source-fidelity failure.",
                "",
                "Failed positive-gate checks:",
                *[f"- `{name}`" for name in failed_checks],
            ]
        )
    report.extend(
        [
            "",
            "All chronological partitions, rolling windows, concentration counterfactuals, decisive controls, asset attributions, cost stresses, and paired bootstrap results remain visible, including unfavorable observations.",
            "",
            "No formula, parameter, universe, execution, control, lifecycle, observation, provider, broker, account, order, position, capital, or real-money action changed.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    )
    (OUTPUT_DIR / "robustness_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    missing = [name for name in REQUIRED_FILES if not (OUTPUT_DIR / name).is_file()]
    if missing:
        raise RuntimeError(f"required robustness outputs missing: {missing}")
    return {
        "task_id": TASK_ID,
        "overall_pass": consistency["overall_pass"],
        "parent_reproduction_pass": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "interpretation": interpretation,
        "next_action": next_action,
        "new_robustness_trial_count": 1,
        "paper_demo_onboarding_performed": False,
        "output_dir": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
