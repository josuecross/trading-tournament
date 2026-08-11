from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1 as parent


TASK_ID = "run_spdj_dynamic_inflation_robustness_v1"
STRATEGY_ID = parent.STRATEGY_ID
FAMILY_ID = parent.FAMILY_ID
ARCHITECTURE_ID = parent.ARCHITECTURE_ID
PARENT_TRIAL_ID = parent.TRIAL_ID
ROBUSTNESS_TRIAL_ID = f"{TASK_ID}__robustness"
PARENT_EVIDENCE_HASH = "sha256:0f3cff1fbed4af952e5264fb60d21b4f0bdec2d7080bb3d16c356bef3e9ccea9"
PARENT_CODE_HASH = "sha256:55eff61ee55999df76d023e570440197c7dbf0d05da41775cf23671dbd15b1e4"
PRICE_BUNDLE_HASH = "sha256:ab05bef8ac2b12c6391bca65cb1312148db7d64bed11e9932379464f8bcc72c8"
V2_HASH = parent.V2_EXPECTED_HASH
UNIVERSE_HASH = parent.UNIVERSE_EXPECTED_HASH
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-10
BOOTSTRAP_BLOCK_MONTHS = 12
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260810
ROLLING_MONTHS = 36
ROLLING_STEP_MONTHS = 12
TIMING_DELAYS = (1, 2)
PARETO_TOLERANCE = 1e-10

NAMED_CONTROL = parent.NAMED_CONTROL
EQUAL_CONTROL = parent.EQUAL_CONTROL
DIAGNOSTIC_CONTROL = parent.DIAGNOSTIC_CONTROL
BLOCKING_CONTROLS = (NAMED_CONTROL, EQUAL_CONTROL)

OUTCOME_PASS = "spdj_dynamic_inflation_robustness_passed"
OUTCOME_FAIL = "spdj_dynamic_inflation_robustness_failed"
OUTCOME_BLOCK = "spdj_dynamic_inflation_robustness_blocked"
NEXT_PASS = "assess_spdj_dynamic_inflation_research_eligibility_v1"
NEXT_FAIL = "direction_owner_review_spdj_dynamic_inflation_robustness_failure_v1"
NEXT_BLOCK = "direction_owner_review_spdj_dynamic_inflation_robustness_blocker_v1"

PARENT_DIR = parent.OUTPUT_DIR
OUTPUT_DIR = ROOT / "evidence" / "robustness" / "spdj_dynamic_inflation_robustness_v1" / "latest"
PARENT_CODE_PATH = Path(parent.__file__)

PROTECTED_PATHS = (
    PARENT_DIR,
    PARENT_CODE_PATH,
    parent.V1_DIR,
    parent.V2_DIR,
    parent.V1_EVIDENCE_DIR,
    parent.V2_EVIDENCE_DIR,
    parent.INTAKE_DIR,
    parent.UNIVERSE_DIR,
    parent.PHASE2_CACHE,
    parent.PILOT_CACHE,
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations",
    ROOT / "paper_forward_observation_plans",
)

REQUIRED_OUTPUTS = {
    "robustness_preregistration.json",
    "robustness_report.md",
    "parent_reproduction.csv",
    "cost_robustness.csv",
    "chronological_block_results.csv",
    "rolling_window_results.csv",
    "bootstrap_summary.json",
    "bootstrap_control_comparison.csv",
    "regime_attribution.csv",
    "transition_attribution.csv",
    "timing_sensitivity.csv",
    "control_information_set_audit.csv",
    "robustness_gate_results.json",
    "trial_accounting.json",
    "consistency_check.json",
    "next_action.md",
}

FORBIDDEN_ADAPTATIONS = (
    "threshold_perturbation",
    "alternative_CPI_series",
    "rounded_CPI_signal",
    "alternative_lookback_or_warmup",
    "alternative_ETF_mapping",
    "trade_management_overlay",
    "parameter_optimization",
    "new_strategy_variant",
)


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, pd.Period)):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_value(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str] | None = None) -> None:
    materialized = list(rows)
    if fields is None:
        ordered: list[str] = []
        for row in materialized:
            for field in row:
                if field not in ordered:
                    ordered.append(field)
        fields = ordered
    field_list = list(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: csv_value(row.get(field, "")) for field in field_list})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(json_value(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def hash_tree(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_path(path)
    digest = hashlib.sha256()
    for item in sorted(child for child in path.rglob("*") if child.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_snapshot() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): hash_tree(path) for path in PROTECTED_PATHS}


def packet_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name != "consistency_check.json"):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def pareto_dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    sharpe_at_least = float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - PARETO_TOLERANCE
    drawdown_at_least = float(control["maximum_drawdown"]) >= float(candidate["maximum_drawdown"]) - PARETO_TOLERANCE
    strict = (
        float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + PARETO_TOLERANCE
        or float(control["maximum_drawdown"]) > float(candidate["maximum_drawdown"]) + PARETO_TOLERANCE
    )
    return bool(sharpe_at_least and drawdown_at_least and strict)


def monthly_metrics(values: np.ndarray | pd.Series) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    if not len(data):
        raise ValueError("monthly metrics require observations")
    wealth = np.cumprod(1.0 + data)
    standard_deviation = float(np.std(data, ddof=1)) if len(data) > 1 else 0.0
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    return {
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / len(data)) - 1.0),
        "annualized_volatility": standard_deviation * math.sqrt(12.0),
        "sharpe_ratio": float(np.mean(data) / standard_deviation * math.sqrt(12.0)) if standard_deviation > 0.0 else 0.0,
        "maximum_drawdown": float(drawdown.min()),
    }


def control_targets(prepared: dict[str, Any]) -> dict[str, pd.DataFrame]:
    dates = prepared["targets"].index
    named = parent.control_targets(dates, parent.low_weights())
    equal = parent.control_targets(dates, {symbol: 1.0 / 6.0 for symbol in parent.SYMBOLS})
    average = {symbol: float(prepared["targets"][symbol].mean()) for symbol in parent.SYMBOLS}
    diagnostic = parent.control_targets(dates, average)
    return {NAMED_CONTROL: named, EQUAL_CONTROL: equal, DIAGNOSTIC_CONTROL: diagnostic}


def build_parent_context() -> dict[str, Any]:
    parent_consistency = json.loads((PARENT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    parent_trial = json.loads((PARENT_DIR / "trial_manifest.json").read_text(encoding="utf-8"))
    correction = json.loads((PARENT_DIR / "implementation_correction_log.json").read_text(encoding="utf-8"))
    source = json.loads((PARENT_DIR / "source_conformance.json").read_text(encoding="utf-8"))
    lineage_checks = {
        "parent_outcome_matches": parent_consistency["outcome"] == parent.OUTCOME_FOLLOWUP,
        "parent_evidence_hash_matches": parent_consistency["deterministic_evidence_hash"] == PARENT_EVIDENCE_HASH,
        "parent_trial_id_matches": parent_trial["canonical_trial_id"] == PARENT_TRIAL_ID,
        "parent_trial_count_one": parent_trial["canonical_trial_count"] == 1,
        "corrected_code_hash_matches_manifest": parent_trial["code_hash"] == PARENT_CODE_HASH,
        "corrected_code_hash_matches_file": sha256_path(PARENT_CODE_PATH) == PARENT_CODE_HASH,
        "correction_type_matches": correction["correction_type"] == "source_contract_preserving_implementation_defect_correction",
        "correction_defect_matches": correction["defect"] == "fully_invested_invariant_incorrectly_included_the_pre_initialization_holdings_row",
        "correction_did_not_change_rule_or_trial": not correction["strategy_rule_changed"] and not correction["trial_id_changed"],
        "correction_not_performance_selected": not correction["performance_result_used_to_choose_correction"],
        "invalidated_evidence_preserved": correction["invalidated_selection_results_preserved"],
        "source_conformance_passed": source["all_preperformance_checks_pass"] is True,
    }
    if not all(lineage_checks.values()):
        raise RuntimeError("parent_lineage_or_hash_failure")
    v2 = parent.verify_v2()
    prices, preflight, price_contract = parent.load_prices()
    if v2["observed_hash"] != V2_HASH:
        raise RuntimeError("frozen_signal_hash_mismatch")
    if price_contract["frozen_price_data_bundle_hash"] != PRICE_BUNDLE_HASH:
        raise RuntimeError("frozen_price_bundle_hash_mismatch")
    if price_contract["universe_hash"] != UNIVERSE_HASH:
        raise RuntimeError("frozen_universe_hash_mismatch")
    signal = parent.load_signal()
    prepared = parent.build_signals(prices, signal)
    split = parent.build_split(prices, prepared["targets"])
    controls = control_targets(prepared)
    targets = {"candidate": prepared["targets"], **controls}
    selection_paths: dict[tuple[str, float], dict[str, Any]] = {}
    full_paths: dict[tuple[str, float], dict[str, Any]] = {}
    selection_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    evaluation_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    selection_end = split.selection_index.max()
    for cost in COSTS:
        for entity, target in targets.items():
            selection_path = parent.simulate(prices, target, cost, end=selection_end)
            full_path = parent.simulate(prices, target, cost)
            selection_paths[(entity, cost)] = selection_path
            full_paths[(entity, cost)] = full_path
            selection_metrics[(entity, cost)] = parent.path_metrics(
                selection_path,
                split.selection_index,
                prepared["event_regimes"] if entity == "candidate" else {},
            )
            evaluation_metrics[(entity, cost)] = parent.path_metrics(
                full_path,
                split.evaluation_index,
                prepared["event_regimes"] if entity == "candidate" else {},
            )
    midpoint = len(split.evaluation_index) // 2
    halves_pass = True
    for period in (split.evaluation_index[:midpoint], split.evaluation_index[midpoint:]):
        candidate_half = parent.path_metrics(full_paths[("candidate", PRIMARY_COST)], period, prepared["event_regimes"])
        named_half = parent.path_metrics(full_paths[(NAMED_CONTROL, PRIMARY_COST)], period, {})
        if (
            candidate_half["sharpe_ratio"] < named_half["sharpe_ratio"] - parent.TOLERANCE
            and candidate_half["maximum_drawdown"] < named_half["maximum_drawdown"] - parent.TOLERANCE
        ):
            halves_pass = False
    original_selection_gate = parent.selection_vector(
        {key: value for key, value in selection_metrics.items() if key[0] != DIAGNOSTIC_CONTROL}
    )
    original_evaluation_gate = parent.evaluation_vector(
        {key: value for key, value in evaluation_metrics.items() if key[0] != DIAGNOSTIC_CONTROL},
        halves_pass,
    )
    return {
        "parent_consistency": parent_consistency,
        "parent_trial": parent_trial,
        "correction": correction,
        "source": source,
        "lineage_checks": lineage_checks,
        "v2": v2,
        "prices": prices,
        "preflight": preflight,
        "price_contract": price_contract,
        "signal": signal,
        "prepared": prepared,
        "split": split,
        "controls": controls,
        "targets": targets,
        "selection_paths": selection_paths,
        "full_paths": full_paths,
        "selection_metrics": selection_metrics,
        "evaluation_metrics": evaluation_metrics,
        "original_selection_gate": original_selection_gate,
        "original_evaluation_gate": original_evaluation_gate,
        "original_halves_pass": halves_pass,
    }


def parent_reproduction_rows(context: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    metric_fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "cpi_rebalance_event_count",
        "actual_allocation_change_count",
    )
    entity_ids = {STRATEGY_ID: "candidate", NAMED_CONTROL: NAMED_CONTROL, EQUAL_CONTROL: EQUAL_CONTROL}
    for period_id, file_name, observed_map in (
        ("selection", "selection_results.csv", context["selection_metrics"]),
        ("evaluation", "evaluation_results.csv", context["evaluation_metrics"]),
    ):
        for archived in read_csv(PARENT_DIR / file_name):
            if archived["entity_id"] not in entity_ids:
                continue
            entity = entity_ids[archived["entity_id"]]
            cost = float(archived["cost_bps_one_way"])
            observed = observed_map[(entity, cost)]
            field_passes: list[bool] = []
            deltas: dict[str, float] = {}
            for field in metric_fields:
                expected = float(archived[field])
                actual = float(observed[field])
                delta = actual - expected
                deltas[f"{field}_delta"] = delta
                field_passes.append(abs(delta) <= REPRODUCTION_TOLERANCE)
            rows.append(
                {
                    "period_id": period_id,
                    "entity_id": archived["entity_id"],
                    "cost_bps_one_way": cost,
                    "expected_start": archived["evaluation_start"],
                    "observed_start": observed["evaluation_start"],
                    "expected_end": archived["evaluation_end"],
                    "observed_end": observed["evaluation_end"],
                    **deltas,
                    "repository_tolerance": REPRODUCTION_TOLERANCE,
                    "reproduction_pass": all(field_passes)
                    and archived["evaluation_start"] == observed["evaluation_start"]
                    and archived["evaluation_end"] == observed["evaluation_end"],
                }
            )
    required_counts = {
        "selection_events": context["selection_metrics"][("candidate", PRIMARY_COST)]["cpi_rebalance_event_count"] == 121,
        "evaluation_events": context["evaluation_metrics"][("candidate", PRIMARY_COST)]["cpi_rebalance_event_count"] == 82,
        "total_events": len(context["prepared"]["targets"]) == 203,
        "selection_changes": context["selection_metrics"][("candidate", PRIMARY_COST)]["actual_allocation_change_count"] == 86,
        "evaluation_changes": context["evaluation_metrics"][("candidate", PRIMARY_COST)]["actual_allocation_change_count"] == 73,
        "first_valid_formation": context["prepared"]["first_valid"].date().isoformat() == "2009-08-17",
    }
    rows.append(
        {
            "period_id": "required_parent_counts",
            "entity_id": STRATEGY_ID,
            "cost_bps_one_way": PRIMARY_COST,
            **required_counts,
            "reproduction_pass": all(required_counts.values()),
        }
    )
    return rows, all(bool(row["reproduction_pass"]) for row in rows)


def preregistration_payload(context: dict[str, Any]) -> dict[str, Any]:
    event_groups = np.array_split(np.array(context["split"].event_dates, dtype="datetime64[ns]"), 4)
    blocks = [
        {
            "block_id": position + 1,
            "event_count": len(group),
            "first_event": pd.Timestamp(group[0]).date().isoformat(),
            "last_event": pd.Timestamp(group[-1]).date().isoformat(),
        }
        for position, group in enumerate(event_groups)
    ]
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "parent_canonical_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "parent_deterministic_evidence_hash": PARENT_EVIDENCE_HASH,
        "corrected_parent_code_hash": PARENT_CODE_HASH,
        "CPI_V2_hash": V2_HASH,
        "price_bundle_hash": PRICE_BUNDLE_HASH,
        "universe_hash": UNIVERSE_HASH,
        "robustness_axes": {
            "costs_bps_one_way": list(COSTS),
            "chronological_blocks": blocks,
            "chronological_partition_algorithm": "ordered_numpy_array_split_of_203_CPI_events_into_4_contiguous_blocks",
            "bootstrap": {
                "method": "paired_monthly_moving_block_bootstrap",
                "complete_boundary_months_only": True,
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "replications": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
                "identical_sample_indices_for_candidate_and_controls": True,
            },
            "rolling_windows": {"months": ROLLING_MONTHS, "step_months": ROLLING_STEP_MONTHS, "role": "diagnostic_only"},
            "regime_and_transition_attribution": "diagnostic_only",
            "timing_delays_business_days": list(TIMING_DELAYS),
        },
        "control_roles": {
            NAMED_CONTROL: "blocking_control",
            EQUAL_CONTROL: "blocking_control",
            DIAGNOSTIC_CONTROL: "diagnostic_only",
        },
        "dominance_rule": "control_Sharpe_at_least_candidate_and_control_max_drawdown_at_least_candidate_with_one_strict_improvement",
        "blocking_gates": {
            "parent_reproduction_and_original_gates": True,
            "cost_robustness": "at_5_and_10bps_candidate_CAGR_and_Sharpe_positive_and_neither_blocking_control_Pareto_dominates",
            "four_blocks": "candidate_CAGR_positive_at_least_3;each_control_nondominance_at_least_3;simultaneous_dominance_at_most_1",
            "bootstrap_absolute_viability": "candidate_5th_percentile_CAGR_strictly_positive",
            "source_accounting_exposure_invariants": True,
        },
        "diagnostic_only_tests": [
            "rolling_36_month_windows_stepped_12_months",
            "regime_attribution",
            "transition_attribution",
            "plus_1_and_plus_2_business_day_execution_delays",
            DIAGNOSTIC_CONTROL,
        ],
        "timing_brittleness_definition": "true_if_any_delay_has_nonpositive_CAGR_or_nonpositive_Sharpe_or_Sharpe_drop_at_least_0.25_or_drawdown_worsening_at_least_0.05",
        "regime_concentration_flag_definition": "true_if_one_regime_supplies_more_than_80_percent_of_positive_arithmetic_return_contribution",
        "no_new_untouched_holdout": True,
        "combined_parent_history_previously_observed": True,
        "strategy_rule_changes_allowed": False,
        "strategy_variant_count": 0,
        "forbidden_adaptations": list(FORBIDDEN_ADAPTATIONS),
        "robustness_code_hash": sha256_path(Path(__file__)),
        "robustness_results_calculated_before_preregistration": False,
    }


def write_preregistration(payload: dict[str, Any]) -> dict[str, Any]:
    path = OUTPUT_DIR / "robustness_preregistration.json"
    contract_hash = stable_hash(payload)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["preregistration_contract_hash"] != contract_hash:
            raise RuntimeError("robustness_preregistration_changed")
        return existing
    recorded = {
        **payload,
        "preregistration_timestamp": datetime.now(timezone.utc).isoformat(),
        "preregistration_contract_hash": contract_hash,
        "written_before_robustness_results": True,
    }
    write_json(path, recorded)
    return recorded


def full_metrics(context: dict[str, Any]) -> dict[tuple[str, float], dict[str, Any]]:
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        for entity in ("candidate", *BLOCKING_CONTROLS):
            metrics[(entity, cost)] = parent.path_metrics(
                context["full_paths"][(entity, cost)],
                context["split"].full_index,
                context["prepared"]["event_regimes"] if entity == "candidate" else {},
            )
    return metrics


def cost_rows(metrics: dict[tuple[str, float], dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    rows: list[dict[str, Any]] = []
    gates: dict[str, bool] = {}
    for cost in COSTS:
        candidate = metrics[("candidate", cost)]
        for entity in ("candidate", *BLOCKING_CONTROLS):
            values = metrics[(entity, cost)]
            row = {
                "entity_id": STRATEGY_ID if entity == "candidate" else entity,
                "entity_role": "canonical_candidate" if entity == "candidate" else "blocking_control",
                "cost_bps_one_way": cost,
                **values,
            }
            if entity != "candidate":
                row.update(
                    {
                        "candidate_minus_control_CAGR": candidate["cagr"] - values["cagr"],
                        "candidate_minus_control_Sharpe": candidate["sharpe_ratio"] - values["sharpe_ratio"],
                        "candidate_minus_control_max_drawdown": candidate["maximum_drawdown"] - values["maximum_drawdown"],
                        "control_pareto_dominates_candidate": pareto_dominates(values, candidate),
                    }
                )
            rows.append(row)
        if cost in (5.0, 10.0):
            gates[f"candidate_CAGR_positive_{cost:g}bps"] = candidate["cagr"] > 0.0
            gates[f"candidate_Sharpe_positive_{cost:g}bps"] = candidate["sharpe_ratio"] > 0.0
            for control in BLOCKING_CONTROLS:
                gates[f"{control}_does_not_dominate_{cost:g}bps"] = not pareto_dominates(metrics[(control, cost)], candidate)
    return rows, gates


def chronological_blocks(context: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = np.array(context["split"].event_dates, dtype="datetime64[ns]")
    groups = np.array_split(events, 4)
    rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    full_index = context["split"].full_index
    for position, group in enumerate(groups):
        start = pd.Timestamp(group[0])
        if position + 1 < len(groups):
            next_start = pd.Timestamp(groups[position + 1][0])
            period = full_index[(full_index >= start) & (full_index < next_start)]
        else:
            period = full_index[full_index >= start]
        metrics = {
            entity: parent.path_metrics(
                context["full_paths"][(entity, PRIMARY_COST)],
                period,
                context["prepared"]["event_regimes"] if entity == "candidate" else {},
            )
            for entity in ("candidate", *BLOCKING_CONTROLS)
        }
        candidate = metrics["candidate"]
        named_dominates = pareto_dominates(metrics[NAMED_CONTROL], candidate)
        equal_dominates = pareto_dominates(metrics[EQUAL_CONTROL], candidate)
        outcome = {
            "block_id": position + 1,
            "event_count": len(group),
            "candidate_CAGR_positive": candidate["cagr"] > 0.0,
            "named_control_dominates": named_dominates,
            "equal_weight_control_dominates": equal_dominates,
            "both_controls_dominate": named_dominates and equal_dominates,
        }
        outcomes.append(outcome)
        for entity in ("candidate", *BLOCKING_CONTROLS):
            values = metrics[entity]
            row = {
                "block_id": position + 1,
                "block_event_count": len(group),
                "first_event": pd.Timestamp(group[0]).date().isoformat(),
                "last_event": pd.Timestamp(group[-1]).date().isoformat(),
                "period_start": period.min().date().isoformat(),
                "period_end": period.max().date().isoformat(),
                "entity_id": STRATEGY_ID if entity == "candidate" else entity,
                "entity_role": "canonical_candidate" if entity == "candidate" else "blocking_control",
                "cost_bps_one_way": PRIMARY_COST,
                **values,
                **outcome,
            }
            if entity != "candidate":
                row["candidate_minus_control_Sharpe"] = candidate["sharpe_ratio"] - values["sharpe_ratio"]
                row["candidate_minus_control_max_drawdown"] = candidate["maximum_drawdown"] - values["maximum_drawdown"]
                row["control_pareto_dominates_candidate"] = pareto_dominates(values, candidate)
            rows.append(row)
    summary = {
        "candidate_positive_CAGR_block_count": sum(item["candidate_CAGR_positive"] for item in outcomes),
        "named_control_nondominance_block_count": sum(not item["named_control_dominates"] for item in outcomes),
        "equal_weight_nondominance_block_count": sum(not item["equal_weight_control_dominates"] for item in outcomes),
        "simultaneous_control_dominance_block_count": sum(item["both_controls_dominate"] for item in outcomes),
        "block_event_counts": [item["event_count"] for item in outcomes],
        "block_outcomes": outcomes,
    }
    summary["candidate_positive_CAGR_gate"] = summary["candidate_positive_CAGR_block_count"] >= 3
    summary["named_control_nondominance_gate"] = summary["named_control_nondominance_block_count"] >= 3
    summary["equal_weight_nondominance_gate"] = summary["equal_weight_nondominance_block_count"] >= 3
    summary["simultaneous_dominance_gate"] = summary["simultaneous_control_dominance_block_count"] <= 1
    summary["four_block_gate_pass"] = all(
        summary[key]
        for key in (
            "candidate_positive_CAGR_gate",
            "named_control_nondominance_gate",
            "equal_weight_nondominance_gate",
            "simultaneous_dominance_gate",
        )
    )
    return rows, summary


def complete_monthly_returns(context: dict[str, Any]) -> pd.DataFrame:
    series = []
    for entity in ("candidate", *BLOCKING_CONTROLS):
        daily = context["full_paths"][(entity, PRIMARY_COST)]["returns"].reindex(context["split"].full_index)
        monthly = (1.0 + daily).groupby(daily.index.to_period("M")).prod() - 1.0
        monthly.name = entity
        series.append(monthly)
    frame = pd.concat(series, axis=1).dropna()
    if len(frame) < 3:
        raise RuntimeError("insufficient_monthly_returns")
    return frame.iloc[1:-1]


def paired_bootstrap(monthly: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values = monthly[["candidate", *BLOCKING_CONTROLS]].to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BOOTSTRAP_BLOCK_MONTHS)
    max_start = count - BOOTSTRAP_BLOCK_MONTHS
    if max_start < 0:
        raise RuntimeError("insufficient_monthly_observations_for_bootstrap")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = rng.integers(0, max_start + 1, size=(BOOTSTRAP_RESAMPLES, block_count))
    offsets = np.arange(BOOTSTRAP_BLOCK_MONTHS)
    locations = (starts[:, :, None] + offsets[None, None, :]).reshape(BOOTSTRAP_RESAMPLES, -1)[:, :count]
    samples = values[locations]
    wealth = np.cumprod(1.0 + samples, axis=1)
    cagr = wealth[:, -1, :] ** (12.0 / count) - 1.0
    standard_deviation = samples.std(axis=1, ddof=1)
    sharpe = np.divide(
        samples.mean(axis=1),
        standard_deviation,
        out=np.zeros_like(standard_deviation),
        where=standard_deviation > 0.0,
    ) * math.sqrt(12.0)
    drawdown = (wealth / np.maximum.accumulate(wealth, axis=1) - 1.0).min(axis=1)
    candidate = 0
    summary = {
        "resampling_method": "paired_monthly_moving_block_bootstrap",
        "monthly_observation_count": count,
        "first_complete_month": str(monthly.index.min()),
        "last_complete_month": str(monthly.index.max()),
        "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
        "replications": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "cross_series_dependence_preserved": True,
        "candidate_CAGR_percentiles": {
            "p05": float(np.quantile(cagr[:, candidate], 0.05)),
            "p50": float(np.quantile(cagr[:, candidate], 0.50)),
            "p95": float(np.quantile(cagr[:, candidate], 0.95)),
        },
        "candidate_Sharpe_percentiles": {
            "p05": float(np.quantile(sharpe[:, candidate], 0.05)),
            "p50": float(np.quantile(sharpe[:, candidate], 0.50)),
            "p95": float(np.quantile(sharpe[:, candidate], 0.95)),
        },
        "candidate_max_drawdown_percentiles": {
            "p05": float(np.quantile(drawdown[:, candidate], 0.05)),
            "p50": float(np.quantile(drawdown[:, candidate], 0.50)),
            "p95": float(np.quantile(drawdown[:, candidate], 0.95)),
        },
    }
    summary["bootstrap_absolute_viability_pass"] = summary["candidate_CAGR_percentiles"]["p05"] > 0.0
    comparison_rows: list[dict[str, Any]] = []
    for column, control in enumerate(BLOCKING_CONTROLS, start=1):
        control_dominates = (
            (sharpe[:, column] >= sharpe[:, candidate] - PARETO_TOLERANCE)
            & (drawdown[:, column] >= drawdown[:, candidate] - PARETO_TOLERANCE)
            & (
                (sharpe[:, column] > sharpe[:, candidate] + PARETO_TOLERANCE)
                | (drawdown[:, column] > drawdown[:, candidate] + PARETO_TOLERANCE)
            )
        )
        comparison_rows.append(
            {
                "control_id": control,
                "replications": BOOTSTRAP_RESAMPLES,
                "block_length_months": BOOTSTRAP_BLOCK_MONTHS,
                "seed": BOOTSTRAP_SEED,
                "probability_candidate_Sharpe_exceeds_control": float(np.mean(sharpe[:, candidate] > sharpe[:, column])),
                "probability_candidate_max_drawdown_better_than_control": float(np.mean(drawdown[:, candidate] > drawdown[:, column])),
                "probability_control_pareto_dominates_candidate": float(np.mean(control_dominates)),
                "relative_probability_role": "diagnostic_only",
                "paired_sample_indices": True,
            }
        )
    return summary, comparison_rows


def rolling_windows(monthly: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for start in range(0, len(monthly) - ROLLING_MONTHS + 1, ROLLING_STEP_MONTHS):
        window = monthly.iloc[start : start + ROLLING_MONTHS]
        metrics = {entity: monthly_metrics(window[entity]) for entity in ("candidate", *BLOCKING_CONTROLS)}
        candidate = metrics["candidate"]
        named_dominates = pareto_dominates(metrics[NAMED_CONTROL], candidate)
        equal_dominates = pareto_dominates(metrics[EQUAL_CONTROL], candidate)
        outcome = {
            "window_id": len(outcomes) + 1,
            "candidate_CAGR_positive": candidate["cagr"] > 0.0,
            "candidate_Sharpe_positive": candidate["sharpe_ratio"] > 0.0,
            "named_control_dominates": named_dominates,
            "equal_weight_control_dominates": equal_dominates,
            "neither_control_dominates": not named_dominates and not equal_dominates,
        }
        outcomes.append(outcome)
        for entity in ("candidate", *BLOCKING_CONTROLS):
            values = metrics[entity]
            row = {
                "window_id": outcome["window_id"],
                "window_start_month": str(window.index.min()),
                "window_end_month": str(window.index.max()),
                "window_months": len(window),
                "step_months": ROLLING_STEP_MONTHS,
                "entity_id": STRATEGY_ID if entity == "candidate" else entity,
                "entity_role": "canonical_candidate" if entity == "candidate" else "blocking_control",
                **values,
                **outcome,
                "gate_role": "diagnostic_only",
            }
            if entity != "candidate":
                row["control_pareto_dominates_candidate"] = pareto_dominates(values, candidate)
            rows.append(row)
    count = len(outcomes)
    summary = {
        "window_count": count,
        "positive_candidate_CAGR_percentage": sum(item["candidate_CAGR_positive"] for item in outcomes) / count,
        "positive_candidate_Sharpe_percentage": sum(item["candidate_Sharpe_positive"] for item in outcomes) / count,
        "named_control_dominance_percentage": sum(item["named_control_dominates"] for item in outcomes) / count,
        "equal_weight_dominance_percentage": sum(item["equal_weight_control_dominates"] for item in outcomes) / count,
        "neither_control_dominates_percentage": sum(item["neither_control_dominates"] for item in outcomes) / count,
        "role": "diagnostic_only",
    }
    return rows, summary


def regime_attribution(context: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = context["split"].full_index
    path = context["full_paths"][("candidate", PRIMARY_COST)]
    event_regimes = pd.Series(context["prepared"]["event_regimes"]).sort_index()
    active_regime = event_regimes.reindex(context["prices"].index).ffill().shift(1).reindex(index)
    target_schedule = parent.complete_target_schedule(context["prices"], context["prepared"]["targets"]).shift(1).reindex(index)
    returns = path["returns"].reindex(index)
    daily = path["daily"].reindex(index)
    transition_counts = {name: 0 for name in ("low", "medium", "high")}
    previous = ""
    for regime in event_regimes:
        if regime != previous:
            transition_counts[regime] += 1
        previous = regime
    rows: list[dict[str, Any]] = []
    positive_contributions: dict[str, float] = {}
    total_squared = float(np.square(returns.to_numpy(dtype=float)).sum())
    for regime in ("low", "medium", "high"):
        mask = active_regime.eq(regime)
        values = returns.loc[mask]
        targets = target_schedule.loc[mask]
        event_dates = [date for date, value in event_regimes.items() if value == regime and date in daily.index]
        arithmetic = float(values.sum())
        positive_contributions[regime] = max(arithmetic, 0.0)
        metrics = parent.phase2.metrics_from_returns(values)
        rows.append(
            {
                "regime": regime,
                "observation_count": len(values),
                "time_share": len(values) / int(active_regime.notna().sum()),
                "arithmetic_return_contribution": arithmetic,
                "compounded_regime_subseries_return": metrics["total_return"],
                "annualized_regime_volatility": metrics["annualized_volatility"],
                "squared_return_volatility_share": float(np.square(values.to_numpy(dtype=float)).sum() / total_squared) if total_squared > 0.0 else 0.0,
                "worst_regime_subseries_drawdown": metrics["maximum_drawdown"],
                "turnover_contribution": float(daily.loc[daily.index.intersection(event_dates), "one_way_turnover"].sum()),
                "transaction_cost_contribution": float(daily.loc[daily.index.intersection(event_dates), "transaction_cost_drag"].sum()),
                "inbound_transition_count": transition_counts[regime],
                **{f"average_target_{symbol}": float(targets[symbol].mean()) for symbol in parent.SYMBOLS},
                "gate_role": "diagnostic_only",
            }
        )
    positive_total = sum(positive_contributions.values())
    concentration_share = max(positive_contributions.values()) / positive_total if positive_total > 0.0 else 0.0
    summary = {
        "largest_positive_return_contribution_regime": max(positive_contributions, key=positive_contributions.get),
        "largest_positive_return_contribution_share": concentration_share,
        "performance_concentration_flag": concentration_share > 0.80,
        "role": "diagnostic_only",
    }
    return rows, summary


def transition_attribution(context: dict[str, Any]) -> list[dict[str, Any]]:
    path = context["full_paths"][("candidate", PRIMARY_COST)]
    index = context["prices"].index
    events = list(context["prepared"]["targets"].index)
    regimes = context["prepared"]["event_regimes"]
    observations: list[dict[str, Any]] = []
    previous = ""
    for position, event_date in enumerate(events):
        current = regimes[pd.Timestamp(event_date)]
        transition = "initialization" if not previous else "unchanged" if previous == current else f"{previous}_to_{current}"
        event_position = int(index.get_loc(event_date))
        interval_start = event_position + 1
        interval_end = int(index.get_loc(events[position + 1])) if position + 1 < len(events) else len(index) - 1
        interval = index[interval_start : interval_end + 1]
        gross_values = path["daily"].loc[interval, "gross_return"]
        turnover = float(path["daily"].loc[event_date, "one_way_turnover"])
        event_cost = float(path["daily"].loc[event_date, "transaction_cost_drag"])
        gross_return = float((1.0 + gross_values).prod() - 1.0)
        net_after_transition_cost = float((1.0 - turnover * PRIMARY_COST / 10000.0) * (1.0 + gross_return) - 1.0)
        observations.append(
            {
                "transition": transition,
                "turnover": turnover,
                "transaction_cost": event_cost,
                "following_interval_gross_return": gross_return,
                "following_interval_net_after_transition_cost": net_after_transition_cost,
            }
        )
        previous = current
    rows: list[dict[str, Any]] = []
    for transition in sorted({item["transition"] for item in observations}):
        group = [item for item in observations if item["transition"] == transition]
        rows.append(
            {
                "transition": transition,
                "event_count": len(group),
                "average_following_interval_gross_return": float(np.mean([item["following_interval_gross_return"] for item in group])),
                "median_following_interval_gross_return": float(np.median([item["following_interval_gross_return"] for item in group])),
                "average_following_interval_net_after_transition_cost": float(np.mean([item["following_interval_net_after_transition_cost"] for item in group])),
                "total_turnover": sum(item["turnover"] for item in group),
                "average_turnover": float(np.mean([item["turnover"] for item in group])),
                "total_transaction_cost_drag": sum(item["transaction_cost"] for item in group),
                "gate_role": "diagnostic_only",
            }
        )
    return rows


def delayed_targets(prices: pd.DataFrame, targets: pd.DataFrame, delay: int) -> pd.DataFrame:
    dates: list[pd.Timestamp] = []
    rows: list[np.ndarray] = []
    for event_date, row in targets.iterrows():
        position = int(prices.index.get_loc(event_date)) + delay
        if position >= len(prices):
            raise RuntimeError("timing_delay_outside_frozen_sample")
        dates.append(pd.Timestamp(prices.index[position]))
        rows.append(row.to_numpy(dtype=float))
    if len(dates) != len(set(dates)):
        raise RuntimeError("timing_delay_event_collision")
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates), columns=list(targets.columns), dtype=float)


def timing_sensitivity(context: dict[str, Any], canonical: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows = [
        {
            "timing_id": "canonical_source_timing",
            "delay_business_days": 0,
            "role": "canonical_reference",
            **canonical,
            "CAGR_difference_vs_canonical": 0.0,
            "Sharpe_difference_vs_canonical": 0.0,
            "max_drawdown_difference_vs_canonical": 0.0,
        }
    ]
    brittle = False
    for delay in TIMING_DELAYS:
        targets = delayed_targets(context["prices"], context["prepared"]["targets"], delay)
        path = parent.simulate(context["prices"], targets, PRIMARY_COST)
        metrics = parent.path_metrics(path, context["split"].full_index, {})
        sharpe_drop = canonical["sharpe_ratio"] - metrics["sharpe_ratio"]
        drawdown_worsening = canonical["maximum_drawdown"] - metrics["maximum_drawdown"]
        delay_brittle = bool(
            metrics["cagr"] <= 0.0
            or metrics["sharpe_ratio"] <= 0.0
            or sharpe_drop >= 0.25
            or drawdown_worsening >= 0.05
        )
        brittle = brittle or delay_brittle
        rows.append(
            {
                "timing_id": f"canonical_effective_close_plus_{delay}_business_day" + ("" if delay == 1 else "s"),
                "delay_business_days": delay,
                "role": "diagnostic_only_timing_stress",
                **metrics,
                "CAGR_difference_vs_canonical": metrics["cagr"] - canonical["cagr"],
                "Sharpe_difference_vs_canonical": metrics["sharpe_ratio"] - canonical["sharpe_ratio"],
                "max_drawdown_difference_vs_canonical": metrics["maximum_drawdown"] - canonical["maximum_drawdown"],
                "timing_brittleness_flag": delay_brittle,
                "signals_recomputed": False,
                "canonical_rule_changed": False,
            }
        )
    return rows, brittle


def failure_reasons(gates: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not gates["parent_exploration_survival_pass"]:
        reasons.append("source_conformance_failure")
    if not gates["cost_robustness_pass"]:
        reasons.append("cost_instability")
        if any(not value for key, value in gates["cost_gate_components"].items() if "does_not_dominate" in key):
            reasons.append("control_dominance")
    if not gates["four_block_stability_pass"]:
        reasons.append("period_instability")
    if not gates["bootstrap_absolute_viability_pass"]:
        reasons.append("bootstrap_absolute_viability_failure")
    if not gates["source_accounting_exposure_invariants_pass"]:
        reasons.append("accounting_invariant_failure")
    return list(dict.fromkeys(reasons))


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    context = build_parent_context()
    reproduction_rows, reproduction_pass = parent_reproduction_rows(context)
    if not reproduction_pass:
        raise RuntimeError("parent_reproduction_failure")

    preregistration = write_preregistration(preregistration_payload(context))
    metrics = full_metrics(context)
    cost_result_rows, cost_gate_components = cost_rows(metrics)
    block_rows, block_summary = chronological_blocks(context)
    monthly = complete_monthly_returns(context)
    bootstrap_summary, bootstrap_comparisons = paired_bootstrap(monthly)
    rolling_rows, rolling_summary = rolling_windows(monthly)
    regime_rows, regime_summary = regime_attribution(context)
    transition_rows = transition_attribution(context)
    timing_rows, timing_brittleness = timing_sensitivity(context, metrics[("candidate", PRIMARY_COST)])

    original_survival = bool(
        context["original_selection_gate"]["selection_eligible"]
        and context["original_evaluation_gate"]["exploration_followup_justified"]
        and context["original_halves_pass"]
        and context["source"]["all_preperformance_checks_pass"]
        and context["source"]["postperformance_accounting_invariants_pass"]
    )
    invariants_pass = bool(
        all(metrics[("candidate", cost)]["invariant_pass"] for cost in COSTS)
        and all(context["lineage_checks"].values())
        and context["v2"]["observed_hash"] == V2_HASH
        and context["price_contract"]["frozen_price_data_bundle_hash"] == PRICE_BUNDLE_HASH
        and context["price_contract"]["universe_hash"] == UNIVERSE_HASH
    )
    gates = {
        "parent_reproduction_pass": reproduction_pass,
        "parent_exploration_survival_pass": original_survival,
        "cost_gate_components": cost_gate_components,
        "cost_robustness_pass": all(cost_gate_components.values()),
        "four_block_summary": block_summary,
        "four_block_stability_pass": block_summary["four_block_gate_pass"],
        "bootstrap_summary": bootstrap_summary,
        "bootstrap_absolute_viability_pass": bootstrap_summary["bootstrap_absolute_viability_pass"],
        "source_accounting_exposure_invariants_pass": invariants_pass,
        "diagnostic_findings": {
            "rolling_windows": rolling_summary,
            "regime_attribution": regime_summary,
            "timing_brittleness_flag": timing_brittleness,
        },
    }
    blocking_pass = all(
        gates[key]
        for key in (
            "parent_reproduction_pass",
            "parent_exploration_survival_pass",
            "cost_robustness_pass",
            "four_block_stability_pass",
            "bootstrap_absolute_viability_pass",
            "source_accounting_exposure_invariants_pass",
        )
    )
    reasons = failure_reasons(gates)
    outcome = OUTCOME_PASS if blocking_pass else OUTCOME_FAIL
    next_action = NEXT_PASS if blocking_pass else NEXT_FAIL

    control_audit = [
        {
            "control_id": NAMED_CONTROL,
            "control_role": "blocking_control",
            "ex_ante_investable": True,
            "uses_candidate_full_history": False,
            "uses_future_candidate_allocations": False,
            "can_determine_robustness": True,
            "status": "pass",
        },
        {
            "control_id": EQUAL_CONTROL,
            "control_role": "blocking_control",
            "ex_ante_investable": True,
            "uses_candidate_full_history": False,
            "uses_future_candidate_allocations": False,
            "can_determine_robustness": True,
            "status": "pass",
        },
        {
            "control_id": DIAGNOSTIC_CONTROL,
            "control_role": "diagnostic_only",
            "ex_ante_investable": False,
            "uses_candidate_full_history": True,
            "uses_future_candidate_allocations": True,
            "can_determine_robustness": False,
            "status": "pass",
        },
    ]
    accounting = {
        "parent_architecture_count": 1,
        "parent_canonical_configuration_count": 1,
        "parent_canonical_trial_count": 1,
        "robustness_trial_count": 1,
        "strategy_variant_count": 0,
        "chronological_blocks_counted_as_trials": 0,
        "cost_levels_counted_as_trials": 0,
        "bootstrap_replications_counted_as_trials": 0,
        "rolling_windows_counted_as_trials": 0,
        "timing_diagnostics_counted_as_trials": 0,
        "control_count": 3,
        "blocking_control_count": 2,
        "diagnostic_control_count": 1,
        "provider_calls": 0,
        "broker_calls": 0,
        "forward_observation_accesses": 0,
        "eligibility_decisions": 0,
        "handoffs": 0,
        "trade_management_overlays": 0,
    }

    write_csv(OUTPUT_DIR / "parent_reproduction.csv", reproduction_rows)
    write_csv(OUTPUT_DIR / "cost_robustness.csv", cost_result_rows)
    write_csv(OUTPUT_DIR / "chronological_block_results.csv", block_rows)
    write_csv(OUTPUT_DIR / "rolling_window_results.csv", rolling_rows)
    write_json(OUTPUT_DIR / "bootstrap_summary.json", bootstrap_summary)
    write_csv(OUTPUT_DIR / "bootstrap_control_comparison.csv", bootstrap_comparisons)
    write_csv(OUTPUT_DIR / "regime_attribution.csv", regime_rows)
    write_csv(OUTPUT_DIR / "transition_attribution.csv", transition_rows)
    write_csv(OUTPUT_DIR / "timing_sensitivity.csv", timing_rows)
    write_csv(OUTPUT_DIR / "control_information_set_audit.csv", control_audit)
    write_json(OUTPUT_DIR / "robustness_gate_results.json", {**gates, "blocking_gates_passed": blocking_pass, "failure_reasons": reasons})
    write_json(OUTPUT_DIR / "trial_accounting.json", accounting)
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    report = (
        "# S&P DJI Dynamic Inflation ETF Portability Robustness\n\n"
        "The corrected canonical ETF-portability implementation reproduced exactly. The reserved evaluation was already accessed during exploration, so every robustness slice here uses previously observed research history and is not a new holdout.\n\n"
        f"- Outcome: `{outcome}`\n"
        f"- Blocking gates passed: `{str(blocking_pass).lower()}`\n"
        f"- Failure reasons: `{','.join(reasons) if reasons else 'none'}`\n"
        f"- Full-history 5 bps CAGR / Sharpe / drawdown: `{metrics[('candidate', 5.0)]['cagr']:.6f}` / `{metrics[('candidate', 5.0)]['sharpe_ratio']:.6f}` / `{metrics[('candidate', 5.0)]['maximum_drawdown']:.6f}`\n"
        f"- Four-block counts: positive CAGR `{block_summary['candidate_positive_CAGR_block_count']}/4`, 60/40 nondominance `{block_summary['named_control_nondominance_block_count']}/4`, equal-weight nondominance `{block_summary['equal_weight_nondominance_block_count']}/4`\n"
        f"- Bootstrap fifth-percentile CAGR: `{bootstrap_summary['candidate_CAGR_percentiles']['p05']:.6f}`\n"
        f"- Timing brittleness flag: `{str(timing_brittleness).lower()}`\n"
        f"- Next action: `{next_action}`\n\n"
        "No thresholds, lookbacks, mappings, controls, or source timing rules were changed. Timing delays, rolling windows, regime attribution, and transition attribution are diagnostic only.\n"
    )
    (OUTPUT_DIR / "robustness_report.md").write_text(report, encoding="utf-8")

    protected_after = protected_snapshot()
    deterministic_hash = packet_hash()
    consistency_checks = {
        "parent_evidence_unchanged": protected_before[PARENT_DIR.relative_to(ROOT).as_posix()] == protected_after[PARENT_DIR.relative_to(ROOT).as_posix()],
        "corrected_parent_code_hash_matches": sha256_path(PARENT_CODE_PATH) == PARENT_CODE_HASH,
        "CPI_V2_hash_matches": context["v2"]["observed_hash"] == V2_HASH,
        "price_bundle_hash_matches": context["price_contract"]["frozen_price_data_bundle_hash"] == PRICE_BUNDLE_HASH,
        "universe_hash_matches": context["price_contract"]["universe_hash"] == UNIVERSE_HASH,
        "canonical_rules_unchanged": True,
        "ETF_mapping_unchanged": tuple(parent.SYMBOLS) == ("SPY", "IYR", "GSG", "GLD", "AGG", "TIP"),
        "parameters_unchanged": True,
        "one_parent_canonical_trial": accounting["parent_canonical_trial_count"] == 1,
        "one_robustness_trial": accounting["robustness_trial_count"] == 1,
        "no_strategy_variants": accounting["strategy_variant_count"] == 0,
        "blocking_controls_ex_ante": all(row["ex_ante_investable"] for row in control_audit if row["control_role"] == "blocking_control"),
        "ex_post_control_diagnostic_only": next(row for row in control_audit if row["control_id"] == DIAGNOSTIC_CONTROL)["can_determine_robustness"] is False,
        "no_provider_broker_or_forward_calls": accounting["provider_calls"] == accounting["broker_calls"] == accounting["forward_observation_accesses"] == 0,
        "no_eligibility_handoff_or_overlay": accounting["eligibility_decisions"] == accounting["handoffs"] == accounting["trade_management_overlays"] == 0,
        "preregistration_preceded_robustness_results": preregistration["written_before_robustness_results"],
        "all_required_outputs_present": all((OUTPUT_DIR / name).exists() for name in REQUIRED_OUTPUTS if name != "consistency_check.json"),
        "all_protected_state_unchanged": protected_before == protected_after,
    }
    consistency = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "outcome": outcome,
        "failure_reasons": reasons,
        "next_action": next_action,
        "overall_pass": all(consistency_checks.values()),
        "blocking_gates_passed": blocking_pass,
        "checks": consistency_checks,
        "parent_reproduction_pass": reproduction_pass,
        "full_history_metrics": {
            f"candidate_{cost:g}bps": metrics[("candidate", cost)] for cost in COSTS
        },
        "four_block_summary": block_summary,
        "bootstrap_summary": bootstrap_summary,
        "rolling_window_summary": rolling_summary,
        "regime_attribution_summary": regime_summary,
        "timing_brittleness_flag": timing_brittleness,
        "trial_accounting": accounting,
        "parent_evidence_hash": PARENT_EVIDENCE_HASH,
        "parent_code_hash": PARENT_CODE_HASH,
        "CPI_V2_hash": V2_HASH,
        "price_bundle_hash": PRICE_BUNDLE_HASH,
        "universe_hash": UNIVERSE_HASH,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "deterministic_evidence_hash": deterministic_hash,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    if not consistency["overall_pass"]:
        raise RuntimeError("robustness_consistency_failure")
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
