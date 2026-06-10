from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import math
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtester import Backtester, BacktestResult
from .metrics import cagr, consecutive_losses, expectancy, max_drawdown, profit_factor, sharpe_ratio, sortino_ratio
from .portfolio import is_backtest_strategy
from .risk import compute_target_timing, evaluate_project_stop, project_stop_config
from .strategies import A, B, C, D, E, N1, N2, N3, N4
from .utils import refresh_latest, sha256_file, write_json


MAIN_STRATEGIES = [A, B, C, D, E]
EVIDENCE_STRATEGIES = [N1, N2, N3, N4]
STRATEGY_ORDER_ALL = [A, B, C, E, D, N1, N2, N3, N4]


VARIANTS = {
    "original_full_tournament": MAIN_STRATEGIES,
    "current_no_cash_proxy_alpha_AB": [A, B],
    "current_core_only_AB": [A, B],
    "current_momentum_only_A": [A],
    "trend_only_B": [B],
    "satellites_only_CDE": [C, D, E],
    "evidence_dual_momentum_taa": [N1],
    "evidence_absolute_trend_taa": [N2],
    "evidence_dual_momentum_vol_scaled": [N3],
    "evidence_inverse_vol_defensive": [N4],
    "evidence_core_combo": [N1, N2],
}

ROLLING_CANDIDATE_VARIANTS = (
    "current_no_cash_proxy_alpha_AB",
    "current_core_only_AB",
    "current_momentum_only_A",
    "original_full_tournament",
    "evidence_dual_momentum_taa",
    "evidence_absolute_trend_taa",
    "evidence_dual_momentum_vol_scaled",
    "evidence_inverse_vol_defensive",
    "evidence_core_combo",
)

DEFAULT_VALIDATION_MODES: dict[str, dict[str, Any]] = {
    "smoke": {
        "purpose": "Fast code correctness check. Not research evidence.",
        "variants": ["current_no_cash_proxy_alpha_AB", "evidence_dual_momentum_taa"],
        "slippage_labels": ["standard"],
        "horizons": [90],
        "rolling_method": "deterministic_stratified_sample",
        "sample_size_per_group": 24,
        "mark_as_final": False,
    },
    "research_sample": {
        "purpose": "Preliminary research screen. Useful but non-final.",
        "variants": [
            "current_no_cash_proxy_alpha_AB",
            "current_core_only_AB",
            "current_momentum_only_A",
            "evidence_dual_momentum_taa",
            "evidence_absolute_trend_taa",
            "evidence_dual_momentum_vol_scaled",
            "evidence_inverse_vol_defensive",
            "evidence_core_combo",
        ],
        "slippage_labels": ["standard", "stress"],
        "horizons": [90, 180],
        "rolling_method": "deterministic_stratified_sample",
        "sample_size_per_group": 500,
        "mark_as_final": False,
    },
    "candidate_exhaustive": {
        "purpose": "All-possible validation for finalists only.",
        "variants": [
            "current_no_cash_proxy_alpha_AB",
            "evidence_dual_momentum_taa",
            "evidence_dual_momentum_vol_scaled",
            "evidence_core_combo",
        ],
        "slippage_labels": ["standard", "stress"],
        "horizons": [30, 60, 90, 180],
        "rolling_method": "all_possible",
        "mark_as_final": True,
    },
    "nightly_full_exhaustive": {
        "purpose": "Slow archival audit. Run manually only.",
        "variants": "all",
        "slippage_labels": ["standard", "stress"],
        "horizons": [30, 60, 90, 180],
        "rolling_method": "all_possible",
        "mark_as_final": True,
    },
}

_ROLLING_WORKER_DATA: dict[str, pd.DataFrame] | None = None
_ROLLING_WORKER_CONFIG: dict[str, Any] | None = None
_ROLLING_WORKER_DATES: list[pd.Timestamp] | None = None


def validation_mode_settings(config: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    validation_cfg = config.get("validation", {})
    selected = mode or validation_cfg.get("mode") or "research_sample"
    if selected not in DEFAULT_VALIDATION_MODES:
        raise ValueError(f"Unknown validation mode: {selected}")
    settings = copy.deepcopy(DEFAULT_VALIDATION_MODES[selected])
    configured = validation_cfg.get("modes", {}).get(selected, {})
    if configured:
        settings.update(configured)
    settings["mode"] = selected
    settings["sampled_results_are_final"] = bool(
        settings.get("mark_as_final", False) and settings.get("rolling_method") == "all_possible"
    )
    return settings


def apply_validation_mode(config: dict[str, Any], mode: str) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    cfg.setdefault("validation", {})["mode"] = mode
    settings = validation_mode_settings(cfg, mode)
    rolling_cfg = cfg.setdefault("rolling_validation", {})
    rolling_cfg["method"] = settings["rolling_method"]
    rolling_cfg["max_windows_per_group"] = (
        None if settings["rolling_method"] == "all_possible" else int(settings.get("sample_size_per_group", 0))
    )
    return cfg


def _stable_hash_obj(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def data_fingerprint(data: dict[str, pd.DataFrame]) -> str:
    rows: list[dict[str, Any]] = []
    for symbol, frame in sorted(data.items()):
        if frame.empty or "date" not in frame:
            rows.append({"symbol": symbol, "rows": 0})
            continue
        close = frame["close"].dropna() if "close" in frame else pd.Series(dtype=float)
        rows.append(
            {
                "symbol": symbol,
                "rows": int(len(frame)),
                "first_date": str(pd.to_datetime(frame["date"]).min().date()),
                "last_date": str(pd.to_datetime(frame["date"]).max().date()),
                "last_close": float(close.iloc[-1]) if not close.empty else None,
            }
        )
    return _stable_hash_obj(rows)


def strategy_variant_config(config: dict[str, Any], variant_name: str) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    enabled = set(VARIANTS[variant_name])
    for strategy, strategy_cfg in cfg["strategies"].items():
        if not strategy.startswith(("F_", "G_")):
            strategy_cfg["enabled"] = strategy in enabled
    cfg["strategy_order"] = [s for s in STRATEGY_ORDER_ALL if s in enabled]
    if variant_name in {"current_no_cash_proxy_alpha_AB", "no_cash_proxy_alpha_AB"}:
        cfg["universe"]["symbols"] = [s for s in cfg["universe"]["symbols"] if s not in {"BIL", "SHY"}]
    return cfg


def _top_5_trade_contribution_pct(trades: pd.DataFrame) -> float:
    if trades.empty or trades["pnl"].sum() == 0:
        return np.nan
    positive = trades.loc[trades["pnl"] > 0, "pnl"].sort_values(ascending=False)
    denom = positive.sum()
    if denom <= 0:
        return np.nan
    return float(positive.head(5).sum() / denom)


def _best_worst_strategy_by_pnl(trades: pd.DataFrame) -> tuple[str, str]:
    if trades.empty:
        return "", ""
    pnl = trades.groupby("strategy")["pnl"].sum().sort_values()
    return str(pnl.index[-1]), str(pnl.index[0])


def variant_result_row(
    result: BacktestResult,
    variant_name: str,
    enabled_strategies: list[str],
    slippage_label: str,
    slippage_pct: float,
) -> dict[str, Any]:
    combined = result.strategy_metrics.loc[result.strategy_metrics["name"] == "combined_tournament"].iloc[0]
    best, worst = _best_worst_strategy_by_pnl(result.trades)
    meta = result.metadata
    return {
        "variant_name": variant_name,
        "enabled_strategies": ",".join(enabled_strategies),
        "slippage_label": slippage_label,
        "slippage_pct_per_side": slippage_pct,
        "final_equity": combined["final_equity"],
        "total_return": combined["total_return"],
        "cagr": combined["cagr"],
        "max_drawdown_dollars": combined["max_drawdown"],
        "max_drawdown_pct": combined["max_drawdown_pct"],
        "number_of_trades": combined["number_of_trades"],
        "profit_factor": combined["profit_factor"],
        "expectancy_per_trade_dollars": combined["expectancy_per_trade_dollars"],
        "expectancy_per_trade_r": combined["expectancy_per_trade_r"],
        "win_rate": combined["win_rate"],
        "target_300_hit": meta.get("target_300_hit", False),
        "target_300_before_any_stop": meta.get("target_300_before_any_stop", False),
        "target_400_hit": meta.get("target_400_hit", False),
        "target_400_before_any_stop": meta.get("target_400_before_any_stop", False),
        "absolute_floor_stop_hit": meta.get("absolute_floor_stop_hit", False),
        "trailing_drawdown_stop_hit": meta.get("trailing_drawdown_stop_hit", False),
        "any_project_stop_hit": meta.get("any_project_stop_hit", meta.get("project_stop_hit", False)),
        "first_project_stop_date": meta.get("first_project_stop_date", ""),
        "strategies_killed": ",".join(result.killed_strategies),
        "top_5_trade_pnl_contribution_pct": _top_5_trade_contribution_pct(result.trades),
        "best_strategy_by_pnl": best,
        "worst_strategy_by_pnl": worst,
        "suitable_for_forward_paper_test": "",
        "forward_test_decision_reason": "",
        "evidence_family": "",
        "evidence_strength": "",
        "primary_failure_mode": "",
        "recommended_status": "",
    }


def run_strategy_variants(
    data: dict[str, pd.DataFrame],
    config: dict[str, Any],
    variant_names: list[str] | tuple[str, ...] | None = None,
    slippage_labels: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    if slippage_labels is not None:
        slippages = {label: slippages[label] for label in slippage_labels if label in slippages}
    selected_variants = list(variant_names) if variant_names is not None else list(VARIANTS.keys())
    if "original_full_tournament" not in selected_variants:
        selected_variants.append("original_full_tournament")
    full = config["date_ranges"]["full"]
    for variant_name in selected_variants:
        if variant_name not in VARIANTS:
            continue
        enabled = VARIANTS[variant_name]
        variant_cfg = strategy_variant_config(config, variant_name)
        backtester = Backtester(data, variant_cfg)
        for label, slippage in slippages.items():
            result = backtester.run("full", str(full["start"]), full.get("end") or config["data"].get("end_date"), slippage)
            rows.append(variant_result_row(result, variant_name, enabled, label, slippage))
    return pd.DataFrame(rows)


def candidate_gate_results(variants: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "variant_name",
        "slippage_label",
        "final_equity",
        "total_return",
        "max_drawdown_dollars",
        "max_drawdown_pct",
        "target_300_before_any_stop",
        "target_400_before_any_stop",
        "any_project_stop_hit",
        "number_of_trades",
        "profit_factor",
        "stress_delta_if_available",
        "passed_gate",
        "gate_status",
        "gate_failure_reasons",
    ]
    if variants.empty:
        return pd.DataFrame(columns=columns)

    stress_delta = {}
    for variant, group in variants.groupby("variant_name"):
        std = group.loc[group["slippage_label"] == "standard", "final_equity"]
        stress = group.loc[group["slippage_label"] == "stress", "final_equity"]
        stress_delta[variant] = float(stress.iloc[0] - std.iloc[0]) if not std.empty and not stress.empty else np.nan

    rows: list[dict[str, Any]] = []
    for _, row in variants.iterrows():
        variant = str(row["variant_name"])
        slippage = str(row["slippage_label"])
        enabled = str(row.get("enabled_strategies", ""))
        reasons: list[str] = []
        status = "pass"
        passed = True

        if variant == "original_full_tournament":
            status = "reference_only"
            reasons.append("legacy full tournament is retained as reference only")
        elif any(strategy in enabled for strategy in [C, D, E]):
            status = "shadow_only"
            passed = False
            reasons.append("variant includes rejected/shadow C/D/E sleeve")
        elif variant == "evidence_inverse_vol_defensive":
            status = "benchmark_only"
            reasons.append("inverse-vol defensive allocation is benchmark/control only")

        profit = row.get("profit_factor", np.nan)
        if status not in {"benchmark_only", "reference_only", "shadow_only"}:
            if slippage == "stress" and float(row.get("final_equity", np.nan)) < 2700:
                passed = False
                status = "fail"
                reasons.append("full-period stress final equity below 2700")
            if pd.notna(profit) and np.isfinite(float(profit)) and float(profit) < 1.0:
                passed = False
                status = "fail"
                reasons.append("profit factor below 1.0")
            delta = stress_delta.get(variant, np.nan)
            if pd.notna(delta) and float(delta) < -150:
                reasons.append("stress slippage materially degraded final equity")

        if status in {"benchmark_only", "reference_only"}:
            passed = True
        rows.append(
            {
                "variant_name": variant,
                "slippage_label": slippage,
                "final_equity": row.get("final_equity", np.nan),
                "total_return": row.get("total_return", np.nan),
                "max_drawdown_dollars": row.get("max_drawdown_dollars", np.nan),
                "max_drawdown_pct": row.get("max_drawdown_pct", np.nan),
                "target_300_before_any_stop": row.get("target_300_before_any_stop", False),
                "target_400_before_any_stop": row.get("target_400_before_any_stop", False),
                "any_project_stop_hit": row.get("any_project_stop_hit", False),
                "number_of_trades": row.get("number_of_trades", 0),
                "profit_factor": profit,
                "stress_delta_if_available": stress_delta.get(variant, np.nan),
                "passed_gate": passed,
                "gate_status": status,
                "gate_failure_reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _rolling_group_allowed(candidate_gate: pd.DataFrame, variant: str, slippage_label: str) -> bool:
    if candidate_gate.empty:
        return True
    row = candidate_gate.loc[
        (candidate_gate["variant_name"] == variant) & (candidate_gate["slippage_label"] == slippage_label)
    ]
    if row.empty:
        return True
    return str(row.iloc[0].get("gate_status", "")) in {"pass", "benchmark_only", "reference_only"}


def add_variant_decisions(variants: pd.DataFrame, independent_summary: pd.DataFrame | None = None) -> pd.DataFrame:
    if variants.empty:
        return variants
    out = variants.copy()
    family_map = {
        "original_full_tournament": "legacy_reference",
        "current_no_cash_proxy_alpha_AB": "current_ab",
        "current_core_only_AB": "current_ab",
        "current_momentum_only_A": "current_a",
        "trend_only_B": "current_b",
        "satellites_only_CDE": "legacy_satellites",
        "evidence_dual_momentum_taa": "evidence_taa",
        "evidence_absolute_trend_taa": "evidence_taa",
        "evidence_dual_momentum_vol_scaled": "evidence_taa",
        "evidence_inverse_vol_defensive": "defensive_benchmark",
        "evidence_core_combo": "evidence_taa_combo",
    }
    for idx, row in out.iterrows():
        variant = row["variant_name"]
        slippage = row["slippage_label"]
        killed = str(row.get("strategies_killed", ""))
        enabled = str(row.get("enabled_strategies", ""))
        reasons: list[str] = []
        status = "watchlist"
        primary_failure = ""
        if variant == "original_full_tournament":
            status = "benchmark_only"
            reasons.append("original full tournament is retained as reference only")
        if any(s in enabled for s in [C, D, E]) and killed:
            status = "shadow_only"
            primary_failure = "legacy_satellites_killed_by_loss_budget"
            reasons.append("variant includes C/D/E and at least one was killed by loss budget")
        if independent_summary is not None and not independent_summary.empty:
            row90 = independent_summary.loc[
                (independent_summary["variant_name"] == variant)
                & (independent_summary["slippage_label"] == slippage)
                & (independent_summary["horizon_trading_days"] == 90)
            ]
            if not row90.empty:
                rate = float(row90.iloc[0]["pct_windows_target_300_before_stop"])
                if rate < 0.10:
                    reasons.append(f"90-day +300 before stop rate is {rate:.2%}, below 10%")
                    primary_failure = primary_failure or "low_90_day_target_300_rate"
                    status = "watchlist" if status not in {"shadow_only", "benchmark_only"} else status
                rate400 = float(row90.iloc[0]["pct_windows_target_400_before_stop"])
                if rate400 < 0.05:
                    reasons.append(f"90-day +400 before stop rate is {rate400:.2%}, below 5%")
                    primary_failure = primary_failure or "low_90_day_target_400_rate"
        pair = out.loc[(out["variant_name"] == variant)]
        if slippage == "stress":
            std = pair.loc[pair["slippage_label"] == "standard", "final_equity"]
            if not std.empty and float(row["final_equity"]) < float(std.iloc[0]) - 150:
                reasons.append("stress slippage materially degrades final equity")
                primary_failure = primary_failure or "stress_slippage_fragility"
                status = "watchlist" if status not in {"shadow_only", "benchmark_only"} else status
        if variant == "evidence_inverse_vol_defensive":
            status = "benchmark_only"
            primary_failure = primary_failure or "defensive_strategy_low_target_engine"
        if not reasons and slippage == "standard":
            status = "watchlist"
            reasons.append("not validated until independent rolling windows show stronger target reliability")
        if variant.startswith("evidence_") and status == "watchlist":
            evidence_strength = "plausible_fixed_rules_needs_forward_paper_test"
        elif status == "benchmark_only":
            evidence_strength = "benchmark_or_reference_only"
        elif status == "shadow_only":
            evidence_strength = "weak_or_shadow_only"
        else:
            evidence_strength = "watchlist"
        out.at[idx, "suitable_for_forward_paper_test"] = status
        out.at[idx, "forward_test_decision_reason"] = "; ".join(reasons)
        out.at[idx, "evidence_family"] = family_map.get(variant, "unknown")
        out.at[idx, "evidence_strength"] = evidence_strength
        out.at[idx, "primary_failure_mode"] = primary_failure
        out.at[idx, "recommended_status"] = status
    return out


def _target_and_stop_for_slice(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    timing = compute_target_timing(frame, config)
    return timing


def build_rolling_window_results(
    result: BacktestResult,
    config: dict[str, Any],
    horizons: tuple[int, ...] = (30, 60, 90, 180),
) -> pd.DataFrame:
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    values = equity["equity"].astype(float).to_numpy()
    dates = equity["date"].to_list()
    rows: list[dict[str, Any]] = []
    trades = result.trades.copy()
    skips = result.skipped_signals.copy()
    if not trades.empty:
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    if not skips.empty:
        skips["date"] = pd.to_datetime(skips["date"])

    for horizon in horizons:
        if len(equity) < horizon:
            continue
        for start_idx in range(0, len(equity) - horizon + 1):
            end_idx = start_idx + horizon - 1
            start_date = dates[start_idx]
            end_date = dates[end_idx]
            base = values[start_idx]
            if not np.isfinite(base) or base <= 0:
                continue
            normalized = values[start_idx : end_idx + 1] / base * float(config["project"]["starting_equity"])
            window = pd.DataFrame({"date": dates[start_idx : end_idx + 1], "equity": normalized})
            window["high_water_mark"] = window["equity"].cummax()
            window["drawdown_dollars"] = window["equity"] - window["high_water_mark"]
            window["drawdown_pct"] = window["equity"] / window["high_water_mark"] - 1.0
            stop_eval_rows = [
                evaluate_project_stop(row.equity, row.high_water_mark, config)
                for row in window.itertuples(index=False)
            ]
            window["absolute_floor_stop_active"] = [r["absolute_floor_stop_active"] for r in stop_eval_rows]
            window["trailing_drawdown_stop_active"] = [r["trailing_drawdown_stop_active"] for r in stop_eval_rows]
            timing = _target_and_stop_for_slice(window, config)
            in_window_trades = (
                trades.loc[(trades["entry_date"] >= start_date) & (trades["entry_date"] <= end_date)]
                if not trades.empty
                else trades
            )
            in_window_skips = (
                skips.loc[(skips["date"] >= start_date) & (skips["date"] <= end_date)] if not skips.empty else skips
            )
            best, worst = _best_worst_strategy_by_pnl(in_window_trades)
            strategy_pnl = in_window_trades.groupby("strategy")["pnl"].sum() if not in_window_trades.empty else pd.Series(dtype=float)
            killed = ",".join(
                sorted(in_window_trades.loc[in_window_trades["exit_reason"] == "strategy_loss_budget", "strategy"].unique())
            ) if not in_window_trades.empty else ""
            rows.append(
                {
                    "window_id": f"{horizon}_{start_idx:05d}",
                    "horizon_trading_days": horizon,
                    "start_date": start_date.date().isoformat(),
                    "end_date": end_date.date().isoformat(),
                    "final_equity": float(window["equity"].iloc[-1]),
                    "total_return": float(window["equity"].iloc[-1] / window["equity"].iloc[0] - 1.0),
                    "max_equity": float(window["equity"].max()),
                    "min_equity": float(window["equity"].min()),
                    "max_drawdown_dollars": float(window["drawdown_dollars"].min()),
                    "max_drawdown_pct": float(window["drawdown_pct"].min()),
                    "target_300_hit": timing.get("target_300_hit", False),
                    "target_300_first_date": timing.get("target_300_first_date", ""),
                    "target_300_trading_days": timing.get("target_300_trading_days", pd.NA),
                    "target_400_hit": timing.get("target_400_hit", False),
                    "target_400_first_date": timing.get("target_400_first_date", ""),
                    "target_400_trading_days": timing.get("target_400_trading_days", pd.NA),
                    "absolute_floor_stop_hit": timing.get("absolute_floor_stop_hit", False),
                    "absolute_floor_stop_date": timing.get("absolute_floor_stop_date", ""),
                    "trailing_drawdown_stop_hit": timing.get("trailing_drawdown_stop_hit", False),
                    "trailing_drawdown_stop_date": timing.get("trailing_drawdown_stop_date", ""),
                    "any_project_stop_hit": timing.get("any_project_stop_hit", False),
                    "first_project_stop_date": timing.get("first_project_stop_date", ""),
                    "first_project_stop_type": timing.get("first_project_stop_type", ""),
                    "target_300_before_any_stop": timing.get("target_300_before_any_stop", False),
                    "target_400_before_any_stop": timing.get("target_400_before_any_stop", False),
                    "number_of_trades": int(len(in_window_trades)),
                    "number_of_skipped_signals": int(len(in_window_skips)),
                    "strategies_killed": killed,
                    "best_strategy_by_pnl": best,
                    "worst_strategy_by_pnl": worst,
                    "ending_open_positions_count": int(equity["open_positions"].iloc[end_idx])
                    if "open_positions" in equity
                    else 0,
                }
            )
    return pd.DataFrame(rows)


def summarize_rolling_windows(rolling: pd.DataFrame) -> pd.DataFrame:
    if rolling.empty:
        return pd.DataFrame()
    grouped = rolling.groupby("horizon_trading_days")
    return grouped.agg(
        number_of_windows=("window_id", "count"),
        median_final_equity=("final_equity", "median"),
        mean_final_equity=("final_equity", "mean"),
        pct_windows_target_300_hit=("target_300_hit", "mean"),
        pct_windows_target_300_before_stop=("target_300_before_any_stop", "mean"),
        pct_windows_target_400_hit=("target_400_hit", "mean"),
        pct_windows_target_400_before_stop=("target_400_before_any_stop", "mean"),
        pct_windows_absolute_stop_hit=("absolute_floor_stop_hit", "mean"),
        pct_windows_trailing_stop_hit=("trailing_drawdown_stop_hit", "mean"),
        pct_windows_any_stop_hit=("any_project_stop_hit", "mean"),
        median_max_drawdown=("max_drawdown_dollars", "median"),
        worst_max_drawdown=("max_drawdown_dollars", "min"),
        median_number_of_trades=("number_of_trades", "median"),
        pct_windows_positive_return=("total_return", lambda s: float((s > 0).mean())),
        pct_windows_loss=("total_return", lambda s: float((s < 0).mean())),
        pct_windows_below_2400=("final_equity", lambda s: float((s < 2400).mean())),
        pct_windows_above_3300=("final_equity", lambda s: float((s >= 3300).mean())),
        pct_windows_above_3400=("final_equity", lambda s: float((s >= 3400).mean())),
    ).reset_index()


def _summary_group_cols(rolling: pd.DataFrame) -> list[str]:
    cols = []
    for col in ["variant_name", "slippage_label", "horizon_trading_days"]:
        if col in rolling:
            cols.append(col)
    return cols or ["horizon_trading_days"]


def summarize_independent_rolling_windows(rolling: pd.DataFrame) -> pd.DataFrame:
    if rolling.empty:
        return pd.DataFrame()
    grouped = rolling.groupby(_summary_group_cols(rolling), dropna=False)
    aggregations: dict[str, tuple[str, str | Any]] = {
        "number_of_windows": ("start_date", "count"),
        "median_final_equity": ("final_equity", "median"),
        "mean_final_equity": ("final_equity", "mean"),
        "pct_windows_positive_return": ("total_return", lambda s: float((s > 0).mean())),
        "pct_windows_loss": ("total_return", lambda s: float((s < 0).mean())),
        "pct_windows_target_300_hit": ("target_300_hit", "mean"),
        "pct_windows_target_300_before_stop": ("target_300_before_any_stop", "mean"),
        "pct_windows_target_400_hit": ("target_400_hit", "mean"),
        "pct_windows_target_400_before_stop": ("target_400_before_any_stop", "mean"),
        "pct_windows_absolute_stop_hit": ("absolute_floor_stop_hit", "mean"),
        "pct_windows_trailing_stop_hit": ("trailing_drawdown_stop_hit", "mean"),
        "pct_windows_any_stop_hit": ("any_project_stop_hit", "mean"),
        "median_max_drawdown": ("max_drawdown_dollars", "median"),
        "worst_max_drawdown": ("max_drawdown_dollars", "min"),
        "median_number_of_trades": ("number_of_trades", "median"),
        "pct_windows_above_3300": ("final_equity", lambda s: float((s >= 3300).mean())),
        "pct_windows_above_3400": ("final_equity", lambda s: float((s >= 3400).mean())),
        "pct_windows_below_2400": ("final_equity", lambda s: float((s < 2400).mean())),
        "10th_percentile_final_equity": ("final_equity", lambda s: float(s.quantile(0.10))),
        "25th_percentile_final_equity": ("final_equity", lambda s: float(s.quantile(0.25))),
        "75th_percentile_final_equity": ("final_equity", lambda s: float(s.quantile(0.75))),
        "90th_percentile_final_equity": ("final_equity", lambda s: float(s.quantile(0.90))),
    }
    if "possible_window_count" in rolling:
        aggregations["possible_window_count"] = ("possible_window_count", "max")
    if "window_sampling_method" in rolling:
        aggregations["window_sampling_method"] = ("window_sampling_method", "first")
    summary = grouped.agg(**aggregations).reset_index()
    rename_map = {
        "10th_percentile_final_equity": "percentile_10_final_equity",
        "25th_percentile_final_equity": "percentile_25_final_equity",
        "75th_percentile_final_equity": "percentile_75_final_equity",
        "90th_percentile_final_equity": "percentile_90_final_equity",
    }
    for old, new in rename_map.items():
        if old in summary and new not in summary:
            summary[new] = summary[old]
    return summary


def _select_window_starts(max_start: int, max_windows: int | None, method: str = "deterministic_sample") -> list[int]:
    if max_start <= 0:
        return []
    if method == "all_possible" or max_windows is None:
        return list(range(max_start))
    if max_start <= max_windows:
        return list(range(max_start))
    return sorted(set(int(round(x)) for x in np.linspace(0, max_start - 1, max_windows)))


def _evenly_pick(indices: list[int], n: int) -> list[int]:
    if not indices or n <= 0:
        return []
    if len(indices) <= n:
        return list(indices)
    positions = np.linspace(0, len(indices) - 1, n)
    return [indices[int(round(pos))] for pos in positions]


def _spy_start_context(data: dict[str, pd.DataFrame], dates: list[pd.Timestamp]) -> pd.DataFrame:
    if "SPY" not in data:
        return pd.DataFrame({"date": dates, "regime_label": "", "spy_volatility_percentile": np.nan})
    spy = data["SPY"].copy()
    spy["date"] = pd.to_datetime(spy["date"])
    cols = ["date"]
    for col in ["close", "sma_200", "rv_20"]:
        if col in spy:
            cols.append(col)
    spy = spy[cols].drop_duplicates("date").sort_values("date")
    if "rv_20" in spy:
        vals: list[float] = []
        history: list[float] = []
        for value in spy["rv_20"].astype(float):
            if np.isfinite(value):
                history.append(float(value))
                vals.append(float((np.array(history) <= value).mean()))
            else:
                vals.append(np.nan)
        spy["spy_volatility_percentile"] = vals
    else:
        spy["spy_volatility_percentile"] = np.nan
    if {"close", "sma_200"}.issubset(spy.columns):
        spy["regime_label"] = np.where(spy["close"] > spy["sma_200"], "spy_above_200sma", "spy_below_200sma")
    else:
        spy["regime_label"] = ""
    context = pd.DataFrame({"date": pd.to_datetime(dates)})
    return context.merge(spy[["date", "regime_label", "spy_volatility_percentile"]], on="date", how="left")


def _deterministic_stratified_starts(
    max_start: int,
    sample_size: int,
    context: pd.DataFrame,
) -> dict[int, str]:
    if max_start <= 0:
        return {}
    all_indices = list(range(max_start))
    if max_start <= sample_size:
        return {idx: "all_available" for idx in all_indices}
    bucket_size = max(1, math.ceil(sample_size / 6))
    eligible_context = context.iloc[:max_start].copy()
    buckets: list[tuple[str, list[int]]] = [
        ("evenly_spaced", _evenly_pick(all_indices, bucket_size)),
    ]
    if "spy_volatility_percentile" in eligible_context:
        vol = eligible_context["spy_volatility_percentile"].astype(float)
        valid = eligible_context.loc[vol.notna()].assign(_idx=lambda df: df.index)
        high = valid.sort_values(["spy_volatility_percentile", "date"], ascending=[False, True])["_idx"].tolist()
        low = valid.sort_values(["spy_volatility_percentile", "date"], ascending=[True, True])["_idx"].tolist()
        buckets.append(("high_volatility_start", _evenly_pick([int(x) for x in high], bucket_size)))
        buckets.append(("low_volatility_start", _evenly_pick([int(x) for x in low], bucket_size)))
    below = eligible_context.index[eligible_context.get("regime_label", pd.Series(index=eligible_context.index)) == "spy_below_200sma"].tolist()
    above = eligible_context.index[eligible_context.get("regime_label", pd.Series(index=eligible_context.index)) == "spy_above_200sma"].tolist()
    buckets.append(("spy_below_200sma_start", _evenly_pick([int(x) for x in below], bucket_size)))
    buckets.append(("spy_above_200sma_start", _evenly_pick([int(x) for x in above], bucket_size)))
    buckets.append(("recent_period_start", list(range(max(0, max_start - bucket_size), max_start))))

    selected: dict[int, list[str]] = {}
    max_bucket_len = max((len(items) for _, items in buckets), default=0)
    for pos in range(max_bucket_len):
        for reason, items in buckets:
            if pos >= len(items):
                continue
            idx = int(items[pos])
            if idx < 0 or idx >= max_start:
                continue
            selected.setdefault(idx, [])
            if reason not in selected[idx]:
                selected[idx].append(reason)
            if len(selected) >= sample_size:
                break
        if len(selected) >= sample_size:
            break
    if len(selected) < sample_size:
        for idx in _evenly_pick(all_indices, sample_size):
            selected.setdefault(idx, [])
            if "top_up_evenly_spaced" not in selected[idx]:
                selected[idx].append("top_up_evenly_spaced")
            if len(selected) >= sample_size:
                break
    return {idx: ";".join(reasons) for idx, reasons in sorted(selected.items())}


def build_rolling_sample_plan(
    data: dict[str, pd.DataFrame],
    config: dict[str, Any],
    dates: list[pd.Timestamp],
    variants: list[str],
    slippage_labels: list[str],
    horizons: list[int],
    rolling_method: str,
    sample_size_per_group: int | None,
    candidate_gate: pd.DataFrame | None = None,
) -> pd.DataFrame:
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    context = _spy_start_context(data, dates)
    rows: list[dict[str, Any]] = []
    for variant in variants:
        if variant not in VARIANTS:
            continue
        for slippage_label in slippage_labels:
            if slippage_label not in slippages:
                continue
            if candidate_gate is not None and not _rolling_group_allowed(candidate_gate, variant, slippage_label):
                continue
            for horizon in horizons:
                possible = max(0, len(dates) - int(horizon) + 1)
                if possible <= 0:
                    continue
                if rolling_method == "all_possible":
                    selected = {idx: "all_possible" for idx in range(possible)}
                    requested = possible
                else:
                    requested = int(sample_size_per_group or 0)
                    selected = _deterministic_stratified_starts(possible, requested, context)
                method_label = "all_possible" if len(selected) == possible else "deterministic_stratified_sample"
                for start_idx, reason in selected.items():
                    end_idx = start_idx + int(horizon) - 1
                    start_ctx = context.iloc[start_idx] if start_idx < len(context) else {}
                    rows.append(
                        {
                            "variant_name": variant,
                            "slippage_label": slippage_label,
                            "slippage_pct_per_side": slippages[slippage_label],
                            "horizon_trading_days": int(horizon),
                            "start_index": int(start_idx),
                            "start_date": pd.Timestamp(dates[start_idx]).date().isoformat(),
                            "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                            "sample_reason": reason,
                            "regime_label_if_available": start_ctx.get("regime_label", "") if hasattr(start_ctx, "get") else "",
                            "spy_volatility_percentile_if_available": start_ctx.get("spy_volatility_percentile", np.nan)
                            if hasattr(start_ctx, "get")
                            else np.nan,
                            "sampling_method": method_label,
                            "sample_size_requested": requested,
                            "possible_window_count": possible,
                        }
                    )
    if not rows:
        return pd.DataFrame(
            columns=[
                "variant_name",
                "slippage_label",
                "slippage_pct_per_side",
                "horizon_trading_days",
                "start_index",
                "start_date",
                "end_date",
                "sample_reason",
                "regime_label_if_available",
                "spy_volatility_percentile_if_available",
                "sampling_method",
                "sample_size_requested",
                "possible_window_count",
            ]
        )
    return pd.DataFrame(rows).sort_values(
        ["variant_name", "slippage_label", "horizon_trading_days", "start_index"]
    ).reset_index(drop=True)


def _chunk_start_indices(starts: list[int], chunk_size: int | None) -> list[list[int]]:
    if not starts:
        return []
    if chunk_size is None or chunk_size <= 0 or chunk_size >= len(starts):
        return [starts]
    return [starts[idx : idx + chunk_size] for idx in range(0, len(starts), chunk_size)]


def _rolling_group_rows(
    data: dict[str, pd.DataFrame],
    config: dict[str, Any],
    dates: list[pd.Timestamp],
    variant_name: str,
    slippage_label: str,
    slippage: float,
    horizon: int,
    start_indices: list[int],
    sampling_method: str,
    possible_window_count: int,
) -> list[dict[str, Any]]:
    variant_cfg = strategy_variant_config(config, variant_name)
    bt = Backtester(data, variant_cfg)
    rows: list[dict[str, Any]] = []
    for start_idx in start_indices:
        window_dates = dates[start_idx : start_idx + horizon]
        if len(window_dates) < horizon:
            continue
        result = bt.run(
            f"independent_{variant_name}_{slippage_label}_{horizon}",
            str(window_dates[0].date()),
            str(window_dates[-1].date()),
            slippage,
            dates_override=window_dates,
            lightweight_outputs=True,
        )
        eq = result.equity_curve
        if eq.empty:
            continue
        combined = result.strategy_metrics.loc[
            result.strategy_metrics["name"] == "combined_tournament"
        ].iloc[0]
        best, worst = _best_worst_strategy_by_pnl(result.trades)
        rows.append(
            {
                "variant_name": variant_name,
                "slippage_label": slippage_label,
                "horizon_trading_days": horizon,
                "start_date": pd.Timestamp(window_dates[0]).date().isoformat(),
                "end_date": pd.Timestamp(window_dates[-1]).date().isoformat(),
                "final_equity": combined["final_equity"],
                "total_return": combined["total_return"],
                "max_equity": float(eq["equity"].max()),
                "min_equity": float(eq["equity"].min()),
                "max_drawdown_dollars": combined["max_drawdown"],
                "max_drawdown_pct": combined["max_drawdown_pct"],
                "target_300_hit": result.metadata.get("target_300_hit", False),
                "target_300_before_any_stop": result.metadata.get("target_300_before_any_stop", False),
                "target_300_first_date": result.metadata.get("target_300_first_date", ""),
                "target_300_trading_days": result.metadata.get("target_300_trading_days", pd.NA),
                "target_400_hit": result.metadata.get("target_400_hit", False),
                "target_400_before_any_stop": result.metadata.get("target_400_before_any_stop", False),
                "target_400_first_date": result.metadata.get("target_400_first_date", ""),
                "target_400_trading_days": result.metadata.get("target_400_trading_days", pd.NA),
                "absolute_floor_stop_hit": result.metadata.get("absolute_floor_stop_hit", False),
                "trailing_drawdown_stop_hit": result.metadata.get("trailing_drawdown_stop_hit", False),
                "any_project_stop_hit": result.metadata.get("any_project_stop_hit", False),
                "first_project_stop_date": result.metadata.get("first_project_stop_date", ""),
                "first_project_stop_type": result.metadata.get("first_project_stop_type", ""),
                "number_of_trades": int(len(result.trades)),
                "number_of_skipped_signals": int(len(result.skipped_signals)),
                "strategies_killed": ",".join(result.killed_strategies),
                "best_strategy_by_pnl": best,
                "worst_strategy_by_pnl": worst,
                "ending_open_positions_count": int(eq["open_positions"].iloc[-1]) if "open_positions" in eq else 0,
                "possible_window_count": possible_window_count,
                "window_sampling_method": sampling_method,
            }
        )
    return rows


def _rolling_group_worker(args: tuple[str, str, float, int, list[int], str, int]) -> list[dict[str, Any]]:
    if _ROLLING_WORKER_DATA is None or _ROLLING_WORKER_CONFIG is None or _ROLLING_WORKER_DATES is None:
        raise RuntimeError("Rolling worker globals were not initialized.")
    variant_name, slippage_label, slippage, horizon, start_indices, sampling_method, possible_window_count = args
    return _rolling_group_rows(
        _ROLLING_WORKER_DATA,
        _ROLLING_WORKER_CONFIG,
        _ROLLING_WORKER_DATES,
        variant_name,
        slippage_label,
        slippage,
        horizon,
        start_indices,
        sampling_method,
        possible_window_count,
    )


def build_independent_rolling_windows(
    data: dict[str, pd.DataFrame],
    config: dict[str, Any],
    horizons: tuple[int, ...] = (30, 60, 90, 180),
    variants: tuple[str, ...] = ROLLING_CANDIDATE_VARIANTS,
    max_windows_per_group: int | None = None,
) -> pd.DataFrame:
    rolling_cfg = config.get("rolling_validation", {})
    method = str(rolling_cfg.get("method", "deterministic_sample"))
    if max_windows_per_group is None:
        max_windows_per_group = rolling_cfg.get("max_windows_per_group", 12)
    if method == "all_possible":
        max_windows_per_group = None

    base_bt = Backtester(data, config)
    full_range = config["date_ranges"]["full"]
    dates = base_bt._effective_calendar(str(full_range["start"]), full_range.get("end") or config["data"].get("end_date"))
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    total_possible_windows = sum(
        max(0, len(dates) - horizon + 1)
        for _variant_name in variants
        for _slippage_label in slippages
        for horizon in horizons
    )
    max_total_windows = rolling_cfg.get("max_total_windows_for_local_run")
    if method == "all_possible" and max_total_windows not in {None, ""}:
        max_total_windows = int(max_total_windows)
        if total_possible_windows > max_total_windows:
            print(
                "WARNING: all_possible independent rolling validation was not run. "
                f"Estimated windows={total_possible_windows:,} exceeds "
                f"rolling_validation.max_total_windows_for_local_run={max_total_windows:,}. "
                "Evidence will be marked non-final for rolling-window validation.",
                flush=True,
            )
            return pd.DataFrame()
    tasks: list[tuple[str, str, float, int, list[int], str, int]] = []
    chunk_size = rolling_cfg.get("chunk_size")
    chunk_size = int(chunk_size) if chunk_size not in {None, ""} else None
    for variant_name in variants:
        for slippage_label, slippage in slippages.items():
            for horizon in horizons:
                max_start = len(dates) - horizon + 1
                starts = _select_window_starts(max_start, max_windows_per_group, method)
                sampling_method = (
                    "all_possible"
                    if len(starts) == max_start
                    else f"deterministic_even_sample_{len(starts)}"
                )
                for chunk in _chunk_start_indices(starts, chunk_size if method == "all_possible" else None):
                    tasks.append((variant_name, slippage_label, slippage, horizon, chunk, sampling_method, max_start))

    rows: list[dict[str, Any]] = []
    worker_count = int(rolling_cfg.get("parallel_workers", 0) or 0)
    if method == "all_possible" and worker_count <= 0:
        worker_count = min(12, os.cpu_count() or 1)

    if worker_count > 1 and len(tasks) > 1:
        global _ROLLING_WORKER_DATA, _ROLLING_WORKER_CONFIG, _ROLLING_WORKER_DATES
        _ROLLING_WORKER_DATA = data
        _ROLLING_WORKER_CONFIG = config
        _ROLLING_WORKER_DATES = dates
        context = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
        with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count, mp_context=context) as executor:
            for group_rows in executor.map(_rolling_group_worker, tasks):
                rows.extend(group_rows)
        _ROLLING_WORKER_DATA = None
        _ROLLING_WORKER_CONFIG = None
        _ROLLING_WORKER_DATES = None
    else:
        for task in tasks:
            variant_name, slippage_label, slippage, horizon, starts, sampling_method, max_start = task
            rows.extend(
                _rolling_group_rows(
                    data,
                    config,
                    dates,
                    variant_name,
                    slippage_label,
                    slippage,
                    horizon,
                    starts,
                    sampling_method,
                    max_start,
                )
            )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["variant_name", "slippage_label", "horizon_trading_days", "start_date"]
    ).reset_index(drop=True)


def _rolling_cache_key(
    data_hash: str,
    config_hash_value: str,
    strategy_definitions_hash: str,
    variant_name: str,
    slippage_label: str,
    horizon: int,
    rolling_method: str,
    validation_mode: str,
    sample_plan_hash: str,
    project_stop_mode: str,
) -> str:
    return _stable_hash_obj(
        {
            "data_hash": data_hash,
            "config_hash": config_hash_value,
            "strategy_definitions_hash": strategy_definitions_hash,
            "variant_name": variant_name,
            "slippage_label": slippage_label,
            "horizon_trading_days": horizon,
            "rolling_method": rolling_method,
            "validation_mode": validation_mode,
            "sample_plan_hash": sample_plan_hash,
            "project_stop_mode": project_stop_mode,
        }
    )


def _append_progress(progress_path: Path, row: dict[str, Any]) -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": datetime.now(UTC).isoformat(), **row}
    with progress_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str, sort_keys=True) + "\n")


def _sanitize_filename(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def _write_empty_rolling_files(run_dir: Path) -> None:
    pd.DataFrame().to_csv(run_dir / "independent_rolling_window_results.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "independent_rolling_window_summary.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "rolling_sample_plan.csv", index=False)
    write_json(run_dir / "rolling_cache_manifest.json", {"entries": []})
    (run_dir / "rolling_progress.jsonl").write_text("", encoding="utf-8")


def run_independent_rolling_validation(
    data: dict[str, pd.DataFrame],
    config: dict[str, Any],
    run_dir: Path,
    candidate_gate: pd.DataFrame,
    *,
    run_id: str,
    skip_rolling: bool = False,
    reuse_cache: bool = False,
    force_recompute: bool = False,
    max_workers: int | None = None,
    rolling_time_budget_minutes: float | None = None,
    profile_rolling: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    settings = validation_mode_settings(config)
    validation_mode = settings["mode"]
    rolling_method = str(settings["rolling_method"])
    mark_as_final = bool(settings.get("mark_as_final", False))
    variants_setting = settings.get("variants", [])
    variants = list(VARIANTS.keys()) if variants_setting == "all" else list(variants_setting)
    slippage_labels = list(settings.get("slippage_labels", ["standard", "stress"]))
    horizons = [int(h) for h in settings.get("horizons", [90])]
    sample_size = settings.get("sample_size_per_group")
    sample_size_int = int(sample_size) if sample_size not in {None, ""} else None
    rolling_cfg = config.get("rolling_validation", {})
    chunk_size = int(rolling_cfg.get("chunk_size", 250) or 250)
    worker_count = int(max_workers if max_workers is not None else rolling_cfg.get("parallel_workers", 0) or 0)
    if worker_count <= 0:
        worker_count = min(8, os.cpu_count() or 1)
    cache_root = Path(config.get("project_root", Path.cwd())) / str(rolling_cfg.get("cache_dir", "evidence/cache/rolling"))
    cache_root.mkdir(parents=True, exist_ok=True)
    chunks_dir = run_dir / "rolling_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    progress_path = run_dir / "rolling_progress.jsonl"
    progress_path.write_text("", encoding="utf-8")
    start_wall = time.time()
    deadline = start_wall + rolling_time_budget_minutes * 60 if rolling_time_budget_minutes else None

    base_bt = Backtester(data, config)
    full_range = config["date_ranges"]["full"]
    dates = base_bt._effective_calendar(str(full_range["start"]), full_range.get("end") or config["data"].get("end_date"))
    if skip_rolling:
        _write_empty_rolling_files(run_dir)
        status = {
            "validation_mode": validation_mode,
            "purpose": settings.get("purpose", ""),
            "rolling_method": rolling_method,
            "mark_as_final": mark_as_final,
            "sampled_results_are_final": False,
            "final_validation_completed": False,
            "rolling_completed": False,
            "rolling_skipped": True,
            "number_of_windows": 0,
            "possible_window_count": 0,
            "cache_hits": 0,
            "cache_entries": 0,
            "elapsed_seconds": 0.0,
        }
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), status

    sample_plan = build_rolling_sample_plan(
        data,
        config,
        dates,
        variants,
        slippage_labels,
        horizons,
        rolling_method,
        sample_size_int,
        candidate_gate,
    )
    sample_plan.to_csv(run_dir / "rolling_sample_plan.csv", index=False)
    if sample_plan.empty:
        _write_empty_rolling_files(run_dir)
        status = {
            "validation_mode": validation_mode,
            "purpose": settings.get("purpose", ""),
            "rolling_method": rolling_method,
            "mark_as_final": mark_as_final,
            "sampled_results_are_final": False,
            "final_validation_completed": False,
            "rolling_completed": False,
            "rolling_skipped": False,
            "number_of_windows": 0,
            "possible_window_count": 0,
            "cache_hits": 0,
            "cache_entries": 0,
            "elapsed_seconds": time.time() - start_wall,
        }
        return pd.DataFrame(), sample_plan, pd.DataFrame(), status

    total_windows = int(len(sample_plan))
    total_possible = int(sample_plan.drop_duplicates(["variant_name", "slippage_label", "horizon_trading_days"])["possible_window_count"].sum())
    print(
        f"Rolling validation mode={validation_mode} method={rolling_method} "
        f"planned_windows={total_windows:,} possible_windows={total_possible:,} workers={worker_count}",
        flush=True,
    )

    data_hash = data_fingerprint(data)
    config_hash_value = _stable_hash_obj(config)
    strategy_defs_hash = _stable_hash_obj(config.get("strategies", {}))
    project_stop_mode = str(config.get("project", {}).get("project_stop", {}).get("mode", "absolute_floor"))
    rows: list[pd.DataFrame] = []
    cache_rows: list[dict[str, Any]] = []
    rolling_completed = True
    completed_windows = 0
    completed_chunks_total = 0
    total_chunks_estimate = 0
    group_items = list(sample_plan.groupby(["variant_name", "slippage_label", "horizon_trading_days"], sort=True))
    for _, group_plan in group_items:
        total_chunks_estimate += len(_chunk_start_indices(group_plan["start_index"].astype(int).tolist(), chunk_size))

    global _ROLLING_WORKER_DATA, _ROLLING_WORKER_CONFIG, _ROLLING_WORKER_DATES
    _ROLLING_WORKER_DATA = data
    _ROLLING_WORKER_CONFIG = config
    _ROLLING_WORKER_DATES = dates
    context = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
    executor: concurrent.futures.ProcessPoolExecutor | None = None
    if worker_count > 1:
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=worker_count, mp_context=context)
    try:
        for (variant_name, slippage_label, horizon), group_plan in group_items:
            if deadline and time.time() >= deadline:
                rolling_completed = False
                break
            group_plan = group_plan.sort_values("start_index")
            starts = group_plan["start_index"].astype(int).tolist()
            sampling_method = str(group_plan["sampling_method"].iloc[0])
            possible = int(group_plan["possible_window_count"].iloc[0])
            slippage = float(group_plan["slippage_pct_per_side"].iloc[0])
            sample_plan_hash = _stable_hash_obj(
                group_plan[["start_index", "start_date", "end_date", "sample_reason"]].to_dict(orient="records")
            )
            cache_key = _rolling_cache_key(
                data_hash,
                config_hash_value,
                strategy_defs_hash,
                str(variant_name),
                str(slippage_label),
                int(horizon),
                rolling_method,
                validation_mode,
                sample_plan_hash,
                project_stop_mode,
            )
            cache_file = cache_root / f"{cache_key}.csv"
            if reuse_cache and not force_recompute and cache_file.exists():
                cached = pd.read_csv(cache_file)
                rows.append(cached)
                completed_windows += len(cached)
                cached_chunk_count = len(_chunk_start_indices(starts, chunk_size))
                cache_rows.append(
                    {
                        "cache_key": cache_key,
                        "cache_file": str(cache_file),
                        "cache_hit": True,
                        "rows_loaded": len(cached),
                        "rows_written": 0,
                        "variant_name": variant_name,
                        "slippage_label": slippage_label,
                        "horizon_trading_days": int(horizon),
                        "rolling_method": rolling_method,
                        "validation_mode": validation_mode,
                    }
                )
                completed_chunks_total += cached_chunk_count
                _append_progress(
                    progress_path,
                    {
                        "run_id": run_id,
                        "validation_mode": validation_mode,
                        "variant_name": variant_name,
                        "slippage_label": slippage_label,
                        "horizon_trading_days": int(horizon),
                        "rolling_method": rolling_method,
                        "completed_chunks": completed_chunks_total,
                        "total_chunks": total_chunks_estimate,
                        "completed_windows": completed_windows,
                        "total_windows": total_windows,
                        "elapsed_seconds": time.time() - start_wall,
                        "cache_hit": True,
                    },
                )
                continue

            chunks = _chunk_start_indices(starts, chunk_size)
            print(
                f"Rolling group variant={variant_name} slippage={slippage_label} horizon={horizon} "
                f"method={sampling_method} windows={len(starts):,} chunks={len(chunks)}",
                flush=True,
            )
            group_frames: list[pd.DataFrame] = []
            if executor is not None and len(chunks) > 1:
                future_to_chunk: dict[concurrent.futures.Future, tuple[int, list[int], Path]] = {}
                for chunk_no, chunk in enumerate(chunks, start=1):
                    if deadline and time.time() >= deadline:
                        rolling_completed = False
                        break
                    chunk_path = chunks_dir / (
                        f"rolling__variant={_sanitize_filename(variant_name)}__slippage={_sanitize_filename(slippage_label)}"
                        f"__horizon={int(horizon)}__chunk={chunk_no}.csv"
                    )
                    future = executor.submit(
                        _rolling_group_worker,
                        (str(variant_name), str(slippage_label), slippage, int(horizon), chunk, sampling_method, possible),
                    )
                    future_to_chunk[future] = (chunk_no, chunk, chunk_path)
                for future in concurrent.futures.as_completed(future_to_chunk):
                    chunk_no, chunk, chunk_path = future_to_chunk[future]
                    chunk_rows = future.result()
                    chunk_df = pd.DataFrame(chunk_rows)
                    chunk_df.to_csv(chunk_path, index=False)
                    group_frames.append(chunk_df)
                    completed_windows += len(chunk_df)
                    completed_chunks_total += 1
                    elapsed = time.time() - start_wall
                    _append_progress(
                        progress_path,
                        {
                            "run_id": run_id,
                            "validation_mode": validation_mode,
                            "variant_name": variant_name,
                            "slippage_label": slippage_label,
                            "horizon_trading_days": int(horizon),
                            "rolling_method": rolling_method,
                            "completed_chunks": completed_chunks_total,
                            "total_chunks": total_chunks_estimate,
                            "completed_windows": completed_windows,
                            "total_windows": total_windows,
                            "elapsed_seconds": elapsed,
                        },
                    )
                    if profile_rolling:
                        remaining = max(0, total_windows - completed_windows)
                        rate = completed_windows / elapsed if elapsed > 0 else 0
                        eta = remaining / rate if rate > 0 else np.nan
                        print(
                            f"Rolling progress {completed_windows:,}/{total_windows:,} windows "
                            f"elapsed={elapsed:.1f}s eta={eta:.1f}s",
                            flush=True,
                        )
            else:
                for chunk_no, chunk in enumerate(chunks, start=1):
                    if deadline and time.time() >= deadline:
                        rolling_completed = False
                        break
                    chunk_path = chunks_dir / (
                        f"rolling__variant={_sanitize_filename(variant_name)}__slippage={_sanitize_filename(slippage_label)}"
                        f"__horizon={int(horizon)}__chunk={chunk_no}.csv"
                    )
                    chunk_rows = _rolling_group_rows(
                        data,
                        config,
                        dates,
                        str(variant_name),
                        str(slippage_label),
                        slippage,
                        int(horizon),
                        chunk,
                        sampling_method,
                        possible,
                    )
                    chunk_df = pd.DataFrame(chunk_rows)
                    chunk_df.to_csv(chunk_path, index=False)
                    group_frames.append(chunk_df)
                    completed_windows += len(chunk_df)
                    completed_chunks_total += 1
                    _append_progress(
                        progress_path,
                        {
                            "run_id": run_id,
                            "validation_mode": validation_mode,
                            "variant_name": variant_name,
                            "slippage_label": slippage_label,
                            "horizon_trading_days": int(horizon),
                            "rolling_method": rolling_method,
                            "completed_chunks": completed_chunks_total,
                            "total_chunks": total_chunks_estimate,
                            "completed_windows": completed_windows,
                            "total_windows": total_windows,
                            "elapsed_seconds": time.time() - start_wall,
                        },
                    )
            group_df = pd.concat([frame for frame in group_frames if not frame.empty], ignore_index=True) if group_frames else pd.DataFrame()
            if not group_df.empty:
                group_df = group_df.sort_values(["variant_name", "slippage_label", "horizon_trading_days", "start_date"])
                group_df.to_csv(cache_file, index=False)
                rows.append(group_df)
            cache_rows.append(
                {
                    "cache_key": cache_key,
                    "cache_file": str(cache_file),
                    "cache_hit": False,
                    "rows_loaded": 0,
                    "rows_written": len(group_df),
                    "variant_name": variant_name,
                    "slippage_label": slippage_label,
                    "horizon_trading_days": int(horizon),
                    "rolling_method": rolling_method,
                    "validation_mode": validation_mode,
                }
            )
            if not rolling_completed:
                break
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        _ROLLING_WORKER_DATA = None
        _ROLLING_WORKER_CONFIG = None
        _ROLLING_WORKER_DATES = None

    results = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not results.empty:
        results = results.drop_duplicates(
            ["variant_name", "slippage_label", "horizon_trading_days", "start_date"]
        ).sort_values(["variant_name", "slippage_label", "horizon_trading_days", "start_date"]).reset_index(drop=True)
    summary = summarize_independent_rolling_windows(results)
    results.to_csv(run_dir / "independent_rolling_window_results.csv", index=False)
    summary.to_csv(run_dir / "independent_rolling_window_summary.csv", index=False)
    cache_manifest = pd.DataFrame(cache_rows)
    write_json(run_dir / "rolling_cache_manifest.json", {"entries": cache_rows})

    final_validation_completed = bool(
        rolling_completed
        and mark_as_final
        and rolling_method == "all_possible"
        and not results.empty
        and "possible_window_count" in summary
        and (summary["number_of_windows"] == summary["possible_window_count"]).all()
    )
    sampled_results_are_final = bool(final_validation_completed)
    status = {
        "validation_mode": validation_mode,
        "purpose": settings.get("purpose", ""),
        "rolling_method": rolling_method,
        "mark_as_final": mark_as_final,
        "sampled_results_are_final": sampled_results_are_final,
        "final_validation_completed": final_validation_completed,
        "rolling_completed": bool(rolling_completed and completed_windows == len(results)),
        "rolling_skipped": False,
        "number_of_windows": int(len(results)),
        "possible_window_count": total_possible,
        "cache_hits": int(sum(1 for row in cache_rows if row.get("cache_hit"))),
        "cache_entries": int(len(cache_rows)),
        "elapsed_seconds": time.time() - start_wall,
        "worker_count": worker_count,
        "chunk_size": chunk_size,
        "time_budget_minutes": rolling_time_budget_minutes,
        "profile_rolling": profile_rolling,
    }
    if not rolling_completed:
        (run_dir / "rolling_validation_incomplete.md").write_text(
            "# Rolling Validation Incomplete\n\n"
            f"Validation mode: `{validation_mode}`\n\n"
            f"Rolling method: `{rolling_method}`\n\n"
            f"Completed windows: {len(results):,} of planned {total_windows:,}.\n\n"
            "The run stopped because the rolling time budget was reached before all groups/chunks completed. "
            "These results are partial and are not final validation.\n\n"
            "No real-money recommendation.\n",
            encoding="utf-8",
        )
    return results, sample_plan, cache_manifest, status


def skipped_signal_summary(skipped: pd.DataFrame) -> pd.DataFrame:
    if skipped.empty:
        return pd.DataFrame(columns=["reason_skipped", "strategy", "count", "pct_of_all_skips", "first_date", "last_date"])
    total = len(skipped)
    grouped = skipped.groupby(["reason_skipped", "strategy"], dropna=False)
    return grouped.agg(
        count=("reason_skipped", "count"),
        first_date=("date", "min"),
        last_date=("date", "max"),
    ).reset_index().assign(pct_of_all_skips=lambda df: df["count"] / total)[
        ["reason_skipped", "strategy", "count", "pct_of_all_skips", "first_date", "last_date"]
    ]


def skipped_signal_sample(skipped: pd.DataFrame, n: int = 200) -> pd.DataFrame:
    if skipped.empty:
        return skipped.copy()
    priority = skipped.copy()
    risk_reasons = {"max_open_risk_exceeded", "correlation_cluster_risk_exceeded", "strategy_loss_budget_hit"}
    priority["_priority"] = priority["reason_skipped"].isin(risk_reasons).astype(int)
    sampled = (
        priority.sort_values(["_priority", "strategy", "reason_skipped", "date"], ascending=[False, True, True, True])
        .groupby(["strategy", "reason_skipped"], group_keys=False)
        .head(max(1, math.ceil(n / max(1, priority.groupby(["strategy", "reason_skipped"]).ngroups))))
        .head(n)
        .drop(columns=["_priority"])
    )
    return sampled


def strategy_health(result: BacktestResult, variants: pd.DataFrame | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    trades = result.trades
    equity = result.equity_curve
    for strategy in MAIN_STRATEGIES:
        st = trades.loc[trades["strategy"] == strategy].copy() if not trades.empty else trades.copy()
        pnl_col = f"{strategy}_total_pnl"
        pnl_series = equity[pnl_col] if pnl_col in equity else pd.Series(dtype=float)
        exp_dollars, exp_r = expectancy(st)
        max_dd, _ = max_drawdown(pnl_series + 0.0) if not pnl_series.empty else (np.nan, np.nan)
        wins = int((st["pnl"] > 0).sum()) if not st.empty else 0
        losses = int((st["pnl"] < 0).sum()) if not st.empty else 0
        kill_rows = result.strategy_lifecycle_events.loc[
            (result.strategy_lifecycle_events.get("strategy") == strategy)
            & (result.strategy_lifecycle_events.get("event_type") == "strategy_disabled_loss_budget")
        ] if not result.strategy_lifecycle_events.empty else pd.DataFrame()
        stress_delta = np.nan
        stress_available = False
        if variants is not None and not variants.empty:
            variant_for_strategy = {
                "A_ETF_sector_momentum": "current_momentum_only_A",
                "B_ETF_trend_following": "trend_only_B",
            }.get(strategy)
            if variant_for_strategy and {"variant_name", "slippage_label", "final_equity"}.issubset(variants.columns):
                v = variants.loc[variants["variant_name"] == variant_for_strategy]
                std = v.loc[v["slippage_label"] == "standard", "final_equity"]
                stress = v.loc[v["slippage_label"] == "stress", "final_equity"]
                if not std.empty and not stress.empty:
                    stress_delta = float(stress.iloc[0] - std.iloc[0])
                    stress_available = True
        rows.append(
            {
                "strategy": strategy,
                "enabled": True,
                "final_pnl": float(pnl_series.iloc[-1]) if not pnl_series.empty else 0.0,
                "final_unrealized_pnl": float(equity.get(f"{strategy}_unrealized_pnl", pd.Series([0])).iloc[-1])
                if not equity.empty
                else 0.0,
                "total_trades": int(len(st)),
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate": float(wins / len(st)) if len(st) else np.nan,
                "profit_factor": profit_factor(st),
                "expectancy_dollars": exp_dollars,
                "expectancy_r": exp_r,
                "max_drawdown": max_dd,
                "max_consecutive_losses": consecutive_losses(st),
                "killed_by_loss_budget": not kill_rows.empty,
                "kill_date": kill_rows.iloc[0]["date"] if not kill_rows.empty else "",
                "kill_equity": kill_rows.iloc[0]["project_equity"] if not kill_rows.empty else np.nan,
                "kill_strategy_pnl": kill_rows.iloc[0]["strategy_pnl"] if not kill_rows.empty else np.nan,
                "first_trade_date": st["entry_date"].min() if not st.empty else "",
                "last_trade_date": st["exit_date"].max() if not st.empty else "",
                "target_contribution_dollars": float(st["pnl"].sum()) if not st.empty else 0.0,
                "top_trade_contribution_pct": _top_5_trade_contribution_pct(st),
                "stress_result_available": stress_available,
                "standard_vs_stress_delta": stress_delta,
            }
        )
    return pd.DataFrame(rows)


def r_multiple_diagnostics(trades: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty
    min_stop = float(config["project"].get("min_stop_distance_pct", 0.0025))
    min_util = float(config["project"].get("min_actual_risk_utilization_pct", 0.25))
    diag = {
        "total_trades": len(trades),
        "avg_intended_risk": trades["intended_risk_amount"].mean(),
        "median_intended_risk": trades["intended_risk_amount"].median(),
        "avg_actual_risk": trades["actual_risk_amount"].mean(),
        "median_actual_risk": trades["actual_risk_amount"].median(),
        "avg_risk_utilization_pct": trades["risk_utilization_pct"].mean(),
        "median_risk_utilization_pct": trades["risk_utilization_pct"].median(),
        "pct_trades_risk_utilization_lt_25": (trades["risk_utilization_pct"] < 0.25).mean(),
        "pct_trades_risk_utilization_lt_50": (trades["risk_utilization_pct"] < 0.50).mean(),
        "pct_trades_stop_distance_lt_0_25pct": (trades["stop_distance_pct"] < 0.0025).mean(),
        "pct_trades_stop_distance_lt_0_50pct": (trades["stop_distance_pct"] < 0.0050).mean(),
        "max_r_multiple": trades["r_multiple"].max(),
        "min_r_multiple": trades["r_multiple"].min(),
        "mean_r_multiple": trades["r_multiple"].mean(),
        "median_r_multiple": trades["r_multiple"].median(),
        "top_10_r_multiple_symbols": ",".join(trades.sort_values("r_multiple", ascending=False).head(10)["symbol"].astype(str)),
        "bil_trade_count": int((trades["symbol"] == "BIL").sum()),
        "shy_trade_count": int((trades["symbol"] == "SHY").sum()),
        "bil_pnl": float(trades.loc[trades["symbol"] == "BIL", "pnl"].sum()),
        "shy_pnl": float(trades.loc[trades["symbol"] == "SHY", "pnl"].sum()),
        "bil_avg_r_multiple": trades.loc[trades["symbol"] == "BIL", "r_multiple"].mean(),
        "shy_avg_r_multiple": trades.loc[trades["symbol"] == "SHY", "r_multiple"].mean(),
        "would_exclude_min_stop_distance_pct_count": int((trades["stop_distance_pct"] < min_stop).sum()),
        "would_exclude_min_stop_distance_pct_pnl": float(trades.loc[trades["stop_distance_pct"] < min_stop, "pnl"].sum()),
        "would_exclude_min_actual_risk_utilization_count": int((trades["risk_utilization_pct"] < min_util).sum()),
        "would_exclude_min_actual_risk_utilization_pnl": float(trades.loc[trades["risk_utilization_pct"] < min_util, "pnl"].sum()),
    }
    top_r = trades.sort_values("r_multiple", ascending=False).head(50)
    top_pnl = trades.sort_values("pnl", ascending=False).head(50)
    bottom_pnl = trades.sort_values("pnl", ascending=True).head(50)
    return pd.DataFrame([diag]), top_r, top_pnl, bottom_pnl


def symbol_contribution(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    gross_loss = -trades.loc[trades["pnl"] < 0, "pnl"].sum()
    rows = []
    for symbol, group in trades.groupby("symbol"):
        rows.append(
            {
                "symbol": symbol,
                "total_trades": len(group),
                "total_pnl": group["pnl"].sum(),
                "avg_pnl": group["pnl"].mean(),
                "win_rate": (group["pnl"] > 0).mean(),
                "profit_factor": profit_factor(group),
                "avg_r_multiple": group["r_multiple"].mean(),
                "median_r_multiple": group["r_multiple"].median(),
                "total_days_held": group["holding_days"].sum(),
                "strategies_trading_symbol": ",".join(sorted(group["strategy"].unique())),
                "pct_of_total_profit": group.loc[group["pnl"] > 0, "pnl"].sum() / gross_profit if gross_profit else np.nan,
                "pct_of_total_loss": -group.loc[group["pnl"] < 0, "pnl"].sum() / gross_loss if gross_loss else np.nan,
                "is_cash_proxy_symbol": symbol in {"BIL", "SHY"},
            }
        )
    return pd.DataFrame(rows).sort_values("total_pnl", ascending=False)


def regime_summary(trades: pd.DataFrame, rolling: pd.DataFrame | None = None) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    regime_col = "regime_at_signal" if "regime_at_signal" in trades else "market_regime_at_entry"
    grouped = trades.groupby([regime_col, "strategy"], dropna=False)
    out = grouped.agg(
        total_trades=("trade_id", "count"),
        total_pnl=("pnl", "sum"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        profit_factor=("pnl", lambda s: profit_factor(pd.DataFrame({"pnl": s}))),
        avg_r_multiple=("r_multiple", "mean"),
        median_r_multiple=("r_multiple", "median"),
        avg_holding_days=("holding_days", "mean"),
    ).reset_index().rename(columns={regime_col: "regime_label"})
    return out


def data_quality_summary(data_coverage: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    out = data_coverage.copy()
    if "symbol" not in out:
        return out
    first_trade = trades.groupby("symbol")["entry_date"].min() if not trades.empty else pd.Series(dtype=str)
    out["warmup_start_available"] = out["row_count"].fillna(0).astype(float) >= 252
    out["first_trade_eligible_date"] = out["symbol"].map(first_trade).fillna("")
    out["data_gap_count"] = np.nan
    out["suspicious_adjustment_factor_count"] = np.nan
    return out


def data_quality_markdown(data_quality: pd.DataFrame) -> str:
    if data_quality.empty:
        return "# Data Quality Summary\n\nNo data quality rows were generated.\n"
    excluded = data_quality.loc[data_quality.get("status", "") == "excluded"]
    late = data_quality.sort_values("first_date").tail(5)
    return (
        "# Data Quality Summary\n\n"
        f"- Symbols reviewed: {len(data_quality)}\n"
        f"- Excluded symbols: {len(excluded)}\n"
        f"- Symbols with at least 252 rows: {int(data_quality['warmup_start_available'].sum())}\n"
        "- Late or limited-history symbols should be reviewed for inception-date effects.\n\n"
        "## Latest First Dates\n\n"
        + "```text\n"
        + late[["symbol", "first_date", "last_date", "row_count", "excluded_reason"]].to_string(index=False)
        + "\n```"
        + "\n"
    )


def benchmark_summary_frame(result: BacktestResult, config: dict[str, Any], independent_summary: pd.DataFrame) -> pd.DataFrame:
    if result.benchmark_curve.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    rolling90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90] if not independent_summary.empty else pd.DataFrame()
    dates = pd.to_datetime(result.benchmark_curve["date"])
    for col in result.benchmark_curve.columns:
        if col == "date":
            continue
        equity = result.benchmark_curve[col].astype(float)
        frame = pd.DataFrame({"date": dates, "equity": equity})
        frame["high_water_mark"] = frame["equity"].cummax()
        frame["drawdown_dollars"] = frame["equity"] - frame["high_water_mark"]
        frame["drawdown_pct"] = frame["equity"] / frame["high_water_mark"] - 1.0
        stop_rows = [evaluate_project_stop(row.equity, row.high_water_mark, config) for row in frame.itertuples(index=False)]
        frame["absolute_floor_stop_active"] = [item["absolute_floor_stop_active"] for item in stop_rows]
        frame["trailing_drawdown_stop_active"] = [item["trailing_drawdown_stop_active"] for item in stop_rows]
        timing = compute_target_timing(frame, config)
        max_dd, max_dd_pct = max_drawdown(equity)
        rows.append(
            {
                "benchmark": col,
                "final_equity": float(equity.iloc[-1]),
                "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
                "cagr": cagr(equity, dates),
                "max_drawdown": max_dd,
                "max_drawdown_pct": max_dd_pct,
                "sharpe": sharpe_ratio(equity),
                "sortino": sortino_ratio(equity),
                "target_300_hit": timing.get("target_300_hit", False),
                "target_300_before_stop": timing.get("target_300_before_any_stop", False),
                "target_400_hit": timing.get("target_400_hit", False),
                "target_400_before_stop": timing.get("target_400_before_any_stop", False),
                "90_day_target_300_before_stop_rate": np.nan,
                "90_day_target_400_before_stop_rate": np.nan,
            }
        )
    for _, row in rolling90.iterrows():
        rows.append(
            {
                "benchmark": f"variant_{row['variant_name']}_{row['slippage_label']}",
                "final_equity": np.nan,
                "total_return": np.nan,
                "cagr": np.nan,
                "max_drawdown": row.get("median_max_drawdown", np.nan),
                "max_drawdown_pct": np.nan,
                "sharpe": np.nan,
                "sortino": np.nan,
                "target_300_hit": np.nan,
                "target_300_before_stop": np.nan,
                "target_400_hit": np.nan,
                "target_400_before_stop": np.nan,
                "90_day_target_300_before_stop_rate": row.get("pct_windows_target_300_before_stop", np.nan),
                "90_day_target_400_before_stop_rate": row.get("pct_windows_target_400_before_stop", np.nan),
            }
        )
    return pd.DataFrame(rows)


def make_audit_packet(
    run_dir: Path,
    run_id: str,
    result: BacktestResult,
    config: dict[str, Any],
    metadata: dict[str, Any],
    data_coverage: pd.DataFrame,
    comparative: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    variants: pd.DataFrame,
    extras: dict[str, pd.DataFrame],
) -> None:
    packet = run_dir / "audit_packet"
    packet.mkdir(parents=True, exist_ok=True)
    files_to_copy = [
        "target_timing.csv",
        "rolling_window_summary.csv",
        "strategy_variant_results.csv",
        "r_multiple_diagnostics.csv",
        "symbol_contribution.csv",
        "regime_summary.csv",
        "data_quality_summary.csv",
        "strategy_health.csv",
        "strategy_lifecycle_events.csv",
        "risk_events.csv",
        "skipped_signal_summary.csv",
        "skipped_signal_sample.csv",
    ]
    for name in files_to_copy:
        src = run_dir / name
        if src.exists():
            (packet / name).write_bytes(src.read_bytes())

    trades = result.trades
    if not trades.empty:
        trades.head(200).to_csv(packet / "trade_audit_sample.csv", index=False)
        trades.sort_values("pnl").head(100).to_csv(packet / "losing_trade_audit_sample.csv", index=False)
        trades.sort_values("pnl", ascending=False).head(100).to_csv(packet / "winning_trade_audit_sample.csv", index=False)
    else:
        pd.DataFrame().to_csv(packet / "trade_audit_sample.csv", index=False)
        pd.DataFrame().to_csv(packet / "losing_trade_audit_sample.csv", index=False)
        pd.DataFrame().to_csv(packet / "winning_trade_audit_sample.csv", index=False)

    main_metric = result.strategy_metrics.loc[result.strategy_metrics["name"] == "combined_tournament"].iloc[0].to_dict()
    target = result.metadata
    rolling90 = rolling_summary.loc[rolling_summary["horizon_trading_days"] == 90].iloc[0].to_dict() if not rolling_summary.empty and (rolling_summary["horizon_trading_days"] == 90).any() else {}
    std_stress = comparative.loc[comparative["period"] == "full"] if not comparative.empty else pd.DataFrame()
    key_findings = {
        "main_result": main_metric,
        "risk_findings": {
            "project_stop_mode": metadata.get("project_stop_mode"),
            "absolute_floor_stop_hit": target.get("absolute_floor_stop_hit"),
            "trailing_drawdown_stop_hit": target.get("trailing_drawdown_stop_hit"),
            "first_project_stop_date": target.get("first_project_stop_date"),
        },
        "target_findings": {
            "target_300_hit": target.get("target_300_hit"),
            "target_300_before_any_stop": target.get("target_300_before_any_stop"),
            "target_400_hit": target.get("target_400_hit"),
            "target_400_before_any_stop": target.get("target_400_before_any_stop"),
        },
        "strategy_findings": {
            "killed_strategies": result.killed_strategies,
            "best_worst_by_pnl": _best_worst_strategy_by_pnl(result.trades),
        },
        "slippage_findings": std_stress.to_dict(orient="records"),
        "rolling_window_findings": rolling90,
        "r_multiple_findings": extras.get("r_multiple_diagnostics", pd.DataFrame()).to_dict(orient="records"),
        "data_quality_findings": {
            "valid_symbols": int((data_coverage.get("status") == "valid").sum()) if "status" in data_coverage else 0,
            "excluded_symbols": int((data_coverage.get("status") == "excluded").sum()) if "status" in data_coverage else 0,
        },
        "recommended_next_actions": [
            "Review whether trailing drawdown invalidates the headline result.",
            "Compare A/B core-only against the full tournament under stress slippage.",
            "Review BIL/SHY and tiny-risk trade diagnostics before trusting R multiples.",
            "Paper-forward-test the strongest fixed variant before adding any new strategy logic.",
        ],
    }
    (packet / "key_findings.json").write_text(json.dumps(key_findings, indent=2, default=str), encoding="utf-8")

    output_files = sorted(str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file())
    row_counts = {}
    for csv in run_dir.glob("*.csv"):
        try:
            row_counts[csv.name] = len(pd.read_csv(csv))
        except Exception:
            row_counts[csv.name] = None
    manifest = {
        "run_id": run_id,
        "run_timestamp_utc": metadata.get("run_timestamp_utc"),
        "code_git_commit_if_available": metadata.get("git_commit_hash"),
        "config_hash": metadata.get("config_hash"),
        "python_version": metadata.get("python_version"),
        "package_versions": metadata.get("package_versions"),
        "data_start": metadata.get("full_backtest_start"),
        "data_end": metadata.get("full_backtest_end"),
        "effective_trading_start": result.metadata.get("effective_first_trading_date"),
        "effective_trading_end": result.metadata.get("effective_last_trading_date"),
        "project_stop_mode": metadata.get("project_stop_mode"),
        "standard_slippage": config["execution"]["standard_slippage_pct_per_side"],
        "stress_slippage": config["execution"]["stress_slippage_pct_per_side"],
        "enabled_strategies_main_run": [s for s in MAIN_STRATEGIES if config["strategies"][s].get("enabled", False)],
        "output_file_list": output_files,
        "row_counts": row_counts,
        "notes": "Paper/demo research only. No broker integration, no real orders, no real-money recommendation.",
    }
    (packet / "audit_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    summary = (
        "# Audit Summary\n\n"
        "This packet summarizes a research-only paper/demo backtest and is intended for human or ChatGPT audit, not live trading.\n\n"
        f"- Final equity: {main_metric.get('final_equity'):.2f}\n"
        f"- Total return: {main_metric.get('total_return'):.2%}\n"
        f"- Max drawdown: {main_metric.get('max_drawdown'):.2f}\n"
        f"- Project stop mode: {metadata.get('project_stop_mode')}\n"
        f"- +300 before any stop: {target.get('target_300_before_any_stop')}\n"
        f"- +400 before any stop: {target.get('target_400_before_any_stop')}\n"
        f"- Killed strategies: {', '.join(result.killed_strategies) if result.killed_strategies else 'None'}\n\n"
        "## Rolling Window Conclusion\n\n"
        f"Rolling 90-day summary: {json.dumps(rolling90, default=str)}\n\n"
        "## R-Multiple Reliability Warning\n\n"
        "Review tiny-risk and BIL/SHY diagnostics before trusting R multiples.\n\n"
        "## Recommended Next Tests\n\n"
        "- Forward-test A/B-only and original variants without parameter changes.\n"
        "- Review stress slippage and rolling 90-day target/stop rates.\n"
        "- Decide whether C/D/E should become shadow-only.\n\n"
        "No real-money recommendation.\n"
    )
    (packet / "audit_summary.md").write_text(summary, encoding="utf-8")
    (packet / "next_questions_for_auditor.md").write_text(
        "# Questions For Auditor\n\n"
        "- Does A/B core-only outperform the full tournament after stress slippage?\n"
        "- Does the strategy hit +300/+400 often enough in rolling 90-day windows?\n"
        "- Does trailing drawdown stop invalidate the headline result?\n"
        "- Are C/D/E worth keeping or should they be shadow-only?\n"
        "- Are BIL/SHY or tiny-risk trades distorting R-multiples?\n"
        "- Which strategy should be paper-forward-tested first?\n",
        encoding="utf-8",
    )
    (packet / "README_FOR_AUDITOR.md").write_text(
        "# README For Auditor\n\n"
        "Start with `audit_summary.md`, then inspect `key_findings.json`, `strategy_variant_results.csv`, "
        "`rolling_window_summary.csv`, `risk_events.csv`, and the trade/skipped-signal samples. "
        "This is research-only paper/demo output and is not a real-money recommendation.\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(run_dir / "audit_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in packet.rglob("*"):
            zf.write(path, path.relative_to(run_dir))


def _git_dirty_status(repo_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return "unknown"
        return "dirty" if result.stdout.strip() else "clean"
    except Exception:
        return "unknown"


def build_headline_metrics(
    run_id: str,
    result: BacktestResult,
    config: dict[str, Any],
    comparative: pd.DataFrame,
    variants: pd.DataFrame,
) -> dict[str, Any]:
    combined = result.strategy_metrics.loc[result.strategy_metrics["name"] == "combined_tournament"].iloc[0]
    equity = result.equity_curve
    best, worst = _best_worst_strategy_by_pnl(result.trades)
    original = variants.loc[
        (variants["variant_name"] == "original_full_tournament")
        & (variants["slippage_label"].isin(["standard", "stress"]))
    ] if not variants.empty else pd.DataFrame()
    standard_final = float(combined["final_equity"])
    stress_final = np.nan
    if not original.empty:
        std = original.loc[original["slippage_label"] == "standard", "final_equity"]
        stress = original.loc[original["slippage_label"] == "stress", "final_equity"]
        if not std.empty:
            standard_final = float(std.iloc[0])
        if not stress.empty:
            stress_final = float(stress.iloc[0])

    bench = result.benchmark_curve
    def bench_final(col: str) -> float:
        return float(bench[col].iloc[-1]) if not bench.empty and col in bench else np.nan

    candidates = variants.loc[
        (variants["slippage_label"] == "standard")
        & (~variants["enabled_strategies"].fillna("").str.contains("C_swing_trend_pullback|D_mean_reversion|E_breakout_vcb", regex=True))
    ] if not variants.empty else pd.DataFrame()
    if candidates.empty:
        best_candidate = ""
        status = "no_candidate"
    else:
        best_row = candidates.sort_values("final_equity", ascending=False).iloc[0]
        best_candidate = str(best_row["variant_name"])
        status = str(best_row.get("suitable_for_forward_paper_test", "watchlist"))

    meta = result.metadata
    return {
        "run_id": run_id,
        "selected_main_run_name": "original_full_tournament_standard",
        "project_stop_mode": config["project"]["project_stop"]["mode"],
        "final_equity": float(combined["final_equity"]),
        "total_return": float(combined["total_return"]),
        "cagr": float(combined["cagr"]),
        "max_drawdown_dollars": float(combined["max_drawdown"]),
        "max_drawdown_pct": float(combined["max_drawdown_pct"]),
        "max_equity": float(equity["equity"].max()) if not equity.empty else np.nan,
        "min_equity": float(equity["equity"].min()) if not equity.empty else np.nan,
        "high_water_mark": float(equity["high_water_mark"].max()) if "high_water_mark" in equity else np.nan,
        "number_of_trades": int(combined["number_of_trades"]),
        "number_of_skipped_signals": int(len(result.skipped_signals)),
        "absolute_floor_stop_hit": bool(meta.get("absolute_floor_stop_hit", False)),
        "trailing_drawdown_stop_hit": bool(meta.get("trailing_drawdown_stop_hit", False)),
        "any_project_stop_hit": bool(meta.get("absolute_floor_stop_hit", False) or meta.get("trailing_drawdown_stop_hit", False)),
        "first_project_stop_type": meta.get("first_project_stop_type", ""),
        "first_project_stop_date": meta.get("first_project_stop_date", ""),
        "equity_at_first_project_stop": meta.get("equity_at_first_project_stop", np.nan),
        "target_300_hit": bool(meta.get("target_300_hit", False)),
        "target_300_first_date": meta.get("target_300_first_date", ""),
        "target_300_trading_days": meta.get("target_300_trading_days", ""),
        "target_300_before_absolute_stop": bool(meta.get("target_300_before_absolute_stop", False)),
        "target_300_before_trailing_stop": bool(meta.get("target_300_before_trailing_stop", False)),
        "target_300_before_any_stop": bool(meta.get("target_300_before_any_stop", False)),
        "target_400_hit": bool(meta.get("target_400_hit", False)),
        "target_400_first_date": meta.get("target_400_first_date", ""),
        "target_400_trading_days": meta.get("target_400_trading_days", ""),
        "target_400_before_absolute_stop": bool(meta.get("target_400_before_absolute_stop", False)),
        "target_400_before_trailing_stop": bool(meta.get("target_400_before_trailing_stop", False)),
        "target_400_before_any_stop": bool(meta.get("target_400_before_any_stop", False)),
        "killed_strategies": result.killed_strategies,
        "best_strategy_by_pnl": best,
        "worst_strategy_by_pnl": worst,
        "standard_slippage_final_equity": standard_final,
        "stress_slippage_final_equity": stress_final,
        "stress_slippage_delta": stress_final - standard_final if np.isfinite(stress_final) else np.nan,
        "benchmark_spy_final_equity": bench_final("SPY_buy_hold"),
        "benchmark_equal_weight_final_equity": bench_final("equal_weight_basket"),
        "benchmark_cash_proxy_final_equity": bench_final("BIL_cash_proxy"),
        "best_forward_test_candidate": best_candidate,
        "forward_test_recommendation_status": status,
    }


def key_findings_from_headline(
    headline: dict[str, Any],
    variants: pd.DataFrame,
    independent_summary: pd.DataFrame,
    r_diag: pd.DataFrame,
    data_quality: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "run_id": headline["run_id"],
        "main_result": {
            "final_equity": headline["final_equity"],
            "total_return": headline["total_return"],
            "max_drawdown_dollars": headline["max_drawdown_dollars"],
            "max_drawdown_pct": headline["max_drawdown_pct"],
            "number_of_trades": headline["number_of_trades"],
        },
        "risk_findings": {
            "project_stop_mode": headline["project_stop_mode"],
            "absolute_floor_stop_hit": headline["absolute_floor_stop_hit"],
            "trailing_drawdown_stop_hit": headline["trailing_drawdown_stop_hit"],
            "any_project_stop_hit": headline["any_project_stop_hit"],
            "first_project_stop_date": headline["first_project_stop_date"],
        },
        "target_findings": {
            "target_300_hit": headline["target_300_hit"],
            "target_300_before_any_stop": headline["target_300_before_any_stop"],
            "target_400_hit": headline["target_400_hit"],
            "target_400_before_any_stop": headline["target_400_before_any_stop"],
        },
        "strategy_findings": {
            "killed_strategies": headline["killed_strategies"],
            "best_strategy_by_pnl": headline["best_strategy_by_pnl"],
            "worst_strategy_by_pnl": headline["worst_strategy_by_pnl"],
            "best_forward_test_candidate": headline["best_forward_test_candidate"],
        },
        "slippage_findings": {
            "standard_final_equity": headline["standard_slippage_final_equity"],
            "stress_final_equity": headline["stress_slippage_final_equity"],
            "stress_delta": headline["stress_slippage_delta"],
        },
        "rolling_window_findings": independent_summary.to_dict(orient="records"),
        "variant_findings": variants.to_dict(orient="records"),
        "exhaustive_rolling_decision": rolling_decision_from_summary(independent_summary),
        "r_multiple_findings": r_diag.to_dict(orient="records"),
        "data_quality_findings": {
            "valid_symbols": int((data_quality.get("status") == "valid").sum()) if "status" in data_quality else 0,
            "excluded_symbols": int((data_quality.get("status") == "excluded").sum()) if "status" in data_quality else 0,
        },
        "recommended_next_actions": [
            "Use independent rolling results as primary validation, not replay diagnostics.",
            "Treat variants with low 90-day target rates as watchlist only.",
            "Keep C/D/E shadow-only unless redesigned and revalidated without optimization.",
            "Review R-multiple diagnostics before trusting expectancy in R.",
        ],
    }


def rolling_decision_from_summary(independent_summary: pd.DataFrame) -> dict[str, Any]:
    if independent_summary.empty:
        return {
            "best_90d_300_before_stop_variant": "",
            "best_90d_400_before_stop_variant": "",
            "best_stress_stability_variant": "",
            "lowest_drawdown_risk_variant": "",
            "best_candidate": "",
            "candidate_status": "not_available",
            "target_probability_assessment": "not_available",
            "cde_status": "shadow_only_or_rejected",
            "fragile_variants": [],
        }

    rows90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90].copy()
    if rows90.empty:
        return {
            "best_90d_300_before_stop_variant": "",
            "best_90d_400_before_stop_variant": "",
            "best_stress_stability_variant": "",
            "lowest_drawdown_risk_variant": "",
            "best_candidate": "",
            "candidate_status": "not_available",
            "target_probability_assessment": "no_90_day_rows",
            "cde_status": "shadow_only_or_rejected",
            "fragile_variants": [],
        }

    candidates = [variant for variant in ROLLING_CANDIDATE_VARIANTS if variant != "original_full_tournament"]
    candidate_rows = rows90.loc[rows90["variant_name"].isin(candidates)].copy()

    def robust_rates(field: str) -> pd.Series:
        return candidate_rows.groupby("variant_name")[field].min().sort_values(ascending=False)

    robust_300 = robust_rates("pct_windows_target_300_before_stop")
    robust_400 = robust_rates("pct_windows_target_400_before_stop")
    best_300 = str(robust_300.index[0]) if not robust_300.empty else ""
    best_400 = str(robust_400.index[0]) if not robust_400.empty else ""

    fragile: list[str] = []
    stability_rows: list[dict[str, Any]] = []
    for variant, group in candidate_rows.groupby("variant_name"):
        standard = group.loc[group["slippage_label"] == "standard"]
        stress = group.loc[group["slippage_label"] == "stress"]
        if standard.empty or stress.empty:
            continue
        std = standard.iloc[0]
        st = stress.iloc[0]
        target_300_delta = float(st["pct_windows_target_300_before_stop"] - std["pct_windows_target_300_before_stop"])
        target_400_delta = float(st["pct_windows_target_400_before_stop"] - std["pct_windows_target_400_before_stop"])
        median_dd_delta = float(st["median_max_drawdown"] - std["median_max_drawdown"])
        worst_dd_delta = float(st["worst_max_drawdown"] - std["worst_max_drawdown"])
        if target_300_delta < -0.05 or target_400_delta < -0.05 or median_dd_delta < -100 or worst_dd_delta < -100:
            fragile.append(str(variant))
        stability_rows.append(
            {
                "variant_name": str(variant),
                "stability_score": target_300_delta + target_400_delta + median_dd_delta / 1000.0 + worst_dd_delta / 1000.0,
            }
        )

    stability = pd.DataFrame(stability_rows)
    best_stability = (
        str(stability.sort_values("stability_score", ascending=False).iloc[0]["variant_name"])
        if not stability.empty
        else ""
    )
    drawdown = candidate_rows.groupby("variant_name")["median_max_drawdown"].min().sort_values(ascending=False)
    lowest_drawdown = str(drawdown.index[0]) if not drawdown.empty else ""

    no_cash_leads = False
    if "current_no_cash_proxy_alpha_AB" in robust_300.index:
        no_cash_leads = all(
            float(robust_300["current_no_cash_proxy_alpha_AB"]) >= float(robust_300.get(other, -np.inf))
            and float(robust_400["current_no_cash_proxy_alpha_AB"]) >= float(robust_400.get(other, -np.inf))
            for other in ["current_momentum_only_A", "current_core_only_AB"]
        )

    best_300_rate = float(robust_300.iloc[0]) if not robust_300.empty else 0.0
    best_400_rate = float(robust_400.iloc[0]) if not robust_400.empty else 0.0
    best_candidate = "current_no_cash_proxy_alpha_AB" if no_cash_leads else best_300
    candidate_status = "leading_watchlist_candidate" if best_300_rate >= 0.10 and best_candidate else "watchlist_not_validated"
    low_300 = best_300_rate < 0.10
    very_low_400 = best_400_rate < 0.05
    if low_300 and very_low_400:
        probability = "low_probability_for_300_and_very_low_probability_for_400"
    elif low_300:
        probability = "low_probability_for_300"
    elif very_low_400:
        probability = "very_low_probability_for_400"
    else:
        probability = "watchlist_not_validated"

    return {
        "best_90d_300_before_stop_variant": best_300,
        "best_90d_300_before_stop_rate": best_300_rate,
        "best_90d_400_before_stop_variant": best_400,
        "best_90d_400_before_stop_rate": best_400_rate,
        "best_stress_stability_variant": best_stability,
        "lowest_drawdown_risk_variant": lowest_drawdown,
        "best_candidate": best_candidate,
        "candidate_status": candidate_status,
        "target_probability_assessment": probability,
        "cde_status": "remain_rejected_or_shadow_only",
        "fragile_variants": sorted(set(fragile)),
    }


def write_exhaustive_rolling_decision(path: Path, independent_summary: pd.DataFrame) -> None:
    decision = rolling_decision_from_summary(independent_summary)
    rows90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90].copy() if not independent_summary.empty else pd.DataFrame()
    display_cols = [
        "variant_name",
        "slippage_label",
        "number_of_windows",
        "window_sampling_method",
        "pct_windows_target_300_before_stop",
        "pct_windows_target_400_before_stop",
        "pct_windows_any_stop_hit",
        "pct_windows_trailing_stop_hit",
        "median_max_drawdown",
        "worst_max_drawdown",
    ]
    table = rows90[[c for c in display_cols if c in rows90]].to_string(index=False) if not rows90.empty else "No 90-day rows."
    text = f"""# Exhaustive Rolling Decision

This file is research-only paper/demo evidence. It is not a real-money trading recommendation.

Replay rolling diagnostics are secondary. The table below is based on independent rolling-window simulations.

## 90-Day Summary
{table}

## Decision Answers
- Best 90-day +$300 before stop rate: `{decision['best_90d_300_before_stop_variant']}` at {decision.get('best_90d_300_before_stop_rate', 0.0):.2%} using the robust minimum across standard/stress slippage.
- Best 90-day +$400 before stop rate: `{decision['best_90d_400_before_stop_variant']}` at {decision.get('best_90d_400_before_stop_rate', 0.0):.2%} using the robust minimum across standard/stress slippage.
- Best stress-slippage stability: `{decision['best_stress_stability_variant']}`.
- Lowest drawdown risk: `{decision['lowest_drawdown_risk_variant']}` by the least-bad robust median drawdown.
- Best current candidate: `{decision['best_candidate']}` with status `{decision['candidate_status']}`.
- Target probability assessment: `{decision['target_probability_assessment']}`.
- C/D/E status: `{decision['cde_status']}`.
- Fragile variants: {decision['fragile_variants']}.

## Interpretation Rules Applied
- If 90-day +$300 before stop rate is below 10%, mark low-probability.
- If 90-day +$400 before stop rate is below 5%, mark very low-probability.
- If stress slippage materially worsens target rates or drawdown, mark fragile.
- If original_full_tournament is weaker than A/B variants, do not forward-test it.
- If current_no_cash_proxy_alpha_AB beats current_momentum_only_A and current_core_only_AB under both standard and stress, mark it as leading watchlist candidate, not validated.
- Nothing is marked validated unless evidence is strong across both standard and stress.
"""
    path.write_text(text, encoding="utf-8")


def strategy_family_comparison(variants: pd.DataFrame, independent_summary: pd.DataFrame) -> pd.DataFrame:
    if variants.empty:
        return pd.DataFrame()
    standard = variants.loc[variants["slippage_label"] == "standard"].copy()
    stress = variants.loc[variants["slippage_label"] == "stress", ["variant_name", "final_equity"]].rename(
        columns={"final_equity": "stress_final_equity"}
    )
    out = standard.merge(stress, on="variant_name", how="left")
    out["stress_final_equity_delta"] = out["stress_final_equity"] - out["final_equity"]
    if not independent_summary.empty:
        rolling90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90]
        pivot = rolling90.pivot_table(
            index="variant_name",
            columns="slippage_label",
            values=["pct_windows_target_300_before_stop", "pct_windows_target_400_before_stop", "pct_windows_any_stop_hit"],
            aggfunc="first",
        )
        pivot.columns = [f"rolling90_{metric}_{label}" for metric, label in pivot.columns]
        out = out.merge(pivot.reset_index(), on="variant_name", how="left")
    columns = [
        "variant_name",
        "evidence_family",
        "recommended_status",
        "final_equity",
        "stress_final_equity",
        "stress_final_equity_delta",
        "max_drawdown_dollars",
        "target_300_before_any_stop",
        "target_400_before_any_stop",
        "rolling90_pct_windows_target_300_before_stop_standard",
        "rolling90_pct_windows_target_300_before_stop_stress",
        "rolling90_pct_windows_target_400_before_stop_standard",
        "rolling90_pct_windows_target_400_before_stop_stress",
        "rolling90_pct_windows_any_stop_hit_standard",
        "rolling90_pct_windows_any_stop_hit_stress",
        "forward_test_decision_reason",
    ]
    return out[[col for col in columns if col in out]]


def write_anti_overfitting_log(
    path: Path,
    independent_summary: pd.DataFrame,
    rolling_status: dict[str, Any] | None = None,
    candidate_gate: pd.DataFrame | None = None,
) -> None:
    rolling_status = rolling_status or {}
    methods = sorted(independent_summary["window_sampling_method"].dropna().unique()) if "window_sampling_method" in independent_summary else []
    all_possible = bool(methods and set(methods) == {"all_possible"})
    nonfinal_note = ""
    if independent_summary.empty:
        nonfinal_note = "- Independent rolling validation did not complete; this run is non-final for rolling-window probability claims.\n"
    elif not rolling_status.get("final_validation_completed", all_possible):
        nonfinal_note = "- Rolling results are deterministic research samples or partial results; they are non-final.\n"
    gate_note = ""
    if candidate_gate is not None and not candidate_gate.empty:
        excluded = candidate_gate.loc[~candidate_gate["passed_gate"].astype(bool)]
        if not excluded.empty:
            gate_note = (
                "- Candidate gate excluded or shadowed these rows before rolling validation:\n"
                + "\n".join(
                    f"  - {row.variant_name} / {row.slippage_label}: {row.gate_status} ({row.gate_failure_reasons})"
                    for row in excluded.itertuples(index=False)
                )
                + "\n"
            )
    text = f"""# Anti-Overfitting Log

- No parameter optimization was run.
- No grid search was run.
- Validation mode used: {rolling_status.get('validation_mode', 'unknown')}.
- Strategy parameters were pre-specified in `config_used.yaml`.
- Existing C/D/E strategies were not tuned to improve results.
- New strategy families N1-N4 were tested using fixed daily ETF rules.
- All weak results are retained in `strategy_variant_results.csv` and `independent_rolling_window_summary.csv`.
- All possible rolling windows used: {all_possible}.
- Rolling window methods observed: {methods}.
- Rolling validation final: {bool(rolling_status.get('final_validation_completed', all_possible and not independent_summary.empty))}.
- Rolling method used: {rolling_status.get('rolling_method', 'unknown')}.
- Sampled results are final: {rolling_status.get('sampled_results_are_final', False)}.
{nonfinal_note.rstrip()}
{gate_note.rstrip()}
- If any sampled windows appear in a run, treat that run as non-final validation.
- No broker integration, no live orders, no AI trading gate, and no real-money recommendation.
"""
    path.write_text(text, encoding="utf-8")


def write_vectorized_monthly_allocation_deferred(path: Path) -> None:
    path.write_text(
        "# Vectorized Monthly Allocation Deferred\n\n"
        "A vectorized monthly-allocation rolling path was considered for N1-N4 style strategies, "
        "but it was deferred in this pass to avoid introducing a second execution model with subtle "
        "fill, stop, cash, or target-timing differences from the audited event engine.\n\n"
        "The current validation speedup comes from validation modes, deterministic sampling, candidate "
        "gating, rolling cache reuse, chunk checkpointing, and progress logging. Candidate-exhaustive "
        "validation still uses the same event-driven backtest simulation as the main evidence path.\n\n"
        "No strategy parameters were changed, no optimization was introduced, and no real-money "
        "recommendation is made.\n",
        encoding="utf-8",
    )


def write_redesigned_tournament_decision(path: Path, variants: pd.DataFrame, independent_summary: pd.DataFrame) -> None:
    if independent_summary.empty:
        table = variants.to_string(index=False) if not variants.empty else "No variant rows."
        path.write_text(
            "# Redesigned Tournament Decision\n\n"
            "This run is non-final for redesigned tournament selection because independent all-possible "
            "rolling-window validation did not complete.\n\n"
            "No evidence-backed strategy is validated or promoted. Current A/B variants and new N1-N4 families "
            "remain watchlist/research candidates only until exact rolling validation is completed or the rolling "
            "engine is optimized.\n\n"
            "C/D/E remain rejected or shadow-only based on prior loss-budget kills.\n\n"
            "## Variant Full-Period Rows\n\n"
            f"{table}\n\n"
            "No real-money recommendation.\n",
            encoding="utf-8",
        )
        return
    comparison = strategy_family_comparison(variants, independent_summary)
    decision = rolling_decision_from_summary(independent_summary)
    rows90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90] if not independent_summary.empty else pd.DataFrame()
    def rate(variant: str, slip: str, col: str) -> float:
        row = rows90.loc[(rows90["variant_name"] == variant) & (rows90["slippage_label"] == slip)]
        return float(row.iloc[0][col]) if not row.empty and col in row else float("nan")
    current = "current_no_cash_proxy_alpha_AB"
    evidence_variants = [v for v in variants["variant_name"].unique() if str(v).startswith("evidence_")] if not variants.empty else []
    best_new = ""
    best_new_rate = -np.inf
    for variant in evidence_variants:
        robust = min(
            rate(variant, "standard", "pct_windows_target_300_before_stop"),
            rate(variant, "stress", "pct_windows_target_300_before_stop"),
        )
        if np.isfinite(robust) and robust > best_new_rate:
            best_new_rate = robust
            best_new = str(variant)
    current_rate = min(
        rate(current, "standard", "pct_windows_target_300_before_stop"),
        rate(current, "stress", "pct_windows_target_300_before_stop"),
    )
    beats_current = bool(np.isfinite(best_new_rate) and np.isfinite(current_rate) and best_new_rate > current_rate)
    table = comparison.to_string(index=False) if not comparison.empty else "No comparison rows."
    text = f"""# Redesigned Tournament Decision

This is research-only paper/demo evidence. It is not a real-money trading recommendation.

## Blunt Answers
1. Did any evidence-backed strategy beat current_no_cash_proxy_alpha_AB? {'Yes: ' + best_new if beats_current else 'No.'}
2. Did any strategy materially improve 90-day +$300 before stop rate? {'Yes.' if beats_current else 'No material improvement over current_no_cash_proxy_alpha_AB.'}
3. Did any strategy materially improve 90-day +$400 before stop rate? Review the table; +$400 remains low probability unless the rate is consistently above 5% under stress.
4. Did any strategy improve stress-slippage robustness? Best stress-stability variant: `{decision['best_stress_stability_variant']}`.
5. Did any strategy reduce drawdown while preserving target probability? Lowest drawdown-risk variant: `{decision['lowest_drawdown_risk_variant']}`; target preservation must be judged against the rolling target columns.
6. Should current A/B remain the best candidate? {'No, a new evidence variant leads on 90-day +300 robustness.' if beats_current else 'Yes, current_no_cash_proxy_alpha_AB remains the main comparator.'}
7. Should any new strategy become the leading candidate? {'Leading watchlist candidate: ' + best_new if beats_current else 'No new strategy displaces the current comparator.'}
8. Should C/D/E remain rejected/shadow-only? Yes.
9. Is the +$300 target still modest probability? Yes; even useful rates are not high enough to call reliable.
10. Is the +$400 target still low probability? Yes unless the final evidence table shows stress 90-day +$400 before-stop rates above 5%.
11. Is the redesigned tournament better than the current tournament? {'Possibly, but not validated.' if beats_current else 'Not demonstrated by this run.'}
12. Single best next paper-forward candidate: `{best_new if beats_current else current}`.

## Strategy Family Comparison
{table}

No variant is marked validated.
"""
    path.write_text(text, encoding="utf-8")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def consistency_check(
    evidence_dir: Path,
    run_dir: Path,
    headline: dict[str, Any],
) -> dict[str, Any]:
    checked_files = []
    errors: list[str] = []
    warnings: list[str] = []
    checked_fields = [
        "run_id",
        "final_equity",
        "total_return",
        "max_drawdown_dollars",
        "max_drawdown_pct",
        "number_of_trades",
        "project_stop_mode",
        "absolute_floor_stop_hit",
        "trailing_drawdown_stop_hit",
        "any_project_stop_hit",
        "first_project_stop_date",
        "target_300_before_any_stop",
        "target_400_before_any_stop",
    ]

    def close(field: str, actual: Any, expected: Any, source: str) -> None:
        if isinstance(expected, float):
            if not np.isfinite(expected) and pd.isna(actual):
                return
            if abs(float(actual) - expected) > 1e-6:
                errors.append(f"{source}.{field}={actual} != headline {expected}")
        elif isinstance(expected, bool):
            if _coerce_bool(actual) != expected:
                errors.append(f"{source}.{field}={actual} != headline {expected}")
        else:
            if str(actual) != str(expected):
                errors.append(f"{source}.{field}={actual} != headline {expected}")

    key_path = evidence_dir / "key_findings.json"
    headline_path = evidence_dir / "headline_metrics.json"
    if headline_path.exists():
        checked_files.append(str(headline_path.name))
        stored = json.loads(headline_path.read_text(encoding="utf-8"))
        for field in checked_fields:
            if field in stored and field in headline:
                close(field, stored[field], headline[field], "headline_metrics")

    if key_path.exists():
        checked_files.append(str(key_path.name))
        key = json.loads(key_path.read_text(encoding="utf-8"))
        close("final_equity", key["main_result"]["final_equity"], headline["final_equity"], "key_findings")
        close("total_return", key["main_result"]["total_return"], headline["total_return"], "key_findings")
        close("max_drawdown_dollars", key["main_result"]["max_drawdown_dollars"], headline["max_drawdown_dollars"], "key_findings")
        close("number_of_trades", key["main_result"]["number_of_trades"], headline["number_of_trades"], "key_findings")
        close("any_project_stop_hit", key["risk_findings"]["any_project_stop_hit"], headline["any_project_stop_hit"], "key_findings")

    target_path = evidence_dir / "target_timing.csv"
    if target_path.exists():
        checked_files.append(str(target_path.name))
        row = pd.read_csv(target_path).iloc[0]
        for field in [
            "target_300_before_any_stop",
            "target_400_before_any_stop",
            "absolute_floor_stop_hit",
            "trailing_drawdown_stop_hit",
            "any_project_stop_hit",
            "first_project_stop_date",
        ]:
            if field in row:
                close(field, row[field], headline[field], "target_timing")

    variant_path = evidence_dir / "strategy_variant_results.csv"
    if variant_path.exists():
        checked_files.append(str(variant_path.name))
        variants = pd.read_csv(variant_path)
        row = variants.loc[
            (variants["variant_name"] == "original_full_tournament")
            & (variants["slippage_label"] == "standard")
        ].iloc[0]
        close(
            "final_equity",
            row["final_equity"],
            headline.get("standard_slippage_final_equity", headline["final_equity"]),
            "strategy_variant_results",
        )
        close("target_300_before_any_stop", row["target_300_before_any_stop"], headline["target_300_before_any_stop"], "strategy_variant_results")
        close("target_400_before_any_stop", row["target_400_before_any_stop"], headline["target_400_before_any_stop"], "strategy_variant_results")

    metadata_path = evidence_dir / "run_metadata.json"
    if metadata_path.exists():
        checked_files.append(str(metadata_path.name))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        main = metadata.get("main_run", {})
        meta_headline = metadata.get("headline_metrics", {})
        close("project_stop_mode", metadata.get("project_stop_mode"), headline["project_stop_mode"], "run_metadata")
        if meta_headline:
            close("final_equity", meta_headline.get("final_equity"), headline["final_equity"], "run_metadata")
            close("total_return", meta_headline.get("total_return"), headline["total_return"], "run_metadata")
            close("max_drawdown_dollars", meta_headline.get("max_drawdown_dollars"), headline["max_drawdown_dollars"], "run_metadata")
            close("max_drawdown_pct", meta_headline.get("max_drawdown_pct"), headline["max_drawdown_pct"], "run_metadata")
            close("number_of_trades", meta_headline.get("number_of_trades"), headline["number_of_trades"], "run_metadata")
        close("target_300_before_any_stop", main.get("target_300_before_any_stop"), headline["target_300_before_any_stop"], "run_metadata")
        close("target_400_before_any_stop", main.get("target_400_before_any_stop"), headline["target_400_before_any_stop"], "run_metadata")

    manifest_path = evidence_dir / "evidence_manifest.json"
    if manifest_path.exists():
        checked_files.append(str(manifest_path.name))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        close("run_id", manifest.get("run_id"), headline["run_id"], "evidence_manifest")
        close("project_stop_mode", manifest.get("project_stop_mode"), headline["project_stop_mode"], "evidence_manifest")

    report_path = run_dir / "summary_report.md"
    if report_path.exists():
        checked_files.append(str(report_path.name))
        text = report_path.read_text(encoding="utf-8")
        match = re.search(r"Final equity: \$([0-9,]+\.[0-9]{2})", text)
        if match:
            parsed = float(match.group(1).replace(",", ""))
            if round(parsed, 2) != round(float(headline["final_equity"]), 2):
                errors.append(f"summary_report final_equity={parsed} != headline {headline['final_equity']}")
        else:
            warnings.append("summary_report final equity was not parseable")

    if headline["trailing_drawdown_stop_hit"] and not headline["any_project_stop_hit"]:
        errors.append("trailing_drawdown_stop_hit true but any_project_stop_hit false")

    return {
        "passed": not errors,
        "checked_files": checked_files,
        "checked_fields": checked_fields,
        "errors": errors,
        "warnings": warnings,
    }


def _artifact_counts(path: Path) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for file in sorted(path.rglob("*")):
        if not file.is_file() or file.name == "evidence_packet.zip":
            continue
        rel = str(file.relative_to(path))
        try:
            if file.suffix == ".csv":
                counts[rel] = len(pd.read_csv(file))
            else:
                counts[rel] = len(file.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            counts[rel] = None
    return counts


def _copy_if_exists(src: Path, dest: Path) -> None:
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def write_evidence_summary(
    evidence_dir: Path,
    headline: dict[str, Any],
    consistency: dict[str, Any],
    independent_summary: pd.DataFrame,
    replay_summary: pd.DataFrame,
    variants: pd.DataFrame,
    strategy_health_df: pd.DataFrame,
    r_diag: pd.DataFrame,
) -> None:
    rolling90 = independent_summary.loc[independent_summary["horizon_trading_days"] == 90] if not independent_summary.empty else pd.DataFrame()
    rolling_decision = rolling_decision_from_summary(independent_summary)
    best_candidate = headline.get("best_forward_test_candidate", "")
    cde_status = "shadow-only or rejected for now because C/D/E were killed by loss budgets in the main tournament"
    warning = "" if consistency["passed"] else "\n> WARNING: Evidence consistency failed. Review `consistency_check.json` before using this packet.\n"
    validation_mode = headline.get("validation_mode", "unknown")
    rolling_method = headline.get("rolling_method", "unknown")
    final_validation_completed = bool(headline.get("final_validation_completed", False))
    sampled_results_are_final = bool(headline.get("sampled_results_are_final", False))
    rolling_warning = ""
    if independent_summary.empty:
        rolling_warning = (
            "\n> WARNING: Independent rolling validation did not complete in this run. "
            "Treat strategy-family conclusions as non-final and review `rolling_validation_failure.md` or "
            "`rolling_validation_incomplete.md` if present.\n"
        )
    elif not final_validation_completed:
        rolling_warning = (
            "\n> WARNING: These rolling results are deterministic research samples, not final exhaustive validation. "
            "Use them for screening only; finalist claims still require candidate_exhaustive mode.\n"
        )
    sampling_note = ""
    if not independent_summary.empty and "window_sampling_method" in independent_summary:
        methods = ", ".join(sorted(str(x) for x in independent_summary["window_sampling_method"].dropna().unique()))
        possible = ""
        if "possible_window_count" in independent_summary:
            possible = f" Possible window counts by group range up to {int(independent_summary['possible_window_count'].max())}."
        sampling_note = (
            f"\nSampling note: independent rolling rows report `window_sampling_method={methods}`."
            f"{possible} If the method is not `all_possible`, treat the rates as deterministic audit samples, not exhaustive rolling probabilities.\n"
        )
    text = f"""# Evidence Summary

{warning}{rolling_warning}
## 1. Research-Only Statement
This is paper/demo research only. There is no broker integration, no live orders, no AI trading gate, and no real-money recommendation.

## 2. Run Identity And Config
- Run id: `{headline['run_id']}`
- Project stop mode: `{headline['project_stop_mode']}`
- Selected main run: `{headline['selected_main_run_name']}`
- Validation mode: `{validation_mode}`
- Rolling method: `{rolling_method}`
- Final validation completed: {final_validation_completed}
- Sampled results are final: {sampled_results_are_final}

If `rolling_method` is not `all_possible`, these rolling results are deterministic research samples, not final exhaustive validation.

## 3. Headline Result
- Final equity: ${headline['final_equity']:,.2f}
- Total return: {headline['total_return']:.2%}
- CAGR: {headline['cagr']:.2%}
- Max drawdown: ${headline['max_drawdown_dollars']:,.2f} ({headline['max_drawdown_pct']:.2%})
- Trades: {headline['number_of_trades']}
- Skipped signals: {headline['number_of_skipped_signals']}

## 4. Stop Mode And Risk-Budget Result
- Absolute floor stop hit: {headline['absolute_floor_stop_hit']}
- Trailing drawdown stop hit: {headline['trailing_drawdown_stop_hit']}
- Any project stop hit: {headline['any_project_stop_hit']}
- First project stop: {headline['first_project_stop_type']} on {headline['first_project_stop_date']}

## 5. Target Timing
- +$300 hit before any selected stop: {headline['target_300_before_any_stop']}
- +$400 hit before any selected stop: {headline['target_400_before_any_stop']}

## 6. Standard Vs Stress Slippage
- Standard final equity: ${headline['standard_slippage_final_equity']:,.2f}
- Stress final equity: ${headline['stress_slippage_final_equity']:,.2f}
- Stress delta: ${headline['stress_slippage_delta']:,.2f}

## 7. Strategy Variant Comparison
{variants.to_string(index=False)}

New evidence-backed strategy family comparison is written to `evidence_strategy_family_comparison.csv`.
The redesigned tournament decision is written to `redesigned_tournament_decision.md`, and anti-overfitting notes are written to `anti_overfitting_log.md`.

## 8. Independent Rolling-Window Validation
Replay rolling diagnostics are not final validation. Independent rolling-window simulations are the primary validation.
{sampling_note}

Decision snapshot from `exhaustive_rolling_decision.md`:
- Best robust 90-day +$300 before stop variant: `{rolling_decision['best_90d_300_before_stop_variant']}` at {rolling_decision.get('best_90d_300_before_stop_rate', 0.0):.2%}
- Best robust 90-day +$400 before stop variant: `{rolling_decision['best_90d_400_before_stop_variant']}` at {rolling_decision.get('best_90d_400_before_stop_rate', 0.0):.2%}
- Best candidate status: `{rolling_decision['best_candidate']}` / `{rolling_decision['candidate_status']}`
- Probability assessment: `{rolling_decision['target_probability_assessment']}`

{independent_summary.to_string(index=False) if not independent_summary.empty else 'No independent rolling summary.'}

## 9. Replay Rolling Diagnostics
These are secondary diagnostics only and do not reset strategy state independently.

{replay_summary.to_string(index=False) if not replay_summary.empty else 'No replay rolling summary.'}

## 10. Strategy Health: A/B/C/D/E
{strategy_health_df.to_string(index=False) if not strategy_health_df.empty else 'No strategy health rows.'}

## 11. R-Multiple Quality Warning
R-multiple quality is not automatically trusted. Review tiny actual-risk and BIL/SHY rows in `r_multiple_diagnostics.csv`.

{r_diag.to_string(index=False) if not r_diag.empty else 'No R diagnostics.'}

## 12. Symbol Concentration
Review `symbol_contribution.csv`, especially BIL and SHY flags.

## 13. Skipped Signals
Review `skipped_signal_summary.csv` and `skipped_signal_sample.csv`; only rejected generated signals are included.

## 14. Risk Events
Review `risk_events.csv` for stops, loss blocks, risk-cap blocks, gap-through stops, and final marks.

## 15. Data Quality
Review `data_quality_summary.csv` and `data_quality_summary.md` for coverage, late inception, and exclusions.

## 16. Consistency Check Result
- Passed: {consistency['passed']}
- Errors: {consistency['errors']}
- Warnings: {consistency['warnings']}

## 17. What Would Invalidate This Strategy
- Low independent 90-day +$300/+400 target-before-stop rates.
- Trailing drawdown stop invalidates most target-reaching windows.
- Stress slippage materially damages results.
- A-only or A/B does not survive risk-adjusted review.
- Results depend on BIL/SHY or tiny-risk R-multiple artifacts.
- C/D/E continue hitting loss budgets.
- Top trades explain most profit.

## 18. Best Current Candidate For Paper Forward Test
- Candidate: {rolling_decision.get('best_candidate') or best_candidate or 'None'}
- Status: {headline.get('forward_test_recommendation_status', 'watchlist')}
- C/D/E status: {cde_status}.

## 19. Recommended Next Actions
- Upload the recommended evidence files in `README_FOR_AUDITOR.md`.
- Audit independent rolling windows before any forward paper test.
- Do not tune parameters based on this packet.
- Treat all candidates as watchlist until independent evidence improves.

## 20. No Real-Money Recommendation
This packet does not recommend real-money trading.
"""
    (evidence_dir / "evidence_summary.md").write_text(text, encoding="utf-8")


def create_evidence_bundle(
    run_dir: Path,
    evidence_root: Path,
    run_id: str,
    result: BacktestResult,
    config: dict[str, Any],
    metadata: dict[str, Any],
    data_coverage: pd.DataFrame,
    comparative: pd.DataFrame,
    replay_rolling_summary: pd.DataFrame,
    independent_results: pd.DataFrame,
    independent_summary: pd.DataFrame,
    variants: pd.DataFrame,
    audit_tables: dict[str, pd.DataFrame],
    rolling_status: dict[str, Any] | None = None,
    candidate_gate: pd.DataFrame | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    rolling_status = rolling_status or {}
    evidence_dir = evidence_root / "runs" / run_id
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    (evidence_dir / "charts").mkdir(parents=True, exist_ok=True)

    _copy_if_exists(run_dir / "config_used.yaml", evidence_dir / "config_used.yaml")
    _copy_if_exists(run_dir / "run_metadata.json", evidence_dir / "run_metadata.json")
    _copy_if_exists(run_dir / "package_versions.json", evidence_dir / "package_versions.json")
    _copy_if_exists(run_dir / "pip_freeze.txt", evidence_dir / "pip_freeze.txt")
    _copy_if_exists(run_dir / "target_timing.csv", evidence_dir / "target_timing.csv")
    _copy_if_exists(run_dir / "risk_events.csv", evidence_dir / "risk_events.csv")
    _copy_if_exists(run_dir / "strategy_lifecycle_events.csv", evidence_dir / "strategy_lifecycle_events.csv")
    _copy_if_exists(run_dir / "equity_curve.png", evidence_dir / "charts" / "equity_curve.png")
    _copy_if_exists(run_dir / "drawdown_curve.png", evidence_dir / "charts" / "drawdown_curve.png")
    for extra_name in [
        "candidate_gate_results.csv",
        "rolling_sample_plan.csv",
        "rolling_progress.jsonl",
        "rolling_cache_manifest.json",
        "rolling_validation_incomplete.md",
        "rolling_validation_failure.md",
    ]:
        _copy_if_exists(run_dir / extra_name, evidence_dir / extra_name)

    for name, df in audit_tables.items():
        df.to_csv(evidence_dir / f"{name}.csv", index=False)
    if candidate_gate is not None and not candidate_gate.empty:
        candidate_gate.to_csv(evidence_dir / "candidate_gate_results.csv", index=False)
    variants.to_csv(evidence_dir / "strategy_variant_results.csv", index=False)
    independent_results.to_csv(evidence_dir / "independent_rolling_window_results.csv", index=False)
    independent_results.head(500).to_csv(evidence_dir / "independent_rolling_window_results_sample.csv", index=False)
    independent_summary.to_csv(evidence_dir / "independent_rolling_window_summary.csv", index=False)
    replay_rolling_summary.to_csv(evidence_dir / "replay_rolling_window_summary.csv", index=False)
    if independent_summary.empty:
        failure_text = (
            "# Rolling Validation Failure / Non-Final Notice\n\n"
            "Independent all-possible rolling-window validation did not complete for this run.\n\n"
            "The expanded candidate matrix was too expensive for the current pure-Python daily backtest engine "
            "during local execution. No sampled rolling-window result is being presented as final validation.\n\n"
            f"Configured rolling validation: `{config.get('rolling_validation', {})}`\n\n"
            "Implication: 30/60/90/180-day target-before-stop probabilities for the redesigned strategy families "
            "are unavailable in this evidence bundle. Treat all strategy-family conclusions as non-final watchlist "
            "research only until the rolling engine is optimized or an explicit long-running job completes.\n\n"
            "No real-money recommendation.\n"
        )
        (run_dir / "rolling_validation_failure.md").write_text(failure_text, encoding="utf-8")
        (evidence_dir / "rolling_validation_failure.md").write_text(failure_text, encoding="utf-8")
    result.trades.to_csv(evidence_dir / "trade_audit_full.csv", index=False)
    result.trades.head(200).to_csv(evidence_dir / "trade_audit_sample.csv", index=False)
    result.trades.sort_values("pnl", ascending=False).head(100).to_csv(evidence_dir / "winning_trade_audit_sample.csv", index=False)
    result.trades.sort_values("pnl", ascending=True).head(100).to_csv(evidence_dir / "losing_trade_audit_sample.csv", index=False)
    data_quality_markdown(audit_tables.get("data_quality_summary", pd.DataFrame())).encode()
    (evidence_dir / "data_quality_summary.md").write_text(
        data_quality_markdown(audit_tables.get("data_quality_summary", pd.DataFrame())),
        encoding="utf-8",
    )

    benchmark_summary = benchmark_summary_frame(result, config, independent_summary)
    benchmark_summary.to_csv(evidence_dir / "benchmark_summary.csv", index=False)
    write_exhaustive_rolling_decision(run_dir / "exhaustive_rolling_decision.md", independent_summary)
    write_exhaustive_rolling_decision(evidence_dir / "exhaustive_rolling_decision.md", independent_summary)
    family_comparison = strategy_family_comparison(variants, independent_summary)
    family_comparison.to_csv(run_dir / "evidence_strategy_family_comparison.csv", index=False)
    family_comparison.to_csv(evidence_dir / "evidence_strategy_family_comparison.csv", index=False)
    write_redesigned_tournament_decision(run_dir / "redesigned_tournament_decision.md", variants, independent_summary)
    write_redesigned_tournament_decision(evidence_dir / "redesigned_tournament_decision.md", variants, independent_summary)
    write_anti_overfitting_log(run_dir / "anti_overfitting_log.md", independent_summary, rolling_status, candidate_gate)
    write_anti_overfitting_log(evidence_dir / "anti_overfitting_log.md", independent_summary, rolling_status, candidate_gate)
    write_vectorized_monthly_allocation_deferred(run_dir / "vectorized_monthly_allocation_deferred.md")
    write_vectorized_monthly_allocation_deferred(evidence_dir / "vectorized_monthly_allocation_deferred.md")

    headline = build_headline_metrics(run_id, result, config, comparative, variants)
    headline.update(
        {
            "validation_mode": rolling_status.get("validation_mode", config.get("validation", {}).get("mode", "unknown")),
            "rolling_method": rolling_status.get("rolling_method", config.get("rolling_validation", {}).get("method", "unknown")),
            "mark_as_final": bool(rolling_status.get("mark_as_final", False)),
            "sampled_results_are_final": bool(rolling_status.get("sampled_results_are_final", False)),
            "final_validation_completed": bool(rolling_status.get("final_validation_completed", False)),
            "rolling_completed": bool(rolling_status.get("rolling_completed", False)),
            "rolling_windows_run": int(rolling_status.get("number_of_windows", len(independent_results))),
            "rolling_possible_windows": int(rolling_status.get("possible_window_count", 0) or 0),
        }
    )
    rolling_decision = rolling_decision_from_summary(independent_summary)
    headline["best_forward_test_candidate"] = rolling_decision.get("best_candidate", headline["best_forward_test_candidate"])
    headline["forward_test_recommendation_status"] = rolling_decision.get(
        "candidate_status", headline["forward_test_recommendation_status"]
    )
    metadata_with_headline = dict(metadata)
    metadata_with_headline["headline_metrics"] = headline
    write_json(run_dir / "run_metadata.json", metadata_with_headline)
    write_json(evidence_dir / "run_metadata.json", metadata_with_headline)
    write_json(evidence_dir / "headline_metrics.json", headline)
    key = key_findings_from_headline(
        headline,
        variants,
        independent_summary,
        audit_tables.get("r_multiple_diagnostics", pd.DataFrame()),
        audit_tables.get("data_quality_summary", pd.DataFrame()),
    )
    write_json(evidence_dir / "key_findings.json", key)

    consistency = consistency_check(evidence_dir, run_dir, headline)
    write_json(evidence_dir / "consistency_check.json", consistency)
    write_evidence_summary(
        evidence_dir,
        headline,
        consistency,
        independent_summary,
        replay_rolling_summary,
        variants,
        audit_tables.get("strategy_health", pd.DataFrame()),
        audit_tables.get("r_multiple_diagnostics", pd.DataFrame()),
    )
    readme_warning = "" if consistency["passed"] else "\nWARNING: Evidence consistency failed. Inspect `consistency_check.json` first.\n"
    (evidence_dir / "README_FOR_AUDITOR.md").write_text(
        "# README For Auditor\n\n"
        f"{readme_warning}\n"
        "Upload this folder or `evidence_packet.zip` for audit. Recommended upload set:\n\n"
        "1. `evidence_summary.md`\n"
        "2. `key_findings.json`\n"
        "3. `headline_metrics.json`\n"
        "4. `consistency_check.json`\n"
        "5. `exhaustive_rolling_decision.md`\n"
        "6. `redesigned_tournament_decision.md`\n"
        "7. `anti_overfitting_log.md`\n"
        "8. `evidence_strategy_family_comparison.csv`\n"
        "9. `independent_rolling_window_summary.csv`\n"
        "10. `strategy_variant_results.csv`\n"
        "11. `strategy_health.csv`\n"
        "12. `r_multiple_diagnostics.csv`\n"
        "13. `symbol_contribution.csv`\n"
        "14. `risk_events.csv`\n"
        "15. `trade_audit_sample.csv`\n"
        "16. `skipped_signal_summary.csv`\n\n"
        "If the auditor asks for full trade evidence, upload `trade_audit_full.csv` separately because it may be larger.\n\n"
        "This is paper/demo research only. No broker integration, no real orders, no real-money recommendation.\n",
        encoding="utf-8",
    )
    (evidence_dir / "next_questions_for_auditor.md").write_text(
        "# Next Questions For Auditor\n\n"
        "- Are all evidence files internally consistent?\n"
        "- Did +300/+400 happen before the selected project stop?\n"
        "- Does the strategy reach +300/+400 often enough in independent 90-day windows?\n"
        "- Does trailing drawdown stop invalidate the headline result?\n"
        "- Does stress slippage destroy the edge?\n"
        "- Does A-only outperform A/B or full tournament after risk adjustment?\n"
        "- Should C/D/E be removed, shadow-tested, or redesigned?\n"
        "- Are R-multiples distorted by tiny actual-risk trades?\n"
        "- Do BIL/SHY distort results?\n"
        "- Which variant, if any, deserves a 30- to 90-day paper-forward test?\n",
        encoding="utf-8",
    )

    output_files = sorted(str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file())
    evidence_files = sorted(str(p.relative_to(evidence_dir)) for p in evidence_dir.rglob("*") if p.is_file())
    repo_path = run_dir.parents[2]
    manifest = {
        "run_id": run_id,
        "run_timestamp_utc": metadata.get("run_timestamp_utc"),
        "repo_path": str(repo_path),
        "code_git_commit_if_available": metadata.get("git_commit_hash"),
        "dirty_git_tree_if_available": _git_dirty_status(repo_path),
        "config_hash": metadata.get("config_hash"),
        "python_version": metadata.get("python_version"),
        "platform": metadata.get("platform"),
        "package_versions": metadata.get("package_versions"),
        "data_start": metadata.get("full_backtest_start"),
        "data_end": metadata.get("full_backtest_end"),
        "effective_trading_start": result.metadata.get("effective_first_trading_date"),
        "effective_trading_end": result.metadata.get("effective_last_trading_date"),
        "project_stop_mode": headline["project_stop_mode"],
        "rolling_validation": config.get("rolling_validation", {}),
        "validation_mode_used": headline["validation_mode"],
        "rolling_method": headline["rolling_method"],
        "mark_as_final": headline["mark_as_final"],
        "sampled_results_are_final": headline["sampled_results_are_final"],
        "final_validation_completed": headline["final_validation_completed"],
        "rolling_validation_status": rolling_status,
        "standard_slippage": config["execution"]["standard_slippage_pct_per_side"],
        "stress_slippage": config["execution"]["stress_slippage_pct_per_side"],
        "enabled_strategies_main_run": [s for s in MAIN_STRATEGIES if config["strategies"][s].get("enabled", False)],
        "output_files": output_files,
        "evidence_files": evidence_files,
        "row_counts": _artifact_counts(evidence_dir),
        "headline_metric_sources": {
            "single_source_of_truth": "headline_metrics.json",
            "derived_from": ["strategy_metrics.csv", "target_timing.csv", "strategy_variant_results.csv", "benchmark_equity_curve.csv"],
        },
        "evidence_consistency_passed": consistency["passed"],
        "consistency_errors": consistency["errors"],
        "notes": "Paper/demo research only. No broker integration, no real orders, no real-money recommendation.",
    }
    write_json(evidence_dir / "evidence_manifest.json", manifest)
    consistency = consistency_check(evidence_dir, run_dir, headline)
    write_json(evidence_dir / "consistency_check.json", consistency)
    manifest["evidence_consistency_passed"] = consistency["passed"]
    manifest["consistency_errors"] = consistency["errors"]
    manifest["row_counts"] = _artifact_counts(evidence_dir)
    manifest["evidence_files"] = sorted(str(p.relative_to(evidence_dir)) for p in evidence_dir.rglob("*") if p.is_file())
    write_json(evidence_dir / "evidence_manifest.json", manifest)

    zip_path = evidence_dir / "evidence_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in evidence_dir.rglob("*"):
            if path.is_file() and path != zip_path:
                zf.write(path, path.relative_to(evidence_dir))
    refresh_latest(evidence_dir, evidence_root / "latest")
    return evidence_dir, headline, consistency
