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
    ExposureCapsOverlay,
    IdentityOverlay,
    LaggedVolatilityTargetOverlay,
    RebalanceBandOverlay,
    StaticScaleOverlay,
    TimeStopOverlay,
    TradeManagementOverlay,
    WideATRCatastrophicStopOverlay,
    stable_hash,
)
from src.trade_management_calibration import (
    INVALID_INSUFFICIENT_CALIBRATION_HISTORY,
    INVALID_NON_DYNAMIC_VOLATILITY_SCALER,
    PASS_DYNAMIC_VOLATILITY_SCALER,
    calibrate_volatility_target_from_equity,
    capped_scales_from_events,
    dynamic_scale_diagnostics_from_events,
    static_control_scale_from_capped_scales,
)
from src.utils import config_hash, git_commit_hash, load_config, write_json


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "codex_overlay_v1_canonical_exploratory"
PRIOR_VALIDATION = ROOT / "reports" / "trade_management" / "codex_overlay_v1_validation2"
PRIOR_AUDIT = ROOT / "reports" / "trade_management" / "codex_overlay_v1_correctness_audit"
REQUESTED_START = "2017-01-01"
REQUESTED_END = "2020-12-31"
SLIPPAGES = [0.0, 0.0005, 0.001]
STANDARD_SLIPPAGE = 0.0005
LABEL = "methodology_correction;research_only_exploratory"

CLASS_APPLICABLE_EFFECTIVE = "APPLICABLE_EFFECTIVE"
CLASS_APPLICABLE_NO_EFFECT = "APPLICABLE_NO_EFFECT"
CLASS_NOT_APPLICABLE_INTENT_UNIT = "NOT_APPLICABLE_INTENT_UNIT"
CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE = "NOT_APPLICABLE_STRATEGY_LIFECYCLE"
CLASS_INVALID_METHODOLOGY = "INVALID_METHODOLOGY"
CLASS_MECHANICAL_CONTROL = "MECHANICAL_CONTROL"

OVERLAY_PARAMETER_MAP = {
    "BASE": {},
    "IDENTITY": {},
    "OVL-SIZ-001": {"lookback": 63, "scale_floor": 0.25, "scale_cap": 1.0, "leverage": "none"},
    "STATIC-CALIBRATION-SCALE-CONTROL": {"scale_source": "median_pre_evaluation_capped_dynamic_scale"},
    "OVL-RSK-001": {"max_gross_exposure": 1.0, "per_asset_cap": None, "group_caps": {}},
    "OVL-ORD-001": {"min_weight_delta": 0.01, "min_nav_order_pct": 0.001},
    "OVL-STP-001": {"atr_lookback": 20, "atr_multiple": 4.0, "trailing": False},
    "OVL-EXT-001": {"max_completed_bars": 5},
}


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
    start: str,
    end: str | None,
    overlay_factory: Callable[[], TradeManagementOverlay | None],
) -> tuple[BacktestResult | None, pd.DataFrame, str]:
    strategy_hash = _strategy_source_hash(config, strategy_id)
    try:
        overlay = overlay_factory()
        bt = Backtester(prepared, config)
        result = bt.run(
            trial_name,
            start,
            end,
            slippage,
            lightweight_outputs=True,
            overlay=overlay,
            run_id=f"canonical_{strategy_id}_{trial_name}_{int(round(slippage * 10000))}bps",
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


def static_calibration_overlay(scale: float) -> StaticScaleOverlay:
    overlay = StaticScaleOverlay(scale=scale)
    overlay.overlay_id = "STATIC-CALIBRATION-SCALE-CONTROL"
    overlay.config["control_name"] = "STATIC-CALIBRATION-SCALE-CONTROL"
    overlay.config_hash = stable_hash(overlay.config)
    return overlay


def add_trial_row(
    rows: list[dict[str, Any]],
    *,
    result: BacktestResult | None,
    strategy: dict[str, str],
    trial_name: str,
    overlay_id: str,
    slippage: float,
    execution_status: str,
    research_classification: str,
    invalidity_code: str = "",
    error: str = "",
    overlay_config: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result is not None:
        row = summarize_result(
            result=result,
            strategy_id=strategy["strategy_id"],
            strategy_kind=strategy["kind"],
            trial_name=trial_name,
            overlay_id=overlay_id,
            slippage=slippage,
            status=execution_status,
            error=error,
            validation_label=LABEL,
        )
    else:
        row = blank_row(
            strategy=strategy,
            trial_name=trial_name,
            overlay_id=overlay_id,
            slippage=slippage,
            status=execution_status,
            error=error,
        )
    row.update(
        {
            "execution_status": execution_status,
            "research_classification": research_classification,
            "invalidity_code": invalidity_code,
            "methodology_label": "methodology_correction",
            "research_label": "research_only_exploratory",
            "overlay_config_hash": stable_hash(overlay_config or {}),
            "overlay_config": json.dumps(overlay_config or {}, sort_keys=True),
        }
    )
    if extra:
        row.update(extra)
    rows.append(row)
    return row


def blank_row(
    *,
    strategy: dict[str, str],
    trial_name: str,
    overlay_id: str,
    slippage: float,
    status: str,
    error: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "strategy_id": strategy["strategy_id"],
        "strategy_kind": strategy["kind"],
        "trial_name": trial_name,
        "overlay_id": overlay_id,
        "slippage_bps_per_side": slippage * 10000.0,
        "status": status,
        "error": error,
        "validation_label": LABEL,
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
        "number_skipped_or_resized_orders",
        "number_stop_events",
        "number_time_exit_events",
        "average_holding_period",
        "trade_mfe",
        "trade_mae",
        "worst_trade",
        "final_equity",
        "number_of_trades",
    ]:
        row[key] = np.nan
    return row


def event_count(events: pd.DataFrame, *, reason: str | None = None, decision: str | None = None) -> int:
    if events.empty:
        return 0
    mask = pd.Series(True, index=events.index)
    if reason is not None:
        mask &= events["reason_code"] == reason
    if decision is not None:
        mask &= events["decision_type"] == decision
    return int(mask.sum())


def classify_exposure_caps_trial(events: pd.DataFrame) -> str:
    if event_count(events, reason="unsupported_intent_unit"):
        return CLASS_NOT_APPLICABLE_INTENT_UNIT
    if event_count(events, reason="exposure_cap"):
        return CLASS_APPLICABLE_EFFECTIVE
    return CLASS_APPLICABLE_NO_EFFECT


def classify_wide_atr_trial(events: pd.DataFrame) -> str:
    overlay_stop_exits = event_count(events, reason="atr_stop_normal_touch") + event_count(
        events, reason="atr_stop_gap_through"
    )
    if overlay_stop_exits:
        return CLASS_APPLICABLE_EFFECTIVE
    if event_count(events, reason="base_stop_precedence"):
        return CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE
    return CLASS_APPLICABLE_NO_EFFECT


def exposure_cap_headroom(identity_events: pd.DataFrame, *, max_gross: float, per_asset_cap: float | None) -> dict[str, float]:
    if identity_events.empty:
        return {"minimum_gross_cap_headroom": np.nan, "minimum_per_asset_cap_headroom": np.nan}
    entries = identity_events[
        (identity_events["reason_code"] == "identity_pass")
        & (identity_events["target_unit"] == "target_weight")
    ].copy()
    if entries.empty:
        return {"minimum_gross_cap_headroom": np.nan, "minimum_per_asset_cap_headroom": np.nan}
    entries["base_target"] = pd.to_numeric(entries["base_target"], errors="coerce")
    by_time = entries.groupby("timestamp")["base_target"]
    gross_headroom = (max_gross - by_time.apply(lambda series: series.abs().sum())).min()
    per_asset_headroom = (per_asset_cap - entries["base_target"].abs()).min() if per_asset_cap is not None else np.nan
    return {
        "minimum_gross_cap_headroom": float(gross_headroom),
        "minimum_per_asset_cap_headroom": float(per_asset_headroom),
    }


def make_trial_lineage() -> pd.DataFrame:
    prior = pd.read_csv(PRIOR_VALIDATION / "metrics.csv")
    rows: list[dict[str, Any]] = []
    for index, row in prior.reset_index(drop=True).iterrows():
        strategy = str(row["strategy_id"])
        trial = str(row["trial_name"])
        if trial in {"base", "identity"}:
            disposition = "RETAINED_MECHANICAL_CONTROL"
            rationale = "Full-state base versus Identity controls were rechecked by the methodology audit."
        elif trial == "lagged_volatility_target":
            disposition = "INVALID_METHODOLOGY"
            rationale = "Original target volatility was zero and all dynamic decisions were forced to the floor."
        elif trial == "static_lower_exposure_control":
            disposition = "NON_INFORMATIVE_STATIC_EXPOSURE"
            rationale = "Original static 0.25 control is descriptive lower exposure only, not calibration-derived."
        elif trial == "calibration_base":
            disposition = "NOT_APPLICABLE"
            rationale = "Original calibration helper row is not an overlay comparison trial."
        elif trial == "rebalance_band" and strategy == "B_ETF_trend_following":
            disposition = "NOT_APPLICABLE"
            rationale = "Rebalance band supports target-weight intents, while this frozen base emits risk-dollar intents."
        elif trial == "exposure_caps" and strategy == "B_ETF_trend_following":
            disposition = "NOT_APPLICABLE"
            rationale = "Exposure caps are target-weight transforms and did not apply to risk-dollar intents."
        elif trial == "exposure_caps":
            disposition = "NO_EFFECT"
            rationale = "No cap-binding resize occurred in the original row; canonical rerun reports headroom explicitly."
        else:
            disposition = "SUPERSEDED_BY_CORRECTED_RERUN"
            rationale = "Canonical methodology-correction rerun replaces this row with corrected costs and classification."
        rows.append(
            {
                "prior_row_id": index + 1,
                "prior_strategy_id": strategy,
                "prior_trial_name": trial,
                "prior_overlay_id": row.get("overlay_id", ""),
                "prior_slippage_bps_per_side": row.get("slippage_bps_per_side", np.nan),
                "prior_status": row.get("status", ""),
                "disposition": disposition,
                "rationale": rationale,
            }
        )
    return pd.DataFrame(rows)


def cost_exposure_attribution(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bases = metrics[metrics["trial_name"] == "base"].set_index(["strategy_id", "slippage_bps_per_side"])
    statics = metrics[metrics["overlay_id"] == "STATIC-CALIBRATION-SCALE-CONTROL"].set_index(
        ["strategy_id", "slippage_bps_per_side"]
    )
    for _, row in metrics.iterrows():
        if row["trial_name"] == "base":
            continue
        key = (row["strategy_id"], row["slippage_bps_per_side"])
        if key not in bases.index:
            continue
        base = bases.loc[key]
        out = {
            "strategy_id": row["strategy_id"],
            "trial_name": row["trial_name"],
            "overlay_id": row["overlay_id"],
            "slippage_bps_per_side": row["slippage_bps_per_side"],
            "research_classification": row.get("research_classification", ""),
            "base_total_return": base.get("total_return", np.nan),
            "overlay_total_return": row.get("total_return", np.nan),
            "total_return_delta": row.get("total_return", np.nan) - base.get("total_return", np.nan),
            "base_average_gross_exposure": base.get("average_gross_exposure", np.nan),
            "overlay_average_gross_exposure": row.get("average_gross_exposure", np.nan),
            "average_gross_exposure_delta": row.get("average_gross_exposure", np.nan)
            - base.get("average_gross_exposure", np.nan),
            "dynamic_to_base_exposure_ratio": row.get("average_gross_exposure", np.nan)
            / base.get("average_gross_exposure", np.nan)
            if base.get("average_gross_exposure", np.nan)
            else np.nan,
            "base_modeled_transaction_cost": base.get("modeled_transaction_cost", np.nan),
            "overlay_modeled_transaction_cost": row.get("modeled_transaction_cost", np.nan),
            "modeled_transaction_cost_delta": row.get("modeled_transaction_cost", np.nan)
            - base.get("modeled_transaction_cost", np.nan),
            "base_trade_count": base.get("number_of_trades", np.nan),
            "overlay_trade_count": row.get("number_of_trades", np.nan),
            "trade_count_delta": row.get("number_of_trades", np.nan) - base.get("number_of_trades", np.nan),
        }
        if row["trial_name"] == "lagged_volatility_target" and key in statics.index:
            static = statics.loc[key]
            out.update(
                {
                    "static_control_total_return": static.get("total_return", np.nan),
                    "dynamic_minus_static_total_return": row.get("total_return", np.nan)
                    - static.get("total_return", np.nan),
                    "static_control_average_gross_exposure": static.get("average_gross_exposure", np.nan),
                    "dynamic_minus_static_average_gross_exposure": row.get("average_gross_exposure", np.nan)
                    - static.get("average_gross_exposure", np.nan),
                    "static_control_modeled_transaction_cost": static.get("modeled_transaction_cost", np.nan),
                }
            )
        rows.append(out)
    return pd.DataFrame(rows)


def rebalance_attribution(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base = metrics[(metrics["strategy_id"] == "N2_absolute_trend_taa") & (metrics["trial_name"] == "base")]
    reb = metrics[(metrics["strategy_id"] == "N2_absolute_trend_taa") & (metrics["trial_name"] == "rebalance_band")]
    for _, row in reb.iterrows():
        base_row = base[base["slippage_bps_per_side"] == row["slippage_bps_per_side"]]
        if base_row.empty:
            continue
        b = base_row.iloc[0]
        trades_avoided = b["number_of_trades"] - row["number_of_trades"]
        cost_avoided = b["modeled_transaction_cost"] - row["modeled_transaction_cost"]
        exposure_delta = row["average_gross_exposure"] - b["average_gross_exposure"]
        improvement = row["total_return"] > b["total_return"]
        if abs(exposure_delta) > 0.005 and trades_avoided > 0:
            cause = "fewer_replacement_trades_and_changed_exposure"
        elif trades_avoided > 0:
            cause = "fewer_unnecessary_replacement_trades"
        elif abs(exposure_delta) > 0.005:
            cause = "changed_exposure"
        else:
            cause = "no_material_path_change"
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "slippage_bps_per_side": row["slippage_bps_per_side"],
                "base_total_return": b["total_return"],
                "rebalance_total_return": row["total_return"],
                "return_delta": row["total_return"] - b["total_return"],
                "improvement_survives_this_cost_assumption": bool(improvement),
                "base_trade_count": b["number_of_trades"],
                "rebalance_trade_count": row["number_of_trades"],
                "trades_avoided": trades_avoided,
                "direct_modeled_cost_avoided": cost_avoided,
                "base_average_gross_exposure": b["average_gross_exposure"],
                "rebalance_average_gross_exposure": row["average_gross_exposure"],
                "exposure_retained_delta": exposure_delta,
                "trade_path_changed": bool(trades_avoided != 0),
                "primary_cause": cause,
                "research_classification": row.get("research_classification", ""),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        survives_all = bool(frame["improvement_survives_this_cost_assumption"].all())
        frame["improvement_survives_0_5_10_bps"] = survives_all
    return frame


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    table = df[columns].copy() if not df.empty else pd.DataFrame(columns=columns)
    for col in table.columns:
        if pd.api.types.is_numeric_dtype(table[col]):
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    lines = [
        "| " + " | ".join(table.columns) + " |",
        "| " + " | ".join("---" for _ in table.columns) + " |",
    ]
    for _, row in table.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(row[col]) else str(row[col]) for col in table.columns) + " |")
    return "\n".join(lines)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_comparison(metrics: pd.DataFrame, calibration: pd.DataFrame, lineage: pd.DataFrame) -> None:
    display_cols = [
        "strategy_id",
        "trial_name",
        "overlay_id",
        "slippage_bps_per_side",
        "execution_status",
        "research_classification",
        "invalidity_code",
        "total_return",
        "annualized_volatility",
        "max_drawdown_pct",
        "sharpe",
        "average_gross_exposure",
        "number_of_trades",
        "modeled_transaction_cost",
    ]
    text = [
        "# Canonical Trade-Management Overlay v1 Exploratory Comparison",
        "",
        "Research-only methodology correction. This is not a promotion, holdout, paper/demo/live, or parameter-search exercise.",
        "",
        "## Framework Status",
        "",
        "`PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION`.",
        "",
        "The prior `FAIL_METHODOLOGY_CORRECTIONS_REQUIRED` verdict applies to the original comparison before corrections, not to the corrected framework controls.",
        "",
        "## Calibration",
        "",
        markdown_table(
            calibration,
            [
                "strategy_id",
                "evaluation_start",
                "selected_return_start",
                "selected_return_end",
                "selected_return_count",
                "rolling_volatility_count",
                "target_volatility",
                "static_control_scale",
                "calibration_status",
            ],
        ),
        "",
        "## Canonical Matrix",
        "",
        markdown_table(metrics, display_cols),
        "",
        "## Prior Lineage Summary",
        "",
        markdown_table(
            lineage.groupby("disposition", as_index=False).size().rename(columns={"size": "row_count"}),
            ["disposition", "row_count"],
        ),
    ]
    (OUT_DIR / "comparison.md").write_text("\n".join(text), encoding="utf-8")


def write_source_of_truth_update(metrics: pd.DataFrame, calibration: pd.DataFrame, lineage: pd.DataFrame) -> None:
    lines = [
        "# Source Of Truth Update",
        "",
        "Corrected framework status: `PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION`.",
        "",
        "Original comparison status remains: `FAIL_METHODOLOGY_CORRECTIONS_REQUIRED`.",
        "",
        f"All prior rows classified: `{len(lineage)}`.",
        "",
        "No base strategy source, parameters, universes, signal timestamps, execution-connected paper/demo/live/broker path, scheduler, or webhook path was changed or activated.",
        "",
        "OVL-SIZ-001 uses a fixed target from the final 252 valid base-strategy daily returns strictly before each strategy's first actual evaluation date.",
        "",
        markdown_table(
            calibration,
            ["strategy_id", "target_volatility", "static_control_scale", "calibration_status"],
        ),
    ]
    invalid_dynamic = metrics[
        (metrics["trial_name"] == "lagged_volatility_target")
        & (metrics["research_classification"] == CLASS_INVALID_METHODOLOGY)
    ]
    if not invalid_dynamic.empty:
        lines.extend(["", "Invalid dynamic-volatility rows remain research-invalid and are not reported as effective overlays."])
    (OUT_DIR / "source_of_truth_update.md").write_text("\n".join(lines), encoding="utf-8")


def run_test_commands() -> None:
    commands = [
        [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
        [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
        [
            sys.executable,
            "-m",
            "py_compile",
            "src/overlays.py",
            "src/portfolio.py",
            "src/backtester.py",
            "src/trade_management_calibration.py",
            "run_trade_management_overlay_canonical_exploratory.py",
        ],
    ]
    chunks: list[str] = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        chunks.append("$ " + " ".join(cmd))
        chunks.append(proc.stdout)
        if proc.stderr:
            chunks.append(proc.stderr)
        chunks.append(f"exit_code={proc.returncode}")
    (OUT_DIR / "test_results.txt").write_text("\n".join(chunks), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / "config.yaml")
    config["project_root"] = str(ROOT)
    data_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(data_result.data)

    metrics_rows: list[dict[str, Any]] = []
    event_frames: list[pd.DataFrame] = []
    calibration_rows: list[dict[str, Any]] = []
    vol_diag_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    base_results: dict[tuple[str, float], BacktestResult] = {}
    identity_events_by_key: dict[tuple[str, float], pd.DataFrame] = {}
    strategy_hashes: dict[str, str] = {}

    for strategy in FROZEN_STRATEGIES:
        strategy_id = strategy["strategy_id"]
        strategy_cfg = _strategy_only_config(config, strategy_id)
        strategy_hashes[strategy_id] = _strategy_source_hash(strategy_cfg, strategy_id)
        print(f"Running canonical base rows for {strategy_id}...", flush=True)
        for slippage in SLIPPAGES:
            result, events, error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="base",
                slippage=slippage,
                start=REQUESTED_START,
                end=REQUESTED_END,
                overlay_factory=lambda: None,
            )
            add_trial_row(
                metrics_rows,
                result=result,
                strategy=strategy,
                trial_name="base",
                overlay_id="BASE",
                slippage=slippage,
                execution_status="completed" if result is not None else "failed",
                research_classification=CLASS_MECHANICAL_CONTROL,
                error=error,
                overlay_config=OVERLAY_PARAMETER_MAP["BASE"],
            )
            if result is None:
                raise RuntimeError(error)
            base_results[(strategy_id, slippage)] = result

        standard_base = base_results[(strategy_id, STANDARD_SLIPPAGE)]
        eval_start = pd.Timestamp(standard_base.metadata["effective_first_trading_date"])
        eval_end = pd.Timestamp(standard_base.metadata["effective_last_trading_date"])
        pre_eval_end = (eval_start - pd.Timedelta(days=1)).date().isoformat()
        calibration_base, _, error = run_backtest(
            prepared=prepared,
            config=strategy_cfg,
            strategy_id=strategy_id,
            trial_name="pre_evaluation_calibration_base",
            slippage=STANDARD_SLIPPAGE,
            start=str(config["date_ranges"]["full"]["start"]),
            end=pre_eval_end,
            overlay_factory=lambda: None,
        )
        if calibration_base is None:
            raise RuntimeError(error)
        calibration = calibrate_volatility_target_from_equity(
            calibration_base.equity_curve,
            evaluation_start=eval_start,
            return_count=252,
            lookback=63,
            min_rolling_volatility_estimates=126,
        )
        target_vol = calibration.target_volatility
        static_scale = np.nan
        static_scale_count = 0
        if calibration.status == "valid":
            pre_dynamic, pre_events, error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="pre_evaluation_dynamic_scale_observation",
                slippage=STANDARD_SLIPPAGE,
                start=str(config["date_ranges"]["full"]["start"]),
                end=pre_eval_end,
                overlay_factory=lambda target_vol=target_vol: LaggedVolatilityTargetOverlay(
                    target_volatility=target_vol,
                    lookback=63,
                    scale_floor=0.25,
                    scale_cap=1.0,
                ),
            )
            if pre_dynamic is None:
                calibration.invalidity_code = error or INVALID_INSUFFICIENT_CALIBRATION_HISTORY
                calibration.status = "invalid"
            else:
                event_slice = pre_events.copy()
                if not event_slice.empty:
                    event_slice["timestamp_ts"] = pd.to_datetime(event_slice["timestamp"], errors="coerce")
                    event_slice = event_slice[
                        (event_slice["timestamp_ts"] >= pd.Timestamp(calibration.selected_return_start))
                        & (event_slice["timestamp_ts"] <= pd.Timestamp(calibration.selected_return_end))
                    ]
                scales = capped_scales_from_events(event_slice)
                if not scales:
                    scales = capped_scales_from_events(pre_events)
                static_scale_count = len(scales)
                try:
                    static_scale = static_control_scale_from_capped_scales(scales)
                except ValueError:
                    calibration.invalidity_code = INVALID_INSUFFICIENT_CALIBRATION_HISTORY
                    calibration.status = "invalid"

        calibration_record = calibration.to_record()
        calibration_record.update(
            {
                "strategy_id": strategy_id,
                "requested_evaluation_start": REQUESTED_START,
                "requested_evaluation_end": REQUESTED_END,
                "actual_evaluation_start": eval_start.date().isoformat(),
                "actual_evaluation_end": eval_end.date().isoformat(),
                "calibration_status": calibration.status,
                "static_control_scale": static_scale,
                "static_control_scale_observation_count": static_scale_count,
                "calibration_slippage_bps_per_side": STANDARD_SLIPPAGE * 10000.0,
            }
        )
        calibration_rows.append(calibration_record)

        print(f"Running canonical overlays for {strategy_id}...", flush=True)
        for slippage in SLIPPAGES:
            result, events, error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="identity",
                slippage=slippage,
                start=REQUESTED_START,
                end=REQUESTED_END,
                overlay_factory=lambda: IdentityOverlay(),
            )
            base_hash = result_hashes(base_results[(strategy_id, slippage)])
            identity_hash = result_hashes(result) if result is not None else {}
            identity_pass = bool(result is not None and base_hash["complete_state_hash"] == identity_hash["complete_state_hash"])
            add_trial_row(
                metrics_rows,
                result=result,
                strategy=strategy,
                trial_name="identity",
                overlay_id="IDENTITY",
                slippage=slippage,
                execution_status="completed" if result is not None else "failed",
                research_classification=CLASS_MECHANICAL_CONTROL if identity_pass else CLASS_INVALID_METHODOLOGY,
                invalidity_code="" if identity_pass else "FAIL_IDENTITY_EQUIVALENCE",
                error=error,
                overlay_config=OVERLAY_PARAMETER_MAP["IDENTITY"],
                extra={"identity_complete_hash_match": identity_pass},
            )
            if result is not None:
                identity_rows.append(
                    {
                        "strategy_id": strategy_id,
                        "slippage_bps_per_side": slippage * 10000.0,
                        "complete_hash_match": identity_pass,
                        "base_complete_state_hash": base_hash["complete_state_hash"],
                        "identity_complete_state_hash": identity_hash["complete_state_hash"],
                    }
                )
            if not events.empty:
                event_frames.append(events)
                identity_events_by_key[(strategy_id, slippage)] = events

            if calibration.status == "valid":
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name="lagged_volatility_target",
                    slippage=slippage,
                    start=REQUESTED_START,
                    end=REQUESTED_END,
                    overlay_factory=lambda target_vol=target_vol: LaggedVolatilityTargetOverlay(
                        target_volatility=target_vol,
                        lookback=63,
                        scale_floor=0.25,
                        scale_cap=1.0,
                    ),
                )
                diag = dynamic_scale_diagnostics_from_events(events, target_volatility=target_vol)
                diag.update({"strategy_id": strategy_id, "slippage_bps_per_side": slippage * 10000.0})
                vol_diag_rows.append(diag)
                dynamic_class = (
                    CLASS_APPLICABLE_EFFECTIVE
                    if result is not None and diag["status"] == PASS_DYNAMIC_VOLATILITY_SCALER
                    else CLASS_INVALID_METHODOLOGY
                )
                add_trial_row(
                    metrics_rows,
                    result=result,
                    strategy=strategy,
                    trial_name="lagged_volatility_target",
                    overlay_id="OVL-SIZ-001",
                    slippage=slippage,
                    execution_status="completed" if result is not None else "failed",
                    research_classification=dynamic_class,
                    invalidity_code="" if dynamic_class != CLASS_INVALID_METHODOLOGY else diag["status"],
                    error=error,
                    overlay_config={**OVERLAY_PARAMETER_MAP["OVL-SIZ-001"], "target_volatility": target_vol},
                    extra={
                        "target_volatility": target_vol,
                        "average_dynamic_scale": diag["average_scale"],
                        "dynamic_to_base_exposure_ratio": (
                            np.nan
                            if result is None
                            else float(result.equity_curve["gross_exposure"].mean())
                            / float(base_results[(strategy_id, slippage)].equity_curve["gross_exposure"].mean())
                        ),
                    },
                )
                if not events.empty:
                    event_frames.append(events)
            else:
                vol_diag_rows.append(
                    {
                        "strategy_id": strategy_id,
                        "slippage_bps_per_side": slippage * 10000.0,
                        "target_volatility": target_vol,
                        "status": calibration.invalidity_code,
                    }
                )
                add_trial_row(
                    metrics_rows,
                    result=None,
                    strategy=strategy,
                    trial_name="lagged_volatility_target",
                    overlay_id="OVL-SIZ-001",
                    slippage=slippage,
                    execution_status="not_run_invalid_calibration",
                    research_classification=CLASS_INVALID_METHODOLOGY,
                    invalidity_code=calibration.invalidity_code,
                    error=calibration.invalidity_code,
                    overlay_config=OVERLAY_PARAMETER_MAP["OVL-SIZ-001"],
                    extra={"target_volatility": target_vol},
                )

            if calibration.status == "valid" and np.isfinite(static_scale):
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name="static_calibration_scale_control",
                    slippage=slippage,
                    start=REQUESTED_START,
                    end=REQUESTED_END,
                    overlay_factory=lambda static_scale=static_scale: static_calibration_overlay(static_scale),
                )
                add_trial_row(
                    metrics_rows,
                    result=result,
                    strategy=strategy,
                    trial_name="static_calibration_scale_control",
                    overlay_id="STATIC-CALIBRATION-SCALE-CONTROL",
                    slippage=slippage,
                    execution_status="completed" if result is not None else "failed",
                    research_classification=CLASS_MECHANICAL_CONTROL,
                    error=error,
                    overlay_config={
                        **OVERLAY_PARAMETER_MAP["STATIC-CALIBRATION-SCALE-CONTROL"],
                        "scale": static_scale,
                    },
                    extra={"static_control_scale": static_scale},
                )
                if not events.empty:
                    event_frames.append(events)
            else:
                add_trial_row(
                    metrics_rows,
                    result=None,
                    strategy=strategy,
                    trial_name="static_calibration_scale_control",
                    overlay_id="STATIC-CALIBRATION-SCALE-CONTROL",
                    slippage=slippage,
                    execution_status="not_run_invalid_calibration",
                    research_classification=CLASS_INVALID_METHODOLOGY,
                    invalidity_code=calibration.invalidity_code,
                    error=calibration.invalidity_code,
                    overlay_config=OVERLAY_PARAMETER_MAP["STATIC-CALIBRATION-SCALE-CONTROL"],
                )

            result, events, error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="exposure_caps",
                slippage=slippage,
                start=REQUESTED_START,
                end=REQUESTED_END,
                overlay_factory=lambda: ExposureCapsOverlay(max_gross_exposure=1.0),
            )
            unsupported = event_count(events, reason="unsupported_intent_unit")
            cap_events = event_count(events, reason="exposure_cap")
            headroom = exposure_cap_headroom(
                identity_events_by_key.get((strategy_id, slippage), pd.DataFrame()),
                max_gross=1.0,
                per_asset_cap=None,
            )
            cap_class = classify_exposure_caps_trial(events)
            add_trial_row(
                metrics_rows,
                result=result,
                strategy=strategy,
                trial_name="exposure_caps",
                overlay_id="OVL-RSK-001",
                slippage=slippage,
                execution_status="completed" if result is not None else "failed",
                research_classification=cap_class,
                error=error,
                overlay_config=OVERLAY_PARAMETER_MAP["OVL-RSK-001"],
                extra={
                    "cap_bind_event_count": cap_events,
                    "unsupported_intent_event_count": unsupported,
                    **headroom,
                },
            )
            if not events.empty:
                event_frames.append(events)

            if strategy_id == "N2_absolute_trend_taa":
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name="rebalance_band",
                    slippage=slippage,
                    start=REQUESTED_START,
                    end=REQUESTED_END,
                    overlay_factory=lambda: RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001),
                )
                suppress_count = event_count(events, decision="suppress_order")
                add_trial_row(
                    metrics_rows,
                    result=result,
                    strategy=strategy,
                    trial_name="rebalance_band",
                    overlay_id="OVL-ORD-001",
                    slippage=slippage,
                    execution_status="completed" if result is not None else "failed",
                    research_classification=CLASS_APPLICABLE_EFFECTIVE if suppress_count else CLASS_APPLICABLE_NO_EFFECT,
                    error=error,
                    overlay_config=OVERLAY_PARAMETER_MAP["OVL-ORD-001"],
                    extra={"suppressed_decision_count": suppress_count},
                )
                if not events.empty:
                    event_frames.append(events)
            else:
                add_trial_row(
                    metrics_rows,
                    result=None,
                    strategy=strategy,
                    trial_name="rebalance_band",
                    overlay_id="OVL-ORD-001",
                    slippage=slippage,
                    execution_status="not_run_not_applicable",
                    research_classification=CLASS_NOT_APPLICABLE_INTENT_UNIT,
                    invalidity_code="UNSUPPORTED_TARGET_UNIT_RISK_AMOUNT_DOLLARS",
                    error="Rebalance band supports target_weight intents; frozen base emits risk_amount_dollars intents.",
                    overlay_config=OVERLAY_PARAMETER_MAP["OVL-ORD-001"],
                )

            result, events, error = run_backtest(
                prepared=prepared,
                config=strategy_cfg,
                strategy_id=strategy_id,
                trial_name="wide_atr_catastrophic_stop",
                slippage=slippage,
                start=REQUESTED_START,
                end=REQUESTED_END,
                overlay_factory=lambda: WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0),
            )
            overlay_stop_exits = event_count(events, reason="atr_stop_normal_touch") + event_count(
                events, reason="atr_stop_gap_through"
            )
            base_precedence = event_count(events, reason="base_stop_precedence")
            stop_class = classify_wide_atr_trial(events)
            add_trial_row(
                metrics_rows,
                result=result,
                strategy=strategy,
                trial_name="wide_atr_catastrophic_stop",
                overlay_id="OVL-STP-001",
                slippage=slippage,
                execution_status="completed" if result is not None else "failed",
                research_classification=stop_class,
                error=error,
                overlay_config=OVERLAY_PARAMETER_MAP["OVL-STP-001"],
                extra={
                    "overlay_stop_exit_count": overlay_stop_exits,
                    "base_stop_precedence_event_count": base_precedence,
                },
            )
            if not events.empty:
                event_frames.append(events)

            if strategy_id == "B_ETF_trend_following":
                result, events, error = run_backtest(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy_id=strategy_id,
                    trial_name="time_stop",
                    slippage=slippage,
                    start=REQUESTED_START,
                    end=REQUESTED_END,
                    overlay_factory=lambda strategy_id=strategy_id: TimeStopOverlay(
                        max_completed_bars=5,
                        strategies=[strategy_id],
                    ),
                )
                time_events = event_count(events, reason="time_stop")
                add_trial_row(
                    metrics_rows,
                    result=result,
                    strategy=strategy,
                    trial_name="time_stop",
                    overlay_id="OVL-EXT-001",
                    slippage=slippage,
                    execution_status="completed" if result is not None else "failed",
                    research_classification=CLASS_APPLICABLE_EFFECTIVE if time_events else CLASS_APPLICABLE_NO_EFFECT,
                    error=error,
                    overlay_config={**OVERLAY_PARAMETER_MAP["OVL-EXT-001"], "strategies": [strategy_id]},
                    extra={"time_stop_event_count": time_events},
                )
                if not events.empty:
                    event_frames.append(events)

        for order_name, order in {"forward": ["base", "identity"], "reverse": ["identity", "base"]}.items():
            for trial_name in order:
                for slippage in SLIPPAGES:
                    factory: Callable[[], TradeManagementOverlay | None] = (lambda: None) if trial_name == "base" else (lambda: IdentityOverlay())
                    result, _, error = run_backtest(
                        prepared=prepared,
                        config=strategy_cfg,
                        strategy_id=strategy_id,
                        trial_name=trial_name,
                        slippage=slippage,
                        start=REQUESTED_START,
                        end=REQUESTED_END,
                        overlay_factory=factory,
                    )
                    if result is None:
                        raise RuntimeError(error)
                    if trial_name == "identity":
                        reference_hash = next(
                            item["identity_complete_state_hash"]
                            for item in identity_rows
                            if item["strategy_id"] == strategy_id
                            and item["slippage_bps_per_side"] == slippage * 10000.0
                        )
                    else:
                        reference_hash = result_hashes(base_results[(strategy_id, slippage)])["complete_state_hash"]
                    order_rows.append(
                        {
                            "strategy_id": strategy_id,
                            "trial_name": trial_name,
                            "slippage_bps_per_side": slippage * 10000.0,
                            "execution_order": order_name,
                            "hash_match": result_hashes(result)["complete_state_hash"] == reference_hash,
                        }
                    )

    metrics = pd.DataFrame(metrics_rows)
    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    calibration = pd.DataFrame(calibration_rows)
    volatility = pd.DataFrame(vol_diag_rows)
    lineage = make_trial_lineage()
    applicability = metrics[
        [
            "strategy_id",
            "trial_name",
            "overlay_id",
            "slippage_bps_per_side",
            "execution_status",
            "research_classification",
            "invalidity_code",
        ]
    ].copy()
    cost_exposure = cost_exposure_attribution(metrics)
    rebalance = rebalance_attribution(metrics)
    identity_checks = pd.DataFrame(identity_rows)
    order_checks = pd.DataFrame(order_rows)

    metrics.to_csv(OUT_DIR / "metrics.csv", index=False)
    metrics.to_csv(OUT_DIR / "trial_registry.csv", index=False)
    lineage.to_csv(OUT_DIR / "trial_lineage.csv", index=False)
    applicability.to_csv(OUT_DIR / "applicability_matrix.csv", index=False)
    calibration.to_csv(OUT_DIR / "calibration_diagnostics.csv", index=False)
    volatility.to_csv(OUT_DIR / "volatility_scaler_diagnostics.csv", index=False)
    events.to_csv(OUT_DIR / "overlay_events.csv", index=False)
    cost_exposure.to_csv(OUT_DIR / "cost_exposure_attribution.csv", index=False)
    rebalance.to_csv(OUT_DIR / "rebalance_attribution.csv", index=False)
    identity_checks.to_csv(OUT_DIR / "identity_hashes.csv", index=False)
    order_checks.to_csv(OUT_DIR / "trial_order_independence.csv", index=False)
    write_comparison(metrics, calibration, lineage)
    write_source_of_truth_update(metrics, calibration, lineage)

    manifest = {
        "run_id": "codex_overlay_v1_canonical_exploratory",
        "v1_closure_verdict": "PASS_MECHANICALLY_VALID_WITH_OVL_SIZ_FAILS_CLOSED_INVALID_DEGENERATE_CALIBRATION",
        "created_utc": datetime.now(UTC).isoformat(),
        "research_only": True,
        "exploratory": True,
        "labels": ["methodology_correction", "research_only_exploratory"],
        "no_combinations": True,
        "overlay_combinations_run": False,
        "paper_demo_live_broker_scheduler_webhook_paths_activated": False,
        "paper_demo_live_broker_scheduler_webhook_paths_modified": False,
        "repository_commit": git_commit_hash(ROOT),
        "config_hash": config_hash(config),
        "requested_evaluation_dates": {"start": REQUESTED_START, "end": REQUESTED_END},
        "actual_evaluation_dates_by_strategy": {
            row["strategy_id"]: {
                "start": row["actual_evaluation_start"],
                "end": row["actual_evaluation_end"],
            }
            for row in calibration_rows
        },
        "base_strategy_hashes": strategy_hashes,
        "overlay_configuration_hashes": {
            key: stable_hash(value) for key, value in OVERLAY_PARAMETER_MAP.items()
        },
        "overlay_parameter_mappings": OVERLAY_PARAMETER_MAP,
        "calibration_dates": {
            row["strategy_id"]: {
                "calibration_start": row["calibration_start"],
                "calibration_end": row["calibration_end"],
                "selected_return_start": row["selected_return_start"],
                "selected_return_end": row["selected_return_end"],
                "target_volatility": row["target_volatility"],
                "static_control_scale": row["static_control_scale"],
            }
            for row in calibration_rows
        },
        "identity_complete_state_equivalence_passed": bool(
            not identity_checks.empty and identity_checks["complete_hash_match"].all()
        ),
        "trial_order_independence_passed": bool(not order_checks.empty and order_checks["hash_match"].all()),
        "prior_runs": {
            "validation2": str(PRIOR_VALIDATION),
            "correctness_audit": str(PRIOR_AUDIT),
        },
        "prior_lineage_row_count": int(len(lineage)),
        "outputs": {
            name: str(OUT_DIR / filename)
            for name, filename in {
                "manifest": "manifest.json",
                "trial_registry": "trial_registry.csv",
                "trial_lineage": "trial_lineage.csv",
                "applicability_matrix": "applicability_matrix.csv",
                "calibration_diagnostics": "calibration_diagnostics.csv",
                "volatility_scaler_diagnostics": "volatility_scaler_diagnostics.csv",
                "metrics": "metrics.csv",
                "overlay_events": "overlay_events.csv",
                "cost_exposure_attribution": "cost_exposure_attribution.csv",
                "rebalance_attribution": "rebalance_attribution.csv",
                "comparison": "comparison.md",
                "test_results": "test_results.txt",
                "source_of_truth_update": "source_of_truth_update.md",
            }.items()
        },
    }
    write_json(OUT_DIR / "manifest.json", json_ready(manifest))
    run_test_commands()
    print(f"Canonical exploratory comparison complete: {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
