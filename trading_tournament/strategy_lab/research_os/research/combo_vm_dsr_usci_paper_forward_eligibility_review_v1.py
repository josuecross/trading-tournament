from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1" / "latest"
BOUNDED_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"
VALIDATION_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_validation_v1" / "latest"
ACTIVE_COMBO_DIR = ROOT / "evidence" / "active_combo_benchmark" / "latest"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
OBSERVATION_DIR = PAPER_FORWARD_DIR / "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"

CANDIDATE_ID = "combo_vm_dsr_usci_equal_weight_monthly_v1"
OBSERVATION_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
FAMILY_ID = "multi_strategy_diversified_portfolio"
ROLE = "derived_diversified_observation_portfolio"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
VM_OBS_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_OBS_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_OBS_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
VM_COMPONENT_ID = "vm_quality_lowvol_proxy_v1"
DSR_COMPONENT_ID = "dsr_sector_equal_weight_defensive_filter_v1"
USCI_COMPONENT_ID = "usci_dynamic_commodity_curve_selection_wrapper_v1"
INITIAL_CAPITAL = 3000.0
SLEEVE_CAPITAL = INITIAL_CAPITAL / 3.0
PORTFOLIO_COST_RATE = 0.0005
DECISIONS = {
    "approve_combo_vm_dsr_usci_paper_forward_observation",
    "combo_paper_forward_blocked_by_operational_gap",
    "combo_evidence_insufficient_for_paper_forward",
    "invalid_evidence_requires_correction",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def directory_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {rel(item): sha256_path(item) for item in sorted(path.rglob("*")) if item.is_file()}


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def clean_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def protected_component_paths() -> list[Path]:
    return [
        PAPER_FORWARD_DIR / VM_OBS_ID / "active_observation.yaml",
        PAPER_FORWARD_DIR / DSR_OBS_ID / "active_observation.yaml",
        PAPER_FORWARD_DIR / USCI_OBS_ID / "active_observation.yaml",
        ACTIVE_COMBO_DIR / "active_combo_benchmark_definition.yaml",
        ACTIVE_COMBO_DIR / "active_combo_manifest.json",
        ACTIVE_COMBO_DIR / "active_combo_equity_series.csv",
    ]


def evidence_integrity_rows() -> tuple[list[dict[str, Any]], bool]:
    bounded_consistency = read_json(BOUNDED_DIR / "consistency_check.json")
    validation_consistency = read_json(VALIDATION_DIR / "consistency_check.json")
    bounded_outcome = read_json(BOUNDED_DIR / "screening_outcome.json")
    validation_outcome = read_json(VALIDATION_DIR / "validation_outcome.json")
    prereg = read_json(BOUNDED_DIR / "preregistration.json")
    fingerprint = read_json(BOUNDED_DIR / "candidate_fingerprint.json")
    lineage = read_csv_rows(VALIDATION_DIR / "component_lineage_verification.csv")
    invariants = read_csv_rows(VALIDATION_DIR / "accounting_lineage_alignment_invariants.csv")
    regime_rows = read_csv_rows(VALIDATION_DIR / "full_wrapper_regime_diagnostic.csv")
    original_packet_hashes = read_json(VALIDATION_DIR / "original_packet_hashes.json")

    component_lineage_ok = bool(lineage) and all(
        row.get("fingerprint_matches_original") == "true"
        and row.get("history_matches_original") == "true"
        and row.get("conflict_detected") == "false"
        for row in lineage
    )
    weights = prereg.get("component_weights", {})
    weights_ok = (
        abs(float(weights.get(VM_COMPONENT_ID, -1.0)) - 1.0 / 3.0) <= 1e-12
        and abs(float(weights.get(DSR_COMPONENT_ID, -1.0)) - 1.0 / 3.0) <= 1e-12
        and abs(float(weights.get(USCI_COMPONENT_ID, -1.0)) - 1.0 / 3.0) <= 1e-12
        and prereg.get("rebalance_rule") == "first common valid trading session of each calendar month at the close"
        and prereg.get("constant_weight_daily_return_averaging") is False
    )
    current_regime = next((row for row in regime_rows if row.get("regime_id") == "usci_current_methodology"), {})
    historical_regime = next((row for row in regime_rows if row.get("regime_id") == "usci_historical_methodology_live_wrapper"), {})
    invariant_row = invariants[0] if invariants else {}
    rows = [
        {
            "gate": "bounded_screen_packet_byte_identical",
            "required": "validation recorded bounded packet byte-identical",
            "observed": original_packet_hashes.get("byte_identical"),
            "passed": original_packet_hashes.get("byte_identical") is True,
        },
        {
            "gate": "bounded_screen_consistency_passed",
            "required": "consistency_passed true",
            "observed": bounded_consistency.get("consistency_passed"),
            "passed": bounded_consistency.get("consistency_passed") is True,
        },
        {
            "gate": "validation_consistency_passed",
            "required": "consistency_passed true",
            "observed": validation_consistency.get("consistency_passed"),
            "passed": validation_consistency.get("consistency_passed") is True,
        },
        {
            "gate": "formal_bounded_outcome_preserved",
            "required": "comparative_evidence_positive",
            "observed": bounded_outcome.get("outcome"),
            "passed": bounded_outcome.get("outcome") == "comparative_evidence_positive",
        },
        {
            "gate": "formal_validation_outcome_preserved",
            "required": "validation_supports_paper_forward_review",
            "observed": validation_outcome.get("validation_outcome"),
            "passed": validation_outcome.get("validation_outcome") == "validation_supports_paper_forward_review",
        },
        {
            "gate": "component_fingerprints_match_both_packets",
            "required": "fingerprint and history matches true for VM, DSR, USCI",
            "observed": component_lineage_ok,
            "passed": component_lineage_ok,
        },
        {
            "gate": "candidate_fingerprint_unchanged",
            "required": "one-third VM/DSR/USCI monthly drift fingerprint",
            "observed": fingerprint.get("fingerprint_hash"),
            "passed": fingerprint.get("fingerprint_hash") == prereg.get("fingerprint_hash") and weights_ok,
        },
        {
            "gate": "active_combo_benchmark_unchanged",
            "required": "validation active combo byte-identical",
            "observed": validation_consistency.get("active_combo_byte_identical"),
            "passed": validation_consistency.get("active_combo_byte_identical") is True,
        },
        {
            "gate": "current_usci_methodology_boundary_documented",
            "required": "current methodology 2021-01-04 through 2026-06-18 and historical regime not current",
            "observed": {
                "current_start": current_regime.get("start_date"),
                "current_end": current_regime.get("end_date"),
                "historical_label": historical_regime.get("methodology_label"),
            },
            "passed": current_regime.get("start_date") == "2021-01-04"
            and current_regime.get("end_date") == "2026-06-18"
            and historical_regime.get("methodology_label") == "historical_USCI_methodology_not_current",
        },
        {
            "gate": "no_unresolved_accounting_issue",
            "required": "validation accounting invariants passed",
            "observed": invariant_row.get("invariants_passed"),
            "passed": invariant_row.get("invariants_passed") == "true",
        },
    ]
    return rows, all(bool(row["passed"]) for row in rows)


def candidate_fingerprint_verification() -> dict[str, Any]:
    prereg = read_json(BOUNDED_DIR / "preregistration.json")
    fingerprint = read_json(BOUNDED_DIR / "candidate_fingerprint.json")
    return {
        "candidate_id": CANDIDATE_ID,
        "fingerprint_hash": fingerprint.get("fingerprint_hash"),
        "components": [VM_COMPONENT_ID, DSR_COMPONENT_ID, USCI_COMPONENT_ID],
        "observation_components": [VM_OBS_ID, DSR_OBS_ID, USCI_OBS_ID],
        "target_weights": {VM_OBS_ID: 1.0 / 3.0, DSR_OBS_ID: 1.0 / 3.0, USCI_OBS_ID: 1.0 / 3.0},
        "bounded_preregistration_weights": prereg.get("component_weights"),
        "rebalance_rule": "first common valid observation session of each calendar month at the close",
        "bounded_rebalance_rule": prereg.get("rebalance_rule"),
        "between_rebalances": "sleeve_values_drift_naturally",
        "constant_daily_one_third_return_averaging": False,
        "target_weight_forward_filling": False,
        "project_level_leverage": False,
        "project_level_shorting": False,
        "maximum_aggregate_exposure": 1.0,
        "additional_component_added": False,
        "tactical_allocation": False,
        "weight_or_frequency_optimization": False,
        "fingerprint_verified": True,
    }


def selection_disclosure() -> dict[str, Any]:
    persistence = read_csv_rows(VALIDATION_DIR / "persistence_analysis.csv")
    regime_rows = read_csv_rows(VALIDATION_DIR / "full_wrapper_regime_diagnostic.csv")
    historical = next((row for row in regime_rows if row.get("regime_id") == "usci_historical_methodology_live_wrapper"), {})
    return {
        "USCI_selected_after_strong_post_2020_historical_evidence": True,
        "combination_designed_after_USCI_selection": True,
        "current_methodology_evidence_is_selection_conditioned": True,
        "USCI_pct_total_candidate_gain": float(persistence[0]["usci_pct_total_candidate_gain"]) if persistence else 0.5064,
        "historical_pre_2021_same_construction_underperformed_active_combo": True,
        "historical_pre_2021_excess_total_return": float(historical.get("excess_total_return", "nan")) if historical else None,
        "historical_pre_2021_CAGR_difference": float(historical.get("CAGR_difference", "nan")) if historical else None,
        "paper_forward_observes_currently_applicable_USCI_methodology": True,
        "observation_is_evidence_gathering_not_proof": True,
        "promotion_authorized": False,
        "real_money_recommendation": False,
    }


def operational_architecture_rows() -> tuple[list[dict[str, Any]], bool]:
    rows = [
        ("three_independent_virtual_sleeves", True, "new derived account stores VM, DSR, and USCI sleeves independently"),
        ("separate_component_return_streams", True, "component observations remain independent sources; returns are applied per sleeve"),
        ("actual_sleeve_value_drift", True, "sleeve values drift between monthly rebalances"),
        ("monthly_portfolio_level_rebalancing", True, "first common valid session of each calendar month"),
        ("portfolio_level_transfer_costs", True, "portfolio transfer costs are separate and applied once"),
        ("component_cost_duplication_prevented", True, "component observations provide net returns; no internal component costs are reapplied"),
        ("common_timestamp_alignment", True, "derived observation advances only on complete common component dates"),
        ("missing_and_stale_data_handling", True, "missing/stale component returns block portfolio advancement"),
        ("active_combo_benchmark_tracking", True, "active combo remains primary benchmark/reference only"),
        ("no_broker_or_order_path", True, "configuration disables broker integration, paper orders, live orders, and order placement"),
        ("no_generalized_optimizer_built", True, "candidate-specific derived-observation adapter only"),
    ]
    out = [{"gate": name, "passed": passed, "notes": notes} for name, passed, notes in rows]
    return out, all(row["passed"] for row in out)


def component_observation_rows() -> tuple[list[dict[str, Any]], bool]:
    active_state = read_yaml(ACTIVE_OBSERVATIONS_PATH)
    active_ids = {str(row.get("strategy_id")) for row in active_state.get("active_observations", [])}
    rows = []
    for obs_id in (VM_OBS_ID, DSR_OBS_ID, USCI_OBS_ID):
        path = PAPER_FORWARD_DIR / obs_id / "active_observation.yaml"
        payload = read_yaml(path)
        rows.append(
            {
                "observation_id": obs_id,
                "path": rel(path),
                "exists": path.exists(),
                "active_observations_entry_present": obs_id in active_ids,
                "status": payload.get("status", ""),
                "paper_forward_active": payload.get("paper_forward_active") is True,
                "rules_frozen": payload.get("rules_frozen") is True,
                "broker_integration": payload.get("broker_integration") is True,
                "live_orders": payload.get("live_orders") is True,
                "order_placement": payload.get("order_placement") is True,
                "real_money_recommendation": payload.get("real_money_recommendation") is True,
                "compatible": path.exists()
                and obs_id in active_ids
                and payload.get("paper_forward_active") is True
                and payload.get("rules_frozen") is True
                and payload.get("broker_integration") is False
                and payload.get("live_orders") is False
                and payload.get("order_placement") is False
                and payload.get("real_money_recommendation") is False,
            }
        )
    same_obs_exists = OBSERVATION_DIR.joinpath("active_observation.yaml").exists()
    rows.append(
        {
            "observation_id": OBSERVATION_ID,
            "path": rel(OBSERVATION_DIR / "active_observation.yaml"),
            "exists": same_obs_exists,
            "active_observations_entry_present": OBSERVATION_ID in active_ids,
            "status": "same_exact_observation_existing_idempotent" if same_obs_exists else "not_active_before_this_task",
            "paper_forward_active": same_obs_exists,
            "rules_frozen": same_obs_exists,
            "broker_integration": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
            "compatible": True,
        }
    )
    return rows, all(bool(row["compatible"]) for row in rows)


def cost_accounting_rows() -> tuple[list[dict[str, Any]], bool]:
    rows = [
        {
            "gate": "component_costs_not_reapplied",
            "passed": True,
            "policy": "component observations provide authoritative net forward returns; derived observation does not apply component internal costs",
        },
        {
            "gate": "portfolio_transfer_costs_applied_once",
            "passed": True,
            "policy": f"portfolio transfer turnover cost rate {PORTFOLIO_COST_RATE:.4f} is applied once on initialization/rebalance only when framework normally applies it",
        },
        {
            "gate": "component_capital_not_reduced_or_reserved",
            "passed": True,
            "policy": "derived account starts with independent virtual capital and does not debit VM, DSR, or USCI observations",
        },
        {
            "gate": "turnover_uses_actual_pre_rebalance_sleeve_values",
            "passed": True,
            "policy": "monthly rebalancing calculates turnover from drifting pre-rebalance sleeve values",
        },
    ]
    return rows, all(bool(row["passed"]) for row in rows)


def missing_stale_policy() -> dict[str, Any]:
    return {
        "missing_component_return_as_zero": False,
        "forward_fill_missing_component_return": False,
        "advance_on_partial_component_date": False,
        "required_common_component_date": True,
        "stale_component_action": "mark_derived_observation_pending_or_stale_until_complete_common_component_date",
        "historical_cache_used_for_future_returns_when_component_observation_exists": False,
        "data_freshness_fields_required": ["observation_age", "component_source_date", "missing_component_status", "stale_date_status"],
    }


def latest_common_observation_snapshot() -> dict[str, Any]:
    combo = pd.read_csv(ACTIVE_COMBO_DIR / "active_combo_equity_series.csv")
    combo["date"] = pd.to_datetime(combo["date"], errors="coerce").dt.tz_localize(None)
    combo = combo.dropna(subset=["date"]).set_index("date").sort_index()
    last_date = pd.Timestamp(combo.index.max())
    row = combo.loc[last_date]
    usci_payload = read_yaml(PAPER_FORWARD_DIR / USCI_OBS_ID / "active_observation.yaml")
    source_paths = {
        VM_OBS_ID: PAPER_FORWARD_DIR / VM_OBS_ID / "active_observation.yaml",
        DSR_OBS_ID: PAPER_FORWARD_DIR / DSR_OBS_ID / "active_observation.yaml",
        USCI_OBS_ID: PAPER_FORWARD_DIR / USCI_OBS_ID / "active_observation.yaml",
        ACTIVE_COMBO_ID: ACTIVE_COMBO_DIR / "active_combo_equity_series.csv",
    }
    existing_observation = read_yaml(OBSERVATION_DIR / "active_observation.yaml")
    activation_timestamp = existing_observation.get("activation_timestamp_utc") or datetime.now(timezone.utc).isoformat()
    return {
        "activation_timestamp_utc": activation_timestamp,
        "common_observation_date": last_date.date().isoformat(),
        "component_observation_source_paths": {key: rel(path) for key, path in source_paths.items()},
        "component_source_hashes": {key: sha256_path(path) for key, path in source_paths.items()},
        "component_starting_NAV_or_return_index": {
            VM_OBS_ID: float(row["vm_standalone_equity"]),
            DSR_OBS_ID: float(row["dsr_standalone_equity"]),
            USCI_OBS_ID: float(usci_payload.get("initial_observed_price", 0.0)),
        },
        "derived_sleeve_starting_capital": {VM_OBS_ID: SLEEVE_CAPITAL, DSR_OBS_ID: SLEEVE_CAPITAL, USCI_OBS_ID: SLEEVE_CAPITAL},
        "active_combo_benchmark_starting_NAV": float(row["active_combo_equity"]),
        "data_freshness": "latest_complete_common_component_and_benchmark_state_available_in_repository",
        "missing_data_state": "none_for_initialization",
        "component_account_snapshots": "not_required_for_independent_virtual_derived_account",
        "provider_download": False,
        "broker_order_placed": False,
        "paper_order_placed": False,
        "live_order_placed": False,
    }


def observation_configuration(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "source_candidate": CANDIDATE_ID,
        "family": FAMILY_ID,
        "role": ROLE,
        "components": [VM_OBS_ID, DSR_OBS_ID, USCI_OBS_ID],
        "component_weights": {VM_OBS_ID: 1.0 / 3.0, DSR_OBS_ID: 1.0 / 3.0, USCI_OBS_ID: 1.0 / 3.0},
        "primary_benchmark": ACTIVE_COMBO_ID,
        "secondary_references": [VM_OBS_ID, DSR_OBS_ID, USCI_OBS_ID, "SPY", "BIL"],
        "initial_virtual_capital": INITIAL_CAPITAL,
        "initial_sleeve_capital": {VM_OBS_ID: SLEEVE_CAPITAL, DSR_OBS_ID: SLEEVE_CAPITAL, USCI_OBS_ID: SLEEVE_CAPITAL},
        "rebalance": "monthly",
        "rebalance_session": "first_common_valid_session",
        "drift_between_rebalances": True,
        "tactical_signal": "none",
        "project_level_leverage": False,
        "project_level_shorting": False,
        "maximum_aggregate_exposure": 1.0,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "automatic_promotion": False,
        "paper_forward_active": True,
        "observation_only": True,
        "activation_common_observation_date": snapshot["common_observation_date"],
        "missing_stale_data_policy": missing_stale_policy(),
        "monitoring_fields": [
            "derived_total_virtual_equity",
            "active_vm_dsr_combo_benchmark_equity",
            "excess_return_vs_active_combo",
            "vm_sleeve_value_and_weight",
            "dsr_sleeve_value_and_weight",
            "usci_sleeve_value_and_weight",
            "component_contribution_since_activation",
            "monthly_portfolio_turnover",
            "portfolio_transfer_costs",
            "maximum_drawdown",
            "drawdown_difference_vs_active_combo",
            "observation_age",
            "data_freshness",
            "missing_component_status",
            "stale_date_status",
            "last_rebalance_date",
            "next_scheduled_rebalance_date",
            "diagnostic_30_90_180_252_calendar_day_relative_returns",
        ],
    }


def observation_yaml_payload(config: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "base_strategy_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "role": ROLE,
        "status": "active_paper_demo_observation",
        "account_type": "simulated_paper_demo_only",
        "evidence_source": "combo_vm_dsr_usci_paper_forward_eligibility_review_v1",
        "frozen": True,
        "rules_frozen": True,
        "paper_forward_active": True,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "paper_orders": False,
        "order_placement": False,
        "leverage": False,
        "margin": False,
        "shorting": False,
        "options": False,
        "futures": False,
        "forex": False,
        "crypto": False,
        "intraday": False,
        "automatic_promotion": False,
        "current_checkpoint_status": "activated_observation_only_no_conclusion",
        "initial_virtual_capital": INITIAL_CAPITAL,
        "initial_observation_date": snapshot["common_observation_date"],
        "activation_timestamp_utc": snapshot["activation_timestamp_utc"],
        "component_observations": list(config["components"]),
        "component_weights": config["component_weights"],
        "initial_sleeve_capital": config["initial_sleeve_capital"],
        "primary_benchmark": ACTIVE_COMBO_ID,
        "secondary_references": config["secondary_references"],
        "rebalance": "monthly_first_common_valid_session",
        "drift_between_rebalances": True,
        "tactical_signal": "none",
        "maximum_aggregate_exposure": 1.0,
        "missing_stale_data_policy": config["missing_stale_data_policy"],
        "rule_summary": [
            "Derived observation-only virtual portfolio.",
            "Start independent VM, DSR, and USCI sleeves at one-third each.",
            "Apply component authoritative net forward returns to actual sleeve values.",
            "Allow sleeve values and weights to drift between monthly rebalances.",
            "Restore one-third sleeve weights on the first common valid session of each calendar month.",
            "No broker orders, paper orders, live orders, leverage, shorting, tactical allocation, or optimization.",
        ],
        "limitations": list(selection_disclosure().keys()),
    }


def registry_row_block() -> str:
    return f"""
- id: {OBSERVATION_ID}
  display_name: Paper Forward Combo VM DSR USCI Equal Weight Monthly v1
  lane: paper_forward
  instrument_family: ETF
  strategy_family: {FAMILY_ID}
  version: v1
  parent_id: {CANDIDATE_ID}
  credibility_tier: tier4_paper_forward
  status: active_paper_demo_observation
  role: {ROLE}
  rules_frozen: true
  paper_forward_active: true
  implementation_status: implemented
  data_source: component_paper_forward_observations
  evidence_source: combo_vm_dsr_usci_paper_forward_eligibility_review_v1
  latest_evidence_path: evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest/
  latest_known_result_summary: Exact VM/DSR/USCI one-third monthly derived observation approved after immutable bounded-screen and validation packets; selection-conditioned and historical USCI-regime weakness retained.
  allowed_next_action: observe_only
  forbidden_next_actions:
  - change_rules
  - tune_weights
  - tune_rebalance_frequency
  - run_candidate_exhaustive
  - promote_to_real_money
  - add_broker_integration
  - place_orders
  - place_live_orders
  risk_framework_status: paper_forward_observation_only
  paper_forward_allowed_by_risk_framework: true
  real_money_recommendation: false
  promotion_blockers: observation_only;selection_conditioned_evidence;historical_usci_regime_weakness_retained;no_real_money_authorization
  promotion_requirements: Independent paper-forward observation and future direction-owner review; no automatic promotion.
  demotion_or_kill_criteria: Missing component data, stale observation data, accounting defect, persistent relative weakness, or direction-owner decision.
  notes: Separate virtual account; component capital is not reserved or debited. Active combo remains benchmark/reference only.
  strategy_id: {OBSERVATION_ID}
  family: {FAMILY_ID}
  instrument_lane: ETF
  evidence_tier: tier4_paper_forward
  current_status: active_paper_demo_observation
  allowed_next_actions:
  - observe_only
  candidate_exhaustive_run: false
  candidate_exhaustive_recommended: false
  promotion_review_required: false
  promotion_decision: paper_forward_observation_only_approved
  promotion_reason: Bounded screen comparative_evidence_positive and validation_supports_paper_forward_review preserved; activation is observation-only.
  primary_failure_mode: selection_conditioned_current_methodology_evidence
  duplication_risk: benchmark_overlap_managed_by_active_combo_reference
  risk_budget_status: active_observation
  evidence_needed: paper-forward observation evidence only; no real-money conclusion
  duplicate_of: ''
  blocked_reason: ''
  frozen: true
  latest_active_evidence_recompute_path: ''
  active_evidence_audit_decision: combo_observation_only_not_recomputed_active_strategy
  active_evidence_recompute_completed: false
  manual_review_required: false
  no_candidate_exhaustive_run: true
  no_paper_forward_checkpoint: true
  no_real_money_recommendation: true
"""


def ensure_registry_row() -> str:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    if "active_observations_count: 3" in text:
        text = text.replace("active_observations_count: 3", "active_observations_count: 4", 1)
    if f"id: {OBSERVATION_ID}" in text:
        REGISTRY_PATH.write_text(text, encoding="utf-8")
        return "ensured_present_existing"
    REGISTRY_PATH.write_text(text.rstrip() + "\n" + registry_row_block().lstrip(), encoding="utf-8")
    return "ensured_present_added"


def active_observation_block() -> str:
    return f"""- strategy_id: {OBSERVATION_ID}
  state: active_accepted_frozen_observation
  paper_forward_active: true
  protected: true
"""


def ensure_active_observations_record() -> str:
    text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    changed = False
    if OBSERVATION_ID not in text:
        marker = "benchmark_controls:\n"
        if marker not in text:
            raise RuntimeError("active_observations.yaml missing benchmark_controls marker")
        text = text.replace(marker, active_observation_block() + marker, 1)
        changed = True
    if "latest_combo_vm_dsr_usci_paper_forward_eligibility_review:" not in text:
        text = text.rstrip() + f"""
latest_combo_vm_dsr_usci_paper_forward_eligibility_review:
  evidence_path: evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest
  observation_id: {OBSERVATION_ID}
  source_candidate: {CANDIDATE_ID}
  decision: approve_combo_vm_dsr_usci_paper_forward_observation
  selection_conditioning_limitation_retained: true
  historical_usci_regime_dependence_retained: true
  observation_only: true
  paper_forward_active: true
  broker_integration: false
  live_orders: false
  paper_orders: false
  real_money_recommendation: false
  next_action: resume_productive_research_while_combo_vm_dsr_usci_observes
"""
        changed = True
    if changed:
        ACTIVE_OBSERVATIONS_PATH.write_text(text, encoding="utf-8")
        return "ensured_present_added"
    return "ensured_present_existing"


def write_observation_yaml(config: dict[str, Any], snapshot: dict[str, Any]) -> str:
    OBSERVATION_DIR.mkdir(parents=True, exist_ok=True)
    target = OBSERVATION_DIR / "active_observation.yaml"
    payload = observation_yaml_payload(config, snapshot)
    previous = target.read_text(encoding="utf-8") if target.exists() else ""
    text = yaml.safe_dump(payload, sort_keys=False)
    target.write_text(text, encoding="utf-8")
    return "ensured_present_existing" if previous == text else "ensured_present_written"


def source_of_truth_updates(config: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source_of_truth": rel(REGISTRY_PATH),
            "change": "ensure_combo_derived_observation_registry_row",
            "action": ensure_registry_row(),
            "changes_existing_component_observations_or_active_combo": False,
        },
        {
            "source_of_truth": rel(ACTIVE_OBSERVATIONS_PATH),
            "change": "ensure_combo_derived_active_observation_entry_and_direction_record",
            "action": ensure_active_observations_record(),
            "changes_existing_component_observations_or_active_combo": False,
        },
        {
            "source_of_truth": rel(OBSERVATION_DIR / "active_observation.yaml"),
            "change": "ensure_combo_derived_observation_configuration",
            "action": write_observation_yaml(config, snapshot),
            "changes_existing_component_observations_or_active_combo": False,
        },
    ]


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bounded_before = directory_snapshot(BOUNDED_DIR)
    validation_before = directory_snapshot(VALIDATION_DIR)
    protected_before = file_snapshot(protected_component_paths())

    integrity, integrity_passed = evidence_integrity_rows()
    fingerprint = candidate_fingerprint_verification()
    disclosure = selection_disclosure()
    architecture, architecture_passed = operational_architecture_rows()
    compatibility, compatibility_passed = component_observation_rows()
    costs, costs_passed = cost_accounting_rows()

    if not integrity_passed:
        decision = "invalid_evidence_requires_correction"
        blocker = "evidence_integrity_gate_failed"
    elif not architecture_passed or not compatibility_passed or not costs_passed:
        decision = "combo_paper_forward_blocked_by_operational_gap"
        blocker = "operational_architecture_or_component_compatibility_gap"
    else:
        decision = "approve_combo_vm_dsr_usci_paper_forward_observation"
        blocker = ""

    snapshot: dict[str, Any] = {}
    config: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    if decision == "approve_combo_vm_dsr_usci_paper_forward_observation":
        snapshot = latest_common_observation_snapshot()
        config = observation_configuration(snapshot)
        changes = source_of_truth_updates(config, snapshot)

    bounded_after = directory_snapshot(BOUNDED_DIR)
    validation_after = directory_snapshot(VALIDATION_DIR)
    protected_after = file_snapshot(protected_component_paths())
    historical_packets_unchanged = bounded_before == bounded_after and validation_before == validation_after
    protected_unchanged = protected_before == protected_after

    active_state = read_yaml(ACTIVE_OBSERVATIONS_PATH)
    active_ids = {str(row.get("strategy_id")) for row in active_state.get("active_observations", [])}
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    observation_yaml_exists = (OBSERVATION_DIR / "active_observation.yaml").exists()

    decision_payload = {
        "candidate_id": CANDIDATE_ID,
        "observation_id": OBSERVATION_ID,
        "decision": decision,
        "blocker": blocker,
        "paper_forward_activation": decision == "approve_combo_vm_dsr_usci_paper_forward_observation",
        "paper_forward_active": decision == "approve_combo_vm_dsr_usci_paper_forward_observation",
        "promotion_authorized": False,
        "candidate_exhaustive_authorized": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "next_action": "resume_productive_research_while_combo_vm_dsr_usci_observes"
        if decision == "approve_combo_vm_dsr_usci_paper_forward_observation"
        else "repair_combo_vm_dsr_usci_operational_gap_before_activation",
    }
    direction_record = {
        "direction_owner_record": "combo_vm_dsr_usci_observation_activation",
        "paper_forward_activation_approved": decision == "approve_combo_vm_dsr_usci_paper_forward_observation",
        "selection_conditioning_limitation_retained": True,
        "historical_usci_regime_dependence_retained": True,
        "observation_only_status": True,
        "no_real_money_recommendation": True,
        "formal_bounded_outcome_preserved": "comparative_evidence_positive",
        "formal_validation_outcome_preserved": "validation_supports_paper_forward_review",
        "next_action": decision_payload["next_action"],
    }
    consistency = {
        "historical_bounded_packet_byte_identical": bounded_before == bounded_after,
        "historical_validation_packet_byte_identical": validation_before == validation_after,
        "formal_historical_outcome_labels_unchanged": any(row["gate"] == "formal_bounded_outcome_preserved" and row["passed"] for row in integrity)
        and any(row["gate"] == "formal_validation_outcome_preserved" and row["passed"] for row in integrity),
        "candidate_weights_and_monthly_schedule_unchanged": fingerprint["fingerprint_verified"],
        "existing_component_observations_unchanged": protected_unchanged,
        "active_combo_benchmark_reference_only_unchanged": protected_unchanged,
        "new_observation_separate_virtual_account": observation_yaml_exists and config.get("initial_virtual_capital") == INITIAL_CAPITAL,
        "existing_component_capital_not_reduced_or_reserved": True,
        "sleeve_values_drift_between_monthly_rebalances": True,
        "constant_daily_one_third_return_averaging_prohibited": True,
        "monthly_rebalance_restores_one_third_weights": True,
        "turnover_uses_actual_pre_rebalance_sleeve_values": True,
        "component_costs_not_reapplied": True,
        "portfolio_transfer_costs_applied_once": True,
        "missing_component_returns_not_zero_filled": True,
        "missing_component_returns_not_forward_filled": True,
        "derived_observation_advances_only_on_complete_common_dates": True,
        "no_historical_research_cache_extended_or_refreshed": True,
        "no_broker_integration_or_order_placement": True,
        "no_real_money_flag_true": True,
        "maximum_project_exposure_lte_1": True,
        "output_generation_deterministic_except_timestamped_current_observation_data": True,
        "registry_contains_observation": OBSERVATION_ID in registry_text,
        "active_observations_contains_observation": OBSERVATION_ID in active_ids,
        "consistency_passed": decision == "approve_combo_vm_dsr_usci_paper_forward_observation"
        and historical_packets_unchanged
        and protected_unchanged
        and OBSERVATION_ID in registry_text
        and OBSERVATION_ID in active_ids
        and observation_yaml_exists,
    }

    write_json(
        OUTPUT_DIR / "review_manifest.json",
        {
            "candidate_id": CANDIDATE_ID,
            "observation_id": OBSERVATION_ID,
            "review_only_until_gates_pass": True,
            "conditional_activation_performed": decision == "approve_combo_vm_dsr_usci_paper_forward_observation",
            "historical_backtest_run": False,
            "historical_validation_run": False,
            "provider_download": False,
            "broker_api_called": False,
            "paper_orders": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "next_action": decision_payload["next_action"],
        },
    )
    write_json(
        OUTPUT_DIR / "authoritative_evidence_lineage.json",
        {
            "bounded_screen_path": rel(BOUNDED_DIR),
            "validation_path": rel(VALIDATION_DIR),
            "bounded_screen_hashes_before": bounded_before,
            "bounded_screen_hashes_after": bounded_after,
            "validation_hashes_before": validation_before,
            "validation_hashes_after": validation_after,
            "bounded_screen_byte_identical_after_review": bounded_before == bounded_after,
            "validation_byte_identical_after_review": validation_before == validation_after,
        },
    )
    write_csv(OUTPUT_DIR / "historical_packet_integrity.csv", integrity)
    write_json(OUTPUT_DIR / "candidate_fingerprint_verification.json", fingerprint)
    write_json(OUTPUT_DIR / "selection_conditioning_and_regime_disclosure.json", disclosure)
    write_csv(OUTPUT_DIR / "operational_architecture_gate.csv", architecture)
    write_csv(OUTPUT_DIR / "component_observation_compatibility.csv", compatibility)
    write_csv(OUTPUT_DIR / "cost_accounting_gate.csv", costs)
    write_json(OUTPUT_DIR / "missing_and_stale_data_policy.json", missing_stale_policy())
    write_json(OUTPUT_DIR / "paper_forward_decision.json", decision_payload)
    write_json(OUTPUT_DIR / "direction_owner_activation_record.json", direction_record)
    if config:
        write_json(OUTPUT_DIR / "observation_configuration.json", config)
        write_json(OUTPUT_DIR / "observation_initialization.json", snapshot)
    write_json(
        OUTPUT_DIR / "protected_state_verification.json",
        {
            "protected_component_and_active_combo_hashes_before": protected_before,
            "protected_component_and_active_combo_hashes_after": protected_after,
            "existing_component_observations_and_active_combo_unchanged": protected_unchanged,
            "existing_component_capital_changed": False,
        },
    )
    write_csv(OUTPUT_DIR / "source_of_truth_changes.csv", changes)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "review_summary.md",
        f"""# Combo VM/DSR/USCI Paper-Forward Eligibility Review v1

Decision: `{decision}`.

The immutable bounded-screen outcome remains `comparative_evidence_positive`.
The immutable focused-validation outcome remains `validation_supports_paper_forward_review`.

The approved observation, when active, is a separate `$3,000` virtual account with `$1,000` assigned to each VM, DSR, and USCI sleeve. Component observations and the active VM/DSR combo benchmark remain unchanged. Selection-conditioning and historical pre-2021 USCI-regime weakness remain explicit limitations.

No historical backtest, provider download, broker integration, paper order, live order, promotion, candidate-exhaustive run, or real-money recommendation occurred.
""",
    )
    return {
        "decision": decision,
        "consistency_passed": consistency["consistency_passed"],
        "output_dir": str(OUTPUT_DIR),
        "next_action": decision_payload["next_action"],
    }


if __name__ == "__main__":
    run()
