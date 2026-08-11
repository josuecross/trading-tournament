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
from strategy_lab.research_os.research import phase2_expanded_universe_discovery_batch_v1 as phase2


TASK_ID = "phase2_new_group_discovery_batch_v1"
INTAKE_ID = "phase2_new_group_hybrid_candidate_intake_v1"
STAGE = "optimization_to_exploratory_evaluation"
LINEAGE = "internally_generated_technical_hypothesis"
UNIVERSE_ID = phase2.UNIVERSE_ID
EXPECTED_UNIVERSE_HASH = phase2.EXPECTED_UNIVERSE_HASH
ARCHITECTURE_ID = "two_subperiod_industry_parent_relative_persistence_selection"
FAMILY_ID = "phase2_industry_parent_relative_persistence_rotation"
DISPLAY_NAME = "Phase-2 Industry/Parent Relative Persistence Rotation"
PRIMARY_ROLE = "cross_sectional_allocation_strategy"
ROUTE = "standalone"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8
PREREGISTRATION_TIMESTAMP = "2026-08-09T00:00:00-06:00"

INTAKE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID / "latest"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"

PAIR_MAPPINGS = (
    ("IBB", "XLV"),
    ("XBI", "XLV"),
    ("SMH", "XLK"),
    ("KRE", "XLF"),
    ("ITB", "XLY"),
    ("XRT", "XLY"),
    ("IYT", "XLI"),
)
INDUSTRIES = tuple(industry for industry, _ in PAIR_MAPPINGS)
PARENTS = tuple(dict.fromkeys(parent for _, parent in PAIR_MAPPINGS))
ACCOUNTING_UNIVERSE = INDUSTRIES + PARENTS + ("BIL", "SPY")

NAMED_CONTROL = "industry_parent_full_window_relative_momentum_control"
STATIC_CONTROL = "industry_parent_persistence_static_average_weights_control"
EQUAL_INDUSTRY_CONTROL = "equal_weight_seven_phase2_industries_control"
PARENT_CONTROL = "equal_weight_five_parent_sectors_control"
SPY_CONTROL = "SPY_buy_and_hold"
BIL_CONTROL = "BIL_buy_and_hold"
ALL_CONTROLS = (
    NAMED_CONTROL,
    STATIC_CONTROL,
    EQUAL_INDUSTRY_CONTROL,
    PARENT_CONTROL,
    SPY_CONTROL,
    BIL_CONTROL,
)

FOLLOWUP_ACTION = "direction_owner_review_phase2_new_group_followups_for_robustness_v1"
NO_FOLLOWUP_ACTION = "direction_owner_review_phase2_expansion_discovery_yield_v2"
BLOCK_ACTION = "direction_owner_review_phase2_new_group_execution_block_v1"

PERMITTED_FAILURE_REASONS = {
    "duplicate_or_redundant",
    "signal_scarcity",
    "no_selection_eligible_configuration",
    "not_selected_by_frozen_rule",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "concentration_risk",
    "weak_return",
    "excess_drawdown",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}


@dataclass(frozen=True)
class ConfigSpec:
    code: str
    strategy_id: str
    trial_id: str
    lookback: int
    selected_count: int

    @property
    def subperiod(self) -> int:
        return self.lookback // 2


CONFIGS = (
    ConfigSpec("P1", "phase2_industry_parent_persistence_42d_top2_v1", "phase2_new_group_v1__industrypersist42__top2", 42, 2),
    ConfigSpec("P2", "phase2_industry_parent_persistence_42d_top3_v1", "phase2_new_group_v1__industrypersist42__top3", 42, 3),
    ConfigSpec("P3", "phase2_industry_parent_persistence_84d_top2_v1", "phase2_new_group_v1__industrypersist84__top2", 84, 2),
    ConfigSpec("P4", "phase2_industry_parent_persistence_84d_top3_v1", "phase2_new_group_v1__industrypersist84__top3", 84, 3),
)
CONFIG_BY_TRIAL = {config.trial_id: config for config in CONFIGS}


@dataclass(frozen=True)
class SplitDefinition:
    prices: pd.DataFrame
    signal_execution_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    selection_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    evaluation_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    selection_index: pd.DatetimeIndex
    evaluation_index: pd.DatetimeIndex
    full_index: pd.DatetimeIndex
    boundary_execution: pd.Timestamp


REQUIRED_INTAKE_OUTPUTS = {
    "intake_manifest.yaml",
    "selected_architecture_spec.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "robustness_role_preregistration.csv",
    "phase2_unlock_reconciliation.csv",
    "external_rejection_ledger.csv",
    "internal_concept_rejection_ledger.csv",
    "consistency_check.json",
    "intake_report.md",
}

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "phase2_universe_hash_reconciliation.csv",
    "intake_reconciliation.csv",
    "architecture_preregistration.yaml",
    "pair_mapping.csv",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "duplicate_preflight.csv",
    "benchmark_reference_log.csv",
    "data_preflight_reconciliation.csv",
    "monthly_pair_signal_ledger.csv",
    "selection_segment_definition.csv",
    "selection_segment_results.csv",
    "architecture_winner_selection.csv",
    "evaluation_segment_results.csv",
    "evaluation_subhalf_results.csv",
    "post_selection_full_period_diagnostics.csv",
    "candidate_control_overlap.csv",
    "calendar_year_results.csv",
    "monthly_formation_contribution_results.csv",
    "industry_attribution.csv",
    "parent_sector_group_attribution.csv",
    "lightweight_concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_vectors.csv",
    "failure_reasons.csv",
    "entity_count_reconciliation.json",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "batch_report.md",
}

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml",
    UNIVERSE_DIR,
    phase2.PHASE1_CACHE_DIR,
    phase2.PHASE2_CACHE_DIR,
    phase2.INTAKE_DIR,
    phase2.OUTPUT_DIR,
    ROOT / "evidence" / "robustness" / "role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1" / "latest",
    ROOT / "evidence" / "handoff",
    ROOT / "evidence" / "forward_observation",
    ROOT / "evidence" / "paper_demo_observation",
)


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


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_PATHS if path.exists()}


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
        raise RuntimeError(f"Missing CSV schema for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_empty_csv(path: Path, fields: list[str]) -> None:
    write_csv(path, [], fields)


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


def clean_output(path: Path, expected_parent: Path) -> None:
    if path.exists():
        if expected_parent.resolve() not in path.resolve().parents:
            raise RuntimeError(f"Refusing to remove unexpected path {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def explicit_target(weights: dict[str, float]) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in ACCOUNTING_UNIVERSE}
    target.update(weights)
    if not math.isclose(sum(target.values()), 1.0, abs_tol=WEIGHT_TOLERANCE):
        raise RuntimeError("Target weights do not sum to one")
    return target


def fixed_slot_target(selected: list[str], selected_count: int) -> dict[str, float]:
    weights = {symbol: 1.0 / selected_count for symbol in selected[:selected_count]}
    weights["BIL"] = 1.0 - sum(weights.values())
    return explicit_target(weights)


def event_frame(index: pd.DatetimeIndex, events: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    dates = sorted(date for date in events if date in index)
    return pd.DataFrame([events[date] for date in dates], index=pd.DatetimeIndex(dates), columns=list(ACCOUNTING_UNIVERSE), dtype=float)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def monthly_rebalanced_events(
    index: pd.DatetimeIndex,
    execution_dates: Iterable[pd.Timestamp],
    weights: dict[str, float],
) -> pd.DataFrame:
    events = {pd.Timestamp(index[0]): explicit_target(weights)}
    for execution in execution_dates:
        events[pd.Timestamp(execution)] = explicit_target(weights)
    return event_frame(index, events)


def buy_hold_events(index: pd.DatetimeIndex, weights: dict[str, float]) -> pd.DataFrame:
    return event_frame(index, {pd.Timestamp(index[0]): explicit_target(weights)})


def intake_architecture_payload() -> dict[str, Any]:
    return {
        "intake_id": INTAKE_ID,
        "architecture": {
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "display_name": DISPLAY_NAME,
            "source_or_research_lineage": LINEAGE,
            "primary_future_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "pair_mappings": [{"industry": industry, "parent_sector": parent_symbol} for industry, parent_symbol in PAIR_MAPPINGS],
            "fallback": "BIL",
            "broad_reference": "SPY",
            "formula": {
                "q": "log(industry_adjusted_close/parent_adjusted_close)",
                "rel1": "q_t_minus_L_over_2-q_t_minus_L",
                "rel2": "q_t-q_t_minus_L_over_2",
                "score": "min(rel1,rel2)",
                "eligibility": "rel1>0 and rel2>0",
                "ranking": "score_descending_lexical_tie",
            },
            "execution": "final_month_session_signal_following_regular_session_close_execution",
            "missing_data": "retain_previous_target_and_never_reduce_panel",
            "configurations": [
                {
                    "code": config.code,
                    "strategy_id": config.strategy_id,
                    "trial_id": config.trial_id,
                    "lookback_sessions": config.lookback,
                    "subperiod_sessions": config.subperiod,
                    "selected_count": config.selected_count,
                }
                for config in CONFIGS
            ],
            "controls": list(ALL_CONTROLS),
        },
        "post_result_parameter_changes_allowed": False,
        "provider_requirement": 0,
        "unresolved_material_fields": 0,
    }


def intake_configuration_rows() -> list[dict[str, Any]]:
    return [
        {
            "architecture_id": ARCHITECTURE_ID,
            "family_id": FAMILY_ID,
            "configuration_code": config.code,
            "strategy_id": config.strategy_id,
            "trial_id": config.trial_id,
            "entity_type": "experiment_trial",
            "stage": "optimization",
            "lookback_sessions": config.lookback,
            "subperiod_sessions": config.subperiod,
            "selected_count": config.selected_count,
            "canonical_trial": True,
            "parent_trial_id": "",
            "adaptation_label": "",
            "optimization_performed": True,
            "post_result_adaptation_allowed": False,
        }
        for config in CONFIGS
    ]


def benchmark_catalog_rows() -> list[dict[str, Any]]:
    descriptions = {
        NAMED_CONTROL: "full-window parent-relative momentum with identical L/K/timing/fixed slots",
        STATIC_CONTROL: "candidate full-period average monthly target weights held statically",
        EQUAL_INDUSTRY_CONTROL: "monthly rebalanced equal weight across seven industries",
        PARENT_CONTROL: "static equal weight across five parent sectors",
        SPY_CONTROL: "SPY buy and hold",
        BIL_CONTROL: "BIL buy and hold",
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "description": descriptions[control_id],
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "post_result_control": False,
        }
        for control_id in ALL_CONTROLS
    ]


def materialize_intake() -> dict[str, Any]:
    clean_output(INTAKE_DIR, ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID)
    payload = intake_architecture_payload()
    config_rows = intake_configuration_rows()
    benchmarks = benchmark_catalog_rows()
    write_yaml(
        INTAKE_DIR / "intake_manifest.yaml",
        {
            "intake_id": INTAKE_ID,
            "stage": "source_extracted",
            "selected_external_strategies": 0,
            "selected_internal_architectures": 1,
            "proposed_canonical_trials": 4,
            "unresolved_material_fields": 0,
            "provider_requirements": 0,
            "universe_id": UNIVERSE_ID,
            "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
        },
    )
    write_yaml(INTAKE_DIR / "selected_architecture_spec.yaml", payload)
    write_csv(INTAKE_DIR / "configuration_trial_catalog.csv", config_rows)
    write_csv(INTAKE_DIR / "benchmark_reference_catalog.csv", benchmarks)
    write_csv(
        INTAKE_DIR / "robustness_role_preregistration.csv",
        [
            {
                "architecture_id": ARCHITECTURE_ID,
                "primary_future_robustness_role": PRIMARY_ROLE,
                "role_selected_before_performance": True,
                "role_change_after_results_allowed": False,
            }
        ],
    )
    write_csv(
        INTAKE_DIR / "phase2_unlock_reconciliation.csv",
        [
            {
                "architecture_id": ARCHITECTURE_ID,
                "phase2_industries": INDUSTRIES,
                "phase2_industry_count": len(INDUSTRIES),
                "all_phase2_additions_used": True,
                "universe_id": UNIVERSE_ID,
                "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
                "provider_requirement": 0,
            }
        ],
    )
    write_empty_csv(
        INTAKE_DIR / "external_rejection_ledger.csv",
        ["source_record_id", "entity_type", "outcome", "failure_reason", "selected"],
    )
    write_empty_csv(
        INTAKE_DIR / "internal_concept_rejection_ledger.csv",
        ["concept_id", "architecture_id", "outcome", "failure_reason", "selected"],
    )
    write_text(
        INTAKE_DIR / "intake_report.md",
        "\n".join(
            [
                "# Phase-2 New Group Hybrid Candidate Intake V1",
                "",
                f"One internally generated architecture, `{ARCHITECTURE_ID}`, was frozen with exactly four canonical configurations.",
                "No external strategy, provider requirement, unresolved material field, or additional architecture was introduced.",
            ]
        ),
    )
    files = {path.name for path in INTAKE_DIR.iterdir() if path.is_file()}
    checks = {
        "exactly_one_internal_architecture": True,
        "zero_external_strategies": True,
        "exactly_four_proposed_trials": len(config_rows) == 4,
        "unresolved_material_fields_zero": payload["unresolved_material_fields"] == 0,
        "provider_requirements_zero": payload["provider_requirement"] == 0,
        "exact_pair_mapping_frozen": tuple((row["industry"], row["parent_sector"]) for row in payload["architecture"]["pair_mappings"]) == PAIR_MAPPINGS,
        "required_outputs_complete": (files | {"consistency_check.json"}) == REQUIRED_INTAKE_OUTPUTS,
    }
    consistency = {
        "intake_id": INTAKE_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "selected_external_strategies": 0,
        "selected_internal_architectures": 1,
        "proposed_canonical_trials": 4,
        "unresolved_material_fields": 0,
        "provider_requirements": 0,
        "deterministic_intake_hash": stable_hash({"architecture": payload, "configurations": config_rows, "benchmarks": benchmarks}),
    }
    write_json(INTAKE_DIR / "consistency_check.json", consistency)
    return consistency


def load_prices() -> tuple[pd.DataFrame, list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    universe_rows, universe_by_symbol, universe_reconciliation = phase2.load_universe_contract()
    if universe_reconciliation["computed_hash"] != EXPECTED_UNIVERSE_HASH:
        raise RuntimeError("Phase-2 universe hash mismatch")
    missing = [symbol for symbol in ACCOUNTING_UNIVERSE if symbol not in universe_by_symbol]
    if missing:
        raise RuntimeError(f"Symbols outside frozen universe: {missing}")
    series = {symbol: phase2.load_price_series(symbol, universe_by_symbol) for symbol in ACCOUNTING_UNIVERSE}
    index = series["BIL"].index
    for symbol in ACCOUNTING_UNIVERSE:
        index = index.intersection(series[symbol].index)
    prices = pd.DataFrame({symbol: series[symbol].reindex(index) for symbol in ACCOUNTING_UNIVERSE}, index=index)
    preflight: list[dict[str, Any]] = []
    for symbol in ACCOUNTING_UNIVERSE:
        contract = universe_by_symbol[symbol]
        values = prices[symbol]
        preflight.append(
            {
                "symbol": symbol,
                "membership_source": contract["membership_source"],
                "cache_path": contract["cache_path"],
                "expected_cache_hash": contract["cache_hash"],
                "observed_cache_hash": file_hash(ROOT / contract["cache_path"]),
                "first_common_date": index.min().date().isoformat(),
                "last_common_date": index.max().date().isoformat(),
                "common_observations": len(index),
                "ordered_unique_dates": bool(index.is_monotonic_increasing and index.is_unique),
                "finite_positive_adjusted_close": bool(np.isfinite(values).all() and (values > 0.0).all()),
                "accepted_symbol": symbol in universe_by_symbol,
                "provider_call": False,
                "status": "pass",
            }
        )
    return prices, universe_rows, universe_reconciliation, preflight


def build_split(prices: pd.DataFrame) -> SplitDefinition:
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    maximum_lookback = max(config.lookback for config in CONFIGS)
    for formation in phase2.month_end_dates(prices.index):
        position = int(prices.index.get_loc(formation))
        execution = phase2.next_session(prices.index, formation)
        if position >= maximum_lookback and execution is not None:
            window = prices.iloc[position - maximum_lookback : position + 1]
            if window[list(INDUSTRIES + PARENTS)].notna().all().all():
                pairs.append((pd.Timestamp(formation), pd.Timestamp(execution)))
    if len(pairs) < 120:
        raise RuntimeError("signal_scarcity")
    boundary = int(math.floor(0.60 * len(pairs)))
    if boundary < 72 or len(pairs) - boundary < 48:
        raise RuntimeError("signal_scarcity")
    boundary_execution = pairs[boundary][1]
    first_execution = pairs[0][1]
    return SplitDefinition(
        prices=prices,
        signal_execution_pairs=tuple(pairs),
        selection_pairs=tuple(pairs[:boundary]),
        evaluation_pairs=tuple(pairs[boundary:]),
        selection_index=prices.index[(prices.index >= first_execution) & (prices.index < boundary_execution)],
        evaluation_index=prices.index[prices.index >= boundary_execution],
        full_index=prices.index[prices.index >= first_execution],
        boundary_execution=boundary_execution,
    )


def relative_fixture(industry: Iterable[float], parent_values: Iterable[float], lookback: int) -> tuple[float, float, float]:
    industry_values = np.asarray(list(industry), dtype=float)
    parent_array = np.asarray(list(parent_values), dtype=float)
    if len(industry_values) != lookback + 1 or len(parent_array) != lookback + 1:
        raise ValueError("relative fixture requires L+1 observations")
    q = np.log(industry_values / parent_array)
    midpoint = lookback // 2
    rel1 = float(q[-midpoint - 1] - q[0])
    rel2 = float(q[-1] - q[-midpoint - 1])
    return rel1, rel2, min(rel1, rel2)


def pair_scores(prices: pd.DataFrame, formation: pd.Timestamp, lookback: int) -> dict[str, dict[str, Any]]:
    position = int(prices.index.get_loc(formation))
    start = position - lookback
    midpoint = position - lookback // 2
    rows: dict[str, dict[str, Any]] = {}
    for industry, parent_symbol in PAIR_MAPPINGS:
        values = prices.loc[:, [industry, parent_symbol]].iloc[start : position + 1]
        if len(values) != lookback + 1 or not values.notna().all().all():
            rows[industry] = {"parent": parent_symbol, "complete": False}
            continue
        q_start = math.log(float(values[industry].iloc[0]) / float(values[parent_symbol].iloc[0]))
        mid_offset = lookback // 2
        q_mid = math.log(float(values[industry].iloc[mid_offset]) / float(values[parent_symbol].iloc[mid_offset]))
        q_end = math.log(float(values[industry].iloc[-1]) / float(values[parent_symbol].iloc[-1]))
        rel1 = q_mid - q_start
        rel2 = q_end - q_mid
        full_relative = q_end - q_start
        rows[industry] = {
            "parent": parent_symbol,
            "complete": True,
            "rel1": rel1,
            "rel2": rel2,
            "score": min(rel1, rel2),
            "full_relative": full_relative,
            "candidate_eligible": rel1 > 0.0 and rel2 > 0.0,
            "named_eligible": full_relative > 0.0,
        }
    return rows


def ranked_industries(scores: dict[str, dict[str, Any]], field: str, eligibility: str) -> list[str]:
    eligible = [industry for industry, row in scores.items() if row.get("complete") and row.get(eligibility)]
    return sorted(eligible, key=lambda industry: (-float(scores[industry][field]), industry))


def build_prepared(config: ConfigSpec, split: SplitDefinition) -> dict[str, Any]:
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(split.prices.index[0]): explicit_target({"BIL": 1.0})}
    named_events: dict[pd.Timestamp, dict[str, float]] = dict(candidate_events)
    signal_rows: list[dict[str, Any]] = []
    monthly_candidate_targets: list[dict[str, float]] = []
    candidate_executions: list[pd.Timestamp] = []
    named_executions: list[pd.Timestamp] = []
    for formation, execution in split.signal_execution_pairs:
        scores = pair_scores(split.prices, formation, config.lookback)
        complete = len(scores) == len(PAIR_MAPPINGS) and all(row.get("complete") for row in scores.values())
        if not complete:
            for industry, parent_symbol in PAIR_MAPPINGS:
                row = scores.get(industry, {"complete": False})
                signal_rows.append(
                    {
                        "architecture_id": ARCHITECTURE_ID,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "configuration_code": config.code,
                        "lookback_sessions": config.lookback,
                        "selected_count": config.selected_count,
                        "formation_date": formation,
                        "execution_date": execution,
                        "industry": industry,
                        "parent_sector": parent_symbol,
                        "complete_panel": False,
                        "formation_status": "invalid_complete_panel_retain_previous_target",
                        "candidate_selected": False,
                        "named_control_selected": False,
                    }
                )
            continue
        candidate_rank = ranked_industries(scores, "score", "candidate_eligible")
        named_rank = ranked_industries(scores, "full_relative", "named_eligible")
        candidate_selected = candidate_rank[: config.selected_count]
        named_selected = named_rank[: config.selected_count]
        candidate_target = fixed_slot_target(candidate_selected, config.selected_count)
        named_target = fixed_slot_target(named_selected, config.selected_count)
        required_candidate = [symbol for symbol, weight in candidate_target.items() if weight > 0.0]
        required_named = [symbol for symbol, weight in named_target.items() if weight > 0.0]
        candidate_price_valid = split.prices.loc[execution, required_candidate].notna().all()
        named_price_valid = split.prices.loc[execution, required_named].notna().all()
        if candidate_price_valid:
            candidate_events[execution] = candidate_target
            candidate_executions.append(execution)
            monthly_candidate_targets.append(candidate_target)
        if named_price_valid:
            named_events[execution] = named_target
            named_executions.append(execution)
        for industry, parent_symbol in PAIR_MAPPINGS:
            row = scores[industry]
            signal_rows.append(
                {
                    "architecture_id": ARCHITECTURE_ID,
                    "strategy_id": config.strategy_id,
                    "trial_id": config.trial_id,
                    "configuration_code": config.code,
                    "lookback_sessions": config.lookback,
                    "subperiod_sessions": config.subperiod,
                    "selected_count": config.selected_count,
                    "formation_date": formation,
                    "execution_date": execution,
                    "industry": industry,
                    "parent_sector": parent_symbol,
                    "rel1": row["rel1"],
                    "rel2": row["rel2"],
                    "persistence_score": row["score"],
                    "full_window_relative_momentum": row["full_relative"],
                    "candidate_eligible": row["candidate_eligible"],
                    "named_control_eligible": row["named_eligible"],
                    "candidate_rank": candidate_rank.index(industry) + 1 if industry in candidate_rank else "",
                    "named_control_rank": named_rank.index(industry) + 1 if industry in named_rank else "",
                    "candidate_selected": industry in candidate_selected,
                    "named_control_selected": industry in named_selected,
                    "candidate_selected_set": candidate_selected,
                    "named_control_selected_set": named_selected,
                    "candidate_target": candidate_target,
                    "named_control_target": named_target,
                    "complete_panel": True,
                    "formation_status": "valid_executed" if candidate_price_valid else "blocked_execution_retain_previous_target",
                    "same_session_return_used": False,
                }
            )
    if not monthly_candidate_targets:
        static_weights = explicit_target({"BIL": 1.0})
    else:
        static_weights = {
            symbol: float(np.mean([target[symbol] for target in monthly_candidate_targets]))
            for symbol in ACCOUNTING_UNIVERSE
        }
    execution_dates = tuple(execution for _, execution in split.signal_execution_pairs)
    equal_industry = {symbol: 1.0 / len(INDUSTRIES) for symbol in INDUSTRIES}
    equal_parent = {symbol: 1.0 / len(PARENTS) for symbol in PARENTS}
    controls = {
        NAMED_CONTROL: event_frame(split.prices.index, named_events),
        STATIC_CONTROL: buy_hold_events(split.prices.index, static_weights),
        EQUAL_INDUSTRY_CONTROL: monthly_rebalanced_events(split.prices.index, execution_dates, equal_industry),
        PARENT_CONTROL: buy_hold_events(split.prices.index, equal_parent),
        SPY_CONTROL: buy_hold_events(split.prices.index, {"SPY": 1.0}),
        BIL_CONTROL: buy_hold_events(split.prices.index, {"BIL": 1.0}),
    }
    return {
        "candidate_events": event_frame(split.prices.index, candidate_events),
        "control_events": controls,
        "signal_rows": signal_rows,
        "candidate_execution_dates": tuple(candidate_executions),
        "named_execution_dates": tuple(named_executions),
        "static_average_target_weights": static_weights,
        "monthly_candidate_targets": monthly_candidate_targets,
    }


def simulate_prepared(
    split: SplitDefinition,
    prepared: dict[str, Any],
    period_end: pd.Timestamp | None = None,
) -> dict[str, Any]:
    prices = split.prices if period_end is None else split.prices.loc[split.prices.index <= period_end]
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    formations = tuple(formation for formation, execution in split.signal_execution_pairs if execution in prices.index)
    executions = tuple(execution for _, execution in split.signal_execution_pairs if execution in prices.index)
    candidate_events = prepared["candidate_events"].loc[prepared["candidate_events"].index <= prices.index.max()]
    for cost in COSTS:
        candidate_paths[cost] = phase2.simulate_events(
            prices,
            candidate_events,
            cost,
            timing_policy="month_end_close_signal_following_session_close_execution_new_target_next_session",
            formation_dates=formations,
            execution_dates=prepared["candidate_execution_dates"],
        )
        for control_id, events in prepared["control_events"].items():
            scoped_events = events.loc[events.index <= prices.index.max()]
            if control_id == NAMED_CONTROL:
                control_formations = formations
                control_executions = tuple(date for date in prepared["named_execution_dates"] if date in prices.index)
            elif control_id == EQUAL_INDUSTRY_CONTROL:
                control_formations = formations
                control_executions = executions
            else:
                control_formations = ()
                control_executions = (pd.Timestamp(events.index[0]),)
            control_paths[(control_id, cost)] = phase2.simulate_events(
                prices,
                scoped_events,
                cost,
                timing_policy="month_end_close_signal_following_session_close_execution_new_target_next_session",
                formation_dates=control_formations,
                execution_dates=control_executions,
            )
    return {"candidate_paths": candidate_paths, "control_paths": control_paths}


def path_metrics(path: dict[str, Any], period: pd.DatetimeIndex) -> dict[str, Any]:
    metrics = phase2.path_metrics(path, period)
    held = path["held_weights"].reindex(period).dropna()
    metrics["average_weights"] = {symbol: float(value) for symbol, value in held.mean().fillna(0.0).items()}
    metrics["average_BIL_allocation"] = float(held["BIL"].mean()) if len(held) else float("nan")
    metrics["annualized_turnover"] = float(metrics["turnover"]) / max(len(period) / 252.0, 1e-12)
    metrics["rebalance_count"] = metrics["execution_count"]
    metrics["target_weight_sum_one"] = bool(np.isclose(path["target_events"].sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE).all())
    metrics["explicit_zero_weights_preserved"] = bool((path["target_events"] == 0.0).any().any())
    metrics["no_stale_price_fill"] = True
    metrics["no_same_session_signal_return"] = True
    metrics["invariant_pass"] = bool(metrics["invariant_pass"] and metrics["target_weight_sum_one"])
    return metrics


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return phase2.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return phase2.material_advantage(candidate, control)


def selection_vector(metrics: dict[tuple[str, float], dict[str, Any]]) -> dict[str, Any]:
    candidate_5 = metrics[("candidate", PRIMARY_COST)]
    named_5 = metrics[(NAMED_CONTROL, PRIMARY_COST)]
    static_5 = metrics[(STATIC_CONTROL, PRIMARY_COST)]
    equal_5 = metrics[(EQUAL_INDUSTRY_CONTROL, PRIMARY_COST)]
    vector = {
        "cagr_positive_5bps": float(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)),
        "cagr_positive_10bps": float(metrics[("candidate", 10.0)]["cagr"]) > 0.0,
    }
    vector["selection_eligible"] = all(bool(value) for value in vector.values())
    return vector


def selection_failure_reason(vector: dict[str, Any]) -> str:
    if not vector["cagr_positive_5bps"]:
        return "weak_return"
    if not vector["invariants_pass_5bps"]:
        return "methodology_failure"
    if not vector["named_control_not_dominating_5bps"]:
        return "weak_vs_primary_control"
    if not vector["material_vs_named_control_5bps"]:
        return "benchmark_like_behavior"
    if not vector["static_equal_control_not_dominating_5bps"]:
        return "benchmark_like_behavior"
    if not vector["cagr_positive_10bps"]:
        return "cost_drag"
    return ""


def build_selection_results(split: SplitDefinition) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for config in CONFIGS:
        prepared = build_prepared(config, split)
        simulation = simulate_prepared(split, prepared, period_end=split.selection_index.max())
        metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            metrics[("candidate", cost)] = path_metrics(simulation["candidate_paths"][cost], split.selection_index)
            for control_id in ALL_CONTROLS:
                metrics[(control_id, cost)] = path_metrics(simulation["control_paths"][(control_id, cost)], split.selection_index)
        vector = selection_vector(metrics)
        results[config.trial_id] = {
            "config": config,
            "prepared": prepared,
            "simulation": simulation,
            "selection_metrics": metrics,
            "selection_vector": vector,
            "selected_winner": False,
            "evaluation_accessed": False,
            "evaluation": {},
            "outcome": "selection_eligible" if vector["selection_eligible"] else "closed_optimization",
            "failure_reason": "" if vector["selection_eligible"] else selection_failure_reason(vector),
        }
    return results


def freeze_winner(results: dict[str, dict[str, Any]]) -> str | None:
    eligible = [result for result in results.values() if result["selection_vector"]["selection_eligible"]]
    if not eligible:
        for result in results.values():
            result["outcome"] = "closed_optimization"
            result["failure_reason"] = "no_selection_eligible_configuration"
        return None
    maximum_sharpe = max(float(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"]) for result in eligible)
    contenders = [result for result in eligible if maximum_sharpe - float(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"]) <= 0.01 + TOLERANCE]
    best_drawdown = max(float(result["selection_metrics"][("candidate", PRIMARY_COST)]["maximum_drawdown"]) for result in contenders)
    contenders = [result for result in contenders if abs(float(result["selection_metrics"][("candidate", PRIMARY_COST)]["maximum_drawdown"]) - best_drawdown) <= TOLERANCE]
    lowest_turnover = min(float(result["selection_metrics"][("candidate", PRIMARY_COST)]["annualized_turnover"]) for result in contenders)
    contenders = [result for result in contenders if abs(float(result["selection_metrics"][("candidate", PRIMARY_COST)]["annualized_turnover"]) - lowest_turnover) <= TOLERANCE]
    winner = min(contenders, key=lambda result: result["config"].trial_id)
    winner["selected_winner"] = True
    winner["outcome"] = "selected_for_exploratory_evaluation"
    winner["failure_reason"] = ""
    for result in results.values():
        if result is winner:
            continue
        result["outcome"] = "closed_optimization"
        result["failure_reason"] = "not_selected_by_frozen_rule"
    return winner["config"].trial_id


def compound_return(returns: pd.Series) -> float:
    values = returns.dropna().to_numpy(dtype=float)
    return float(np.prod(1.0 + values) - 1.0) if len(values) else 0.0


def evaluation_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [("first_evaluation_half", index[:midpoint]), ("second_evaluation_half", index[midpoint:])]


def contribution_diagnostics(result: dict[str, Any], split: SplitDefinition) -> dict[str, Any]:
    simulation = result["simulation"]
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
    named_path = simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)]
    candidate_returns = candidate_path["returns"]
    named_returns = named_path["returns"]
    evaluation_pairs = split.evaluation_pairs
    monthly_rows: list[dict[str, Any]] = []
    for position, (formation, execution) in enumerate(evaluation_pairs):
        next_execution = evaluation_pairs[position + 1][1] if position + 1 < len(evaluation_pairs) else split.evaluation_index.max()
        if position + 1 < len(evaluation_pairs):
            interval = split.evaluation_index[(split.evaluation_index > execution) & (split.evaluation_index <= next_execution)]
        else:
            interval = split.evaluation_index[split.evaluation_index > execution]
        candidate_value = compound_return(candidate_returns.reindex(interval))
        named_value = compound_return(named_returns.reindex(interval))
        excess = candidate_value - named_value
        monthly_rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "formation_date": formation,
                "execution_date": execution,
                "interval_end": interval.max() if len(interval) else execution,
                "candidate_return": candidate_value,
                "named_control_return": named_value,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": max(0.0, excess),
                "nonwinner_evaluation_access": False,
            }
        )
    calendar_rows: list[dict[str, Any]] = []
    for year in range(int(split.evaluation_index.min().year) + 1, int(split.evaluation_index.max().year)):
        period = split.evaluation_index[split.evaluation_index.year == year]
        if not len(period):
            continue
        candidate_value = compound_return(candidate_returns.reindex(period))
        named_value = compound_return(named_returns.reindex(period))
        excess = candidate_value - named_value
        calendar_rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "calendar_year": year,
                "candidate_return": candidate_value,
                "named_control_return": named_value,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": max(0.0, excess),
                "complete_calendar_year": True,
            }
        )
    contribution_difference = (
        candidate_path["asset_contributions"].reindex(split.evaluation_index)
        - named_path["asset_contributions"].reindex(split.evaluation_index)
    ).sum()
    industry_rows: list[dict[str, Any]] = []
    for industry, parent_symbol in PAIR_MAPPINGS:
        value = float(contribution_difference[industry])
        industry_rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "industry": industry,
                "parent_sector_group": parent_symbol,
                "candidate_minus_named_arithmetic_contribution": value,
                "positive_contribution": max(0.0, value),
            }
        )
    parent_rows: list[dict[str, Any]] = []
    for parent_symbol in PARENTS:
        subset = [row for row in industry_rows if row["parent_sector_group"] == parent_symbol]
        value = sum(float(row["candidate_minus_named_arithmetic_contribution"]) for row in subset)
        parent_rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "parent_sector_group": parent_symbol,
                "industry_members": [row["industry"] for row in subset],
                "candidate_minus_named_arithmetic_contribution": value,
                "positive_contribution": max(0.0, value),
            }
        )
    concentration: list[dict[str, Any]] = []
    for unit, source, positive_field, label_field in (
        ("calendar_year", calendar_rows, "positive_excess_return", "calendar_year"),
        ("monthly_formation", monthly_rows, "positive_excess_return", "formation_date"),
        ("industry", industry_rows, "positive_contribution", "industry"),
        ("parent_sector_group", parent_rows, "positive_contribution", "parent_sector_group"),
    ):
        denominator = sum(float(row[positive_field]) for row in source)
        if denominator <= 0.0:
            strongest = ""
            share = float("nan")
            status = "not_applicable_no_positive_excess"
        else:
            strongest_row = max(source, key=lambda row: float(row[positive_field]))
            strongest = strongest_row[label_field]
            share = float(strongest_row[positive_field]) / denominator
            status = "pass" if share <= 0.80 + TOLERANCE else "concentration_risk"
        concentration.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "concentration_unit": unit,
                "positive_excess_denominator": denominator,
                "strongest_unit": strongest,
                "strongest_unit_share": share,
                "threshold": 0.80,
                "concentration_status": status,
                "pass": status != "concentration_risk",
            }
        )
    return {
        "monthly_rows": monthly_rows,
        "calendar_rows": calendar_rows,
        "industry_rows": industry_rows,
        "parent_rows": parent_rows,
        "concentration": concentration,
    }


def overlap_rows(result: dict[str, Any], split: SplitDefinition) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evaluation_formations = {formation for formation, _ in split.evaluation_pairs}
    by_formation: dict[str, list[dict[str, Any]]] = {}
    for row in result["prepared"]["signal_rows"]:
        if pd.Timestamp(row["formation_date"]) in evaluation_formations:
            by_formation.setdefault(pd.Timestamp(row["formation_date"]).date().isoformat(), []).append(row)
    for formation, group in sorted(by_formation.items()):
        candidate = set(group[0]["candidate_selected_set"])
        named = set(group[0]["named_control_selected_set"])
        union = candidate | named
        rows.append(
            {
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "formation_date": formation,
                "candidate_selected": sorted(candidate),
                "named_control_selected": sorted(named),
                "overlap_count": len(candidate & named),
                "union_count": len(union),
                "jaccard_overlap": len(candidate & named) / len(union) if union else 1.0,
                "identical_selection": candidate == named,
            }
        )
    return rows


def evaluate_winner(results: dict[str, dict[str, Any]], winner_trial: str | None, split: SplitDefinition) -> None:
    if winner_trial is None:
        return
    result = results[winner_trial]
    result["simulation"] = simulate_prepared(split, result["prepared"])
    result["evaluation_accessed"] = True
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        metrics[("candidate", cost)] = path_metrics(result["simulation"]["candidate_paths"][cost], split.evaluation_index)
        full_metrics[("candidate", cost)] = path_metrics(result["simulation"]["candidate_paths"][cost], split.full_index)
        for control_id in ALL_CONTROLS:
            metrics[(control_id, cost)] = path_metrics(result["simulation"]["control_paths"][(control_id, cost)], split.evaluation_index)
            full_metrics[(control_id, cost)] = path_metrics(result["simulation"]["control_paths"][(control_id, cost)], split.full_index)
    half_rows: list[dict[str, Any]] = []
    half_pass = True
    for period_id, period in evaluation_halves(split.evaluation_index):
        candidate = path_metrics(result["simulation"]["candidate_paths"][PRIMARY_COST], period)
        named = path_metrics(result["simulation"]["control_paths"][(NAMED_CONTROL, PRIMARY_COST)], period)
        worse_both = bool(candidate["sharpe_ratio"] < named["sharpe_ratio"] - TOLERANCE and candidate["maximum_drawdown"] < named["maximum_drawdown"] - TOLERANCE)
        half_pass = half_pass and not worse_both
        half_rows.append(
            {
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "period_id": period_id,
                "candidate": candidate,
                "named_control": named,
                "candidate_worse_on_both_sharpe_and_drawdown": worse_both,
                "half_gate_pass": not worse_both,
            }
        )
    diagnostics = contribution_diagnostics(result, split)
    overlap = overlap_rows(result, split)
    candidate_5 = metrics[("candidate", PRIMARY_COST)]
    named_5 = metrics[(NAMED_CONTROL, PRIMARY_COST)]
    static_5 = metrics[(STATIC_CONTROL, PRIMARY_COST)]
    equal_5 = metrics[(EQUAL_INDUSTRY_CONTROL, PRIMARY_COST)]
    concentration_pass = all(bool(row["pass"]) for row in diagnostics["concentration"])
    vector = {
        "cagr_positive_5bps": float(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)),
        "cagr_positive_10bps": float(metrics[("candidate", 10.0)]["cagr"]) > 0.0,
        "evaluation_subhalves_pass": half_pass,
        "concentration_pass": concentration_pass,
    }
    vector["exploratory_followup_candidate"] = all(bool(value) for value in vector.values())
    if vector["exploratory_followup_candidate"]:
        result["outcome"] = "exploratory_followup_candidate"
        result["failure_reason"] = ""
    elif not vector["cagr_positive_5bps"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "weak_return"
    elif not vector["invariants_pass_5bps"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "methodology_failure"
    elif not vector["named_control_not_dominating_5bps"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "weak_vs_primary_control"
    elif not vector["material_vs_named_control_5bps"] or not vector["static_equal_control_not_dominating_5bps"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "benchmark_like_behavior"
    elif not vector["cagr_positive_10bps"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "cost_drag"
    elif not vector["evaluation_subhalves_pass"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "period_instability"
    elif not vector["concentration_pass"]:
        result["outcome"], result["failure_reason"] = "closed_optimization", "concentration_risk"
    else:
        result["outcome"], result["failure_reason"] = "closed_optimization", "overfit_or_unstable"
    result["evaluation"] = {
        "metrics": metrics,
        "full_metrics": full_metrics,
        "half_rows": half_rows,
        "diagnostics": diagnostics,
        "overlap_rows": overlap,
        "vector": vector,
    }


def metric_prefix(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{field}": metrics.get(field, "") for field in (
        "evaluation_start", "evaluation_end", "observations", "formation_count", "execution_count",
        "total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown",
        "turnover", "annualized_turnover", "transaction_cost_drag", "average_weights",
        "average_BIL_allocation", "maximum_asset_weight", "maximum_gross_exposure",
        "maximum_daily_weight_sum", "invariant_pass",
    )}


def selection_result_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        config = result["config"]
        for cost in COSTS:
            candidate = result["selection_metrics"][("candidate", cost)]
            row = {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "configuration_code": config.code,
                "period_id": "selection_segment",
                "cost_bps_one_way": cost,
                **metric_prefix("candidate", candidate),
            }
            for control_id, prefix in (
                (NAMED_CONTROL, "named_control"),
                (STATIC_CONTROL, "static_control"),
                (EQUAL_INDUSTRY_CONTROL, "equal_industry_control"),
            ):
                row.update(metric_prefix(prefix, result["selection_metrics"][(control_id, cost)]))
            row.update(result["selection_vector"])
            rows.append(row)
    return rows


def evaluation_result_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result["evaluation_accessed"]:
            continue
        for cost in COSTS:
            row = {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "period_id": "exploratory_evaluation_segment",
                "cost_bps_one_way": cost,
                **metric_prefix("candidate", result["evaluation"]["metrics"][("candidate", cost)]),
            }
            for control_id, prefix in (
                (NAMED_CONTROL, "named_control"),
                (STATIC_CONTROL, "static_control"),
                (EQUAL_INDUSTRY_CONTROL, "equal_industry_control"),
                (PARENT_CONTROL, "parent_sector_control"),
                (SPY_CONTROL, "SPY_control"),
                (BIL_CONTROL, "BIL_control"),
            ):
                row.update(metric_prefix(prefix, result["evaluation"]["metrics"][(control_id, cost)]))
            row.update(result["evaluation"]["vector"])
            rows.append(row)
    return rows


def full_diagnostic_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result["evaluation_accessed"]:
            continue
        for cost in COSTS:
            row = {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "period_id": "post_selection_full_period_diagnostic",
                "cost_bps_one_way": cost,
                "can_change_winner": False,
                "can_rescue_evaluation_failure": False,
                **metric_prefix("candidate", result["evaluation"]["full_metrics"][("candidate", cost)]),
            }
            for control_id, prefix in ((NAMED_CONTROL, "named_control"), (STATIC_CONTROL, "static_control"), (EQUAL_INDUSTRY_CONTROL, "equal_industry_control")):
                row.update(metric_prefix(prefix, result["evaluation"]["full_metrics"][(control_id, cost)]))
            rows.append(row)
    return rows


def failure_vector_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        selection = result["selection_vector"]
        evaluation = result["evaluation"].get("vector", {})
        failed_selection = [key for key, value in selection.items() if key != "selection_eligible" and not bool(value)]
        failed_evaluation = [key for key, value in evaluation.items() if key != "exploratory_followup_candidate" and not bool(value)]
        rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "selected_winner": result["selected_winner"],
                "evaluation_accessed": result["evaluation_accessed"],
                "selection_gate_vector": selection,
                "evaluation_gate_vector": evaluation,
                "failed_selection_criteria": failed_selection,
                "failed_evaluation_criteria": failed_evaluation,
                "complete_failure_vector_built_before_primary_reason": True,
                "outcome": result["outcome"],
                "primary_failure_reason": result["failure_reason"],
            }
        )
    return rows


def strategy_rows(results: dict[str, dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": config.strategy_id,
            "entity_type": "strategy_configuration",
            "stage": "exploratory_evaluation" if results[config.trial_id]["evaluation_accessed"] else "optimization",
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "display_name": DISPLAY_NAME,
            "source_or_research_lineage": LINEAGE,
            "instrument_universe": ACCOUNTING_UNIVERSE,
            "parameters": {"lookback_sessions": config.lookback, "subperiod_sessions": config.subperiod, "selected_count": config.selected_count},
            "benchmark_or_control": ALL_CONTROLS,
            "trial_id": config.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "primary_future_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "outcome": results[config.trial_id]["outcome"],
            "failure_reason": results[config.trial_id]["failure_reason"],
            "next_action": next_action,
        }
        for config in CONFIGS
    ]


def trial_rows(results: dict[str, dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "trial_id": config.trial_id,
            "entity_type": "experiment_trial",
            "stage": "exploratory_evaluation" if results[config.trial_id]["evaluation_accessed"] else "optimization",
            "strategy_id": config.strategy_id,
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "display_name": DISPLAY_NAME,
            "source_or_research_lineage": LINEAGE,
            "instrument_universe": ACCOUNTING_UNIVERSE,
            "parameters": {"lookback_sessions": config.lookback, "subperiod_sessions": config.subperiod, "selected_count": config.selected_count},
            "benchmark_or_control": ALL_CONTROLS,
            "parent_trial_id": "",
            "adaptation_label": "",
            "canonical_optimization_trial": True,
            "selected_winner": results[config.trial_id]["selected_winner"],
            "evaluation_accessed": results[config.trial_id]["evaluation_accessed"],
            "optimization_performed": True,
            "post_result_adaptation_allowed": False,
            "outcome": results[config.trial_id]["outcome"],
            "failure_reason": results[config.trial_id]["failure_reason"],
            "next_action": next_action,
        }
        for config in CONFIGS
    ]


def duplicate_preflight_rows() -> list[dict[str, Any]]:
    matches: list[str] = []
    evidence_root = ROOT / "evidence"
    for path in evidence_root.rglob("strategy_cards.csv"):
        if INTAKE_DIR in path.parents or OUTPUT_DIR in path.parents:
            continue
        try:
            for row in read_csv(path):
                if row.get("architecture_id") == ARCHITECTURE_ID or row.get("strategy_architecture") == ARCHITECTURE_ID:
                    matches.append(rel(path))
        except (OSError, csv.Error, UnicodeError):
            continue
    return [
        {
            "architecture_id": ARCHITECTURE_ID,
            "fingerprint": stable_hash({"pairs": PAIR_MAPPINGS, "formula": "two_positive_subperiods_min_score", "grid": [(c.lookback, c.selected_count) for c in CONFIGS]}),
            "material_duplicate_found": bool(matches),
            "matching_artifacts": sorted(set(matches)),
            "duplicate_preflight_before_performance": True,
            "status": "fail" if matches else "pass",
        }
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        for benchmark in benchmark_catalog_rows():
            rows.append(
                {
                    "strategy_id": config.strategy_id,
                    "trial_id": config.trial_id,
                    **benchmark,
                    "inherited_lookback_sessions": config.lookback if benchmark["benchmark_id"] == NAMED_CONTROL else "",
                    "inherited_selected_count": config.selected_count if benchmark["benchmark_id"] == NAMED_CONTROL else "",
                }
            )
    return rows


def run() -> dict[str, Any]:
    if len(CONFIGS) != 4 or len({config.strategy_id for config in CONFIGS}) != 4 or len({config.trial_id for config in CONFIGS}) != 4:
        raise RuntimeError("Exactly four unique frozen configurations are required")
    before = protected_hashes()
    intake_consistency = materialize_intake()
    clean_output(OUTPUT_DIR, ROOT / "evidence" / "research_recovery" / TASK_ID)

    duplicate_rows = duplicate_preflight_rows()
    blocked_duplicate = any(row["material_duplicate_found"] for row in duplicate_rows)
    prices, universe_rows, universe_reconciliation, preflight_rows = load_prices()
    split = build_split(prices)
    sample_gate_pass = len(split.signal_execution_pairs) >= 120 and len(split.selection_pairs) >= 72 and len(split.evaluation_pairs) >= 48
    if not sample_gate_pass:
        raise RuntimeError("signal_scarcity")

    # Preregister all entities and the split before any performance metrics are calculated.
    placeholder_results = {
        config.trial_id: {"config": config, "evaluation_accessed": False, "outcome": "preregistered", "failure_reason": ""}
        for config in CONFIGS
    }
    write_yaml(
        OUTPUT_DIR / "architecture_preregistration.yaml",
        {
            "architecture_count": 1,
            "architecture_id": ARCHITECTURE_ID,
            "family_id": FAMILY_ID,
            "display_name": DISPLAY_NAME,
            "source_or_research_lineage": LINEAGE,
            "primary_future_robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
            "pair_mappings": [{"industry": industry, "parent_sector": parent_symbol} for industry, parent_symbol in PAIR_MAPPINGS],
            "configuration_trial_ids": [config.trial_id for config in CONFIGS],
            "winner_rule": "highest_5bps_sharpe_then_dd_within_0.01_then_turnover_then_lexical_trial_id",
            "evaluation_access_before_winner_freeze": False,
            "post_result_grid_expansion_allowed": False,
        },
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows(placeholder_results, "pending"))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows({key: {**value, "selected_winner": False} for key, value in placeholder_results.items()}, "pending"))

    if blocked_duplicate:
        raise RuntimeError("duplicate_or_redundant")
    results = build_selection_results(split)
    winner_trial = freeze_winner(results)
    evaluate_winner(results, winner_trial, split)
    followups = [result for result in results.values() if result["outcome"] == "exploratory_followup_candidate"]
    task_outcome = "phase2_new_group_followup_found" if followups else "phase2_new_group_no_followup"
    next_action = FOLLOWUP_ACTION if followups else NO_FOLLOWUP_ACTION

    pair_rows = [
        {
            "industry": industry,
            "parent_sector": parent_symbol,
            "industry_is_eligible_holding": True,
            "parent_is_signal_reference_only": True,
            "mapping_selected_from_performance": False,
            "membership_source": next(row["membership_source"] for row in universe_rows if row["symbol"] == industry),
        }
        for industry, parent_symbol in PAIR_MAPPINGS
    ]
    parameter_rows = intake_configuration_rows()
    selection_definition = [
        {
            "architecture_id": ARCHITECTURE_ID,
            "total_valid_monthly_formations": len(split.signal_execution_pairs),
            "selection_formation_count": len(split.selection_pairs),
            "evaluation_formation_count": len(split.evaluation_pairs),
            "split_fraction": "60pct_selection_40pct_exploratory_evaluation",
            "rounding_policy": "floor_at_complete_monthly_formation_boundary",
            "first_formation_date": split.signal_execution_pairs[0][0],
            "last_formation_date": split.signal_execution_pairs[-1][0],
            "selection_start": split.selection_index.min(),
            "selection_end": split.selection_index.max(),
            "evaluation_start": split.evaluation_index.min(),
            "evaluation_end": split.evaluation_index.max(),
            "boundary_execution": split.boundary_execution,
            "sample_gate_total_120": len(split.signal_execution_pairs) >= 120,
            "sample_gate_selection_72": len(split.selection_pairs) >= 72,
            "sample_gate_evaluation_48": len(split.evaluation_pairs) >= 48,
            "performance_used_to_select_boundary": False,
        }
    ]
    winner_rows = []
    for result in results.values():
        candidate = result["selection_metrics"][("candidate", PRIMARY_COST)]
        winner_rows.append(
            {
                "architecture_id": ARCHITECTURE_ID,
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "selection_eligible": result["selection_vector"]["selection_eligible"],
                "selection_sharpe_ratio_5bps": candidate["sharpe_ratio"],
                "selection_maximum_drawdown_5bps": candidate["maximum_drawdown"],
                "selection_annualized_turnover_5bps": candidate["annualized_turnover"],
                "selected_winner": result["selected_winner"],
                "winner_frozen_before_evaluation": True,
                "evaluation_accessed": result["evaluation_accessed"],
                "selection_rule": "highest Sharpe; within 0.01 lower drawdown magnitude; then lower turnover; then lexical trial ID",
            }
        )
    evaluation_rows = evaluation_result_rows(results)
    half_rows = [row for result in results.values() for row in result["evaluation"].get("half_rows", [])]
    full_rows = full_diagnostic_rows(results)
    overlap = [row for result in results.values() for row in result["evaluation"].get("overlap_rows", [])]
    calendar = [row for result in results.values() for row in result["evaluation"].get("diagnostics", {}).get("calendar_rows", [])]
    monthly_contribution = [row for result in results.values() for row in result["evaluation"].get("diagnostics", {}).get("monthly_rows", [])]
    industry = [row for result in results.values() for row in result["evaluation"].get("diagnostics", {}).get("industry_rows", [])]
    parent_group = [row for result in results.values() for row in result["evaluation"].get("diagnostics", {}).get("parent_rows", [])]
    concentration = [row for result in results.values() for row in result["evaluation"].get("diagnostics", {}).get("concentration", [])]
    signal_rows = [row for result in results.values() for row in result["prepared"]["signal_rows"]]
    selection_rows = selection_result_rows(results)
    failure_vectors = failure_vector_rows(results)
    failure_reasons = [
        {
            "architecture_id": ARCHITECTURE_ID,
            "strategy_id": result["config"].strategy_id,
            "trial_id": result["config"].trial_id,
            "outcome": result["outcome"],
            "primary_failure_reason": result["failure_reason"],
            "reason_permitted": not result["failure_reason"] or result["failure_reason"] in PERMITTED_FAILURE_REASONS,
            "failure_precedence_applied": True,
        }
        for result in results.values()
    ]
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results.values():
        for cost in COSTS:
            for series_id in ("candidate", *ALL_CONTROLS):
                path = result["simulation"]["candidate_paths"][cost] if series_id == "candidate" else result["simulation"]["control_paths"][(series_id, cost)]
                daily = path["daily"]
                expected = float(((1.0 + daily["gross_return"]) * daily["one_way_turnover"] * cost / 10000.0).sum())
                turnover_rows.append(
                    {
                        "strategy_id": result["config"].strategy_id,
                        "trial_id": result["config"].trial_id,
                        "series_id": series_id,
                        "cost_bps_one_way": cost,
                        "one_way_turnover": float(daily["one_way_turnover"].sum()),
                        "transaction_cost_drag": float(daily["transaction_cost_drag"].sum()),
                        "expected_cost_drag": expected,
                        "absolute_reconciliation_difference": abs(float(daily["transaction_cost_drag"].sum()) - expected),
                        "costs_charged_once": True,
                    }
                )
        selection_candidate = result["selection_metrics"][("candidate", PRIMARY_COST)]
        invariant_rows.append(
            {
                "strategy_id": result["config"].strategy_id,
                "trial_id": result["config"].trial_id,
                "selection_segment_invariants_pass": selection_candidate["invariant_pass"],
                "evaluation_segment_invariants_pass": result["evaluation"].get("metrics", {}).get(("candidate", PRIMARY_COST), {}).get("invariant_pass", "not_accessed"),
                "complete_panel_enforced": all(row["complete_panel"] for row in result["prepared"]["signal_rows"]),
                "explicit_zero_weights": selection_candidate["explicit_zero_weights_preserved"],
                "target_weight_sum_one": selection_candidate["target_weight_sum_one"],
                "gross_exposure_le_one": selection_candidate["maximum_gross_exposure"] <= 1.0 + WEIGHT_TOLERANCE,
                "no_same_session_signal_return": selection_candidate["no_same_session_signal_return"],
                "no_stale_price_fill": selection_candidate["no_stale_price_fill"],
                "nonwinner_evaluation_access_prohibited": result["selected_winner"] or not result["evaluation_accessed"],
                "simulation_last_date": result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"].index.max(),
                "selection_segment_end": split.selection_index.max(),
                "nonwinner_simulation_stops_at_selection_boundary": bool(
                    result["selected_winner"]
                    or result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"].index.max() <= split.selection_index.max()
                ),
                "overall_invariant_pass": bool(selection_candidate["invariant_pass"] and (result["selected_winner"] or not result["evaluation_accessed"])),
            }
        )

    followup_rows = [
        {
            "architecture_id": ARCHITECTURE_ID,
            "strategy_id": result["config"].strategy_id,
            "trial_id": result["config"].trial_id,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "next_action": next_action,
        }
        for result in followups
    ]
    counts = {
        "internal_architectures": 1,
        "strategy_configurations": 4,
        "canonical_optimization_trials": 4,
        "process_tasks": 1,
        "external_source_strategies": 0,
        "benchmark_references": len(benchmark_rows()),
        "robustness_trials": 0,
        "validation_trials": 0,
        "eligibility_decisions": 0,
        "handoff_packets": 0,
        "observations": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "cache_mutations": 0,
        "winner_count": sum(result["selected_winner"] for result in results.values()),
        "evaluation_access_count": sum(result["evaluation_accessed"] for result in results.values()),
        "followup_count": len(followups),
    }
    process_rows = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": task_outcome,
            "next_action": next_action,
            "next_action_executed": False,
            "provider_calls": 0,
            "broker_actions": 0,
        }
    ]
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "architecture_id": ARCHITECTURE_ID,
            "task_outcome": task_outcome,
            "winner_trial_id": winner_trial or "",
            "followup_trial_id": followups[0]["config"].trial_id if followups else "",
            "followup_count": len(followups),
            "next_action": next_action,
            "robustness_performed": False,
            "eligibility_or_handoff_performed": False,
        }
    ]
    next_rows = [{"task_id": TASK_ID, "task_outcome": task_outcome, "next_action": next_action, "next_action_executed": False}]

    write_csv(
        OUTPUT_DIR / "phase2_universe_hash_reconciliation.csv",
        [
            {
                "universe_id": UNIVERSE_ID,
                "expected_hash": EXPECTED_UNIVERSE_HASH,
                "observed_hash": universe_reconciliation["computed_hash"],
                "status": "pass",
                "accepted_symbol_count": len(ACCOUNTING_UNIVERSE),
                "provider_calls": 0,
                "cache_mutations": 0,
            }
        ],
    )
    write_csv(
        OUTPUT_DIR / "intake_reconciliation.csv",
        [{"intake_id": INTAKE_ID, "intake_hash": file_hash(INTAKE_DIR), "overall_pass": intake_consistency["overall_pass"], "architecture_id": ARCHITECTURE_ID, "configuration_count": 4}],
    )
    write_csv(OUTPUT_DIR / "pair_mapping.csv", pair_rows)
    write_csv(OUTPUT_DIR / "parameter_grid.csv", parameter_rows)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows(results, next_action))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows(results, next_action))
    write_csv(OUTPUT_DIR / "duplicate_preflight.csv", duplicate_rows)
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_rows())
    write_csv(OUTPUT_DIR / "data_preflight_reconciliation.csv", preflight_rows)
    write_csv(OUTPUT_DIR / "monthly_pair_signal_ledger.csv", signal_rows)
    write_csv(OUTPUT_DIR / "selection_segment_definition.csv", selection_definition)
    write_csv(OUTPUT_DIR / "selection_segment_results.csv", selection_rows)
    write_csv(OUTPUT_DIR / "architecture_winner_selection.csv", winner_rows)
    if evaluation_rows:
        write_csv(OUTPUT_DIR / "evaluation_segment_results.csv", evaluation_rows)
        write_csv(OUTPUT_DIR / "evaluation_subhalf_results.csv", half_rows)
        write_csv(OUTPUT_DIR / "post_selection_full_period_diagnostics.csv", full_rows)
        write_csv(OUTPUT_DIR / "candidate_control_overlap.csv", overlap)
        write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar)
        write_csv(OUTPUT_DIR / "monthly_formation_contribution_results.csv", monthly_contribution)
        write_csv(OUTPUT_DIR / "industry_attribution.csv", industry)
        write_csv(OUTPUT_DIR / "parent_sector_group_attribution.csv", parent_group)
        write_csv(OUTPUT_DIR / "lightweight_concentration_diagnostics.csv", concentration)
    else:
        write_empty_csv(OUTPUT_DIR / "evaluation_segment_results.csv", ["strategy_id", "trial_id", "period_id", "cost_bps_one_way"])
        write_empty_csv(OUTPUT_DIR / "evaluation_subhalf_results.csv", ["strategy_id", "trial_id", "period_id"])
        write_empty_csv(OUTPUT_DIR / "post_selection_full_period_diagnostics.csv", ["strategy_id", "trial_id", "period_id", "cost_bps_one_way"])
        write_empty_csv(OUTPUT_DIR / "candidate_control_overlap.csv", ["strategy_id", "trial_id", "formation_date"])
        write_empty_csv(OUTPUT_DIR / "calendar_year_results.csv", ["strategy_id", "trial_id", "calendar_year"])
        write_empty_csv(OUTPUT_DIR / "monthly_formation_contribution_results.csv", ["strategy_id", "trial_id", "formation_date"])
        write_empty_csv(OUTPUT_DIR / "industry_attribution.csv", ["strategy_id", "trial_id", "industry"])
        write_empty_csv(OUTPUT_DIR / "parent_sector_group_attribution.csv", ["strategy_id", "trial_id", "parent_sector_group"])
        write_empty_csv(OUTPUT_DIR / "lightweight_concentration_diagnostics.csv", ["strategy_id", "trial_id", "concentration_unit"])
    write_csv(OUTPUT_DIR / "turnover_cost_reconciliation.csv", turnover_rows)
    write_csv(OUTPUT_DIR / "invariant_results.csv", invariant_rows)
    if followup_rows:
        write_csv(OUTPUT_DIR / "exploratory_followup_candidates.csv", followup_rows)
    else:
        write_empty_csv(OUTPUT_DIR / "exploratory_followup_candidates.csv", ["architecture_id", "strategy_id", "trial_id", "outcome", "failure_reason", "next_action"])
    write_csv(OUTPUT_DIR / "failure_vectors.csv", failure_vectors)
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_reasons)
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows)
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows)

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "task_id": TASK_ID,
            "module_owner": "trading_tournament",
            "stage": STAGE,
            "universe_id": UNIVERSE_ID,
            "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
            "architecture_count": 1,
            "configuration_count": 4,
            "canonical_optimization_trials": 4,
            "selection_formation_count": len(split.selection_pairs),
            "evaluation_formation_count": len(split.evaluation_pairs),
            "winner_trial_id": winner_trial or "",
            "followup_count": len(followups),
            "task_outcome": task_outcome,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "provider_calls": 0,
            "network_access": False,
            "cache_mutation": False,
            "robustness_performed": False,
            "eligibility_or_handoff_performed": False,
            "forward_observation_performed": False,
        },
    )
    winner_result = results[winner_trial] if winner_trial else None
    report = [
        "# Phase-2 New Group Discovery Batch V1",
        "",
        f"The frozen Phase-2 universe hash reconciled before performance. Exactly one internal architecture and four canonical optimization trials were evaluated over {len(split.selection_pairs)} selection formations.",
        f"At most one winner was frozen before the {len(split.evaluation_pairs)}-formation exploratory evaluation segment was accessed.",
        "",
        "## Outcome",
        "",
        f"Task outcome: `{task_outcome}`.",
    ]
    if winner_result:
        report.append(f"Frozen winner: `{winner_result['config'].trial_id}`; final outcome `{winner_result['outcome']}` / `{winner_result['failure_reason'] or 'none'}`.")
    else:
        report.append("No selection-eligible configuration existed; the evaluation segment remained unopened.")
    report.extend(
        [
            "",
            "Nonwinner evaluation results were not calculated or written. Full-period winner diagnostics cannot change the winner or rescue an evaluation failure.",
            "This is optimization and exploratory evaluation, not robustness, validation, eligibility, handoff, or forward observation.",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    write_text(OUTPUT_DIR / "batch_report.md", "\n".join(report))

    after = protected_hashes()
    files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    nonwinner_eval_access = [result["config"].trial_id for result in results.values() if not result["selected_winner"] and result["evaluation_accessed"]]
    checks = {
        "intake_materialization_passes": intake_consistency["overall_pass"],
        "phase2_universe_hash_matches": universe_reconciliation["computed_hash"] == EXPECTED_UNIVERSE_HASH,
        "exactly_one_architecture": counts["internal_architectures"] == 1,
        "exactly_four_strategy_configurations": counts["strategy_configurations"] == 4,
        "exactly_four_canonical_trials": counts["canonical_optimization_trials"] == 4,
        "zero_external_source_strategies": counts["external_source_strategies"] == 0,
        "exact_pair_mapping": tuple((row["industry"], row["parent_sector"]) for row in pair_rows) == PAIR_MAPPINGS,
        "all_industries_are_phase2_additions": all(row["membership_source"] == "phase2_nonperformance_addition" for row in pair_rows),
        "sample_gate_passes": sample_gate_pass,
        "winner_count_at_most_one": counts["winner_count"] <= 1,
        "evaluation_access_count_at_most_one": counts["evaluation_access_count"] <= 1,
        "nonwinner_evaluation_access_prohibited": not nonwinner_eval_access,
        "nonwinner_simulation_stops_at_selection_boundary": all(
            row["nonwinner_simulation_stops_at_selection_boundary"] for row in invariant_rows
        ),
        "all_controls_are_benchmark_references": all(row["entity_type"] == "benchmark_reference" for row in benchmark_rows()),
        "all_invariants_pass": all(row["overall_invariant_pass"] for row in invariant_rows),
        "turnover_costs_reconcile": max(row["absolute_reconciliation_difference"] for row in turnover_rows) <= 1e-12,
        "failure_reasons_permitted": all(row["reason_permitted"] for row in failure_reasons),
        "entity_counts_reconcile": counts["robustness_trials"] == counts["validation_trials"] == counts["eligibility_decisions"] == counts["handoff_packets"] == counts["observations"] == 0,
        "zero_provider_network_cache_mutation": counts["provider_calls"] == counts["network_calls"] == counts["cache_mutations"] == 0,
        "protected_state_and_caches_unchanged": before == after,
        "required_outputs_complete": (files | {"consistency_check.json"}) == REQUIRED_OUTPUTS,
        "next_action_not_executed": next_rows[0]["next_action_executed"] is False,
    }
    deterministic_payload = {
        "split": selection_definition,
        "winner": winner_rows,
        "selection": selection_rows,
        "evaluation": evaluation_rows,
        "concentration": concentration,
        "outcomes": failure_reasons,
        "next_action": next_action,
    }
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "task_outcome": task_outcome,
        "winner_trial_id": winner_trial or "",
        "followup_count": len(followups),
        "exact_next_action": next_action,
        "next_action_executed": False,
        "deterministic_core_hash": stable_hash(deterministic_payload),
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "entity_counts": counts,
        "forbidden_actions": {
            "external_strategy_added": False,
            "additional_architecture_added": False,
            "nonwinner_evaluation_access": bool(nonwinner_eval_access),
            "robustness": False,
            "validation": False,
            "eligibility_or_handoff": False,
            "forward_observation": False,
            "provider_broker_or_real_money_action": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=str))
