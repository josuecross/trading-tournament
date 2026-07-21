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

from run_trade_management_overlay_canonical_exploratory import json_ready, markdown_table, result_hashes
from run_trade_management_overlay_comparison import _strategy_only_config, _strategy_source_hash, summarize_result
from src.backtester import Backtester, BacktestResult
from src.data import DataLoadResult, load_market_data
from src.indicators import prepare_indicators
from src.overlays import IdentityOverlay, RebalanceBandOverlay, TradeManagementOverlay, stable_hash
from src.utils import config_hash, git_commit_hash, load_config, sha256_file, write_json


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "rebalance_band_robustness_v1"
CANONICAL_SOURCE = ROOT / "reports" / "trade_management" / "codex_overlay_v1_canonical_exploratory"
FAMILY_PORTABILITY_SOURCE = ROOT / "reports" / "trade_management" / "family_portability_batch_v1"
LABEL = "timeframe_diagnostic;research_only_robustness"
SOURCE_FRAMEWORK_STATUS = "PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION"

STRATEGIES = {
    "N2_absolute_trend_taa": {
        "family_id": "absolute_trend_taa_anchor",
        "economic_family_id": "absolute_trend_taa",
        "kind": "monthly_periodic_target_weight",
        "selection_reason": "exploratory_effect_followup",
        "lineage_note": "Previously tested responsive anchor with nonzero OVL-ORD-001 decisions.",
        "implicit_required_symbols": [],
    },
    "N4_inverse_vol_defensive_allocation": {
        "family_id": "inverse_vol_defensive_allocation",
        "economic_family_id": "inverse_vol_defensive_allocation",
        "kind": "monthly_periodic_target_weight",
        "selection_reason": "exploratory_effect_followup",
        "lineage_note": "Selected because family-portability exploratory batch showed nonzero OVL-ORD-001 decisions.",
        "implicit_required_symbols": ["BIL"],
    },
}

SLIPPAGES = [0.0, 0.0005, 0.001]
OVERLAY_CONFIG = {"min_weight_delta": 0.01, "min_nav_order_pct": 0.001}
OVERLAY_CONFIGS = {
    "BASE": {},
    "IDENTITY": {},
    "OVL-ORD-001": OVERLAY_CONFIG,
}

INDEPENDENT_PERIODS = {"PRE_ORIGINAL_WINDOW", "ORIGINAL_EXPLORATORY_WINDOW", "POST_ORIGINAL_WINDOW"}
ORIGINAL_REQUEST = {"start": "2017-01-01", "end": "2020-12-31"}
POST_REQUEST_START = "2021-01-01"


def parse_json_cell(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def result_key(strategy_id: str, period_id: str, trial_name: str, slippage: float) -> tuple[str, str, str, float]:
    return strategy_id, period_id, trial_name, slippage


def strategy_symbols(config: dict[str, Any], strategy_id: str) -> list[str]:
    cfg = config.get("strategies", {}).get(strategy_id, {})
    symbols: set[str] = set()
    for key in ["assets", "risk_assets", "defensive_assets", "risk_off_allowed_assets"]:
        symbols.update(cfg.get(key, []) or [])
    symbols.update(STRATEGIES[strategy_id].get("implicit_required_symbols", []))
    return sorted(symbols)


def data_coverage_for_strategy(
    config: dict[str, Any],
    data_load: DataLoadResult,
    strategy_id: str,
) -> dict[str, Any]:
    symbols = strategy_symbols(config, strategy_id)
    coverage = data_load.coverage.copy()
    rows = coverage[coverage["symbol"].isin(symbols)].copy()
    missing = sorted(set(symbols) - set(rows.loc[rows["status"] == "valid", "symbol"]))
    if missing:
        return {
            "strategy_id": strategy_id,
            "symbols": symbols,
            "available": False,
            "raw_start": "",
            "raw_end": "",
            "missing_symbols": missing,
            "file_rows": rows.to_dict(orient="records"),
            "data_hash": stable_hash({"symbols": symbols, "missing": missing}),
        }
    first_dates = pd.to_datetime(rows["first_date"])
    last_dates = pd.to_datetime(rows["last_date"])
    file_rows = rows.sort_values("symbol").to_dict(orient="records")
    return {
        "strategy_id": strategy_id,
        "symbols": symbols,
        "available": True,
        "raw_start": first_dates.max().date().isoformat(),
        "raw_end": last_dates.min().date().isoformat(),
        "missing_symbols": [],
        "file_rows": file_rows,
        "data_hash": stable_hash(
            [
                {
                    "symbol": row["symbol"],
                    "first_date": row["first_date"],
                    "last_date": row["last_date"],
                    "row_count": row["row_count"],
                    "cache_file_hash": row["cache_file_hash"],
                }
                for row in file_rows
            ]
        ),
    }


def requested_periods(raw_start: str, raw_end: str) -> list[dict[str, str]]:
    return [
        {
            "period_id": "PRE_ORIGINAL_WINDOW",
            "requested_start": raw_start,
            "requested_end": "2017-12-31",
            "chronological_role": "pre_original",
        },
        {
            "period_id": "ORIGINAL_EXPLORATORY_WINDOW",
            "requested_start": ORIGINAL_REQUEST["start"],
            "requested_end": ORIGINAL_REQUEST["end"],
            "chronological_role": "original_exploratory",
        },
        {
            "period_id": "POST_ORIGINAL_WINDOW",
            "requested_start": POST_REQUEST_START,
            "requested_end": raw_end,
            "chronological_role": "post_original",
        },
        {
            "period_id": "FULL_AVAILABLE_RANGE",
            "requested_start": raw_start,
            "requested_end": raw_end,
            "chronological_role": "full_available_not_independent",
        },
    ]


def freeze_ranges(
    *,
    config: dict[str, Any],
    prepared: dict[str, pd.DataFrame],
    data_coverage: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    warmup = int(config["project"]["warmup_days"])
    for strategy_id, coverage in data_coverage.items():
        strategy_config = _strategy_only_config(config, strategy_id)
        backtester = Backtester(prepared, strategy_config)
        for period in requested_periods(coverage["raw_start"], coverage["raw_end"]):
            calendar = backtester._calendar(period["requested_start"], period["requested_end"])
            effective = backtester._effective_calendar(period["requested_start"], period["requested_end"])
            unavailable_reason = ""
            if not coverage["available"]:
                unavailable_reason = "missing_required_data"
            elif not effective:
                unavailable_reason = "insufficient_calendar_after_warmup"
            elif len(effective) < 40:
                unavailable_reason = "insufficient_effective_activity_window"
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "family_id": STRATEGIES[strategy_id]["family_id"],
                    "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
                    "period_id": period["period_id"],
                    "chronological_role": period["chronological_role"],
                    "is_independent_chronological_period": period["period_id"] in INDEPENDENT_PERIODS,
                    "requested_start": period["requested_start"],
                    "requested_end": period["requested_end"],
                    "raw_data_intersection_start": coverage["raw_start"],
                    "raw_data_intersection_end": coverage["raw_end"],
                    "effective_start": effective[0].date().isoformat() if effective else "",
                    "effective_end": effective[-1].date().isoformat() if effective else "",
                    "raw_calendar_days": len(calendar),
                    "warmup_days": warmup,
                    "effective_trading_days": len(effective),
                    "availability_status": "available" if not unavailable_reason else "unavailable",
                    "unavailable_reason": unavailable_reason,
                    "required_symbols": ",".join(coverage["symbols"]),
                    "data_hash": coverage["data_hash"],
                }
            )
    return pd.DataFrame(rows)


def economic_family_mapping() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_id": "N1_dual_momentum_taa",
                "strategy_family_id": "cross_asset_dual_momentum_taa",
                "economic_family_id": "dual_momentum_taa",
                "independent_economic_family_confirmation_unit": False,
                "notes": "Grouped with N3 for economic-family counting; preserve separate strategy implementation ID.",
            },
            {
                "strategy_id": "N3_dual_momentum_vol_scaled",
                "strategy_family_id": "cross_asset_dual_momentum_vol_scaled_taa",
                "economic_family_id": "dual_momentum_taa",
                "independent_economic_family_confirmation_unit": False,
                "notes": "Grouped with N1 for economic-family counting; preserve separate strategy implementation ID.",
            },
            {
                "strategy_id": "N2_absolute_trend_taa",
                "strategy_family_id": "absolute_trend_taa_anchor",
                "economic_family_id": "absolute_trend_taa",
                "independent_economic_family_confirmation_unit": True,
                "notes": "Responsive anchor follow-up; exact-combination robustness diagnostic only.",
            },
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "strategy_family_id": "inverse_vol_defensive_allocation",
                "economic_family_id": "inverse_vol_defensive_allocation",
                "independent_economic_family_confirmation_unit": True,
                "notes": "Exact-combination robustness diagnostic only; no family-level portability claim.",
            },
            {
                "strategy_id": "C_swing_trend_pullback",
                "strategy_family_id": "daily_swing_pullback_reversal",
                "economic_family_id": "daily_swing_pullback_reversal",
                "independent_economic_family_confirmation_unit": True,
                "notes": "C + OVL-EXT-001(5 bars) exact combination corrected as closed; time-stop family remains open.",
            },
        ]
    )


def prior_status_corrections() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_id": "N4_inverse_vol_defensive_allocation",
                "overlay_id": "OVL-ORD-001",
                "overlay_parameters": json.dumps(OVERLAY_CONFIG, sort_keys=True),
                "previous_status": "PROMISING_FOR_DEEPER_EXPLORATION",
                "corrected_status": "EXACT_COMBINATION_CANDIDATE_FOR_ROBUSTNESS",
                "scope": "exact_strategy_overlay_combination_only",
                "do_not_infer": "inverse_volatility_defensive_allocation_family_portability",
                "reason": "One strategy is not an economic-family portability proof; prior nonzero effect only authorizes exact-combination robustness follow-up.",
            },
            {
                "strategy_id": "C_swing_trend_pullback",
                "overlay_id": "OVL-EXT-001",
                "overlay_parameters": json.dumps({"max_completed_bars": 5}, sort_keys=True),
                "previous_status": "PROMISING_FOR_DEEPER_EXPLORATION",
                "corrected_status": "MIXED_NO_MATERIAL_EDGE_WINNER_TRUNCATION",
                "scope": "exact_strategy_overlay_combination_closed_only",
                "do_not_infer": "time_stop_overlay_family_closed",
                "reason": "Returns remained negative, improvements were small, winners were exited early more often than losing trades were shortened, turnover rose at 0 and 5 bps, and risk-adjusted improvement was inconsistent.",
            },
        ]
    )


def pre_registered_manifest(
    *,
    config: dict[str, Any],
    data_coverage: dict[str, dict[str, Any]],
    range_coverage: pd.DataFrame,
) -> dict[str, Any]:
    selected = []
    for strategy_id, meta in STRATEGIES.items():
        selected.append(
            {
                "strategy_id": strategy_id,
                "family_id": meta["family_id"],
                "economic_family_id": meta["economic_family_id"],
                "overlay_id": "OVL-ORD-001",
                "overlay_parameters": copy.deepcopy(OVERLAY_CONFIG),
                "selection_reason": meta["selection_reason"],
                "selection_lineage": meta["lineage_note"],
                "selection_is_adaptive_from_prior_exploratory_results": True,
                "promotion_or_validation_claim": False,
            }
        )
    return {
        "run_id": "rebalance_band_robustness_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "labels": ["timeframe_diagnostic", "research_only_robustness"],
        "research_only": True,
        "clean_holdout_validation": False,
        "optimization_or_tuning": False,
        "selection_reason": "exploratory_effect_followup",
        "selection_note": "N2 and N4 were selected adaptively because prior exploratory runs showed nonzero rebalance-band overlay decisions.",
        "source_framework_status": SOURCE_FRAMEWORK_STATUS,
        "source_of_truth_packages_preserved": [str(CANONICAL_SOURCE), str(FAMILY_PORTABILITY_SOURCE)],
        "selected_strategy_overlay_pairs": selected,
        "chronological_windows": range_coverage.to_dict(orient="records"),
        "slippage_bps_per_side": [slippage * 10000.0 for slippage in SLIPPAGES],
        "overlay_parameter_mapping": {"OVL-ORD-001": copy.deepcopy(OVERLAY_CONFIG), "IDENTITY": {}},
        "overlay_configuration_hashes": {
            overlay_id: stable_hash(config_payload) for overlay_id, config_payload in OVERLAY_CONFIGS.items()
        },
        "repository_commit": git_commit_hash(ROOT),
        "config_hash": config_hash(config),
        "strategy_configuration_hashes": {
            strategy_id: stable_hash(config.get("strategies", {}).get(strategy_id, {})) for strategy_id in STRATEGIES
        },
        "strategy_source_hashes": {
            strategy_id: _strategy_source_hash(config, strategy_id) for strategy_id in STRATEGIES
        },
        "overlay_implementation_hash": sha256_file(ROOT / "src" / "overlays.py"),
        "backtester_implementation_hash": sha256_file(ROOT / "src" / "backtester.py"),
        "portfolio_implementation_hash": sha256_file(ROOT / "src" / "portfolio.py"),
        "data_files_and_coverage": data_coverage,
        "benchmark_assumptions": config.get("benchmarks", {}),
        "cost_assumptions": {
            "slippage_bps_per_side": [slippage * 10000.0 for slippage in SLIPPAGES],
            "fees": "none_in_current_backtester",
            "modeled_transaction_cost_source": "entry_exit_slippage_paid_estimate",
        },
        "no_overlay_variants_or_ablations": True,
        "no_overlay_combinations": True,
        "ovl_siz_excluded": True,
        "ovl_stp_excluded": True,
        "c_time_stop_not_rerun": True,
        "n1_n3_not_rerun": True,
        "paper_demo_live_broker_scheduler_webhook_paths_activated": False,
        "paper_demo_live_broker_scheduler_webhook_paths_modified": False,
    }


def overlay_factory(trial_name: str) -> Callable[[], TradeManagementOverlay | None]:
    if trial_name == "base":
        return lambda: None
    if trial_name == "identity":
        return lambda: IdentityOverlay()
    if trial_name == "rebalance_band":
        return lambda: RebalanceBandOverlay(**OVERLAY_CONFIG)
    raise ValueError(f"Unsupported trial {trial_name}")


def run_backtest(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    strategy_id: str,
    period_id: str,
    requested_start: str,
    requested_end: str,
    trial_name: str,
    slippage: float,
) -> tuple[BacktestResult | None, pd.DataFrame, str]:
    strategy_config = _strategy_only_config(config, strategy_id)
    strategy_hash = _strategy_source_hash(config, strategy_id)
    try:
        overlay = overlay_factory(trial_name)()
        result = Backtester(prepared, strategy_config).run(
            f"{period_id}_{trial_name}",
            requested_start,
            requested_end,
            slippage,
            lightweight_outputs=True,
            overlay=overlay,
            run_id=f"rebalance_band_robustness_v1_{strategy_id}_{period_id}_{trial_name}_{int(round(slippage * 10000))}bps",
            base_strategy_id=strategy_id,
            base_strategy_hash=strategy_hash,
        )
        events = result.overlay_events.copy()
        if not events.empty:
            events.insert(0, "period_id", period_id)
            events.insert(0, "trial_name", trial_name)
            events.insert(0, "strategy_id", strategy_id)
            events.insert(0, "slippage_bps_per_side", slippage * 10000.0)
        return result, events, ""
    except Exception as exc:
        return None, pd.DataFrame(), str(exc)


def exit_count(trades: pd.DataFrame, reasons: set[str]) -> int:
    if trades.empty or "exit_reason" not in trades:
        return 0
    return int(trades["exit_reason"].isin(reasons).sum())


def trailing_exit_count(trades: pd.DataFrame) -> int:
    if trades.empty or "exit_reason" not in trades:
        return 0
    stop_trades = trades[trades["exit_reason"].isin({"stop_loss", "stop_loss_gap"})].copy()
    if stop_trades.empty:
        return 0
    initial = pd.to_numeric(stop_trades.get("stop_price_initial", np.nan), errors="coerce")
    final = pd.to_numeric(stop_trades.get("stop_price_final", np.nan), errors="coerce")
    return int((final > initial + 1e-9).sum())


def suppressed_stats(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {
            "suppressed_decision_count": 0,
            "average_suppressed_weight_difference": 0.0,
            "maximum_suppressed_weight_difference": 0.0,
        }
    suppress = events[events["decision_type"] == "suppress_order"].copy()
    deltas = []
    for _, event in suppress.iterrows():
        proposed = parse_json_cell(event.get("proposed_order"))
        value = proposed.get("target_weight_delta")
        if value is not None and np.isfinite(float(value)):
            deltas.append(float(value))
    return {
        "suppressed_decision_count": int(len(suppress)),
        "average_suppressed_weight_difference": float(np.mean(deltas)) if deltas else 0.0,
        "maximum_suppressed_weight_difference": float(np.max(deltas)) if deltas else 0.0,
    }


def failed_metric_row(
    *,
    strategy_id: str,
    period_id: str,
    trial_name: str,
    overlay_id: str,
    slippage: float,
    error: str,
) -> dict[str, Any]:
    row = {
        "strategy_id": strategy_id,
        "family_id": STRATEGIES[strategy_id]["family_id"],
        "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
        "period_id": period_id,
        "strategy_kind": STRATEGIES[strategy_id]["kind"],
        "trial_name": trial_name,
        "overlay_id": overlay_id,
        "slippage_bps_per_side": slippage * 10000.0,
        "status": "failed",
        "execution_status": "failed",
        "error": error,
        "validation_label": LABEL,
        "research_classification": "FAILED",
    }
    for key in [
        "start",
        "end",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "max_drawdown_pct",
        "drawdown_duration_days",
        "sharpe",
        "sortino",
        "return_to_drawdown",
        "average_gross_exposure",
        "maximum_gross_exposure",
        "average_cash_weight",
        "turnover",
        "number_of_orders",
        "number_of_fills",
        "modeled_transaction_cost",
        "corrected_modeled_transaction_cost",
        "number_skipped_or_resized_orders",
        "number_stop_events",
        "number_target_exit_events",
        "number_trailing_exit_events",
        "number_time_exit_events",
        "average_holding_period",
        "final_equity",
        "number_of_trades",
        "suppressed_decision_count",
        "average_suppressed_weight_difference",
        "maximum_suppressed_weight_difference",
    ]:
        row[key] = np.nan
    return row


def metric_row(
    *,
    result: BacktestResult | None,
    events: pd.DataFrame,
    strategy_id: str,
    period_id: str,
    trial_name: str,
    overlay_id: str,
    slippage: float,
    error: str = "",
) -> dict[str, Any]:
    if result is None:
        return failed_metric_row(
            strategy_id=strategy_id,
            period_id=period_id,
            trial_name=trial_name,
            overlay_id=overlay_id,
            slippage=slippage,
            error=error,
        )
    row = summarize_result(
        result=result,
        strategy_id=strategy_id,
        strategy_kind=STRATEGIES[strategy_id]["kind"],
        trial_name=trial_name,
        overlay_id=overlay_id,
        slippage=slippage,
        status="completed",
        validation_label=LABEL,
    )
    row.update(
        {
            "family_id": STRATEGIES[strategy_id]["family_id"],
            "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
            "period_id": period_id,
            "execution_status": "completed",
            "research_classification": "MECHANICAL_CONTROL" if overlay_id in {"BASE", "IDENTITY"} else "ROBUSTNESS_DIAGNOSTIC",
            "overlay_config_hash": stable_hash(OVERLAY_CONFIGS.get(overlay_id, {})),
            "overlay_config": json.dumps(OVERLAY_CONFIGS.get(overlay_id, {}), sort_keys=True),
            "corrected_modeled_transaction_cost": row["modeled_transaction_cost"],
            "number_target_exit_events": exit_count(result.trades, {"target_hit"}),
            "number_trailing_exit_events": trailing_exit_count(result.trades),
        }
    )
    row.update(suppressed_stats(events))
    return row


def add_overlay_minus_base_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    delta_columns = [
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown_pct",
        "drawdown_duration_days",
        "sharpe",
        "sortino",
        "return_to_drawdown",
        "average_gross_exposure",
        "maximum_gross_exposure",
        "average_cash_weight",
        "turnover",
        "number_of_orders",
        "number_of_fills",
        "number_of_trades",
        "corrected_modeled_transaction_cost",
        "average_holding_period",
        "number_stop_events",
        "number_target_exit_events",
        "number_trailing_exit_events",
    ]
    for column in delta_columns:
        metrics[f"overlay_minus_base_{column}"] = np.nan
    for idx, row in metrics.iterrows():
        if row["trial_name"] == "base":
            continue
        base = metrics[
            (metrics["strategy_id"] == row["strategy_id"])
            & (metrics["period_id"] == row["period_id"])
            & (metrics["trial_name"] == "base")
            & (metrics["slippage_bps_per_side"] == row["slippage_bps_per_side"])
        ]
        if base.empty:
            continue
        base_row = base.iloc[0]
        for column in delta_columns:
            metrics.at[idx, f"overlay_minus_base_{column}"] = row.get(column, np.nan) - base_row.get(column, np.nan)
    return metrics


def trade_descriptor(trade: pd.Series | None) -> str:
    if trade is None or trade.empty:
        return ""
    return (
        f"{trade.get('strategy','')}:{trade.get('symbol','')}:"
        f"{trade.get('entry_signal_date','')}:{trade.get('entry_date','')}:"
        f"{trade.get('exit_date','')}:{trade.get('exit_reason','')}"
    )


def trade_sequence_after(result: BacktestResult, timestamp: pd.Timestamp) -> list[str]:
    if result.trades.empty:
        return []
    trades = result.trades.copy()
    trades["_entry_dt"] = pd.to_datetime(trades["entry_date"])
    trades["_exit_dt"] = pd.to_datetime(trades["exit_date"])
    trades = trades[(trades["_entry_dt"] >= timestamp) | (trades["_exit_dt"] >= timestamp)]
    return [trade_descriptor(row) for _, row in trades.sort_values(["_entry_dt", "_exit_dt", "symbol"]).iterrows()]


def first_trade_divergence_after(base: BacktestResult, overlay: BacktestResult, timestamp: pd.Timestamp) -> str:
    left = trade_sequence_after(base, timestamp)
    right = trade_sequence_after(overlay, timestamp)
    for idx, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return f"sequence={idx} base={a} overlay={b}"
    if len(left) != len(right):
        return f"length_changed base={len(left)} overlay={len(right)}"
    return ""


def first_trade_after(result: BacktestResult, timestamp: pd.Timestamp, asset: str) -> pd.Series | None:
    if result.trades.empty:
        return None
    trades = result.trades.copy()
    trades["_entry_dt"] = pd.to_datetime(trades["entry_date"])
    trades["_exit_dt"] = pd.to_datetime(trades["exit_date"])
    trades = trades[(trades["symbol"] == asset) & ((trades["_entry_dt"] >= timestamp) | (trades["_exit_dt"] >= timestamp))]
    if trades.empty:
        return None
    return trades.sort_values(["_exit_dt", "_entry_dt", "trade_id"]).iloc[0]


def spanning_trade(result: BacktestResult, timestamp: pd.Timestamp, asset: str, trade_id: Any = None) -> pd.Series | None:
    if result.trades.empty:
        return None
    trades = result.trades.copy()
    trades["_entry_dt"] = pd.to_datetime(trades["entry_date"])
    trades["_exit_dt"] = pd.to_datetime(trades["exit_date"])
    if trade_id not in (None, "", np.nan):
        exact = trades[trades["trade_id"].astype(str) == str(trade_id)]
        if not exact.empty:
            return exact.iloc[0]
    mask = (
        (trades["symbol"] == asset)
        & (trades["_entry_dt"] <= timestamp)
        & (trades["_exit_dt"] >= timestamp)
    )
    if not trades[mask].empty:
        return trades[mask].sort_values(["_exit_dt", "_entry_dt"]).iloc[0]
    return first_trade_after(result, timestamp, asset)


def suppression_groups(events: pd.DataFrame) -> dict[tuple[str, str, float, str, str], dict[str, Any]]:
    suppress = events[events["decision_type"] == "suppress_order"].copy()
    groups: dict[tuple[str, str, float, str, str], dict[str, Any]] = {}
    for _, event in suppress.iterrows():
        key = (
            str(event["strategy_id"]),
            str(event["period_id"]),
            float(event["slippage_bps_per_side"]),
            str(event["timestamp"]),
            str(event["asset"]),
        )
        bucket = groups.setdefault(key, {"entry": None, "exit": None, "events": []})
        bucket["events"].append(event)
        if ":exit:" in str(event.get("signal_id", "")):
            bucket["exit"] = event
        else:
            bucket["entry"] = event
    return groups


def suppression_mechanism(
    *,
    flags: dict[str, Any],
    paired_exit_reentry: bool,
    delta: float,
    state: dict[str, Any],
    subsequent_base_exit_reason: str,
    subsequent_overlay_exit_reason: str,
) -> str:
    mechanisms = []
    if paired_exit_reentry:
        mechanisms.append("economically_redundant_replacement")
        mechanisms.append("lifecycle_state_continuation")
    if flags.get("below_weight_band"):
        mechanisms.append("small_target_adjustment")
    if flags.get("below_nav_order"):
        mechanisms.append("minimum_notional_trade")
    if not paired_exit_reentry and delta >= OVERLAY_CONFIG["min_weight_delta"]:
        mechanisms.append("genuine_allocation_change")
    if state.get("enable_trailing_stop"):
        mechanisms.append("trailing_state_preserved")
    if subsequent_base_exit_reason and subsequent_overlay_exit_reason and subsequent_base_exit_reason != subsequent_overlay_exit_reason:
        mechanisms.append("later_stop_or_target_divergence")
    return ",".join(dict.fromkeys(mechanisms)) or "unclassified_suppression"


def suppressed_event_audit(
    *,
    events: pd.DataFrame,
    results: dict[tuple[str, str, str, float], BacktestResult],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if events.empty:
        return pd.DataFrame(rows)
    groups = suppression_groups(events)
    suppress = events[events["decision_type"] == "suppress_order"].copy()
    for _, event in suppress.iterrows():
        strategy_id = str(event["strategy_id"])
        period_id = str(event["period_id"])
        bps = float(event["slippage_bps_per_side"])
        slippage = bps / 10000.0
        timestamp_text = str(event["timestamp"])
        timestamp = pd.Timestamp(timestamp_text)
        asset = str(event["asset"])
        key = (strategy_id, period_id, bps, timestamp_text, asset)
        group = groups.get(key, {})
        entry_event = group.get("entry")
        exit_event = group.get("exit")
        is_exit = ":exit:" in str(event.get("signal_id", ""))
        paired = entry_event is not None and exit_event is not None
        state = parse_json_cell(event.get("current_position"))
        if not state and exit_event is not None:
            state = parse_json_cell(exit_event.get("current_position"))
        proposed = parse_json_cell(event.get("proposed_order"))
        flags = parse_json_cell(event.get("data_quality_flags"))
        delta = float(proposed.get("target_weight_delta", abs(float(event.get("base_target", 0.0)) - float(event.get("managed_target", 0.0)))) or 0.0)
        base_result = results.get(result_key(strategy_id, period_id, "base", slippage))
        overlay_result = results.get(result_key(strategy_id, period_id, "rebalance_band", slippage))
        next_base = first_trade_after(base_result, timestamp, asset) if base_result is not None else None
        next_overlay = first_trade_after(overlay_result, timestamp, asset) if overlay_result is not None else None
        subsequent_base_exit_reason = str(next_base.get("exit_reason", "")) if next_base is not None else ""
        subsequent_overlay_exit_reason = str(next_overlay.get("exit_reason", "")) if next_overlay is not None else ""
        divergence = (
            first_trade_divergence_after(base_result, overlay_result, timestamp)
            if base_result is not None and overlay_result is not None
            else ""
        )
        rows.append(
            {
                "strategy_id": strategy_id,
                "period_id": period_id,
                "cost_assumption_bps_per_side": bps,
                "timestamp": timestamp.date().isoformat(),
                "asset": asset,
                "event_id": event.get("event_id", ""),
                "decision_event_kind": "suppressed_exit" if is_exit else "suppressed_replacement_entry",
                "exit_signal_id": exit_event.get("signal_id", "") if exit_event is not None else (event.get("signal_id", "") if is_exit else ""),
                "replacement_entry_signal_id": entry_event.get("signal_id", "") if entry_event is not None else (event.get("signal_id", "") if not is_exit else ""),
                "old_position_weight_before_decision": float(event.get("managed_target", np.nan)),
                "frozen_new_target_weight": float(event.get("base_target", np.nan)),
                "absolute_target_current_difference": delta,
                "proposed_order_notional": float(proposed.get("notional_delta", 0.0) or 0.0),
                "suppression_reason": event.get("reason_code", ""),
                "exit_reentry_pair": bool(paired),
                "minimum_trade_only_suppression": bool(flags.get("below_nav_order") and not flags.get("below_weight_band")),
                "bars_held_before_suppression": state.get("bars_held", ""),
                "existing_entry_date": state.get("entry_date", ""),
                "existing_entry_price": state.get("entry_price", ""),
                "existing_stop_price": state.get("stop_price", ""),
                "existing_initial_stop_price": state.get("stop_price_initial", ""),
                "existing_highest_close_trailing_state": state.get("highest_close", ""),
                "existing_trailing_enabled": state.get("enable_trailing_stop", ""),
                "closing_and_reopening_would_reset_lifecycle_state": bool(paired and state),
                "next_base_trade": trade_descriptor(next_base),
                "next_overlay_trade": trade_descriptor(next_overlay),
                "first_subsequent_trade_path_divergence": divergence,
                "subsequent_base_exit_reason": subsequent_base_exit_reason,
                "subsequent_overlay_exit_reason": subsequent_overlay_exit_reason,
                "economically_redundant_replacement": bool(paired),
                "small_target_adjustment": bool(flags.get("below_weight_band")),
                "minimum_notional_trade": bool(flags.get("below_nav_order")),
                "genuine_allocation_change": bool((not paired) and delta >= OVERLAY_CONFIG["min_weight_delta"]),
                "lifecycle_state_continuation": bool(paired and state),
                "later_stop_or_target_divergence": bool(
                    subsequent_base_exit_reason
                    and subsequent_overlay_exit_reason
                    and subsequent_base_exit_reason != subsequent_overlay_exit_reason
                ),
                "mechanism_tags": suppression_mechanism(
                    flags=flags,
                    paired_exit_reentry=bool(paired),
                    delta=delta,
                    state=state,
                    subsequent_base_exit_reason=subsequent_base_exit_reason,
                    subsequent_overlay_exit_reason=subsequent_overlay_exit_reason,
                ),
            }
        )
    return pd.DataFrame(rows)


def invested_days(result: BacktestResult) -> int:
    if result.equity_curve.empty or "gross_exposure" not in result.equity_curve:
        return 0
    return int((pd.to_numeric(result.equity_curve["gross_exposure"], errors="coerce").fillna(0.0) > 1e-9).sum())


def metric_lookup(metrics: pd.DataFrame, strategy_id: str, period_id: str, trial_name: str, bps: float) -> pd.Series | None:
    row = metrics[
        (metrics["strategy_id"] == strategy_id)
        & (metrics["period_id"] == period_id)
        & (metrics["trial_name"] == trial_name)
        & (metrics["slippage_bps_per_side"] == bps)
    ]
    return None if row.empty else row.iloc[0]


def cost_path_decomposition(
    *,
    metrics: pd.DataFrame,
    audit: pd.DataFrame,
    results: dict[tuple[str, str, str, float], BacktestResult],
    range_coverage: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    starting_equity = float(config["project"]["starting_equity"])
    available_ranges = range_coverage[range_coverage["availability_status"] == "available"]
    for _, range_row in available_ranges.iterrows():
        strategy_id = range_row["strategy_id"]
        period_id = range_row["period_id"]
        for slippage in SLIPPAGES:
            bps = slippage * 10000.0
            base = metric_lookup(metrics, strategy_id, period_id, "base", bps)
            overlay = metric_lookup(metrics, strategy_id, period_id, "rebalance_band", bps)
            if base is None or overlay is None:
                continue
            base_result = results.get(result_key(strategy_id, period_id, "base", slippage))
            overlay_result = results.get(result_key(strategy_id, period_id, "rebalance_band", slippage))
            period_audit = audit[
                (audit["strategy_id"] == strategy_id)
                & (audit["period_id"] == period_id)
                & (audit["cost_assumption_bps_per_side"] == bps)
            ]
            suppressed_notional = float(pd.to_numeric(period_audit.get("proposed_order_notional", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
            avoided_orders = int(len(period_audit))
            cost_avoided_dollars = float(base["corrected_modeled_transaction_cost"] - overlay["corrected_modeled_transaction_cost"])
            direct_cost_return_component = 0.0 if bps == 0.0 else cost_avoided_dollars / starting_equity
            return_delta = float(overlay["total_return"] - base["total_return"])
            residual_return_delta = return_delta - direct_cost_return_component
            exposure_delta = float(overlay["average_gross_exposure"] - base["average_gross_exposure"])
            cash_delta = float(overlay["average_cash_weight"] - base["average_cash_weight"])
            invested_delta = (
                invested_days(overlay_result) - invested_days(base_result)
                if base_result is not None and overlay_result is not None
                else np.nan
            )
            if not period_audit.empty and "exit_reentry_pair" in period_audit:
                retained = (
                    period_audit[period_audit["exit_reentry_pair"]]
                    .groupby("asset")
                    .size()
                    .sort_values(ascending=False)
                )
            else:
                retained = pd.Series(dtype=int)
            asset_retained = ";".join(f"{asset}:{count}" for asset, count in retained.items())
            first_divergence = (
                first_trade_divergence_after(base_result, overlay_result, pd.Timestamp(range_row["effective_start"]))
                if base_result is not None and overlay_result is not None and range_row["effective_start"]
                else ""
            )
            largest_asset = retained.index[0] if not retained.empty else ""
            mechanism = []
            if bps > 0 and cost_avoided_dollars > 0:
                mechanism.append("DIRECT_COST_REDUCTION")
            if abs(exposure_delta) > 0.01 or abs(cash_delta) > 0.01:
                mechanism.append("EXPOSURE_CONTINUITY")
            if bool(period_audit.get("lifecycle_state_continuation", pd.Series(dtype=bool)).any()):
                mechanism.append("LIFECYCLE_STATE_CONTINUITY")
            if abs(residual_return_delta) > 0.001:
                mechanism.append("RESIDUAL_TRADE_PATH")
            if not mechanism:
                mechanism.append("NO_MATERIAL_COMPONENT")
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "family_id": STRATEGIES[strategy_id]["family_id"],
                    "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
                    "period_id": period_id,
                    "cost_assumption_bps_per_side": bps,
                    "suppressed_decision_count": avoided_orders,
                    "avoided_order_count": avoided_orders,
                    "modeled_transaction_cost_avoided": cost_avoided_dollars,
                    "direct_cost_return_component": direct_cost_return_component,
                    "notional_turnover_avoided_from_suppressed_orders": suppressed_notional,
                    "turnover_change": float(overlay["turnover"] - base["turnover"]),
                    "total_return_difference": return_delta,
                    "annualized_return_difference": float(overlay["annualized_return"] - base["annualized_return"]),
                    "drawdown_difference": float(overlay["max_drawdown_pct"] - base["max_drawdown_pct"]),
                    "average_gross_exposure_change": exposure_delta,
                    "average_cash_weight_change": cash_delta,
                    "invested_days_change": invested_delta,
                    "asset_level_exposure_retained": asset_retained,
                    "continuous_entry_date_positions": int(period_audit["exit_reentry_pair"].sum()) if not period_audit.empty and "exit_reentry_pair" in period_audit else 0,
                    "continuous_stop_or_trailing_state_positions": int(period_audit["lifecycle_state_continuation"].sum()) if not period_audit.empty and "lifecycle_state_continuation" in period_audit else 0,
                    "later_exit_differences_attributable_to_continuity": int(period_audit["later_stop_or_target_divergence"].sum()) if not period_audit.empty and "later_stop_or_target_divergence" in period_audit else 0,
                    "residual_path_return_difference": residual_return_delta,
                    "first_divergence": first_divergence,
                    "largest_residual_asset_or_event": largest_asset,
                    "component_classification": ",".join(mechanism),
                    "zero_cost_difference_component_rule": "cost_component_forced_zero" if bps == 0.0 else "",
                }
            )
    return pd.DataFrame(rows)


def lifecycle_continuity_attribution(
    *,
    audit: pd.DataFrame,
    results: dict[tuple[str, str, str, float], BacktestResult],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if audit.empty:
        return pd.DataFrame(rows)
    paired = audit[(audit["decision_event_kind"] == "suppressed_exit") & (audit["exit_reentry_pair"])].copy()
    if paired.empty:
        return pd.DataFrame(rows)
    paired["continuous_position_key"] = (
        paired["strategy_id"].astype(str)
        + "|"
        + paired["period_id"].astype(str)
        + "|"
        + paired["cost_assumption_bps_per_side"].astype(str)
        + "|"
        + paired["asset"].astype(str)
        + "|"
        + paired["existing_entry_date"].astype(str)
    )
    for _, event in paired.drop_duplicates("continuous_position_key").iterrows():
        strategy_id = event["strategy_id"]
        period_id = event["period_id"]
        bps = float(event["cost_assumption_bps_per_side"])
        slippage = bps / 10000.0
        timestamp = pd.Timestamp(event["timestamp"])
        asset = event["asset"]
        base_result = results.get(result_key(strategy_id, period_id, "base", slippage))
        overlay_result = results.get(result_key(strategy_id, period_id, "rebalance_band", slippage))
        base_trade = first_trade_after(base_result, timestamp, asset) if base_result is not None else None
        overlay_trade = spanning_trade(overlay_result, timestamp, asset) if overlay_result is not None else None
        base_path_pnl = np.nan
        overlay_pnl = np.nan
        if overlay_trade is not None:
            overlay_exit = pd.Timestamp(overlay_trade["exit_date"])
            overlay_pnl = float(overlay_trade.get("pnl", np.nan))
            if base_result is not None and not base_result.trades.empty:
                base_trades = base_result.trades.copy()
                base_trades["_entry_dt"] = pd.to_datetime(base_trades["entry_date"])
                base_trades["_exit_dt"] = pd.to_datetime(base_trades["exit_date"])
                path = base_trades[
                    (base_trades["symbol"] == asset)
                    & (base_trades["_exit_dt"] >= timestamp)
                    & (base_trades["_entry_dt"] <= overlay_exit)
                ]
                base_path_pnl = float(pd.to_numeric(path.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
        rows.append(
            {
                "strategy_id": strategy_id,
                "period_id": period_id,
                "cost_assumption_bps_per_side": bps,
                "asset": asset,
                "first_suppression_timestamp": event["timestamp"],
                "continuous_entry_date": event["existing_entry_date"],
                "entry_price_preserved": event["existing_entry_price"],
                "stop_price_preserved_at_suppression": event["existing_stop_price"],
                "initial_stop_price": event["existing_initial_stop_price"],
                "highest_close_trailing_state_preserved": event["existing_highest_close_trailing_state"],
                "trailing_enabled": event["existing_trailing_enabled"],
                "base_first_trade_after_suppression": trade_descriptor(base_trade),
                "overlay_continuous_trade": trade_descriptor(overlay_trade),
                "base_exit_reason_after_suppression": base_trade.get("exit_reason", "") if base_trade is not None else "",
                "overlay_exit_reason_after_suppression": overlay_trade.get("exit_reason", "") if overlay_trade is not None else "",
                "later_exit_reason_diverged": bool(
                    base_trade is not None
                    and overlay_trade is not None
                    and base_trade.get("exit_reason", "") != overlay_trade.get("exit_reason", "")
                ),
                "base_path_pnl_until_overlay_exit": base_path_pnl,
                "overlay_continuous_trade_pnl": overlay_pnl,
                "estimated_lifecycle_path_pnl_delta": overlay_pnl - base_path_pnl if np.isfinite(overlay_pnl) and np.isfinite(base_path_pnl) else np.nan,
                "attribution_note": "Suppressed paired monthly exit/re-entry preserved entry date, stop, and trailing state; P&L delta is path-level diagnostic, not a tuned attribution model.",
            }
        )
    return pd.DataFrame(rows)


def classify_combination(decomp: pd.DataFrame) -> dict[str, dict[str, Any]]:
    classifications: dict[str, dict[str, Any]] = {}
    for strategy_id, frame in decomp[decomp["period_id"].isin(INDEPENDENT_PERIODS)].groupby("strategy_id"):
        active = frame.groupby("period_id")["suppressed_decision_count"].sum()
        active_periods = int((active > 0).sum())
        improved = frame[frame["suppressed_decision_count"] > 0].groupby("period_id")["total_return_difference"].max()
        improve_periods = int((improved > 1e-8).sum())
        turnover = frame[frame["suppressed_decision_count"] > 0].groupby("period_id")["turnover_change"].min()
        turnover_reduce_periods = int((turnover < -1e-8).sum())
        drawdown = frame[frame["suppressed_decision_count"] > 0].groupby("period_id")["drawdown_difference"].max()
        drawdown_reduce_periods = int((drawdown > 1e-8).sum())
        zero = frame[(frame["cost_assumption_bps_per_side"] == 0.0) & (frame["suppressed_decision_count"] > 0)]
        pos5 = frame[(frame["cost_assumption_bps_per_side"] == 5.0) & (frame["suppressed_decision_count"] > 0)]
        pos10 = frame[(frame["cost_assumption_bps_per_side"] == 10.0) & (frame["suppressed_decision_count"] > 0)]
        zero_improve_periods = int((zero.groupby("period_id")["total_return_difference"].max() > 1e-8).sum()) if not zero.empty else 0
        survives5 = int((pos5.groupby("period_id")["total_return_difference"].max() > 1e-8).sum()) if not pos5.empty else 0
        survives10 = int((pos10.groupby("period_id")["total_return_difference"].max() > 1e-8).sum()) if not pos10.empty else 0
        harmful = bool((frame[frame["suppressed_decision_count"] > 0]["total_return_difference"] < -1e-8).any())
        independent_abs = frame.groupby("period_id")["total_return_difference"].apply(lambda s: float(np.abs(s).sum()))
        total_abs = float(independent_abs.sum())
        original_share = float(independent_abs.get("ORIGINAL_EXPLORATORY_WINDOW", 0.0) / total_abs) if total_abs else 0.0
        cost_component = float(np.abs(frame["direct_cost_return_component"]).sum())
        residual_component = float(np.abs(frame["residual_path_return_difference"]).sum())
        lifecycle_events = int(frame["continuous_stop_or_trailing_state_positions"].sum())
        exposure_component = bool((frame["average_gross_exposure_change"].abs() > 0.01).any())

        labels: list[str] = []
        if active_periods < 2:
            labels.append("INSUFFICIENT_ACTIVITY")
        else:
            if improve_periods >= 2 and zero_improve_periods >= 2 and survives5 >= 2 and survives10 >= 2 and not harmful:
                labels.append("ROBUST_ACROSS_CHRONOLOGICAL_PERIODS")
            elif improve_periods >= 2 and survives5 >= 2 and survives10 >= 2 and zero_improve_periods < 2:
                labels.append("ROBUST_ONLY_UNDER_POSITIVE_COSTS")
            if original_share > 0.65 and improve_periods <= 1:
                labels.append("PERIOD_SPECIFIC")
            if harmful:
                labels.append("HARMFUL_IN_ONE_OR_MORE_PERIODS")
            if improve_periods == 0:
                labels.append("NO_MATERIAL_EDGE")
            if zero_improve_periods < survives5 or zero_improve_periods < survives10:
                labels.append("COST_SENSITIVE")
            if cost_component > 0 and cost_component >= residual_component * 1.25:
                labels.append("DIRECT_COST_REDUCTION_DOMINANT")
            if lifecycle_events > 0 and residual_component > cost_component * 0.5:
                labels.append("LIFECYCLE_STATE_DOMINANT")
            if exposure_component and residual_component > cost_component * 0.5:
                labels.append("EXPOSURE_CONTINUITY_DOMINANT")
            mechanism_count = sum(
                label in labels
                for label in ["DIRECT_COST_REDUCTION_DOMINANT", "LIFECYCLE_STATE_DOMINANT", "EXPOSURE_CONTINUITY_DOMINANT"]
            )
            if mechanism_count >= 2:
                labels.append("MIXED_MECHANISM")
        if not labels:
            labels.append("NO_MATERIAL_EDGE")
        labels = list(dict.fromkeys(labels))
        advancement = (
            "ROBUSTNESS_REVIEW_CANDIDATE"
            if any(label in labels for label in ["ROBUST_ACROSS_CHRONOLOGICAL_PERIODS", "ROBUST_ONLY_UNDER_POSITIVE_COSTS"])
            and not any(label in labels for label in ["HARMFUL_IN_ONE_OR_MORE_PERIODS", "INSUFFICIENT_ACTIVITY", "NO_MATERIAL_EDGE"])
            else "NO_ADVANCEMENT"
        )
        classifications[strategy_id] = {
            "exact_combination_classification": "|".join(labels),
            "advancement_status": advancement,
            "independent_periods_with_suppressions": active_periods,
            "periods_improving_total_return": improve_periods,
            "periods_reducing_turnover": turnover_reduce_periods,
            "periods_reducing_drawdown": drawdown_reduce_periods,
            "improvement_exists_at_zero_cost_periods": zero_improve_periods,
            "improvement_survives_5bps_periods": survives5,
            "improvement_survives_10bps_periods": survives10,
            "original_window_abs_benefit_share": original_share,
            "lifecycle_state_material": lifecycle_events > 0 and residual_component > 0.001,
            "preserved_lifecycle_state_event_count": lifecycle_events,
        }
    return classifications


def chronological_robustness_matrix(decomp: pd.DataFrame) -> pd.DataFrame:
    classifications = classify_combination(decomp)
    rows: list[dict[str, Any]] = []
    for _, row in decomp.iterrows():
        cls = classifications.get(row["strategy_id"], {})
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "overlay_id": "OVL-ORD-001",
                "family_id": STRATEGIES[row["strategy_id"]]["family_id"],
                "economic_family_id": STRATEGIES[row["strategy_id"]]["economic_family_id"],
                "period_id": row["period_id"],
                "cost_assumption_bps_per_side": row["cost_assumption_bps_per_side"],
                "suppressed_decision_count": row["suppressed_decision_count"],
                "total_return_difference": row["total_return_difference"],
                "turnover_change": row["turnover_change"],
                "drawdown_difference": row["drawdown_difference"],
                "direct_cost_return_component": row["direct_cost_return_component"],
                "residual_path_return_difference": row["residual_path_return_difference"],
                "component_classification": row["component_classification"],
                **cls,
            }
        )
    return pd.DataFrame(rows)


def failure_registry(
    *,
    metrics: pd.DataFrame,
    range_coverage: pd.DataFrame,
    matrix: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in range_coverage[range_coverage["availability_status"] != "available"].iterrows():
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "period_id": row["period_id"],
                "overlay_id": "OVL-ORD-001",
                "cost_assumption_bps_per_side": "",
                "failure_code": row["unavailable_reason"],
                "details": "Frozen range unavailable; not substituted.",
            }
        )
    for _, row in metrics[metrics["execution_status"] != "completed"].iterrows():
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "period_id": row["period_id"],
                "overlay_id": row["overlay_id"],
                "cost_assumption_bps_per_side": row["slippage_bps_per_side"],
                "failure_code": "RUN_FAILED",
                "details": row.get("error", ""),
            }
        )
    for strategy_id, cls in classify_combination(matrix).items() if False else []:
        _ = strategy_id, cls
    for _, row in matrix.drop_duplicates(["strategy_id", "exact_combination_classification"]).iterrows():
        labels = str(row.get("exact_combination_classification", ""))
        for code in ["INSUFFICIENT_ACTIVITY", "PERIOD_SPECIFIC", "HARMFUL_IN_ONE_OR_MORE_PERIODS", "NO_MATERIAL_EDGE"]:
            if code in labels:
                rows.append(
                    {
                        "strategy_id": row["strategy_id"],
                        "period_id": "ALL_INDEPENDENT_PERIODS",
                        "overlay_id": "OVL-ORD-001",
                        "cost_assumption_bps_per_side": "",
                        "failure_code": code,
                        "details": labels,
                    }
                )
    return pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["strategy_id", "period_id", "overlay_id", "cost_assumption_bps_per_side", "failure_code", "details"])


def write_comparison(
    *,
    range_coverage: pd.DataFrame,
    metrics: pd.DataFrame,
    identity: pd.DataFrame,
    audit: pd.DataFrame,
    decomp: pd.DataFrame,
    lifecycle: pd.DataFrame,
    matrix: pd.DataFrame,
    corrections: pd.DataFrame,
    mapping: pd.DataFrame,
) -> None:
    parts = [
        "# Rebalance Band Robustness v1",
        "",
        "Timeframe diagnostic; research-only robustness. Adaptive follow-up from prior exploratory results, not clean holdout validation, optimization, promotion, or paper/demo eligibility.",
        "",
        "## Frozen Ranges",
        markdown_table(
            range_coverage,
            [
                "strategy_id",
                "period_id",
                "requested_start",
                "requested_end",
                "effective_start",
                "effective_end",
                "availability_status",
                "effective_trading_days",
            ],
        ),
        "",
        "## Identity Equivalence",
        markdown_table(
            identity,
            [
                "strategy_id",
                "period_id",
                "slippage_bps_per_side",
                "base_status",
                "identity_status",
                "complete_state_hash_match",
            ],
        ),
        "",
        "## Metrics",
        markdown_table(
            metrics[metrics["trial_name"].isin(["base", "rebalance_band"])],
            [
                "strategy_id",
                "period_id",
                "trial_name",
                "slippage_bps_per_side",
                "total_return",
                "max_drawdown_pct",
                "return_to_drawdown",
                "average_gross_exposure",
                "turnover",
                "number_of_trades",
                "corrected_modeled_transaction_cost",
                "suppressed_decision_count",
            ],
        ),
        "",
        "## Cost Path Decomposition",
        markdown_table(
            decomp,
            [
                "strategy_id",
                "period_id",
                "cost_assumption_bps_per_side",
                "suppressed_decision_count",
                "modeled_transaction_cost_avoided",
                "direct_cost_return_component",
                "total_return_difference",
                "residual_path_return_difference",
                "average_gross_exposure_change",
                "continuous_stop_or_trailing_state_positions",
                "component_classification",
            ],
        ),
        "",
        "## Suppressed Event Distribution",
        markdown_table(
            audit.groupby(["strategy_id", "period_id", "cost_assumption_bps_per_side", "mechanism_tags"]).size().reset_index(name="event_count")
            if not audit.empty
            else pd.DataFrame(),
            ["strategy_id", "period_id", "cost_assumption_bps_per_side", "mechanism_tags", "event_count"],
        ),
        "",
        "## Lifecycle Continuity",
        markdown_table(
            lifecycle,
            [
                "strategy_id",
                "period_id",
                "cost_assumption_bps_per_side",
                "asset",
                "continuous_entry_date",
                "base_exit_reason_after_suppression",
                "overlay_exit_reason_after_suppression",
                "estimated_lifecycle_path_pnl_delta",
            ],
        ),
        "",
        "## Exact Combination Classifications",
        markdown_table(
            matrix.drop_duplicates(["strategy_id", "exact_combination_classification"]),
            [
                "strategy_id",
                "overlay_id",
                "exact_combination_classification",
                "advancement_status",
                "independent_periods_with_suppressions",
                "periods_improving_total_return",
                "periods_reducing_turnover",
                "periods_reducing_drawdown",
                "improvement_exists_at_zero_cost_periods",
                "improvement_survives_5bps_periods",
                "improvement_survives_10bps_periods",
            ],
        ),
        "",
        "## Prior Status Corrections",
        markdown_table(corrections, ["strategy_id", "overlay_id", "previous_status", "corrected_status", "scope"]),
        "",
        "## Economic Family Mapping",
        markdown_table(mapping, ["strategy_id", "strategy_family_id", "economic_family_id", "independent_economic_family_confirmation_unit"]),
        "",
        "No parameter recommendation, overlay variant, strategy mutation, family-level promotion, or paper/demo/live/broker/scheduler/webhook action was created.",
    ]
    (OUT_DIR / "comparison.md").write_text("\n".join(parts), encoding="utf-8")


def write_source_of_truth_update(matrix: pd.DataFrame, corrections: pd.DataFrame) -> None:
    parts = [
        "# Source Of Truth Update",
        "",
        "Rebalance band robustness v1 completed as `timeframe_diagnostic;research_only_robustness`.",
        "",
        f"The source framework remains `{SOURCE_FRAMEWORK_STATUS}`.",
        "",
        "Prior packages were preserved unchanged:",
        f"- `{CANONICAL_SOURCE}`",
        f"- `{FAMILY_PORTABILITY_SOURCE}`",
        "",
        "Corrected prior statuses are recorded without overwriting older packages:",
        markdown_table(corrections, ["strategy_id", "overlay_id", "corrected_status", "scope"]),
        "",
        "Exact-combination robustness classifications:",
        markdown_table(
            matrix.drop_duplicates(["strategy_id", "exact_combination_classification"]),
            ["strategy_id", "overlay_id", "exact_combination_classification", "advancement_status"],
        ),
        "",
        "No strategy, signal, lifecycle rule, overlay parameter, overlay combination, calibration, promotion, or paper/demo/live path was changed.",
    ]
    (OUT_DIR / "source_of_truth_update.md").write_text("\n".join(parts), encoding="utf-8")


def run_test_commands() -> None:
    commands = [
        [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_rebalance_band_robustness_v1.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_current_multi_asset_portfolio_accounting_blast_radius_v1.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_risk_parity_trend_portfolio_accounting_review_v1.py", "-q"],
        [
            sys.executable,
            "-m",
            "py_compile",
            "src/overlays.py",
            "src/portfolio.py",
            "src/backtester.py",
            "run_trade_management_rebalance_band_robustness_v1.py",
        ],
    ]
    chunks: list[str] = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        chunks.append("$ " + " ".join(command))
        chunks.append(result.stdout)
        if result.stderr:
            chunks.append(result.stderr)
        chunks.append(f"exit_code={result.returncode}")
        if result.returncode != 0:
            (OUT_DIR / "test_results.txt").write_text("\n".join(chunks), encoding="utf-8")
            raise RuntimeError(f"Test command failed: {' '.join(command)}")
    (OUT_DIR / "test_results.txt").write_text("\n".join(chunks), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "config.yaml")
    data_load = load_market_data(config, ROOT)
    prepared = prepare_indicators(data_load.data)
    data_coverage = {
        strategy_id: data_coverage_for_strategy(config, data_load, strategy_id)
        for strategy_id in STRATEGIES
    }
    range_coverage = freeze_ranges(config=config, prepared=prepared, data_coverage=data_coverage)
    mapping = economic_family_mapping()
    corrections = prior_status_corrections()

    range_coverage.to_csv(OUT_DIR / "range_coverage.csv", index=False)
    mapping.to_csv(OUT_DIR / "economic_family_mapping.csv", index=False)
    corrections.to_csv(OUT_DIR / "prior_status_corrections.csv", index=False)
    write_json(
        OUT_DIR / "pre_registered_manifest.json",
        json_ready(pre_registered_manifest(config=config, data_coverage=data_coverage, range_coverage=range_coverage)),
    )

    available_ranges = range_coverage[range_coverage["availability_status"] == "available"].copy()
    metrics_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    event_frames: list[pd.DataFrame] = []
    results: dict[tuple[str, str, str, float], BacktestResult] = {}

    for _, range_row in available_ranges.iterrows():
        strategy_id = range_row["strategy_id"]
        period_id = range_row["period_id"]
        for slippage in SLIPPAGES:
            bps = slippage * 10000.0
            for trial_name in ["base", "identity", "rebalance_band"]:
                overlay_id = {"base": "BASE", "identity": "IDENTITY", "rebalance_band": "OVL-ORD-001"}[trial_name]
                print(f"Running {strategy_id} {period_id} {trial_name} {bps:.0f} bps...", flush=True)
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=config,
                    strategy_id=strategy_id,
                    period_id=period_id,
                    requested_start=range_row["requested_start"],
                    requested_end=range_row["requested_end"],
                    trial_name=trial_name,
                    slippage=slippage,
                )
                metrics_rows.append(
                    metric_row(
                        result=result,
                        events=events,
                        strategy_id=strategy_id,
                        period_id=period_id,
                        trial_name=trial_name,
                        overlay_id=overlay_id,
                        slippage=slippage,
                        error=error,
                    )
                )
                if result is not None:
                    results[result_key(strategy_id, period_id, trial_name, slippage)] = result
                if not events.empty:
                    event_frames.append(events)
            base = results.get(result_key(strategy_id, period_id, "base", slippage))
            identity = results.get(result_key(strategy_id, period_id, "identity", slippage))
            if base is not None and identity is not None:
                base_hashes = result_hashes(base)
                identity_hashes = result_hashes(identity)
                match = base_hashes["complete_state_hash"] == identity_hashes["complete_state_hash"]
                identity_rows.append(
                    {
                        "strategy_id": strategy_id,
                        "family_id": STRATEGIES[strategy_id]["family_id"],
                        "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
                        "period_id": period_id,
                        "slippage_bps_per_side": bps,
                        "base_status": "completed",
                        "identity_status": "completed",
                        "complete_state_hash_match": bool(match),
                        "base_complete_state_hash": base_hashes["complete_state_hash"],
                        "identity_complete_state_hash": identity_hashes["complete_state_hash"],
                    }
                )
            else:
                identity_rows.append(
                    {
                        "strategy_id": strategy_id,
                        "family_id": STRATEGIES[strategy_id]["family_id"],
                        "economic_family_id": STRATEGIES[strategy_id]["economic_family_id"],
                        "period_id": period_id,
                        "slippage_bps_per_side": bps,
                        "base_status": "missing",
                        "identity_status": "missing",
                        "complete_state_hash_match": False,
                        "base_complete_state_hash": "",
                        "identity_complete_state_hash": "",
                    }
                )

    metrics = add_overlay_minus_base_deltas(pd.DataFrame(metrics_rows))
    identity = pd.DataFrame(identity_rows)
    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    audit = suppressed_event_audit(events=events, results=results)
    decomp = cost_path_decomposition(metrics=metrics, audit=audit, results=results, range_coverage=range_coverage, config=config)
    lifecycle = lifecycle_continuity_attribution(audit=audit, results=results)
    matrix = chronological_robustness_matrix(decomp)
    failures = failure_registry(metrics=metrics, range_coverage=range_coverage, matrix=matrix)

    metrics.to_csv(OUT_DIR / "trial_registry.csv", index=False)
    metrics.to_csv(OUT_DIR / "metrics.csv", index=False)
    identity.to_csv(OUT_DIR / "identity_equivalence.csv", index=False)
    events.to_csv(OUT_DIR / "overlay_events.csv", index=False)
    audit.to_csv(OUT_DIR / "suppressed_event_audit.csv", index=False)
    decomp.to_csv(OUT_DIR / "cost_path_decomposition.csv", index=False)
    lifecycle.to_csv(OUT_DIR / "lifecycle_continuity_attribution.csv", index=False)
    matrix.to_csv(OUT_DIR / "chronological_robustness_matrix.csv", index=False)
    failures.to_csv(OUT_DIR / "failure_registry.csv", index=False)
    write_comparison(
        range_coverage=range_coverage,
        metrics=metrics,
        identity=identity,
        audit=audit,
        decomp=decomp,
        lifecycle=lifecycle,
        matrix=matrix,
        corrections=corrections,
        mapping=mapping,
    )
    write_source_of_truth_update(matrix, corrections)
    run_test_commands()
    print(f"Rebalance band robustness batch complete: {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
