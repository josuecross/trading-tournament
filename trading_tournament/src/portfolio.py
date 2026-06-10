from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


ALLOWED_SKIP_REASONS = {
    "invalid_stop_distance",
    "max_open_risk_exceeded",
    "correlation_cluster_risk_exceeded",
    "strategy_loss_budget_hit",
    "project_stop_hit",
    "insufficient_data",
    "no_eligible_symbols",
    "missing_price_data",
    "position_limit_exceeded",
    "duplicate_position",
    "not_enough_cash_or_notional_cap",
}

RISK_LIMIT_EXIT_REASONS = {
    "project_stop",
    "absolute_floor_stop_hit",
    "trailing_drawdown_stop_hit",
    "strategy_loss_budget",
    "daily_loss",
    "weekly_loss",
    "forced_risk_rule",
}


def is_backtest_strategy(name: str, cfg: dict[str, Any] | None = None) -> bool:
    if cfg is not None and not cfg.get("enabled", False):
        return False
    return not name.startswith(("F_", "G_"))


@dataclass
class Position:
    trade_id: int
    strategy: str
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float | None
    shares: float
    risk_amount: float
    requested_risk: float
    market_regime_at_entry: str
    notes: str = ""
    highest_close: float = 0.0
    bars_held: int = 0
    entry_signal_date: pd.Timestamp | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def open_risk(self) -> float:
        return max(0.0, (self.entry_price - self.stop_price) * self.shares)


def calculate_position_size(
    entry_price: float,
    stop_price: float,
    risk_dollars: float,
    account_equity: float,
    available_cash: float,
    max_notional_pct: float,
    min_stop_distance: float = 0.01,
) -> tuple[float, float, str | None]:
    if not np.isfinite(entry_price) or not np.isfinite(stop_price) or entry_price <= 0:
        return 0.0, 0.0, "missing_price_data"
    stop_distance = abs(entry_price - stop_price)
    if not np.isfinite(stop_distance) or stop_distance < min_stop_distance:
        return 0.0, 0.0, "invalid_stop_distance"
    if stop_price >= entry_price:
        return 0.0, 0.0, "invalid_stop_distance"

    raw_shares = risk_dollars / stop_distance
    max_notional = max(0.0, account_equity * max_notional_pct)
    affordable_notional = max(0.0, min(max_notional, available_cash))
    capped_shares = min(raw_shares, affordable_notional / entry_price)
    actual_risk = capped_shares * stop_distance
    if capped_shares <= 0 or actual_risk <= 0:
        return 0.0, 0.0, "not_enough_cash_or_notional_cap"
    return float(capped_shares), float(actual_risk), None


class Portfolio:
    def __init__(self, config: dict[str, Any], slippage_pct: float):
        self.config = config
        self.slippage_pct = slippage_pct
        self.starting_equity = float(config["project"]["starting_equity"])
        self.cash = self.starting_equity
        self.positions: list[Position] = []
        self.closed_trades: list[dict[str, Any]] = []
        self.skipped_signals: list[dict[str, Any]] = []
        self.realized_pnl_by_strategy = {
            name: 0.0 for name, cfg in config.get("strategies", {}).items() if is_backtest_strategy(name, cfg)
        }
        self.disabled_strategies: dict[str, str] = {}
        self.trade_counter = 0
        self.project_stopped = False
        self.project_stop_info: dict[str, Any] = {}
        self.daily_entry_block = False
        self.weekly_entry_block = False

    def cluster_for_symbol(self, symbol: str) -> str:
        for cluster, symbols in self.config["universe"].get("clusters", {}).items():
            if symbol in symbols:
                return cluster
        return "other"

    def current_open_risk(self) -> float:
        return float(sum(pos.open_risk() for pos in self.positions))

    def cluster_open_risk(self, symbol: str) -> float:
        cluster = self.cluster_for_symbol(symbol)
        return float(sum(pos.open_risk() for pos in self.positions if self.cluster_for_symbol(pos.symbol) == cluster))

    def positions_for_strategy(self, strategy: str) -> list[Position]:
        return [pos for pos in self.positions if pos.strategy == strategy]

    def has_position(self, strategy: str, symbol: str) -> bool:
        return any(pos.strategy == strategy and pos.symbol == symbol for pos in self.positions)

    def mark_to_market(self, rows_by_symbol: dict[str, pd.Series]) -> tuple[float, dict[str, float]]:
        unrealized = {strategy: 0.0 for strategy in self.realized_pnl_by_strategy}
        market_value = 0.0
        for pos in self.positions:
            row = rows_by_symbol.get(pos.symbol)
            if row is None or pd.isna(row.get("close")):
                price = pos.entry_price
            else:
                price = float(row["close"])
            market_value += pos.shares * price
            unrealized[pos.strategy] = unrealized.get(pos.strategy, 0.0) + (price - pos.entry_price) * pos.shares
        return self.cash + market_value, unrealized

    def strategy_total_pnl(self, strategy: str, unrealized: dict[str, float]) -> float:
        return self.realized_pnl_by_strategy.get(strategy, 0.0) + unrealized.get(strategy, 0.0)

    def log_skip_signal(
        self,
        date: pd.Timestamp,
        strategy: str,
        symbol: str,
        signal_type: str,
        reason_skipped: str,
        requested_risk: float,
        project_equity: float,
        strategy_pnl: float = 0.0,
        notes: str = "",
        high_water_mark: float | None = None,
        current_drawdown: float | None = None,
        intended_risk_amount: float | None = None,
        strategy_loss_budget_remaining: float | None = None,
        rank_at_signal: float | int | str | None = "",
        regime_at_signal: str = "",
    ) -> None:
        if reason_skipped not in ALLOWED_SKIP_REASONS:
            raise ValueError(f"Unknown skip reason: {reason_skipped}")
        self.skipped_signals.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "strategy": strategy,
                "symbol": symbol,
                "signal_type": signal_type,
                "reason_skipped": reason_skipped,
                "requested_risk": float(requested_risk or 0.0),
                "intended_risk_amount": float(
                    intended_risk_amount if intended_risk_amount is not None else requested_risk or 0.0
                ),
                "total_open_risk": self.current_open_risk(),
                "cluster_open_risk": self.cluster_open_risk(symbol) if symbol else 0.0,
                "strategy_status": self.disabled_strategies.get(strategy, "active"),
                "strategy_pnl": float(strategy_pnl),
                "strategy_loss_budget_remaining": (
                    float(strategy_loss_budget_remaining)
                    if strategy_loss_budget_remaining is not None
                    else self.strategy_loss_budget_remaining(strategy, strategy_pnl)
                ),
                "project_equity": float(project_equity),
                "high_water_mark": float(high_water_mark if high_water_mark is not None else project_equity),
                "current_drawdown": float(
                    current_drawdown
                    if current_drawdown is not None
                    else project_equity - (high_water_mark if high_water_mark is not None else project_equity)
                ),
                "rank_at_signal": rank_at_signal if rank_at_signal is not None else "",
                "regime_at_signal": regime_at_signal,
                "notes": notes,
            }
        )

    def strategy_loss_budget_remaining(self, strategy: str, strategy_pnl: float | None = None) -> float:
        cfg = self.config.get("strategies", {}).get(strategy, {})
        max_loss = float(cfg.get("max_strategy_loss", 0.0))
        pnl = self.realized_pnl_by_strategy.get(strategy, 0.0) if strategy_pnl is None else float(strategy_pnl)
        return max(0.0, max_loss + pnl)

    def _auto_outcome_class(self, pnl: float, exit_reason: str, rule_followed: bool) -> str:
        if exit_reason == "final_mark_to_market":
            return "final_mark_to_market"
        if exit_reason == "data_issue":
            return "data_issue"
        if exit_reason in RISK_LIMIT_EXIT_REASONS:
            return "risk_limit_exit"
        if abs(pnl) < 1e-9:
            return "breakeven"
        if pnl > 0 and rule_followed:
            return "valid_win"
        if pnl < 0 and rule_followed:
            return "valid_loss"
        return "data_issue"

    def close_position(
        self,
        position: Position,
        exit_date: pd.Timestamp,
        exit_price: float,
        exit_reason: str,
        rule_followed: bool = True,
        notes: str = "",
    ) -> dict[str, Any]:
        if position not in self.positions:
            return {}
        self.positions.remove(position)
        self.cash += position.shares * exit_price
        pnl = (exit_price - position.entry_price) * position.shares
        self.realized_pnl_by_strategy[position.strategy] = (
            self.realized_pnl_by_strategy.get(position.strategy, 0.0) + pnl
        )
        r_multiple = pnl / position.risk_amount if position.risk_amount else np.nan
        signal_date = (
            position.entry_signal_date.date().isoformat()
            if position.entry_signal_date is not None
            else ""
        )
        stop_price_initial = float(position.metadata.get("stop_price_initial", position.stop_price))
        stop_distance = position.entry_price - stop_price_initial
        slippage_exit = abs(position.shares * exit_price * self.slippage_pct)
        trade = {
            "trade_id": position.trade_id,
            "strategy": position.strategy,
            "strategy_version": position.metadata.get("strategy_version", "v1_fixed_rules"),
            "symbol": position.symbol,
            "correlation_cluster": self.cluster_for_symbol(position.symbol),
            "signal_date": signal_date,
            "entry_date": position.entry_date.date().isoformat(),
            "entry_signal_date": signal_date,
            "exit_date": pd.Timestamp(exit_date).date().isoformat(),
            "regime_at_signal": position.metadata.get("regime_at_signal", ""),
            "regime_at_entry": position.market_regime_at_entry,
            "spy_close_at_signal": position.metadata.get("spy_close_at_signal", np.nan),
            "spy_200sma_at_signal": position.metadata.get("spy_200sma_at_signal", np.nan),
            "spy_above_200sma_at_signal": position.metadata.get("spy_above_200sma_at_signal", ""),
            "realized_vol_20_at_signal": position.metadata.get("realized_vol_20_at_signal", np.nan),
            "volatility_regime_at_signal": position.metadata.get("volatility_regime_at_signal", ""),
            "entry_rule_name": position.metadata.get("entry_rule_name", ""),
            "entry_reason_code": position.metadata.get("entry_reason_code", ""),
            "entry_reason_text": position.metadata.get("entry_reason_text", ""),
            "signal_values_json": position.metadata.get("signal_values_json", "{}"),
            "project_equity_at_signal": position.metadata.get("project_equity_at_signal", np.nan),
            "project_equity_at_entry": position.metadata.get("project_equity_at_entry", np.nan),
            "high_water_mark_at_entry": position.metadata.get("high_water_mark_at_entry", np.nan),
            "drawdown_at_entry": position.metadata.get("drawdown_at_entry", np.nan),
            "total_open_risk_before_entry": position.metadata.get("total_open_risk_before_entry", np.nan),
            "total_open_risk_after_entry": position.metadata.get("total_open_risk_after_entry", np.nan),
            "cluster_open_risk_before_entry": position.metadata.get("cluster_open_risk_before_entry", np.nan),
            "cluster_open_risk_after_entry": position.metadata.get("cluster_open_risk_after_entry", np.nan),
            "strategy_pnl_before_entry": position.metadata.get("strategy_pnl_before_entry", np.nan),
            "strategy_loss_budget_remaining_before_entry": position.metadata.get(
                "strategy_loss_budget_remaining_before_entry", np.nan
            ),
            "strategy_status_at_entry": position.metadata.get("strategy_status_at_entry", "active"),
            "entry_price": position.entry_price,
            "stop_price_initial": stop_price_initial,
            "stop_price_final": position.stop_price,
            "exit_price": exit_price,
            "stop_price": position.stop_price,
            "target_price": position.target_price if position.target_price is not None else np.nan,
            "shares": position.shares,
            "notional_value": position.shares * position.entry_price,
            "intended_risk_amount": position.requested_risk,
            "actual_risk_amount": position.risk_amount,
            "risk_amount": position.risk_amount,
            "risk_utilization_pct": position.risk_amount / position.requested_risk if position.requested_risk else np.nan,
            "stop_distance": stop_distance,
            "stop_distance_pct": stop_distance / position.entry_price if position.entry_price else np.nan,
            "pnl": pnl,
            "r_multiple": r_multiple,
            "slippage_paid_estimate": position.metadata.get("slippage_paid_estimate_entry", 0.0) + slippage_exit,
            "fees_paid_estimate": 0.0,
            "exit_reason": exit_reason,
            "exit_reason_text": exit_reason.replace("_", " "),
            "stop_hit": exit_reason in {"stop_loss", "stop_loss_gap"},
            "target_hit": exit_reason == "target_hit",
            "same_bar_stop_target": position.metadata.get("same_bar_stop_target", False),
            "gap_through_stop": exit_reason == "stop_loss_gap",
            "final_mark_to_market": exit_reason == "final_mark_to_market",
            "holding_days": int(position.bars_held),
            "market_regime_at_entry": position.market_regime_at_entry,
            "valid_trade": bool(rule_followed),
            "auto_outcome_class": self._auto_outcome_class(pnl, exit_reason, rule_followed),
            "manual_review_class": "",
            "rule_followed": bool(rule_followed),
            "notes": "; ".join(part for part in [position.notes, notes] if part),
        }
        self.closed_trades.append(trade)
        return trade

    def attempt_open_position(
        self,
        signal: Any,
        entry_date: pd.Timestamp,
        entry_price: float,
        stop_price: float,
        target_price: float | None,
        project_equity: float,
        strategy_pnl: float,
        market_regime: str,
        high_water_mark: float | None = None,
        current_drawdown: float | None = None,
    ) -> Position | None:
        strategy_cfg = self.config["strategies"][signal.strategy]
        requested_risk = float(signal.requested_risk)

        if self.project_stopped:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "project_stop_hit",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None
        if signal.strategy in self.disabled_strategies:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "strategy_loss_budget_hit",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None
        if self.has_position(signal.strategy, signal.symbol):
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "duplicate_position",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None
        if len(self.positions_for_strategy(signal.strategy)) >= int(strategy_cfg["max_positions"]):
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "position_limit_exceeded",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None

        target_weight = signal.metadata.get("target_weight")
        if target_weight is not None:
            stop_distance = abs(entry_price - stop_price) if np.isfinite(stop_price) else np.nan
            if not np.isfinite(entry_price) or not np.isfinite(stop_price) or entry_price <= 0:
                shares, actual_risk, reason = 0.0, 0.0, "missing_price_data"
            elif not np.isfinite(stop_distance) or stop_distance < 0.01 or stop_price >= entry_price:
                shares, actual_risk, reason = 0.0, 0.0, "invalid_stop_distance"
            else:
                max_notional = project_equity * float(self.config["project"]["max_position_notional_pct"])
                target_notional = project_equity * min(float(target_weight), float(self.config["project"]["max_position_notional_pct"]))
                notional = max(0.0, min(target_notional, max_notional, self.cash))
                shares = notional / entry_price if entry_price else 0.0
                actual_risk = shares * stop_distance
                reason = None if shares > 0 and actual_risk > 0 else "not_enough_cash_or_notional_cap"
        else:
            shares, actual_risk, reason = calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_price,
                risk_dollars=requested_risk,
                account_equity=project_equity,
                available_cash=self.cash,
                max_notional_pct=float(self.config["project"]["max_position_notional_pct"]),
            )
        if reason:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                reason,
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None

        projected_open_risk = self.current_open_risk() + actual_risk
        if projected_open_risk > float(self.config["project"]["max_open_risk"]) + 1e-9:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "max_open_risk_exceeded",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None

        projected_cluster_risk = self.cluster_open_risk(signal.symbol) + actual_risk
        if projected_cluster_risk > float(self.config["project"]["max_cluster_open_risk"]) + 1e-9:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "correlation_cluster_risk_exceeded",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None

        notional = shares * entry_price
        if notional > self.cash + 1e-9:
            self.log_skip_signal(
                entry_date,
                signal.strategy,
                signal.symbol,
                signal.signal_type,
                "not_enough_cash_or_notional_cap",
                requested_risk,
                project_equity,
                strategy_pnl,
            )
            return None

        total_before = self.current_open_risk()
        cluster_before = self.cluster_open_risk(signal.symbol)
        metadata = dict(signal.metadata)
        metadata.update(
            {
                "project_equity_at_entry": float(project_equity),
                "high_water_mark_at_entry": float(high_water_mark if high_water_mark is not None else project_equity),
                "drawdown_at_entry": float(
                    current_drawdown
                    if current_drawdown is not None
                    else project_equity - (high_water_mark if high_water_mark is not None else project_equity)
                ),
                "total_open_risk_before_entry": total_before,
                "total_open_risk_after_entry": total_before + actual_risk,
                "cluster_open_risk_before_entry": cluster_before,
                "cluster_open_risk_after_entry": cluster_before + actual_risk,
                "strategy_pnl_before_entry": float(strategy_pnl),
                "strategy_loss_budget_remaining_before_entry": self.strategy_loss_budget_remaining(
                    signal.strategy, strategy_pnl
                ),
                "strategy_status_at_entry": self.disabled_strategies.get(signal.strategy, "active"),
                "stop_price_initial": float(stop_price),
                "slippage_paid_estimate_entry": abs(shares * entry_price * self.slippage_pct),
            }
        )

        self.trade_counter += 1
        position = Position(
            trade_id=self.trade_counter,
            strategy=signal.strategy,
            symbol=signal.symbol,
            entry_date=pd.Timestamp(entry_date),
            entry_price=float(entry_price),
            stop_price=float(stop_price),
            target_price=float(target_price) if target_price is not None and np.isfinite(target_price) else None,
            shares=float(shares),
            risk_amount=float(actual_risk),
            requested_risk=requested_risk,
            market_regime_at_entry=market_regime,
            notes=signal.notes,
            highest_close=float(entry_price),
            entry_signal_date=signal.date,
            metadata=metadata,
        )
        self.cash -= notional
        self.positions.append(position)
        return position

    def trades_frame(self) -> pd.DataFrame:
        columns = [
            "trade_id",
            "strategy",
            "strategy_version",
            "symbol",
            "correlation_cluster",
            "signal_date",
            "entry_date",
            "entry_signal_date",
            "exit_date",
            "regime_at_signal",
            "regime_at_entry",
            "spy_close_at_signal",
            "spy_200sma_at_signal",
            "spy_above_200sma_at_signal",
            "realized_vol_20_at_signal",
            "volatility_regime_at_signal",
            "entry_rule_name",
            "entry_reason_code",
            "entry_reason_text",
            "signal_values_json",
            "project_equity_at_signal",
            "project_equity_at_entry",
            "high_water_mark_at_entry",
            "drawdown_at_entry",
            "total_open_risk_before_entry",
            "total_open_risk_after_entry",
            "cluster_open_risk_before_entry",
            "cluster_open_risk_after_entry",
            "strategy_pnl_before_entry",
            "strategy_loss_budget_remaining_before_entry",
            "strategy_status_at_entry",
            "entry_price",
            "stop_price_initial",
            "stop_price_final",
            "exit_price",
            "stop_price",
            "target_price",
            "shares",
            "notional_value",
            "intended_risk_amount",
            "actual_risk_amount",
            "risk_amount",
            "risk_utilization_pct",
            "stop_distance",
            "stop_distance_pct",
            "pnl",
            "r_multiple",
            "slippage_paid_estimate",
            "fees_paid_estimate",
            "exit_reason",
            "exit_reason_text",
            "stop_hit",
            "target_hit",
            "same_bar_stop_target",
            "gap_through_stop",
            "final_mark_to_market",
            "holding_days",
            "market_regime_at_entry",
            "valid_trade",
            "auto_outcome_class",
            "manual_review_class",
            "rule_followed",
            "notes",
        ]
        return pd.DataFrame(self.closed_trades, columns=columns)

    def skipped_frame(self) -> pd.DataFrame:
        columns = [
            "date",
            "strategy",
            "symbol",
            "signal_type",
            "reason_skipped",
            "requested_risk",
            "intended_risk_amount",
            "total_open_risk",
            "cluster_open_risk",
            "strategy_status",
            "strategy_pnl",
            "strategy_loss_budget_remaining",
            "project_equity",
            "high_water_mark",
            "current_drawdown",
            "rank_at_signal",
            "regime_at_signal",
            "notes",
        ]
        return pd.DataFrame(self.skipped_signals, columns=columns)
