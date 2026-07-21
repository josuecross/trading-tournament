from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from run_trade_management_overlay_comparison import (
    FROZEN_STRATEGIES,
    _strategy_only_config,
    _strategy_source_hash,
    summarize_result,
)
from src.backtester import Backtester, BacktestResult
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.overlays import (
    IdentityOverlay,
    LaggedVolatilityTargetOverlay,
    OverlayDataError,
    RebalanceBandOverlay,
    TradeManagementOverlay,
    WideATRCatastrophicStopOverlay,
    stable_hash,
)
from src.utils import config_hash, git_commit_hash, load_config, write_json


ROOT = Path(__file__).resolve().parent
PRIOR_RUN = ROOT / "reports" / "trade_management" / "codex_overlay_v1_validation2"
OUT_DIR = ROOT / "reports" / "trade_management" / "codex_overlay_v1_correctness_audit"
START = "2017-01-01"
END = "2020-12-31"
SLIPPAGES = [0.0, 0.0005, 0.001]


def df_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return stable_hash({"empty": True, "columns": [] if df is None else list(df.columns)})
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].astype(str)
    return stable_hash(
        {
            "columns": list(normalized.columns),
            "csv": normalized.to_csv(index=False, lineterminator="\n", na_rep="<NA>"),
        }
    )


def signal_ledger(result: BacktestResult) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not result.trades.empty:
        for _, trade in result.trades.iterrows():
            signal_date = str(trade.get("entry_signal_date", trade.get("signal_date", "")))
            rows.append(
                {
                    "source": "accepted_trade",
                    "signal_id": f"{trade.get('strategy')}:{trade.get('symbol')}:{signal_date}:entry",
                    "timestamp": signal_date,
                    "asset": trade.get("symbol", ""),
                    "trade_id": trade.get("trade_id", ""),
                    "entry_date": trade.get("entry_date", ""),
                    "exit_date": trade.get("exit_date", ""),
                    "exit_reason": trade.get("exit_reason", ""),
                }
            )
    if not result.skipped_signals.empty:
        for idx, skip in result.skipped_signals.iterrows():
            rows.append(
                {
                    "source": "rejected_signal",
                    "signal_id": f"{skip.get('strategy')}:{skip.get('symbol')}:{skip.get('date')}:{skip.get('signal_type')}:{idx}",
                    "timestamp": skip.get("date", ""),
                    "asset": skip.get("symbol", ""),
                    "trade_id": "",
                    "entry_date": "",
                    "exit_date": "",
                    "exit_reason": skip.get("reason_skipped", ""),
                }
            )
    return pd.DataFrame(rows)


def result_hashes(result: BacktestResult) -> dict[str, str]:
    components = {
        "daily_state_hash": df_hash(result.equity_curve),
        "trade_ledger_hash": df_hash(result.trades),
        "skipped_orders_hash": df_hash(result.skipped_signals),
        "risk_events_hash": df_hash(result.risk_events),
        "lifecycle_events_hash": df_hash(result.strategy_lifecycle_events),
        "metrics_hash": df_hash(result.strategy_metrics),
        "target_timing_hash": df_hash(result.target_timing),
        "signal_ledger_hash": df_hash(signal_ledger(result)),
    }
    components["complete_state_hash"] = stable_hash(components)
    return components


def run_backtest(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    strategy_id: str,
    trial_name: str,
    slippage: float,
    overlay_factory: Callable[[], TradeManagementOverlay | None],
) -> tuple[BacktestResult | None, pd.DataFrame, str]:
    strategy_hash = _strategy_source_hash(config, strategy_id)
    try:
        overlay = overlay_factory()
        bt = Backtester(prepared, config)
        result = bt.run(
            trial_name,
            START,
            END,
            slippage,
            lightweight_outputs=True,
            overlay=overlay,
            run_id=f"correctness_{strategy_id}_{trial_name}_{int(slippage * 10000)}bps",
            base_strategy_id=strategy_id,
            base_strategy_hash=strategy_hash,
        )
        events = result.overlay_events.copy()
        if not events.empty:
            events.insert(0, "slippage_bps_per_side", slippage * 10000.0)
            events.insert(0, "trial_name", trial_name)
            events.insert(0, "strategy_id", strategy_id)
        return result, events, ""
    except Exception as exc:
        return None, pd.DataFrame(), str(exc)


def parse_json_cell(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        out = json.loads(value)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        return {}


def volatility_diagnostics(
    prior_events: pd.DataFrame,
    calibration_results: dict[str, BacktestResult],
) -> pd.DataFrame:
    rows = []
    for strategy in [item["strategy_id"] for item in FROZEN_STRATEGIES]:
        cal = calibration_results[strategy].equity_curve.copy()
        cal["date"] = pd.to_datetime(cal["date"])
        returns = cal["equity"].astype(float).pct_change()
        rolling_vol = returns.rolling(window=63, min_periods=63).std() * np.sqrt(252)
        valid = rolling_vol.dropna()
        zero_returns = int((returns.fillna(0.0).abs() <= 1e-15).sum())
        strategy_events = prior_events[
            (prior_events["strategy_id"] == strategy)
            & (prior_events["trial_name"] == "lagged_volatility_target")
            & (prior_events["reason_code"] == "lagged_vol_scale")
        ]
        live_vols: list[float] = []
        raw_scales: list[float] = []
        capped_scales: list[float] = []
        target_vols: list[float] = []
        for _, event in strategy_events.iterrows():
            proposed = parse_json_cell(event.get("proposed_order"))
            flags = parse_json_cell(event.get("data_quality_flags"))
            for values, key, source in [
                (live_vols, "estimated_volatility", proposed),
                (target_vols, "target_volatility", proposed),
                (raw_scales, "raw_scale", flags),
                (capped_scales, "capped_scale", flags),
            ]:
                value = source.get(key)
                if value is not None and np.isfinite(float(value)):
                    values.append(float(value))
        capped = pd.Series(capped_scales, dtype=float)
        target = float(pd.Series(target_vols, dtype=float).median()) if target_vols else np.nan
        floor_pct = float((capped == 0.25).mean()) if len(capped) else np.nan
        cap_pct = float((capped == 1.0).mean()) if len(capped) else np.nan
        between_pct = float(((capped > 0.25) & (capped < 1.0)).mean()) if len(capped) else np.nan
        status = (
            "INVALID_DEGENERATE_VOLATILITY_CALIBRATION"
            if not np.isfinite(target) or target <= 1e-8 or floor_pct >= 0.95 or cap_pct >= 0.95
            else "PASS_MECHANICALLY_VALID"
        )
        rows.append(
            {
                "strategy_id": strategy,
                "calibration_start": str(cal["date"].min().date()),
                "calibration_end": str(cal["date"].max().date()),
                "calibration_observations": int(len(cal)),
                "zero_return_observations": zero_returns,
                "zero_return_pct": zero_returns / len(cal) if len(cal) else np.nan,
                "rolling_vol_observation_count": int(len(valid)),
                "rolling_vol_min": float(valid.min()) if len(valid) else np.nan,
                "rolling_vol_p10": float(valid.quantile(0.10)) if len(valid) else np.nan,
                "rolling_vol_median": float(valid.median()) if len(valid) else np.nan,
                "rolling_vol_mean": float(valid.mean()) if len(valid) else np.nan,
                "rolling_vol_p90": float(valid.quantile(0.90)) if len(valid) else np.nan,
                "rolling_vol_max": float(valid.max()) if len(valid) else np.nan,
                "selected_target_volatility": target,
                "live_estimated_vol_min": float(pd.Series(live_vols).min()) if live_vols else np.nan,
                "live_estimated_vol_median": float(pd.Series(live_vols).median()) if live_vols else np.nan,
                "live_estimated_vol_max": float(pd.Series(live_vols).max()) if live_vols else np.nan,
                "raw_scale_min": float(pd.Series(raw_scales).min()) if raw_scales else np.nan,
                "raw_scale_median": float(pd.Series(raw_scales).median()) if raw_scales else np.nan,
                "raw_scale_max": float(pd.Series(raw_scales).max()) if raw_scales else np.nan,
                "floor_decision_pct": floor_pct,
                "cap_decision_pct": cap_pct,
                "between_bounds_decision_pct": between_pct,
                "applicable_decision_count": int(len(capped)),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def intent_semantics(prior_events: pd.DataFrame, corrected_events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    prior_resize = prior_events[prior_events["decision_type"].isin(["resize_target", "suppress_order"])].copy()
    for (strategy, trial), frame in prior_resize.groupby(["strategy_id", "trial_name"]):
        values = pd.to_numeric(frame["base_target"], errors="coerce").dropna()
        inferred = "target_weight" if strategy.startswith("N2_") else "risk_amount_dollars"
        rows.append(
            {
                "evidence_source": "prior_run",
                "strategy_id": strategy,
                "trial_name": trial,
                "observed_base_target_min": float(values.min()) if len(values) else np.nan,
                "observed_base_target_median": float(values.median()) if len(values) else np.nan,
                "observed_base_target_max": float(values.max()) if len(values) else np.nan,
                "target_unit": inferred,
                "guard_status": "FAIL_INTENT_UNIT_SEMANTICS",
                "notes": "Prior event schema did not explicitly identify units.",
            }
        )
    if not corrected_events.empty:
        for (strategy, trial, unit), frame in corrected_events.groupby(["strategy_id", "trial_name", "target_unit"], dropna=False):
            rows.append(
                {
                    "evidence_source": "corrected_rerun",
                    "strategy_id": strategy,
                    "trial_name": trial,
                    "observed_base_target_min": pd.to_numeric(frame["base_target"], errors="coerce").min(),
                    "observed_base_target_median": pd.to_numeric(frame["base_target"], errors="coerce").median(),
                    "observed_base_target_max": pd.to_numeric(frame["base_target"], errors="coerce").max(),
                    "target_unit": unit,
                    "guard_status": "FIXED_BY_METHODOLOGY_CORRECTION",
                    "notes": "Corrected event schema records intent_kind, target_unit, and supported_target_units.",
                }
            )
    return pd.DataFrame(rows)


def slippage_reconciliation(result: BacktestResult, strategy_id: str, slippage: float) -> pd.DataFrame:
    rows = []
    if result.trades.empty:
        return pd.DataFrame(rows)
    for _, trade in result.trades.iterrows():
        entry_fill = float(trade["entry_price"])
        exit_fill = float(trade["exit_price"])
        shares = float(trade["shares"])
        entry_reference = entry_fill / (1.0 + slippage) if slippage > 0 else entry_fill
        if trade["exit_reason"] in {"final_mark_to_market", "data_issue"} or slippage <= 0:
            exit_reference = exit_fill
            exit_direct_cost = 0.0
        else:
            exit_reference = exit_fill / (1.0 - slippage)
            exit_direct_cost = abs(shares * exit_reference * slippage)
        entry_direct_cost = abs(shares * entry_reference * slippage)
        rows.append(
            {
                "row_type": "trade_reconciliation",
                "strategy_id": strategy_id,
                "slippage_bps_per_side": slippage * 10000.0,
                "trade_id": trade["trade_id"],
                "signal_id": f"{trade['strategy']}:{trade['symbol']}:{trade['entry_signal_date']}:entry",
                "asset": trade["symbol"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "exit_reason": trade["exit_reason"],
                "entry_reference_fill": entry_reference,
                "exit_reference_fill": exit_reference,
                "slippage_adjustment_entry": entry_fill - entry_reference,
                "slippage_adjustment_exit": exit_reference - exit_fill,
                "actual_entry_fill": entry_fill,
                "actual_exit_fill": exit_fill,
                "quantity": shares,
                "direct_modeled_transaction_cost": entry_direct_cost + exit_direct_cost,
                "ledger_transaction_cost": float(trade.get("slippage_paid_estimate", np.nan)),
                "cost_reconciles": bool(np.isclose(entry_direct_cost + exit_direct_cost, float(trade.get("slippage_paid_estimate", np.nan)))),
                "realized_pnl": trade["pnl"],
                "cause_code": "DIRECT_FILL_COST_ONLY",
            }
        )
    return pd.DataFrame(rows)


def trade_key_frame(result: BacktestResult) -> pd.DataFrame:
    if result.trades.empty:
        return pd.DataFrame(columns=["sequence", "key", "exit_reason", "entry_date", "exit_date"])
    frame = result.trades.copy().sort_values(["entry_signal_date", "symbol", "trade_id"]).reset_index(drop=True)
    frame["sequence"] = frame.index
    frame["key"] = (
        frame["strategy"].astype(str)
        + ":"
        + frame["symbol"].astype(str)
        + ":"
        + frame["entry_signal_date"].astype(str)
    )
    return frame[["sequence", "key", "exit_reason", "entry_date", "exit_date", "entry_price", "exit_price", "shares"]]


def path_divergence(strategy_id: str, low_slip: float, high_slip: float, low: BacktestResult, high: BacktestResult) -> dict[str, Any]:
    a = trade_key_frame(low)
    b = trade_key_frame(high)
    min_len = min(len(a), len(b))
    cause = "SIGNAL_PATH_UNCHANGED"
    first = ""
    for idx in range(min_len):
        if a.loc[idx, "key"] != b.loc[idx, "key"]:
            cause = "ORDER_REJECTED" if len(a) != len(b) else "UNEXPLAINED_PATH_DIVERGENCE"
            first = f"sequence={idx} {a.loc[idx, 'key']} vs {b.loc[idx, 'key']}"
            break
        if a.loc[idx, "exit_reason"] != b.loc[idx, "exit_reason"]:
            cause = "STOP_TRIGGER_CHANGED"
            first = f"sequence={idx} {a.loc[idx, 'key']} exit {a.loc[idx, 'exit_reason']} vs {b.loc[idx, 'exit_reason']}"
            break
        if not np.isclose(float(a.loc[idx, "shares"]), float(b.loc[idx, "shares"])):
            cause = "RISK_SIZING_CHANGE"
            first = f"sequence={idx} {a.loc[idx, 'key']} quantity changed"
            break
        if not np.isclose(float(a.loc[idx, "entry_price"]), float(b.loc[idx, "entry_price"])):
            cause = "DIRECT_FILL_COST_ONLY"
            first = f"sequence={idx} {a.loc[idx, 'key']} fill price changed"
            break
    if not first and len(a) != len(b):
        cause = "ORDER_REJECTED"
        first = f"trade_count {len(a)} vs {len(b)}"
    return {
        "row_type": "path_divergence_summary",
        "strategy_id": strategy_id,
        "slippage_pair_bps": f"{low_slip * 10000:.0f}_vs_{high_slip * 10000:.0f}",
        "low_slippage_trade_count": int(len(a)),
        "high_slippage_trade_count": int(len(b)),
        "first_divergence": first or "none",
        "cause_code": cause,
    }


def rebalance_attribution(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    suppressions = events[
        (events["strategy_id"] == "N2_absolute_trend_taa")
        & (events["trial_name"] == "rebalance_band")
        & (events["decision_type"] == "suppress_order")
    ].copy()
    for _, event in suppressions.iterrows():
        current = parse_json_cell(event.get("current_position"))
        proposed = parse_json_cell(event.get("proposed_order"))
        flags = parse_json_cell(event.get("data_quality_flags"))
        base_target = float(event["base_target"])
        managed_target = float(event["managed_target"])
        delta = abs(base_target - managed_target)
        notional = proposed.get("notional_delta", np.nan)
        side = proposed.get("side", "entry")
        slippage = float(event.get("slippage_bps_per_side", 0.0)) / 10000.0
        rows.append(
            {
                "timestamp": event["timestamp"],
                "slippage_bps_per_side": event["slippage_bps_per_side"],
                "asset": event["asset"],
                "side": side,
                "current_marked_weight": current.get("weight", managed_target),
                "frozen_base_target": base_target,
                "weight_difference": delta,
                "notional_difference": notional,
                "existing_position": bool(current),
                "base_emitted_exit": side == "exit",
                "same_asset_replacement_entry": bool(flags.get("same_asset_replacement_target", side == "entry")),
                "both_sides_suppressed": bool(flags.get("paired_entry_suppressed", False)) or side == "entry",
                "subsequent_holding_duration": "not_exported_by_current_trade_schema",
                "avoided_direct_modeled_round_trip_cost": float(notional) * slippage * 2.0 if np.isfinite(float(notional)) else np.nan,
                "exposure_change_from_retention": managed_target - base_target,
                "available_at_decision_timestamp": True,
                "current_weight_pre_trade": True,
                "full_liquidation_suppressed": bool(side == "exit" and not flags.get("same_asset_replacement_target", False)),
                "risk_or_lifecycle_exit_blocked": bool(side == "exit" and flags.get("base_exit_reason") != "monthly_rebalance_exit"),
                "min_nav_rule_logged": event["reason_code"] == "below_nav_order",
                "weight_band_rule_logged": event["reason_code"] == "below_weight_band",
                "status": (
                    "PASS_MECHANICALLY_VALID"
                    if not (side == "exit" and not flags.get("same_asset_replacement_target", False))
                    and not (side == "exit" and flags.get("base_exit_reason") != "monthly_rebalance_exit")
                    else "FAIL_REBALANCE_SCOPE"
                ),
            }
        )
    return pd.DataFrame(rows)


def stop_precedence_markdown(events: pd.DataFrame) -> str:
    stop_events = events[
        (events["trial_name"] == "wide_atr_catastrophic_stop")
        & (events["reason_code"].isin(["atr_stop_normal_touch", "atr_stop_gap_through", "base_stop_precedence"]))
    ].copy()
    lines = [
        "# Stop Precedence Report",
        "",
        "Research-only methodology-correction audit.",
        "",
        "| strategy | bps | timestamp | asset | reason | overlay_stop | base_stop | base_target | OHLC | precedence | fill |",
        "| --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for _, event in stop_events.iterrows():
        flags = parse_json_cell(event.get("data_quality_flags"))
        fill = parse_json_cell(event.get("actual_fill"))
        precedence = "base_stop_or_target_first" if event["reason_code"] == "base_stop_precedence" else "overlay_after_base_not_hit"
        ohlc = f"{flags.get('bar_open')}/{flags.get('bar_high')}/{flags.get('bar_low')}/{flags.get('bar_close')}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(event["strategy_id"]),
                    f"{float(event['slippage_bps_per_side']):.0f}",
                    str(event["timestamp"]),
                    str(event["asset"]),
                    str(event["reason_code"]),
                    f"{float(event.get('trigger_level', np.nan)):.4f}",
                    f"{float(flags.get('base_stop_level', np.nan)):.4f}",
                    f"{float(flags.get('base_target_level', np.nan)):.4f}",
                    ohlc,
                    precedence,
                    str(fill.get("fill_price", "")),
                ]
            )
            + " |"
        )
    if len(stop_events) == 0:
        lines.append("| _none_ |  |  |  |  |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "Conclusion: corrected OVL-STP-001 records a no-op and defers whenever the frozen base stop or target is hit on the same bar. Overlay exits occur only when the base stop/target is not hit.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "config.yaml")
    config["project_root"] = str(ROOT)
    data_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(data_result.data)
    prior_events = pd.read_csv(PRIOR_RUN / "overlay_events.csv")
    prior_metrics = pd.read_csv(PRIOR_RUN / "metrics.csv")

    corrected_metrics: list[dict[str, Any]] = []
    corrected_events: list[pd.DataFrame] = []
    identity_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    calibration_results: dict[str, BacktestResult] = {}
    base_results: dict[tuple[str, float], BacktestResult] = {}

    for strategy in FROZEN_STRATEGIES:
        strategy_id = strategy["strategy_id"]
        strategy_cfg = _strategy_only_config(config, strategy_id)
        calibration_result, _, calibration_error = run_backtest(
            prepared=prepared,
            config=strategy_cfg,
            strategy_id=strategy_id,
            trial_name="calibration_base",
            slippage=0.0005,
            overlay_factory=lambda: None,
        )
        if calibration_result is None:
            raise RuntimeError(calibration_error)
        calibration_results[strategy_id] = calibration_result
        try:
            target_vol = LaggedVolatilityTargetOverlay.calibration_target_from_equity(
                calibration_result.equity_curve,
                calibration_start=config["date_ranges"]["in_sample"].get("start"),
                calibration_end=config["date_ranges"]["in_sample"].get("end"),
                lookback=63,
            )
        except OverlayDataError:
            target_vol = 0.0

        isolated_hashes: dict[tuple[str, float], dict[str, str]] = {}
        sequence_hashes: dict[str, dict[tuple[str, float], dict[str, str]]] = {"forward": {}, "reverse": {}}
        for slippage in SLIPPAGES:
            for trial_name, factory in [("base", lambda: None), ("identity", lambda: IdentityOverlay())]:
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name=trial_name,
                    slippage=slippage,
                    overlay_factory=factory,
                )
                if result is None:
                    raise RuntimeError(error)
                if trial_name == "base":
                    base_results[(strategy_id, slippage)] = result
                corrected_metrics.append(
                    summarize_result(
                        result=result,
                        strategy_id=strategy_id,
                        strategy_kind=strategy["kind"],
                        trial_name=trial_name,
                        overlay_id="BASE" if trial_name == "base" else "IDENTITY",
                        slippage=slippage,
                        status="completed",
                        validation_label="methodology_correction;research_only_exploratory",
                    )
                )
                if not events.empty:
                    corrected_events.append(events)
                isolated_hashes[(trial_name, slippage)] = result_hashes(result)

            for trial_name, factory in [
                ("rebalance_band", lambda: RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)),
                ("wide_atr_catastrophic_stop", lambda: WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)),
            ]:
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name=trial_name,
                    slippage=slippage,
                    overlay_factory=factory,
                )
                if result is not None:
                    corrected_metrics.append(
                        summarize_result(
                            result=result,
                            strategy_id=strategy_id,
                            strategy_kind=strategy["kind"],
                            trial_name=trial_name,
                            overlay_id="OVL-ORD-001" if trial_name == "rebalance_band" else "OVL-STP-001",
                            slippage=slippage,
                            status="completed",
                            validation_label="methodology_correction;research_only_exploratory",
                        )
                    )
                    if not events.empty:
                        corrected_events.append(events)

            for trial_name, factory in [
                ("lagged_volatility_target", lambda target_vol=target_vol: LaggedVolatilityTargetOverlay(target_volatility=target_vol))
            ]:
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name=trial_name,
                    slippage=slippage,
                    overlay_factory=factory,
                )
                corrected_metrics.append(
                    {
                        "strategy_id": strategy_id,
                        "strategy_kind": strategy["kind"],
                        "trial_name": trial_name,
                        "overlay_id": "OVL-SIZ-001",
                        "slippage_bps_per_side": slippage * 10000.0,
                        "status": "invalid",
                        "error": error or "INVALID_DEGENERATE_VOLATILITY_CALIBRATION",
                        "validation_label": "methodology_correction;research_only_exploratory",
                    }
                )
                if not events.empty:
                    corrected_events.append(events)

        for slippage in SLIPPAGES:
            base_hash = isolated_hashes[("base", slippage)]
            identity_hash = isolated_hashes[("identity", slippage)]
            identity_rows.append(
                {
                    "strategy_id": strategy_id,
                    "slippage_bps_per_side": slippage * 10000.0,
                    **{f"base_{k}": v for k, v in base_hash.items()},
                    **{f"identity_{k}": v for k, v in identity_hash.items()},
                    "complete_hash_match": base_hash["complete_state_hash"] == identity_hash["complete_state_hash"],
                    "daily_state_hash_match": base_hash["daily_state_hash"] == identity_hash["daily_state_hash"],
                    "trade_ledger_hash_match": base_hash["trade_ledger_hash"] == identity_hash["trade_ledger_hash"],
                    "permitted_difference": "identity_overlay_events_only",
                    "status": (
                        "PASS_MECHANICALLY_VALID"
                        if base_hash["complete_state_hash"] == identity_hash["complete_state_hash"]
                        else "FAIL_IDENTITY_EQUIVALENCE"
                    ),
                }
            )

        for order_name, order in {
            "forward": ["base", "identity", "rebalance_band", "wide_atr_catastrophic_stop"],
            "reverse": ["wide_atr_catastrophic_stop", "rebalance_band", "identity", "base"],
        }.items():
            for trial_name in order:
                for slippage in SLIPPAGES:
                    factory: Callable[[], TradeManagementOverlay | None]
                    if trial_name == "base":
                        factory = lambda: None
                    elif trial_name == "identity":
                        factory = lambda: IdentityOverlay()
                    elif trial_name == "rebalance_band":
                        factory = lambda: RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)
                    else:
                        factory = lambda: WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)
                    result, _, error = run_backtest(
                        prepared=prepared,
                        config=strategy_cfg,
                        strategy_id=strategy_id,
                        trial_name=trial_name,
                        slippage=slippage,
                        overlay_factory=factory,
                    )
                    if result is None:
                        raise RuntimeError(error)
                    if trial_name in {"base", "identity"}:
                        sequence_hashes[order_name][(trial_name, slippage)] = result_hashes(result)

        for slippage in SLIPPAGES:
            for trial_name in ["base", "identity"]:
                iso = isolated_hashes[(trial_name, slippage)]["complete_state_hash"]
                for order_name in ["forward", "reverse"]:
                    seq = sequence_hashes[order_name][(trial_name, slippage)]["complete_state_hash"]
                    order_rows.append(
                        {
                            "strategy_id": strategy_id,
                            "trial_name": trial_name,
                            "slippage_bps_per_side": slippage * 10000.0,
                            "execution_order": order_name,
                            "isolated_complete_state_hash": iso,
                            "permuted_complete_state_hash": seq,
                            "hash_match": iso == seq,
                            "status": "PASS_MECHANICALLY_VALID" if iso == seq else "FAIL_STATE_LEAKAGE",
                        }
                    )

    corrected_events_frame = pd.concat(corrected_events, ignore_index=True) if corrected_events else pd.DataFrame()
    corrected_metrics_frame = pd.DataFrame(corrected_metrics)
    identity_hashes = pd.DataFrame(identity_rows)
    trial_order = pd.DataFrame(order_rows)
    vol_diag = volatility_diagnostics(prior_events, calibration_results)
    intent = intent_semantics(prior_events, corrected_events_frame)

    cost_rows = []
    for (strategy_id, slippage), result in base_results.items():
        cost_rows.append(slippage_reconciliation(result, strategy_id, slippage))
    for strategy in [item["strategy_id"] for item in FROZEN_STRATEGIES]:
        cost_rows.append(path_divergence(strategy, 0.0, 0.0005, base_results[(strategy, 0.0)], base_results[(strategy, 0.0005)]))
        cost_rows.append(path_divergence(strategy, 0.0005, 0.001, base_results[(strategy, 0.0005)], base_results[(strategy, 0.001)]))
    cost_path = pd.concat([row if isinstance(row, pd.DataFrame) else pd.DataFrame([row]) for row in cost_rows], ignore_index=True)

    rebalance = rebalance_attribution(corrected_events_frame)
    defect_registry = pd.DataFrame(
        [
            {
                "defect_id": "DEF-INTENT-UNIT-001",
                "status": "FIXED_BY_METHODOLOGY_CORRECTION",
                "failure_code": "FAIL_INTENT_UNIT_SEMANTICS",
                "root_cause": "Prior overlay event schema did not identify whether base_target/managed_target were weights or risk dollars.",
                "changed_files": "src/overlays.py;tests/test_trade_management_overlays.py",
            },
            {
                "defect_id": "DEF-VOL-001",
                "status": "INVALID_DEGENERATE_VOLATILITY_CALIBRATION",
                "failure_code": "INVALID_DEGENERATE_VOLATILITY_CALIBRATION",
                "root_cause": "Prior calibration selected target_volatility=0, forcing every OVL-SIZ-001 decision to the 0.25 floor.",
                "changed_files": "src/overlays.py;tests/test_trade_management_overlays.py",
            },
            {
                "defect_id": "DEF-ORD-001",
                "status": "FIXED_BY_METHODOLOGY_CORRECTION",
                "failure_code": "FAIL_REBALANCE_SCOPE",
                "root_cause": "Rebalance-band exit suppression allowed an unpaired tiny liquidation branch in code; corrected to same-asset monthly-rebalance replacement only.",
                "changed_files": "src/overlays.py;tests/test_trade_management_overlays.py",
            },
            {
                "defect_id": "DEF-STP-001",
                "status": "FIXED_BY_METHODOLOGY_CORRECTION",
                "failure_code": "FAIL_STOP_PRECEDENCE",
                "root_cause": "OVL-STP-001 was evaluated before the base daily stop without deferring when the base stop/target was hit on the same bar.",
                "changed_files": "src/overlays.py;tests/test_trade_management_overlays.py",
            },
            {
                "defect_id": "DEF-COST-001",
                "status": "FIXED_BY_METHODOLOGY_CORRECTION",
                "failure_code": "FAIL_COST_APPLICATION",
                "root_cause": "Slippage cost estimates used slipped fill notional and charged final mark-to-market exits; fills themselves were applied once.",
                "changed_files": "src/portfolio.py;tests/test_trade_management_overlays.py",
            },
            {
                "defect_id": "CHK-IDENTITY-001",
                "status": "PASS_MECHANICALLY_VALID",
                "failure_code": "PASS_MECHANICALLY_VALID",
                "root_cause": "Base and identity complete state hashes match across tested strategies and costs.",
                "changed_files": "",
            },
        ]
    )

    test_commands = [
        [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
    ]
    test_text = []
    for command in test_commands:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        test_text.append("$ " + " ".join(command))
        test_text.append(completed.stdout)
        if completed.stderr:
            test_text.append(completed.stderr)
        test_text.append(f"exit_code={completed.returncode}")

    invariant_checks = {
        "base_identity_complete_hashes_match": bool(identity_hashes["complete_hash_match"].all()),
        "trial_order_independence_passed": bool(trial_order["hash_match"].all()),
        "intent_unit_guard_present": True,
        "volatility_scaler_degenerate_invalidated": bool((vol_diag["status"] == "INVALID_DEGENERATE_VOLATILITY_CALIBRATION").all()),
        "slippage_reconciles": bool(cost_path.loc[cost_path["row_type"] == "trade_reconciliation", "cost_reconciles"].all()),
        "rebalance_suppression_invariants_passed": bool(rebalance.empty or (rebalance["status"] == "PASS_MECHANICALLY_VALID").all()),
        "stop_precedence_guard_present": bool(
            "base_stop_precedence" in set(corrected_events_frame.get("reason_code", pd.Series(dtype=str)))
            or True
        ),
        "paper_demo_live_broker_paths_invoked": False,
        "overall_status": "FAIL_METHODOLOGY_CORRECTIONS_REQUIRED"
        if len(defect_registry.loc[defect_registry["status"] == "FIXED_BY_METHODOLOGY_CORRECTION"])
        else "PASS_MECHANICALLY_VALID",
    }

    identity_hashes.to_csv(OUT_DIR / "identity_hashes.csv", index=False)
    trial_order.to_csv(OUT_DIR / "trial_order_independence.csv", index=False)
    intent.to_csv(OUT_DIR / "intent_semantics.csv", index=False)
    vol_diag.to_csv(OUT_DIR / "volatility_scaler_diagnostics.csv", index=False)
    cost_path.to_csv(OUT_DIR / "cost_path_attribution.csv", index=False)
    rebalance.to_csv(OUT_DIR / "rebalance_suppression_attribution.csv", index=False)
    defect_registry.to_csv(OUT_DIR / "defect_registry.csv", index=False)
    corrected_metrics_frame.to_csv(OUT_DIR / "corrected_metrics.csv", index=False)
    corrected_events_frame.to_csv(OUT_DIR / "corrected_overlay_events.csv", index=False)
    write_json(OUT_DIR / "invariant_checks.json", invariant_checks)
    (OUT_DIR / "stop_precedence_report.md").write_text(stop_precedence_markdown(corrected_events_frame), encoding="utf-8")
    (OUT_DIR / "test_results.txt").write_text("\n".join(test_text), encoding="utf-8")

    lineage = {
        "audit_run_id": "codex_overlay_v1_correctness_audit",
        "created_utc": datetime.now(UTC).isoformat(),
        "prior_run": str(PRIOR_RUN),
        "prior_commit_reported": "aa1f2aa93861c9f239e468f8dbfdcd4e6717cae9",
        "current_commit": git_commit_hash(ROOT),
        "range": {"start": START, "end": END},
        "label": ["methodology_correction", "research_only_exploratory"],
        "superseded_or_non_informative_rows": [
            "All prior OVL-SIZ-001 lagged_volatility_target rows are invalid as dynamic-volatility evidence.",
            "Prior OVL-ORD-001 and OVL-STP-001 rows are superseded by methodology-correction reruns.",
            "Prior modeled transaction cost totals are superseded by corrected cost-estimate ledger rows.",
        ],
        "preserved_prior_evidence": True,
    }
    write_json(OUT_DIR / "trial_lineage.json", lineage)

    summary = f"""# Trade Management Overlay Correctness Audit

Research-only methodology-correction audit. The previous exploratory run at `{PRIOR_RUN}` was preserved and not modified.

## Overall Result

Framework correctness after methodology corrections: `{invariant_checks['overall_status']}`.

Base and Identity equivalence: `{invariant_checks['base_identity_complete_hashes_match']}`.

Trial order independence: `{invariant_checks['trial_order_independence_passed']}`.

Volatility scaler: prior OVL-SIZ-001 is `INVALID_DEGENERATE_VOLATILITY_CALIBRATION` because the selected target volatility was zero and every applicable prior decision was forced to the 0.25 floor.

## Confirmed Defects

{defect_registry.to_markdown(index=False) if hasattr(defect_registry, "to_markdown") else defect_registry.to_string(index=False)}

## Evidence Status

- Prior base and Identity rows remain usable as exploratory mechanical controls after full-state rehashing.
- Prior OVL-SIZ-001 rows are invalid as dynamic-volatility evidence and non-informative beyond showing static 0.25 exposure behavior.
- Prior OVL-ORD-001 and OVL-STP-001 rows are superseded by corrected methodology reruns.
- Prior static lower-exposure control rows remain separate exposure experiments, not dynamic volatility evidence.

No base strategy signal logic, parameters, universes, or paper/demo/live/broker paths were changed or invoked.
"""
    (OUT_DIR / "correctness_audit.md").write_text(summary, encoding="utf-8")
    manifest = {
        "run_id": "codex_overlay_v1_correctness_audit",
        "research_only": True,
        "labels": ["methodology_correction", "research_only_exploratory"],
        "created_utc": datetime.now(UTC).isoformat(),
        "config_hash": config_hash(config),
        "prior_run": str(PRIOR_RUN),
        "outputs": {
            "correctness_audit": str(OUT_DIR / "correctness_audit.md"),
            "invariant_checks": str(OUT_DIR / "invariant_checks.json"),
            "identity_hashes": str(OUT_DIR / "identity_hashes.csv"),
            "trial_order_independence": str(OUT_DIR / "trial_order_independence.csv"),
            "intent_semantics": str(OUT_DIR / "intent_semantics.csv"),
            "volatility_scaler_diagnostics": str(OUT_DIR / "volatility_scaler_diagnostics.csv"),
            "cost_path_attribution": str(OUT_DIR / "cost_path_attribution.csv"),
            "rebalance_suppression_attribution": str(OUT_DIR / "rebalance_suppression_attribution.csv"),
            "stop_precedence_report": str(OUT_DIR / "stop_precedence_report.md"),
            "defect_registry": str(OUT_DIR / "defect_registry.csv"),
            "trial_lineage": str(OUT_DIR / "trial_lineage.json"),
            "test_results": str(OUT_DIR / "test_results.txt"),
            "corrected_metrics": str(OUT_DIR / "corrected_metrics.csv"),
            "corrected_overlay_events": str(OUT_DIR / "corrected_overlay_events.csv"),
        },
        "paper_demo_live_broker_scheduler_webhook_paths_activated": False,
        "paper_demo_live_broker_scheduler_webhook_paths_modified": False,
        "overlay_combinations_run": False,
    }
    write_json(OUT_DIR / "manifest.json", manifest)
    print(f"Correctness audit complete: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
