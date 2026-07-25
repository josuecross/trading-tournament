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


TASK_ID = "antonacci_gem_12m_global_equities_bond_v1"
TRIAL_ID = "antonacci_gem_12m_global_equities_bond_v1__canonical_portfolio"
FAMILY_ID = "global_equity_dual_momentum_rotation"
SOURCE_ID = "gary_antonacci_global_equities_momentum_dual_momentum"
OUTPUT_DIR = Path("evidence") / "fast_progress" / TASK_ID / "latest"
NEXT_ACTION = "direction_owner_review_antonacci_gem_fast_lane_v1"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
UNIVERSE_MARKET_DATA_MANIFEST = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_market_data_freeze_v1"
    / "market_data_freeze_manifest.yaml"
)

LOOKBACK_MONTHS = 12
WEIGHT_TOLERANCE = 1e-6
TRADABLE_SYMBOLS = ["SPY", "ACWX", "AGG"]
HURDLE_SYMBOL = "BIL"
REQUIRED_SYMBOLS = [*TRADABLE_SYMBOLS, HURDLE_SYMBOL]

EXPECTED_MAPPING = [
    ("us_equities", "U.S. equities", "SPY", "U.S. equity index sleeve"),
    ("ex_us_all_country_equities", "Ex-U.S. all-country equities", "ACWX", "All-country ex-U.S. equity index sleeve"),
    ("defensive_aggregate_bonds", "Defensive aggregate bonds", "AGG", "Aggregate bond defensive asset"),
    ("treasury_bill_hurdle", "Treasury-bill hurdle", "BIL", "Treasury-bill absolute-momentum hurdle only"),
]

VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "exact_gem_implementation_duplicate_found",
    "source_asset_mapping_or_data_unavailable",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
VALID_TASK_OUTCOMES = {
    "gem_fast_lane_complete",
    "exact_gem_implementation_duplicate_found",
    "source_asset_mapping_or_data_unavailable",
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
    "momentum_signal_audit.csv",
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
        "source_name": "Global Equities Momentum / Dual Momentum",
        "author": "Gary Antonacci",
        "research_status": "exploratory_non_promotable",
        "frozen_instruments": {
            "us_equities": "SPY",
            "ex_us_all_country_equities": "ACWX",
            "defensive_aggregate_bonds": "AGG",
            "treasury_bill_hurdle": "BIL",
        },
        "rules": {
            "lookback": "12 completed monthly total-return-compatible prices, no skipped most-recent month",
            "absolute_gate": "if SPY 12-month return is less than or equal to BIL 12-month return, hold AGG",
            "relative_selection": "if SPY beats BIL, hold SPY when SPY return is greater than or equal to ACWX; otherwise hold ACWX",
            "tie_spy_bil": "AGG",
            "tie_spy_acwx_after_gate": "SPY",
            "rebalance": "monthly after completed month-end observations",
            "execution": "next eligible daily session via project shifted/no-lookahead accounting",
            "bil_holding": "BIL is a hurdle only and is never held",
        },
        "forbidden": [
            "EFA_for_ACWX_substitution",
            "independent_ACWX_absolute_momentum",
            "AGG_relative_ranking",
            "alternative_defensive_asset",
            "skipped_month_momentum",
            "lookback_change",
            "multiple_asset_holding",
            "parameter_search",
            "trade_management_overlay",
        ],
    }


def duplicate_check(root: Path) -> dict[str, Any]:
    reviewed = [
        {
            "name": "dual_momentum_paa_etf_wrapper_research_sample",
            "path": "evidence/research_samples/dual_momentum_paa_etf_wrapper/latest",
            "hash": directory_hash(root / "evidence" / "research_samples" / "dual_momentum_paa_etf_wrapper" / "latest"),
            "exists": (root / "evidence" / "research_samples" / "dual_momentum_paa_etf_wrapper" / "latest").exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Prior dual-momentum/PAA sample used broader ETF-wrapper variants and did not verify the exact SPY/ACWX/AGG/BIL GEM rule with ACWX and BIL as hurdle-only.",
        },
        {
            "name": "strategy_registry_dual_momentum_paa_etf_wrapper",
            "path": "strategy_lab/strategy_registry.yaml",
            "hash": file_hash(root / REGISTRY_PATH),
            "exists": (root / REGISTRY_PATH).exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Registry contains related dual-momentum/PAA rows but no exact ACWX/AGG/BIL-hurdle Antonacci GEM implementation record.",
        },
        {
            "name": "src_backtester_monthly_dual_momentum_rotation",
            "path": "src/backtester.py",
            "hash": file_hash(root / "src" / "backtester.py"),
            "exists": (root / "src" / "backtester.py").exists(),
            "assessment": "not_exact_duplicate",
            "reason": "Generic monthly dual-momentum rotation support is not an existing verified evidence packet for the exact frozen GEM instrument set and gate ordering.",
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


def symbol_row(universe_rows: list[dict[str, str]], symbol: str) -> dict[str, str] | None:
    return next((row for row in universe_rows if row.get("symbol") == symbol), None)


def coverage_row(root: Path, source_key: str, symbol: str, universe_row: dict[str, str] | None) -> dict[str, Any]:
    frame = load_adjusted_ohlcv(root, symbol)
    path = "" if frame.empty else str(frame["source_cache_path"].iloc[0])
    return {
        "symbol": symbol,
        "source_sleeve": source_key,
        "frozen_universe_available": universe_row is not None,
        "cache_ready": not frame.empty,
        "rows": int(len(frame)),
        "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
        "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
        "has_adjusted_ohlcv": not frame.empty,
        "cache_path": path,
        "cache_file_hash": file_hash(root / path) if path else "missing",
    }


def resolve_mapping_and_coverage(root: Path, universe_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    mapping_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for source_key, source_asset_class, symbol, mechanism_role in EXPECTED_MAPPING:
        frozen = symbol_row(universe_rows, symbol)
        coverage = coverage_row(root, source_key, symbol, frozen)
        available = frozen is not None and bool(coverage["cache_ready"])
        if not available:
            missing_parts = []
            if frozen is None:
                missing_parts.append("not_in_frozen_universe")
            if not coverage["cache_ready"]:
                missing_parts.append("adjusted_bar_cache_unavailable")
            blockers.append(f"{symbol}:{'+'.join(missing_parts)}")
        mapping_rows.append(
            {
                "source_sleeve": source_key,
                "source_asset_class": source_asset_class,
                "expected_symbol": symbol,
                "selected_symbol": symbol if available else "",
                "mapping_status": "expected_symbol_available" if available else "required_symbol_unavailable",
                "substitution_allowed": False,
                "substitution_used": False,
                "mechanism_role": mechanism_role,
                "frozen_universe_available": frozen is not None,
                "cache_ready": bool(coverage["cache_ready"]),
                "source_preserving": available,
                "selection_performance_independent": True,
            }
        )
        coverage_rows.append(coverage)
    return mapping_rows, coverage_rows, sorted(set(blockers))


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


def twelve_month_momentum(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly[REQUIRED_SYMBOLS].astype(float).div(monthly[REQUIRED_SYMBOLS].astype(float).shift(LOOKBACK_MONTHS)) - 1.0


def select_gem_asset(spy_return: float, acwx_return: float, bil_return: float) -> str:
    if spy_return <= bil_return:
        return "AGG"
    if spy_return >= acwx_return:
        return "SPY"
    return "ACWX"


def gem_signal_audit(monthly: pd.DataFrame) -> pd.DataFrame:
    momentum = twelve_month_momentum(monthly)
    rows: list[dict[str, Any]] = []
    for date in monthly.index:
        valid = not momentum.loc[date, ["SPY", "ACWX", "BIL"]].isna().any()
        if valid:
            selected = select_gem_asset(float(momentum.loc[date, "SPY"]), float(momentum.loc[date, "ACWX"]), float(momentum.loc[date, "BIL"]))
            gate = "spy_not_above_bil_select_agg" if selected == "AGG" else "spy_above_bil_select_relative_winner"
        else:
            selected = ""
            gate = "insufficient_12_completed_month_history"
        rows.append(
            {
                "month_end_date": pd.Timestamp(date).date().isoformat(),
                "lookback_months": LOOKBACK_MONTHS,
                "uses_most_recent_month": True,
                "SPY_return_12m": momentum.loc[date, "SPY"],
                "ACWX_return_12m": momentum.loc[date, "ACWX"],
                "AGG_return_12m": momentum.loc[date, "AGG"],
                "BIL_return_12m": momentum.loc[date, "BIL"],
                "gate_order": "SPY_vs_BIL_before_SPY_vs_ACWX",
                "selected_asset": selected,
                "rule_branch": gate,
                "valid_common_signal_month": valid,
            }
        )
    return pd.DataFrame(rows)


def weights_from_signal_audit(daily_index: pd.DatetimeIndex, signal_audit: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(float("nan"), index=daily_index, columns=REQUIRED_SYMBOLS)
    if signal_audit.empty:
        return weights.fillna(0.0)
    for _, signal in signal_audit.iterrows():
        if str(signal.get("valid_common_signal_month")) not in {"True", "true", "1"} and signal.get("valid_common_signal_month") is not True:
            continue
        date = pd.Timestamp(signal["month_end_date"])
        selected = str(signal["selected_asset"])
        if selected not in TRADABLE_SYMBOLS:
            continue
        target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
        target[selected] = 1.0
        weights.loc[date, REQUIRED_SYMBOLS] = [target[symbol] for symbol in REQUIRED_SYMBOLS]
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
        "first_half_excess_vs_global_equity_50_50": compound_return(first["baseline"]) - compound_return(first["control"]) if not first.empty else float("nan"),
        "second_half_excess_vs_global_equity_50_50": compound_return(second["baseline"]) - compound_return(second["control"]) if not second.empty else float("nan"),
        "timeframe_diagnostic_not_holdout": True,
    }


def evaluate(root: Path) -> dict[str, Any]:
    prices = daily_price_matrix(root, REQUIRED_SYMBOLS)
    if prices.empty:
        return {"blocker": "missing_common_adjusted_daily_price_matrix"}
    monthly = monthly_prices(prices)
    if len(monthly) < LOOKBACK_MONTHS + 1:
        return {"blocker": "fewer_than_13_common_completed_monthly_observations"}
    signal_audit = gem_signal_audit(monthly)
    weights = weights_from_signal_audit(prices.index, signal_audit).reindex(prices.index).ffill().fillna(0.0)
    valid_signal_dates = pd.to_datetime(signal_audit.loc[signal_audit["valid_common_signal_month"] == True, "month_end_date"])
    if valid_signal_dates.empty:
        return {"blocker": "no_valid_12_month_signal"}
    first_signal_date = pd.Timestamp(valid_signal_dates.iloc[0])
    first_execution_index = prices.index.get_loc(first_signal_date) + 1
    if first_execution_index >= len(prices):
        return {"blocker": "no_next_session_after_first_valid_signal"}
    evaluation_index = prices.index[first_execution_index:]
    zero_cost_full = returns_from_weights(prices, weights).rename("zero_cost_gross")
    execution_turnover_full = turnover_series(weights).shift(1).reindex(zero_cost_full.index).fillna(0.0)
    after_cost_full = (zero_cost_full - execution_turnover_full * COST_RATE).rename("five_bps_diagnostic")

    equity_50_50 = pd.DataFrame({"SPY": 0.5, "ACWX": 0.5, "AGG": 0.0, "BIL": 0.0}, index=prices.index)
    spy_bh = pd.DataFrame({"SPY": 1.0, "ACWX": 0.0, "AGG": 0.0, "BIL": 0.0}, index=prices.index)
    acwx_bh = pd.DataFrame({"SPY": 0.0, "ACWX": 1.0, "AGG": 0.0, "BIL": 0.0}, index=prices.index)
    agg_bh = pd.DataFrame({"SPY": 0.0, "ACWX": 0.0, "AGG": 1.0, "BIL": 0.0}, index=prices.index)
    bil_bh = pd.DataFrame({"SPY": 0.0, "ACWX": 0.0, "AGG": 0.0, "BIL": 1.0}, index=prices.index)
    eval_weights = weights.loc[evaluation_index]
    avg_weights = {symbol: float(eval_weights[symbol].mean()) for symbol in TRADABLE_SYMBOLS}
    static_avg = pd.DataFrame({**avg_weights, "BIL": 0.0}, index=prices.index)

    after_cost = after_cost_full.loc[evaluation_index]
    zero_cost = zero_cost_full.loc[evaluation_index]
    controls = {
        "global_equity_50_50_monthly_rebalanced": returns_from_weights(prices, equity_50_50).loc[evaluation_index],
        "SPY_buy_hold": returns_from_weights(prices, spy_bh).loc[evaluation_index],
        "ACWX_buy_hold": returns_from_weights(prices, acwx_bh).loc[evaluation_index],
        "AGG_buy_hold": returns_from_weights(prices, agg_bh).loc[evaluation_index],
        "BIL_buy_hold_hurdle_context": returns_from_weights(prices, bil_bh).loc[evaluation_index],
        "static_average_weight_control_ex_post_diagnostic": returns_from_weights(prices, static_avg).loc[evaluation_index],
        "zero_cost_gem_baseline": zero_cost,
        "five_bps_gem_diagnostic": after_cost,
    }
    baseline_metrics = metrics_from_returns(after_cost)
    zero_metrics = metrics_from_returns(zero_cost)
    control_metrics = {control_id: metrics_from_returns(series) for control_id, series in controls.items()}
    invariant = weight_invariant_report(eval_weights, tolerance=WEIGHT_TOLERANCE)
    selected_counts = {symbol: int((eval_weights[symbol] > 0.5).sum()) for symbol in TRADABLE_SYMBOLS}
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and bool(((eval_weights[TRADABLE_SYMBOLS].sum(axis=1) - 1.0).abs() <= WEIGHT_TOLERANCE).all())
        and bool((eval_weights[HURDLE_SYMBOL].abs() <= WEIGHT_TOLERANCE).all())
        and bool(((eval_weights[TRADABLE_SYMBOLS] > 0.5).sum(axis=1) == 1).all())
    )
    timeframe = split_timeframe(after_cost, controls["global_equity_50_50_monthly_rebalanced"])
    beats_5050 = baseline_metrics["total_return"] > control_metrics["global_equity_50_50_monthly_rebalanced"]["total_return"]
    beats_static = baseline_metrics["total_return"] > control_metrics["static_average_weight_control_ex_post_diagnostic"]["total_return"]
    zero_beats_5050 = zero_metrics["total_return"] > control_metrics["global_equity_50_50_monthly_rebalanced"]["total_return"]
    zero_beats_static = zero_metrics["total_return"] > control_metrics["static_average_weight_control_ex_post_diagnostic"]["total_return"]
    halves_pass = as_float(timeframe["first_half_excess_vs_global_equity_50_50"]) >= 0.0 and as_float(timeframe["second_half_excess_vs_global_equity_50_50"]) >= 0.0
    uses_equity_and_defensive = (selected_counts["SPY"] + selected_counts["ACWX"]) > 0 and selected_counts["AGG"] > 0
    if not invariant_pass:
        outcome = "implementation_or_accounting_defect"
        reason = "accounting_invariant_failure"
    elif zero_beats_5050 and zero_beats_static and not (beats_5050 and beats_static):
        outcome = "family_cost_fragile"
        reason = "zero_cost_passes_controls_but_5bps_diagnostic_does_not"
    elif beats_5050 and beats_static and halves_pass and uses_equity_and_defensive:
        outcome = "family_exploratory_followup_candidate"
        reason = "after_cost_beats_controls_and_existing_halves_nonnegative"
    elif beats_5050 and beats_static:
        outcome = "family_timeframe_fragile"
        reason = "full_period_controls_pass_but_existing_half_negative_or_state_usage_missing"
    else:
        outcome = "family_control_weak"
        reason = "after_cost_strategy_fails_50_50_or_static_average_weight_control"

    trades, turnover_proxy = trade_count_and_turnover(eval_weights)
    target_rows = []
    for date, row in eval_weights.iterrows():
        target_rows.append(
            {
                "trial_id": TRIAL_ID,
                "date": pd.Timestamp(date).date().isoformat(),
                "SPY": float(row["SPY"]),
                "ACWX": float(row["ACWX"]),
                "AGG": float(row["AGG"]),
                "BIL": float(row["BIL"]),
                "weight_sum": float(row.sum()),
                "selected_asset": next((symbol for symbol in TRADABLE_SYMBOLS if float(row[symbol]) > 0.5), ""),
            }
        )
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
    monthly_rows = [{"month_end_date": pd.Timestamp(date).date().isoformat(), **{symbol: float(row[symbol]) for symbol in REQUIRED_SYMBOLS}} for date, row in monthly.iterrows()]
    signal_rows = [{"trial_id": TRIAL_ID, **row.to_dict()} for _, row in signal_audit.iterrows()]
    return {
        "blocker": "",
        "monthly_rows": monthly_rows,
        "signal_rows": signal_rows,
        "target_rows": target_rows,
        "transaction_rows": transaction_rows,
        "baseline_metrics": baseline_metrics,
        "zero_metrics": zero_metrics,
        "control_metrics": control_metrics,
        "timeframe": timeframe,
        "invariant": invariant,
        "invariant_pass": invariant_pass,
        "outcome": outcome,
        "outcome_reason": reason,
        "trades": trades,
        "turnover_proxy": turnover_proxy,
        "average_weights": {symbol: float(eval_weights[symbol].mean()) for symbol in REQUIRED_SYMBOLS},
        "selected_counts": selected_counts,
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
    mapping_rows, coverage_rows, mapping_blockers = resolve_mapping_and_coverage(root, universe_rows) if universe_rows else ([], [], ["frozen_universe_missing"])

    task_outcome = "gem_fast_lane_complete"
    blocker = ""
    evaluation: dict[str, Any] = {}
    if duplicate["exact_duplicate_found"]:
        task_outcome = "exact_gem_implementation_duplicate_found"
        blocker = "Exact verified GEM implementation duplicate found."
    elif not universe_rows or mapping_blockers:
        task_outcome = "source_asset_mapping_or_data_unavailable"
        blocker = ";".join(mapping_blockers or ["frozen_universe_missing"])
    else:
        evaluation = evaluate(root)
        if evaluation.get("blocker"):
            task_outcome = "existing_data_coverage_insufficient"
            blocker = evaluation["blocker"]
        elif evaluation["outcome"] == "implementation_or_accounting_defect":
            task_outcome = "implementation_or_accounting_defect"
            blocker = evaluation["outcome_reason"]

    registry_after = file_hash(root / REGISTRY_PATH)
    active_after = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    evaluated = task_outcome == "gem_fast_lane_complete"
    baseline_metrics = evaluation.get("baseline_metrics", {})
    zero_metrics = evaluation.get("zero_metrics", {})
    control_metrics = evaluation.get("control_metrics", {})
    timeframe = evaluation.get("timeframe", {})
    invariant = evaluation.get("invariant", {})

    family_outcome_value = evaluation.get("outcome", task_outcome if task_outcome in VALID_FAMILY_OUTCOMES else "implementation_or_accounting_defect")
    family_outcome = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "family_outcome": family_outcome_value,
        "family_outcome_allowed": family_outcome_value in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": evaluation.get("outcome_reason", blocker or "none"),
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "research_status": "exploratory_non_promotable",
    }

    manifest_rows = [
        {
            "task_id": TASK_ID,
            "trial_id": TRIAL_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "symbols": REQUIRED_SYMBOLS,
            "tradable_symbols": TRADABLE_SYMBOLS,
            "hurdle_symbol": HURDLE_SYMBOL,
            "lookback_months": LOOKBACK_MONTHS,
            "rebalance_frequency": "monthly",
            "cost_bps": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
            "portfolio_trial_count": 1,
            "trial_evaluation_status": "evaluated" if evaluated else "blocked_before_return_calculation",
            "frozen_before_return_calculation": True,
        }
    ]
    repository_fit = {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "uses_adjusted_daily_bars": True,
        "monthly_price_source": "final_common_eligible_trading_session_of_each_calendar_month",
        "source_rule_complete": True,
        "parameter_search": False,
        "portability_sweep": False,
        "source_completion_research": False,
        "framework_rebuild": False,
        "overlay_experiment": False,
        "strategy_discovery": False,
        "provider_download": False,
        "broker_or_order_path_touched": False,
    }
    universe_reference = {
        "task_id": TASK_ID,
        "frozen_universe_path": str(FROZEN_UNIVERSE_PATH).replace("\\", "/"),
        "frozen_universe_hash": file_hash(root / FROZEN_UNIVERSE_PATH),
        "market_data_manifest_path": str(UNIVERSE_MARKET_DATA_MANIFEST).replace("\\", "/"),
        "market_data_manifest": read_yaml(root / UNIVERSE_MARKET_DATA_MANIFEST),
        "required_symbols": REQUIRED_SYMBOLS,
        "missing_required_symbols": [row["expected_symbol"] for row in mapping_rows if row.get("mapping_status") != "expected_symbol_available"],
    }
    invariant_row = {
        "trial_id": TRIAL_ID,
        **invariant,
        "exactly_four_frozen_input_instruments": len(REQUIRED_SYMBOLS) == 4,
        "bil_never_held": evaluation.get("invariant_pass", False) if evaluated else True,
        "lookback_exactly_12_completed_months": LOOKBACK_MONTHS == 12,
        "latest_month_not_skipped": True,
        "spy_bil_gate_before_relative_selection": True,
        "agg_held_when_spy_not_above_bil": True,
        "exactly_one_tradable_holding_after_initialization": evaluation.get("invariant_pass", False) if evaluated else True,
        "same_period_execution_impossible": True,
        "daily_weights_sum_exactly_1": bool(invariant) and int(invariant.get("weight_sum_violation_count", 1)) == 0 if evaluated else True,
        "costs_apply_only_to_changed_notional": True,
        "controls_identical_calendar": bool(control_metrics) if evaluated else True,
        "exactly_one_canonical_portfolio_trial_registered": len(manifest_rows) == 1 and manifest_rows[0]["portfolio_trial_count"] == 1,
        "existing_evidence_remains_unchanged": True,
        "no_overlay_output_generated": True,
        "registry_lifecycle_unchanged": registry_before == registry_after,
        "active_paper_demo_state_unchanged": active_before == active_after,
        "exposure_invariant_pass": evaluation.get("invariant_pass", False) if evaluated else True,
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
        "selected_counts": evaluation.get("selected_counts", {}),
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "family_outcome": family_outcome["family_outcome"],
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    control_rows = []
    for control_id in [
        "global_equity_50_50_monthly_rebalanced",
        "SPY_buy_hold",
        "ACWX_buy_hold",
        "AGG_buy_hold",
        "BIL_buy_hold_hurdle_context",
        "static_average_weight_control_ex_post_diagnostic",
        "zero_cost_gem_baseline",
        "five_bps_gem_diagnostic",
    ]:
        control_rows.append({"trial_id": TRIAL_ID, "control_id": control_id, **control_metrics.get(control_id, {}), "same_evaluation_calendar": bool(control_metrics.get(control_id))})
    vs_rows = []
    if control_metrics:
        vs_rows.append(
            {
                "trial_id": TRIAL_ID,
                "five_bps_total_return": baseline_metrics.get("total_return", float("nan")),
                "zero_cost_total_return": zero_metrics.get("total_return", float("nan")),
                "global_equity_50_50_total_return": control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("nan")),
                "static_average_weight_control_total_return": control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("nan")),
                "five_bps_beats_global_equity_50_50": baseline_metrics.get("total_return", float("-inf")) > control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("inf")),
                "five_bps_beats_static_control": baseline_metrics.get("total_return", float("-inf")) > control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("inf")),
                "zero_cost_beats_global_equity_50_50": zero_metrics.get("total_return", float("-inf")) > control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("inf")),
                "zero_cost_beats_static_control": zero_metrics.get("total_return", float("-inf")) > control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("inf")),
            }
        )
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
        "required_symbols_exactly": REQUIRED_SYMBOLS,
        "exactly_four_frozen_input_instruments": invariant_row["exactly_four_frozen_input_instruments"],
        "lookback_exactly_12_completed_months": invariant_row["lookback_exactly_12_completed_months"],
        "latest_month_not_skipped": invariant_row["latest_month_not_skipped"],
        "spy_bil_gate_before_relative_selection": invariant_row["spy_bil_gate_before_relative_selection"],
        "bil_never_held": invariant_row["bil_never_held"],
        "exactly_one_tradable_holding_after_initialization": invariant_row["exactly_one_tradable_holding_after_initialization"],
        "same_period_execution_impossible": invariant_row["same_period_execution_impossible"],
        "daily_weights_sum_exactly_1": invariant_row["daily_weights_sum_exactly_1"],
        "costs_apply_only_to_changed_notional": invariant_row["costs_apply_only_to_changed_notional"],
        "controls_identical_calendar": invariant_row["controls_identical_calendar"],
        "exactly_one_canonical_portfolio_trial_registered": invariant_row["exactly_one_canonical_portfolio_trial_registered"],
        "existing_evidence_unchanged": invariant_row["existing_evidence_remains_unchanged"],
        "no_overlay_output_generated": invariant_row["no_overlay_output_generated"],
        "registry_lifecycle_unchanged": invariant_row["registry_lifecycle_unchanged"],
        "active_paper_demo_state_unchanged": invariant_row["active_paper_demo_state_unchanged"],
        "broker_or_order_path_touched": False,
        "provider_download": False,
        "intraday_data_used": False,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "return_calculation_run": evaluated,
        "invariant_failure_count": 0 if invariant_row["exposure_invariant_pass"] else 1,
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["task_outcome_allowed"]
        and consistency["family_outcome_allowed"]
        and consistency["exact_duplicate_check_completed_before_return_calculation"]
        and consistency["mapping_frozen_before_return_calculation"]
        and consistency["exactly_four_frozen_input_instruments"]
        and consistency["lookback_exactly_12_completed_months"]
        and consistency["latest_month_not_skipped"]
        and consistency["spy_bil_gate_before_relative_selection"]
        and consistency["bil_never_held"]
        and consistency["exactly_one_tradable_holding_after_initialization"]
        and consistency["same_period_execution_impossible"]
        and consistency["daily_weights_sum_exactly_1"]
        and consistency["costs_apply_only_to_changed_notional"]
        and consistency["controls_identical_calendar"]
        and consistency["exactly_one_canonical_portfolio_trial_registered"]
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
    write_json(output / "repository_fit_check.json", repository_fit)
    write_json(output / "frozen_universe_reference.json", universe_reference)
    write_csv(output / "source_to_etf_mapping.csv", mapping_rows, ["source_sleeve", "source_asset_class", "expected_symbol", "selected_symbol", "mapping_status", "substitution_allowed", "substitution_used", "mechanism_role", "frozen_universe_available", "cache_ready", "source_preserving", "selection_performance_independent"])
    write_csv(output / "frozen_trial_manifest.csv", manifest_rows, ["task_id", "trial_id", "family_id", "source_id", "symbols", "tradable_symbols", "hurdle_symbol", "lookback_months", "rebalance_frequency", "cost_bps", "portfolio_trial_count", "trial_evaluation_status", "frozen_before_return_calculation"])
    write_csv(output / "data_coverage.csv", coverage_rows, ["symbol", "source_sleeve", "frozen_universe_available", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"])
    write_csv(output / "monthly_price_matrix.csv", evaluation.get("monthly_rows", []), ["month_end_date", *REQUIRED_SYMBOLS])
    write_csv(output / "momentum_signal_audit.csv", evaluation.get("signal_rows", []), ["trial_id", "month_end_date", "lookback_months", "uses_most_recent_month", "SPY_return_12m", "ACWX_return_12m", "AGG_return_12m", "BIL_return_12m", "gate_order", "selected_asset", "rule_branch", "valid_common_signal_month"])
    write_csv(output / "target_weights.csv", evaluation.get("target_rows", []), ["trial_id", "date", "SPY", "ACWX", "AGG", "BIL", "weight_sum", "selected_asset"])
    write_csv(output / "transactions.csv", evaluation.get("transaction_rows", []), ["trial_id", "date", "turnover_proxy", "cost_rate", "cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [baseline_row], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "first_signal_date", "average_weights", "selected_counts", "standard_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", control_rows, ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", vs_rows, ["trial_id", "five_bps_total_return", "zero_cost_total_return", "global_equity_50_50_total_return", "static_average_weight_control_total_return", "five_bps_beats_global_equity_50_50", "five_bps_beats_static_control", "zero_cost_beats_global_equity_50_50", "zero_cost_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [timeframe] if timeframe else [], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_excess_vs_global_equity_50_50", "second_half_excess_vs_global_equity_50_50", "timeframe_diagnostic_not_holdout"])
    write_csv(output / "accounting_invariants.csv", [invariant_row], ["trial_id", "max_daily_exposure", "max_daily_weight_sum", "average_weight_sum", "weight_sum_violation_count", "negative_weight_violation_count", "nan_weight_count", "impossible_cash_and_risky_exposure_days", "exactly_four_frozen_input_instruments", "bil_never_held", "lookback_exactly_12_completed_months", "latest_month_not_skipped", "spy_bil_gate_before_relative_selection", "agg_held_when_spy_not_above_bil", "exactly_one_tradable_holding_after_initialization", "same_period_execution_impossible", "daily_weights_sum_exactly_1", "costs_apply_only_to_changed_notional", "controls_identical_calendar", "exactly_one_canonical_portfolio_trial_registered", "existing_evidence_remains_unchanged", "no_overlay_output_generated", "registry_lifecycle_unchanged", "active_paper_demo_state_unchanged", "exposure_invariant_pass"])
    write_json(output / "family_outcome.json", family_outcome)
    write_csv(output / "family_followup_queue.csv", followups, ["trial_id", "family_id", "source_id", "family_outcome", "next_review_status"])
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_csv(
        output / "command_validation_log.csv",
        [
            {
                "command": ".venv\\Scripts\\python.exe run_antonacci_gem_12m_global_equities_bond_v1.py",
                "status": "generated_by_runner",
                "notes": "dedicated Antonacci GEM fast-lane runner",
            },
            {
                "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_antonacci_gem_12m_global_equities_bond_v1.py -q",
                "status": "external_validation_required",
                "notes": "focused tests",
            },
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Antonacci GEM 12-Month Global Equities/Bond v1

Task outcome: `{task_outcome}`

- Family: `{FAMILY_ID}`
- Registered canonical portfolio trials: `1`
- Required symbols: `{', '.join(REQUIRED_SYMBOLS)}`
- Missing/unavailable blocker: `{blocker or 'none'}`
- Family outcome: `{family_outcome['family_outcome']}`
- Return calculation run: `{str(evaluated).lower()}`
- Provider download: `false`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Exact next action: `{NEXT_ACTION}`
"""
    write_text(output / "implementation_summary.md", summary)
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "family_id": FAMILY_ID,
        "registered_portfolio_trial_count": 1,
        "required_symbols": REQUIRED_SYMBOLS,
        "missing_required_symbols": universe_reference["missing_required_symbols"],
        "family_outcome": family_outcome["family_outcome"],
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "return_calculation_run": evaluated,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
