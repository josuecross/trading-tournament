from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    reconcile_and_close_ibs_after_validation_v1 as lifecycle,
)


TASK_ID = "reconcile_and_close_kaufman_after_robustness_v1"
MODE = "standardization-patch"
STAGE = "correction"
OUTPUT_DIR = ROOT / "evidence" / "lifecycle" / TASK_ID / "latest"

STRATEGY_REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ROADMAP = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
RESEARCH_QUEUE = (
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
)
FAMILY_LEDGER = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "family_lineage"
    / "family_ledger.yaml"
)
ACTIVE_OBSERVATIONS = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "operations"
    / "active_observations.yaml"
)
CACHE_DIR = ROOT / "data" / "cache"

STANDALONE_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "implement_targeted_medium_frequency_breakout_candidate_v1"
    / "latest"
)
FOLLOWUP_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "kaufman_breakout_diversifier_incremental_value_followup_v1"
    / "latest"
)
ROBUSTNESS_DIR = (
    ROOT
    / "evidence"
    / "robustness"
    / "kaufman_breakout_diversifier_robustness_v1"
    / "latest"
)
RESOLUTION_DIR = (
    ROOT
    / "evidence"
    / "robustness"
    / "resolve_kaufman_diversifier_concentration_risk_v1"
    / "latest"
)

STRATEGY_ID = "kaufman_pjk_lr_channel_breakout_spy_bil_v1"
FAMILY_ID = "projected_linear_regression_channel_breakout"
DISPLAY_NAME = "Kaufman PJK 40-Day Regression-Channel Breakout"
ARCHITECTURE = "long_only_projected_linear_regression_envelope_breakout"
SOURCE_LINEAGE = (
    "targeted_medium_frequency_breakout_source_sprint_v1:"
    "src_kaufman_pjk_lr_channel_breakout_spy_v1"
)
UNIVERSE_TEXT = "SPY|BIL"

STANDALONE_TRIAL_ID = (
    "implement_targeted_medium_frequency_breakout_candidate_v1__canonical"
)
FOLLOWUP_TRIAL_ID = (
    "kaufman_breakout_diversifier_incremental_value_followup_v1__child"
)
ROBUSTNESS_TRIAL_ID = "kaufman_breakout_diversifier_robustness_v1__child"
RESOLUTION_TRIAL_ID = (
    "resolve_kaufman_diversifier_concentration_risk_v1__child"
)

FAILURE_REASON = "concentration_risk"
DECISION_REASON = "single_trade_concentration_exceeded_frozen_50pct_limit"
DECISION_DETAIL = (
    "single_2020_trade_contributed_113_38pct_of_total_additive_excess_"
    "and_removal_made_additive_excess_negative"
)
SECONDARY_FAILURE = "standalone_period_instability"
STRATEGY_NEXT_ACTION = "targeted_defensive_cross_asset_state_source_sprint_v1"
PROCESS_OUTCOME_SUCCESS = "lifecycle_reconciliation_completed"
PROCESS_OUTCOME_BLOCKED = "lifecycle_reconciliation_blocked"
PROJECT_NEXT_ACTION_BLOCKED = (
    "direction_owner_review_kaufman_registry_reconciliation_block_v1"
)
REGISTRATION_REASON = "retrospective_status_reconciliation"
FAMILY_INTERPRETATION = (
    "exact_rule2_40_session_SPY_BIL_configuration_and_two_authorized_routes_"
    "closed_without_family_wide_closure"
)
FINGERPRINT_SCHEMA = "kaufman_rule2_40_spy_bil_exact_config_fingerprint_v1"

FROZEN_PARAMETERS = {
    "channel_contract": "TradingView_Rule_2_only",
    "rule": 2,
    "period_sessions": 40,
    "price_source": "adjusted_close",
    "regression_window": "latest_40_completed_closes",
    "deviation_window": "i_0_through_40_inclusive",
    "entry_comparison": "strictly_above_projected_upper",
    "exit_comparison": "strictly_below_projected_lower",
    "signal_timestamp": "completed_close_t",
    "execution_timestamp": "next_regular_session_open",
    "active_asset": "SPY",
    "inactive_asset": "BIL",
    "long_only": True,
    "leverage_allowed": False,
    "shorting_allowed": False,
    "warmup_sessions": 41,
    "standalone_route": "tested_and_closed",
    "diversifier_route": "20pct_diversifier_only",
    "outer_reference": "frozen_current_active_vm_dsr_usci_combo",
    "outer_reference_weight": 0.8,
    "outer_candidate_weight": 0.2,
    "outer_rebalance": "monthly_following_session_close",
    "primary_cost_bps_per_one_way_turnover": 5.0,
    "exact_source_replication_claimed": False,
}
BENCHMARKS = (
    "frozen_current_active_vm_dsr_usci_combo",
    "donchian_40_close_channel_spy_bil_v1",
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1",
    "kaufman_pjk_slope_only_40_spy_bil_v1",
    "SPY_200_day_trend_control",
    "BIL_buy_and_hold",
)

SOURCE_OF_TRUTH_PATHS = (
    STRATEGY_REGISTRY,
    ROADMAP,
    RESEARCH_QUEUE,
    FAMILY_LEDGER,
    ACTIVE_OBSERVATIONS,
)
INPUT_EVIDENCE_FILES = (
    STANDALONE_DIR / "strategy_cards.csv",
    STANDALONE_DIR / "trial_ledger.csv",
    STANDALONE_DIR / "outcome_summary.csv",
    FOLLOWUP_DIR / "strategy_cards.csv",
    FOLLOWUP_DIR / "trial_ledger.csv",
    ROBUSTNESS_DIR / "strategy_cards.csv",
    ROBUSTNESS_DIR / "trial_ledger.csv",
    RESOLUTION_DIR / "resolution_manifest.yaml",
    RESOLUTION_DIR / "strategy_cards.csv",
    RESOLUTION_DIR / "trial_ledger.csv",
    RESOLUTION_DIR / "outcome_summary.csv",
    RESOLUTION_DIR / "failure_reasons.csv",
    RESOLUTION_DIR / "consistency_check.json",
)

REQUIRED_OUTPUTS = {
    "reconciliation_manifest.yaml",
    "duplicate_and_alias_check.csv",
    "configuration_fingerprint.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "registry_record_before_after.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "reconciliation_report.md",
}

FORBIDDEN_FLAGS = {
    "strategy_or_portfolio_rerun": False,
    "performance_calculation": False,
    "exploration_or_robustness_run": False,
    "validation_run": False,
    "source_research": False,
    "data_acquisition": False,
    "promotion_or_paper_demo_action": False,
    "broker_account_order_or_real_money_action": False,
    "new_strategy_candidate_created": False,
    "new_experiment_trial_created": False,
    "family_wide_kaufman_or_breakout_closure": False,
}


def rel(path: str | Path) -> str:
    return lifecycle.rel(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    return lifecycle.read_csv_rows(path)


def read_yaml(path: Path) -> dict[str, Any]:
    return lifecycle.read_yaml(path)


def read_json(path: Path) -> dict[str, Any]:
    return lifecycle.read_json(path)


def file_hash(path: Path) -> str:
    return lifecycle.file_hash(path)


def hash_paths(paths: tuple[Path, ...]) -> dict[str, str]:
    return lifecycle.hash_paths(paths)


def cache_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in CACHE_DIR.rglob("*") if item.is_file()):
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def clean_output() -> None:
    expected = (ROOT / "evidence" / "lifecycle" / TASK_ID / "latest").resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_universe(value: Any) -> str:
    if isinstance(value, str):
        pieces = [
            piece.strip().upper()
            for piece in value.replace(",", "|").split("|")
            if piece.strip()
        ]
    elif isinstance(value, (list, tuple, set)):
        pieces = [str(item).strip().upper() for item in value]
    else:
        pieces = []
    return "|".join(pieces)


def parse_parameters(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def configuration_fingerprint_payload() -> dict[str, Any]:
    return {
        "family_id": FAMILY_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": UNIVERSE_TEXT,
        "channel_contract": FROZEN_PARAMETERS["channel_contract"],
        "rule": FROZEN_PARAMETERS["rule"],
        "period_sessions": FROZEN_PARAMETERS["period_sessions"],
        "entry_comparison": FROZEN_PARAMETERS["entry_comparison"],
        "exit_comparison": FROZEN_PARAMETERS["exit_comparison"],
        "signal_timestamp": FROZEN_PARAMETERS["signal_timestamp"],
        "execution_timestamp": FROZEN_PARAMETERS["execution_timestamp"],
        "active_asset": FROZEN_PARAMETERS["active_asset"],
        "inactive_asset": FROZEN_PARAMETERS["inactive_asset"],
        "long_only": FROZEN_PARAMETERS["long_only"],
        "leverage_allowed": FROZEN_PARAMETERS["leverage_allowed"],
        "shorting_allowed": FROZEN_PARAMETERS["shorting_allowed"],
        "standalone_route": FROZEN_PARAMETERS["standalone_route"],
        "diversifier_route": FROZEN_PARAMETERS["diversifier_route"],
        "outer_reference": FROZEN_PARAMETERS["outer_reference"],
        "outer_reference_weight": FROZEN_PARAMETERS["outer_reference_weight"],
        "outer_candidate_weight": FROZEN_PARAMETERS["outer_candidate_weight"],
    }


def configuration_fingerprint(
    payload: dict[str, Any] | None = None,
) -> str:
    source = configuration_fingerprint_payload() if payload is None else payload
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def record_fingerprint_payload(record: dict[str, Any]) -> dict[str, Any]:
    params = parse_parameters(record.get("parameters", {}))
    return {
        "family_id": record.get("family_id")
        or record.get("family")
        or record.get("strategy_family")
        or "",
        "source_or_research_lineage": record.get(
            "source_or_research_lineage", ""
        ),
        "instrument_universe": normalize_universe(
            record.get("instrument_universe")
            or record.get("universe")
            or record.get("instruments")
        ),
        "channel_contract": params.get("channel_contract", ""),
        "rule": params.get("rule"),
        "period_sessions": params.get("period_sessions"),
        "entry_comparison": params.get("entry_comparison", ""),
        "exit_comparison": params.get("exit_comparison", ""),
        "signal_timestamp": params.get("signal_timestamp", ""),
        "execution_timestamp": params.get("execution_timestamp", ""),
        "active_asset": params.get("active_asset", ""),
        "inactive_asset": params.get("inactive_asset", ""),
        "long_only": params.get("long_only"),
        "leverage_allowed": params.get("leverage_allowed"),
        "shorting_allowed": params.get("shorting_allowed"),
        "standalone_route": params.get("standalone_route", ""),
        "diversifier_route": params.get("diversifier_route", ""),
        "outer_reference": params.get("outer_reference", ""),
        "outer_reference_weight": params.get("outer_reference_weight"),
        "outer_candidate_weight": params.get("outer_candidate_weight"),
    }


def inspect_registry(
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    target = configuration_fingerprint_payload()
    exact: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    for record in registry.get("strategies", []):
        if not isinstance(record, dict):
            continue
        record_id = record.get("strategy_id") or record.get("id") or ""
        candidate = record_fingerprint_payload(record)
        matched = [
            field
            for field, expected in target.items()
            if candidate.get(field) not in ("", None)
            and candidate.get(field) == expected
        ]
        if record_id == STRATEGY_ID:
            exact.append(
                {
                    "record_id": record_id,
                    "match_type": "exact_strategy_id",
                    "matched_field_count": len(target),
                    "matched_fields": list(target),
                    "record": record,
                }
            )
            continue
        fingerprint_match = (
            record.get("configuration_fingerprint")
            == configuration_fingerprint()
        )
        plausible = bool(
            fingerprint_match
            or (
                candidate.get("family_id") == FAMILY_ID
                and candidate.get("instrument_universe") == UNIVERSE_TEXT
                and len(matched) >= 12
            )
        )
        if plausible:
            aliases.append(
                {
                    "record_id": record_id,
                    "match_type": (
                        "exact_configuration_alias"
                        if fingerprint_match or len(matched) == len(target)
                        else "plausible_equivalent_alias"
                    ),
                    "matched_field_count": len(matched),
                    "matched_fields": matched,
                    "record": record,
                }
            )
    return exact, aliases


def target_registry_record() -> dict[str, Any]:
    return {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "family": FAMILY_ID,
        "strategy_family": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": UNIVERSE_TEXT,
        "exact_source_replication_claimed": False,
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": list(BENCHMARKS),
        "stage": "closed",
        "lane": "archive",
        "instrument_family": "ETF",
        "version": "v1",
        "parent_id": STANDALONE_TRIAL_ID,
        "credibility_tier": "blocked",
        "status": "rejected",
        "current_status": "closed",
        "outcome": "robustness_failed",
        "trial_id": RESOLUTION_TRIAL_ID,
        "parent_trial_id": ROBUSTNESS_TRIAL_ID,
        "adaptation_label": "result_driven_robustness_diagnostic",
        "failure_reason": FAILURE_REASON,
        "primary_failure_reason": FAILURE_REASON,
        "decision_reason": DECISION_REASON,
        "decision_detail": DECISION_DETAIL,
        "strongest_contributing_trade": "2020-03-31_to_2020-09-09",
        "largest_trade_fraction_of_additive_excess": 1.1337989832791708,
        "additive_excess_after_removing_strongest_trade": -0.006514,
        "secondary_failure_evidence": SECONDARY_FAILURE,
        "secondary_route_failure": SECONDARY_FAILURE,
        "standalone_outcome": "closed_exploration",
        "standalone_failure_reason": "period_instability",
        "diversifier_route": "20pct_diversifier_only",
        "diversifier_outcome": "robustness_failed",
        "diversifier_failure_reason": FAILURE_REASON,
        "independent_validation_claimed": False,
        "validation_supported": False,
        "paper_demo_eligible": False,
        "paper_demo_active": False,
        "paper_forward_active": False,
        "paper_forward_allowed_by_risk_framework": False,
        "further_same_period_diagnostic_authorized": False,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "no_real_money_recommendation": True,
        "next_action": STRATEGY_NEXT_ACTION,
        "allowed_next_action": "no_action",
        "allowed_next_actions": ["no_action"],
        "benchmark_reference_only": False,
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "registration_reason": REGISTRATION_REASON,
        "closure_scope": (
            "exact_Kaufman_Rule2_40_session_SPY_BIL_completed_close_signal_"
            "following_session_open_long_only_standalone_and_20pct_frozen_"
            "reference_diversifier_routes_only"
        ),
        "data_source": "existing_canonical_adjusted_SPY_BIL_cache",
        "implementation_status": "archived",
        "evidence_source": TASK_ID,
        "latest_evidence_path": rel(RESOLUTION_DIR),
        "latest_known_result_summary": (
            "Standalone exploration closed for period instability. The 20% "
            "diversifier route failed robustness because one 2020 trade "
            "contributed 113.38% of total additive excess and removal made "
            "additive excess negative."
        ),
        "role": "closed_exact_configuration",
        "rules_frozen": True,
        "risk_framework_status": "not_paper_demo_eligible",
        "risk_budget_status": "closed_concentration_and_stability_failure",
        "promotion_decision": "do_not_promote",
        "promotion_review_required": False,
        "promotion_reason": (
            "Closed exact Kaufman configuration after both authorized routes "
            "failed their final gates."
        ),
        "promotion_blockers": (
            "robustness_failed;concentration_risk;period_instability;"
            "not_validated;not_paper_demo_eligible;no_real_money_authorization"
        ),
        "promotion_requirements": (
            "No further same-period diagnostic or variant is authorized by "
            "this closure. A materially distinct source-backed configuration "
            "would require a separate direction-owner decision."
        ),
        "demotion_or_kill_criteria": (
            "Exact tested standalone and 20% diversifier routes are closed."
        ),
        "notes": (
            "Retrospective reconciliation for the exact Rule-2, 40-session, "
            "SPY/BIL following-open configuration and its authorized 20% "
            "frozen-reference diversifier route only. The Kaufman, regression-"
            "channel, and breakout families remain open to materially distinct "
            "source-backed configurations."
        ),
        "instrument_lane": "ETF",
        "evidence_tier": "blocked",
        "primary_failure_mode": FAILURE_REASON,
        "duplication_risk": "exact_configuration_closed",
        "evidence_needed": "none_for_exact_closed_configuration",
        "duplicate_of": "",
        "blocked_reason": FAILURE_REASON,
        "forbidden_next_actions": [
            "rerun_exact_configuration",
            "run_further_same_period_Kaufman_diagnostic",
            "change_rule_or_40_session_period",
            "change_SPY_or_BIL",
            "change_execution_timing",
            "change_20pct_sleeve_or_frozen_reference",
            "promote_to_validation",
            "promote_to_paper_demo",
            "activate_paper_demo",
            "promote_to_real_money",
            "add_broker_integration",
            "place_orders",
        ],
        "configuration_fingerprint_schema": FINGERPRINT_SCHEMA,
        "configuration_fingerprint": configuration_fingerprint(),
    }


def required_record_complete(record: dict[str, Any]) -> bool:
    required = (
        "id",
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "stage",
        "outcome",
        "trial_id",
        "parent_trial_id",
        "failure_reason",
        "decision_reason",
        "decision_detail",
        "strongest_contributing_trade",
        "largest_trade_fraction_of_additive_excess",
        "additive_excess_after_removing_strongest_trade",
        "secondary_route_failure",
        "standalone_outcome",
        "standalone_failure_reason",
        "diversifier_route",
        "diversifier_outcome",
        "diversifier_failure_reason",
        "next_action",
        "registration_reason",
        "closure_scope",
        "configuration_fingerprint",
    )
    if any(
        record.get(field) in ("", None, "unknown", "unmapped")
        for field in required
    ):
        return False
    expected_false = (
        "independent_validation_claimed",
        "validation_supported",
        "paper_demo_eligible",
        "paper_demo_active",
        "further_same_period_diagnostic_authorized",
        "real_money_authorized",
    )
    return bool(
        record.get("stage") == "closed"
        and record.get("outcome") == "robustness_failed"
        and record.get("failure_reason") == FAILURE_REASON
        and all(record.get(field) is False for field in expected_false)
        and record_fingerprint_payload(record)
        == configuration_fingerprint_payload()
    )


def target_record_yaml() -> str:
    return yaml.safe_dump(
        [target_registry_record()],
        sort_keys=False,
        width=120,
        allow_unicode=False,
    )


def atomic_write_registry(text: str) -> None:
    temporary = STRATEGY_REGISTRY.with_suffix(".yaml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, STRATEGY_REGISTRY)


def append_or_replace_record(original_text: str) -> None:
    replacement = target_record_yaml()
    lines = original_text.splitlines(keepends=True)
    span = lifecycle.find_record_span(original_text, STRATEGY_ID)
    if span is None:
        updated = original_text.rstrip() + "\n" + replacement
    else:
        start, end = span
        lines[start:end] = replacement.splitlines(keepends=True)
        updated = "".join(lines)
        if not updated.endswith("\n"):
            updated += "\n"
    atomic_write_registry(updated)


def load_inputs() -> dict[str, Any]:
    return {
        "standalone_strategy": read_csv(
            STANDALONE_DIR / "strategy_cards.csv"
        ),
        "standalone_trial": read_csv(STANDALONE_DIR / "trial_ledger.csv"),
        "standalone_outcome": read_csv(
            STANDALONE_DIR / "outcome_summary.csv"
        ),
        "followup_strategy": read_csv(FOLLOWUP_DIR / "strategy_cards.csv"),
        "followup_trial": read_csv(FOLLOWUP_DIR / "trial_ledger.csv"),
        "robustness_strategy": read_csv(
            ROBUSTNESS_DIR / "strategy_cards.csv"
        ),
        "robustness_trial": read_csv(ROBUSTNESS_DIR / "trial_ledger.csv"),
        "resolution_manifest": read_yaml(
            RESOLUTION_DIR / "resolution_manifest.yaml"
        ),
        "resolution_strategy": read_csv(
            RESOLUTION_DIR / "strategy_cards.csv"
        ),
        "resolution_trial": read_csv(RESOLUTION_DIR / "trial_ledger.csv"),
        "resolution_outcome": read_csv(
            RESOLUTION_DIR / "outcome_summary.csv"
        ),
        "resolution_failures": read_csv(
            RESOLUTION_DIR / "failure_reasons.csv"
        ),
        "resolution_consistency": read_json(
            RESOLUTION_DIR / "consistency_check.json"
        ),
    }


def evidence_gate(inputs: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []

    def one(
        key: str,
        trial_id: str,
        stage: str,
        outcome: str,
        failure_reason: str,
    ) -> None:
        rows = inputs[key]
        if len(rows) != 1:
            blockers.append(f"{key}_count_not_one")
            return
        row = rows[0]
        if row.get("trial_id") != trial_id:
            blockers.append(f"{key}_trial_id_mismatch")
        if row.get("stage") != stage:
            blockers.append(f"{key}_stage_mismatch")
        if row.get("outcome") != outcome:
            blockers.append(f"{key}_outcome_mismatch")
        if row.get("failure_reason", "") != failure_reason:
            blockers.append(f"{key}_failure_reason_mismatch")

    one(
        "standalone_trial",
        STANDALONE_TRIAL_ID,
        "exploration",
        "closed_exploration",
        "period_instability",
    )
    one(
        "followup_trial",
        FOLLOWUP_TRIAL_ID,
        "exploration",
        "exploratory_followup_candidate_diversifier",
        "",
    )
    one(
        "robustness_trial",
        ROBUSTNESS_TRIAL_ID,
        "robustness",
        "robustness_mixed",
        "concentration_risk",
    )
    one(
        "resolution_trial",
        RESOLUTION_TRIAL_ID,
        "robustness",
        "robustness_failed",
        "concentration_risk",
    )
    manifest = inputs["resolution_manifest"]
    consistency = inputs["resolution_consistency"]
    outcome = inputs["resolution_outcome"]
    failures = inputs["resolution_failures"]
    if manifest.get("strategy_id") != STRATEGY_ID:
        blockers.append("resolution_manifest_strategy_id_mismatch")
    if manifest.get("outcome") != "robustness_failed":
        blockers.append("resolution_manifest_outcome_mismatch")
    if manifest.get("failure_reason") != FAILURE_REASON:
        blockers.append("resolution_manifest_failure_reason_mismatch")
    if (
        manifest.get("further_same_period_kaufman_diagnostic_authorized")
        is not False
    ):
        blockers.append("resolution_manifest_further_diagnostic_not_false")
    if consistency.get("overall_pass") is not True:
        blockers.append("resolution_consistency_not_passed")
    if consistency.get("parent_evidence_unchanged") is not True:
        blockers.append("resolution_parent_evidence_not_unchanged")
    gate = consistency.get("resolution_gate", {})
    fraction = gate.get("largest_trade_fraction_of_total_additive_excess")
    try:
        if abs(float(fraction) - 1.1337989832791708) > 1e-12:
            blockers.append("largest_trade_fraction_mismatch")
    except (TypeError, ValueError):
        blockers.append("largest_trade_fraction_missing")
    if len(outcome) != 1 or outcome[0].get("outcome") != "robustness_failed":
        blockers.append("resolution_outcome_row_mismatch")
    if (
        len(failures) != 1
        or failures[0].get("failure_reason") != FAILURE_REASON
    ):
        blockers.append("resolution_failure_row_mismatch")
    for strategy_key in (
        "standalone_strategy",
        "followup_strategy",
        "robustness_strategy",
        "resolution_strategy",
    ):
        rows = inputs[strategy_key]
        if len(rows) != 1 or rows[0].get("strategy_id") != STRATEGY_ID:
            blockers.append(f"{strategy_key}_identity_mismatch")
    return not blockers, blockers


def duplicate_rows(
    exact: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    registry_count: int,
) -> list[dict[str, Any]]:
    if aliases:
        return [
            {
                "registry_record_count_before": registry_count,
                "searched_strategy_id": STRATEGY_ID,
                "record_id": row["record_id"],
                "match_type": row["match_type"],
                "matched_field_count": row["matched_field_count"],
                "matched_fields": row["matched_fields"],
                "duplicate_check_result": "status_reconciliation_required",
                "authoritative_change_allowed": False,
            }
            for row in aliases
        ]
    if exact:
        return [
            {
                "registry_record_count_before": registry_count,
                "searched_strategy_id": STRATEGY_ID,
                "record_id": STRATEGY_ID,
                "match_type": "exact_strategy_id",
                "matched_field_count": len(configuration_fingerprint_payload()),
                "matched_fields": list(configuration_fingerprint_payload()),
                "duplicate_check_result": "exact_record_exists_update_allowed",
                "authoritative_change_allowed": True,
            }
        ]
    return [
        {
            "registry_record_count_before": registry_count,
            "searched_strategy_id": STRATEGY_ID,
            "record_id": "",
            "match_type": "no_exact_record_no_equivalent_alias",
            "matched_field_count": 0,
            "matched_fields": [],
            "duplicate_check_result": "clear_to_create_one_closed_record",
            "authoritative_change_allowed": True,
        }
    ]


def fingerprint_rows() -> list[dict[str, Any]]:
    return [
        {
            "fingerprint_schema": FINGERPRINT_SCHEMA,
            "field": field,
            "value": value,
            "fingerprint": configuration_fingerprint(),
            "deterministic": True,
        }
        for field, value in configuration_fingerprint_payload().items()
    ]


def strategy_card(process_outcome: str) -> dict[str, Any]:
    record = target_registry_record()
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": UNIVERSE_TEXT,
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": list(BENCHMARKS),
        "stage": "closed",
        "outcome": "robustness_failed",
        "primary_failure_reason": FAILURE_REASON,
        "secondary_failure_evidence": SECONDARY_FAILURE,
        "decision_reason": DECISION_REASON,
        "standalone_outcome": "closed_exploration",
        "standalone_failure_reason": "period_instability",
        "diversifier_route": "20pct_diversifier_only",
        "diversifier_outcome": "robustness_failed",
        "diversifier_failure_reason": FAILURE_REASON,
        "trial_id": RESOLUTION_TRIAL_ID,
        "parent_trial_id": ROBUSTNESS_TRIAL_ID,
        "adaptation_label": "result_driven_robustness_diagnostic",
        "next_action": STRATEGY_NEXT_ACTION,
        "validation_supported": False,
        "paper_demo_eligible": False,
        "paper_demo_active": False,
        "further_same_period_diagnostic_authorized": False,
        "real_money_authorized": False,
        "registration_reason": REGISTRATION_REASON,
        "configuration_fingerprint": record["configuration_fingerprint"],
        "process_outcome": process_outcome,
    }


def trial_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = (
        (
            "standalone_trial",
            STANDALONE_DIR,
            STANDALONE_TRIAL_ID,
            "",
        ),
        (
            "followup_trial",
            FOLLOWUP_DIR,
            FOLLOWUP_TRIAL_ID,
            STANDALONE_TRIAL_ID,
        ),
        (
            "robustness_trial",
            ROBUSTNESS_DIR,
            ROBUSTNESS_TRIAL_ID,
            FOLLOWUP_TRIAL_ID,
        ),
        (
            "resolution_trial",
            RESOLUTION_DIR,
            RESOLUTION_TRIAL_ID,
            ROBUSTNESS_TRIAL_ID,
        ),
    )
    rows: list[dict[str, Any]] = []
    for key, path, trial_id, parent_trial_id in definitions:
        source = inputs[key][0]
        rows.append(
            {
                "entity_type": "experiment_trial",
                "trial_id": trial_id,
                "parent_trial_id": parent_trial_id,
                "stage": source["stage"],
                "strategy_id": STRATEGY_ID,
                "outcome": source["outcome"],
                "failure_reason": source.get("failure_reason", ""),
                "adaptation_label": source.get("adaptation_label", ""),
                "changed_fields_from_parent": source.get(
                    "changed_fields_from_parent", ""
                ),
                "source_evidence_next_action": source.get("next_action", ""),
                "read_only": True,
                "source_evidence_path": rel(path),
                "new_experiment_trial_created": False,
                "counted_as_new_trial": False,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    source = read_csv(RESOLUTION_DIR / "benchmark_reference_log.csv")
    by_id = {row["benchmark_reference_id"]: row for row in source}
    return [
        {
            "benchmark_or_control_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "critical_control": by_id.get(benchmark, {}).get(
                "critical_control", "false"
            ),
            "source_evidence_path": rel(RESOLUTION_DIR),
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "counted_as_observation": False,
        }
        for benchmark in BENCHMARKS
    ]


def registry_state_rows(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state, records in (("before", before), ("after", after)):
        record = records[0] if len(records) == 1 else {}
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
        rows.append(
            {
                "state": state,
                "strategy_id": STRATEGY_ID,
                "record_count": len(records),
                "record_exists": len(records) == 1,
                "record_hash": (
                    "sha256:"
                    + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
                    if record
                    else ""
                ),
                "stage": record.get("stage", ""),
                "outcome": record.get("outcome", ""),
                "failure_reason": record.get("failure_reason", ""),
                "standalone_failure_reason": record.get(
                    "standalone_failure_reason", ""
                ),
                "diversifier_failure_reason": record.get(
                    "diversifier_failure_reason", ""
                ),
                "next_action": record.get("next_action", ""),
                "configuration_fingerprint": record.get(
                    "configuration_fingerprint", ""
                ),
                "record_json": record,
            }
        )
    return rows


def state_change_rows(
    hashes_before: dict[str, str],
    hashes_after: dict[str, str],
    cache_before: str,
    cache_after: str,
    permitted_paths: list[str],
) -> list[dict[str, Any]]:
    permitted = set(permitted_paths)
    rows = [
        {
            "path": path,
            "hash_before": hashes_before[path],
            "hash_after": hashes_after[path],
            "changed": hashes_before[path] != hashes_after[path],
            "change_permitted": path in permitted,
            "change_scope": (
                "exact_Kaufman_strategy_registry_record"
                if path == rel(STRATEGY_REGISTRY)
                else "protected_unchanged"
            ),
        }
        for path in sorted(hashes_before)
    ]
    rows.append(
        {
            "path": "data/cache",
            "hash_before": cache_before,
            "hash_after": cache_after,
            "changed": cache_before != cache_after,
            "change_permitted": False,
            "change_scope": "protected_unchanged",
        }
    )
    return rows


def report_text(
    process_outcome: str,
    process_failure_reason: str,
    created: int,
    updated: int,
    exact_after: int,
    next_action: str,
) -> str:
    return f"""# Reconcile And Close Kaufman After Robustness V1

## Scope

This lifecycle correction records the final decision for exactly
`{STRATEGY_ID}`. It does not rerun or reinterpret performance evidence.

## Authoritative State

- Stage: `closed`
- Outcome: `robustness_failed`
- Primary failure reason: `concentration_risk`
- Secondary route evidence: `standalone_period_instability`
- Standalone route: `closed_exploration / period_instability`
- 20% diversifier route: `robustness_failed / concentration_risk`
- Strongest contributing trade: `2020-03-31_to_2020-09-09`
- Largest trade fraction of additive excess: `1.1337989832791708`
- Additive excess after removing that trade: `-0.006514`
- Further same-period Kaufman diagnostics authorized: `false`
- Validation supported: `false`
- Paper/demo eligible or active: `false`
- Real-money authorized: `false`

Closure applies only to the exact Rule-2, 40-session, SPY/BIL,
following-session-open configuration and its standalone and 20% frozen
reference diversifier routes. It does not close the Kaufman,
regression-channel, or breakout families.

## Reconciliation

- Process outcome: `{process_outcome}`
- Process failure reason: `{process_failure_reason or "none"}`
- Authoritative records created: `{created}`
- Authoritative records updated: `{updated}`
- Exact records after reconciliation: `{exact_after}`
- Existing trials carried forward: `4`
- New trials: `0`
- Benchmark references carried forward: `6`
- Paper/demo observations changed: `0`

## Exact Next Action

`{next_action}`

The next action was recorded and not executed.
"""


def run() -> dict[str, Any]:
    source_before = hash_paths(SOURCE_OF_TRUTH_PATHS)
    cache_before = cache_hash()
    input_hashes_before = hash_paths(INPUT_EVIDENCE_FILES)
    prior_before = lifecycle.tree_identity_hash(
        ROOT / "evidence", excluded=OUTPUT_DIR
    )
    clean_output()

    inputs = load_inputs()
    evidence_ok, evidence_blockers = evidence_gate(inputs)
    registry_before = read_yaml(STRATEGY_REGISTRY)
    registry_text_before = STRATEGY_REGISTRY.read_text(encoding="utf-8")
    exact_before, aliases_before = inspect_registry(registry_before)
    records_before = [
        row
        for row in registry_before.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
    ]

    process_outcome = PROCESS_OUTCOME_BLOCKED
    process_failure_reason = ""
    created = 0
    updated = 0
    permitted_paths: list[str] = []
    registry_validation = {"passed": False, "errors": ["not_run"]}
    if not evidence_ok:
        process_failure_reason = "methodology_failure"
    elif len(exact_before) > 1 or aliases_before:
        process_failure_reason = "status_reconciliation_required"
    else:
        created = 1 if not exact_before else 0
        updated = 0 if created else 1
        append_or_replace_record(registry_text_before)
        candidate_registry = read_yaml(STRATEGY_REGISTRY)
        registry_validation = validate_registry_data(candidate_registry)
        exact_candidate, aliases_candidate = inspect_registry(candidate_registry)
        candidate_records = [
            row
            for row in candidate_registry.get("strategies", [])
            if isinstance(row, dict)
            and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
        ]
        post_write_ok = bool(
            registry_validation["passed"]
            and len(exact_candidate) == 1
            and not aliases_candidate
            and len(candidate_records) == 1
            and required_record_complete(candidate_records[0])
        )
        if post_write_ok:
            process_outcome = PROCESS_OUTCOME_SUCCESS
            permitted_paths = [rel(STRATEGY_REGISTRY)]
        else:
            atomic_write_registry(registry_text_before)
            created = 0
            updated = 0
            process_failure_reason = "methodology_failure"

    registry_after = read_yaml(STRATEGY_REGISTRY)
    exact_after, aliases_after = inspect_registry(registry_after)
    records_after = [
        row
        for row in registry_after.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
    ]
    final_record = records_after[0] if len(records_after) == 1 else {}
    exact_after_count = len(exact_after)
    project_next_action = (
        STRATEGY_NEXT_ACTION
        if process_outcome == PROCESS_OUTCOME_SUCCESS
        else PROJECT_NEXT_ACTION_BLOCKED
    )

    source_after = hash_paths(SOURCE_OF_TRUTH_PATHS)
    cache_after = cache_hash()
    input_hashes_after = hash_paths(INPUT_EVIDENCE_FILES)
    prior_after = lifecycle.tree_identity_hash(
        ROOT / "evidence", excluded=OUTPUT_DIR
    )
    changed_paths = sorted(
        path
        for path in source_before
        if source_before[path] != source_after[path]
    )
    all_changes_permitted = set(changed_paths).issubset(set(permitted_paths))

    duplicate_check = duplicate_rows(
        exact_before,
        aliases_before,
        len(registry_before.get("strategies", [])),
    )
    fingerprint = fingerprint_rows()
    strategies = [strategy_card(process_outcome)]
    trials = trial_rows(inputs)
    benchmarks = benchmark_rows()
    process_tasks = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": process_outcome,
            "failure_reason": process_failure_reason,
            "exact_next_action": project_next_action,
            "strategy_counted": False,
            "experiment_trial_counted": False,
        }
    ]
    before_after = registry_state_rows(records_before, records_after)
    state_changes = state_change_rows(
        source_before,
        source_after,
        cache_before,
        cache_after,
        permitted_paths,
    )
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "process_outcome": process_outcome,
            "process_failure_reason": process_failure_reason,
            "authoritative_strategy_records_created": created,
            "authoritative_strategy_records_updated": updated,
            "exact_configuration_records_after_success": exact_after_count,
            "existing_experiment_trials_carried_forward": 4,
            "new_experiment_trials": 0,
            "benchmark_references_carried_forward": len(benchmarks),
            "process_tasks_created": 1,
            "paper_demo_observations_changed": 0,
            "new_strategy_candidates_created": 0,
            "strategy_stage": "closed",
            "strategy_outcome": "robustness_failed",
            "primary_failure_reason": FAILURE_REASON,
            "secondary_failure_evidence": SECONDARY_FAILURE,
            "decision_reason": DECISION_REASON,
            "further_same_period_diagnostic_authorized": False,
            "validation_supported": False,
            "paper_demo_eligible": False,
            "real_money_authorized": False,
            "exact_next_action": project_next_action,
        }
    ]
    failures = [
        {
            "entity_type": (
                "strategy_configuration"
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else "process_task"
            ),
            "entity_id": (
                STRATEGY_ID
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else TASK_ID
            ),
            "stage": "closed"
            if process_outcome == PROCESS_OUTCOME_SUCCESS
            else STAGE,
            "outcome": (
                "robustness_failed"
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else process_outcome
            ),
            "failure_reason": (
                FAILURE_REASON
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else process_failure_reason
            ),
            "decision_reason": (
                DECISION_REASON
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else "|".join(evidence_blockers)
                or "duplicate_or_alias_reconciliation_block"
            ),
            "secondary_evidence": (
                SECONDARY_FAILURE
                if process_outcome == PROCESS_OUTCOME_SUCCESS
                else ""
            ),
        }
    ]
    next_actions = [
        {
            "scope": "project",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": project_next_action,
            "execute_now": False,
        }
    ]

    lifecycle.write_csv(
        OUTPUT_DIR / "duplicate_and_alias_check.csv",
        duplicate_check,
        list(duplicate_check[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "configuration_fingerprint.csv",
        fingerprint,
        list(fingerprint[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategies,
        list(strategies[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0])
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_tasks,
        list(process_tasks[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "registry_record_before_after.csv",
        before_after,
        list(before_after[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_changes,
        list(state_changes[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        list(failures[0]),
    )
    lifecycle.write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_actions,
        list(next_actions[0]),
    )

    record_complete = bool(
        process_outcome == PROCESS_OUTCOME_SUCCESS
        and required_record_complete(final_record)
    )
    consistency_passed = bool(
        process_outcome == PROCESS_OUTCOME_SUCCESS
        and not process_failure_reason
        and evidence_ok
        and exact_after_count == 1
        and not aliases_after
        and record_complete
        and registry_validation.get("passed") is True
        and len(trials) == 4
        and len(benchmarks) == 6
        and input_hashes_before == input_hashes_after
        and prior_before == prior_after
        and cache_before == cache_after
        and all_changes_permitted
        and changed_paths == [rel(STRATEGY_REGISTRY)]
        and not any(FORBIDDEN_FLAGS.values())
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "evidence_gate_passed": evidence_ok,
        "evidence_gate_blockers": evidence_blockers,
        "registry_validation_passed": registry_validation.get("passed", False),
        "registry_validation_errors": registry_validation.get("errors", []),
        "exact_configuration_records_after_reconciliation": exact_after_count,
        "unresolved_equivalent_alias_count_after_reconciliation": len(
            aliases_after
        ),
        "authoritative_record_complete": record_complete,
        "configuration_fingerprint": configuration_fingerprint(),
        "strategy_stage": final_record.get("stage", ""),
        "strategy_outcome": final_record.get("outcome", ""),
        "strategy_failure_reason": final_record.get("failure_reason", ""),
        "strategy_secondary_failure_evidence": final_record.get(
            "secondary_failure_evidence", ""
        ),
        "strategy_next_action": final_record.get("next_action", ""),
        "further_same_period_diagnostic_authorized": final_record.get(
            "further_same_period_diagnostic_authorized"
        ),
        "closure_scope_is_exact_configuration_only": bool(
            final_record.get("family_level_interpretation")
            == FAMILY_INTERPRETATION
        ),
        "existing_experiment_trials_carried_forward": 4,
        "new_experiment_trials": 0,
        "benchmark_reference_count": 6,
        "process_task_count": 1,
        "paper_demo_observations_changed": 0,
        "new_strategy_candidates_created": 0,
        "source_of_truth_hashes_before": source_before,
        "source_of_truth_hashes_after": source_after,
        "source_of_truth_changed_paths": changed_paths,
        "permitted_changed_paths": permitted_paths,
        "all_source_of_truth_changes_permitted": all_changes_permitted,
        "input_evidence_hashes_before": input_hashes_before,
        "input_evidence_hashes_after": input_hashes_after,
        "input_evidence_hashes_unchanged": input_hashes_before
        == input_hashes_after,
        "prior_evidence_identity_hash_before": prior_before,
        "prior_evidence_identity_hash_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        **FORBIDDEN_FLAGS,
        "exact_next_action": project_next_action,
        "next_action_executed": False,
    }
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "exact_configuration_records_after_success": exact_after_count,
        "existing_experiment_trials_carried_forward": 4,
        "new_experiment_trials": 0,
        "benchmark_references_carried_forward": 6,
        "process_tasks_created": 1,
        "paper_demo_observations_changed": 0,
        "new_strategy_candidates_created": 0,
        "source_of_truth_changed_paths": changed_paths,
        "exact_next_action": project_next_action,
        "next_action_executed": False,
    }
    lifecycle.write_yaml(OUTPUT_DIR / "reconciliation_manifest.yaml", manifest)
    lifecycle.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    lifecycle.write_text(
        OUTPUT_DIR / "reconciliation_report.md",
        report_text(
            process_outcome,
            process_failure_reason,
            created,
            updated,
            exact_after_count,
            project_next_action,
        ),
    )
    actual_outputs = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    if actual_outputs != REQUIRED_OUTPUTS:
        raise RuntimeError(
            "Lifecycle artifact mismatch: "
            f"missing={sorted(REQUIRED_OUTPUTS-actual_outputs)}, "
            f"extra={sorted(actual_outputs-REQUIRED_OUTPUTS)}"
        )
    if process_outcome == PROCESS_OUTCOME_SUCCESS and not consistency_passed:
        raise RuntimeError("Kaufman lifecycle reconciliation failed consistency")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "exact_configuration_records_after_reconciliation": exact_after_count,
        "existing_experiment_trials_carried_forward": 4,
        "new_experiment_trials": 0,
        "paper_demo_observations_changed": 0,
        "consistency_passed": consistency_passed,
        "exact_next_action": project_next_action,
        "output_dir": rel(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
