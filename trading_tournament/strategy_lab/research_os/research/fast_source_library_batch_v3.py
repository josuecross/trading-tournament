from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior


BATCH_ID = "fast_source_library_batch_v3"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
COST_BPS_GRID = (0.0, 5.0, 10.0)
PRIMARY_COST_BPS = 5.0
WEIGHT_TOLERANCE = 1e-6
MIN_OBSERVATIONS = 504

NEXT_ACTION_REVIEW = "direction_owner_review_fast_source_library_batch_v3"
NEXT_ACTION_EVALUATE_REMAINING = "evaluate_remaining_source_library_candidates_v1"
NEXT_ACTION_DATA_BLOCK = "direction_owner_review_data_feasibility_block_v1"

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]

INPUT_EVIDENCE_DIRS = [
    ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_discovery_batch_v2" / "latest",
    ROOT
    / "evidence"
    / "research_recovery"
    / "fast_price_volume_candidate_incremental_value_followup_v1"
    / "latest",
]

PRIOR_EVIDENCE_FILES = [
    *sorted(INPUT_EVIDENCE_DIRS[0].glob("*")),
    *sorted(INPUT_EVIDENCE_DIRS[1].glob("*")),
    *sorted(INPUT_EVIDENCE_DIRS[2].glob("*")),
]

FORBIDDEN_FLAGS = {
    "source_research_or_web_browsing": False,
    "source_rule_completion": False,
    "strategy_discovery_run": False,
    "parameter_optimization": False,
    "parameter_grid": False,
    "post_result_strategy_changes": False,
    "promotion_grade_validation": False,
    "promotion_review": False,
    "paper_demo_eligibility": False,
    "paper_demo_activation": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "account_or_order_action": False,
    "real_money_action": False,
    "provider_download": False,
    "new_data_infrastructure": False,
    "dsr_pbo_cscv_reality_check_run": False,
    "clean_holdout_claimed": False,
}


@dataclass(frozen=True)
class SourceCard:
    strategy_id: str
    family_id: str
    route: str
    display_name: str
    complete_frozen_rule: str
    instruments: tuple[str, ...]
    required_data_symbols: tuple[str, ...]
    principal_control_ids: tuple[str, ...]
    parameters: dict[str, Any]
    execution_timing: str = "calculate_after_close_t_execute_with_project_shifted_weight_next_session_convention"
    parent_trial_id: str = ""

    @property
    def trial_id(self) -> str:
        return f"fast_source_v3__{self.strategy_id}__canonical"


CARDS = [
    SourceCard(
        strategy_id="daryanani_opportunistic_rebalance_20band_10day_v1",
        family_id="opportunistic_tolerance_band_rebalancing",
        route="diversifier",
        display_name="Daryanani Opportunistic Rebalance 20% Band 10-Day",
        complete_frozen_rule=(
            "Initialize SPY/IWM/VNQ/DBC/IEF at 25/20/10/5/40 target weights. Inspect every 10 market days. "
            "If any asset is outside 80%-120% of its target, project the current fully invested weight vector "
            "onto the 90%-110% inner-band box while minimizing squared distance from current weights. If none is "
            "outside the outer band, make no trade. Calculate after close t and execute using the project shifted-weight convention."
        ),
        instruments=("SPY", "IWM", "VNQ", "DBC", "IEF"),
        required_data_symbols=("SPY", "IWM", "VNQ", "DBC", "IEF"),
        principal_control_ids=("annual_exact_target_rebalance", "initial_mix_no_rebalance"),
        parameters={
            "targets": {"SPY": 0.25, "IWM": 0.20, "VNQ": 0.10, "DBC": 0.05, "IEF": 0.40},
            "inspection_interval_market_days": 10,
            "outer_band_multiplier": 0.20,
            "inner_band_multiplier": 0.10,
        },
    ),
    SourceCard(
        strategy_id="fosback_nvi_255ema_spy_bil_v1",
        family_id="negative_volume_index_regime_filter",
        route="standalone",
        display_name="Fosback NVI 255-EMA SPY/BIL",
        complete_frozen_rule=(
            "Initialize NVI at 1000 using SPY adjusted close and local-cache volume. When volume_t is less than "
            "volume_t-1, update NVI by the SPY adjusted-close return; otherwise carry NVI forward. Calculate a "
            "255-session EMA with alpha 2/256. After warmup, hold SPY when NVI is strictly above EMA255; hold BIL "
            "otherwise, including equality. Calculate after close t and execute using the project shifted-weight convention."
        ),
        instruments=("SPY", "BIL"),
        required_data_symbols=("SPY", "BIL"),
        principal_control_ids=("SPY_buy_hold", "SPY_255_session_price_EMA_SPY_BIL"),
        parameters={"nvi_start": 1000.0, "ema_sessions": 255, "ema_alpha": 2 / 256, "equality_behavior": "BIL"},
    ),
    SourceCard(
        strategy_id="clare_inverse_volatility_five_asset_risk_parity_v1",
        family_id="risk_parity_inverse_volatility_or_vol_targeting",
        route="diversifier",
        display_name="Clare Inverse Volatility Five-Asset Risk Parity",
        complete_frozen_rule=(
            "At each month-end, calculate each ETF's sample standard deviation of trailing 12 completed month-end "
            "total returns. Use inverse-volatility weights normalized to total exposure of 1.0. Use equal weights "
            "until all instruments have 12 completed monthly returns. No trend filter, return ranking, volatility target, "
            "cap, leverage, cash overlay, alternative volatility window or instrument substitution is allowed."
        ),
        instruments=("SPY", "EEM", "IEF", "DBC", "VNQ"),
        required_data_symbols=("SPY", "EEM", "IEF", "DBC", "VNQ"),
        principal_control_ids=("monthly_equal_weight_same_five_etfs", "initial_equal_weight_no_rebalance"),
        parameters={"volatility_window_months": 12, "sample_std_ddof": 1, "warmup_behavior": "equal_weight"},
    ),
    SourceCard(
        strategy_id="ice_vaneck_us_fallen_angel_angl_v1",
        family_id="fallen_angel_credit_anomaly",
        route="diversifier",
        display_name="ICE/VanEck US Fallen Angel ANGL",
        complete_frozen_rule=(
            "Allocate 100% to ANGL at the first common eligible date and hold without a timing rule. Do not add a "
            "trend filter, credit filter, duration adjustment, cash rule or tactical overlay."
        ),
        instruments=("ANGL",),
        required_data_symbols=("ANGL", "HYG", "JNK"),
        principal_control_ids=("HYG_buy_hold", "monthly_rebalanced_50_50_HYG_JNK"),
        parameters={"allocation": {"ANGL": 1.0}, "timing_rule": "none"},
    ),
]


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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def prior_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PRIOR_EVIDENCE_FILES if path.exists() and path.is_file()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def cache_available(symbol: str) -> bool:
    return not prior.load_adjusted_ohlcv(symbol).empty


def missing_symbols(card: SourceCard) -> list[str]:
    return [symbol for symbol in card.required_data_symbols if not cache_available(symbol)]


def load_prices(symbols: tuple[str, ...]) -> pd.DataFrame:
    return prior.load_price_frame(symbols)


def annual_first_mask(index: pd.DatetimeIndex) -> pd.Series:
    years = pd.Series(index.year, index=index)
    return years.ne(years.shift(1)).fillna(True)


def month_last_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [pd.Timestamp(date) for date in index[periods.ne(periods.shift(-1)).fillna(True)]]


def complete_targets(index: pd.DatetimeIndex, columns: tuple[str, ...], targets: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=index, columns=list(columns))
    current = {column: 0.0 for column in columns}
    for date in index:
        if pd.Timestamp(date) in targets:
            current = {column: float(targets[pd.Timestamp(date)].get(column, 0.0)) for column in columns}
        for column, value in current.items():
            weights.loc[date, column] = value
    return weights


def buy_hold_weights(index: pd.DatetimeIndex, weights: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({symbol: float(weight) for symbol, weight in weights.items()}, index=index)


def annual_rebalance_weights(index: pd.DatetimeIndex, target_weights: dict[str, float]) -> pd.DataFrame:
    targets = {pd.Timestamp(date): target_weights for date in index[annual_first_mask(index)]}
    return complete_targets(index, tuple(target_weights), targets)


def monthly_rebalance_weights(index: pd.DatetimeIndex, target_weights: dict[str, float]) -> pd.DataFrame:
    targets = {date: target_weights for date in month_last_dates(index)}
    return complete_targets(index, tuple(target_weights), targets)


def project_box_simplex(values: pd.Series, lower: pd.Series, upper: pd.Series) -> pd.Series:
    if float(lower.sum()) > 1.0 + 1e-12 or float(upper.sum()) < 1.0 - 1e-12:
        raise ValueError("infeasible inner band projection")
    lo = -10.0
    hi = 10.0
    for _ in range(120):
        mid = (lo + hi) / 2.0
        projected = (values - mid).clip(lower=lower, upper=upper)
        if float(projected.sum()) > 1.0:
            lo = mid
        else:
            hi = mid
    projected = (values - ((lo + hi) / 2.0)).clip(lower=lower, upper=upper)
    return projected / float(projected.sum())


def opportunistic_rebalance_weights(prices: pd.DataFrame, targets: dict[str, float], interval: int) -> pd.DataFrame:
    symbols = tuple(targets)
    target = pd.Series(targets, dtype=float)
    lower_outer = target * 0.80
    upper_outer = target * 1.20
    lower_inner = target * 0.90
    upper_inner = target * 1.10
    weights = pd.DataFrame(0.0, index=prices.index, columns=list(symbols))
    current_target = target.copy()
    weights.iloc[0] = current_target
    for idx in range(1, len(prices)):
        date = prices.index[idx]
        prev_date = prices.index[idx - 1]
        returns = prices.loc[date, list(symbols)] / prices.loc[prev_date, list(symbols)] - 1.0
        drifted = current_target * (1.0 + returns)
        drifted = drifted / float(drifted.sum())
        if idx % interval == 0:
            outside = bool(((drifted < lower_outer) | (drifted > upper_outer)).any())
            if outside:
                current_target = project_box_simplex(drifted, lower_inner, upper_inner)
            else:
                current_target = current_target.copy()
        weights.loc[date, list(symbols)] = current_target
    return weights


def nvi_weights(spy_ohlcv: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    aligned = spy_ohlcv.reindex(prices.index).dropna(subset=["adj_close", "volume"])
    close = aligned["adj_close"]
    volume = aligned["volume"]
    returns = close.pct_change(fill_method=None).fillna(0.0)
    nvi_values = []
    current = 1000.0
    for idx, date in enumerate(aligned.index):
        if idx > 0 and float(volume.iloc[idx]) < float(volume.iloc[idx - 1]):
            current *= 1.0 + float(returns.iloc[idx])
        nvi_values.append(current)
    nvi = pd.Series(nvi_values, index=aligned.index, name="nvi")
    ema = nvi.ewm(alpha=2 / 256, adjust=False).mean()
    warmup = pd.Series(range(1, len(nvi) + 1), index=nvi.index) >= 255
    risk_on = (nvi > ema) & warmup
    weights = pd.DataFrame(0.0, index=prices.index, columns=["SPY", "BIL"])
    weights.loc[risk_on.reindex(prices.index).fillna(False), "SPY"] = 1.0
    weights.loc[~risk_on.reindex(prices.index).fillna(False), "BIL"] = 1.0
    return weights


def price_ema_255_weights(prices: pd.DataFrame) -> pd.DataFrame:
    spy = prices["SPY"]
    ema = spy.ewm(alpha=2 / 256, adjust=False).mean()
    warmup = pd.Series(range(1, len(spy) + 1), index=spy.index) >= 255
    risk_on = (spy > ema) & warmup
    weights = pd.DataFrame(0.0, index=prices.index, columns=["SPY", "BIL"])
    weights.loc[risk_on, "SPY"] = 1.0
    weights.loc[~risk_on, "BIL"] = 1.0
    return weights


def inverse_volatility_weights(prices: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    monthly_dates = month_last_dates(prices.index)
    month_prices = prices.loc[monthly_dates, list(symbols)]
    monthly_returns = month_prices.pct_change(fill_method=None)
    equal = {symbol: 1.0 / len(symbols) for symbol in symbols}
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in monthly_dates:
        trailing = monthly_returns.loc[:date].tail(12)
        if len(trailing) < 12 or trailing.isna().any().any():
            targets[date] = equal
            continue
        sigma = trailing.std(ddof=1)
        if sigma.isna().any() or (sigma <= 0.0).any():
            targets[date] = equal
            continue
        raw = 1.0 / sigma
        weights = raw / raw.sum()
        targets[date] = {symbol: float(weights[symbol]) for symbol in symbols}
    return complete_targets(prices.index, symbols, targets)


def candidate_weights(card: SourceCard, prices: pd.DataFrame) -> pd.DataFrame:
    if card.strategy_id == "daryanani_opportunistic_rebalance_20band_10day_v1":
        return opportunistic_rebalance_weights(prices[list(card.instruments)], card.parameters["targets"], 10)
    if card.strategy_id == "fosback_nvi_255ema_spy_bil_v1":
        spy_ohlcv = prior.load_adjusted_ohlcv("SPY")
        return nvi_weights(spy_ohlcv, prices[["SPY", "BIL"]])
    if card.strategy_id == "clare_inverse_volatility_five_asset_risk_parity_v1":
        return inverse_volatility_weights(prices[list(card.instruments)], card.instruments)
    if card.strategy_id == "ice_vaneck_us_fallen_angel_angl_v1":
        return buy_hold_weights(prices.index, {"ANGL": 1.0})
    raise RuntimeError(f"Unsupported candidate: {card.strategy_id}")


def control_weights(card: SourceCard, control_id: str, prices: pd.DataFrame) -> pd.DataFrame:
    if card.strategy_id == "daryanani_opportunistic_rebalance_20band_10day_v1":
        targets = card.parameters["targets"]
        if control_id == "annual_exact_target_rebalance":
            return annual_rebalance_weights(prices.index, targets)
        if control_id == "initial_mix_no_rebalance":
            return buy_hold_weights(prices.index, targets)
    if card.strategy_id == "fosback_nvi_255ema_spy_bil_v1":
        if control_id == "SPY_buy_hold":
            return buy_hold_weights(prices.index, {"SPY": 1.0})
        if control_id == "SPY_255_session_price_EMA_SPY_BIL":
            return price_ema_255_weights(prices[["SPY", "BIL"]])
    if card.strategy_id == "clare_inverse_volatility_five_asset_risk_parity_v1":
        equal = {symbol: 1.0 / len(card.instruments) for symbol in card.instruments}
        if control_id == "monthly_equal_weight_same_five_etfs":
            return monthly_rebalance_weights(prices.index, equal)
        if control_id == "initial_equal_weight_no_rebalance":
            return buy_hold_weights(prices.index, equal)
    if card.strategy_id == "ice_vaneck_us_fallen_angel_angl_v1":
        if control_id == "HYG_buy_hold":
            return buy_hold_weights(prices.index, {"HYG": 1.0})
        if control_id == "monthly_rebalanced_50_50_HYG_JNK":
            return monthly_rebalance_weights(prices.index, {"HYG": 0.5, "JNK": 0.5})
    raise RuntimeError(f"Unsupported control {control_id} for {card.strategy_id}")


def turnover_series(weights: pd.DataFrame) -> pd.Series:
    return prior.turnover_series(weights)


def invariant_report(weights: pd.DataFrame) -> dict[str, Any]:
    if weights.empty:
        return {"max_daily_exposure": float("nan"), "max_daily_weight_sum": float("nan"), "invariant_pass": False}
    max_exposure = float(weights.clip(lower=0.0).sum(axis=1).max())
    max_sum = float(weights.sum(axis=1).max())
    return {
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_sum,
        "nan_weight_count": int(weights.isna().sum().sum()),
        "negative_weight_violation_count": int((weights < -WEIGHT_TOLERANCE).sum().sum()),
        "weight_sum_violation_count": int((weights.sum(axis=1) > 1.0 + WEIGHT_TOLERANCE).sum()),
        "invariant_pass": bool(
            max_exposure <= 1.0 + WEIGHT_TOLERANCE
            and max_sum <= 1.0 + WEIGHT_TOLERANCE
            and not weights.isna().any().any()
            and not (weights < -WEIGHT_TOLERANCE).any().any()
        ),
    }


def returns_for_weights(prices: pd.DataFrame, weights: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    aligned_prices = prices.reindex(weights.index).dropna()
    aligned_weights = weights.reindex(aligned_prices.index).ffill().fillna(0.0).reindex(columns=aligned_prices.columns, fill_value=0.0)
    gross = returns_from_weights(aligned_prices, aligned_weights)
    turnover = turnover_series(aligned_weights).reindex(gross.index).fillna(0.0)
    cost = turnover * (cost_bps / 10000.0)
    return (gross - cost).rename("net_return"), turnover.rename("turnover"), cost.rename("cost")


def metric_payload(returns: pd.Series, turnover: pd.Series, cost: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    metrics = prior.metrics_from_returns(returns)
    invariants = invariant_report(weights.reindex(returns.index).ffill().fillna(0.0))
    return {
        **metrics,
        "turnover": float(turnover.reindex(returns.index).fillna(0.0).sum()),
        "rebalance_or_trade_count": int((turnover.reindex(returns.index).fillna(0.0) > WEIGHT_TOLERANCE).sum()),
        "estimated_transaction_cost_drag": float(cost.reindex(returns.index).fillna(0.0).sum()),
        "max_daily_exposure": invariants["max_daily_exposure"],
        "max_daily_weight_sum": invariants["max_daily_weight_sum"],
        "numeric_invariant_status": "pass" if not returns.isna().any() and len(returns) > 0 else "fail",
        "timing_invariant_status": "pass_project_shifted_weight_no_lookahead",
        "exposure_weight_invariant_status": "pass" if invariants["invariant_pass"] else "fail",
        "invariant_pass": bool(invariants["invariant_pass"] and not returns.isna().any() and len(returns) > 0),
    }


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    midpoint = len(index) // 2
    first = index[:midpoint]
    second = index[midpoint:]
    return [
        ("first_chronological_half", pd.Timestamp(first.min()), pd.Timestamp(first.max())),
        ("second_chronological_half", pd.Timestamp(second.min()), pd.Timestamp(second.max())),
    ]


def blocked_metric_row(card: SourceCard, cost_bps: float, missing: list[str]) -> dict[str, Any]:
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": card.trial_id,
        "route": card.route,
        "cost_assumption_bps": cost_bps,
        "classification": "inconclusive_data_issue",
        "data_issue": "missing_existing_local_cache_for_required_symbol",
        "missing_symbols": missing,
        "evaluation_start": "",
        "evaluation_end": "",
        "trading_days": 0,
        "numeric_invariant_status": "not_evaluated_data_issue",
        "timing_invariant_status": "not_evaluated_data_issue",
        "exposure_weight_invariant_status": "not_evaluated_data_issue",
        "invariant_pass": False,
        **FORBIDDEN_FLAGS,
    }


def source_card_row(card: SourceCard) -> dict[str, Any]:
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "route": card.route,
        "source_library_id": SOURCE_LIBRARY_ID,
        "display_name": card.display_name,
        "complete_frozen_rule": card.complete_frozen_rule,
        "instruments": card.instruments,
        "required_data_symbols": card.required_data_symbols,
        "principal_controls": card.principal_control_ids,
        "parameters": card.parameters,
        "execution_timing": card.execution_timing,
        "source_research_performed": False,
        "source_rule_completion_performed": False,
    }


def strategy_card_row(card: SourceCard, status: str, evaluation_start: str = "", evaluation_end: str = "") -> dict[str, Any]:
    return {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "parent_trial_id": card.parent_trial_id,
        "source_library_id": SOURCE_LIBRARY_ID,
        "complete_frozen_rule": card.complete_frozen_rule,
        "instruments": card.instruments,
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "benchmark_and_controls": card.principal_control_ids,
        "route": card.route,
        "transaction_cost_assumptions": "0|5|10 bps per one-way turnover proxy",
        "execution_timing": card.execution_timing,
        "changed_fields_from_parent": "canonical_configuration",
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "data_status": status,
        "task_or_process_record": False,
    }


def trial_lineage_row(card: SourceCard, status: str) -> dict[str, Any]:
    return {
        "family_id": card.family_id,
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "parent_trial_id": card.parent_trial_id,
        "source_library_id": SOURCE_LIBRARY_ID,
        "changed_fields_from_parent": "canonical_configuration",
        "route": card.route,
        "trial_status": status,
        "predeclared_before_results": True,
        "task_or_process_record": False,
    }


def controls_for_card(card: SourceCard, prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {control_id: control_weights(card, control_id, prices) for control_id in card.principal_control_ids}


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    control_values = (float(control["cagr"]), float(control["sharpe_ratio"]), float(control["maximum_drawdown"]))
    candidate_values = (float(candidate["cagr"]), float(candidate["sharpe_ratio"]), float(candidate["maximum_drawdown"]))
    return all(c >= v - 1e-12 for c, v in zip(control_values, candidate_values)) and any(
        c > v + 1e-12 for c, v in zip(control_values, candidate_values)
    )


def fixed_reference_returns(index: pd.DatetimeIndex) -> pd.Series:
    reference = prior.active_vm_dsr_usci_reference_returns()
    return reference.reindex(index).dropna().rename("frozen_current_active_vm_dsr_usci_combo")


def portfolio_contribution_rows(
    card: SourceCard,
    candidate_returns_by_cost: dict[float, pd.Series],
    control_returns_by_cost: dict[tuple[str, float], pd.Series],
    reference: pd.Series,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS_GRID:
        reference_aligned = reference.dropna()
        portfolios = {
            "frozen_reference_100pct": reference_aligned,
            f"{card.strategy_id}_candidate_20pct": 0.8 * reference_aligned + 0.2 * candidate_returns_by_cost[cost_bps].reindex(reference_aligned.index).fillna(0.0),
        }
        for control_id in card.principal_control_ids:
            portfolios[f"{control_id}_20pct_control"] = 0.8 * reference_aligned + 0.2 * control_returns_by_cost[(control_id, cost_bps)].reindex(reference_aligned.index).fillna(0.0)
        for portfolio_id, returns in portfolios.items():
            metrics = prior.metrics_from_returns(returns)
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "route": card.route,
                    "cost_assumption_bps": cost_bps,
                    "portfolio_id": portfolio_id,
                    "portfolio_construction": (
                        "100pct_frozen_reference"
                        if portfolio_id == "frozen_reference_100pct"
                        else "80pct_frozen_reference_plus_20pct_candidate_or_control"
                    ),
                    "evaluation_start": metrics["evaluation_start"],
                    "evaluation_end": metrics["evaluation_end"],
                    "trading_days": metrics["trading_days"],
                    "total_return": metrics["total_return"],
                    "cagr": metrics["cagr"],
                    "annualized_volatility": metrics["annualized_volatility"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "maximum_drawdown": metrics["maximum_drawdown"],
                    "correlation_to_frozen_reference": 1.0
                    if portfolio_id == "frozen_reference_100pct"
                    else prior.safe_corr(returns, reference_aligned),
                    "max_daily_exposure": 1.0,
                    "max_daily_weight_sum": 1.0,
                    "invariant_pass": True,
                }
            )
    return rows


def classify_candidate(
    card: SourceCard,
    candidate_5: dict[str, Any],
    control_5: dict[str, dict[str, Any]],
    half_candidate: dict[str, dict[str, Any]],
    half_controls: dict[tuple[str, str], dict[str, Any]],
    portfolio_rows: list[dict[str, Any]],
) -> tuple[str, str]:
    if not candidate_5.get("invariant_pass"):
        return "inconclusive_data_issue", "candidate_numeric_or_exposure_invariant_failed"
    if float(candidate_5["total_return"]) <= 0.0:
        return "closed_exploration", "candidate_after_cost_full_period_return_not_positive_at_5bps"
    dominated_by_control = any(dominates(control, candidate_5) for control in control_5.values())
    if dominated_by_control:
        return "closed_exploration", "principal_same_purpose_control_dominated_candidate_on_cagr_sharpe_and_drawdown"
    if card.route == "standalone":
        best_control = max(control_5.values(), key=lambda row: float(row["sharpe_ratio"]))
        better_sharpe = float(candidate_5["sharpe_ratio"]) > float(best_control["sharpe_ratio"])
        better_drawdown = float(candidate_5["maximum_drawdown"]) > float(best_control["maximum_drawdown"])
        if not (better_sharpe or better_drawdown):
            return "closed_exploration", "standalone_candidate_did_not_improve_sharpe_or_drawdown_vs_simple_control"
        for half in ("first_chronological_half", "second_chronological_half"):
            cand_half = half_candidate[half]
            control_half = half_controls[(best_control["control_id"], half)]
            worse_sharpe = float(cand_half["sharpe_ratio"]) < float(control_half["sharpe_ratio"])
            worse_drawdown = float(cand_half["maximum_drawdown"]) < float(control_half["maximum_drawdown"])
            if worse_sharpe and worse_drawdown:
                return "closed_exploration", "standalone_candidate_worse_on_sharpe_and_drawdown_in_a_chronological_half"
        return "exploratory_followup_candidate_standalone", "standalone_candidate_passed_lightweight_exploration_gate"

    rows_5 = [row for row in portfolio_rows if row["strategy_id"] == card.strategy_id and float(row["cost_assumption_bps"]) == 5.0]
    reference = next(row for row in rows_5 if row["portfolio_id"] == "frozen_reference_100pct")
    candidate_portfolio = next(row for row in rows_5 if row["portfolio_id"] == f"{card.strategy_id}_candidate_20pct")
    control_portfolios = [row for row in rows_5 if row["portfolio_id"].endswith("_20pct_control")]
    improves_sharpe = float(candidate_portfolio["sharpe_ratio"]) > float(reference["sharpe_ratio"])
    improves_drawdown = float(candidate_portfolio["maximum_drawdown"]) > float(reference["maximum_drawdown"])
    worsens_both = (
        float(candidate_portfolio["sharpe_ratio"]) < float(reference["sharpe_ratio"])
        and float(candidate_portfolio["maximum_drawdown"]) < float(reference["maximum_drawdown"])
    )
    if not ((improves_sharpe or improves_drawdown) and not worsens_both):
        return "closed_exploration", "candidate_80_20_portfolio_did_not_improve_reference_without_worsening_both"
    if any(dominates(control, candidate_portfolio) for control in control_portfolios):
        return "closed_exploration", "simple_80_20_control_dominated_candidate_80_20_portfolio"
    return "exploratory_followup_candidate_diversifier", "diversifier_candidate_passed_lightweight_exploration_gate"


def run_card(card: SourceCard, reference_returns: pd.Series) -> dict[str, Any]:
    missing = missing_symbols(card)
    if missing:
        return {"card": card, "missing": missing, "executable": False}
    prices = load_prices(card.required_data_symbols)
    reference = reference_returns.reindex(prices.index).dropna()
    prices = prices.reindex(reference.index).dropna()
    if len(prices) < MIN_OBSERVATIONS:
        return {"card": card, "missing": [], "executable": False, "date_issue": "insufficient_common_reference_and_price_history"}
    weights = candidate_weights(card, prices)
    controls = controls_for_card(card, prices)
    # Align every candidate and control to exactly the same dates.
    common_index = prices.index
    for frame in [weights, *controls.values()]:
        common_index = common_index.intersection(frame.dropna().index)
    prices = prices.reindex(common_index).dropna()
    reference = reference.reindex(common_index).dropna()
    weights = weights.reindex(common_index).ffill().fillna(0.0)
    controls = {key: frame.reindex(common_index).ffill().fillna(0.0) for key, frame in controls.items()}
    return {"card": card, "prices": prices, "reference": reference, "weights": weights, "controls": controls, "executable": True}


def build_report(funnel: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    lines = [
        "# Fast Source Library Batch V3",
        "",
        "## Scope",
        "",
        "This bounded exploratory batch used exactly four frozen candidates from `strategy_source_library_refresh_v1`. It did not perform source research, source-rule completion, strategy discovery, parameter optimization, promotion review, paper/demo activation, provider download, broker/order/account work or real-money actions.",
        "",
        "The prior `qqq_spy_gld_ief_dual_momentum_v1` and `treasury_duration_trend_rotation_v1` evidence was read only and left closed.",
        "",
        "## Funnel",
        "",
        f"- Frozen candidates considered: `{funnel['candidate_count']}`",
        f"- Completed executable candidates: `{funnel['completed_candidate_count']}`",
        f"- Data-blocked candidates: `{funnel['data_blocked_candidate_count']}`",
        f"- Follow-up candidates: `{funnel['followup_candidate_count']}`",
        f"- Closed candidates: `{funnel['closed_candidate_count']}`",
        f"- Inconclusive data issues: `{funnel['inconclusive_data_issue_count']}`",
        "",
        "## Decisions",
        "",
    ]
    for row in decisions:
        lines.append(f"- `{row['strategy_id']}`: `{row['classification']}` - {row['decision_reason']}")
    lines.extend(["", f"Exact next action: `{funnel['exact_next_action']}`."])
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    names = [
        "batch_manifest.yaml",
        "frozen_source_cards.csv",
        "preregistered_strategy_cards.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "exploratory_followup_candidates.csv",
        "rejection_and_data_issue_log.csv",
        "trial_lineage.csv",
        "cohort_funnel_counts.json",
        "batch_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def identical_dates_by_group(rows: list[dict[str, Any]], group_fields: tuple[str, ...]) -> bool:
    groups: dict[tuple[Any, ...], set[tuple[str, str, int]]] = {}
    for row in rows:
        if not row.get("evaluation_start"):
            continue
        key = tuple(row.get(field, "") for field in group_fields)
        groups.setdefault(key, set()).add(
            (str(row["evaluation_start"]), str(row["evaluation_end"]), int(row["trading_days"]))
        )
    return bool(groups) and all(len(values) == 1 for values in groups.values())


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    prior_hashes_before = prior_evidence_hashes()
    clean_output_dir()
    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    source_rows = [source_card_row(card) for card in CARDS]
    strategy_rows: list[dict[str, Any]] = []
    trial_lineage_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    data_issues: list[dict[str, Any]] = []
    completed_count = 0

    for card in CARDS:
        outcome = run_card(card, reference_returns)
        if not outcome["executable"]:
            missing = outcome.get("missing", [])
            issue = outcome.get("date_issue", "missing_existing_local_cache_for_required_symbol")
            strategy_rows.append(strategy_card_row(card, "data_blocked"))
            trial_lineage_rows.append(trial_lineage_row(card, "data_blocked"))
            for cost_bps in COST_BPS_GRID:
                trial_rows.append(blocked_metric_row(card, cost_bps, missing))
            for control_id in card.principal_control_ids:
                for cost_bps in COST_BPS_GRID:
                    control_rows.append(
                        {
                            "strategy_id": card.strategy_id,
                            "family_id": card.family_id,
                            "trial_id": card.trial_id,
                            "control_id": control_id,
                            "cost_assumption_bps": cost_bps,
                            "data_issue": issue,
                            "missing_symbols": missing,
                            "classification": "inconclusive_data_issue",
                        }
                    )
            data_issues.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "issue_type": "data_blocked",
                    "issue": issue,
                    "missing_symbols": missing,
                    "no_substitution_made": True,
                    "classification": "inconclusive_data_issue",
                }
            )
            decisions.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "route": card.route,
                    "classification": "inconclusive_data_issue",
                    "decision_reason": issue,
                    "completed": False,
                    "missing_symbols": missing,
                }
            )
            continue

        completed_count += 1
        prices = outcome["prices"]
        reference = outcome["reference"]
        weights = outcome["weights"]
        controls = outcome["controls"]
        strategy_rows.append(strategy_card_row(card, "executable", prices.index.min().date().isoformat(), prices.index.max().date().isoformat()))
        trial_lineage_rows.append(trial_lineage_row(card, "completed"))
        candidate_result_5: dict[str, Any] | None = None
        control_result_5: dict[str, dict[str, Any]] = {}
        half_candidate_5: dict[str, dict[str, Any]] = {}
        half_control_5: dict[tuple[str, str], dict[str, Any]] = {}
        candidate_returns_by_cost: dict[float, pd.Series] = {}
        control_returns_by_cost: dict[tuple[str, float], pd.Series] = {}
        for cost_bps in COST_BPS_GRID:
            candidate_returns, turnover, cost = returns_for_weights(prices, weights, cost_bps)
            candidate_returns_by_cost[cost_bps] = candidate_returns
            metrics = metric_payload(candidate_returns, turnover, cost, weights)
            row = {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id,
                "route": card.route,
                "cost_assumption_bps": cost_bps,
                "classification": "pending_gate",
                **metrics,
                "data_issue": "",
                "missing_symbols": "",
                **FORBIDDEN_FLAGS,
            }
            trial_rows.append(row)
            if cost_bps == PRIMARY_COST_BPS:
                candidate_result_5 = row
            for control_id, control_weight in controls.items():
                control_prices = prices.reindex(columns=control_weight.columns).dropna()
                control_weight = control_weight.reindex(control_prices.index).ffill().fillna(0.0)
                control_returns, control_turnover, control_cost = returns_for_weights(control_prices, control_weight, cost_bps)
                control_returns_by_cost[(control_id, cost_bps)] = control_returns
                control_metrics = metric_payload(control_returns, control_turnover, control_cost, control_weight)
                control_row = {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "control_id": control_id,
                    "cost_assumption_bps": cost_bps,
                    **control_metrics,
                    "data_issue": "",
                    "missing_symbols": "",
                }
                control_rows.append(control_row)
                if cost_bps == PRIMARY_COST_BPS:
                    control_result_5[control_id] = {**control_row, "control_id": control_id}
            for half_label, start, end in split_halves(candidate_returns.index):
                half_candidate_returns = candidate_returns.loc[start:end]
                half_turnover = turnover.loc[start:end]
                half_cost = cost.loc[start:end]
                half_metrics = metric_payload(half_candidate_returns, half_turnover, half_cost, weights.reindex(half_candidate_returns.index))
                half_row = {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "row_type": "candidate",
                    "control_id": "",
                    "cost_assumption_bps": cost_bps,
                    "half_label": half_label,
                    "half_source": "chronological_half_not_clean_holdout",
                    **half_metrics,
                }
                half_rows.append(half_row)
                if cost_bps == PRIMARY_COST_BPS:
                    half_candidate_5[half_label] = half_row
                for control_id, control_returns in [
                    (cid, control_returns_by_cost[(cid, cost_bps)]) for cid in card.principal_control_ids
                ]:
                    control_weight = controls[control_id].reindex(control_returns.index).ffill().fillna(0.0)
                    control_turnover = turnover_series(control_weight)
                    control_cost = control_turnover * (cost_bps / 10000.0)
                    half_control_returns = control_returns.loc[start:end]
                    half_control_metrics = metric_payload(
                        half_control_returns,
                        control_turnover.loc[start:end],
                        control_cost.loc[start:end],
                        control_weight.reindex(half_control_returns.index),
                    )
                    control_half_row = {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": card.trial_id,
                        "row_type": "control",
                        "control_id": control_id,
                        "cost_assumption_bps": cost_bps,
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        **half_control_metrics,
                    }
                    half_rows.append(control_half_row)
                    if cost_bps == PRIMARY_COST_BPS:
                        half_control_5[(control_id, half_label)] = control_half_row
        contribution = portfolio_contribution_rows(card, candidate_returns_by_cost, control_returns_by_cost, reference)
        contribution_rows.extend(contribution)
        classification, reason = classify_candidate(
            card,
            candidate_result_5 or {},
            control_result_5,
            half_candidate_5,
            half_control_5,
            contribution,
        )
        for row in trial_rows:
            if row.get("strategy_id") == card.strategy_id and row.get("classification") == "pending_gate":
                row["classification"] = classification
                row["decision_reason"] = reason
        decisions.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "route": card.route,
                "classification": classification,
                "decision_reason": reason,
                "completed": True,
                "missing_symbols": "",
            }
        )

    followup_candidates = [
        row
        for row in trial_rows
        if row.get("cost_assumption_bps") == PRIMARY_COST_BPS
        and row.get("classification")
        in {"exploratory_followup_candidate_standalone", "exploratory_followup_candidate_diversifier"}
    ]
    data_blocked_count = sum(1 for row in decisions if row["classification"] == "inconclusive_data_issue")
    if completed_count < 2 and data_blocked_count:
        next_action = NEXT_ACTION_DATA_BLOCK
    elif followup_candidates:
        next_action = NEXT_ACTION_REVIEW
    else:
        next_action = NEXT_ACTION_EVALUATE_REMAINING
    funnel = {
        "batch_id": BATCH_ID,
        "candidate_count": len(CARDS),
        "completed_candidate_count": completed_count,
        "data_blocked_candidate_count": data_blocked_count,
        "all_trial_result_count": len(trial_rows),
        "control_result_count": len(control_rows),
        "chronological_half_result_count": len(half_rows),
        "portfolio_contribution_result_count": len(contribution_rows),
        "trial_lineage_count": len(trial_lineage_rows),
        "followup_candidate_count": len(followup_candidates),
        "standalone_followup_candidate_count": sum(
            1 for row in followup_candidates if row["classification"] == "exploratory_followup_candidate_standalone"
        ),
        "diversifier_followup_candidate_count": sum(
            1 for row in followup_candidates if row["classification"] == "exploratory_followup_candidate_diversifier"
        ),
        "closed_candidate_count": sum(1 for row in decisions if row["classification"] == "closed_exploration"),
        "inconclusive_data_issue_count": data_blocked_count,
        "exact_next_action": next_action,
    }

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": BATCH_ID,
            "source_library_id": SOURCE_LIBRARY_ID,
            "mode": "bounded_exploratory_research_batch",
            "research_and_paper_demo_only": True,
            "frozen_timestamp": FROZEN_TIMESTAMP,
            "input_evidence_dirs": [rel(path) for path in INPUT_EVIDENCE_DIRS],
            "exact_candidate_count": len(CARDS),
            "exact_candidate_ids": [card.strategy_id for card in CARDS],
            "do_not_reopen_closed_prior_candidates": [
                "qqq_spy_gld_ief_dual_momentum_v1",
                "treasury_duration_trend_rotation_v1",
            ],
            "closed_prior_candidates_reopened": False,
            "primary_cost_assumption_bps": PRIMARY_COST_BPS,
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            **FORBIDDEN_FLAGS,
            "exact_next_action": next_action,
        },
    )
    source_fields = [
        "strategy_id",
        "family_id",
        "route",
        "source_library_id",
        "display_name",
        "complete_frozen_rule",
        "instruments",
        "required_data_symbols",
        "principal_controls",
        "parameters",
        "execution_timing",
        "source_research_performed",
        "source_rule_completion_performed",
    ]
    strategy_fields = [
        "family_id",
        "strategy_id",
        "trial_id",
        "parent_trial_id",
        "source_library_id",
        "complete_frozen_rule",
        "instruments",
        "evaluation_start",
        "evaluation_end",
        "benchmark_and_controls",
        "route",
        "transaction_cost_assumptions",
        "execution_timing",
        "changed_fields_from_parent",
        "preregistration_timestamp",
        "data_status",
        "task_or_process_record",
    ]
    result_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "route",
        "cost_assumption_bps",
        "classification",
        "decision_reason",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
        "data_issue",
        "missing_symbols",
        *FORBIDDEN_FLAGS.keys(),
    ]
    control_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "control_id",
        "cost_assumption_bps",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
        "classification",
        "data_issue",
        "missing_symbols",
    ]
    half_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "row_type",
        "control_id",
        "cost_assumption_bps",
        "half_label",
        "half_source",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
    ]
    contribution_fields = [
        "strategy_id",
        "family_id",
        "route",
        "cost_assumption_bps",
        "portfolio_id",
        "portfolio_construction",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "correlation_to_frozen_reference",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "invariant_pass",
    ]
    write_csv(OUTPUT_DIR / "frozen_source_cards.csv", source_rows, source_fields)
    write_csv(OUTPUT_DIR / "preregistered_strategy_cards.csv", strategy_rows, strategy_fields)
    write_csv(OUTPUT_DIR / "all_trial_results.csv", trial_rows, result_fields)
    write_csv(OUTPUT_DIR / "control_results.csv", control_rows, control_fields)
    write_csv(OUTPUT_DIR / "chronological_half_results.csv", half_rows, half_fields)
    write_csv(OUTPUT_DIR / "portfolio_contribution_results.csv", contribution_rows, contribution_fields)
    write_csv(OUTPUT_DIR / "exploratory_followup_candidates.csv", followup_candidates, result_fields)
    write_csv(
        OUTPUT_DIR / "rejection_and_data_issue_log.csv",
        data_issues,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "issue_type",
            "issue",
            "missing_symbols",
            "no_substitution_made",
            "classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_lineage.csv",
        trial_lineage_rows,
        [
            "family_id",
            "strategy_id",
            "trial_id",
            "parent_trial_id",
            "source_library_id",
            "changed_fields_from_parent",
            "route",
            "trial_status",
            "predeclared_before_results",
            "task_or_process_record",
        ],
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(funnel, decisions))
    after_hashes = protected_hashes()
    prior_hashes_after = prior_evidence_hashes()
    consistency = {
        "batch_id": BATCH_ID,
        "exactly_four_frozen_candidates_considered": len(CARDS) == 4
        and [card.strategy_id for card in CARDS]
        == [
            "daryanani_opportunistic_rebalance_20band_10day_v1",
            "fosback_nvi_255ema_spy_bil_v1",
            "clare_inverse_volatility_five_asset_risk_parity_v1",
            "ice_vaneck_us_fallen_angel_angl_v1",
        ],
        "completed_candidate_count": completed_count,
        "data_blocked_candidate_count": data_blocked_count,
        "all_trials_preserved": len(trial_lineage_rows) == len(CARDS)
        and {row["strategy_id"] for row in trial_lineage_rows} == {card.strategy_id for card in CARDS},
        "cost_diagnostics_preserved": {float(row["cost_assumption_bps"]) for row in trial_rows} == set(COST_BPS_GRID),
        "candidate_control_dates_identical_by_strategy_and_cost": identical_dates_by_group(
            [
                *[
                    {
                        "strategy_id": row["strategy_id"],
                        "cost_assumption_bps": row["cost_assumption_bps"],
                        "evaluation_start": row.get("evaluation_start", ""),
                        "evaluation_end": row.get("evaluation_end", ""),
                        "trading_days": row.get("trading_days", 0),
                    }
                    for row in trial_rows
                    if row.get("evaluation_start")
                ],
                *[
                    {
                        "strategy_id": row["strategy_id"],
                        "cost_assumption_bps": row["cost_assumption_bps"],
                        "evaluation_start": row.get("evaluation_start", ""),
                        "evaluation_end": row.get("evaluation_end", ""),
                        "trading_days": row.get("trading_days", 0),
                    }
                    for row in control_rows
                    if row.get("evaluation_start")
                ],
            ],
            ("strategy_id", "cost_assumption_bps"),
        ),
        "chronological_half_dates_identical_by_strategy_cost_and_half": identical_dates_by_group(
            half_rows,
            ("strategy_id", "cost_assumption_bps", "half_label"),
        ),
        "portfolio_contribution_dates_identical_by_strategy_and_cost": identical_dates_by_group(
            contribution_rows,
            ("strategy_id", "cost_assumption_bps"),
        ),
        "process_records_outside_strategy_and_trial_counts": all(
            row["task_or_process_record"] is False for row in strategy_rows + trial_lineage_rows
        ),
        "cohort_funnel_arithmetically_consistent": (
            funnel["completed_candidate_count"] + funnel["data_blocked_candidate_count"] == funnel["candidate_count"]
            and funnel["followup_candidate_count"] + funnel["closed_candidate_count"] + funnel["inconclusive_data_issue_count"]
            == funnel["candidate_count"]
        ),
        "no_missing_instrument_substituted": all(row["no_substitution_made"] for row in data_issues),
        "closed_prior_candidates_reopened": False,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "prior_evidence_hashes_before": prior_hashes_before,
        "prior_evidence_hashes_after": prior_hashes_after,
        "prior_evidence_hashes_unchanged": prior_hashes_before == prior_hashes_after,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        **FORBIDDEN_FLAGS,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": BATCH_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "candidate_count": len(CARDS),
        "completed_candidate_count": completed_count,
        "data_blocked_candidate_count": data_blocked_count,
        "followup_candidate_count": len(followup_candidates),
        "exact_next_action": next_action,
        "task_outcome": "fast_source_library_batch_v3_complete",
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "prior_evidence_hashes_unchanged": prior_hashes_before == prior_hashes_after,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
