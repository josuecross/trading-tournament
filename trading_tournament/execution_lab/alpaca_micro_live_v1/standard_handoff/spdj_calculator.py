from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from contracts.forward_observation.forward_observation_handoff_standard_v1.calendar import (
    MarketSession,
    StaticExchangeCalendar,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    CalculationEvent,
    CalculationResult,
    IdentityBinding,
    StandardHandoff,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.timing import (
    resolve_effective_timestamp,
)


SYMBOLS = ("SPY", "IYR", "GSG", "GLD", "AGG", "TIP")
MIN_MONTHLY_RETURNS = 36
MAX_MONTHLY_RETURNS = 120
WEIGHT_TOLERANCE = 1e-8
FORMULA_TOLERANCE = 1e-10


class SpdjCalculationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def classify_regime(cpi_yoy: float) -> str:
    if cpi_yoy < 1.5:
        return "low"
    if cpi_yoy <= 2.5:
        return "medium"
    return "high"


def low_regime_weights() -> dict[str, float]:
    return {symbol: 0.60 if symbol == "SPY" else 0.40 if symbol == "AGG" else 0.0 for symbol in SYMBOLS}


def inverse_volatility_weights(window_returns: pd.DataFrame) -> tuple[dict[str, float], dict[str, Any]]:
    volatility = window_returns.loc[:, SYMBOLS].std(axis=0, ddof=1)
    if not np.isfinite(volatility.to_numpy(dtype=float)).all() or (volatility <= 0.0).any():
        raise SpdjCalculationError("receiver_calculator_conformance_failure", "Invalid sample volatility")
    raw = 1.0 / volatility
    weights = raw / raw.sum()
    diagnostics = {
        "sample_volatility_ddof": 1,
        "sample_volatility": {symbol: float(volatility[symbol]) for symbol in SYMBOLS},
        "raw_inverse_volatility": {symbol: float(raw[symbol]) for symbol in SYMBOLS},
    }
    return {symbol: float(weights[symbol]) for symbol in SYMBOLS}, diagnostics


def beta_transform(beta: float) -> float:
    return 1.0 + beta if beta >= 0.0 else 1.0 / (1.0 - beta)


def rolling_twelve_month_returns(window_returns: pd.DataFrame) -> pd.DataFrame:
    return (1.0 + window_returns).rolling(12, min_periods=12).apply(np.prod, raw=True) - 1.0


def pro_ib_weights(
    window_returns: pd.DataFrame,
    cpi_reference: pd.DataFrame,
    *,
    formation_release: pd.Timestamp,
) -> tuple[dict[str, float], dict[str, Any]]:
    returns_12m = rolling_twelve_month_returns(window_returns.loc[:, SYMBOLS]).dropna(how="any")
    pair_months = [
        month
        for month in returns_12m.index
        if month in cpi_reference.index and bool(cpi_reference.loc[month, "event"])
    ]
    if len(pair_months) < 2:
        raise SpdjCalculationError("receiver_price_semantics_validation_failed", "Insufficient CPI/return pairs")
    release_dates = pd.to_datetime(cpi_reference.loc[pair_months, "release_date"], errors="coerce")
    if release_dates.isna().any() or not bool((release_dates <= formation_release).all()):
        raise SpdjCalculationError("CPI_conformance_failure", "ProIB used unavailable CPI information")
    cpi = cpi_reference.loc[pair_months, "cpi_yoy"].astype(float).to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(cpi)), cpi])
    transformed: dict[str, float] = {}
    asset_diagnostics: dict[str, Any] = {}
    for symbol in SYMBOLS:
        response = returns_12m.loc[pair_months, symbol].to_numpy(dtype=float)
        intercept, beta = np.linalg.lstsq(design, response, rcond=None)[0]
        transformed_beta = beta_transform(float(beta))
        if not math.isfinite(transformed_beta) or transformed_beta <= 0.0:
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Invalid ProIB beta transform")
        transformed[symbol] = transformed_beta
        asset_diagnostics[symbol] = {
            "intercept": float(intercept),
            "beta": float(beta),
            "transformed_beta": transformed_beta,
        }
    denominator = sum(transformed.values())
    weights = {symbol: transformed[symbol] / denominator for symbol in SYMBOLS}
    return weights, {
        "pair_count": len(pair_months),
        "pair_months": [str(month) for month in pair_months],
        "CPI_YoY_by_pair": {str(month): float(cpi_reference.loc[month, "cpi_yoy"]) for month in pair_months},
        "rolling_12m_returns": {
            str(month): {symbol: float(returns_12m.loc[month, symbol]) for symbol in SYMBOLS}
            for month in pair_months
        },
        "latest_CPI_release_used": release_dates.max().date().isoformat(),
        "all_CPI_releases_available_by_formation": True,
        "assets": asset_diagnostics,
    }


def load_cpi_reference(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str).fillna("")
    frame["reference_period"] = pd.PeriodIndex(frame["reference_month"], freq="M")
    if frame["reference_period"].duplicated().any() or not frame["reference_period"].is_monotonic_increasing:
        raise SpdjCalculationError("CPI_conformance_failure", "CPI reference months are not ordered and unique")
    frame["release_date"] = pd.to_datetime(frame["bls_release_date"], errors="coerce")
    current_level = pd.to_numeric(frame["cpi_all_items_nsa_level_as_published"], errors="coerce")
    prior_level = pd.to_numeric(frame["prior_year_cpi_level"], errors="coerce")
    exported_yoy = pd.to_numeric(frame["canonical_cpi_yoy_unrounded"], errors="coerce")
    calculated_yoy = 100.0 * (current_level / prior_level - 1.0)
    event_mask = frame["rebalance_event"].str.lower().eq("true")
    if calculated_yoy[event_mask].isna().any() or (
        calculated_yoy[event_mask] - exported_yoy[event_mask]
    ).abs().max() > FORMULA_TOLERANCE:
        raise SpdjCalculationError("CPI_conformance_failure", "CPI YoY formula does not reproduce exported unrounded values")
    frame["exported_cpi_yoy"] = exported_yoy
    frame["cpi_yoy"] = calculated_yoy
    frame["event"] = frame["rebalance_event"].str.lower().eq("true")
    return frame.set_index("reference_period", drop=False)


def normalize_provider_frames(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, Any]]:
    series: dict[str, pd.Series] = {}
    rows: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            raise SpdjCalculationError("historical_provider_unavailable", f"No receiver history for {symbol}")
        local = frame.copy()
        if "date" not in local or "close" not in local:
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", f"Missing date/close for {symbol}")
        local["date"] = pd.to_datetime(local["date"], errors="coerce")
        local["close"] = pd.to_numeric(local["close"], errors="coerce")
        if local["date"].isna().any() or local["close"].isna().any() or (local["close"] <= 0.0).any():
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", f"Invalid adjusted history for {symbol}")
        local = local.sort_values("date")
        if local["date"].duplicated().any():
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", f"Duplicate sessions for {symbol}")
        value = local.set_index("date")["close"].astype(float)
        value.index = pd.DatetimeIndex(value.index).tz_localize(None)
        series[symbol] = value
        rows[symbol] = {
            "first_date": value.index.min().date().isoformat(),
            "last_date": value.index.max().date().isoformat(),
            "session_count": len(value),
        }
    base = series["SPY"].index
    start = max(value.index.min() for value in series.values())
    end = min(value.index.max() for value in series.values())
    base = base[(base >= start) & (base <= end)]
    missing = {symbol: int(series[symbol].reindex(base).isna().sum()) for symbol in SYMBOLS}
    if any(missing.values()):
        raise SpdjCalculationError(
            "receiver_price_semantics_validation_failed",
            f"Missing required common sessions: {missing}",
        )
    prices = pd.concat([series[symbol].reindex(base) for symbol in SYMBOLS], axis=1)
    prices.columns = list(SYMBOLS)
    return prices, {"symbols": rows, "common_start": start.date().isoformat(), "common_end": end.date().isoformat(), "common_sessions": len(base)}


def monthly_return_history(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_prices = prices.groupby(prices.index.to_period("M")).last()
    monthly_returns = monthly_prices.pct_change(fill_method=None).dropna(how="any")
    return monthly_prices, monthly_returns


@dataclass(frozen=True)
class SpdjTargetCalculation:
    reference_month: str
    release_date: str
    cpi_yoy: float
    regime: str
    statistics_cutoff: str
    effective_timestamp: str
    lookback_monthly_returns: int
    target_weights: dict[str, float]
    monthly_return_history: dict[str, dict[str, float]]
    volatility_diagnostics: dict[str, Any]
    pro_ib_diagnostics: dict[str, Any]
    result: CalculationResult


class SpdjReceiverCalculator:
    def __init__(self, handoff: StandardHandoff, binding: IdentityBinding) -> None:
        self.handoff = handoff
        self.binding = binding
        configured = handoff.calculator_contract.calculator_configuration
        if handoff.envelope.strategy_id != "spdj_multi_asset_dynamic_inflation_etf_portability_v1":
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Unexpected strategy identity")
        if [row.symbol for row in handoff.tradable_instruments] != list(SYMBOLS):
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Unexpected SPDJ symbol contract")
        if int(configured["warmup"]["minimum_underlying_monthly_returns"]) != MIN_MONTHLY_RETURNS:
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Unexpected minimum history")
        if int(configured["warmup"]["maximum_underlying_monthly_returns"]) != MAX_MONTHLY_RETURNS:
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Unexpected maximum history")

    def calculate(
        self,
        *,
        reference_month: str,
        cpi_reference: pd.DataFrame,
        prices: pd.DataFrame,
        calendar: StaticExchangeCalendar,
        fixture_id: str,
    ) -> SpdjTargetCalculation:
        month = pd.Period(reference_month, freq="M")
        monthly_prices, returns = monthly_return_history(prices)
        statistics_session = prices.index[prices.index.to_period("M") == month]
        if statistics_session.empty:
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", "Month-end statistics session unavailable")
        return self._calculate_from_returns(
            reference_month=reference_month,
            cpi_reference=cpi_reference,
            monthly_returns=returns,
            statistics_cutoff=statistics_session.max().date().isoformat(),
            month_is_available=month in monthly_prices.index,
            calendar=calendar,
            fixture_id=fixture_id,
            input_source="operational_provider",
        )

    def calculate_from_monthly_inputs(
        self,
        *,
        reference_month: str,
        cpi_reference: pd.DataFrame,
        monthly_returns: pd.DataFrame,
        month_end_sessions: dict[str, str],
        calendar: StaticExchangeCalendar,
        fixture_id: str,
        input_source: str = "frozen_conformance_bundle",
    ) -> SpdjTargetCalculation:
        month = pd.Period(reference_month, freq="M")
        local = monthly_returns.copy()
        if not isinstance(local.index, pd.PeriodIndex):
            local.index = pd.PeriodIndex(local.index.astype(str), freq="M")
        local = local.loc[:, SYMBOLS].astype(float).sort_index()
        return self._calculate_from_returns(
            reference_month=reference_month,
            cpi_reference=cpi_reference,
            monthly_returns=local,
            statistics_cutoff=month_end_sessions.get(reference_month, ""),
            month_is_available=month in local.index,
            calendar=calendar,
            fixture_id=fixture_id,
            input_source=input_source,
        )

    def _calculate_from_returns(
        self,
        *,
        reference_month: str,
        cpi_reference: pd.DataFrame,
        monthly_returns: pd.DataFrame,
        statistics_cutoff: str,
        month_is_available: bool,
        calendar: StaticExchangeCalendar,
        fixture_id: str,
        input_source: str,
    ) -> SpdjTargetCalculation:
        month = pd.Period(reference_month, freq="M")
        if month not in cpi_reference.index or not bool(cpi_reference.loc[month, "event"]):
            raise SpdjCalculationError("CPI_conformance_failure", "Calculation requires a published CPI event")
        cpi_row = cpi_reference.loc[month]
        release = pd.Timestamp(cpi_row["release_date"])
        cpi_yoy = float(cpi_row["cpi_yoy"])
        regime = classify_regime(cpi_yoy)
        if regime != cpi_row["canonical_regime"]:
            raise SpdjCalculationError("CPI_conformance_failure", "CPI regime does not reproduce")
        available = monthly_returns.loc[monthly_returns.index <= month]
        if not month_is_available or len(available) < MIN_MONTHLY_RETURNS:
            raise SpdjCalculationError("not_applicable_pre_warmup", "Fewer than 36 complete monthly returns")
        window = available.tail(min(len(available), MAX_MONTHLY_RETURNS))
        if window.index.max() != month:
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", "Statistics cutoff month is unavailable")
        if not statistics_cutoff:
            raise SpdjCalculationError("receiver_price_semantics_validation_failed", "Month-end statistics session unavailable")
        volatility_weights, volatility_diagnostics = inverse_volatility_weights(window)
        pro_weights, pro_diagnostics = pro_ib_weights(window, cpi_reference, formation_release=release)
        if regime == "low":
            target = low_regime_weights()
        elif regime == "medium":
            target = volatility_weights
        else:
            target = pro_weights
        values = np.array([target[symbol] for symbol in SYMBOLS], dtype=float)
        if not np.isfinite(values).all() or (values < -WEIGHT_TOLERANCE).any() or abs(values.sum() - 1.0) > WEIGHT_TOLERANCE:
            raise SpdjCalculationError("receiver_calculator_conformance_failure", "Invalid receiver target")
        release_timestamp = datetime.combine(release.date(), datetime.min.time(), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        event = CalculationEvent(
            event_id=f"CPIAUCNS:{reference_month}:{release.date().isoformat()}",
            event_type="external_release_event",
            source_id="U.S. Bureau of Labor Statistics:CPIAUCNS",
            source_event_id=str(cpi_row["release_artifact_hash"]),
            source_reference_period=reference_month,
            available_timestamp=release_timestamp,
            processing_timestamp=release_timestamp,
        )
        effective_timestamp = resolve_effective_timestamp(
            self.handoff.timing_contract,
            event=event,
            calendar=calendar,
        )
        result = CalculationResult.target(
            handoff=self.handoff,
            binding=self.binding,
            event=event,
            calculation_run_id=f"historical_fixture:{fixture_id}",
            calculated_at=release_timestamp,
            calculation_reference_time=f"{statistics_cutoff}T21:00:00Z",
            effective_timestamp=effective_timestamp,
            target_weights=target,
            cash_weight=0.0,
            diagnostics={
                "historical_fixture_only": True,
                "reference_month": reference_month,
                "regime": regime,
                "statistics_cutoff": statistics_cutoff,
                "lookback_monthly_returns": len(window),
                "proib_pair_count": pro_diagnostics["pair_count"],
            },
            provenance={
                "calculator": "receiver_native_spdj_calculator_v1",
                "input_source": input_source,
                "research_implementation_executed": False,
                "current_target_calculated": False,
            },
        )
        return SpdjTargetCalculation(
            reference_month=reference_month,
            release_date=release.date().isoformat(),
            cpi_yoy=cpi_yoy,
            regime=regime,
            statistics_cutoff=statistics_cutoff,
            effective_timestamp=effective_timestamp,
            lookback_monthly_returns=len(window),
            target_weights=result.target_weights,
            monthly_return_history={
                str(month_key): {symbol: float(window.loc[month_key, symbol]) for symbol in SYMBOLS}
                for month_key in window.index
            },
            volatility_diagnostics=volatility_diagnostics,
            pro_ib_diagnostics=pro_diagnostics,
            result=result,
        )

    def no_event_result(self, *, reference_month: str, calculated_at: str) -> CalculationResult:
        return CalculationResult.no_event(
            strategy_id=self.handoff.envelope.strategy_id,
            receiver_strategy_id=self.binding.receiver_strategy_id,
            strategy_instance_id=self.binding.strategy_instance_id,
            calculation_run_id=f"historical_no_event:{reference_month}",
            calculated_at=calculated_at,
            calculation_reference_time=calculated_at,
            diagnostics={
                "historical_fixture_only": True,
                "reference_month": reference_month,
                "classification": "no_CPI_announcement_no_rebalance_event",
            },
        )


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    return cursor - timedelta(days=(cursor.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def xnys_holidays(year: int) -> set[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    exceptional = {
        date(2007, 1, 2),
        date(2012, 10, 29),
        date(2012, 10, 30),
        date(2018, 12, 5),
        date(2025, 1, 9),
    }
    return holidays | {day for day in exceptional if day.year == year}


def build_xnys_calendar(start: str = "2005-01-01", end: str = "2025-12-31") -> StaticExchangeCalendar:
    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end)
    eastern = ZoneInfo("America/New_York")
    sessions: list[MarketSession] = []
    cursor = start_day
    holidays_by_year = {year: xnys_holidays(year) for year in range(start_day.year, end_day.year + 1)}
    while cursor <= end_day:
        if cursor.weekday() < 5 and cursor not in holidays_by_year[cursor.year]:
            opened = datetime(cursor.year, cursor.month, cursor.day, 9, 30, tzinfo=eastern).astimezone(timezone.utc)
            closed = datetime(cursor.year, cursor.month, cursor.day, 16, 0, tzinfo=eastern).astimezone(timezone.utc)
            sessions.append(
                MarketSession(
                    session_date=cursor.isoformat(),
                    open_timestamp=opened.isoformat().replace("+00:00", "Z"),
                    close_timestamp=closed.isoformat().replace("+00:00", "Z"),
                )
            )
        cursor += timedelta(days=1)
    return StaticExchangeCalendar("XNYS", sessions)
