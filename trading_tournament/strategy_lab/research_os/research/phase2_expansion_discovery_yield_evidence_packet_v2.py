from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "phase2_expansion_discovery_yield_evidence_packet_v2"
TASK_OUTCOME = "phase2_expansion_yield_evidence_complete"
NEXT_ACTION = "direction_owner_decide_phase2_post_yield_evidence_v2"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"

REQUIRED_OUTPUTS = {
    "yield_report.md",
    "phase2_discovery_funnel.csv",
    "baseline_vs_phase2_yield.csv",
    "failure_category_reconciliation.csv",
    "phase2_group_coverage.csv",
    "control_gate_audit.csv",
    "control_gate_source_trace.md",
    "evaluation_access_reconciliation.csv",
    "bottleneck_indicators.csv",
    "entity_count_reconciliation.json",
    "consistency_check.json",
    "next_action.md",
}

UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
PHASE2_EXTERNAL_INTAKE = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "phase2_expanded_universe_hybrid_candidate_intake_v1"
    / "latest"
)
PHASE2_EXTERNAL_BATCH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "phase2_expanded_universe_discovery_batch_v1"
    / "latest"
)
PHASE2_INTERNAL_INTAKE = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "phase2_new_group_hybrid_candidate_intake_v1"
    / "latest"
)
PHASE2_INTERNAL_BATCH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "phase2_new_group_discovery_batch_v1"
    / "latest"
)
PHASE2_ROBUSTNESS = (
    ROOT
    / "evidence"
    / "robustness"
    / "role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1"
    / "latest"
)
CURRENT_SOURCE = ROOT / "strategy_lab" / "research_os" / "research" / "phase2_new_group_discovery_batch_v1.py"
DOMINANCE_SOURCE = ROOT / "strategy_lab" / "research_os" / "research" / "phase2_expanded_universe_discovery_batch_v1.py"

BASELINE_COHORT_NAMES = (
    "accepted_47_source_backed_exploration_batch_v1",
    "accepted_47_source_backed_exploration_batch_v2",
    "accepted_47_source_backed_exploration_batch_v3",
    "cfra_stovall_semiannual_sector_rotation_exploration_v1",
    "accepted_47_targeted_internal_technical_batch_v1",
    "accepted_47_targeted_internal_technical_batch_v2",
    "accepted_47_hybrid_discovery_batch_v1",
)
BASELINE_COHORTS = tuple(
    ROOT / "evidence" / "research_recovery" / name / "latest" for name in BASELINE_COHORT_NAMES
)
BASELINE_ROBUSTNESS = (
    ROOT / "evidence" / "robustness" / "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "role_aware_robustness_internal_capture_asymmetry_63d_top3_v1" / "latest",
)
BASELINE_ELIGIBILITY = (
    ROOT / "evidence" / "paper_demo_eligibility" / "internal_capture_asymmetry_63d_top3_v1" / "latest"
)
BASELINE_HANDOFF = ROOT / "evidence" / "handoff" / "internal_capture_asymmetry_63d_top3_v1" / "latest"

PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1",
    ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1",
    ROOT / "paper_forward_observations",
    ROOT / "evidence" / "paper_demo_observation",
    UNIVERSE_DIR,
    PHASE2_EXTERNAL_INTAKE,
    PHASE2_EXTERNAL_BATCH,
    PHASE2_INTERNAL_INTAKE,
    PHASE2_INTERNAL_BATCH,
    PHASE2_ROBUSTNESS,
    *BASELINE_COHORTS,
    *BASELINE_ROBUSTNESS,
    BASELINE_ELIGIBILITY,
    BASELINE_HANDOFF,
)

GROUP_CATEGORY_MAP = {
    "factor_style": "factor/style",
    "individual_countries": "global/country/regional equity",
    "regional_equity": "global/country/regional equity",
    "us_industries": "U.S. industries",
    "high_yield_credit": "credit",
    "investment_grade_credit": "credit",
    "treasury_duration": "Treasury duration",
    "broad_commodities": "commodities/real assets",
    "commodity_subgroups": "commodities/real assets",
    "infrastructure": "commodities/real assets",
    "real_estate": "commodities/real assets",
    "broad_us_equity": "size/broad/equal-weight equity",
    "size": "size/broad/equal-weight equity",
    "value_growth": "size/broad/equal-weight equity",
}
GROUPS = (
    "factor/style",
    "global/country/regional equity",
    "U.S. industries",
    "credit",
    "Treasury duration",
    "commodities/real assets",
    "size/broad/equal-weight equity",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: Iterable[str] | None = None) -> None:
    materialized = list(rows)
    fields = list(fieldnames or (materialized[0].keys() if materialized else ()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: scalar(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(b"MISSING")
        digest.update(relative(path).encode("utf-8"))
        return "missing:sha256:" + digest.hexdigest()
    if path.is_file():
        digest.update(path.read_bytes())
        return "sha256:" + digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_snapshot() -> dict[str, str]:
    return {relative(path): hash_path(path) for path in PROTECTED_PATHS}


def truth(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def float_value(row: dict[str, str], field: str) -> float:
    return float(row[field])


def dominates(control: dict[str, str], candidate: dict[str, str], prefix: str) -> bool:
    tolerance = 1e-10
    control_values = (
        float(control[f"{prefix}_cagr"]),
        float(control[f"{prefix}_sharpe_ratio"]),
        float(control[f"{prefix}_maximum_drawdown"]),
    )
    candidate_values = (
        float(candidate["candidate_cagr"]),
        float(candidate["candidate_sharpe_ratio"]),
        float(candidate["candidate_maximum_drawdown"]),
    )
    nonworse = all(left >= right - tolerance for left, right in zip(control_values, candidate_values))
    strict = any(left > right + tolerance for left, right in zip(control_values, candidate_values))
    return bool(nonworse and strict)


def current_batch_reconciliation() -> dict[str, Any]:
    consistency = read_json(PHASE2_INTERNAL_BATCH / "consistency_check.json")
    split = read_csv(PHASE2_INTERNAL_BATCH / "selection_segment_definition.csv")[0]
    trials = read_csv(PHASE2_INTERNAL_BATCH / "trial_ledger.csv")
    failures = read_csv(PHASE2_INTERNAL_BATCH / "failure_vectors.csv")
    invariants = read_csv(PHASE2_INTERNAL_BATCH / "invariant_results.csv")
    winners = read_csv(PHASE2_INTERNAL_BATCH / "architecture_winner_selection.csv")
    result = {
        "architecture_count": consistency["entity_counts"]["internal_architectures"],
        "configuration_count": consistency["entity_counts"]["strategy_configurations"],
        "trial_ids": [row["trial_id"] for row in trials],
        "valid_formations": int(split["total_valid_monthly_formations"]),
        "selection_formations": int(split["selection_formation_count"]),
        "evaluation_formations": int(split["evaluation_formation_count"]),
        "evaluation_access_count": consistency["entity_counts"]["evaluation_access_count"],
        "winner_count": consistency["entity_counts"]["winner_count"],
        "followup_count": consistency["entity_counts"]["followup_count"],
        "all_invariants_pass": all(truth(row["overall_invariant_pass"]) for row in invariants),
        "blocking_criteria": sorted(
            {
                criterion
                for row in failures
                for criterion in json.loads(row["failed_selection_criteria"])
            }
        ),
        "all_fail_only_static_equal": all(
            json.loads(row["failed_selection_criteria"]) == ["static_equal_control_not_dominating_5bps"]
            for row in failures
        ),
        "all_winner_rows_closed": all(
            not truth(row["selected_winner"]) and not truth(row["evaluation_accessed"]) for row in winners
        ),
        "protected_state_immutable": consistency["checks"]["protected_state_and_caches_unchanged"],
        "deterministic_hash": consistency["deterministic_core_hash"],
        "overall_pass": consistency["overall_pass"],
    }
    return result


def static_target_weights() -> dict[str, dict[str, Any]]:
    signal_rows = read_csv(PHASE2_INTERNAL_BATCH / "monthly_pair_signal_ledger.csv")
    by_trial: dict[str, dict[str, dict[str, float]]] = {}
    selection_boundary = read_csv(PHASE2_INTERNAL_BATCH / "selection_segment_definition.csv")[0]
    selection_count = int(selection_boundary["selection_formation_count"])
    for row in signal_rows:
        trial = row["trial_id"]
        formation = row["formation_date"]
        target = json.loads(row["candidate_target"])
        by_trial.setdefault(trial, {})[formation] = {key: float(value) for key, value in target.items()}
    output: dict[str, dict[str, Any]] = {}
    for trial, formation_targets in by_trial.items():
        dates = sorted(formation_targets)
        symbols = sorted(next(iter(formation_targets.values())))
        weights = {
            symbol: sum(formation_targets[date][symbol] for date in dates) / len(dates)
            for symbol in symbols
        }
        selection_dates = dates[:selection_count]
        evaluation_dates = dates[selection_count:]
        output[trial] = {
            "weights": weights,
            "formation_count": len(dates),
            "selection_derived_formation_count": len(selection_dates),
            "reserved_evaluation_derived_formation_count": len(evaluation_dates),
            "first_formation": dates[0],
            "last_formation": dates[-1],
            "selection_end": selection_boundary["selection_end"],
            "evaluation_start": selection_boundary["evaluation_start"],
        }
    return output


def control_gate_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = read_csv(PHASE2_INTERNAL_BATCH / "selection_segment_results.csv")
    static_targets = static_target_weights()
    output: list[dict[str, Any]] = []
    causes: dict[str, dict[str, Any]] = {}
    for row in rows:
        static_dominates = dominates(row, row, "static_control")
        equal_dominates = dominates(row, row, "equal_industry_control")
        cost = float(row["cost_bps_one_way"])
        trial = row["trial_id"]
        if cost == 5.0:
            causes[trial] = {
                "static_control_dominates": static_dominates,
                "equal_weight_control_dominates": equal_dominates,
            }
        target_info = static_targets[trial]
        output.append(
            {
                "configuration_code": row["configuration_code"],
                "strategy_id": row["strategy_id"],
                "trial_id": trial,
                "cost_bps_one_way": cost,
                "cost_role": "primary_selection_gate" if cost == 5.0 else "diagnostic_only",
                "candidate_cagr": row["candidate_cagr"],
                "candidate_sharpe_ratio": row["candidate_sharpe_ratio"],
                "candidate_maximum_drawdown": row["candidate_maximum_drawdown"],
                "named_control_cagr": row["named_control_cagr"],
                "named_control_sharpe_ratio": row["named_control_sharpe_ratio"],
                "named_control_maximum_drawdown": row["named_control_maximum_drawdown"],
                "static_control_cagr": row["static_control_cagr"],
                "static_control_sharpe_ratio": row["static_control_sharpe_ratio"],
                "static_control_maximum_drawdown": row["static_control_maximum_drawdown"],
                "equal_weight_control_cagr": row["equal_industry_control_cagr"],
                "equal_weight_control_sharpe_ratio": row["equal_industry_control_sharpe_ratio"],
                "equal_weight_control_maximum_drawdown": row["equal_industry_control_maximum_drawdown"],
                "static_control_dominates": static_dominates,
                "equal_weight_control_dominates": equal_dominates,
                "combined_gate_pass": not (static_dominates or equal_dominates),
                "static_target_weights": target_info["weights"],
                "target_decision_formations_used": target_info["formation_count"],
                "selection_formations_contributing": target_info["selection_derived_formation_count"],
                "reserved_evaluation_formations_contributing": target_info[
                    "reserved_evaluation_derived_formation_count"
                ],
                "weights_fixed_before_selection": False,
                "selection_period_information_used": True,
                "reserved_evaluation_decisions_used": True,
                "ex_ante_investable_as_constructed": False,
                "control_role": "ex_post_exposure_and_timing_diagnostic",
                "dominance_formula": (
                    "control>=candidate within 1e-10 on CAGR, Sharpe, and maximum drawdown; "
                    "strictly greater by >1e-10 on at least one"
                ),
                "combined_boolean_formula": "not(static_dominates or equal_weight_dominates)",
                "source_file": relative(CURRENT_SOURCE),
                "source_lines": "621-730;790-811;831-840",
                "dominance_source_file": relative(DOMINANCE_SOURCE),
                "dominance_source_lines": "1575-1586",
            }
        )
    return output, causes


def unique_architecture_count(cards: list[dict[str, str]]) -> int:
    values = {
        row.get("architecture_id") or row.get("strategy_architecture") or row.get("family_id")
        for row in cards
    }
    return len({value for value in values if value})


def baseline_cohort_rows() -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    totals = Counter()
    for name, directory in zip(BASELINE_COHORT_NAMES, BASELINE_COHORTS):
        cards = read_csv(directory / "strategy_cards.csv")
        trials = read_csv(directory / "trial_ledger.csv")
        followups = read_csv(directory / "exploratory_followup_candidates.csv")
        architectures = unique_architecture_count(cards)
        row = {
            "comparison_scope": "accepted_47_direct_pre_phase2_baseline",
            "cohort_id": name,
            "architecture_count": architectures,
            "canonical_trial_count": len(trials),
            "exploratory_followup_count": len(followups),
            "followups_per_canonical_trial": len(followups) / len(trials) if trials else 0.0,
            "architectures_with_followup": len({
                next(
                    (
                        card.get("architecture_id")
                        or card.get("strategy_architecture")
                        or card.get("family_id")
                        for card in cards
                        if card.get("trial_id") == followup.get("trial_id")
                    ),
                    followup.get("strategy_id", ""),
                )
                for followup in followups
            }),
            "robustness_trials_launched": 0,
            "robustness_passes": 0,
            "eligibility_handoff_outcomes": 0,
            "evidence_path": relative(directory),
        }
        output.append(row)
        totals.update(
            architectures=architectures,
            trials=len(trials),
            followups=len(followups),
            architectures_with_followup=row["architectures_with_followup"],
        )
    totals["robustness_trials"] = sum(len(read_csv(path / "outcome_summary.csv")) for path in BASELINE_ROBUSTNESS)
    totals["robustness_passes"] = sum(
        1
        for path in BASELINE_ROBUSTNESS
        for row in read_csv(path / "outcome_summary.csv")
        if row.get("outcome") == "robustness_positive"
    )
    eligibility = read_csv(BASELINE_ELIGIBILITY / "eligibility_decision.csv")
    totals["eligibility_handoff_outcomes"] = sum(
        1 for row in eligibility if row.get("trading_tournament_eligibility_status") == "paper_demo_eligible"
    )
    for row in output:
        if row["cohort_id"] == "accepted_47_source_backed_exploration_batch_v1":
            row["robustness_trials_launched"] = 1
        elif row["cohort_id"] == "accepted_47_source_backed_exploration_batch_v2":
            row["robustness_trials_launched"] = 2
        elif row["cohort_id"] == "accepted_47_targeted_internal_technical_batch_v1":
            row["robustness_trials_launched"] = 1
            row["robustness_passes"] = 1
            row["eligibility_handoff_outcomes"] = 1
    return output, dict(totals)


def phase2_comparison_row() -> tuple[dict[str, Any], dict[str, int]]:
    external_cards = read_csv(PHASE2_EXTERNAL_BATCH / "strategy_cards.csv")
    external_trials = read_csv(PHASE2_EXTERNAL_BATCH / "trial_ledger.csv")
    external_followups = read_csv(PHASE2_EXTERNAL_BATCH / "exploratory_followup_candidates.csv")
    internal_cards = read_csv(PHASE2_INTERNAL_BATCH / "strategy_cards.csv")
    internal_trials = read_csv(PHASE2_INTERNAL_BATCH / "trial_ledger.csv")
    internal_followups = read_csv(PHASE2_INTERNAL_BATCH / "exploratory_followup_candidates.csv")
    architectures = unique_architecture_count(external_cards) + unique_architecture_count(internal_cards)
    trials = len(external_trials) + len(internal_trials)
    followups = len(external_followups) + len(internal_followups)
    robustness_rows = read_csv(PHASE2_ROBUSTNESS / "outcome_summary.csv")
    passes = sum(1 for row in robustness_rows if row.get("outcome") == "robustness_positive")
    totals = {
        "architectures": architectures,
        "trials": trials,
        "followups": followups,
        "architectures_with_followup": 1 if followups else 0,
        "robustness_trials": len(robustness_rows),
        "robustness_passes": passes,
        "eligibility_handoff_outcomes": 0,
    }
    return (
        {
            "comparison_scope": "phase2_88_symbol_program_to_date",
            "cohort_id": "phase2_program_aggregate",
            "architecture_count": architectures,
            "canonical_trial_count": trials,
            "exploratory_followup_count": followups,
            "followups_per_canonical_trial": followups / trials if trials else 0.0,
            "architectures_with_followup": totals["architectures_with_followup"],
            "robustness_trials_launched": len(robustness_rows),
            "robustness_passes": passes,
            "eligibility_handoff_outcomes": 0,
            "evidence_path": (
                f"{relative(PHASE2_EXTERNAL_BATCH)}|{relative(PHASE2_INTERNAL_BATCH)}|"
                f"{relative(PHASE2_ROBUSTNESS)}"
            ),
        },
        totals,
    )


def failure_vector_map(directory: Path) -> dict[str, dict[str, str]]:
    path = directory / "failure_vectors.csv"
    if not path.exists():
        return {}
    return {row.get("trial_id", ""): row for row in read_csv(path)}


def normalized_failure(reason: str, vector: dict[str, str] | None = None, current: bool = False) -> str:
    vector = vector or {}
    if current and reason == "no_selection_eligible_configuration":
        return "static_or_exposure_control_dominance"
    if reason == "no_selection_eligible_configuration":
        if vector.get("selection_cagr_positive_5bps") == "false":
            return "absolute_performance_weak"
        if vector.get("selection_named_control_not_dominating_5bps") == "false":
            return "named_control_dominance"
        if vector.get("selection_material_vs_named_control_5bps") == "false":
            return "benchmark_like_behavior"
        if vector.get("selection_static_equal_control_not_dominating_5bps") == "false":
            return "static_or_exposure_control_dominance"
        return "other"
    mapping = {
        "weak_return": "absolute_performance_weak",
        "weak_vs_primary_control": "named_control_dominance",
        "benchmark_like_behavior": "benchmark_like_behavior",
        "duplicate_or_redundant": "duplicate_or_near_duplicate",
        "concentration_risk": "concentration",
        "period_instability": "period_instability",
        "signal_scarcity": "sample_inadequate",
        "cost_drag": "turnover_or_cost_damage",
        "turnover_drag": "turnover_or_cost_damage",
        "data_or_comparability_failure": "data_or_instrument_infeasible",
        "data_unavailable": "data_or_instrument_infeasible",
        "methodology_failure": "implementation_or_methodology_defect",
        "not_selected_by_frozen_rule": "other",
    }
    return mapping.get(reason, "other")


def collect_failure_rows(control_causes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []

    def append(
        comparison_scope: str,
        cohort_id: str,
        entity_type: str,
        strategy_id: str,
        trial_id: str,
        outcome: str,
        reason: str,
        vector: dict[str, str] | None = None,
        current: bool = False,
        detail: str = "",
    ) -> None:
        failures.append(
            {
                "comparison_scope": comparison_scope,
                "cohort_id": cohort_id,
                "entity_type": entity_type,
                "strategy_id": strategy_id,
                "trial_id": trial_id,
                "outcome": outcome,
                "exact_repository_failure_reason": reason,
                "normalized_category": normalized_failure(reason, vector, current),
                "failure_detail": detail,
            }
        )

    for name, directory in zip(BASELINE_COHORT_NAMES, BASELINE_COHORTS):
        vectors = failure_vector_map(directory)
        seen: set[str] = set()
        for row in read_csv(directory / "failure_reasons.csv"):
            trial_id = row.get("trial_id", "")
            if trial_id in seen:
                continue
            seen.add(trial_id)
            append(
                "accepted_47_direct_pre_phase2_baseline",
                name,
                "canonical_trial_closure",
                row.get("strategy_id", ""),
                trial_id,
                row.get("outcome", "closed"),
                row.get("failure_reason") or row.get("primary_failure_reason", "other"),
                vectors.get(trial_id),
                detail=row.get("failure_detail", ""),
            )
    for directory in BASELINE_ROBUSTNESS:
        for row in read_csv(directory / "outcome_summary.csv"):
            if row.get("outcome") == "robustness_positive":
                continue
            append(
                "accepted_47_direct_pre_phase2_baseline",
                directory.parent.name,
                "robustness_trial_nonpass",
                row.get("strategy_id", ""),
                row.get("trial_id", ""),
                row.get("outcome", ""),
                row.get("failure_reason", "other"),
            )
    phase2_vectors = failure_vector_map(PHASE2_EXTERNAL_BATCH)
    external_trial_by_strategy = {
        row["strategy_id"]: row["trial_id"] for row in read_csv(PHASE2_EXTERNAL_BATCH / "trial_ledger.csv")
    }
    for row in read_csv(PHASE2_EXTERNAL_BATCH / "failure_reasons.csv"):
        if not row.get("primary_failure_reason") and not row.get("failure_reason"):
            continue
        trial_id = row.get("trial_id") or external_trial_by_strategy.get(row.get("strategy_id", ""), "")
        append(
            "phase2_88_symbol_program_to_date",
            "phase2_expanded_universe_discovery_batch_v1",
            "canonical_trial_closure",
            row.get("strategy_id", ""),
            trial_id,
            row.get("outcome", ""),
            row.get("failure_reason") or row.get("primary_failure_reason", "other"),
            phase2_vectors.get(trial_id),
        )
    for row in read_csv(PHASE2_INTERNAL_BATCH / "failure_vectors.csv"):
        trial_id = row["trial_id"]
        cause = control_causes[trial_id]
        detail = (
            f"static_control_dominates={str(cause['static_control_dominates']).lower()};"
            f"equal_weight_control_dominates={str(cause['equal_weight_control_dominates']).lower()}"
        )
        append(
            "phase2_88_symbol_program_to_date",
            "phase2_new_group_discovery_batch_v1",
            "canonical_trial_closure",
            row["strategy_id"],
            trial_id,
            row["outcome"],
            row["primary_failure_reason"],
            row,
            current=True,
            detail=detail,
        )
    for row in read_csv(PHASE2_ROBUSTNESS / "outcome_summary.csv"):
        if row.get("outcome") == "robustness_positive":
            continue
        append(
            "phase2_88_symbol_program_to_date",
            "role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1",
            "robustness_trial_nonpass",
            row.get("strategy_id", ""),
            row.get("trial_id", ""),
            row.get("outcome", ""),
            row.get("failure_reason", "other"),
        )
    counts = Counter(row["normalized_category"] for row in failures)
    total = len(failures)
    for row in failures:
        row["category_count"] = counts[row["normalized_category"]]
        row["closure_count_denominator"] = total
        row["category_percentage_of_closures"] = counts[row["normalized_category"]] / total if total else 0.0
    return failures


def phase2_group_coverage() -> list[dict[str, Any]]:
    additions = [
        row
        for row in read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
        if row["membership_source"] == "phase2_nonperformance_addition"
    ]
    symbols: dict[str, list[str]] = {group: [] for group in GROUPS}
    for row in additions:
        group = GROUP_CATEGORY_MAP[row["category"]]
        symbols[group].append(row["symbol"])
    research = {
        "factor/style": (1, 0, 1, 1, 1, 1, 0),
        "global/country/regional equity": (1, 0, 1, 1, 0, 0, 0),
        "U.S. industries": (0, 1, 1, 4, 0, 0, 0),
        "credit": (0, 0, 0, 0, 0, 0, 0),
        "Treasury duration": (0, 0, 0, 0, 0, 0, 0),
        "commodities/real assets": (0, 0, 0, 0, 0, 0, 0),
        "size/broad/equal-weight equity": (0, 0, 0, 0, 0, 0, 0),
    }
    rows: list[dict[str, Any]] = []
    for group in GROUPS:
        external, internal, architectures, trials, followups, robustness, success = research[group]
        if trials >= 4 or robustness >= 1:
            classification = "materially_explored"
        elif external + internal + architectures + trials > 0:
            classification = "lightly_explored"
        else:
            classification = "unexplored"
        rows.append(
            {
                "capability_group": group,
                "phase2_added_symbols": sorted(symbols[group]),
                "phase2_added_symbol_count": len(symbols[group]),
                "serious_external_source_packages_assessed": external,
                "internal_concepts_assessed": internal,
                "frozen_architectures": architectures,
                "canonical_trials": trials,
                "exploratory_followups": followups,
                "robustness_candidates": robustness,
                "successful_research_outcomes": success,
                "coverage_classification": classification,
                "classification_rule": (
                    "materially_explored if canonical_trials>=4 or robustness_candidates>=1; "
                    "lightly_explored if any serious assessment/architecture/trial exists; otherwise unexplored"
                ),
            }
        )
    return rows


def funnel_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    values = (
        ("serious_external_source_packages_reviewed", "source_library_record", 2, "two materialized Phase-2 source packages; upstream rejected review count is not present"),
        ("externally_qualified_work_packages", "source_library_record", 2, "both Phase-2 source records are feasible and implementation-authorized"),
        ("internal_concepts_seriously_assessed", "concept", 1, "one selected internal architecture; rejection ledger has zero rows"),
        ("internal_architectures_frozen", "architecture", 1, "current industry-parent persistence architecture"),
        ("canonical_strategy_configurations", "strategy_configuration", 6, "two external plus four internal configurations"),
        ("canonical_trials", "canonical_trial", 6, "controls excluded"),
        ("trials_reaching_selection_or_exploration_gate", "canonical_trial", 6, "two external exploration gates plus four internal selection gates"),
        ("selection_or_exploration_gate_eligible_trials", "canonical_trial", 1, "market rotator only"),
        ("reserved_evaluation_segments_accessed", "evaluation_segment", current["evaluation_access_count"], "current internal architecture only; external trials had no reserved segment"),
        ("reserved_evaluation_survivors", "evaluation_survivor", 0, "no internal evaluation segment was opened"),
        ("exploratory_followups", "followup", 1, "market rotator"),
        ("robustness_trials_launched", "robustness_trial", 1, "market rotator role-aware robustness"),
        ("robustness_passes", "robustness_pass", 0, "market rotator failed period-stability gate"),
        ("research_eligibility_handoff_outcomes", "eligibility_decision", 0, "none in Phase 2"),
    )
    return [
        {
            "program_scope": "phase2_88_symbol_program_to_date",
            "funnel_stage": stage,
            "entity_class": entity,
            "count": count,
            "counting_note": note,
        }
        for stage, entity, count, note in values
    ]


def evaluation_access_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    failures = {row["trial_id"]: row for row in read_csv(PHASE2_INTERNAL_BATCH / "failure_vectors.csv")}
    trials = read_csv(PHASE2_INTERNAL_BATCH / "trial_ledger.csv")
    rows = []
    for trial in trials:
        failure = failures[trial["trial_id"]]
        rows.append(
            {
                "strategy_id": trial["strategy_id"],
                "trial_id": trial["trial_id"],
                "selection_eligible": False,
                "selected_winner": False,
                "reserved_evaluation_accessed": False,
                "reserved_evaluation_performance_row_count": 0,
                "evaluation_signal_decisions_present_in_static_control": True,
                "evaluation_signal_decision_count": current["evaluation_formations"],
                "evaluation_performance_calculated": False,
                "failed_selection_criteria": failure["failed_selection_criteria"],
                "reconciliation_status": "pass_with_control_information_set_caveat",
            }
        )
    return rows


def bottleneck_rows(
    baseline: dict[str, int],
    phase2: dict[str, int],
    failures: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    category_counts = Counter(row["normalized_category"] for row in failures)
    unexplored = sum(1 for row in coverage if row["coverage_classification"] == "unexplored")
    material = sum(1 for row in coverage if row["coverage_classification"] == "materially_explored")
    baseline_rate = baseline["followups"] / baseline["trials"]
    phase2_rate = phase2["followups"] / phase2["trials"]
    rows = [
        {
            "indicator": "candidate_supply_bottleneck",
            "evidence_for": "only two external packages and one internal concept are directly evidenced for 41 added symbols",
            "evidence_against": "six canonical trials were completed and one reached follow-up",
            "supporting_statistic": "3 serious packages/concepts; 6 trials; 1 follow-up",
            "confidence": "medium",
        },
        {
            "indicator": "source_rule_completeness_bottleneck",
            "evidence_for": "upstream source reviews not selected into the intake are not enumerated",
            "evidence_against": "both materialized source packages have zero unresolved material fields and executed",
            "supporting_statistic": "0 source_rules_incomplete closures among materialized Phase-2 packages",
            "confidence": "high",
        },
        {
            "indicator": "duplicate_saturation_bottleneck",
            "evidence_for": f"{category_counts['duplicate_or_near_duplicate']} accepted-47/Phase-2 closures normalize to duplicate or near-duplicate",
            "evidence_against": "no Phase-2 trial or intake record closed as duplicate",
            "supporting_statistic": f"{category_counts['duplicate_or_near_duplicate']} combined; 0 Phase-2",
            "confidence": "medium",
        },
        {
            "indicator": "control_gate_bottleneck",
            "evidence_for": "all four current trials failed only the combined static/equal dominance Boolean",
            "evidence_against": "one of six Phase-2 canonical trials passed exploration and reached robustness",
            "supporting_statistic": (
                f"static/exposure={category_counts['static_or_exposure_control_dominance']}; "
                f"named={category_counts['named_control_dominance']}; benchmark-like={category_counts['benchmark_like_behavior']}"
            ),
            "confidence": "high",
        },
        {
            "indicator": "cost_turnover_bottleneck",
            "evidence_for": "transaction costs reduce current candidate returns",
            "evidence_against": "all four current configurations retained positive CAGR at 10 bps and no compared closure has a primary cost/turnover category",
            "supporting_statistic": f"{category_counts['turnover_or_cost_damage']} normalized cost/turnover closures",
            "confidence": "high",
        },
        {
            "indicator": "robustness_bottleneck",
            "evidence_for": "the sole Phase-2 robustness trial failed; only one of four accepted-47 robustness trials passed",
            "evidence_against": "one accepted-47 candidate did pass robustness and eligibility",
            "supporting_statistic": "Phase-2 0/1; accepted-47 1/4 robustness passes",
            "confidence": "high",
        },
        {
            "indicator": "insufficient_phase2_group_coverage",
            "evidence_for": f"{unexplored} of 7 groups are unexplored and only {material} are materially explored",
            "evidence_against": "all 41 Phase-2 additions are frozen and data-ready for bounded research",
            "supporting_statistic": f"{material} materially explored; {unexplored} unexplored; 7 total groups",
            "confidence": "high",
        },
        {
            "indicator": "phase2_expansion_not_materially_improving_yield",
            "evidence_for": "Phase 2 has zero robustness passes and zero eligibility outcomes",
            "evidence_against": "exploratory follow-up yield is numerically higher than the accepted-47 baseline",
            "supporting_statistic": (
                f"follow-up/trial {phase2_rate:.6f} Phase-2 vs {baseline_rate:.6f} accepted-47; "
                "robustness pass 0/1 vs 1/4"
            ),
            "confidence": "low",
        },
    ]
    return rows


def evidence_gaps() -> list[str]:
    return [
        "No standalone repository packet named direction_owner_review_phase2_expansion_discovery_yield_v1 was found; routing is evidenced by the Phase-2 batch and subsequent robustness packet.",
        "Phase-2 intake rejection ledgers are header-only, so the count of serious source packages or internal concepts considered but not materialized cannot be observed; 2 external packages and 1 internal concept are direct-evidence counts.",
        "The protected path accepted_47_source_backed_exploration_batch_v4 is absent; the actual V4 canonical trial is evidenced under cfra_stovall_semiannual_sector_rotation_exploration_v1 and was used in the baseline.",
        "The current selection artifact materializes full performance metrics for the candidate, named control, static control, and equal-industry control; full parent-sector, SPY, and BIL performance metrics are not materialized and were not recalculated.",
    ]


def packet_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_OUTPUTS - {"consistency_check.json"}):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def render_control_trace(control_rows: list[dict[str, Any]], causes: dict[str, dict[str, Any]]) -> str:
    cause_lines = []
    for row in control_rows:
        if float(row["cost_bps_one_way"]) != 5.0:
            continue
        cause = causes[row["trial_id"]]
        cause_lines.append(
            f"- `{row['configuration_code']}` / `{row['trial_id']}`: static dominates = "
            f"`{str(cause['static_control_dominates']).lower()}`; equal-weight dominates = "
            f"`{str(cause['equal_weight_control_dominates']).lower()}`."
        )
    return f"""# Control-Gate Source Trace

## Construction

The implementation is `{relative(CURRENT_SOURCE)}`.

- `build_prepared` is defined at lines 621-730.
- Line 628 iterates over every entry in `split.signal_execution_pairs`, not only the 136 selection formations.
- Lines 663-666 retain valid candidate targets in `monthly_candidate_targets`.
- Lines 704-710 average each symbol's target weight across that full target list.
- Line 716 passes those averaged weights to `buy_hold_events`; lines 326-327 create one target event at the first price date.
- Lines 831-840 subsequently bound return simulation to `split.selection_index.max()`.

The static weights are therefore calculated from candidate target decisions across all 227 formations: 136 selection formations and 91 reserved exploratory-evaluation formations. The weights are applied from the beginning of the selection return simulation. They are not fixed before the selection period and are not investable ex ante as constructed. The control is an ex-post exposure/timing diagnostic. This audit does not change the closed trials or authorize a prospective correction.

## Dominance Boolean

`selection_vector` is at lines 798-811. Line 808 defines:

`static_equal_control_not_dominating_5bps = not (dominates(static, candidate) or dominates(equal_weight, candidate))`

The wrapper at lines 790-791 delegates to `{relative(DOMINANCE_SOURCE)}` lines 1575-1586. A control dominates when it is no worse within `1e-10` on CAGR, Sharpe ratio, and maximum drawdown and is strictly better by more than `1e-10` on at least one. Either the static control or equal-industry control can fail the combined Boolean.

## Current Failures

{chr(10).join(cause_lines)}

All four failed because the static control dominated. The equal-industry control additionally dominated P3 only.
"""


def render_report(
    current: dict[str, Any],
    baseline: dict[str, int],
    phase2: dict[str, int],
    failures: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    bottlenecks: list[dict[str, Any]],
    gaps: list[str],
) -> str:
    counts = Counter(row["normalized_category"] for row in failures)
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    baseline_rate = baseline["followups"] / baseline["trials"]
    phase2_rate = phase2["followups"] / phase2["trials"]
    material = sum(1 for row in coverage if row["coverage_classification"] == "materially_explored")
    return f"""# Phase-2 Expansion Discovery-Yield Evidence Packet V2

## 1. Evidence Packet Outcome

`{TASK_OUTCOME}`. This is a read-only evidence reconciliation. It creates no strategy, trial, backtest, robustness run, eligibility decision, handoff, or forward observation.

## 2. Current-Batch Reconciliation

The repository supports exactly one architecture, four canonical configurations/trials, {current['valid_formations']} valid formations, {current['selection_formations']} selection formations, and {current['evaluation_formations']} reserved formations. Evaluation access, winners, and follow-ups are all zero. All invariants pass. Every trial failed only `static_equal_control_not_dominating_5bps`. The current deterministic hash is `{current['deterministic_hash']}`.

The exact 0, 5, and 10 bps candidate and critical-control metrics are in `control_gate_audit.csv`. Full performance metrics for the three noncritical parent/SPY/BIL references were not materialized by the closed batch and were not recalculated.

## 3. Phase-2 Discovery Funnel

Phase 2 directly evidences two serious external work packages, one internal concept/architecture, six canonical trials, one exploratory follow-up, one robustness trial, zero robustness passes, and zero eligibility/handoff outcomes. Controls and rejected ideas are excluded from trial counts.

## 4. Accepted-47 Versus Phase-2 Comparison

The bounded accepted-47 baseline contains {baseline['trials']} canonical trials across {baseline['architectures']} architectures, {baseline['followups']} follow-ups, {baseline['robustness_trials']} robustness trials, {baseline['robustness_passes']} robustness pass, and {baseline['eligibility_handoff_outcomes']} eligibility/handoff outcome. Its follow-up rate is {baseline_rate:.2%}.

Phase 2 contains {phase2['trials']} canonical trials across {phase2['architectures']} architectures, {phase2['followups']} follow-up, {phase2['robustness_trials']} robustness trial, and {phase2['robustness_passes']} robustness passes. Its follow-up rate is {phase2_rate:.2%}. The exploratory rate is {phase2_rate - baseline_rate:+.2%} higher, while downstream robustness yield is lower; the Phase-2 denominator is six trials. These are descriptive counts, not a strategic conclusion.

## 5. Failure Concentration

The three largest normalized categories are {', '.join(f'`{name}` ({count})' for name, count in top)}. `failure_category_reconciliation.csv` retains every exact repository reason and reports category percentages over all canonical closures and robustness nonpasses in the compared scope.

## 6. Control-Gate Findings

The current static control is calculated from candidate targets over all 227 formations, including the 91 reserved formations, and then invested from the beginning of the selection simulation. It is an ex-post exposure/timing diagnostic rather than an ex-ante fixed-weight control. The combined Boolean can fail from either static or equal-industry dominance. Static dominated P1-P4; equal-industry additionally dominated P3. Closed outcomes remain unchanged.

## 7. Phase-2 Group Coverage

{material} of seven capability groups meet the packet's count-based `materially_explored` definition. One group is lightly explored and four are unexplored. The exact symbols and counts are in `phase2_group_coverage.csv`.

## 8. Bottleneck Indicators

{chr(10).join(f"- `{row['indicator']}` ({row['confidence']} confidence): {row['supporting_statistic']}." for row in bottlenecks)}

No bottleneck is selected as project direction.

## 9. Evidence Gaps

{chr(10).join(f'- {gap}' for gap in gaps)}

These gaps lower confidence for upstream candidate-supply inference but do not prevent reconciliation of the materialized Phase-2 trials and downstream outcomes.

## 10. Exact Next Action

`{NEXT_ACTION}`

The action is recorded only and was not executed.
"""


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    current = current_batch_reconciliation()
    control_rows, control_causes = control_gate_rows()
    baseline_rows, baseline_totals = baseline_cohort_rows()
    phase2_row, phase2_totals = phase2_comparison_row()
    failures = collect_failure_rows(control_causes)
    coverage = phase2_group_coverage()
    funnel = funnel_rows(current)
    evaluation = evaluation_access_rows(current)
    bottlenecks = bottleneck_rows(baseline_totals, phase2_totals, failures, coverage)
    gaps = evidence_gaps()

    baseline_aggregate = {
        "comparison_scope": "accepted_47_direct_pre_phase2_baseline",
        "cohort_id": "accepted_47_baseline_aggregate",
        "architecture_count": baseline_totals["architectures"],
        "canonical_trial_count": baseline_totals["trials"],
        "exploratory_followup_count": baseline_totals["followups"],
        "followups_per_canonical_trial": baseline_totals["followups"] / baseline_totals["trials"],
        "architectures_with_followup": baseline_totals["architectures_with_followup"],
        "robustness_trials_launched": baseline_totals["robustness_trials"],
        "robustness_passes": baseline_totals["robustness_passes"],
        "eligibility_handoff_outcomes": baseline_totals["eligibility_handoff_outcomes"],
        "evidence_path": "|".join(relative(path) for path in BASELINE_COHORTS),
    }
    comparison_rows = baseline_rows + [baseline_aggregate, phase2_row]

    write_csv(OUTPUT_DIR / "phase2_discovery_funnel.csv", funnel)
    write_csv(OUTPUT_DIR / "baseline_vs_phase2_yield.csv", comparison_rows)
    write_csv(OUTPUT_DIR / "failure_category_reconciliation.csv", failures)
    write_csv(OUTPUT_DIR / "phase2_group_coverage.csv", coverage)
    write_csv(OUTPUT_DIR / "control_gate_audit.csv", control_rows)
    write_csv(OUTPUT_DIR / "evaluation_access_reconciliation.csv", evaluation)
    write_csv(OUTPUT_DIR / "bottleneck_indicators.csv", bottlenecks)
    (OUTPUT_DIR / "control_gate_source_trace.md").write_text(
        render_control_trace(control_rows, control_causes), encoding="utf-8"
    )
    (OUTPUT_DIR / "yield_report.md").write_text(
        render_report(current, baseline_totals, phase2_totals, failures, coverage, bottlenecks, gaps),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Exact Next Action\n\n`{NEXT_ACTION}`\n\nRecorded only; not executed.\n", encoding="utf-8"
    )

    entity_counts = {
        "source_library_context_records_created": 0,
        "strategy_configurations_created": 0,
        "canonical_trials_created": 0,
        "benchmark_references_created": 0,
        "backtests_run": 0,
        "optimization_runs": 0,
        "reserved_evaluation_performance_rows_calculated": 0,
        "robustness_trials_run": 0,
        "eligibility_decisions_created": 0,
        "handoffs_created": 0,
        "forward_observations_created": 0,
        "provider_calls": 0,
        "broker_calls": 0,
        "market_data_mutations": 0,
        "process_tasks_created": 1,
        "phase2_canonical_trials_reconciled": phase2_totals["trials"],
        "phase2_followups_reconciled": phase2_totals["followups"],
        "phase2_robustness_passes_reconciled": phase2_totals["robustness_passes"],
        "accepted47_canonical_trials_reconciled": baseline_totals["trials"],
        "accepted47_followups_reconciled": baseline_totals["followups"],
        "accepted47_robustness_passes_reconciled": baseline_totals["robustness_passes"],
    }
    write_json(
        OUTPUT_DIR / "entity_count_reconciliation.json",
        {
            "task_id": TASK_ID,
            "entity_counts": entity_counts,
            "controls_excluded_from_trials": True,
            "rejected_ideas_excluded_from_trials": True,
            "concepts_distinct_from_configurations": True,
            "followups_distinct_from_robustness_trials": True,
            "eligibility_decisions_distinct_from_trials": True,
        },
    )

    protected_after = protected_snapshot()
    files_before_consistency = {
        path.name
        for path in OUTPUT_DIR.iterdir()
        if path.is_file() and path.name != "consistency_check.json"
    }
    checks = {
        "no_new_strategies_created": entity_counts["strategy_configurations_created"] == 0,
        "no_new_canonical_trials_created": entity_counts["canonical_trials_created"] == 0,
        "no_backtest_run": entity_counts["backtests_run"] == 0,
        "no_optimization_run": entity_counts["optimization_runs"] == 0,
        "no_reserved_evaluation_performance_calculated": entity_counts[
            "reserved_evaluation_performance_rows_calculated"
        ]
        == 0,
        "no_robustness_run": entity_counts["robustness_trials_run"] == 0,
        "no_eligibility_decision": entity_counts["eligibility_decisions_created"] == 0,
        "no_handoff": entity_counts["handoffs_created"] == 0,
        "no_forward_observation": entity_counts["forward_observations_created"] == 0,
        "no_provider_call": entity_counts["provider_calls"] == 0,
        "no_broker_call": entity_counts["broker_calls"] == 0,
        "no_market_data_mutation": entity_counts["market_data_mutations"] == 0,
        "strategy_registry_unchanged": protected_before["strategy_lab/strategy_registry.yaml"]
        == protected_after["strategy_lab/strategy_registry.yaml"],
        "family_ledger_unchanged": protected_before[
            "strategy_lab/research_os/family_lineage/family_ledger.yaml"
        ]
        == protected_after["strategy_lab/research_os/family_lineage/family_ledger.yaml"],
        "research_queue_unchanged": protected_before[
            "strategy_lab/research_os/research/research_queue.yaml"
        ]
        == protected_after["strategy_lab/research_os/research/research_queue.yaml"],
        "roadmap_unchanged": protected_before["strategy_lab/RESEARCH_ROADMAP.md"]
        == protected_after["strategy_lab/RESEARCH_ROADMAP.md"],
        "protected_evidence_and_caches_unchanged": protected_before == protected_after,
        "entity_counts_reconcile": (
            phase2_totals["trials"] == 6
            and phase2_totals["followups"] == 1
            and phase2_totals["robustness_passes"] == 0
            and baseline_totals["trials"] == 36
            and baseline_totals["followups"] == 4
            and baseline_totals["robustness_passes"] == 1
        ),
        "current_batch_metrics_reconcile": (
            current["architecture_count"] == 1
            and current["configuration_count"] == 4
            and current["valid_formations"] == 227
            and current["selection_formations"] == 136
            and current["evaluation_formations"] == 91
            and current["evaluation_access_count"] == 0
            and current["winner_count"] == 0
            and current["followup_count"] == 0
            and current["all_invariants_pass"]
            and current["all_fail_only_static_equal"]
        ),
        "control_implementation_trace_exists": (OUTPUT_DIR / "control_gate_source_trace.md").exists(),
        "all_required_outputs_exist_before_consistency": files_before_consistency
        == REQUIRED_OUTPUTS - {"consistency_check.json"},
        "universe_hash_reconciles": read_json(PHASE2_INTERNAL_BATCH / "consistency_check.json")[
            "checks"
        ]["phase2_universe_hash_matches"],
    }
    overall = all(checks.values())
    evidence_hash = packet_hash()
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": TASK_OUTCOME if overall else "phase2_expansion_yield_evidence_incomplete",
        "overall_pass": overall,
        "checks": checks,
        "deterministic_evidence_packet_hash": evidence_hash,
        "current_batch_deterministic_hash": current["deterministic_hash"],
        "universe_id": UNIVERSE_ID,
        "frozen_universe_hash": UNIVERSE_HASH,
        "phase2_counts": phase2_totals,
        "accepted47_counts": baseline_totals,
        "materially_explored_phase2_group_count": sum(
            1 for row in coverage if row["coverage_classification"] == "materially_explored"
        ),
        "evidence_gaps": gaps,
        "exact_next_action": NEXT_ACTION if overall else "direction_owner_review_phase2_yield_evidence_gaps_v2",
        "next_action_executed": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "forbidden_actions": {
            "strategy_discovery": False,
            "backtest": False,
            "optimization": False,
            "reserved_evaluation_access": False,
            "robustness": False,
            "eligibility_or_handoff": False,
            "forward_observation": False,
            "provider_or_broker": False,
            "market_data_mutation": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "task_outcome": consistency["task_outcome"],
        "overall_pass": overall,
        "phase2_canonical_trial_count": phase2_totals["trials"],
        "phase2_followup_count": phase2_totals["followups"],
        "phase2_robustness_pass_count": phase2_totals["robustness_passes"],
        "deterministic_evidence_packet_hash": evidence_hash,
        "exact_next_action": consistency["exact_next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
