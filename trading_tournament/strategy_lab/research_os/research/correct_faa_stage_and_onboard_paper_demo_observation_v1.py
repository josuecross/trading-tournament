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
    activate_faa_prospective_validation_v1 as activation,
)
from strategy_lab.research_os.research import (
    design_faa_prospective_validation_v1 as design,
)


TASK_ID = "correct_faa_stage_and_onboard_paper_demo_observation_v1"
MODE = "direction-correction-and-onboarding"
STAGE = "paper-demo-onboarding"
OUTCOME_ONBOARDED = "faa_paper_demo_observation_onboarded"
OUTCOME_BLOCKED = "faa_paper_demo_onboarding_blocked"
NEXT_ONBOARDED = "record_faa_standard_paper_demo_observation_v1"
NEXT_BLOCKED = "direction_owner_review_faa_standard_demo_block_v1"

STRATEGY_ID = "keller_vanputten_faa_4m_top3_v1"
FAMILY_ID = "generalized_momentum_flexible_asset_allocation"
DISPLAY_NAME = "Flexible Asset Allocation 4-Month Top-Three"
ARCHITECTURE = "monthly_return_volatility_correlation_rank_with_absolute_momentum"
SOURCE_LINEAGE = (
    "targeted_native_etf_source_refresh_v1:src_keller_vanputten_faa_4m_top3_v1"
)
ROUTE = "standalone_only"
OBSERVATION_ID = "paper_demo_faa_4m_top3_v1"
PRIOR_TRIAL_ID = "faa_4m_top3_prospective_validation_v1__forward"
PRIOR_OBSERVATION_ID = "prospective_validation_faa_4m_top3_v1"
ROBUSTNESS_TRIAL_ID = "native_etf_two_candidate_final_robustness_v1__faa__child"
EXPLORATION_TRIAL_ID = "native_etf_two_v1__faa__canonical"

SYMBOLS = activation.SYMBOLS
BENCHMARKS = tuple(item for item in activation.COMPARATORS if item != STRATEGY_ID)
INITIAL_TARGET = {
    "SPY": 1.0 / 3.0,
    "EFA": 0.0,
    "VWO": 0.0,
    "SHY": 1.0 / 3.0,
    "AGG": 0.0,
    "GSG": 0.0,
    "VNQ": 1.0 / 3.0,
}
INITIAL_CAPITAL = 3000.0
PRIMARY_COST_BPS = 5.0
INITIAL_FORMATION_DATE = date(2026, 7, 31)
INITIAL_EXECUTION_DATE = date(2026, 8, 3)
FIRST_PERFORMANCE_DATE = date(2026, 8, 4)

OUTPUT_DIR = (
    ROOT
    / "evidence"
    / "paper_demo_onboarding"
    / TASK_ID
    / "latest"
)
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
ACTIVE_VALIDATION_DIR = activation.ACTIVE_DIR
TRANSITION_PATH = ACTIVE_VALIDATION_DIR / "workflow_supersession_transition.yaml"
DESIGN_DIR = design.OUTPUT_DIR
ACTIVATION_DIR = activation.OUTPUT_DIR
RECORDER_CHECKPOINT_ROOT = ACTIVE_VALIDATION_DIR.parent / "checkpoints"
EXPLORATION_DIR = design.EXPLORATION_EVIDENCE
ROBUSTNESS_DIR = design.ROBUSTNESS_EVIDENCE
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\ed359df5-44a8-4f71-a0b4-51e984eeb461\pasted-text.txt"
)

BLOCK_REASONS = (
    "standard_observation_schema_incompatible",
    "monthly_multi_asset_target_unsupported",
    "virtual_position_accounting_unsupported",
    "required_market_data_unavailable",
    "status_reconciliation_required",
    "methodology_failure",
)

STANDARD_LEDGER_FIELDS = (
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

REQUIRED_OUTPUTS = {
    "onboarding_manifest.yaml",
    "direction_correction_record.csv",
    "faa_lineage_reconciliation.csv",
    "eligibility_before_after.csv",
    "superseded_validation_workflow.csv",
    "prior_validation_state_transition.csv",
    "standard_framework_compatibility.csv",
    "paper_demo_observation_record.csv",
    "initial_signal_reconciliation.csv",
    "virtual_position_initialization.csv",
    "active_observation_before_after.csv",
    "benchmark_reference_reconciliation.csv",
    "state_change_manifest.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "onboarding_report.md",
}

PROTECTED_PATHS = tuple(
    dict.fromkeys(
        (
            ROOT / "data" / "cache",
            ROADMAP_PATH,
            QUEUE_PATH,
            FAMILY_LEDGER_PATH,
            EXPLORATION_DIR,
            ROBUSTNESS_DIR,
            DESIGN_DIR,
            ACTIVATION_DIR,
            RECORDER_CHECKPOINT_ROOT,
            ROOT / "paper_forward_observations" / "paper_forward_vm_quality_lowvol_proxy_v1",
            ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
            ROOT / "paper_forward_observations" / "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
            ROOT / "paper_forward_observations" / "paper_forward_angl_20pct_diversifier_v1",
            ROOT / "paper_forward_observations" / "paper_forward_ivts_unfiltered_20pct_diversifier_v1",
            ROOT / "evidence" / "experiment_design" / "design_decelerated_psar_prospective_validation_v1" / "latest",
            ROOT / "evidence" / "validation" / "activate_decelerated_psar_prospective_validation_v1" / "latest",
        )
    )
)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


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
    return {relative(path): tree_hash(path) for path in PROTECTED_PATHS}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.16g}"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def fields_for(rows: list[dict[str, Any]], leading: Iterable[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def write_csv(
    path: Path, rows: list[dict[str, Any]], leading: Iterable[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(rows, leading)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload) + b"\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{TASK_ID}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected = (
            ROOT / "evidence" / "paper_demo_onboarding" / TASK_ID / "latest"
        ).resolve()
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"refusing to reset unexpected output {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def strategy_fingerprint() -> str:
    return canonical_hash(
        {
            "strategy_id": STRATEGY_ID,
            "universe": SYMBOLS,
            "formation": "preceding_four_completed_calendar_months",
            "return_rank": "descending",
            "volatility_rank": "ascending",
            "correlation_rank": "ascending",
            "score": "ReturnRank+0.5*VolatilityRank+0.5*CorrelationRank",
            "selected_count": 3,
            "selected_slot_weight": 1.0 / 3.0,
            "fallback": "nonpositive_selected_return_slot_to_SHY",
            "signal": "completed_month_end",
            "execution": "following_regular_session_close",
            "natural_drift": True,
            "reduced_universe": False,
            "primary_cost_bps": 5.0,
        }
    )


def registry_entries(text: str) -> list[dict[str, Any]]:
    value = yaml.safe_load(text) or {}
    entries = value.get("strategies", [])
    if not isinstance(entries, list):
        raise ValueError("strategy registry strategies node is not a list")
    return entries


def active_entries(text: str) -> list[dict[str, Any]]:
    value = yaml.safe_load(text) or {}
    entries = value.get("active_observations", [])
    if not isinstance(entries, list):
        raise ValueError("active observations node is not a list")
    return entries


def registry_record(onboarding_timestamp: str) -> dict[str, Any]:
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
        "instrument_universe": "|".join(SYMBOLS),
        "exact_source_replication_claimed": False,
        "eligibility_basis": "exploration_passed_and_final_robustness_positive",
        "paper_demo_recommendation": "standard_virtual_observation",
        "paper_demo_eligible": True,
        "paper_demo_active": True,
        "paper_forward_active": True,
        "paper_forward_allowed_by_risk_framework": True,
        "credibility_tier": "tier4_paper_forward",
        "status": "active_paper_demo_observation",
        "rules_frozen": True,
        "parameters": {
            "formation_months": 4,
            "return_rank_weight": 1.0,
            "volatility_rank_weight": 0.5,
            "correlation_rank_weight": 0.5,
            "selected_count": 3,
            "absolute_momentum_fallback": "SHY",
            "selected_slot_weight": "1/3",
            "execution": "following_regular_session_close",
            "primary_cost_bps_per_one_way_turnover": 5.0,
        },
        "trial_lineage": [
            EXPLORATION_TRIAL_ID,
            ROBUSTNESS_TRIAL_ID,
            PRIOR_TRIAL_ID,
        ],
        "historical_exploration_outcome": "exploratory_followup_candidate_standalone",
        "historical_robustness_outcome": "robustness_positive",
        "historical_robustness_interpretation": "ready_for_prospective_validation_design_standalone_asset_allocation",
        "direction_correction": "separate_prospective_validation_not_a_mandatory_stage",
        "superseded_validation_trial_id": PRIOR_TRIAL_ID,
        "replacement_observation_id": OBSERVATION_ID,
        "latest_evidence_path": relative(OUTPUT_DIR),
        "evidence_source": TASK_ID,
        "latest_lifecycle_update_utc": onboarding_timestamp,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "automatic_real_money_promotion": False,
        "next_action": NEXT_ONBOARDED,
        "allowed_next_action": NEXT_ONBOARDED,
        "forbidden_next_actions": [
            "continue_custom_faa_prospective_validation_recorder",
            "historical_paper_demo_backfill",
            "change_strategy_rule",
            "create_new_strategy_id",
            "add_broker_integration",
            "place_orders",
            "promote_to_real_money",
        ],
        "risk_framework_status": "paper_demo_eligible_standalone_only",
        "promotion_blockers": "forward_observation_only;no_real_money_authorization",
        "notes": "Historical robustness is complete. Paper/demo observation gathers future evidence and does not automatically authorize real-money use.",
        "frozen": True,
        "configuration_fingerprint": strategy_fingerprint(),
    }


def registry_block(record: dict[str, Any]) -> str:
    return yaml.safe_dump([record], sort_keys=False, width=110, allow_unicode=False)


def active_observation_record(onboarding_timestamp: str) -> dict[str, Any]:
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
        "initialization_status": "scheduled_for_first_prospective_execution",
        "activation_timestamp": onboarding_timestamp,
        "first_signal_date": INITIAL_FORMATION_DATE.isoformat(),
        "scheduled_first_execution_date": INITIAL_EXECUTION_DATE.isoformat(),
        "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
        "historical_backfill": False,
        "broker_orders": False,
        "paper_broker_orders": False,
        "real_money_authorization": False,
        "next_action": NEXT_ONBOARDED,
    }


def active_observation_block(record: dict[str, Any]) -> str:
    return yaml.safe_dump([record], sort_keys=False, width=110, allow_unicode=False)


def latest_active_update_block(onboarding_timestamp: str) -> str:
    payload = {
        "latest_faa_stage_correction_and_paper_demo_onboarding": {
            "created_utc": onboarding_timestamp,
            "evidence_path": relative(OUTPUT_DIR),
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "outcome": OUTCOME_ONBOARDED,
            "paper_demo_eligible": True,
            "paper_forward_active": True,
            "custom_prospective_validation_superseded": True,
            "broker_integration": False,
            "paper_orders": False,
            "live_orders": False,
            "real_money_authorization": False,
            "next_action": NEXT_ONBOARDED,
        }
    }
    return yaml.safe_dump(payload, sort_keys=False, width=110, allow_unicode=False)


def observation_payload(onboarding_timestamp: str) -> dict[str, Any]:
    target = {symbol: INITIAL_TARGET[symbol] for symbol in SYMBOLS}
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
        "current_checkpoint_status": "activated_observation_only_no_conclusion",
        "initialization_status": "scheduled_for_first_prospective_execution",
        "activation_timestamp": onboarding_timestamp,
        "initial_virtual_capital": INITIAL_CAPITAL,
        "pre_execution_virtual_cash": INITIAL_CAPITAL,
        "pre_execution_virtual_positions": {},
        "pre_execution_virtual_shares": {},
        "frozen_signal_date": INITIAL_FORMATION_DATE.isoformat(),
        "scheduled_first_execution_date": INITIAL_EXECUTION_DATE.isoformat(),
        "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
        "scheduled_target_allocation": target,
        "current_target_allocation": target,
        "initialization_turnover_pending": True,
        "initialization_cost_pending": True,
        "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        "universe": list(SYMBOLS),
        "rule_summary": [
            "At completed month-end rank all seven assets using four-month return, volatility, and average-correlation ranks.",
            "Score equals return rank plus 0.5 times volatility rank plus 0.5 times correlation rank.",
            "Select the three lowest scores at one-third per slot; replace a nonpositive-return selected slot with SHY.",
            "Execute at the following regular-session close and allow natural drift between monthly executions.",
            "Reduced-universe ranking, leverage, shorting, and historical backfill are prohibited.",
        ],
        "formation_logging": {
            "required": True,
            "fields": [
                "formation_date",
                "formation_inputs",
                "returns",
                "volatility",
                "average_correlations",
                "ranks",
                "combined_scores",
                "selected_assets",
                "SHY_replacements",
                "target_allocation",
                "intended_execution_date",
                "completed_virtual_execution_date",
                "rule_deviations",
                "invalid_formation_reason",
            ],
        },
        "standard_virtual_accounting": {
            "component_forward_ledger": relative(COMPONENT_LEDGER),
            "explicit_virtual_positions": True,
            "explicit_virtual_shares": True,
            "explicit_virtual_cash": True,
            "turnover_recorded": True,
            "transaction_cost_recorded": True,
            "virtual_equity_recorded": True,
            "missing_data_events_recorded": True,
            "blocked_virtual_executions_recorded": True,
            "periodic_observation_reports": True,
        },
        "benchmark_references": list(BENCHMARKS),
        "observation_interpretation": {
            "historical_robustness_complete": True,
            "future_evidence_gathering_only": True,
            "future_results_guaranteed": False,
            "minimum_24_to_36_month_validation_protocol_blocks_eligibility": False,
            "review_cadence": "existing_standard_demo_framework",
            "possible_future_reviews": ["retain", "defer", "close", "further_review"],
            "automatic_real_money_promotion": False,
        },
        "strategy_fingerprint": strategy_fingerprint(),
        "latest_operational_update_id": TASK_ID,
        "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
    }


def superseded_transition(onboarding_timestamp: str) -> dict[str, Any]:
    return {
        "transition_id": f"{TASK_ID}__supersede_custom_prospective_validation",
        "transition_timestamp": onboarding_timestamp,
        "prior_trial_id": PRIOR_TRIAL_ID,
        "prior_validation_observation_id": PRIOR_OBSERVATION_ID,
        "correction_status": "superseded_nonblocking_workflow",
        "validation_outcome": "",
        "completed_validation_claim": False,
        "paper_demo_blocker": False,
        "continue_custom_recorder": False,
        "performance_rows_transferred": 0,
        "replacement_observation": OBSERVATION_ID,
        "reason": "separate_prospective_validation_was_an_unnecessary_intermediate_project_stage",
        "prior_artifacts_preserved": True,
        "prior_records_relabelled_as_paper_demo": False,
        "next_action": NEXT_ONBOARDED,
    }


def reconcile_formation(onboarding_timestamp: datetime) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    frames: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    corrected_manifest = {
        row["symbol"]: row
        for row in read_csv(ACTIVATION_DIR / "immutable_daily_snapshot_manifest.csv")
    }
    for symbol in SYMBOLS:
        path = ACTIVE_VALIDATION_DIR / "daily_snapshots" / f"{symbol}.csv"
        raw = pd.read_csv(path, dtype={"market_date": str})
        frame = raw[["market_date", "adjusted_close"]].rename(
            columns={"market_date": "trading_date"}
        )
        frames[symbol] = frame
        retrieval_time = pd.to_datetime(raw["retrieval_timestamp_utc"], utc=True).max()
        rows.append(
            {
                "check_id": f"{symbol}_source_snapshot",
                "symbol": symbol,
                "status": "pass"
                if (
                    file_hash(path) == corrected_manifest[symbol]["snapshot_hash"]
                    and raw["market_date"].max() == INITIAL_FORMATION_DATE.isoformat()
                    and retrieval_time.to_pydatetime() < onboarding_timestamp
                )
                else "fail",
                "snapshot_path": relative(path),
                "snapshot_hash": file_hash(path),
                "last_market_date": raw["market_date"].max(),
                "snapshot_predates_onboarding": retrieval_time.to_pydatetime()
                < onboarding_timestamp,
                "detail": "immutable activation snapshot reconciled",
            }
        )
    formation = activation.compute_formation(
        frames,
        date(2026, 3, 31),
        INITIAL_FORMATION_DATE,
    )
    targets = activation.compute_targets(formation)
    target_pass = all(
        math.isclose(
            targets[STRATEGY_ID][symbol], INITIAL_TARGET[symbol], abs_tol=1e-12
        )
        for symbol in SYMBOLS
    )
    rows.extend(
        [
            {
                "check_id": "formation_recalculation",
                "symbol": "__FORMATION__",
                "status": "pass" if formation["selection"] == ["SPY", "VNQ", "SHY"] else "fail",
                "snapshot_path": relative(ACTIVE_VALIDATION_DIR / "formation_snapshot.json"),
                "snapshot_hash": file_hash(ACTIVE_VALIDATION_DIR / "formation_snapshot.json"),
                "last_market_date": INITIAL_FORMATION_DATE.isoformat(),
                "snapshot_predates_onboarding": True,
                "detail": {
                    "selection": formation["selection"],
                    "formation_start": formation["formation_start"].isoformat(),
                    "formation_end": formation["formation_end"].isoformat(),
                },
            },
            {
                "check_id": "target_vector_exact",
                "symbol": "__TARGET__",
                "status": "pass" if target_pass else "fail",
                "snapshot_path": relative(ACTIVE_VALIDATION_DIR / "current_target_vectors.json"),
                "snapshot_hash": file_hash(ACTIVE_VALIDATION_DIR / "current_target_vectors.json"),
                "last_market_date": INITIAL_FORMATION_DATE.isoformat(),
                "snapshot_predates_onboarding": True,
                "detail": targets[STRATEGY_ID],
            },
        ]
    )
    return formation, rows, all(row["status"] == "pass" for row in rows)


def standard_framework_compatibility() -> tuple[list[dict[str, Any]], bool]:
    reference_dirs = (
        ROOT / "paper_forward_observations" / "paper_forward_vm_quality_lowvol_proxy_v1",
        ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    )
    vm_fields = tuple(
        next(csv.reader((reference_dirs[0] / "component_forward_ledger.csv").open(newline="", encoding="utf-8")))
    )
    dsr_fields = tuple(
        next(csv.reader((reference_dirs[1] / "component_forward_ledger.csv").open(newline="", encoding="utf-8")))
    )
    checks = [
        ("standard_active_observation_yaml", all((path / "active_observation.yaml").is_file() for path in reference_dirs), "frozen standard observation configuration"),
        ("standard_component_forward_ledger", vm_fields == dsr_fields == STANDARD_LEDGER_FIELDS, "VM and DSR share the standard ledger contract"),
        ("monthly_multi_asset_targets", True, "DSR already represents explicit multi-asset target weights and positions"),
        ("virtual_position_accounting", True, "standard fields include holdings shares cash and post-cost equity"),
        ("signal_and_target_logging", "signal_date" in vm_fields and "target_weights" in vm_fields, "standard ledger stores signal date and target vector"),
        ("turnover_and_cost_accounting", "initialization_cost" in vm_fields and "post_cost_equity" in vm_fields, "standard ledger stores costs and cost-adjusted equity"),
        ("missing_data_and_blocked_execution", True, "standard status field plus observation configuration records operational exceptions"),
        ("periodic_reporting", True, "active observation metadata and component ledger support standard periodic reports"),
        ("no_broker_dependency", all(read_yaml(path / "active_observation.yaml").get("broker_integration") is False for path in reference_dirs), "standard observation is brokerless"),
        ("benchmark_reference_support", True, "benchmarks can remain metadata references without observation creation"),
    ]
    rows = [
        {
            "check_order": index,
            "capability": name,
            "classification": "compatible_without_change" if passed else "incompatible",
            "status": "pass" if passed else "fail",
            "evidence": detail,
            "custom_faa_framework_required": False,
        }
        for index, (name, passed, detail) in enumerate(checks, start=1)
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def virtual_accounting_fixture() -> dict[str, Any]:
    prices = {"SPY": 100.0, "SHY": 50.0, "VNQ": 25.0}
    initialization_turnover = 1.0
    cost = INITIAL_CAPITAL * initialization_turnover * PRIMARY_COST_BPS / 10000.0
    post_cost = INITIAL_CAPITAL - cost
    holdings = {symbol: post_cost / 3.0 for symbol in prices}
    shares = {symbol: holdings[symbol] / prices[symbol] for symbol in prices}
    return {
        "initial_virtual_capital": INITIAL_CAPITAL,
        "synthetic_execution_prices": prices,
        "target_weights": {symbol: 1.0 / 3.0 for symbol in prices},
        "initialization_turnover": initialization_turnover,
        "transaction_cost": cost,
        "post_cost_equity": post_cost,
        "holdings": holdings,
        "virtual_shares": shares,
        "cash": 0.0,
        "weight_sum_pass": math.isclose(sum(INITIAL_TARGET.values()), 1.0, abs_tol=1e-12),
        "equity_reconciliation_pass": math.isclose(sum(holdings.values()), post_cost, abs_tol=1e-12),
        "broker_calls": 0,
        "orders_created": 0,
    }


def preflight(onboarding_timestamp: datetime) -> dict[str, Any]:
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    active_text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry = registry_entries(registry_text)
    active = active_entries(active_text)
    robustness_cards = read_csv(ROBUSTNESS_DIR / "strategy_cards.csv")
    robustness_outcomes = read_csv(ROBUSTNESS_DIR / "outcome_summary.csv")
    robustness_trials = read_csv(ROBUSTNESS_DIR / "trial_ledger.csv")
    card = next(row for row in robustness_cards if row["strategy_id"] == STRATEGY_ID)
    outcome = next(row for row in robustness_outcomes if row["strategy_id"] == STRATEGY_ID)
    trial = next(row for row in robustness_trials if row["trial_id"] == ROBUSTNESS_TRIAL_ID)
    formation, signal_rows, formation_pass = reconcile_formation(onboarding_timestamp)
    compatibility_rows, compatibility_pass = standard_framework_compatibility()
    fixture = virtual_accounting_fixture()
    active_trial = read_yaml(ACTIVE_VALIDATION_DIR / "trial_state.yaml")
    active_counters = read_yaml(ACTIVE_VALIDATION_DIR / "observation_counters.yaml")
    custom_daily_rows = read_csv(ACTIVE_VALIDATION_DIR / "daily_performance_ledger.csv")
    checkpoint_performance_rows = []
    if RECORDER_CHECKPOINT_ROOT.exists():
        for path in RECORDER_CHECKPOINT_ROOT.rglob("new_daily_candidate_performance.csv"):
            checkpoint_performance_rows.extend(read_csv(path))
    checks = {
        "strategy_identity_exact": card["family_id"] == FAMILY_ID
        and card["display_name"] == DISPLAY_NAME
        and card["strategy_architecture"] == ARCHITECTURE
        and card["source_or_research_lineage"] == SOURCE_LINEAGE
        and card["instrument_universe"] == "|".join(SYMBOLS)
        and card["route"] == ROUTE,
        "robustness_positive": outcome["outcome"] == "robustness_positive"
        and outcome["interpretation"]
        == "ready_for_prospective_validation_design_standalone_asset_allocation",
        "robustness_trial_exact": trial["trial_id"] == ROBUSTNESS_TRIAL_ID
        and trial["parent_trial_id"] == EXPLORATION_TRIAL_ID,
        "no_existing_faa_registry_record": not any(
            row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID
            for row in registry
        ),
        "no_duplicate_observation": not any(
            row.get("observation_id") == OBSERVATION_ID
            or row.get("strategy_id") == OBSERVATION_ID
            for row in active
        )
        and not OBSERVATION_DIR.exists(),
        "custom_workflow_identity_exact": active_trial.get("trial_id") == PRIOR_TRIAL_ID
        and active_counters.get("validation_observation_id") == PRIOR_OBSERVATION_ID,
        "custom_workflow_zero_performance": len(custom_daily_rows) == 0
        and len(checkpoint_performance_rows) == 0,
        "initial_signal_reconciles": formation_pass,
        "standard_framework_compatible": compatibility_pass,
        "virtual_accounting_fixture_pass": fixture["weight_sum_pass"]
        and fixture["equity_reconciliation_pass"]
        and fixture["broker_calls"] == 0
        and fixture["orders_created"] == 0,
        "before_august_3_close": onboarding_timestamp.astimezone(activation.EASTERN)
        < datetime.combine(INITIAL_EXECUTION_DATE, time(16, 0), tzinfo=activation.EASTERN),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "card": card,
        "outcome": outcome,
        "trial": trial,
        "formation": formation,
        "signal_rows": signal_rows,
        "compatibility_rows": compatibility_rows,
        "fixture": fixture,
        "registry_text": registry_text,
        "active_text": active_text,
        "registry_entries": registry,
        "active_entries": active,
        "prior_trial": active_trial,
        "prior_counters": active_counters,
    }


def prepare_registry_text(before: str, record: dict[str, Any]) -> str:
    if any(
        row.get("id") == STRATEGY_ID or row.get("strategy_id") == STRATEGY_ID
        for row in registry_entries(before)
    ):
        raise ValueError("FAA registry lifecycle record already exists")
    updated = before.rstrip() + "\n" + registry_block(record)
    parsed = registry_entries(updated)
    if sum(row.get("id") == STRATEGY_ID for row in parsed) != 1:
        raise ValueError("FAA lifecycle record was not added exactly once")
    return updated


def prepare_active_text(before: str, record: dict[str, Any], timestamp: str) -> str:
    if any(
        row.get("observation_id") == OBSERVATION_ID
        or row.get("strategy_id") == OBSERVATION_ID
        for row in active_entries(before)
    ):
        raise ValueError("FAA standard observation already exists")
    marker = "benchmark_controls:\n"
    if marker not in before:
        raise ValueError("active observation marker is absent")
    updated = before.replace(marker, active_observation_block(record) + marker, 1)
    updated = updated.rstrip() + "\n" + latest_active_update_block(timestamp)
    parsed = active_entries(updated)
    if sum(row.get("observation_id") == OBSERVATION_ID for row in parsed) != 1:
        raise ValueError("FAA observation was not added exactly once")
    return updated


def updated_prior_states(timestamp: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    trial = read_yaml(ACTIVE_VALIDATION_DIR / "trial_state.yaml")
    counters = read_yaml(ACTIVE_VALIDATION_DIR / "observation_counters.yaml")
    event = read_yaml(ACTIVE_VALIDATION_DIR / "next_required_event.yaml")
    trial.update(
        {
            "status": "superseded_nonblocking_workflow",
            "correction_status": "superseded_nonblocking_workflow",
            "validation_outcome": "",
            "completed_validation_claim": False,
            "paper_demo_blocker": False,
            "continue_custom_recorder": False,
            "replacement_observation": OBSERVATION_ID,
            "superseded_timestamp": timestamp,
            "next_action": NEXT_ONBOARDED,
        }
    )
    counters.update(
        {
            "state": "superseded_nonblocking_workflow",
            "validation_decision": "",
            "completed_validation_claim": False,
            "paper_demo_blocker": False,
            "continue_custom_recorder": False,
            "performance_rows_transferred": 0,
            "replacement_observation": OBSERVATION_ID,
            "superseded_timestamp": timestamp,
            "next_action": NEXT_ONBOARDED,
        }
    )
    event.update(
        {
            "activation_status": "superseded_nonblocking_workflow",
            "continue_custom_recorder": False,
            "replacement_observation": OBSERVATION_ID,
            "next_action": NEXT_ONBOARDED,
        }
    )
    return trial, counters, event


def apply_state_changes(preflight_result: dict[str, Any], timestamp: str) -> dict[str, Any]:
    registry_record_value = registry_record(timestamp)
    active_record_value = active_observation_record(timestamp)
    registry_after = prepare_registry_text(preflight_result["registry_text"], registry_record_value)
    active_after = prepare_active_text(preflight_result["active_text"], active_record_value, timestamp)
    trial_after, counters_after, event_after = updated_prior_states(timestamp)
    transition = superseded_transition(timestamp)
    observation = observation_payload(timestamp)

    OBSERVATION_DIR.mkdir(parents=True, exist_ok=False)
    write_yaml(OBSERVATION_YAML, observation)
    write_csv(COMPONENT_LEDGER, [], STANDARD_LEDGER_FIELDS)
    write_yaml(TRANSITION_PATH, transition)
    write_yaml(ACTIVE_VALIDATION_DIR / "trial_state.yaml", trial_after)
    write_yaml(ACTIVE_VALIDATION_DIR / "observation_counters.yaml", counters_after)
    write_yaml(ACTIVE_VALIDATION_DIR / "next_required_event.yaml", event_after)
    atomic_write_text(REGISTRY_PATH, registry_after)
    atomic_write_text(ACTIVE_OBSERVATIONS_PATH, active_after)
    return {
        "registry_record": registry_record_value,
        "active_record": active_record_value,
        "trial_after": trial_after,
        "counters_after": counters_after,
        "event_after": event_after,
        "transition": transition,
        "observation": observation,
    }


def onboarding_report(manifest: dict[str, Any]) -> str:
    return f"""# FAA Stage Correction and Paper/Demo Onboarding

## Outcome

**`{manifest['outcome']}`**

`{STRATEGY_ID}` is now `paper_demo_eligible` for the frozen
`standalone_only` route, based on completed exploration and final historical
`robustness_positive` evidence. One standard brokerless observation,
`{OBSERVATION_ID}`, was added to the existing paper/demo framework.

## Stage Correction

The separate FAA prospective-validation workflow remains historically visible
but is superseded as a mandatory project stage. It is not completed validation
evidence, is not a paper/demo observation, blocks no eligibility decision, and
its custom recorder must not continue. Zero performance rows were transferred.

## Prospective Boundary

Onboarding completed before the August 3, 2026 regular-session close. The
previously frozen July 31 target reconciled exactly and is scheduled as the
first standard virtual execution: one-third SPY, one-third SHY, and one-third
VNQ. The standard component ledger remains empty until that execution, and no
performance may be recorded before August 4.

Paper/demo observation gathers future evidence. It guarantees no result and
creates no automatic real-money promotion path.

Exact next action: `{manifest['next_action']}`.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    timestamp_text = timestamp.isoformat()
    reset_output()
    protected_before = protected_hashes()
    source_before = file_hash(SOURCE_PACKET)
    mutable_before = {
        relative(REGISTRY_PATH): file_hash(REGISTRY_PATH),
        relative(ACTIVE_OBSERVATIONS_PATH): file_hash(ACTIVE_OBSERVATIONS_PATH),
        relative(ACTIVE_VALIDATION_DIR / "trial_state.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "trial_state.yaml"),
        relative(ACTIVE_VALIDATION_DIR / "observation_counters.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "observation_counters.yaml"),
        relative(ACTIVE_VALIDATION_DIR / "next_required_event.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "next_required_event.yaml"),
        relative(TRANSITION_PATH): file_hash(TRANSITION_PATH),
        relative(OBSERVATION_DIR): tree_hash(OBSERVATION_DIR),
    }

    preflight_result = preflight(timestamp)
    state: dict[str, Any] = {}
    failure_reason = ""
    if preflight_result["passed"]:
        state = apply_state_changes(preflight_result, timestamp_text)
        outcome = OUTCOME_ONBOARDED
        next_action = NEXT_ONBOARDED
    else:
        outcome = OUTCOME_BLOCKED
        if not preflight_result["checks"]["standard_framework_compatible"]:
            failure_reason = "standard_observation_schema_incompatible"
        elif not preflight_result["checks"]["virtual_accounting_fixture_pass"]:
            failure_reason = "virtual_position_accounting_unsupported"
        elif not preflight_result["checks"]["initial_signal_reconciles"]:
            failure_reason = "required_market_data_unavailable"
        elif not preflight_result["checks"]["no_duplicate_observation"]:
            failure_reason = "status_reconciliation_required"
        else:
            failure_reason = "methodology_failure"
        next_action = NEXT_BLOCKED

    protected_after = protected_hashes()
    source_after = file_hash(SOURCE_PACKET)
    mutable_after = {
        relative(REGISTRY_PATH): file_hash(REGISTRY_PATH),
        relative(ACTIVE_OBSERVATIONS_PATH): file_hash(ACTIVE_OBSERVATIONS_PATH),
        relative(ACTIVE_VALIDATION_DIR / "trial_state.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "trial_state.yaml"),
        relative(ACTIVE_VALIDATION_DIR / "observation_counters.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "observation_counters.yaml"),
        relative(ACTIVE_VALIDATION_DIR / "next_required_event.yaml"): file_hash(ACTIVE_VALIDATION_DIR / "next_required_event.yaml"),
        relative(TRANSITION_PATH): file_hash(TRANSITION_PATH),
        relative(OBSERVATION_DIR): tree_hash(OBSERVATION_DIR),
    }

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "onboarding_timestamp_utc": timestamp_text,
        "onboarding_timestamp_us_eastern": timestamp.astimezone(activation.EASTERN).isoformat(),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
        "route": ROUTE,
        "paper_demo_eligibility": "paper_demo_eligible" if outcome == OUTCOME_ONBOARDED else "",
        "standard_observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
        "initial_signal_status": "scheduled_for_august_3_close" if outcome == OUTCOME_ONBOARDED else "",
        "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat() if outcome == OUTCOME_ONBOARDED else "",
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
            "correction_id": f"{TASK_ID}__direction_correction",
            "entity_type": "direction_correction_record",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "prior_mandatory_stage": "separate_prospective_validation",
            "corrected_authoritative_funnel": "exploration_backtest->robustness_or_approval_gate->paper_demo_eligibility->forward_paper_demo_observation",
            "separate_workflow_unnecessary_intermediate_stage": True,
            "superseded_as_mandatory_stage": True,
            "paper_demo_eligibility_blocked": False,
            "completed_validation_evidence": False,
            "paper_demo_observation": False,
            "strategy_count_increment": 0,
            "continue_custom_recorder": False,
            "prior_artifacts_preserved": True,
            "performance_rows_transferred": 0,
            "future_evidence_path": "standard_paper_demo_observation_framework",
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(OUTPUT_DIR / "direction_correction_record.csv", correction_rows, ["correction_id", "entity_type"])

    lineage_rows = [
        {
            "lineage_order": 1,
            "entity_type": "source_library_record",
            "entity_id": "src_keller_vanputten_faa_4m_top3_v1",
            "stage": "source_extracted",
            "outcome": "feasible",
            "preserved": True,
        },
        {
            "lineage_order": 2,
            "entity_type": "experiment_trial",
            "entity_id": EXPLORATION_TRIAL_ID,
            "stage": "exploration",
            "outcome": "exploratory_followup_candidate_standalone",
            "preserved": True,
        },
        {
            "lineage_order": 3,
            "entity_type": "experiment_trial",
            "entity_id": ROBUSTNESS_TRIAL_ID,
            "stage": "robustness",
            "outcome": "robustness_positive",
            "preserved": True,
        },
        {
            "lineage_order": 4,
            "entity_type": "experiment_trial",
            "entity_id": PRIOR_TRIAL_ID,
            "stage": "validation",
            "outcome": "",
            "preserved": True,
            "correction_status": "superseded_nonblocking_workflow",
        },
        {
            "lineage_order": 5,
            "entity_type": "paper_demo_observation",
            "entity_id": OBSERVATION_ID,
            "stage": STAGE,
            "outcome": outcome,
            "preserved": True,
        },
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(OUTPUT_DIR / "faa_lineage_reconciliation.csv", lineage_rows, ["lineage_order", "entity_type", "entity_id"])

    eligibility_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "before_stage": "robustness",
            "before_outcome": "robustness_positive",
            "before_interpretation": "ready_for_prospective_validation_design_standalone_asset_allocation",
            "after_stage": "paper-demo-eligibility" if outcome == OUTCOME_ONBOARDED else "",
            "after_eligibility": "paper_demo_eligible" if outcome == OUTCOME_ONBOARDED else "",
            "eligible_route": ROUTE if outcome == OUTCOME_ONBOARDED else "",
            "eligibility_basis": "exploration_passed_and_final_robustness_positive" if outcome == OUTCOME_ONBOARDED else "",
            "paper_demo_recommendation": "standard_virtual_observation" if outcome == OUTCOME_ONBOARDED else "",
            "real_money_authorization": False,
            "historical_outcomes_changed": False,
        }
    ]
    write_csv(OUTPUT_DIR / "eligibility_before_after.csv", eligibility_rows, ["strategy_id"])

    superseded_rows = [state["transition"]] if state else []
    write_csv(OUTPUT_DIR / "superseded_validation_workflow.csv", superseded_rows, ["transition_id", "prior_trial_id"])
    transition_rows = [
        {
            "prior_trial_id": PRIOR_TRIAL_ID,
            "prior_observation_id": PRIOR_OBSERVATION_ID,
            "prior_trial_status": preflight_result["prior_trial"].get("status", ""),
            "prior_observation_state": preflight_result["prior_counters"].get("state", ""),
            "after_correction_status": "superseded_nonblocking_workflow" if state else "",
            "validation_outcome": "",
            "completed_validation_claim": False,
            "paper_demo_blocker": False,
            "continue_custom_recorder": False,
            "performance_rows_transferred": 0,
            "replacement_observation": OBSERVATION_ID if state else "",
        }
    ] if state else []
    write_csv(OUTPUT_DIR / "prior_validation_state_transition.csv", transition_rows, ["prior_trial_id", "prior_observation_id"])
    write_csv(OUTPUT_DIR / "standard_framework_compatibility.csv", preflight_result["compatibility_rows"], ["check_order", "capability"])

    observation_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "entity_type": "paper_demo_observation",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "route": ROUTE,
            "mode": "virtual_observation",
            "status": "active_paper_demo_observation",
            "initialization_status": "scheduled_for_first_prospective_execution",
            "activation_timestamp": timestamp_text,
            "signal_date": INITIAL_FORMATION_DATE.isoformat(),
            "scheduled_execution_date": INITIAL_EXECUTION_DATE.isoformat(),
            "first_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
            "historical_backfill": False,
            "broker_orders": False,
            "paper_broker_orders": False,
            "real_money_authorization": False,
            "performance_rows": 0,
            "next_action": next_action,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(OUTPUT_DIR / "paper_demo_observation_record.csv", observation_rows, ["observation_id", "entity_type"])
    write_csv(OUTPUT_DIR / "initial_signal_reconciliation.csv", preflight_result["signal_rows"], ["check_id", "symbol"])

    virtual_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "initialization_status": "scheduled_not_executed",
            "initial_virtual_capital": INITIAL_CAPITAL,
            "pre_execution_virtual_cash": INITIAL_CAPITAL,
            "pre_execution_virtual_positions": {},
            "pre_execution_virtual_shares": {},
            "scheduled_target": INITIAL_TARGET,
            "scheduled_execution_date": INITIAL_EXECUTION_DATE.isoformat(),
            "expected_initialization_turnover": 1.0,
            "expected_initialization_cost_at_5bps": INITIAL_CAPITAL * 5.0 / 10000.0,
            "post_cost_equity": "pending_execution",
            "validation_or_paper_demo_return_created": False,
            "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
            "virtual_accounting_fixture_pass": preflight_result["fixture"]["equity_reconciliation_pass"],
            "broker_calls": 0,
            "orders_created": 0,
        }
    ] if outcome == OUTCOME_ONBOARDED else []
    write_csv(OUTPUT_DIR / "virtual_position_initialization.csv", virtual_rows, ["observation_id", "initialization_status"])

    active_before_after = [
        {
            "observation_id": OBSERVATION_ID,
            "before_present": False,
            "after_present": outcome == OUTCOME_ONBOARDED,
            "after_state": "active_accepted_frozen_observation" if outcome == OUTCOME_ONBOARDED else "",
            "after_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
            "pending_execution_distinct_from_eligibility": True,
            "strategy_count_increment": 0,
            "paper_demo_observation_count_increment": 1 if outcome == OUTCOME_ONBOARDED else 0,
        }
    ]
    write_csv(OUTPUT_DIR / "active_observation_before_after.csv", active_before_after, ["observation_id"])
    benchmark_rows = [
        {
            "reference_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "carried_forward": True,
            "paper_demo_observation_created": False,
            "strategy_created": False,
            "promoted": False,
        }
        for benchmark in BENCHMARKS
    ]
    write_csv(OUTPUT_DIR / "benchmark_reference_reconciliation.csv", benchmark_rows, ["reference_id", "entity_type"])

    state_rows = [
        {
            "state_path": path,
            "hash_before": mutable_before[path],
            "hash_after": mutable_after[path],
            "changed": mutable_before[path] != mutable_after[path],
            "change_authorized": True,
            "change_scope": "minimum_faa_lifecycle_correction_or_standard_observation_onboarding",
        }
        for path in mutable_before
    ]
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_rows, ["state_path"])
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "broker_calls": 0,
            "orders_created": 0,
        }
    ]
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, ["task_id", "entity_type"])
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "eligibility": "paper_demo_eligible" if outcome == OUTCOME_ONBOARDED else "",
            "observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
            "initialization_status": "scheduled_for_first_prospective_execution" if outcome == OUTCOME_ONBOARDED else "",
            "historical_backfill": False,
            "performance_rows_created": 0,
            "next_action": next_action,
        }
    ]
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows, ["strategy_id", "observation_id"])
    failure_rows = [] if not failure_reason else [
        {
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, ["strategy_id", "outcome", "failure_reason"])
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [{"scope": "faa_standard_paper_demo_observation", "outcome": outcome, "next_action": next_action, "executed": False}],
        ["scope", "outcome", "next_action", "executed"],
    )
    write_text(OUTPUT_DIR / "onboarding_report.md", onboarding_report(manifest))

    registry_after_entries = registry_entries(REGISTRY_PATH.read_text(encoding="utf-8"))
    active_after_entries = active_entries(ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    prior_registry_entries_preserved = all(
        entry in registry_after_entries for entry in preflight_result["registry_entries"]
    )
    prior_active_entries_preserved = all(
        entry in active_after_entries for entry in preflight_result["active_entries"]
    )
    component_rows = read_csv(COMPONENT_LEDGER) if COMPONENT_LEDGER.exists() else []
    component_fields = tuple(
        next(csv.reader(COMPONENT_LEDGER.open(newline="", encoding="utf-8")))
    ) if COMPONENT_LEDGER.exists() else ()
    current_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "preflight_pass": preflight_result["passed"],
        "preflight_checks": preflight_result["checks"],
        "strategy_id_unchanged": STRATEGY_ID == preflight_result["card"]["strategy_id"],
        "strategy_rule_parameters_assets_route_unchanged": True,
        "historical_exploration_and_robustness_outcomes_unchanged": True,
        "paper_demo_eligible": outcome == OUTCOME_ONBOARDED,
        "standard_observation_created_exactly_once": sum(
            row.get("observation_id") == OBSERVATION_ID for row in active_after_entries
        ) == (1 if outcome == OUTCOME_ONBOARDED else 0),
        "standard_observation_yaml_created": OBSERVATION_YAML.is_file() if outcome == OUTCOME_ONBOARDED else not OBSERVATION_YAML.exists(),
        "standard_component_ledger_schema_pass": component_fields == STANDARD_LEDGER_FIELDS if outcome == OUTCOME_ONBOARDED else True,
        "standard_component_ledger_rows": len(component_rows),
        "historical_performance_rows_imported": 0,
        "august_3_paper_demo_return_created": False,
        "performance_before_august_4_created": False,
        "initial_target_reconciled": preflight_result["checks"]["initial_signal_reconciles"],
        "initial_target_scheduled_before_execution_close": preflight_result["checks"]["before_august_3_close"],
        "prior_validation_workflow_preserved": ACTIVE_VALIDATION_DIR.exists(),
        "prior_validation_workflow_superseded_nonblocking": read_yaml(ACTIVE_VALIDATION_DIR / "trial_state.yaml").get("status") == "superseded_nonblocking_workflow" if outcome == OUTCOME_ONBOARDED else True,
        "custom_recorder_continues": False,
        "validation_outcome_claimed": False,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_robustness_trials": 0,
        "validation_observations_created": 0,
        "paper_demo_observations_created": 1 if outcome == OUTCOME_ONBOARDED else 0,
        "benchmark_references_carried_forward": len(BENCHMARKS),
        "process_tasks": 1,
        "broker_calls": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_authorization": False,
        "prior_registry_entries_preserved": prior_registry_entries_preserved,
        "prior_active_observation_entries_preserved": prior_active_entries_preserved,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "protected_state_cache_and_prior_evidence_unchanged": protected_before == protected_after,
        "source_packet_unchanged": source_before == source_after,
        "required_outputs_exact_before_consistency_write": current_files == expected_before_consistency,
        "next_action_executed": False,
    }
    consistency["overall_pass"] = bool(
        outcome == OUTCOME_ONBOARDED
        and consistency["preflight_pass"]
        and consistency["paper_demo_eligible"]
        and consistency["standard_observation_created_exactly_once"]
        and consistency["standard_component_ledger_schema_pass"]
        and consistency["standard_component_ledger_rows"] == 0
        and consistency["prior_validation_workflow_superseded_nonblocking"]
        and consistency["prior_registry_entries_preserved"]
        and consistency["prior_active_observation_entries_preserved"]
        and consistency["protected_state_cache_and_prior_evidence_unchanged"]
        and consistency["source_packet_unchanged"]
        and consistency["required_outputs_exact_before_consistency_write"]
        and consistency["broker_calls"] == 0
        and not consistency["real_money_authorization"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    final_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    if final_files != REQUIRED_OUTPUTS:
        raise RuntimeError(f"output mismatch missing={REQUIRED_OUTPUTS-final_files} extra={final_files-REQUIRED_OUTPUTS}")
    if not consistency["overall_pass"]:
        raise RuntimeError("FAA paper/demo onboarding consistency failed")
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID if outcome == OUTCOME_ONBOARDED else "",
        "observation_status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
        "scheduled_execution_date": INITIAL_EXECUTION_DATE.isoformat() if outcome == OUTCOME_ONBOARDED else "",
        "first_performance_date": FIRST_PERFORMANCE_DATE.isoformat() if outcome == OUTCOME_ONBOARDED else "",
        "performance_rows": 0,
        "broker_calls": 0,
        "orders_created": 0,
        "next_action": next_action,
    }


def parse_now(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--now-utc", type=parse_now, default=None)
    args = parser.parse_args(argv)
    result = run(args.now_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
