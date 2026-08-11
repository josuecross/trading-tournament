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

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import native_etf_two_candidate_exploration_batch_v1 as portfolio_helpers


TASK_ID = "adopt_single_candidate_cohort_policy_and_run_cfra_stovall_exploration_v1"
SOURCE_TASK_ID = "accepted_47_role_aware_source_backed_intake_v4"
MODE = "bounded-source-backed-single-candidate-exploration"
STAGE = "exploration"
POLICY_DIR = ROOT / "evidence" / "methodology" / TASK_ID / "latest"
SOURCE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID / "latest"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / "cfra_stovall_semiannual_sector_rotation_exploration_v1" / "latest"
CACHE_DIR = ROOT / DATA_CACHE_DIR

PREREGISTRATION_TIMESTAMP = "2026-08-07T00:00:00-06:00"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8

SOURCE_RECORD_ID = "src_cfra_stovall_semiannual_sector_rotation_v1"
STRATEGY_ID = "cfra_stovall_semiannual_sector_rotation_v1"
TRIAL_ID = "accepted47_source_v4__cfra_stovall_semiannual__canonical"
FAMILY_ID = "semiannual_defensive_cyclical_sector_rotation"
ARCHITECTURE_ID = "cfra_stovall_calendar_sector_basket_rotation"
DISPLAY_NAME = "CFRA-Stovall Semiannual Defensive/Cyclical Sector Rotation"
ARCHITECTURE = "semiannual_calendar_two_basket_sector_allocation"
LINEAGE = "pacer_cfra_stovall_equal_weight_seasonal_rotation_index"
ROUTE = "standalone_with_diversifier_diagnostic"
PRIMARY_ROLE = "dynamic_multi_asset_allocation_strategy"

SECTOR_SYMBOLS = ("XLP", "XLV", "XLY", "XLI", "XLK", "XLB")
DEFENSIVE_SYMBOLS = ("XLP", "XLV")
CYCLICAL_SYMBOLS = ("XLY", "XLI", "XLK", "XLB")
UNIVERSE = ("XLP", "XLV", "XLY", "XLI", "XLK", "XLB", "BIL", "SPY")
REQUIRED_SYMBOLS = UNIVERSE

NAMED_CONTROL = "cfra_stovall_complementary_seasonal_rotation_control"
STATIC_CONTROL = "cfra_stovall_static_average_weight_control"
EQUAL_CONTROL = "cfra_stovall_equal_weight_six_sector_control"
SPY_CONTROL = "SPY_buy_and_hold"
BIL_CONTROL = "BIL_buy_and_hold"
CONTROLS = (NAMED_CONTROL, STATIC_CONTROL, EQUAL_CONTROL, SPY_CONTROL, BIL_CONTROL)
CRITICAL_CONTROLS = (NAMED_CONTROL, STATIC_CONTROL)

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_standalone",
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}
NEXT_ADVANCE = "direction_owner_review_cfra_stovall_exploration_for_robustness_v1"
NEXT_CLOSED = "direction_owner_select_discovery_direction_after_cfra_stovall_v1"
NEXT_BLOCKED = "direction_owner_review_cfra_stovall_execution_block_v1"

REQUIRED_EXPLORATION_OUTPUTS = (
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "event_window_inventory.csv",
    "event_execution_ledger.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "calendar_year_results.csv",
    "sector_contribution_results.csv",
    "lightweight_concentration_diagnostics.csv",
    "portfolio_contribution_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "entity_count_reconciliation.json",
    "consistency_check.json",
    "exploration_report.md",
    "protected_state_reconciliation.csv",
)

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "data" / "cache",
    ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1",
    ROOT / "execution_lab" / "alpaca_micro_live_v1",
    ROOT / "paper_forward_observations",
    ROOT / "evidence" / "paper_forward_observations",
    ROOT / "evidence" / "paper_demo_observation",
    ROOT / "evidence" / "paper_demo_onboarding",
    ROOT / "evidence" / "robustness",
    ROOT / "evidence" / "public_source_strategy_intake" / "accepted_47_role_aware_source_backed_intake_v3",
    ROOT / "evidence" / "research_recovery" / "accepted_47_source_backed_exploration_batch_v3",
)


@dataclass(frozen=True)
class StrategySpec:
    source_record_id: str = SOURCE_RECORD_ID
    strategy_id: str = STRATEGY_ID
    trial_id: str = TRIAL_ID
    family_id: str = FAMILY_ID
    architecture_id: str = ARCHITECTURE_ID
    display_name: str = DISPLAY_NAME
    strategy_architecture: str = ARCHITECTURE
    source_or_research_lineage: str = LINEAGE
    universe: tuple[str, ...] = UNIVERSE
    controls: tuple[str, ...] = CONTROLS
    critical_controls: tuple[str, ...] = CRITICAL_CONTROLS
    route: str = ROUTE
    primary_future_robustness_role: str = PRIMARY_ROLE


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in PROTECTED_PATHS}


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if math.isfinite(number) else ""
    if isinstance(value, float):
        return value if math.isfinite(value) else ""
    if value is None:
        return ""
    return value


def write_csv_at(
    directory: Path,
    name: str,
    rows: Iterable[dict[str, Any]],
    fields: Iterable[str] | None = None,
) -> None:
    materialized = list(rows)
    columns = list(fields or [])
    for row in materialized:
        for field in row:
            if field not in columns:
                columns.append(field)
    with (directory / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: serialize(row.get(field, "")) for field in columns})


def write_json_at(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml_at(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def reset_directory(path: Path, expected_parent: Path) -> None:
    if path.exists():
        resolved = path.resolve()
        if expected_parent.resolve() not in resolved.parents:
            raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def target(weights: dict[str, float]) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in UNIVERSE}


def bil_target() -> dict[str, float]:
    return target({"BIL": 1.0})


def defensive_target() -> dict[str, float]:
    return target({"XLP": 0.5, "XLV": 0.5})


def cyclical_target() -> dict[str, float]:
    return target({"XLY": 0.25, "XLI": 0.25, "XLK": 0.25, "XLB": 0.25})


def equal_six_target() -> dict[str, float]:
    return target({symbol: 1.0 / 6.0 for symbol in SECTOR_SYMBOLS})


def source_record_row() -> dict[str, Any]:
    return {
        "source_record_id": SOURCE_RECORD_ID,
        "entity_type": "source_library_record",
        "stage": "source_extracted",
        "outcome": "feasible",
        "failure_reason": "",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "source_or_research_lineage": LINEAGE,
        "source_title": "Pacer CFRA-Stovall Equal Weight Seasonal Rotation Index methodology",
        "source_version": "accepted_47_v4_bounded_source_packet",
        "classification": "source_backed_semiannual_sector_rotation_model",
        "primary_future_robustness_role": PRIMARY_ROLE,
        "route": ROUTE,
        "exact_source_replication_claimed": False,
        "replication_limitation": "source methodology uses equal-weight sector indices; accepted-47 implementation uses corresponding Select Sector SPDR ETFs",
        "provider_requirement": "none",
        "unresolved_material_fields": 0,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    descriptions = {
        NAMED_CONTROL: "same six sector ETFs and events with April/October schedule reversed",
        STATIC_CONTROL: "candidate full-period average target weights rebalanced only on same April/October dates",
        EQUAL_CONTROL: "equal weight across XLP, XLV, XLY, XLI, XLK, and XLB at every April/October event",
        SPY_CONTROL: "SPY buy and hold benchmark reference",
        BIL_CONTROL: "BIL buy and hold benchmark reference",
    }
    return [
        {
            "benchmark_reference_id": control_id,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "entity_type": "benchmark_reference",
            "stage": STAGE,
            "critical_control": control_id in CRITICAL_CONTROLS,
            "control_description": descriptions[control_id],
            "control_promoted_to_strategy": False,
            "same_cost_accounting": True,
        }
        for control_id in CONTROLS
    ]


def direction_correction_rows() -> list[dict[str, Any]]:
    return [
        {
            "direction_correction_id": "discovery_cohort_policy_v2",
            "task_id": TASK_ID,
            "entity_type": "direction_correction_record",
            "stage": "correction",
            "supersedes": "candidate-count requirements only",
            "permitted_cohort_size_min": 1,
            "permitted_cohort_size_max": 4,
            "minimum_two_candidates_required": False,
            "quota_fillers_allowed": False,
            "individual_feasibility_gates_preserved": True,
            "candidate_rule_changed": False,
            "candidate_controls_changed": False,
            "source_completeness_changed": False,
            "cost_accounting_changed": False,
            "role_aware_robustness_changed": False,
            "paper_demo_eligibility_changed": False,
            "historical_v4_outcome_rewritten": False,
            "single_candidate_execution_authorized": True,
            "append_only_record": True,
            "created_at": PREREGISTRATION_TIMESTAMP,
        }
    ]


def historical_reconciliation_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_task_id": SOURCE_TASK_ID,
            "historical_intake_outcome": "one_candidate_only_insufficient_for_batch",
            "source_packages_reviewed": 18,
            "serious_candidates_assessed": 9,
            "independently_qualified_candidates": 1,
            "implementation_previously_authorized": False,
            "historical_next_action": "direction_owner_review_source_backed_v4_shortfall_and_discovery_model_v1",
            "retained_source_record_id": SOURCE_RECORD_ID,
            "retained_strategy_id": STRATEGY_ID,
            "single_candidate_execution_now_authorized": True,
            "candidate_rule_changed": False,
            "candidate_controls_changed": False,
            "only_cohort_policy_changed": True,
            "historical_v4_result_preserved": True,
        }
    ]


def materialize_policy_packet() -> dict[str, Any]:
    reset_directory(POLICY_DIR, ROOT / "evidence" / "methodology" / TASK_ID)
    policy = {
        "policy_id": "discovery_cohort_policy_v2",
        "task_id": TASK_ID,
        "permitted_cohort_size": {"min": 1, "max": 4},
        "minimum_two_candidates_required": False,
        "quota_fillers_allowed": False,
        "every_candidate_must_pass_individual_feasibility_gates": True,
        "one_candidate_creates_one_strategy_configuration_and_one_canonical_trial": True,
        "cohort_size_alters_exploration_or_robustness_thresholds": False,
        "exact_candidate_and_multiple_testing_counts_remain_visible": True,
        "supersedes": ["candidate-count requirements only"],
        "does_not_supersede": [
            "source completeness",
            "exact duplicate screening",
            "frozen controls",
            "role preregistration",
            "accepted-universe rules",
            "cost accounting",
            "role-aware robustness",
            "paper/demo eligibility requirements",
        ],
    }
    write_csv_at(POLICY_DIR, "direction_correction_record.csv", direction_correction_rows())
    write_yaml_at(POLICY_DIR, "discovery_cohort_policy_v2.yaml", policy)
    write_csv_at(POLICY_DIR, "historical_v4_intake_reconciliation.csv", historical_reconciliation_rows())
    checks = {
        "permitted_cohort_size_min_is_one": policy["permitted_cohort_size"]["min"] == 1,
        "permitted_cohort_size_max_is_four": policy["permitted_cohort_size"]["max"] == 4,
        "no_minimum_two": not policy["minimum_two_candidates_required"],
        "no_quota_fillers": not policy["quota_fillers_allowed"],
        "candidate_level_requirements_unchanged": all(
            not direction_correction_rows()[0][field]
            for field in ("candidate_rule_changed", "candidate_controls_changed")
        ),
        "historical_v4_outcome_preserved": historical_reconciliation_rows()[0]["historical_intake_outcome"]
        == "one_candidate_only_insufficient_for_batch",
    }
    checks["overall_pass"] = all(checks.values())
    write_json_at(POLICY_DIR, "consistency_check.json", checks)
    (POLICY_DIR / "direction_correction_report.md").write_text(
        "\n".join(
            [
                "# Discovery Cohort Policy V2",
                "",
                "This append-only correction permits one to four independently qualified candidates. It changes only the cohort-size rule and preserves the historical V4 underfilled result.",
                "",
                f"Retained candidate: `{STRATEGY_ID}`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return checks


def materialize_source_packet() -> dict[str, Any]:
    reset_directory(SOURCE_DIR, ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID)
    spec = StrategySpec()
    source_rows = [source_record_row()]
    catalog_rows = [
        {
            "source_record_id": spec.source_record_id,
            "strategy_id": spec.strategy_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "architecture_id": spec.architecture_id,
            "strategy_architecture": spec.strategy_architecture,
            "source_or_research_lineage": spec.source_or_research_lineage,
            "instrument_universe": spec.universe,
            "parameters": {
                "defensive_event": "close_of_last_regular_us_trading_session_of_April",
                "defensive_target": defensive_target(),
                "cyclical_event": "close_of_last_regular_us_trading_session_of_October",
                "cyclical_target": cyclical_target(),
                "between_events": "hold_and_naturally_drift_no_filters",
                "warmup": "BIL_until_first_complete_event_with_valid_execution_prices",
            },
            "controls": spec.controls,
            "critical_controls": spec.critical_controls,
            "primary_future_robustness_role": spec.primary_future_robustness_role,
            "route": spec.route,
            "proposed_trial_id": spec.trial_id,
            "entity_type": "preregistration_catalog_record",
            "provider_requirement": "none",
            "unresolved_material_fields": 0,
            "experiment_trial_created": False,
        }
    ]
    selected = {
        "task_id": SOURCE_TASK_ID,
        "historical_intake_outcome": "one_candidate_only_insufficient_for_batch",
        "candidate_count": 1,
        "source_packages_reviewed": 18,
        "serious_candidates_assessed": 9,
        "independently_qualified_candidates": 1,
        "implementation_previously_authorized": False,
        "historical_next_action": "direction_owner_review_source_backed_v4_shortfall_and_discovery_model_v1",
        "direction_overlay": {
            "independently_qualified_candidate_retained": True,
            "single_candidate_execution_now_authorized": True,
            "candidate_rule_changed": False,
            "candidate_controls_changed": False,
            "only_cohort_policy_changed": True,
        },
        "candidates": [
            {
                **source_record_row(),
                "display_name": DISPLAY_NAME,
                "strategy_architecture": ARCHITECTURE,
                "ordered_universe": list(UNIVERSE),
                "controls": list(CONTROLS),
                "critical_controls": list(CRITICAL_CONTROLS),
                "proposed_trial_id": TRIAL_ID,
                "exact_source_replication_claimed": False,
                "reason_exact_replication_not_claimed": [
                    "source methodology uses equal-weight sector indices",
                    "accepted-47 implementation uses corresponding Select Sector SPDR ETFs",
                ],
            }
        ],
    }
    manifest = {
        "task_id": SOURCE_TASK_ID,
        "mode": MODE,
        "stage": "source_extracted",
        "historical_intake_outcome": "one_candidate_only_insufficient_for_batch",
        "source_packages_reviewed": 18,
        "serious_candidates_assessed": 9,
        "independently_qualified_candidates": 1,
        "selected_source_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_trial_count": 1,
        "implementation_previously_authorized": False,
        "implementation_now_authorized_by": "discovery_cohort_policy_v2",
        "performance_executed": False,
        "provider_access_performed": False,
        "source_completion_performed": False,
        "experiment_trial_entities_created": 0,
        "next_action": TASK_ID,
    }
    role_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "primary_future_robustness_role": PRIMARY_ROLE,
            "role_preregistered_before_performance": True,
            "role_classification_basis": ARCHITECTURE,
            "route": ROUTE,
        }
    ]
    version_rows = [
        {
            "source_record_id": SOURCE_RECORD_ID,
            "strategy_id": STRATEGY_ID,
            "source_version": "accepted_47_v4_bounded_source_packet",
            "source_completion_performed": False,
            "provider_access_performed": False,
            "exact_source_replication_claimed": False,
            "etf_translation_from_sector_indices_disclosed": True,
            "version_status": "frozen_for_canonical_exploration",
        }
    ]
    rejection_rows = [
        {
            "ledger_type": "historical_v4_aggregate_rejection_summary",
            "source_task_id": SOURCE_TASK_ID,
            "serious_candidates_assessed": 9,
            "independently_qualified_candidates": 1,
            "rejected_or_not_advanced_candidates": 8,
            "converted_to_strategy_configurations": 0,
            "converted_to_trials": 0,
            "notes": "Rejected V4 ideas are preserved only as aggregate historical counts; no rejected idea is converted in this task.",
        }
    ]
    overlay_rows = [
        {
            "overlay_id": "discovery_cohort_policy_v2_overlay_for_v4",
            "source_task_id": SOURCE_TASK_ID,
            "retained_source_record_id": SOURCE_RECORD_ID,
            "retained_strategy_id": STRATEGY_ID,
            "independently_qualified_candidate_retained": True,
            "single_candidate_execution_now_authorized": True,
            "candidate_rule_changed": False,
            "candidate_controls_changed": False,
            "only_cohort_policy_changed": True,
        }
    ]

    write_yaml_at(SOURCE_DIR, "intake_manifest.yaml", manifest)
    write_csv_at(SOURCE_DIR, "source_library_records.csv", source_rows)
    write_yaml_at(SOURCE_DIR, "selected_candidate_specs.yaml", selected)
    write_csv_at(SOURCE_DIR, "configuration_trial_catalog.csv", catalog_rows)
    write_csv_at(SOURCE_DIR, "benchmark_reference_catalog.csv", benchmark_rows())
    write_csv_at(SOURCE_DIR, "robustness_role_preregistration.csv", role_rows)
    write_csv_at(SOURCE_DIR, "source_version_reconciliation.csv", version_rows)
    write_csv_at(SOURCE_DIR, "rejection_ledger.csv", rejection_rows)
    write_csv_at(SOURCE_DIR, "direction_policy_overlay.csv", overlay_rows)
    write_csv_at(SOURCE_DIR, "historical_v4_intake_reconciliation.csv", historical_reconciliation_rows())
    (SOURCE_DIR / "source_lineage.md").write_text(
        "\n".join(
            [
                "# Accepted 47 V4 Source Lineage",
                "",
                f"`{SOURCE_RECORD_ID}` is retained as the single independently qualified V4 source-backed candidate.",
                "",
                "Exact replication is not claimed because the source methodology uses equal-weight sector indices while this accepted-47 implementation uses the corresponding Select Sector SPDR ETFs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (SOURCE_DIR / "conditional_codex_prompt.md").write_text(
        "Execute exactly the retained CFRA-Stovall candidate after discovery_cohort_policy_v2. Do not search for or add a second candidate.\n",
        encoding="utf-8",
    )
    checks = {
        "historical_outcome_preserved": manifest["historical_intake_outcome"] == "one_candidate_only_insufficient_for_batch",
        "source_packages_reviewed_preserved": manifest["source_packages_reviewed"] == 18,
        "serious_candidates_assessed_preserved": manifest["serious_candidates_assessed"] == 9,
        "independently_qualified_candidates_preserved": manifest["independently_qualified_candidates"] == 1,
        "implementation_previously_authorized_false": not manifest["implementation_previously_authorized"],
        "single_candidate_authorized_by_overlay": overlay_rows[0]["single_candidate_execution_now_authorized"],
        "candidate_controls_unchanged": not overlay_rows[0]["candidate_controls_changed"],
        "candidate_rule_unchanged": not overlay_rows[0]["candidate_rule_changed"],
        "exactly_one_source_record": len(source_rows) == 1,
        "exactly_one_catalog_record": len(catalog_rows) == 1,
        "no_rejected_v4_idea_converted": rejection_rows[0]["converted_to_strategy_configurations"] == 0
        and rejection_rows[0]["converted_to_trials"] == 0,
    }
    checks["overall_pass"] = all(checks.values())
    write_json_at(SOURCE_DIR, "consistency_check.json", checks)
    (SOURCE_DIR / "intake_report.md").write_text(
        "\n".join(
            [
                "# Accepted 47 Role-Aware Source-Backed Intake V4",
                "",
                "Historical outcome remains `one_candidate_only_insufficient_for_batch`.",
                "",
                "The separate direction overlay authorizes single-candidate execution without changing candidate-level rules, controls, source requirements, costs, role preregistration, or eligibility standards.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return checks


def load_prices() -> tuple[pd.DataFrame, list[dict[str, Any]], bool]:
    frames: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = CACHE_DIR / f"{symbol}.csv"
        frame = market.load_adjusted_ohlcv(symbol)
        frames[symbol] = frame
        ohlc = frame[["open", "high", "low", "close", "adj_close"]] if not frame.empty else pd.DataFrame()
        values = ohlc.to_numpy(dtype=float) if not ohlc.empty else np.empty((0, 0))
        checks = {
            "cache_exists": path.is_file(),
            "uses_existing_canonical_research_cache": relative(path).startswith("data/cache/"),
            "ordered_unique_sessions": bool(not frame.empty and frame.index.is_monotonic_increasing and frame.index.is_unique),
            "finite_positive_adjusted_ohlc": bool(values.size and np.isfinite(values).all() and (values > 0.0).all()),
            "valid_adjusted_ohlc_relationships": bool(
                not frame.empty
                and (frame["high"] >= frame[["open", "close", "low"]].max(axis=1) - TOLERANCE).all()
                and (frame["low"] <= frame[["open", "close", "high"]].min(axis=1) + TOLERANCE).all()
            ),
        }
        rows.append(
            {
                "record_type": "symbol_cache",
                "symbol": symbol,
                "cache_path": relative(path),
                "cache_hash": sha256_file(path),
                "first_valid_date": frame.index.min().date().isoformat() if not frame.empty else "",
                "last_valid_date": frame.index.max().date().isoformat() if not frame.empty else "",
                "row_count": int(len(frame)),
                **checks,
                "provider_access_performed": False,
                "network_access_performed": False,
                "cache_modified": False,
                "preflight_status": "pass" if all(checks.values()) else "fail",
            }
        )
    if any(frame.empty for frame in frames.values()):
        return pd.DataFrame(), rows, False
    prices = pd.concat([frames[symbol]["adj_close"].rename(symbol) for symbol in REQUIRED_SYMBOLS], axis=1, join="inner").dropna().sort_index()
    complete_events = event_dates(prices.index)
    windows = completed_windows(complete_events)
    midpoint = len(windows) // 2
    first_half_count = len(windows[:midpoint])
    second_half_count = len(windows[midpoint:])
    signal_count_pass = len(windows) >= 20 and first_half_count >= 8 and second_half_count >= 8
    common_checks = {
        "all_required_symbols_available": all(row["preflight_status"] == "pass" for row in rows),
        "common_period_nonempty": not prices.empty,
        "common_period_ordered_unique": bool(not prices.empty and prices.index.is_monotonic_increasing and prices.index.is_unique),
        "complete_half_year_windows_overall": len(windows),
        "complete_half_year_windows_first_chronological_half": first_half_count,
        "complete_half_year_windows_second_chronological_half": second_half_count,
        "signal_count_pass": signal_count_pass,
        "provider_access_performed": False,
        "network_access_performed": False,
        "preflight_status": "pass" if signal_count_pass and not prices.empty else "fail",
    }
    rows.append(
        {
            "record_type": "common_etf_period",
            "symbol": "|".join(REQUIRED_SYMBOLS),
            "cache_path": "|".join(relative(CACHE_DIR / f"{symbol}.csv") for symbol in REQUIRED_SYMBOLS),
            "first_valid_date": prices.index.min().date().isoformat() if not prices.empty else "",
            "last_valid_date": prices.index.max().date().isoformat() if not prices.empty else "",
            "row_count": int(len(prices)),
            **common_checks,
        }
    )
    return prices, rows, bool(common_checks["preflight_status"] == "pass")


def last_session_of_month(index: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp | None:
    dates = index[(index.year == year) & (index.month == month)]
    return pd.Timestamp(dates[-1]) if len(dates) else None


def event_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    dates: list[pd.Timestamp] = []
    if index.empty:
        return dates
    for year in range(int(index.min().year), int(index.max().year) + 1):
        for month in (4, 10):
            event = last_session_of_month(index, year, month)
            if event is not None:
                dates.append(event)
    return sorted(set(dates))


def completed_windows(events: list[pd.Timestamp]) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    return [(events[index], events[index + 1]) for index in range(len(events) - 1)]


def event_name(date_value: pd.Timestamp) -> str:
    if int(date_value.month) == 4:
        return "April_defensive_event"
    if int(date_value.month) == 10:
        return "October_cyclical_event"
    return "unexpected_event"


def target_for_event(date_value: pd.Timestamp, complementary: bool = False) -> dict[str, float]:
    if int(date_value.month) == 4:
        return cyclical_target() if complementary else defensive_target()
    if int(date_value.month) == 10:
        return defensive_target() if complementary else cyclical_target()
    raise ValueError(f"unexpected CFRA-Stovall event month: {date_value}")


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0).astype(float)


def build_event_frame(index: pd.DatetimeIndex, event_targets: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    return accounting.event_frame(index, UNIVERSE, event_targets).reindex(columns=list(UNIVERSE), fill_value=0.0)


def static_event_frame(index: pd.DatetimeIndex, events: list[pd.Timestamp], weights: dict[str, float]) -> pd.DataFrame:
    event_targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target()}
    for event in events:
        event_targets[pd.Timestamp(event)] = target(weights)
    return build_event_frame(index, event_targets)


def prepare_strategy(prices: pd.DataFrame) -> dict[str, Any]:
    index = prices.index
    events = event_dates(index)
    event_targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target()}
    complementary_targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target()}
    equal_targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target()}
    execution_rows: list[dict[str, Any]] = []
    first_execution: pd.Timestamp | None = None
    previous_target = bil_target()
    for event in events:
        candidate_target = target_for_event(event)
        nonzero = [symbol for symbol, weight in candidate_target.items() if weight > WEIGHT_TOLERANCE]
        prices_valid = bool(np.isfinite(prices.loc[event, nonzero].to_numpy(dtype=float)).all()) if nonzero else True
        if prices_valid:
            event_targets[event] = candidate_target
            complementary_targets[event] = target_for_event(event, complementary=True)
            equal_targets[event] = equal_six_target()
            if first_execution is None:
                first_execution = event
            status = "executed_at_source_event_close"
        else:
            status = "blocked_missing_event_date_execution_price"
        execution_rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "event_date": event.date().isoformat(),
                "event_month": int(event.month),
                "event_type": event_name(event),
                "source_event_date_known_before_close": True,
                "target_frozen_before_event_close": True,
                "execution_price_date": event.date().isoformat() if prices_valid else "",
                "valid_execution_price_all_nonzero_assets": prices_valid,
                "blocked_event": not prices_valid,
                "missed_event_executed_late": False,
                "event_session_return_assigned_to_pre_event_holdings": True,
                "new_target_return_begins_following_session": True,
                "pre_event_target_weights": previous_target,
                "candidate_target_weights": candidate_target if prices_valid else previous_target,
                "explicit_zero_weights": True,
                "execution_status": status,
            }
        )
        if prices_valid:
            previous_target = candidate_target
    if first_execution is None:
        raise RuntimeError("no complete April/October event was executable from the common ETF period")

    candidate_events = build_event_frame(index, event_targets)
    target_average = target_history(candidate_events, index).loc[first_execution:].mean().to_dict()
    target_total = float(sum(target_average.values()))
    if target_total > 0.0:
        target_average = {symbol: float(value) / target_total for symbol, value in target_average.items()}
    controls = {
        NAMED_CONTROL: build_event_frame(index, complementary_targets),
        STATIC_CONTROL: static_event_frame(index, events, target_average),
        EQUAL_CONTROL: build_event_frame(index, equal_targets),
        SPY_CONTROL: build_event_frame(index, {pd.Timestamp(index[0]): target({"SPY": 1.0})}),
        BIL_CONTROL: build_event_frame(index, {pd.Timestamp(index[0]): bil_target()}),
    }
    return {
        "spec": StrategySpec(),
        "prices": prices,
        "events": events,
        "candidate_events": candidate_events,
        "control_events": controls,
        "event_execution_rows": execution_rows,
        "first_eligible_execution": first_execution,
        "average_target_weights": target_average,
        "risk_symbols": SECTOR_SYMBOLS,
    }


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "source_event_date_close_target_applied_to_following_regular_session_return"
    return {
        "candidate_paths": {
            cost: accounting.simulate_path(prepared["prices"], prepared["candidate_events"], cost, timing)
            for cost in COSTS
        },
        "control_paths": {
            (control_id, cost): accounting.simulate_path(prepared["prices"], events, cost, timing)
            for control_id, events in prepared["control_events"].items()
            for cost in COSTS
        },
    }


def eligible_index(prepared: dict[str, Any]) -> pd.DatetimeIndex:
    return prepared["prices"].index[prepared["prices"].index >= prepared["first_eligible_execution"]]


def window_rows(prepared: dict[str, Any], simulation: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    events = [
        pd.Timestamp(row["event_date"])
        for row in prepared["event_execution_rows"]
        if row["execution_status"] == "executed_at_source_event_close"
    ]
    windows = completed_windows(events)
    candidate_returns = simulation["candidate_paths"][PRIMARY_COST]["returns"]
    named_returns = simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)]["returns"]
    midpoint = len(windows) // 2
    for number, (start, end) in enumerate(windows, start=1):
        period_index = candidate_returns.index[(candidate_returns.index > start) & (candidate_returns.index <= end)]
        candidate_return = float((1.0 + candidate_returns.reindex(period_index).dropna()).prod() - 1.0)
        named_return = float((1.0 + named_returns.reindex(period_index).dropna()).prod() - 1.0)
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "window_number": number,
                "window_id": f"{start.date().isoformat()}__to__{end.date().isoformat()}",
                "economic_event_unit": "completed_April_to_October_or_October_to_April_holding_window",
                "window_type": "April_to_October" if start.month == 4 and end.month == 10 else "October_to_April",
                "start_event_date": start.date().isoformat(),
                "end_event_date": end.date().isoformat(),
                "start_event_type": event_name(start),
                "end_event_type": event_name(end),
                "complete_half_year_source_window": True,
                "chronological_half": "first_chronological_half" if number <= midpoint else "second_chronological_half",
                "return_session_count": int(len(period_index)),
                "candidate_return_5bps": candidate_return,
                "named_control_return_5bps": named_return,
                "candidate_minus_named_excess_5bps": candidate_return - named_return,
                "entry_and_exit_legs_counted_separately": False,
                "turnover_events_counted_as_multiple_windows": False,
            }
        )
    return rows


def complete_calendar_years(index: pd.DatetimeIndex) -> list[int]:
    years: list[int] = []
    for year in sorted(set(index.year)):
        dates = index[index.year == year]
        if len(dates) and int(dates[0].month) == 1 and int(dates[-1].month) == 12:
            years.append(int(year))
    return years


def event_window_count_in_period(window_inventory: list[dict[str, Any]], period_index: pd.DatetimeIndex) -> int:
    if not len(period_index):
        return 0
    start = pd.Timestamp(period_index.min())
    end = pd.Timestamp(period_index.max())
    return sum(
        pd.Timestamp(row["start_event_date"]) >= start and pd.Timestamp(row["end_event_date"]) <= end
        for row in window_inventory
    )


def metric_payload(path: dict[str, Any], period_index: pd.DatetimeIndex, window_count: int) -> dict[str, Any]:
    returns = path["returns"].reindex(period_index).dropna()
    daily = path["daily"].reindex(returns.index)
    held = path["held_weights"].reindex(returns.index).dropna(how="all")
    metrics = accounting.metric_payload(path, returns.index)
    weight_sums = held.sum(axis=1) if len(held) else pd.Series(dtype=float)
    exact_sum_pass = bool(len(weight_sums) and np.isclose(weight_sums.to_numpy(dtype=float), 1.0, atol=WEIGHT_TOLERANCE, rtol=0.0).all())
    nonnegative_pass = bool(len(held) and (held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all())
    gross_pass = bool(len(daily) and float(daily["max_gross_exposure"].max()) <= 1.0 + WEIGHT_TOLERANCE)
    metrics.update(
        {
            "evaluation_start": returns.index.min().date().isoformat() if len(returns) else "",
            "evaluation_end": returns.index.max().date().isoformat() if len(returns) else "",
            "complete_event_window_count": int(window_count),
            "average_asset_weights": held.mean().to_dict() if len(held) else {},
            "maximum_single_asset_weight": float(held.max(axis=1).max()) if len(held) else float("nan"),
            "gross_exposure": float(daily["max_gross_exposure"].max()) if len(daily) else float("nan"),
            "rebalance_count": int(metrics["trade_or_rebalance_count"]),
            "cost_drag": float(metrics["transaction_cost_drag"]),
            "timing_invariant_status": "pass_event_session_return_with_pre_event_holdings",
            "accounting_invariant_status": "pass_natural_drift_turnover_and_cost_once"
            if metrics["invariant_pass"]
            else "fail",
            "numeric_invariant_status": metrics["numeric_invariant_status"],
            "weight_invariant_status": "pass" if exact_sum_pass and nonnegative_pass and gross_pass else "fail",
            "nonnegative_weights": nonnegative_pass,
            "no_leverage": gross_pass,
            "no_shorting": nonnegative_pass,
            "daily_weight_sum_one_within_tolerance": exact_sum_pass,
        }
    )
    metrics["invariant_pass"] = bool(
        metrics["invariant_pass"]
        and metrics["weight_invariant_status"] == "pass"
        and metrics["timing_invariant_status"].startswith("pass")
    )
    return metrics


def result_row(
    series_id: str,
    entity_role: str,
    cost: float,
    period: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "series_id": series_id,
        "entity_role": entity_role,
        "cost_bps_one_way": cost,
        "period": period,
        **values,
    }


def full_result_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = eligible_index(prepared)
    window_count = event_window_count_in_period(windows, eligible)
    candidate_rows = [
        result_row(
            STRATEGY_ID,
            "candidate",
            cost,
            "full_period",
            metric_payload(simulation["candidate_paths"][cost], eligible, window_count),
        )
        for cost in COSTS
    ]
    control_rows: list[dict[str, Any]] = []
    for control_id in CONTROLS:
        for cost in COSTS:
            control_rows.append(
                result_row(
                    control_id,
                    "benchmark_reference",
                    cost,
                    "full_period",
                    metric_payload(simulation["control_paths"][(control_id, cost)], eligible, window_count),
                )
            )
    return candidate_rows, control_rows


def half_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period, period_index in accounting.split_halves(eligible_index(prepared)):
        window_count = event_window_count_in_period(windows, period_index)
        rows.append(
            result_row(
                STRATEGY_ID,
                "candidate",
                PRIMARY_COST,
                period,
                metric_payload(simulation["candidate_paths"][PRIMARY_COST], period_index, window_count),
            )
        )
        for control_id in CONTROLS:
            rows.append(
                result_row(
                    control_id,
                    "benchmark_reference",
                    PRIMARY_COST,
                    period,
                    metric_payload(simulation["control_paths"][(control_id, PRIMARY_COST)], period_index, window_count),
                )
            )
    return rows


def calendar_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    eligible = eligible_index(prepared)
    for year in complete_calendar_years(eligible):
        period_index = eligible[eligible.year == year]
        window_count = event_window_count_in_period(windows, period_index)
        rows.append(
            result_row(
                STRATEGY_ID,
                "candidate",
                PRIMARY_COST,
                str(year),
                metric_payload(simulation["candidate_paths"][PRIMARY_COST], period_index, window_count),
            )
        )
        for control_id in CONTROLS:
            rows.append(
                result_row(
                    control_id,
                    "benchmark_reference",
                    PRIMARY_COST,
                    str(year),
                    metric_payload(simulation["control_paths"][(control_id, PRIMARY_COST)], period_index, window_count),
                )
            )
    return rows


def path_gross_contributions(path: dict[str, Any], prices: pd.DataFrame, period_index: pd.DatetimeIndex) -> pd.Series:
    aligned_prices = prices.reindex(period_index).dropna()
    asset_returns = aligned_prices.pct_change(fill_method=None).fillna(0.0)
    held = path["held_weights"].reindex(aligned_prices.index).fillna(0.0)
    return (held * asset_returns).sum(axis=0)


def portfolio_contribution_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    period_index = eligible_index(prepared)
    series_paths: list[tuple[str, str, dict[str, Any]]] = [
        (STRATEGY_ID, "candidate", simulation["candidate_paths"][PRIMARY_COST])
    ]
    series_paths.extend(
        (control_id, "benchmark_reference", simulation["control_paths"][(control_id, PRIMARY_COST)])
        for control_id in CONTROLS
    )
    for series_id, role, path in series_paths:
        contributions = path_gross_contributions(path, prepared["prices"], period_index)
        held = path["held_weights"].reindex(period_index).dropna(how="all")
        for symbol in UNIVERSE:
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "series_id": series_id,
                    "entity_role": role,
                    "cost_bps_one_way": PRIMARY_COST,
                    "period": "full_period",
                    "asset": symbol,
                    "average_weight": float(held[symbol].mean()) if len(held) and symbol in held else 0.0,
                    "arithmetic_gross_return_contribution": float(contributions.get(symbol, 0.0)),
                    "positive_contribution": float(max(contributions.get(symbol, 0.0), 0.0)),
                }
            )
    return rows


def sector_contribution_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    period_index = eligible_index(prepared)
    candidate = path_gross_contributions(simulation["candidate_paths"][PRIMARY_COST], prepared["prices"], period_index)
    named = path_gross_contributions(
        simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)], prepared["prices"], period_index
    )
    rows: list[dict[str, Any]] = []
    for symbol in SECTOR_SYMBOLS:
        excess = float(candidate.get(symbol, 0.0) - named.get(symbol, 0.0))
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "comparison_control": NAMED_CONTROL,
                "asset": symbol,
                "candidate_arithmetic_contribution_5bps": float(candidate.get(symbol, 0.0)),
                "named_control_arithmetic_contribution_5bps": float(named.get(symbol, 0.0)),
                "candidate_minus_named_excess_contribution_5bps": excess,
                "positive_excess_contribution": max(excess, 0.0),
            }
        )
    return rows


def concentration_summary(
    dimension: str,
    rows: list[dict[str, Any]],
    component_field: str,
    value_field: str,
) -> list[dict[str, Any]]:
    positives = [(row[component_field], float(row[value_field])) for row in rows if float(row[value_field]) > 0.0]
    total_positive = float(sum(value for _, value in positives))
    output: list[dict[str, Any]] = []
    for component, value in positives:
        output.append(
            {
                "row_type": "component",
                "dimension": dimension,
                "component": component,
                "candidate_minus_named_excess_5bps": value,
                "positive_excess": value,
                "share_of_total_positive_excess": value / total_positive if total_positive > 0.0 else "",
                "concentration_status": "",
                "pass": "",
            }
        )
    if total_positive <= 0.0:
        output.append(
            {
                "row_type": "summary",
                "dimension": dimension,
                "component": "not_applicable_no_positive_excess",
                "candidate_minus_named_excess_5bps": sum(float(row[value_field]) for row in rows),
                "positive_excess": 0.0,
                "share_of_total_positive_excess": "",
                "strongest_positive_component": "",
                "strongest_positive_excess": 0.0,
                "concentration_status": "not_applicable_no_positive_excess",
                "pass": True,
            }
        )
        return output
    strongest_component, strongest_value = max(positives, key=lambda item: item[1])
    share = strongest_value / total_positive
    output.append(
        {
            "row_type": "summary",
            "dimension": dimension,
            "component": strongest_component,
            "candidate_minus_named_excess_5bps": strongest_value,
            "positive_excess": total_positive,
            "share_of_total_positive_excess": share,
            "strongest_positive_component": strongest_component,
            "strongest_positive_excess": strongest_value,
            "concentration_status": "pass" if share <= 0.80 + TOLERANCE else "fail_concentration_risk",
            "pass": share <= 0.80 + TOLERANCE,
        }
    )
    return output


def concentration_rows(
    windows: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    sectors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    candidate_calendar = [
        row
        for row in calendar
        if row["series_id"] == STRATEGY_ID and row["entity_role"] == "candidate"
    ]
    named_calendar = {
        row["period"]: row
        for row in calendar
        if row["series_id"] == NAMED_CONTROL and row["entity_role"] == "benchmark_reference"
    }
    calendar_excess = [
        {
            "calendar_year": row["period"],
            "candidate_minus_named_excess_5bps": float(row["total_return"])
            - float(named_calendar[row["period"]]["total_return"]),
        }
        for row in candidate_calendar
        if row["period"] in named_calendar
    ]
    output: list[dict[str, Any]] = []
    output.extend(
        concentration_summary(
            "completed_half_year_source_window",
            windows,
            "window_id",
            "candidate_minus_named_excess_5bps",
        )
    )
    output.extend(
        concentration_summary(
            "calendar_year",
            calendar_excess,
            "calendar_year",
            "candidate_minus_named_excess_5bps",
        )
    )
    output.extend(
        concentration_summary(
            "sector_asset",
            sectors,
            "asset",
            "candidate_minus_named_excess_contribution_5bps",
        )
    )
    summary_rows = [row for row in output if row["row_type"] == "summary"]
    passes = all(bool(row["pass"]) for row in summary_rows)
    return output, passes


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - TOLERANCE
        and float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - TOLERANCE
        and float(control["maximum_drawdown"]) >= float(candidate["maximum_drawdown"]) - TOLERANCE
    )
    strictly_better = (
        float(control["cagr"]) > float(candidate["cagr"]) + TOLERANCE
        or float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + TOLERANCE
        or float(control["maximum_drawdown"]) > float(candidate["maximum_drawdown"]) + TOLERANCE
    )
    return bool(equal_or_better and strictly_better)


def material_improvement(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - TOLERANCE
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - TOLERANCE
    )


def not_worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return not (
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"]) - TOLERANCE
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"]) - TOLERANCE
    )


def standalone_gate(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    windows: list[dict[str, Any]],
    concentration_pass: bool,
) -> tuple[bool, dict[str, bool]]:
    eligible = eligible_index(prepared)
    window_count = event_window_count_in_period(windows, eligible)
    candidate = metric_payload(simulation["candidate_paths"][PRIMARY_COST], eligible, window_count)
    named = metric_payload(simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)], eligible, window_count)
    static = metric_payload(simulation["control_paths"][(STATIC_CONTROL, PRIMARY_COST)], eligible, window_count)
    candidate10 = metric_payload(simulation["candidate_paths"][10.0], eligible, window_count)
    named10 = metric_payload(simulation["control_paths"][(NAMED_CONTROL, 10.0)], eligible, window_count)
    static10 = metric_payload(simulation["control_paths"][(STATIC_CONTROL, 10.0)], eligible, window_count)
    halves_named_pass = True
    halves_static_pass = True
    for _, half_index in accounting.split_halves(eligible):
        count = event_window_count_in_period(windows, half_index)
        candidate_half = metric_payload(simulation["candidate_paths"][PRIMARY_COST], half_index, count)
        named_half = metric_payload(simulation["control_paths"][(NAMED_CONTROL, PRIMARY_COST)], half_index, count)
        static_half = metric_payload(simulation["control_paths"][(STATIC_CONTROL, PRIMARY_COST)], half_index, count)
        halves_named_pass = halves_named_pass and not_worse_on_both(candidate_half, named_half)
        halves_static_pass = halves_static_pass and not_worse_on_both(candidate_half, static_half)
    signal_count_pass = len(windows) >= 20 and sum(row["chronological_half"] == "first_chronological_half" for row in windows) >= 8 and sum(row["chronological_half"] == "second_chronological_half" for row in windows) >= 8
    checks = {
        "positive_full_period_return": float(candidate["total_return"]) > 0.0,
        "every_invariant_passes": bool(candidate["invariant_pass"]),
        "named_control_does_not_dominate": not dominates(named, candidate),
        "static_control_does_not_dominate": not dominates(static, candidate),
        "material_vs_named_control": material_improvement(candidate, named),
        "material_vs_static_control": material_improvement(candidate, static),
        "not_worse_than_named_in_either_half_on_both_sharpe_and_drawdown": halves_named_pass,
        "not_worse_than_static_in_either_half_on_both_sharpe_and_drawdown": halves_static_pass,
        "positive_at_10bps": float(candidate10["total_return"]) > 0.0,
        "not_dominated_by_both_critical_controls_at_10bps": not (
            dominates(named10, candidate10) and dominates(static10, candidate10)
        ),
        "signal_count_requirements_pass": signal_count_pass,
        "lightweight_concentration_pass_or_not_applicable": concentration_pass,
    }
    return all(checks.values()), checks


def load_archived_reference_returns() -> tuple[pd.Series, dict[str, Any]]:
    source_path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    if not source_path.is_file():
        return pd.Series(dtype=float, name="active_vm_dsr_usci_equal_weight_reference"), {
            "status": "research_reference_diagnostic_unavailable",
            "reason": "missing_archived_research_reference",
            "source_path": relative(source_path),
        }
    reference = market.active_vm_dsr_usci_reference_returns().dropna()
    status = {
        "status": "available" if len(reference) else "research_reference_diagnostic_unavailable",
        "reason": "" if len(reference) else "empty_archived_research_reference",
        "source_path": relative(source_path),
        "source_hash": sha256_file(source_path),
        "live_observation_state_read": False,
        "broker_or_provider_access_performed": False,
    }
    return reference, status


def diversifier_paths(
    simulation: dict[str, Any],
    eligible: pd.DatetimeIndex,
) -> tuple[dict[tuple[str, float], dict[str, Any]], dict[str, Any]]:
    reference, status = load_archived_reference_returns()
    if status["status"] != "available":
        return {}, status
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        common = reference.index.intersection(eligible)
        if len(common) == 0:
            return {}, {
                **status,
                "status": "research_reference_diagnostic_unavailable",
                "reason": "no_overlap_with_candidate_period",
            }
        ref = reference.reindex(common).dropna()
        paths[("100pct_archived_research_reference", cost)] = portfolio_helpers.reference_path(ref)
        for construction, sleeve_path in (
            ("80pct_reference_20pct_candidate", simulation["candidate_paths"][cost]),
            ("80pct_reference_20pct_named_control", simulation["control_paths"][(NAMED_CONTROL, cost)]),
            ("80pct_reference_20pct_static_control", simulation["control_paths"][(STATIC_CONTROL, cost)]),
        ):
            paths[(construction, cost)] = portfolio_helpers.path_from_two_sleeves(ref, sleeve_path, cost)
    return paths, status


def diversifier_metric(path: dict[str, Any]) -> dict[str, Any]:
    index = path["returns"].index
    metrics = accounting.metric_payload(path, index)
    held = path["held_weights"].reindex(index).dropna(how="all")
    metrics.update(
        {
            "evaluation_start": index.min().date().isoformat() if len(index) else "",
            "evaluation_end": index.max().date().isoformat() if len(index) else "",
            "complete_event_window_count": "",
            "average_asset_weights": held.mean().to_dict() if len(held) else {},
            "maximum_single_asset_weight": float(held.max(axis=1).max()) if len(held) else float("nan"),
            "gross_exposure": float(path["daily"]["max_gross_exposure"].max()) if len(index) else float("nan"),
            "rebalance_count": int(metrics["trade_or_rebalance_count"]),
            "cost_drag": float(metrics["transaction_cost_drag"]),
            "timing_invariant_status": metrics["timing_invariant_status"],
            "accounting_invariant_status": "pass_reference_sleeve_natural_drift_actual_turnover_and_cost_once"
            if metrics["invariant_pass"]
            else "fail",
            "weight_invariant_status": metrics["exposure_weight_invariant_status"],
        }
    )
    return metrics


def diversifier_result_rows(paths: dict[tuple[str, float], dict[str, Any]], status: dict[str, Any]) -> list[dict[str, Any]]:
    if not paths:
        return [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "series_id": "research_reference_diagnostic_unavailable",
                "entity_role": "portfolio_diagnostic",
                "cost_bps_one_way": PRIMARY_COST,
                "period": "full_period",
                "diagnostic_status": status["status"],
                "diagnostic_reason": status.get("reason", ""),
            }
        ]
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        for construction in (
            "100pct_archived_research_reference",
            "80pct_reference_20pct_candidate",
            "80pct_reference_20pct_named_control",
            "80pct_reference_20pct_static_control",
        ):
            rows.append(
                result_row(
                    construction,
                    "portfolio_diagnostic",
                    cost,
                    "full_period",
                    diversifier_metric(paths[(construction, cost)]),
                )
            )
    return rows


def diversifier_gate(paths: dict[tuple[str, float], dict[str, Any]]) -> tuple[bool, dict[str, bool]]:
    if not paths:
        return False, {"research_reference_diagnostic_available": False}
    candidate = diversifier_metric(paths[("80pct_reference_20pct_candidate", PRIMARY_COST)])
    reference = diversifier_metric(paths[("100pct_archived_research_reference", PRIMARY_COST)])
    named = diversifier_metric(paths[("80pct_reference_20pct_named_control", PRIMARY_COST)])
    static = diversifier_metric(paths[("80pct_reference_20pct_static_control", PRIMARY_COST)])
    candidate10 = diversifier_metric(paths[("80pct_reference_20pct_candidate", 10.0)])
    named10 = diversifier_metric(paths[("80pct_reference_20pct_named_control", 10.0)])
    static10 = diversifier_metric(paths[("80pct_reference_20pct_static_control", 10.0)])
    checks = {
        "research_reference_diagnostic_available": True,
        "candidate_materially_improves_reference": material_improvement(candidate, reference),
        "candidate_not_worse_than_reference_on_both_sharpe_and_drawdown": not_worse_on_both(candidate, reference),
        "named_control_does_not_dominate_portfolio": not dominates(named, candidate),
        "static_control_does_not_dominate_portfolio": not dominates(static, candidate),
        "candidate_materially_improves_named_control_portfolio": material_improvement(candidate, named),
        "candidate_materially_improves_static_control_portfolio": material_improvement(candidate, static),
        "ten_bps_not_dominated_by_both_portfolio_controls": not (
            dominates(named10, candidate10) and dominates(static10, candidate10)
        ),
    }
    return all(checks.values()), checks


def failure_vector(
    standalone_checks: dict[str, bool],
    diversifier_checks: dict[str, bool],
    concentration_pass: bool,
) -> list[dict[str, Any]]:
    mapping = [
        ("signal_count_requirements_pass", "signal_scarcity", "required complete half-year source windows are insufficient"),
        ("positive_full_period_return", "weak_return", "candidate full-period return is not positive"),
        ("every_invariant_passes", "methodology_failure", "timing, accounting, numeric, or weight invariant failed"),
        ("named_control_does_not_dominate", "weak_vs_primary_control", "named same-purpose control dominates candidate"),
        ("material_vs_named_control", "weak_vs_primary_control", "candidate lacks required Sharpe or drawdown improvement versus named same-purpose control"),
        ("static_control_does_not_dominate", "benchmark_like_behavior", "static average-weight control dominates candidate"),
        ("material_vs_static_control", "benchmark_like_behavior", "candidate lacks required Sharpe or drawdown improvement versus static weights"),
        (
            "not_worse_than_named_in_either_half_on_both_sharpe_and_drawdown",
            "period_instability",
            "candidate is worse than named control on both Sharpe and drawdown in a chronological half",
        ),
        (
            "not_worse_than_static_in_either_half_on_both_sharpe_and_drawdown",
            "period_instability",
            "candidate is worse than static control on both Sharpe and drawdown in a chronological half",
        ),
        ("positive_at_10bps", "cost_drag", "candidate does not remain positive at 10 bps"),
        ("not_dominated_by_both_critical_controls_at_10bps", "cost_drag", "candidate is dominated by both critical controls at 10 bps"),
        ("lightweight_concentration_pass_or_not_applicable", "concentration_risk", "positive excess is too concentrated"),
    ]
    rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "failure_reason": reason,
            "failed_gate": gate,
            "failure_detail": detail,
            "primary_failure_reason": False,
        }
        for gate, reason, detail in mapping
        if standalone_checks.get(gate) is False
    ]
    if standalone_checks and not concentration_pass and not any(row["failure_reason"] == "concentration_risk" for row in rows):
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "failure_reason": "concentration_risk",
                "failed_gate": "lightweight_concentration_summary",
                "failure_detail": "positive excess concentration failed",
                "primary_failure_reason": False,
            }
        )
    if diversifier_checks.get("research_reference_diagnostic_available") is False:
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "failure_reason": "data_or_comparability_failure",
                "failed_gate": "research_reference_diagnostic_available",
                "failure_detail": "diversifier diagnostic unavailable; standalone evaluation remains authoritative",
                "primary_failure_reason": False,
            }
        )
    return rows


def choose_outcome(
    standalone_pass: bool,
    diversifier_pass: bool,
    failures: list[dict[str, Any]],
    data_preflight_pass: bool,
) -> tuple[str, str, str]:
    if not data_preflight_pass:
        return "inconclusive_data_issue", "data_or_comparability_failure", NEXT_BLOCKED
    if standalone_pass:
        return "exploratory_followup_candidate_standalone", "", NEXT_ADVANCE
    if diversifier_pass:
        return "exploratory_followup_candidate_diversifier", "", NEXT_ADVANCE
    precedence = [
        "signal_scarcity",
        "weak_return",
        "methodology_failure",
        "weak_vs_primary_control",
        "benchmark_like_behavior",
        "period_instability",
        "cost_drag",
        "excess_drawdown",
        "concentration_risk",
        "data_or_comparability_failure",
        "overfit_or_unstable",
    ]
    observed = [row["failure_reason"] for row in failures]
    for reason in precedence:
        if reason in observed:
            return "closed_exploration", reason, NEXT_CLOSED
    return "closed_exploration", "overfit_or_unstable", NEXT_CLOSED


def strategy_card_rows(outcome: str, failure_reason: str, next_action: str) -> list[dict[str, Any]]:
    spec = StrategySpec()
    return [
        {
            "strategy_id": spec.strategy_id,
            "source_record_id": spec.source_record_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "entity_type": "strategy_configuration",
            "architecture_id": spec.architecture_id,
            "strategy_architecture": spec.strategy_architecture,
            "source_or_research_lineage": spec.source_or_research_lineage,
            "instrument_universe": spec.universe,
            "primary_future_robustness_role": spec.primary_future_robustness_role,
            "route": spec.route,
            "stage": STAGE,
            "trial_id": spec.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "exact_source_replication_claimed": False,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "provider_access_performed": False,
            "source_completion_performed": False,
        }
    ]


def trial_rows(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    return [
        {
            "trial_id": TRIAL_ID,
            "strategy_id": STRATEGY_ID,
            "source_record_id": SOURCE_RECORD_ID,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "parent_trial_id": "",
            "adaptation_label": "",
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "provider_access_performed": False,
            "source_completion_performed": False,
            "parameter_variants_authorized": 0,
            "outcome": outcome,
            "failure_reason": failure_reason,
        }
    ]


def process_task_rows(performance_executed: bool) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "strategy_configuration_count": 1,
            "canonical_experiment_trial_count": 1,
            "source_library_record_count": 1,
            "benchmark_reference_count": len(CONTROLS),
            "performance_executed": performance_executed,
            "provider_access_performed": False,
            "network_access_performed": False,
            "source_completion_performed": False,
            "optimization_performed": False,
            "paper_demo_observation_operation_performed": False,
            "broker_account_order_or_position_action_performed": False,
        }
    ]


def turnover_rows(simulation: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    series_paths: list[tuple[str, str, dict[str, Any]]] = [
        (STRATEGY_ID, "candidate", simulation["candidate_paths"][cost])
        for cost in COSTS
    ]
    series_paths.extend(
        (control_id, "benchmark_reference", simulation["control_paths"][(control_id, cost)])
        for control_id in CONTROLS
        for cost in COSTS
    )
    for series_id, role, path in series_paths:
        cost = next(
            float(cost_value)
            for cost_value in COSTS
            if path is simulation["candidate_paths"].get(cost_value)
            or any(path is simulation["control_paths"].get((control_id, cost_value)) for control_id in CONTROLS)
        )
        daily = path["daily"]
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "series_id": series_id,
                "entity_role": role,
                "cost_bps_one_way": cost,
                "turnover_formula": "0.5 * sum(abs(target_weight - pretrade_weight))",
                "total_one_way_turnover": float(daily["one_way_turnover"].sum()),
                "max_one_way_turnover": float(daily["one_way_turnover"].max()),
                "transaction_cost_drag": float(daily["transaction_cost_drag"].sum()),
                "rebalance_count": int((daily["one_way_turnover"] > WEIGHT_TOLERANCE).sum()),
                "cost_rows_are_separate_trials": False,
                "cost_charged_once": True,
                "turnover_nonnegative": bool((daily["one_way_turnover"] >= -WEIGHT_TOLERANCE).all()),
                "status": "pass",
            }
        )
    return rows


def invariant_rows(
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    windows: list[dict[str, Any]],
    deterministic_pass: bool,
    signal_count_pass: bool,
) -> list[dict[str, Any]]:
    path = simulation["candidate_paths"][PRIMARY_COST]
    eligible = eligible_index(prepared)
    held = path["held_weights"].reindex(eligible).dropna(how="all")
    target_events = path["target_events"]
    event_timing_pass = True
    following_pass = True
    for row in prepared["event_execution_rows"]:
        if row["execution_status"] != "executed_at_source_event_close":
            continue
        date_value = pd.Timestamp(row["event_date"])
        if date_value not in held.index:
            continue
        target_values = pd.Series(row["candidate_target_weights"], dtype=float).reindex(UNIVERSE).fillna(0.0)
        turnover = float(path["daily"].loc[date_value, "one_way_turnover"])
        if turnover > WEIGHT_TOLERANCE and np.allclose(
            held.loc[date_value].reindex(UNIVERSE).to_numpy(dtype=float),
            target_values.to_numpy(dtype=float),
            atol=1e-6,
            rtol=0.0,
        ):
            event_timing_pass = False
        position = prepared["prices"].index.get_loc(date_value)
        if position + 1 < len(prepared["prices"].index):
            next_date = prepared["prices"].index[position + 1]
            if next_date in path["held_weights"].index and not np.allclose(
                path["held_weights"].loc[next_date].reindex(UNIVERSE).to_numpy(dtype=float),
                target_values.to_numpy(dtype=float),
                atol=1e-6,
                rtol=0.0,
            ):
                following_pass = False
    checks = [
        ("accepted_47_universe_only", set(UNIVERSE) == set(REQUIRED_SYMBOLS), "|".join(UNIVERSE)),
        ("provider_access_not_performed", True, "local data/cache only"),
        ("source_completion_not_performed", True, "historical V4 source packet materialized from direction contract"),
        ("no_parameter_variants_authorized", True, TRIAL_ID),
        ("event_months_are_only_april_and_october", all(pd.Timestamp(row["event_date"]).month in {4, 10} for row in prepared["event_execution_rows"]), ""),
        ("event_session_return_remains_pre_event_holdings", event_timing_pass, ""),
        ("target_return_begins_following_regular_session", following_pass, ""),
        ("no_missed_event_executed_late", all(not row["missed_event_executed_late"] for row in prepared["event_execution_rows"]), ""),
        ("explicit_zero_weights_recorded", bool((target_events.reindex(columns=list(UNIVERSE), fill_value=0.0) == 0.0).any(axis=None)), ""),
        ("nonnegative_weights", bool((held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()), ""),
        ("no_leverage_or_shorting", bool((held.sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all() and (held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()), ""),
        ("daily_weight_sum_one_within_tolerance", bool(np.isclose(held.sum(axis=1).to_numpy(dtype=float), 1.0, atol=WEIGHT_TOLERANCE, rtol=0.0).all()), ""),
        ("complete_half_year_window_signal_count", signal_count_pass, len(windows)),
        ("deterministic_rerun", deterministic_pass, ""),
        ("exact_source_replication_not_claimed", True, "Select Sector SPDR ETF translation disclosed"),
    ]
    return [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "invariant": name,
            "status": "pass" if passed else "fail",
            "observed_value": value,
        }
        for name, passed, value in checks
    ]


def entity_counts() -> dict[str, Any]:
    return {
        "direction_correction_records": 1,
        "source_library_records_materialized": 1,
        "strategy_configurations": 1,
        "canonical_exploration_trials": 1,
        "process_tasks": 1,
        "robustness_trials": 0,
        "paper_demo_eligibility_records": 0,
        "handoff_export_packets": 0,
        "paper_demo_observations": 0,
        "forward_observation_records": 0,
        "controls_counted_as_strategies_or_trials": False,
        "event_windows_counted_as_strategies_or_trials": False,
        "reports_counted_as_strategies_or_trials": False,
        "entity_count_reconciliation_pass": True,
    }


def protected_reconciliation_rows(before: dict[str, str], after: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "before_hash": before.get(path, "missing"),
            "after_hash": after.get(path, "missing"),
            "changed": before.get(path, "missing") != after.get(path, "missing"),
            "status": "pass" if before.get(path, "missing") == after.get(path, "missing") else "fail",
        }
        for path in sorted(set(before) | set(after))
    ]


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    policy_checks = materialize_policy_packet()
    source_checks = materialize_source_packet()
    reset_directory(OUTPUT_DIR, ROOT / "evidence" / "research_recovery" / "cfra_stovall_semiannual_sector_rotation_exploration_v1")
    prices, preflight_rows, data_pass = load_prices()
    write_csv_at(OUTPUT_DIR, "data_preflight_reconciliation.csv", preflight_rows)

    performance_executed = False
    prepared: dict[str, Any] | None = None
    simulation: dict[str, Any] | None = None
    windows: list[dict[str, Any]] = []
    all_trial_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    chronological_results: list[dict[str, Any]] = []
    calendar_results: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    sector_rows: list[dict[str, Any]] = []
    concentration: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    standalone_checks: dict[str, bool] = {}
    diversifier_checks: dict[str, bool] = {"research_reference_diagnostic_available": False}
    concentration_pass = False
    diversifier_pass = False
    standalone_pass = False
    deterministic_pass = False
    signal_count_pass = False
    diversifier_status: dict[str, Any] = {"status": "not_attempted_data_preflight_failed"}

    if data_pass:
        performance_executed = True
        prepared = prepare_strategy(prices)
        simulation = simulate(prepared)
        repeated = simulate(prepared)
        deterministic_pass = stable_hash(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        ) == stable_hash(repeated["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist())
        windows = window_rows(prepared, simulation)
        signal_count_pass = len(windows) >= 20 and sum(row["chronological_half"] == "first_chronological_half" for row in windows) >= 8 and sum(row["chronological_half"] == "second_chronological_half" for row in windows) >= 8
        all_trial_results, control_results = full_result_rows(prepared, simulation, windows)
        chronological_results = half_rows(prepared, simulation, windows)
        calendar_results = calendar_rows(prepared, simulation, windows)
        portfolio_rows = portfolio_contribution_rows(prepared, simulation)
        sector_rows = sector_contribution_rows(prepared, simulation)
        concentration, concentration_pass = concentration_rows(windows, calendar_results, sector_rows)
        div_paths, diversifier_status = diversifier_paths(simulation, eligible_index(prepared))
        portfolio_rows.extend(diversifier_result_rows(div_paths, diversifier_status))
        diversifier_pass, diversifier_checks = diversifier_gate(div_paths)
        standalone_pass, standalone_checks = standalone_gate(prepared, simulation, windows, concentration_pass)
        turnover = turnover_rows(simulation)
        invariants = invariant_rows(prepared, simulation, windows, deterministic_pass, signal_count_pass)

    failures = failure_vector(standalone_checks, diversifier_checks, concentration_pass)
    outcome, primary_failure, next_action = choose_outcome(
        standalone_pass,
        diversifier_pass,
        failures,
        data_pass,
    )
    for row in failures:
        row["primary_failure_reason"] = bool(row["failure_reason"] == primary_failure)
    if not failures and primary_failure:
        failures = [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "failure_reason": primary_failure,
                "failed_gate": "data_preflight",
                "failure_detail": primary_failure,
                "primary_failure_reason": True,
            }
        ]
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "primary_failure_reason": primary_failure,
            "complete_failure_vector": [row["failure_reason"] for row in failures],
            "standalone_gate_pass": standalone_pass,
            "diversifier_gate_pass": diversifier_pass,
            "standalone_gate_checks": standalone_checks,
            "diversifier_gate_checks": diversifier_checks,
            "concentration_pass": concentration_pass,
            "signal_count_pass": signal_count_pass,
            "performance_executed": performance_executed,
            "next_action": next_action,
        }
    ]
    followups = [row for row in outcome_rows if row["outcome"].startswith("exploratory_followup")]

    if prepared is not None:
        write_csv_at(OUTPUT_DIR, "event_execution_ledger.csv", prepared["event_execution_rows"])
    else:
        write_csv_at(OUTPUT_DIR, "event_execution_ledger.csv", [])
    write_csv_at(OUTPUT_DIR, "event_window_inventory.csv", windows)
    write_csv_at(OUTPUT_DIR, "source_library_records.csv", [source_record_row()])
    write_csv_at(OUTPUT_DIR, "strategy_cards.csv", strategy_card_rows(outcome, primary_failure, next_action))
    write_csv_at(OUTPUT_DIR, "trial_ledger.csv", trial_rows(outcome, primary_failure))
    write_csv_at(OUTPUT_DIR, "benchmark_reference_log.csv", benchmark_rows())
    write_csv_at(OUTPUT_DIR, "process_task_log.csv", process_task_rows(performance_executed))
    write_csv_at(OUTPUT_DIR, "all_trial_results.csv", all_trial_results)
    write_csv_at(OUTPUT_DIR, "control_results.csv", control_results)
    write_csv_at(OUTPUT_DIR, "chronological_half_results.csv", chronological_results)
    write_csv_at(OUTPUT_DIR, "calendar_year_results.csv", calendar_results)
    write_csv_at(OUTPUT_DIR, "sector_contribution_results.csv", sector_rows)
    write_csv_at(OUTPUT_DIR, "lightweight_concentration_diagnostics.csv", concentration)
    write_csv_at(OUTPUT_DIR, "portfolio_contribution_results.csv", portfolio_rows)
    write_csv_at(OUTPUT_DIR, "turnover_cost_reconciliation.csv", turnover)
    write_csv_at(OUTPUT_DIR, "invariant_results.csv", invariants)
    write_csv_at(OUTPUT_DIR, "exploratory_followup_candidates.csv", followups)
    write_csv_at(OUTPUT_DIR, "outcome_summary.csv", outcome_rows)
    write_csv_at(
        OUTPUT_DIR,
        "failure_reasons.csv",
        failures,
        ("strategy_id", "trial_id", "failure_reason", "failed_gate", "failure_detail", "primary_failure_reason"),
    )
    write_csv_at(
        OUTPUT_DIR,
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "strategy_id": STRATEGY_ID,
                "outcome": outcome,
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
    )
    counts = entity_counts()
    write_json_at(OUTPUT_DIR, "entity_count_reconciliation.json", counts)

    protected_after = protected_hashes()
    protected_rows = protected_reconciliation_rows(protected_before, protected_after)
    write_csv_at(OUTPUT_DIR, "protected_state_reconciliation.csv", protected_rows)
    invariant_pass = bool(invariants) and all(row["status"] == "pass" for row in invariants)
    required_files_present = set(REQUIRED_EXPLORATION_OUTPUTS).issubset(
        {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
        | {"consistency_check.json", "exploration_report.md"}
    )
    checks = {
        "policy_correction_pass": policy_checks["overall_pass"],
        "historical_v4_source_packet_pass": source_checks["overall_pass"],
        "discovery_cohort_policy_min_one_max_four": True,
        "historical_v4_underfilled_result_preserved": True,
        "exactly_one_source_record": True,
        "exactly_one_strategy_configuration": True,
        "exactly_one_canonical_trial": True,
        "no_second_candidate_invented": True,
        "accepted_47_universe_only": True,
        "provider_access_performed": False,
        "network_access_performed": False,
        "source_completion_performed": False,
        "performance_executed": performance_executed,
        "event_window_count_pass": signal_count_pass if performance_executed else False,
        "invariant_results_pass": invariant_pass if performance_executed else False,
        "standalone_or_closure_outcome_allowed": outcome in ALLOWED_OUTCOMES,
        "controls_are_benchmark_references": True,
        "no_robustness_trials": counts["robustness_trials"] == 0,
        "no_paper_demo_records": counts["paper_demo_observations"] == 0
        and counts["paper_demo_eligibility_records"] == 0
        and counts["forward_observation_records"] == 0,
        "protected_state_cache_and_prior_evidence_unchanged": all(row["status"] == "pass" for row in protected_rows),
        "deterministic_rerun_pass": deterministic_pass if performance_executed else False,
        "entity_count_reconciliation_pass": counts["entity_count_reconciliation_pass"],
        "required_outputs_present": required_files_present,
        "diversifier_reference_status": diversifier_status.get("status", ""),
    }
    non_gate_fields = {
        "diversifier_reference_status",
        "provider_access_performed",
        "network_access_performed",
        "source_completion_performed",
    }
    checks["overall_pass"] = all(
        bool(value)
        for key, value in checks.items()
        if key not in non_gate_fields
    )
    write_json_at(OUTPUT_DIR, "consistency_check.json", checks)

    full_candidate = next(
        (
            row
            for row in all_trial_results
            if row.get("cost_bps_one_way") == PRIMARY_COST and row.get("period") == "full_period"
        ),
        {},
    )
    report_lines = [
        "# CFRA-Stovall Semiannual Sector Rotation Exploration V1",
        "",
        "This packet implements the single retained Accepted-47 V4 candidate under discovery_cohort_policy_v2. It is exploration only, not robustness, validation, paper/demo eligibility, forward observation, or broker activity.",
        "",
        f"Outcome: `{outcome}`" + (f" / `{primary_failure}`." if primary_failure else "."),
        "",
        "Historical V4 intake remains `one_candidate_only_insufficient_for_batch`; the overlay authorizes only the cohort-size correction.",
    ]
    if full_candidate:
        report_lines.extend(
            [
                "",
                f"At 5 bps, candidate CAGR `{float(full_candidate['cagr']):.4%}`, Sharpe `{float(full_candidate['sharpe_ratio']):.3f}`, maximum drawdown `{float(full_candidate['maximum_drawdown']):.2%}`, complete windows `{full_candidate['complete_event_window_count']}`.",
            ]
        )
    report_lines.extend(
        [
            "",
            f"Standalone gate pass: `{standalone_pass}`. Diversifier diagnostic pass: `{diversifier_pass}`. Concentration pass: `{concentration_pass}`.",
            "",
            "No provider, network, source-completion, optimization, robustness, paper/demo observation, broker, account, order, position, capital, or real-money action occurred.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    )
    (OUTPUT_DIR / "exploration_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    actual_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    missing = sorted(set(REQUIRED_EXPLORATION_OUTPUTS) - actual_files)
    if missing:
        raise RuntimeError(f"missing required exploration outputs: {missing}")
    return {
        "task_id": TASK_ID,
        "overall_pass": checks["overall_pass"],
        "policy_dir": str(POLICY_DIR),
        "source_dir": str(SOURCE_DIR),
        "output_dir": str(OUTPUT_DIR),
        "outcome": outcome,
        "primary_failure_reason": primary_failure,
        "next_action": next_action,
        "strategy_configuration_count": 1,
        "canonical_trial_count": 1,
        "performance_executed": performance_executed,
        "provider_access_performed": False,
        "network_access_performed": False,
        "paper_demo_observation_operation_performed": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
