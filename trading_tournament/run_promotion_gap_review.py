from __future__ import annotations

import csv
import json
import math
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent
PROMOTION_LATEST = Path("evidence/promotion_review/latest")
STRATEGY_LAB_LATEST = Path("evidence/strategy_lab/latest")
OUTPUT_ROOT = Path("evidence/promotion_gap")
CORE_INPUT = PROMOTION_LATEST / "promotion_decisions.csv"

REQUIRED_DECISION_COLUMNS = {
    "strategy_id",
    "family",
    "instrument_lane",
    "evidence_tier",
    "current_status",
    "paper_forward_active",
    "real_money_recommendation",
    "candidate_exhaustive_run",
    "promotion_decision",
    "promotion_reason",
    "primary_failure_mode",
    "duplication_risk",
    "risk_budget_status",
    "target_300_evidence",
    "target_400_evidence",
    "drawdown_evidence",
    "stop_hit_evidence",
    "stress_evidence",
    "missing_evidence",
    "evidence_needed",
    "blocked_reason",
    "duplicate_of",
    "recommended_next_action",
    "candidate_exhaustive_allowed",
    "paper_forward_allowed",
    "allowed_next_actions",
    "forbidden_next_actions",
}

INPUT_FILES = [
    PROMOTION_LATEST / "promotion_decisions.csv",
    PROMOTION_LATEST / "promotion_candidates.csv",
    PROMOTION_LATEST / "protected_successful_strategies.csv",
    PROMOTION_LATEST / "historical_success_registry.csv",
    PROMOTION_LATEST / "rejected_or_blocked_rows.csv",
    PROMOTION_LATEST / "duplicate_or_near_duplicate_rows.csv",
    PROMOTION_LATEST / "promotion_review_summary.md",
    PROMOTION_LATEST / "promotion_review_manifest.json",
    PROMOTION_LATEST / "promotion_thresholds_used.yaml",
    PROMOTION_LATEST / "promotion_review_consistency_check.json",
    STRATEGY_LAB_LATEST / "active_observations.csv",
    STRATEGY_LAB_LATEST / "candidate_status_matrix.csv",
    STRATEGY_LAB_LATEST / "historical_leaders.csv",
    STRATEGY_LAB_LATEST / "blocked_and_gated_items.csv",
    STRATEGY_LAB_LATEST / "next_allowed_actions.csv",
    STRATEGY_LAB_LATEST / "research_state_manifest.json",
    STRATEGY_LAB_LATEST / "warnings_and_limitations.md",
    Path("strategy_lab/PROMOTION_POLICY.md"),
    Path("strategy_lab/policies/EVIDENCE_TIER_POLICY.md"),
    Path("strategy_lab/policies/EXPERIMENT_LANE_POLICY.md"),
    Path("strategy_lab/policies/PAPER_FORWARD_FREEZE_POLICY.md"),
    Path("strategy_lab/promotion_thresholds.yaml"),
    Path("strategy_lab/strategy_registry.yaml"),
]

REQUIRED_OUTPUTS = [
    "promotion_gap_summary.md",
    "closest_to_promotion.csv",
    "failure_mode_summary.csv",
    "watchlist_next_actions.csv",
    "blocked_gated_summary.csv",
    "too_risky_summary.csv",
    "too_slow_summary.csv",
    "duplicate_near_duplicate_summary.csv",
    "protected_rows_summary.csv",
    "next_research_lane_recommendation.md",
    "next_allowed_action.md",
    "promotion_gap_manifest.json",
    "promotion_gap_consistency_check.json",
    "promotion_gap_packet.zip",
]

OPTIONAL_OUTPUTS = [
    "promotion_gap_score_details.csv",
    "missing_evidence_by_row.csv",
    "lane_opportunity_matrix.csv",
    "research_lane_ranking.csv",
    "near_candidate_decision_tree.md",
]

FAILURE_MODES = {
    "protected_active_observation",
    "protected_frozen_control",
    "protected_historical_leader",
    "ready_for_candidate_exhaustive",
    "promotion_review_required",
    "watchlist_insufficient_evidence",
    "watchlist_short_history",
    "watchlist_missing_diagnostics",
    "watchlist_needs_stress_check",
    "watchlist_needs_attribution",
    "too_risky_drawdown_budget",
    "too_risky_stop_hit_rate",
    "too_risky_leverage_or_unapproved_mechanics",
    "too_slow_target_dilution",
    "duplicate_existing_leader",
    "blocked_data_access",
    "blocked_provider_terms",
    "blocked_instrument_policy",
    "blocked_survivorship_or_point_in_time_data",
    "rejected_low_value",
    "rejected_worse_than_controls",
    "evidence_missing",
    "unknown",
}


@dataclass(frozen=True)
class GapClassification:
    failure_mode: str
    reason: str


def rel_path(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def now_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def is_missing_value(value: object) -> bool:
    text = str(value or "").strip()
    return text == "" or text.lower() in {"nan", "none", "null", "missing", "unavailable"}


def to_float(value: object) -> float | None:
    if is_missing_value(value):
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def joined_text(row: dict[str, str], fields: Iterable[str] | None = None) -> str:
    fields = fields or row.keys()
    return " ".join(str(row.get(field, "")) for field in fields).lower()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def require_core_inputs(project_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    core_path = rel_path(CORE_INPUT, project_root)
    if not core_path.exists():
        raise FileNotFoundError(
            f"Required promotion decisions file is missing: {core_path}. "
            "Run `.venv/bin/python run_promotion_review.py` first."
        )
    rows = read_csv_rows(core_path)
    if not rows:
        raise ValueError(f"Required promotion decisions file has no rows: {core_path}")
    missing_columns = sorted(REQUIRED_DECISION_COLUMNS.difference(rows[0].keys()))
    if missing_columns:
        raise ValueError(
            f"promotion_decisions.csv is missing required columns: {', '.join(missing_columns)}"
        )
    missing_files = [
        str(path)
        for path in INPUT_FILES
        if not rel_path(path, project_root).exists()
    ]
    return rows, missing_files


def classify_failure_mode(row: dict[str, str]) -> GapClassification:
    decision = row.get("promotion_decision", "").strip()
    current_status = row.get("current_status", "").strip().lower()
    primary_failure = row.get("primary_failure_mode", "").strip().lower()
    blocked_reason = row.get("blocked_reason", "").strip().lower()
    duplicate_of = row.get("duplicate_of", "").strip()
    missing_text = joined_text(row, ["missing_evidence", "evidence_needed", "promotion_reason"])
    all_text = joined_text(row)
    detail_text = joined_text(
        row,
        [
            "strategy_id",
            "family",
            "instrument_lane",
            "current_status",
            "promotion_decision",
            "promotion_reason",
            "primary_failure_mode",
            "duplication_risk",
            "risk_budget_status",
            "missing_evidence",
            "evidence_needed",
            "blocked_reason",
            "duplicate_of",
            "recommended_next_action",
        ],
    )

    if decision == "keep_active_observation":
        return GapClassification(
            "protected_active_observation",
            "Active paper/demo observation is protected from mutation.",
        )
    if decision == "keep_frozen_control":
        return GapClassification(
            "protected_frozen_control",
            "Frozen control or benchmark row is preserved for comparison.",
        )
    if decision == "mark_historical_leader":
        return GapClassification(
            "protected_historical_leader",
            "Historical leader remains preserved as a comparison row.",
        )
    if decision == "promote_to_candidate_exhaustive_queue":
        return GapClassification(
            "ready_for_candidate_exhaustive",
            "Promotion review queued the row for future candidate_exhaustive validation.",
        )
    if decision.startswith("promotion_review_required"):
        return GapClassification(
            "promotion_review_required",
            "Promotion review requested a specific follow-up before queueing.",
        )
    if decision == "mark_duplicate_or_near_duplicate" or duplicate_of:
        return GapClassification(
            "duplicate_existing_leader",
            f"Row duplicates or mostly inherits existing leader behavior ({duplicate_of or 'leader overlap flagged'}).",
        )
    if decision == "mark_too_risky":
        if any(term in detail_text for term in ["drawdown", "risk_budget", "risk budget", "breach", "high-risk"]):
            return GapClassification(
                "too_risky_drawdown_budget",
                "Drawdown or risk-budget behavior is too weak for promotion.",
            )
        if "stop" in primary_failure or "stop" in detail_text:
            return GapClassification(
                "too_risky_stop_hit_rate",
                "Stop-hit risk was the dominant risk concern.",
            )
        if any(term in detail_text for term in ["leverage", "margin", "shorting", "futures", "options", "forex", "intraday", "broker", "live-order", "live order"]):
            return GapClassification(
                "too_risky_leverage_or_unapproved_mechanics",
                "Risk or policy text references unapproved mechanics or leverage-like exposure.",
            )
        return GapClassification(
            "too_risky_drawdown_budget",
            "Drawdown or risk-budget behavior is too weak for promotion.",
        )
    if decision == "mark_too_slow":
        return GapClassification(
            "too_slow_target_dilution",
            "Defensive scaling or low target rates made the row too slow.",
        )
    if decision == "blocked":
        if any(term in detail_text for term in ["survivorship", "point-in-time", "point in time", "delisting", "delisted", "current-ticker", "current ticker"]):
            return GapClassification(
                "blocked_survivorship_or_point_in_time_data",
                "Serious evidence is blocked by survivorship, delisting, or point-in-time data requirements.",
            )
        if any(term in detail_text for term in ["provider", "terms", "subscription", "api key", "api_key", "package", "norgate", "sharadar", "access"]):
            return GapClassification(
                "blocked_provider_terms",
                blocked_reason or "Provider access, terms, package, or security review is unresolved.",
            )
        if any(term in detail_text for term in ["options", "futures", "forex", "intraday", "volatility", "broker", "perps", "perpetual"]):
            return GapClassification(
                "blocked_instrument_policy",
                "Instrument lane requires a separate policy, execution, or product gate.",
            )
        return GapClassification(
            "blocked_data_access",
            blocked_reason or "Data, provider, or implementation gate is unresolved.",
        )
    if decision == "reject":
        if any(term in all_text for term in ["worse", "controls", "benchmark"]):
            return GapClassification(
                "rejected_worse_than_controls",
                "Row was rejected because it failed against controls or benchmarks.",
            )
        return GapClassification("rejected_low_value", "Row has low research value under current gates.")
    if decision == "keep_watchlist":
        if "short" in all_text:
            return GapClassification(
                "watchlist_short_history",
                "Row is interesting but short-history limits confidence.",
            )
        if "stress" in missing_text:
            return GapClassification(
                "watchlist_needs_stress_check",
                "Watchlist row is missing stress evidence.",
            )
        if any(term in missing_text for term in ["attribution", "contribution"]):
            return GapClassification(
                "watchlist_needs_attribution",
                "Watchlist row is missing attribution or contribution evidence.",
            )
        if any(term in missing_text for term in ["diagnostic", "overlap", "co-movement", "independence"]):
            return GapClassification(
                "watchlist_missing_diagnostics",
                "Watchlist row is missing target-window or overlap diagnostics.",
            )
        if any(term in current_status for term in ["watchlist", "research_sample", "implemented"]):
            return GapClassification(
                "watchlist_insufficient_evidence",
                "Row remains watchlist because evidence is not strong enough for candidate_exhaustive.",
            )
    if is_missing_value(row.get("target_300_evidence")) and is_missing_value(row.get("drawdown_evidence")):
        return GapClassification(
            "evidence_missing",
            "Target and drawdown evidence are missing.",
        )
    return GapClassification("unknown", "Could not map row into the promotion-gap taxonomy.")


def has_evidence(row: dict[str, str], field: str) -> bool:
    return not is_missing_value(row.get(field))


def promotion_readiness_score(row: dict[str, str], failure_mode: str) -> tuple[int, str, list[str]]:
    decision = row.get("promotion_decision", "")
    if failure_mode.startswith("protected_") or decision == "reject":
        return 0, "not_close", ["protected_or_rejected"]

    score = 0
    reasons: list[str] = []
    evidence_tier = row.get("evidence_tier", "").lower()
    all_text = joined_text(row)

    if any(term in evidence_tier for term in ["research_sample", "credible", "tier1", "tier2"]):
        score += 20
        reasons.append("+20 evidence tier can support review")
    if has_evidence(row, "target_300_evidence") or has_evidence(row, "target_400_evidence"):
        score += 20
        reasons.append("+20 target evidence exists")
    else:
        score -= 20
        reasons.append("-20 missing target evidence")
    if has_evidence(row, "drawdown_evidence"):
        score += 15
        reasons.append("+15 drawdown evidence exists")
    else:
        score -= 20
        reasons.append("-20 missing drawdown evidence")
    if has_evidence(row, "stop_hit_evidence"):
        score += 15
        reasons.append("+15 stop-hit evidence exists")
    if has_evidence(row, "stress_evidence"):
        score += 10
        reasons.append("+10 stress evidence exists")
    else:
        score -= 15
        reasons.append("-15 stress evidence missing")

    missing_text = joined_text(row, ["missing_evidence", "evidence_needed"])
    if not any(term in missing_text for term in ["attribution", "contribution"]):
        score += 10
        reasons.append("+10 attribution not flagged as missing")
    else:
        score -= 15
        reasons.append("-15 attribution missing")

    if not failure_mode.startswith("blocked"):
        score += 10
        reasons.append("+10 not blocked by data/provider/instrument policy")
    else:
        score -= 40
        reasons.append("-40 blocked")
    if failure_mode.startswith("too_risky"):
        score -= 35
        reasons.append("-35 too risky")
    if failure_mode.startswith("too_slow"):
        score -= 25
        reasons.append("-25 too slow")
    if failure_mode == "duplicate_existing_leader":
        score -= 25
        reasons.append("-25 duplicate or near-duplicate")
    if "short" in all_text:
        score -= 15
        reasons.append("-15 short history")
    if "exploratory" in evidence_tier:
        score -= 10
        reasons.append("-10 exploratory evidence tier")
    if any(term in all_text for term in ["inherits", "mostly combo", "small tilt", "near duplicate"]):
        score -= 10
        reasons.append("-10 mostly inherits current leader behavior")

    score = max(0, min(100, score))
    if score >= 80:
        label = "near_candidate"
    elif score >= 60:
        label = "high_watchlist"
    elif score >= 40:
        label = "medium_watchlist"
    elif score >= 20:
        label = "low_watchlist"
    else:
        label = "not_close"
    return score, label, reasons


def recommended_watchlist_action(row: dict[str, str], failure_mode: str, score: int) -> tuple[str, str]:
    missing = joined_text(row, ["missing_evidence", "evidence_needed", "promotion_reason"])
    if failure_mode.startswith("blocked"):
        return "blocked_until_data_gate_resolved", "Resolve the named data/provider/instrument gate before further validation."
    if failure_mode == "duplicate_existing_leader":
        return "keep_watchlist_due_to_duplicate_behavior", "Only revisit if new target-window independence evidence appears."
    if failure_mode.startswith("too_risky"):
        return "run_drawdown_overlap_test", "Only revisit if fixed-risk evidence shows drawdown/stop behavior inside budget."
    if failure_mode.startswith("too_slow"):
        return "keep_watchlist_too_slow", "Only revisit if target rates improve without adding risk or tuning."
    if failure_mode == "watchlist_short_history":
        return "keep_watchlist_short_history", "Wait for longer history or use explicit short-history labels."
    if "stress" in missing or failure_mode == "watchlist_needs_stress_check":
        return "run_missing_stress_check", "Stress evidence is the specific missing promotion input."
    if any(term in missing for term in ["attribution", "contribution"]) or failure_mode == "watchlist_needs_attribution":
        return "run_missing_attribution", "Attribution/contribution is the specific missing promotion input."
    if any(term in missing for term in ["overlap", "independence", "co-movement"]) or failure_mode == "watchlist_missing_diagnostics":
        return "run_target_window_independence_test", "Target-window independence is the specific missing promotion input."
    if score >= 80:
        return "candidate_exhaustive_review_if_thresholds_met", "Near-candidate score requires threshold confirmation before queueing."
    if score >= 60:
        return "run_duplicate_overlap_test", "High watchlist row needs duplicate/overlap proof before deeper validation."
    return "reject_if_no_new_evidence", "No specific near-candidate gap is visible in current evidence."


def exact_evidence_needed(row: dict[str, str], failure_mode: str) -> str:
    existing = row.get("evidence_needed") or row.get("missing_evidence")
    if existing and not is_missing_value(existing):
        return existing
    mapping = {
        "watchlist_needs_stress_check": "stress degradation evidence",
        "watchlist_needs_attribution": "component attribution or contribution evidence",
        "watchlist_missing_diagnostics": "target-window independence and drawdown-overlap diagnostics",
        "duplicate_existing_leader": "incremental target windows versus existing leaders",
        "too_risky_drawdown_budget": "drawdown evidence inside the -$600 budget without tuning",
        "too_risky_stop_hit_rate": "stop-hit rate evidence inside policy threshold",
        "too_slow_target_dilution": "+300/+400 target evidence above minimum thresholds",
        "blocked_provider_terms": "provider/package/terms/security resolution",
        "blocked_data_access": "data access and cache/quality gate resolution",
        "blocked_instrument_policy": "instrument policy gate resolution",
        "blocked_survivorship_or_point_in_time_data": "survivorship-aware point-in-time data path",
    }
    return mapping.get(failure_mode, "specific missing evidence not identified")


def build_lane_ranking(
    failure_counts: Counter[str],
    duplicate_count: int,
    too_risky_count: int,
    too_slow_count: int,
    blocked_count: int,
) -> list[dict[str, object]]:
    lane_specs = [
        {
            "lane": "volatility_managed_equity_etf",
            "gap_fit": 90,
            "non_duplicate": 75,
            "drawdown_control": 85,
            "target_potential": 70,
            "data_feasibility": 90,
            "simplicity": 75,
            "policy_compatibility": 95,
            "false_confidence_risk": 35,
            "why": "Directly addresses too-risky equity/high-upside rows with ETF/fund data and risk controls.",
        },
        {
            "lane": "defensive_sector_rotation_etf",
            "gap_fit": 80,
            "non_duplicate": 65,
            "drawdown_control": 75,
            "target_potential": 65,
            "data_feasibility": 90,
            "simplicity": 70,
            "policy_compatibility": 95,
            "false_confidence_risk": 40,
            "why": "May improve sector exposure while staying in ETF/fund policy lanes.",
        },
        {
            "lane": "quality_low_volatility_etf_proxy",
            "gap_fit": 78,
            "non_duplicate": 70,
            "drawdown_control": 80,
            "target_potential": 55,
            "data_feasibility": 90,
            "simplicity": 80,
            "policy_compatibility": 95,
            "false_confidence_risk": 35,
            "why": "Targets drawdown control and non-duplicate defensive behavior, but may be too slow.",
        },
        {
            "lane": "global_risk_on_risk_off_etf",
            "gap_fit": 72,
            "non_duplicate": 55,
            "drawdown_control": 70,
            "target_potential": 65,
            "data_feasibility": 85,
            "simplicity": 70,
            "policy_compatibility": 95,
            "false_confidence_risk": 45,
            "why": "Could broaden regimes, but current global/multi-asset rows already showed duplication risk.",
        },
        {
            "lane": "carry_yield_etf_proxy",
            "gap_fit": 62,
            "non_duplicate": 70,
            "drawdown_control": 65,
            "target_potential": 45,
            "data_feasibility": 80,
            "simplicity": 65,
            "policy_compatibility": 90,
            "false_confidence_risk": 45,
            "why": "Possible diversifier, but likely slower than challenge target needs.",
        },
        {
            "lane": "managed_futures_etf_wrapper",
            "gap_fit": 58,
            "non_duplicate": 75,
            "drawdown_control": 70,
            "target_potential": 45,
            "data_feasibility": 75,
            "simplicity": 60,
            "policy_compatibility": 75,
            "false_confidence_risk": 60,
            "why": "Potential diversifier, but current wrapper evidence is too slow/gated and product interpretation is tricky.",
        },
        {
            "lane": "commodity_wrapper_reopen",
            "gap_fit": 45,
            "non_duplicate": 45,
            "drawdown_control": 45,
            "target_potential": 70,
            "data_feasibility": 85,
            "simplicity": 70,
            "policy_compatibility": 80,
            "false_confidence_risk": 65,
            "why": "Commodity rows showed target power but failed risk budget or duplicated combo behavior.",
        },
        {
            "lane": "crypto_spot_reopen",
            "gap_fit": 35,
            "non_duplicate": 60,
            "drawdown_control": 25,
            "target_potential": 85,
            "data_feasibility": 70,
            "simplicity": 55,
            "policy_compatibility": 65,
            "false_confidence_risk": 75,
            "why": "High upside remains dominated by drawdown and Tier 2 risk.",
        },
        {
            "lane": "individual_stock_momentum_provider_resolution",
            "gap_fit": 40,
            "non_duplicate": 85,
            "drawdown_control": 55,
            "target_potential": 75,
            "data_feasibility": 20,
            "simplicity": 30,
            "policy_compatibility": 60,
            "false_confidence_risk": 80,
            "why": "Potentially valuable, but still blocked by survivorship-aware provider access and terms.",
        },
        {
            "lane": "options_research_memo_only",
            "gap_fit": 15,
            "non_duplicate": 80,
            "drawdown_control": 20,
            "target_potential": 70,
            "data_feasibility": 15,
            "simplicity": 15,
            "policy_compatibility": 20,
            "false_confidence_risk": 90,
            "why": "Instrument lane is policy-gated; memo-only is appropriate.",
        },
        {
            "lane": "futures_research_memo_only",
            "gap_fit": 15,
            "non_duplicate": 80,
            "drawdown_control": 35,
            "target_potential": 65,
            "data_feasibility": 20,
            "simplicity": 20,
            "policy_compatibility": 20,
            "false_confidence_risk": 90,
            "why": "Direct futures remain gated; memo-only unless a separate futures lane is approved.",
        },
        {
            "lane": "forex_research_memo_only",
            "gap_fit": 12,
            "non_duplicate": 75,
            "drawdown_control": 35,
            "target_potential": 45,
            "data_feasibility": 20,
            "simplicity": 20,
            "policy_compatibility": 20,
            "false_confidence_risk": 85,
            "why": "Forex remains instrument-gated and outside current ETF/fund fast lane.",
        },
        {
            "lane": "no_new_lane_validate_current_observation",
            "gap_fit": 50,
            "non_duplicate": 40,
            "drawdown_control": 80,
            "target_potential": 35,
            "data_feasibility": 100,
            "simplicity": 90,
            "policy_compatibility": 100,
            "false_confidence_risk": 20,
            "why": "Useful if research queue is saturated, but it does not find a new candidate.",
        },
    ]
    for spec in lane_specs:
        score = (
            spec["gap_fit"]
            + spec["non_duplicate"]
            + spec["drawdown_control"]
            + spec["target_potential"]
            + spec["data_feasibility"]
            + spec["simplicity"]
            + spec["policy_compatibility"]
            - spec["false_confidence_risk"]
        )
        if too_risky_count > too_slow_count and spec["lane"] in {
            "volatility_managed_equity_etf",
            "quality_low_volatility_etf_proxy",
            "defensive_sector_rotation_etf",
        }:
            score += 20
        if duplicate_count >= 8 and spec["lane"] in {"global_risk_on_risk_off_etf", "commodity_wrapper_reopen"}:
            score -= 15
        if blocked_count >= 10 and spec["lane"] in {
            "individual_stock_momentum_provider_resolution",
            "options_research_memo_only",
            "futures_research_memo_only",
            "forex_research_memo_only",
        }:
            score -= 20
        spec["lane_score"] = score
    return sorted(lane_specs, key=lambda row: row["lane_score"], reverse=True)


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return "_None._\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def write_markdown_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    classified: list[dict[str, object]],
    missing_files: list[str],
    failure_counts: Counter[str],
    decision_counts: Counter[str],
    lane_ranking: list[dict[str, object]],
) -> None:
    closest = sorted(
        [row for row in classified if not str(row["failure_mode"]).startswith("protected_") and row["promotion_decision"] != "reject"],
        key=lambda row: (-int(row["closest_to_promotion_score"]), row["strategy_id"]),
    )
    top_closest = closest[:10]
    protected = [row for row in classified if str(row["failure_mode"]).startswith("protected_")]
    queued = [row for row in classified if row["failure_mode"] == "ready_for_candidate_exhaustive"]
    best_lane = lane_ranking[0]

    summary = [
        "# Promotion Gap Summary",
        "",
        "This is a promotion-gap analysis only. It reads existing evidence and does not run backtests, Profit Exploration, candidate_exhaustive, data downloads, provider APIs, or paper-forward activation.",
        "",
        f"- Rows reviewed: {len(rows)}",
        f"- Candidate_exhaustive queue rows: {len(queued)}",
        f"- Protected active/control/leader rows: {len(protected)}",
        f"- Dominant failure modes: {', '.join(f'{mode}={count}' for mode, count in failure_counts.most_common(5))}",
        f"- Next recommended lane: `{best_lane['lane']}`",
        f"- Exact next allowed action: `create_volatility_managed_equity_etf_fast_exploration_review_prompt`",
        "",
        "## Closest Rows",
        markdown_table(
            top_closest,
            [
                "strategy_id",
                "promotion_decision",
                "failure_mode",
                "closest_to_promotion_score",
                "readiness_label",
                "recommended_next_action",
            ],
        ),
        "## Missing Input Files",
        "\n".join(f"- {path}" for path in missing_files) if missing_files else "- None",
        "",
        "## Decision Counts",
        "\n".join(f"- {decision}: {count}" for decision, count in decision_counts.most_common()),
    ]
    (output_dir / "promotion_gap_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    recommendation = [
        "# Next Research Lane Recommendation",
        "",
        f"Recommended next lane: `{best_lane['lane']}`.",
        "",
        "Reason: the current promotion gap is dominated by too-risky high-upside rows, duplicate blends, and blocked provider/instrument lanes. A volatility-managed equity ETF lane best targets drawdown control while staying in the fast ETF/fund evidence policy and retaining plausible target potential.",
        "",
        "Do not reopen crypto now: standalone crypto rows are too risky and small crypto blends showed limited incremental value.",
        "",
        "Do not reopen commodity now: commodity wrappers showed target power, but the best blend was mostly existing combo behavior and the standalone rows breached the drawdown budget.",
        "",
        "Individual stock momentum remains blocked until survivorship-aware provider/package/terms/access issues are resolved.",
        "",
        "Instrument lanes such as options, direct futures, forex, intraday, leverage, margin, and broker/live-order mechanics remain gated or memo-only.",
        "",
        "## Lane Ranking",
        markdown_table(
            lane_ranking,
            [
                "lane",
                "lane_score",
                "gap_fit",
                "non_duplicate",
                "drawdown_control",
                "target_potential",
                "data_feasibility",
                "policy_compatibility",
                "why",
            ],
        ),
    ]
    (output_dir / "next_research_lane_recommendation.md").write_text("\n".join(recommendation) + "\n", encoding="utf-8")

    action = [
        "# Next Allowed Action",
        "",
        "Exact next allowed action:",
        "",
        "`create_volatility_managed_equity_etf_fast_exploration_review_prompt`",
        "",
        "The next prompt should be a review/design gate, not candidate_exhaustive and not paper-forward activation. It may define a fixed ETF/fund wrapper lane, data QA requirements, failure criteria, and research_sample-only evidence expectations.",
        "",
        "Forbidden in the next action unless separately approved: candidate_exhaustive, live trading, broker integration, order placement, real-money recommendations, leverage, margin, shorting, options, direct futures, forex, intraday logic, and mutation of active paper/demo rows.",
    ]
    (output_dir / "next_allowed_action.md").write_text("\n".join(action) + "\n", encoding="utf-8")

    tree = [
        "# Near-Candidate Decision Tree",
        "",
        "1. If a row is active paper/demo or frozen control, preserve it.",
        "2. If blocked by provider/data/instrument policy, resolve the gate first.",
        "3. If duplicate, require incremental target-window evidence before deeper validation.",
        "4. If too risky, require drawdown and stop evidence inside budget without tuning.",
        "5. If too slow, require materially better +300/+400 target evidence.",
        "6. Only queue candidate_exhaustive when target, drawdown, stop, stress, duplicate, and evidence-tier checks all pass.",
    ]
    (output_dir / "near_candidate_decision_tree.md").write_text("\n".join(tree) + "\n", encoding="utf-8")


def consistency_check(output_dir: Path, rows: list[dict[str, str]], classified: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    required_files = REQUIRED_OUTPUTS.copy()
    missing = [name for name in required_files if not (output_dir / name).exists()]
    if missing:
        errors.append(f"Missing required output files: {', '.join(missing)}")
    if not rows:
        errors.append("promotion_decisions.csv row count is zero")
    if any(row.get("failure_mode") not in FAILURE_MODES for row in classified):
        errors.append("At least one row has an invalid failure mode")
    if any(is_missing_value(row.get("failure_mode")) for row in classified):
        errors.append("At least one row lacks a classification")
    if any(parse_bool(row.get("real_money_recommendation")) for row in rows):
        errors.append("A row has real_money_recommendation true")
    if any(parse_bool(row.get("candidate_exhaustive_run")) for row in rows):
        errors.append("A row indicates candidate_exhaustive_run true")
    if any(
        row.get("failure_mode", "").startswith("blocked") and row.get("failure_mode") == "ready_for_candidate_exhaustive"
        for row in classified
    ):
        errors.append("A row is both blocked and ready for candidate_exhaustive")
    return {
        "consistency_passed": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "promotion_decisions_exists": True,
        "promotion_decisions_row_count": len(rows),
        "all_rows_classified": not any(is_missing_value(row.get("failure_mode")) for row in classified),
        "paper_forward_activated": False,
        "real_money_recommendation_added": False,
        "broker_integration_added": False,
        "live_order_path_added": False,
        "active_observations_changed": False,
        "frozen_controls_changed": False,
        "candidate_exhaustive_run": False,
        "backtest_triggered": False,
        "data_download_triggered": False,
        "provider_api_call_triggered": False,
    }


def zip_packet(output_dir: Path) -> None:
    zip_path = output_dir / "promotion_gap_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.name)


def run_gap_review(project_root: Path = PROJECT_ROOT, run_id: str | None = None) -> dict[str, object]:
    run_id = run_id or now_run_id()
    rows, missing_files = require_core_inputs(project_root)
    thresholds = load_yaml(rel_path(Path("strategy_lab/promotion_thresholds.yaml"), project_root))

    classified: list[dict[str, object]] = []
    for row in rows:
        classification = classify_failure_mode(row)
        score, label, score_reasons = promotion_readiness_score(row, classification.failure_mode)
        next_action, next_action_reason = recommended_watchlist_action(row, classification.failure_mode, score)
        evidence_needed = exact_evidence_needed(row, classification.failure_mode)
        classified.append(
            {
                **row,
                "failure_mode": classification.failure_mode,
                "failure_mode_reason": classification.reason,
                "closest_to_promotion_score": score,
                "readiness_label": label,
                "score_reason": "; ".join(score_reasons),
                "gap_recommended_next_action": next_action,
                "gap_next_action_reason": next_action_reason,
                "exact_evidence_needed_to_change_decision": evidence_needed,
            }
        )

    failure_counts = Counter(str(row["failure_mode"]) for row in classified)
    decision_counts = Counter(row.get("promotion_decision", "") for row in rows)
    duplicate_count = failure_counts["duplicate_existing_leader"]
    too_risky_count = sum(count for mode, count in failure_counts.items() if mode.startswith("too_risky"))
    too_slow_count = failure_counts["too_slow_target_dilution"]
    blocked_count = sum(count for mode, count in failure_counts.items() if mode.startswith("blocked"))
    lane_ranking = build_lane_ranking(failure_counts, duplicate_count, too_risky_count, too_slow_count, blocked_count)

    output_root = rel_path(OUTPUT_ROOT, project_root)
    run_dir = output_root / "runs" / run_id
    latest_dir = output_root / "latest"
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    closest_rows = sorted(
        [
            row
            for row in classified
            if not str(row["failure_mode"]).startswith("protected_") and row["promotion_decision"] != "reject"
        ],
        key=lambda row: (-int(row["closest_to_promotion_score"]), row["strategy_id"]),
    )
    watchlist_rows = [row for row in classified if row.get("promotion_decision") == "keep_watchlist"]
    blocked_rows = [row for row in classified if str(row["failure_mode"]).startswith("blocked")]
    too_risky_rows = [row for row in classified if str(row["failure_mode"]).startswith("too_risky")]
    too_slow_rows = [row for row in classified if row["failure_mode"] == "too_slow_target_dilution"]
    duplicate_rows = [row for row in classified if row["failure_mode"] == "duplicate_existing_leader"]
    protected_rows = [row for row in classified if str(row["failure_mode"]).startswith("protected_")]

    common_fields = [
        "strategy_id",
        "family",
        "instrument_lane",
        "evidence_tier",
        "current_status",
        "promotion_decision",
        "failure_mode",
        "closest_to_promotion_score",
        "readiness_label",
        "gap_recommended_next_action",
        "failure_mode_reason",
        "exact_evidence_needed_to_change_decision",
    ]
    write_csv(run_dir / "closest_to_promotion.csv", closest_rows, common_fields)
    write_csv(
        run_dir / "failure_mode_summary.csv",
        [
            {
                "failure_mode": mode,
                "row_count": count,
                "share_of_rows": round(count / len(rows), 4),
            }
            for mode, count in failure_counts.most_common()
        ],
        ["failure_mode", "row_count", "share_of_rows"],
    )
    write_csv(
        run_dir / "watchlist_next_actions.csv",
        watchlist_rows,
        [
            "strategy_id",
            "current_status",
            "promotion_decision",
            "failure_mode",
            "missing_evidence",
            "closest_to_promotion_score",
            "gap_recommended_next_action",
            "gap_next_action_reason",
            "exact_evidence_needed_to_change_decision",
        ],
    )
    write_csv(run_dir / "blocked_gated_summary.csv", blocked_rows, common_fields + ["blocked_reason"])
    write_csv(run_dir / "too_risky_summary.csv", too_risky_rows, common_fields + ["drawdown_evidence", "stop_hit_evidence"])
    write_csv(run_dir / "too_slow_summary.csv", too_slow_rows, common_fields + ["target_300_evidence", "target_400_evidence"])
    write_csv(run_dir / "duplicate_near_duplicate_summary.csv", duplicate_rows, common_fields + ["duplicate_of", "duplication_risk"])
    write_csv(run_dir / "protected_rows_summary.csv", protected_rows, common_fields + ["paper_forward_active"])
    write_csv(run_dir / "promotion_gap_score_details.csv", classified, common_fields + ["score_reason"])
    write_csv(
        run_dir / "missing_evidence_by_row.csv",
        [
            row
            for row in classified
            if not is_missing_value(row.get("missing_evidence")) or not is_missing_value(row.get("evidence_needed"))
        ],
        common_fields + ["missing_evidence", "evidence_needed"],
    )
    write_csv(
        run_dir / "lane_opportunity_matrix.csv",
        lane_ranking,
        [
            "lane",
            "gap_fit",
            "non_duplicate",
            "drawdown_control",
            "target_potential",
            "data_feasibility",
            "simplicity",
            "policy_compatibility",
            "false_confidence_risk",
            "lane_score",
            "why",
        ],
    )
    write_csv(
        run_dir / "research_lane_ranking.csv",
        lane_ranking,
        ["lane", "lane_score", "why"],
    )

    write_markdown_outputs(run_dir, rows, classified, missing_files, failure_counts, decision_counts, lane_ranking)

    manifest = {
        "run_id": run_id,
        "research_only": True,
        "rows_reviewed": len(rows),
        "missing_input_files": missing_files,
        "failure_mode_counts": dict(failure_counts),
        "decision_counts": dict(decision_counts),
        "next_recommended_research_lane": lane_ranking[0]["lane"],
        "exact_next_allowed_action": "create_volatility_managed_equity_etf_fast_exploration_review_prompt",
        "thresholds_loaded": bool(thresholds),
        "candidate_exhaustive_run": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "paper_forward_activated": False,
        "active_observations_changed": False,
        "frozen_controls_changed": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    (run_dir / "promotion_gap_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    pre_zip_consistency = consistency_check(run_dir, rows, classified)
    (run_dir / "promotion_gap_consistency_check.json").write_text(
        json.dumps(pre_zip_consistency, indent=2) + "\n",
        encoding="utf-8",
    )
    zip_packet(run_dir)
    final_consistency = consistency_check(run_dir, rows, classified)
    (run_dir / "promotion_gap_consistency_check.json").write_text(
        json.dumps(final_consistency, indent=2) + "\n",
        encoding="utf-8",
    )
    zip_packet(run_dir)

    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)

    if not final_consistency["consistency_passed"]:
        raise RuntimeError(f"Promotion gap consistency check failed: {final_consistency['errors']}")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_dir": str(latest_dir),
        "rows_reviewed": len(rows),
        "next_recommended_research_lane": lane_ranking[0]["lane"],
        "exact_next_allowed_action": "create_volatility_managed_equity_etf_fast_exploration_review_prompt",
        "consistency_passed": final_consistency["consistency_passed"],
        "candidate_exhaustive_run": False,
        "backtest_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
    }


def main() -> None:
    result = run_gap_review()
    print(f"promotion_gap_run_dir={result['run_dir']}")
    print(f"promotion_gap_latest_dir={result['latest_dir']}")
    print(f"rows_reviewed={result['rows_reviewed']}")
    print(f"next_recommended_research_lane={result['next_recommended_research_lane']}")
    print(f"exact_next_allowed_action={result['exact_next_allowed_action']}")
    print(f"consistency_passed={str(result['consistency_passed']).lower()}")
    print("candidate_exhaustive_run=false")
    print("backtest_run=false")
    print("data_downloaded=false")
    print("provider_api_called=false")


if __name__ == "__main__":
    main()
