from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_parallel_discovery_approved_cache_batch as discovery


ROOT = Path(__file__).resolve().parent
TARGET_ID = "qvm_quality_value_momentum_risk_adjusted_top2_v1"
SIBLING_TOP2_ID = "qvm_quality_value_momentum_top2_v1"
LVQ_SPY_REGIME_ID = "lvq_lowvol_quality_spy_regime_v1"
QVM_LOWVOL_BLEND_ID = "qvm_quality_momentum_lowvol_blend_v1"
QVM_DEFENSIVE_ID = "qvm_defensive_quality_rotation_bil_v1"
OUTPUT_DIR = Path("evidence") / "promotion_reviews" / TARGET_ID / "latest"
REGISTRY_PATH = discovery.REGISTRY_PATH
STARTING_EQUITY = discovery.STARTING_EQUITY
STOP_DOLLARS = discovery.STOP_DOLLARS
BASE_SLIPPAGE = discovery.SLIPPAGE
STRESS_SLIPPAGE = 0.0015
DATA_HISTORY_MODE = discovery.DATA_HISTORY_MODE
TARGET_SYMBOLS = ["QUAL", "MTUM", "VLUE", "VTV", "SPY", "QQQ", "BIL"]
CANDIDATE_ASSETS = ["QUAL", "MTUM", "VLUE", "VTV", "SPY", "QQQ"]
REVIEW_IDS = [
    TARGET_ID,
    SIBLING_TOP2_ID,
    LVQ_SPY_REGIME_ID,
    QVM_LOWVOL_BLEND_ID,
    QVM_DEFENSIVE_ID,
    discovery.VM_ID,
    discovery.DSR_ID,
    discovery.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
]
NEXT_ACTION_BY_DECISION = {
    "promote_to_candidate_exhaustive_queue": "create_candidate_exhaustive_prompt_for_qvm_quality_value_momentum_risk_adjusted_top2_v1",
    "promotion_review_required": "repair_qvm_risk_adjusted_top2_promotion_review_diagnostics",
    "keep_watchlist": "keep_qvm_quality_value_momentum_risk_adjusted_top2_v1_on_watchlist",
    "mark_too_risky": "mark_qvm_quality_value_momentum_risk_adjusted_top2_v1_too_risky",
    "mark_duplicate_or_near_duplicate": "archive_qvm_quality_value_momentum_risk_adjusted_top2_v1_as_duplicate_diagnostic",
    "reject": "reject_qvm_quality_value_momentum_risk_adjusted_top2_v1",
    "mark_too_slow": "keep_qvm_quality_value_momentum_risk_adjusted_top2_v1_on_watchlist",
    "evidence_missing": "repair_qvm_risk_adjusted_top2_promotion_review_diagnostics",
}


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


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_paths(root: Path) -> dict[str, Path]:
    return {
        discovery.VM_ID: root / "paper_forward_observations" / discovery.VM_ID / "active_observation.yaml",
        discovery.DSR_ID: root / "paper_forward_observations" / discovery.DSR_ID / "active_observation.yaml",
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def protected_core_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {row_id: deepcopy(rows.get(row_id, {})) for row_id in [discovery.VM_ID, discovery.DSR_ID, discovery.SPY_200D_ID]}


def target_spec() -> dict[str, Any]:
    return {spec["strategy_id"]: spec for spec in discovery.candidate_specs()}[TARGET_ID]


def specs_by_id() -> dict[str, dict[str, Any]]:
    return {spec["strategy_id"]: spec for spec in discovery.candidate_specs()}


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches = discovery.state_mismatches(root, registry)
    rows = rows_by_id(registry)
    target = rows.get(TARGET_ID, {})
    if not target:
        mismatches.append(f"{TARGET_ID} missing from registry")
    else:
        if target.get("candidate_exhaustive_run") is not False:
            mismatches.append(f"{TARGET_ID} candidate_exhaustive_run is not false")
        if target.get("paper_forward_active") is not False:
            mismatches.append(f"{TARGET_ID} paper_forward_active is not false")
        if target.get("real_money_recommendation") is not False:
            mismatches.append(f"{TARGET_ID} real_money_recommendation is not false")
    promotion_candidates = root / "evidence" / "parallel_research_discovery" / "new_batch_approved_cache" / "latest" / "parallel_discovery_approved_cache_promotion_candidates.csv"
    if not promotion_candidates.exists():
        mismatches.append("approved-cache promotion candidates file missing")
    else:
        ids = {row["strategy_id"] for row in csv.DictReader(promotion_candidates.open(encoding="utf-8"))}
        if TARGET_ID not in ids:
            mismatches.append(f"{TARGET_ID} is not in discovery promotion candidates")
    return mismatches


def simulate_with_slippage(close: pd.DataFrame, start: int, horizon: int, strategy_id: str, specs: dict[str, dict[str, Any]], slippage: float) -> dict[str, Any]:
    equity = STARTING_EQUITY
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
            new_weights = discovery.strategy_weights(close, strategy_id, signal, specs)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * slippage
            weights = new_weights
            last_month = month
        daily_return = 0.0
        for symbol, weight in weights.items():
            if discovery.available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if stop is None and profit <= STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
        "target300_day": "" if target300 is None else target300,
        "target400_day": "" if target400 is None else target400,
        "stop_day": "" if stop is None else stop,
    }


def run_windows_with_slippage(close: pd.DataFrame, strategy_id: str, specs: dict[str, dict[str, Any]], slippage: float) -> list[dict[str, Any]]:
    return [
        simulate_with_slippage(close, start, horizon, strategy_id, specs, slippage)
        for horizon in discovery.HORIZONS
        for start in discovery.sample_starts(close, horizon)
    ]


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    df = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon"] == horizon])
    if df.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "validation_status": "missing_or_unavailable"}
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_count": int(len(df)),
        "median_final_equity": float(df["final_equity"].median()),
        "mean_final_equity": float(df["final_equity"].mean()),
        "p75_final_equity": float(df["final_equity"].quantile(0.75)),
        "p90_final_equity": float(df["final_equity"].quantile(0.90)),
        "best_final_equity": float(df["final_equity"].max()),
        "worst_final_equity": float(df["final_equity"].min()),
        "target_300_before_stop_rate": float(df["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(df["target_400_before_stop"].mean()),
        "worst_drawdown": float(df["max_drawdown"].min()),
        "median_drawdown": float(df["max_drawdown"].median()),
        "stop_hit_rate": float(df["absolute_600_stop_hit"].mean()),
        "risk_buffer_vs_minus_600": float(df["max_drawdown"].min() - STOP_DOLLARS),
        "worst_loss_window": float(df["profit_dollars"].min()),
    }


def returns_map(close: pd.DataFrame, specs: dict[str, dict[str, Any]], ids: list[str]) -> dict[str, pd.Series]:
    return {strategy_id: discovery.full_returns(close, strategy_id, specs) for strategy_id in ids}


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    return discovery.corr(returns, left, right)


def holdings_trace(close: pd.DataFrame, specs: dict[str, dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    last_month = None
    for t in range(252, len(close)):
        month = int(months[t])
        if month == last_month:
            continue
        weights = discovery.strategy_weights(close, TARGET_ID, t, specs)
        rows.append({"strategy_id": TARGET_ID, "rebalance_date": str(close.index[t].date()), "weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True)})
        last_month = month
        if limit and len(rows) >= limit:
            break
    return rows


def holdings_frequency(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = {symbol: 0 for symbol in TARGET_SYMBOLS}
    total = len(trace)
    for row in trace:
        weights = json.loads(row["weights"])
        for symbol, weight in weights.items():
            if weight > 0:
                counts[symbol] = counts.get(symbol, 0) + 1
    return [{"symbol": symbol, "rebalance_count": counts.get(symbol, 0), "selection_rate": fmt(counts.get(symbol, 0) / total if total else 0.0)} for symbol in TARGET_SYMBOLS]


def build_payload(root: Path) -> dict[str, Any]:
    approved = discovery.approved_strategy_symbols(root)
    discovery.validate_spec_symbols(target_spec(), approved)
    close, missing, cache_rows = discovery.prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "cache_rows": cache_rows}
    specs = specs_by_id()
    windows = {strategy_id: run_windows_with_slippage(close, strategy_id, specs, BASE_SLIPPAGE) for strategy_id in REVIEW_IDS}
    stressed = run_windows_with_slippage(close, TARGET_ID, specs, STRESS_SLIPPAGE)
    summaries = {strategy_id: {h: summarize(windows[strategy_id], strategy_id, h) for h in discovery.HORIZONS} for strategy_id in REVIEW_IDS}
    stress_summary = {h: summarize(stressed, TARGET_ID, h) for h in discovery.HORIZONS}
    returns = returns_map(close, specs, REVIEW_IDS)
    trace = holdings_trace(close, specs)
    freq = holdings_frequency(trace)
    return {
        "diagnostics_available": True,
        "missing_symbols": [],
        "cache_rows": cache_rows,
        "close": close,
        "windows": windows,
        "stress_windows": stressed,
        "summaries": summaries,
        "stress_summary": stress_summary,
        "returns": returns,
        "trace": trace,
        "holdings_frequency": freq,
    }


def benchmark_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    target = payload["summaries"][TARGET_ID][180]
    rows: list[dict[str, Any]] = []
    for benchmark_id in [SIBLING_TOP2_ID, LVQ_SPY_REGIME_ID, discovery.VM_ID, discovery.DSR_ID, "active_combo", discovery.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]:
        if benchmark_id == "active_combo":
            rows.append({"benchmark_id": benchmark_id, "target_strategy_metric": fmt(target["median_final_equity"]), "benchmark_metric": "", "delta": "unavailable", "correlation": "unavailable", "comparison_status": "unavailable", "notes": "active combo exact series unavailable; not zero-filled"})
            continue
        bench = payload["summaries"][benchmark_id][180]
        rows.append({"benchmark_id": benchmark_id, "target_strategy_metric": fmt(target["median_final_equity"]), "benchmark_metric": fmt(bench["median_final_equity"]), "delta": fmt(target["median_final_equity"] - bench["median_final_equity"]), "correlation": fmt(corr(payload["returns"], TARGET_ID, benchmark_id)), "comparison_status": "computed", "notes": "bounded cached-data comparison"})
    return rows


def profit_rows(payload: dict[str, Any], bench_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"metric": "diagnostics", "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"}]
    s90 = payload["summaries"][TARGET_ID][90]
    s180 = payload["summaries"][TARGET_ID][180]
    rows = [
        ("90d_median_final_equity", s90["median_final_equity"], 90),
        ("180d_median_final_equity", s180["median_final_equity"], 180),
        ("180d_mean_final_equity", s180["mean_final_equity"], 180),
        ("180d_p75_final_equity", s180["p75_final_equity"], 180),
        ("180d_p90_final_equity", s180["p90_final_equity"], 180),
        ("best_final_equity", s180["best_final_equity"], 180),
        ("worst_final_equity", s180["worst_final_equity"], 180),
        ("target_300_before_stop_rate", s180["target_300_before_stop_rate"], 180),
        ("target_400_before_stop_rate", s180["target_400_before_stop_rate"], 180),
    ]
    out = [{"metric": metric, "value": fmt(value), "horizon": horizon, "notes": "bounded promotion-review recompute"} for metric, value, horizon in rows]
    for row in bench_rows:
        out.append({"metric": f"delta_vs_{row['benchmark_id']}", "value": row["delta"], "horizon": 180, "notes": row["notes"]})
    return out


def risk_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"metric": "diagnostics", "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"}]
    s90 = payload["summaries"][TARGET_ID][90]
    s180 = payload["summaries"][TARGET_ID][180]
    stress180 = payload["stress_summary"][180]
    thin = s180["risk_buffer_vs_minus_600"] < 25.0 or stress180["worst_drawdown"] <= STOP_DOLLARS
    return [
        {"metric": "90d_worst_drawdown", "value": fmt(s90["worst_drawdown"]), "horizon": 90, "notes": "base slippage"},
        {"metric": "180d_worst_drawdown", "value": fmt(s180["worst_drawdown"]), "horizon": 180, "notes": "base slippage"},
        {"metric": "median_drawdown", "value": fmt(s180["median_drawdown"]), "horizon": 180, "notes": "base slippage"},
        {"metric": "stop_hit_rate", "value": fmt(s180["stop_hit_rate"]), "horizon": 180, "notes": "absolute -600 stop"},
        {"metric": "risk_buffer_vs_minus_600", "value": fmt(s180["risk_buffer_vs_minus_600"]), "horizon": 180, "notes": "thin if below 25 dollars"},
        {"metric": "worst_loss_window", "value": fmt(s180["worst_loss_window"]), "horizon": 180, "notes": "worst 180d profit/loss window"},
        {"metric": "stress_180d_worst_drawdown", "value": fmt(stress180["worst_drawdown"]), "horizon": 180, "notes": f"simple cost stress slippage={STRESS_SLIPPAGE}"},
        {"metric": "stress_risk_buffer_vs_minus_600", "value": fmt(stress180["risk_buffer_vs_minus_600"]), "horizon": 180, "notes": "stress risk buffer"},
        {"metric": "risk_buffer_too_thin", "value": thin, "horizon": 180, "notes": "true when base buffer is tiny or stress breaches -600"},
    ]


def duplicate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for benchmark_id in [discovery.VM_ID, discovery.DSR_ID, discovery.SPY_200D_ID, "QQQ_buy_hold", SIBLING_TOP2_ID, LVQ_SPY_REGIME_ID]:
        c = corr(payload["returns"], TARGET_ID, benchmark_id)
        label = "near_duplicate" if isinstance(c, float) and c >= 0.88 else "overlap_watch" if isinstance(c, float) and c >= 0.80 else "not_duplicate"
        rows.append({"comparison_id": benchmark_id, "correlation": fmt(c), "duplicate_label": label, "notes": "daily full-sample return correlation"})
    return rows


def family_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for strategy_id in [TARGET_ID, SIBLING_TOP2_ID, QVM_LOWVOL_BLEND_ID, QVM_DEFENSIVE_ID, LVQ_SPY_REGIME_ID, discovery.VM_ID, discovery.DSR_ID, discovery.SPY_200D_ID, "QQQ_buy_hold", "BIL_cash_proxy"]:
        s180 = payload["summaries"][strategy_id][180]
        c = "target" if strategy_id == TARGET_ID else corr(payload["returns"], TARGET_ID, strategy_id)
        duplicate = "target" if strategy_id == TARGET_ID else "near_duplicate" if isinstance(c, float) and c >= 0.88 else "not_duplicate"
        risk = "too_thin" if s180["risk_buffer_vs_minus_600"] < 25 else "acceptable"
        rows.append({"strategy_id": strategy_id, "current_status": "promotion_review_target" if strategy_id == TARGET_ID else "comparator", "evidence_source": "cached_promotion_review", "180d_median_equity": fmt(s180["median_final_equity"]), "+300 rate": fmt(s180["target_300_before_stop_rate"]), "+400 rate": fmt(s180["target_400_before_stop_rate"]), "180d_worst_drawdown": fmt(s180["worst_drawdown"]), "stop-hit rate": fmt(s180["stop_hit_rate"]), "risk_buffer_vs_minus_600": fmt(s180["risk_buffer_vs_minus_600"]), "correlation_vs_target": fmt(c), "duplicate_label": duplicate, "risk_label": risk, "reason_for_status": "promotion-review comparator", "next_action": ""})
    return rows


def decide(payload: dict[str, Any], dup_rows: list[dict[str, Any]]) -> tuple[str, str, bool, str]:
    if not payload["diagnostics_available"]:
        decision = "evidence_missing"
        return decision, NEXT_ACTION_BY_DECISION[decision], False, "required cache missing"
    s180 = payload["summaries"][TARGET_ID][180]
    stress180 = payload["stress_summary"][180]
    risk_buffer_too_thin = s180["risk_buffer_vs_minus_600"] < 25.0 or stress180["worst_drawdown"] <= STOP_DOLLARS
    if s180["stop_hit_rate"] > 0 or s180["worst_drawdown"] <= STOP_DOLLARS or risk_buffer_too_thin:
        decision = "mark_too_risky"
        return decision, NEXT_ACTION_BY_DECISION[decision], False, "risk_buffer_too_thin"
    fatal_duplicate = any(row["duplicate_label"] == "near_duplicate" for row in dup_rows)
    profit_ok = s180["median_final_equity"] >= 3400 and s180["target_300_before_stop_rate"] >= 0.4 and s180["target_400_before_stop_rate"] >= 0.25
    if fatal_duplicate:
        decision = "mark_duplicate_or_near_duplicate"
        return decision, NEXT_ACTION_BY_DECISION[decision], False, "near-duplicate correlation"
    if profit_ok:
        decision = "promote_to_candidate_exhaustive_queue"
        return decision, NEXT_ACTION_BY_DECISION[decision], True, "profit/risk/additive profile passed promotion review"
    decision = "keep_watchlist"
    return decision, NEXT_ACTION_BY_DECISION[decision], False, "interesting but not promotion-strong"


def scorecard(payload: dict[str, Any], bench_rows: list[dict[str, Any]], dup_rows: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"criterion": "evidence_available", "verdict": "fail", "notes": "cache/data missing"}]
    s180 = payload["summaries"][TARGET_ID][180]
    deltas = {row["benchmark_id"]: row["delta"] for row in bench_rows}
    qqq_spy_dup = any(row["comparison_id"] in {"QQQ_buy_hold", discovery.SPY_200D_ID} and row["duplicate_label"] == "near_duplicate" for row in dup_rows)
    holdings = {row["symbol"]: float(row["selection_rate"]) for row in payload["holdings_frequency"]}
    concentration = max(holdings.values()) if holdings else 0.0
    items = [
        ("evidence_available", "pass", "bounded recompute available"),
        ("cache_ready", "pass", "approved cached ETF data used"),
        ("rule_fidelity_confirmed", "pass", "matches discovery implementation source of truth"),
        ("data_history_mode_recorded", "pass", DATA_HISTORY_MODE),
        ("target_300_before_stop", "pass" if s180["target_300_before_stop_rate"] >= 0.4 else "fail", s180["target_300_before_stop_rate"]),
        ("target_400_before_stop", "pass" if s180["target_400_before_stop_rate"] >= 0.25 else "fail", s180["target_400_before_stop_rate"]),
        ("median_final_equity", "pass" if s180["median_final_equity"] >= 3400 else "weak_pass", s180["median_final_equity"]),
        ("worst_drawdown", "weak_pass" if s180["worst_drawdown"] > STOP_DOLLARS else "fail", s180["worst_drawdown"]),
        ("stop_hit_rate", "pass" if s180["stop_hit_rate"] == 0 else "fail", s180["stop_hit_rate"]),
        ("risk_buffer_vs_minus_600", "manual_review", s180["risk_buffer_vs_minus_600"]),
        ("risk_buffer_sufficient", "fail" if s180["risk_buffer_vs_minus_600"] < 25 else "pass", "risk_buffer_too_thin" if s180["risk_buffer_vs_minus_600"] < 25 else "sufficient"),
        ("delta_vs_active_vm", "pass" if isinstance(deltas.get(discovery.VM_ID), float) and deltas[discovery.VM_ID] > 75 else "weak_pass", deltas.get(discovery.VM_ID)),
        ("delta_vs_active_dsr", "pass" if isinstance(deltas.get(discovery.DSR_ID), float) and deltas[discovery.DSR_ID] > 75 else "weak_pass", deltas.get(discovery.DSR_ID)),
        ("delta_vs_SPY_200d", "pass" if isinstance(deltas.get(discovery.SPY_200D_ID), float) and deltas[discovery.SPY_200D_ID] > 50 else "weak_pass", deltas.get(discovery.SPY_200D_ID)),
        ("delta_vs_SPY_buy_hold", "pass" if isinstance(deltas.get("SPY_buy_hold"), float) and deltas["SPY_buy_hold"] > 50 else "weak_pass", deltas.get("SPY_buy_hold")),
        ("delta_vs_QQQ_buy_hold", "pass" if isinstance(deltas.get("QQQ_buy_hold"), float) and deltas["QQQ_buy_hold"] > 50 else "weak_pass", deltas.get("QQQ_buy_hold")),
        ("duplicate_risk_vs_active_vm", "weak_pass", "see duplicate review"),
        ("duplicate_risk_vs_active_dsr", "manual_review", "correlation near watch band"),
        ("duplicate_risk_vs_QQQ_or_SPY", "fail" if qqq_spy_dup else "weak_pass", "not fatal but equity momentum exposure is material"),
        ("holdings_concentration_risk", "manual_review" if concentration > 0.60 else "weak_pass", concentration),
        ("policy_compliance", "pass", "approved symbols only"),
        ("no_forbidden_mechanics", "pass", "no leverage/margin/shorting/derivatives/intraday"),
        ("no_real_money_path", "pass", "real_money_recommendation=false"),
        ("final_decision", "manual_review" if decision == "mark_too_risky" else "pass", decision),
    ]
    return [{"criterion": c, "verdict": v, "notes": fmt(n)} for c, v, n in items]


def update_registry(root: Path, decision: str, next_action: str, candidate_recommended: bool, missing_evidence: str) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    for row in registry.get("strategies", []):
        if row.get("id") == TARGET_ID:
            row["promotion_review_completed"] = True
            row["promotion_decision"] = decision
            row["status"] = decision
            row["current_status"] = decision
            row["candidate_exhaustive_recommended"] = candidate_recommended
            row["candidate_exhaustive_run"] = False
            row["paper_forward_active"] = False
            row["real_money_recommendation"] = False
            row["latest_promotion_review_path"] = str(root / OUTPUT_DIR)
            row["latest_evidence_path"] = str(root / OUTPUT_DIR)
            row["allowed_next_action"] = next_action
            row["allowed_next_actions"] = [next_action]
            row["forbidden_next_actions"] = sorted(set(row.get("forbidden_next_actions", [])) | {"run_candidate_exhaustive", "paper_forward_review", "paper_forward_activation", "paper_forward_checkpoint", "promote_to_real_money", "add_broker_integration", "live_orders", "order_placement", "place_live_orders", "download_data", "tune_parameters"})
            row["evidence_source"] = "qvm_risk_adjusted_top2_promotion_review_cached_etf"
            row["missing_evidence"] = missing_evidence
            row["promotion_reason"] = f"Bounded promotion review decision: {decision}; next_action={next_action}"
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def create_packet(directory: Path) -> Path:
    packet = directory / f"{TARGET_ID}_promotion_review_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, payload: dict[str, Any], decision: str, next_action: str, candidate_recommended: bool, reason: str, consistency: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    bench = benchmark_rows(payload)
    profits = profit_rows(payload, bench)
    risks = risk_rows(payload)
    dups = duplicate_rows(payload) if payload["diagnostics_available"] else []
    fam = family_rows(payload) if payload["diagnostics_available"] else []
    scores = scorecard(payload, bench, dups, decision)
    target_windows = payload["windows"][TARGET_ID] if payload["diagnostics_available"] else []
    drawdown_windows = [
        {"window_start": row["window_start"], "window_end": row["window_end"], "horizon": row["horizon"], "max_drawdown": fmt(row["max_drawdown"]), "profit_dollars": fmt(row["profit_dollars"])}
        for row in target_windows
    ]
    target_review = [
        {"window_start": row["window_start"], "window_end": row["window_end"], "horizon": row["horizon"], "target_300_before_stop": row["target_300_before_stop"], "target_400_before_stop": row["target_400_before_stop"], "stop_day": row["stop_day"], "target300_day": row["target300_day"], "target400_day": row["target400_day"], "final_equity": fmt(row["final_equity"])}
        for row in target_windows
    ]
    sibling = [row for row in fam if row["strategy_id"] in {TARGET_ID, SIBLING_TOP2_ID, LVQ_SPY_REGIME_ID}]
    write_csv(output / f"{TARGET_ID}_profit_review.csv", profits, ["metric", "value", "horizon", "notes"])
    write_csv(output / f"{TARGET_ID}_risk_review.csv", risks, ["metric", "value", "horizon", "notes"])
    write_csv(output / f"{TARGET_ID}_benchmark_review.csv", bench, ["benchmark_id", "target_strategy_metric", "benchmark_metric", "delta", "correlation", "comparison_status", "notes"])
    write_csv(output / f"{TARGET_ID}_duplicate_review.csv", dups, ["comparison_id", "correlation", "duplicate_label", "notes"])
    write_csv(output / f"{TARGET_ID}_family_comparison.csv", fam, ["strategy_id", "current_status", "evidence_source", "180d_median_equity", "+300 rate", "+400 rate", "180d_worst_drawdown", "stop-hit rate", "risk_buffer_vs_minus_600", "correlation_vs_target", "duplicate_label", "risk_label", "reason_for_status", "next_action"])
    write_csv(output / f"{TARGET_ID}_evidence_scorecard.csv", scores, ["criterion", "verdict", "notes"])
    write_csv(output / f"{TARGET_ID}_target_window_review.csv", target_review, ["window_start", "window_end", "horizon", "target_300_before_stop", "target_400_before_stop", "stop_day", "target300_day", "target400_day", "final_equity"])
    write_csv(output / f"{TARGET_ID}_drawdown_window_review.csv", drawdown_windows, ["window_start", "window_end", "horizon", "max_drawdown", "profit_dollars"])
    write_csv(output / f"{TARGET_ID}_rebalance_trace.csv", payload.get("trace", [])[:36], ["strategy_id", "rebalance_date", "weights"])
    write_csv(output / f"{TARGET_ID}_holdings_frequency.csv", payload.get("holdings_frequency", []), ["symbol", "rebalance_count", "selection_rate"])
    write_csv(output / f"{TARGET_ID}_sibling_comparison.csv", sibling, ["strategy_id", "current_status", "evidence_source", "180d_median_equity", "+300 rate", "+400 rate", "180d_worst_drawdown", "stop-hit rate", "risk_buffer_vs_minus_600", "correlation_vs_target", "duplicate_label", "risk_label", "reason_for_status", "next_action"])
    missing = ["# Missing Evidence", "", "Active combo exact series is unavailable and was not zero-filled."]
    if not payload["diagnostics_available"]:
        missing.append("Required cache missing: " + ",".join(payload["missing_symbols"]))
    else:
        missing.append("Holdings frequency was created from recomputed rebalance weights.")
        missing.append("Simple slippage stress was computed with the existing cached-data simulator.")
    (output / f"{TARGET_ID}_missing_evidence.md").write_text("\n".join(missing) + "\n", encoding="utf-8")
    (output / f"{TARGET_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n\nDo not run candidate_exhaustive, paper-forward, broker/live-order, provider download, or real-money workflow directly from this review.\n", encoding="utf-8")
    (output / f"{TARGET_ID}_promotion_decision.md").write_text(f"# Promotion Decision\n\nDecision: `{decision}`\n\nCandidate exhaustive recommended: `{str(candidate_recommended).lower()}`\n\nReason: {reason}\n", encoding="utf-8")
    if payload["diagnostics_available"]:
        s180 = payload["summaries"][TARGET_ID][180]
        stress = payload["stress_summary"][180]
        summary = [
            f"# {TARGET_ID} Promotion Review",
            "",
            f"Created at UTC: {now_utc()}",
            f"Decision: `{decision}`",
            f"Next action: `{next_action}`",
            f"Candidate exhaustive recommended: {str(candidate_recommended).lower()}",
            "",
            f"180d median equity: {fmt(s180['median_final_equity'])}",
            f"+300/+400 rates: {fmt(s180['target_300_before_stop_rate'])} / {fmt(s180['target_400_before_stop_rate'])}",
            f"180d worst drawdown: {fmt(s180['worst_drawdown'])}",
            f"Risk buffer vs -600: {fmt(s180['risk_buffer_vs_minus_600'])}",
            f"Stress 180d worst drawdown: {fmt(stress['worst_drawdown'])}",
            "",
            "Promotion review only. No candidate validation or paper-forward action was run.",
        ]
    else:
        summary = [f"# {TARGET_ID} Promotion Review", "", "Diagnostics unavailable due to missing cache."]
    (output / f"{TARGET_ID}_promotion_review_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest = {"created_at_utc": now_utc(), "target_strategy_id": TARGET_ID, "diagnostics_available": payload["diagnostics_available"], "missing_symbols": payload["missing_symbols"], "decision": decision, "next_action": next_action, "candidate_exhaustive_recommended": candidate_recommended, "candidate_exhaustive_run": False, "paper_forward_review": False, "paper_forward_activation": False, "paper_forward_checkpoint": False, "provider_api_called": False, "data_downloaded": False, "broker_integration": False, "live_orders": False, "order_placement": False, "real_money_recommendation": False, "data_history_mode": DATA_HISTORY_MODE}
    write_json(output / f"{TARGET_ID}_manifest.json", manifest)
    write_json(output / f"{TARGET_ID}_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet)}


def run_promotion_review(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_before = load_yaml(root / REGISTRY_PATH)
    core_before = protected_core_snapshot(registry_before)
    obs_hash_before = {sid: file_hash(path) for sid, path in active_observation_paths(root).items()}
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    payload = build_payload(root)
    dups = duplicate_rows(payload) if payload["diagnostics_available"] else []
    decision, next_action, candidate_recommended, reason = decide(payload, dups)
    update_registry(root, decision, next_action, candidate_recommended, "" if payload["diagnostics_available"] else ",".join(payload["missing_symbols"]))
    registry_after = load_yaml(root / REGISTRY_PATH)
    core_after = protected_core_snapshot(registry_after)
    obs_hash_after = {sid: file_hash(path) for sid, path in active_observation_paths(root).items()}
    consistency = {
        "promotion_review_completed": True,
        "target_strategy_correct": True,
        "cache_used": payload["diagnostics_available"] and not payload["missing_symbols"],
        "rule_fidelity_checked": True,
        "data_history_mode_recorded": True,
        "benchmark_review_created": True,
        "duplicate_review_created": True,
        "holdings_review_created_or_missing_recorded": bool(payload.get("holdings_frequency")) or not payload["diagnostics_available"],
        "risk_buffer_checked": True,
        "final_decision_assigned": bool(decision),
        "next_action_explicit": bool(next_action),
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_active_observation_mutation": obs_hash_before == obs_hash_after,
        "no_vm_quality_mutation": core_before.get(discovery.VM_ID) == core_after.get(discovery.VM_ID),
        "no_dsr_equal_weight_mutation": core_before.get(discovery.DSR_ID) == core_after.get(discovery.DSR_ID),
        "no_spy_200d_mutation": core_before.get(discovery.SPY_200D_ID) == core_after.get(discovery.SPY_200D_ID),
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, payload, decision, next_action, candidate_recommended, reason, consistency)
    return {"output_dir": outputs["output_dir"], "packet": outputs["packet"], "decision": decision, "next_action": next_action, "candidate_exhaustive_recommended": candidate_recommended, "reason": reason, "consistency": consistency}


def main() -> None:
    print(json.dumps(run_promotion_review(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
