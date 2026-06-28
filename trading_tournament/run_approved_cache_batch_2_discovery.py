from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_parallel_discovery_approved_cache_batch as base
import run_qvm_risk_adjusted_top2_promotion_review as review_tools


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = base.REGISTRY_PATH
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "approved_cache_batch_2" / "latest"
BATCH_ID = "approved_cache_batch_2_risk_controlled_growth_defensive"
DATA_HISTORY_MODE = base.DATA_HISTORY_MODE
FORBIDDEN_SYMBOLS = {"DBC"}
NEXT_ACTIONS = {
    "promotion": "create_promotion_review_for_best_approved_cache_batch_2_candidate",
    "diversifier": "review_best_diversifier_watchlist_candidate_or_continue_discovery",
    "none": "continue_next_approved_family_discovery_batch",
    "data_issue": "repair_approved_cache_batch_2_data_issue",
}
BENCHMARK_IDS = [base.VM_ID, base.DSR_ID, base.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]


def specs() -> list[dict[str, Any]]:
    return [
        {"strategy_id": "gdb_growth_defensive_barbell_60_40_v1", "family_group": "growth_defensive_barbell", "symbols": ["SPY", "QQQ", "MTUM", "QUAL", "GLD", "IEF", "TLT", "BIL"], "rule": "growth_defensive_barbell", "growth_weight": 0.60},
        {"strategy_id": "gdb_growth_defensive_barbell_70_30_v1", "family_group": "growth_defensive_barbell", "symbols": ["SPY", "QQQ", "MTUM", "QUAL", "GLD", "IEF", "TLT", "BIL"], "rule": "growth_defensive_barbell", "growth_weight": 0.70},
        {"strategy_id": "gdb_qmtum_gold_bond_cash_v1", "family_group": "growth_defensive_barbell", "symbols": ["SPY", "QQQ", "MTUM", "QUAL", "GLD", "IEF", "TLT", "BIL"], "rule": "qmtum_gold_bond_cash"},
        {"strategy_id": "matr_multi_asset_top3_with_cash_floor_v1", "family_group": "multi_asset_trend_risk_control", "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG", "BIL"], "rule": "top3_cash_floor"},
        {"strategy_id": "matr_multi_asset_top2_defensive_fallback_v1", "family_group": "multi_asset_trend_risk_control", "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG", "BIL"], "rule": "risk_top2_defensive_fallback"},
        {"strategy_id": "matr_global_assets_absolute_momentum_cash_v1", "family_group": "multi_asset_trend_risk_control", "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG", "BIL"], "rule": "absolute_momentum_cash"},
        {"strategy_id": "qldg_quality_lowvol_growth_50_30_20_v1", "family_group": "quality_lowvol_defensive_growth", "symbols": ["QQQ", "MTUM", "QUAL", "SPLV", "USMV", "VTV", "SPY", "BIL"], "rule": "quality_lowvol_growth_50_30_20"},
        {"strategy_id": "qldg_quality_lowvol_growth_equal_risk_proxy_v1", "family_group": "quality_lowvol_defensive_growth", "symbols": ["QQQ", "MTUM", "QUAL", "SPLV", "USMV", "VTV", "BIL"], "rule": "equal_risk_proxy_30_30_20"},
        {"strategy_id": "benchmark_spy_qqq_gold_bond_equal_weight_v1", "family_group": "benchmark_sanity_rows", "symbols": ["SPY", "QQQ", "GLD", "IEF", "BIL"], "rule": "benchmark_spy_qqq_gold_bond"},
        {"strategy_id": "benchmark_quality_lowvol_equal_weight_v1", "family_group": "benchmark_sanity_rows", "symbols": ["QUAL", "SPLV", "USMV", "VTV", "BIL"], "rule": "benchmark_quality_lowvol"},
    ]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def fmt(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def required_symbols() -> list[str]:
    symbols = {"SPY", "QQQ", "BIL", "SPLV", "USMV", "QUAL", "VTV", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"}
    for spec in specs():
        symbols.update(spec["symbols"])
    return sorted(symbols)


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches = base.state_mismatches(root, registry)
    rows = rows_by_id(registry)
    expected = {
        "qvm_quality_value_momentum_risk_adjusted_top2_v1": "mark_too_risky",
        "qvm_quality_value_momentum_top2_v1": "mark_duplicate_or_near_duplicate",
        "lvq_lowvol_quality_spy_regime_v1": "keep_watchlist",
    }
    for sid, status in expected.items():
        row = rows.get(sid, {})
        if row.get("promotion_decision") != status and row.get("status") != status:
            mismatches.append(f"{sid} is not exhausted as {status}")
    return mismatches


def validate_spec_symbols(spec: dict[str, Any], approved: set[str]) -> None:
    symbols = set(spec.get("symbols", []))
    forbidden = sorted((symbols - approved) | (symbols & FORBIDDEN_SYMBOLS))
    if forbidden:
        raise ValueError(f"{spec.get('strategy_id')} uses forbidden or unapproved symbols: {','.join(forbidden)}")


def prepare_prices(root: Path) -> tuple[pd.DataFrame, list[str], list[dict[str, Any]]]:
    close_map: dict[str, pd.Series] = {}
    missing: list[str] = []
    cache_rows = [base.qa_cache(root, symbol) for symbol in required_symbols()]
    for row in cache_rows:
        series = base.read_close(root, row["symbol"])
        if series is None:
            missing.append(row["symbol"])
        else:
            close_map[row["symbol"]] = series
    if missing:
        return pd.DataFrame(), missing, cache_rows
    return pd.concat(close_map.values(), axis=1, join="outer", sort=True).sort_index(), [], cache_rows


def add(weights: dict[str, float], symbol: str, amount: float) -> None:
    if amount > 1e-12:
        weights[symbol] = weights.get(symbol, 0.0) + amount


def score(close: pd.DataFrame, symbol: str, t: int) -> float:
    r = base.ret126(close, symbol, t)
    v = base.vol60(close, symbol, t)
    return r / v if np.isfinite(r) and np.isfinite(v) and v > 0 else float("nan")


def ranked(close: pd.DataFrame, symbols: list[str], t: int, positive_return: bool = False) -> list[str]:
    scored: list[tuple[str, float]] = []
    for symbol in symbols:
        if not base.eligible(close, symbol, t):
            continue
        r = base.ret126(close, symbol, t)
        if positive_return and (not np.isfinite(r) or r <= 0):
            continue
        s = score(close, symbol, t)
        if np.isfinite(s):
            scored.append((symbol, s))
    return [symbol for symbol, _ in sorted(scored, key=lambda item: item[1], reverse=True)]


def best(close: pd.DataFrame, symbols: list[str], t: int, require_eligible: bool = True) -> str:
    pool = ranked(close, symbols, t) if require_eligible else [s for s in symbols if np.isfinite(score(close, s, t))]
    return pool[0] if pool else "BIL"


def strategy_weights(close: pd.DataFrame, strategy_id: str, t: int, specs_by_id: dict[str, dict[str, Any]]) -> dict[str, float]:
    if strategy_id not in specs_by_id:
        return base.strategy_weights(close, strategy_id, t, base_specs_for_benchmarks())
    spec = specs_by_id[strategy_id]
    rule = spec["rule"]
    weights: dict[str, float] = {}
    if rule == "growth_defensive_barbell":
        gw = float(spec["growth_weight"])
        growth = ranked(close, ["SPY", "QQQ", "MTUM", "QUAL"], t)[:2]
        if growth:
            for symbol in growth:
                add(weights, symbol, gw / len(growth))
        else:
            add(weights, "BIL", gw)
        add(weights, best(close, ["GLD", "IEF", "TLT", "BIL"], t, require_eligible=False), 1.0 - gw)
    elif rule == "qmtum_gold_bond_cash":
        if base.eligible(close, "SPY", t) and base.eligible(close, "QQQ", t):
            add(weights, "QQQ", 0.40)
            add(weights, "MTUM", 0.20)
            add(weights, "QUAL", 0.20)
            add(weights, best(close, ["GLD", "IEF"], t, require_eligible=False), 0.20)
        else:
            add(weights, "GLD", 0.40)
            add(weights, best(close, ["IEF", "TLT"], t, require_eligible=False), 0.40)
            add(weights, "BIL", 0.20)
    elif rule == "top3_cash_floor":
        picks = ranked(close, ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG"], t)[:3]
        for symbol in picks:
            add(weights, symbol, 0.75 / 3.0)
        add(weights, "BIL", 0.25 + 0.75 * (3 - len(picks)) / 3.0)
    elif rule == "risk_top2_defensive_fallback":
        if base.eligible(close, "SPY", t):
            risk = ranked(close, ["SPY", "QQQ", "IWM", "EFA", "EEM"], t)[:2]
            for symbol in risk:
                add(weights, symbol, 0.70 / max(2, len(risk)))
            if len(risk) < 2:
                add(weights, "BIL", 0.70 * (2 - len(risk)) / 2.0)
            add(weights, best(close, ["GLD", "IEF", "TLT", "AGG", "BIL"], t, require_eligible=False), 0.30)
        else:
            defensives = ranked(close, ["GLD", "IEF", "TLT", "AGG"], t)[:2]
            if defensives:
                for symbol in defensives:
                    add(weights, symbol, 1.0 / len(defensives))
            else:
                add(weights, "BIL", 1.0)
    elif rule == "absolute_momentum_cash":
        picks = ranked(close, ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG"], t, positive_return=True)[:3]
        for symbol in picks:
            add(weights, symbol, 1.0 / 3.0)
        add(weights, "BIL", (3 - len(picks)) / 3.0)
    elif rule == "quality_lowvol_growth_50_30_20":
        if base.eligible(close, "SPY", t):
            add(weights, best(close, ["QQQ", "MTUM", "QUAL"], t), 0.50)
            add(weights, best(close, ["SPLV", "USMV", "VTV"], t), 0.30)
            add(weights, "BIL", 0.20)
        else:
            defensive = ranked(close, ["SPLV", "USMV", "VTV"], t)[:1]
            if defensive:
                add(weights, defensive[0], 0.50)
            else:
                add(weights, "BIL", 0.50)
            add(weights, "BIL", 0.50)
    elif rule == "equal_risk_proxy_30_30_20":
        picks = ranked(close, ["QQQ", "MTUM", "QUAL", "SPLV", "USMV", "VTV"], t)[:3]
        allocations = [0.30, 0.30, 0.20]
        for symbol, amount in zip(picks, allocations):
            add(weights, symbol, amount)
        add(weights, "BIL", 0.20 + sum(allocations[len(picks) :]))
    elif rule == "benchmark_spy_qqq_gold_bond":
        for symbol in ["SPY", "QQQ", "GLD", "IEF"]:
            add(weights, symbol if base.eligible(close, symbol, t) else "BIL", 0.25)
    elif rule == "benchmark_quality_lowvol":
        for symbol in ["QUAL", "SPLV", "USMV", "VTV"]:
            add(weights, symbol if base.eligible(close, symbol, t) else "BIL", 0.25)
    return weights or {"BIL": 1.0}


def base_specs_for_benchmarks() -> dict[str, dict[str, Any]]:
    return {spec["strategy_id"]: spec for spec in base.candidate_specs()}


def simulate(close: pd.DataFrame, start: int, horizon: int, strategy_id: str, specs_by_id: dict[str, dict[str, Any]], slippage: float = base.SLIPPAGE) -> dict[str, Any]:
    equity = base.STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights: dict[str, float] = {}
    last_month = None
    stop = None
    target300 = None
    target400 = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            new_weights = strategy_weights(close, strategy_id, signal, specs_by_id)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * slippage
            weights = new_weights
            last_month = month
        daily_return = 0.0
        for symbol, weight in weights.items():
            if base.available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - base.STARTING_EQUITY
        if stop is None and profit <= base.STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {"strategy_id": strategy_id, "horizon": horizon, "window_start": str(close.index[start].date()), "window_end": str(close.index[start + horizon].date()), "final_equity": equity, "profit_dollars": equity - base.STARTING_EQUITY, "max_drawdown": max_drawdown, "absolute_600_stop_hit": stop is not None, "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)), "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop))}


def run_windows(close: pd.DataFrame, strategy_id: str, specs_by_id: dict[str, dict[str, Any]], slippage: float = base.SLIPPAGE) -> list[dict[str, Any]]:
    return [simulate(close, start, horizon, strategy_id, specs_by_id, slippage) for horizon in base.HORIZONS for start in base.sample_starts(close, horizon)]


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    return review_tools.summarize(rows, strategy_id, horizon)


def full_returns(close: pd.DataFrame, strategy_id: str, specs_by_id: dict[str, dict[str, Any]]) -> pd.Series:
    equity = base.STARTING_EQUITY
    weights: dict[str, float] = {}
    last_month = None
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(253, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            weights = strategy_weights(close, strategy_id, signal, specs_by_id)
            last_month = month
        daily_return = 0.0
        for symbol, weight in weights.items():
            if base.available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(close.index[today])
    return pd.Series(values, index=dates).pct_change().dropna()


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def classify(summary: dict[str, Any], stress: dict[str, Any], deltas: dict[str, Any], correlations: dict[str, Any], family: str) -> tuple[str, str]:
    if summary.get("validation_status") == "missing_or_unavailable":
        return "evidence_missing", "diagnostics unavailable"
    if summary["stop_hit_rate"] > 0 or summary["worst_drawdown"] <= base.STOP_DOLLARS or summary["risk_buffer_vs_minus_600"] < 50 or stress["risk_buffer_vs_minus_600"] < 25:
        return "too_risky", "drawdown/risk buffer too close to -600"
    duplicate_like = any(isinstance(correlations.get(k), float) and correlations[k] >= 0.88 for k in ["corr_vs_active_vm", "corr_vs_active_dsr", "corr_vs_spy_200d"])
    if duplicate_like:
        return "duplicate_or_near_duplicate", "high correlation with active/control benchmark"
    if family == "benchmark_sanity_rows":
        return "benchmark_watchlist", "benchmark/sanity row"
    weak_benchmark = any(isinstance(deltas.get(k), float) and deltas[k] < -75 for k in ["delta_vs_spy_200d", "delta_vs_spy_buy_hold", "delta_vs_bil"])
    useful = summary["median_final_equity"] >= 3350 and summary["target_300_before_stop_rate"] >= 0.4 and summary["target_400_before_stop_rate"] >= 0.25
    if useful and not weak_benchmark:
        return "promotion_review_candidate", "useful target profile, acceptable risk buffer, not near-duplicate"
    if summary["target_300_before_stop_rate"] < 0.2 or summary["median_final_equity"] < 3150:
        return "too_slow_for_profit_goal", "target/profit profile too weak"
    if not weak_benchmark and max([v for v in correlations.values() if isinstance(v, float)] or [1.0]) < 0.80:
        return "diversifier_watchlist_candidate", "different profile but not promotion-strong"
    return "needs_benchmark_delta_review", "weaker than key benchmarks or active references"


def build_payload(root: Path) -> dict[str, Any]:
    approved = base.approved_strategy_symbols(root)
    for spec in specs():
        validate_spec_symbols(spec, approved)
    close, missing, cache_rows = prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "cache_rows": cache_rows, "rows": [], "family_rows": [], "benchmark_rows": [], "decision_rows": [], "next_action": NEXT_ACTIONS["data_issue"], "best_row": ""}
    specs_by_id = {spec["strategy_id"]: spec for spec in specs()}
    ids = [spec["strategy_id"] for spec in specs()] + BENCHMARK_IDS
    windows = {sid: run_windows(close, sid, specs_by_id) for sid in ids}
    stress_windows = {sid: run_windows(close, sid, specs_by_id, review_tools.STRESS_SLIPPAGE) for sid in [spec["strategy_id"] for spec in specs()]}
    summaries = {sid: {h: summarize(windows[sid], sid, h) for h in base.HORIZONS} for sid in ids}
    stress_summaries = {sid: {h: summarize(stress_windows[sid], sid, h) for h in base.HORIZONS} for sid in stress_windows}
    returns = {sid: full_returns(close, sid, specs_by_id) for sid in ids}
    result_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for spec in specs():
        sid = spec["strategy_id"]
        s90 = summaries[sid][90]
        s180 = summaries[sid][180]
        stress180 = stress_summaries[sid][180]
        deltas = {
            "delta_vs_active_vm": s180["median_final_equity"] - summaries[base.VM_ID][180]["median_final_equity"],
            "delta_vs_active_dsr": s180["median_final_equity"] - summaries[base.DSR_ID][180]["median_final_equity"],
            "delta_vs_active_combo": "unavailable",
            "delta_vs_spy_200d": s180["median_final_equity"] - summaries[base.SPY_200D_ID][180]["median_final_equity"],
            "delta_vs_spy_buy_hold": s180["median_final_equity"] - summaries["SPY_buy_hold"][180]["median_final_equity"],
            "delta_vs_qqq_buy_hold": s180["median_final_equity"] - summaries["QQQ_buy_hold"][180]["median_final_equity"],
            "delta_vs_bil": s180["median_final_equity"] - summaries["BIL_cash_proxy"][180]["median_final_equity"],
        }
        correlations = {"corr_vs_active_vm": corr(returns, sid, base.VM_ID), "corr_vs_active_dsr": corr(returns, sid, base.DSR_ID), "corr_vs_spy_200d": corr(returns, sid, base.SPY_200D_ID)}
        verdict, reason = classify(s180, stress180, deltas, correlations, spec["family_group"])
        row = {"strategy_id": sid, "family_group": spec["family_group"], "rule": spec["rule"], "symbols": ";".join(spec["symbols"]), "data_history_mode": DATA_HISTORY_MODE, "90d_median_final_equity": fmt(s90["median_final_equity"]), "180d_median_final_equity": fmt(s180["median_final_equity"]), "180d_mean_final_equity": fmt(s180["mean_final_equity"]), "180d_p75_final_equity": fmt(s180["p75_final_equity"]), "180d_p90_final_equity": fmt(s180["p90_final_equity"]), "best_final_equity": fmt(s180["best_final_equity"]), "worst_final_equity": fmt(s180["worst_final_equity"]), "target_300_before_stop_rate": fmt(s180["target_300_before_stop_rate"]), "target_400_before_stop_rate": fmt(s180["target_400_before_stop_rate"]), "180d_worst_drawdown": fmt(s180["worst_drawdown"]), "stop_hit_rate": fmt(s180["stop_hit_rate"]), "risk_buffer_vs_minus_600": fmt(s180["risk_buffer_vs_minus_600"]), "stress_180d_worst_drawdown": fmt(stress180["worst_drawdown"]), "stress_risk_buffer_vs_minus_600": fmt(stress180["risk_buffer_vs_minus_600"]), **{k: fmt(v) for k, v in correlations.items()}, **{k: fmt(v) for k, v in deltas.items()}, "decision": verdict, "decision_reason": reason, "candidate_exhaustive_run": False, "paper_forward_active": False, "real_money_recommendation": False}
        result_rows.append(row)
        decision_rows.append({"strategy_id": sid, "family_group": spec["family_group"], "decision": verdict, "decision_reason": reason, "next_allowed_step": "promotion_review_only" if verdict == "promotion_review_candidate" else "research_sample_review_or_archive"})
        for bench in BENCHMARK_IDS:
            benchmark_rows.append({"strategy_id": sid, "benchmark_id": bench, "strategy_180d_median_final_equity": fmt(s180["median_final_equity"]), "benchmark_180d_median_final_equity": fmt(summaries[bench][180]["median_final_equity"]), "delta": fmt(s180["median_final_equity"] - summaries[bench][180]["median_final_equity"]), "correlation": fmt(corr(returns, sid, bench)), "comparison_status": "computed"})
        benchmark_rows.append({"strategy_id": sid, "benchmark_id": "active_combo", "strategy_180d_median_final_equity": fmt(s180["median_final_equity"]), "benchmark_180d_median_final_equity": "", "delta": "unavailable", "correlation": "unavailable", "comparison_status": "unavailable"})
    family_rows = []
    frame = pd.DataFrame(result_rows)
    for family, family_frame in frame.groupby("family_group"):
        best_row = family_frame.sort_values("180d_median_final_equity", ascending=False).iloc[0]
        family_rows.append({"family_group": family, "row_count": int(len(family_frame)), "best_strategy_id": best_row["strategy_id"], "best_180d_median_final_equity": best_row["180d_median_final_equity"], "promotion_candidates": int((family_frame["decision"] == "promotion_review_candidate").sum()), "watchlist_candidates": int(family_frame["decision"].astype(str).str.contains("watchlist").sum())})
    promotions = [row for row in result_rows if row["decision"] == "promotion_review_candidate"]
    diversifiers = [row for row in result_rows if row["decision"] == "diversifier_watchlist_candidate"]
    next_action = NEXT_ACTIONS["promotion"] if promotions else NEXT_ACTIONS["diversifier"] if diversifiers else NEXT_ACTIONS["none"]
    best_result = max(result_rows, key=lambda row: float(row["180d_median_final_equity"])) if result_rows else {}
    return {"diagnostics_available": True, "missing_symbols": [], "cache_rows": cache_rows, "rows": result_rows, "family_rows": family_rows, "benchmark_rows": benchmark_rows, "decision_rows": decision_rows, "next_action": next_action, "best_row": best_result.get("strategy_id", "")}


def registry_row(spec: dict[str, Any], result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    verdict = result["decision"]
    return {"id": spec["strategy_id"], "display_name": spec["strategy_id"].replace("_", " ").title(), "lane": "profit_exploration", "instrument_family": "ETF", "strategy_family": spec["family_group"], "version": "v1", "parent_id": "", "credibility_tier": "tier2_exploratory", "status": verdict, "role": "approved_cache_batch_2_discovery_row", "rules_frozen": True, "paper_forward_active": False, "implementation_status": "implemented_research_sample", "data_source": "existing_adjusted_etf_cache", "evidence_source": "approved_cache_batch_2_discovery", "latest_evidence_path": str(output_dir), "latest_known_result_summary": f"Approved-cache batch 2 verdict: {verdict}; 180d median equity {result['180d_median_final_equity']}.", "allowed_next_action": "create_promotion_review_for_best_approved_cache_batch_2_candidate" if verdict == "promotion_review_candidate" else "research_sample_review", "forbidden_next_actions": ["run_candidate_exhaustive", "paper_forward_activation", "paper_forward_checkpoint", "paper_forward_review", "promote_to_real_money", "add_broker_integration", "live_orders", "order_placement", "place_live_orders", "download_data", "tune_parameters"], "risk_framework_status": "research_sample_only", "paper_forward_allowed_by_risk_framework": False, "real_money_recommendation": False, "promotion_blockers": "research_sample_only;not_candidate_exhaustive;not_paper_forward_allowed", "promotion_requirements": "Separate promotion review only; no candidate_exhaustive from discovery batch.", "demotion_or_kill_criteria": "Weak target profile, unacceptable drawdown, duplicate exposure, or benchmark lag.", "notes": "Fixed-rule approved-cache batch 2 discovery row; no broker/live-order/real-money path.", "strategy_id": spec["strategy_id"], "family": spec["family_group"], "instrument_lane": "ETF", "evidence_tier": "research_sample", "current_status": verdict, "allowed_next_actions": ["create_promotion_review_for_best_approved_cache_batch_2_candidate"] if verdict == "promotion_review_candidate" else ["research_sample_review"], "candidate_exhaustive_run": False, "candidate_exhaustive_recommended": False, "promotion_review_required": verdict == "promotion_review_candidate", "promotion_decision": verdict, "promotion_reason": result["decision_reason"], "primary_failure_mode": "not_flagged" if verdict == "promotion_review_candidate" else verdict, "duplication_risk": "flagged" if "duplicate" in verdict else "not_flagged", "risk_budget_status": "research_sample_screened", "evidence_needed": "promotion review only if selected; no paper-forward action", "duplicate_of": "", "blocked_reason": ""}


def update_registry(root: Path, payload: dict[str, Any]) -> None:
    registry = load_yaml(root / REGISTRY_PATH)
    result_by_id = {row["strategy_id"]: row for row in payload["rows"]}
    spec_by_id = {spec["strategy_id"]: spec for spec in specs()}
    registry["strategies"] = [row for row in registry.get("strategies", []) if row.get("id") not in spec_by_id] + [registry_row(spec_by_id[sid], result_by_id[sid], root / OUTPUT_DIR) for sid in spec_by_id if sid in result_by_id]
    (root / REGISTRY_PATH).write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def create_packet(directory: Path) -> Path:
    packet = directory / "approved_cache_batch_2_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


RESULT_FIELDS = ["strategy_id", "family_group", "rule", "symbols", "data_history_mode", "90d_median_final_equity", "180d_median_final_equity", "180d_mean_final_equity", "180d_p75_final_equity", "180d_p90_final_equity", "best_final_equity", "worst_final_equity", "target_300_before_stop_rate", "target_400_before_stop_rate", "180d_worst_drawdown", "stop_hit_rate", "risk_buffer_vs_minus_600", "stress_180d_worst_drawdown", "stress_risk_buffer_vs_minus_600", "corr_vs_active_vm", "corr_vs_active_dsr", "corr_vs_spy_200d", "delta_vs_active_vm", "delta_vs_active_dsr", "delta_vs_active_combo", "delta_vs_spy_200d", "delta_vs_spy_buy_hold", "delta_vs_qqq_buy_hold", "delta_vs_bil", "decision", "decision_reason", "candidate_exhaustive_run", "paper_forward_active", "real_money_recommendation"]


def write_outputs(root: Path, payload: dict[str, Any], consistency: dict[str, Any]) -> dict[str, str]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "approved_cache_batch_2_results.csv", payload["rows"], RESULT_FIELDS)
    write_csv(output / "approved_cache_batch_2_family_summary.csv", payload["family_rows"], ["family_group", "row_count", "best_strategy_id", "best_180d_median_final_equity", "promotion_candidates", "watchlist_candidates"])
    write_csv(output / "approved_cache_batch_2_benchmark_delta.csv", payload["benchmark_rows"], ["strategy_id", "benchmark_id", "strategy_180d_median_final_equity", "benchmark_180d_median_final_equity", "delta", "correlation", "comparison_status"])
    write_csv(output / "approved_cache_batch_2_decision_log.csv", payload["decision_rows"], ["strategy_id", "family_group", "decision", "decision_reason", "next_allowed_step"])
    write_csv(output / "approved_cache_batch_2_watchlist.csv", [r for r in payload["rows"] if "watchlist" in r["decision"]], RESULT_FIELDS)
    write_csv(output / "approved_cache_batch_2_promotion_candidates.csv", [r for r in payload["rows"] if r["decision"] == "promotion_review_candidate"], RESULT_FIELDS)
    write_csv(output / "approved_cache_batch_2_rejects.csv", [r for r in payload["rows"] if r["decision"] in {"reject", "too_risky", "mark_too_risky", "too_slow_for_profit_goal", "duplicate_or_near_duplicate", "evidence_missing", "needs_benchmark_delta_review"}], RESULT_FIELDS)
    (output / "approved_cache_batch_2_next_action.md").write_text(f"# Next Action\n\n`{payload['next_action']}`\n\nDo not run candidate_exhaustive or any paper-forward/broker/real-money workflow directly from this discovery batch.\n", encoding="utf-8")
    summary = ["# Approved Cache Batch 2", "", f"Created at UTC: {now_utc()}", f"Batch: `{BATCH_ID}`", f"Rows tested: {len(payload['rows'])}", f"Best row overall: `{payload['best_row']}`", f"Promotion candidates: {sum(1 for r in payload['rows'] if r['decision'] == 'promotion_review_candidate')}", f"Diversifier watchlist candidates: {sum(1 for r in payload['rows'] if r['decision'] == 'diversifier_watchlist_candidate')}", f"Next action: `{payload['next_action']}`", "", "Discovery only; no candidate validation, paper-forward action, broker/live-order, provider download, or real-money recommendation."]
    (output / "approved_cache_batch_2_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest = {"created_at_utc": now_utc(), "batch_id": BATCH_ID, "families_tested": sorted({spec["family_group"] for spec in specs()}), "rows_tested": [spec["strategy_id"] for spec in specs()], "best_row": payload["best_row"], "next_action": payload["next_action"], "diagnostics_available": payload["diagnostics_available"], "missing_symbols": payload["missing_symbols"], "candidate_exhaustive_run": False, "paper_forward_review": False, "paper_forward_activation": False, "paper_forward_checkpoint": False, "provider_api_called": False, "data_downloaded": False, "broker_integration": False, "live_orders": False, "order_placement": False, "real_money_recommendation": False, "data_history_mode": DATA_HISTORY_MODE}
    write_json(output / "approved_cache_batch_2_manifest.json", manifest)
    write_json(output / "approved_cache_batch_2_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet)}


def run_batch_2(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    mismatches = state_mismatches(root, registry)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    payload = build_payload(root)
    update_registry(root, payload)
    consistency = {"approved_symbols_only": True, "forbidden_symbols_rejected": True, "fixed_rules_predefined": True, "parallel_discovery_completed": True, "cache_used": payload["diagnostics_available"] and not payload["missing_symbols"], "no_candidate_exhaustive_run": True, "no_paper_forward_review": True, "no_paper_forward_activation": True, "no_paper_forward_checkpoint": True, "no_active_observation_mutation": True, "no_broker_path_added": True, "no_live_order_path_added": True, "no_real_money_recommendation": True, "benchmark_unavailable_not_zero_filled": any(r["benchmark_id"] == "active_combo" and r["delta"] == "unavailable" for r in payload["benchmark_rows"]), "risk_buffer_gate_applied": all(r["decision"] != "promotion_review_candidate" or float(r["risk_buffer_vs_minus_600"]) >= 50 for r in payload["rows"]), "next_action_explicit": bool(payload["next_action"])}
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, payload, consistency)
    return {"output_dir": outputs["output_dir"], "packet": outputs["packet"], "best_row": payload["best_row"], "next_action": payload["next_action"], "promotion_candidates": [r["strategy_id"] for r in payload["rows"] if r["decision"] == "promotion_review_candidate"], "diversifier_watchlist_candidates": [r["strategy_id"] for r in payload["rows"] if r["decision"] == "diversifier_watchlist_candidate"], "consistency": consistency}


def main() -> None:
    print(json.dumps(run_batch_2(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
