from __future__ import annotations

import csv
import json
import math
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .sandbox_config import (
    ACTIVE_OBSERVATION_IDS,
    BENCHMARK_CONTROL_IDS,
    DATA_CACHE_DIR,
    INITIAL_SANDBOX_STATUS,
    MAX_TOTAL_FUTURE_VARIANTS,
    REGISTRY_PATH,
    ROADMAP_PATH,
    ROOT,
)
from .sandbox_indicators import validate_indicator_concept
from .sandbox_status_taxonomy import ALLOWED_SANDBOX_STATUSES, FORBIDDEN_STATUSES


IMPLEMENTATION_DIR = Path("evidence") / "governance" / "exploratory_strategy_search_sandbox_implementation" / "latest"
PLAN_FILE = IMPLEMENTATION_DIR / "sandbox_variant_plan_dry_run.csv"
IMPLEMENTATION_MANIFEST = IMPLEMENTATION_DIR / "exploratory_sandbox_implementation_manifest.json"
OUTPUT_ROOT = Path("evidence") / "exploratory_sandbox"

VALID_BATCH_NEXT_ACTIONS = {
    "audit_exploratory_sandbox_batch_results",
    "pre_register_one_family_from_sandbox_findings",
    "manual_review_required_for_exploratory_sandbox_batch",
    "pause_expansion_and_wait_for_manual_direction",
}
NEXT_ACTION_AUDIT = "audit_exploratory_sandbox_batch_results"
NEXT_ACTION_MANUAL = "manual_review_required_for_exploratory_sandbox_batch"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"

MANIFEST_FLAGS = {
    "sandbox_batch_run": True,
    "sandbox_results_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "trading_backtests_run": True,
    "sandbox_exploratory_metrics_computed": True,
    "new_promotable_strategy_metrics_computed": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
}

REQUIRED_OUTPUT_FILES = (
    "sandbox_batch_manifest.json",
    "sandbox_batch_summary.md",
    "sandbox_batch_preflight_report.md",
    "sandbox_variant_results.csv",
    "sandbox_family_summary.csv",
    "sandbox_family_summary.md",
    "sandbox_benchmark_comparison_summary.csv",
    "sandbox_risk_summary.csv",
    "sandbox_diversification_summary.csv",
    "sandbox_practicality_summary.csv",
    "sandbox_overfitting_risk_summary.md",
    "sandbox_research_only_leverage_summary.md",
    "sandbox_future_preregistration_candidates.md",
    "sandbox_discarded_or_weak_families.md",
    "sandbox_do_not_promote.md",
    "sandbox_batch_next_action.md",
    "sandbox_batch_consistency_check.json",
)

STARTING_EQUITY = 3000.0
ROLLING_WINDOW_DAYS = 126
TARGET_300 = STARTING_EQUITY + 300.0
TARGET_400 = STARTING_EQUITY + 400.0
STOP_EQUITY = STARTING_EQUITY - 600.0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def load_plan_rows(root: Path) -> list[dict[str, str]]:
    path = root / PLAN_FILE
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def repair_implementation_packet_flag(root: Path) -> tuple[bool, str]:
    manifest_path = root / IMPLEMENTATION_MANIFEST
    manifest = read_json(manifest_path)
    packet = root / IMPLEMENTATION_DIR / "exploratory_sandbox_implementation_packet.zip"
    if manifest.get("evidence_packet_created") is False and packet.exists():
        manifest["evidence_packet_created"] = True
        manifest["evidence_packet_path"] = str(packet.resolve())
        write_json(manifest_path, manifest)
        return True, "implementation packet flag repaired because packet exists"
    if manifest.get("evidence_packet_created") is True and packet.exists():
        return False, "implementation packet flag already true"
    return False, "implementation packet flag not repaired"


def approved_symbols(root: Path) -> set[str]:
    path = root / "strategy_lab" / "approved_etf_symbol_map.yaml"
    data = load_yaml(path)
    return {
        str(row.get("symbol", "")).upper()
        for row in data.get("symbols", [])
        if row.get("allowed_for_strategy") or row.get("allowed_for_benchmark")
    }


def cached_symbols(root: Path) -> set[str]:
    path = root / DATA_CACHE_DIR
    if not path.exists():
        return set()
    return {item.stem.upper() for item in path.glob("*.csv")}


def preflight(root: Path, max_variants: int) -> dict[str, Any]:
    root = root.resolve()
    registry = load_yaml(root / REGISTRY_PATH)
    roadmap = (root / ROADMAP_PATH).read_text(encoding="utf-8") if (root / ROADMAP_PATH).exists() else ""
    compact = (root / "reports" / "compact_state" / "current_tournament_state.md").read_text(encoding="utf-8") if (
        root / "reports" / "compact_state" / "current_tournament_state.md"
    ).exists() else ""
    implementation = read_json(root / IMPLEMENTATION_MANIFEST)
    repaired, repair_note = repair_implementation_packet_flag(root)
    rows = load_plan_rows(root)
    approved = approved_symbols(root)
    cached = cached_symbols(root)
    failures: list[str] = []
    warnings: list[str] = []

    metadata = registry.get("registry", {})
    expected_next = "run_exploratory_strategy_search_sandbox_batch"
    if metadata.get("current_next_action") != expected_next or metadata.get("official_current_next_action") != expected_next:
        failures.append("registry current/official next action does not authorize sandbox batch")
    if expected_next not in roadmap:
        failures.append("roadmap does not authorize sandbox batch")
    if implementation.get("next_action") != expected_next:
        failures.append("implementation manifest does not authorize sandbox batch")
    if expected_next not in compact:
        warnings.append("compact current_tournament_state.md is stale and does not show the sandbox batch next action")
    if not rows:
        failures.append("variant plan missing")
    if len(rows) != 80:
        failures.append(f"variant plan row count expected 80, found {len(rows)}")
    if len(rows) > max_variants or len(rows) > MAX_TOTAL_FUTURE_VARIANTS:
        failures.append("variant count exceeds authorized limit")

    forbidden_seen = sorted({row.get("status", "") for row in rows if row.get("status", "") in FORBIDDEN_STATUSES})
    if forbidden_seen:
        failures.append(f"forbidden statuses present: {forbidden_seen}")
    for row in rows:
        if row.get("promotable") != "false":
            failures.append(f"variant is promotable: {row.get('variant_id')}")
        if row.get("paper_candidate_allowed") != "false":
            failures.append(f"variant can create paper candidate: {row.get('variant_id')}")
        if row.get("status") != INITIAL_SANDBOX_STATUS:
            failures.append(f"variant status is not non_promotable_exploration: {row.get('variant_id')}")
        try:
            validate_indicator_concept(row.get("indicator_concept", ""))
        except ValueError as exc:
            failures.append(str(exc))
        symbols = [symbol.strip().upper() for symbol in row.get("symbols", "").split(",") if symbol.strip()]
        for symbol in symbols:
            if symbol not in approved:
                failures.append(f"symbol is not approved locally: {symbol}")
            if symbol not in cached:
                failures.append(f"symbol cache is missing locally: {symbol}")

    if metadata.get("intraday_research_remains_paused") is not True:
        failures.append("intraday is not marked paused in registry")
    for strategy_id in ACTIVE_OBSERVATION_IDS:
        if strategy_id not in {str(row.get("id", "")) for row in registry.get("strategies", [])}:
            failures.append(f"active observation missing from registry: {strategy_id}")
    if metadata.get("static_all_weather_benchmark_control_status") != "benchmark_control_accepted":
        failures.append("static all-weather benchmark/control status not confirmed")

    return {
        "preflight_passed": not failures,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "implementation_packet_flag_repaired": repaired,
        "implementation_packet_note": repair_note,
        "variant_count_planned": len(rows),
        "max_variants_requested": max_variants,
        "compact_state_stale_warning": expected_next not in compact,
    }


def read_price_series(root: Path, symbol: str) -> pd.Series:
    path = root / DATA_CACHE_DIR / f"{symbol.upper()}.csv"
    frame = pd.read_csv(path)
    price_col = "adj_close" if "adj_close" in frame.columns else "close"
    series = pd.Series(frame[price_col].astype(float).values, index=pd.to_datetime(frame["date"]), name=symbol.upper())
    return series[~series.index.duplicated()].sort_index()


def price_frame(root: Path, symbols: list[str]) -> pd.DataFrame:
    series = [read_price_series(root, symbol) for symbol in symbols]
    return pd.concat(series, axis=1, join="inner").dropna().sort_index()


def returns_from_prices(root: Path, symbols: list[str]) -> pd.DataFrame:
    return price_frame(root, symbols).pct_change().dropna()


def equity_to_returns(frame: pd.DataFrame, column: str) -> pd.Series:
    series = pd.Series(frame[column].astype(float).values, index=pd.to_datetime(frame["date"]), name=column)
    return series.pct_change().dropna()


def reference_returns(root: Path) -> dict[str, pd.Series]:
    refs: dict[str, pd.Series] = {}
    for symbol in ("SPY", "QQQ", "BIL"):
        refs[symbol] = returns_from_prices(root, [symbol]).iloc[:, 0].rename(symbol)

    combo_path = root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
    if combo_path.exists():
        frame = pd.read_csv(combo_path)
        refs["active_combo"] = equity_to_returns(frame, "active_combo_equity")
        refs["active_vm"] = equity_to_returns(frame, "vm_standalone_equity")
        refs["active_dsr"] = equity_to_returns(frame, "dsr_standalone_equity")
    else:
        refs["active_vm"] = returns_from_prices(root, ["SPLV", "USMV", "QUAL"]).mean(axis=1).rename("active_vm_proxy")
        refs["active_dsr"] = returns_from_prices(root, ["XLK", "XLF", "XLV", "XLE"]).mean(axis=1).rename("active_dsr_proxy")
        active_pair = pd.concat([refs["active_vm"], refs["active_dsr"]], axis=1, join="inner").dropna()
        refs["active_combo"] = active_pair.mean(axis=1).rename("active_combo_proxy")

    all_weather = returns_from_prices(root, ["SPY", "IEF", "GLD", "BIL"])
    refs["static_all_weather"] = (
        all_weather["SPY"] * 0.30 + all_weather["IEF"] * 0.40 + all_weather["GLD"] * 0.20 + all_weather["BIL"] * 0.10
    ).rename("static_all_weather")
    return refs


def rolling_return(price: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return price / price.shift(lookback) - 1.0


def rsi_score(price: pd.DataFrame, lookback: int) -> pd.DataFrame:
    delta = price.diff()
    gain = delta.clip(lower=0).rolling(lookback, min_periods=lookback).mean()
    loss = (-delta.clip(upper=0)).rolling(lookback, min_periods=lookback).mean()
    rs = gain / loss.replace(0, math.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return (50.0 - rsi).fillna(0.0)


def bollinger_reversion_score(price: pd.DataFrame, lookback: int) -> pd.DataFrame:
    mid = price.rolling(lookback, min_periods=lookback).mean()
    std = price.rolling(lookback, min_periods=lookback).std()
    z = (price - mid) / std.replace(0, math.nan)
    return (-z).fillna(0.0)


def score_frame(family: str, indicator: str, params: dict[str, Any], price: pd.DataFrame) -> pd.DataFrame:
    lookback = int(params.get("lookback") or params.get("fast") or params.get("window") or 50)
    if indicator == "sma":
        return price / price.rolling(lookback, min_periods=lookback).mean() - 1.0
    if indicator == "ema":
        return price / price.ewm(span=lookback, min_periods=lookback, adjust=False).mean() - 1.0
    if indicator == "rsi":
        return rsi_score(price, lookback)
    if indicator == "bollinger_bands":
        return bollinger_reversion_score(price, lookback)
    if indicator == "donchian_prior_high":
        prior_high = price.shift(1).rolling(lookback, min_periods=lookback).max()
        return price / prior_high - 1.0
    if indicator in {"atr", "realized_volatility"}:
        vol = price.pct_change().rolling(lookback, min_periods=lookback).std()
        return -vol
    if indicator == "rolling_percentile_rank":
        roc = rolling_return(price, lookback)
        return roc.rolling(lookback, min_periods=lookback).rank(pct=True)
    if indicator == "moving_average_regime":
        fast = int(params.get("fast", 50))
        slow = int(params.get("slow", 200))
        return price.rolling(fast, min_periods=fast).mean() / price.rolling(slow, min_periods=slow).mean() - 1.0
    if indicator == "spy_regime_features":
        return rolling_return(price, 63)
    if indicator == "roc_rolling_return":
        return rolling_return(price, lookback)
    if indicator == "volume_sma_filter_alignment":
        return rolling_return(price, lookback)
    return rolling_return(price, lookback)


def weights_from_score(score: pd.DataFrame, family: str, top_n: int = 2) -> pd.DataFrame:
    if family == "mean_reversion":
        eligible = score > 0.25
    elif family == "volatility_regime":
        eligible = score.notna()
    else:
        eligible = score > 0.0
    ranks = score.rank(axis=1, ascending=False, method="first")
    selected = eligible & (ranks <= top_n)
    counts = selected.sum(axis=1).replace(0, math.nan)
    return selected.div(counts, axis=0).fillna(0.0)


def variant_returns(
    root: Path,
    row: dict[str, str],
    refs: dict[str, pd.Series],
) -> dict[str, Any]:
    symbols = [symbol.strip().upper() for symbol in row["symbols"].split(",") if symbol.strip()]
    prices = price_frame(root, symbols)
    asset_returns = prices.pct_change().fillna(0.0)
    bil = refs["BIL"].reindex(asset_returns.index).fillna(0.0)
    params = json.loads(row["parameter_set"])
    score = score_frame(row["family_id"], row["indicator_concept"], params, prices)
    weights = weights_from_score(score, row["family_id"])
    cash_weight = (1.0 - weights.sum(axis=1)).clip(lower=0.0, upper=1.0)
    shifted_weights = weights.shift(1).fillna(0.0)
    shifted_cash = cash_weight.shift(1).fillna(1.0)
    sleeve_returns = (shifted_weights * asset_returns).sum(axis=1) + shifted_cash * bil

    strategy_returns = sleeve_returns.rename(row["variant_id"])
    if row["family_id"] == "portfolio_combination_sleeve_ensemble":
        active_combo = refs["active_combo"].reindex(strategy_returns.index).fillna(0.0)
        aligned = pd.concat([sleeve_returns, active_combo], axis=1, join="inner").dropna()
        strategy_returns = (aligned.iloc[:, 0] * 0.50 + aligned.iloc[:, 1] * 0.50).rename(row["variant_id"])

    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    trade_count = int((turnover > 0.01).sum())
    avg_turnover = float(turnover.mean()) if len(turnover) else 0.0
    avg_cash = float(cash_weight.mean()) if len(cash_weight) else 1.0
    max_symbol_weight = float(weights.max(axis=1).max()) if not weights.empty else 0.0
    avg_symbols_held = float((weights > 0).sum(axis=1).mean()) if not weights.empty else 0.0
    return {
        "returns": strategy_returns.dropna(),
        "sleeve_returns": sleeve_returns.reindex(strategy_returns.index).fillna(0.0),
        "trade_count": trade_count,
        "avg_turnover": avg_turnover,
        "avg_cash_allocation": avg_cash,
        "max_symbol_weight": max_symbol_weight,
        "avg_symbols_held": avg_symbols_held,
        "start_date": strategy_returns.index.min().date().isoformat(),
        "end_date": strategy_returns.index.max().date().isoformat(),
        "data_window_length": int(strategy_returns.shape[0]),
    }


def equity_curve(returns: pd.Series) -> pd.Series:
    return STARTING_EQUITY * (1.0 + returns.fillna(0.0)).cumprod()


def drawdown_dollars(equity: pd.Series) -> pd.Series:
    return equity - equity.cummax()


def rolling_window_stats(returns: pd.Series) -> dict[str, float]:
    if len(returns) < ROLLING_WINDOW_DAYS:
        return {
            "median_final": float("nan"),
            "mean_final": float("nan"),
            "worst_final": float("nan"),
            "worst_drawdown": float("nan"),
            "target_300_before_stop_rate": float("nan"),
            "target_400_before_stop_rate": float("nan"),
            "stop_hit_rate": float("nan"),
        }
    finals: list[float] = []
    worst_drawdowns: list[float] = []
    target_300_hits: list[bool] = []
    target_400_hits: list[bool] = []
    stop_hits: list[bool] = []
    values = returns.dropna().to_numpy(dtype=float)
    max_start = len(values) - ROLLING_WINDOW_DAYS
    step = max(1, math.ceil(max_start / 64)) if max_start else 1
    starts = list(range(0, max_start + 1, step))
    if starts[-1] != max_start:
        starts.append(max_start)
    for start in starts:
        window = values[start : start + ROLLING_WINDOW_DAYS]
        equity = STARTING_EQUITY * np.cumprod(1.0 + window)
        dd = equity - np.maximum.accumulate(equity)
        finals.append(float(equity[-1]))
        worst_drawdowns.append(float(dd.min()))
        stop_indexes = np.flatnonzero(dd <= -600.0)
        stop_index = int(stop_indexes[0]) if len(stop_indexes) else None
        target_300_indexes = np.flatnonzero(equity >= TARGET_300)
        target_400_indexes = np.flatnonzero(equity >= TARGET_400)
        target_300_hits.append(bool(len(target_300_indexes) and (stop_index is None or int(target_300_indexes[0]) < stop_index)))
        target_400_hits.append(bool(len(target_400_indexes) and (stop_index is None or int(target_400_indexes[0]) < stop_index)))
        stop_hits.append(bool(len(stop_indexes)))
    return {
        "median_final": float(pd.Series(finals).median()),
        "mean_final": float(pd.Series(finals).mean()),
        "worst_final": float(pd.Series(finals).min()),
        "worst_drawdown": float(pd.Series(worst_drawdowns).min()),
        "target_300_before_stop_rate": float(pd.Series(target_300_hits).mean()),
        "target_400_before_stop_rate": float(pd.Series(target_400_hits).mean()),
        "stop_hit_rate": float(pd.Series(stop_hits).mean()),
    }


def metrics_for_returns(returns: pd.Series) -> dict[str, float]:
    returns = returns.dropna()
    equity = equity_curve(returns)
    dd = drawdown_dollars(equity)
    total_return = float(equity.iloc[-1] / STARTING_EQUITY - 1.0) if len(equity) else 0.0
    annualized = (1.0 + total_return) ** (252.0 / len(returns)) - 1.0 if len(returns) and total_return > -1.0 else float("nan")
    vol = float(returns.std() * math.sqrt(252.0)) if len(returns) > 1 else 0.0
    sharpe = float((returns.mean() / returns.std()) * math.sqrt(252.0)) if len(returns) > 1 and returns.std() != 0 else 0.0
    rolling = rolling_window_stats(returns)
    max_dd = float(dd.min()) if len(dd) else 0.0
    return {
        "ending_equity": float(equity.iloc[-1]) if len(equity) else STARTING_EQUITY,
        "total_return": total_return,
        "annualized_return": annualized,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "max_drawdown_pct": float(((equity / equity.cummax()) - 1.0).min()) if len(equity) else 0.0,
        "risk_buffer_vs_minus_600": 600.0 + max_dd,
        "stop_risk_breach_flag": bool(max_dd <= -600.0),
        "180d_median_final_equity": rolling["median_final"],
        "180d_mean_final_equity": rolling["mean_final"],
        "180d_worst_final_equity": rolling["worst_final"],
        "180d_worst_drawdown": rolling["worst_drawdown"],
        "target_300_before_stop_rate": rolling["target_300_before_stop_rate"],
        "target_400_before_stop_rate": rolling["target_400_before_stop_rate"],
        "stop_hit_rate": rolling["stop_hit_rate"],
    }


def aligned_metric_delta(variant_returns_series: pd.Series, ref: pd.Series) -> dict[str, float]:
    aligned = pd.concat([variant_returns_series, ref], axis=1, join="inner").dropna()
    if aligned.empty:
        return {"correlation": float("nan"), "delta_180d_median_final_equity": float("nan"), "ref_180d_median_final_equity": float("nan")}
    variant_metrics = metrics_for_returns(aligned.iloc[:, 0])
    ref_metrics = metrics_for_returns(aligned.iloc[:, 1])
    corr = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])) if len(aligned) > 2 else float("nan")
    return {
        "correlation": corr,
        "delta_180d_median_final_equity": variant_metrics["180d_median_final_equity"] - ref_metrics["180d_median_final_equity"],
        "ref_180d_median_final_equity": ref_metrics["180d_median_final_equity"],
    }


def safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number


def assign_status(row: dict[str, Any]) -> str:
    if row["data_blocked"]:
        return "sandbox_data_blocked"
    positive = bool(row["positive_objective_progress"])
    drawdown_ok = bool(row["basic_drawdown_screen_pass"])
    beats_combo = bool(row["beats_active_combo"])
    low_corr = bool(row["low_correlation_to_active_combo"])
    if row["family_id"] == "portfolio_combination_sleeve_ensemble" and positive and drawdown_ok and (beats_combo or low_corr):
        return "sandbox_portfolio_sleeve_candidate"
    if positive and drawdown_ok and beats_combo:
        return "sandbox_component_candidate"
    if positive and drawdown_ok:
        return "sandbox_family_interesting"
    if positive:
        return "sandbox_family_weak"
    return "sandbox_discard"


def evaluate_variants(root: Path, plan_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    refs = reference_returns(root)
    variant_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    diversification_rows: list[dict[str, Any]] = []
    for row in plan_rows:
        try:
            payload = variant_returns(root, row, refs)
            returns = payload["returns"]
            metrics = metrics_for_returns(returns)
            active_combo_delta = aligned_metric_delta(returns, refs["active_combo"])
            correlations = {name: aligned_metric_delta(returns, ref)["correlation"] for name, ref in refs.items()}
            result = {
                **row,
                **payload,
                **metrics,
                "data_blocked": False,
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "delta_vs_active_combo_180d_median": active_combo_delta["delta_180d_median_final_equity"],
                "corr_vs_active_combo": correlations.get("active_combo"),
                "corr_vs_active_vm": correlations.get("active_vm"),
                "corr_vs_active_dsr": correlations.get("active_dsr"),
                "corr_vs_spy": correlations.get("SPY"),
                "corr_vs_qqq": correlations.get("QQQ"),
                "corr_vs_static_all_weather": correlations.get("static_all_weather"),
            }
            result["positive_objective_progress"] = bool(
                result["ending_equity"] > STARTING_EQUITY or result["180d_median_final_equity"] > STARTING_EQUITY
            )
            result["beats_active_combo"] = bool(safe_float(result["delta_vs_active_combo_180d_median"]) > 0)
            result["basic_drawdown_screen_pass"] = bool(result["max_drawdown"] > -600.0 and result["180d_worst_drawdown"] > -600.0)
            result["low_correlation_to_active_combo"] = bool(abs(safe_float(result["corr_vs_active_combo"])) < 0.75)
            result["exploratory_score"] = (
                (safe_float(result["180d_median_final_equity"]) - STARTING_EQUITY) / 100.0
                + max(min(safe_float(result["risk_buffer_vs_minus_600"]) / 100.0, 5.0), -5.0)
                + max(min(safe_float(result["delta_vs_active_combo_180d_median"]) / 100.0, 5.0), -5.0)
                - max(safe_float(result["max_symbol_weight"]) - 0.60, 0.0)
            )
            result["status"] = assign_status(result)
            if result["status"] in FORBIDDEN_STATUSES:
                raise RuntimeError(f"forbidden status generated: {result['status']}")
            variant_results.append(result)

            for benchmark_id, ref in refs.items():
                comparison = aligned_metric_delta(returns, ref)
                benchmark_rows.append(
                    {
                        "variant_id": row["variant_id"],
                        "family_id": row["family_id"],
                        "benchmark_id": benchmark_id,
                        "correlation": comparison["correlation"],
                        "delta_180d_median_final_equity": comparison["delta_180d_median_final_equity"],
                        "benchmark_180d_median_final_equity": comparison["ref_180d_median_final_equity"],
                    }
                )
            diversification_rows.append(
                {
                    "variant_id": row["variant_id"],
                    "family_id": row["family_id"],
                    "corr_vs_active_combo": result["corr_vs_active_combo"],
                    "corr_vs_active_vm": result["corr_vs_active_vm"],
                    "corr_vs_active_dsr": result["corr_vs_active_dsr"],
                    "corr_vs_spy": result["corr_vs_spy"],
                    "corr_vs_qqq": result["corr_vs_qqq"],
                    "corr_vs_static_all_weather": result["corr_vs_static_all_weather"],
                    "low_correlation_to_active_combo": result["low_correlation_to_active_combo"],
                }
            )
        except Exception as exc:
            blocked = {
                **row,
                "data_blocked": True,
                "block_reason": str(exc),
                "status": "sandbox_data_blocked",
                "promotable": "false",
                "paper_candidate_allowed": "false",
            }
            variant_results.append(blocked)
    return variant_results, benchmark_rows, diversification_rows


def family_summaries(variant_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(variant_results)
    rows: list[dict[str, Any]] = []
    for family_id, group in frame.groupby("family_id", sort=True):
        evaluated = group[group["status"] != "sandbox_data_blocked"]
        best = evaluated.sort_values("exploratory_score", ascending=False).iloc[0] if not evaluated.empty else group.iloc[0]
        positive_count = int(group.get("positive_objective_progress", pd.Series(dtype=bool)).fillna(False).sum())
        beating_combo_count = int(group.get("beats_active_combo", pd.Series(dtype=bool)).fillna(False).sum())
        drawdown_pass_count = int(group.get("basic_drawdown_screen_pass", pd.Series(dtype=bool)).fillna(False).sum())
        low_corr_count = int(group.get("low_correlation_to_active_combo", pd.Series(dtype=bool)).fillna(False).sum())
        data_blocked_count = int((group["status"] == "sandbox_data_blocked").sum())
        variant_count = int(len(group))
        interesting = positive_count >= 2 and drawdown_pass_count >= max(2, variant_count // 3)
        future_candidate = bool(
            positive_count >= max(3, variant_count // 2)
            and beating_combo_count >= 2
            and drawdown_pass_count >= max(3, variant_count // 2)
            and data_blocked_count == 0
        )
        status = "sandbox_family_interesting" if interesting else "sandbox_family_weak"
        if data_blocked_count == variant_count:
            status = "sandbox_data_blocked"
        if future_candidate:
            status = "sandbox_future_preregistration_candidate"
        rows.append(
            {
                "family_id": family_id,
                "family_status": status,
                "best_variant_by_exploratory_score": best.get("variant_id", ""),
                "best_exploratory_score": best.get("exploratory_score", ""),
                "median_180d_final_equity": safe_float(evaluated["180d_median_final_equity"].median()) if not evaluated.empty else "",
                "median_ending_equity": safe_float(evaluated["ending_equity"].median()) if not evaluated.empty else "",
                "worst_180d_final_equity": safe_float(evaluated["180d_worst_final_equity"].min()) if not evaluated.empty else "",
                "worst_max_drawdown": safe_float(evaluated["max_drawdown"].min()) if not evaluated.empty else "",
                "variants_tested": variant_count,
                "variants_data_blocked": data_blocked_count,
                "variants_positive_objective_progress": positive_count,
                "variants_beating_active_combo": beating_combo_count,
                "variants_passing_basic_drawdown_screen": drawdown_pass_count,
                "variants_low_correlation_to_active_combo": low_corr_count,
                "possible_future_preregistration_candidate": future_candidate,
                "robustness_notes": "multiple variants show similar positive/drawdown behavior" if interesting else "insufficient family-level robustness",
                "overfitting_risk_notes": "exploratory only; single best row and parameter winner blocked from promotion",
            }
        )
    return rows


def aggregate_by_family(rows: list[dict[str, Any]], metrics: list[str]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    out: list[dict[str, Any]] = []
    for family_id, group in frame.groupby("family_id", sort=True):
        item = {"family_id": family_id, "variants": len(group)}
        for metric in metrics:
            if metric in group:
                item[f"median_{metric}"] = safe_float(pd.to_numeric(group[metric], errors="coerce").median())
                item[f"worst_{metric}"] = safe_float(pd.to_numeric(group[metric], errors="coerce").min())
        out.append(item)
    return out


def benchmark_family_summary(benchmark_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(benchmark_rows)
    rows: list[dict[str, Any]] = []
    for (family_id, benchmark_id), group in frame.groupby(["family_id", "benchmark_id"], sort=True):
        rows.append(
            {
                "family_id": family_id,
                "benchmark_id": benchmark_id,
                "variant_count": len(group),
                "median_delta_180d_median_final_equity": safe_float(
                    pd.to_numeric(group["delta_180d_median_final_equity"], errors="coerce").median()
                ),
                "best_delta_180d_median_final_equity": safe_float(
                    pd.to_numeric(group["delta_180d_median_final_equity"], errors="coerce").max()
                ),
                "median_correlation": safe_float(pd.to_numeric(group["correlation"], errors="coerce").median()),
            }
        )
    return rows


def md_family_summary(rows: list[dict[str, Any]]) -> str:
    lines = ["# Sandbox Family Summary", "", "Family-level results are exploratory and non-promotable.", ""]
    for row in rows:
        lines.append(f"## `{row['family_id']}`")
        lines.append(f"- Status: `{row['family_status']}`")
        lines.append(f"- Variants tested: `{row['variants_tested']}`")
        lines.append(f"- Positive objective progress variants: `{row['variants_positive_objective_progress']}`")
        lines.append(f"- Variants beating active combo: `{row['variants_beating_active_combo']}`")
        lines.append(f"- Basic drawdown-screen passes: `{row['variants_passing_basic_drawdown_screen']}`")
        lines.append(f"- Best exploratory-score variant: `{row['best_variant_by_exploratory_score']}`")
        lines.append(f"- Future preregistration candidate: `{row['possible_future_preregistration_candidate']}`")
        lines.append(f"- Robustness notes: {row['robustness_notes']}")
        lines.append("")
    return "\n".join(lines)


def md_overfitting(rows: list[dict[str, Any]]) -> str:
    return """# Sandbox Overfitting Risk Summary

- Best single variant cannot be promoted.
- Best parameter cannot be promoted.
- Best family cannot move directly to promotion review.
- Future candidate requires separate preregistration.
- Exact rejected variants remain closed.
- Indicators cannot be added after results to rescue rows.
- No gate weakening after results.
- No paper-forward activation.
- No real-money recommendation.

Family-level robustness is summarized in `sandbox_family_summary.csv`; single-row winners are treated as diagnostic only.
"""


def md_leverage() -> str:
    return """# Sandbox Research-Only Leverage Summary

Leverage sensitivity status: `not_implemented_in_this_batch`

No leverage diagnostic was used to improve, rescue, or promote any strategy. No broker, margin, live, or real-money leverage path was touched.
"""


def md_future_candidates(family_rows: list[dict[str, Any]]) -> str:
    candidates = [row for row in family_rows if row["possible_future_preregistration_candidate"]]
    lines = ["# Sandbox Future Preregistration Candidates", ""]
    if not candidates:
        lines.append("Future preregistration candidate count: `0`")
        lines.append("")
        lines.append("No family is promoted or paper-forward eligible from this batch.")
    else:
        lines.append(f"Future preregistration candidate count: `{len(candidates)}`")
        lines.append("")
        for row in candidates:
            lines.append(f"- `{row['family_id']}`: requires separate audit and preregistration before any further work.")
    return "\n".join(lines)


def md_discarded(family_rows: list[dict[str, Any]]) -> str:
    weak = [row for row in family_rows if row["family_status"] in {"sandbox_family_weak", "sandbox_data_blocked"}]
    lines = ["# Sandbox Discarded Or Weak Families", ""]
    if not weak:
        lines.append("No family was cleanly discarded; audit is required because the opportunity map has mixed results.")
    for row in weak:
        lines.append(f"- `{row['family_id']}`: `{row['family_status']}`; {row['robustness_notes']}")
    return "\n".join(lines)


def md_do_not_promote() -> str:
    return """# Sandbox Do Not Promote

All batch outputs remain `non_promotable_exploration`.

Forbidden from this batch:

- promotion-review candidates
- candidate_exhaustive candidates
- paper-forward candidates
- paper-forward activation
- demo-active or live-ready labels
- broker/live-order paths
- real-money recommendations

Any future work must start with a separate audit and preregistration.
"""


def md_next_action(next_action: str) -> str:
    return f"""# Sandbox Batch Next Action

Exact next action: `{next_action}`

Do not run the next action in this batch task.
"""


def md_preflight(pre: dict[str, Any]) -> str:
    failures = "\n".join(f"- {item}" for item in pre["failures"]) or "- none"
    warnings = "\n".join(f"- {item}" for item in pre["warnings"]) or "- none"
    return f"""# Sandbox Batch Preflight Report

Preflight passed: `{pre['preflight_passed']}`

Variant count planned: `{pre['variant_count_planned']}`

Implementation packet check: `{pre['implementation_packet_note']}`

Failures:

{failures}

Warnings:

{warnings}
"""


def md_summary(manifest: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    candidate_count = manifest["sandbox_future_preregistration_candidate_count"]
    interesting = [row["family_id"] for row in family_rows if row["family_status"] in {"sandbox_family_interesting", "sandbox_future_preregistration_candidate"}]
    weak = [row["family_id"] for row in family_rows if row["family_status"] in {"sandbox_family_weak", "sandbox_data_blocked"}]
    return f"""# Exploratory Sandbox Batch 001 Summary

Sandbox batch run: `{manifest['sandbox_batch_run']}`

Variant count planned: `{manifest['variant_count_planned']}`

Variant count evaluated: `{manifest['variant_count_evaluated']}`

Families evaluated: `{manifest['families_evaluated_count']}`

Future preregistration candidate count: `{candidate_count}`

Interesting families: `{', '.join(interesting) or 'none'}`

Weak/data-blocked families: `{', '.join(weak) or 'none'}`

Next action: `{manifest['next_action']}`

All results remain `non_promotable_exploration`; no candidate_exhaustive, paper-forward, broker/live, provider-download, intraday, or real-money action occurred.
"""


def decide_next_action(family_rows: list[dict[str, Any]], preflight_passed: bool) -> str:
    if not preflight_passed:
        return NEXT_ACTION_MANUAL
    if all(row["family_status"] in {"sandbox_family_weak", "sandbox_data_blocked"} for row in family_rows):
        return NEXT_ACTION_PAUSE
    return NEXT_ACTION_AUDIT


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before = deepcopy(metadata)
    metadata.update(
        {
            "exploratory_sandbox_batch_001_path": str(output.resolve()),
            "exploratory_sandbox_batch_001_status": "completed_non_promotable_exploration",
            "exploratory_sandbox_batch_001_created_utc": created_utc,
            "current_research_mode": "exploratory_sandbox_batch_completed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_batch_run": True,
            "sandbox_batch_variant_count_planned": manifest["variant_count_planned"],
            "sandbox_batch_variant_count_evaluated": manifest["variant_count_evaluated"],
            "sandbox_future_preregistration_candidate_count": manifest["sandbox_future_preregistration_candidate_count"],
            "sandbox_results_non_promotable": True,
            "sandbox_can_create_paper_candidates": False,
            "sandbox_strategy_discovery_run": False,
            "sandbox_formal_discovery_run": False,
            "sandbox_trading_backtests_run": True,
            "sandbox_exploratory_metrics_computed": True,
            "sandbox_new_promotable_strategy_metrics_computed": False,
            "sandbox_provider_download": False,
            "sandbox_intraday_data_used": False,
            "sandbox_candidate_exhaustive_run": False,
            "sandbox_paper_forward_review": False,
            "sandbox_paper_forward_activation": False,
            "sandbox_broker_orders_submitted": False,
            "sandbox_broker_orders_cancelled": False,
            "sandbox_live_orders": False,
            "sandbox_real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_text = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `exploratory_sandbox_batch_completed`
- Official current next action: `{manifest['next_action']}`
- Exploratory sandbox batch evidence: `{output.resolve()}`
- Sandbox batch run: `true`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['families_evaluated_count']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Sandbox results are non-promotable: `true`
- Sandbox can create paper candidates: `false`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed; old managed-futures top1/top2 rows remain historical context only.
- Intraday remains paused: `true`
- This batch did not run formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation.
"""
    section = f"""## Exploratory Sandbox Batch 001

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Sandbox batch run: `true`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['families_evaluated_count']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Best single variant promoted: `false`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this batch task.
- No formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation occurred.
"""
    after = replace_or_append_section(before_text, "## Compact Current State", compact)
    after = replace_or_append_section(after, "## Exploratory Sandbox Batch 001", section)
    write_text(roadmap_path, after)
    return before != metadata, before_text != after


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    rows = []
    result_path = output / "sandbox_variant_results.csv"
    if result_path.exists():
        with result_path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    statuses = {row.get("status", "") for row in rows}
    check = {
        "sandbox_batch_run_mode": manifest["sandbox_batch_run"] is True,
        "results_non_promotable": manifest["sandbox_results_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "variant_count_planned_bounded": manifest["variant_count_planned"] <= MAX_TOTAL_FUTURE_VARIANTS,
        "variant_count_evaluated_bounded": manifest["variant_count_evaluated"] <= MAX_TOTAL_FUTURE_VARIANTS,
        "every_result_allowed_status": statuses <= set(ALLOWED_SANDBOX_STATUSES),
        "forbidden_statuses_absent": not (statuses & set(FORBIDDEN_STATUSES)),
        "no_result_promotable": all(row.get("promotable") == "false" for row in rows),
        "no_result_paper_candidate_allowed": all(row.get("paper_candidate_allowed") == "false" for row in rows),
        "family_summary_exists": (output / "sandbox_family_summary.csv").exists(),
        "benchmark_comparison_summary_exists": (output / "sandbox_benchmark_comparison_summary.csv").exists(),
        "risk_summary_exists": (output / "sandbox_risk_summary.csv").exists(),
        "diversification_summary_exists": (output / "sandbox_diversification_summary.csv").exists(),
        "overfitting_risk_summary_exists": (output / "sandbox_overfitting_risk_summary.md").exists(),
        "do_not_promote_file_exists": (output / "sandbox_do_not_promote.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_BATCH_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_OUTPUT_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def create_packet(output: Path) -> Path:
    packet = output / "sandbox_batch_packet.zip"
    with zipfile.ZipFile(packet, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path == packet or path.suffix == ".zip":
                continue
            archive.write(path, path.name)
    return packet


def run_sandbox_batch(
    root: Path = ROOT,
    *,
    batch_id: str = "batch_001",
    max_variants: int = MAX_TOTAL_FUTURE_VARIANTS,
    update_registry: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_ROOT / batch_id / "latest"
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    pre = preflight(root, max_variants)
    plan_rows = load_plan_rows(root)
    variant_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    diversification_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    if pre["preflight_passed"]:
        variant_results, benchmark_rows, diversification_rows = evaluate_variants(root, plan_rows[:max_variants])
        family_rows = family_summaries(variant_results)
    next_action = decide_next_action(family_rows, pre["preflight_passed"])
    future_count = sum(1 for row in family_rows if row.get("possible_future_preregistration_candidate"))
    manifest = {
        "created_utc": created_utc,
        "batch_id": batch_id,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "variant_count_planned": pre["variant_count_planned"],
        "variant_count_evaluated": len(variant_results),
        "families_evaluated_count": len({row.get("family_id") for row in variant_results}),
        "sandbox_future_preregistration_candidate_count": future_count,
        "best_single_variant_promoted": False,
        "preflight_passed": pre["preflight_passed"],
        "preflight_failures": pre["failures"],
        "preflight_warnings": pre["warnings"],
        "next_action": next_action,
    }
    write_json(output / "sandbox_batch_manifest.json", manifest)
    write_text(output / "sandbox_batch_preflight_report.md", md_preflight(pre))

    result_fields = [
        "variant_id",
        "family_id",
        "universe_group",
        "symbols",
        "indicator_concept",
        "parameter_set",
        "status",
        "promotable",
        "paper_candidate_allowed",
        "exploratory_score",
        "ending_equity",
        "total_return",
        "annualized_return",
        "180d_median_final_equity",
        "target_300_before_stop_rate",
        "target_400_before_stop_rate",
        "max_drawdown",
        "180d_worst_drawdown",
        "risk_buffer_vs_minus_600",
        "volatility",
        "sharpe",
        "stop_risk_breach_flag",
        "delta_vs_active_combo_180d_median",
        "corr_vs_active_combo",
        "corr_vs_active_vm",
        "corr_vs_active_dsr",
        "corr_vs_spy",
        "corr_vs_qqq",
        "corr_vs_static_all_weather",
        "trade_count",
        "avg_turnover",
        "avg_cash_allocation",
        "avg_symbols_held",
        "max_symbol_weight",
        "data_window_length",
        "start_date",
        "end_date",
        "positive_objective_progress",
        "beats_active_combo",
        "basic_drawdown_screen_pass",
        "low_correlation_to_active_combo",
        "data_blocked",
    ]
    write_csv(output / "sandbox_variant_results.csv", variant_results, result_fields)
    family_fields = [
        "family_id",
        "family_status",
        "best_variant_by_exploratory_score",
        "best_exploratory_score",
        "median_180d_final_equity",
        "median_ending_equity",
        "worst_180d_final_equity",
        "worst_max_drawdown",
        "variants_tested",
        "variants_data_blocked",
        "variants_positive_objective_progress",
        "variants_beating_active_combo",
        "variants_passing_basic_drawdown_screen",
        "variants_low_correlation_to_active_combo",
        "possible_future_preregistration_candidate",
        "robustness_notes",
        "overfitting_risk_notes",
    ]
    write_csv(output / "sandbox_family_summary.csv", family_rows, family_fields)
    write_text(output / "sandbox_family_summary.md", md_family_summary(family_rows))
    write_csv(
        output / "sandbox_benchmark_comparison_summary.csv",
        benchmark_family_summary(benchmark_rows),
        ["family_id", "benchmark_id", "variant_count", "median_delta_180d_median_final_equity", "best_delta_180d_median_final_equity", "median_correlation"],
    )
    write_csv(
        output / "sandbox_risk_summary.csv",
        aggregate_by_family(variant_results, ["max_drawdown", "180d_worst_drawdown", "risk_buffer_vs_minus_600", "volatility", "stop_hit_rate"]),
        [
            "family_id",
            "variants",
            "median_max_drawdown",
            "worst_max_drawdown",
            "median_180d_worst_drawdown",
            "worst_180d_worst_drawdown",
            "median_risk_buffer_vs_minus_600",
            "worst_risk_buffer_vs_minus_600",
            "median_volatility",
            "worst_volatility",
            "median_stop_hit_rate",
            "worst_stop_hit_rate",
        ],
    )
    write_csv(
        output / "sandbox_diversification_summary.csv",
        aggregate_by_family(
            diversification_rows,
            ["corr_vs_active_combo", "corr_vs_active_vm", "corr_vs_active_dsr", "corr_vs_spy", "corr_vs_qqq", "corr_vs_static_all_weather"],
        ),
        [
            "family_id",
            "variants",
            "median_corr_vs_active_combo",
            "worst_corr_vs_active_combo",
            "median_corr_vs_active_vm",
            "worst_corr_vs_active_vm",
            "median_corr_vs_active_dsr",
            "worst_corr_vs_active_dsr",
            "median_corr_vs_spy",
            "worst_corr_vs_spy",
            "median_corr_vs_qqq",
            "worst_corr_vs_qqq",
            "median_corr_vs_static_all_weather",
            "worst_corr_vs_static_all_weather",
        ],
    )
    write_csv(
        output / "sandbox_practicality_summary.csv",
        aggregate_by_family(variant_results, ["trade_count", "avg_turnover", "avg_cash_allocation", "avg_symbols_held", "max_symbol_weight", "data_window_length"]),
        [
            "family_id",
            "variants",
            "median_trade_count",
            "worst_trade_count",
            "median_avg_turnover",
            "worst_avg_turnover",
            "median_avg_cash_allocation",
            "worst_avg_cash_allocation",
            "median_avg_symbols_held",
            "worst_avg_symbols_held",
            "median_max_symbol_weight",
            "worst_max_symbol_weight",
            "median_data_window_length",
            "worst_data_window_length",
        ],
    )
    write_text(output / "sandbox_overfitting_risk_summary.md", md_overfitting(family_rows))
    write_text(output / "sandbox_research_only_leverage_summary.md", md_leverage())
    write_text(output / "sandbox_future_preregistration_candidates.md", md_future_candidates(family_rows))
    write_text(output / "sandbox_discarded_or_weak_families.md", md_discarded(family_rows))
    write_text(output / "sandbox_do_not_promote.md", md_do_not_promote())
    write_text(output / "sandbox_batch_next_action.md", md_next_action(next_action))
    write_text(output / "sandbox_batch_summary.md", md_summary(manifest, family_rows))
    after_strategies = strategy_snapshot(root)
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    if update_registry:
        registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
        manifest["registry_metadata_updated"] = registry_updated
        manifest["roadmap_updated"] = roadmap_updated
    else:
        manifest["registry_metadata_updated"] = False
        manifest["roadmap_updated"] = False
    consistency = consistency_check(manifest, output)
    write_json(output / "sandbox_batch_manifest.json", manifest)
    write_json(output / "sandbox_batch_consistency_check.json", consistency)
    packet = create_packet(output)
    manifest["sandbox_batch_packet_created"] = packet.exists()
    manifest["sandbox_batch_packet_path"] = str(packet.resolve())
    consistency = consistency_check(manifest, output)
    write_json(output / "sandbox_batch_manifest.json", manifest)
    write_json(output / "sandbox_batch_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "variant_count_planned": manifest["variant_count_planned"],
        "variant_count_evaluated": manifest["variant_count_evaluated"],
        "families_evaluated_count": manifest["families_evaluated_count"],
        "sandbox_future_preregistration_candidate_count": manifest["sandbox_future_preregistration_candidate_count"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
