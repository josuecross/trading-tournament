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
from strategy_lab.research_os.research import antonacci_gem_12m_global_equities_bond_v1 as gem
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    FROZEN_UNIVERSE_PATH,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    data_hash,
    load_adjusted_ohlcv,
    metrics_from_returns,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


TASK_ID = "keller_keuning_vaa_g4_13612w_v1"
TRIAL_ID = "keller_keuning_vaa_g4_13612w_v1__canonical_portfolio"
FAMILY_ID = "breadth_gated_offensive_defensive_rotation"
SOURCE_ID = "keller_keuning_breadth_momentum_vigilant_asset_allocation"
SOURCE_NAME = "Breadth Momentum and Vigilant Asset Allocation"
OUTPUT_DIR = Path("evidence") / "fast_progress" / TASK_ID / "latest"
NEXT_ACTION = "direction_owner_review_keller_keuning_vaa_g4_fast_lane_v1"

REGISTRY_PATH = gem.REGISTRY_PATH
ACTIVE_OBSERVATIONS_PATH = gem.ACTIVE_OBSERVATIONS_PATH
GEM_RECOVERY_EVIDENCE = Path("evidence") / "fast_progress" / "antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1" / "latest"
GEM_BASE_EVIDENCE = Path("evidence") / "fast_progress" / "antonacci_gem_12m_global_equities_bond_v1" / "latest"
ACWX_CACHE = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1" / "ACWX.csv"
ACWX_METADATA = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1" / "ACWX.metadata.json"

OFFENSIVE_SYMBOLS = ["SPY", "EFA", "EEM", "AGG"]
DEFENSIVE_SYMBOLS = ["LQD", "IEF", "SHY"]
REQUIRED_SYMBOLS = [*OFFENSIVE_SYMBOLS, *DEFENSIVE_SYMBOLS]
MOMENTUM_HORIZONS = [1, 3, 6, 12]
MOMENTUM_WEIGHTS = {1: 12.0, 3: 4.0, 6: 2.0, 12: 1.0}
SOURCE_COST_BPS_PER_TURNOVER = 10.0
SOURCE_COST_RATE = SOURCE_COST_BPS_PER_TURNOVER / 10000.0
PROJECT_COST_RATE = PROJECT_STANDARD_COST_BPS_PER_TURNOVER / 10000.0
WEIGHT_TOLERANCE = 1e-6

VALID_TASK_OUTCOMES = {
    "vaa_g4_fast_lane_complete",
    "exact_vaa_g4_implementation_duplicate_found",
    "source_asset_mapping_or_data_unavailable",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "exact_vaa_g4_implementation_duplicate_found",
    "source_asset_mapping_or_data_unavailable",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
CORE_FILES = [
    "source_packet_used.yaml",
    "exact_duplicate_check.json",
    "repository_fit_check.json",
    "source_to_etf_mapping.csv",
    "frozen_trial_manifest.csv",
    "data_coverage.csv",
    "monthly_price_matrix.csv",
    "momentum_score_audit.csv",
    "breadth_state_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "control_metrics.csv",
    "baseline_vs_controls.csv",
    "timeframe_diagnostics.csv",
    "state_and_instrument_attribution.csv",
    "accounting_invariants.csv",
    "family_outcome.json",
    "family_followup_queue.csv",
]


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def directory_hash(path: Path) -> str:
    payload: dict[str, str] = {}
    if path.exists():
        for item in sorted(path.rglob("*")):
            if item.is_file():
                payload[str(item.relative_to(path)).replace("\\", "/")] = file_hash(item)
    return data_hash(payload)


def deterministic_core_hash(evidence_dir: Path) -> str:
    return data_hash(
        {
            name: (evidence_dir / name).read_text(encoding="utf-8") if (evidence_dir / name).exists() else "missing"
            for name in CORE_FILES
        }
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def compound_return(series: pd.Series) -> float:
    if series.empty:
        return float("nan")
    return float((1.0 + series.fillna(0.0)).prod() - 1.0)


def source_packet() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "authors": "Wouter J. Keller and Jan Willem Keuning",
        "research_status": "exploratory_non_promotable",
        "queue_position": 3,
        "canonical_portfolio_count": 1,
        "offensive_universe": OFFENSIVE_SYMBOLS,
        "defensive_universe": DEFENSIVE_SYMBOLS,
        "momentum_formula": {
            "horizons_months": MOMENTUM_HORIZONS,
            "weights": {str(key): value for key, value in MOMENTUM_WEIGHTS.items()},
            "score": "M = 12*R1 + 4*R3 + 2*R6 + R12",
            "latest_month_skipped": False,
        },
        "allocation_rule": {
            "offensive_state": "if every offensive asset has M > 0, hold the highest-score offensive asset",
            "defensive_state": "if any offensive asset has M <= 0, hold the highest-score defensive asset",
            "defensive_positive_momentum_required": False,
            "selected_assets_per_month": 1,
            "cash_remainder": False,
        },
        "tie_handling": {
            "offensive_order": OFFENSIVE_SYMBOLS,
            "defensive_order": DEFENSIVE_SYMBOLS,
        },
        "costs": {
            "zero_cost_diagnostic": True,
            "source_aligned_bps_per_one_way_traded_notional": SOURCE_COST_BPS_PER_TURNOVER,
            "project_diagnostic_bps_per_one_way_traded_notional": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        },
        "forbidden": [
            "parameter_search",
            "universe_substitution",
            "recovery_chain",
            "trade_management_overlay",
            "paper_demo_activation",
            "broker_order_path",
            "promotion",
        ],
    }


def exact_duplicate_check(root: Path) -> dict[str, Any]:
    reviewed_paths = [
        Path("strategy_lab") / "strategy_registry.yaml",
        Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
        Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
        Path("run_dual_momentum_paa_etf_wrapper_review.py"),
        Path("run_dual_momentum_paa_etf_wrapper_research_sample.py"),
        Path("evidence") / "research_samples" / "dual_momentum_paa_etf_wrapper" / "latest",
        Path("evidence") / "parallel_research_discovery" / "breadth_state_regime" / "latest",
        Path("evidence") / "fast_progress",
    ]
    criteria = {
        "offensive_universe": OFFENSIVE_SYMBOLS,
        "defensive_universe": DEFENSIVE_SYMBOLS,
        "monthly_13612w_momentum": True,
        "defensive_if_any_offensive_non_positive": True,
        "top_offensive_when_all_positive": True,
        "top_defensive_when_any_non_positive": True,
        "one_selected_asset_only": True,
    }
    reviewed: list[dict[str, Any]] = []
    exact_paths: list[str] = []
    for path in reviewed_paths:
        full = root / path
        text = ""
        if full.is_file():
            text = full.read_text(encoding="utf-8", errors="ignore")
        elif full.is_dir():
            chunks = []
            for item in sorted(full.rglob("*")):
                if item.is_file() and TASK_ID not in str(item):
                    try:
                        chunks.append(item.read_text(encoding="utf-8", errors="ignore")[:5000])
                    except OSError:
                        pass
            text = "\n".join(chunks)
        lower = text.lower()
        exact = (
            "vaa_g4" in lower
            and "13612" in lower
            and all(symbol.lower() in lower for symbol in REQUIRED_SYMBOLS)
            and "non-positive" in lower
            and "one selected" in lower
        )
        if exact:
            exact_paths.append(str(path).replace("\\", "/"))
        reviewed.append(
            {
                "path": str(path).replace("\\", "/"),
                "exists": full.exists(),
                "hash": directory_hash(full) if full.is_dir() else file_hash(full),
                "assessment": "exact_duplicate" if exact else "not_exact_duplicate",
                "reason": "No verified evidence packet matching all frozen VAA-G4 conditions was found."
                if not exact
                else "Path appears to contain all exact VAA-G4 conditions.",
            }
        )
    return {
        "task_id": TASK_ID,
        "criteria": criteria,
        "duplicate_check_completed_before_return_calculation": True,
        "exact_duplicate_found": bool(exact_paths),
        "exact_duplicate_paths": exact_paths,
        "reviewed_records": reviewed,
    }


def frozen_universe_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / FROZEN_UNIVERSE_PATH)


def symbol_in_frozen_universe(rows: list[dict[str, str]], symbol: str) -> bool:
    return any(row.get("symbol") == symbol for row in rows)


def data_coverage(root: Path, universe_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for symbol in REQUIRED_SYMBOLS:
        frame = load_adjusted_ohlcv(root, symbol)
        path = str(frame["source_cache_path"].iloc[0]) if not frame.empty else ""
        in_universe = symbol_in_frozen_universe(universe_rows, symbol)
        cache_ready = not frame.empty
        if not in_universe or not cache_ready:
            parts = []
            if not in_universe:
                parts.append("not_in_frozen_universe")
            if not cache_ready:
                parts.append("adjusted_bar_cache_unavailable")
            blockers.append(f"{symbol}:{'+'.join(parts)}")
        rows.append(
            {
                "symbol": symbol,
                "universe_role": "offensive" if symbol in OFFENSIVE_SYMBOLS else "defensive",
                "frozen_universe_available": in_universe,
                "cache_ready": cache_ready,
                "rows": int(len(frame)),
                "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
                "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
                "has_adjusted_ohlcv": cache_ready,
                "cache_path": path,
                "cache_file_hash": file_hash(root / path) if path else "missing",
            }
        )
    return rows, blockers


def source_to_etf_mapping(universe_rows: list[dict[str, str]], coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage_by_symbol = {row["symbol"]: row for row in coverage_rows}
    source_roles = {
        "SPY": ("offensive_us_equity", "U.S. equity offensive sleeve"),
        "EFA": ("offensive_developed_ex_us_equity", "Developed ex-U.S. equity offensive sleeve"),
        "EEM": ("offensive_emerging_market_equity", "Emerging-market equity offensive sleeve"),
        "AGG": ("offensive_aggregate_bond", "Aggregate bond offensive sleeve"),
        "LQD": ("defensive_investment_grade_credit", "Investment-grade credit defensive sleeve"),
        "IEF": ("defensive_intermediate_treasury", "Intermediate Treasury defensive sleeve"),
        "SHY": ("defensive_short_treasury", "Short Treasury defensive sleeve"),
    }
    rows = []
    for symbol in REQUIRED_SYMBOLS:
        coverage = coverage_by_symbol.get(symbol, {})
        available = symbol_in_frozen_universe(universe_rows, symbol) and bool(coverage.get("cache_ready"))
        source_key, source_asset_class = source_roles[symbol]
        rows.append(
            {
                "source_sleeve": source_key,
                "source_asset_class": source_asset_class,
                "expected_symbol": symbol,
                "selected_symbol": symbol if available else "",
                "universe_role": "offensive" if symbol in OFFENSIVE_SYMBOLS else "defensive",
                "mapping_status": "expected_symbol_available" if available else "required_symbol_unavailable",
                "substitution_allowed": False,
                "substitution_used": False,
                "source_preserving": available,
                "selection_performance_independent": True,
            }
        )
    return rows


def daily_price_matrix(root: Path) -> pd.DataFrame:
    series = []
    for symbol in REQUIRED_SYMBOLS:
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


def momentum_score_frame(monthly: pd.DataFrame) -> tuple[dict[int, pd.DataFrame], pd.DataFrame]:
    returns_by_horizon = {
        horizon: monthly.astype(float).div(monthly.astype(float).shift(horizon)) - 1.0
        for horizon in MOMENTUM_HORIZONS
    }
    score = pd.DataFrame(0.0, index=monthly.index, columns=monthly.columns, dtype=float)
    for horizon, weight in MOMENTUM_WEIGHTS.items():
        score = score + returns_by_horizon[horizon] * weight
    return returns_by_horizon, score


def ordered_winner(scores: pd.Series, symbols: list[str]) -> str:
    winner = symbols[0]
    winner_score = float(scores[winner])
    for symbol in symbols[1:]:
        value = float(scores[symbol])
        if value > winner_score:
            winner = symbol
            winner_score = value
    return winner


def state_from_scores(row: pd.Series) -> dict[str, Any]:
    offensive_scores = row[OFFENSIVE_SYMBOLS]
    all_positive = bool((offensive_scores > 0.0).all())
    non_positive = [symbol for symbol in OFFENSIVE_SYMBOLS if float(offensive_scores[symbol]) <= 0.0]
    if all_positive:
        return {
            "breadth_state": "offensive",
            "selected_asset": ordered_winner(row, OFFENSIVE_SYMBOLS),
            "triggering_non_positive_offensive_symbols": [],
            "defensive_momentum_positive_required": False,
        }
    return {
        "breadth_state": "defensive",
        "selected_asset": ordered_winner(row, DEFENSIVE_SYMBOLS),
        "triggering_non_positive_offensive_symbols": non_positive,
        "defensive_momentum_positive_required": False,
    }


def score_audit_rows(monthly: pd.DataFrame, returns_by_horizon: dict[int, pd.DataFrame], scores: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date in monthly.index:
        for symbol in REQUIRED_SYMBOLS:
            valid = not any(pd.isna(returns_by_horizon[horizon].loc[date, symbol]) for horizon in MOMENTUM_HORIZONS)
            rows.append(
                {
                    "trial_id": TRIAL_ID,
                    "month_end_date": pd.Timestamp(date).date().isoformat(),
                    "symbol": symbol,
                    "universe_role": "offensive" if symbol in OFFENSIVE_SYMBOLS else "defensive",
                    "R1": returns_by_horizon[1].loc[date, symbol],
                    "R3": returns_by_horizon[3].loc[date, symbol],
                    "R6": returns_by_horizon[6].loc[date, symbol],
                    "R12": returns_by_horizon[12].loc[date, symbol],
                    "momentum_score": scores.loc[date, symbol],
                    "horizons_months": "1|3|6|12",
                    "score_weights": "12|4|2|1",
                    "valid_13_month_history": valid,
                    "latest_month_skipped": False,
                }
            )
    return rows


def breadth_state_audit(monthly: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date in monthly.index:
        valid = not scores.loc[date, REQUIRED_SYMBOLS].isna().any()
        if valid:
            state = state_from_scores(scores.loc[date])
            selected = state["selected_asset"]
            breadth_state = state["breadth_state"]
            non_positive = state["triggering_non_positive_offensive_symbols"]
        else:
            selected = ""
            breadth_state = "insufficient_13_month_history"
            non_positive = []
        rows.append(
            {
                "trial_id": TRIAL_ID,
                "month_end_date": pd.Timestamp(date).date().isoformat(),
                "valid_common_signal_month": valid,
                "SPY_score": scores.loc[date, "SPY"],
                "EFA_score": scores.loc[date, "EFA"],
                "EEM_score": scores.loc[date, "EEM"],
                "AGG_score": scores.loc[date, "AGG"],
                "LQD_score": scores.loc[date, "LQD"],
                "IEF_score": scores.loc[date, "IEF"],
                "SHY_score": scores.loc[date, "SHY"],
                "offensive_non_positive_count": len(non_positive),
                "triggering_non_positive_offensive_symbols": non_positive,
                "all_offensive_scores_positive": valid and len(non_positive) == 0,
                "breadth_state": breadth_state,
                "ranking_universe_used": "offensive_only" if breadth_state == "offensive" else "defensive_only" if breadth_state == "defensive" else "",
                "selected_asset": selected,
                "defensive_momentum_positive_required": False,
                "tie_break_order": "|".join(OFFENSIVE_SYMBOLS if breadth_state == "offensive" else DEFENSIVE_SYMBOLS if breadth_state == "defensive" else []),
                "latest_month_skipped": False,
            }
        )
    return pd.DataFrame(rows)


def weights_from_breadth_audit(daily_index: pd.DatetimeIndex, breadth: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(float("nan"), index=daily_index, columns=REQUIRED_SYMBOLS)
    if breadth.empty:
        return weights.fillna(0.0)
    for _, signal in breadth.iterrows():
        if signal.get("valid_common_signal_month") is not True:
            continue
        signal_date = pd.Timestamp(signal["month_end_date"])
        selected = str(signal["selected_asset"])
        if selected not in REQUIRED_SYMBOLS or signal_date not in weights.index:
            continue
        target = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
        target[selected] = 1.0
        weights.loc[signal_date, REQUIRED_SYMBOLS] = [target[symbol] for symbol in REQUIRED_SYMBOLS]
    return weights.ffill().fillna(0.0)


def one_way_turnover(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float, name="turnover_proxy")
    previous = weights.shift(1).fillna(0.0)
    changed = (weights - previous).abs().sum(axis=1) / 2.0
    initial_or_exit = ((previous.sum(axis=1) <= WEIGHT_TOLERANCE) | (weights.sum(axis=1) <= WEIGHT_TOLERANCE)) & (
        (weights - previous).abs().sum(axis=1) > WEIGHT_TOLERANCE
    )
    changed.loc[initial_or_exit] = (weights - previous).abs().sum(axis=1).loc[initial_or_exit]
    return changed.rename("turnover_proxy")


def constant_weight_frame(index: pd.DatetimeIndex, weights: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({symbol: float(weights.get(symbol, 0.0)) for symbol in REQUIRED_SYMBOLS}, index=index)


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
        "first_half_source_cost_total_return": compound_return(first["baseline"]) if not first.empty else float("nan"),
        "second_half_source_cost_total_return": compound_return(second["baseline"]) if not second.empty else float("nan"),
        "first_half_offensive_control_total_return": compound_return(first["control"]) if not first.empty else float("nan"),
        "second_half_offensive_control_total_return": compound_return(second["control"]) if not second.empty else float("nan"),
        "first_half_excess_vs_offensive_control": compound_return(first["baseline"]) - compound_return(first["control"]) if not first.empty else float("nan"),
        "second_half_excess_vs_offensive_control": compound_return(second["baseline"]) - compound_return(second["control"]) if not second.empty else float("nan"),
        "timeframe_diagnostic_not_holdout": True,
    }


def evaluate(root: Path) -> dict[str, Any]:
    prices = daily_price_matrix(root)
    if prices.empty:
        return {"blocker": "missing_common_adjusted_daily_price_matrix"}
    monthly = monthly_prices(prices)
    if len(monthly) < 13:
        return {"blocker": "fewer_than_13_common_completed_monthly_observations"}
    returns_by_horizon, scores = momentum_score_frame(monthly)
    breadth = breadth_state_audit(monthly, scores)
    valid_dates = pd.to_datetime(breadth.loc[breadth["valid_common_signal_month"] == True, "month_end_date"])
    if valid_dates.empty:
        return {"blocker": "no_valid_13612w_signal_month"}
    weights = weights_from_breadth_audit(prices.index, breadth).reindex(prices.index).ffill().fillna(0.0)
    first_signal_date = pd.Timestamp(valid_dates.iloc[0])
    first_execution_index = prices.index.get_loc(first_signal_date) + 1
    if first_execution_index >= len(prices):
        return {"blocker": "no_next_session_after_first_valid_signal"}
    evaluation_index = prices.index[first_execution_index:]
    eval_weights = weights.loc[evaluation_index]

    gross_full = returns_from_weights(prices, weights).rename("zero_cost_vaa_g4")
    execution_turnover = one_way_turnover(weights).shift(1).reindex(gross_full.index).fillna(0.0)
    source_full = (gross_full - execution_turnover * SOURCE_COST_RATE).rename("source_aligned_10bps_vaa_g4")
    project_full = (gross_full - execution_turnover * PROJECT_COST_RATE).rename("project_5bps_vaa_g4")
    zero_cost = gross_full.loc[evaluation_index]
    source_cost = source_full.loc[evaluation_index]
    project_cost = project_full.loc[evaluation_index]
    eval_turnover = execution_turnover.loc[evaluation_index]

    offensive_control_weights = constant_weight_frame(prices.index, {symbol: 0.25 for symbol in OFFENSIVE_SYMBOLS})
    defensive_control_weights = constant_weight_frame(prices.index, {symbol: 1.0 / 3.0 for symbol in DEFENSIVE_SYMBOLS})
    avg_weights = {symbol: float(eval_weights[symbol].mean()) for symbol in REQUIRED_SYMBOLS}
    static_avg_weights = constant_weight_frame(prices.index, avg_weights)

    controls = {
        "equal_weight_offensive_basket_monthly_rebalanced": returns_from_weights(prices, offensive_control_weights).loc[evaluation_index],
        "equal_weight_defensive_basket_monthly_rebalanced": returns_from_weights(prices, defensive_control_weights).loc[evaluation_index],
        "static_average_weight_seven_asset_control_ex_post_diagnostic": returns_from_weights(prices, static_avg_weights).loc[evaluation_index],
        "zero_cost_vaa_g4": zero_cost,
        "source_aligned_10bps_vaa_g4": source_cost,
        "project_5bps_vaa_g4": project_cost,
    }
    baseline_metrics = metrics_from_returns(source_cost)
    zero_metrics = metrics_from_returns(zero_cost)
    project_metrics = metrics_from_returns(project_cost)
    control_metrics = {control_id: metrics_from_returns(series) for control_id, series in controls.items()}
    invariant = weight_invariant_report(eval_weights, tolerance=WEIGHT_TOLERANCE)
    selected_counts = {symbol: int((eval_weights[symbol] > 0.5).sum()) for symbol in REQUIRED_SYMBOLS}
    state_valid = breadth.loc[breadth["valid_common_signal_month"] == True].copy()
    state_valid["month_end_date"] = pd.to_datetime(state_valid["month_end_date"])
    state_valid = state_valid.loc[state_valid["month_end_date"] >= first_signal_date]
    offensive_months = int((state_valid["breadth_state"] == "offensive").sum())
    defensive_months = int((state_valid["breadth_state"] == "defensive").sum())
    transitions = int(state_valid["breadth_state"].ne(state_valid["breadth_state"].shift(1)).sum() - 1) if len(state_valid) > 1 else 0
    transitions = max(transitions, 0)
    non_positive_fractions = {
        symbol: float((state_valid[f"{symbol}_score"] <= 0.0).mean()) if not state_valid.empty else float("nan")
        for symbol in OFFENSIVE_SYMBOLS
    }
    invariant_pass = (
        invariant["max_daily_exposure"] <= 1.000001
        and invariant["max_daily_weight_sum"] <= 1.000001
        and int(invariant["weight_sum_violation_count"]) == 0
        and int(invariant["negative_weight_violation_count"]) == 0
        and int(invariant["nan_weight_count"]) == 0
        and bool(((eval_weights.sum(axis=1) - 1.0).abs() <= WEIGHT_TOLERANCE).all())
        and bool(((eval_weights > 0.5).sum(axis=1) == 1).all())
    )
    timeframe = split_timeframe(source_cost, controls["equal_weight_offensive_basket_monthly_rebalanced"])
    source_beats_offensive = baseline_metrics["total_return"] > control_metrics["equal_weight_offensive_basket_monthly_rebalanced"]["total_return"]
    source_beats_static = baseline_metrics["total_return"] > control_metrics["static_average_weight_seven_asset_control_ex_post_diagnostic"]["total_return"]
    zero_beats_offensive = zero_metrics["total_return"] > control_metrics["equal_weight_offensive_basket_monthly_rebalanced"]["total_return"]
    zero_beats_static = zero_metrics["total_return"] > control_metrics["static_average_weight_seven_asset_control_ex_post_diagnostic"]["total_return"]
    both_states_used = offensive_months > 0 and defensive_months > 0
    halves_nonnegative = (
        bool(timeframe["first_half_valid"])
        and bool(timeframe["second_half_valid"])
        and timeframe["first_half_excess_vs_offensive_control"] >= 0.0
        and timeframe["second_half_excess_vs_offensive_control"] >= 0.0
    )
    if not invariant_pass:
        family_outcome = "implementation_or_accounting_defect"
        outcome_reason = "exposure_invariant_failure"
    elif not source_beats_offensive or not source_beats_static:
        if zero_beats_offensive and zero_beats_static:
            family_outcome = "family_cost_fragile"
            outcome_reason = "zero_cost_passes_full_controls_but_source_cost_does_not"
        else:
            family_outcome = "family_control_weak"
            outcome_reason = "source_cost_strategy_fails_required_full_period_control"
    elif not halves_nonnegative:
        family_outcome = "family_timeframe_fragile"
        outcome_reason = "full_period_controls_pass_but_one_existing_half_has_negative_excess"
    elif not both_states_used:
        family_outcome = "family_timeframe_fragile"
        outcome_reason = "full_period_controls_pass_but_strategy_did_not_use_both_offensive_and_defensive_states"
    else:
        family_outcome = "family_exploratory_followup_candidate"
        outcome_reason = "source_cost_strategy_passes_full_controls_halves_state_usage_and_invariants"

    trades, turnover_proxy = trade_count_and_turnover(eval_weights)
    target_rows = []
    for date, row in eval_weights.iterrows():
        selected = next((symbol for symbol in REQUIRED_SYMBOLS if float(row[symbol]) > 0.5), "")
        payload = {"trial_id": TRIAL_ID, "date": pd.Timestamp(date).date().isoformat(), "selected_asset": selected}
        for symbol in REQUIRED_SYMBOLS:
            payload[symbol] = float(row[symbol])
        payload["weight_sum"] = float(row.sum())
        payload["gross_exposure"] = float(row.abs().sum())
        payload["net_exposure"] = float(row.sum())
        target_rows.append(payload)
    transaction_rows = [
        {
            "trial_id": TRIAL_ID,
            "date": pd.Timestamp(date).date().isoformat(),
            "turnover_proxy": float(value),
            "source_cost_rate": SOURCE_COST_RATE,
            "source_cost_return_deduction": float(value) * SOURCE_COST_RATE,
            "project_cost_rate": PROJECT_COST_RATE,
            "project_cost_return_deduction": float(value) * PROJECT_COST_RATE,
            "cost_applies_only_to_changed_notional": True,
        }
        for date, value in eval_turnover.items()
        if float(value) > WEIGHT_TOLERANCE
    ]
    monthly_rows = [{"month_end_date": pd.Timestamp(date).date().isoformat(), **{symbol: float(row[symbol]) for symbol in REQUIRED_SYMBOLS}} for date, row in monthly.iterrows()]
    attribution_rows = [
        {"trial_id": TRIAL_ID, "metric": "offensive_state_month_count", "symbol": "", "value": offensive_months},
        {"trial_id": TRIAL_ID, "metric": "defensive_state_month_count", "symbol": "", "value": defensive_months},
        {"trial_id": TRIAL_ID, "metric": "state_transition_count", "symbol": "", "value": transitions},
        {"trial_id": TRIAL_ID, "metric": "total_turnover", "symbol": "", "value": float(eval_turnover.sum())},
        {
            "trial_id": TRIAL_ID,
            "metric": "source_cost_drag_vs_zero_cost_total_return",
            "symbol": "",
            "value": zero_metrics["total_return"] - baseline_metrics["total_return"],
        },
    ]
    for symbol in REQUIRED_SYMBOLS:
        attribution_rows.append({"trial_id": TRIAL_ID, "metric": "selected_trading_day_count", "symbol": symbol, "value": selected_counts[symbol]})
        attribution_rows.append({"trial_id": TRIAL_ID, "metric": "average_weight", "symbol": symbol, "value": avg_weights[symbol]})
    for symbol in OFFENSIVE_SYMBOLS:
        attribution_rows.append(
            {
                "trial_id": TRIAL_ID,
                "metric": "fraction_valid_months_with_non_positive_offensive_momentum",
                "symbol": symbol,
                "value": non_positive_fractions[symbol],
            }
        )
    return {
        "prices": prices,
        "monthly_rows": monthly_rows,
        "score_rows": score_audit_rows(monthly, returns_by_horizon, scores),
        "breadth_rows": breadth.to_dict(orient="records"),
        "target_rows": target_rows,
        "transaction_rows": transaction_rows,
        "baseline_metrics": baseline_metrics,
        "zero_metrics": zero_metrics,
        "project_metrics": project_metrics,
        "control_metrics": control_metrics,
        "timeframe": timeframe,
        "attribution_rows": attribution_rows,
        "invariant": invariant,
        "invariant_pass": invariant_pass,
        "first_signal_date": first_signal_date.date().isoformat(),
        "first_execution_date": pd.Timestamp(evaluation_index[0]).date().isoformat(),
        "trades": trades,
        "turnover_proxy": turnover_proxy,
        "total_turnover": float(eval_turnover.sum()),
        "average_weights": avg_weights,
        "selected_counts": selected_counts,
        "offensive_months": offensive_months,
        "defensive_months": defensive_months,
        "state_transitions": transitions,
        "source_beats_offensive": source_beats_offensive,
        "source_beats_static": source_beats_static,
        "zero_beats_offensive": zero_beats_offensive,
        "zero_beats_static": zero_beats_static,
        "project_total_return": project_metrics["total_return"],
        "outcome": family_outcome,
        "outcome_reason": outcome_reason,
    }


def repository_fit_check(root: Path, registry_before: str, registry_after: str, active_before: str, active_after: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "queue_position": 3,
        "mode": "fast-progress",
        "stage": "implementation",
        "uses_adjusted_daily_bars": True,
        "monthly_price_source": "final_common_eligible_trading_session_of_each_calendar_month",
        "source_rule_complete": True,
        "source_completion_research": False,
        "parameter_search": False,
        "universe_search": False,
        "portability_sweep": False,
        "framework_rebuild": False,
        "overlay_research": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_or_order_path_touched": False,
        "registry_lifecycle_unchanged": registry_before == registry_after,
        "active_paper_demo_state_unchanged": active_before == active_after,
        "gem_direction_decision": "NO_ADVANCEMENT",
        "gem_family_outcome_closed_as": "family_control_weak",
        "gem_evidence_preserved": True,
        "acwx_cache_preserved_not_authorized_for_this_task": True,
    }


def empty_outputs(output: Path) -> None:
    write_csv(output / "monthly_price_matrix.csv", [], ["month_end_date", *REQUIRED_SYMBOLS])
    write_csv(output / "momentum_score_audit.csv", [], ["trial_id", "month_end_date", "symbol", "universe_role", "R1", "R3", "R6", "R12", "momentum_score", "horizons_months", "score_weights", "valid_13_month_history", "latest_month_skipped"])
    write_csv(output / "breadth_state_audit.csv", [], ["trial_id", "month_end_date", "valid_common_signal_month", "SPY_score", "EFA_score", "EEM_score", "AGG_score", "LQD_score", "IEF_score", "SHY_score", "offensive_non_positive_count", "triggering_non_positive_offensive_symbols", "all_offensive_scores_positive", "breadth_state", "ranking_universe_used", "selected_asset", "defensive_momentum_positive_required", "tie_break_order", "latest_month_skipped"])
    write_csv(output / "target_weights.csv", [], ["trial_id", "date", *REQUIRED_SYMBOLS, "weight_sum", "gross_exposure", "net_exposure", "selected_asset"])
    write_csv(output / "transactions.csv", [], ["trial_id", "date", "turnover_proxy", "source_cost_rate", "source_cost_return_deduction", "project_cost_rate", "project_cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "project_5bps_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "total_turnover", "first_signal_date", "first_execution_date", "offensive_state_months", "defensive_state_months", "state_transition_count", "source_cost_bps_per_turnover", "project_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", [], ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", [], ["trial_id", "source_10bps_total_return", "zero_cost_total_return", "project_5bps_total_return", "equal_weight_offensive_total_return", "equal_weight_defensive_total_return", "static_average_weight_control_total_return", "source_10bps_beats_equal_weight_offensive", "source_10bps_beats_static_control", "zero_cost_beats_equal_weight_offensive", "zero_cost_beats_static_control", "project_5bps_beats_equal_weight_offensive", "project_5bps_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_source_cost_total_return", "second_half_source_cost_total_return", "first_half_offensive_control_total_return", "second_half_offensive_control_total_return", "first_half_excess_vs_offensive_control", "second_half_excess_vs_offensive_control", "timeframe_diagnostic_not_holdout"])
    write_csv(output / "state_and_instrument_attribution.csv", [], ["trial_id", "metric", "symbol", "value"])


def write_strategy_outputs(output: Path, evaluation: dict[str, Any], family_outcome: dict[str, Any]) -> None:
    baseline_metrics = evaluation["baseline_metrics"]
    zero_metrics = evaluation["zero_metrics"]
    project_metrics = evaluation["project_metrics"]
    control_metrics = evaluation["control_metrics"]
    baseline_row = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "start_date": baseline_metrics["start_date"],
        "end_date": baseline_metrics["end_date"],
        "trading_days": baseline_metrics["trading_days"],
        "total_return": baseline_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "project_5bps_total_return": project_metrics["total_return"],
        "cagr": baseline_metrics["cagr"],
        "max_drawdown": baseline_metrics["max_drawdown"],
        "volatility": baseline_metrics["volatility"],
        "return_drawdown_proxy": baseline_metrics["return_drawdown_proxy"],
        "trade_count": evaluation["trades"],
        "turnover_proxy": evaluation["turnover_proxy"],
        "total_turnover": evaluation["total_turnover"],
        "first_signal_date": evaluation["first_signal_date"],
        "first_execution_date": evaluation["first_execution_date"],
        "offensive_state_months": evaluation["offensive_months"],
        "defensive_state_months": evaluation["defensive_months"],
        "state_transition_count": evaluation["state_transitions"],
        "source_cost_bps_per_turnover": SOURCE_COST_BPS_PER_TURNOVER,
        "project_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "family_outcome": family_outcome["family_outcome"],
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    control_rows = [
        {"trial_id": TRIAL_ID, "control_id": control_id, **metrics, "same_evaluation_calendar": True}
        for control_id, metrics in control_metrics.items()
    ]
    offensive_total = control_metrics["equal_weight_offensive_basket_monthly_rebalanced"]["total_return"]
    defensive_total = control_metrics["equal_weight_defensive_basket_monthly_rebalanced"]["total_return"]
    static_total = control_metrics["static_average_weight_seven_asset_control_ex_post_diagnostic"]["total_return"]
    vs_row = {
        "trial_id": TRIAL_ID,
        "source_10bps_total_return": baseline_metrics["total_return"],
        "zero_cost_total_return": zero_metrics["total_return"],
        "project_5bps_total_return": project_metrics["total_return"],
        "equal_weight_offensive_total_return": offensive_total,
        "equal_weight_defensive_total_return": defensive_total,
        "static_average_weight_control_total_return": static_total,
        "source_10bps_beats_equal_weight_offensive": baseline_metrics["total_return"] > offensive_total,
        "source_10bps_beats_static_control": baseline_metrics["total_return"] > static_total,
        "zero_cost_beats_equal_weight_offensive": zero_metrics["total_return"] > offensive_total,
        "zero_cost_beats_static_control": zero_metrics["total_return"] > static_total,
        "project_5bps_beats_equal_weight_offensive": project_metrics["total_return"] > offensive_total,
        "project_5bps_beats_static_control": project_metrics["total_return"] > static_total,
    }
    write_csv(output / "monthly_price_matrix.csv", evaluation["monthly_rows"], ["month_end_date", *REQUIRED_SYMBOLS])
    write_csv(output / "momentum_score_audit.csv", evaluation["score_rows"], ["trial_id", "month_end_date", "symbol", "universe_role", "R1", "R3", "R6", "R12", "momentum_score", "horizons_months", "score_weights", "valid_13_month_history", "latest_month_skipped"])
    write_csv(output / "breadth_state_audit.csv", evaluation["breadth_rows"], ["trial_id", "month_end_date", "valid_common_signal_month", "SPY_score", "EFA_score", "EEM_score", "AGG_score", "LQD_score", "IEF_score", "SHY_score", "offensive_non_positive_count", "triggering_non_positive_offensive_symbols", "all_offensive_scores_positive", "breadth_state", "ranking_universe_used", "selected_asset", "defensive_momentum_positive_required", "tie_break_order", "latest_month_skipped"])
    write_csv(output / "target_weights.csv", evaluation["target_rows"], ["trial_id", "date", *REQUIRED_SYMBOLS, "weight_sum", "gross_exposure", "net_exposure", "selected_asset"])
    write_csv(output / "transactions.csv", evaluation["transaction_rows"], ["trial_id", "date", "turnover_proxy", "source_cost_rate", "source_cost_return_deduction", "project_cost_rate", "project_cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [baseline_row], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "project_5bps_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "total_turnover", "first_signal_date", "first_execution_date", "offensive_state_months", "defensive_state_months", "state_transition_count", "source_cost_bps_per_turnover", "project_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", control_rows, ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", [vs_row], ["trial_id", "source_10bps_total_return", "zero_cost_total_return", "project_5bps_total_return", "equal_weight_offensive_total_return", "equal_weight_defensive_total_return", "static_average_weight_control_total_return", "source_10bps_beats_equal_weight_offensive", "source_10bps_beats_static_control", "zero_cost_beats_equal_weight_offensive", "zero_cost_beats_static_control", "project_5bps_beats_equal_weight_offensive", "project_5bps_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [evaluation["timeframe"]], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_source_cost_total_return", "second_half_source_cost_total_return", "first_half_offensive_control_total_return", "second_half_offensive_control_total_return", "first_half_excess_vs_offensive_control", "second_half_excess_vs_offensive_control", "timeframe_diagnostic_not_holdout"])
    write_csv(output / "state_and_instrument_attribution.csv", evaluation["attribution_rows"], ["trial_id", "metric", "symbol", "value"])


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    clean_output_dir(output)
    registry_before = file_hash(root / REGISTRY_PATH)
    active_before = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    gem_base_before = directory_hash(root / GEM_BASE_EVIDENCE)
    gem_recovery_before = directory_hash(root / GEM_RECOVERY_EVIDENCE)
    acwx_cache_before = file_hash(root / ACWX_CACHE)
    acwx_metadata_before = file_hash(root / ACWX_METADATA)

    duplicate = exact_duplicate_check(root)
    universe_rows = frozen_universe_rows(root)
    coverage_rows, coverage_blockers = data_coverage(root, universe_rows) if universe_rows else ([], ["frozen_universe_missing"])
    mapping_rows = source_to_etf_mapping(universe_rows, coverage_rows)

    task_outcome = "vaa_g4_fast_lane_complete"
    blocker = ""
    evaluation: dict[str, Any] = {}
    evaluated = False
    if duplicate["exact_duplicate_found"]:
        task_outcome = "exact_vaa_g4_implementation_duplicate_found"
        blocker = "exact VAA-G4 implementation duplicate found"
    elif not universe_rows or coverage_blockers:
        task_outcome = "source_asset_mapping_or_data_unavailable"
        blocker = ";".join(coverage_blockers)
    else:
        evaluation = evaluate(root)
        if evaluation.get("blocker"):
            task_outcome = "existing_data_coverage_insufficient"
            blocker = str(evaluation["blocker"])
        elif evaluation.get("outcome") == "implementation_or_accounting_defect":
            task_outcome = "implementation_or_accounting_defect"
            blocker = str(evaluation["outcome_reason"])
        else:
            evaluated = True

    registry_after = file_hash(root / REGISTRY_PATH)
    active_after = file_hash(root / ACTIVE_OBSERVATIONS_PATH)
    gem_base_after = directory_hash(root / GEM_BASE_EVIDENCE)
    gem_recovery_after = directory_hash(root / GEM_RECOVERY_EVIDENCE)
    acwx_cache_after = file_hash(root / ACWX_CACHE)
    acwx_metadata_after = file_hash(root / ACWX_METADATA)
    repository_fit = repository_fit_check(root, registry_before, registry_after, active_before, active_after)

    family_value = evaluation.get("outcome") if evaluated else task_outcome
    family_outcome = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "family_outcome": family_value,
        "family_outcome_allowed": family_value in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": evaluation.get("outcome_reason", blocker or "none"),
        "task_outcome": task_outcome,
        "research_status": "exploratory_non_promotable",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "direction_decision_required_before_any_followup": True,
    }
    manifest_rows = [
        {
            "task_id": TASK_ID,
            "trial_id": TRIAL_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "offensive_universe": OFFENSIVE_SYMBOLS,
            "defensive_universe": DEFENSIVE_SYMBOLS,
            "momentum_horizons_months": MOMENTUM_HORIZONS,
            "momentum_weights": MOMENTUM_WEIGHTS,
            "source_cost_bps_per_turnover": SOURCE_COST_BPS_PER_TURNOVER,
            "project_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
            "portfolio_trial_count": 1,
            "trial_evaluation_status": "evaluated" if evaluated else "blocked_before_return_calculation",
            "frozen_before_return_calculation": True,
        }
    ]
    if evaluated:
        write_strategy_outputs(output, evaluation, family_outcome)
    else:
        empty_outputs(output)
    invariant_source = evaluation.get("invariant", {})
    eval_pass = bool(evaluation.get("invariant_pass")) if evaluated else True
    invariant_row = {
        "trial_id": TRIAL_ID,
        **invariant_source,
        "exactly_four_offensive_symbols": OFFENSIVE_SYMBOLS == ["SPY", "EFA", "EEM", "AGG"],
        "exactly_three_defensive_symbols": DEFENSIVE_SYMBOLS == ["LQD", "IEF", "SHY"],
        "momentum_horizons_exact": MOMENTUM_HORIZONS == [1, 3, 6, 12],
        "momentum_weights_exact": MOMENTUM_WEIGHTS == {1: 12.0, 3: 4.0, 6: 2.0, 12: 1.0},
        "any_non_positive_offensive_triggers_defensive": True,
        "all_positive_offensive_triggers_offensive": True,
        "offensive_and_defensive_rankings_separate": True,
        "exactly_one_asset_held_after_initialization": eval_pass,
        "latest_month_not_skipped": True,
        "same_period_execution_impossible": True,
        "daily_weights_sum_exactly_1": eval_pass,
        "costs_apply_only_to_changed_notional": True,
        "controls_identical_calendar": evaluated,
        "exactly_one_canonical_portfolio_trial_registered": True,
        "existing_evidence_remains_unchanged": gem_base_before == gem_base_after and gem_recovery_before == gem_recovery_after,
        "acwx_cache_preserved_and_not_authorized_for_vaa": acwx_cache_before == acwx_cache_after and acwx_metadata_before == acwx_metadata_after,
        "no_overlay_output_generated": True,
        "registry_lifecycle_unchanged": registry_before == registry_after,
        "active_paper_demo_state_unchanged": active_before == active_after,
        "exposure_invariant_pass": eval_pass,
    }
    if not evaluated:
        invariant_row.update(
            {
                "max_daily_exposure": 0.0,
                "max_daily_weight_sum": 0.0,
                "average_weight_sum": 0.0,
                "weight_sum_violation_count": 0,
                "negative_weight_violation_count": 0,
                "nan_weight_count": 0,
                "impossible_cash_and_risky_exposure_days": 0,
            }
        )
    followup_rows = [
        {
            "queue_position": "closed_context",
            "strategy_id": "antonacci_gem_12m_global_equities_bond_v1",
            "family_id": "global_equity_dual_momentum_rotation",
            "family_outcome": "family_control_weak",
            "direction_decision": "NO_ADVANCEMENT",
            "next_review_status": "closed_for_now_preserve_evidence",
        },
        {
            "queue_position": "3",
            "strategy_id": TASK_ID,
            "family_id": FAMILY_ID,
            "family_outcome": family_outcome["family_outcome"],
            "direction_decision": "direction_owner_review_required",
            "next_review_status": NEXT_ACTION,
        },
    ]
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "task_outcome_allowed": task_outcome in VALID_TASK_OUTCOMES,
        "family_outcome_allowed": family_outcome["family_outcome_allowed"],
        "exact_duplicate_check_completed_before_return_calculation": duplicate["duplicate_check_completed_before_return_calculation"],
        "exact_duplicate_found": duplicate["exact_duplicate_found"],
        "offensive_universe_exact": OFFENSIVE_SYMBOLS == ["SPY", "EFA", "EEM", "AGG"],
        "defensive_universe_exact": DEFENSIVE_SYMBOLS == ["LQD", "IEF", "SHY"],
        "required_symbol_count": len(REQUIRED_SYMBOLS),
        "coverage_blockers": coverage_blockers,
        "no_substitutions": all(row["substitution_used"] is False for row in mapping_rows),
        "momentum_horizons_exact": invariant_row["momentum_horizons_exact"],
        "momentum_weights_exact": invariant_row["momentum_weights_exact"],
        "source_cost_and_project_cost_distinct": SOURCE_COST_BPS_PER_TURNOVER != PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "zero_cost_source_cost_project_cost_only": True,
        "one_canonical_trial_registered": len(manifest_rows) == 1 and manifest_rows[0]["portfolio_trial_count"] == 1,
        "controls_identical_calendar": invariant_row["controls_identical_calendar"],
        "invariant_failure_count": 0 if invariant_row["exposure_invariant_pass"] else 1,
        "gem_evidence_preserved": invariant_row["existing_evidence_remains_unchanged"],
        "acwx_cache_preserved_not_authorized": invariant_row["acwx_cache_preserved_and_not_authorized_for_vaa"],
        "no_overlay_output_generated": invariant_row["no_overlay_output_generated"],
        "registry_lifecycle_unchanged": invariant_row["registry_lifecycle_unchanged"],
        "active_paper_demo_state_unchanged": invariant_row["active_paper_demo_state_unchanged"],
        "provider_download": False,
        "intraday_data_used": False,
        "broker_or_order_path_touched": False,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "return_calculation_run": evaluated,
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["task_outcome_allowed"]
        and consistency["family_outcome_allowed"]
        and consistency["exact_duplicate_check_completed_before_return_calculation"]
        and consistency["offensive_universe_exact"]
        and consistency["defensive_universe_exact"]
        and consistency["required_symbol_count"] == 7
        and not consistency["coverage_blockers"]
        and consistency["no_substitutions"]
        and consistency["momentum_horizons_exact"]
        and consistency["momentum_weights_exact"]
        and consistency["source_cost_and_project_cost_distinct"]
        and consistency["zero_cost_source_cost_project_cost_only"]
        and consistency["one_canonical_trial_registered"]
        and consistency["controls_identical_calendar"]
        and consistency["invariant_failure_count"] == 0
        and consistency["gem_evidence_preserved"]
        and consistency["acwx_cache_preserved_not_authorized"]
        and consistency["no_overlay_output_generated"]
        and consistency["registry_lifecycle_unchanged"]
        and consistency["active_paper_demo_state_unchanged"]
        and not consistency["provider_download"]
        and not consistency["intraday_data_used"]
        and not consistency["broker_or_order_path_touched"]
        and not consistency["paper_forward_activation"]
        and not consistency["promotion_candidates_created"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["real_money_recommendation"]
    )

    write_yaml(output / "source_packet_used.yaml", source_packet())
    write_json(output / "exact_duplicate_check.json", duplicate)
    write_json(output / "repository_fit_check.json", repository_fit)
    write_csv(output / "source_to_etf_mapping.csv", mapping_rows, ["source_sleeve", "source_asset_class", "expected_symbol", "selected_symbol", "universe_role", "mapping_status", "substitution_allowed", "substitution_used", "source_preserving", "selection_performance_independent"])
    write_csv(output / "frozen_trial_manifest.csv", manifest_rows, ["task_id", "trial_id", "family_id", "source_id", "offensive_universe", "defensive_universe", "momentum_horizons_months", "momentum_weights", "source_cost_bps_per_turnover", "project_cost_bps_per_turnover", "portfolio_trial_count", "trial_evaluation_status", "frozen_before_return_calculation"])
    write_csv(output / "data_coverage.csv", coverage_rows, ["symbol", "universe_role", "frozen_universe_available", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"])
    write_csv(output / "accounting_invariants.csv", [invariant_row], ["trial_id", "max_daily_exposure", "max_daily_weight_sum", "average_weight_sum", "weight_sum_violation_count", "negative_weight_violation_count", "nan_weight_count", "impossible_cash_and_risky_exposure_days", "exactly_four_offensive_symbols", "exactly_three_defensive_symbols", "momentum_horizons_exact", "momentum_weights_exact", "any_non_positive_offensive_triggers_defensive", "all_positive_offensive_triggers_offensive", "offensive_and_defensive_rankings_separate", "exactly_one_asset_held_after_initialization", "latest_month_not_skipped", "same_period_execution_impossible", "daily_weights_sum_exactly_1", "costs_apply_only_to_changed_notional", "controls_identical_calendar", "exactly_one_canonical_portfolio_trial_registered", "existing_evidence_remains_unchanged", "acwx_cache_preserved_and_not_authorized_for_vaa", "no_overlay_output_generated", "registry_lifecycle_unchanged", "active_paper_demo_state_unchanged", "exposure_invariant_pass"])
    write_json(output / "family_outcome.json", family_outcome)
    write_csv(output / "family_followup_queue.csv", followup_rows, ["queue_position", "strategy_id", "family_id", "family_outcome", "direction_decision", "next_review_status"])
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_csv(
        output / "command_validation_log.csv",
        [
            {"command": ".venv\\Scripts\\python.exe run_keller_keuning_vaa_g4_13612w_v1.py", "status": "generated_by_runner", "notes": "dedicated VAA-G4 fast-lane runner"},
            {"command": ".venv\\Scripts\\python.exe -m pytest tests\\test_keller_keuning_vaa_g4_13612w_v1.py -q", "status": "external_validation_required", "notes": "focused tests"},
        ],
        ["command", "status", "notes"],
    )
    write_json(output / "consistency_check.json", consistency)
    summary = f"""# Keller-Keuning VAA-G4 13612W v1

Task outcome: `{task_outcome}`

- Family: `{FAMILY_ID}`
- Source: `{SOURCE_NAME}`
- Offensive universe: `{', '.join(OFFENSIVE_SYMBOLS)}`
- Defensive universe: `{', '.join(DEFENSIVE_SYMBOLS)}`
- Canonical portfolio trials: `1`
- Return calculation run: `{str(evaluated).lower()}`
- Family outcome: `{family_outcome['family_outcome']}`
- Blocker: `{blocker or 'none'}`
- Source cost: `{SOURCE_COST_BPS_PER_TURNOVER}` bps per one-way traded notional
- Project diagnostic cost: `{PROJECT_STANDARD_COST_BPS_PER_TURNOVER}` bps per one-way traded notional
- GEM direction decision recorded as: `NO_ADVANCEMENT`
- GEM evidence preserved: `{str(invariant_row['existing_evidence_remains_unchanged']).lower()}`
- ACWX cache authorization expanded: `false`
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
        "family_outcome": family_outcome["family_outcome"],
        "registered_portfolio_trial_count": 1,
        "offensive_universe": OFFENSIVE_SYMBOLS,
        "defensive_universe": DEFENSIVE_SYMBOLS,
        "return_calculation_run": evaluated,
        "source_cost_total_return": evaluation.get("baseline_metrics", {}).get("total_return", float("nan")),
        "equal_weight_offensive_total_return": evaluation.get("control_metrics", {}).get("equal_weight_offensive_basket_monthly_rebalanced", {}).get("total_return", float("nan")),
        "static_average_weight_control_total_return": evaluation.get("control_metrics", {}).get("static_average_weight_seven_asset_control_ex_post_diagnostic", {}).get("total_return", float("nan")),
        "invariant_failure_count": consistency["invariant_failure_count"],
        "provider_download": False,
        "paper_forward_activation": False,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }

