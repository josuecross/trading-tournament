from __future__ import annotations

import argparse
import json
import math
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = REPO_ROOT / "strategy_lab" / "strategy_registry.yaml"
THRESHOLDS_PATH = REPO_ROOT / "strategy_lab" / "promotion_thresholds.yaml"
OUTPUT_ROOT = REPO_ROOT / "evidence" / "promotion_review"
STRATEGY_LAB_LATEST = REPO_ROOT / "evidence" / "strategy_lab" / "latest"
RESEARCH_STATE_LATEST = REPO_ROOT / "evidence" / "research_state" / "latest"
PROFIT_LATEST = REPO_ROOT / "evidence" / "profit_exploration" / "latest"

REQUIRED_OUTPUT_FILES = [
    "promotion_review_summary.md",
    "promotion_decisions.csv",
    "promotion_candidates.csv",
    "protected_successful_strategies.csv",
    "historical_success_registry.csv",
    "rejected_or_blocked_rows.csv",
    "duplicate_or_near_duplicate_rows.csv",
    "promotion_thresholds_used.yaml",
    "promotion_review_manifest.json",
    "promotion_review_warnings.md",
    "next_candidate_exhaustive_queue.md",
    "next_paper_forward_review_queue.md",
    "promotion_review_consistency_check.json",
]

DECISION_ALLOWED_NEXT_ACTION = {
    "promote_to_candidate_exhaustive_queue": "candidate_exhaustive_review",
    "promotion_review_required": "promotion_review_required",
    "keep_watchlist": "research_sample_review",
    "keep_active_observation": "observe_only",
    "keep_frozen_control": "compare_only",
    "mark_historical_leader": "research_sample_review",
    "mark_duplicate_or_near_duplicate": "duplicate_risk_review",
    "mark_too_risky": "research_sample_review",
    "mark_too_slow": "research_sample_review",
    "blocked": "resolve_blocker_before_review",
    "reject": "no_action",
}

CONTROL_IDS = {"SPY_200d_trend_model", "SPY_buy_hold", "BIL_cash_proxy", "GLD_buy_hold"}
HISTORICAL_LEADER_IDS = {"combo_SPY200d_GLD_50_50_v1", "profit_combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1"}

ALIASES = {
    "profit_combo_SPY200d_GLD_50_50_v1": {"profit_combo_SPY200d_GLD_50_50_v1", "combo_SPY200d_GLD_50_50_v1"},
    "combo_SPY200d_GLD_50_50_v1": {"profit_combo_SPY200d_GLD_50_50_v1", "combo_SPY200d_GLD_50_50_v1"},
}


@dataclass
class Metrics:
    p90_target_300: float | None = None
    p90_target_400: float | None = None
    p90_stop: float | None = None
    worst_90d_drawdown: float | None = None
    p180_target_300: float | None = None
    p180_target_400: float | None = None
    p180_stop: float | None = None
    worst_180d_drawdown: float | None = None
    stress_degradation: float | None = None
    verdict: str = ""
    duplicate_of: str = ""
    duplicate_status: str = ""
    candidate_exhaustive_recommended: bool = False
    source: str = ""
    high_correlation_to_leader: bool = False
    correlation_evidence: str = ""

    def merge(self, other: "Metrics") -> None:
        for field in self.__dataclass_fields__:
            if field in {"candidate_exhaustive_recommended", "high_correlation_to_leader"}:
                setattr(self, field, bool(getattr(self, field)) or bool(getattr(other, field)))
            elif not getattr(self, field) and getattr(other, field):
                setattr(self, field, getattr(other, field))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def list_value(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def aliases_for(strategy_id: str) -> set[str]:
    return set(ALIASES.get(strategy_id, {strategy_id}))


def any_alias_in(strategy_id: str, values: set[str]) -> bool:
    return bool(aliases_for(strategy_id) & values)


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing required registry: {REGISTRY_PATH}")
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def load_thresholds() -> dict[str, Any]:
    if not THRESHOLDS_PATH.exists():
        raise FileNotFoundError(f"Missing required thresholds: {THRESHOLDS_PATH}")
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")) or {}


def read_first_csv(*paths: Path) -> pd.DataFrame:
    for path in paths:
        frame = safe_read_csv(path)
        if not frame.empty:
            return frame
    return pd.DataFrame()


def evidence_sets() -> dict[str, set[str]]:
    active = read_first_csv(STRATEGY_LAB_LATEST / "active_observations.csv", RESEARCH_STATE_LATEST / "active_observations.csv")
    leaders = read_first_csv(STRATEGY_LAB_LATEST / "historical_leaders.csv", RESEARCH_STATE_LATEST / "historical_leaders.csv")
    candidate = read_first_csv(STRATEGY_LAB_LATEST / "candidate_status_matrix.csv", RESEARCH_STATE_LATEST / "candidate_status_matrix.csv")
    blocked = read_first_csv(STRATEGY_LAB_LATEST / "blocked_items.csv", RESEARCH_STATE_LATEST / "blocked_and_gated_items.csv")

    active_ids = set(active.get("strategy", pd.Series(dtype=str)).dropna().astype(str))
    active_ids.update(active.get("id", pd.Series(dtype=str)).dropna().astype(str))
    leader_ids = set(leaders.get("strategy", pd.Series(dtype=str)).dropna().astype(str))
    leader_ids.update(leaders.get("id", pd.Series(dtype=str)).dropna().astype(str))
    leader_ids.update(HISTORICAL_LEADER_IDS)
    if not candidate.empty and "candidate_id" in candidate:
        leader_like = candidate[
            candidate.get("latest_verdict", pd.Series(dtype=str)).astype(str).isin({"leading_profit_candidate", "practical_candidate"})
            | candidate.get("deserves_candidate_exhaustive", pd.Series(dtype=str)).astype(str).str.lower().isin({"true", "1"})
        ]
        leader_ids.update(leader_like["candidate_id"].dropna().astype(str))
    blocked_ids = set(blocked.get("id", pd.Series(dtype=str)).dropna().astype(str))
    blocked_ids.update(blocked.get("candidate_id", pd.Series(dtype=str)).dropna().astype(str))
    blocked_ids.update(blocked.get("strategy_id", pd.Series(dtype=str)).dropna().astype(str))
    return {"active": active_ids, "leaders": leader_ids, "blocked": blocked_ids}


def metrics_from_profit_rankings() -> dict[str, Metrics]:
    path = PROFIT_LATEST / "profit_rankings.csv"
    frame = safe_read_csv(path)
    metrics: dict[str, Metrics] = {}
    if frame.empty or "experiment_id" not in frame:
        return metrics
    for _, row in frame.iterrows():
        experiment_id = str(row.get("experiment_id", ""))
        if not experiment_id:
            continue
        metrics[experiment_id] = Metrics(
            p90_target_300=safe_float(row.get("p_90d_target_300_before_stop")),
            p90_target_400=safe_float(row.get("p_90d_target_400_before_stop")),
            p90_stop=safe_float(row.get("p_90d_any_stop_hit")),
            worst_90d_drawdown=safe_float(row.get("worst_90d_max_drawdown")),
            p180_target_300=safe_float(row.get("p_180d_target_300_before_stop")),
            p180_target_400=safe_float(row.get("p_180d_target_400_before_stop")),
            p180_stop=safe_float(row.get("p_180d_any_stop_hit")),
            worst_180d_drawdown=safe_float(row.get("worst_180d_max_drawdown")),
            stress_degradation=safe_float(row.get("stress_degradation")),
            verdict=str(row.get("practical_verdict_v2") or row.get("profit_verdict") or ""),
            duplicate_of=str(row.get("duplicate_of") or ""),
            duplicate_status=str(row.get("duplicate_status") or ""),
            source=path.as_posix(),
        )
    return metrics


def merge_metrics(target: dict[str, Metrics], source: dict[str, Metrics]) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = value
        else:
            target[key].merge(value)


def metrics_from_horizon_results(path: Path) -> dict[str, Metrics]:
    frame = safe_read_csv(path)
    metrics: dict[str, Metrics] = {}
    if frame.empty or "experiment_id" not in frame:
        return metrics
    rows = frame.copy()
    if "row_type" in rows:
        rows = rows[rows["row_type"].astype(str).eq("candidate_horizon")]
    if "horizon" not in rows:
        return metrics
    for experiment_id, group in rows.groupby("experiment_id"):
        metric = Metrics(source=path.as_posix())
        for _, row in group.iterrows():
            horizon = int(safe_float(row.get("horizon")) or 0)
            if horizon == 90:
                metric.p90_target_300 = safe_float(row.get("p_target_300_before_stop"))
                metric.p90_target_400 = safe_float(row.get("p_target_400_before_stop"))
                metric.p90_stop = safe_float(row.get("p_any_project_stop_hit"))
                metric.worst_90d_drawdown = safe_float(row.get("worst_max_drawdown"))
            if horizon == 180:
                metric.p180_target_300 = safe_float(row.get("p_target_300_before_stop"))
                metric.p180_target_400 = safe_float(row.get("p_target_400_before_stop"))
                metric.p180_stop = safe_float(row.get("p_any_project_stop_hit"))
                metric.worst_180d_drawdown = safe_float(row.get("worst_max_drawdown"))
            if not metric.verdict:
                metric.verdict = str(row.get("verdict") or "")
        metrics[str(experiment_id)] = metric
    return metrics


def metrics_from_status(path: Path) -> dict[str, Metrics]:
    frame = safe_read_csv(path)
    metrics: dict[str, Metrics] = {}
    if frame.empty or "experiment_id" not in frame:
        return metrics
    for _, row in frame.iterrows():
        experiment_id = str(row.get("experiment_id", ""))
        if not experiment_id:
            continue
        metrics[experiment_id] = Metrics(
            verdict=str(row.get("verdict") or row.get("status") or ""),
            candidate_exhaustive_recommended=safe_bool(row.get("candidate_exhaustive_recommended")),
            source=path.as_posix(),
        )
    return metrics


def metrics_from_candidate_matrix() -> dict[str, Metrics]:
    frame = read_first_csv(STRATEGY_LAB_LATEST / "candidate_status_matrix.csv", RESEARCH_STATE_LATEST / "candidate_status_matrix.csv")
    metrics: dict[str, Metrics] = {}
    if frame.empty or "candidate_id" not in frame:
        return metrics
    for _, row in frame.iterrows():
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id:
            continue
        metrics[candidate_id] = Metrics(
            verdict=str(row.get("latest_verdict") or ""),
            duplicate_status=str(row.get("duplicate_label") or ""),
            candidate_exhaustive_recommended=safe_bool(row.get("deserves_candidate_exhaustive")),
            source="candidate_status_matrix.csv",
        )
    return metrics


def apply_correlation_diagnostics(metrics: dict[str, Metrics]) -> None:
    diagnostic_paths = [
        REPO_ROOT / "evidence" / "multi_asset_lab" / "fast_exploration_batch1" / "latest" / "fast_exploration_batch1_diagnostics.csv",
        REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest" / "risk_control_batch1_diagnostics.csv",
        REPO_ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest" / "tier2_risk_control_batch1_diagnostics.csv",
    ]
    for path in diagnostic_paths:
        frame = safe_read_csv(path)
        if frame.empty or "experiment_id" not in frame:
            continue
        corr_col = "daily_equity_return_correlation"
        if corr_col not in frame:
            continue
        for _, row in frame.iterrows():
            experiment_id = str(row.get("experiment_id", ""))
            benchmark_id = str(row.get("benchmark_id", ""))
            corr = safe_float(row.get(corr_col))
            if not experiment_id or corr is None:
                continue
            if abs(corr) >= 0.85 and benchmark_id in HISTORICAL_LEADER_IDS | CONTROL_IDS:
                metric = metrics.setdefault(experiment_id, Metrics(source=path.as_posix()))
                metric.high_correlation_to_leader = True
                metric.correlation_evidence = f"{benchmark_id} correlation {corr:.3f}"


def collect_metrics() -> dict[str, Metrics]:
    metrics = metrics_from_profit_rankings()
    for path in [
        REPO_ROOT / "evidence" / "commodity_exploratory" / "latest" / "commodity_exploratory_results.csv",
        REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest" / "risk_control_batch1_results.csv",
        REPO_ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest" / "tier2_risk_control_batch1_results.csv",
        REPO_ROOT / "evidence" / "multi_asset_lab" / "fast_exploration_batch1" / "latest" / "fast_exploration_batch1_results.csv",
        REPO_ROOT / "evidence" / "combination_lab" / "latest" / "combination_batch1_results.csv",
    ]:
        merge_metrics(metrics, metrics_from_horizon_results(path))
    for path in [
        REPO_ROOT / "evidence" / "commodity_exploratory" / "latest" / "commodity_exploratory_status.csv",
        REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest" / "risk_control_batch1_status.csv",
        REPO_ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest" / "tier2_risk_control_batch1_status.csv",
        REPO_ROOT / "evidence" / "multi_asset_lab" / "fast_exploration_batch1" / "latest" / "fast_exploration_batch1_status.csv",
        REPO_ROOT / "evidence" / "combination_lab" / "latest" / "combination_batch1_status.csv",
    ]:
        merge_metrics(metrics, metrics_from_status(path))
    merge_metrics(metrics, metrics_from_candidate_matrix())
    apply_correlation_diagnostics(metrics)
    return metrics


def metric_for(strategy_id: str, metrics: dict[str, Metrics]) -> Metrics:
    combined = Metrics()
    for alias in aliases_for(strategy_id):
        if alias in metrics:
            combined.merge(metrics[alias])
    return combined


def row_text(row: dict[str, Any]) -> str:
    values = [
        row.get("id", ""),
        row.get("lane", ""),
        row.get("instrument_family", ""),
        row.get("strategy_family", ""),
        row.get("status", ""),
        row.get("credibility_tier", ""),
        row.get("implementation_status", ""),
        row.get("promotion_blockers", ""),
    ]
    return " ".join(str(value).lower() for value in values)


def classify_strategy(row: dict[str, Any], metrics: Metrics, sets: dict[str, set[str]], thresholds: dict[str, Any]) -> dict[str, Any]:
    strategy_id = str(row.get("id", ""))
    status = str(row.get("status", ""))
    lane = str(row.get("lane", ""))
    tier = str(row.get("credibility_tier", ""))
    implementation = str(row.get("implementation_status", ""))
    text = row_text(row)
    minimums = thresholds["promotion"]["minimum_candidate_exhaustive_requirements"]
    budget = thresholds["promotion"]["risk_budget"]

    active = bool(row.get("paper_forward_active")) or any_alias_in(strategy_id, sets["active"]) or status in {
        "active_observation",
        "active_paper_demo_observation",
    }
    frozen_control = strategy_id == "SPY_200d_trend_model" or strategy_id in CONTROL_IDS or tier == "benchmark" or status in {
        "benchmark",
        "benchmark_candidate",
    }
    historical_leader = any_alias_in(strategy_id, sets["leaders"]) or strategy_id in HISTORICAL_LEADER_IDS
    blocked = (
        implementation == "blocked_by_gate"
        or tier in {"blocked", "blocked_by_gate", "tier0_research_map"}
        or status in {"blocked", "deferred", "gated", "data_gated", "execution_gated", "complexity_gated"}
        or "individual_stock_momentum" in text
        or any(term in text for term in ["options_", "futures_", "forex_", "intraday", "broker", "live_order"])
    )
    policy_risky = any(term in text for term in ["leverage", "margin", "shorting", "perpetual", "direct futures"])
    duplicate = (
        "duplicate" in status
        or "duplicate" in metrics.duplicate_status.lower()
        or bool(metrics.duplicate_of)
        or metrics.high_correlation_to_leader
    )
    too_risky = (
        status in {"too_risky", "high_upside_high_risk_watchlist", "research_sample_candidate_risk_budget_breach", "watchlist_high_upside_high_drawdown"}
        or metrics.verdict in {"too_risky", "high_upside_high_risk_watchlist", "research_sample_candidate_risk_budget_breach"}
        or policy_risky
        or (metrics.p90_stop is not None and metrics.p90_stop > minimums["max_90d_stop_hit_rate"])
        or (metrics.p180_stop is not None and metrics.p180_stop > minimums["max_90d_stop_hit_rate"])
        or (metrics.worst_90d_drawdown is not None and abs(metrics.worst_90d_drawdown) > budget["max_drawdown_budget_dollars"])
        or (metrics.worst_180d_drawdown is not None and abs(metrics.worst_180d_drawdown) > budget["max_drawdown_budget_dollars"])
    )
    too_slow = status in {"too_slow", "too_slow_defensive_watchlist", "short_horizon_too_slow"} or metrics.verdict in {
        "too_slow",
        "too_slow_defensive_watchlist",
    }
    rejected = status in {"rejected", "reject_for_now", "reject_proxy_not_suitable", "reject_proxy_not_useful"} or metrics.verdict == "reject_for_now"
    missing_core_metrics = any(
        value is None
        for value in [
            metrics.p90_target_300,
            metrics.p90_target_400,
            metrics.p90_stop,
            metrics.worst_90d_drawdown,
        ]
    )
    target_pass = (
        metrics.p90_target_300 is not None
        and metrics.p90_target_400 is not None
        and metrics.p90_target_300 >= minimums["min_90d_target_300_before_stop_rate"]
        and metrics.p90_target_400 >= minimums["min_90d_target_400_before_stop_rate"]
    )
    risk_pass = (
        metrics.p90_stop is not None
        and metrics.worst_90d_drawdown is not None
        and metrics.p90_stop <= minimums["max_90d_stop_hit_rate"]
        and abs(metrics.worst_90d_drawdown) <= minimums["max_worst_drawdown_dollars"]
        and (metrics.p180_stop is None or metrics.p180_stop <= minimums["max_90d_stop_hit_rate"])
        and (metrics.worst_180d_drawdown is None or abs(metrics.worst_180d_drawdown) <= budget["max_drawdown_budget_dollars"])
    )
    tier_allows = tier in {
        "tier2_credible_prototype",
        "tier2_credible_prototype_candidate",
        "tier3_candidate_validation",
        "tier3_candidate_validation_candidate",
        "tier1_or_tier2_exploratory",
    }
    crypto_gate = "crypto" in text and "exchange_cost_24_7_review_required" in text

    decision = "keep_watchlist"
    reason = "Row remains watchlist because it does not clear all candidate_exhaustive queue checks."
    failure = "not_enough_incremental_evidence"
    evidence_needed = "research_sample metrics, duplicate diagnostics, and risk review"
    duplicate_risk = "not_flagged"
    risk_budget_status = "unavailable"
    blocked_reason = ""
    candidate_allowed = False
    paper_forward_allowed = False
    review_required = False

    if frozen_control:
        decision = "keep_frozen_control"
        reason = "Frozen control or benchmark/control row must remain preserved for comparison; no rule mutation is allowed."
        failure = "none"
        evidence_needed = "none; compare or observe only"
        risk_budget_status = "control_or_benchmark"
    elif active:
        decision = "keep_active_observation"
        reason = "Active paper/demo observation row is protected; review can record status but must not mutate rules or activate anything new."
        failure = "none"
        evidence_needed = "scheduled paper/demo checkpoint only"
        risk_budget_status = "observe_only"
    elif historical_leader:
        decision = "mark_historical_leader"
        reason = "Historical leader or serious challenger should be preserved as comparison evidence, not mutated or deleted."
        failure = "none"
        evidence_needed = "preserve and compare in future reviews"
        risk_budget_status = "leader_preserved"
    elif rejected:
        decision = "reject"
        reason = "Existing evidence already rejects this row or marks it reject_for_now."
        failure = "rejected_by_existing_evidence"
        evidence_needed = "new isolated version and fresh evidence required to reopen"
    elif blocked:
        decision = "blocked"
        reason = "Promotion is blocked by unresolved data, provider, terms, survivorship, instrument, or execution gate."
        failure = "blocked_by_gate"
        evidence_needed = "resolve blocker before any candidate_exhaustive queue decision"
        blocked_reason = str(row.get("promotion_blockers") or status or implementation)
    elif duplicate:
        decision = "mark_duplicate_or_near_duplicate"
        detail = metrics.correlation_evidence or metrics.duplicate_status or metrics.duplicate_of or status
        reason = f"Duplicate or near-duplicate behavior is already flagged ({detail}); do not promote without incremental target-window evidence."
        failure = "duplicate_or_near_duplicate"
        evidence_needed = "incremental target-window and attribution evidence"
        duplicate_risk = detail or "flagged"
    elif too_risky:
        decision = "mark_too_risky"
        reason = "Risk budget, stop rate, leverage/mechanics, or high-upside/high-risk status prevents promotion."
        failure = "risk_budget_or_policy_breach"
        evidence_needed = "risk-control evidence with drawdown inside budget"
        risk_budget_status = "breached_or_high_risk"
    elif too_slow:
        decision = "mark_too_slow"
        reason = "Row is defensive or slow relative to the +300/+400 challenge target."
        failure = "target_rate_too_slow"
        evidence_needed = "meaningful target-rate improvement without risk-budget breach"
        risk_budget_status = "controlled_but_too_slow"
    elif target_pass and risk_pass and tier_allows and not crypto_gate and not missing_core_metrics:
        if metrics.stress_degradation is None:
            decision = "promotion_review_required"
            reason = "Target and risk checks pass, but stress evidence is missing; require stress check before queueing."
            failure = "missing_stress_check"
            evidence_needed = "promotion_review_required_missing_stress_check"
            review_required = True
        else:
            decision = "promote_to_candidate_exhaustive_queue"
            reason = "Row meets configured target, stop, drawdown, stress, tier, and non-duplicate checks for future candidate_exhaustive review."
            failure = "none"
            evidence_needed = "future candidate_exhaustive prompt only; do not run automatically"
            candidate_allowed = True
    elif target_pass and risk_pass and crypto_gate:
        decision = "promotion_review_required"
        reason = "Target and risk checks pass, but crypto exchange/cost/24-7 execution review remains required before deeper validation."
        failure = "crypto_execution_review_required"
        evidence_needed = "promotion_review_required_missing_crypto_execution_review"
        review_required = True
    elif target_pass and risk_pass and missing_core_metrics:
        decision = "promotion_review_required"
        reason = "Partial target/risk evidence exists but at least one core promotion metric is missing."
        failure = "evidence_missing"
        evidence_needed = "promotion_review_required_missing_core_metrics"
        review_required = True
    elif missing_core_metrics and status in {"research_sample_candidate", "candidate_diagnostics_review_required"}:
        decision = "promotion_review_required"
        reason = "Candidate-like row lacks core metrics in latest evidence; exact missing fields must be exported before promotion."
        failure = "evidence_missing"
        evidence_needed = "promotion_review_required_missing_target_or_drawdown_fields"
        review_required = True
    else:
        if metrics.p90_target_300 is not None and metrics.p90_target_300 < minimums["min_90d_target_300_before_stop_rate"]:
            decision = "mark_too_slow"
            reason = "90d +300 target rate is below the configured candidate_exhaustive threshold."
            failure = "target_rate_too_slow"
            evidence_needed = "higher target-before-stop evidence"
        else:
            decision = "keep_watchlist"
            reason = "Evidence does not justify candidate_exhaustive queue, but the row may remain useful for comparison or later review."
            failure = "watchlist_not_promotable"
            evidence_needed = "stronger target/risk/duplicate diagnostics"

    if risk_budget_status == "unavailable":
        if metrics.worst_90d_drawdown is None:
            risk_budget_status = "evidence_missing"
        elif abs(metrics.worst_90d_drawdown) <= budget["max_drawdown_budget_dollars"]:
            risk_budget_status = "inside_90d_budget"
        else:
            risk_budget_status = "breaches_90d_budget"

    return {
        "strategy_id": strategy_id,
        "family": row.get("strategy_family", ""),
        "instrument_lane": row.get("instrument_family", ""),
        "registry_lane": lane,
        "evidence_tier": tier,
        "current_status": status,
        "implementation_status": implementation,
        "paper_forward_active": bool(row.get("paper_forward_active")),
        "real_money_recommendation": bool(row.get("real_money_recommendation")) if row.get("real_money_recommendation") is not None else False,
        "candidate_exhaustive_run": bool(row.get("candidate_exhaustive_run") or metrics.source and "candidate_exhaustive_completed" in status),
        "candidate_exhaustive_recommended": candidate_allowed,
        "promotion_review_required": review_required or decision == "promotion_review_required",
        "promotion_decision": decision,
        "promotion_reason": reason,
        "primary_failure_mode": failure,
        "duplication_risk": duplicate_risk,
        "risk_budget_status": risk_budget_status,
        "latest_evidence_path": row.get("latest_evidence_path", ""),
        "metrics_source": metrics.source,
        "target_300_evidence": metrics.p90_target_300,
        "target_400_evidence": metrics.p90_target_400,
        "drawdown_evidence": metrics.worst_90d_drawdown,
        "stop_hit_evidence": metrics.p90_stop,
        "stress_evidence": metrics.stress_degradation,
        "missing_evidence": evidence_needed if "missing" in evidence_needed else "",
        "evidence_needed": evidence_needed,
        "blocked_reason": blocked_reason,
        "duplicate_of": metrics.duplicate_of or row.get("duplicate_of", ""),
        "recommended_next_action": DECISION_ALLOWED_NEXT_ACTION[decision],
        "candidate_exhaustive_allowed": candidate_allowed,
        "paper_forward_allowed": paper_forward_allowed,
        "allowed_next_actions": list_value(row.get("allowed_next_actions") or row.get("allowed_next_action")),
        "forbidden_next_actions": list_value(row.get("forbidden_next_actions")),
    }


def decisions_frame(registry_data: dict[str, Any], thresholds: dict[str, Any]) -> pd.DataFrame:
    sets = evidence_sets()
    metrics = collect_metrics()
    decisions = [classify_strategy(row, metric_for(str(row.get("id", "")), metrics), sets, thresholds) for row in registry_data.get("strategies", [])]
    return pd.DataFrame(decisions)


def protected_frame(decisions: pd.DataFrame) -> pd.DataFrame:
    protected = decisions[decisions["promotion_decision"].isin(["keep_active_observation", "keep_frozen_control", "mark_historical_leader"])].copy()
    protected["role"] = protected["promotion_decision"]
    protected["why_preserved"] = protected["promotion_reason"]
    protected["can_be_changed"] = False
    return protected[
        [
            "strategy_id",
            "role",
            "current_status",
            "evidence_tier",
            "why_preserved",
            "can_be_changed",
            "allowed_next_actions",
            "forbidden_next_actions",
        ]
    ]


def build_summary(decisions: pd.DataFrame, run_id: str) -> str:
    counts = decisions["promotion_decision"].value_counts().to_dict()
    queued = decisions[decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")]
    review_required = decisions[decisions["promotion_decision"].eq("promotion_review_required")]
    lines = [
        "# Promotion Review Summary",
        "",
        "This is a research-only promotion review. It does not run candidate_exhaustive, change paper-forward rules, replace SPY_200d, add broker integration, place orders, or make real-money recommendations.",
        "",
        f"- run_id: `{run_id}`",
        f"- rows reviewed: `{len(decisions)}`",
        f"- candidate_exhaustive queue rows: `{len(queued)}`",
        f"- promotion_review_required rows: `{len(review_required)}`",
        f"- active observations protected: `{int(decisions['promotion_decision'].eq('keep_active_observation').sum())}`",
        f"- frozen controls/benchmarks protected: `{int(decisions['promotion_decision'].eq('keep_frozen_control').sum())}`",
        "",
        "## Decision Counts",
        "",
    ]
    for decision, count in sorted(counts.items()):
        lines.append(f"- `{decision}`: {count}")
    if queued.empty:
        lines.extend(["", "## Candidate Exhaustive Queue", "", "No row qualifies for automatic queueing in this review."])
    else:
        lines.extend(["", "## Candidate Exhaustive Queue", ""])
        for _, row in queued.iterrows():
            lines.append(f"- `{row['strategy_id']}`: {row['promotion_reason']}")
    return "\n".join(lines) + "\n"


def build_queue_markdown(decisions: pd.DataFrame, decision: str, title: str) -> str:
    rows = decisions[decisions["promotion_decision"].eq(decision)]
    lines = [f"# {title}", "", "This queue is research-only and does not execute any validation or activate paper-forward."]
    if rows.empty:
        lines.extend(["", "No rows currently qualify."])
    else:
        for _, row in rows.iterrows():
            lines.extend(
                [
                    "",
                    f"## {row['strategy_id']}",
                    "",
                    f"- decision: `{row['promotion_decision']}`",
                    f"- reason: {row['promotion_reason']}",
                    f"- next_action: `{row['recommended_next_action']}`",
                    f"- paper_forward_allowed_now: `{row['paper_forward_allowed']}`",
                    f"- candidate_exhaustive_allowed_now: `{row['candidate_exhaustive_allowed']}`",
                ]
            )
    return "\n".join(lines) + "\n"


def no_promotion_reason(decisions: pd.DataFrame) -> str:
    queued = decisions[decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")]
    if not queued.empty:
        return ""
    near = decisions[decisions["promotion_decision"].isin(["promotion_review_required", "keep_watchlist", "mark_too_risky"])].head(12)
    lines = [
        "# No Promotion Reason",
        "",
        "No row qualifies for candidate_exhaustive queue in this generic promotion review.",
        "",
        "## Closest Rows Or Useful Non-Promotions",
    ]
    for _, row in near.iterrows():
        lines.append(f"- `{row['strategy_id']}`: `{row['promotion_decision']}` because {row['promotion_reason']} Needed: {row['evidence_needed']}.")
    return "\n".join(lines) + "\n"


def build_warnings(decisions: pd.DataFrame) -> str:
    missing = decisions[decisions["primary_failure_mode"].eq("evidence_missing")]
    lines = [
        "# Promotion Review Warnings",
        "",
        "- Promotion review does not prove future performance.",
        "- Candidate_exhaustive queue is only a future validation queue, not an executed run.",
        "- Paper-forward activation remains a separate explicit review.",
        "- No real-money recommendation is made.",
    ]
    if not missing.empty:
        lines.extend(["", "## Evidence Missing Rows"])
        for _, row in missing.iterrows():
            lines.append(f"- `{row['strategy_id']}`: {row['evidence_needed']}")
    return "\n".join(lines) + "\n"


def consistency_check(decisions: pd.DataFrame, run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if decisions["real_money_recommendation"].astype(bool).any():
        errors.append("A row has real_money_recommendation=true.")
    newly_paper = decisions[
        decisions["promotion_decision"].isin(["promote_to_candidate_exhaustive_queue", "promotion_review_required", "keep_watchlist"])
        & decisions["paper_forward_active"].astype(bool)
    ]
    if not newly_paper.empty:
        errors.append("A non-protected decision is paper_forward_active.")
    if decisions["promotion_reason"].fillna("").astype(str).str.strip().eq("").any():
        errors.append("At least one row lacks a promotion reason.")
    blocked_and_promotable = decisions[
        decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")
        & decisions["primary_failure_mode"].astype(str).str.contains("blocked", case=False, na=False)
    ]
    if not blocked_and_promotable.empty:
        errors.append("A blocked row is marked promotable.")
    duplicate_and_promotable = decisions[
        decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")
        & decisions["primary_failure_mode"].astype(str).str.contains("duplicate", case=False, na=False)
    ]
    if not duplicate_and_promotable.empty:
        errors.append("A duplicate row is marked promotable.")
    for name in REQUIRED_OUTPUT_FILES:
        if name == "promotion_review_consistency_check.json":
            continue
        if not (run_dir / name).exists():
            errors.append(f"Missing required output file: {name}")
    queued = decisions[decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")]
    for _, row in queued.iterrows():
        needed = [row["target_300_evidence"], row["target_400_evidence"], row["drawdown_evidence"], row["stop_hit_evidence"]]
        if any(pd.isna(value) for value in needed):
            errors.append(f"Queued row {row['strategy_id']} lacks core evidence fields.")
    return {
        "consistency_status": "passed" if not errors else "failed",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "paper_forward_activated": False,
        "real_money_recommendation_added": False,
        "broker_integration_added": False,
        "live_orders_added": False,
        "candidate_exhaustive_run": False,
        "active_observation_rules_changed": False,
        "frozen_controls_changed": False,
    }


def write_outputs(decisions: pd.DataFrame, thresholds: dict[str, Any], output_root: Path = OUTPUT_ROOT) -> tuple[Path, Path]:
    run_id = utc_run_id()
    run_dir = output_root / "runs" / run_id
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    decisions.to_csv(run_dir / "promotion_decisions.csv", index=False)
    decisions[decisions["promotion_decision"].isin(["promote_to_candidate_exhaustive_queue", "promotion_review_required"])].to_csv(
        run_dir / "promotion_candidates.csv", index=False
    )
    protected_frame(decisions).to_csv(run_dir / "protected_successful_strategies.csv", index=False)
    decisions[decisions["promotion_decision"].isin(["mark_historical_leader", "keep_active_observation", "keep_frozen_control"])].to_csv(
        run_dir / "historical_success_registry.csv", index=False
    )
    decisions[decisions["promotion_decision"].isin(["blocked", "reject", "mark_too_risky", "mark_too_slow"])].to_csv(
        run_dir / "rejected_or_blocked_rows.csv", index=False
    )
    decisions[decisions["promotion_decision"].eq("mark_duplicate_or_near_duplicate")].to_csv(
        run_dir / "duplicate_or_near_duplicate_rows.csv", index=False
    )
    (run_dir / "promotion_thresholds_used.yaml").write_text(yaml.safe_dump(thresholds, sort_keys=False), encoding="utf-8")
    (run_dir / "promotion_review_summary.md").write_text(build_summary(decisions, run_id), encoding="utf-8")
    (run_dir / "promotion_review_warnings.md").write_text(build_warnings(decisions), encoding="utf-8")
    (run_dir / "next_candidate_exhaustive_queue.md").write_text(
        build_queue_markdown(decisions, "promote_to_candidate_exhaustive_queue", "Next Candidate Exhaustive Queue"),
        encoding="utf-8",
    )
    (run_dir / "next_paper_forward_review_queue.md").write_text(
        build_queue_markdown(decisions, "paper_forward_review_required", "Next Paper Forward Review Queue"),
        encoding="utf-8",
    )
    no_reason = no_promotion_reason(decisions)
    if no_reason:
        (run_dir / "no_promotion_reason.md").write_text(no_reason, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "research_only": True,
        "rows_reviewed": int(len(decisions)),
        "candidate_exhaustive_queue_count": int(decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue").sum()),
        "promotion_review_required_count": int(decisions["promotion_decision"].eq("promotion_review_required").sum()),
        "paper_forward_activated": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "candidate_exhaustive_run": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "data_downloaded": False,
        "active_observation_rules_changed": False,
        "spy200d_replaced": False,
    }
    (run_dir / "promotion_review_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    check = consistency_check(decisions, run_dir)
    (run_dir / "promotion_review_consistency_check.json").write_text(json.dumps(check, indent=2, sort_keys=True), encoding="utf-8")
    if check["consistency_status"] != "passed":
        raise RuntimeError(f"Promotion review consistency failed: {check['errors']}")

    shutil.copytree(run_dir, latest_dir)
    zip_path = output_root / "latest_promotion_review_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run evidence-backed promotion review.")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_data = load_registry()
    thresholds = load_thresholds()
    decisions = decisions_frame(registry_data, thresholds)
    run_dir, latest_dir = write_outputs(decisions, thresholds, Path(args.output_root))
    queued = decisions[decisions["promotion_decision"].eq("promote_to_candidate_exhaustive_queue")]
    review_required = decisions[decisions["promotion_decision"].eq("promotion_review_required")]
    print(f"promotion_review_run_dir={run_dir}")
    print(f"promotion_review_latest_dir={latest_dir}")
    print(f"promotion_review_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    print(f"candidate_exhaustive_queue_count={len(queued)}")
    print(f"promotion_review_required_count={len(review_required)}")
    print("candidate_exhaustive_run=false")
    print("paper_forward_activated=false")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
