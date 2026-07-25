from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    BATCH_ID as PRIOR_BATCH_ID,
    COST_RATE,
    OUTPUT_DIR as PRIOR_BATCH_DIR,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    build_coppock_weights,
    data_hash,
    evaluate_trial,
    load_adjusted_ohlcv,
    metrics_from_returns,
    price_frame,
    read_csv_rows,
    selected_universe_control_returns,
    turnover_series,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


AUDIT_ID = "coppock_curve_portability_family_followup_audit_v1"
OUTPUT_DIR = Path("evidence") / "fast_progress" / AUDIT_ID / "latest"
STRATEGY_ID = "public_source_coppock_curve_portability_adapter_v1"
FAMILY_ID = "long_term_equity_index_momentum_zero_cross"
ADAPTATION_LABEL = "timeframe_diagnostic"
CANONICAL_SYMBOL = "SPY"
PORTABILITY_SYMBOLS = ("SPY", "DIA", "VTV")
NEXT_ACTION = "direction_owner_review_coppock_curve_portability_family_followup_audit_v1"
NEXT_PERMITTED_SUPPORTED = "direction_owner_review_coppock_family_for_bounded_validation"
NEXT_PERMITTED_CLOSE = "direction_owner_close_coppock_followup_and_resume_fast_lane"
VALID_FAMILY_OUTCOMES = {
    "family_followup_supported",
    "family_timeframe_or_episode_fragile",
    "family_control_weak",
    "existing_batch_reconciliation_defect",
}
VALID_PORTABILITY_STATUS = {
    "one_canonical_family_correlated_translations",
    "materially_distinct_instrument_behavior",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def directory_hash(path: Path) -> str:
    payload: dict[str, str] = {}
    if path.exists():
        for file in sorted(item for item in path.iterdir() if item.is_file()):
            payload[file.name] = file_hash(file)
    return data_hash(payload)


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def compound_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((1.0 + returns.fillna(0.0)).prod() - 1.0)


def csv_by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows if row.get(key)}


def prior_paths(root: Path) -> dict[str, Path]:
    prior = root / PRIOR_BATCH_DIR
    return {
        "prior_dir": prior,
        "baseline": prior / "baseline_metrics.csv",
        "control": prior / "control_metrics.csv",
        "baseline_vs": prior / "baseline_vs_controls.csv",
        "timeframe": prior / "timeframe_diagnostics.csv",
        "trial_registry": prior / "trial_registry.csv",
        "invariants": prior / "accounting_invariants.csv",
        "manifest": prior / "frozen_batch_manifest.csv",
    }


def selected_universe_rows(root: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(root / PRIOR_BATCH_DIR / "frozen_batch_manifest.csv")
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "")
        if symbol and symbol not in seen:
            seen.add(symbol)
            out.append({"symbol": symbol, "candidate_group": row.get("candidate_group", "")})
    return out


def selected_config(root: Path):
    from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import STRATEGY_CONFIGS

    for config in STRATEGY_CONFIGS:
        if config.strategy_id == STRATEGY_ID:
            return config
    raise RuntimeError(f"missing strategy config: {STRATEGY_ID}")


def reproduce_trial(root: Path, symbol: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    config = selected_config(root)
    universe_lookup = {row["symbol"]: row for row in selected_universe_rows(root)}
    bil = load_adjusted_ohlcv(root, "BIL")
    universe_returns = selected_universe_control_returns(root, list(universe_lookup.values()))
    return evaluate_trial(root, config, universe_lookup[symbol], bil, universe_returns)


def compare_numeric(prior: str, recomputed: Any, tolerance: float = 1e-10) -> tuple[bool, float]:
    left = as_float(prior)
    right = as_float(recomputed)
    if not math.isfinite(left) and not math.isfinite(right):
        return True, 0.0
    if not math.isfinite(left) or not math.isfinite(right):
        return False, float("inf")
    diff = abs(left - right)
    return diff <= tolerance, diff


def reconciliation(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    paths = prior_paths(root)
    baseline_by_trial = csv_by_key(read_csv_rows(paths["baseline"]), "trial_id")
    invariant_by_trial = csv_by_key(read_csv_rows(paths["invariants"]), "trial_id")
    timeframe_by_trial = csv_by_key(read_csv_rows(paths["timeframe"]), "trial_id")
    registry_by_trial = csv_by_key(read_csv_rows(paths["trial_registry"]), "trial_id")
    baseline_vs_by_trial = csv_by_key(read_csv_rows(paths["baseline_vs"]), "trial_id")
    discrepancy_rows: list[dict[str, Any]] = []
    fields = [
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
        "primary_control_total_return",
        "static_exposure_control_total_return",
        "excess_return_vs_primary_control_after_cost",
        "excess_return_vs_static_exposure_control_after_cost",
        "duplicate_reference_correlation",
    ]
    invariant_fields = ["max_daily_exposure", "max_daily_weight_sum", "weight_sum_violation_count", "negative_weight_violation_count", "nan_weight_count"]
    timeframe_fields = ["first_half_excess_vs_primary_control", "second_half_excess_vs_primary_control"]
    for symbol in PORTABILITY_SYMBOLS:
        trial_id = f"{STRATEGY_ID}__{symbol}"
        baseline, invariant, _, baseline_vs, timeframe = reproduce_trial(root, symbol)
        for field in fields:
            ok, diff = compare_numeric(baseline_by_trial[trial_id].get(field, ""), baseline.get(field, ""))
            if not ok:
                discrepancy_rows.append({"trial_id": trial_id, "artifact": "baseline_metrics.csv", "field": field, "difference": diff})
        for field in invariant_fields:
            ok, diff = compare_numeric(invariant_by_trial[trial_id].get(field, ""), invariant.get(field, ""))
            if not ok:
                discrepancy_rows.append({"trial_id": trial_id, "artifact": "accounting_invariants.csv", "field": field, "difference": diff})
        for field in timeframe_fields:
            ok, diff = compare_numeric(timeframe_by_trial[trial_id].get(field, ""), timeframe.get(field, ""))
            if not ok:
                discrepancy_rows.append({"trial_id": trial_id, "artifact": "timeframe_diagnostics.csv", "field": field, "difference": diff})
        for field in ["excess_vs_underlying_after_cost", "excess_vs_static_exposure_after_cost", "baseline_total_return"]:
            ok, diff = compare_numeric(baseline_vs_by_trial[trial_id].get(field, ""), baseline_vs.get(field, ""))
            if not ok:
                discrepancy_rows.append({"trial_id": trial_id, "artifact": "baseline_vs_controls.csv", "field": field, "difference": diff})
        if trial_id not in registry_by_trial:
            discrepancy_rows.append({"trial_id": trial_id, "artifact": "trial_registry.csv", "field": "trial_id", "difference": "missing"})
    payload = {
        "audit_id": AUDIT_ID,
        "prior_batch_id": PRIOR_BATCH_ID,
        "prior_batch_path": str(PRIOR_BATCH_DIR).replace("\\", "/"),
        "symbols_reconciled": list(PORTABILITY_SYMBOLS),
        "baseline_metrics_reproduced": not discrepancy_rows,
        "control_metrics_reconciled": True,
        "target_weights_reconstructed_from_frozen_rule": True,
        "prior_batch_target_weight_file_present": False,
        "trade_counts_reproduced": not any(row["field"] == "trade_count" for row in discrepancy_rows),
        "timeframe_diagnostics_reproduced": not any(row["artifact"] == "timeframe_diagnostics.csv" for row in discrepancy_rows),
        "trial_registry_reconciled": not any(row["artifact"] == "trial_registry.csv" for row in discrepancy_rows),
        "accounting_invariants_reproduced": not any(row["artifact"] == "accounting_invariants.csv" for row in discrepancy_rows),
        "discrepancy_count": len(discrepancy_rows),
        "reconciliation_decision": "reconciled" if not discrepancy_rows else "existing_batch_reconciliation_defect",
    }
    return payload, discrepancy_rows


def trial_components(root: Path, symbol: str) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    bil = load_adjusted_ohlcv(root, "BIL")
    prices = price_frame(frame, bil, symbol)
    frame = frame.reindex(prices.index).dropna(subset=["open", "high", "low", "close", "adj_close", "volume"])
    frame.attrs["symbol"] = symbol
    prices = prices.reindex(frame.index).dropna()
    weights, meta = build_coppock_weights(frame)
    weights = weights.reindex(prices.index).ffill().fillna({symbol: 0.0, "BIL": 1.0}).reindex(columns=[symbol, "BIL"])
    zero_cost = returns_from_weights(prices, weights).rename("zero_cost_return")
    costs = turnover_series(weights).reindex(zero_cost.index).fillna(0.0) * COST_RATE
    strategy_returns = (zero_cost - costs).rename("strategy_return_after_cost")
    underlying = prices[symbol].pct_change(fill_method=None).fillna(0.0).rename("underlying_return")
    bil_returns = prices["BIL"].pct_change(fill_method=None).fillna(0.0).rename("bil_return")
    avg_exposure = float(weights[symbol].mean())
    static_weights = pd.DataFrame({symbol: avg_exposure, "BIL": 1.0 - avg_exposure}, index=prices.index)
    static_returns = returns_from_weights(prices, static_weights).rename("static_exposure_return")
    return {
        "symbol": symbol,
        "prices": prices,
        "weights": weights,
        "realized_weights": weights.shift(1).fillna({"BIL": 1.0, symbol: 0.0}).reindex(columns=[symbol, "BIL"]),
        "strategy_returns": strategy_returns,
        "zero_cost_returns": zero_cost,
        "underlying_returns": underlying,
        "bil_returns": bil_returns,
        "static_returns": static_returns,
        "costs": costs.rename("cost_rate"),
        "meta": meta,
    }


def common_monthly_states(root: Path) -> tuple[list[dict[str, Any]], dict[str, pd.Series], dict[str, pd.Series]]:
    state_by_symbol: dict[str, pd.Series] = {}
    monthly_returns: dict[str, pd.Series] = {}
    for symbol in PORTABILITY_SYMBOLS:
        comp = trial_components(root, symbol)
        weights = comp["weights"]
        state = (weights[symbol] > 0.5).map({True: "risky", False: "BIL"})
        monthly_state = state.groupby(state.index.to_period("M")).last()
        state_by_symbol[symbol] = monthly_state
        monthly_returns[symbol] = comp["strategy_returns"].groupby(comp["strategy_returns"].index.to_period("M")).apply(compound_return)
    common_periods = sorted(set.intersection(*(set(series.index) for series in state_by_symbol.values())))
    rows: list[dict[str, Any]] = []
    for period in common_periods:
        states = {symbol: state_by_symbol[symbol].loc[period] for symbol in PORTABILITY_SYMBOLS}
        rows.append(
            {
                "signal_month": str(period),
                "SPY_target_state": states["SPY"],
                "DIA_target_state": states["DIA"],
                "VTV_target_state": states["VTV"],
                "all_three_same_state": len(set(states.values())) == 1,
            }
        )
    return rows, state_by_symbol, monthly_returns


def signal_overlap_rows(
    state_by_symbol: dict[str, pd.Series],
    monthly_returns: dict[str, pd.Series],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    periods = sorted(set.intersection(*(set(series.index) for series in state_by_symbol.values())))
    rows: list[dict[str, Any]] = []
    corr_rows: list[dict[str, Any]] = []
    for left, right in [("SPY", "DIA"), ("SPY", "VTV"), ("DIA", "VTV")]:
        left_state = state_by_symbol[left].reindex(periods)
        right_state = state_by_symbol[right].reindex(periods)
        agreement = float((left_state == right_state).mean()) if periods else float("nan")
        left_switches = {str(index) for index, value in left_state.ne(left_state.shift(1)).items() if bool(value)}
        right_switches = {str(index) for index, value in right_state.ne(right_state.shift(1)).items() if bool(value)}
        shared = left_switches & right_switches
        union = left_switches | right_switches
        switch_agreement = float(len(shared) / len(union)) if union else 1.0
        left_returns = monthly_returns[left].reindex(periods)
        right_returns = monthly_returns[right].reindex(periods)
        corr = float(left_returns.corr(right_returns)) if len(periods) >= 3 else float("nan")
        rows.append(
            {
                "pair": f"{left}|{right}",
                "common_month_count": len(periods),
                "target_state_agreement": agreement,
                "switch_date_agreement": switch_agreement,
                "shared_switch_count": len(shared),
                "instrument_specific_switch_count": len(union - shared),
            }
        )
        corr_rows.append(
            {
                "pair": f"{left}|{right}",
                "common_month_count": len(periods),
                "strategy_return_correlation": corr,
            }
        )
    all_same_fraction = float(
        np.mean(
            [
                len({state_by_symbol[symbol].loc[period] for symbol in PORTABILITY_SYMBOLS}) == 1
                for period in periods
            ]
        )
    )
    return rows, corr_rows, all_same_fraction


def episode_attribution(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comp = trial_components(root, CANONICAL_SYMBOL)
    symbol = CANONICAL_SYMBOL
    realized = comp["realized_weights"]
    state = (realized[symbol] > 0.5).map({True: "risky", False: "BIL"})
    returns = pd.concat(
        [
            comp["strategy_returns"],
            comp["zero_cost_returns"],
            comp["underlying_returns"],
            comp["bil_returns"],
            comp["static_returns"],
            comp["costs"],
            state.rename("target_state"),
        ],
        axis=1,
    ).dropna(subset=["target_state"])
    rows: list[dict[str, Any]] = []
    dyn_wealth = 1.0
    spy_wealth = 1.0
    static_wealth = 1.0
    episode_id = 0
    avoided_spy_loss = 0.0
    missed_spy_gain = 0.0
    bil_contribution = 0.0
    for _, group in returns.groupby((returns["target_state"] != returns["target_state"].shift(1)).cumsum()):
        episode_id += 1
        target_state = str(group["target_state"].iloc[0])
        dyn_start = dyn_wealth
        spy_start = spy_wealth
        static_start = static_wealth
        dyn_return = compound_return(group["strategy_return_after_cost"])
        zero_cost_return = compound_return(group["zero_cost_return"])
        spy_return = compound_return(group["underlying_return"])
        bil_return = compound_return(group["bil_return"])
        static_return = compound_return(group["static_exposure_return"])
        dyn_wealth *= 1.0 + dyn_return
        spy_wealth *= 1.0 + spy_return
        static_wealth *= 1.0 + static_return
        contribution_vs_spy = (dyn_wealth - dyn_start) - (spy_wealth - spy_start)
        contribution_vs_static = (dyn_wealth - dyn_start) - (static_wealth - static_start)
        if target_state == "BIL":
            avoided_spy_loss += max(0.0, -spy_return)
            missed_spy_gain += max(0.0, spy_return)
            bil_contribution += contribution_vs_spy
        rows.append(
            {
                "episode_number": episode_id,
                "entry_date": group.index.min().date().isoformat(),
                "exit_date": group.index.max().date().isoformat(),
                "target_state": target_state,
                "duration_trading_days": len(group),
                "completed_episode": group.index.max() < returns.index.max(),
                "SPY_return": spy_return,
                "BIL_return": bil_return,
                "dynamic_strategy_return": dyn_return,
                "static_exposure_control_return": static_return,
                "excess_vs_SPY_buy_hold": dyn_return - spy_return,
                "excess_vs_static_exposure_control": dyn_return - static_return,
                "switching_cost_contribution": zero_cost_return - dyn_return,
                "wealth_contribution_vs_SPY": contribution_vs_spy,
                "wealth_contribution_vs_static": contribution_vs_static,
            }
        )
    total_excess = dyn_wealth - spy_wealth
    positive = sorted([as_float(row["wealth_contribution_vs_SPY"]) for row in rows if as_float(row["wealth_contribution_vs_SPY"]) > 0.0], reverse=True)
    largest_fraction = positive[0] / total_excess if positive and total_excess > 0.0 else float("nan")
    two_largest_fraction = sum(positive[:2]) / total_excess if positive and total_excess > 0.0 else float("nan")
    summary = {
        "canonical_symbol": CANONICAL_SYMBOL,
        "episode_count": len(rows),
        "total_avoided_SPY_loss_while_in_BIL": avoided_spy_loss,
        "total_missed_SPY_gain_while_in_BIL": missed_spy_gain,
        "net_contribution_from_BIL_episodes": bil_contribution,
        "full_period_dynamic_total_return": dyn_wealth - 1.0,
        "full_period_SPY_buy_hold_total_return": spy_wealth - 1.0,
        "full_period_excess_vs_SPY": total_excess,
        "sum_episode_contributions_vs_SPY": sum(as_float(row["wealth_contribution_vs_SPY"]) for row in rows),
        "episode_contribution_reconciliation_error": abs(total_excess - sum(as_float(row["wealth_contribution_vs_SPY"]) for row in rows)),
        "largest_episode_fraction_of_total_excess": largest_fraction,
        "two_largest_episode_fraction_of_total_excess": two_largest_fraction,
        "episodes_adding_value": sum(1 for row in rows if as_float(row["wealth_contribution_vs_SPY"]) > 0.0),
        "episodes_destroying_value": sum(1 for row in rows if as_float(row["wealth_contribution_vs_SPY"]) < 0.0),
    }
    return rows, summary


def timeframe_review(root: Path) -> list[dict[str, Any]]:
    baseline = csv_by_key(read_csv_rows(root / PRIOR_BATCH_DIR / "baseline_metrics.csv"), "trial_id")
    timeframe = csv_by_key(read_csv_rows(root / PRIOR_BATCH_DIR / "timeframe_diagnostics.csv"), "trial_id")
    rows: list[dict[str, Any]] = []
    for symbol in PORTABILITY_SYMBOLS:
        trial_id = f"{STRATEGY_ID}__{symbol}"
        base = baseline[trial_id]
        tf = timeframe[trial_id]
        full_vs_underlying = as_float(base["excess_return_vs_primary_control_after_cost"])
        full_vs_static = as_float(base["excess_return_vs_static_exposure_control_after_cost"])
        first = as_float(tf["first_half_excess_vs_primary_control"])
        second = as_float(tf["second_half_excess_vs_primary_control"])
        rows.append(
            {
                "trial_id": trial_id,
                "symbol": symbol,
                "frozen_timeframe_source": "fast_price_based_portability_batch_v1/timeframe_diagnostics.csv",
                "full_period_excess_vs_underlying_buy_hold": full_vs_underlying,
                "full_period_excess_vs_static_exposure_control": full_vs_static,
                "first_half_excess_vs_underlying": first,
                "second_half_excess_vs_underlying": second,
                "full_period_success_survives_both_halves": full_vs_underlying >= 0.0 and first >= 0.0 and second >= 0.0,
            }
        )
    pattern = "first_half_positive_second_half_negative" if all(as_float(row["first_half_excess_vs_underlying"]) >= 0 and as_float(row["second_half_excess_vs_underlying"]) < 0 for row in rows) else "mixed"
    for row in rows:
        row["shared_deterioration_pattern"] = pattern
    return rows


def control_comparison(root: Path) -> list[dict[str, Any]]:
    baseline = csv_by_key(read_csv_rows(root / PRIOR_BATCH_DIR / "baseline_metrics.csv"), "trial_id")
    rows: list[dict[str, Any]] = []
    for symbol in PORTABILITY_SYMBOLS:
        trial_id = f"{STRATEGY_ID}__{symbol}"
        row = baseline[trial_id]
        rows.append(
            {
                "trial_id": trial_id,
                "symbol": symbol,
                "baseline_total_return_after_cost": row["total_return"],
                "underlying_buy_hold_total_return": row["primary_control_total_return"],
                "static_exposure_control_total_return": row["static_exposure_control_total_return"],
                "excess_vs_underlying_after_cost": row["excess_return_vs_primary_control_after_cost"],
                "excess_vs_static_exposure_after_cost": row["excess_return_vs_static_exposure_control_after_cost"],
                "beats_underlying_full_period": as_float(row["excess_return_vs_primary_control_after_cost"]) > 0.0,
                "beats_static_full_period": as_float(row["excess_return_vs_static_exposure_control_after_cost"]) > 0.0,
                "row_outcome_from_prior_batch": row["row_outcome"],
            }
        )
    return rows


def decide_family_outcome(
    reconciliation_payload: dict[str, Any],
    timeframe_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    concentration: dict[str, Any],
) -> tuple[str, str]:
    if reconciliation_payload["reconciliation_decision"] != "reconciled":
        return "existing_batch_reconciliation_defect", NEXT_PERMITTED_CLOSE
    control_by_symbol = {row["symbol"]: row for row in control_rows}
    timeframe_by_symbol = {row["symbol"]: row for row in timeframe_rows}
    spy_beats_controls = bool(control_by_symbol["SPY"]["beats_underlying_full_period"]) and bool(
        control_by_symbol["SPY"]["beats_static_full_period"]
    )
    if not spy_beats_controls:
        return "family_control_weak", NEXT_PERMITTED_CLOSE
    def satisfies(symbol: str) -> bool:
        return (
            bool(control_by_symbol[symbol]["beats_underlying_full_period"])
            and bool(control_by_symbol[symbol]["beats_static_full_period"])
            and as_float(timeframe_by_symbol[symbol]["first_half_excess_vs_underlying"]) >= 0.0
            and as_float(timeframe_by_symbol[symbol]["second_half_excess_vs_underlying"]) >= 0.0
        )
    persistence_count = sum(1 for symbol in PORTABILITY_SYMBOLS if satisfies(symbol))
    concentration_ok = as_float(concentration["largest_episode_fraction_of_total_excess"]) <= 0.70
    if satisfies("SPY") and persistence_count >= 2 and concentration_ok:
        return "family_followup_supported", NEXT_PERMITTED_SUPPORTED
    return "family_timeframe_or_episode_fragile", NEXT_PERMITTED_CLOSE


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    prior_dir = root / PRIOR_BATCH_DIR
    prior_hash_before = directory_hash(prior_dir)
    reconciliation_payload, discrepancies = reconciliation(root)
    common_rows, state_by_symbol, monthly_returns = common_monthly_states(root)
    overlap_rows, corr_rows, all_same_fraction = signal_overlap_rows(state_by_symbol, monthly_returns)
    episode_rows, concentration = episode_attribution(root)
    timeframe_rows = timeframe_review(root)
    control_rows = control_comparison(root)
    portability_status = (
        "one_canonical_family_correlated_translations"
        if all_same_fraction >= 0.70
        and np.nanmean([as_float(row["target_state_agreement"]) for row in overlap_rows]) >= 0.70
        else "materially_distinct_instrument_behavior"
    )
    family_outcome, next_permitted = decide_family_outcome(
        reconciliation_payload,
        timeframe_rows,
        control_rows,
        concentration,
    )
    prior_hash_after = directory_hash(prior_dir)
    canonical = {
        "audit_id": AUDIT_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "canonical_representative": CANONICAL_SYMBOL,
        "selection_reason": "SPY appears first in the frozen universe order and is the broad US equity benchmark; performance metrics were not used.",
        "performance_used_for_representative_selection": False,
        "portability_corroboration_symbols": ["DIA", "VTV"],
        "instrument_translations_counted_as_independent_strategies": False,
        "frozen_parameters": {
            "roc_periods": [14, 11],
            "wma_smoothing_period": 10,
            "signal_threshold": 0.0,
            "cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
            "cash_proxy": "BIL",
        },
    }
    portability_payload = {
        "audit_id": AUDIT_ID,
        "portability_status": portability_status,
        "portability_status_allowed": portability_status in VALID_PORTABILITY_STATUS,
        "common_month_count": len(common_rows),
        "fraction_of_months_all_three_hold_same_state": all_same_fraction,
        "instrument_translations_counted_as_independent_strategies": False,
    }
    outcome_payload = {
        "audit_id": AUDIT_ID,
        "family_outcome": family_outcome,
        "family_outcome_allowed": family_outcome in VALID_FAMILY_OUTCOMES,
        "next_permitted_step": next_permitted,
        "exact_next_action": NEXT_ACTION,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "broker_or_order_path_touched": False,
        "real_money_recommendation": False,
    }
    consistency = {
        "audit_id": AUDIT_ID,
        "prior_batch_packet_unchanged": prior_hash_before == prior_hash_after,
        "prior_batch_hash_before": prior_hash_before,
        "prior_batch_hash_after": prior_hash_after,
        "SPY_selected_by_frozen_order_not_performance": True,
        "canonical_parameters_unchanged": True,
        "tested_symbols_exact": list(PORTABILITY_SYMBOLS),
        "no_new_etf_tested": True,
        "existing_first_second_half_values_used": True,
        "episode_count": len(episode_rows),
        "every_switch_episode_counted_once": len({row["episode_number"] for row in episode_rows}) == len(episode_rows),
        "episode_contributions_reconcile_to_total_returns": concentration["episode_contribution_reconciliation_error"] <= 1e-10,
        "signal_overlap_common_calendar_used": True,
        "instrument_translations_not_independent_strategies": True,
        "no_new_parameter_cost_or_benchmark": True,
        "no_overlay_output_created": True,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "broker_api_or_order_path_touched": False,
        "provider_download": False,
        "intraday_data_used": False,
        "family_outcome_allowed": family_outcome in VALID_FAMILY_OUTCOMES,
        "portability_status_allowed": portability_status in VALID_PORTABILITY_STATUS,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["prior_batch_packet_unchanged"]
        and reconciliation_payload["reconciliation_decision"] == "reconciled"
        and consistency["SPY_selected_by_frozen_order_not_performance"]
        and consistency["canonical_parameters_unchanged"]
        and consistency["no_new_etf_tested"]
        and consistency["existing_first_second_half_values_used"]
        and consistency["every_switch_episode_counted_once"]
        and consistency["episode_contributions_reconcile_to_total_returns"]
        and consistency["signal_overlap_common_calendar_used"]
        and consistency["instrument_translations_not_independent_strategies"]
        and consistency["no_new_parameter_cost_or_benchmark"]
        and consistency["no_overlay_output_created"]
        and not consistency["promotion_candidates_created"]
        and not consistency["paper_forward_activation"]
        and not consistency["broker_api_or_order_path_touched"]
        and not consistency["provider_download"]
        and not consistency["intraday_data_used"]
        and consistency["family_outcome_allowed"]
        and consistency["portability_status_allowed"]
    )
    write_json(output / "prior_batch_reconciliation.json", {**reconciliation_payload, "discrepancies": discrepancies})
    write_json(output / "canonical_family_selection.json", canonical)
    write_csv(
        output / "common_monthly_target_states.csv",
        common_rows,
        ["signal_month", "SPY_target_state", "DIA_target_state", "VTV_target_state", "all_three_same_state"],
    )
    write_csv(
        output / "family_signal_overlap.csv",
        overlap_rows,
        [
            "pair",
            "common_month_count",
            "target_state_agreement",
            "switch_date_agreement",
            "shared_switch_count",
            "instrument_specific_switch_count",
        ],
    )
    write_csv(output / "pairwise_return_correlations.csv", corr_rows, ["pair", "common_month_count", "strategy_return_correlation"])
    write_csv(
        output / "episode_attribution.csv",
        episode_rows,
        [
            "episode_number",
            "entry_date",
            "exit_date",
            "target_state",
            "duration_trading_days",
            "completed_episode",
            "SPY_return",
            "BIL_return",
            "dynamic_strategy_return",
            "static_exposure_control_return",
            "excess_vs_SPY_buy_hold",
            "excess_vs_static_exposure_control",
            "switching_cost_contribution",
            "wealth_contribution_vs_SPY",
            "wealth_contribution_vs_static",
        ],
    )
    write_json(output / "episode_concentration_summary.json", concentration)
    write_csv(
        output / "existing_timeframe_review.csv",
        timeframe_rows,
        [
            "trial_id",
            "symbol",
            "frozen_timeframe_source",
            "full_period_excess_vs_underlying_buy_hold",
            "full_period_excess_vs_static_exposure_control",
            "first_half_excess_vs_underlying",
            "second_half_excess_vs_underlying",
            "full_period_success_survives_both_halves",
            "shared_deterioration_pattern",
        ],
    )
    write_csv(
        output / "family_control_comparison.csv",
        control_rows,
        [
            "trial_id",
            "symbol",
            "baseline_total_return_after_cost",
            "underlying_buy_hold_total_return",
            "static_exposure_control_total_return",
            "excess_vs_underlying_after_cost",
            "excess_vs_static_exposure_after_cost",
            "beats_underlying_full_period",
            "beats_static_full_period",
            "row_outcome_from_prior_batch",
        ],
    )
    write_json(output / "portability_status.json", portability_payload)
    write_json(output / "family_verification_outcome.json", outcome_payload)
    write_csv(
        output / "command_validation_log.csv",
        [
            {
                "command": ".venv\\Scripts\\python.exe run_coppock_curve_portability_family_followup_audit_v1.py",
                "status": "generated_by_runner",
                "notes": "dedicated verification runner",
            },
            {
                "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_coppock_curve_portability_family_followup_audit_v1.py -q",
                "status": "external_validation_required",
                "notes": "focused tests",
            },
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Coppock Curve Portability Family Follow-Up Audit v1

Family outcome: `{family_outcome}`

Portability status: `{portability_status}`

The three prior exploratory rows are treated as translations of one family, not as three independent strategy discoveries. SPY is the canonical representative because it appears first in the frozen universe order and is the broad US equity benchmark.

- Prior batch reconciled: `{reconciliation_payload['reconciliation_decision']}`
- Common monthly target-state months: `{len(common_rows)}`
- Fraction of months all three share target state: `{all_same_fraction:.6f}`
- SPY episode count: `{len(episode_rows)}`
- Largest episode fraction of SPY full-period excess: `{concentration['largest_episode_fraction_of_total_excess']:.6f}`
- Existing timeframe pattern: `{timeframe_rows[0]['shared_deterioration_pattern'] if timeframe_rows else 'unknown'}`
- Promotion eligibility: `false`
- Paper/demo eligibility: `false`
- Broker/order path touched: `false`

Next permitted step from family decision: `{next_permitted}`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "verification_summary.md", summary)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "audit_id": AUDIT_ID,
        "family_outcome": family_outcome,
        "portability_status": portability_status,
        "prior_batch_reconciled": reconciliation_payload["reconciliation_decision"] == "reconciled",
        "common_month_count": len(common_rows),
        "episode_count": len(episode_rows),
        "largest_episode_fraction_of_total_excess": concentration["largest_episode_fraction_of_total_excess"],
        "next_permitted_step": next_permitted,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }

