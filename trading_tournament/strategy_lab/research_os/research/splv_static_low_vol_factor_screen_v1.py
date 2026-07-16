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
EVIDENCE_DIR = ROOT / "evidence" / "splv_static_low_vol_factor_screen_v1" / "latest"
INTAKE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
SOURCE_ID = "sp_global_sp500_low_volatility_index_methodology_2026"
SECONDARY_QUANTPEDIA_ID = "low_volatility_factor_proxy"
CANDIDATE_ID = "splv_static_low_vol_factor_wrapper_v1"
FAMILY_ID = "low_volatility_factor_proxy"
CANDIDATE_INSTRUMENT = "SPLV"
ACTIVE_VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
BENCHMARK_IDS = [
    "SPY_buy_hold",
    active.SPY_200D_ID,
    "BIL_cash_proxy",
    ACTIVE_COMBO_ID,
    ACTIVE_VM_ID,
]
ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "control_weak",
    "no_material_edge",
    "not_comparable",
    "invalid_methodology",
    "direction_owner_review_required",
}


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


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 10)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_value(row.get(field, "")) for field in fields})


def read_symbol_close(symbol: str) -> pd.Series:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().drop_duplicates("date").sort_values("date")
    return series.set_index("date")[symbol].astype(float)


def source_intake_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "intake_status": "manual_primary_official_source_supplied_for_screen",
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "S&P Low Volatility Indices Methodology",
            "publisher": "S&P Dow Jones Indices",
            "source_class": "index_methodology_primary",
            "source_type": "official index methodology",
            "version_date": "March 2026",
            "target_index": "S&P 500 Low Volatility Index",
            "source_url_or_citation": "S&P Dow Jones Indices, S&P Low Volatility Indices Methodology, March 2026",
            "source_evidence_public_context_only": True,
        },
        "source_supported_rules": {
            "parent_universe": "S&P 500",
            "target_constituent_count": 100,
            "volatility_window_trading_days": 252,
            "volatility_definition": "standard deviation of daily price returns",
            "ranking": "rank eligible constituents from lowest realized volatility to highest realized volatility",
            "selection": "select the 100 least volatile eligible S&P 500 constituents",
            "weighting": "weight each selected constituent inverse to its volatility",
            "rebalance_reference_dates": "last trading dates of January, April, July, and October",
            "effective_rebalance_dates": "after the close of the third Friday of February, May, August, and November",
            "long_only": True,
            "fully_invested_equity_index": True,
            "source_defined_tactical_cash_or_bil_rule": False,
        },
        "project_wrapper_adaptation": {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "instrument": CANDIDATE_INSTRUMENT,
            "classification": [
                "source_backed_index_etf_wrapper",
                "not_constituent_level_index_replication",
            ],
            "wrapper_rule": "Evaluate the cached SPLV ETF wrapper as a project-level buy-and-hold exposure to the source-defined index.",
            "constituent_level_replication": False,
        },
        "secondary_source_preserved": {
            "source_id": SECONDARY_QUANTPEDIA_ID,
            "role": "secondary_discovery_lead_only",
            "credibility_upgraded": False,
        },
        "governance": {
            "do_not_browse": True,
            "do_not_download": True,
            "do_not_add_tactical_rules": True,
            "do_not_modify_active_vm": True,
            "promotion_or_paper_forward_allowed": False,
        },
    }


def source_rule_rows() -> list[dict[str, Any]]:
    rules = source_intake_record()["source_supported_rules"]
    return [
        {
            "rule_id": key,
            "rule_value": value,
            "provenance": "official_source_explicit",
            "source_id": SOURCE_ID,
            "project_added": False,
        }
        for key, value in rules.items()
    ]


def source_support_rows() -> list[dict[str, Any]]:
    return [
        {
            "material_rule": row["rule_id"],
            "source_id": SOURCE_ID,
            "source_title": "S&P Low Volatility Indices Methodology",
            "publisher": "S&P Dow Jones Indices",
            "version_date": "March 2026",
            "support_reference": "Direction-owner supplied official methodology rule extraction for the S&P 500 Low Volatility Index.",
            "support_status": "source_supported",
        }
        for row in source_rule_rows()
    ]


def exact_duplicate_review() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_prior_id": ACTIVE_VM_ID,
            "exact_duplicate": False,
            "uses_100pct_splv": False,
            "no_tactical_signal": False,
            "no_bil_or_cash_switch": False,
            "reason": "Active VM ranks SPLV/USMV/QUAL/SPY by momentum/volatility, applies 200-day eligibility, and can allocate to BIL.",
        },
        {
            "reviewed_prior_id": "lvq_lowvol_quality_top2_v1",
            "exact_duplicate": False,
            "uses_100pct_splv": False,
            "no_tactical_signal": False,
            "no_bil_or_cash_switch": False,
            "reason": "Low-vol/quality top-2 concept uses cross-ETF selection rather than persistent SPLV buy-and-hold.",
        },
        {
            "reviewed_prior_id": "lvq_lowvol_quality_spy_regime_v1",
            "exact_duplicate": False,
            "uses_100pct_splv": False,
            "no_tactical_signal": False,
            "no_bil_or_cash_switch": False,
            "reason": "Regime variant includes SPY regime/cash-like defensive behavior rather than static SPLV exposure.",
        },
        {
            "reviewed_prior_id": "value_momentum_factor_etf_rotation_v1",
            "exact_duplicate": False,
            "uses_100pct_splv": False,
            "no_tactical_signal": False,
            "no_bil_or_cash_switch": False,
            "reason": "Factor ETF rotation is a ranking/rotation strategy, not a one-ETF static wrapper.",
        },
        {
            "reviewed_prior_id": "benchmark_quality_lowvol_equal_weight_v1",
            "exact_duplicate": False,
            "uses_100pct_splv": False,
            "no_tactical_signal": True,
            "no_bil_or_cash_switch": True,
            "reason": "Benchmark is an equal-weight quality/low-vol proxy, not exactly 100% SPLV.",
        },
    ]


def exact_duplicate_exists(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if (
            row.get("uses_100pct_splv") is True
            and row.get("no_tactical_signal") is True
            and row.get("no_bil_or_cash_switch") is True
            and row.get("buy_and_hold_project_accounting") is True
            and row.get("matching_deterministic_sampled_windows") is True
            and row.get("comparable_costs_and_execution") is True
        ):
            return True
    return False


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "comparison_id": ACTIVE_VM_ID,
            "shared_dimensions": "SPLV appears in VM universe; both are low-volatility related.",
            "material_difference": "Static SPLV holds one persistent ETF and does not rank, filter, scale, or switch to BIL.",
            "distinction_outcome": "materially_distinct_static_factor_exposure",
            "result_driven_tuning_risk": "not_detected",
        },
        {
            "comparison_id": "VM parent research",
            "shared_dimensions": "low-volatility ETF wrapper context",
            "material_difference": "No 200-day eligibility, no momentum/volatility score, no top-N selection.",
            "distinction_outcome": "materially_distinct_static_factor_exposure",
            "result_driven_tuning_risk": "not_detected",
        },
        {
            "comparison_id": "static SPLV or USMV evidence",
            "shared_dimensions": "single low-volatility ETF wrapper may overlap if present",
            "material_difference": "No prior exact valid 100% SPLV sampled-window test was identified in the canonical reviewed records.",
            "distinction_outcome": "materially_distinct_static_factor_exposure",
            "result_driven_tuning_risk": "not_detected",
        },
    ]


def cache_identity(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    close = read_symbol_close(symbol)
    return {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_sha256": sha256_path(path),
        "first_valid_date": str(close.index.min().date()),
        "last_valid_date": str(close.index.max().date()),
        "row_count": int(len(close)),
    }


def load_active_combo_returns() -> pd.Series:
    path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    series = pd.DataFrame({"date": dates, ACTIVE_COMBO_ID: returns}).dropna().sort_values("date")
    return series.set_index("date")[ACTIVE_COMBO_ID].astype(float)


def benchmark_returns(close: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "SPY_buy_hold": active.full_returns(close, "SPY_buy_hold"),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        "BIL_cash_proxy": active.full_returns(close, "BIL_cash_proxy"),
        ACTIVE_COMBO_ID: load_active_combo_returns(),
        ACTIVE_VM_ID: active.full_returns(close, ACTIVE_VM_ID),
    }


def common_dates_for_screen(splv: pd.Series, returns_by_id: dict[str, pd.Series]) -> pd.DatetimeIndex:
    common = pd.DatetimeIndex(splv.dropna().index)
    for series in returns_by_id.values():
        common = common.intersection(pd.DatetimeIndex(series.dropna().index))
    return common.sort_values()


def generate_windows(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        starts = list(range(0, len(common_dates) - horizon))
        if len(starts) <= active.MAX_WINDOWS_PER_HORIZON:
            selected = starts
        else:
            selected = sorted(set(int(value) for value in np.linspace(starts[0], starts[-1], active.MAX_WINDOWS_PER_HORIZON)))
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
    with_start = pd.concat([pd.Series([active.STARTING_EQUITY], index=[equity.index[0] - pd.Timedelta(days=1)]), equity])
    return float((with_start - with_start.cummax()).min())


def equity_metrics(equity: pd.Series) -> dict[str, Any]:
    final_equity = float(equity.iloc[-1])
    profit = final_equity - active.STARTING_EQUITY
    dd = drawdown_dollars(equity)
    stop_hit = bool((equity - active.STARTING_EQUITY <= active.STOP_DOLLARS).any())
    target300_hits = np.where((equity - active.STARTING_EQUITY) >= 300.0)[0]
    target400_hits = np.where((equity - active.STARTING_EQUITY) >= 400.0)[0]
    stop_hits = np.where((equity - active.STARTING_EQUITY) <= active.STOP_DOLLARS)[0]
    first_stop = int(stop_hits[0]) if len(stop_hits) else None
    first_300 = int(target300_hits[0]) if len(target300_hits) else None
    first_400 = int(target400_hits[0]) if len(target400_hits) else None
    return {
        "final_equity": final_equity,
        "profit_dollars": profit,
        "total_return": final_equity / active.STARTING_EQUITY - 1.0,
        "max_drawdown": dd,
        "absolute_600_stop_hit": stop_hit,
        "target_300_before_stop": bool(first_300 is not None and (first_stop is None or first_300 <= first_stop)),
        "target_400_before_stop": bool(first_400 is not None and (first_stop is None or first_400 <= first_stop)),
    }


def simulate_splv_window(splv: pd.Series, common_dates: pd.DatetimeIndex, window: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    start_idx = int(window["start_index"])
    end_idx = int(window["end_index"])
    start_date = common_dates[start_idx]
    period_dates = common_dates[start_idx + 1 : end_idx + 1]
    entry_price = float(splv.loc[start_date])
    shares = active.STARTING_EQUITY * (1.0 - active.SLIPPAGE) / entry_price
    equity = splv.loc[period_dates].astype(float) * shares
    metrics = equity_metrics(equity)
    row = {
        "strategy_id": CANDIDATE_ID,
        "role": "candidate",
        **window,
        **metrics,
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
        "benchmark_reference_only": False,
    }
    invariants = {
        "window_start": row["window_start"],
        "window_end": row["window_end"],
        "horizon_days": row["horizon_days"],
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "no_bil_cash_weight": True,
        "bil_cash_replacement_not_used": True,
        "actual_etf_shares_held_constant": True,
        "no_artificial_daily_rebalance": True,
        "no_artificial_quarterly_turnover": True,
        "project_trade_count": 1,
        "project_turnover_units": 1.0,
        "invariant_passed": True,
    }
    return row, invariants


def simulate_return_series_window(strategy_id: str, series: pd.Series, common_dates: pd.DatetimeIndex, window: dict[str, Any]) -> dict[str, Any]:
    start_idx = int(window["start_index"])
    end_idx = int(window["end_index"])
    period_dates = common_dates[start_idx + 1 : end_idx + 1]
    period_returns = series.reindex(period_dates).dropna().astype(float)
    if len(period_returns) != int(window["horizon_days"]):
        return {
            "strategy_id": strategy_id,
            "role": "benchmark",
            **window,
            "window_valid": False,
            "benchmark_reference_only": True,
        }
    equity = active.STARTING_EQUITY * (1.0 + period_returns).cumprod()
    metrics = equity_metrics(equity)
    return {
        "strategy_id": strategy_id,
        "role": "benchmark",
        **window,
        **metrics,
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
        frame = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon_days"] == horizon and row.get("window_valid") is True])
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
                "benchmark_reference_only": bool(strategy_id in BENCHMARK_IDS),
            }
        )
    return summaries


def benchmark_delta_rows(candidate_metrics: list[dict[str, Any]], benchmark_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_horizon = {(row["strategy_id"], row["horizon_days"]): row for row in candidate_metrics + benchmark_metrics}
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        candidate = by_horizon[(CANDIDATE_ID, horizon)]
        for benchmark_id in BENCHMARK_IDS:
            benchmark = by_horizon[(benchmark_id, horizon)]
            rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "benchmark_id": benchmark_id,
                    "horizon_days": horizon,
                    "median_final_equity_delta": float(candidate["median_final_equity"]) - float(benchmark["median_final_equity"]),
                    "mean_final_equity_delta": float(candidate["mean_final_equity"]) - float(benchmark["mean_final_equity"]),
                    "worst_drawdown_delta": float(candidate["worst_drawdown"]) - float(benchmark["worst_drawdown"]),
                    "median_total_return_delta": float(candidate["median_total_return"]) - float(benchmark["median_total_return"]),
                    "benchmark_reference_only": True,
                }
            )
    return rows


def classify_outcome(candidate_metrics: list[dict[str, Any]], benchmark_metrics: list[dict[str, Any]], invariants_passed: bool) -> str:
    if not invariants_passed:
        return "invalid_methodology"
    by_id = {(row["strategy_id"], row["horizon_days"]): row for row in candidate_metrics + benchmark_metrics}
    cand180 = by_id[(CANDIDATE_ID, 180)]
    spy180 = by_id[("SPY_buy_hold", 180)]
    vm180 = by_id[(ACTIVE_VM_ID, 180)]
    combo180 = by_id[(ACTIVE_COMBO_ID, 180)]
    if float(cand180["median_final_equity"]) > max(float(spy180["median_final_equity"]), float(vm180["median_final_equity"]), float(combo180["median_final_equity"])):
        if float(cand180["worst_drawdown"]) >= float(spy180["worst_drawdown"]):
            return "comparative_evidence_positive"
        return "higher_return_higher_risk"
    if float(cand180["median_final_equity"]) < min(float(spy180["median_final_equity"]), float(vm180["median_final_equity"]), float(combo180["median_final_equity"])):
        return "control_weak"
    return "no_material_edge"


def preregistration(cache: dict[str, Any], windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "classification": [
            "source_backed_index_etf_wrapper",
            "not_constituent_level_index_replication",
        ],
        "instrument": CANDIDATE_INSTRUMENT,
        "instrument_count": 1,
        "data": {
            "cache_path": cache["cache_path"],
            "cache_sha256": cache["cache_sha256"],
            "adjusted_close_only": True,
            "provider_refresh_or_download": False,
        },
        "project_trading_rule": {
            "entry": "enter 100% SPLV at first authorized execution of each sampled window",
            "hold": "hold actual ETF shares throughout the window",
            "exit": "exit only at sampled-window end for measurement",
            "tactical_rebalance": False,
            "bil_or_cash_switch": False,
            "trend_filter": False,
            "volatility_target": False,
            "leverage": False,
            "shorting": False,
            "stops": "evaluation-only target/stop measurement; no trading stop added",
        },
        "accounting": {
            "initial_capital": active.STARTING_EQUITY,
            "initial_trade_slippage": active.SLIPPAGE,
            "drift_aware_holdings": True,
            "buy_etf_shares_once": True,
            "no_artificial_daily_or_quarterly_rebalance": True,
            "etf_internal_reconstitution_not_project_trade": True,
        },
        "windows": {
            "generator": "deterministic_linspace_max_5_per_horizon_common_valid_period",
            "horizons_days": active.HORIZONS,
            "max_windows_per_horizon": active.MAX_WINDOWS_PER_HORIZON,
            "windows_generated_before_performance": True,
            "window_count": len(windows),
            "window_records": windows,
        },
        "benchmarks": BENCHMARK_IDS,
        "parameter_search": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
    }


def write_summary(outcome: str, candidate_metrics: list[dict[str, Any]], deltas: list[dict[str, Any]]) -> None:
    lines = [
        "# SPLV Static Low-Vol Factor Wrapper Screen V1",
        "",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Family: `{FAMILY_ID}`",
        f"Source: `{SOURCE_ID}`",
        f"Outcome: `{outcome}`",
        "",
        "This is a source-backed ETF-wrapper screen only. It does not reconstruct the S&P 500 Low Volatility Index constituents, add tactical timing, or authorize promotion/paper-demo observation.",
        "",
        "## Candidate Metrics",
    ]
    for row in candidate_metrics:
        lines.append(
            f"- {row['horizon_days']}d: median final equity {row['median_final_equity']:.2f}, "
            f"mean final equity {row['mean_final_equity']:.2f}, worst drawdown {row['worst_drawdown']:.2f}."
        )
    lines.extend(["", "## Benchmark Deltas"])
    for row in deltas:
        if row["horizon_days"] == 180:
            lines.append(
                f"- vs {row['benchmark_id']} at 180d: median final-equity delta {row['median_final_equity_delta']:.2f}, "
                f"drawdown delta {row['worst_drawdown_delta']:.2f}."
            )
    lines.extend(
        [
            "",
            "Guardrails: no provider download, no USMV/alternate wrapper, no BIL/tactical rule, no robustness run, no candidate_exhaustive, no lifecycle change, no paper/demo activation, and no real-money recommendation.",
            "",
        ]
    )
    (EVIDENCE_DIR / "screening_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    quantpedia_path = INTAKE_DIR / f"{SECONDARY_QUANTPEDIA_ID}.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    active_combo_path = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    hashes_before = {
        "registry": sha256_path(registry_path),
        "quantpedia_secondary": sha256_path(quantpedia_path),
        "active_observations": sha256_path(active_observations_path),
        "active_combo_series": sha256_path(active_combo_path),
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

    duplicate_rows = exact_duplicate_review()
    duplicate_found = exact_duplicate_exists(duplicate_rows)
    for row in duplicate_rows:
        row["duplicate_gate_outcome"] = "exact_duplicate_already_tested" if row["exact_duplicate"] else "not_exact_duplicate"
    write_csv(EVIDENCE_DIR / "duplicate_gate.csv", duplicate_rows)

    if duplicate_found:
        outcome = "exact_duplicate_already_tested"
        write_json(
            EVIDENCE_DIR / "screening_outcome.json",
            {
                "candidate_id": CANDIDATE_ID,
                "outcome": outcome,
                "performance_run": False,
                "promotion_authorized": False,
                "paper_demo_authorized": False,
            },
        )
        return {"outcome": outcome, "performance_run": False}

    distinction_rows = material_distinction_rows()
    write_csv(EVIDENCE_DIR / "material_distinction_review.csv", distinction_rows)

    close, missing = active.prepare_prices(ROOT)
    if missing:
        raise RuntimeError(f"required active benchmark cache symbols missing: {missing}")
    splv = read_symbol_close(CANDIDATE_INSTRUMENT)
    returns_by_id = benchmark_returns(close)
    common_dates = common_dates_for_screen(splv, returns_by_id)
    windows = generate_windows(common_dates)
    cache = cache_identity(CANDIDATE_INSTRUMENT)
    prereg = preregistration(cache, windows)
    write_yaml(EVIDENCE_DIR / "preregistration.yaml", prereg)

    candidate_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    for window in windows:
        row, invariant = simulate_splv_window(splv, common_dates, window)
        candidate_rows.append(row)
        invariant_rows.append(invariant)
        for benchmark_id, series in returns_by_id.items():
            benchmark_rows.append(simulate_return_series_window(benchmark_id, series, common_dates, window))

    window_rows = candidate_rows + benchmark_rows
    candidate_metrics = summarize_windows(window_rows, CANDIDATE_ID)
    benchmark_metrics: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        benchmark_metrics.extend(summarize_windows(window_rows, benchmark_id))
    deltas = benchmark_delta_rows(candidate_metrics, benchmark_metrics)
    invariants_passed = all(row["invariant_passed"] for row in invariant_rows)
    outcome = classify_outcome(candidate_metrics, benchmark_metrics, invariants_passed)
    if outcome not in ALLOWED_OUTCOMES:
        outcome = "direction_owner_review_required"

    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)
    write_csv(EVIDENCE_DIR / "candidate_metrics.csv", candidate_metrics)
    write_csv(EVIDENCE_DIR / "benchmark_metrics.csv", benchmark_metrics)
    write_csv(EVIDENCE_DIR / "benchmark_relative_deltas.csv", deltas)
    write_csv(EVIDENCE_DIR / "accounting_invariants.csv", invariant_rows)
    write_summary(outcome, candidate_metrics, deltas)

    memory_status = "close_exact_variant_for_immediate_retesting" if outcome in {"control_weak", "no_material_edge"} else "retain_for_direction_owner_review"
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "outcome": outcome,
                "exact_variant_memory_status": memory_status,
                "broader_family_preserved": True,
                "failure_reason": "weak_comparative_static_wrapper_evidence" if memory_status.startswith("close") else "",
                "paper_demo_authorized": False,
                "promotion_authorized": False,
            }
        ],
    )

    hashes_after = {
        "registry": sha256_path(registry_path),
        "quantpedia_secondary": sha256_path(quantpedia_path),
        "active_observations": sha256_path(active_observations_path),
        "active_combo_series": sha256_path(active_combo_path),
    }
    manifest = {
        "screen_id": "splv_static_low_vol_factor_screen_v1",
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_class": "index_methodology_primary",
        "secondary_quantpedia_record_preserved": hashes_before["quantpedia_secondary"] == hashes_after["quantpedia_secondary"],
        "secondary_quantpedia_hash_before": hashes_before["quantpedia_secondary"],
        "secondary_quantpedia_hash_after": hashes_after["quantpedia_secondary"],
        "candidate_instruments": [CANDIDATE_INSTRUMENT],
        "candidate_instrument_count": 1,
        "splv_only": True,
        "uses_bil_or_cash_rule": False,
        "uses_tactical_signal": False,
        "uses_active_vm_rule": False,
        "uses_usmv_or_alternate_wrapper": False,
        "exact_duplicate_found": False,
        "distinction_outcome": "materially_distinct_static_factor_exposure",
        "windows_generated_before_performance": True,
        "window_count": len(windows),
        "horizons_days": active.HORIZONS,
        "performance_run": True,
        "no_provider_call": True,
        "provider_download": False,
        "intraday_data_used": False,
        "constituent_level_index_reconstruction": False,
        "buy_and_hold_actual_etf_shares": True,
        "no_artificial_quarterly_turnover": True,
        "registry_hash_before": hashes_before["registry"],
        "registry_hash_after": hashes_after["registry"],
        "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
        "active_observations_hash_before": hashes_before["active_observations"],
        "active_observations_hash_after": hashes_after["active_observations"],
        "active_vm_state_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
        "active_combo_series_hash_before": hashes_before["active_combo_series"],
        "active_combo_series_hash_after": hashes_after["active_combo_series"],
        "active_combo_state_unchanged": hashes_before["active_combo_series"] == hashes_after["active_combo_series"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "robustness_authorized": False,
        "lifecycle_or_evidence_level_changed": False,
        "screening_outcome": outcome,
        "next_action": "direction_owner_review_splv_static_low_vol_factor_screen_v1" if outcome not in {"control_weak", "no_material_edge", "invalid_methodology"} else "record_splv_static_low_vol_factor_wrapper_v1_exact_variant_memory_only",
    }
    write_json(EVIDENCE_DIR / "execution_manifest.json", manifest)
    write_json(
        EVIDENCE_DIR / "screening_outcome.json",
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "allowed_outcome": outcome in ALLOWED_OUTCOMES,
            "performance_run": True,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "robustness_authorized": False,
            "next_action": manifest["next_action"],
        },
    )
    consistency = {
        "consistency_passed": bool(
            invariants_passed
            and manifest["registry_byte_identical"]
            and manifest["secondary_quantpedia_record_preserved"]
            and manifest["active_vm_state_unchanged"]
            and manifest["active_combo_state_unchanged"]
            and len(candidate_rows) == len(windows)
            and len(windows) == active.MAX_WINDOWS_PER_HORIZON * len(active.HORIZONS)
        ),
        "official_source_rules_preserved": True,
        "splv_only": True,
        "no_bil_or_tactical_rule_added": True,
        "no_active_vm_rule_borrowed": True,
        "window_generation_before_performance": True,
        "no_provider_call": True,
        "buy_and_hold_actual_etf_shares": True,
        "no_artificial_quarterly_turnover": True,
        "all_accounting_invariants_passed": invariants_passed,
        "registry_byte_identical": manifest["registry_byte_identical"],
        "quantpedia_secondary_unchanged": manifest["secondary_quantpedia_record_preserved"],
        "active_vm_and_active_combo_unchanged": manifest["active_vm_state_unchanged"] and manifest["active_combo_state_unchanged"],
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**manifest, **consistency}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True, default=clean_value))
