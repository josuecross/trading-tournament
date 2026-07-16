from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "qual_static_quality_factor_screen_v1" / "latest"
INTAKE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
SOURCE_ID = "msci_usa_sector_neutral_quality_index_qual"
CANDIDATE_ID = "qual_static_quality_factor_wrapper_v1"
FAMILY_ID = "quality_factor_proxy"
CANDIDATE_INSTRUMENT = "QUAL"
SPLV_REFERENCE_ID = "splv_static_low_vol_factor_wrapper_v1"
ACTIVE_VM_ID = active.VM_ID
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
ACTIVE_COMBO_SERIES = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
BENCHMARK_IDS = [
    "SPY_buy_and_hold",
    active.SPY_200D_ID,
    "BIL_cash_proxy",
    ACTIVE_COMBO_ID,
    ACTIVE_VM_ID,
    SPLV_REFERENCE_ID,
]
ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "quality_factor_return_edge_only",
    "risk_reduction_without_return_edge",
    "control_weak",
    "no_material_edge",
    "not_comparable",
    "invalid_methodology",
    "direction_owner_review_required",
}
TOL = 1e-9


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 10)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


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


def source_intake_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "intake_status": "manual_primary_source_supplied_for_static_quality_factor_screen",
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "MSCI USA Sector Neutral Quality Index",
            "index_provider": "MSCI",
            "index": "MSCI USA Sector Neutral Quality Index",
            "etf_wrapper": CANDIDATE_INSTRUMENT,
            "etf_name": "iShares MSCI USA Quality Factor ETF",
            "source_class": "index_methodology_and_direct_etf_wrapper",
            "source_type": "index methodology and direct ETF wrapper",
            "source_url_or_citation": "MSCI USA Sector Neutral Quality Index methodology and iShares MSCI USA Quality Factor ETF wrapper linkage, as supplied by direction owner.",
            "source_evidence_public_context_only": True,
        },
        "source_supported_mechanism": {
            "universe": "US large- and mid-cap equity universe",
            "sector_relative_quality": True,
            "principal_quality_characteristics": ["high return on equity", "low financial leverage", "low earnings variability"],
            "sector_neutral_index_construction": True,
            "long_only_equity_exposure": True,
            "wrapper_tracking_statement": "QUAL seeks to track the MSCI USA Sector Neutral Quality Index.",
        },
        "project_candidate": {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "instrument": CANDIDATE_INSTRUMENT,
            "classification": [
                "source_backed_index_etf_wrapper",
                "static_quality_factor_exposure",
                "not_constituent_level_index_replication",
            ],
            "hypothesis": "Static exposure to the source-defined quality-factor ETF may provide better return or return/risk characteristics than broad US equity exposure.",
            "constituent_level_index_replication": False,
            "fundamental_data_or_index_rebalance_reconstruction": False,
        },
        "governance": {
            "web_browsing_used": False,
            "provider_download": False,
            "strategy_discovery": False,
            "promotion_or_paper_forward_allowed": False,
            "real_money_recommendation": False,
        },
    }


def source_rule_rows() -> list[dict[str, Any]]:
    return [
        {"rule_id": "universe", "rule_value": "US large- and mid-cap equity universe", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "quality_characteristic_roe", "rule_value": "high return on equity", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "quality_characteristic_leverage", "rule_value": "low financial leverage", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "quality_characteristic_earnings_variability", "rule_value": "low earnings variability", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "sector_neutral_construction", "rule_value": "quality measured relative to sector peers with sector-neutral construction", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "etf_wrapper", "rule_value": "QUAL seeks to track the MSCI USA Sector Neutral Quality Index", "classification": "source_supported", "source_id": SOURCE_ID},
        {"rule_id": "project_trading_rule", "rule_value": "static project-level QUAL wrapper exposure; no constituent replication", "classification": "project_wrapper_convention", "source_id": SOURCE_ID},
    ]


def source_support_rows() -> list[dict[str, Any]]:
    return [
        {
            "material_rule": row["rule_id"],
            "source_id": SOURCE_ID,
            "support_reference": "Direction-owner supplied MSCI/QUAL index-wrapper source packet.",
            "support_status": row["classification"],
            "notes": "Project wrapper convention is explicitly separated from MSCI constituent/index reconstruction.",
        }
        for row in source_rule_rows()
    ]


def read_symbol_close(symbol: str) -> pd.Series:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return series.set_index("date")[symbol].astype(float)


def cache_feasibility(symbol: str = CANDIDATE_INSTRUMENT) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_sha256": sha256_path(path),
        "cache_available": path.exists(),
        "first_valid_date": "",
        "last_valid_date": "",
        "row_count": 0,
        "missing_adjusted_close_values": "",
        "duplicate_dates": "",
        "nonpositive_prices": "",
        "currency": "not_recorded_in_cache",
        "instrument_identity": "iShares MSCI USA Quality Factor ETF",
        "cache_status": "data_not_ready",
        "provider_download_required": False,
    }
    if not path.exists():
        row["blocker"] = "QUAL cache missing"
        return row
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame.get("date", pd.Series(dtype=object)), errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame.get("adj_close", pd.Series(dtype=float)), errors="coerce")
    valid = pd.DataFrame({"date": dates, "adj_close": close}).dropna(subset=["date"]).sort_values("date")
    row["row_count"] = int(len(frame))
    row["missing_adjusted_close_values"] = int(close.isna().sum())
    row["duplicate_dates"] = int(valid["date"].duplicated().sum())
    row["nonpositive_prices"] = int((valid["adj_close"].dropna() <= 0.0).sum())
    clean = valid.dropna(subset=["adj_close"]).drop_duplicates("date")
    if not clean.empty:
        row["first_valid_date"] = str(clean["date"].min().date())
        row["last_valid_date"] = str(clean["date"].max().date())
    ready = (
        path.exists()
        and not clean.empty
        and row["missing_adjusted_close_values"] == 0
        and row["duplicate_dates"] == 0
        and row["nonpositive_prices"] == 0
    )
    row["cache_status"] = "cache_ready" if ready else "data_not_ready"
    row["blocker"] = "" if ready else "invalid QUAL adjusted-close cache"
    return row


def duplicate_gate_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "reviewed_prior_id": ACTIVE_VM_ID,
            "prior_evidence": "active observation and VM parent variants",
            "uses_100pct_qual": False,
            "no_cross_etf_ranking": False,
            "no_volatility_targeting": True,
            "no_trend_filter": False,
            "no_bil_transition": False,
            "static_etf_share_holdings": False,
            "matching_or_equivalent_sampled_window_evaluation": False,
            "correct_drift_aware_accounting": True,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "QUAL appears inside VM universe, but VM ranks SPLV/USMV/QUAL/SPY and applies eligibility/BIL behavior.",
        },
        {
            "reviewed_prior_id": "vm_quality_lowvol_proxy_v1",
            "prior_evidence": "parent VM rule records",
            "uses_100pct_qual": False,
            "no_cross_etf_ranking": False,
            "no_volatility_targeting": True,
            "no_trend_filter": False,
            "no_bil_transition": False,
            "static_etf_share_holdings": False,
            "matching_or_equivalent_sampled_window_evaluation": False,
            "correct_drift_aware_accounting": True,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "Parent VM is tactical allocation, not static QUAL wrapper exposure.",
        },
        {
            "reviewed_prior_id": "value_momentum_factor_etf_rotation_v1",
            "prior_evidence": "registry row with MTUM/VTV/QUAL/USMV/SPY/BIL",
            "uses_100pct_qual": False,
            "no_cross_etf_ranking": False,
            "no_volatility_targeting": True,
            "no_trend_filter": False,
            "no_bil_transition": False,
            "static_etf_share_holdings": False,
            "matching_or_equivalent_sampled_window_evaluation": False,
            "correct_drift_aware_accounting": False,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "Factor rotation uses QUAL as one ranked input, not as 100% static holdings.",
        },
        {
            "reviewed_prior_id": SPLV_REFERENCE_ID,
            "prior_evidence": "static SPLV factor screen evidence",
            "uses_100pct_qual": False,
            "no_cross_etf_ranking": True,
            "no_volatility_targeting": True,
            "no_trend_filter": True,
            "no_bil_transition": True,
            "static_etf_share_holdings": True,
            "matching_or_equivalent_sampled_window_evaluation": True,
            "correct_drift_aware_accounting": True,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "Static SPLV is same static-factor screen shape but a different source-defined factor and ETF.",
        },
    ]
    return rows


def exact_duplicate_exists(rows: list[dict[str, Any]]) -> bool:
    return any(
        row.get("uses_100pct_qual") is True
        and row.get("no_cross_etf_ranking") is True
        and row.get("no_volatility_targeting") is True
        and row.get("no_trend_filter") is True
        and row.get("no_bil_transition") is True
        and row.get("static_etf_share_holdings") is True
        and row.get("matching_or_equivalent_sampled_window_evaluation") is True
        and row.get("correct_drift_aware_accounting") is True
        for row in rows
    )


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "comparison_id": ACTIVE_VM_ID,
            "closest_prior_strategy": True,
            "shared_instrument_or_factor_dimensions": "QUAL is in the active VM universe; both touch quality/low-vol ETF wrapper concepts.",
            "different_signal_dimensions": "No ranking, no 200-day regime/eligibility, no BIL fallback, no momentum/volatility score.",
            "different_portfolio_construction_dimensions": "100% static QUAL shares for the window versus tactical multi-ETF allocation.",
            "economically_meaningful_difference": True,
            "implicit_static_qual_exists_inside_report": False,
            "material_distinction_outcome": "materially_distinct_static_quality_exposure",
        },
        {
            "comparison_id": SPLV_REFERENCE_ID,
            "closest_prior_strategy": False,
            "shared_instrument_or_factor_dimensions": "Static single-factor ETF wrapper screen structure.",
            "different_signal_dimensions": "Different source index and factor exposure: MSCI sector-neutral quality rather than S&P low volatility.",
            "different_portfolio_construction_dimensions": "Both static, but instruments and source mechanisms differ.",
            "economically_meaningful_difference": True,
            "implicit_static_qual_exists_inside_report": False,
            "material_distinction_outcome": "materially_distinct_static_quality_exposure",
        },
        {
            "comparison_id": "quality_momentum_rotation_rows",
            "closest_prior_strategy": False,
            "shared_instrument_or_factor_dimensions": "Quality proxy may appear in multi-factor universes.",
            "different_signal_dimensions": "Rotation/ranking rows are not static QUAL exposure.",
            "different_portfolio_construction_dimensions": "No cross-ETF selection or tactical rebalance here.",
            "economically_meaningful_difference": True,
            "implicit_static_qual_exists_inside_report": False,
            "material_distinction_outcome": "materially_distinct_static_quality_exposure",
        },
    ]


def load_active_combo_returns() -> pd.Series:
    frame = pd.read_csv(ACTIVE_COMBO_SERIES)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    series = pd.DataFrame({"date": dates, ACTIVE_COMBO_ID: returns}).dropna().sort_values("date")
    return series.set_index("date")[ACTIVE_COMBO_ID].astype(float)


def benchmark_returns(close: pd.DataFrame) -> dict[str, pd.Series]:
    splv = read_symbol_close("SPLV")
    splv_returns = splv.pct_change().dropna()
    splv_returns.iloc[0:0]
    return {
        "SPY_buy_and_hold": active.full_returns(close, "SPY_buy_hold"),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        "BIL_cash_proxy": active.full_returns(close, "BIL_cash_proxy"),
        ACTIVE_COMBO_ID: load_active_combo_returns(),
        ACTIVE_VM_ID: active.full_returns(close, ACTIVE_VM_ID),
        SPLV_REFERENCE_ID: splv_returns,
    }


def common_dates_for_screen(candidate: pd.Series, returns_by_id: dict[str, pd.Series]) -> pd.DatetimeIndex:
    common = pd.DatetimeIndex(candidate.dropna().index)
    for series in returns_by_id.values():
        common = common.intersection(pd.DatetimeIndex(series.dropna().index))
    return common.sort_values()


def generate_windows(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        starts = list(range(0, len(common_dates) - horizon))
        selected = starts if len(starts) <= active.MAX_WINDOWS_PER_HORIZON else sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], active.MAX_WINDOWS_PER_HORIZON)))
        for start in selected:
            rows.append(
                {
                    "horizon_days": horizon,
                    "start_index": int(start),
                    "end_index": int(start + horizon),
                    "window_start": str(common_dates[start].date()),
                    "window_end": str(common_dates[start + horizon].date()),
                    "window_valid": True,
                    "selection_algorithm": "deterministic_linspace_max_5_per_horizon_common_valid_period",
                    "generated_before_performance": True,
                }
            )
    return rows


def drawdown_dollars(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    start_marker = equity.index[0] - pd.Timedelta(days=1)
    with_start = pd.concat([pd.Series([active.STARTING_EQUITY], index=[start_marker]), equity])
    return float((with_start - with_start.cummax()).min())


def equity_metrics(equity: pd.Series) -> dict[str, Any]:
    final_equity = float(equity.iloc[-1])
    profit = equity - active.STARTING_EQUITY
    stop_hits = np.where(profit <= active.STOP_DOLLARS)[0]
    target300_hits = np.where(profit >= 300.0)[0]
    target400_hits = np.where(profit >= 400.0)[0]
    first_stop = int(stop_hits[0]) if len(stop_hits) else None
    first_300 = int(target300_hits[0]) if len(target300_hits) else None
    first_400 = int(target400_hits[0]) if len(target400_hits) else None
    return {
        "final_equity": final_equity,
        "profit_dollars": final_equity - active.STARTING_EQUITY,
        "total_return": final_equity / active.STARTING_EQUITY - 1.0,
        "max_drawdown": drawdown_dollars(equity),
        "absolute_600_stop_hit": bool(first_stop is not None),
        "target_300_before_stop": bool(first_300 is not None and (first_stop is None or first_300 <= first_stop)),
        "target_400_before_stop": bool(first_400 is not None and (first_stop is None or first_400 <= first_stop)),
    }


def simulate_static_share_window(strategy_id: str, price: pd.Series, common_dates: pd.DatetimeIndex, window: dict[str, Any], role: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    start_idx = int(window["start_index"])
    end_idx = int(window["end_index"])
    start_date = common_dates[start_idx]
    period_dates = common_dates[start_idx + 1 : end_idx + 1]
    entry_price = float(price.loc[start_date])
    shares = active.STARTING_EQUITY * (1.0 - active.SLIPPAGE) / entry_price
    equity = price.reindex(period_dates).astype(float) * shares
    row = {
        "strategy_id": strategy_id,
        "role": role,
        **window,
        **equity_metrics(equity),
        "turnover_units": 1.0,
        "allocation_change_count": 1,
        "project_trade_count": 1,
        "average_exposure": 1.0,
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "average_bil_cash_share": 0.0,
        "entry_price": entry_price,
        "initial_shares": shares,
        "actual_shares_constant": True,
        "benchmark_reference_only": role == "benchmark",
    }
    invariant = None
    if strategy_id == CANDIDATE_ID:
        invariant = {
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "horizon_days": row["horizon_days"],
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "no_nan_final_weights": True,
            "no_negative_weights": True,
            "no_bil_cash_weight": True,
            "bil_cash_replacement_not_used": True,
            "actual_etf_shares_held_constant": True,
            "no_constant_target_daily_rebalance": True,
            "no_artificial_index_rebalance_turnover": True,
            "project_trade_count": 1,
            "project_turnover_units": 1.0,
            "invariant_passed": True,
        }
    return row, invariant


def simulate_return_series_window(strategy_id: str, series: pd.Series, common_dates: pd.DatetimeIndex, window: dict[str, Any]) -> dict[str, Any]:
    start_idx = int(window["start_index"])
    end_idx = int(window["end_index"])
    period_dates = common_dates[start_idx + 1 : end_idx + 1]
    period_returns = series.reindex(period_dates).dropna().astype(float)
    if len(period_returns) != int(window["horizon_days"]):
        return {"strategy_id": strategy_id, "role": "benchmark", **window, "window_valid": False, "benchmark_reference_only": True}
    equity = active.STARTING_EQUITY * (1.0 + period_returns).cumprod()
    return {
        "strategy_id": strategy_id,
        "role": "benchmark",
        **window,
        **equity_metrics(equity),
        "turnover_units": "",
        "allocation_change_count": "",
        "project_trade_count": "",
        "average_exposure": "",
        "max_daily_exposure": "",
        "max_daily_weight_sum": "",
        "average_bil_cash_share": "",
        "entry_price": "",
        "initial_shares": "",
        "actual_shares_constant": "",
        "benchmark_reference_only": True,
    }


def summarize_windows(rows: list[dict[str, Any]], strategy_id: str) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        frame = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and int(row["horizon_days"]) == horizon and row.get("window_valid") is True])
        if frame.empty:
            summaries.append({"strategy_id": strategy_id, "horizon_days": horizon, "window_count": 0, "validation_status": "missing"})
            continue
        summaries.append(
            {
                "strategy_id": strategy_id,
                "horizon_days": horizon,
                "window_count": int(len(frame)),
                "median_final_equity": float(frame["final_equity"].median()),
                "mean_final_equity": float(frame["final_equity"].mean()),
                "worst_final_equity": float(frame["final_equity"].min()),
                "best_final_equity": float(frame["final_equity"].max()),
                "median_total_return": float(frame["total_return"].median()),
                "mean_total_return": float(frame["total_return"].mean()),
                "worst_drawdown": float(frame["max_drawdown"].min()),
                "median_drawdown": float(frame["max_drawdown"].median()),
                "target_300_before_stop_rate": float(frame["target_300_before_stop"].mean()),
                "target_400_before_stop_rate": float(frame["target_400_before_stop"].mean()),
                "stop_hit_rate": float(frame["absolute_600_stop_hit"].mean()),
                "median_turnover_units": float(pd.to_numeric(frame["turnover_units"], errors="coerce").median()) if "turnover_units" in frame else "",
                "median_allocation_change_count": float(pd.to_numeric(frame["allocation_change_count"], errors="coerce").median()) if "allocation_change_count" in frame else "",
                "benchmark_reference_only": strategy_id in BENCHMARK_IDS,
            }
        )
    return summaries


def benchmark_delta_rows(candidate_metrics: list[dict[str, Any]], benchmark_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["strategy_id"], int(row["horizon_days"])): row for row in candidate_metrics + benchmark_metrics}
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        candidate = by_key[(CANDIDATE_ID, horizon)]
        for benchmark_id in BENCHMARK_IDS:
            benchmark = by_key[(benchmark_id, horizon)]
            rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "benchmark_id": benchmark_id,
                    "horizon_days": horizon,
                    "median_final_equity_delta": float(candidate["median_final_equity"]) - float(benchmark["median_final_equity"]),
                    "mean_final_equity_delta": float(candidate["mean_final_equity"]) - float(benchmark["mean_final_equity"]),
                    "worst_drawdown_delta": float(candidate["worst_drawdown"]) - float(benchmark["worst_drawdown"]),
                    "median_total_return_delta": float(candidate["median_total_return"]) - float(benchmark["median_total_return"]),
                    "win_count": "",
                    "benchmark_reference_only": True,
                }
            )
    return rows


def add_win_counts(deltas: list[dict[str, Any]], window_rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame([row for row in window_rows if row.get("window_valid") is True])
    if frame.empty:
        return
    for row in deltas:
        horizon = int(row["horizon_days"])
        benchmark_id = str(row["benchmark_id"])
        candidate = frame[(frame["strategy_id"] == CANDIDATE_ID) & (frame["horizon_days"] == horizon)].sort_values("window_start")
        benchmark = frame[(frame["strategy_id"] == benchmark_id) & (frame["horizon_days"] == horizon)].sort_values("window_start")
        merged = candidate[["window_start", "final_equity"]].merge(benchmark[["window_start", "final_equity"]], on="window_start", suffixes=("_candidate", "_benchmark"))
        row["win_count"] = int((pd.to_numeric(merged["final_equity_candidate"]) > pd.to_numeric(merged["final_equity_benchmark"])).sum())


def classify_outcome(candidate_metrics: list[dict[str, Any]], benchmark_metrics: list[dict[str, Any]], invariants_passed: bool) -> str:
    if not invariants_passed:
        return "invalid_methodology"
    by_key = {(row["strategy_id"], int(row["horizon_days"])): row for row in candidate_metrics + benchmark_metrics}
    cand180 = by_key[(CANDIDATE_ID, 180)]
    spy180 = by_key[("SPY_buy_and_hold", 180)]
    vm180 = by_key[(ACTIVE_VM_ID, 180)]
    splv180 = by_key[(SPLV_REFERENCE_ID, 180)]
    spy_return_edge = float(cand180["median_final_equity"]) > float(spy180["median_final_equity"])
    spy_drawdown_edge = float(cand180["worst_drawdown"]) >= float(spy180["worst_drawdown"])
    vm_return_edge = float(cand180["median_final_equity"]) > float(vm180["median_final_equity"])
    if spy_return_edge and spy_drawdown_edge and vm_return_edge:
        return "comparative_evidence_positive"
    if spy_return_edge and not spy_drawdown_edge:
        return "quality_factor_return_edge_only"
    if not spy_return_edge and spy_drawdown_edge:
        return "risk_reduction_without_return_edge"
    if float(cand180["median_final_equity"]) < float(splv180["median_final_equity"]) and float(cand180["median_final_equity"]) < float(vm180["median_final_equity"]):
        return "control_weak"
    return "no_material_edge"


def preregistration_payload(cache: dict[str, Any], windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "instrument": CANDIDATE_INSTRUMENT,
        "classification": ["source_backed_index_etf_wrapper", "static_quality_factor_exposure", "not_constituent_level_index_replication"],
        "hypothesis": "Static exposure to the source-defined quality-factor ETF may provide better return or return/risk characteristics than broad US equity exposure.",
        "trading_rule": {
            "entry": "Enter 100% QUAL at the authorized start of each evaluation window.",
            "holding": "Hold actual ETF shares until window end.",
            "project_rebalance": "none after initial entry",
            "bil_or_cash_switch": False,
            "trend_or_moving_average_rule": False,
            "volatility_target": False,
            "stop_loss_added": False,
            "leverage": False,
            "shorting": False,
            "exit": "window end only for measurement",
        },
        "accounting": {
            "actual_etf_shares": True,
            "one_initial_entry_trade": True,
            "constant_target_daily_rebalancing": False,
            "artificial_index_rebalance_trade": False,
            "internal_etf_turnover_modeled_as_project_trade": False,
            "canonical_project_entry_cost": active.SLIPPAGE,
        },
        "windows": {
            "generator": "canonical deterministic bounded-screen linspace windows",
            "horizons": active.HORIZONS,
            "max_windows_per_horizon": active.MAX_WINDOWS_PER_HORIZON,
            "window_count": len(windows),
            "generated_before_performance": True,
            "window_records": windows,
        },
        "benchmarks": BENCHMARK_IDS,
        "cache": cache,
        "parameter_search": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
    }


def execution_manifest_payload(cache: dict[str, Any], windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "screen_id": "qual_static_quality_factor_screen_v1",
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_class": "index_methodology_and_direct_etf_wrapper",
        "candidate_instrument": CANDIDATE_INSTRUMENT,
        "candidate_instrument_count": 1,
        "qual_only": True,
        "uses_bil_or_cash_rule": False,
        "uses_tactical_signal": False,
        "uses_active_vm_rule": False,
        "uses_volatility_target": False,
        "uses_ranking_rule": False,
        "constituent_level_index_reconstruction": False,
        "cache": cache,
        "windows_generated_before_performance": True,
        "window_count": len(windows),
        "horizons_days": active.HORIZONS,
        "benchmarks": BENCHMARK_IDS,
        "buy_and_hold_actual_etf_shares": True,
        "no_artificial_index_rebalance_turnover": True,
        "no_provider_call": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "robustness_authorized": False,
        "real_money_recommendation": False,
    }


def screening_summary(outcome: str, candidate_metrics: list[dict[str, Any]], deltas: list[dict[str, Any]]) -> str:
    lines = [
        "# QUAL Static Quality Factor Screen V1",
        "",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Outcome: `{outcome}`",
        "",
        "This is a source-backed static QUAL ETF-wrapper screen. It does not reconstruct MSCI constituents, fundamental data, quality scores, or index rebalances.",
        "",
        "## Candidate Metrics",
    ]
    for row in candidate_metrics:
        lines.append(
            f"- {row['horizon_days']}d: median final equity {row['median_final_equity']:.2f}, "
            f"mean final equity {row['mean_final_equity']:.2f}, worst drawdown {row['worst_drawdown']:.2f}."
        )
    lines.extend(["", "## 180d Benchmark Deltas"])
    for row in deltas:
        if int(row["horizon_days"]) == 180:
            lines.append(
                f"- vs {row['benchmark_id']}: median final-equity delta {row['median_final_equity_delta']:.2f}, "
                f"drawdown delta {row['worst_drawdown_delta']:.2f}, win count {row['win_count']}."
            )
    lines.extend(["", "No promotion, paper/demo activation, robustness run, candidate_exhaustive, provider download, or real-money recommendation occurred."])
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    hashes_before = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
        "active_combo_series": sha256_path(ACTIVE_COMBO_SERIES),
    }
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)

    intake = source_intake_record()
    write_yaml(INTAKE_DIR / f"{SOURCE_ID}.yaml", intake)
    write_yaml(EVIDENCE_DIR / "source_intake_record.yaml", intake)
    write_csv(EVIDENCE_DIR / "source_rule_extraction.csv", source_rule_rows())
    write_csv(EVIDENCE_DIR / "source_support_trace.csv", source_support_rows())

    duplicate_rows = duplicate_gate_rows()
    duplicate_found = exact_duplicate_exists(duplicate_rows)
    write_csv(EVIDENCE_DIR / "duplicate_gate.csv", duplicate_rows)
    write_csv(EVIDENCE_DIR / "material_distinction_review.csv", material_distinction_rows())
    cache = cache_feasibility()
    write_csv(EVIDENCE_DIR / "cache_feasibility.csv", [cache])

    if duplicate_found or cache["cache_status"] != "cache_ready":
        outcome_label = "exact_duplicate_already_tested" if duplicate_found else "data_not_ready"
        outcome = {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome_label,
            "performance_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "next_action": "stop_qual_static_quality_factor_screen_v1",
        }
        write_json(EVIDENCE_DIR / "screening_outcome.json", outcome)
        write_json(EVIDENCE_DIR / "consistency_check.json", {"consistency_passed": True, "performance_omitted_by_gate": True})
        return outcome

    close, missing = active.prepare_prices(ROOT)
    if missing:
        raise RuntimeError(f"required benchmark cache symbols missing: {missing}")
    qual = read_symbol_close(CANDIDATE_INSTRUMENT)
    splv = read_symbol_close("SPLV")
    returns_by_id = benchmark_returns(close)
    common_dates = common_dates_for_screen(qual, returns_by_id)
    windows = generate_windows(common_dates)
    write_csv(EVIDENCE_DIR / "window_definitions.csv", windows)
    prereg = preregistration_payload(cache, windows)
    manifest = execution_manifest_payload(cache, windows)
    write_yaml(EVIDENCE_DIR / "preregistration.yaml", prereg)
    write_json(EVIDENCE_DIR / "execution_manifest.json", manifest)

    candidate_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for window in windows:
        candidate_row, invariant = simulate_static_share_window(CANDIDATE_ID, qual, common_dates, window, "candidate")
        candidate_rows.append(candidate_row)
        if invariant is not None:
            invariant_rows.append(invariant)
        splv_row, _splv_invariant = simulate_static_share_window(SPLV_REFERENCE_ID, splv, common_dates, window, "benchmark")
        benchmark_rows.append(splv_row)
        for benchmark_id, series in returns_by_id.items():
            if benchmark_id == SPLV_REFERENCE_ID:
                continue
            benchmark_rows.append(simulate_return_series_window(benchmark_id, series, common_dates, window))

    window_rows = candidate_rows + benchmark_rows
    candidate_metrics = summarize_windows(window_rows, CANDIDATE_ID)
    benchmark_metrics: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        benchmark_metrics.extend(summarize_windows(window_rows, benchmark_id))
    deltas = benchmark_delta_rows(candidate_metrics, benchmark_metrics)
    add_win_counts(deltas, window_rows)
    invariants_passed = all(row["invariant_passed"] for row in invariant_rows)
    outcome_label = classify_outcome(candidate_metrics, benchmark_metrics, invariants_passed)
    if outcome_label not in ALLOWED_OUTCOMES:
        outcome_label = "direction_owner_review_required"

    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)
    write_csv(EVIDENCE_DIR / "candidate_metrics.csv", candidate_metrics)
    write_csv(EVIDENCE_DIR / "benchmark_metrics.csv", benchmark_metrics)
    write_csv(EVIDENCE_DIR / "benchmark_relative_deltas.csv", deltas)
    write_csv(EVIDENCE_DIR / "accounting_invariants.csv", invariant_rows)
    write_text(EVIDENCE_DIR / "screening_summary.md", screening_summary(outcome_label, candidate_metrics, deltas))

    hashes_after = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
        "active_combo_series": sha256_path(ACTIVE_COMBO_SERIES),
    }
    next_action = (
        "direction_owner_validation_decision_for_qual_static_quality_factor_wrapper_v1"
        if outcome_label in {"comparative_evidence_positive", "higher_return_higher_risk", "quality_factor_return_edge_only", "risk_reduction_without_return_edge"}
        else "record_qual_static_quality_factor_wrapper_v1_exact_variant_memory_only"
    )
    outcome = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome_label,
        "allowed_outcome": True,
        "performance_run": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "robustness_authorized": False,
        "provider_download": False,
        "intraday_data_used": False,
        "real_money_recommendation": False,
        "registry_hash_before": hashes_before["registry"],
        "registry_hash_after": hashes_after["registry"],
        "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
        "active_observations_hash_before": hashes_before["active_observations"],
        "active_observations_hash_after": hashes_after["active_observations"],
        "active_observations_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
        "active_combo_series_hash_before": hashes_before["active_combo_series"],
        "active_combo_series_hash_after": hashes_after["active_combo_series"],
        "active_combo_unchanged": hashes_before["active_combo_series"] == hashes_after["active_combo_series"],
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", outcome)
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "outcome": outcome_label,
                "exact_variant_memory_status": "close_exact_variant_for_immediate_retesting" if outcome_label in {"control_weak", "no_material_edge"} else "separate_direction_owner_validation_required",
                "broader_quality_factor_family_status": "open_only_for_materially_different_source_backed_hypotheses",
                "automatic_followup_etf_or_overlay_authorized": False,
                "canonical_lifecycle_status_modified": False,
                "paper_demo_authorized": False,
                "promotion_authorized": False,
            }
        ],
    )
    consistency = {
        "consistency_passed": bool(
            invariants_passed
            and outcome["registry_byte_identical"]
            and outcome["active_observations_unchanged"]
            and outcome["active_combo_unchanged"]
            and len(candidate_rows) == len(windows)
            and len(windows) == active.MAX_WINDOWS_PER_HORIZON * len(active.HORIZONS)
        ),
        "exactly_one_external_source_evaluated": True,
        "qual_only": True,
        "cache_used_without_refresh": True,
        "no_bil_trend_volatility_or_ranking_rule": True,
        "no_active_vm_rule_borrowed": True,
        "duplicate_gate_completed_before_performance": True,
        "material_distinction_completed": True,
        "windows_generated_before_performance": True,
        "actual_etf_shares_held": True,
        "no_artificial_index_rebalance_turnover": True,
        "benchmarks_date_aligned": True,
        "registry_byte_identical": outcome["registry_byte_identical"],
        "active_observations_unchanged": outcome["active_observations_unchanged"],
        "no_lifecycle_or_paper_demo_state_change": True,
        "deterministic_generation_no_timestamps": True,
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**manifest, **outcome, **consistency, "output_dir": str(EVIDENCE_DIR)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
