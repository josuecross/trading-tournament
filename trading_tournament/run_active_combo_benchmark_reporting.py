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

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "active_combo_benchmark" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
NEXT_ACTION_SUCCESS = "pre_register_active_sleeve_ensemble_lane"
NEXT_ACTION_INPUT_REPAIR = "repair_active_combo_inputs_before_new_research"
NEXT_ACTION_STALE_REPAIR = "repair_registry_stale_flags_before_new_research"
WEAKER_LABEL = "weaker_than_active_references_watchlist"
REFERENCE_IDS = [
    active.VM_ID,
    active.DSR_ID,
    COMBO_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
]


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


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def protected_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    protected: dict[str, dict[str, Any]] = {}
    metadata = {
        "active_combo_benchmark_path",
        "active_combo_reference_available",
        "current_permission_status",
        "historical_flag_only",
        "stale_flag_warning",
        "current_candidate_exhaustive_permission",
        "current_promotion_review_permission",
        "latest_checkpoint_path",
    }
    for row_id in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID]:
        row = deepcopy(rows.get(row_id, {}))
        for key in metadata:
            row.pop(key, None)
        protected[row_id] = row
    return protected


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(path) for strategy_id, path in active.active_observation_paths(root).items()}


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    rows = rows_by_id(registry)
    mismatches: list[str] = []
    meta = registry.get("registry", {})
    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    pipeline = read_csv_rows(checkpoint / "candidate_pipeline_status.csv")
    pipeline_by_stage = {row.get("stage", ""): row for row in pipeline}
    if meta.get("etf_discovery_status") != "paused":
        mismatches.append("ETF discovery is not paused in registry metadata")
    if not checkpoint.exists():
        mismatches.append("current research checkpoint path missing")
    for strategy_id in [active.VM_ID, active.DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
    if pipeline_by_stage.get("candidate_exhaustive_queue", {}).get("count") not in {"0", 0}:
        mismatches.append("candidate_exhaustive_queue is not empty")
    if pipeline_by_stage.get("promotion_review_candidates", {}).get("count") not in {"0", 0}:
        mismatches.append("promotion_review_candidates is not empty")
    if pipeline_by_stage.get("paper_forward_active", {}).get("count") not in {"2", 2}:
        mismatches.append("checkpoint protected paper-forward active count is not 2")
    for path in active.active_observation_paths(root).values():
        if not path.exists():
            mismatches.append(f"active observation missing: {path}")
    return mismatches


def sleeve_daily_return(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    return active.weighted_return(weights, active.daily_asset_returns(close, today, set(weights)))


def combo_window(close: pd.DataFrame, start: int, horizon: int) -> dict[str, Any]:
    vm_value = active.STARTING_EQUITY * 0.5
    dsr_value = active.STARTING_EQUITY * 0.5
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
            total = vm_value + dsr_value
            vm_value = total * 0.5
            dsr_value = total * 0.5
            new_vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            new_dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            vm_value = active.apply_rebalance_cost(vm_value, active.rebalance_turnover_units(new_vm_weights, vm_weights))
            dsr_value = active.apply_rebalance_cost(dsr_value, active.rebalance_turnover_units(new_dsr_weights, dsr_weights))
            vm_weights = new_vm_weights
            dsr_weights = new_dsr_weights
            last_month = month
        vm_ret, vm_weights, _vm_cost = active.portfolio_step(close, today, vm_weights)
        dsr_ret, dsr_weights, _dsr_cost = active.portfolio_step(close, today, dsr_weights)
        vm_value *= 1.0 + vm_ret
        dsr_value *= 1.0 + dsr_ret
        equity = vm_value + dsr_value
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
        "strategy_id": COMBO_ID,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": vm_value + dsr_value,
        "profit_dollars": vm_value + dsr_value - active.STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def run_windows(close: pd.DataFrame, strategy_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        for start in active.sample_starts(close, horizon):
            if strategy_id == COMBO_ID:
                rows.append(combo_window(close, start, horizon))
            else:
                rows.append(active.simulate(close, start, horizon, strategy_id))
    return rows


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    return active.summarize(rows, strategy_id, horizon)


def full_equity_series(close: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    vm_value = active.STARTING_EQUITY * 0.5
    dsr_value = active.STARTING_EQUITY * 0.5
    vm_standalone = active.STARTING_EQUITY
    dsr_standalone = active.STARTING_EQUITY
    last_month = None
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    vm_standalone_weights: dict[str, float] = {}
    dsr_standalone_weights: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(253, len(close)):
        signal = today - 1
        month = int(months[today])
        vm_cost_return = 0.0
        dsr_cost_return = 0.0
        vm_turnover = 0.0
        dsr_turnover = 0.0
        if month != last_month:
            total = vm_value + dsr_value
            vm_value = total * 0.5
            dsr_value = total * 0.5
            new_vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            new_dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            vm_turnover = active.rebalance_turnover_units(new_vm_weights, vm_weights)
            dsr_turnover = active.rebalance_turnover_units(new_dsr_weights, dsr_weights)
            vm_standalone_turnover = active.rebalance_turnover_units(new_vm_weights, vm_standalone_weights)
            dsr_standalone_turnover = active.rebalance_turnover_units(new_dsr_weights, dsr_standalone_weights)
            vm_cost_return = vm_turnover * active.SLIPPAGE
            dsr_cost_return = dsr_turnover * active.SLIPPAGE
            vm_value = active.apply_rebalance_cost(vm_value, vm_turnover)
            dsr_value = active.apply_rebalance_cost(dsr_value, dsr_turnover)
            vm_standalone = active.apply_rebalance_cost(vm_standalone, vm_standalone_turnover)
            dsr_standalone = active.apply_rebalance_cost(dsr_standalone, dsr_standalone_turnover)
            vm_weights = new_vm_weights
            dsr_weights = new_dsr_weights
            vm_standalone_weights = new_vm_weights.copy()
            dsr_standalone_weights = new_dsr_weights.copy()
            allocations.append(
                {
                    "rebalance_date": str(close.index[today].date()),
                    "combo_id": COMBO_ID,
                    "vm_sleeve_weight": 0.5,
                    "dsr_sleeve_weight": 0.5,
                    "vm_sleeve_value_after_rebalance": round(vm_value, 4),
                    "dsr_sleeve_value_after_rebalance": round(dsr_value, 4),
                    "vm_internal_turnover_units": round(vm_turnover, 8),
                    "dsr_internal_turnover_units": round(dsr_turnover, 8),
                    "vm_internal_cost_return": round(vm_cost_return, 10),
                    "dsr_internal_cost_return": round(dsr_cost_return, 10),
                    "vm_holdings": json.dumps({k: round(v, 6) for k, v in sorted(vm_weights.items())}, sort_keys=True),
                    "dsr_holdings": json.dumps({k: round(v, 6) for k, v in sorted(dsr_weights.items())}, sort_keys=True),
                }
            )
            last_month = month
        vm_ret, vm_weights, _vm_step_cost = active.portfolio_step(close, today, vm_weights)
        dsr_ret, dsr_weights, _dsr_step_cost = active.portfolio_step(close, today, dsr_weights)
        vm_standalone_ret, vm_standalone_weights, _vm_standalone_cost = active.portfolio_step(close, today, vm_standalone_weights)
        dsr_standalone_ret, dsr_standalone_weights, _dsr_standalone_cost = active.portfolio_step(close, today, dsr_standalone_weights)
        vm_value *= 1.0 + vm_ret
        dsr_value *= 1.0 + dsr_ret
        vm_standalone *= 1.0 + vm_standalone_ret
        dsr_standalone *= 1.0 + dsr_standalone_ret
        combo_equity = vm_value + dsr_value
        rows.append(
            {
                "date": str(close.index[today].date()),
                "active_combo_equity": round(combo_equity, 6),
                "vm_sleeve_equity": round(vm_value, 6),
                "dsr_sleeve_equity": round(dsr_value, 6),
                "vm_standalone_equity": round(vm_standalone, 6),
                "dsr_standalone_equity": round(dsr_standalone, 6),
                "active_combo_daily_return": "",
                "vm_sleeve_daily_return": round(vm_ret, 10),
                "dsr_sleeve_daily_return": round(dsr_ret, 10),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        combo_returns = frame["active_combo_equity"].astype(float).pct_change()
        frame["active_combo_daily_return"] = combo_returns.round(10).fillna("")
    return frame, allocations


def returns_from_equity(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(frame["date"])
    return pd.Series(pd.to_numeric(frame[column], errors="coerce").values, index=dates).pct_change().dropna()


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def fmt(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def risk_buffer(summary: dict[str, Any]) -> float | str:
    if "worst_drawdown" not in summary:
        return "unavailable"
    return float(summary["worst_drawdown"]) - active.STOP_DOLLARS


def build_payload(root: Path) -> dict[str, Any]:
    close, missing = active.prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "close": close}
    ids = REFERENCE_IDS
    window_rows = {strategy_id: run_windows(close, strategy_id) for strategy_id in ids}
    summaries = {strategy_id: {h: summarize(window_rows[strategy_id], strategy_id, h) for h in active.HORIZONS} for strategy_id in ids}
    equity_frame, allocations = full_equity_series(close)
    returns = {
        active.VM_ID: active.full_returns(close, active.VM_ID),
        active.DSR_ID: active.full_returns(close, active.DSR_ID),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        "SPY_buy_hold": active.full_returns(close, "SPY_buy_hold"),
        "QQQ_buy_hold": active.full_returns(close, "QQQ_buy_hold"),
        "BIL_cash_proxy": active.full_returns(close, "BIL_cash_proxy"),
        COMBO_ID: returns_from_equity(equity_frame, "active_combo_equity"),
    }
    return {
        "diagnostics_available": True,
        "missing_symbols": [],
        "close": close,
        "window_rows": window_rows,
        "summaries": summaries,
        "equity_frame": equity_frame,
        "allocations": allocations,
        "returns": returns,
    }


def metric_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    s90 = payload["summaries"][COMBO_ID][90]
    s180 = payload["summaries"][COMBO_ID][180]
    metrics = [
        ("90d_median_final_equity", s90.get("median_final_equity"), 90),
        ("180d_median_final_equity", s180.get("median_final_equity"), 180),
        ("180d_mean_final_equity", s180.get("mean_final_equity"), 180),
        ("180d_p75_final_equity", s180.get("p75_final_equity"), 180),
        ("180d_p90_final_equity", s180.get("p90_final_equity"), 180),
        ("best_final_equity", s180.get("best_final_equity"), 180),
        ("worst_final_equity", s180.get("worst_final_equity"), 180),
        ("target_300_before_stop_rate", s180.get("target_300_before_stop_rate"), 180),
        ("target_400_before_stop_rate", s180.get("target_400_before_stop_rate"), 180),
        ("180d_worst_drawdown", s180.get("worst_drawdown"), 180),
        ("stop_hit_rate", s180.get("stop_hit_rate"), 180),
        ("risk_buffer_vs_minus_600", risk_buffer(s180), 180),
        ("corr_vs_active_vm", corr(payload["returns"], COMBO_ID, active.VM_ID), "full_series"),
        ("corr_vs_active_dsr", corr(payload["returns"], COMBO_ID, active.DSR_ID), "full_series"),
        ("corr_vs_spy_200d", corr(payload["returns"], COMBO_ID, active.SPY_200D_ID), "full_series"),
    ]
    rows = [{"benchmark_id": COMBO_ID, "metric": metric, "value": fmt(value), "horizon": horizon, "notes": "deterministic active combo benchmark"} for metric, value, horizon in metrics]
    for ref in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]:
        delta = s180["median_final_equity"] - payload["summaries"][ref][180]["median_final_equity"]
        rows.append({"benchmark_id": COMBO_ID, "metric": f"delta_vs_{ref}", "value": fmt(delta), "horizon": 180, "notes": "180d median final equity delta"})
    return rows


def component_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    combo = payload["summaries"][COMBO_ID][180]
    rows: list[dict[str, Any]] = []
    for ref in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]:
        ref_summary = payload["summaries"][ref][180]
        rows.append(
            {
                "reference_id": ref,
                "combo_180d_median_final_equity": fmt(combo["median_final_equity"]),
                "reference_180d_median_final_equity": fmt(ref_summary["median_final_equity"]),
                "delta": fmt(combo["median_final_equity"] - ref_summary["median_final_equity"]),
                "correlation": fmt(corr(payload["returns"], COMBO_ID, ref)),
                "comparison_status": "computed",
            }
        )
    return rows


def delta_reference_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    combo = payload["summaries"][COMBO_ID][180]
    rows: list[dict[str, Any]] = []
    for ref in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]:
        ref_summary = payload["summaries"][ref][180]
        rows.append(
            {
                "benchmark_id": COMBO_ID,
                "reference_id": ref,
                "benchmark_180d_median_final_equity": fmt(combo["median_final_equity"]),
                "reference_180d_median_final_equity": fmt(ref_summary["median_final_equity"]),
                "delta": fmt(combo["median_final_equity"] - ref_summary["median_final_equity"]),
                "comparison_status": "computed",
                "missing_reason": "",
            }
        )
    return rows


def target_window_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    return [
        {
            "benchmark_id": COMBO_ID,
            "horizon": row["horizon"],
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "target_300_before_stop": row["target_300_before_stop"],
            "target_400_before_stop": row["target_400_before_stop"],
            "absolute_600_stop_hit": row["absolute_600_stop_hit"],
            "final_equity": fmt(row["final_equity"]),
        }
        for row in payload["window_rows"][COMBO_ID]
    ]


def drawdown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    return [
        {
            "benchmark_id": COMBO_ID,
            "horizon": row["horizon"],
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "max_drawdown": fmt(row["max_drawdown"]),
            "profit_dollars": fmt(row["profit_dollars"]),
        }
        for row in payload["window_rows"][COMBO_ID]
    ]


def registry_stale_flag_rows(registry: dict[str, Any], checkpoint_path: Path) -> list[dict[str, Any]]:
    rows = []
    checkpoint_manifest = json.loads((checkpoint_path / "current_research_checkpoint_manifest.json").read_text(encoding="utf-8")) if (checkpoint_path / "current_research_checkpoint_manifest.json").exists() else {}
    checkpoint_stale = set(checkpoint_manifest.get("stale_candidate_exhaustive_flags", [])) | set(checkpoint_manifest.get("stale_promotion_review_flags", []))
    watched = {"gror_balanced_momentum_60_40_v1"} | checkpoint_stale
    for row in registry.get("strategies", []):
        sid = str(row.get("id", ""))
        flags = []
        if row.get("candidate_exhaustive_recommended") is True:
            flags.append(("candidate_exhaustive_recommended", True))
        if row.get("promotion_review_required") is True:
            flags.append(("promotion_review_required", True))
        if row.get("status") in {"promotion_review_candidate", "candidate_exhaustive_queue", "deferred_candidate_queue"}:
            flags.append(("status", row.get("status")))
        if sid in watched or flags:
            for field, val in flags or [("checkpoint_watch", "historical_residue")]:
                rows.append(
                    {
                        "strategy_id": sid,
                        "stale_field": field,
                        "stale_value": val,
                        "current_checkpoint_status": "not_current_candidate",
                        "should_be_current_permission": False,
                        "recommended_registry_action": "mark_historical_flag_only_and_block_current_permission",
                        "notes": "Checkpoint says promotion and candidate_exhaustive queues are empty.",
                    }
                )
    return rows


def update_registry_hygiene(root: Path, stale_rows: list[dict[str, Any]]) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    stale_ids = {row["strategy_id"] for row in stale_rows}
    for row in registry.get("strategies", []):
        if row.get("id") in stale_ids:
            row["current_permission_status"] = "not_current_candidate"
            row["historical_flag_only"] = True
            row["stale_flag_warning"] = "Historical flag retained for audit; current checkpoint grants no promotion/candidate_exhaustive permission."
            row["current_candidate_exhaustive_permission"] = False
            row["current_promotion_review_permission"] = False
            row["latest_checkpoint_path"] = str(root / "evidence" / "current_research_checkpoint" / "latest")
    meta = registry.setdefault("registry", {})
    meta["active_combo_benchmark_path"] = str(root / OUTPUT_DIR)
    meta["active_combo_reference_available"] = True
    meta["next_engineering_action"] = "none_active_combo_repaired"
    meta["next_research_action_after_engineering"] = NEXT_ACTION_SUCCESS
    meta["no_candidate_exhaustive_run"] = True
    meta["no_paper_forward_action"] = True
    meta["no_real_money_recommendation"] = True
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def create_packet(output: Path) -> Path:
    packet = output / "active_combo_benchmark_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, payload: dict[str, Any], stale_rows: list[dict[str, Any]], consistency: dict[str, Any], state_notes: list[str], next_action: str) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    definition = {
        "benchmark_id": COMBO_ID,
        "role": "benchmark_reference_only",
        "starting_equity": active.STARTING_EQUITY,
        "rebalance": "monthly",
        "sleeves": [
            {"strategy_id": active.VM_ID, "allocation": 0.5, "rule_source": "frozen_active_rule_reconstruction"},
            {"strategy_id": active.DSR_ID, "allocation": 0.5, "rule_source": "frozen_active_rule_reconstruction"},
        ],
        "forbidden": ["leverage", "margin", "shorting", "broker_integration", "live_orders", "real_money_recommendation"],
        "notes": "Reference benchmark only; not an active strategy and not paper-forward activation.",
    }
    (output / "active_combo_benchmark_definition.yaml").write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")
    if payload["diagnostics_available"]:
        payload["equity_frame"].to_csv(output / "active_combo_equity_series.csv", index=False)
        write_csv(output / "active_combo_monthly_allocations.csv", payload["allocations"], ["rebalance_date", "combo_id", "vm_sleeve_weight", "dsr_sleeve_weight", "vm_sleeve_value_after_rebalance", "dsr_sleeve_value_after_rebalance", "vm_holdings", "dsr_holdings"])
    else:
        write_csv(output / "active_combo_equity_series.csv", [], ["date", "active_combo_equity", "vm_sleeve_equity", "dsr_sleeve_equity", "vm_standalone_equity", "dsr_standalone_equity", "active_combo_daily_return", "vm_sleeve_daily_return", "dsr_sleeve_daily_return"])
        write_csv(output / "active_combo_monthly_allocations.csv", [], ["rebalance_date", "combo_id", "vm_sleeve_weight", "dsr_sleeve_weight", "vm_sleeve_value_after_rebalance", "dsr_sleeve_value_after_rebalance", "vm_holdings", "dsr_holdings"])
    write_csv(output / "active_combo_benchmark_metrics.csv", metric_rows(payload), ["benchmark_id", "metric", "value", "horizon", "notes"])
    write_csv(output / "active_combo_component_comparison.csv", component_rows(payload), ["reference_id", "combo_180d_median_final_equity", "reference_180d_median_final_equity", "delta", "correlation", "comparison_status"])
    write_csv(output / "active_combo_benchmark_delta_reference.csv", delta_reference_rows(payload), ["benchmark_id", "reference_id", "benchmark_180d_median_final_equity", "reference_180d_median_final_equity", "delta", "comparison_status", "missing_reason"])
    write_csv(output / "active_combo_target_window_review.csv", target_window_rows(payload), ["benchmark_id", "horizon", "window_start", "window_end", "target_300_before_stop", "target_400_before_stop", "absolute_600_stop_hit", "final_equity"])
    write_csv(output / "active_combo_drawdown_review.csv", drawdown_rows(payload), ["benchmark_id", "horizon", "window_start", "window_end", "max_drawdown", "profit_dollars"])
    write_csv(output / "active_combo_rebalance_trace.csv", (payload["allocations"][:36] if payload["diagnostics_available"] else []), ["rebalance_date", "combo_id", "vm_sleeve_weight", "dsr_sleeve_weight", "vm_sleeve_value_after_rebalance", "dsr_sleeve_value_after_rebalance", "vm_holdings", "dsr_holdings"])
    write_csv(output / "registry_stale_flag_audit.csv", stale_rows, ["strategy_id", "stale_field", "stale_value", "current_checkpoint_status", "should_be_current_permission", "recommended_registry_action", "notes"])
    missing_lines = ["# Active Combo Missing Evidence", ""]
    if payload["missing_symbols"]:
        missing_lines.append("Missing required cached symbols: " + ", ".join(payload["missing_symbols"]))
    else:
        missing_lines.append("No required cached symbols are missing for the active-combo benchmark reconstruction.")
    missing_lines.append("Unavailable comparisons must remain marked unavailable and must not be zero-filled.")
    (output / "active_combo_missing_evidence.md").write_text("\n".join(missing_lines) + "\n", encoding="utf-8")
    integration = f"""# Active Combo Reporting Integration

- `{COMBO_ID}` is now emitted as a benchmark/reference series under `{root / OUTPUT_DIR}`.
- It is not an active paper-forward strategy and does not activate any paper-forward workflow.
- Dashboard and advisor packet builders now read the active-combo manifest when present.
- Future benchmark delta exports should use `active_combo_benchmark_delta_reference.csv` or the reusable `active_combo_equity_series.csv`.
- Missing comparisons must be reported as `unavailable`, not zero-filled.
"""
    (output / "active_combo_reporting_integration.md").write_text(integration, encoding="utf-8")
    taxonomy = f"""# Decision Taxonomy Review

`{WEAKER_LABEL}` is allowed for future reporting when benchmark deltas exist and a row is weaker than active VM, active DSR, active combo, SPY_200d, SPY, or QQQ but remains diagnostically useful.

Do not rerun old batches solely to relabel historical decisions. Historical `needs_benchmark_delta_review` labels should remain historical unless their original evidence is being regenerated for another approved reason.
"""
    (output / "decision_taxonomy_review.md").write_text(taxonomy, encoding="utf-8")
    (output / "active_combo_next_action.md").write_text(f"# Active Combo Next Action\n\n`{next_action}`\n\nDo not run strategy discovery directly without pre-registration.\n", encoding="utf-8")
    summary = ["# Active Combo Benchmark", "", f"Created at UTC: `{now_utc()}`", f"Benchmark id: `{COMBO_ID}`", "Definition: 50% active VM sleeve / 50% active DSR sleeve, monthly rebalanced.", f"Next action: `{next_action}`", ""]
    if payload["diagnostics_available"]:
        s = payload["summaries"][COMBO_ID][180]
        summary.append(f"180d median final equity: `{fmt(s['median_final_equity'])}`")
        summary.append(f"180d worst drawdown: `{fmt(s['worst_drawdown'])}`")
        summary.append(f"Stop-hit rate: `{fmt(s['stop_hit_rate'])}`")
    else:
        summary.append("Diagnostics unavailable due missing cached inputs.")
    summary.append("")
    summary.append("Reference benchmark only; no active observation mutation, paper-forward activation, broker/live-order path, provider download, or real-money recommendation.")
    (output / "active_combo_benchmark_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest = {
        "created_at_utc": now_utc(),
        "benchmark_id": COMBO_ID,
        "portfolio_accounting_method": "monthly 50/50 VM/DSR sleeve targets; sleeve values drift between combo rebalances; component holdings drift between component rebalances",
        "component_turnover_basis": "sum(abs(new component target weight - pre-trade actual component weight)) using active recompute convention",
        "combo_level_cost_basis": "no separate combo-level cost in frozen benchmark definition; component-level costs are included",
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "active_combo_benchmark_created": payload["diagnostics_available"],
        "active_combo_reference_available": payload["diagnostics_available"],
        "next_action": next_action,
        "state_notes": state_notes,
        "strategy_discovery_run": False,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_download": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "active_combo_is_reference_not_active_strategy": True,
    }
    write_json(output / "active_combo_manifest.json", manifest)
    write_json(output / "active_combo_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest}


def run_active_combo_benchmark_reporting(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    core_before = protected_snapshot(registry_before)
    obs_before = active_observation_hashes(root)
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    payload = build_payload(root)
    stale_rows = registry_stale_flag_rows(registry_before, root / "evidence" / "current_research_checkpoint" / "latest")
    next_action = NEXT_ACTION_INPUT_REPAIR if not payload["diagnostics_available"] else NEXT_ACTION_SUCCESS
    update_registry_hygiene(root, stale_rows)
    registry_after = load_yaml(registry_path)
    core_after = protected_snapshot(registry_after)
    obs_after = active_observation_hashes(root)
    consistency = {
        "active_combo_benchmark_created": payload["diagnostics_available"],
        "active_combo_definition_created": True,
        "active_combo_series_created": payload["diagnostics_available"],
        "active_combo_is_reference_not_active_strategy": True,
        "reporting_integration_completed": True,
        "stale_flag_audit_created": bool(stale_rows),
        "stale_flags_do_not_grant_current_permission": all(row["should_be_current_permission"] is False for row in stale_rows),
        "decision_taxonomy_review_created": True,
        "no_strategy_discovery_run": True,
        "no_research_sample_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": obs_before == obs_after and core_before == core_after,
        "next_action_explicit": bool(next_action),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, payload, stale_rows, consistency, mismatches, next_action)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "benchmark_id": COMBO_ID,
        "next_action": next_action,
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "stale_flag_count": len(stale_rows),
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_active_combo_benchmark_reporting(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
