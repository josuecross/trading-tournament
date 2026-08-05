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
    native_etf_two_candidate_exploration_batch_v1 as exploration,
)
from strategy_lab.research_os.research import (
    native_etf_two_candidate_final_robustness_v1 as robustness,
)


TASK_ID = "design_faa_prospective_validation_v1"
MODE = "experiment-design"
STAGE = "validation"
DESIGN_ID = f"{TASK_ID}__design"
FUTURE_TRIAL_ID = "faa_4m_top3_prospective_validation_v1__forward"
PARENT_TRIAL_ID = robustness.FAA_TRIAL
EXPLORATION_TRIAL_ID = exploration.FAA_TRIAL
OUTPUT_DIR = ROOT / "evidence" / "experiment_design" / TASK_ID / "latest"
EXPLORATION_EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "native_etf_two_candidate_exploration_batch_v1"
    / "latest"
)
ROBUSTNESS_EVIDENCE = (
    ROOT
    / "evidence"
    / "robustness"
    / "native_etf_two_candidate_final_robustness_v1"
    / "latest"
)
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\20597f9a-3603-4ce8-b7c1-b945e72244a6\pasted-text.txt"
)

STRATEGY_ID = exploration.FAA_ID
VIX_STRATEGY_ID = exploration.VIX_ID
FAMILY_ID = "generalized_momentum_flexible_asset_allocation"
DISPLAY_NAME = "Flexible Asset Allocation 4-Month Top-Three"
ARCHITECTURE = (
    "monthly_return_volatility_correlation_rank_with_absolute_momentum"
)
SOURCE_LINEAGE = (
    "targeted_native_etf_source_refresh_v1:"
    "src_keller_vanputten_faa_4m_top3_v1"
)
UNIVERSE = ("SPY", "EFA", "VWO", "SHY", "AGG", "GSG", "VNQ")
COMPARATORS = (
    STRATEGY_ID,
    "faa_4m_return_only_top3_control",
    "faa_4m_return_volatility_top3_no_correlation_control",
    "faa_full_period_average_weight_static_control",
    "monthly_equal_weight_7asset_control",
    "SPY_buy_and_hold",
    "SHY_buy_and_hold",
)
CRITICAL_CONTROLS = (
    "faa_4m_return_only_top3_control",
    "faa_4m_return_volatility_top3_no_correlation_control",
    "faa_full_period_average_weight_static_control",
)
STATIC_WEIGHTS = {
    "SPY": 0.1284041394335510,
    "EFA": 0.0644063180827883,
    "VWO": 0.0629084967320259,
    "SHY": 0.3246868191721107,
    "AGG": 0.1866149237472829,
    "GSG": 0.1266339869281042,
    "VNQ": 0.1063453159041368,
}
STATIC_WEIGHT_TEXT = {
    "SPY": "0.1284041394335510",
    "EFA": "0.0644063180827883",
    "VWO": "0.0629084967320259",
    "SHY": "0.3246868191721107",
    "AGG": "0.1866149237472829",
    "GSG": "0.1266339869281042",
    "VNQ": "0.1063453159041368",
}
PRIMARY_COST_BPS = 5.0
DIAGNOSTIC_COST_BPS = (0.0, 10.0)
MINIMUM_MONTHS = 24
MINIMUM_INTERVALS = 24
MINIMUM_DIFFERENTIATION_MONTHS = 6
MAXIMUM_MONTHS = 36
DIFFERENTIATION_TOLERANCE = 1e-12
DESIGN_TIMESTAMP = "2026-07-30T00:00:00-06:00"

OUTCOME_COMPLETED = "prospective_validation_design_completed"
OUTCOME_BLOCKED = "prospective_validation_design_blocked"
NEXT_COMPLETED = "activate_faa_prospective_validation_v1"
NEXT_BLOCKED = "direction_owner_review_faa_prospective_design_block_v1"
DESIGN_FAILURE_REASONS = (
    "lineage_reconciliation_failure",
    "parameter_reconciliation_failure",
    "control_reconciliation_failure",
    "methodology_failure",
)
FUTURE_OUTCOMES = (
    "validation_positive",
    "validation_mixed",
    "validation_failed",
    "validation_inconclusive_insufficient_component_differentiation",
    "validation_data_or_methodology_blocked",
)
FUTURE_FAILURE_REASONS = (
    "weak_vs_return_only_control",
    "weak_correlation_component",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "weak_component_attribution",
    "weak_return",
    "data_or_comparability_failure",
    "methodology_failure",
)

REQUIRED_OUTPUTS = {
    "design_manifest.yaml",
    "experiment_design_record.csv",
    "future_trial_specification.yaml",
    "strategy_and_lineage_reconciliation.csv",
    "frozen_parameter_specification.csv",
    "required_symbol_scope.csv",
    "prospective_daily_snapshot_schema.csv",
    "prospective_monthly_formation_schema.csv",
    "portfolio_and_control_definitions.csv",
    "archived_static_weight_reconciliation.csv",
    "activation_boundary_rules.csv",
    "minimum_observation_requirements.csv",
    "component_differentiation_definition.csv",
    "monthly_checkpoint_schema.csv",
    "future_validation_outcome_gates.csv",
    "future_failure_reasons.csv",
    "activation_readiness_checklist.csv",
    "vix_fix_deferred_state_reconciliation.csv",
    "process_task_log.csv",
    "next_actions.csv",
    "consistency_check.json",
    "prospective_validation_design.md",
}

PROTECTED_PATHS = tuple(
    dict.fromkeys(
        (
            *robustness.PROTECTED_STATE_PATHS,
            *robustness.PROTECTED_EVIDENCE_PATHS,
            exploration.CACHE_PATH,
            EXPLORATION_EVIDENCE,
            ROBUSTNESS_EVIDENCE,
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


def snapshot_hashes() -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in PROTECTED_PATHS}


def reset_output() -> None:
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


def one_row(path: Path, predicate: Any) -> dict[str, str]:
    matches = [row for row in read_csv(path) if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one authoritative row in {path}")
    return matches[0]


def parse_json_field(row: dict[str, str], field: str) -> Any:
    value = row.get(field, "")
    return json.loads(value) if value else None


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.16g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def fields_for(rows: list[dict[str, Any]], leading: Iterable[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: Iterable[str],
) -> None:
    fields = fields_for(rows, leading)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
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


def reconcile_authoritative_evidence() -> dict[str, Any]:
    exploration_strategy = one_row(
        EXPLORATION_EVIDENCE / "strategy_cards.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    exploration_trial = one_row(
        EXPLORATION_EVIDENCE / "trial_ledger.csv",
        lambda row: row.get("trial_id") == EXPLORATION_TRIAL_ID,
    )
    exploration_outcome = one_row(
        EXPLORATION_EVIDENCE / "outcome_summary.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    robustness_strategy = one_row(
        ROBUSTNESS_EVIDENCE / "strategy_cards.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    robustness_trial = one_row(
        ROBUSTNESS_EVIDENCE / "trial_ledger.csv",
        lambda row: row.get("trial_id") == PARENT_TRIAL_ID,
    )
    robustness_outcome = one_row(
        ROBUSTNESS_EVIDENCE / "outcome_summary.csv",
        lambda row: row.get("strategy_id") == STRATEGY_ID,
    )
    vix_outcome = one_row(
        ROBUSTNESS_EVIDENCE / "outcome_summary.csv",
        lambda row: row.get("strategy_id") == VIX_STRATEGY_ID,
    )
    static_rows = [
        row
        for row in read_csv(
            ROBUSTNESS_EVIDENCE / "archived_control_parameter_reconciliation.csv"
        )
        if row.get("strategy_id") == STRATEGY_ID
        and row.get("control_id")
        == "faa_full_period_average_weight_static_control"
    ]
    bootstrap_rows = [
        row
        for row in read_csv(
            ROBUSTNESS_EVIDENCE / "paired_block_bootstrap_results.csv"
        )
        if row.get("strategy_id") == STRATEGY_ID
    ]
    exploration_consistency = json.loads(
        (EXPLORATION_EVIDENCE / "consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    robustness_consistency = json.loads(
        (ROBUSTNESS_EVIDENCE / "consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    exploration_parameters = parse_json_field(exploration_strategy, "parameters")
    robustness_parameters = parse_json_field(robustness_strategy, "parameters")
    exploration_controls = tuple(
        parse_json_field(exploration_strategy, "benchmark_or_control")
    )
    static_map = {
        row["asset"]: float(row["archived_target_weight"]) for row in static_rows
    }
    bootstrap_map = {row["comparison_id"]: row for row in bootstrap_rows}

    identity_pass = bool(
        exploration_strategy["family_id"] == FAMILY_ID
        and exploration_strategy["display_name"] == DISPLAY_NAME
        and exploration_strategy["strategy_architecture"] == ARCHITECTURE
        and exploration_strategy["source_or_research_lineage"] == SOURCE_LINEAGE
        and exploration_strategy["instrument_universe"] == "|".join(UNIVERSE)
        and robustness_strategy["family_id"] == FAMILY_ID
        and robustness_strategy["strategy_architecture"] == ARCHITECTURE
    )
    lineage_pass = bool(
        exploration_trial["trial_id"] == EXPLORATION_TRIAL_ID
        and exploration_trial["parent_trial_id"] == ""
        and exploration_trial["outcome"]
        == "exploratory_followup_candidate_standalone"
        and exploration_outcome["standalone_gate_pass"] == "true"
        and exploration_outcome["diversifier_gate_pass"] == "false"
        and robustness_trial["trial_id"] == PARENT_TRIAL_ID
        and robustness_trial["parent_trial_id"] == EXPLORATION_TRIAL_ID
        and robustness_trial["route"] == "standalone_only"
        and robustness_trial["outcome"] == "robustness_positive"
        and robustness_outcome["interpretation"]
        == "ready_for_prospective_validation_design_standalone_asset_allocation"
        and robustness_outcome["independent_validation_claimed"] == "false"
        and robustness_outcome["paper_demo_eligibility_claimed"] == "false"
    )
    parameter_pass = bool(
        exploration_parameters
        == {
            "absolute_momentum_fallback": "SHY",
            "correlation_rank_weight": 0.5,
            "formation_months": 4,
            "return_rank_weight": 1.0,
            "selected_count": 3,
            "volatility_rank_weight": 0.5,
        }
        and robustness_parameters == exploration_parameters
    )
    control_pass = bool(
        set(exploration_controls)
        == {
            "faa_4m_return_only_top3_control",
            "faa_4m_return_volatility_top3_no_correlation_control",
            "monthly_equal_weight_7asset_control",
            "faa_full_period_average_weight_static_control",
            "SPY_buy_and_hold",
            "SHY_buy_and_hold",
        }
        and set(static_map) == set(UNIVERSE)
        and all(
            math.isclose(
                static_map[symbol],
                STATIC_WEIGHTS[symbol],
                rel_tol=0.0,
                abs_tol=1e-15,
            )
            for symbol in UNIVERSE
        )
        and math.isclose(sum(static_map.values()), 1.0, abs_tol=1e-12)
    )
    bootstrap_pass = bool(
        set(bootstrap_map)
        == {
            "faa_4m_return_only_top3_control",
            "faa_4m_return_volatility_top3_no_correlation_control",
            "faa_full_period_average_weight_static_control",
        }
        and all(row["independent_validation_claimed"] == "false" for row in bootstrap_rows)
        and all(row["used_for_strategy_change"] == "false" for row in bootstrap_rows)
    )
    vix_deferred_pass = bool(
        vix_outcome["outcome"] == "robustness_mixed"
        and vix_outcome["failure_reason"] == "period_instability"
        and vix_outcome["interpretation"]
        == "historically_promising_not_ready_for_prospective_validation"
        and vix_outcome["prospective_validation_started"] == "false"
    )
    return {
        "identity_pass": identity_pass,
        "lineage_pass": lineage_pass,
        "parameter_pass": parameter_pass,
        "control_pass": control_pass,
        "bootstrap_pass": bootstrap_pass,
        "vix_deferred_pass": vix_deferred_pass,
        "prior_consistency_pass": bool(
            exploration_consistency["overall_pass"]
            and robustness_consistency["overall_pass"]
        ),
        "exploration_strategy": exploration_strategy,
        "exploration_trial": exploration_trial,
        "exploration_outcome": exploration_outcome,
        "robustness_trial": robustness_trial,
        "robustness_outcome": robustness_outcome,
        "vix_outcome": vix_outcome,
        "static_rows": static_rows,
        "bootstrap_rows": bootstrap_rows,
    }


def classify_design(reconciliation: dict[str, Any]) -> tuple[str, str, str]:
    if not (
        reconciliation["identity_pass"]
        and reconciliation["lineage_pass"]
        and reconciliation["prior_consistency_pass"]
    ):
        return OUTCOME_BLOCKED, "lineage_reconciliation_failure", NEXT_BLOCKED
    if not reconciliation["parameter_pass"]:
        return OUTCOME_BLOCKED, "parameter_reconciliation_failure", NEXT_BLOCKED
    if not reconciliation["control_pass"]:
        return OUTCOME_BLOCKED, "control_reconciliation_failure", NEXT_BLOCKED
    if not (
        reconciliation["bootstrap_pass"]
        and reconciliation["vix_deferred_pass"]
    ):
        return OUTCOME_BLOCKED, "methodology_failure", NEXT_BLOCKED
    return OUTCOME_COMPLETED, "", NEXT_COMPLETED


def future_trial_specification() -> dict[str, Any]:
    return {
        "record_status": "frozen_not_activated",
        "record_execution_status": "future_specification_not_executed",
        "trial_id": FUTURE_TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "prospective_validation_variant",
        "changed_fields_from_parent": "prospective_evaluation_boundary_only",
        "route": "standalone_only",
        "prospective_claim": (
            "The full FAA score's volatility and correlation components improve "
            "the prospective risk-adjusted and downside behavior of the standalone "
            "portfolio beyond return-only momentum, return-plus-volatility without "
            "correlation, and static average asset exposure."
        ),
        "claim_limits": {
            "higher_CAGR_than_return_only_claimed": False,
            "guaranteed_absolute_return_claimed": False,
            "standalone_alpha_claimed": False,
            "superiority_to_every_equity_benchmark_claimed": False,
            "independent_historical_validation_claimed": False,
            "paper_demo_eligibility_claimed": False,
            "historical_return_only_higher_CAGR_limitation_preserved": True,
        },
        "flags": {
            "formula_changed": False,
            "parameters_changed": False,
            "instruments_changed": False,
            "mappings_changed": False,
            "execution_changed": False,
            "controls_changed": False,
            "cost_model_changed": False,
            "optimization_performed": False,
            "historical_backfill_permitted": False,
            "validation_evidence_observed_before_activation": False,
        },
        "universe": list(UNIVERSE),
        "instrument_mappings": {
            "US_broad_equity": "SPY",
            "developed_ex_US_equity": "EFA",
            "aggregate_bonds": "AGG",
        },
        "formation": {
            "frequency": "completed_month_end",
            "lookback": "preceding_four_completed_calendar_months",
            "return_formula": (
                "month_end_close_t/month_end_close_t_minus_4_completed_months-1"
            ),
            "volatility": (
                "sample_standard_deviation_daily_total_returns_same_interval"
            ),
            "volatility_ddof": 1,
            "correlation": (
                "Pearson_daily_return_correlation_same_interval_then_arithmetic_mean_of_six"
            ),
            "reduced_universe_ranking_permitted": False,
        },
        "ranking": {
            "return": "descending_rank_1_highest",
            "volatility": "ascending_rank_1_lowest",
            "average_correlation": "ascending_rank_1_lowest",
            "score": (
                "1.0*ReturnRank+0.5*VolatilityRank+0.5*CorrelationRank"
            ),
            "lower_score_better": True,
            "exact_score_tie_break": "lexical_ticker",
        },
        "selection_and_allocation": {
            "selected_count": 3,
            "slot_weight": 1.0 / 3.0,
            "absolute_momentum_test": "four_month_return_strictly_positive",
            "zero_or_negative_replacement": "SHY",
            "repeated_SHY_slots_aggregated": True,
            "pre_warmup_target": {"SHY": 1.0},
            "invalid_formation_rule": (
                "retain_previously_executable_holding_and_log_invalid_formation"
            ),
        },
        "execution": {
            "timestamp": "following_regular_session_close",
            "same_session_execution_permitted": False,
            "natural_drift": True,
            "explicit_zero_weights": True,
            "missing_execution_price_rule": (
                "block_changed_target_retain_pretrade_holding_and_log"
            ),
        },
        "comparators": list(COMPARATORS),
        "critical_controls": list(CRITICAL_CONTROLS),
        "static_control_weights": STATIC_WEIGHTS,
        "costs_bps_per_one_way_turnover": {
            "primary": PRIMARY_COST_BPS,
            "diagnostics": list(DIAGNOSTIC_COST_BPS),
            "cost_diagnostics_create_trials": False,
        },
        "prospective_boundary": {
            "start_rule": (
                "valid_US_regular_trading_session_strictly_after_activation_and_immutable_initialization"
            ),
            "selected_from_market_conditions": False,
            "retrospective_execution_or_performance_record_permitted": False,
            "initialization_label": (
                "initialization_state_input_not_validation_performance"
            ),
            "gap_after_historical_robustness_end_backfill_permitted": False,
            "old_returns_as_validation_observations_permitted": False,
            "initialization_counts_as_completed_formation": False,
            "retrospective_validation_NAV_permitted": False,
        },
        "minimum_evidence": {
            "minimum_completed_calendar_months": MINIMUM_MONTHS,
            "minimum_completed_monthly_holding_intervals": MINIMUM_INTERVALS,
            "minimum_differentiation_months_vs_return_only": (
                MINIMUM_DIFFERENTIATION_MONTHS
            ),
            "minimum_differentiation_months_vs_no_correlation": (
                MINIMUM_DIFFERENTIATION_MONTHS
            ),
            "hard_maximum_completed_calendar_months": MAXIMUM_MONTHS,
            "decision_boundary": "later_of_all_minimum_requirements",
            "early_favorable_stop_permitted": False,
            "insufficient_differentiation_outcome": (
                "validation_inconclusive_insufficient_component_differentiation"
            ),
        },
        "differentiation_definition": {
            "basis": "post_fallback_target_vector",
            "distance": "sum_absolute_weight_difference",
            "strict_threshold": DIFFERENTIATION_TOLERANCE,
            "comparison": "distance_greater_than_threshold",
        },
        "future_outcomes": list(FUTURE_OUTCOMES),
        "validated_claim_if_positive": (
            "exact_faa_4m_top3_standalone_configuration_under_prospective_snapshot_data"
        ),
        "automatic_paper_demo_eligibility": False,
        "lifecycle_change_authorized": False,
        "broker_or_real_money_authorization": False,
    }


def lineage_rows(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": 1,
            "record_id": STRATEGY_ID,
            "record_type": "strategy_configuration",
            "stage": "exploration",
            "role": "frozen_strategy_identity",
            "outcome": "carried_forward_unchanged",
            "parent_id": "",
            "route": "standalone_only",
            "evidence_path": relative(
                EXPLORATION_EVIDENCE / "strategy_cards.csv"
            ),
            "reconciliation_pass": reconciliation["identity_pass"],
        },
        {
            "sequence": 2,
            "record_id": EXPLORATION_TRIAL_ID,
            "record_type": "experiment_trial",
            "stage": "exploration",
            "role": "canonical_exploration_parent",
            "outcome": "exploratory_followup_candidate_standalone",
            "parent_id": "",
            "route": "standalone_with_diversifier_diagnostic",
            "diversifier_gate_pass": False,
            "diversifier_route_reopen_permitted": False,
            "evidence_path": relative(EXPLORATION_EVIDENCE / "trial_ledger.csv"),
            "reconciliation_pass": reconciliation["lineage_pass"],
        },
        {
            "sequence": 3,
            "record_id": PARENT_TRIAL_ID,
            "record_type": "experiment_trial",
            "stage": "robustness",
            "role": "final_same_period_historical_parent",
            "outcome": "robustness_positive",
            "parent_id": EXPLORATION_TRIAL_ID,
            "route": "standalone_only",
            "interpretation": (
                "ready_for_prospective_validation_design_standalone_asset_allocation"
            ),
            "independent_validation_claimed": False,
            "paper_demo_eligibility_claimed": False,
            "further_same_period_FAA_diagnostics_authorized": False,
            "evidence_path": relative(ROBUSTNESS_EVIDENCE / "trial_ledger.csv"),
            "reconciliation_pass": reconciliation["lineage_pass"],
        },
        {
            "sequence": 4,
            "record_id": FUTURE_TRIAL_ID,
            "record_type": "future_trial_specification",
            "stage": STAGE,
            "role": "prospective_validation_design",
            "outcome": "frozen_not_activated",
            "parent_id": PARENT_TRIAL_ID,
            "route": "standalone_only",
            "executed_trial": False,
            "validation_observations": 0,
            "evidence_path": relative(
                OUTPUT_DIR / "future_trial_specification.yaml"
            ),
            "reconciliation_pass": True,
        },
    ]


def parameter_rows() -> list[dict[str, Any]]:
    parameters = [
        ("formation_frequency", "completed_month_end", "formation"),
        ("lookback_months", 4, "formation"),
        ("return_measure", "four_completed_calendar_month_total_return", "formation"),
        ("volatility_measure", "sample_daily_total_return_standard_deviation", "formation"),
        ("volatility_ddof", 1, "formation"),
        ("correlation_measure", "Pearson_daily_total_return", "formation"),
        ("correlation_average_count", 6, "formation"),
        ("return_rank_direction", "descending", "ranking"),
        ("volatility_rank_direction", "ascending", "ranking"),
        ("correlation_rank_direction", "ascending", "ranking"),
        ("return_rank_weight", 1.0, "score"),
        ("volatility_rank_weight", 0.5, "score"),
        ("correlation_rank_weight", 0.5, "score"),
        ("selected_count", 3, "allocation"),
        ("slot_weight", 1.0 / 3.0, "allocation"),
        ("absolute_momentum_operator", "strictly_positive", "allocation"),
        ("absolute_momentum_fallback", "SHY", "allocation"),
        ("score_tie_break", "lexical_ticker", "ranking"),
        ("execution", "following_regular_session_close", "execution"),
        ("natural_drift", True, "accounting"),
        ("primary_cost_bps_one_way", PRIMARY_COST_BPS, "cost"),
        ("diagnostic_costs_bps_one_way", list(DIAGNOSTIC_COST_BPS), "cost"),
        ("route", "standalone_only", "claim"),
    ]
    return [
        {
            "parameter_name": name,
            "frozen_value": value,
            "parameter_group": group,
            "prospective_change_permitted": False,
            "source": "authoritative_exploration_and_robustness_evidence",
        }
        for name, value, group in parameters
    ]


def symbol_rows() -> list[dict[str, Any]]:
    mapping = {
        "SPY": "US_broad_equity_mapping",
        "EFA": "developed_ex_US_equity_mapping",
        "AGG": "aggregate_bonds_mapping",
    }
    return [
        {
            "symbol": symbol,
            "universe_order": index,
            "required_for_every_formation": True,
            "required_for_daily_valuation": True,
            "instrument_mapping_role": mapping.get(symbol, "frozen_direct_instrument"),
            "replacement_permitted": False,
            "reduced_universe_permitted": False,
            "prospective_snapshot_required": True,
        }
        for index, symbol in enumerate(UNIVERSE, start=1)
    ]


def schema_rows(
    fields: list[tuple[str, str, bool, str]],
) -> list[dict[str, Any]]:
    return [
        {
            "field_order": index,
            "field_name": name,
            "data_type": data_type,
            "required": required,
            "description": description,
            "immutable_after_capture": True,
            "original_rows_overwritable": False,
            "revision_handling": (
                "append_revision_alert_without_mutating_original_decision_record"
            ),
        }
        for index, (name, data_type, required, description) in enumerate(
            fields, start=1
        )
    ]


def daily_snapshot_rows() -> list[dict[str, Any]]:
    return schema_rows(
        [
            ("symbol", "string", True, "Frozen universe symbol"),
            ("market_date", "date", True, "Regular-session market date"),
            ("retrieval_timestamp_utc", "timestamp", True, "Immutable UTC retrieval time"),
            (
                "retrieval_timestamp_us_eastern",
                "timestamp",
                True,
                "Immutable U.S. Eastern retrieval time",
            ),
            ("provider", "string", True, "Authorized provider identity"),
            ("raw_source_identifier", "string", True, "Provider source record identity"),
            ("raw_hash", "sha256", True, "Hash of immutable raw bytes"),
            ("normalized_hash", "sha256", True, "Hash of normalized daily record"),
            ("adjusted_close", "decimal", True, "Frozen adjusted close"),
            ("data_version_identifier", "string", True, "Snapshot data version"),
            ("revision_status", "enum", True, "Original, unchanged, or revision alert"),
            (
                "validation_return_eligible",
                "boolean",
                True,
                "False for initialization-only rows",
            ),
            (
                "initialization_label",
                "string",
                True,
                "initialization_state_input_not_validation_performance when applicable",
            ),
        ]
    )


def monthly_formation_rows() -> list[dict[str, Any]]:
    return schema_rows(
        [
            ("formation_id", "string", True, "Unique immutable formation ID"),
            ("completed_formation_date", "date", True, "Completed month-end date"),
            ("four_month_start_date", "date", True, "Start of completed interval"),
            ("four_month_end_date", "date", True, "End of completed interval"),
            (
                "observation_count_by_asset",
                "json_object",
                True,
                "Daily observation count for every frozen asset",
            ),
            ("four_month_return_by_asset", "json_object", True, "Return_i values"),
            ("volatility_by_asset", "json_object", True, "Sample daily volatility"),
            (
                "pairwise_correlations",
                "json_object",
                True,
                "All 21 unique pairwise Pearson correlations",
            ),
            (
                "average_correlation_by_asset",
                "json_object",
                True,
                "Arithmetic mean of six correlations per asset",
            ),
            ("return_ranks", "json_object", True, "Descending return ranks"),
            ("volatility_ranks", "json_object", True, "Ascending volatility ranks"),
            ("correlation_ranks", "json_object", True, "Ascending correlation ranks"),
            ("combined_scores", "json_object", True, "Frozen FAA combined scores"),
            ("selected_slots", "json_array", True, "Three selected ticker slots"),
            ("SHY_replacements", "json_array", True, "Slot-level fallback decisions"),
            (
                "candidate_target_vector",
                "json_object",
                True,
                "Post-fallback aggregate target",
            ),
            (
                "comparator_target_vectors",
                "json_object",
                True,
                "Every comparator post-fallback target",
            ),
            (
                "intended_execution_session",
                "date",
                True,
                "Following regular session close",
            ),
            ("execution_status", "enum", True, "Executed or blocked"),
            ("blocked_reason", "string", False, "Missing data or execution reason"),
            ("initialization_turnover", "decimal", True, "Non-return initialization ledger"),
            ("monthly_rebalance_turnover", "decimal", True, "One-way turnover"),
            ("transaction_cost_by_ledger", "json_object", True, "0, 5, and 10 bps costs"),
            ("cost_adjusted_holdings", "json_object", True, "Post-cost holdings"),
            ("cost_adjusted_NAV", "json_object", True, "NAV by cost ledger"),
            (
                "differentiation_distance_by_control",
                "json_object",
                True,
                "Target-vector L1 distance against critical controls",
            ),
            ("data_revision_alert_ids", "json_array", True, "Append-only revision alerts"),
        ]
    )


def control_rows() -> list[dict[str, Any]]:
    definitions = {
        STRATEGY_ID: {
            "role": "candidate",
            "definition": (
                "full_FAA_score_return_1_0_volatility_0_5_correlation_0_5"
            ),
        },
        "faa_4m_return_only_top3_control": {
            "role": "critical_component_control",
            "definition": "rank_four_month_return_descending_only",
        },
        "faa_4m_return_volatility_top3_no_correlation_control": {
            "role": "critical_component_control",
            "definition": "score_return_rank_plus_0_5_volatility_rank",
        },
        "faa_full_period_average_weight_static_control": {
            "role": "critical_static_control",
            "definition": "monthly_rebalanced_frozen_archived_average_target_weights",
        },
        "monthly_equal_weight_7asset_control": {
            "role": "secondary_control",
            "definition": "monthly_equal_weight_frozen_seven_asset_universe",
        },
        "SPY_buy_and_hold": {
            "role": "secondary_context",
            "definition": "SPY_buy_and_hold",
        },
        "SHY_buy_and_hold": {
            "role": "secondary_context",
            "definition": "SHY_buy_and_hold",
        },
    }
    return [
        {
            "comparison_order": index,
            "portfolio_or_control_id": comparator,
            "entity_type": "benchmark_specification",
            "stage": "validation_design_only",
            "role": definitions[comparator]["role"],
            "definition": definitions[comparator]["definition"],
            "critical_control": comparator in CRITICAL_CONTROLS,
            "universe": "|".join(UNIVERSE),
            "following_session_close_execution": True,
            "primary_cost_bps": PRIMARY_COST_BPS,
            "prospective_change_permitted": False,
            "counted_as_strategy": False,
            "counted_as_executed_trial": False,
        }
        for index, comparator in enumerate(COMPARATORS, start=1)
    ]


def static_weight_rows(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    archived_rows = {
        row["asset"]: row for row in reconciliation["static_rows"]
    }
    return [
        {
            "control_id": "faa_full_period_average_weight_static_control",
            "symbol": symbol,
            "frozen_design_weight": STATIC_WEIGHT_TEXT[symbol],
            "archived_evidence_weight": archived_rows[symbol][
                "archived_target_weight"
            ],
            "absolute_difference": abs(
                STATIC_WEIGHTS[symbol]
                - float(archived_rows[symbol]["archived_target_weight"])
            ),
            "monthly_rebalance": True,
            "prospective_recalculation_permitted": False,
            "optimization_permitted": False,
            "reconciliation_pass": math.isclose(
                STATIC_WEIGHTS[symbol],
                float(archived_rows[symbol]["archived_target_weight"]),
                rel_tol=0.0,
                abs_tol=1e-15,
            ),
        }
        for symbol in UNIVERSE
    ]


def boundary_rows() -> list[dict[str, Any]]:
    rules = [
        ("after_activation", "start_strictly_after_future_activation_completes"),
        ("after_snapshots", "start_after_immutable_initialization_snapshots"),
        ("valid_session", "start_is_valid_US_regular_trading_session"),
        ("non_market_selected", "start_not_selected_from_market_conditions"),
        ("no_retrospective_execution", "no_retrospective_execution_record"),
        ("no_retrospective_NAV", "no_retrospective_validation_NAV"),
        (
            "initialization_only",
            "history_used_only_for_current_formation_ranks_targets_and_comparator_holdings",
        ),
        (
            "initialization_label",
            "initialization_state_input_not_validation_performance",
        ),
        ("no_gap_backfill", "gap_after_historical_robustness_not_backfilled"),
        ("no_old_returns", "historical_returns_not_validation_observations"),
        ("no_initialization_formation", "initialization_not_completed_formation"),
    ]
    return [
        {
            "rule_order": index,
            "rule_id": rule_id,
            "frozen_rule": rule,
            "exception_permitted": False,
            "activation_task_must_verify": True,
        }
        for index, (rule_id, rule) in enumerate(rules, start=1)
    ]


def minimum_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": "completed_calendar_months",
            "minimum_value": MINIMUM_MONTHS,
            "unit": "months",
            "decision_role": "minimum_boundary",
        },
        {
            "requirement_id": "completed_monthly_holding_intervals",
            "minimum_value": MINIMUM_INTERVALS,
            "unit": "intervals",
            "decision_role": "minimum_boundary",
        },
        {
            "requirement_id": "differentiation_vs_return_only",
            "minimum_value": MINIMUM_DIFFERENTIATION_MONTHS,
            "unit": "months",
            "decision_role": "minimum_boundary",
        },
        {
            "requirement_id": "differentiation_vs_no_correlation",
            "minimum_value": MINIMUM_DIFFERENTIATION_MONTHS,
            "unit": "months",
            "decision_role": "minimum_boundary",
        },
        {
            "requirement_id": "hard_maximum_calendar_months",
            "minimum_value": MAXIMUM_MONTHS,
            "unit": "months",
            "decision_role": "hard_maximum",
        },
    ]


def differentiation_rows() -> list[dict[str, Any]]:
    return [
        {
            "comparison_id": control,
            "candidate_vector": "post_fallback_candidate_target_vector",
            "control_vector": "post_fallback_control_target_vector",
            "distance_formula": "sum(abs(candidate_weight_i-control_weight_i))",
            "strict_threshold": DIFFERENTIATION_TOLERANCE,
            "differentiation_test": "distance > 1e-12",
            "minimum_differentiation_months": MINIMUM_DIFFERENTIATION_MONTHS,
            "hard_maximum_months": MAXIMUM_MONTHS,
            "insufficient_outcome": (
                "validation_inconclusive_insufficient_component_differentiation"
            ),
        }
        for control in CRITICAL_CONTROLS[:2]
    ]


def checkpoint_rows() -> list[dict[str, Any]]:
    fields = [
        ("checkpoint_id", "string"),
        ("checkpoint_timestamp", "timestamp"),
        ("elapsed_calendar_months", "integer"),
        ("completed_monthly_intervals", "integer"),
        ("differentiation_months_vs_return_only", "integer"),
        ("differentiation_months_vs_no_correlation", "integer"),
        ("candidate_NAV_by_cost", "json_object"),
        ("comparator_NAVs_by_cost", "json_object"),
        ("total_return_by_portfolio", "json_object"),
        ("annualized_volatility_when_meaningful", "json_object"),
        ("Sharpe_when_meaningful", "json_object"),
        ("maximum_drawdown", "json_object"),
        ("turnover", "json_object"),
        ("transaction_costs", "json_object"),
        ("selected_assets", "json_array"),
        ("SHY_replacement_count", "integer"),
        ("candidate_control_overlap", "json_object"),
        ("candidate_minus_control_returns_differentiation_months", "json_object"),
        ("data_gaps", "json_array"),
        ("blocked_executions", "json_array"),
        ("revision_alerts", "json_array"),
        ("invariant_results", "json_object"),
        ("decision_authorized", "boolean"),
    ]
    return [
        {
            "field_order": index,
            "field_name": field,
            "data_type": data_type,
            "required": True,
            "interim_rule_change_permitted": False,
            "outcome_gate_change_permitted": False,
        }
        for index, (field, data_type) in enumerate(fields, start=1)
    ]


def outcome_gate_rows() -> list[dict[str, Any]]:
    positive_conditions = [
        "all_data_timing_accounting_weight_and_exposure_invariants_pass",
        "at_least_24_months_and_24_completed_holding_intervals",
        "at_least_6_differentiation_months_vs_both_component_controls",
        "candidate_positive_total_return_at_5bps",
        "neither_return_only_nor_no_correlation_dominates_on_CAGR_Sharpe_drawdown",
        "materiality_vs_each_component_control_Sharpe_0_02_or_drawdown_0_01",
        "static_average_weights_do_not_dominate",
        "materiality_vs_static_Sharpe_0_02_or_drawdown_0_01",
        "return_only_differentiation_average_excess_nonnegative_and_win_rate_over_50pct",
        "no_correlation_differentiation_average_excess_nonnegative_and_win_rate_over_50pct",
        "at_10bps_candidate_positive_not_dominated_and_not_worse_than_both_component_controls_on_both_metrics",
        "no_unresolved_revision_missing_execution_or_reconciliation_issue_can_change_decision",
    ]
    mixed_conditions = [
        "candidate_remains_viable",
        "candidate_improves_at_least_one_major_risk_metric",
        "control_attribution_differentiation_cost_or_drawdown_evidence_conflicts",
    ]
    failed_conditions = [
        "return_only_or_no_correlation_dominates",
        "full_FAA_score_fails_materiality",
        "static_weights_explain_result",
        "candidate_worsens_both_Sharpe_and_drawdown",
        "cost_removes_advantage",
        "differentiation_months_show_unfavorable_component_evidence",
    ]
    return [
        {
            "future_outcome": "validation_positive",
            "decision_timing": "after_minimum_boundary_only",
            "conditions": positive_conditions,
            "validated_claim": (
                "exact_faa_4m_top3_standalone_configuration_under_prospective_snapshot_data"
            ),
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_mixed",
            "decision_timing": "after_minimum_boundary_only",
            "conditions": mixed_conditions,
            "validated_claim": "conflicting_prospective_evidence_only",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_failed",
            "decision_timing": "after_minimum_boundary_only",
            "conditions": failed_conditions,
            "validated_claim": "none",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": (
                "validation_inconclusive_insufficient_component_differentiation"
            ),
            "decision_timing": "at_hard_maximum_36_months",
            "conditions": [
                "fewer_than_6_differentiation_months_vs_either_component_control"
            ],
            "validated_claim": "none",
            "automatic_paper_demo_eligibility": False,
        },
        {
            "future_outcome": "validation_data_or_methodology_blocked",
            "decision_timing": "when_valid_evaluation_cannot_continue",
            "conditions": [
                "unresolved_data_timing_accounting_or_methodology_failure"
            ],
            "validated_claim": "none",
            "automatic_paper_demo_eligibility": False,
        },
    ]


def failure_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "reason_scope": "design_task",
            "failure_reason": reason,
            "future_or_current": "current_design",
            "permitted_outcome": OUTCOME_BLOCKED,
        }
        for reason in DESIGN_FAILURE_REASONS
    ]
    rows.extend(
        {
            "reason_scope": "future_validation",
            "failure_reason": reason,
            "future_or_current": "future_only",
            "permitted_outcome": (
                "validation_data_or_methodology_blocked"
                if reason in {"data_or_comparability_failure", "methodology_failure"}
                else "validation_failed"
            ),
        }
        for reason in FUTURE_FAILURE_REASONS
    )
    return rows


def readiness_rows() -> list[dict[str, Any]]:
    checks = [
        ("all_symbols_available", "all_seven_symbols_available_prospectively"),
        ("duplicate_normalization", "duplicate_retrievals_normalize_identically"),
        ("immutable_initialization", "four_month_initialization_captured_immutably"),
        (
            "identical_observations",
            "candidate_and_comparators_initialize_from_identical_observations",
        ),
        ("pre_execution_signal", "monthly_signals_captured_before_execution"),
        ("append_only_valuation", "daily_valuation_stored_without_overwrite"),
        ("initialization_separation", "initialization_separate_from_performance"),
        ("strictly_prospective_start", "first_performance_session_strictly_prospective"),
        ("brokerless_operation", "no_broker_or_order_system_required"),
        ("cache_immutability", "no_historical_canonical_cache_mutation_required"),
    ]
    return [
        {
            "check_order": index,
            "check_id": check_id,
            "activation_requirement": requirement,
            "status_in_design_task": "specified_not_executed",
            "bounded_readiness_attempts_allowed": 1,
            "failure_action": (
                "remain_unactivated_while_strategy_discovery_continues_independently"
            ),
            "activation_authorized_in_this_task": False,
        }
        for index, (check_id, requirement) in enumerate(checks, start=1)
    ]


def vix_rows(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    row = reconciliation["vix_outcome"]
    return [
        {
            "strategy_id": VIX_STRATEGY_ID,
            "stage": "robustness",
            "outcome": row["outcome"],
            "failure_reason": row["failure_reason"],
            "interpretation": row["interpretation"],
            "prospective_validation_design_created": False,
            "future_trial_created": False,
            "variant_created": False,
            "followup_authorized": False,
            "carried_forward_unchanged": True,
            "reconciliation_pass": reconciliation["vix_deferred_pass"],
        }
    ]


def design_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
    reconciliation: dict[str, Any],
) -> str:
    bootstrap = {
        row["comparison_id"]: row for row in reconciliation["bootstrap_rows"]
    }
    return f"""# FAA Prospective Validation Design V1

## Outcome

* Design outcome: `{outcome}`
* Failure reason: `{failure_reason}`
* Exact next action: `{next_action}`
* Future trial: `{FUTURE_TRIAL_ID}`
* Status: `frozen_not_activated`

## Frozen Claim

This design tests whether the full FAA score's volatility and correlation
components improve prospective risk-adjusted and downside behavior beyond
return-only momentum, return-plus-volatility without correlation, and the
archived static average asset exposure.

The claim does not assert higher CAGR than return-only momentum. Historical
evidence showed higher return-only CAGR while full FAA showed higher Sharpe
and a shallower drawdown. The historical evidence and its paired bootstrap
diagnostics are viewed development evidence, not independent validation.

## Lineage

The future validation specification is a child of
`{PARENT_TRIAL_ID}` and changes only the prospective evaluation boundary.
The strategy remains `{STRATEGY_ID}` on the standalone-only route. The failed
diversifier route remains closed. No new strategy configuration or executed
trial is created by this design task.

The historical paired-bootstrap probability that FAA had higher Sharpe was
`{bootstrap['faa_4m_return_only_top3_control']['probability_candidate_higher_sharpe']}`
versus return-only and
`{bootstrap['faa_4m_return_volatility_top3_no_correlation_control']['probability_candidate_higher_sharpe']}`
versus the no-correlation control. These values constrain interpretation and
do not count as prospective evidence.

## Prospective Boundary

Activation must first store immutable initialization snapshots. The first
performance session must be a valid U.S. regular trading session strictly
after activation. Initialization history is labeled
`initialization_state_input_not_validation_performance`; it may form current
targets but may not create validation returns, formations, NAV, or gap
backfill.

Original daily and monthly snapshots are append-only. Later revisions create
alerts without mutating the original decision ledger.

## Decision Boundary

A decision is forbidden before all of these are satisfied:

* 24 completed calendar months;
* 24 completed prospective monthly holding intervals;
* six differentiation months versus return-only;
* six differentiation months versus no-correlation.

The hard maximum is 36 completed calendar months. Insufficient component
differentiation at that point produces
`validation_inconclusive_insufficient_component_differentiation`.

## Controls And Costs

The decisive controls are return-only, return-plus-volatility without
correlation, and the exact archived static weights. The static weights are
never recalculated. Primary one-way cost is 5 bps, with immutable 0 and
10 bps diagnostic ledgers.

## Scope Limits

This task ran no historical performance calculation, provider acquisition,
prospective activation, lifecycle update, paper/demo action, broker action,
order, or real-money action. VIX Fix remains deferred as
`robustness_mixed` with `period_instability`.
"""


def validate_schemas(
    future_spec: dict[str, Any],
    lineage: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    daily: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    controls: list[dict[str, Any]],
    static: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    minimums: list[dict[str, Any]],
    differentiations: list[dict[str, Any]],
    checkpoints: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    readiness: list[dict[str, Any]],
    vix: list[dict[str, Any]],
) -> dict[str, bool]:
    daily_fields = {row["field_name"] for row in daily}
    monthly_fields = {row["field_name"] for row in monthly}
    checkpoint_fields = {row["field_name"] for row in checkpoints}
    return {
        "future_trial_identity": (
            future_spec["trial_id"] == FUTURE_TRIAL_ID
            and future_spec["parent_trial_id"] == PARENT_TRIAL_ID
            and future_spec["record_status"] == "frozen_not_activated"
            and future_spec["route"] == "standalone_only"
        ),
        "lineage_complete": len(lineage) == 4,
        "parameters_frozen": len(parameters) >= 20
        and all(not row["prospective_change_permitted"] for row in parameters),
        "symbols_exact": tuple(row["symbol"] for row in symbols) == UNIVERSE,
        "daily_snapshot_complete": {
            "symbol",
            "market_date",
            "retrieval_timestamp_utc",
            "retrieval_timestamp_us_eastern",
            "provider",
            "raw_source_identifier",
            "raw_hash",
            "normalized_hash",
            "adjusted_close",
            "data_version_identifier",
            "revision_status",
        }
        <= daily_fields,
        "monthly_snapshot_complete": {
            "formation_id",
            "four_month_return_by_asset",
            "volatility_by_asset",
            "pairwise_correlations",
            "average_correlation_by_asset",
            "return_ranks",
            "volatility_ranks",
            "correlation_ranks",
            "combined_scores",
            "selected_slots",
            "SHY_replacements",
            "candidate_target_vector",
            "comparator_target_vectors",
            "intended_execution_session",
            "execution_status",
            "monthly_rebalance_turnover",
            "transaction_cost_by_ledger",
            "cost_adjusted_NAV",
        }
        <= monthly_fields,
        "all_snapshots_immutable": all(
            row["immutable_after_capture"] and not row["original_rows_overwritable"]
            for row in daily + monthly
        ),
        "seven_comparators": tuple(
            row["portfolio_or_control_id"] for row in controls
        )
        == COMPARATORS,
        "three_critical_controls": {
            row["portfolio_or_control_id"]
            for row in controls
            if row["critical_control"]
        }
        == set(CRITICAL_CONTROLS),
        "static_weights_exact": len(static) == 7
        and all(row["reconciliation_pass"] for row in static)
        and math.isclose(
            sum(float(row["frozen_design_weight"]) for row in static),
            1.0,
            abs_tol=1e-12,
        ),
        "boundary_rules_frozen": len(boundaries) == 11
        and all(not row["exception_permitted"] for row in boundaries),
        "minimum_boundary_complete": len(minimums) == 5,
        "differentiation_controls_exact": {
            row["comparison_id"] for row in differentiations
        }
        == set(CRITICAL_CONTROLS[:2]),
        "checkpoint_complete": {
            "elapsed_calendar_months",
            "completed_monthly_intervals",
            "differentiation_months_vs_return_only",
            "differentiation_months_vs_no_correlation",
            "candidate_NAV_by_cost",
            "comparator_NAVs_by_cost",
            "revision_alerts",
            "invariant_results",
        }
        <= checkpoint_fields,
        "future_outcomes_exact": tuple(
            row["future_outcome"] for row in gates
        )
        == FUTURE_OUTCOMES,
        "future_failures_exact": {
            row["failure_reason"]
            for row in failures
            if row["reason_scope"] == "future_validation"
        }
        == set(FUTURE_FAILURE_REASONS),
        "readiness_complete": len(readiness) == 10
        and all(
            row["status_in_design_task"] == "specified_not_executed"
            for row in readiness
        ),
        "vix_remains_deferred": len(vix) == 1
        and vix[0]["reconciliation_pass"]
        and not vix[0]["future_trial_created"],
    }


def run() -> dict[str, Any]:
    protected_before = snapshot_hashes()
    source_before = file_hash(SOURCE_PACKET)
    reconciliation = reconcile_authoritative_evidence()
    outcome, failure_reason, next_action = classify_design(reconciliation)
    reset_output()

    future_spec = future_trial_specification()
    lineage = lineage_rows(reconciliation)
    parameters = parameter_rows()
    symbols = symbol_rows()
    daily = daily_snapshot_rows()
    monthly = monthly_formation_rows()
    controls = control_rows()
    static = static_weight_rows(reconciliation)
    boundaries = boundary_rows()
    minimums = minimum_rows()
    differentiations = differentiation_rows()
    checkpoints = checkpoint_rows()
    gates = outcome_gate_rows()
    failures = failure_rows()
    readiness = readiness_rows()
    vix = vix_rows(reconciliation)
    schema_checks = validate_schemas(
        future_spec,
        lineage,
        parameters,
        symbols,
        daily,
        monthly,
        controls,
        static,
        boundaries,
        minimums,
        differentiations,
        checkpoints,
        gates,
        failures,
        readiness,
        vix,
    )

    design_rows = [
        {
            "design_id": DESIGN_ID,
            "entity_type": "experiment_design",
            "stage": STAGE,
            "mode": MODE,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "route": "standalone_only",
            "future_trial_id": FUTURE_TRIAL_ID,
            "future_parent_trial_id": PARENT_TRIAL_ID,
            "future_trial_status": "frozen_not_activated",
            "future_trial_executed": False,
            "validation_observation_count": 0,
            "paper_demo_observation_count": 0,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "next_action_executed": False,
        }
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "historical_backtests_executed": 0,
            "robustness_calculations_executed": 0,
            "future_trials_executed": 0,
            "provider_access": False,
            "activation_performed": False,
            "lifecycle_state_changed": False,
            "paper_demo_action": False,
            "broker_or_order_action": False,
            "counted_as_strategy": False,
            "counted_as_executed_trial": False,
        }
    ]
    next_action_rows = [
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
            "outcome": "frozen_not_activated",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
    ]
    bootstrap_caveats = {
        row["comparison_id"]: {
            "probability_candidate_higher_cagr": float(
                row["probability_candidate_higher_cagr"]
            ),
            "probability_candidate_higher_sharpe": float(
                row["probability_candidate_higher_sharpe"]
            ),
            "probability_candidate_less_severe_maximum_drawdown": float(
                row["probability_candidate_less_severe_maximum_drawdown"]
            ),
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": float(
                row[
                    "probability_candidate_higher_sharpe_or_less_severe_drawdown"
                ]
            ),
            "historical_only": True,
            "independent_validation": False,
        }
        for row in reconciliation["bootstrap_rows"]
    }
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "design_id": DESIGN_ID,
        "strategy_id": STRATEGY_ID,
        "future_trial_id": FUTURE_TRIAL_ID,
        "future_parent_trial_id": PARENT_TRIAL_ID,
        "future_trial_status": "frozen_not_activated",
        "route": "standalone_only",
        "source_authority": str(SOURCE_PACKET),
        "source_authority_hash": source_before,
        "design_timestamp": DESIGN_TIMESTAMP,
        "historical_evidence_role": (
            "viewed_development_and_robustness_not_independent_validation"
        ),
        "historical_bootstrap_caveats": bootstrap_caveats,
        "new_strategy_configurations": 0,
        "experiment_trials_executed": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "experiment_design_records": 1,
        "future_trial_specifications": 1,
        "benchmark_specifications": 7,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "historical_performance_recalculated": False,
        "provider_access_performed": False,
        "prospective_activation_performed": False,
        "lifecycle_state_changed": False,
        "paper_demo_action_performed": False,
        "broker_or_real_money_action_performed": False,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml("design_manifest.yaml", manifest)
    write_csv("experiment_design_record.csv", design_rows, ["design_id"])
    write_yaml("future_trial_specification.yaml", future_spec)
    write_csv(
        "strategy_and_lineage_reconciliation.csv",
        lineage,
        ["sequence", "record_id"],
    )
    write_csv(
        "frozen_parameter_specification.csv",
        parameters,
        ["parameter_name"],
    )
    write_csv("required_symbol_scope.csv", symbols, ["symbol"])
    write_csv(
        "prospective_daily_snapshot_schema.csv",
        daily,
        ["field_order", "field_name"],
    )
    write_csv(
        "prospective_monthly_formation_schema.csv",
        monthly,
        ["field_order", "field_name"],
    )
    write_csv(
        "portfolio_and_control_definitions.csv",
        controls,
        ["comparison_order", "portfolio_or_control_id"],
    )
    write_csv(
        "archived_static_weight_reconciliation.csv",
        static,
        ["control_id", "symbol"],
    )
    write_csv(
        "activation_boundary_rules.csv",
        boundaries,
        ["rule_order", "rule_id"],
    )
    write_csv(
        "minimum_observation_requirements.csv",
        minimums,
        ["requirement_id"],
    )
    write_csv(
        "component_differentiation_definition.csv",
        differentiations,
        ["comparison_id"],
    )
    write_csv(
        "monthly_checkpoint_schema.csv",
        checkpoints,
        ["field_order", "field_name"],
    )
    write_csv(
        "future_validation_outcome_gates.csv",
        gates,
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
        ["check_order", "check_id"],
    )
    write_csv(
        "vix_fix_deferred_state_reconciliation.csv",
        vix,
        ["strategy_id"],
    )
    write_csv("process_task_log.csv", process_rows, ["task_id"])
    write_csv("next_actions.csv", next_action_rows, ["scope", "design_id"])
    write_text(
        "prospective_validation_design.md",
        design_report(outcome, failure_reason, next_action, reconciliation),
    )

    outputs_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    protected_after = snapshot_hashes()
    source_after = file_hash(SOURCE_PACKET)
    consistency = {
        "task_id": TASK_ID,
        "design_id": DESIGN_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            outcome == OUTCOME_COMPLETED
            and all(schema_checks.values())
            and outputs_before_consistency == expected_before_consistency
            and protected_before == protected_after
            and source_before == source_after
        ),
        "schema_validation_pass": all(schema_checks.values()),
        "schema_checks": schema_checks,
        "required_outputs_exact_before_consistency_write": (
            outputs_before_consistency == expected_before_consistency
        ),
        "identity_reconciliation_pass": reconciliation["identity_pass"],
        "lineage_reconciliation_pass": reconciliation["lineage_pass"],
        "parameter_reconciliation_pass": reconciliation["parameter_pass"],
        "control_reconciliation_pass": reconciliation["control_pass"],
        "bootstrap_caveat_reconciliation_pass": reconciliation["bootstrap_pass"],
        "vix_fix_deferred_reconciliation_pass": reconciliation["vix_deferred_pass"],
        "prior_evidence_consistency_pass": reconciliation[
            "prior_consistency_pass"
        ],
        "new_strategy_configurations": 0,
        "experiment_trials_executed": 0,
        "future_trial_specifications_created": 1,
        "validation_observations_created": 0,
        "paper_demo_observations_created": 0,
        "experiment_design_records_created": 1,
        "benchmark_specifications_created": 7,
        "process_tasks_created": 1,
        "data_capability_tasks_created": 0,
        "historical_backtests_executed": 0,
        "robustness_calculations_executed": 0,
        "historical_performance_recalculated": False,
        "future_trial_activated": False,
        "historical_backfill_performed": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "protected_state_and_prior_evidence_unchanged": (
            protected_before == protected_after
        ),
        "source_packet_unchanged": source_before == source_after,
        "network_access": False,
        "provider_access": False,
        "lifecycle_state_changed": False,
        "paper_demo_action": False,
        "broker_or_order_action": False,
        "real_money_action": False,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    if {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    } != REQUIRED_OUTPUTS:
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
        "future_trial_activated": False,
        "evidence_path": relative(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
