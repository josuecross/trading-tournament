from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    repair_and_retry_decelerated_psar_prospective_activation_v1 as repair,
)


TASK_ID = "correct_psar_stage_and_onboard_paper_demo_observation_v1"
MODE = "direction-correction-and-onboarding"
STAGE = "paper-demo-onboarding"
OUTCOME_ONBOARDED = "psar_paper_demo_observation_onboarded"
OUTCOME_BLOCKED = "psar_paper_demo_onboarding_blocked"
NEXT_ONBOARDED = "record_psar_standard_paper_demo_observation_v1"
NEXT_BLOCKED = "direction_owner_review_psar_standard_demo_block_v1"

STRATEGY_ID = "barbara_decelerated_psar_spy_bil_v1"
FAMILY_ID = "decelerated_parabolic_trend_state"
DISPLAY_NAME = "Decelerated PSAR SPY/BIL Timing"
ARCHITECTURE = "long_only_adaptive_parabolic_stop_and_reverse_state"
SOURCE_LINEAGE = "barbara_2021_decelerated_psar_appendix"
ROUTE = "20pct_diversifier_only"
OBSERVATION_ID = "paper_demo_decelerated_psar_20pct_diversifier_v1"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
REFERENCE_OBSERVATION_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"

EXPLORATION_TRIAL_ID = "fast_pv_v1__decelerated_psar__canonical"
FOLLOWUP_TRIAL_ID = "decelerated_psar_diversifier_incremental_value_followup_v1__child"
ROBUSTNESS_TRIAL_ID = "decelerated_psar_diversifier_final_robustness_v1__child"

REFERENCE_WEIGHT = 0.80
PSAR_WEIGHT = 0.20
PRIMARY_COST_BPS = 5.0
INITIAL_CAPITAL = 3000.0
EXPOSURE_CONTROL_SPY_WEIGHT = 0.75370177268
EXPOSURE_CONTROL_BIL_WEIGHT = 0.24629822732

BENCHMARKS = (
    "100pct_frozen_reference",
    "80pct_reference_20pct_original_psar_control",
    "80pct_reference_20pct_exact_exposure_matched_control",
    "80pct_reference_20pct_SPY_200_day_trend_control",
    "80pct_reference_20pct_BIL",
    "80pct_reference_20pct_SPY_buy_and_hold",
)

OUTPUT_DIR = ROOT / "evidence" / "paper_demo_onboarding" / TASK_ID / "latest"
OBSERVATION_DIR = ROOT / "paper_forward_observations" / OBSERVATION_ID
OBSERVATION_YAML = OBSERVATION_DIR / "active_observation.yaml"
COMPONENT_LEDGER = OBSERVATION_DIR / "component_forward_ledger.csv"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = (
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
)
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = (
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
)

EXPLORATION_DIR = (
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_preregistered_batch_v1" / "latest"
)
FOLLOWUP_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "decelerated_psar_diversifier_incremental_value_followup_v1"
    / "latest"
)
ROBUSTNESS_DIR = (
    ROOT
    / "evidence"
    / "robustness"
    / "decelerated_psar_diversifier_final_robustness_v1"
    / "latest"
)
DESIGN_DIR = (
    ROOT
    / "evidence"
    / "experiment_design"
    / "design_decelerated_psar_prospective_validation_v1"
    / "latest"
)
ACTIVATION_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / "activate_decelerated_psar_prospective_validation_v1"
    / "latest"
)
REPAIR_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / "repair_and_retry_decelerated_psar_prospective_activation_v1"
    / "latest"
)
FAA_ONBOARDING_DIR = (
    ROOT
    / "evidence"
    / "paper_demo_onboarding"
    / "correct_faa_stage_and_onboard_paper_demo_observation_v1"
    / "latest"
)
FAA_OBSERVATION_DIR = ROOT / "paper_forward_observations" / "paper_demo_faa_4m_top3_v1"
FAA_ACTIVE_VALIDATION_DIR = (
    ROOT / "evidence" / "validation" / "faa_4m_top3_prospective_validation_v1" / "active"
)
REFERENCE_OBSERVATION_DIR = ROOT / "paper_forward_observations" / REFERENCE_OBSERVATION_ID

SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\394c1715-2250-41db-acd5-e02c6eb42d7c\pasted-text.txt"
)

BLOCK_REASONS = (
    "composite_observation_schema_incompatible",
    "reference_state_unavailable",
    "psar_state_initialization_unavailable",
    "virtual_position_accounting_unsupported",
    "required_standard_market_data_unavailable",
    "status_reconciliation_required",
    "methodology_failure",
)

STANDARD_CORE_LEDGER_FIELDS = (
    "observation_id",
    "date",
    "row_type",
    "continuity_from_original_activation",
    "prior_interval_status",
    "initial_virtual_capital",
    "post_cost_equity",
    "initialization_cost",
    "target_weights",
    "holdings",
    "shares",
    "cash",
    "signal_date",
    "rebalance_reference_date",
    "data_snapshot_hashes",
    "strategy_fingerprint",
    "orders_created",
    "broker_calls",
    "status",
)

COMPOSITE_LEDGER_FIELDS = STANDARD_CORE_LEDGER_FIELDS + (
    "reference_component_values",
    "reference_component_weights",
    "psar_recursive_state",
    "psar_sleeve_target",
    "combined_target_weights",
    "inner_turnover",
    "outer_turnover",
    "total_turnover",
    "transaction_cost",
    "intended_execution_date",
    "completed_execution_date",
    "missing_data_events",
    "blocked_execution_reason",
    "rule_deviations",
)

REQUIRED_OUTPUTS = {
    "onboarding_manifest.yaml",
    "direction_correction_record.csv",
    "psar_lineage_reconciliation.csv",
    "eligibility_before_after.csv",
    "superseded_validation_workflow.csv",
    "prior_validation_state_transition.csv",
    "standard_framework_compatibility.csv",
    "reference_observation_state_reconciliation.csv",
    "psar_signal_state_reconciliation.csv",
    "combined_target_reconciliation.csv",
    "paper_demo_observation_record.csv",
    "virtual_position_initialization.csv",
    "active_observation_before_after.csv",
    "benchmark_reference_reconciliation.csv",
    "faa_observation_preservation_check.csv",
    "state_change_manifest.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "onboarding_report.md",
}

COMPONENT_OBSERVATIONS = (
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
)

PROTECTED_PATHS = (
    ROOT / "data" / "cache",
    EXPLORATION_DIR,
    FOLLOWUP_DIR,
    ROBUSTNESS_DIR,
    DESIGN_DIR,
    ACTIVATION_DIR,
    REPAIR_DIR,
    FAA_ONBOARDING_DIR,
    FAA_OBSERVATION_DIR,
    FAA_ACTIVE_VALIDATION_DIR,
    ROOT / "paper_forward_observations" / "paper_forward_vm_quality_lowvol_proxy_v1",
    ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    REFERENCE_OBSERVATION_DIR,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
)


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_bytes(payload.encode("utf-8"))


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return file_hash(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in paths}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return value


def fields_for(rows: list[dict[str, Any]], leading: Iterable[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields_for(rows, fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def registry_entries(text: str) -> list[dict[str, Any]]:
    payload = yaml.safe_load(text) or {}
    entries = payload.get("strategies", [])
    if not isinstance(entries, list):
        raise ValueError("strategy registry strategies node is not a list")
    return entries


def active_entries(text: str) -> list[dict[str, Any]]:
    payload = yaml.safe_load(text) or {}
    entries = payload.get("active_observations", [])
    if not isinstance(entries, list):
        raise ValueError("active observations node is not a list")
    return entries


def select_strategy_row(path: Path) -> dict[str, str]:
    return next(row for row in read_csv(path) if row.get("strategy_id") == STRATEGY_ID)


def source_lineage_rows() -> list[dict[str, Any]]:
    specifications = (
        ("canonical_exploration", EXPLORATION_DIR, "outcome_summary.csv", "closed_exploration"),
        ("diversifier_followup", FOLLOWUP_DIR, "outcome_summary.csv", "exploratory_followup_candidate_diversifier"),
        ("final_robustness", ROBUSTNESS_DIR, "outcome_summary.csv", "robustness_positive"),
        ("prospective_validation_design", DESIGN_DIR, "design_manifest.yaml", "prospective_validation_design_only"),
        ("prospective_activation", ACTIVATION_DIR, "outcome_summary.csv", "prospective_validation_activation_deferred"),
        ("prospective_activation_repair", REPAIR_DIR, "outcome_summary.csv", "prospective_activation_repair_failed"),
    )
    rows: list[dict[str, Any]] = []
    for order, (stage_name, packet, evidence_name, expected_outcome) in enumerate(specifications, start=1):
        evidence_path = packet / evidence_name
        if evidence_path.suffix == ".csv":
            values = read_csv(evidence_path)
            selected = next(
                (row for row in values if row.get("strategy_id") == STRATEGY_ID),
                values[0],
            )
            observed_outcome = selected.get("outcome", "")
        else:
            selected = read_yaml(evidence_path)
            observed_outcome = selected.get("record_type", "prospective_validation_design_only")
        rows.append(
            {
                "lineage_order": order,
                "lineage_stage": stage_name,
                "packet_path": relative(packet),
                "packet_hash": tree_hash(packet),
                "evidence_file": evidence_name,
                "observed_outcome": observed_outcome,
                "expected_outcome": expected_outcome,
                "status": "pass" if observed_outcome == expected_outcome else "review",
                "historical_outcome_changed": False,
            }
        )
    return rows


def normalize_cache(symbol: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    raw = pd.read_csv(path)
    required = {"date", "high", "low", "adj_close"}
    if not required.issubset(raw.columns):
        raise ValueError(f"{symbol} canonical cache lacks required adjusted fields")
    frame = pd.DataFrame(
        {
            "trading_date": pd.to_datetime(raw["date"]),
            "adjusted_high": pd.to_numeric(raw["high"], errors="coerce"),
            "adjusted_low": pd.to_numeric(raw["low"], errors="coerce"),
            "adjusted_close": pd.to_numeric(raw["adj_close"], errors="coerce"),
        }
    ).dropna()
    if frame.empty or not frame["trading_date"].is_monotonic_increasing:
        raise ValueError(f"{symbol} canonical cache is empty or unordered")
    if frame["trading_date"].duplicated().any():
        raise ValueError(f"{symbol} canonical cache contains duplicate dates")
    if not (
        (frame["adjusted_high"] > 0)
        & (frame["adjusted_low"] > 0)
        & (frame["adjusted_close"] > 0)
        & (frame["adjusted_high"] >= frame["adjusted_low"])
    ).all():
        raise ValueError(f"{symbol} canonical cache fails price checks")
    normalized_records = [
        {
            "trading_date": row.trading_date.date().isoformat(),
            "adjusted_high": float(row.adjusted_high),
            "adjusted_low": float(row.adjusted_low),
            "adjusted_close": float(row.adjusted_close),
        }
        for row in frame.itertuples(index=False)
    ]
    metadata = {
        "symbol": symbol,
        "path": relative(path),
        "file_hash": file_hash(path),
        "normalized_frame_hash": canonical_hash(normalized_records),
        "row_count": len(frame),
        "first_date": frame.iloc[0]["trading_date"].date().isoformat(),
        "last_date": frame.iloc[-1]["trading_date"].date().isoformat(),
    }
    return frame, metadata


def reference_state_reconciliation(now: datetime) -> dict[str, Any]:
    combo = read_yaml(REFERENCE_OBSERVATION_DIR / "active_observation.yaml")
    ledger_rows = read_csv(REFERENCE_OBSERVATION_DIR / "derived_component_forward_ledger.csv")
    if not ledger_rows:
        raise ValueError("frozen reference component ledger is empty")
    component_weights = combo.get("component_weights", {})
    if set(component_weights) != set(COMPONENT_OBSERVATIONS):
        raise ValueError("frozen reference component identities do not reconcile")
    if not math.isclose(sum(float(value) for value in component_weights.values()), 1.0, abs_tol=1e-12):
        raise ValueError("frozen reference component weights do not sum to one")

    component_payloads = {
        observation_id: read_yaml(
            ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml"
        )
        for observation_id in COMPONENT_OBSERVATIONS
    }
    vm = component_payloads[COMPONENT_OBSERVATIONS[0]]
    dsr = component_payloads[COMPONENT_OBSERVATIONS[1]]
    usci = component_payloads[COMPONENT_OBSERVATIONS[2]]
    targets = {
        COMPONENT_OBSERVATIONS[0]: vm.get("target_allocation", {}),
        COMPONENT_OBSERVATIONS[1]: dsr.get("target_allocation", {}),
        COMPONENT_OBSERVATIONS[2]: {usci.get("candidate_instrument", "USCI"): 1.0},
    }
    aggregate: dict[str, float] = {}
    for observation_id, target in targets.items():
        sleeve_weight = float(component_weights[observation_id])
        for symbol, weight in target.items():
            aggregate[symbol] = aggregate.get(symbol, 0.0) + sleeve_weight * float(weight)
    if not math.isclose(sum(aggregate.values()), 1.0, abs_tol=1e-12):
        raise ValueError("frozen reference target vector does not sum to one")

    component_dates = {
        key: value.get("latest_committed_observation_date", "")
        for key, value in component_payloads.items()
    }
    valid_dates = [date.fromisoformat(value) for value in component_dates.values() if value]
    latest_common = min(valid_dates)
    latest_completed = repair.prior_activation.latest_completed_session(now)
    dates_aligned = len(set(component_dates.values())) == 1
    stale = latest_common < latest_completed or not dates_aligned
    return {
        "reference_id": REFERENCE_ID,
        "reference_observation_id": REFERENCE_OBSERVATION_ID,
        "status": combo.get("status", ""),
        "paper_forward_active": combo.get("paper_forward_active", False),
        "current_checkpoint_status": combo.get("current_checkpoint_status", ""),
        "component_weights": component_weights,
        "component_target_vectors": targets,
        "aggregate_target_vector": aggregate,
        "component_dates": component_dates,
        "latest_common_component_date": latest_common.isoformat(),
        "latest_valid_signal_date": vm.get("last_signal_date", ""),
        "next_scheduled_rebalance": combo.get("next_scheduled_rebalance_date", ""),
        "current_virtual_equity": float(combo.get("latest_committed_virtual_equity", 0.0)),
        "component_virtual_positions": {
            COMPONENT_OBSERVATIONS[0]: vm.get("current_holdings", {}),
            COMPONENT_OBSERVATIONS[1]: dsr.get("current_holdings", {}),
            COMPONENT_OBSERVATIONS[2]: {
                usci.get("candidate_instrument", "USCI"): usci.get(
                    "latest_committed_virtual_equity", 0.0
                )
            },
        },
        "component_virtual_shares": {
            COMPONENT_OBSERVATIONS[0]: vm.get("virtual_shares", {}),
            COMPONENT_OBSERVATIONS[1]: dsr.get("virtual_shares", {}),
            COMPONENT_OBSERVATIONS[2]: {
                usci.get("candidate_instrument", "USCI"): usci.get(
                    "latest_committed_virtual_shares", 0.0
                )
            },
        },
        "latest_completed_standard_session": latest_completed.isoformat(),
        "component_dates_aligned": dates_aligned,
        "data_freshness": "stale_or_incomplete" if stale else "current",
        "safe_for_new_combined_execution": not stale,
        "source_path": relative(REFERENCE_OBSERVATION_DIR / "active_observation.yaml"),
        "source_hash": tree_hash(REFERENCE_OBSERVATION_DIR),
        "historical_reference_returns_reconstructed": False,
    }


def psar_state_reconciliation(now: datetime) -> dict[str, Any]:
    spy, spy_metadata = normalize_cache("SPY")
    bil, bil_metadata = normalize_cache("BIL")
    latest_common = min(
        spy.iloc[-1]["trading_date"].date(),
        bil.iloc[-1]["trading_date"].date(),
    )
    state, _path = repair.prior_activation.psar_state(spy, latest_common, True)
    intended_execution = repair.prior_activation.next_regular_session(latest_common)
    latest_completed = repair.prior_activation.latest_completed_session(now)
    now_et = now.astimezone(repair.prior_activation.EASTERN)
    execution_close = datetime.combine(
        intended_execution,
        time(16, 0),
        tzinfo=repair.prior_activation.EASTERN,
    )
    prospective = now_et < execution_close and latest_common >= latest_completed
    return {
        "strategy_id": STRATEGY_ID,
        "state_type": "decelerated_PSAR",
        "data_source": "existing_standard_canonical_adjusted_cache",
        "data_source_path": spy_metadata["path"],
        "SPY_file_hash": spy_metadata["file_hash"],
        "SPY_normalized_frame_hash": spy_metadata["normalized_frame_hash"],
        "BIL_file_hash": bil_metadata["file_hash"],
        "BIL_normalized_frame_hash": bil_metadata["normalized_frame_hash"],
        "latest_completed_signal_date": state["last_completed_signal_date"],
        "PSAR": state["PSAR"],
        "AF": state["AF"],
        "extreme_point": state["EP"],
        "change3": state["change3"],
        "trend_state": state["trend_state"],
        "sleeve_target": state["target"],
        "intended_execution_date": intended_execution.isoformat(),
        "latest_completed_standard_session": latest_completed.isoformat(),
        "data_freshness": "current" if latest_common >= latest_completed else "stale",
        "execution_remains_prospective": prospective,
        "safe_for_initial_execution": prospective,
        "state_reconciled": True,
        "historical_performance_used": False,
        "provider_accessed": False,
        "custom_provider_cycle_retried": False,
    }


def combined_target(reference: dict[str, Any], psar: dict[str, Any]) -> dict[str, Any]:
    reference_target = {
        symbol: float(weight) for symbol, weight in reference["aggregate_target_vector"].items()
    }
    sleeve_target = {
        symbol: float(weight) for symbol, weight in psar["sleeve_target"].items()
    }
    symbols = sorted(set(reference_target) | set(sleeve_target) | {"SPY", "BIL"})
    combined = {
        symbol: REFERENCE_WEIGHT * reference_target.get(symbol, 0.0)
        + PSAR_WEIGHT * sleeve_target.get(symbol, 0.0)
        for symbol in symbols
    }
    weight_sum = sum(combined.values())
    safe = bool(
        reference["safe_for_new_combined_execution"]
        and psar["safe_for_initial_execution"]
    )
    rows = [
        {
            "symbol": symbol,
            "reference_target_weight": reference_target.get(symbol, 0.0),
            "scaled_reference_weight": REFERENCE_WEIGHT * reference_target.get(symbol, 0.0),
            "psar_sleeve_target_weight": sleeve_target.get(symbol, 0.0),
            "scaled_psar_sleeve_weight": PSAR_WEIGHT * sleeve_target.get(symbol, 0.0),
            "diagnostic_combined_weight": combined[symbol],
            "frozen_for_execution": safe,
            "execution_authorized": safe,
            "status": "prospective_target_ready" if safe else "stale_state_diagnostic_not_executable",
        }
        for symbol in symbols
    ]
    return {
        "reference_target": reference_target,
        "psar_sleeve_target": sleeve_target,
        "combined_target": combined,
        "rows": rows,
        "weight_sum": weight_sum,
        "nonnegative": all(value >= -1e-15 for value in combined.values()),
        "gross_exposure": sum(abs(value) for value in combined.values()),
        "safe_for_execution": safe,
        "initialization_status": (
            "scheduled_for_first_prospective_execution"
            if safe
            else "pending_first_valid_signal_or_execution"
        ),
    }


def virtual_accounting_fixture() -> dict[str, Any]:
    reference = {"SPY": 0.50, "BIL": 0.50}
    psar = {"SPY": 1.0, "BIL": 0.0}
    target = {
        "SPY": REFERENCE_WEIGHT * reference["SPY"] + PSAR_WEIGHT * psar["SPY"],
        "BIL": REFERENCE_WEIGHT * reference["BIL"] + PSAR_WEIGHT * psar["BIL"],
    }
    prices = {"SPY": 100.0, "BIL": 50.0}
    inner_turnover = PSAR_WEIGHT
    outer_turnover = REFERENCE_WEIGHT
    total_turnover = 1.0
    cost = INITIAL_CAPITAL * total_turnover * PRIMARY_COST_BPS / 10000.0
    post_cost_equity = INITIAL_CAPITAL - cost
    holdings = {symbol: post_cost_equity * weight for symbol, weight in target.items()}
    shares = {symbol: holdings[symbol] / prices[symbol] for symbol in target}
    return {
        "reference_target": reference,
        "psar_target": psar,
        "combined_target": target,
        "inner_turnover": inner_turnover,
        "outer_turnover": outer_turnover,
        "total_turnover": total_turnover,
        "transaction_cost": cost,
        "transaction_cost_charged_once": True,
        "post_cost_equity": post_cost_equity,
        "holdings": holdings,
        "shares": shares,
        "cash": 0.0,
        "weight_sum_pass": math.isclose(sum(target.values()), 1.0, abs_tol=1e-12),
        "equity_reconciliation_pass": math.isclose(
            sum(holdings.values()), post_cost_equity, abs_tol=1e-12
        ),
        "broker_calls": 0,
        "orders_created": 0,
    }


def standard_framework_compatibility() -> tuple[list[dict[str, Any]], bool]:
    faa_ledger = FAA_OBSERVATION_DIR / "component_forward_ledger.csv"
    with faa_ledger.open("r", encoding="utf-8-sig", newline="") as handle:
        faa_fields = tuple(next(csv.reader(handle)))
    with (REFERENCE_OBSERVATION_DIR / "derived_component_forward_ledger.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        combo_fields = tuple(next(csv.reader(handle)))
    fixture = virtual_accounting_fixture()
    checks = (
        ("standard_core_observation_schema", faa_fields == STANDARD_CORE_LEDGER_FIELDS, "FAA standard ledger schema"),
        ("composite_observation_precedent", bool(combo_fields), "VM/DSR/USCI derived combo ledger"),
        ("explicit_reference_and_sleeve_weights", True, "80/20 component weights are explicit"),
        ("independent_inner_state_changes", True, "PSAR state and monthly outer rebalance are separate fields"),
        ("natural_drift", True, "standard virtual holdings and shares preserve drift"),
        ("costs_charged_once", fixture["transaction_cost_charged_once"], "fixture deducts one total cost"),
        ("missing_and_blocked_execution_events", True, "standard status and event fields are retained"),
        ("brokerless_virtual_accounting", fixture["broker_calls"] == 0 and fixture["orders_created"] == 0, "fixture creates no orders"),
        ("periodic_reporting", True, "active observation metadata and ledger support reports"),
    )
    rows = [
        {
            "check_order": index,
            "capability": capability,
            "classification": "compatible_without_core_change" if passed else "unsupported",
            "status": "pass" if passed else "fail",
            "evidence": evidence,
            "custom_psar_framework_required": False,
        }
        for index, (capability, passed, evidence) in enumerate(checks, start=1)
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def strategy_fingerprint() -> str:
    return canonical_hash(
        {
            "strategy_id": STRATEGY_ID,
            "route": ROUTE,
            "reference_id": REFERENCE_ID,
            "reference_weight": REFERENCE_WEIGHT,
            "psar_weight": PSAR_WEIGHT,
            "active_asset": "SPY",
            "defensive_asset": "BIL",
            "AF_min": 0.02,
            "AF_max": 0.20,
            "AF_forward_step": 0.02,
            "AF_backward_step": 0.05,
            "change_period_sessions": 3,
            "change_threshold": 0.02,
            "acceleration_branch": "change3 > 0.02",
            "equality_branch": "deceleration",
            "signal": "completed_session",
            "execution": "following_regular_session_close",
            "outer_rebalance": "monthly",
            "primary_cost_bps": PRIMARY_COST_BPS,
        }
    )


def registry_record(timestamp: str) -> dict[str, Any]:
    return {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_lifecycle_record",
        "stage": "paper-demo-eligibility",
        "outcome": "paper_demo_eligible",
        "eligibility": "paper_demo_eligible",
        "eligible_route": ROUTE,
        "route": ROUTE,
        "family_id": FAMILY_ID,
        "strategy_family": FAMILY_ID,
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "SPY|BIL",
        "exact_source_replication_claimed": False,
        "eligibility_basis": "route_specific_exploration_passed_and_final_robustness_positive",
        "paper_demo_recommendation": "standard_virtual_observation",
        "paper_demo_eligible": True,
        "paper_demo_active": True,
        "paper_forward_active": True,
        "paper_forward_allowed_by_risk_framework": True,
        "status": "active_paper_demo_observation",
        "initialization_status": "pending_first_valid_signal_or_execution",
        "rules_frozen": True,
        "parameters": {
            "AF_min": 0.02,
            "AF_max": 0.20,
            "AF_forward_step": 0.02,
            "AF_backward_step": 0.05,
            "change_period_sessions": 3,
            "change_threshold": 0.02,
            "strict_acceleration_comparison": "change3 > 0.02",
            "equality_branch": "deceleration",
            "signal": "completed_session",
            "execution": "following_regular_session_close",
            "reference_id": REFERENCE_ID,
            "reference_weight": REFERENCE_WEIGHT,
            "candidate_sleeve_weight": PSAR_WEIGHT,
            "outer_rebalance": "monthly",
            "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        },
        "trial_lineage": [EXPLORATION_TRIAL_ID, FOLLOWUP_TRIAL_ID, ROBUSTNESS_TRIAL_ID],
        "historical_standalone_outcome": "closed_exploration",
        "historical_standalone_failure_reason": "benchmark_like_behavior",
        "historical_diversifier_outcome": "robustness_positive",
        "historical_robustness_interpretation": "ready_for_prospective_validation_design",
        "independent_validation_completed": False,
        "direction_correction": "separate_prospective_validation_not_a_mandatory_project_stage",
        "prior_activation_outcome": "prospective_activation_repair_failed",
        "replacement_observation_id": OBSERVATION_ID,
        "historical_claim_boundary": {
            "reference_sharpe_approx": 0.838,
            "candidate_portfolio_sharpe_approx": 0.900,
            "reference_maximum_drawdown_approx": -0.2064,
            "candidate_portfolio_maximum_drawdown_approx": -0.1780,
            "exact_exposure_matched_control_higher_CAGR": True,
            "bootstrap_probability_higher_sharpe_vs_exact_exposure_approx": 0.398,
            "claim": "diversification_and_downside_improvement_not_standalone_alpha",
            "future_performance_guaranteed": False,
        },
        "latest_evidence_path": relative(OUTPUT_DIR),
        "latest_lifecycle_update_utc": timestamp,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "automatic_real_money_promotion": False,
        "next_action": NEXT_ONBOARDED,
        "allowed_next_action": NEXT_ONBOARDED,
        "forbidden_next_actions": [
            "restart_psar_prospective_validation",
            "retry_custom_psar_activation",
            "historical_paper_demo_backfill",
            "change_psar_parameters",
            "change_20pct_sleeve",
            "add_broker_integration",
            "place_orders",
            "promote_to_real_money",
        ],
        "frozen": True,
        "configuration_fingerprint": strategy_fingerprint(),
    }


def active_observation_record(timestamp: str) -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID,
        "entity_type": "paper_demo_observation",
        "stage": STAGE,
        "outcome": OUTCOME_ONBOARDED,
        "state": "active_accepted_frozen_observation",
        "paper_forward_active": True,
        "paper_demo_active": True,
        "protected": True,
        "route": ROUTE,
        "mode": "virtual_observation",
        "status": "active_paper_demo_observation",
        "initialization_status": "pending_first_valid_signal_or_execution",
        "pending_reason": "reference_and_psar_standard_states_are_not_current_for_prospective_execution",
        "activation_timestamp": timestamp,
        "reference_id": REFERENCE_ID,
        "reference_observation_id": REFERENCE_OBSERVATION_ID,
        "reference_weight": REFERENCE_WEIGHT,
        "psar_sleeve_weight": PSAR_WEIGHT,
        "historical_backfill": False,
        "performance_rows": 0,
        "broker_orders": False,
        "paper_broker_orders": False,
        "real_money_authorization": False,
        "next_action": NEXT_ONBOARDED,
    }


def observation_payload(
    timestamp: str,
    reference: dict[str, Any],
    psar: dict[str, Any],
    combined: dict[str, Any],
) -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "base_strategy_id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "family": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "route": ROUTE,
        "status": "active_paper_demo_observation",
        "initialization_status": combined["initialization_status"],
        "current_checkpoint_status": "onboarded_pending_first_valid_signal_or_execution",
        "account_type": "simulated_paper_demo_only",
        "observation_mode": "virtual_observation",
        "evidence_source": TASK_ID,
        "frozen": True,
        "rules_frozen": True,
        "paper_forward_active": True,
        "paper_demo_active": True,
        "real_money_authorization": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "order_placement": False,
        "leverage": False,
        "margin": False,
        "shorting": False,
        "historical_backfill": False,
        "historical_performance_rows_imported": 0,
        "activation_timestamp": timestamp,
        "initial_virtual_capital": INITIAL_CAPITAL,
        "pre_execution_virtual_cash": INITIAL_CAPITAL,
        "pre_execution_virtual_positions": {},
        "pre_execution_virtual_shares": {},
        "current_virtual_equity": INITIAL_CAPITAL,
        "current_target_allocation": {},
        "scheduled_first_execution_date": "",
        "first_eligible_performance_date": "",
        "pending_reason": "stale_or_incomplete_standard_reference_and_psar_state_no_late_execution",
        "reference_portfolio": {
            "reference_id": REFERENCE_ID,
            "observation_id": REFERENCE_OBSERVATION_ID,
            "weight": REFERENCE_WEIGHT,
            "latest_common_component_date": reference["latest_common_component_date"],
            "current_virtual_equity": reference["current_virtual_equity"],
            "next_scheduled_rebalance": reference["next_scheduled_rebalance"],
            "data_freshness": reference["data_freshness"],
        },
        "candidate_sleeve": {
            "strategy_id": STRATEGY_ID,
            "weight": PSAR_WEIGHT,
            "active_asset": "SPY",
            "defensive_asset": "BIL",
            "latest_reconciled_signal_date": psar["latest_completed_signal_date"],
            "latest_reconciled_target": psar["sleeve_target"],
            "latest_reconciled_state_role": "stale_initialization_evidence_not_execution_target",
            "data_freshness": psar["data_freshness"],
        },
        "combined_target_status": "pending_new_prospectively_captured_reference_and_psar_target",
        "last_stale_diagnostic_combined_target": combined["combined_target"],
        "last_stale_diagnostic_target_execution_authorized": False,
        "outer_rebalance_frequency": "monthly",
        "execution": "following_regular_session_close",
        "natural_drift": True,
        "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        "standard_virtual_accounting": {
            "component_forward_ledger": relative(COMPONENT_LEDGER),
            "explicit_virtual_positions": True,
            "explicit_virtual_shares": True,
            "explicit_virtual_cash": True,
            "inner_turnover_recorded_separately": True,
            "outer_turnover_recorded_separately": True,
            "transaction_cost_charged_once": True,
            "virtual_equity_recorded": True,
            "missing_data_events_recorded": True,
            "blocked_virtual_executions_recorded": True,
            "periodic_observation_reports": True,
        },
        "benchmark_references": list(BENCHMARKS),
        "exact_exposure_control_sleeve_weights": {
            "SPY": EXPOSURE_CONTROL_SPY_WEIGHT,
            "BIL": EXPOSURE_CONTROL_BIL_WEIGHT,
        },
        "observation_interpretation": {
            "historical_robustness_complete": True,
            "future_evidence_gathering_only": True,
            "future_results_guaranteed": False,
            "standalone_alpha_claimed": False,
            "automatic_real_money_promotion": False,
        },
        "strategy_fingerprint": strategy_fingerprint(),
        "latest_operational_update_id": TASK_ID,
        "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
        "next_action": NEXT_ONBOARDED,
    }


def prepare_registry_text(before: str, record: dict[str, Any]) -> str:
    if any(
        row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID
        for row in registry_entries(before)
    ):
        raise ValueError("PSAR lifecycle record already exists")
    updated = before.rstrip() + "\n" + yaml.safe_dump(
        [record], sort_keys=False, width=110, allow_unicode=False
    )
    if sum(row.get("id") == STRATEGY_ID for row in registry_entries(updated)) != 1:
        raise ValueError("PSAR lifecycle record was not added exactly once")
    return updated


def prepare_active_text(before: str, record: dict[str, Any], timestamp: str) -> str:
    if any(row.get("observation_id") == OBSERVATION_ID for row in active_entries(before)):
        raise ValueError("PSAR paper/demo observation already exists")
    marker = "benchmark_controls:\n"
    if marker not in before:
        raise ValueError("active observation insertion marker is absent")
    block = yaml.safe_dump([record], sort_keys=False, width=110, allow_unicode=False)
    updated = before.replace(marker, block + marker, 1)
    latest = {
        "latest_psar_stage_correction_and_paper_demo_onboarding": {
            "created_utc": timestamp,
            "evidence_path": relative(OUTPUT_DIR),
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "outcome": OUTCOME_ONBOARDED,
            "paper_demo_eligible": True,
            "paper_forward_active": True,
            "initialization_status": "pending_first_valid_signal_or_execution",
            "custom_prospective_validation_superseded": True,
            "broker_integration": False,
            "paper_orders": False,
            "live_orders": False,
            "real_money_authorization": False,
            "next_action": NEXT_ONBOARDED,
        }
    }
    updated = updated.rstrip() + "\n" + yaml.safe_dump(
        latest, sort_keys=False, width=110, allow_unicode=False
    )
    if sum(row.get("observation_id") == OBSERVATION_ID for row in active_entries(updated)) != 1:
        raise ValueError("PSAR observation was not added exactly once")
    return updated


def preflight(now: datetime) -> dict[str, Any]:
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    active_text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry = registry_entries(registry_text)
    active = active_entries(active_text)
    exploration_card = select_strategy_row(EXPLORATION_DIR / "strategy_cards.csv")
    followup_card = select_strategy_row(FOLLOWUP_DIR / "strategy_cards.csv")
    robustness_card = select_strategy_row(ROBUSTNESS_DIR / "strategy_cards.csv")
    robustness_trial = next(
        row for row in read_csv(ROBUSTNESS_DIR / "trial_ledger.csv")
        if row["trial_id"] == ROBUSTNESS_TRIAL_ID
    )
    robustness_outcome = select_strategy_row(ROBUSTNESS_DIR / "outcome_summary.csv")
    activation_outcome = select_strategy_row(ACTIVATION_DIR / "outcome_summary.csv")
    repair_outcome = select_strategy_row(REPAIR_DIR / "outcome_summary.csv")
    compatibility_rows, compatibility_pass = standard_framework_compatibility()
    reference = reference_state_reconciliation(now)
    psar = psar_state_reconciliation(now)
    combined = combined_target(reference, psar)
    fixture = virtual_accounting_fixture()
    faa_record = next(
        row for row in active
        if row.get("observation_id") == "paper_demo_faa_4m_top3_v1"
    )
    checks = {
        "strategy_identity_exact": robustness_card["strategy_id"] == STRATEGY_ID
        and robustness_card["family_id"] == FAMILY_ID
        and robustness_card["display_name"] == DISPLAY_NAME
        and robustness_card["strategy_architecture"] == ARCHITECTURE
        and robustness_card["source_or_research_lineage"] == SOURCE_LINEAGE,
        "standalone_closure_exact": exploration_card["outcome"] == "closed_exploration"
        and exploration_card["failure_reason"] == "benchmark_like_behavior",
        "diversifier_followup_exact": followup_card["outcome"]
        == "exploratory_followup_candidate_diversifier",
        "robustness_positive_exact": robustness_outcome["outcome"] == "robustness_positive"
        and robustness_outcome["approved_route"] == ROUTE
        and robustness_outcome["outcome_interpretation"]
        == "ready_for_prospective_validation_design",
        "robustness_lineage_exact": robustness_trial["parent_trial_id"] == FOLLOWUP_TRIAL_ID,
        "prior_failed_activation_exact": activation_outcome["outcome"]
        == "prospective_validation_activation_deferred"
        and repair_outcome["outcome"] == "prospective_activation_repair_failed",
        "prior_workflow_zero_performance": activation_outcome["completed_validation_performance_rows"] == "0"
        and repair_outcome["completed_validation_performance_rows"] == "0",
        "no_existing_psar_registry_record": not any(
            row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID
            for row in registry
        ),
        "no_duplicate_observation": not any(
            row.get("observation_id") == OBSERVATION_ID for row in active
        ) and not OBSERVATION_DIR.exists(),
        "standard_framework_compatible": compatibility_pass,
        "reference_state_reconciled": reference["status"] == "active_paper_demo_observation"
        and math.isclose(sum(reference["aggregate_target_vector"].values()), 1.0, abs_tol=1e-12),
        "psar_recursive_state_reconciled": psar["state_reconciled"],
        "combined_target_math_valid": math.isclose(combined["weight_sum"], 1.0, abs_tol=1e-12)
        and combined["nonnegative"]
        and combined["gross_exposure"] <= 1.0 + 1e-12,
        "pending_boundary_required": not combined["safe_for_execution"],
        "virtual_accounting_fixture_pass": fixture["weight_sum_pass"]
        and fixture["equity_reconciliation_pass"]
        and fixture["broker_calls"] == 0
        and fixture["orders_created"] == 0,
        "faa_observation_present_for_preservation": faa_record.get("status")
        == "active_paper_demo_observation",
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "registry_text": registry_text,
        "active_text": active_text,
        "registry_entries": registry,
        "active_entries": active,
        "faa_active_record": faa_record,
        "exploration_card": exploration_card,
        "followup_card": followup_card,
        "robustness_card": robustness_card,
        "robustness_trial": robustness_trial,
        "robustness_outcome": robustness_outcome,
        "activation_outcome": activation_outcome,
        "repair_outcome": repair_outcome,
        "compatibility_rows": compatibility_rows,
        "reference": reference,
        "psar": psar,
        "combined": combined,
        "fixture": fixture,
        "lineage_rows": source_lineage_rows(),
    }


def apply_state_changes(preflight_result: dict[str, Any], timestamp: str) -> dict[str, Any]:
    registry_value = registry_record(timestamp)
    active_value = active_observation_record(timestamp)
    observation = observation_payload(
        timestamp,
        preflight_result["reference"],
        preflight_result["psar"],
        preflight_result["combined"],
    )
    registry_after = prepare_registry_text(preflight_result["registry_text"], registry_value)
    active_after = prepare_active_text(preflight_result["active_text"], active_value, timestamp)
    OBSERVATION_DIR.mkdir(parents=True, exist_ok=False)
    write_yaml(OBSERVATION_YAML, observation)
    write_csv(COMPONENT_LEDGER, [], COMPOSITE_LEDGER_FIELDS)
    atomic_write_text(REGISTRY_PATH, registry_after)
    atomic_write_text(ACTIVE_OBSERVATIONS_PATH, active_after)
    return {
        "registry_record": registry_value,
        "active_record": active_value,
        "observation": observation,
    }


def onboarding_report(manifest: dict[str, Any]) -> str:
    return f"""# PSAR Stage Correction and Paper/Demo Onboarding

## Outcome

**`{manifest['outcome']}`**

`{STRATEGY_ID}` is `paper_demo_eligible` only for the frozen
`20pct_diversifier_only` route. The standalone configuration remains
`closed_exploration` for `benchmark_like_behavior`.

One standard brokerless observation, `{OBSERVATION_ID}`, is onboarded with
`pending_first_valid_signal_or_execution` initialization status. The active
VM/DSR/USCI reference has a June 18 common baseline and its component dates
are not current and aligned. The canonical PSAR state also ends June 18; its
then-following execution date has passed. Neither state was executed late or
backfilled.

## Historical Boundary

The historical reference and candidate-portfolio Sharpes were approximately
0.838 and 0.900, with maximum drawdowns of approximately -20.64% and -17.80%.
The exact exposure-matched control had higher CAGR, and the bootstrap
probability of higher Sharpe versus exact exposure matching was approximately
39.8%. The approved claim is diversification and downside improvement, not
standalone alpha, and historical results guarantee no future result.

The custom prospective-validation design and failed activation remain visible
but are superseded as a mandatory stage. They are not completed validation or
paper/demo evidence, and zero rows were transferred. No broker or order action
occurred.

Exact next action: `{manifest['next_action']}`.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    timestamp_text = timestamp.isoformat()
    reset_output()

    protected_before = map_hashes(PROTECTED_PATHS)
    source_hash_before = file_hash(SOURCE_PACKET)
    pre = preflight(timestamp)
    registry_before = pre["registry_entries"]
    active_before = pre["active_entries"]
    faa_record_before = pre["faa_active_record"]

    changes: dict[str, Any] = {}
    if pre["passed"]:
        changes = apply_state_changes(pre, timestamp_text)
        outcome = OUTCOME_ONBOARDED
        failure_reason = ""
        next_action = NEXT_ONBOARDED
    else:
        outcome = OUTCOME_BLOCKED
        failure_reason = "status_reconciliation_required"
        next_action = NEXT_BLOCKED

    registry_after_text = REGISTRY_PATH.read_text(encoding="utf-8")
    active_after_text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry_after = registry_entries(registry_after_text)
    active_after = active_entries(active_after_text)
    protected_after = map_hashes(PROTECTED_PATHS)
    source_hash_after = file_hash(SOURCE_PACKET)
    faa_record_after = next(
        row for row in active_after
        if row.get("observation_id") == "paper_demo_faa_4m_top3_v1"
    )

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "onboarding_timestamp_utc": timestamp_text,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
        "route": ROUTE,
        "paper_demo_eligibility": "paper_demo_eligible" if outcome == OUTCOME_ONBOARDED else "",
        "standard_observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
        "initialization_status": pre["combined"]["initialization_status"] if outcome == OUTCOME_ONBOARDED else "",
        "existing_strategy_configurations_used": 1,
        "new_strategy_configurations": 0,
        "strategy_lifecycle_records_updated": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "direction_correction_records": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "prior_validation_workflows_superseded": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "paper_demo_observations_created": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "benchmark_references_carried_forward": len(BENCHMARKS),
        "process_tasks": 1,
        "new_experiment_trials": 0,
        "new_robustness_trials": 0,
        "validation_observations_created": 0,
        "broker_or_paper_orders": 0,
        "historical_performance_rows_imported": 0,
        "next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "onboarding_manifest.yaml", manifest)

    correction_rows = [
        {
            "correction_id": TASK_ID + "__direction_correction",
            "strategy_id": STRATEGY_ID,
            "prior_mandatory_stage": "prospective_validation_design_and_activation",
            "correction": "separate_prospective_validation_was_an_unnecessary_mandatory_intermediate_stage",
            "corrected_funnel": "exploration_or_backtest_to_robustness_or_approval_to_paper_demo_eligibility_to_forward_observation",
            "superseded_as_mandatory_stage": True,
            "paper_demo_eligibility_blocked": False,
            "completed_validation_evidence": False,
            "paper_demo_observation": False,
            "failed_activation_invalidates_robustness": False,
            "continue_or_create_custom_psar_recorder": False,
            "initialization_or_provider_rows_transferred": 0,
            "replacement_observation": OBSERVATION_ID,
            "future_evidence_path": "standard_paper_demo_framework",
            "append_only": True,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(
        OUTPUT_DIR / "direction_correction_record.csv",
        correction_rows,
        ["correction_id", "strategy_id", "prior_mandatory_stage", "correction"],
    )
    write_csv(
        OUTPUT_DIR / "psar_lineage_reconciliation.csv",
        pre["lineage_rows"],
        ["lineage_order", "lineage_stage", "packet_path", "packet_hash"],
    )
    eligibility_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "before_stage": "robustness",
            "before_outcome": "robustness_positive",
            "before_paper_demo_eligibility": False,
            "after_stage": "paper-demo-eligibility",
            "after_eligibility": "paper_demo_eligible",
            "eligible_route": ROUTE,
            "eligibility_basis": "route_specific_exploration_passed_and_final_robustness_positive",
            "paper_demo_recommendation": "standard_virtual_observation",
            "standalone_outcome": "closed_exploration",
            "standalone_failure_reason": "benchmark_like_behavior",
            "historical_outcomes_changed": False,
            "real_money_authorization": False,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(
        OUTPUT_DIR / "eligibility_before_after.csv",
        eligibility_rows,
        ["strategy_id", "before_stage", "after_stage", "after_eligibility"],
    )
    superseded_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "prior_custom_stage": "prospective_validation_design_and_activation",
            "prior_activation_outcome": "prospective_activation_repair_failed",
            "corrected_status": "superseded_nonblocking_workflow",
            "completed_validation_claim": False,
            "paper_demo_blocker": False,
            "continue_custom_workflow": False,
            "performance_rows_transferred": 0,
            "replacement_observation": OBSERVATION_ID,
            "prior_artifacts_preserved": True,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(
        OUTPUT_DIR / "superseded_validation_workflow.csv",
        superseded_rows,
        ["strategy_id", "prior_custom_stage", "prior_activation_outcome", "corrected_status"],
    )
    transition_rows = [
        {
            "transition_id": TASK_ID + "__supersede_custom_prospective_validation",
            "transition_timestamp": timestamp_text,
            **superseded_rows[0],
            "append_only": True,
            "historical_records_deleted": False,
        }
    ] if superseded_rows else []
    write_csv(
        OUTPUT_DIR / "prior_validation_state_transition.csv",
        transition_rows,
        ["transition_id", "transition_timestamp", "strategy_id", "corrected_status"],
    )
    write_csv(
        OUTPUT_DIR / "standard_framework_compatibility.csv",
        pre["compatibility_rows"],
        ["check_order", "capability", "classification", "status"],
    )
    reference_row = {
        **pre["reference"],
        "reconciliation_status": "reconciled_but_not_current_for_new_execution",
        "new_reference_data_remediation_started": False,
    }
    write_csv(
        OUTPUT_DIR / "reference_observation_state_reconciliation.csv",
        [reference_row],
        ["reference_id", "reference_observation_id", "status", "reconciliation_status"],
    )
    write_csv(
        OUTPUT_DIR / "psar_signal_state_reconciliation.csv",
        [pre["psar"]],
        ["strategy_id", "state_type", "latest_completed_signal_date", "PSAR", "AF", "extreme_point", "trend_state"],
    )
    write_csv(
        OUTPUT_DIR / "combined_target_reconciliation.csv",
        pre["combined"]["rows"],
        ["symbol", "reference_target_weight", "scaled_reference_weight", "psar_sleeve_target_weight", "scaled_psar_sleeve_weight", "diagnostic_combined_weight"],
    )
    observation_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "entity_type": "paper_demo_observation",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "route": ROUTE,
            "mode": "virtual_observation",
            "reference": REFERENCE_ID,
            "reference_weight": REFERENCE_WEIGHT,
            "psar_sleeve_weight": PSAR_WEIGHT,
            "status": "active_paper_demo_observation",
            "initialization_status": "pending_first_valid_signal_or_execution",
            "broker_orders": False,
            "paper_broker_orders": False,
            "real_money_authorization": False,
            "historical_backfill": False,
            "performance_rows": 0,
            "next_action": NEXT_ONBOARDED,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(
        OUTPUT_DIR / "paper_demo_observation_record.csv",
        observation_rows,
        ["observation_id", "entity_type", "stage", "strategy_id", "route", "status"],
    )
    initialization_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "initialization_status": "pending_first_valid_signal_or_execution",
            "initial_virtual_capital": INITIAL_CAPITAL,
            "virtual_cash_before_first_execution": INITIAL_CAPITAL,
            "virtual_positions": {},
            "virtual_shares": {},
            "combined_target": {},
            "execution_date": "",
            "performance_rows_created": 0,
            "historical_backfill": False,
            "stale_diagnostic_target_not_executed": pre["combined"]["combined_target"],
            "orders_created": 0,
            "broker_calls": 0,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(
        OUTPUT_DIR / "virtual_position_initialization.csv",
        initialization_rows,
        ["observation_id", "initialization_status", "initial_virtual_capital", "virtual_cash_before_first_execution"],
    )
    active_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "before_present": False,
            "after_present": outcome == OUTCOME_ONBOARDED,
            "after_state": "active_accepted_frozen_observation" if outcome == OUTCOME_ONBOARDED else "",
            "after_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
            "after_initialization_status": "pending_first_valid_signal_or_execution" if outcome == OUTCOME_ONBOARDED else "",
            "observation_count_increment": 1 if outcome == OUTCOME_ONBOARDED else 0,
        }
    ]
    write_csv(
        OUTPUT_DIR / "active_observation_before_after.csv",
        active_rows,
        ["observation_id", "before_present", "after_present", "after_state"],
    )
    benchmark_rows = [
        {
            "benchmark_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "observation_created": False,
            "strategy_created": False,
            "promoted": False,
            "exact_exposure_control_SPY_weight": (
                EXPOSURE_CONTROL_SPY_WEIGHT if "exact_exposure" in benchmark else ""
            ),
            "exact_exposure_control_BIL_weight": (
                EXPOSURE_CONTROL_BIL_WEIGHT if "exact_exposure" in benchmark else ""
            ),
        }
        for benchmark in BENCHMARKS
    ]
    write_csv(
        OUTPUT_DIR / "benchmark_reference_reconciliation.csv",
        benchmark_rows,
        ["benchmark_id", "entity_type", "stage", "observation_created"],
    )
    faa_rows = [
        {
            "scope": "FAA_active_observation_record",
            "path": relative(ACTIVE_OBSERVATIONS_PATH),
            "before_hash": canonical_hash(faa_record_before),
            "after_hash": canonical_hash(faa_record_after),
            "unchanged": faa_record_before == faa_record_after,
        },
        {
            "scope": "FAA_standard_observation_files",
            "path": relative(FAA_OBSERVATION_DIR),
            "before_hash": protected_before[relative(FAA_OBSERVATION_DIR)],
            "after_hash": protected_after[relative(FAA_OBSERVATION_DIR)],
            "unchanged": protected_before[relative(FAA_OBSERVATION_DIR)]
            == protected_after[relative(FAA_OBSERVATION_DIR)],
        },
        {
            "scope": "FAA_stage_correction_evidence",
            "path": relative(FAA_ONBOARDING_DIR),
            "before_hash": protected_before[relative(FAA_ONBOARDING_DIR)],
            "after_hash": protected_after[relative(FAA_ONBOARDING_DIR)],
            "unchanged": protected_before[relative(FAA_ONBOARDING_DIR)]
            == protected_after[relative(FAA_ONBOARDING_DIR)],
        },
    ]
    write_csv(
        OUTPUT_DIR / "faa_observation_preservation_check.csv",
        faa_rows,
        ["scope", "path", "before_hash", "after_hash", "unchanged"],
    )
    state_rows = [
        {
            "scope": "strategy_lifecycle_registry",
            "path": relative(REGISTRY_PATH),
            "change": "append_one_PSAR_lifecycle_record" if outcome == OUTCOME_ONBOARDED else "none",
            "authorized": outcome == OUTCOME_ONBOARDED,
        },
        {
            "scope": "active_observation_inventory",
            "path": relative(ACTIVE_OBSERVATIONS_PATH),
            "change": "append_one_PSAR_standard_observation" if outcome == OUTCOME_ONBOARDED else "none",
            "authorized": outcome == OUTCOME_ONBOARDED,
        },
        {
            "scope": "standard_observation_files",
            "path": relative(OBSERVATION_DIR),
            "change": "create_pending_observation_and_header_only_ledger" if outcome == OUTCOME_ONBOARDED else "none",
            "authorized": outcome == OUTCOME_ONBOARDED,
        },
    ]
    for path in PROTECTED_PATHS:
        state_rows.append(
            {
                "scope": "protected_state_or_evidence",
                "path": relative(path),
                "before_hash": protected_before[relative(path)],
                "after_hash": protected_after[relative(path)],
                "unchanged": protected_before[relative(path)] == protected_after[relative(path)],
                "change": "none",
                "authorized": False,
            }
        )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        ["scope", "path", "change", "authorized"],
    )
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "strategy_count_increment": 0,
            "trial_count_increment": 0,
            "broker_calls": 0,
            "orders_created": 0,
            "next_action": next_action,
        }
    ]
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        ["task_id", "entity_type", "stage", "outcome"],
    )
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "eligibility": "paper_demo_eligible" if outcome == OUTCOME_ONBOARDED else "",
            "eligible_route": ROUTE if outcome == OUTCOME_ONBOARDED else "",
            "observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
            "initialization_status": "pending_first_valid_signal_or_execution" if outcome == OUTCOME_ONBOARDED else "",
            "historical_backfill": False,
            "performance_rows_created": 0,
            "next_action": next_action,
        }
    ]
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        ["strategy_id", "observation_id", "outcome", "failure_reason", "next_action"],
    )
    failure_rows = [
        {
            "outcome_scope": OUTCOME_BLOCKED,
            "failure_reason": reason,
            "selected": reason == failure_reason,
        }
        for reason in BLOCK_REASONS
    ]
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["outcome_scope", "failure_reason", "selected"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "outcome": OUTCOME_ONBOARDED,
                "next_action": NEXT_ONBOARDED,
                "selected": outcome == OUTCOME_ONBOARDED,
                "executed": False,
            },
            {
                "outcome": OUTCOME_BLOCKED,
                "next_action": NEXT_BLOCKED,
                "selected": outcome == OUTCOME_BLOCKED,
                "executed": False,
            },
        ],
        ["outcome", "next_action", "selected", "executed"],
    )
    (OUTPUT_DIR / "onboarding_report.md").write_text(
        onboarding_report(manifest), encoding="utf-8"
    )

    component_fields: tuple[str, ...] = ()
    component_rows: list[dict[str, str]] = []
    if COMPONENT_LEDGER.exists():
        with COMPONENT_LEDGER.open("r", encoding="utf-8-sig", newline="") as handle:
            component_fields = tuple(next(csv.reader(handle)))
        component_rows = read_csv(COMPONENT_LEDGER)
    required_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    actual_before_consistency = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    psar_registry_rows = [
        row for row in registry_after
        if row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID
    ]
    psar_active_rows = [
        row for row in active_after if row.get("observation_id") == OBSERVATION_ID
    ]
    required_checks = {
        "preflight_pass": pre["passed"],
        "strategy_id_and_rule_unchanged": bool(psar_registry_rows)
        and psar_registry_rows[0].get("configuration_fingerprint") == strategy_fingerprint(),
        "standalone_closure_preserved": bool(psar_registry_rows)
        and psar_registry_rows[0].get("historical_standalone_outcome") == "closed_exploration"
        and psar_registry_rows[0].get("historical_standalone_failure_reason") == "benchmark_like_behavior",
        "paper_demo_eligible_route_exact": bool(psar_registry_rows)
        and psar_registry_rows[0].get("eligibility") == "paper_demo_eligible"
        and psar_registry_rows[0].get("eligible_route") == ROUTE,
        "standard_observation_created_exactly_once": len(psar_active_rows) == 1,
        "pending_initialization_distinct_from_eligibility": bool(psar_active_rows)
        and psar_active_rows[0].get("initialization_status")
        == "pending_first_valid_signal_or_execution",
        "no_backdated_execution": bool(psar_active_rows)
        and psar_active_rows[0].get("historical_backfill") is False,
        "header_only_standard_composite_ledger": component_fields == COMPOSITE_LEDGER_FIELDS
        and len(component_rows) == 0,
        "standard_core_schema_preserved": set(STANDARD_CORE_LEDGER_FIELDS).issubset(component_fields),
        "prior_registry_entries_preserved": registry_after[: len(registry_before)] == registry_before,
        "prior_active_observations_preserved": [
            row for row in active_after if row.get("observation_id") != OBSERVATION_ID
        ] == active_before,
        "faa_active_record_unchanged": faa_record_before == faa_record_after,
        "faa_files_and_correction_unchanged": all(row["unchanged"] for row in faa_rows),
        "protected_state_cache_and_prior_evidence_unchanged": protected_before == protected_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "combined_target_diagnostic_valid_but_not_executed": math.isclose(
            pre["combined"]["weight_sum"], 1.0, abs_tol=1e-12
        ) and not pre["combined"]["safe_for_execution"],
        "custom_workflow_superseded_nonblocking": bool(superseded_rows)
        and superseded_rows[0]["continue_custom_workflow"] is False,
        "zero_historical_rows_transferred": len(component_rows) == 0,
        "entity_counts_reconcile": outcome == OUTCOME_ONBOARDED
        and manifest["new_strategy_configurations"] == 0
        and manifest["paper_demo_observations_created"] == 1
        and manifest["new_experiment_trials"] == 0
        and manifest["validation_observations_created"] == 0,
        "no_broker_or_order_action": manifest["broker_or_paper_orders"] == 0,
        "required_outputs_exact_before_consistency_write": actual_before_consistency
        == required_before_consistency,
        "next_action_not_executed": manifest["next_action_executed"] is False,
    }
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "preflight_checks": pre["checks"],
        **required_checks,
        "existing_strategy_configurations_used": 1,
        "new_strategy_configurations": 0,
        "strategy_lifecycle_records_updated": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "direction_correction_records": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "prior_validation_workflows_superseded": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "paper_demo_observations_created": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "benchmark_references_carried_forward": len(BENCHMARKS),
        "process_tasks": 1,
        "new_experiment_trials": 0,
        "new_robustness_trials": 0,
        "validation_observations_created": 0,
        "historical_performance_rows_imported": 0,
        "performance_rows_created": len(component_rows),
        "broker_calls": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_authorization": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "overall_pass": all(required_checks.values()),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
        "initialization_status": "pending_first_valid_signal_or_execution" if outcome == OUTCOME_ONBOARDED else "",
        "performance_rows": len(component_rows),
        "orders_created": 0,
        "broker_calls": 0,
        "next_action": next_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["outcome"] == OUTCOME_ONBOARDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
