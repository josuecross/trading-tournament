from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STARTING_EQUITY = 3000.0
TARGET_300_EQUITY = 3300.0
TARGET_400_EQUITY = 3400.0
STOP_DOLLARS = -600.0
MAX_WINDOWS_PER_HORIZON = 180


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    family: str
    source_file: str
    rule_type: str
    universe: tuple[str, ...]
    rebalance_frequency: str
    documented_rule: str
    benchmark_set: tuple[str, ...]


STRATEGY_SPECS: dict[str, StrategySpec] = {
    "mf_wrapper_top1_trend_v1": StrategySpec("mf_wrapper_top1_trend_v1", "managed_futures_etf_wrapper", "run_managed_futures_etf_wrapper_research_sample.py", "mf_top1_trend", ("DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL"), "monthly", "Pick top eligible managed-futures wrapper by 126-day return above 200-day SMA; otherwise BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "mf_wrapper_top2_risk_adjusted_v1": StrategySpec("mf_wrapper_top2_risk_adjusted_v1", "managed_futures_etf_wrapper", "run_managed_futures_etf_wrapper_research_sample.py", "mf_top2_risk_adjusted", ("DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL"), "monthly", "Pick top two eligible wrappers by 126-day return divided by 60-day volatility; unused slots to BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "mf_wrapper_plus_spy_70_30_v1": StrategySpec("mf_wrapper_plus_spy_70_30_v1", "managed_futures_etf_wrapper", "run_managed_futures_etf_wrapper_research_sample.py", "mf_plus_spy", ("SPY", "DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL"), "monthly", "70% SPY if SPY above 200-day SMA else BIL; 30% top eligible wrapper else BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "mf_wrapper_defensive_cash_switch_v1": StrategySpec("mf_wrapper_defensive_cash_switch_v1", "managed_futures_etf_wrapper", "run_managed_futures_etf_wrapper_research_sample.py", "mf_defensive_cash_switch", ("DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL"), "monthly", "Equal-weight all eligible wrappers when at least two qualify; one qualifier gets 50% with 50% BIL; none gets 100% BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "dm_global_dual_momentum_top1_v1": StrategySpec("dm_global_dual_momentum_top1_v1", "dual_momentum_paa_etf_wrapper", "run_dual_momentum_paa_etf_wrapper_research_sample.py", "dm_global_top1", ("SPY", "EFA", "EEM", "BIL"), "monthly", "Pick top eligible global equity by 126-day return with positive return and 200-day SMA gate; otherwise BIL.", ("SPY_200d", "equal_weight_tactical_basket", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "dm_multi_asset_top2_absolute_momentum_v1": StrategySpec("dm_multi_asset_top2_absolute_momentum_v1", "dual_momentum_paa_etf_wrapper", "run_dual_momentum_paa_etf_wrapper_research_sample.py", "dm_multi_top2", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "Pick top two positive absolute-momentum assets by 126-day return divided by 60-day volatility; unused slots to BIL.", ("SPY_200d", "equal_weight_tactical_basket", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "dm_protective_canary_bil_v1": StrategySpec("dm_protective_canary_bil_v1", "dual_momentum_paa_etf_wrapper", "run_dual_momentum_paa_etf_wrapper_research_sample.py", "dm_canary", ("SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"), "monthly", "If both EFA and EEM fail canary eligibility, hold BIL; otherwise pick two offensive/defensive assets by risk-adjusted momentum.", ("SPY_200d", "equal_weight_tactical_basket", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "dm_balanced_offensive_defensive_v1": StrategySpec("dm_balanced_offensive_defensive_v1", "dual_momentum_paa_etf_wrapper", "run_dual_momentum_paa_etf_wrapper_research_sample.py", "dm_balanced", ("SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"), "monthly", "60% best offensive when SPY above 200-day SMA plus 40% best defensive; otherwise 60% BIL and 40% defensive.", ("SPY_200d", "equal_weight_tactical_basket", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "dm_paa_breadth_protection_v1": StrategySpec("dm_paa_breadth_protection_v1", "dual_momentum_paa_etf_wrapper", "run_dual_momentum_paa_etf_wrapper_research_sample.py", "dm_paa_breadth", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "If fewer than two risky assets are positive and above trend, split defensive/BIL; otherwise pick top two risk-adjusted assets.", ("SPY_200d", "equal_weight_tactical_basket", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "gtaa_top3_trend_filter_v1": StrategySpec("gtaa_top3_trend_filter_v1", "gtaa_faber_style_benchmark_lane", "run_parallel_research_discovery.py", "gtaa_top3", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "Pick top three assets by 126-day return among assets above 200-day SMA; unused slots to BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "gtaa_equal_weight_trend_filter_v1": StrategySpec("gtaa_equal_weight_trend_filter_v1", "gtaa_faber_style_benchmark_lane", "run_parallel_research_discovery.py", "gtaa_equal_weight", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "Equal-weight all assets above 200-day SMA; unused allocation to BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "gtaa_top2_risk_adjusted_v1": StrategySpec("gtaa_top2_risk_adjusted_v1", "gtaa_faber_style_benchmark_lane", "run_parallel_research_discovery.py", "gtaa_top2_risk_adjusted", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "Pick top two assets above 200-day SMA by 126-day return divided by 60-day volatility; unused slots to BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "gtaa_spy_gld_ief_static_trend_v1": StrategySpec("gtaa_spy_gld_ief_static_trend_v1", "gtaa_faber_style_benchmark_lane", "run_parallel_research_discovery.py", "gtaa_static_trend", ("SPY", "GLD", "IEF", "BIL"), "monthly", "Static SPY/GLD/IEF weights with failed trend sleeves routed to BIL.", ("SPY_200d", "SPY_buy_hold", "BIL_cash_proxy")),
    "gtaa_breadth_defensive_v1": StrategySpec("gtaa_breadth_defensive_v1", "gtaa_faber_style_benchmark_lane", "run_parallel_research_discovery.py", "gtaa_breadth", ("SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"), "monthly", "If at least three risk assets are above trend, hold top three; otherwise split defensive leader/BIL.", ("SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy")),
    "vm_quality_lowvol_proxy_v1": StrategySpec("vm_quality_lowvol_proxy_v1", "volatility_managed_equity_etf", "strategy_lab/strategy_registry.yaml", "reference_only", ("USMV", "SPLV", "QUAL", "SPY", "BIL"), "monthly", "Recovered frozen reference row; implementation not rerun by this audit.", ("SPY_200d", "SPY_buy_hold", "BIL_cash_proxy")),
    "dsr_sector_equal_weight_defensive_filter_v1": StrategySpec("dsr_sector_equal_weight_defensive_filter_v1", "defensive_sector_rotation_etf", "strategy_lab/strategy_registry.yaml", "reference_only", ("SPY", "BIL"), "monthly", "Recovered frozen reference row; implementation not rerun by this audit.", ("SPY_200d", "SPY_buy_hold", "BIL_cash_proxy")),
    "gror_balanced_momentum_60_40_v1": StrategySpec("gror_balanced_momentum_60_40_v1", "global_risk_on_risk_off_etf", "run_gror_balanced_momentum_candidate_exhaustive.py", "gror_60_40", ("SPY", "QQQ", "GLD", "IEF", "BIL"), "monthly", "60% best risk-on when SPY above 200-day SMA, otherwise BIL; 40% best defensive above trend, otherwise BIL.", ("active_combo_proxy", "SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "GLD_buy_hold", "BIL_cash_proxy")),
}


def prepare_indicators(close: pd.DataFrame) -> dict[str, Any]:
    ordered = close.astype(float).sort_index()
    returns = ordered.pct_change().fillna(0.0)
    return {
        "close": ordered,
        "sma200": ordered.rolling(200).mean(),
        "above200": ordered > ordered.rolling(200).mean(),
        "ret126": ordered / ordered.shift(126) - 1.0,
        "ret63": ordered / ordered.shift(63) - 1.0,
        "returns": returns,
        "vol60": returns.rolling(60).std().replace(0, np.nan),
    }


def is_eligible(indicators: dict[str, Any], date: pd.Timestamp, symbol: str, require_positive_return: bool = False) -> bool:
    if symbol not in indicators["close"].columns or date not in indicators["close"].index:
        return False
    above = bool(indicators["above200"].at[date, symbol])
    if not above:
        return False
    if require_positive_return:
        value = indicators["ret126"].at[date, symbol]
        return bool(pd.notna(value) and value > 0)
    return True


def rank_assets(
    indicators: dict[str, Any],
    date: pd.Timestamp,
    assets: list[str],
    risk_adjusted: bool = False,
    require_positive_return: bool = False,
) -> list[tuple[str, float]]:
    ranked: list[tuple[str, float]] = []
    for symbol in assets:
        if symbol == "BIL" or not is_eligible(indicators, date, symbol, require_positive_return=require_positive_return):
            continue
        score = indicators["ret126"].at[date, symbol]
        if pd.isna(score):
            continue
        if risk_adjusted:
            vol = indicators["vol60"].at[date, symbol]
            score = score / vol if pd.notna(vol) and vol > 0 else -1e9
        ranked.append((symbol, float(score)))
    return sorted(ranked, key=lambda item: item[1], reverse=True)


def normalize_with_bil(weights: dict[str, float]) -> dict[str, float]:
    cleaned = {symbol: float(weight) for symbol, weight in weights.items() if abs(float(weight)) > 1e-12}
    total = sum(cleaned.values())
    if total < 1.0 - 1e-9:
        cleaned["BIL"] = cleaned.get("BIL", 0.0) + (1.0 - total)
    elif total > 1.0 + 1e-9:
        cleaned = {symbol: weight / total for symbol, weight in cleaned.items()}
    return cleaned or {"BIL": 1.0}


def monthly_rebalance_mask(dates: pd.DatetimeIndex) -> pd.Series:
    months = pd.Series([date.year * 12 + date.month for date in dates], index=dates)
    return months.ne(months.shift(1)).fillna(True)


def sample_starts(length: int, horizon: int, max_windows: int = MAX_WINDOWS_PER_HORIZON) -> list[int]:
    starts = list(range(252, length - horizon))
    if len(starts) <= max_windows:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], max_windows)))


def evaluate_equity_curve(equity: list[float] | pd.Series) -> dict[str, Any]:
    series = pd.Series(equity, dtype=float).reset_index(drop=True)
    peak = series.cummax()
    drawdown = series - peak
    stop_level = STARTING_EQUITY + STOP_DOLLARS
    stop_hits = series[series <= stop_level]
    target300_hits = series[series >= TARGET_300_EQUITY]
    target400_hits = series[series >= TARGET_400_EQUITY]
    stop_idx = None if stop_hits.empty else int(stop_hits.index[0])
    target300_idx = None if target300_hits.empty else int(target300_hits.index[0])
    target400_idx = None if target400_hits.empty else int(target400_hits.index[0])
    return {
        "max_drawdown": float(drawdown.min()),
        "stop_hit": stop_idx is not None,
        "target_300_before_stop": target300_idx is not None and (stop_idx is None or target300_idx <= stop_idx),
        "target_400_before_stop": target400_idx is not None and (stop_idx is None or target400_idx <= stop_idx),
        "target_300_after_stop": target300_idx is not None and stop_idx is not None and target300_idx > stop_idx,
        "target_400_after_stop": target400_idx is not None and stop_idx is not None and target400_idx > stop_idx,
    }


def benchmark_delta(strategy_values: list[float], benchmark_values: list[float] | None) -> dict[str, Any]:
    if benchmark_values is None:
        return {"comparison_status": "unavailable", "delta_median_final_equity": ""}
    strategy = pd.Series(strategy_values, dtype=float)
    benchmark = pd.Series(benchmark_values, dtype=float)
    if strategy.empty or benchmark.empty:
        return {"comparison_status": "unavailable", "delta_median_final_equity": ""}
    return {
        "comparison_status": "available",
        "delta_median_final_equity": float(strategy.median() - benchmark.median()),
    }


def promotion_verdict(metrics: dict[str, Any]) -> str:
    required = ["score", "target_300_rate", "stop_hit_rate", "worst_drawdown", "benchmark_delta_status"]
    if any(metrics.get(key) in {None, "", "unavailable"} for key in required):
        return "watchlist"
    if float(metrics["stop_hit_rate"]) > 0 or float(metrics["worst_drawdown"]) <= STOP_DOLLARS:
        return "too_risky"
    if float(metrics["score"]) >= 70 and float(metrics["target_300_rate"]) >= 0.25:
        return "promotion_review_candidate"
    return "watchlist"


def load_cached_close(root: Path, symbols: list[str]) -> pd.DataFrame:
    series = []
    for symbol in symbols:
        path = root / "data" / "cache" / f"{symbol}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if "date" not in frame or "adj_close" not in frame:
            continue
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        one = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
        if not one.empty:
            series.append(one.set_index("date")[symbol].astype(float))
    return pd.concat(series, axis=1, join="inner").dropna().sort_index() if series else pd.DataFrame()
