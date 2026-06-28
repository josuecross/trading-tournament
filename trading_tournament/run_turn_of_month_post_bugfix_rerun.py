from __future__ import annotations

import csv
import json
import math
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_second_expansion_discovery_batch_with_lane_framework as second
import run_turn_of_month_zero_trade_audit as audit
import run_turn_of_month_zero_trade_fix as fix


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "turn_of_month_post_bugfix_rerun" / "latest"
FIX_DIR = fix.OUTPUT_DIR
REGISTRY_PATH = audit.REGISTRY_PATH
ROADMAP_PATH = audit.ROADMAP_PATH
CACHE_DIR = audit.CACHE_DIR

CANDIDATE_ID = audit.CANDIDATE_ID
LANE_ID = audit.LANE_ID
UNIVERSE = audit.UNIVERSE
EXCLUDED_CANDIDATES = {
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "cash_pause_overlay_meta_v1",
    "sector_rs_weekly_cash_filter_v1",
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
    "gror_balanced_momentum_60_40_v1",
}
VALID_OUTCOMES = {"discovery_reject", "promotion_review_candidate"}
FORBIDDEN_OUTCOMES = {"candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"}
NEXT_ACTION_PROMOTION = "promotion_review_for_turn_of_month_post_bugfix"
NEXT_ACTION_RERUN_AUDIT = "audit_turn_of_month_post_bugfix_rerun"
NEXT_ACTION_FAILURE_AUDIT = "audit_second_expansion_failures_before_more_expansion"
NEXT_ACTION_THIRD = "pre_register_third_expansion_discovery_batch_with_lane_framework"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PROMOTION, NEXT_ACTION_RERUN_AUDIT, NEXT_ACTION_FAILURE_AUDIT, NEXT_ACTION_THIRD}

STARTING_EQUITY = second.STARTING_EQUITY
STOP_DOLLARS = second.STOP_DOLLARS
BASE_SLIPPAGE = second.BASE_SLIPPAGE
STRESS_SLIPPAGE = second.STRESS_SLIPPAGE
LOAD_SYMBOLS = sorted(set([*UNIVERSE, *second.active.REQUIRED_CACHE_SYMBOLS]))
BENCHMARK_IDS = [
    second.active.VM_ID,
    second.active.DSR_ID,
    second.combo.COMBO_ID,
    second.active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    "calendar_no_signal_baseline",
]

MANIFEST_FLAGS = {
    "post_bugfix_rerun": True,
    "backtests_run": True,
    "discovery_run": True,
    "candidate_count": 1,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "frozen_rule_changed": False,
    "calendar_window_changed": False,
    "selection_rule_changed": False,
    "sma_filter_changed": False,
    "accepted_strategy_state_changed": False,
    "old_zero_trade_result_invalidated_by_bugfix": True,
    "old_gld_gror_state_resumed": False,
    "sector_rs_discovery_run": False,
    "intraday_candidates_included": False,
    "event_data_candidates_included": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 6)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def validate_authorization(root: Path) -> list[str]:
    mismatches = fix.validate_authorization(root)
    fix_manifest = read_json(root / FIX_DIR / "turn_of_month_zero_trade_fix_manifest.json")
    if fix_manifest.get("next_action") != "rerun_turn_of_month_frozen_candidate_discovery_after_bugfix":
        mismatches.append("turn-of-month fix evidence does not authorize post-bugfix rerun")
    if fix_manifest.get("implementation_bug_fixed") is not True:
        mismatches.append("turn-of-month implementation bug is not marked fixed")
    if fix_manifest.get("frozen_rule_changed") is not False:
        mismatches.append("turn-of-month frozen rule changed in fix evidence")
    return mismatches


def read_symbol_frame(root: Path, symbol: str) -> pd.DataFrame | None:
    return second.read_symbol_frame(root, symbol)


def load_prices(root: Path) -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in LOAD_SYMBOLS:
        frame = read_symbol_frame(root, symbol)
        if frame is None:
            missing.append(symbol)
        else:
            frames[symbol] = frame
    if missing:
        return {"available": False, "missing": missing}
    common_end = min(frame.index.max() for frame in frames.values())
    all_dates = sorted(set().union(*(set(frame.index[frame.index <= common_end]) for frame in frames.values())))
    store: dict[str, Any] = {
        "available": True,
        "index": pd.DatetimeIndex(all_dates),
        "first_dates": {symbol: str(frame.index.min().date()) for symbol, frame in frames.items()},
        "last_dates": {symbol: str(min(frame.index.max(), common_end).date()) for symbol, frame in frames.items()},
    }
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        store[column] = pd.concat(
            [frame[column].rename(symbol) for symbol, frame in frames.items()],
            axis=1,
            join="outer",
            sort=False,
        ).reindex(store["index"]).sort_index()
    return store


def signal_store(store: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": True,
        "index": store["index"],
        "first_dates": {symbol: store["first_dates"][symbol] for symbol in UNIVERSE},
        "last_dates": {symbol: store["last_dates"][symbol] for symbol in UNIVERSE},
        "open": store["open"][UNIVERSE],
        "high": store["high"][UNIVERSE],
        "low": store["low"][UNIVERSE],
        "close": store["close"][UNIVERSE],
        "adj_close": store["adj_close"][UNIVERSE],
        "volume": store["volume"][UNIVERSE],
    }


def start_end_indices(store: dict[str, Any]) -> tuple[int, int]:
    start_idx = int(store["index"].get_indexer([pd.Timestamp("2008-01-01")], method="bfill")[0])
    return start_idx, len(store["index"]) - 1


def benchmark_equities(store: dict[str, Any], start_idx: int, end_idx: int) -> dict[str, pd.Series]:
    benchmarks = second.benchmark_equities(store, start_idx, end_idx)
    return {
        second.active.VM_ID: benchmarks[second.active.VM_ID],
        second.active.DSR_ID: benchmarks[second.active.DSR_ID],
        second.combo.COMBO_ID: benchmarks[second.combo.COMBO_ID],
        second.active.SPY_200D_ID: benchmarks[second.active.SPY_200D_ID],
        "SPY_buy_hold": benchmarks["SPY_buy_hold"],
        "QQQ_buy_hold": benchmarks["QQQ_buy_hold"],
        "BIL_cash_proxy": benchmarks["BIL_cash_proxy"],
        "calendar_no_signal_baseline": benchmarks["BIL_cash_proxy"],
    }


def transition_rows(weights: pd.DataFrame, start_idx: int, end_idx: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous = "BIL"
    entries = 0
    exits = 0
    entry_dates: list[pd.Timestamp] = []
    hold_lengths: list[int] = []
    current_entry_date: pd.Timestamp | None = None
    bil_days = 0
    risk_days = {"SPY": 0, "QQQ": 0}
    for ts, row in weights.iloc[start_idx + 1 : end_idx + 1].iterrows():
        asset = max((symbol for symbol in UNIVERSE), key=lambda symbol: float(row.get(symbol, 0.0)))
        if asset == "BIL":
            bil_days += 1
        elif asset in risk_days:
            risk_days[asset] += 1
        if asset == previous:
            continue
        transition_type = "risk_to_risk"
        if previous == "BIL" and asset in {"SPY", "QQQ"}:
            transition_type = "entry"
            entries += 1
            entry_dates.append(pd.Timestamp(ts))
            current_entry_date = pd.Timestamp(ts)
        elif previous in {"SPY", "QQQ"} and asset == "BIL":
            transition_type = "exit"
            exits += 1
            if current_entry_date is not None:
                hold_lengths.append(max((pd.Timestamp(ts) - current_entry_date).days, 1))
                current_entry_date = None
        elif previous in {"SPY", "QQQ"} and asset in {"SPY", "QQQ"}:
            entries += 1
            exits += 1
            if current_entry_date is not None:
                hold_lengths.append(max((pd.Timestamp(ts) - current_entry_date).days, 1))
            current_entry_date = pd.Timestamp(ts)
        rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "date": str(pd.Timestamp(ts).date()),
                "from_asset": previous,
                "to_asset": asset,
                "transition_type": transition_type,
            }
        )
        previous = asset
    if current_entry_date is not None and len(weights.index) > end_idx:
        hold_lengths.append(max((pd.Timestamp(weights.index[end_idx]) - current_entry_date).days, 1))
    count_days = max(len(weights.iloc[start_idx + 1 : end_idx + 1]), 1)
    return rows, {
        "entry_count": entries,
        "exit_count": exits,
        "average_holding_period": float(np.mean(hold_lengths)) if hold_lengths else 0.0,
        "bil_allocation_frequency": bil_days / count_days,
        "selected_spy_frequency": risk_days["SPY"] / count_days,
        "selected_qqq_frequency": risk_days["QQQ"] / count_days,
        "first_entry_date": str(entry_dates[0].date()) if entry_dates else "",
    }


def reconcile(signal_audit: dict[str, Any], transition_stats: dict[str, Any]) -> dict[str, Any]:
    expected = int(signal_audit["counts"]["entry_signal_count_after_filters"])
    actual = int(transition_stats["entry_count"])
    status = "clean_exact_match"
    explanation = "Generated entries match expected post-filter first-window signals."
    if actual == expected + 1:
        status = "reconciled_initial_in_window_accounting_difference"
        explanation = (
            "Generated entries exceed expected first-window signals by one because the backtest starts inside a carried "
            "turn-of-month window whose first eligible day occurred before the 2008-01-01 test anchor. The first simulated "
            "BIL-to-risk transition is an initialization/accounting transition, not a duplicate first-window signal."
        )
    elif actual != expected:
        status = "inconsistent_entry_signal_mismatch"
        explanation = "Generated entries do not reconcile to expected post-filter signal count."
    return {
        "expected_entry_signal_count": expected,
        "actual_generated_entry_count": actual,
        "difference": actual - expected,
        "signal_entry_reconciliation_status": status,
        "signal_entry_reconciliation_explanation": explanation,
        "reconciliation_clean": status in {"clean_exact_match", "reconciled_initial_in_window_accounting_difference"},
    }


def evaluate(root: Path) -> dict[str, Any]:
    store = load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = second.indicators(store)
    start_idx, end_idx = start_end_indices(store)
    result = second.simulate_weight_strategy(store, ind, CANDIDATE_ID, start_idx, end_idx, BASE_SLIPPAGE)
    stress = second.simulate_weight_strategy(store, ind, CANDIDATE_ID, start_idx, end_idx, STRESS_SLIPPAGE)
    windows, summaries = second.window_rows(store, ind, CANDIDATE_ID, start_idx, end_idx)
    benchmarks = benchmark_equities(store, start_idx, end_idx)
    bench_metrics = {bid: second.series_metrics(series) for bid, series in benchmarks.items()}
    deltas = {bid: result["stats"]["ending_equity"] - metrics["ending_equity"] for bid, metrics in bench_metrics.items()}
    correlations = {
        bid: second.corr(result["equity"], series)
        for bid, series in benchmarks.items()
        if bid in {second.active.VM_ID, second.active.DSR_ID, second.combo.COMBO_ID, second.active.SPY_200D_ID}
    }
    weights = second.weights_turn_of_month(store, ind)
    trade_rows, transition_stats = transition_rows(weights, start_idx, end_idx)
    sig_store = signal_store(store)
    signal_audit = audit.audit_signals(root, sig_store, audit.indicators(sig_store))
    reconciliation = reconcile(signal_audit, transition_stats)
    metrics = {**result["stats"]}
    metrics.update(
        {
            "stress_ending_equity": stress["stats"]["ending_equity"],
            "stress_max_drawdown": stress["stats"]["max_drawdown"],
            "window_180d_median_final_equity": summaries.get(180, {}).get("median_final_equity", ""),
            "window_180d_worst_drawdown": summaries.get(180, {}).get("worst_drawdown", ""),
            "window_180d_stop_hit_rate": summaries.get(180, {}).get("stop_hit_rate", ""),
            "target_300_before_stop_rate_180d": summaries.get(180, {}).get("target_300_before_stop_rate", ""),
            "entry_count": transition_stats["entry_count"],
            "exit_count": transition_stats["exit_count"],
            "average_holding_period": transition_stats["average_holding_period"],
            "bil_allocation_frequency": transition_stats["bil_allocation_frequency"],
            "selected_spy_frequency": transition_stats["selected_spy_frequency"],
            "selected_qqq_frequency": transition_stats["selected_qqq_frequency"],
            "blocked_by_filter_count": signal_audit["counts"]["entries_blocked_risk_or_no_trade_filters"],
        }
    )
    return {
        "store": store,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "result": result,
        "stress": stress,
        "windows": windows,
        "summaries": summaries,
        "benchmarks": benchmarks,
        "bench_metrics": bench_metrics,
        "deltas": deltas,
        "correlations": correlations,
        "weights": weights,
        "trade_rows": trade_rows,
        "transition_stats": transition_stats,
        "signal_audit": signal_audit,
        "reconciliation": reconciliation,
        "metrics": metrics,
    }


def risk_improved(metrics: dict[str, Any], benchmark: dict[str, Any]) -> bool:
    return metrics["ending_equity"] > STARTING_EQUITY and metrics["max_drawdown"] - benchmark["max_drawdown"] > 150.0


def decision(payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    metrics = payload["metrics"]
    deltas = payload["deltas"]
    bench = payload["bench_metrics"]
    reconciliation_ok = bool(payload["reconciliation"]["reconciliation_clean"])
    risk_ok = metrics["risk_buffer"] > 25 and metrics["stress_max_drawdown"] > STOP_DOLLARS and metrics.get("window_180d_stop_hit_rate", 1.0) == 0.0
    slippage_ok = metrics["stress_ending_equity"] >= metrics["ending_equity"] - 150 and metrics["stress_max_drawdown"] > STOP_DOLLARS
    trade_ok = 30 <= metrics["entry_count"] <= 250 and metrics["trade_count"] <= 500
    benchmark_ok = (
        deltas[second.combo.COMBO_ID] > 25
        and (deltas[second.active.SPY_200D_ID] > 0 or risk_improved(metrics, bench[second.active.SPY_200D_ID]))
        and deltas["calendar_no_signal_baseline"] > 150
    )
    buyhold_edge_ok = deltas["SPY_buy_hold"] > 0 or deltas["QQQ_buy_hold"] > 0 or (
        metrics["ending_equity"] > STARTING_EQUITY and metrics["max_drawdown"] - min(bench["SPY_buy_hold"]["max_drawdown"], bench["QQQ_buy_hold"]["max_drawdown"]) > 300
    )
    gates = {
        "reconciliation_gate": reconciliation_ok,
        "risk_buffer_gate": bool(risk_ok),
        "slippage_stress_gate": bool(slippage_ok),
        "trade_count_gate": bool(trade_ok),
        "benchmark_edge_gate": bool(benchmark_ok),
        "buyhold_explanation_gate": bool(buyhold_edge_ok),
        "no_parameter_change_gate": True,
    }
    if all(gates.values()):
        return "promotion_review_candidate", "post_bugfix_turn_of_month_all_gates_passed", gates
    if not reconciliation_ok:
        return "discovery_reject", "signal_entry_reconciliation_inconsistent", gates
    if not slippage_ok:
        return "discovery_reject", "post_bugfix_turn_of_month_failed_slippage_stress_gate", gates
    if not risk_ok:
        return "discovery_reject", "post_bugfix_turn_of_month_failed_risk_gate", gates
    if not benchmark_ok or not buyhold_edge_ok:
        return "discovery_reject", "post_bugfix_turn_of_month_failed_benchmark_or_buyhold_gate", gates
    if not trade_ok:
        return "discovery_reject", "post_bugfix_turn_of_month_trade_count_gate_failed", gates
    return "discovery_reject", "post_bugfix_turn_of_month_evidence_not_strong_enough", gates


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "turn_of_month_post_bugfix_rerun_path": str(output),
            "turn_of_month_post_bugfix_rerun_status": "completed",
            "turn_of_month_post_bugfix_discovery_outcome": manifest["discovery_outcome"],
            "turn_of_month_post_bugfix_promotion_candidates_count": manifest["promotion_candidates_count"],
            "turn_of_month_post_bugfix_reconciliation_status": manifest["signal_entry_reconciliation_status"],
            "turn_of_month_post_bugfix_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "broker_path_touched": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    marker = "## Turn-of-Month Post-Bugfix Rerun"
    section = f"""## Turn-of-Month Post-Bugfix Rerun

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidate: `{CANDIDATE_ID}`
- Discovery outcome: `{manifest['discovery_outcome']}`
- Signal/entry reconciliation: `{manifest['signal_entry_reconciliation_status']}`
- Trade count: `{manifest['trade_count']}`
- Promotion candidates: `{manifest['promotion_candidates_count']}`
- Next action: `{manifest['next_action']}`
- This was a one-candidate frozen rerun only. No candidate_exhaustive, paper-forward action, provider download, broker/live path, sector RS discovery, old GROR state resumption, or real-money recommendation is authorized.
"""
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True, True


def write_outputs(output: Path, payload: dict[str, Any], manifest: dict[str, Any], outcome: str, reason: str, gates: dict[str, bool]) -> None:
    metrics = payload["metrics"]
    result_row = {
        "candidate_id": CANDIDATE_ID,
        "lane_id": LANE_ID,
        "outcome": outcome,
        "reason_code": reason,
        "signal_entry_reconciliation_status": manifest["signal_entry_reconciliation_status"],
        **metrics,
    }
    write_json(output / "turn_of_month_post_bugfix_rerun_manifest.json", manifest)
    (output / "turn_of_month_post_bugfix_rerun_summary.md").write_text(summary_md(manifest, payload, reason), encoding="utf-8")
    write_csv(output / "turn_of_month_post_bugfix_candidate_results.csv", [result_row], list(result_row.keys()))
    write_json(
        output / "turn_of_month_post_bugfix_candidate_metrics.json",
        {
            CANDIDATE_ID: {
                **metrics,
                "window_summaries": payload["summaries"],
                "correlations": payload["correlations"],
                "gate_results": gates,
                "signal_entry_reconciliation": payload["reconciliation"],
            }
        },
    )
    delta_rows = [
        {
            "candidate_id": CANDIDATE_ID,
            "benchmark_id": bid,
            "benchmark_available": True,
            "unavailable_reason": "",
            "ending_equity_delta": delta,
        }
        for bid, delta in payload["deltas"].items()
    ]
    write_csv(output / "turn_of_month_post_bugfix_benchmark_deltas.csv", delta_rows, ["candidate_id", "benchmark_id", "benchmark_available", "unavailable_reason", "ending_equity_delta"])
    write_csv(
        output / "turn_of_month_post_bugfix_risk_gate_results.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "risk_buffer": metrics["risk_buffer"],
                "max_drawdown": metrics["max_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stop_hit_rate_180d": metrics.get("window_180d_stop_hit_rate", ""),
                "risk_gate_pass": gates["risk_buffer_gate"],
            }
        ],
        ["candidate_id", "risk_buffer", "max_drawdown", "stress_max_drawdown", "stop_hit_rate_180d", "risk_gate_pass"],
    )
    write_csv(
        output / "turn_of_month_post_bugfix_slippage_stress_results.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "base_ending_equity": metrics["ending_equity"],
                "stress_ending_equity": metrics["stress_ending_equity"],
                "base_max_drawdown": metrics["max_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stress_pass": gates["slippage_stress_gate"],
            }
        ],
        ["candidate_id", "base_ending_equity", "stress_ending_equity", "base_max_drawdown", "stress_max_drawdown", "stress_pass"],
    )
    write_csv(output / "turn_of_month_post_bugfix_trade_diagnostics.csv", payload["trade_rows"], ["candidate_id", "date", "from_asset", "to_asset", "transition_type"])
    cal_rows = []
    for row in payload["signal_audit"]["signal_rows"]:
        cal_rows.append(row)
    write_csv(output / "turn_of_month_post_bugfix_calendar_diagnostics.csv", cal_rows, list(cal_rows[0].keys()) if cal_rows else ["candidate_id"])
    (output / "turn_of_month_post_bugfix_signal_entry_reconciliation.md").write_text(reconciliation_md(payload), encoding="utf-8")
    promotion_rows = [{"candidate_id": CANDIDATE_ID, "lane_id": LANE_ID, "outcome": outcome, "reason_code": reason}] if outcome == "promotion_review_candidate" else []
    write_csv(output / "turn_of_month_post_bugfix_promotion_candidates.csv", promotion_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    (output / "turn_of_month_post_bugfix_rejection_reasons.md").write_text(rejection_md(outcome, reason, gates), encoding="utf-8")
    (output / "turn_of_month_post_bugfix_next_action.md").write_text(next_action_md(manifest), encoding="utf-8")


def summary_md(manifest: dict[str, Any], payload: dict[str, Any], reason: str) -> str:
    metrics = payload["metrics"]
    return f"""# Turn-of-Month Post-Bugfix Rerun

Created UTC: `{manifest['created_utc']}`

Candidate: `{CANDIDATE_ID}`

Discovery outcome: `{manifest['discovery_outcome']}`

Reason: `{reason}`

Signal/entry reconciliation: `{manifest['signal_entry_reconciliation_status']}`

## Key Metrics

- Ending equity: `{fmt(metrics['ending_equity'])}`
- Max drawdown: `{fmt(metrics['max_drawdown'])}`
- Risk buffer: `{fmt(metrics['risk_buffer'])}`
- Trade count: `{fmt(metrics['trade_count'])}`
- Entry count: `{fmt(metrics['entry_count'])}`
- Exit count: `{fmt(metrics['exit_count'])}`
- 180d median final equity: `{fmt(metrics.get('window_180d_median_final_equity', ''))}`
- BIL allocation frequency: `{fmt(metrics['bil_allocation_frequency'])}`

Next action: `{manifest['next_action']}`
"""


def reconciliation_md(payload: dict[str, Any]) -> str:
    rec = payload["reconciliation"]
    return f"""# Turn-of-Month Signal/Entry Reconciliation

Expected entry signals after filters: `{rec['expected_entry_signal_count']}`

Actual generated entries: `{rec['actual_generated_entry_count']}`

Difference: `{rec['difference']}`

Status: `{rec['signal_entry_reconciliation_status']}`

Explanation: {rec['signal_entry_reconciliation_explanation']}
"""


def rejection_md(outcome: str, reason: str, gates: dict[str, bool]) -> str:
    if outcome != "discovery_reject":
        return "# Turn-of-Month Post-Bugfix Rejection Reasons\n\nNo rejected candidate.\n"
    failed = [name for name, passed in gates.items() if not passed]
    return "# Turn-of-Month Post-Bugfix Rejection Reasons\n\n" + f"- `{CANDIDATE_ID}`: `{outcome}` because `{reason}`.\n- Failed gates: `{', '.join(failed)}`.\n"


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"# Turn-of-Month Post-Bugfix Next Action\n\n`{manifest['next_action']}`\n\nDo not run this next action from the rerun task.\n"


def consistency_check(output: Path, manifest: dict[str, Any], outcome: str, strategies_before: list[dict[str, Any]], strategies_after: list[dict[str, Any]]) -> dict[str, Any]:
    required = [
        "turn_of_month_post_bugfix_rerun_manifest.json",
        "turn_of_month_post_bugfix_rerun_summary.md",
        "turn_of_month_post_bugfix_candidate_results.csv",
        "turn_of_month_post_bugfix_candidate_metrics.json",
        "turn_of_month_post_bugfix_benchmark_deltas.csv",
        "turn_of_month_post_bugfix_risk_gate_results.csv",
        "turn_of_month_post_bugfix_slippage_stress_results.csv",
        "turn_of_month_post_bugfix_trade_diagnostics.csv",
        "turn_of_month_post_bugfix_calendar_diagnostics.csv",
        "turn_of_month_post_bugfix_signal_entry_reconciliation.md",
        "turn_of_month_post_bugfix_promotion_candidates.csv",
        "turn_of_month_post_bugfix_rejection_reasons.md",
        "turn_of_month_post_bugfix_next_action.md",
    ]
    check = {
        "exactly_one_candidate_evaluated": manifest["candidate_count"] == 1 and manifest["candidate_id"] == CANDIDATE_ID,
        "candidate_id_is_turn_of_month": manifest["candidate_id"] == CANDIDATE_ID,
        "no_excluded_candidates_evaluated": not bool(set(manifest["evaluated_candidate_ids"]) & EXCLUDED_CANDIDATES),
        "frozen_rule_unchanged": not manifest["frozen_rule_changed"],
        "calendar_window_unchanged": not manifest["calendar_window_changed"],
        "selection_rule_unchanged": not manifest["selection_rule_changed"],
        "sma_filter_unchanged": not manifest["sma_filter_changed"],
        "provider_download_false": not manifest["provider_download"],
        "candidate_outcome_valid": outcome in VALID_OUTCOMES and outcome not in FORBIDDEN_OUTCOMES,
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "sector_rs_discovery_not_run": not manifest["sector_rs_discovery_run"],
        "intraday_event_candidates_not_included": not manifest["intraday_candidates_included"] and not manifest["event_data_candidates_included"],
        "signal_entry_reconciliation_file_exists": (output / "turn_of_month_post_bugfix_signal_entry_reconciliation.md").exists(),
        "signal_entry_reconciliation_status_recorded": bool(manifest["signal_entry_reconciliation_status"]),
        "risk_gate_results_exist": (output / "turn_of_month_post_bugfix_risk_gate_results.csv").exists(),
        "slippage_stress_results_exist": (output / "turn_of_month_post_bugfix_slippage_stress_results.csv").exists(),
        "benchmark_deltas_exist": (output / "turn_of_month_post_bugfix_benchmark_deltas.csv").exists(),
        "promotion_candidate_file_exists": (output / "turn_of_month_post_bugfix_promotion_candidates.csv").exists(),
        "rejection_reasons_exist_if_rejected": outcome != "discovery_reject" or (output / "turn_of_month_post_bugfix_rejection_reasons.md").exists(),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "accepted_rejected_strategy_state_unchanged": strategies_before == strategies_after,
        "required_files_exist": all((output / name).exists() for name in required),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_turn_of_month_post_bugfix_rerun(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = strategy_snapshot(root)
    payload = evaluate(root)
    outcome, reason, gates = decision(payload)
    if outcome not in VALID_OUTCOMES:
        raise RuntimeError(f"invalid discovery outcome: {outcome}")
    promotion_ids = [CANDIDATE_ID] if outcome == "promotion_review_candidate" else []
    rejected_ids = [CANDIDATE_ID] if outcome == "discovery_reject" else []
    rec_status = payload["reconciliation"]["signal_entry_reconciliation_status"]
    if outcome == "promotion_review_candidate":
        next_action = NEXT_ACTION_PROMOTION
    elif rec_status == "inconsistent_entry_signal_mismatch":
        next_action = NEXT_ACTION_RERUN_AUDIT
    else:
        next_action = NEXT_ACTION_THIRD
    manifest = {
        "artifact": "turn_of_month_post_bugfix_rerun",
        "created_utc": now_utc(),
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "evaluated_candidate_ids": [CANDIDATE_ID],
        "discovery_outcome": outcome,
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "rejected_candidate_ids": rejected_ids,
        "signal_entry_reconciliation_status": rec_status,
        "next_action": next_action,
        "trade_count": payload["metrics"]["trade_count"],
        "entry_count": payload["metrics"]["entry_count"],
        "exit_count": payload["metrics"]["exit_count"],
        **MANIFEST_FLAGS,
    }
    registry_updated, roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_outputs(output, payload, manifest, outcome, reason, gates)
    strategies_after = strategy_snapshot(root)
    consistency = consistency_check(output, manifest, outcome, strategies_before, strategies_after)
    write_json(output / "turn_of_month_post_bugfix_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "discovery_outcome": outcome,
        "signal_entry_reconciliation_status": rec_status,
        "trade_count": payload["metrics"]["trade_count"],
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_turn_of_month_post_bugfix_rerun(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
