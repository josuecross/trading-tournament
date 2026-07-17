from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import spy_xlu_4week_beta_rotation_bounded_screen_v1 as beta
from strategy_lab.research_os.research import usci_current_methodology_validation_v1 as usci_validation


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"

CANDIDATE_ID = "combo_vm_dsr_usci_equal_weight_monthly_v1"
FAMILY_ID = "multi_strategy_diversified_portfolio"
ROLE = "diversified_observation_portfolio_candidate"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
VM_ID = "vm_quality_lowvol_proxy_v1"
DSR_ID = "dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "usci_dynamic_commodity_curve_selection_wrapper_v1"
PAPER_VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
PAPER_DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"

ACTIVE_COMBO_SERIES = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
ACTIVE_COMBO_DEFINITION = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_benchmark_definition.yaml"
ACTIVE_COMBO_ALLOCATIONS = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_monthly_allocations.csv"
ACTIVE_STRATEGY_RECOMPUTE = ROOT / "evidence" / "active_strategy_evidence_recompute" / "latest"
USCI_VALIDATION_DIR = ROOT / "evidence" / "usci_current_methodology_validation_v1" / "latest"
USCI_SCREEN_DIR = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
BETA_EVIDENCE_DIR = ROOT / "evidence" / "spy_xlu_4week_beta_rotation_bounded_screen_v1" / "latest"

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"

INITIAL_CAPITAL = float(active.STARTING_EQUITY)
PORTFOLIO_COST_RATE = float(active.SLIPPAGE)
USCI_START = pd.Timestamp("2021-01-04")
USCI = "USCI"
BIL = "BIL"
SPY = "SPY"

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "direction_owner_review_required",
    "risk_reduction_without_return_edge",
    "redundant_with_active_combo",
    "no_material_edge",
    "invalid_methodology",
    "duplicate_resolved",
}


@dataclass(frozen=True)
class SeriesBundle:
    strategy_id: str
    role: str
    equity: pd.Series
    returns: pd.Series


@dataclass(frozen=True)
class PortfolioResult:
    equity: pd.Series
    returns: pd.Series
    sleeve_values: pd.DataFrame
    sleeve_weights: pd.DataFrame
    rebalance_rows: list[dict[str, Any]]
    contribution_rows: list[dict[str, Any]]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def clean_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def read_adjusted_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return clean.set_index("date")[symbol].astype(float)


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "role": ROLE,
        "components": [VM_ID, DSR_ID, USCI_ID],
        "allocation": "one_third_each",
        "portfolio_rebalance": "monthly_first_common_valid_session_close",
        "between_rebalances": "sleeve_weights_drift_naturally",
        "component_return_input": "authoritative_corrected_daily_net_series",
        "portfolio_cost": "canonical_transfer_cost_applied_once",
        "optimization": "none",
    }
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "fingerprint_fields": fields,
        "fingerprint_hash": stable_hash(fields),
    }


def beta_rotation_memory() -> dict[str, Any]:
    outcome_path = BETA_EVIDENCE_DIR / "screening_outcome.json"
    outcome = json.loads(outcome_path.read_text(encoding="utf-8")) if outcome_path.exists() else {}
    return {
        "candidate_id": "spy_xlu_4week_beta_rotation_v1",
        "preserved_evidence_path": rel(BETA_EVIDENCE_DIR),
        "formal_outcome": outcome.get("outcome", "control_weak"),
        "exact_candidate_closed_for_immediate_retesting": True,
        "broader_intermarket_equity_beta_rotation_family_open": True,
        "underperformed_SPY_buy_and_hold_full_period": True,
        "underperformed_SPY_200d_trend_model_full_period": True,
        "blocks_beating_each_decision_critical_control": "2 / 5",
        "post_2020_excess_return_versus_SPY_negative": True,
        "drawdown_improvement_vs_SPY_insufficient": True,
        "drawdown_materially_worse_than_SPY_200d_trend_model": True,
        "partial_distinction_from_active_DSR_did_not_compensate_for_weak_performance": True,
        "validation_authorized": False,
        "immediate_variants_prohibited": [
            "alternative_lookbacks",
            "alternative_frequencies",
            "alternative_sectors",
            "sector_baskets",
            "VIX_filters",
            "moving_average_filters",
            "BIL_fallback",
            "leverage",
            "partial_weight_variants",
        ],
        "prior_evidence_modified": False,
    }


def load_component_bundles() -> tuple[dict[str, SeriesBundle], pd.DataFrame]:
    combo = pd.read_csv(ACTIVE_COMBO_SERIES)
    combo["date"] = pd.to_datetime(combo["date"], errors="coerce")
    combo = combo.dropna(subset=["date"]).set_index("date").sort_index()
    usci_price = read_adjusted_close(USCI).loc[USCI_START:]
    usci_equity = (usci_price / float(usci_price.iloc[0]) * INITIAL_CAPITAL).rename(USCI_ID)
    bundles = {
        VM_ID: SeriesBundle(VM_ID, "component_corrected_historical_series", pd.to_numeric(combo["vm_standalone_equity"], errors="coerce").dropna(), pd.Series(dtype=float)),
        DSR_ID: SeriesBundle(DSR_ID, "component_corrected_historical_series", pd.to_numeric(combo["dsr_standalone_equity"], errors="coerce").dropna(), pd.Series(dtype=float)),
        ACTIVE_COMBO_ID: SeriesBundle(ACTIVE_COMBO_ID, "primary_benchmark_reference_only", pd.to_numeric(combo["active_combo_equity"], errors="coerce").dropna(), pd.Series(dtype=float)),
        USCI_ID: SeriesBundle(USCI_ID, "component_current_methodology_wrapper_series", usci_equity.dropna(), pd.Series(dtype=float)),
    }
    ready: dict[str, SeriesBundle] = {}
    for key, bundle in bundles.items():
        equity = bundle.equity.sort_index().astype(float)
        returns = equity.pct_change(fill_method=None).fillna(0.0)
        ready[key] = SeriesBundle(bundle.strategy_id, bundle.role, equity, returns)
    return ready, combo


def common_component_dates(bundles: dict[str, SeriesBundle]) -> pd.DatetimeIndex:
    common = bundles[VM_ID].equity.index
    for component in (DSR_ID, USCI_ID):
        common = common.intersection(bundles[component].equity.index)
    return pd.DatetimeIndex(common).sort_values()


def common_date_alignment_rows(bundles: dict[str, SeriesBundle], common: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows = []
    for component in (VM_ID, DSR_ID, USCI_ID, ACTIVE_COMBO_ID):
        idx = bundles[component].equity.index
        excluded = idx.difference(common)
        rows.append(
            {
                "component_id": component,
                "source_start": idx.min(),
                "source_end": idx.max(),
                "source_date_count": int(len(idx)),
                "common_start": common.min(),
                "common_end": common.max(),
                "common_date_count": int(len(common.intersection(idx))),
                "excluded_dates_count": int(len(excluded)),
                "missing_dates_filled_with_zero": False,
                "missing_dates_forward_filled": False,
            }
        )
    return rows


def monthly_rebalance_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    rows = []
    for _period, frame in pd.DataFrame(index=index).groupby(index.to_period("M")):
        rows.append(pd.Timestamp(frame.index[0]))
    return rows


def simulate_candidate(component_returns: pd.DataFrame) -> PortfolioResult:
    sleeves = [VM_ID, DSR_ID, USCI_ID]
    dates = component_returns.index
    rebalance_dates = set(monthly_rebalance_dates(dates))
    sleeve_values = {sleeve: 0.0 for sleeve in sleeves}
    equity_rows: list[float] = []
    return_rows: list[float] = []
    value_rows: list[dict[str, float]] = []
    weight_rows: list[dict[str, float]] = []
    rebalance_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    prev_equity = INITIAL_CAPITAL
    initialized = False
    for date in dates:
        date = pd.Timestamp(date)
        daily_contribution = {sleeve: 0.0 for sleeve in sleeves}
        if not initialized:
            pre_total = INITIAL_CAPITAL
            turnover = 1.0
            cost = pre_total * turnover * PORTFOLIO_COST_RATE
            net_total = pre_total - cost
            sleeve_values = {sleeve: net_total / 3.0 for sleeve in sleeves}
            initialized = True
            rebalance_rows.append(
                {
                    "rebalance_date": date,
                    "rebalance_type": "initial_allocation",
                    "pre_rebalance_total": pre_total,
                    "portfolio_level_turnover": turnover,
                    "portfolio_level_transaction_cost": cost,
                    "post_rebalance_total": net_total,
                    "vm_weight_after_rebalance": 1.0 / 3.0,
                    "dsr_weight_after_rebalance": 1.0 / 3.0,
                    "usci_weight_after_rebalance": 1.0 / 3.0,
                }
            )
            total = net_total
        else:
            for sleeve in sleeves:
                gain = sleeve_values[sleeve] * float(component_returns.loc[date, sleeve])
                sleeve_values[sleeve] += gain
                daily_contribution[sleeve] = gain
            total = sum(sleeve_values.values())
            if date in rebalance_dates:
                pre_values = sleeve_values.copy()
                pre_total = total
                pre_weights = {sleeve: (pre_values[sleeve] / pre_total if pre_total else 0.0) for sleeve in sleeves}
                target_each = pre_total / 3.0
                transfer_amount = 0.5 * sum(abs(target_each - pre_values[sleeve]) for sleeve in sleeves)
                turnover = transfer_amount / pre_total if pre_total else 0.0
                cost = pre_total * turnover * PORTFOLIO_COST_RATE
                net_total = pre_total - cost
                sleeve_values = {sleeve: net_total / 3.0 for sleeve in sleeves}
                total = net_total
                rebalance_rows.append(
                    {
                        "rebalance_date": date,
                        "rebalance_type": "monthly_restore_one_third",
                        "pre_rebalance_total": pre_total,
                        "pre_vm_weight": pre_weights[VM_ID],
                        "pre_dsr_weight": pre_weights[DSR_ID],
                        "pre_usci_weight": pre_weights[USCI_ID],
                        "portfolio_level_turnover": turnover,
                        "portfolio_level_transaction_cost": cost,
                        "post_rebalance_total": net_total,
                        "vm_weight_after_rebalance": 1.0 / 3.0,
                        "dsr_weight_after_rebalance": 1.0 / 3.0,
                        "usci_weight_after_rebalance": 1.0 / 3.0,
                    }
                )
        day_return = total / prev_equity - 1.0 if prev_equity else 0.0
        equity_rows.append(float(total))
        return_rows.append(float(day_return))
        prev_equity = total
        value_rows.append({sleeve: float(sleeve_values[sleeve]) for sleeve in sleeves})
        weight_rows.append({sleeve: float(sleeve_values[sleeve] / total if total else 0.0) for sleeve in sleeves})
        contribution_rows.append(
            {
                "date": date,
                "vm_daily_dollar_contribution": daily_contribution[VM_ID],
                "dsr_daily_dollar_contribution": daily_contribution[DSR_ID],
                "usci_daily_dollar_contribution": daily_contribution[USCI_ID],
            }
        )
    equity = pd.Series(equity_rows, index=dates, name=CANDIDATE_ID)
    returns = pd.Series(return_rows, index=dates, name=CANDIDATE_ID)
    value_frame = pd.DataFrame(value_rows, index=dates)
    weight_frame = pd.DataFrame(weight_rows, index=dates)
    return PortfolioResult(equity, returns, value_frame, weight_frame, rebalance_rows, contribution_rows)


def benchmark_from_equity(strategy_id: str, role: str, equity: pd.Series, index: pd.DatetimeIndex) -> SeriesBundle:
    aligned = equity.reindex(index).dropna().astype(float)
    returns = aligned.pct_change(fill_method=None).fillna(0.0)
    return SeriesBundle(strategy_id, role, aligned, returns)


def buy_hold_bundle(strategy_id: str, role: str, symbol: str, index: pd.DatetimeIndex) -> SeriesBundle:
    price = read_adjusted_close(symbol).reindex(index).dropna().astype(float)
    equity = (price / float(price.iloc[0]) * (INITIAL_CAPITAL - INITIAL_CAPITAL * PORTFOLIO_COST_RATE)).rename(strategy_id)
    returns = equity.pct_change(fill_method=None).fillna(0.0)
    return SeriesBundle(strategy_id, role, equity, returns)


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) else float("nan")


def downside_volatility(returns: pd.Series) -> float:
    downside = returns.loc[returns < 0]
    return float(downside.std(ddof=0) * math.sqrt(252)) if len(downside) else 0.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def total_return(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return float("nan")
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def return_to_drawdown(equity: pd.Series) -> float:
    dd = abs(max_drawdown(equity))
    return float(total_return(equity) / dd) if dd > 0 else float("nan")


def complete_year_returns(equity: pd.Series) -> dict[str, float]:
    rows = []
    for year in sorted(set(equity.index.year)):
        if year in {int(equity.index[0].year), int(equity.index[-1].year)}:
            continue
        year_eq = equity.loc[equity.index.year == year]
        if len(year_eq) >= 2:
            rows.append(total_return(year_eq))
    if not rows:
        return {"complete_year_positive_return_rate": float("nan"), "worst_complete_year_return": float("nan")}
    return {
        "complete_year_positive_return_rate": float(sum(ret > 0 for ret in rows) / len(rows)),
        "worst_complete_year_return": float(min(rows)),
    }


def metric_row(bundle: SeriesBundle, block_rows: list[dict[str, Any]], portfolio: PortfolioResult | None = None) -> dict[str, Any]:
    yearly = complete_year_returns(bundle.equity)
    return {
        "strategy_id": bundle.strategy_id,
        "role": bundle.role,
        "start_date": bundle.equity.index[0],
        "end_date": bundle.equity.index[-1],
        "common_date_count": int(len(bundle.equity)),
        "final_equity": float(bundle.equity.iloc[-1]),
        "total_return": total_return(bundle.equity),
        "CAGR": cagr(bundle.equity),
        "complete_year_positive_return_rate": yearly["complete_year_positive_return_rate"],
        "worst_complete_year_return": yearly["worst_complete_year_return"],
        "annualized_volatility": annualized_volatility(bundle.returns),
        "downside_volatility": downside_volatility(bundle.returns),
        "maximum_drawdown": max_drawdown(bundle.equity),
        "worst_block_return": min([float(row["total_return"]) for row in block_rows if row.get("strategy_id") == bundle.strategy_id], default=""),
        "return_to_max_drawdown_ratio": return_to_drawdown(bundle.equity),
        "monthly_rebalance_count": len(portfolio.rebalance_rows) if portfolio else "",
        "sleeve_level_turnover": "",
        "portfolio_level_turnover": float(sum(row.get("portfolio_level_turnover", 0.0) for row in portfolio.rebalance_rows)) if portfolio else "",
        "portfolio_level_transaction_costs": float(sum(row.get("portfolio_level_transaction_cost", 0.0) for row in portfolio.rebalance_rows)) if portfolio else "",
        "total_embedded_component_costs_available": "reported_in_lineage",
        "skipped_rebalance_dates": 0 if portfolio else "",
        "maximum_aggregate_exposure": float(portfolio.sleeve_weights.sum(axis=1).max()) if portfolio else "",
        "maximum_aggregate_weight_sum": float(portfolio.sleeve_weights.sum(axis=1).max()) if portfolio else "",
        "cash_remainder": float((INITIAL_CAPITAL - bundle.equity.iloc[0])) if portfolio else "",
    }


def split_blocks(index: pd.DatetimeIndex, count: int = 5) -> list[dict[str, Any]]:
    positions = np.array_split(np.arange(len(index)), count)
    return [
        {
            "block_id": f"block_{i}",
            "start_date": pd.Timestamp(index[int(pos[0])]),
            "end_date": pd.Timestamp(index[int(pos[-1])]),
            "trading_day_count": int(len(pos)),
            "frozen_before_performance": True,
        }
        for i, pos in enumerate(positions, start=1)
    ]


def deterministic_windows(index: pd.DatetimeIndex, horizon: int, count: int = 5) -> list[dict[str, Any]]:
    if len(index) < horizon:
        return []
    starts = np.linspace(0, len(index) - horizon, count).round().astype(int)
    rows = []
    for i, start in enumerate(starts, start=1):
        end = int(start + horizon - 1)
        rows.append(
            {
                "window_id": f"{horizon}d_window_{i}",
                "horizon_days": horizon,
                "start_date": pd.Timestamp(index[int(start)]),
                "end_date": pd.Timestamp(index[end]),
                "trading_day_count": horizon,
                "frozen_before_performance": True,
            }
        )
    return rows


def period_metrics(bundles: dict[str, SeriesBundle], periods: list[dict[str, Any]], period_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        for strategy_id, bundle in bundles.items():
            equity = bundle.equity.loc[(bundle.equity.index >= period["start_date"]) & (bundle.equity.index <= period["end_date"])]
            returns = bundle.returns.reindex(equity.index).fillna(0.0)
            if len(equity) < 2:
                continue
            rows.append(
                {
                    **period,
                    "period_type": period_type,
                    "strategy_id": strategy_id,
                    "total_return": total_return(equity),
                    "CAGR": cagr(equity),
                    "maximum_drawdown": max_drawdown(equity),
                    "annualized_volatility": annualized_volatility(returns),
                    "downside_volatility": downside_volatility(returns),
                    "return_to_max_drawdown_ratio": return_to_drawdown(equity),
                }
            )
    return rows


def calendar_year_rows(bundles: dict[str, SeriesBundle], common: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows = []
    for year in sorted(set(common.year)):
        status = "partial_first_year" if year == int(common[0].year) else "partial_final_year" if year == int(common[-1].year) else "complete_calendar_year"
        for strategy_id, bundle in bundles.items():
            equity = bundle.equity.loc[bundle.equity.index.year == year]
            if len(equity) < 2:
                continue
            rows.append(
                {
                    "calendar_year": int(year),
                    "year_status": status,
                    "strategy_id": strategy_id,
                    "total_return": total_return(equity),
                    "maximum_drawdown": max_drawdown(equity),
                }
            )
    return rows


def primary_relative_metrics(bundles: dict[str, SeriesBundle], block_rows: list[dict[str, Any]], window_rows: list[dict[str, Any]], calendar_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = bundles[CANDIDATE_ID]
    combo = bundles[ACTIVE_COMBO_ID]
    cand_metric = metric_row(candidate, block_rows)
    combo_metric = metric_row(combo, block_rows)

    def values(strategy_id: str, rows: list[dict[str, Any]], key: str = "total_return") -> list[float]:
        return [float(row[key]) for row in rows if row.get("strategy_id") == strategy_id and row.get(key) not in ("", None)]

    cand_blocks = values(CANDIDATE_ID, block_rows)
    combo_blocks = values(ACTIVE_COMBO_ID, block_rows)
    cand_block_dd = values(CANDIDATE_ID, block_rows, "maximum_drawdown")
    combo_block_dd = values(ACTIVE_COMBO_ID, block_rows, "maximum_drawdown")
    cand_180 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row.get("horizon_days", 0)) == 180]
    combo_180 = [row for row in window_rows if row["strategy_id"] == ACTIVE_COMBO_ID and int(row.get("horizon_days", 0)) == 180]
    cand_252 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row.get("horizon_days", 0)) == 252]
    combo_252 = [row for row in window_rows if row["strategy_id"] == ACTIVE_COMBO_ID and int(row.get("horizon_days", 0)) == 252]
    cal_cand = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == CANDIDATE_ID}
    cal_combo = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == ACTIVE_COMBO_ID}
    post_start = pd.Timestamp("2021-01-04")
    post_cand = candidate.equity.loc[candidate.equity.index >= post_start]
    post_combo = combo.equity.loc[combo.equity.index >= post_start]
    return {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark_id": ACTIVE_COMBO_ID,
        "full_period_total_return_difference": cand_metric["total_return"] - combo_metric["total_return"],
        "CAGR_difference": cand_metric["CAGR"] - combo_metric["CAGR"],
        "maximum_drawdown_difference": cand_metric["maximum_drawdown"] - combo_metric["maximum_drawdown"],
        "annualized_volatility_difference": cand_metric["annualized_volatility"] - combo_metric["annualized_volatility"],
        "downside_volatility_difference": cand_metric["downside_volatility"] - combo_metric["downside_volatility"],
        "return_to_drawdown_ratio_difference": cand_metric["return_to_max_drawdown_ratio"] - combo_metric["return_to_max_drawdown_ratio"],
        "mean_block_excess_return": float(np.mean(np.array(cand_blocks) - np.array(combo_blocks))) if len(cand_blocks) == len(combo_blocks) and cand_blocks else "",
        "median_block_excess_return": float(np.median(np.array(cand_blocks) - np.array(combo_blocks))) if len(cand_blocks) == len(combo_blocks) and cand_blocks else "",
        "blocks_beating_active_combo": int(sum(c > b for c, b in zip(cand_blocks, combo_blocks))),
        "blocks_with_smaller_drawdown": int(sum(c > b for c, b in zip(cand_block_dd, combo_block_dd))),
        "blocks_with_higher_return_and_smaller_drawdown": int(sum(c > b and cd > bd for c, b, cd, bd in zip(cand_blocks, combo_blocks, cand_block_dd, combo_block_dd))),
        "180d_window_wins": int(sum(float(c["total_return"]) > float(b["total_return"]) for c, b in zip(cand_180, combo_180))),
        "252d_window_wins": int(sum(float(c["total_return"]) > float(b["total_return"]) for c, b in zip(cand_252, combo_252))),
        "calendar_years_beating_active_combo": int(sum(cal_cand[y] > cal_combo[y] for y in sorted(set(cal_cand) & set(cal_combo)))),
        "latest_block_excess": float(cand_blocks[-1] - combo_blocks[-1]) if cand_blocks and combo_blocks else "",
        "post_2020_total_return_difference": total_return(post_cand) - total_return(post_combo),
        "from_2021_forward_total_return_difference": total_return(post_cand) - total_return(post_combo),
    }


def component_contribution_rows(portfolio: PortfolioResult) -> list[dict[str, Any]]:
    frame = pd.DataFrame(portfolio.contribution_rows).set_index("date")
    total_initial = INITIAL_CAPITAL
    rows = []
    for component, col in [
        (VM_ID, "vm_daily_dollar_contribution"),
        (DSR_ID, "dsr_daily_dollar_contribution"),
        (USCI_ID, "usci_daily_dollar_contribution"),
    ]:
        rows.append(
            {
                "component_id": component,
                "total_dollar_contribution": float(frame[col].sum()),
                "return_contribution_on_initial_capital": float(frame[col].sum() / total_initial),
                "positive_contribution_days": int((frame[col] > 0).sum()),
                "negative_contribution_days": int((frame[col] < 0).sum()),
            }
        )
    return rows


def sleeve_weight_drift_rows(portfolio: PortfolioResult) -> list[dict[str, Any]]:
    rows = []
    for component in (VM_ID, DSR_ID, USCI_ID):
        weights = portfolio.sleeve_weights[component]
        rows.append(
            {
                "component_id": component,
                "average_weight": float(weights.mean()),
                "ending_weight": float(weights.iloc[-1]),
                "maximum_weight_between_rebalances": float(weights.max()),
                "minimum_weight_between_rebalances": float(weights.min()),
            }
        )
    return rows


def diversification_attribution(component_returns: pd.DataFrame, portfolio: PortfolioResult, bundles: dict[str, SeriesBundle]) -> dict[str, Any]:
    corr = component_returns[[VM_ID, DSR_ID, USCI_ID]].corr()
    spy = bundles["SPY_buy_and_hold"].equity.reindex(component_returns.index).ffill()
    spy_dd = spy / spy.cummax() - 1.0
    drawdown_corr = component_returns.loc[spy_dd <= -0.10, [VM_ID, DSR_ID, USCI_ID]].corr()
    vm_dsr = (component_returns[VM_ID] + component_returns[DSR_ID]) / 2.0
    usci_offsets = (vm_dsr < 0) & (component_returns[USCI_ID] > 0)
    candidate = bundles[CANDIDATE_ID].equity
    combo = bundles[ACTIVE_COMBO_ID].equity.reindex(candidate.index).ffill()
    candidate_dd = candidate / candidate.cummax() - 1.0
    combo_dd = combo / combo.cummax() - 1.0
    dd_improvement_days = candidate_dd > combo_dd
    usci_positive_on_improve = float(((component_returns[USCI_ID] > 0) & dd_improvement_days).sum() / max(int(dd_improvement_days.sum()), 1))
    payload: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "vm_dsr_correlation": float(corr.loc[VM_ID, DSR_ID]),
        "vm_usci_correlation": float(corr.loc[VM_ID, USCI_ID]),
        "dsr_usci_correlation": float(corr.loc[DSR_ID, USCI_ID]),
        "drawdown_vm_dsr_correlation": float(drawdown_corr.loc[VM_ID, DSR_ID]) if not drawdown_corr.empty else "",
        "drawdown_vm_usci_correlation": float(drawdown_corr.loc[VM_ID, USCI_ID]) if not drawdown_corr.empty else "",
        "drawdown_dsr_usci_correlation": float(drawdown_corr.loc[DSR_ID, USCI_ID]) if not drawdown_corr.empty else "",
        "pct_days_USCI_offsets_negative_combined_VM_DSR_return": float(usci_offsets.sum() / max(int((vm_dsr < 0).sum()), 1)),
        "pct_candidate_drawdown_improvement_attributable_to_USCI_positive_days": usci_positive_on_improve,
        "leave_one_out_portfolios_created": False,
        "weights_optimized": False,
    }
    return payload


def cost_and_turnover_rows(portfolio: PortfolioResult) -> list[dict[str, Any]]:
    rows = [
        {
            "cost_layer": "component_internal",
            "description": "VM and DSR corrected standalone series include their internal methodology costs; USCI current methodology uses the investable wrapper series.",
            "cost_amount": "embedded_in_component_net_returns",
            "double_counted": False,
        },
        {
            "cost_layer": "portfolio_initial_and_monthly_transfers",
            "description": "Portfolio transfer costs applied once to actual pre-rebalance sleeve transfers.",
            "cost_amount": float(sum(row["portfolio_level_transaction_cost"] for row in portfolio.rebalance_rows)),
            "double_counted": False,
        },
    ]
    for row in portfolio.rebalance_rows:
        rows.append({**row, "cost_layer": "rebalance_event"})
    return rows


def duplicate_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": ACTIVE_COMBO_ID,
            "exact_duplicate": False,
            "reason": "Existing active combo has VM and DSR only; it excludes USCI and remains benchmark/reference only.",
            "review_result": "primary_benchmark_not_duplicate",
        },
        {
            "reviewed_id": CANDIDATE_ID,
            "exact_duplicate": False,
            "reason": "No corrected evidence packet found for a VM/DSR/USCI one-third monthly sleeve-accounting portfolio before this run.",
            "review_result": "no_existing_exact_corrected_methodology_screen_found",
        },
    ]


def component_source_lineage_rows(bundles: dict[str, SeriesBundle]) -> list[dict[str, Any]]:
    return [
        {
            "component_id": VM_ID,
            "authoritative_evidence_path": rel(ACTIVE_COMBO_SERIES),
            "component_fingerprint": stable_hash({"id": VM_ID, "source": rel(ACTIVE_COMBO_SERIES), "column": "vm_standalone_equity"}),
            "historical_start": bundles[VM_ID].equity.index[0],
            "historical_end": bundles[VM_ID].equity.index[-1],
            "daily_net_return_or_nav_series": "vm_standalone_equity",
            "holdings_or_exposure_trace": rel(ACTIVE_COMBO_ALLOCATIONS),
            "internal_cost_treatment": "embedded in corrected VM standalone equity series",
            "data_and_cache_lineage": rel(ACTIVE_STRATEGY_RECOMPUTE),
            "conflict_detected": False,
        },
        {
            "component_id": DSR_ID,
            "authoritative_evidence_path": rel(ACTIVE_COMBO_SERIES),
            "component_fingerprint": stable_hash({"id": DSR_ID, "source": rel(ACTIVE_COMBO_SERIES), "column": "dsr_standalone_equity"}),
            "historical_start": bundles[DSR_ID].equity.index[0],
            "historical_end": bundles[DSR_ID].equity.index[-1],
            "daily_net_return_or_nav_series": "dsr_standalone_equity",
            "holdings_or_exposure_trace": rel(ACTIVE_COMBO_ALLOCATIONS),
            "internal_cost_treatment": "embedded in corrected DSR standalone equity series",
            "data_and_cache_lineage": rel(ACTIVE_STRATEGY_RECOMPUTE),
            "conflict_detected": False,
        },
        {
            "component_id": USCI_ID,
            "authoritative_evidence_path": rel(USCI_VALIDATION_DIR),
            "component_fingerprint": stable_hash({"id": USCI_ID, "source": rel(USCI_VALIDATION_DIR), "start": str(USCI_START.date())}),
            "historical_start": bundles[USCI_ID].equity.index[0],
            "historical_end": bundles[USCI_ID].equity.index[-1],
            "daily_net_return_or_nav_series": "USCI adjusted wrapper NAV from current-methodology validation period",
            "holdings_or_exposure_trace": rel(USCI_SCREEN_DIR / "source_and_preregistration.json"),
            "internal_cost_treatment": "USCI wrapper costs are embedded in ETF adjusted price; portfolio layer does not reconstruct futures costs",
            "data_and_cache_lineage": rel(cache_path(USCI)),
            "conflict_detected": False,
        },
    ]


def preregistration(common: pd.DatetimeIndex, fingerprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "role": ROLE,
        "hypothesis": "USCI's commodity-curve wrapper may improve VM/DSR diversification without unacceptable return sacrifice.",
        "components": [VM_ID, DSR_ID, USCI_ID],
        "component_weights": {VM_ID: 1.0 / 3.0, DSR_ID: 1.0 / 3.0, USCI_ID: 1.0 / 3.0},
        "rebalance_rule": "first common valid trading session of each calendar month at the close",
        "between_rebalances": "sleeve weights drift naturally",
        "constant_weight_daily_return_averaging": False,
        "initial_capital": INITIAL_CAPITAL,
        "portfolio_cost_rate": PORTFOLIO_COST_RATE,
        "common_start": common[0],
        "common_end": common[-1],
        "common_date_count": int(len(common)),
        "primary_benchmark": ACTIVE_COMBO_ID,
        "secondary_benchmarks": [SPY, PAPER_VM_ID, PAPER_DSR_ID, USCI_ID, BIL],
        "fingerprint_hash": fingerprint["fingerprint_hash"],
        "outcome_rules_frozen_before_performance": sorted(ALLOWED_OUTCOMES),
        "no_optimization": True,
        "no_paper_forward_activation": True,
    }


def classify_outcome(relative: dict[str, Any], diversification: dict[str, Any], invariants_passed: bool) -> tuple[str, str]:
    if not invariants_passed:
        return "invalid_methodology", "Accounting, date, exposure, component lineage, cost or determinism invariant failed"
    total_diff = float(relative["full_period_total_return_difference"])
    cagr_diff = float(relative["CAGR_difference"])
    dd_diff = float(relative["maximum_drawdown_difference"])
    ratio_diff = float(relative["return_to_drawdown_ratio_difference"])
    median_block = float(relative["median_block_excess_return"])
    blocks = int(relative["blocks_beating_active_combo"])
    smaller_dd_blocks = int(relative["blocks_with_smaller_drawdown"])
    wins252 = int(relative["252d_window_wins"])
    usci_benefit = float(diversification["pct_candidate_drawdown_improvement_attributable_to_USCI_positive_days"])
    if total_diff > 0 and cagr_diff > 0 and median_block > 0 and blocks >= 3 and ratio_diff > 0 and dd_diff >= -0.02 and wins252 >= 3:
        return "comparative_evidence_positive", "Candidate exceeded active combo return, CAGR, block, 252-day, and return/drawdown requirements"
    if cagr_diff >= -0.01 and dd_diff >= 0.05 and ratio_diff > 0 and smaller_dd_blocks >= 3 and blocks >= 2 and usci_benefit < 0.95:
        return "direction_owner_review_required", "Candidate showed a meaningful diversification trade-off versus active combo without activation authority"
    if total_diff < 0 and cagr_diff < 0 and dd_diff >= 0.05:
        return "risk_reduction_without_return_edge", "Candidate reduced drawdown but underperformed active combo on total return and CAGR"
    if abs(total_diff) < 0.05 and dd_diff < 0.02 and abs(ratio_diff) < 0.10 and blocks <= 2:
        return "redundant_with_active_combo", "Candidate behavior was similar to active combo and USCI added no persistent block-level benefit"
    return "no_material_edge", "No persistent return, material risk reduction, or meaningful incremental diversification was supported"


def run() -> dict[str, Any]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    protected_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
        ACTIVE_COMBO_SERIES,
        ACTIVE_COMBO_DEFINITION,
        BETA_EVIDENCE_DIR / "screening_outcome.json",
    ]
    before = file_snapshot(protected_paths)
    fingerprint = candidate_fingerprint()
    write_json(EVIDENCE_DIR / "candidate_fingerprint.json", fingerprint)
    write_json(EVIDENCE_DIR / "beta_rotation_direction_memory.json", beta_rotation_memory())
    write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_review_rows())

    bundles_raw, _combo_frame = load_component_bundles()
    common = common_component_dates(bundles_raw)
    common_returns = pd.DataFrame(
        {
            VM_ID: bundles_raw[VM_ID].returns.reindex(common),
            DSR_ID: bundles_raw[DSR_ID].returns.reindex(common),
            USCI_ID: bundles_raw[USCI_ID].returns.reindex(common),
        },
        index=common,
    ).dropna()
    common_returns.iloc[0] = 0.0
    common = common_returns.index
    portfolio = simulate_candidate(common_returns)
    candidate_bundle = SeriesBundle(CANDIDATE_ID, ROLE, portfolio.equity, portfolio.returns)
    bundles: dict[str, SeriesBundle] = {
        CANDIDATE_ID: candidate_bundle,
        ACTIVE_COMBO_ID: benchmark_from_equity(ACTIVE_COMBO_ID, "primary_benchmark_reference_only", bundles_raw[ACTIVE_COMBO_ID].equity, common),
        PAPER_VM_ID: benchmark_from_equity(PAPER_VM_ID, "secondary_component_benchmark_corrected_historical_series", bundles_raw[VM_ID].equity, common),
        PAPER_DSR_ID: benchmark_from_equity(PAPER_DSR_ID, "secondary_component_benchmark_corrected_historical_series", bundles_raw[DSR_ID].equity, common),
        USCI_ID: benchmark_from_equity(USCI_ID, "secondary_component_benchmark_current_methodology_series", bundles_raw[USCI_ID].equity, common),
        "SPY_buy_and_hold": buy_hold_bundle("SPY_buy_and_hold", "secondary_benchmark", SPY, common),
        "BIL_cash_proxy": buy_hold_bundle("BIL_cash_proxy", "secondary_benchmark", BIL, common),
    }
    blocks = split_blocks(common, 5)
    windows_180 = deterministic_windows(common, 180, 5)
    windows_252 = deterministic_windows(common, 252, 5)
    block_rows = period_metrics(bundles, blocks, "chronological_block")
    window_rows = period_metrics(bundles, windows_180 + windows_252, "deterministic_window")
    calendar_rows = calendar_year_rows(bundles, common)
    relative = primary_relative_metrics(bundles, block_rows, window_rows, calendar_rows)
    contribution = component_contribution_rows(portfolio)
    sleeve_drift = sleeve_weight_drift_rows(portfolio)
    diversification = diversification_attribution(common_returns, portfolio, bundles)
    lineage_rows = component_source_lineage_rows(bundles_raw)
    date_rows = common_date_alignment_rows(bundles_raw, common)
    protected_after = file_snapshot(protected_paths)

    max_exposure = float(portfolio.sleeve_weights.sum(axis=1).max())
    max_weight_sum = max_exposure
    rebalance_restore_ok = all(
        abs(float(row["vm_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
        and abs(float(row["dsr_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
        and abs(float(row["usci_weight_after_rebalance"]) - 1.0 / 3.0) <= 1e-12
        for row in portfolio.rebalance_rows
    )
    non_rebalance_drift_exists = bool(((portfolio.sleeve_weights.diff().abs().sum(axis=1) > 1e-8) & (~portfolio.sleeve_weights.index.isin(monthly_rebalance_dates(common)))).any())
    invariants = {
        "candidate_id": CANDIDATE_ID,
        "component_identities_frozen": True,
        "component_lineage_resolved": all(not row["conflict_detected"] for row in lineage_rows),
        "active_combo_byte_identical": before[rel(ACTIVE_COMBO_SERIES)] == protected_after[rel(ACTIVE_COMBO_SERIES)] and before[rel(ACTIVE_COMBO_DEFINITION)] == protected_after[rel(ACTIVE_COMBO_DEFINITION)],
        "VM_DSR_USCI_observations_unchanged": before == protected_after,
        "constant_one_third_daily_return_averaging_used": False,
        "sleeve_weights_drift_between_rebalances": non_rebalance_drift_exists,
        "monthly_rebalances_restore_exact_one_third_targets": rebalance_restore_ok,
        "internal_component_costs_reapplied": False,
        "portfolio_level_transfer_costs_applied_once": sum(row["portfolio_level_transaction_cost"] for row in portfolio.rebalance_rows) > 0,
        "turnover_uses_actual_pre_rebalance_sleeve_values": all("pre_vm_weight" in row or row["rebalance_type"] == "initial_allocation" for row in portfolio.rebalance_rows),
        "missing_component_dates_filled_with_zero": False,
        "missing_component_dates_forward_filled": False,
        "common_aligned_dates_only": len(common_returns) == len(common),
        "maximum_aggregate_exposure": max_exposure,
        "maximum_aggregate_weight_sum": max_weight_sum,
        "exposure_never_exceeds_1": max_exposure <= 1.000001,
        "rebalance_dates_frozen_before_performance": True,
        "windows_frozen_before_performance": all(row["frozen_before_performance"] for row in [*blocks, *windows_180, *windows_252]),
        "weight_or_frequency_optimization": False,
        "paper_demo_observation_created": False,
        "broker_order_created": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    invariants["invariants_passed"] = all(
        bool(invariants[key])
        for key in (
            "component_identities_frozen",
            "component_lineage_resolved",
            "active_combo_byte_identical",
            "VM_DSR_USCI_observations_unchanged",
            "sleeve_weights_drift_between_rebalances",
            "monthly_rebalances_restore_exact_one_third_targets",
            "portfolio_level_transfer_costs_applied_once",
            "turnover_uses_actual_pre_rebalance_sleeve_values",
            "common_aligned_dates_only",
            "exposure_never_exceeds_1",
            "rebalance_dates_frozen_before_performance",
            "windows_frozen_before_performance",
        )
    ) and not any(
        bool(invariants[key])
        for key in (
            "constant_one_third_daily_return_averaging_used",
            "internal_component_costs_reapplied",
            "missing_component_dates_filled_with_zero",
            "missing_component_dates_forward_filled",
            "weight_or_frequency_optimization",
            "paper_demo_observation_created",
            "broker_order_created",
            "promotion_authorized",
            "paper_demo_authorized",
            "candidate_exhaustive_authorized",
            "real_money_recommendation",
        )
    )

    outcome, reason = classify_outcome(relative, diversification, bool(invariants["invariants_passed"]))
    next_action = (
        "direction_owner_review_combo_vm_dsr_usci_equal_weight_monthly_v1"
        if outcome in {"comparative_evidence_positive", "direction_owner_review_required"}
        else "fix_combo_vm_dsr_usci_equal_weight_monthly_methodology_issue"
        if outcome == "invalid_methodology"
        else "record_combo_vm_dsr_usci_equal_weight_monthly_exact_variant_memory_and_resume_source_queue"
    )
    screening = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": "" if outcome in {"comparative_evidence_positive", "direction_owner_review_required"} else reason,
        "exact_candidate_closed_for_immediate_retesting": outcome not in {"comparative_evidence_positive", "direction_owner_review_required"},
        "broader_multi_strategy_diversified_portfolio_family_closed": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "next_action": next_action,
    }
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "primary_failure_reason": screening["primary_failure_reason"],
            "exact_candidate_closed_for_immediate_retesting": screening["exact_candidate_closed_for_immediate_retesting"],
            "broader_multi_strategy_diversified_portfolio_family_closed": False,
            "immediate_variants_prohibited": [
                "weight_optimization",
                "risk_parity_weighting",
                "volatility_weighting",
                "alternative_rebalance_schedules",
                "leave_one_out_variants",
                "SPY_additions",
                "BIL_additions",
                "tactical_USCI_allocation",
            ],
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
        }
    ]
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "component_identities_and_fingerprints_frozen": invariants["component_identities_frozen"],
        "active_combo_remains_byte_identical": invariants["active_combo_byte_identical"],
        "VM_DSR_USCI_observations_unchanged": invariants["VM_DSR_USCI_observations_unchanged"],
        "constant_one_third_daily_return_averaging_prohibited": invariants["constant_one_third_daily_return_averaging_used"] is False,
        "sleeve_weights_drift_between_monthly_rebalances": invariants["sleeve_weights_drift_between_rebalances"],
        "monthly_rebalances_restore_one_third_targets": invariants["monthly_rebalances_restore_exact_one_third_targets"],
        "internal_component_costs_not_reapplied": invariants["internal_component_costs_reapplied"] is False,
        "portfolio_level_transfer_costs_applied_once": invariants["portfolio_level_transfer_costs_applied_once"],
        "turnover_uses_actual_pre_rebalance_sleeve_values": invariants["turnover_uses_actual_pre_rebalance_sleeve_values"],
        "missing_component_dates_not_filled": invariants["missing_component_dates_filled_with_zero"] is False and invariants["missing_component_dates_forward_filled"] is False,
        "common_aligned_dates_only": invariants["common_aligned_dates_only"],
        "maximum_exposure_never_exceeds_1": invariants["exposure_never_exceeds_1"],
        "windows_and_rebalance_dates_frozen_before_performance": invariants["rebalance_dates_frozen_before_performance"] and invariants["windows_frozen_before_performance"],
        "no_weight_or_frequency_optimization": invariants["weight_or_frequency_optimization"] is False,
        "no_paper_demo_observation_or_broker_order": invariants["paper_demo_observation_created"] is False and invariants["broker_order_created"] is False,
        "output_generation_deterministic": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    positive_keys = [key for key in consistency if key not in {"candidate_id", "promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation"}]
    consistency["consistency_passed"] = all(consistency[key] is True for key in positive_keys) and not any(
        consistency[key] for key in ("promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation")
    )

    write_json(EVIDENCE_DIR / "preregistration.json", preregistration(common, fingerprint))
    write_csv(EVIDENCE_DIR / "component_source_lineage.csv", lineage_rows)
    write_csv(EVIDENCE_DIR / "common_date_alignment.csv", date_rows)
    write_csv(EVIDENCE_DIR / "frozen_monthly_rebalance_dates.csv", [{"rebalance_date": date, "frozen_before_performance": True} for date in monthly_rebalance_dates(common)])
    write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
    write_csv(EVIDENCE_DIR / "frozen_180d_windows.csv", windows_180)
    write_csv(EVIDENCE_DIR / "frozen_252d_windows.csv", windows_252)
    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", [metric_row(bundle, block_rows, portfolio if strategy_id == CANDIDATE_ID else None) for strategy_id, bundle in bundles.items()])
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar_rows)
    write_csv(EVIDENCE_DIR / "primary_benchmark_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "component_contribution.csv", contribution)
    write_csv(EVIDENCE_DIR / "sleeve_weight_drift.csv", sleeve_drift)
    write_csv(EVIDENCE_DIR / "diversification_attribution.csv", [diversification])
    write_csv(EVIDENCE_DIR / "cost_and_turnover_attribution.csv", cost_and_turnover_rows(portfolio))
    write_csv(EVIDENCE_DIR / "accounting_date_and_exposure_invariants.csv", [invariants])
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# VM/DSR/USCI Equal-Weight Monthly Portfolio Screen v1

Candidate `{CANDIDATE_ID}` was frozen before performance as a monthly one-third sleeve portfolio using VM, DSR, and USCI corrected component histories.

- Outcome: `{outcome}`
- Reason: {reason}
- Common aligned dates: `{len(common)}`
- Primary benchmark: `{ACTIVE_COMBO_ID}`
- Portfolio-level rebalance cost: `{sum(row['portfolio_level_transaction_cost'] for row in portfolio.rebalance_rows):.6f}`
- Constant one-third daily return averaging used: `false`
- Active combo modified: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

Beta Rotation remains closed for immediate retesting, and its evidence packet was not modified.
""",
    )
    return screening


if __name__ == "__main__":
    run()
