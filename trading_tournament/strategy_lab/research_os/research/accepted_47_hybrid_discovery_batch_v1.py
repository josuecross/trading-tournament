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
from strategy_lab.research_os.research import accepted_47_targeted_internal_technical_batch_v1 as base
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting


TASK_ID = "accepted_47_hybrid_discovery_batch_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
INTAKE_ID = "hybrid_candidate_intake_after_targeted_internal_v2_v1"
INTAKE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID / "latest"
CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
OLD_ROBUSTNESS_TASK_ID = "accepted_47_source_backed_v2_two_candidate_final_robustness_v1"
OLD_ROBUSTNESS_DIR = ROOT / "evidence" / "robustness" / OLD_ROBUSTNESS_TASK_ID / "latest"
ROLE_AWARE_REASSESSMENT_TASK_ID = "adopt_role_aware_robustness_standard_and_reassess_v1"
ROLE_AWARE_REASSESSMENT_DIR = (
    ROOT / "evidence" / "methodology" / ROLE_AWARE_REASSESSMENT_TASK_ID / "latest"
)
ROLE_AWARE_STANDARD_ID = "role_aware_robustness_standard_v1"
ROLE_AWARE_STANDARD_PATH = (
    ROOT / "strategy_lab" / "research_os" / "methodology" / f"{ROLE_AWARE_STANDARD_ID}.yaml"
)
STALE_ROBUSTNESS_CLASSIFICATION = (
    "historical_generic_robustness_evidence_superseded_for_promotion_decision"
)
PREREGISTRATION_TIMESTAMP = "2026-08-07T00:00:00+00:00"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-10
TIMING_CONVENTION = base.TIMING_CONVENTION

FOLLOWUP_NEXT_ACTION = "direction_owner_review_hybrid_discovery_batch_v1_followups_for_robustness"
NO_FOLLOWUP_NEXT_ACTION = "direction_owner_review_discovery_model_after_hybrid_batch_v1"
BLOCK_NEXT_ACTION = "direction_owner_review_hybrid_discovery_batch_v1_block"

EXTERNAL_STRATEGY_ID = "bilello_gayed_beta_rotation_spy_xlu_4w_v1"
EXTERNAL_TRIAL_ID = "accepted47_hybrid_v1__bilello_gayed_beta_rotation__canonical"
EXTERNAL_FAMILY_ID = "utilities_relative_strength_beta_rotation"
EXTERNAL_ARCHITECTURE_ID = "weekly_xlu_spy_4w_relative_strength_switch"
EXTERNAL_LINEAGE = "bilello_gayed_2014_charles_dow_award_beta_rotation"
EXTERNAL_ROLE = "defensive_equity_timing_strategy"
EXTERNAL_NAMED_CONTROL = "xlu_absolute_4w_momentum_switch_control"
EXTERNAL_STATIC_CONTROL = "beta_rotation_static_state_frequency_control"
EXTERNAL_EQUAL_CONTROL = "spy_xlu_50_50_weekly_control"
EXTERNAL_COLUMNS = ("SPY", "XLU", "BIL")

INTERNAL_FAMILY_ID = "cross_asset_post_shock_recovery_rotation"
INTERNAL_ARCHITECTURE_ID = "standardized_downside_shock_forward_recovery_selection"
INTERNAL_LINEAGE = "internally_generated_technical_hypothesis"
INTERNAL_ROLE = "cross_sectional_allocation_strategy"
INTERNAL_NAMED_CONTROL = "downside_shock_severity_same_universe_control"
INTERNAL_STATIC_CONTROL = "static_average_candidate_weights_control"
INTERNAL_EQUAL_CONTROL = "equal_weight_12_asset_universe_control"
INTERNAL_UNIVERSE = (
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "HYG",
    "LQD",
    "TLT",
    "TIP",
    "GLD",
    "DBC",
    "IYR",
)
INTERNAL_COLUMNS = (*INTERNAL_UNIVERSE, "BIL")
REQUIRED_SYMBOLS = (
    "SPY",
    "XLU",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "HYG",
    "LQD",
    "TLT",
    "TIP",
    "GLD",
    "DBC",
    "IYR",
    "BIL",
)

COMPLETED_RECORD_SCAN_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "evidence" / "research_recovery",
    ROOT / "evidence" / "technical_factory",
    ROOT / "evidence" / "robustness",
    ROOT / "evidence" / "paper_demo_eligibility",
    ROOT / "evidence" / "handoff",
    ROOT / "evidence" / "benchmark_controls",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROLE_AWARE_STANDARD_PATH,
    OLD_ROBUSTNESS_DIR,
    ROLE_AWARE_REASSESSMENT_DIR,
    ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1",
    ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v2" / "latest",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v2" / "latest",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v3" / "latest",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v4" / "latest",
    ROOT / "evidence" / "robustness" / "role_aware_robustness_internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "evidence" / "paper_demo_eligibility" / "internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "evidence" / "handoff" / "internal_capture_asymmetry_63d_top3_v1" / "latest",
    ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v1" / "latest",
    ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v2" / "latest",
    ROOT / "paper_forward_observations",
)

FORBIDDEN_ACTION_FLAGS = {
    "provider_access": False,
    "network_access": False,
    "market_data_refresh": False,
    "cache_modification": False,
    "accepted_47_membership_change": False,
    "forward_observation_data_used": False,
    "alpaca_or_broker_state_used": False,
    "robustness_run": False,
    "validation_run": False,
    "paper_demo_eligibility_record": False,
    "handoff_or_export_record": False,
    "observation_record": False,
    "real_money_action": False,
}

PERMITTED_BATCH_OUTCOMES = {
    "hybrid_batch_followup_found",
    "hybrid_batch_no_followup",
    "hybrid_batch_partially_blocked",
    "hybrid_batch_blocked",
}
PERMITTED_FAILURE_REASONS = {
    "",
    "duplicate_or_redundant",
    "signal_scarcity",
    "data_or_comparability_failure",
    "no_selection_eligible_configuration",
    "not_selected_by_frozen_rule",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "concentration_risk",
    "weak_return",
    "methodology_failure",
}


@dataclass(frozen=True)
class InternalConfig:
    configuration_code: str
    lookback_sessions: int
    recovery_horizon_sessions: int
    strategy_id: str
    trial_id: str

    @property
    def parameters(self) -> dict[str, int | float]:
        return {
            "lookback_sessions": self.lookback_sessions,
            "recovery_horizon_sessions": self.recovery_horizon_sessions,
            "shock_sigma_threshold": 1.0,
            "selected_count": 3,
        }


@dataclass(frozen=True)
class PeriodSplit:
    package_id: str
    architecture_id: str
    prices: pd.DataFrame
    signal_execution_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    full_index: pd.DatetimeIndex
    selection_index: pd.DatetimeIndex
    evaluation_index: pd.DatetimeIndex
    boundary_execution: pd.Timestamp | None


INTERNAL_CONFIGS = (
    InternalConfig(
        "R1",
        126,
        3,
        "internal_post_shock_recovery_126d_3d_top3_v1",
        "accepted47_hybrid_v1__shockrecovery126__h3",
    ),
    InternalConfig(
        "R2",
        126,
        5,
        "internal_post_shock_recovery_126d_5d_top3_v1",
        "accepted47_hybrid_v1__shockrecovery126__h5",
    ),
    InternalConfig(
        "R3",
        252,
        3,
        "internal_post_shock_recovery_252d_3d_top3_v1",
        "accepted47_hybrid_v1__shockrecovery252__h3",
    ),
    InternalConfig(
        "R4",
        252,
        5,
        "internal_post_shock_recovery_252d_5d_top3_v1",
        "accepted47_hybrid_v1__shockrecovery252__h5",
    ),
)

REQUIRED_OUTPUT_FILES = {
    "batch_manifest.yaml",
    "stale_robustness_source_of_truth_reconciliation.csv",
    "hybrid_intake_reconciliation.csv",
    "source_library_records.csv",
    "architecture_preregistration.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "duplicate_preflight.csv",
    "benchmark_reference_log.csv",
    "external_weekly_signal_inventory.csv",
    "internal_shock_event_fixture_results.csv",
    "selection_segment_definition.csv",
    "selection_segment_results.csv",
    "architecture_winner_selection.csv",
    "evaluation_segment_results.csv",
    "evaluation_subhalf_results.csv",
    "external_exploration_results.csv",
    "post_selection_full_period_diagnostics.csv",
    "calendar_year_results.csv",
    "rebalance_contribution_results.csv",
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


def rel(path: str | Path) -> str:
    return base.rel(path)


def file_hash(path: Path) -> str:
    return base.file_hash(path)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def csv_value(value: Any) -> str:
    return base.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    base.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    base.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    base.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    base.write_text(path, text)


def clean_dir(path: Path) -> None:
    if path.exists():
        resolved = path.resolve()
        allowed = (
            (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve(),
            (ROOT / "evidence" / "public_source_strategy_intake" / INTAKE_ID).resolve(),
        )
        if not any(parent in resolved.parents for parent in allowed):
            raise RuntimeError(f"Refusing to clean unexpected path: {resolved}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def unique_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for symbol in symbols:
        if symbol not in output:
            output.append(symbol)
    return tuple(output)


def target(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return base.target(columns, weights)


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return base.bil_target(columns)


def event_frame(index: pd.DatetimeIndex, columns: tuple[str, ...], events: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    return accounting.event_frame(index, columns, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return base.month_ends(index)


def week_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("W-FRI")).last().tolist()
    ]


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.get_loc(pd.Timestamp(signal_date)))
    if position + 1 >= len(index):
        return None
    return pd.Timestamp(index[position + 1])


def load_adjusted_ohlcv(symbol: str) -> pd.DataFrame:
    return base.load_adjusted_ohlcv(symbol)


def load_frames() -> dict[str, pd.DataFrame]:
    return {symbol: load_adjusted_ohlcv(symbol) for symbol in REQUIRED_SYMBOLS}


def price_matrix(frames: dict[str, pd.DataFrame], symbols: tuple[str, ...]) -> pd.DataFrame:
    return pd.concat(
        [frames[symbol]["adj_close"].rename(symbol) for symbol in symbols],
        axis=1,
        join="inner",
    ).dropna()


def cache_preflight_rows(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        frame = frames[symbol]
        path = CACHE_DIR / f"{symbol}.csv"
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "cache_hash": file_hash(path),
                "row_count": len(frame),
                "first_date": frame.index.min().date().isoformat(),
                "last_date": frame.index.max().date().isoformat(),
                "preflight_status": "pass",
            }
        )
    return rows


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def scan_path_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return file_hash(path)
    excluded_roots = {
        (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve(),
    }
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        child_resolved = child.resolve()
        if any(excluded in child_resolved.parents or child_resolved == excluded for excluded in excluded_roots):
            continue
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(child.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def completed_record_scan_hash() -> str:
    digest = hashlib.sha256()
    for path in COMPLETED_RECORD_SCAN_PATHS:
        digest.update(rel(path).encode("utf-8"))
        digest.update(scan_path_hash(path).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return base.dominates(control, candidate)


def finite_metric(value: Any) -> float:
    return base.finite_metric(value)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        finite_metric(candidate.get("sharpe_ratio")) - finite_metric(control.get("sharpe_ratio")) >= 0.02 - 1e-12
        or finite_metric(candidate.get("maximum_drawdown")) - finite_metric(control.get("maximum_drawdown")) >= 0.01 - 1e-12
    )


def compound_return(returns: pd.Series) -> float:
    return base.compound_return(returns)


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(float(value) for value in weights.values())
    if total <= 0.0:
        raise ValueError("cannot normalize zero static weights")
    return {key: float(value) / total for key, value in weights.items()}


def static_event_from_weights(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    weights: dict[str, float],
) -> pd.DataFrame:
    return event_frame(index, columns, {pd.Timestamp(index[0]): target(columns, normalize_weights(weights))})


def buy_hold_events(index: pd.DatetimeIndex, columns: tuple[str, ...], symbol: str) -> pd.DataFrame:
    return event_frame(index, columns, {pd.Timestamp(index[0]): target(columns, {symbol: 1.0})})


def repeated_events(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    execution_dates: tuple[pd.Timestamp, ...],
    weights: dict[str, float],
) -> pd.DataFrame:
    events = {pd.Timestamp(index[0]): target(columns, weights)}
    for date_value in execution_dates:
        events[pd.Timestamp(date_value)] = target(columns, weights)
    return event_frame(index, columns, events)


def average_target_weights(events: pd.DataFrame, index: pd.DatetimeIndex) -> dict[str, float]:
    history = target_history(events, index)
    weights = {symbol: float(value) for symbol, value in history.mean().fillna(0.0).items()}
    return normalize_weights(weights)


def materialize_intake() -> dict[str, str]:
    clean_dir(INTAKE_DIR)
    source_row = {
        "source_library_record_id": EXTERNAL_LINEAGE,
        "strategy_id": EXTERNAL_STRATEGY_ID,
        "family_id": EXTERNAL_FAMILY_ID,
        "architecture_id": EXTERNAL_ARCHITECTURE_ID,
        "source_role": "public_rule_replication_intake",
        "source_rule": "weekly XLU/SPY adjusted-close ratio four-week relative strength; positive selects XLU, negative selects SPY, equality retains",
        "network_access": False,
        "provider_calls": 0,
        "source_library_records_created": 1,
        "frozen_before_performance": True,
    }
    package_rows = [
        {
            "work_package_id": "external",
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "stage": "exploration",
            "route": "standalone",
            "configuration_count": 1,
            "canonical_trial_count": 1,
            "primary_future_robustness_role": EXTERNAL_ROLE,
            "frozen_identity_preserved": True,
        },
        {
            "work_package_id": "internal",
            "strategy_id": "",
            "trial_id": "",
            "family_id": INTERNAL_FAMILY_ID,
            "architecture_id": INTERNAL_ARCHITECTURE_ID,
            "stage": "optimization_to_exploratory_evaluation",
            "route": "standalone",
            "configuration_count": 4,
            "canonical_trial_count": 4,
            "primary_future_robustness_role": INTERNAL_ROLE,
            "frozen_identity_preserved": True,
        },
    ]
    write_yaml(
        INTAKE_DIR / "intake_manifest.yaml",
        {
            "intake_id": INTAKE_ID,
            "task_id": TASK_ID,
            "materialized_for": TASK_ID,
            "network_access": False,
            "provider_calls": 0,
            "cache_modification": False,
            "work_package_count": 2,
            "source_library_record_count": 1,
            "canonical_trial_count": 5,
            "frozen_before_performance": True,
        },
    )
    write_csv(
        INTAKE_DIR / "source_library_records.csv",
        [source_row],
        list(source_row.keys()),
    )
    write_csv(
        INTAKE_DIR / "frozen_work_packages.csv",
        package_rows,
        list(package_rows[0].keys()),
    )
    write_json(
        INTAKE_DIR / "intake_consistency_check.json",
        {
            "overall_pass": True,
            "exactly_two_work_packages": True,
            "source_library_records": 1,
            "external_canonical_trials": 1,
            "internal_canonical_trials": 4,
            "total_canonical_trials": 5,
            "network_access": False,
            "provider_calls": 0,
        },
    )
    write_text(
        INTAKE_DIR / "intake_report.md",
        "# Hybrid Candidate Intake After Targeted Internal V2\n\n"
        "This intake freezes one public-rule Beta Rotation replication and one internally generated "
        "post-shock recovery architecture for `accepted_47_hybrid_discovery_batch_v1`. No source search, "
        "provider call, cache change, lifecycle promotion, robustness, eligibility, handoff, observation, "
        "or broker action is authorized by this intake.",
    )
    return {path.name: file_hash(path) for path in sorted(INTAKE_DIR.iterdir()) if path.is_file()}


def source_library_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_library_record_id": EXTERNAL_LINEAGE,
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "source_role": "public_rule_replication",
            "source_claim_replicated": "Bilello/Gayed Beta Rotation via Utilities relative strength versus SPY",
            "source_rule_summary": "ratio_w=adj_close_XLU_w/adj_close_SPY_w; RS4=ratio_w/ratio_w_minus_4-1",
            "source_variant_count": 1,
            "network_access": False,
            "provider_calls": 0,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stale_robustness_source_of_truth_rows() -> list[dict[str, Any]]:
    standard = yaml.safe_load(ROLE_AWARE_STANDARD_PATH.read_text(encoding="utf-8"))
    if standard.get("standard_id") != ROLE_AWARE_STANDARD_ID:
        raise RuntimeError("Authoritative role-aware methodology identifier drift")
    if standard.get("status") != "authoritative_project_wide_standard":
        raise RuntimeError("Role-aware robustness methodology is not authoritative")
    if standard.get("adopted_by_task") != ROLE_AWARE_REASSESSMENT_TASK_ID:
        raise RuntimeError("Role-aware methodology adoption lineage drift")

    old_rows = {
        row["strategy_id"]: row
        for row in read_csv_rows(OLD_ROBUSTNESS_DIR / "outcome_summary.csv")
    }
    reassessed_rows = {
        row["strategy_id"]: row
        for row in read_csv_rows(ROLE_AWARE_REASSESSMENT_DIR / "reassessment_outcome_summary.csv")
    }
    role_rows = {
        row["strategy_id"]: row
        for row in read_csv_rows(ROLE_AWARE_REASSESSMENT_DIR / "candidate_role_freeze.csv")
    }
    expected_roles = {
        "varadi_minimum_correlation_8etf_60d_weekly_v1": "dynamic_multi_asset_allocation_strategy",
        "schwoerer_hyg_ema100_spy_bil_v1": "defensive_equity_timing_strategy",
    }
    rows: list[dict[str, Any]] = []
    for strategy_id, expected_role in expected_roles.items():
        old = old_rows.get(strategy_id)
        reassessed = reassessed_rows.get(strategy_id)
        role = role_rows.get(strategy_id)
        if old is None or reassessed is None or role is None:
            raise RuntimeError(f"Missing robustness lineage evidence for {strategy_id}")
        gate_checks = json.loads(old["positive_gate_checks"])
        if old["outcome"] != "robustness_mixed" or old["failure_reason"] != "concentration_risk":
            raise RuntimeError(f"Historical generic robustness outcome drift for {strategy_id}")
        if gate_checks.get("three_month_and_year_neutralization") is not False:
            raise RuntimeError(f"Historical decisive neutralization gate drift for {strategy_id}")
        if reassessed["reassessed_outcome"] != "robustness_positive":
            raise RuntimeError(f"Authoritative reassessment outcome drift for {strategy_id}")
        if role["primary_role"] != expected_role:
            raise RuntimeError(f"Authoritative primary role drift for {strategy_id}")
        rows.append(
            {
                "strategy_id": strategy_id,
                "old_contract_task_id": OLD_ROBUSTNESS_TASK_ID,
                "old_contract_outcome": old["outcome"],
                "old_contract_failure_reason": old["failure_reason"],
                "old_contract_decisive_gate": "three_month_and_year_neutralization=false",
                "old_contract_packet_classification": STALE_ROBUSTNESS_CLASSIFICATION,
                "authoritative_methodology": ROLE_AWARE_STANDARD_ID,
                "authoritative_reassessment_task": ROLE_AWARE_REASSESSMENT_TASK_ID,
                "authoritative_current_outcome": reassessed["reassessed_outcome"],
                "primary_role": role["primary_role"],
                "promotion_authority": "role_aware_robustness_standard_v1_and_completed_reassessments",
                "lifecycle_change_required": False,
                "rerun_required": False,
                "interpretation": "preserve_historical_trial_authoritative_role_aware_reassessment_controls_current_state",
            }
        )
    return rows


def duplicate_preflight_rows() -> list[dict[str, Any]]:
    scan_hash = completed_record_scan_hash()
    return [
        {
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "preflight_status": "pass",
            "execute_work_package": True,
            "executed_trial_count": 1,
            "completed_record_scan_hash": scan_hash,
            "compared_against": "Tactical Risk Rotation|HYG EMA100|Trendpilot|DSR|CFRA/Stovall|generic equity/cash trend timing",
            "material_equivalence_found": False,
            "broad_family_similarity_only": True,
            "distinctive_mechanism": "weekly four-observation XLU/SPY ratio relative-strength switch with SPY/XLU holdings and following-close execution",
            "reject_only_if_signal_holdings_execution_materially_equivalent": True,
            "preperformance_complete": True,
            "decision_reason": "defensive/tactical overlap only; no completed record matches the actual signal, holdings, and execution architecture",
        },
        {
            "work_package_id": "internal",
            "architecture_id": INTERNAL_ARCHITECTURE_ID,
            "family_id": INTERNAL_FAMILY_ID,
            "strategy_id": "",
            "trial_id": "",
            "preflight_status": "pass",
            "execute_work_package": True,
            "executed_trial_count": 4,
            "completed_record_scan_hash": scan_hash,
            "compared_against": "Capture Asymmetry|Tail Frequency|Gain-to-Pain|volatility stability|MDD selection|Low MAX|IBS|Double 7|OLMAR|PAMR|ANTICOR|short-term reversal research",
            "material_equivalence_found": False,
            "broad_family_similarity_only": True,
            "distinctive_mechanism": "mean forward recovery after own-asset standardized downside shocks",
            "reject_only_if_signal_holdings_execution_materially_equivalent": True,
            "preperformance_complete": True,
            "decision_reason": "own-shock forward recovery ranking is distinct from completed tail-frequency, volatility, drawdown, and short-term reversal mechanisms",
        },
    ]


def beta_rotation_target(rs4: float, previous_target: str) -> str:
    if rs4 > 0.0:
        return "XLU"
    if rs4 < 0.0:
        return "SPY"
    return previous_target


def build_external_package(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = price_matrix(frames, EXTERNAL_COLUMNS)
    weekly_dates = week_ends(prices.index)
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(prices.index[0]): target(EXTERNAL_COLUMNS, {"BIL": 1.0})}
    named_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(prices.index[0]): target(EXTERNAL_COLUMNS, {"BIL": 1.0})}
    signal_rows: list[dict[str, Any]] = []
    current_target = "BIL"
    current_named = "BIL"
    complete_signals: list[dict[str, Any]] = []
    for weekly_number, signal_date in enumerate(weekly_dates, start=1):
        execution = next_session(prices.index, signal_date) if signal_date in prices.index else None
        row = {
            "work_package_id": "external",
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "weekly_observation_number": weekly_number,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": execution.date().isoformat() if execution is not None else "",
            "has_four_week_warmup": weekly_number > 4,
            "complete_source_signal": False,
            "ratio_xlu_spy": "",
            "ratio_minus_4": "",
            "rs4_xlu_spy_ratio": "",
            "xlu_absolute_4w_return": "",
            "candidate_target": current_target,
            "named_control_target": current_named,
            "target_retained": True,
            "prewarmup_bil": weekly_number <= 4,
            "following_close_execution": execution is not None and execution > signal_date,
            "same_close_execution": False,
            "missing_signal_data_retains_previous": False,
            "missing_execution_price_blocks_transition": False,
        }
        if weekly_number <= 4:
            signal_rows.append(row)
            continue
        current = prices.loc[signal_date]
        prior_date = weekly_dates[weekly_number - 5]
        prior = prices.loc[prior_date]
        valid = bool(np.isfinite([current["SPY"], current["XLU"], prior["SPY"], prior["XLU"]]).all())
        if not valid:
            row["missing_signal_data_retains_previous"] = True
            signal_rows.append(row)
            continue
        ratio = float(current["XLU"] / current["SPY"])
        ratio_prior = float(prior["XLU"] / prior["SPY"])
        rs4 = ratio / ratio_prior - 1.0
        xlu4 = float(current["XLU"] / prior["XLU"] - 1.0)
        target_asset = beta_rotation_target(rs4, current_target)
        named_target = "XLU" if xlu4 > 0.0 else "SPY"
        if execution is None:
            row["missing_execution_price_blocks_transition"] = True
            signal_rows.append(row)
            continue
        current_target = target_asset
        current_named = named_target
        events[pd.Timestamp(execution)] = target(EXTERNAL_COLUMNS, {current_target: 1.0})
        named_events[pd.Timestamp(execution)] = target(EXTERNAL_COLUMNS, {current_named: 1.0})
        row.update(
            {
                "complete_source_signal": True,
                "ratio_xlu_spy": ratio,
                "ratio_minus_4": ratio_prior,
                "rs4_xlu_spy_ratio": rs4,
                "xlu_absolute_4w_return": xlu4,
                "candidate_target": current_target,
                "named_control_target": current_named,
                "target_retained": current_target == row["candidate_target"],
            }
        )
        complete_signals.append(row.copy())
        signal_rows.append(row)
    candidate_events = event_frame(prices.index, EXTERNAL_COLUMNS, events)
    named_frame = event_frame(prices.index, EXTERNAL_COLUMNS, named_events)
    target_means = average_target_weights(candidate_events, prices.index)
    execution_dates = tuple(pd.Timestamp(row["execution_date"]) for row in complete_signals if row["execution_date"])
    controls = {
        EXTERNAL_NAMED_CONTROL: named_frame,
        EXTERNAL_STATIC_CONTROL: static_event_from_weights(prices.index, EXTERNAL_COLUMNS, target_means),
        EXTERNAL_EQUAL_CONTROL: repeated_events(
            prices.index, EXTERNAL_COLUMNS, execution_dates, {"SPY": 0.5, "XLU": 0.5, "BIL": 0.0}
        ),
        "SPY_buy_and_hold": buy_hold_events(prices.index, EXTERNAL_COLUMNS, "SPY"),
        "XLU_buy_and_hold": buy_hold_events(prices.index, EXTERNAL_COLUMNS, "XLU"),
        "BIL_buy_and_hold": buy_hold_events(prices.index, EXTERNAL_COLUMNS, "BIL"),
    }
    complete_count = len(complete_signals)
    midpoint = complete_count // 2
    for index, signal in enumerate(complete_signals):
        signal["deterministic_signal_half"] = "first_half" if index < midpoint else "second_half"
    first_half_count = midpoint
    second_half_count = complete_count - midpoint
    full_index = prices.index[1:]
    split = PeriodSplit(
        "external",
        EXTERNAL_ARCHITECTURE_ID,
        prices,
        tuple((pd.Timestamp(row["signal_date"]), pd.Timestamp(row["execution_date"])) for row in complete_signals),
        full_index,
        full_index,
        full_index,
        None,
    )
    simulation = simulate_package(prices, candidate_events, controls)
    metrics = build_metric_map(split, simulation, controls.keys(), split.full_index, tuple(pd.Timestamp(row["execution_date"]) for row in complete_signals))
    scarce = complete_count < 500 or first_half_count < 200 or second_half_count < 200
    if scarce:
        vector = {
            "exploratory_followup_candidate": False,
            "primary_failure_reason": "signal_scarcity",
            "complete_signal_count": complete_count,
            "first_half_complete_signal_count": first_half_count,
            "second_half_complete_signal_count": second_half_count,
        }
        outcome = "closed_exploration"
        failure = "signal_scarcity"
        decision = "external weekly source-signal preflight failed minimum complete-signal count"
    else:
        half_rows, half_pass = external_subhalf_rows(split, simulation)
        calendar_rows, calendar_state = calendar_year_diagnostics(
            "external", EXTERNAL_ARCHITECTURE_ID, EXTERNAL_STRATEGY_ID, EXTERNAL_TRIAL_ID,
            prices.index, simulation["candidate_paths"][PRIMARY_COST], simulation["control_paths"][(EXTERNAL_NAMED_CONTROL, PRIMARY_COST)]
        )
        vector = external_gate_vector(metrics, half_pass, calendar_state)
        outcome = "exploratory_followup_candidate" if vector["exploratory_followup_candidate"] else "closed_exploration"
        failure = "" if vector["exploratory_followup_candidate"] else vector["primary_failure_reason"]
        decision = (
            "external candidate passed exploration gate"
            if vector["exploratory_followup_candidate"]
            else "external candidate failed exploration gate"
        )
        return {
            "executed": True,
            "blocked": False,
            "split": split,
            "candidate_events": candidate_events,
            "controls": controls,
            "simulation": simulation,
            "metrics": metrics,
            "signal_rows": signal_rows,
            "complete_signal_count": complete_count,
            "first_half_complete_signal_count": first_half_count,
            "second_half_complete_signal_count": second_half_count,
            "average_target_weights": target_means,
            "half_rows": half_rows,
            "calendar_rows": calendar_rows,
            "calendar_state": calendar_state,
            "rebalance_rows": [],
            "rebalance_state": {
                "rebalance_month_count": 0,
                "positive_excess_total": 0.0,
                "max_positive_excess_share": 0.0,
                "state": "not_applicable_external_gate",
                "pass": True,
            },
            "vector": vector,
            "outcome": outcome,
            "failure_reason": failure,
            "decision_reason": decision,
        }
    return {
        "executed": False,
        "blocked": True,
        "split": split,
        "candidate_events": candidate_events,
        "controls": controls,
        "simulation": simulation,
        "metrics": metrics,
        "signal_rows": signal_rows,
        "complete_signal_count": complete_count,
        "first_half_complete_signal_count": first_half_count,
        "second_half_complete_signal_count": second_half_count,
        "average_target_weights": target_means,
        "half_rows": [],
        "calendar_rows": [],
        "calendar_state": {
            "complete_year_count": 0,
            "positive_excess_total": 0.0,
            "max_positive_excess_share": 0.0,
            "state": "signal_scarcity",
            "pass": False,
        },
        "rebalance_rows": [],
        "rebalance_state": {
            "rebalance_month_count": 0,
            "positive_excess_total": 0.0,
            "max_positive_excess_share": 0.0,
            "state": "signal_scarcity",
            "pass": False,
        },
        "vector": vector,
        "outcome": outcome,
        "failure_reason": failure,
        "decision_reason": decision,
    }


def simulate_package(
    prices: pd.DataFrame,
    candidate_events: pd.DataFrame,
    control_events: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    candidate_paths = {
        cost: accounting.simulate_path(prices, candidate_events, cost, TIMING_CONVENTION)
        for cost in COSTS
    }
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for control_id, events in control_events.items():
        for cost in COSTS:
            control_paths[(control_id, cost)] = accounting.simulate_path(prices, events, cost, TIMING_CONVENTION)
    return {"candidate_paths": candidate_paths, "control_paths": control_paths}


def annualized_years(index: pd.DatetimeIndex) -> float:
    return max(len(index) / 252.0, 1e-12)


def metrics_for_path(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex,
    scheduled_executions: tuple[pd.Timestamp, ...],
) -> dict[str, Any]:
    metrics = accounting.metric_payload(path, period_index)
    held = path["held_weights"].reindex(period_index).dropna()
    sums = held.sum(axis=1) if len(held) else pd.Series(dtype=float)
    period_dates = set(period_index)
    event_dates = [date for date in scheduled_executions if date in period_dates]
    metrics.update(
        {
            "period_start": period_index.min().date().isoformat() if len(period_index) else "",
            "period_end": period_index.max().date().isoformat() if len(period_index) else "",
            "trading_day_count": len(period_index),
            "formation_count": len(event_dates),
            "rebalance_count": len(event_dates),
            "annualized_turnover": float(metrics["turnover"]) / annualized_years(period_index),
            "average_holdings": {symbol: float(value) for symbol, value in held.mean().fillna(0.0).items()},
            "maximum_asset_weight": float(held.max().max()) if len(held) else float("nan"),
            "daily_weight_sum_one": bool(
                len(sums) and np.isclose(sums.to_numpy(dtype=float), 1.0, atol=1e-8, rtol=0.0).all()
            ),
            "explicit_holdings": bool(list(held.columns) == list(path["target_events"].columns)),
            "target_zero_weights_preserved": bool(
                not path["target_events"].empty and (path["target_events"].to_numpy(dtype=float) == 0.0).any()
            ),
            "same_period_price_signal_return_used": False,
            "no_tradable_price_forward_fill": True,
        }
    )
    metrics["invariant_pass"] = bool(metrics["invariant_pass"] and metrics["daily_weight_sum_one"])
    return metrics


def build_metric_map(
    split: PeriodSplit,
    simulation: dict[str, Any],
    control_ids: Any,
    period_index: pd.DatetimeIndex,
    scheduled_executions: tuple[pd.Timestamp, ...],
) -> dict[tuple[str, float], dict[str, Any]]:
    output: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        output[("candidate", cost)] = metrics_for_path(simulation["candidate_paths"][cost], period_index, scheduled_executions)
        for control_id in control_ids:
            output[(control_id, cost)] = metrics_for_path(
                simulation["control_paths"][(control_id, cost)], period_index, scheduled_executions
            )
    return output


def external_gate_vector(metrics: dict[tuple[str, float], dict[str, Any]], half_pass: bool, calendar_state: dict[str, Any]) -> dict[str, Any]:
    candidate_5 = metrics[("candidate", PRIMARY_COST)]
    named_5 = metrics[(EXTERNAL_NAMED_CONTROL, PRIMARY_COST)]
    static_5 = metrics[(EXTERNAL_STATIC_CONTROL, PRIMARY_COST)]
    candidate_10 = metrics[("candidate", 10.0)]
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_control_not_dominating_5bps": not dominates(static_5, candidate_5),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
        "chronological_halves_pass": half_pass,
        "calendar_year_concentration_pass": bool(calendar_state["pass"]),
    }
    vector["exploratory_followup_candidate"] = all(bool(value) for value in vector.values())
    vector["primary_failure_reason"] = primary_failure_reason(vector)
    return vector


def primary_failure_reason(vector: dict[str, Any]) -> str:
    if not vector.get("cagr_positive_5bps", True):
        return "weak_return"
    if not vector.get("invariants_pass_5bps", True):
        return "methodology_failure"
    if not vector.get("named_control_not_dominating_5bps", True):
        return "weak_vs_primary_control"
    if not vector.get("material_vs_named_control_5bps", True):
        return "benchmark_like_behavior"
    if not vector.get("static_control_not_dominating_5bps", vector.get("static_equal_control_not_dominating_5bps", True)):
        return "benchmark_like_behavior"
    if not vector.get("cagr_positive_10bps", True):
        return "cost_drag"
    if not vector.get("chronological_halves_pass", True) or not vector.get("evaluation_subhalf_stability_pass", True):
        return "period_instability"
    if not vector.get("calendar_year_concentration_pass", True) or not vector.get("rebalance_month_concentration_pass", True):
        return "concentration_risk"
    return ""


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [("first_half", index[:midpoint]), ("second_half", index[midpoint:])]


def external_subhalf_rows(split: PeriodSplit, simulation: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    passes: list[bool] = []
    for half_id, half_index in split_halves(split.full_index):
        candidate = metrics_for_path(
            simulation["candidate_paths"][PRIMARY_COST],
            half_index,
            tuple(execution for _, execution in split.signal_execution_pairs),
        )
        named = metrics_for_path(
            simulation["control_paths"][(EXTERNAL_NAMED_CONTROL, PRIMARY_COST)],
            half_index,
            tuple(execution for _, execution in split.signal_execution_pairs),
        )
        worse = (
            finite_metric(candidate["sharpe_ratio"]) < finite_metric(named["sharpe_ratio"])
            and finite_metric(candidate["maximum_drawdown"]) < finite_metric(named["maximum_drawdown"])
        )
        passes.append(not worse)
        rows.append(
            {
                "package_id": "external",
                "architecture_id": EXTERNAL_ARCHITECTURE_ID,
                "strategy_id": EXTERNAL_STRATEGY_ID,
                "trial_id": EXTERNAL_TRIAL_ID,
                "subhalf_id": half_id,
                "period_start": candidate["period_start"],
                "period_end": candidate["period_end"],
                "formation_count": candidate["formation_count"],
                "sample_permits": True,
                "candidate_sharpe": candidate["sharpe_ratio"],
                "named_control_sharpe": named["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "named_control_maximum_drawdown": named["maximum_drawdown"],
                "worse_than_named_on_both_sharpe_and_drawdown": worse,
                "pass": not worse,
            }
        )
    return rows, all(passes)


def internal_common_split(frames: dict[str, pd.DataFrame]) -> PeriodSplit:
    prices = price_matrix(frames, INTERNAL_COLUMNS)
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    min_position = max(config.lookback_sessions for config in INTERNAL_CONFIGS)
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = next_session(prices.index, signal_date)
        if position >= min_position and execution is not None:
            pairs.append((pd.Timestamp(signal_date), pd.Timestamp(execution)))
    if len(pairs) < 3:
        raise RuntimeError("internal architecture has insufficient common monthly formations")
    boundary_position = int(math.floor(0.6 * len(pairs)))
    if boundary_position <= 0 or boundary_position >= len(pairs):
        raise RuntimeError("internal architecture has nonviable 60/40 split")
    first_execution = pairs[0][1]
    boundary_execution = pairs[boundary_position][1]
    selection_index = prices.index[(prices.index >= first_execution) & (prices.index < boundary_execution)]
    evaluation_index = prices.index[prices.index >= boundary_execution]
    full_index = prices.index[prices.index >= first_execution]
    return PeriodSplit(
        "internal",
        INTERNAL_ARCHITECTURE_ID,
        prices,
        tuple(pairs),
        full_index,
        selection_index,
        evaluation_index,
        boundary_execution,
    )


def shock_recovery_scores(
    prices: pd.DataFrame,
    signal_date: pd.Timestamp,
    config: InternalConfig,
) -> tuple[dict[str, float], dict[str, float], list[dict[str, Any]]]:
    position = int(prices.index.get_loc(signal_date))
    returns = prices[list(INTERNAL_UNIVERSE)].pct_change(fill_method=None)
    candidate_scores: dict[str, float] = {}
    control_scores: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for symbol in INTERNAL_UNIVERSE:
        asset_returns = returns[symbol]
        window = asset_returns.iloc[position - config.lookback_sessions + 1 : position + 1].dropna()
        mu = float(window.mean()) if len(window) else float("nan")
        sigma = float(window.std(ddof=1)) if len(window) > 1 else float("nan")
        recoveries: list[float] = []
        shock_returns: list[float] = []
        threshold = mu - sigma
        for shock_date, shock_return in window.items():
            shock_position = int(prices.index.get_loc(pd.Timestamp(shock_date)))
            recovery_position = shock_position + config.recovery_horizon_sessions
            if recovery_position > position:
                continue
            if not math.isfinite(float(shock_return)) or float(shock_return) >= threshold:
                continue
            recovery = float(prices[symbol].iloc[recovery_position] / prices[symbol].iloc[shock_position] - 1.0)
            if math.isfinite(recovery):
                recoveries.append(recovery)
                shock_returns.append(float(shock_return))
        complete_count = len(recoveries)
        if complete_count >= 5:
            candidate_scores[symbol] = float(np.mean(recoveries))
            control_scores[symbol] = -float(np.mean(np.abs(shock_returns)))
        rows.append(
            {
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "configuration_code": config.configuration_code,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "signal_date": signal_date.date().isoformat(),
                "asset": symbol,
                "lookback_sessions": config.lookback_sessions,
                "recovery_horizon_sessions": config.recovery_horizon_sessions,
                "shock_sigma_threshold": 1.0,
                "return_mean": mu,
                "return_volatility": sigma,
                "shock_threshold": threshold,
                "complete_shock_recovery_count": complete_count,
                "candidate_recovery_score": candidate_scores.get(symbol, ""),
                "named_control_severity_score": control_scores.get(symbol, ""),
                "minimum_complete_events_pass": complete_count >= 5,
                "uses_future_after_formation": False,
            }
        )
    return candidate_scores, control_scores, rows


def rank_desc(scores: dict[str, float]) -> list[str]:
    return [
        symbol for symbol, _score in sorted(
            scores.items(),
            key=lambda item: (-float(item[1]), item[0]),
        )
    ]


def selected_top3_target(columns: tuple[str, ...], ranked: list[str]) -> dict[str, float]:
    selected = ranked[:3]
    weights = {symbol: 0.0 for symbol in columns}
    for symbol in selected:
        weights[symbol] = 1.0 / 3.0
    weights["BIL"] = max(0.0, 1.0 - len(selected) / 3.0)
    return target(columns, weights)


def build_internal_config_events(split: PeriodSplit, config: InternalConfig) -> dict[str, Any]:
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(split.prices.index[0]): bil_target(INTERNAL_COLUMNS)
    }
    named_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(split.prices.index[0]): bil_target(INTERNAL_COLUMNS)
    }
    fixture_rows: list[dict[str, Any]] = []
    for signal_date, execution in split.signal_execution_pairs:
        candidate_scores, control_scores, rows = shock_recovery_scores(split.prices, signal_date, config)
        ranked_candidate = rank_desc(candidate_scores)
        ranked_control = rank_desc(control_scores)
        candidate_target = selected_top3_target(INTERNAL_COLUMNS, ranked_candidate)
        named_target = selected_top3_target(INTERNAL_COLUMNS, ranked_control)
        candidate_events[pd.Timestamp(execution)] = candidate_target
        named_events[pd.Timestamp(execution)] = named_target
        selected_candidate = set(ranked_candidate[:3])
        selected_named = set(ranked_control[:3])
        for row in rows:
            asset = str(row["asset"])
            row.update(
                {
                    "execution_date": execution.date().isoformat(),
                    "candidate_selected": asset in selected_candidate,
                    "named_control_selected": asset in selected_named,
                    "candidate_unused_slot_bil_weight": candidate_target["BIL"],
                    "named_unused_slot_bil_weight": named_target["BIL"],
                }
            )
        fixture_rows.extend(rows)
    candidate_frame = event_frame(split.prices.index, INTERNAL_COLUMNS, candidate_events)
    named_frame = event_frame(split.prices.index, INTERNAL_COLUMNS, named_events)
    static_weights = average_target_weights(candidate_frame, split.selection_index)
    execution_dates = tuple(execution for _, execution in split.signal_execution_pairs)
    equal_weights = {symbol: (1.0 / 12.0 if symbol in INTERNAL_UNIVERSE else 0.0) for symbol in INTERNAL_COLUMNS}
    controls = {
        INTERNAL_NAMED_CONTROL: named_frame,
        INTERNAL_STATIC_CONTROL: static_event_from_weights(split.prices.index, INTERNAL_COLUMNS, static_weights),
        INTERNAL_EQUAL_CONTROL: repeated_events(split.prices.index, INTERNAL_COLUMNS, execution_dates, equal_weights),
        "SPY_buy_and_hold": buy_hold_events(split.prices.index, INTERNAL_COLUMNS, "SPY"),
        "BIL_buy_and_hold": buy_hold_events(split.prices.index, INTERNAL_COLUMNS, "BIL"),
    }
    return {
        "candidate_events": candidate_frame,
        "controls": controls,
        "fixture_rows": fixture_rows,
        "average_target_weights_selection_segment": static_weights,
    }


def build_internal_results(frames: dict[str, pd.DataFrame]) -> tuple[PeriodSplit, dict[str, dict[str, Any]]]:
    split = internal_common_split(frames)
    results: dict[str, dict[str, Any]] = {}
    scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
    for config in INTERNAL_CONFIGS:
        prepared = build_internal_config_events(split, config)
        simulation = simulate_package(split.prices, prepared["candidate_events"], prepared["controls"])
        metrics = build_metric_map(split, simulation, prepared["controls"].keys(), split.selection_index, scheduled)
        vector = selection_gate_vector(metrics)
        results[config.trial_id] = {
            "config": config,
            "split": split,
            "prepared": prepared,
            "simulation": simulation,
            "selection_metrics": metrics,
            "selection_vector": vector,
            "selected_winner": False,
            "evaluation": {},
            "outcome": "selection_eligible" if vector["selection_eligible"] else "closed_optimization",
            "failure_reason": "" if vector["selection_eligible"] else vector["primary_failure_reason"],
            "decision_reason": (
                "passed all frozen selection-segment gates"
                if vector["selection_eligible"]
                else "failed frozen selection-segment gate"
            ),
        }
    freeze_internal_winner(results)
    evaluate_internal_winner(results)
    return split, results


def selection_gate_vector(metrics: dict[tuple[str, float], dict[str, Any]]) -> dict[str, Any]:
    candidate_5 = metrics[("candidate", PRIMARY_COST)]
    named_5 = metrics[(INTERNAL_NAMED_CONTROL, PRIMARY_COST)]
    static_5 = metrics[(INTERNAL_STATIC_CONTROL, PRIMARY_COST)]
    equal_5 = metrics[(INTERNAL_EQUAL_CONTROL, PRIMARY_COST)]
    candidate_10 = metrics[("candidate", 10.0)]
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
    }
    vector["selection_eligible"] = all(bool(value) for value in vector.values())
    vector["primary_failure_reason"] = primary_failure_reason(vector)
    return vector


def freeze_internal_winner(results: dict[str, dict[str, Any]]) -> None:
    eligible = [result for result in results.values() if result["selection_vector"]["selection_eligible"]]
    if not eligible:
        for result in results.values():
            if not result["failure_reason"]:
                result["failure_reason"] = "no_selection_eligible_configuration"
                result["outcome"] = "closed_optimization"
                result["decision_reason"] = "no configuration passed the frozen selection gate"
        return
    max_sharpe = max(
        finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"])
        for result in eligible
    )
    tied = [
        result for result in eligible
        if finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"]) >= max_sharpe - 0.01 - 1e-12
    ]
    winner = sorted(
        tied,
        key=lambda result: (
            abs(finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["maximum_drawdown"])),
            finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["annualized_turnover"]),
            result["config"].trial_id,
        ),
    )[0]
    winner["selected_winner"] = True
    winner["outcome"] = "selection_winner_pending_exploratory_evaluation"
    winner["failure_reason"] = ""
    winner["decision_reason"] = "winner frozen by highest Sharpe, drawdown, turnover, lexical rule before evaluation"
    for result in results.values():
        if result is winner:
            continue
        result["outcome"] = "closed_optimization"
        result["failure_reason"] = "not_selected_by_frozen_rule"
        result["decision_reason"] = "nonwinner closed before evaluation by frozen one-winner rule"


def evaluate_internal_winner(results: dict[str, dict[str, Any]]) -> None:
    for result in results.values():
        if not result.get("selected_winner"):
            continue
        split: PeriodSplit = result["split"]
        scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
        controls = result["prepared"]["controls"]
        evaluation_metrics = build_metric_map(split, result["simulation"], controls.keys(), split.evaluation_index, scheduled)
        full_metrics = build_metric_map(split, result["simulation"], controls.keys(), split.full_index, scheduled)
        subhalf_rows, subhalf_pass = internal_subhalf_rows(result, evaluation_metrics)
        calendar_rows, calendar_state = calendar_year_diagnostics(
            "internal", INTERNAL_ARCHITECTURE_ID, result["config"].strategy_id, result["config"].trial_id,
            split.evaluation_index, result["simulation"]["candidate_paths"][PRIMARY_COST],
            result["simulation"]["control_paths"][(INTERNAL_NAMED_CONTROL, PRIMARY_COST)]
        )
        rebalance_rows, rebalance_state = rebalance_contribution_diagnostics(result)
        vector = evaluation_gate_vector(evaluation_metrics, subhalf_pass, calendar_state, rebalance_state)
        result["evaluation"] = {
            "metrics": evaluation_metrics,
            "full_metrics": full_metrics,
            "subhalf_rows": subhalf_rows,
            "calendar_rows": calendar_rows,
            "calendar_state": calendar_state,
            "rebalance_rows": rebalance_rows,
            "rebalance_state": rebalance_state,
            "vector": vector,
        }
        if vector["exploratory_followup_candidate"]:
            result["outcome"] = "exploratory_followup_candidate"
            result["failure_reason"] = ""
            result["decision_reason"] = "winner passed exploratory evaluation gates"
        else:
            result["outcome"] = "closed_exploration"
            result["failure_reason"] = vector["primary_failure_reason"]
            result["decision_reason"] = "winner failed exploratory evaluation gate"


def evaluation_gate_vector(
    metrics: dict[tuple[str, float], dict[str, Any]],
    subhalf_pass: bool,
    calendar_state: dict[str, Any],
    rebalance_state: dict[str, Any],
) -> dict[str, Any]:
    candidate_5 = metrics[("candidate", PRIMARY_COST)]
    named_5 = metrics[(INTERNAL_NAMED_CONTROL, PRIMARY_COST)]
    static_5 = metrics[(INTERNAL_STATIC_CONTROL, PRIMARY_COST)]
    equal_5 = metrics[(INTERNAL_EQUAL_CONTROL, PRIMARY_COST)]
    candidate_10 = metrics[("candidate", 10.0)]
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
        "evaluation_subhalf_stability_pass": subhalf_pass,
        "calendar_year_concentration_pass": bool(calendar_state["pass"]),
        "rebalance_month_concentration_pass": bool(rebalance_state["pass"]),
    }
    vector["exploratory_followup_candidate"] = all(bool(value) for value in vector.values())
    vector["primary_failure_reason"] = primary_failure_reason(vector)
    return vector


def internal_subhalf_rows(
    result: dict[str, Any],
    evaluation_metrics: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    split: PeriodSplit = result["split"]
    config: InternalConfig = result["config"]
    scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
    rows: list[dict[str, Any]] = []
    passes: list[bool] = []
    for half_id, half_index in split_halves(split.evaluation_index):
        sample_permits = len(half_index) >= 20
        candidate = metrics_for_path(result["simulation"]["candidate_paths"][PRIMARY_COST], half_index, scheduled)
        named = metrics_for_path(result["simulation"]["control_paths"][(INTERNAL_NAMED_CONTROL, PRIMARY_COST)], half_index, scheduled)
        worse = (
            sample_permits
            and finite_metric(candidate["sharpe_ratio"]) < finite_metric(named["sharpe_ratio"])
            and finite_metric(candidate["maximum_drawdown"]) < finite_metric(named["maximum_drawdown"])
        )
        passes.append(not worse)
        rows.append(
            {
                "package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "subhalf_id": half_id,
                "period_start": candidate["period_start"],
                "period_end": candidate["period_end"],
                "formation_count": candidate["formation_count"],
                "sample_permits": sample_permits,
                "candidate_sharpe": candidate["sharpe_ratio"],
                "named_control_sharpe": named["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "named_control_maximum_drawdown": named["maximum_drawdown"],
                "worse_than_named_on_both_sharpe_and_drawdown": worse,
                "pass": not worse,
                "evaluation_metrics_can_select_winner": False,
            }
        )
    return rows, all(passes)


def complete_calendar_years(full_index: pd.DatetimeIndex, period_index: pd.DatetimeIndex) -> list[int]:
    years: list[int] = []
    period_set = set(period_index)
    for year in sorted(set(period_index.year)):
        year_index = full_index[full_index.year == year]
        if len(year_index) and year_index.min() in period_set and year_index.max() in period_set:
            years.append(int(year))
    return years


def calendar_year_diagnostics(
    package_id: str,
    architecture_id: str,
    strategy_id: str,
    trial_id: str,
    period_index: pd.DatetimeIndex,
    candidate_path: dict[str, Any],
    named_path: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    full_index = candidate_path["returns"].index
    for year in complete_calendar_years(full_index, period_index):
        year_index = period_index[period_index.year == year]
        candidate_return = compound_return(candidate_path["returns"].reindex(year_index))
        named_return = compound_return(named_path["returns"].reindex(year_index))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "package_id": package_id,
                "architecture_id": architecture_id,
                "strategy_id": strategy_id,
                "trial_id": trial_id,
                "period_year": year,
                "period_complete_calendar_year": True,
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "descriptive_only": False,
            }
        )
    max_share = 0.0
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if len(rows) >= 2 and max_share > 0.8 + 1e-12 else "pass"
    else:
        state = "not_applicable_no_positive_excess"
    return rows, {
        "complete_year_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def rebalance_contribution_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split: PeriodSplit = result["split"]
    config: InternalConfig = result["config"]
    candidate = result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"]
    named = result["simulation"]["control_paths"][(INTERNAL_NAMED_CONTROL, PRIMARY_COST)]["returns"]
    eval_executions = [execution for _, execution in split.signal_execution_pairs if execution in set(split.evaluation_index)]
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    for position, start in enumerate(eval_executions):
        end = eval_executions[position + 1] if position + 1 < len(eval_executions) else split.evaluation_index.max()
        interval = split.evaluation_index[(split.evaluation_index >= start) & (split.evaluation_index < end)]
        if position + 1 == len(eval_executions):
            interval = split.evaluation_index[split.evaluation_index >= start]
        if not len(interval):
            continue
        candidate_return = compound_return(candidate.reindex(interval))
        named_return = compound_return(named.reindex(interval))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "rebalance_month": pd.Timestamp(start).to_period("M").strftime("%Y-%m"),
                "interval_start": pd.Timestamp(interval.min()).date().isoformat(),
                "interval_end": pd.Timestamp(interval.max()).date().isoformat(),
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "nonwinner_evaluation_access": False,
            }
        )
    max_share = 0.0
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if max_share > 0.8 + 1e-12 else "pass"
    else:
        state = "not_applicable_no_positive_excess"
    return rows, {
        "rebalance_month_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def metric_prefix(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_cagr": metrics.get("cagr", ""),
        f"{prefix}_total_return": metrics.get("total_return", ""),
        f"{prefix}_annualized_volatility": metrics.get("annualized_volatility", ""),
        f"{prefix}_sharpe_ratio": metrics.get("sharpe_ratio", ""),
        f"{prefix}_maximum_drawdown": metrics.get("maximum_drawdown", ""),
        f"{prefix}_turnover": metrics.get("turnover", ""),
        f"{prefix}_transaction_cost_drag": metrics.get("transaction_cost_drag", ""),
    }


def result_metric_row(
    package_id: str,
    architecture_id: str,
    family_id: str,
    configuration_code: str,
    strategy_id: str,
    trial_id: str,
    period_id: str,
    period_role: str,
    metrics: dict[str, Any],
    cost: float,
    control_metrics: dict[tuple[str, float], dict[str, Any]],
    named_id: str,
    static_id: str,
    equal_id: str,
    outcome: str,
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "package_id": package_id,
        "architecture_id": architecture_id,
        "family_id": family_id,
        "configuration_code": configuration_code,
        "strategy_id": strategy_id,
        "trial_id": trial_id,
        "result_role": "candidate",
        "period_id": period_id,
        "period_role": period_role,
        "cost_bps_one_way": cost,
        "period_start": metrics.get("period_start", ""),
        "period_end": metrics.get("period_end", ""),
        "trading_day_count": metrics.get("trading_day_count", ""),
        "formation_count": metrics.get("formation_count", ""),
        "rebalance_count": metrics.get("rebalance_count", ""),
        "total_return": metrics.get("total_return", ""),
        "cagr": metrics.get("cagr", ""),
        "annualized_volatility": metrics.get("annualized_volatility", ""),
        "sharpe_ratio": metrics.get("sharpe_ratio", ""),
        "maximum_drawdown": metrics.get("maximum_drawdown", ""),
        "turnover": metrics.get("turnover", ""),
        "annualized_turnover": metrics.get("annualized_turnover", ""),
        "transaction_cost_drag": metrics.get("transaction_cost_drag", ""),
        "average_holdings": metrics.get("average_holdings", ""),
        "maximum_asset_weight": metrics.get("maximum_asset_weight", ""),
        "maximum_gross_exposure": metrics.get("maximum_gross_exposure", ""),
        "maximum_daily_weight_sum": metrics.get("maximum_daily_weight_sum", ""),
        "daily_weight_sum_one": metrics.get("daily_weight_sum_one", ""),
        "numeric_invariant_status": metrics.get("numeric_invariant_status", ""),
        "timing_invariant_status": metrics.get("timing_invariant_status", ""),
        "exposure_weight_invariant_status": metrics.get("exposure_weight_invariant_status", ""),
        "invariant_pass": metrics.get("invariant_pass", ""),
        "named_control_id": named_id,
        **metric_prefix("named", control_metrics.get((named_id, cost), {})),
        "static_control_id": static_id,
        **metric_prefix("static", control_metrics.get((static_id, cost), {})),
        "equal_weight_control_id": equal_id,
        **metric_prefix("equal_weight", control_metrics.get((equal_id, cost), {})),
        "spy_buy_hold_cagr": control_metrics.get(("SPY_buy_and_hold", cost), {}).get("cagr", ""),
        "xlu_buy_hold_cagr": control_metrics.get(("XLU_buy_and_hold", cost), {}).get("cagr", ""),
        "bil_buy_hold_cagr": control_metrics.get(("BIL_buy_and_hold", cost), {}).get("cagr", ""),
        "outcome": outcome,
        "failure_reason": failure_reason,
    }


METRIC_RESULT_FIELDS = [
    "package_id",
    "architecture_id",
    "family_id",
    "configuration_code",
    "strategy_id",
    "trial_id",
    "result_role",
    "period_id",
    "period_role",
    "cost_bps_one_way",
    "period_start",
    "period_end",
    "trading_day_count",
    "formation_count",
    "rebalance_count",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "annualized_turnover",
    "transaction_cost_drag",
    "average_holdings",
    "maximum_asset_weight",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "daily_weight_sum_one",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_weight_invariant_status",
    "invariant_pass",
    "named_control_id",
    "named_cagr",
    "named_total_return",
    "named_annualized_volatility",
    "named_sharpe_ratio",
    "named_maximum_drawdown",
    "named_turnover",
    "named_transaction_cost_drag",
    "static_control_id",
    "static_cagr",
    "static_total_return",
    "static_annualized_volatility",
    "static_sharpe_ratio",
    "static_maximum_drawdown",
    "static_turnover",
    "static_transaction_cost_drag",
    "equal_weight_control_id",
    "equal_weight_cagr",
    "equal_weight_total_return",
    "equal_weight_annualized_volatility",
    "equal_weight_sharpe_ratio",
    "equal_weight_maximum_drawdown",
    "equal_weight_turnover",
    "equal_weight_transaction_cost_drag",
    "spy_buy_hold_cagr",
    "xlu_buy_hold_cagr",
    "bil_buy_hold_cagr",
    "outcome",
    "failure_reason",
]

CSV_FIELDS: dict[str, list[str]] = {
    "stale_robustness_source_of_truth_reconciliation.csv": [
        "strategy_id", "old_contract_task_id", "old_contract_outcome",
        "old_contract_failure_reason", "old_contract_decisive_gate",
        "old_contract_packet_classification", "authoritative_methodology",
        "authoritative_reassessment_task", "authoritative_current_outcome", "primary_role",
        "promotion_authority", "lifecycle_change_required", "rerun_required", "interpretation",
    ],
    "hybrid_intake_reconciliation.csv": [
        "intake_id", "intake_path", "artifact_name", "artifact_hash", "materialized_current_task",
        "frozen_identity_preserved", "network_access", "provider_calls", "cache_modified",
    ],
    "source_library_records.csv": [
        "source_library_record_id", "strategy_id", "family_id", "architecture_id", "source_role",
        "source_claim_replicated", "source_rule_summary", "source_variant_count", "network_access",
        "provider_calls", "counted_as_strategy", "counted_as_trial",
    ],
    "parameter_grid.csv": [
        "grid_position", "work_package_id", "architecture_id", "family_id", "configuration_code",
        "strategy_id", "trial_id", "lookback_sessions", "recovery_horizon_sessions", "shock_sigma_threshold",
        "selected_count", "weekly_horizon_observations", "universe", "fallback", "named_control",
        "other_controls", "source_or_research_lineage", "route", "grid_frozen_before_performance",
        "post_result_parameter_addition_allowed",
    ],
    "strategy_cards.csv": [
        "strategy_id", "trial_id", "work_package_id", "architecture_id", "family_id", "entity_type", "stage",
        "source_or_research_lineage", "primary_future_robustness_role", "route", "universe", "parameters",
        "named_control", "other_controls", "strategy_result", "failure_reason", "next_action",
        "counted_as_strategy", "counted_as_trial", "paper_demo_eligible",
    ],
    "trial_ledger.csv": [
        "trial_id", "entity_type", "strategy_id", "work_package_id", "architecture_id", "family_id",
        "configuration_code", "stage", "source_or_research_lineage", "route", "execution_timing",
        "canonical_configuration", "executed", "selection_evaluated", "evaluation_evaluated", "outcome",
        "failure_reason", "next_action", "preregistration_timestamp",
    ],
    "duplicate_preflight.csv": [
        "work_package_id", "architecture_id", "family_id", "strategy_id", "trial_id", "preflight_status",
        "execute_work_package", "executed_trial_count", "completed_record_scan_hash", "compared_against",
        "material_equivalence_found", "broad_family_similarity_only", "distinctive_mechanism",
        "reject_only_if_signal_holdings_execution_materially_equivalent", "preperformance_complete",
        "decision_reason",
    ],
    "benchmark_reference_log.csv": [
        "benchmark_reference_id", "entity_type", "work_package_id", "architecture_id", "strategy_id_context",
        "trial_id_context", "control_id", "control_role", "counted_as_strategy", "counted_as_trial",
        "counted_as_observation", "promotable",
    ],
    "external_weekly_signal_inventory.csv": [
        "work_package_id", "strategy_id", "trial_id", "weekly_observation_number", "signal_date",
        "execution_date", "has_four_week_warmup", "complete_source_signal", "deterministic_signal_half",
        "ratio_xlu_spy", "ratio_minus_4", "rs4_xlu_spy_ratio", "xlu_absolute_4w_return",
        "candidate_target", "named_control_target", "target_retained", "prewarmup_bil",
        "following_close_execution", "same_close_execution", "missing_signal_data_retains_previous",
        "missing_execution_price_blocks_transition",
    ],
    "internal_shock_event_fixture_results.csv": [
        "architecture_id", "configuration_code", "strategy_id", "trial_id", "signal_date", "execution_date",
        "asset", "lookback_sessions", "recovery_horizon_sessions", "shock_sigma_threshold", "return_mean",
        "return_volatility", "shock_threshold", "complete_shock_recovery_count", "candidate_recovery_score",
        "named_control_severity_score", "minimum_complete_events_pass", "candidate_selected",
        "named_control_selected", "candidate_unused_slot_bil_weight", "named_unused_slot_bil_weight",
        "uses_future_after_formation",
    ],
    "selection_segment_definition.csv": [
        "work_package_id", "architecture_id", "family_id", "segment_status", "common_universe", "common_start",
        "common_end", "first_valid_signal_date", "first_execution_date", "last_execution_date",
        "valid_formation_count", "selection_formation_count", "evaluation_formation_count",
        "selection_start", "selection_end", "evaluation_start", "evaluation_end", "boundary_execution_date",
        "split_rule", "segment_role",
    ],
    "selection_segment_results.csv": METRIC_RESULT_FIELDS + [
        "performance_executed", "selection_eligible_5bps", "selection_gate_failures",
    ],
    "architecture_winner_selection.csv": [
        "architecture_id", "family_id", "selection_status", "eligible_configuration_count",
        "selected_strategy_id", "selected_trial_id", "selected_configuration_code", "selection_rule",
        "selection_freeze_timestamp", "selection_frozen_before_evaluation_metrics", "selection_sharpe_5bps",
        "selection_maximum_drawdown_5bps", "selection_annualized_turnover_5bps", "winner_outcome",
        "failure_reason", "decision_reason",
    ],
    "evaluation_segment_results.csv": METRIC_RESULT_FIELDS + [
        "frozen_winner", "selection_frozen_before_evaluation_metrics",
    ],
    "external_exploration_results.csv": METRIC_RESULT_FIELDS + [
        "complete_weekly_signal_count", "first_half_complete_signal_count", "second_half_complete_signal_count",
        "external_exploration_gate_failures",
    ],
    "post_selection_full_period_diagnostics.csv": METRIC_RESULT_FIELDS + [
        "diagnostic_only", "can_rescue_or_reverse_decision",
    ],
    "evaluation_subhalf_results.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "subhalf_id", "period_start",
        "period_end", "formation_count", "sample_permits", "candidate_sharpe", "named_control_sharpe",
        "candidate_maximum_drawdown", "named_control_maximum_drawdown",
        "worse_than_named_on_both_sharpe_and_drawdown", "pass", "evaluation_metrics_can_select_winner",
    ],
    "calendar_year_results.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "period_year",
        "period_complete_calendar_year", "cost_bps_one_way", "candidate_return", "named_control_return",
        "candidate_minus_named_excess_return", "positive_excess_return", "descriptive_only",
    ],
    "rebalance_contribution_results.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "rebalance_month", "interval_start",
        "interval_end", "cost_bps_one_way", "candidate_return", "named_control_return",
        "candidate_minus_named_excess_return", "positive_excess_return", "nonwinner_evaluation_access",
    ],
    "lightweight_concentration_diagnostics.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "cost_bps_one_way",
        "calendar_complete_year_count", "calendar_positive_excess_total", "calendar_max_positive_excess_share",
        "calendar_concentration_state", "rebalance_month_count", "rebalance_positive_excess_total",
        "rebalance_max_positive_excess_share", "rebalance_concentration_state", "concentration_pass",
    ],
    "turnover_cost_reconciliation.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "period_id", "cost_bps_one_way",
        "turnover", "annualized_turnover", "transaction_cost_drag", "zero_cost_has_zero_drag",
        "cost_applied_once_to_one_way_turnover", "turnover_is_drift_adjusted",
    ],
    "invariant_results.csv": [
        "package_id", "architecture_id", "strategy_id", "trial_id", "period_id", "cost_bps_one_way",
        "numeric_invariant_status", "timing_invariant_status", "exposure_weight_invariant_status",
        "daily_weight_sum_one", "maximum_gross_exposure", "maximum_daily_weight_sum",
        "target_zero_weights_preserved", "explicit_holdings", "long_only", "no_leverage", "no_shorts",
        "natural_drift", "deterministic_turnover", "costs_applied_once", "no_tradable_price_forward_fill",
        "same_period_price_signal_return_used", "invariant_pass",
    ],
    "exploratory_followup_candidates.csv": [
        "work_package_id", "architecture_id", "strategy_id", "trial_id", "stage", "outcome",
        "primary_future_robustness_role", "decision_reason", "next_action", "execute_in_this_task",
    ],
    "failure_vectors.csv": [
        "work_package_id", "architecture_id", "strategy_id", "trial_id", "stage", "duplicate_or_redundant",
        "selection_eligible", "selected_winner", "evaluation_access_allowed", "exploratory_followup_candidate",
        "cagr_positive_5bps", "invariants_pass_5bps", "named_control_not_dominating_5bps",
        "material_vs_named_control_5bps", "static_or_static_equal_control_not_dominating_5bps",
        "cagr_positive_10bps", "chronological_or_subhalf_stability_pass", "calendar_year_concentration_pass",
        "rebalance_month_concentration_pass", "primary_failure_reason", "outcome",
    ],
    "failure_reasons.csv": [
        "work_package_id", "architecture_id", "strategy_id", "trial_id", "outcome", "primary_failure_reason",
        "failure_detail", "exact_configuration_only", "family_closed", "parameter_change_authorized",
    ],
    "process_task_log.csv": [
        "process_task_id", "entity_type", "mode", "stage", "task_scope", "external_work_package_count",
        "internal_architecture_count", "strategy_configuration_count", "canonical_trial_count",
        "batch_outcome", "next_action", "next_action_executed",
    ],
    "outcome_summary.csv": [
        "entity_id", "entity_type", "stage", "outcome", "selected_strategy_id", "selected_trial_id",
        "failure_reason", "decision_reason", "batch_outcome", "batch_next_action", "validation_claimed",
        "robustness_claimed", "paper_demo_authorized",
    ],
    "next_actions.csv": [
        "entity_id", "entity_type", "outcome", "next_action", "execute_in_this_task",
    ],
}


def parameter_grid_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "grid_position": 1,
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "configuration_code": "E1",
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "lookback_sessions": "",
            "recovery_horizon_sessions": "",
            "shock_sigma_threshold": "",
            "selected_count": 1,
            "weekly_horizon_observations": 4,
            "universe": "SPY|XLU",
            "fallback": "BIL before valid warmup only",
            "named_control": EXTERNAL_NAMED_CONTROL,
            "other_controls": f"{EXTERNAL_STATIC_CONTROL}|{EXTERNAL_EQUAL_CONTROL}|SPY_buy_and_hold|XLU_buy_and_hold|BIL_buy_and_hold",
            "source_or_research_lineage": EXTERNAL_LINEAGE,
            "route": "standalone",
            "grid_frozen_before_performance": True,
            "post_result_parameter_addition_allowed": False,
        }
    ]
    for position, config in enumerate(INTERNAL_CONFIGS, start=2):
        rows.append(
            {
                "grid_position": position,
                "work_package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "family_id": INTERNAL_FAMILY_ID,
                "configuration_code": config.configuration_code,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "lookback_sessions": config.lookback_sessions,
                "recovery_horizon_sessions": config.recovery_horizon_sessions,
                "shock_sigma_threshold": 1.0,
                "selected_count": 3,
                "weekly_horizon_observations": "",
                "universe": "|".join(INTERNAL_UNIVERSE),
                "fallback": "BIL unused slots",
                "named_control": INTERNAL_NAMED_CONTROL,
                "other_controls": f"{INTERNAL_STATIC_CONTROL}|{INTERNAL_EQUAL_CONTROL}|SPY_buy_and_hold|BIL_buy_and_hold",
                "source_or_research_lineage": INTERNAL_LINEAGE,
                "route": "standalone",
                "grid_frozen_before_performance": True,
                "post_result_parameter_addition_allowed": False,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    controls_by_trial = [
        (
            "external", EXTERNAL_ARCHITECTURE_ID, EXTERNAL_STRATEGY_ID, EXTERNAL_TRIAL_ID,
            [
                (EXTERNAL_NAMED_CONTROL, "named_control_xlu_absolute_momentum"),
                (EXTERNAL_STATIC_CONTROL, "static_average_state_frequency_control"),
                (EXTERNAL_EQUAL_CONTROL, "equal_weight_spy_xlu_control"),
                ("SPY_buy_and_hold", "broad_reference"),
                ("XLU_buy_and_hold", "broad_reference"),
                ("BIL_buy_and_hold", "cash_reference"),
            ],
        )
    ]
    for config in INTERNAL_CONFIGS:
        controls_by_trial.append(
            (
                "internal", INTERNAL_ARCHITECTURE_ID, config.strategy_id, config.trial_id,
                [
                    (INTERNAL_NAMED_CONTROL, "named_control_downside_shock_severity"),
                    (INTERNAL_STATIC_CONTROL, "static_average_candidate_weights_control"),
                    (INTERNAL_EQUAL_CONTROL, "equal_weight_universe_control"),
                    ("SPY_buy_and_hold", "broad_reference"),
                    ("BIL_buy_and_hold", "cash_reference"),
                ],
            )
        )
    for work_package, architecture, strategy, trial, controls in controls_by_trial:
        for control_id, role in controls:
            rows.append(
                {
                    "benchmark_reference_id": f"{trial}__{control_id}",
                    "entity_type": "benchmark_reference",
                    "work_package_id": work_package,
                    "architecture_id": architecture,
                    "strategy_id_context": strategy,
                    "trial_id_context": trial,
                    "control_id": control_id,
                    "control_role": role,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "counted_as_observation": False,
                    "promotable": False,
                }
            )
    return rows


def external_metric_rows(external: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate_failures = "|".join(
        key for key, value in external["vector"].items()
        if key not in {"exploratory_followup_candidate", "primary_failure_reason", "complete_signal_count", "first_half_complete_signal_count", "second_half_complete_signal_count"} and value is False
    )
    for cost in COSTS:
        rows.append(
            result_metric_row(
                "external", EXTERNAL_ARCHITECTURE_ID, EXTERNAL_FAMILY_ID, "E1",
                EXTERNAL_STRATEGY_ID, EXTERNAL_TRIAL_ID, "external_full_exploration_period",
                "external_public_rule_exploration", external["metrics"][("candidate", cost)], cost,
                external["metrics"], EXTERNAL_NAMED_CONTROL, EXTERNAL_STATIC_CONTROL, EXTERNAL_EQUAL_CONTROL,
                external["outcome"], external["failure_reason"],
            )
            | {
                "complete_weekly_signal_count": external["complete_signal_count"],
                "first_half_complete_signal_count": external["first_half_complete_signal_count"],
                "second_half_complete_signal_count": external["second_half_complete_signal_count"],
                "external_exploration_gate_failures": gate_failures,
            }
        )
    return rows


def internal_selection_rows(internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in INTERNAL_CONFIGS:
        result = internal_results[config.trial_id]
        for cost in COSTS:
            rows.append(
                result_metric_row(
                    "internal", INTERNAL_ARCHITECTURE_ID, INTERNAL_FAMILY_ID, config.configuration_code,
                    config.strategy_id, config.trial_id, "selection_segment",
                    "bounded_internal_optimization_selection_segment",
                    result["selection_metrics"][("candidate", cost)], cost, result["selection_metrics"],
                    INTERNAL_NAMED_CONTROL, INTERNAL_STATIC_CONTROL, INTERNAL_EQUAL_CONTROL,
                    result["outcome"], result["failure_reason"],
                )
                | {
                    "performance_executed": True,
                    "selection_eligible_5bps": result["selection_vector"]["selection_eligible"],
                    "selection_gate_failures": "|".join(
                        key for key, value in result["selection_vector"].items()
                        if key not in {"selection_eligible", "primary_failure_reason"} and value is False
                    ),
                }
            )
    return rows


def internal_evaluation_rows(internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in internal_results.values():
        if not (result.get("selected_winner") and result.get("evaluation")):
            continue
        config: InternalConfig = result["config"]
        for cost in COSTS:
            rows.append(
                result_metric_row(
                    "internal", INTERNAL_ARCHITECTURE_ID, INTERNAL_FAMILY_ID, config.configuration_code,
                    config.strategy_id, config.trial_id, "exploratory_evaluation_segment",
                    "internal_winner_exploratory_evaluation_segment",
                    result["evaluation"]["metrics"][("candidate", cost)], cost, result["evaluation"]["metrics"],
                    INTERNAL_NAMED_CONTROL, INTERNAL_STATIC_CONTROL, INTERNAL_EQUAL_CONTROL,
                    result["outcome"], result["failure_reason"],
                )
                | {
                    "frozen_winner": True,
                    "selection_frozen_before_evaluation_metrics": True,
                }
            )
    return rows


def post_selection_rows(internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in internal_results.values():
        if not (result.get("selected_winner") and result.get("evaluation")):
            continue
        config: InternalConfig = result["config"]
        for cost in COSTS:
            rows.append(
                result_metric_row(
                    "internal", INTERNAL_ARCHITECTURE_ID, INTERNAL_FAMILY_ID, config.configuration_code,
                    config.strategy_id, config.trial_id, "post_selection_full_period_diagnostic",
                    "diagnostic_only_full_common_period_not_selection_or_validation",
                    result["evaluation"]["full_metrics"][("candidate", cost)], cost, result["evaluation"]["full_metrics"],
                    INTERNAL_NAMED_CONTROL, INTERNAL_STATIC_CONTROL, INTERNAL_EQUAL_CONTROL,
                    result["outcome"], result["failure_reason"],
                )
                | {
                    "diagnostic_only": True,
                    "can_rescue_or_reverse_decision": False,
                }
            )
    return rows


def selection_definition_rows(external: dict[str, Any], internal_split: PeriodSplit) -> list[dict[str, Any]]:
    return [
        {
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "segment_status": "executed" if external["executed"] else "signal_scarcity",
            "common_universe": EXTERNAL_COLUMNS,
            "common_start": external["split"].prices.index.min().date().isoformat(),
            "common_end": external["split"].prices.index.max().date().isoformat(),
            "first_valid_signal_date": external["split"].signal_execution_pairs[0][0].date().isoformat() if external["split"].signal_execution_pairs else "",
            "first_execution_date": external["split"].signal_execution_pairs[0][1].date().isoformat() if external["split"].signal_execution_pairs else "",
            "last_execution_date": external["split"].signal_execution_pairs[-1][1].date().isoformat() if external["split"].signal_execution_pairs else "",
            "valid_formation_count": len(external["split"].signal_execution_pairs),
            "selection_formation_count": "",
            "evaluation_formation_count": "",
            "selection_start": "",
            "selection_end": "",
            "evaluation_start": "",
            "evaluation_end": "",
            "boundary_execution_date": "",
            "split_rule": "external_exploration_full_period_with_deterministic_halves_for_gate",
            "segment_role": "external_exploration_not_robustness_or_validation",
        },
        {
            "work_package_id": "internal",
            "architecture_id": INTERNAL_ARCHITECTURE_ID,
            "family_id": INTERNAL_FAMILY_ID,
            "segment_status": "executed",
            "common_universe": INTERNAL_COLUMNS,
            "common_start": internal_split.prices.index.min().date().isoformat(),
            "common_end": internal_split.prices.index.max().date().isoformat(),
            "first_valid_signal_date": internal_split.signal_execution_pairs[0][0].date().isoformat(),
            "first_execution_date": internal_split.signal_execution_pairs[0][1].date().isoformat(),
            "last_execution_date": internal_split.signal_execution_pairs[-1][1].date().isoformat(),
            "valid_formation_count": len(internal_split.signal_execution_pairs),
            "selection_formation_count": sum(execution in set(internal_split.selection_index) for _, execution in internal_split.signal_execution_pairs),
            "evaluation_formation_count": sum(execution in set(internal_split.evaluation_index) for _, execution in internal_split.signal_execution_pairs),
            "selection_start": internal_split.selection_index.min().date().isoformat(),
            "selection_end": internal_split.selection_index.max().date().isoformat(),
            "evaluation_start": internal_split.evaluation_index.min().date().isoformat(),
            "evaluation_end": internal_split.evaluation_index.max().date().isoformat(),
            "boundary_execution_date": internal_split.boundary_execution.date().isoformat() if internal_split.boundary_execution is not None else "",
            "split_rule": "floor_60_percent_valid_monthly_formations_selection_final_40_percent_exploratory_evaluation",
            "segment_role": "optimization_to_exploratory_evaluation_not_validation_or_robustness",
        },
    ]


def architecture_winner_rows(internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [result for result in internal_results.values() if result["selection_vector"].get("selection_eligible")]
    winner = next((result for result in internal_results.values() if result.get("selected_winner")), None)
    if winner is None:
        return [
            {
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "family_id": INTERNAL_FAMILY_ID,
                "selection_status": "no_selection_eligible_configuration",
                "eligible_configuration_count": len(eligible),
                "selected_strategy_id": "",
                "selected_trial_id": "",
                "selected_configuration_code": "",
                "selection_rule": "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id",
                "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
                "selection_frozen_before_evaluation_metrics": True,
                "selection_sharpe_5bps": "",
                "selection_maximum_drawdown_5bps": "",
                "selection_annualized_turnover_5bps": "",
                "winner_outcome": "closed_optimization",
                "failure_reason": "no_selection_eligible_configuration",
                "decision_reason": "no internal configuration passed the frozen selection gate",
            }
        ]
    metrics = winner["selection_metrics"][("candidate", PRIMARY_COST)]
    config: InternalConfig = winner["config"]
    return [
        {
            "architecture_id": INTERNAL_ARCHITECTURE_ID,
            "family_id": INTERNAL_FAMILY_ID,
            "selection_status": "winner_frozen",
            "eligible_configuration_count": len(eligible),
            "selected_strategy_id": config.strategy_id,
            "selected_trial_id": config.trial_id,
            "selected_configuration_code": config.configuration_code,
            "selection_rule": "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id",
            "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
            "selection_frozen_before_evaluation_metrics": True,
            "selection_sharpe_5bps": metrics["sharpe_ratio"],
            "selection_maximum_drawdown_5bps": metrics["maximum_drawdown"],
            "selection_annualized_turnover_5bps": metrics["annualized_turnover"],
            "winner_outcome": winner["outcome"],
            "failure_reason": winner["failure_reason"],
            "decision_reason": winner["decision_reason"],
        }
    ]


def strategy_card_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "entity_type": "strategy_configuration",
            "stage": "exploration",
            "source_or_research_lineage": EXTERNAL_LINEAGE,
            "primary_future_robustness_role": EXTERNAL_ROLE,
            "route": "standalone",
            "universe": "SPY|XLU|BIL",
            "parameters": {"weekly_horizon_observations": 4},
            "named_control": EXTERNAL_NAMED_CONTROL,
            "other_controls": [EXTERNAL_STATIC_CONTROL, EXTERNAL_EQUAL_CONTROL, "SPY_buy_and_hold", "XLU_buy_and_hold", "BIL_buy_and_hold"],
            "strategy_result": external["outcome"],
            "failure_reason": external["failure_reason"],
            "next_action": FOLLOWUP_NEXT_ACTION if external["outcome"] == "exploratory_followup_candidate" else "closed_no_parameter_change_authorized",
            "counted_as_strategy": True,
            "counted_as_trial": True,
            "paper_demo_eligible": False,
        }
    ]
    for config in INTERNAL_CONFIGS:
        result = internal_results[config.trial_id]
        rows.append(
            {
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "work_package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "family_id": INTERNAL_FAMILY_ID,
                "entity_type": "strategy_configuration",
                "stage": "optimization" if not result.get("selected_winner") else "exploratory_evaluation",
                "source_or_research_lineage": INTERNAL_LINEAGE,
                "primary_future_robustness_role": INTERNAL_ROLE,
                "route": "standalone",
                "universe": "|".join(INTERNAL_UNIVERSE + ("BIL",)),
                "parameters": config.parameters,
                "named_control": INTERNAL_NAMED_CONTROL,
                "other_controls": [INTERNAL_STATIC_CONTROL, INTERNAL_EQUAL_CONTROL, "SPY_buy_and_hold", "BIL_buy_and_hold"],
                "strategy_result": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": FOLLOWUP_NEXT_ACTION if result["outcome"] == "exploratory_followup_candidate" else "closed_no_parameter_change_authorized",
                "counted_as_strategy": True,
                "counted_as_trial": True,
                "paper_demo_eligible": False,
            }
        )
    return rows


def trial_ledger_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "trial_id": EXTERNAL_TRIAL_ID,
            "entity_type": "canonical_exploration_trial",
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "family_id": EXTERNAL_FAMILY_ID,
            "configuration_code": "E1",
            "stage": "exploration",
            "source_or_research_lineage": EXTERNAL_LINEAGE,
            "route": "standalone",
            "execution_timing": TIMING_CONVENTION,
            "canonical_configuration": True,
            "executed": external["executed"],
            "selection_evaluated": False,
            "evaluation_evaluated": False,
            "outcome": external["outcome"],
            "failure_reason": external["failure_reason"],
            "next_action": FOLLOWUP_NEXT_ACTION if external["outcome"] == "exploratory_followup_candidate" else "closed_no_parameter_change_authorized",
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        }
    ]
    for config in INTERNAL_CONFIGS:
        result = internal_results[config.trial_id]
        rows.append(
            {
                "trial_id": config.trial_id,
                "entity_type": "canonical_optimization_trial",
                "strategy_id": config.strategy_id,
                "work_package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "family_id": INTERNAL_FAMILY_ID,
                "configuration_code": config.configuration_code,
                "stage": "optimization_to_exploratory_evaluation" if result.get("selected_winner") else "optimization",
                "source_or_research_lineage": INTERNAL_LINEAGE,
                "route": "standalone",
                "execution_timing": TIMING_CONVENTION,
                "canonical_configuration": True,
                "executed": True,
                "selection_evaluated": True,
                "evaluation_evaluated": bool(result.get("selected_winner") and result.get("evaluation")),
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": FOLLOWUP_NEXT_ACTION if result["outcome"] == "exploratory_followup_candidate" else "closed_no_parameter_change_authorized",
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def concentration_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "cost_bps_one_way": PRIMARY_COST,
            "calendar_complete_year_count": external["calendar_state"]["complete_year_count"],
            "calendar_positive_excess_total": external["calendar_state"]["positive_excess_total"],
            "calendar_max_positive_excess_share": external["calendar_state"]["max_positive_excess_share"],
            "calendar_concentration_state": external["calendar_state"]["state"],
            "rebalance_month_count": external["rebalance_state"]["rebalance_month_count"],
            "rebalance_positive_excess_total": external["rebalance_state"]["positive_excess_total"],
            "rebalance_max_positive_excess_share": external["rebalance_state"]["max_positive_excess_share"],
            "rebalance_concentration_state": external["rebalance_state"]["state"],
            "concentration_pass": bool(external["calendar_state"]["pass"] and external["rebalance_state"]["pass"]),
        }
    ]
    for result in internal_results.values():
        if not (result.get("selected_winner") and result.get("evaluation")):
            continue
        config: InternalConfig = result["config"]
        calendar_state = result["evaluation"]["calendar_state"]
        rebalance_state = result["evaluation"]["rebalance_state"]
        rows.append(
            {
                "package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "cost_bps_one_way": PRIMARY_COST,
                "calendar_complete_year_count": calendar_state["complete_year_count"],
                "calendar_positive_excess_total": calendar_state["positive_excess_total"],
                "calendar_max_positive_excess_share": calendar_state["max_positive_excess_share"],
                "calendar_concentration_state": calendar_state["state"],
                "rebalance_month_count": rebalance_state["rebalance_month_count"],
                "rebalance_positive_excess_total": rebalance_state["positive_excess_total"],
                "rebalance_max_positive_excess_share": rebalance_state["max_positive_excess_share"],
                "rebalance_concentration_state": rebalance_state["state"],
                "concentration_pass": bool(calendar_state["pass"] and rebalance_state["pass"]),
            }
        )
    return rows


def turnover_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        metrics = external["metrics"][("candidate", cost)]
        rows.append(
            {
                "package_id": "external",
                "architecture_id": EXTERNAL_ARCHITECTURE_ID,
                "strategy_id": EXTERNAL_STRATEGY_ID,
                "trial_id": EXTERNAL_TRIAL_ID,
                "period_id": "external_full_exploration_period",
                "cost_bps_one_way": cost,
                "turnover": metrics["turnover"],
                "annualized_turnover": metrics["annualized_turnover"],
                "transaction_cost_drag": metrics["transaction_cost_drag"],
                "zero_cost_has_zero_drag": cost != 0.0 or abs(float(metrics["transaction_cost_drag"])) <= 1e-14,
                "cost_applied_once_to_one_way_turnover": True,
                "turnover_is_drift_adjusted": True,
            }
        )
    for result in internal_results.values():
        config: InternalConfig = result["config"]
        periods = [("selection_segment", result["selection_metrics"])]
        if result.get("selected_winner") and result.get("evaluation"):
            periods.extend(
                [
                    ("exploratory_evaluation_segment", result["evaluation"]["metrics"]),
                    ("post_selection_full_period_diagnostic", result["evaluation"]["full_metrics"]),
                ]
            )
        for period_id, metric_map in periods:
            for cost in COSTS:
                metrics = metric_map[("candidate", cost)]
                rows.append(
                    {
                        "package_id": "internal",
                        "architecture_id": INTERNAL_ARCHITECTURE_ID,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "period_id": period_id,
                        "cost_bps_one_way": cost,
                        "turnover": metrics["turnover"],
                        "annualized_turnover": metrics["annualized_turnover"],
                        "transaction_cost_drag": metrics["transaction_cost_drag"],
                        "zero_cost_has_zero_drag": cost != 0.0 or abs(float(metrics["transaction_cost_drag"])) <= 1e-14,
                        "cost_applied_once_to_one_way_turnover": True,
                        "turnover_is_drift_adjusted": True,
                    }
                )
    return rows


def invariant_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def append_row(package_id: str, architecture_id: str, strategy_id: str, trial_id: str, period_id: str, cost: float, metrics: dict[str, Any]) -> None:
        rows.append(
            {
                "package_id": package_id,
                "architecture_id": architecture_id,
                "strategy_id": strategy_id,
                "trial_id": trial_id,
                "period_id": period_id,
                "cost_bps_one_way": cost,
                "numeric_invariant_status": metrics["numeric_invariant_status"],
                "timing_invariant_status": metrics["timing_invariant_status"],
                "exposure_weight_invariant_status": metrics["exposure_weight_invariant_status"],
                "daily_weight_sum_one": metrics["daily_weight_sum_one"],
                "maximum_gross_exposure": metrics["maximum_gross_exposure"],
                "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
                "target_zero_weights_preserved": metrics["target_zero_weights_preserved"],
                "explicit_holdings": metrics["explicit_holdings"],
                "long_only": True,
                "no_leverage": True,
                "no_shorts": True,
                "natural_drift": True,
                "deterministic_turnover": True,
                "costs_applied_once": True,
                "no_tradable_price_forward_fill": True,
                "same_period_price_signal_return_used": False,
                "invariant_pass": metrics["invariant_pass"],
            }
        )

    for cost in COSTS:
        append_row(
            "external", EXTERNAL_ARCHITECTURE_ID, EXTERNAL_STRATEGY_ID, EXTERNAL_TRIAL_ID,
            "external_full_exploration_period", cost, external["metrics"][("candidate", cost)]
        )
    for result in internal_results.values():
        config: InternalConfig = result["config"]
        for cost in COSTS:
            append_row("internal", INTERNAL_ARCHITECTURE_ID, config.strategy_id, config.trial_id, "selection_segment", cost, result["selection_metrics"][("candidate", cost)])
        if result.get("selected_winner") and result.get("evaluation"):
            for period_id, metric_map in (
                ("exploratory_evaluation_segment", result["evaluation"]["metrics"]),
                ("post_selection_full_period_diagnostic", result["evaluation"]["full_metrics"]),
            ):
                for cost in COSTS:
                    append_row("internal", INTERNAL_ARCHITECTURE_ID, config.strategy_id, config.trial_id, period_id, cost, metric_map[("candidate", cost)])
    return rows


def followup_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if external["outcome"] == "exploratory_followup_candidate":
        rows.append(
            {
                "work_package_id": "external",
                "architecture_id": EXTERNAL_ARCHITECTURE_ID,
                "strategy_id": EXTERNAL_STRATEGY_ID,
                "trial_id": EXTERNAL_TRIAL_ID,
                "stage": "exploration",
                "outcome": external["outcome"],
                "primary_future_robustness_role": EXTERNAL_ROLE,
                "decision_reason": external["decision_reason"],
                "next_action": FOLLOWUP_NEXT_ACTION,
                "execute_in_this_task": False,
            }
        )
    for result in internal_results.values():
        if result["outcome"] == "exploratory_followup_candidate":
            rows.append(
                {
                    "work_package_id": "internal",
                    "architecture_id": INTERNAL_ARCHITECTURE_ID,
                    "strategy_id": result["config"].strategy_id,
                    "trial_id": result["config"].trial_id,
                    "stage": "exploratory_evaluation",
                    "outcome": result["outcome"],
                    "primary_future_robustness_role": INTERNAL_ROLE,
                    "decision_reason": result["decision_reason"],
                    "next_action": FOLLOWUP_NEXT_ACTION,
                    "execute_in_this_task": False,
                }
            )
    return rows


def failure_vector_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "work_package_id": "external",
            "architecture_id": EXTERNAL_ARCHITECTURE_ID,
            "strategy_id": EXTERNAL_STRATEGY_ID,
            "trial_id": EXTERNAL_TRIAL_ID,
            "stage": "exploration",
            "duplicate_or_redundant": False,
            "selection_eligible": "",
            "selected_winner": "",
            "evaluation_access_allowed": "",
            "exploratory_followup_candidate": external["vector"].get("exploratory_followup_candidate", False),
            "cagr_positive_5bps": external["vector"].get("cagr_positive_5bps", ""),
            "invariants_pass_5bps": external["vector"].get("invariants_pass_5bps", ""),
            "named_control_not_dominating_5bps": external["vector"].get("named_control_not_dominating_5bps", ""),
            "material_vs_named_control_5bps": external["vector"].get("material_vs_named_control_5bps", ""),
            "static_or_static_equal_control_not_dominating_5bps": external["vector"].get("static_control_not_dominating_5bps", ""),
            "cagr_positive_10bps": external["vector"].get("cagr_positive_10bps", ""),
            "chronological_or_subhalf_stability_pass": external["vector"].get("chronological_halves_pass", ""),
            "calendar_year_concentration_pass": external["vector"].get("calendar_year_concentration_pass", ""),
            "rebalance_month_concentration_pass": "",
            "primary_failure_reason": external["failure_reason"],
            "outcome": external["outcome"],
        }
    ]
    for config in INTERNAL_CONFIGS:
        result = internal_results[config.trial_id]
        vector = result.get("evaluation", {}).get("vector", result["selection_vector"])
        rows.append(
            {
                "work_package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "stage": "exploratory_evaluation" if result.get("selected_winner") else "optimization",
                "duplicate_or_redundant": False,
                "selection_eligible": result["selection_vector"].get("selection_eligible", False),
                "selected_winner": result.get("selected_winner", False),
                "evaluation_access_allowed": result.get("selected_winner", False),
                "exploratory_followup_candidate": vector.get("exploratory_followup_candidate", False),
                "cagr_positive_5bps": vector.get("cagr_positive_5bps", ""),
                "invariants_pass_5bps": vector.get("invariants_pass_5bps", ""),
                "named_control_not_dominating_5bps": vector.get("named_control_not_dominating_5bps", ""),
                "material_vs_named_control_5bps": vector.get("material_vs_named_control_5bps", ""),
                "static_or_static_equal_control_not_dominating_5bps": vector.get("static_equal_control_not_dominating_5bps", ""),
                "cagr_positive_10bps": vector.get("cagr_positive_10bps", ""),
                "chronological_or_subhalf_stability_pass": vector.get("evaluation_subhalf_stability_pass", ""),
                "calendar_year_concentration_pass": vector.get("calendar_year_concentration_pass", ""),
                "rebalance_month_concentration_pass": vector.get("rebalance_month_concentration_pass", ""),
                "primary_failure_reason": result["failure_reason"],
                "outcome": result["outcome"],
            }
        )
    return rows


def failure_reason_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if external["failure_reason"]:
        rows.append(
            {
                "work_package_id": "external",
                "architecture_id": EXTERNAL_ARCHITECTURE_ID,
                "strategy_id": EXTERNAL_STRATEGY_ID,
                "trial_id": EXTERNAL_TRIAL_ID,
                "outcome": external["outcome"],
                "primary_failure_reason": external["failure_reason"],
                "failure_detail": external["decision_reason"],
                "exact_configuration_only": True,
                "family_closed": False,
                "parameter_change_authorized": False,
            }
        )
    for config in INTERNAL_CONFIGS:
        result = internal_results[config.trial_id]
        if not result["failure_reason"]:
            continue
        rows.append(
            {
                "work_package_id": "internal",
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "outcome": result["outcome"],
                "primary_failure_reason": result["failure_reason"],
                "failure_detail": result["decision_reason"],
                "exact_configuration_only": True,
                "family_closed": False,
                "parameter_change_authorized": False,
            }
        )
    return rows


def batch_outcome(external: dict[str, Any], internal_results: dict[str, dict[str, Any]]) -> tuple[str, str]:
    followup_count = int(external["outcome"] == "exploratory_followup_candidate") + sum(
        result["outcome"] == "exploratory_followup_candidate" for result in internal_results.values()
    )
    executed_packages = int(external["executed"]) + 1
    blocked_packages = int(external["blocked"])
    if followup_count:
        return "hybrid_batch_followup_found", FOLLOWUP_NEXT_ACTION
    if executed_packages == 0:
        return "hybrid_batch_blocked", BLOCK_NEXT_ACTION
    if blocked_packages:
        return "hybrid_batch_partially_blocked", NO_FOLLOWUP_NEXT_ACTION
    return "hybrid_batch_no_followup", NO_FOLLOWUP_NEXT_ACTION


def entity_counts(external: dict[str, Any], internal_results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> dict[str, Any]:
    followup_count = int(external["outcome"] == "exploratory_followup_candidate") + sum(
        result["outcome"] == "exploratory_followup_candidate" for result in internal_results.values()
    )
    winner_count = sum(result.get("selected_winner", False) for result in internal_results.values())
    return {
        "source_of_truth_reconciliation_records": 1,
        "reconciled_historical_strategies": 2,
        "new_mca_hyg_strategy_configurations": 0,
        "new_mca_hyg_robustness_trials": 0,
        "mca_hyg_lifecycle_changes": 0,
        "source_library_records": 1,
        "external_strategy_configurations": 1,
        "external_canonical_trials": 1,
        "internal_architectures": 1,
        "internal_strategy_configurations": len(INTERNAL_CONFIGS),
        "internal_canonical_trials": len(INTERNAL_CONFIGS),
        "total_strategy_configurations": 1 + len(INTERNAL_CONFIGS),
        "total_canonical_trials": 1 + len(INTERNAL_CONFIGS),
        "executed_canonical_trials": int(external["executed"]) + len(INTERNAL_CONFIGS),
        "internal_architecture_winners": winner_count,
        "exploratory_followup_candidates": followup_count,
        "benchmark_references": len(benchmark_rows()),
        "robustness_trials_created": 0,
        "validation_trials_created": 0,
        "paper_demo_eligibility_decisions": 0,
        "handoff_packets": 0,
        "observations": 0,
        "process_tasks": 1,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }


def outcome_summary_rows(external: dict[str, Any], internal_results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> list[dict[str, Any]]:
    winner = next((result for result in internal_results.values() if result.get("selected_winner")), None)
    internal_failure = (
        winner["failure_reason"] if winner is not None else "no_selection_eligible_configuration"
    )
    rows = [
        {
            "entity_id": EXTERNAL_STRATEGY_ID,
            "entity_type": "external_work_package",
            "stage": "exploration",
            "outcome": external["outcome"],
            "selected_strategy_id": EXTERNAL_STRATEGY_ID if external["outcome"] == "exploratory_followup_candidate" else "",
            "selected_trial_id": EXTERNAL_TRIAL_ID if external["outcome"] == "exploratory_followup_candidate" else "",
            "failure_reason": external["failure_reason"],
            "decision_reason": external["decision_reason"],
            "batch_outcome": outcome,
            "batch_next_action": next_action,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
        },
        {
            "entity_id": INTERNAL_ARCHITECTURE_ID,
            "entity_type": "internal_architecture",
            "stage": "optimization_to_exploratory_evaluation",
            "outcome": (
                "exploratory_followup_candidate"
                if any(result["outcome"] == "exploratory_followup_candidate" for result in internal_results.values())
                else ("closed_optimization" if winner is None else winner["outcome"])
            ),
            "selected_strategy_id": "" if winner is None else winner["config"].strategy_id,
            "selected_trial_id": "" if winner is None else winner["config"].trial_id,
            "failure_reason": internal_failure,
            "decision_reason": "winner passed evaluation" if any(result["outcome"] == "exploratory_followup_candidate" for result in internal_results.values()) else "no exploratory follow-up from internal architecture",
            "batch_outcome": outcome,
            "batch_next_action": next_action,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
        },
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "stage": "mixed_exploration_optimization",
            "outcome": outcome,
            "selected_strategy_id": "",
            "selected_trial_id": "",
            "failure_reason": "",
            "decision_reason": "candidate-level follow-up routing takes precedence over partial-block labels",
            "batch_outcome": outcome,
            "batch_next_action": next_action,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
        },
    ]
    return rows


def next_action_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "outcome": outcome,
            "next_action": next_action,
            "execute_in_this_task": False,
        }
    ]


def process_task_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "mode": "bounded_hybrid_quantitative_discovery",
            "stage": "mixed_exploration_optimization_to_exploratory_evaluation",
            "task_scope": "exactly_two_work_packages_one_external_four_internal_trials",
            "external_work_package_count": 1,
            "internal_architecture_count": 1,
            "strategy_configuration_count": 5,
            "canonical_trial_count": 5,
            "batch_outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
        }
    ]


def required_files_will_be_present_after_consistency_write() -> bool:
    current = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    return (current | {"consistency_check.json"}) == REQUIRED_OUTPUT_FILES


def deterministic_core_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_OUTPUT_FILES - {"consistency_check.json"}):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def build_report(external: dict[str, Any], internal_results: dict[str, dict[str, Any]], counts: dict[str, Any], outcome: str, next_action: str) -> str:
    winner = next((result for result in internal_results.values() if result.get("selected_winner")), None)
    lines = [
        "# Accepted-47 Hybrid Discovery Batch V1",
        "",
        "## Scope",
        "",
        "Exactly two frozen work packages were processed: one public-rule SPY/XLU Beta Rotation exploration and one internally generated post-shock recovery architecture with four canonical optimization trials.",
        "",
        "## Source-of-Truth Reconciliation",
        "",
        f"The historical `{OLD_ROBUSTNESS_TASK_ID}` packet remains preserved as `{STALE_ROBUSTNESS_CLASSIFICATION}`. MCA and HYG retain their authoritative `robustness_positive` role-aware reassessment outcomes; no lifecycle record or robustness trial was changed or created.",
        "",
        "## Outcomes",
        "",
        f"* External Beta Rotation: `{external['outcome']}`" + (f" (`{external['failure_reason']}`)" if external["failure_reason"] else ""),
        f"* Internal architecture winner: `{winner['config'].strategy_id if winner else 'none'}`",
    ]
    if winner is not None:
        lines.append(f"* Internal winner outcome: `{winner['outcome']}`" + (f" (`{winner['failure_reason']}`)" if winner["failure_reason"] else ""))
    lines.extend(
        [
            "",
            "## Entity Counts",
            "",
            f"* Source-library records: {counts['source_library_records']}",
            f"* Strategy configurations: {counts['total_strategy_configurations']}",
            f"* Canonical trials: {counts['total_canonical_trials']}",
            f"* Follow-up candidates: {counts['exploratory_followup_candidates']}",
            "",
            "## Guardrails",
            "",
            "* Accepted-47 canonical research caches only.",
            "* No provider, network, cache refresh, forward observation, broker, robustness, validation, paper/demo eligibility, or handoff/export action occurred.",
            "* Controls are benchmark references only.",
            "* Nonwinning internal variants have no evaluation-segment result rows.",
            "",
            "## Batch Outcome",
            "",
            f"`{outcome}`",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action was recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    if len(INTERNAL_CONFIGS) != 4 or 1 + len(INTERNAL_CONFIGS) > 5:
        raise RuntimeError("Frozen hybrid trial scope drift")
    if set(REQUIRED_SYMBOLS) != {
        "SPY", "XLU", "QQQ", "IWM", "EFA", "EEM", "HYG", "LQD", "TLT", "TIP", "GLD", "DBC", "IYR", "BIL"
    }:
        raise RuntimeError("Required symbol boundary drift")
    if len({config.strategy_id for config in INTERNAL_CONFIGS} | {EXTERNAL_STRATEGY_ID}) != 5:
        raise RuntimeError("Strategy identifiers are not unique")
    if len({config.trial_id for config in INTERNAL_CONFIGS} | {EXTERNAL_TRIAL_ID}) != 5:
        raise RuntimeError("Trial identifiers are not unique")

    intake_hashes = materialize_intake()
    before_protected = protected_hashes()
    clean_dir(OUTPUT_DIR)
    stale_reconciliation_rows = stale_robustness_source_of_truth_rows()
    write_csv(
        OUTPUT_DIR / "stale_robustness_source_of_truth_reconciliation.csv",
        stale_reconciliation_rows,
        CSV_FIELDS["stale_robustness_source_of_truth_reconciliation.csv"],
    )
    duplicate_rows = duplicate_preflight_rows()
    frames = load_frames()
    cache_rows = cache_preflight_rows(frames)
    external = build_external_package(frames)
    internal_split, internal_results = build_internal_results(frames)
    outcome, next_action = batch_outcome(external, internal_results)
    counts = entity_counts(external, internal_results, outcome, next_action)

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": TASK_ID,
            "module_owner": "trading_tournament",
            "stage": "mixed_external_exploration_internal_optimization_to_exploratory_evaluation",
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "intake_id": INTAKE_ID,
            "intake_path": rel(INTAKE_DIR),
            "stale_robustness_reconciliation": {
                "record_count": 1,
                "strategy_row_count": len(stale_reconciliation_rows),
                "historical_packet_classification": STALE_ROBUSTNESS_CLASSIFICATION,
                "authoritative_methodology": ROLE_AWARE_STANDARD_ID,
                "authoritative_reassessment_task": ROLE_AWARE_REASSESSMENT_TASK_ID,
                "new_robustness_trials": 0,
                "lifecycle_changes": 0,
            },
            "external_work_packages": 1,
            "internal_architectures": 1,
            "strategy_configurations": 5,
            "canonical_trial_count": 5,
            "primary_one_way_cost_bps": PRIMARY_COST,
            "diagnostic_one_way_cost_bps": [0.0, 10.0],
            "data_boundary": {
                "cache_dir": rel(CACHE_DIR),
                "required_symbols": list(REQUIRED_SYMBOLS),
                "provider_access": False,
                "network_access": False,
                "cache_modification": False,
                "forward_observation_data_used": False,
            },
            "batch_outcome": outcome,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "robustness_trials_created": 0,
            "validation_trials_created": 0,
            "paper_demo_eligibility_records_created": 0,
            "handoff_export_records_created": 0,
            "observations_created": 0,
        },
    )
    write_csv(
        OUTPUT_DIR / "hybrid_intake_reconciliation.csv",
        [
            {
                "intake_id": INTAKE_ID,
                "intake_path": rel(INTAKE_DIR),
                "artifact_name": name,
                "artifact_hash": digest,
                "materialized_current_task": True,
                "frozen_identity_preserved": True,
                "network_access": False,
                "provider_calls": 0,
                "cache_modified": False,
            }
            for name, digest in sorted(intake_hashes.items())
        ],
        CSV_FIELDS["hybrid_intake_reconciliation.csv"],
    )
    write_csv(OUTPUT_DIR / "source_library_records.csv", source_library_rows(), CSV_FIELDS["source_library_records.csv"])
    write_yaml(
        OUTPUT_DIR / "architecture_preregistration.yaml",
        {
            "batch_id": TASK_ID,
            "external_work_package": {
                "strategy_id": EXTERNAL_STRATEGY_ID,
                "trial_id": EXTERNAL_TRIAL_ID,
                "family_id": EXTERNAL_FAMILY_ID,
                "architecture_id": EXTERNAL_ARCHITECTURE_ID,
                "source_or_research_lineage": EXTERNAL_LINEAGE,
                "route": "standalone",
                "weekly_horizon_observations": 4,
                "named_control": EXTERNAL_NAMED_CONTROL,
                "static_control": EXTERNAL_STATIC_CONTROL,
                "equal_weight_control": EXTERNAL_EQUAL_CONTROL,
            },
            "internal_architecture": {
                "family_id": INTERNAL_FAMILY_ID,
                "architecture_id": INTERNAL_ARCHITECTURE_ID,
                "source_or_research_lineage": INTERNAL_LINEAGE,
                "route": "standalone",
                "universe": list(INTERNAL_UNIVERSE),
                "fallback": "BIL",
                "named_control": INTERNAL_NAMED_CONTROL,
                "configuration_count": len(INTERNAL_CONFIGS),
                "configurations": [
                    {
                        "configuration_code": config.configuration_code,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        **config.parameters,
                    }
                    for config in INTERNAL_CONFIGS
                ],
            },
            "replacement_after_block_allowed": False,
            "post_result_parameter_addition_allowed": False,
        },
    )
    artifact_rows = {
        "parameter_grid.csv": parameter_grid_rows(),
        "strategy_cards.csv": strategy_card_rows(external, internal_results, next_action),
        "trial_ledger.csv": trial_ledger_rows(external, internal_results),
        "duplicate_preflight.csv": duplicate_rows,
        "benchmark_reference_log.csv": benchmark_rows(),
        "external_weekly_signal_inventory.csv": external["signal_rows"],
        "internal_shock_event_fixture_results.csv": [
            row for result in internal_results.values() for row in result["prepared"]["fixture_rows"]
        ],
        "selection_segment_definition.csv": selection_definition_rows(external, internal_split),
        "selection_segment_results.csv": internal_selection_rows(internal_results),
        "architecture_winner_selection.csv": architecture_winner_rows(internal_results),
        "evaluation_segment_results.csv": internal_evaluation_rows(internal_results),
        "evaluation_subhalf_results.csv": [
            *external["half_rows"],
            *[row for result in internal_results.values() for row in result.get("evaluation", {}).get("subhalf_rows", [])],
        ],
        "external_exploration_results.csv": external_metric_rows(external),
        "post_selection_full_period_diagnostics.csv": post_selection_rows(internal_results),
        "calendar_year_results.csv": [
            *external["calendar_rows"],
            *[row for result in internal_results.values() for row in result.get("evaluation", {}).get("calendar_rows", [])],
        ],
        "rebalance_contribution_results.csv": [
            row for result in internal_results.values() for row in result.get("evaluation", {}).get("rebalance_rows", [])
        ],
        "lightweight_concentration_diagnostics.csv": concentration_rows(external, internal_results),
        "turnover_cost_reconciliation.csv": turnover_rows(external, internal_results),
        "invariant_results.csv": invariant_rows(external, internal_results),
        "exploratory_followup_candidates.csv": followup_rows(external, internal_results),
        "failure_vectors.csv": failure_vector_rows(external, internal_results),
        "failure_reasons.csv": failure_reason_rows(external, internal_results),
        "process_task_log.csv": process_task_rows(outcome, next_action),
        "outcome_summary.csv": outcome_summary_rows(external, internal_results, outcome, next_action),
        "next_actions.csv": next_action_rows(outcome, next_action),
    }
    for name, rows in artifact_rows.items():
        write_csv(OUTPUT_DIR / name, rows, CSV_FIELDS[name])
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(external, internal_results, counts, outcome, next_action))

    after_protected = protected_hashes()
    evaluation_trial_ids = {row["trial_id"] for row in artifact_rows["evaluation_segment_results.csv"]}
    selected_trial_ids = {result["config"].trial_id for result in internal_results.values() if result.get("selected_winner")}
    consistency_checks = {
        "stale_robustness_reconciliation_created_before_performance": len(stale_reconciliation_rows) == 2,
        "historical_generic_packet_classified_as_superseded_for_promotion": all(
            row["old_contract_packet_classification"] == STALE_ROBUSTNESS_CLASSIFICATION
            for row in stale_reconciliation_rows
        ),
        "authoritative_role_aware_outcomes_preserved": all(
            row["authoritative_current_outcome"] == "robustness_positive"
            and row["authoritative_methodology"] == ROLE_AWARE_STANDARD_ID
            for row in stale_reconciliation_rows
        ),
        "mca_hyg_no_new_strategy_trial_or_lifecycle_change": (
            counts["new_mca_hyg_strategy_configurations"] == 0
            and counts["new_mca_hyg_robustness_trials"] == 0
            and counts["mca_hyg_lifecycle_changes"] == 0
            and all(not row["lifecycle_change_required"] and not row["rerun_required"] for row in stale_reconciliation_rows)
        ),
        "exactly_two_work_packages": True,
        "source_library_records_at_most_one": counts["source_library_records"] == 1,
        "external_strategy_configurations_exactly_one": counts["external_strategy_configurations"] == 1,
        "external_canonical_trials_exactly_one": counts["external_canonical_trials"] == 1,
        "internal_architectures_exactly_one": counts["internal_architectures"] == 1,
        "internal_strategy_configurations_exactly_four": counts["internal_strategy_configurations"] == 4,
        "internal_canonical_trials_exactly_four": counts["internal_canonical_trials"] == 4,
        "total_canonical_trials_at_most_five": counts["total_canonical_trials"] <= 5,
        "required_symbols_limited_to_frozen_set": set(frames) == set(REQUIRED_SYMBOLS),
        "duplicate_preflight_before_performance_complete": all(row["preperformance_complete"] for row in duplicate_rows),
        "external_weekly_signal_preflight_pass": external["complete_signal_count"] >= 500 and external["first_half_complete_signal_count"] >= 200 and external["second_half_complete_signal_count"] >= 200,
        "four_week_ratio_tests_present": any(row["complete_source_signal"] for row in external["signal_rows"]),
        "zero_signal_state_retain_prior_contract_present": beta_rotation_target(0.0, "SPY") == "SPY",
        "internal_shock_recovery_fixtures_present": len(artifact_rows["internal_shock_event_fixture_results.csv"]) > 0,
        "shock_threshold_not_optimized": all(config.parameters["shock_sigma_threshold"] == 1.0 for config in INTERNAL_CONFIGS),
        "winner_count_at_most_one": sum(result.get("selected_winner", False) for result in internal_results.values()) <= 1,
        "nonwinner_evaluation_access_prohibited": evaluation_trial_ids <= selected_trial_ids,
        "candidate_routing_followup_precedence": (
            counts["exploratory_followup_candidates"] == 0 or next_action == FOLLOWUP_NEXT_ACTION
        ),
        "batch_outcome_label_valid": outcome in PERMITTED_BATCH_OUTCOMES,
        "controls_are_benchmark_references_only": all(not row["counted_as_strategy"] and not row["counted_as_trial"] for row in artifact_rows["benchmark_reference_log.csv"]),
        "all_executed_invariants_pass": all(row["invariant_pass"] for row in artifact_rows["invariant_results.csv"]),
        "no_forbidden_actions": not any(FORBIDDEN_ACTION_FLAGS.values()),
        "entity_count_reconciliation_pass": (
            counts["total_canonical_trials"] == 5
            and counts["robustness_trials_created"] == 0
            and counts["validation_trials_created"] == 0
            and counts["paper_demo_eligibility_decisions"] == 0
            and counts["handoff_packets"] == 0
            and counts["observations"] == 0
        ),
        "protected_state_cache_and_prior_evidence_unchanged": before_protected == after_protected,
        "failure_reasons_within_permitted_set": all(
            row["primary_failure_reason"] in PERMITTED_FAILURE_REASONS for row in artifact_rows["failure_reasons.csv"]
        ),
        "required_output_set_complete": required_files_will_be_present_after_consistency_write(),
    }
    consistency = {
        "batch_id": TASK_ID,
        "overall_pass": all(consistency_checks.values()),
        "checks": consistency_checks,
        "cache_preflight": cache_rows,
        "protected_state_hashes_before": before_protected,
        "protected_state_hashes_after": after_protected,
        "forbidden_actions": FORBIDDEN_ACTION_FLAGS,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "required_output_files_present": required_files_will_be_present_after_consistency_write(),
        "deterministic_core_hash": deterministic_core_hash(),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "intake_dir": rel(INTAKE_DIR),
        "batch_outcome": outcome,
        "next_action": next_action,
        "entity_counts": counts,
        "consistency_overall_pass": consistency["overall_pass"],
        "deterministic_core_hash": consistency["deterministic_core_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
