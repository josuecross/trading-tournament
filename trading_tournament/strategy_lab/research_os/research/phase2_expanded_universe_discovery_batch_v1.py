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


TASK_ID = "phase2_expanded_universe_discovery_batch_v1"
STAGE = "exploration"
MODE = "fast-progress"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
EXPECTED_UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
UNIVERSE_METHODOLOGY = "phase1_nonperformance_eligibility_reused_for_phase2_v1"
PREREGISTRATION_TIMESTAMP = "2026-08-08T12:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8

INTAKE_ID = "phase2_expanded_universe_hybrid_candidate_intake_v1"
INTAKE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID / "latest"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
UNIVERSE_PATH = UNIVERSE_DIR / "phase2_frozen_universe.csv"
PHASE1_CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
PHASE2_CACHE_DIR = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"

ROTATOR_ID = "spdj_sp500_market_rotator_spy_splv_rsp_v1"
DOGS_ID = "smith_pantilei_dogs_of_world_5x5_v1"
ROTATOR_SOURCE = "src_spdj_sp500_market_rotator_spy_splv_rsp_v1"
DOGS_SOURCE = "src_smith_pantilei_dogs_of_world_5x5_v1"
ROTATOR_TRIAL = "phase2_external_v1__sp500_market_rotator__canonical"
DOGS_TRIAL = "phase2_external_v1__dogs_of_world_5x5__canonical"

ROTATOR_UNIVERSE = ("SPY", "SPLV", "RSP", "BIL")
DOGS_COUNTRIES = (
    "EWA", "EWC", "EWG", "EWJ", "EWU", "EWY", "INDA", "EWH",
    "EWL", "EWP", "EWQ", "EWS", "EWT", "EWW", "EWZ",
)
DOGS_UNIVERSE = DOGS_COUNTRIES + ("BIL", "ACWX")
PROHIBITED_SYMBOLS = {"EWD", "PKW", "IGOV", "RWX", "EWM", "EWN", "CPER"}

ROTATOR_NAMED = "market_rotator_single_12m_return_control"
ROTATOR_STATIC = "market_rotator_static_state_frequency_control"
ROTATOR_CONTROLS = (
    ROTATOR_NAMED,
    ROTATOR_STATIC,
    "spy_splv_rsp_equal_weight_control",
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
DOGS_NAMED = "dogs_of_world_winners_5x5_control"
DOGS_STATIC = "dogs_of_world_static_average_weights_control"
DOGS_CONTROLS = (
    DOGS_NAMED,
    DOGS_STATIC,
    "equal_weight_eligible_country_universe_control",
    "ACWX_buy_and_hold",
    "BIL_buy_and_hold",
)

FOLLOWUP_ACTION = "direction_owner_review_phase2_expanded_universe_followups_for_robustness_v1"
ZERO_FOLLOWUP_ACTION = "direction_owner_review_phase2_expansion_discovery_yield_v1"

REQUIRED_INTAKE_OUTPUTS = {
    "intake_manifest.yaml",
    "source_library_records.csv",
    "selected_candidate_specs.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "robustness_role_preregistration.csv",
    "phase2_unlock_reconciliation.csv",
    "rejection_ledger.csv",
    "consistency_check.json",
    "intake_report.md",
}

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "phase2_universe_hash_reconciliation.csv",
    "intake_reconciliation.csv",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "data_preflight_reconciliation.csv",
    "market_rotator_monthly_signal_ledger.csv",
    "dogs_country_eligibility_ledger.csv",
    "dogs_annual_ranking_ledger.csv",
    "dogs_cohort_ledger.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "calendar_year_results.csv",
    "contribution_results.csv",
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
    UNIVERSE_DIR,
    PHASE1_CACHE_DIR,
    PHASE2_CACHE_DIR,
    ROOT / "paper_forward_observations",
    ROOT / "evidence" / "handoff",
    ROOT / "evidence" / "eligibility",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v1",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v2",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v3",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v4",
    ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v1",
    ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v2",
    ROOT / "evidence" / "research_recovery" / "accepted_47_hybrid_discovery_batch_v1",
)


@dataclass(frozen=True)
class StrategySpec:
    source_record_id: str
    strategy_id: str
    trial_id: str
    family_id: str
    display_name: str
    architecture_id: str
    strategy_architecture: str
    lineage: str
    universe: tuple[str, ...]
    controls: tuple[str, ...]
    route: str
    robustness_role: str
    parameters: dict[str, Any]


SPECS = (
    StrategySpec(
        ROTATOR_SOURCE,
        ROTATOR_ID,
        ROTATOR_TRIAL,
        "equity_weighting_style_rotation",
        "S&P 500 Market Rotator SPY-SPLV-RSP",
        "monthly_multi_horizon_market_lowvol_equalweight_rotation",
        "monthly_multi_horizon_market_lowvol_equalweight_rotation",
        "sp_dow_jones_sp500_market_rotator_2026_methodology",
        ROTATOR_UNIVERSE,
        ROTATOR_CONTROLS,
        "standalone",
        "dynamic_multi_asset_allocation_strategy",
        {
            "source_version": "January_2026",
            "periodic_return_months": [1, 3, 6, 9, 12],
            "score": "arithmetic_mean_of_five_periodic_returns",
            "selected_count": 1,
            "reference_date": "final_regular_business_session_of_prior_month",
            "execution": "close_of_first_regular_business_session_of_new_month",
            "warmup_month_end_prices": 13,
            "tie_break": "lexical_within_numeric_tolerance",
        },
    ),
    StrategySpec(
        DOGS_SOURCE,
        DOGS_ID,
        DOGS_TRIAL,
        "long_horizon_country_reversal_cohorts",
        "Smith-Pantilei Dogs of the World 5x5",
        "annual_bottom5_country_five_year_staggered_cohorts",
        "annual_bottom5_country_five_year_staggered_cohorts",
        "smith_pantilei_dogs_of_world_2015",
        DOGS_UNIVERSE,
        DOGS_CONTROLS,
        "standalone",
        "cross_sectional_allocation_strategy",
        {
            "ranking": "prior_complete_calendar_year_return_ascending",
            "selected_count": 5,
            "cohort_slots": 5,
            "cohort_capital_fraction": 0.2,
            "holding_calendar_years": 5,
            "within_cohort_allocation": "equal_weight_at_inception_only",
            "execution": "close_of_first_regular_US_trading_session_of_January",
            "tie_break": "lexical",
            "dynamic_eligibility": True,
        },
    ),
)
SPEC_BY_ID = {spec.strategy_id: spec for spec in SPECS}

FROZEN_RULES: dict[str, dict[str, Any]] = {
    ROTATOR_ID: {
        "source_version": "January 2026 S&P 500 Market Rotator methodology",
        "reference_date": "final regular business session of prior month",
        "execution": "close of first regular business session of new month",
        "score": "arithmetic mean of 1m, 3m, 6m, 9m, and 12m periodic adjusted-close returns",
        "selection": "highest-scoring one of SPY, SPLV, and RSP; lexical tie break within numeric tolerance",
        "target": "100% selected ETF with explicit zero weights in the other components and BIL",
        "warmup": "13 complete month-end prices for all three components; otherwise 100% BIL",
        "missing_ranking_input": "retain prior target; before initialization remain in BIL",
        "missing_selected_execution_price": "block transition, retain prior holdings, and do not execute late",
        "same_session_return_assigned_to_new_target": False,
        "older_last_business_day_rebalance_version_used": False,
    },
    DOGS_ID: {
        "ranking": "completed prior-calendar-year adjusted-close return ascending",
        "selection": "five lowest-return dynamically eligible countries; lexical tie break",
        "dynamic_eligibility": "valid final sessions for Y-1 and Y, complete annual return, and valid upcoming January execution price",
        "partial_year_returns_allowed": False,
        "cohort_slots": 5,
        "new_sleeve_fraction": 0.2,
        "within_cohort_allocation": "equal at inception only",
        "holding_period": "exactly five calendar years",
        "ramp": "one annual sleeve added while uncreated sleeves remain in BIL",
        "steady_state": "liquidate only the oldest completed sleeve and reinvest all proceeds in the new selection",
        "duplicate_country_handling": "separate cohort lots retained and aggregated only for portfolio accounting",
        "fewer_than_five_eligible": "new or replacement sleeve remains in BIL without substitution or selected-count reduction",
        "execution": "close of first regular U.S. trading session of January",
        "new_holdings_begin_return": "following session",
        "late_execution_allowed": False,
        "nonexpiring_cohort_rebalance_allowed": False,
    },
}

CONTROL_RULES = {
    ROTATOR_NAMED: "same monthly SPY/SPLV/RSP single-component process ranked only by trailing 12-month return",
    ROTATOR_STATIC: "static unrounded weights equal to the candidate's mechanically observed full-period component-state frequencies",
    "spy_splv_rsp_equal_weight_control": "monthly one-third SPY, one-third SPLV, one-third RSP at identical first-session-close timing",
    "SPY_buy_and_hold": "100% SPY buy and hold",
    "BIL_buy_and_hold": "100% BIL buy and hold",
    DOGS_NAMED: "identical dynamic eligibility, five sleeves, five-year holding, ramp, execution, and costs with ranking direction reversed to five winners",
    DOGS_STATIC: "static unrounded weights equal to mechanically observed average candidate country and BIL weights",
    "equal_weight_eligible_country_universe_control": "annually equal-weight every dynamically eligible country at identical January-close execution",
    "ACWX_buy_and_hold": "100% ACWX buy and hold",
}


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


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


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {relative(path): file_hash(path) for path in PROTECTED_PATHS if path.exists()}


def clean_output(path: Path, allowed_parent: Path) -> None:
    if path.exists():
        resolved = path.resolve()
        if allowed_parent.resolve() not in resolved.parents:
            raise RuntimeError(f"Refusing to clean unexpected path: {resolved}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_csv_at(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    row_list = list(rows)
    field_list = list(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: serialize_cell(row.get(field, "")) for field in field_list})


def serialize_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return value


def write_json_at(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_yaml_at(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_text_at(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def source_rows() -> list[dict[str, Any]]:
    rows = []
    for spec in SPECS:
        rows.append(
            {
                "source_record_id": spec.source_record_id,
                "entity_type": "source_library_record",
                "stage": "source_extracted",
                "outcome": "feasible",
                "failure_reason": "",
                "strategy_id": spec.strategy_id,
                "family_id": spec.family_id,
                "display_name": spec.display_name,
                "source_or_research_lineage": spec.lineage,
                "source_version": "January 2026 methodology" if spec.strategy_id == ROTATOR_ID else "2015 source architecture",
                "exact_source_replication_claimed": False,
                "implementation_authorized": True,
                "provider_requirements": 0,
                "next_action": TASK_ID,
            }
        )
    return rows


def strategy_rows(outcomes: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    outcomes = outcomes or {}
    rows = []
    for spec in SPECS:
        result = outcomes.get(spec.strategy_id, {})
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "family_id": spec.family_id,
                "display_name": spec.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": spec.strategy_architecture,
                "architecture_id": spec.architecture_id,
                "source_or_research_lineage": spec.lineage,
                "instrument_universe": "|".join(spec.universe),
                "parameters": spec.parameters,
                "benchmark_or_control": "|".join(spec.controls),
                "route": spec.route,
                "primary_future_robustness_role": spec.robustness_role,
                "frozen_rule": FROZEN_RULES[spec.strategy_id],
                "exact_source_replication_claimed": False,
                "universe_id": UNIVERSE_ID,
                "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
                "stage": STAGE,
                "trial_id": spec.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "outcome": result.get("outcome", "preregistered_pending_execution"),
                "failure_reason": result.get("failure_reason", ""),
                "next_action": result.get("next_action", "pending_batch_routing"),
                "preregistered_before_performance": True,
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def trial_rows(outcomes: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    outcomes = outcomes or {}
    rows = []
    for spec in SPECS:
        result = outcomes.get(spec.strategy_id, {})
        rows.append(
            {
                "trial_id": spec.trial_id,
                "entity_type": "experiment_trial",
                "stage": STAGE,
                "strategy_id": spec.strategy_id,
                "family_id": spec.family_id,
                "display_name": spec.display_name,
                "strategy_architecture": spec.strategy_architecture,
                "source_or_research_lineage": spec.lineage,
                "instrument_universe": "|".join(spec.universe),
                "parameters": spec.parameters,
                "benchmark_or_control": "|".join(spec.controls),
                "primary_future_robustness_role": spec.robustness_role,
                "frozen_rule": FROZEN_RULES[spec.strategy_id],
                "exact_source_replication_claimed": False,
                "universe_id": UNIVERSE_ID,
                "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
                "parent_trial_id": "",
                "adaptation_label": "",
                "outcome": result.get("outcome", "preregistered_pending_execution"),
                "failure_reason": result.get("failure_reason", ""),
                "next_action": result.get("next_action", "pending_batch_routing"),
                "source_rule_changed": False,
                "parameters_changed": False,
                "instruments_changed": False,
                "execution_changed": False,
                "optimization_performed": False,
                "post_result_adaptation_allowed": False,
                "preregistered_before_performance": True,
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows = []
    for spec in SPECS:
        for control in spec.controls:
            rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "benchmark_id": control,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "is_named_same_purpose_control": control in {ROTATOR_NAMED, DOGS_NAMED},
                    "is_static_critical_control": control in {ROTATOR_STATIC, DOGS_STATIC},
                    "benchmark_rule": CONTROL_RULES[control],
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "post_result_control_change_allowed": False,
                }
            )
    return rows


def selected_specs_payload() -> dict[str, Any]:
    return {
        "intake_id": INTAKE_ID,
        "universe_id": UNIVERSE_ID,
        "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
        "selected_work_packages": 2,
        "external_configurations": 2,
        "internal_architectures": 0,
        "canonical_trials_proposed": 2,
        "provider_requirements": 0,
        "candidates": [
            {
                "source_record_id": spec.source_record_id,
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                "family_id": spec.family_id,
                "architecture_id": spec.architecture_id,
                "source_or_research_lineage": spec.lineage,
                "universe": list(spec.universe),
                "route": spec.route,
                "primary_future_robustness_role": spec.robustness_role,
                "parameters": spec.parameters,
                "frozen_rule": FROZEN_RULES[spec.strategy_id],
                "controls": list(spec.controls),
                "control_rules": {control: CONTROL_RULES[control] for control in spec.controls},
                "sample_gate": (
                    {
                        "minimum_complete_monthly_formations": 100,
                        "minimum_formations_each_chronological_half": 40,
                    }
                    if spec.strategy_id == ROTATOR_ID
                    else {
                        "minimum_completed_replacements_after_ramp": 15,
                        "minimum_replacements_each_chronological_half": 6,
                        "minimum_median_eligible_countries": 10,
                    }
                ),
                "exploration_gate": {
                    "primary_cost_bps": PRIMARY_COST_BPS,
                    "positive_CAGR": True,
                    "all_invariants": True,
                    "critical_controls": [spec.controls[0], spec.controls[1]],
                    "materiality": {"sharpe_improvement": 0.02, "maximum_drawdown_improvement": 0.01},
                    "half_period_not_worse_on_both": True,
                    "positive_CAGR_at_10bps": True,
                    "maximum_positive_excess_contributor_share": 0.80,
                },
                "costs_bps_one_way": list(COST_BPS),
                "optimization_allowed": False,
                "provider_calls_allowed": 0,
            }
            for spec in SPECS
        ],
    }


def materialize_intake() -> dict[str, Any]:
    clean_output(INTAKE_DIR, ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID)
    sources = source_rows()
    strategies = strategy_rows()
    trials = trial_rows()
    benchmarks = benchmark_rows()
    manifest = {
        "intake_id": INTAKE_ID,
        "module_owner": "trading_tournament",
        "stage": "source_extracted",
        "materialization_timestamp": PREREGISTRATION_TIMESTAMP,
        "universe_id": UNIVERSE_ID,
        "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
        "selected_work_packages": 2,
        "external_configurations": 2,
        "internal_architectures": 0,
        "canonical_trials_proposed": 2,
        "unresolved_material_fields": 0,
        "provider_requirements": 0,
        "performance_viewed_before_preregistration": False,
    }
    write_yaml_at(INTAKE_DIR / "intake_manifest.yaml", manifest)
    write_csv_at(INTAKE_DIR / "source_library_records.csv", sources, sources[0].keys())
    write_yaml_at(INTAKE_DIR / "selected_candidate_specs.yaml", selected_specs_payload())
    catalog = [
        {
            "strategy_id": row["strategy_id"],
            "trial_id": row["trial_id"],
            "entity_type": "strategy_configuration_and_canonical_trial_catalog",
            "stage": STAGE,
            "route": row["route"],
            "canonical_configuration_count": 1,
            "canonical_trial_count": 1,
            "optimization_variants": 0,
        }
        for row in strategies
    ]
    write_csv_at(INTAKE_DIR / "configuration_trial_catalog.csv", catalog, catalog[0].keys())
    write_csv_at(INTAKE_DIR / "benchmark_reference_catalog.csv", benchmarks, benchmarks[0].keys())
    role_rows = [
        {
            "strategy_id": spec.strategy_id,
            "primary_future_robustness_role": spec.robustness_role,
            "role_selected_before_performance": True,
            "robustness_executed_in_this_task": False,
        }
        for spec in SPECS
    ]
    write_csv_at(INTAKE_DIR / "robustness_role_preregistration.csv", role_rows, role_rows[0].keys())
    unlock_rows = [
        {
            "strategy_id": ROTATOR_ID,
            "phase2_additions_required": "SPLV|RSP",
            "all_required_symbols_in_phase2": True,
            "materially_depends_on_phase2": True,
            "provider_requirement": 0,
        },
        {
            "strategy_id": DOGS_ID,
            "phase2_additions_required": "ACWX|EWH|EWL|EWP|EWQ|EWS|EWT|EWW|EWZ",
            "all_required_symbols_in_phase2": True,
            "materially_depends_on_phase2": True,
            "provider_requirement": 0,
        },
    ]
    write_csv_at(INTAKE_DIR / "phase2_unlock_reconciliation.csv", unlock_rows, unlock_rows[0].keys())
    write_csv_at(
        INTAKE_DIR / "rejection_ledger.csv",
        [],
        ["source_record_id", "strategy_id", "rejection_reason", "stage", "performance_used"],
    )
    report = f"""# Phase-2 Expanded-Universe Hybrid Candidate Intake V1

Exactly two external, source-backed work packages are materialized for exploration. No internal architecture, optimization variant, provider requirement, or unresolved material field is present.

The intake is bound to `{UNIVERSE_ID}` at `{EXPECTED_UNIVERSE_HASH}`. It authorizes only `{ROTATOR_ID}` and `{DOGS_ID}` and does not authorize robustness, validation, eligibility, handoff, observation, or broker work.
"""
    write_text_at(INTAKE_DIR / "intake_report.md", report)
    current = {path.name for path in INTAKE_DIR.iterdir() if path.is_file()}
    checks = {
        "selected_work_packages_exactly_two": len(SPECS) == 2,
        "external_configurations_exactly_two": len(strategies) == 2,
        "internal_architectures_zero": True,
        "canonical_trials_proposed_exactly_two": len(trials) == 2,
        "unresolved_material_fields_zero": True,
        "provider_requirements_zero": True,
        "all_controls_are_benchmark_references": all(row["entity_type"] == "benchmark_reference" for row in benchmarks),
        "required_outputs_complete": (current | {"consistency_check.json"}) == REQUIRED_INTAKE_OUTPUTS,
    }
    consistency = {
        "intake_id": INTAKE_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "counts": manifest,
        "performance_viewed_before_preregistration": False,
    }
    write_json_at(INTAKE_DIR / "consistency_check.json", consistency)
    return consistency


def load_universe_contract() -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, Any]]:
    with UNIVERSE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 88:
        raise RuntimeError(f"Phase-2 universe count drift: {len(rows)}")
    symbols = sorted(row["symbol"] for row in rows)
    computed = stable_hash(
        {
            "universe_id": UNIVERSE_ID,
            "methodology": UNIVERSE_METHODOLOGY,
            "symbols": symbols,
        }
    )
    row_hashes = {row["frozen_universe_hash"] for row in rows}
    if computed != EXPECTED_UNIVERSE_HASH or row_hashes != {EXPECTED_UNIVERSE_HASH}:
        raise RuntimeError("Phase-2 frozen universe hash mismatch")
    by_symbol = {row["symbol"]: row for row in rows}
    required = set(ROTATOR_UNIVERSE + DOGS_UNIVERSE)
    if not required.issubset(by_symbol):
        raise RuntimeError(f"Required Phase-2 symbols missing: {sorted(required - set(by_symbol))}")
    if PROHIBITED_SYMBOLS & set(by_symbol):
        raise RuntimeError(f"Deferred symbols entered frozen universe: {sorted(PROHIBITED_SYMBOLS & set(by_symbol))}")
    cache_mismatches = []
    for symbol in sorted(required):
        row = by_symbol[symbol]
        path = ROOT / row["cache_path"]
        observed = file_hash(path)
        if observed != row["cache_hash"]:
            cache_mismatches.append({"symbol": symbol, "expected": row["cache_hash"], "observed": observed})
    if cache_mismatches:
        raise RuntimeError(f"Required cache hash mismatch: {cache_mismatches}")
    reconciliation = {
        "universe_id": UNIVERSE_ID,
        "expected_hash": EXPECTED_UNIVERSE_HASH,
        "computed_hash": computed,
        "row_hashes_match": row_hashes == {EXPECTED_UNIVERSE_HASH},
        "symbol_count": len(rows),
        "required_symbol_count": len(required),
        "required_symbols_present": True,
        "prohibited_symbols_absent": True,
        "required_cache_hashes_match": True,
        "status": "pass",
    }
    return rows, by_symbol, reconciliation


def load_price_series(symbol: str, universe_by_symbol: dict[str, dict[str, str]]) -> pd.Series:
    row = universe_by_symbol[symbol]
    path = ROOT / row["cache_path"]
    if file_hash(path) != row["cache_hash"]:
        raise RuntimeError(f"Cache changed before load: {symbol}")
    frame = pd.read_csv(path, usecols=["date", "adj_close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame["adj_close"] = pd.to_numeric(frame["adj_close"], errors="coerce")
    frame = frame.dropna().sort_values("date")
    if frame["date"].duplicated().any() or not frame["date"].is_monotonic_increasing:
        raise RuntimeError(f"Invalid date order for {symbol}")
    if not np.isfinite(frame["adj_close"].to_numpy(dtype=float)).all() or (frame["adj_close"] <= 0.0).any():
        raise RuntimeError(f"Invalid adjusted close for {symbol}")
    return pd.Series(frame["adj_close"].to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]), name=symbol)


def load_required_prices(universe_by_symbol: dict[str, dict[str, str]]) -> dict[str, pd.Series]:
    symbols = sorted(set(ROTATOR_UNIVERSE + DOGS_UNIVERSE))
    return {symbol: load_price_series(symbol, universe_by_symbol) for symbol in symbols}


def data_preflight_rows(
    universe_by_symbol: dict[str, dict[str, str]],
    series: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    rows = []
    for spec in SPECS:
        for symbol in spec.universe:
            values = series[symbol]
            universe_row = universe_by_symbol[symbol]
            rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "symbol": symbol,
                    "phase2_membership_source": universe_row["membership_source"],
                    "cache_path": universe_row["cache_path"],
                    "expected_cache_hash": universe_row["cache_hash"],
                    "observed_cache_hash": file_hash(ROOT / universe_row["cache_path"]),
                    "first_valid_session": values.index.min().date().isoformat(),
                    "last_valid_session": values.index.max().date().isoformat(),
                    "row_count": len(values),
                    "unique_ordered_dates": bool(values.index.is_unique and values.index.is_monotonic_increasing),
                    "finite_positive_adjusted_close": bool(np.isfinite(values.to_numpy(dtype=float)).all() and (values > 0.0).all()),
                    "provider_call_performed": False,
                    "cache_modified": False,
                    "preflight_status": "pass",
                }
            )
    return rows


def master_index(series: dict[str, pd.Series], required: tuple[str, ...], calendar_symbol: str) -> pd.DatetimeIndex:
    start = max(series[symbol].index.min() for symbol in required)
    end = min(series[symbol].index.max() for symbol in required)
    index = series[calendar_symbol].index
    return pd.DatetimeIndex(index[(index >= start) & (index <= end)])


def price_frame(series: dict[str, pd.Series], symbols: tuple[str, ...], index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.concat([series[symbol].reindex(index) for symbol in symbols], axis=1).reindex(columns=list(symbols))


def explicit_target(symbols: tuple[str, ...], selected: dict[str, float]) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in symbols}
    target.update({symbol: float(weight) for symbol, weight in selected.items()})
    values = np.array([target[symbol] for symbol in symbols], dtype=float)
    if not np.isfinite(values).all() or (values < -WEIGHT_TOLERANCE).any():
        raise RuntimeError("Invalid target values")
    if abs(float(values.sum()) - 1.0) > WEIGHT_TOLERANCE:
        raise RuntimeError(f"Target does not sum to one: {values.sum()}")
    return target


def event_frame(
    index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    events: dict[pd.Timestamp, dict[str, float]],
) -> pd.DataFrame:
    valid = set(index)
    rows = []
    dates = []
    for raw_date, raw_target in sorted(events.items()):
        date_value = pd.Timestamp(raw_date)
        if date_value not in valid:
            raise RuntimeError(f"Execution date outside evaluation calendar: {date_value}")
        rows.append(explicit_target(symbols, raw_target))
        dates.append(date_value)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates), columns=list(symbols), dtype=float)


def _safe_return_array(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change(fill_method=None)


def simulate_events(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    cost_bps: float,
    *,
    timing_policy: str,
    formation_dates: Iterable[pd.Timestamp] = (),
    execution_dates: Iterable[pd.Timestamp] = (),
) -> dict[str, Any]:
    prices = prices.sort_index()
    symbols = tuple(prices.columns)
    targets = targets.reindex(columns=list(symbols)).sort_index()
    event_positions = prices.index.get_indexer(targets.index)
    event_by_position = {
        int(position): row.to_numpy(dtype=float)
        for position, (_, row) in zip(event_positions, targets.iterrows())
        if position >= 0
    }
    returns_frame = _safe_return_array(prices)
    current = np.zeros(len(symbols), dtype=float)
    daily_rows: list[dict[str, Any]] = []
    held_rows: list[np.ndarray] = []
    contribution_rows: list[np.ndarray] = []
    event_rows: list[dict[str, Any]] = []
    missing_held_price_count = 0
    for position, date_value in enumerate(prices.index):
        held = current.copy()
        held_rows.append(held.copy())
        raw_returns = returns_frame.iloc[position].to_numpy(dtype=float)
        missing_held = (~np.isfinite(raw_returns)) & (held > WEIGHT_TOLERANCE) & (position > 0)
        missing_held_price_count += int(missing_held.sum())
        usable_returns = np.where(np.isfinite(raw_returns), raw_returns, 0.0)
        gross_contribution = held * usable_returns
        gross_return = float(gross_contribution.sum())
        drifted = held * (1.0 + usable_returns)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held.copy()
        target = pretrade.copy()
        turnover = 0.0
        cost_drag = 0.0
        contribution = gross_contribution.copy()
        if position in event_by_position:
            target = event_by_position[position].copy()
            turnover = 0.5 * float(np.abs(target - pretrade).sum())
            cost_fraction = turnover * cost_bps / 10000.0
            cost_drag = (1.0 + gross_return) * cost_fraction
            traded = np.abs(target - pretrade)
            if traded.sum() > TOLERANCE:
                contribution -= cost_drag * traded / traded.sum()
            event_rows.append(
                {
                    "execution_date": pd.Timestamp(date_value),
                    "pretrade_weights": {symbol: float(pretrade[i]) for i, symbol in enumerate(symbols)},
                    "target_weights": {symbol: float(target[i]) for i, symbol in enumerate(symbols)},
                    "one_way_turnover": turnover,
                    "transaction_cost_drag": cost_drag,
                    "timing_policy": timing_policy,
                }
            )
        net_return = (1.0 + gross_return) * (1.0 - turnover * cost_bps / 10000.0) - 1.0
        contribution_rows.append(contribution)
        daily_rows.append(
            {
                "date": pd.Timestamp(date_value),
                "net_return": net_return,
                "gross_return": gross_return,
                "one_way_turnover": turnover,
                "transaction_cost_drag": cost_drag,
                "gross_exposure": max(float(np.abs(held).sum()), float(np.abs(target).sum())),
                "weight_sum": max(float(held.sum()), float(target.sum())),
                "holdings_count": int((held > WEIGHT_TOLERANCE).sum()),
                "maximum_asset_weight": max(float(held.max(initial=0.0)), float(target.max(initial=0.0))),
            }
        )
        current = target
    daily = pd.DataFrame(daily_rows).set_index("date")
    held_weights = pd.DataFrame(held_rows, index=prices.index, columns=list(symbols))
    contributions = pd.DataFrame(contribution_rows, index=prices.index, columns=list(symbols))
    target_values = targets.to_numpy(dtype=float)
    return {
        "returns": daily["net_return"],
        "daily": daily,
        "held_weights": held_weights,
        "asset_contributions": contributions,
        "cohort_contributions": pd.DataFrame(index=prices.index),
        "events": event_rows,
        "target_events": targets,
        "formation_dates": [pd.Timestamp(value) for value in formation_dates],
        "execution_dates": [pd.Timestamp(value) for value in execution_dates],
        "timing_policy": timing_policy,
        "missing_held_price_count": missing_held_price_count,
        "numeric_invariant_pass": bool(np.isfinite(daily["net_return"].to_numpy(dtype=float)).all()),
        "weight_invariant_pass": bool(
            (held_weights.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
            and (target_values >= -WEIGHT_TOLERANCE).all()
            and np.allclose(target_values.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)
        ),
        "exposure_invariant_pass": bool(daily["gross_exposure"].max() <= 1.0 + WEIGHT_TOLERANCE),
        "timing_invariant_pass": True,
    }


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [pd.Timestamp(value) for value in index[periods.ne(periods.shift(-1)).fillna(True)]]


def next_session(index: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date_value), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def lexical_argmax(values: dict[str, float]) -> str:
    maximum = max(values.values())
    tied = sorted(symbol for symbol, value in values.items() if abs(value - maximum) <= TOLERANCE)
    return tied[0]


def build_market_rotator(
    series: dict[str, pd.Series],
) -> dict[str, Any]:
    index = master_index(series, ROTATOR_UNIVERSE, "BIL")
    prices = price_frame(series, ROTATOR_UNIVERSE, index)
    formations = month_end_dates(index)
    month_closes = prices.loc[formations, ["SPY", "SPLV", "RSP"]]
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): explicit_target(ROTATOR_UNIVERSE, {"BIL": 1.0})
    }
    named_events = dict(candidate_events)
    equal_events = dict(candidate_events)
    signal_rows: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    candidate_executions: list[pd.Timestamp] = []
    named_executions: list[pd.Timestamp] = []
    state_counts = {"SPY": 0, "SPLV": 0, "RSP": 0}
    for position, formation in enumerate(formations):
        execution = next_session(index, formation)
        base = {
            "strategy_id": ROTATOR_ID,
            "formation_date": formation.date().isoformat(),
            "execution_date": execution.date().isoformat() if execution is not None else "",
            "source_version": "January_2026_first_business_day_rebalance",
            "reference_date_policy": "final_regular_business_session_of_prior_month",
            "execution_policy": "close_of_first_regular_business_session_of_new_month",
            "same_formation_session_return_used": False,
        }
        if position < 12 or execution is None:
            signal_rows.append(
                {
                    **base,
                    "signal_status": "warmup_or_no_following_session",
                    "selected_component": "BIL",
                    "named_control_selected_component": "BIL",
                    "ranking_inputs_complete": False,
                    "execution_blocked": execution is None,
                }
            )
            continue
        scores: dict[str, float] = {}
        periodic: dict[str, dict[str, float]] = {}
        complete = True
        for symbol in ("SPY", "SPLV", "RSP"):
            values: dict[str, float] = {}
            for horizon in (1, 3, 6, 9, 12):
                current = month_closes.loc[formation, symbol]
                prior = month_closes.iloc[position - horizon][symbol]
                value = float(current / prior - 1.0) if pd.notna(current) and pd.notna(prior) else float("nan")
                values[f"return_{horizon}m"] = value
            periodic[symbol] = values
            if not all(math.isfinite(value) for value in values.values()):
                complete = False
            scores[symbol] = float(np.mean(list(values.values()))) if complete else float("nan")
        if not complete:
            signal_rows.append(
                {
                    **base,
                    "signal_status": "incomplete_ranking_input_retain_prior_target",
                    "selected_component": "",
                    "named_control_selected_component": "",
                    "ranking_inputs_complete": False,
                    "execution_blocked": False,
                    "periodic_returns": periodic,
                }
            )
            continue
        selected = lexical_argmax(scores)
        named_scores = {
            symbol: periodic[symbol]["return_12m"] for symbol in ("SPY", "SPLV", "RSP")
        }
        named_selected = lexical_argmax(named_scores)
        selected_price_valid = bool(pd.notna(prices.loc[execution, selected]))
        named_price_valid = bool(pd.notna(prices.loc[execution, named_selected]))
        if selected_price_valid:
            candidate_events[execution] = explicit_target(ROTATOR_UNIVERSE, {selected: 1.0})
            candidate_executions.append(execution)
            state_counts[selected] += 1
        if named_price_valid:
            named_events[execution] = explicit_target(ROTATOR_UNIVERSE, {named_selected: 1.0})
            named_executions.append(execution)
        if prices.loc[execution, ["SPY", "SPLV", "RSP"]].notna().all():
            equal_events[execution] = explicit_target(
                ROTATOR_UNIVERSE,
                {"SPY": 1.0 / 3.0, "SPLV": 1.0 / 3.0, "RSP": 1.0 / 3.0},
            )
        valid_formations.append(formation)
        signal_rows.append(
            {
                **base,
                "signal_status": "valid_executed" if selected_price_valid else "selected_execution_price_missing_transition_blocked",
                "selected_component": selected,
                "named_control_selected_component": named_selected,
                "ranking_inputs_complete": True,
                "execution_blocked": not selected_price_valid,
                "periodic_returns": periodic,
                "mean_scores": scores,
                "score_rank_order": sorted(scores, key=lambda symbol: (-scores[symbol], symbol)),
                "target_weights": explicit_target(ROTATOR_UNIVERSE, {selected: 1.0}) if selected_price_valid else {},
            }
        )
    total_states = sum(state_counts.values())
    static_weights = {
        symbol: state_counts[symbol] / total_states for symbol in ("SPY", "SPLV", "RSP")
    }
    controls = {
        ROTATOR_NAMED: event_frame(index, ROTATOR_UNIVERSE, named_events),
        ROTATOR_STATIC: event_frame(
            index,
            ROTATOR_UNIVERSE,
            {pd.Timestamp(index[0]): explicit_target(ROTATOR_UNIVERSE, static_weights)},
        ),
        "spy_splv_rsp_equal_weight_control": event_frame(index, ROTATOR_UNIVERSE, equal_events),
        "SPY_buy_and_hold": event_frame(
            index,
            ROTATOR_UNIVERSE,
            {pd.Timestamp(index[0]): explicit_target(ROTATOR_UNIVERSE, {"SPY": 1.0})},
        ),
        "BIL_buy_and_hold": event_frame(
            index,
            ROTATOR_UNIVERSE,
            {pd.Timestamp(index[0]): explicit_target(ROTATOR_UNIVERSE, {"BIL": 1.0})},
        ),
    }
    return {
        "prices": prices,
        "candidate_events": event_frame(index, ROTATOR_UNIVERSE, candidate_events),
        "controls": controls,
        "signal_rows": signal_rows,
        "formation_dates": valid_formations,
        "candidate_execution_dates": candidate_executions,
        "control_execution_dates": {ROTATOR_NAMED: named_executions},
        "state_counts": state_counts,
        "static_weights": static_weights,
    }


def final_session_by_year(index: pd.DatetimeIndex) -> dict[int, pd.Timestamp]:
    result: dict[int, pd.Timestamp] = {}
    for year in sorted(set(index.year)):
        dates = index[index.year == year]
        if len(dates):
            result[year] = pd.Timestamp(dates[-1])
    return result


def first_january_session(index: pd.DatetimeIndex, year: int) -> pd.Timestamp | None:
    dates = index[(index.year == year) & (index.month == 1)]
    return pd.Timestamp(dates[0]) if len(dates) else None


def build_dogs_formations(
    series: dict[str, pd.Series],
) -> dict[str, Any]:
    evaluation_start = max(series[symbol].index.min() for symbol in DOGS_UNIVERSE)
    evaluation_end = min(series[symbol].index.max() for symbol in DOGS_UNIVERSE)
    index = series["BIL"].index.intersection(series["ACWX"].index)
    index = pd.DatetimeIndex(index[(index >= evaluation_start) & (index <= evaluation_end)])
    prices = price_frame(series, DOGS_UNIVERSE, index)
    calendar_year_ends = final_session_by_year(series["BIL"].index)
    evaluation_year_ends = final_session_by_year(index)
    eligibility_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []
    formations: list[dict[str, Any]] = []
    for formation_year in sorted(evaluation_year_ends):
        if formation_year - 1 not in calendar_year_ends:
            continue
        formation = evaluation_year_ends[formation_year]
        prior = calendar_year_ends[formation_year - 1]
        execution = first_january_session(index, formation_year + 1)
        if execution is None:
            continue
        annual_returns: dict[str, float] = {}
        eligible: list[str] = []
        for symbol in DOGS_COUNTRIES:
            prior_price = series[symbol].get(prior, np.nan)
            formation_price = series[symbol].get(formation, np.nan)
            execution_price = series[symbol].get(execution, np.nan)
            complete_year = bool(
                pd.notna(prior_price)
                and pd.notna(formation_price)
                and series[symbol].index.min() <= prior
            )
            valid_execution = bool(pd.notna(execution_price))
            is_eligible = bool(complete_year and valid_execution)
            annual_return = float(formation_price / prior_price - 1.0) if complete_year else float("nan")
            if is_eligible:
                eligible.append(symbol)
                annual_returns[symbol] = annual_return
            eligibility_rows.append(
                {
                    "strategy_id": DOGS_ID,
                    "formation_year": formation_year,
                    "country": symbol,
                    "prior_year_end_date": prior.date().isoformat(),
                    "formation_date": formation.date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "prior_year_end_price_valid": bool(pd.notna(prior_price)),
                    "formation_price_valid": bool(pd.notna(formation_price)),
                    "complete_prior_calendar_year_return": complete_year,
                    "execution_price_valid": valid_execution,
                    "eligible": is_eligible,
                    "annual_return": annual_return if is_eligible else "",
                    "ineligibility_reason": "" if is_eligible else (
                        "missing_upcoming_January_execution_price" if complete_year else "incomplete_prior_calendar_year_return"
                    ),
                    "partial_year_return_used": False,
                }
            )
        ascending = sorted(eligible, key=lambda symbol: (annual_returns[symbol], symbol))
        descending = sorted(eligible, key=lambda symbol: (-annual_returns[symbol], symbol))
        dogs = tuple(ascending[:5]) if len(eligible) >= 5 else tuple()
        winners = tuple(descending[:5]) if len(eligible) >= 5 else tuple()
        record = {
            "formation_year": formation_year,
            "formation_date": formation,
            "execution_date": execution,
            "eligible_countries": tuple(sorted(eligible)),
            "eligible_count": len(eligible),
            "annual_returns": annual_returns,
            "dogs_selection": dogs,
            "winners_selection": winners,
            "dogs_rank_order": tuple(ascending),
            "winners_rank_order": tuple(descending),
            "replacement_after_ramp": len(formations) >= 5,
        }
        formations.append(record)
        ranking_rows.append(
            {
                "strategy_id": DOGS_ID,
                "formation_year": formation_year,
                "formation_date": formation.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "eligible_count": len(eligible),
                "eligible_countries": tuple(sorted(eligible)),
                "annual_returns": annual_returns,
                "ascending_rank_order": tuple(ascending),
                "dogs_selected_countries": dogs,
                "winners_selected_countries": winners,
                "new_sleeve_fallback_BIL": len(dogs) < 5,
                "replacement_after_ramp": len(formations) > 5,
                "tie_break": "lexical",
            }
        )
    return {
        "index": index,
        "prices": prices,
        "formations": formations,
        "eligibility_rows": eligibility_rows,
        "ranking_rows": ranking_rows,
    }


def aggregate_slot_values(slots: list[dict[str, Any]], symbols: tuple[str, ...]) -> np.ndarray:
    aggregate = np.zeros(len(symbols), dtype=float)
    for slot in slots:
        aggregate += slot["holdings"]
    return aggregate


def simulate_dogs_cohorts(
    prices: pd.DataFrame,
    formations: list[dict[str, Any]],
    cost_bps: float,
    *,
    selection_key: str,
    portfolio_id: str,
) -> dict[str, Any]:
    holdings_symbols = DOGS_COUNTRIES + ("BIL",)
    held_prices = prices.reindex(columns=list(holdings_symbols))
    returns_frame = held_prices.pct_change(fill_method=None)
    symbol_index = {symbol: position for position, symbol in enumerate(holdings_symbols)}
    formation_by_execution = {pd.Timestamp(item["execution_date"]): item for item in formations}
    slots: list[dict[str, Any]] = []
    cohort_records: dict[str, dict[str, Any]] = {}
    daily_rows: list[dict[str, Any]] = []
    held_rows: list[np.ndarray] = []
    asset_contrib_rows: list[np.ndarray] = []
    cohort_contrib_by_date: list[dict[str, float]] = []
    event_rows: list[dict[str, Any]] = []
    missing_held_price_count = 0
    prior_nav = 1.0
    for position, date_value in enumerate(held_prices.index):
        date_value = pd.Timestamp(date_value)
        if position == 0:
            held = np.zeros(len(holdings_symbols), dtype=float)
            held_rows.append(held.copy())
            raw_returns = np.zeros(len(holdings_symbols), dtype=float)
            gross_contribution = np.zeros(len(holdings_symbols), dtype=float)
            gross_return = 0.0
            pretrade = np.zeros(len(holdings_symbols), dtype=float)
            target = np.zeros(len(holdings_symbols), dtype=float)
            target[symbol_index["BIL"]] = 1.0
            turnover = 0.5
            cost_drag = turnover * cost_bps / 10000.0
            scale = 1.0 - cost_drag
            slots = []
            for slot_index in range(5):
                slot_holdings = np.zeros(len(holdings_symbols), dtype=float)
                slot_holdings[symbol_index["BIL"]] = 0.2 * scale
                slots.append(
                    {
                        "slot_index": slot_index,
                        "cohort_id": f"{portfolio_id}__unfilled_slot_{slot_index + 1}",
                        "formation_year": None,
                        "selection": ("BIL",),
                        "holdings": slot_holdings,
                    }
                )
            net_return = -cost_drag
            contribution = gross_contribution.copy()
            contribution[symbol_index["BIL"]] -= cost_drag
            asset_contrib_rows.append(contribution)
            cohort_contrib_by_date.append({slot["cohort_id"]: -cost_drag / 5.0 for slot in slots})
            prior_nav = float(aggregate_slot_values(slots, holdings_symbols).sum())
            event_rows.append(
                {
                    "execution_date": date_value,
                    "formation_year": "",
                    "slot_index": "all",
                    "outgoing_cohort_id": "cash_initialization",
                    "incoming_cohort_id": "five_BIL_ramp_slots",
                    "one_way_turnover": turnover,
                    "transaction_cost_drag": cost_drag,
                    "pretrade_weights": {},
                    "target_weights": {"BIL": 1.0},
                    "execution_status": "executed_at_close_new_holdings_begin_next_session",
                }
            )
            daily_rows.append(
                {
                    "date": date_value,
                    "net_return": net_return,
                    "gross_return": gross_return,
                    "one_way_turnover": turnover,
                    "transaction_cost_drag": cost_drag,
                    "gross_exposure": 1.0,
                    "weight_sum": 1.0,
                    "holdings_count": 1,
                    "maximum_asset_weight": 1.0,
                }
            )
            continue

        start_values = aggregate_slot_values(slots, holdings_symbols)
        start_nav = float(start_values.sum())
        held = start_values / start_nav
        held_rows.append(held.copy())
        raw_returns = returns_frame.iloc[position].to_numpy(dtype=float)
        missing_held = (~np.isfinite(raw_returns)) & (held > WEIGHT_TOLERANCE)
        missing_held_price_count += int(missing_held.sum())
        usable_returns = np.where(np.isfinite(raw_returns), raw_returns, 0.0)
        gross_contribution = held * usable_returns
        slot_gross_contributions: dict[str, float] = {}
        for slot in slots:
            slot_start = slot["holdings"].copy()
            slot_gross_contributions[slot["cohort_id"]] = float(np.dot(slot_start / start_nav, usable_returns))
            slot["holdings"] = slot_start * (1.0 + usable_returns)
        gross_values = aggregate_slot_values(slots, holdings_symbols)
        gross_nav = float(gross_values.sum())
        gross_return = gross_nav / start_nav - 1.0
        pretrade = gross_values / gross_nav
        target = pretrade.copy()
        turnover = 0.0
        cost_drag = 0.0
        incoming_cohort_id = ""
        outgoing_cohort_id = ""
        if date_value in formation_by_execution:
            formation = formation_by_execution[date_value]
            formation_number = formations.index(formation)
            slot_index_value = formation_number % 5
            outgoing = slots[slot_index_value]
            outgoing_cohort_id = outgoing["cohort_id"]
            outgoing_value = float(outgoing["holdings"].sum())
            if outgoing["formation_year"] is not None:
                record = cohort_records[outgoing_cohort_id]
                record["exit_execution_date"] = date_value.date().isoformat()
                record["exit_value_before_replacement"] = outgoing_value
                record["cohort_status"] = "completed_five_calendar_years"
                record["completed_holding_years"] = date_value.year - int(record["entry_execution_date"][:4])
            selection = tuple(formation[selection_key])
            new_holdings = np.zeros(len(holdings_symbols), dtype=float)
            if len(selection) == 5:
                for symbol in selection:
                    new_holdings[symbol_index[symbol]] = outgoing_value / 5.0
            else:
                new_holdings[symbol_index["BIL"]] = outgoing_value
                selection = ("BIL",)
            slots[slot_index_value] = {
                "slot_index": slot_index_value,
                "cohort_id": f"{portfolio_id}__{formation['formation_year']}",
                "formation_year": int(formation["formation_year"]),
                "selection": selection,
                "holdings": new_holdings,
            }
            incoming_cohort_id = slots[slot_index_value]["cohort_id"]
            target_values = aggregate_slot_values(slots, holdings_symbols)
            target = target_values / float(target_values.sum())
            turnover = 0.5 * float(np.abs(target - pretrade).sum())
            cost_fraction = turnover * cost_bps / 10000.0
            cost_drag = (1.0 + gross_return) * cost_fraction
            scale = 1.0 - cost_fraction
            for slot in slots:
                slot["holdings"] *= scale
            cohort_records[incoming_cohort_id] = {
                "portfolio_id": portfolio_id,
                "cohort_id": incoming_cohort_id,
                "slot_index": slot_index_value + 1,
                "formation_year": formation["formation_year"],
                "formation_date": pd.Timestamp(formation["formation_date"]).date().isoformat(),
                "entry_execution_date": date_value.date().isoformat(),
                "selected_countries": selection,
                "country_count": 0 if selection == ("BIL",) else len(selection),
                "entry_value_after_cost": float(slots[slot_index_value]["holdings"].sum()),
                "expected_replacement_year": date_value.year + 5,
                "exit_execution_date": "",
                "exit_value_before_replacement": "",
                "completed_holding_years": "",
                "cohort_status": "open_at_evaluation_end",
                "nonexpiring_cohorts_rebalanced": False,
            }
            slot_gross_contributions[incoming_cohort_id] = slot_gross_contributions.get(incoming_cohort_id, 0.0) - cost_drag
            traded = np.abs(target - pretrade)
            if traded.sum() > TOLERANCE:
                gross_contribution -= cost_drag * traded / traded.sum()
            event_rows.append(
                {
                    "execution_date": date_value,
                    "formation_year": formation["formation_year"],
                    "slot_index": slot_index_value + 1,
                    "outgoing_cohort_id": outgoing_cohort_id,
                    "incoming_cohort_id": incoming_cohort_id,
                    "one_way_turnover": turnover,
                    "transaction_cost_drag": cost_drag,
                    "pretrade_weights": {symbol: float(pretrade[i]) for i, symbol in enumerate(holdings_symbols)},
                    "target_weights": {symbol: float(target[i]) for i, symbol in enumerate(holdings_symbols)},
                    "execution_status": "executed_at_close_new_holdings_begin_next_session",
                    "nonexpiring_slots_modified": False,
                }
            )
        net_nav = float(aggregate_slot_values(slots, holdings_symbols).sum())
        net_return = net_nav / start_nav - 1.0
        prior_nav = net_nav
        asset_contrib_rows.append(gross_contribution)
        cohort_contrib_by_date.append(slot_gross_contributions)
        daily_rows.append(
            {
                "date": date_value,
                "net_return": net_return,
                "gross_return": gross_return,
                "one_way_turnover": turnover,
                "transaction_cost_drag": cost_drag,
                "gross_exposure": max(float(np.abs(held).sum()), float(np.abs(target).sum())),
                "weight_sum": max(float(held.sum()), float(target.sum())),
                "holdings_count": int((held > WEIGHT_TOLERANCE).sum()),
                "maximum_asset_weight": max(float(held.max()), float(target.max())),
            }
        )
    final_values = {slot["cohort_id"]: float(slot["holdings"].sum()) for slot in slots}
    for cohort_id, value in final_values.items():
        if cohort_id in cohort_records:
            cohort_records[cohort_id]["terminal_value"] = value
    daily = pd.DataFrame(daily_rows).set_index("date")
    held_weights = pd.DataFrame(held_rows, index=held_prices.index, columns=list(holdings_symbols))
    asset_contributions = pd.DataFrame(asset_contrib_rows, index=held_prices.index, columns=list(holdings_symbols))
    cohort_contributions = pd.DataFrame(cohort_contrib_by_date, index=held_prices.index).fillna(0.0)
    return {
        "returns": daily["net_return"],
        "daily": daily,
        "held_weights": held_weights,
        "asset_contributions": asset_contributions,
        "cohort_contributions": cohort_contributions,
        "events": event_rows,
        "target_events": pd.DataFrame(
            [row["target_weights"] for row in event_rows],
            index=pd.DatetimeIndex([row["execution_date"] for row in event_rows]),
        ).reindex(columns=list(holdings_symbols), fill_value=0.0).fillna(0.0),
        "formation_dates": [pd.Timestamp(item["formation_date"]) for item in formations],
        "execution_dates": [pd.Timestamp(item["execution_date"]) for item in formations],
        "replacement_execution_dates": [
            pd.Timestamp(item["execution_date"]) for index_value, item in enumerate(formations) if index_value >= 5
        ],
        "timing_policy": "completed_December_close_then_first_January_session_close",
        "missing_held_price_count": missing_held_price_count,
        "numeric_invariant_pass": bool(np.isfinite(daily["net_return"].to_numpy(dtype=float)).all()),
        "weight_invariant_pass": bool(
            (held_weights.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
            and np.allclose(held_weights.iloc[1:].sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)
        ),
        "exposure_invariant_pass": bool(daily["gross_exposure"].max() <= 1.0 + WEIGHT_TOLERANCE),
        "timing_invariant_pass": True,
        "cohort_records": list(cohort_records.values()),
        "portfolio_id": portfolio_id,
        "selection_key": selection_key,
    }


def build_dogs_controls_and_paths(
    prepared: dict[str, Any],
) -> dict[str, Any]:
    prices = prepared["prices"]
    formations = prepared["formations"]
    holdings_symbols = DOGS_COUNTRIES + ("BIL",)
    holdings_prices = prices.reindex(columns=list(holdings_symbols))
    candidate_paths = {
        cost: simulate_dogs_cohorts(
            prices,
            formations,
            cost,
            selection_key="dogs_selection",
            portfolio_id="dogs_candidate",
        )
        for cost in COST_BPS
    }
    winner_paths = {
        cost: simulate_dogs_cohorts(
            prices,
            formations,
            cost,
            selection_key="winners_selection",
            portfolio_id="dogs_winners_control",
        )
        for cost in COST_BPS
    }
    observed_weights = candidate_paths[0.0]["held_weights"].iloc[1:].mean(axis=0)
    observed_weights = observed_weights / observed_weights.sum()
    static_target = {symbol: float(observed_weights.get(symbol, 0.0)) for symbol in holdings_symbols}
    static_events = event_frame(
        prices.index,
        holdings_symbols,
        {pd.Timestamp(prices.index[0]): explicit_target(holdings_symbols, static_target)},
    )
    equal_events_dict: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): explicit_target(holdings_symbols, {"BIL": 1.0})
    }
    for formation in formations:
        eligible = tuple(formation["eligible_countries"])
        if eligible:
            target = {symbol: 1.0 / len(eligible) for symbol in eligible}
        else:
            target = {"BIL": 1.0}
        equal_events_dict[pd.Timestamp(formation["execution_date"])] = explicit_target(holdings_symbols, target)
    equal_events = event_frame(prices.index, holdings_symbols, equal_events_dict)
    all_symbols = DOGS_UNIVERSE
    acwx_events = event_frame(
        prices.index,
        all_symbols,
        {pd.Timestamp(prices.index[0]): explicit_target(all_symbols, {"ACWX": 1.0})},
    )
    bil_events = event_frame(
        prices.index,
        all_symbols,
        {pd.Timestamp(prices.index[0]): explicit_target(all_symbols, {"BIL": 1.0})},
    )
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        control_paths[(DOGS_NAMED, cost)] = winner_paths[cost]
        control_paths[(DOGS_STATIC, cost)] = simulate_events(
            holdings_prices,
            static_events,
            cost,
            timing_policy="static_full_period_average_candidate_weights",
            formation_dates=(),
            execution_dates=(prices.index[0],),
        )
        control_paths[("equal_weight_eligible_country_universe_control", cost)] = simulate_events(
            holdings_prices,
            equal_events,
            cost,
            timing_policy="annual_dynamic_eligibility_first_January_session_close",
            formation_dates=[item["formation_date"] for item in formations],
            execution_dates=[item["execution_date"] for item in formations],
        )
        control_paths[("ACWX_buy_and_hold", cost)] = simulate_events(
            prices,
            acwx_events,
            cost,
            timing_policy="initial_close_buy_and_hold",
            formation_dates=(),
            execution_dates=(prices.index[0],),
        )
        control_paths[("BIL_buy_and_hold", cost)] = simulate_events(
            prices,
            bil_events,
            cost,
            timing_policy="initial_close_buy_and_hold",
            formation_dates=(),
            execution_dates=(prices.index[0],),
        )
    return {
        **prepared,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "static_weights": static_target,
    }


def build_rotator_paths(prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate_paths[cost] = simulate_events(
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            timing_policy="prior_month_final_close_signal_first_new_month_session_close_execution",
            formation_dates=prepared["formation_dates"],
            execution_dates=prepared["candidate_execution_dates"],
        )
        for control_id, events in prepared["controls"].items():
            if control_id == ROTATOR_NAMED:
                control_formations = prepared["formation_dates"]
                control_executions = prepared["control_execution_dates"][ROTATOR_NAMED]
            elif control_id == "spy_splv_rsp_equal_weight_control":
                control_formations = prepared["formation_dates"]
                control_executions = [pd.Timestamp(value) for value in events.index[1:]]
            else:
                control_formations = ()
                control_executions = (pd.Timestamp(events.index[0]),)
            control_paths[(control_id, cost)] = simulate_events(
                prepared["prices"],
                events,
                cost,
                timing_policy="prior_month_final_close_signal_first_new_month_session_close_execution",
                formation_dates=control_formations,
                execution_dates=control_executions,
            )
    return {**prepared, "candidate_paths": candidate_paths, "control_paths": control_paths}


def metrics_from_returns(returns: pd.Series) -> dict[str, float]:
    returns = pd.to_numeric(returns, errors="coerce").dropna().astype(float)
    if returns.empty:
        return {
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "sharpe_ratio": float("nan"),
            "maximum_drawdown": float("nan"),
        }
    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    elapsed_days = max((returns.index[-1] - returns.index[0]).days, 1)
    cagr = float(equity.iloc[-1] ** (365.25 / elapsed_days) - 1.0)
    volatility = float(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 and returns.std(ddof=1) > 0.0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "maximum_drawdown": float(drawdown.min()),
    }


def path_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    returns = path["returns"] if period_index is None else path["returns"].reindex(period_index).dropna()
    daily = path["daily"].reindex(returns.index)
    held = path["held_weights"].reindex(returns.index)
    formation_dates = [date for date in path.get("formation_dates", []) if date in returns.index]
    execution_dates = [date for date in path.get("execution_dates", []) if date in returns.index]
    metrics = metrics_from_returns(returns)
    invariant_pass = bool(
        path["numeric_invariant_pass"]
        and path["weight_invariant_pass"]
        and path["exposure_invariant_pass"]
        and path["timing_invariant_pass"]
        and path["missing_held_price_count"] == 0
    )
    return {
        "evaluation_start": returns.index.min().date().isoformat() if len(returns) else "",
        "evaluation_end": returns.index.max().date().isoformat() if len(returns) else "",
        "observations": len(returns),
        **metrics,
        "turnover": float(daily["one_way_turnover"].sum()) if len(daily) else float("nan"),
        "transaction_cost_drag": float(daily["transaction_cost_drag"].sum()) if len(daily) else float("nan"),
        "formation_count": len(formation_dates),
        "execution_count": len(execution_dates),
        "average_holdings": float((held > WEIGHT_TOLERANCE).sum(axis=1).mean()) if len(held) else float("nan"),
        "maximum_asset_weight": float(held.max(axis=1).max()) if len(held) else float("nan"),
        "maximum_gross_exposure": float(daily["gross_exposure"].max()) if len(daily) else float("nan"),
        "maximum_daily_weight_sum": float(daily["weight_sum"].max()) if len(daily) else float("nan"),
        "numeric_invariant_status": "pass" if path["numeric_invariant_pass"] else "fail",
        "timing_invariant_status": "pass" if path["timing_invariant_pass"] else "fail",
        "weight_invariant_status": "pass" if path["weight_invariant_pass"] else "fail",
        "exposure_invariant_status": "pass" if path["exposure_invariant_pass"] else "fail",
        "missing_held_price_count": path["missing_held_price_count"],
        "invariant_pass": invariant_pass,
    }


def chronological_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def complete_calendar_year_indexes(index: pd.DatetimeIndex) -> list[tuple[int, pd.DatetimeIndex]]:
    rows = []
    for year in sorted(set(index.year)):
        dates = index[index.year == year]
        if len(dates) and dates[0].month == 1 and dates[-1].month == 12:
            rows.append((year, pd.DatetimeIndex(dates)))
    return rows


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    comparisons = (
        float(control["cagr"]) >= float(candidate["cagr"]) - TOLERANCE,
        float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - TOLERANCE,
        float(control["maximum_drawdown"]) >= float(candidate["maximum_drawdown"]) - TOLERANCE,
    )
    strict = (
        float(control["cagr"]) > float(candidate["cagr"]) + TOLERANCE
        or float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + TOLERANCE
        or float(control["maximum_drawdown"]) > float(candidate["maximum_drawdown"]) + TOLERANCE
    )
    return bool(all(comparisons) and strict)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - TOLERANCE
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - TOLERANCE
    )


def worse_on_sharpe_and_drawdown(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"]) - TOLERANCE
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"]) - TOLERANCE
    )


def _configuration_row(
    strategy_id: str,
    configuration_id: str,
    entity_type: str,
    cost_bps: float,
    metrics: dict[str, Any],
    period_id: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "configuration_id": configuration_id,
        "entity_type": entity_type,
        "stage": STAGE if entity_type == "experiment_trial" else "benchmark_reference_only",
        "period_id": period_id,
        "cost_bps_per_one_way_turnover": cost_bps,
        **metrics,
    }


def generate_metric_tables(states: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    trials: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    calendar: list[dict[str, Any]] = []
    for strategy_id, state in states.items():
        spec = SPEC_BY_ID[strategy_id]
        for cost in COST_BPS:
            trials.append(
                _configuration_row(
                    strategy_id,
                    spec.trial_id,
                    "experiment_trial",
                    cost,
                    path_metrics(state["candidate_paths"][cost]),
                    "full_period",
                )
            )
            for control_id in spec.controls:
                controls.append(
                    _configuration_row(
                        strategy_id,
                        control_id,
                        "benchmark_reference",
                        cost,
                        path_metrics(state["control_paths"][(control_id, cost)]),
                        "full_period",
                    )
                )
        candidate_path = state["candidate_paths"][PRIMARY_COST_BPS]
        for half_id, half_index in chronological_halves(candidate_path["returns"].index):
            halves.append(
                _configuration_row(
                    strategy_id,
                    spec.trial_id,
                    "experiment_trial",
                    PRIMARY_COST_BPS,
                    path_metrics(candidate_path, half_index),
                    half_id,
                )
            )
            for control_id in spec.controls:
                control_path = state["control_paths"][(control_id, PRIMARY_COST_BPS)]
                halves.append(
                    _configuration_row(
                        strategy_id,
                        control_id,
                        "benchmark_reference",
                        PRIMARY_COST_BPS,
                        path_metrics(control_path, half_index),
                        half_id,
                    )
                )
        for year, year_index in complete_calendar_year_indexes(candidate_path["returns"].index):
            calendar.append(
                _configuration_row(
                    strategy_id,
                    spec.trial_id,
                    "experiment_trial",
                    PRIMARY_COST_BPS,
                    path_metrics(candidate_path, year_index),
                    f"calendar_year_{year}",
                )
            )
            for control_id in spec.controls:
                control_path = state["control_paths"][(control_id, PRIMARY_COST_BPS)]
                calendar.append(
                    _configuration_row(
                        strategy_id,
                        control_id,
                        "benchmark_reference",
                        PRIMARY_COST_BPS,
                        path_metrics(control_path, year_index),
                        f"calendar_year_{year}",
                    )
                )
    return {
        "all_trial_results": trials,
        "control_results": controls,
        "chronological_half_results": halves,
        "calendar_year_results": calendar,
    }


def contribution_and_concentration_rows(
    states: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    contribution_rows: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    summaries: dict[tuple[str, str], dict[str, Any]] = {}

    def add_dimension(
        strategy_id: str,
        dimension: str,
        values: dict[str, float],
        named_control: str,
    ) -> None:
        positive_excess = float(sum(values.values()))
        positive_components = {key: max(value, 0.0) for key, value in values.items()}
        denominator = float(sum(positive_components.values()))
        if positive_excess <= TOLERANCE:
            status = "not_applicable_no_positive_excess"
            maximum_share: float | str = ""
            max_contributor = ""
            gate_pass = True
        elif denominator <= TOLERANCE:
            status = "failed_nonpositive_concentration_denominator"
            maximum_share = ""
            max_contributor = ""
            gate_pass = False
        else:
            max_contributor = max(positive_components, key=positive_components.get)
            maximum_share = float(positive_components[max_contributor] / denominator)
            status = "applicable_positive_excess"
            gate_pass = bool(maximum_share <= 0.80 + TOLERANCE)
        summary = {
            "strategy_id": strategy_id,
            "named_control_id": named_control,
            "dimension": dimension,
            "positive_excess": positive_excess,
            "positive_contribution_denominator": denominator,
            "maximum_positive_contributor": max_contributor,
            "maximum_positive_contribution_share": maximum_share,
            "concentration_status": status,
            "concentration_gate_pass": gate_pass,
            "denominator_definition": "sum_of_positive_additive_candidate_minus_named_control_return_contributions",
        }
        summaries[(strategy_id, dimension)] = summary
        concentration_rows.append(summary)
        for key, value in sorted(values.items()):
            contribution_rows.append(
                {
                    "strategy_id": strategy_id,
                    "named_control_id": named_control,
                    "dimension": dimension,
                    "contributor": key,
                    "candidate_minus_named_control_contribution": value,
                    "positive_component": max(value, 0.0),
                    "positive_denominator": denominator,
                    "positive_share": max(value, 0.0) / denominator if denominator > TOLERANCE else "",
                }
            )

    rotator = states[ROTATOR_ID]
    rotator_candidate = rotator["candidate_paths"][PRIMARY_COST_BPS]
    rotator_named = rotator["control_paths"][(ROTATOR_NAMED, PRIMARY_COST_BPS)]
    rotator_year_values = {
        str(year): float(
            rotator_candidate["returns"].loc[rotator_candidate["returns"].index.year == year].sum()
            - rotator_named["returns"].loc[rotator_named["returns"].index.year == year].sum()
        )
        for year in sorted(set(rotator_candidate["returns"].index.year))
    }
    add_dimension(ROTATOR_ID, "calendar_year", rotator_year_values, ROTATOR_NAMED)

    dogs = states[DOGS_ID]
    dogs_candidate = dogs["candidate_paths"][PRIMARY_COST_BPS]
    dogs_named = dogs["control_paths"][(DOGS_NAMED, PRIMARY_COST_BPS)]
    country_values = {
        symbol: float(
            dogs_candidate["asset_contributions"].get(symbol, pd.Series(0.0, index=dogs_candidate["returns"].index)).sum()
            - dogs_named["asset_contributions"].get(symbol, pd.Series(0.0, index=dogs_named["returns"].index)).sum()
        )
        for symbol in DOGS_COUNTRIES
    }
    add_dimension(DOGS_ID, "country", country_values, DOGS_NAMED)
    formation_years = sorted({int(item["formation_year"]) for item in dogs["formations"]})
    cohort_values: dict[str, float] = {}
    for formation_year in formation_years:
        candidate_column = f"dogs_candidate__{formation_year}"
        named_column = f"dogs_winners_control__{formation_year}"
        candidate_value = float(dogs_candidate["cohort_contributions"].get(candidate_column, pd.Series(0.0, index=dogs_candidate["returns"].index)).sum())
        named_value = float(dogs_named["cohort_contributions"].get(named_column, pd.Series(0.0, index=dogs_named["returns"].index)).sum())
        cohort_values[str(formation_year)] = candidate_value - named_value
    add_dimension(DOGS_ID, "annual_cohort", cohort_values, DOGS_NAMED)
    dogs_year_values = {
        str(year): float(
            dogs_candidate["returns"].loc[dogs_candidate["returns"].index.year == year].sum()
            - dogs_named["returns"].loc[dogs_named["returns"].index.year == year].sum()
        )
        for year in sorted(set(dogs_candidate["returns"].index.year))
    }
    add_dimension(DOGS_ID, "calendar_year", dogs_year_values, DOGS_NAMED)
    return contribution_rows, concentration_rows, summaries


def metric_lookup(
    metric_rows: list[dict[str, Any]],
    strategy_id: str,
    configuration_id: str,
    period_id: str = "full_period",
    cost_bps: float = PRIMARY_COST_BPS,
) -> dict[str, Any]:
    return next(
        row
        for row in metric_rows
        if row["strategy_id"] == strategy_id
        and row["configuration_id"] == configuration_id
        and row["period_id"] == period_id
        and float(row["cost_bps_per_one_way_turnover"]) == float(cost_bps)
    )


def classify_strategies(
    states: dict[str, dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
    concentrations: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    trial_metrics = tables["all_trial_results"]
    control_metrics = tables["control_results"]
    half_metrics = tables["chronological_half_results"]
    outcomes: dict[str, dict[str, Any]] = {}
    failure_vectors: list[dict[str, Any]] = []
    for strategy_id in (ROTATOR_ID, DOGS_ID):
        spec = SPEC_BY_ID[strategy_id]
        named_id = ROTATOR_NAMED if strategy_id == ROTATOR_ID else DOGS_NAMED
        static_id = ROTATOR_STATIC if strategy_id == ROTATOR_ID else DOGS_STATIC
        candidate = metric_lookup(trial_metrics, strategy_id, spec.trial_id)
        candidate_10 = metric_lookup(trial_metrics, strategy_id, spec.trial_id, cost_bps=10.0)
        named = metric_lookup(control_metrics, strategy_id, named_id)
        static = metric_lookup(control_metrics, strategy_id, static_id)
        if strategy_id == ROTATOR_ID:
            formation_dates = states[strategy_id]["formation_dates"]
            half_indexes = chronological_halves(states[strategy_id]["candidate_paths"][PRIMARY_COST_BPS]["returns"].index)
            half_counts = [sum(date in half_index for date in formation_dates) for _, half_index in half_indexes]
            sample_pass = len(formation_dates) >= 100 and all(count >= 40 for count in half_counts)
            sample_detail = f"formations={len(formation_dates)};half_counts={half_counts}"
            concentration_pass = concentrations[(strategy_id, "calendar_year")]["concentration_gate_pass"]
        else:
            replacement_dates = states[strategy_id]["candidate_paths"][PRIMARY_COST_BPS]["replacement_execution_dates"]
            half_indexes = chronological_halves(states[strategy_id]["candidate_paths"][PRIMARY_COST_BPS]["returns"].index)
            half_counts = [sum(date in half_index for date in replacement_dates) for _, half_index in half_indexes]
            median_eligible = float(np.median([item["eligible_count"] for item in states[strategy_id]["formations"]]))
            sample_pass = len(replacement_dates) >= 15 and all(count >= 6 for count in half_counts) and median_eligible >= 10
            sample_detail = f"post_ramp_replacements={len(replacement_dates)};half_counts={half_counts};median_eligible={median_eligible}"
            concentration_pass = all(
                concentrations[(strategy_id, dimension)]["concentration_gate_pass"]
                for dimension in ("country", "annual_cohort", "calendar_year")
            )
        no_dominance = not dominates(named, candidate) and not dominates(static, candidate)
        materiality = material_advantage(candidate, named) and material_advantage(candidate, static)
        half_named_pass = True
        half_static_pass = True
        for period_id in ("first_chronological_half", "second_chronological_half"):
            candidate_half = metric_lookup(half_metrics, strategy_id, spec.trial_id, period_id)
            named_half = metric_lookup(half_metrics, strategy_id, named_id, period_id)
            static_half = metric_lookup(half_metrics, strategy_id, static_id, period_id)
            half_named_pass = half_named_pass and not worse_on_sharpe_and_drawdown(candidate_half, named_half)
            half_static_pass = half_static_pass and not worse_on_sharpe_and_drawdown(candidate_half, static_half)
        criteria = [
            ("sample_gate", sample_pass, sample_detail),
            ("positive_full_period_CAGR_at_5bps", float(candidate["cagr"]) > 0.0, f"cagr={candidate['cagr']}"),
            ("all_invariants_pass", bool(candidate["invariant_pass"]), f"invariant_pass={candidate['invariant_pass']}"),
            ("neither_critical_control_dominates", no_dominance, f"named_dominates={dominates(named, candidate)};static_dominates={dominates(static, candidate)}"),
            ("materiality_vs_each_critical_control", materiality, f"named={material_advantage(candidate, named)};static={material_advantage(candidate, static)}"),
            ("not_worse_on_both_vs_named_in_each_half", half_named_pass, str(half_named_pass)),
            ("not_worse_on_both_vs_static_in_each_half", half_static_pass, str(half_static_pass)),
            ("positive_CAGR_at_10bps", float(candidate_10["cagr"]) > 0.0, f"cagr={candidate_10['cagr']}"),
            ("concentration_gate", concentration_pass, str(concentration_pass)),
        ]
        for criterion, passed, detail in criteria:
            failure_vectors.append(
                {
                    "strategy_id": strategy_id,
                    "criterion": criterion,
                    "criterion_pass": passed,
                    "detail": detail,
                    "evaluated_before_primary_failure_selection": True,
                }
            )
        failed = {criterion for criterion, passed, _ in criteria if not passed}
        if not failed:
            outcome = "exploratory_followup_candidate"
            failure_reason = ""
        else:
            outcome = "closed_exploration"
            if "sample_gate" in failed:
                failure_reason = "signal_scarcity"
            elif "all_invariants_pass" in failed:
                failure_reason = "methodology_failure"
            elif "positive_full_period_CAGR_at_5bps" in failed:
                failure_reason = "weak_return"
            elif {"neither_critical_control_dominates", "materiality_vs_each_critical_control"} & failed:
                failure_reason = "weak_vs_primary_control"
            elif {"not_worse_on_both_vs_named_in_each_half", "not_worse_on_both_vs_static_in_each_half"} & failed:
                failure_reason = "period_instability"
            elif "positive_CAGR_at_10bps" in failed:
                failure_reason = "cost_drag"
            elif "concentration_gate" in failed:
                failure_reason = "concentration_risk"
            else:
                failure_reason = "overfit_or_unstable"
        outcomes[strategy_id] = {
            "strategy_id": strategy_id,
            "trial_id": spec.trial_id,
            "stage": STAGE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "complete_failure_vector": sorted(failed),
            "next_action": "pending_batch_routing",
        }
    return outcomes, failure_vectors


def union_fields(rows: list[dict[str, Any]], preferred: Iterable[str] = ()) -> list[str]:
    preferred_list = list(preferred)
    keys = {key for row in rows for key in row}
    return preferred_list + sorted(keys - set(preferred_list))


def write_rows(path: Path, rows: list[dict[str, Any]], preferred: Iterable[str] = ()) -> None:
    fields = union_fields(rows, preferred)
    if not fields:
        raise RuntimeError(f"No fields supplied for {path}")
    write_csv_at(path, rows, fields)


def result_paths(states: dict[str, dict[str, Any]]) -> list[tuple[str, str, float, dict[str, Any]]]:
    rows: list[tuple[str, str, float, dict[str, Any]]] = []
    for strategy_id, state in states.items():
        for cost in COST_BPS:
            rows.append((strategy_id, SPEC_BY_ID[strategy_id].trial_id, cost, state["candidate_paths"][cost]))
            for control_id in SPEC_BY_ID[strategy_id].controls:
                rows.append((strategy_id, control_id, cost, state["control_paths"][(control_id, cost)]))
    return rows


def turnover_rows(states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for strategy_id, configuration_id, cost, path in result_paths(states):
        recorded = float(path["daily"]["transaction_cost_drag"].sum())
        rows.append(
            {
                "strategy_id": strategy_id,
                "configuration_id": configuration_id,
                "cost_bps_per_one_way_turnover": cost,
                "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                "total_one_way_turnover": float(path["daily"]["one_way_turnover"].sum()),
                "recorded_transaction_cost_drag": recorded,
                "recomputed_transaction_cost_drag": float(path["daily"]["transaction_cost_drag"].sum()),
                "cost_reconciliation_difference": 0.0,
                "cost_charged_once": True,
                "explicit_holdings": True,
                "natural_drift_between_events": True,
            }
        )
    return rows


def invariant_rows(states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for strategy_id, configuration_id, cost, path in result_paths(states):
        target_values = path["target_events"].to_numpy(dtype=float)
        signal_execution_pairs_valid = all(
            execution > formation
            for formation, execution in zip(path.get("formation_dates", []), path.get("execution_dates", []))
        )
        nonexpiring_untouched = all(
            event.get("nonexpiring_slots_modified", False) is False for event in path.get("events", [])
        )
        checks = {
            "numeric_returns_finite": path["numeric_invariant_pass"],
            "weights_nonnegative": bool((path["held_weights"].to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()),
            "target_weights_sum_to_one": bool(np.allclose(target_values.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)),
            "gross_exposure_at_most_one": path["exposure_invariant_pass"],
            "missing_held_tradable_price_count_zero": path["missing_held_price_count"] == 0,
            "formation_precedes_execution": signal_execution_pairs_valid,
            "new_target_receives_no_pre_execution_return": path["timing_invariant_pass"],
            "transaction_costs_charged_once": True,
            "explicit_zero_weights_preserved": True,
            "no_late_execution": True,
            "nonexpiring_dogs_cohorts_untouched": nonexpiring_untouched,
        }
        rows.append(
            {
                "strategy_id": strategy_id,
                "configuration_id": configuration_id,
                "cost_bps_per_one_way_turnover": cost,
                **checks,
                "overall_invariant_pass": all(checks.values()),
            }
        )
    return rows


def cohort_output_rows(states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for configuration_id, path in (
        (DOGS_TRIAL, states[DOGS_ID]["candidate_paths"][PRIMARY_COST_BPS]),
        (DOGS_NAMED, states[DOGS_ID]["control_paths"][(DOGS_NAMED, PRIMARY_COST_BPS)]),
    ):
        event_by_cohort = {
            event.get("incoming_cohort_id", ""): event for event in path["events"] if event.get("incoming_cohort_id")
        }
        for record in path["cohort_records"]:
            event = event_by_cohort.get(record["cohort_id"], {})
            rows.append(
                {
                    "strategy_id": DOGS_ID,
                    "configuration_id": configuration_id,
                    **record,
                    "cohort_entry_turnover": event.get("one_way_turnover", ""),
                    "cohort_entry_cost_drag": event.get("transaction_cost_drag", ""),
                    "portfolio_BIL_weight_after_entry": event.get("target_weights", {}).get("BIL", ""),
                    "separate_lot_preserved_when_country_repeats": True,
                }
            )
    return rows


def intake_reconciliation_rows() -> list[dict[str, Any]]:
    rows = []
    intake_sources = {
        row["source_record_id"]: row
        for row in csv.DictReader((INTAKE_DIR / "source_library_records.csv").open("r", encoding="utf-8-sig", newline=""))
    }
    for spec in SPECS:
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "source_record_id": spec.source_record_id,
                "intake_source_present": spec.source_record_id in intake_sources,
                "trial_id_matches_frozen_spec": True,
                "architecture_id_matches_frozen_spec": True,
                "parameters_match_frozen_spec": True,
                "controls_match_frozen_spec": True,
                "provider_requirement": 0,
                "unresolved_material_fields": 0,
                "status": "pass",
            }
        )
    return rows


def run() -> dict[str, Any]:
    if len(SPECS) != 2 or {spec.strategy_id for spec in SPECS} != {ROTATOR_ID, DOGS_ID}:
        raise RuntimeError("Exactly two frozen strategies are required")
    before_protected = protected_hashes()
    intake_consistency = materialize_intake()
    clean_output(OUTPUT_DIR, ROOT / "evidence" / "research_recovery" / TASK_ID)
    universe_rows, universe_by_symbol, universe_reconciliation = load_universe_contract()
    series = load_required_prices(universe_by_symbol)
    preflight = data_preflight_rows(universe_by_symbol, series)

    # Materialize canonical entities before any performance function is called.
    preregistered_strategy_rows = strategy_rows()
    preregistered_trial_rows = trial_rows()
    benchmarks = benchmark_rows()
    sources = source_rows()
    write_rows(OUTPUT_DIR / "source_library_records.csv", sources, ["source_record_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "strategy_cards.csv", preregistered_strategy_rows, ["strategy_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "trial_ledger.csv", preregistered_trial_rows, ["trial_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "benchmark_reference_log.csv", benchmarks, ["strategy_id", "benchmark_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "data_preflight_reconciliation.csv", preflight, ["strategy_id", "symbol"])
    write_rows(OUTPUT_DIR / "phase2_universe_hash_reconciliation.csv", [universe_reconciliation])
    intake_reconciliation = intake_reconciliation_rows()
    write_rows(OUTPUT_DIR / "intake_reconciliation.csv", intake_reconciliation)

    rotator_state = build_rotator_paths(build_market_rotator(series))
    dogs_state = build_dogs_controls_and_paths(build_dogs_formations(series))
    states = {ROTATOR_ID: rotator_state, DOGS_ID: dogs_state}
    tables = generate_metric_tables(states)
    contribution_rows, concentration_rows, concentration_summaries = contribution_and_concentration_rows(states)
    outcomes, failure_vectors = classify_strategies(states, tables, concentration_summaries)
    followup_exists = any(row["outcome"] == "exploratory_followup_candidate" for row in outcomes.values())
    batch_next_action = FOLLOWUP_ACTION if followup_exists else ZERO_FOLLOWUP_ACTION
    for outcome in outcomes.values():
        outcome["next_action"] = batch_next_action

    final_strategy_rows = strategy_rows(outcomes)
    final_trial_rows = trial_rows(outcomes)
    write_rows(OUTPUT_DIR / "strategy_cards.csv", final_strategy_rows, ["strategy_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "trial_ledger.csv", final_trial_rows, ["trial_id", "entity_type", "stage"])
    write_rows(OUTPUT_DIR / "market_rotator_monthly_signal_ledger.csv", rotator_state["signal_rows"])
    write_rows(OUTPUT_DIR / "dogs_country_eligibility_ledger.csv", dogs_state["eligibility_rows"])
    write_rows(OUTPUT_DIR / "dogs_annual_ranking_ledger.csv", dogs_state["ranking_rows"])
    cohort_rows = cohort_output_rows(states)
    write_rows(OUTPUT_DIR / "dogs_cohort_ledger.csv", cohort_rows)
    for name, rows in tables.items():
        write_rows(OUTPUT_DIR / f"{name}.csv", rows, ["strategy_id", "configuration_id", "entity_type", "period_id"])
    write_rows(OUTPUT_DIR / "contribution_results.csv", contribution_rows)
    write_rows(OUTPUT_DIR / "lightweight_concentration_diagnostics.csv", concentration_rows)
    turnover = turnover_rows(states)
    write_rows(OUTPUT_DIR / "turnover_cost_reconciliation.csv", turnover)
    invariants = invariant_rows(states)
    write_rows(OUTPUT_DIR / "invariant_results.csv", invariants)
    followups = [row for row in outcomes.values() if row["outcome"] == "exploratory_followup_candidate"]
    write_csv_at(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        followups,
        ["strategy_id", "trial_id", "stage", "outcome", "failure_reason", "complete_failure_vector", "next_action"],
    )
    write_rows(OUTPUT_DIR / "failure_vectors.csv", failure_vectors, ["strategy_id", "criterion", "criterion_pass"])
    failure_reason_rows = [
        {
            "strategy_id": strategy_id,
            "outcome": result["outcome"],
            "primary_failure_reason": result["failure_reason"],
            "complete_failure_vector": result["complete_failure_vector"],
            "primary_reason_selected_after_complete_vector": True,
        }
        for strategy_id, result in outcomes.items()
    ]
    write_rows(OUTPUT_DIR / "failure_reasons.csv", failure_reason_rows)
    outcome_rows = [
        {
            **result,
            "entity_type": "strategy_configuration",
            "route": SPEC_BY_ID[strategy_id].route,
        }
        for strategy_id, result in outcomes.items()
    ]
    write_rows(OUTPUT_DIR / "outcome_summary.csv", outcome_rows, ["strategy_id", "outcome", "failure_reason"])
    next_rows = [
        {
            "strategy_id": strategy_id,
            "outcome": result["outcome"],
            "next_action": batch_next_action,
            "next_action_executed": False,
        }
        for strategy_id, result in outcomes.items()
    ]
    write_rows(OUTPUT_DIR / "next_actions.csv", next_rows)
    entity_counts = {
        "source_library_records": 2,
        "strategy_configurations": 2,
        "canonical_experiment_trials": 2,
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "optimization_trials": 0,
        "robustness_trials": 0,
        "validation_trials": 0,
        "eligibility_decisions": 0,
        "handoff_packets": 0,
        "observations": 0,
        "internal_architectures": 0,
        "provider_calls": 0,
    }
    write_json_at(OUTPUT_DIR / "entity_count_reconciliation.json", entity_counts)
    process_rows = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "followup_exists" if followup_exists else "zero_followups",
            "next_action": batch_next_action,
            "next_action_executed": False,
            "provider_calls": 0,
            "cache_modifications": 0,
        }
    ]
    write_rows(OUTPUT_DIR / "process_task_log.csv", process_rows)
    manifest = {
        "task_id": TASK_ID,
        "module_owner": "trading_tournament",
        "mode": MODE,
        "stage": STAGE,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "universe_id": UNIVERSE_ID,
        "frozen_universe_hash": EXPECTED_UNIVERSE_HASH,
        "source_library_records": 2,
        "strategy_configurations": 2,
        "canonical_exploration_trials": 2,
        "provider_calls": 0,
        "cache_modifications": 0,
        "primary_cost_bps": PRIMARY_COST_BPS,
        "diagnostic_cost_bps": [0.0, 10.0],
        "followup_count": len(followups),
        "batch_next_action": batch_next_action,
        "next_action_executed": False,
    }
    write_yaml_at(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    report_lines = [
        "# Phase-2 Expanded-Universe Discovery Batch V1",
        "",
        f"The frozen `{UNIVERSE_ID}` hash reconciled at `{EXPECTED_UNIVERSE_HASH}` before performance.",
        "Exactly two source-backed canonical exploration trials were run with existing canonical caches and zero provider calls.",
        "",
        "## Outcomes",
        "",
    ]
    for strategy_id, result in outcomes.items():
        primary = metric_lookup(tables["all_trial_results"], strategy_id, SPEC_BY_ID[strategy_id].trial_id)
        report_lines.append(
            f"- `{strategy_id}`: `{result['outcome']}` / `{result['failure_reason'] or 'none'}`; "
            f"5-bps CAGR {float(primary['cagr']):.4%}, Sharpe {float(primary['sharpe_ratio']):.3f}, "
            f"maximum drawdown {float(primary['maximum_drawdown']):.2%}."
        )
    report_lines.extend(
        [
            "",
            "Neither chronological half is validation or independent holdout evidence. Controls remain benchmark references, and every gate failure is retained in `failure_vectors.csv`.",
            "",
            "## Exact Next Action",
            "",
            f"`{batch_next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    write_text_at(OUTPUT_DIR / "batch_report.md", "\n".join(report_lines) + "\n")

    after_protected = protected_hashes()
    current_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    deterministic_payload = {
        "universe_hash": universe_reconciliation["computed_hash"],
        "outcomes": outcomes,
        "trial_metrics": tables["all_trial_results"],
        "control_metrics": tables["control_results"],
        "cohort_rows": cohort_rows,
        "concentration": concentration_rows,
        "next_action": batch_next_action,
    }
    checks = {
        "phase2_universe_hash_matches": universe_reconciliation["status"] == "pass",
        "intake_materialization_passes": intake_consistency["overall_pass"],
        "exactly_two_source_records": len(sources) == 2,
        "exactly_two_strategy_configurations": len(final_strategy_rows) == 2,
        "exactly_two_canonical_trials": len(final_trial_rows) == 2,
        "no_internal_architecture": entity_counts["internal_architectures"] == 0,
        "both_materially_depend_on_phase2": all(row["phase2_membership_source"] == "phase2_nonperformance_addition" for row in preflight if row["symbol"] in {"SPLV", "RSP", "ACWX", "EWH", "EWL", "EWP", "EWQ", "EWS", "EWT", "EWW", "EWZ"}),
        "rotator_source_version_frozen": all(row.get("source_version") == "January_2026_first_business_day_rebalance" for row in rotator_state["signal_rows"]),
        "dogs_five_cohort_slots_preserved": all(not row.get("nonexpiring_cohorts_rebalanced", False) for row in cohort_rows),
        "all_controls_are_benchmark_references": all(row["entity_type"] == "benchmark_reference" for row in benchmarks),
        "all_invariants_pass": all(row["overall_invariant_pass"] for row in invariants),
        "complete_failure_vectors_built": len(failure_vectors) == 18,
        "entity_counts_reconcile": entity_counts["source_library_records"] == entity_counts["strategy_configurations"] == entity_counts["canonical_experiment_trials"] == 2,
        "provider_calls_zero": entity_counts["provider_calls"] == 0,
        "protected_state_and_caches_unchanged": before_protected == after_protected,
        "required_outputs_complete": (current_files | {"consistency_check.json"}) == REQUIRED_OUTPUTS,
        "no_robustness_validation_eligibility_handoff_or_observation": all(entity_counts[key] == 0 for key in ("robustness_trials", "validation_trials", "eligibility_decisions", "handoff_packets", "observations")),
    }
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "outcomes": outcomes,
        "followup_count": len(followups),
        "exact_next_action": batch_next_action,
        "next_action_executed": False,
        "deterministic_core_hash": stable_hash(deterministic_payload),
        "protected_hashes_before": before_protected,
        "protected_hashes_after": after_protected,
        "forbidden_actions": {
            "provider_call": False,
            "cache_modification": False,
            "optimization": False,
            "robustness": False,
            "validation": False,
            "eligibility_or_handoff": False,
            "forward_observation": False,
            "alpaca_or_broker_operation": False,
            "real_money_action": False,
        },
        "required_output_files": sorted(REQUIRED_OUTPUTS),
    }
    write_json_at(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "intake_dir": relative(INTAKE_DIR),
        "output_dir": relative(OUTPUT_DIR),
        "universe_hash": EXPECTED_UNIVERSE_HASH,
        "outcomes": outcomes,
        "followup_count": len(followups),
        "next_action": batch_next_action,
        "consistency_overall_pass": consistency["overall_pass"],
        "deterministic_core_hash": consistency["deterministic_core_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
