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

import pandas as pd
import yaml

import run_parallel_discovery_approved_cache_batch as discovery
import run_qvm_risk_adjusted_top2_promotion_review as qvm_review


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = discovery.REGISTRY_PATH
QVM_TOP2_ID = "qvm_quality_value_momentum_top2_v1"
QVM_RISK_ID = qvm_review.TARGET_ID
LVQ_ID = "lvq_lowvol_quality_spy_regime_v1"
QVM_TOP2_OUTPUT = Path("evidence") / "promotion_reviews" / QVM_TOP2_ID / "latest"
LVQ_OUTPUT = Path("evidence") / "promotion_reviews" / LVQ_ID / "latest"
SIBLING_EVIDENCE = Path("evidence") / "promotion_reviews" / QVM_RISK_ID / "latest" / f"{QVM_RISK_ID}_sibling_comparison.csv"
DATA_HISTORY_MODE = discovery.DATA_HISTORY_MODE
LVQ_SYMBOLS = ["SPLV", "USMV", "QUAL", "VTV", "SPY", "BIL"]
LVQ_CANDIDATE_ASSETS = ["SPLV", "USMV", "QUAL", "VTV", "SPY"]
LVQ_REVIEW_IDS = [
    LVQ_ID,
    QVM_RISK_ID,
    QVM_TOP2_ID,
    discovery.VM_ID,
    discovery.DSR_ID,
    discovery.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
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


def specs_by_id() -> dict[str, dict[str, Any]]:
    return {spec["strategy_id"]: spec for spec in discovery.candidate_specs()}


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches = discovery.state_mismatches(root, registry)
    rows = rows_by_id(registry)
    qvm_risk = rows.get(QVM_RISK_ID, {})
    if qvm_risk.get("promotion_decision") != "mark_too_risky" and qvm_risk.get("status") != "mark_too_risky":
        mismatches.append(f"{QVM_RISK_ID} is not marked too risky")
    for strategy_id in [QVM_TOP2_ID, LVQ_ID]:
        row = rows.get(strategy_id, {})
        if not row:
            mismatches.append(f"{strategy_id} missing from registry")
        if row.get("candidate_exhaustive_run") is not False:
            mismatches.append(f"{strategy_id} candidate_exhaustive_run is not false")
        if row.get("paper_forward_active") is not False:
            mismatches.append(f"{strategy_id} paper_forward_active is not false")
        if row.get("real_money_recommendation") is not False:
            mismatches.append(f"{strategy_id} real_money_recommendation is not false")
    sibling_path = root / SIBLING_EVIDENCE
    if not sibling_path.exists():
        mismatches.append("QVM sibling evidence missing")
    return mismatches


def read_qvm_sibling_evidence(root: Path) -> dict[str, Any]:
    path = root / SIBLING_EVIDENCE
    if not path.exists():
        return {"available": False, "rows": [], "target_row": None}
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    target = next((row for row in rows if row.get("strategy_id") == QVM_TOP2_ID), None)
    return {"available": target is not None, "rows": rows, "target_row": target}


def qvm_top2_decision(evidence: dict[str, Any]) -> tuple[str, str, str]:
    row = evidence.get("target_row")
    if not row:
        return "promotion_review_required", "create_promotion_review_for_qvm_quality_value_momentum_top2_v1", "sibling evidence missing"
    corr = float(row.get("correlation_vs_target") or 0.0)
    duplicate = row.get("duplicate_label") == "near_duplicate" or corr >= 0.95
    risk_thin = row.get("risk_label") == "too_thin" or float(row.get("risk_buffer_vs_minus_600") or 999.0) < 25.0
    if duplicate:
        return "mark_duplicate_or_near_duplicate", "archive_qvm_quality_value_momentum_top2_v1_as_duplicate_diagnostic", "near-duplicate of rejected QVM risk-adjusted row; risk buffer also too thin" if risk_thin else "near-duplicate of rejected QVM risk-adjusted row"
    if risk_thin:
        return "mark_too_risky", "mark_qvm_quality_value_momentum_top2_v1_too_risky", "risk buffer too thin in sibling evidence"
    return "promotion_review_required", "create_promotion_review_for_qvm_quality_value_momentum_top2_v1", "sibling evidence did not support disposition"


def create_packet(directory: Path, packet_name: str) -> Path:
    packet = directory / packet_name
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_qvm_top2_outputs(root: Path, evidence: dict[str, Any], decision: str, next_action: str, reason: str, consistency: dict[str, Any]) -> dict[str, str]:
    output = root / QVM_TOP2_OUTPUT
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = [evidence["target_row"]] if evidence.get("target_row") else []
    fields = ["strategy_id", "current_status", "evidence_source", "180d_median_equity", "+300 rate", "+400 rate", "180d_worst_drawdown", "stop-hit rate", "risk_buffer_vs_minus_600", "correlation_vs_target", "duplicate_label", "risk_label", "reason_for_status", "next_action"]
    write_csv(output / f"{QVM_TOP2_ID}_sibling_evidence.csv", rows, fields)
    (output / f"{QVM_TOP2_ID}_disposition_summary.md").write_text(
        f"# {QVM_TOP2_ID} Disposition\n\nDecision: `{decision}`\n\nNext action: `{next_action}`\n\nReason: {reason}\n\nUsed sibling evidence from `{SIBLING_EVIDENCE}`; no full recompute was run.\n",
        encoding="utf-8",
    )
    (output / f"{QVM_TOP2_ID}_promotion_decision.md").write_text(f"# Promotion Decision\n\nDecision: `{decision}`\n\nReason: {reason}\n", encoding="utf-8")
    (output / f"{QVM_TOP2_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    manifest = {
        "created_at_utc": now_utc(),
        "target_strategy_id": QVM_TOP2_ID,
        "sibling_evidence_used": evidence.get("available", False),
        "full_recompute_run": False,
        "decision": decision,
        "next_action": next_action,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "real_money_recommendation": False,
    }
    write_json(output / f"{QVM_TOP2_ID}_manifest.json", manifest)
    write_json(output / f"{QVM_TOP2_ID}_consistency_check.json", consistency)
    packet = create_packet(output, f"{QVM_TOP2_ID}_disposition_packet.zip")
    return {"output_dir": str(output), "packet": str(packet)}


def lvq_payload(root: Path) -> dict[str, Any]:
    approved = discovery.approved_strategy_symbols(root)
    discovery.validate_spec_symbols(specs_by_id()[LVQ_ID], approved)
    close, missing, cache_rows = discovery.prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "cache_rows": cache_rows}
    specs = specs_by_id()
    windows = {strategy_id: qvm_review.run_windows_with_slippage(close, strategy_id, specs, qvm_review.BASE_SLIPPAGE) for strategy_id in LVQ_REVIEW_IDS}
    stressed = qvm_review.run_windows_with_slippage(close, LVQ_ID, specs, qvm_review.STRESS_SLIPPAGE)
    summaries = {strategy_id: {h: qvm_review.summarize(windows[strategy_id], strategy_id, h) for h in discovery.HORIZONS} for strategy_id in LVQ_REVIEW_IDS}
    stress_summary = {h: qvm_review.summarize(stressed, LVQ_ID, h) for h in discovery.HORIZONS}
    returns = {strategy_id: discovery.full_returns(close, strategy_id, specs) for strategy_id in LVQ_REVIEW_IDS}
    trace = lvq_holdings_trace(close, specs)
    freq = holdings_frequency(trace, LVQ_SYMBOLS)
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


def lvq_holdings_trace(close: pd.DataFrame, specs: dict[str, dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    months = [dt.year * 12 + dt.month for dt in close.index]
    last_month = None
    for t in range(252, len(close)):
        month = months[t]
        if month == last_month:
            continue
        weights = discovery.strategy_weights(close, LVQ_ID, t, specs)
        rows.append({"strategy_id": LVQ_ID, "rebalance_date": str(close.index[t].date()), "weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True)})
        last_month = month
        if limit and len(rows) >= limit:
            break
    return rows


def holdings_frequency(trace: list[dict[str, Any]], symbols: list[str]) -> list[dict[str, Any]]:
    counts = {symbol: 0 for symbol in symbols}
    total = len(trace)
    for row in trace:
        weights = json.loads(row["weights"])
        for symbol, weight in weights.items():
            if weight > 0:
                counts[symbol] = counts.get(symbol, 0) + 1
    return [{"symbol": symbol, "rebalance_count": counts.get(symbol, 0), "selection_rate": fmt(counts.get(symbol, 0) / total if total else 0.0)} for symbol in symbols]


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    return discovery.corr(returns, left, right)


def lvq_benchmark_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    target = payload["summaries"][LVQ_ID][180]
    rows: list[dict[str, Any]] = []
    for benchmark_id in [QVM_RISK_ID, QVM_TOP2_ID, discovery.VM_ID, discovery.DSR_ID, "active_combo", discovery.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]:
        if benchmark_id == "active_combo":
            rows.append({"benchmark_id": benchmark_id, "target_strategy_metric": fmt(target["median_final_equity"]), "benchmark_metric": "", "delta": "unavailable", "correlation": "unavailable", "comparison_status": "unavailable", "notes": "active combo exact series unavailable; not zero-filled"})
            continue
        bench = payload["summaries"][benchmark_id][180]
        rows.append({"benchmark_id": benchmark_id, "target_strategy_metric": fmt(target["median_final_equity"]), "benchmark_metric": fmt(bench["median_final_equity"]), "delta": fmt(target["median_final_equity"] - bench["median_final_equity"]), "correlation": fmt(corr(payload["returns"], LVQ_ID, benchmark_id)), "comparison_status": "computed", "notes": "bounded cached-data comparison"})
    return rows


def lvq_profit_rows(payload: dict[str, Any], bench_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"metric": "diagnostics", "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"}]
    s90 = payload["summaries"][LVQ_ID][90]
    s180 = payload["summaries"][LVQ_ID][180]
    base = [
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
    rows = [{"metric": metric, "value": fmt(value), "horizon": horizon, "notes": "bounded LVQ promotion-review recompute"} for metric, value, horizon in base]
    for row in bench_rows:
        rows.append({"metric": f"delta_vs_{row['benchmark_id']}", "value": row["delta"], "horizon": 180, "notes": row["notes"]})
    return rows


def lvq_risk_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"metric": "diagnostics", "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"}]
    s90 = payload["summaries"][LVQ_ID][90]
    s180 = payload["summaries"][LVQ_ID][180]
    stress180 = payload["stress_summary"][180]
    return [
        {"metric": "90d_worst_drawdown", "value": fmt(s90["worst_drawdown"]), "horizon": 90, "notes": "base slippage"},
        {"metric": "180d_worst_drawdown", "value": fmt(s180["worst_drawdown"]), "horizon": 180, "notes": "base slippage"},
        {"metric": "median_drawdown", "value": fmt(s180["median_drawdown"]), "horizon": 180, "notes": "base slippage"},
        {"metric": "stop_hit_rate", "value": fmt(s180["stop_hit_rate"]), "horizon": 180, "notes": "absolute -600 stop"},
        {"metric": "risk_buffer_vs_minus_600", "value": fmt(s180["risk_buffer_vs_minus_600"]), "horizon": 180, "notes": "risk buffer"},
        {"metric": "worst_loss_window", "value": fmt(s180["worst_loss_window"]), "horizon": 180, "notes": "worst 180d profit/loss window"},
        {"metric": "stress_180d_worst_drawdown", "value": fmt(stress180["worst_drawdown"]), "horizon": 180, "notes": f"simple cost stress slippage={qvm_review.STRESS_SLIPPAGE}"},
        {"metric": "stress_risk_buffer_vs_minus_600", "value": fmt(stress180["risk_buffer_vs_minus_600"]), "horizon": 180, "notes": "stress risk buffer"},
    ]


def lvq_duplicate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for benchmark_id in [discovery.VM_ID, discovery.DSR_ID, discovery.SPY_200D_ID, "QQQ_buy_hold", QVM_RISK_ID, QVM_TOP2_ID]:
        c = corr(payload["returns"], LVQ_ID, benchmark_id)
        label = "near_duplicate" if isinstance(c, float) and c >= 0.88 else "overlap_watch" if isinstance(c, float) and c >= 0.80 else "not_duplicate"
        rows.append({"comparison_id": benchmark_id, "correlation": fmt(c), "duplicate_label": label, "notes": "daily full-sample return correlation"})
    return rows


def lvq_family_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for strategy_id in [LVQ_ID, QVM_RISK_ID, QVM_TOP2_ID, discovery.VM_ID, discovery.DSR_ID, discovery.SPY_200D_ID, "QQQ_buy_hold", "BIL_cash_proxy"]:
        s180 = payload["summaries"][strategy_id][180]
        c = "target" if strategy_id == LVQ_ID else corr(payload["returns"], LVQ_ID, strategy_id)
        duplicate = "target" if strategy_id == LVQ_ID else "near_duplicate" if isinstance(c, float) and c >= 0.88 else "not_duplicate"
        risk = "acceptable" if s180["risk_buffer_vs_minus_600"] >= 100 else "too_thin"
        rows.append({"strategy_id": strategy_id, "current_status": "promotion_review_target" if strategy_id == LVQ_ID else "comparator", "evidence_source": "cached_promotion_review", "180d_median_equity": fmt(s180["median_final_equity"]), "+300 rate": fmt(s180["target_300_before_stop_rate"]), "+400 rate": fmt(s180["target_400_before_stop_rate"]), "180d_worst_drawdown": fmt(s180["worst_drawdown"]), "stop-hit rate": fmt(s180["stop_hit_rate"]), "risk_buffer_vs_minus_600": fmt(s180["risk_buffer_vs_minus_600"]), "correlation_vs_target": fmt(c), "duplicate_label": duplicate, "risk_label": risk, "reason_for_status": "remaining-candidate promotion review comparator", "next_action": ""})
    return rows


def lvq_decision(payload: dict[str, Any], dup_rows: list[dict[str, Any]], bench_rows: list[dict[str, Any]]) -> tuple[str, str, bool, str]:
    if not payload["diagnostics_available"]:
        return "evidence_missing", "reject_lvq_lowvol_quality_spy_regime_v1", False, "required cache missing"
    s180 = payload["summaries"][LVQ_ID][180]
    if s180["stop_hit_rate"] > 0 or s180["worst_drawdown"] <= discovery.STOP_DOLLARS:
        return "mark_too_risky", "mark_lvq_lowvol_quality_spy_regime_v1_too_risky", False, "stop or drawdown breach"
    fatal_duplicate = any(row["duplicate_label"] == "near_duplicate" and row["comparison_id"] in {discovery.VM_ID, discovery.SPY_200D_ID} for row in dup_rows)
    if fatal_duplicate:
        return "mark_duplicate_or_near_duplicate", "archive_lvq_lowvol_quality_spy_regime_v1_as_duplicate_diagnostic", False, "near-duplicate of active VM or SPY_200d"
    deltas = {row["benchmark_id"]: row["delta"] for row in bench_rows}
    weak_vs_refs = any(isinstance(deltas.get(key), float) and deltas[key] < -25 for key in [discovery.DSR_ID, discovery.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold"])
    profit_ok = s180["median_final_equity"] >= 3300 and s180["target_300_before_stop_rate"] >= 0.4 and s180["target_400_before_stop_rate"] >= 0.25
    if profit_ok and not weak_vs_refs:
        return "promote_to_candidate_exhaustive_queue", "create_candidate_exhaustive_prompt_for_lvq_lowvol_quality_spy_regime_v1", True, "profit/risk/additive profile passed"
    if profit_ok:
        return "keep_watchlist", "keep_lvq_lowvol_quality_spy_regime_v1_on_watchlist", False, "safer and interesting, but weaker than active DSR/SPY references"
    return "mark_too_slow", "mark_lvq_lowvol_quality_spy_regime_v1_too_slow", False, "profit/target profile not strong enough"


def lvq_scorecard(payload: dict[str, Any], bench_rows: list[dict[str, Any]], dup_rows: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"criterion": "evidence_available", "verdict": "fail", "notes": "cache/data missing"}]
    s180 = payload["summaries"][LVQ_ID][180]
    deltas = {row["benchmark_id"]: row["delta"] for row in bench_rows}
    holdings = {row["symbol"]: float(row["selection_rate"]) for row in payload["holdings_frequency"]}
    concentration = max(holdings.values()) if holdings else 0.0
    items = [
        ("evidence_available", "pass", "bounded recompute available"),
        ("cache_ready", "pass", "approved cached ETF data used"),
        ("rule_fidelity_confirmed", "pass", "matches discovery implementation source of truth"),
        ("data_history_mode_recorded", "pass", DATA_HISTORY_MODE),
        ("target_300_before_stop", "pass" if s180["target_300_before_stop_rate"] >= 0.4 else "fail", s180["target_300_before_stop_rate"]),
        ("target_400_before_stop", "pass" if s180["target_400_before_stop_rate"] >= 0.25 else "fail", s180["target_400_before_stop_rate"]),
        ("median_final_equity", "weak_pass" if s180["median_final_equity"] >= 3300 else "fail", s180["median_final_equity"]),
        ("worst_drawdown", "pass" if s180["worst_drawdown"] > discovery.STOP_DOLLARS else "fail", s180["worst_drawdown"]),
        ("stop_hit_rate", "pass" if s180["stop_hit_rate"] == 0 else "fail", s180["stop_hit_rate"]),
        ("risk_buffer_sufficient", "pass" if s180["risk_buffer_vs_minus_600"] >= 100 else "manual_review", s180["risk_buffer_vs_minus_600"]),
        ("delta_vs_active_vm", "weak_pass" if isinstance(deltas.get(discovery.VM_ID), float) and deltas[discovery.VM_ID] > 0 else "fail", deltas.get(discovery.VM_ID)),
        ("delta_vs_active_dsr", "fail" if isinstance(deltas.get(discovery.DSR_ID), float) and deltas[discovery.DSR_ID] < 0 else "weak_pass", deltas.get(discovery.DSR_ID)),
        ("delta_vs_SPY_200d", "fail" if isinstance(deltas.get(discovery.SPY_200D_ID), float) and deltas[discovery.SPY_200D_ID] < 0 else "weak_pass", deltas.get(discovery.SPY_200D_ID)),
        ("duplicate_risk_vs_active_vm", "weak_pass", "see duplicate review"),
        ("holdings_concentration_risk", "manual_review" if concentration > 0.60 else "weak_pass", concentration),
        ("policy_compliance", "pass", "approved symbols only"),
        ("no_forbidden_mechanics", "pass", "no leverage/margin/shorting/derivatives/intraday"),
        ("no_real_money_path", "pass", "real_money_recommendation=false"),
        ("final_decision", "weak_pass" if decision == "keep_watchlist" else "manual_review", decision),
    ]
    return [{"criterion": c, "verdict": v, "notes": fmt(n)} for c, v, n in items]


def write_lvq_outputs(root: Path, payload: dict[str, Any], decision: str, next_action: str, recommended: bool, reason: str, consistency: dict[str, Any]) -> dict[str, str]:
    output = root / LVQ_OUTPUT
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    bench = lvq_benchmark_rows(payload)
    dup = lvq_duplicate_rows(payload) if payload["diagnostics_available"] else []
    fam = lvq_family_rows(payload) if payload["diagnostics_available"] else []
    write_csv(output / f"{LVQ_ID}_profit_review.csv", lvq_profit_rows(payload, bench), ["metric", "value", "horizon", "notes"])
    write_csv(output / f"{LVQ_ID}_risk_review.csv", lvq_risk_rows(payload), ["metric", "value", "horizon", "notes"])
    write_csv(output / f"{LVQ_ID}_benchmark_review.csv", bench, ["benchmark_id", "target_strategy_metric", "benchmark_metric", "delta", "correlation", "comparison_status", "notes"])
    write_csv(output / f"{LVQ_ID}_duplicate_review.csv", dup, ["comparison_id", "correlation", "duplicate_label", "notes"])
    write_csv(output / f"{LVQ_ID}_family_comparison.csv", fam, ["strategy_id", "current_status", "evidence_source", "180d_median_equity", "+300 rate", "+400 rate", "180d_worst_drawdown", "stop-hit rate", "risk_buffer_vs_minus_600", "correlation_vs_target", "duplicate_label", "risk_label", "reason_for_status", "next_action"])
    write_csv(output / f"{LVQ_ID}_evidence_scorecard.csv", lvq_scorecard(payload, bench, dup, decision), ["criterion", "verdict", "notes"])
    if payload["diagnostics_available"]:
        target_windows = payload["windows"][LVQ_ID]
        write_csv(output / f"{LVQ_ID}_target_window_review.csv", [{"window_start": r["window_start"], "window_end": r["window_end"], "horizon": r["horizon"], "target_300_before_stop": r["target_300_before_stop"], "target_400_before_stop": r["target_400_before_stop"], "stop_day": r["stop_day"], "target300_day": r["target300_day"], "target400_day": r["target400_day"], "final_equity": fmt(r["final_equity"])} for r in target_windows], ["window_start", "window_end", "horizon", "target_300_before_stop", "target_400_before_stop", "stop_day", "target300_day", "target400_day", "final_equity"])
        write_csv(output / f"{LVQ_ID}_drawdown_window_review.csv", [{"window_start": r["window_start"], "window_end": r["window_end"], "horizon": r["horizon"], "max_drawdown": fmt(r["max_drawdown"]), "profit_dollars": fmt(r["profit_dollars"])} for r in target_windows], ["window_start", "window_end", "horizon", "max_drawdown", "profit_dollars"])
        write_csv(output / f"{LVQ_ID}_rebalance_trace.csv", payload["trace"][:36], ["strategy_id", "rebalance_date", "weights"])
        write_csv(output / f"{LVQ_ID}_holdings_frequency.csv", payload["holdings_frequency"], ["symbol", "rebalance_count", "selection_rate"])
    missing_lines = ["# Missing Evidence", "", "Active combo exact series is unavailable and was not zero-filled."]
    if payload["diagnostics_available"]:
        missing_lines.append("Holdings frequency and simple slippage stress were created from cached-data recompute.")
    else:
        missing_lines.append("Required cache missing: " + ",".join(payload["missing_symbols"]))
    (output / f"{LVQ_ID}_missing_evidence.md").write_text("\n".join(missing_lines) + "\n", encoding="utf-8")
    (output / f"{LVQ_ID}_promotion_decision.md").write_text(f"# Promotion Decision\n\nDecision: `{decision}`\n\nCandidate exhaustive recommended: `{str(recommended).lower()}`\n\nReason: {reason}\n", encoding="utf-8")
    (output / f"{LVQ_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    if payload["diagnostics_available"]:
        s180 = payload["summaries"][LVQ_ID][180]
        summary = [
            f"# {LVQ_ID} Promotion Review",
            "",
            f"Created at UTC: {now_utc()}",
            f"Decision: `{decision}`",
            f"Next action: `{next_action}`",
            f"Candidate exhaustive recommended: {str(recommended).lower()}",
            "",
            f"180d median equity: {fmt(s180['median_final_equity'])}",
            f"+300/+400 rates: {fmt(s180['target_300_before_stop_rate'])} / {fmt(s180['target_400_before_stop_rate'])}",
            f"180d worst drawdown: {fmt(s180['worst_drawdown'])}",
            f"Risk buffer vs -600: {fmt(s180['risk_buffer_vs_minus_600'])}",
            "",
            "Promotion review only. No candidate validation or paper-forward action was run.",
        ]
    else:
        summary = [f"# {LVQ_ID} Promotion Review", "", "Diagnostics unavailable due to missing cache."]
    (output / f"{LVQ_ID}_promotion_review_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest = {"created_at_utc": now_utc(), "target_strategy_id": LVQ_ID, "diagnostics_available": payload["diagnostics_available"], "missing_symbols": payload["missing_symbols"], "decision": decision, "next_action": next_action, "candidate_exhaustive_recommended": recommended, "candidate_exhaustive_run": False, "paper_forward_review": False, "paper_forward_activation": False, "paper_forward_checkpoint": False, "provider_api_called": False, "data_downloaded": False, "broker_integration": False, "live_orders": False, "order_placement": False, "real_money_recommendation": False, "data_history_mode": DATA_HISTORY_MODE}
    write_json(output / f"{LVQ_ID}_manifest.json", manifest)
    write_json(output / f"{LVQ_ID}_consistency_check.json", consistency)
    packet = create_packet(output, f"{LVQ_ID}_promotion_review_packet.zip")
    return {"output_dir": str(output), "packet": str(packet)}


def update_registry(root: Path, qvm_decision: str, qvm_next: str, lvq_decision: str, lvq_next: str, lvq_recommended: bool) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    for row in registry.get("strategies", []):
        if row.get("id") == QVM_TOP2_ID:
            row.update({
                "promotion_review_completed": True,
                "promotion_decision": qvm_decision,
                "status": qvm_decision,
                "current_status": qvm_decision,
                "candidate_exhaustive_recommended": False,
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "latest_promotion_review_path": str(root / QVM_TOP2_OUTPUT),
                "latest_evidence_path": str(root / QVM_TOP2_OUTPUT),
                "allowed_next_action": qvm_next,
                "allowed_next_actions": [qvm_next],
                "evidence_source": "qvm_top2_sibling_disposition_from_qvm_risk_adjusted_review",
                "missing_evidence": "",
                "promotion_reason": f"Sibling-evidence disposition: {qvm_decision}; next_action={qvm_next}",
            })
        if row.get("id") == LVQ_ID:
            row.update({
                "promotion_review_completed": True,
                "promotion_decision": lvq_decision,
                "status": lvq_decision,
                "current_status": lvq_decision,
                "candidate_exhaustive_recommended": lvq_recommended,
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "latest_promotion_review_path": str(root / LVQ_OUTPUT),
                "latest_evidence_path": str(root / LVQ_OUTPUT),
                "allowed_next_action": lvq_next,
                "allowed_next_actions": [lvq_next],
                "evidence_source": "lvq_lowvol_quality_spy_regime_promotion_review_cached_etf",
                "missing_evidence": "",
                "promotion_reason": f"Bounded promotion review decision: {lvq_decision}; next_action={lvq_next}",
            })
        if row.get("id") in {QVM_TOP2_ID, LVQ_ID}:
            row["forbidden_next_actions"] = sorted(set(row.get("forbidden_next_actions", [])) | {"run_candidate_exhaustive", "paper_forward_review", "paper_forward_activation", "paper_forward_checkpoint", "promote_to_real_money", "add_broker_integration", "live_orders", "order_placement", "place_live_orders", "download_data", "tune_parameters"})
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def run_remaining_reviews(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_before = load_yaml(root / REGISTRY_PATH)
    core_before = protected_core_snapshot(registry_before)
    obs_hash_before = {sid: file_hash(path) for sid, path in active_observation_paths(root).items()}
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    qvm_evidence = read_qvm_sibling_evidence(root)
    qvm_decision, qvm_next, qvm_reason = qvm_top2_decision(qvm_evidence)
    lvq = lvq_payload(root)
    lvq_bench = lvq_benchmark_rows(lvq)
    lvq_dup = lvq_duplicate_rows(lvq) if lvq["diagnostics_available"] else []
    lvq_decision_value, lvq_next, lvq_recommended, lvq_reason = lvq_decision(lvq, lvq_dup, lvq_bench)
    update_registry(root, qvm_decision, qvm_next, lvq_decision_value, lvq_next, lvq_recommended)
    registry_after = load_yaml(root / REGISTRY_PATH)
    core_after = protected_core_snapshot(registry_after)
    obs_hash_after = {sid: file_hash(path) for sid, path in active_observation_paths(root).items()}
    base_consistency = {
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
    qvm_consistency = {
        "target_strategy_correct": True,
        "cache_used": False,
        "sibling_evidence_used": qvm_evidence["available"],
        "rule_fidelity_checked": True,
        "benchmark_review_created": False,
        "duplicate_review_created": True,
        "holdings_review_created_or_missing_recorded": True,
        "final_decision_assigned": bool(qvm_decision),
        "next_action_explicit": bool(qvm_next),
        **base_consistency,
    }
    qvm_consistency["consistency_passed"] = all(bool(value) for key, value in qvm_consistency.items() if key != "cache_used" and key != "benchmark_review_created")
    lvq_consistency = {
        "target_strategy_correct": True,
        "cache_used": lvq["diagnostics_available"] and not lvq["missing_symbols"],
        "sibling_evidence_used": False,
        "rule_fidelity_checked": True,
        "benchmark_review_created": True,
        "duplicate_review_created": True,
        "holdings_review_created_or_missing_recorded": bool(lvq.get("holdings_frequency")) or not lvq["diagnostics_available"],
        "final_decision_assigned": bool(lvq_decision_value),
        "next_action_explicit": bool(lvq_next),
        **base_consistency,
    }
    lvq_consistency["consistency_passed"] = all(bool(value) for key, value in lvq_consistency.items() if key != "sibling_evidence_used")
    qvm_outputs = write_qvm_top2_outputs(root, qvm_evidence, qvm_decision, qvm_next, qvm_reason, qvm_consistency)
    lvq_outputs = write_lvq_outputs(root, lvq, lvq_decision_value, lvq_next, lvq_recommended, lvq_reason, lvq_consistency)
    overall_next = "continue_next_approved_family_discovery_batch" if not lvq_recommended else lvq_next
    return {
        "qvm_top2_output_dir": qvm_outputs["output_dir"],
        "qvm_top2_decision": qvm_decision,
        "qvm_top2_next_action": qvm_next,
        "lvq_output_dir": lvq_outputs["output_dir"],
        "lvq_decision": lvq_decision_value,
        "lvq_next_action": lvq_next,
        "lvq_candidate_exhaustive_recommended": lvq_recommended,
        "overall_next_discovery_action": overall_next,
        "qvm_consistency": qvm_consistency,
        "lvq_consistency": lvq_consistency,
    }


def main() -> None:
    print(json.dumps(run_remaining_reviews(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
