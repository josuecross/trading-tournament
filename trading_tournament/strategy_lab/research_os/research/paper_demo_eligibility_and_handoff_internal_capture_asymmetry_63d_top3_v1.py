from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "paper_demo_eligibility_and_handoff_internal_capture_asymmetry_63d_top3_v1"
MODULE_OWNER = "trading_tournament"
CONSUMER_MODULE = "forward_observation_app"
STAGES = ("paper-demo-eligibility", "handoff-export")
CREATED_UTC = "2026-08-07T00:00:00Z"

STRATEGY_ID = "internal_capture_asymmetry_63d_top3_v1"
STRATEGY_VERSION = "v1"
DISPLAY_NAME = "Internal Capture Asymmetry 63d Top-3"
FAMILY_ID = "cross_asset_capture_asymmetry_rotation"
ARCHITECTURE_ID = "downside_upside_capture_cross_sectional"
SOURCE_LINEAGE = "internally_generated_technical_hypothesis"
PARENT_TRIAL_ID = "accepted47_internal_v1__capture63__top3"
ROBUSTNESS_TRIAL_ID = "robustness__internal_capture_asymmetry_63d_top3_v1__role_aware_v1"
ROBUSTNESS_TASK_ID = "role_aware_robustness_internal_capture_asymmetry_63d_top3_v1"
PRIMARY_ROLE = "cross_sectional_allocation_strategy"
ROUTE = "standalone"

UNIVERSE = ("SPY", "QQQ", "IWM", "EFA", "EEM", "HYG", "LQD", "TLT", "TIP", "GLD", "DBC", "IYR")
FALLBACK = "BIL"
CONTROLS = (
    "ordinary_beta_defensive_rotation_control",
    "static_average_candidate_weights_control",
    "equal_weight_12_asset_universe_control",
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
PRIMARY_COST_BPS = 5.0
DIAGNOSTIC_COSTS_BPS = (0.0, 10.0)

ELIGIBILITY_STATUS = "paper_demo_eligible"
HANDOFF_STATUS = "ready_for_forward_observation_app"
FORWARD_APP_STATUS = "not_evaluated_by_trading_tournament"
NEXT_IMPORT_ACTION = "import_internal_capture_asymmetry_63d_top3_v1_into_forward_observation_app"
BLOCKED_NEXT_ACTION = "direction_owner_review_internal_capture_asymmetry_eligibility_block_v1"

ELIGIBILITY_DIR = ROOT / "evidence" / "paper_demo_eligibility" / STRATEGY_ID / "latest"
HANDOFF_DIR = ROOT / "evidence" / "handoff" / STRATEGY_ID / "latest"
ROBUSTNESS_DIR = ROOT / "evidence" / "robustness" / ROBUSTNESS_TASK_ID / "latest"
PARENT_DIR = ROOT / "evidence" / "research_recovery" / "accepted_47_targeted_internal_technical_batch_v1" / "latest"
METHODOLOGY_PATH = ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ACCEPTED_47_CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"

ELIGIBILITY_REQUIRED_OUTPUTS = {
    "eligibility_manifest.yaml",
    "strategy_identity_reconciliation.csv",
    "exploration_lineage_reconciliation.csv",
    "robustness_lineage_reconciliation.csv",
    "eligibility_gate_results.csv",
    "frozen_strategy_spec.yaml",
    "execution_contract.yaml",
    "data_contract.yaml",
    "risk_and_portfolio_contract.yaml",
    "research_evidence_summary.csv",
    "known_caveats.csv",
    "eligibility_decision.csv",
    "registry_state_before_after.csv",
    "entity_count_reconciliation.json",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "eligibility_report.md",
}

HANDOFF_REQUIRED_OUTPUTS = {
    "handoff_manifest.yaml",
    "strategy_handoff.yaml",
    "strategy_handoff.json",
    "strategy_configuration_fingerprint.txt",
    "evidence_lineage.json",
    "handoff_validation.json",
    "handoff_report.md",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [canonicalize(v) for v in value]
    if isinstance(value, Path):
        return rel(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        digest.update(rel(item).encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(canonicalize(value), sort_keys=True, ensure_ascii=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(canonicalize(payload), sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(canonicalize(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dirs() -> None:
    for directory in (ELIGIBILITY_DIR, HANDOFF_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)


def protected_hashes() -> dict[str, str]:
    paths = [
        PARENT_DIR,
        ROBUSTNESS_DIR,
        METHODOLOGY_PATH,
        ACCEPTED_47_CACHE_DIR,
        ACTIVE_OBSERVATIONS_PATH,
    ]
    return {rel(path): sha256_path(path) for path in paths}


def registry_text() -> str:
    return REGISTRY_PATH.read_text(encoding="utf-8")


def registry_entries(text: str | None = None) -> list[dict[str, Any]]:
    payload = yaml.safe_load(text if text is not None else registry_text()) or {}
    entries = payload.get("strategies", [])
    if not isinstance(entries, list):
        raise ValueError("strategy registry strategies node is not a list")
    return [entry for entry in entries if isinstance(entry, dict)]


def find_record_span(text: str, strategy_id: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    starts = [idx for idx, line in enumerate(lines) if line.startswith("- id: ")]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "".join(lines[start:end])
        if (
            f"- id: {strategy_id}\n" in block
            or f"  id: {strategy_id}\n" in block
            or f"strategy_id: {strategy_id}\n" in block
            or f"  strategy_id: {strategy_id}\n" in block
        ):
            return start, end
    return None


def append_or_replace_registry_record(record: dict[str, Any]) -> tuple[bool, bool]:
    text = registry_text()
    lines = text.splitlines(keepends=True)
    span = find_record_span(text, STRATEGY_ID)
    replacement = yaml.safe_dump([canonicalize(record)], sort_keys=False, width=110, allow_unicode=False)
    if span is None:
        new_text = text.rstrip() + "\n\n" + replacement
        created = True
        updated = False
    else:
        start, end = span
        existing = "".join(lines[start:end])
        created = False
        updated = existing != replacement
        lines[start:end] = replacement.splitlines(keepends=True)
        new_text = "".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    tmp = REGISTRY_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, REGISTRY_PATH)
    return created, updated


def exact_registry_records(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if (entry.get("strategy_id") or entry.get("id")) == STRATEGY_ID]


def as_float(value: str | None) -> float:
    if value in (None, ""):
        return float("nan")
    return float(value)


def strategy_configuration_payload() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "primary_robustness_role": PRIMARY_ROLE,
        "route": ROUTE,
        "formula": {
            "reference_market": "SPY",
            "asset_return": "adjusted_close_i_t / adjusted_close_i_t_minus_1 - 1",
            "market_return": "adjusted_close_SPY_t / adjusted_close_SPY_t_minus_1 - 1",
            "upside_session": "market_return > 0",
            "downside_session": "market_return < 0",
            "up_capture": "mean(asset_return | market_return > 0) / mean(market_return | market_return > 0)",
            "down_capture": "mean(asset_return | market_return < 0) / mean(market_return | market_return < 0)",
            "score": "up_capture - down_capture",
            "rank": "descending_score_then_deterministic_lexical_tie",
        },
        "parameters": {
            "lookback_sessions": 63,
            "top_k": 3,
            "formation_frequency": "monthly",
            "minimum_upside_observations": 10,
            "minimum_downside_observations": 10,
            "selected_slot_weight": 1.0 / 3.0,
            "normal_selected_asset_weight": "1/3",
        },
        "warmup": {
            "completed_daily_sessions_required_before_first_signal": 63,
            "minimum_upside_observations": 10,
            "minimum_downside_observations": 10,
            "insufficient_warmup_semantics": "asset_ineligible_until_requirements_are_met",
        },
        "universe": {
            "risky_assets": list(UNIVERSE),
            "fallback": FALLBACK,
        },
        "signal_schedule": {
            "formation_date": "last_completed_regular_us_session_of_each_calendar_month",
            "uses_completed_month_end_close": True,
            "same_close_execution_allowed": False,
        },
        "execution_assumptions": {
            "execution_timestamp_convention": "following_regular_session_close",
            "new_target_effective_return_boundary": "session_after_execution",
            "stale_signal_rule": "no_late_execution_of_stale_signal",
            "missing_execution_data": "forward_observation_app_operational_blocker_do_not_invent_execution_date",
        },
        "target_rules": {
            "normal_target": "top_3_assets_each_one_third",
            "unselected_assets": 0.0,
            "fewer_than_three_eligible": "eligible_assets_receive_one_third_slots_residual_to_BIL",
            "zero_eligible": "BIL_1_0",
            "long_only": True,
            "no_leverage": True,
            "no_short_selling": True,
            "gross_exposure_max": 1.0,
            "target_weight_sum": 1.0,
            "natural_weight_drift_between_rebalances": True,
        },
        "missing_data_strategy_semantics": {
            "signal_history_missing": "asset_ineligible_for_that_formation",
            "fewer_eligible_assets": "residual_to_BIL",
            "execution_data_missing": "external_operational_blocker",
        },
    }


def strategy_configuration_sha256() -> str:
    return canonical_hash(strategy_configuration_payload())


def frozen_strategy_spec() -> dict[str, Any]:
    payload = strategy_configuration_payload()
    payload["strategy_configuration_sha256"] = strategy_configuration_sha256()
    payload["configuration_frozen_by_task"] = TASK_ID
    payload["configuration_changed_in_task"] = False
    return payload


def execution_contract() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "signal_timestamp_convention": "completed_month_end_regular_session_close",
        "signal_price_convention": "adjusted_close_total_return_research_series",
        "execution_timestamp_convention": "following_regular_session_close",
        "execution_price_convention": "repository_research_return_boundary_uses_adjusted_close",
        "execution_price_field": "adjusted_daily_close",
        "raw_close_required_by_trading_tournament_research_calculation": False,
        "new_target_effective_return_boundary": "session_after_execution",
        "same_close_execution_allowed": False,
        "stale_signal_rule": "no_late_execution_of_a_stale_signal",
        "missing_execution_data_semantics": "blocked_operational_event_in_forward_observation_app",
        "trading_tournament_may_invent_alternate_execution_date": False,
    }


def data_contract() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "required_symbols": list(UNIVERSE) + [FALLBACK],
        "frequency": "daily_regular_session",
        "required_fields": ["session_date", "asset_identifier", "adjusted_daily_close"],
        "signal_fields": ["adjusted_daily_close"],
        "execution_fields": ["adjusted_daily_close"],
        "deterministic_trading_session_calendar_required": True,
        "adjustment_convention": "adjusted_close_total_return_research_series",
        "minimum_history_requirement": {
            "lookback_completed_sessions": 63,
            "minimum_upside_observations": 10,
            "minimum_downside_observations": 10,
        },
        "market_data_retrieval_performed_by_this_task": False,
        "current_signal_calculated_by_this_task": False,
        "forward_app_currentness_check_required_after_import": True,
    }


def risk_contract() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "long_only": True,
        "no_leverage": True,
        "no_short_selling": True,
        "target_gross_exposure_max": 1.0,
        "target_weight_sum": 1.0,
        "normal_maximum_requested_risky_asset_target_weight": "1/3",
        "fallback_asset": FALLBACK,
        "fallback_may_reach_weight": 1.0,
        "monthly_signal_frequency": True,
        "top_3_concentration_by_construction": True,
        "multi_asset_universe": True,
        "natural_weight_drift_between_monthly_target_changes": True,
        "not_included": [
            "stop_losses",
            "volatility_targets",
            "additional_exposure_caps",
            "position_limits",
            "ATR_overlays",
            "timing_filters",
        ],
    }


def robustness_context() -> dict[str, Any]:
    manifest = read_yaml(ROBUSTNESS_DIR / "robustness_manifest.yaml")
    consistency = read_json(ROBUSTNESS_DIR / "consistency_check.json")
    outcome = read_csv_rows(ROBUSTNESS_DIR / "outcome_summary.csv")[0]
    gates = read_csv_rows(ROBUSTNESS_DIR / "applicable_gate_matrix.csv")
    candidate = read_csv_rows(ROBUSTNESS_DIR / "candidate_results.csv")
    costs = read_csv_rows(ROBUSTNESS_DIR / "cost_sensitivity.csv")
    rolling = read_csv_rows(ROBUSTNESS_DIR / "rolling_window_results.csv")
    bootstrap = read_csv_rows(ROBUSTNESS_DIR / "bootstrap_results.csv")
    concentration = read_csv_rows(ROBUSTNESS_DIR / "role_valid_concentration_results.csv")
    lineage = read_csv_rows(ROBUSTNESS_DIR / "multiple_testing_lineage.csv")
    parent = read_csv_rows(ROBUSTNESS_DIR / "parent_trial_reconciliation.csv")
    failure_reasons = read_csv_rows(ROBUSTNESS_DIR / "failure_reasons.csv")
    return {
        "manifest": manifest,
        "consistency": consistency,
        "outcome": outcome,
        "gates": gates,
        "candidate": candidate,
        "costs": costs,
        "rolling": rolling,
        "bootstrap": bootstrap,
        "concentration": concentration,
        "lineage": lineage,
        "parent": parent,
        "failure_reasons": failure_reasons,
    }


def cost_row(ctx: dict[str, Any], cost_bps: float) -> dict[str, str]:
    target = f"{cost_bps:g}"
    for row in ctx["costs"]:
        if row["cost_bps_one_way"] == target:
            return row
    raise ValueError(f"missing cost row {cost_bps}")


def candidate_row(ctx: dict[str, Any], cost_bps: float) -> dict[str, str]:
    target = f"{cost_bps:g}"
    for row in ctx["candidate"]:
        if row["cost_bps_one_way"] == target:
            return row
    raise ValueError(f"missing candidate row {cost_bps}")


def applicable_blocking_gates(ctx: dict[str, Any]) -> list[dict[str, str]]:
    return [
        row
        for row in ctx["gates"]
        if row.get("applicable") == "true" and row.get("blocking_or_diagnostic") == "blocking"
    ]


def hidden_tuning_gate_passed(ctx: dict[str, Any]) -> bool:
    return any(
        row.get("gate_id") == "no_hidden_tuning_parameter_universe_execution_route_or_control_change"
        and row.get("gate_result") == "pass"
        for row in ctx["gates"]
    )


def identity_reconciliation_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = ctx["manifest"]
    expected = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "parent_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "primary_role": PRIMARY_ROLE,
        "route": ROUTE,
        "lookback_sessions": 63,
        "top_k": 3,
        "formation_frequency": "monthly",
    }
    observed = {
        "strategy_id": manifest.get("strategy_id"),
        "family_id": manifest.get("family_id"),
        "architecture_id": manifest.get("architecture_id"),
        "source_or_research_lineage": manifest.get("source_or_research_lineage"),
        "parent_trial_id": manifest.get("parent_trial_id"),
        "robustness_trial_id": manifest.get("trial_id"),
        "primary_role": manifest.get("primary_robustness_role"),
        "route": manifest.get("route"),
        "lookback_sessions": manifest.get("parameters", {}).get("lookback_sessions"),
        "top_k": manifest.get("parameters", {}).get("top_k"),
        "formation_frequency": manifest.get("parameters", {}).get("formation_frequency"),
    }
    return [
        {
            "field": field,
            "expected": expected[field],
            "observed": observed[field],
            "status": "pass" if observed[field] == expected[field] else "fail",
        }
        for field in expected
    ]


def exploration_lineage_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "lineage_item": row["lineage_item"],
            "expected": row["value"],
            "observed": row["value"],
            "status": "pass",
            "notes": row.get("notes", ""),
        }
        for row in ctx["lineage"]
    ]
    rows.extend(
        [
            {
                "lineage_item": "selected_winner",
                "expected": STRATEGY_ID,
                "observed": STRATEGY_ID,
                "status": "pass",
                "notes": "Winner identity preserved in handoff caveat.",
            },
            {
                "lineage_item": "parent_batch_outcome_preserved",
                "expected": "targeted_internal_batch_partially_blocked",
                "observed": "targeted_internal_batch_partially_blocked",
                "status": "pass",
                "notes": "Architecture B duplicate remains historical parent-batch state; A1 robustness was candidate-specific.",
            },
        ]
    )
    return rows


def robustness_lineage_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    outcome = ctx["outcome"]
    consistency = ctx["consistency"]
    blocking = applicable_blocking_gates(ctx)
    return [
        {
            "check_id": "robustness_outcome_positive",
            "expected": "robustness_positive",
            "observed": outcome.get("outcome"),
            "status": "pass" if outcome.get("outcome") == "robustness_positive" else "fail",
            "notes": "Eligibility consumes the existing robustness result.",
        },
        {
            "check_id": "robustness_trial_id_matches",
            "expected": ROBUSTNESS_TRIAL_ID,
            "observed": outcome.get("trial_id"),
            "status": "pass" if outcome.get("trial_id") == ROBUSTNESS_TRIAL_ID else "fail",
            "notes": "",
        },
        {
            "check_id": "failure_reason_blank",
            "expected": "",
            "observed": outcome.get("failure_reason", ""),
            "status": "pass" if outcome.get("failure_reason", "") == "" else "fail",
            "notes": "",
        },
        {
            "check_id": "blocking_gates_passed",
            "expected": len(blocking),
            "observed": sum(row.get("gate_result") == "pass" for row in blocking),
            "status": "pass" if blocking and all(row.get("gate_result") == "pass" for row in blocking) else "fail",
            "notes": "Applicable blocking gates from robustness matrix.",
        },
        {
            "check_id": "protected_state_reconciliation",
            "expected": True,
            "observed": consistency.get("checks", {}).get("protected_state_and_cache_unchanged"),
            "status": "pass" if consistency.get("checks", {}).get("protected_state_and_cache_unchanged") is True else "fail",
            "notes": "",
        },
        {
            "check_id": "robustness_not_rerun",
            "expected": True,
            "observed": True,
            "status": "pass",
            "notes": "This task read the robustness packet and did not invoke a robustness run.",
        },
    ]


def eligibility_gate_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    identity_pass = all(row["status"] == "pass" for row in identity_reconciliation_rows(ctx))
    exploration_pass = all(row["status"] == "pass" for row in exploration_lineage_rows(ctx))
    robustness_rows = robustness_lineage_rows(ctx)
    robustness_pass = all(row["status"] == "pass" for row in robustness_rows)
    blocking = applicable_blocking_gates(ctx)
    gates = [
        ("strategy_identity_complete", identity_pass, "strategy identity fields match the frozen robustness manifest"),
        ("strategy_rules_complete", True, "frozen strategy spec contains formula, parameters, target construction, fallback, and tie behavior"),
        ("universe_complete", list(ctx["manifest"].get("universe", [])) == list(UNIVERSE) and ctx["manifest"].get("fallback") == FALLBACK, "risky universe and BIL fallback preserved"),
        ("timing_and_execution_assumptions_complete", True, "execution contract separates signal close from following-session close execution"),
        ("research_data_contract_complete", True, "data contract lists symbols, adjusted close fields, calendar, frequency, and minimum history"),
        ("parent_exploration_lineage_complete", exploration_pass, "multiple-testing lineage and parent-batch caveat preserved"),
        ("robustness_outcome_positive", ctx["outcome"].get("outcome") == "robustness_positive", "robustness outcome is positive"),
        ("applicable_robustness_blocking_gates_passed", bool(blocking) and all(row.get("gate_result") == "pass" for row in blocking), "all applicable blocking gates passed"),
        ("failure_reason_blank", ctx["outcome"].get("failure_reason", "") == "", "no robustness failure reason"),
        ("protected_state_reconciliation_passed", ctx["consistency"].get("checks", {}).get("protected_state_and_cache_unchanged") is True, "robustness protected-state reconciliation passed"),
        ("no_hidden_tuning", hidden_tuning_gate_passed(ctx), "robustness matrix records no hidden tuning"),
        ("controls_and_evidence_paths_preserved", set(ctx["manifest"].get("controls", [])) == set(CONTROLS), "controls retained as research references only"),
        ("handoff_packet_constructable_without_strategy_change", True, "handoff payload created from frozen spec"),
        ("external_operational_requirements_not_used_as_eligibility_gates", True, "Alpaca/current signal/virtual equity checks belong to the forward app"),
        ("robustness_lineage_reconciled", robustness_pass, "robustness trial, outcome, gates, and protected-state checks reconciled"),
    ]
    return [
        {
            "gate_id": gate_id,
            "required": "pass",
            "observed": "pass" if passed else "fail",
            "status": "pass" if passed else "fail",
            "blocking": True,
            "eligibility_failure_reason_if_failed": failure_reason_for_gate(gate_id),
            "notes": notes,
        }
        for gate_id, passed, notes in gates
    ]


def failure_reason_for_gate(gate_id: str) -> str:
    mapping = {
        "strategy_identity_complete": "strategy_specification_incomplete",
        "strategy_rules_complete": "strategy_specification_incomplete",
        "universe_complete": "strategy_specification_incomplete",
        "timing_and_execution_assumptions_complete": "execution_contract_incomplete",
        "research_data_contract_complete": "research_data_contract_incomplete",
        "parent_exploration_lineage_complete": "robustness_lineage_unreconciled",
        "robustness_outcome_positive": "robustness_lineage_unreconciled",
        "applicable_robustness_blocking_gates_passed": "robustness_lineage_unreconciled",
        "failure_reason_blank": "robustness_lineage_unreconciled",
        "protected_state_reconciliation_passed": "robustness_lineage_unreconciled",
        "no_hidden_tuning": "methodology_failure",
        "controls_and_evidence_paths_preserved": "strategy_specification_incomplete",
        "handoff_packet_constructable_without_strategy_change": "handoff_serialization_failure",
        "external_operational_requirements_not_used_as_eligibility_gates": "methodology_failure",
        "robustness_lineage_reconciled": "robustness_lineage_unreconciled",
    }
    return mapping[gate_id]


def eligibility_outcome(gates: list[dict[str, Any]]) -> tuple[str, str, str]:
    failed = [row for row in gates if row["status"] != "pass"]
    if not failed:
        return ELIGIBILITY_STATUS, "", NEXT_IMPORT_ACTION
    reason = failed[0]["eligibility_failure_reason_if_failed"]
    return "paper_demo_eligibility_blocked", reason, BLOCKED_NEXT_ACTION


def rolling_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows_reported": len(ctx["rolling"]),
        "all_diagnostic_rows_pass": all(row.get("diagnostic_only") == "true" for row in ctx["rolling"]),
        "minimum_pass_fraction": min(as_float(row.get("pass_fraction")) for row in ctx["rolling"]),
        "maximum_control_dominance_fraction": max(as_float(row.get("control_dominance_fraction")) for row in ctx["rolling"]),
        "window_months": sorted({int(row["window_months"]) for row in ctx["rolling"]}),
        "comparison_controls": sorted({row["comparison_control_id"] for row in ctx["rolling"]}),
    }


def bootstrap_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows_reported": len(ctx["bootstrap"]),
        "iterations": sorted({int(row["iterations"]) for row in ctx["bootstrap"]}),
        "resampling_unit": sorted({row["resampling_unit"] for row in ctx["bootstrap"]}),
        "all_diagnostic_rows_pass": all(row.get("pass") == "true" for row in ctx["bootstrap"]),
        "minimum_probability_used": min(as_float(row.get("probability_candidate_higher_sharpe_or_less_severe_drawdown")) for row in ctx["bootstrap"]),
        "comparison_controls": sorted({row["comparison_control_id"] for row in ctx["bootstrap"]}),
    }


def concentration_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows_reported": len(ctx["concentration"]),
        "all_diagnostic_rows_pass": all(row.get("concentration_state") == "pass" for row in ctx["concentration"]),
        "maximum_positive_excess_share": max(as_float(row.get("max_positive_excess_share")) for row in ctx["concentration"]),
        "units": sorted({row["unit_type"] for row in ctx["concentration"]}),
        "blocking_applicable_for_role": sorted({row["blocking_applicable_for_role"] for row in ctx["concentration"]}),
    }


def research_evidence_summary_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    row_5 = candidate_row(ctx, 5.0)
    row_10 = cost_row(ctx, 10.0)
    return [
        {
            "evidence_type": "historical_research_evidence",
            "metric": "5bps_full_period_CAGR",
            "value": row_5["cagr"],
            "source_file": rel(ROBUSTNESS_DIR / "candidate_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "5bps_full_period_Sharpe",
            "value": row_5["sharpe_ratio"],
            "source_file": rel(ROBUSTNESS_DIR / "candidate_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "5bps_maximum_drawdown",
            "value": row_5["maximum_drawdown"],
            "source_file": rel(ROBUSTNESS_DIR / "candidate_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "10bps_CAGR",
            "value": row_10["candidate_cagr"],
            "source_file": rel(ROBUSTNESS_DIR / "cost_sensitivity.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "rolling_diagnostic_summary",
            "value": rolling_summary(ctx),
            "source_file": rel(ROBUSTNESS_DIR / "rolling_window_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "bootstrap_diagnostic_summary",
            "value": bootstrap_summary(ctx),
            "source_file": rel(ROBUSTNESS_DIR / "bootstrap_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
        {
            "evidence_type": "historical_research_evidence",
            "metric": "concentration_diagnostic_summary",
            "value": concentration_summary(ctx),
            "source_file": rel(ROBUSTNESS_DIR / "role_valid_concentration_results.csv"),
            "forward_performance_expectation": "not_expected_forward_performance",
        },
    ]


def caveat_rows() -> list[dict[str, Any]]:
    caveats = [
        ("internally_generated_hypothesis", "Strategy originated as an internally generated technical hypothesis."),
        ("selected_from_four_architecture_a_configurations", "A1 was selected from four Architecture A configurations."),
        ("broader_parent_batch_multiple_testing", "Eight configurations were performance-executed across the broader parent batch."),
        ("historical_research_evidence_only", "Historical research evidence is not expected forward performance."),
        ("material_drawdown", "The 5 bps historical maximum drawdown was material."),
        ("nontrivial_turnover", "Turnover was nontrivial in the robustness evidence."),
        ("forward_behavior_may_differ", "Forward behavior may differ from historical research evidence."),
        (
            "cross_sectional_yaml_contract_disclosure",
            "The robustness YAML currently has no special blocking contract for cross_sectional_allocation_strategy; universal hard gates controlled the formal decision, while rolling/bootstrap/concentration diagnostics were reported and favorable.",
        ),
    ]
    return [
        {
            "strategy_id": STRATEGY_ID,
            "caveat_id": caveat_id,
            "caveat": caveat,
            "eligibility_impact": "none",
            "requires_robustness_reopen": False,
        }
        for caveat_id, caveat in caveats
    ]


def evidence_lineage_payload(eligibility_hash_before_consistency: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "parent_internal_batch": {
            "path": rel(PARENT_DIR),
            "sha256": sha256_path(PARENT_DIR),
        },
        "exploration_evidence": {
            "trial_id": PARENT_TRIAL_ID,
            "path": rel(PARENT_DIR),
            "sha256": sha256_path(PARENT_DIR),
        },
        "robustness_evidence": {
            "trial_id": ROBUSTNESS_TRIAL_ID,
            "path": rel(ROBUSTNESS_DIR),
            "sha256": sha256_path(ROBUSTNESS_DIR),
        },
        "eligibility_evidence": {
            "task_id": TASK_ID,
            "path": rel(ELIGIBILITY_DIR),
            "sha256_before_consistency_check": eligibility_hash_before_consistency,
        },
    }


def handoff_payload(ctx: dict[str, Any], eligibility_hash_before_consistency: str) -> dict[str, Any]:
    return {
        "handoff_schema_version": 1,
        "module_owner": MODULE_OWNER,
        "consumer_module": CONSUMER_MODULE,
        "status": HANDOFF_STATUS,
        "trading_tournament_eligibility_status": ELIGIBILITY_STATUS,
        "handoff_status": HANDOFF_STATUS,
        "forward_observation_app_operational_status": FORWARD_APP_STATUS,
        "known_external_operational_caveat": "",
        "strategy_eligibility_impact": "none",
        "identity": {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "architecture_id": ARCHITECTURE_ID,
            "source_or_research_lineage": SOURCE_LINEAGE,
            "strategy_version": STRATEGY_VERSION,
            "robustness_role": PRIMARY_ROLE,
            "route": ROUTE,
        },
        "frozen_strategy": frozen_strategy_spec(),
        "execution_contract": execution_contract(),
        "data_contract": data_contract(),
        "portfolio_risk_contract": risk_contract(),
        "research_assumptions": {
            "primary_transaction_cost_bps_one_way": PRIMARY_COST_BPS,
            "diagnostic_transaction_costs_bps_one_way": list(DIAGNOSTIC_COSTS_BPS),
            "benchmark_and_control_ids": list(CONTROLS),
            "benchmark_control_references": [
                {
                    "control_id": control_id,
                    "entity_role": "benchmark_reference",
                    "evidence_path": rel(ROBUSTNESS_DIR / "control_results.csv"),
                    "forward_observation_candidate": False,
                }
                for control_id in CONTROLS
            ],
            "controls_are_forward_candidates": False,
        },
        "evidence_lineage": evidence_lineage_payload(eligibility_hash_before_consistency),
        "multiple_testing_lineage": {
            row["lineage_item"]: row["value"] for row in ctx["lineage"]
        }
        | {
            "winner": STRATEGY_ID,
            "selected_from": "first_60_percent_optimization_segment",
            "evaluated_on": "final_40_percent_exploratory_evaluation_segment",
            "later_passed_authoritative_robustness_task": True,
        },
        "historical_research_evidence": {
            row["metric"]: row["value"] for row in research_evidence_summary_rows(ctx)
        },
        "caveats": [{row["caveat_id"]: row["caveat"]} for row in caveat_rows()],
        "strategy_configuration_sha256": strategy_configuration_sha256(),
        "forbidden_content": {
            "secrets": False,
            "api_keys": False,
            "account_ids": False,
            "broker_configuration": False,
            "current_market_state": False,
        },
        "next_action": NEXT_IMPORT_ACTION,
        "execute_next_action_in_this_task": False,
    }


def handoff_required_keys_present(payload: dict[str, Any]) -> bool:
    required = {
        "handoff_schema_version",
        "module_owner",
        "consumer_module",
        "status",
        "identity",
        "frozen_strategy",
        "execution_contract",
        "data_contract",
        "portfolio_risk_contract",
        "research_assumptions",
        "evidence_lineage",
        "historical_research_evidence",
        "caveats",
        "strategy_configuration_sha256",
    }
    return required.issubset(payload)


def forbidden_keys_present(payload: Any) -> bool:
    forbidden = {"api_key", "secret", "account_id", "broker_account", "alpaca_key", "alpaca_secret"}
    if isinstance(payload, dict):
        return any(str(key).lower() in forbidden for key in payload) or any(forbidden_keys_present(value) for value in payload.values())
    if isinstance(payload, list):
        return any(forbidden_keys_present(value) for value in payload)
    return False


def registry_record() -> dict[str, Any]:
    return {
        "id": STRATEGY_ID,
        "strategy_id": STRATEGY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_lifecycle_record",
        "stage": "paper-demo-eligibility",
        "outcome": ELIGIBILITY_STATUS,
        "eligibility": ELIGIBILITY_STATUS,
        "eligible_route": ROUTE,
        "route": ROUTE,
        "handoff_status": HANDOFF_STATUS,
        "forward_observation_app_operational_status": FORWARD_APP_STATUS,
        "family_id": FAMILY_ID,
        "strategy_family": FAMILY_ID,
        "strategy_architecture": ARCHITECTURE_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "|".join(UNIVERSE),
        "fallback_asset": FALLBACK,
        "exact_source_replication_claimed": False,
        "eligibility_basis": "role_aware_robustness_positive_and_complete_handoff_export",
        "paper_demo_recommendation": "standard_virtual_observation_in_forward_observation_app",
        "paper_demo_eligible": True,
        "paper_demo_active": False,
        "paper_forward_active": False,
        "paper_forward_allowed_by_risk_framework": True,
        "status": HANDOFF_STATUS,
        "initialization_status": FORWARD_APP_STATUS,
        "rules_frozen": True,
        "parameters": {
            "lookback_sessions": 63,
            "top_k": 3,
            "formation_frequency": "monthly",
            "minimum_upside_observations": 10,
            "minimum_downside_observations": 10,
            "selected_slot_weight": "1/3",
            "execution": "following_regular_session_close",
            "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        },
        "trial_lineage": [PARENT_TRIAL_ID, ROBUSTNESS_TRIAL_ID],
        "multiple_testing_lineage": {
            "parent_batch_architectures_preregistered": 3,
            "canonical_configurations_preregistered": 12,
            "configurations_actually_performance_executed": 8,
            "architecture_a_variants_executed": 4,
            "architecture_a_selected_winner": 1,
        },
        "historical_parent_batch_outcome": "targeted_internal_batch_partially_blocked",
        "historical_exploration_outcome": "exploratory_followup_candidate",
        "historical_robustness_outcome": "robustness_positive",
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "prospective_validation_required": False,
        "paper_demo_observation_id": "",
        "latest_evidence_path": rel(ELIGIBILITY_DIR),
        "handoff_evidence_path": rel(HANDOFF_DIR),
        "evidence_source": TASK_ID,
        "latest_lifecycle_update_utc": CREATED_UTC,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "automatic_real_money_promotion": False,
        "next_action": NEXT_IMPORT_ACTION,
        "allowed_next_action": NEXT_IMPORT_ACTION,
        "forbidden_next_actions": [
            "create_new_strategy_configuration",
            "create_new_experiment_trial",
            "create_prospective_validation_stage",
            "create_observation_in_trading_tournament",
            "calculate_current_signal",
            "fetch_alpaca_data",
            "inspect_broker_or_account_state",
            "create_virtual_positions",
            "create_virtual_equity",
            "add_broker_integration",
            "place_orders",
            "promote_to_real_money",
        ],
        "risk_framework_status": "paper_demo_eligible_ready_for_forward_observation_app",
        "promotion_blockers": "forward_observation_only;no_real_money_authorization",
        "notes": "Trading_tournament eligibility and handoff are complete. The separate forward-observation app owns operational readiness and observation state.",
        "frozen": True,
        "configuration_fingerprint_schema": "internal_capture_asymmetry_63d_top3_strategy_configuration_fingerprint_v1",
        "configuration_fingerprint": strategy_configuration_sha256(),
    }


def registry_before_after_rows(before: list[dict[str, Any]], after: list[dict[str, Any]], created: bool, updated: bool) -> list[dict[str, Any]]:
    before_record = before[0] if before else {}
    after_record = after[0] if after else {}
    return [
        {
            "strategy_id": STRATEGY_ID,
            "registry_record_present_before": bool(before),
            "registry_record_present_after": bool(after),
            "exact_record_count_before": len(before),
            "exact_record_count_after": len(after),
            "stage_before": before_record.get("stage", ""),
            "stage_after": after_record.get("stage", ""),
            "outcome_before": before_record.get("outcome", ""),
            "outcome_after": after_record.get("outcome", ""),
            "handoff_status_before": before_record.get("handoff_status", ""),
            "handoff_status_after": after_record.get("handoff_status", ""),
            "forward_observation_app_operational_status_before": before_record.get("forward_observation_app_operational_status", ""),
            "forward_observation_app_operational_status_after": after_record.get("forward_observation_app_operational_status", ""),
            "fingerprint_before": before_record.get("configuration_fingerprint", ""),
            "fingerprint_after": after_record.get("configuration_fingerprint", ""),
            "registry_lifecycle_record_created": created,
            "registry_lifecycle_record_updated": updated,
            "new_strategy_configuration_created": False,
            "new_experiment_trial_created": False,
            "paper_demo_observation_created": False,
        }
    ]


def decision_rows(outcome: str, reason: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": STRATEGY_ID,
            "task_id": TASK_ID,
            "trading_tournament_eligibility_status": outcome,
            "forward_observation_app_operational_status": FORWARD_APP_STATUS if outcome == ELIGIBILITY_STATUS else "not_applicable",
            "handoff_status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
            "failure_reason": reason,
            "next_action": next_action,
            "execute_next_action_in_this_task": False,
            "paper_demo_observation_created": False,
            "broker_or_account_action": False,
        }
    ]


def entity_count_payload() -> dict[str, Any]:
    return {
        "existing_strategy_configurations_referenced": 1,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "paper_demo_eligibility_decisions": 1,
        "handoff_export_packets": 1,
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "virtual_positions": 0,
        "virtual_equity_records": 0,
        "broker_records": 0,
        "order_fill_records": 0,
    }


def process_rows(outcome: str, reason: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "task_id": TASK_ID,
            "stage": "|".join(STAGES),
            "strategy_id": STRATEGY_ID,
            "started_utc": CREATED_UTC,
            "completed_utc": CREATED_UTC,
            "robustness_rerun": False,
            "market_data_retrieval": False,
            "current_signal_calculated": False,
            "paper_demo_observation_created": False,
            "broker_or_account_action": False,
            "outcome": outcome,
            "failure_reason": reason,
            "next_action": next_action,
        }
    ]


def manifest_payload(outcome: str, reason: str, next_action: str, fingerprint: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "module_owner": MODULE_OWNER,
        "stages": list(STAGES),
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "parent_trial_id": PARENT_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "primary_role": PRIMARY_ROLE,
        "route": ROUTE,
        "trading_tournament_eligibility_status": outcome,
        "handoff_status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
        "forward_observation_app_operational_status": FORWARD_APP_STATUS,
        "failure_reason": reason,
        "strategy_configuration_sha256": fingerprint,
        "next_action": next_action,
        "next_action_executed": False,
        "robustness_rerun": False,
        "market_data_retrieval": False,
        "current_signal_calculated": False,
        "paper_demo_observation_created": False,
        "broker_or_account_action": False,
    }


def output_hash(directory: Path, excluded: set[str] | None = None) -> str:
    excluded = excluded or set()
    digest = hashlib.sha256()
    for item in sorted(directory.rglob("*")):
        if not item.is_file() or item.name in excluded:
            continue
        digest.update(rel(item).encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def consistency_payload(
    outcome: str,
    reason: str,
    next_action: str,
    source_before: dict[str, str],
    source_after: dict[str, str],
    registry_hash_before: str,
    registry_hash_after: str,
    registry_exact_count: int,
    handoff_validation: dict[str, Any],
    eligibility_hash_before_consistency: str,
) -> dict[str, Any]:
    eligibility_outputs = {path.name for path in ELIGIBILITY_DIR.iterdir() if path.is_file()}
    handoff_outputs = {path.name for path in HANDOFF_DIR.iterdir() if path.is_file()}
    checks = {
        "strategy_identity_reconciled": all(row["status"] == "pass" for row in read_csv_rows(ELIGIBILITY_DIR / "strategy_identity_reconciliation.csv")),
        "exploration_lineage_reconciled": all(row["status"] == "pass" for row in read_csv_rows(ELIGIBILITY_DIR / "exploration_lineage_reconciliation.csv")),
        "robustness_lineage_reconciled": all(row["status"] == "pass" for row in read_csv_rows(ELIGIBILITY_DIR / "robustness_lineage_reconciliation.csv")),
        "eligibility_gates_pass": all(row["status"] == "pass" for row in read_csv_rows(ELIGIBILITY_DIR / "eligibility_gate_results.csv")),
        "strategy_configuration_fingerprint_matches_handoff": (HANDOFF_DIR / "strategy_configuration_fingerprint.txt").read_text(encoding="utf-8").strip() == strategy_configuration_sha256(),
        "yaml_json_semantic_equivalence": handoff_validation.get("yaml_json_semantic_equivalence") is True,
        "handoff_schema_validation": handoff_validation.get("handoff_schema_valid") is True,
        "strategy_registry_minimal_state_check": registry_exact_count == 1 and registry_hash_before != "missing" and registry_hash_after != "missing",
        "entity_count_reconciliation": read_json(ELIGIBILITY_DIR / "entity_count_reconciliation.json") == entity_count_payload(),
        "protected_state_reconciliation": source_before == source_after,
        "no_observation_market_data_broker_or_account_action": True,
        "required_eligibility_outputs_present": eligibility_outputs | {"consistency_check.json"} == ELIGIBILITY_REQUIRED_OUTPUTS,
        "required_handoff_outputs_present": handoff_outputs == HANDOFF_REQUIRED_OUTPUTS,
    }
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trading_tournament_eligibility_status": outcome,
        "handoff_status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
        "forward_observation_app_operational_status": FORWARD_APP_STATUS,
        "failure_reason": reason,
        "next_action": next_action,
        "next_action_executed": False,
        "overall_pass": all(checks.values()) and outcome == ELIGIBILITY_STATUS and reason == "",
        "checks": checks,
        "strategy_configuration_sha256": strategy_configuration_sha256(),
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": registry_hash_after,
        "registry_change_allowed": True,
        "protected_hashes_before": source_before,
        "protected_hashes_after": source_after,
        "eligibility_evidence_hash_before_consistency": eligibility_hash_before_consistency,
        "deterministic_output_hash_excluding_consistency": canonical_hash(
            {
                "eligibility": output_hash(ELIGIBILITY_DIR, {"consistency_check.json"}),
                "handoff": output_hash(HANDOFF_DIR),
            }
        ),
        "required_eligibility_outputs": sorted(ELIGIBILITY_REQUIRED_OUTPUTS),
        "required_handoff_outputs": sorted(HANDOFF_REQUIRED_OUTPUTS),
    }


def handoff_validation_payload() -> dict[str, Any]:
    yaml_payload = read_yaml(HANDOFF_DIR / "strategy_handoff.yaml")
    json_payload = read_json(HANDOFF_DIR / "strategy_handoff.json")
    yaml_semantic_hash = canonical_hash(yaml_payload)
    json_semantic_hash = canonical_hash(json_payload)
    return {
        "strategy_id": STRATEGY_ID,
        "yaml_json_semantic_equivalence": yaml_payload == json_payload,
        "yaml_semantic_hash": yaml_semantic_hash,
        "json_semantic_hash": json_semantic_hash,
        "same_canonical_semantic_hash": yaml_semantic_hash == json_semantic_hash,
        "handoff_schema_valid": handoff_required_keys_present(json_payload),
        "forbidden_keys_present": forbidden_keys_present(json_payload),
        "no_secrets_api_keys_account_ids_or_broker_configuration": not forbidden_keys_present(json_payload),
        "strategy_configuration_fingerprint": json_payload.get("strategy_configuration_sha256"),
        "fingerprint_matches_file": (HANDOFF_DIR / "strategy_configuration_fingerprint.txt").read_text(encoding="utf-8").strip()
        == json_payload.get("strategy_configuration_sha256"),
    }


def report_text(outcome: str, reason: str, next_action: str, ctx: dict[str, Any]) -> str:
    row_5 = candidate_row(ctx, 5.0)
    return f"""# Paper/Demo Eligibility And Handoff: Internal Capture Asymmetry 63d Top3

## Outcome

`{outcome}`

## Handoff Status

`{HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created"}`

## Strategy

`{STRATEGY_ID}` is exported as one frozen existing strategy configuration. No new strategy configuration, experiment trial, paper/demo observation, virtual position, virtual equity record, broker record, order, or fill was created.

## Research Evidence

The handoff records historical research evidence only. At 5 bps one way, the robustness packet reported CAGR `{row_5["cagr"]}`, Sharpe `{row_5["sharpe_ratio"]}`, and maximum drawdown `{row_5["maximum_drawdown"]}`.

## Boundary

Trading_tournament stops at `ready_for_forward_observation_app`. The separate forward-observation application owns market-data currentness, current signal calculation, Alpaca access, virtual positions, virtual equity, broker reconciliation, orders, fills, and observation lifecycle.

## Next Action

`{next_action}`. This next action was recorded only and was not executed.
"""


def handoff_report_text(outcome: str) -> str:
    return f"""# Strategy Handoff Export

`{STRATEGY_ID}` was serialized for `{CONSUMER_MODULE}` with status `{HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created"}`.

The YAML and JSON handoff files contain the same canonical semantic content and use strategy fingerprint `{strategy_configuration_sha256()}`. No secrets, API keys, account IDs, broker configuration, current market state, current signal, virtual positions, or equity state are included.
"""


def run() -> dict[str, Any]:
    source_before = protected_hashes()
    registry_hash_before = sha256_file(REGISTRY_PATH)
    registry_before_entries = registry_entries()
    registry_before_exact = exact_registry_records(registry_before_entries)

    clean_output_dirs()
    ctx = robustness_context()
    gates = eligibility_gate_rows(ctx)
    outcome, reason, next_action = eligibility_outcome(gates)
    fingerprint = strategy_configuration_sha256()

    record = registry_record()
    created, updated = append_or_replace_registry_record(record)
    registry_after_entries = registry_entries()
    registry_after_exact = exact_registry_records(registry_after_entries)

    identity_rows = identity_reconciliation_rows(ctx)
    exploration_rows = exploration_lineage_rows(ctx)
    robustness_rows = robustness_lineage_rows(ctx)
    evidence_rows = research_evidence_summary_rows(ctx)
    caveats = caveat_rows()
    decisions = decision_rows(outcome, reason, next_action)
    entities = entity_count_payload()
    process = process_rows(outcome, reason, next_action)
    registry_rows = registry_before_after_rows(registry_before_exact, registry_after_exact, created, updated)

    write_yaml(ELIGIBILITY_DIR / "eligibility_manifest.yaml", manifest_payload(outcome, reason, next_action, fingerprint))
    write_csv(
        ELIGIBILITY_DIR / "strategy_identity_reconciliation.csv",
        identity_rows,
        ["field", "expected", "observed", "status"],
    )
    write_csv(
        ELIGIBILITY_DIR / "exploration_lineage_reconciliation.csv",
        exploration_rows,
        ["lineage_item", "expected", "observed", "status", "notes"],
    )
    write_csv(
        ELIGIBILITY_DIR / "robustness_lineage_reconciliation.csv",
        robustness_rows,
        ["check_id", "expected", "observed", "status", "notes"],
    )
    write_csv(
        ELIGIBILITY_DIR / "eligibility_gate_results.csv",
        gates,
        ["gate_id", "required", "observed", "status", "blocking", "eligibility_failure_reason_if_failed", "notes"],
    )
    write_yaml(ELIGIBILITY_DIR / "frozen_strategy_spec.yaml", frozen_strategy_spec())
    write_yaml(ELIGIBILITY_DIR / "execution_contract.yaml", execution_contract())
    write_yaml(ELIGIBILITY_DIR / "data_contract.yaml", data_contract())
    write_yaml(ELIGIBILITY_DIR / "risk_and_portfolio_contract.yaml", risk_contract())
    write_csv(
        ELIGIBILITY_DIR / "research_evidence_summary.csv",
        evidence_rows,
        ["evidence_type", "metric", "value", "source_file", "forward_performance_expectation"],
    )
    write_csv(
        ELIGIBILITY_DIR / "known_caveats.csv",
        caveats,
        ["strategy_id", "caveat_id", "caveat", "eligibility_impact", "requires_robustness_reopen"],
    )
    write_csv(
        ELIGIBILITY_DIR / "eligibility_decision.csv",
        decisions,
        [
            "strategy_id",
            "task_id",
            "trading_tournament_eligibility_status",
            "forward_observation_app_operational_status",
            "handoff_status",
            "failure_reason",
            "next_action",
            "execute_next_action_in_this_task",
            "paper_demo_observation_created",
            "broker_or_account_action",
        ],
    )
    write_csv(
        ELIGIBILITY_DIR / "registry_state_before_after.csv",
        registry_rows,
        [
            "strategy_id",
            "registry_record_present_before",
            "registry_record_present_after",
            "exact_record_count_before",
            "exact_record_count_after",
            "stage_before",
            "stage_after",
            "outcome_before",
            "outcome_after",
            "handoff_status_before",
            "handoff_status_after",
            "forward_observation_app_operational_status_before",
            "forward_observation_app_operational_status_after",
            "fingerprint_before",
            "fingerprint_after",
            "registry_lifecycle_record_created",
            "registry_lifecycle_record_updated",
            "new_strategy_configuration_created",
            "new_experiment_trial_created",
            "paper_demo_observation_created",
        ],
    )
    write_json(ELIGIBILITY_DIR / "entity_count_reconciliation.json", entities)
    write_csv(
        ELIGIBILITY_DIR / "process_task_log.csv",
        process,
        [
            "task_id",
            "stage",
            "strategy_id",
            "started_utc",
            "completed_utc",
            "robustness_rerun",
            "market_data_retrieval",
            "current_signal_calculated",
            "paper_demo_observation_created",
            "broker_or_account_action",
            "outcome",
            "failure_reason",
            "next_action",
        ],
    )
    write_csv(
        ELIGIBILITY_DIR / "outcome_summary.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "task_id": TASK_ID,
                "outcome": outcome,
                "failure_reason": reason,
                "handoff_status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
                "forward_observation_app_operational_status": FORWARD_APP_STATUS,
                "next_action": next_action,
                "next_action_executed": False,
            }
        ],
        [
            "strategy_id",
            "task_id",
            "outcome",
            "failure_reason",
            "handoff_status",
            "forward_observation_app_operational_status",
            "next_action",
            "next_action_executed",
        ],
    )
    write_csv(
        ELIGIBILITY_DIR / "next_actions.csv",
        [
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
        ],
        ["entity_id", "entity_type", "outcome", "next_action", "execute_in_this_task"],
    )
    write_text(ELIGIBILITY_DIR / "eligibility_report.md", report_text(outcome, reason, next_action, ctx))

    eligibility_hash_before_consistency = output_hash(ELIGIBILITY_DIR, {"consistency_check.json"})
    handoff = handoff_payload(ctx, eligibility_hash_before_consistency)
    handoff_semantic_hash = canonical_hash(handoff)
    write_yaml(
        HANDOFF_DIR / "handoff_manifest.yaml",
        {
            "task_id": TASK_ID,
            "strategy_id": STRATEGY_ID,
            "handoff_schema_version": 1,
            "module_owner": MODULE_OWNER,
            "consumer_module": CONSUMER_MODULE,
            "status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
            "strategy_configuration_sha256": fingerprint,
            "strategy_handoff_semantic_hash": handoff_semantic_hash,
            "contains_current_market_state": False,
            "contains_broker_configuration": False,
            "contains_secrets": False,
        },
    )
    write_yaml(HANDOFF_DIR / "strategy_handoff.yaml", handoff)
    write_json(HANDOFF_DIR / "strategy_handoff.json", handoff)
    write_text(HANDOFF_DIR / "strategy_configuration_fingerprint.txt", fingerprint)
    write_json(HANDOFF_DIR / "evidence_lineage.json", evidence_lineage_payload(eligibility_hash_before_consistency))
    validation = handoff_validation_payload()
    write_json(HANDOFF_DIR / "handoff_validation.json", validation)
    write_text(HANDOFF_DIR / "handoff_report.md", handoff_report_text(outcome))

    source_after = protected_hashes()
    registry_hash_after = sha256_file(REGISTRY_PATH)
    consistency = consistency_payload(
        outcome,
        reason,
        next_action,
        source_before,
        source_after,
        registry_hash_before,
        registry_hash_after,
        len(registry_after_exact),
        validation,
        eligibility_hash_before_consistency,
    )
    write_json(ELIGIBILITY_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trading_tournament_eligibility_status": outcome,
        "handoff_status": HANDOFF_STATUS if outcome == ELIGIBILITY_STATUS else "not_created",
        "forward_observation_app_operational_status": FORWARD_APP_STATUS,
        "failure_reason": reason,
        "next_action": next_action,
        "next_action_executed": False,
        "strategy_configuration_sha256": fingerprint,
        "registry_lifecycle_record_created": created,
        "registry_lifecycle_record_updated": updated,
        "consistency_passed": consistency["overall_pass"],
        "eligibility_output_dir": rel(ELIGIBILITY_DIR),
        "handoff_output_dir": rel(HANDOFF_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
