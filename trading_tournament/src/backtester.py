from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .metrics import build_benchmark_curves, compute_strategy_metrics, monthly_returns, regime_performance
from .overlays import ManagedIntentBatch, TradeManagementOverlay
from .portfolio import Portfolio, Position, is_backtest_strategy
from .risk import compute_target_timing, evaluate_project_stop, project_stop_config, target_timing_frame
from .strategies import A, EntrySignal, ExitSignal, StrategyEngine


@dataclass
class PendingEntry:
    signal: EntrySignal


@dataclass
class PendingExit:
    signal: ExitSignal


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    skipped_signals: pd.DataFrame
    strategy_metrics: pd.DataFrame
    equity_curve: pd.DataFrame
    benchmark_curve: pd.DataFrame
    monthly_returns: pd.DataFrame
    regime_performance: pd.DataFrame
    target_timing: pd.DataFrame
    risk_events: pd.DataFrame
    strategy_lifecycle_events: pd.DataFrame
    overlay_events: pd.DataFrame
    killed_strategies: list[str]
    metadata: dict[str, Any]


def apply_entry_slippage(open_price: float, slippage_pct: float) -> float:
    return float(open_price * (1.0 + slippage_pct))


def apply_exit_slippage(price: float, slippage_pct: float) -> float:
    return float(price * (1.0 - slippage_pct))


def simulate_long_intraday_exit(position: Position, row: pd.Series, slippage_pct: float) -> tuple[float, str] | None:
    required = ["open", "high", "low", "close"]
    if any(pd.isna(row.get(col)) for col in required):
        return float(position.entry_price), "data_issue"

    open_price = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    stop = float(position.stop_price)
    target = position.target_price
    stop_hit = low <= stop
    target_hit = target is not None and high >= target

    if stop_hit:
        if open_price <= stop:
            return apply_exit_slippage(open_price, slippage_pct), "stop_loss_gap"
        return apply_exit_slippage(stop, slippage_pct), "stop_loss"

    if target_hit and target is not None:
        # Conservative daily-bar handling: even if price gaps above target, do not
        # award a better fill than the target.
        return apply_exit_slippage(float(target), slippage_pct), "target_hit"

    return None


class Backtester:
    def __init__(self, data: dict[str, pd.DataFrame], config: dict[str, Any]):
        self.data = data
        self.config = config
        self.indexed_data = {
            symbol: df.sort_values("date").set_index("date", drop=False)
            for symbol, df in data.items()
        }
        self._row_cache: dict[tuple[str, pd.Timestamp], pd.Series | None] = {}
        self._rows_by_date_cache: dict[pd.Timestamp, dict[str, pd.Series]] = {}

    def _calendar(self, start: str, end: str | None) -> list[pd.Timestamp]:
        if "SPY" in self.indexed_data:
            dates = list(pd.to_datetime(self.indexed_data["SPY"].index))
        else:
            dates = sorted({date for df in self.indexed_data.values() for date in pd.to_datetime(df.index)})
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end) if end else max(dates)
        return [pd.Timestamp(d) for d in dates if start_ts <= pd.Timestamp(d) <= end_ts]

    def _effective_calendar(self, start: str, end: str | None) -> list[pd.Timestamp]:
        dates = self._calendar(start, end)
        warmup = int(self.config["project"]["warmup_days"])
        if len(dates) <= warmup:
            return []
        return dates[warmup:]

    def _weekly_rebalance_days(self, dates: list[pd.Timestamp]) -> set[pd.Timestamp]:
        rebalance_days: set[pd.Timestamp] = set()
        for idx, date in enumerate(dates):
            if idx == len(dates) - 1:
                rebalance_days.add(date)
                continue
            this_week = date.isocalendar()[:2]
            next_week = dates[idx + 1].isocalendar()[:2]
            if this_week != next_week:
                rebalance_days.add(date)
        return rebalance_days

    def _row(self, symbol: str, date: pd.Timestamp) -> pd.Series | None:
        date = pd.Timestamp(date)
        cache_key = (symbol, date)
        if cache_key in self._row_cache:
            return self._row_cache[cache_key]
        df = self.indexed_data.get(symbol)
        if df is None or date not in df.index:
            self._row_cache[cache_key] = None
            return None
        row = df.loc[date]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        self._row_cache[cache_key] = row
        return row

    def _rows_by_symbol(self, date: pd.Timestamp) -> dict[str, pd.Series]:
        date = pd.Timestamp(date)
        if date not in self._rows_by_date_cache:
            self._rows_by_date_cache[date] = {
                symbol: row for symbol in self.indexed_data if (row := self._row(symbol, date)) is not None
            }
        return self._rows_by_date_cache[date]

    def _find_position(self, portfolio: Portfolio, trade_id: int) -> Position | None:
        return next((pos for pos in portfolio.positions if pos.trade_id == trade_id), None)

    def _strategy_pnls(self, portfolio: Portfolio, rows: dict[str, pd.Series]) -> tuple[float, dict[str, float], dict[str, float]]:
        equity, unrealized = portfolio.mark_to_market(rows)
        total = {
            strategy: portfolio.realized_pnl_by_strategy.get(strategy, 0.0) + unrealized.get(strategy, 0.0)
            for strategy in portfolio.realized_pnl_by_strategy
        }
        return equity, unrealized, total

    def _risk_event(
        self,
        events: list[dict[str, Any]],
        date: pd.Timestamp,
        event_type: str,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        high_water_mark: float,
        daily_pnl: float = 0.0,
        weekly_pnl: float = 0.0,
        strategy: str = "",
        symbol: str = "",
        notes: str = "",
    ) -> None:
        equity, _, _ = self._strategy_pnls(portfolio, rows)
        events.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "event_type": event_type,
                "strategy": strategy,
                "symbol": symbol,
                "project_equity": equity,
                "high_water_mark": high_water_mark,
                "drawdown_dollars": equity - high_water_mark,
                "drawdown_pct": equity / high_water_mark - 1.0 if high_water_mark else 0.0,
                "daily_pnl": daily_pnl,
                "weekly_pnl": weekly_pnl,
                "total_open_risk": portfolio.current_open_risk(),
                "cluster_open_risk": portfolio.cluster_open_risk(symbol) if symbol else 0.0,
                "notes": notes,
            }
        )

    def _lifecycle_event(
        self,
        events: list[dict[str, Any]],
        date: pd.Timestamp,
        strategy: str,
        event_type: str,
        event_reason: str,
        strategy_pnl: float,
        project_equity: float,
        notes: str = "",
    ) -> None:
        events.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "strategy": strategy,
                "event_type": event_type,
                "event_reason": event_reason,
                "strategy_pnl": strategy_pnl,
                "project_equity": project_equity,
                "notes": notes,
            }
        )

    def _compact_signal_values(self, signal: EntrySignal, row: pd.Series | None) -> str:
        if row is None:
            return "{}"
        keys = {
            "close": "close",
            "sma_50": "sma_50",
            "sma_100": "sma_100",
            "sma_200": "sma_200",
            "ema_10": "ema_10",
            "atr_20": "atr_20",
            "rsi_2": "rsi_2",
            "bollinger_lower": "bb_lower",
            "volume": "volume",
            "volume_sma_20": "avg_volume_20",
            "momentum_63": "ret_63",
            "momentum_126": "ret_126",
            "realized_vol_20": "rv_20",
            "breakout_level": "high_20",
        }
        values: dict[str, Any] = {}
        for label, col in keys.items():
            if col in row and pd.notna(row[col]) and np.isfinite(row[col]):
                values[label] = round(float(row[col]), 6)
        for key in ["score", "rank_score", "rank_at_signal", "pullback_days", "breakout_level"]:
            if key in signal.metadata:
                value = signal.metadata[key]
                values[key] = round(float(value), 6) if isinstance(value, (float, int)) else value
        return json.dumps(values, sort_keys=True)

    def _annotate_signal(
        self,
        signal: EntrySignal,
        date: pd.Timestamp,
        portfolio: Portfolio,
        equity: float,
        total_pnl: dict[str, float],
        high_water_mark: float,
    ) -> EntrySignal:
        row = self._row(signal.symbol, date) if signal.symbol else None
        spy = self._row("SPY", date)
        regime = str(row.get("market_regime", "")) if row is not None else ""
        if not regime and spy is not None:
            regime = str(spy.get("market_regime", ""))
        reason_map = {
            "A_ETF_sector_momentum": ("weekly_momentum_rotation", "ranked_momentum_risk_on", "Weekly momentum rotation selected an eligible top-ranked ETF."),
            "B_ETF_trend_following": ("trend_following_breakout", "trend_breakout", "Trend filter and 20-day breakout conditions were met."),
            "C_swing_trend_pullback": ("swing_trend_pullback", "pullback_reclaim", "Uptrend pullback reclaimed the short trigger."),
            "D_mean_reversion": ("mean_reversion_trend_filter", "oversold_in_uptrend", "Oversold ETF signal appeared while trend filter allowed long exposure."),
            "E_breakout_vcb": ("volatility_contraction_breakout", "volume_confirmed_breakout", "Breakout and volume/volatility filters were satisfied."),
            "N1_dual_momentum_taa": ("dual_momentum_taa", "monthly_dual_momentum_rotation", "Monthly dual momentum TAA selected an eligible ETF or defensive asset."),
            "N2_absolute_trend_taa": ("absolute_trend_taa", "monthly_absolute_trend_allocation", "Monthly absolute-trend TAA selected eligible risk or defensive assets."),
            "N3_dual_momentum_vol_scaled": ("dual_momentum_vol_scaled", "monthly_dual_momentum_vol_scaled", "Monthly dual momentum TAA selected assets with SPY volatility scaling applied."),
            "N4_inverse_vol_defensive_allocation": ("inverse_vol_defensive_allocation", "monthly_inverse_vol_allocation", "Monthly inverse-volatility defensive allocation selected eligible assets."),
        }
        rule_name, reason_code, reason_text = reason_map.get(signal.strategy, ("unknown", "unknown", signal.notes))
        signal.metadata.update(
            {
                "strategy_version": "v1_fixed_rules",
                "entry_rule_name": rule_name,
                "entry_reason_code": reason_code,
                "entry_reason_text": reason_text,
                "signal_values_json": self._compact_signal_values(signal, row),
                "project_equity_at_signal": equity,
                "regime_at_signal": regime,
                "spy_close_at_signal": float(spy["close"]) if spy is not None and pd.notna(spy.get("close")) else np.nan,
                "spy_200sma_at_signal": float(spy["sma_200"]) if spy is not None and pd.notna(spy.get("sma_200")) else np.nan,
                "spy_above_200sma_at_signal": (
                    bool(spy["close"] > spy["sma_200"])
                    if spy is not None and pd.notna(spy.get("close")) and pd.notna(spy.get("sma_200"))
                    else ""
                ),
                "realized_vol_20_at_signal": float(row["rv_20"]) if row is not None and pd.notna(row.get("rv_20")) else np.nan,
                "volatility_regime_at_signal": regime.split("_", 1)[1] if "_" in regime else regime,
                "rank_at_signal": signal.metadata.get("rank_at_signal", ""),
                "total_open_risk_before_entry": portfolio.current_open_risk(),
                "cluster_open_risk_before_entry": portfolio.cluster_open_risk(signal.symbol) if signal.symbol else 0.0,
                "strategy_pnl_before_entry": total_pnl.get(signal.strategy, 0.0),
                "strategy_loss_budget_remaining_before_entry": portfolio.strategy_loss_budget_remaining(
                    signal.strategy, total_pnl.get(signal.strategy, 0.0)
                ),
                "strategy_status_at_entry": portfolio.disabled_strategies.get(signal.strategy, "active"),
                "high_water_mark_at_signal": high_water_mark,
                "drawdown_at_signal": equity - high_water_mark,
            }
        )
        return signal

    def _record_equity_row(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        prior_day_equity: float,
        prior_week_close_equity: float,
        daily_block: bool,
        weekly_block: bool,
        high_water_mark: float,
        absolute_floor_stop_active: bool = False,
        trailing_drawdown_stop_active: bool = False,
    ) -> dict[str, Any]:
        equity, unrealized, total = self._strategy_pnls(portfolio, rows)
        gross_market_value = 0.0
        for pos in portfolio.positions:
            row_for_pos = rows.get(pos.symbol)
            price = pos.entry_price if row_for_pos is None or pd.isna(row_for_pos.get("close")) else float(row_for_pos["close"])
            gross_market_value += abs(pos.shares * price)
        row: dict[str, Any] = {
            "date": date.date().isoformat(),
            "equity": equity,
            "high_water_mark": high_water_mark,
            "drawdown_dollars": equity - high_water_mark,
            "drawdown_pct": equity / high_water_mark - 1.0 if high_water_mark else 0.0,
            "cash": portfolio.cash,
            "synthetic_safe_account_value": portfolio.synthetic_safe_account_value,
            "synthetic_safe_account_weight": portfolio.synthetic_safe_account_value / equity if equity else np.nan,
            "cash_weight": portfolio.cash / equity if equity else np.nan,
            "gross_market_value": gross_market_value,
            "gross_exposure": gross_market_value / equity if equity else np.nan,
            "total_open_risk": portfolio.current_open_risk(),
            "open_positions": len(portfolio.positions),
            "daily_pnl": equity - prior_day_equity,
            "weekly_pnl": equity - prior_week_close_equity,
            "daily_entry_block": daily_block,
            "weekly_entry_block": weekly_block,
            "project_stopped": portfolio.project_stopped,
            "absolute_floor_stop_active": absolute_floor_stop_active,
            "trailing_drawdown_stop_active": trailing_drawdown_stop_active,
            "project_trade_blocked": portfolio.project_stopped,
            "reserve_cash_buffer": float(self.config["project"]["reserve_cash_buffer"]),
        }
        for strategy in portfolio.realized_pnl_by_strategy:
            row[f"{strategy}_realized_pnl"] = portfolio.realized_pnl_by_strategy.get(strategy, 0.0)
            row[f"{strategy}_unrealized_pnl"] = unrealized.get(strategy, 0.0)
            row[f"{strategy}_total_pnl"] = total.get(strategy, 0.0)
            row[f"{strategy}_open_positions"] = len(portfolio.positions_for_strategy(strategy))
        return row

    def _fill_pending_exits(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        pending_exits: list[PendingExit],
        slippage_pct: float,
        overlay: TradeManagementOverlay | None = None,
    ) -> list[PendingExit]:
        remaining: list[PendingExit] = []
        for pending in pending_exits:
            pos = self._find_position(portfolio, pending.signal.trade_id)
            if pos is None:
                continue
            row = self._row(pos.symbol, date)
            if row is None or pd.isna(row.get("open")):
                remaining.append(pending)
                continue
            exit_price = apply_exit_slippage(float(row["open"]), slippage_pct)
            trade = portfolio.close_position(pos, date, exit_price, pending.signal.reason, notes=pending.signal.notes)
            if overlay is not None and trade:
                overlay.on_after_exit_fill(
                    date=date,
                    signal=pending.signal,
                    trade=trade,
                    proposed_order={"side": "exit", "price_source": "next_open"},
                    actual_fill={
                        "fill_price": exit_price,
                        "fill_time": pd.Timestamp(date).isoformat(),
                        "exit_reason": pending.signal.reason,
                    },
                    modeled_cost=abs(pos.shares * exit_price * slippage_pct),
                )
        return remaining

    def _fill_pending_entries(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        engine: StrategyEngine,
        pending_entries: list[PendingEntry],
        slippage_pct: float,
        rows: dict[str, pd.Series],
        high_water_mark: float,
        overlay: TradeManagementOverlay | None = None,
    ) -> list[PendingEntry]:
        remaining: list[PendingEntry] = []
        for pending in pending_entries:
            signal = pending.signal
            row = self._row(signal.symbol, date)
            equity, unrealized, total = self._strategy_pnls(portfolio, rows)
            strategy_pnl = total.get(signal.strategy, 0.0)
            if row is None or pd.isna(row.get("open")):
                remaining.append(pending)
                continue
            entry_price = apply_entry_slippage(float(row["open"]), slippage_pct)
            stop_price, target_price = engine.compute_entry_stop_target(signal, entry_price)
            market_regime = str(row.get("market_regime", "unknown"))
            position = portfolio.attempt_open_position(
                signal,
                date,
                entry_price,
                stop_price,
                target_price,
                equity,
                strategy_pnl,
                market_regime,
                high_water_mark=high_water_mark,
                current_drawdown=equity - high_water_mark,
            )
            if overlay is not None:
                overlay.on_after_entry_fill(
                    date=date,
                    signal=signal,
                    position=position,
                    proposed_order={
                        "side": "entry",
                        "price_source": "next_open",
                        "target_weight": signal.metadata.get("target_weight", np.nan),
                        "requested_risk": signal.requested_risk,
                    },
                    actual_fill=(
                        {
                            "fill_price": entry_price,
                            "fill_time": pd.Timestamp(date).isoformat(),
                            "shares": position.shares,
                            "trade_id": position.trade_id,
                        }
                        if position is not None
                        else None
                    ),
                    modeled_cost=abs(position.shares * entry_price * slippage_pct) if position is not None else 0.0,
                )
        return remaining

    def _process_intraday_stops(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        engine: StrategyEngine,
        slippage_pct: float,
        risk_events: list[dict[str, Any]],
        high_water_mark: float,
        overlay: TradeManagementOverlay | None = None,
    ) -> None:
        for pos in list(portfolio.positions):
            row = self._row(pos.symbol, date)
            if row is None:
                trade = portfolio.close_position(pos, date, pos.entry_price, "data_issue", rule_followed=False, notes="missing daily bar")
                if overlay is not None and trade:
                    overlay.on_after_exit_fill(
                        date=date,
                        signal=None,
                        trade=trade,
                        proposed_order={"side": "exit", "price_source": "data_issue"},
                        actual_fill={"fill_price": pos.entry_price, "fill_time": pd.Timestamp(date).isoformat()},
                        modeled_cost=0.0,
                    )
                continue
            stop_hit = pd.notna(row.get("low")) and float(row["low"]) <= float(pos.stop_price)
            target_hit = pos.target_price is not None and pd.notna(row.get("high")) and float(row["high"]) >= float(pos.target_price)
            if stop_hit and target_hit:
                pos.metadata["same_bar_stop_target"] = True
                self._risk_event(
                    risk_events,
                    date,
                    "same_bar_stop_target_stop_wins",
                    portfolio,
                    self._rows_by_symbol(date),
                    high_water_mark,
                    strategy=pos.strategy,
                    symbol=pos.symbol,
                    notes="Daily bar touched both stop and target; stop assumed first.",
                )
            result = simulate_long_intraday_exit(pos, row, slippage_pct)
            if result is None:
                continue
            exit_price, reason = result
            if reason == "stop_loss_gap":
                self._risk_event(
                    risk_events,
                    date,
                    "gap_through_stop",
                    portfolio,
                    self._rows_by_symbol(date),
                    high_water_mark,
                    strategy=pos.strategy,
                    symbol=pos.symbol,
                    notes="Open was below stop; filled at open.",
                )
            trade = portfolio.close_position(pos, date, exit_price, reason)
            if overlay is not None and trade:
                overlay.on_after_exit_fill(
                    date=date,
                    signal=None,
                    trade=trade,
                    proposed_order={"side": "exit", "price_source": reason},
                    actual_fill={
                        "fill_price": exit_price,
                        "fill_time": pd.Timestamp(date).isoformat(),
                        "exit_reason": reason,
                    },
                    modeled_cost=abs(pos.shares * exit_price * slippage_pct),
                )
            if pos.strategy == A and reason in {"stop_loss", "stop_loss_gap"}:
                engine.mark_a_stopped(pos.symbol)

    def _force_close_strategy(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        strategy: str,
        reason: str,
        slippage_pct: float,
    ) -> None:
        for pos in list(portfolio.positions_for_strategy(strategy)):
            row = self._row(pos.symbol, date)
            if row is None or pd.isna(row.get("close")):
                price = pos.entry_price
                portfolio.close_position(pos, date, price, "data_issue", rule_followed=False, notes=reason)
            else:
                price = apply_exit_slippage(float(row["close"]), slippage_pct)
                portfolio.close_position(pos, date, price, reason)

    def _force_close_all(
        self,
        date: pd.Timestamp,
        portfolio: Portfolio,
        reason: str,
        slippage_pct: float,
    ) -> None:
        for pos in list(portfolio.positions):
            row = self._row(pos.symbol, date)
            if row is None or pd.isna(row.get("close")):
                portfolio.close_position(pos, date, pos.entry_price, "data_issue", rule_followed=False, notes=reason)
            else:
                price = apply_exit_slippage(float(row["close"]), slippage_pct)
                portfolio.close_position(pos, date, price, reason)

    def _final_mark_to_market(self, date: pd.Timestamp, portfolio: Portfolio) -> None:
        for pos in list(portfolio.positions):
            row = self._row(pos.symbol, date)
            if row is None or pd.isna(row.get("close")):
                portfolio.close_position(pos, date, pos.entry_price, "data_issue", rule_followed=False, notes="final missing close")
            else:
                portfolio.close_position(pos, date, float(row["close"]), "final_mark_to_market")

    def _minimal_combined_metrics(self, trades: pd.DataFrame, equity_curve: pd.DataFrame) -> pd.DataFrame:
        equity = equity_curve["equity"].astype(float)
        starting = float(self.config["project"]["starting_equity"])
        running_peak = equity.cummax()
        drawdown_dollars = equity - running_peak
        drawdown_pct = equity / running_peak - 1.0
        return pd.DataFrame(
            [
                {
                    "name": "combined_tournament",
                    "final_equity": float(equity.iloc[-1]),
                    "total_return": float(equity.iloc[-1] / starting - 1.0) if starting else np.nan,
                    "max_drawdown": float(drawdown_dollars.min()),
                    "max_drawdown_pct": float(drawdown_pct.min()),
                    "number_of_trades": int(len(trades)),
                }
            ]
        )

    def _minimal_target_timing(self, equity_curve: pd.DataFrame) -> dict[str, Any]:
        if equity_curve.empty:
            return {}
        equity = equity_curve["equity"].astype(float).reset_index(drop=True)
        dates = equity_curve["date"].astype(str).reset_index(drop=True)
        abs_mask = (
            equity_curve["absolute_floor_stop_active"].fillna(False).astype(bool).reset_index(drop=True)
            if "absolute_floor_stop_active" in equity_curve
            else pd.Series(False, index=equity.index)
        )
        trail_mask = (
            equity_curve["trailing_drawdown_stop_active"].fillna(False).astype(bool).reset_index(drop=True)
            if "trailing_drawdown_stop_active" in equity_curve
            else pd.Series(False, index=equity.index)
        )
        any_mask = abs_mask | trail_mask

        def first_index(mask: pd.Series) -> int | None:
            hits = mask[mask].index
            return int(hits[0]) if len(hits) else None

        abs_idx = first_index(abs_mask)
        trail_idx = first_index(trail_mask)
        any_idx = first_index(any_mask)
        starting = float(self.config["project"]["starting_equity"])
        targets = {
            "target_300": starting + float(self.config["project"]["target_profit_1"]),
            "target_400": starting + float(self.config["project"]["target_profit_2"]),
        }
        out: dict[str, Any] = {}
        for label, target in targets.items():
            hit_idx = first_index(equity >= target)
            hit = hit_idx is not None
            out[f"{label}_hit"] = bool(hit)
            out[f"{label}_first_date"] = dates.iloc[hit_idx] if hit else ""
            out[f"{label}_trading_days"] = int(hit_idx + 1) if hit else pd.NA
            out[f"equity_at_{label}"] = float(equity.iloc[hit_idx]) if hit else float("nan")
            out[f"{label}_before_absolute_stop"] = bool(hit and (abs_idx is None or hit_idx <= abs_idx))
            out[f"{label}_before_trailing_stop"] = bool(hit and (trail_idx is None or hit_idx <= trail_idx))
            out[f"{label}_before_any_stop"] = bool(hit and (any_idx is None or hit_idx <= any_idx))

        out["absolute_floor_stop_hit"] = bool(abs_idx is not None)
        out["absolute_floor_stop_date"] = dates.iloc[abs_idx] if abs_idx is not None else ""
        out["trailing_drawdown_stop_hit"] = bool(trail_idx is not None)
        out["trailing_drawdown_stop_date"] = dates.iloc[trail_idx] if trail_idx is not None else ""
        out["any_project_stop_hit"] = bool(any_idx is not None)
        out["first_project_stop_date"] = dates.iloc[any_idx] if any_idx is not None else ""
        if any_idx is not None:
            stop_row = equity_curve.iloc[any_idx]
            abs_active = bool(stop_row.get("absolute_floor_stop_active", False))
            trail_active = bool(stop_row.get("trailing_drawdown_stop_active", False))
            if abs_active and trail_active:
                stop_type = "absolute_floor_stop_hit,trailing_drawdown_stop_hit"
            elif abs_active:
                stop_type = "absolute_floor_stop_hit"
            else:
                stop_type = "trailing_drawdown_stop_hit"
            out["first_project_stop_type"] = stop_type
            out["equity_at_first_project_stop"] = float(stop_row["equity"])
            out["high_water_mark_at_stop"] = float(stop_row.get("high_water_mark", stop_row["equity"]))
            out["drawdown_at_stop"] = float(stop_row.get("drawdown_dollars", 0.0))
        else:
            out["first_project_stop_type"] = ""
            out["equity_at_first_project_stop"] = float("nan")
            out["high_water_mark_at_stop"] = float("nan")
            out["drawdown_at_stop"] = float("nan")
        return out

    def run(
        self,
        period_name: str,
        start: str,
        end: str | None,
        slippage_pct: float,
        dates_override: list[pd.Timestamp] | None = None,
        lightweight_outputs: bool = False,
        overlay: TradeManagementOverlay | None = None,
        run_id: str | None = None,
        base_strategy_id: str | None = None,
        base_strategy_hash: str | None = None,
    ) -> BacktestResult:
        effective_dates = list(dates_override) if dates_override is not None else self._effective_calendar(start, end)
        if not effective_dates:
            raise RuntimeError(f"No effective trading dates for period {period_name}; check date range and warmup.")

        portfolio = Portfolio(self.config, slippage_pct)
        engine = StrategyEngine(self.data, self.config, indexed_data=self.indexed_data, row_cache=self._row_cache)
        enabled_strategy_ids = [
            strategy
            for strategy, cfg in self.config.get("strategies", {}).items()
            if is_backtest_strategy(strategy, cfg)
        ]
        if overlay is not None:
            overlay.bind(
                run_id=run_id or f"{period_name}_{overlay.overlay_id}",
                base_strategy_id=base_strategy_id or ",".join(enabled_strategy_ids),
                base_strategy_hash=base_strategy_hash or "",
                data=self.data,
                indexed_data=self.indexed_data,
                calendar=effective_dates,
                config=self.config,
            )
        rebalance_days = self._weekly_rebalance_days(effective_dates)
        pending_entries: list[PendingEntry] = []
        pending_exits: list[PendingExit] = []
        pending_exit_ids: set[int] = set()
        equity_rows: list[dict[str, Any]] = []
        killed_strategies: list[str] = []
        risk_events: list[dict[str, Any]] = []
        lifecycle_events: list[dict[str, Any]] = []

        prior_day_equity = float(self.config["project"]["starting_equity"])
        prior_week_close_equity = prior_day_equity
        equity_high_water_mark = prior_day_equity
        previous_date: pd.Timestamp | None = None
        previous_equity = prior_day_equity
        weekly_entry_block = False
        project_stop = project_stop_config(self.config)
        last_stop_eval = evaluate_project_stop(prior_day_equity, equity_high_water_mark, self.config)

        for strategy, cfg in self.config["strategies"].items():
            if is_backtest_strategy(strategy, cfg):
                self._lifecycle_event(
                    lifecycle_events,
                    effective_dates[0],
                    strategy,
                    "strategy_enabled",
                    "configured_enabled",
                    0.0,
                    prior_day_equity,
                )

        for date in effective_dates:
            if previous_date is not None and date.isocalendar()[:2] != previous_date.isocalendar()[:2]:
                prior_week_close_equity = previous_equity
                weekly_entry_block = False

            rows = self._rows_by_symbol(date)
            if overlay is not None:
                overlay.on_before_order_fills(
                    date=date,
                    portfolio=portfolio,
                    rows=rows,
                    pending_entries=pending_entries,
                    pending_exits=pending_exits,
                    slippage_pct=slippage_pct,
                )
            pending_exits = self._fill_pending_exits(date, portfolio, pending_exits, slippage_pct, overlay)
            pending_exit_ids = {pending.signal.trade_id for pending in pending_exits}
            pending_entries = self._fill_pending_entries(
                date,
                portfolio,
                engine,
                pending_entries,
                slippage_pct,
                rows,
                equity_high_water_mark,
                overlay,
            )
            if overlay is not None:
                overlay.process_position_lifecycle(
                    date=date,
                    portfolio=portfolio,
                    rows=self._rows_by_symbol(date),
                    slippage_pct=slippage_pct,
                )
            self._process_intraday_stops(date, portfolio, engine, slippage_pct, risk_events, equity_high_water_mark, overlay)

            for pos in portfolio.positions:
                pos.bars_held += 1

            rows = self._rows_by_symbol(date)
            equity, _, total_pnl = self._strategy_pnls(portfolio, rows)

            for strategy, cfg in self.config["strategies"].items():
                if not is_backtest_strategy(strategy, cfg):
                    continue
                if strategy in portfolio.disabled_strategies:
                    continue
                max_loss = float(cfg["max_strategy_loss"])
                if total_pnl.get(strategy, 0.0) <= -max_loss:
                    portfolio.disabled_strategies[strategy] = "strategy_loss_budget_hit"
                    killed_strategies.append(strategy)
                    self._risk_event(
                        risk_events,
                        date,
                        "strategy_loss_budget_hit",
                        portfolio,
                        rows,
                        equity_high_water_mark,
                        strategy=strategy,
                        notes=f"Strategy P&L {total_pnl.get(strategy, 0.0):.2f} breached max loss {max_loss:.2f}.",
                    )
                    self._lifecycle_event(
                        lifecycle_events,
                        date,
                        strategy,
                        "strategy_disabled_loss_budget",
                        "strategy_loss_budget_hit",
                        total_pnl.get(strategy, 0.0),
                        equity,
                    )
                    self._force_close_strategy(date, portfolio, strategy, "strategy_loss_budget", slippage_pct)
                    pending_entries = [p for p in pending_entries if p.signal.strategy != strategy]
                    pending_exits = [p for p in pending_exits if p.signal.strategy != strategy]

            rows = self._rows_by_symbol(date)
            equity, _, _ = self._strategy_pnls(portfolio, rows)
            equity_high_water_mark = max(equity_high_water_mark, equity)
            last_stop_eval = evaluate_project_stop(equity, equity_high_water_mark, self.config)
            if last_stop_eval["any_project_stop_active"]:
                portfolio.project_stopped = True
                portfolio.project_stop_info = {
                    "project_stop_mode": project_stop["mode"],
                    "absolute_floor_stop_hit": last_stop_eval["absolute_floor_stop_hit"],
                    "absolute_floor_stop_date": date.date().isoformat()
                    if last_stop_eval["absolute_floor_stop_active"]
                    else "",
                    "trailing_drawdown_stop_hit": last_stop_eval["trailing_drawdown_stop_hit"],
                    "trailing_drawdown_stop_date": date.date().isoformat()
                    if last_stop_eval["trailing_drawdown_stop_active"]
                    else "",
                    "first_project_stop_type": last_stop_eval["first_project_stop_type"],
                    "first_project_stop_date": date.date().isoformat(),
                    "equity_at_first_project_stop": equity,
                    "high_water_mark_at_stop": equity_high_water_mark,
                    "drawdown_at_stop": equity - equity_high_water_mark,
                }
                if last_stop_eval["absolute_floor_stop_active"]:
                    self._risk_event(
                        risk_events,
                        date,
                        "absolute_floor_stop_hit",
                        portfolio,
                        rows,
                        equity_high_water_mark,
                        notes=f"Equity <= absolute floor {project_stop['absolute_floor_equity']:.2f}.",
                    )
                if last_stop_eval["trailing_drawdown_stop_active"]:
                    self._risk_event(
                        risk_events,
                        date,
                        "trailing_drawdown_stop_hit",
                        portfolio,
                        rows,
                        equity_high_water_mark,
                        notes=f"Equity <= high water mark - {project_stop['trailing_drawdown_dollars']:.2f}.",
                    )
                exit_reason = (
                    "absolute_floor_stop_hit"
                    if last_stop_eval["absolute_floor_stop_active"]
                    else "trailing_drawdown_stop_hit"
                )
                self._force_close_all(date, portfolio, exit_reason, slippage_pct)
                pending_entries.clear()
                pending_exits.clear()
                rows = self._rows_by_symbol(date)
                equity, _, _ = self._strategy_pnls(portfolio, rows)

            daily_pnl = equity - prior_day_equity
            weekly_pnl = equity - prior_week_close_equity
            daily_entry_block = daily_pnl <= -float(self.config["project"]["max_daily_loss"])
            if weekly_pnl <= -float(self.config["project"]["max_weekly_loss"]):
                weekly_entry_block = True
            if daily_entry_block:
                self._risk_event(
                    risk_events,
                    date,
                    "daily_loss_block_triggered",
                    portfolio,
                    rows,
                    equity_high_water_mark,
                    daily_pnl=daily_pnl,
                    weekly_pnl=weekly_pnl,
                    notes="New entries blocked for the rest of the day.",
                )
            if weekly_entry_block:
                self._risk_event(
                    risk_events,
                    date,
                    "weekly_loss_block_triggered",
                    portfolio,
                    rows,
                    equity_high_water_mark,
                    daily_pnl=daily_pnl,
                    weekly_pnl=weekly_pnl,
                    notes="New entries blocked for the rest of the week.",
                )

            is_rebalance = date in rebalance_days
            if not portfolio.project_stopped:
                exits = engine.generate_exits(date, portfolio, is_rebalance)
                entry_signals: list[EntrySignal] = []

                if not daily_entry_block and not weekly_entry_block:
                    signals = engine.generate_entries(date, portfolio, is_rebalance)
                    for signal in signals:
                        rows_now = self._rows_by_symbol(date)
                        equity_now, _, total_now = self._strategy_pnls(portfolio, rows_now)
                        signal = self._annotate_signal(
                            signal, date, portfolio, equity_now, total_now, equity_high_water_mark
                        )
                        skip_reason = signal.metadata.get("skip_reason")
                        if skip_reason:
                            portfolio.log_skip_signal(
                                date,
                                signal.strategy,
                                signal.symbol,
                                signal.signal_type,
                                skip_reason,
                                signal.requested_risk,
                                equity_now,
                                total_now.get(signal.strategy, 0.0),
                                signal.notes,
                                high_water_mark=equity_high_water_mark,
                                current_drawdown=equity_now - equity_high_water_mark,
                                rank_at_signal=signal.metadata.get("rank_at_signal", ""),
                                regime_at_signal=signal.metadata.get("regime_at_signal", ""),
                            )
                            self._lifecycle_event(
                                lifecycle_events,
                                date,
                                signal.strategy,
                                "strategy_no_eligible_symbols",
                                skip_reason,
                                total_now.get(signal.strategy, 0.0),
                                equity_now,
                                signal.notes,
                            )
                        else:
                            entry_signals.append(signal)

                if overlay is not None:
                    rows_now = self._rows_by_symbol(date)
                    equity_now, _, _ = self._strategy_pnls(portfolio, rows_now)
                    managed_batch = overlay.on_signal_batch(
                        date=date,
                        entries=entry_signals,
                        exits=exits,
                        portfolio=portfolio,
                        rows=rows_now,
                        equity=equity_now,
                        pending_exit_ids=pending_exit_ids | {exit_signal.trade_id for exit_signal in exits},
                    )
                else:
                    managed_batch = ManagedIntentBatch(entries=entry_signals, exits=exits)

                for exit_signal in managed_batch.exits:
                    if exit_signal.trade_id not in pending_exit_ids:
                        pending_exits.append(PendingExit(exit_signal))
                        pending_exit_ids.add(exit_signal.trade_id)
                for signal in managed_batch.entries:
                    pending_entries.append(PendingEntry(signal))

                engine.update_trailing_stops(date, portfolio)

            if overlay is not None:
                overlay.on_end_of_day(
                    date=date,
                    portfolio=portfolio,
                    rows=self._rows_by_symbol(date),
                    slippage_pct=slippage_pct,
                )

            equity_rows.append(
                self._record_equity_row(
                    date,
                    portfolio,
                    self._rows_by_symbol(date),
                    prior_day_equity,
                    prior_week_close_equity,
                    daily_entry_block,
                    weekly_entry_block,
                    equity_high_water_mark,
                    bool(last_stop_eval.get("absolute_floor_stop_active", False)),
                    bool(last_stop_eval.get("trailing_drawdown_stop_active", False)),
                )
            )
            previous_date = date
            previous_equity = equity_rows[-1]["equity"]
            prior_day_equity = previous_equity

            if portfolio.project_stopped:
                break

        final_date = pd.Timestamp(equity_rows[-1]["date"])
        open_before_final = len(portfolio.positions)
        self._final_mark_to_market(final_date, portfolio)
        if open_before_final:
            self._risk_event(
                risk_events,
                final_date,
                "final_mark_to_market",
                portfolio,
                self._rows_by_symbol(final_date),
                equity_high_water_mark,
                notes=f"{open_before_final} open positions closed/marked at final adjusted close.",
            )
        if overlay is not None:
            overlay.on_end_of_day(
                date=final_date,
                portfolio=portfolio,
                rows=self._rows_by_symbol(final_date),
                slippage_pct=slippage_pct,
            )
        final_rows = self._rows_by_symbol(final_date)
        if equity_rows:
            final_equity, _, _ = self._strategy_pnls(portfolio, final_rows)
            equity_high_water_mark = max(equity_high_water_mark, final_equity)
            final_stop_eval = evaluate_project_stop(final_equity, equity_high_water_mark, self.config)
            equity_rows[-1] = self._record_equity_row(
                final_date,
                portfolio,
                final_rows,
                equity_rows[-2]["equity"] if len(equity_rows) > 1 else float(self.config["project"]["starting_equity"]),
                prior_week_close_equity,
                bool(equity_rows[-1]["daily_entry_block"]),
                bool(equity_rows[-1]["weekly_entry_block"]),
                equity_high_water_mark,
                bool(final_stop_eval.get("absolute_floor_stop_active", False)),
                bool(final_stop_eval.get("trailing_drawdown_stop_active", False)),
            )

        equity_curve = pd.DataFrame(equity_rows)
        trades = portfolio.trades_frame()
        skipped = portfolio.skipped_frame()
        for _, skip in skipped.iterrows():
            event_type = {
                "max_open_risk_exceeded": "max_open_risk_block",
                "correlation_cluster_risk_exceeded": "cluster_risk_block",
                "position_limit_exceeded": "strategy_position_limit_reached",
            }.get(skip.get("reason_skipped"))
            if event_type:
                risk_events.append(
                    {
                        "date": skip["date"],
                        "event_type": event_type,
                        "strategy": skip["strategy"],
                        "symbol": skip["symbol"],
                        "project_equity": skip["project_equity"],
                        "high_water_mark": skip.get("high_water_mark", skip["project_equity"]),
                        "drawdown_dollars": skip.get("current_drawdown", 0.0),
                        "drawdown_pct": (
                            skip.get("current_drawdown", 0.0) / skip.get("high_water_mark", skip["project_equity"])
                            if skip.get("high_water_mark", skip["project_equity"])
                            else 0.0
                        ),
                        "daily_pnl": np.nan,
                        "weekly_pnl": np.nan,
                        "total_open_risk": skip.get("total_open_risk", np.nan),
                        "cluster_open_risk": skip.get("cluster_open_risk", np.nan),
                        "notes": f"Skipped signal: {skip['reason_skipped']}",
                    }
                )
                lifecycle_events.append(
                    {
                        "date": skip["date"],
                        "strategy": skip["strategy"],
                        "event_type": (
                            "strategy_position_limit_reached"
                            if event_type == "strategy_position_limit_reached"
                            else "strategy_risk_cap_block"
                        ),
                        "event_reason": skip["reason_skipped"],
                        "strategy_pnl": skip.get("strategy_pnl", np.nan),
                        "project_equity": skip.get("project_equity", np.nan),
                        "notes": skip.get("notes", ""),
                    }
                )

        if lightweight_outputs:
            benchmark = pd.DataFrame()
            strategy_metrics = self._minimal_combined_metrics(trades, equity_curve)
            monthlies = pd.DataFrame()
            regimes = pd.DataFrame()
            target_dict = self._minimal_target_timing(equity_curve)
            target_timing = pd.DataFrame([target_dict]) if target_dict else pd.DataFrame()
        else:
            benchmark = build_benchmark_curves(self.data, [pd.Timestamp(d) for d in equity_curve["date"]], self.config)
            strategy_metrics = compute_strategy_metrics(trades, equity_curve, self.config, benchmark)
            monthlies = monthly_returns(equity_curve, benchmark)
            regimes = regime_performance(trades)
            target_timing = target_timing_frame(equity_curve, self.config)
            target_dict = target_timing.iloc[0].to_dict() if not target_timing.empty else {}
        stop_info = {
            "absolute_floor_stop_hit": False,
            "absolute_floor_stop_date": "",
            "trailing_drawdown_stop_hit": False,
            "trailing_drawdown_stop_date": "",
            "first_project_stop_type": "",
            "first_project_stop_date": "",
            "equity_at_first_project_stop": np.nan,
            "high_water_mark_at_stop": np.nan,
            "drawdown_at_stop": np.nan,
        }
        stop_info.update(portfolio.project_stop_info)

        metadata = {
            "period_name": period_name,
            "requested_start": start,
            "requested_end": end,
            "effective_first_trading_date": equity_curve["date"].iloc[0],
            "effective_last_trading_date": equity_curve["date"].iloc[-1],
            "slippage_pct_per_side": slippage_pct,
            "overlay_id": overlay.overlay_id if overlay is not None else "",
            "overlay_version": overlay.version if overlay is not None else "",
            "overlay_config_hash": overlay.config_hash if overlay is not None else "",
            "project_stop_mode": project_stop["mode"],
            "project_stop_hit": bool(portfolio.project_stopped),
            **stop_info,
            **target_dict,
            "killed_strategies": sorted(set(killed_strategies)),
        }
        return BacktestResult(
            trades=trades,
            skipped_signals=skipped,
            strategy_metrics=strategy_metrics,
            equity_curve=equity_curve,
            benchmark_curve=benchmark,
            monthly_returns=monthlies,
            regime_performance=regimes,
            target_timing=target_timing,
            risk_events=pd.DataFrame(risk_events),
            strategy_lifecycle_events=pd.DataFrame(lifecycle_events),
            overlay_events=overlay.events_frame() if overlay is not None else pd.DataFrame(),
            killed_strategies=sorted(set(killed_strategies)),
            metadata=metadata,
        )
