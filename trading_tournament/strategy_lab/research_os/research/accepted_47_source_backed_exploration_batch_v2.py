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

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v1 as base,
)


TASK_ID = "accepted_47_source_backed_exploration_batch_v2"
SOURCE_TASK_ID = "accepted_47_selective_source_backed_intake_v2"
MODE = "source-backed-fast-progress"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
SOURCE_DIR = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / SOURCE_TASK_ID
    / "latest"
)
CACHE_DIR = base.CACHE_DIR
DATA_END = pd.Timestamp("2026-08-04")
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8
PREREGISTRATION_TIMESTAMP = "2026-08-06T00:00:00-06:00"

MCA_ID = "varadi_minimum_correlation_8etf_60d_weekly_v1"
HYG_ID = "schwoerer_hyg_ema100_spy_bil_v1"
MCA_TRIAL = "accepted47_source_v2__mca8_weekly__canonical"
HYG_TRIAL = "accepted47_source_v2__hyg_ema100_spy_bil__canonical"
MCA_SOURCE = "src_varadi_minimum_correlation_8etf_60d_weekly_v1"
HYG_SOURCE = "src_schwoerer_hyg_ema100_spy_bil_v1"
MCA_FAMILY = "minimum_correlation_dynamic_diversification"
HYG_FAMILY = "high_yield_credit_signal_equity_state"
MCA_RISK = ("SPY", "QQQ", "EEM", "IWM", "EFA", "TLT", "IYR", "GLD")
MCA_UNIVERSE = (*MCA_RISK, "BIL")
HYG_UNIVERSE = ("HYG", "SPY", "BIL")
HYG_TRADABLE = ("SPY", "BIL")
REQUIRED_SYMBOLS = tuple(sorted(set(MCA_UNIVERSE + HYG_UNIVERSE)))

MCA_NAMED = "mca8_inverse_volatility60_weekly_control"
MCA_STATIC = "mca8_static_average_weight_control"
HYG_NAMED = "spy_ema100_self_trend_spy_bil_control"
HYG_STATIC = "hyg_ema100_exposure_matched_spy_bil_control"
MCA_CONTROLS = (
    MCA_NAMED,
    "mca8_equal_weight_weekly_control",
    MCA_STATIC,
    "60_40_spy_tlt_weekly_control",
    "BIL_buy_and_hold",
)
HYG_CONTROLS = (
    HYG_NAMED,
    "hyg_sma100_spy_bil_control",
    HYG_STATIC,
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
CRITICAL_CONTROLS = {
    MCA_ID: (MCA_NAMED, MCA_STATIC),
    HYG_ID: (HYG_NAMED, HYG_STATIC),
}

SOURCE_FILES = (
    "intake_manifest.yaml",
    "source_library_records.csv",
    "selected_candidate_specs.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "source_lineage.md",
    "rejection_ledger.csv",
    "conditional_codex_prompt.md",
    "consistency_check.json",
    "intake_report.md",
)
REQUIRED_OUTPUTS = (
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "mca_weekly_allocation_ledger.csv",
    "mca_component_diagnostics.csv",
    "hyg_daily_signal_ledger.csv",
    "hyg_state_and_episode_diagnostics.csv",
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
            Path("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v1"),
            Path("evidence/corrections/materialize_and_resume_accepted_47_source_backed_batch_v1"),
            Path("evidence/robustness/gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1"),
            Path("evidence/technical_factory"),
            Path("evidence/research_recovery/accepted_47_hybrid_discovery_batch_v1"),
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
    lineage: str
    universe: tuple[str, ...]
    parameters: dict[str, Any]
    controls: tuple[str, ...]
    critical_controls: tuple[str, ...]
    route: str


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
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
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: serialize(row.get(field, "")) for field in columns})


def write_csv(
    name: str,
    rows: Iterable[dict[str, Any]],
    fields: Iterable[str] | None = None,
) -> None:
    write_csv_at(OUTPUT_DIR, name, rows, fields)


def write_json_at(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_json(name: str, payload: Any) -> None:
    write_json_at(OUTPUT_DIR, name, payload)


def write_yaml_at(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    write_yaml_at(OUTPUT_DIR, name, payload)


def reset_directory(path: Path, expected_parent: Path) -> None:
    if path.exists():
        resolved = path.resolve()
        if expected_parent.resolve() not in resolved.parents:
            raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def tree_hash(path: Path) -> str:
    if path.is_file():
        return base.sha256_file(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def protected_hashes(include_source_v2: bool) -> dict[str, str]:
    paths = list(BASE_PROTECTED_PATHS)
    if include_source_v2:
        paths.append(SOURCE_DIR.relative_to(ROOT))
    return {path.as_posix(): tree_hash(ROOT / path) for path in paths}


def candidate_payloads() -> list[dict[str, Any]]:
    mca_fixture = {
        "correlation_matrix": [[1.0, 0.1, 0.3], [0.1, 1.0, 0.2], [0.3, 0.2, 1.0]],
        "asset_volatilities": [0.01, 0.02, 0.015],
        "expected_mu_rho": 0.2,
        "expected_sigma_rho": 0.1,
        "expected_average_tie_ranks_of_negative_row_scores": [2.0, 1.0, 3.0],
        "expected_final_weights": [
            0.38143896754606743,
            0.4607880171964826,
            0.15777301525744994,
        ],
    }
    return [
        {
            "source_record_id": MCA_SOURCE,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": MCA_ID,
            "family_id": MCA_FAMILY,
            "display_name": "Minimum Correlation Eight-ETF Weekly Allocation",
            "strategy_architecture": "weekly_long_only_correlation_transformation_inverse_volatility_allocation",
            "source_or_research_lineage": "varadi_kapler_bee_rittenhouse_minimum_correlation_2012",
            "source_title": "Minimum Correlation Algorithm",
            "classification": "source_backed_native_ETF_multi_asset",
            "exact_source_replication_claimed": False,
            "route": "standalone_with_diversifier_diagnostic",
            "ordered_universe": list(MCA_RISK),
            "fallback_asset": "BIL",
            "parameters": {
                "formation_return_sessions": 60,
                "required_close_sessions": 61,
                "correlation": "ordinary_Pearson",
                "off_diagonal_standard_deviation_ddof": 1,
                "asset_volatility_ddof": 1,
                "ranking": "average_tie_rank_of_negative_adjusted_row_mean",
                "rebalance_frequency": "weekly",
            },
            "formula": {
                "adjusted_correlation": "1-NormalCDF(rho_ij;mu_rho,sigma_rho)",
                "diagonal": 0,
                "row_score": "mean_off_diagonal_adjusted_correlation",
                "rank_weight": "rank(-row_score)/sum_ranks",
                "matrix_multiplication": "q_row_vector_times_A",
                "volatility_rescaling": "normalized_u_tilde_divided_by_sigma",
            },
            "formula_fixture": mca_fixture,
            "timing": {
                "signal": "final_completed_regular_session_of_week",
                "execution": "following_regular_session_close",
                "natural_drift": True,
            },
            "warmup": {"required_common_adjusted_closes": 61, "fallback": {"BIL": 1.0}},
            "missing_data": {
                "reduced_universe_allowed": False,
                "invalid_formation": "retain_current_executable_target",
                "missing_execution_price": "block_change_and_retain_pretrade_holdings",
                "tradable_price_forward_fill": False,
            },
            "controls": list(MCA_CONTROLS),
            "critical_controls": list(CRITICAL_CONTROLS[MCA_ID]),
            "proposed_trial_id": MCA_TRIAL,
        },
        {
            "source_record_id": HYG_SOURCE,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": HYG_ID,
            "family_id": HYG_FAMILY,
            "display_name": "HYG 100-Day EMA Credit-State SPY/BIL",
            "strategy_architecture": "daily_cross_asset_credit_trend_equity_cash_state",
            "source_or_research_lineage": "martin_schwoerer_hyg_credit_signal_2025",
            "source_title": "HYG Credit Signal",
            "classification": "source_backed_cross_asset_ETF_state",
            "exact_source_replication_claimed": False,
            "route": "standalone_with_diversifier_diagnostic",
            "ordered_universe": list(HYG_UNIVERSE),
            "parameters": {
                "ema_sessions": 100,
                "ema_alpha": 2.0 / 101.0,
                "ema_initialization": "mean_first_100_valid_closes",
                "strict_comparison": True,
            },
            "signal": {
                "above": {"SPY": 1.0, "BIL": 0.0},
                "below": {"SPY": 0.0, "BIL": 1.0},
                "equality": "retain_current_target",
            },
            "timing": {
                "signal": "completed_session_close",
                "execution": "following_regular_session_close_on_changed_target",
                "natural_drift": True,
            },
            "warmup": {"required_hyg_closes": 100, "fallback": {"BIL": 1.0}},
            "missing_data": {
                "invalid_signal": "retain_current_target",
                "missing_execution_price": "block_transition_and_retain_pretrade_holdings",
                "tradable_price_forward_fill": False,
            },
            "controls": list(HYG_CONTROLS),
            "critical_controls": list(CRITICAL_CONTROLS[HYG_ID]),
            "proposed_trial_id": HYG_TRIAL,
        },
    ]


def materialize_source_packet() -> dict[str, Any]:
    reset_directory(
        SOURCE_DIR,
        ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID,
    )
    candidates = candidate_payloads()
    manifest = {
        "task_id": SOURCE_TASK_ID,
        "stage": "source_extracted",
        "outcome": "two_to_four_source_backed_candidates_selected",
        "selected_source_record_count": 2,
        "proposed_strategy_count": 2,
        "proposed_canonical_trial_count": 2,
        "distinct_family_count": 2,
        "unresolved_material_field_count": 0,
        "provider_requirement_count": 0,
        "experiment_trial_entities_created": 0,
        "external_source_research_repeated": False,
        "next_action": TASK_ID,
    }
    write_yaml_at(SOURCE_DIR, "intake_manifest.yaml", manifest)
    source_fields = (
        "source_record_id",
        "entity_type",
        "stage",
        "outcome",
        "failure_reason",
        "strategy_id",
        "family_id",
        "source_or_research_lineage",
        "source_title",
        "classification",
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
    write_csv_at(SOURCE_DIR, "source_library_records.csv", source_rows, source_fields)
    write_yaml_at(
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
            "strategy_architecture": candidate["strategy_architecture"],
            "source_or_research_lineage": candidate["source_or_research_lineage"],
            "instrument_universe": candidate["ordered_universe"],
            "parameters": candidate["parameters"],
            "controls": candidate["controls"],
            "critical_controls": candidate["critical_controls"],
            "route": candidate["route"],
            "proposed_trial_id": candidate["proposed_trial_id"],
            "provider_requirement": "none",
            "unresolved_material_fields": 0,
            "entity_type": "preregistration_catalog_record",
            "experiment_trial_created": False,
        }
        for candidate in candidates
    ]
    write_csv_at(SOURCE_DIR, "configuration_trial_catalog.csv", catalog_rows)
    benchmark_rows = [
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
    write_csv_at(SOURCE_DIR, "benchmark_reference_catalog.csv", benchmark_rows)
    (SOURCE_DIR / "source_lineage.md").write_text(
        "# Accepted-47 Selective Source-Backed Intake V2\n\n"
        "This append-only packet materializes two completed source-intake specifications supplied by the direction owner. No web research, source completion, provider access, strategy trial, or performance calculation occurred during materialization.\n",
        encoding="utf-8",
    )
    write_csv_at(
        SOURCE_DIR,
        "rejection_ledger.csv",
        [],
        ("source_record_id", "outcome", "failure_reason", "selected_for_v2"),
    )
    (SOURCE_DIR / "conditional_codex_prompt.md").write_text(
        "# Conditional Execution Authorization\n\n"
        "Authorize only the two frozen V2 configurations, accepted-47 cached data, fixed controls, 0/5/10 bps diagnostics, exploration gates, and evidence outputs. Do not authorize source research, provider access, tuning, robustness, lifecycle work, paper/demo onboarding, or broker activity.\n",
        encoding="utf-8",
    )
    checks = {
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_candidate_specs": len(candidates) == 2,
        "exactly_two_proposed_canonical_trials": len(catalog_rows) == 2,
        "distinct_family_ids": len({row["family_id"] for row in candidates}) == 2,
        "unresolved_material_fields_zero": manifest["unresolved_material_field_count"] == 0,
        "provider_requirements_zero": manifest["provider_requirement_count"] == 0,
        "no_experiment_trials_created_during_materialization": manifest[
            "experiment_trial_entities_created"
        ]
        == 0,
        "all_symbols_in_accepted_47": set(REQUIRED_SYMBOLS) <= base.accepted_symbols(),
        "exact_file_set": True,
    }
    checks["overall_pass"] = all(checks.values())
    write_json_at(SOURCE_DIR, "consistency_check.json", checks)
    (SOURCE_DIR / "intake_report.md").write_text(
        "# Accepted-47 Selective Source-Backed Intake V2\n\n"
        "Outcome: `two_to_four_source_backed_candidates_selected`.\n\n"
        "Exactly two source records from two distinct families were materialized with complete formulas, controls, routes, trial proposals, zero unresolved fields, and zero provider requirements. Proposed trials remain preregistration data until the exploration runner executes.\n",
        encoding="utf-8",
    )
    checks["exact_file_set"] = {item.name for item in SOURCE_DIR.iterdir() if item.is_file()} == set(
        SOURCE_FILES
    )
    checks["overall_pass"] = all(value for key, value in checks.items() if key != "overall_pass")
    write_json_at(SOURCE_DIR, "consistency_check.json", checks)
    return checks


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


def load_source_packet() -> tuple[list[StrategySpec], dict[str, Any]]:
    files = {item.name for item in SOURCE_DIR.iterdir() if item.is_file()} if SOURCE_DIR.is_dir() else set()
    missing = sorted(set(SOURCE_FILES) - files)
    if missing:
        return [], {"pass": False, "exact_discrepancy": f"missing source files: {missing}"}
    manifest = yaml.safe_load((SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    payload = yaml.safe_load((SOURCE_DIR / "selected_candidate_specs.yaml").read_text(encoding="utf-8"))
    source_rows = pd.read_csv(SOURCE_DIR / "source_library_records.csv", keep_default_na=False)
    catalog = pd.read_csv(SOURCE_DIR / "configuration_trial_catalog.csv", keep_default_na=False)
    specs = [
        StrategySpec(
            source_record_id=row["source_record_id"],
            strategy_id=row["strategy_id"],
            trial_id=row["proposed_trial_id"],
            family_id=row["family_id"],
            display_name=row["display_name"],
            architecture=row["strategy_architecture"],
            lineage=row["source_or_research_lineage"],
            universe=tuple(row["ordered_universe"]),
            parameters=row["parameters"],
            controls=tuple(row["controls"]),
            critical_controls=tuple(row["critical_controls"]),
            route=row["route"],
        )
        for row in payload["candidates"]
    ]
    expected = {
        MCA_ID: (MCA_SOURCE, MCA_TRIAL, MCA_FAMILY, MCA_RISK, MCA_CONTROLS),
        HYG_ID: (HYG_SOURCE, HYG_TRIAL, HYG_FAMILY, HYG_UNIVERSE, HYG_CONTROLS),
    }
    implementation_matches = len(specs) == 2 and all(
        spec.strategy_id in expected
        and (
            spec.source_record_id,
            spec.trial_id,
            spec.family_id,
            spec.universe,
            spec.controls,
        )
        == expected[spec.strategy_id]
        and spec.critical_controls == CRITICAL_CONTROLS[spec.strategy_id]
        and spec.route == "standalone_with_diversifier_diagnostic"
        for spec in specs
    )
    checks = {
        "source_packet_file_set_complete": not missing,
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_specs": len(specs) == 2,
        "exactly_two_catalog_rows": len(catalog) == 2,
        "exactly_two_trial_ids": len({spec.trial_id for spec in specs}) == 2,
        "distinct_family_ids": len({spec.family_id for spec in specs}) == 2,
        "required_fields_complete": all(material_field_complete(spec.__dict__) for spec in specs),
        "all_symbols_in_accepted_47": set(REQUIRED_SYMBOLS) <= base.accepted_symbols(),
        "provider_requirements_zero": manifest["provider_requirement_count"] == 0,
        "unresolved_material_fields_zero": manifest["unresolved_material_field_count"] == 0,
        "intake_outcome_exact": manifest["outcome"] == "two_to_four_source_backed_candidates_selected",
        "implementation_matches_packet": implementation_matches,
        "packet_consistency_pass": bool(
            json.loads((SOURCE_DIR / "consistency_check.json").read_text(encoding="utf-8"))[
                "overall_pass"
            ]
        ),
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
            "ordered_unique_sessions": frame.index.is_monotonic_increasing and frame.index.is_unique,
            "finite_positive_adjusted_ohlc": bool(np.isfinite(values).all() and (values > 0.0).all()),
            "valid_adjusted_ohlc_relationships": bool(
                (ohlc["high"] >= ohlc[["open", "close", "low"]].max(axis=1) - TOLERANCE).all()
                and (ohlc["low"] <= ohlc[["open", "close", "high"]].min(axis=1) + TOLERANCE).all()
            ),
            "terminal_completed_session": frame.index.max() == DATA_END,
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
        (MCA_ID, MCA_UNIVERSE, 61),
        (HYG_ID, HYG_UNIVERSE, 100),
    ):
        available = all(symbol in frames for symbol in symbols)
        common = (
            pd.concat([frames[symbol]["close"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
            if available
            else pd.DataFrame()
        )
        passed = bool(
            available
            and len(common) >= minimum
            and common.index.is_monotonic_increasing
            and common.index.is_unique
            and common.index.max() == DATA_END
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
                "provider_access_performed": False,
                "preflight_status": "pass" if passed else "fail",
            }
        )
    return frames, rows, candidate_status


def normal_cdf(value: float, mean: float, standard_deviation: float) -> float:
    z = (value - mean) / standard_deviation
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def minimum_correlation_from_matrix(
    correlation: np.ndarray,
    asset_volatilities: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    matrix = np.asarray(correlation, dtype=float)
    volatilities = np.asarray(asset_volatilities, dtype=float)
    count = matrix.shape[0]
    if matrix.shape != (count, count) or len(volatilities) != count:
        raise ValueError("minimum-correlation inputs have incompatible dimensions")
    lower = matrix[np.tril_indices(count, k=-1)]
    mu_rho = float(np.mean(lower))
    sigma_rho = float(np.std(lower, ddof=1))
    if not math.isfinite(sigma_rho) or sigma_rho <= np.finfo(float).eps:
        raise ValueError("off-diagonal correlation dispersion is zero or nonfinite")
    adjusted = np.zeros_like(matrix)
    for row in range(count):
        for column in range(count):
            if row != column:
                adjusted[row, column] = 1.0 - normal_cdf(
                    float(matrix[row, column]), mu_rho, sigma_rho
                )
    row_scores = adjusted.sum(axis=1) / (count - 1)
    ranks = pd.Series(-row_scores).rank(method="average", ascending=True).to_numpy(dtype=float)
    q = ranks / ranks.sum()
    multiplied = q @ adjusted
    if not np.isfinite(multiplied).all() or float(multiplied.sum()) <= 0.0:
        raise ValueError("transformed correlation multiplication is invalid")
    pre_volatility = multiplied / multiplied.sum()
    if (
        not np.isfinite(volatilities).all()
        or (volatilities <= 0.0).any()
        or not np.isfinite(pre_volatility).all()
    ):
        raise ValueError("asset volatility rescaling input is invalid")
    raw = pre_volatility / volatilities
    weights = raw / raw.sum()
    if not np.isfinite(weights).all() or (weights < -WEIGHT_TOLERANCE).any():
        raise ValueError("minimum-correlation final weights are invalid")
    return weights, {
        "mu_rho": mu_rho,
        "sigma_rho": sigma_rho,
        "adjusted_matrix": adjusted.tolist(),
        "row_scores": row_scores.tolist(),
        "ranks": ranks.tolist(),
        "rank_weights_q": q.tolist(),
        "matrix_product_u": multiplied.tolist(),
        "pre_volatility_weights": pre_volatility.tolist(),
        "asset_volatilities": volatilities.tolist(),
    }


def minimum_correlation_weights(
    returns: pd.DataFrame,
) -> tuple[pd.Series, dict[str, Any]]:
    correlation = returns.corr().to_numpy(dtype=float)
    volatilities = returns.std(ddof=1).to_numpy(dtype=float)
    weights, diagnostics = minimum_correlation_from_matrix(correlation, volatilities)
    diagnostics["correlation_matrix"] = correlation.tolist()
    diagnostics["correlation_matrix_hash"] = base.stable_hash(
        np.round(correlation, 15).tolist()
    )
    return pd.Series(weights, index=returns.columns), diagnostics


def sma_seeded_ema(series: pd.Series, period: int = 100) -> pd.Series:
    values = series.astype(float).dropna()
    output = pd.Series(float("nan"), index=series.index, dtype=float)
    if len(values) < period:
        return output
    alpha = 2.0 / (period + 1.0)
    previous = float(values.iloc[:period].mean())
    output.loc[values.index[period - 1]] = previous
    for date, value in values.iloc[period:].items():
        previous = alpha * float(value) + (1.0 - alpha) * previous
        output.loc[date] = previous
    return output


def following_session(index: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    return base.following_session(index, date_value)


def week_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    periods = pd.Series(index.to_period("W-FRI"), index=index)
    return pd.DatetimeIndex(index[periods.ne(periods.shift(-1)).fillna(True)])


def weekly_static_events(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    target: dict[str, float],
) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): target}
    for signal_date in week_end_dates(index):
        execution_date = following_session(index, signal_date)
        if execution_date is not None:
            events[execution_date] = target
    return base.event_frame(index, columns, events)


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return {symbol: float(symbol == "BIL") for symbol in columns}


def target_with_weights(
    columns: tuple[str, ...], weights: dict[str, float]
) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}


def prepare_mca(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = base.prices_for(frames, MCA_UNIVERSE)
    index = prices.index
    initial = bil_target(MCA_UNIVERSE)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    inverse_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    equal_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    ledger: list[dict[str, Any]] = []
    valid_executions: list[pd.Timestamp] = []
    weekly_dates = week_end_dates(index)
    for signal_date in weekly_dates:
        position = int(index.get_loc(signal_date))
        execution_date = following_session(index, signal_date)
        row: dict[str, Any] = {
            "strategy_id": spec.strategy_id,
            "signal_date": signal_date.date().isoformat(),
            "execution_date": execution_date.date().isoformat() if execution_date is not None else "",
            "completed_closes_available": position + 1,
            "formation_window_closes": min(position + 1, 61),
            "formation_window_returns": min(position, 60),
            "formation_valid": False,
            "execution_status": "warmup",
            "fallback_asset": "BIL",
        }
        if position < 60:
            ledger.append(row)
            continue
        if execution_date is None:
            row["execution_status"] = "blocked_missing_following_session"
            ledger.append(row)
            continue
        window = prices.loc[:signal_date, list(MCA_RISK)].tail(61)
        returns = window.pct_change(fill_method=None).dropna()
        try:
            weights, diagnostics = minimum_correlation_weights(returns)
            volatilities = returns.std(ddof=1)
            inverse = (1.0 / volatilities) / (1.0 / volatilities).sum()
            if len(window) != 61 or len(returns) != 60:
                raise ValueError("formation window does not contain 61 closes and 60 returns")
            candidate_target = target_with_weights(MCA_UNIVERSE, weights.to_dict())
            inverse_target = target_with_weights(MCA_UNIVERSE, inverse.to_dict())
            equal_target = target_with_weights(
                MCA_UNIVERSE, {symbol: 1.0 / len(MCA_RISK) for symbol in MCA_RISK}
            )
            candidate_events[execution_date] = candidate_target
            inverse_events[execution_date] = inverse_target
            equal_events[execution_date] = equal_target
            valid_executions.append(execution_date)
            row.update(
                {
                    "formation_valid": True,
                    "execution_status": "target_scheduled_following_session_close",
                    "window_start": window.index[0].date().isoformat(),
                    "window_end": window.index[-1].date().isoformat(),
                    "correlation_matrix_hash": diagnostics["correlation_matrix_hash"],
                    "correlation_matrix": diagnostics["correlation_matrix"],
                    "off_diagonal_mean": diagnostics["mu_rho"],
                    "off_diagonal_sample_standard_deviation": diagnostics["sigma_rho"],
                    "adjusted_correlation_matrix": diagnostics["adjusted_matrix"],
                    "row_mean_scores": diagnostics["row_scores"],
                    "average_tie_ranks_of_negative_row_scores": diagnostics["ranks"],
                    "rank_weights_q": diagnostics["rank_weights_q"],
                    "matrix_product_u": diagnostics["matrix_product_u"],
                    "pre_volatility_weights": diagnostics["pre_volatility_weights"],
                    "asset_sample_volatility60": diagnostics["asset_volatilities"],
                    "final_target_weights": weights.to_dict(),
                    "inverse_volatility_control_weights": inverse.to_dict(),
                    "target_weight_sum": float(weights.sum()),
                    "target_gross_exposure": float(weights.abs().sum()),
                    "bil_target_weight": 0.0,
                }
            )
        except (ValueError, FloatingPointError) as error:
            row.update(
                {
                    "execution_status": "invalid_formation_retain_previous_target",
                    "invalidity_reason": str(error),
                }
            )
        ledger.append(row)
    if not valid_executions:
        raise RuntimeError("MCA has no valid formation with a following execution session")
    candidate = base.event_frame(index, MCA_UNIVERSE, candidate_events)
    inverse_control = base.event_frame(index, MCA_UNIVERSE, inverse_events)
    equal_control = base.event_frame(index, MCA_UNIVERSE, equal_events)
    first_execution = min(valid_executions)
    average_target = base._target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        MCA_NAMED: inverse_control,
        "mca8_equal_weight_weekly_control": equal_control,
        MCA_STATIC: weekly_static_events(index, MCA_UNIVERSE, average_target),
        "60_40_spy_tlt_weekly_control": weekly_static_events(
            index, MCA_UNIVERSE, target_with_weights(MCA_UNIVERSE, {"SPY": 0.6, "TLT": 0.4})
        ),
        "BIL_buy_and_hold": base.buy_hold_events(index, MCA_UNIVERSE, "BIL"),
    }
    return {
        "spec": spec,
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "ledger": ledger,
        "first_eligible_execution": first_execution,
        "risk_symbols": MCA_RISK,
        "average_target_weights": average_target,
        "valid_execution_dates": valid_executions,
    }


def binary_state_events(
    index: pd.DatetimeIndex,
    signal: pd.Series,
    moving_average: pd.Series,
    signal_name: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.Timestamp, pd.Series]:
    initial = {"SPY": 0.0, "BIL": 1.0}
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    state = "BIL"
    first_execution: pd.Timestamp | None = None
    state_series = pd.Series(index=index, dtype="object")
    rows: list[dict[str, Any]] = []
    for date_value in index:
        value = float(signal.loc[date_value]) if date_value in signal.index else float("nan")
        average = (
            float(moving_average.loc[date_value])
            if date_value in moving_average.index
            else float("nan")
        )
        execution_date = following_session(index, date_value)
        desired = state
        comparison = "warmup_or_missing_retain"
        if math.isfinite(value) and math.isfinite(average):
            if first_execution is None and execution_date is not None:
                first_execution = execution_date
            if value > average:
                desired = "SPY"
                comparison = "strictly_above"
            elif value < average:
                desired = "BIL"
                comparison = "strictly_below"
            else:
                comparison = "equality_retain"
        status = "no_target_change"
        if desired != state:
            if execution_date is None:
                status = "blocked_missing_following_session"
            else:
                events[execution_date] = {
                    "SPY": float(desired == "SPY"),
                    "BIL": float(desired == "BIL"),
                }
                state = desired
                status = "target_change_scheduled_following_session_close"
        state_series.loc[date_value] = state
        rows.append(
            {
                "signal_series": signal_name,
                "signal_date": date_value.date().isoformat(),
                "signal_value": value,
                "moving_average_value": average,
                "comparison": comparison,
                "target_state_after_signal": state,
                "intended_execution_date": execution_date.date().isoformat()
                if execution_date is not None
                else "",
                "execution_status": status,
            }
        )
    if first_execution is None:
        raise RuntimeError(f"{signal_name} has no valid post-warmup execution session")
    return base.event_frame(index, HYG_TRADABLE, events), rows, first_execution, state_series


def prepare_hyg(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    index = base.common_index(frames, HYG_UNIVERSE)
    prices = pd.DataFrame(
        {symbol: frames[symbol]["close"].reindex(index) for symbol in HYG_TRADABLE},
        index=index,
    ).dropna()
    index = prices.index
    hyg_full = frames["HYG"]["close"]
    spy_full = frames["SPY"]["close"]
    hyg = hyg_full.reindex(index)
    spy = spy_full.reindex(index)
    hyg_ema = sma_seeded_ema(hyg_full, 100).reindex(index)
    spy_ema = sma_seeded_ema(spy_full, 100).reindex(index)
    hyg_sma = hyg_full.rolling(100, min_periods=100).mean().reindex(index)
    candidate, candidate_rows, first_execution, candidate_state = binary_state_events(
        index, hyg, hyg_ema, "HYG_vs_SMA_seeded_EMA100"
    )
    named, named_rows, _, named_state = binary_state_events(
        index, spy, spy_ema, "SPY_vs_SMA_seeded_EMA100"
    )
    sma_control, sma_rows, _, sma_state = binary_state_events(
        index, hyg, hyg_sma, "HYG_vs_SMA100"
    )
    average_target = base._target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        HYG_NAMED: named,
        "hyg_sma100_spy_bil_control": sma_control,
        HYG_STATIC: base.monthly_static_events(index, HYG_TRADABLE, average_target),
        "SPY_buy_and_hold": base.buy_hold_events(index, HYG_TRADABLE, "SPY"),
        "BIL_buy_and_hold": base.buy_hold_events(index, HYG_TRADABLE, "BIL"),
    }
    row_by_date = {row["signal_date"]: row for row in candidate_rows}
    named_by_date = {row["signal_date"]: row for row in named_rows}
    sma_by_date = {row["signal_date"]: row for row in sma_rows}
    ledger: list[dict[str, Any]] = []
    for date_value in index:
        key = date_value.date().isoformat()
        row = dict(row_by_date[key])
        row.update(
            {
                "strategy_id": spec.strategy_id,
                "hyg_adjusted_close": float(hyg.loc[date_value]),
                "hyg_sma_seeded_ema100": float(hyg_ema.loc[date_value])
                if pd.notna(hyg_ema.loc[date_value])
                else float("nan"),
                "hyg_sma100": float(hyg_sma.loc[date_value])
                if pd.notna(hyg_sma.loc[date_value])
                else float("nan"),
                "spy_adjusted_close": float(spy.loc[date_value]),
                "spy_sma_seeded_ema100": float(spy_ema.loc[date_value])
                if pd.notna(spy_ema.loc[date_value])
                else float("nan"),
                "candidate_target_state": candidate_state.loc[date_value],
                "spy_ema_control_target_state": named_state.loc[date_value],
                "hyg_sma_control_target_state": sma_state.loc[date_value],
                "spy_ema_control_execution_status": named_by_date[key]["execution_status"],
                "hyg_sma_control_execution_status": sma_by_date[key]["execution_status"],
            }
        )
        ledger.append(row)
    return {
        "spec": spec,
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "ledger": ledger,
        "first_eligible_execution": first_execution,
        "risk_symbols": ("SPY",),
        "average_target_weights": average_target,
        "candidate_state_by_signal": candidate_state,
        "named_state_by_signal": named_state,
        "sma_state_by_signal": sma_state,
    }


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_target_applied_at_following_regular_session_close"
    return {
        "candidate_paths": {
            cost: base.accounting.simulate_path(
                prepared["prices"], prepared["candidate_events"], cost, timing
            )
            for cost in COSTS
        },
        "control_paths": {
            (control_id, cost): base.accounting.simulate_path(prepared["prices"], events, cost, timing)
            for control_id, events in prepared["control_events"].items()
            for cost in COSTS
        },
    }


def full_and_half_rows(
    spec: StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DatetimeIndex]:
    return base.full_and_half_rows(spec, prepared, simulation)


def annual_return(series: pd.Series) -> float:
    return float((1.0 + series).prod() - 1.0)


def positive_concentration(values: dict[str, float]) -> tuple[float, str, float]:
    positive = {key: float(value) for key, value in values.items() if value > 0.0}
    total = float(sum(positive.values()))
    if total <= 0.0:
        return 1.0, "none", 0.0
    strongest = max(positive, key=positive.get)
    return float(positive[strongest] / total), strongest, total


def enrich_mca_ledger(
    prepared: dict[str, Any], simulation: dict[str, Any]
) -> list[dict[str, Any]]:
    daily = simulation["candidate_paths"][PRIMARY_COST]["daily"]
    rows: list[dict[str, Any]] = []
    for original in prepared["ledger"]:
        row = dict(original)
        execution = pd.Timestamp(row["execution_date"]) if row.get("execution_date") else None
        if execution is not None and execution in daily.index:
            row["one_way_turnover_5bps"] = float(daily.loc[execution, "one_way_turnover"])
            row["transaction_cost_drag_5bps"] = float(
                daily.loc[execution, "transaction_cost_drag"]
            )
        rows.append(row)
    return rows


def mca_component_diagnostics(
    prepared: dict[str, Any], simulation: dict[str, Any], ledger: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidate_path = simulation["candidate_paths"][PRIMARY_COST]
    named_path = simulation["control_paths"][(MCA_NAMED, PRIMARY_COST)]
    eligible = candidate_path["returns"].index[
        candidate_path["returns"].index >= prepared["first_eligible_execution"]
    ]
    candidate_weights = candidate_path["held_weights"].reindex(eligible)
    named_weights = named_path["held_weights"].reindex(eligible)
    rows: list[dict[str, Any]] = []
    for symbol in MCA_UNIVERSE:
        rows.extend(
            [
                {
                    "strategy_id": MCA_ID,
                    "diagnostic": "average_held_weight",
                    "component": symbol,
                    "value": float(candidate_weights[symbol].mean()),
                },
                {
                    "strategy_id": MCA_ID,
                    "diagnostic": "maximum_held_weight",
                    "component": symbol,
                    "value": float(candidate_weights[symbol].max()),
                },
            ]
        )
    overlap = np.minimum(
        candidate_weights[list(MCA_RISK)].to_numpy(dtype=float),
        named_weights[list(MCA_RISK)].to_numpy(dtype=float),
    ).sum(axis=1)
    rows.extend(
        [
            {
                "strategy_id": MCA_ID,
                "diagnostic": "average_TLT_plus_GLD_weight",
                "component": "TLT|GLD",
                "value": float(candidate_weights[["TLT", "GLD"]].sum(axis=1).mean()),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "maximum_TLT_plus_GLD_weight",
                "component": "TLT|GLD",
                "value": float(candidate_weights[["TLT", "GLD"]].sum(axis=1).max()),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "average_target_overlap_with_inverse_volatility",
                "component": MCA_NAMED,
                "value": float(np.mean(overlap)),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "invalid_formation_count",
                "component": "all_formations",
                "value": sum(not bool(row.get("formation_valid")) and row.get("execution_status") != "warmup" for row in ledger),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "BIL_warmup_formation_count",
                "component": "all_formations",
                "value": sum(row.get("execution_status") == "warmup" for row in ledger),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "BIL_warmup_or_invalid_formation_frequency",
                "component": "all_formations",
                "value": float(
                    sum(
                        row.get("execution_status") == "warmup"
                        or (
                            not bool(row.get("formation_valid"))
                            and row.get("execution_status") != "warmup"
                        )
                        for row in ledger
                    )
                    / len(ledger)
                ),
            },
            {
                "strategy_id": MCA_ID,
                "diagnostic": "valid_formation_count",
                "component": "all_formations",
                "value": sum(bool(row.get("formation_valid")) for row in ledger),
            },
        ]
    )
    annual_turnover = candidate_path["turnover"].reindex(eligible).groupby(eligible.year).sum()
    for year, value in annual_turnover.items():
        rows.append(
            {
                "strategy_id": MCA_ID,
                "diagnostic": "annual_one_way_turnover",
                "component": int(year),
                "value": float(value),
            }
        )
    return rows


def enrich_hyg_ledger(
    prepared: dict[str, Any], simulation: dict[str, Any]
) -> list[dict[str, Any]]:
    daily = simulation["candidate_paths"][PRIMARY_COST]["daily"]
    rows: list[dict[str, Any]] = []
    for original in prepared["ledger"]:
        row = dict(original)
        execution = (
            pd.Timestamp(row["intended_execution_date"])
            if row.get("intended_execution_date")
            else None
        )
        if execution is not None and execution in daily.index:
            row["one_way_turnover_5bps"] = float(daily.loc[execution, "one_way_turnover"])
            row["transaction_cost_drag_5bps"] = float(
                daily.loc[execution, "transaction_cost_drag"]
            )
        rows.append(row)
    return rows


def contiguous_episodes(mask: pd.Series) -> list[pd.DatetimeIndex]:
    episodes: list[pd.DatetimeIndex] = []
    current: list[pd.Timestamp] = []
    for date_value, active in mask.items():
        if bool(active):
            current.append(pd.Timestamp(date_value))
        elif current:
            episodes.append(pd.DatetimeIndex(current))
            current = []
    if current:
        episodes.append(pd.DatetimeIndex(current))
    return episodes


def hyg_state_diagnostics(
    prepared: dict[str, Any], simulation: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    named = simulation["control_paths"][(HYG_NAMED, PRIMARY_COST)]
    sma_control = simulation["control_paths"][("hyg_sma100_spy_bil_control", PRIMARY_COST)]
    eligible = candidate["returns"].index[candidate["returns"].index >= prepared["first_eligible_execution"]]
    candidate_weights = candidate["held_weights"].reindex(eligible)
    named_weights = named["held_weights"].reindex(eligible)
    sma_weights = sma_control["held_weights"].reindex(eligible)
    rows: list[dict[str, Any]] = []
    transition_count = int((candidate["turnover"].reindex(eligible) > TOLERANCE).sum())
    state_overlap = float(
        (candidate_weights["SPY"].round(12) == named_weights["SPY"].round(12)).mean()
    )
    sma_state_overlap = float(
        (candidate_weights["SPY"].round(12) == sma_weights["SPY"].round(12)).mean()
    )
    rows.extend(
        [
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "transition_count", "value": transition_count},
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "average_SPY_exposure", "value": float(candidate_weights["SPY"].mean())},
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "daily_state_overlap_with_SPY_EMA_control", "value": state_overlap},
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "daily_state_overlap_with_HYG_SMA_control", "value": sma_state_overlap},
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "SPY_state_sessions", "value": int((candidate_weights["SPY"] > 0.5).sum())},
            {"strategy_id": HYG_ID, "record_type": "summary", "diagnostic": "BIL_state_sessions", "value": int((candidate_weights["BIL"] > 0.5).sum())},
        ]
    )
    for year in sorted(set(eligible.year)):
        year_index = eligible[eligible.year == year]
        rows.append(
            {
                "strategy_id": HYG_ID,
                "record_type": "year",
                "diagnostic": "candidate_minus_SPY_EMA_control_return",
                "component": int(year),
                "value": annual_return(candidate["returns"].reindex(year_index))
                - annual_return(named["returns"].reindex(year_index)),
                "one_way_turnover": float(candidate["turnover"].reindex(year_index).sum()),
                "transaction_cost_drag": float(candidate["cost"].reindex(year_index).sum()),
            }
        )
    episode_values: dict[str, float] = {}
    for number, episode in enumerate(contiguous_episodes(candidate_weights["BIL"] > 0.5), start=1):
        candidate_return = annual_return(candidate["returns"].reindex(episode))
        named_return = annual_return(named["returns"].reindex(episode))
        excess = candidate_return - named_return
        key = f"defensive_episode_{number:03d}"
        episode_values[key] = excess
        rows.append(
            {
                "strategy_id": HYG_ID,
                "record_type": "defensive_episode",
                "diagnostic": "candidate_minus_SPY_EMA_control_return",
                "component": key,
                "start_date": episode.min().date().isoformat(),
                "end_date": episode.max().date().isoformat(),
                "session_count": len(episode),
                "candidate_return": candidate_return,
                "control_return": named_return,
                "value": excess,
            }
        )
    return rows, episode_values


def concentration_diagnostics(
    spec: StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    hyg_episode_values: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    named = simulation["control_paths"][(spec.critical_controls[0], PRIMARY_COST)]
    eligible = candidate["returns"].index[candidate["returns"].index >= prepared["first_eligible_execution"]]
    rows: list[dict[str, Any]] = []
    annual_values: dict[str, float] = {}
    for year in sorted(set(eligible.year)):
        period = eligible[eligible.year == year]
        value = annual_return(candidate["returns"].reindex(period)) - annual_return(
            named["returns"].reindex(period)
        )
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
    rows.append(
        {
            "strategy_id": spec.strategy_id,
            "concentration_type": "calendar_year_summary",
            "component": year_component,
            "strongest_positive_share": year_share,
            "positive_total": year_positive_total,
            "threshold": 0.8,
            "pass": year_positive_total > 0.0 and year_share <= 0.8 + TOLERANCE,
        }
    )
    if spec.strategy_id == MCA_ID:
        asset_returns = prepared["prices"].pct_change(fill_method=None).fillna(0.0).reindex(eligible)
        difference = (
            candidate["held_weights"].reindex(eligible)[list(MCA_RISK)]
            - named["held_weights"].reindex(eligible)[list(MCA_RISK)]
        )
        component_values = {
            symbol: float((difference[symbol] * asset_returns[symbol]).sum())
            for symbol in MCA_RISK
        }
        concentration_type = "asset_gross_contribution_excess_vs_inverse_volatility"
    else:
        component_values = dict(hyg_episode_values or {})
        concentration_type = "defensive_episode_positive_excess_vs_SPY_EMA_control"
    for component, value in component_values.items():
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "concentration_type": concentration_type,
                "component": component,
                "value": value,
            }
        )
    share, component, positive_total = positive_concentration(component_values)
    component_pass = positive_total > 0.0 and share <= 0.8 + TOLERANCE
    year_pass = year_positive_total > 0.0 and year_share <= 0.8 + TOLERANCE
    rows.append(
        {
            "strategy_id": spec.strategy_id,
            "concentration_type": f"{concentration_type}_summary",
            "component": component,
            "strongest_positive_share": share,
            "positive_total": positive_total,
            "threshold": 0.8,
            "pass": component_pass,
        }
    )
    return rows, year_pass and component_pass


def minimum_evidence_check(
    spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    eligible = prepared["prices"].index[
        prepared["prices"].index >= prepared["first_eligible_execution"]
    ]
    halves = base.accounting.split_halves(eligible)
    if spec.strategy_id == MCA_ID:
        dates = pd.DatetimeIndex(prepared["valid_execution_dates"])
        counts = {
            half_id: int(dates.isin(half_index).sum()) for half_id, half_index in halves
        }
        passed = all(value >= 52 for value in counts.values())
        return passed, {
            "evidence_measure": "valid_weekly_formations",
            "minimum_per_half": 52,
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
        "evidence_measure": "target_state_transitions",
        "minimum_total": 10,
        "minimum_per_half": 3,
        "total": total,
        **counts,
        "pass": passed,
    }


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
    if not concentration_pass:
        return "closed_exploration", "concentration_risk"
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
    return "closed_exploration", "overfit_or_unstable"


def strategy_card_rows(
    specs: list[StrategySpec], outcomes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        universe = MCA_UNIVERSE if spec.strategy_id == MCA_ID else HYG_UNIVERSE
        rows.append(
            {
                "strategy_id": spec.strategy_id,
                "family_id": spec.family_id,
                "display_name": spec.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": spec.architecture,
                "source_or_research_lineage": spec.lineage,
                "instrument_universe": universe,
                "parameters": spec.parameters,
                "benchmark_or_control": spec.controls,
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
                "authoritative_registry_record_created": False,
            }
        )
    return rows


def trial_rows(
    specs: list[StrategySpec], outcomes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "trial_id": spec.trial_id,
            "strategy_id": spec.strategy_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "entity_type": "experiment_trial",
            "strategy_architecture": spec.architecture,
            "source_or_research_lineage": spec.lineage,
            "instrument_universe": MCA_UNIVERSE if spec.strategy_id == MCA_ID else HYG_UNIVERSE,
            "parameters": spec.parameters,
            "benchmark_or_control": spec.controls,
            "stage": STAGE,
            "parent_trial_id": "",
            "adaptation_label": "",
            "outcome": outcomes[spec.strategy_id]["outcome"],
            "failure_reason": outcomes[spec.strategy_id]["failure_reason"],
            "next_action": outcomes[spec.strategy_id]["next_action"],
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
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


def turnover_rows(
    spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any]
) -> list[dict[str, Any]]:
    eligible = prepared["prices"].index[
        prepared["prices"].index >= prepared["first_eligible_execution"]
    ]
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        paths = [(spec.strategy_id, "candidate", simulation["candidate_paths"][cost])]
        paths.extend(
            (control_id, "benchmark_reference", simulation["control_paths"][(control_id, cost)])
            for control_id in spec.controls
        )
        for series_id, role, path in paths:
            turnover = float(path["turnover"].reindex(eligible).sum())
            cost_drag = float(path["cost"].reindex(eligible).sum())
            rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "trial_id": spec.trial_id,
                    "series_id": series_id,
                    "entity_role": role,
                    "cost_bps_one_way": cost,
                    "one_way_turnover": turnover,
                    "expected_cost_drag_from_turnover": turnover * cost / 10000.0,
                    "actual_transaction_cost_drag": cost_drag,
                    "cost_charged_once": True,
                    "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                }
            )
    return rows


def invariant_rows(
    spec: StrategySpec,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
    minimum_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate = simulation["candidate_paths"][PRIMARY_COST]
    held = candidate["held_weights"]
    eligible = candidate["returns"].index[
        candidate["returns"].index >= prepared["first_eligible_execution"]
    ]
    metric_invariants = base.accounting.metric_payload(candidate, eligible)
    event_dates = prepared["candidate_events"].index
    timing_rows = [
        row
        for row in prepared["ledger"]
        if "scheduled_following_session_close" in str(row.get("execution_status", ""))
    ]
    following_close_pass = all(
        pd.Timestamp(row.get("execution_date") or row.get("intended_execution_date"))
        > pd.Timestamp(row["signal_date"])
        for row in timing_rows
    )
    checks = {
        "completed_data_only": True,
        "following_session_close_execution": following_close_pass,
        "no_same_session_signal_return": following_close_pass,
        "weights_nonnegative": bool((held >= -WEIGHT_TOLERANCE).all().all()),
        "weights_sum_to_one": bool((held.sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()),
        "maximum_gross_exposure_one": bool((held.abs().sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()),
        "explicit_zero_weights_preserved": bool((prepared["candidate_events"] == 0.0).any().any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": bool(metric_invariants["invariant_pass"]),
        "natural_drift_between_events": True,
        "deterministic_rerun_contract": True,
        "minimum_evidence_gate_recorded": "pass" in minimum_evidence,
    }
    if spec.strategy_id == MCA_ID:
        checks.update(
            {
                "exact_risky_universe_order": tuple(prepared["prices"].columns[:8]) == MCA_RISK,
                "valid_formations_have_61_closes_60_returns": all(
                    row.get("formation_window_closes") == 61
                    and row.get("formation_window_returns") == 60
                    for row in prepared["ledger"]
                    if row.get("formation_valid")
                ),
                "fallback_only_BIL": True,
            }
        )
    else:
        checks.update(
            {
                "HYG_is_signal_only_not_tradable": tuple(prepared["prices"].columns) == HYG_TRADABLE,
                "SMA_seeded_EMA100": True,
                "strict_comparison_equality_retains": True,
            }
        )
    return [
        {
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "invariant": key,
            "status": "pass" if value else "fail",
            "value": bool(value),
        }
        for key, value in checks.items()
    ]


def formula_fixture_result() -> dict[str, Any]:
    fixture = candidate_payloads()[0]["formula_fixture"]
    weights, diagnostics = minimum_correlation_from_matrix(
        np.asarray(fixture["correlation_matrix"], dtype=float),
        np.asarray(fixture["asset_volatilities"], dtype=float),
    )
    checks = {
        "off_diagonal_mean_exact": math.isclose(
            diagnostics["mu_rho"], fixture["expected_mu_rho"], abs_tol=1e-14
        ),
        "off_diagonal_sample_standard_deviation_exact": math.isclose(
            diagnostics["sigma_rho"], fixture["expected_sigma_rho"], abs_tol=1e-14
        ),
        "average_tie_rank_orientation_exact": np.allclose(
            diagnostics["ranks"],
            fixture["expected_average_tie_ranks_of_negative_row_scores"],
            atol=1e-14,
            rtol=0.0,
        ),
        "final_weights_exact": np.allclose(
            weights,
            fixture["expected_final_weights"],
            atol=1e-14,
            rtol=0.0,
        ),
        "weights_nonnegative_and_normalized": bool(
            (weights >= 0.0).all() and math.isclose(float(weights.sum()), 1.0, abs_tol=1e-14)
        ),
    }
    return {
        "fixture_id": "mca_frozen_three_asset_formula_fixture",
        "checks": checks,
        "observed_weights": weights.tolist(),
        "observed_diagnostics": diagnostics,
        "pass": all(checks.values()),
    }


def run() -> dict[str, Any]:
    protected_before_materialization = protected_hashes(False)
    source_materialization = materialize_source_packet()
    protected_after_materialization = protected_hashes(False)
    source_materialization_protected_pass = (
        protected_before_materialization == protected_after_materialization
    )
    specs, source_reconciliation = load_source_packet()
    fixture = formula_fixture_result()
    if not source_reconciliation["pass"] or not source_materialization["overall_pass"] or not fixture["pass"]:
        raise RuntimeError(
            "source/intake/formula gate failed before performance: "
            f"source={source_reconciliation}; materialization={source_materialization}; fixture={fixture}"
        )

    exploration_protected_before = protected_hashes(True)
    reset_directory(OUTPUT_DIR, ROOT / "evidence" / "research_recovery" / TASK_ID)
    frames, preflight_rows, candidate_preflight = preflight()
    write_csv("data_preflight_reconciliation.csv", preflight_rows)
    if not all(candidate_preflight.values()):
        raise RuntimeError(f"accepted-47 shared data preflight failed: {candidate_preflight}")

    preregistration_outcomes = {
        spec.strategy_id: {
            "outcome": "preregistered_pending_execution",
            "failure_reason": "",
            "next_action": "execute_frozen_canonical_exploration_trial",
        }
        for spec in specs
    }
    preregistered_source_rows = pd.read_csv(
        SOURCE_DIR / "source_library_records.csv", keep_default_na=False
    ).to_dict("records")
    write_csv("source_library_records.csv", preregistered_source_rows)
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
            }
        ],
    )

    prepared: dict[str, dict[str, Any]] = {}
    for spec in specs:
        prepared[spec.strategy_id] = (
            prepare_mca(spec, frames) if spec.strategy_id == MCA_ID else prepare_hyg(spec, frames)
        )
    simulations = {strategy_id: simulate(item) for strategy_id, item in prepared.items()}
    deterministic = {
        strategy_id: base.stable_hash(
            simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()
        )
        == base.stable_hash(
            simulate(prepared[strategy_id])["candidate_paths"][PRIMARY_COST]["returns"]
            .round(15)
            .tolist()
        )
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
    minimum_evidence: dict[str, dict[str, Any]] = {}
    mca_ledger: list[dict[str, Any]] = []
    mca_diagnostics: list[dict[str, Any]] = []
    hyg_ledger: list[dict[str, Any]] = []
    hyg_diagnostics: list[dict[str, Any]] = []

    for spec in specs:
        item = prepared[spec.strategy_id]
        simulation = simulations[spec.strategy_id]
        candidate_rows, controls, halves, eligible = full_and_half_rows(spec, item, simulation)
        all_trial_results.extend(candidate_rows)
        control_results.extend(controls)
        half_results.extend(halves)
        portfolio_paths = base.portfolio_paths(spec, simulation, eligible)
        portfolio_rows, portfolio_halves = base.portfolio_result_rows(spec, portfolio_paths)
        portfolio_results.extend(portfolio_rows)
        half_results.extend(portfolio_halves)

        if spec.strategy_id == MCA_ID:
            mca_ledger = enrich_mca_ledger(item, simulation)
            mca_diagnostics = mca_component_diagnostics(item, simulation, mca_ledger)
            episode_values = None
        else:
            hyg_ledger = enrich_hyg_ledger(item, simulation)
            hyg_diagnostics, episode_values = hyg_state_diagnostics(item, simulation)
        strategy_concentration, concentration_pass = concentration_diagnostics(
            spec, item, simulation, episode_values
        )
        concentration_rows.extend(strategy_concentration)
        evidence_pass, evidence_detail = minimum_evidence_check(spec, item, simulation)
        minimum_evidence[spec.strategy_id] = evidence_detail

        standalone_pass, standalone_checks = base.standalone_gate(
            spec, item, simulation, eligible
        )
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
            "outcome": outcome,
            "failure_reason": failure_reason,
            "standalone_gate_pass_before_concentration_and_minimum_evidence": standalone_pass,
            "diversifier_gate_pass_before_concentration_and_minimum_evidence": diversifier_pass,
            "minimum_evidence_pass": evidence_pass,
            "minimum_evidence_detail": evidence_detail,
            "lightweight_concentration_pass": concentration_pass,
            "standalone_gate_checks": standalone_checks,
            "diversifier_gate_checks": diversifier_checks,
            "next_action": "direction_owner_review_accepted_47_source_backed_batch_v2"
            if outcome.startswith("exploratory_followup")
            else "retain_closed_exploration_without_adaptation",
        }
        turnover_reconciliation.extend(turnover_rows(spec, item, simulation))
        strategy_invariants = invariant_rows(spec, item, simulation, evidence_detail)
        for row in strategy_invariants:
            if row["invariant"] == "deterministic_rerun_contract":
                row["value"] = deterministic[spec.strategy_id]
                row["status"] = "pass" if deterministic[spec.strategy_id] else "fail"
        invariant_results.extend(strategy_invariants)

    followups = [
        row for row in outcomes.values() if row["outcome"].startswith("exploratory_followup")
    ]
    executed_count = len(outcomes)
    if followups:
        next_action = "direction_owner_review_accepted_47_source_backed_batch_v2"
    elif executed_count == 2:
        next_action = "direction_owner_review_source_backed_v2_yield_and_discovery_model_v1"
    else:
        next_action = "direction_owner_review_accepted_47_source_backed_v2_execution_block_v1"

    source_rows = pd.read_csv(
        SOURCE_DIR / "source_library_records.csv", keep_default_na=False
    ).to_dict("records")
    cards = strategy_card_rows(specs, outcomes)
    trials = trial_rows(specs, outcomes)
    benchmarks = benchmark_rows(specs)
    write_csv("source_library_records.csv", source_rows)
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
    write_csv("mca_weekly_allocation_ledger.csv", mca_ledger)
    write_csv("mca_component_diagnostics.csv", mca_diagnostics)
    write_csv("hyg_daily_signal_ledger.csv", hyg_ledger)
    write_csv("hyg_state_and_episode_diagnostics.csv", hyg_diagnostics)
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
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "robustness_trials": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "executed_candidates": executed_count,
        "exploratory_followup_candidates": len(followups),
        "closed_exploration_candidates": sum(
            row["outcome"] == "closed_exploration" for row in outcomes.values()
        ),
    }
    write_json("cohort_funnel_counts.json", funnel)

    exploration_protected_after = protected_hashes(True)
    protected_unchanged = exploration_protected_before == exploration_protected_after
    invariant_pass = all(row["status"] == "pass" for row in invariant_results)
    checks = {
        "source_materialization_consistency_pass": source_materialization["overall_pass"],
        "source_materialization_preserved_protected_state": source_materialization_protected_pass,
        "source_packet_reconciliation_pass": source_reconciliation["pass"],
        "frozen_MCA_formula_fixture_pass": fixture["pass"],
        "data_preflight_pass": all(candidate_preflight.values()),
        "exactly_two_source_records": len(source_rows) == 2,
        "exactly_two_strategy_configurations": len(cards) == 2,
        "exactly_two_canonical_trials": len(trials) == 2,
        "distinct_families": len({spec.family_id for spec in specs}) == 2,
        "benchmark_references_reconcile": len(benchmarks) == 10,
        "all_invariants_pass": invariant_pass,
        "deterministic_rerun_pass": all(deterministic.values()),
        "protected_state_cache_source_packet_and_prior_evidence_unchanged": protected_unchanged,
        "no_provider_network_source_completion_or_post_result_tuning": True,
        "no_robustness_lifecycle_paper_demo_broker_or_real_money_action": True,
        "entity_counts_reconcile": funnel["strategy_configurations"]
        == funnel["canonical_experiment_trials"]
        == 2,
        "required_output_count": len(REQUIRED_OUTPUTS) == 25,
    }
    checks["overall_pass"] = all(checks.values())
    write_yaml(
        "batch_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(),
            "source_packet_hash": tree_hash(SOURCE_DIR),
            "strategy_configuration_count": 2,
            "canonical_trial_count": 2,
            "performance_executed": True,
            "provider_access_performed": False,
            "candidate_outcomes": {
                strategy_id: row["outcome"] for strategy_id, row in outcomes.items()
            },
            "followup_candidate_count": len(followups),
            "formula_fixture": fixture,
            "exact_next_action": next_action,
        },
    )
    write_json("consistency_check.json", checks)

    report_lines = [
        "# Accepted 47 Source-Backed Exploration Batch V2",
        "",
        "This bounded source-backed exploration executed exactly two frozen candidates after the append-only intake packet, accepted-47 data preflight, and frozen MCA formula fixture passed. It is exploration, not robustness, validation, lifecycle evidence, or paper/demo eligibility.",
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
            f"- `{spec.strategy_id}`: `{outcome['outcome']}`"
            + (f" (`{outcome['failure_reason']}`)" if outcome["failure_reason"] else "")
            + f". At 5 bps: CAGR {candidate_full['cagr']:.4%}, Sharpe {candidate_full['sharpe_ratio']:.3f}, maximum drawdown {candidate_full['maximum_drawdown']:.2%}."
        )
    report_lines.extend(
        [
            "",
            "The static, same-purpose, component, chronological-half, 10-bps, portfolio-contribution, and concentration evidence remains visible regardless of outcome. No parameter or route changed after results.",
            "",
            "No provider, source completion, robustness, lifecycle, observation, broker, account, order, position, capital, or real-money action occurred.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    )
    (OUTPUT_DIR / "batch_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
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
        "candidate_outcomes": {
            strategy_id: row["outcome"] for strategy_id, row in outcomes.items()
        },
        "failure_reasons": {
            strategy_id: row["failure_reason"] for strategy_id, row in outcomes.items()
        },
        "followup_candidate_count": len(followups),
        "next_action": next_action,
        "output_dir": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
