from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from .portfolio import Portfolio, Position
from .strategies import EntrySignal, ExitSignal


TRADING_DAYS = 252


class OverlayDataError(RuntimeError):
    """Raised when an overlay cannot act without inventing unavailable data."""


class DecisionPhase(str, Enum):
    PRE_RUN = "pre_run"
    SIGNAL_BATCH = "signal_batch"
    ORDER_FILTER = "order_filter"
    TARGET_TRANSFORM = "target_transform"
    POSITION_LIFECYCLE = "position_lifecycle"
    STOP_CHECK = "stop_check"
    POST_FILL = "post_fill"


class DecisionType(str, Enum):
    PASS_THROUGH = "pass_through"
    SUPPRESS_ORDER = "suppress_order"
    RESIZE_TARGET = "resize_target"
    EXIT_POSITION = "exit_position"
    RECORD_FILL = "record_fill"
    FAIL_FAST = "fail_fast"
    NO_OP = "no_op"


class ReasonCode(str, Enum):
    IDENTITY_PASS = "identity_pass"
    NO_OVERLAY = "no_overlay"
    OVERLAY_INITIALIZED = "overlay_initialized"
    BELOW_WEIGHT_BAND = "below_weight_band"
    BELOW_NAV_ORDER = "below_nav_order"
    LAGGED_VOL_SCALE = "lagged_vol_scale"
    STATIC_SCALE = "static_scale"
    EXPOSURE_CAP = "exposure_cap"
    GROSS_EXPOSURE_CAP = "gross_exposure_cap"
    ASSET_EXPOSURE_CAP = "asset_exposure_cap"
    GROUP_EXPOSURE_CAP = "group_exposure_cap"
    ATR_STOP_NORMAL_TOUCH = "atr_stop_normal_touch"
    ATR_STOP_GAP_THROUGH = "atr_stop_gap_through"
    ATR_STOP_ARMED = "atr_stop_armed"
    TIME_STOP = "time_stop"
    MISSING_REQUIRED_DATA = "missing_required_data"
    UNSUPPORTED_INTENT_UNIT = "unsupported_intent_unit"
    BASE_STOP_PRECEDENCE = "base_stop_precedence"
    CPPI_RESIZE = "cppi_resize"
    CPPI_SAFE_ACCOUNT_ACCRUAL = "cppi_safe_account_accrual"
    CPPI_SAFE_ACCOUNT_TRANSFER = "cppi_safe_account_transfer"
    CPPI_SAFE_ASSET_REDIRECT = "cppi_safe_asset_redirect"
    CPPI_CASH_LOCK = "cppi_cash_lock"
    CPPI_GAP_BREACH = "cppi_gap_breach"
    CPPI_INTRAPERIOD_FLOOR_SHORTFALL = "cppi_intraperiod_floor_shortfall"
    CPPI_SCHEDULED_FLOOR_BREACH = "cppi_scheduled_floor_breach"
    CPPI_MISSING_REQUIRED_METADATA = "cppi_missing_required_metadata"
    CPPI_NAV_RECONCILIATION_ERROR = "cppi_nav_reconciliation_error"
    INVALID_INSUFFICIENT_CALIBRATION_HISTORY = "INVALID_INSUFFICIENT_CALIBRATION_HISTORY"
    INVALID_DEGENERATE_VOLATILITY_CALIBRATION = "INVALID_DEGENERATE_VOLATILITY_CALIBRATION"
    INVALID_NONFINITE_VOLATILITY_TARGET = "INVALID_NONFINITE_VOLATILITY_TARGET"
    INVALID_NON_DYNAMIC_VOLATILITY_SCALER = "INVALID_NON_DYNAMIC_VOLATILITY_SCALER"


class TargetUnit(str, Enum):
    TARGET_WEIGHT = "target_weight"
    RISK_AMOUNT_DOLLARS = "risk_amount_dollars"
    POSITION_LIFECYCLE = "position_lifecycle"


@dataclass
class ManagedIntentBatch:
    entries: list[EntrySignal]
    exits: list[ExitSignal]


@dataclass(frozen=True)
class StopFillResult:
    fill_price: float
    reason_code: ReasonCode
    exit_reason: str
    trigger_level: float
    gap_through_stop: bool


def stable_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def signal_id(signal: EntrySignal | ExitSignal) -> str:
    if isinstance(signal, EntrySignal):
        rank = signal.metadata.get("rank_at_signal", "")
        return f"{signal.strategy}:{signal.symbol}:{pd.Timestamp(signal.date).date().isoformat()}:{signal.signal_type}:{rank}"
    return f"{signal.strategy}:{signal.symbol}:{pd.Timestamp(signal.date).date().isoformat()}:exit:{signal.trade_id}"


def clone_entry_signal(
    signal: EntrySignal,
    *,
    requested_risk: float | None = None,
    metadata_updates: dict[str, Any] | None = None,
    notes: str | None = None,
) -> EntrySignal:
    metadata = copy.deepcopy(signal.metadata)
    if metadata_updates:
        metadata.update(metadata_updates)
    return EntrySignal(
        date=signal.date,
        strategy=signal.strategy,
        symbol=signal.symbol,
        requested_risk=float(signal.requested_risk if requested_risk is None else requested_risk),
        signal_type=signal.signal_type,
        notes=signal.notes if notes is None else notes,
        metadata=metadata,
    )


def position_state(position: Position | None) -> dict[str, Any]:
    if position is None:
        return {}
    return {
        "trade_id": position.trade_id,
        "strategy": position.strategy,
        "symbol": position.symbol,
        "entry_date": position.entry_date.date().isoformat(),
        "entry_price": position.entry_price,
        "stop_price": position.stop_price,
        "target_price": position.target_price,
        "shares": position.shares,
        "risk_amount": position.risk_amount,
        "bars_held": position.bars_held,
        "highest_close": position.highest_close,
        "stop_price_initial": position.metadata.get("stop_price_initial", position.stop_price),
        "enable_trailing_stop": position.metadata.get("enable_trailing_stop", False),
        "overlay_state": position.metadata.get("trade_management_overlay", {}),
    }


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _target_weight(signal: EntrySignal) -> float | None:
    value = signal.metadata.get("target_weight")
    if value is None or pd.isna(value):
        return None
    return float(value)


def target_unit_for_signal(signal: EntrySignal | ExitSignal | None) -> TargetUnit:
    if signal is None:
        return TargetUnit.POSITION_LIFECYCLE
    if isinstance(signal, ExitSignal):
        return TargetUnit.POSITION_LIFECYCLE
    explicit = signal.metadata.get("target_unit") or signal.metadata.get("intent_kind")
    if explicit:
        try:
            return TargetUnit(str(explicit))
        except ValueError:
            return TargetUnit.RISK_AMOUNT_DOLLARS
    if _target_weight(signal) is not None:
        return TargetUnit.TARGET_WEIGHT
    return TargetUnit.RISK_AMOUNT_DOLLARS


def coerce_target_unit(value: TargetUnit | str) -> TargetUnit:
    if isinstance(value, TargetUnit):
        return value
    return TargetUnit(str(value))


def base_target_for_signal(signal: EntrySignal) -> float:
    target = _target_weight(signal)
    return float(target) if target is not None else float(signal.requested_risk)


def current_position_weights(portfolio: Portfolio, rows: dict[str, pd.Series], nav: float) -> dict[str, float]:
    weights: dict[str, float] = {}
    if nav <= 0:
        return weights
    for pos in portfolio.positions:
        row = rows.get(pos.symbol)
        price = pos.entry_price if row is None or pd.isna(row.get("close")) else float(row["close"])
        weights[pos.symbol] = weights.get(pos.symbol, 0.0) + (pos.shares * price / nav)
    return weights


PAIRED_REBALANCE_EXIT_REASON = "monthly_rebalance_exit"
MIN_NOTIONAL_RESIDUAL_LIQUIDATION_POLICY = (
    "suppress_only_nonmandatory_monthly_rebalance_residual_below_min_notional"
)


def _positions_by_trade_id(portfolio: Portfolio) -> dict[int, Position]:
    return {pos.trade_id: pos for pos in portfolio.positions}


def _monthly_rebalance_exit_symbols(
    exits: list[ExitSignal],
    positions_by_trade: dict[int, Position],
) -> set[str]:
    symbols: set[str] = set()
    for exit_signal in exits:
        if exit_signal.reason != PAIRED_REBALANCE_EXIT_REASON:
            continue
        pos = positions_by_trade.get(exit_signal.trade_id)
        if pos is not None:
            symbols.add(pos.symbol)
    return symbols


class TradeManagementOverlay:
    overlay_id = "NO_OVERLAY"
    version = "v1"
    supported_target_units: set[TargetUnit] = {
        TargetUnit.TARGET_WEIGHT,
        TargetUnit.RISK_AMOUNT_DOLLARS,
        TargetUnit.POSITION_LIFECYCLE,
    }

    def __init__(self, **config: Any):
        self.config = dict(config)
        self.config_hash = stable_hash(self.config)
        self.run_id = ""
        self.base_strategy_id = ""
        self.base_strategy_hash = ""
        self._events: list[dict[str, Any]] = []
        self._event_counter = 0
        self.data: dict[str, pd.DataFrame] = {}
        self.indexed_data: dict[str, pd.DataFrame] = {}
        self.calendar: list[pd.Timestamp] = []
        self._unsupported_intent_counts: dict[str, int] = {}

    def bind(
        self,
        *,
        run_id: str,
        base_strategy_id: str,
        base_strategy_hash: str,
        data: dict[str, pd.DataFrame],
        indexed_data: dict[str, pd.DataFrame],
        calendar: list[pd.Timestamp],
        config: dict[str, Any],
    ) -> None:
        self.run_id = run_id
        self.base_strategy_id = base_strategy_id
        self.base_strategy_hash = base_strategy_hash
        self.data = data
        self.indexed_data = indexed_data
        self.calendar = list(calendar)
        self.on_start(config)

    def on_start(self, config: dict[str, Any]) -> None:
        self.record_event(
            timestamp=pd.NaT,
            phase=DecisionPhase.PRE_RUN,
            decision_type=DecisionType.PASS_THROUGH,
            reason_code=ReasonCode.OVERLAY_INITIALIZED,
        )

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        return ManagedIntentBatch(entries=entries, exits=exits)

    def process_position_lifecycle(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        return None

    def on_before_order_fills(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None = None,
        pending_exits: list[Any] | None = None,
        slippage_pct: float = 0.0,
    ) -> None:
        return None

    def on_end_of_day(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        return None

    def on_after_entry_fill(
        self,
        *,
        date: pd.Timestamp,
        signal: EntrySignal,
        position: Position | None,
        proposed_order: dict[str, Any],
        actual_fill: dict[str, Any] | None,
        modeled_cost: float,
    ) -> None:
        return None

    def on_after_exit_fill(
        self,
        *,
        date: pd.Timestamp,
        signal: ExitSignal | None,
        trade: dict[str, Any],
        proposed_order: dict[str, Any],
        actual_fill: dict[str, Any] | None,
        modeled_cost: float,
    ) -> None:
        return None

    def record_event(
        self,
        *,
        timestamp: pd.Timestamp | pd.NaT,
        phase: DecisionPhase,
        decision_type: DecisionType,
        reason_code: ReasonCode,
        signal: EntrySignal | ExitSignal | None = None,
        trade_id: int | str | None = "",
        asset: str = "",
        base_target: float | None = np.nan,
        managed_target: float | None = np.nan,
        current_position: dict[str, Any] | None = None,
        trigger_level: float | None = np.nan,
        proposed_order: dict[str, Any] | None = None,
        actual_fill: dict[str, Any] | None = None,
        modeled_cost: float | None = np.nan,
        state_before: dict[str, Any] | None = None,
        state_after: dict[str, Any] | None = None,
        data_quality_flags: dict[str, Any] | None = None,
        target_unit: TargetUnit | str | None = None,
    ) -> None:
        self._event_counter += 1
        event_signal_id = signal_id(signal) if signal is not None else ""
        event_trade_id = trade_id if trade_id not in (None, "") else getattr(signal, "trade_id", "")
        event_asset = asset or getattr(signal, "symbol", "")
        unit = target_unit_for_signal(signal) if target_unit is None else coerce_target_unit(target_unit)
        if pd.isna(timestamp):
            timestamp_text = ""
        else:
            timestamp_text = pd.Timestamp(timestamp).isoformat()
        self._events.append(
            {
                "event_id": f"{self.run_id}:{self.overlay_id}:{self._event_counter:08d}",
                "run_id": self.run_id,
                "base_strategy_id": self.base_strategy_id,
                "base_strategy_hash": self.base_strategy_hash,
                "overlay_id": self.overlay_id,
                "overlay_version": self.version,
                "overlay_config_hash": self.config_hash,
                "signal_id": event_signal_id,
                "trade_id": event_trade_id,
                "asset": event_asset,
                "timestamp": timestamp_text,
                "decision_phase": phase.value,
                "decision_type": decision_type.value,
                "reason_code": reason_code.value,
                "intent_kind": unit.value,
                "target_unit": unit.value,
                "supported_target_units": ",".join(sorted(unit.value for unit in self.supported_target_units)),
                "base_target": base_target,
                "managed_target": managed_target,
                "current_position": _json(current_position or {}),
                "trigger_level": trigger_level,
                "proposed_order": _json(proposed_order or {}),
                "actual_fill": _json(actual_fill or {}),
                "modeled_cost": modeled_cost,
                "state_before": _json(state_before or {}),
                "state_after": _json(state_after or {}),
                "data_quality_flags": _json(data_quality_flags or {}),
            }
        )

    def record_unsupported_intent_unit_once(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        phase: DecisionPhase,
    ) -> None:
        unit_counts: dict[str, int] = {}
        for entry in entries:
            unit = target_unit_for_signal(entry)
            unit_counts[unit.value] = unit_counts.get(unit.value, 0) + 1
        for unit_value, batch_count in sorted(unit_counts.items()):
            cumulative = self._unsupported_intent_counts.get(unit_value, 0) + batch_count
            previously_reported = self._unsupported_intent_counts.get(unit_value, 0) > 0
            self._unsupported_intent_counts[unit_value] = cumulative
            if previously_reported:
                continue
            representative = next(entry for entry in entries if target_unit_for_signal(entry).value == unit_value)
            target_unit = target_unit_for_signal(representative)
            self.record_event(
                timestamp=date,
                phase=phase,
                decision_type=DecisionType.NO_OP,
                reason_code=ReasonCode.UNSUPPORTED_INTENT_UNIT,
                signal=representative,
                asset=representative.symbol,
                base_target=base_target_for_signal(representative),
                managed_target=base_target_for_signal(representative),
                target_unit=target_unit,
                data_quality_flags={
                    "trial_level_applicability_event": True,
                    "first_batch_unsupported_entry_count": batch_count,
                    "cumulative_unsupported_entry_count_at_event": cumulative,
                    "supported_target_units": [
                        unit.value for unit in sorted(self.supported_target_units, key=lambda item: item.value)
                    ],
                },
            )

    def events_frame(self) -> pd.DataFrame:
        columns = [
            "event_id",
            "run_id",
            "base_strategy_id",
            "base_strategy_hash",
            "overlay_id",
            "overlay_version",
            "overlay_config_hash",
            "signal_id",
            "trade_id",
            "asset",
            "timestamp",
            "decision_phase",
            "decision_type",
            "reason_code",
            "intent_kind",
            "target_unit",
            "supported_target_units",
            "base_target",
            "managed_target",
            "current_position",
            "trigger_level",
            "proposed_order",
            "actual_fill",
            "modeled_cost",
            "state_before",
            "state_after",
            "data_quality_flags",
        ]
        return pd.DataFrame(self._events, columns=columns)


class NoOverlay(TradeManagementOverlay):
    overlay_id = "NO_OVERLAY"

    def on_start(self, config: dict[str, Any]) -> None:
        return None


class IdentityOverlay(TradeManagementOverlay):
    overlay_id = "IDENTITY"

    def on_start(self, config: dict[str, Any]) -> None:
        self.record_event(
            timestamp=pd.NaT,
            phase=DecisionPhase.PRE_RUN,
            decision_type=DecisionType.PASS_THROUGH,
            reason_code=ReasonCode.IDENTITY_PASS,
        )

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        for exit_signal in exits:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.SIGNAL_BATCH,
                decision_type=DecisionType.PASS_THROUGH,
                reason_code=ReasonCode.IDENTITY_PASS,
                signal=exit_signal,
                trade_id=exit_signal.trade_id,
                asset=exit_signal.symbol,
            )
        for entry in entries:
            target = _target_weight(entry)
            unit = target_unit_for_signal(entry)
            base_target = target if target is not None else float(entry.requested_risk)
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.SIGNAL_BATCH,
                decision_type=DecisionType.PASS_THROUGH,
                reason_code=ReasonCode.IDENTITY_PASS,
                signal=entry,
                asset=entry.symbol,
                base_target=base_target,
                managed_target=base_target,
                target_unit=unit,
            )
        return ManagedIntentBatch(entries=entries, exits=exits)


class WeightChangeBandOverlay(TradeManagementOverlay):
    overlay_id = "OVL-ORD-WEIGHT-BAND-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, min_weight_delta: float = 0.01):
        super().__init__(min_weight_delta=min_weight_delta)
        self.min_weight_delta = float(min_weight_delta)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            if entries:
                self.record_unsupported_intent_unit_once(
                    date=date,
                    entries=entries,
                    phase=DecisionPhase.ORDER_FILTER,
                )
            return ManagedIntentBatch(entries=entries, exits=exits)

        current_weights = current_position_weights(portfolio, rows, equity)
        target_by_symbol = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        positions_by_trade = _positions_by_trade_id(portfolio)
        paired_rebalance_symbols = _monthly_rebalance_exit_symbols(exits, positions_by_trade)
        suppressed_symbols: set[str] = set()
        managed_entries: list[EntrySignal] = []

        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            if entry.symbol not in paired_rebalance_symbols:
                managed_entries.append(entry)
                continue
            current = current_weights.get(entry.symbol, 0.0)
            delta = abs(float(target) - current)
            if delta < self.min_weight_delta:
                suppressed_symbols.add(entry.symbol)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.ORDER_FILTER,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.BELOW_WEIGHT_BAND,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=target,
                    managed_target=current,
                    current_position={"weight": current},
                    proposed_order={
                        "target_weight_delta": delta,
                        "notional_delta": delta * equity,
                        "side": "entry_or_resize",
                    },
                    data_quality_flags={
                        "below_weight_band": True,
                        "min_notional_filter_applied": False,
                        "requires_paired_monthly_rebalance_exit": True,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_entries.append(entry)

        managed_exits: list[ExitSignal] = []
        for exit_signal in exits:
            pos = positions_by_trade.get(exit_signal.trade_id)
            suppress = (
                pos is not None
                and pos.symbol in suppressed_symbols
                and pos.symbol in target_by_symbol
                and exit_signal.reason == PAIRED_REBALANCE_EXIT_REASON
            )
            if suppress:
                current = current_weights.get(pos.symbol, 0.0)
                target = target_by_symbol.get(pos.symbol, 0.0)
                delta = abs(target - current)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.ORDER_FILTER,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.BELOW_WEIGHT_BAND,
                    signal=exit_signal,
                    trade_id=exit_signal.trade_id,
                    asset=pos.symbol,
                    base_target=target,
                    managed_target=current,
                    current_position=position_state(pos),
                    proposed_order={
                        "target_weight_delta": delta,
                        "notional_delta": delta * equity,
                        "side": "exit",
                        "base_exit_reason": exit_signal.reason,
                    },
                    data_quality_flags={
                        "paired_entry_suppressed": True,
                        "same_asset_replacement_target": True,
                        "base_exit_reason": exit_signal.reason,
                        "mandatory_liquidation_preserved": False,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_exits.append(exit_signal)
        return ManagedIntentBatch(entries=managed_entries, exits=managed_exits)


class MinimumNotionalOverlay(TradeManagementOverlay):
    overlay_id = "OVL-ORD-MIN-NOTIONAL-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, min_nav_order_pct: float = 0.001):
        super().__init__(min_nav_order_pct=min_nav_order_pct)
        self.min_nav_order_pct = float(min_nav_order_pct)

    def _threshold(self, equity: float) -> float:
        return max(0.0, float(equity) * self.min_nav_order_pct)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        threshold = self._threshold(equity)
        current_weights = current_position_weights(portfolio, rows, equity)
        if not target_entries:
            if entries:
                self.record_unsupported_intent_unit_once(
                    date=date,
                    entries=entries,
                    phase=DecisionPhase.ORDER_FILTER,
                )
            managed_entries = list(entries)
            target_by_symbol: dict[str, float] = {}
            suppressed_symbols: set[str] = set()
        else:
            target_by_symbol = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
            suppressed_symbols = set()
            managed_entries = []

            for entry in entries:
                target = _target_weight(entry)
                if target is None:
                    managed_entries.append(entry)
                    continue
                current = current_weights.get(entry.symbol, 0.0)
                notional_delta = abs(float(target) - current) * equity
                if notional_delta < threshold:
                    suppressed_symbols.add(entry.symbol)
                    self.record_event(
                        timestamp=date,
                        phase=DecisionPhase.ORDER_FILTER,
                        decision_type=DecisionType.SUPPRESS_ORDER,
                        reason_code=ReasonCode.BELOW_NAV_ORDER,
                        signal=entry,
                        asset=entry.symbol,
                        base_target=target,
                        managed_target=current,
                        current_position={"weight": current},
                        proposed_order={
                            "notional_delta": notional_delta,
                            "min_notional_threshold": threshold,
                            "side": "entry_or_resize",
                        },
                        data_quality_flags={
                            "below_nav_order": True,
                            "target_weight_band_applied": False,
                        },
                        target_unit=TargetUnit.TARGET_WEIGHT,
                    )
                    continue
                managed_entries.append(entry)

        managed_exits: list[ExitSignal] = []
        positions_by_trade = _positions_by_trade_id(portfolio)
        for exit_signal in exits:
            pos = positions_by_trade.get(exit_signal.trade_id)
            if pos is None or exit_signal.reason != PAIRED_REBALANCE_EXIT_REASON:
                managed_exits.append(exit_signal)
                continue
            row = rows.get(pos.symbol)
            price = pos.entry_price if row is None or pd.isna(row.get("close")) else float(row["close"])
            liquidation_notional = abs(float(pos.shares) * price)
            paired_entry_suppressed = pos.symbol in suppressed_symbols and pos.symbol in target_by_symbol
            small_residual_liquidation = liquidation_notional < threshold
            if paired_entry_suppressed or small_residual_liquidation:
                current = current_weights.get(pos.symbol, 0.0)
                target = target_by_symbol.get(pos.symbol, 0.0)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.ORDER_FILTER,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.BELOW_NAV_ORDER,
                    signal=exit_signal,
                    trade_id=exit_signal.trade_id,
                    asset=pos.symbol,
                    base_target=target,
                    managed_target=current,
                    current_position=position_state(pos),
                    proposed_order={
                        "liquidation_notional": liquidation_notional,
                        "min_notional_threshold": threshold,
                        "side": "exit",
                        "base_exit_reason": exit_signal.reason,
                    },
                    data_quality_flags={
                        "paired_entry_suppressed": paired_entry_suppressed,
                        "small_residual_liquidation": small_residual_liquidation,
                        "residual_liquidation_policy": MIN_NOTIONAL_RESIDUAL_LIQUIDATION_POLICY,
                        "mandatory_risk_exit_suppressed": False,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_exits.append(exit_signal)
        return ManagedIntentBatch(entries=managed_entries, exits=managed_exits)


class RebalanceBandOverlay(TradeManagementOverlay):
    overlay_id = "OVL-ORD-001"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, min_weight_delta: float = 0.01, min_nav_order_pct: float = 0.001):
        super().__init__(min_weight_delta=min_weight_delta, min_nav_order_pct=min_nav_order_pct)
        self.min_weight_delta = float(min_weight_delta)
        self.min_nav_order_pct = float(min_nav_order_pct)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            self.record_unsupported_intent_unit_once(
                date=date,
                entries=entries,
                phase=DecisionPhase.ORDER_FILTER,
            )
            return ManagedIntentBatch(entries=entries, exits=exits)

        current_weights = current_position_weights(portfolio, rows, equity)
        target_by_symbol = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        suppressed_symbols: set[str] = set()
        managed_entries: list[EntrySignal] = []

        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            current = current_weights.get(entry.symbol, 0.0)
            delta = abs(float(target) - current)
            notional_delta = delta * equity
            below_band = delta < self.min_weight_delta
            below_nav = notional_delta < equity * self.min_nav_order_pct
            if below_band or below_nav:
                reason = ReasonCode.BELOW_WEIGHT_BAND if below_band else ReasonCode.BELOW_NAV_ORDER
                suppressed_symbols.add(entry.symbol)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.ORDER_FILTER,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=reason,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=target,
                    managed_target=current,
                    current_position={"weight": current},
                    proposed_order={"target_weight_delta": delta, "notional_delta": notional_delta},
                    data_quality_flags={
                        "below_weight_band": below_band,
                        "below_nav_order": below_nav,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_entries.append(entry)

        managed_exits: list[ExitSignal] = []
        positions_by_trade = {pos.trade_id: pos for pos in portfolio.positions}
        for exit_signal in exits:
            pos = positions_by_trade.get(exit_signal.trade_id)
            if pos is None:
                managed_exits.append(exit_signal)
                continue
            current = current_weights.get(pos.symbol, 0.0)
            target = target_by_symbol.get(pos.symbol, 0.0)
            delta = abs(target - current)
            notional_delta = delta * equity
            suppress = (
                pos.symbol in suppressed_symbols
                and pos.symbol in target_by_symbol
                and exit_signal.reason == "monthly_rebalance_exit"
            )
            if suppress:
                reason = ReasonCode.BELOW_WEIGHT_BAND
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.ORDER_FILTER,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=reason,
                    signal=exit_signal,
                    trade_id=exit_signal.trade_id,
                    asset=pos.symbol,
                    base_target=target,
                    managed_target=current,
                    current_position=position_state(pos),
                    proposed_order={
                        "target_weight_delta": delta,
                        "notional_delta": notional_delta,
                        "side": "exit",
                        "base_exit_reason": exit_signal.reason,
                    },
                    data_quality_flags={
                        "paired_entry_suppressed": pos.symbol in suppressed_symbols,
                        "same_asset_replacement_target": pos.symbol in target_by_symbol,
                        "base_exit_reason": exit_signal.reason,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_exits.append(exit_signal)
        return ManagedIntentBatch(entries=managed_entries, exits=managed_exits)


class LaggedVolatilityTargetOverlay(TradeManagementOverlay):
    overlay_id = "OVL-SIZ-001"
    supported_target_units = {TargetUnit.TARGET_WEIGHT, TargetUnit.RISK_AMOUNT_DOLLARS}

    def __init__(
        self,
        target_volatility: float,
        lookback: int = 63,
        scale_floor: float = 0.25,
        scale_cap: float = 1.0,
        min_target_volatility: float = 1e-8,
    ):
        super().__init__(
            target_volatility=target_volatility,
            lookback=lookback,
            scale_floor=scale_floor,
            scale_cap=scale_cap,
            min_target_volatility=min_target_volatility,
        )
        self.target_volatility = float(target_volatility)
        self.lookback = int(lookback)
        self.scale_floor = float(scale_floor)
        self.scale_cap = min(1.0, float(scale_cap))
        self.min_target_volatility = float(min_target_volatility)
        if (
            not np.isfinite(self.target_volatility)
            or self.target_volatility <= self.min_target_volatility
        ):
            raise OverlayDataError(
                f"{ReasonCode.INVALID_DEGENERATE_VOLATILITY_CALIBRATION.value}: "
                f"target_volatility={self.target_volatility!r} below tolerance {self.min_target_volatility}"
            )

    @staticmethod
    def calibration_target_from_equity(
        equity_curve: pd.DataFrame,
        *,
        calibration_start: str | None,
        calibration_end: str | None,
        lookback: int = 63,
    ) -> float:
        frame = equity_curve.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        returns = frame["equity"].astype(float).pct_change()
        vol = returns.rolling(window=lookback, min_periods=lookback).std() * np.sqrt(TRADING_DAYS)
        mask = pd.Series(True, index=frame.index)
        if calibration_start:
            mask &= frame["date"] >= pd.Timestamp(calibration_start)
        if calibration_end:
            mask &= frame["date"] <= pd.Timestamp(calibration_end)
        sample = vol.loc[mask].dropna()
        if sample.empty:
            raise OverlayDataError("No calibration volatility observations are available.")
        return float(sample.median())

    def _returns_window(self, symbol: str, date: pd.Timestamp) -> tuple[pd.Series, str]:
        df = self.indexed_data.get(symbol)
        if df is None or "close" not in df:
            raise OverlayDataError(f"{self.overlay_id}: missing close data for {symbol}")
        idx = df.index.searchsorted(pd.Timestamp(date))
        if idx < self.lookback + 1:
            raise OverlayDataError(f"{self.overlay_id}: insufficient lagged history for {symbol} at {date.date()}")
        closes = df["close"].iloc[idx - self.lookback - 1 : idx].astype(float)
        returns = closes.pct_change().dropna()
        if len(returns) != self.lookback or not np.isfinite(returns).all():
            raise OverlayDataError(f"{self.overlay_id}: invalid lagged return window for {symbol} at {date.date()}")
        return returns, pd.Timestamp(df.index[idx - 1]).date().isoformat()

    def _estimate_volatility(self, date: pd.Timestamp, weights: dict[str, float]) -> tuple[float, str]:
        windows: dict[str, pd.Series] = {}
        lookback_ends: set[str] = set()
        for symbol in sorted(weights):
            returns, lookback_end = self._returns_window(symbol, date)
            windows[symbol] = returns.reset_index(drop=True)
            lookback_ends.add(lookback_end)
        frame = pd.DataFrame(windows)
        weight_vector = np.array([weights[col] for col in frame.columns], dtype=float)
        cov = frame.cov().to_numpy(dtype=float)
        variance = float(weight_vector.T @ cov @ weight_vector)
        if not np.isfinite(variance) or variance <= 0:
            raise OverlayDataError(f"{self.overlay_id}: non-positive lagged volatility estimate at {date.date()}")
        return float(np.sqrt(variance) * np.sqrt(TRADING_DAYS)), ",".join(sorted(lookback_ends))

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        actionable = [entry for entry in entries if entry.symbol]
        if not actionable:
            return ManagedIntentBatch(entries=entries, exits=exits)

        target_entries = [entry for entry in actionable if _target_weight(entry) is not None]
        if target_entries:
            weights = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        else:
            weights = {entry.symbol: 1.0 / len(actionable) for entry in actionable}
        estimated_vol, lookback_end = self._estimate_volatility(date, weights)
        raw_scale = self.target_volatility / estimated_vol
        capped_scale = min(self.scale_cap, max(self.scale_floor, raw_scale))

        managed_entries: list[EntrySignal] = []
        gross_before = sum(abs(weight) for weight in weights.values())
        gross_after = gross_before * capped_scale
        for entry in entries:
            target = _target_weight(entry)
            if target is not None:
                managed_target = float(target) * capped_scale
                managed_entries.append(
                    clone_entry_signal(
                        entry,
                        metadata_updates={
                            "target_weight": managed_target,
                            "overlay_base_target_weight": float(target),
                            "overlay_vol_estimate": estimated_vol,
                            "overlay_target_volatility": self.target_volatility,
                            "overlay_raw_scale": raw_scale,
                            "overlay_capped_scale": capped_scale,
                        },
                    )
                )
                base_target = float(target)
            elif entry.symbol:
                managed_entries.append(
                    clone_entry_signal(
                        entry,
                        requested_risk=float(entry.requested_risk) * capped_scale,
                        metadata_updates={
                            "overlay_base_requested_risk": float(entry.requested_risk),
                            "overlay_vol_estimate": estimated_vol,
                            "overlay_target_volatility": self.target_volatility,
                            "overlay_raw_scale": raw_scale,
                            "overlay_capped_scale": capped_scale,
                        },
                    )
                )
                base_target = float(entry.requested_risk)
                managed_target = float(entry.requested_risk) * capped_scale
            else:
                managed_entries.append(entry)
                continue
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.RESIZE_TARGET,
                reason_code=ReasonCode.LAGGED_VOL_SCALE,
                signal=entry,
                asset=entry.symbol,
                base_target=base_target,
                managed_target=managed_target,
                proposed_order={"estimated_volatility": estimated_vol, "target_volatility": self.target_volatility},
                state_before={"gross_exposure": gross_before},
                state_after={"gross_exposure": gross_after},
                data_quality_flags={
                    "lagged_lookback_days": self.lookback,
                    "lookback_end_date": lookback_end,
                    "signal_date": pd.Timestamp(date).date().isoformat(),
                    "raw_scale": raw_scale,
                    "capped_scale": capped_scale,
                },
                target_unit=target_unit_for_signal(entry),
            )
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class StaticScaleOverlay(TradeManagementOverlay):
    overlay_id = "STATIC-LOWER-EXPOSURE-CONTROL"
    supported_target_units = {TargetUnit.TARGET_WEIGHT, TargetUnit.RISK_AMOUNT_DOLLARS}

    def __init__(self, scale: float):
        super().__init__(scale=scale)
        self.scale = min(1.0, max(0.0, float(scale)))

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        managed: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if target is not None:
                managed_target = float(target) * self.scale
                managed.append(
                    clone_entry_signal(
                        entry,
                        metadata_updates={"target_weight": managed_target, "overlay_static_scale": self.scale},
                    )
                )
                base_target = float(target)
            else:
                managed_target = float(entry.requested_risk) * self.scale
                managed.append(
                    clone_entry_signal(
                        entry,
                        requested_risk=managed_target,
                        metadata_updates={"overlay_static_scale": self.scale},
                    )
                )
                base_target = float(entry.requested_risk)
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.RESIZE_TARGET,
                reason_code=ReasonCode.STATIC_SCALE,
                signal=entry,
                asset=entry.symbol,
                base_target=base_target,
                managed_target=managed_target,
                target_unit=target_unit_for_signal(entry),
            )
        return ManagedIntentBatch(entries=managed, exits=exits)


class ExposureCapsOverlay(TradeManagementOverlay):
    overlay_id = "OVL-RSK-001"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(
        self,
        max_gross_exposure: float = 1.0,
        per_asset_cap: float | None = None,
        group_caps: dict[str, float] | None = None,
    ):
        super().__init__(
            max_gross_exposure=max_gross_exposure,
            per_asset_cap=per_asset_cap,
            group_caps=group_caps or {},
        )
        self.max_gross_exposure = float(max_gross_exposure)
        self.per_asset_cap = None if per_asset_cap is None else float(per_asset_cap)
        self.group_caps = dict(group_caps or {})

    def _group_for_symbol(self, portfolio: Portfolio, symbol: str) -> str:
        return portfolio.cluster_for_symbol(symbol)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            self.record_unsupported_intent_unit_once(
                date=date,
                entries=entries,
                phase=DecisionPhase.TARGET_TRANSFORM,
            )
            return ManagedIntentBatch(entries=entries, exits=exits)

        base_targets = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        cap = self.per_asset_cap
        if cap is None and len([w for w in base_targets.values() if abs(w) > 1e-12]) >= 3:
            cap = 0.35

        managed_targets = dict(base_targets)
        if cap is not None:
            managed_targets = {
                symbol: float(np.sign(weight) * min(abs(weight), cap))
                for symbol, weight in managed_targets.items()
            }

        if self.group_caps:
            by_group: dict[str, list[str]] = {}
            for symbol in managed_targets:
                by_group.setdefault(self._group_for_symbol(portfolio, symbol), []).append(symbol)
            for group, symbols in by_group.items():
                group_cap = self.group_caps.get(group)
                if group_cap is None:
                    continue
                group_gross = sum(abs(managed_targets[symbol]) for symbol in symbols)
                if group_gross > group_cap > 0:
                    scale = group_cap / group_gross
                    for symbol in sorted(symbols):
                        managed_targets[symbol] *= scale

        gross_before = sum(abs(weight) for weight in base_targets.values())
        gross_after_caps = sum(abs(weight) for weight in managed_targets.values())
        gross_scale = 1.0
        if gross_after_caps > self.max_gross_exposure > 0:
            gross_scale = self.max_gross_exposure / gross_after_caps
            managed_targets = {symbol: weight * gross_scale for symbol, weight in managed_targets.items()}
        gross_after = sum(abs(weight) for weight in managed_targets.values())
        cash_created = max(0.0, gross_before - gross_after)

        managed_entries: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            managed_target = managed_targets.get(entry.symbol, 0.0)
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "overlay_max_gross_exposure": self.max_gross_exposure,
                        "overlay_per_asset_cap": cap,
                        "overlay_cash_weight_created": cash_created,
                    },
                )
            )
            if not np.isclose(float(target), managed_target):
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.RESIZE_TARGET,
                    reason_code=ReasonCode.EXPOSURE_CAP,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=managed_target,
                    proposed_order={
                        "deterministic_priority": "clip_per_asset_then_group_then_scale_gross_by_symbol",
                        "gross_before": gross_before,
                        "gross_after": gross_after,
                    },
                    state_before={"gross_exposure": gross_before, "cash_weight_created": 0.0},
                    state_after={"gross_exposure": gross_after, "cash_weight_created": cash_created},
                    data_quality_flags={"per_asset_cap_applied": cap is not None, "gross_scale": gross_scale},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class GrossExposureCapOverlay(TradeManagementOverlay):
    overlay_id = "OVL-RISK-GROSS-CAP-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, max_gross_exposure: float = 1.0):
        super().__init__(max_gross_exposure=max_gross_exposure)
        self.max_gross_exposure = float(max_gross_exposure)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            if entries:
                self.record_unsupported_intent_unit_once(
                    date=date,
                    entries=entries,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                )
            return ManagedIntentBatch(entries=entries, exits=exits)

        base_targets = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        gross_before = sum(abs(weight) for weight in base_targets.values())
        gross_scale = 1.0
        managed_targets = dict(base_targets)
        if gross_before > self.max_gross_exposure > 0:
            gross_scale = self.max_gross_exposure / gross_before
            managed_targets = {symbol: weight * gross_scale for symbol, weight in base_targets.items()}
        gross_after = sum(abs(weight) for weight in managed_targets.values())
        cash_created = max(0.0, gross_before - gross_after)

        managed_entries: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            managed_target = managed_targets.get(entry.symbol, 0.0)
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "overlay_max_gross_exposure": self.max_gross_exposure,
                        "overlay_cash_weight_created": cash_created,
                    },
                )
            )
            if not np.isclose(float(target), managed_target):
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.RESIZE_TARGET,
                    reason_code=ReasonCode.GROSS_EXPOSURE_CAP,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=managed_target,
                    proposed_order={
                        "cap_operation": "gross_exposure_scale",
                        "gross_before": gross_before,
                        "gross_after": gross_after,
                    },
                    state_before={"gross_exposure": gross_before, "cash_weight_created": 0.0},
                    state_after={"gross_exposure": gross_after, "cash_weight_created": cash_created},
                    data_quality_flags={"gross_scale": gross_scale},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class AssetExposureCapOverlay(TradeManagementOverlay):
    overlay_id = "OVL-RISK-ASSET-CAP-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, per_asset_cap: float = 0.35):
        super().__init__(per_asset_cap=per_asset_cap)
        self.per_asset_cap = float(per_asset_cap)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            if entries:
                self.record_unsupported_intent_unit_once(
                    date=date,
                    entries=entries,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                )
            return ManagedIntentBatch(entries=entries, exits=exits)

        base_targets = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        managed_targets = {
            symbol: float(np.sign(weight) * min(abs(weight), self.per_asset_cap))
            for symbol, weight in base_targets.items()
        }
        gross_before = sum(abs(weight) for weight in base_targets.values())
        gross_after = sum(abs(weight) for weight in managed_targets.values())
        cash_created = max(0.0, gross_before - gross_after)

        managed_entries: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            managed_target = managed_targets.get(entry.symbol, 0.0)
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "overlay_per_asset_cap": self.per_asset_cap,
                        "overlay_cash_weight_created": cash_created,
                    },
                )
            )
            if not np.isclose(float(target), managed_target):
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.RESIZE_TARGET,
                    reason_code=ReasonCode.ASSET_EXPOSURE_CAP,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=managed_target,
                    proposed_order={
                        "cap_operation": "per_asset_clip",
                        "gross_before": gross_before,
                        "gross_after": gross_after,
                    },
                    state_before={"gross_exposure": gross_before, "cash_weight_created": 0.0},
                    state_after={"gross_exposure": gross_after, "cash_weight_created": cash_created},
                    data_quality_flags={"per_asset_cap": self.per_asset_cap},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class GroupExposureCapOverlay(TradeManagementOverlay):
    overlay_id = "OVL-RISK-GROUP-CAP-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(self, group_caps: dict[str, float] | None = None):
        super().__init__(group_caps=group_caps or {})
        self.group_caps = {group: float(cap) for group, cap in (group_caps or {}).items()}

    def _group_for_symbol(self, portfolio: Portfolio, symbol: str) -> str:
        return portfolio.cluster_for_symbol(symbol)

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        target_entries = [entry for entry in entries if _target_weight(entry) is not None]
        if not target_entries:
            if entries:
                self.record_unsupported_intent_unit_once(
                    date=date,
                    entries=entries,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                )
            return ManagedIntentBatch(entries=entries, exits=exits)

        base_targets = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in target_entries}
        managed_targets = dict(base_targets)
        by_group: dict[str, list[str]] = {}
        for symbol in managed_targets:
            by_group.setdefault(self._group_for_symbol(portfolio, symbol), []).append(symbol)
        group_scales: dict[str, float] = {}
        for group, symbols in by_group.items():
            group_cap = self.group_caps.get(group)
            if group_cap is None:
                continue
            group_gross = sum(abs(managed_targets[symbol]) for symbol in symbols)
            if group_gross > group_cap > 0:
                scale = group_cap / group_gross
                group_scales[group] = scale
                for symbol in sorted(symbols):
                    managed_targets[symbol] *= scale
        gross_before = sum(abs(weight) for weight in base_targets.values())
        gross_after = sum(abs(weight) for weight in managed_targets.values())
        cash_created = max(0.0, gross_before - gross_after)

        managed_entries: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if target is None:
                managed_entries.append(entry)
                continue
            managed_target = managed_targets.get(entry.symbol, 0.0)
            group = self._group_for_symbol(portfolio, entry.symbol)
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "overlay_group_cap": self.group_caps.get(group),
                        "overlay_cash_weight_created": cash_created,
                    },
                )
            )
            if not np.isclose(float(target), managed_target):
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.RESIZE_TARGET,
                    reason_code=ReasonCode.GROUP_EXPOSURE_CAP,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=managed_target,
                    proposed_order={
                        "cap_operation": "group_exposure_scale",
                        "group": group,
                        "group_cap": self.group_caps.get(group),
                        "gross_before": gross_before,
                        "gross_after": gross_after,
                    },
                    state_before={"gross_exposure": gross_before, "cash_weight_created": 0.0},
                    state_after={"gross_exposure": gross_after, "cash_weight_created": cash_created},
                    data_quality_flags={"group_scales": group_scales},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class CPPIOverlay(TradeManagementOverlay):
    overlay_id = "OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1"
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(
        self,
        *,
        risky_assets: set[str] | list[str] | tuple[str, ...],
        safe_assets: set[str] | list[str] | tuple[str, ...],
        horizon_years: float = 5.0,
        guarantee_fraction: float = 1.0,
        risk_free_rate: float = 0.05,
        multiplier: float = 3.0,
        max_risky_exposure: float = 1.0,
        leverage_allowed: bool = False,
        cash_lock_after_floor_breach: bool = True,
        episode_start: str | None = None,
    ):
        risky = sorted(set(risky_assets))
        safe = sorted(set(safe_assets))
        super().__init__(
            horizon_years=horizon_years,
            guarantee_fraction=guarantee_fraction,
            risk_free_rate=risk_free_rate,
            multiplier=multiplier,
            rebalance_frequency="month_end",
            max_risky_exposure=max_risky_exposure,
            leverage_allowed=leverage_allowed,
            cash_lock_after_floor_breach=cash_lock_after_floor_breach,
            risky_assets=risky,
            safe_assets=safe,
            episode_start=episode_start,
        )
        self.risky_assets = set(risky)
        self.safe_assets = set(safe)
        self.horizon_years = float(horizon_years)
        self.guarantee_fraction = float(guarantee_fraction)
        self.risk_free_rate = float(risk_free_rate)
        self.multiplier = float(multiplier)
        self.max_risky_exposure = min(1.0, float(max_risky_exposure))
        self.leverage_allowed = bool(leverage_allowed)
        self.cash_lock_after_floor_breach = bool(cash_lock_after_floor_breach)
        self.explicit_episode_start = pd.Timestamp(episode_start) if episode_start else None
        self.episode_start: pd.Timestamp | None = None
        self.episode_maturity: pd.Timestamp | None = None
        self.initial_value: float | None = None
        self.guarantee_value: float | None = None
        self.cash_locked = False
        self.floor_breached = False
        self.scheduled_floor_breached = False
        self.first_breach_timestamp: str = ""
        self.scheduled_breach_timestamp: str = ""
        self.floor_shortfall_amount = 0.0
        self.current_floor = np.nan
        self.current_cushion = np.nan
        self.raw_risky_exposure = np.nan
        self.capped_risky_exposure = np.nan
        self.risky_fraction = 0.0
        self.pending_safe_sweep_date: pd.Timestamp | None = None
        self.pending_safe_release_date: pd.Timestamp | None = None
        self.last_rebalance_calculation_date: pd.Timestamp | None = None
        self._safe_ledger_started = False

        if not self.risky_assets or not self.safe_assets:
            raise OverlayDataError(f"{self.overlay_id}: explicit risky and safe asset mappings are required.")
        if self.risky_assets & self.safe_assets:
            raise OverlayDataError(f"{self.overlay_id}: risky/safe asset mapping overlaps.")
        if (
            not np.isfinite(self.horizon_years)
            or self.horizon_years <= 0
            or not np.isfinite(self.guarantee_fraction)
            or self.guarantee_fraction <= 0
            or not np.isfinite(self.risk_free_rate)
            or not np.isfinite(self.multiplier)
            or self.multiplier < 0
            or self.max_risky_exposure < 0
        ):
            raise OverlayDataError(f"{self.overlay_id}: invalid CPPI source parameters.")
        if self.leverage_allowed or self.max_risky_exposure > 1.0 + 1e-12:
            raise OverlayDataError(f"{self.overlay_id}: source-exact baseline is unlevered.")

    def on_start(self, config: dict[str, Any]) -> None:
        super().on_start(config)
        if self.calendar:
            self.episode_start = self.explicit_episode_start or pd.Timestamp(self.calendar[0])
            self.episode_maturity = self.episode_start + pd.DateOffset(years=int(round(self.horizon_years)))
            self.initial_value = float(config["project"]["starting_equity"])
            self.guarantee_value = self.initial_value * self.guarantee_fraction
            self.current_floor = self.floor_value(self.episode_start)
            self.record_event(
                timestamp=self.episode_start,
                phase=DecisionPhase.PRE_RUN,
                decision_type=DecisionType.PASS_THROUGH,
                reason_code=ReasonCode.CPPI_RESIZE,
                state_after=self.state_snapshot(self.episode_start, self.initial_value),
                data_quality_flags={"episode_initialized": True, "source_parameterization": "M3_5Y_monthly_unlevered"},
            )

    def _ensure_episode(self, date: pd.Timestamp, portfolio_value: float) -> None:
        if self.episode_start is None:
            self.episode_start = self.explicit_episode_start or pd.Timestamp(date)
            self.episode_maturity = self.episode_start + pd.DateOffset(years=int(round(self.horizon_years)))
        if self.episode_maturity is None:
            raise OverlayDataError(f"{self.overlay_id}: missing episode maturity.")
        if self.initial_value is None:
            if not np.isfinite(portfolio_value) or portfolio_value <= 0:
                raise OverlayDataError(f"{self.overlay_id}: non-finite initial NAV.")
            self.initial_value = float(portfolio_value)
            self.guarantee_value = self.initial_value * self.guarantee_fraction

    def _episode_total_days(self) -> int:
        if self.episode_start is None or self.episode_maturity is None:
            raise OverlayDataError(f"{self.overlay_id}: missing episode dates.")
        return max(1, (self.episode_maturity.normalize() - self.episode_start.normalize()).days)

    def years_remaining(self, date: pd.Timestamp) -> float:
        if self.episode_start is None or self.episode_maturity is None:
            raise OverlayDataError(f"{self.overlay_id}: missing episode dates.")
        current = pd.Timestamp(date).normalize()
        if current <= self.episode_start.normalize():
            return self.horizon_years
        if current >= self.episode_maturity.normalize():
            return 0.0
        remaining_days = (self.episode_maturity.normalize() - current).days
        return float(self.horizon_years * remaining_days / self._episode_total_days())

    def floor_value(self, date: pd.Timestamp) -> float:
        if self.guarantee_value is None:
            raise OverlayDataError(f"{self.overlay_id}: missing guarantee value.")
        return float(self.guarantee_value * np.exp(-self.risk_free_rate * self.years_remaining(date)))

    def cppi_state(self, date: pd.Timestamp, portfolio_value: float) -> dict[str, float | bool | str]:
        if not np.isfinite(portfolio_value) or portfolio_value <= 0:
            raise OverlayDataError(f"{self.overlay_id}: non-finite NAV.")
        self._ensure_episode(date, portfolio_value)
        floor = self.floor_value(date)
        cushion = max(float(portfolio_value) - floor, 0.0)
        raw_risky = self.multiplier * cushion
        capped_risky = min(float(portfolio_value) * self.max_risky_exposure, raw_risky)
        if self.cash_locked:
            capped_risky = 0.0
        risky_fraction = capped_risky / float(portfolio_value) if portfolio_value > 0 else 0.0
        shortfall = max(floor - float(portfolio_value), 0.0)
        return {
            "episode_id": self.overlay_id,
            "episode_start": self.episode_start.date().isoformat() if self.episode_start is not None else "",
            "episode_maturity": self.episode_maturity.date().isoformat() if self.episode_maturity is not None else "",
            "portfolio_value": float(portfolio_value),
            "floor": floor,
            "cushion": cushion,
            "raw_risky_exposure": raw_risky,
            "capped_risky_exposure": capped_risky,
            "risky_fraction": risky_fraction,
            "cash_locked": bool(self.cash_locked),
            "floor_breached": bool(self.floor_breached),
            "floor_shortfall_amount": shortfall,
        }

    def state_snapshot(self, date: pd.Timestamp, portfolio_value: float, portfolio: Portfolio | None = None) -> dict[str, Any]:
        state = self.cppi_state(date, portfolio_value)
        state.update(
            {
                "safe_account_value": portfolio.synthetic_safe_account_value if portfolio is not None else np.nan,
                "first_breach_timestamp": self.first_breach_timestamp,
                "scheduled_floor_breached": self.scheduled_floor_breached,
                "scheduled_breach_timestamp": self.scheduled_breach_timestamp,
                "cash_lock_after_floor_breach": self.cash_lock_after_floor_breach,
            }
        )
        return state

    def _update_state_from_nav(self, date: pd.Timestamp, nav: float, *, activate_cash_lock: bool = False) -> dict[str, Any]:
        state = self.cppi_state(date, nav)
        self.current_floor = float(state["floor"])
        self.current_cushion = float(state["cushion"])
        self.raw_risky_exposure = float(state["raw_risky_exposure"])
        self.capped_risky_exposure = float(state["capped_risky_exposure"])
        self.risky_fraction = float(state["risky_fraction"])
        self.floor_shortfall_amount = max(self.floor_shortfall_amount, float(state["floor_shortfall_amount"]))
        if float(state["floor_shortfall_amount"]) > 0:
            self.floor_breached = True
            if not self.first_breach_timestamp:
                self.first_breach_timestamp = pd.Timestamp(date).date().isoformat()
            if activate_cash_lock:
                self.scheduled_floor_breached = True
                if not self.scheduled_breach_timestamp:
                    self.scheduled_breach_timestamp = pd.Timestamp(date).date().isoformat()
            if activate_cash_lock and self.cash_lock_after_floor_breach:
                self.cash_locked = True
                state = self.cppi_state(date, nav)
        return state

    def _classify_symbol(self, symbol: str) -> str:
        if symbol in self.risky_assets:
            return "risky"
        if symbol in self.safe_assets:
            return "safe"
        raise OverlayDataError(f"{self.overlay_id}: ambiguous risky/safe mapping for {symbol!r}")

    def _is_scheduled_decision(self, date: pd.Timestamp) -> bool:
        current = pd.Timestamp(date)
        if not self.calendar:
            return False
        calendar = [pd.Timestamp(value) for value in self.calendar]
        try:
            idx = calendar.index(current)
        except ValueError:
            return False
        if idx >= len(calendar) - 1:
            return True
        return calendar[idx + 1].month != current.month

    def _next_execution_date(self, date: pd.Timestamp) -> pd.Timestamp:
        next_dates = [pd.Timestamp(value) for value in self.calendar if pd.Timestamp(value) > pd.Timestamp(date)]
        return next_dates[0] if next_dates else pd.Timestamp(date)

    def _record_scheduled_breach_if_needed(
        self,
        *,
        date: pd.Timestamp,
        equity: float,
        portfolio: Portfolio,
        exits: list[ExitSignal],
    ) -> dict[str, Any]:
        state = self._update_state_from_nav(date, equity, activate_cash_lock=False)
        if float(state["floor_shortfall_amount"]) > 0 and self.cash_lock_after_floor_breach:
            state = self._update_state_from_nav(date, equity, activate_cash_lock=True)
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.RESIZE_TARGET,
                reason_code=ReasonCode.CPPI_SCHEDULED_FLOOR_BREACH,
                state_after=self.state_snapshot(date, equity, portfolio),
                data_quality_flags={
                    "scheduled_floor_breach": True,
                    "intraperiod_diagnostic": False,
                    "shortfall_retained": True,
                    "capital_repaired": False,
                    "execute_liquidation_at_next_open": True,
                },
            )
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.FAIL_FAST if not exits else DecisionType.RESIZE_TARGET,
                reason_code=ReasonCode.CPPI_CASH_LOCK,
                state_after=self.state_snapshot(date, equity, portfolio),
                data_quality_flags={"floor_breach": True, "cash_lock": True, "shortfall_retained": True},
            )
        return state

    def _set_next_safe_timing(self, date: pd.Timestamp) -> None:
        next_execution = self._next_execution_date(date)
        self.pending_safe_release_date = next_execution
        self.pending_safe_sweep_date = next_execution

    def _expected_exit_cash(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_exits: list[Any] | None,
        slippage_pct: float,
        portfolio: Portfolio,
    ) -> float:
        cash = 0.0
        for pending in pending_exits or []:
            signal = getattr(pending, "signal", pending)
            trade_id = getattr(signal, "trade_id", None)
            pos = next((item for item in portfolio.positions if item.trade_id == trade_id), None)
            if pos is None:
                continue
            row = rows.get(pos.symbol)
            if row is None or pd.isna(row.get("open")):
                continue
            exit_price = float(row["open"])
            if np.isfinite(slippage_pct) and 0.0 <= slippage_pct < 1.0:
                exit_price *= 1.0 - float(slippage_pct)
            cash += max(0.0, float(pos.shares) * exit_price)
        return cash

    def _expected_entry_funding(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None,
        portfolio: Portfolio,
    ) -> float:
        nav, _ = portfolio.mark_to_market(rows)
        if not np.isfinite(nav) or nav <= 0:
            return 0.0
        max_notional_pct = float(portfolio.config["project"].get("max_position_notional_pct", 1.0))
        projected_counts = {
            strategy: len(portfolio.positions_for_strategy(strategy))
            for strategy in portfolio.config.get("strategies", {})
        }
        funding = 0.0
        for pending in pending_entries or []:
            signal = getattr(pending, "signal", pending)
            symbol = getattr(signal, "symbol", "")
            if not symbol or self._classify_symbol(symbol) != "risky":
                continue
            row = rows.get(symbol)
            if row is None or pd.isna(row.get("open")):
                continue
            if portfolio.project_stopped or signal.strategy in portfolio.disabled_strategies:
                continue
            if portfolio.has_position(signal.strategy, symbol):
                continue
            strategy_cfg = portfolio.config["strategies"][signal.strategy]
            if projected_counts.get(signal.strategy, 0) >= int(strategy_cfg["max_positions"]):
                continue
            target = _target_weight(signal)
            if target is None or target <= 0:
                continue
            target_notional = nav * min(float(target), max_notional_pct)
            funding += max(0.0, target_notional)
            projected_counts[signal.strategy] = projected_counts.get(signal.strategy, 0) + 1
        return funding

    def _required_safe_release(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None,
        pending_exits: list[Any] | None,
        slippage_pct: float,
        portfolio: Portfolio,
    ) -> tuple[float, dict[str, Any]]:
        entry_funding = self._expected_entry_funding(
            rows=rows,
            pending_entries=pending_entries,
            portfolio=portfolio,
        )
        exit_cash = self._expected_exit_cash(
            rows=rows,
            pending_exits=pending_exits,
            slippage_pct=slippage_pct,
            portfolio=portfolio,
        )
        available = max(0.0, float(portfolio.cash)) + exit_cash
        required = max(0.0, entry_funding - available)
        return required, {
            "expected_risky_purchase_funding": entry_funding,
            "expected_exit_cash_before_entries": exit_cash,
            "broker_cash_before_release": float(portfolio.cash),
            "required_safe_release": required,
        }

    def _sweep_broker_cash_to_safe(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        reason: str,
    ) -> None:
        if portfolio.cash < -1e-9 or portfolio.synthetic_safe_account_value < -1e-9:
            raise OverlayDataError(f"{self.overlay_id}: negative safe-account reconciliation.")
        amount = max(0.0, float(portfolio.cash))
        if amount <= 1e-9:
            return
        portfolio.transfer_cash_to_synthetic_safe(amount)
        self.record_event(
            timestamp=date,
            phase=DecisionPhase.POST_FILL,
            decision_type=DecisionType.RECORD_FILL,
            reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_TRANSFER,
            proposed_order={"side": "broker_cash_to_synthetic_safe", "non_orderable": True, "reason": reason},
            actual_fill={"amount": amount, "fill_time": pd.Timestamp(date).isoformat()},
            modeled_cost=0.0,
            state_after={"safe_account_value": portfolio.synthetic_safe_account_value, "broker_cash": portfolio.cash},
        )

    def _accrue_safe_account(self, date: pd.Timestamp, portfolio: Portfolio) -> float:
        opening = float(portfolio.synthetic_safe_account_value)
        previous_date = portfolio.synthetic_safe_account_last_accrual_date
        elapsed_days = (
            max(0, (pd.Timestamp(date).normalize() - previous_date.normalize()).days)
            if previous_date is not None
            else 0
        )
        accrued = portfolio.accrue_synthetic_safe_account(date, self.risk_free_rate)
        if accrued > 1e-9:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.POSITION_LIFECYCLE,
                decision_type=DecisionType.RECORD_FILL,
                reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_ACCRUAL,
                modeled_cost=0.0,
                state_after={
                    "opening_safe_account_value": opening,
                    "safe_account_value": portfolio.synthetic_safe_account_value,
                    "elapsed_calendar_days": elapsed_days,
                    "accrued_amount": accrued,
                    "risk_free_rate": self.risk_free_rate,
                },
            )
        return accrued

    def on_before_order_fills(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None = None,
        pending_exits: list[Any] | None = None,
        slippage_pct: float = 0.0,
    ) -> None:
        self._accrue_safe_account(date, portfolio)
        if (
            self.pending_safe_release_date is not None
            and pd.Timestamp(date) >= self.pending_safe_release_date
            and portfolio.synthetic_safe_account_value > 1e-9
            and not self.cash_locked
        ):
            required, funding_state = self._required_safe_release(
                rows=rows,
                pending_entries=pending_entries,
                pending_exits=pending_exits,
                slippage_pct=slippage_pct,
                portfolio=portfolio,
            )
            amount = min(portfolio.synthetic_safe_account_value, required)
            if amount > 1e-9:
                portfolio.transfer_synthetic_safe_to_cash(amount)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.POST_FILL,
                    decision_type=DecisionType.RECORD_FILL,
                    reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_TRANSFER,
                    proposed_order={
                        "side": "synthetic_safe_to_broker_cash",
                        "non_orderable": True,
                        "reason": "execution_funding",
                        **funding_state,
                    },
                    actual_fill={"amount": amount, "fill_time": pd.Timestamp(date).isoformat()},
                    modeled_cost=0.0,
                    state_after={"safe_account_value": portfolio.synthetic_safe_account_value, "broker_cash": portfolio.cash},
                    data_quality_flags={
                        "required_funding_release": True,
                        "released_without_funding_requirement": required <= 1e-9,
                    },
                )
            self.pending_safe_release_date = None
        elif self.pending_safe_release_date is not None and pd.Timestamp(date) >= self.pending_safe_release_date:
            self.pending_safe_release_date = None

    def process_position_lifecycle(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        self._accrue_safe_account(date, portfolio)
        nav, _ = portfolio.mark_to_market(rows)
        state = self._update_state_from_nav(date, nav, activate_cash_lock=False)
        if float(state["floor_shortfall_amount"]) > 0:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.POSITION_LIFECYCLE,
                decision_type=DecisionType.NO_OP,
                reason_code=ReasonCode.CPPI_INTRAPERIOD_FLOOR_SHORTFALL,
                modeled_cost=0.0,
                state_after=self.state_snapshot(date, nav, portfolio),
                data_quality_flags={
                    "intraperiod_diagnostic": True,
                    "scheduled_floor_breach": False,
                    "trade_triggered": False,
                    "cash_lock_activated": False,
                    "shortfall_retained": True,
                    "capital_repaired": False,
                },
            )
        if self.pending_safe_sweep_date is not None and pd.Timestamp(date) >= self.pending_safe_sweep_date:
            self._sweep_broker_cash_to_safe(
                date=date,
                portfolio=portfolio,
                reason="post_execution_same_day_sweep",
            )
            self.pending_safe_sweep_date = None

    def on_end_of_day(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        self._sweep_broker_cash_to_safe(
            date=date,
            portfolio=portfolio,
            reason="end_of_day_safe_persistence",
        )

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        actionable = [entry for entry in entries if entry.symbol]
        scheduled_decision = self._is_scheduled_decision(date)
        if not actionable and not exits and not scheduled_decision:
            return ManagedIntentBatch(entries=entries, exits=exits)
        if not np.isfinite(equity) or equity <= 0:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.FAIL_FAST,
                reason_code=ReasonCode.CPPI_NAV_RECONCILIATION_ERROR,
                data_quality_flags={"non_finite_nav": True},
            )
            raise OverlayDataError(f"{self.overlay_id}: non-finite NAV.")
        if not actionable:
            self._ensure_episode(date, equity)
            self._record_scheduled_breach_if_needed(date=date, equity=equity, portfolio=portfolio, exits=exits)
            self.last_rebalance_calculation_date = pd.Timestamp(date)
            self._set_next_safe_timing(date)
            self.capped_risky_exposure = 0.0
            self.safe_ledger_target_value = float(equity)
            return ManagedIntentBatch(entries=[], exits=exits)
        if any(_target_weight(entry) is None for entry in actionable):
            self.record_unsupported_intent_unit_once(
                date=date,
                entries=actionable,
                phase=DecisionPhase.TARGET_TRANSFORM,
            )
            raise OverlayDataError(f"{self.overlay_id}: unsupported intent unit; target_weight required.")

        self._ensure_episode(date, equity)
        state = self._record_scheduled_breach_if_needed(date=date, equity=equity, portfolio=portfolio, exits=exits)

        classified: dict[str, str] = {}
        base_targets: dict[str, float] = {}
        for entry in actionable:
            classification = self._classify_symbol(entry.symbol)
            classified[entry.symbol] = classification
            base_targets[entry.symbol] = float(_target_weight(entry) or 0.0)
        base_risky_gross = sum(abs(weight) for symbol, weight in base_targets.items() if classified[symbol] == "risky")
        target_risky_fraction = 0.0 if self.cash_locked else min(float(state["risky_fraction"]), self.max_risky_exposure)
        managed_risky_gross = min(base_risky_gross, target_risky_fraction)
        risky_scale = managed_risky_gross / base_risky_gross if base_risky_gross > 1e-12 else 0.0
        if risky_scale > 1.0 + 1e-12 or managed_risky_gross > base_risky_gross + 1e-12:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.FAIL_FAST,
                reason_code=ReasonCode.CPPI_NAV_RECONCILIATION_ERROR,
                data_quality_flags={"attempted_to_exceed_base_exposure": True},
            )
            raise OverlayDataError(f"{self.overlay_id}: attempted to exceed base exposure.")

        managed_entries: list[EntrySignal] = []
        gross_after = 0.0
        for entry in entries:
            target = _target_weight(entry)
            if not entry.symbol or target is None:
                managed_entries.append(entry)
                continue
            classification = classified[entry.symbol]
            if classification == "safe":
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.CPPI_SAFE_ASSET_REDIRECT,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=0.0,
                    proposed_order={"synthetic_safe_account": True, "base_safe_target_weight": float(target)},
                    state_before={"base_target_weight": float(target)},
                    state_after=self.state_snapshot(date, equity, portfolio),
                    data_quality_flags={"safe_asset_redirected_to_synthetic_ledger": True},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_target = float(target) * risky_scale
            if managed_target <= 1e-12:
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.CPPI_CASH_LOCK if self.cash_locked else ReasonCode.CPPI_RESIZE,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=0.0,
                    proposed_order={
                        "base_risky_gross": base_risky_gross,
                        "managed_risky_gross": managed_risky_gross,
                        "risky_scale": risky_scale,
                        "execute_at_next_open": True,
                    },
                    state_before={"base_target_weight": float(target), "base_risky_gross": base_risky_gross},
                    state_after=self.state_snapshot(date, equity, portfolio),
                    data_quality_flags={
                        "cash_lock": bool(self.cash_locked),
                        "base_exposure_not_increased": True,
                        "risky_entry_suppressed": True,
                    },
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            gross_after += abs(managed_target)
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "cppi_risky_fraction": target_risky_fraction,
                        "cppi_risky_scale": risky_scale,
                        "cppi_floor": float(state["floor"]),
                        "cppi_cushion": float(state["cushion"]),
                        "cppi_cash_locked": bool(self.cash_locked),
                    },
                )
            )
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.RESIZE_TARGET,
                reason_code=ReasonCode.CPPI_RESIZE,
                signal=entry,
                asset=entry.symbol,
                base_target=float(target),
                managed_target=managed_target,
                proposed_order={
                    "base_risky_gross": base_risky_gross,
                    "managed_risky_gross": managed_risky_gross,
                    "risky_scale": risky_scale,
                    "execute_at_next_open": True,
                },
                state_before={"base_target_weight": float(target), "base_risky_gross": base_risky_gross},
                state_after=self.state_snapshot(date, equity, portfolio),
                data_quality_flags={
                    "month_end_information_date": pd.Timestamp(date).date().isoformat(),
                    "same_close_execution": False,
                    "base_exposure_not_increased": managed_target <= float(target) + 1e-12,
                    "leverage_allowed": self.leverage_allowed,
                },
                target_unit=TargetUnit.TARGET_WEIGHT,
            )

        self.last_rebalance_calculation_date = pd.Timestamp(date)
        self._set_next_safe_timing(date)
        self.capped_risky_exposure = managed_risky_gross * float(equity)
        self.safe_ledger_target_value = max(0.0, float(equity) * (1.0 - gross_after))
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


def simulate_atr_stop_exit(
    position: Position,
    row: pd.Series,
    stop_level: float,
    slippage_pct: float,
) -> StopFillResult | None:
    required = ["open", "high", "low", "close"]
    missing = [col for col in required if pd.isna(row.get(col))]
    if missing:
        raise OverlayDataError(f"Missing required OHLC columns for ATR stop: {','.join(missing)}")

    open_price = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    stop = float(stop_level)
    is_short = position.shares < 0
    if is_short:
        if open_price >= stop:
            return StopFillResult(
                fill_price=float(open_price * (1.0 + slippage_pct)),
                reason_code=ReasonCode.ATR_STOP_GAP_THROUGH,
                exit_reason="overlay_atr_stop_gap",
                trigger_level=stop,
                gap_through_stop=True,
            )
        if high >= stop:
            return StopFillResult(
                fill_price=float(stop * (1.0 + slippage_pct)),
                reason_code=ReasonCode.ATR_STOP_NORMAL_TOUCH,
                exit_reason="overlay_atr_stop",
                trigger_level=stop,
                gap_through_stop=False,
            )
        return None

    if open_price <= stop:
        return StopFillResult(
            fill_price=float(open_price * (1.0 - slippage_pct)),
            reason_code=ReasonCode.ATR_STOP_GAP_THROUGH,
            exit_reason="overlay_atr_stop_gap",
            trigger_level=stop,
            gap_through_stop=True,
        )
    if low <= stop:
        return StopFillResult(
            fill_price=float(stop * (1.0 - slippage_pct)),
            reason_code=ReasonCode.ATR_STOP_NORMAL_TOUCH,
            exit_reason="overlay_atr_stop",
            trigger_level=stop,
            gap_through_stop=False,
        )
    return None


class WideATRCatastrophicStopOverlay(TradeManagementOverlay):
    overlay_id = "OVL-STP-001"
    supported_target_units = {TargetUnit.POSITION_LIFECYCLE}

    def __init__(self, atr_lookback: int = 20, atr_multiple: float = 4.0):
        super().__init__(atr_lookback=atr_lookback, atr_multiple=atr_multiple, trailing=False)
        self.atr_lookback = int(atr_lookback)
        self.atr_multiple = float(atr_multiple)

    def on_after_entry_fill(
        self,
        *,
        date: pd.Timestamp,
        signal: EntrySignal,
        position: Position | None,
        proposed_order: dict[str, Any],
        actual_fill: dict[str, Any] | None,
        modeled_cost: float,
    ) -> None:
        if position is None:
            return
        atr_value = signal.metadata.get("atr")
        if atr_value is None or not np.isfinite(float(atr_value)) or float(atr_value) <= 0:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.POST_FILL,
                decision_type=DecisionType.FAIL_FAST,
                reason_code=ReasonCode.MISSING_REQUIRED_DATA,
                signal=signal,
                trade_id=position.trade_id,
                asset=position.symbol,
                actual_fill=actual_fill,
                data_quality_flags={"missing": "atr", "atr_lookback": self.atr_lookback},
            )
            raise OverlayDataError(f"{self.overlay_id}: ATR unavailable for {position.symbol} at entry.")
        entry_atr = float(atr_value)
        stop_level = (
            position.entry_price + self.atr_multiple * entry_atr
            if position.shares < 0
            else position.entry_price - self.atr_multiple * entry_atr
        )
        before = position_state(position)
        overlay_state = dict(position.metadata.get("trade_management_overlay", {}))
        overlay_state[self.overlay_id] = {
            "entry_atr": entry_atr,
            "atr_lookback": self.atr_lookback,
            "atr_multiple": self.atr_multiple,
            "stop_level": stop_level,
            "entry_date": pd.Timestamp(date).date().isoformat(),
            "active_after_bars_held": 1,
            "trailing": False,
        }
        position.metadata["trade_management_overlay"] = overlay_state
        self.record_event(
            timestamp=date,
            phase=DecisionPhase.POST_FILL,
            decision_type=DecisionType.RECORD_FILL,
            reason_code=ReasonCode.ATR_STOP_ARMED,
            signal=signal,
            trade_id=position.trade_id,
            asset=position.symbol,
            trigger_level=stop_level,
            actual_fill=actual_fill,
            modeled_cost=modeled_cost,
            state_before=before,
                state_after=position_state(position),
                data_quality_flags={"entry_atr_fixed": True, "trailing": False},
                target_unit=TargetUnit.POSITION_LIFECYCLE,
            )

    def _base_exit_hit(self, pos: Position, row: pd.Series) -> dict[str, Any]:
        required = ["open", "high", "low", "close"]
        missing = [col for col in required if pd.isna(row.get(col))]
        if missing:
            raise OverlayDataError(f"Missing required OHLC columns for ATR stop: {','.join(missing)}")
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        base_stop = float(pos.stop_price)
        target = pos.target_price
        if pos.shares < 0:
            stop_hit = high >= base_stop
            target_hit = target is not None and low <= float(target)
            gap_stop = open_price >= base_stop
        else:
            stop_hit = low <= base_stop
            target_hit = target is not None and high >= float(target)
            gap_stop = open_price <= base_stop
        return {
            "base_stop_level": base_stop,
            "base_target_level": float(target) if target is not None else np.nan,
            "base_stop_hit": bool(stop_hit),
            "base_target_hit": bool(target_hit),
            "base_gap_stop": bool(gap_stop),
            "bar_open": open_price,
            "bar_high": high,
            "bar_low": low,
            "bar_close": float(row["close"]),
        }

    def process_position_lifecycle(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        for pos in list(portfolio.positions):
            state = pos.metadata.get("trade_management_overlay", {}).get(self.overlay_id)
            if not state:
                continue
            if pos.bars_held < int(state.get("active_after_bars_held", 1)):
                continue
            row = rows.get(pos.symbol)
            if row is None:
                raise OverlayDataError(f"{self.overlay_id}: missing OHLC row for {pos.symbol} on {date.date()}")
            base_state = self._base_exit_hit(pos, row)
            if base_state["base_stop_hit"] or base_state["base_target_hit"]:
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.STOP_CHECK,
                    decision_type=DecisionType.NO_OP,
                    reason_code=ReasonCode.BASE_STOP_PRECEDENCE,
                    trade_id=pos.trade_id,
                    asset=pos.symbol,
                    current_position=position_state(pos),
                    trigger_level=float(state["stop_level"]),
                    proposed_order={"side": "exit", "stop_level": float(state["stop_level"])},
                    data_quality_flags=base_state,
                    target_unit=TargetUnit.POSITION_LIFECYCLE,
                )
                continue
            result = simulate_atr_stop_exit(pos, row, float(state["stop_level"]), slippage_pct)
            if result is None:
                continue
            before = position_state(pos)
            trade = portfolio.close_position(pos, date, result.fill_price, result.exit_reason)
            actual_fill = {
                "fill_price": result.fill_price,
                "fill_time": pd.Timestamp(date).isoformat(),
                "exit_reason": result.exit_reason,
                "gap_through_stop": result.gap_through_stop,
            }
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.STOP_CHECK,
                decision_type=DecisionType.EXIT_POSITION,
                reason_code=result.reason_code,
                trade_id=pos.trade_id,
                asset=pos.symbol,
                trigger_level=result.trigger_level,
                current_position=before,
                proposed_order={"side": "exit", "stop_level": result.trigger_level},
                actual_fill=actual_fill,
                modeled_cost=abs(pos.shares * result.fill_price * slippage_pct),
                state_before=before,
                state_after={"closed_trade": trade},
                data_quality_flags={**base_state, "gap_through_stop": result.gap_through_stop},
                target_unit=TargetUnit.POSITION_LIFECYCLE,
            )


class TimeStopOverlay(TradeManagementOverlay):
    overlay_id = "OVL-EXT-001"
    supported_target_units = {TargetUnit.POSITION_LIFECYCLE}

    def __init__(self, max_completed_bars: int = 5, strategies: list[str] | None = None):
        super().__init__(max_completed_bars=max_completed_bars, strategies=strategies or [])
        self.max_completed_bars = int(max_completed_bars)
        self.strategies = set(strategies or [])

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        managed_exits = list(exits)
        existing_exit_ids = set(pending_exit_ids) | {exit_signal.trade_id for exit_signal in exits}
        for pos in list(portfolio.positions):
            if self.strategies and pos.strategy not in self.strategies:
                continue
            if pos.trade_id in existing_exit_ids:
                continue
            if pos.bars_held < self.max_completed_bars:
                continue
            exit_signal = ExitSignal(
                date=date,
                strategy=pos.strategy,
                symbol=pos.symbol,
                trade_id=pos.trade_id,
                reason="overlay_time_stop",
                notes=f"max_completed_bars={self.max_completed_bars}",
            )
            managed_exits.append(exit_signal)
            existing_exit_ids.add(pos.trade_id)
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.POSITION_LIFECYCLE,
                decision_type=DecisionType.EXIT_POSITION,
                reason_code=ReasonCode.TIME_STOP,
                signal=exit_signal,
                trade_id=pos.trade_id,
                asset=pos.symbol,
                current_position=position_state(pos),
                proposed_order={"side": "exit_next_valid_open", "bars_held": pos.bars_held},
                data_quality_flags={"max_completed_bars": self.max_completed_bars},
                target_unit=TargetUnit.POSITION_LIFECYCLE,
            )
        return ManagedIntentBatch(entries=entries, exits=managed_exits)
