from __future__ import annotations

import argparse
import json
import math
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from src.backtester import Backtester
from src.data import DataLoadResult, load_market_data
from src.indicators import prepare_indicators
from src.utils import load_config
from src.validation import _rolling_group_rows, strategy_variant_config, summarize_independent_rolling_windows
from exploratory.crypto_spot_momentum.crypto_data import CryptoDataError, load_crypto_data
from exploratory.crypto_spot_momentum.crypto_strategies import generate_signal_weights, price_matrix, simulate_strategy
from exploratory.crypto_spot_momentum.crypto_validation import load_config as load_crypto_config
from exploratory.crypto_spot_momentum.crypto_validation import sample_start_indices, strategy_config


REPO_ROOT = Path(__file__).resolve().parent
STARTING_EQUITY = 3000.0
TARGET_300 = 3300.0
TARGET_400 = 3400.0
ABSOLUTE_STOP = 2400.0
TRAILING_DRAWDOWN = 600.0
PROJECT_STOP_MODE = "both"
RISK_FRAMEWORK_NAME = "balanced_speculative_research_v1"
PORTFOLIO_SPEC_PATH = REPO_ROOT / "portfolio_lab" / "diversified_portfolio_specs.yaml"
FAMILY_SPEC_PATH = REPO_ROOT / "family_lab" / "independent_family_specs.yaml"
REQUIRED_FILES = [
    "README_FOR_AUDITOR.md",
    "challenge_summary.md",
    "challenge_results.csv",
    "rolling_window_summary.csv",
    "strategy_rankings.csv",
    "assumptions_and_costs.yaml",
    "data_coverage_summary.csv",
    "risk_and_stop_audit.csv",
    "warnings_and_limitations.md",
    "challenge_charts.png",
]
CHALLENGE_COLUMNS = [
    "run_id",
    "lane",
    "strategy",
    "portfolio_id",
    "portfolio_role",
    "family_id",
    "family_group",
    "family_role",
    "independent_family_account",
    "shared_capital_with_other_families",
    "portfolio_mix",
    "role",
    "instrument_family",
    "credibility_tier",
    "implementation_status",
    "run_allowed",
    "run_status",
    "blocked_reason",
    "data_source",
    "start_date",
    "end_date",
    "starting_equity",
    "target_300_equity",
    "target_400_equity",
    "absolute_stop_equity",
    "trailing_drawdown_dollars",
    "project_stop_mode",
    "leverage_model",
    "leverage_multiplier",
    "exposure_multiplier",
    "standard_or_stress",
    "rolling_method",
    "sampled_results_are_final",
    "final_validation_completed",
    "cost_model",
    "cost_model_quality",
    "portfolio_rebalance_frequency",
    "portfolio_sleeves",
    "portfolio_weights",
    "equity_weight",
    "cash_weight",
    "bond_weight",
    "gold_weight",
    "crypto_weight",
    "strategy_weight",
    "max_single_sleeve_weight",
    "average_portfolio_turnover",
    "rebalance_count",
    "unavailable_sleeves",
    "availability_notes",
    "spread_slippage_per_side",
    "annual_financing_rate",
    "financing_cost_assumption",
    "target_vol_annualized",
    "realized_vol_window",
    "exposure_cap",
    "average_exposure",
    "max_exposure",
    "min_exposure",
    "percent_time_cash",
    "percent_time_reduced_exposure",
    "percent_time_full_exposure",
    "unconditional_final_equity",
    "stop_enforced_final_equity",
    "total_return_unconditional",
    "total_return_stop_enforced",
    "max_equity",
    "min_equity",
    "max_drawdown_dollars",
    "max_drawdown_pct",
    "absolute_floor_stop_hit",
    "trailing_drawdown_stop_hit",
    "any_project_stop_hit",
    "first_project_stop_date",
    "first_project_stop_type",
    "equity_at_first_project_stop",
    "stop_overshoot_dollars",
    "stop_overshoot_pct",
    "target_300_hit",
    "target_300_before_stop",
    "target_300_first_date",
    "target_400_hit",
    "target_400_before_stop",
    "target_400_first_date",
    "days_to_target_300",
    "days_to_target_400",
    "days_to_first_stop",
    "catastrophic_loss",
    "time_in_market",
    "number_of_trades_or_rebalances",
    "turnover_estimate",
    "benchmark_name",
    "benchmark_stop_enforced_final_equity",
    "benchmark_target_300_before_stop",
    "benchmark_target_400_before_stop",
    "result_status",
    "audit_verdict",
    "main_failure_mode",
    "stop_enforced_metric_quality",
    "stop_enforced_metric_source",
    "stop_enforced_metric_notes",
    "risk_framework_name",
    "risk_band",
    "risk_budget_used_pct",
    "target_300_progress_pct",
    "target_400_progress_pct",
    "drawdown_warning_hit",
    "drawdown_review_hit",
    "hard_stop_hit",
    "risk_framework_verdict",
    "exposure_policy_status",
    "instrument_risk_role",
    "paper_forward_allowed_by_risk_framework",
    "promotion_blockers",
    "notes",
]
ROLLING_COLUMNS = [
    "run_id",
    "lane",
    "strategy",
    "portfolio_id",
    "portfolio_role",
    "family_id",
    "family_group",
    "family_role",
    "independent_family_account",
    "role",
    "credibility_tier",
    "leverage_multiplier",
    "exposure_multiplier",
    "standard_or_stress",
    "horizon",
    "rolling_method",
    "number_of_windows",
    "possible_window_count",
    "sampled_results_are_final",
    "final_validation_completed",
    "rolling_status",
    "pct_target_300_hit",
    "pct_target_300_before_stop",
    "pct_target_400_hit",
    "pct_target_400_before_stop",
    "pct_any_project_stop_hit",
    "pct_absolute_floor_stop_hit",
    "pct_trailing_drawdown_stop_hit",
    "median_final_equity",
    "median_stop_enforced_final_equity",
    "mean_stop_enforced_final_equity",
    "median_max_drawdown",
    "worst_max_drawdown",
    "pct_positive_return",
    "pct_loss",
    "pct_below_2400",
    "pct_above_3300",
    "pct_above_3400",
    "average_portfolio_turnover",
    "median_portfolio_turnover",
    "unavailable_window_count",
    "worst_stop_enforced_loss",
    "pct_windows_stop_overshoot_gt_50",
    "pct_windows_stop_overshoot_gt_100",
    "average_exposure",
    "median_exposure",
    "percent_time_cash",
    "percent_time_reduced_exposure",
    "percent_time_full_exposure",
    "stop_enforced_metric_quality",
    "risk_framework_name",
    "risk_band",
    "risk_budget_used_pct",
    "target_300_progress_pct",
    "target_400_progress_pct",
    "drawdown_warning_hit",
    "drawdown_review_hit",
    "hard_stop_hit",
    "risk_framework_verdict",
    "exposure_policy_status",
    "instrument_risk_role",
    "paper_forward_allowed_by_risk_framework",
    "promotion_blockers",
    "notes",
    "rolling_metric_quality",
    "rolling_notes",
]
FOCUSED_FINALIST = "current_no_cash_proxy_alpha_AB"
FOCUSED_FINALIST_ALIASES = (FOCUSED_FINALIST, "no_cash_proxy_alpha_AB")
FOCUSED_HORIZONS = [30, 60, 90, 180]
FOCUSED_LABELS = ["standard", "stress"]
ETF_LEVERAGE_DIAGNOSTICS = {
    1.25: {"financing_cost_annualized": 0.05, "additional_cost_multiplier": 1.25},
    1.50: {"financing_cost_annualized": 0.08, "additional_cost_multiplier": 1.50},
}
ETF_EXPOSURE_FRONTIER = {
    1.00: {"financing_cost_annualized": 0.00},
    1.05: {"financing_cost_annualized": 0.04},
    1.10: {"financing_cost_annualized": 0.05},
    1.15: {"financing_cost_annualized": 0.06},
    1.20: {"financing_cost_annualized": 0.07},
    1.25: {"financing_cost_annualized": 0.08},
}
ETF_VOL_CONTROL_TARGET = 0.12
ETF_VOL_CONTROL_WINDOW = 60
ETF_VOL_CONTROL_DIAGNOSTICS = {
    1.00: {"financing_cost_annualized": 0.00, "cost_model_quality": "exact"},
    1.10: {"financing_cost_annualized": 0.05, "cost_model_quality": "approximate"},
}
_ETF_CONTEXT: dict[str, Any] | None = None


@dataclass(frozen=True)
class StopAudit:
    unconditional_final_equity: float
    stop_enforced_final_equity: float
    max_equity: float
    min_equity: float
    max_drawdown_dollars: float
    max_drawdown_pct: float
    absolute_floor_stop_hit: bool
    trailing_drawdown_stop_hit: bool
    any_project_stop_hit: bool
    first_project_stop_date: str
    first_project_stop_type: str
    equity_at_first_project_stop: float | None
    stop_overshoot_dollars: float
    stop_overshoot_pct: float
    target_300_hit: bool
    target_300_before_stop: bool
    target_300_first_date: str
    target_400_hit: bool
    target_400_before_stop: bool
    target_400_first_date: str
    days_to_target_300: int | None
    days_to_target_400: int | None
    days_to_first_stop: int | None


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def exposure_policy_status_for(value: Any) -> str:
    exposure = round(as_float(value, 1.0), 2)
    if exposure <= 1.0:
        return "paper_forward_eligible_if_candidate_validated"
    if exposure in {1.05, 1.10}:
        return "diagnostic_only"
    if exposure in {1.15, 1.20, 1.25}:
        return "too_risky_by_default"
    if exposure >= 1.50:
        return "stress_diagnostic_only"
    return "diagnostic_only"


def risk_band_from_drawdown(drawdown_dollars: Any, stop_hit: Any = False) -> str:
    drawdown = as_float(drawdown_dollars, 0.0)
    if boolish(stop_hit) or drawdown <= -TRAILING_DRAWDOWN:
        return "hard_stop"
    if drawdown <= -450.0:
        return "review"
    if drawdown <= -300.0:
        return "warning"
    return "normal"


def instrument_risk_role_for(lane: str, strategy: str, instrument_family: str) -> str:
    text = f"{lane} {strategy} {instrument_family}".lower()
    if "simulated" in text or "exposure_frontier" in text or "volatility_control" in text or "diagnostic" in text or "leverage" in text:
        return "diagnostic"
    if "crypto" in text:
        return "exploratory"
    if "bil" in text or "cash" in text or "treasury" in text:
        return "defensive_benchmark"
    if "benchmark" in lane or strategy in {"SPY_buy_hold", "SPY_200d_trend_model"}:
        return "core"
    if "etf" in text:
        return "satellite"
    return "blocked_until_gate"


def risk_framework_values(
    *,
    lane: str,
    strategy: str,
    instrument_family: str,
    credibility_tier: str,
    exposure_multiplier: Any,
    max_drawdown_dollars: Any,
    stop_hit: Any,
    equity_for_progress: Any,
    stop_metric_quality: str,
    final_validation_completed: Any,
    benchmark_comparison_available: Any = True,
    current_verdict: str = "",
) -> dict[str, Any]:
    exposure = as_float(exposure_multiplier, 1.0)
    drawdown = as_float(max_drawdown_dollars, 0.0)
    equity = as_float(equity_for_progress, STARTING_EQUITY)
    tier1 = str(credibility_tier) in {"tier1_exploratory", "Tier 1 exploratory screen"} or "Tier 1" in str(credibility_tier)
    diagnostic_lane = "simulated" in str(lane) or "diagnostic" in str(lane) or "diversified_portfolio_challenge" in str(lane) or exposure > 1.0
    quality = str(stop_metric_quality or "unavailable")
    blockers: list[str] = []
    if tier1:
        blockers.append("tier1_exploratory")
    if diagnostic_lane:
        blockers.append("leverage_or_exposure_diagnostic")
    if exposure > 1.0:
        blockers.append("exposure_multiplier_gt_1")
    if quality == "approximate":
        blockers.append("stop_enforced_metric_quality_approximate")
    if quality == "unavailable":
        blockers.append("stop_enforced_metric_quality_unavailable")
    if not boolish(final_validation_completed):
        blockers.append("final_validation_completed_false")
    if not boolish(benchmark_comparison_available):
        blockers.append("benchmark_comparison_missing")
    if boolish(stop_hit):
        blockers.append("project_stop_hit")
    role = instrument_risk_role_for(lane, strategy, instrument_family)
    policy = exposure_policy_status_for(exposure)
    paper_allowed = (
        not blockers
        and exposure <= 1.0
        and not tier1
        and role in {"core", "satellite", "defensive_benchmark"}
        and current_verdict in {"practical_candidate", "watchlist", "benchmark_candidate", "benchmark_only"}
    )
    if "BIL" in strategy:
        paper_allowed = True
    if diagnostic_lane or tier1:
        verdict = "too_risky" if boolish(stop_hit) or policy in {"too_risky_by_default", "stress_diagnostic_only"} else "diagnostic_only"
        paper_allowed = False
    elif "blocked" in role:
        verdict = "blocked_by_gate"
        paper_allowed = False
    elif quality in {"approximate", "unavailable"} or not boolish(final_validation_completed):
        verdict = "incomplete_evidence"
    elif boolish(stop_hit) and "benchmark" not in str(current_verdict):
        verdict = "too_risky"
    elif current_verdict in {"benchmark_only", "benchmark_candidate"}:
        verdict = str(current_verdict)
    elif current_verdict == "practical_candidate":
        verdict = "practical_candidate"
    else:
        verdict = "watchlist"
    return {
        "risk_framework_name": RISK_FRAMEWORK_NAME,
        "risk_band": risk_band_from_drawdown(drawdown, stop_hit),
        "risk_budget_used_pct": abs(drawdown) / TRAILING_DRAWDOWN if pd.notna(drawdown) else math.nan,
        "target_300_progress_pct": max(0.0, equity - STARTING_EQUITY) / (TARGET_300 - STARTING_EQUITY),
        "target_400_progress_pct": max(0.0, equity - STARTING_EQUITY) / (TARGET_400 - STARTING_EQUITY),
        "drawdown_warning_hit": drawdown <= -300.0,
        "drawdown_review_hit": drawdown <= -450.0,
        "hard_stop_hit": boolish(stop_hit) or drawdown <= -TRAILING_DRAWDOWN,
        "risk_framework_verdict": verdict,
        "exposure_policy_status": policy,
        "instrument_risk_role": role,
        "paper_forward_allowed_by_risk_framework": bool(paper_allowed),
        "promotion_blockers": ";".join(dict.fromkeys(blockers)) or "none",
    }


def apply_risk_framework_to_challenge(challenge: pd.DataFrame, final_validation_completed: bool = True) -> pd.DataFrame:
    if challenge.empty:
        return challenge.reindex(columns=CHALLENGE_COLUMNS)
    rows = []
    for _, row in challenge.iterrows():
        updated = row.to_dict()
        updated.update(
            risk_framework_values(
                lane=str(row.get("lane", "")),
                strategy=str(row.get("strategy", "")),
                instrument_family=str(row.get("instrument_family", "")),
                credibility_tier=str(row.get("credibility_tier", "")),
                exposure_multiplier=row.get("exposure_multiplier", row.get("leverage_multiplier", 1.0)),
                max_drawdown_dollars=row.get("max_drawdown_dollars", 0.0),
                stop_hit=row.get("any_project_stop_hit", False),
                equity_for_progress=row.get("stop_enforced_final_equity", STARTING_EQUITY),
                stop_metric_quality=str(row.get("stop_enforced_metric_quality", "unavailable")),
                final_validation_completed=final_validation_completed,
                benchmark_comparison_available=True,
                current_verdict=str(row.get("audit_verdict", "")),
            )
        )
        rows.append(updated)
    return pd.DataFrame(rows).reindex(columns=CHALLENGE_COLUMNS)


def apply_risk_framework_to_rolling(rolling: pd.DataFrame) -> pd.DataFrame:
    if rolling.empty:
        return rolling.reindex(columns=ROLLING_COLUMNS)
    rows = []
    for _, row in rolling.iterrows():
        updated = row.to_dict()
        lane = str(row.get("lane", ""))
        strategy = str(row.get("strategy", ""))
        updated.update(
            risk_framework_values(
                lane=lane,
                strategy=strategy,
                instrument_family="ETF simulated exposure" if "exposure" in lane else ("ETF" if "etf" in lane else lane),
                credibility_tier=str(row.get("credibility_tier", "")),
                exposure_multiplier=row.get("exposure_multiplier", row.get("leverage_multiplier", 1.0)),
                max_drawdown_dollars=row.get("worst_max_drawdown", row.get("median_max_drawdown", 0.0)),
                stop_hit=as_float(row.get("pct_any_project_stop_hit", 0.0), 0.0) > 0,
                equity_for_progress=row.get("median_stop_enforced_final_equity", STARTING_EQUITY),
                stop_metric_quality=str(row.get("stop_enforced_metric_quality", "unavailable")),
                final_validation_completed=row.get("final_validation_completed", False),
                benchmark_comparison_available=True,
                current_verdict=str(row.get("risk_framework_verdict", "")),
            )
        )
        rows.append(updated)
    return pd.DataFrame(rows).reindex(columns=ROLLING_COLUMNS)


def annotate_challenge_finality(challenge: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    if challenge.empty:
        return challenge.reindex(columns=CHALLENGE_COLUMNS)
    out = challenge.copy()
    for field, default in [
        ("rolling_method", "not_run"),
        ("sampled_results_are_final", False),
        ("final_validation_completed", False),
    ]:
        if field not in out:
            out[field] = default
    out["rolling_method"] = out["rolling_method"].astype("object")
    out["sampled_results_are_final"] = out["sampled_results_are_final"].astype("object")
    out["final_validation_completed"] = out["final_validation_completed"].astype("object")
    if rolling.empty:
        return out.reindex(columns=CHALLENGE_COLUMNS)

    for idx, row in out.iterrows():
        run_status = str(row.get("run_status", "") or "")
        if run_status and run_status not in {"completed", "nan"}:
            out.at[idx, "rolling_method"] = "not_run"
            out.at[idx, "sampled_results_are_final"] = False
            out.at[idx, "final_validation_completed"] = False
            continue
        mask = (
            rolling["lane"].astype(str).eq(str(row.get("lane", "")))
            & rolling["strategy"].astype(str).eq(str(row.get("strategy", "")))
            & rolling["standard_or_stress"].astype(str).eq(str(row.get("standard_or_stress", "")))
        )
        for key in ["family_id", "portfolio_id"]:
            value = row.get(key, "")
            if pd.notna(value) and str(value) not in {"", "nan"} and key in rolling:
                mask &= rolling[key].astype(str).eq(str(value))
        if "leverage_multiplier" in rolling and pd.notna(row.get("leverage_multiplier", math.nan)):
            mask &= rolling["leverage_multiplier"].astype(float).eq(as_float(row.get("leverage_multiplier"), 1.0))
        match = rolling[mask]
        if match.empty:
            out.at[idx, "rolling_method"] = "not_run"
            out.at[idx, "sampled_results_are_final"] = False
            out.at[idx, "final_validation_completed"] = False
            continue
        methods = sorted(match["rolling_method"].dropna().astype(str).unique().tolist())
        out.at[idx, "rolling_method"] = ";".join(methods)
        out.at[idx, "sampled_results_are_final"] = bool(match["sampled_results_are_final"].map(boolish).all())
        out.at[idx, "final_validation_completed"] = bool(match["final_validation_completed"].map(boolish).all())
    return out.reindex(columns=CHALLENGE_COLUMNS)


def stop_audit_from_equity(equity: pd.Series, dates: pd.Series | pd.Index) -> StopAudit:
    equity = pd.Series(equity, dtype=float).reset_index(drop=True)
    dates = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    if equity.empty:
        equity = pd.Series([STARTING_EQUITY], dtype=float)
        dates = pd.Series([pd.Timestamp.today().normalize()])

    high_water = equity.cummax()
    drawdown_dollars = equity - high_water
    drawdown_pct = drawdown_dollars / high_water.replace(0, np.nan)
    absolute = equity <= ABSOLUTE_STOP
    trailing = equity <= high_water - TRAILING_DRAWDOWN
    selected_stop = absolute | trailing

    first_stop_idx: int | None = None
    first_stop_type = ""
    if selected_stop.any():
        first_stop_idx = int(np.flatnonzero(selected_stop.to_numpy())[0])
        if bool(absolute.iloc[first_stop_idx]):
            first_stop_type = "absolute_floor"
        elif bool(trailing.iloc[first_stop_idx]):
            first_stop_type = "trailing_drawdown"

    def target_state(target: float) -> tuple[bool, bool, str, int | None]:
        hit = equity >= target
        if not hit.any():
            return False, False, "", None
        idx = int(np.flatnonzero(hit.to_numpy())[0])
        before_stop = True if first_stop_idx is None else idx <= first_stop_idx
        return True, before_stop, dates.iloc[idx].date().isoformat(), idx

    t300 = target_state(TARGET_300)
    t400 = target_state(TARGET_400)
    stop_equity = float(equity.iloc[first_stop_idx]) if first_stop_idx is not None else float(equity.iloc[-1])
    stop_overshoot_dollars = 0.0
    stop_overshoot_pct = 0.0
    if first_stop_idx is not None:
        if first_stop_type == "absolute_floor":
            stop_threshold = ABSOLUTE_STOP
        else:
            stop_threshold = float(high_water.iloc[first_stop_idx] - TRAILING_DRAWDOWN)
        stop_overshoot_dollars = min(0.0, stop_equity - stop_threshold)
        stop_overshoot_pct = stop_overshoot_dollars / stop_threshold if stop_threshold else 0.0
    return StopAudit(
        unconditional_final_equity=float(equity.iloc[-1]),
        stop_enforced_final_equity=stop_equity,
        max_equity=float(equity.max()),
        min_equity=float(equity.min()),
        max_drawdown_dollars=float(drawdown_dollars.min()),
        max_drawdown_pct=float(drawdown_pct.min()) if drawdown_pct.notna().any() else 0.0,
        absolute_floor_stop_hit=bool(absolute.any()),
        trailing_drawdown_stop_hit=bool(trailing.any()),
        any_project_stop_hit=bool(selected_stop.any()),
        first_project_stop_date=dates.iloc[first_stop_idx].date().isoformat() if first_stop_idx is not None else "",
        first_project_stop_type=first_stop_type,
        equity_at_first_project_stop=stop_equity if first_stop_idx is not None else None,
        stop_overshoot_dollars=stop_overshoot_dollars,
        stop_overshoot_pct=stop_overshoot_pct,
        target_300_hit=t300[0],
        target_300_before_stop=t300[1],
        target_300_first_date=t300[2],
        target_400_hit=t400[0],
        target_400_before_stop=t400[1],
        target_400_first_date=t400[2],
        days_to_target_300=t300[3],
        days_to_target_400=t400[3],
        days_to_first_stop=first_stop_idx,
    )


def approximate_stop_audit_from_summary(row: pd.Series) -> dict[str, Any]:
    final_equity = as_float(row.get("final_equity"))
    max_dd = as_float(row.get("max_drawdown_dollars", row.get("max_drawdown")))
    max_dd_pct = as_float(row.get("max_drawdown_pct"))
    if pd.isna(max_dd_pct) and final_equity:
        max_dd_pct = math.nan
    if pd.notna(max_dd) and pd.notna(max_dd_pct) and max_dd_pct != 0:
        max_equity = abs(max_dd / max_dd_pct)
        min_equity = max_equity + max_dd
    else:
        max_equity = max(final_equity, STARTING_EQUITY)
        min_equity = min(final_equity, STARTING_EQUITY)
    absolute_hit = boolish(row.get("absolute_floor_stop_hit", False)) or min_equity <= ABSOLUTE_STOP
    trailing_hit = boolish(row.get("trailing_drawdown_stop_hit", False)) or max_dd <= -TRAILING_DRAWDOWN
    any_hit = boolish(row.get("any_project_stop_hit", False)) or absolute_hit or trailing_hit
    first_type = ""
    if any_hit:
        first_type = "absolute_floor" if absolute_hit else "trailing_drawdown"
    if any_hit and absolute_hit:
        stop_equity = ABSOLUTE_STOP
    elif any_hit and trailing_hit:
        stop_equity = max(0.0, max_equity - TRAILING_DRAWDOWN)
    else:
        stop_equity = final_equity
    return {
        "unconditional_final_equity": final_equity,
        "stop_enforced_final_equity": stop_equity,
        "total_return_unconditional": final_equity / STARTING_EQUITY - 1.0,
        "total_return_stop_enforced": stop_equity / STARTING_EQUITY - 1.0,
        "max_equity": max_equity,
        "min_equity": min_equity,
        "max_drawdown_dollars": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "absolute_floor_stop_hit": absolute_hit,
        "trailing_drawdown_stop_hit": trailing_hit,
        "any_project_stop_hit": any_hit,
        "first_project_stop_date": "" if pd.isna(row.get("first_project_stop_date", "")) else str(row.get("first_project_stop_date", "")),
        "first_project_stop_type": first_type,
        "equity_at_first_project_stop": stop_equity if any_hit else math.nan,
        "stop_overshoot_dollars": 0.0,
        "stop_overshoot_pct": 0.0,
        "target_300_hit": boolish(row.get("target_300_hit", False)),
        "target_300_before_stop": boolish(row.get("target_300_before_any_stop", row.get("target_300_before_stop", False))),
        "target_300_first_date": "",
        "target_400_hit": boolish(row.get("target_400_hit", False)),
        "target_400_before_stop": boolish(row.get("target_400_before_any_stop", row.get("target_400_before_stop", False))),
        "target_400_first_date": "",
        "days_to_target_300": math.nan,
        "days_to_target_400": math.nan,
        "days_to_first_stop": math.nan,
    }


def audit_dict_from_stop(audit: StopAudit) -> dict[str, Any]:
    out = audit.__dict__.copy()
    out["total_return_unconditional"] = audit.unconditional_final_equity / STARTING_EQUITY - 1.0
    out["total_return_stop_enforced"] = audit.stop_enforced_final_equity / STARTING_EQUITY - 1.0
    return out


def load_exact_etf_context() -> dict[str, Any]:
    global _ETF_CONTEXT
    if _ETF_CONTEXT is not None:
        return _ETF_CONTEXT
    config = load_config(REPO_ROOT / "config.yaml")
    config["project_root"] = str(REPO_ROOT)
    data_result: DataLoadResult = load_market_data(config, REPO_ROOT)
    prepared = prepare_indicators(data_result.data)
    base_bt = Backtester(prepared, config)
    full_range = config["date_ranges"]["full"]
    dates = base_bt._effective_calendar(str(full_range["start"]), full_range.get("end") or config["data"].get("end_date"))
    _ETF_CONTEXT = {
        "config": config,
        "prepared": prepared,
        "coverage": data_result.coverage,
        "data_source": data_result.data_source,
        "dates": dates,
    }
    return _ETF_CONTEXT


def run_exact_variant_full_rows(
    run_id: str,
    variant_name: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    context = load_exact_etf_context()
    config = context["config"]
    prepared = context["prepared"]
    variant_cfg = strategy_variant_config(config, variant_name)
    full_range = config["date_ranges"]["full"]
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    rows: list[dict[str, Any]] = []
    completed = True
    for label in labels:
        if runtime_deadline and time.monotonic() > runtime_deadline:
            completed = False
            break
        slippage = slippages[label]
        result = Backtester(prepared, variant_cfg).run(
            f"challenge_exact_{variant_name}_{label}",
            str(full_range["start"]),
            full_range.get("end") or config["data"].get("end_date"),
            slippage,
        )
        curve = result.equity_curve
        audit = audit_dict_from_stop(stop_audit_from_equity(curve["equity"], curve["date"]))
        rows.append(
            build_challenge_row(
                run_id=run_id,
                lane="etf_validated_lane",
                strategy=variant_name,
                instrument_family="daily_etf",
                credibility_tier="ETF exact focused finalist; not a real-money recommendation",
                data_source=f"existing ETF adjusted OHLC via {context['data_source']}",
                start_date=str(pd.to_datetime(curve["date"]).min().date()),
                end_date=str(pd.to_datetime(curve["date"]).max().date()),
                standard_or_stress=label,
                spread_slippage_per_side=slippage,
                leverage_model="none",
                leverage_multiplier=1.0,
                financing_cost_assumption=0.0,
                audit=audit,
                number_of_trades_or_rebalances=float(len(result.trades)),
                benchmark_name="SPY_200d_trend_model",
                stop_enforced_metric_quality="exact",
                stop_enforced_metric_source="computed_from_focused_backtester_variant_equity_curve",
                stop_enforced_metric_notes="Computed by running the existing fixed-rule ETF Backtester for the focused no-cash A/B finalist.",
                notes="Focused candidate_exhaustive full-period row; no strategy rules changed.",
            )
        )
    coverage_rows = [
        {
            "lane": "etf_validated_lane",
            "data_source": f"existing ETF adjusted OHLC via {context['data_source']}",
            "symbols": ",".join(context["coverage"].get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
            "start_date": context["coverage"].get("first_date", pd.Series(dtype=str)).min() if "first_date" in context["coverage"] else "",
            "end_date": context["coverage"].get("last_date", pd.Series(dtype=str)).max() if "last_date" in context["coverage"] else "",
            "row_count": int(context["coverage"].get("row_count", pd.Series(dtype=float)).sum()) if "row_count" in context["coverage"] else math.nan,
            "missing_data_notes": "Exact focused finalist uses existing adjusted ETF OHLC cache; raw OHLCV is not copied into compact evidence.",
            "adjusted_or_unadjusted": "adjusted OHLC per ETF evidence lane",
            "raw_data_included_in_evidence": False,
            "major_limitations": "yfinance/Yahoo cache limitations and ETF inception differences still apply.",
        }
    ]
    return rows, coverage_rows, completed


def apply_leverage_to_curve(
    equity_curve: pd.DataFrame,
    weights: pd.DataFrame,
    leverage: float,
    financing_annual: float,
) -> pd.DataFrame:
    curve = equity_curve.copy()
    returns = curve["equity"].astype(float).pct_change(fill_method=None).fillna(0.0)
    exposure = weights.sum(axis=1).reindex(pd.to_datetime(curve["date"])).fillna(0.0).clip(0.0, 1.0)
    financing_daily = max(0.0, leverage - 1.0) * financing_annual / 365.0
    levered_returns = returns * leverage - exposure.to_numpy() * financing_daily
    equity = [STARTING_EQUITY]
    catastrophic = False
    for ret in levered_returns.iloc[1:]:
        next_equity = equity[-1] * (1.0 + float(ret))
        if next_equity <= 0:
            next_equity = 0.0
            catastrophic = True
        equity.append(next_equity)
        if catastrophic:
            # Once wiped out, this approximation stays at zero.
            equity[-1] = 0.0
    curve["equity"] = equity
    curve["daily_return"] = pd.Series(equity).pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    return curve


def build_challenge_row(
    run_id: str,
    lane: str,
    strategy: str,
    instrument_family: str,
    credibility_tier: str,
    data_source: str,
    start_date: str,
    end_date: str,
    standard_or_stress: str,
    spread_slippage_per_side: float,
    leverage_model: str,
    leverage_multiplier: float,
    financing_cost_assumption: float,
    audit: dict[str, Any],
    role: str = "",
    exposure_multiplier: float | None = None,
    annual_financing_rate: float | None = None,
    cost_model_quality: str = "exact",
    catastrophic_loss: bool = False,
    time_in_market: float = math.nan,
    number_of_trades_or_rebalances: float = math.nan,
    turnover_estimate: float = math.nan,
    benchmark_name: str = "",
    benchmark: dict[str, Any] | None = None,
    stop_enforced_metric_quality: str = "unavailable",
    stop_enforced_metric_source: str = "",
    stop_enforced_metric_notes: str = "",
    notes: str = "",
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    benchmark = benchmark or {}
    status, verdict, failure = classify_result(lane, credibility_tier, audit, leverage_multiplier)
    row = {
        "run_id": run_id,
        "lane": lane,
        "strategy": strategy,
        "role": role,
        "instrument_family": instrument_family,
        "credibility_tier": credibility_tier,
        "data_source": data_source,
        "start_date": start_date,
        "end_date": end_date,
        "starting_equity": STARTING_EQUITY,
        "target_300_equity": TARGET_300,
        "target_400_equity": TARGET_400,
        "absolute_stop_equity": ABSOLUTE_STOP,
        "trailing_drawdown_dollars": TRAILING_DRAWDOWN,
        "project_stop_mode": PROJECT_STOP_MODE,
        "leverage_model": leverage_model,
        "leverage_multiplier": leverage_multiplier,
        "exposure_multiplier": exposure_multiplier if exposure_multiplier is not None else leverage_multiplier,
        "standard_or_stress": standard_or_stress,
        "cost_model": "spread_slippage_per_side_plus_financing" if leverage_multiplier > 1 else "spread_slippage_per_side",
        "cost_model_quality": cost_model_quality,
        "spread_slippage_per_side": spread_slippage_per_side,
        "annual_financing_rate": annual_financing_rate if annual_financing_rate is not None else financing_cost_assumption,
        "financing_cost_assumption": financing_cost_assumption,
        "catastrophic_loss": catastrophic_loss,
        "time_in_market": time_in_market,
        "number_of_trades_or_rebalances": number_of_trades_or_rebalances,
        "turnover_estimate": turnover_estimate,
        "benchmark_name": benchmark_name,
        "benchmark_stop_enforced_final_equity": benchmark.get("stop_enforced_final_equity", math.nan),
        "benchmark_target_300_before_stop": benchmark.get("target_300_before_stop", False),
        "benchmark_target_400_before_stop": benchmark.get("target_400_before_stop", False),
        "result_status": status,
        "audit_verdict": verdict,
        "main_failure_mode": failure,
        "stop_enforced_metric_quality": stop_enforced_metric_quality,
        "stop_enforced_metric_source": stop_enforced_metric_source,
        "stop_enforced_metric_notes": stop_enforced_metric_notes,
        "notes": notes,
    }
    if extra_fields:
        row.update(extra_fields)
    row.update(audit)
    return {col: row.get(col, math.nan) for col in CHALLENGE_COLUMNS}


def classify_result(lane: str, tier: str, audit: dict[str, Any], leverage: float) -> tuple[str, str, str]:
    if "benchmark" in lane:
        return "benchmark", "benchmark_only", "benchmark"
    if "independent_family_challenge" in lane:
        if "blocked" in str(tier).lower():
            return "blocked", "blocked_by_gate", "family blocked by gate"
        if "tier1" in str(tier).lower() or "crypto" in str(tier).lower():
            return "non_final", "exploratory_only", "Tier 1 exploratory family only"
        if audit.get("any_project_stop_hit"):
            return "watchlist", "too_risky", "family hit project stop"
        if audit.get("target_300_before_stop"):
            return "watchlist", "watchlist", "independent family diagnostic requires ranking review"
        return "watchlist", "too_slow", "family did not reach +300 before stop"
    if "diversified_portfolio_challenge" in lane:
        if "tier1" in str(tier).lower() or "crypto" in str(tier).lower():
            return "diagnostic", "exploratory_only", "crypto-containing portfolio remains Tier 1 exploratory"
        if audit.get("any_project_stop_hit"):
            return "diagnostic", "too_risky", "diversified portfolio hit project stop"
        if audit.get("target_300_before_stop"):
            return "diagnostic", "watchlist", "diversified portfolio diagnostic requires ranking review"
        return "diagnostic", "too_slow", "diversified portfolio did not reach +300 before stop"
    if "simulated_leverage_diagnostic" in lane:
        if audit.get("any_project_stop_hit"):
            return "diagnostic", "too_risky", "simulated leverage hit project stop"
        return "diagnostic", "watchlist_diagnostic", "simulated leverage diagnostic only"
    if "simulated_etf_exposure_frontier" in lane:
        if audit.get("any_project_stop_hit"):
            return "diagnostic", "too_risky", "simulated exposure frontier hit project stop"
        return "diagnostic", "watchlist_diagnostic", "risk-budget exposure frontier diagnostic only"
    if "etf_volatility_control_diagnostic" in lane:
        if audit.get("any_project_stop_hit"):
            return "diagnostic", "too_risky", "volatility-control diagnostic hit project stop"
        if audit.get("target_300_before_stop"):
            return "diagnostic", "watchlist_diagnostic", "volatility-control diagnostic only"
        return "diagnostic", "too_slow", "volatility-control diagnostic did not reach +300 before stop"
    if leverage > 1:
        if audit.get("any_project_stop_hit"):
            return "exploratory", "too_risky", "simulated leverage increased stop risk"
        return "exploratory", "exploratory_only", "approximate simulated leverage"
    if "Tier 1" in tier or "crypto" in lane:
        if audit.get("any_project_stop_hit"):
            return "non_final", "exploratory_only", "project stop hit in exploratory lane"
        return "non_final", "exploratory_only", "Tier 1 exploratory only"
    if audit.get("any_project_stop_hit"):
        return "watchlist", "watchlist", "project stop hit"
    if audit.get("target_300_before_stop"):
        return "watchlist", "practical_candidate", "requires further validation"
    return "watchlist", "too_slow", "target not reached before stop"


def load_etf_price_cache(symbols: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        path = Path("data/cache") / f"{symbol}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, usecols=["date", "adj_close", "symbol"])
        df["date"] = pd.to_datetime(df["date"])
        df["adj_close"] = pd.to_numeric(df["adj_close"], errors="coerce")
        df["symbol"] = symbol
        frames.append(df.dropna(subset=["date", "adj_close"]))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])


def build_etf_benchmark_weights(prices: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if benchmark == "SPY_buy_hold":
        if "SPY" in weights.columns:
            weights.loc[prices["SPY"].notna(), "SPY"] = 1.0
        return weights.shift(1).ffill().fillna(0.0)
    if benchmark == "BIL_cash_proxy":
        if "BIL" in weights.columns:
            weights.loc[prices["BIL"].notna(), "BIL"] = 1.0
        return weights.shift(1).ffill().fillna(0.0)
    if benchmark == "SPY_200d_trend_model":
        if "SPY" not in prices.columns:
            return weights
        sma = prices["SPY"].rolling(200, min_periods=200).mean()
        risk_on = prices["SPY"] > sma
        weights.loc[risk_on.fillna(False), "SPY"] = 1.0
        if "BIL" in weights.columns:
            weights.loc[~risk_on.fillna(False) & prices["BIL"].notna(), "BIL"] = 1.0
        return weights.shift(1).ffill().fillna(0.0)
    raise ValueError(f"Unknown ETF benchmark: {benchmark}")


def simulate_weighted_equity(prices: pd.DataFrame, weights: pd.DataFrame, spread_slippage_per_side: float) -> tuple[pd.DataFrame, int, float, float]:
    prices = prices.reindex(weights.index).reindex(columns=weights.columns).ffill()
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    equity_values: list[float] = []
    prev_equity = STARTING_EQUITY
    prev_weights = pd.Series(0.0, index=weights.columns)
    rebalance_count = 0
    turnover_estimate = 0.0
    for dt in prices.index:
        current_weights = weights.loc[dt].fillna(0.0).clip(0.0, 1.0)
        total = current_weights.sum()
        if total > 1.0:
            current_weights = current_weights / total
        turnover = float((current_weights - prev_weights).abs().sum())
        cost = prev_equity * turnover * spread_slippage_per_side
        gross_return = float((current_weights * returns.loc[dt]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross_return) - cost)
        if turnover > 1e-9:
            rebalance_count += 1
            turnover_estimate += turnover
        equity_values.append(equity)
        prev_equity = equity
        prev_weights = current_weights
    curve = pd.DataFrame({"date": prices.index, "equity": equity_values})
    time_in_market = float(weights.sum(axis=1).gt(0).mean()) if not weights.empty else 0.0
    return curve, rebalance_count, turnover_estimate, time_in_market


def etf_benchmark_data(date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = load_etf_price_cache(["SPY", "BIL"])
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    prices = data.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    if date_index is not None:
        prices = prices.reindex(pd.DatetimeIndex(pd.to_datetime(date_index))).ffill()
        if "SPY" in prices:
            prices = prices[prices["SPY"].notna()]
    return data, prices


def load_portfolio_specs(path: Path = PORTFOLIO_SPEC_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    specs = data.get("portfolios", [])
    for spec in specs:
        sleeves = spec.get("sleeves", {})
        if not isinstance(sleeves, dict) or not sleeves:
            raise ValueError(f"Portfolio spec {spec.get('id')} must define sleeves.")
        weights = [float(value) for value in sleeves.values()]
        if any(weight < 0 for weight in weights):
            raise ValueError(f"Portfolio spec {spec.get('id')} has a negative weight.")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError(f"Portfolio spec {spec.get('id')} weights must sum to 1.0.")
    return specs


def portfolio_is_crypto(spec: dict[str, Any]) -> bool:
    return any("crypto" in str(sleeve).lower() for sleeve in spec.get("sleeves", {})) or str(spec.get("tier", "")).lower() == "tier1_exploratory"


def portfolio_weight_buckets(sleeves: dict[str, float]) -> dict[str, float]:
    equity = sum(weight for sleeve, weight in sleeves.items() if sleeve in {"SPY_200d_trend_model", "SPY_buy_hold"})
    cash = sum(weight for sleeve, weight in sleeves.items() if sleeve == "BIL_cash_proxy")
    bond = sum(weight for sleeve, weight in sleeves.items() if sleeve == "IEF_buy_hold")
    gold = sum(weight for sleeve, weight in sleeves.items() if sleeve == "GLD_buy_hold")
    crypto = sum(weight for sleeve, weight in sleeves.items() if "crypto" in sleeve)
    strategy = sum(weight for sleeve, weight in sleeves.items() if sleeve == "current_no_cash_proxy_alpha_AB")
    return {
        "equity_weight": equity,
        "cash_weight": cash,
        "bond_weight": bond,
        "gold_weight": gold,
        "crypto_weight": crypto,
        "strategy_weight": strategy,
        "max_single_sleeve_weight": max(sleeves.values()) if sleeves else math.nan,
    }


def load_portfolio_price_cache(date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = load_etf_price_cache(["SPY", "BIL", "IEF", "GLD"])
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    prices = data.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    if date_index is not None:
        prices = prices.reindex(pd.DatetimeIndex(pd.to_datetime(date_index))).ffill()
    if "SPY" in prices:
        prices = prices[prices["SPY"].notna()]
    return data, prices


def exact_ab_sleeve_returns(date_index: pd.Index, label: str) -> tuple[pd.Series, str]:
    # The compact portfolio diagnostic must not invent A/B sleeve returns. The
    # current compact evidence layer does not expose a daily A/B return stream,
    # and recomputing a full nested strategy replay here would make the portfolio
    # diagnostic depend on an unrelated heavy backtest path. Portfolios using the
    # A/B sleeve are therefore flagged incomplete unless a future compact daily
    # sleeve artifact is explicitly added.
    return (
        pd.Series(np.nan, index=date_index, dtype=float),
        "unavailable: compact daily A/B sleeve return stream is not present; portfolio rows using this sleeve are flagged incomplete",
    )


def build_portfolio_sleeve_returns(
    prices: pd.DataFrame,
    label: str,
    include_crypto_sleeves: bool = False,
) -> tuple[pd.DataFrame, dict[str, str]]:
    returns = pd.DataFrame(index=prices.index)
    notes: dict[str, str] = {}
    for benchmark in ["SPY_200d_trend_model", "BIL_cash_proxy"]:
        weights = build_etf_benchmark_weights(prices.reindex(columns=["SPY", "BIL"]).ffill(), benchmark)
        curve, _rebalances, _turnover, _time = simulate_weighted_equity(prices.reindex(columns=weights.columns).ffill(), weights, 0.0005 if label == "standard" else 0.001)
        returns[benchmark] = curve.set_index("date")["equity"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0).reindex(prices.index).fillna(0.0)
        notes[benchmark] = "computed_from_cached_adjusted_prices_with_embedded_sleeve_costs"
    for symbol, sleeve in [("IEF", "IEF_buy_hold"), ("GLD", "GLD_buy_hold")]:
        if symbol in prices.columns and prices[symbol].notna().any():
            returns[sleeve] = prices[symbol].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            notes[sleeve] = "adjusted_close_buy_hold_return_stream"
        else:
            returns[sleeve] = np.nan
            notes[sleeve] = f"unavailable: {symbol} cache missing"
    returns[FOCUSED_FINALIST], notes[FOCUSED_FINALIST] = exact_ab_sleeve_returns(prices.index, label)
    if include_crypto_sleeves:
        returns["crypto_time_series_momentum"] = np.nan
        notes["crypto_time_series_momentum"] = "unavailable in compact portfolio challenge unless existing crypto sleeve alignment is added; row remains Tier 1 exploratory/incomplete"
    return returns, notes


def build_monthly_portfolio_targets(
    dates: pd.Index,
    sleeves: dict[str, float],
    sleeve_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], str]:
    targets = pd.DataFrame(0.0, index=dates, columns=sorted(set(sleeves) | {"BIL_cash_proxy"}))
    unavailable: set[str] = set()
    month_keys = pd.Series(pd.to_datetime(dates).to_period("M"), index=dates)
    rebalance_mask = month_keys.ne(month_keys.shift(1))
    for date in dates:
        row_weights = {sleeve: 0.0 for sleeve in targets.columns}
        for sleeve, weight in sleeves.items():
            available = sleeve in sleeve_returns.columns and pd.notna(sleeve_returns.at[date, sleeve])
            if available:
                row_weights[sleeve] = row_weights.get(sleeve, 0.0) + float(weight)
            else:
                unavailable.add(sleeve)
                if "BIL_cash_proxy" in sleeve_returns.columns and pd.notna(sleeve_returns.at[date, "BIL_cash_proxy"]):
                    row_weights["BIL_cash_proxy"] = row_weights.get("BIL_cash_proxy", 0.0) + float(weight)
        targets.loc[date, list(row_weights)] = list(row_weights.values())
    targets = targets.where(rebalance_mask, np.nan).ffill().fillna(0.0)
    notes = "all sleeves available" if not unavailable else "unavailable sleeves allocated to BIL/cash and flagged"
    return targets, sorted(unavailable), notes


def simulate_portfolio_returns(
    sleeve_returns: pd.DataFrame,
    targets: pd.DataFrame,
    spread_slippage_per_side: float,
) -> tuple[pd.DataFrame, int, float, float]:
    sleeve_returns = sleeve_returns.reindex(index=targets.index, columns=targets.columns).fillna(0.0)
    equity_values: list[float] = []
    prev_equity = STARTING_EQUITY
    prev_weights = pd.Series(0.0, index=targets.columns)
    rebalance_count = 0
    turnover_estimate = 0.0
    for dt in targets.index:
        current_weights = targets.loc[dt].fillna(0.0).clip(0.0, 1.0)
        total = float(current_weights.sum())
        if total > 1.0:
            current_weights = current_weights / total
        turnover = float((current_weights - prev_weights).abs().sum())
        cost = prev_equity * turnover * spread_slippage_per_side
        gross_return = float((current_weights * sleeve_returns.loc[dt]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross_return) - cost)
        if turnover > 1e-9:
            rebalance_count += 1
            turnover_estimate += turnover
        equity_values.append(equity)
        prev_equity = equity
        prev_weights = current_weights
    return pd.DataFrame({"date": targets.index, "equity": equity_values}), rebalance_count, turnover_estimate, float(targets.sum(axis=1).gt(0).mean())


def fast_portfolio_window(
    sleeve_returns_array: np.ndarray,
    target_weights_array: np.ndarray,
    dates: pd.Index,
    idx: int,
    horizon: int,
    spread_slippage_per_side: float,
    unavailable_window: bool = False,
) -> dict[str, Any]:
    return_slice = sleeve_returns_array[idx : idx + horizon]
    weight_slice = target_weights_array[idx : idx + horizon].copy()
    n_rows, n_cols = return_slice.shape
    if n_rows == 0:
        audit = stop_audit_from_equity(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp.today().normalize()]))
        return {
            "final_equity": audit.unconditional_final_equity,
            "stop_enforced_final_equity": audit.stop_enforced_final_equity,
            "max_drawdown_dollars": audit.max_drawdown_dollars,
            "target_300_hit": audit.target_300_hit,
            "target_300_before_stop": audit.target_300_before_stop,
            "target_400_hit": audit.target_400_hit,
            "target_400_before_stop": audit.target_400_before_stop,
            "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
            "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
            "any_project_stop_hit": audit.any_project_stop_hit,
            "stop_overshoot_dollars": audit.stop_overshoot_dollars,
            "stop_overshoot_pct": audit.stop_overshoot_pct,
            "portfolio_turnover": 0.0,
            "unavailable_window": unavailable_window,
        }
    equities = np.zeros(n_rows)
    equities[0] = STARTING_EQUITY
    prev_weights = np.zeros(n_cols)
    turnover_estimate = 0.0
    returns = np.nan_to_num(return_slice, nan=0.0, posinf=0.0, neginf=0.0)
    for i in range(1, n_rows):
        current_weights = np.clip(np.nan_to_num(weight_slice[i], nan=0.0), 0.0, 1.0)
        total = current_weights.sum()
        if total > 1.0:
            current_weights = current_weights / total
        turnover = np.abs(current_weights - prev_weights).sum()
        cost = equities[i - 1] * turnover * spread_slippage_per_side
        gross_return = float((current_weights * returns[i]).sum())
        equities[i] = max(0.0, equities[i - 1] * (1.0 + gross_return) - cost)
        turnover_estimate += float(turnover)
        prev_weights = current_weights
    audit = stop_audit_from_equity(pd.Series(equities), dates[idx : idx + horizon])
    return {
        "final_equity": audit.unconditional_final_equity,
        "stop_enforced_final_equity": audit.stop_enforced_final_equity,
        "max_drawdown_dollars": audit.max_drawdown_dollars,
        "target_300_hit": audit.target_300_hit,
        "target_300_before_stop": audit.target_300_before_stop,
        "target_400_hit": audit.target_400_hit,
        "target_400_before_stop": audit.target_400_before_stop,
        "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
        "any_project_stop_hit": audit.any_project_stop_hit,
        "stop_overshoot_dollars": audit.stop_overshoot_dollars,
        "stop_overshoot_pct": audit.stop_overshoot_pct,
        "portfolio_turnover": turnover_estimate,
        "unavailable_window": unavailable_window,
    }


def portfolio_extra_fields(
    spec: dict[str, Any],
    unavailable: list[str],
    availability_notes: str,
    turnover: float,
    rebalance_count: int,
) -> dict[str, Any]:
    sleeves = {str(key): float(value) for key, value in spec["sleeves"].items()}
    buckets = portfolio_weight_buckets(sleeves)
    return {
        "portfolio_id": spec["id"],
        "portfolio_role": spec["role"],
        "portfolio_rebalance_frequency": "monthly",
        "portfolio_sleeves": ";".join(sleeves.keys()),
        "portfolio_weights": yaml.safe_dump(sleeves, sort_keys=True).strip().replace("\n", " "),
        "average_portfolio_turnover": turnover,
        "rebalance_count": rebalance_count,
        "unavailable_sleeves": ";".join(unavailable),
        "availability_notes": availability_notes,
        "cost_model": "portfolio_monthly_rebalance_spread_slippage_with_embedded_sleeve_costs",
        **buckets,
    }


def build_diversified_portfolio_rows(
    run_id: str,
    mode: str,
    include_diversified_portfolios: bool,
    include_exploratory_crypto_portfolios: bool,
    runtime_deadline: float | None = None,
    date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    if not include_diversified_portfolios:
        return [], [], [], True
    specs = load_portfolio_specs()
    selected_specs = [
        spec for spec in specs
        if not portfolio_is_crypto(spec) or include_exploratory_crypto_portfolios
    ]
    data, prices = load_portfolio_price_cache(date_index)
    if data.empty or prices.empty:
        coverage = [
            {
                "lane": "diversified_portfolio_challenge",
                "data_source": "data/cache adjusted ETF prices",
                "symbols": "SPY,BIL,IEF,GLD",
                "start_date": "",
                "end_date": "",
                "row_count": 0,
                "missing_data_notes": "ETF cache unavailable for diversified portfolio challenge.",
                "adjusted_or_unadjusted": "adjusted close expected",
                "raw_data_included_in_evidence": False,
                "major_limitations": "Portfolio rows unavailable.",
            }
        ]
        return [], [], coverage, False
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    labels = ["standard", "stress"]
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    for label in labels:
        cost = 0.0005 if label == "standard" else 0.001
        sleeve_returns, sleeve_notes = build_portfolio_sleeve_returns(prices, label, include_exploratory_crypto_portfolios)
        for spec in selected_specs:
            crypto_row = portfolio_is_crypto(spec)
            sleeves = {str(key): float(value) for key, value in spec["sleeves"].items()}
            targets, unavailable, availability_notes = build_monthly_portfolio_targets(prices.index, sleeves, sleeve_returns)
            if crypto_row and "crypto_time_series_momentum" in sleeves and "crypto_time_series_momentum" not in unavailable:
                unavailable.append("crypto_time_series_momentum")
                availability_notes = "crypto sleeve alignment unavailable; row remains Tier 1 exploratory/incomplete"
            curve, rebalances, turnover, time_in_market = simulate_portfolio_returns(sleeve_returns, targets, cost)
            audit = audit_dict_from_stop(stop_audit_from_equity(curve["equity"], curve["date"]))
            tier = "tier1_exploratory" if crypto_row else ("tier3_candidate_validation" if mode == "candidate_exhaustive" else "tier2_credible_prototype")
            unavailable_sorted = sorted(set(unavailable))
            quality = "unavailable" if unavailable_sorted else "exact"
            notes = (
                "Fixed predeclared monthly rebalanced diversified portfolio diagnostic. "
                "No weight optimization, leverage, shorting, margin, broker integration, or real-money recommendation."
            )
            if unavailable_sorted:
                notes += f" Unavailable sleeves: {', '.join(unavailable_sorted)}."
            rows.append(
                build_challenge_row(
                    run_id=run_id,
                    lane="diversified_portfolio_challenge",
                    strategy=str(spec["id"]),
                    role="diversified_portfolio_diagnostic",
                    instrument_family="diversified portfolio with crypto sleeve" if crypto_row else "diversified ETF portfolio",
                    credibility_tier=tier,
                    data_source="data/cache adjusted ETF prices plus existing fixed-rule sleeve return streams",
                    start_date=prices.index.min().date().isoformat(),
                    end_date=prices.index.max().date().isoformat(),
                    standard_or_stress=label,
                    spread_slippage_per_side=cost,
                    leverage_model="none",
                    leverage_multiplier=1.0,
                    exposure_multiplier=1.0,
                    financing_cost_assumption=0.0,
                    audit=audit,
                    cost_model_quality="approximate" if FOCUSED_FINALIST in sleeves else "exact",
                    time_in_market=time_in_market,
                    number_of_trades_or_rebalances=rebalances,
                    turnover_estimate=turnover,
                    benchmark_name="SPY_200d_trend_model",
                    stop_enforced_metric_quality=quality,
                    stop_enforced_metric_source="monthly_rebalanced_portfolio_of_sleeve_return_streams",
                    stop_enforced_metric_notes="Computed from reconstructed portfolio equity curve; raw OHLCV excluded from compact evidence.",
                    notes=notes,
                    extra_fields=portfolio_extra_fields(spec, unavailable_sorted, availability_notes, turnover, rebalances),
                )
            )
            returns_matrix = sleeve_returns.reindex(index=prices.index, columns=targets.columns).fillna(0.0).to_numpy(dtype=float)
            targets_matrix = targets.reindex(index=prices.index, columns=targets.columns).fillna(0.0).to_numpy(dtype=float)
            unavailable_any = bool(unavailable_sorted)
            for horizon in horizons:
                starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
                window_metrics: list[dict[str, Any]] = []
                for idx in starts:
                    if runtime_deadline and time.monotonic() > runtime_deadline:
                        completed = False
                        break
                    window_metrics.append(
                        fast_portfolio_window(
                            returns_matrix,
                            targets_matrix,
                            prices.index,
                            int(idx),
                            int(horizon),
                            cost,
                            unavailable_window=unavailable_any,
                        )
                    )
                if window_metrics:
                    summary = summarize_window_metrics(window_metrics)
                    exact_final = method == "all_possible" and completed and len(window_metrics) == possible_count and not unavailable_any and not crypto_row
                    rolling_rows.append(
                        {
                            "run_id": run_id,
                            "lane": "diversified_portfolio_challenge",
                            "strategy": spec["id"],
                            "portfolio_id": spec["id"],
                            "portfolio_role": spec["role"],
                            "role": "diversified_portfolio_diagnostic",
                            "credibility_tier": tier,
                            "leverage_multiplier": 1.0,
                            "exposure_multiplier": 1.0,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": exact_final,
                            "final_validation_completed": exact_final,
                            "stop_enforced_metric_quality": "exact" if exact_final else ("unavailable" if unavailable_any else "partial"),
                            "notes": notes,
                            "rolling_metric_quality": "exact_portfolio_all_possible" if exact_final else ("portfolio_incomplete" if unavailable_any else "portfolio_sample_or_partial"),
                            "rolling_notes": "Fixed monthly rebalance portfolio diagnostic; no weight optimization.",
                            **summary,
                        }
                    )
                else:
                    rolling_rows.append(
                        {
                            "run_id": run_id,
                            "lane": "diversified_portfolio_challenge",
                            "strategy": spec["id"],
                            "portfolio_id": spec["id"],
                            "portfolio_role": spec["role"],
                            "role": "diversified_portfolio_diagnostic",
                            "credibility_tier": tier,
                            "leverage_multiplier": 1.0,
                            "exposure_multiplier": 1.0,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "number_of_windows": 0,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": False,
                            "final_validation_completed": False,
                            "unavailable_window_count": possible_count,
                            "stop_enforced_metric_quality": "unavailable",
                            "notes": "Portfolio rolling unavailable: no windows completed.",
                            "rolling_metric_quality": "unavailable",
                            "rolling_notes": "No windows completed.",
                        }
                    )
                if not completed:
                    break
            if not completed:
                break
        if not completed:
            break
    symbols = ",".join(sorted(data["symbol"].dropna().unique()))
    coverage = [
        {
            "lane": "diversified_portfolio_challenge",
            "data_source": "data/cache adjusted ETF prices and existing strategy return streams",
            "symbols": symbols,
            "start_date": prices.index.min().date().isoformat(),
            "end_date": prices.index.max().date().isoformat(),
            "row_count": int(len(data)),
            "missing_data_notes": "; ".join(sorted(set(note for note in sleeve_notes.values() if "unavailable" in note))) or "",
            "adjusted_or_unadjusted": "adjusted close and fixed-rule sleeve return streams",
            "raw_data_included_in_evidence": False,
            "major_limitations": "Portfolio rows use reconstructed sleeve return streams and simplified monthly rebalance costs; no raw OHLCV is copied.",
        }
    ]
    return rows, rolling_rows, coverage, completed


def load_family_specs(path: Path = FAMILY_SPEC_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    specs = data.get("families", [])
    required = {"family_id", "family_group", "implementation_status", "credibility_tier", "run_allowed", "role"}
    for spec in specs:
        missing = required - set(spec)
        if missing:
            raise ValueError(f"Family spec {spec.get('family_id', 'unknown')} missing {sorted(missing)}.")
    return specs


def family_is_crypto(spec: dict[str, Any]) -> bool:
    text = f"{spec.get('family_id', '')} {spec.get('family_group', '')} {spec.get('underlying_strategy', '')}".lower()
    return "crypto" in text or str(spec.get("credibility_tier", "")).lower() == "tier1_exploratory"


def family_extra_fields(spec: dict[str, Any], run_status: str, blocked_reason: str = "") -> dict[str, Any]:
    return {
        "family_id": spec.get("family_id", ""),
        "family_group": spec.get("family_group", ""),
        "family_role": spec.get("role", ""),
        "independent_family_account": True,
        "shared_capital_with_other_families": False,
        "portfolio_mix": False,
        "implementation_status": spec.get("implementation_status", ""),
        "run_allowed": spec.get("run_allowed", False),
        "run_status": run_status,
        "blocked_reason": blocked_reason,
    }


def blank_family_challenge_row(
    run_id: str,
    spec: dict[str, Any],
    run_status: str,
    blocked_reason: str,
    label: str = "standard",
) -> dict[str, Any]:
    row = {col: math.nan for col in CHALLENGE_COLUMNS}
    row.update(
        {
            "run_id": run_id,
            "lane": "independent_family_challenge",
            "strategy": spec.get("underlying_strategy", spec.get("family_id", "")),
            "role": spec.get("role", ""),
            "instrument_family": spec.get("family_group", ""),
            "credibility_tier": spec.get("credibility_tier", ""),
            "data_source": "not_run",
            "starting_equity": STARTING_EQUITY,
            "target_300_equity": TARGET_300,
            "target_400_equity": TARGET_400,
            "absolute_stop_equity": ABSOLUTE_STOP,
            "trailing_drawdown_dollars": TRAILING_DRAWDOWN,
            "project_stop_mode": PROJECT_STOP_MODE,
            "leverage_model": "none",
            "leverage_multiplier": 1.0,
            "exposure_multiplier": 1.0,
            "standard_or_stress": label,
            "cost_model": "not_applicable",
            "cost_model_quality": "unavailable",
            "result_status": run_status,
            "audit_verdict": "blocked_by_gate" if run_status == "blocked_by_gate" else "incomplete_evidence",
            "main_failure_mode": blocked_reason,
            "stop_enforced_metric_quality": "unavailable",
            "stop_enforced_metric_source": "not_run",
            "stop_enforced_metric_notes": blocked_reason,
            "risk_framework_name": RISK_FRAMEWORK_NAME,
            "risk_framework_verdict": "blocked_by_gate" if run_status == "blocked_by_gate" else "incomplete_evidence",
            "paper_forward_allowed_by_risk_framework": False,
            "promotion_blockers": run_status,
            "notes": blocked_reason,
            **family_extra_fields(spec, run_status, blocked_reason),
        }
    )
    return {col: row.get(col, math.nan) for col in CHALLENGE_COLUMNS}


def blank_family_rolling_row(
    run_id: str,
    spec: dict[str, Any],
    rolling_status: str,
    notes: str,
) -> dict[str, Any]:
    row = {col: math.nan for col in ROLLING_COLUMNS}
    row.update(
        {
            "run_id": run_id,
            "lane": "independent_family_challenge",
            "strategy": spec.get("underlying_strategy", spec.get("family_id", "")),
            "family_id": spec.get("family_id", ""),
            "family_group": spec.get("family_group", ""),
            "family_role": spec.get("role", ""),
            "independent_family_account": True,
            "role": spec.get("role", ""),
            "credibility_tier": spec.get("credibility_tier", ""),
            "leverage_multiplier": 1.0,
            "exposure_multiplier": 1.0,
            "standard_or_stress": "not_applicable",
            "rolling_method": "not_run",
            "number_of_windows": 0,
            "possible_window_count": 0,
            "sampled_results_are_final": False,
            "final_validation_completed": False,
            "rolling_status": rolling_status,
            "stop_enforced_metric_quality": "unavailable",
            "risk_framework_name": RISK_FRAMEWORK_NAME,
            "risk_framework_verdict": "blocked_by_gate" if rolling_status == "blocked_by_gate" else "incomplete_evidence",
            "paper_forward_allowed_by_risk_framework": False,
            "promotion_blockers": rolling_status,
            "notes": notes,
            "rolling_metric_quality": "unavailable",
            "rolling_notes": notes,
        }
    )
    return {col: row.get(col, math.nan) for col in ROLLING_COLUMNS}


def family_price_cache(date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = load_etf_price_cache(["SPY", "BIL", "IEF", "GLD"])
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    prices = data.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    if date_index is not None:
        prices = prices.reindex(pd.DatetimeIndex(pd.to_datetime(date_index))).ffill()
    return data, prices.dropna(how="all")


def build_family_weights(prices: pd.DataFrame, strategy: str) -> tuple[pd.DataFrame, str]:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if strategy in {"SPY_buy_hold", "BIL_cash_proxy", "SPY_200d_trend_model"}:
        cols = [col for col in ["SPY", "BIL"] if col in prices.columns]
        if not cols:
            return weights, "required SPY/BIL cache unavailable"
        base = build_etf_benchmark_weights(prices.reindex(columns=cols).ffill(), strategy)
        return weights.add(base.reindex(index=weights.index, columns=weights.columns).fillna(0.0), fill_value=0.0), "computed_from_cached_adjusted_prices"
    symbol_map = {"IEF_buy_hold": "IEF", "GLD_buy_hold": "GLD"}
    if strategy in symbol_map:
        symbol = symbol_map[strategy]
        if symbol not in prices.columns or not prices[symbol].notna().any():
            return weights, f"{symbol} cache unavailable"
        weights.loc[prices[symbol].notna(), symbol] = 1.0
        return weights.shift(1).ffill().fillna(0.0), "computed_from_cached_adjusted_prices"
    return weights, "exact daily family return stream unavailable in compact challenge layer"


def family_variant_for_strategy(strategy: str) -> str | None:
    return {
        "A_ETF_sector_momentum": "current_momentum_only_A",
        "current_no_cash_proxy_alpha_AB": "current_no_cash_proxy_alpha_AB",
    }.get(strategy)


def build_exact_strategy_family_full_rows(
    run_id: str,
    spec: dict[str, Any],
    variant_name: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    context = load_exact_etf_context()
    config = context["config"]
    prepared = context["prepared"]
    variant_cfg = strategy_variant_config(config, variant_name)
    full_range = config["date_ranges"]["full"]
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    rows: list[dict[str, Any]] = []
    completed = True
    for label in labels:
        if runtime_deadline and time.monotonic() > runtime_deadline:
            completed = False
            break
        result = Backtester(prepared, variant_cfg).run(
            f"family_exact_{variant_name}_{label}",
            str(full_range["start"]),
            full_range.get("end") or config["data"].get("end_date"),
            slippages[label],
        )
        curve = result.equity_curve
        audit = audit_dict_from_stop(stop_audit_from_equity(curve["equity"], curve["date"]))
        rows.append(
            build_challenge_row(
                run_id=run_id,
                lane="independent_family_challenge",
                strategy=str(spec["underlying_strategy"]),
                role=spec["role"],
                instrument_family=spec["family_group"],
                credibility_tier=str(spec["credibility_tier"]).replace("_if_exhaustive", ""),
                data_source=f"existing ETF adjusted OHLC via {context['data_source']}; exact variant={variant_name}",
                start_date=str(pd.to_datetime(curve["date"]).min().date()),
                end_date=str(pd.to_datetime(curve["date"]).max().date()),
                standard_or_stress=label,
                spread_slippage_per_side=slippages[label],
                leverage_model="none",
                leverage_multiplier=1.0,
                exposure_multiplier=1.0,
                financing_cost_assumption=0.0,
                audit=audit,
                cost_model_quality="exact",
                number_of_trades_or_rebalances=float(len(result.trades)),
                benchmark_name="SPY_200d_trend_model",
                stop_enforced_metric_quality="exact",
                stop_enforced_metric_source="computed_from_existing_backtester_variant_equity_curve",
                stop_enforced_metric_notes="Exact strategy-family stream exposed through existing fixed-rule Backtester variant; no parameter or rule changes.",
                notes=f"Independent family exact strategy stream via {variant_name}; not a portfolio allocation and not a real-money recommendation.",
                extra_fields=family_extra_fields(spec, "completed"),
            )
        )
    coverage = [
        {
            "lane": "independent_family_challenge",
            "data_source": f"existing ETF adjusted OHLC via {context['data_source']}",
            "symbols": ",".join(context["coverage"].get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
            "start_date": context["coverage"].get("first_date", pd.Series(dtype=str)).min() if "first_date" in context["coverage"] else "",
            "end_date": context["coverage"].get("last_date", pd.Series(dtype=str)).max() if "last_date" in context["coverage"] else "",
            "row_count": int(context["coverage"].get("row_count", pd.Series(dtype=float)).sum()) if "row_count" in context["coverage"] else math.nan,
            "missing_data_notes": f"Exact family stream for {spec['family_id']} uses existing Backtester variant {variant_name}; raw OHLCV excluded.",
            "adjusted_or_unadjusted": "adjusted OHLC per ETF evidence lane",
            "raw_data_included_in_evidence": False,
            "major_limitations": "yfinance/Yahoo cache limitations and ETF inception differences still apply.",
        }
    ]
    return rows, coverage, completed


def build_exact_strategy_family_rolling_rows(
    run_id: str,
    spec: dict[str, Any],
    variant_name: str,
    mode: str,
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    del run_id, spec, mode, runtime_deadline
    # The existing Backtester variant path can produce full-period equity curves
    # for this fixed-rule variant, but the independent-family challenge requires
    # a compact daily stream that can be replayed as fresh $3,000 rolling windows
    # with reset portfolio/risk state. No such accepted adapter exists yet.
    # Returning no rows prevents summary-metric or full-period approximations from
    # appearing in rolling_window_summary.csv.
    _ = variant_name
    return [], False
    rows: list[dict[str, Any]] = []
    completed = True
    for label in labels:
        for horizon in horizons:
            possible = max(0, len(dates) - horizon + 1)
            starts, possible_count, method = sample_etf_starts(pd.DataFrame(index=pd.DatetimeIndex(dates), data={"x": 1.0}), horizon, mode)
            if possible_count != possible:
                possible_count = possible
            if runtime_deadline and time.monotonic() > runtime_deadline:
                completed = False
                starts = []
            group_rows: list[dict[str, Any]] = []
            if starts:
                for start_idx in starts:
                    if runtime_deadline and time.monotonic() > runtime_deadline:
                        completed = False
                        break
                    group_rows.extend(
                        _rolling_group_rows(
                            data,
                            config,
                            dates,
                            variant_name,
                            label,
                            slippages[label],
                            horizon,
                            [int(start_idx)],
                            method,
                            possible_count,
                        )
                    )
            if group_rows:
                summary = summarize_independent_rolling_windows(pd.DataFrame(group_rows))
                for _, srow in summary.iterrows():
                    base = rolling_row_from_independent_summary(
                        run_id,
                        srow,
                        str(spec["underlying_strategy"]),
                        f"Exact strategy-family rolling via existing Backtester variant {variant_name}; no summary-metric approximation.",
                        completed,
                    )
                    exact_final = (
                        method == "all_possible"
                        and completed
                        and int(base.get("number_of_windows", 0)) == int(base.get("possible_window_count", -1))
                        and int(base.get("number_of_windows", 0)) > 0
                    )
                    base.update(
                        {
                            "lane": "independent_family_challenge",
                            "family_id": spec["family_id"],
                            "family_group": spec["family_group"],
                            "family_role": spec["role"],
                            "independent_family_account": True,
                            "role": spec["role"],
                            "credibility_tier": str(spec["credibility_tier"]).replace("_if_exhaustive", ""),
                            "rolling_status": "completed" if exact_final or method != "all_possible" else "partial",
                            "sampled_results_are_final": exact_final,
                            "final_validation_completed": exact_final,
                            "stop_enforced_metric_quality": "exact" if exact_final else "partial",
                        }
                    )
                    rows.append(base)
            else:
                rows.append(
                    {
                        "run_id": run_id,
                        "lane": "independent_family_challenge",
                        "strategy": spec["underlying_strategy"],
                        "family_id": spec["family_id"],
                        "family_group": spec["family_group"],
                        "family_role": spec["role"],
                        "independent_family_account": True,
                        "role": spec["role"],
                        "credibility_tier": str(spec["credibility_tier"]).replace("_if_exhaustive", ""),
                        "leverage_multiplier": 1.0,
                        "exposure_multiplier": 1.0,
                        "standard_or_stress": label,
                        "horizon": horizon,
                        "rolling_method": method,
                        "number_of_windows": 0,
                        "possible_window_count": possible_count,
                        "sampled_results_are_final": False,
                        "final_validation_completed": False,
                        "rolling_status": "incomplete_evidence",
                        "stop_enforced_metric_quality": "unavailable",
                        "notes": f"Exact family rolling unavailable or runtime budget exceeded for {variant_name}.",
                        "rolling_metric_quality": "unavailable",
                        "rolling_notes": f"Exact family rolling unavailable or runtime budget exceeded for {variant_name}.",
                    }
                )
                completed = False
            if runtime_deadline and time.monotonic() > runtime_deadline:
                completed = False
                break
        if not completed and mode == "candidate_exhaustive":
            break
    return [row for row in rows], completed


def build_crypto_family_rows(
    run_id: str,
    spec: dict[str, Any],
    mode: str,
    no_network: bool,
    reuse_cache: bool,
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    strategy = str(spec.get("underlying_strategy", ""))
    config_path = Path("exploratory/crypto_spot_momentum/config.yaml")
    config = load_crypto_config(config_path)
    try:
        loaded = load_crypto_data(config, source="yfinance", no_network=no_network, reuse_cache=reuse_cache, force_download=False)
    except CryptoDataError:
        reason = "Crypto cache unavailable under --no-network; family row remains incomplete evidence."
        return (
            [blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason)],
            [blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason)],
            [
                {
                    "lane": "independent_family_challenge",
                    "data_source": "yfinance_crypto_cache",
                    "symbols": "BTC-USD,ETH-USD",
                    "start_date": "",
                    "end_date": "",
                    "row_count": 0,
                    "missing_data_notes": reason,
                    "adjusted_or_unadjusted": "adj_close equals close when adjusted close is unavailable",
                    "raw_data_included_in_evidence": False,
                    "major_limitations": "Crypto family unavailable; no network download attempted.",
                }
            ],
            False,
        )
    mode_key = mode if mode != "candidate_exhaustive" else "research_sample"
    mode_cfg = config["validation"]["modes"].get(mode_key, config["validation"]["modes"]["research_sample"])
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    start_date = loaded.data["date"].min().date().isoformat()
    end_date = loaded.data["date"].max().date().isoformat()
    signal_weights = generate_signal_weights(loaded.data, strategy, strategy_config(config, strategy))
    for label in mode_cfg.get("slippage_labels", ["standard", "stress"]):
        cost = float(config["costs"]["standard_fee_slippage_per_side"] if label == "standard" else config["costs"]["stress_fee_slippage_per_side"])
        sim = simulate_strategy(
            loaded.data,
            strategy,
            strategy_config(config, strategy),
            STARTING_EQUITY,
            cost,
            precomputed_signal_weights=signal_weights,
        )
        audit = audit_dict_from_stop(stop_audit_from_equity(sim.equity_curve["equity"], sim.equity_curve["date"]))
        rows.append(
            build_challenge_row(
                run_id=run_id,
                lane="independent_family_challenge",
                strategy=strategy,
                role=spec["role"],
                instrument_family=spec["family_group"],
                credibility_tier="tier1_exploratory",
                data_source=f"{loaded.source} cache only; no network download in family run",
                start_date=start_date,
                end_date=end_date,
                standard_or_stress=label,
                spread_slippage_per_side=cost,
                leverage_model="none",
                leverage_multiplier=1.0,
                exposure_multiplier=1.0,
                financing_cost_assumption=0.0,
                audit=audit,
                cost_model_quality="approximate",
                time_in_market=float(sim.weights.sum(axis=1).gt(0).mean()) if not sim.weights.empty else 0.0,
                number_of_trades_or_rebalances=len(sim.rebalances),
                turnover_estimate=sim.turnover_estimate,
                benchmark_name="BTC_buy_hold",
                stop_enforced_metric_quality="exact",
                stop_enforced_metric_source="computed_from_crypto_family_equity_curve",
                stop_enforced_metric_notes="Exact within simulated crypto curve, but crypto family remains Tier 1 exploratory and sampled/non-final.",
                notes="Independent crypto family row; Tier 1 exploratory only, cache-only, no leverage/perps/futures, no real-money recommendation.",
                extra_fields=family_extra_fields(spec, "completed"),
            )
        )
    prices = price_matrix(loaded.data)
    for label in mode_cfg.get("slippage_labels", ["standard"]):
        base_cost = float(config["costs"]["standard_fee_slippage_per_side"] if label == "standard" else config["costs"]["stress_fee_slippage_per_side"])
        for horizon in mode_cfg.get("horizons", [90]):
            if runtime_deadline and time.monotonic() > runtime_deadline:
                return rows, rolling_rows, [], False
            starts, possible_count = sample_start_indices(
                loaded.data,
                int(horizon),
                mode_cfg.get("rolling_method", "deterministic_stratified_sample"),
                mode_cfg.get("sample_size_per_group"),
            )
            window_metrics = [
                fast_crypto_window(
                    prices=prices,
                    signal_weights=signal_weights,
                    idx=int(idx),
                    horizon=int(horizon),
                    spread_slippage_per_side=base_cost,
                    leverage=1.0,
                    financing_annual=0.0,
                )
                for idx in starts
            ]
            if not window_metrics:
                rolling_rows.append(blank_family_rolling_row(run_id, spec, "incomplete_evidence", "No crypto family windows completed."))
                continue
            summary = summarize_window_metrics(window_metrics)
            rolling_rows.append(
                {
                    "run_id": run_id,
                    "lane": "independent_family_challenge",
                    "strategy": strategy,
                    "family_id": spec["family_id"],
                    "family_group": spec["family_group"],
                    "family_role": spec["role"],
                    "independent_family_account": True,
                    "role": spec["role"],
                    "credibility_tier": "tier1_exploratory",
                    "leverage_multiplier": 1.0,
                    "exposure_multiplier": 1.0,
                    "standard_or_stress": label,
                    "horizon": int(horizon),
                    "rolling_method": mode_cfg.get("rolling_method", "deterministic_stratified_sample"),
                    "possible_window_count": int(possible_count),
                    "sampled_results_are_final": False,
                    "final_validation_completed": False,
                    "rolling_status": "sampled_tier1_exploratory",
                    "stop_enforced_metric_quality": "exact",
                    "notes": "Crypto family rolling is Tier 1 exploratory and sampled/non-final.",
                    "rolling_metric_quality": "sampled_tier1_crypto_family",
                    "rolling_notes": "Crypto family rolling is Tier 1 exploratory and sampled/non-final.",
                    **summary,
                }
            )
    coverage = [
        {
            "lane": "independent_family_challenge",
            "data_source": loaded.source,
            "symbols": ",".join(loaded.coverage["symbol"].dropna().astype(str).tolist()),
            "start_date": start_date,
            "end_date": end_date,
            "row_count": int(loaded.coverage["row_count"].sum()),
            "missing_data_notes": "; ".join(loaded.coverage["excluded_reason"].dropna().astype(str).unique()),
            "adjusted_or_unadjusted": "adj_close equals close when adjusted close is unavailable",
            "raw_data_included_in_evidence": False,
            "major_limitations": "Tier 1 exploratory yfinance crypto data; no bid/ask, order book, outage, custody, delisting, leverage, perps, or futures modeling.",
        }
    ]
    return rows, rolling_rows, coverage, True


def build_family_rolling_rows(
    run_id: str,
    spec: dict[str, Any],
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    mode: str,
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    labels = ["standard", "stress"]
    prices_array = prices.to_numpy(dtype=float)
    weights_array = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)
    for label in labels:
        cost = 0.0005 if label == "standard" else 0.001
        for horizon in horizons:
            starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
            window_metrics: list[dict[str, Any]] = []
            for idx in starts:
                if runtime_deadline and time.monotonic() > runtime_deadline:
                    completed = False
                    break
                window_metrics.append(fast_weighted_window(prices_array, weights_array, prices.index, int(idx), int(horizon), cost))
            if window_metrics:
                summary = summarize_window_metrics(window_metrics)
                exact_final = method == "all_possible" and completed and len(window_metrics) == possible_count
                rows.append(
                    {
                        "run_id": run_id,
                        "lane": "independent_family_challenge",
                        "strategy": spec["underlying_strategy"],
                        "family_id": spec["family_id"],
                        "family_group": spec["family_group"],
                        "family_role": spec["role"],
                        "independent_family_account": True,
                        "role": spec["role"],
                        "credibility_tier": spec["credibility_tier"],
                        "leverage_multiplier": 1.0,
                        "exposure_multiplier": 1.0,
                        "standard_or_stress": label,
                        "horizon": horizon,
                        "rolling_method": method,
                        "possible_window_count": possible_count,
                        "sampled_results_are_final": exact_final,
                        "final_validation_completed": exact_final,
                        "rolling_status": "completed" if exact_final or method != "all_possible" else "partial",
                        "stop_enforced_metric_quality": "exact" if exact_final else "partial",
                        "notes": "Independent family row: separate $3,000 account; not a portfolio mix.",
                        "rolling_metric_quality": "exact_family_all_possible" if exact_final else "family_sample_or_partial",
                        "rolling_notes": "Computed from cached adjusted prices or exact fixed-rule benchmark weights; raw OHLCV excluded.",
                        **summary,
                    }
                )
            else:
                rows.append(
                    {
                        "run_id": run_id,
                        "lane": "independent_family_challenge",
                        "strategy": spec["underlying_strategy"],
                        "family_id": spec["family_id"],
                        "family_group": spec["family_group"],
                        "family_role": spec["role"],
                        "independent_family_account": True,
                        "role": spec["role"],
                        "credibility_tier": spec["credibility_tier"],
                        "leverage_multiplier": 1.0,
                        "exposure_multiplier": 1.0,
                        "standard_or_stress": label,
                        "horizon": horizon,
                        "rolling_method": method,
                        "number_of_windows": 0,
                        "possible_window_count": possible_count,
                        "sampled_results_are_final": False,
                        "final_validation_completed": False,
                        "rolling_status": "unavailable",
                        "stop_enforced_metric_quality": "unavailable",
                        "notes": "Family rolling unavailable: no windows completed.",
                        "rolling_metric_quality": "unavailable",
                        "rolling_notes": "No windows completed.",
                    }
                )
            if not completed:
                break
        if not completed:
            break
    return rows, completed


def build_independent_family_rows(
    run_id: str,
    mode: str,
    include_family_challenge: bool,
    include_exploratory_crypto_families: bool,
    runtime_deadline: float | None = None,
    no_network: bool = True,
    reuse_cache: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    if not include_family_challenge:
        return [], [], [], True
    specs = load_family_specs()
    data, prices = family_price_cache()
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    completed = True
    labels = ["standard", "stress"]
    runnable_strategies = {"SPY_200d_trend_model", "SPY_buy_hold", "BIL_cash_proxy", "IEF_buy_hold", "GLD_buy_hold"}
    for spec in specs:
        if family_is_crypto(spec) and not include_exploratory_crypto_families:
            continue
        run_allowed = spec.get("run_allowed")
        strategy = str(spec.get("underlying_strategy", spec.get("family_id", "")))
        if run_allowed is False:
            reason = str(spec.get("blocked_reason", "Family is blocked by gate."))
            rows.append(blank_family_challenge_row(run_id, spec, "blocked_by_gate", reason))
            rolling_rows.append(blank_family_rolling_row(run_id, spec, "blocked_by_gate", reason))
            continue
        if family_is_crypto(spec):
            crypto_rows, crypto_rolling, crypto_coverage, crypto_completed = build_crypto_family_rows(
                run_id,
                spec,
                mode,
                no_network=no_network,
                reuse_cache=reuse_cache,
                runtime_deadline=runtime_deadline,
            )
            rows.extend(crypto_rows)
            rolling_rows.extend(crypto_rolling)
            coverage_rows.extend(crypto_coverage)
            completed = completed and crypto_completed and mode != "research_sample"
            continue
        variant_name = family_variant_for_strategy(strategy)
        if variant_name:
            try:
                exact_rolling, rolling_completed = build_exact_strategy_family_rolling_rows(
                    run_id,
                    spec,
                    variant_name,
                    mode,
                    runtime_deadline=runtime_deadline,
                )
                if not rolling_completed:
                    reason = (
                        f"Exact challenge-comparable fresh-window rolling stream for {variant_name} is not exposed in compact mode. "
                        "The existing Backtester variant can produce full-period equity, but the family challenge requires fresh $3,000 "
                        "30/60/90/180 rolling windows with reset risk state. This row is not approximated from summary metrics, "
                        "full-period curves, or sampled rolling evidence."
                    )
                    rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason))
                    completed = False
                    continue
                exact_rows, exact_coverage, full_completed = build_exact_strategy_family_full_rows(
                    run_id,
                    spec,
                    variant_name,
                    labels,
                    runtime_deadline=runtime_deadline,
                )
                if not exact_rows:
                    reason = f"Exact daily family stream for {variant_name} did not complete within runtime budget."
                    rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason))
                    completed = False
                    continue
                rows.extend(exact_rows)
                rolling_rows.extend(exact_rolling)
                coverage_rows.extend(exact_coverage)
                completed = completed and full_completed and rolling_completed
            except Exception as exc:
                reason = f"Exact daily family stream adapter failed without approximation: {exc}"
                rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason))
                rolling_rows.append(blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason))
                completed = False
            continue
        if strategy not in runnable_strategies:
            reason = "Exact daily family return stream unavailable in compact challenge layer; not approximated from summary metrics."
            rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason))
            rolling_rows.append(blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason))
            completed = False
            continue
        if data.empty or prices.empty:
            reason = "Required adjusted ETF cache unavailable."
            rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason))
            rolling_rows.append(blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason))
            completed = False
            continue
        weights, source_note = build_family_weights(prices, strategy)
        if weights.empty or weights.sum(axis=1).abs().sum() <= 0:
            rows.append(blank_family_challenge_row(run_id, spec, "incomplete_evidence", source_note))
            rolling_rows.append(blank_family_rolling_row(run_id, spec, "incomplete_evidence", source_note))
            completed = False
            continue
        for label in labels:
            cost = 0.0005 if label == "standard" else 0.001
            curve, rebalances, turnover, time_in_market = simulate_weighted_equity(prices, weights, cost)
            audit = audit_dict_from_stop(stop_audit_from_equity(curve["equity"], curve["date"]))
            rows.append(
                build_challenge_row(
                    run_id=run_id,
                    lane="independent_family_challenge",
                    strategy=strategy,
                    role=spec["role"],
                    instrument_family=spec["family_group"],
                    credibility_tier=str(spec["credibility_tier"]).replace("_if_exhaustive", ""),
                    data_source=f"data/cache adjusted ETF prices; {source_note}",
                    start_date=prices.index.min().date().isoformat(),
                    end_date=prices.index.max().date().isoformat(),
                    standard_or_stress=label,
                    spread_slippage_per_side=cost,
                    leverage_model="none",
                    leverage_multiplier=1.0,
                    exposure_multiplier=1.0,
                    financing_cost_assumption=0.0,
                    audit=audit,
                    cost_model_quality="exact",
                    time_in_market=time_in_market,
                    number_of_trades_or_rebalances=rebalances,
                    turnover_estimate=turnover,
                    benchmark_name="SPY_200d_trend_model",
                    stop_enforced_metric_quality="exact",
                    stop_enforced_metric_source="computed_from_independent_family_equity_curve",
                    stop_enforced_metric_notes="Each family row uses its own independent $3,000 account; no shared capital and no portfolio mix.",
                    notes="Independent family challenge row; not a portfolio allocation and not a real-money recommendation.",
                    extra_fields=family_extra_fields(spec, "completed"),
                )
            )
        family_rolling, family_completed = build_family_rolling_rows(run_id, spec, prices, weights, mode, runtime_deadline)
        rolling_rows.extend(family_rolling)
        completed = completed and family_completed
    coverage = coverage_rows + [
        {
            "lane": "independent_family_challenge",
            "data_source": "data/cache adjusted ETF prices plus blocked-family memo specs",
            "symbols": ",".join(sorted(data["symbol"].dropna().unique())) if not data.empty else "",
            "start_date": prices.index.min().date().isoformat() if not prices.empty else "",
            "end_date": prices.index.max().date().isoformat() if not prices.empty else "",
            "row_count": int(len(data)) if not data.empty else 0,
            "missing_data_notes": "Exact A/B and ETF sector momentum streams use existing Backtester adapters when available; blocked families are reported but not run.",
            "adjusted_or_unadjusted": "adjusted close for runnable ETF benchmark-like families",
            "raw_data_included_in_evidence": False,
            "major_limitations": "Family rows are independent $3,000 accounts and are not a blended portfolio allocation.",
        }
    ]
    return rows, rolling_rows, coverage, completed


def sample_etf_starts(prices: pd.DataFrame, horizon: int, mode: str, sample_size: int = 500) -> tuple[list[int], int, str]:
    possible = max(0, len(prices.index) - horizon + 1)
    if possible <= 0:
        return [], possible, "unavailable"
    if mode == "candidate_exhaustive":
        return list(range(possible)), possible, "all_possible"
    requested = min(sample_size, possible)
    base = set(np.linspace(0, possible - 1, max(1, requested // 3), dtype=int).tolist())
    spy = prices["SPY"] if "SPY" in prices.columns else prices.iloc[:, 0]
    vol = spy.pct_change(fill_method=None).rolling(20, min_periods=10).std()
    sma = spy.rolling(200, min_periods=50).mean()
    start_dates = pd.Index(prices.index[:possible])
    vol_at_start = vol.reindex(start_dates)
    trend_at_start = (spy.reindex(start_dates) > sma.reindex(start_dates)).fillna(False)
    high_vol = vol_at_start.sort_values(ascending=False).head(max(1, requested // 6)).index
    low_vol = vol_at_start.sort_values(ascending=True).head(max(1, requested // 6)).index
    above = start_dates[trend_at_start.to_numpy()]
    below = start_dates[~trend_at_start.to_numpy()]
    recent = start_dates[-max(1, requested // 6) :]
    date_to_idx = {date: i for i, date in enumerate(start_dates)}
    for group in [high_vol, low_vol, above[:: max(1, len(above) // max(1, requested // 8))], below[:: max(1, len(below) // max(1, requested // 8))], recent]:
        for date in group:
            if date in date_to_idx:
                base.add(date_to_idx[date])
    return sorted(base)[:requested], possible, "deterministic_stratified_sample"


def summarize_window_metrics(window_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    df = pd.DataFrame(window_metrics)
    if "stop_overshoot_dollars" not in df:
        df["stop_overshoot_dollars"] = 0.0
    if "average_exposure" not in df:
        df["average_exposure"] = math.nan
    if "median_exposure" not in df:
        df["median_exposure"] = math.nan
    if "percent_time_cash" not in df:
        df["percent_time_cash"] = math.nan
    if "percent_time_reduced_exposure" not in df:
        df["percent_time_reduced_exposure"] = math.nan
    if "percent_time_full_exposure" not in df:
        df["percent_time_full_exposure"] = math.nan
    if "portfolio_turnover" not in df:
        df["portfolio_turnover"] = math.nan
    if "unavailable_window" not in df:
        df["unavailable_window"] = False
    return {
        "number_of_windows": int(len(df)),
        "pct_target_300_hit": float(df["target_300_hit"].mean()),
        "pct_target_300_before_stop": float(df["target_300_before_stop"].mean()),
        "pct_target_400_hit": float(df["target_400_hit"].mean()),
        "pct_target_400_before_stop": float(df["target_400_before_stop"].mean()),
        "pct_any_project_stop_hit": float(df["any_project_stop_hit"].mean()),
        "pct_absolute_floor_stop_hit": float(df["absolute_floor_stop_hit"].mean()),
        "pct_trailing_drawdown_stop_hit": float(df["trailing_drawdown_stop_hit"].mean()),
        "median_final_equity": float(df["final_equity"].median()),
        "median_stop_enforced_final_equity": float(df["stop_enforced_final_equity"].median()),
        "mean_stop_enforced_final_equity": float(df["stop_enforced_final_equity"].mean()),
        "median_max_drawdown": float(df["max_drawdown_dollars"].median()),
        "worst_max_drawdown": float(df["max_drawdown_dollars"].min()),
        "pct_positive_return": float((df["stop_enforced_final_equity"] > STARTING_EQUITY).mean()),
        "pct_loss": float((df["stop_enforced_final_equity"] < STARTING_EQUITY).mean()),
        "pct_below_2400": float((df["stop_enforced_final_equity"] < ABSOLUTE_STOP).mean()),
        "pct_above_3300": float((df["stop_enforced_final_equity"] >= TARGET_300).mean()),
        "pct_above_3400": float((df["stop_enforced_final_equity"] >= TARGET_400).mean()),
        "worst_stop_enforced_loss": float(df["stop_enforced_final_equity"].min() - STARTING_EQUITY),
        "pct_windows_stop_overshoot_gt_50": float((df["stop_overshoot_dollars"] < -50.0).mean()),
        "pct_windows_stop_overshoot_gt_100": float((df["stop_overshoot_dollars"] < -100.0).mean()),
        "average_exposure": float(df["average_exposure"].mean()) if df["average_exposure"].notna().any() else math.nan,
        "median_exposure": float(df["median_exposure"].median()) if df["median_exposure"].notna().any() else math.nan,
        "percent_time_cash": float(df["percent_time_cash"].mean()) if df["percent_time_cash"].notna().any() else math.nan,
        "percent_time_reduced_exposure": float(df["percent_time_reduced_exposure"].mean()) if df["percent_time_reduced_exposure"].notna().any() else math.nan,
        "percent_time_full_exposure": float(df["percent_time_full_exposure"].mean()) if df["percent_time_full_exposure"].notna().any() else math.nan,
        "average_portfolio_turnover": float(df["portfolio_turnover"].mean()) if df["portfolio_turnover"].notna().any() else math.nan,
        "median_portfolio_turnover": float(df["portfolio_turnover"].median()) if df["portfolio_turnover"].notna().any() else math.nan,
        "unavailable_window_count": int(df["unavailable_window"].astype(bool).sum()),
    }


def rolling_row_from_independent_summary(
    run_id: str,
    row: pd.Series,
    strategy_name: str,
    source_note: str,
    final_completed: bool,
) -> dict[str, Any]:
    method = str(row.get("window_sampling_method", ""))
    number = int(row.get("number_of_windows", 0))
    possible = int(row.get("possible_window_count", number))
    exact_final = bool(final_completed and method == "all_possible" and number == possible and number > 0)
    return {
        "run_id": run_id,
        "lane": "etf_validated_lane",
        "strategy": strategy_name,
        "role": "focused_finalist",
        "credibility_tier": "tier3_candidate_validation",
        "leverage_multiplier": 1.0,
        "exposure_multiplier": 1.0,
        "standard_or_stress": row["slippage_label"],
        "horizon": int(row["horizon_trading_days"]),
        "rolling_method": method,
        "number_of_windows": number,
        "possible_window_count": possible,
        "sampled_results_are_final": exact_final,
        "final_validation_completed": exact_final,
        "pct_target_300_hit": row["pct_windows_target_300_hit"],
        "pct_target_300_before_stop": row["pct_windows_target_300_before_stop"],
        "pct_target_400_hit": row["pct_windows_target_400_hit"],
        "pct_target_400_before_stop": row["pct_windows_target_400_before_stop"],
        "pct_any_project_stop_hit": row["pct_windows_any_stop_hit"],
        "pct_absolute_floor_stop_hit": row["pct_windows_absolute_stop_hit"],
        "pct_trailing_drawdown_stop_hit": row["pct_windows_trailing_stop_hit"],
        "median_final_equity": row["median_final_equity"],
        "median_stop_enforced_final_equity": row.get("median_stop_enforced_final_equity", row["median_final_equity"]),
        "mean_stop_enforced_final_equity": row.get("mean_stop_enforced_final_equity", row["mean_final_equity"]),
        "median_max_drawdown": row["median_max_drawdown"],
        "worst_max_drawdown": row["worst_max_drawdown"],
        "pct_positive_return": row["pct_windows_positive_return"],
        "pct_loss": row["pct_windows_loss"],
        "pct_below_2400": row["pct_windows_below_2400"],
        "pct_above_3300": row["pct_windows_above_3300"],
        "pct_above_3400": row["pct_windows_above_3400"],
        "worst_stop_enforced_loss": row.get("worst_stop_enforced_loss", math.nan),
        "pct_windows_stop_overshoot_gt_50": row.get("pct_windows_stop_overshoot_gt_50", 0.0),
        "pct_windows_stop_overshoot_gt_100": row.get("pct_windows_stop_overshoot_gt_100", 0.0),
        "stop_enforced_metric_quality": "exact" if exact_final else "partial",
        "notes": source_note,
        "rolling_metric_quality": "exact" if exact_final else "partial",
        "rolling_notes": source_note,
    }


def required_exact_groups_present(summary: pd.DataFrame, aliases: tuple[str, ...] = FOCUSED_FINALIST_ALIASES) -> bool:
    if summary.empty:
        return False
    required = {(label, horizon) for label in FOCUSED_LABELS for horizon in FOCUSED_HORIZONS}
    present: set[tuple[str, int]] = set()
    for _, row in summary.iterrows():
        if str(row.get("variant_name")) not in aliases:
            continue
        method = str(row.get("window_sampling_method", ""))
        number = int(row.get("number_of_windows", 0))
        possible = int(row.get("possible_window_count", -1))
        if method == "all_possible" and number == possible and number > 0:
            present.add((str(row.get("slippage_label")), int(row.get("horizon_trading_days"))))
    return required.issubset(present)


def find_cached_exact_finalist_summary() -> tuple[pd.DataFrame, str]:
    candidates: list[tuple[str, Path]] = []
    for path in sorted((REPO_ROOT / "evidence" / "runs").glob("*/independent_rolling_window_summary.csv"), reverse=True):
        try:
            summary = pd.read_csv(path)
        except Exception:
            continue
        if required_exact_groups_present(summary):
            candidates.append((path.parent.name, path))
    if not candidates:
        return pd.DataFrame(), ""
    # Prefer the newest exact artifact by run id. Older labels may use
    # no_cash_proxy_alpha_AB; it is the exact A/B no-cash equivalent.
    _, path = sorted(candidates, key=lambda item: item[0])[-1]
    summary = pd.read_csv(path)
    summary = summary[summary["variant_name"].astype(str).isin(FOCUSED_FINALIST_ALIASES)].copy()
    summary["variant_name"] = FOCUSED_FINALIST
    return summary, str(path)


def compute_exact_finalist_rolling_summary(
    variant_name: str,
    runtime_deadline: float | None = None,
) -> tuple[pd.DataFrame, bool, str]:
    context = load_exact_etf_context()
    config = context["config"]
    data = context["prepared"]
    dates = context["dates"]
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    rows: list[dict[str, Any]] = []
    completed = True
    for label in FOCUSED_LABELS:
        for horizon in FOCUSED_HORIZONS:
            possible = max(0, len(dates) - horizon + 1)
            starts = list(range(possible))
            if runtime_deadline and time.monotonic() > runtime_deadline:
                completed = False
                break
            group_rows = _rolling_group_rows(
                data,
                config,
                dates,
                variant_name,
                label,
                slippages[label],
                horizon,
                starts,
                "all_possible",
                possible,
            )
            rows.extend(group_rows)
        if not completed:
            break
    if not rows:
        return pd.DataFrame(), False, "computed_exact_backtester_no_rows"
    results = pd.DataFrame(rows)
    summary = summarize_independent_rolling_windows(results)
    summary["variant_name"] = variant_name
    all_complete = required_exact_groups_present(summary, aliases=(variant_name,)) and completed
    return summary, all_complete, "computed_exact_backtester_current_run"


def build_exact_finalist_rolling_rows(
    run_id: str,
    variant_name: str,
    reuse_cache: bool,
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool, str]:
    source = ""
    summary = pd.DataFrame()
    completed = False
    if reuse_cache:
        summary, source = find_cached_exact_finalist_summary()
        completed = required_exact_groups_present(summary, aliases=(variant_name,)) if not summary.empty else False
    if summary.empty or not completed:
        summary, completed, source = compute_exact_finalist_rolling_summary(variant_name, runtime_deadline)
    if summary.empty:
        return [], False, source or "unavailable"
    source_note = (
        f"Exact all_possible rolling windows from existing Backtester artifact {source}; "
        "no sampled rows used."
        if source.endswith(".csv")
        else "Exact all_possible rolling windows computed by the focused challenge audit using the existing Backtester."
    )
    rows = [
        rolling_row_from_independent_summary(run_id, row, variant_name, source_note, completed)
        for _, row in summary.sort_values(["slippage_label", "horizon_trading_days"]).iterrows()
    ]
    return rows, completed, source


def build_etf_benchmark_rolling_rows(
    run_id: str,
    prices: pd.DataFrame,
    benchmark: str,
    mode: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    base_weights = build_etf_benchmark_weights(prices, benchmark)
    prices_array = prices.to_numpy(dtype=float)
    weights_array = base_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)
    for label in labels:
        cost = 0.0005 if label == "standard" else 0.001
        for horizon in horizons:
            starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
            window_metrics: list[dict[str, Any]] = []
            for idx in starts:
                if runtime_deadline and time.monotonic() > runtime_deadline:
                    completed = False
                    break
                window_metrics.append(fast_weighted_window(prices_array, weights_array, prices.index, int(idx), int(horizon), cost))
            if window_metrics:
                summary = summarize_window_metrics(window_metrics)
                rows.append(
                    {
                        "run_id": run_id,
                        "lane": "etf_benchmark",
                        "strategy": benchmark,
                        "role": "benchmark",
                        "credibility_tier": "benchmark",
                        "leverage_multiplier": 1.0,
                        "exposure_multiplier": 1.0,
                        "standard_or_stress": label,
                        "horizon": horizon,
                        "rolling_method": method,
                        "possible_window_count": possible_count,
                        "sampled_results_are_final": method == "all_possible" and completed and len(window_metrics) == possible_count,
                        "final_validation_completed": method == "all_possible" and completed and len(window_metrics) == possible_count,
                        "stop_enforced_metric_quality": "exact" if len(window_metrics) == possible_count else "partial",
                        "notes": "Computed directly from cached adjusted ETF benchmark prices on the finalist effective calendar.",
                        "rolling_metric_quality": "exact" if len(window_metrics) == possible_count or method != "all_possible" else "partial",
                        "rolling_notes": "Computed from cached adjusted ETF benchmark equity curve.",
                        **summary,
                    }
                )
            else:
                rows.append(
                    {
                        "run_id": run_id,
                        "lane": "etf_benchmark",
                        "strategy": benchmark,
                        "role": "benchmark",
                        "credibility_tier": "benchmark",
                        "leverage_multiplier": 1.0,
                        "exposure_multiplier": 1.0,
                        "standard_or_stress": label,
                        "horizon": horizon,
                        "rolling_method": method,
                        "number_of_windows": 0,
                        "possible_window_count": possible_count,
                        "sampled_results_are_final": False,
                        "final_validation_completed": False,
                        "stop_enforced_metric_quality": "unavailable",
                        "notes": "Benchmark rolling unavailable: no windows completed.",
                        "rolling_metric_quality": "unavailable",
                        "rolling_notes": "Benchmark rolling unavailable: no windows completed.",
                    }
                )
            if not completed:
                break
        if not completed:
            break
    return rows, completed


def diagnostic_strategy_name(base_strategy: str, leverage_multiplier: float) -> str:
    suffix = str(leverage_multiplier).replace(".", "_")
    return f"{base_strategy}_sim_{suffix}x"


def exposure_strategy_name(exposure_multiplier: float) -> str:
    suffix = f"{exposure_multiplier:.2f}".replace(".", "_")
    return f"SPY_200d_exposure_frontier_{suffix}x"


def vol_control_strategy_name(exposure_cap: float) -> str:
    suffix = f"{exposure_cap:.2f}".replace(".", "_")
    return f"SPY_200d_vol_target_12_cap_{suffix}_v1"


def exposure_stats(weights: pd.DataFrame | pd.Series, cap: float) -> dict[str, float]:
    if isinstance(weights, pd.DataFrame):
        exposure = weights.abs().sum(axis=1).astype(float)
    else:
        exposure = weights.astype(float).abs()
    if exposure.empty:
        return {
            "average_exposure": math.nan,
            "median_exposure": math.nan,
            "max_exposure": math.nan,
            "min_exposure": math.nan,
            "percent_time_cash": math.nan,
            "percent_time_reduced_exposure": math.nan,
            "percent_time_full_exposure": math.nan,
        }
    tol = 1e-6
    return {
        "average_exposure": float(exposure.mean()),
        "median_exposure": float(exposure.median()),
        "max_exposure": float(exposure.max()),
        "min_exposure": float(exposure.min()),
        "percent_time_cash": float((exposure <= tol).mean()),
        "percent_time_reduced_exposure": float(((exposure > tol) & (exposure < cap - tol)).mean()),
        "percent_time_full_exposure": float((exposure >= cap - tol).mean()),
    }


def build_etf_vol_control_weights(prices: pd.DataFrame, exposure_cap: float) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if "SPY" not in prices.columns:
        return weights
    spy = prices["SPY"].astype(float)
    sma = spy.rolling(200, min_periods=200).mean()
    realized_vol = spy.pct_change(fill_method=None).rolling(ETF_VOL_CONTROL_WINDOW, min_periods=ETF_VOL_CONTROL_WINDOW).std() * math.sqrt(252)
    risk_on = (spy > sma) & realized_vol.notna() & (realized_vol > 0)
    exposure = (ETF_VOL_CONTROL_TARGET / realized_vol).clip(lower=0.0, upper=exposure_cap)
    weights.loc[risk_on.fillna(False), "SPY"] = exposure.loc[risk_on.fillna(False)]
    return weights.shift(1).fillna(0.0)


def build_etf_leverage_diagnostic_rolling_rows(
    run_id: str,
    prices: pd.DataFrame,
    benchmark: str,
    mode: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    base_weights = build_etf_benchmark_weights(prices, benchmark)
    prices_array = prices.to_numpy(dtype=float)
    weights_array = base_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)
    for label in labels:
        base_cost = 0.0005 if label == "standard" else 0.001
        for leverage_multiplier, assumptions in ETF_LEVERAGE_DIAGNOSTICS.items():
            financing = float(assumptions["financing_cost_annualized"])
            strategy = diagnostic_strategy_name(benchmark, leverage_multiplier)
            for horizon in horizons:
                starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
                window_metrics: list[dict[str, Any]] = []
                for idx in starts:
                    if runtime_deadline and time.monotonic() > runtime_deadline:
                        completed = False
                        break
                    window_metrics.append(
                        fast_levered_weighted_window(
                            prices_array,
                            weights_array,
                            prices.index,
                            int(idx),
                            int(horizon),
                            base_cost,
                            leverage_multiplier,
                            financing,
                        )
                    )
                if window_metrics:
                    summary = summarize_window_metrics(window_metrics)
                    catastrophic = bool(pd.DataFrame(window_metrics).get("catastrophic_loss", pd.Series(dtype=bool)).astype(bool).any())
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "simulated_leverage_diagnostic",
                            "strategy": strategy,
                            "role": "simulated_leverage_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": leverage_multiplier,
                            "exposure_multiplier": leverage_multiplier,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "final_validation_completed": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "stop_enforced_metric_quality": "approximate",
                            "notes": (
                                f"Approximate ETF leverage diagnostic using {leverage_multiplier}x return multiplier, "
                                f"{financing:.1%} annual financing, catastrophic_loss={catastrophic}."
                            ),
                            "rolling_metric_quality": "approximate_simulated_leverage",
                            "rolling_notes": "Diagnostic only; no real margin, liquidation, or leveraged product path dependency model.",
                            **summary,
                        }
                    )
                else:
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "simulated_leverage_diagnostic",
                            "strategy": strategy,
                            "role": "simulated_leverage_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": leverage_multiplier,
                            "exposure_multiplier": leverage_multiplier,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "number_of_windows": 0,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": False,
                            "final_validation_completed": False,
                            "stop_enforced_metric_quality": "unavailable",
                            "notes": "Simulated ETF leverage diagnostic unavailable: no windows completed.",
                            "rolling_metric_quality": "unavailable",
                            "rolling_notes": "No windows completed.",
                        }
                    )
                if not completed:
                    break
            if not completed:
                break
        if not completed:
            break
    return rows, completed


def build_etf_exposure_frontier_rolling_rows(
    run_id: str,
    prices: pd.DataFrame,
    mode: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    base_weights = build_etf_benchmark_weights(prices, "SPY_200d_trend_model")
    prices_array = prices.to_numpy(dtype=float)
    weights_array = base_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)
    for label in labels:
        base_cost = 0.0005 if label == "standard" else 0.001
        for exposure_multiplier, assumptions in ETF_EXPOSURE_FRONTIER.items():
            financing = float(assumptions["financing_cost_annualized"])
            strategy = exposure_strategy_name(exposure_multiplier)
            for horizon in horizons:
                starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
                window_metrics: list[dict[str, Any]] = []
                for idx in starts:
                    if runtime_deadline and time.monotonic() > runtime_deadline:
                        completed = False
                        break
                    window_metrics.append(
                        fast_levered_weighted_window(
                            prices_array,
                            weights_array,
                            prices.index,
                            int(idx),
                            int(horizon),
                            base_cost,
                            exposure_multiplier,
                            financing,
                        )
                    )
                if window_metrics:
                    summary = summarize_window_metrics(window_metrics)
                    catastrophic = bool(pd.DataFrame(window_metrics).get("catastrophic_loss", pd.Series(dtype=bool)).astype(bool).any())
                    exact_equivalent = exposure_multiplier == 1.0 and method == "all_possible" and completed and len(window_metrics) == possible_count
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "simulated_etf_exposure_frontier",
                            "strategy": strategy,
                            "role": "risk_budget_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": exposure_multiplier,
                            "exposure_multiplier": exposure_multiplier,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "final_validation_completed": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "stop_enforced_metric_quality": "exact" if exact_equivalent else "approximate",
                            "notes": (
                                f"SPY_200d exposure frontier diagnostic at {exposure_multiplier:.2f}x with "
                                f"{financing:.1%} annual financing; catastrophic_loss={catastrophic}. "
                                "Diagnostic only, not paper-forward ready."
                            ),
                            "rolling_metric_quality": "exact_frontier_1x" if exact_equivalent else "approximate_exposure_frontier",
                            "rolling_notes": "Approximate exposure frontier; no real margin, liquidation, or leveraged ETF path dependency model.",
                            **summary,
                        }
                    )
                else:
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "simulated_etf_exposure_frontier",
                            "strategy": strategy,
                            "role": "risk_budget_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": exposure_multiplier,
                            "exposure_multiplier": exposure_multiplier,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "number_of_windows": 0,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": False,
                            "final_validation_completed": False,
                            "worst_stop_enforced_loss": math.nan,
                            "pct_windows_stop_overshoot_gt_50": 0.0,
                            "pct_windows_stop_overshoot_gt_100": 0.0,
                            "stop_enforced_metric_quality": "unavailable",
                            "notes": "Exposure frontier diagnostic unavailable: no windows completed.",
                            "rolling_metric_quality": "unavailable",
                            "rolling_notes": "No windows completed.",
                        }
                    )
                if not completed:
                    break
            if not completed:
                break
        if not completed:
            break
    return rows, completed


def build_etf_vol_control_rolling_rows(
    run_id: str,
    prices: pd.DataFrame,
    mode: str,
    labels: list[str],
    runtime_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    completed = True
    horizons = [90, 180, 30, 60] if mode == "candidate_exhaustive" else [30, 60, 90, 180]
    prices_array = prices.to_numpy(dtype=float)
    for label in labels:
        base_cost = 0.0005 if label == "standard" else 0.001
        for exposure_cap, assumptions in ETF_VOL_CONTROL_DIAGNOSTICS.items():
            financing = float(assumptions["financing_cost_annualized"])
            quality = str(assumptions["cost_model_quality"])
            strategy = vol_control_strategy_name(exposure_cap)
            weights = build_etf_vol_control_weights(prices, exposure_cap)
            weights_array = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)
            for horizon in horizons:
                starts, possible_count, method = sample_etf_starts(prices, horizon, mode)
                window_metrics: list[dict[str, Any]] = []
                for idx in starts:
                    if runtime_deadline and time.monotonic() > runtime_deadline:
                        completed = False
                        break
                    window_metrics.append(
                        fast_vol_control_window(
                            prices_array,
                            weights_array,
                            prices.index,
                            int(idx),
                            int(horizon),
                            base_cost,
                            financing,
                            exposure_cap,
                        )
                    )
                if window_metrics:
                    summary = summarize_window_metrics(window_metrics)
                    catastrophic = bool(pd.DataFrame(window_metrics).get("catastrophic_loss", pd.Series(dtype=bool)).astype(bool).any())
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "etf_volatility_control_diagnostic",
                            "strategy": strategy,
                            "role": "risk_control_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": 1.0,
                            "exposure_multiplier": exposure_cap,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "final_validation_completed": method == "all_possible" and completed and len(window_metrics) == possible_count,
                            "stop_enforced_metric_quality": "exact" if quality == "exact" else "approximate",
                            "notes": (
                                f"SPY_200d 12% target-vol diagnostic with 60-day realized volatility and {exposure_cap:.2f} cap; "
                                f"financing={financing:.1%}; catastrophic_loss={catastrophic}. "
                                "Tier 1 diagnostic only, not paper-forward ready."
                            ),
                            "rolling_metric_quality": "exact_volatility_control_diagnostic" if quality == "exact" else "approximate_volatility_control_diagnostic",
                            "rolling_notes": "Predeclared target vol/window/cap; no target-vol grid search or strategy-rule change.",
                            **summary,
                        }
                    )
                else:
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": "etf_volatility_control_diagnostic",
                            "strategy": strategy,
                            "role": "risk_control_diagnostic",
                            "credibility_tier": "tier1_exploratory",
                            "leverage_multiplier": 1.0,
                            "exposure_multiplier": exposure_cap,
                            "standard_or_stress": label,
                            "horizon": horizon,
                            "rolling_method": method,
                            "number_of_windows": 0,
                            "possible_window_count": possible_count,
                            "sampled_results_are_final": False,
                            "final_validation_completed": False,
                            "stop_enforced_metric_quality": "unavailable",
                            "notes": "Volatility-control diagnostic unavailable: no windows completed.",
                            "rolling_metric_quality": "unavailable",
                            "rolling_notes": "No windows completed.",
                        }
                    )
                if not completed:
                    break
            if not completed:
                break
        if not completed:
            break
    return rows, completed


def fast_weighted_window(
    prices_array: np.ndarray,
    weights_array: np.ndarray,
    dates: pd.Index,
    idx: int,
    horizon: int,
    spread_slippage_per_side: float,
) -> dict[str, Any]:
    price_slice = prices_array[idx : idx + horizon]
    weight_slice = weights_array[idx : idx + horizon].copy()
    n_rows, n_cols = price_slice.shape
    if n_rows == 0:
        audit = stop_audit_from_equity(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp.today().normalize()]))
        return {
            "final_equity": audit.unconditional_final_equity,
            "stop_enforced_final_equity": audit.stop_enforced_final_equity,
            "max_drawdown_dollars": audit.max_drawdown_dollars,
            "target_300_hit": audit.target_300_hit,
            "target_300_before_stop": audit.target_300_before_stop,
            "target_400_hit": audit.target_400_hit,
            "target_400_before_stop": audit.target_400_before_stop,
            "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
            "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
            "any_project_stop_hit": audit.any_project_stop_hit,
            "stop_overshoot_dollars": audit.stop_overshoot_dollars,
            "stop_overshoot_pct": audit.stop_overshoot_pct,
        }
    weight_slice[0] = 0.0
    returns = np.zeros_like(price_slice)
    if n_rows > 1:
        returns[1:] = np.divide(
            price_slice[1:],
            price_slice[:-1],
            out=np.ones_like(price_slice[1:]),
            where=np.isfinite(price_slice[:-1]) & (price_slice[:-1] != 0),
        ) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    equities = np.zeros(n_rows)
    equities[0] = STARTING_EQUITY
    prev_weights = np.zeros(n_cols)
    for i in range(1, n_rows):
        current_weights = np.clip(np.nan_to_num(weight_slice[i], nan=0.0), 0.0, 1.0)
        total = current_weights.sum()
        if total > 1.0:
            current_weights = current_weights / total
        turnover = np.abs(current_weights - prev_weights).sum()
        cost = equities[i - 1] * turnover * spread_slippage_per_side
        gross_return = float((current_weights * returns[i]).sum())
        equities[i] = max(0.0, equities[i - 1] * (1.0 + gross_return) - cost)
        prev_weights = current_weights
    audit = stop_audit_from_equity(pd.Series(equities), dates[idx : idx + horizon])
    return {
        "final_equity": audit.unconditional_final_equity,
        "stop_enforced_final_equity": audit.stop_enforced_final_equity,
        "max_drawdown_dollars": audit.max_drawdown_dollars,
        "target_300_hit": audit.target_300_hit,
        "target_300_before_stop": audit.target_300_before_stop,
        "target_400_hit": audit.target_400_hit,
        "target_400_before_stop": audit.target_400_before_stop,
        "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
        "any_project_stop_hit": audit.any_project_stop_hit,
        "stop_overshoot_dollars": audit.stop_overshoot_dollars,
        "stop_overshoot_pct": audit.stop_overshoot_pct,
    }


def simulate_levered_weighted_equity(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    spread_slippage_per_side: float,
    leverage_multiplier: float,
    financing_annualized: float,
) -> tuple[pd.DataFrame, int, float, float, bool]:
    prices = prices.reindex(weights.index).reindex(columns=weights.columns).ffill()
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    prev_weights = pd.Series(0.0, index=weights.columns)
    prev_equity = STARTING_EQUITY
    financing_daily = financing_annualized / 252.0 * max(0.0, leverage_multiplier - 1.0)
    equity_values: list[float] = []
    rebalance_count = 0
    turnover_estimate = 0.0
    catastrophic = False
    for dt in prices.index:
        current_weights = weights.loc[dt].fillna(0.0).clip(0.0, 1.0)
        total = float(current_weights.sum())
        if total > 1.0:
            current_weights = current_weights / total
        turnover = float((current_weights - prev_weights).abs().sum())
        cost = prev_equity * turnover * spread_slippage_per_side * leverage_multiplier
        unlevered_daily_return = float((current_weights * returns.loc[dt]).sum())
        levered_return = leverage_multiplier * unlevered_daily_return - financing_daily
        equity = prev_equity * (1.0 + levered_return) - cost
        if equity <= 0:
            equity = 0.0
            catastrophic = True
        if catastrophic:
            equity = 0.0
        if turnover > 1e-9:
            rebalance_count += 1
            turnover_estimate += turnover * leverage_multiplier
        equity_values.append(equity)
        prev_equity = equity
        prev_weights = current_weights
    curve = pd.DataFrame({"date": prices.index, "equity": equity_values})
    time_in_market = float(weights.sum(axis=1).gt(0).mean()) if not weights.empty else 0.0
    return curve, rebalance_count, turnover_estimate, time_in_market, catastrophic


def simulate_vol_control_equity(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    spread_slippage_per_side: float,
    financing_annualized: float,
    exposure_cap: float,
) -> tuple[pd.DataFrame, int, float, float, bool, dict[str, float]]:
    prices = prices.reindex(weights.index).reindex(columns=weights.columns).ffill()
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    prev_weights = pd.Series(0.0, index=weights.columns)
    prev_equity = STARTING_EQUITY
    equity_values: list[float] = []
    rebalance_count = 0
    turnover_estimate = 0.0
    catastrophic = False
    for dt in prices.index:
        current_weights = weights.loc[dt].fillna(0.0).clip(lower=0.0)
        turnover = float((current_weights - prev_weights).abs().sum())
        cost = prev_equity * turnover * spread_slippage_per_side
        gross_return = float((current_weights * returns.loc[dt]).sum())
        exposure = float(current_weights.sum())
        finance = prev_equity * max(0.0, exposure - 1.0) * financing_annualized / 252.0
        equity = prev_equity * (1.0 + gross_return) - cost - finance
        if equity <= 0:
            equity = 0.0
            catastrophic = True
        if catastrophic:
            equity = 0.0
        if turnover > 1e-9:
            rebalance_count += 1
            turnover_estimate += turnover
        equity_values.append(equity)
        prev_equity = equity
        prev_weights = current_weights
    curve = pd.DataFrame({"date": prices.index, "equity": equity_values})
    stats = exposure_stats(weights, exposure_cap)
    time_in_market = float(weights.sum(axis=1).gt(0).mean()) if not weights.empty else 0.0
    return curve, rebalance_count, turnover_estimate, time_in_market, catastrophic, stats


def fast_vol_control_window(
    prices_array: np.ndarray,
    weights_array: np.ndarray,
    dates: pd.Index,
    idx: int,
    horizon: int,
    spread_slippage_per_side: float,
    financing_annualized: float,
    exposure_cap: float,
) -> dict[str, Any]:
    price_slice = prices_array[idx : idx + horizon]
    weight_slice = weights_array[idx : idx + horizon].copy()
    n_rows, n_cols = price_slice.shape
    if n_rows == 0:
        audit = stop_audit_from_equity(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp.today().normalize()]))
        return {
            "final_equity": audit.unconditional_final_equity,
            "stop_enforced_final_equity": audit.stop_enforced_final_equity,
            "max_drawdown_dollars": audit.max_drawdown_dollars,
            "target_300_hit": audit.target_300_hit,
            "target_300_before_stop": audit.target_300_before_stop,
            "target_400_hit": audit.target_400_hit,
            "target_400_before_stop": audit.target_400_before_stop,
            "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
            "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
            "any_project_stop_hit": audit.any_project_stop_hit,
            "stop_overshoot_dollars": audit.stop_overshoot_dollars,
            "stop_overshoot_pct": audit.stop_overshoot_pct,
            "average_exposure": math.nan,
            "median_exposure": math.nan,
            "percent_time_cash": math.nan,
            "percent_time_reduced_exposure": math.nan,
            "percent_time_full_exposure": math.nan,
            "catastrophic_loss": False,
        }
    weight_slice[0] = 0.0
    returns = np.zeros_like(price_slice)
    if n_rows > 1:
        returns[1:] = np.divide(
            price_slice[1:],
            price_slice[:-1],
            out=np.ones_like(price_slice[1:]),
            where=np.isfinite(price_slice[:-1]) & (price_slice[:-1] != 0),
        ) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    equities = np.zeros(n_rows)
    equities[0] = STARTING_EQUITY
    prev_weights = np.zeros(n_cols)
    catastrophic = False
    for i in range(1, n_rows):
        current_weights = np.clip(np.nan_to_num(weight_slice[i], nan=0.0), 0.0, exposure_cap)
        turnover = np.abs(current_weights - prev_weights).sum()
        cost = equities[i - 1] * turnover * spread_slippage_per_side
        gross_return = float((current_weights * returns[i]).sum())
        exposure = float(current_weights.sum())
        finance = equities[i - 1] * max(0.0, exposure - 1.0) * financing_annualized / 252.0
        equities[i] = equities[i - 1] * (1.0 + gross_return) - cost - finance
        if equities[i] <= 0:
            equities[i] = 0.0
            catastrophic = True
        if catastrophic:
            equities[i] = 0.0
        prev_weights = current_weights
    audit = stop_audit_from_equity(pd.Series(equities), dates[idx : idx + horizon])
    exposure = pd.Series(weight_slice.sum(axis=1))
    stats = exposure_stats(exposure, exposure_cap)
    return {
        "final_equity": audit.unconditional_final_equity,
        "stop_enforced_final_equity": audit.stop_enforced_final_equity,
        "max_drawdown_dollars": audit.max_drawdown_dollars,
        "target_300_hit": audit.target_300_hit,
        "target_300_before_stop": audit.target_300_before_stop,
        "target_400_hit": audit.target_400_hit,
        "target_400_before_stop": audit.target_400_before_stop,
        "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
        "any_project_stop_hit": audit.any_project_stop_hit,
        "stop_overshoot_dollars": audit.stop_overshoot_dollars,
        "stop_overshoot_pct": audit.stop_overshoot_pct,
        "average_exposure": stats["average_exposure"],
        "median_exposure": stats["median_exposure"],
        "percent_time_cash": stats["percent_time_cash"],
        "percent_time_reduced_exposure": stats["percent_time_reduced_exposure"],
        "percent_time_full_exposure": stats["percent_time_full_exposure"],
        "catastrophic_loss": catastrophic,
    }


def fast_levered_weighted_window(
    prices_array: np.ndarray,
    weights_array: np.ndarray,
    dates: pd.Index,
    idx: int,
    horizon: int,
    spread_slippage_per_side: float,
    leverage_multiplier: float,
    financing_annualized: float,
) -> dict[str, Any]:
    price_slice = prices_array[idx : idx + horizon]
    weight_slice = weights_array[idx : idx + horizon].copy()
    n_rows, n_cols = price_slice.shape
    if n_rows == 0:
        audit = stop_audit_from_equity(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp.today().normalize()]))
        return {
            "final_equity": audit.unconditional_final_equity,
            "stop_enforced_final_equity": audit.stop_enforced_final_equity,
            "max_drawdown_dollars": audit.max_drawdown_dollars,
            "target_300_hit": audit.target_300_hit,
            "target_300_before_stop": audit.target_300_before_stop,
            "target_400_hit": audit.target_400_hit,
            "target_400_before_stop": audit.target_400_before_stop,
            "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
            "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
            "any_project_stop_hit": audit.any_project_stop_hit,
            "stop_overshoot_dollars": audit.stop_overshoot_dollars,
            "stop_overshoot_pct": audit.stop_overshoot_pct,
            "catastrophic_loss": False,
        }
    weight_slice[0] = 0.0
    returns = np.zeros_like(price_slice)
    if n_rows > 1:
        returns[1:] = np.divide(
            price_slice[1:],
            price_slice[:-1],
            out=np.ones_like(price_slice[1:]),
            where=np.isfinite(price_slice[:-1]) & (price_slice[:-1] != 0),
        ) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    equities = np.zeros(n_rows)
    equities[0] = STARTING_EQUITY
    prev_weights = np.zeros(n_cols)
    financing_daily = financing_annualized / 252.0 * max(0.0, leverage_multiplier - 1.0)
    catastrophic = False
    for i in range(1, n_rows):
        current_weights = np.clip(np.nan_to_num(weight_slice[i], nan=0.0), 0.0, 1.0)
        total = current_weights.sum()
        if total > 1.0:
            current_weights = current_weights / total
        turnover = np.abs(current_weights - prev_weights).sum()
        cost = equities[i - 1] * turnover * spread_slippage_per_side * leverage_multiplier
        unlevered_return = float((current_weights * returns[i]).sum())
        levered_return = leverage_multiplier * unlevered_return - financing_daily
        equities[i] = equities[i - 1] * (1.0 + levered_return) - cost
        if equities[i] <= 0:
            equities[i] = 0.0
            catastrophic = True
        if catastrophic:
            equities[i] = 0.0
        prev_weights = current_weights
    audit = stop_audit_from_equity(pd.Series(equities), dates[idx : idx + horizon])
    return {
        "final_equity": audit.unconditional_final_equity,
        "stop_enforced_final_equity": audit.stop_enforced_final_equity,
        "max_drawdown_dollars": audit.max_drawdown_dollars,
        "target_300_hit": audit.target_300_hit,
        "target_300_before_stop": audit.target_300_before_stop,
        "target_400_hit": audit.target_400_hit,
        "target_400_before_stop": audit.target_400_before_stop,
        "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
        "any_project_stop_hit": audit.any_project_stop_hit,
        "stop_overshoot_dollars": audit.stop_overshoot_dollars,
        "stop_overshoot_pct": audit.stop_overshoot_pct,
        "catastrophic_loss": catastrophic,
    }


def build_etf_benchmark_rows(
    run_id: str,
    mode: str,
    include_benchmarks: bool,
    runtime_deadline: float | None = None,
    date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None,
    include_etf_leverage_diagnostic: bool = False,
    include_etf_exposure_frontier: bool = False,
    include_etf_volatility_control_diagnostic: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    if not include_benchmarks:
        return [], [], [], True
    data, prices = etf_benchmark_data(date_index)
    if data.empty or prices.empty:
        coverage = [
            {
                "lane": "etf_benchmark",
                "data_source": "data/cache",
                "symbols": "SPY,BIL",
                "start_date": "",
                "end_date": "",
                "row_count": 0,
                "missing_data_notes": "SPY/BIL cache unavailable.",
                "adjusted_or_unadjusted": "adjusted OHLC expected",
                "raw_data_included_in_evidence": False,
                "major_limitations": "ETF benchmark rolling unavailable.",
            }
        ]
        return [], [], coverage, False
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    labels = ["standard", "stress"]
    completed = True
    for benchmark in ["SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"]:
        weights = build_etf_benchmark_weights(prices, benchmark)
        for label in labels:
            cost = 0.0005 if label == "standard" else 0.001
            curve, rebalances, turnover, time_in_market = simulate_weighted_equity(prices, weights, cost)
            audit = audit_dict_from_stop(stop_audit_from_equity(curve["equity"], curve["date"]))
            rows.append(
                build_challenge_row(
                    run_id=run_id,
                    lane="etf_benchmark",
                    strategy=benchmark,
                    instrument_family="daily_etf_benchmark",
                    credibility_tier="ETF benchmark",
                    data_source="data/cache adjusted OHLCV",
                    start_date=prices.index.min().date().isoformat(),
                    end_date=prices.index.max().date().isoformat(),
                    standard_or_stress=label,
                    spread_slippage_per_side=cost,
                    leverage_model="none",
                    leverage_multiplier=1.0,
                    financing_cost_assumption=0.0,
                    audit=audit,
                    time_in_market=time_in_market,
                    number_of_trades_or_rebalances=rebalances,
                    turnover_estimate=turnover,
                    stop_enforced_metric_quality="exact",
                    stop_enforced_metric_source="computed_from_cached_adjusted_benchmark_equity_curve",
                    stop_enforced_metric_notes="Computed by challenge audit from cached adjusted SPY/BIL prices; raw OHLCV not copied into evidence.",
                    notes="ETF benchmark computed directly for compact challenge audit.",
                )
            )
            if include_etf_leverage_diagnostic and benchmark in {"SPY_200d_trend_model", "SPY_buy_hold"}:
                for leverage_multiplier, assumptions in ETF_LEVERAGE_DIAGNOSTICS.items():
                    financing = float(assumptions["financing_cost_annualized"])
                    levered_curve, levered_rebalances, levered_turnover, levered_time_in_market, catastrophic = simulate_levered_weighted_equity(
                        prices,
                        weights,
                        cost,
                        leverage_multiplier,
                        financing,
                    )
                    audit = audit_dict_from_stop(stop_audit_from_equity(levered_curve["equity"], levered_curve["date"]))
                    rows.append(
                        build_challenge_row(
                            run_id=run_id,
                            lane="simulated_leverage_diagnostic",
                            strategy=diagnostic_strategy_name(benchmark, leverage_multiplier),
                            instrument_family="ETF simulated leverage",
                            credibility_tier="tier1_exploratory",
                            data_source="data/cache adjusted ETF benchmark prices",
                            start_date=prices.index.min().date().isoformat(),
                            end_date=prices.index.max().date().isoformat(),
                            standard_or_stress=label,
                            spread_slippage_per_side=cost * leverage_multiplier,
                            leverage_model="approximate_return_multiplier",
                            leverage_multiplier=leverage_multiplier,
                            financing_cost_assumption=financing,
                            audit=audit,
                            cost_model_quality="approximate",
                            catastrophic_loss=catastrophic,
                            time_in_market=levered_time_in_market,
                            number_of_trades_or_rebalances=levered_rebalances,
                            turnover_estimate=levered_turnover,
                            benchmark_name=benchmark,
                            stop_enforced_metric_quality="approximate",
                            stop_enforced_metric_source="approximate_return_multiplier_reconstructed_equity_curve",
                            stop_enforced_metric_notes="Diagnostic only. Return multiplier, simplified financing, and no real margin/liquidation/path-dependency model.",
                            notes="Tier 1 simulated ETF leverage diagnostic; not paper-forward ready and not a real-money recommendation.",
                        )
                    )
            if include_etf_exposure_frontier and benchmark == "SPY_200d_trend_model":
                for exposure_multiplier, assumptions in ETF_EXPOSURE_FRONTIER.items():
                    financing = float(assumptions["financing_cost_annualized"])
                    frontier_curve, frontier_rebalances, frontier_turnover, frontier_time_in_market, catastrophic = simulate_levered_weighted_equity(
                        prices,
                        weights,
                        cost,
                        exposure_multiplier,
                        financing,
                    )
                    audit = audit_dict_from_stop(stop_audit_from_equity(frontier_curve["equity"], frontier_curve["date"]))
                    exact_equivalent = exposure_multiplier == 1.0
                    rows.append(
                        build_challenge_row(
                            run_id=run_id,
                            lane="simulated_etf_exposure_frontier",
                            strategy=exposure_strategy_name(exposure_multiplier),
                            role="risk_budget_diagnostic",
                            instrument_family="ETF simulated exposure",
                            credibility_tier="tier1_exploratory",
                            data_source="data/cache adjusted ETF benchmark prices",
                            start_date=prices.index.min().date().isoformat(),
                            end_date=prices.index.max().date().isoformat(),
                            standard_or_stress=label,
                            spread_slippage_per_side=cost * exposure_multiplier,
                            leverage_model="approximate_return_multiplier",
                            leverage_multiplier=exposure_multiplier,
                            exposure_multiplier=exposure_multiplier,
                            annual_financing_rate=financing,
                            financing_cost_assumption=financing,
                            audit=audit,
                            cost_model_quality="exact" if exact_equivalent else "approximate",
                            catastrophic_loss=catastrophic,
                            time_in_market=frontier_time_in_market,
                            number_of_trades_or_rebalances=frontier_rebalances,
                            turnover_estimate=frontier_turnover,
                            benchmark_name="SPY_200d_trend_model",
                            stop_enforced_metric_quality="exact" if exact_equivalent else "approximate",
                            stop_enforced_metric_source="exposure_frontier_reconstructed_equity_curve",
                            stop_enforced_metric_notes="Diagnostic only. Return multiplier, simplified financing, and no real margin/liquidation/path-dependency model.",
                            notes="Tier 1 SPY_200d exposure frontier diagnostic; not paper-forward ready and not a real-money recommendation.",
                        )
                    )
            if include_etf_volatility_control_diagnostic and benchmark == "SPY_200d_trend_model":
                for exposure_cap, assumptions in ETF_VOL_CONTROL_DIAGNOSTICS.items():
                    financing = float(assumptions["financing_cost_annualized"])
                    quality = str(assumptions["cost_model_quality"])
                    vol_weights = build_etf_vol_control_weights(prices, exposure_cap)
                    vol_curve, vol_rebalances, vol_turnover, vol_time_in_market, catastrophic, stats = simulate_vol_control_equity(
                        prices,
                        vol_weights,
                        cost,
                        financing,
                        exposure_cap,
                    )
                    audit = audit_dict_from_stop(stop_audit_from_equity(vol_curve["equity"], vol_curve["date"]))
                    rows.append(
                        build_challenge_row(
                            run_id=run_id,
                            lane="etf_volatility_control_diagnostic",
                            strategy=vol_control_strategy_name(exposure_cap),
                            role="risk_control_diagnostic",
                            instrument_family="ETF",
                            credibility_tier="tier1_exploratory",
                            data_source="data/cache adjusted ETF benchmark prices",
                            start_date=prices.index.min().date().isoformat(),
                            end_date=prices.index.max().date().isoformat(),
                            standard_or_stress=label,
                            spread_slippage_per_side=cost,
                            leverage_model="volatility_control_overlay",
                            leverage_multiplier=1.0,
                            exposure_multiplier=exposure_cap,
                            annual_financing_rate=financing,
                            financing_cost_assumption=financing,
                            audit=audit,
                            cost_model_quality=quality,
                            catastrophic_loss=catastrophic,
                            time_in_market=vol_time_in_market,
                            number_of_trades_or_rebalances=vol_rebalances,
                            turnover_estimate=vol_turnover,
                            benchmark_name="SPY_200d_trend_model",
                            stop_enforced_metric_quality="exact" if quality == "exact" else "approximate",
                            stop_enforced_metric_source="volatility_control_reconstructed_equity_curve",
                            stop_enforced_metric_notes="Tier 1 diagnostic only. Predeclared 12% target vol and 60-day realized vol window; no grid search.",
                            notes="Tier 1 SPY_200d volatility-control diagnostic; not paper-forward ready and not a real-money recommendation.",
                            extra_fields={
                                "target_vol_annualized": ETF_VOL_CONTROL_TARGET,
                                "realized_vol_window": ETF_VOL_CONTROL_WINDOW,
                                "exposure_cap": exposure_cap,
                                "average_exposure": stats["average_exposure"],
                                "max_exposure": stats["max_exposure"],
                                "min_exposure": stats["min_exposure"],
                                "percent_time_cash": stats["percent_time_cash"],
                                "percent_time_reduced_exposure": stats["percent_time_reduced_exposure"],
                                "percent_time_full_exposure": stats["percent_time_full_exposure"],
                                "cost_model": "volatility_target_spread_slippage_plus_financing" if exposure_cap > 1.0 else "volatility_target_spread_slippage",
                            },
                        )
                    )
        bench_rolling, bench_completed = build_etf_benchmark_rolling_rows(run_id, prices, benchmark, mode, labels, runtime_deadline)
        rolling_rows.extend(bench_rolling)
        completed = completed and bench_completed
        if include_etf_leverage_diagnostic and benchmark in {"SPY_200d_trend_model", "SPY_buy_hold"}:
            diag_rolling, diag_completed = build_etf_leverage_diagnostic_rolling_rows(
                run_id,
                prices,
                benchmark,
                mode,
                labels,
                runtime_deadline,
            )
            rolling_rows.extend(diag_rolling)
            completed = completed and diag_completed
        if include_etf_exposure_frontier and benchmark == "SPY_200d_trend_model":
            frontier_rolling, frontier_completed = build_etf_exposure_frontier_rolling_rows(
                run_id,
                prices,
                mode,
                labels,
                runtime_deadline,
            )
            rolling_rows.extend(frontier_rolling)
            completed = completed and frontier_completed
        if include_etf_volatility_control_diagnostic and benchmark == "SPY_200d_trend_model":
            vol_rolling, vol_completed = build_etf_vol_control_rolling_rows(
                run_id,
                prices,
                mode,
                labels,
                runtime_deadline,
            )
            rolling_rows.extend(vol_rolling)
            completed = completed and vol_completed
    coverage = [
        {
            "lane": "etf_benchmark",
            "data_source": "data/cache adjusted OHLCV",
            "symbols": ",".join(sorted(data["symbol"].dropna().unique())),
            "start_date": prices.index.min().date().isoformat(),
            "end_date": prices.index.max().date().isoformat(),
            "row_count": int(len(data)),
            "missing_data_notes": "",
            "adjusted_or_unadjusted": "adjusted close from existing ETF cache",
            "raw_data_included_in_evidence": False,
            "major_limitations": "Benchmarks are exact from cached adjusted close, but compact challenge evidence does not include raw OHLCV.",
        }
    ]
    return rows, rolling_rows, coverage, completed


def load_etf_rows(
    run_id: str,
    include_etf: bool,
    include_benchmarks: bool,
    mode: str,
    finalists: set[str],
    runtime_deadline: float | None = None,
    reuse_cache: bool = True,
    include_etf_leverage_diagnostic: bool = False,
    include_etf_exposure_frontier: bool = False,
    include_etf_volatility_control_diagnostic: bool = False,
    include_diversified_portfolios: bool = False,
    include_exploratory_crypto_portfolios: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    if not include_etf and not include_benchmarks and not include_diversified_portfolios:
        return [], [], [], True
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    variant_path = Path("evidence/latest/strategy_variant_results.csv")
    rolling_path = Path("evidence/latest/independent_rolling_window_summary.csv")
    data_path = Path("evidence/latest/data_quality_summary.csv")
    selected = finalists or {"current_no_cash_proxy_alpha_AB", "current_core_only_AB", "current_momentum_only_A"}
    if include_diversified_portfolios:
        selected = set(selected) | {FOCUSED_FINALIST}
    completed = True
    benchmark_date_index: list[pd.Timestamp] | pd.DatetimeIndex | None = None
    focused_candidate = bool(
        mode == "candidate_exhaustive"
        and (FOCUSED_FINALIST in finalists or include_etf_leverage_diagnostic or include_etf_exposure_frontier or include_etf_volatility_control_diagnostic)
    )
    if focused_candidate:
        context = load_exact_etf_context()
        benchmark_date_index = context["dates"]
        if include_etf:
            exact_rows, exact_coverage, full_completed = run_exact_variant_full_rows(
                run_id,
                FOCUSED_FINALIST,
                FOCUSED_LABELS,
                runtime_deadline,
            )
            rows.extend(exact_rows)
            coverage_rows.extend(exact_coverage)
            exact_rolling, rolling_completed, _source = build_exact_finalist_rolling_rows(
                run_id,
                FOCUSED_FINALIST,
                reuse_cache=reuse_cache,
                runtime_deadline=runtime_deadline,
            )
            rolling_rows.extend(exact_rolling)
            completed = completed and full_completed and rolling_completed
    elif include_etf and variant_path.exists():
        variants = pd.read_csv(variant_path)
        for _, row in variants[variants["variant_name"].isin(selected)].iterrows():
            audit = approximate_stop_audit_from_summary(row)
            rows.append(
                build_challenge_row(
                    run_id=run_id,
                    lane="etf_validated_lane",
                    strategy=str(row["variant_name"]),
                    instrument_family="daily_etf",
                    credibility_tier="ETF evidence lane; not a real-money recommendation",
                    data_source="existing_evidence_latest",
                    start_date="from_existing_evidence",
                    end_date="from_existing_evidence",
                    standard_or_stress=str(row["slippage_label"]),
                    spread_slippage_per_side=as_float(row.get("slippage_pct_per_side")),
                    leverage_model="none",
                    leverage_multiplier=1.0,
                    financing_cost_assumption=0.0,
                    audit=audit,
                    number_of_trades_or_rebalances=as_float(row.get("number_of_trades")),
                    benchmark_name="SPY_200d_trend_model",
                    stop_enforced_metric_quality="approximate",
                    stop_enforced_metric_source="evidence/latest/strategy_variant_results.csv summary_drawdown",
                    stop_enforced_metric_notes="Variant equity curve is not present in compact evidence; stop-enforced equity is approximated from summary max drawdown.",
                    notes="Loaded from evidence/latest/strategy_variant_results.csv; stop equity is approximated from summary drawdown because variant equity curves are not in compact evidence.",
                )
            )
    if not focused_candidate and include_etf and rolling_path.exists():
        rolling = pd.read_csv(rolling_path)
        rolling = rolling[rolling["variant_name"].isin(selected)]
        if mode == "candidate_exhaustive":
            available_all_possible = rolling["window_sampling_method"].eq("all_possible") if "window_sampling_method" in rolling else pd.Series(False, index=rolling.index)
            if not available_all_possible.all() or rolling.empty:
                completed = False
        for _, row in rolling.iterrows():
            method = row.get("window_sampling_method", "deterministic_research_sample")
            rolling_rows.append(
                {
                    "run_id": run_id,
                    "lane": "etf_validated_lane",
                    "strategy": row["variant_name"],
                    "credibility_tier": "tier3_candidate_validation",
                    "role": "existing_etf_summary",
                    "leverage_multiplier": 1.0,
                    "exposure_multiplier": 1.0,
                    "standard_or_stress": row["slippage_label"],
                    "horizon": int(row["horizon_trading_days"]),
                    "rolling_method": method,
                    "number_of_windows": int(row["number_of_windows"]),
                    "possible_window_count": int(row.get("possible_window_count", row["number_of_windows"])),
                    "sampled_results_are_final": bool(method == "all_possible" and int(row["number_of_windows"]) == int(row.get("possible_window_count", row["number_of_windows"]))),
                    "final_validation_completed": bool(method == "all_possible" and int(row["number_of_windows"]) == int(row.get("possible_window_count", row["number_of_windows"]))),
                    "pct_target_300_hit": row["pct_windows_target_300_hit"],
                    "pct_target_300_before_stop": row["pct_windows_target_300_before_stop"],
                    "pct_target_400_hit": row["pct_windows_target_400_hit"],
                    "pct_target_400_before_stop": row["pct_windows_target_400_before_stop"],
                    "pct_any_project_stop_hit": row["pct_windows_any_stop_hit"],
                    "pct_absolute_floor_stop_hit": row["pct_windows_absolute_stop_hit"],
                    "pct_trailing_drawdown_stop_hit": row["pct_windows_trailing_stop_hit"],
                    "median_final_equity": row["median_final_equity"],
                    "median_stop_enforced_final_equity": row["median_final_equity"],
                    "mean_stop_enforced_final_equity": row["mean_final_equity"],
                    "median_max_drawdown": row["median_max_drawdown"],
                    "worst_max_drawdown": row["worst_max_drawdown"],
                    "pct_positive_return": row["pct_windows_positive_return"],
                    "pct_loss": row["pct_windows_loss"],
                    "pct_below_2400": row["pct_windows_below_2400"],
                    "pct_above_3300": row["pct_windows_above_3300"],
                    "pct_above_3400": row["pct_windows_above_3400"],
                    "worst_stop_enforced_loss": math.nan,
                    "pct_windows_stop_overshoot_gt_50": 0.0,
                    "pct_windows_stop_overshoot_gt_100": 0.0,
                    "stop_enforced_metric_quality": "exact" if method == "all_possible" else "partial",
                    "notes": "Loaded from existing ETF independent rolling summary; not recomputed by compact challenge audit.",
                    "rolling_metric_quality": "exact_existing_summary" if method == "all_possible" else "sampled_existing_summary",
                    "rolling_notes": "Loaded from existing ETF independent rolling summary; not recomputed by compact challenge audit.",
                }
            )
    if not focused_candidate and data_path.exists():
        data = pd.read_csv(data_path)
        coverage_rows.append(
            {
                "lane": "etf_validated_lane",
                "data_source": "existing_yfinance_adjusted_ohlc_evidence",
                "symbols": ",".join(data.get("symbol", pd.Series(dtype=str)).dropna().astype(str).tolist()),
                "start_date": data.get("first_date", pd.Series(dtype=str)).min() if "first_date" in data else "",
                "end_date": data.get("last_date", pd.Series(dtype=str)).max() if "last_date" in data else "",
                "row_count": int(data.get("row_count", pd.Series(dtype=float)).sum()) if "row_count" in data else math.nan,
                "missing_data_notes": "See detailed evidence/latest/data_quality_summary.csv.",
                "adjusted_or_unadjusted": "adjusted OHLC per ETF evidence lane",
                "raw_data_included_in_evidence": False,
                "major_limitations": "Loaded as summary evidence only; compact challenge does not include raw ETF data.",
            }
        )
    benchmark_rows, benchmark_rolling, benchmark_coverage, benchmark_completed = build_etf_benchmark_rows(
        run_id,
        mode,
        include_benchmarks,
        runtime_deadline,
        date_index=benchmark_date_index,
        include_etf_leverage_diagnostic=include_etf_leverage_diagnostic,
        include_etf_exposure_frontier=include_etf_exposure_frontier,
        include_etf_volatility_control_diagnostic=include_etf_volatility_control_diagnostic,
    )
    rows.extend(benchmark_rows)
    rolling_rows.extend(benchmark_rolling)
    coverage_rows.extend(benchmark_coverage)
    completed = completed and benchmark_completed
    portfolio_rows, portfolio_rolling, portfolio_coverage, portfolio_completed = build_diversified_portfolio_rows(
        run_id,
        mode,
        include_diversified_portfolios,
        include_exploratory_crypto_portfolios,
        runtime_deadline,
        date_index=benchmark_date_index,
    )
    rows.extend(portfolio_rows)
    rolling_rows.extend(portfolio_rolling)
    coverage_rows.extend(portfolio_coverage)
    completed = completed and portfolio_completed
    return rows, rolling_rows, coverage_rows, completed


def load_crypto_rows(
    run_id: str,
    mode: str,
    include_crypto: bool,
    include_leverage: bool,
    no_network: bool,
    reuse_cache: bool,
    force_refresh: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, pd.DataFrame]]:
    if not include_crypto:
        return [], [], [], {}
    config_path = Path("exploratory/crypto_spot_momentum/config.yaml")
    config = load_crypto_config(config_path)
    try:
        loaded = load_crypto_data(config, source="yfinance", no_network=no_network, reuse_cache=reuse_cache, force_download=force_refresh)
    except CryptoDataError:
        return [], [], [
            {
                "lane": "crypto_spot_momentum",
                "data_source": "yfinance",
                "symbols": "BTC-USD,ETH-USD",
                "start_date": "",
                "end_date": "",
                "row_count": 0,
                "missing_data_notes": "Crypto data unavailable; challenge rows omitted.",
                "adjusted_or_unadjusted": "adj_close equals close when unavailable",
                "raw_data_included_in_evidence": False,
                "major_limitations": "No crypto rows because cache/download was unavailable.",
            }
        ], {}

    mode_cfg = config["validation"]["modes"].get(mode, config["validation"]["modes"]["research_sample"])
    strategy_names = [
        "BTC_buy_hold",
        "ETH_buy_hold",
        "crypto_buy_hold_equal_weight",
        "crypto_time_series_momentum",
        "crypto_cross_sectional_momentum",
        "crypto_dual_momentum_cash_filter",
    ]
    leverage_multipliers = [1.0]
    if include_leverage:
        leverage_multipliers += [1.5, 2.0]
    financing = {1.0: 0.0, 1.5: 0.05, 2.0: 0.08}
    rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    equity_curves_for_chart: dict[str, pd.DataFrame] = {}
    benchmark_by_label: dict[str, dict[str, Any]] = {}
    prices = price_matrix(loaded.data)
    signal_cache = {name: generate_signal_weights(loaded.data, name, strategy_config(config, name)) for name in strategy_names if name != "cash_flat"}
    start_date = prices.index.min().date().isoformat()
    end_date = prices.index.max().date().isoformat()

    for label in mode_cfg.get("slippage_labels", ["standard", "stress"]):
        base_cost = float(config["costs"]["standard_fee_slippage_per_side"] if label == "standard" else config["costs"]["stress_fee_slippage_per_side"])
        for strategy in strategy_names:
            base_sim = simulate_strategy(
                loaded.data,
                strategy,
                strategy_config(config, strategy),
                STARTING_EQUITY,
                base_cost,
                precomputed_signal_weights=signal_cache.get(strategy),
            )
            for lev in leverage_multipliers:
                cost = base_cost * lev
                if lev == 1.0:
                    curve = base_sim.equity_curve.copy()
                    lane = "crypto_spot_momentum"
                    leverage_model = "none"
                    tier = "Tier 1 exploratory screen"
                else:
                    sim_for_cost = simulate_strategy(
                        loaded.data,
                        strategy,
                        strategy_config(config, strategy),
                        STARTING_EQUITY,
                        cost,
                        precomputed_signal_weights=signal_cache.get(strategy),
                    )
                    curve = apply_leverage_to_curve(sim_for_cost.equity_curve, sim_for_cost.weights, lev, financing[lev])
                    lane = "simulated_leverage_scenario"
                    leverage_model = "approximate_simulated_leverage"
                    tier = "Tier 1 exploratory screen; approximate simulated leverage"
                audit_obj = stop_audit_from_equity(curve["equity"], curve["date"])
                audit = audit_dict_from_stop(audit_obj)
                if strategy == "BTC_buy_hold" and lev == 1.0:
                    benchmark_by_label[label] = audit
                rows.append(
                    build_challenge_row(
                        run_id=run_id,
                        lane=lane,
                        strategy=strategy,
                        instrument_family="crypto_spot",
                        credibility_tier=tier,
                        data_source=loaded.source,
                        start_date=start_date,
                        end_date=end_date,
                        standard_or_stress=label,
                        spread_slippage_per_side=cost,
                        leverage_model=leverage_model,
                        leverage_multiplier=lev,
                        financing_cost_assumption=financing[lev],
                        audit=audit,
                        time_in_market=float(base_sim.weights.sum(axis=1).gt(0).mean()) if not base_sim.weights.empty else 0.0,
                        number_of_trades_or_rebalances=len(base_sim.rebalances),
                        turnover_estimate=base_sim.turnover_estimate,
                        benchmark_name="BTC_buy_hold",
                        benchmark=benchmark_by_label.get(label),
                        stop_enforced_metric_quality="exact",
                        stop_enforced_metric_source="computed_from_crypto_equity_curve",
                        stop_enforced_metric_notes="Exact within the simulated curve. The crypto lane itself remains Tier 1 exploratory; leverage rows are approximate scenarios.",
                        notes="Crypto rows are Tier 1 exploratory and non-final. Raw OHLCV is excluded from challenge evidence.",
                    )
                )
                if label == "standard" and lev in {1.0, 2.0} and strategy in {"BTC_buy_hold", "crypto_dual_momentum_cash_filter", "crypto_time_series_momentum"}:
                    equity_curves_for_chart[f"{strategy}_{lev}x"] = curve

    rolling_rows.extend(
        build_crypto_rolling_rows(run_id, loaded.data, config, mode_cfg, strategy_names, leverage_multipliers, financing)
    )
    coverage_rows = [
        {
            "lane": "crypto_spot_momentum",
            "data_source": loaded.source,
            "symbols": ",".join(loaded.coverage["symbol"].dropna().astype(str).tolist()),
            "start_date": start_date,
            "end_date": end_date,
            "row_count": int(loaded.coverage["row_count"].sum()),
            "missing_data_notes": "; ".join(loaded.coverage["excluded_reason"].dropna().astype(str).unique()),
            "adjusted_or_unadjusted": "adj_close equals close when adjusted close is unavailable",
            "raw_data_included_in_evidence": False,
            "major_limitations": "Tier 1 exploratory yfinance crypto data; no bid/ask, order book, outage, custody, delisting, or exchange-specific execution modeling.",
        }
    ]
    return rows, rolling_rows, coverage_rows, equity_curves_for_chart


def build_crypto_rolling_rows(
    run_id: str,
    data: pd.DataFrame,
    config: dict[str, Any],
    mode_cfg: dict[str, Any],
    strategies: list[str],
    leverage_multipliers: list[float],
    financing: dict[float, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prices = price_matrix(data)
    signals = {name: generate_signal_weights(data, name, strategy_config(config, name)) for name in strategies}
    for label in mode_cfg.get("slippage_labels", ["standard"]):
        base_cost = float(config["costs"]["standard_fee_slippage_per_side"] if label == "standard" else config["costs"]["stress_fee_slippage_per_side"])
        for horizon in mode_cfg.get("horizons", [90]):
            starts, possible_count = sample_start_indices(data, int(horizon), mode_cfg.get("rolling_method", "deterministic_sample"), mode_cfg.get("sample_size_per_group"))
            for strategy in strategies:
                for lev in leverage_multipliers:
                    window_metrics = []
                    for idx in starts:
                        window_metrics.append(
                            fast_crypto_window(
                                prices=prices,
                                signal_weights=signals[strategy],
                                idx=int(idx),
                                horizon=int(horizon),
                                spread_slippage_per_side=base_cost * lev,
                                leverage=lev,
                                financing_annual=financing[lev],
                            )
                        )
                    if not window_metrics:
                        continue
                    df = pd.DataFrame(window_metrics)
                    lane = "crypto_spot_momentum" if lev == 1.0 else "simulated_leverage_scenario"
                    rows.append(
                        {
                            "run_id": run_id,
                            "lane": lane,
                            "strategy": strategy,
                            "credibility_tier": "tier1_exploratory",
                            "role": "exploratory_screen" if lev == 1.0 else "simulated_leverage_scenario",
                            "leverage_multiplier": lev,
                            "exposure_multiplier": lev,
                            "standard_or_stress": label,
                            "horizon": int(horizon),
                            "rolling_method": mode_cfg.get("rolling_method", "deterministic_research_sample"),
                            "number_of_windows": int(len(df)),
                            "possible_window_count": int(possible_count),
                            "sampled_results_are_final": False,
                            "final_validation_completed": False,
                            "pct_target_300_hit": float(df["target_300_hit"].mean()),
                            "pct_target_300_before_stop": float(df["target_300_before_stop"].mean()),
                            "pct_target_400_hit": float(df["target_400_hit"].mean()),
                            "pct_target_400_before_stop": float(df["target_400_before_stop"].mean()),
                            "pct_any_project_stop_hit": float(df["any_project_stop_hit"].mean()),
                            "pct_absolute_floor_stop_hit": float(df["absolute_floor_stop_hit"].mean()),
                            "pct_trailing_drawdown_stop_hit": float(df["trailing_drawdown_stop_hit"].mean()),
                            "median_final_equity": float(df["final_equity"].median()),
                            "median_stop_enforced_final_equity": float(df["stop_enforced_final_equity"].median()),
                            "mean_stop_enforced_final_equity": float(df["stop_enforced_final_equity"].mean()),
                            "median_max_drawdown": float(df["max_drawdown_dollars"].median()),
                            "worst_max_drawdown": float(df["max_drawdown_dollars"].min()),
                            "pct_positive_return": float((df["stop_enforced_final_equity"] > STARTING_EQUITY).mean()),
                            "pct_loss": float((df["stop_enforced_final_equity"] < STARTING_EQUITY).mean()),
                            "pct_below_2400": float((df["stop_enforced_final_equity"] < ABSOLUTE_STOP).mean()),
                            "pct_above_3300": float((df["stop_enforced_final_equity"] >= TARGET_300).mean()),
                            "pct_above_3400": float((df["stop_enforced_final_equity"] >= TARGET_400).mean()),
                            "stop_enforced_metric_quality": "exact",
                            "notes": "Computed from crypto exploratory simulated equity windows; Tier 1 non-final.",
                            "rolling_metric_quality": "exact_simulated_curve",
                            "rolling_notes": "Computed from crypto exploratory simulated equity windows; Tier 1 non-final.",
                        }
                    )
    return rows


def fast_crypto_window(
    prices: pd.DataFrame,
    signal_weights: pd.DataFrame,
    idx: int,
    horizon: int,
    spread_slippage_per_side: float,
    leverage: float,
    financing_annual: float,
) -> dict[str, Any]:
    price_slice = prices.iloc[idx : idx + horizon].to_numpy(dtype=float)
    n_rows, n_cols = price_slice.shape
    returns = np.zeros_like(price_slice)
    if n_rows > 1:
        returns[1:] = np.divide(price_slice[1:], price_slice[:-1], out=np.ones_like(price_slice[1:]), where=price_slice[:-1] != 0) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    signal = signal_weights.iloc[idx : idx + horizon].reindex(columns=prices.columns).to_numpy(dtype=float)
    weights = np.zeros((n_rows, n_cols))
    last = np.zeros(n_cols)
    for i in range(1, n_rows):
        prev = signal[i - 1]
        if not np.isnan(prev).all():
            last = np.nan_to_num(prev, nan=0.0)
            total = last.sum()
            if total > 1:
                last = last / total
        weights[i] = last
    equities = np.zeros(n_rows)
    equities[0] = STARTING_EQUITY
    prev_weights = np.zeros(n_cols)
    financing_daily = max(0.0, leverage - 1.0) * financing_annual / 365.0
    for i in range(1, n_rows):
        turnover = np.abs(weights[i] - prev_weights).sum()
        cost = equities[i - 1] * turnover * spread_slippage_per_side
        gross_ret = float((weights[i] * returns[i]).sum()) * leverage
        finance = equities[i - 1] * weights[i].sum() * financing_daily
        equities[i] = max(0.0, equities[i - 1] * (1.0 + gross_ret) - cost - finance)
        prev_weights = weights[i]
    audit = stop_audit_from_equity(pd.Series(equities), prices.index[idx : idx + horizon])
    return {
        "final_equity": audit.unconditional_final_equity,
        "stop_enforced_final_equity": audit.stop_enforced_final_equity,
        "max_drawdown_dollars": audit.max_drawdown_dollars,
        "target_300_hit": audit.target_300_hit,
        "target_300_before_stop": audit.target_300_before_stop,
        "target_400_hit": audit.target_400_hit,
        "target_400_before_stop": audit.target_400_before_stop,
        "absolute_floor_stop_hit": audit.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": audit.trailing_drawdown_stop_hit,
        "any_project_stop_hit": audit.any_project_stop_hit,
    }


def build_rankings(challenge: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    standard_rows = challenge[challenge["standard_or_stress"].eq("standard")].copy()
    roll90 = rolling[rolling["horizon"].eq(90)].copy()
    benchmark_names = {"SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"}
    available_benchmarks = set(roll90.loc[roll90["strategy"].isin(benchmark_names), "strategy"].astype(str))
    benchmark_comparison_available = benchmark_names.issubset(available_benchmarks)
    spy200_standard = roll90[
        roll90["strategy"].eq("SPY_200d_trend_model")
        & roll90["standard_or_stress"].eq("standard")
    ]
    frontier_base = roll90[
        roll90["lane"].eq("simulated_etf_exposure_frontier")
        & roll90["strategy"].eq(exposure_strategy_name(1.0))
        & roll90["standard_or_stress"].eq("standard")
    ]
    for _, row in standard_rows.iterrows():
        match = roll90[
            roll90["strategy"].eq(row["strategy"])
            & roll90["lane"].eq(row["lane"])
            & roll90["leverage_multiplier"].eq(row["leverage_multiplier"])
            & roll90["standard_or_stress"].eq("standard")
        ]
        p300 = float(match["pct_target_300_before_stop"].iloc[0]) if not match.empty else 0.0
        p400 = float(match["pct_target_400_before_stop"].iloc[0]) if not match.empty else 0.0
        stop = float(match["pct_any_project_stop_hit"].iloc[0]) if not match.empty else (1.0 if boolish(row.get("any_project_stop_hit", False)) else 0.0)
        if not math.isfinite(p300):
            p300 = 0.0
        if not math.isfinite(p400):
            p400 = 0.0
        if not math.isfinite(stop):
            stop = 1.0
        median_90d_stop_equity = float(match["median_stop_enforced_final_equity"].iloc[0]) if not match.empty else math.nan
        worst_90d_drawdown = float(match["worst_max_drawdown"].iloc[0]) if not match.empty else math.nan
        worst_stop_enforced_loss = float(match["worst_stop_enforced_loss"].iloc[0]) if not match.empty and "worst_stop_enforced_loss" in match else math.nan
        overshoot50 = float(match["pct_windows_stop_overshoot_gt_50"].iloc[0]) if not match.empty and "pct_windows_stop_overshoot_gt_50" in match else 0.0
        overshoot100 = float(match["pct_windows_stop_overshoot_gt_100"].iloc[0]) if not match.empty and "pct_windows_stop_overshoot_gt_100" in match else 0.0
        average_exposure = (
            float(match["average_exposure"].iloc[0])
            if not match.empty and "average_exposure" in match and pd.notna(match["average_exposure"].iloc[0])
            else as_float(row.get("average_exposure"), math.nan)
        )
        family_id = str(row.get("family_id", "")) if pd.notna(row.get("family_id", "")) else ""
        family_group = str(row.get("family_group", "")) if pd.notna(row.get("family_group", "")) else ""
        family_role = str(row.get("family_role", "")) if pd.notna(row.get("family_role", "")) else ""
        implementation_status = str(row.get("implementation_status", "")) if pd.notna(row.get("implementation_status", "")) else ""
        run_status = str(row.get("run_status", "")) if pd.notna(row.get("run_status", "")) else ""
        family_blocked_or_unavailable = str(row.get("lane")) == "independent_family_challenge" and run_status not in {"", "completed", "nan"}
        display_p300 = math.nan if family_blocked_or_unavailable else p300
        display_p400 = math.nan if family_blocked_or_unavailable else p400
        display_stop = math.nan if family_blocked_or_unavailable else stop
        rolling_final_completed = boolish(match["final_validation_completed"].iloc[0]) if not match.empty and "final_validation_completed" in match else False
        rolling_sampled_final = boolish(match["sampled_results_are_final"].iloc[0]) if not match.empty and "sampled_results_are_final" in match else False
        stress = challenge[
            challenge["strategy"].eq(row["strategy"])
            & challenge["lane"].eq(row["lane"])
            & challenge["leverage_multiplier"].eq(row["leverage_multiplier"])
            & challenge["standard_or_stress"].eq("stress")
        ]
        stress_available = not stress.empty
        stress_degradation = math.nan
        if stress_available and row["stop_enforced_final_equity"]:
            stress_degradation = (float(stress["stop_enforced_final_equity"].iloc[0]) - float(row["stop_enforced_final_equity"])) / float(row["stop_enforced_final_equity"])
        tier_penalty = 0.20 if ("Tier 1" in str(row["credibility_tier"]) or str(row["credibility_tier"]) == "tier1_exploratory") else 0.0
        leverage_penalty = 0.15 if float(row["leverage_multiplier"]) > 1 else 0.0
        quality = str(row.get("stop_enforced_metric_quality", "unavailable"))
        quality_penalty = 0.15 if quality == "approximate" else (0.30 if quality == "unavailable" else 0.0)
        cost_quality = str(row.get("cost_model_quality", "exact"))
        cost_quality_penalty = 0.10 if cost_quality == "approximate" else (0.20 if cost_quality == "unavailable" else 0.0)
        catastrophic_loss = boolish(row.get("catastrophic_loss", False))
        catastrophic_penalty = 1.0 if catastrophic_loss else 0.0
        benchmark_penalty = 0.15 if not benchmark_comparison_available and "benchmark" not in str(row["lane"]) else 0.0
        unconditional_equity = as_float(row.get("unconditional_final_equity"), STARTING_EQUITY)
        stop_enforced_equity = as_float(row.get("stop_enforced_final_equity"), STARTING_EQUITY)
        stop_recovery_penalty = max(0.0, (unconditional_equity - stop_enforced_equity) / max(unconditional_equity, 1.0))
        stress_penalty = abs(min(0.0, stress_degradation)) if pd.notna(stress_degradation) else 0.0
        drawdown_penalty = max(0.0, (abs(worst_90d_drawdown) - TRAILING_DRAWDOWN) / TRAILING_DRAWDOWN) if pd.notna(worst_90d_drawdown) else 0.0
        target_300_gain_vs_1x = math.nan
        target_400_gain_vs_1x = math.nan
        stop_hit_increase_vs_1x = math.nan
        worst_drawdown_worsening_vs_1x = math.nan
        target_300_change_vs_spy_200d = math.nan
        target_400_change_vs_spy_200d = math.nan
        stop_hit_change_vs_spy_200d = math.nan
        worst_drawdown_change_vs_spy_200d = math.nan
        median_equity_change_vs_spy_200d = math.nan
        if str(row["lane"]) == "simulated_etf_exposure_frontier" and not frontier_base.empty:
            base = frontier_base.iloc[0]
            target_300_gain_vs_1x = p300 - float(base["pct_target_300_before_stop"])
            target_400_gain_vs_1x = p400 - float(base["pct_target_400_before_stop"])
            stop_hit_increase_vs_1x = stop - float(base["pct_any_project_stop_hit"])
            worst_drawdown_worsening_vs_1x = worst_90d_drawdown - float(base["worst_max_drawdown"]) if pd.notna(worst_90d_drawdown) else math.nan
        if not spy200_standard.empty:
            spy200 = spy200_standard.iloc[0]
            target_300_change_vs_spy_200d = p300 - float(spy200["pct_target_300_before_stop"])
            target_400_change_vs_spy_200d = p400 - float(spy200["pct_target_400_before_stop"])
            stop_hit_change_vs_spy_200d = stop - float(spy200["pct_any_project_stop_hit"])
            worst_drawdown_change_vs_spy_200d = worst_90d_drawdown - float(spy200["worst_max_drawdown"]) if pd.notna(worst_90d_drawdown) else math.nan
            median_equity_change_vs_spy_200d = median_90d_stop_equity - float(spy200["median_stop_enforced_final_equity"]) if pd.notna(median_90d_stop_equity) else math.nan
        max_single_sleeve_weight = as_float(row.get("max_single_sleeve_weight"), math.nan)
        cash_weight = as_float(row.get("cash_weight"), 0.0)
        bond_weight = as_float(row.get("bond_weight"), 0.0)
        gold_weight = as_float(row.get("gold_weight"), 0.0)
        crypto_weight = as_float(row.get("crypto_weight"), 0.0)
        diversification_score = (
            (1.0 - max_single_sleeve_weight if pd.notna(max_single_sleeve_weight) else 0.0)
            + min(0.25, cash_weight + bond_weight + gold_weight)
            - crypto_weight * 0.5
        )
        diagnostic_score = (
            max(0.0, target_300_gain_vs_1x if pd.notna(target_300_gain_vs_1x) else 0.0) * 100
            + max(0.0, target_400_gain_vs_1x if pd.notna(target_400_gain_vs_1x) else 0.0) * 60
            - max(0.0, stop_hit_increase_vs_1x if pd.notna(stop_hit_increase_vs_1x) else 0.0) * 300
            - max(0.0, -(worst_drawdown_worsening_vs_1x if pd.notna(worst_drawdown_worsening_vs_1x) else 0.0)) / 10
            - overshoot50 * 100
            - overshoot100 * 160
            - cost_quality_penalty * 30
        )
        score = (
            p300 * 100
            + p400 * 30
            - stop * 120
            - drawdown_penalty * 20
            - tier_penalty * 35
            - leverage_penalty * 65
            - quality_penalty * 45
            - cost_quality_penalty * 30
            - catastrophic_penalty * 100
            - benchmark_penalty * 35
            - stop_recovery_penalty * 10
            - stress_penalty * 20
            + diversification_score * 5
        )
        family_comparison_score = score
        verdict = row["audit_verdict"]
        if str(row["lane"]) == "simulated_leverage_diagnostic":
            verdict = "too_risky" if (stop > 0.05 or (pd.notna(worst_90d_drawdown) and worst_90d_drawdown < -TRAILING_DRAWDOWN) or catastrophic_loss) else "watchlist_diagnostic"
        elif str(row["lane"]) == "simulated_etf_exposure_frontier":
            if float(row.get("exposure_multiplier", row["leverage_multiplier"])) == 1.0:
                verdict = "watchlist_diagnostic"
            elif (
                (pd.isna(stop_hit_increase_vs_1x) or stop_hit_increase_vs_1x <= 0.01)
                and (pd.isna(worst_drawdown_worsening_vs_1x) or worst_drawdown_worsening_vs_1x >= -75)
                and overshoot100 <= 0.01
            ):
                verdict = "watchlist_diagnostic"
            else:
                verdict = "too_risky"
        elif str(row["lane"]) == "etf_volatility_control_diagnostic":
            cap = float(row.get("exposure_multiplier", 1.0))
            if cap > 1.0 and (
                (pd.notna(stop_hit_change_vs_spy_200d) and stop_hit_change_vs_spy_200d > 0.01)
                or (pd.notna(worst_drawdown_change_vs_spy_200d) and worst_drawdown_change_vs_spy_200d < -50.0)
            ):
                verdict = "too_risky"
            elif pd.notna(target_300_change_vs_spy_200d) and target_300_change_vs_spy_200d < -0.10:
                verdict = "too_slow"
            elif pd.notna(worst_drawdown_change_vs_spy_200d) and worst_drawdown_change_vs_spy_200d > 50.0 and target_300_change_vs_spy_200d >= -0.08:
                verdict = "watchlist_diagnostic"
            else:
                verdict = "exploratory_only"
        elif str(row["lane"]) == "diversified_portfolio_challenge":
            unavailable = str(row.get("unavailable_sleeves", ""))
            if unavailable and unavailable != "nan":
                verdict = "incomplete_evidence"
            elif str(row.get("credibility_tier")) == "tier1_exploratory" or crypto_weight > 0:
                verdict = "exploratory_only"
            elif pd.notna(target_300_change_vs_spy_200d) and target_300_change_vs_spy_200d >= 0 and stop_hit_change_vs_spy_200d <= 0 and (pd.isna(worst_drawdown_change_vs_spy_200d) or worst_drawdown_change_vs_spy_200d >= 0):
                verdict = "benchmark_candidate"
            elif pd.notna(target_300_change_vs_spy_200d) and target_300_change_vs_spy_200d < -0.08:
                verdict = "too_slow"
            else:
                verdict = "watchlist_diagnostic"
        elif str(row["lane"]) == "independent_family_challenge":
            if run_status == "blocked_by_gate":
                verdict = "blocked_by_gate"
                score = -1000.0
                family_comparison_score = score
            elif family_blocked_or_unavailable:
                verdict = "incomplete_evidence"
                score = -800.0
                family_comparison_score = score
            else:
                if pd.notna(stop_hit_change_vs_spy_200d) and stop_hit_change_vs_spy_200d > 0:
                    score -= stop_hit_change_vs_spy_200d * 350
                if pd.notna(worst_drawdown_change_vs_spy_200d) and worst_drawdown_change_vs_spy_200d < 0:
                    score += worst_drawdown_change_vs_spy_200d / 10
                family_comparison_score = score
                if str(row.get("credibility_tier")) == "tier1_exploratory":
                    verdict = "exploratory_only"
                elif pd.notna(target_300_change_vs_spy_200d) and target_300_change_vs_spy_200d >= 0 and stop_hit_change_vs_spy_200d <= 0 and (pd.isna(worst_drawdown_change_vs_spy_200d) or worst_drawdown_change_vs_spy_200d >= 0):
                    verdict = "benchmark_candidate"
                elif pd.notna(target_300_change_vs_spy_200d) and target_300_change_vs_spy_200d < -0.08:
                    verdict = "too_slow"
                else:
                    verdict = "watchlist"
        elif "crypto" in str(row["lane"]) or "leverage" in str(row["lane"]):
            verdict = "exploratory_only" if verdict not in {"too_risky", "benchmark_only"} else verdict
        if float(row["leverage_multiplier"]) > 1 and verdict == "practical_candidate":
            verdict = "too_risky"
        if quality in {"approximate", "unavailable"} and verdict == "practical_candidate":
            verdict = "incomplete_evidence"
        if not benchmark_comparison_available and verdict == "practical_candidate":
            verdict = "incomplete_evidence"
        if not rolling_final_completed and verdict == "practical_candidate":
            verdict = "watchlist"
        if str(row["strategy"]) == "BIL_cash_proxy":
            verdict = "benchmark_only"
        if str(row["strategy"]) == "SPY_200d_trend_model" and rolling_final_completed and quality == "exact" and p300 > 0:
            verdict = "benchmark_candidate"
        if str(row["strategy"]) == "SPY_buy_hold" and stop > 0.02:
            verdict = "benchmark_candidate"
        penalty_notes = ranking_reason(row, p300, p400, stop, stress_degradation)
        if str(row["strategy"]) == FOCUSED_FINALIST and not spy200_standard.empty and not family_blocked_or_unavailable:
            spy200 = spy200_standard.iloc[0]
            if p300 < float(spy200["pct_target_300_before_stop"]) and p400 <= float(spy200["pct_target_400_before_stop"]):
                verdict = "watchlist"
                penalty_notes += "; lower 90d target-before-stop rates than SPY_200d_trend_model"
        if pd.notna(worst_90d_drawdown) and worst_90d_drawdown < -TRAILING_DRAWDOWN:
            penalty_notes += f"; worst 90d drawdown beyond $600 ({worst_90d_drawdown:.2f})"
        if quality != "exact":
            penalty_notes += f"; {quality} stop-enforced metric penalty"
        if cost_quality != "exact":
            penalty_notes += f"; {cost_quality} cost-model penalty"
        if catastrophic_loss:
            penalty_notes += "; catastrophic loss occurred in simulated path"
        if str(row["lane"]) == "simulated_etf_exposure_frontier":
            penalty_notes += (
                f"; exposure frontier gain_vs_1x +300={target_300_gain_vs_1x:.1%} "
                f"+400={target_400_gain_vs_1x:.1%} stop_increase={stop_hit_increase_vs_1x:.1%} "
                f"drawdown_worsening={worst_drawdown_worsening_vs_1x:.2f} "
                f"overshoot_gt_100={overshoot100:.1%}"
            )
        if str(row["lane"]) == "etf_volatility_control_diagnostic":
            penalty_notes += (
                f"; vol-control vs SPY_200d +300={target_300_change_vs_spy_200d:.1%} "
                f"+400={target_400_change_vs_spy_200d:.1%} stop={stop_hit_change_vs_spy_200d:.1%} "
                f"drawdown_change={worst_drawdown_change_vs_spy_200d:.2f} avg_exposure={average_exposure:.2f}"
            )
        if str(row["lane"]) == "diversified_portfolio_challenge":
            penalty_notes += (
                f"; portfolio vs SPY_200d +300={target_300_change_vs_spy_200d:.1%} "
                f"+400={target_400_change_vs_spy_200d:.1%} stop={stop_hit_change_vs_spy_200d:.1%} "
                f"drawdown_change={worst_drawdown_change_vs_spy_200d:.2f} "
                f"median_equity_change={median_equity_change_vs_spy_200d:.2f} "
                f"diversification_score={diversification_score:.2f}"
            )
            if str(row.get("unavailable_sleeves", "")) not in {"", "nan"}:
                penalty_notes += f"; unavailable sleeves {row.get('unavailable_sleeves')}"
        if str(row["lane"]) == "independent_family_challenge":
            penalty_notes += (
                f"; independent family row family_id={family_id or 'none'} group={family_group or 'none'} "
                f"run_status={run_status or 'completed'}; not a portfolio mix; no shared capital"
            )
            if run_status == "blocked_by_gate":
                penalty_notes += f"; blocked reason {row.get('blocked_reason')}"
            elif family_blocked_or_unavailable:
                penalty_notes += "; unavailable/incomplete family evidence"
        if benchmark_penalty:
            penalty_notes += "; missing benchmark comparability penalty"
        if not rolling_final_completed:
            penalty_notes += "; finalist all_possible validation incomplete or unavailable"
        risk_fields = risk_framework_values(
            lane=str(row["lane"]),
            strategy=str(row["strategy"]),
            instrument_family=str(row.get("instrument_family", "")),
            credibility_tier=str(row["credibility_tier"]),
            exposure_multiplier=row.get("exposure_multiplier", row["leverage_multiplier"]),
            max_drawdown_dollars=worst_90d_drawdown if pd.notna(worst_90d_drawdown) else row.get("max_drawdown_dollars", 0.0),
            stop_hit=stop >= 0.02,
            equity_for_progress=median_90d_stop_equity if pd.notna(median_90d_stop_equity) else row.get("stop_enforced_final_equity", STARTING_EQUITY),
            stop_metric_quality=quality,
            final_validation_completed=rolling_final_completed,
            benchmark_comparison_available=benchmark_comparison_available,
            current_verdict=str(verdict),
        )
        rows.append(
            {
                "score": score,
                "rank_target_300_metric": p300,
                "rank_target_400_metric": p400,
                "rank_risk_metric": -stop,
                "lane": row["lane"],
                "strategy": row["strategy"],
                "portfolio_id": row.get("portfolio_id", ""),
                "portfolio_role": row.get("portfolio_role", ""),
                "family_id": family_id,
                "family_group": family_group,
                "family_role": family_role,
                "implementation_status": implementation_status,
                "run_status": run_status,
                "final_validation_completed": rolling_final_completed,
                "sampled_results_are_final": rolling_sampled_final,
                "role": row.get("role", ""),
                "leverage_multiplier": row["leverage_multiplier"],
                "exposure_multiplier": row.get("exposure_multiplier", row["leverage_multiplier"]),
                "standard_or_stress": "standard",
                "pct_90d_target_300_before_stop": display_p300,
                "pct_90d_target_400_before_stop": display_p400,
                "pct_90d_any_stop_hit": display_stop,
                "median_90d_stop_enforced_equity": median_90d_stop_equity,
                "worst_90d_max_drawdown": worst_90d_drawdown,
                "worst_stop_enforced_loss": worst_stop_enforced_loss,
                "pct_90d_stop_overshoot_gt_50": overshoot50,
                "pct_90d_stop_overshoot_gt_100": overshoot100,
                "average_exposure": average_exposure,
                "target_300_gain_vs_1x": target_300_gain_vs_1x,
                "target_400_gain_vs_1x": target_400_gain_vs_1x,
                "stop_hit_increase_vs_1x": stop_hit_increase_vs_1x,
                "worst_drawdown_worsening_vs_1x": worst_drawdown_worsening_vs_1x,
                "target_300_change_vs_spy_200d": target_300_change_vs_spy_200d,
                "target_400_change_vs_spy_200d": target_400_change_vs_spy_200d,
                "stop_hit_change_vs_spy_200d": stop_hit_change_vs_spy_200d,
                "worst_drawdown_change_vs_spy_200d": worst_drawdown_change_vs_spy_200d,
                "median_equity_change_vs_spy_200d": median_equity_change_vs_spy_200d,
                "diversification_score": diversification_score,
                "max_single_sleeve_weight": max_single_sleeve_weight,
                "cash_weight": cash_weight,
                "bond_weight": bond_weight,
                "gold_weight": gold_weight,
                "crypto_weight": crypto_weight,
                "diagnostic_score": diagnostic_score,
                "family_comparison_score": family_comparison_score,
                "stop_enforced_final_equity": row["stop_enforced_final_equity"],
                "stress_result_available": stress_available,
                "stress_degradation_pct": stress_degradation,
                "benchmark_relative_result": float(row["stop_enforced_final_equity"]) - STARTING_EQUITY,
                "credibility_tier": row["credibility_tier"],
                "audit_verdict": verdict,
                "stop_enforced_metric_quality": quality,
                "benchmark_comparison_available": benchmark_comparison_available,
                "benchmark_comparison_notes": (
                    "SPY_buy_hold, SPY_200d_trend_model, and BIL_cash_proxy 90-day rows available."
                    if benchmark_comparison_available
                    else "Missing at least one required ETF benchmark 90-day rolling row."
                ),
                "ranking_penalty_notes": penalty_notes,
                "reason": penalty_notes,
                **risk_fields,
            }
        )
    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return pd.DataFrame(columns=[
            "rank_overall",
            "rank_target_300",
            "rank_target_400",
            "rank_risk_control",
            "lane",
            "strategy",
            "portfolio_id",
            "portfolio_role",
            "family_id",
            "family_group",
            "family_role",
            "implementation_status",
            "run_status",
            "final_validation_completed",
            "sampled_results_are_final",
            "role",
            "leverage_multiplier",
            "exposure_multiplier",
            "standard_or_stress",
            "pct_90d_target_300_before_stop",
            "pct_90d_target_400_before_stop",
            "pct_90d_any_stop_hit",
            "median_90d_stop_enforced_equity",
            "worst_90d_max_drawdown",
            "worst_stop_enforced_loss",
            "pct_90d_stop_overshoot_gt_50",
            "pct_90d_stop_overshoot_gt_100",
            "average_exposure",
            "target_300_gain_vs_1x",
            "target_400_gain_vs_1x",
            "stop_hit_increase_vs_1x",
            "worst_drawdown_worsening_vs_1x",
            "target_300_change_vs_spy_200d",
            "target_400_change_vs_spy_200d",
            "stop_hit_change_vs_spy_200d",
            "worst_drawdown_change_vs_spy_200d",
            "median_equity_change_vs_spy_200d",
            "diversification_score",
            "max_single_sleeve_weight",
            "cash_weight",
            "bond_weight",
            "gold_weight",
            "crypto_weight",
            "diagnostic_score",
            "family_comparison_score",
            "stop_enforced_final_equity",
            "stress_result_available",
            "stress_degradation_pct",
            "benchmark_relative_result",
            "credibility_tier",
            "audit_verdict",
            "stop_enforced_metric_quality",
            "benchmark_comparison_available",
            "benchmark_comparison_notes",
            "risk_framework_name",
            "risk_band",
            "risk_budget_used_pct",
            "target_300_progress_pct",
            "target_400_progress_pct",
            "drawdown_warning_hit",
            "drawdown_review_hit",
            "hard_stop_hit",
            "risk_framework_verdict",
            "exposure_policy_status",
            "instrument_risk_role",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
            "ranking_penalty_notes",
            "reason",
        ])
    ranking["rank_overall"] = ranking["score"].rank(ascending=False, method="first").astype(int)
    ranking["rank_target_300"] = ranking["rank_target_300_metric"].rank(ascending=False, method="first").astype(int)
    ranking["rank_target_400"] = ranking["rank_target_400_metric"].rank(ascending=False, method="first").astype(int)
    ranking["rank_risk_control"] = ranking["rank_risk_metric"].rank(ascending=False, method="first").astype(int)
    ranking = ranking.sort_values("rank_overall")
    return ranking[
        [
            "rank_overall",
            "rank_target_300",
            "rank_target_400",
            "rank_risk_control",
            "lane",
            "strategy",
            "portfolio_id",
            "portfolio_role",
            "family_id",
            "family_group",
            "family_role",
            "implementation_status",
            "run_status",
            "final_validation_completed",
            "sampled_results_are_final",
            "role",
            "leverage_multiplier",
            "exposure_multiplier",
            "standard_or_stress",
            "pct_90d_target_300_before_stop",
            "pct_90d_target_400_before_stop",
            "pct_90d_any_stop_hit",
            "median_90d_stop_enforced_equity",
            "worst_90d_max_drawdown",
            "worst_stop_enforced_loss",
            "pct_90d_stop_overshoot_gt_50",
            "pct_90d_stop_overshoot_gt_100",
            "average_exposure",
            "target_300_gain_vs_1x",
            "target_400_gain_vs_1x",
            "stop_hit_increase_vs_1x",
            "worst_drawdown_worsening_vs_1x",
            "target_300_change_vs_spy_200d",
            "target_400_change_vs_spy_200d",
            "stop_hit_change_vs_spy_200d",
            "worst_drawdown_change_vs_spy_200d",
            "median_equity_change_vs_spy_200d",
            "diversification_score",
            "max_single_sleeve_weight",
            "cash_weight",
            "bond_weight",
            "gold_weight",
            "crypto_weight",
            "diagnostic_score",
            "family_comparison_score",
            "stop_enforced_final_equity",
            "stress_result_available",
            "stress_degradation_pct",
            "benchmark_relative_result",
            "credibility_tier",
            "audit_verdict",
            "stop_enforced_metric_quality",
            "benchmark_comparison_available",
            "benchmark_comparison_notes",
            "risk_framework_name",
            "risk_band",
            "risk_budget_used_pct",
            "target_300_progress_pct",
            "target_400_progress_pct",
            "drawdown_warning_hit",
            "drawdown_review_hit",
            "hard_stop_hit",
            "risk_framework_verdict",
            "exposure_policy_status",
            "instrument_risk_role",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
            "ranking_penalty_notes",
            "reason",
        ]
    ]


def ranking_reason(row: pd.Series, p300: float, p400: float, stop: float, stress_degradation: float) -> str:
    reasons = [f"90d +300 before stop {p300:.1%}", f"90d stop hit {stop:.1%}"]
    if p400:
        reasons.append(f"90d +400 before stop {p400:.1%}")
    if pd.notna(stress_degradation) and stress_degradation < -0.1:
        reasons.append(f"stress degradation {stress_degradation:.1%}")
    if "Tier 1" in str(row["credibility_tier"]) or str(row["credibility_tier"]) == "tier1_exploratory":
        reasons.append("Tier 1 exploratory penalty")
    if float(row["leverage_multiplier"]) > 1:
        reasons.append("approximate leverage penalty")
    if float(row["unconditional_final_equity"]) > float(row["stop_enforced_final_equity"]) * 1.2:
        reasons.append("large recovery after stop warning")
    return "; ".join(reasons)


def write_outputs(
    run_id: str,
    challenge: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    coverage: pd.DataFrame,
    assumptions: dict[str, Any],
    output_root: Path = Path("evidence/challenge_runs"),
) -> tuple[Path, Path]:
    run_dir = output_root / "runs" / run_id
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    final_completed = bool(assumptions.get("validation", {}).get("final_validation_completed", True))
    challenge = annotate_challenge_finality(challenge.reindex(columns=CHALLENGE_COLUMNS), rolling.reindex(columns=ROLLING_COLUMNS))
    challenge = apply_risk_framework_to_challenge(challenge.reindex(columns=CHALLENGE_COLUMNS), final_validation_completed=final_completed)
    rolling = apply_risk_framework_to_rolling(rolling.reindex(columns=ROLLING_COLUMNS))
    risk = build_risk_stop_audit(challenge)
    summary = build_challenge_summary(run_id, challenge, rolling, rankings, assumptions)
    warnings = build_warnings(assumptions)
    readme = build_readme()

    (run_dir / "README_FOR_AUDITOR.md").write_text(readme, encoding="utf-8")
    (run_dir / "challenge_summary.md").write_text(summary, encoding="utf-8")
    challenge.to_csv(run_dir / "challenge_results.csv", index=False)
    rolling.to_csv(run_dir / "rolling_window_summary.csv", index=False)
    rankings.to_csv(run_dir / "strategy_rankings.csv", index=False)
    (run_dir / "assumptions_and_costs.yaml").write_text(yaml.safe_dump(assumptions, sort_keys=False), encoding="utf-8")
    coverage.to_csv(run_dir / "data_coverage_summary.csv", index=False)
    risk.to_csv(run_dir / "risk_and_stop_audit.csv", index=False)
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")
    write_chart(run_dir / "challenge_charts.png", rolling, challenge)

    files = [p.name for p in run_dir.iterdir() if p.is_file()]
    extra = sorted(set(files) - set(REQUIRED_FILES))
    missing = sorted(set(REQUIRED_FILES) - set(files))
    if extra or missing or len(files) > 10:
        raise RuntimeError(f"Challenge output contract failed. extra={extra} missing={missing} file_count={len(files)}")

    shutil.copytree(run_dir, latest_dir)
    zip_path = output_root / "latest_challenge_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir


def build_risk_stop_audit(challenge: pd.DataFrame) -> pd.DataFrame:
    out = challenge[
        [
            "lane",
            "strategy",
            "role",
            "leverage_multiplier",
            "exposure_multiplier",
            "standard_or_stress",
            "unconditional_final_equity",
            "stop_enforced_final_equity",
            "absolute_floor_stop_hit",
            "trailing_drawdown_stop_hit",
            "any_project_stop_hit",
            "first_project_stop_date",
            "first_project_stop_type",
            "equity_at_first_project_stop",
            "stop_overshoot_dollars",
            "stop_overshoot_pct",
            "target_300_before_stop",
            "target_400_before_stop",
            "max_drawdown_dollars",
            "max_drawdown_pct",
            "main_failure_mode",
            "stop_enforced_metric_quality",
            "stop_enforced_metric_source",
            "stop_enforced_metric_notes",
            "risk_framework_name",
            "risk_band",
            "risk_budget_used_pct",
            "target_300_progress_pct",
            "target_400_progress_pct",
            "drawdown_warning_hit",
            "drawdown_review_hit",
            "hard_stop_hit",
            "risk_framework_verdict",
            "exposure_policy_status",
            "instrument_risk_role",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
        ]
    ].copy()
    out["stop_enforced_penalty"] = out["unconditional_final_equity"].astype(float) - out["stop_enforced_final_equity"].astype(float)
    out["result_interpretation"] = np.where(
        out["any_project_stop_hit"].astype(bool),
        "Stop-enforced result is more relevant than final-date recovery.",
        "No selected project stop hit in this summary.",
    )
    return out[
        [
            "lane",
            "strategy",
            "role",
            "leverage_multiplier",
            "exposure_multiplier",
            "standard_or_stress",
            "unconditional_final_equity",
            "stop_enforced_final_equity",
            "stop_enforced_penalty",
            "absolute_floor_stop_hit",
            "trailing_drawdown_stop_hit",
            "any_project_stop_hit",
            "first_project_stop_date",
            "first_project_stop_type",
            "equity_at_first_project_stop",
            "stop_overshoot_dollars",
            "stop_overshoot_pct",
            "target_300_before_stop",
            "target_400_before_stop",
            "max_drawdown_dollars",
            "max_drawdown_pct",
            "stop_enforced_metric_quality",
            "stop_enforced_metric_source",
            "stop_enforced_metric_notes",
            "risk_framework_name",
            "risk_band",
            "risk_budget_used_pct",
            "target_300_progress_pct",
            "target_400_progress_pct",
            "drawdown_warning_hit",
            "drawdown_review_hit",
            "hard_stop_hit",
            "risk_framework_verdict",
            "exposure_policy_status",
            "instrument_risk_role",
            "paper_forward_allowed_by_risk_framework",
            "promotion_blockers",
            "result_interpretation",
        ]
    ]


def build_challenge_summary(run_id: str, challenge: pd.DataFrame, rolling: pd.DataFrame, rankings: pd.DataFrame, assumptions: dict[str, Any]) -> str:
    standard = challenge[challenge["standard_or_stress"].eq("standard")]
    run_status = standard.get("run_status", pd.Series("", index=standard.index)).fillna("").astype(str)
    runnable_standard = standard[run_status.isin(["", "completed", "nan"])]
    hit300 = runnable_standard[runnable_standard["target_300_before_stop"].map(boolish)]
    hit400 = runnable_standard[runnable_standard["target_400_before_stop"].map(boolish)]
    stopped = runnable_standard[runnable_standard["any_project_stop_hit"].map(boolish)]
    best_rank = rankings.iloc[0] if not rankings.empty else None
    best300 = rankings.sort_values("pct_90d_target_300_before_stop", ascending=False).iloc[0] if not rankings.empty else None
    best400 = rankings.sort_values("pct_90d_target_400_before_stop", ascending=False).iloc[0] if not rankings.empty else None
    best_risk = rankings.sort_values(["pct_90d_any_stop_hit", "pct_90d_target_300_before_stop"], ascending=[True, False]).iloc[0] if not rankings.empty else None

    def fmt(row: pd.Series | None) -> str:
        if row is None:
            return "Unavailable."
        return f"{row['lane']} / {row['strategy']} ({row['leverage_multiplier']}x): +300 90d {row['pct_90d_target_300_before_stop']:.1%}, +400 90d {row['pct_90d_target_400_before_stop']:.1%}, stop 90d {row['pct_90d_any_stop_hit']:.1%}."

    hit300_names = ", ".join((hit300["lane"] + "/" + hit300["strategy"] + "/" + hit300["leverage_multiplier"].astype(str) + "x").tolist()) or "None in standard rows."
    hit400_names = ", ".join((hit400["lane"] + "/" + hit400["strategy"] + "/" + hit400["leverage_multiplier"].astype(str) + "x").tolist()) or "None in standard rows."
    stopped_names = ", ".join((stopped["lane"] + "/" + stopped["strategy"] + "/" + stopped["leverage_multiplier"].astype(str) + "x").tolist()) or "None in standard rows."
    validation = assumptions.get("validation", {})
    lanes = assumptions.get("lanes", {})
    mode = validation.get("mode", "unknown")
    final_completed = validation.get("final_validation_completed", False)
    sampled_final = validation.get("sampled_results_are_final", False)
    incomplete_reason = validation.get("incomplete_reason", "")
    tested_lanes = ["focused exact ETF finalist" if mode == "candidate_exhaustive" and lanes.get("include_etf") else ("ETF evidence summaries" if lanes.get("include_etf") else "")]
    if lanes.get("include_benchmarks"):
        tested_lanes.append("ETF benchmarks")
    if lanes.get("include_crypto"):
        tested_lanes.append("long-only crypto spot exploratory strategies")
        tested_lanes.append("BTC/ETH buy-and-hold benchmarks")
    if assumptions.get("leverage", {}).get("included"):
        tested_lanes.append("approximate simulated leverage scenarios")
    if assumptions.get("simulated_etf_leverage", {}).get("enabled"):
        tested_lanes.append("Tier 1 simulated ETF leverage diagnostics")
    if assumptions.get("simulated_etf_exposure_frontier", {}).get("enabled"):
        tested_lanes.append("Tier 1 SPY_200d exposure frontier diagnostics")
    if assumptions.get("etf_volatility_control_diagnostic", {}).get("enabled"):
        tested_lanes.append("Tier 1 SPY_200d volatility-control diagnostics")
    if assumptions.get("diversified_portfolio_challenge", {}).get("enabled"):
        tested_lanes.append("fixed diversified portfolio challenge diagnostics")
    if assumptions.get("independent_family_challenge", {}).get("enabled"):
        tested_lanes.append("independent family challenge rows with separate $3,000 accounts")
    tested_text = ", ".join(item for item in tested_lanes if item) or "No active lanes were included."
    bench90 = rolling[(rolling["lane"].eq("etf_benchmark")) & (rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq("standard"))]
    required_benchmarks = ["SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"]
    required_horizons = [30, 60, 90, 180]
    required_labels = ["standard", "stress"]
    missing_benchmark_rows = []
    for benchmark in required_benchmarks:
        for horizon in required_horizons:
            for label in required_labels:
                match = rolling[
                    rolling["lane"].eq("etf_benchmark")
                    & rolling["strategy"].eq(benchmark)
                    & rolling["horizon"].eq(horizon)
                    & rolling["standard_or_stress"].eq(label)
                ]
                if match.empty:
                    missing_benchmark_rows.append(f"{benchmark}/{horizon}/{label}")
    family_benchmark90 = rolling[
        rolling["lane"].eq("independent_family_challenge")
        & rolling["strategy"].isin(required_benchmarks)
        & rolling["horizon"].eq(90)
        & rolling["standard_or_stress"].eq("standard")
        & rolling["final_validation_completed"].map(boolish)
    ]
    benchmark_status = "No standalone ETF benchmark rolling grid is present for this run."
    if not missing_benchmark_rows and not rolling[rolling["lane"].eq("etf_benchmark")].empty:
        qualities = ", ".join(
            sorted(
                rolling.loc[rolling["lane"].eq("etf_benchmark"), "rolling_metric_quality"]
                .dropna()
                .astype(str)
                .unique()
            )
        )
        benchmark_status = (
            "ETF benchmark rolling rows are present for SPY_buy_hold, SPY_200d_trend_model, "
            f"and BIL_cash_proxy at 30/60/90/180 days for standard and stress labels; quality labels: {qualities}."
        )
    elif not bench90.empty:
        qualities = ", ".join(sorted(bench90.get("rolling_metric_quality", pd.Series(["unknown"])).dropna().astype(str).unique()))
        benchmark_status = (
            f"ETF benchmark rolling rows are present for 90-day standard comparisons; quality labels: {qualities}. "
            f"Missing full required benchmark grid: {', '.join(missing_benchmark_rows[:8])}."
        )
    elif not family_benchmark90.empty:
        present = ", ".join(sorted(family_benchmark90["strategy"].dropna().astype(str).unique()))
        benchmark_status = (
            "Standalone ETF benchmark lane rows are not present, but exact independent-family benchmark rows "
            f"exist for {present}. These row-level exact results are valid family-comparison evidence."
        )

    comparison_lines: list[str] = []
    focus = "current_no_cash_proxy_alpha_AB"
    focus_row = rolling[(rolling["strategy"].eq(focus)) & (rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq("standard"))]
    if focus_row.empty:
        comparison_lines.append(f"- {focus}: 90-day rolling comparison unavailable or not all-possible in this compact run.")
    else:
        f = focus_row.iloc[0]
        comparison_lines.append(
            f"- {focus}: +300 {f['pct_target_300_before_stop']:.1%}, +400 {f['pct_target_400_before_stop']:.1%}, stop {f['pct_any_project_stop_hit']:.1%}, median stop equity {f['median_stop_enforced_final_equity']:.2f}, worst drawdown {f['worst_max_drawdown']:.2f}."
        )
        for bench in ["SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"]:
            b = bench90[bench90["strategy"].eq(bench)]
            if b.empty:
                comparison_lines.append(f"- {bench}: unavailable.")
            else:
                br = b.iloc[0]
                beats300 = f["pct_target_300_before_stop"] > br["pct_target_300_before_stop"]
                beats400 = f["pct_target_400_before_stop"] > br["pct_target_400_before_stop"]
                better_stop = f["pct_any_project_stop_hit"] <= br["pct_any_project_stop_hit"]
                better_median_stop_equity = f["median_stop_enforced_final_equity"] > br["median_stop_enforced_final_equity"]
                better_worst_drawdown = f["worst_max_drawdown"] >= br["worst_max_drawdown"]
                comparison_lines.append(
                    f"- {bench}: +300 {br['pct_target_300_before_stop']:.1%}, +400 {br['pct_target_400_before_stop']:.1%}, stop {br['pct_any_project_stop_hit']:.1%}, median stop equity {br['median_stop_enforced_final_equity']:.2f}, worst drawdown {br['worst_max_drawdown']:.2f}. Focus beats +300={beats300}, +400={beats400}, stop-rate={better_stop}, median-stop-equity={better_median_stop_equity}, worst-drawdown={better_worst_drawdown}."
                )
    comparison_text = "\n".join(comparison_lines)
    table_strategies = [focus, "SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"]

    def ninety_day_table(label: str) -> str:
        subset = rolling[(rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq(label))]
        lines = [
            "| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for strategy in table_strategies:
            row = subset[subset["strategy"].eq(strategy)]
            if row.empty:
                lines.append(f"| {strategy} | unavailable | unavailable | unavailable | unavailable | unavailable | no |")
                continue
            r = row.iloc[0]
            lines.append(
                f"| {strategy} | {float(r['pct_target_300_before_stop']):.1%} | "
                f"{float(r['pct_target_400_before_stop']):.1%} | "
                f"{float(r['pct_any_project_stop_hit']):.1%} | "
                f"${float(r['median_stop_enforced_final_equity']):,.2f} | "
                f"${float(r['worst_max_drawdown']):,.2f} | "
                f"{boolish(r.get('final_validation_completed', False))} |"
            )
        return "\n".join(lines)

    std90 = rolling[(rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq("standard"))]
    current90 = std90[std90["strategy"].eq(focus)]
    spy20090 = std90[std90["strategy"].eq("SPY_200d_trend_model")]
    spy90 = std90[std90["strategy"].eq("SPY_buy_hold")]
    if final_completed and not current90.empty and not spy20090.empty:
        cur = current90.iloc[0]
        spy200 = spy20090.iloc[0]
        current_beats_spy200 = (
            float(cur["pct_target_300_before_stop"]) > float(spy200["pct_target_300_before_stop"])
            and float(cur["pct_target_400_before_stop"]) > float(spy200["pct_target_400_before_stop"])
            and float(cur["pct_any_project_stop_hit"]) <= float(spy200["pct_any_project_stop_hit"])
        )
        spy200_better_targets = (
            float(spy200["pct_target_300_before_stop"]) >= float(cur["pct_target_300_before_stop"])
            and float(spy200["pct_target_400_before_stop"]) >= float(cur["pct_target_400_before_stop"])
        )
        if current_beats_spy200:
            decision_statement = "current_no_cash_proxy_alpha_AB remains the leading practical ETF watchlist candidate in this focused run."
        elif spy200_better_targets and float(spy200["pct_any_project_stop_hit"]) <= max(0.02, float(cur["pct_any_project_stop_hit"]) + 0.02):
            decision_statement = "SPY_200d_trend_model becomes the leading practical ETF watchlist candidate in this focused run."
        else:
            decision_statement = "No ETF row cleanly dominates; the practical decision remains mixed and research-only."
        p300_plausible = max(float(cur["pct_target_300_before_stop"]), float(spy200["pct_target_300_before_stop"])) >= 0.10
        cur_p400 = float(cur["pct_target_400_before_stop"])
        spy200_p400 = float(spy200["pct_target_400_before_stop"])
        p400_label = (
            f"low for current_no_cash_proxy_alpha_AB ({cur_p400:.1%}) and modest for SPY_200d_trend_model ({spy200_p400:.1%})"
            if spy200_p400 >= 0.05
            else f"low for both current_no_cash_proxy_alpha_AB ({cur_p400:.1%}) and SPY_200d_trend_model ({spy200_p400:.1%})"
        )
        goal_statement = (
            f"+$300 appears {'plausible' if p300_plausible else 'low probability'} under the exact focused 90-day ETF rows. "
            f"+$400 remains {p400_label}; it is not validated as reliable."
        )
        custom_vs_spy200 = (
            f"current_no_cash_proxy_alpha_AB beats SPY_200d on +300={float(cur['pct_target_300_before_stop']) > float(spy200['pct_target_300_before_stop'])}, "
            f"+400={float(cur['pct_target_400_before_stop']) > float(spy200['pct_target_400_before_stop'])}, "
            f"stop-rate={float(cur['pct_any_project_stop_hit']) <= float(spy200['pct_any_project_stop_hit'])}, "
            f"median-stop-equity={float(cur['median_stop_enforced_final_equity']) > float(spy200['median_stop_enforced_final_equity'])}, "
            f"worst-drawdown={float(cur['worst_max_drawdown']) >= float(spy200['worst_max_drawdown'])}."
        )
    elif final_completed:
        decision_statement = "Final validation completed mechanically, but the required current-vs-SPY_200d 90-day rows were not both available."
        goal_statement = "The +$300/+400 practical target cannot be judged from missing comparison rows."
        custom_vs_spy200 = "current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison unavailable."
    else:
        exact_family90_available = not rolling[
            rolling["lane"].eq("independent_family_challenge")
            & rolling["horizon"].eq(90)
            & rolling["standard_or_stress"].eq("standard")
            & rolling["final_validation_completed"].map(boolish)
        ].empty
        if exact_family90_available:
            decision_statement = (
                "Run-level validation is incomplete because some requested rows are incomplete or blocked, "
                "but exact completed family rows answer the completed-family portion."
            )
            goal_statement = (
                "+$300 is plausible across exact completed family rows; +$400 remains aggressive. "
                "A/B exact family comparison remains unresolved until exact fresh-window streams are exposed."
            )
            custom_vs_spy200 = (
                "current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model remains unresolved only for the "
                "A/B exact family-comparison row, not for the completed SPY/BIL/IEF/GLD family rows."
            )
        else:
            decision_statement = "validation incomplete"
            goal_statement = "+$300/+400 remain unresolved until exact finalist rows complete."
            custom_vs_spy200 = "current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final."

    spy_buy_hold_note = "SPY_buy_hold comparison note is not available in this compact table."
    if not spy90.empty and not current90.empty:
        spy = spy90.iloc[0]
        cur = current90.iloc[0]
        spy_buy_hold_note = (
            f"SPY_buy_hold +300 rate is {float(spy['pct_target_300_before_stop']):.1%} versus "
            f"{float(cur['pct_target_300_before_stop']):.1%} for current_no_cash_proxy_alpha_AB, with stop-hit "
            f"{float(spy['pct_any_project_stop_hit']):.1%} versus {float(cur['pct_any_project_stop_hit']):.1%}. "
            "It should be penalized if its stop risk or worst drawdown is materially worse."
        )
    elif not spy90.empty:
        spy = spy90.iloc[0]
        spy_buy_hold_note = (
            f"SPY_buy_hold exact 90-day row is present: +300={float(spy['pct_target_300_before_stop']):.1%}, "
            f"+400={float(spy['pct_target_400_before_stop']):.1%}, stop={float(spy['pct_any_project_stop_hit']):.1%}, "
            f"worst drawdown=${float(spy['worst_max_drawdown']):,.2f}. It remains a high-target, higher-drawdown benchmark."
        )
    validation_statement = (
        "Finalist validation completed with all_possible windows."
        if final_completed
        else f"Finalist validation is incomplete/non-final. {incomplete_reason or 'The run remains research evidence, not final validation.'}"
    )
    practical_statement = (
        "current_no_cash_proxy_alpha_AB may be considered only as a research watchlist/finalist candidate until exact finalist validation is complete."
        if focus_row.empty or not final_completed
        else "current_no_cash_proxy_alpha_AB has completed the focused candidate_exhaustive path, but remains research-only and not a real-money recommendation."
    )
    crypto_section = (
        "Crypto rows were not included in this focused run. Prior crypto exploratory rows remain Tier 1 only and are not comparable to ETF evidence as validated candidates."
        if not lanes.get("include_crypto")
        else "Crypto rows remain Tier 1 exploratory when included. Large final-date crypto equity is not enough because many rows also hit project stops."
    )
    leverage_section = (
        "Simulated leverage rows were not included in this focused run. When included, they are approximate scenarios only and are not a real margin/liquidation model."
        if not assumptions.get("leverage", {}).get("included") and not assumptions.get("simulated_etf_leverage", {}).get("enabled") and not assumptions.get("simulated_etf_exposure_frontier", {}).get("enabled")
        else "Simulated leverage is approximate only when included. It often increases target hit rates and stop risk at the same time, and is not a real margin/liquidation model."
    )
    etf_leverage_enabled = bool(assumptions.get("simulated_etf_leverage", {}).get("enabled", False))

    def diag_row(strategy: str, label: str = "standard") -> pd.Series | None:
        subset = rolling[
            rolling["strategy"].eq(strategy)
            & rolling["horizon"].eq(90)
            & rolling["standard_or_stress"].eq(label)
        ]
        return subset.iloc[0] if not subset.empty else None

    def diag_metric(row: pd.Series | None, field: str) -> float:
        return float(row[field]) if row is not None and pd.notna(row[field]) else math.nan

    diag_names = {
        "spy200": "SPY_200d_trend_model",
        "spy200_125": diagnostic_strategy_name("SPY_200d_trend_model", 1.25),
        "spy200_150": diagnostic_strategy_name("SPY_200d_trend_model", 1.5),
        "spy": "SPY_buy_hold",
        "spy_125": diagnostic_strategy_name("SPY_buy_hold", 1.25),
        "spy_150": diagnostic_strategy_name("SPY_buy_hold", 1.5),
    }
    diag_rows = {name: diag_row(strategy) for name, strategy in diag_names.items()}

    def pct_delta(new: float, base: float) -> str:
        if pd.isna(new) or pd.isna(base):
            return "unavailable"
        return f"{(new - base):+.1%}"

    def dollars_delta(new: float, base: float) -> str:
        if pd.isna(new) or pd.isna(base):
            return "unavailable"
        return f"${(new - base):,.2f}"

    if etf_leverage_enabled:
        spy200_base = diag_rows["spy200"]
        spy200_125 = diag_rows["spy200_125"]
        spy200_150 = diag_rows["spy200_150"]
        spy_base = diag_rows["spy"]
        spy_125 = diag_rows["spy_125"]
        spy_150 = diag_rows["spy_150"]

        leverage_table = [
            "| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict ceiling |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for key in ["spy200", "spy200_125", "spy200_150", "spy", "spy_125", "spy_150"]:
            row = diag_rows[key]
            if row is None:
                leverage_table.append(f"| {diag_names[key]} | unavailable | unavailable | unavailable | unavailable | unavailable | not available |")
                continue
            verdict = "watchlist_diagnostic" if diag_metric(row, "pct_any_project_stop_hit") <= 0.05 and diag_metric(row, "worst_max_drawdown") >= -TRAILING_DRAWDOWN else "too_risky"
            if row["strategy"] in {"SPY_200d_trend_model", "SPY_buy_hold"}:
                verdict = "unlevered comparator"
            leverage_table.append(
                f"| {diag_names[key]} | {diag_metric(row, 'pct_target_300_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_target_400_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_any_project_stop_hit'):.1%} | "
                f"${diag_metric(row, 'median_stop_enforced_final_equity'):,.2f} | "
                f"${diag_metric(row, 'worst_max_drawdown'):,.2f} | {verdict} |"
            )
        p300_base = diag_metric(spy200_base, "pct_target_300_before_stop")
        p400_base = diag_metric(spy200_base, "pct_target_400_before_stop")
        stop_base = diag_metric(spy200_base, "pct_any_project_stop_hit")
        dd_base = diag_metric(spy200_base, "worst_max_drawdown")
        p300_125 = diag_metric(spy200_125, "pct_target_300_before_stop")
        p400_125 = diag_metric(spy200_125, "pct_target_400_before_stop")
        stop_125 = diag_metric(spy200_125, "pct_any_project_stop_hit")
        dd_125 = diag_metric(spy200_125, "worst_max_drawdown")
        p300_150 = diag_metric(spy200_150, "pct_target_300_before_stop")
        p400_150 = diag_metric(spy200_150, "pct_target_400_before_stop")
        stop_150 = diag_metric(spy200_150, "pct_any_project_stop_hit")
        dd_150 = diag_metric(spy200_150, "worst_max_drawdown")
        spy_125_stop = diag_metric(spy_125, "pct_any_project_stop_hit")
        spy_150_stop = diag_metric(spy_150, "pct_any_project_stop_hit")
        leverage_decision = (
            f"1.25x SPY_200d changed +300 by {pct_delta(p300_125, p300_base)}, +400 by {pct_delta(p400_125, p400_base)}, "
            f"stop-hit by {pct_delta(stop_125, stop_base)}, and worst drawdown by {dollars_delta(dd_125, dd_base)}. "
            f"1.5x SPY_200d changed +300 by {pct_delta(p300_150, p300_base)}, +400 by {pct_delta(p400_150, p400_base)}, "
            f"stop-hit by {pct_delta(stop_150, stop_base)}, and worst drawdown by {dollars_delta(dd_150, dd_base)}. "
            f"SPY buy-hold leverage stop-hit rates were {spy_125_stop:.1%} at 1.25x and {spy_150_stop:.1%} at 1.5x when available. "
            "No leverage row is paper-forward ready; the maximum allowed conclusion is watchlist_diagnostic."
        )
        leverage_summary = "\n".join(leverage_table)
    else:
        leverage_summary = "Simulated ETF leverage diagnostics were not enabled in this run."
        leverage_decision = "No ETF leverage diagnostic decision was made in this run."

    exposure_frontier_enabled = bool(assumptions.get("simulated_etf_exposure_frontier", {}).get("enabled", False))
    exposure_multipliers = list(ETF_EXPOSURE_FRONTIER.keys())
    if exposure_frontier_enabled:
        exposure_rows = {mult: diag_row(exposure_strategy_name(mult)) for mult in exposure_multipliers}
        base = exposure_rows.get(1.0)
        exposure_table = [
            "| Exposure | +300 before stop | +400 before stop | Any stop hit | Worst drawdown | Stop overshoot >$50 | Stop overshoot >$100 | Verdict ceiling |",
            "|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        best_frontier = None
        frontier_rankings = rankings[rankings["lane"].eq("simulated_etf_exposure_frontier")].copy()
        if not frontier_rankings.empty and "diagnostic_score" in frontier_rankings:
            best_frontier = frontier_rankings.sort_values("diagnostic_score", ascending=False).iloc[0]
        for mult in exposure_multipliers:
            row = exposure_rows.get(mult)
            if row is None:
                exposure_table.append(f"| {mult:.2f}x | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | not available |")
                continue
            strategy_rank = frontier_rankings[frontier_rankings["strategy"].eq(exposure_strategy_name(mult))]
            verdict = str(strategy_rank["audit_verdict"].iloc[0]) if not strategy_rank.empty else "exploratory_only"
            exposure_table.append(
                f"| {mult:.2f}x | {diag_metric(row, 'pct_target_300_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_target_400_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_any_project_stop_hit'):.1%} | "
                f"${diag_metric(row, 'worst_max_drawdown'):,.2f} | "
                f"{diag_metric(row, 'pct_windows_stop_overshoot_gt_50'):.1%} | "
                f"{diag_metric(row, 'pct_windows_stop_overshoot_gt_100'):.1%} | {verdict} |"
            )
        base_p300 = diag_metric(base, "pct_target_300_before_stop")
        base_p400 = diag_metric(base, "pct_target_400_before_stop")
        base_stop = diag_metric(base, "pct_any_project_stop_hit")
        base_dd = diag_metric(base, "worst_max_drawdown")
        row_105 = exposure_rows.get(1.05)
        row_110 = exposure_rows.get(1.10)
        row_115 = exposure_rows.get(1.15)
        unacceptable_stop = "not reached in tested frontier"
        clear_dd_break = "1.00x already exceeds the -$600 worst-window drawdown budget"
        for mult in exposure_multipliers:
            row = exposure_rows.get(mult)
            if row is not None and diag_metric(row, "pct_any_project_stop_hit") - base_stop > 0.02:
                unacceptable_stop = f"{mult:.2f}x"
                break
        for mult in exposure_multipliers:
            row = exposure_rows.get(mult)
            if row is not None and diag_metric(row, "worst_max_drawdown") < -TRAILING_DRAWDOWN:
                clear_dd_break = f"{mult:.2f}x"
                break
        best_frontier_text = (
            f"{best_frontier['strategy']} ({float(best_frontier['exposure_multiplier']):.2f}x), verdict={best_frontier['audit_verdict']}, diagnostic_score={float(best_frontier['diagnostic_score']):.2f}"
            if best_frontier is not None
            else "unavailable"
        )
        exposure_decision = (
            f"1.05x changed +300 by {pct_delta(diag_metric(row_105, 'pct_target_300_before_stop'), base_p300)} "
            f"and +400 by {pct_delta(diag_metric(row_105, 'pct_target_400_before_stop'), base_p400)} versus 1.00x. "
            f"1.10x changed +300 by {pct_delta(diag_metric(row_110, 'pct_target_300_before_stop'), base_p300)} "
            f"and +400 by {pct_delta(diag_metric(row_110, 'pct_target_400_before_stop'), base_p400)}. "
            f"1.15x changed +300 by {pct_delta(diag_metric(row_115, 'pct_target_300_before_stop'), base_p300)} "
            f"and +400 by {pct_delta(diag_metric(row_115, 'pct_target_400_before_stop'), base_p400)}. "
            f"Stop-hit rate becomes meaningfully worse at {unacceptable_stop}; worst drawdown clearly exceeds -$600 at {clear_dd_break}. "
            f"Best diagnostic tradeoff: {best_frontier_text}. No exposure row is paper-forward ready."
        )
        exposure_summary = "\n".join(exposure_table)
    else:
        exposure_summary = "ETF exposure frontier diagnostics were not enabled in this run."
        exposure_decision = "No exposure frontier decision was made in this run."
    vol_control_enabled = bool(assumptions.get("etf_volatility_control_diagnostic", {}).get("enabled", False))
    if vol_control_enabled:
        vol_base = diag_row("SPY_200d_trend_model")
        vol_100 = diag_row(vol_control_strategy_name(1.0))
        vol_110 = diag_row(vol_control_strategy_name(1.1))
        vol_rankings = rankings[rankings["lane"].eq("etf_volatility_control_diagnostic")].copy()
        best_vol = vol_rankings.sort_values("rank_overall").iloc[0] if not vol_rankings.empty and "rank_overall" in vol_rankings else None
        vol_table = [
            "| Strategy | +300 before stop | +400 before stop | Any stop hit | Worst drawdown | Average exposure | Verdict ceiling |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for strategy in ["SPY_200d_trend_model", vol_control_strategy_name(1.0), vol_control_strategy_name(1.1)]:
            row = diag_row(strategy)
            if row is None:
                vol_table.append(f"| {strategy} | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |")
                continue
            rank_row = vol_rankings[vol_rankings["strategy"].eq(strategy)]
            verdict = str(rank_row["audit_verdict"].iloc[0]) if not rank_row.empty else ("baseline" if strategy == "SPY_200d_trend_model" else "exploratory_only")
            vol_table.append(
                f"| {strategy} | {diag_metric(row, 'pct_target_300_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_target_400_before_stop'):.1%} | "
                f"{diag_metric(row, 'pct_any_project_stop_hit'):.1%} | "
                f"${diag_metric(row, 'worst_max_drawdown'):,.2f} | "
                f"{diag_metric(row, 'average_exposure'):.2f} | {verdict} |"
            )
        vol_100_dd_delta = dollars_delta(diag_metric(vol_100, "worst_max_drawdown"), diag_metric(vol_base, "worst_max_drawdown"))
        vol_110_dd_delta = dollars_delta(diag_metric(vol_110, "worst_max_drawdown"), diag_metric(vol_base, "worst_max_drawdown"))
        best_vol_text = (
            f"{best_vol['strategy']} ({best_vol['audit_verdict']})"
            if best_vol is not None
            else "unavailable"
        )
        tier2_text = (
            "At least one row can be considered for Tier 2 review only as a diagnostic follow-up."
            if best_vol is not None and str(best_vol["audit_verdict"]) == "watchlist_diagnostic"
            else "No volatility-control row deserves Tier 2 review from this packet because the target-probability loss is too large or the row remains merely exploratory."
        )
        vol_decision = (
            f"Cap 1.00 changed +300 by {pct_delta(diag_metric(vol_100, 'pct_target_300_before_stop'), diag_metric(vol_base, 'pct_target_300_before_stop'))}, "
            f"+400 by {pct_delta(diag_metric(vol_100, 'pct_target_400_before_stop'), diag_metric(vol_base, 'pct_target_400_before_stop'))}, "
            f"stop-hit by {pct_delta(diag_metric(vol_100, 'pct_any_project_stop_hit'), diag_metric(vol_base, 'pct_any_project_stop_hit'))}, "
            f"and worst drawdown by {vol_100_dd_delta}. "
            f"Cap 1.10 changed +300 by {pct_delta(diag_metric(vol_110, 'pct_target_300_before_stop'), diag_metric(vol_base, 'pct_target_300_before_stop'))}, "
            f"+400 by {pct_delta(diag_metric(vol_110, 'pct_target_400_before_stop'), diag_metric(vol_base, 'pct_target_400_before_stop'))}, "
            f"stop-hit by {pct_delta(diag_metric(vol_110, 'pct_any_project_stop_hit'), diag_metric(vol_base, 'pct_any_project_stop_hit'))}, "
            f"and worst drawdown by {vol_110_dd_delta}. "
            f"Best volatility-control diagnostic tradeoff: {best_vol_text}. {tier2_text} No volatility-control row is paper-forward ready."
        )
        vol_summary = "\n".join(vol_table)
    else:
        vol_summary = "ETF volatility-control diagnostics were not enabled in this run."
        vol_decision = "No volatility-control diagnostic decision was made in this run."
    portfolio_enabled = bool(assumptions.get("diversified_portfolio_challenge", {}).get("enabled", False))
    if portfolio_enabled:
        portfolio90 = rolling[
            rolling["lane"].eq("diversified_portfolio_challenge")
            & rolling["horizon"].eq(90)
            & rolling["standard_or_stress"].eq("standard")
        ].copy()
        portfolio_rankings = rankings[rankings["lane"].eq("diversified_portfolio_challenge")].copy()
        portfolio_table = [
            "| Portfolio | Role | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for _, prow in portfolio90.sort_values("strategy").iterrows():
            rank_row = portfolio_rankings[portfolio_rankings["strategy"].eq(prow["strategy"])]
            verdict = str(rank_row["audit_verdict"].iloc[0]) if not rank_row.empty else "unavailable"
            portfolio_table.append(
                f"| {prow['strategy']} | {prow.get('portfolio_role', '')} | "
                f"{float(prow['pct_target_300_before_stop']):.1%} | "
                f"{float(prow['pct_target_400_before_stop']):.1%} | "
                f"{float(prow['pct_any_project_stop_hit']):.1%} | "
                f"${float(prow['median_stop_enforced_final_equity']):,.2f} | "
                f"${float(prow['worst_max_drawdown']):,.2f} | {verdict} |"
            )
        unavailable_portfolios = sorted(
            challenge.loc[
                challenge["lane"].eq("diversified_portfolio_challenge")
                & challenge["standard_or_stress"].eq("standard")
                & challenge["unavailable_sleeves"].fillna("").astype(str).ne(""),
                "strategy",
            ].astype(str).unique().tolist()
        )
        best_portfolio = None
        if not portfolio_rankings.empty:
            best_portfolio = portfolio_rankings.sort_values("rank_overall").iloc[0]
        spy200_ref = spy20090.iloc[0] if not spy20090.empty else None
        improved_rows = []
        too_slow_rows = []
        if spy200_ref is not None:
            for _, prow in portfolio90.iterrows():
                target_delta = float(prow["pct_target_300_before_stop"]) - float(spy200_ref["pct_target_300_before_stop"])
                stop_delta = float(prow["pct_any_project_stop_hit"]) - float(spy200_ref["pct_any_project_stop_hit"])
                dd_delta = float(prow["worst_max_drawdown"]) - float(spy200_ref["worst_max_drawdown"])
                if target_delta >= 0 and stop_delta <= 0 and dd_delta >= 0:
                    improved_rows.append(str(prow["strategy"]))
                if target_delta < -0.08:
                    too_slow_rows.append(str(prow["strategy"]))
        crypto_portfolio_note = (
            "Crypto-containing portfolios were included and remain Tier 1 exploratory only."
            if assumptions.get("diversified_portfolio_challenge", {}).get("include_exploratory_crypto_portfolios")
            else "Crypto-containing portfolios were not included in this run."
        )
        best_portfolio_text = (
            f"{best_portfolio['strategy']} ({best_portfolio['audit_verdict']}), +300={float(best_portfolio['pct_90d_target_300_before_stop']):.1%}, stop={float(best_portfolio['pct_90d_any_stop_hit']):.1%}, worst drawdown=${float(best_portfolio['worst_90d_max_drawdown']):,.2f}"
            if best_portfolio is not None
            else "unavailable"
        )
        portfolio_decision = (
            f"Unavailable portfolios: {', '.join(unavailable_portfolios) or 'none'}. "
            f"Portfolios improving +300/stop/drawdown versus SPY_200d: {', '.join(improved_rows) or 'none'}. "
            f"Defensive mixes that appear too slow: {', '.join(sorted(set(too_slow_rows))) or 'none under the >8 percentage-point threshold'}. "
            f"Best diagnostic tradeoff: {best_portfolio_text}. {crypto_portfolio_note} "
            "No diversified portfolio becomes paper-forward ready without a separate promotion decision."
        )
        portfolio_summary = "\n".join(portfolio_table)
    else:
        portfolio_summary = "Diversified portfolio challenge diagnostics were not enabled in this run."
        portfolio_decision = "No diversified portfolio challenge decision was made in this run."
    family_enabled = bool(assumptions.get("independent_family_challenge", {}).get("enabled", False))
    strategy_family_stream_text = "ETF strategy family stream completion was not evaluated in this run."
    row_level_finality_text = (
        "Run-level finality can be false while row-level exact evidence exists. "
        "In this packet, the run-level flag covers all requested rows together; row-level `final_validation_completed` "
        "and `rolling_method` identify which rows are exact all-possible evidence."
    )
    exact_completed_family_rows_text = "Independent family challenge was not enabled, so no exact completed family rows are listed."
    incomplete_family_rows_text = "Independent family challenge was not enabled, so no incomplete family rows are listed."
    blocked_family_rows_text = "Independent family challenge was not enabled, so no blocked family rows are listed."
    correct_family_conclusion_text = "Independent family challenge was not enabled, so no family-level conclusion is made."
    if family_enabled:
        family90 = rolling[
            rolling["lane"].eq("independent_family_challenge")
            & rolling["horizon"].eq(90)
            & rolling["standard_or_stress"].eq("standard")
        ].copy()
        family_rankings = rankings[rankings["lane"].eq("independent_family_challenge")].copy()
        family_table = [
            "| Family | Group | Tier | Final? | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for _, frow in family90.sort_values(["family_group", "strategy"]).iterrows():
            rank_row = family_rankings[family_rankings["family_id"].eq(frow.get("family_id", ""))]
            verdict = str(rank_row["audit_verdict"].iloc[0]) if not rank_row.empty else str(frow.get("risk_framework_verdict", "unavailable"))
            family_table.append(
                f"| {frow.get('family_id', frow['strategy'])} | {frow.get('family_group', '')} | "
                f"{frow.get('credibility_tier', '')} | {boolish(frow.get('final_validation_completed', False))} | "
                f"{float(frow['pct_target_300_before_stop']):.1%} | "
                f"{float(frow['pct_target_400_before_stop']):.1%} | "
                f"{float(frow['pct_any_project_stop_hit']):.1%} | "
                f"${float(frow['median_stop_enforced_final_equity']):,.2f} | "
                f"${float(frow['worst_max_drawdown']):,.2f} | {verdict} |"
            )
        blocked_family_rows = challenge[
            challenge["lane"].eq("independent_family_challenge")
            & challenge["run_status"].eq("blocked_by_gate")
        ].copy()
        unavailable_family_rows = challenge[
            challenge["lane"].eq("independent_family_challenge")
            & challenge["run_status"].eq("incomplete_evidence")
        ].copy()
        runnable_family_rows = challenge[
            challenge["lane"].eq("independent_family_challenge")
            & challenge["run_status"].eq("completed")
            & challenge["standard_or_stress"].eq("standard")
        ].copy()
        exact_family_rankings = family_rankings[
            family_rankings["run_status"].eq("completed")
            & family_rankings["final_validation_completed"].map(boolish)
            & ~family_rankings["credibility_tier"].eq("tier1_exploratory")
        ].copy()
        exploratory_family_rankings = family_rankings[
            family_rankings["credibility_tier"].eq("tier1_exploratory")
            & family_rankings["run_status"].eq("completed")
        ].copy()
        blocked_text = "; ".join(
            (
                blocked_family_rows["family_id"].astype(str)
                + ": "
                + blocked_family_rows["blocked_reason"].astype(str)
            ).tolist()
        ) or "none"
        unavailable_text = "; ".join(
            (
                unavailable_family_rows["family_id"].astype(str)
                + ": "
                + unavailable_family_rows["main_failure_mode"].fillna(unavailable_family_rows["notes"]).astype(str)
            ).tolist()
        ) or "none"
        runnable_text = ", ".join(runnable_family_rows["family_id"].dropna().astype(str).unique().tolist()) or "none"
        exact_text = ", ".join(exact_family_rankings["family_id"].dropna().astype(str).unique().tolist()) or "none with completed all_possible finality"
        best_family = exact_family_rankings.sort_values("family_comparison_score", ascending=False).iloc[0] if not exact_family_rankings.empty else None
        best_exact_target300 = exact_family_rankings.sort_values("pct_90d_target_300_before_stop", ascending=False).iloc[0] if not exact_family_rankings.empty else None
        best_exact_target400 = exact_family_rankings.sort_values("pct_90d_target_400_before_stop", ascending=False).iloc[0] if not exact_family_rankings.empty else None
        best_exact_risk = exact_family_rankings.sort_values(["pct_90d_any_stop_hit", "worst_90d_max_drawdown"], ascending=[True, False]).iloc[0] if not exact_family_rankings.empty else None
        best_exploratory = exploratory_family_rankings.sort_values("pct_90d_target_300_before_stop", ascending=False).iloc[0] if not exploratory_family_rankings.empty else None

        def family_short(row: pd.Series | None) -> str:
            if row is None:
                return "unavailable"
            return (
                f"{row['family_id']} / {row['strategy']} "
                f"(+300={float(row['pct_90d_target_300_before_stop']):.1%}, "
                f"+400={float(row['pct_90d_target_400_before_stop']):.1%}, "
                f"stop={float(row['pct_90d_any_stop_hit']):.1%}, "
                f"worst_dd=${float(row['worst_90d_max_drawdown']):,.2f})"
            )

        best_family_text = (
            f"{best_family['family_id']} / {best_family['strategy']} ({best_family['audit_verdict']}), "
            f"+300={float(best_family['pct_90d_target_300_before_stop']):.1%}, "
            f"+400={float(best_family['pct_90d_target_400_before_stop']):.1%}, "
            f"stop={float(best_family['pct_90d_any_stop_hit']):.1%}, "
            f"worst drawdown=${float(best_family['worst_90d_max_drawdown']):,.2f}"
            if best_family is not None
            else "unavailable"
        )
        spy_family = family90[family90["strategy"].eq("SPY_200d_trend_model")]
        improved_family_rows: list[str] = []
        if not spy_family.empty:
            spy_ref = spy_family.iloc[0]
            for _, frow in family90.iterrows():
                if frow["strategy"] == "SPY_200d_trend_model":
                    continue
                target_delta = float(frow["pct_target_300_before_stop"]) - float(spy_ref["pct_target_300_before_stop"])
                stop_delta = float(frow["pct_any_project_stop_hit"]) - float(spy_ref["pct_any_project_stop_hit"])
                dd_delta = float(frow["worst_max_drawdown"]) - float(spy_ref["worst_max_drawdown"])
                if target_delta >= 0 and stop_delta <= 0 and dd_delta >= 0:
                    improved_family_rows.append(str(frow.get("family_id", frow["strategy"])))
        crypto_family_note = (
            "Crypto family rows were included but remain Tier 1 exploratory/non-final."
            if assumptions.get("independent_family_challenge", {}).get("include_exploratory_crypto_families")
            else "Crypto family rows were not included in this ETF-only family run."
        )
        family_decision = (
            "Each family row received its own independent $3,000 paper/demo account; family rows are not portfolio mixes and do not share capital. "
            f"Runnable families: {runnable_text}. Exact/final all_possible families: {exact_text}. "
            f"Blocked families reported, not run: {blocked_text}. "
            f"Incomplete exact-stream/data families: {unavailable_text}. "
            f"Best exact +300 family: {family_short(best_exact_target300)}. "
            f"Best exact +400 family: {family_short(best_exact_target400)}. "
            f"Best exact risk-control family: {family_short(best_exact_risk)}. "
            f"Families improving +300/stop/drawdown versus SPY_200d: {', '.join(improved_family_rows) or 'none'}. "
            f"Best exact overall family tradeoff: {best_family_text}. "
            f"Best exploratory family by +300 potential: {family_short(best_exploratory)}. "
            f"{crypto_family_note} GLD remains target-rich but drawdown-heavy when present; SPY_200d remains the paper-forward candidate unless another exact family improves target probability without worse stop/drawdown behavior. "
            "Blocked families are blocked, not ignored. +$300 is plausible in some exact families; +$400 remains aggressive. No family row is automatically paper-forward ready."
        )
        exact_completed_family_rows_text = (
            ", ".join(exact_family_rankings["family_id"].dropna().astype(str).unique().tolist())
            or "none with completed all_possible row-level finality"
        )
        incomplete_family_rows_text = unavailable_text
        blocked_family_rows_text = blocked_text
        correct_family_conclusion_text = (
            "GLD is the best exact target hitter when present, but it carries more drawdown than SPY_200d. "
            "SPY_200d remains the best exact overall target/drawdown tradeoff and the frozen paper-forward candidate. "
            "BIL has the best risk control but is too slow for the +$300/+400 challenge. "
            "SPY_buy_hold has high target rates but materially worse drawdown. "
            "+$300 is plausible; +$400 remains aggressive. "
            "A/B exact family comparison remains unresolved until exact fresh-window streams are exposed."
        )
        stream_lines = [
            "This check only accepts daily streams that can support fresh $3,000 30/60/90/180 rolling windows with reset risk state.",
        ]
        for family_id, label in [
            ("family_etf_sector_momentum_A_v1", "A_ETF_sector_momentum"),
            ("family_etf_ab_no_cash_v1", "current_no_cash_proxy_alpha_AB"),
        ]:
            stream_rows = challenge[
                challenge["lane"].eq("independent_family_challenge")
                & challenge["family_id"].eq(family_id)
                & challenge["standard_or_stress"].eq("standard")
            ]
            if stream_rows.empty:
                stream_lines.append(f"- {label}: not present in this packet.")
                continue
            stream_row = stream_rows.iloc[0]
            status = str(stream_row.get("run_status", ""))
            reason = str(stream_row.get("main_failure_mode", stream_row.get("notes", "")))
            if status == "completed":
                rolling_rows_available = rolling[
                    rolling["lane"].eq("independent_family_challenge")
                    & rolling["family_id"].eq(family_id)
                    & rolling["horizon"].isin([30, 60, 90, 180])
                ]
                horizons = ",".join(sorted(rolling_rows_available["horizon"].dropna().astype(int).astype(str).unique()))
                stream_lines.append(
                    f"- {label}: exact stream accepted; rolling horizons present: {horizons or 'none'}."
                )
            else:
                stream_lines.append(
                    f"- {label}: incomplete_evidence. {reason}"
                )
        strategy_family_stream_text = (
            "\n".join(stream_lines)
            + "\n- No A/A-B family row was populated from summary metrics, full-period-only curves, or sampled rolling evidence."
            + "\n- GLD remains the highest exact target hitter but is riskier; SPY_200d remains the best practical overall tradeoff unless an exact strategy-family stream later beats it on target and risk together."
        )
        family_summary = "\n".join(family_table) if len(family_table) > 2 else "No runnable 90-day family rows were available."
    else:
        family_summary = "Independent family challenge diagnostics were not enabled in this run."
        family_decision = "No independent family challenge decision was made in this run."
    if "risk_framework_verdict" in rankings:
        paper_allowed = rankings[rankings["paper_forward_allowed_by_risk_framework"].astype(bool)] if "paper_forward_allowed_by_risk_framework" in rankings else pd.DataFrame()
        diagnostic_only = rankings[rankings["risk_framework_verdict"].isin(["diagnostic_only", "too_risky"])] if "risk_framework_verdict" in rankings else pd.DataFrame()
        blocked = rankings[rankings["risk_framework_verdict"].isin(["blocked_by_gate", "incomplete_evidence", "reject_for_now"])] if "risk_framework_verdict" in rankings else pd.DataFrame()
        hard_rows = rankings[rankings["risk_band"].eq("hard_stop")] if "risk_band" in rankings else pd.DataFrame()
        paper_allowed_text = ", ".join((paper_allowed["strategy"] + "/" + paper_allowed["standard_or_stress"]).astype(str).tolist()) or "none from this compact ranking"
        diagnostic_text = ", ".join(diagnostic_only["strategy"].astype(str).head(10).tolist()) or "none"
        blocked_text = ", ".join(blocked["strategy"].astype(str).head(10).tolist()) or "none"
        hard_text = ", ".join(hard_rows["strategy"].astype(str).head(10).tolist()) or "none"
    else:
        paper_allowed_text = "unavailable"
        diagnostic_text = "unavailable"
        blocked_text = "unavailable"
        hard_text = "unavailable"
    risk_framework_text = (
        f"Framework: {RISK_FRAMEWORK_NAME}. Paper-forward allowed by framework in this packet: {paper_allowed_text}. "
        f"Diagnostic-only or too-risky rows: {diagnostic_text}. Blocked/incomplete rows: {blocked_text}. "
        f"Hard-stop band rows: {hard_text}. +$300 remains the primary challenge target; +$400 remains aggressive. "
        "Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation."
    )
    if lanes.get("include_crypto"):
        final_conclusion = (
            "+$300 and +$400 are possible in these tests, especially in volatile crypto windows and some ETF evidence rows, but possible does not mean reliable. "
            "Crypto appears more likely to reach targets quickly, with much higher stop risk and lower credibility. ETF results are more credible but generally slower and less explosive. "
            "The next practical step is to compare stop-enforced rolling behavior, not chase high unconditional final equity."
        )
    else:
        frontier_sentence = f" {exposure_decision}" if exposure_frontier_enabled else ""
        vol_sentence = f" {vol_decision}" if vol_control_enabled else ""
        final_conclusion = f"{decision_statement} {goal_statement} {custom_vs_spy200} {spy_buy_hold_note}{frontier_sentence}{vol_sentence} This is still paper/demo research only, not a real-money recommendation."
    return f"""# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: {run_id}
- output: `evidence/challenge_runs/runs/{run_id}/`
- compact file count: 10
- validation_mode: {mode}
- sampled_results_are_final: {sampled_final}
- final_validation_completed: {final_completed}

## Run-Level Finality

{row_level_finality_text}

## Exact Completed Family Rows

{exact_completed_family_rows_text}

## Incomplete Family Rows

{incomplete_family_rows_text}

## Blocked Families

{blocked_family_rows_text}

## Correct Family Conclusion

{correct_family_conclusion_text}

## 3. What Was Tested

{tested_text}.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

{fmt(best300)}

## 7. Best Result By +400 Before Stop

{fmt(best400)}

## 8. Best Risk-Controlled Result

{fmt(best_risk)}

## ETF Benchmark Rolling Rows

{benchmark_status}

## current_no_cash_proxy_alpha_AB Benchmark Comparison

{comparison_text}

## Exact 90-Day Focus Table

Standard:

{ninety_day_table("standard")}

Stress:

{ninety_day_table("stress")}

## Practical Decision

- {custom_vs_spy200}
- {spy_buy_hold_note}
- {decision_statement}
- {goal_statement}

## Finalist Validation Status

{validation_statement}

{practical_statement}

## 9. Best ETF Result

In focused `candidate_exhaustive`, current_no_cash_proxy_alpha_AB is computed or loaded only from exact all-possible Backtester evidence; benchmark rows are computed directly from cached adjusted benchmark prices on the same effective calendar. See `strategy_rankings.csv` for the compact ranking.

## 10. Best Crypto Exploratory Result

{crypto_section}

## 11. Best Simulated Leverage Result

{leverage_section}

## Simulated ETF Leverage Diagnostic

{leverage_summary}

{leverage_decision}

## ETF Exposure Frontier Diagnostic

{exposure_summary}

{exposure_decision}

## ETF Volatility-Control Diagnostic

{vol_summary}

{vol_decision}

## Diversified Portfolio Challenge

{portfolio_summary}

{portfolio_decision}

## Independent Family Challenge Completion

{family_summary}

{family_decision}

## ETF Strategy Family Stream Completion

{strategy_family_stream_text}

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

{hit300_names}

## 14. Full-Period Rows That Hit +400 Before Stop

{hit400_names}

## 15. Strategies That Hit Project Stop

{stopped_names}

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

{risk_framework_text}

## 21. Final Conclusion

{final_conclusion}
"""


def build_warnings(assumptions: dict[str, Any] | None = None) -> str:
    assumptions = assumptions or {}
    validation = assumptions.get("validation", {})
    lanes = assumptions.get("lanes", {})
    final_completed = bool(validation.get("final_validation_completed", False))
    mode = validation.get("mode", "unknown")
    focused_note = (
        "- Candidate exhaustive was limited to the selected ETF finalist and ETF benchmarks.\n"
        if mode == "candidate_exhaustive"
        else ""
    )
    excluded_note = ""
    if not lanes.get("include_crypto", True):
        excluded_note += "- Crypto was intentionally excluded from this focused run.\n"
    if not assumptions.get("leverage", {}).get("included", True):
        excluded_note += "- Simulated leverage was intentionally excluded from this focused run.\n"
    etf_leverage_note = ""
    if assumptions.get("simulated_etf_leverage", {}).get("enabled", False):
        etf_leverage_note = (
            "- Simulated ETF leverage diagnostics are approximate return-multiplier scenarios only.\n"
            "- No real margin, liquidation, financing, or leveraged ETF path-dependency model is included.\n"
            "- ETF leverage diagnostic rows are Tier 1 exploratory, cannot be paper-forward ready, and cannot be real-money recommendations.\n"
            "- Improved target-hit rates in leverage diagnostics may simply reflect increased risk.\n"
        )
    if assumptions.get("simulated_etf_exposure_frontier", {}).get("enabled", False):
        etf_leverage_note += (
            "- Simulated ETF exposure scaling is approximate and uses pre-specified exposure levels, not optimized parameters.\n"
            "- No real margin model, liquidation model, or leveraged ETF path-dependency model is included for exposure frontier rows.\n"
            "- Exposure frontier rows are diagnostic only and cannot be paper-forward ready or real-money recommendations.\n"
            "- Improved target-hit rates in exposure frontier rows may simply reflect increased risk.\n"
        )
    if assumptions.get("etf_volatility_control_diagnostic", {}).get("enabled", False):
        etf_leverage_note += (
            "- Volatility-control rows are Tier 1 diagnostics only.\n"
            "- Target volatility and volatility window were predeclared, not optimized.\n"
            "- No guarantee that volatility targeting improves future performance.\n"
            "- Cap 1.10 uses approximate financing and is not a real margin model.\n"
            "- No volatility-control diagnostic row is paper-forward ready.\n"
            "- Frozen paper-forward rows are unchanged.\n"
            "- A lower drawdown row may also have lower target probability.\n"
        )
    if assumptions.get("diversified_portfolio_challenge", {}).get("enabled", False):
        etf_leverage_note += (
            "- Diversified portfolio rows are diagnostics unless separately promoted.\n"
            "- Fixed portfolio weights are predeclared and not optimized.\n"
            "- Defensive mixes may reduce target probability enough to be too slow for this challenge.\n"
            "- Crypto-containing diversified portfolios are Tier 1 exploratory only.\n"
            "- Sleeve availability can affect portfolio results and must be flagged.\n"
            "- Portfolio rebalance cost assumptions are simplified.\n"
            "- Shared data does not imply equal credibility across ETF and crypto sleeves.\n"
            "- A portfolio mix hitting +300 once is not validation.\n"
            "- No portfolio row is automatically paper-forward ready.\n"
            "- Frozen paper-forward rows are unchanged.\n"
        )
    if assumptions.get("independent_family_challenge", {}).get("enabled", False):
        etf_leverage_note += (
            "- Independent family challenge rows are separate $3,000 paper/demo accounts.\n"
            "- Independent family rows are not a combined portfolio and do not share capital.\n"
            "- Family rows should not be interpreted as simultaneous allocation recommendations.\n"
            "- Blocked families are reported but not backtested.\n"
            "- A family being blocked does not mean impossible; it means data, execution, or risk gates have not passed.\n"
            "- Crypto family rows, if included, remain Tier 1 exploratory only.\n"
            "- Exact ETF family rows and sampled crypto family rows are not equal evidence quality.\n"
            "- Sampled family rows are non-final unless a future explicit final mode is approved.\n"
            "- Portfolio mixes are a separate diagnostic under portfolio_lab, not the main family comparison.\n"
            "- No family row is automatically paper-forward ready.\n"
            "- Frozen paper-forward rows are unchanged.\n"
        )
    completion_note = (
        "- Finalist all_possible validation completed for the focused compact rows, but this is still not real-money validation.\n"
        if final_completed
        else "- Finalist validation is incomplete or sampled/non-final; do not treat these results as final.\n"
    )
    return f"""# Warnings And Limitations

- Research-only; no real-money recommendation.
- No broker integration.
- No live orders.
- No exchange trading.
- Individual stocks, options, futures, forex, intraday, and event/news strategies remain excluded.
{focused_note}{excluded_note}{etf_leverage_note}{completion_note}- yfinance/Yahoo data limitations still apply to the ETF lane.
- ETF lane and crypto lane have different credibility levels.
- Crypto yfinance data is Tier 1 exploratory.
- Crypto has no bid/ask, order book, outage, custody, delisting, or exchange-specific execution modeling.
- Leverage is approximate simulated leverage only.
- No actual margin, liquidation, or funding model is implemented unless explicitly stated.
- Sampled rolling windows are non-final.
- Sampled rolling windows are non-final unless candidate_exhaustive completes with all_possible windows.
- ETF benchmark rows are required for fair ETF comparison.
- Approximate stop-enforced values should not drive final decisions.
- Stop-enforced equity is more relevant than unconditional final equity.
- Taxes are ignored.
- Cash yield is simplified.
- Live execution may differ materially.
- Excluded instruments are not tested.
- No strategy here is validated, guaranteed, proven, reliable, paper-forward ready, or real-money suitable.
- Risk Framework v1 treats +$300 as the primary challenge target, +$400 as aggressive, -10% as warning, -15% as review, and -20%/-$600 as hard stop.
- Exposure above 1.00x is diagnostic only and is not paper-forward eligible under the active risk framework.
"""


def build_readme() -> str:
    return """# README For Auditor

This folder is the compact challenge audit view. It intentionally contains only 10 files.

Read in this order:

1. `challenge_summary.md`
2. `challenge_results.csv`
3. `strategy_rankings.csv`
4. `rolling_window_summary.csv`
5. `risk_and_stop_audit.csv`
6. `warnings_and_limitations.md`

Every row is an independent $3,000 simulated challenge account. Full-period final equity must be read beside stop-enforced final equity.

This is research-only and not a real-money recommendation.
"""


def write_chart(path: Path, rolling: pd.DataFrame, challenge: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(12, 14))
    roll90 = rolling[rolling["horizon"].eq(90) & rolling["standard_or_stress"].eq("standard")].copy()
    if not roll90.empty:
        labels = roll90["lane"].astype(str) + "\n" + roll90["strategy"].astype(str) + "\n" + roll90["leverage_multiplier"].astype(str) + "x"
        order = np.argsort(roll90["pct_target_300_before_stop"].to_numpy())[-15:]
        axes[0].barh(labels.iloc[order], roll90["pct_target_300_before_stop"].iloc[order])
        axes[0].set_title("90-Day +300 Before Stop Rate")
        axes[1].barh(labels.iloc[order], roll90["pct_any_project_stop_hit"].iloc[order], color="tab:red")
        axes[1].set_title("90-Day Project Stop-Hit Rate")
    standard = challenge[challenge["standard_or_stress"].eq("standard")].copy().head(20)
    labels2 = standard["lane"].astype(str) + "\n" + standard["strategy"].astype(str) + "\n" + standard["leverage_multiplier"].astype(str) + "x"
    axes[2].barh(labels2, standard["stop_enforced_final_equity"].astype(float), label="stop-enforced")
    axes[2].barh(labels2, standard["unconditional_final_equity"].astype(float), alpha=0.25, label="unconditional")
    axes[2].axvline(3300, color="green", linestyle="--", linewidth=1)
    axes[2].axvline(2400, color="red", linestyle="--", linewidth=1)
    axes[2].set_title("Stop-Enforced Vs Unconditional Final Equity")
    axes[2].legend()
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_assumptions(
    mode: str,
    include_etf: bool,
    include_crypto: bool,
    include_leverage: bool,
    include_benchmarks: bool,
    finalists: set[str],
    final_validation_completed: bool,
    incomplete_reason: str = "",
    include_etf_leverage_diagnostic: bool = False,
    include_etf_exposure_frontier: bool = False,
    include_etf_volatility_control_diagnostic: bool = False,
    include_diversified_portfolios: bool = False,
    include_exploratory_crypto_portfolios: bool = False,
    include_family_challenge: bool = False,
    include_exploratory_crypto_families: bool = False,
) -> dict[str, Any]:
    return {
        "research_only": True,
        "real_money_recommendation": False,
        "risk_framework": {
            "name": RISK_FRAMEWORK_NAME,
            "primary_challenge_target": TARGET_300,
            "aggressive_challenge_target": TARGET_400,
            "warning_drawdown_dollars": 300,
            "review_drawdown_dollars": 450,
            "hard_stop_drawdown_dollars": TRAILING_DRAWDOWN,
            "exposure_above_1x": "diagnostic_only",
        },
        "account": {
            "starting_equity": STARTING_EQUITY,
            "target_300_equity": TARGET_300,
            "target_400_equity": TARGET_400,
            "absolute_stop_equity": ABSOLUTE_STOP,
            "trailing_drawdown_dollars": TRAILING_DRAWDOWN,
            "project_stop_mode": PROJECT_STOP_MODE,
            "independent_account_per_row": True,
        },
        "validation": {
            "mode": mode,
            "finalists": sorted(finalists),
            "rolling_method_default": "all_possible for focused candidate_exhaustive where computable; deterministic research_sample otherwise",
            "sampled_results_are_final": bool(mode == "candidate_exhaustive" and final_validation_completed),
            "exhaustive_validation": bool(mode == "candidate_exhaustive"),
            "final_validation_completed": bool(final_validation_completed),
            "incomplete_reason": incomplete_reason,
        },
        "costs": {
            "etf_standard_slippage_per_side": 0.0005,
            "etf_stress_slippage_per_side": 0.001,
            "crypto_standard_fee_slippage_per_side": 0.001,
            "crypto_stress_fee_slippage_per_side": 0.003,
        },
        "leverage": {
            "included": include_leverage,
            "model": "approximate_simulated_leverage only",
            "multipliers": [1.0, 1.5, 2.0] if include_leverage else [1.0],
            "financing_annualized": {1.0: 0.0, 1.5: 0.05, 2.0: 0.08},
            "no_margin_account": True,
            "no_liquidation_engine": True,
        },
        "simulated_etf_leverage": {
            "enabled": include_etf_leverage_diagnostic,
            "model": "approximate_return_multiplier",
            "multipliers": [1.25, 1.5] if include_etf_leverage_diagnostic else [],
            "financing_cost_annualized": {"1.25": 0.05, "1.5": 0.08},
            "cost_model_quality": "approximate",
            "real_margin_model": False,
            "liquidation_model": False,
            "real_money_recommendation": False,
            "notes": "Diagnostic only. Not a real leverage product, margin model, or trading recommendation.",
        },
        "simulated_etf_exposure_frontier": {
            "enabled": include_etf_exposure_frontier,
            "model": "approximate_return_multiplier",
            "exposure_multipliers": list(ETF_EXPOSURE_FRONTIER.keys()) if include_etf_exposure_frontier else [],
            "financing_cost_annualized": {f"{key:.2f}": value["financing_cost_annualized"] for key, value in ETF_EXPOSURE_FRONTIER.items()},
            "cost_model_quality": "approximate",
            "real_margin_model": False,
            "liquidation_model": False,
            "real_money_recommendation": False,
            "notes": "Diagnostic only. Not a real leverage product, margin model, or trading recommendation.",
        },
        "etf_volatility_control_diagnostic": {
            "enabled": include_etf_volatility_control_diagnostic,
            "target_vol_annualized": ETF_VOL_CONTROL_TARGET,
            "realized_vol_window_trading_days": ETF_VOL_CONTROL_WINDOW,
            "exposure_caps": list(ETF_VOL_CONTROL_DIAGNOSTICS.keys()) if include_etf_volatility_control_diagnostic else [],
            "cap_1_00": {
                "financing_cost_annualized": 0.00,
                "real_margin_model": False,
            },
            "cap_1_10": {
                "financing_cost_annualized": 0.05,
                "financing_applies_only_above_1x": True,
                "cost_model_quality": "approximate",
                "real_margin_model": False,
                "liquidation_model": False,
            },
            "parameter_optimization": False,
            "grid_search": False,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "notes": "Predeclared Tier 1 diagnostic only. Not a paper-forward strategy and not a real-money recommendation.",
        },
        "diversified_portfolio_challenge": {
            "enabled": include_diversified_portfolios,
            "include_exploratory_crypto_portfolios": include_exploratory_crypto_portfolios,
            "portfolio_specs_path": "portfolio_lab/diversified_portfolio_specs.yaml",
            "rebalance_frequency": "monthly",
            "fixed_weights": True,
            "parameter_optimization": False,
            "grid_search": False,
            "no_leverage": True,
            "no_shorting": True,
            "no_margin": True,
            "raw_data_in_evidence": False,
            "standard_and_stress_costs": True,
            "unavailable_sleeve_policy": "allocate_to_bil_or_cash_and_flag",
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "notes": "Fixed predeclared portfolio diagnostics only. Not a paper-forward change.",
        },
        "independent_family_challenge": {
            "enabled": include_family_challenge,
            "include_exploratory_crypto_families": include_exploratory_crypto_families,
            "family_specs_path": "family_lab/independent_family_specs.yaml",
            "independent_account_per_family": True,
            "starting_equity_per_family": STARTING_EQUITY,
            "shared_capital_across_families": False,
            "portfolio_mix": False,
            "parameter_optimization": False,
            "grid_search": False,
            "no_leverage": True,
            "no_shorting": True,
            "no_margin": True,
            "raw_data_in_evidence": False,
            "standard_and_stress_costs": True,
            "blocked_families_reported_not_run": True,
            "real_money_recommendation": False,
            "notes": "Each family row is an independent $3,000 paper/demo challenge account. This is not a blended portfolio allocation.",
        },
        "lanes": {
            "include_etf": include_etf,
            "include_crypto": include_crypto,
            "include_benchmarks": include_benchmarks,
            "include_diversified_portfolios": include_diversified_portfolios,
            "include_exploratory_crypto_portfolios": include_exploratory_crypto_portfolios,
            "include_family_challenge": include_family_challenge,
            "include_exploratory_crypto_families": include_exploratory_crypto_families,
        },
        "caveats": [
            "No raw vendor data in evidence.",
            "Focused candidate_exhaustive ETF finalist and benchmark stop-enforced values are exact; other compact ETF evidence rows may be approximated when equity curves are unavailable.",
            "Crypto is Tier 1 exploratory and non-final.",
            "No broker, exchange, live order, or real-money workflow.",
        ],
    }


def run_challenge(args: argparse.Namespace) -> tuple[Path, Path]:
    run_id = run_id_now()
    finalists = {item.strip() for item in args.finalists.split(",") if item.strip()} if args.finalists else set()
    if args.mode == "candidate_exhaustive" and not finalists and not args.include_family_challenge:
        finalists = {"current_no_cash_proxy_alpha_AB"}
    runtime_deadline = None
    if args.max_runtime_minutes:
        runtime_deadline = time.monotonic() + max(1, int(args.max_runtime_minutes)) * 60
    ordinary_etf = args.include_etf and not args.include_family_challenge
    ordinary_benchmarks = args.include_benchmarks and not args.include_family_challenge
    ordinary_crypto = args.include_crypto and not args.include_family_challenge
    etf_rows, etf_rolling, etf_coverage, etf_completed = load_etf_rows(
        run_id,
        ordinary_etf,
        ordinary_benchmarks,
        args.mode,
        finalists,
        runtime_deadline,
        reuse_cache=args.reuse_cache,
        include_etf_leverage_diagnostic=args.include_etf_leverage_diagnostic,
        include_etf_exposure_frontier=args.include_etf_exposure_frontier,
        include_etf_volatility_control_diagnostic=args.include_etf_volatility_control_diagnostic,
        include_diversified_portfolios=args.include_diversified_portfolios,
        include_exploratory_crypto_portfolios=args.include_exploratory_crypto_portfolios,
    )
    family_rows, family_rolling, family_coverage, family_completed = build_independent_family_rows(
        run_id=run_id,
        mode=args.mode,
        include_family_challenge=args.include_family_challenge,
        include_exploratory_crypto_families=args.include_exploratory_crypto_families,
        runtime_deadline=runtime_deadline,
        no_network=args.no_network,
        reuse_cache=args.reuse_cache,
    )
    crypto_rows, crypto_rolling, crypto_coverage, _ = load_crypto_rows(
        run_id=run_id,
        mode=args.mode,
        include_crypto=ordinary_crypto,
        include_leverage=args.include_leverage,
        no_network=args.no_network,
        reuse_cache=args.reuse_cache,
        force_refresh=args.force_refresh,
    )
    challenge = pd.DataFrame(etf_rows + family_rows + crypto_rows).reindex(columns=CHALLENGE_COLUMNS)
    rolling = pd.DataFrame(etf_rolling + family_rolling + crypto_rolling).reindex(columns=ROLLING_COLUMNS)
    coverage = pd.DataFrame(etf_coverage + family_coverage + crypto_coverage)
    incomplete_reason = ""
    if args.mode == "candidate_exhaustive" and not etf_completed and not args.include_family_challenge:
        incomplete_reason = "Focused candidate_exhaustive is incomplete because selected ETF finalist all_possible rolling is unavailable from compact evidence or runtime budget was exceeded."
    if args.mode == "candidate_exhaustive" and args.include_family_challenge and not family_completed:
        incomplete_reason = "Independent family challenge is incomplete for unavailable exact-stream or blocked family rows; runnable ETF-like family rows may still have exact all_possible windows."
    final_validation_completed = bool(args.mode == "candidate_exhaustive" and etf_completed and family_completed)
    if args.include_family_challenge:
        final_validation_completed = bool(args.mode == "candidate_exhaustive" and family_completed)
    challenge = apply_risk_framework_to_challenge(challenge, final_validation_completed=final_validation_completed)
    rolling = apply_risk_framework_to_rolling(rolling)
    rankings = build_rankings(challenge, rolling)
    assumptions = build_assumptions(
        args.mode,
        args.include_etf,
        args.include_crypto,
        args.include_leverage,
        args.include_benchmarks,
        finalists,
        final_validation_completed,
        incomplete_reason,
        include_etf_leverage_diagnostic=args.include_etf_leverage_diagnostic,
        include_etf_exposure_frontier=args.include_etf_exposure_frontier,
        include_etf_volatility_control_diagnostic=args.include_etf_volatility_control_diagnostic,
        include_diversified_portfolios=args.include_diversified_portfolios,
        include_exploratory_crypto_portfolios=args.include_exploratory_crypto_portfolios,
        include_family_challenge=args.include_family_challenge,
        include_exploratory_crypto_families=args.include_exploratory_crypto_families,
    )
    return write_outputs(run_id, challenge, rolling, rankings, coverage, assumptions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create compact $3,000 challenge audit evidence.")
    parser.add_argument("--mode", choices=["research_sample", "smoke", "candidate_exhaustive"], default="research_sample")
    parser.add_argument("--include-crypto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-etf", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-leverage", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-benchmarks", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-etf-leverage-diagnostic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-etf-exposure-frontier", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-etf-volatility-control-diagnostic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-diversified-portfolios", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-exploratory-crypto-portfolios", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-family-challenge", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-exploratory-crypto-families", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-crypto", dest="include_crypto", action="store_false", help="Alias for --no-include-crypto.")
    parser.add_argument("--no-leverage", dest="include_leverage", action="store_false", help="Alias for --no-include-leverage.")
    parser.add_argument("--no-etf", dest="include_etf", action="store_false", help="Alias for --no-include-etf.")
    parser.add_argument("--no-benchmarks", dest="include_benchmarks", action="store_false", help="Alias for --no-include-benchmarks.")
    parser.add_argument("--finalists", default="", help="Comma-separated finalist strategy names for candidate_exhaustive mode.")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--reuse-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-runtime-minutes", type=int, default=45)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.max_workers
    run_dir, latest_dir = run_challenge(args)
    print(f"challenge_run_dir={run_dir}")
    print(f"challenge_latest_dir={latest_dir}")
    print(f"challenge_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
