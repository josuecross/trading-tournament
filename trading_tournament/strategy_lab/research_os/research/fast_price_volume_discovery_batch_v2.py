from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import equity_from_returns, returns_from_weights


BATCH_ID = "fast_price_volume_discovery_batch_v2"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
FROZEN_PREREGISTRATION_TIMESTAMP = "2026-07-23T00:00:00+00:00"
PROJECT_STANDARD_COST_BPS_PER_TURNOVER = 5.0
COST_RATE = PROJECT_STANDARD_COST_BPS_PER_TURNOVER / 10000.0
WEIGHT_TOLERANCE = 1e-6
MAX_FAMILIES = 8
MIN_OBSERVATIONS = 504

NEXT_ACTION_WITH_CANDIDATES = "direction_owner_review_fast_price_volume_discovery_batch_v2_candidates"
NEXT_ACTION_ZERO_CANDIDATES = "refresh_source_library_after_zero_candidate_fast_batch_v2"

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]

INPUT_EVIDENCE_PATHS = [
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "tournament_funnel_counts.json",
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "exact_strategy_inventory.csv",
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "family_inventory.csv",
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "recent_fast_lane_results.csv",
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "closed_and_deferred_inventory.csv",
    ROOT
    / "evidence"
    / "tournament_status"
    / "tournament_strategy_readiness_inventory_v1"
    / "latest"
    / "missing_or_conflicting_evidence.csv",
]

LOCAL_QUEUE_PATHS = [
    ROOT / "evidence" / "strategy_candidate_queue" / "latest" / "candidate_queue_matrix.csv",
    ROOT / "evidence" / "strategy_candidate_queue" / "latest" / "strategy_candidate_queue.yaml",
    ROOT / "strategy_lab" / "parallel_research_discovery_queue.yaml",
    ROOT / "strategy_lab" / "approved_etf_symbol_map.yaml",
]


@dataclass(frozen=True)
class StrategyCard:
    family_id: str
    strategy_id: str
    display_name: str
    strategy_architecture: str
    source_or_research_lineage: str
    economic_or_behavioral_rationale: str
    complete_canonical_rule: str
    parameters: dict[str, Any]
    instrument_universe: tuple[str, ...]
    risky_universe: tuple[str, ...]
    evaluation_start: str
    evaluation_end: str
    primary_benchmark_control: str
    static_control: str
    transaction_cost_assumption: str
    objective_route: str
    trial_id: str
    parent_trial_id: str
    changed_fields_from_parent: str
    preregistration_timestamp: str


SELECTED_CARDS = [
    StrategyCard(
        family_id="dual_momentum",
        strategy_id="qqq_spy_gld_ief_dual_momentum_v1",
        display_name="QQQ/SPY/GLD/IEF Dual Momentum",
        strategy_architecture="monthly_relative_momentum_plus_absolute_trend_long_cash_rotation",
        source_or_research_lineage=(
            "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv:"
            "qqq_spy_gld_ief_dual_momentum_v1"
        ),
        economic_or_behavioral_rationale=(
            "Local queue item: growth, broad equity, gold and Treasury sleeves may show persistent relative momentum "
            "while an absolute trend gate prevents holding below-trend sleeves."
        ),
        complete_canonical_rule=(
            "At each first common trading session of a calendar month, using only prices available through the prior "
            "completed close, compute 126-trading-day total return and a 200-day SMA for QQQ, SPY, GLD and IEF. "
            "Eligible assets must have positive trailing return and prior close above their 200-day SMA. Allocate "
            "100% to the eligible asset with highest trailing return; allocate 100% to BIL when no asset is eligible. "
            "Hold until the next monthly rebalance. Target weights are applied with the repository one-bar shifted "
            "return convention."
        ),
        parameters={
            "lookback_trading_days": 126,
            "absolute_trend_sma_days": 200,
            "rebalance_frequency": "monthly_first_common_trading_session",
            "top_n": 1,
            "cash_proxy": "BIL",
        },
        instrument_universe=("QQQ", "SPY", "GLD", "IEF", "BIL"),
        risky_universe=("QQQ", "SPY", "GLD", "IEF"),
        evaluation_start="common_cache_after_200d_warmup",
        evaluation_end="latest_common_cache_date",
        primary_benchmark_control="combo_SPY200d_GLD_50_50_v1_recomputed_control",
        static_control="static_equal_weight_QQQ_SPY_GLD_IEF",
        transaction_cost_assumption="5 bps per one-way turnover proxy",
        objective_route="standalone_or_diversifier",
        trial_id="fast_pv_v2__qqq_spy_gld_ief_dual_momentum_v1__canonical",
        parent_trial_id="",
        changed_fields_from_parent="canonical_configuration",
        preregistration_timestamp=FROZEN_PREREGISTRATION_TIMESTAMP,
    ),
    StrategyCard(
        family_id="bond_trend_rotation",
        strategy_id="treasury_duration_trend_rotation_v1",
        display_name="Treasury Duration Trend Rotation",
        strategy_architecture="monthly_duration_relative_momentum_plus_absolute_trend_long_cash_rotation",
        source_or_research_lineage=(
            "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv:"
            "treasury_duration_trend_rotation_v1"
        ),
        economic_or_behavioral_rationale=(
            "Local queue item: Treasury duration sleeves may trend across rate regimes; a fixed duration universe can "
            "test defensive adaptation without macro data, leverage, futures or shorting."
        ),
        complete_canonical_rule=(
            "At each first common trading session of a calendar month, using only prices available through the prior "
            "completed close, compute 126-trading-day total return and a 200-day SMA for SHY, IEF and TLT. Eligible "
            "assets must have positive trailing return and prior close above their 200-day SMA. Allocate 100% to the "
            "eligible asset with highest trailing return; allocate 100% to BIL when no asset is eligible. Hold until "
            "the next monthly rebalance. Target weights are applied with the repository one-bar shifted return convention."
        ),
        parameters={
            "lookback_trading_days": 126,
            "absolute_trend_sma_days": 200,
            "rebalance_frequency": "monthly_first_common_trading_session",
            "top_n": 1,
            "cash_proxy": "BIL",
        },
        instrument_universe=("SHY", "IEF", "TLT", "BIL"),
        risky_universe=("SHY", "IEF", "TLT"),
        evaluation_start="common_cache_after_200d_warmup",
        evaluation_end="latest_common_cache_date",
        primary_benchmark_control="IEF_buy_hold",
        static_control="static_equal_weight_SHY_IEF_TLT",
        transaction_cost_assumption="5 bps per one-way turnover proxy",
        objective_route="diversifier",
        trial_id="fast_pv_v2__treasury_duration_trend_rotation_v1__canonical",
        parent_trial_id="",
        changed_fields_from_parent="canonical_configuration",
        preregistration_timestamp=FROZEN_PREREGISTRATION_TIMESTAMP,
    ),
]

QUEUE_EXCLUSION_REASONS = {
    "value_momentum_factor_etf_rotation_v1": "excluded_duplicate_or_near_duplicate_registry_status_or_prior_research_sample",
    "low_vol_quality_defensive_rotation_v1": "excluded_near_duplicate_active_vm_or_prior_low_beta_research_sample",
    "sector_top2_momentum_simple_v1": "excluded_near_duplicate_sector_momentum_prior_evidence",
    "managed_futures_proxy_etf_trend_v1": "excluded_futures_or_managed_futures_wrapper_family",
    "commodity_basket_etf_momentum_v1": "excluded_recently_tested_commodity_family",
    "crypto_spot_tsmom_tier2_review_v1": "excluded_crypto",
    "individual_stock_momentum_gate1b_v1": "excluded_individual_stock_and_survivorship_data_required",
    "options_futures_forex_intraday_blocked_reference_v1": "excluded_options_futures_forex_intraday_blocked_reference",
}

PARALLEL_QUEUE_EXCLUSION_REASONS = {
    "gtaa_faber_style_benchmark_lane": "excluded_recent_fast_lane_or_global_tactical_duplicate",
    "static_all_weather_or_permanent_portfolio_benchmark": "excluded_benchmark_or_reference_only",
    "low_beta_defensive_equity_etf": "excluded_near_duplicate_active_vm_or_prior_low_beta_research_sample",
    "dividend_quality_yield_etf": "excluded_previously_tested_research_sample",
    "carry_yield_etf_proxy": "excluded_previously_tested_research_sample",
}


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def data_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_adjusted_ohlcv(symbol: str) -> pd.DataFrame:
    path = ROOT / DATA_CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    if not required.issubset(raw.columns):
        return pd.DataFrame()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = raw.dropna(subset=["date"]).sort_values("date")
    raw = raw.drop_duplicates(subset=["date"], keep="last").set_index("date")
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw = raw[["open", "high", "low", "close", "adj_close", "volume"]].dropna()
    raw = raw.loc[(raw[["open", "high", "low", "close", "adj_close"]] > 0.0).all(axis=1)]
    raw = raw.loc[raw["volume"] >= 0.0]
    raw.attrs["cache_path"] = rel(path)
    raw.attrs["cache_hash"] = file_hash(path)
    return raw


def load_price_frame(symbols: tuple[str, ...]) -> pd.DataFrame:
    series = []
    for symbol in symbols:
        frame = load_adjusted_ohlcv(symbol)
        if frame.empty:
            return pd.DataFrame()
        series.append(frame["adj_close"].rename(symbol))
    return pd.concat(series, axis=1, join="inner").dropna().sort_index()


def monthly_first_mask(index: pd.DatetimeIndex) -> pd.Series:
    periods = pd.Series(index.to_period("M"), index=index)
    return periods.ne(periods.shift(1)).fillna(True)


def build_rotation_weights(prices: pd.DataFrame, risky: tuple[str, ...], cash: str, lookback: int, sma_days: int) -> pd.DataFrame:
    columns = list(risky) + [cash]
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    if prices.empty:
        return weights
    prior = prices[list(risky)].shift(1)
    trailing = prior / prior.shift(lookback) - 1.0
    sma = prior.rolling(sma_days, min_periods=sma_days).mean()
    targets: dict[pd.Timestamp, str] = {}
    for date in prices.index[monthly_first_mask(prices.index)]:
        score = trailing.loc[date].dropna()
        if score.empty:
            selected = cash
        else:
            eligible = []
            for symbol in risky:
                if symbol not in score.index:
                    continue
                is_eligible = (
                    math.isfinite(float(score[symbol]))
                    and float(score[symbol]) > 0.0
                    and pd.notna(prior.loc[date, symbol])
                    and pd.notna(sma.loc[date, symbol])
                    and float(prior.loc[date, symbol]) > float(sma.loc[date, symbol])
                )
                if is_eligible:
                    eligible.append(symbol)
            selected = max(eligible, key=lambda symbol: float(score[symbol])) if eligible else cash
        targets[pd.Timestamp(date)] = selected
    current = cash
    for date in prices.index:
        if date in targets:
            current = targets[pd.Timestamp(date)]
        weights.loc[date, current] = 1.0
    return weights


def turnover_series(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float, name="turnover")
    diff = weights.diff().abs().fillna(weights.abs())
    return (diff.sum(axis=1) / 2.0).rename("turnover")


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def metrics_from_returns(returns: pd.Series) -> dict[str, Any]:
    daily = returns.dropna().astype(float)
    if daily.empty:
        return {
            "evaluation_start": "",
            "evaluation_end": "",
            "trading_days": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "sharpe_ratio": float("nan"),
            "maximum_drawdown": float("nan"),
        }
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(daily.std(ddof=0) * np.sqrt(252.0))
    sharpe = float((daily.mean() * 252.0) / volatility) if volatility > 0.0 else float("nan")
    return {
        "evaluation_start": daily.index.min().date().isoformat(),
        "evaluation_end": daily.index.max().date().isoformat(),
        "trading_days": int(len(daily)),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "maximum_drawdown": max_drawdown(equity),
    }


def total_return(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    return float((1.0 + returns.fillna(0.0)).prod() - 1.0)


def split_half_results(candidate: pd.Series, control: pd.Series) -> dict[str, Any]:
    aligned = pd.concat([candidate.rename("candidate"), control.rename("control")], axis=1).dropna()
    if len(aligned) < 60:
        return {
            "first_half_start": "",
            "first_half_end": "",
            "second_half_start": "",
            "second_half_end": "",
            "first_half_total_return": float("nan"),
            "second_half_total_return": float("nan"),
            "first_half_primary_control_return": float("nan"),
            "second_half_primary_control_return": float("nan"),
            "first_half_excess_vs_primary_control": float("nan"),
            "second_half_excess_vs_primary_control": float("nan"),
            "both_halves_negative_excess": False,
        }
    midpoint = len(aligned) // 2
    first = aligned.iloc[:midpoint]
    second = aligned.iloc[midpoint:]
    first_candidate = total_return(first["candidate"])
    first_control = total_return(first["control"])
    second_candidate = total_return(second["candidate"])
    second_control = total_return(second["control"])
    return {
        "first_half_start": first.index.min().date().isoformat(),
        "first_half_end": first.index.max().date().isoformat(),
        "second_half_start": second.index.min().date().isoformat(),
        "second_half_end": second.index.max().date().isoformat(),
        "first_half_total_return": first_candidate,
        "second_half_total_return": second_candidate,
        "first_half_primary_control_return": first_control,
        "second_half_primary_control_return": second_control,
        "first_half_excess_vs_primary_control": first_candidate - first_control,
        "second_half_excess_vs_primary_control": second_candidate - second_control,
        "both_halves_negative_excess": (first_candidate - first_control) < 0.0
        and (second_candidate - second_control) < 0.0,
    }


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 30:
        return float("nan")
    left_std = float(aligned["left"].std(ddof=0))
    right_std = float(aligned["right"].std(ddof=0))
    if left_std <= 0.0 or right_std <= 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def invariant_summary(weights: pd.DataFrame) -> dict[str, Any]:
    if weights.empty:
        return {
            "max_daily_exposure": float("nan"),
            "max_daily_weight_sum": float("nan"),
            "nan_weight_count": 0,
            "negative_weight_violation_count": 0,
            "weight_sum_violation_count": 0,
            "exposure_invariant_pass": False,
        }
    risky = weights.drop(columns=["BIL"], errors="ignore")
    max_exposure = float(risky.clip(lower=0.0).sum(axis=1).max()) if not risky.empty else 0.0
    max_weight_sum = float(weights.sum(axis=1).max())
    nan_count = int(weights.isna().sum().sum())
    negative_count = int((weights < -WEIGHT_TOLERANCE).sum().sum())
    weight_sum_count = int((weights.sum(axis=1) > 1.0 + WEIGHT_TOLERANCE).sum())
    return {
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "nan_weight_count": nan_count,
        "negative_weight_violation_count": negative_count,
        "weight_sum_violation_count": weight_sum_count,
        "exposure_invariant_pass": bool(
            max_exposure <= 1.0 + WEIGHT_TOLERANCE
            and max_weight_sum <= 1.0 + WEIGHT_TOLERANCE
            and nan_count == 0
            and negative_count == 0
            and weight_sum_count == 0
        ),
    }


def spy200d_returns(common_index: pd.DatetimeIndex) -> pd.Series:
    prices = load_price_frame(("SPY", "BIL")).reindex(common_index).dropna()
    prior_spy = prices["SPY"].shift(1)
    sma = prices["SPY"].shift(1).rolling(200, min_periods=200).mean()
    risk_on = prior_spy > sma
    weights = pd.DataFrame(0.0, index=prices.index, columns=["SPY", "BIL"])
    weights.loc[risk_on.fillna(False), "SPY"] = 1.0
    weights.loc[~risk_on.fillna(False), "BIL"] = 1.0
    return returns_from_weights(prices, weights).rename("SPY_200d_trend_model")


def combo_spy200d_gld_returns(common_index: pd.DatetimeIndex) -> pd.Series:
    prices = load_price_frame(("SPY", "BIL", "GLD")).reindex(common_index).dropna()
    spy200d = spy200d_returns(prices.index)
    gld = prices["GLD"].pct_change(fill_method=None).fillna(0.0)
    return (0.5 * spy200d.reindex(prices.index).fillna(0.0) + 0.5 * gld).rename(
        "combo_SPY200d_GLD_50_50_v1_recomputed_control"
    )


def active_vm_dsr_usci_reference_returns() -> pd.Series:
    combo_path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    combo = read_csv_rows(combo_path)
    if not combo:
        return pd.Series(dtype=float, name="active_vm_dsr_usci_equal_weight_reference")
    combo_df = pd.DataFrame(combo)
    combo_df["date"] = pd.to_datetime(combo_df["date"], errors="coerce")
    combo_df = combo_df.dropna(subset=["date"]).set_index("date").sort_index()
    vm = pd.to_numeric(combo_df["vm_standalone_equity"], errors="coerce").pct_change(fill_method=None).fillna(0.0)
    dsr = pd.to_numeric(combo_df["dsr_standalone_equity"], errors="coerce").pct_change(fill_method=None).fillna(0.0)
    usci_prices = load_price_frame(("USCI",))
    usci = usci_prices["USCI"].pct_change(fill_method=None).fillna(0.0)
    aligned = pd.concat([vm.rename("vm"), dsr.rename("dsr"), usci.rename("usci")], axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.Series(dtype=float, name="active_vm_dsr_usci_equal_weight_reference")
    return aligned.mean(axis=1).rename("active_vm_dsr_usci_equal_weight_reference")


def static_control_returns(card: StrategyCard, common_index: pd.DatetimeIndex) -> pd.Series:
    prices = load_price_frame(card.risky_universe).reindex(common_index).dropna()
    if prices.empty:
        return pd.Series(dtype=float, name=card.static_control)
    weights = pd.DataFrame(1.0 / len(card.risky_universe), index=prices.index, columns=list(card.risky_universe))
    return returns_from_weights(prices, weights).rename(card.static_control)


def primary_control_returns(card: StrategyCard, common_index: pd.DatetimeIndex) -> pd.Series:
    if card.primary_benchmark_control == "combo_SPY200d_GLD_50_50_v1_recomputed_control":
        return combo_spy200d_gld_returns(common_index)
    if card.primary_benchmark_control == "IEF_buy_hold":
        prices = load_price_frame(("IEF",)).reindex(common_index).dropna()
        return prices["IEF"].pct_change(fill_method=None).fillna(0.0).rename("IEF_buy_hold")
    raise ValueError(f"Unsupported primary control: {card.primary_benchmark_control}")


def evaluated_common_prices(card: StrategyCard, reference_returns: pd.Series) -> pd.DataFrame:
    prices = load_price_frame(card.instrument_universe)
    if prices.empty or reference_returns.empty:
        return pd.DataFrame()
    prices = prices.join(reference_returns.rename("reference_return"), how="inner").dropna()
    if len(prices) <= 252:
        return pd.DataFrame()
    # Drop the indicator warm-up period before scoring. Signals themselves also use prior data.
    return prices.iloc[252:].copy()


def evaluate_card(card: StrategyCard, reference_returns: pd.Series) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], pd.Series]:
    common_prices = evaluated_common_prices(card, reference_returns)
    if common_prices.empty or len(common_prices) < MIN_OBSERVATIONS:
        issue = {
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "trial_id": card.trial_id,
            "issue_type": "data_blocked_configuration",
            "issue": "insufficient_common_adjusted_ohlcv_or_reference_history",
            "blocking": True,
            "source": card.source_or_research_lineage,
        }
        result = base_trial_result(card, "inconclusive_data_issue", issue["issue"])
        lineage = trial_lineage_row(card)
        return result, lineage, issue, pd.Series(dtype=float, name=card.trial_id)

    price_cols = list(card.instrument_universe)
    prices = common_prices[price_cols].dropna()
    reference = common_prices["reference_return"].reindex(prices.index).fillna(0.0)
    weights = build_rotation_weights(
        prices,
        card.risky_universe,
        "BIL",
        int(card.parameters["lookback_trading_days"]),
        int(card.parameters["absolute_trend_sma_days"]),
    ).reindex(prices.index).fillna(0.0)
    gross_returns = returns_from_weights(prices, weights).rename("gross_candidate_return")
    turnover = turnover_series(weights).reindex(gross_returns.index).fillna(0.0)
    cost = turnover * COST_RATE
    candidate = (gross_returns - cost).rename(card.trial_id)
    primary = primary_control_returns(card, prices.index).reindex(candidate.index).fillna(0.0)
    static = static_control_returns(card, prices.index).reindex(candidate.index).fillna(0.0)
    reference = reference.reindex(candidate.index).fillna(0.0)

    candidate_metrics = metrics_from_returns(candidate)
    primary_metrics = metrics_from_returns(primary)
    static_metrics = metrics_from_returns(static)
    reference_metrics = metrics_from_returns(reference)
    combined_returns = (0.8 * reference + 0.2 * candidate).rename(f"{card.trial_id}_20pct_sleeve")
    combined_metrics = metrics_from_returns(combined_returns)
    halves = split_half_results(candidate, primary)
    invariants = invariant_summary(weights)
    total_turnover = float(turnover.sum())
    trade_or_rebalance_count = int((turnover > WEIGHT_TOLERANCE).sum())
    estimated_cost = float(cost.sum())
    standalone_pass = (
        candidate_metrics["total_return"] > primary_metrics["total_return"]
        and not bool(halves["both_halves_negative_excess"])
        and bool(invariants["exposure_invariant_pass"])
    )
    sharpe_improved = combined_metrics["sharpe_ratio"] > reference_metrics["sharpe_ratio"]
    drawdown_improved = combined_metrics["maximum_drawdown"] > reference_metrics["maximum_drawdown"]
    both_worse = (
        combined_metrics["sharpe_ratio"] < reference_metrics["sharpe_ratio"]
        and combined_metrics["maximum_drawdown"] < reference_metrics["maximum_drawdown"]
    )
    diversifier_pass = (
        candidate_metrics["total_return"] > 0.0
        and (sharpe_improved or drawdown_improved)
        and not both_worse
        and bool(invariants["exposure_invariant_pass"])
    )
    if standalone_pass:
        classification = "exploratory_followup_candidate_standalone"
        failure_reason = ""
    elif diversifier_pass:
        classification = "exploratory_followup_candidate_diversifier"
        failure_reason = ""
    else:
        classification = "closed_exploration"
        failure_reason = "failed_standalone_and_diversifier_lightweight_exploration_gates"

    result = {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "display_name": card.display_name,
        "classification": classification,
        "failure_reason": failure_reason,
        "evaluation_start": candidate_metrics["evaluation_start"],
        "evaluation_end": candidate_metrics["evaluation_end"],
        "trading_days": candidate_metrics["trading_days"],
        "total_return": candidate_metrics["total_return"],
        "cagr": candidate_metrics["cagr"],
        "annualized_volatility": candidate_metrics["annualized_volatility"],
        "sharpe_ratio": candidate_metrics["sharpe_ratio"],
        "maximum_drawdown": candidate_metrics["maximum_drawdown"],
        "turnover": total_turnover,
        "trade_or_rebalance_count": trade_or_rebalance_count,
        "transaction_cost_assumption_bps": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "estimated_cost_return_drag": estimated_cost,
        "primary_control_id": card.primary_benchmark_control,
        "primary_control_total_return": primary_metrics["total_return"],
        "primary_control_cagr": primary_metrics["cagr"],
        "primary_control_sharpe_ratio": primary_metrics["sharpe_ratio"],
        "primary_control_maximum_drawdown": primary_metrics["maximum_drawdown"],
        "delta_total_return_vs_primary_control": candidate_metrics["total_return"] - primary_metrics["total_return"],
        "delta_sharpe_vs_primary_control": candidate_metrics["sharpe_ratio"] - primary_metrics["sharpe_ratio"],
        "delta_max_drawdown_vs_primary_control": candidate_metrics["maximum_drawdown"]
        - primary_metrics["maximum_drawdown"],
        "static_control_id": card.static_control,
        "static_control_total_return": static_metrics["total_return"],
        "static_control_cagr": static_metrics["cagr"],
        "static_control_sharpe_ratio": static_metrics["sharpe_ratio"],
        "static_control_maximum_drawdown": static_metrics["maximum_drawdown"],
        "delta_total_return_vs_static_control": candidate_metrics["total_return"] - static_metrics["total_return"],
        "delta_sharpe_vs_static_control": candidate_metrics["sharpe_ratio"] - static_metrics["sharpe_ratio"],
        "delta_max_drawdown_vs_static_control": candidate_metrics["maximum_drawdown"] - static_metrics["maximum_drawdown"],
        **halves,
        "correlation_to_frozen_current_active_vm_dsr_usci_combo": safe_corr(candidate, reference),
        "reference_combo_total_return": reference_metrics["total_return"],
        "reference_combo_sharpe_ratio": reference_metrics["sharpe_ratio"],
        "reference_combo_maximum_drawdown": reference_metrics["maximum_drawdown"],
        "fixed_20pct_sleeve_total_return": combined_metrics["total_return"],
        "fixed_20pct_sleeve_sharpe_ratio": combined_metrics["sharpe_ratio"],
        "fixed_20pct_sleeve_maximum_drawdown": combined_metrics["maximum_drawdown"],
        "fixed_20pct_sleeve_improves_sharpe": sharpe_improved,
        "fixed_20pct_sleeve_improves_max_drawdown": drawdown_improved,
        "fixed_20pct_sleeve_worsens_both": both_worse,
        "standalone_gate_pass": standalone_pass,
        "diversifier_gate_pass": diversifier_pass,
        "max_daily_exposure": invariants["max_daily_exposure"],
        "max_daily_weight_sum": invariants["max_daily_weight_sum"],
        "exposure_invariant_pass": invariants["exposure_invariant_pass"],
        "numeric_result_interpretable": True,
        "promotion_review": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive": False,
        "real_money_action": False,
        "supporting_strategy_card_source": "preregistered_strategy_cards.csv",
    }
    return result, trial_lineage_row(card), {}, candidate


def base_trial_result(card: StrategyCard, classification: str, failure_reason: str) -> dict[str, Any]:
    return {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "display_name": card.display_name,
        "classification": classification,
        "failure_reason": failure_reason,
        "evaluation_start": "",
        "evaluation_end": "",
        "trading_days": 0,
        "total_return": "",
        "cagr": "",
        "annualized_volatility": "",
        "sharpe_ratio": "",
        "maximum_drawdown": "",
        "turnover": "",
        "trade_or_rebalance_count": "",
        "transaction_cost_assumption_bps": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "estimated_cost_return_drag": "",
        "primary_control_id": card.primary_benchmark_control,
        "static_control_id": card.static_control,
        "numeric_result_interpretable": False,
        "promotion_review": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive": False,
        "real_money_action": False,
    }


def trial_lineage_row(card: StrategyCard) -> dict[str, Any]:
    return {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "parent_trial_id": card.parent_trial_id,
        "changed_fields_from_parent": card.changed_fields_from_parent,
        "task_or_process_record": False,
        "predeclared_before_results": True,
        "source_or_research_lineage": card.source_or_research_lineage,
    }


def card_to_row(card: StrategyCard) -> dict[str, Any]:
    return {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "display_name": card.display_name,
        "strategy_architecture": card.strategy_architecture,
        "source_or_research_lineage": card.source_or_research_lineage,
        "economic_or_behavioral_rationale": card.economic_or_behavioral_rationale,
        "complete_canonical_rule": card.complete_canonical_rule,
        "parameters": card.parameters,
        "instrument_universe": card.instrument_universe,
        "evaluation_start": card.evaluation_start,
        "evaluation_end": card.evaluation_end,
        "primary_benchmark_control": card.primary_benchmark_control,
        "static_control": card.static_control,
        "transaction_cost_assumption": card.transaction_cost_assumption,
        "objective_route": card.objective_route,
        "trial_id": card.trial_id,
        "parent_trial_id": card.parent_trial_id,
        "changed_fields_from_parent": card.changed_fields_from_parent,
        "preregistration_timestamp": card.preregistration_timestamp,
        "task_or_process_record": False,
    }


def build_rejection_log(
    exact_inventory: list[dict[str, str]],
    recent_fast: list[dict[str, str]],
    closed_deferred: list[dict[str, str]],
) -> list[dict[str, Any]]:
    selected_ids = {card.strategy_id for card in SELECTED_CARDS}
    selected_families = {card.family_id for card in SELECTED_CARDS}
    exact_by_id = {row.get("strategy_id", ""): row for row in exact_inventory}
    recent_family_ids = {row.get("family_id", "") for row in recent_fast}
    active_families = {
        row.get("family_id", "")
        for row in exact_inventory
        if row.get("paper_demo_eligible") == "true" or row.get("paper_demo_active") == "true"
    }
    closed_ids = {row.get("strategy_id", "") for row in closed_deferred}
    rows: list[dict[str, Any]] = []
    matrix = read_csv_rows(ROOT / "evidence" / "strategy_candidate_queue" / "latest" / "candidate_queue_matrix.csv")
    for row in matrix:
        strategy_id = row.get("candidate_id", "")
        family_id = row.get("strategy_family", "")
        if strategy_id in selected_ids:
            reason = "selected"
            eligible = True
        elif strategy_id in QUEUE_EXCLUSION_REASONS:
            reason = QUEUE_EXCLUSION_REASONS[strategy_id]
            eligible = False
        elif family_id in recent_family_ids:
            reason = "excluded_recent_fast_lane_family"
            eligible = False
        elif family_id in active_families:
            reason = "excluded_current_paper_demo_active_or_eligible_family"
            eligible = False
        elif strategy_id in closed_ids or exact_by_id.get(strategy_id, {}).get("trial_count", "0") not in {"", "0"}:
            reason = "excluded_previously_tested_or_closed_configuration"
            eligible = False
        elif parse_bool(row.get("uses_shorting")) or parse_bool(row.get("uses_leverage")) or parse_bool(row.get("uses_margin")):
            reason = "excluded_forbidden_exposure_mechanic"
            eligible = False
        elif str(row.get("instrument_family", "")).lower() in {"crypto_spot", "individual_stocks"}:
            reason = "excluded_forbidden_instrument_family"
            eligible = False
        else:
            reason = "not_selected_due_batch_cap_or_incomplete_local_rule_after_filters"
            eligible = False
        rows.append(
            {
                "strategy_id": strategy_id,
                "family_id": family_id,
                "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
                "eligible_for_this_batch": eligible,
                "rejection_or_status": reason,
                "data_issue": "",
                "blocking": not eligible,
            }
        )
    parallel = read_yaml(ROOT / "strategy_lab" / "parallel_research_discovery_queue.yaml").get("families", [])
    for row in parallel:
        family_id = row.get("family_id", "")
        if family_id in selected_families:
            continue
        rows.append(
            {
                "strategy_id": "",
                "family_id": family_id,
                "source": "strategy_lab/parallel_research_discovery_queue.yaml",
                "eligible_for_this_batch": False,
                "rejection_or_status": PARALLEL_QUEUE_EXCLUSION_REASONS.get(
                    family_id, "excluded_not_not_previously_tested_or_not_clean_price_volume_family"
                ),
                "data_issue": "",
                "blocking": True,
            }
        )
    return sorted(rows, key=lambda row: (str(row["eligible_for_this_batch"]), str(row["family_id"]), str(row["strategy_id"])))


def family_summary_rows(all_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_family: dict[str, list[dict[str, Any]]] = {}
    for result in all_results:
        by_family.setdefault(str(result["family_id"]), []).append(result)
    for family_id, results in sorted(by_family.items()):
        candidate_count = sum(
            row["classification"]
            in {
                "exploratory_followup_candidate_standalone",
                "exploratory_followup_candidate_diversifier",
            }
            for row in results
        )
        rows.append(
            {
                "family_id": family_id,
                "strategy_count": len({row["strategy_id"] for row in results}),
                "trial_count": len(results),
                "completed_trial_count": sum(row.get("numeric_result_interpretable") is True for row in results),
                "data_blocked_trial_count": sum(row["classification"] == "inconclusive_data_issue" for row in results),
                "standalone_followup_candidate_count": sum(
                    row["classification"] == "exploratory_followup_candidate_standalone" for row in results
                ),
                "diversifier_followup_candidate_count": sum(
                    row["classification"] == "exploratory_followup_candidate_diversifier" for row in results
                ),
                "closed_exploration_count": sum(row["classification"] == "closed_exploration" for row in results),
                "family_outcome": "exploratory_followup_candidate" if candidate_count else "closed_exploration",
                "best_total_return": max((parse_float(row.get("total_return")) for row in results), default=float("nan")),
                "best_sharpe_ratio": max((parse_float(row.get("sharpe_ratio")) for row in results), default=float("nan")),
            }
        )
    return rows


def cohort_funnel_counts(
    cards: list[StrategyCard],
    all_results: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    standalone = sum(row["classification"] == "exploratory_followup_candidate_standalone" for row in all_results)
    diversifier = sum(row["classification"] == "exploratory_followup_candidate_diversifier" for row in all_results)
    closed = sum(row["classification"] == "closed_exploration" for row in all_results)
    data_blocked = sum(row["classification"] == "inconclusive_data_issue" for row in all_results)
    completed = sum(row.get("numeric_result_interpretable") is True for row in all_results)
    return {
        "batch_id": BATCH_ID,
        "eligible_family_cap": MAX_FAMILIES,
        "selected_family_count": len({card.family_id for card in cards}),
        "eligible_family_shortfall_vs_cap": MAX_FAMILIES - len({card.family_id for card in cards}),
        "implemented_configuration_count": len(cards),
        "completed_trial_count": completed,
        "data_blocked_configuration_count": data_blocked,
        "standalone_followup_candidate_count": standalone,
        "diversifier_followup_candidate_count": diversifier,
        "total_followup_candidate_count": standalone + diversifier,
        "closed_configuration_count": closed,
        "all_trial_result_count": len(all_results),
        "trial_lineage_count": len(cards),
        "rejection_or_data_issue_log_count": len(rejection_rows),
    }


def build_batch_report(funnel: dict[str, Any], family_rows: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    family_lines = "\n".join(
        f"- `{row['family_id']}`: {row['trial_count']} trial(s), outcome `{row['family_outcome']}`"
        for row in family_rows
    )
    candidate_lines = "\n".join(
        f"- `{row['strategy_id']}` / `{row['trial_id']}`: `{row['classification']}`"
        for row in candidates
    )
    if not candidate_lines:
        candidate_lines = "- No trial cleared the lightweight standalone or diversifier follow-up gates."
    next_action = NEXT_ACTION_WITH_CANDIDATES if candidates else NEXT_ACTION_ZERO_CANDIDATES
    return f"""# Fast Price/Volume Discovery Batch V2

## Scope

This bounded exploratory batch used existing adjusted daily OHLCV cache files and the existing shifted-weight return convention. It did not run strategy discovery outside the pre-registered cohort, did not tune parameters, did not run promotion review, and did not touch broker, order, paper/demo activation or real-money paths.

## Selected Families

{family_lines}

Eligible local family shortfall versus cap: `{funnel['eligible_family_shortfall_vs_cap']}`.

## Implemented Configurations

- Implemented configurations: `{funnel['implemented_configuration_count']}`
- Completed trials: `{funnel['completed_trial_count']}`
- Data-blocked configurations: `{funnel['data_blocked_configuration_count']}`

## Follow-Up Candidates

{candidate_lines}

## Closed Configurations

Closed configurations: `{funnel['closed_configuration_count']}`.

## Cohort Funnel

- Selected families: `{funnel['selected_family_count']}`
- Trials preserved in all_trial_results.csv: `{funnel['all_trial_result_count']}`
- Trial lineage rows: `{funnel['trial_lineage_count']}`
- Standalone follow-up candidates: `{funnel['standalone_followup_candidate_count']}`
- Diversifier follow-up candidates: `{funnel['diversifier_followup_candidate_count']}`

## Guardrails

All outputs remain exploratory and non-promotable. No DSR, PBO, CSCV, holdout validation, candidate_exhaustive, paper/demo activation, broker action or real-money recommendation was run or claimed.

Exact next action: `{next_action}`.
"""


TRIAL_FIELDS = [
    "family_id",
    "strategy_id",
    "trial_id",
    "display_name",
    "classification",
    "failure_reason",
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_assumption_bps",
    "estimated_cost_return_drag",
    "primary_control_id",
    "primary_control_total_return",
    "primary_control_cagr",
    "primary_control_sharpe_ratio",
    "primary_control_maximum_drawdown",
    "delta_total_return_vs_primary_control",
    "delta_sharpe_vs_primary_control",
    "delta_max_drawdown_vs_primary_control",
    "static_control_id",
    "static_control_total_return",
    "static_control_cagr",
    "static_control_sharpe_ratio",
    "static_control_maximum_drawdown",
    "delta_total_return_vs_static_control",
    "delta_sharpe_vs_static_control",
    "delta_max_drawdown_vs_static_control",
    "first_half_start",
    "first_half_end",
    "second_half_start",
    "second_half_end",
    "first_half_total_return",
    "second_half_total_return",
    "first_half_primary_control_return",
    "second_half_primary_control_return",
    "first_half_excess_vs_primary_control",
    "second_half_excess_vs_primary_control",
    "both_halves_negative_excess",
    "correlation_to_frozen_current_active_vm_dsr_usci_combo",
    "reference_combo_total_return",
    "reference_combo_sharpe_ratio",
    "reference_combo_maximum_drawdown",
    "fixed_20pct_sleeve_total_return",
    "fixed_20pct_sleeve_sharpe_ratio",
    "fixed_20pct_sleeve_maximum_drawdown",
    "fixed_20pct_sleeve_improves_sharpe",
    "fixed_20pct_sleeve_improves_max_drawdown",
    "fixed_20pct_sleeve_worsens_both",
    "standalone_gate_pass",
    "diversifier_gate_pass",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "exposure_invariant_pass",
    "numeric_result_interpretable",
    "promotion_review",
    "paper_demo_eligibility",
    "paper_demo_activation",
    "candidate_exhaustive",
    "real_money_action",
    "supporting_strategy_card_source",
]


def deterministic_core_hash() -> str:
    names = [
        "batch_manifest.yaml",
        "preregistered_strategy_cards.csv",
        "all_trial_results.csv",
        "family_results_summary.csv",
        "exploratory_followup_candidates.csv",
        "rejection_and_data_issue_log.csv",
        "trial_lineage.csv",
        "cohort_funnel_counts.json",
        "batch_report.md",
    ]
    payload = {name: (OUTPUT_DIR / name).read_text(encoding="utf-8") for name in names if (OUTPUT_DIR / name).exists()}
    return data_hash(payload)


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    exact_inventory = read_csv_rows(INPUT_EVIDENCE_PATHS[1])
    recent_fast = read_csv_rows(INPUT_EVIDENCE_PATHS[3])
    closed_deferred = read_csv_rows(INPUT_EVIDENCE_PATHS[4])
    missing_conflicts = read_csv_rows(INPUT_EVIDENCE_PATHS[5])
    clean_output_dir()

    card_rows = [card_to_row(card) for card in SELECTED_CARDS]
    reference_returns = active_vm_dsr_usci_reference_returns()
    all_results: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    data_issues: list[dict[str, Any]] = []
    candidate_returns: dict[str, pd.Series] = {}
    for card in SELECTED_CARDS:
        result, lineage, issue, candidate = evaluate_card(card, reference_returns)
        all_results.append(result)
        lineage_rows.append(lineage)
        if issue:
            data_issues.append(issue)
        if not candidate.empty:
            candidate_returns[card.trial_id] = candidate

    rejection_rows = build_rejection_log(exact_inventory, recent_fast, closed_deferred) + data_issues
    family_rows = family_summary_rows(all_results)
    followup_candidates = [
        row
        for row in all_results
        if row["classification"]
        in {"exploratory_followup_candidate_standalone", "exploratory_followup_candidate_diversifier"}
    ]
    funnel = cohort_funnel_counts(SELECTED_CARDS, all_results, rejection_rows)
    next_action = NEXT_ACTION_WITH_CANDIDATES if followup_candidates else NEXT_ACTION_ZERO_CANDIDATES

    manifest = {
        "batch_id": BATCH_ID,
        "mode": "bounded_exploratory_batch",
        "stage": "research_sample",
        "research_and_paper_demo_only": True,
        "preregistration_timestamp": FROZEN_PREREGISTRATION_TIMESTAMP,
        "input_evidence": [
            {"path": rel(path), "exists": path.exists(), "sha256": file_hash(path)} for path in INPUT_EVIDENCE_PATHS
        ],
        "local_queue_sources": [
            {"path": rel(path), "exists": path.exists(), "sha256": file_hash(path)} for path in LOCAL_QUEUE_PATHS
        ],
        "selected_family_count": funnel["selected_family_count"],
        "max_distinct_families_allowed": MAX_FAMILIES,
        "eligible_family_cap": MAX_FAMILIES,
        "eligible_family_shortfall_vs_cap": funnel["eligible_family_shortfall_vs_cap"],
        "strategy_cards_created_before_backtest": True,
        "broad_strategy_discovery": False,
        "strategy_discovery_run": False,
        "hidden_parameter_grid": False,
        "parameter_grid_or_optimizer_run": False,
        "post_result_parameter_changes": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "live_orders": False,
        "paper_demo_activation": False,
        "promotion_review": False,
        "candidate_exhaustive": False,
        "dsr_pbo_cscv_or_reality_check_run": False,
        "clean_holdout_claimed": False,
        "real_money_recommendation": False,
        "exact_next_action": next_action,
    }

    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "preregistered_strategy_cards.csv",
        card_rows,
        [
            "family_id",
            "strategy_id",
            "display_name",
            "strategy_architecture",
            "source_or_research_lineage",
            "economic_or_behavioral_rationale",
            "complete_canonical_rule",
            "parameters",
            "instrument_universe",
            "evaluation_start",
            "evaluation_end",
            "primary_benchmark_control",
            "static_control",
            "transaction_cost_assumption",
            "objective_route",
            "trial_id",
            "parent_trial_id",
            "changed_fields_from_parent",
            "preregistration_timestamp",
            "task_or_process_record",
        ],
    )
    write_csv(OUTPUT_DIR / "all_trial_results.csv", all_results, TRIAL_FIELDS)
    write_csv(
        OUTPUT_DIR / "family_results_summary.csv",
        family_rows,
        [
            "family_id",
            "strategy_count",
            "trial_count",
            "completed_trial_count",
            "data_blocked_trial_count",
            "standalone_followup_candidate_count",
            "diversifier_followup_candidate_count",
            "closed_exploration_count",
            "family_outcome",
            "best_total_return",
            "best_sharpe_ratio",
        ],
    )
    write_csv(OUTPUT_DIR / "exploratory_followup_candidates.csv", followup_candidates, TRIAL_FIELDS)
    write_csv(
        OUTPUT_DIR / "rejection_and_data_issue_log.csv",
        rejection_rows,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "source",
            "eligible_for_this_batch",
            "rejection_or_status",
            "issue_type",
            "issue",
            "data_issue",
            "blocking",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_lineage.csv",
        lineage_rows,
        [
            "family_id",
            "strategy_id",
            "trial_id",
            "parent_trial_id",
            "changed_fields_from_parent",
            "task_or_process_record",
            "predeclared_before_results",
            "source_or_research_lineage",
        ],
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(OUTPUT_DIR / "batch_report.md", build_batch_report(funnel, family_rows, followup_candidates))

    after_hashes = protected_hashes()
    consistency = {
        "batch_id": BATCH_ID,
        "report_path": rel(OUTPUT_DIR),
        "selected_family_count": funnel["selected_family_count"],
        "implemented_configuration_count": funnel["implemented_configuration_count"],
        "completed_trial_count": funnel["completed_trial_count"],
        "all_trials_preserved": funnel["all_trial_result_count"] == funnel["trial_lineage_count"],
        "cohort_funnel_arithmetically_consistent": (
            funnel["completed_trial_count"]
            + funnel["data_blocked_configuration_count"]
            == funnel["all_trial_result_count"]
            and funnel["standalone_followup_candidate_count"]
            + funnel["diversifier_followup_candidate_count"]
            + funnel["closed_configuration_count"]
            + funnel["data_blocked_configuration_count"]
            == funnel["all_trial_result_count"]
        ),
        "strategy_cards_have_required_non_unknown_fields": all(
            all(str(row.get(field, "")).strip() not in {"", "unknown"} for field in [
                "family_id",
                "strategy_id",
                "display_name",
                "strategy_architecture",
                "source_or_research_lineage",
                "complete_canonical_rule",
                "parameters",
                "instrument_universe",
                "primary_benchmark_control",
                "static_control",
                "trial_id",
            ])
            for row in card_rows
        ),
        "task_audit_runner_report_records_kept_out_of_trial_tables": all(
            row.get("task_or_process_record") is False for row in card_rows + lineage_rows
        ),
        "no_post_result_parameter_benchmark_timeframe_universe_changes": True,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "broad_strategy_discovery": False,
        "strategy_discovery_run": False,
        "hidden_parameter_grid": False,
        "parameter_grid_or_optimizer_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "live_orders": False,
        "paper_demo_activation": False,
        "promotion_review": False,
        "candidate_exhaustive": False,
        "dsr_pbo_cscv_or_reality_check_run": False,
        "clean_holdout_claimed": False,
        "real_money_recommendation": False,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        "input_missing_or_conflicting_evidence_rows": len(missing_conflicts),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "batch_id": BATCH_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "selected_family_count": funnel["selected_family_count"],
        "completed_trial_count": funnel["completed_trial_count"],
        "followup_candidate_count": funnel["total_followup_candidate_count"],
        "task_outcome": "fast_price_volume_discovery_batch_v2_complete",
        "exact_next_action": next_action,
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
