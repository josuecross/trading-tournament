from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import (
    invariant_summary,
    load_local_price_frame,
    reference_spy200d_weights,
    returns_from_weights,
)
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


OUTPUT_DIR = Path("evidence") / "public_source_comparative_screening_batch_v1" / "latest"
ACTIVE_COMBO_SERIES = Path("evidence") / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
ACTIVE_COMBO_MANIFEST = (
    Path("evidence") / "active_combo_series_reconciliation" / "latest" / "active_combo_series_reconciliation.json"
)
ACTIVE_COMBO_CONSISTENCY = (
    Path("evidence") / "active_combo_series_reconciliation" / "latest" / "reconciliation_consistency_check.json"
)
SCREENING_BATCH_ID = "public_source_comparative_screening_batch_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
SPY200D_ID = "SPY_200d_trend_model"
SPY_BUY_HOLD_ID = "SPY_buy_hold"
BIL_ID = "BIL_cash_proxy"
NEXT_ACTION = "direction_owner_review_public_source_comparative_screening_batch_v1"

INCLUDED_LANE_IDS = (
    "public_source_adx_dmi_bounded_bt_lane_v1",
    "public_source_cci_correction_bounded_bt_lane_v1",
    "public_source_coppock_curve_bounded_bt_lane_v1",
    "public_source_larry_connors_rsi2_bounded_bt_lane_v1",
    "public_source_parabolic_sar_bounded_bt_lane_v1",
    "public_source_percent_b_money_flow_bounded_bt_lane_v1",
)
EXCLUDED_PUBLIC_SOURCE_IDS = (
    "bollinger_band_squeeze_breakout",
    "golden_cross_50_200",
    "low_volatility_factor_proxy",
    "macd_stochastic_double_cross",
    "sector_momentum_rotational_system",
    "sell_in_may_halloween_effect",
)


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    module_name: str
    implementation_path: Path
    runner_path: Path


LANES: tuple[LaneSpec, ...] = (
    LaneSpec(
        "public_source_adx_dmi_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_adx_dmi_bounded_bt_run.py",
        Path("run_public_source_adx_dmi_bounded_bt_lane.py"),
    ),
    LaneSpec(
        "public_source_cci_correction_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_cci_correction_bounded_bt_run.py",
        Path("run_public_source_cci_correction_bounded_bt_lane.py"),
    ),
    LaneSpec(
        "public_source_coppock_curve_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_coppock_curve_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_coppock_curve_bounded_bt_run.py",
        Path("run_public_source_coppock_curve_bounded_bt_lane.py"),
    ),
    LaneSpec(
        "public_source_larry_connors_rsi2_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_larry_connors_rsi2_bounded_bt_run.py",
        Path("run_public_source_larry_connors_rsi2_bounded_bt_lane.py"),
    ),
    LaneSpec(
        "public_source_parabolic_sar_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_parabolic_sar_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_parabolic_sar_bounded_bt_run.py",
        Path("run_public_source_parabolic_sar_bounded_bt_lane.py"),
    ),
    LaneSpec(
        "public_source_percent_b_money_flow_bounded_bt_lane_v1",
        "strategy_lab.research_os.research.public_source_percent_b_money_flow_bounded_bt_run",
        Path("strategy_lab") / "research_os" / "research" / "public_source_percent_b_money_flow_bounded_bt_run.py",
        Path("run_public_source_percent_b_money_flow_bounded_bt_lane.py"),
    ),
)

OUTCOME_LABELS = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "control_weak",
    "no_material_edge",
    "not_comparable",
    "invalid_methodology",
    "implementation_blocked",
    "direction_owner_review_required",
}
FAILURE_PATTERNS = {
    "none",
    "insufficient_return",
    "excess_drawdown",
    "weak_versus_spy_control",
    "weak_versus_active_combo_benchmark",
    "too_few_signals",
    "excess_turnover_or_cost_sensitivity",
    "window_instability",
    "missing_data_dependence",
    "methodology_or_implementation_failure",
    "non_comparability",
    "duplicate_economic_behavior",
    "direction_owner_review_required",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_data(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fmt(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "" if value is None else str(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.6f}".rstrip("0").rstrip(".")


def date_text(date: Any) -> str:
    return pd.Timestamp(date).date().isoformat()


def design_files(module: Any) -> list[Path]:
    design_dir = getattr(module, "DESIGN_DIR", None)
    if not design_dir:
        return []
    base = ROOT / design_dir
    return sorted(path for path in base.glob("*") if path.is_file()) if base.exists() else []


def design_hash(module: Any) -> str:
    files = design_files(module)
    return hash_data({str(path.relative_to(ROOT)).replace("\\", "/"): file_hash(path) for path in files})


def cache_identity(root: Path) -> dict[str, Any]:
    paths = [root / "data" / "cache" / "SPY.csv", root / "data" / "cache" / "BIL.csv", root / ACTIVE_COMBO_SERIES]
    return {
        "cache_files": [
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "exists": path.exists(),
                "hash": file_hash(path),
            }
            for path in paths
        ],
        "identity_hash": hash_data({str(path.relative_to(root)).replace("\\", "/"): file_hash(path) for path in paths}),
    }


def load_active_combo_returns(root: Path) -> pd.Series:
    path = root / ACTIVE_COMBO_SERIES
    if not path.exists():
        return pd.Series(dtype=float, name=ACTIVE_COMBO_ID)
    frame = pd.read_csv(path)
    if "date" not in frame or "active_combo_daily_return" not in frame:
        return pd.Series(dtype=float, name=ACTIVE_COMBO_ID)
    dates = pd.to_datetime(frame["date"], errors="coerce")
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    out = pd.DataFrame({"date": dates, ACTIVE_COMBO_ID: returns}).dropna().sort_values("date")
    return out.set_index("date")[ACTIVE_COMBO_ID].astype(float)


def benchmark_returns(root: Path) -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame]]:
    prices = load_local_price_frame(root).sort_index()
    if prices.empty:
        return {}, {}
    prices = prices.loc[prices[["SPY", "BIL"]].notna().all(axis=1), ["SPY", "BIL"]].copy()
    weights: dict[str, pd.DataFrame] = {
        SPY_BUY_HOLD_ID: pd.DataFrame({"SPY": 1.0, "BIL": 0.0}, index=prices.index),
        BIL_ID: pd.DataFrame({"SPY": 0.0, "BIL": 1.0}, index=prices.index),
        SPY200D_ID: reference_spy200d_weights(prices).reindex(columns=["SPY", "BIL"], fill_value=0.0),
    }
    returns = {benchmark_id: returns_from_weights(prices, frame).rename(benchmark_id) for benchmark_id, frame in weights.items()}
    combo = load_active_combo_returns(root)
    if not combo.empty:
        returns[ACTIVE_COMBO_ID] = combo
    return returns, weights


def load_lane(spec: LaneSpec) -> Any:
    module = importlib.import_module(spec.module_name)
    if getattr(module, "LANE_ID", "") != spec.lane_id:
        raise RuntimeError(f"lane id mismatch for {spec.module_name}")
    return module


def lane_lineage(root: Path, spec: LaneSpec, module: Any) -> dict[str, Any]:
    design = design_files(module)
    return {
        "lane_id": spec.lane_id,
        "source_id": getattr(module, "SOURCE_ID", "unknown"),
        "family_id": getattr(module, "FAMILY_ID", "unknown"),
        "implementation_path": str(spec.implementation_path).replace("\\", "/"),
        "implementation_hash": file_hash(root / spec.implementation_path),
        "runner_path": str(spec.runner_path).replace("\\", "/"),
        "runner_hash": file_hash(root / spec.runner_path),
        "configuration_or_rule_reference": str(getattr(module, "DESIGN_DIR", "unknown")).replace("\\", "/"),
        "configuration_hash": design_hash(module),
        "expected_variant_ids": list(getattr(module, "EXPECTED_VARIANTS", ())),
        "standard_cost_assumption": getattr(module, "STANDARD_COST_ASSUMPTION", "unknown"),
        "signal_execution_timing": "completed signal bar; project one-bar shifted-weight execution convention",
        "design_files": [str(path.relative_to(root)).replace("\\", "/") for path in design],
    }


def preregistration_payload(root: Path, modules: dict[str, Any], common_index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    cache = cache_identity(root)
    windows: list[dict[str, Any]] = []
    if common_index is not None and len(common_index) > max(active.HORIZONS, default=0) + 252:
        dummy = pd.DataFrame({"dummy": np.arange(len(common_index), dtype=float)}, index=common_index)
        for horizon in active.HORIZONS:
            for start in active.sample_starts(dummy, horizon):
                windows.append(
                    {
                        "horizon": horizon,
                        "start_index": start,
                        "window_start": date_text(common_index[start]),
                        "window_end": date_text(common_index[start + horizon]),
                    }
                )
    return {
        "batch_id": SCREENING_BATCH_ID,
        "frozen_screening_manifest": True,
        "included_lane_ids": list(INCLUDED_LANE_IDS),
        "excluded_public_source_ids": list(EXCLUDED_PUBLIC_SOURCE_IDS),
        "implementation_lineage": [lane_lineage(root, spec, modules[spec.lane_id]) for spec in LANES],
        "dataset_cache_identity": cache,
        "evaluation_windows": windows,
        "initial_capital": active.STARTING_EQUITY,
        "stop_dollars": active.STOP_DOLLARS,
        "horizons": active.HORIZONS,
        "max_windows_per_horizon": active.MAX_WINDOWS_PER_HORIZON,
        "cost_slippage_assumptions": {
            "sampled_window_protocol_source": "run_active_strategy_evidence_recompute.py",
            "active_strategy_protocol_slippage": active.SLIPPAGE,
            "public_source_lane_daily_return_costs": "existing frozen lane standard cost assumptions; no added batch-level costs",
        },
        "signal_and_execution_timing": "lane modules compute completed-bar signals; returns use project shifted-weight convention",
        "benchmarks": [SPY200D_ID, SPY_BUY_HOLD_ID, BIL_ID, ACTIVE_COMBO_ID],
        "active_combo_role": "benchmark_reference_only",
        "active_combo_status": "benchmark_watchlist_reference",
        "metrics": [
            "180d_median_final_equity",
            "target_300_before_stop_rate",
            "target_400_before_stop_rate",
            "worst_drawdown_dollars",
            "worst_drawdown_pct",
            "stop_hit_rate",
            "maximum_exposure",
            "average_exposure",
            "turnover",
            "trade_or_allocation_change_count",
            "percentage_time_invested",
            "benchmark_relative_final_equity_delta",
            "benchmark_relative_drawdown_delta",
            "valid_window_count",
            "invalid_window_count",
        ],
        "screening_rules": {
            "classification_rule_source": "existing lane numeric_criteria_pass plus sign-only same-window benchmark deltas; no new magnitude thresholds",
            "fallback_without_explicit_rule": "direction_owner_review_required",
        },
        "parameter_search": False,
        "parameter_selection_from_results": False,
        "new_strategy_variants_created": False,
    }


def preregistration_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tuple(payload.get("included_lane_ids", [])) != INCLUDED_LANE_IDS:
        errors.append("included lane set mismatch")
    if payload.get("parameter_search") is not False or payload.get("parameter_selection_from_results") is not False:
        errors.append("parameter search flag is not false")
    for row in payload.get("implementation_lineage", []):
        if row.get("implementation_hash") == "missing":
            errors.append(f"implementation missing: {row.get('lane_id')}")
        if row.get("configuration_hash", "").endswith("44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"):
            errors.append(f"empty configuration hash: {row.get('lane_id')}")
    if not payload.get("evaluation_windows"):
        errors.append("evaluation windows missing")
    if payload.get("active_combo_role") != "benchmark_reference_only":
        errors.append("active combo role is not benchmark_reference_only")
    return errors


def evaluate_frozen_lanes(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    lanes: dict[str, dict[str, Any]] = {}
    lineage_rows: list[dict[str, Any]] = []
    for spec in LANES:
        module = load_lane(spec)
        lineage = lane_lineage(root, spec, module)
        lineage_rows.append(lineage)
        try:
            evaluated = module.evaluate_lane(root)
            result_rows = evaluated[0]
            weights_by_variant = evaluated[1]
            returns_by_variant = evaluated[2]
            preflight = evaluated[-1]
            primary = next((row for row in result_rows if row.get("variant_role") == "source_primary"), None)
            if primary is None:
                lanes[spec.lane_id] = {
                    "lineage": lineage,
                    "blocked": True,
                    "blocker": "source_primary_row_missing",
                    "result_rows": result_rows,
                    "primary_row": {},
                    "weights": pd.DataFrame(),
                    "returns": pd.Series(dtype=float),
                    "preflight": preflight if isinstance(preflight, dict) else {},
                }
                continue
            variant_id = primary["variant_id"]
            lanes[spec.lane_id] = {
                "lineage": lineage,
                "blocked": False,
                "blocker": "",
                "result_rows": result_rows,
                "primary_row": primary,
                "weights": weights_by_variant.get(variant_id, pd.DataFrame()),
                "returns": returns_by_variant.get(variant_id, pd.Series(dtype=float)).rename(spec.lane_id),
                "preflight": preflight if isinstance(preflight, dict) else {},
            }
        except Exception as exc:
            lanes[spec.lane_id] = {
                "lineage": lineage,
                "blocked": True,
                "blocker": f"implementation_exception:{type(exc).__name__}:{exc}",
                "result_rows": [],
                "primary_row": {},
                "weights": pd.DataFrame(),
                "returns": pd.Series(dtype=float),
                "preflight": {},
            }
    return lanes, lineage_rows


def common_scored_index(lanes: dict[str, dict[str, Any]], benchmarks: dict[str, pd.Series]) -> pd.DatetimeIndex:
    indexes: list[pd.DatetimeIndex] = []
    for lane in lanes.values():
        if not lane["blocked"] and not lane["returns"].empty:
            indexes.append(pd.DatetimeIndex(lane["returns"].dropna().index))
    for returns in benchmarks.values():
        if not returns.empty:
            indexes.append(pd.DatetimeIndex(returns.dropna().index))
    if not indexes:
        return pd.DatetimeIndex([])
    common = indexes[0]
    for index in indexes[1:]:
        common = common.intersection(index)
    return pd.DatetimeIndex(sorted(common))


def window_result_rows(strategy_id: str, daily_returns: pd.Series, common_index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    aligned = daily_returns.reindex(common_index)
    rows: list[dict[str, Any]] = []
    dummy = pd.DataFrame({"dummy": np.arange(len(common_index), dtype=float)}, index=common_index)
    for horizon in active.HORIZONS:
        for start in active.sample_starts(dummy, horizon):
            period = aligned.iloc[start + 1 : start + horizon + 1]
            if len(period) != horizon or period.isna().any():
                rows.append(
                    {
                        "strategy_id": strategy_id,
                        "horizon": horizon,
                        "window_start": date_text(common_index[start]),
                        "window_end": date_text(common_index[start + horizon]),
                        "window_valid": False,
                        "invalid_reason": "missing_daily_return_inside_window",
                    }
                )
                continue
            equity = active.STARTING_EQUITY * (1.0 + period.fillna(0.0)).cumprod()
            peak = equity.cummax()
            drawdown_dollars = equity - peak
            drawdown_pct = equity / peak - 1.0
            profit = equity - active.STARTING_EQUITY
            stop_hits = np.flatnonzero((profit <= active.STOP_DOLLARS).to_numpy())
            target300_hits = np.flatnonzero((profit >= 300.0).to_numpy())
            target400_hits = np.flatnonzero((profit >= 400.0).to_numpy())
            stop = int(stop_hits[0]) if len(stop_hits) else None
            target300 = int(target300_hits[0]) if len(target300_hits) else None
            target400 = int(target400_hits[0]) if len(target400_hits) else None
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "horizon": horizon,
                    "window_start": date_text(common_index[start]),
                    "window_end": date_text(common_index[start + horizon]),
                    "window_valid": True,
                    "invalid_reason": "",
                    "final_equity": float(equity.iloc[-1]),
                    "profit_dollars": float(equity.iloc[-1] - active.STARTING_EQUITY),
                    "max_drawdown_dollars": float(drawdown_dollars.min()),
                    "max_drawdown_pct": float(drawdown_pct.min()),
                    "absolute_600_stop_hit": stop is not None,
                    "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
                    "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
                }
            )
    return rows


def summarize_windows(rows: list[dict[str, Any]], strategy_id: str, horizon: int = 180) -> dict[str, Any]:
    frame = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and int(row["horizon"]) == horizon])
    if frame.empty:
        return {
            "strategy_id": strategy_id,
            "horizon": horizon,
            "valid_window_count": 0,
            "invalid_window_count": 0,
            "comparability_status": "not_comparable",
        }
    valid = frame[frame["window_valid"] == True].copy()  # noqa: E712
    invalid_count = int((frame["window_valid"] != True).sum())  # noqa: E712
    if valid.empty:
        return {
            "strategy_id": strategy_id,
            "horizon": horizon,
            "valid_window_count": 0,
            "invalid_window_count": invalid_count,
            "comparability_status": "not_comparable",
        }
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "valid_window_count": int(len(valid)),
        "invalid_window_count": invalid_count,
        "median_final_equity": float(valid["final_equity"].median()),
        "mean_final_equity": float(valid["final_equity"].mean()),
        "best_final_equity": float(valid["final_equity"].max()),
        "worst_final_equity": float(valid["final_equity"].min()),
        "target_300_before_stop_rate": float(valid["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(valid["target_400_before_stop"].mean()),
        "worst_drawdown_dollars": float(valid["max_drawdown_dollars"].min()),
        "worst_drawdown_pct": float(valid["max_drawdown_pct"].min()),
        "stop_hit_rate": float(valid["absolute_600_stop_hit"].mean()),
        "comparability_status": "comparable" if invalid_count == 0 else "partially_comparable",
    }


def full_period_metrics(daily: pd.Series, weights: pd.DataFrame | None = None) -> dict[str, Any]:
    daily = daily.dropna().astype(float)
    if daily.empty:
        return {}
    equity = (1.0 + daily).cumprod()
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    result = {
        "full_period_start": date_text(daily.index.min()),
        "full_period_end": date_text(daily.index.max()),
        "full_period_total_return": float(equity.iloc[-1] - 1.0),
        "full_period_cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "full_period_max_drawdown_pct": float((equity / equity.cummax() - 1.0).min()),
        "full_period_volatility": float(daily.std() * np.sqrt(252.0)),
    }
    if weights is not None and not weights.empty:
        aligned_weights = weights.reindex(daily.index).ffill().fillna(0.0)
        risky_cols = [col for col in aligned_weights.columns if col != "BIL"]
        risky = aligned_weights[risky_cols].sum(axis=1) if risky_cols else pd.Series(0.0, index=aligned_weights.index)
        result.update(
            {
                "maximum_exposure": float(risky.max()),
                "average_exposure": float(risky.mean()),
                "percentage_time_invested": float((risky > 1e-9).mean()),
                "trade_or_allocation_change_count": int(
                    (aligned_weights.diff().abs().fillna(aligned_weights.abs()).sum(axis=1) > 1e-6).sum()
                ),
                "turnover": float(aligned_weights.diff().abs().fillna(aligned_weights.abs()).sum(axis=1).sum() / 2.0),
            }
        )
    return result


def benchmark_delta_rows(
    lane_ids: list[str],
    summaries: dict[str, dict[str, Any]],
    benchmarks: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane_id in lane_ids:
        lane = summaries.get(lane_id, {})
        for benchmark_id in benchmarks:
            bench = summaries.get(benchmark_id, {})
            rows.append(
                {
                    "lane_id": lane_id,
                    "benchmark_id": benchmark_id,
                    "horizon": 180,
                    "lane_median_final_equity": lane.get("median_final_equity", ""),
                    "benchmark_median_final_equity": bench.get("median_final_equity", ""),
                    "median_final_equity_delta": (
                        float(lane.get("median_final_equity")) - float(bench.get("median_final_equity"))
                        if lane.get("median_final_equity") is not None and bench.get("median_final_equity") is not None
                        else ""
                    ),
                    "lane_worst_drawdown_dollars": lane.get("worst_drawdown_dollars", ""),
                    "benchmark_worst_drawdown_dollars": bench.get("worst_drawdown_dollars", ""),
                    "worst_drawdown_delta": (
                        float(lane.get("worst_drawdown_dollars")) - float(bench.get("worst_drawdown_dollars"))
                        if lane.get("worst_drawdown_dollars") is not None and bench.get("worst_drawdown_dollars") is not None
                        else ""
                    ),
                    "comparison_status": "comparable"
                    if lane.get("comparability_status") == "comparable" and bench.get("comparability_status") == "comparable"
                    else "not_comparable",
                }
            )
    return rows


def delta_lookup(deltas: list[dict[str, Any]], lane_id: str, benchmark_id: str, key: str) -> float | None:
    for row in deltas:
        if row["lane_id"] == lane_id and row["benchmark_id"] == benchmark_id:
            value = row.get(key)
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def outcome_for_lane(lane_id: str, lane: dict[str, Any], summary: dict[str, Any], deltas: list[dict[str, Any]]) -> tuple[str, str, str]:
    if lane["blocked"]:
        return "implementation_blocked", "methodology_or_implementation_failure", lane["blocker"]
    primary = lane["primary_row"]
    if primary.get("exposure_invariant_pass") is not True:
        return "invalid_methodology", "methodology_or_implementation_failure", "primary exposure invariant failed"
    if summary.get("comparability_status") != "comparable":
        return "not_comparable", "non_comparability", "common scored windows unavailable"
    if primary.get("numeric_criteria_pass") is not True:
        if float(summary.get("target_300_before_stop_rate", 0.0)) == 0.0 and float(summary.get("target_400_before_stop_rate", 0.0)) == 0.0:
            return "no_material_edge", "insufficient_return", "primary lane numeric criteria failed and target hit rates are zero"
        return "control_weak", "direction_owner_review_required", "primary lane numeric criteria failed under its existing rule"

    active_combo_delta = delta_lookup(deltas, lane_id, ACTIVE_COMBO_ID, "median_final_equity_delta")
    spy200d_delta = delta_lookup(deltas, lane_id, SPY200D_ID, "median_final_equity_delta")
    bil_delta = delta_lookup(deltas, lane_id, BIL_ID, "median_final_equity_delta")
    active_combo_drawdown_delta = delta_lookup(deltas, lane_id, ACTIVE_COMBO_ID, "worst_drawdown_delta")
    if active_combo_delta is not None and spy200d_delta is not None and bil_delta is not None:
        if active_combo_delta > 0.0 and spy200d_delta > 0.0 and bil_delta > 0.0:
            if active_combo_drawdown_delta is not None and active_combo_drawdown_delta < 0.0:
                return "higher_return_higher_risk", "excess_drawdown", "positive return deltas but worse drawdown than active combo"
            return "comparative_evidence_positive", "none", "existing lane criteria passed and sign-only benchmark deltas are positive"
        if active_combo_delta <= 0.0:
            return "control_weak", "weak_versus_active_combo_benchmark", "existing lane criteria passed but active-combo delta is not positive"
        if spy200d_delta <= 0.0:
            return "control_weak", "weak_versus_spy_control", "existing lane criteria passed but SPY_200d delta is not positive"
        if bil_delta <= 0.0:
            return "no_material_edge", "insufficient_return", "existing lane criteria passed but BIL delta is not positive"
    return "direction_owner_review_required", "direction_owner_review_required", "no explicit repository rule covers this mixed comparison"


def write_summary(output: Path, manifest: dict[str, Any], lane_metrics: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> None:
    evaluated = [row["lane_id"] for row in lane_metrics if row.get("comparability_status") == "comparable"]
    blocked = [row["lane_id"] for row in lane_metrics if row.get("comparability_status") != "comparable"]
    positive = [row["lane_id"] for row in outcomes if row["screening_outcome"] == "comparative_evidence_positive"]
    lines = [
        "# Public-Source Comparative Screening Batch V1",
        "",
        f"Batch ID: `{SCREENING_BATCH_ID}`",
        f"Included lanes: `{len(INCLUDED_LANE_IDS)}`",
        f"Comparable/evaluated lanes: `{len(evaluated)}`",
        f"Blocked or not comparable lanes: `{len(blocked)}`",
        f"Comparative-evidence-positive lanes: `{len(positive)}`",
        "",
        "This is diagnostic screening evidence only. No strategy is promoted, rejected, paper/demo activated, or made eligible by this packet.",
        "",
        "## Outcomes",
    ]
    for row in outcomes:
        lines.append(
            f"- `{row['lane_id']}`: `{row['screening_outcome']}`; failure pattern `{row['primary_failure_pattern']}`."
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            f"- Provider download: `{manifest['provider_download']}`",
            f"- Intraday data used: `{manifest['intraday_data_used']}`",
            f"- Parameter search: `{manifest['parameter_search']}`",
            f"- Strategy variants created: `{manifest['new_strategy_variants_created']}`",
            f"- Paper/demo activation: `{manifest['paper_forward_activation']}`",
            f"- Active combo role: `{manifest['active_combo_role']}`",
            f"- Next action: `{manifest['next_action']}`",
        ]
    )
    write_text(output / "screening_summary.md", "\n".join(lines) + "\n")


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    modules = {spec.lane_id: load_lane(spec) for spec in LANES}
    benchmarks, benchmark_weights = benchmark_returns(root)
    prereg_preview = preregistration_payload(root, modules)
    lane_inputs, lineage_rows = evaluate_frozen_lanes(root)
    common_index = common_scored_index(lane_inputs, benchmarks)
    prereg = preregistration_payload(root, modules, common_index)
    prereg_errors = preregistration_errors(prereg)
    write_json(output / "screening_preregistration.json", {**prereg, "created_utc": created, "internal_consistency_errors": prereg_errors})
    if prereg_errors:
        manifest = {
            "created_utc": created,
            "batch_id": SCREENING_BATCH_ID,
            "screening_batch_run": False,
            "blocked_before_execution": True,
            "internal_consistency_errors": prereg_errors,
            "next_action": "fix_public_source_comparative_screening_manifest",
        }
        write_json(output / "screening_manifest.json", manifest)
        return {**manifest, "output_dir": str(output.resolve())}

    all_returns: dict[str, pd.Series] = {
        lane_id: lane["returns"].rename(lane_id)
        for lane_id, lane in lane_inputs.items()
        if not lane["blocked"] and not lane["returns"].empty
    }
    all_returns.update(benchmarks)
    window_rows: list[dict[str, Any]] = []
    for strategy_id, daily in all_returns.items():
        for row in window_result_rows(strategy_id, daily, common_index):
            row["record_type"] = "lane" if strategy_id in INCLUDED_LANE_IDS else "benchmark"
            window_rows.append(row)

    summaries = {strategy_id: summarize_windows(window_rows, strategy_id, 180) for strategy_id in all_returns}
    benchmark_ids = (SPY200D_ID, SPY_BUY_HOLD_ID, BIL_ID, ACTIVE_COMBO_ID)
    deltas = benchmark_delta_rows(list(INCLUDED_LANE_IDS), summaries, benchmark_ids)

    lane_metrics: list[dict[str, Any]] = []
    comparability_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for lane_id in INCLUDED_LANE_IDS:
        lane = lane_inputs[lane_id]
        summary = summaries.get(lane_id, {"comparability_status": "not_comparable"})
        primary = lane.get("primary_row", {})
        weights = lane.get("weights", pd.DataFrame())
        full = full_period_metrics(lane.get("returns", pd.Series(dtype=float)), weights)
        outcome, failure, explanation = outcome_for_lane(lane_id, lane, summary, deltas)
        lane_metrics.append(
            {
                "lane_id": lane_id,
                "source_id": lane["lineage"].get("source_id"),
                "family_id": lane["lineage"].get("family_id"),
                "primary_variant_id": primary.get("variant_id", ""),
                "comparability_status": summary.get("comparability_status", "not_comparable"),
                "valid_window_count": summary.get("valid_window_count", 0),
                "invalid_window_count": summary.get("invalid_window_count", 0),
                "180d_median_final_equity": summary.get("median_final_equity", ""),
                "target_300_success_rate": summary.get("target_300_before_stop_rate", ""),
                "target_400_success_rate": summary.get("target_400_before_stop_rate", ""),
                "worst_drawdown_dollars": summary.get("worst_drawdown_dollars", ""),
                "worst_drawdown_pct": summary.get("worst_drawdown_pct", ""),
                "stop_hit_rate": summary.get("stop_hit_rate", ""),
                "maximum_exposure": full.get("maximum_exposure", primary.get("max_daily_exposure", "")),
                "average_exposure": full.get("average_exposure", primary.get("average_spy_exposure_share", "")),
                "turnover": full.get("turnover", primary.get("turnover_proxy", "")),
                "trade_or_allocation_change_count": full.get("trade_or_allocation_change_count", primary.get("trade_count", "")),
                "percentage_time_invested": full.get("percentage_time_invested", primary.get("average_spy_exposure_share", "")),
                "existing_primary_numeric_criteria_pass": primary.get("numeric_criteria_pass", ""),
                "screening_outcome": outcome,
                "primary_failure_pattern": failure,
            }
        )
        comparability_rows.append(
            {
                "lane_id": lane_id,
                "status": "implementation_blocked" if lane["blocked"] else summary.get("comparability_status", "not_comparable"),
                "blocker": lane["blocker"] or ("" if summary.get("comparability_status") == "comparable" else "common_window_alignment_failed"),
                "common_scored_start": date_text(common_index.min()) if len(common_index) else "",
                "common_scored_end": date_text(common_index.max()) if len(common_index) else "",
                "common_scored_day_count": len(common_index),
                "warmup_or_first_valid_note": json.dumps(lane.get("preflight", {}), sort_keys=True, default=str),
            }
        )
        if not weights.empty:
            inv = invariant_summary(weights)
        else:
            inv = {
                "max_daily_exposure": "",
                "max_daily_weight_sum": "",
                "weight_sum_violation_count": "",
                "negative_weight_violation_count": "",
                "nan_weight_count": "",
                "impossible_cash_and_risky_exposure_days": "",
                "exposure_invariant_passed": False,
            }
        invariant_rows.append(
            {
                "record_id": lane_id,
                "record_type": "lane",
                "max_daily_exposure": inv.get("max_daily_exposure", ""),
                "max_daily_weight_sum": inv.get("max_daily_weight_sum", ""),
                "weight_sum_violation_count": inv.get("weight_sum_violation_count", ""),
                "negative_weight_violation_count": inv.get("negative_weight_violation_count", ""),
                "nan_weight_count": inv.get("nan_weight_count", ""),
                "impossible_cash_and_risky_exposure_days": inv.get("impossible_cash_and_risky_exposure_days", ""),
                "zero_weight_preservation_status": "no_weight_sum_or_nan_violation" if inv.get("exposure_invariant_passed") else "failed_or_unavailable",
                "bil_cash_fallback_status": "replacement_or_control_cash_only",
                "signal_execution_ordering": "completed_signal_then_shifted_weight_execution",
                "no_lookahead_status": "project_shifted_weight_convention",
                "invariant_passed": inv.get("exposure_invariant_passed", False),
            }
        )
        outcome_rows.append(
            {
                "lane_id": lane_id,
                "screening_outcome": outcome,
                "primary_failure_pattern": failure,
                "outcome_label_allowed": outcome in OUTCOME_LABELS,
                "rule_source": "existing_lane_numeric_criteria_plus_sign_only_same_window_benchmark_deltas_v1",
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
                "candidate_exhaustive_eligibility": False,
                "explanation": explanation,
            }
        )
        failure_rows.append(
            {
                "lane_id": lane_id,
                "primary_failure_pattern": failure,
                "failure_pattern_allowed": failure in FAILURE_PATTERNS,
                "failure_explanation": explanation,
            }
        )

    benchmark_metric_rows: list[dict[str, Any]] = []
    for benchmark_id in benchmark_ids:
        summary = summaries.get(benchmark_id, {})
        full = full_period_metrics(benchmarks.get(benchmark_id, pd.Series(dtype=float)), benchmark_weights.get(benchmark_id))
        benchmark_metric_rows.append(
            {
                "benchmark_id": benchmark_id,
                "benchmark_role": "benchmark_reference_only" if benchmark_id == ACTIVE_COMBO_ID else "control_benchmark",
                "benchmark_status": "benchmark_watchlist_reference" if benchmark_id == ACTIVE_COMBO_ID else "control_only",
                "comparability_status": summary.get("comparability_status", "not_comparable"),
                "valid_window_count": summary.get("valid_window_count", 0),
                "invalid_window_count": summary.get("invalid_window_count", 0),
                "180d_median_final_equity": summary.get("median_final_equity", ""),
                "target_300_success_rate": summary.get("target_300_before_stop_rate", ""),
                "target_400_success_rate": summary.get("target_400_before_stop_rate", ""),
                "worst_drawdown_dollars": summary.get("worst_drawdown_dollars", ""),
                "worst_drawdown_pct": summary.get("worst_drawdown_pct", ""),
                "stop_hit_rate": summary.get("stop_hit_rate", ""),
                "full_period_total_return": full.get("full_period_total_return", ""),
                "full_period_max_drawdown_pct": full.get("full_period_max_drawdown_pct", ""),
            }
        )
        if benchmark_id in benchmark_weights:
            inv = invariant_summary(benchmark_weights[benchmark_id])
            invariant_rows.append(
                {
                    "record_id": benchmark_id,
                    "record_type": "benchmark",
                    "max_daily_exposure": inv.get("max_daily_exposure", ""),
                    "max_daily_weight_sum": inv.get("max_daily_weight_sum", ""),
                    "weight_sum_violation_count": inv.get("weight_sum_violation_count", ""),
                    "negative_weight_violation_count": inv.get("negative_weight_violation_count", ""),
                    "nan_weight_count": inv.get("nan_weight_count", ""),
                    "impossible_cash_and_risky_exposure_days": inv.get("impossible_cash_and_risky_exposure_days", ""),
                    "zero_weight_preservation_status": "no_weight_sum_or_nan_violation",
                    "bil_cash_fallback_status": "replacement_or_control_cash_only",
                    "signal_execution_ordering": "completed_signal_then_shifted_weight_execution",
                    "no_lookahead_status": "project_shifted_weight_convention",
                    "invariant_passed": inv.get("exposure_invariant_passed", False),
                }
            )
        elif benchmark_id == ACTIVE_COMBO_ID:
            combo_manifest = read_json(root / ACTIVE_COMBO_MANIFEST)
            combo_consistency = read_json(root / ACTIVE_COMBO_CONSISTENCY)
            invariant_rows.append(
                {
                    "record_id": benchmark_id,
                    "record_type": "benchmark",
                    "max_daily_exposure": combo_manifest.get("max_daily_exposure", ""),
                    "max_daily_weight_sum": combo_manifest.get("max_daily_exposure", ""),
                    "weight_sum_violation_count": 0 if combo_manifest.get("weight_invariant_passed") else "",
                    "negative_weight_violation_count": 0 if combo_manifest.get("weight_invariant_passed") else "",
                    "nan_weight_count": 0 if combo_manifest.get("date_alignment_passed") else "",
                    "impossible_cash_and_risky_exposure_days": 0 if combo_manifest.get("bil_remainder_passed") else "",
                    "zero_weight_preservation_status": "active_combo_reconciliation_invariants",
                    "bil_cash_fallback_status": "active_combo_reconciliation_invariants",
                    "signal_execution_ordering": "active_combo_reconciliation_existing_protocol",
                    "no_lookahead_status": "active_combo_reconciliation_existing_protocol",
                    "invariant_passed": combo_consistency.get("consistency_passed") is True,
                }
            )

    required_files = [
        "screening_preregistration.json",
        "screening_manifest.json",
        "screening_summary.md",
        "lane_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "comparability_review.csv",
        "weight_exposure_invariants.csv",
        "failure_patterns.csv",
        "screening_outcomes.csv",
        "artifact_lineage.csv",
        "screening_consistency_check.json",
    ]
    positive_count = sum(row["screening_outcome"] == "comparative_evidence_positive" for row in outcome_rows)
    invariant_failures = [row["record_id"] for row in invariant_rows if str(row.get("invariant_passed")).lower() != "true"]
    comparable_count = sum(row["comparability_status"] == "comparable" for row in lane_metrics)
    manifest = {
        "created_utc": created,
        "batch_id": SCREENING_BATCH_ID,
        "screening_batch_run": True,
        "included_lane_ids": list(INCLUDED_LANE_IDS),
        "included_lane_count": len(INCLUDED_LANE_IDS),
        "excluded_public_source_ids": list(EXCLUDED_PUBLIC_SOURCE_IDS),
        "excluded_unimplemented_or_duplicate_entries": True,
        "lanes_evaluated_count": len(lane_metrics),
        "lanes_comparable_count": comparable_count,
        "lanes_blocked_count": len(INCLUDED_LANE_IDS) - comparable_count,
        "benchmarks": list(benchmark_ids),
        "benchmark_comparability_complete": all(row["comparability_status"] == "comparable" for row in benchmark_metric_rows),
        "common_scored_start": date_text(common_index.min()) if len(common_index) else "",
        "common_scored_end": date_text(common_index.max()) if len(common_index) else "",
        "common_scored_day_count": len(common_index),
        "common_window_horizons": active.HORIZONS,
        "common_window_count": len([row for row in window_rows if row.get("strategy_id") == INCLUDED_LANE_IDS[0]]),
        "initial_capital": active.STARTING_EQUITY,
        "stop_dollars": active.STOP_DOLLARS,
        "parameter_search": False,
        "parameter_selection_from_results": False,
        "new_strategy_variants_created": False,
        "new_strategies_added": False,
        "strategy_discovery_run": False,
        "broad_discovery_run": False,
        "robustness_run": False,
        "candidate_exhaustive_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "paper_forward_activation": False,
        "strategy_lifecycle_statuses_changed": False,
        "evidence_levels_changed": False,
        "active_observations_changed": False,
        "active_combo_changed": False,
        "active_combo_role": "benchmark_reference_only",
        "active_combo_status": "benchmark_watchlist_reference",
        "dsr_unverified_historical_4071_04_used": False,
        "screening_outputs_non_promotable": True,
        "comparative_evidence_positive_count": positive_count,
        "direction_owner_review_required_count": sum(
            row["screening_outcome"] == "direction_owner_review_required" for row in outcome_rows
        ),
        "invariant_failure_count": len(invariant_failures),
        "invariant_failure_records": invariant_failures,
        "next_action": NEXT_ACTION,
        "deterministic_core_hash": "",
    }
    manifest["deterministic_core_hash"] = hash_data(
        {
            "lane_metrics": lane_metrics,
            "benchmark_metrics": benchmark_metric_rows,
            "deltas": deltas,
            "outcomes": outcome_rows,
            "common_scored_start": manifest["common_scored_start"],
            "common_scored_end": manifest["common_scored_end"],
        }
    )

    consistency = {
        "consistency_passed": (
            tuple(manifest["included_lane_ids"]) == INCLUDED_LANE_IDS
            and manifest["included_lane_count"] == 6
            and manifest["lanes_evaluated_count"] == 6
            and manifest["invariant_failure_count"] == 0
            and manifest["provider_download"] is False
            and manifest["intraday_data_used"] is False
            and manifest["parameter_search"] is False
            and manifest["new_strategy_variants_created"] is False
            and manifest["active_combo_role"] == "benchmark_reference_only"
            and manifest["dsr_unverified_historical_4071_04_used"] is False
            and all(row["outcome_label_allowed"] for row in outcome_rows)
            and all(row["failure_pattern_allowed"] for row in failure_rows)
        ),
        "included_lane_set_exact": tuple(manifest["included_lane_ids"]) == INCLUDED_LANE_IDS,
        "excluded_records_not_evaluated": all(source_id not in manifest["included_lane_ids"] for source_id in EXCLUDED_PUBLIC_SOURCE_IDS),
        "common_scored_windows_present": bool(manifest["common_window_count"]),
        "active_combo_benchmark_only": manifest["active_combo_role"] == "benchmark_reference_only",
        "no_dsr_unverified_historical_metric": manifest["dsr_unverified_historical_4071_04_used"] is False,
        "no_lifecycle_or_evidence_level_changes": manifest["strategy_lifecycle_statuses_changed"] is False
        and manifest["evidence_levels_changed"] is False,
        "checked_at_utc": created,
    }

    write_json(output / "screening_manifest.json", manifest)
    write_csv(output / "lane_metrics.csv", lane_metrics, list(lane_metrics[0].keys()) if lane_metrics else [])
    write_csv(
        output / "benchmark_metrics.csv",
        benchmark_metric_rows,
        list(benchmark_metric_rows[0].keys()) if benchmark_metric_rows else [],
    )
    write_csv(output / "benchmark_relative_deltas.csv", deltas, list(deltas[0].keys()) if deltas else [])
    write_csv(output / "window_level_results.csv", window_rows, list(window_rows[0].keys()) if window_rows else [])
    write_csv(output / "comparability_review.csv", comparability_rows, list(comparability_rows[0].keys()))
    write_csv(output / "weight_exposure_invariants.csv", invariant_rows, list(invariant_rows[0].keys()))
    write_csv(output / "failure_patterns.csv", failure_rows, list(failure_rows[0].keys()))
    write_csv(output / "screening_outcomes.csv", outcome_rows, list(outcome_rows[0].keys()))
    write_csv(output / "artifact_lineage.csv", lineage_rows, list(lineage_rows[0].keys()))
    write_json(output / "screening_consistency_check.json", consistency)
    write_summary(output, manifest, lane_metrics, outcome_rows)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=str))
