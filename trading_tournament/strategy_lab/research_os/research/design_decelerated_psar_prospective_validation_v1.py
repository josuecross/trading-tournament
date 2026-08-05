from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    decelerated_psar_diversifier_final_robustness_v1 as robustness,
)
from strategy_lab.research_os.research import (
    remediate_angl_observation_required_market_data_v1 as reference_contract,
)


TASK_ID = "design_decelerated_psar_prospective_validation_v1"
MODE = "experiment-design"
STAGE = "validation"
DESIGN_ID = f"{TASK_ID}__design"
FUTURE_TRIAL_ID = "decelerated_psar_prospective_validation_v1__forward"
PARENT_TRIAL_ID = robustness.TRIAL_ID
OUTPUT_DIR = ROOT / "evidence" / "experiment_design" / TASK_ID / "latest"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\996269cd-37df-4109-a71d-5a7f57e24e5e\pasted-text.txt"
)

STANDALONE_EVIDENCE = robustness.STANDALONE_EVIDENCE
EXPLORATION_EVIDENCE = robustness.EXPLORATION_EVIDENCE
ROBUSTNESS_EVIDENCE = robustness.OUTPUT_DIR
STRATEGY_ID = robustness.STRATEGY_ID
FAMILY_ID = robustness.FAMILY_ID
ARCHITECTURE = robustness.ARCHITECTURE
SOURCE_LINEAGE = robustness.SOURCE_LINEAGE

PRIMARY_COST_BPS = 5.0
DIAGNOSTIC_COST_BPS = (0.0, 10.0)
EXACT_EXPOSURE_SPY = 0.75370177268
EXACT_EXPOSURE_BIL = 0.24629822732
MINIMUM_MONTHS = 24
MINIMUM_DEFENSIVE_EPISODES = 6
MAXIMUM_MONTHS = 36
BOOTSTRAP_SHARPE_CAVEAT = 0.3978
BOOTSTRAP_EITHER_CAVEAT = 0.7286
DESIGN_TIMESTAMP = "2026-07-29T00:00:00-06:00"

OUTCOME_COMPLETED = "prospective_validation_design_completed"
OUTCOME_BLOCKED = "prospective_validation_design_blocked"
NEXT_COMPLETED = "activate_decelerated_psar_prospective_validation_v1"
NEXT_BLOCKED = "direction_owner_review_psar_prospective_design_block_v1"
DESIGN_BLOCK_REASONS = {
    "",
    "lineage_reconciliation_failure",
    "parameter_reconciliation_failure",
    "reference_definition_unavailable",
    "methodology_failure",
}
FUTURE_OUTCOMES = (
    "validation_positive",
    "validation_mixed",
    "validation_failed",
    "validation_inconclusive_insufficient_events",
    "validation_data_or_methodology_blocked",
)
FUTURE_FAILURE_REASONS = (
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "weak_portfolio_contribution",
    "data_or_comparability_failure",
    "methodology_failure",
)
PORTFOLIO_IDS = (
    "100pct_frozen_reference",
    "80pct_reference_20pct_decelerated_psar_candidate",
    "80pct_reference_20pct_original_psar_control",
    "80pct_reference_20pct_exact_exposure_matched_control",
    "80pct_reference_20pct_SPY_200_day_trend_control",
    "80pct_reference_20pct_BIL",
    "80pct_reference_20pct_SPY_buy_and_hold",
)
CRITICAL_CONTROLS = (
    "80pct_reference_20pct_original_psar_control",
    "80pct_reference_20pct_exact_exposure_matched_control",
)

EXPECTED_REFERENCE_SYMBOLS = (
    "BIL",
    "DBC",
    "QUAL",
    "SPLV",
    "SPY",
    "USCI",
    "USMV",
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)

REQUIRED_OUTPUTS = {
    "design_manifest.yaml",
    "experiment_design_record.csv",
    "future_trial_specification.yaml",
    "strategy_and_lineage_reconciliation.csv",
    "frozen_parameter_specification.csv",
    "required_symbol_scope.csv",
    "prospective_data_snapshot_schema.csv",
    "portfolio_and_control_definitions.csv",
    "activation_boundary_rules.csv",
    "minimum_observation_requirements.csv",
    "monthly_checkpoint_schema.csv",
    "future_validation_outcome_gates.csv",
    "future_failure_reasons.csv",
    "activation_readiness_checklist.csv",
    "process_task_log.csv",
    "next_actions.csv",
    "consistency_check.json",
    "prospective_validation_design.md",
}

PROTECTED_PATHS = robustness.PROTECTED_PATHS


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def file_hash(path: Path) -> str:
    return robustness.file_hash(path)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.is_file()}


def packet_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file())


def cache_files() -> list[Path]:
    return robustness.cache_files()


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "experiment_design" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def fields_for(rows: list[dict[str, Any]], leading: list[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: list[str],
) -> None:
    path = OUTPUT_DIR / name
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
            writer.writerow(
                {field: csv_value(row.get(field, "")) for field in fields}
            )


def write_yaml(name: str, payload: dict[str, Any]) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            width=110,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def write_json(name: str, payload: dict[str, Any]) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(name: str, value: str) -> None:
    (OUTPUT_DIR / name).write_text(value.rstrip() + "\n", encoding="utf-8")


def parse_json_field(row: dict[str, str], field: str) -> dict[str, Any]:
    value = row.get(field, "")
    return json.loads(value) if value else {}


def one_row(path: Path, predicate: Any) -> dict[str, str]:
    matches = [row for row in read_csv(path) if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one authoritative row in {path}")
    return matches[0]


def reconcile_authoritative_evidence() -> dict[str, Any]:
    standalone_row = one_row(
        STANDALONE_EVIDENCE / "outcome_summary.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    exploration_trial = one_row(
        EXPLORATION_EVIDENCE / "trial_ledger.csv",
        lambda row: row.get("trial_id") == robustness.PARENT_TRIAL_ID,
    )
    robustness_trial = one_row(
        ROBUSTNESS_EVIDENCE / "trial_ledger.csv",
        lambda row: row.get("trial_id") == PARENT_TRIAL_ID,
    )
    robustness_outcome = one_row(
        ROBUSTNESS_EVIDENCE / "outcome_summary.csv",
        lambda row: row.get("trial_id") == PARENT_TRIAL_ID,
    )
    standalone_strategy = one_row(
        STANDALONE_EVIDENCE / "strategy_cards.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    standalone_parameters = parse_json_field(standalone_strategy, "parameters")
    robustness_parameters = parse_json_field(
        one_row(
            ROBUSTNESS_EVIDENCE / "strategy_cards.csv",
            lambda row: row.get("strategy_id") == STRATEGY_ID,
        ),
        "parameters",
    )
    gate = parse_json_field(robustness_outcome, "robustness_gate")
    bootstrap = gate.get("bootstrap_probabilities", {}).get(
        robustness.EXACT_EXPOSURE_ID, {}
    )
    lineage_pass = bool(
        standalone_row["outcome"] == "closed_exploration"
        and standalone_row["failure_reason"] == "benchmark_like_behavior"
        and exploration_trial["outcome"]
        == "exploratory_followup_candidate_diversifier"
        and exploration_trial["parent_trial_id"]
        == robustness.PARENT_STANDALONE_TRIAL_ID
        and robustness_trial["outcome"] == "robustness_positive"
        and robustness_trial["parent_trial_id"] == robustness.PARENT_TRIAL_ID
        and robustness_outcome["outcome_interpretation"]
        == "ready_for_prospective_validation_design"
        and robustness_outcome["independent_validation_claimed"] == "false"
        and robustness_outcome["paper_demo_eligibility_supported"] == "false"
    )
    parameter_pass = bool(
        float(standalone_parameters["AF_min"]) == 0.02
        and float(standalone_parameters["AF_max"]) == 0.20
        and float(standalone_parameters["AF_forward_step"]) == 0.02
        and float(standalone_parameters["AF_backward_step"]) == 0.05
        and int(standalone_parameters["change_period_sessions"]) == 3
        and float(standalone_parameters["change_threshold"]) == 0.02
        and float(
            robustness_parameters["corrected_exposure_control_SPY_weight"]
        )
        == EXACT_EXPOSURE_SPY
        and float(
            robustness_parameters["corrected_exposure_control_BIL_weight"]
        )
        == EXACT_EXPOSURE_BIL
        and float(robustness_parameters["outer_candidate_weight"]) == 0.20
        and float(robustness_parameters["outer_reference_weight"]) == 0.80
    )
    caveat_pass = bool(
        float(bootstrap["probability_candidate_higher_sharpe"])
        == BOOTSTRAP_SHARPE_CAVEAT
        and float(
            bootstrap[
                "probability_candidate_higher_sharpe_or_less_severe_drawdown"
            ]
        )
        == BOOTSTRAP_EITHER_CAVEAT
    )
    reference_symbols = tuple(reference_contract.REFERENCE_SYMBOLS)
    reference_pass = reference_symbols == EXPECTED_REFERENCE_SYMBOLS
    return {
        "lineage_pass": lineage_pass,
        "parameter_pass": parameter_pass,
        "caveat_pass": caveat_pass,
        "reference_pass": reference_pass,
        "reference_symbols": reference_symbols,
        "standalone_row": standalone_row,
        "exploration_trial": exploration_trial,
        "robustness_trial": robustness_trial,
        "robustness_outcome": robustness_outcome,
        "standalone_parameters": standalone_parameters,
        "robustness_parameters": robustness_parameters,
        "bootstrap_caveat": bootstrap,
    }


def design_outcome(
    reconciliation: dict[str, Any],
) -> tuple[str, str, str]:
    if not reconciliation["lineage_pass"]:
        return OUTCOME_BLOCKED, "lineage_reconciliation_failure", NEXT_BLOCKED
    if not reconciliation["parameter_pass"] or not reconciliation["caveat_pass"]:
        return OUTCOME_BLOCKED, "parameter_reconciliation_failure", NEXT_BLOCKED
    if not reconciliation["reference_pass"]:
        return OUTCOME_BLOCKED, "reference_definition_unavailable", NEXT_BLOCKED
    return OUTCOME_COMPLETED, "", NEXT_COMPLETED


def experiment_design_row(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "design_id": DESIGN_ID,
        "entity_type": "experiment_design",
        "stage": STAGE,
        "mode": MODE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "approved_route": "20pct_diversifier_only",
        "primary_claim": "portfolio_downside_and_diversification_value",
        "future_trial_id": FUTURE_TRIAL_ID,
        "future_parent_trial_id": PARENT_TRIAL_ID,
        "future_trial_record_executed": False,
        "future_trial_activated": False,
        "historical_backfill_permitted": False,
        "paper_demo_eligibility_granted": False,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "next_action_executed": False,
    }


def future_trial_specification() -> dict[str, Any]:
    return {
        "record_status": "frozen_future_specification_not_executed",
        "trial_id": FUTURE_TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": "validation",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "prospective_validation_variant",
        "changed_fields_from_parent": "prospective_evaluation_boundary_only",
        "approved_route": "20pct_diversifier_only",
        "primary_claim": "portfolio_downside_and_diversification_value",
        "flags": {
            "strategy_rule_changed": False,
            "parameters_changed": False,
            "instruments_changed": False,
            "execution_changed": False,
            "sleeve_weight_changed": False,
            "reference_changed": False,
            "controls_changed": False,
            "optimization_performed": False,
            "historical_backfill_permitted": False,
            "validation_period_observed_before_activation": False,
        },
        "prospective_boundary": {
            "start_rule": (
                "first_valid_US_trading_session_strictly_after_activation_and_all_immutable_initialization_snapshots"
            ),
            "not_earlier_than_activation_timestamp": True,
            "historical_forward_rows_prohibited": True,
            "gap_after_2026_06_18_backfill_prohibited": True,
            "historical_returns_as_prospective_observations_prohibited": True,
            "market_condition_start_selection_prohibited": True,
        },
        "observation_duration": {
            "minimum_decision_boundary": (
                "later_of_24_completed_calendar_months_and_6_completed_defensive_episodes"
            ),
            "minimum_completed_calendar_months": MINIMUM_MONTHS,
            "minimum_completed_defensive_episodes": MINIMUM_DEFENSIVE_EPISODES,
            "hard_maximum_completed_calendar_months": MAXIMUM_MONTHS,
            "maximum_boundary_insufficient_episode_outcome": (
                "validation_inconclusive_insufficient_events"
            ),
            "interim_decision_permitted": False,
        },
        "strategy": {
            "architecture": ARCHITECTURE,
            "active_asset": "SPY",
            "defensive_asset": "BIL",
            "AF_min": 0.02,
            "AF_max": 0.20,
            "AF_forward_step": 0.02,
            "AF_backward_step": 0.05,
            "change_period_sessions": 3,
            "change_threshold": 0.02,
            "acceleration_comparison": "change3 > 0.02",
            "equality_branch": "deceleration",
            "signal_timing": "completed_close",
            "execution": "following_regular_session_close",
            "library_PSAR_substitution_permitted": False,
            "leverage_allowed": False,
            "shorting_allowed": False,
        },
        "portfolio": {
            "reference_id": "frozen_current_active_vm_dsr_usci_combo",
            "reference_weight": 0.80,
            "candidate_weight": 0.20,
            "outer_rebalance": "monthly_following_session_close",
            "explicit_holdings": True,
            "natural_drift": True,
            "inner_outer_turnover_separate": True,
            "costs_charged_once": True,
        },
        "comparators": list(PORTFOLIO_IDS),
        "critical_controls": list(CRITICAL_CONTROLS),
        "exact_exposure_control": {
            "SPY": EXACT_EXPOSURE_SPY,
            "BIL": EXACT_EXPOSURE_BIL,
            "prospective_recalculation_permitted": False,
        },
        "costs_bps_per_one_way_turnover": {
            "primary": PRIMARY_COST_BPS,
            "diagnostic_ledgers": list(DIAGNOSTIC_COST_BPS),
            "diagnostic_rows_create_trials": False,
        },
        "future_outcomes": list(FUTURE_OUTCOMES),
        "paper_demo_eligibility_automatic": False,
        "real_money_authorization": False,
    }


def lineage_rows(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": 1,
            "record_id": robustness.PARENT_STANDALONE_TRIAL_ID,
            "record_type": "experiment_trial",
            "stage": "exploration",
            "role": "standalone_route_parent",
            "outcome": "closed_exploration",
            "failure_reason": "benchmark_like_behavior",
            "parent_id": "",
            "carried_forward_unchanged": True,
            "evidence_path": rel(STANDALONE_EVIDENCE),
        },
        {
            "sequence": 2,
            "record_id": robustness.PARENT_TRIAL_ID,
            "record_type": "experiment_trial",
            "stage": "exploration",
            "role": "diversifier_route_exploration",
            "outcome": "exploratory_followup_candidate_diversifier",
            "failure_reason": "",
            "parent_id": robustness.PARENT_STANDALONE_TRIAL_ID,
            "carried_forward_unchanged": True,
            "evidence_path": rel(EXPLORATION_EVIDENCE),
        },
        {
            "sequence": 3,
            "record_id": PARENT_TRIAL_ID,
            "record_type": "experiment_trial",
            "stage": "robustness",
            "role": "final_historical_robustness_parent",
            "outcome": "robustness_positive",
            "failure_reason": "",
            "parent_id": robustness.PARENT_TRIAL_ID,
            "carried_forward_unchanged": True,
            "evidence_path": rel(ROBUSTNESS_EVIDENCE),
        },
        {
            "sequence": 4,
            "record_id": FUTURE_TRIAL_ID,
            "record_type": "future_trial_specification",
            "stage": "validation",
            "role": "prospective_forward_validation",
            "outcome": "not_executed_design_only",
            "failure_reason": "",
            "parent_id": PARENT_TRIAL_ID,
            "carried_forward_unchanged": False,
            "evidence_path": rel(OUTPUT_DIR / "future_trial_specification.yaml"),
        },
    ]


def parameter_rows() -> list[dict[str, Any]]:
    values = [
        ("AF_min", 0.02, "PSAR"),
        ("AF_max", 0.20, "PSAR"),
        ("AF_forward_step", 0.02, "PSAR"),
        ("AF_backward_step", 0.05, "PSAR"),
        ("change_period_sessions", 3, "PSAR"),
        ("change_threshold", 0.02, "PSAR"),
        ("acceleration_comparison", "change3 > 0.02", "PSAR"),
        ("equality_branch", "deceleration", "PSAR"),
        ("signal_timing", "completed_close", "execution"),
        ("execution", "following_regular_session_close", "execution"),
        ("reference_weight", 0.80, "outer_portfolio"),
        ("candidate_sleeve_weight", 0.20, "outer_portfolio"),
        ("outer_rebalance", "monthly", "outer_portfolio"),
        ("exact_exposure_control_SPY", EXACT_EXPOSURE_SPY, "control"),
        ("exact_exposure_control_BIL", EXACT_EXPOSURE_BIL, "control"),
        ("primary_cost_bps_one_way", PRIMARY_COST_BPS, "cost"),
        ("diagnostic_cost_bps_one_way", list(DIAGNOSTIC_COST_BPS), "cost"),
        ("minimum_completed_months", MINIMUM_MONTHS, "decision_boundary"),
        (
            "minimum_completed_defensive_episodes",
            MINIMUM_DEFENSIVE_EPISODES,
            "decision_boundary",
        ),
        ("hard_maximum_completed_months", MAXIMUM_MONTHS, "decision_boundary"),
    ]
    return [
        {
            "parameter_name": name,
            "frozen_value": value,
            "parameter_group": group,
            "source": (
                "authoritative_PSAR_evidence_and_direction_owner_design_packet"
            ),
            "modifiable_after_activation": False,
            "result_driven_change_permitted": False,
        }
        for name, value, group in values
    ]


def symbol_scope_rows() -> list[dict[str, Any]]:
    vm = set(reference_contract.VM_SYMBOLS)
    dsr = set(reference_contract.DSR_SYMBOLS)
    usci = set(reference_contract.USCI_SYMBOLS)
    rows: list[dict[str, Any]] = []
    for symbol in EXPECTED_REFERENCE_SYMBOLS:
        components = []
        if symbol in vm:
            components.append("paper_forward_vm_quality_lowvol_proxy_v1")
        if symbol in dsr:
            components.append(
                "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
            )
        if symbol in usci:
            components.append(
                "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
            )
        control_roles = []
        if symbol in {"SPY", "BIL"}:
            control_roles.extend(PORTFOLIO_IDS[1:])
        rows.append(
            {
                "symbol": symbol,
                "required_for_frozen_reference": True,
                "frozen_reference_components": components,
                "required_for_candidate_or_controls": bool(control_roles),
                "candidate_or_control_ids": control_roles,
                "required_fields": [
                    "trading_date",
                    "adjusted_open",
                    "adjusted_high",
                    "adjusted_low",
                    "adjusted_close",
                    "adjusted_volume",
                ],
                "future_snapshot_required": True,
                "provider_access_in_design_task": False,
                "source_definition_file": (
                    "strategy_lab/research_os/research/"
                    "remediate_angl_observation_required_market_data_v1.py"
                ),
                "source_definition_constant": (
                    "VM_SYMBOLS|DSR_SYMBOLS|USCI_SYMBOLS|REFERENCE_SYMBOLS"
                ),
                "inferred_from_name": False,
            }
        )
    return rows


def snapshot_schema_rows() -> list[dict[str, Any]]:
    fields = [
        ("snapshot_id", "string", "primary immutable record identity"),
        ("snapshot_role", "enum", "initialization|signal|execution|valuation|revision_alert"),
        ("signal_date", "date", "completed session used by the signal"),
        ("retrieval_timestamp_utc", "timestamp", "capture time in UTC"),
        ("retrieval_timestamp_us_eastern", "timestamp", "capture time in U.S. Eastern time"),
        ("source_provider", "string", "authorized source identifier"),
        ("source_request_metadata", "json", "read-only request metadata without secrets"),
        ("raw_source_records", "json_or_path", "verbatim captured source records"),
        ("raw_source_hash", "sha256", "hash of immutable raw source bytes"),
        ("normalized_frame_hash", "sha256", "hash of deterministic normalized frame"),
        ("market_data_version_id", "string", "immutable market-data version identity"),
        ("symbol", "string", "one of the frozen required symbols"),
        ("adjusted_open", "float", "canonical adjusted open"),
        ("adjusted_high", "float", "canonical adjusted high"),
        ("adjusted_low", "float", "canonical adjusted low"),
        ("adjusted_close", "float", "canonical adjusted close"),
        ("adjusted_volume", "float", "canonical adjusted volume"),
        ("PSAR_state_before", "json", "recursive state before signal calculation"),
        ("calculated_PSAR", "float", "candidate PSAR after completed close"),
        ("acceleration_factor", "float", "frozen recursive AF"),
        ("extreme_point", "float", "frozen recursive EP"),
        ("trend_state", "enum", "uptrend|downtrend|uninitialized"),
        ("change3", "float", "three-session acceleration comparison input"),
        ("candidate_target", "json", "explicit SPY/BIL target"),
        ("comparator_targets", "json", "all six comparator targets"),
        ("intended_execution_date", "date", "following valid regular session"),
        ("actual_execution_status", "enum", "executed|blocked|not_due"),
        ("blocked_data_reason", "string", "explicit missing or invalid data reason"),
        ("pretrade_holdings", "json", "explicit holdings before execution"),
        ("posttrade_holdings", "json", "explicit holdings after execution"),
        ("inner_turnover", "float", "candidate/control inner one-way turnover"),
        ("outer_turnover", "float", "monthly outer one-way turnover"),
        ("initialization_turnover", "float", "separate initialization ledger"),
        ("transaction_cost", "float", "cost charged once"),
        ("cost_adjusted_NAV", "float", "post-cost NAV"),
        ("revision_alert_id", "string", "separate later-revision record"),
        ("original_snapshot_superseded", "boolean", "must always remain false"),
    ]
    return [
        {
            "field_name": name,
            "data_type": data_type,
            "definition": definition,
            "required": True,
            "immutable_after_capture": True,
            "nullable_only_when_not_applicable": name
            in {
                "blocked_data_reason",
                "revision_alert_id",
                "adjusted_open",
                "adjusted_high",
                "adjusted_low",
                "adjusted_close",
                "adjusted_volume",
            },
            "validation_decision_field": name
            not in {"source_request_metadata", "revision_alert_id"},
        }
        for name, data_type, definition in fields
    ]


def portfolio_rows() -> list[dict[str, Any]]:
    definitions = {
        PORTFOLIO_IDS[0]: (
            "100% frozen_current_active_vm_dsr_usci_combo",
            "frozen_reference",
        ),
        PORTFOLIO_IDS[1]: (
            "80% frozen reference plus 20% Decelerated PSAR SPY/BIL sleeve",
            "candidate",
        ),
        PORTFOLIO_IDS[2]: (
            "80% frozen reference plus 20% ordinary PSAR SPY/BIL sleeve",
            "critical_control",
        ),
        PORTFOLIO_IDS[3]: (
            "80% frozen reference plus 20% monthly static 0.75370177268 SPY and 0.24629822732 BIL sleeve",
            "critical_control",
        ),
        PORTFOLIO_IDS[4]: (
            "80% frozen reference plus 20% SPY 200-session trend sleeve",
            "additional_control",
        ),
        PORTFOLIO_IDS[5]: (
            "80% frozen reference plus 20% BIL buy-and-hold sleeve",
            "additional_control",
        ),
        PORTFOLIO_IDS[6]: (
            "80% frozen reference plus 20% SPY buy-and-hold sleeve",
            "additional_control",
        ),
    }
    return [
        {
            "portfolio_id": portfolio_id,
            "entity_type": "benchmark_specification",
            "stage": "benchmark_reference_only",
            "role": definitions[portfolio_id][1],
            "definition": definitions[portfolio_id][0],
            "reference_weight": 1.0 if portfolio_id == PORTFOLIO_IDS[0] else 0.8,
            "sleeve_weight": 0.0 if portfolio_id == PORTFOLIO_IDS[0] else 0.2,
            "outer_rebalance": (
                "frozen_reference_convention"
                if portfolio_id == PORTFOLIO_IDS[0]
                else "monthly_following_session_close"
            ),
            "natural_drift": True,
            "costs_charged_once": True,
            "critical_control": portfolio_id in CRITICAL_CONTROLS,
            "counted_as_strategy": False,
            "counted_as_executed_trial": False,
        }
        for portfolio_id in PORTFOLIO_IDS
    ]


def activation_boundary_rows() -> list[dict[str, Any]]:
    rules = [
        ("start_after_activation", "start strictly after activation task completes"),
        ("start_after_snapshots", "start strictly after every immutable initialization snapshot is captured"),
        ("valid_US_session", "start must be a valid U.S. regular trading session"),
        ("not_before_activation", "start cannot precede any recorded activation timestamp"),
        ("no_historical_rows", "historical forward-row creation is prohibited"),
        ("no_gap_backfill", "the interval after 2026-06-18 cannot be retrospectively filled"),
        ("no_historical_observations", "historical returns cannot become prospective observations"),
        ("no_market_timing", "start date cannot be chosen from market conditions"),
        ("initialization_separate", "initialization is separately labeled and has no performance row"),
        ("missing_execution_data", "block execution rather than forward-fill a tradable price"),
    ]
    return [
        {
            "rule_id": rule_id,
            "rule": rule,
            "frozen_before_activation": True,
            "exception_permitted": False,
            "activation_task_must_verify": True,
        }
        for rule_id, rule in rules
    ]


def minimum_observation_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": "completed_calendar_months",
            "minimum": MINIMUM_MONTHS,
            "maximum": MAXIMUM_MONTHS,
            "unit": "completed_calendar_months",
            "decision_rule": "minimum_boundary_uses_later_of_months_and_episodes",
        },
        {
            "requirement_id": "completed_defensive_episodes",
            "minimum": MINIMUM_DEFENSIVE_EPISODES,
            "maximum": "",
            "unit": "SPY_to_BIL_to_SPY_completed_episodes",
            "decision_rule": "minimum_boundary_uses_later_of_months_and_episodes",
        },
        {
            "requirement_id": "hard_maximum",
            "minimum": "",
            "maximum": MAXIMUM_MONTHS,
            "unit": "completed_calendar_months",
            "decision_rule": (
                "at_36_months_with_fewer_than_6_episodes_use_validation_inconclusive_insufficient_events"
            ),
        },
        {
            "requirement_id": "interim_reports",
            "minimum": 1,
            "maximum": MAXIMUM_MONTHS,
            "unit": "monthly_checkpoints",
            "decision_rule": "reporting_allowed_but_no_decision_before_minimum_boundary",
        },
    ]


def checkpoint_schema_rows() -> list[dict[str, Any]]:
    fields = [
        ("checkpoint_id", "string"),
        ("checkpoint_month_end", "date"),
        ("elapsed_completed_months", "integer"),
        ("completed_defensive_episodes", "integer"),
        ("minimum_decision_boundary_met", "boolean"),
        ("hard_maximum_boundary_met", "boolean"),
        ("portfolio_id", "string"),
        ("NAV", "float"),
        ("total_return", "float"),
        ("CAGR_when_mathematically_meaningful", "float"),
        ("annualized_volatility", "float"),
        ("Sharpe_ratio", "float"),
        ("maximum_drawdown", "float"),
        ("inner_turnover", "float"),
        ("outer_turnover", "float"),
        ("initialization_turnover_excluded", "float"),
        ("transaction_costs", "float"),
        ("reference_negative_month_count", "integer"),
        ("average_candidate_minus_reference_negative_month_return", "float"),
        ("negative_month_outperformance_fraction", "float"),
        ("PSAR_state_counts", "json"),
        ("PSAR_state_durations", "json"),
        ("missing_or_blocked_observations", "json"),
        ("data_revision_alerts", "json"),
        ("interim_strategy_change_permitted", "boolean_false"),
        ("interim_favorable_stop_permitted", "boolean_false"),
        ("validation_decision", "blank_until_boundary"),
    ]
    return [
        {
            "field_name": name,
            "data_type": data_type,
            "required_at_monthly_checkpoint": True,
            "creates_separate_trial": False,
            "used_to_modify_strategy": False,
        }
        for name, data_type in fields
    ]


def future_outcome_gate_rows() -> list[dict[str, Any]]:
    positive_conditions = [
        "all_data_timing_accounting_and_exposure_invariants_pass",
        "at_least_24_completed_months_and_6_completed_defensive_episodes",
        "candidate_not_worse_than_reference_on_both_Sharpe_and_drawdown",
        "candidate_reference_Sharpe_improvement_at_least_0_02_or_drawdown_improvement_at_least_0_01",
        "neither_critical_control_dominates_on_CAGR_Sharpe_and_drawdown",
        "materiality_vs_each_critical_control_separately",
        "reference_drawdown_improved_in_at_least_4_of_first_6_defensive_episodes",
        "negative_reference_month_average_excess_positive_and_outperformance_fraction_above_0_50",
        "at_10bps_candidate_not_worse_than_reference_on_both_Sharpe_and_drawdown",
        "no_unresolved_revision_or_reconciliation_issue_could_change_target_or_return",
    ]
    return [
        {
            "future_outcome": "validation_positive",
            "conditions": positive_conditions,
            "decision_timing": "after_minimum_boundary_only",
            "primary_failure_reason_required": False,
            "validated_claim": (
                "exact_20pct_diversifier_route_under_prospective_snapshot_data"
            ),
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_mixed",
            "conditions": [
                "candidate_improves_reference",
                "critical_control_episode_cost_or_downside_evidence_conflicts",
            ],
            "decision_timing": "after_minimum_boundary_only",
            "primary_failure_reason_required": True,
            "validated_claim": "",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_failed",
            "conditions": [
                "reference_materiality_fails_or_critical_control_dominates_or_candidate_worsens_both_reference_metrics",
                "episode_benefit_not_repeatable_or_advantage_disappears_at_10bps",
            ],
            "decision_timing": "after_minimum_boundary_only",
            "primary_failure_reason_required": True,
            "validated_claim": "",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_inconclusive_insufficient_events",
            "conditions": [
                "36_completed_calendar_months",
                "fewer_than_6_completed_defensive_episodes",
            ],
            "decision_timing": "hard_maximum_boundary",
            "primary_failure_reason_required": False,
            "validated_claim": "",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_data_or_methodology_blocked",
            "conditions": [
                "unresolved_data_timing_accounting_revision_or_comparability_failure"
            ],
            "decision_timing": "immediate_operational_block_or_boundary",
            "primary_failure_reason_required": True,
            "validated_claim": "",
            "automatic_paper_demo_eligibility": False,
        },
    ]


def failure_reason_rows() -> list[dict[str, Any]]:
    design_reasons = [
        "lineage_reconciliation_failure",
        "parameter_reconciliation_failure",
        "reference_definition_unavailable",
        "methodology_failure",
    ]
    rows = [
        {
            "reason_scope": "future_validation",
            "failure_reason": reason,
            "allowed_for_outcomes": [
                "validation_mixed",
                "validation_failed",
                "validation_data_or_methodology_blocked",
            ],
            "frozen_before_activation": True,
        }
        for reason in FUTURE_FAILURE_REASONS
    ]
    rows.extend(
        {
            "reason_scope": "design_task",
            "failure_reason": reason,
            "allowed_for_outcomes": [OUTCOME_BLOCKED],
            "frozen_before_activation": True,
        }
        for reason in design_reasons
    )
    return rows


def readiness_rows() -> list[dict[str, Any]]:
    items = [
        ("exact_symbol_scope_available", "all 17 frozen reference/candidate/control symbols are available"),
        ("immutable_snapshots_supported", "raw and normalized immutable prospective snapshots can be stored"),
        ("initialization_without_backfill", "candidate and reference states initialize without performance backfill"),
        ("identical_sessions", "candidate, reference and all controls can be valued on identical sessions"),
        ("storage_roles_separate", "initialization, signal, execution and completed performance rows are distinct"),
        ("brokerless_operation", "no broker or order path is required"),
        ("cost_ledgers_ready", "inner, outer and initialization turnover plus 0/5/10-bps ledgers are separate"),
        ("revision_log_ready", "later revisions append alerts without overwriting original snapshots"),
    ]
    return [
        {
            "check_id": check_id,
            "activation_requirement": requirement,
            "status_in_design_task": "specified_not_executed",
            "later_activation_must_verify": True,
            "bounded_readiness_attempts_allowed": 1,
            "failure_action": "remain_unactivated",
        }
        for check_id, requirement in items
    ]


def validate_design_schemas(
    experiment_rows: list[dict[str, Any]],
    lineage: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    portfolios: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, bool]:
    return {
        "one_experiment_design_record": len(experiment_rows) == 1,
        "zero_executed_trial_records": not experiment_rows[0][
            "future_trial_record_executed"
        ],
        "lineage_complete": len(lineage) == 4
        and lineage[-1]["record_type"] == "future_trial_specification",
        "parameters_complete": len(parameters) == 20,
        "exact_reference_symbol_scope": tuple(row["symbol"] for row in symbols)
        == EXPECTED_REFERENCE_SYMBOLS,
        "snapshot_schema_complete": len(snapshots) >= 30,
        "seven_benchmark_specifications": len(portfolios) == 7,
        "five_future_outcomes": tuple(row["future_outcome"] for row in outcomes)
        == FUTURE_OUTCOMES,
        "no_historical_calculation": True,
        "no_activation": True,
    }


def design_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> str:
    return f"""# Decelerated PSAR Prospective Validation Design V1

## Scope

This packet freezes a future prospective validation for
`barbara_decelerated_psar_spy_bil_v1` under the
`20pct_diversifier_only` route. It creates an experiment design, not an
executed trial or observation.

The standalone route remains `closed_exploration`. Historical robustness
remains `robustness_positive` over the already-viewed period and is not
reclassified as independent validation.

## Claim

The prospective claim is limited to
`portfolio_downside_and_diversification_value`. It does not claim standalone
alpha or guaranteed Sharpe superiority. The historical paired-bootstrap
probability of higher Sharpe versus exact exposure matching was `0.3978`;
the probability of higher Sharpe or less severe drawdown was `0.7286`.

## Frozen Boundary

The future observation begins only on a valid U.S. trading session strictly
after activation and immutable initialization snapshots. No interval after
`2026-06-18` may be backfilled. Initialization has no performance row.

The decision boundary is the later of 24 completed calendar months and six
completed SPY-to-BIL-to-SPY defensive episodes. At 36 months with fewer than
six completed episodes, the outcome is
`validation_inconclusive_insufficient_events`.

## Data And Accounting

The exact 17-symbol reference/candidate/control scope is frozen in
`required_symbol_scope.csv`. Raw snapshots, normalized hashes, recursive PSAR
state, target decisions, execution status, explicit holdings, turnover, costs,
and NAV are immutable. Revisions append alerts and cannot overwrite the
decision record.

## Design Outcome

* Outcome: `{outcome}`
* Failure reason: `{failure_reason or "none"}`
* Exact next action: `{next_action}`

The next action was not executed. No historical calculation, activation,
paper/demo eligibility, provider access, broker action, or real-money action
occurred.
"""


def run() -> dict[str, Any]:
    protected_before = map_hashes(PROTECTED_PATHS)
    cache_before = map_hashes(cache_files())
    standalone_before = map_hashes(packet_files(STANDALONE_EVIDENCE))
    exploration_before = map_hashes(packet_files(EXPLORATION_EVIDENCE))
    robustness_before = map_hashes(packet_files(ROBUSTNESS_EVIDENCE))
    source_before = file_hash(SOURCE_PACKET)

    clean_output()
    reconciliation = reconcile_authoritative_evidence()
    outcome, failure_reason, next_action = design_outcome(reconciliation)
    if failure_reason not in DESIGN_BLOCK_REASONS:
        raise RuntimeError("Unexpected design failure reason")

    experiment_rows = [
        experiment_design_row(outcome, failure_reason, next_action)
    ]
    future_spec = future_trial_specification()
    lineage = lineage_rows(reconciliation)
    parameters = parameter_rows()
    symbols = symbol_scope_rows()
    snapshots = snapshot_schema_rows()
    portfolios = portfolio_rows()
    boundaries = activation_boundary_rows()
    minimums = minimum_observation_rows()
    checkpoints = checkpoint_schema_rows()
    outcome_gates = future_outcome_gate_rows()
    failures = failure_reason_rows()
    readiness = readiness_rows()
    schema_checks = validate_design_schemas(
        experiment_rows,
        lineage,
        parameters,
        symbols,
        snapshots,
        portfolios,
        outcome_gates,
    )

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "design_id": DESIGN_ID,
        "strategy_id": STRATEGY_ID,
        "approved_route": "20pct_diversifier_only",
        "future_trial_id": FUTURE_TRIAL_ID,
        "future_parent_trial_id": PARENT_TRIAL_ID,
        "future_trial_status": "frozen_specification_not_executed",
        "primary_claim": "portfolio_downside_and_diversification_value",
        "historical_period_role": "viewed_development_and_robustness_evidence_not_independent_validation",
        "historical_period_end": "2026-06-18",
        "historical_bootstrap_caveat": {
            "probability_higher_sharpe_vs_exact_exposure": (
                BOOTSTRAP_SHARPE_CAVEAT
            ),
            "probability_higher_sharpe_or_less_severe_drawdown_vs_exact_exposure": (
                BOOTSTRAP_EITHER_CAVEAT
            ),
        },
        "minimum_completed_months": MINIMUM_MONTHS,
        "minimum_completed_defensive_episodes": MINIMUM_DEFENSIVE_EPISODES,
        "hard_maximum_completed_months": MAXIMUM_MONTHS,
        "required_symbol_count": len(symbols),
        "strategy_configurations_created": 0,
        "experiment_trials_executed": 0,
        "paper_demo_observations": 0,
        "experiment_design_records": 1,
        "process_tasks": 1,
        "benchmark_specifications": 7,
        "data_capability_tasks": 0,
        "historical_calculations_executed": 0,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    process = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": outcome,
            "exact_next_action": next_action,
            "executed_trial_count": 0,
            "activated_observation_count": 0,
            "historical_calculation_count": 0,
            "provider_access": False,
            "broker_or_order_action": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    next_actions = [
        {
            "scope": "experiment_design",
            "design_id": DESIGN_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "scope": "future_trial_specification",
            "design_id": DESIGN_ID,
            "outcome": "not_executed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
    ]
    reconciliation_rows = lineage + [
        {
            "sequence": 5,
            "record_id": "exact_exposure_control_methodology",
            "record_type": "methodology_reconciliation",
            "stage": "robustness",
            "role": "exact_control_weight",
            "outcome": "reconciled",
            "failure_reason": "",
            "parent_id": PARENT_TRIAL_ID,
            "carried_forward_unchanged": True,
            "evidence_path": rel(
                ROBUSTNESS_EVIDENCE
                / "exposure_control_weight_correction.csv"
            ),
            "SPY_weight": EXACT_EXPOSURE_SPY,
            "BIL_weight": EXACT_EXPOSURE_BIL,
        },
        {
            "sequence": 6,
            "record_id": "historical_bootstrap_caveat",
            "record_type": "interpretation_reconciliation",
            "stage": "robustness",
            "role": "claim_constraint",
            "outcome": "reconciled",
            "failure_reason": "",
            "parent_id": PARENT_TRIAL_ID,
            "carried_forward_unchanged": True,
            "evidence_path": rel(ROBUSTNESS_EVIDENCE / "bootstrap_results.csv"),
            "probability_higher_sharpe": BOOTSTRAP_SHARPE_CAVEAT,
            "probability_higher_sharpe_or_less_severe_drawdown": (
                BOOTSTRAP_EITHER_CAVEAT
            ),
        },
    ]

    write_yaml("design_manifest.yaml", manifest)
    write_csv(
        "experiment_design_record.csv",
        experiment_rows,
        ["design_id", "entity_type"],
    )
    write_yaml("future_trial_specification.yaml", future_spec)
    write_csv(
        "strategy_and_lineage_reconciliation.csv",
        reconciliation_rows,
        ["sequence", "record_id", "record_type"],
    )
    write_csv(
        "frozen_parameter_specification.csv",
        parameters,
        ["parameter_name"],
    )
    write_csv("required_symbol_scope.csv", symbols, ["symbol"])
    write_csv(
        "prospective_data_snapshot_schema.csv",
        snapshots,
        ["field_name"],
    )
    write_csv(
        "portfolio_and_control_definitions.csv",
        portfolios,
        ["portfolio_id"],
    )
    write_csv(
        "activation_boundary_rules.csv",
        boundaries,
        ["rule_id"],
    )
    write_csv(
        "minimum_observation_requirements.csv",
        minimums,
        ["requirement_id"],
    )
    write_csv(
        "monthly_checkpoint_schema.csv",
        checkpoints,
        ["field_name"],
    )
    write_csv(
        "future_validation_outcome_gates.csv",
        outcome_gates,
        ["future_outcome"],
    )
    write_csv(
        "future_failure_reasons.csv",
        failures,
        ["reason_scope", "failure_reason"],
    )
    write_csv(
        "activation_readiness_checklist.csv",
        readiness,
        ["check_id"],
    )
    write_csv("process_task_log.csv", process, ["task_id"])
    write_csv("next_actions.csv", next_actions, ["scope", "design_id"])
    write_text(
        "prospective_validation_design.md",
        design_report(outcome, failure_reason, next_action),
    )

    protected_after = map_hashes(PROTECTED_PATHS)
    cache_after = map_hashes(cache_files())
    standalone_after = map_hashes(packet_files(STANDALONE_EVIDENCE))
    exploration_after = map_hashes(packet_files(EXPLORATION_EVIDENCE))
    robustness_after = map_hashes(packet_files(ROBUSTNESS_EVIDENCE))
    source_after = file_hash(SOURCE_PACKET)
    outputs_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    required_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    schema_validation_pass = all(schema_checks.values())
    consistency = {
        "task_id": TASK_ID,
        "design_id": DESIGN_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            outcome == OUTCOME_COMPLETED
            and schema_validation_pass
            and outputs_before_consistency == required_before_consistency
            and protected_before == protected_after
            and cache_before == cache_after
            and standalone_before == standalone_after
            and exploration_before == exploration_after
            and robustness_before == robustness_after
            and source_before == source_after
        ),
        "schema_validation_pass": schema_validation_pass,
        "schema_checks": schema_checks,
        "required_outputs_exact_before_consistency_write": (
            outputs_before_consistency == required_before_consistency
        ),
        "lineage_reconciliation_pass": reconciliation["lineage_pass"],
        "parameter_reconciliation_pass": reconciliation["parameter_pass"],
        "bootstrap_caveat_reconciliation_pass": reconciliation["caveat_pass"],
        "reference_definition_pass": reconciliation["reference_pass"],
        "reference_symbols": list(reconciliation["reference_symbols"]),
        "strategy_configurations_created": 0,
        "experiment_trials_executed": 0,
        "future_trial_specifications_created": 1,
        "paper_demo_observations_created": 0,
        "experiment_design_records_created": 1,
        "process_tasks_created": 1,
        "benchmark_specifications_created": 7,
        "data_capability_tasks_created": 0,
        "historical_calculations_executed": 0,
        "historical_backfill_performed": False,
        "trial_activated": False,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "standalone_evidence_unchanged": standalone_before == standalone_after,
        "exploration_evidence_unchanged": exploration_before == exploration_after,
        "robustness_evidence_unchanged": robustness_before == robustness_after,
        "prior_PSAR_evidence_unchanged": bool(
            standalone_before == standalone_after
            and exploration_before == exploration_after
            and robustness_before == robustness_after
        ),
        "source_packet_unchanged": source_before == source_after,
        "provider_access": False,
        "network_access": False,
        "broker_or_order_action": False,
        "lifecycle_state_changed": False,
        "paper_demo_action": False,
        "real_money_action": False,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    final_outputs_exact = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    } == REQUIRED_OUTPUTS
    if not final_outputs_exact:
        raise RuntimeError("Design evidence output set does not match contract")
    return {
        "task_id": TASK_ID,
        "design_id": DESIGN_ID,
        "strategy_id": STRATEGY_ID,
        "future_trial_id": FUTURE_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "future_trial_executed": False,
        "trial_activated": False,
        "evidence_path": rel(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
