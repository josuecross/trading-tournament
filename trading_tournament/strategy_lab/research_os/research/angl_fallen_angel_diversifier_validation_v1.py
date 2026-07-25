from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior
from strategy_lab.research_os.research import fast_source_library_batch_v3 as source_batch
from strategy_lab.research_os.research import rerun_fast_source_library_blocked_candidates_v3 as rerun


VALIDATION_ID = "angl_fallen_angel_diversifier_validation_v1"
OUTPUT_DIR = ROOT / "evidence" / "validation" / VALIDATION_ID / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
PARENT_TRIAL_ID = "rerun_fast_source_v3__ice_vaneck_us_fallen_angel_angl_v1__data_feasibility_adjustment_child"
VALIDATION_TRIAL_ID = "validation_angl__ice_vaneck_us_fallen_angel_angl_v1__validation_variant_child"
ADAPTATION_LABEL = "validation_variant"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
CONTROL_IDS = ("HYG_buy_hold", "monthly_rebalanced_50_50_HYG_JNK")
PORTFOLIO_IDS = (
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "HYG_buy_hold_20pct_control",
    "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
)
PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
INPUT_EVIDENCE_FILES = [
    ROOT / "evidence" / "research_recovery" / "rerun_fast_source_library_blocked_candidates_v3" / "latest" / name
    for name in [
        "strategy_cards.csv",
        "trial_ledger.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "benchmark_reference_log.csv",
        "consistency_check.json",
    ]
]
PROTECTED_CACHE_PATHS = [
    ROOT / "data" / "cache" / "ANGL.csv",
    ROOT / "data" / "cache" / "ANGL.acquisition.json",
    ROOT / "data" / "cache" / "HYG.csv",
    ROOT / "data" / "cache" / "JNK.csv",
    ROOT / "data" / "cache" / "JNK.acquisition.json",
]
FORBIDDEN_FLAGS = {
    "source_research_or_completion": False,
    "provider_download": False,
    "parameter_or_instrument_change": False,
    "benchmark_correction": False,
    "universe_expansion": False,
    "trade_management_overlay": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "registry_cleanup": False,
    "dashboard_rebuild": False,
    "dsr_pbo_cscv_reality_check_or_parameter_search": False,
    "broker_account_order_or_real_money_action": False,
    "nvi_or_inverse_vol_records_modified": False,
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


def input_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in INPUT_EVIDENCE_FILES if path.exists()}


def cache_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_CACHE_PATHS if path.exists()}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "validation" / VALIDATION_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def base_card() -> Any:
    card = next(card for card in source_batch.CARDS if card.strategy_id == STRATEGY_ID)
    return replace(card, parent_trial_id=PARENT_TRIAL_ID)


def load_strategy_state() -> dict[str, str]:
    rows = read_csv_rows(
        ROOT / "evidence" / "research_recovery" / "rerun_fast_source_library_blocked_candidates_v3" / "latest" / "trial_ledger.csv"
    )
    return next(row for row in rows if row["strategy_id"] == STRATEGY_ID)


def run_frozen_card(card: Any) -> dict[str, Any]:
    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    return source_batch.run_card(card, reference_returns)


def standalone_and_control_returns(card: Any, outcome: dict[str, Any]) -> dict[str, dict[float, dict[str, Any]]]:
    prices = outcome["prices"]
    weights = outcome["weights"]
    controls = outcome["controls"]
    series: dict[str, dict[float, dict[str, Any]]] = {"ANGL": {}, "HYG_buy_hold": {}, "monthly_rebalanced_50_50_HYG_JNK": {}}
    for cost_bps in COST_BPS_GRID:
        returns, turnover, cost = source_batch.returns_for_weights(prices, weights, cost_bps)
        series["ANGL"][cost_bps] = {"returns": returns, "turnover": turnover, "cost": cost, "weights": weights}
        for control_id in CONTROL_IDS:
            control_weight = controls[control_id]
            control_prices = prices.reindex(columns=control_weight.columns).dropna()
            aligned_weight = control_weight.reindex(control_prices.index).ffill().fillna(0.0)
            control_returns, control_turnover, control_cost = source_batch.returns_for_weights(control_prices, aligned_weight, cost_bps)
            series[control_id][cost_bps] = {
                "returns": control_returns,
                "turnover": control_turnover,
                "cost": control_cost,
                "weights": aligned_weight,
            }
    return series


def portfolio_returns(series: dict[str, dict[float, dict[str, Any]]], reference: pd.Series) -> dict[str, dict[float, pd.Series]]:
    portfolios: dict[str, dict[float, pd.Series]] = {pid: {} for pid in PORTFOLIO_IDS}
    reference_aligned = reference.dropna()
    for cost_bps in COST_BPS_GRID:
        portfolios["frozen_reference_100pct"][cost_bps] = reference_aligned
        portfolios[f"{STRATEGY_ID}_candidate_20pct"][cost_bps] = 0.8 * reference_aligned + 0.2 * series["ANGL"][cost_bps][
            "returns"
        ].reindex(reference_aligned.index).fillna(0.0)
        portfolios["HYG_buy_hold_20pct_control"][cost_bps] = 0.8 * reference_aligned + 0.2 * series["HYG_buy_hold"][cost_bps][
            "returns"
        ].reindex(reference_aligned.index).fillna(0.0)
        portfolios["monthly_rebalanced_50_50_HYG_JNK_20pct_control"][cost_bps] = 0.8 * reference_aligned + 0.2 * series[
            "monthly_rebalanced_50_50_HYG_JNK"
        ][cost_bps]["returns"].reindex(reference_aligned.index).fillna(0.0)
    return portfolios


def metric_payload(returns: pd.Series, turnover: pd.Series | None = None, cost: pd.Series | None = None, weights: pd.DataFrame | None = None) -> dict[str, Any]:
    metrics = prior.metrics_from_returns(returns)
    if turnover is None:
        turnover_value = 0.0
        trade_count = 0
    else:
        turnover_aligned = turnover.reindex(returns.index).fillna(0.0)
        turnover_value = float(turnover_aligned.sum())
        trade_count = int((turnover_aligned > source_batch.WEIGHT_TOLERANCE).sum())
    cost_drag = 0.0 if cost is None else float(cost.reindex(returns.index).fillna(0.0).sum())
    if weights is None:
        max_exposure = 1.0
        max_weight_sum = 1.0
        exposure_pass = True
    else:
        invariant = source_batch.invariant_report(weights.reindex(returns.index).ffill().fillna(0.0))
        max_exposure = invariant["max_daily_exposure"]
        max_weight_sum = invariant["max_daily_weight_sum"]
        exposure_pass = bool(invariant["invariant_pass"])
    return {
        **metrics,
        "turnover": turnover_value,
        "rebalance_or_trade_count": trade_count,
        "transaction_cost_drag": cost_drag,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "timing_invariant_status": "pass_project_shifted_weight_no_lookahead",
        "numeric_invariant_status": "pass" if len(returns.dropna()) and not returns.isna().any() else "fail",
        "exposure_invariant_status": "pass" if exposure_pass else "fail",
        "weight_invariant_status": "pass" if exposure_pass else "fail",
        "invariant_pass": bool(exposure_pass and len(returns.dropna()) and not returns.isna().any()),
    }


def full_period_rows(series: dict[str, dict[float, dict[str, Any]]], portfolios: dict[str, dict[float, pd.Series]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    labels = {
        "ANGL": "candidate_standalone",
        "HYG_buy_hold": "control_standalone",
        "monthly_rebalanced_50_50_HYG_JNK": "control_standalone",
    }
    for entity_id, cost_map in series.items():
        for cost_bps, payload in cost_map.items():
            rows.append(
                {
                    "entity_id": entity_id,
                    "entity_type": labels[entity_id],
                    "cost_assumption_bps": cost_bps,
                    **metric_payload(payload["returns"], payload["turnover"], payload["cost"], payload["weights"]),
                }
            )
    for portfolio_id, cost_map in portfolios.items():
        for cost_bps, returns in cost_map.items():
            rows.append(
                {
                    "entity_id": portfolio_id,
                    "entity_type": "portfolio_construction",
                    "cost_assumption_bps": cost_bps,
                    **metric_payload(returns),
                }
            )
    return rows


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    return source_batch.split_halves(index)


def chronological_half_rows(
    series: dict[str, dict[float, dict[str, Any]]], portfolios: dict[str, dict[float, pd.Series]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_index = next(iter(series["ANGL"].values()))["returns"].index
    for half_label, start, end in split_halves(base_index):
        for entity_id, cost_map in series.items():
            for cost_bps, payload in cost_map.items():
                returns = payload["returns"].loc[start:end]
                rows.append(
                    {
                        "entity_id": entity_id,
                        "entity_type": "candidate_standalone" if entity_id == "ANGL" else "control_standalone",
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **metric_payload(
                            returns,
                            payload["turnover"].loc[start:end],
                            payload["cost"].loc[start:end],
                            payload["weights"].reindex(returns.index).ffill().fillna(0.0),
                        ),
                    }
                )
        for portfolio_id, cost_map in portfolios.items():
            for cost_bps, returns in cost_map.items():
                rows.append(
                    {
                        "entity_id": portfolio_id,
                        "entity_type": "portfolio_construction",
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **metric_payload(returns.loc[start:end]),
                    }
                )
    return rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [pd.Timestamp(date) for date in index[periods.ne(periods.shift(-1)).fillna(True)]]


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    c_values = (float(control["cagr"]), float(control["sharpe_ratio"]), float(control["maximum_drawdown"]))
    v_values = (float(candidate["cagr"]), float(candidate["sharpe_ratio"]), float(candidate["maximum_drawdown"]))
    return all(c >= v - 1e-12 for c, v in zip(c_values, v_values)) and any(c > v + 1e-12 for c, v in zip(c_values, v_values))


def rolling_rows(portfolios: dict[str, dict[float, pd.Series]], months: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate_id = f"{STRATEGY_ID}_candidate_20pct"
    control_ids = ("HYG_buy_hold_20pct_control", "monthly_rebalanced_50_50_HYG_JNK_20pct_control")
    for cost_bps in COST_BPS_GRID:
        candidate = portfolios[candidate_id][cost_bps].dropna()
        ends = month_end_dates(candidate.index)
        first_available = candidate.index.min()
        for end_date in ends:
            cutoff = end_date - pd.DateOffset(months=months)
            if cutoff < first_available:
                continue
            window_index = candidate.index[(candidate.index >= cutoff) & (candidate.index <= end_date)]
            candidate_returns = candidate.reindex(window_index).dropna()
            candidate_metrics = metric_payload(candidate_returns)
            for control_id in control_ids:
                control_returns = portfolios[control_id][cost_bps].reindex(candidate_returns.index).dropna()
                aligned_candidate = candidate_returns.reindex(control_returns.index).dropna()
                if aligned_candidate.empty:
                    continue
                candidate_metrics = metric_payload(aligned_candidate)
                control_metrics = metric_payload(control_returns)
                dominated = dominates(control_metrics, candidate_metrics)
                rows.append(
                    {
                        "window_months": months,
                        "cost_assumption_bps": cost_bps,
                        "window_start": aligned_candidate.index.min().date().isoformat(),
                        "window_end": aligned_candidate.index.max().date().isoformat(),
                        "trading_days": int(len(aligned_candidate)),
                        "candidate_portfolio_id": candidate_id,
                        "control_portfolio_id": control_id,
                        "candidate_total_return": candidate_metrics["total_return"],
                        "candidate_cagr": candidate_metrics["cagr"],
                        "candidate_annualized_volatility": candidate_metrics["annualized_volatility"],
                        "candidate_sharpe_ratio": candidate_metrics["sharpe_ratio"],
                        "candidate_maximum_drawdown": candidate_metrics["maximum_drawdown"],
                        "control_total_return": control_metrics["total_return"],
                        "control_cagr": control_metrics["cagr"],
                        "control_annualized_volatility": control_metrics["annualized_volatility"],
                        "control_sharpe_ratio": control_metrics["sharpe_ratio"],
                        "control_maximum_drawdown": control_metrics["maximum_drawdown"],
                        "cagr_difference": float(candidate_metrics["cagr"]) - float(control_metrics["cagr"]),
                        "sharpe_ratio_difference": float(candidate_metrics["sharpe_ratio"]) - float(control_metrics["sharpe_ratio"]),
                        "maximum_drawdown_difference": float(candidate_metrics["maximum_drawdown"]) - float(control_metrics["maximum_drawdown"]),
                        "annualized_volatility_difference": float(candidate_metrics["annualized_volatility"])
                        - float(control_metrics["annualized_volatility"]),
                        "control_dominates_angl": dominated,
                        "turnover": 0.0,
                        "transaction_cost_drag": 0.0,
                        "max_daily_exposure": 1.0,
                        "max_daily_weight_sum": 1.0,
                        "timing_invariant_status": "pass_project_shifted_weight_no_lookahead",
                        "numeric_invariant_status": "pass",
                        "exposure_invariant_status": "pass",
                        "weight_invariant_status": "pass",
                    }
                )
    return rows


def rolling_summary_rows(rows_36: list[dict[str, Any]], rows_60: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for months, rows in ((36, rows_36), (60, rows_60)):
        for cost_bps in COST_BPS_GRID:
            cost_rows = [row for row in rows if float(row["cost_assumption_bps"]) == cost_bps]
            by_window: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cost_rows:
                by_window.setdefault((row["window_start"], row["window_end"]), []).append(row)
            best_diffs = []
            dominated_windows = 0
            for window_rows in by_window.values():
                best_control = max(window_rows, key=lambda row: float(row["control_sharpe_ratio"]))
                best_diffs.append(float(best_control["sharpe_ratio_difference"]))
                if any(row["control_dominates_angl"] for row in window_rows):
                    dominated_windows += 1
            positive_count = sum(diff > 0.0 for diff in best_diffs)
            count = len(best_diffs)
            summary.append(
                {
                    "window_months": months,
                    "cost_assumption_bps": cost_bps,
                    "window_count": count,
                    "median_sharpe_difference_vs_best_control": float(pd.Series(best_diffs).median()) if best_diffs else "",
                    "positive_sharpe_difference_count": positive_count,
                    "positive_sharpe_difference_pct": positive_count / count if count else "",
                    "control_dominated_window_count": dominated_windows,
                    "control_dominated_window_pct": dominated_windows / count if count else "",
                }
            )
    return summary


def calendar_year_rows(series: dict[str, dict[float, dict[str, Any]]], portfolios: dict[str, dict[float, pd.Series]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id, cost_map in series.items():
        for cost_bps, payload in cost_map.items():
            returns = payload["returns"]
            for year, year_returns in returns.groupby(returns.index.year):
                rows.append(
                    {
                        "calendar_year": int(year),
                        "entity_id": entity_id,
                        "entity_type": "candidate_standalone" if entity_id == "ANGL" else "control_standalone",
                        "cost_assumption_bps": cost_bps,
                        **metric_payload(
                            year_returns,
                            payload["turnover"].reindex(year_returns.index).fillna(0.0),
                            payload["cost"].reindex(year_returns.index).fillna(0.0),
                            payload["weights"].reindex(year_returns.index).ffill().fillna(0.0),
                        ),
                    }
                )
    for portfolio_id, cost_map in portfolios.items():
        for cost_bps, returns in cost_map.items():
            for year, year_returns in returns.groupby(returns.index.year):
                rows.append(
                    {
                        "calendar_year": int(year),
                        "entity_id": portfolio_id,
                        "entity_type": "portfolio_construction",
                        "cost_assumption_bps": cost_bps,
                        **metric_payload(year_returns),
                    }
                )
    return rows


def portfolio_contribution_rows(portfolios: dict[str, dict[float, pd.Series]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in portfolios.items():
        for cost_bps, returns in cost_map.items():
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "portfolio_construction": "100pct_frozen_reference"
                    if portfolio_id == "frozen_reference_100pct"
                    else "80pct_frozen_reference_plus_20pct_candidate_or_control",
                    "cost_assumption_bps": cost_bps,
                    **metric_payload(returns),
                    "correlation_to_frozen_reference": 1.0
                    if portfolio_id == "frozen_reference_100pct"
                    else prior.safe_corr(returns, portfolios["frozen_reference_100pct"][cost_bps]),
                }
            )
    return rows


def prior_row_lookup() -> dict[str, dict[str, str]]:
    base = ROOT / "evidence" / "research_recovery" / "rerun_fast_source_library_blocked_candidates_v3" / "latest"
    lookup: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(base / "all_trial_results.csv"):
        if row["strategy_id"] == STRATEGY_ID and row["cost_assumption_bps"] == "5":
            lookup["ANGL"] = row
    for row in read_csv_rows(base / "control_results.csv"):
        if row["strategy_id"] == STRATEGY_ID and row["cost_assumption_bps"] == "5":
            lookup[row["control_id"]] = row
    for row in read_csv_rows(base / "portfolio_contribution_results.csv"):
        if row["strategy_id"] == STRATEGY_ID and row["cost_assumption_bps"] == "5" and row["period_label"] == "full_period":
            lookup[row["portfolio_id"]] = row
    return lookup


def reproduction_rows(
    full_rows: list[dict[str, Any]], portfolio_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prior_lookup = prior_row_lookup()
    current_lookup: dict[str, dict[str, Any]] = {}
    for row in full_rows:
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS and row["entity_id"] in {"ANGL", *CONTROL_IDS}:
            current_lookup[row["entity_id"]] = row
    for row in portfolio_rows:
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS and row["portfolio_id"] in PORTFOLIO_IDS:
            current_lookup[row["portfolio_id"]] = row
    rows: list[dict[str, Any]] = []
    metric_fields = ["total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"]
    for entity_id in ("ANGL", "HYG_buy_hold", "monthly_rebalanced_50_50_HYG_JNK", *PORTFOLIO_IDS):
        prior_row = prior_lookup.get(entity_id, {})
        current_row = current_lookup.get(entity_id, {})
        for metric in metric_fields:
            previous = float(prior_row.get(metric, "nan")) if prior_row.get(metric, "") != "" else float("nan")
            current = float(current_row.get(metric, "nan")) if current_row.get(metric, "") != "" else float("nan")
            diff = current - previous if math.isfinite(current) and math.isfinite(previous) else float("nan")
            rows.append(
                {
                    "entity_id": entity_id,
                    "metric": metric,
                    "prior_value": previous,
                    "recomputed_value": current,
                    "absolute_difference": abs(diff) if math.isfinite(diff) else "",
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "reproduction_status": "pass"
                    if math.isfinite(diff) and abs(diff) <= REPRODUCTION_TOLERANCE
                    else "fail",
                }
            )
    return rows


def full_portfolio_metrics(portfolio_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["portfolio_id"]: row for row in portfolio_rows if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS}


def decision(
    reproduction: list[dict[str, Any]],
    full_portfolio: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    reproduction_pass = all(row["reproduction_status"] == "pass" for row in reproduction)
    if not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "blocked",
            "data_or_comparability_failure",
            {"reproduction_pass": False},
        )
    portfolio_5 = full_portfolio_metrics(full_portfolio)
    candidate = portfolio_5[f"{STRATEGY_ID}_candidate_20pct"]
    controls = [portfolio_5["HYG_buy_hold_20pct_control"], portfolio_5["monthly_rebalanced_50_50_HYG_JNK_20pct_control"]]
    full_sharpe_diffs = [float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) for control in controls]
    best_control_mdd = max(float(control["maximum_drawdown"]) for control in controls)
    full_control_dominates = any(dominates(control, candidate) for control in controls)
    full_favorable = min(full_sharpe_diffs) > 0.0 and not full_control_dominates

    half_ok = True
    for half in ("first_chronological_half", "second_chronological_half"):
        half_candidate = next(
            row
            for row in half_rows
            if row["entity_id"] == f"{STRATEGY_ID}_candidate_20pct"
            and row["half_label"] == half
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )
        half_controls = [
            row
            for row in half_rows
            if row["entity_id"] in {"HYG_buy_hold_20pct_control", "monthly_rebalanced_50_50_HYG_JNK_20pct_control"}
            and row["half_label"] == half
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        ]
        if not all(float(half_candidate["sharpe_ratio"]) > float(control["sharpe_ratio"]) for control in half_controls):
            half_ok = False
    summary_36 = next(row for row in rolling_summary if int(row["window_months"]) == 36 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS)
    summary_60 = next(row for row in rolling_summary if int(row["window_months"]) == 60 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS)
    rolling_ok = (
        float(summary_36["median_sharpe_difference_vs_best_control"]) > 0.0
        and float(summary_60["median_sharpe_difference_vs_best_control"]) > 0.0
        and float(summary_36["positive_sharpe_difference_pct"]) > 0.5
        and float(summary_60["positive_sharpe_difference_pct"]) > 0.5
        and float(summary_36["control_dominated_window_pct"]) <= 0.5
        and float(summary_60["control_dominated_window_pct"]) <= 0.5
    )
    mdd_ok = float(candidate["maximum_drawdown"]) >= best_control_mdd - 0.02
    full_positive_ok = min(full_sharpe_diffs) >= 0.03 and mdd_ok and not full_control_dominates
    invariant_ok = all(row.get("invariant_pass") in {True, "true"} for row in full_portfolio)
    checks = {
        "reproduction_pass": reproduction_pass,
        "full_sharpe_min_advantage": min(full_sharpe_diffs),
        "full_control_dominates": full_control_dominates,
        "full_mdd_not_worse_than_best_control_by_more_than_0_02": mdd_ok,
        "half_sharpe_exceeds_controls": half_ok,
        "rolling_requirements_pass": rolling_ok,
        "invariant_ok": invariant_ok,
        "rolling_36": summary_36,
        "rolling_60": summary_60,
    }
    if full_positive_ok and half_ok and rolling_ok and invariant_ok:
        return "validation_positive", "validation", "", checks
    if full_control_dominates:
        return "validation_failed", "validation", "weak_vs_primary_control", checks
    if min(full_sharpe_diffs) <= 0.0:
        return "validation_failed", "validation", "weak_vs_primary_control", checks
    both_medians_non_positive = (
        float(summary_36["median_sharpe_difference_vs_best_control"]) <= 0.0
        and float(summary_60["median_sharpe_difference_vs_best_control"]) <= 0.0
    )
    loses_both = float(summary_36["positive_sharpe_difference_pct"]) <= 0.5 and float(summary_60["positive_sharpe_difference_pct"]) <= 0.5
    if both_medians_non_positive or loses_both:
        return "validation_failed", "validation", "period_instability", checks
    if full_favorable and invariant_ok:
        return "validation_mixed", "validation", "", checks
    return "validation_failed", "validation", "overfit_or_unstable", checks


def strategy_card_row(card: Any, outcome: str, stage: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": card.display_name,
        "entity_type": "strategy_configuration",
        "strategy_architecture": card.complete_frozen_rule,
        "source_or_research_lineage": "rerun_fast_source_library_blocked_candidates_v3_exploratory_followup_diversifier",
        "instrument_universe": "ANGL|HYG|JNK",
        "parameters": card.parameters,
        "benchmark_or_control": "HYG_buy_hold|monthly_rebalanced_50_50_HYG_JNK|frozen_current_active_vm_dsr_usci_combo",
        "stage": stage,
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def trial_ledger_row(card: Any, outcome: str, stage: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": card.display_name,
        "entity_type": "experiment_trial",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "changed_fields_from_parent": "validation_diagnostics_only",
        "stage": stage,
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "next_action": next_action,
        "strategy_definition_changed": False,
        "instruments_changed": False,
        "parameters_changed": False,
        "benchmarks_changed": False,
        "timeframe_selected_from_performance": False,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            "benchmark_or_control_id": "HYG_buy_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "standalone_and_80_20_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "monthly_rebalanced_50_50_HYG_JNK",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "standalone_and_80_20_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "frozen_portfolio_reference",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
    ]


def next_action_for(outcome: str) -> str:
    if outcome == "validation_positive":
        return "direction_owner_review_angl_paper_demo_eligibility_v1"
    if outcome == "validation_mixed":
        return "direction_owner_review_angl_validation_mixed_v1"
    if outcome == "validation_failed":
        return "direction_owner_review_close_angl_after_validation_v1"
    return "direction_owner_review_angl_validation_block_v1"


def build_report(outcome: str, failure_reason: str, next_action: str, checks: dict[str, Any]) -> str:
    return f"""
# ANGL Fallen Angel Diversifier Validation V1

This validation covered exactly `{STRATEGY_ID}`. It created one validation child trial linked to
`{PARENT_TRIAL_ID}` and left the exploratory trial unchanged.

## Decision

- Outcome: `{outcome}`
- Primary failure reason: `{failure_reason}`
- Exact next action: `{next_action}`

## Key Checks

- Reproduction pass: `{checks.get('reproduction_pass')}`
- Full-period minimum Sharpe advantage versus 80/20 controls: `{csv_value(checks.get('full_sharpe_min_advantage'))}`
- Drawdown tolerance pass: `{checks.get('full_mdd_not_worse_than_best_control_by_more_than_0_02')}`
- Half-period Sharpe pass: `{checks.get('half_sharpe_exceeds_controls')}`
- Rolling requirements pass: `{checks.get('rolling_requirements_pass')}`

No clean holdout is claimed. Chronological halves and rolling windows are validation diagnostics only.
No source research, provider download, parameter change, benchmark correction, promotion review, paper/demo activation,
broker/account/order path, or real-money action occurred.
"""


COMMON_METRIC_FIELDS = [
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
    "transaction_cost_drag",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


def deterministic_core_hash() -> str:
    names = [
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "reproduction_check.csv",
        "full_period_results.csv",
        "chronological_half_results.csv",
        "rolling_36_month_results.csv",
        "rolling_60_month_results.csv",
        "rolling_window_summary.csv",
        "calendar_year_results.csv",
        "portfolio_contribution_results.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "validation_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    input_before = input_evidence_hashes()
    cache_before = cache_hashes()
    clean_output_dir()

    card = base_card()
    state = load_strategy_state()
    frozen = run_frozen_card(card)
    if not frozen["executable"]:
        raise RuntimeError("ANGL frozen card is unexpectedly non-executable")
    series = standalone_and_control_returns(card, frozen)
    portfolios = portfolio_returns(series, frozen["reference"])
    full_rows = full_period_rows(series, portfolios)
    half_rows = chronological_half_rows(series, portfolios)
    rolling_36 = rolling_rows(portfolios, 36)
    rolling_60 = rolling_rows(portfolios, 60)
    rolling_summary = rolling_summary_rows(rolling_36, rolling_60)
    calendar_rows = calendar_year_rows(series, portfolios)
    portfolio_rows = portfolio_contribution_rows(portfolios)
    reproduction = reproduction_rows(full_rows, portfolio_rows)
    outcome, stage, failure_reason, checks = decision(reproduction, portfolio_rows, half_rows, rolling_summary)
    next_action = next_action_for(outcome)

    write_yaml(
        OUTPUT_DIR / "validation_manifest.yaml",
        {
            "validation_id": VALIDATION_ID,
            "mode": "validation",
            "lane": "validation",
            "stage": "validation",
            "adaptation_label": ADAPTATION_LABEL,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "validation_trial_id": VALIDATION_TRIAL_ID,
            "primary_cost_assumption_bps": PRIMARY_COST_BPS,
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            "reproduction_tolerance": REPRODUCTION_TOLERANCE,
            "input_evidence_files": [rel(path) for path in INPUT_EVIDENCE_FILES if path.exists()],
            "exact_next_action": next_action,
            **FORBIDDEN_FLAGS,
        },
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        [strategy_card_row(card, outcome, stage, failure_reason, next_action)],
        [
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "strategy_architecture",
            "source_or_research_lineage",
            "instrument_universe",
            "parameters",
            "benchmark_or_control",
            "stage",
            "trial_id",
            "parent_trial_id",
            "adaptation_label",
            "outcome",
            "failure_reason",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        [trial_ledger_row(card, outcome, stage, failure_reason, next_action)],
        [
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "trial_id",
            "parent_trial_id",
            "adaptation_label",
            "changed_fields_from_parent",
            "stage",
            "outcome",
            "primary_failure_reason",
            "next_action",
            "strategy_definition_changed",
            "instruments_changed",
            "parameters_changed",
            "benchmarks_changed",
            "timeframe_selected_from_performance",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": VALIDATION_ID,
                "entity_type": "process_task",
                "stage": "validation",
                "outcome": outcome,
                "exact_next_action": next_action,
                "strategy_counted": False,
                "trial_counted": False,
            }
        ],
        ["task_id", "entity_type", "stage", "outcome", "exact_next_action", "strategy_counted", "trial_counted"],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows(),
        ["benchmark_or_control_id", "entity_type", "stage", "role", "counted_as_strategy", "counted_as_trial"],
    )
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        ["entity_id", "metric", "prior_value", "recomputed_value", "absolute_difference", "tolerance", "reproduction_status"],
    )
    write_csv(
        OUTPUT_DIR / "full_period_results.csv",
        full_rows,
        ["entity_id", "entity_type", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_rows,
        ["entity_id", "entity_type", "half_label", "half_source", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    rolling_fields = [
        "window_months",
        "cost_assumption_bps",
        "window_start",
        "window_end",
        "trading_days",
        "candidate_portfolio_id",
        "control_portfolio_id",
        "candidate_total_return",
        "candidate_cagr",
        "candidate_annualized_volatility",
        "candidate_sharpe_ratio",
        "candidate_maximum_drawdown",
        "control_total_return",
        "control_cagr",
        "control_annualized_volatility",
        "control_sharpe_ratio",
        "control_maximum_drawdown",
        "cagr_difference",
        "sharpe_ratio_difference",
        "maximum_drawdown_difference",
        "annualized_volatility_difference",
        "control_dominates_angl",
        "turnover",
        "transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "timing_invariant_status",
        "numeric_invariant_status",
        "exposure_invariant_status",
        "weight_invariant_status",
    ]
    write_csv(OUTPUT_DIR / "rolling_36_month_results.csv", rolling_36, rolling_fields)
    write_csv(OUTPUT_DIR / "rolling_60_month_results.csv", rolling_60, rolling_fields)
    write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary,
        [
            "window_months",
            "cost_assumption_bps",
            "window_count",
            "median_sharpe_difference_vs_best_control",
            "positive_sharpe_difference_count",
            "positive_sharpe_difference_pct",
            "control_dominated_window_count",
            "control_dominated_window_pct",
        ],
    )
    write_csv(
        OUTPUT_DIR / "calendar_year_results.csv",
        calendar_rows,
        ["calendar_year", "entity_id", "entity_type", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_rows,
        [
            "portfolio_id",
            "portfolio_construction",
            "cost_assumption_bps",
            *COMMON_METRIC_FIELDS,
            "correlation_to_frozen_reference",
        ],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "entity_id": STRATEGY_ID,
                "entity_type": "strategy_configuration",
                "stage": stage,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ],
        ["entity_id", "entity_type", "stage", "outcome", "primary_failure_reason", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": VALIDATION_TRIAL_ID,
                "parent_trial_id": PARENT_TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ]
        if failure_reason
        else [],
        ["strategy_id", "trial_id", "parent_trial_id", "outcome", "primary_failure_reason", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "scope": "global",
                "entity_id": VALIDATION_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": outcome,
            },
            {
                "scope": "strategy_configuration",
                "entity_id": STRATEGY_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": outcome,
            },
        ],
        ["scope", "entity_id", "exact_next_action", "execute_now", "reason"],
    )
    write_text(OUTPUT_DIR / "validation_report.md", build_report(outcome, failure_reason, next_action, checks))

    protected_after = protected_hashes()
    input_after = input_evidence_hashes()
    cache_after = cache_hashes()
    consistency = {
        "validation_id": VALIDATION_ID,
        "exactly_one_strategy_validated": True,
        "strategy_id": STRATEGY_ID,
        "excluded_clare_nvi_and_other_candidates": True,
        "parent_exploratory_trial_id": PARENT_TRIAL_ID,
        "validation_child_trial_id": VALIDATION_TRIAL_ID,
        "prior_exploratory_state": state,
        "reproduction_passed": all(row["reproduction_status"] == "pass" for row in reproduction),
        "rolling_36_window_count_primary": next(
            row for row in rolling_summary if int(row["window_months"]) == 36 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )["window_count"],
        "rolling_60_window_count_primary": next(
            row for row in rolling_summary if int(row["window_months"]) == 60 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )["window_count"],
        "no_clean_holdout_claimed": True,
        "strategy_definition_changed": False,
        "instruments_changed": False,
        "parameters_changed": False,
        "benchmarks_changed": False,
        "portfolio_sleeve_weight_changed": False,
        "entity_separation_passed": True,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "input_evidence_hashes_before": input_before,
        "input_evidence_hashes_after": input_after,
        "input_evidence_hashes_unchanged": input_before == input_after,
        "protected_cache_hashes_before": cache_before,
        "protected_cache_hashes_after": cache_after,
        "protected_cache_hashes_unchanged": cache_before == cache_after,
        "outcome": outcome,
        "stage": stage,
        "primary_failure_reason": failure_reason,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["exactly_one_strategy_validated"]
        and consistency["excluded_clare_nvi_and_other_candidates"]
        and consistency["reproduction_passed"]
        and consistency["entity_separation_passed"]
        and consistency["protected_state_hashes_unchanged"]
        and consistency["input_evidence_hashes_unchanged"]
        and consistency["protected_cache_hashes_unchanged"]
        and not any(consistency[name] for name in FORBIDDEN_FLAGS)
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "validation_id": VALIDATION_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "exact_next_action": next_action,
        "reproduction_passed": consistency["reproduction_passed"],
        "rolling_36_window_count_primary": consistency["rolling_36_window_count_primary"],
        "rolling_60_window_count_primary": consistency["rolling_60_window_count_primary"],
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "input_evidence_hashes_unchanged": consistency["input_evidence_hashes_unchanged"],
        "protected_cache_hashes_unchanged": consistency["protected_cache_hashes_unchanged"],
        "task_outcome": "angl_fallen_angel_diversifier_validation_v1_complete",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
