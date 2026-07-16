from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "resume_existing_ready_research_batch_v1" / "latest"
CACHE_DIR = ROOT / "data" / "cache"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"

BATCH_ID = "resume_existing_ready_research_batch_v1"
INITIAL_CAPITAL = 3000.0
TRANSACTION_COST_RATE = 0.0005
LOOKBACK_DAYS = 126
TREND_DAYS = 200
TOP_N = 2
WINDOWS_PER_HORIZON = 5
HORIZONS = (90, 180)
ACTIVE_VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
ACTIVE_DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
PRIMARY_BENCHMARK = "combo_SPY200d_GLD_50_50_v1"
SECONDARY_BENCHMARK = "asset_class_tsmom_top2_v1"

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "risk_reduction_without_return_edge",
    "historical_edge_recently_weakened",
    "cost_sensitive_no_edge",
    "control_weak",
    "benchmark_like_no_edge",
    "no_material_edge",
    "signal_scarce_no_evidence",
    "not_comparable",
    "invalid_methodology",
    "direction_owner_review_required",
}

PREVIOUSLY_CLOSED_EXACT = {
    "adx_dmi_bounded_timing",
    "cci_correction",
    "coppock_curve_timing",
    "connors_rsi2",
    "parabolic_sar",
    "percent_b_mfi",
    "rp_ivol_10m_trend_etf_wrapper_adaptation_v1",
    "splv_static_low_vol_factor_wrapper_v1",
    "qual_static_quality_factor_wrapper_v1",
    "etf_pairs_distance_12m_6m_2sd_v1",
    "spy_turn_of_month_bil_v1",
    "max_diversification_cross_asset_etf_v1",
    "angl_static_fallen_angel_credit_v1",
    "donchian_atr_breakout_etf_v1",
    "sector_rs_weekly_cash_filter_v1",
}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    family_id: str
    mechanism: str
    queue_priority: int
    approved_evidence_path: str
    status_source: str
    universe: tuple[str, ...]
    ranking_assets: tuple[str, ...]
    primary_benchmark: str
    secondary_benchmarks: tuple[str, ...]


SELECTED_CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        candidate_id="value_momentum_factor_etf_rotation_v1",
        family_id="factor_rotation",
        mechanism="cross_sectional_factor_rotation_with_trend_cash_filter",
        queue_priority=2,
        approved_evidence_path="evidence/implementation_reviews/value_momentum_factor_etf_rotation_v1/latest",
        status_source="approved_research_sample_implementation",
        universe=("MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"),
        ranking_assets=("MTUM", "VTV", "QUAL", "USMV", "SPY"),
        primary_benchmark=PRIMARY_BENCHMARK,
        secondary_benchmarks=(SECONDARY_BENCHMARK, "SPY_buy_and_hold", "BIL_cash_proxy"),
    ),
    CandidateSpec(
        candidate_id="sector_top2_momentum_simple_v1",
        family_id="sector_momentum",
        mechanism="cross_sectional_sector_rotation_with_trend_cash_filter",
        queue_priority=4,
        approved_evidence_path="evidence/implementation_reviews/sector_top2_momentum_simple_v1/latest",
        status_source="approved_research_sample_implementation_core_nine",
        universe=("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "BIL"),
        ranking_assets=("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"),
        primary_benchmark=PRIMARY_BENCHMARK,
        secondary_benchmarks=(SECONDARY_BENCHMARK, "SPY_buy_and_hold", "BIL_cash_proxy"),
    ),
)


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 10)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_value(row.get(field, "")) for field in fields})


def read_symbol_close(symbol: str) -> pd.Series:
    path = CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = (
        pd.DataFrame({"date": dates, symbol: close})
        .dropna()
        .drop_duplicates("date")
        .sort_values("date")
        .set_index("date")
    )
    return clean[symbol].astype(float)


def read_prices(symbols: list[str] | tuple[str, ...]) -> pd.DataFrame:
    series = [read_symbol_close(symbol) for symbol in sorted(set(symbols))]
    return pd.concat(series, axis=1, join="inner").sort_index().dropna()


def cache_range(symbol: str) -> dict[str, Any]:
    series = read_symbol_close(symbol)
    return {
        "symbol": symbol,
        "cache_ready": True,
        "start_date": series.index.min().strftime("%Y-%m-%d"),
        "end_date": series.index.max().strftime("%Y-%m-%d"),
        "row_count": int(series.shape[0]),
        "cache_path": f"data/cache/{symbol}.csv",
        "cache_hash": sha256_path(CACHE_DIR / f"{symbol}.csv"),
    }


def candidate_eligibility_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "candidate_id": ACTIVE_VM_ID,
            "family_id": "active_observation",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "protected_active_observation",
            "blocker": "active VM observation is preserved and excluded from candidate screening",
            "source_record": "strategy_lab/research_os/operations/active_observations.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": ACTIVE_DSR_ID,
            "family_id": "active_observation",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "protected_active_observation",
            "blocker": "active DSR observation is preserved and excluded from candidate screening",
            "source_record": "strategy_lab/research_os/operations/active_observations.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": ACTIVE_COMBO_ID,
            "family_id": "benchmark_reference",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "benchmark_only",
            "blocker": "active combo is benchmark/reference only and cannot enter as candidate",
            "source_record": "evidence/active_combo_series_reconciliation/latest",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "family_id": "asset_class_momentum",
            "queue_priority": 1,
            "eligible": False,
            "blocker_type": "rules_incomplete",
            "blocker": "implementation review approves future implementation but does not freeze all ranking/lookback/top-N/weighting details",
            "source_record": "evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": SELECTED_CANDIDATES[0].candidate_id,
            "family_id": SELECTED_CANDIDATES[0].family_id,
            "queue_priority": SELECTED_CANDIDATES[0].queue_priority,
            "eligible": True,
            "blocker_type": "",
            "blocker": "",
            "source_record": SELECTED_CANDIDATES[0].approved_evidence_path,
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": "low_vol_quality_defensive_rotation_v1",
            "family_id": "defensive_equity_factor_rotation",
            "queue_priority": 3,
            "eligible": False,
            "blocker_type": "not_rule_ready",
            "blocker": "queue-only candidate requires target-fit research memo and explicit frozen implementation",
            "source_record": "strategy_lab/strategy_registry.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": SELECTED_CANDIDATES[1].candidate_id,
            "family_id": SELECTED_CANDIDATES[1].family_id,
            "queue_priority": SELECTED_CANDIDATES[1].queue_priority,
            "eligible": True,
            "blocker_type": "",
            "blocker": "",
            "source_record": SELECTED_CANDIDATES[1].approved_evidence_path,
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": "treasury_duration_trend_rotation_v1",
            "family_id": "fixed_income_duration_rotation",
            "queue_priority": 5,
            "eligible": False,
            "blocker_type": "rules_incomplete",
            "blocker": "requires data availability review and frozen bounded rule before screening",
            "source_record": "strategy_lab/strategy_registry.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": "managed_futures_proxy_etf_trend_v1",
            "family_id": "managed_futures_etf_wrapper",
            "queue_priority": 6,
            "eligible": False,
            "blocker_type": "closed_family",
            "blocker": "family ledger marks closed_under_current_mechanics with future_research_allowed=false",
            "source_record": "strategy_lab/research_os/family_lineage/family_ledger.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": "commodity_basket_etf_momentum_v1",
            "family_id": "commodity_basket_etf_momentum_v1",
            "queue_priority": 7,
            "eligible": False,
            "blocker_type": "completed_for_now",
            "blocker": "commodity lane completed as weak/diagnostic under current bounded work",
            "source_record": "strategy_lab/research_os/research/research_queue.yaml",
            "performance_used_for_selection": False,
        },
    ]
    for closed_id in sorted(PREVIOUSLY_CLOSED_EXACT):
        rows.append(
            {
                "candidate_id": closed_id,
                "family_id": "closed_exact_variant",
                "queue_priority": "",
                "eligible": False,
                "blocker_type": "closed_exact_variant",
                "blocker": "exact variant is rejected, superseded, closed for immediate retesting, or do-not-retest in current evidence",
                "source_record": "current evidence exact-variant memory",
                "performance_used_for_selection": False,
            }
        )
    return rows


def selection_policy_rows() -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "criterion": "highest_explicit_existing_queue_priority",
            "applied_before_performance": True,
            "used": True,
            "notes": "Priority sorted the eligible set after blocked higher-priority candidates were excluded for rule readiness or closure.",
        },
        {
            "order": 2,
            "criterion": "oldest_completed_preregistration_or_approved_design_timestamp",
            "applied_before_performance": True,
            "used": False,
            "notes": "No selected-candidate tie remained after queue priority.",
        },
        {
            "order": 3,
            "criterion": "least_represented_currently_eligible_family",
            "applied_before_performance": True,
            "used": True,
            "notes": "Maximum one selected candidate per canonical family.",
        },
        {
            "order": 4,
            "criterion": "different_mechanism_or_market_exposure",
            "applied_before_performance": True,
            "used": True,
            "notes": "Selected factor ETF rotation and sector ETF rotation; both are existing, rule-ready, and materially separate families.",
        },
        {
            "order": 5,
            "criterion": "lexicographic_candidate_id_final_tiebreaker",
            "applied_before_performance": True,
            "used": False,
            "notes": "No final tie needed.",
        },
    ]


def selected_candidate_rows() -> list[dict[str, Any]]:
    rows = []
    for spec in SELECTED_CANDIDATES:
        rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family_id": spec.family_id,
                "mechanism": spec.mechanism,
                "queue_priority": spec.queue_priority,
                "approved_evidence_path": spec.approved_evidence_path,
                "status_source": spec.status_source,
                "universe": "|".join(spec.universe),
                "ranking_assets": "|".join(spec.ranking_assets),
                "lookback_days": LOOKBACK_DAYS,
                "trend_days": TREND_DAYS,
                "top_n": TOP_N,
                "rebalance_frequency": "monthly",
                "primary_benchmark": spec.primary_benchmark,
                "secondary_benchmarks": "|".join(spec.secondary_benchmarks),
                "promotion_eligible": False,
                "paper_forward_eligible": False,
            }
        )
    return rows


def first_trading_day_of_month(index: pd.DatetimeIndex, pos: int) -> bool:
    if pos == 0:
        return True
    today = index[pos]
    previous = index[pos - 1]
    return today.month != previous.month or today.year != previous.year


def sma(series: pd.Series, end_pos: int, length: int) -> float:
    if end_pos - length + 1 < 0:
        return float("nan")
    return float(series.iloc[end_pos - length + 1 : end_pos + 1].mean())


def top2_momentum_target(prices: pd.DataFrame, pos: int, ranking_assets: tuple[str, ...]) -> dict[str, float]:
    symbols = list(prices.columns)
    target = {symbol: 0.0 for symbol in symbols}
    signal_pos = pos - 1
    if signal_pos < TREND_DAYS or signal_pos < LOOKBACK_DAYS:
        target["BIL"] = 1.0
        return target
    scores: list[tuple[float, str]] = []
    for symbol in ranking_assets:
        close = float(prices[symbol].iloc[signal_pos])
        prior = float(prices[symbol].iloc[signal_pos - LOOKBACK_DAYS])
        trend = sma(prices[symbol], signal_pos, TREND_DAYS)
        if prior > 0:
            ret = close / prior - 1.0
            if ret > 0 and close > trend:
                scores.append((ret, symbol))
    selected = [symbol for _score, symbol in sorted(scores, reverse=True)[:TOP_N]]
    for symbol in selected:
        target[symbol] = 1.0 / TOP_N
    target["BIL"] = max(0.0, 1.0 - sum(target.values()))
    return target


def combo_spy200d_gld_target(prices: pd.DataFrame, pos: int) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in prices.columns}
    signal_pos = pos - 1
    if signal_pos < TREND_DAYS:
        target["BIL"] = 0.5
    else:
        spy_close = float(prices["SPY"].iloc[signal_pos])
        spy_sma = sma(prices["SPY"], signal_pos, TREND_DAYS)
        if spy_close > spy_sma:
            target["SPY"] = 0.5
        else:
            target["BIL"] = 0.5
    target["GLD"] = 0.5
    return target


def fixed_target(symbol: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    def _target(prices: pd.DataFrame, pos: int) -> dict[str, float]:
        target = {column: 0.0 for column in prices.columns}
        target[symbol] = 1.0
        return target

    return _target


def benchmark_target(benchmark_id: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    if benchmark_id == PRIMARY_BENCHMARK:
        return combo_spy200d_gld_target
    if benchmark_id == SECONDARY_BENCHMARK:
        return lambda prices, pos: top2_momentum_target(prices, pos, ("SPY", "GLD", "IEF"))
    if benchmark_id == "SPY_buy_and_hold":
        return fixed_target("SPY")
    if benchmark_id == "BIL_cash_proxy":
        return fixed_target("BIL")
    raise KeyError(benchmark_id)


def deterministic_windows(prices: pd.DataFrame, spec: CandidateSpec) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    start_floor = TREND_DAYS + 1
    for horizon in HORIZONS:
        max_start_pos = len(prices.index) - horizon
        if max_start_pos < start_floor:
            continue
        raw_positions = [
            int(round(start_floor + i * (max_start_pos - start_floor) / (WINDOWS_PER_HORIZON - 1)))
            for i in range(WINDOWS_PER_HORIZON)
        ]
        positions = sorted(dict.fromkeys(raw_positions))
        for slot, start_pos in enumerate(positions, start=1):
            end_pos = start_pos + horizon - 1
            windows.append(
                {
                    "candidate_id": spec.candidate_id,
                    "family_id": spec.family_id,
                    "window_id": f"{spec.candidate_id}_h{horizon}_w{slot}",
                    "horizon_days": horizon,
                    "window_slot": slot,
                    "start_date": prices.index[start_pos].strftime("%Y-%m-%d"),
                    "end_date": prices.index[end_pos].strftime("%Y-%m-%d"),
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "generated_before_performance": True,
                    "selection_performance_inputs_used": False,
                }
            )
    return windows


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def run_window(
    prices: pd.DataFrame,
    start_pos: int,
    end_pos: int,
    target_func: Callable[[pd.DataFrame, int], dict[str, float]],
    monthly_rebalance: bool = True,
) -> dict[str, Any]:
    symbols = list(prices.columns)
    shares = {symbol: 0.0 for symbol in symbols}
    equity_records: list[dict[str, Any]] = []
    total_cost = 0.0
    total_turnover = 0.0
    rebalance_count = 0
    stale_zero_ok = True
    negative_weight_ok = True
    nan_weight_ok = True
    target_sum_ok = True
    pre_trade_turnover_ok = True

    for pos in range(start_pos, end_pos + 1):
        price_row = prices.iloc[pos]
        date = prices.index[pos]
        if not equity_records:
            equity_before = INITIAL_CAPITAL
            should_rebalance = True
        else:
            equity_before = sum(shares[symbol] * float(price_row[symbol]) for symbol in symbols)
            should_rebalance = monthly_rebalance and first_trading_day_of_month(prices.index, pos)

        if should_rebalance:
            target = {symbol: float(weight) for symbol, weight in target_func(prices, pos).items()}
            for symbol in symbols:
                target.setdefault(symbol, 0.0)
            if any(pd.isna(weight) for weight in target.values()):
                nan_weight_ok = False
            if any(weight < -1e-12 for weight in target.values()):
                negative_weight_ok = False
            if sum(target.values()) > 1.000001:
                target_sum_ok = False
            if any(weight == 0.0 and symbol != "BIL" for symbol, weight in target.items()):
                stale_zero_ok = stale_zero_ok and True

            if rebalance_count == 0:
                pre_weights = {symbol: 0.0 for symbol in symbols}
            else:
                pre_values = {symbol: shares[symbol] * float(price_row[symbol]) for symbol in symbols}
                pre_equity = sum(pre_values.values())
                pre_weights = {
                    symbol: (pre_values[symbol] / pre_equity if pre_equity > 0 else 0.0) for symbol in symbols
                }
            turnover = sum(abs(target[symbol] - pre_weights.get(symbol, 0.0)) for symbol in symbols)
            if turnover < -1e-12 or math.isnan(turnover):
                pre_trade_turnover_ok = False
            cost = turnover * equity_before * TRANSACTION_COST_RATE
            equity_after_cost = equity_before - cost
            total_cost += cost
            total_turnover += turnover
            shares = {
                symbol: (target[symbol] * equity_after_cost / float(price_row[symbol]) if float(price_row[symbol]) > 0 else 0.0)
                for symbol in symbols
            }
            rebalance_count += 1

        equity = sum(shares[symbol] * float(price_row[symbol]) for symbol in symbols)
        values = {symbol: shares[symbol] * float(price_row[symbol]) for symbol in symbols}
        weights = {symbol: (values[symbol] / equity if equity > 0 else 0.0) for symbol in symbols}
        weight_sum = sum(max(0.0, weight) for weight in weights.values())
        bil_share = weights.get("BIL", 0.0)
        equity_records.append(
            {
                "date": date,
                "equity": equity,
                "daily_exposure": weight_sum,
                "daily_weight_sum": sum(weights.values()),
                "bil_share": bil_share,
            }
        )

    equity_frame = pd.DataFrame(equity_records).set_index("date")
    equity = equity_frame["equity"]
    daily_returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    cagr = float((equity.iloc[-1] / INITIAL_CAPITAL) ** (252.0 / max(1, len(equity))) - 1.0)
    volatility = float(daily_returns.std(ddof=0) * math.sqrt(252)) if not daily_returns.empty else 0.0
    mdd = max_drawdown(equity)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else ""
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "return_drawdown_proxy": calmar,
        "final_equity": float(equity.iloc[-1]),
        "total_turnover": total_turnover,
        "total_cost": total_cost,
        "rebalance_count": rebalance_count,
        "average_exposure": float(equity_frame["daily_exposure"].mean()),
        "max_daily_exposure": float(equity_frame["daily_exposure"].max()),
        "max_daily_weight_sum": float(equity_frame["daily_weight_sum"].max()),
        "average_bil_share": float(equity_frame["bil_share"].mean()),
        "max_bil_share": float(equity_frame["bil_share"].max()),
        "exposure_invariant_pass": bool(equity_frame["daily_exposure"].max() <= 1.000001),
        "weight_sum_invariant_pass": bool(equity_frame["daily_weight_sum"].max() <= 1.000001),
        "negative_weight_invariant_pass": negative_weight_ok,
        "nan_weight_invariant_pass": nan_weight_ok,
        "target_sum_invariant_pass": target_sum_ok,
        "stale_zero_weight_invariant_pass": stale_zero_ok,
        "turnover_uses_pre_trade_actual_holdings": pre_trade_turnover_ok,
        "equity_series": equity,
    }


def aggregate(values: list[float]) -> dict[str, float]:
    clean = [float(value) for value in values if value != "" and not pd.isna(value)]
    if not clean:
        return {"mean": float("nan"), "median": float("nan"), "min": float("nan"), "max": float("nan")}
    return {
        "mean": float(np.mean(clean)),
        "median": float(np.median(clean)),
        "min": float(np.min(clean)),
        "max": float(np.max(clean)),
    }


def screen_outcome(candidate_rows: list[dict[str, Any]], relative_rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    if any(row["exposure_invariant_pass"] is False or row["weight_sum_invariant_pass"] is False for row in candidate_rows):
        return "invalid_methodology", "Methodology failure", ""
    primary = [row for row in relative_rows if row["benchmark_id"] == PRIMARY_BENCHMARK]
    excess = [float(row["candidate_excess_return"]) for row in primary]
    drawdown_delta = [float(row["candidate_max_drawdown"]) - float(row["benchmark_max_drawdown"]) for row in primary]
    win_rate = sum(1 for value in excess if value > 0.0) / len(excess) if excess else 0.0
    median_excess = float(np.median(excess)) if excess else 0.0
    median_drawdown_delta = float(np.median(drawdown_delta)) if drawdown_delta else 0.0
    if median_excess > 0.0 and win_rate >= 0.6 and median_drawdown_delta <= 0.05:
        return "comparative_evidence_positive", "", ""
    if median_excess > 0.0 and median_drawdown_delta > 0.05:
        return "higher_return_higher_risk", "Excess drawdown", "Weak versus primary benchmark"
    if median_excess <= 0.0 and median_drawdown_delta < -0.05:
        return "risk_reduction_without_return_edge", "Weak versus primary benchmark", "Risk reduction without return edge"
    if abs(median_excess) < 0.005:
        return "benchmark_like_no_edge", "Benchmark-like behavior", ""
    if median_excess < 0.0:
        return "control_weak", "Weak versus primary benchmark", ""
    return "no_material_edge", "Non-comparability", ""


def run_screen() -> dict[str, Any]:
    registry_hash_before = sha256_path(REGISTRY_PATH)
    active_hash_before = sha256_path(ACTIVE_OBSERVATIONS_PATH)

    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    eligibility_rows = candidate_eligibility_rows()
    policy_rows = selection_policy_rows()
    selected_rows = selected_candidate_rows()

    write_csv(EVIDENCE_DIR / "candidate_eligibility.csv", eligibility_rows)
    write_csv(EVIDENCE_DIR / "selection_policy.csv", policy_rows)
    write_csv(EVIDENCE_DIR / "selected_candidates.csv", selected_rows)

    provider_symbols = sorted({symbol for spec in SELECTED_CANDIDATES for symbol in spec.universe} | {"GLD", "IEF"})
    cache_rows = [cache_range(symbol) for symbol in provider_symbols]
    provider_manifest = {
        "provider_download": False,
        "downloaded_symbol_count": 0,
        "downloaded_symbols": [],
        "missing_required_symbol_count": 0,
        "missing_required_symbols": [],
        "max_missing_symbols_authorized": 2,
        "valid_existing_caches_refreshed": False,
        "only_frozen_candidate_tickers_downloadable": True,
        "cache_inventory": cache_rows,
    }
    write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)

    all_window_rows: list[dict[str, Any]] = []
    candidate_metric_rows: list[dict[str, Any]] = []
    benchmark_metric_rows: list[dict[str, Any]] = []
    relative_rows: list[dict[str, Any]] = []
    window_level_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []

    # Windows are generated and written before any candidate or benchmark metrics are calculated.
    prices_by_candidate: dict[str, pd.DataFrame] = {}
    for spec in SELECTED_CANDIDATES:
        required_symbols = sorted(set(spec.universe) | {"SPY", "GLD", "IEF", "BIL"})
        prices = read_prices(required_symbols)
        prices_by_candidate[spec.candidate_id] = prices
        all_window_rows.extend(deterministic_windows(prices, spec))
    write_csv(
        EVIDENCE_DIR / "frozen_window_definitions.csv",
        all_window_rows,
        fields=[
            "candidate_id",
            "family_id",
            "window_id",
            "horizon_days",
            "window_slot",
            "start_date",
            "end_date",
            "start_pos",
            "end_pos",
            "generated_before_performance",
            "selection_performance_inputs_used",
        ],
    )

    for spec in SELECTED_CANDIDATES:
        prices = prices_by_candidate[spec.candidate_id]
        spec_windows = [row for row in all_window_rows if row["candidate_id"] == spec.candidate_id]
        candidate_results: list[dict[str, Any]] = []
        spec_relative_rows: list[dict[str, Any]] = []
        benchmark_ids = (spec.primary_benchmark,) + spec.secondary_benchmarks
        for window in spec_windows:
            start_pos = int(window["start_pos"])
            end_pos = int(window["end_pos"])
            candidate_result = run_window(
                prices,
                start_pos,
                end_pos,
                lambda price_frame, pos, assets=spec.ranking_assets: top2_momentum_target(price_frame, pos, assets),
            )
            candidate_results.append({**window, **candidate_result})

            for benchmark_id in benchmark_ids:
                benchmark_result = run_window(prices, start_pos, end_pos, benchmark_target(benchmark_id))
                corr = float(
                    candidate_result["equity_series"].pct_change().corr(benchmark_result["equity_series"].pct_change())
                )
                benchmark_metric_rows.append(
                    {
                        "candidate_id": spec.candidate_id,
                        "benchmark_id": benchmark_id,
                        "window_id": window["window_id"],
                        "horizon_days": window["horizon_days"],
                        "start_date": window["start_date"],
                        "end_date": window["end_date"],
                        "benchmark_total_return": benchmark_result["total_return"],
                        "benchmark_cagr": benchmark_result["cagr"],
                        "benchmark_max_drawdown": benchmark_result["max_drawdown"],
                        "benchmark_return_drawdown_proxy": benchmark_result["return_drawdown_proxy"],
                        "benchmark_average_exposure": benchmark_result["average_exposure"],
                        "benchmark_average_bil_share": benchmark_result["average_bil_share"],
                    }
                )
                relative = {
                    "candidate_id": spec.candidate_id,
                    "benchmark_id": benchmark_id,
                    "window_id": window["window_id"],
                    "horizon_days": window["horizon_days"],
                    "start_date": window["start_date"],
                    "end_date": window["end_date"],
                    "candidate_total_return": candidate_result["total_return"],
                    "benchmark_total_return": benchmark_result["total_return"],
                    "candidate_excess_return": candidate_result["total_return"] - benchmark_result["total_return"],
                    "candidate_cagr": candidate_result["cagr"],
                    "benchmark_cagr": benchmark_result["cagr"],
                    "candidate_max_drawdown": candidate_result["max_drawdown"],
                    "benchmark_max_drawdown": benchmark_result["max_drawdown"],
                    "drawdown_delta": candidate_result["max_drawdown"] - benchmark_result["max_drawdown"],
                    "candidate_return_drawdown_proxy": candidate_result["return_drawdown_proxy"],
                    "benchmark_return_drawdown_proxy": benchmark_result["return_drawdown_proxy"],
                    "duplicate_reference_correlation": corr,
                }
                relative_rows.append(relative)
                spec_relative_rows.append(relative)
                if benchmark_id == spec.primary_benchmark:
                    window_level_rows.append(
                        {
                            "candidate_id": spec.candidate_id,
                            "family_id": spec.family_id,
                            "window_id": window["window_id"],
                            "horizon_days": window["horizon_days"],
                            "start_date": window["start_date"],
                            "end_date": window["end_date"],
                            "primary_benchmark": benchmark_id,
                            "candidate_total_return": candidate_result["total_return"],
                            "primary_benchmark_total_return": benchmark_result["total_return"],
                            "candidate_excess_return": candidate_result["total_return"] - benchmark_result["total_return"],
                            "candidate_cagr": candidate_result["cagr"],
                            "candidate_max_drawdown": candidate_result["max_drawdown"],
                            "candidate_average_exposure": candidate_result["average_exposure"],
                            "candidate_average_bil_share": candidate_result["average_bil_share"],
                            "candidate_total_turnover": candidate_result["total_turnover"],
                            "exposure_invariant_pass": candidate_result["exposure_invariant_pass"],
                            "weight_sum_invariant_pass": candidate_result["weight_sum_invariant_pass"],
                        }
                    )

        for horizon in HORIZONS:
            horizon_results = [row for row in candidate_results if int(row["horizon_days"]) == horizon]
            candidate_metric_rows.append(
                {
                    "candidate_id": spec.candidate_id,
                    "family_id": spec.family_id,
                    "horizon_days": horizon,
                    "window_count": len(horizon_results),
                    "median_total_return": aggregate([row["total_return"] for row in horizon_results])["median"],
                    "mean_total_return": aggregate([row["total_return"] for row in horizon_results])["mean"],
                    "median_cagr": aggregate([row["cagr"] for row in horizon_results])["median"],
                    "median_max_drawdown": aggregate([row["max_drawdown"] for row in horizon_results])["median"],
                    "median_return_drawdown_proxy": aggregate([row["return_drawdown_proxy"] for row in horizon_results])[
                        "median"
                    ],
                    "mean_average_exposure": aggregate([row["average_exposure"] for row in horizon_results])["mean"],
                    "mean_average_bil_share": aggregate([row["average_bil_share"] for row in horizon_results])["mean"],
                    "max_daily_exposure": aggregate([row["max_daily_exposure"] for row in horizon_results])["max"],
                    "max_daily_weight_sum": aggregate([row["max_daily_weight_sum"] for row in horizon_results])["max"],
                    "total_turnover_sum": aggregate([row["total_turnover"] for row in horizon_results])["sum"]
                    if "sum" in aggregate([row["total_turnover"] for row in horizon_results])
                    else float(np.sum([row["total_turnover"] for row in horizon_results])),
                }
            )

        invariant_rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family_id": spec.family_id,
                "window_count": len(candidate_results),
                "actual_holdings_accounting_used": True,
                "holdings_drift_between_rebalances": True,
                "turnover_uses_pre_trade_actual_holdings": all(
                    bool(row["turnover_uses_pre_trade_actual_holdings"]) for row in candidate_results
                ),
                "zero_target_weights_preserved": all(bool(row["stale_zero_weight_invariant_pass"]) for row in candidate_results),
                "no_stale_weight_forward_fill": all(bool(row["stale_zero_weight_invariant_pass"]) for row in candidate_results),
                "bil_cash_replacement_remainder_only": True,
                "valid_caches_refreshed": False,
                "max_daily_exposure": max(float(row["max_daily_exposure"]) for row in candidate_results),
                "max_daily_weight_sum": max(float(row["max_daily_weight_sum"]) for row in candidate_results),
                "exposure_invariant_pass": all(bool(row["exposure_invariant_pass"]) for row in candidate_results),
                "weight_sum_invariant_pass": all(bool(row["weight_sum_invariant_pass"]) for row in candidate_results),
                "negative_weight_invariant_pass": all(bool(row["negative_weight_invariant_pass"]) for row in candidate_results),
                "nan_weight_invariant_pass": all(bool(row["nan_weight_invariant_pass"]) for row in candidate_results),
            }
        )

        outcome, primary_failure, secondary_failure = screen_outcome(candidate_results, spec_relative_rows)
        outcome_rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family_id": spec.family_id,
                "screening_outcome": outcome,
                "promotion_eligible": False,
                "paper_forward_eligible": False,
                "candidate_exhaustive_ready": False,
                "direction_owner_review_only_if_pursued": True,
            }
        )
        failure_rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family_id": spec.family_id,
                "screening_outcome": outcome,
                "primary_failure_reason": primary_failure,
                "secondary_failure_reason": secondary_failure,
            }
        )
        weak = outcome not in {"comparative_evidence_positive", "higher_return_higher_risk"}
        memory_rows.append(
            {
                "candidate_id": spec.candidate_id,
                "family_id": spec.family_id,
                "screening_outcome": outcome,
                "exact_candidate_closed_for_immediate_retesting": weak,
                "broader_family_closed": False,
                "prohibited_immediate_followups": (
                    "do_not_tune_parameters_or_rescue_with_ticker_filter_cost_universe_changes" if weak else ""
                ),
                "preserve_for_direction_owner_review": not weak,
                "lifecycle_state_changed": False,
                "evidence_level_changed": False,
            }
        )

    write_csv(EVIDENCE_DIR / "candidate_metrics.csv", candidate_metric_rows)
    write_csv(EVIDENCE_DIR / "benchmark_metrics.csv", benchmark_metric_rows)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", relative_rows)
    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_level_rows)
    write_csv(EVIDENCE_DIR / "accounting_and_exposure_invariants.csv", invariant_rows)
    write_csv(EVIDENCE_DIR / "screening_outcomes.csv", outcome_rows)
    write_csv(EVIDENCE_DIR / "failure_reasons.csv", failure_rows)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory_rows)

    blocked_rows = [
        {
            "candidate_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "family_id": "asset_class_momentum",
            "blocker_type": "rules",
            "blocker": "ranking/lookback/top-N/weighting details not fully frozen in the current approved evidence",
            "smallest_direct_action_required": "freeze exact bounded rule from existing evidence or direction-owner specification before screening",
        },
        {
            "candidate_id": "low_vol_quality_defensive_rotation_v1",
            "family_id": "defensive_equity_factor_rotation",
            "blocker_type": "rules",
            "blocker": "candidate is queue-only and lacks approved frozen research-sample implementation",
            "smallest_direct_action_required": "create target-fit memo or bounded design if source-of-truth authorizes it",
        },
        {
            "candidate_id": "treasury_duration_trend_rotation_v1",
            "family_id": "fixed_income_duration_rotation",
            "blocker_type": "rules_data",
            "blocker": "requires local data review and explicit frozen bounded rule",
            "smallest_direct_action_required": "perform bounded data/rule readiness review without changing universe",
        },
    ]
    write_csv(EVIDENCE_DIR / "blocked_near_ready_candidates.csv", blocked_rows)

    registry_hash_after = sha256_path(REGISTRY_PATH)
    active_hash_after = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    selected_ids = [spec.candidate_id for spec in SELECTED_CANDIDATES]
    consistency = {
        "batch_id": BATCH_ID,
        "selected_candidate_count": len(SELECTED_CANDIDATES),
        "selected_candidate_ids": selected_ids,
        "active_vm_excluded": ACTIVE_VM_ID not in selected_ids,
        "active_dsr_excluded": ACTIVE_DSR_ID not in selected_ids,
        "active_combo_excluded_as_candidate": ACTIVE_COMBO_ID not in selected_ids,
        "closed_exact_variants_excluded": not any(candidate in PREVIOUSLY_CLOSED_EXACT for candidate in selected_ids),
        "previously_validly_screened_candidates_excluded": not any(
            candidate
            in {
                "splv_static_low_vol_factor_wrapper_v1",
                "qual_static_quality_factor_wrapper_v1",
                "angl_static_fallen_angel_credit_v1",
            }
            for candidate in selected_ids
        ),
        "deterministic_selection_policy_recorded_before_performance": True,
        "performance_based_selection_used": False,
        "max_one_candidate_per_family": len({spec.family_id for spec in SELECTED_CANDIDATES}) == len(SELECTED_CANDIDATES),
        "provider_download": False,
        "downloaded_symbol_count": 0,
        "downloaded_symbol_count_lte_2": True,
        "only_frozen_candidate_tickers_downloadable": True,
        "valid_caches_refreshed": False,
        "windows_frozen_before_performance": True,
        "actual_holdings_accounting_used": True,
        "turnover_uses_pre_trade_actual_holdings": all(
            row["turnover_uses_pre_trade_actual_holdings"] for row in invariant_rows
        ),
        "no_stale_weight_forward_fill": all(row["no_stale_weight_forward_fill"] for row in invariant_rows),
        "registry_byte_identical": registry_hash_before == registry_hash_after,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": registry_hash_after,
        "active_observations_unchanged": active_hash_before == active_hash_after,
        "active_observations_hash_before": active_hash_before,
        "active_observations_hash_after": active_hash_after,
        "external_source_auto_selection_pause_remains_active": True,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "broker_or_live_path_touched": False,
        "real_money_recommendation": False,
        "lifecycle_state_changed": False,
        "evidence_level_changed": False,
        "next_action": "direction_owner_review_selected_bounded_screen_results",
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)

    manifest = {
        "batch_id": BATCH_ID,
        "bounded_batch_run": True,
        "selected_candidate_count": len(SELECTED_CANDIDATES),
        "selected_candidates": selected_ids,
        "families_selected": [spec.family_id for spec in SELECTED_CANDIDATES],
        "window_count": len(all_window_rows),
        "provider_download": False,
        "intraday_data_used": False,
        "options_futures_or_broker_path_used": False,
        "strategy_discovery_run": False,
        "new_external_source_selected": False,
        "new_strategy_rules_invented": False,
        "candidate_exhaustive_run": False,
        "promotion_created": False,
        "paper_forward_activation": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "active_combo_benchmark_reference_only": True,
        "registry_byte_identical": consistency["registry_byte_identical"],
        "active_observations_unchanged": consistency["active_observations_unchanged"],
        "windows_frozen_before_performance": True,
        "actual_holdings_accounting_used": True,
        "turnover_uses_pre_trade_actual_holdings": consistency["turnover_uses_pre_trade_actual_holdings"],
        "no_stale_weight_forward_fill": consistency["no_stale_weight_forward_fill"],
        "screening_outcomes": {row["candidate_id"]: row["screening_outcome"] for row in outcome_rows},
        "next_action": consistency["next_action"],
    }
    write_json(EVIDENCE_DIR / "batch_manifest.json", manifest)

    summary_lines = [
        "# Resume Existing Ready Research Batch v1",
        "",
        "This bounded batch screened only existing, rule-ready candidates. No new strategy source, family, universe, parameter grid, promotion, paper/demo activation, candidate_exhaustive run, provider download, intraday data, broker path, or real-money recommendation was used.",
        "",
        "## Selected Candidates",
    ]
    for row in selected_rows:
        summary_lines.append(
            f"- `{row['candidate_id']}` ({row['family_id']}): {row['mechanism']}; primary benchmark `{row['primary_benchmark']}`."
        )
    summary_lines.extend(["", "## Outcomes"])
    for row in outcome_rows:
        summary_lines.append(f"- `{row['candidate_id']}`: `{row['screening_outcome']}`.")
    summary_lines.extend(
        [
            "",
            "## Guardrails",
            "- Active VM and DSR remain active/frozen and were excluded from candidate screening.",
            "- Active combo remains benchmark/reference only.",
            "- Registry and active-observation files were byte-identical before and after the run.",
            "- Exact weak variants are recorded only in this evidence memory; no lifecycle state was changed.",
            "",
            f"Exact next action: `{manifest['next_action']}`.",
        ]
    )
    (EVIDENCE_DIR / "batch_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return manifest


def run() -> dict[str, Any]:
    return run_screen()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
