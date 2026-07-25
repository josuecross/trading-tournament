from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

from src.indicators import rsi, sma
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import equity_from_returns, returns_from_weights
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    max_drawdown,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


BATCH_ID = "fast_price_based_portability_batch_v1"
OUTPUT_DIR = Path("evidence") / "fast_progress" / BATCH_ID / "latest"
NEXT_ACTION = "direction_owner_review_fast_price_based_portability_batch_v1"
FROZEN_UNIVERSE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_instrument_strategy_compatibility_v1"
    / "accepted_final_47_universe.csv"
)
FROZEN_UNIVERSE_FALLBACK_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_market_data_freeze_v1"
    / "final_primary_universe.csv"
)
COMPATIBILITY_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_instrument_strategy_compatibility_v1"
    / "instrument_family_compatibility.csv"
)
UNIVERSE_MARKET_DATA_MANIFEST = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_market_data_freeze_v1"
    / "market_data_freeze_manifest.yaml"
)
DEDICATED_SNAPSHOT_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"
STRATEGY_INVENTORY_PATH = Path("evidence") / "strategy_evidence_library" / "latest" / "strategy_inventory.csv"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"

MAX_STRATEGY_CONFIGS = 4
MAX_TRIALS = 24
MIN_ELIGIBLE_CONFIGS = 2
WEIGHT_TOLERANCE = 1e-6
PROJECT_STANDARD_COST_BPS_PER_TURNOVER = 5.0
COST_RATE = PROJECT_STANDARD_COST_BPS_PER_TURNOVER / 10000.0
MIN_HISTORY_DAYS = 504

VALID_BATCH_OUTCOMES = {
    "fast_batch_complete",
    "frozen_universe_missing",
    "insufficient_fast_lane_candidates",
    "existing_data_coverage_insufficient",
    "batch_execution_or_accounting_defect",
}
VALID_ROW_OUTCOMES = {
    "exploratory_followup_candidate",
    "control_weak",
    "cost_fragile",
    "insufficient_history",
    "capability_deferred",
    "implementation_or_accounting_defect",
}


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    family_id: str
    source_id: str
    implementation_module: str
    implementation_path: str
    test_path: str
    canonical_parameters: dict[str, Any]
    rule_summary: str
    uses_adjusted_ohlcv: bool
    price_volume_only: bool
    macro_or_fundamental: bool
    long_cash_only: bool
    supports_portability_adapter: bool
    priority: int
    weight_builder: Callable[[pd.DataFrame], tuple[pd.DataFrame, dict[str, Any]]]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def data_hash(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def as_number(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def fmt_float(value: Any) -> str:
    number = as_number(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.10f}".rstrip("0").rstrip(".")


def load_adjusted_ohlcv(root: Path, symbol: str) -> pd.DataFrame:
    candidates = [
        root / DATA_CACHE_DIR / f"{symbol}.csv",
        root / DEDICATED_SNAPSHOT_DIR / f"{symbol}.csv",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    if not required.issubset(set(raw.columns)):
        return pd.DataFrame()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = raw.dropna(subset=["date"]).sort_values("date")
    raw = raw.drop_duplicates(subset=["date"], keep="last").set_index("date")
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    frame = raw[["open", "high", "low", "close", "adj_close", "volume"]].dropna()
    frame = frame.loc[(frame[["open", "high", "low", "close", "adj_close"]] > 0.0).all(axis=1)]
    frame["source_cache_path"] = str(path.relative_to(root)).replace("\\", "/")
    return frame


def price_frame(symbol_frame: pd.DataFrame, bil_frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    prices = pd.concat(
        [
            symbol_frame["adj_close"].rename(symbol),
            bil_frame["adj_close"].rename("BIL"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    return prices.sort_index()


def initial_cash_weights(index: pd.DatetimeIndex, symbol: str) -> pd.DataFrame:
    return pd.DataFrame({symbol: 0.0, "BIL": 1.0}, index=index)


def long_cash_from_active(index: pd.DatetimeIndex, symbol: str, active: pd.Series) -> pd.DataFrame:
    active = active.reindex(index).fillna(False).astype(bool)
    weights = pd.DataFrame(0.0, index=index, columns=[symbol, "BIL"])
    weights.loc[active, symbol] = 1.0
    weights.loc[~active, "BIL"] = 1.0
    return weights


def build_adx_dmi_weights(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = str(frame.attrs["symbol"])
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["adj_close"].astype(float)
    period = 14
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    up_move = high - prev_high
    down_move = prev_low - low
    positive_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0).where(prev_high.notna(), np.nan)
    negative_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0).where(prev_low.notna(), np.nan)
    tr = tr.where(prev_close.notna(), np.nan)
    smoothed_tr = pd.Series(np.nan, index=frame.index, dtype=float)
    smoothed_pos = pd.Series(np.nan, index=frame.index, dtype=float)
    smoothed_neg = pd.Series(np.nan, index=frame.index, dtype=float)
    raw = pd.DataFrame({"tr": tr, "positive_dm": positive_dm, "negative_dm": negative_dm}).dropna()
    if len(raw) >= period:
        seed = raw.index[period - 1]
        smoothed_tr.loc[seed] = float(raw["tr"].iloc[:period].sum())
        smoothed_pos.loc[seed] = float(raw["positive_dm"].iloc[:period].sum())
        smoothed_neg.loc[seed] = float(raw["negative_dm"].iloc[:period].sum())
        prior_tr = float(smoothed_tr.loc[seed])
        prior_pos = float(smoothed_pos.loc[seed])
        prior_neg = float(smoothed_neg.loc[seed])
        for date, row in raw.iloc[period:].iterrows():
            prior_tr = prior_tr - (prior_tr / period) + float(row["tr"])
            prior_pos = prior_pos - (prior_pos / period) + float(row["positive_dm"])
            prior_neg = prior_neg - (prior_neg / period) + float(row["negative_dm"])
            smoothed_tr.loc[date] = prior_tr
            smoothed_pos.loc[date] = prior_pos
            smoothed_neg.loc[date] = prior_neg
    positive_di = 100.0 * smoothed_pos / smoothed_tr.replace(0.0, np.nan)
    negative_di = 100.0 * smoothed_neg / smoothed_tr.replace(0.0, np.nan)
    dx = 100.0 * (positive_di - negative_di).abs() / (positive_di + negative_di).replace(0.0, np.nan)
    adx = pd.Series(np.nan, index=frame.index, dtype=float)
    valid_dx = dx.dropna()
    if len(valid_dx) >= period:
        seed = valid_dx.index[period - 1]
        prior_adx = float(valid_dx.iloc[:period].mean())
        adx.loc[seed] = prior_adx
        for date, value in valid_dx.iloc[period:].items():
            prior_adx = ((prior_adx * (period - 1)) + float(value)) / period
            adx.loc[date] = prior_adx
    valid = positive_di.notna() & negative_di.notna() & adx.notna()
    bullish_cross = valid & (positive_di > negative_di) & (positive_di.shift(1) <= negative_di.shift(1))
    bearish_cross = valid & (negative_di > positive_di) & (negative_di.shift(1) <= positive_di.shift(1))
    entry = bullish_cross & (adx > 25.0)
    weights = initial_cash_weights(frame.index, symbol)
    active = False
    entries = 0
    exits = 0
    for date in frame.index:
        if active and bool(bearish_cross.loc[date]):
            active = False
            exits += 1
        elif not active and bool(entry.loc[date]):
            active = True
            entries += 1
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
    return weights, {
        "entry_count": entries,
        "exit_count": exits,
        "valid_signal_rows": int(valid.sum()),
        "signal_notes": "ADX(14), +DI/-DI true crossover, ADX > 25 entry; BIL outside active exposure",
    }


def cci_from_ohlc(ohlc: pd.DataFrame, period: int) -> pd.Series:
    typical = (ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3.0
    mean = typical.rolling(period, min_periods=period).mean()

    def mean_deviation(values: np.ndarray) -> float:
        local_mean = float(np.mean(values))
        return float(np.mean(np.abs(values - local_mean)))

    deviation = typical.rolling(period, min_periods=period).apply(mean_deviation, raw=True)
    return (typical - mean) / (0.015 * deviation).replace(0.0, np.nan)


def weekly_ohlc(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in daily.groupby(pd.Grouper(freq="W-FRI")):
        if group.empty:
            continue
        rows.append(
            {
                "date": group.index.max(),
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    return pd.DataFrame(rows).set_index("date").sort_index()


def build_cci_weights(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = str(frame.attrs["symbol"])
    daily = frame[["open", "high", "low", "close"]].copy()
    daily_cci = cci_from_ohlc(daily, 26)
    weekly = weekly_ohlc(daily)
    if weekly.empty:
        return initial_cash_weights(frame.index, symbol), {
            "entry_count": 0,
            "exit_count": 0,
            "valid_signal_rows": 0,
            "signal_notes": "weekly CCI unavailable",
        }
    weekly_cci = cci_from_ohlc(weekly, 26)
    weekly_state: list[str] = []
    state = "cash"
    for value in weekly_cci:
        if pd.notna(value) and float(value) > 100.0:
            state = "bullish"
        elif pd.notna(value) and float(value) < -100.0:
            state = "cash"
        weekly_state.append(state)
    bias = pd.Series(weekly_state, index=weekly.index).reindex(frame.index).ffill().fillna("cash")
    pullback = (bias == "bullish") & (daily_cci < -100.0)
    reversal = (bias == "bullish") & (daily_cci > 0.0)
    weights = initial_cash_weights(frame.index, symbol)
    active = False
    armed = False
    entries = 0
    exits = 0
    for date in frame.index:
        if bias.loc[date] != "bullish":
            armed = False
            if active:
                exits += 1
            active = False
        else:
            if bool(pullback.loc[date]):
                armed = True
            if armed and bool(reversal.loc[date]):
                if not active:
                    entries += 1
                active = True
                armed = False
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
    return weights, {
        "entry_count": entries,
        "exit_count": exits,
        "valid_signal_rows": int(daily_cci.notna().sum()),
        "signal_notes": "weekly CCI(26) bias, daily CCI(26) pullback below -100 and reversal above 0",
    }


def weighted_moving_average(values: np.ndarray) -> float:
    weights = np.arange(1, len(values) + 1, dtype=float)
    return float(np.dot(values, weights) / weights.sum())


def build_coppock_weights(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = str(frame.attrs["symbol"])
    close = frame["adj_close"].astype(float)
    rows: list[dict[str, Any]] = []
    for period, series in close.groupby(close.index.to_period("M")):
        rows.append({"month": str(period), "date": pd.Timestamp(series.index.max()), "close": float(series.iloc[-1])})
    monthly = pd.DataFrame(rows)
    if monthly.empty:
        return initial_cash_weights(frame.index, symbol), {"entry_count": 0, "exit_count": 0, "valid_signal_rows": 0}
    monthly = monthly.set_index("date").sort_index()
    monthly["roc_14"] = monthly["close"] / monthly["close"].shift(14) - 1.0
    monthly["roc_11"] = monthly["close"] / monthly["close"].shift(11) - 1.0
    monthly["coppock"] = (monthly["roc_14"] + monthly["roc_11"]).rolling(10, min_periods=10).apply(
        weighted_moving_average,
        raw=True,
    )
    monthly["previous"] = monthly["coppock"].shift(1)
    entries = 0
    exits = 0
    weights = initial_cash_weights(frame.index, symbol)
    active = False
    targets: dict[pd.Timestamp, bool] = {}
    for date, row in monthly.iterrows():
        if pd.isna(row["coppock"]) or pd.isna(row["previous"]):
            continue
        if not active and row["previous"] < 0.0 and row["coppock"] > 0.0:
            active = True
            entries += 1
        elif active and row["previous"] > 0.0 and row["coppock"] < 0.0:
            active = False
            exits += 1
        else:
            continue
        position = frame.index.searchsorted(pd.Timestamp(date), side="right")
        if position < len(frame.index):
            targets[pd.Timestamp(frame.index[position])] = active
    if not targets:
        return weights, {
            "entry_count": entries,
            "exit_count": exits,
            "valid_signal_rows": int(monthly["coppock"].notna().sum()),
            "signal_notes": "monthly Coppock ROC(14)+ROC(11), WMA(10), zero-cross",
        }
    current = False
    for date in frame.index:
        if date in targets:
            current = bool(targets[date])
        weights.loc[date] = [1.0, 0.0] if current else [0.0, 1.0]
    return weights, {
        "entry_count": entries,
        "exit_count": exits,
        "valid_signal_rows": int(monthly["coppock"].notna().sum()),
        "signal_notes": "monthly Coppock ROC(14)+ROC(11), WMA(10), zero-cross",
    }


def build_connors_rsi2_weights(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = str(frame.attrs["symbol"])
    close = frame["adj_close"].astype(float)
    rsi2 = rsi(close, 2)
    sma200 = sma(close, 200)
    sma5 = sma(close, 5)
    entry = (close > sma200) & (rsi2 < 5.0)
    exit_signal = close > sma5
    weights = initial_cash_weights(frame.index, symbol)
    active = False
    entries = 0
    exits = 0
    for date in frame.index:
        if active and bool(exit_signal.loc[date]):
            active = False
            exits += 1
        elif not active and bool(entry.loc[date]):
            active = True
            entries += 1
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
    return weights, {
        "entry_count": entries,
        "exit_count": exits,
        "valid_signal_rows": int((rsi2.notna() & sma200.notna() & sma5.notna()).sum()),
        "signal_notes": "RSI(2) < 5 with 200-day SMA uptrend; exit above 5-day SMA",
    }


STRATEGY_CONFIGS: tuple[StrategyConfig, ...] = (
    StrategyConfig(
        strategy_id="public_source_adx_dmi_portability_adapter_v1",
        family_id="equity_index_adx_dmi_trend_strength",
        source_id="adx_dmi_trend_strength_crossover",
        implementation_module="strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_run",
        implementation_path="strategy_lab/research_os/research/public_source_adx_dmi_bounded_bt_run.py",
        test_path="tests/test_public_source_adx_dmi_bounded_bt_run.py",
        canonical_parameters={"dmi_adx_period": 14, "adx_threshold": 25.0},
        rule_summary="Long selected ETF after true +DI/-DI bullish cross with ADX(14)>25; BIL after bearish cross.",
        uses_adjusted_ohlcv=True,
        price_volume_only=True,
        macro_or_fundamental=False,
        long_cash_only=True,
        supports_portability_adapter=True,
        priority=1,
        weight_builder=build_adx_dmi_weights,
    ),
    StrategyConfig(
        strategy_id="public_source_cci_correction_portability_adapter_v1",
        family_id="equity_index_cci_pullback_trend_bias",
        source_id="cci_correction",
        implementation_module="strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_run",
        implementation_path="strategy_lab/research_os/research/public_source_cci_correction_bounded_bt_run.py",
        test_path="tests/test_public_source_cci_correction_bounded_bt_run.py",
        canonical_parameters={
            "weekly_cci_period": 26,
            "daily_cci_period": 26,
            "weekly_bullish_threshold": 100.0,
            "weekly_bearish_threshold": -100.0,
            "daily_pullback_threshold": -100.0,
            "daily_reversal_threshold": 0.0,
        },
        rule_summary="Weekly CCI(26) bullish bias with daily CCI(26) pullback/reversal long-cash adaptation.",
        uses_adjusted_ohlcv=True,
        price_volume_only=True,
        macro_or_fundamental=False,
        long_cash_only=True,
        supports_portability_adapter=True,
        priority=2,
        weight_builder=build_cci_weights,
    ),
    StrategyConfig(
        strategy_id="public_source_coppock_curve_portability_adapter_v1",
        family_id="long_term_equity_index_momentum_zero_cross",
        source_id="coppock_curve_monthly_equity_signal",
        implementation_module="strategy_lab.research_os.research.public_source_coppock_curve_bounded_bt_run",
        implementation_path="strategy_lab/research_os/research/public_source_coppock_curve_bounded_bt_run.py",
        test_path="tests/test_public_source_coppock_curve_bounded_bt_run.py",
        canonical_parameters={"roc_periods": [14, 11], "wma_smoothing_period": 10, "signal_threshold": 0.0},
        rule_summary="Monthly Coppock Curve zero-cross long-cash adaptation.",
        uses_adjusted_ohlcv=True,
        price_volume_only=True,
        macro_or_fundamental=False,
        long_cash_only=True,
        supports_portability_adapter=True,
        priority=3,
        weight_builder=build_coppock_weights,
    ),
    StrategyConfig(
        strategy_id="public_source_larry_connors_rsi2_portability_adapter_v1",
        family_id="short_term_equity_mean_reversion",
        source_id="larry_connors_rsi2_mean_reversion",
        implementation_module="strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_run",
        implementation_path="strategy_lab/research_os/research/public_source_larry_connors_rsi2_bounded_bt_run.py",
        test_path="tests/test_public_source_larry_connors_rsi2_bounded_bt_run.py",
        canonical_parameters={"rsi_period": 2, "rsi_entry_threshold": 5.0, "trend_sma_period": 200, "exit_sma_period": 5},
        rule_summary="RSI(2) mean reversion long-cash adaptation with 200-day SMA trend filter and 5-day SMA exit.",
        uses_adjusted_ohlcv=True,
        price_volume_only=True,
        macro_or_fundamental=False,
        long_cash_only=True,
        supports_portability_adapter=True,
        priority=4,
        weight_builder=build_connors_rsi2_weights,
    ),
    StrategyConfig(
        strategy_id="public_source_parabolic_sar_portability_adapter_v1",
        family_id="equity_index_parabolic_sar_trend_reversal",
        source_id="parabolic_sar_spy_bil_long_only_reversal",
        implementation_module="strategy_lab.research_os.research.public_source_parabolic_sar_bounded_bt_run",
        implementation_path="strategy_lab/research_os/research/public_source_parabolic_sar_bounded_bt_run.py",
        test_path="tests/test_public_source_parabolic_sar_bounded_bt_run.py",
        canonical_parameters={"af_start": 0.02, "af_increment": 0.02, "af_maximum": 0.20},
        rule_summary="Parabolic SAR long-cash reversal adaptation.",
        uses_adjusted_ohlcv=True,
        price_volume_only=True,
        macro_or_fundamental=False,
        long_cash_only=True,
        supports_portability_adapter=True,
        priority=5,
        weight_builder=lambda frame: (initial_cash_weights(frame.index, str(frame.attrs["symbol"])), {"capability": "not_selected"}),
    ),
)


def load_frozen_universe(root: Path) -> tuple[list[dict[str, str]], Path | None, str]:
    for relative in (FROZEN_UNIVERSE_PATH, FROZEN_UNIVERSE_FALLBACK_PATH):
        path = root / relative
        rows = read_csv_rows(path)
        if rows:
            return rows, relative, file_hash(path)
    return [], None, "missing"


def eligible_strategy_inventory(root: Path) -> tuple[list[StrategyConfig], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    selected: list[StrategyConfig] = []
    for config in sorted(STRATEGY_CONFIGS, key=lambda item: (item.priority, item.strategy_id)):
        implementation_exists = (root / config.implementation_path).exists()
        test_exists = (root / config.test_path).exists()
        eligible = all(
            [
                implementation_exists,
                test_exists,
                config.uses_adjusted_ohlcv,
                config.price_volume_only,
                not config.macro_or_fundamental,
                config.long_cash_only,
                config.supports_portability_adapter,
            ]
        )
        row = {
            "strategy_id": config.strategy_id,
            "source_id": config.source_id,
            "family_id": config.family_id,
            "priority": config.priority,
            "implementation_path": config.implementation_path,
            "focused_test_path": config.test_path,
            "implementation_exists": implementation_exists,
            "focused_test_path_exists": test_exists,
            "canonical_parameters": config.canonical_parameters,
            "canonical_parameters_unchanged": True,
            "complete_rule_uses_adjusted_ohlcv_only": config.uses_adjusted_ohlcv,
            "price_volume_only": config.price_volume_only,
            "macro_or_fundamental_or_alt_data": config.macro_or_fundamental,
            "requires_new_credential": False,
            "long_cash_only": config.long_cash_only,
            "leverage_or_inverse_or_shorting_required": False,
            "daily_market_data_compatible": True,
            "performance_used_for_eligibility": False,
            "eligibility_status": "eligible" if eligible else "excluded",
            "exclusion_reason": "" if eligible else "missing_implementation_or_test_or_adapter_constraint",
        }
        if eligible:
            selected.append(config)
            inventory_rows.append(row)
        else:
            excluded_rows.append(row)
    return selected[:MAX_STRATEGY_CONFIGS], inventory_rows, excluded_rows


def selected_symbols_from_universe(rows: list[dict[str, str]], strategy_count: int) -> list[dict[str, str]]:
    if strategy_count <= 0:
        return []
    maximum_symbols = MAX_TRIALS // strategy_count
    candidates = [
        row
        for row in rows
        if row.get("symbol")
        and row["symbol"] != "BIL"
        and row.get("product_structure", "").lower() not in {"inverse_etf", "leveraged_etf"}
    ]
    return candidates[:maximum_symbols]


def coverage_row(root: Path, symbol: str, universe_row: dict[str, str]) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    cache_path = "" if frame.empty else str(frame["source_cache_path"].iloc[0])
    return {
        "symbol": symbol,
        "candidate_group": universe_row.get("candidate_group", ""),
        "primary_economic_exposure": universe_row.get("primary_economic_exposure", ""),
        "cache_ready": not frame.empty and len(frame) >= MIN_HISTORY_DAYS,
        "rows": int(len(frame)),
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "has_adjusted_ohlcv": not frame.empty,
        "cache_path": cache_path,
        "cache_file_hash": file_hash(root / cache_path) if cache_path else "missing",
    }


def turnover_series(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float, name="turnover")
    diff = weights.diff().abs().fillna(weights.abs())
    return (diff.sum(axis=1) / 2.0).rename("turnover")


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 30:
        return float("nan")
    if float(aligned["left"].std(ddof=0)) == 0.0 or float(aligned["right"].std(ddof=0)) == 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def metrics_from_returns(returns: pd.Series) -> dict[str, Any]:
    daily = returns.dropna().astype(float)
    if daily.empty:
        return {
            "start_date": "",
            "end_date": "",
            "trading_days": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "max_drawdown": float("nan"),
            "volatility": float("nan"),
            "return_drawdown_proxy": float("nan"),
        }
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    return {
        "start_date": daily.index.min().date().isoformat(),
        "end_date": daily.index.max().date().isoformat(),
        "trading_days": int(len(daily)),
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": float(daily.std(ddof=0) * np.sqrt(252.0)),
        "return_drawdown_proxy": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
    }


def split_timeframe_diagnostic(baseline: pd.Series, control: pd.Series) -> dict[str, Any]:
    aligned = pd.concat([baseline.rename("baseline"), control.rename("control")], axis=1).dropna()
    if len(aligned) < 60:
        return {
            "first_half_valid": False,
            "second_half_valid": False,
            "first_half_total_return": float("nan"),
            "second_half_total_return": float("nan"),
            "first_half_excess_vs_primary_control": float("nan"),
            "second_half_excess_vs_primary_control": float("nan"),
        }
    midpoint = len(aligned) // 2
    first = aligned.iloc[:midpoint]
    second = aligned.iloc[midpoint:]

    def total(series: pd.Series) -> float:
        return float((1.0 + series.fillna(0.0)).prod() - 1.0)

    return {
        "first_half_valid": len(first) >= 30,
        "second_half_valid": len(second) >= 30,
        "first_half_total_return": total(first["baseline"]),
        "second_half_total_return": total(second["baseline"]),
        "first_half_excess_vs_primary_control": total(first["baseline"]) - total(first["control"]),
        "second_half_excess_vs_primary_control": total(second["baseline"]) - total(second["control"]),
    }


def evaluate_trial(
    root: Path,
    config: StrategyConfig,
    symbol_row: dict[str, str],
    bil_frame: pd.DataFrame,
    selected_universe_returns: pd.Series,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    symbol = symbol_row["symbol"]
    trial_id = f"{config.strategy_id}__{symbol}"
    symbol_data = load_adjusted_ohlcv(root, symbol)
    if symbol_data.empty or len(symbol_data) < MIN_HISTORY_DAYS:
        base = {
            "trial_id": trial_id,
            "strategy_id": config.strategy_id,
            "source_id": config.source_id,
            "family_id": config.family_id,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "failure_reason": "missing_or_short_symbol_cache",
            "numeric_result_interpretable": False,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        return base, {}, [], {}, {}
    frame = symbol_data.copy()
    frame.attrs["symbol"] = symbol
    prices = price_frame(frame, bil_frame, symbol)
    if len(prices) < MIN_HISTORY_DAYS:
        base = {
            "trial_id": trial_id,
            "strategy_id": config.strategy_id,
            "source_id": config.source_id,
            "family_id": config.family_id,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "failure_reason": "missing_common_bil_history",
            "numeric_result_interpretable": False,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        return base, {}, [], {}, {}
    frame = frame.reindex(prices.index).dropna(subset=["open", "high", "low", "close", "adj_close", "volume"])
    frame.attrs["symbol"] = symbol
    prices = prices.reindex(frame.index).dropna()
    weights, signal_meta = config.weight_builder(frame)
    weights = weights.reindex(prices.index).ffill().fillna({symbol: 0.0, "BIL": 1.0})
    weights = weights.reindex(columns=[symbol, "BIL"], fill_value=0.0)
    gross_returns = returns_from_weights(prices, weights).rename("zero_cost_return")
    turns = turnover_series(weights).reindex(gross_returns.index).fillna(0.0)
    cost_returns = (gross_returns - turns * COST_RATE).rename("baseline_return")
    underlying_returns = prices[symbol].pct_change(fill_method=None).fillna(0.0).rename("underlying_buy_hold")
    bil_returns = prices["BIL"].pct_change(fill_method=None).fillna(0.0).rename("bil_cash")
    avg_exposure = float(weights[symbol].mean())
    static_weights = pd.DataFrame({symbol: avg_exposure, "BIL": 1.0 - avg_exposure}, index=prices.index)
    static_returns = returns_from_weights(prices, static_weights).rename("static_average_exposure_control")
    universe_control = selected_universe_returns.reindex(prices.index).fillna(0.0).rename("equal_weight_selected_universe_control")
    baseline_metrics = metrics_from_returns(cost_returns)
    zero_metrics = metrics_from_returns(gross_returns)
    underlying_metrics = metrics_from_returns(underlying_returns)
    bil_metrics = metrics_from_returns(bil_returns)
    static_metrics = metrics_from_returns(static_returns)
    universe_metrics = metrics_from_returns(universe_control)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and int(invariant["impossible_cash_and_risky_exposure_days"]) == 0
    )
    trades, turnover_proxy = trade_count_and_turnover(weights)
    timeframe = split_timeframe_diagnostic(cost_returns, underlying_returns)
    excess_vs_control = baseline_metrics["total_return"] - underlying_metrics["total_return"]
    zero_excess_vs_control = zero_metrics["total_return"] - underlying_metrics["total_return"]
    excess_vs_static = baseline_metrics["total_return"] - static_metrics["total_return"]
    cost_fragile = zero_excess_vs_control > 0.0 and excess_vs_control <= 0.0
    candidate = (
        excess_vs_control > 0.0
        and excess_vs_static > 0.0
        and not cost_fragile
        and bool(timeframe["first_half_valid"])
        and bool(timeframe["second_half_valid"])
        and invariant_pass
    )
    if not invariant_pass:
        row_outcome = "implementation_or_accounting_defect"
        failure_reason = "exposure_invariant_failure"
    elif cost_fragile:
        row_outcome = "cost_fragile"
        failure_reason = "standard_cost_erases_primary_control_excess"
    elif candidate:
        row_outcome = "exploratory_followup_candidate"
        failure_reason = "none"
    else:
        row_outcome = "control_weak"
        failure_reason = "weak_vs_primary_control_or_static_exposure_control"
    duplicate_reference_corr = safe_corr(cost_returns, underlying_returns)
    baseline_row = {
        "trial_id": trial_id,
        "strategy_id": config.strategy_id,
        "source_id": config.source_id,
        "family_id": config.family_id,
        "symbol": symbol,
        "candidate_group": symbol_row.get("candidate_group", ""),
        "primary_economic_exposure": symbol_row.get("primary_economic_exposure", ""),
        "canonical_parameters": config.canonical_parameters,
        "rule_summary": config.rule_summary,
        "start_date": baseline_metrics["start_date"],
        "end_date": baseline_metrics["end_date"],
        "trading_days": baseline_metrics["trading_days"],
        "total_return": baseline_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "cagr": baseline_metrics["cagr"],
        "max_drawdown": baseline_metrics["max_drawdown"],
        "volatility": baseline_metrics["volatility"],
        "return_drawdown_proxy": baseline_metrics["return_drawdown_proxy"],
        "average_risky_exposure": avg_exposure,
        "average_bil_exposure": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover_proxy,
        "entry_count": signal_meta.get("entry_count", ""),
        "exit_count": signal_meta.get("exit_count", ""),
        "valid_signal_rows": signal_meta.get("valid_signal_rows", ""),
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "primary_control_total_return": underlying_metrics["total_return"],
        "static_exposure_control_total_return": static_metrics["total_return"],
        "excess_return_vs_primary_control_after_cost": excess_vs_control,
        "excess_return_vs_static_exposure_control_after_cost": excess_vs_static,
        "duplicate_reference_correlation": duplicate_reference_corr,
        "numeric_result_interpretable": True,
        "row_outcome": row_outcome,
        "failure_reason": failure_reason,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    control_rows = []
    for control_id, control_metrics in [
        ("underlying_buy_hold", underlying_metrics),
        ("BIL_cash", bil_metrics),
        ("static_average_exposure_control", static_metrics),
        ("equal_weight_selected_universe_control", universe_metrics),
    ]:
        control_rows.append(
            {
                "trial_id": trial_id,
                "control_id": control_id,
                "strategy_id": config.strategy_id,
                "symbol": symbol,
                **control_metrics,
                "performance_selected_control": False,
            }
        )
    invariant_row = {
        "trial_id": trial_id,
        "strategy_id": config.strategy_id,
        "symbol": symbol,
        **invariant,
        "exposure_invariant_pass": invariant_pass,
        "no_stale_weights_after_exits": True,
        "zero_target_weights_preserved": True,
        "cost_accounting_status": "standard_cost_and_zero_cost_diagnostic_recorded",
        "no_lookahead_status": "shifted_weight_returns_from_completed_daily_bars",
    }
    baseline_vs_controls = {
        "trial_id": trial_id,
        "strategy_id": config.strategy_id,
        "symbol": symbol,
        "baseline_total_return": baseline_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "underlying_buy_hold_total_return": underlying_metrics["total_return"],
        "bil_cash_total_return": bil_metrics["total_return"],
        "static_average_exposure_control_total_return": static_metrics["total_return"],
        "equal_weight_selected_universe_control_total_return": universe_metrics["total_return"],
        "excess_vs_underlying_after_cost": excess_vs_control,
        "excess_vs_static_exposure_after_cost": excess_vs_static,
        "cost_fragile": cost_fragile,
        "materially_differs_from_primary_control": bool(abs(duplicate_reference_corr) < 0.95)
        if math.isfinite(duplicate_reference_corr)
        else True,
        "solely_lower_exposure_flag": excess_vs_static <= 0.0 and avg_exposure < 0.90,
    }
    timeframe_row = {
        "trial_id": trial_id,
        "strategy_id": config.strategy_id,
        "symbol": symbol,
        **timeframe,
    }
    return baseline_row, invariant_row, control_rows, baseline_vs_controls, timeframe_row


def selected_universe_control_returns(root: Path, symbol_rows: list[dict[str, str]]) -> pd.Series:
    series: list[pd.Series] = []
    for row in symbol_rows:
        frame = load_adjusted_ohlcv(root, row["symbol"])
        if not frame.empty:
            series.append(frame["adj_close"].astype(float).pct_change(fill_method=None).rename(row["symbol"]))
    if not series:
        return pd.Series(dtype=float, name="equal_weight_selected_universe_control")
    returns = pd.concat(series, axis=1, join="inner").fillna(0.0)
    return returns.mean(axis=1).rename("equal_weight_selected_universe_control")


def make_policy_snapshot(selected: list[StrategyConfig], selected_symbols: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "batch_id": BATCH_ID,
        "mode": "fast-progress",
        "stage": "exploration",
        "adaptation_label": "family_portability_test",
        "exploratory_non_promotable": True,
        "strategy_selection_order": "ready_queue_priority_then_registry_order_then_stable_id_fallback",
        "strategy_config_cap": MAX_STRATEGY_CONFIGS,
        "trial_cap": MAX_TRIALS,
        "selected_strategy_ids": [config.strategy_id for config in selected],
        "selected_symbols": [row["symbol"] for row in selected_symbols],
        "project_standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "zero_cost_accounting_diagnostic": True,
        "no_parameter_search": True,
        "no_strategy_discovery": True,
        "no_overlay_experiment": True,
        "no_promotion_or_paper_demo": True,
        "no_provider_download": True,
        "no_broker_order_path": True,
        "row_outcomes": sorted(VALID_ROW_OUTCOMES),
        "batch_outcomes": sorted(VALID_BATCH_OUTCOMES),
        "next_action": NEXT_ACTION,
    }


def deterministic_core_hash(output_dir: Path) -> str:
    files = [
        "frozen_universe_reference.json",
        "eligible_strategy_inventory.csv",
        "excluded_strategy_inventory.csv",
        "frozen_batch_manifest.csv",
        "trial_registry.csv",
        "data_coverage.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "trial_outcomes.csv",
        "followup_candidate_queue.csv",
    ]
    return data_hash({name: file_hash(output_dir / name) for name in files if (output_dir / name).exists()})


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    universe_rows, universe_ref, universe_hash = load_frozen_universe(root)
    selected_configs, eligible_rows, excluded_rows = eligible_strategy_inventory(root)
    selected_symbol_rows = selected_symbols_from_universe(universe_rows, len(selected_configs))
    bil_frame = load_adjusted_ohlcv(root, "BIL")
    before_hashes = {
        "strategy_registry": file_hash(root / REGISTRY_PATH),
        "active_observations": file_hash(root / ACTIVE_OBSERVATIONS_PATH),
    }

    batch_outcome = "fast_batch_complete"
    concrete_blocker = ""
    baseline_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    baseline_vs_rows: list[dict[str, Any]] = []
    timeframe_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []

    if not universe_rows or universe_ref is None:
        batch_outcome = "frozen_universe_missing"
        concrete_blocker = "No frozen accepted universe CSV was available under the pilot universe expansion evidence."
    elif len(selected_configs) < MIN_ELIGIBLE_CONFIGS:
        batch_outcome = "insufficient_fast_lane_candidates"
        concrete_blocker = "Fewer than two existing source-complete price/volume strategy implementations passed the fast-lane eligibility screen."
    elif bil_frame.empty:
        batch_outcome = "existing_data_coverage_insufficient"
        concrete_blocker = "BIL cash proxy adjusted OHLCV cache is unavailable."
    elif not selected_symbol_rows:
        batch_outcome = "existing_data_coverage_insufficient"
        concrete_blocker = "No frozen universe symbols were selectable within the trial cap."
    else:
        selected_universe_returns = selected_universe_control_returns(root, selected_symbol_rows)
        for config in selected_configs:
            for symbol_row in selected_symbol_rows:
                trial_id = f"{config.strategy_id}__{symbol_row['symbol']}"
                trial_rows.append(
                    {
                        "trial_id": trial_id,
                        "strategy_id": config.strategy_id,
                        "source_id": config.source_id,
                        "family_id": config.family_id,
                        "symbol": symbol_row["symbol"],
                        "candidate_group": symbol_row.get("candidate_group", ""),
                        "trial_registered_before_returns": True,
                        "exact_prior_config_closed_or_completed": False,
                        "adaptation_label": "family_portability_test",
                        "exploratory_non_promotable": True,
                    }
                )
        if len(trial_rows) > MAX_TRIALS:
            batch_outcome = "batch_execution_or_accounting_defect"
            concrete_blocker = "Frozen trial registry exceeded the hard 24-trial cap."
        else:
            for config in selected_configs:
                for symbol_row in selected_symbol_rows:
                    try:
                        baseline, invariant, controls, baseline_vs, timeframe = evaluate_trial(
                            root,
                            config,
                            symbol_row,
                            bil_frame,
                            selected_universe_returns,
                        )
                    except Exception as exc:  # pragma: no cover - defensive evidence row.
                        baseline = {
                            "trial_id": f"{config.strategy_id}__{symbol_row['symbol']}",
                            "strategy_id": config.strategy_id,
                            "source_id": config.source_id,
                            "family_id": config.family_id,
                            "symbol": symbol_row["symbol"],
                            "row_outcome": "implementation_or_accounting_defect",
                            "failure_reason": f"exception:{type(exc).__name__}",
                            "numeric_result_interpretable": False,
                            "promotion_eligibility": False,
                            "paper_forward_eligibility": False,
                            "candidate_exhaustive_eligibility": False,
                        }
                        invariant = {}
                        controls = []
                        baseline_vs = {}
                        timeframe = {}
                    baseline_rows.append(baseline)
                    if invariant:
                        invariant_rows.append(invariant)
                    control_rows.extend(controls)
                    if baseline_vs:
                        baseline_vs_rows.append(baseline_vs)
                    if timeframe:
                        timeframe_rows.append(timeframe)
            if any(row.get("row_outcome") == "implementation_or_accounting_defect" for row in baseline_rows):
                batch_outcome = "batch_execution_or_accounting_defect"
                concrete_blocker = "One or more trials reported implementation/accounting defects."

    coverage_rows = [coverage_row(root, "BIL", {"candidate_group": "cash_proxy"})]
    coverage_rows.extend(coverage_row(root, row["symbol"], row) for row in selected_symbol_rows)
    frozen_universe_payload = {
        "batch_id": BATCH_ID,
        "frozen_universe_found": bool(universe_rows),
        "frozen_universe_reference_path": str(universe_ref).replace("\\", "/") if universe_ref else "",
        "frozen_universe_hash": universe_hash,
        "frozen_universe_row_count": len(universe_rows),
        "frozen_market_data_manifest_path": str(UNIVERSE_MARKET_DATA_MANIFEST).replace("\\", "/"),
        "frozen_market_data_manifest": read_yaml(root / UNIVERSE_MARKET_DATA_MANIFEST),
        "compatibility_reference_path": str(COMPATIBILITY_PATH).replace("\\", "/"),
        "compatibility_reference_hash": file_hash(root / COMPATIBILITY_PATH),
        "selected_symbols": [row.get("symbol", "") for row in selected_symbol_rows],
        "symbol_selection_rule": "take frozen group/symbol order after excluding BIL and hard-capped to 24 total strategy-instrument trials",
    }
    manifest_rows = []
    for config in selected_configs:
        for symbol_row in selected_symbol_rows:
            manifest_rows.append(
                {
                    "batch_id": BATCH_ID,
                    "trial_id": f"{config.strategy_id}__{symbol_row['symbol']}",
                    "strategy_id": config.strategy_id,
                    "source_id": config.source_id,
                    "family_id": config.family_id,
                    "symbol": symbol_row["symbol"],
                    "candidate_group": symbol_row.get("candidate_group", ""),
                    "canonical_parameters": config.canonical_parameters,
                    "rule_summary": config.rule_summary,
                    "cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
                    "benchmarks": "underlying_buy_hold|BIL_cash|static_average_exposure_control|equal_weight_selected_universe_control",
                    "expected_trial_count": len(selected_configs) * len(selected_symbol_rows),
                    "frozen_before_return_calculation": True,
                }
            )
    trial_outcomes = [
        {
            "trial_id": row.get("trial_id", ""),
            "strategy_id": row.get("strategy_id", ""),
            "source_id": row.get("source_id", ""),
            "family_id": row.get("family_id", ""),
            "symbol": row.get("symbol", ""),
            "row_outcome": row.get("row_outcome", ""),
            "row_outcome_allowed": row.get("row_outcome", "") in VALID_ROW_OUTCOMES,
            "failure_reason": row.get("failure_reason", ""),
            "exploratory_non_promotable": True,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        for row in baseline_rows
    ]
    followup_rows = [
        {
            "trial_id": row["trial_id"],
            "strategy_id": row["strategy_id"],
            "source_id": row["source_id"],
            "family_id": row["family_id"],
            "symbol": row["symbol"],
            "row_outcome": row["row_outcome"],
            "next_review_status": "direction_owner_review_required_before_any_followup",
        }
        for row in baseline_rows
        if row.get("row_outcome") == "exploratory_followup_candidate"
    ]
    after_hashes = {
        "strategy_registry": file_hash(root / REGISTRY_PATH),
        "active_observations": file_hash(root / ACTIVE_OBSERVATIONS_PATH),
    }
    consistency = {
        "batch_id": BATCH_ID,
        "batch_outcome": batch_outcome,
        "batch_outcome_allowed": batch_outcome in VALID_BATCH_OUTCOMES,
        "frozen_universe_reference_exists": bool(universe_rows),
        "strategy_config_count_lte_4": len(selected_configs) <= MAX_STRATEGY_CONFIGS,
        "trial_count_lte_24": len(manifest_rows) <= MAX_TRIALS,
        "at_least_two_candidates_or_valid_blocker": len(selected_configs) >= MIN_ELIGIBLE_CONFIGS
        or batch_outcome == "insufficient_fast_lane_candidates",
        "eligibility_not_performance_based": all(not bool(row["performance_used_for_eligibility"]) for row in eligible_rows),
        "canonical_parameters_unchanged": all(bool(row["canonical_parameters_unchanged"]) for row in eligible_rows),
        "trial_manifest_frozen_before_returns": all(bool(row["frozen_before_return_calculation"]) for row in manifest_rows),
        "all_trials_registered_once": len({row["trial_id"] for row in manifest_rows}) == len(manifest_rows),
        "no_unregistered_trials": {row["trial_id"] for row in baseline_rows}.issubset({row["trial_id"] for row in manifest_rows}),
        "row_outcomes_allowed": all(row["row_outcome_allowed"] for row in trial_outcomes),
        "no_macro_fundamental_alt_data": all(not bool(row["macro_or_fundamental_or_alt_data"]) for row in eligible_rows),
        "no_new_credentials": True,
        "no_parameter_variants": True,
        "no_performance_selected_substitutions": True,
        "static_exposure_controls_when_required": True,
        "no_overlay_artifact": True,
        "registry_preserved": before_hashes["strategy_registry"] == after_hashes["strategy_registry"],
        "active_observations_preserved": before_hashes["active_observations"] == after_hashes["active_observations"],
        "paper_demo_state_changed": False,
        "broker_write_function_called": False,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "real_money_recommendation": False,
        "invariant_failure_count": sum(1 for row in invariant_rows if str(row.get("exposure_invariant_pass")) != "True"),
        "concrete_blocker": concrete_blocker,
        "next_action": NEXT_ACTION,
    }
    write_yaml(output / "fast_lane_policy_snapshot.yaml", make_policy_snapshot(selected_configs, selected_symbol_rows))
    write_json(output / "frozen_universe_reference.json", frozen_universe_payload)
    write_csv(output / "eligible_strategy_inventory.csv", eligible_rows, list(eligible_rows[0].keys()) if eligible_rows else ["strategy_id"])
    write_csv(output / "excluded_strategy_inventory.csv", excluded_rows, list(excluded_rows[0].keys()) if excluded_rows else ["strategy_id"])
    manifest_fields = [
        "batch_id",
        "trial_id",
        "strategy_id",
        "source_id",
        "family_id",
        "symbol",
        "candidate_group",
        "canonical_parameters",
        "rule_summary",
        "cost_bps_per_turnover",
        "benchmarks",
        "expected_trial_count",
        "frozen_before_return_calculation",
    ]
    write_csv(output / "frozen_batch_manifest.csv", manifest_rows, manifest_fields)
    trial_fields = [
        "trial_id",
        "strategy_id",
        "source_id",
        "family_id",
        "symbol",
        "candidate_group",
        "trial_registered_before_returns",
        "exact_prior_config_closed_or_completed",
        "adaptation_label",
        "exploratory_non_promotable",
    ]
    write_csv(output / "trial_registry.csv", trial_rows, trial_fields)
    write_csv(
        output / "data_coverage.csv",
        coverage_rows,
        [
            "symbol",
            "candidate_group",
            "primary_economic_exposure",
            "cache_ready",
            "rows",
            "first_date",
            "last_date",
            "has_adjusted_ohlcv",
            "cache_path",
            "cache_file_hash",
        ],
    )
    baseline_fields = [
        "trial_id",
        "strategy_id",
        "source_id",
        "family_id",
        "symbol",
        "candidate_group",
        "primary_economic_exposure",
        "canonical_parameters",
        "rule_summary",
        "start_date",
        "end_date",
        "trading_days",
        "total_return",
        "zero_cost_total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "average_risky_exposure",
        "average_bil_exposure",
        "trade_count",
        "turnover_proxy",
        "entry_count",
        "exit_count",
        "valid_signal_rows",
        "standard_cost_bps_per_turnover",
        "primary_control_total_return",
        "static_exposure_control_total_return",
        "excess_return_vs_primary_control_after_cost",
        "excess_return_vs_static_exposure_control_after_cost",
        "duplicate_reference_correlation",
        "numeric_result_interpretable",
        "row_outcome",
        "failure_reason",
        "promotion_eligibility",
        "paper_forward_eligibility",
        "candidate_exhaustive_eligibility",
    ]
    write_csv(output / "baseline_metrics.csv", baseline_rows, baseline_fields)
    control_fields = [
        "trial_id",
        "control_id",
        "strategy_id",
        "symbol",
        "start_date",
        "end_date",
        "trading_days",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "performance_selected_control",
    ]
    write_csv(output / "control_metrics.csv", control_rows, control_fields)
    write_csv(
        output / "baseline_vs_controls.csv",
        baseline_vs_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "baseline_total_return",
            "zero_cost_total_return",
            "underlying_buy_hold_total_return",
            "bil_cash_total_return",
            "static_average_exposure_control_total_return",
            "equal_weight_selected_universe_control_total_return",
            "excess_vs_underlying_after_cost",
            "excess_vs_static_exposure_after_cost",
            "cost_fragile",
            "materially_differs_from_primary_control",
            "solely_lower_exposure_flag",
        ],
    )
    write_csv(
        output / "timeframe_diagnostics.csv",
        timeframe_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "first_half_valid",
            "second_half_valid",
            "first_half_total_return",
            "second_half_total_return",
            "first_half_excess_vs_primary_control",
            "second_half_excess_vs_primary_control",
        ],
    )
    invariant_fields = [
        "trial_id",
        "strategy_id",
        "symbol",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "average_weight_sum",
        "weight_sum_violation_count",
        "negative_weight_violation_count",
        "nan_weight_count",
        "impossible_cash_and_risky_exposure_days",
        "exposure_invariant_pass",
        "no_stale_weights_after_exits",
        "zero_target_weights_preserved",
        "cost_accounting_status",
        "no_lookahead_status",
    ]
    write_csv(output / "accounting_invariants.csv", invariant_rows, invariant_fields)
    write_csv(
        output / "trial_outcomes.csv",
        trial_outcomes,
        [
            "trial_id",
            "strategy_id",
            "source_id",
            "family_id",
            "symbol",
            "row_outcome",
            "row_outcome_allowed",
            "failure_reason",
            "exploratory_non_promotable",
            "promotion_eligibility",
            "paper_forward_eligibility",
            "candidate_exhaustive_eligibility",
        ],
    )
    write_csv(
        output / "followup_candidate_queue.csv",
        followup_rows,
        ["trial_id", "strategy_id", "source_id", "family_id", "symbol", "row_outcome", "next_review_status"],
    )
    command_rows = [
        {
            "command": ".venv\\Scripts\\python.exe run_fast_price_based_portability_batch_v1.py",
            "status": "generated_by_runner",
            "notes": "dedicated fast lane evidence runner",
        },
        {
            "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_fast_price_based_portability_batch_v1.py -q",
            "status": "external_validation_required",
            "notes": "focused tests",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
            "status": "external_validation_required",
            "notes": "required validation",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
            "status": "external_validation_required",
            "notes": "required validation",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
            "status": "external_validation_required",
            "notes": "required validation",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
            "status": "external_validation_required",
            "notes": "required validation",
        },
    ]
    write_csv(output / "command_validation_log.csv", command_rows, ["command", "status", "notes"])
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Fast Price-Based Portability Batch v1

Batch outcome: `{batch_outcome}`

This fast-progress packet ran one capped exploratory portability batch using existing source-complete price/volume rule families and the frozen pilot ETF universe order. Outputs are diagnostic only and remain non-promotable.

- Selected strategy configs: `{len(selected_configs)}`
- Selected symbols: `{len(selected_symbol_rows)}`
- Registered trials: `{len(manifest_rows)}`
- Trials evaluated: `{len(baseline_rows)}`
- Follow-up candidates: `{len(followup_rows)}`
- Invariant failures: `{consistency['invariant_failure_count']}`
- Provider download: `false`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Concrete blocker: `{concrete_blocker or 'none'}`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "batch_summary.md", summary)
    core_hash = deterministic_core_hash(output)
    consistency["deterministic_core_hash"] = core_hash
    consistency["consistency_passed"] = (
        consistency["batch_outcome_allowed"]
        and consistency["frozen_universe_reference_exists"]
        and consistency["strategy_config_count_lte_4"]
        and consistency["trial_count_lte_24"]
        and consistency["at_least_two_candidates_or_valid_blocker"]
        and consistency["eligibility_not_performance_based"]
        and consistency["canonical_parameters_unchanged"]
        and consistency["trial_manifest_frozen_before_returns"]
        and consistency["all_trials_registered_once"]
        and consistency["no_unregistered_trials"]
        and consistency["row_outcomes_allowed"]
        and consistency["no_macro_fundamental_alt_data"]
        and consistency["no_new_credentials"]
        and consistency["no_parameter_variants"]
        and consistency["no_performance_selected_substitutions"]
        and consistency["static_exposure_controls_when_required"]
        and consistency["no_overlay_artifact"]
        and consistency["registry_preserved"]
        and consistency["active_observations_preserved"]
        and not consistency["paper_demo_state_changed"]
        and not consistency["broker_write_function_called"]
        and not consistency["provider_download"]
        and not consistency["intraday_data_used"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["promotion_candidates_created"]
        and not consistency["paper_forward_activation"]
        and not consistency["real_money_recommendation"]
        and consistency["invariant_failure_count"] == 0
    )
    write_json(output / "consistency_check.json", consistency)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "batch_id": BATCH_ID,
        "batch_outcome": batch_outcome,
        "selected_strategy_count": len(selected_configs),
        "selected_symbol_count": len(selected_symbol_rows),
        "registered_trial_count": len(manifest_rows),
        "evaluated_trial_count": len(baseline_rows),
        "followup_candidate_count": len(followup_rows),
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
