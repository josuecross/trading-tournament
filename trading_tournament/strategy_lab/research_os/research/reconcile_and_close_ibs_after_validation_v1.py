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


TASK_ID = "reconcile_and_close_ibs_after_validation_v1"
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

VALIDATION_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / "pagonidis_ibs_next_open_incremental_validation_v1"
    / "latest"
)
EXPLORATION_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "pagonidis_ibs_next_open_portability_exploration_v1"
    / "latest"
)

STRATEGY_ID = "pagonidis_ibs_spy_next_open_intraday_v1"
FAMILY_ID = "internal_bar_strength_mean_reversion"
DISPLAY_NAME = "SPY IBS Next-Open Intraday Portability"
ARCHITECTURE = (
    "completed_close_range_position_signal_next_open_intraday_allocation"
)
SOURCE_LINEAGE = (
    "strategy_source_library_refresh_v5:"
    "pagonidis_ibs_equity_etf_reversal:execution_portability_test"
)
UNIVERSE_TEXT = "SPY|BIL"
EXPLORATION_TRIAL_ID = "pagonidis_ibs_next_open_portability_v1__canonical"
VALIDATION_TRIAL_ID = (
    "pagonidis_ibs_next_open_incremental_validation_v1__child"
)
ADAPTATION_LABEL = "validation_variant"
CHANGED_FIELDS_FROM_PARENT = (
    "validation_period_cost_and_stability_diagnostics_only"
)
FAILURE_REASON = "cost_drag"
DECISION_REASON = (
    "break_even_one_way_cost_below_10bps_and_negative_return_at_10bps"
)
SECONDARY_DIAGNOSTIC = "second_half_and_rolling_period_instability"
STRATEGY_NEXT_ACTION = (
    "do_not_retest_exact_ibs_next_open_portability_configuration"
)
PROJECT_NEXT_ACTION_SUCCESS = (
    "direction_owner_review_long_short_relative_value_capability_v1"
)
PROJECT_NEXT_ACTION_BLOCKED = (
    "direction_owner_review_ibs_registry_reconciliation_block_v1"
)
PROCESS_OUTCOME_SUCCESS = "lifecycle_reconciliation_completed"
PROCESS_OUTCOME_BLOCKED = "lifecycle_reconciliation_blocked"
FAMILY_INTERPRETATION = (
    "exact_execution_portability_configuration_closed_cost_and_stability_failure"
)
REGISTRATION_REASON = "retrospective_status_reconciliation"
FINGERPRINT_SCHEMA = "ibs_next_open_exact_config_fingerprint_v1"

FROZEN_PARAMETERS = {
    "ibs_formula": (
        "(adjusted_close-adjusted_low)/(adjusted_high-adjusted_low)"
    ),
    "ibs_threshold": 0.20,
    "comparison": "strict_less_than",
    "zero_range_behavior": "inactive",
    "signal_timestamp": "completed_close_t",
    "entry_timestamp": "regular_session_open_t_plus_1",
    "exit_timestamp": "regular_session_close_t_plus_1",
    "overnight_asset": "BIL",
    "inactive_session_asset": "BIL",
    "SPY_overnight_return_included": False,
    "holding_period": "one_regular_session",
    "source_execution_translated": True,
    "exact_source_replication_claimed": False,
    "short_leg": "none",
    "additional_filter": "none",
    "stop_rule": "none",
    "primary_cost_bps_per_one_way_turnover": 5.0,
}
BENCHMARKS = (
    "prior_day_negative_return_spy_intraday_v1",
    "all_sessions_spy_open_to_close_v1",
    "exposure_matched_fractional_spy_intraday_v1",
    "SPY_buy_and_hold",
)

SOURCE_OF_TRUTH_PATHS = (
    STRATEGY_REGISTRY,
    ROADMAP,
    RESEARCH_QUEUE,
    FAMILY_LEDGER,
    ACTIVE_OBSERVATIONS,
)
CACHE_FILES = tuple(
    sorted(path for path in CACHE_DIR.rglob("*") if path.is_file())
)
PROTECTED_PATHS = SOURCE_OF_TRUTH_PATHS + CACHE_FILES

VALIDATION_INPUT_NAMES = (
    "validation_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "full_period_results.csv",
    "chronological_half_results.csv",
    "rolling_window_summary.csv",
    "cost_sensitivity_results.csv",
    "break_even_cost_results.csv",
    "consistency_check.json",
)
EXPLORATION_INPUT_NAMES = (
    "strategy_cards.csv",
    "trial_ledger.csv",
)
INPUT_EVIDENCE_FILES = tuple(
    [VALIDATION_DIR / name for name in VALIDATION_INPUT_NAMES]
    + [EXPLORATION_DIR / name for name in EXPLORATION_INPUT_NAMES]
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
    "backtest_or_strategy_rerun": False,
    "threshold_or_execution_tuning": False,
    "validation_or_robustness_run": False,
    "source_research": False,
    "data_acquisition": False,
    "promotion_or_paper_demo_action": False,
    "broker_account_order_or_real_money_action": False,
    "strategy_discovery": False,
    "broad_registry_cleanup": False,
    "family_wide_IBS_closure": False,
}


def rel(path: str | Path) -> str:
    item = Path(path)
    if not item.is_absolute():
        return item.as_posix()
    try:
        return item.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(item.resolve())


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
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            width=120,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def tree_identity_hash(root: Path, excluded: Path | None = None) -> str:
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if excluded_resolved is not None and (
            resolved == excluded_resolved or excluded_resolved in resolved.parents
        ):
            continue
        stat = path.stat()
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "lifecycle" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
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
        pieces = [str(piece).strip().upper() for piece in value if str(piece).strip()]
    else:
        pieces = []
    return "|".join(pieces)


def normalize_parameters(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(value, dict):
        parsed = value
    else:
        parsed = {}
    return {
        "ibs_formula": str(parsed.get("ibs_formula", "")).replace(" ", ""),
        "ibs_threshold": (
            float(parsed["ibs_threshold"])
            if parsed.get("ibs_threshold") is not None
            else None
        ),
        "comparison": parsed.get("comparison", ""),
        "zero_range_behavior": parsed.get("zero_range_behavior", ""),
        "signal_timestamp": parsed.get("signal_timestamp", ""),
        "entry_timestamp": parsed.get("entry_timestamp", ""),
        "exit_timestamp": parsed.get("exit_timestamp", ""),
        "overnight_asset": parsed.get("overnight_asset", ""),
        "inactive_session_asset": parsed.get("inactive_session_asset", ""),
        "SPY_overnight_return_included": parsed.get(
            "SPY_overnight_return_included"
        ),
        "holding_period": parsed.get("holding_period", ""),
        "source_execution_translated": parsed.get("source_execution_translated"),
        "exact_source_replication_claimed": parsed.get(
            "exact_source_replication_claimed"
        ),
        "short_leg": parsed.get("short_leg", ""),
        "additional_filter": parsed.get("additional_filter", ""),
        "stop_rule": parsed.get("stop_rule", ""),
    }


def configuration_fingerprint_payload() -> dict[str, Any]:
    return {
        "family_id": FAMILY_ID,
        "instrument_universe": UNIVERSE_TEXT,
        "ibs_formula": FROZEN_PARAMETERS["ibs_formula"],
        "ibs_threshold": FROZEN_PARAMETERS["ibs_threshold"],
        "comparison": FROZEN_PARAMETERS["comparison"],
        "zero_range_behavior": FROZEN_PARAMETERS["zero_range_behavior"],
        "signal_timestamp": FROZEN_PARAMETERS["signal_timestamp"],
        "entry_timestamp": FROZEN_PARAMETERS["entry_timestamp"],
        "exit_timestamp": FROZEN_PARAMETERS["exit_timestamp"],
        "overnight_asset": FROZEN_PARAMETERS["overnight_asset"],
        "inactive_session_asset": FROZEN_PARAMETERS["inactive_session_asset"],
        "SPY_overnight_return_included": FROZEN_PARAMETERS[
            "SPY_overnight_return_included"
        ],
        "holding_period": FROZEN_PARAMETERS["holding_period"],
        "source_execution_translated": FROZEN_PARAMETERS[
            "source_execution_translated"
        ],
        "exact_source_replication_claimed": FROZEN_PARAMETERS[
            "exact_source_replication_claimed"
        ],
        "short_leg": FROZEN_PARAMETERS["short_leg"],
        "additional_filter": FROZEN_PARAMETERS["additional_filter"],
        "stop_rule": FROZEN_PARAMETERS["stop_rule"],
    }


def configuration_fingerprint(
    payload: dict[str, Any] | None = None,
) -> str:
    source = configuration_fingerprint_payload() if payload is None else payload
    text = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_fingerprint_payload(record: dict[str, Any]) -> dict[str, Any]:
    params = normalize_parameters(record.get("parameters", {}))
    return {
        "family_id": record.get("family_id")
        or record.get("family")
        or record.get("strategy_family")
        or "",
        "instrument_universe": normalize_universe(
            record.get("instrument_universe")
            or record.get("universe")
            or record.get("instruments")
        ),
        **params,
    }


def alias_score(record: dict[str, Any]) -> tuple[int, list[str]]:
    target = configuration_fingerprint_payload()
    candidate = record_fingerprint_payload(record)
    matched = [
        field
        for field, expected in target.items()
        if candidate.get(field) not in ("", None)
        and candidate.get(field) == expected
    ]
    return len(matched), matched


def load_registry() -> dict[str, Any]:
    return read_yaml(STRATEGY_REGISTRY)


def inspect_registry(
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    target_field_count = len(configuration_fingerprint_payload())
    for record in registry.get("strategies", []):
        if not isinstance(record, dict):
            continue
        record_id = record.get("strategy_id") or record.get("id") or ""
        if record_id == STRATEGY_ID:
            exact.append(
                {
                    "record_id": record_id,
                    "match_type": "exact_strategy_id",
                    "matched_field_count": target_field_count,
                    "matched_fields": list(configuration_fingerprint_payload()),
                    "record": record,
                }
            )
            continue
        score, matched = alias_score(record)
        fingerprint_match = (
            record.get("configuration_fingerprint")
            == configuration_fingerprint()
        )
        family_and_universe = {
            "family_id",
            "instrument_universe",
        }.issubset(matched)
        plausible = bool(
            fingerprint_match
            or (
                family_and_universe
                and score >= max(8, target_field_count - 4)
            )
        )
        if plausible:
            aliases.append(
                {
                    "record_id": record_id,
                    "match_type": "exact_configuration_alias"
                    if fingerprint_match or score == target_field_count
                    else "plausible_equivalent_alias",
                    "matched_field_count": score,
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
        "parameters": FROZEN_PARAMETERS,
        "benchmark_or_control": list(BENCHMARKS),
        "stage": "closed",
        "lane": "archive",
        "instrument_family": "ETF",
        "version": "v1",
        "parent_id": EXPLORATION_TRIAL_ID,
        "credibility_tier": "blocked",
        "status": "rejected",
        "current_status": "closed",
        "outcome": "validation_failed",
        "trial_id": VALIDATION_TRIAL_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": EXPLORATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "failure_reason": FAILURE_REASON,
        "primary_failure_reason": FAILURE_REASON,
        "decision_reason": DECISION_REASON,
        "secondary_diagnostic": SECONDARY_DIAGNOSTIC,
        "next_action": STRATEGY_NEXT_ACTION,
        "allowed_next_action": "no_action",
        "allowed_next_actions": ["no_action"],
        "paper_demo_eligible": False,
        "paper_demo_active": False,
        "paper_forward_active": False,
        "paper_forward_allowed_by_risk_framework": False,
        "benchmark_reference_only": False,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "no_real_money_recommendation": True,
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "family_level_interpretation": FAMILY_INTERPRETATION,
        "registration_reason": REGISTRATION_REASON,
        "closure_scope": (
            "exact_SPY_BIL_IBS_strict_lt_0_20_completed_close_signal_"
            "next_open_entry_same_session_close_exit_BIL_overnight_"
            "5bps_primary_no_filter_no_short_no_stop_configuration_only"
        ),
        "data_source": "existing_canonical_adjusted_SPY_BIL_cache",
        "implementation_status": "archived",
        "evidence_source": (
            "pagonidis_ibs_next_open_incremental_validation_v1"
        ),
        "latest_evidence_path": rel(VALIDATION_DIR),
        "latest_known_result_summary": (
            "Validation failed: break-even one-way cost was approximately "
            "6.4056 bps, full-period return was negative at 10 bps, and "
            "second-half and rolling diagnostics were unstable."
        ),
        "role": "closed_exact_configuration",
        "rules_frozen": True,
        "risk_framework_status": "not_paper_demo_eligible",
        "risk_budget_status": "closed_cost_and_stability_failure",
        "promotion_decision": "do_not_promote",
        "promotion_review_required": False,
        "promotion_reason": (
            "Closed exact IBS next-open portability configuration after "
            "validation failed for cost drag."
        ),
        "promotion_blockers": (
            "validation_failed;cost_drag;period_instability;"
            "not_paper_demo_eligible;no_real_money_authorization"
        ),
        "promotion_requirements": (
            "A materially distinct execution configuration and explicit "
            "direction-owner evidence would be required for future review."
        ),
        "demotion_or_kill_criteria": (
            "Exact tested configuration is already closed after validation failure."
        ),
        "notes": (
            "Retrospective reconciliation for the exact SPY/BIL IBS<0.20 "
            "next-open to same-close portability configuration only. This "
            "does not close all IBS, mean-reversion, threshold, or source "
            "close-to-close configurations."
        ),
        "instrument_lane": "ETF",
        "evidence_tier": "blocked",
        "primary_failure_mode": FAILURE_REASON,
        "duplication_risk": "exact_configuration_closed",
        "evidence_needed": "none_for_exact_closed_configuration",
        "duplicate_of": "",
        "blocked_reason": FAILURE_REASON,
        "forbidden_next_actions": [
            "retest_exact_configuration",
            "change_IBS_threshold",
            "change_entry_or_exit_timing",
            "add_filter_stop_or_short",
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
        "benchmark_or_control",
        "stage",
        "outcome",
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "failure_reason",
        "decision_reason",
        "secondary_diagnostic",
        "next_action",
        "family_level_interpretation",
        "registration_reason",
        "closure_scope",
        "configuration_fingerprint",
    )
    if any(record.get(field) in ("", None, "unknown", "unmapped") for field in required):
        return False
    if record.get("stage") != "closed":
        return False
    if record.get("outcome") != "validation_failed":
        return False
    if record.get("failure_reason") != FAILURE_REASON:
        return False
    if record.get("paper_demo_eligible") is not False:
        return False
    if record.get("paper_demo_active") is not False:
        return False
    if record.get("real_money_authorized") is not False:
        return False
    return record_fingerprint_payload(record) == configuration_fingerprint_payload()


def target_record_yaml() -> str:
    return yaml.safe_dump(
        [target_registry_record()],
        sort_keys=False,
        width=120,
        allow_unicode=False,
    )


def find_record_span(text: str, strategy_id: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    starts = [
        index for index, line in enumerate(lines) if line.startswith("- id: ")
    ]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "".join(lines[start:end])
        if (
            f"- id: {strategy_id}\n" in block
            or f"  strategy_id: {strategy_id}\n" in block
        ):
            return start, end
    return None


def atomic_write_registry_text(text: str) -> None:
    temporary = STRATEGY_REGISTRY.with_suffix(".yaml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, STRATEGY_REGISTRY)


def append_or_replace_target_record() -> None:
    text = STRATEGY_REGISTRY.read_text(encoding="utf-8")
    replacement = target_record_yaml()
    lines = text.splitlines(keepends=True)
    span = find_record_span(text, STRATEGY_ID)
    if span is None:
        new_text = text.rstrip() + "\n" + replacement
    else:
        start, end = span
        lines[start:end] = replacement.splitlines(keepends=True)
        new_text = "".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    atomic_write_registry_text(new_text)


def load_authoritative_inputs() -> dict[str, Any]:
    return {
        "validation_manifest": read_yaml(
            VALIDATION_DIR / "validation_manifest.yaml"
        ),
        "validation_strategy": read_csv_rows(
            VALIDATION_DIR / "strategy_cards.csv"
        ),
        "validation_trial": read_csv_rows(
            VALIDATION_DIR / "trial_ledger.csv"
        ),
        "validation_outcome": read_csv_rows(
            VALIDATION_DIR / "outcome_summary.csv"
        ),
        "validation_failures": read_csv_rows(
            VALIDATION_DIR / "failure_reasons.csv"
        ),
        "validation_next_actions": read_csv_rows(
            VALIDATION_DIR / "next_actions.csv"
        ),
        "full_period": read_csv_rows(
            VALIDATION_DIR / "full_period_results.csv"
        ),
        "halves": read_csv_rows(
            VALIDATION_DIR / "chronological_half_results.csv"
        ),
        "rolling": read_csv_rows(
            VALIDATION_DIR / "rolling_window_summary.csv"
        ),
        "costs": read_csv_rows(
            VALIDATION_DIR / "cost_sensitivity_results.csv"
        ),
        "break_even": read_csv_rows(
            VALIDATION_DIR / "break_even_cost_results.csv"
        ),
        "validation_consistency": read_json(
            VALIDATION_DIR / "consistency_check.json"
        ),
        "exploration_strategy": read_csv_rows(
            EXPLORATION_DIR / "strategy_cards.csv"
        ),
        "exploration_trial": read_csv_rows(
            EXPLORATION_DIR / "trial_ledger.csv"
        ),
    }


def evidence_gate(inputs: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    manifest = inputs["validation_manifest"]
    consistency = inputs["validation_consistency"]
    if manifest.get("strategy_id") != STRATEGY_ID:
        blockers.append("validation_manifest_strategy_id_mismatch")
    if manifest.get("outcome") != "validation_failed":
        blockers.append("validation_manifest_outcome_mismatch")
    if manifest.get("failure_reason") != FAILURE_REASON:
        blockers.append("validation_manifest_failure_reason_mismatch")
    if consistency.get("consistency_passed") is not True:
        blockers.append("validation_consistency_not_passed")
    if consistency.get("reproduction_pass") is not True:
        blockers.append("validation_reproduction_not_passed")
    if consistency.get("all_invariants_pass") is not True:
        blockers.append("validation_invariants_not_passed")
    validation_trials = inputs["validation_trial"]
    if len(validation_trials) != 1:
        blockers.append("validation_trial_count_not_one")
    elif (
        validation_trials[0].get("trial_id") != VALIDATION_TRIAL_ID
        or validation_trials[0].get("parent_trial_id") != EXPLORATION_TRIAL_ID
        or validation_trials[0].get("outcome") != "validation_failed"
        or validation_trials[0].get("failure_reason") != FAILURE_REASON
    ):
        blockers.append("validation_trial_lineage_or_outcome_mismatch")
    exploration_trials = inputs["exploration_trial"]
    if len(exploration_trials) != 1:
        blockers.append("exploration_trial_count_not_one")
    elif (
        exploration_trials[0].get("trial_id") != EXPLORATION_TRIAL_ID
        or exploration_trials[0].get("outcome")
        != "exploratory_followup_candidate_standalone"
    ):
        blockers.append("exploration_trial_identity_or_outcome_mismatch")

    def find_row(
        name: str,
        predicate: Any,
        blocker: str,
    ) -> dict[str, str]:
        matches = [row for row in inputs[name] if predicate(row)]
        if len(matches) != 1:
            blockers.append(blocker)
            return {}
        return matches[0]

    full_five = find_row(
        "full_period",
        lambda row: row.get("row_id") == STRATEGY_ID
        and float(row.get("cost_assumption_bps", -1)) == 5.0,
        "full_period_5bps_candidate_row_missing",
    )
    second_half = find_row(
        "halves",
        lambda row: row.get("row_id") == STRATEGY_ID
        and row.get("period_label") == "second_chronological_half"
        and float(row.get("cost_assumption_bps", -1)) == 5.0,
        "second_half_5bps_candidate_row_missing",
    )
    cost_ten = find_row(
        "costs",
        lambda row: row.get("row_id") == STRATEGY_ID
        and float(row.get("cost_assumption_bps", -1)) == 10.0,
        "full_period_10bps_candidate_row_missing",
    )
    break_even = find_row(
        "break_even",
        lambda row: row.get("period_label") == "full_period",
        "full_period_break_even_row_missing",
    )
    rolling_36 = find_row(
        "rolling",
        lambda row: int(row.get("window_months", -1)) == 36,
        "rolling_36_summary_missing",
    )
    rolling_60 = find_row(
        "rolling",
        lambda row: int(row.get("window_months", -1)) == 60,
        "rolling_60_summary_missing",
    )
    numeric_checks = (
        (
            full_five,
            "total_return",
            0.279412588299,
            "full_period_5bps_total_return_mismatch",
        ),
        (
            second_half,
            "total_return",
            -0.0865952600428,
            "second_half_5bps_total_return_mismatch",
        ),
        (
            second_half,
            "sharpe_ratio",
            -0.100867140275,
            "second_half_5bps_sharpe_mismatch",
        ),
        (
            cost_ten,
            "total_return",
            -0.467544766888,
            "full_period_10bps_total_return_mismatch",
        ),
        (
            break_even,
            "break_even_one_way_cost_bps",
            6.40559668519,
            "full_period_break_even_cost_mismatch",
        ),
        (
            rolling_36,
            "positive_candidate_total_return_fraction",
            0.445595854922,
            "rolling_36_positive_return_fraction_mismatch",
        ),
        (
            rolling_60,
            "median_candidate_sharpe_ratio",
            -0.054179401101,
            "rolling_60_median_sharpe_mismatch",
        ),
        (
            rolling_60,
            "positive_candidate_total_return_fraction",
            0.405882352941,
            "rolling_60_positive_return_fraction_mismatch",
        ),
    )
    for row, field, expected, blocker in numeric_checks:
        if not row:
            continue
        try:
            actual = float(row[field])
        except (KeyError, TypeError, ValueError):
            blockers.append(blocker)
            continue
        if abs(actual - expected) > 1e-9:
            blockers.append(blocker)
    return not blockers, blockers


def apply_reconciliation(
    registry: dict[str, Any],
    exact: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    evidence_ok: bool,
) -> tuple[str, str, int, int, list[str]]:
    if not evidence_ok:
        return PROCESS_OUTCOME_BLOCKED, "methodology_failure", 0, 0, []
    if len(exact) > 1 or aliases:
        return (
            PROCESS_OUTCOME_BLOCKED,
            "status_reconciliation_required",
            0,
            0,
            [],
        )
    created = 1 if not exact else 0
    updated = 0 if created else 1
    append_or_replace_target_record()
    return (
        PROCESS_OUTCOME_SUCCESS,
        "",
        created,
        updated,
        [rel(STRATEGY_REGISTRY)],
    )


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
                "record_id": alias["record_id"],
                "match_type": alias["match_type"],
                "matched_field_count": alias["matched_field_count"],
                "matched_fields": alias["matched_fields"],
                "duplicate_check_result": "status_reconciliation_required",
                "authoritative_change_allowed": False,
            }
            for alias in aliases
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
                "duplicate_check_result": "exact_record_exists",
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
    fingerprint = configuration_fingerprint()
    return [
        {
            "fingerprint_schema": FINGERPRINT_SCHEMA,
            "field": field,
            "value": value,
            "fingerprint": fingerprint,
            "deterministic": True,
        }
        for field, value in configuration_fingerprint_payload().items()
    ]


def strategy_card_row(process_outcome: str) -> dict[str, Any]:
    record = target_registry_record()
    return {
        "strategy_id": record["strategy_id"],
        "family_id": record["family_id"],
        "display_name": record["display_name"],
        "entity_type": record["entity_type"],
        "strategy_architecture": record["strategy_architecture"],
        "source_or_research_lineage": record["source_or_research_lineage"],
        "instrument_universe": record["instrument_universe"],
        "parameters": record["parameters"],
        "benchmark_or_control": record["benchmark_or_control"],
        "route": "standalone",
        "stage": record["stage"],
        "outcome": record["outcome"],
        "trial_id": record["trial_id"],
        "parent_trial_id": record["parent_trial_id"],
        "adaptation_label": record["adaptation_label"],
        "failure_reason": record["failure_reason"],
        "decision_reason": record["decision_reason"],
        "secondary_diagnostic": record["secondary_diagnostic"],
        "next_action": record["next_action"],
        "paper_demo_eligible": record["paper_demo_eligible"],
        "paper_demo_active": record["paper_demo_active"],
        "real_money_authorized": record["real_money_authorized"],
        "family_level_interpretation": record[
            "family_level_interpretation"
        ],
        "registration_reason": record["registration_reason"],
        "configuration_fingerprint": record["configuration_fingerprint"],
        "process_outcome": process_outcome,
    }


def trial_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    exploration = inputs["exploration_trial"][0]
    validation = inputs["validation_trial"][0]
    return [
        {
            "entity_type": "experiment_trial",
            "trial_id": EXPLORATION_TRIAL_ID,
            "parent_trial_id": "",
            "stage": "exploration",
            "outcome": "exploratory_followup_candidate_standalone",
            "adaptation_label": "exploratory_variant",
            "changed_fields_from_parent": "",
            "execution_portability_explicit": True,
            "failure_reason": "",
            "source_evidence_next_action": exploration.get("next_action", ""),
            "next_action": exploration.get("next_action", ""),
            "read_only": True,
            "source_evidence_path": rel(EXPLORATION_DIR),
            "new_experiment_trial_created": False,
            "counted_as_new_trial": False,
        },
        {
            "entity_type": "experiment_trial",
            "trial_id": VALIDATION_TRIAL_ID,
            "parent_trial_id": EXPLORATION_TRIAL_ID,
            "stage": "validation",
            "outcome": "validation_failed",
            "adaptation_label": ADAPTATION_LABEL,
            "changed_fields_from_parent": CHANGED_FIELDS_FROM_PARENT,
            "execution_portability_explicit": True,
            "failure_reason": FAILURE_REASON,
            "source_evidence_next_action": validation.get("next_action", ""),
            "next_action": STRATEGY_NEXT_ACTION,
            "read_only": True,
            "source_evidence_path": rel(VALIDATION_DIR),
            "new_experiment_trial_created": False,
            "counted_as_new_trial": False,
        },
    ]


def benchmark_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    source = read_csv_rows(VALIDATION_DIR / "benchmark_reference_log.csv")
    by_id = {row["benchmark_id"]: row for row in source}
    return [
        {
            "benchmark_or_control_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "source_stage": by_id.get(benchmark, {}).get(
                "stage",
                "benchmark_reference_only",
            ),
            "source_evidence_path": rel(VALIDATION_DIR),
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
                "next_action": record.get("next_action", ""),
                "configuration_fingerprint": record.get(
                    "configuration_fingerprint",
                    "",
                ),
                "record_json": record,
            }
        )
    return rows


def state_change_rows(
    before: dict[str, str],
    after: dict[str, str],
    permitted_paths: list[str],
) -> list[dict[str, Any]]:
    permitted = set(permitted_paths)
    return [
        {
            "path": path,
            "hash_before": before.get(path, "missing"),
            "hash_after": after.get(path, "missing"),
            "changed": before.get(path) != after.get(path),
            "change_permitted": path in permitted,
            "change_scope": (
                "exact_IBS_strategy_registry_record"
                if path == rel(STRATEGY_REGISTRY)
                else "protected_unchanged"
            ),
        }
        for path in sorted(set(before) | set(after))
    ]


def report_text(
    process_outcome: str,
    process_failure_reason: str,
    created: int,
    updated: int,
    exact_after_count: int,
    aliases_after: list[dict[str, Any]],
    project_next_action: str,
) -> str:
    return f"""# Reconcile And Close IBS After Validation V1

## Scope

This correction records the failed validation of exactly
`{STRATEGY_ID}`. No backtest, validation, tuning, source research, data
acquisition, paper/demo, promotion, broker, account, order, or real-money
action occurred.

## Duplicate And Alias Check

- Exact configuration records after reconciliation: `{exact_after_count}`
- Unresolved plausible aliases after reconciliation: `{len(aliases_after)}`
- Configuration fingerprint: `{configuration_fingerprint()}`

## Authoritative State

- Stage: `closed`
- Outcome: `validation_failed`
- Primary failure reason: `cost_drag`
- Decision reason:
  `{DECISION_REASON}`
- Secondary evidence: `{SECONDARY_DIAGNOSTIC}`
- Strategy next action: `{STRATEGY_NEXT_ACTION}`

Closure applies only to the exact SPY/BIL, strict IBS below 0.20,
completed-close signal, next-open entry, same-session-close exit, BIL
overnight, 5 bps primary-cost configuration. It does not close all IBS or
mean-reversion research.

## Reconciliation

- Process outcome: `{process_outcome}`
- Process failure reason: `{process_failure_reason or 'none'}`
- Authoritative records created: `{created}`
- Authoritative records updated: `{updated}`
- Existing trials carried forward: `2`
- New experiment trials: `0`
- Benchmark references: `4`
- Observations changed: `0`

## Exact Project Next Action

`{project_next_action}`

The next action was recorded and not executed.
"""


def run() -> dict[str, Any]:
    source_before = hash_paths(PROTECTED_PATHS)
    inputs_before = hash_paths(INPUT_EVIDENCE_FILES)
    prior_before = tree_identity_hash(ROOT / "evidence", excluded=OUTPUT_DIR)
    clean_output()

    inputs = load_authoritative_inputs()
    evidence_ok, evidence_blockers = evidence_gate(inputs)
    registry_before = load_registry()
    exact_before, aliases_before = inspect_registry(registry_before)
    before_records = [
        row
        for row in registry_before.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
    ]
    (
        process_outcome,
        process_failure_reason,
        created,
        updated,
        permitted_paths,
    ) = apply_reconciliation(
        registry_before,
        exact_before,
        aliases_before,
        evidence_ok,
    )
    registry_after = load_registry()
    exact_after, aliases_after = inspect_registry(registry_after)
    after_records = [
        row
        for row in registry_after.get("strategies", [])
        if isinstance(row, dict)
        and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
    ]
    exact_after_count = len(exact_after)
    final_record = after_records[0] if len(after_records) == 1 else {}
    project_next_action = (
        PROJECT_NEXT_ACTION_SUCCESS
        if process_outcome == PROCESS_OUTCOME_SUCCESS
        else PROJECT_NEXT_ACTION_BLOCKED
    )
    if evidence_blockers:
        process_decision_reason = "|".join(evidence_blockers)
    elif aliases_before:
        process_decision_reason = "targeted_equivalent_alias_conflict"
    else:
        process_decision_reason = (
            "closed_record_reconciled_from_exploration_and_validation_evidence"
        )

    source_after = hash_paths(PROTECTED_PATHS)
    inputs_after = hash_paths(INPUT_EVIDENCE_FILES)
    prior_after = tree_identity_hash(ROOT / "evidence", excluded=OUTPUT_DIR)
    changed_paths = sorted(
        path
        for path in set(source_before) | set(source_after)
        if source_before.get(path) != source_after.get(path)
    )
    all_changes_permitted = set(changed_paths).issubset(set(permitted_paths))

    duplicate_check = duplicate_rows(
        exact_before,
        aliases_before,
        len(registry_before.get("strategies", [])),
    )
    fingerprint = fingerprint_rows()
    strategy_cards = [strategy_card_row(process_outcome)]
    trials = trial_rows(inputs)
    benchmarks = benchmark_rows(inputs)
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
    before_after = registry_state_rows(before_records, after_records)
    state_changes = state_change_rows(
        source_before,
        source_after,
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
            "total_exact_configuration_records_after_reconciliation": (
                exact_after_count
            ),
            "existing_experiment_trials_carried_forward": 2,
            "new_experiment_trials": 0,
            "benchmark_references": len(benchmarks),
            "process_tasks": 1,
            "observations_changed": 0,
            "new_research_candidates_created": 0,
            "strategy_stage": "closed",
            "strategy_outcome": "validation_failed",
            "strategy_failure_reason": FAILURE_REASON,
            "strategy_decision_reason": DECISION_REASON,
            "strategy_secondary_evidence": SECONDARY_DIAGNOSTIC,
            "strategy_next_action": STRATEGY_NEXT_ACTION,
            "project_next_action": project_next_action,
        }
    ]
    if process_outcome == PROCESS_OUTCOME_SUCCESS:
        failures = [
            {
                "entity_type": "strategy_configuration",
                "entity_id": STRATEGY_ID,
                "stage": "closed",
                "outcome": "validation_failed",
                "failure_reason": FAILURE_REASON,
                "decision_reason": DECISION_REASON,
                "secondary_evidence": SECONDARY_DIAGNOSTIC,
            }
        ]
    else:
        failures = [
            {
                "entity_type": "process_task",
                "entity_id": TASK_ID,
                "stage": STAGE,
                "outcome": process_outcome,
                "failure_reason": process_failure_reason,
                "decision_reason": process_decision_reason,
                "secondary_evidence": "",
            }
        ]
    next_actions = [
        {
            "scope": "strategy",
            "strategy_id": STRATEGY_ID,
            "exact_next_action": STRATEGY_NEXT_ACTION,
            "execute_now": False,
        },
        {
            "scope": "project",
            "strategy_id": "",
            "exact_next_action": project_next_action,
            "execute_now": False,
        },
    ]

    write_csv(
        OUTPUT_DIR / "duplicate_and_alias_check.csv",
        duplicate_check,
        [
            "registry_record_count_before",
            "searched_strategy_id",
            "record_id",
            "match_type",
            "matched_field_count",
            "matched_fields",
            "duplicate_check_result",
            "authoritative_change_allowed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "configuration_fingerprint.csv",
        fingerprint,
        [
            "fingerprint_schema",
            "field",
            "value",
            "fingerprint",
            "deterministic",
        ],
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_cards,
        list(strategy_cards[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trials,
        list(trials[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_tasks,
        list(process_tasks[0]),
    )
    write_csv(
        OUTPUT_DIR / "registry_record_before_after.csv",
        before_after,
        list(before_after[0]),
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_changes,
        list(state_changes[0]),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        list(failures[0]),
    )
    write_csv(
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
        and process_failure_reason == ""
        and evidence_ok
        and exact_after_count == 1
        and not aliases_after
        and record_complete
        and len(trials) == 2
        and len(benchmarks) == 4
        and inputs_before == inputs_after
        and prior_before == prior_after
        and all_changes_permitted
        and not any(FORBIDDEN_FLAGS.values())
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "evidence_gate_passed": evidence_ok,
        "evidence_gate_blockers": evidence_blockers,
        "exact_configuration_records_after_reconciliation": exact_after_count,
        "unresolved_equivalent_alias_count_after_reconciliation": len(
            aliases_after
        ),
        "authoritative_record_complete": record_complete,
        "configuration_fingerprint": configuration_fingerprint(),
        "strategy_stage": final_record.get("stage", ""),
        "strategy_outcome": final_record.get("outcome", ""),
        "strategy_failure_reason": final_record.get("failure_reason", ""),
        "strategy_decision_reason": final_record.get("decision_reason", ""),
        "strategy_secondary_diagnostic": final_record.get(
            "secondary_diagnostic",
            "",
        ),
        "strategy_next_action": final_record.get("next_action", ""),
        "closure_scope_is_exact_configuration_only": bool(
            final_record.get("family_level_interpretation")
            == FAMILY_INTERPRETATION
        ),
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "benchmark_reference_count": 4,
        "process_task_count": 1,
        "observations_changed": 0,
        "new_research_candidates_created": 0,
        "source_of_truth_hashes_before": source_before,
        "source_of_truth_hashes_after": source_after,
        "source_of_truth_changed_paths": changed_paths,
        "permitted_changed_paths": permitted_paths,
        "all_source_of_truth_changes_permitted": all_changes_permitted,
        "input_evidence_hashes_before": inputs_before,
        "input_evidence_hashes_after": inputs_after,
        "input_evidence_hashes_unchanged": inputs_before == inputs_after,
        "prior_evidence_reconciliation_method": (
            "deterministic_path_size_mtime_identity_manifest"
        ),
        "prior_evidence_identity_hash_before": prior_before,
        "prior_evidence_identity_hash_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        **FORBIDDEN_FLAGS,
        "exact_project_next_action": project_next_action,
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
        "total_exact_configuration_records_after_reconciliation": (
            exact_after_count
        ),
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "benchmark_references": 4,
        "process_tasks": 1,
        "observations_changed": 0,
        "new_research_candidates_created": 0,
        "source_of_truth_changed_paths": changed_paths,
        "exact_next_action": project_next_action,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "reconciliation_manifest.yaml", manifest)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "reconciliation_report.md",
        report_text(
            process_outcome,
            process_failure_reason,
            created,
            updated,
            exact_after_count,
            aliases_after,
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
        raise RuntimeError("Lifecycle reconciliation consistency check failed")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "process_outcome": process_outcome,
        "process_failure_reason": process_failure_reason,
        "authoritative_strategy_records_created": created,
        "authoritative_strategy_records_updated": updated,
        "total_exact_configuration_records_after_reconciliation": (
            exact_after_count
        ),
        "existing_experiment_trials_carried_forward": 2,
        "new_experiment_trials": 0,
        "observations_changed": 0,
        "new_research_candidates_created": 0,
        "consistency_passed": consistency_passed,
        "exact_next_action": project_next_action,
        "output_dir": rel(OUTPUT_DIR),
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
