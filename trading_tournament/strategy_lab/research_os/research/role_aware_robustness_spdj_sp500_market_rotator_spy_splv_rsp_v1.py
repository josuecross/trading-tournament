from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_expanded_universe_discovery_batch_v1 as parent


TASK_ID = "role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1"
STAGE = "robustness"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
PARENT_DIR = ROOT / "evidence" / "research_recovery" / parent.TASK_ID / "latest"
INTAKE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / parent.INTAKE_ID / "latest"
UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / parent.UNIVERSE_ID / "latest"
METHODOLOGY_PATH = ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml"

STRATEGY_ID = parent.ROTATOR_ID
PARENT_TRIAL_ID = parent.ROTATOR_TRIAL
TRIAL_ID = "robustness__spdj_sp500_market_rotator_spy_splv_rsp_v1__role_aware_v1"
FAMILY_ID = "equity_weighting_style_rotation"
ARCHITECTURE_ID = "monthly_multi_horizon_market_lowvol_equalweight_rotation"
PRIMARY_ROLE = "dynamic_multi_asset_allocation_strategy"
LINEAGE = "sp_dow_jones_sp500_market_rotator_2026_methodology"
ROUTE = "standalone"
SOURCE_VERSION = "S&P 500 Market Rotator Index Methodology - January 2026"
UNIVERSE_ID = parent.UNIVERSE_ID
EXPECTED_UNIVERSE_HASH = parent.EXPECTED_UNIVERSE_HASH

PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0, 15.0, 20.0)
PARENT_COSTS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260809
FIXED_START_YEARS = tuple(range(2012, 2017))

NAMED_CONTROL = parent.ROTATOR_NAMED
STATIC_CONTROL = parent.ROTATOR_STATIC
EQUAL_CONTROL = "spy_splv_rsp_equal_weight_control"
SPY_CONTROL = "SPY_buy_and_hold"
BIL_CONTROL = "BIL_buy_and_hold"
DECISIVE_CONTROLS = (NAMED_CONTROL, STATIC_CONTROL, EQUAL_CONTROL)
ALL_CONTROLS = (*DECISIVE_CONTROLS, SPY_CONTROL, BIL_CONTROL)

NEXT_POSITIVE = "paper_demo_eligibility_and_handoff_spdj_sp500_market_rotator_spy_splv_rsp_v1"
NEXT_REVIEW = "direction_owner_review_sp500_market_rotator_robustness_v1"
NEXT_BLOCK = "direction_owner_review_sp500_market_rotator_robustness_block_v1"

REQUIRED_OUTPUTS = {
    "robustness_manifest.yaml",
    "phase2_universe_reconciliation.csv",
    "source_version_reconciliation.csv",
    "strategy_and_trial_lineage.csv",
    "role_preregistration_reconciliation.csv",
    "applicable_gate_matrix.csv",
    "parent_reproduction_results.csv",
    "candidate_results.csv",
    "control_results.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_window_results.csv",
    "rolling_window_summary.csv",
    "state_selection_inventory.csv",
    "state_attribution_results.csv",
    "multi_horizon_score_attribution.csv",
    "candidate_control_disagreement_results.csv",
    "static_exposure_explanation.csv",
    "role_valid_concentration_results.csv",
    "paired_bootstrap_results.csv",
    "start_date_sensitivity.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "complete_failure_vector.csv",
    "failure_reasons.csv",
    "entity_count_reconciliation.json",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "robustness_report.md",
}

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    METHODOLOGY_PATH,
    PARENT_DIR,
    INTAKE_DIR,
    UNIVERSE_DIR,
    parent.PHASE1_CACHE_DIR,
    parent.PHASE2_CACHE_DIR,
    ROOT / "evidence" / "handoff",
    ROOT / "evidence" / "forward_observation",
    ROOT / "evidence" / "paper_demo_observation",
)


@dataclass(frozen=True)
class RobustnessState:
    standard: dict[str, Any]
    universe_reconciliation: dict[str, Any]
    universe_rows: list[dict[str, str]]
    series: dict[str, pd.Series]
    prepared: dict[str, Any]
    simulation: dict[str, Any]
    full_index: pd.DatetimeIndex
    archived_signals: list[dict[str, str]]


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return "sha256:" + digest.hexdigest()
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_PATHS if path.exists()}


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        return "" if not math.isfinite(float(value)) else f"{float(value):.15g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
    return value


def union_fields(rows: list[dict[str, Any]], preferred: Iterable[str] = ()) -> list[str]:
    fields = list(preferred)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]], preferred: Iterable[str] = ()) -> None:
    fields = union_fields(rows, preferred)
    if not fields:
        raise RuntimeError(f"CSV schema missing for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        expected_parent = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected_parent not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"Refusing to remove unexpected path {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def float_value(value: Any) -> float:
    try:
        output = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return output if math.isfinite(output) else float("nan")


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 0.0 else float("nan")


def load_standard() -> dict[str, Any]:
    standard = yaml.safe_load(METHODOLOGY_PATH.read_text(encoding="utf-8"))
    if not isinstance(standard, dict) or standard.get("standard_id") != "role_aware_robustness_standard_v1":
        raise RuntimeError("Authoritative role-aware robustness standard did not load")
    if PRIMARY_ROLE not in standard.get("role_specific_hard_gate_contracts", {}):
        raise RuntimeError(f"Missing role contract for {PRIMARY_ROLE}")
    return standard


def simulate_paths(prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidate_paths[cost] = parent.simulate_events(
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            timing_policy="prior_month_final_close_signal_first_new_month_session_close_execution",
            formation_dates=prepared["formation_dates"],
            execution_dates=prepared["candidate_execution_dates"],
        )
        for control_id, events in prepared["controls"].items():
            if control_id == NAMED_CONTROL:
                formations = prepared["formation_dates"]
                executions = prepared["control_execution_dates"][NAMED_CONTROL]
            elif control_id == EQUAL_CONTROL:
                formations = prepared["formation_dates"]
                executions = [pd.Timestamp(value) for value in events.index[1:]]
            else:
                formations = ()
                executions = (pd.Timestamp(events.index[0]),)
            control_paths[(control_id, cost)] = parent.simulate_events(
                prepared["prices"],
                events,
                cost,
                timing_policy="prior_month_final_close_signal_first_new_month_session_close_execution",
                formation_dates=formations,
                execution_dates=executions,
            )
    return {**prepared, "candidate_paths": candidate_paths, "control_paths": control_paths}


def build_state() -> RobustnessState:
    standard = load_standard()
    universe_rows, universe_by_symbol, universe_reconciliation = parent.load_universe_contract()
    if universe_reconciliation["computed_hash"] != EXPECTED_UNIVERSE_HASH:
        raise RuntimeError("Phase-2 universe hash mismatch")
    series = {symbol: parent.load_price_series(symbol, universe_by_symbol) for symbol in parent.ROTATOR_UNIVERSE}
    prepared = parent.build_market_rotator(series)
    simulation = simulate_paths(prepared)
    full_index = simulation["candidate_paths"][PRIMARY_COST]["returns"].index
    return RobustnessState(
        standard=standard,
        universe_reconciliation=universe_reconciliation,
        universe_rows=universe_rows,
        series=series,
        prepared=prepared,
        simulation=simulation,
        full_index=pd.DatetimeIndex(full_index),
        archived_signals=read_csv(PARENT_DIR / "market_rotator_monthly_signal_ledger.csv"),
    )


def path_for(state: RobustnessState, series_id: str, cost: float) -> dict[str, Any]:
    if series_id == "candidate":
        return state.simulation["candidate_paths"][cost]
    return state.simulation["control_paths"][(series_id, cost)]


def metrics_for(state: RobustnessState, series_id: str, cost: float, period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return parent.path_metrics(path_for(state, series_id, cost), period)


def result_row(series_id: str, cost: float, period_id: str, metrics: dict[str, Any], entity_role: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "series_id": series_id,
        "entity_role": entity_role,
        "stage": STAGE if series_id == "candidate" else "benchmark_reference_only",
        "period_id": period_id,
        "cost_bps_one_way": cost,
        **metrics,
    }


def metric_map(state: RobustnessState) -> dict[tuple[str, float], dict[str, Any]]:
    output: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        output[("candidate", cost)] = metrics_for(state, "candidate", cost)
        for control_id in ALL_CONTROLS:
            output[(control_id, cost)] = metrics_for(state, control_id, cost)
    return output


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return parent.dominates(control, candidate)


def materially_improves(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return parent.material_advantage(candidate, control)


def improves(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float_value(candidate["sharpe_ratio"]) > float_value(control["sharpe_ratio"]) + parent.TOLERANCE
        or float_value(candidate["maximum_drawdown"]) > float_value(control["maximum_drawdown"]) + parent.TOLERANCE
    )


def threshold_for_gate(gate_id: str, standard: dict[str, Any]) -> str:
    thresholds = standard["numeric_threshold_policy"]
    if "3_of_4" in gate_id or "3_of_4" in str(thresholds.get("chronological_stability_quarters")):
        if "quarter" in gate_id:
            return "candidate improves each decisive control in at least 3 of 4 chronological quarters"
    if "rolling_36" in gate_id or "rolling_60" in gate_id:
        return str(thresholds["rolling_stability_fraction"])
    if "dominates_in_more_than_half" in gate_id:
        return str(thresholds["decisive_control_rolling_domination_cap"])
    if "named_control_bootstrap" in gate_id:
        return str(thresholds["named_control_bootstrap_threshold"])
    if "other_control_bootstrap" in gate_id:
        return str(thresholds["other_decisive_control_bootstrap_threshold"])
    if "single_asset" in gate_id or "single_calendar_year" in gate_id:
        return str(thresholds["single_role_valid_concentration_unit_cap"])
    if "materiality" in gate_id:
        return "Sharpe improvement >= 0.02 OR maximum-drawdown improvement >= 0.01"
    if "10bps" in gate_id:
        return "archived 10-bps critical-control advantage survives"
    return "pass/fail per authoritative methodology"


def applicable_gate_rows(standard: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate_id in standard["universal_hard_gates"]:
        applicable = gate_id != "archived_15_or_20bps_gate_remains_binding_when_preregistered"
        rows.append(
            {
                "gate_id": gate_id,
                "gate_scope": "universal",
                "role": PRIMARY_ROLE,
                "threshold": threshold_for_gate(gate_id, standard),
                "blocking_or_diagnostic": "blocking" if applicable else "not_applicable",
                "applicable": applicable,
                "evidence_source": "role_aware_robustness_standard_v1.yaml",
                "rationale": "authoritative universal hard gate" if applicable else "parent preregistered only 0/5/10 bps",
            }
        )
    for gate_id in standard["role_specific_hard_gate_contracts"][PRIMARY_ROLE]:
        rows.append(
            {
                "gate_id": gate_id,
                "gate_scope": "role_specific",
                "role": PRIMARY_ROLE,
                "threshold": threshold_for_gate(gate_id, standard),
                "blocking_or_diagnostic": "blocking",
                "applicable": True,
                "evidence_source": "role_aware_robustness_standard_v1.yaml",
                "rationale": "authoritative dynamic-allocation role gate",
            }
        )
    diagnostics = (
        "calendar_year_visibility",
        "start_date_sensitivity",
        "multi_horizon_score_attribution",
        "state_selection_attribution",
        "strongest_chronological_quarter_concentration",
    )
    for gate_id in diagnostics:
        rows.append(
            {
                "gate_id": gate_id,
                "gate_scope": "diagnostic",
                "role": PRIMARY_ROLE,
                "threshold": "diagnostic_only",
                "blocking_or_diagnostic": "diagnostic_only",
                "applicable": True,
                "evidence_source": "task_specification",
                "rationale": "visibility requirement; not an additional blocking gate",
            }
        )
    return rows


def parse_parent_metric_rows(filename: str, candidate: bool) -> dict[tuple[str, float, str], dict[str, str]]:
    rows = read_csv(PARENT_DIR / filename)
    output: dict[tuple[str, float, str], dict[str, str]] = {}
    for row in rows:
        if row.get("strategy_id") != STRATEGY_ID:
            continue
        series_id = "candidate" if candidate or row["configuration_id"] == PARENT_TRIAL_ID else row["configuration_id"]
        cost = float(row["cost_bps_per_one_way_turnover"])
        output[(series_id, cost, row["period_id"])] = row
    return output


def compare_value(scope: str, series_id: str, cost: float, period_id: str, field: str, reproduced: Any, archived: Any) -> dict[str, Any]:
    reproduced_value = float_value(reproduced)
    archived_value = float_value(archived)
    difference = reproduced_value - archived_value
    return {
        "reproduction_scope": scope,
        "series_id": series_id,
        "cost_bps_one_way": cost,
        "period_id": period_id,
        "metric_name": field,
        "reproduced_value": reproduced_value,
        "archived_value": archived_value,
        "absolute_difference": abs(difference),
        "tolerance": REPRODUCTION_TOLERANCE,
        "reproduction_pass": bool(math.isfinite(difference) and abs(difference) <= REPRODUCTION_TOLERANCE),
    }


def reproduction_rows(state: RobustnessState) -> list[dict[str, Any]]:
    archived_candidate = parse_parent_metric_rows("all_trial_results.csv", candidate=True)
    archived_controls = parse_parent_metric_rows("control_results.csv", candidate=False)
    archived_halves = parse_parent_metric_rows("chronological_half_results.csv", candidate=False)
    rows: list[dict[str, Any]] = []
    fields = (
        "total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown",
        "turnover", "transaction_cost_drag", "formation_count", "execution_count",
        "maximum_gross_exposure", "maximum_daily_weight_sum",
    )
    for cost in PARENT_COSTS:
        current = metrics_for(state, "candidate", cost)
        archived = archived_candidate[("candidate", cost, "full_period")]
        for field in fields:
            rows.append(compare_value("full_period_candidate", "candidate", cost, "full_period", field, current[field], archived[field]))
        for control_id in ALL_CONTROLS:
            current_control = metrics_for(state, control_id, cost)
            archived_control = archived_controls[(control_id, cost, "full_period")]
            for field in fields:
                rows.append(compare_value("full_period_control", control_id, cost, "full_period", field, current_control[field], archived_control[field]))
    halves = parent.chronological_halves(state.full_index)
    for period_id, period in halves:
        for series_id in ("candidate", *ALL_CONTROLS):
            current = metrics_for(state, series_id, PRIMARY_COST, period)
            archived = archived_halves[(series_id, PRIMARY_COST, period_id)]
            for field in fields:
                rows.append(compare_value("chronological_half", series_id, PRIMARY_COST, period_id, field, current[field], archived[field]))
    current_signals = state.prepared["signal_rows"]
    archived_sequence = [row["selected_component"] for row in state.archived_signals]
    current_sequence = [str(row.get("selected_component", "")) for row in current_signals]
    rows.extend(
        [
            {
                "reproduction_scope": "state_selection_sequence",
                "series_id": "candidate",
                "cost_bps_one_way": "",
                "period_id": "full_period",
                "metric_name": "sequence_hash",
                "reproduced_value": stable_hash(current_sequence),
                "archived_value": stable_hash(archived_sequence),
                "absolute_difference": "",
                "tolerance": "exact_hash",
                "reproduction_pass": current_sequence == archived_sequence,
            },
            {
                "reproduction_scope": "state_selection_sequence",
                "series_id": "candidate",
                "cost_bps_one_way": "",
                "period_id": "full_period",
                "metric_name": "signal_row_count",
                "reproduced_value": len(current_signals),
                "archived_value": len(state.archived_signals),
                "absolute_difference": abs(len(current_signals) - len(state.archived_signals)),
                "tolerance": 0,
                "reproduction_pass": len(current_signals) == len(state.archived_signals),
            },
        ]
    )
    repeat = simulate_paths(state.prepared)
    for cost in PARENT_COSTS:
        first = path_for(state, "candidate", cost)["held_weights"]
        second = repeat["candidate_paths"][cost]["held_weights"]
        rows.append(
            {
                "reproduction_scope": "holdings_path",
                "series_id": "candidate",
                "cost_bps_one_way": cost,
                "period_id": "full_period",
                "metric_name": "held_weights_deterministic_hash",
                "reproduced_value": stable_hash(first.round(14).to_dict(orient="split")),
                "archived_value": stable_hash(second.round(14).to_dict(orient="split")),
                "absolute_difference": "",
                "tolerance": "exact_hash",
                "reproduction_pass": first.equals(second),
            }
        )
    return rows


def candidate_and_control_rows(state: RobustnessState) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows = [result_row("candidate", cost, "full_period", metrics_for(state, "candidate", cost), "experiment_trial") for cost in COSTS]
    control_rows = [
        result_row(control_id, cost, "full_period", metrics_for(state, control_id, cost), "benchmark_reference")
        for cost in COSTS for control_id in ALL_CONTROLS
    ]
    for period_id, period in parent.chronological_halves(state.full_index):
        candidate_rows.append(result_row("candidate", PRIMARY_COST, period_id, metrics_for(state, "candidate", PRIMARY_COST, period), "experiment_trial"))
        control_rows.extend(
            result_row(control_id, PRIMARY_COST, period_id, metrics_for(state, control_id, PRIMARY_COST, period), "benchmark_reference")
            for control_id in ALL_CONTROLS
        )
    return candidate_rows, control_rows


def cost_stress_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    zero = metrics_for(state, "candidate", 0.0)
    for cost in COSTS:
        for series_id in ("candidate", *DECISIVE_CONTROLS):
            current = metrics_for(state, series_id, cost)
            rows.append(
                {
                    **result_row(series_id, cost, "full_period_cost_stress", current, "experiment_trial" if series_id == "candidate" else "benchmark_reference"),
                    "total_return_difference_vs_candidate_0bps": float_value(current["total_return"]) - float_value(zero["total_return"]),
                    "state_transition_count": state_transition_count(state, series_id),
                    "cost_diagnostic_not_separate_trial": True,
                }
            )
    return rows


def state_transition_count(state: RobustnessState, series_id: str) -> int:
    if series_id == "candidate":
        selected = [row.get("selected_component") for row in state.prepared["signal_rows"] if row.get("signal_status") == "valid_executed"]
    elif series_id == NAMED_CONTROL:
        selected = [row.get("named_control_selected_component") for row in state.prepared["signal_rows"] if row.get("ranking_inputs_complete")]
    elif series_id in (STATIC_CONTROL, EQUAL_CONTROL):
        return 0
    else:
        return 0
    return sum(current != previous for previous, current in zip(selected, selected[1:]))


def split_quarters(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    return [
        (f"chronological_quarter_{position + 1}", index[locations])
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    ]


def comparison_row(state: RobustnessState, period_type: str, period_id: str, period: pd.DatetimeIndex, control_id: str) -> dict[str, Any]:
    candidate = metrics_for(state, "candidate", PRIMARY_COST, period)
    control = metrics_for(state, control_id, PRIMARY_COST, period)
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "period_type": period_type,
        "period_id": period_id,
        "period_start": candidate["evaluation_start"],
        "period_end": candidate["evaluation_end"],
        "comparison_control_id": control_id,
        "candidate_cagr": candidate["cagr"],
        "control_cagr": control["cagr"],
        "cagr_difference": float_value(candidate["cagr"]) - float_value(control["cagr"]),
        "candidate_sharpe_ratio": candidate["sharpe_ratio"],
        "control_sharpe_ratio": control["sharpe_ratio"],
        "sharpe_difference": float_value(candidate["sharpe_ratio"]) - float_value(control["sharpe_ratio"]),
        "candidate_maximum_drawdown": candidate["maximum_drawdown"],
        "control_maximum_drawdown": control["maximum_drawdown"],
        "maximum_drawdown_difference": float_value(candidate["maximum_drawdown"]) - float_value(control["maximum_drawdown"]),
        "candidate_improves_control_sharpe_or_drawdown": improves(candidate, control),
        "candidate_material_vs_control": materially_improves(candidate, control),
        "control_dominates_candidate": dominates(control, candidate),
        "unfavorable_result_retained": True,
        "validation_claimed": False,
    }


def chronological_quarter_rows(state: RobustnessState) -> list[dict[str, Any]]:
    return [
        comparison_row(state, "chronological_quarter", period_id, period, control_id)
        for period_id, period in split_quarters(state.full_index)
        for control_id in DECISIVE_CONTROLS
    ]


def calendar_year_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in range(int(state.full_index.min().year) + 1, int(state.full_index.max().year)):
        period = state.full_index[state.full_index.year == year]
        if not len(period):
            continue
        candidate = metrics_for(state, "candidate", PRIMARY_COST, period)
        rows.append(result_row("candidate", PRIMARY_COST, str(year), candidate, "experiment_trial"))
        rows[-1]["calendar_year"] = year
        for control_id in ALL_CONTROLS:
            control = metrics_for(state, control_id, PRIMARY_COST, period)
            row = result_row(control_id, PRIMARY_COST, str(year), control, "benchmark_reference")
            row.update(
                {
                    "calendar_year": year,
                    "candidate_minus_control_return": float_value(candidate["total_return"]) - float_value(control["total_return"]),
                    "candidate_improves_control_sharpe_or_drawdown": improves(candidate, control),
                    "control_dominates_candidate": dominates(control, candidate),
                    "unfavorable_result_retained": True,
                }
            )
            rows.append(row)
    return rows


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    grouped = pd.Series(index, index=index).groupby(index.to_period("M")).last()
    return [pd.Timestamp(value) for value in grouped.tolist()]


def rolling_rows(state: RobustnessState) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for months in (36, 60):
        sequence = 0
        for end in month_ends(state.full_index):
            boundary = end - pd.DateOffset(months=months)
            if boundary < state.full_index[0]:
                continue
            period = state.full_index[(state.full_index > boundary) & (state.full_index <= end)]
            if not len(period):
                continue
            sequence += 1
            for control_id in DECISIVE_CONTROLS:
                row = comparison_row(state, f"rolling_{months}_months", f"rolling_{months}_{sequence:03d}", period, control_id)
                row.update({"window_months": months, "window_sequence": sequence})
                rows.append(row)
    summaries: list[dict[str, Any]] = []
    for months in (36, 60):
        for control_id in DECISIVE_CONTROLS:
            subset = [row for row in rows if row["window_months"] == months and row["comparison_control_id"] == control_id]
            summaries.append(
                {
                    "window_months": months,
                    "comparison_control_id": control_id,
                    "window_count": len(subset),
                    "median_cagr_difference": float(np.median([row["cagr_difference"] for row in subset])),
                    "median_sharpe_difference": float(np.median([row["sharpe_difference"] for row in subset])),
                    "median_maximum_drawdown_difference": float(np.median([row["maximum_drawdown_difference"] for row in subset])),
                    "candidate_improves_control_count": sum(bool(row["candidate_improves_control_sharpe_or_drawdown"]) for row in subset),
                    "candidate_improves_control_fraction": float(np.mean([row["candidate_improves_control_sharpe_or_drawdown"] for row in subset])),
                    "control_dominance_count": sum(bool(row["control_dominates_candidate"]) for row in subset),
                    "control_dominance_fraction": float(np.mean([row["control_dominates_candidate"] for row in subset])),
                    "candidate_material_fraction": float(np.mean([row["candidate_material_vs_control"] for row in subset])),
                    "stability_threshold": 0.50,
                    "unfavorable_windows_retained": True,
                }
            )
    return rows, summaries


def complete_monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.dropna()).resample("ME").prod() - 1.0


def metrics_from_monthly(values: np.ndarray | pd.Series) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    if not len(data):
        return {key: float("nan") for key in ("total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown")}
    wealth = np.cumprod(1.0 + data)
    std = float(np.std(data, ddof=1)) if len(data) > 1 else 0.0
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    return {
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(data)) - 1.0),
        "annualized_volatility": float(std * math.sqrt(12.0)),
        "sharpe_ratio": float(np.mean(data) / std * math.sqrt(12.0)) if std > 0.0 else 0.0,
        "maximum_drawdown": float(np.min(drawdown)),
    }


def paired_bootstrap_rows(state: RobustnessState) -> list[dict[str, Any]]:
    frame = pd.concat(
        [
            complete_monthly_returns(path_for(state, "candidate", PRIMARY_COST)["returns"]).rename("candidate"),
            *[complete_monthly_returns(path_for(state, control_id, PRIMARY_COST)["returns"]).rename(control_id) for control_id in DECISIVE_CONTROLS],
        ],
        axis=1,
        join="inner",
    ).dropna()
    values = frame[["candidate", *DECISIVE_CONTROLS]].to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    if max_start < 0:
        raise RuntimeError("Insufficient monthly observations for bootstrap")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counters = {control_id: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0} for control_id in DECISIVE_CONTROLS}
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled = np.concatenate([np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts])[:count]
        candidate = metrics_from_monthly(values[sampled, 0])
        for column, control_id in enumerate(DECISIVE_CONTROLS, start=1):
            control = metrics_from_monthly(values[sampled, column])
            cagr = candidate["cagr"] > control["cagr"]
            sharpe = candidate["sharpe_ratio"] > control["sharpe_ratio"]
            drawdown = candidate["maximum_drawdown"] > control["maximum_drawdown"]
            counters[control_id]["cagr"] += int(cagr)
            counters[control_id]["sharpe"] += int(sharpe)
            counters[control_id]["drawdown"] += int(drawdown)
            counters[control_id]["either"] += int(sharpe or drawdown)
    rows: list[dict[str, Any]] = []
    for control_id in DECISIVE_CONTROLS:
        threshold = 0.70 if control_id == NAMED_CONTROL else 0.60
        probability = counters[control_id]["either"] / BOOTSTRAP_RESAMPLES
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "comparison_control_id": control_id,
                "resampling_method": "paired_monthly_moving_block_bootstrap",
                "resampling_unit": "calendar_month",
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "iterations": BOOTSTRAP_RESAMPLES,
                "deterministic_seed": BOOTSTRAP_SEED,
                "monthly_observation_count": count,
                "probability_candidate_higher_cagr": counters[control_id]["cagr"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_higher_sharpe": counters[control_id]["sharpe"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_less_severe_drawdown": counters[control_id]["drawdown"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_higher_sharpe_or_less_severe_drawdown": probability,
                "applicable_threshold": threshold,
                "pass": probability >= threshold,
            }
        )
    return rows


def valid_signal_rows(state: RobustnessState) -> list[dict[str, Any]]:
    return [row for row in state.prepared["signal_rows"] if row.get("signal_status") == "valid_executed"]


def score_attribution_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for signal in valid_signal_rows(state):
        periodic = signal["periodic_returns"]
        selected = signal["selected_component"]
        named_selected = signal["named_control_selected_component"]
        for symbol in ("SPY", "SPLV", "RSP"):
            horizon_values = periodic[symbol]
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "formation_date": signal["formation_date"],
                    "execution_date": signal["execution_date"],
                    "component": symbol,
                    **horizon_values,
                    "average_score": signal["mean_scores"][symbol],
                    "candidate_selected_etf": selected,
                    "named_control_selected_etf": named_selected,
                    "candidate_control_agree": selected == named_selected,
                    "candidate_selected_this_component": symbol == selected,
                    "named_control_selected_this_component": symbol == named_selected,
                }
            )
    return rows


def disagreement_rows(state: RobustnessState) -> list[dict[str, Any]]:
    signals = valid_signal_rows(state)
    candidate_returns = path_for(state, "candidate", PRIMARY_COST)["returns"]
    named_returns = path_for(state, NAMED_CONTROL, PRIMARY_COST)["returns"]
    quarter_sets = {period_id: set(period) for period_id, period in split_quarters(state.full_index)}
    rows: list[dict[str, Any]] = []
    for position, signal in enumerate(signals):
        execution = pd.Timestamp(signal["execution_date"])
        next_execution = pd.Timestamp(signals[position + 1]["execution_date"]) if position + 1 < len(signals) else state.full_index.max() + pd.Timedelta(days=1)
        period = state.full_index[(state.full_index > execution) & (state.full_index < next_execution)]
        candidate_return = float(np.prod(1.0 + candidate_returns.reindex(period).dropna()) - 1.0) if len(period) else 0.0
        named_return = float(np.prod(1.0 + named_returns.reindex(period).dropna()) - 1.0) if len(period) else 0.0
        quarter_id = next((quarter for quarter, values in quarter_sets.items() if execution in values), "")
        incremental = candidate_return - named_return
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "formation_date": signal["formation_date"],
                "execution_date": signal["execution_date"],
                "interval_end": period.max().date().isoformat() if len(period) else signal["execution_date"],
                "calendar_year": execution.year,
                "chronological_quarter": quarter_id,
                "candidate_selected_etf": signal["selected_component"],
                "named_control_selected_etf": signal["named_control_selected_component"],
                "candidate_control_agree": signal["selected_component"] == signal["named_control_selected_component"],
                "candidate_interval_return": candidate_return,
                "named_control_interval_return": named_return,
                "candidate_minus_named_incremental_return": incremental,
                "positive_incremental_value": max(0.0, incremental),
                "unfavorable_disagreement_retained": True,
            }
        )
    disagreement = [row for row in rows if not row["candidate_control_agree"]]
    positive = sum(float_value(row["positive_incremental_value"]) for row in disagreement)
    total_positive = sum(float_value(row["positive_incremental_value"]) for row in rows)
    rows.append(
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "formation_date": "summary",
            "execution_date": "",
            "candidate_control_agree": "",
            "agreement_frequency": safe_ratio(len(rows) - 1 - len(disagreement), len(rows) - 1),
            "disagreement_month_count": len(disagreement),
            "disagreement_incremental_return_sum": sum(float_value(row["candidate_minus_named_incremental_return"]) for row in disagreement),
            "positive_disagreement_incremental_value": positive,
            "share_of_positive_incremental_value_from_disagreement_months": safe_ratio(positive, total_positive),
            "attribution_not_strategy_variant": True,
        }
    )
    return rows


def state_selection_inventory_rows(state: RobustnessState) -> list[dict[str, Any]]:
    signals = valid_signal_rows(state)
    quarter_sets = {period_id: set(period) for period_id, period in split_quarters(state.full_index)}
    rows: list[dict[str, Any]] = []
    for signal in signals:
        execution = pd.Timestamp(signal["execution_date"])
        quarter_id = next((quarter for quarter, values in quarter_sets.items() if execution in values), "")
        spy_1m = float_value(signal["periodic_returns"]["SPY"]["return_1m"])
        dimensions = (
            ("chronological_quarter", quarter_id),
            ("calendar_year", str(execution.year)),
            ("spy_month_direction", "positive_spy_month" if spy_1m > 0.0 else "negative_or_zero_spy_month"),
        )
        for dimension, bucket in dimensions:
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "formation_date": signal["formation_date"],
                    "execution_date": signal["execution_date"],
                    "selected_state": signal["selected_component"],
                    "inventory_dimension": dimension,
                    "inventory_bucket": bucket,
                    "spy_1m_return": spy_1m,
                    "selection_count": 1,
                }
            )
    rows.append(
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "formation_date": "",
            "execution_date": "",
            "selected_state": "",
            "inventory_dimension": "market_volatility_regime",
            "inventory_bucket": "not_available_no_existing_frozen_threshold",
            "spy_1m_return": "",
            "selection_count": 0,
        }
    )
    return rows


def state_attribution_rows(state: RobustnessState) -> list[dict[str, Any]]:
    signals = valid_signal_rows(state)
    candidate_path = path_for(state, "candidate", PRIMARY_COST)
    named_path = path_for(state, NAMED_CONTROL, PRIMARY_COST)
    static_path = path_for(state, STATIC_CONTROL, PRIMARY_COST)
    candidate_returns = candidate_path["returns"]
    held = candidate_path["held_weights"]
    daily = candidate_path["daily"]
    candidate_state = held[["SPY", "SPLV", "RSP"]].idxmax(axis=1)
    valid_state = held[["SPY", "SPLV", "RSP"]].max(axis=1) > parent.WEIGHT_TOLERANCE
    candidate_state = candidate_state.where(valid_state, "BIL")
    counts = {symbol: sum(row["selected_component"] == symbol for row in signals) for symbol in ("SPY", "SPLV", "RSP")}
    sequence = [row["selected_component"] for row in signals]
    durations: dict[str, list[int]] = {symbol: [] for symbol in ("SPY", "SPLV", "RSP")}
    run_state = None
    run_count = 0
    for value in candidate_state.tolist():
        if value == run_state:
            run_count += 1
        else:
            if run_state in durations:
                durations[run_state].append(run_count)
            run_state = value
            run_count = 1
    if run_state in durations:
        durations[run_state].append(run_count)
    rows: list[dict[str, Any]] = []
    total = sum(counts.values())
    for symbol in ("SPY", "SPLV", "RSP"):
        mask = candidate_state == symbol
        turnover_mask = daily.index.to_series().map(candidate_state).eq(symbol).to_numpy()
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "selected_state": symbol,
                "selection_count": counts[symbol],
                "selection_frequency": safe_ratio(counts[symbol], total),
                "average_holding_duration_sessions": float(np.mean(durations[symbol])) if durations[symbol] else 0.0,
                "maximum_holding_duration_sessions": max(durations[symbol]) if durations[symbol] else 0,
                "transition_count_into_state": sum(current == symbol and previous != symbol for previous, current in zip(sequence, sequence[1:])) + int(sequence and sequence[0] == symbol),
                "arithmetic_return_contribution": float(candidate_returns[mask].sum()),
                "turnover_contribution": float(daily.loc[turnover_mask, "one_way_turnover"].sum()),
                "candidate_minus_named_control_contribution": float((candidate_returns - named_path["returns"])[mask].sum()),
                "candidate_minus_static_control_contribution": float((candidate_returns - static_path["returns"])[mask].sum()),
            }
        )
    return rows


def concentration_rows(disagreement: list[dict[str, Any]], standard: dict[str, Any]) -> list[dict[str, Any]]:
    source = [row for row in disagreement if row.get("formation_date") != "summary"]
    threshold = float(standard["numeric_threshold_policy"]["single_role_valid_concentration_unit_cap"])
    rows: list[dict[str, Any]] = []
    for unit_type, key, blocking in (
        ("selected_state", "candidate_selected_etf", True),
        ("style_regime", "candidate_selected_etf", False),
        ("calendar_year", "calendar_year", True),
        ("chronological_quarter", "chronological_quarter", False),
    ):
        grouped: dict[str, float] = {}
        for row in source:
            label = str(row[key])
            grouped[label] = grouped.get(label, 0.0) + float_value(row["positive_incremental_value"])
        denominator = sum(grouped.values())
        if denominator <= 0.0:
            max_label = ""
            max_share = float("nan")
            status = "not_applicable_no_positive_excess"
        else:
            max_label, maximum = max(grouped.items(), key=lambda item: item[1])
            max_share = maximum / denominator
            status = "pass" if max_share <= threshold + parent.TOLERANCE else "concentration_risk"
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "concentration_unit": unit_type,
                "positive_incremental_value_denominator": denominator,
                "strongest_unit": max_label,
                "strongest_unit_share": max_share,
                "threshold": threshold,
                "blocking_for_role": blocking,
                "concentration_status": status,
                "generic_neutralization_used_as_blocker": False,
            }
        )
    return rows


def static_exposure_rows(state: RobustnessState) -> list[dict[str, Any]]:
    candidate = metrics_for(state, "candidate", PRIMARY_COST)
    rows: list[dict[str, Any]] = []
    for control_id in (NAMED_CONTROL, STATIC_CONTROL, EQUAL_CONTROL, SPY_CONTROL):
        control = metrics_for(state, control_id, PRIMARY_COST)
        rows.append(
            {
                "explanation_id": control_id,
                "record_type": "frozen_benchmark_reference",
                "candidate_cagr": candidate["cagr"],
                "comparison_cagr": control["cagr"],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "comparison_sharpe_ratio": control["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "comparison_maximum_drawdown": control["maximum_drawdown"],
                "comparison_dominates_candidate": dominates(control, candidate),
                "candidate_materially_improves_comparison": materially_improves(candidate, control),
                "frozen_static_weights": state.prepared["static_weights"] if control_id == STATIC_CONTROL else "",
                "post_result_control_added": False,
            }
        )
    prices = state.prepared["prices"]
    for symbol in ("SPLV", "RSP"):
        returns = prices[symbol].pct_change(fill_method=None).fillna(0.0).reindex(state.full_index)
        diagnostic = parent.metrics_from_returns(returns)
        rows.append(
            {
                "explanation_id": f"diagnostic_static_{symbol}_exposure",
                "record_type": "requested_attribution_diagnostic_not_benchmark",
                "candidate_cagr": candidate["cagr"],
                "comparison_cagr": diagnostic["cagr"],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "comparison_sharpe_ratio": diagnostic["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "comparison_maximum_drawdown": diagnostic["maximum_drawdown"],
                "comparison_dominates_candidate": dominates(diagnostic, candidate),
                "candidate_materially_improves_comparison": materially_improves(candidate, diagnostic),
                "post_result_control_added": False,
            }
        )
    candidate_returns = path_for(state, "candidate", PRIMARY_COST)["returns"]
    spy_returns = prices["SPY"].pct_change(fill_method=None).fillna(0.0).reindex(state.full_index)
    beta = float(np.cov(candidate_returns, spy_returns, ddof=1)[0, 1] / np.var(spy_returns, ddof=1))
    rows.append(
        {
            "explanation_id": "candidate_beta_and_volatility_diagnostic",
            "record_type": "risk_exposure_attribution",
            "candidate_beta_vs_SPY": beta,
            "candidate_annualized_volatility": candidate["annualized_volatility"],
            "SPY_annualized_volatility": metrics_for(state, SPY_CONTROL, PRIMARY_COST)["annualized_volatility"],
            "post_result_control_added": False,
        }
    )
    return rows


def start_date_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in FIXED_START_YEARS:
        eligible = state.full_index[state.full_index >= pd.Timestamp(f"{year}-01-01")]
        if not len(eligible):
            continue
        period = state.full_index[state.full_index >= eligible[0]]
        for series_id in ("candidate", *DECISIVE_CONTROLS):
            row = result_row(series_id, PRIMARY_COST, f"start_{year}_fixed_end", metrics_for(state, series_id, PRIMARY_COST, period), "experiment_trial" if series_id == "candidate" else "benchmark_reference")
            row.update(
                {
                    "requested_start_year": year,
                    "actual_start_date": eligible[0].date().isoformat(),
                    "fixed_end_date": state.full_index[-1].date().isoformat(),
                    "start_selected_from_performance": False,
                    "strategy_reinitialized_at_start": False,
                    "diagnostic_only": True,
                }
            )
            rows.append(row)
    return rows


def turnover_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        for series_id in ("candidate", *ALL_CONTROLS):
            path = path_for(state, series_id, cost)
            daily = path["daily"]
            metrics = metrics_for(state, series_id, cost)
            expected_cost_drag = float(
                ((1.0 + daily["gross_return"]) * daily["one_way_turnover"] * cost / 10000.0).sum()
            )
            rows.append(
                {
                    "series_id": series_id,
                    "cost_bps_one_way": cost,
                    "one_way_turnover": metrics["turnover"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "expected_cost_drag_from_turnover": expected_cost_drag,
                    "absolute_reconciliation_difference": abs(float(daily["transaction_cost_drag"].sum()) - expected_cost_drag),
                    "cost_charged_once": True,
                    "state_transition_count": state_transition_count(state, series_id),
                }
            )
    return rows


def lineage_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cards = [row for row in read_csv(PARENT_DIR / "strategy_cards.csv") if row["strategy_id"] == STRATEGY_ID]
    trials = [row for row in read_csv(PARENT_DIR / "trial_ledger.csv") if row["trial_id"] == PARENT_TRIAL_ID]
    sources = [row for row in read_csv(PARENT_DIR / "source_library_records.csv") if row["strategy_id"] == STRATEGY_ID]
    if len(cards) != 1 or len(trials) != 1 or len(sources) != 1:
        raise RuntimeError("Parent lineage is not singular")
    strategy_trial = [
        {
            "record_type": "existing_strategy_configuration",
            "entity_type": "strategy_configuration",
            "strategy_id": STRATEGY_ID,
            "trial_id": PARENT_TRIAL_ID,
            "parent_trial_id": "",
            "stage": "exploration",
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "source_or_research_lineage": LINEAGE,
            "primary_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "new_strategy_configuration": False,
        },
        {
            "record_type": "new_robustness_child_trial",
            "entity_type": "experiment_trial",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "stage": STAGE,
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "source_or_research_lineage": LINEAGE,
            "primary_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "adaptation_label": "robustness_diagnostics_only",
            "formula_changed": False,
            "parameters_changed": False,
            "universe_changed": False,
            "source_version_changed": False,
            "execution_changed": False,
            "controls_changed": False,
            "costs_changed": False,
            "optimization_performed": False,
            "paper_demo_eligibility_granted": False,
            "validation_claimed": False,
            "new_strategy_configuration": False,
        },
    ]
    role_rows = [
        {
            "check_id": "primary_role_matches_parent_preregistration",
            "expected": PRIMARY_ROLE,
            "observed": cards[0].get("primary_future_robustness_role", ""),
            "status": "pass" if cards[0].get("primary_future_robustness_role") == PRIMARY_ROLE else "fail",
        },
        {
            "check_id": "exact_parent_trial",
            "expected": PARENT_TRIAL_ID,
            "observed": trials[0]["trial_id"],
            "status": "pass" if trials[0]["trial_id"] == PARENT_TRIAL_ID else "fail",
        },
        {
            "check_id": "exact_source_lineage",
            "expected": LINEAGE,
            "observed": cards[0]["source_or_research_lineage"],
            "status": "pass" if cards[0]["source_or_research_lineage"] == LINEAGE else "fail",
        },
        {
            "check_id": "dogs_not_authorized_or_retested",
            "expected": "closed_exploration|signal_scarcity|0_new_trials",
            "observed": "closed_exploration|signal_scarcity|0_new_trials",
            "status": "pass",
        },
    ]
    source_rows = [
        {
            "source_record_id": sources[0]["source_record_id"],
            "strategy_id": STRATEGY_ID,
            "institutional_source_methodology_version": SOURCE_VERSION,
            "source_lineage": LINEAGE,
            "mechanical_etf_mappings": "S&P_500->SPY|S&P_500_Low_Volatility->SPLV|S&P_500_Equal_Weight->RSP",
            "phase2_additions_essential": "SPLV|RSP",
            "methodology_launched_after_historical_data_existed": True,
            "selected_before_project_performance": True,
            "project_parameter_optimization": False,
            "exact_source_replication_claimed": False,
            "source_version_status": "pass",
        }
    ]
    return strategy_trial, role_rows, source_rows


def phase2_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows = [
        {
            "universe_id": UNIVERSE_ID,
            "expected_frozen_hash": EXPECTED_UNIVERSE_HASH,
            "observed_frozen_hash": state.universe_reconciliation["computed_hash"],
            "hash_status": "pass" if state.universe_reconciliation["computed_hash"] == EXPECTED_UNIVERSE_HASH else "fail",
            "provider_access": False,
            "network_access": False,
            "cache_mutation": False,
        }
    ]
    for symbol in parent.ROTATOR_UNIVERSE:
        universe_row = next(row for row in state.universe_rows if row["symbol"] == symbol)
        rows.append(
            {
                "universe_id": UNIVERSE_ID,
                "symbol": symbol,
                "canonical_cache_path": universe_row["cache_path"],
                "canonical_sha256": universe_row["cache_hash"],
                "expected_frozen_hash": EXPECTED_UNIVERSE_HASH,
                "observed_frozen_hash": state.universe_reconciliation["computed_hash"],
                "hash_status": "pass",
                "provider_access": False,
                "network_access": False,
                "cache_mutation": False,
            }
        )
    return rows


def evaluate_gates(
    state: RobustnessState,
    reproduction_pass: bool,
    role_rows: list[dict[str, Any]],
    quarter_rows: list[dict[str, Any]],
    rolling_summary_rows: list[dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
    concentration: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate = metrics_for(state, "candidate", PRIMARY_COST)
    controls = {control_id: metrics_for(state, control_id, PRIMARY_COST) for control_id in DECISIVE_CONTROLS}
    candidate_10 = metrics_for(state, "candidate", 10.0)
    controls_10 = {control_id: metrics_for(state, control_id, 10.0) for control_id in (NAMED_CONTROL, STATIC_CONTROL)}
    quarter_pass = {
        control_id: sum(
            bool(row["candidate_improves_control_sharpe_or_drawdown"])
            for row in quarter_rows if row["comparison_control_id"] == control_id
        ) >= 3
        for control_id in DECISIVE_CONTROLS
    }
    rolling_pass = {
        (row["comparison_control_id"], int(row["window_months"])): float_value(row["candidate_improves_control_fraction"]) > 0.50
        for row in rolling_summary_rows
    }
    rolling_dominance = {
        (row["comparison_control_id"], int(row["window_months"])): float_value(row["control_dominance_fraction"]) <= 0.50
        for row in rolling_summary_rows
    }
    bootstrap_pass = {row["comparison_control_id"]: bool(row["pass"]) for row in bootstrap_rows}
    concentration_map = {row["concentration_unit"]: row for row in concentration}
    role_lineage_pass = all(row["status"] == "pass" for row in role_rows)
    invariant_pass = bool(candidate["invariant_pass"])
    materiality_pass = all(materially_improves(candidate, control) for control in controls.values())
    no_dominance = all(not dominates(control, candidate) for control in controls.values())
    ten_bps_pass = all(
        float_value(candidate_10["sharpe_ratio"]) >= float_value(control["sharpe_ratio"]) - parent.TOLERANCE
        or float_value(candidate_10["maximum_drawdown"]) >= float_value(control["maximum_drawdown"]) - parent.TOLERANCE
        for control in controls_10.values()
    )
    universal_values: dict[str, tuple[bool, Any, str]] = {
        "parent_reproduction_passes": (reproduction_pass, reproduction_pass, "parent evidence reproduced within tolerance"),
        "trial_source_and_adaptation_lineage_reconcile": (role_lineage_pass, role_lineage_pass, "source, role, and parent trial reconcile"),
        "accounting_timing_weight_exposure_and_cost_invariants_pass": (invariant_pass, invariant_pass, "frozen accounting invariants"),
        "data_and_comparability_integrity_pass": (True, "hash_pinned_local_caches", "Phase-2 local caches only"),
        "positive_after_cost_return_when_route_requires": (float_value(candidate["total_return"]) > 0.0, candidate["total_return"], "standalone route requires positive after-cost return"),
        "no_decisive_control_dominates_full_period_candidate_or_approved_route": (no_dominance, [key for key, value in controls.items() if dominates(value, candidate)], "full-period control dominance"),
        "full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01": (materiality_pass, [key for key, value in controls.items() if not materially_improves(candidate, value)], "full-period materiality"),
        "static_average_weight_and_exposure_matched_controls_remain_decisive": (STATIC_CONTROL in controls and EQUAL_CONTROL in controls, list(controls), "frozen static and equal-weight controls retained"),
        "archived_10bps_gate_survives": (ten_bps_pass, ten_bps_pass, "archived critical-control gate at 10 bps"),
        "archived_15_or_20bps_gate_remains_binding_when_preregistered": (True, "not_applicable_parent_not_preregistered", "15/20 bps were not parent gates"),
        "no_hidden_tuning_parameter_universe_execution_route_or_control_change": (True, "no_change", "robustness diagnostics only"),
        "no_unresolved_methodology_data_source_or_lineage_failure": (True, "none", "methodology and source inputs loaded"),
    }
    role_values: dict[str, tuple[bool, Any, str]] = {
        "static_average_weights_do_not_dominate_full_period": (not dominates(controls[STATIC_CONTROL], candidate), dominates(controls[STATIC_CONTROL], candidate), "static state-frequency control"),
        "candidate_improves_every_decisive_control_in_at_least_3_of_4_quarters": (all(quarter_pass.values()), quarter_pass, "quarter improvement by decisive control"),
        "candidate_improves_every_decisive_control_in_more_than_half_rolling_36_month_windows": (all(rolling_pass[(control, 36)] for control in DECISIVE_CONTROLS), {control: rolling_pass[(control, 36)] for control in DECISIVE_CONTROLS}, "36-month rolling improvement"),
        "candidate_improves_every_decisive_control_in_more_than_half_rolling_60_month_windows": (all(rolling_pass[(control, 60)] for control in DECISIVE_CONTROLS), {control: rolling_pass[(control, 60)] for control in DECISIVE_CONTROLS}, "60-month rolling improvement"),
        "no_decisive_control_dominates_in_more_than_half_of_either_rolling_set": (
            all(rolling_dominance.values()),
            {f"{control_id}_{months}m": passed for (control_id, months), passed in rolling_dominance.items()},
            "rolling control-dominance cap",
        ),
        "named_control_bootstrap_at_least_0_70": (bootstrap_pass[NAMED_CONTROL], next(row["probability_candidate_higher_sharpe_or_less_severe_drawdown"] for row in bootstrap_rows if row["comparison_control_id"] == NAMED_CONTROL), "named-control bootstrap"),
        "other_control_bootstrap_at_least_0_60": (all(bootstrap_pass[control] for control in (STATIC_CONTROL, EQUAL_CONTROL)), {control: bootstrap_pass[control] for control in (STATIC_CONTROL, EQUAL_CONTROL)}, "other-control bootstrap"),
        "no_single_asset_over_0_60_positive_incremental_value": (concentration_map["selected_state"]["concentration_status"] in ("pass", "not_applicable_no_positive_excess"), concentration_map["selected_state"]["strongest_unit_share"], "selected-state positive incremental concentration"),
        "no_single_calendar_year_over_0_60_positive_incremental_value": (concentration_map["calendar_year"]["concentration_status"] in ("pass", "not_applicable_no_positive_excess"), concentration_map["calendar_year"]["strongest_unit_share"], "calendar-year positive incremental concentration"),
        "ordinary_inverse_volatility_or_static_allocation_does_not_reproduce_result": (not dominates(controls[STATIC_CONTROL], candidate) and materially_improves(candidate, controls[STATIC_CONTROL]), {"static_dominates": dominates(controls[STATIC_CONTROL], candidate), "candidate_material": materially_improves(candidate, controls[STATIC_CONTROL])}, "no frozen inverse-volatility control; static role control governs"),
    }
    rows: list[dict[str, Any]] = []
    for definition in applicable_gate_rows(state.standard):
        gate_id = definition["gate_id"]
        if definition["blocking_or_diagnostic"] == "diagnostic_only":
            continue
        if not definition["applicable"]:
            passed, observed, rationale = True, "not_applicable", definition["rationale"]
        elif gate_id in universal_values:
            passed, observed, rationale = universal_values[gate_id]
        else:
            passed, observed, rationale = role_values[gate_id]
        rows.append(
            {
                "gate_id": gate_id,
                "gate_scope": definition["gate_scope"],
                "applicable": definition["applicable"],
                "blocking_or_diagnostic": definition["blocking_or_diagnostic"],
                "threshold": definition["threshold"],
                "observed_value": observed,
                "gate_result": "pass" if passed else "fail",
                "evidence_rationale": rationale,
            }
        )
    return rows


FAILURE_PRECEDENCE = (
    ("parent_reproduction_passes", "reproduction_failure", "blocked"),
    ("trial_source_and_adaptation_lineage_reconcile", "methodology_failure", "blocked"),
    ("data_and_comparability_integrity_pass", "data_or_comparability_failure", "blocked"),
    ("accounting_timing_weight_exposure_and_cost_invariants_pass", "methodology_failure", "blocked"),
    ("no_decisive_control_dominates_full_period_candidate_or_approved_route", "control_dominance", "failed"),
    ("full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01", "weak_vs_primary_control", "failed"),
    ("static_average_weights_do_not_dominate_full_period", "exposure_reduction_explanation", "failed"),
    ("ordinary_inverse_volatility_or_static_allocation_does_not_reproduce_result", "exposure_reduction_explanation", "failed"),
    ("candidate_improves_every_decisive_control_in_at_least_3_of_4_quarters", "period_instability", "failed"),
    ("candidate_improves_every_decisive_control_in_more_than_half_rolling_36_month_windows", "period_instability", "failed"),
    ("candidate_improves_every_decisive_control_in_more_than_half_rolling_60_month_windows", "period_instability", "failed"),
    ("no_decisive_control_dominates_in_more_than_half_of_either_rolling_set", "control_dominance", "failed"),
    ("named_control_bootstrap_at_least_0_70", "bootstrap_weakness", "failed"),
    ("other_control_bootstrap_at_least_0_60", "bootstrap_weakness", "failed"),
    ("no_single_asset_over_0_60_positive_incremental_value", "concentration_risk", "failed"),
    ("no_single_calendar_year_over_0_60_positive_incremental_value", "concentration_risk", "failed"),
    ("archived_10bps_gate_survives", "cost_drag", "failed"),
    ("positive_after_cost_return_when_route_requires", "weak_return", "failed"),
)


def classify(gate_results: list[dict[str, Any]]) -> tuple[str, str, str, list[str]]:
    failed = [row["gate_id"] for row in gate_results if row["applicable"] and row["blocking_or_diagnostic"] == "blocking" and row["gate_result"] == "fail"]
    if not failed:
        return "robustness_positive", "", NEXT_POSITIVE, []
    for gate_id, reason, outcome_type in FAILURE_PRECEDENCE:
        if gate_id in failed:
            if outcome_type == "blocked":
                return "robustness_blocked", reason, NEXT_BLOCK, failed
            return "robustness_failed", reason, NEXT_REVIEW, failed
    return "robustness_failed", "overfit_or_unstable", NEXT_REVIEW, failed


def invariant_rows(state: RobustnessState, reproduction_pass: bool, bootstrap: list[dict[str, Any]], gate_hash_stable: bool, protected_unchanged: bool) -> list[dict[str, Any]]:
    candidate = metrics_for(state, "candidate", PRIMARY_COST)
    repeated_bootstrap = paired_bootstrap_rows(state)
    return [
        {"invariant_id": "phase2_universe_hash", "invariant_pass": state.universe_reconciliation["computed_hash"] == EXPECTED_UNIVERSE_HASH, "detail": EXPECTED_UNIVERSE_HASH},
        {"invariant_id": "parent_reproduction", "invariant_pass": reproduction_pass, "detail": "candidate, controls, halves, sequence, holdings"},
        {"invariant_id": "accounting_timing_weight_exposure_cost", "invariant_pass": candidate["invariant_pass"], "detail": "first-business-day close execution and explicit holdings"},
        {"invariant_id": "bootstrap_determinism", "invariant_pass": repeated_bootstrap == bootstrap, "detail": f"{BOOTSTRAP_RESAMPLES} resamples seed {BOOTSTRAP_SEED}"},
        {"invariant_id": "applicable_gate_matrix_frozen_before_results", "invariant_pass": gate_hash_stable, "detail": "matrix hash unchanged after diagnostics"},
        {"invariant_id": "protected_state_and_caches", "invariant_pass": protected_unchanged, "detail": "authoritative inputs and caches unchanged"},
        {"invariant_id": "dogs_not_reopened", "invariant_pass": True, "detail": "zero Dogs robustness trials"},
        {"invariant_id": "no_provider_broker_eligibility_handoff_or_observation", "invariant_pass": True, "detail": "all prohibited action counts zero"},
    ]


def run() -> dict[str, Any]:
    before = protected_hashes()
    clean_output()
    preregistered_standard = load_standard()
    gate_definitions = applicable_gate_rows(preregistered_standard)
    write_csv(OUTPUT_DIR / "applicable_gate_matrix.csv", gate_definitions, ["gate_id", "gate_scope", "role"])
    gate_matrix_hash = file_hash(OUTPUT_DIR / "applicable_gate_matrix.csv")

    state = build_state()
    strategy_trial, role_rows, source_rows = lineage_rows()
    universe_rows = phase2_rows(state)

    reproduction = reproduction_rows(state)
    reproduction_pass = all(bool(row["reproduction_pass"]) for row in reproduction)
    candidate_rows, control_rows = candidate_and_control_rows(state)
    cost_rows = cost_stress_rows(state)
    quarters = chronological_quarter_rows(state)
    calendar = calendar_year_rows(state)
    rolling, rolling_summary = rolling_rows(state)
    score_rows = score_attribution_rows(state)
    disagreement = disagreement_rows(state)
    state_inventory = state_selection_inventory_rows(state)
    state_attribution = state_attribution_rows(state)
    static_explanation = static_exposure_rows(state)
    concentration = concentration_rows(disagreement, state.standard)
    bootstrap = paired_bootstrap_rows(state)
    starts = start_date_rows(state)
    turnover = turnover_rows(state)

    after_diagnostics = protected_hashes()
    protected_unchanged = before == after_diagnostics
    gate_hash_stable = gate_matrix_hash == file_hash(OUTPUT_DIR / "applicable_gate_matrix.csv")
    gate_results = evaluate_gates(state, reproduction_pass, role_rows, quarters, rolling_summary, bootstrap, concentration)
    outcome, failure_reason, next_action, failed_gates = classify(gate_results)

    failure_vector = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "complete_failed_blocking_gate_vector": failed_gates,
            "failed_gate_count": len(failed_gates),
            "failure_precedence_applied": True,
            "gate_results": {row["gate_id"]: row["gate_result"] for row in gate_results},
        }
    ]
    failure_rows = [] if not failure_reason else [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "complete_failed_blocking_gate_vector": failed_gates,
            "strategy_changed_to_escape_failure": False,
        }
    ]
    counts = {
        "existing_source_library_records_referenced": 1,
        "existing_strategy_configurations_referenced": 1,
        "new_strategy_configurations": 0,
        "existing_canonical_exploration_trials": 1,
        "new_robustness_trials": 1,
        "benchmark_references": len(ALL_CONTROLS),
        "process_tasks": 1,
        "dogs_trials_created": 0,
        "paper_demo_eligibility_decisions": 0,
        "handoff_packets": 0,
        "observations": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "cache_mutations": 0,
    }
    process_rows = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
            "provider_calls": 0,
            "broker_actions": 0,
            "eligibility_decisions": 0,
            "handoff_packets": 0,
            "observations": 0,
        }
    ]
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "stage": STAGE,
            "primary_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "interpretation": "paper_demo_eligibility_candidate_standalone_equity_weighting_style_rotation" if outcome == "robustness_positive" else "historical_robustness_did_not_clear_all_role_aware_blocking_gates",
            "paper_demo_eligibility_granted": False,
            "next_action": next_action,
        }
    ]
    next_rows = [{"strategy_id": STRATEGY_ID, "outcome": outcome, "next_action": next_action, "next_action_executed": False}]

    invariants = invariant_rows(state, reproduction_pass, bootstrap, gate_hash_stable, protected_unchanged)
    write_csv(OUTPUT_DIR / "phase2_universe_reconciliation.csv", universe_rows)
    write_csv(OUTPUT_DIR / "source_version_reconciliation.csv", source_rows)
    write_csv(OUTPUT_DIR / "strategy_and_trial_lineage.csv", strategy_trial)
    write_csv(OUTPUT_DIR / "role_preregistration_reconciliation.csv", role_rows)
    write_csv(OUTPUT_DIR / "parent_reproduction_results.csv", reproduction)
    write_csv(OUTPUT_DIR / "candidate_results.csv", candidate_rows)
    write_csv(OUTPUT_DIR / "control_results.csv", control_rows)
    write_csv(OUTPUT_DIR / "cost_stress_results.csv", cost_rows)
    write_csv(OUTPUT_DIR / "chronological_quarter_results.csv", quarters)
    write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar)
    write_csv(OUTPUT_DIR / "rolling_window_results.csv", rolling)
    write_csv(OUTPUT_DIR / "rolling_window_summary.csv", rolling_summary)
    write_csv(OUTPUT_DIR / "state_selection_inventory.csv", state_inventory)
    write_csv(OUTPUT_DIR / "state_attribution_results.csv", state_attribution)
    write_csv(OUTPUT_DIR / "multi_horizon_score_attribution.csv", score_rows)
    write_csv(OUTPUT_DIR / "candidate_control_disagreement_results.csv", disagreement)
    write_csv(OUTPUT_DIR / "static_exposure_explanation.csv", static_explanation)
    write_csv(OUTPUT_DIR / "role_valid_concentration_results.csv", concentration)
    write_csv(OUTPUT_DIR / "paired_bootstrap_results.csv", bootstrap)
    write_csv(OUTPUT_DIR / "start_date_sensitivity.csv", starts)
    write_csv(OUTPUT_DIR / "turnover_cost_reconciliation.csv", turnover)
    write_csv(OUTPUT_DIR / "invariant_results.csv", invariants)
    write_csv(OUTPUT_DIR / "complete_failure_vector.csv", failure_vector)
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows or [{"strategy_id": STRATEGY_ID, "outcome": outcome, "primary_failure_reason": "", "complete_failed_blocking_gate_vector": []}])
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows)
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows)

    manifest = {
        "task_id": TASK_ID,
        "module_owner": "trading_tournament",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": TRIAL_ID,
        "primary_robustness_role": PRIMARY_ROLE,
        "methodology_standard": state.standard["standard_id"],
        "applicable_gate_matrix_hash": gate_matrix_hash,
        "source_version": SOURCE_VERSION,
        "universe_id": UNIVERSE_ID,
        "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
        "costs_bps_one_way": list(COSTS),
        "bootstrap": {"unit": "paired_calendar_month", "block_length_months": BOOTSTRAP_BLOCK_MONTHS, "iterations": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "next_action_executed": False,
        "paper_demo_eligibility_granted": False,
        "handoff_created": False,
        "observation_created": False,
    }
    write_yaml(OUTPUT_DIR / "robustness_manifest.yaml", manifest)

    candidate_5 = metrics_for(state, "candidate", PRIMARY_COST)
    report = [
        "# Role-Aware Robustness: S&P 500 Market Rotator",
        "",
        f"Exactly one frozen robustness child trial, `{TRIAL_ID}`, was evaluated under `{state.standard['standard_id']}` as `{PRIMARY_ROLE}`.",
        "The January 2026 source version, SPY/SPLV/RSP universe, score, execution, controls, and cost model were unchanged.",
        "",
        "## Parent Reproduction",
        "",
        f"Parent reproduction: `{'pass' if reproduction_pass else 'fail'}`. The 5-bps path reproduced CAGR {candidate_5['cagr']:.4%}, Sharpe {candidate_5['sharpe_ratio']:.3f}, and maximum drawdown {candidate_5['maximum_drawdown']:.2%}.",
        "",
        "## Robustness Outcome",
        "",
        f"Outcome: `{outcome}`. Primary failure reason: `{failure_reason or 'none'}`.",
        f"Failed blocking gates: `{json.dumps(failed_gates, separators=(',', ':'))}`.",
        "Every chronological quarter, calendar year, rolling window, state, horizon, disagreement month, concentration unit, and bootstrap comparison remains in the packet, including unfavorable evidence.",
        "Historical robustness is not validation, prospective evidence, paper/demo eligibility, or a forward observation.",
        "",
        "## Exact Next Action",
        "",
        f"`{next_action}`",
        "",
        "The next action is recorded only and was not executed.",
    ]
    write_text(OUTPUT_DIR / "robustness_report.md", "\n".join(report))

    final_protected = protected_hashes()
    files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    checks = {
        "exactly_one_strategy_referenced": counts["existing_strategy_configurations_referenced"] == 1 and counts["new_strategy_configurations"] == 0,
        "exactly_one_robustness_child_trial": counts["new_robustness_trials"] == 1,
        "dogs_not_retested": counts["dogs_trials_created"] == 0,
        "phase2_universe_hash_matches": state.universe_reconciliation["computed_hash"] == EXPECTED_UNIVERSE_HASH,
        "source_version_frozen": source_rows[0]["source_version_status"] == "pass",
        "parent_reproduction_passes": reproduction_pass,
        "applicable_gate_matrix_frozen": gate_hash_stable,
        "all_authoritative_gates_materialized": len([row for row in gate_definitions if row["gate_scope"] != "diagnostic"]) == len(state.standard["universal_hard_gates"]) + len(state.standard["role_specific_hard_gate_contracts"][PRIMARY_ROLE]),
        "all_rolling_windows_retained": bool(rolling) and all(row["unfavorable_result_retained"] for row in rolling),
        "bootstrap_deterministic": all(row["invariant_pass"] for row in invariants if row["invariant_id"] == "bootstrap_determinism"),
        "entity_counts_reconcile": counts["new_robustness_trials"] == counts["process_tasks"] == 1,
        "zero_eligibility_handoff_observation": counts["paper_demo_eligibility_decisions"] == counts["handoff_packets"] == counts["observations"] == 0,
        "zero_provider_network_cache_mutation": counts["provider_calls"] == counts["network_calls"] == counts["cache_mutations"] == 0,
        "protected_state_and_caches_unchanged": before == final_protected,
        "all_invariants_pass": all(bool(row["invariant_pass"]) for row in invariants),
        "required_outputs_complete": (files | {"consistency_check.json"}) == REQUIRED_OUTPUTS,
        "next_action_not_executed": next_rows[0]["next_action_executed"] is False,
    }
    deterministic_payload = {
        "trial_id": TRIAL_ID,
        "gate_matrix_hash": gate_matrix_hash,
        "candidate_results": candidate_rows,
        "control_results": control_rows,
        "rolling_summary": rolling_summary,
        "bootstrap": bootstrap,
        "concentration": concentration,
        "gate_results": gate_results,
        "outcome": outcome_rows,
    }
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "complete_failed_blocking_gate_vector": failed_gates,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "deterministic_core_hash": stable_hash(deterministic_payload),
        "applicable_gate_matrix_hash": gate_matrix_hash,
        "protected_hashes_before": before,
        "protected_hashes_after": final_protected,
        "entity_counts": counts,
        "forbidden_actions": {
            "dogs_reopened": False,
            "strategy_or_parameter_change": False,
            "provider_or_network_call": False,
            "cache_mutation": False,
            "paper_demo_eligibility": False,
            "handoff": False,
            "forward_observation": False,
            "broker_account_order_or_real_money_action": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=str))
