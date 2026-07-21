from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.backtester import Backtester, BacktestResult
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.metrics import cagr, max_drawdown, recovery_time_days, sharpe_ratio, sortino_ratio
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
from src.utils import config_hash, git_commit_hash, load_config, sha256_file, write_json


ROOT = Path(__file__).resolve().parent
FROZEN_STRATEGIES = [
    {
        "strategy_id": "N2_absolute_trend_taa",
        "kind": "monthly_or_periodic_asset_allocation",
        "signal_timing": "month-end signal, next-open execution",
    },
    {
        "strategy_id": "B_ETF_trend_following",
        "kind": "daily",
        "signal_timing": "daily close signal, next-open execution",
    },
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research-only trade-management overlay comparisons.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--slippages", default="0,0.0005,0.001")
    parser.add_argument("--lightweight", action="store_true", default=True)
    return parser.parse_args(argv)


def _run_id() -> str:
    return "tmovl_" + datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _strategy_only_config(config: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    cfg["strategy_order"] = [strategy_id]
    for name, strategy_cfg in cfg.get("strategies", {}).items():
        strategy_cfg["enabled"] = name == strategy_id
    return cfg


def _strategy_source_hash(config: dict[str, Any], strategy_id: str) -> str:
    payload = {
        "strategy_id": strategy_id,
        "strategy_config": config.get("strategies", {}).get(strategy_id, {}),
        "strategies_py_sha256": sha256_file(ROOT / "src" / "strategies.py"),
        "backtester_py_sha256": sha256_file(ROOT / "src" / "backtester.py"),
    }
    return stable_hash(payload)


def _period_end(config: dict[str, Any], explicit_end: str | None) -> str | None:
    return explicit_end if explicit_end is not None else config.get("data", {}).get("end_date")


def _combined_metrics(result: BacktestResult) -> pd.Series:
    metrics = result.strategy_metrics
    if metrics.empty:
        return pd.Series(dtype=object)
    row = metrics.loc[metrics["name"] == "combined_tournament"]
    return row.iloc[0] if not row.empty else metrics.iloc[0]


def _turnover(trades: pd.DataFrame, equity_curve: pd.DataFrame) -> float:
    if trades.empty or equity_curve.empty:
        return 0.0
    entry_notional = trades.get("notional_value", pd.Series(dtype=float)).astype(float).abs().sum()
    exit_notional = (trades["shares"].astype(float).abs() * trades["exit_price"].astype(float).abs()).sum()
    average_equity = equity_curve["equity"].astype(float).mean()
    return float((entry_notional + exit_notional) / average_equity) if average_equity else np.nan


def _events_count(events: pd.DataFrame, reason_codes: set[str] | None = None, decision_types: set[str] | None = None) -> int:
    if events.empty:
        return 0
    mask = pd.Series(True, index=events.index)
    if reason_codes is not None:
        mask &= events["reason_code"].isin(reason_codes)
    if decision_types is not None:
        mask &= events["decision_type"].isin(decision_types)
    return int(mask.sum())


def summarize_result(
    *,
    result: BacktestResult,
    strategy_id: str,
    strategy_kind: str,
    trial_name: str,
    overlay_id: str,
    slippage: float,
    status: str,
    error: str = "",
    validation_label: str = "research_only_exploratory",
) -> dict[str, Any]:
    combined = _combined_metrics(result)
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    equity_series = equity["equity"].astype(float)
    dates = equity["date"]
    dd_dollars, dd_pct = max_drawdown(equity_series)
    total_return = float(equity_series.iloc[-1] / equity_series.iloc[0] - 1.0) if len(equity_series) else np.nan
    return_to_drawdown = total_return / abs(dd_pct) if dd_pct not in (0.0, np.nan) and np.isfinite(dd_pct) else np.nan
    trades = result.trades
    events = result.overlay_events
    worst_trade = ""
    if not trades.empty and "pnl" in trades:
        worst = trades.sort_values("pnl", ascending=True).iloc[0]
        worst_trade = f"{worst.get('symbol', '')}:{float(worst.get('pnl', 0.0)):.2f}"

    return {
        "strategy_id": strategy_id,
        "strategy_kind": strategy_kind,
        "trial_name": trial_name,
        "overlay_id": overlay_id,
        "slippage_bps_per_side": slippage * 10000.0,
        "status": status,
        "error": error,
        "validation_label": validation_label,
        "start": result.metadata.get("effective_first_trading_date", ""),
        "end": result.metadata.get("effective_last_trading_date", ""),
        "total_return": total_return,
        "annualized_return": cagr(equity_series, dates),
        "annualized_volatility": float(equity_series.pct_change().std() * np.sqrt(252)) if len(equity_series) > 1 else np.nan,
        "max_drawdown": dd_dollars,
        "max_drawdown_pct": dd_pct,
        "drawdown_duration_days": recovery_time_days(equity_series),
        "sharpe": sharpe_ratio(equity_series),
        "sortino": sortino_ratio(equity_series),
        "return_to_drawdown": return_to_drawdown,
        "average_gross_exposure": float(equity.get("gross_exposure", pd.Series(dtype=float)).mean()),
        "maximum_gross_exposure": float(equity.get("gross_exposure", pd.Series(dtype=float)).max()),
        "average_cash_weight": float(equity.get("cash_weight", pd.Series(dtype=float)).mean()),
        "turnover": _turnover(trades, equity),
        "number_of_orders": int(len(trades) * 2),
        "number_of_fills": int(len(trades) * 2),
        "modeled_transaction_cost": float(trades.get("slippage_paid_estimate", pd.Series(dtype=float)).sum()),
        "number_skipped_or_resized_orders": _events_count(
            events,
            decision_types={"suppress_order", "resize_target"},
        ),
        "number_stop_events": _events_count(events, reason_codes={"atr_stop_normal_touch", "atr_stop_gap_through"}),
        "number_time_exit_events": _events_count(events, reason_codes={"time_stop"}),
        "average_holding_period": float(trades["holding_days"].mean()) if not trades.empty and "holding_days" in trades else np.nan,
        "trade_mfe": "unavailable_in_existing_trade_schema",
        "trade_mae": "unavailable_in_existing_trade_schema",
        "worst_trade": worst_trade,
        "final_equity": float(combined.get("final_equity", equity_series.iloc[-1] if len(equity_series) else np.nan)),
        "number_of_trades": int(combined.get("number_of_trades", len(trades))),
    }


def failed_summary(
    *,
    strategy_id: str,
    strategy_kind: str,
    trial_name: str,
    overlay_id: str,
    slippage: float,
    error: str,
) -> dict[str, Any]:
    row = {
        "strategy_id": strategy_id,
        "strategy_kind": strategy_kind,
        "trial_name": trial_name,
        "overlay_id": overlay_id,
        "slippage_bps_per_side": slippage * 10000.0,
        "status": "failed",
        "error": error,
        "validation_label": "research_only_exploratory",
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


def run_trial(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    strategy: dict[str, str],
    trial_name: str,
    overlay_factory: Callable[[], TradeManagementOverlay | None],
    slippage: float,
    start: str,
    end: str | None,
    run_id: str,
    lightweight: bool,
) -> tuple[dict[str, Any], pd.DataFrame, BacktestResult | None]:
    strategy_id = strategy["strategy_id"]
    strategy_hash = _strategy_source_hash(config, strategy_id)
    overlay = overlay_factory()
    overlay_id = overlay.overlay_id if overlay is not None else "BASE"
    trial_run_id = f"{run_id}_{strategy_id}_{trial_name}_{int(round(slippage * 10000))}bps"
    print(
        f"Running {strategy_id} / {trial_name} / {slippage * 10000.0:.1f} bps / {overlay_id}...",
        flush=True,
    )
    try:
        bt = Backtester(prepared, config)
        result = bt.run(
            trial_name,
            start,
            end,
            slippage,
            lightweight_outputs=lightweight,
            overlay=overlay,
            run_id=trial_run_id,
            base_strategy_id=strategy_id,
            base_strategy_hash=strategy_hash,
        )
        row = summarize_result(
            result=result,
            strategy_id=strategy_id,
            strategy_kind=strategy["kind"],
            trial_name=trial_name,
            overlay_id=overlay_id,
            slippage=slippage,
            status="completed",
        )
        events = result.overlay_events.copy()
        if not events.empty:
            events.insert(0, "trial_name", trial_name)
            events.insert(0, "strategy_id", strategy_id)
            events.insert(0, "slippage_bps_per_side", slippage * 10000.0)
        return row, events, result
    except Exception as exc:
        print(f"FAILED {strategy_id} / {trial_name} / {overlay_id}: {exc}", flush=True)
        return (
            failed_summary(
                strategy_id=strategy_id,
                strategy_kind=strategy["kind"],
                trial_name=trial_name,
                overlay_id=overlay_id,
                slippage=slippage,
                error=str(exc),
            ),
            pd.DataFrame(),
            None,
        )


def _median_capped_scale(events: pd.DataFrame) -> float:
    if events.empty or "data_quality_flags" not in events:
        return 1.0
    scales: list[float] = []
    for value in events["data_quality_flags"]:
        try:
            flags = json.loads(value) if isinstance(value, str) and value else {}
        except json.JSONDecodeError:
            flags = {}
        scale = flags.get("capped_scale")
        if scale is not None and np.isfinite(float(scale)):
            scales.append(float(scale))
    if not scales:
        return 1.0
    return float(np.median(scales))


def _write_comparison_md(path: Path, metrics: pd.DataFrame, manifest: dict[str, Any]) -> None:
    display_cols = [
        "strategy_id",
        "trial_name",
        "overlay_id",
        "slippage_bps_per_side",
        "status",
        "total_return",
        "annualized_volatility",
        "max_drawdown_pct",
        "sharpe",
        "average_gross_exposure",
        "number_skipped_or_resized_orders",
        "number_stop_events",
        "number_time_exit_events",
    ]
    table = metrics[display_cols].copy() if not metrics.empty else pd.DataFrame(columns=display_cols)
    for col in ["total_return", "annualized_volatility", "max_drawdown_pct", "sharpe", "average_gross_exposure"]:
        if col in table:
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    lines = [
        "| " + " | ".join(table.columns) + " |",
        "| " + " | ".join("---" for _ in table.columns) + " |",
    ]
    for _, row in table.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(row[col]) else str(row[col]) for col in table.columns) + " |")
    markdown = [
        "# Trade Management Overlay Comparison",
        "",
        "Research-only and exploratory. No paper, demo, broker, scheduled, webhook, live order-routing, or account-management path was activated or modified.",
        "",
        "## Frozen Bases",
    ]
    for frozen in manifest["frozen_bases"]:
        markdown.extend(
            [
                f"- `{frozen['strategy_id']}` ({frozen['kind']}): {frozen['signal_timing']}; universe={', '.join(frozen['universe'])}; source_hash={frozen['source_hash'][:12]}.",
            ]
        )
    markdown.extend(
        [
            "",
            "## Architecture Points",
            "See `docs/trade_management_overlay_architecture.md` for the implementation notes and map.",
            "",
            "## Results",
            "\n".join(lines),
            "",
            "## Lower Exposure Attribution",
            "Rows with materially lower average gross exposure should be interpreted as exposure changes first and overlay edge second. The static lower-exposure control is included for the volatility overlay where calibration produced a scale.",
            "",
            "## Limitations",
            "- MFE/MAE are marked unavailable because the canonical trade schema does not store path-level trade excursions.",
            "- Group caps use existing portfolio clusters; no new sector classifier was introduced.",
            "- Short symmetry is implemented in the ATR stop fill helper, but the canonical portfolio engine remains long-only.",
        ]
    )
    path.write_text("\n".join(markdown), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or _run_id()
    out_dir = ROOT / "reports" / "trade_management" / run_id
    out_dir.mkdir(parents=True, exist_ok=False)

    config = load_config(ROOT / "config.yaml")
    config["project_root"] = str(ROOT)
    start = args.start or str(config["date_ranges"]["full"]["start"])
    end = _period_end(config, args.end)
    slippages = [float(value) for value in args.slippages.split(",") if value.strip()]

    data_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(data_result.data)
    data_result.coverage.to_csv(out_dir / "data_coverage.csv", index=False)

    metrics_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    event_frames: list[pd.DataFrame] = []
    frozen_bases: list[dict[str, Any]] = []

    for strategy in FROZEN_STRATEGIES:
        strategy_id = strategy["strategy_id"]
        strategy_cfg = _strategy_only_config(config, strategy_id)
        strategy_hash = _strategy_source_hash(strategy_cfg, strategy_id)
        frozen_bases.append(
            {
                "strategy_id": strategy_id,
                "configuration": strategy_cfg["strategies"][strategy_id],
                "kind": strategy["kind"],
                "current_repository_commit": git_commit_hash(ROOT),
                "source_hash": strategy_hash,
                "data_source": data_result.data_source,
                "date_range": {"start": start, "end": end},
                "universe": list(strategy_cfg["universe"]["symbols"]),
                "signal_timing": strategy["signal_timing"],
                "execution_assumptions": strategy_cfg.get("execution", {}),
                "cost_assumptions": {
                    "slippage_bps_per_side": [value * 10000.0 for value in slippages],
                    "commission_model": "none",
                },
            }
        )

        standard_slippage = 0.0005 if 0.0005 in slippages else slippages[0]
        calibration = config["date_ranges"].get("in_sample", {})
        calibration_row, calibration_events, calibration_result = run_trial(
            prepared=prepared,
            config=strategy_cfg,
            strategy=strategy,
            trial_name="calibration_base",
            overlay_factory=lambda: None,
            slippage=standard_slippage,
            start=str(calibration.get("start", start)),
            end=calibration.get("end"),
            run_id=run_id,
            lightweight=args.lightweight,
        )
        metrics_rows.append(calibration_row)
        registry_rows.append(calibration_row)
        if not calibration_events.empty:
            event_frames.append(calibration_events)
        base_standard_row, _, base_standard = run_trial(
            prepared=prepared,
            config=strategy_cfg,
            strategy=strategy,
            trial_name="base",
            overlay_factory=lambda: None,
            slippage=standard_slippage,
            start=start,
            end=end,
            run_id=run_id,
            lightweight=args.lightweight,
        )
        metrics_rows.append(base_standard_row)
        registry_rows.append(base_standard_row)

        if base_standard is None:
            continue

        try:
            target_vol = LaggedVolatilityTargetOverlay.calibration_target_from_equity(
                (calibration_result or base_standard).equity_curve,
                calibration_start=calibration.get("start"),
                calibration_end=calibration.get("end"),
                lookback=63,
            )
        except Exception:
            target_vol = float(base_standard.equity_curve["equity"].pct_change().rolling(63).std().dropna().median() * np.sqrt(252))

        overlay_factories: list[tuple[str, Callable[[], TradeManagementOverlay | None]]] = [
            ("identity", lambda: IdentityOverlay()),
            ("rebalance_band", lambda: RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)),
            ("lagged_volatility_target", lambda target_vol=target_vol: LaggedVolatilityTargetOverlay(target_volatility=target_vol)),
            ("exposure_caps", lambda: ExposureCapsOverlay(max_gross_exposure=1.0)),
            ("wide_atr_catastrophic_stop", lambda: WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)),
        ]
        if strategy["kind"] == "daily":
            overlay_factories.append(
                ("time_stop", lambda strategy_id=strategy_id: TimeStopOverlay(max_completed_bars=5, strategies=[strategy_id]))
            )

        lagged_standard_events = pd.DataFrame()
        for slippage in slippages:
            if slippage != standard_slippage:
                row, events, _ = run_trial(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy=strategy,
                    trial_name="base",
                    overlay_factory=lambda: None,
                    slippage=slippage,
                    start=start,
                    end=end,
                    run_id=run_id,
                    lightweight=args.lightweight,
                )
                metrics_rows.append(row)
                registry_rows.append(row)
                if not events.empty:
                    event_frames.append(events)
            for trial_name, factory in overlay_factories:
                row, events, _ = run_trial(
                    prepared=prepared,
                    config=strategy_cfg,
                    strategy=strategy,
                    trial_name=trial_name,
                    overlay_factory=factory,
                    slippage=slippage,
                    start=start,
                    end=end,
                    run_id=run_id,
                    lightweight=args.lightweight,
                )
                metrics_rows.append(row)
                registry_rows.append(row)
                if not events.empty:
                    event_frames.append(events)
                if trial_name == "lagged_volatility_target" and slippage == standard_slippage:
                    lagged_standard_events = events

        static_scale = min(1.0, max(0.25, _median_capped_scale(lagged_standard_events)))
        for slippage in slippages:
            row, events, _ = run_trial(
                prepared=prepared,
                config=strategy_cfg,
                strategy=strategy,
                trial_name="static_lower_exposure_control",
                overlay_factory=lambda static_scale=static_scale: StaticScaleOverlay(scale=static_scale),
                slippage=slippage,
                start=start,
                end=end,
                run_id=run_id,
                lightweight=args.lightweight,
            )
            row["static_control_scale"] = static_scale
            metrics_rows.append(row)
            registry_rows.append(row)
            if not events.empty:
                event_frames.append(events)

    metrics = pd.DataFrame(metrics_rows)
    registry = pd.DataFrame(registry_rows)
    overlay_events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()

    metrics.to_csv(out_dir / "metrics.csv", index=False)
    registry.to_csv(out_dir / "trial_registry.csv", index=False)
    overlay_events.to_csv(out_dir / "overlay_events.csv", index=False)

    manifest = {
        "run_id": run_id,
        "research_only": True,
        "validation_label": "research_only_exploratory",
        "created_utc": datetime.now(UTC).isoformat(),
        "config_hash": config_hash(config),
        "frozen_bases": frozen_bases,
        "trial_count": int(len(registry)),
        "failed_trial_count": int((registry["status"] == "failed").sum()) if not registry.empty else 0,
        "paper_demo_live_broker_scheduler_webhook_paths_activated": False,
        "paper_demo_live_broker_scheduler_webhook_paths_modified": False,
        "overlay_combinations_run": False,
        "architecture_notes": str(ROOT / "docs" / "trade_management_overlay_architecture.md"),
        "outputs": {
            "manifest": str(out_dir / "manifest.json"),
            "metrics": str(out_dir / "metrics.csv"),
            "trial_registry": str(out_dir / "trial_registry.csv"),
            "overlay_events": str(out_dir / "overlay_events.csv"),
            "comparison": str(out_dir / "comparison.md"),
        },
    }
    write_json(out_dir / "manifest.json", manifest)
    _write_comparison_md(out_dir / "comparison.md", metrics, manifest)
    print(f"Trade-management overlay comparison complete: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
