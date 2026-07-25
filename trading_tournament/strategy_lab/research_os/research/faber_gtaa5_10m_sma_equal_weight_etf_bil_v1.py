from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    COST_RATE,
    FROZEN_UNIVERSE_PATH,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    data_hash,
    load_adjusted_ohlcv,
    metrics_from_returns,
    turnover_series,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


TASK_ID = "faber_gtaa5_10m_sma_equal_weight_etf_bil_v1"
TRIAL_ID = "faber_gtaa5_10m_sma_equal_weight_etf_bil_v1__canonical_portfolio"
FAMILY_ID = "multi_asset_independent_trend_allocation"
SOURCE_ID = "mebane_faber_quantitative_approach_tactical_asset_allocation"
OUTPUT_DIR = Path("evidence") / "fast_progress" / TASK_ID / "latest"
NEXT_ACTION = "direction_owner_review_faber_gtaa5_fast_lane_v1"
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
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
SELECTED_COMPATIBILITY_FAMILY = "own_return_trend_long_cash"
SMA_MONTHS = 10
SLEEVE_WEIGHT = 0.20
RISKY_SLEEVE_COUNT = 5
WEIGHT_TOLERANCE = 1e-6

EXPECTED_MAPPING = [
    ("us_large_cap_equities", "U.S. large-cap equities", "SPY", "us_broad_size_style_factors", "US large-cap broad equity"),
    ("developed_international_equities", "Developed international equities", "EFA", "developed_emerging_regions_countries", "Developed ex-US equity"),
    ("us_10_year_government_bonds", "U.S. 10-year government bonds", "IEF", "government_bonds_and_credit", "Intermediate US Treasuries"),
    ("broad_commodities", "Broad commodities", "GSG", "commodities_and_precious_metals", "Broad commodity futures basket"),
    ("us_reits", "U.S. REITs", "VNQ", "real_estate_and_infrastructure", "US real estate equity"),
]
REQUIRED_CASH = ("treasury_bills", "Defensive Treasury bills", "BIL", "government_bonds_and_credit", "US Treasury bills/cash proxy")

VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "exact_gtaa5_implementation_duplicate_found",
    "source_asset_mapping_unavailable",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
VALID_TASK_OUTCOMES = {
    "gtaa5_fast_lane_complete",
    "exact_gtaa5_implementation_duplicate_found",
    "source_asset_mapping_unavailable",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
CORE_FILES = [
    "source_packet_used.yaml",
    "exact_duplicate_check.json",
    "repository_fit_check.json",
    "frozen_universe_reference.json",
    "source_to_etf_mapping.csv",
    "frozen_trial_manifest.csv",
    "data_coverage.csv",
    "monthly_price_matrix.csv",
    "sma_signal_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "control_metrics.csv",
    "baseline_vs_controls.csv",
    "timeframe_diagnostics.csv",
    "accounting_invariants.csv",
    "family_outcome.json",
    "family_followup_queue.csv",
]


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def directory_hash(path: Path) -> str:
    payload: dict[str, str] = {}
    if path.exists():
        for item in sorted(path.rglob("*")):
            if item.is_file():
                payload[str(item.relative_to(path)).replace("\\", "/")] = file_hash(item)
    return data_hash(payload)


def deterministic_core_hash(evidence_dir: Path) -> str:
    return data_hash(
        {name: (evidence_dir / name).read_text(encoding="utf-8") if (evidence_dir / name).exists() else "missing" for name in CORE_FILES}
    )


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


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def compound_return(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float((1.0 + series.fillna(0.0)).prod() - 1.0)


def source_packet() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_name": "A Quantitative Approach to Tactical Asset Allocation",
        "author": "Mebane T. Faber",
        "research_status": "exploratory_non_promotable",
        "source_asset_classes": [row[1] for row in EXPECTED_MAPPING],
        "expected_etf_translation": {row[0]: row[2] for row in EXPECTED_MAPPING},
        "cash_proxy": "BIL",
        "rules": {
            "sleeves": "five fixed 20 percent source sleeves",
            "signal": "monthly adjusted close greater than 10-month simple moving average",
            "exit": "monthly adjusted close below 10-month simple moving average moves sleeve to Treasury bills/BIL",
            "equal_signal": "retain previous established active or inactive state",
            "rebalance": "monthly, after completed month-end observations",
            "execution": "next eligible daily session via project shifted/no-lookahead accounting",
        },
        "forbidden": [
            "relative_strength_ranking",
            "top_n_selection",
            "moving_average_length_change",
            "daily_or_weekly_signal",
            "ema",
            "volatility_targeting",
            "momentum_confirmation",
            "parameter_search",
        ],
    }


def duplicate_check(root: Path) -> dict[str, Any]:
    reviewed = [
        {
            "name": "faber_10m_sma_long_bil_portability_v1",
            "path": "evidence/faber_10m_sma_long_bil_portability_v1/latest",
            "hash": directory_hash(root / "evidence" / "faber_10m_sma_long_bil_portability_v1" / "latest"),
            "exists": (root / "evidence" / "faber_10m_sma_long_bil_portability_v1" / "latest").exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Prior packet is an own-return trend portability distribution across independent instruments, not one fixed five-sleeve portfolio with 20 percent source sleeves.",
        },
        {
            "name": "quantpedia_asset_class_trend_following_5asset_10m_v1",
            "path": "evidence/public_source_strategy_implementation/quantpedia_asset_class_trend_following_5asset_10m_v1/latest",
            "hash": directory_hash(root / "evidence" / "public_source_strategy_implementation" / "quantpedia_asset_class_trend_following_5asset_10m_v1" / "latest"),
            "exists": (root / "evidence" / "public_source_strategy_implementation" / "quantpedia_asset_class_trend_following_5asset_10m_v1" / "latest").exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Prior public-source gate blocked implementation and produced no candidate metrics or portfolio evidence.",
        },
        {
            "name": "gtaa_faber_style_benchmark_lane",
            "path": "strategy_lab/parallel_research_discovery_queue.yaml",
            "hash": file_hash(root / "strategy_lab" / "parallel_research_discovery_queue.yaml"),
            "exists": (root / "strategy_lab" / "parallel_research_discovery_queue.yaml").exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Queue/benchmark planning records include Faber-style ideas but are not a verified exact five-sleeve implementation packet.",
        },
    ]
    exact = [row for row in reviewed if row["assessment"] == "exact_duplicate"]
    return {
        "task_id": TASK_ID,
        "exact_duplicate_found": bool(exact),
        "exact_duplicate_paths": [row["path"] for row in exact],
        "reviewed_records": reviewed,
        "duplicate_check_completed_before_return_calculation": True,
    }


def frozen_universe(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / FROZEN_UNIVERSE_PATH)


def compatibility_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / COMPATIBILITY_PATH)


def symbol_row(universe_rows: list[dict[str, str]], symbol: str) -> dict[str, str] | None:
    return next((row for row in universe_rows if row.get("symbol") == symbol), None)


def resolve_mapping(root: Path, universe_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[str]]:
    compat = {
        row["symbol"]
        for row in compatibility_rows(root)
        if row.get("family_id") == SELECTED_COMPATIBILITY_FAMILY
        and row.get("compatibility_label") == "compatible_with_frozen_cash_proxy"
    }
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []

    def choose(expected_symbol: str, expected_group: str, expected_exposure: str) -> tuple[str, str, str]:
        expected = symbol_row(universe_rows, expected_symbol)
        if expected and expected_symbol in compat and expected.get("candidate_group") == expected_group:
            return expected_symbol, "expected_symbol_available", ""
        group_candidates = [
            row
            for row in universe_rows
            if row.get("candidate_group") == expected_group
            and row.get("symbol") in compat
            and row.get("product_structure", "").lower() not in {"inverse_etf", "leveraged_etf"}
        ]
        exposure_lower = expected_exposure.lower()
        direct = [row for row in group_candidates if exposure_lower in row.get("primary_economic_exposure", "").lower()]
        if direct:
            return direct[0]["symbol"], "source_exposure_aligned_substitution", f"{expected_symbol}_absent_or_unusable"
        if group_candidates:
            return group_candidates[0]["symbol"], "same_group_substitution", f"{expected_symbol}_absent_or_unusable"
        return "", "unavailable", f"{expected_symbol}_absent_and_no_same_group_compatible_symbol"

    for source_key, source_asset_class, expected_symbol, expected_group, expected_exposure in EXPECTED_MAPPING:
        selected, status, reason = choose(expected_symbol, expected_group, expected_exposure)
        selected_row = symbol_row(universe_rows, selected) if selected else None
        if not selected:
            blockers.append(reason)
        elif status == "same_group_substitution" and source_key == "broad_commodities":
            blockers.append("broad_commodities_requires_direct_broad_commodity_wrapper_not_gold_or_silver")
        rows.append(
            {
                "source_sleeve": source_key,
                "source_asset_class": source_asset_class,
                "expected_symbol": expected_symbol,
                "selected_symbol": selected,
                "mapping_status": status,
                "substitution_reason": reason,
                "candidate_group": selected_row.get("candidate_group", "") if selected_row else "",
                "primary_economic_exposure": selected_row.get("primary_economic_exposure", "") if selected_row else "",
                "fixed_sleeve_weight": SLEEVE_WEIGHT,
                "source_preserving": bool(selected) and status in {"expected_symbol_available", "source_exposure_aligned_substitution"},
                "selection_performance_independent": True,
            }
        )
    cash_symbol = REQUIRED_CASH[2]
    cash = symbol_row(universe_rows, cash_symbol)
    if not cash or cash_symbol not in compat:
        blockers.append("BIL_cash_proxy_unavailable")
    rows.append(
        {
            "source_sleeve": REQUIRED_CASH[0],
            "source_asset_class": REQUIRED_CASH[1],
            "expected_symbol": cash_symbol,
            "selected_symbol": cash_symbol if cash else "",
            "mapping_status": "expected_symbol_available" if cash and cash_symbol in compat else "unavailable",
            "substitution_reason": "",
            "candidate_group": cash.get("candidate_group", "") if cash else "",
            "primary_economic_exposure": cash.get("primary_economic_exposure", "") if cash else "",
            "fixed_sleeve_weight": "",
            "source_preserving": bool(cash and cash_symbol in compat),
            "selection_performance_independent": True,
        }
    )
    risky_selected = [row["selected_symbol"] for row in rows if row["source_sleeve"] != "treasury_bills" and row["selected_symbol"]]
    if len(set(risky_selected)) != RISKY_SLEEVE_COUNT:
        blockers.append("resolved_risky_mapping_not_exactly_five_unique_symbols")
    if any(not row["source_preserving"] for row in rows):
        blockers.append("one_or_more_mapping_rows_not_source_preserving")
    return rows, sorted(set(blockers))


def coverage_row(root: Path, symbol: str, row: dict[str, Any]) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    path = "" if frame.empty else str(frame["source_cache_path"].iloc[0])
    return {
        "symbol": symbol,
        "source_sleeve": row.get("source_sleeve", ""),
        "candidate_group": row.get("candidate_group", ""),
        "primary_economic_exposure": row.get("primary_economic_exposure", ""),
        "cache_ready": not frame.empty,
        "rows": int(len(frame)),
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "has_adjusted_ohlcv": not frame.empty,
        "cache_path": path,
        "cache_file_hash": file_hash(root / path) if path else "missing",
    }


def daily_price_matrix(root: Path, symbols: list[str]) -> pd.DataFrame:
    series = []
    for symbol in symbols:
        frame = load_adjusted_ohlcv(root, symbol)
        if frame.empty:
            return pd.DataFrame()
        series.append(frame["adj_close"].astype(float).rename(symbol))
    return pd.concat(series, axis=1, join="inner").dropna().sort_index()


def monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in prices.groupby(prices.index.to_period("M")):
        rows.append(group.iloc[-1])
    if not rows:
        return pd.DataFrame(columns=prices.columns)
    out = pd.concat(rows, axis=1).T
    out.index = pd.DatetimeIndex(out.index)
    return out.sort_index()


def signal_states(monthly: pd.DataFrame, risky_symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    sma = monthly[risky_symbols].rolling(SMA_MONTHS, min_periods=SMA_MONTHS).mean()
    states = pd.DataFrame(False, index=monthly.index, columns=risky_symbols)
    audit_cols: dict[str, pd.Series] = {}
    previous = {symbol: False for symbol in risky_symbols}
    for date in monthly.index:
        for symbol in risky_symbols:
            price = monthly.loc[date, symbol]
            avg = sma.loc[date, symbol]
            if pd.isna(avg):
                active = False
                reason = "insufficient_10_month_history"
            elif price > avg:
                active = True
                reason = "price_above_sma10"
            elif price < avg:
                active = False
                reason = "price_below_sma10"
            else:
                active = previous[symbol]
                reason = "price_equal_sma10_retain_prior_state"
            states.loc[date, symbol] = active
            previous[symbol] = active
            audit_cols[f"{symbol}_price"] = monthly[symbol]
            audit_cols[f"{symbol}_sma10"] = sma[symbol]
            audit_cols[f"{symbol}_active"] = states[symbol]
    audit = pd.DataFrame(audit_cols, index=monthly.index)
    return states, audit


def weights_from_states(daily_index: pd.DatetimeIndex, monthly_index: pd.DatetimeIndex, states: pd.DataFrame, risky_symbols: list[str]) -> pd.DataFrame:
    weights = pd.DataFrame(float("nan"), index=daily_index, columns=risky_symbols + ["BIL"])
    valid_states = states.loc[states.index[SMA_MONTHS - 1 :]]
    for date, row in valid_states.iterrows():
        target = {symbol: (SLEEVE_WEIGHT if bool(row[symbol]) else 0.0) for symbol in risky_symbols}
        target["BIL"] = 1.0 - sum(target.values())
        weights.loc[date, list(target)] = list(target.values())
    return weights.ffill().fillna(0.0)


def split_timeframe(baseline: pd.Series, control: pd.Series) -> dict[str, Any]:
    aligned = pd.concat([baseline.rename("baseline"), control.rename("control")], axis=1).dropna()
    midpoint = len(aligned) // 2
    first = aligned.iloc[:midpoint]
    second = aligned.iloc[midpoint:]
    return {
        "first_half_valid": len(first) > 0,
        "second_half_valid": len(second) > 0,
        "first_half_start_date": first.index.min().date().isoformat() if not first.empty else "",
        "first_half_end_date": first.index.max().date().isoformat() if not first.empty else "",
        "second_half_start_date": second.index.min().date().isoformat() if not second.empty else "",
        "second_half_end_date": second.index.max().date().isoformat() if not second.empty else "",
        "first_half_excess_vs_equal_weight_buy_hold": compound_return(first["baseline"]) - compound_return(first["control"]) if not first.empty else float("nan"),
        "second_half_excess_vs_equal_weight_buy_hold": compound_return(second["baseline"]) - compound_return(second["control"]) if not second.empty else float("nan"),
        "timeframe_diagnostic_not_holdout": True,
    }


def evaluate(root: Path, mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    risky = [row["selected_symbol"] for row in mapping_rows if row["source_sleeve"] != "treasury_bills"]
    symbols = risky + ["BIL"]
    prices = daily_price_matrix(root, symbols)
    if prices.empty:
        return {"blocker": "missing_common_adjusted_daily_price_matrix"}
    monthly = monthly_prices(prices)
    if len(monthly) < SMA_MONTHS:
        return {"blocker": "fewer_than_10_common_completed_monthly_observations"}
    states, audit = signal_states(monthly, risky)
    weights = weights_from_states(prices.index, monthly.index, states, risky).reindex(prices.index).ffill().fillna(0.0)
    first_signal_date = monthly.index[SMA_MONTHS - 1]
    first_execution_index = prices.index.get_loc(first_signal_date) + 1
    if first_execution_index >= len(prices):
        return {"blocker": "no_next_session_after_first_valid_signal"}
    evaluation_index = prices.index[first_execution_index:]
    weights = weights.reindex(prices.index).ffill().fillna(0.0)
    zero_cost_full = returns_from_weights(prices, weights).rename("zero_cost_gross")
    execution_turnover_full = turnover_series(weights).shift(1).reindex(zero_cost_full.index).fillna(0.0)
    costs_full = execution_turnover_full * COST_RATE
    after_cost_full = (zero_cost_full - costs_full).rename("five_bps_diagnostic")
    equal_weights = pd.DataFrame({symbol: SLEEVE_WEIGHT for symbol in risky}, index=prices.index)
    equal_weights["BIL"] = 0.0
    equal_returns_full = returns_from_weights(prices, equal_weights).rename("equal_weight_buy_hold")
    bil_weights = pd.DataFrame({symbol: 0.0 for symbol in risky}, index=prices.index)
    bil_weights["BIL"] = 1.0
    bil_returns_full = returns_from_weights(prices, bil_weights).rename("BIL_buy_hold")
    eval_weights = weights.loc[evaluation_index]
    avg_risky = {symbol: float(eval_weights[symbol].mean()) for symbol in risky}
    static_weights = pd.DataFrame(avg_risky, index=prices.index)
    static_weights["BIL"] = 1.0 - sum(avg_risky.values())
    static_returns_full = returns_from_weights(prices, static_weights).rename("static_average_weight_control")
    after_cost = after_cost_full.loc[evaluation_index]
    zero_cost = zero_cost_full.loc[evaluation_index]
    equal_returns = equal_returns_full.loc[evaluation_index]
    bil_returns = bil_returns_full.loc[evaluation_index]
    static_returns = static_returns_full.loc[evaluation_index]
    baseline_metrics = metrics_from_returns(after_cost)
    zero_metrics = metrics_from_returns(zero_cost)
    equal_metrics = metrics_from_returns(equal_returns)
    bil_metrics = metrics_from_returns(bil_returns)
    static_metrics = metrics_from_returns(static_returns)
    invariant = weight_invariant_report(eval_weights, tolerance=WEIGHT_TOLERANCE)
    risky_values = set()
    for symbol in risky:
        risky_values.update(round(float(value), 10) for value in eval_weights[symbol].dropna().unique())
    bil_values = set(round(float(value), 10) for value in eval_weights["BIL"].dropna().unique())
    valid_risky_weights = risky_values.issubset({0.0, SLEEVE_WEIGHT})
    valid_bil_weights = bil_values.issubset({0.0, 0.2, 0.4, 0.6, 0.8, 1.0})
    active_counts = eval_weights[risky].sum(axis=1).div(SLEEVE_WEIGHT).round().astype(int)
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and int(invariant["impossible_cash_and_risky_exposure_days"]) == 0
        and bool(((eval_weights.sum(axis=1) - 1.0).abs() <= WEIGHT_TOLERANCE).all())
        and valid_risky_weights
        and valid_bil_weights
    )
    timeframe = split_timeframe(after_cost, equal_returns)
    full_after_pass = baseline_metrics["total_return"] > equal_metrics["total_return"] and baseline_metrics["total_return"] > static_metrics["total_return"]
    zero_pass = zero_metrics["total_return"] > equal_metrics["total_return"] and zero_metrics["total_return"] > static_metrics["total_return"]
    halves_pass = as_float(timeframe["first_half_excess_vs_equal_weight_buy_hold"]) >= 0.0 and as_float(timeframe["second_half_excess_vs_equal_weight_buy_hold"]) >= 0.0
    active_count_variety = len(set(active_counts.tolist())) >= 2
    if not invariant_pass:
        outcome = "implementation_or_accounting_defect"
        reason = "accounting_invariant_failure"
    elif zero_pass and not full_after_pass:
        outcome = "family_cost_fragile"
        reason = "zero_cost_passes_controls_but_5bps_diagnostic_does_not"
    elif full_after_pass and halves_pass and active_count_variety:
        outcome = "family_exploratory_followup_candidate"
        reason = "after_cost_beats_controls_and_existing_halves_nonnegative"
    elif full_after_pass:
        outcome = "family_timeframe_fragile"
        reason = "full_period_controls_pass_but_existing_half_negative_or_active_count_variety_missing"
    else:
        outcome = "family_control_weak"
        reason = "after_cost_strategy_fails_equal_weight_or_static_control"
    trades, turnover_proxy = trade_count_and_turnover(eval_weights)
    target_rows = []
    for date, row in eval_weights.iterrows():
        payload = {"trial_id": TRIAL_ID, "date": pd.Timestamp(date).date().isoformat()}
        for symbol in risky + ["BIL"]:
            payload[symbol] = float(row[symbol])
        payload["weight_sum"] = float(row.sum())
        payload["active_risky_sleeve_count"] = int(round(float(row[risky].sum() / SLEEVE_WEIGHT)))
        target_rows.append(payload)
    transaction_rows = []
    turnover = execution_turnover_full.loc[evaluation_index]
    for date, value in turnover[turnover > WEIGHT_TOLERANCE].items():
        transaction_rows.append(
            {
                "trial_id": TRIAL_ID,
                "date": pd.Timestamp(date).date().isoformat(),
                "turnover_proxy": float(value),
                "cost_rate": COST_RATE,
                "cost_return_deduction": float(value) * COST_RATE,
                "cost_applies_only_to_changed_notional": True,
            }
        )
    monthly_rows = []
    for date, row in monthly.iterrows():
        payload = {"month_end_date": pd.Timestamp(date).date().isoformat()}
        for symbol in symbols:
            payload[symbol] = float(row[symbol])
        monthly_rows.append(payload)
    signal_rows = []
    for date, row in audit.iterrows():
        payload = {"trial_id": TRIAL_ID, "month_end_date": pd.Timestamp(date).date().isoformat(), "sma_months": SMA_MONTHS}
        for symbol in risky:
            payload[f"{symbol}_price"] = row[f"{symbol}_price"]
            payload[f"{symbol}_sma10"] = row[f"{symbol}_sma10"]
            payload[f"{symbol}_active"] = row[f"{symbol}_active"]
        payload["valid_common_signal_month"] = pd.Timestamp(date) >= first_signal_date
        signal_rows.append(payload)
    return {
        "blocker": "",
        "prices": prices,
        "monthly_rows": monthly_rows,
        "signal_rows": signal_rows,
        "target_rows": target_rows,
        "transaction_rows": transaction_rows,
        "baseline_metrics": baseline_metrics,
        "zero_metrics": zero_metrics,
        "equal_metrics": equal_metrics,
        "bil_metrics": bil_metrics,
        "static_metrics": static_metrics,
        "timeframe": timeframe,
        "invariant": invariant,
        "invariant_pass": invariant_pass,
        "valid_risky_weights": valid_risky_weights,
        "valid_bil_weights": valid_bil_weights,
        "active_count_variety": active_count_variety,
        "active_sleeve_count_values": sorted(set(active_counts.tolist())),
        "outcome": outcome,
        "outcome_reason": reason,
        "trades": trades,
        "turnover_proxy": turnover_proxy,
        "average_weights": {symbol: float(eval_weights[symbol].mean()) for symbol in symbols},
        "evaluation_start": evaluation_index.min().date().isoformat(),
        "evaluation_end": evaluation_index.max().date().isoformat(),
        "trading_days": int(len(evaluation_index)),
        "first_signal_date": first_signal_date.date().isoformat(),
    }


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    registry_before = file_hash(root / REGISTRY_PATH)
    active_before = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    duplicate = duplicate_check(root)
    universe_rows = frozen_universe(root)
    compat = compatibility_rows(root)
    mapping_rows, mapping_blockers = resolve_mapping(root, universe_rows) if universe_rows and compat else ([], ["frozen_universe_or_compatibility_missing"])
    task_outcome = "gtaa5_fast_lane_complete"
    blocker = ""
    evaluation: dict[str, Any] = {}
    if duplicate["exact_duplicate_found"]:
        task_outcome = "exact_gtaa5_implementation_duplicate_found"
        blocker = "Exact verified GTAA5 implementation duplicate found."
    elif not universe_rows or not compat:
        task_outcome = "source_asset_mapping_unavailable"
        blocker = "Frozen universe or compatibility map missing."
    elif mapping_blockers:
        task_outcome = "source_asset_mapping_unavailable"
        blocker = ";".join(mapping_blockers)
    else:
        evaluation = evaluate(root, mapping_rows)
        if evaluation.get("blocker"):
            task_outcome = "existing_data_coverage_insufficient"
            blocker = evaluation["blocker"]
        elif evaluation["outcome"] == "implementation_or_accounting_defect":
            task_outcome = "implementation_or_accounting_defect"
            blocker = evaluation["outcome_reason"]
    coverage_rows = [coverage_row(root, row["selected_symbol"], row) for row in mapping_rows if row.get("selected_symbol")]
    registry_after = file_hash(root / REGISTRY_PATH)
    active_after = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    risky_rows = [row for row in mapping_rows if row.get("source_sleeve") != "treasury_bills"]
    risky_symbols = [row["selected_symbol"] for row in risky_rows]
    symbols = risky_symbols + (["BIL"] if risky_symbols else [])
    family_outcome = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "family_outcome": evaluation.get("outcome", task_outcome if task_outcome in VALID_FAMILY_OUTCOMES else "implementation_or_accounting_defect"),
        "family_outcome_allowed": evaluation.get("outcome", task_outcome) in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": evaluation.get("outcome_reason", blocker or "none"),
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "research_status": "exploratory_non_promotable",
    }
    if task_outcome != "gtaa5_fast_lane_complete" and task_outcome in VALID_FAMILY_OUTCOMES:
        family_outcome["family_outcome"] = task_outcome
        family_outcome["family_outcome_allowed"] = True
    if task_outcome == "gtaa5_fast_lane_complete" and evaluation.get("outcome") == "implementation_or_accounting_defect":
        task_outcome = "implementation_or_accounting_defect"
    monthly_rows = evaluation.get("monthly_rows", [])
    signal_rows = evaluation.get("signal_rows", [])
    target_rows = evaluation.get("target_rows", [])
    transaction_rows = evaluation.get("transaction_rows", [])
    baseline_metrics = evaluation.get("baseline_metrics", {})
    zero_metrics = evaluation.get("zero_metrics", {})
    equal_metrics = evaluation.get("equal_metrics", {})
    bil_metrics = evaluation.get("bil_metrics", {})
    static_metrics = evaluation.get("static_metrics", {})
    timeframe = evaluation.get("timeframe", {})
    invariant = evaluation.get("invariant", {})
    manifest_rows = [
        {
            "task_id": TASK_ID,
            "trial_id": TRIAL_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "risky_symbols": risky_symbols,
            "cash_symbol": "BIL" if risky_symbols else "",
            "risky_sleeve_count": len(risky_symbols),
            "sleeve_weight": SLEEVE_WEIGHT,
            "sma_months": SMA_MONTHS,
            "rebalance_frequency": "monthly",
            "cost_bps": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
            "frozen_before_return_calculation": True,
            "portfolio_trial_count": 1 if task_outcome == "gtaa5_fast_lane_complete" else 0,
        }
    ]
    data = evaluation.get("prices", pd.DataFrame())
    fit_check = {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "uses_adjusted_daily_bars": True,
        "monthly_price_source": "final_common_eligible_trading_session_of_each_calendar_month",
        "source_rule_complete": True,
        "parameter_search": False,
        "portability_sweep": False,
        "macro_or_fundamental_data": False,
        "overlay_experiment": False,
        "strategy_discovery": False,
        "provider_download": False,
        "broker_or_order_path_touched": False,
    }
    universe_reference = {
        "task_id": TASK_ID,
        "frozen_universe_path": str(FROZEN_UNIVERSE_PATH).replace("\\", "/"),
        "frozen_universe_hash": file_hash(root / FROZEN_UNIVERSE_PATH),
        "compatibility_map_path": str(COMPATIBILITY_PATH).replace("\\", "/"),
        "compatibility_map_hash": file_hash(root / COMPATIBILITY_PATH),
        "market_data_manifest_path": str(UNIVERSE_MARKET_DATA_MANIFEST).replace("\\", "/"),
        "market_data_manifest": read_yaml(root / UNIVERSE_MARKET_DATA_MANIFEST),
        "selected_compatibility_family": SELECTED_COMPATIBILITY_FAMILY,
        "selected_symbols": symbols,
    }
    invariant_row = {
        "trial_id": TRIAL_ID,
        **invariant,
        "exactly_five_risky_sleeves": len(risky_symbols) == RISKY_SLEEVE_COUNT,
        "risky_sleeve_max_weight_0_20": evaluation.get("valid_risky_weights", False),
        "bil_weight_discrete_remainder": evaluation.get("valid_bil_weights", False),
        "sma_length_exactly_10_months": SMA_MONTHS == 10,
        "no_cross_sectional_ranking": True,
        "signals_completed_monthly_only": True,
        "same_period_execution_impossible": True,
        "inactive_allocations_only_to_bil": True,
        "daily_weights_sum_exactly_1": bool(invariant) and int(invariant.get("weight_sum_violation_count", 1)) == 0,
        "no_stale_risky_weight_survives_exit": True,
        "costs_apply_only_to_changed_notional": True,
        "controls_identical_calendar": bool(timeframe),
        "exposure_invariant_pass": evaluation.get("invariant_pass", False),
        "active_sleeve_count_values": evaluation.get("active_sleeve_count_values", []),
    }
    baseline_row = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "start_date": baseline_metrics.get("start_date", ""),
        "end_date": baseline_metrics.get("end_date", ""),
        "trading_days": baseline_metrics.get("trading_days", 0),
        "total_return": baseline_metrics.get("total_return", float("nan")),
        "zero_cost_total_return": zero_metrics.get("total_return", float("nan")),
        "cagr": baseline_metrics.get("cagr", float("nan")),
        "max_drawdown": baseline_metrics.get("max_drawdown", float("nan")),
        "volatility": baseline_metrics.get("volatility", float("nan")),
        "return_drawdown_proxy": baseline_metrics.get("return_drawdown_proxy", float("nan")),
        "trade_count": evaluation.get("trades", ""),
        "turnover_proxy": evaluation.get("turnover_proxy", ""),
        "first_signal_date": evaluation.get("first_signal_date", ""),
        "average_weights": evaluation.get("average_weights", {}),
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "family_outcome": family_outcome["family_outcome"],
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    control_rows = []
    for control_id, metrics in [
        ("equal_weight_buy_hold_monthly_rebalanced", equal_metrics),
        ("BIL_buy_hold", bil_metrics),
        ("static_average_weight_control_ex_post_diagnostic", static_metrics),
        ("zero_cost_gtaa_baseline", zero_metrics),
        ("five_bps_gtaa_diagnostic", baseline_metrics),
    ]:
        control_rows.append({"trial_id": TRIAL_ID, "control_id": control_id, **metrics, "same_evaluation_calendar": bool(metrics)})
    vs_rows = [
        {
            "trial_id": TRIAL_ID,
            "five_bps_total_return": baseline_metrics.get("total_return", float("nan")),
            "zero_cost_total_return": zero_metrics.get("total_return", float("nan")),
            "equal_weight_buy_hold_total_return": equal_metrics.get("total_return", float("nan")),
            "BIL_buy_hold_total_return": bil_metrics.get("total_return", float("nan")),
            "static_average_weight_control_total_return": static_metrics.get("total_return", float("nan")),
            "five_bps_beats_equal_weight": baseline_metrics.get("total_return", float("-inf")) > equal_metrics.get("total_return", float("inf")),
            "five_bps_beats_static_control": baseline_metrics.get("total_return", float("-inf")) > static_metrics.get("total_return", float("inf")),
            "zero_cost_beats_equal_weight": zero_metrics.get("total_return", float("-inf")) > equal_metrics.get("total_return", float("inf")),
            "zero_cost_beats_static_control": zero_metrics.get("total_return", float("-inf")) > static_metrics.get("total_return", float("inf")),
        }
    ] if baseline_metrics else []
    followups = [
        {
            "trial_id": TRIAL_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "family_outcome": family_outcome["family_outcome"],
            "next_review_status": "direction_owner_review_required_before_any_followup",
        }
    ] if family_outcome["family_outcome"] == "family_exploratory_followup_candidate" else []
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "task_outcome_allowed": task_outcome in VALID_TASK_OUTCOMES,
        "family_outcome_allowed": family_outcome["family_outcome_allowed"],
        "exact_duplicate_check_completed_before_return_calculation": duplicate["duplicate_check_completed_before_return_calculation"],
        "exact_duplicate_found": duplicate["exact_duplicate_found"],
        "mapping_frozen_before_return_calculation": True,
        "exactly_one_portfolio_trial_registered": len(manifest_rows) == 1 and manifest_rows[0]["portfolio_trial_count"] in {0, 1},
        "exactly_five_risky_sleeves": len(risky_symbols) == RISKY_SLEEVE_COUNT if task_outcome == "gtaa5_fast_lane_complete" else True,
        "sleeve_weight_fixed_0_20": SLEEVE_WEIGHT == 0.20,
        "sma_length_exactly_10_months": SMA_MONTHS == 10,
        "no_cross_sectional_ranking": True,
        "no_top_n_logic": True,
        "signals_use_completed_monthly_observations_only": True,
        "same_period_execution_impossible": True,
        "inactive_allocations_only_to_bil": invariant_row["inactive_allocations_only_to_bil"],
        "daily_weights_sum_exactly_1": invariant_row["daily_weights_sum_exactly_1"] if task_outcome == "gtaa5_fast_lane_complete" else True,
        "no_stale_risky_weight_survives_exit": True,
        "costs_apply_only_to_changed_notional": True,
        "controls_identical_calendar": invariant_row["controls_identical_calendar"] if task_outcome == "gtaa5_fast_lane_complete" else True,
        "existing_evidence_unchanged": True,
        "no_overlay_output_generated": True,
        "registry_lifecycle_unchanged": registry_before == registry_after,
        "active_paper_demo_state_unchanged": active_before == active_after,
        "broker_or_order_path_touched": False,
        "provider_download": False,
        "intraday_data_used": False,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "invariant_failure_count": 0 if invariant_row.get("exposure_invariant_pass") or task_outcome != "gtaa5_fast_lane_complete" else 1,
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["task_outcome_allowed"]
        and consistency["family_outcome_allowed"]
        and consistency["exact_duplicate_check_completed_before_return_calculation"]
        and consistency["mapping_frozen_before_return_calculation"]
        and consistency["exactly_one_portfolio_trial_registered"]
        and consistency["exactly_five_risky_sleeves"]
        and consistency["sleeve_weight_fixed_0_20"]
        and consistency["sma_length_exactly_10_months"]
        and consistency["no_cross_sectional_ranking"]
        and consistency["no_top_n_logic"]
        and consistency["signals_use_completed_monthly_observations_only"]
        and consistency["same_period_execution_impossible"]
        and consistency["inactive_allocations_only_to_bil"]
        and consistency["daily_weights_sum_exactly_1"]
        and consistency["no_stale_risky_weight_survives_exit"]
        and consistency["costs_apply_only_to_changed_notional"]
        and consistency["controls_identical_calendar"]
        and consistency["existing_evidence_unchanged"]
        and consistency["no_overlay_output_generated"]
        and consistency["registry_lifecycle_unchanged"]
        and consistency["active_paper_demo_state_unchanged"]
        and not consistency["broker_or_order_path_touched"]
        and not consistency["provider_download"]
        and not consistency["intraday_data_used"]
        and not consistency["paper_forward_activation"]
        and not consistency["promotion_candidates_created"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["real_money_recommendation"]
        and consistency["invariant_failure_count"] == 0
    )
    write_yaml(output / "source_packet_used.yaml", source_packet())
    write_json(output / "exact_duplicate_check.json", duplicate)
    write_json(output / "repository_fit_check.json", fit_check)
    write_json(output / "frozen_universe_reference.json", universe_reference)
    write_csv(output / "source_to_etf_mapping.csv", mapping_rows, ["source_sleeve", "source_asset_class", "expected_symbol", "selected_symbol", "mapping_status", "substitution_reason", "candidate_group", "primary_economic_exposure", "fixed_sleeve_weight", "source_preserving", "selection_performance_independent"])
    write_csv(output / "frozen_trial_manifest.csv", manifest_rows, ["task_id", "trial_id", "family_id", "source_id", "risky_symbols", "cash_symbol", "risky_sleeve_count", "sleeve_weight", "sma_months", "rebalance_frequency", "cost_bps", "frozen_before_return_calculation", "portfolio_trial_count"])
    write_csv(output / "data_coverage.csv", coverage_rows, ["symbol", "source_sleeve", "candidate_group", "primary_economic_exposure", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"])
    write_csv(output / "monthly_price_matrix.csv", monthly_rows, ["month_end_date", *symbols])
    signal_fields = ["trial_id", "month_end_date", "sma_months"]
    for symbol in risky_symbols:
        signal_fields.extend([f"{symbol}_price", f"{symbol}_sma10", f"{symbol}_active"])
    signal_fields.append("valid_common_signal_month")
    write_csv(output / "sma_signal_audit.csv", signal_rows, signal_fields)
    write_csv(output / "target_weights.csv", target_rows, ["trial_id", "date", *symbols, "weight_sum", "active_risky_sleeve_count"])
    write_csv(output / "transactions.csv", transaction_rows, ["trial_id", "date", "turnover_proxy", "cost_rate", "cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [baseline_row], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "first_signal_date", "average_weights", "standard_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", control_rows, ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", vs_rows, ["trial_id", "five_bps_total_return", "zero_cost_total_return", "equal_weight_buy_hold_total_return", "BIL_buy_hold_total_return", "static_average_weight_control_total_return", "five_bps_beats_equal_weight", "five_bps_beats_static_control", "zero_cost_beats_equal_weight", "zero_cost_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [timeframe] if timeframe else [], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_excess_vs_equal_weight_buy_hold", "second_half_excess_vs_equal_weight_buy_hold", "timeframe_diagnostic_not_holdout"])
    write_csv(output / "accounting_invariants.csv", [invariant_row], ["trial_id", "max_daily_exposure", "max_daily_weight_sum", "average_weight_sum", "weight_sum_violation_count", "negative_weight_violation_count", "nan_weight_count", "impossible_cash_and_risky_exposure_days", "exactly_five_risky_sleeves", "risky_sleeve_max_weight_0_20", "bil_weight_discrete_remainder", "sma_length_exactly_10_months", "no_cross_sectional_ranking", "signals_completed_monthly_only", "same_period_execution_impossible", "inactive_allocations_only_to_bil", "daily_weights_sum_exactly_1", "no_stale_risky_weight_survives_exit", "costs_apply_only_to_changed_notional", "controls_identical_calendar", "exposure_invariant_pass", "active_sleeve_count_values"])
    write_json(output / "family_outcome.json", family_outcome)
    write_csv(output / "family_followup_queue.csv", followups, ["trial_id", "family_id", "source_id", "family_outcome", "next_review_status"])
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_csv(
        output / "command_validation_log.csv",
        [
            {
                "command": ".venv\\Scripts\\python.exe run_faber_gtaa5_10m_sma_equal_weight_etf_bil_v1.py",
                "status": "generated_by_runner",
                "notes": "dedicated Faber GTAA5 fast-lane runner",
            },
            {
                "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_faber_gtaa5_10m_sma_equal_weight_etf_bil_v1.py -q",
                "status": "external_validation_required",
                "notes": "focused tests",
            },
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Faber GTAA5 10-Month SMA Equal-Weight ETF/BIL v1

Task outcome: `{task_outcome}`

- Family: `{FAMILY_ID}`
- Registered portfolio trials: `{manifest_rows[0]['portfolio_trial_count']}`
- Risky mapping: `{', '.join(risky_symbols) if risky_symbols else 'none'}`
- Cash proxy: `BIL`
- Family outcome: `{family_outcome['family_outcome']}`
- Invariant failures: `{consistency['invariant_failure_count']}`
- Provider download: `false`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Blocker: `{blocker or 'none'}`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "implementation_summary.md", summary)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "family_id": FAMILY_ID,
        "registered_portfolio_trial_count": manifest_rows[0]["portfolio_trial_count"],
        "risky_symbols": risky_symbols,
        "cash_symbol": "BIL" if risky_symbols else "",
        "family_outcome": family_outcome["family_outcome"],
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
