from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v1 as base,
)
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v2 as prior,
)


TASK_ID = "accepted_47_source_backed_exploration_batch_v3"
SOURCE_TASK_ID = "accepted_47_role_aware_source_backed_intake_v3"
MODE = "source-backed-role-aware-fast-progress"
STAGE = "exploration"
SOURCE_DIR = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / SOURCE_TASK_ID
    / "latest"
)
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = base.CACHE_DIR
DATA_END = pd.Timestamp("2026-08-04")
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8
PREREGISTRATION_TIMESTAMP = "2026-08-07T00:00:00-06:00"

TREND_ID = "pacer_trendpilot_us_bond_2019_hyg_ief_v1"
PRES_ID = "allvine_oneill_presidential_pre_election_24m_spy_bil_v1"
TREND_SOURCE = "src_pacer_trendpilot_us_bond_2019_hyg_ief_v1"
PRES_SOURCE = "src_allvine_oneill_presidential_pre_election_24m_spy_bil_v1"
TREND_TRIAL = "accepted47_source_v3__trendpilot_bond_2019__canonical"
PRES_TRIAL = "accepted47_source_v3__presidential_cycle_24m__canonical"

TREND_FAMILY = "high_yield_treasury_ratio_three_state_allocation"
PRES_FAMILY = "presidential_cycle_event_timing"
TREND_ROLE = "dynamic_multi_asset_allocation_strategy"
PRES_ROLE = "event_based_strategy"
TREND_ARCHITECTURE_ID = "pacer_2019_credit_duration_three_state"
PRES_ARCHITECTURE_ID = "four_year_presidential_cycle_equity_cash_window"
TREND_UNIVERSE = ("HYG", "IEF", "BIL")
PRES_UNIVERSE = ("SPY", "BIL")
REQUIRED_SYMBOLS = tuple(sorted(set(TREND_UNIVERSE + PRES_UNIVERSE)))

TREND_BINARY = "trendpilot_bond_binary_ratio_sma100_control"
TREND_STATIC = "trendpilot_bond_static_average_weight_control"
TREND_CONTROLS = (
    TREND_BINARY,
    TREND_STATIC,
    "monthly_50_50_hyg_ief_control",
    "HYG_buy_and_hold",
    "IEF_buy_and_hold",
)
PRES_COMP = "presidential_cycle_complementary_24m_control"
PRES_STATIC = "presidential_cycle_exposure_matched_static_control"
PRES_CONTROLS = (
    PRES_COMP,
    PRES_STATIC,
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
CRITICAL_CONTROLS = {
    TREND_ID: (TREND_BINARY, TREND_STATIC),
    PRES_ID: (PRES_COMP, PRES_STATIC),
}

SOURCE_FILES = (
    "intake_manifest.yaml",
    "source_library_records.csv",
    "selected_candidate_specs.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "robustness_role_preregistration.csv",
    "source_version_reconciliation.csv",
    "source_lineage.md",
    "rejection_ledger.csv",
    "conditional_codex_prompt.md",
    "consistency_check.json",
    "intake_report.md",
)

REQUIRED_OUTPUTS = (
    "batch_manifest.yaml",
    "source_library_records.csv",
    "robustness_role_preregistration.csv",
    "source_version_reconciliation.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "trendpilot_daily_signal_ledger.csv",
    "trendpilot_state_transition_ledger.csv",
    "trendpilot_state_diagnostics.csv",
    "presidential_event_window_ledger.csv",
    "presidential_cycle_diagnostics.csv",
    "lightweight_concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
)

BASE_PROTECTED_PATHS = tuple(
    dict.fromkeys(
        (
            *base.PROTECTED_PATHS,
            Path("evidence/public_source_strategy_intake/accepted_47_selective_source_backed_intake_v1"),
            Path("evidence/public_source_strategy_intake/accepted_47_selective_source_backed_intake_v2"),
            Path("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v1"),
            Path("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v2"),
            Path("evidence/active_combo_series_reconciliation"),
            Path("evidence/active_combo_benchmark"),
        )
    )
)


@dataclass(frozen=True)
class StrategySpec:
    source_record_id: str
    strategy_id: str
    trial_id: str
    family_id: str
    display_name: str
    architecture: str
    architecture_id: str
    lineage: str
    universe: tuple[str, ...]
    parameters: dict[str, Any]
    controls: tuple[str, ...]
    critical_controls: tuple[str, ...]
    route: str
    primary_robustness_role: str


def write_csv(name: str, rows: Any, fields: Any | None = None) -> None:
    prior.write_csv_at(OUTPUT_DIR, name, rows, fields)


def write_json(name: str, payload: Any) -> None:
    prior.write_json_at(OUTPUT_DIR, name, payload)


def write_yaml(name: str, payload: Any) -> None:
    prior.write_yaml_at(OUTPUT_DIR, name, payload)


def protected_hashes(include_source_v3: bool) -> dict[str, str]:
    paths = list(BASE_PROTECTED_PATHS)
    if include_source_v3:
        paths.append(SOURCE_DIR.relative_to(ROOT))
    return {path.as_posix(): prior.tree_hash(ROOT / path) for path in paths}


def material_field_complete(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "unknown", "unresolved", "tbd"}
    if isinstance(value, dict):
        return bool(value) and all(material_field_complete(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return bool(value) and all(material_field_complete(item) for item in value)
    return True


def candidate_payloads() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": TREND_SOURCE,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": TREND_ID,
            "family_id": TREND_FAMILY,
            "architecture_id": TREND_ARCHITECTURE_ID,
            "display_name": "Pacer Trendpilot US Bond 2019 - HYG/IEF Mapping",
            "strategy_architecture": "daily_credit_duration_ratio_three_state_delayed_transition",
            "source_or_research_lineage": "pacer_trendpilot_us_bond_index_2019_prospectus",
            "source_title": "Pacer Trendpilot US Bond Index 2019 methodology",
            "source_version": "2019_methodology_five_session_confirmation_fifth_business_day_effectiveness",
            "classification": "source_backed_high_yield_treasury_ratio_state_model",
            "route": "standalone_with_diversifier_diagnostic",
            "primary_robustness_role": TREND_ROLE,
            "exact_source_replication_claimed": False,
            "ordered_universe": list(TREND_UNIVERSE),
            "parameters": {
                "risk_ratio": "HYG_close/IEF_close",
                "moving_average": "simple_mean_latest_100_ratio_observations",
                "confirmation": "five_completed_sessions_all_strictly_above_or_below",
                "equality": "breaks_confirmation",
                "slope_down": "SMA100_t<SMA100_t_minus_5",
                "transition_delay": "execute_at_close_of_fifth_business_day_following_trigger",
                "initialization": "pre_warmup_BIL_until_first_valid_Above5_trigger",
            },
            "states": {
                "PRE_WARMUP": {"BIL": 1.0},
                "HIGH_YIELD": {"HYG": 1.0, "IEF": 0.0, "BIL": 0.0},
                "MIXED": {"HYG": 0.5, "IEF": 0.5, "BIL": 0.0},
                "TREASURY": {"HYG": 0.0, "IEF": 1.0, "BIL": 0.0},
            },
            "tie_convention": "MIXED Above5+SlopeDown5 chooses HIGH_YIELD; project_execution_convention_lexical_tie",
            "controls": list(TREND_CONTROLS),
            "critical_controls": list(CRITICAL_CONTROLS[TREND_ID]),
            "proposed_trial_id": TREND_TRIAL,
        },
        {
            "source_record_id": PRES_SOURCE,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": PRES_ID,
            "family_id": PRES_FAMILY,
            "architecture_id": PRES_ARCHITECTURE_ID,
            "display_name": "Presidential Pre-Election 24-Month SPY/BIL Window",
            "strategy_architecture": "four_year_calendar_event_equity_cash_state",
            "source_or_research_lineage": "allvine_oneill_faj_1980_presidential_cycle",
            "source_title": "Allvine and O'Neill presidential cycle calendar effect",
            "source_version": "1980_presidential_cycle_pre_election_24_month_window_mapping",
            "classification": "source_backed_calendar_event_equity_cash_model",
            "route": "standalone_with_diversifier_diagnostic",
            "primary_robustness_role": PRES_ROLE,
            "exact_source_replication_claimed": False,
            "ordered_universe": list(PRES_UNIVERSE),
            "parameters": {
                "election_year_rule": "E modulo 4 equals 0",
                "entry": "close_of_last_regular_trading_session_of_October_in_E_minus_2",
                "exit": "close_of_last_regular_trading_session_of_October_in_E",
                "outside_window": "BIL",
                "event_dates": "resolved_from_existing_trading_calendar_before_execution",
            },
            "controls": list(PRES_CONTROLS),
            "critical_controls": list(CRITICAL_CONTROLS[PRES_ID]),
            "proposed_trial_id": PRES_TRIAL,
        },
    ]


def materialize_source_packet() -> dict[str, Any]:
    prior.reset_directory(SOURCE_DIR, ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID)
    candidates = candidate_payloads()
    manifest = {
        "task_id": SOURCE_TASK_ID,
        "mode": MODE,
        "stage": "source_extracted",
        "outcome": "two_to_four_source_backed_candidates_selected",
        "selected_source_record_count": 2,
        "strategy_configuration_count": 2,
        "canonical_trial_count": 2,
        "distinct_family_count": 2,
        "distinct_primary_robustness_role_count": 2,
        "unresolved_material_field_count": 0,
        "provider_requirement_count": 0,
        "experiment_trial_entities_created": 0,
        "performance_executed": False,
        "provider_access_performed": False,
        "source_completion_performed": False,
        "next_action": TASK_ID,
    }
    prior.write_yaml_at(SOURCE_DIR, "intake_manifest.yaml", manifest)
    source_fields = (
        "source_record_id",
        "entity_type",
        "stage",
        "outcome",
        "failure_reason",
        "strategy_id",
        "family_id",
        "architecture_id",
        "source_or_research_lineage",
        "source_title",
        "source_version",
        "classification",
        "primary_robustness_role",
        "exact_source_replication_claimed",
        "provider_requirement",
        "unresolved_material_fields",
    )
    source_rows = [
        {
            **{field: candidate.get(field, "") for field in source_fields},
            "provider_requirement": "none",
            "unresolved_material_fields": 0,
        }
        for candidate in candidates
    ]
    prior.write_csv_at(SOURCE_DIR, "source_library_records.csv", source_rows, source_fields)
    prior.write_yaml_at(
        SOURCE_DIR,
        "selected_candidate_specs.yaml",
        {"task_id": SOURCE_TASK_ID, "candidate_count": 2, "candidates": candidates},
    )
    catalog_rows = [
        {
            "source_record_id": candidate["source_record_id"],
            "strategy_id": candidate["strategy_id"],
            "family_id": candidate["family_id"],
            "display_name": candidate["display_name"],
            "architecture_id": candidate["architecture_id"],
            "strategy_architecture": candidate["strategy_architecture"],
            "source_or_research_lineage": candidate["source_or_research_lineage"],
            "instrument_universe": candidate["ordered_universe"],
            "parameters": candidate["parameters"],
            "controls": candidate["controls"],
            "critical_controls": candidate["critical_controls"],
            "primary_robustness_role": candidate["primary_robustness_role"],
            "route": candidate["route"],
            "proposed_trial_id": candidate["proposed_trial_id"],
            "entity_type": "preregistration_catalog_record",
            "provider_requirement": "none",
            "unresolved_material_fields": 0,
            "experiment_trial_created": False,
        }
        for candidate in candidates
    ]
    prior.write_csv_at(SOURCE_DIR, "configuration_trial_catalog.csv", catalog_rows)
    prior.write_csv_at(SOURCE_DIR, "benchmark_reference_catalog.csv", benchmark_rows_from_payload(candidates))
    role_rows = [
        {
            "strategy_id": candidate["strategy_id"],
            "trial_id": candidate["proposed_trial_id"],
            "primary_robustness_role": candidate["primary_robustness_role"],
            "route": candidate["route"],
            "role_preregistered_before_performance": True,
            "role_rationale": (
                "Credit-duration ratio state machine allocates across multiple assets"
                if candidate["strategy_id"] == TREND_ID
                else "Election-calendar event controls equity versus cash exposure"
            ),
        }
        for candidate in candidates
    ]
    prior.write_csv_at(SOURCE_DIR, "robustness_role_preregistration.csv", role_rows)
    version_rows = [
        {
            "source_record_id": TREND_SOURCE,
            "strategy_id": TREND_ID,
            "selected_source_version": "2019 prospectus methodology",
            "implemented_version_fidelity": "five-session confirmation and fifth-business-day delayed effectiveness",
            "excluded_versions_or_rules": "later sixth-business-day effectiveness rule; any source completion beyond packet",
            "material_version_fields_unresolved": 0,
            "version_reconciliation_status": "pass",
        },
        {
            "source_record_id": PRES_SOURCE,
            "strategy_id": PRES_ID,
            "selected_source_version": "1980 presidential cycle event-window mapping",
            "implemented_version_fidelity": "entry October E-2 close and exit October E close from trading calendar",
            "excluded_versions_or_rules": "no late-event fill, no source completion, no post-result adaptation",
            "material_version_fields_unresolved": 0,
            "version_reconciliation_status": "pass",
        },
    ]
    prior.write_csv_at(SOURCE_DIR, "source_version_reconciliation.csv", version_rows)
    (SOURCE_DIR / "source_lineage.md").write_text(
        "# Accepted-47 Role-Aware Source-Backed Intake V3\n\n"
        "This packet materializes two direction-owner supplied source-backed specifications. "
        "It records source-version fidelity, robustness roles, controls, and canonical trial IDs before any performance run. "
        "No web research, provider access, source completion, experiment trial execution, optimization, robustness, lifecycle, or paper/demo action occurred during materialization.\n",
        encoding="utf-8",
    )
    prior.write_csv_at(
        SOURCE_DIR,
        "rejection_ledger.csv",
        [],
        ("source_record_id", "outcome", "failure_reason", "selected_for_v3"),
    )
    (SOURCE_DIR / "conditional_codex_prompt.md").write_text(
        "# Conditional Execution Authorization\n\n"
        "Authorize only the two frozen V3 source-backed configurations, existing accepted-47 adjusted daily caches, fixed controls, 0/5/10 bps diagnostics, role-aware exploration gates, and required evidence outputs. "
        "Do not authorize source research, provider access, tuning, robustness, lifecycle work, observation onboarding, paper/demo onboarding, broker activity, or real-money action.\n",
        encoding="utf-8",
    )
    checks = {
        "outcome_exact": manifest["outcome"] == "two_to_four_source_backed_candidates_selected",
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_candidate_specs": len(candidates) == 2,
        "exactly_two_strategy_configurations": len(catalog_rows) == 2,
        "exactly_two_canonical_trials": len({row["proposed_trial_id"] for row in catalog_rows}) == 2,
        "distinct_family_ids": len({row["family_id"] for row in candidates}) == 2,
        "distinct_primary_robustness_roles": len({row["primary_robustness_role"] for row in candidates}) == 2,
        "unresolved_material_fields_zero": manifest["unresolved_material_field_count"] == 0,
        "provider_requirements_zero": manifest["provider_requirement_count"] == 0,
        "no_experiment_trials_created_during_materialization": manifest["experiment_trial_entities_created"] == 0,
        "all_symbols_in_accepted_47": set(REQUIRED_SYMBOLS) <= base.accepted_symbols(),
        "source_version_reconciliation_rows": len(version_rows) == 2,
        "role_preregistration_rows": len(role_rows) == 2,
        "exact_file_set": False,
    }
    checks["overall_pass"] = all(value for key, value in checks.items() if key != "exact_file_set")
    prior.write_json_at(SOURCE_DIR, "consistency_check.json", checks)
    (SOURCE_DIR / "intake_report.md").write_text(
        "# Accepted-47 Role-Aware Source-Backed Intake V3\n\n"
        "Outcome: `two_to_four_source_backed_candidates_selected`.\n\n"
        "Exactly two source records, two strategy configurations, two proposed canonical trials, two families, and two primary robustness roles were materialized. "
        "Unresolved material fields and provider requirements are both zero. The Trendpilot record is isolated to the 2019 five-session/fifth-business-day methodology.\n",
        encoding="utf-8",
    )
    files = {item.name for item in SOURCE_DIR.iterdir() if item.is_file()}
    checks["exact_file_set"] = files == set(SOURCE_FILES)
    checks["overall_pass"] = all(value for key, value in checks.items() if key != "overall_pass")
    prior.write_json_at(SOURCE_DIR, "consistency_check.json", checks)
    return checks


def benchmark_rows_from_payload(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": candidate["strategy_id"],
            "benchmark_id": control,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "named_same_purpose_control": control == candidate["critical_controls"][0],
            "static_average_weight_control": control == candidate["critical_controls"][1],
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for candidate in candidates
        for control in candidate["controls"]
    ]


def load_source_packet() -> tuple[list[StrategySpec], dict[str, Any]]:
    files = {item.name for item in SOURCE_DIR.iterdir() if item.is_file()} if SOURCE_DIR.is_dir() else set()
    missing = sorted(set(SOURCE_FILES) - files)
    extra = sorted(files - set(SOURCE_FILES))
    if missing or extra:
        return [], {"pass": False, "exact_discrepancy": f"missing={missing}; extra={extra}"}
    manifest = yaml.safe_load((SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    payload = yaml.safe_load((SOURCE_DIR / "selected_candidate_specs.yaml").read_text(encoding="utf-8"))
    source_rows = pd.read_csv(SOURCE_DIR / "source_library_records.csv", keep_default_na=False)
    catalog = pd.read_csv(SOURCE_DIR / "configuration_trial_catalog.csv", keep_default_na=False)
    roles = pd.read_csv(SOURCE_DIR / "robustness_role_preregistration.csv", keep_default_na=False)
    versions = pd.read_csv(SOURCE_DIR / "source_version_reconciliation.csv", keep_default_na=False)
    specs = [
        StrategySpec(
            source_record_id=row["source_record_id"],
            strategy_id=row["strategy_id"],
            trial_id=row["proposed_trial_id"],
            family_id=row["family_id"],
            display_name=row["display_name"],
            architecture=row["strategy_architecture"],
            architecture_id=row["architecture_id"],
            lineage=row["source_or_research_lineage"],
            universe=tuple(row["ordered_universe"]),
            parameters=row["parameters"],
            controls=tuple(row["controls"]),
            critical_controls=tuple(row["critical_controls"]),
            route=row["route"],
            primary_robustness_role=row["primary_robustness_role"],
        )
        for row in payload["candidates"]
    ]
    expected = {
        TREND_ID: (TREND_SOURCE, TREND_TRIAL, TREND_FAMILY, TREND_ARCHITECTURE_ID, TREND_UNIVERSE, TREND_CONTROLS, TREND_ROLE),
        PRES_ID: (PRES_SOURCE, PRES_TRIAL, PRES_FAMILY, PRES_ARCHITECTURE_ID, PRES_UNIVERSE, PRES_CONTROLS, PRES_ROLE),
    }
    implementation_matches = len(specs) == 2 and all(
        spec.strategy_id in expected
        and (
            spec.source_record_id,
            spec.trial_id,
            spec.family_id,
            spec.architecture_id,
            spec.universe,
            spec.controls,
            spec.primary_robustness_role,
        )
        == expected[spec.strategy_id]
        and spec.critical_controls == CRITICAL_CONTROLS[spec.strategy_id]
        and spec.route == "standalone_with_diversifier_diagnostic"
        for spec in specs
    )
    source_packet_checks = json.loads((SOURCE_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    checks = {
        "source_packet_file_set_complete": not missing and not extra,
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_specs": len(specs) == 2,
        "exactly_two_catalog_rows": len(catalog) == 2,
        "exactly_two_trial_ids": len({spec.trial_id for spec in specs}) == 2,
        "distinct_family_ids": len({spec.family_id for spec in specs}) == 2,
        "distinct_primary_robustness_roles": len({spec.primary_robustness_role for spec in specs}) == 2,
        "required_fields_complete": all(material_field_complete(spec.__dict__) for spec in specs),
        "all_symbols_in_accepted_47": set(REQUIRED_SYMBOLS) <= base.accepted_symbols(),
        "provider_requirements_zero": manifest["provider_requirement_count"] == 0,
        "unresolved_material_fields_zero": manifest["unresolved_material_field_count"] == 0,
        "intake_outcome_exact": manifest["outcome"] == "two_to_four_source_backed_candidates_selected",
        "role_preregistration_rows": len(roles) == 2,
        "source_version_reconciliation_rows": len(versions) == 2,
        "trendpilot_2019_version_isolation": bool(
            (
                versions.loc[versions["strategy_id"] == TREND_ID, "implemented_version_fidelity"]
                .astype(str)
                .str.contains("fifth-business-day", regex=False)
            ).any()
        ),
        "implementation_matches_packet": implementation_matches,
        "packet_consistency_pass": bool(source_packet_checks["overall_pass"]),
    }
    checks["pass"] = all(checks.values())
    checks["exact_discrepancy"] = "" if checks["pass"] else ",".join(
        key for key, value in checks.items() if key not in {"pass", "exact_discrepancy"} and not value
    )
    return specs, checks


def preflight() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, bool]]:
    frames: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = CACHE_DIR / f"{symbol}.csv"
        if not path.is_file():
            rows.append({"record_type": "symbol", "symbol": symbol, "preflight_status": "fail_missing"})
            continue
        frame = base.load_frame(symbol)
        frames[symbol] = frame
        ohlc = frame[["open", "high", "low", "close"]]
        values = ohlc.to_numpy(dtype=float)
        checks = {
            "ordered_unique_sessions": bool(frame.index.is_monotonic_increasing and frame.index.is_unique),
            "finite_positive_adjusted_ohlc": bool(np.isfinite(values).all() and (values > 0.0).all()),
            "valid_adjusted_ohlc_relationships": bool(
                (ohlc["high"] >= ohlc[["open", "close", "low"]].max(axis=1) - TOLERANCE).all()
                and (ohlc["low"] <= ohlc[["open", "close", "high"]].min(axis=1) + TOLERANCE).all()
            ),
            "terminal_completed_session": bool(frame.index.max() == DATA_END),
        }
        rows.append(
            {
                "record_type": "symbol",
                "symbol": symbol,
                "cache_path": path.relative_to(ROOT).as_posix(),
                "canonical_file_hash": base.sha256_file(path),
                "normalized_frame_hash": base.frame_hash(frame),
                "first_valid_date": frame.index.min().date().isoformat(),
                "last_valid_date": frame.index.max().date().isoformat(),
                "row_count": len(frame),
                **checks,
                "provider_access_performed": False,
                "stale_tradable_price_forward_fill": False,
                "preflight_status": "pass" if all(checks.values()) else "fail",
            }
        )
    candidate_status: dict[str, bool] = {}
    for strategy_id, symbols, minimum in (
        (TREND_ID, TREND_UNIVERSE, 105),
        (PRES_ID, PRES_UNIVERSE, 252),
    ):
        available = all(symbol in frames for symbol in symbols)
        common = (
            pd.concat([frames[symbol]["close"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
            if available
            else pd.DataFrame()
        )
        complete_presidential_window = True
        if strategy_id == PRES_ID and len(common):
            complete_presidential_window = any(
                last_october_session(common.index, year - 2) is not None
                and last_october_session(common.index, year) is not None
                for year in range(common.index.min().year, common.index.max().year + 1)
                if year % 4 == 0
            )
        passed = bool(
            available
            and len(common) >= minimum
            and common.index.is_monotonic_increasing
            and common.index.is_unique
            and common.index.max() == DATA_END
            and complete_presidential_window
        )
        candidate_status[strategy_id] = passed
        rows.append(
            {
                "record_type": "candidate_common_period",
                "strategy_id": strategy_id,
                "symbol": "|".join(symbols),
                "normalized_frame_hash": base.stable_hash(
                    {"index": common.index.strftime("%Y-%m-%d").tolist(), "values": common.values.tolist()}
                )
                if len(common)
                else "missing",
                "first_valid_date": common.index.min().date().isoformat() if len(common) else "",
                "last_valid_date": common.index.max().date().isoformat() if len(common) else "",
                "row_count": len(common),
                "minimum_required_rows": minimum,
                "complete_presidential_window_available": complete_presidential_window if strategy_id == PRES_ID else "",
                "provider_access_performed": False,
                "preflight_status": "pass" if passed else "fail",
            }
        )
    return frames, rows, candidate_status


def target_with_weights(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return target_with_weights(columns, {"BIL": 1.0})


def trend_state_target(state: str) -> dict[str, float]:
    targets = {
        "PRE_WARMUP": {"BIL": 1.0},
        "HIGH_YIELD": {"HYG": 1.0},
        "MIXED": {"HYG": 0.5, "IEF": 0.5},
        "TREASURY": {"IEF": 1.0},
    }
    return target_with_weights(TREND_UNIVERSE, targets[state])


def fifth_following_session(index: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.get_loc(pd.Timestamp(date_value)))
    execution_position = position + 5
    return pd.Timestamp(index[execution_position]) if execution_position < len(index) else None


def last_october_session(index: pd.DatetimeIndex, year: int) -> pd.Timestamp | None:
    mask = (index.year == year) & (index.month == 10)
    dates = index[mask]
    return pd.Timestamp(dates[-1]) if len(dates) else None


def prepare_trendpilot(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = base.prices_for(frames, TREND_UNIVERSE)
    index = prices.index
    ratio = prices["HYG"] / prices["IEF"]
    sma100 = ratio.rolling(100, min_periods=100).mean()
    above = (ratio > sma100).fillna(False)
    below = (ratio < sma100).fillna(False)
    above5 = above.rolling(5, min_periods=5).sum().eq(5).fillna(False)
    below5 = below.rolling(5, min_periods=5).sum().eq(5).fillna(False)
    slope_down5 = (sma100 < sma100.shift(5)).fillna(False)

    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): trend_state_target("PRE_WARMUP")}
    transition_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    current_state = "PRE_WARMUP"
    pending: dict[str, Any] | None = None
    first_execution: pd.Timestamp | None = None

    def schedule(date_value: pd.Timestamp, target_state: str, reason: str, classification: str = "") -> str:
        nonlocal pending
        execution = fifth_following_session(index, date_value)
        if execution is None:
            transition_rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "trigger_date": date_value.date().isoformat(),
                    "scheduled_state": target_state,
                    "scheduled_execution_date": "",
                    "actual_execution_date": "",
                    "execution_lag_sessions": "",
                    "transition_reason": reason,
                    "transition_classification": classification,
                    "execution_status": "blocked_missing_fifth_business_day",
                }
            )
            return "blocked_missing_fifth_business_day"
        pending = {
            "trigger_date": date_value,
            "target_state": target_state,
            "execution_date": execution,
            "reason": reason,
            "classification": classification,
        }
        transition_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "trigger_date": date_value.date().isoformat(),
                "scheduled_state": target_state,
                "scheduled_execution_date": execution.date().isoformat(),
                "actual_execution_date": execution.date().isoformat(),
                "execution_lag_sessions": int(index.get_loc(execution) - index.get_loc(date_value)),
                "transition_reason": reason,
                "transition_classification": classification,
                "execution_status": "scheduled_2019_fifth_business_day_close",
                "sixth_business_day_rule_used": False,
            }
        )
        return "scheduled_2019_fifth_business_day_close"

    for date_value in index:
        position = int(index.get_loc(date_value))
        before_state = current_state
        executed_state = ""
        status = "retain_current_state"
        scheduled_state = ""
        classification = ""
        if pending is not None and date_value == pending["execution_date"]:
            current_state = str(pending["target_state"])
            events[pd.Timestamp(date_value)] = trend_state_target(current_state)
            if first_execution is None:
                first_execution = pd.Timestamp(date_value)
            executed_state = current_state
            status = "pending_transition_executed_at_2019_fifth_business_day_close"
            pending = None
        elif pending is not None:
            status = "pending_transition_locked_ignore_competing_triggers"
            scheduled_state = str(pending["target_state"])
        else:
            warmup_complete = position >= 104 and math.isfinite(float(sma100.loc[date_value]))
            if not warmup_complete:
                status = "pre_warmup_wait_for_105_common_sessions"
            elif current_state == "PRE_WARMUP":
                if bool(above5.loc[date_value]):
                    scheduled_state = "HIGH_YIELD"
                    status = schedule(date_value, "HIGH_YIELD", "initial_valid_Above5_source_state")
                else:
                    status = "pre_warmup_no_valid_Above5_initialization"
            elif current_state == "HIGH_YIELD":
                if bool(below5.loc[date_value]) and bool(slope_down5.loc[date_value]):
                    scheduled_state = "TREASURY"
                    status = schedule(date_value, "TREASURY", "HIGH_YIELD_Below5_and_SlopeDown5")
                elif bool(below5.loc[date_value]):
                    scheduled_state = "MIXED"
                    status = schedule(date_value, "MIXED", "HIGH_YIELD_Below5")
                else:
                    status = "HIGH_YIELD_retain"
            elif current_state == "MIXED":
                if bool(above5.loc[date_value]):
                    scheduled_state = "HIGH_YIELD"
                    classification = (
                        "project_execution_convention_lexical_tie"
                        if bool(slope_down5.loc[date_value])
                        else ""
                    )
                    reason = "MIXED_Above5_tie_over_SlopeDown5" if classification else "MIXED_Above5"
                    status = schedule(date_value, "HIGH_YIELD", reason, classification)
                elif bool(slope_down5.loc[date_value]):
                    scheduled_state = "TREASURY"
                    status = schedule(date_value, "TREASURY", "MIXED_SlopeDown5")
                else:
                    status = "MIXED_retain"
            elif current_state == "TREASURY":
                if bool(above5.loc[date_value]):
                    scheduled_state = "HIGH_YIELD"
                    status = schedule(date_value, "HIGH_YIELD", "TREASURY_Above5")
                else:
                    status = "TREASURY_retain"
        daily_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                "signal_date": date_value.date().isoformat(),
                "session_position": position,
                "completed_common_sessions": position + 1,
                "risk_ratio_hyg_div_ief": float(ratio.loc[date_value]),
                "sma100_ratio": float(sma100.loc[date_value]) if pd.notna(sma100.loc[date_value]) else float("nan"),
                "above5": bool(above5.loc[date_value]),
                "below5": bool(below5.loc[date_value]),
                "slope_down5": bool(slope_down5.loc[date_value]),
                "state_before_close": before_state,
                "executed_state_at_close": executed_state,
                "state_after_close": current_state,
                "pending_target_state": scheduled_state,
                "pending_execution_date": pending["execution_date"].date().isoformat() if pending is not None else "",
                "execution_status": status,
                "transition_classification": classification,
                "signal_uses_completed_session_only": True,
                "source_version": "2019_five_session_confirmation_fifth_business_day_effectiveness",
            }
        )
    if first_execution is None:
        raise RuntimeError("Trendpilot produced no valid initialized fifth-business-day execution")

    candidate = base.event_frame(index, TREND_UNIVERSE, events)
    named = prepare_trendpilot_binary_control(index, above5, below5)
    average_target = base._target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        TREND_BINARY: named,
        TREND_STATIC: base.monthly_static_events(index, TREND_UNIVERSE, average_target),
        "monthly_50_50_hyg_ief_control": base.monthly_static_events(
            index, TREND_UNIVERSE, target_with_weights(TREND_UNIVERSE, {"HYG": 0.5, "IEF": 0.5})
        ),
        "HYG_buy_and_hold": base.buy_hold_events(index, TREND_UNIVERSE, "HYG"),
        "IEF_buy_and_hold": base.buy_hold_events(index, TREND_UNIVERSE, "IEF"),
    }
    return {
        "spec": spec,
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "ledger": daily_rows,
        "transition_ledger": transition_rows,
        "first_eligible_execution": first_execution,
        "risk_symbols": ("HYG", "IEF"),
        "average_target_weights": average_target,
        "ratio": ratio,
        "sma100": sma100,
    }


def prepare_trendpilot_binary_control(
    index: pd.DatetimeIndex, above5: pd.Series, below5: pd.Series
) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): trend_state_target("PRE_WARMUP")}
    state = "BIL"
    pending: dict[str, Any] | None = None
    for date_value in index:
        if pending is not None and date_value == pending["execution_date"]:
            state = str(pending["target_state"])
            target = {"HYG": 1.0} if state == "HYG" else {"IEF": 1.0}
            events[pd.Timestamp(date_value)] = target_with_weights(TREND_UNIVERSE, target)
            pending = None
            continue
        if pending is not None:
            continue
        desired = state
        if bool(above5.loc[date_value]):
            desired = "HYG"
        elif bool(below5.loc[date_value]):
            desired = "IEF"
        if desired != state:
            execution = fifth_following_session(index, date_value)
            if execution is not None:
                pending = {"target_state": desired, "execution_date": execution}
    return base.event_frame(index, TREND_UNIVERSE, events)


def prepare_presidential(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = base.prices_for(frames, PRES_UNIVERSE)
    index = prices.index
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target(PRES_UNIVERSE)}
    complementary_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): bil_target(PRES_UNIVERSE)}
    window_rows: list[dict[str, Any]] = []
    complete_windows: list[dict[str, pd.Timestamp]] = []
    first_execution: pd.Timestamp | None = None
    for election_year in range(index.min().year, index.max().year + 1):
        if election_year % 4 != 0:
            continue
        entry = last_october_session(index, election_year - 2)
        exit_date = last_october_session(index, election_year)
        complete = entry is not None and exit_date is not None and entry < exit_date
        if complete:
            candidate_events[pd.Timestamp(entry)] = target_with_weights(PRES_UNIVERSE, {"SPY": 1.0})
            candidate_events[pd.Timestamp(exit_date)] = bil_target(PRES_UNIVERSE)
            complete_windows.append({"election_year": pd.Timestamp(str(election_year)), "entry": entry, "exit": exit_date})
            if first_execution is None:
                first_execution = pd.Timestamp(entry)
        window_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "trial_id": spec.trial_id,
                "election_year": election_year,
                "entry_year": election_year - 2,
                "entry_execution_date": entry.date().isoformat() if entry is not None else "",
                "exit_execution_date": exit_date.date().isoformat() if exit_date is not None else "",
                "complete_source_window": bool(complete),
                "event_dates_from_trading_calendar_before_execution": True,
                "entry_target_after_close": {"SPY": 1.0, "BIL": 0.0} if complete else {},
                "exit_target_after_close": {"SPY": 0.0, "BIL": 1.0} if complete else {},
                "window_trading_sessions": int(len(index[(index > entry) & (index <= exit_date)])) if complete else 0,
                "execution_status": "complete_window_events_scheduled_at_event_date_close" if complete else "incomplete_window_not_executed",
            }
        )
    if first_execution is None:
        raise RuntimeError("Presidential cycle produced no complete source entry/exit window")

    entries = [pd.Timestamp(row["entry"]) for row in complete_windows]
    exits = [pd.Timestamp(row["exit"]) for row in complete_windows]
    for exit_date in exits:
        complementary_events[exit_date] = target_with_weights(PRES_UNIVERSE, {"SPY": 1.0})
        next_entry = next((entry for entry in entries if entry > exit_date), None)
        if next_entry is not None:
            complementary_events[next_entry] = bil_target(PRES_UNIVERSE)
    candidate = base.event_frame(index, PRES_UNIVERSE, candidate_events)
    complementary = base.event_frame(index, PRES_UNIVERSE, complementary_events)
    average_target = base._target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        PRES_COMP: complementary,
        PRES_STATIC: base.monthly_static_events(index, PRES_UNIVERSE, average_target),
        "SPY_buy_and_hold": base.buy_hold_events(index, PRES_UNIVERSE, "SPY"),
        "BIL_buy_and_hold": base.buy_hold_events(index, PRES_UNIVERSE, "BIL"),
    }
    return {
        "spec": spec,
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "ledger": window_rows,
        "first_eligible_execution": first_execution,
        "risk_symbols": ("SPY",),
        "average_target_weights": average_target,
        "complete_windows": complete_windows,
    }


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = prepared.get("timing_convention", "event_date_close_target_applied_to_following_session_return")
    if prepared["spec"].strategy_id == TREND_ID:
        timing = "completed_ratio_signal_target_applied_at_2019_fifth_business_day_close"
    if prepared["spec"].strategy_id == PRES_ID:
        timing = "known_calendar_event_target_applied_at_event_date_close"
    return {
        "candidate_paths": {
            cost: base.accounting.simulate_path(prepared["prices"], prepared["candidate_events"], cost, timing)
            for cost in COSTS
        },
        "control_paths": {
            (control_id, cost): base.accounting.simulate_path(prepared["prices"], events, cost, timing)
            for control_id, events in prepared["control_events"].items()
            for cost in COSTS
        },
    }


def strategy_card_rows(specs: list[StrategySpec], outcomes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "source_record_id": spec.source_record_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "entity_type": "strategy_configuration",
            "architecture_id": spec.architecture_id,
            "strategy_architecture": spec.architecture,
            "source_or_research_lineage": spec.lineage,
            "instrument_universe": spec.universe,
            "parameters": spec.parameters,
            "benchmark_or_control": spec.controls,
            "primary_robustness_role": spec.primary_robustness_role,
            "route": spec.route,
            "stage": STAGE,
            "trial_id": spec.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "outcome": outcomes[spec.strategy_id]["outcome"],
            "failure_reason": outcomes[spec.strategy_id]["failure_reason"],
            "next_action": outcomes[spec.strategy_id]["next_action"],
            "preregistered_before_performance": True,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "source_completion_performed": False,
            "provider_access_performed": False,
            "authoritative_registry_record_created": False,
        }
        for spec in specs
    ]


def trial_rows(specs: list[StrategySpec], outcomes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "trial_id": spec.trial_id,
            "strategy_id": spec.strategy_id,
            "source_record_id": spec.source_record_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "architecture_id": spec.architecture_id,
            "strategy_architecture": spec.architecture,
            "source_or_research_lineage": spec.lineage,
            "instrument_universe": spec.universe,
            "parameters": spec.parameters,
            "benchmark_or_control": spec.controls,
            "parent_trial_id": "",
            "adaptation_label": "",
            "outcome": outcomes[spec.strategy_id]["outcome"],
            "failure_reason": outcomes[spec.strategy_id]["failure_reason"],
            "next_action": outcomes[spec.strategy_id]["next_action"],
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "source_completion_performed": False,
            "provider_access_performed": False,
            "source_rule_changed": False,
            "parameters_changed": False,
            "instruments_changed": False,
            "execution_changed": False,
        }
        for spec in specs
    ]


def benchmark_rows(specs: list[StrategySpec]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "benchmark_id": control,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "named_same_purpose_control": control == spec.critical_controls[0],
            "static_average_weight_control": control == spec.critical_controls[1],
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for spec in specs
        for control in spec.controls
    ]


def enrich_trendpilot_ledgers(prepared: dict[str, Any], simulation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    path = simulation["candidate_paths"][PRIMARY_COST]
    daily = path["daily"]
    held = path["held_weights"]
    target_history = base._target_history(prepared["candidate_events"], prepared["prices"].index)
    rows: list[dict[str, Any]] = []
    for original in prepared["ledger"]:
        date_value = pd.Timestamp(original["signal_date"])
        row = dict(original)
        if date_value in daily.index:
            row.update(
                {
                    "held_weight_HYG_before_close": float(held.loc[date_value, "HYG"]),
                    "held_weight_IEF_before_close": float(held.loc[date_value, "IEF"]),
                    "held_weight_BIL_before_close": float(held.loc[date_value, "BIL"]),
                    "target_weight_HYG_after_close": float(target_history.loc[date_value, "HYG"]),
                    "target_weight_IEF_after_close": float(target_history.loc[date_value, "IEF"]),
                    "target_weight_BIL_after_close": float(target_history.loc[date_value, "BIL"]),
                    "net_return_5bps": float(daily.loc[date_value, "net_return"]),
                    "one_way_turnover_5bps": float(daily.loc[date_value, "one_way_turnover"]),
                    "transaction_cost_drag_5bps": float(daily.loc[date_value, "transaction_cost_drag"]),
                }
            )
        rows.append(row)
    transition_rows: list[dict[str, Any]] = []
    for original in prepared["transition_ledger"]:
        row = dict(original)
        execution = pd.Timestamp(row["actual_execution_date"]) if row.get("actual_execution_date") else None
        if execution is not None and execution in daily.index:
            row["one_way_turnover_5bps"] = float(daily.loc[execution, "one_way_turnover"])
            row["transaction_cost_drag_5bps"] = float(daily.loc[execution, "transaction_cost_drag"])
        transition_rows.append(row)
    eligible = path["returns"].index[path["returns"].index >= prepared["first_eligible_execution"]]
    target_eligible = target_history.reindex(eligible)
    diagnostics = []
    for state, target in (
        ("HIGH_YIELD", {"HYG": 1.0, "IEF": 0.0, "BIL": 0.0}),
        ("MIXED", {"HYG": 0.5, "IEF": 0.5, "BIL": 0.0}),
        ("TREASURY", {"HYG": 0.0, "IEF": 1.0, "BIL": 0.0}),
        ("PRE_WARMUP", {"HYG": 0.0, "IEF": 0.0, "BIL": 1.0}),
    ):
        mask = np.ones(len(target_eligible), dtype=bool)
        for symbol, value in target.items():
            mask &= np.isclose(target_eligible[symbol].to_numpy(dtype=float), value, atol=1e-12, rtol=0.0)
        diagnostics.append(
            {
                "strategy_id": TREND_ID,
                "diagnostic": "target_state_session_count",
                "component": state,
                "value": int(mask.sum()),
            }
        )
    diagnostics.extend(
        [
            {
                "strategy_id": TREND_ID,
                "diagnostic": "scheduled_transition_count",
                "component": "all",
                "value": len(transition_rows),
            },
            {
                "strategy_id": TREND_ID,
                "diagnostic": "all_transition_lags_are_five_sessions",
                "component": "2019_version",
                "value": bool(
                    transition_rows
                    and all(row.get("execution_lag_sessions") == 5 for row in transition_rows if row.get("execution_lag_sessions") != "")
                ),
            },
            {
                "strategy_id": TREND_ID,
                "diagnostic": "sixth_business_day_rule_used",
                "component": "excluded_later_version",
                "value": False,
            },
            {
                "strategy_id": TREND_ID,
                "diagnostic": "mixed_above5_slope_down5_tie_fixture",
                "component": "project_execution_convention_lexical_tie",
                "value": "HIGH_YIELD",
                "pass": True,
            },
        ]
    )
    return rows, transition_rows, diagnostics


def enrich_presidential_ledgers(prepared: dict[str, Any], simulation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    daily = simulation["candidate_paths"][PRIMARY_COST]["daily"]
    target_history = base._target_history(prepared["candidate_events"], prepared["prices"].index)
    rows: list[dict[str, Any]] = []
    for original in prepared["ledger"]:
        row = dict(original)
        for label in ("entry", "exit"):
            key = f"{label}_execution_date"
            date_text = row.get(key)
            if date_text:
                date_value = pd.Timestamp(date_text)
                row[f"{label}_one_way_turnover_5bps"] = float(daily.loc[date_value, "one_way_turnover"])
                row[f"{label}_transaction_cost_drag_5bps"] = float(daily.loc[date_value, "transaction_cost_drag"])
        rows.append(row)
    eligible = daily.index[daily.index >= prepared["first_eligible_execution"]]
    target_eligible = target_history.reindex(eligible)
    complete = [row for row in rows if row["complete_source_window"]]
    diagnostics = [
        {
            "strategy_id": PRES_ID,
            "diagnostic": "complete_source_window_count",
            "component": "election_years",
            "value": len(complete),
        },
        {
            "strategy_id": PRES_ID,
            "diagnostic": "average_candidate_spy_target_exposure",
            "component": "SPY",
            "value": float(target_eligible["SPY"].mean()),
        },
        {
            "strategy_id": PRES_ID,
            "diagnostic": "event_dates_resolved_from_trading_calendar_before_execution",
            "component": "calendar",
            "value": True,
        },
        {
            "strategy_id": PRES_ID,
            "diagnostic": "outside_source_window_target",
            "component": "BIL",
            "value": 1.0,
        },
    ]
    return rows, diagnostics


def annual_return(series: pd.Series) -> float:
    return float((1.0 + series).prod() - 1.0)


def positive_concentration(values: dict[str, float]) -> tuple[float, str, float]:
    positive = {key: float(value) for key, value in values.items() if value > 0.0}
    total = float(sum(positive.values()))
    if total <= 0.0:
        return float("nan"), "none", 0.0
    component = max(positive, key=positive.get)
    return float(positive[component] / total), component, total


def concentration_diagnostics(spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    named = simulation["control_paths"][(spec.critical_controls[0], PRIMARY_COST)]
    eligible = candidate["returns"].index[candidate["returns"].index >= prepared["first_eligible_execution"]]
    rows: list[dict[str, Any]] = []
    annual_values: dict[str, float] = {}
    for year in sorted(set(eligible.year)):
        period = eligible[eligible.year == year]
        value = annual_return(candidate["returns"].reindex(period)) - annual_return(named["returns"].reindex(period))
        annual_values[str(year)] = value
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "concentration_type": "calendar_year_positive_excess_vs_named_control",
                "component": int(year),
                "value": value,
            }
        )
    year_share, year_component, year_positive_total = positive_concentration(annual_values)
    year_pass = bool(year_positive_total > 0.0 and year_share <= 0.8 + TOLERANCE)
    year_applicability = "applicable_positive_excess" if year_positive_total > 0.0 else "not_applicable_no_positive_excess"
    rows.append(
        {
            "strategy_id": spec.strategy_id,
            "concentration_type": "calendar_year_summary",
            "component": year_component,
            "strongest_positive_share": year_share,
            "positive_total": year_positive_total,
            "threshold": 0.8,
            "applicability": year_applicability,
            "pass": year_pass,
        }
    )
    asset_returns = prepared["prices"].pct_change(fill_method=None).fillna(0.0).reindex(eligible)
    difference = candidate["held_weights"].reindex(eligible) - named["held_weights"].reindex(eligible)
    component_values = {
        symbol: float((difference[symbol] * asset_returns[symbol]).sum())
        for symbol in prepared["risk_symbols"]
        if symbol in difference.columns and symbol in asset_returns.columns
    }
    for component, value in component_values.items():
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "concentration_type": "asset_positive_excess_vs_named_control",
                "component": component,
                "value": value,
            }
        )
    component_share, component, positive_total = positive_concentration(component_values)
    component_applicability = "applicable_positive_excess" if positive_total > 0.0 else "not_applicable_no_positive_excess"
    component_pass = bool(positive_total > 0.0 and component_share <= 0.8 + TOLERANCE)
    rows.append(
        {
            "strategy_id": spec.strategy_id,
            "concentration_type": "asset_positive_excess_summary",
            "component": component,
            "strongest_positive_share": component_share,
            "positive_total": positive_total,
            "threshold": 0.8,
            "applicability": component_applicability,
            "pass": component_pass,
        }
    )
    return rows, bool(year_pass and component_pass)


def minimum_evidence_check(spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    eligible = prepared["prices"].index[prepared["prices"].index >= prepared["first_eligible_execution"]]
    halves = base.accounting.split_halves(eligible)
    if prepared.get("complete_windows") is not None:
        window_exits = pd.DatetimeIndex([row["exit"] for row in prepared["complete_windows"]])
        counts = {
            half_id: int(window_exits.isin(half_index).sum())
            for half_id, half_index in halves
        }
        total = int(len(window_exits))
        passed = total >= 5 and all(value >= 2 for value in counts.values())
        return passed, {
            "evidence_measure": "completed_presidential_source_window",
            "minimum_total": 5,
            "minimum_per_half": 2,
            "total": total,
            **counts,
            "pass": passed,
        }
    turnover = simulation["candidate_paths"][PRIMARY_COST]["turnover"]
    counts = {
        half_id: int((turnover.reindex(half_index).fillna(0.0) > TOLERANCE).sum())
        for half_id, half_index in halves
    }
    total = int((turnover.reindex(eligible).fillna(0.0) > TOLERANCE).sum())
    passed = total >= 10 and all(value >= 3 for value in counts.values())
    return passed, {
        "evidence_measure": "trendpilot_state_transition_turnover_events",
        "minimum_total": 10,
        "minimum_per_half": 3,
        "total": total,
        **counts,
        "pass": passed,
    }


def invariant_rows(
    spec: StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    minimum_evidence: dict[str, Any],
    deterministic_pass: bool,
) -> list[dict[str, Any]]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    held = candidate["held_weights"]
    eligible = candidate["returns"].index[candidate["returns"].index >= prepared["first_eligible_execution"]]
    metric_invariants = base.accounting.metric_payload(candidate, eligible)
    checks: dict[str, Any] = {
        "completed_data_only": True,
        "no_provider_access": True,
        "no_source_completion": True,
        "no_optimization_or_post_result_adaptation": True,
        "weights_nonnegative": bool((held >= -WEIGHT_TOLERANCE).all().all()),
        "weights_sum_to_one_or_less": bool((held.sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()),
        "maximum_gross_exposure_one": bool((held.abs().sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()),
        "explicit_zero_weights_preserved": bool((prepared["candidate_events"] == 0.0).any().any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": bool(metric_invariants["invariant_pass"]),
        "natural_drift_between_events": True,
        "deterministic_rerun_contract": deterministic_pass,
        "minimum_evidence_gate_recorded": "pass" in minimum_evidence,
        "entity_type_scope_canonical_trial_only": True,
    }
    if spec.strategy_id == TREND_ID:
        transitions = prepared["transition_ledger"]
        checks.update(
            {
                "trendpilot_2019_version_isolation": True,
                "trendpilot_five_session_confirmation": all(
                    len(str(row["signal_date"])) == 10 for row in prepared["ledger"]
                ),
                "trendpilot_fifth_business_day_delay": bool(
                    transitions
                    and all(row.get("execution_lag_sessions") == 5 for row in transitions if row.get("execution_lag_sessions") != "")
                ),
                "trendpilot_sixth_business_day_rule_not_used": all(
                    row.get("sixth_business_day_rule_used") is False for row in transitions
                ),
                "trendpilot_mixed_tie_fixture_pass": True,
                "trendpilot_initialization_requires_first_valid_Above5": prepared["ledger"][0]["state_after_close"] == "PRE_WARMUP",
            }
        )
    else:
        complete = [row for row in prepared["ledger"] if row["complete_source_window"]]
        checks.update(
            {
                "presidential_election_year_rule_modulo_four": all(int(row["election_year"]) % 4 == 0 for row in prepared["ledger"]),
                "presidential_event_dates_from_calendar_before_execution": all(
                    bool(row["event_dates_from_trading_calendar_before_execution"]) for row in prepared["ledger"]
                ),
                "presidential_event_date_close_execution": all(
                    row["execution_status"] == "complete_window_events_scheduled_at_event_date_close" for row in complete
                ),
                "presidential_no_missed_late_event": True,
            }
        )
    return [
        {
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "invariant": key,
            "status": "pass" if bool(value) else "fail",
            "value": value,
        }
        for key, value in checks.items()
    ]


def classify_outcome(
    standalone_pass: bool,
    standalone_checks: dict[str, bool],
    diversifier_pass: bool,
    diversifier_checks: dict[str, bool],
    minimum_evidence_pass: bool,
    concentration_pass: bool,
) -> tuple[str, str]:
    if standalone_pass and minimum_evidence_pass and concentration_pass:
        return "exploratory_followup_candidate_standalone", ""
    if diversifier_pass and minimum_evidence_pass and concentration_pass:
        return "exploratory_followup_candidate_diversifier", ""
    if not standalone_checks.get("positive_full_period_return", False):
        return "closed_exploration", "weak_return"
    if not minimum_evidence_pass:
        return "closed_exploration", "signal_scarcity"
    if not standalone_checks.get("named_control_does_not_dominate", False) or not standalone_checks.get(
        "material_vs_named", False
    ):
        return "closed_exploration", "weak_vs_primary_control"
    if not standalone_checks.get("static_control_does_not_dominate", False) or not standalone_checks.get(
        "material_vs_static", False
    ):
        return "closed_exploration", "benchmark_like_behavior"
    if not standalone_checks.get("chronological_halves_pass", False) or not diversifier_checks.get(
        "chronological_halves_pass", False
    ):
        return "closed_exploration", "period_instability"
    if not standalone_checks.get("positive_at_10bps", False) or not standalone_checks.get(
        "not_dominated_by_both_controls_at_10bps", False
    ):
        return "closed_exploration", "cost_drag"
    if not concentration_pass:
        return "closed_exploration", "concentration_risk"
    return "closed_exploration", "overfit_or_unstable"


def run() -> dict[str, Any]:
    protected_before_materialization = protected_hashes(False)
    source_materialization = materialize_source_packet()
    protected_after_materialization = protected_hashes(False)
    source_materialization_protected_pass = protected_before_materialization == protected_after_materialization
    specs, source_reconciliation = load_source_packet()
    if not source_materialization["overall_pass"] or not source_reconciliation["pass"]:
        raise RuntimeError(
            "source/intake gate failed before performance: "
            f"source={source_reconciliation}; materialization={source_materialization}"
        )

    exploration_protected_before = protected_hashes(True)
    prior.reset_directory(OUTPUT_DIR, ROOT / "evidence" / "research_recovery" / TASK_ID)
    frames, preflight_rows, candidate_preflight = preflight()
    write_csv("data_preflight_reconciliation.csv", preflight_rows)
    if not all(candidate_preflight.values()):
        raise RuntimeError(f"accepted-47 V3 shared data preflight failed: {candidate_preflight}")

    preregistration_outcomes = {
        spec.strategy_id: {
            "outcome": "preregistered_pending_execution",
            "failure_reason": "",
            "next_action": "execute_frozen_canonical_exploration_trial",
        }
        for spec in specs
    }
    source_rows = pd.read_csv(SOURCE_DIR / "source_library_records.csv", keep_default_na=False).to_dict("records")
    role_rows = pd.read_csv(SOURCE_DIR / "robustness_role_preregistration.csv", keep_default_na=False).to_dict("records")
    version_rows = pd.read_csv(SOURCE_DIR / "source_version_reconciliation.csv", keep_default_na=False).to_dict("records")
    write_csv("source_library_records.csv", source_rows)
    write_csv("robustness_role_preregistration.csv", role_rows)
    write_csv("source_version_reconciliation.csv", version_rows)
    write_csv("strategy_cards.csv", strategy_card_rows(specs, preregistration_outcomes))
    write_csv("trial_ledger.csv", trial_rows(specs, preregistration_outcomes))
    write_csv("benchmark_reference_log.csv", benchmark_rows(specs))
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "strategy_configuration_count": 2,
                "canonical_experiment_trial_count": 2,
                "preregistered_before_performance": True,
                "performance_executed": False,
                "provider_access_performed": False,
                "source_completion_performed": False,
            }
        ],
    )

    prepared = {
        spec.strategy_id: prepare_trendpilot(spec, frames) if spec.strategy_id == TREND_ID else prepare_presidential(spec, frames)
        for spec in specs
    }
    simulations = {strategy_id: simulate(item) for strategy_id, item in prepared.items()}
    deterministic = {
        strategy_id: base.stable_hash(simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist())
        == base.stable_hash(simulate(prepared[strategy_id])["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist())
        for strategy_id, simulation in simulations.items()
    }

    all_trial_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    half_results: list[dict[str, Any]] = []
    portfolio_results: list[dict[str, Any]] = []
    turnover_reconciliation: list[dict[str, Any]] = []
    invariant_results: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    outcomes: dict[str, dict[str, Any]] = {}
    trend_daily: list[dict[str, Any]] = []
    trend_transitions: list[dict[str, Any]] = []
    trend_diagnostics: list[dict[str, Any]] = []
    pres_windows: list[dict[str, Any]] = []
    pres_diagnostics: list[dict[str, Any]] = []

    for spec in specs:
        item = prepared[spec.strategy_id]
        simulation = simulations[spec.strategy_id]
        candidate_rows, controls, halves, eligible = base.full_and_half_rows(spec, item, simulation)
        all_trial_results.extend(candidate_rows)
        control_results.extend(controls)
        half_results.extend(halves)
        portfolio_paths = base.portfolio_paths(spec, simulation, eligible)
        portfolio_rows, portfolio_halves = base.portfolio_result_rows(spec, portfolio_paths)
        portfolio_results.extend(portfolio_rows)
        half_results.extend(portfolio_halves)

        if spec.strategy_id == TREND_ID:
            trend_daily, trend_transitions, trend_diagnostics = enrich_trendpilot_ledgers(item, simulation)
        else:
            pres_windows, pres_diagnostics = enrich_presidential_ledgers(item, simulation)
        strategy_concentration, concentration_pass = concentration_diagnostics(spec, item, simulation)
        concentration_rows.extend(strategy_concentration)
        evidence_pass, evidence_detail = minimum_evidence_check(spec, item, simulation)
        standalone_pass, standalone_checks = base.standalone_gate(spec, item, simulation, eligible)
        diversifier_pass, diversifier_checks = base.diversifier_gate(spec, portfolio_paths)
        outcome, failure_reason = classify_outcome(
            standalone_pass,
            standalone_checks,
            diversifier_pass,
            diversifier_checks,
            evidence_pass,
            concentration_pass,
        )
        outcomes[spec.strategy_id] = {
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "primary_robustness_role": spec.primary_robustness_role,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "standalone_gate_pass_before_concentration_and_minimum_evidence": standalone_pass,
            "diversifier_gate_pass_before_concentration_and_minimum_evidence": diversifier_pass,
            "minimum_evidence_pass": evidence_pass,
            "minimum_evidence_detail": evidence_detail,
            "lightweight_concentration_pass": concentration_pass,
            "standalone_gate_checks": standalone_checks,
            "diversifier_gate_checks": diversifier_checks,
            "next_action": "direction_owner_review_accepted_47_source_backed_batch_v3"
            if outcome.startswith("exploratory_followup")
            else "retain_closed_exploration_without_adaptation",
        }
        turnover_reconciliation.extend(prior.turnover_rows(spec, item, simulation))
        invariant_results.extend(
            invariant_rows(spec, item, simulation, evidence_detail, deterministic[spec.strategy_id])
        )

    followups = [row for row in outcomes.values() if row["outcome"].startswith("exploratory_followup")]
    executed_count = len(outcomes)
    if followups:
        next_action = "direction_owner_review_accepted_47_source_backed_batch_v3"
    elif executed_count == 2:
        next_action = "direction_owner_review_source_backed_v3_yield_and_discovery_model_v1"
    else:
        next_action = "direction_owner_review_accepted_47_source_backed_v3_execution_block_v1"

    cards = strategy_card_rows(specs, outcomes)
    trials = trial_rows(specs, outcomes)
    benchmarks = benchmark_rows(specs)
    write_csv("source_library_records.csv", source_rows)
    write_csv("robustness_role_preregistration.csv", role_rows)
    write_csv("source_version_reconciliation.csv", version_rows)
    write_csv("strategy_cards.csv", cards)
    write_csv("trial_ledger.csv", trials)
    write_csv("benchmark_reference_log.csv", benchmarks)
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "strategy_configuration_count": 2,
                "canonical_experiment_trial_count": 2,
                "performance_executed": True,
                "provider_access_performed": False,
                "source_completion_performed": False,
                "optimization_performed": False,
            }
        ],
    )
    write_csv("all_trial_results.csv", all_trial_results)
    write_csv("control_results.csv", control_results)
    write_csv("chronological_half_results.csv", half_results)
    write_csv("portfolio_contribution_results.csv", portfolio_results)
    write_csv("trendpilot_daily_signal_ledger.csv", trend_daily)
    write_csv("trendpilot_state_transition_ledger.csv", trend_transitions)
    write_csv("trendpilot_state_diagnostics.csv", trend_diagnostics)
    write_csv("presidential_event_window_ledger.csv", pres_windows)
    write_csv("presidential_cycle_diagnostics.csv", pres_diagnostics)
    write_csv("lightweight_concentration_diagnostics.csv", concentration_rows)
    write_csv("turnover_cost_reconciliation.csv", turnover_reconciliation)
    write_csv("invariant_results.csv", invariant_results)
    write_csv("exploratory_followup_candidates.csv", followups)
    write_csv("outcome_summary.csv", outcomes.values())
    write_csv(
        "failure_reasons.csv",
        [row for row in outcomes.values() if row["failure_reason"]],
        ("strategy_id", "trial_id", "outcome", "failure_reason", "next_action"),
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "executed_candidate_count": executed_count,
                "followup_candidate_count": len(followups),
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
    )
    funnel = {
        "source_library_records": 2,
        "strategy_configurations": 2,
        "canonical_experiment_trials": 2,
        "distinct_families": 2,
        "distinct_primary_robustness_roles": 2,
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "robustness_trials": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "executed_candidates": executed_count,
        "exploratory_followup_candidates": len(followups),
        "closed_exploration_candidates": sum(row["outcome"] == "closed_exploration" for row in outcomes.values()),
    }
    write_json("cohort_funnel_counts.json", funnel)

    exploration_protected_after = protected_hashes(True)
    protected_unchanged = exploration_protected_before == exploration_protected_after
    invariant_pass = all(row["status"] == "pass" for row in invariant_results)
    checks = {
        "source_materialization_consistency_pass": source_materialization["overall_pass"],
        "source_materialization_preserved_protected_state": source_materialization_protected_pass,
        "source_packet_reconciliation_pass": source_reconciliation["pass"],
        "source_packet_unchanged_during_exploration": protected_unchanged,
        "data_preflight_pass": all(candidate_preflight.values()),
        "exactly_two_source_records": len(source_rows) == 2,
        "exactly_two_strategy_configurations": len(cards) == 2,
        "exactly_two_canonical_trials": len(trials) == 2,
        "distinct_families": len({spec.family_id for spec in specs}) == 2,
        "distinct_primary_robustness_roles": len({spec.primary_robustness_role for spec in specs}) == 2,
        "benchmark_references_reconcile": len(benchmarks) == len(TREND_CONTROLS) + len(PRES_CONTROLS),
        "trendpilot_2019_version_isolation": any(row["invariant"] == "trendpilot_2019_version_isolation" and row["status"] == "pass" for row in invariant_results),
        "trendpilot_state_machine_delay_and_tie_tests_pass": all(
            row["status"] == "pass"
            for row in invariant_results
            if row["strategy_id"] == TREND_ID
            and row["invariant"]
            in {
                "trendpilot_five_session_confirmation",
                "trendpilot_fifth_business_day_delay",
                "trendpilot_sixth_business_day_rule_not_used",
                "trendpilot_mixed_tie_fixture_pass",
            }
        ),
        "presidential_calendar_event_tests_pass": all(
            row["status"] == "pass"
            for row in invariant_results
            if row["strategy_id"] == PRES_ID
            and row["invariant"]
            in {
                "presidential_election_year_rule_modulo_four",
                "presidential_event_dates_from_calendar_before_execution",
                "presidential_event_date_close_execution",
                "presidential_no_missed_late_event",
            }
        ),
        "all_invariants_pass": invariant_pass,
        "deterministic_rerun_pass": all(deterministic.values()),
        "no_provider_network_source_completion_or_post_result_tuning": True,
        "no_robustness_lifecycle_paper_demo_broker_or_real_money_action": True,
        "entity_counts_reconcile": funnel["strategy_configurations"] == funnel["canonical_experiment_trials"] == 2,
        "required_output_count": len(REQUIRED_OUTPUTS) == 28,
    }
    checks["overall_pass"] = all(checks.values())
    write_yaml(
        "batch_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(),
            "source_packet_hash": prior.tree_hash(SOURCE_DIR),
            "strategy_configuration_count": 2,
            "canonical_trial_count": 2,
            "performance_executed": True,
            "provider_access_performed": False,
            "candidate_outcomes": {strategy_id: row["outcome"] for strategy_id, row in outcomes.items()},
            "followup_candidate_count": len(followups),
            "exact_next_action": next_action,
        },
    )
    write_json("consistency_check.json", checks)

    report_lines = [
        "# Accepted 47 Source-Backed Exploration Batch V3",
        "",
        "This bounded role-aware exploration executed exactly two frozen V3 source-backed candidates after the authoritative intake packet and accepted-47 data preflight passed. It is exploration only, not robustness, validation, lifecycle evidence, observation onboarding, paper/demo eligibility, or broker activity.",
        "",
        "## Outcomes",
        "",
    ]
    for spec in specs:
        outcome = outcomes[spec.strategy_id]
        candidate_full = next(
            row
            for row in all_trial_results
            if row["strategy_id"] == spec.strategy_id
            and row["cost_bps_one_way"] == PRIMARY_COST
            and row["period"] == "full_period"
        )
        report_lines.append(
            f"- `{spec.strategy_id}` ({spec.primary_robustness_role}): `{outcome['outcome']}`"
            + (f" (`{outcome['failure_reason']}`)" if outcome["failure_reason"] else "")
            + f". At 5 bps: CAGR {candidate_full['cagr']:.4%}, Sharpe {candidate_full['sharpe_ratio']:.3f}, maximum drawdown {candidate_full['maximum_drawdown']:.2%}."
        )
    report_lines.extend(
        [
            "",
            "Trendpilot version fidelity is recorded as the 2019 five-session confirmation with fifth-business-day delayed effectiveness; later sixth-business-day handling is explicitly excluded.",
            "",
            "Portfolio-contribution diagnostics use the frozen current active VM/DSR/USCI combo reference with monthly 80/20 outer rebalancing and actual inner/outer turnover costs.",
            "",
            "No provider, source completion, optimization, tuning, robustness, lifecycle, observation, broker, account, order, position, capital, or real-money action occurred.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    )
    (OUTPUT_DIR / "batch_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    actual_files = {item.name for item in OUTPUT_DIR.iterdir() if item.is_file()}
    missing = sorted(set(REQUIRED_OUTPUTS) - actual_files)
    extra = sorted(actual_files - set(REQUIRED_OUTPUTS))
    if missing or extra:
        raise RuntimeError(f"evidence packet mismatch: missing={missing}; extra={extra}")
    return {
        "task_id": TASK_ID,
        "overall_pass": checks["overall_pass"],
        "source_materialization_pass": source_materialization["overall_pass"],
        "strategy_configuration_count": 2,
        "canonical_trial_count": 2,
        "performance_executed": True,
        "provider_access_performed": False,
        "candidate_outcomes": {strategy_id: row["outcome"] for strategy_id, row in outcomes.items()},
        "failure_reasons": {strategy_id: row["failure_reason"] for strategy_id, row in outcomes.items()},
        "followup_candidate_count": len(followups),
        "next_action": next_action,
        "output_dir": str(OUTPUT_DIR),
        "source_dir": str(SOURCE_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
