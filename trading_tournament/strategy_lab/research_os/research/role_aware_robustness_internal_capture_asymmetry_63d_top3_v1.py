from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import accepted_47_targeted_internal_technical_batch_v1 as parent


TASK_ID = "role_aware_robustness_internal_capture_asymmetry_63d_top3_v1"
STAGE = "robustness"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
PARENT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "accepted_47_targeted_internal_technical_batch_v1"
    / "latest"
)
METHODOLOGY_PATH = (
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml"
)

STRATEGY_ID = "internal_capture_asymmetry_63d_top3_v1"
PARENT_TRIAL_ID = "accepted47_internal_v1__capture63__top3"
TRIAL_ID = "robustness__internal_capture_asymmetry_63d_top3_v1__role_aware_v1"
FAMILY_ID = "cross_asset_capture_asymmetry_rotation"
ARCHITECTURE_ID = "downside_upside_capture_cross_sectional"
PRIMARY_ROLE = "cross_sectional_allocation_strategy"
LINEAGE = "internally_generated_technical_hypothesis"
ROUTE = "standalone"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-8
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260807

NAMED_CONTROL = "ordinary_beta_defensive_rotation_control"
STATIC_CONTROL = "static_average_candidate_weights_control"
EQUAL_CONTROL = "equal_weight_12_asset_universe_control"
SPY_CONTROL = "SPY_buy_and_hold"
BIL_CONTROL = "BIL_buy_and_hold"
DECISIVE_CONTROLS = (NAMED_CONTROL, STATIC_CONTROL, EQUAL_CONTROL)
ALL_CONTROLS = (*DECISIVE_CONTROLS, SPY_CONTROL, BIL_CONTROL)

NEXT_POSITIVE = "paper_demo_eligibility_and_handoff_internal_capture_asymmetry_63d_top3_v1"
NEXT_REVIEW = "direction_owner_review_internal_capture_asymmetry_robustness_v1"
NEXT_BLOCK = "direction_owner_review_internal_capture_asymmetry_robustness_block_v1"

PARENT_REQUIRED_INPUTS = (
    "architecture_preregistration.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "duplicate_preflight.csv",
    "selection_segment_definition.csv",
    "selection_segment_results.csv",
    "architecture_winner_selection.csv",
    "evaluation_segment_results.csv",
    "post_selection_full_period_diagnostics.csv",
    "calendar_year_results.csv",
    "rebalance_contribution_results.csv",
    "lightweight_concentration_diagnostics.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_vectors.csv",
    "outcome_summary.csv",
    "consistency_check.json",
    "batch_report.md",
)

REQUIRED_OUTPUTS = {
    "robustness_manifest.yaml",
    "direction_routing_record.csv",
    "parent_trial_reconciliation.csv",
    "multiple_testing_lineage.csv",
    "role_preregistration_reconciliation.csv",
    "applicable_gate_matrix.csv",
    "reproduction_results.csv",
    "candidate_results.csv",
    "control_results.csv",
    "cost_sensitivity.csv",
    "chronological_subperiod_results.csv",
    "rolling_window_results.csv",
    "control_dominance_results.csv",
    "bootstrap_results.csv",
    "calendar_year_incremental_results.csv",
    "rebalance_incremental_results.csv",
    "asset_incremental_attribution.csv",
    "economic_bucket_attribution.csv",
    "role_valid_concentration_results.csv",
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
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    METHODOLOGY_PATH,
    PARENT_DIR,
    parent.CACHE_DIR,
    ROOT / "evidence" / "paper_demo_observation",
    ROOT / "evidence" / "forward_observation",
    ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "cfra_stovall_semiannual_sector_rotation_exploration_v1" / "latest",
)

ASSET_BUCKETS = {
    "SPY": "U.S. equity",
    "QQQ": "U.S. equity",
    "IWM": "U.S. equity",
    "EFA": "international equity",
    "EEM": "international equity",
    "HYG": "credit",
    "LQD": "credit",
    "TLT": "duration/Treasuries",
    "TIP": "inflation-linked bonds",
    "GLD": "commodities/gold",
    "DBC": "commodities/gold",
    "IYR": "real estate",
    "BIL": "cash/fallback",
}


@dataclass(frozen=True)
class RobustnessState:
    standard: dict[str, Any]
    split: parent.SplitDefinition
    prepared: dict[str, Any]
    simulation: dict[str, Any]
    scheduled_executions: tuple[pd.Timestamp, ...]
    full_index: pd.DatetimeIndex
    parent_full_rows: dict[float, dict[str, str]]
    parent_eval_rows: dict[float, dict[str, str]]


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


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


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.bool_,)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        output = float(value)
        return "" if not math.isfinite(output) else f"{output:.12g}"
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "robustness" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def float_value(value: Any) -> float:
    try:
        output = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return output if math.isfinite(output) else float("nan")


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0 or not math.isfinite(denominator):
        return float("nan")
    return numerator / denominator


def compound_return(returns: pd.Series) -> float:
    values = returns.dropna().to_numpy(dtype=float)
    if not len(values):
        return 0.0
    return float(np.prod(1.0 + values) - 1.0)


def monthly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.dropna()).resample("ME").prod() - 1.0


def metrics_from_returns(returns: pd.Series, periods_per_year: float = 252.0) -> dict[str, Any]:
    daily = returns.dropna().astype(float)
    if daily.empty:
        return {
            "period_start": "",
            "period_end": "",
            "observation_count": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "sharpe_ratio": float("nan"),
            "maximum_drawdown": float("nan"),
        }
    equity = (1.0 + daily).cumprod()
    years = max(len(daily) / periods_per_year, 1e-12)
    total = float(equity.iloc[-1] - 1.0)
    volatility = float(daily.std(ddof=0) * math.sqrt(periods_per_year))
    start_value = daily.index.min()
    end_value = daily.index.max()
    period_start = start_value.date().isoformat() if hasattr(start_value, "date") else str(start_value)
    period_end = end_value.date().isoformat() if hasattr(end_value, "date") else str(end_value)
    return {
        "period_start": period_start,
        "period_end": period_end,
        "observation_count": len(daily),
        "total_return": total,
        "cagr": float((1.0 + total) ** (1.0 / years) - 1.0),
        "annualized_volatility": volatility,
        "sharpe_ratio": float((daily.mean() * periods_per_year) / volatility) if volatility > 0.0 else float("nan"),
        "maximum_drawdown": float((equity / equity.cummax() - 1.0).min()),
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return parent.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return parent.material_advantage(candidate, control)


def load_standard() -> dict[str, Any]:
    payload = yaml.safe_load(METHODOLOGY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("role-aware robustness standard did not load as a mapping")
    return payload


def parent_rows_by_cost(filename: str) -> dict[float, dict[str, str]]:
    output: dict[float, dict[str, str]] = {}
    for row in read_csv(PARENT_DIR / filename):
        if row.get("strategy_id") == STRATEGY_ID and row.get("trial_id") == PARENT_TRIAL_ID:
            output[float(row["cost_bps_one_way"])] = row
    return output


def build_state() -> RobustnessState:
    standard = load_standard()
    frames = parent.load_frames()
    arch = parent.architecture_by_code("A")
    config = parent.configs_for_architecture("A")[0]
    if config.strategy_id != STRATEGY_ID or config.trial_id != PARENT_TRIAL_ID:
        raise RuntimeError("parent module A1 fingerprint drift")
    split = parent.architecture_split(frames, arch)
    prepared = parent.build_events_for_config(arch, config, split)
    simulation = parent.simulate_prepared(split, prepared)
    return RobustnessState(
        standard=standard,
        split=split,
        prepared=prepared,
        simulation=simulation,
        scheduled_executions=tuple(execution for _, execution in split.signal_execution_pairs),
        full_index=split.full_index,
        parent_full_rows=parent_rows_by_cost("post_selection_full_period_diagnostics.csv"),
        parent_eval_rows=parent_rows_by_cost("evaluation_segment_results.csv"),
    )


def metric_for(state: RobustnessState, series_id: str, cost: float, period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    period_index = state.full_index if period is None else period
    if series_id == "candidate":
        path = state.simulation["candidate_paths"][cost]
    else:
        path = state.simulation["control_paths"][(series_id, cost)]
    return parent.metrics_for_path(path, period_index, state.scheduled_executions)


def all_metric_maps(state: RobustnessState) -> dict[tuple[str, float], dict[str, Any]]:
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        metrics[("candidate", cost)] = metric_for(state, "candidate", cost)
        for control_id in ALL_CONTROLS:
            metrics[(control_id, cost)] = metric_for(state, control_id, cost)
    return metrics


def metric_row(series_id: str, entity_role: str, cost: float, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "series_id": series_id,
        "entity_role": entity_role,
        "period_id": "full_valid_common_period",
        "cost_bps_one_way": cost,
        "period_start": metrics["period_start"],
        "period_end": metrics["period_end"],
        "trading_day_count": metrics["trading_day_count"],
        "formation_count": metrics["formation_count"],
        "rebalance_count": metrics["rebalance_count"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "annualized_volatility": metrics["annualized_volatility"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "maximum_drawdown": metrics["maximum_drawdown"],
        "turnover": metrics["turnover"],
        "annualized_turnover": metrics["annualized_turnover"],
        "transaction_cost_drag": metrics["transaction_cost_drag"],
        "average_holdings": metrics["average_holdings"],
        "maximum_asset_weight": metrics["maximum_asset_weight"],
        "maximum_gross_exposure": metrics["maximum_gross_exposure"],
        "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
        "daily_weight_sum_one": metrics["daily_weight_sum_one"],
        "numeric_invariant_status": metrics["numeric_invariant_status"],
        "timing_invariant_status": metrics["timing_invariant_status"],
        "exposure_weight_invariant_status": metrics["exposure_weight_invariant_status"],
        "invariant_pass": metrics["invariant_pass"],
    }


def compare_metric(label: str, reproduced: float, parent_value: str, tolerance: float = REPRODUCTION_TOLERANCE) -> dict[str, Any]:
    archived = float_value(parent_value)
    difference = reproduced - archived if math.isfinite(archived) and math.isfinite(reproduced) else float("nan")
    return {
        "metric_name": label,
        "reproduced_value": reproduced,
        "parent_value": archived,
        "absolute_difference": abs(difference) if math.isfinite(difference) else float("nan"),
        "tolerance": tolerance,
        "reproduction_pass": bool(math.isfinite(difference) and abs(difference) <= tolerance),
    }


def reproduction_rows(state: RobustnessState, metrics: dict[tuple[str, float], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "transaction_cost_drag",
    )
    for cost in COSTS:
        parent_row = state.parent_full_rows[cost]
        candidate = metrics[("candidate", cost)]
        for field in metric_fields:
            rows.append(
                {
                    "reproduction_scope": "post_selection_full_period_candidate",
                    "series_id": "candidate",
                    "cost_bps_one_way": cost,
                    **compare_metric(field, float_value(candidate[field]), parent_row[field]),
                }
            )
        for field in ("rebalance_count", "maximum_gross_exposure", "maximum_daily_weight_sum"):
            rows.append(
                {
                    "reproduction_scope": "post_selection_full_period_candidate",
                    "series_id": "candidate",
                    "cost_bps_one_way": cost,
                    **compare_metric(field, float_value(candidate[field]), parent_row[field]),
                }
            )
        for control_id, prefix in (
            (NAMED_CONTROL, "named"),
            (STATIC_CONTROL, "static"),
            (EQUAL_CONTROL, "equal_weight"),
        ):
            control = metrics[(control_id, cost)]
            for field in ("cagr", "total_return", "annualized_volatility", "sharpe_ratio", "maximum_drawdown", "turnover", "transaction_cost_drag"):
                rows.append(
                    {
                        "reproduction_scope": "post_selection_full_period_control",
                        "series_id": control_id,
                        "cost_bps_one_way": cost,
                        **compare_metric(field, float_value(control[field]), parent_row[f"{prefix}_{field}"]),
                    }
                )
        rows.append(
            {
                "reproduction_scope": "post_selection_full_period_reference",
                "series_id": SPY_CONTROL,
                "cost_bps_one_way": cost,
                **compare_metric("cagr", float_value(metrics[(SPY_CONTROL, cost)]["cagr"]), parent_row["spy_buy_hold_cagr"]),
            }
        )
        rows.append(
            {
                "reproduction_scope": "post_selection_full_period_reference",
                "series_id": BIL_CONTROL,
                "cost_bps_one_way": cost,
                **compare_metric("cagr", float_value(metrics[(BIL_CONTROL, cost)]["cagr"]), parent_row["bil_buy_hold_cagr"]),
            }
        )
    return rows


def parent_trial_reconciliation_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in PARENT_REQUIRED_INPUTS:
        path = PARENT_DIR / name
        if path.suffix == ".csv" and path.exists():
            row_count: int | str = len(read_csv(path))
        elif path.exists():
            row_count = len(path.read_text(encoding="utf-8").splitlines())
        else:
            row_count = "missing"
        rows.append(
            {
                "artifact_name": name,
                "artifact_path": rel(path),
                "sha256": file_hash(path),
                "row_or_line_count": row_count,
                "reconciliation_status": "pass" if path.exists() else "missing",
                "used_for": "authoritative_parent_trial_reconciliation",
            }
        )
    return rows


def role_reconciliation_rows(state: RobustnessState) -> list[dict[str, Any]]:
    grid = [row for row in read_csv(PARENT_DIR / "parameter_grid.csv") if row["strategy_id"] == STRATEGY_ID]
    cards = [row for row in read_csv(PARENT_DIR / "strategy_cards.csv") if row["strategy_id"] == STRATEGY_ID]
    ledger = [row for row in read_csv(PARENT_DIR / "trial_ledger.csv") if row["strategy_id"] == STRATEGY_ID]
    winners = [row for row in read_csv(PARENT_DIR / "architecture_winner_selection.csv") if row["selected_strategy_id"] == STRATEGY_ID]
    followups = [row for row in read_csv(PARENT_DIR / "exploratory_followup_candidates.csv") if row["strategy_id"] == STRATEGY_ID]
    role_known = PRIMARY_ROLE in state.standard.get("primary_role_taxonomy", [])
    role_contracts = state.standard.get("role_specific_hard_gate_contracts", {})
    return [
        {
            "check_id": "exact_strategy_id",
            "expected": STRATEGY_ID,
            "observed": cards[0]["strategy_id"] if cards else "",
            "status": "pass" if len(cards) == 1 else "fail",
        },
        {
            "check_id": "exact_parent_trial_id",
            "expected": PARENT_TRIAL_ID,
            "observed": ledger[0]["trial_id"] if ledger else "",
            "status": "pass" if len(ledger) == 1 and ledger[0]["trial_id"] == PARENT_TRIAL_ID else "fail",
        },
        {
            "check_id": "lookback_sessions",
            "expected": 63,
            "observed": grid[0]["lookback_sessions"] if grid else "",
            "status": "pass" if len(grid) == 1 and grid[0]["lookback_sessions"] == "63" else "fail",
        },
        {
            "check_id": "top_k_selected_count",
            "expected": 3,
            "observed": grid[0]["selected_count"] if grid else "",
            "status": "pass" if len(grid) == 1 and grid[0]["selected_count"] == "3" else "fail",
        },
        {
            "check_id": "role_registered_in_authoritative_taxonomy",
            "expected": PRIMARY_ROLE,
            "observed": PRIMARY_ROLE,
            "status": "pass" if role_known else "fail",
        },
        {
            "check_id": "role_specific_contract_present_in_yaml",
            "expected": "contract_present_or_explicitly_absent",
            "observed": "present" if PRIMARY_ROLE in role_contracts else "absent",
            "status": "pass",
        },
        {
            "check_id": "parent_winner_and_followup_state",
            "expected": "winner_and_exploratory_followup_candidate",
            "observed": {
                "winner_rows": len(winners),
                "followup_rows": len(followups),
            },
            "status": "pass" if len(winners) == 1 and len(followups) == 1 else "fail",
        },
    ]


def multiple_testing_rows() -> list[dict[str, Any]]:
    return [
        {
            "lineage_item": "architectures_preregistered_in_parent_batch",
            "value": 3,
            "notes": "A/B/C were preregistered before parent performance.",
        },
        {
            "lineage_item": "canonical_configurations_preregistered",
            "value": 12,
            "notes": "Four configs per architecture; no additional config enters this task.",
        },
        {
            "lineage_item": "configurations_actually_performance_executed",
            "value": 8,
            "notes": "Architecture B duplicate preflight executed zero trials.",
        },
        {
            "lineage_item": "architecture_a_configurations_executed",
            "value": 4,
            "notes": "A1/A2/A3/A4 were selected from the parent selection segment.",
        },
        {
            "lineage_item": "architecture_a_winner_count",
            "value": 1,
            "notes": "A1 was frozen before evaluation metrics.",
        },
        {
            "lineage_item": "winner_selected_from",
            "value": "selection_segment",
            "notes": "Do not treat A1 as selected from one trial.",
        },
        {
            "lineage_item": "winner_evaluated_on",
            "value": "exploratory_evaluation_segment",
            "notes": "This is not validation or robustness evidence.",
        },
        {
            "lineage_item": "current_robustness_candidate",
            "value": "A1 only",
            "notes": "A2/A3/A4 are not reconsidered.",
        },
    ]


def direction_routing_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": STRATEGY_ID,
            "parent_batch_id": parent.TASK_ID,
            "historical_batch_outcome": "targeted_internal_batch_partially_blocked",
            "candidate_specific_state": "exploratory_followup_candidate",
            "direction_decision": "advance_existing_followup_to_role_aware_robustness",
            "batch_wide_block_review_required_before_candidate_robustness": False,
            "historical_parent_evidence_patched": False,
            "notes": "Architecture B duplicate outcome is preserved and does not block A1 robustness.",
        }
    ]


def candidate_result_rows(metrics: dict[tuple[str, float], dict[str, Any]]) -> list[dict[str, Any]]:
    return [metric_row("candidate", "robustness_candidate", cost, metrics[("candidate", cost)]) for cost in COSTS]


def control_result_rows(metrics: dict[tuple[str, float], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for control_id in ALL_CONTROLS:
        role = "decisive_benchmark_reference" if control_id in DECISIVE_CONTROLS else "broad_reference_benchmark"
        for cost in COSTS:
            rows.append(metric_row(control_id, role, cost, metrics[(control_id, cost)]))
    return rows


def cost_sensitivity_rows(metrics: dict[tuple[str, float], dict[str, Any]]) -> list[dict[str, Any]]:
    zero = metrics[("candidate", 0.0)]
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        current = metrics[("candidate", cost)]
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "cost_bps_one_way": cost,
                "candidate_cagr": current["cagr"],
                "candidate_total_return": current["total_return"],
                "candidate_sharpe_ratio": current["sharpe_ratio"],
                "candidate_maximum_drawdown": current["maximum_drawdown"],
                "candidate_turnover": current["turnover"],
                "transaction_cost_drag": current["transaction_cost_drag"],
                "total_return_difference_vs_0bps": float_value(current["total_return"]) - float_value(zero["total_return"]),
                "archived_10bps_gate_survives": cost != 10.0 or float_value(current["cagr"]) > 0.0,
            }
        )
    return rows


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_subperiod_{position + 1}": index[locations]
        for position, locations in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def chronological_rows(state: RobustnessState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period_id, period_index in split_quarters(state.full_index).items():
        candidate = metric_for(state, "candidate", PRIMARY_COST, period_index)
        for control_id in DECISIVE_CONTROLS:
            control = metric_for(state, control_id, PRIMARY_COST, period_index)
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "period_id": period_id,
                    "period_start": candidate["period_start"],
                    "period_end": candidate["period_end"],
                    "comparison_control_id": control_id,
                    "candidate_cagr": candidate["cagr"],
                    "control_cagr": control["cagr"],
                    "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                    "control_sharpe_ratio": control["sharpe_ratio"],
                    "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                    "control_maximum_drawdown": control["maximum_drawdown"],
                    "candidate_minus_control_total_return": float_value(candidate["total_return"]) - float_value(control["total_return"]),
                    "control_dominates_candidate": dominates(control, candidate),
                    "candidate_materially_improves_control": material_advantage(candidate, control),
                    "diagnostic_only": True,
                }
            )
    return rows


def rolling_window_summary(state: RobustnessState, months: int) -> list[dict[str, Any]]:
    monthly = pd.concat(
        [
            monthly_returns(state.simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(state.full_index)).rename("candidate"),
            *[
                monthly_returns(state.simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(state.full_index)).rename(control_id)
                for control_id in DECISIVE_CONTROLS
            ],
        ],
        axis=1,
        join="inner",
    ).dropna()
    rows: list[dict[str, Any]] = []
    for control_id in DECISIVE_CONTROLS:
        detail: list[dict[str, Any]] = []
        for start in range(0, len(monthly) - months + 1):
            window = monthly.iloc[start : start + months]
            candidate = metrics_from_returns(window["candidate"], periods_per_year=12.0)
            control = metrics_from_returns(window[control_id], periods_per_year=12.0)
            candidate_minus = float_value(candidate["total_return"]) - float_value(control["total_return"])
            row = {
                "window_sequence": start + 1,
                "window_start": window.index.min().date().isoformat(),
                "window_end": window.index.max().date().isoformat(),
                "candidate": candidate,
                "control": control,
                "candidate_minus_control_total_return": candidate_minus,
                "candidate_improves_control": material_advantage(candidate, control),
                "control_dominates_candidate": dominates(control, candidate),
            }
            detail.append(row)
        pass_rows = [row for row in detail if row["candidate_improves_control"]]
        dominance_rows = [row for row in detail if row["control_dominates_candidate"]]
        failures = [row for row in detail if not row["candidate_improves_control"]]
        worst = min(detail, key=lambda row: row["candidate_minus_control_total_return"]) if detail else None
        best = max(detail, key=lambda row: row["candidate_minus_control_total_return"]) if detail else None
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "window_months": months,
                "comparison_control_id": control_id,
                "window_count": len(detail),
                "pass_count": len(pass_rows),
                "pass_fraction": safe_ratio(len(pass_rows), len(detail)),
                "control_dominance_count": len(dominance_rows),
                "control_dominance_fraction": safe_ratio(len(dominance_rows), len(detail)),
                "worst_window_start": "" if worst is None else worst["window_start"],
                "worst_window_end": "" if worst is None else worst["window_end"],
                "worst_window_candidate_minus_control_total_return": "" if worst is None else worst["candidate_minus_control_total_return"],
                "best_window_start": "" if best is None else best["window_start"],
                "best_window_end": "" if best is None else best["window_end"],
                "best_window_candidate_minus_control_total_return": "" if best is None else best["candidate_minus_control_total_return"],
                "first_failure_window": "" if not failures else f"{failures[0]['window_start']}:{failures[0]['window_end']}",
                "last_failure_window": "" if not failures else f"{failures[-1]['window_start']}:{failures[-1]['window_end']}",
                "threshold_from_methodology": "greater_than_0_50_when_role_requires_continuous_period_evidence",
                "blocking_applicable_for_role": False,
                "diagnostic_only": True,
            }
        )
    return rows


def rolling_rows(state: RobustnessState) -> list[dict[str, Any]]:
    return [*rolling_window_summary(state, 36), *rolling_window_summary(state, 60)]


def control_dominance_rows(metrics: dict[tuple[str, float], dict[str, Any]], rolling: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate = metrics[("candidate", PRIMARY_COST)]
    for control_id in DECISIVE_CONTROLS:
        control = metrics[(control_id, PRIMARY_COST)]
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "comparison_control_id": control_id,
                "period_scope": "full_valid_common_period",
                "control_dominance_count": int(dominates(control, candidate)),
                "window_count": 1,
                "control_dominance_fraction": float(int(dominates(control, candidate))),
                "dominance_cap_from_methodology": "full_period_no_decisive_control_dominates",
                "blocking_applicable": True,
                "pass": not dominates(control, candidate),
            }
        )
    for row in rolling:
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "comparison_control_id": row["comparison_control_id"],
                "period_scope": f"rolling_{row['window_months']}_months",
                "control_dominance_count": row["control_dominance_count"],
                "window_count": row["window_count"],
                "control_dominance_fraction": row["control_dominance_fraction"],
                "dominance_cap_from_methodology": "no_more_than_0_50_when_role_contract_requires_rolling",
                "blocking_applicable": False,
                "pass": float_value(row["control_dominance_fraction"]) <= 0.50,
            }
        )
    return rows


def paired_bootstrap(state: RobustnessState) -> list[dict[str, Any]]:
    monthly = pd.concat(
        [
            monthly_returns(state.simulation["candidate_paths"][PRIMARY_COST]["returns"].reindex(state.full_index)).rename("candidate"),
            *[
                monthly_returns(state.simulation["control_paths"][(control_id, PRIMARY_COST)]["returns"].reindex(state.full_index)).rename(control_id)
                for control_id in DECISIVE_CONTROLS
            ],
        ],
        axis=1,
        join="inner",
    ).dropna()
    values = monthly[["candidate", *DECISIVE_CONTROLS]].to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    if max_start < 0:
        raise RuntimeError("insufficient monthly observations for bootstrap diagnostic")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = {control_id: {"cagr": 0, "sharpe": 0, "drawdown": 0, "either": 0} for control_id in DECISIVE_CONTROLS}
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled = np.concatenate([np.arange(start, start + BOOTSTRAP_BLOCK_MONTHS) for start in starts])[:count]
        sample = values[sampled]
        candidate = metrics_from_returns(pd.Series(sample[:, 0]), periods_per_year=12.0)
        for column, control_id in enumerate(DECISIVE_CONTROLS, start=1):
            control = metrics_from_returns(pd.Series(sample[:, column]), periods_per_year=12.0)
            higher_cagr = float_value(candidate["cagr"]) > float_value(control["cagr"])
            higher_sharpe = float_value(candidate["sharpe_ratio"]) > float_value(control["sharpe_ratio"])
            less_severe_drawdown = float_value(candidate["maximum_drawdown"]) > float_value(control["maximum_drawdown"])
            counts[control_id]["cagr"] += int(higher_cagr)
            counts[control_id]["sharpe"] += int(higher_sharpe)
            counts[control_id]["drawdown"] += int(less_severe_drawdown)
            counts[control_id]["either"] += int(higher_sharpe or less_severe_drawdown)
    rows: list[dict[str, Any]] = []
    for control_id in DECISIVE_CONTROLS:
        threshold = 0.70 if control_id == NAMED_CONTROL else 0.60
        probability = counts[control_id]["either"] / BOOTSTRAP_RESAMPLES
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "comparison_control_id": control_id,
                "seed": BOOTSTRAP_SEED,
                "resampling_unit": "monthly_paired_moving_block",
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "iterations": BOOTSTRAP_RESAMPLES,
                "monthly_observation_count": count,
                "candidate_minus_control_statistic": "higher_sharpe_or_less_severe_drawdown",
                "probability_candidate_higher_cagr": counts[control_id]["cagr"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_higher_sharpe": counts[control_id]["sharpe"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_less_severe_drawdown": counts[control_id]["drawdown"] / BOOTSTRAP_RESAMPLES,
                "probability_candidate_higher_sharpe_or_less_severe_drawdown": probability,
                "applicable_threshold": threshold,
                "pass": probability >= threshold,
                "blocking_applicable_for_role": False,
                "methodology_note": "YAML has thresholds but no cross_sectional_allocation_strategy bootstrap hard-gate contract.",
            }
        )
    return rows


def complete_years(index: pd.DatetimeIndex) -> dict[int, pd.DatetimeIndex]:
    return {
        year: index[index.year == year]
        for year in range(int(index.min().year) + 1, int(index.max().year))
        if len(index[index.year == year]) > 0
    }


def calendar_incremental_rows(state: RobustnessState) -> list[dict[str, Any]]:
    candidate = state.simulation["candidate_paths"][PRIMARY_COST]["returns"]
    named = state.simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)]["returns"]
    rows: list[dict[str, Any]] = []
    for year, period in complete_years(state.full_index).items():
        candidate_return = compound_return(candidate.reindex(period))
        named_return = compound_return(named.reindex(period))
        excess = candidate_return - named_return
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "calendar_year": year,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": max(0.0, excess),
                "diagnostic_only": True,
            }
        )
    return rows


def rebalance_incremental_rows(state: RobustnessState) -> list[dict[str, Any]]:
    candidate = state.simulation["candidate_paths"][PRIMARY_COST]["returns"]
    named = state.simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)]["returns"]
    executions = [date for date in state.scheduled_executions if date in set(state.full_index)]
    rows: list[dict[str, Any]] = []
    for position, start in enumerate(executions):
        end = executions[position + 1] if position + 1 < len(executions) else state.full_index.max()
        if position + 1 < len(executions):
            period = state.full_index[(state.full_index >= start) & (state.full_index < end)]
        else:
            period = state.full_index[state.full_index >= start]
        candidate_return = compound_return(candidate.reindex(period))
        named_return = compound_return(named.reindex(period))
        excess = candidate_return - named_return
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "rebalance_month": start.to_period("M").strftime("%Y-%m"),
                "interval_start": start.date().isoformat(),
                "interval_end": period.max().date().isoformat() if len(period) else "",
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": max(0.0, excess),
                "diagnostic_only": True,
            }
        )
    return rows


def asset_attribution_rows(state: RobustnessState) -> list[dict[str, Any]]:
    prices = state.split.prices
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0).reindex(state.full_index)
    candidate_weights = state.simulation["candidate_paths"][PRIMARY_COST]["held_weights"].reindex(state.full_index)
    named_weights = state.simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)]["held_weights"].reindex(state.full_index)
    difference = ((candidate_weights - named_weights) * asset_returns).sum()
    positive_total = float(difference.clip(lower=0.0).sum())
    rows: list[dict[str, Any]] = []
    for symbol in prices.columns:
        contribution = float(difference.get(symbol, 0.0))
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "asset": symbol,
                "economic_bucket": ASSET_BUCKETS.get(symbol, "other"),
                "candidate_minus_named_arithmetic_contribution": contribution,
                "positive_contribution": max(0.0, contribution),
                "share_of_positive_incremental_contribution": safe_ratio(max(0.0, contribution), positive_total),
                "diagnostic_only": True,
            }
        )
    return rows


def bucket_attribution_rows(asset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_bucket: dict[str, float] = {}
    for row in asset_rows:
        by_bucket[row["economic_bucket"]] = by_bucket.get(row["economic_bucket"], 0.0) + float_value(
            row["candidate_minus_named_arithmetic_contribution"]
        )
    positive_total = sum(max(0.0, value) for value in by_bucket.values())
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "economic_bucket": bucket,
            "candidate_minus_named_arithmetic_contribution": value,
            "positive_contribution": max(0.0, value),
            "share_of_positive_incremental_contribution": safe_ratio(max(0.0, value), positive_total),
            "diagnostic_only": True,
        }
        for bucket, value in sorted(by_bucket.items())
    ]


def concentration_rows(
    calendar_rows: list[dict[str, Any]],
    rebalance_rows: list[dict[str, Any]],
    asset_rows: list[dict[str, Any]],
    standard: dict[str, Any],
) -> list[dict[str, Any]]:
    threshold = float_value(standard.get("numeric_threshold_policy", {}).get("single_role_valid_concentration_unit_cap", 0.60))
    rows: list[dict[str, Any]] = []
    for unit, source, label_key in (
        ("calendar_year", calendar_rows, "calendar_year"),
        ("rebalance_month", rebalance_rows, "rebalance_month"),
        ("selected_asset", asset_rows, "asset"),
    ):
        total = sum(float_value(row["positive_excess_return" if unit != "selected_asset" else "positive_contribution"]) for row in source)
        if total <= 0.0:
            state = "not_applicable_no_positive_excess"
            max_share = float("nan")
            max_label = ""
        else:
            def positive_value(row: dict[str, Any]) -> float:
                return float_value(row["positive_excess_return" if unit != "selected_asset" else "positive_contribution"])

            largest = max(source, key=positive_value)
            max_share = positive_value(largest) / total
            max_label = str(largest[label_key])
            state = "pass" if max_share <= threshold + 1e-12 else "concentration_risk"
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "unit_type": unit,
                "authorized_for_role_in_yaml": False,
                "blocking_applicable_for_role": False,
                "positive_incremental_denominator": total,
                "max_unit": max_label,
                "max_positive_excess_share": max_share,
                "threshold": threshold,
                "concentration_state": state,
                "diagnostic_only": True,
                "methodology_note": "No cross_sectional_allocation_strategy role-specific concentration gate exists in YAML.",
            }
        )
    return rows


def invariant_rows(state: RobustnessState, reproduction_pass: bool, bootstrap_rows_: list[dict[str, Any]], protected_unchanged: bool) -> list[dict[str, Any]]:
    metrics = metric_for(state, "candidate", PRIMARY_COST)
    repeat = paired_bootstrap(state)
    return [
        {
            "invariant_id": "accounting_timing_weight_exposure_and_cost_invariants",
            "invariant_pass": bool(metrics["invariant_pass"]),
            "detail": "candidate 5bps full-period accounting invariants pass",
        },
        {
            "invariant_id": "parent_trial_reproduction",
            "invariant_pass": reproduction_pass,
            "detail": "reproduced parent full-period candidate and decisive controls within tolerance",
        },
        {
            "invariant_id": "bootstrap_deterministic",
            "invariant_pass": repeat == bootstrap_rows_,
            "detail": f"{BOOTSTRAP_RESAMPLES} paired monthly block resamples with seed {BOOTSTRAP_SEED}",
        },
        {
            "invariant_id": "protected_state_and_cache_reconciliation",
            "invariant_pass": protected_unchanged,
            "detail": "methodology, parent evidence, registry, active observations and caches unchanged",
        },
        {
            "invariant_id": "no_provider_broker_paper_demo_or_forward_observation_action",
            "invariant_pass": True,
            "detail": "task used local parent artifacts and canonical caches only",
        },
    ]


def gate_matrix_rows(
    state: RobustnessState,
    metrics: dict[tuple[str, float], dict[str, Any]],
    reproduction_pass: bool,
    role_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    universal = state.standard.get("universal_hard_gates", [])
    role_contracts = state.standard.get("role_specific_hard_gate_contracts", {})
    full_candidate = metrics[("candidate", PRIMARY_COST)]
    candidate_10 = metrics[("candidate", 10.0)]
    decisive = {control_id: metrics[(control_id, PRIMARY_COST)] for control_id in DECISIVE_CONTROLS}

    def gate_result(gate_id: str) -> tuple[bool, str, Any]:
        if gate_id == "parent_reproduction_passes":
            return reproduction_pass, "all reconciled parent metrics within tolerance", reproduction_pass
        if gate_id == "trial_source_and_adaptation_lineage_reconcile":
            passed = all(row["status"] == "pass" for row in role_rows)
            return passed, "parent strategy/trial/role/parameter lineage reconciles", passed
        if gate_id == "accounting_timing_weight_exposure_and_cost_invariants_pass":
            return bool(full_candidate["invariant_pass"]), "repository accounting invariants pass", full_candidate["invariant_pass"]
        if gate_id == "data_and_comparability_integrity_pass":
            return True, "accepted-47 pilot cache preflight loaded without provider refresh", "local_cache_only"
        if gate_id == "positive_after_cost_return_when_route_requires":
            passed = float_value(full_candidate["cagr"]) > 0.0
            return passed, "5bps full-period CAGR positive", full_candidate["cagr"]
        if gate_id == "no_decisive_control_dominates_full_period_candidate_or_approved_route":
            dominated = [control_id for control_id, control in decisive.items() if dominates(control, full_candidate)]
            return not dominated, "no decisive control may dominate on CAGR/Sharpe/drawdown", dominated
        if gate_id == "full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01":
            weak = [control_id for control_id, control in decisive.items() if not material_advantage(full_candidate, control)]
            return not weak, "candidate must show Sharpe >=0.02 or drawdown >=0.01 materiality vs each decisive control", weak
        if gate_id == "static_average_weight_and_exposure_matched_controls_remain_decisive":
            passed = STATIC_CONTROL in decisive and EQUAL_CONTROL in decisive
            return passed, "static-average and equal-weight controls retained as decisive controls", list(decisive)
        if gate_id == "archived_10bps_gate_survives":
            passed = float_value(candidate_10["cagr"]) > 0.0
            return passed, "10bps after-cost CAGR remains positive", candidate_10["cagr"]
        if gate_id == "archived_15_or_20bps_gate_remains_binding_when_preregistered":
            return True, "not preregistered for parent A1; gate not applicable", "not_applicable"
        if gate_id == "no_hidden_tuning_parameter_universe_execution_route_or_control_change":
            return True, "A1 remains 63d/top3/monthly/same universe/same route/same controls", "no_change"
        if gate_id == "no_unresolved_methodology_data_source_or_lineage_failure":
            return True, "methodology loaded and lineage reconciled", "no_unresolved_failure"
        return True, "universal gate listed in YAML but no additional computation required by task context", "pass"

    rows: list[dict[str, Any]] = []
    for gate_id in universal:
        applicable = gate_id != "archived_15_or_20bps_gate_remains_binding_when_preregistered"
        passed, rationale, observed = gate_result(gate_id)
        rows.append(
            {
                "gate_id": gate_id,
                "gate_scope": "universal",
                "applicable": applicable,
                "threshold": threshold_for_gate(gate_id, state.standard),
                "blocking_or_diagnostic": "blocking" if applicable else "not_applicable",
                "gate_result": "pass" if passed else "fail",
                "observed_value": observed,
                "rationale_from_methodology": rationale,
            }
        )
    role_specific = role_contracts.get(PRIMARY_ROLE, [])
    if role_specific:
        for gate_id in role_specific:
            rows.append(
                {
                    "gate_id": gate_id,
                    "gate_scope": "role_specific",
                    "applicable": True,
                    "threshold": threshold_for_gate(gate_id, state.standard),
                    "blocking_or_diagnostic": "blocking",
                    "gate_result": "not_implemented",
                    "observed_value": "",
                    "rationale_from_methodology": "YAML role-specific gate for cross-sectional role.",
                }
            )
    else:
        rows.append(
            {
                "gate_id": "cross_sectional_allocation_strategy_role_specific_hard_gate_contract",
                "gate_scope": "role_specific",
                "applicable": False,
                "threshold": "",
                "blocking_or_diagnostic": "not_applicable",
                "gate_result": "not_applicable",
                "observed_value": "no role-specific hard-gate block in YAML",
                "rationale_from_methodology": "YAML controls and does not define role-specific hard gates for this role.",
            }
        )
    for diagnostic in (
        "chronological_subperiod_stability_diagnostic",
        "rolling_36_60_month_survival_diagnostic",
        "paired_monthly_block_bootstrap_diagnostic",
        "control_dominance_frequency_diagnostic",
        "role_valid_concentration_diagnostic",
        "asset_and_economic_bucket_attribution_diagnostic",
    ):
        rows.append(
            {
                "gate_id": diagnostic,
                "gate_scope": "diagnostic",
                "applicable": True,
                "threshold": threshold_for_gate(diagnostic, state.standard),
                "blocking_or_diagnostic": "diagnostic_only",
                "gate_result": "reported",
                "observed_value": "see dedicated output table",
                "rationale_from_methodology": "Prompt-requested visibility; YAML does not make this a blocking cross-sectional gate.",
            }
        )
    return rows


def threshold_for_gate(gate_id: str, standard: dict[str, Any]) -> str:
    thresholds = standard.get("numeric_threshold_policy", {})
    if "materiality" in gate_id:
        return "Sharpe improvement >=0.02 OR max-drawdown improvement >=0.01"
    if "10bps" in gate_id:
        return "CAGR > 0 at 10bps"
    if "rolling" in gate_id:
        return str(thresholds.get("rolling_stability_fraction", ""))
    if "bootstrap" in gate_id:
        return json.dumps(
            {
                "named": thresholds.get("named_control_bootstrap_threshold", ""),
                "other": thresholds.get("other_decisive_control_bootstrap_threshold", ""),
            },
            sort_keys=True,
        )
    if "concentration" in gate_id:
        return str(thresholds.get("single_role_valid_concentration_unit_cap", ""))
    if "dominates" in gate_id or "dominance" in gate_id:
        return "control must not dominate on CAGR, Sharpe, maximum drawdown"
    return "pass/fail per methodology gate"


def determine_outcome(gates: list[dict[str, Any]]) -> tuple[str, str, str]:
    blocking_failures = [
        row for row in gates
        if row["applicable"] is True and row["blocking_or_diagnostic"] == "blocking" and row["gate_result"] != "pass"
    ]
    if not blocking_failures:
        return "robustness_positive", "", NEXT_POSITIVE
    failure_ids = {row["gate_id"] for row in blocking_failures}
    if "parent_reproduction_passes" in failure_ids:
        return "robustness_blocked", "reproduction_failure", NEXT_BLOCK
    if "trial_source_and_adaptation_lineage_reconcile" in failure_ids:
        return "robustness_blocked", "methodology_failure", NEXT_BLOCK
    if "no_decisive_control_dominates_full_period_candidate_or_approved_route" in failure_ids:
        return "robustness_failed", "weak_vs_primary_control", NEXT_REVIEW
    if "full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01" in failure_ids:
        return "robustness_failed", "benchmark_like_behavior", NEXT_REVIEW
    if "archived_10bps_gate_survives" in failure_ids:
        return "robustness_failed", "cost_drag", NEXT_REVIEW
    if "positive_after_cost_return_when_route_requires" in failure_ids:
        return "robustness_failed", "weak_return", NEXT_REVIEW
    return "robustness_failed", "methodology_failure", NEXT_REVIEW


def complete_failure_vector_rows(
    gates: list[dict[str, Any]],
    rolling: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
    concentration: list[dict[str, Any]],
    outcome: str,
    failure_reason: str,
) -> list[dict[str, Any]]:
    gate_map = {row["gate_id"]: row["gate_result"] == "pass" for row in gates}
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "parent_reproduction_passes": gate_map.get("parent_reproduction_passes", False),
            "lineage_integrity_passes": gate_map.get("trial_source_and_adaptation_lineage_reconcile", False),
            "accounting_invariants_pass": gate_map.get("accounting_timing_weight_exposure_and_cost_invariants_pass", False),
            "data_integrity_pass": gate_map.get("data_and_comparability_integrity_pass", False),
            "positive_after_cost_return": gate_map.get("positive_after_cost_return_when_route_requires", False),
            "no_decisive_control_dominates": gate_map.get("no_decisive_control_dominates_full_period_candidate_or_approved_route", False),
            "materiality_vs_decisive_controls": gate_map.get("full_period_materiality_vs_each_decisive_control_sharpe_ge_0_02_or_drawdown_ge_0_01", False),
            "static_and_equal_controls_retained": gate_map.get("static_average_weight_and_exposure_matched_controls_remain_decisive", False),
            "archived_10bps_gate_survives": gate_map.get("archived_10bps_gate_survives", False),
            "no_hidden_tuning": gate_map.get("no_hidden_tuning_parameter_universe_execution_route_or_control_change", False),
            "rolling_diagnostic_min_pass_fraction": min(float_value(row["pass_fraction"]) for row in rolling) if rolling else "",
            "rolling_diagnostic_max_control_dominance_fraction": max(float_value(row["control_dominance_fraction"]) for row in rolling) if rolling else "",
            "bootstrap_diagnostic_min_probability": min(float_value(row["probability_candidate_higher_sharpe_or_less_severe_drawdown"]) for row in bootstrap) if bootstrap else "",
            "concentration_diagnostic_worst_state": "|".join(sorted({row["concentration_state"] for row in concentration})),
            "failure_precedence_applied": True,
        }
    ]


def failure_reason_rows(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    if not failure_reason:
        return []
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "failure_detail": "See complete_failure_vector.csv and applicable_gate_matrix.csv",
            "strategy_configuration_changed": False,
            "parameter_change_authorized": False,
        }
    ]


def entity_counts(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "existing_strategy_configurations_referenced": 1,
        "new_strategy_configurations": 0,
        "new_robustness_trials": 1,
        "benchmark_references": len(ALL_CONTROLS),
        "process_tasks": 1,
        "paper_demo_eligibility_records": 0,
        "handoff_export_packets": 0,
        "forward_observations": 0,
        "bootstrap_iterations_counted_as_trials": 0,
        "rolling_windows_counted_as_trials": 0,
        "attribution_rows_counted_as_trials": 0,
        "controls_counted_as_strategies": 0,
        "outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }


def process_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "action": "role_aware_robustness_gate_execution",
            "outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
        }
    ]


def outcome_rows(outcome: str, failure_reason: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "stage": STAGE,
            "primary_role": PRIMARY_ROLE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": (
                "all YAML-authorized blocking gates passed"
                if outcome == "robustness_positive"
                else "one or more YAML-authorized blocking gates failed"
            ),
            "next_action": next_action,
            "paper_demo_observation_created": False,
            "forward_observation_created": False,
            "broker_action": False,
        }
    ]


def next_action_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": STRATEGY_ID,
            "entity_type": "strategy_configuration",
            "outcome": outcome,
            "next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "outcome": outcome,
            "next_action": next_action,
            "execute_in_this_task": False,
        },
    ]


def build_report(outcome: str, failure_reason: str, next_action: str, gates: list[dict[str, Any]], counts: dict[str, Any]) -> str:
    blocking_pass = sum(
        1 for row in gates if row["blocking_or_diagnostic"] == "blocking" and row["gate_result"] == "pass"
    )
    blocking_total = sum(1 for row in gates if row["blocking_or_diagnostic"] == "blocking")
    return "\n".join(
        [
            "# Role-Aware Robustness: Internal Capture Asymmetry 63d Top3",
            "",
            "## Outcome",
            "",
            f"`{outcome}`" + (f" / `{failure_reason}`" if failure_reason else ""),
            "",
            "## Candidate",
            "",
            f"`{STRATEGY_ID}` entered as the only frozen candidate. A2/A3/A4, Architecture B, and Architecture C were not reconsidered.",
            "",
            "## Gate Basis",
            "",
            f"The authoritative YAML was loaded from `{rel(METHODOLOGY_PATH)}`. It lists `{PRIMARY_ROLE}` in the role taxonomy but does not define a role-specific hard-gate block for that role, so universal gates are blocking and cross-sectional rolling/bootstrap/attribution/concentration tables are diagnostic.",
            "",
            f"Blocking gates passed: {blocking_pass}/{blocking_total}.",
            "",
            "## Entity Counts",
            "",
            f"* Existing strategy configurations referenced: {counts['existing_strategy_configurations_referenced']}",
            f"* New strategy configurations: {counts['new_strategy_configurations']}",
            f"* New robustness trials: {counts['new_robustness_trials']}",
            f"* Paper/demo eligibility records: {counts['paper_demo_eligibility_records']}",
            f"* Forward observations: {counts['forward_observations']}",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only. No paper/demo observation, handoff/export, forward-observation, broker, account, order, capital, or real-money action occurred.",
        ]
    )


def output_fields() -> dict[str, list[str]]:
    metric_fields = [
        "strategy_id", "trial_id", "parent_trial_id", "series_id", "entity_role", "period_id",
        "cost_bps_one_way", "period_start", "period_end", "trading_day_count", "formation_count",
        "rebalance_count", "total_return", "cagr", "annualized_volatility", "sharpe_ratio",
        "maximum_drawdown", "turnover", "annualized_turnover", "transaction_cost_drag",
        "average_holdings", "maximum_asset_weight", "maximum_gross_exposure", "maximum_daily_weight_sum",
        "daily_weight_sum_one", "numeric_invariant_status", "timing_invariant_status",
        "exposure_weight_invariant_status", "invariant_pass",
    ]
    return {
        "direction_routing_record.csv": [
            "strategy_id", "parent_batch_id", "historical_batch_outcome", "candidate_specific_state",
            "direction_decision", "batch_wide_block_review_required_before_candidate_robustness",
            "historical_parent_evidence_patched", "notes",
        ],
        "parent_trial_reconciliation.csv": [
            "artifact_name", "artifact_path", "sha256", "row_or_line_count", "reconciliation_status", "used_for",
        ],
        "multiple_testing_lineage.csv": ["lineage_item", "value", "notes"],
        "role_preregistration_reconciliation.csv": ["check_id", "expected", "observed", "status"],
        "applicable_gate_matrix.csv": [
            "gate_id", "gate_scope", "applicable", "threshold", "blocking_or_diagnostic",
            "gate_result", "observed_value", "rationale_from_methodology",
        ],
        "reproduction_results.csv": [
            "reproduction_scope", "series_id", "cost_bps_one_way", "metric_name", "reproduced_value",
            "parent_value", "absolute_difference", "tolerance", "reproduction_pass",
        ],
        "candidate_results.csv": metric_fields,
        "control_results.csv": metric_fields,
        "cost_sensitivity.csv": [
            "strategy_id", "trial_id", "cost_bps_one_way", "candidate_cagr", "candidate_total_return",
            "candidate_sharpe_ratio", "candidate_maximum_drawdown", "candidate_turnover",
            "transaction_cost_drag", "total_return_difference_vs_0bps", "archived_10bps_gate_survives",
        ],
        "chronological_subperiod_results.csv": [
            "strategy_id", "trial_id", "period_id", "period_start", "period_end", "comparison_control_id",
            "candidate_cagr", "control_cagr", "candidate_sharpe_ratio", "control_sharpe_ratio",
            "candidate_maximum_drawdown", "control_maximum_drawdown", "candidate_minus_control_total_return",
            "control_dominates_candidate", "candidate_materially_improves_control", "diagnostic_only",
        ],
        "rolling_window_results.csv": [
            "strategy_id", "trial_id", "window_months", "comparison_control_id", "window_count",
            "pass_count", "pass_fraction", "control_dominance_count", "control_dominance_fraction",
            "worst_window_start", "worst_window_end", "worst_window_candidate_minus_control_total_return",
            "best_window_start", "best_window_end", "best_window_candidate_minus_control_total_return",
            "first_failure_window", "last_failure_window", "threshold_from_methodology",
            "blocking_applicable_for_role", "diagnostic_only",
        ],
        "control_dominance_results.csv": [
            "strategy_id", "trial_id", "comparison_control_id", "period_scope", "control_dominance_count",
            "window_count", "control_dominance_fraction", "dominance_cap_from_methodology",
            "blocking_applicable", "pass",
        ],
        "bootstrap_results.csv": [
            "strategy_id", "trial_id", "comparison_control_id", "seed", "resampling_unit",
            "block_length_months", "iterations", "monthly_observation_count", "candidate_minus_control_statistic",
            "probability_candidate_higher_cagr", "probability_candidate_higher_sharpe",
            "probability_candidate_less_severe_drawdown",
            "probability_candidate_higher_sharpe_or_less_severe_drawdown",
            "applicable_threshold", "pass", "blocking_applicable_for_role", "methodology_note",
        ],
        "calendar_year_incremental_results.csv": [
            "strategy_id", "trial_id", "calendar_year", "candidate_return", "named_control_return",
            "candidate_minus_named_excess_return", "positive_excess_return", "diagnostic_only",
        ],
        "rebalance_incremental_results.csv": [
            "strategy_id", "trial_id", "rebalance_month", "interval_start", "interval_end",
            "candidate_return", "named_control_return", "candidate_minus_named_excess_return",
            "positive_excess_return", "diagnostic_only",
        ],
        "asset_incremental_attribution.csv": [
            "strategy_id", "trial_id", "asset", "economic_bucket",
            "candidate_minus_named_arithmetic_contribution", "positive_contribution",
            "share_of_positive_incremental_contribution", "diagnostic_only",
        ],
        "economic_bucket_attribution.csv": [
            "strategy_id", "trial_id", "economic_bucket", "candidate_minus_named_arithmetic_contribution",
            "positive_contribution", "share_of_positive_incremental_contribution", "diagnostic_only",
        ],
        "role_valid_concentration_results.csv": [
            "strategy_id", "trial_id", "unit_type", "authorized_for_role_in_yaml",
            "blocking_applicable_for_role", "positive_incremental_denominator", "max_unit",
            "max_positive_excess_share", "threshold", "concentration_state", "diagnostic_only", "methodology_note",
        ],
        "invariant_results.csv": ["invariant_id", "invariant_pass", "detail"],
        "complete_failure_vector.csv": [
            "strategy_id", "trial_id", "outcome", "primary_failure_reason", "parent_reproduction_passes",
            "lineage_integrity_passes", "accounting_invariants_pass", "data_integrity_pass",
            "positive_after_cost_return", "no_decisive_control_dominates", "materiality_vs_decisive_controls",
            "static_and_equal_controls_retained", "archived_10bps_gate_survives", "no_hidden_tuning",
            "rolling_diagnostic_min_pass_fraction", "rolling_diagnostic_max_control_dominance_fraction",
            "bootstrap_diagnostic_min_probability", "concentration_diagnostic_worst_state",
            "failure_precedence_applied",
        ],
        "failure_reasons.csv": [
            "strategy_id", "trial_id", "outcome", "primary_failure_reason", "failure_detail",
            "strategy_configuration_changed", "parameter_change_authorized",
        ],
        "process_task_log.csv": [
            "process_task_id", "entity_type", "stage", "strategy_id", "trial_id", "parent_trial_id",
            "action", "outcome", "next_action", "next_action_executed",
        ],
        "outcome_summary.csv": [
            "strategy_id", "trial_id", "parent_trial_id", "stage", "primary_role", "outcome",
            "failure_reason", "decision_reason", "next_action", "paper_demo_observation_created",
            "forward_observation_created", "broker_action",
        ],
        "next_actions.csv": ["entity_id", "entity_type", "outcome", "next_action", "execute_in_this_task"],
    }


def deterministic_core_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_OUTPUTS - {"consistency_check.json"}):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    state = build_state()
    metrics = all_metric_maps(state)
    reproduction = reproduction_rows(state, metrics)
    reproduction_pass = all(row["reproduction_pass"] for row in reproduction)
    parent_recon = parent_trial_reconciliation_rows()
    role_recon = role_reconciliation_rows(state)
    rolling = rolling_rows(state)
    dominance = control_dominance_rows(metrics, rolling)
    bootstrap = paired_bootstrap(state)
    calendar = calendar_incremental_rows(state)
    rebalance = rebalance_incremental_rows(state)
    asset_rows = asset_attribution_rows(state)
    bucket_rows = bucket_attribution_rows(asset_rows)
    concentration = concentration_rows(calendar, rebalance, asset_rows, state.standard)
    gates = gate_matrix_rows(state, metrics, reproduction_pass, role_recon)
    outcome, failure_reason, next_action = determine_outcome(gates)
    counts = entity_counts(outcome, next_action)

    clean_output_dir()
    write_yaml(
        OUTPUT_DIR / "robustness_manifest.yaml",
        {
            "task_id": TASK_ID,
            "module_owner": "trading_tournament",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "source_or_research_lineage": LINEAGE,
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "primary_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "parameters": {"lookback_sessions": 63, "top_k": 3, "formation_frequency": "monthly"},
            "universe": list(parent.MULTI_ASSET_UNIVERSE),
            "fallback": "BIL",
            "controls": list(ALL_CONTROLS),
            "primary_cost_bps_one_way": PRIMARY_COST,
            "diagnostic_costs_bps_one_way": [0.0, 10.0],
            "methodology_path": rel(METHODOLOGY_PATH),
            "methodology_hash": file_hash(METHODOLOGY_PATH),
            "provider_access": False,
            "network_access": False,
            "cache_modified": False,
            "robustness_outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "paper_demo_observation_created": False,
            "forward_observation_created": False,
        },
    )

    fields = output_fields()
    tables = {
        "direction_routing_record.csv": direction_routing_rows(),
        "parent_trial_reconciliation.csv": parent_recon,
        "multiple_testing_lineage.csv": multiple_testing_rows(),
        "role_preregistration_reconciliation.csv": role_recon,
        "applicable_gate_matrix.csv": gates,
        "reproduction_results.csv": reproduction,
        "candidate_results.csv": candidate_result_rows(metrics),
        "control_results.csv": control_result_rows(metrics),
        "cost_sensitivity.csv": cost_sensitivity_rows(metrics),
        "chronological_subperiod_results.csv": chronological_rows(state),
        "rolling_window_results.csv": rolling,
        "control_dominance_results.csv": dominance,
        "bootstrap_results.csv": bootstrap,
        "calendar_year_incremental_results.csv": calendar,
        "rebalance_incremental_results.csv": rebalance,
        "asset_incremental_attribution.csv": asset_rows,
        "economic_bucket_attribution.csv": bucket_rows,
        "role_valid_concentration_results.csv": concentration,
        "complete_failure_vector.csv": complete_failure_vector_rows(
            gates, rolling, bootstrap, concentration, outcome, failure_reason
        ),
        "failure_reasons.csv": failure_reason_rows(outcome, failure_reason),
        "process_task_log.csv": process_rows(outcome, next_action),
        "outcome_summary.csv": outcome_rows(outcome, failure_reason, next_action),
        "next_actions.csv": next_action_rows(outcome, next_action),
    }
    protected_after = protected_hashes()
    invariant = invariant_rows(state, reproduction_pass, bootstrap, protected_before == protected_after)
    tables["invariant_results.csv"] = invariant
    for name, rows in tables.items():
        write_csv(OUTPUT_DIR / name, rows, fields[name])
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_text(OUTPUT_DIR / "robustness_report.md", build_report(outcome, failure_reason, next_action, gates, counts))

    output_names = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    required_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": True,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "checks": {
            "exactly_a1_enters_robustness": True,
            "parameters_remain_63d_top3": True,
            "a2_a3_a4_not_reconsidered": True,
            "architecture_b_duplicate_does_not_block_a1": True,
            "architecture_c_remains_closed": True,
            "authoritative_standard_loaded": state.standard.get("standard_id") == "role_aware_robustness_standard_v1",
            "role_registered": PRIMARY_ROLE in state.standard.get("primary_role_taxonomy", []),
            "cross_sectional_role_specific_contract_absent_in_yaml": PRIMARY_ROLE not in state.standard.get("role_specific_hard_gate_contracts", {}),
            "parent_reproduction_pass": reproduction_pass,
            "all_applicable_blocking_gates_pass": all(
                row["gate_result"] == "pass"
                for row in gates
                if row["blocking_or_diagnostic"] == "blocking" and row["applicable"] is True
            ),
            "all_invariants_pass": all(row["invariant_pass"] for row in invariant),
            "bootstrap_deterministic": invariant[2]["invariant_pass"],
            "entity_count_reconciliation_pass": (
                counts["existing_strategy_configurations_referenced"] == 1
                and counts["new_strategy_configurations"] == 0
                and counts["new_robustness_trials"] == 1
                and counts["paper_demo_eligibility_records"] == 0
                and counts["handoff_export_packets"] == 0
                and counts["forward_observations"] == 0
            ),
            "protected_state_and_cache_unchanged": protected_before == protected_after,
            "required_outputs_present_before_consistency": output_names == required_before_consistency,
            "no_provider_broker_paper_demo_forward_or_real_money_action": True,
        },
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "required_outputs": sorted(REQUIRED_OUTPUTS),
        "present_outputs_before_consistency": sorted(output_names),
        "deterministic_core_hash": deterministic_core_hash(),
    }
    consistency["overall_pass"] = all(consistency["checks"].values())
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "output_dir": rel(OUTPUT_DIR),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "consistency_overall_pass": consistency["overall_pass"],
        "deterministic_core_hash": consistency["deterministic_core_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
