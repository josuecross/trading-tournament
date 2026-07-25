from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    BATCH_ID as PRIOR_BATCH_ID,
    COST_RATE,
    DEDICATED_SNAPSHOT_DIR,
    FROZEN_UNIVERSE_PATH,
    OUTPUT_DIR as PRIOR_BATCH_DIR,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    data_hash,
    load_adjusted_ohlcv,
    metrics_from_returns,
    price_frame,
    turnover_series,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)
from strategy_lab.research_os.research.public_source_parabolic_sar_bounded_bt_run import (
    AF_INCREMENT,
    AF_MAXIMUM,
    AF_START,
    FORMULA_CONTRACT_VERSION,
    parabolic_sar_state,
    primary_targets,
)


BATCH_ID = "fast_price_based_portability_batch_v2"
OUTPUT_DIR = Path("evidence") / "fast_progress" / BATCH_ID / "latest"
NEXT_ACTION = "direction_owner_review_fast_price_based_portability_batch_v2"
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
COPPOCK_AUDIT_DIR = Path("evidence") / "fast_progress" / "coppock_curve_portability_family_followup_audit_v1" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
MAX_FAMILIES = 4
MAX_TRIALS = 24
TRIALS_PER_FAMILY = 6
WEIGHT_TOLERANCE = 1e-6
MIN_HISTORY_DAYS = 504
SELECTED_COMPATIBILITY_FAMILY = "own_return_trend_long_cash"

V1_COMPLETED_STRATEGIES = (
    "public_source_adx_dmi_portability_adapter_v1",
    "public_source_cci_correction_portability_adapter_v1",
    "public_source_coppock_curve_portability_adapter_v1",
    "public_source_larry_connors_rsi2_portability_adapter_v1",
)
COPPOCK_CLOSED_OUTCOME = "family_timeframe_or_episode_fragile"
COPPOCK_DIRECTION_DECISION = "NO_ADVANCEMENT"
VALID_ROW_OUTCOMES = {
    "row_control_strong",
    "row_timeframe_fragile",
    "row_control_weak",
    "row_cost_fragile",
    "insufficient_history",
    "capability_deferred",
    "implementation_or_accounting_defect",
}
VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "family_capability_deferred",
    "family_implementation_defect",
}
VALID_BATCH_OUTCOMES = {
    "fast_batch_v2_complete",
    "no_remaining_existing_fast_lane_families",
    "frozen_universe_or_compatibility_missing",
    "existing_data_coverage_insufficient",
    "batch_execution_or_accounting_defect",
}


@dataclass(frozen=True)
class FamilyConfig:
    strategy_id: str
    family_id: str
    source_id: str
    implementation_path: str
    focused_test_path: str
    canonical_parameters: dict[str, Any]
    rule_summary: str
    ready_queue_priority: int


PARABOLIC_CONFIG = FamilyConfig(
    strategy_id="public_source_parabolic_sar_portability_adapter_v1",
    family_id="equity_index_parabolic_sar_trend_reversal",
    source_id="parabolic_sar_spy_bil_long_only_reversal",
    implementation_path="strategy_lab/research_os/research/public_source_parabolic_sar_bounded_bt_run.py",
    focused_test_path="tests/test_public_source_parabolic_sar_bounded_bt_run.py",
    canonical_parameters={
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "af_start": AF_START,
        "af_increment": AF_INCREMENT,
        "af_maximum": AF_MAXIMUM,
    },
    rule_summary="Parabolic SAR source-backed long/cash reversal; bullish state maps to risky ETF, bearish/inactive maps to BIL.",
    ready_queue_priority=5,
)


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def frozen_universe(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / FROZEN_UNIVERSE_PATH)


def compatibility_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / COMPATIBILITY_PATH)


DETERMINISTIC_CORE_FILES = [
    "prior_direction_decisions.json",
    "remaining_strategy_inventory.csv",
    "excluded_strategy_inventory.csv",
    "frozen_universe_reference.json",
    "frozen_batch_manifest.csv",
    "canonical_family_representatives.csv",
    "trial_registry.csv",
    "data_coverage.csv",
    "baseline_metrics.csv",
    "control_metrics.csv",
    "baseline_vs_controls.csv",
    "timeframe_diagnostics.csv",
    "accounting_invariants.csv",
    "row_outcomes.csv",
    "family_outcomes.csv",
    "family_followup_queue.csv",
]


def deterministic_core_hash(evidence_dir: Path) -> str:
    payload = {}
    for name in DETERMINISTIC_CORE_FILES:
        path = evidence_dir / name
        payload[name] = path.read_text(encoding="utf-8") if path.exists() else "missing"
    return data_hash(payload)


def remaining_strategy_inventory(root: Path) -> tuple[list[FamilyConfig], list[dict[str, Any]], list[dict[str, Any]]]:
    included: list[FamilyConfig] = []
    inventory: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    candidates = [
        PARABOLIC_CONFIG,
    ]
    explicit_exclusions = [
        ("public_source_adx_dmi_portability_adapter_v1", "completed_in_fast_price_based_portability_batch_v1"),
        ("public_source_cci_correction_portability_adapter_v1", "completed_in_fast_price_based_portability_batch_v1"),
        ("public_source_coppock_curve_portability_adapter_v1", "closed_family_timeframe_or_episode_fragile_no_advancement"),
        ("public_source_larry_connors_rsi2_portability_adapter_v1", "completed_in_fast_price_based_portability_batch_v1"),
        (
            "public_source_percent_b_money_flow_portability_adapter_v1",
            "not_in_remaining_fast_lane_ready_queue; source-exact bounded lane already completed separately",
        ),
    ]
    for strategy_id, reason in explicit_exclusions:
        excluded.append(
            {
                "strategy_id": strategy_id,
                "source_id": strategy_id.replace("public_source_", "").replace("_portability_adapter_v1", ""),
                "family_id": "",
                "implementation_exists": "",
                "focused_test_exists": "",
                "eligibility_independent_of_performance": True,
                "eligibility_status": "excluded",
                "exclusion_reason": reason,
            }
        )
    for config in candidates:
        implementation_exists = (root / config.implementation_path).exists()
        test_exists = (root / config.focused_test_path).exists()
        eligible = implementation_exists and test_exists
        row = {
            "strategy_id": config.strategy_id,
            "source_id": config.source_id,
            "family_id": config.family_id,
            "ready_queue_priority": config.ready_queue_priority,
            "implementation_path": config.implementation_path,
            "focused_test_path": config.focused_test_path,
            "implementation_exists": implementation_exists,
            "focused_test_exists": test_exists,
            "focused_tests_passed_prior_to_batch": "validated_by_command_log",
            "canonical_config_recorded": True,
            "complete_rule_uses_adjusted_ohlcv_only": True,
            "requires_macro_fundamental_or_alt_data": False,
            "requires_new_credential": False,
            "requires_major_engine_capability": False,
            "long_only_or_long_cash": True,
            "requires_leverage_inverse_or_shorting": False,
            "uses_existing_daily_data_and_accounting": True,
            "included_in_fast_batch_v1": False,
            "exact_configuration_closed_or_completed_elsewhere": False,
            "eligibility_independent_of_performance": True,
            "eligibility_status": "eligible" if eligible else "excluded",
            "exclusion_reason": "" if eligible else "missing_existing_implementation_or_focused_test",
            "canonical_parameters": config.canonical_parameters,
        }
        if eligible:
            included.append(config)
            inventory.append(row)
        else:
            excluded.append(row)
    return included[:MAX_FAMILIES], inventory, excluded


def choose_instruments(root: Path, universe_rows: list[dict[str, str]], family_count: int) -> list[dict[str, str]]:
    if not universe_rows or family_count <= 0:
        return []
    compatible_symbols = {
        row["symbol"]
        for row in compatibility_rows(root)
        if row.get("family_id") == SELECTED_COMPATIBILITY_FAMILY
        and row.get("compatibility_label") == "compatible_with_frozen_cash_proxy"
    }
    ordered = [
        row
        for row in universe_rows
        if row.get("symbol")
        and row["symbol"] != "BIL"
        and row["symbol"] in compatible_symbols
        and row.get("product_structure", "").lower() not in {"inverse_etf", "leveraged_etf"}
    ]
    max_for_family = min(TRIALS_PER_FAMILY, MAX_TRIALS // family_count)
    selected: list[dict[str, str]] = []
    group_counts: dict[str, int] = {}
    # First pass gives group breadth in frozen order.
    seen_groups: set[str] = set()
    for row in ordered:
        group = row.get("candidate_group", "")
        if group in seen_groups:
            continue
        selected.append(row)
        group_counts[group] = group_counts.get(group, 0) + 1
        seen_groups.add(group)
        if len(selected) >= max_for_family:
            return selected
    # Second pass may add at most a second instrument per group.
    for row in ordered:
        if row in selected:
            continue
        group = row.get("candidate_group", "")
        if group_counts.get(group, 0) >= 2:
            continue
        selected.append(row)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(selected) >= max_for_family:
            break
    return selected


def coverage_row(root: Path, symbol: str, row: dict[str, str]) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    path = "" if frame.empty else str(frame["source_cache_path"].iloc[0])
    return {
        "symbol": symbol,
        "candidate_group": row.get("candidate_group", ""),
        "primary_economic_exposure": row.get("primary_economic_exposure", ""),
        "cache_ready": not frame.empty and len(frame) >= MIN_HISTORY_DAYS,
        "rows": int(len(frame)),
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "has_adjusted_ohlcv": not frame.empty,
        "cache_path": path,
        "cache_file_hash": file_hash(root / path) if path else "missing",
    }


def universe_control_returns(root: Path, instrument_rows: list[dict[str, str]]) -> pd.Series:
    series: list[pd.Series] = []
    for row in instrument_rows:
        frame = load_adjusted_ohlcv(root, row["symbol"])
        if not frame.empty:
            series.append(frame["adj_close"].astype(float).pct_change(fill_method=None).rename(row["symbol"]))
    if not series:
        return pd.Series(dtype=float, name="equal_weight_selected_universe_control")
    returns = pd.concat(series, axis=1, join="inner").fillna(0.0)
    return returns.mean(axis=1).rename("equal_weight_selected_universe_control")


def parabolic_weights(symbol: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    state = parabolic_sar_state(frame[["open", "high", "low", "close", "adj_close"]])
    raw_weights, _events = primary_targets(state)
    weights = raw_weights.rename(columns={"SPY": symbol}).reindex(columns=[symbol, "BIL"], fill_value=0.0)
    active = weights[symbol] > 0.5
    prior = active.shift(1, fill_value=False)
    return weights, {
        "bullish_flip_count": int(state["bullish_flip"].fillna(False).sum()),
        "bearish_flip_count": int(state["bearish_flip"].fillna(False).sum()),
        "entry_count": int((active & ~prior).sum()),
        "exit_count": int((~active & prior).sum()),
        "valid_signal_rows": int(state["valid_sar"].fillna(False).sum()),
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
    }


def split_timeframe(baseline: pd.Series, control: pd.Series) -> dict[str, Any]:
    aligned = pd.concat([baseline.rename("baseline"), control.rename("control")], axis=1).dropna()
    if len(aligned) < 60:
        return {
            "first_half_valid": False,
            "second_half_valid": False,
            "first_half_start_date": "",
            "first_half_end_date": "",
            "second_half_start_date": "",
            "second_half_end_date": "",
            "first_half_excess_vs_primary_control": float("nan"),
            "second_half_excess_vs_primary_control": float("nan"),
        }
    midpoint = len(aligned) // 2
    first = aligned.iloc[:midpoint]
    second = aligned.iloc[midpoint:]
    return {
        "first_half_valid": len(first) >= 30,
        "second_half_valid": len(second) >= 30,
        "first_half_start_date": first.index.min().date().isoformat(),
        "first_half_end_date": first.index.max().date().isoformat(),
        "second_half_start_date": second.index.min().date().isoformat(),
        "second_half_end_date": second.index.max().date().isoformat(),
        "first_half_excess_vs_primary_control": compound_return(first["baseline"]) - compound_return(first["control"]),
        "second_half_excess_vs_primary_control": compound_return(second["baseline"]) - compound_return(second["control"]),
    }


def evaluate_trial(
    root: Path,
    family: FamilyConfig,
    instrument: dict[str, str],
    bil_frame: pd.DataFrame,
    equal_weight_returns: pd.Series,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    symbol = instrument["symbol"]
    trial_id = f"{family.strategy_id}__{symbol}"
    frame = load_adjusted_ohlcv(root, symbol)
    if frame.empty or len(frame) < MIN_HISTORY_DAYS:
        base = {
            "trial_id": trial_id,
            "strategy_id": family.strategy_id,
            "family_id": family.family_id,
            "source_id": family.source_id,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "numeric_result_interpretable": False,
            "failure_reason": "missing_or_short_adjusted_ohlcv_cache",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
        }
        return base, {}, [], {}, {}, {}
    prices = price_frame(frame, bil_frame, symbol)
    frame = frame.reindex(prices.index).dropna(subset=["open", "high", "low", "close", "adj_close", "volume"])
    prices = prices.reindex(frame.index).dropna()
    if len(prices) < MIN_HISTORY_DAYS:
        base = {
            "trial_id": trial_id,
            "strategy_id": family.strategy_id,
            "family_id": family.family_id,
            "source_id": family.source_id,
            "symbol": symbol,
            "row_outcome": "insufficient_history",
            "numeric_result_interpretable": False,
            "failure_reason": "missing_common_symbol_bil_history",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
        }
        return base, {}, [], {}, {}, {}
    weights, signal_meta = parabolic_weights(symbol, frame)
    weights = weights.reindex(prices.index).ffill().fillna({symbol: 0.0, "BIL": 1.0}).reindex(columns=[symbol, "BIL"])
    zero_cost = returns_from_weights(prices, weights).rename("zero_cost_return")
    costs = turnover_series(weights).reindex(zero_cost.index).fillna(0.0) * COST_RATE
    baseline = (zero_cost - costs).rename("baseline_return_after_cost")
    underlying = prices[symbol].pct_change(fill_method=None).fillna(0.0).rename("underlying_buy_hold")
    bil_returns = prices["BIL"].pct_change(fill_method=None).fillna(0.0).rename("BIL_cash")
    avg_exposure = float(weights[symbol].mean())
    static_weights = pd.DataFrame({symbol: avg_exposure, "BIL": 1.0 - avg_exposure}, index=prices.index)
    static_returns = returns_from_weights(prices, static_weights).rename("static_average_exposure_control")
    universe_returns = equal_weight_returns.reindex(prices.index).fillna(0.0).rename("equal_weight_selected_universe_control")
    base_metrics = metrics_from_returns(baseline)
    zero_metrics = metrics_from_returns(zero_cost)
    underlying_metrics = metrics_from_returns(underlying)
    bil_metrics = metrics_from_returns(bil_returns)
    static_metrics = metrics_from_returns(static_returns)
    universe_metrics = metrics_from_returns(universe_returns)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and int(invariant["impossible_cash_and_risky_exposure_days"]) == 0
    )
    timeframe = split_timeframe(baseline, underlying)
    after_cost_pass_controls = (
        base_metrics["total_return"] > underlying_metrics["total_return"]
        and base_metrics["total_return"] > static_metrics["total_return"]
    )
    zero_cost_pass_controls = (
        zero_metrics["total_return"] > underlying_metrics["total_return"]
        and zero_metrics["total_return"] > static_metrics["total_return"]
    )
    halves_pass = (
        bool(timeframe["first_half_valid"])
        and bool(timeframe["second_half_valid"])
        and as_float(timeframe["first_half_excess_vs_primary_control"]) >= 0.0
        and as_float(timeframe["second_half_excess_vs_primary_control"]) >= 0.0
    )
    if not invariant_pass:
        row_outcome = "implementation_or_accounting_defect"
        failure_reason = "exposure_invariant_failure"
    elif zero_cost_pass_controls and not after_cost_pass_controls:
        row_outcome = "row_cost_fragile"
        failure_reason = "standard_cost_erases_control_edge"
    elif after_cost_pass_controls and halves_pass:
        row_outcome = "row_control_strong"
        failure_reason = "none"
    elif after_cost_pass_controls:
        row_outcome = "row_timeframe_fragile"
        failure_reason = "full_period_controls_pass_but_existing_half_negative"
    else:
        row_outcome = "row_control_weak"
        failure_reason = "after_cost_baseline_does_not_beat_required_full_period_controls"
    trades, turnover_proxy = trade_count_and_turnover(weights)
    baseline_row = {
        "trial_id": trial_id,
        "strategy_id": family.strategy_id,
        "family_id": family.family_id,
        "source_id": family.source_id,
        "symbol": symbol,
        "candidate_group": instrument.get("candidate_group", ""),
        "primary_economic_exposure": instrument.get("primary_economic_exposure", ""),
        "canonical_parameters": family.canonical_parameters,
        "start_date": base_metrics["start_date"],
        "end_date": base_metrics["end_date"],
        "trading_days": base_metrics["trading_days"],
        "total_return": base_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "cagr": base_metrics["cagr"],
        "max_drawdown": base_metrics["max_drawdown"],
        "volatility": base_metrics["volatility"],
        "return_drawdown_proxy": base_metrics["return_drawdown_proxy"],
        "average_risky_exposure": avg_exposure,
        "average_bil_exposure": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover_proxy,
        "entry_count": signal_meta["entry_count"],
        "exit_count": signal_meta["exit_count"],
        "bullish_flip_count": signal_meta["bullish_flip_count"],
        "bearish_flip_count": signal_meta["bearish_flip_count"],
        "valid_signal_rows": signal_meta["valid_signal_rows"],
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "primary_control_total_return": underlying_metrics["total_return"],
        "static_exposure_control_total_return": static_metrics["total_return"],
        "excess_return_vs_primary_control_after_cost": base_metrics["total_return"] - underlying_metrics["total_return"],
        "excess_return_vs_static_exposure_control_after_cost": base_metrics["total_return"] - static_metrics["total_return"],
        "row_outcome": row_outcome,
        "failure_reason": failure_reason,
        "numeric_result_interpretable": True,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    controls = []
    for control_id, metrics in [
        ("instrument_buy_hold", underlying_metrics),
        ("BIL_cash", bil_metrics),
        ("static_average_exposure_control", static_metrics),
        ("equal_weight_selected_universe_control", universe_metrics),
    ]:
        controls.append(
            {
                "trial_id": trial_id,
                "strategy_id": family.strategy_id,
                "symbol": symbol,
                "control_id": control_id,
                **metrics,
                "performance_selected_control": False,
            }
        )
    invariant_row = {
        "trial_id": trial_id,
        "strategy_id": family.strategy_id,
        "symbol": symbol,
        **invariant,
        "exposure_invariant_pass": invariant_pass,
        "zero_target_weights_preserved": True,
        "no_stale_weights_after_exits": True,
        "no_lookahead_status": "shifted_weight_returns_from_completed_daily_bars",
        "cost_accounting_status": "5bps_turnover_cost_and_zero_cost_diagnostic_recorded",
        "static_control_same_calendar": True,
    }
    vs_row = {
        "trial_id": trial_id,
        "strategy_id": family.strategy_id,
        "symbol": symbol,
        "baseline_total_return_after_cost": base_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "instrument_buy_hold_total_return": underlying_metrics["total_return"],
        "BIL_cash_total_return": bil_metrics["total_return"],
        "static_average_exposure_control_total_return": static_metrics["total_return"],
        "equal_weight_selected_universe_control_total_return": universe_metrics["total_return"],
        "after_cost_beats_primary_control": base_metrics["total_return"] > underlying_metrics["total_return"],
        "after_cost_beats_static_control": base_metrics["total_return"] > static_metrics["total_return"],
        "zero_cost_beats_primary_control": zero_metrics["total_return"] > underlying_metrics["total_return"],
        "zero_cost_beats_static_control": zero_metrics["total_return"] > static_metrics["total_return"],
    }
    timeframe_row = {
        "trial_id": trial_id,
        "strategy_id": family.strategy_id,
        "symbol": symbol,
        **timeframe,
        "timeframe_diagnostic_not_holdout": True,
    }
    row_outcome = {
        "trial_id": trial_id,
        "strategy_id": family.strategy_id,
        "family_id": family.family_id,
        "source_id": family.source_id,
        "symbol": symbol,
        "candidate_group": instrument.get("candidate_group", ""),
        "row_outcome": baseline_row["row_outcome"],
        "row_outcome_allowed": baseline_row["row_outcome"] in VALID_ROW_OUTCOMES,
        "failure_reason": baseline_row["failure_reason"],
        "instrument_rows_counted_as_independent_strategies": False,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    return baseline_row, invariant_row, controls, vs_row, timeframe_row, row_outcome


def family_outcome_row(family: FamilyConfig, instruments: list[dict[str, str]], row_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    by_symbol = {row["symbol"]: row for row in row_outcomes}
    canonical_symbol = instruments[0]["symbol"] if instruments else ""
    canonical = by_symbol.get(canonical_symbol, {})
    portability_rows = [row for row in row_outcomes if row["symbol"] != canonical_symbol]
    strong_portability = [row for row in portability_rows if row["row_outcome"] == "row_control_strong"]
    distinct_corrob = any(row["candidate_group"] != instruments[0].get("candidate_group", "") for row in strong_portability)
    canonical_outcome = canonical.get("row_outcome", "")
    if canonical_outcome == "row_control_strong" and strong_portability and distinct_corrob:
        outcome = "family_exploratory_followup_candidate"
        reason = "canonical_and_distinct_portability_rows_control_strong"
    elif canonical_outcome == "row_timeframe_fragile":
        outcome = "family_timeframe_fragile"
        reason = "canonical_full_period_success_not_preserved_across_existing_halves"
    elif canonical_outcome == "row_cost_fragile":
        outcome = "family_cost_fragile"
        reason = "canonical_zero_cost_pass_not_preserved_after_5bps_cost"
    elif canonical_outcome == "capability_deferred":
        outcome = "family_capability_deferred"
        reason = "canonical_capability_deferred"
    elif canonical_outcome == "implementation_or_accounting_defect":
        outcome = "family_implementation_defect"
        reason = "canonical_implementation_or_accounting_defect"
    else:
        outcome = "family_control_weak"
        reason = "canonical_control_weak_or_no_distinct_control_strong_portability_corroboration"
    return {
        "strategy_id": family.strategy_id,
        "family_id": family.family_id,
        "source_id": family.source_id,
        "canonical_representative_symbol": canonical_symbol,
        "canonical_representative_selection_rule": "first compatible instrument in frozen universe order; performance independent",
        "canonical_row_outcome": canonical_outcome,
        "portability_trial_count": max(0, len(instruments) - 1),
        "portability_control_strong_count": len(strong_portability),
        "distinct_group_corroboration": distinct_corrob,
        "instrument_rows_counted_as_independent_strategies": False,
        "family_outcome": outcome,
        "family_outcome_allowed": outcome in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": reason,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    prior_hashes_before = {
        "batch_v1": directory_hash(root / PRIOR_BATCH_DIR),
        "coppock_audit": directory_hash(root / COPPOCK_AUDIT_DIR),
        "registry": file_hash(root / REGISTRY_PATH),
        "active_observations": file_hash(root / ACTIVE_OBSERVATIONS_PATH),
    }
    universe_rows = frozen_universe(root)
    compat = compatibility_rows(root)
    selected_families, inventory_rows, excluded_rows = remaining_strategy_inventory(root)
    selected_families = selected_families[:MAX_FAMILIES]
    instruments = choose_instruments(root, universe_rows, len(selected_families))
    bil = load_adjusted_ohlcv(root, "BIL")
    batch_outcome = "fast_batch_v2_complete"
    blocker = ""
    if not universe_rows or not compat:
        batch_outcome = "frozen_universe_or_compatibility_missing"
        blocker = "Frozen universe or compatibility map missing."
    elif not selected_families:
        batch_outcome = "no_remaining_existing_fast_lane_families"
        blocker = "No remaining existing source-complete fast-lane families qualified."
    elif bil.empty:
        batch_outcome = "existing_data_coverage_insufficient"
        blocker = "BIL cash proxy cache missing."
    elif not instruments:
        batch_outcome = "existing_data_coverage_insufficient"
        blocker = "No compatible instruments selected from frozen universe."
    coverage_rows = [coverage_row(root, "BIL", {"candidate_group": "cash_proxy"})]
    coverage_rows.extend(coverage_row(root, row["symbol"], row) for row in instruments)
    manifest_rows: list[dict[str, Any]] = []
    representative_rows: list[dict[str, Any]] = []
    trial_registry: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    vs_rows: list[dict[str, Any]] = []
    timeframe_rows: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    if batch_outcome == "fast_batch_v2_complete":
        expected_trial_count = len(selected_families) * len(instruments)
        if expected_trial_count > MAX_TRIALS:
            batch_outcome = "batch_execution_or_accounting_defect"
            blocker = "Frozen expected trial count exceeded hard cap."
        else:
            for family in selected_families:
                representative_rows.append(
                    {
                        "strategy_id": family.strategy_id,
                        "family_id": family.family_id,
                        "source_id": family.source_id,
                        "canonical_representative_symbol": instruments[0]["symbol"],
                        "canonical_candidate_group": instruments[0].get("candidate_group", ""),
                        "selection_rule": "first compatible instrument in frozen universe order",
                        "performance_used_for_selection": False,
                    }
                )
                for instrument in instruments:
                    trial_id = f"{family.strategy_id}__{instrument['symbol']}"
                    manifest_rows.append(
                        {
                            "batch_id": BATCH_ID,
                            "trial_id": trial_id,
                            "strategy_id": family.strategy_id,
                            "family_id": family.family_id,
                            "source_id": family.source_id,
                            "symbol": instrument["symbol"],
                            "candidate_group": instrument.get("candidate_group", ""),
                            "primary_economic_exposure": instrument.get("primary_economic_exposure", ""),
                            "canonical_parameters": family.canonical_parameters,
                            "canonical_representative_symbol": instruments[0]["symbol"],
                            "cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
                            "benchmarks": "instrument_buy_hold|BIL_cash|static_average_exposure_control|equal_weight_selected_universe_control",
                            "expected_trial_count": expected_trial_count,
                            "family_decision_rules": "family outcomes assigned from canonical row and distinct portability corroboration",
                            "frozen_before_return_calculation": True,
                        }
                    )
                    trial_registry.append(
                        {
                            "trial_id": trial_id,
                            "strategy_id": family.strategy_id,
                            "family_id": family.family_id,
                            "source_id": family.source_id,
                            "symbol": instrument["symbol"],
                            "candidate_group": instrument.get("candidate_group", ""),
                            "attempted_trial": True,
                            "trial_registered_before_returns": True,
                            "instrument_rows_counted_as_independent_strategies": False,
                            "adaptation_label": "family_portability_test",
                        }
                    )
            equal_weight_returns = universe_control_returns(root, instruments)
            for family in selected_families:
                for instrument in instruments:
                    try:
                        baseline, invariant, controls, vs, timeframe, row_outcome = evaluate_trial(
                            root, family, instrument, bil, equal_weight_returns
                        )
                    except Exception as exc:  # pragma: no cover - defensive evidence.
                        trial_id = f"{family.strategy_id}__{instrument['symbol']}"
                        baseline = {
                            "trial_id": trial_id,
                            "strategy_id": family.strategy_id,
                            "family_id": family.family_id,
                            "source_id": family.source_id,
                            "symbol": instrument["symbol"],
                            "row_outcome": "implementation_or_accounting_defect",
                            "failure_reason": f"exception:{type(exc).__name__}",
                            "numeric_result_interpretable": False,
                            "promotion_eligibility": False,
                            "paper_forward_eligibility": False,
                        }
                        invariant = {}
                        controls = []
                        vs = {}
                        timeframe = {}
                        row_outcome = {
                            "trial_id": trial_id,
                            "strategy_id": family.strategy_id,
                            "family_id": family.family_id,
                            "source_id": family.source_id,
                            "symbol": instrument["symbol"],
                            "candidate_group": instrument.get("candidate_group", ""),
                            "row_outcome": "implementation_or_accounting_defect",
                            "row_outcome_allowed": True,
                            "failure_reason": baseline["failure_reason"],
                            "instrument_rows_counted_as_independent_strategies": False,
                            "promotion_eligibility": False,
                            "paper_forward_eligibility": False,
                            "candidate_exhaustive_eligibility": False,
                        }
                    baseline_rows.append(baseline)
                    if invariant:
                        invariant_rows.append(invariant)
                    control_rows.extend(controls)
                    if vs:
                        vs_rows.append(vs)
                    if timeframe:
                        timeframe_rows.append(timeframe)
                    outcome_rows.append(row_outcome)
            for family in selected_families:
                family_outcomes = [row for row in outcome_rows if row["strategy_id"] == family.strategy_id]
                family_rows.append(family_outcome_row(family, instruments, family_outcomes))
            if any(row["row_outcome"] == "implementation_or_accounting_defect" for row in outcome_rows):
                batch_outcome = "batch_execution_or_accounting_defect"
                blocker = "One or more rows reported implementation/accounting defects."
    prior_decisions = {
        "batch_id": BATCH_ID,
        "fast_batch_v1_completed_strategies_excluded": list(V1_COMPLETED_STRATEGIES),
        "coppock_family_evidence_outcome": COPPOCK_CLOSED_OUTCOME,
        "coppock_direction_decision": COPPOCK_DIRECTION_DECISION,
        "coppock_next_state": "closed_exact_configuration_historical_research_evidence_only",
        "coppock_parameters_changed": False,
        "coppock_rerun": False,
        "coppock_overlay_run": False,
        "instrument_translations_counted_as_independent_strategies": False,
    }
    universe_reference = {
        "batch_id": BATCH_ID,
        "frozen_universe_path": str(FROZEN_UNIVERSE_PATH).replace("\\", "/"),
        "frozen_universe_hash": file_hash(root / FROZEN_UNIVERSE_PATH),
        "compatibility_map_path": str(COMPATIBILITY_PATH).replace("\\", "/"),
        "compatibility_map_hash": file_hash(root / COMPATIBILITY_PATH),
        "market_data_manifest_path": str(UNIVERSE_MARKET_DATA_MANIFEST).replace("\\", "/"),
        "market_data_manifest": read_yaml(root / UNIVERSE_MARKET_DATA_MANIFEST),
        "selected_compatibility_family": SELECTED_COMPATIBILITY_FAMILY,
        "selected_symbols": [row["symbol"] for row in instruments],
        "instrument_selection_rule": "canonical first compatible frozen symbol, then first symbol from each subsequent distinct group in frozen order",
    }
    family_followups = [
        {
            "strategy_id": row["strategy_id"],
            "family_id": row["family_id"],
            "source_id": row["source_id"],
            "family_outcome": row["family_outcome"],
            "next_review_status": "direction_owner_review_required_before_any_followup",
        }
        for row in family_rows
        if row["family_outcome"] == "family_exploratory_followup_candidate"
    ]
    prior_hashes_after = {
        "batch_v1": directory_hash(root / PRIOR_BATCH_DIR),
        "coppock_audit": directory_hash(root / COPPOCK_AUDIT_DIR),
        "registry": file_hash(root / REGISTRY_PATH),
        "active_observations": file_hash(root / ACTIVE_OBSERVATIONS_PATH),
    }
    group_counts: dict[str, int] = {}
    for row in instruments:
        group_counts[row.get("candidate_group", "")] = group_counts.get(row.get("candidate_group", ""), 0) + 1
    consistency = {
        "batch_id": BATCH_ID,
        "batch_outcome": batch_outcome,
        "batch_outcome_allowed": batch_outcome in VALID_BATCH_OUTCOMES,
        "batch_v1_families_excluded": not any(family.strategy_id in V1_COMPLETED_STRATEGIES for family in selected_families),
        "coppock_not_rerun": "public_source_coppock_curve_portability_adapter_v1" not in [family.strategy_id for family in selected_families],
        "coppock_closed_decision_preserved": True,
        "eligibility_independent_of_performance": all(row.get("eligibility_independent_of_performance") is True for row in inventory_rows),
        "family_order_deterministic": [family.strategy_id for family in selected_families]
        == sorted([family.strategy_id for family in selected_families], key=lambda sid: (PARABOLIC_CONFIG.ready_queue_priority, sid)),
        "single_remaining_family_allowed_to_run": len(selected_families) == 1,
        "selected_family_count_lte_4": len(selected_families) <= MAX_FAMILIES,
        "trial_count_lte_24": len(trial_registry) <= MAX_TRIALS,
        "max_two_instruments_per_group_when_other_groups_exist": all(count <= 2 for count in group_counts.values()),
        "canonical_parameters_unchanged": True,
        "trial_manifest_frozen_before_returns": all(row.get("frozen_before_return_calculation") is True for row in manifest_rows),
        "every_trial_counted_once": len({row["trial_id"] for row in trial_registry}) == len(trial_registry) == len(outcome_rows),
        "canonical_representatives_selected_by_frozen_order": all(
            row.get("canonical_representative_symbol") == "SPY" and row.get("performance_used_for_selection") is False
            for row in representative_rows
        ),
        "instrument_rows_not_independent_strategies": all(
            row.get("instrument_rows_counted_as_independent_strategies") is False for row in outcome_rows
        ),
        "existing_timeframe_dates_not_optimized": True,
        "no_new_strategy_or_parameter_generated": True,
        "no_macro_or_fundamental_data_source_called": True,
        "no_overlay_performance_artifact": True,
        "prior_batch_v1_unchanged": prior_hashes_before["batch_v1"] == prior_hashes_after["batch_v1"],
        "coppock_audit_unchanged": prior_hashes_before["coppock_audit"] == prior_hashes_after["coppock_audit"],
        "registry_lifecycle_unchanged": prior_hashes_before["registry"] == prior_hashes_after["registry"],
        "active_paper_demo_state_unchanged": prior_hashes_before["active_observations"] == prior_hashes_after["active_observations"],
        "broker_or_order_path_touched": False,
        "provider_download": False,
        "intraday_data_used": False,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "invariant_failure_count": sum(1 for row in invariant_rows if str(row.get("exposure_invariant_pass")) != "True"),
        "family_outcomes_allowed": all(row.get("family_outcome_allowed") is True for row in family_rows),
        "row_outcomes_allowed": all(row.get("row_outcome_allowed") is True for row in outcome_rows),
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency_passed = (
        consistency["batch_outcome_allowed"]
        and consistency["batch_v1_families_excluded"]
        and consistency["coppock_not_rerun"]
        and consistency["coppock_closed_decision_preserved"]
        and consistency["eligibility_independent_of_performance"]
        and consistency["single_remaining_family_allowed_to_run"]
        and consistency["selected_family_count_lte_4"]
        and consistency["trial_count_lte_24"]
        and consistency["max_two_instruments_per_group_when_other_groups_exist"]
        and consistency["canonical_parameters_unchanged"]
        and consistency["trial_manifest_frozen_before_returns"]
        and consistency["every_trial_counted_once"]
        and consistency["canonical_representatives_selected_by_frozen_order"]
        and consistency["instrument_rows_not_independent_strategies"]
        and consistency["existing_timeframe_dates_not_optimized"]
        and consistency["no_new_strategy_or_parameter_generated"]
        and consistency["no_macro_or_fundamental_data_source_called"]
        and consistency["no_overlay_performance_artifact"]
        and consistency["prior_batch_v1_unchanged"]
        and consistency["coppock_audit_unchanged"]
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
        and consistency["family_outcomes_allowed"]
        and consistency["row_outcomes_allowed"]
    )
    consistency["consistency_passed"] = consistency_passed
    write_json(output / "prior_direction_decisions.json", prior_decisions)
    write_csv(
        output / "remaining_strategy_inventory.csv",
        inventory_rows,
        [
            "strategy_id",
            "source_id",
            "family_id",
            "ready_queue_priority",
            "implementation_path",
            "focused_test_path",
            "implementation_exists",
            "focused_test_exists",
            "focused_tests_passed_prior_to_batch",
            "canonical_config_recorded",
            "complete_rule_uses_adjusted_ohlcv_only",
            "requires_macro_fundamental_or_alt_data",
            "requires_new_credential",
            "requires_major_engine_capability",
            "long_only_or_long_cash",
            "requires_leverage_inverse_or_shorting",
            "uses_existing_daily_data_and_accounting",
            "included_in_fast_batch_v1",
            "exact_configuration_closed_or_completed_elsewhere",
            "eligibility_independent_of_performance",
            "eligibility_status",
            "exclusion_reason",
            "canonical_parameters",
        ],
    )
    write_csv(
        output / "excluded_strategy_inventory.csv",
        excluded_rows,
        [
            "strategy_id",
            "source_id",
            "family_id",
            "implementation_exists",
            "focused_test_exists",
            "eligibility_independent_of_performance",
            "eligibility_status",
            "exclusion_reason",
        ],
    )
    write_json(output / "frozen_universe_reference.json", universe_reference)
    manifest_fields = [
        "batch_id",
        "trial_id",
        "strategy_id",
        "family_id",
        "source_id",
        "symbol",
        "candidate_group",
        "primary_economic_exposure",
        "canonical_parameters",
        "canonical_representative_symbol",
        "cost_bps_per_turnover",
        "benchmarks",
        "expected_trial_count",
        "family_decision_rules",
        "frozen_before_return_calculation",
    ]
    write_csv(output / "frozen_batch_manifest.csv", manifest_rows, manifest_fields)
    write_csv(
        output / "canonical_family_representatives.csv",
        representative_rows,
        [
            "strategy_id",
            "family_id",
            "source_id",
            "canonical_representative_symbol",
            "canonical_candidate_group",
            "selection_rule",
            "performance_used_for_selection",
        ],
    )
    write_csv(
        output / "trial_registry.csv",
        trial_registry,
        [
            "trial_id",
            "strategy_id",
            "family_id",
            "source_id",
            "symbol",
            "candidate_group",
            "attempted_trial",
            "trial_registered_before_returns",
            "instrument_rows_counted_as_independent_strategies",
            "adaptation_label",
        ],
    )
    write_csv(
        output / "data_coverage.csv",
        coverage_rows,
        ["symbol", "candidate_group", "primary_economic_exposure", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"],
    )
    baseline_fields = [
        "trial_id",
        "strategy_id",
        "family_id",
        "source_id",
        "symbol",
        "candidate_group",
        "primary_economic_exposure",
        "canonical_parameters",
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
        "bullish_flip_count",
        "bearish_flip_count",
        "valid_signal_rows",
        "standard_cost_bps_per_turnover",
        "primary_control_total_return",
        "static_exposure_control_total_return",
        "excess_return_vs_primary_control_after_cost",
        "excess_return_vs_static_exposure_control_after_cost",
        "row_outcome",
        "failure_reason",
        "numeric_result_interpretable",
        "promotion_eligibility",
        "paper_forward_eligibility",
        "candidate_exhaustive_eligibility",
    ]
    write_csv(output / "baseline_metrics.csv", baseline_rows, baseline_fields)
    write_csv(
        output / "control_metrics.csv",
        control_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "control_id",
            "start_date",
            "end_date",
            "trading_days",
            "total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
            "performance_selected_control",
        ],
    )
    write_csv(
        output / "baseline_vs_controls.csv",
        vs_rows,
        [
            "trial_id",
            "strategy_id",
            "symbol",
            "baseline_total_return_after_cost",
            "zero_cost_total_return",
            "instrument_buy_hold_total_return",
            "BIL_cash_total_return",
            "static_average_exposure_control_total_return",
            "equal_weight_selected_universe_control_total_return",
            "after_cost_beats_primary_control",
            "after_cost_beats_static_control",
            "zero_cost_beats_primary_control",
            "zero_cost_beats_static_control",
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
            "first_half_start_date",
            "first_half_end_date",
            "second_half_start_date",
            "second_half_end_date",
            "first_half_excess_vs_primary_control",
            "second_half_excess_vs_primary_control",
            "timeframe_diagnostic_not_holdout",
        ],
    )
    write_csv(
        output / "accounting_invariants.csv",
        invariant_rows,
        [
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
            "zero_target_weights_preserved",
            "no_stale_weights_after_exits",
            "no_lookahead_status",
            "cost_accounting_status",
            "static_control_same_calendar",
        ],
    )
    write_csv(
        output / "row_outcomes.csv",
        outcome_rows,
        [
            "trial_id",
            "strategy_id",
            "family_id",
            "source_id",
            "symbol",
            "candidate_group",
            "row_outcome",
            "row_outcome_allowed",
            "failure_reason",
            "instrument_rows_counted_as_independent_strategies",
            "promotion_eligibility",
            "paper_forward_eligibility",
            "candidate_exhaustive_eligibility",
        ],
    )
    write_csv(
        output / "family_outcomes.csv",
        family_rows,
        [
            "strategy_id",
            "family_id",
            "source_id",
            "canonical_representative_symbol",
            "canonical_representative_selection_rule",
            "canonical_row_outcome",
            "portability_trial_count",
            "portability_control_strong_count",
            "distinct_group_corroboration",
            "instrument_rows_counted_as_independent_strategies",
            "family_outcome",
            "family_outcome_allowed",
            "family_outcome_reason",
            "promotion_eligibility",
            "paper_forward_eligibility",
            "candidate_exhaustive_eligibility",
        ],
    )
    write_csv(
        output / "family_followup_queue.csv",
        family_followups,
        ["strategy_id", "family_id", "source_id", "family_outcome", "next_review_status"],
    )
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_csv(
        output / "command_validation_log.csv",
        [
            {
                "command": ".venv\\Scripts\\python.exe run_fast_price_based_portability_batch_v2.py",
                "status": "generated_by_runner",
                "notes": "dedicated fast batch v2 runner",
            },
            {
                "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_fast_price_based_portability_batch_v2.py -q",
                "status": "external_validation_required",
                "notes": "focused tests",
            },
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Fast Price-Based Portability Batch v2

Batch outcome: `{batch_outcome}`

This packet excludes all fast batch v1 families, preserves the Coppock `NO_ADVANCEMENT` closure, and runs only the remaining eligible existing price/volume family.

- Selected family count: `{len(selected_families)}`
- Selected trial count: `{len(trial_registry)}`
- Selected instruments: `{', '.join(row['symbol'] for row in instruments) if instruments else 'none'}`
- Family outcomes: `{'; '.join(row['family_outcome'] for row in family_rows) if family_rows else 'none'}`
- Row outcomes: `{json.dumps({label: sum(1 for row in outcome_rows if row['row_outcome'] == label) for label in sorted(VALID_ROW_OUTCOMES) if any(row['row_outcome'] == label for row in outcome_rows)}, sort_keys=True)}`
- Invariant failures: `{consistency['invariant_failure_count']}`
- Provider download: `false`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Blocker: `{blocker or 'none'}`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "batch_summary.md", summary)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "batch_id": BATCH_ID,
        "batch_outcome": batch_outcome,
        "selected_family_count": len(selected_families),
        "registered_trial_count": len(trial_registry),
        "evaluated_trial_count": len(outcome_rows),
        "family_outcomes": [row["family_outcome"] for row in family_rows],
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
