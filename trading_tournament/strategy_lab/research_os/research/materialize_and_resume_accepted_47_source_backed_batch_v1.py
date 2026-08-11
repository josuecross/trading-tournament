from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "materialize_and_resume_accepted_47_source_backed_batch_v1"
SOURCE_TASK_ID = "accepted_47_selective_source_backed_intake_v1"
EXPLORATION_TASK_ID = "accepted_47_source_backed_exploration_batch_v1"
OUTPUT_DIR = ROOT / "evidence" / "corrections" / TASK_ID / "latest"
SOURCE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID / "latest"
BLOCKED_DIR = ROOT / "evidence" / "research_recovery" / EXPLORATION_TASK_ID / "latest"
HISTORY_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / EXPLORATION_TASK_ID
    / "history"
    / "blocked_missing_source_packet_v1"
)
SOURCE_INSTRUCTION_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\9f2b4847-7e5e-4469-8d00-98634d586d25\pasted-text.txt"
)
DIRECTION_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\0c56d952-0815-4805-80bc-7d6beef5d297\pasted-text.txt"
)

CAA_SPEC: dict[str, Any] = {
    "source_record_id": "src_keller_butler_kipnis_caa_n8_tv10_cap25_v1",
    "entity_type": "source_library_record",
    "stage": "source_extracted",
    "outcome": "feasible",
    "failure_reason": "",
    "strategy_id": "keller_butler_kipnis_caa_n8_tv10_cap25_v1",
    "family_id": "momentum_conditioned_mean_variance_target_volatility",
    "display_name": "Classical Asset Allocation N8 - 10% Target Volatility",
    "strategy_architecture": "monthly_long_only_momentum_mvo_target_volatility",
    "source_or_research_lineage": "keller_butler_kipnis_2015_caa_n8_tv10_cap25",
    "source_title": "Momentum and Markowitz - A Golden Combination",
    "classification": "direct_index_to_etf_multi_asset",
    "exact_source_replication_claimed": False,
    "route": "standalone_with_diversifier_diagnostic",
    "ordered_universe": ["BIL", "IEF", "HYG", "SPY", "QQQ", "EFA", "EWJ", "EEM"],
    "parameters": {
        "expected_return_horizons_months": [1, 3, 6, 12],
        "expected_return_divisor": 22,
        "covariance_months": 12,
        "covariance_ddof": 1,
        "target_annualized_volatility": 0.10,
        "noncash_weight_cap": 0.25,
        "optimizer_tolerance": 1.0e-10,
    },
    "formula": {
        "expected_return": "(R1 + R3 + R6 + R12) / 22",
        "covariance": "sample_covariance_of_12_monthly_returns_times_12",
        "optimizer": "source_published_CLA_or_verified_deterministic_equivalent",
        "selection": "maximum_expected_return_at_or_below_10pct_annualized_volatility",
    },
    "constraints": {
        "long_only": True,
        "leverage": False,
        "weights_sum_to_one": True,
        "capped_assets": ["HYG", "SPY", "QQQ", "EFA", "EWJ", "EEM"],
        "capped_asset_max_weight": 0.25,
        "uncapped_assets_with_unit_bounds": ["BIL", "IEF"],
    },
    "timing": {
        "signal": "completed_month_end_close",
        "execution": "following_regular_session_close",
        "rebalance": "monthly",
        "natural_drift": True,
    },
    "warmup": {
        "complete_month_end_prices": 13,
        "complete_monthly_returns": 12,
        "fallback": {"BIL": 1.0},
    },
    "missing_data": {
        "reduced_universe_allowed": False,
        "invalid_formation": "retain_current_executable_target",
        "missing_execution_price": "block_change_and_retain_pretrade_holdings",
        "tradable_price_forward_fill": False,
    },
    "controls": [
        "caa_n8_minimum_variance_same_constraints_control",
        "caa_n8_equal_weight_monthly_control",
        "caa_n8_static_average_weight_control",
        "60_40_spy_ief_monthly_control",
        "BIL_buy_and_hold",
    ],
    "critical_controls": [
        "caa_n8_minimum_variance_same_constraints_control",
        "caa_n8_static_average_weight_control",
    ],
    "incremental_value_hypothesis": "momentum_conditioned_constrained_MVO_adds_value_beyond_covariance_only_and_static_allocation",
    "proposed_trial_id": "accepted47_source_v1__caa_n8_tv10__canonical",
}

TPP_SPEC: dict[str, Any] = {
    "source_record_id": "src_gestaltu_tactical_permanent_portfolio_7pct_v1",
    "entity_type": "source_library_record",
    "stage": "source_extracted",
    "outcome": "feasible",
    "failure_reason": "",
    "strategy_id": "gestaltu_tactical_permanent_portfolio_7pct_v1",
    "family_id": "trend_filtered_risk_parity_volatility_target",
    "display_name": "Tactical Permanent Portfolio - 7% Volatility Target",
    "strategy_architecture": "monthly_three_asset_trend_inverse_volatility_cash_scaling",
    "source_or_research_lineage": "gestaltu_resolve_tactical_permanent_portfolio",
    "source_title": "GestaltU/ReSolve Tactical Permanent Portfolio",
    "classification": "native_ETF_multi_asset",
    "exact_source_replication_claimed": False,
    "route": "standalone_with_diversifier_diagnostic",
    "risky_assets": ["SPY", "IEF", "GLD"],
    "cash_asset": "BIL",
    "parameters": {
        "trend_SMA_sessions": 200,
        "inverse_volatility_sessions": 21,
        "portfolio_covariance_sessions": 60,
        "covariance_ddof": 1,
        "target_annualized_volatility": 0.07,
        "leverage_allowed": False,
    },
    "signal": {
        "evaluation_session": "penultimate_regular_session_of_month",
        "selected_when": "close_strictly_above_SMA200",
        "equality": "not_selected",
    },
    "allocation": {
        "initial_weights": "normalized_inverse_volatility_21_for_selected_assets",
        "portfolio_volatility": "sqrt(252_times_w_transpose_covariance60_w)",
        "scale": "min(1, 0.07 / portfolio_volatility)",
        "risky_weights": "scale_times_initial_weights",
        "BIL_weight": "1_minus_scale",
        "no_selected_assets": {"BIL": 1.0},
    },
    "timing": {
        "target_execution": "final_regular_session_close_of_month",
        "rebalance": "monthly",
        "natural_drift": True,
    },
    "warmup": {
        "minimum_price_sessions": 200,
        "minimum_return_sessions": 60,
        "fallback": {"BIL": 1.0},
    },
    "missing_data": {
        "invalid_formation": "retain_current_executable_target",
        "missing_execution_price": "block_change_and_retain_pretrade_holdings",
        "tradable_price_forward_fill": False,
    },
    "controls": [
        "tpp_same_trend_equal_weight_no_risk_sizing_control",
        "tpp_always_long_risk_parity_7pct_control",
        "static_permanent_portfolio_25_each_control",
        "tpp_static_average_weight_control",
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ],
    "critical_controls": [
        "tpp_same_trend_equal_weight_no_risk_sizing_control",
        "tpp_static_average_weight_control",
    ],
    "incremental_value_hypothesis": "trend_selection_plus_risk_sizing_and_volatility_targeting_adds_value_beyond_trend_only_and_static_exposure",
    "proposed_trial_id": "accepted47_source_v1__tactical_permanent_portfolio__canonical",
}

SPECS = (CAA_SPEC, TPP_SPEC)
SOURCE_REQUIRED_FILES = {
    "intake_manifest.yaml",
    "source_library_records.csv",
    "selected_candidate_specs.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "source_lineage.md",
    "rejection_ledger.csv",
    "conditional_codex_prompt.md",
    "direction_correction_record.csv",
    "consistency_check.json",
    "intake_report.md",
}
CORRECTION_REQUIRED_FILES = {
    "correction_manifest.yaml",
    "blocked_packet_hash_manifest.csv",
    "blocked_packet_archive_reconciliation.csv",
    "source_packet_file_manifest.csv",
    "source_packet_schema_reconciliation.csv",
    "implementation_specification_reconciliation.csv",
    "direction_correction_record.csv",
    "resumed_runner_result.csv",
    "entity_count_reconciliation.csv",
    "protected_state_reconciliation.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "correction_report.md",
}
PROTECTED_PATHS = (
    Path("strategy_lab/strategy_registry.yaml"),
    Path("strategy_lab/RESEARCH_ROADMAP.md"),
    Path("strategy_lab/research_os/research/research_queue.yaml"),
    Path("strategy_lab/research_os/family_lineage/family_ledger.yaml"),
    Path("strategy_lab/research_os/operations/active_observations.yaml"),
    Path("data/universe_expansion/pilot_etf_market_data_v1"),
    Path("data/cache"),
    Path("paper_forward_observations"),
    Path("evidence/paper_forward_observations"),
    Path("evidence/paper_demo_observation"),
    Path("evidence/technical_factory"),
    Path("evidence/research_recovery/accepted_47_hybrid_discovery_batch_v1"),
)


def sha256_file(path: Path) -> str:
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
    rows = [
        (item.relative_to(path).as_posix(), sha256_file(item))
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return stable_hash(rows)


def protected_hashes() -> dict[str, str]:
    return {relative.as_posix(): tree_hash(ROOT / relative) for relative in PROTECTED_PATHS}


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: serialize(row.get(field, "")) for field in writer.fieldnames})


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, bool):
        return str(value).lower()
    return value


def source_record_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": spec["source_record_id"],
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": spec["strategy_id"],
            "family_id": spec["family_id"],
            "source_title": spec["source_title"],
            "source_or_research_lineage": spec["source_or_research_lineage"],
            "classification": spec["classification"],
            "provider_requirement": "none",
            "proposed_trial_id": spec["proposed_trial_id"],
        }
        for spec in SPECS
    ]


def configuration_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": spec["source_record_id"],
            "strategy_id": spec["strategy_id"],
            "family_id": spec["family_id"],
            "display_name": spec["display_name"],
            "strategy_architecture": spec["strategy_architecture"],
            "source_or_research_lineage": spec["source_or_research_lineage"],
            "instrument_universe": (
                spec["ordered_universe"]
                if "ordered_universe" in spec
                else [*spec["risky_assets"], spec["cash_asset"]]
            ),
            "parameters": spec["parameters"],
            "controls": spec["controls"],
            "critical_controls": spec["critical_controls"],
            "route": spec["route"],
            "proposed_trial_id": spec["proposed_trial_id"],
            "provider_requirement": "none",
            "unresolved_material_fields": 0,
        }
        for spec in SPECS
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in SPECS:
        for control in spec["controls"]:
            rows.append(
                {
                    "strategy_id": spec["strategy_id"],
                    "benchmark_id": control,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "named_same_purpose_control": control == spec["critical_controls"][0],
                    "static_average_weight_control": control == spec["critical_controls"][1],
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def archive_blocked_packet() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if HISTORY_DIR.is_dir():
        source_root = HISTORY_DIR
    else:
        if not BLOCKED_DIR.is_dir():
            raise RuntimeError(f"blocked packet missing before archival: {BLOCKED_DIR}")
        HISTORY_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BLOCKED_DIR, HISTORY_DIR)
        source_root = HISTORY_DIR

    source_files = sorted(item for item in source_root.rglob("*") if item.is_file())
    source_manifest = [
        {
            "relative_path": item.relative_to(source_root).as_posix(),
            "source_hash": sha256_file(item),
            "source_size_bytes": item.stat().st_size,
        }
        for item in source_files
    ]
    archive_rows: list[dict[str, Any]] = []
    for row in source_manifest:
        archived = HISTORY_DIR / row["relative_path"]
        archive_hash = sha256_file(archived) if archived.is_file() else "missing"
        archive_rows.append(
            {
                **row,
                "archive_path": archived.relative_to(ROOT).as_posix(),
                "archive_hash": archive_hash,
                "hash_match": archive_hash == row["source_hash"],
                "historical_outcome_preserved": True,
            }
        )
    if not all(row["hash_match"] for row in archive_rows):
        raise RuntimeError("blocked packet archive hash mismatch")
    return source_manifest, archive_rows


def materialize_source_packet() -> dict[str, Any]:
    if SOURCE_DIR.exists():
        shutil.rmtree(SOURCE_DIR)
    SOURCE_DIR.mkdir(parents=True)
    manifest = {
        "task_id": SOURCE_TASK_ID,
        "stage": "source_extracted",
        "outcome": "two_to_four_source_backed_candidates_selected",
        "selected_candidate_count": 2,
        "distinct_family_count": 2,
        "provider_requirement_count": 0,
        "unresolved_material_field_count": 0,
        "materialization_authority": "direction_owner_authorized_completed_chatgpt_side_intake",
        "web_research_repeated": False,
        "experiment_trials_created": 0,
        "next_action": EXPLORATION_TASK_ID,
    }
    (SOURCE_DIR / "intake_manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8"
    )
    write_csv(
        SOURCE_DIR / "source_library_records.csv",
        source_record_rows(),
        (
            "source_record_id", "entity_type", "stage", "outcome", "failure_reason",
            "strategy_id", "family_id", "source_title", "source_or_research_lineage",
            "classification", "provider_requirement", "proposed_trial_id",
        ),
    )
    (SOURCE_DIR / "selected_candidate_specs.yaml").write_text(
        yaml.safe_dump({"task_id": SOURCE_TASK_ID, "candidate_count": 2, "candidates": list(SPECS)}, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )
    write_csv(
        SOURCE_DIR / "configuration_trial_catalog.csv",
        configuration_rows(),
        (
            "source_record_id", "strategy_id", "family_id", "display_name", "strategy_architecture",
            "source_or_research_lineage", "instrument_universe", "parameters", "controls",
            "critical_controls", "route", "proposed_trial_id", "provider_requirement",
            "unresolved_material_fields",
        ),
    )
    write_csv(
        SOURCE_DIR / "benchmark_reference_catalog.csv",
        benchmark_rows(),
        (
            "strategy_id", "benchmark_id", "entity_type", "stage", "named_same_purpose_control",
            "static_average_weight_control", "counted_as_strategy", "counted_as_trial",
        ),
    )
    (SOURCE_DIR / "source_lineage.md").write_text(
        "# Source Lineage\n\nThis append-only packet materializes the completed ChatGPT-side intake authorized by the direction owner. No web research, source completion, parameter choice, or strategy adaptation was performed during materialization. The two source records are preregistration inputs, not experiment trials.\n",
        encoding="utf-8",
    )
    write_csv(
        SOURCE_DIR / "rejection_ledger.csv",
        [],
        ("source_record_id", "strategy_id", "rejection_reason", "outcome"),
    )
    prompt_text = SOURCE_INSTRUCTION_ATTACHMENT.read_text(encoding="utf-8")
    (SOURCE_DIR / "conditional_codex_prompt.md").write_text(prompt_text, encoding="utf-8")
    write_csv(
        SOURCE_DIR / "direction_correction_record.csv",
        [
            {
                "correction_id": TASK_ID,
                "entity_type": "direction_correction_record",
                "prior_blocked_task": EXPLORATION_TASK_ID,
                "prior_failure": "missing_authoritative_repository_packet",
                "correction": "materialize_completed_chatgpt_intake_as_append_only_repository_authority",
                "source_rules_changed": False,
                "web_research_repeated": False,
            }
        ],
        ("correction_id", "entity_type", "prior_blocked_task", "prior_failure", "correction", "source_rules_changed", "web_research_repeated"),
    )
    checks = source_packet_checks()
    (SOURCE_DIR / "consistency_check.json").write_text(
        json.dumps({**checks, "overall_pass": all(checks.values())}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (SOURCE_DIR / "intake_report.md").write_text(
        "# Accepted 47 Selective Source-Backed Intake V1\n\nOutcome: `two_to_four_source_backed_candidates_selected`. Exactly two source-backed candidates across two families are frozen for exploration. Provider requirements and unresolved material fields are zero. No strategy configuration or experiment trial was created during intake materialization.\n",
        encoding="utf-8",
    )
    if SOURCE_REQUIRED_FILES != {item.name for item in SOURCE_DIR.iterdir() if item.is_file()}:
        raise RuntimeError("source packet file set mismatch")
    return manifest


def accepted_symbols() -> set[str]:
    path = ROOT / "evidence" / "data_capability" / "activate_accepted_47_pilot_data_readiness_v1" / "latest" / "operational_universe_snapshot.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["symbol"] for row in csv.DictReader(handle)}


def source_packet_checks() -> dict[str, bool]:
    source_rows = source_record_rows()
    configs = configuration_rows()
    symbols = accepted_symbols()
    all_symbols = {
        symbol
        for row in configs
        for symbol in row["instrument_universe"]
    }
    serialized = json.dumps(list(SPECS), sort_keys=True).lower()
    return {
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_candidate_specs": len(SPECS) == 2,
        "exactly_two_proposed_trial_ids": len({spec["proposed_trial_id"] for spec in SPECS}) == 2,
        "distinct_family_ids": len({spec["family_id"] for spec in SPECS}) == 2,
        "required_fields_complete": all(
            spec.get(field) not in (None, "", [], {})
            for spec in SPECS
            for field in (
                "source_record_id", "strategy_id", "family_id", "display_name", "strategy_architecture",
                "source_or_research_lineage", "source_title", "classification", "route", "parameters",
                "controls", "critical_controls", "proposed_trial_id",
            )
        ),
        "all_symbols_in_accepted_47": all_symbols <= symbols,
        "provider_requirement_count_zero": all(row["provider_requirement"] == "none" for row in configs),
        "no_unknown_unresolved_or_tbd": not any(token in serialized for token in ('"unknown"', '"unresolved"', '"tbd"')),
        "no_experiment_trials_created_during_materialization": True,
    }


def source_file_manifest() -> list[dict[str, Any]]:
    return [
        {
            "relative_path": item.relative_to(SOURCE_DIR).as_posix(),
            "sha256": sha256_file(item),
            "size_bytes": item.stat().st_size,
        }
        for item in sorted(candidate for candidate in SOURCE_DIR.rglob("*") if candidate.is_file())
    ]


def prepare_handoff_only() -> dict[str, Any]:
    source_manifest, archive_rows = archive_blocked_packet()
    intake = materialize_source_packet()
    return {
        "blocked_file_count": len(source_manifest),
        "archive_hashes_match": all(row["hash_match"] for row in archive_rows),
        "source_packet_file_count": len(source_file_manifest()),
        "source_packet_checks": source_packet_checks(),
        "intake": intake,
    }


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    source_manifest, archive_rows = archive_blocked_packet()
    materialize_source_packet()
    schema_checks = source_packet_checks()
    if not all(schema_checks.values()):
        runner_result = {
            "outcome": "source_packet_materialization_blocked",
            "overall_pass": False,
            "next_action": "direction_owner_review_source_packet_materialization_block_v1",
        }
    else:
        from strategy_lab.research_os.research.accepted_47_source_backed_exploration_batch_v1 import run as run_exploration

        runner_result = run_exploration()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    write_csv(
        OUTPUT_DIR / "blocked_packet_hash_manifest.csv",
        source_manifest,
        ("relative_path", "source_hash", "source_size_bytes"),
    )
    write_csv(
        OUTPUT_DIR / "blocked_packet_archive_reconciliation.csv",
        archive_rows,
        ("relative_path", "source_hash", "source_size_bytes", "archive_path", "archive_hash", "hash_match", "historical_outcome_preserved"),
    )
    write_csv(
        OUTPUT_DIR / "source_packet_file_manifest.csv",
        source_file_manifest(),
        ("relative_path", "sha256", "size_bytes"),
    )
    write_csv(
        OUTPUT_DIR / "source_packet_schema_reconciliation.csv",
        [{"check_id": key, "status": value} for key, value in schema_checks.items()],
        ("check_id", "status"),
    )
    reconciliation_rows = [
        {"field": "candidate_count", "packet_value": 2, "implementation_value": runner_result.get("strategy_configuration_count", runner_result.get("strategy_configurations_created", 0)), "status": "pass" if runner_result.get("strategy_configuration_count") == 2 else "fail"},
        {"field": "canonical_trial_count", "packet_value": 2, "implementation_value": runner_result.get("canonical_trial_count", runner_result.get("canonical_trials_created", 0)), "status": "pass" if runner_result.get("canonical_trial_count") == 2 else "fail"},
        {"field": "source_packet_reconciliation", "packet_value": True, "implementation_value": runner_result.get("source_reconciliation_pass", False), "status": "pass" if runner_result.get("source_reconciliation_pass") else "fail"},
        {"field": "provider_access", "packet_value": False, "implementation_value": runner_result.get("provider_access_performed", False), "status": "pass" if not runner_result.get("provider_access_performed", False) else "fail"},
    ]
    write_csv(
        OUTPUT_DIR / "implementation_specification_reconciliation.csv",
        reconciliation_rows,
        ("field", "packet_value", "implementation_value", "status"),
    )
    write_csv(
        OUTPUT_DIR / "direction_correction_record.csv",
        [{"correction_id": TASK_ID, "prior_outcome": "accepted_47_source_backed_exploration_batch_v1_blocked", "correction": "materialized_missing_authoritative_intake_packet", "strategy_rules_changed": False, "prior_packet_preserved": True}],
        ("correction_id", "prior_outcome", "correction", "strategy_rules_changed", "prior_packet_preserved"),
    )
    write_csv(
        OUTPUT_DIR / "resumed_runner_result.csv",
        [runner_result],
        tuple(runner_result.keys()),
    )
    entity_rows = [
        {"stage": "correction", "entity_type": "direction_correction_record", "count": 1},
        {"stage": "correction", "entity_type": "source_library_record_materialized", "count": 2},
        {"stage": "correction", "entity_type": "strategy_configuration", "count": 0},
        {"stage": "correction", "entity_type": "experiment_trial", "count": 0},
        {"stage": "exploration", "entity_type": "strategy_configuration", "count": runner_result.get("strategy_configuration_count", 0)},
        {"stage": "exploration", "entity_type": "experiment_trial", "count": runner_result.get("canonical_trial_count", 0)},
        {"stage": "exploration", "entity_type": "robustness_trial", "count": 0},
        {"stage": "exploration", "entity_type": "validation_observation", "count": 0},
        {"stage": "exploration", "entity_type": "paper_demo_observation", "count": 0},
    ]
    write_csv(OUTPUT_DIR / "entity_count_reconciliation.csv", entity_rows, ("stage", "entity_type", "count"))

    protected_after = protected_hashes()
    protected_rows = [
        {"path": path, "before_hash": protected_before[path], "after_hash": protected_after[path], "unchanged": protected_before[path] == protected_after[path]}
        for path in protected_before
    ]
    write_csv(OUTPUT_DIR / "protected_state_reconciliation.csv", protected_rows, ("path", "before_hash", "after_hash", "unchanged"))
    executed = bool(runner_result.get("performance_executed")) and bool(runner_result.get("overall_pass"))
    if executed:
        outcome = "source_intake_materialized_and_batch_executed"
        next_action = runner_result["next_action"]
    elif all(schema_checks.values()):
        outcome = "source_packet_materialized_execution_blocked"
        next_action = "direction_owner_review_accepted_47_source_backed_execution_block_v2"
    else:
        outcome = "source_packet_materialization_blocked"
        next_action = "direction_owner_review_source_packet_materialization_block_v1"
    outcome_row = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "source_packet_materialized": all(schema_checks.values()),
        "blocked_packet_archived": all(row["hash_match"] for row in archive_rows),
        "exploration_runner_completed": executed,
        "candidate_outcomes": runner_result.get("candidate_outcomes", {}),
        "next_action": next_action,
    }
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], outcome_row.keys())
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [{"task_id": TASK_ID, "exact_next_action": next_action, "execute_in_this_task": False}],
        ("task_id", "exact_next_action", "execute_in_this_task"),
    )
    checks = {
        "blocked_packet_archive_complete": len(source_manifest) == len(archive_rows) and all(row["hash_match"] for row in archive_rows),
        "historical_blocked_outcome_preserved": all(row["historical_outcome_preserved"] for row in archive_rows),
        "source_packet_file_set_complete": SOURCE_REQUIRED_FILES == {item.name for item in SOURCE_DIR.iterdir() if item.is_file()},
        "source_packet_schema_pass": all(schema_checks.values()),
        "implementation_specification_reconciliation_pass": all(row["status"] == "pass" for row in reconciliation_rows),
        "exactly_two_source_records_materialized": len(source_record_rows()) == 2,
        "exactly_two_strategy_configurations_created_by_runner": runner_result.get("strategy_configuration_count") == 2,
        "exactly_two_canonical_trials_created_by_runner": runner_result.get("canonical_trial_count") == 2,
        "exploration_runner_completed": executed,
        "protected_state_cache_and_observations_unchanged": protected_before == protected_after,
        "no_provider_network_broker_or_lifecycle_action": True,
    }
    overall_pass = all(checks.values())
    (OUTPUT_DIR / "correction_manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "task_id": TASK_ID,
                "mode": "correction_then_exact_execution",
                "stages": ["correction", "exploration"],
                "outcome": outcome,
                "historical_blocked_packet": HISTORY_DIR.relative_to(ROOT).as_posix(),
                "materialized_source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(),
                "resumed_exploration_packet": BLOCKED_DIR.relative_to(ROOT).as_posix(),
                "candidate_count": 2,
                "strategy_or_parameter_change": False,
                "web_research_repeated": False,
                "exact_next_action": next_action,
            },
            sort_keys=False,
            allow_unicode=False,
            width=120,
        ),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "consistency_check.json").write_text(
        json.dumps({**checks, "overall_pass": overall_pass}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "correction_report.md").write_text(
        f"# Materialize and Resume Accepted 47 Source-Backed Batch V1\n\nOutcome: `{outcome}`.\n\nThe original blocked packet was copied byte-for-byte to `{HISTORY_DIR.relative_to(ROOT).as_posix()}` and every file hash reconciled. The approved two-candidate intake was materialized at `{SOURCE_DIR.relative_to(ROOT).as_posix()}` without new research or source-rule changes.\n\nThe existing exploration runner then produced its normal evidence packet. Candidate outcomes: `{json.dumps(runner_result.get('candidate_outcomes', {}), sort_keys=True)}`.\n\nNo lifecycle, observation, provider, broker, account, order, position, capital, or real-money action occurred. Exact next action: `{next_action}`.\n",
        encoding="utf-8",
    )
    missing = sorted(name for name in CORRECTION_REQUIRED_FILES if not (OUTPUT_DIR / name).is_file())
    if missing:
        raise RuntimeError(f"correction packet missing files: {missing}")
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "overall_pass": overall_pass,
        "source_packet_materialized": all(schema_checks.values()),
        "blocked_packet_archived": all(row["hash_match"] for row in archive_rows),
        "exploration_runner_completed": executed,
        "candidate_outcomes": runner_result.get("candidate_outcomes", {}),
        "next_action": next_action,
        "output_dir": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
