from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .indicators import indicators_ready


A = "A_ETF_sector_momentum"
B = "B_ETF_trend_following"
C = "C_swing_trend_pullback"
D = "D_mean_reversion"
E = "E_breakout_vcb"
N1 = "N1_dual_momentum_taa"
N2 = "N2_absolute_trend_taa"
N3 = "N3_dual_momentum_vol_scaled"
N4 = "N4_inverse_vol_defensive_allocation"
EVIDENCE_STRATEGIES = {N1, N2, N3, N4}


@dataclass
class EntrySignal:
    date: pd.Timestamp
    strategy: str
    symbol: str
    requested_risk: float
    signal_type: str = "entry"
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExitSignal:
    date: pd.Timestamp
    strategy: str
    symbol: str
    trade_id: int
    reason: str
    notes: str = ""


class StrategyEngine:
    def __init__(
        self,
        data: dict[str, pd.DataFrame],
        config: dict[str, Any],
        indexed_data: dict[str, pd.DataFrame] | None = None,
        row_cache: dict[tuple[str, pd.Timestamp], pd.Series | None] | None = None,
    ):
        self.config = config
        self.data = indexed_data if indexed_data is not None else {
            symbol: df.sort_values("date").set_index("date", drop=False)
            for symbol, df in data.items()
        }
        self.symbols = list(config["universe"]["symbols"])
        self.a_stopped_symbols: set[str] = set()
        self._row_cache = row_cache if row_cache is not None else {}

    def row(self, symbol: str, date: pd.Timestamp) -> pd.Series | None:
        date = pd.Timestamp(date)
        cache_key = (symbol, date)
        if cache_key in self._row_cache:
            return self._row_cache[cache_key]
        df = self.data.get(symbol)
        if df is None or date not in df.index:
            self._row_cache[cache_key] = None
            return None
        row = df.loc[date]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        self._row_cache[cache_key] = row
        return row

    def previous_row(self, symbol: str, date: pd.Timestamp) -> pd.Series | None:
        df = self.data.get(symbol)
        if df is None:
            return None
        idx = df.index.searchsorted(date)
        if idx <= 0:
            return None
        return df.iloc[idx - 1]

    def risk(self, strategy: str) -> float:
        cfg = self.config["strategies"][strategy]
        if strategy == C and cfg.get("use_promoted_risk", False):
            return float(cfg.get("promoted_risk_per_trade", cfg["risk_per_trade"]))
        return float(cfg["risk_per_trade"])

    def _is_monthly_rebalance(self, date: pd.Timestamp) -> bool:
        spy = self.data.get("SPY")
        if spy is None:
            dates = sorted({idx for df in self.data.values() for idx in df.index})
        else:
            dates = list(spy.index)
        idx = pd.Index(dates).searchsorted(pd.Timestamp(date))
        if idx >= len(dates) - 1:
            return True
        return pd.Timestamp(dates[idx + 1]).month != pd.Timestamp(date).month

    def is_spy_risk_on(self, date: pd.Timestamp) -> bool:
        row = self.row("SPY", date)
        return row is not None and pd.notna(row.get("sma_200")) and row["close"] > row["sma_200"]

    def spy_not_bear(self, date: pd.Timestamp) -> bool:
        row = self.row("SPY", date)
        if row is None:
            return False
        regime = str(row.get("market_regime", "unknown"))
        return not regime.startswith("bear")

    def rank_a(self, date: pd.Timestamp) -> list[tuple[str, float]]:
        ranked: list[tuple[str, float]] = []
        for symbol in self.symbols:
            row = self.row(symbol, date)
            if row is None:
                continue
            if not indicators_ready(row, ["close", "sma_100", "ret_63", "ret_126", "rv_20", "atr_20"]):
                continue
            if row["close"] <= row["sma_100"] or row["rv_20"] <= 0:
                continue
            score = ((0.5 * row["ret_63"]) + (0.5 * row["ret_126"])) / row["rv_20"]
            if np.isfinite(score):
                ranked.append((symbol, float(score)))
        return sorted(ranked, key=lambda item: (-item[1], item[0]))

    def generate_entries(self, date: pd.Timestamp, portfolio: Any, is_weekly_rebalance: bool) -> list[EntrySignal]:
        signals: list[EntrySignal] = []
        for strategy in self.config["strategy_order"]:
            if not self.config["strategies"].get(strategy, {}).get("enabled", False):
                continue
            if strategy == A:
                signals.extend(self._entries_a(date, portfolio, is_weekly_rebalance))
            elif strategy == B:
                signals.extend(self._entries_b(date, portfolio))
            elif strategy == C:
                signals.extend(self._entries_c(date, portfolio))
            elif strategy == E:
                signals.extend(self._entries_e(date, portfolio))
            elif strategy == D:
                signals.extend(self._entries_d(date, portfolio))
            elif strategy == N1:
                signals.extend(self._entries_monthly_targets(date, portfolio, N1))
            elif strategy == N2:
                signals.extend(self._entries_monthly_targets(date, portfolio, N2))
            elif strategy == N3:
                signals.extend(self._entries_monthly_targets(date, portfolio, N3))
            elif strategy == N4:
                signals.extend(self._entries_monthly_targets(date, portfolio, N4))
        return signals

    def generate_exits(self, date: pd.Timestamp, portfolio: Any, is_weekly_rebalance: bool) -> list[ExitSignal]:
        exits: list[ExitSignal] = []
        ranks = self.rank_a(date) if is_weekly_rebalance else []
        rank_lookup = {symbol: idx + 1 for idx, (symbol, _) in enumerate(ranks)}

        for pos in list(portfolio.positions):
            row = self.row(pos.symbol, date)
            if row is None:
                exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "data_issue", "missing row"))
                continue
            if pos.strategy == A:
                if indicators_ready(row, ["close", "sma_100"]) and row["close"] < row["sma_100"]:
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "sma_exit"))
                elif is_weekly_rebalance:
                    threshold = int(self.config["strategies"][A]["rank_exit_threshold"])
                    if rank_lookup.get(pos.symbol, threshold + 1) > threshold:
                        exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "rank_drop_exit"))
            elif pos.strategy == B:
                if indicators_ready(row, ["close", "sma_50", "sma_200"]) and (
                    row["close"] < row["sma_50"] or row["close"] < row["sma_200"]
                ):
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "trend_exit"))
            elif pos.strategy == C:
                max_days = int(self.config["strategies"][C]["max_holding_days"])
                if indicators_ready(row, ["close", "ema_10"]) and row["close"] < row["ema_10"] and row["close"] <= pos.entry_price:
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "ema10_loss_exit"))
                elif pos.bars_held >= max_days:
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "time_exit"))
            elif pos.strategy == D:
                max_days = int(self.config["strategies"][D]["max_holding_days"])
                if indicators_ready(row, ["close", "sma_5", "sma_200", "rsi_2"]) and (
                    row["rsi_2"] > 60 or row["close"] > row["sma_5"] or row["close"] < row["sma_200"]
                ):
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "mean_reversion_exit"))
                elif pos.bars_held >= max_days:
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "time_exit"))
            elif pos.strategy == E:
                breakout_level = pos.metadata.get("breakout_level")
                if breakout_level is not None and row["close"] < breakout_level:
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "failed_breakout_exit"))
            elif pos.strategy in EVIDENCE_STRATEGIES:
                risk_assets = set(self.config["strategies"][pos.strategy].get("risk_assets", []))
                if pos.strategy in {N1, N2, N3} and pos.symbol in risk_assets:
                    if indicators_ready(row, ["close", "sma_200"]) and row["close"] < row["sma_200"]:
                        exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "taa_trend_exit"))
                        continue
                if self._is_monthly_rebalance(date):
                    exits.append(ExitSignal(date, pos.strategy, pos.symbol, pos.trade_id, "monthly_rebalance_exit"))
        return exits

    def mark_a_stopped(self, symbol: str) -> None:
        self.a_stopped_symbols.add(symbol)

    def _entries_a(self, date: pd.Timestamp, portfolio: Any, is_weekly_rebalance: bool) -> list[EntrySignal]:
        if not is_weekly_rebalance:
            return []
        ranked = self.rank_a(date)
        if not self.is_spy_risk_on(date):
            self.a_stopped_symbols.clear()
            return [
                EntrySignal(date, A, "", self.risk(A), notes="SPY risk-on filter failed", metadata={"skip_reason": "no_eligible_symbols"})
            ]
        if not ranked:
            self.a_stopped_symbols.clear()
            return [
                EntrySignal(date, A, "", self.risk(A), notes="No ETF passed momentum eligibility", metadata={"skip_reason": "no_eligible_symbols"})
            ]

        top_n = int(self.config["strategies"][A]["top_n"])
        signals: list[EntrySignal] = []
        for rank_idx, (symbol, score) in enumerate(ranked[:top_n], start=1):
            if symbol in self.a_stopped_symbols:
                continue
            if portfolio.has_position(A, symbol):
                continue
            row = self.row(symbol, date)
            signals.append(
                EntrySignal(
                    date,
                    A,
                    symbol,
                    self.risk(A),
                    notes=f"weekly rank score={score:.4f}",
                    metadata={"atr": float(row["atr_20"]), "score": score, "rank_score": score, "rank_at_signal": rank_idx},
                )
            )
        self.a_stopped_symbols.clear()
        return signals

    def _entries_b(self, date: pd.Timestamp, portfolio: Any) -> list[EntrySignal]:
        if not self.is_spy_risk_on(date):
            return []
        candidates: list[tuple[str, float]] = []
        for symbol in self.symbols:
            if portfolio.has_position(B, symbol):
                continue
            row = self.row(symbol, date)
            if row is None or not indicators_ready(row, ["close", "sma_50", "sma_200", "high_20", "atr_20", "ret_63", "rv_20"]):
                continue
            if row["close"] > row["sma_50"] and row["sma_50"] > row["sma_200"] and row["close"] > row["high_20"]:
                score = row["ret_63"] / row["rv_20"] if row["rv_20"] > 0 else 0.0
                candidates.append((symbol, float(score)))
        candidates.sort(key=lambda item: (-item[1], item[0]))
        return [
            EntrySignal(date, B, symbol, self.risk(B), notes="trend breakout", metadata={"atr": float(self.row(symbol, date)["atr_20"])})
            for symbol, _ in candidates[:5]
        ]

    def _pullback_days_before_signal(self, symbol: str, date: pd.Timestamp) -> int:
        df = self.data.get(symbol)
        if df is None:
            return 0
        idx = df.index.searchsorted(date)
        if idx < 4:
            return 0
        closes = df["close"].iloc[max(0, idx - 9) : idx + 1].to_numpy()
        count = 0
        # Count consecutive declining closes ending on the prior bar.
        for offset in range(len(closes) - 2, 0, -1):
            if closes[offset] < closes[offset - 1]:
                count += 1
            else:
                break
        return count

    def _entries_c(self, date: pd.Timestamp, portfolio: Any) -> list[EntrySignal]:
        cfg = self.config["strategies"][C]
        candidates: list[tuple[str, float, int]] = []
        for symbol in self.symbols:
            if portfolio.has_position(C, symbol):
                continue
            row = self.row(symbol, date)
            prev = self.previous_row(symbol, date)
            if row is None or prev is None:
                continue
            required = ["close", "high", "low", "sma_50", "sma_200", "ema_10", "atr_20", "ret_63"]
            if not indicators_ready(row, required):
                continue
            trend_ok = row["close"] > row["sma_50"] and row["close"] > row["sma_200"] and row["sma_50"] > row["sma_200"]
            pullback_days = self._pullback_days_before_signal(symbol, date)
            trigger = row["close"] > row["ema_10"] or row["close"] > prev["high"]
            if trend_ok and int(cfg["min_pullback_days"]) <= pullback_days <= int(cfg["max_pullback_days"]) and trigger:
                candidates.append((symbol, float(row["ret_63"]), pullback_days))
        candidates.sort(key=lambda item: (-item[1], item[0]))

        signals: list[EntrySignal] = []
        for symbol, _, pullback_days in candidates[:6]:
            df = self.data[symbol]
            idx = df.index.searchsorted(date)
            lookback = df.iloc[max(0, idx - pullback_days) : idx + 1]
            row = self.row(symbol, date)
            signals.append(
                EntrySignal(
                    date,
                    C,
                    symbol,
                    self.risk(C),
                    notes=f"pullback_days={pullback_days}",
                    metadata={
                        "atr": float(row["atr_20"]),
                        "pullback_low": float(lookback["low"].min()),
                        "target_r_multiple": float(cfg["target_r_multiple"]),
                        "pullback_days": pullback_days,
                    },
                )
            )
        return signals

    def _entries_d(self, date: pd.Timestamp, portfolio: Any) -> list[EntrySignal]:
        if not self.spy_not_bear(date):
            return []
        candidates: list[tuple[str, float]] = []
        for symbol in self.symbols:
            if portfolio.has_position(D, symbol):
                continue
            row = self.row(symbol, date)
            required = ["close", "sma_200", "rsi_2", "bb_lower", "atr_20"]
            if row is None or not indicators_ready(row, required):
                continue
            if row["close"] > row["sma_200"] and (row["rsi_2"] < 10 or row["close"] < row["bb_lower"]):
                candidates.append((symbol, float(row["rsi_2"])))
        candidates.sort(key=lambda item: (item[1], item[0]))
        return [
            EntrySignal(date, D, symbol, self.risk(D), notes="mean reversion setup", metadata={"atr": float(self.row(symbol, date)["atr_20"])})
            for symbol, _ in candidates[:5]
        ]

    def _entries_e(self, date: pd.Timestamp, portfolio: Any) -> list[EntrySignal]:
        cfg = self.config["strategies"][E]
        candidates: list[tuple[str, float]] = []
        for symbol in self.symbols:
            if portfolio.has_position(E, symbol):
                continue
            row = self.row(symbol, date)
            required = ["close", "high_20", "volume", "avg_volume_20", "atr_20", "atr_10_percentile", "ret_63"]
            if row is None or not indicators_ready(row, required):
                continue
            contraction_ok = True
            if cfg.get("use_volatility_contraction_filter", True):
                contraction_ok = row["atr_10_percentile"] < float(cfg["atr10_percentile_threshold"])
            if (
                row["close"] > row["high_20"]
                and row["volume"] > float(cfg["volume_multiple"]) * row["avg_volume_20"]
                and contraction_ok
            ):
                candidates.append((symbol, float(row["ret_63"])))
        candidates.sort(key=lambda item: (-item[1], item[0]))

        signals: list[EntrySignal] = []
        for symbol, _ in candidates[:5]:
            row = self.row(symbol, date)
            signals.append(
                EntrySignal(
                    date,
                    E,
                    symbol,
                    self.risk(E),
                    notes="volume-confirmed breakout",
                    metadata={
                        "atr": float(row["atr_20"]),
                        "breakout_level": float(row["high_20"]),
                        "target_r_multiple": float(cfg["target_r_multiple"]),
                    },
                )
            )
        return signals

    def _momentum_score(self, symbol: str, date: pd.Timestamp) -> float:
        row = self.row(symbol, date)
        if row is None or not indicators_ready(row, ["ret_126", "ret_252"]):
            return np.nan
        return float(0.5 * row["ret_126"] + 0.5 * row["ret_252"])

    def _best_defensive_weights(
        self,
        date: pd.Timestamp,
        defensive_assets: list[str],
        weight_to_allocate: float,
        exclude: set[str] | None = None,
        cap: float = 0.5,
    ) -> dict[str, float]:
        exclude = exclude or set()
        candidates: list[tuple[str, float]] = []
        for symbol in defensive_assets:
            if symbol in exclude:
                continue
            row = self.row(symbol, date)
            if row is None or not indicators_ready(row, ["close", "ret_63"]):
                continue
            candidates.append((symbol, float(row["ret_63"])))
        candidates.sort(key=lambda item: (-item[1], item[0]))
        weights: dict[str, float] = {}
        remaining = max(0.0, float(weight_to_allocate))
        for symbol, _ in candidates:
            if remaining <= 1e-9:
                break
            weight = min(cap, remaining)
            weights[symbol] = weights.get(symbol, 0.0) + weight
            remaining -= weight
        return weights

    def _dual_momentum_weights(self, date: pd.Timestamp, strategy: str, vol_scaled: bool = False) -> dict[str, float]:
        cfg = self.config["strategies"][strategy]
        risk_assets = list(cfg["risk_assets"])
        defensive_assets = list(cfg["defensive_assets"])
        max_weight = float(cfg.get("max_asset_weight", 0.5))
        spy = self.row("SPY", date)
        spy_risk_on = spy is not None and indicators_ready(spy, ["close", "sma_200"]) and spy["close"] > spy["sma_200"]
        bil = self.row("BIL", date)
        threshold = float(bil["ret_126"]) if bil is not None and pd.notna(bil.get("ret_126")) else 0.0
        ranked: list[tuple[str, float]] = []
        for symbol in risk_assets:
            row = self.row(symbol, date)
            if row is None or not indicators_ready(row, ["close", "sma_200", "ret_126", "ret_252", "atr_20"]):
                continue
            score = self._momentum_score(symbol, date)
            if not np.isfinite(score):
                continue
            if row["close"] <= row["sma_200"] or score <= threshold:
                continue
            if not spy_risk_on and symbol not in set(cfg.get("risk_off_allowed_assets", [])):
                continue
            ranked.append((symbol, score))
        ranked.sort(key=lambda item: (-item[1], item[0]))
        top_n = int(cfg.get("top_n", 2))
        selected = ranked[:top_n]
        weights: dict[str, float] = {}
        base_slot_weight = min(max_weight, 1.0 / max(1, top_n))
        scale = 1.0
        high_vol = False
        if vol_scaled and spy is not None and indicators_ready(spy, ["rv_20", "spy_rv_20_q75"]):
            high_vol = bool(spy["rv_20"] > spy["spy_rv_20_q75"])
            if high_vol:
                scale = float(cfg.get("high_vol_risk_asset_scale", 0.5))
        for symbol, _ in selected:
            weights[symbol] = min(max_weight, base_slot_weight * scale)
        remaining = max(0.0, 1.0 - sum(weights.values()))
        if remaining > 1e-9:
            weights.update(self._best_defensive_weights(date, defensive_assets, remaining, set(weights), cap=max_weight))
        return {symbol: weight for symbol, weight in weights.items() if weight > 1e-9}

    def _absolute_trend_weights(self, date: pd.Timestamp) -> dict[str, float]:
        cfg = self.config["strategies"][N2]
        assets = list(cfg["assets"])
        defensive_assets = list(cfg["defensive_assets"])
        max_weight = float(cfg.get("max_asset_weight", 0.5))
        spy = self.row("SPY", date)
        risk_on = spy is not None and indicators_ready(spy, ["close", "sma_200"]) and spy["close"] > spy["sma_200"]
        ranked: list[tuple[str, float]] = []
        if risk_on:
            for symbol in assets:
                if symbol == "BIL":
                    continue
                row = self.row(symbol, date)
                if row is None or not indicators_ready(row, ["close", "sma_200", "ret_126", "atr_20"]):
                    continue
                if row["close"] > row["sma_200"] and row["ret_126"] > 0:
                    ranked.append((symbol, float(row["ret_126"])))
            ranked.sort(key=lambda item: (-item[1], item[0]))
            selected = ranked[: int(cfg.get("risk_on_top_n", 3))]
            slot_weight = min(max_weight, 1.0 / max(1, int(cfg.get("risk_on_top_n", 3))))
            weights = {symbol: slot_weight for symbol, _ in selected}
            remaining = max(0.0, 1.0 - sum(weights.values()))
            if remaining > 1e-9:
                weights.update(self._best_defensive_weights(date, defensive_assets, remaining, set(weights), cap=max_weight))
            return weights
        return self._best_defensive_weights(date, defensive_assets, 1.0, set(), cap=max_weight)

    def _inverse_vol_weights(self, date: pd.Timestamp) -> dict[str, float]:
        cfg = self.config["strategies"][N4]
        assets = list(cfg["assets"])
        max_weight = float(cfg.get("max_asset_weight", 0.4))
        inv_vol: list[tuple[str, float]] = []
        for symbol in assets:
            row = self.row(symbol, date)
            if row is None or not indicators_ready(row, ["close", "sma_200", "rv_60", "atr_20"]):
                continue
            if row["close"] > row["sma_200"] and row["rv_60"] > 0:
                inv_vol.append((symbol, 1.0 / float(row["rv_60"])))
        if not inv_vol:
            return {"BIL": 1.0} if self.row("BIL", date) is not None else {}
        total = sum(value for _, value in inv_vol)
        raw = {symbol: value / total for symbol, value in inv_vol}
        weights = {symbol: min(max_weight, weight) for symbol, weight in raw.items()}
        remainder = max(0.0, 1.0 - sum(weights.values()))
        if remainder > 1e-9 and self.row("BIL", date) is not None:
            weights["BIL"] = weights.get("BIL", 0.0) + remainder
        return weights

    def _monthly_target_weights(self, strategy: str, date: pd.Timestamp) -> dict[str, float]:
        if strategy == N1:
            return self._dual_momentum_weights(date, N1, vol_scaled=False)
        if strategy == N2:
            return self._absolute_trend_weights(date)
        if strategy == N3:
            return self._dual_momentum_weights(date, N3, vol_scaled=True)
        if strategy == N4:
            return self._inverse_vol_weights(date)
        return {}

    def _entries_monthly_targets(self, date: pd.Timestamp, portfolio: Any, strategy: str) -> list[EntrySignal]:
        if not self._is_monthly_rebalance(date):
            return []
        targets = self._monthly_target_weights(strategy, date)
        if not targets:
            return [
                EntrySignal(
                    date,
                    strategy,
                    "",
                    self.risk(strategy),
                    notes="No eligible monthly target assets",
                    metadata={"skip_reason": "no_eligible_symbols"},
                )
            ]
        signals: list[EntrySignal] = []
        defensive_assets = set(self.config["strategies"][strategy].get("defensive_assets", [])) | {"BIL", "SHY"}
        for rank_idx, (symbol, weight) in enumerate(sorted(targets.items(), key=lambda item: (-item[1], item[0])), start=1):
            row = self.row(symbol, date)
            if row is None or not indicators_ready(row, ["atr_20", "close"]):
                continue
            signals.append(
                EntrySignal(
                    date,
                    strategy,
                    symbol,
                    self.risk(strategy),
                    notes=f"monthly target weight={weight:.2%}",
                    metadata={
                        "atr": float(row["atr_20"]),
                        "target_weight": float(weight),
                        "rank_at_signal": rank_idx,
                        "rank_score": self._momentum_score(symbol, date),
                        "enable_trailing_stop": symbol not in defensive_assets,
                    },
                )
            )
        return signals

    def compute_entry_stop_target(self, signal: EntrySignal, entry_price: float) -> tuple[float, float | None]:
        atr = float(signal.metadata.get("atr", np.nan))
        if not np.isfinite(atr) or atr <= 0:
            return np.nan, None

        if signal.strategy == A:
            stop = entry_price - float(self.config["strategies"][A]["initial_atr_multiple"]) * atr
            return stop, None
        if signal.strategy == B:
            stop = entry_price - float(self.config["strategies"][B]["initial_atr_multiple"]) * atr
            return stop, None
        if signal.strategy == C:
            stop = min(
                float(signal.metadata["pullback_low"]),
                entry_price - float(self.config["strategies"][C]["initial_atr_multiple"]) * atr,
            )
            risk = entry_price - stop
            return stop, entry_price + float(signal.metadata["target_r_multiple"]) * risk
        if signal.strategy == D:
            stop = entry_price - float(self.config["strategies"][D]["initial_atr_multiple"]) * atr
            return stop, None
        if signal.strategy == E:
            stop = min(
                float(signal.metadata["breakout_level"]),
                entry_price - float(self.config["strategies"][E]["initial_atr_multiple"]) * atr,
            )
            risk = entry_price - stop
            return stop, entry_price + float(signal.metadata["target_r_multiple"]) * risk
        if signal.strategy in EVIDENCE_STRATEGIES:
            cfg = self.config["strategies"][signal.strategy]
            defensive_assets = set(cfg.get("defensive_assets", [])) | {"BIL", "SHY"}
            multiple = float(
                cfg.get("defensive_atr_multiple", cfg.get("initial_atr_multiple", 3.0))
                if signal.symbol in defensive_assets
                else cfg.get("initial_atr_multiple", 2.5)
            )
            stop = entry_price - multiple * atr
            return stop, None
        return np.nan, None

    def update_trailing_stops(self, date: pd.Timestamp, portfolio: Any) -> None:
        for pos in portfolio.positions:
            row = self.row(pos.symbol, date)
            if row is None or not indicators_ready(row, ["close", "atr_20"]):
                continue
            pos.highest_close = max(pos.highest_close, float(row["close"]))
            if pos.strategy == A:
                trail = pos.highest_close - float(self.config["strategies"][A]["trailing_atr_multiple"]) * float(row["atr_20"])
                pos.stop_price = max(pos.stop_price, trail)
            elif pos.strategy == B:
                trail = pos.highest_close - float(self.config["strategies"][B]["trailing_atr_multiple"]) * float(row["atr_20"])
                pos.stop_price = max(pos.stop_price, trail)
            elif pos.strategy == E:
                trail = pos.highest_close - float(self.config["strategies"][E]["trailing_atr_multiple"]) * float(row["atr_20"])
                pos.stop_price = max(pos.stop_price, trail)
            elif pos.strategy in EVIDENCE_STRATEGIES and pos.metadata.get("enable_trailing_stop", True):
                cfg = self.config["strategies"][pos.strategy]
                multiple = float(cfg.get("trailing_atr_multiple", cfg.get("initial_atr_multiple", 2.5)))
                trail = pos.highest_close - multiple * float(row["atr_20"])
                pos.stop_price = max(pos.stop_price, trail)
