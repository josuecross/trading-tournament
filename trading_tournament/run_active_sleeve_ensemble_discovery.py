from __future__ import annotations

import csv
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

import run_active_combo_benchmark_reporting as combo
import run_active_sleeve_ensemble_preregistration as prereg
import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "active_sleeve_ensemble" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

LANE_ID = "active_sleeve_ensemble_lane"
NEXT_ACTION_RUN = "run_active_sleeve_ensemble_discovery_batch"
NEXT_ACTION_PROMOTION = "create_promotion_review_for_best_active_sleeve_ensemble_candidate"
NEXT_ACTION_WATCHLIST = "keep_active_sleeve_ensemble_as_benchmark_watchlist"
NEXT_ACTION_ARCHIVE = "archive_active_sleeve_ensemble_lane_as_no_improvement"
NEXT_ACTION_REPAIR = "repair_active_sleeve_ensemble_discovery_outputs"

ENSEMBLE_ROWS = [row["row_id"] for row in prereg.FUTURE_ROWS]
REFERENCE_IDS = [
    active.VM_ID,
    active.DSR_ID,
    combo.COMBO_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
]
CORRELATION_REFERENCE_IDS = [active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID]
REJECT_DECISIONS = {"duplicate_or_near_duplicate", "too_slow_for_profit_goal", "too_risky", "evidence_missing"}
WATCHLIST_DECISIONS = {"benchmark_watchlist", "weaker_than_active_references_watchlist"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return round(float(value), 4)
    return value


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: active.file_hash(path) for strategy_id, path in active.active_observation_paths(root).items()}


def protected_core_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    metadata = {
        "latest_discovery_path",
        "latest_active_sleeve_ensemble_discovery_path",
        "discovery_decision",
        "evidence_source",
        "current_permission_status",
        "current_candidate_exhaustive_permission",
        "current_promotion_review_permission",
    }
    protected: dict[str, dict[str, Any]] = {}
    for strategy_id in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID]:
        row = deepcopy(rows.get(strategy_id, {}))
        for key in metadata:
            row.pop(key, None)
        protected[strategy_id] = row
    return protected


def ensure_roadmap_current_next_action(root: Path) -> dict[str, Any]:
    path = root / ROADMAP_PATH
    original = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    lines = original.splitlines()
    current_line_index = next((idx for idx, line in enumerate(lines) if line.startswith("Current next action:")), None)
    stale_value = ""
    updated = False
    if current_line_index is None:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, f"Current next action: `{NEXT_ACTION_RUN}`")
        updated = True
    else:
        stale_value = lines[current_line_index]
        desired = f"Current next action: `{NEXT_ACTION_RUN}`"
        if lines[current_line_index] != desired:
            lines[current_line_index] = desired
            updated = True
    note = (
        "\n## Roadmap Next Action Consistency\n\n"
        f"- Checked at UTC: `{now_utc()}`\n"
        f"- Top-level current next action: `{NEXT_ACTION_RUN}`\n"
        "- Historical backlog entries are deferred/context only and were not otherwise rewritten.\n"
    )
    marker = "## Roadmap Next Action Consistency"
    text = "\n".join(lines).rstrip() + "\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + note
    else:
        text = text.rstrip() + "\n" + note
    if updated or text != original:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {
        "roadmap_updated": updated or text != original,
        "original_current_next_action": stale_value,
        "current_next_action": NEXT_ACTION_RUN,
        "roadmap_next_action_consistent": True,
    }


def preregistered_rows(root: Path) -> list[str]:
    path = root / "evidence" / "pre_registered_lanes" / "active_sleeve_ensemble" / "latest" / "active_sleeve_ensemble_future_rows.csv"
    rows = read_csv_rows(path)
    return [row.get("row_id", "") for row in rows]


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    meta = registry.get("registry", {})
    rows = rows_by_id(registry)
    if meta.get("lane_id") != LANE_ID:
        mismatches.append("active sleeve ensemble lane id missing from registry metadata")
    if meta.get("lane_status") not in {"pre_registered_not_run", "discovery_completed"}:
        mismatches.append("active sleeve ensemble lane is not pre-registered or discovery-completed metadata")
    if meta.get("candidate_exhaustive_run") is not False:
        mismatches.append("registry lane candidate_exhaustive_run is not false")
    if meta.get("paper_forward_active") is not False:
        mismatches.append("registry lane paper_forward_active is not false")
    if meta.get("real_money_recommendation") is not False:
        mismatches.append("registry lane real_money_recommendation is not false")
    if preregistered_rows(root) != ENSEMBLE_ROWS:
        mismatches.append("pre-registered row set does not match fixed six-row list")

    combo_manifest_path = root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json"
    if not combo_manifest_path.exists():
        mismatches.append("active combo benchmark manifest missing")
    else:
        combo_manifest = json.loads(combo_manifest_path.read_text(encoding="utf-8"))
        if combo_manifest.get("benchmark_id") != combo.COMBO_ID:
            mismatches.append("active combo benchmark id mismatch")
        if combo_manifest.get("active_combo_is_reference_not_active_strategy") is not True:
            mismatches.append("active combo is not marked reference-only")

    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    pipeline = {row.get("stage", ""): row for row in read_csv_rows(checkpoint / "candidate_pipeline_status.csv")}
    if pipeline.get("candidate_exhaustive_queue", {}).get("count") not in {"0", 0}:
        mismatches.append("candidate_exhaustive queue is not empty")
    if pipeline.get("promotion_review_candidates", {}).get("count") not in {"0", 0}:
        mismatches.append("promotion review candidate queue is not empty before discovery")

    for strategy_id in [active.VM_ID, active.DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
        if not active.active_observation_paths(root)[strategy_id].exists():
            mismatches.append(f"{strategy_id} active observation file missing")
    spy = rows.get(active.SPY_200D_ID, {})
    if spy.get("paper_forward_active") is not True or spy.get("rules_frozen") is not True:
        mismatches.append(f"{active.SPY_200D_ID} is not active/frozen")
    return mismatches


def sleeve_daily_return(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    daily_return = 0.0
    for symbol, weight in weights.items():
        if active.available_at(close, symbol, today, 1):
            daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
    return daily_return


def spy_trailing_drawdown(close: pd.DataFrame, signal_t: int, lookback: int = 63) -> float | None:
    if "SPY" not in close.columns or signal_t - lookback + 1 < 0 or pd.isna(close.iloc[signal_t]["SPY"]):
        return None
    window = close["SPY"].iloc[signal_t - lookback + 1 : signal_t + 1].dropna()
    if len(window) < lookback:
        return None
    peak = float(window.max())
    return float(window.iloc[-1] / peak - 1.0) if peak > 0 else None


def sleeve_targets(close: pd.DataFrame, row_id: str, signal_t: int) -> dict[str, float]:
    if row_id == "ase_vm_dsr_equal_weight_v1":
        return {"vm": 0.50, "dsr": 0.50, "bil": 0.00}
    if row_id == "ase_dsr_tilt_60_40_v1":
        return {"vm": 0.40, "dsr": 0.60, "bil": 0.00}
    if row_id == "ase_vm_tilt_60_40_v1":
        return {"vm": 0.60, "dsr": 0.40, "bil": 0.00}
    if row_id == "ase_risk_budget_static_45_45_10_bil_v1":
        return {"vm": 0.45, "dsr": 0.45, "bil": 0.10}
    if row_id == "ase_spy200d_canary_vm_dsr_v1":
        if active.eligible(close, "SPY", signal_t):
            return {"vm": 0.50, "dsr": 0.50, "bil": 0.00}
        return {"vm": 0.50, "dsr": 0.25, "bil": 0.25}
    if row_id == "ase_drawdown_guard_reference_v1":
        drawdown = spy_trailing_drawdown(close, signal_t)
        if drawdown is not None and drawdown < -0.10:
            return {"vm": 0.50, "dsr": 0.25, "bil": 0.25}
        return {"vm": 0.50, "dsr": 0.50, "bil": 0.00}
    raise ValueError(f"Unknown active sleeve ensemble row: {row_id}")


def simulate_ensemble_window(close: pd.DataFrame, start: int, horizon: int, row_id: str) -> dict[str, Any]:
    if row_id == "ase_vm_dsr_equal_weight_v1":
        result = combo.combo_window(close, start, horizon)
        result["strategy_id"] = row_id
        return result

    sleeve_values = {"vm": active.STARTING_EQUITY / 2, "dsr": active.STARTING_EQUITY / 2, "bil": 0.0}
    peak = active.STARTING_EQUITY
    max_drawdown = 0.0
    last_month = None
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    stop = None
    target300 = None
    target400 = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            total = sum(sleeve_values.values())
            targets = sleeve_targets(close, row_id, signal)
            sleeve_values = {key: total * targets.get(key, 0.0) for key in ["vm", "dsr", "bil"]}
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            last_month = month
        sleeve_values["vm"] *= 1.0 + sleeve_daily_return(close, today, vm_weights)
        sleeve_values["dsr"] *= 1.0 + sleeve_daily_return(close, today, dsr_weights)
        sleeve_values["bil"] *= 1.0 + sleeve_daily_return(close, today, {"BIL": 1.0})
        equity = sum(sleeve_values.values())
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - active.STARTING_EQUITY
        if stop is None and profit <= active.STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {
        "strategy_id": row_id,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": sum(sleeve_values.values()),
        "profit_dollars": sum(sleeve_values.values()) - active.STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def run_windows(close: pd.DataFrame, strategy_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        for start in active.sample_starts(close, horizon):
            if strategy_id in ENSEMBLE_ROWS:
                rows.append(simulate_ensemble_window(close, start, horizon, strategy_id))
            elif strategy_id == combo.COMBO_ID:
                rows.append(combo.combo_window(close, start, horizon))
            else:
                rows.append(active.simulate(close, start, horizon, strategy_id))
    return rows


def full_equity_series_for_row(close: pd.DataFrame, row_id: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if row_id == "ase_vm_dsr_equal_weight_v1":
        frame, allocations = combo.full_equity_series(close)
        frame = frame.rename(columns={"active_combo_equity": "ensemble_equity"})
        frame["strategy_id"] = row_id
        for row in allocations:
            row["strategy_id"] = row_id
            row["bil_sleeve_weight"] = 0.0
            row["trigger_state"] = "none"
        return frame[["date", "strategy_id", "ensemble_equity"]], allocations

    sleeve_values = {"vm": active.STARTING_EQUITY / 2, "dsr": active.STARTING_EQUITY / 2, "bil": 0.0}
    last_month = None
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    rows: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    for today in range(253, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            total = sum(sleeve_values.values())
            targets = sleeve_targets(close, row_id, signal)
            sleeve_values = {key: total * targets.get(key, 0.0) for key in ["vm", "dsr", "bil"]}
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            trigger_state = "normal"
            if row_id == "ase_spy200d_canary_vm_dsr_v1":
                trigger_state = "spy_above_200d" if active.eligible(close, "SPY", signal) else "spy_below_200d"
            if row_id == "ase_drawdown_guard_reference_v1":
                dd = spy_trailing_drawdown(close, signal)
                trigger_state = "guarded" if dd is not None and dd < -0.10 else "normal"
            allocations.append(
                {
                    "rebalance_date": str(close.index[today].date()),
                    "strategy_id": row_id,
                    "vm_sleeve_weight": targets["vm"],
                    "dsr_sleeve_weight": targets["dsr"],
                    "bil_sleeve_weight": targets["bil"],
                    "vm_sleeve_value_after_rebalance": round(sleeve_values["vm"], 4),
                    "dsr_sleeve_value_after_rebalance": round(sleeve_values["dsr"], 4),
                    "bil_sleeve_value_after_rebalance": round(sleeve_values["bil"], 4),
                    "trigger_state": trigger_state,
                    "vm_holdings": json.dumps({k: round(v, 6) for k, v in sorted(vm_weights.items())}, sort_keys=True),
                    "dsr_holdings": json.dumps({k: round(v, 6) for k, v in sorted(dsr_weights.items())}, sort_keys=True),
                }
            )
            last_month = month
        sleeve_values["vm"] *= 1.0 + sleeve_daily_return(close, today, vm_weights)
        sleeve_values["dsr"] *= 1.0 + sleeve_daily_return(close, today, dsr_weights)
        sleeve_values["bil"] *= 1.0 + sleeve_daily_return(close, today, {"BIL": 1.0})
        rows.append({"date": str(close.index[today].date()), "strategy_id": row_id, "ensemble_equity": round(sum(sleeve_values.values()), 6)})
    return pd.DataFrame(rows), allocations


def returns_from_equity(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(frame["date"])
    return pd.Series(pd.to_numeric(frame["ensemble_equity"], errors="coerce").values, index=dates).pct_change().dropna()


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def risk_buffer(summary: dict[str, Any]) -> float | str:
    if "worst_drawdown" not in summary:
        return "unavailable"
    return float(summary["worst_drawdown"]) - active.STOP_DOLLARS


def build_payload(root: Path) -> dict[str, Any]:
    close, missing = active.prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "close": close}
    ids = ENSEMBLE_ROWS + REFERENCE_IDS
    window_rows = {strategy_id: run_windows(close, strategy_id) for strategy_id in ids}
    summaries = {strategy_id: {h: active.summarize(window_rows[strategy_id], strategy_id, h) for h in active.HORIZONS} for strategy_id in ids}
    returns: dict[str, pd.Series] = {
        active.VM_ID: active.full_returns(close, active.VM_ID),
        active.DSR_ID: active.full_returns(close, active.DSR_ID),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        "SPY_buy_hold": active.full_returns(close, "SPY_buy_hold"),
        "QQQ_buy_hold": active.full_returns(close, "QQQ_buy_hold"),
        "BIL_cash_proxy": active.full_returns(close, "BIL_cash_proxy"),
    }
    combo_frame, _combo_allocations = combo.full_equity_series(close)
    returns[combo.COMBO_ID] = combo.returns_from_equity(combo_frame, "active_combo_equity")
    allocation_rows: list[dict[str, Any]] = []
    equity_frames: list[pd.DataFrame] = []
    for row_id in ENSEMBLE_ROWS:
        equity_frame, allocations = full_equity_series_for_row(close, row_id)
        returns[row_id] = returns_from_equity(equity_frame)
        equity_frames.append(equity_frame)
        allocation_rows.extend(allocations)
    return {
        "diagnostics_available": True,
        "missing_symbols": [],
        "close": close,
        "window_rows": window_rows,
        "summaries": summaries,
        "returns": returns,
        "allocation_rows": allocation_rows,
        "equity_frame": pd.concat(equity_frames, ignore_index=True) if equity_frames else pd.DataFrame(),
    }


def result_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    rows: list[dict[str, Any]] = []
    for row_id in ENSEMBLE_ROWS:
        s90 = payload["summaries"][row_id][90]
        s180 = payload["summaries"][row_id][180]
        result = {
            "strategy_id": row_id,
            "decision": decisions[row_id]["decision"],
            "decision_reason": decisions[row_id]["reason"],
            "90d_median_final_equity": fmt(s90.get("median_final_equity")),
            "180d_median_final_equity": fmt(s180.get("median_final_equity")),
            "180d_mean_final_equity": fmt(s180.get("mean_final_equity")),
            "180d_p75_final_equity": fmt(s180.get("p75_final_equity")),
            "180d_p90_final_equity": fmt(s180.get("p90_final_equity")),
            "best_final_equity": fmt(s180.get("best_final_equity")),
            "worst_final_equity": fmt(s180.get("worst_final_equity")),
            "target_300_before_stop_rate": fmt(s180.get("target_300_before_stop_rate")),
            "target_400_before_stop_rate": fmt(s180.get("target_400_before_stop_rate")),
            "180d_worst_drawdown": fmt(s180.get("worst_drawdown")),
            "stop_hit_rate": fmt(s180.get("stop_hit_rate")),
            "risk_buffer_vs_minus_600": fmt(risk_buffer(s180)),
            "simple_cost_stress_status": "unavailable_not_supported_by_existing_active_combo_model",
            "simple_cost_stress_180d_median_final_equity": "unavailable",
        }
        for ref in CORRELATION_REFERENCE_IDS:
            result[f"corr_vs_{ref}"] = fmt(corr(payload["returns"], row_id, ref))
        for ref in REFERENCE_IDS:
            ref_summary = payload["summaries"][ref][180]
            result[f"delta_vs_{ref}"] = fmt(float(s180["median_final_equity"]) - float(ref_summary["median_final_equity"]))
        rows.append(result)
    return rows


def benchmark_delta_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    rows: list[dict[str, Any]] = []
    for row_id in ENSEMBLE_ROWS:
        row_summary = payload["summaries"][row_id][180]
        for ref in REFERENCE_IDS:
            if ref not in payload["summaries"] or 180 not in payload["summaries"][ref]:
                rows.append(
                    {
                        "strategy_id": row_id,
                        "reference_id": ref,
                        "strategy_180d_median_final_equity": fmt(row_summary.get("median_final_equity")),
                        "reference_180d_median_final_equity": "unavailable",
                        "delta": "unavailable",
                        "correlation": fmt(corr(payload["returns"], row_id, ref)),
                        "comparison_status": "unavailable",
                        "missing_reason": "reference summary unavailable",
                    }
                )
                continue
            ref_summary = payload["summaries"][ref][180]
            rows.append(
                {
                    "strategy_id": row_id,
                    "reference_id": ref,
                    "strategy_180d_median_final_equity": fmt(row_summary["median_final_equity"]),
                    "reference_180d_median_final_equity": fmt(ref_summary["median_final_equity"]),
                    "delta": fmt(float(row_summary["median_final_equity"]) - float(ref_summary["median_final_equity"])),
                    "correlation": fmt(corr(payload["returns"], row_id, ref)),
                    "comparison_status": "computed",
                    "missing_reason": "",
                }
            )
    return rows


def decide_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    if not payload["diagnostics_available"]:
        return {row_id: {"decision": "evidence_missing", "reason": "cached diagnostics unavailable"} for row_id in ENSEMBLE_ROWS}
    combo_s = payload["summaries"][combo.COMBO_ID][180]
    combo_median = float(combo_s["median_final_equity"])
    combo_buffer = float(risk_buffer(combo_s))
    combo_dd = float(combo_s["worst_drawdown"])
    for row_id in ENSEMBLE_ROWS:
        s = payload["summaries"][row_id][180]
        median = float(s["median_final_equity"])
        buffer = float(risk_buffer(s))
        worst_dd = float(s["worst_drawdown"])
        stop = float(s["stop_hit_rate"])
        t300 = float(s["target_300_before_stop_rate"])
        t400 = float(s["target_400_before_stop_rate"])
        delta_combo = median - combo_median
        delta_vm = median - float(payload["summaries"][active.VM_ID][180]["median_final_equity"])
        delta_dsr = median - float(payload["summaries"][active.DSR_ID][180]["median_final_equity"])
        corr_combo = corr(payload["returns"], row_id, combo.COMBO_ID)

        if row_id == "ase_vm_dsr_equal_weight_v1":
            decisions[row_id] = {"decision": "benchmark_watchlist", "reason": "equal-weight active combo control/reference row"}
        elif stop > 0 or buffer < 25 or buffer < combo_buffer - 100 or worst_dd < combo_dd - 100:
            decisions[row_id] = {"decision": "too_risky", "reason": "drawdown/risk buffer materially worse than active combo or near -600 boundary"}
        elif isinstance(corr_combo, float) and corr_combo >= 0.98 and delta_combo < 25 and buffer <= combo_buffer + 25:
            decisions[row_id] = {"decision": "duplicate_or_near_duplicate", "reason": "highly correlated with active combo without meaningful median or buffer benefit"}
        elif (
            delta_combo >= 25
            and buffer >= combo_buffer - 25
            and stop == 0.0
            and t300 >= 0.60
            and t400 >= 0.40
            and delta_vm >= 50
            and delta_dsr >= 50
        ):
            decisions[row_id] = {"decision": "promotion_review_candidate", "reason": "beats active combo and both active sleeves while preserving risk gates"}
        elif median < combo_median or median < float(payload["summaries"][active.SPY_200D_ID][180]["median_final_equity"]):
            decisions[row_id] = {"decision": "weaker_than_active_references_watchlist", "reason": "weaker than active references but diagnostically useful"}
        elif t300 < 0.60 or t400 < 0.40 or median < combo_median + 25:
            decisions[row_id] = {"decision": "too_slow_for_profit_goal", "reason": "risk controlled but target/profit profile does not justify added complexity"}
        else:
            decisions[row_id] = {"decision": "weaker_than_active_references_watchlist", "reason": "bounded discovery did not clear conservative promotion gates"}
    return decisions


def final_next_action(decisions: dict[str, dict[str, Any]], diagnostics_available: bool) -> str:
    if not diagnostics_available:
        return NEXT_ACTION_REPAIR
    labels = {row["decision"] for row in decisions.values()}
    if "promotion_review_candidate" in labels:
        return NEXT_ACTION_PROMOTION
    if labels & WATCHLIST_DECISIONS:
        return NEXT_ACTION_WATCHLIST
    return NEXT_ACTION_ARCHIVE


def registry_row_for_result(row_id: str, decision: str, output_path: Path, next_action: str) -> dict[str, Any]:
    promotion = decision == "promotion_review_candidate"
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "active_sleeve_ensemble",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier2_exploratory",
        "status": decision,
        "role": "active_sleeve_ensemble_discovery_row",
        "rules_frozen": True,
        "paper_forward_active": False,
        "implementation_status": "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "active_sleeve_ensemble_discovery",
        "latest_evidence_path": str(output_path),
        "latest_known_result_summary": f"Active sleeve ensemble discovery verdict: {decision}.",
        "allowed_next_action": NEXT_ACTION_PROMOTION if promotion else "research_sample_review",
        "forbidden_next_actions": [
            "run_candidate_exhaustive",
            "paper_forward_activation",
            "paper_forward_checkpoint",
            "paper_forward_review",
            "promote_to_real_money",
            "add_broker_integration",
            "live_orders",
            "order_placement",
            "download_data",
            "tune_parameters",
        ],
        "risk_framework_status": "research_sample_only",
        "paper_forward_allowed_by_risk_framework": False,
        "real_money_recommendation": False,
        "promotion_blockers": "research_sample_only;not_candidate_exhaustive;not_paper_forward_allowed",
        "promotion_requirements": "Separate promotion review only; no candidate_exhaustive from discovery batch.",
        "demotion_or_kill_criteria": "Weak target profile, unacceptable drawdown, duplicate exposure, or benchmark lag.",
        "notes": "Fixed-rule active sleeve ensemble discovery row; no broker/live-order/real-money path.",
        "strategy_id": row_id,
        "family": "active_sleeve_ensemble",
        "instrument_lane": "ETF",
        "evidence_tier": "research_sample",
        "current_status": decision,
        "allowed_next_actions": [NEXT_ACTION_PROMOTION if promotion else "research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": promotion,
        "promotion_decision": decision,
        "promotion_reason": "promotion review candidate" if promotion else decision,
        "primary_failure_mode": "not_flagged" if promotion else decision,
        "duplication_risk": "near_active_combo" if decision == "duplicate_or_near_duplicate" else "not_flagged",
        "risk_budget_status": "research_sample_screened",
        "evidence_needed": "promotion review only if selected; no paper-forward action",
        "duplicate_of": combo.COMBO_ID if decision == "duplicate_or_near_duplicate" else "",
        "blocked_reason": "",
        "discovery_decision": decision,
        "latest_discovery_path": str(output_path),
        "candidate_exhaustive_run_after_discovery": False,
        "paper_forward_active_after_discovery": False,
    }


def update_registry(root: Path, decisions: dict[str, dict[str, Any]], next_action: str, output_path: Path) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    meta = registry.setdefault("registry", {})
    meta["lane_id"] = LANE_ID
    meta["lane_status"] = "discovery_completed"
    meta["latest_discovery_path"] = str(output_path)
    meta["promotion_candidates_count"] = sum(1 for row in decisions.values() if row["decision"] == "promotion_review_candidate")
    meta["candidate_exhaustive_run"] = False
    meta["paper_forward_active"] = False
    meta["real_money_recommendation"] = False
    meta["next_action"] = next_action
    meta["current_next_action"] = next_action
    meta["no_candidate_exhaustive_run"] = True
    meta["no_paper_forward_action"] = True
    meta["no_real_money_recommendation"] = True

    existing = rows_by_id(registry)
    for row_id, details in decisions.items():
        new_row = registry_row_for_result(row_id, details["decision"], output_path, next_action)
        if row_id in existing:
            existing[row_id].update(new_row)
        else:
            registry.setdefault("strategies", []).append(new_row)
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def decision_log_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id in ENSEMBLE_ROWS:
        s = payload["summaries"].get(row_id, {}).get(180, {}) if payload["diagnostics_available"] else {}
        rows.append(
            {
                "strategy_id": row_id,
                "decision": decisions[row_id]["decision"],
                "decision_reason": decisions[row_id]["reason"],
                "180d_median_final_equity": fmt(s.get("median_final_equity", "unavailable")),
                "180d_worst_drawdown": fmt(s.get("worst_drawdown", "unavailable")),
                "stop_hit_rate": fmt(s.get("stop_hit_rate", "unavailable")),
                "promotion_review_required": decisions[row_id]["decision"] == "promotion_review_candidate",
                "candidate_exhaustive_recommended": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
            }
        )
    return rows


def target_window_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for row_id in ENSEMBLE_ROWS:
        for row in payload["window_rows"][row_id]:
            rows.append(
                {
                    "strategy_id": row_id,
                    "horizon": row["horizon"],
                    "window_start": row["window_start"],
                    "window_end": row["window_end"],
                    "target_300_before_stop": row["target_300_before_stop"],
                    "target_400_before_stop": row["target_400_before_stop"],
                    "absolute_600_stop_hit": row["absolute_600_stop_hit"],
                    "final_equity": fmt(row["final_equity"]),
                }
            )
    return rows


def drawdown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for row_id in ENSEMBLE_ROWS:
        for row in payload["window_rows"][row_id]:
            rows.append(
                {
                    "strategy_id": row_id,
                    "horizon": row["horizon"],
                    "window_start": row["window_start"],
                    "window_end": row["window_end"],
                    "max_drawdown": fmt(row["max_drawdown"]),
                    "profit_dollars": fmt(row["profit_dollars"]),
                }
            )
    return rows


def create_packet(output: Path) -> Path:
    packet = output / "active_sleeve_ensemble_discovery_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(
    root: Path,
    payload: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    next_action: str,
    consistency: dict[str, Any],
    state_notes: list[str],
    roadmap_status: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    results = result_rows(payload, decisions)
    deltas = benchmark_delta_rows(payload)
    decisions_rows = decision_log_rows(payload, decisions)
    watchlist = [row for row in decisions_rows if row["decision"] in WATCHLIST_DECISIONS]
    promotions = [row for row in decisions_rows if row["decision"] == "promotion_review_candidate"]
    rejects = [row for row in decisions_rows if row["decision"] in REJECT_DECISIONS]

    result_fields = [
        "strategy_id",
        "decision",
        "decision_reason",
        "90d_median_final_equity",
        "180d_median_final_equity",
        "180d_mean_final_equity",
        "180d_p75_final_equity",
        "180d_p90_final_equity",
        "best_final_equity",
        "worst_final_equity",
        "target_300_before_stop_rate",
        "target_400_before_stop_rate",
        "180d_worst_drawdown",
        "stop_hit_rate",
        "risk_buffer_vs_minus_600",
        "simple_cost_stress_status",
        "simple_cost_stress_180d_median_final_equity",
        *[f"corr_vs_{ref}" for ref in CORRELATION_REFERENCE_IDS],
        *[f"delta_vs_{ref}" for ref in REFERENCE_IDS],
    ]
    write_csv(output / "active_sleeve_ensemble_results.csv", results, result_fields)
    write_csv(
        output / "active_sleeve_ensemble_benchmark_delta.csv",
        deltas,
        [
            "strategy_id",
            "reference_id",
            "strategy_180d_median_final_equity",
            "reference_180d_median_final_equity",
            "delta",
            "correlation",
            "comparison_status",
            "missing_reason",
        ],
    )
    decision_fields = [
        "strategy_id",
        "decision",
        "decision_reason",
        "180d_median_final_equity",
        "180d_worst_drawdown",
        "stop_hit_rate",
        "promotion_review_required",
        "candidate_exhaustive_recommended",
        "paper_forward_active",
        "real_money_recommendation",
    ]
    write_csv(output / "active_sleeve_ensemble_decision_log.csv", decisions_rows, decision_fields)
    write_csv(output / "active_sleeve_ensemble_watchlist.csv", watchlist, decision_fields)
    write_csv(output / "active_sleeve_ensemble_promotion_candidates.csv", promotions, decision_fields)
    write_csv(output / "active_sleeve_ensemble_rejects.csv", rejects, decision_fields)
    write_csv(output / "active_sleeve_ensemble_drawdown_review.csv", drawdown_rows(payload), ["strategy_id", "horizon", "window_start", "window_end", "max_drawdown", "profit_dollars"])
    write_csv(
        output / "active_sleeve_ensemble_target_window_review.csv",
        target_window_rows(payload),
        ["strategy_id", "horizon", "window_start", "window_end", "target_300_before_stop", "target_400_before_stop", "absolute_600_stop_hit", "final_equity"],
    )
    write_csv(
        output / "active_sleeve_ensemble_allocation_trace.csv",
        payload["allocation_rows"] if payload["diagnostics_available"] else [],
        [
            "rebalance_date",
            "strategy_id",
            "vm_sleeve_weight",
            "dsr_sleeve_weight",
            "bil_sleeve_weight",
            "vm_sleeve_value_after_rebalance",
            "dsr_sleeve_value_after_rebalance",
            "bil_sleeve_value_after_rebalance",
            "trigger_state",
            "vm_holdings",
            "dsr_holdings",
        ],
    )

    (output / "active_sleeve_ensemble_next_action.md").write_text(
        f"# Active Sleeve Ensemble Next Action\n\n`{next_action}`\n\nDo not recommend candidate_exhaustive directly. Do not activate paper-forward, broker/live-order, provider download, or real-money workflows from this discovery batch.\n",
        encoding="utf-8",
    )
    summary = ["# Active Sleeve Ensemble Discovery", "", f"Created at UTC: `{now_utc()}`", f"Lane id: `{LANE_ID}`", f"Rows tested: `{len(ENSEMBLE_ROWS)}`", f"Next action: `{next_action}`", ""]
    if payload["diagnostics_available"] and results:
        best = max(results, key=lambda row: float(row["180d_median_final_equity"]))
        summary.append(f"Best 180d median row: `{best['strategy_id']}` at `{best['180d_median_final_equity']}` with decision `{best['decision']}`.")
    else:
        summary.append("Diagnostics unavailable; repair outputs before using this lane.")
    summary.append("")
    summary.append("This is a bounded discovery packet for the six pre-registered rows only. It did not run candidate_exhaustive, paper-forward review/activation/checkpoint, provider download, broker/live-order, or real-money paths.")
    (output / "active_sleeve_ensemble_discovery_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    manifest = {
        "created_at_utc": now_utc(),
        "lane_id": LANE_ID,
        "lane_status": "discovery_completed",
        "output_dir": str(output),
        "rows_tested": ENSEMBLE_ROWS,
        "reference_ids": REFERENCE_IDS,
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "decisions": {row_id: details["decision"] for row_id, details in decisions.items()},
        "next_action": next_action,
        "state_notes": state_notes,
        "roadmap_status": roadmap_status,
        "strategy_discovery_run": True,
        "research_sample_run": True,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_download": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    write_json(output / "active_sleeve_ensemble_discovery_manifest.json", manifest)
    write_json(output / "active_sleeve_ensemble_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest, "results": results}


def run_active_sleeve_ensemble_discovery(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    obs_before = active_observation_hashes(root)
    core_before = protected_core_snapshot(registry_before)
    roadmap_status = ensure_roadmap_current_next_action(root)
    registry_before_after_roadmap = load_yaml(registry_path)
    mismatches = state_mismatches(root, registry_before_after_roadmap)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))

    payload = build_payload(root)
    decisions = decide_rows(payload)
    next_action = final_next_action(decisions, payload["diagnostics_available"])
    update_registry(root, decisions, next_action, root / OUTPUT_DIR)

    registry_after = load_yaml(registry_path)
    obs_after = active_observation_hashes(root)
    core_after = protected_core_snapshot(registry_after)

    equal_weight_matches = False
    if payload["diagnostics_available"]:
        equal_weight = payload["summaries"]["ase_vm_dsr_equal_weight_v1"][180]
        active_combo = payload["summaries"][combo.COMBO_ID][180]
        equal_weight_matches = abs(float(equal_weight["median_final_equity"]) - float(active_combo["median_final_equity"])) < 1e-9

    consistency = {
        "discovery_completed": payload["diagnostics_available"],
        "only_preregistered_rows_run": set(ENSEMBLE_ROWS) == set(preregistered_rows(root)),
        "no_extra_rows_added": len(ENSEMBLE_ROWS) == 6,
        "active_combo_used_as_reference": combo.COMBO_ID in REFERENCE_IDS,
        "ase_equal_weight_matches_active_combo": equal_weight_matches,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": obs_before == obs_after and core_before == core_after,
        "roadmap_next_action_consistent": roadmap_status["roadmap_next_action_consistent"],
        "final_next_action_explicit": next_action in {NEXT_ACTION_PROMOTION, NEXT_ACTION_WATCHLIST, NEXT_ACTION_ARCHIVE, NEXT_ACTION_REPAIR},
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())

    outputs = write_outputs(root, payload, decisions, next_action, consistency, mismatches, roadmap_status)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "rows_tested": ENSEMBLE_ROWS,
        "next_action": next_action,
        "decisions": {row_id: details["decision"] for row_id, details in decisions.items()},
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "roadmap_status": roadmap_status,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_active_sleeve_ensemble_discovery(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
