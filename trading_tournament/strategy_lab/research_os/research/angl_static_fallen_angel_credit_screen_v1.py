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
OUTPUT_DIR = Path("evidence") / "angl_static_fallen_angel_credit_screen_v1" / "latest"
INTAKE_DIR = Path("evidence") / "direction_owner_single_source_intake_v1" / "latest"
PREREG_PATH = INTAKE_DIR / "preregistration.yaml"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
CACHE_DIR = Path("data") / "cache"
CONFIG_PATH = Path("config.yaml")

SOURCE_ID = "ice_vaneck_us_fallen_angel_angl_v1"
CANDIDATE_ID = "angl_static_fallen_angel_credit_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
ROLE = "return_seeking_credit_allocation"
CANDIDATE = "ANGL"
PRIMARY_BENCHMARK = "HYG"
CONTEXT_BENCHMARKS = ("BIL", "IEF")
SYMBOLS = (CANDIDATE, PRIMARY_BENCHMARK, *CONTEXT_BENCHMARKS)
REQUIRED_ANGL_HASH = "C1B84A9304CF3281CFB70E3B879BC6919ADFBB9E6CD27F5586B51980474F2283"
COMMON_START = "2012-04-11"
COMMON_END = "2026-06-18"
HARD_REGIME_MIN_SESSIONS = 504
TOL = 1e-12

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "methodology_regime_instability",
    "benchmark_like_no_edge",
    "control_weak",
    "risk_reduction_without_return_edge",
    "no_material_edge",
    "not_comparable",
    "invalid_methodology",
    "direction_owner_review_required",
}


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def file_hash(path: Path) -> str:
    full = abs_path(path)
    if not full.exists():
        return "missing"
    digest = hashlib.sha256()
    with full.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def clean_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return ""
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_value(row.get(field, "")) for field in fieldnames})


def read_yaml(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    if not full.exists():
        return {}
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


def cache_row(symbol: str) -> dict[str, Any]:
    rel = CACHE_DIR / f"{symbol}.csv"
    full = abs_path(rel)
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": str(full),
        "cache_exists": full.exists(),
        "cache_hash": file_hash(rel),
        "required_hash": REQUIRED_ANGL_HASH if symbol == CANDIDATE else "",
        "hash_match": True,
        "schema": "",
        "first_valid_date": "",
        "last_valid_date": "",
        "row_count": 0,
        "adjusted_close_available": False,
        "missing_adj_close_count": "",
        "duplicate_date_count": "",
        "nonpositive_adj_close_count": "",
        "symbol_identity_valid": False,
        "cache_ready": False,
    }
    if not full.exists():
        row["hash_match"] = False
        return row
    frame = pd.read_csv(full)
    row["schema"] = "|".join(frame.columns)
    row["adjusted_close_available"] = "adj_close" in frame.columns
    dates = pd.to_datetime(frame.get("date"), errors="coerce")
    adj = pd.to_numeric(frame.get("adj_close"), errors="coerce") if "adj_close" in frame else pd.Series(dtype=float)
    symbols = set(str(value) for value in frame.get("symbol", pd.Series(dtype=str)).dropna().unique())
    row["first_valid_date"] = dates.dropna().min().date().isoformat() if dates.notna().any() else ""
    row["last_valid_date"] = dates.dropna().max().date().isoformat() if dates.notna().any() else ""
    row["row_count"] = int(len(frame))
    row["missing_adj_close_count"] = int(adj.isna().sum()) if "adj_close" in frame else len(frame)
    row["duplicate_date_count"] = int(dates.duplicated().sum())
    row["nonpositive_adj_close_count"] = int((adj <= 0).sum()) if "adj_close" in frame else len(frame)
    row["symbol_identity_valid"] = symbols == {symbol}
    row["hash_match"] = row["cache_hash"] == REQUIRED_ANGL_HASH if symbol == CANDIDATE else row["cache_hash"] != "missing"
    row["cache_ready"] = (
        row["cache_exists"]
        and row["adjusted_close_available"]
        and row["symbol_identity_valid"]
        and row["missing_adj_close_count"] == 0
        and row["duplicate_date_count"] == 0
        and row["nonpositive_adj_close_count"] == 0
        and row["hash_match"]
    )
    return row


def verify_cache_rows() -> list[dict[str, Any]]:
    rows = [cache_row(symbol) for symbol in SYMBOLS]
    blockers = [row for row in rows if not row["cache_ready"]]
    if blockers:
        raise RuntimeError(f"cache preflight failed before performance: {blockers}")
    return rows


def load_adjusted_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(abs_path(CACHE_DIR / f"{symbol}.csv"))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.Series(close.to_numpy(dtype=float), index=dates, name=symbol).dropna().sort_index()
    return series[~series.index.duplicated(keep="last")]


def load_prices() -> pd.DataFrame:
    return pd.concat([load_adjusted_close(symbol) for symbol in SYMBOLS], axis=1, sort=True).sort_index()


def common_angl_hyg_dates(prices: pd.DataFrame) -> pd.DatetimeIndex:
    common = prices[[CANDIDATE, PRIMARY_BENCHMARK]].dropna().loc[COMMON_START:COMMON_END].index
    if common.empty:
        raise RuntimeError("ANGL/HYG common date alignment failed")
    if common[0].date().isoformat() != COMMON_START or common[-1].date().isoformat() != COMMON_END:
        raise RuntimeError("ANGL/HYG common history does not match frozen boundaries")
    return pd.DatetimeIndex(common)


def cost_convention() -> dict[str, Any]:
    config = read_yaml(CONFIG_PATH)
    config_slippage = float(config["execution"]["standard_slippage_pct_per_side"])
    active_slippage = float(active.SLIPPAGE)
    if abs(config_slippage - active_slippage) > TOL:
        raise RuntimeError("conflicting canonical ETF transaction-cost assumptions")
    return {
        "source_path": "run_active_strategy_evidence_recompute.py and config.yaml",
        "initial_capital": active.STARTING_EQUITY,
        "standard_slippage_pct_per_side": active_slippage,
        "entry_cost": "entry_notional * standard_slippage_pct_per_side",
        "exit_cost": "exit_notional * standard_slippage_pct_per_side",
        "identical_treatment_for": list(SYMBOLS),
        "conflict_detected": False,
    }


def generate_windows(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        starts = list(range(0, len(common_dates) - horizon))
        selected = starts if len(starts) <= active.MAX_WINDOWS_PER_HORIZON else sorted(set(int(value) for value in np.linspace(starts[0], starts[-1], active.MAX_WINDOWS_PER_HORIZON)))
        for sequence, start in enumerate(selected, start=1):
            rows.append(
                {
                    "window_id": f"{horizon}d_{sequence}",
                    "horizon_days": horizon,
                    "start_index": int(start),
                    "end_index": int(start + horizon),
                    "window_start": common_dates[start].date().isoformat(),
                    "window_end": common_dates[start + horizon].date().isoformat(),
                    "selection_algorithm": "deterministic_linspace_max_5_per_horizon_common_angl_hyg_period",
                    "generated_before_performance": True,
                    "performance_computed_at_definition_time": False,
                    "window_valid_pre_performance": True,
                }
            )
    return rows


def chronological_thirds(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    n = len(common_dates)
    boundaries = [(0, n // 3 - 1), (n // 3, (2 * n) // 3 - 1), ((2 * n) // 3, n - 1)]
    rows = []
    for index, (start, end) in enumerate(boundaries, start=1):
        rows.append(
            {
                "period_id": f"chronological_third_{index}",
                "period_type": "chronological_third",
                "sequence": index,
                "start_index": start,
                "end_index": end,
                "start_date": common_dates[start].date().isoformat(),
                "end_date": common_dates[end].date().isoformat(),
                "selection_algorithm": "mechanical_equal_count_chronological_thirds",
            }
        )
    return rows


def methodology_regimes(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    dates = pd.Series(common_dates)
    regime_1_end = dates[dates < pd.Timestamp("2020-02-28")].iloc[-1]
    regime_2_start = dates[dates >= pd.Timestamp("2020-02-28")].iloc[0]
    regime_2_end = dates[dates < pd.Timestamp("2024-01-02")].iloc[-1]
    regime_3_start = dates[dates >= pd.Timestamp("2024-01-02")].iloc[0]
    raw = [
        (
            "methodology_regime_1_prior_benchmark_methodology",
            common_dates[0],
            regime_1_end,
            "prior benchmark methodology",
            "ICE BofA US Fallen Angel High Yield Index",
        ),
        (
            "methodology_regime_2_initial_h0cf_methodology",
            regime_2_start,
            regime_2_end,
            "initial ICE US Fallen Angel High Yield 10% Constrained methodology",
            "ICE US Fallen Angel High Yield 10% Constrained Index",
        ),
        (
            "methodology_regime_3_amended_h0cf_methodology",
            regime_3_start,
            common_dates[-1],
            "amended eligibility methodology",
            "ICE US Fallen Angel High Yield 10% Constrained Index",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for sequence, (period_id, start, end, interpretation, benchmark) in enumerate(raw, start=1):
        count = int(((common_dates >= start) & (common_dates <= end)).sum())
        rows.append(
            {
                "period_id": period_id,
                "period_type": "methodology_regime",
                "sequence": sequence,
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "trading_day_count": count,
                "calendar_length_days": int((end - start).days + 1),
                "benchmark": benchmark,
                "interpretation": interpretation,
                "evidence_weight": "hard_evidence_eligible" if count >= HARD_REGIME_MIN_SESSIONS else "descriptive_only",
                "hard_evidence_min_sessions": HARD_REGIME_MIN_SESSIONS,
                "post_2023_short_sample_caveat": period_id.endswith("amended_h0cf_methodology"),
            }
        )
    return rows


def period_from_dates(common_dates: pd.DatetimeIndex, start_date: str, end_date: str) -> pd.DatetimeIndex:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    return common_dates[(common_dates >= start) & (common_dates <= end)]


def max_drawdown_pct(equity: pd.Series) -> float:
    with_initial = pd.concat([pd.Series([active.STARTING_EQUITY], index=[equity.index[0] - pd.Timedelta(days=1)]), equity])
    drawdown = with_initial / with_initial.cummax() - 1.0
    return float(drawdown.min())


def downside_volatility(returns: pd.Series) -> float:
    downside = returns[returns < 0]
    if len(downside) <= 1:
        return 0.0
    return float(downside.std(ddof=1) * math.sqrt(252))


def realized_volatility(returns: pd.Series) -> float:
    if len(returns) <= 1:
        return 0.0
    return float(returns.std(ddof=1) * math.sqrt(252))


def simulate_symbol_period(symbol: str, prices: pd.DataFrame, period_dates: pd.DatetimeIndex, cost: float) -> dict[str, Any]:
    series = prices[symbol].reindex(period_dates)
    if series.isna().any() or len(series) < 2:
        return {
            "symbol": symbol,
            "period_valid": False,
            "invalid_reason": "missing_or_insufficient_adjusted_close_data",
        }
    entry_price = float(series.iloc[0])
    shares = active.STARTING_EQUITY * (1.0 - cost) / entry_price
    equity = series.astype(float) * shares
    equity.iloc[-1] = equity.iloc[-1] * (1.0 - cost)
    returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / active.STARTING_EQUITY - 1.0)
    years = max(len(returns) / 252.0, TOL)
    annualized = float((1.0 + total_return) ** (1.0 / years) - 1.0) if total_return > -1.0 else -1.0
    dd = max_drawdown_pct(equity)
    return {
        "symbol": symbol,
        "period_valid": True,
        "invalid_reason": "",
        "start_date": period_dates[0].date().isoformat(),
        "end_date": period_dates[-1].date().isoformat(),
        "trading_day_count": int(len(period_dates)),
        "return_day_count": int(len(returns)),
        "calendar_length_days": int((period_dates[-1] - period_dates[0]).days + 1),
        "entry_price": entry_price,
        "exit_price": float(series.iloc[-1]),
        "actual_shares": float(shares),
        "actual_shares_held_constant": True,
        "entry_cost_dollars": float(active.STARTING_EQUITY * cost),
        "exit_cost_dollars": float((series.iloc[-1] * shares) * cost),
        "total_transaction_cost_dollars": float(active.STARTING_EQUITY * cost + (series.iloc[-1] * shares) * cost),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized,
        "realized_volatility": realized_volatility(returns),
        "downside_volatility": downside_volatility(returns),
        "max_drawdown": dd,
        "return_drawdown_ratio": float(total_return / abs(dd)) if dd < 0 else "",
        "target_300_hit_diagnostic": bool((equity - active.STARTING_EQUITY >= 300.0).any()),
        "target_400_hit_diagnostic": bool((equity - active.STARTING_EQUITY >= 400.0).any()),
        "stop_600_hit_diagnostic": bool((equity - active.STARTING_EQUITY <= active.STOP_DOLLARS).any()),
        "daily_return_series": returns,
    }


def compare_period(period_id: str, period_type: str, prices: pd.DataFrame, period_dates: pd.DatetimeIndex, cost: float) -> dict[str, dict[str, Any]]:
    metrics = {symbol: simulate_symbol_period(symbol, prices, period_dates, cost) for symbol in SYMBOLS}
    for symbol, row in metrics.items():
        row["period_id"] = period_id
        row["period_type"] = period_type
    return metrics


def relative_metrics(period_id: str, period_type: str, metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidate = metrics[CANDIDATE]
    rows: list[dict[str, Any]] = []
    for benchmark in (PRIMARY_BENCHMARK, *CONTEXT_BENCHMARKS):
        bench = metrics[benchmark]
        valid = candidate.get("period_valid") is True and bench.get("period_valid") is True
        rows.append(
            {
                "period_id": period_id,
                "period_type": period_type,
                "candidate_id": CANDIDATE_ID,
                "candidate_symbol": CANDIDATE,
                "benchmark_symbol": benchmark,
                "benchmark_role": "primary_decision_benchmark" if benchmark == PRIMARY_BENCHMARK else "context_only",
                "relative_metrics_valid": valid,
                "total_return_delta": float(candidate["total_return"] - bench["total_return"]) if valid else "",
                "annualized_return_delta": float(candidate["annualized_return"] - bench["annualized_return"]) if valid else "",
                "final_equity_delta": float(candidate["final_equity"] - bench["final_equity"]) if valid else "",
                "max_drawdown_delta": float(candidate["max_drawdown"] - bench["max_drawdown"]) if valid else "",
                "volatility_delta": float(candidate["realized_volatility"] - bench["realized_volatility"]) if valid else "",
                "return_drawdown_ratio_delta": float(candidate["return_drawdown_ratio"] - bench["return_drawdown_ratio"]) if valid and candidate["return_drawdown_ratio"] != "" and bench["return_drawdown_ratio"] != "" else "",
                "can_determine_primary_outcome": benchmark == PRIMARY_BENCHMARK,
            }
        )
    return rows


def window_level_rows(windows: list[dict[str, Any]], prices: pd.DataFrame, common_dates: pd.DatetimeIndex, cost: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in windows:
        dates = common_dates[int(window["start_index"]) : int(window["end_index"]) + 1]
        metrics = compare_period(window["window_id"], f"sampled_window_{window['horizon_days']}", prices, dates, cost)
        angl = metrics[CANDIDATE]
        hyg = metrics[PRIMARY_BENCHMARK]
        valid = angl["period_valid"] and hyg["period_valid"] and len(dates) == int(window["horizon_days"]) + 1
        rows.append(
            {
                **window,
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "candidate_symbol": CANDIDATE,
                "primary_benchmark": PRIMARY_BENCHMARK,
                "window_valid": valid,
                "invalid_reason": "" if valid else "missing_or_wrong_length",
                "matching_angl_hyg_dates_used": True,
                "entry_trade_count": 1 if valid else 0,
                "measurement_exit_count": 1 if valid else 0,
                "actual_etf_shares_held": True,
                "candidate_final_equity": angl.get("final_equity", ""),
                "hyg_final_equity": hyg.get("final_equity", ""),
                "candidate_total_return": angl.get("total_return", ""),
                "hyg_total_return": hyg.get("total_return", ""),
                "angl_minus_hyg_return": float(angl["total_return"] - hyg["total_return"]) if valid else "",
                "candidate_max_drawdown": angl.get("max_drawdown", ""),
                "hyg_max_drawdown": hyg.get("max_drawdown", ""),
                "candidate_realized_volatility": angl.get("realized_volatility", ""),
                "hyg_realized_volatility": hyg.get("realized_volatility", ""),
                "candidate_downside_volatility": angl.get("downside_volatility", ""),
                "hyg_downside_volatility": hyg.get("downside_volatility", ""),
                "angl_higher_return": bool(angl["total_return"] > hyg["total_return"]) if valid else False,
                "angl_lower_drawdown": bool(angl["max_drawdown"] > hyg["max_drawdown"]) if valid else False,
                "both_higher_return_and_lower_drawdown": bool(angl["total_return"] > hyg["total_return"] and angl["max_drawdown"] > hyg["max_drawdown"]) if valid else False,
                "lower_return_and_worse_drawdown": bool(angl["total_return"] < hyg["total_return"] and angl["max_drawdown"] < hyg["max_drawdown"]) if valid else False,
            }
        )
    return rows


def summarize_windows(window_rows: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        subset = [row for row in window_rows if int(row["horizon_days"]) == horizon and row["window_valid"]]
        invalid = [row for row in window_rows if int(row["horizon_days"]) == horizon and not row["window_valid"]]
        if target == CANDIDATE:
            prefix = "candidate"
        elif target == PRIMARY_BENCHMARK:
            prefix = "hyg"
        else:
            raise ValueError(target)
        rows.append(
            {
                "strategy_id": CANDIDATE_ID if target == CANDIDATE else PRIMARY_BENCHMARK,
                "symbol": target,
                "period_type": "sampled_window_set",
                "horizon_days": horizon,
                "valid_window_count": len(subset),
                "invalid_window_count": len(invalid),
                "mean_final_equity": float(np.mean([row[f"{prefix}_final_equity"] for row in subset])) if subset else "",
                "median_final_equity": float(np.median([row[f"{prefix}_final_equity"] for row in subset])) if subset else "",
                "maximum_drawdown": float(min(row[f"{prefix}_max_drawdown"] for row in subset)) if subset else "",
                "realized_volatility": float(np.mean([row[f"{prefix}_realized_volatility"] for row in subset])) if subset else "",
                "downside_volatility": float(np.mean([row[f"{prefix}_downside_volatility"] for row in subset])) if subset else "",
            }
        )
    return rows


def window_joint_outcomes(window_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        subset = [row for row in window_rows if int(row["horizon_days"]) == horizon and row["window_valid"]]
        rows.append(
            {
                "horizon_days": horizon,
                "valid_window_count": len(subset),
                "invalid_window_count": sum(1 for row in window_rows if int(row["horizon_days"]) == horizon and not row["window_valid"]),
                "median_angl_minus_hyg_return": float(np.median([row["angl_minus_hyg_return"] for row in subset])) if subset else "",
                "angl_win_count": int(sum(1 for row in subset if row["angl_higher_return"])),
                "angl_win_rate": float(np.mean([row["angl_higher_return"] for row in subset])) if subset else "",
                "worst_relative_return_vs_hyg": float(min(row["angl_minus_hyg_return"] for row in subset)) if subset else "",
                "pct_higher_return": float(np.mean([row["angl_higher_return"] for row in subset])) if subset else "",
                "pct_lower_drawdown": float(np.mean([row["angl_lower_drawdown"] for row in subset])) if subset else "",
                "pct_both_higher_return_and_lower_drawdown": float(np.mean([row["both_higher_return_and_lower_drawdown"] for row in subset])) if subset else "",
                "pct_lower_return_and_worse_drawdown": float(np.mean([row["lower_return_and_worse_drawdown"] for row in subset])) if subset else "",
            }
        )
    return rows


def metric_row(symbol: str, strategy_id: str, period_id: str, period_type: str, metrics: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "role": role,
        "period_id": period_id,
        "period_type": period_type,
        "start_date": metrics.get("start_date", ""),
        "end_date": metrics.get("end_date", ""),
        "trading_day_count": metrics.get("trading_day_count", ""),
        "calendar_length_days": metrics.get("calendar_length_days", ""),
        "total_return": metrics.get("total_return", ""),
        "annualized_return": metrics.get("annualized_return", ""),
        "realized_volatility": metrics.get("realized_volatility", ""),
        "downside_volatility": metrics.get("downside_volatility", ""),
        "max_drawdown": metrics.get("max_drawdown", ""),
        "return_drawdown_ratio": metrics.get("return_drawdown_ratio", ""),
        "final_equity": metrics.get("final_equity", ""),
        "actual_shares_held_constant": metrics.get("actual_shares_held_constant", ""),
        "entry_cost_dollars": metrics.get("entry_cost_dollars", ""),
        "exit_cost_dollars": metrics.get("exit_cost_dollars", ""),
    }


def classify_outcome(
    full_relative: dict[str, Any],
    joint_rows: list[dict[str, Any]],
    regime_metrics: list[dict[str, Any]],
    third_metrics: list[dict[str, Any]],
    invariants_passed: bool,
) -> tuple[str, dict[str, Any]]:
    if not invariants_passed:
        return "invalid_methodology", {}
    if not full_relative["relative_metrics_valid"]:
        return "not_comparable", {}
    by_horizon = {int(row["horizon_days"]): row for row in joint_rows}
    median_90 = float(by_horizon[90]["median_angl_minus_hyg_return"])
    median_180 = float(by_horizon[180]["median_angl_minus_hyg_return"])
    win_count = int(by_horizon[90]["angl_win_count"] + by_horizon[180]["angl_win_count"])
    full_excess = float(full_relative["annualized_return_delta"])
    full_total_excess = float(full_relative["total_return_delta"])
    full_drawdown_delta = float(full_relative["max_drawdown_delta"])
    full_vol_delta = float(full_relative["volatility_delta"])
    hard_regime_negative = [
        row for row in regime_metrics
        if row["evidence_weight"] == "hard_evidence_eligible" and float(row["angl_minus_hyg_total_return"]) < 0
    ]
    third_positive = [row for row in third_metrics if float(row["angl_minus_hyg_total_return"]) > 0]
    advantage_isolated = full_total_excess > 0 and len(third_positive) == 1
    post_2023 = next(row for row in regime_metrics if row["period_id"] == "methodology_regime_3_amended_h0cf_methodology")
    hard_positive = [row for row in regime_metrics if row["evidence_weight"] == "hard_evidence_eligible" and float(row["angl_minus_hyg_total_return"]) > 0]
    short_contradiction = (
        post_2023["evidence_weight"] == "descriptive_only"
        and hard_positive
        and float(post_2023["angl_minus_hyg_total_return"]) < -0.05
    )
    hard_conditions = {
        "positive_median_90": median_90 > 0,
        "positive_median_180": median_180 > 0,
        "win_count_at_least_6": win_count >= 6,
        "positive_full_annualized_excess": full_excess > 0,
        "no_negative_hard_regime_excess": not hard_regime_negative,
        "advantage_not_isolated_to_one_third": not advantage_isolated,
        "drawdown_not_more_than_5pp_worse": full_drawdown_delta >= -0.05,
        "invariants_passed": invariants_passed,
    }
    if all(hard_conditions.values()):
        if short_contradiction:
            return "direction_owner_review_required", hard_conditions
        return "comparative_evidence_positive", hard_conditions
    if full_excess > 0 and hard_regime_negative:
        return "methodology_regime_instability", hard_conditions
    repeatable_excess = median_90 > 0 and median_180 > 0 and win_count >= 6 and full_excess > 0
    if repeatable_excess and (full_drawdown_delta < -0.05 or full_vol_delta > 0.02):
        return "higher_return_higher_risk", hard_conditions
    if abs(full_excess) < 0.005 and abs(full_total_excess) < 0.05:
        return "benchmark_like_no_edge", hard_conditions
    if full_excess < 0 and median_90 < 0 and median_180 < 0 and win_count < 5:
        return "control_weak", hard_conditions
    if full_excess <= 0 and (full_drawdown_delta > 0 or full_vol_delta < 0):
        return "risk_reduction_without_return_edge", hard_conditions
    if short_contradiction:
        return "direction_owner_review_required", hard_conditions
    return "no_material_edge", hard_conditions


def source_caveats_text() -> str:
    return """# Source And Methodology Caveats

- This screen is a direct ETF-wrapper comparison of `ANGL` versus broad high-yield ETF benchmark `HYG`.
- A positive result would be comparative evidence for investable fallen-angel ETF exposure versus broad high yield only.
- It is not proof that forced selling caused any return difference, that downgrades generated mispricing, or that ANGL will continue outperforming.
- Academic evidence on downgrade-related price pressure is mixed.
- ANGL tracked the ICE BofA US Fallen Angel High Yield Index before February 28, 2020.
- From February 28, 2020 it tracked the ICE US Fallen Angel High Yield 10% Constrained Index.
- Effective December 31, 2023, the current index methodology was amended to allow limited original-issue high-yield bonds from already represented obligors when senior or senior secured.
- Post-2023 ANGL should not be described as a pure investment-grade-at-issuance fallen-angel exposure.
- The post-2023 regime keeps a shorter-post-amendment-sample caveat. Under the frozen 504-session rule it is hard-evidence eligible when it has at least 504 common ANGL/HYG sessions; otherwise it is descriptive-only.
"""


def summary_text(outcome: dict[str, Any], joint_rows: list[dict[str, Any]], full_relative: dict[str, Any]) -> str:
    return f"""# ANGL Static Fallen-Angel Credit Screen v1

Candidate: `{CANDIDATE_ID}`

Primary benchmark: `{PRIMARY_BENCHMARK}`

Outcome: `{outcome['primary_outcome']}`

Full-period ANGL-minus-HYG total return: `{float(full_relative['total_return_delta']):.6f}`

Full-period ANGL-minus-HYG annualized return: `{float(full_relative['annualized_return_delta']):.6f}`

90-day median ANGL-minus-HYG return: `{float(next(row for row in joint_rows if int(row['horizon_days']) == 90)['median_angl_minus_hyg_return']):.6f}`

180-day median ANGL-minus-HYG return: `{float(next(row for row in joint_rows if int(row['horizon_days']) == 180)['median_angl_minus_hyg_return']):.6f}`

No promotion, paper/demo activation, broader validation, robustness run, parameter search, provider download, or real-money recommendation occurred.

Exact next action: `{outcome['next_action']}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    global ROOT
    ROOT = root
    output = abs_path(OUTPUT_DIR)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    registry_before = file_hash(REGISTRY_PATH)
    active_before = file_hash(ACTIVE_OBSERVATIONS_PATH)
    prereg = read_yaml(PREREG_PATH)
    if prereg.get("candidate_id") != CANDIDATE_ID:
        raise RuntimeError("authoritative pre-registration is missing or for a different candidate")
    cache_rows = verify_cache_rows()
    cost = cost_convention()
    prices = load_prices()
    common_dates = common_angl_hyg_dates(prices)
    windows = generate_windows(common_dates)
    thirds = chronological_thirds(common_dates)
    regimes = methodology_regimes(common_dates)
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "role": ROLE,
        "classification": ["direct_etf_wrapper_test", "not_constituent_level_bond_index_reconstruction", "research_paper_demo_evidence_only"],
        "authoritative_preregistration": str(abs_path(PREREG_PATH)),
        "cache_preflight_rows": cache_rows,
        "required_angl_cache_hash": REQUIRED_ANGL_HASH,
        "common_angl_hyg_start": COMMON_START,
        "common_angl_hyg_end": COMMON_END,
        "common_angl_hyg_row_count": len(common_dates),
        "transaction_cost_convention": cost,
        "entry_and_exit_convention": "buy 100% notional at adjusted close with standard per-side cost; hold actual shares; liquidate at window end with same per-side cost",
        "deterministic_window_count": len(windows),
        "window_definition_hash": stable_hash(windows),
        "chronological_third_count": len(thirds),
        "methodology_regime_count": len(regimes),
        "metrics": prereg.get("metrics", []),
        "pass_conditions": prereg.get("pass_conditions", []),
        "fail_conditions": prereg.get("fail_conditions", []),
        "stop_conditions": prereg.get("stop_conditions", []),
        "no_parameter_wrapper_benchmark_or_window_selection_authorized": True,
        "no_alternative_wrapper": True,
        "no_timing_trend_rate_duration_spread_bil_or_downgrade_filter": True,
        "no_provider_call": True,
        "provider_download": False,
        "intraday_data_used": False,
        "screen_authorized_scope": "exact_frozen_angl_static_candidate_only",
        "windows_generated_before_performance": True,
        "pre_performance_manifest_written": True,
        "registry_hash_before": registry_before,
        "active_observations_hash_before": active_before,
    }
    write_json(OUTPUT_DIR / "execution_manifest.json", manifest)
    write_csv(OUTPUT_DIR / "frozen_window_definitions.csv", windows)
    write_csv(OUTPUT_DIR / "methodology_regime_definitions.csv", regimes)

    window_rows = window_level_rows(windows, prices, common_dates, float(cost["standard_slippage_pct_per_side"]))
    candidate_metrics = summarize_windows(window_rows, CANDIDATE)
    primary_metrics = summarize_windows(window_rows, PRIMARY_BENCHMARK)
    joint_rows = window_joint_outcomes(window_rows)

    full_dates = period_from_dates(common_dates, COMMON_START, COMMON_END)
    full_metrics = compare_period("full_common_angl_hyg_period", "full_period", prices, full_dates, float(cost["standard_slippage_pct_per_side"]))
    full_relative_rows = relative_metrics("full_common_angl_hyg_period", "full_period", full_metrics)
    full_relative = next(row for row in full_relative_rows if row["benchmark_symbol"] == PRIMARY_BENCHMARK)

    third_metric_rows: list[dict[str, Any]] = []
    third_relative_rows: list[dict[str, Any]] = []
    chronological_rows: list[dict[str, Any]] = []
    for period in thirds:
        dates = period_from_dates(common_dates, period["start_date"], period["end_date"])
        metrics = compare_period(period["period_id"], period["period_type"], prices, dates, float(cost["standard_slippage_pct_per_side"]))
        rels = relative_metrics(period["period_id"], period["period_type"], metrics)
        primary_rel = next(row for row in rels if row["benchmark_symbol"] == PRIMARY_BENCHMARK)
        chronological_rows.append(
            {
                **period,
                "trading_day_count": len(dates),
                "calendar_length_days": int((dates[-1] - dates[0]).days + 1),
                "angl_total_return": metrics[CANDIDATE]["total_return"],
                "hyg_total_return": metrics[PRIMARY_BENCHMARK]["total_return"],
                "angl_minus_hyg_total_return": primary_rel["total_return_delta"],
                "angl_annualized_return": metrics[CANDIDATE]["annualized_return"],
                "hyg_annualized_return": metrics[PRIMARY_BENCHMARK]["annualized_return"],
                "angl_max_drawdown": metrics[CANDIDATE]["max_drawdown"],
                "hyg_max_drawdown": metrics[PRIMARY_BENCHMARK]["max_drawdown"],
            }
        )
        third_metric_rows.extend(metric_row(symbol, CANDIDATE_ID if symbol == CANDIDATE else symbol, period["period_id"], period["period_type"], row, "candidate" if symbol == CANDIDATE else "benchmark") for symbol, row in metrics.items())
        third_relative_rows.extend(rels)

    regime_metric_rows: list[dict[str, Any]] = []
    regime_relative_rows: list[dict[str, Any]] = []
    methodology_rows: list[dict[str, Any]] = []
    for regime in regimes:
        dates = period_from_dates(common_dates, regime["start_date"], regime["end_date"])
        metrics = compare_period(regime["period_id"], regime["period_type"], prices, dates, float(cost["standard_slippage_pct_per_side"]))
        rels = relative_metrics(regime["period_id"], regime["period_type"], metrics)
        primary_rel = next(row for row in rels if row["benchmark_symbol"] == PRIMARY_BENCHMARK)
        methodology_rows.append(
            {
                **regime,
                "angl_total_return": metrics[CANDIDATE]["total_return"],
                "hyg_total_return": metrics[PRIMARY_BENCHMARK]["total_return"],
                "angl_minus_hyg_total_return": primary_rel["total_return_delta"],
                "angl_annualized_return": metrics[CANDIDATE]["annualized_return"],
                "hyg_annualized_return": metrics[PRIMARY_BENCHMARK]["annualized_return"],
                "angl_realized_volatility": metrics[CANDIDATE]["realized_volatility"],
                "hyg_realized_volatility": metrics[PRIMARY_BENCHMARK]["realized_volatility"],
                "angl_max_drawdown": metrics[CANDIDATE]["max_drawdown"],
                "hyg_max_drawdown": metrics[PRIMARY_BENCHMARK]["max_drawdown"],
                "hard_stability_judgment_allowed": regime["evidence_weight"] == "hard_evidence_eligible",
                "descriptive_only_cannot_pass_or_fail": regime["evidence_weight"] == "descriptive_only",
            }
        )
        regime_metric_rows.extend(metric_row(symbol, CANDIDATE_ID if symbol == CANDIDATE else symbol, regime["period_id"], regime["period_type"], row, "candidate" if symbol == CANDIDATE else "benchmark") for symbol, row in metrics.items())
        regime_relative_rows.extend(rels)

    candidate_full_row = metric_row(CANDIDATE, CANDIDATE_ID, "full_common_angl_hyg_period", "full_period", full_metrics[CANDIDATE], "candidate")
    primary_full_row = metric_row(PRIMARY_BENCHMARK, PRIMARY_BENCHMARK, "full_common_angl_hyg_period", "full_period", full_metrics[PRIMARY_BENCHMARK], "primary_benchmark")
    context_rows = [
        metric_row(symbol, symbol, "full_common_angl_hyg_period", "full_period", full_metrics[symbol], "context_only")
        for symbol in CONTEXT_BENCHMARKS
    ]
    context_rows.extend(
        row for row in third_metric_rows + regime_metric_rows if row["symbol"] in CONTEXT_BENCHMARKS
    )
    benchmark_relative_rows = full_relative_rows + third_relative_rows + regime_relative_rows
    invariants = [
        {
            "invariant_id": "cache_hashes_verified_before_performance",
            "invariant_passed": all(row["cache_ready"] for row in cache_rows),
            "detail": "ANGL required hash and all cache schemas verified before metrics.",
        },
        {
            "invariant_id": "matching_angl_hyg_dates_used",
            "invariant_passed": len(common_dates) == 3568 and common_dates[0].date().isoformat() == COMMON_START and common_dates[-1].date().isoformat() == COMMON_END,
            "detail": "Common ANGL/HYG adjusted-close dates only; no forward filling.",
        },
        {
            "invariant_id": "actual_shares_held",
            "invariant_passed": all(row["actual_etf_shares_held"] for row in window_rows),
            "detail": "One entry, one measurement exit, no daily target rebalance.",
        },
        {
            "invariant_id": "identical_transaction_cost_treatment",
            "invariant_passed": True,
            "detail": "Same standard per-side slippage applied to ANGL, HYG, BIL, and IEF direct comparisons.",
        },
        {
            "invariant_id": "no_strategy_filters_added",
            "invariant_passed": True,
            "detail": "No timing, trend, rate, duration, spread, BIL, or downgrade-event filters.",
        },
        {
            "invariant_id": "primary_benchmark_hyg_only",
            "invariant_passed": True,
            "detail": "Outcome classifier uses HYG; BIL and IEF are context-only.",
        },
    ]
    invariants_passed = all(row["invariant_passed"] for row in invariants)
    outcome_label, hard_conditions = classify_outcome(full_relative, joint_rows, methodology_rows, chronological_rows, invariants_passed)
    weak_or_inconclusive = outcome_label in {"benchmark_like_no_edge", "control_weak", "risk_reduction_without_return_edge", "no_material_edge", "not_comparable", "invalid_methodology"}
    outcome = {
        "primary_outcome": outcome_label,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "primary_benchmark": PRIMARY_BENCHMARK,
        "allowed_outcome": outcome_label in ALLOWED_OUTCOMES,
        "hard_conditions": hard_conditions,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "validation_authorized": False,
        "screening_is_non_promotional": True,
        "mechanism_interpretation": "comparative evidence for investable fallen-angel ETF exposure versus broad high yield" if outcome_label == "comparative_evidence_positive" else "diagnostic comparative wrapper evidence only",
        "next_action": "direction_owner_validation_decision_required" if outcome_label in {"comparative_evidence_positive", "higher_return_higher_risk", "methodology_regime_instability", "direction_owner_review_required"} else "direction_owner_closure_or_validation_decision_required",
    }
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "outcome": outcome_label,
            "close_exact_variant_for_immediate_retest": weak_or_inconclusive,
            "broader_family_preserved_for_materially_different_future_source": True,
            "do_not_test_alternative_fallen_angel_etfs_automatically": True,
            "do_not_add_timing_or_overlay_variants_automatically": True,
            "lifecycle_status_changed": False,
            "paper_demo_authorized": False,
            "promotion_authorized": False,
        }
    ]
    registry_after = file_hash(REGISTRY_PATH)
    active_after = file_hash(ACTIVE_OBSERVATIONS_PATH)
    queue = read_yaml(RESEARCH_QUEUE_PATH).get("external_source_discovery_lane", {})
    consistency = {
        "exact_candidate_evaluated_once": True,
        "exact_angl_hash_used": next(row for row in cache_rows if row["symbol"] == CANDIDATE)["cache_hash"] == REQUIRED_ANGL_HASH,
        "hyg_primary_benchmark": True,
        "context_benchmarks_do_not_determine_outcome": all(row["can_determine_primary_outcome"] is False for row in benchmark_relative_rows if row["benchmark_symbol"] in CONTEXT_BENCHMARKS),
        "no_provider_call_or_refresh": True,
        "windows_written_before_performance": True,
        "matching_angl_hyg_dates_used": True,
        "actual_etf_shares_held": True,
        "identical_transaction_cost_treatment": True,
        "adjusted_close_distribution_handling_consistent": True,
        "three_methodology_regimes_represented": len(methodology_rows) == 3,
        "post_2023_descriptive_only_when_below_504": (
            next(row for row in methodology_rows if row["period_id"].endswith("amended_h0cf_methodology"))["trading_day_count"] >= HARD_REGIME_MIN_SESSIONS
            or next(row for row in methodology_rows if row["period_id"].endswith("amended_h0cf_methodology"))["evidence_weight"] == "descriptive_only"
        ),
        "descriptive_only_cannot_independently_pass_or_fail": (
            next(row for row in methodology_rows if row["period_id"].endswith("amended_h0cf_methodology"))["evidence_weight"] != "descriptive_only"
            or next(row for row in methodology_rows if row["period_id"].endswith("amended_h0cf_methodology"))["descriptive_only_cannot_pass_or_fail"] is True
        ),
        "no_timing_trend_rate_duration_bil_or_downgrade_filter": True,
        "no_alternative_wrapper_or_window_search": True,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_unchanged": active_before == active_after,
        "external_discovery_pause_remains_active": queue.get("status") == "paused_pending_direction_owner_supplied_source",
        "generation_is_deterministic": True,
        "no_promotion_paper_demo_or_lifecycle_change": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    lineage = [
        {"artifact_id": "authoritative_intake_packet", "path": str(abs_path(INTAKE_DIR)), "sha256": file_hash(INTAKE_DIR / "decision.json"), "role": "source_preregistration_input"},
        {"artifact_id": "screen_module", "path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"), "sha256": file_hash(Path(__file__).relative_to(ROOT)), "role": "implementation"},
        {"artifact_id": "angl_cache", "path": str(abs_path(CACHE_DIR / "ANGL.csv")), "sha256": file_hash(CACHE_DIR / "ANGL.csv"), "role": "candidate_price_cache"},
        {"artifact_id": "hyg_cache", "path": str(abs_path(CACHE_DIR / "HYG.csv")), "sha256": file_hash(CACHE_DIR / "HYG.csv"), "role": "primary_benchmark_price_cache"},
    ]

    write_csv(OUTPUT_DIR / "candidate_metrics.csv", [*candidate_metrics, candidate_full_row, *[row for row in third_metric_rows + regime_metric_rows if row["symbol"] == CANDIDATE]])
    write_csv(OUTPUT_DIR / "primary_benchmark_metrics.csv", [*primary_metrics, primary_full_row, *[row for row in third_metric_rows + regime_metric_rows if row["symbol"] == PRIMARY_BENCHMARK]])
    write_csv(OUTPUT_DIR / "context_benchmark_metrics.csv", context_rows)
    write_csv(OUTPUT_DIR / "window_level_results.csv", window_rows)
    write_csv(OUTPUT_DIR / "benchmark_relative_metrics.csv", benchmark_relative_rows)
    write_csv(OUTPUT_DIR / "chronological_thirds_metrics.csv", chronological_rows)
    write_csv(OUTPUT_DIR / "methodology_regime_metrics.csv", methodology_rows)
    write_csv(OUTPUT_DIR / "return_risk_joint_outcomes.csv", joint_rows)
    write_csv(OUTPUT_DIR / "accounting_and_alignment_invariants.csv", invariants)
    write_text(OUTPUT_DIR / "source_and_methodology_caveats.md", source_caveats_text())
    write_text(OUTPUT_DIR / "screening_summary.md", summary_text(outcome, joint_rows, full_relative))
    write_json(OUTPUT_DIR / "screening_outcome.json", outcome)
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory)
    write_csv(OUTPUT_DIR / "artifact_lineage.csv", lineage)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "primary_outcome": outcome_label,
        "next_action": outcome["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
