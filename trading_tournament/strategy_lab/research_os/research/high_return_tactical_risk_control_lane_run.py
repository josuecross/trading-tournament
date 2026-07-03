from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import LANE_ID
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_v2_audit import (
    OUTPUT_DIR as PATCH_V2_AUDIT_DIR,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    Variant,
    active_combo_returns,
    benchmark_delta,
    benchmark_returns,
    cache_inventory,
    complete_rebalance_weight_frame,
    contribution_metrics,
    equity_curve,
    implementation_practicality_score,
    load_prices,
    load_price_series,
    max_drawdown,
    month_rebalance_mask,
    rolling_window_stats,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_v2" / "latest"
)
METHODOLOGY_SOURCE = (
    Path("evidence")
    / "research_recovery"
    / "profit_oriented_research_batch_v1_methodology_fix"
    / "latest"
    / "corrected_profit_research_variant_results.csv"
)
LABEL_SOURCE = (
    Path("evidence")
    / "research_recovery"
    / "profit_oriented_research_batch_v1_labeling_fix"
    / "latest"
    / "corrected_label_variant_results.csv"
)
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run" / "latest"

SOURCE_FAMILY = "high_return_tactical_etf_equity_index"
VARIANT_COUNT_PLANNED = 24
WEIGHT_TOLERANCE = 1e-6

NEXT_ACTION_AUDIT = "audit_high_return_tactical_risk_control_research_lane_results"
NEXT_ACTION_FIX = "fix_high_return_tactical_risk_control_lane_run_methodology_issue"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_run"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

ALLOWED_LABELS = {
    "risk_control_signal_promising",
    "risk_control_signal_tradeoff_interesting",
    "risk_control_signal_return_destroyed",
    "risk_control_signal_drawdown_not_fixed",
    "risk_control_signal_duplicate_existing_active",
    "risk_control_signal_data_blocked",
    "risk_control_signal_weak",
}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_run_manifest.json",
    "risk_control_lane_run_summary.md",
    "local_cache_run_preflight.md",
    "variant_run_results.csv",
    "variant_run_results.md",
    "family_run_summary.csv",
    "family_run_summary.md",
    "baseline_comparison_results.csv",
    "baseline_comparison_review.md",
    "exposure_invariant_report.md",
    "cash_bil_invariant_report.md",
    "risk_control_label_summary.md",
    "promising_risk_control_signals.md",
    "tradeoff_interesting_signals.md",
    "return_destroyed_signals.md",
    "drawdown_not_fixed_signals.md",
    "duplicate_existing_active_signals.md",
    "do_not_promote_from_risk_control_lane_run.md",
    "risk_control_lane_run_next_action.md",
    "risk_control_lane_run_consistency_check.json",
)

VARIANT_RESULT_FIELDS = (
    "lane_id",
    "source_family",
    "variant_id",
    "baseline_variant_id",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "risk_control_concept",
    "data_availability_status",
    "missing_symbols",
    "start_date",
    "end_date",
    "total_return",
    "cagr",
    "max_drawdown",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_calmar_or_return_drawdown_proxy",
    "drawdown_reduction_vs_baseline",
    "cagr_retention_vs_baseline",
    "calmar_improvement_vs_baseline",
    "spy_total_return_delta",
    "bil_cash_total_return_delta",
    "active_vm_dsr_comparison",
    "active_combo_correlation",
    "active_combo_blend_total_return_delta",
    "active_combo_blend_drawdown_delta",
    "static_all_weather_comparison",
    "average_exposure",
    "max_daily_exposure",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "trade_count",
    "rebalance_count",
    "turnover_proxy",
    "duplicate_reference_correlation",
    "baseline_correlation",
    "spy200d_reference_correlation",
    "worst_180_day_window",
    "best_180_day_window",
    "positive_180_day_window_ratio",
    "risk_control_research_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "max_daily_weight_sum",
    "average_weight_sum",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "methodology_notes",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_ratio(numerator: float, denominator: float) -> float:
    if math.isnan(numerator) or math.isnan(denominator) or abs(denominator) < 1e-12:
        return float("nan")
    return numerator / denominator


def pct_reduction(old_drawdown: float, new_drawdown: float) -> float:
    if math.isnan(old_drawdown) or math.isnan(new_drawdown) or old_drawdown >= 0:
        return float("nan")
    return max(0.0, (abs(old_drawdown) - abs(new_drawdown)) / abs(old_drawdown))


def calmar_improvement(baseline_calmar: float, run_calmar: float) -> float:
    if math.isnan(baseline_calmar) or math.isnan(run_calmar) or abs(baseline_calmar) < 1e-12:
        return float("nan")
    return (run_calmar - baseline_calmar) / abs(baseline_calmar)


def volatility_multiplier(annualized_volatility: float | None, *, enough_history: bool = True) -> float:
    if not enough_history or annualized_volatility is None or math.isnan(float(annualized_volatility)):
        return 1.0
    if annualized_volatility <= 0.25:
        return 1.0
    if annualized_volatility <= 0.35:
        return 0.5
    return 0.25


def drawdown_guard_multiplier(
    prior_controlled_drawdown: float,
    *,
    guard_active: bool,
    active_multiplier: float,
) -> tuple[float, bool]:
    if prior_controlled_drawdown <= -0.25:
        return 0.0, True
    if prior_controlled_drawdown <= -0.15:
        return 0.5, True
    if guard_active and prior_controlled_drawdown <= -0.10:
        return active_multiplier, True
    return 1.0, False


def combined_risky_multiplier(*multipliers: float) -> float:
    clean = [float(value) for value in multipliers if value is not None and not math.isnan(float(value))]
    if not clean:
        return 1.0
    return max(0.0, min(1.0, min(clean)))


def apply_multiplier_to_weights(base_weights: pd.Series, multiplier: float, *, cash_symbol: str = "BIL") -> pd.Series:
    result = pd.Series(0.0, index=base_weights.index, dtype=float)
    risky_symbols = [symbol for symbol in result.index if symbol != cash_symbol]
    risky_sum = float(base_weights.reindex(risky_symbols).fillna(0.0).sum())
    scale = combined_risky_multiplier(multiplier)
    if risky_sum > 0:
        result.loc[risky_symbols] = base_weights.reindex(risky_symbols).fillna(0.0) * scale
    if cash_symbol in result.index:
        result.loc[cash_symbol] = max(0.0, 1.0 - float(result.loc[risky_symbols].sum()))
    return result.clip(lower=0.0)


def load_design(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, Any]]:
    variants = read_csv_rows(root / SOURCE_DESIGN_DIR / "patched_v2_variant_design_table.csv")
    mappings = read_csv_rows(root / SOURCE_DESIGN_DIR / "baseline_mapping_table.csv")
    methodology = {row["variant_id"]: row for row in read_csv_rows(root / METHODOLOGY_SOURCE)}
    labels = {row["variant_id"]: row for row in read_csv_rows(root / LABEL_SOURCE)}
    audit_manifest = read_json(root / PATCH_V2_AUDIT_DIR / "risk_control_lane_design_patch_v2_audit_manifest.json")
    return variants, mappings, methodology, labels, audit_manifest


def available_symbols(root: Path) -> set[str]:
    return {str(row["symbol"]) for row in cache_inventory(root) if row.get("status") == "cache_ready"}


@lru_cache(maxsize=64)
def cached_prices(root_text: str, symbols: tuple[str, ...]) -> pd.DataFrame:
    return load_prices(Path(root_text), symbols)


@lru_cache(maxsize=32)
def cached_price_series(root_text: str, symbol: str) -> pd.Series:
    return load_price_series(Path(root_text), symbol)


@lru_cache(maxsize=32)
def build_baseline_weights_cached(
    root_text: str,
    universe: tuple[str, ...],
    baseline_variant_id: str,
    lookback: int,
    top_n: int,
    universe_group: str,
) -> tuple[pd.Series, pd.DataFrame]:
    variant = Variant(
        family_id=SOURCE_FAMILY,
        variant_id=baseline_variant_id,
        strategy_type="monthly_momentum",
        universe=universe,
        params={"lookback": int(lookback), "top_n": int(top_n), "trend_filter": False},
        rule_summary="Monthly high-return tactical baseline used for risk-control comparison.",
        parameter_sensitivity_group=f"{universe_group}_mom{lookback}",
    )
    prices = cached_prices(root_text, variant.universe)
    if prices.empty or len(prices.dropna(how="all")) < 252:
        return pd.Series(dtype=float), pd.DataFrame()
    prices = prices.ffill()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    scores = prices.pct_change(int(variant.params["lookback"]), fill_method=None).shift(1)
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    cash_symbol = "BIL" if "BIL" in prices.columns else None
    for date in prices.index[month_rebalance_mask(prices.index)]:
        score = scores.loc[date].dropna()
        if cash_symbol:
            score = score.drop(cash_symbol, errors="ignore")
        selected = list(score.sort_values(ascending=False).head(int(variant.params["top_n"])).index)
        target = {symbol: 0.0 for symbol in prices.columns}
        if selected:
            selected_weight = 1.0 / len(selected)
            for symbol in selected:
                target[symbol] = selected_weight
        elif cash_symbol:
            target[cash_symbol] = 1.0
        rebalance_targets[pd.Timestamp(date)] = target
    weights = complete_rebalance_weight_frame(prices.index, list(prices.columns), rebalance_targets)
    baseline_daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    return baseline_daily, weights


def build_baseline_weights(root: Path, row: dict[str, str]) -> tuple[pd.Series, pd.DataFrame]:
    universe = tuple(symbol for symbol in row["universe"].split("|") if symbol)
    return build_baseline_weights_cached(
        str(root),
        universe,
        row["baseline_variant_id"],
        int(row["momentum_lookback_days"]),
        int(row["top_n"]),
        row["universe_group"],
    )


def spy200d_risk_on(root: Path, index: pd.DatetimeIndex) -> pd.Series:
    spy = cached_prices(str(root), ("SPY",))
    if spy.empty or "SPY" not in spy.columns:
        return pd.Series(False, index=index)
    spy_series = spy["SPY"].ffill()
    prior_spy = spy_series.shift(1)
    prior_sma = spy_series.shift(1).rolling(200, min_periods=100).mean()
    risk_on = (prior_spy > prior_sma).reindex(index).ffill().fillna(False)
    return risk_on.astype(bool)


def reference_spy200d_returns(root: Path, index: pd.DatetimeIndex) -> pd.Series:
    prices = cached_prices(str(root), ("SPY", "BIL")).ffill()
    if prices.empty or not {"SPY", "BIL"}.issubset(prices.columns):
        return pd.Series(dtype=float, name="SPY_200d")
    returns = prices.pct_change(fill_method=None).fillna(0.0).reindex(index).fillna(0.0)
    risk_on = spy200d_risk_on(root, index)
    out = pd.Series(0.0, index=index, name="SPY_200d")
    out.loc[risk_on] = returns.loc[risk_on, "SPY"]
    out.loc[~risk_on] = returns.loc[~risk_on, "BIL"]
    return out


def run_controlled_variant(
    root: Path,
    design_row: dict[str, str],
    baseline_daily: pd.Series,
    baseline_weights: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    universe = tuple(symbol for symbol in design_row["universe"].split("|") if symbol)
    prices = cached_prices(str(root), universe).ffill()
    if prices.empty:
        return pd.Series(dtype=float), pd.DataFrame()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    base = baseline_weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    concept = design_row["risk_control_concept"]
    risk_on = spy200d_risk_on(root, prices.index)
    vol = baseline_daily.reindex(prices.index).rolling(60, min_periods=60).std().shift(1) * math.sqrt(252.0)
    equity = 1.0
    peak = 1.0
    guard_active = False
    guard_active_multiplier = 1.0
    output_returns: list[float] = []

    for date in prices.index:
        multipliers = [1.0]
        if concept in {"spy200d_regime_filter", "regime_plus_volatility_guard"} and not bool(risk_on.loc[date]):
            final_multiplier = 0.0
        else:
            if concept in {"realized_volatility_throttle", "regime_plus_volatility_guard"}:
                enough_history = not math.isnan(float(vol.loc[date])) if date in vol.index else False
                multipliers.append(volatility_multiplier(float(vol.loc[date]) if enough_history else float("nan"), enough_history=enough_history))
            if concept == "strategy_drawdown_guard":
                prior_drawdown = equity / peak - 1.0 if peak > 0 else 0.0
                guard_multiplier, guard_active = drawdown_guard_multiplier(
                    prior_drawdown,
                    guard_active=guard_active,
                    active_multiplier=guard_active_multiplier,
                )
                guard_active_multiplier = guard_multiplier
                multipliers.append(guard_multiplier)
            final_multiplier = combined_risky_multiplier(*multipliers)
        weights.loc[date] = apply_multiplier_to_weights(base.loc[date], final_multiplier)
        day_return = float((weights.loc[date] * returns.loc[date]).sum())
        output_returns.append(day_return)
        equity *= 1.0 + day_return
        peak = max(peak, equity)

    daily = pd.Series(output_returns, index=prices.index, name=design_row["variant_id"])
    return daily, weights


def metrics_for_returns(daily: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily.dropna()
    if daily.empty:
        return {}
    eq = equity_curve(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(daily.std() * np.sqrt(252.0))
    mdd = max_drawdown(eq)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    exposure_cols = [col for col in weights.columns if col != "BIL"]
    risky_exposure = weights[exposure_cols].sum(axis=1) if exposure_cols else pd.Series(0.0, index=weights.index)
    bil_share = weights["BIL"] if "BIL" in weights.columns else (1.0 - risky_exposure).clip(lower=0.0)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    rolling = rolling_window_stats(eq)
    return {
        "start_date": daily.index.min().date().isoformat(),
        "end_date": daily.index.max().date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "calmar_or_return_drawdown_proxy": calmar,
        "trade_count": trades,
        "rebalance_count": trades,
        "turnover_proxy": turnover,
        "average_exposure": float(risky_exposure.mean()) if len(risky_exposure) else 0.0,
        "max_daily_exposure": invariant["max_daily_exposure"],
        "average_bil_cash_share": float(bil_share.mean()) if len(bil_share) else 0.0,
        "max_bil_cash_share": float(bil_share.max()) if len(bil_share) else 0.0,
        **invariant,
        "worst_180_day_window": rolling["worst_180d_window"],
        "best_180_day_window": rolling["best_180d_window"],
        "positive_180_day_window_ratio": rolling["positive_180d_window_ratio"],
    }


def baseline_metrics(label_row: dict[str, str]) -> dict[str, float]:
    return {
        "baseline_total_return": parse_float(label_row.get("total_return")),
        "baseline_cagr": parse_float(label_row.get("cagr")),
        "baseline_max_drawdown": parse_float(label_row.get("max_drawdown")),
        "baseline_calmar_or_return_drawdown_proxy": parse_float(label_row.get("calmar_or_return_drawdown_proxy")),
    }


def label_result(row: dict[str, Any], *, one_row_artifact: bool = False) -> str:
    if row.get("data_availability_status") != "cache_ready":
        return "risk_control_signal_data_blocked"
    cagr = parse_float(row.get("cagr"))
    mdd = parse_float(row.get("max_drawdown"))
    drawdown_reduction = parse_float(row.get("drawdown_reduction_vs_baseline"))
    cagr_retention = parse_float(row.get("cagr_retention_vs_baseline"))
    calmar_improvement_value = parse_float(row.get("calmar_improvement_vs_baseline"))
    avg_exposure = parse_float(row.get("average_exposure"))
    max_exposure = parse_float(row.get("max_daily_exposure"))
    avg_bil = parse_float(row.get("average_bil_cash_share"))
    duplicate_corr = parse_float(row.get("duplicate_reference_correlation"))
    if not math.isnan(duplicate_corr) and duplicate_corr >= 0.90:
        return "risk_control_signal_duplicate_existing_active"
    if cagr_retention < 0.40 or cagr < 0.05:
        return "risk_control_signal_return_destroyed"
    if drawdown_reduction < 0.10 or mdd < -0.45:
        return "risk_control_signal_drawdown_not_fixed"
    if (
        drawdown_reduction >= 0.25
        and cagr_retention >= 0.60
        and calmar_improvement_value >= 0.25
        and avg_exposure <= 1.0 + WEIGHT_TOLERANCE
        and max_exposure <= 1.0 + WEIGHT_TOLERANCE
        and avg_bil <= 0.70
        and not one_row_artifact
    ):
        return "risk_control_signal_promising"
    if (drawdown_reduction >= 0.15 and 0.40 <= cagr_retention < 0.60) or (
        cagr_retention >= 0.60 and 0.10 <= drawdown_reduction < 0.25
    ):
        return "risk_control_signal_tradeoff_interesting"
    return "risk_control_signal_weak"


def evaluate_variant(
    root: Path,
    design_row: dict[str, str],
    mapping: dict[str, str],
    label_rows: dict[str, dict[str, str]],
    available: set[str],
    active_returns: pd.Series,
) -> dict[str, Any]:
    universe = [symbol for symbol in design_row["universe"].split("|") if symbol]
    missing = [symbol for symbol in universe if symbol not in available]
    base = {
        "lane_id": LANE_ID,
        "source_family": SOURCE_FAMILY,
        "variant_id": design_row["variant_id"],
        "baseline_variant_id": design_row["baseline_variant_id"],
        "universe_group": design_row["universe_group"],
        "universe": design_row["universe"],
        "lookback": int(design_row["momentum_lookback_days"]),
        "top_n": int(design_row["top_n"]),
        "risk_control_concept": design_row["risk_control_concept"],
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
    }
    baseline_row = label_rows.get(mapping.get("baseline_variant_id", ""))
    if missing or baseline_row is None:
        return {
            **base,
            "data_availability_status": "risk_control_signal_data_blocked",
            "missing_symbols": missing,
            "risk_control_research_label": "risk_control_signal_data_blocked",
            "methodology_notes": "local cache or corrected baseline row missing",
        }
    baseline_daily, baseline_weights = build_baseline_weights(root, design_row)
    daily, weights = run_controlled_variant(root, design_row, baseline_daily, baseline_weights)
    if daily.empty or weights.empty or len(daily.dropna()) < 252:
        return {
            **base,
            "data_availability_status": "risk_control_signal_data_blocked",
            "missing_symbols": [],
            "risk_control_research_label": "risk_control_signal_data_blocked",
            "methodology_notes": "insufficient local history after loading cache",
        }

    run_metrics = metrics_for_returns(daily, weights)
    base_metrics = baseline_metrics(baseline_row)
    baseline_mdd = base_metrics["baseline_max_drawdown"]
    drawdown_reduction = pct_reduction(baseline_mdd, run_metrics["max_drawdown"])
    cagr_retention = safe_ratio(run_metrics["cagr"], base_metrics["baseline_cagr"])
    calmar_delta = calmar_improvement(
        base_metrics["baseline_calmar_or_return_drawdown_proxy"],
        run_metrics["calmar_or_return_drawdown_proxy"],
    )
    spy_delta = benchmark_delta(daily, cached_price_series(str(root), "SPY").pct_change(fill_method=None).dropna().rename("SPY"))
    bil_delta = benchmark_delta(daily, cached_price_series(str(root), "BIL").pct_change(fill_method=None).dropna().rename("BIL"))
    contrib = contribution_metrics(daily, active_returns)
    spy200d_returns = reference_spy200d_returns(root, daily.index)
    aligned_reference = pd.concat([daily.rename("strategy"), spy200d_returns.rename("spy200d")], axis=1).dropna()
    spy200d_corr = float(aligned_reference["strategy"].corr(aligned_reference["spy200d"])) if len(aligned_reference) >= 252 else float("nan")
    aligned_baseline = pd.concat([daily.rename("strategy"), baseline_daily.rename("baseline")], axis=1).dropna()
    baseline_corr = float(aligned_baseline["strategy"].corr(aligned_baseline["baseline"])) if len(aligned_baseline) >= 252 else float("nan")
    duplicate_corr = spy200d_corr

    row = {
        **base,
        **run_metrics,
        **base_metrics,
        "data_availability_status": "cache_ready",
        "missing_symbols": [],
        "drawdown_reduction_vs_baseline": drawdown_reduction,
        "cagr_retention_vs_baseline": cagr_retention,
        "calmar_improvement_vs_baseline": calmar_delta,
        "spy_total_return_delta": spy_delta,
        "bil_cash_total_return_delta": bil_delta,
        "active_vm_dsr_comparison": "active_combo_80_20_blend_proxy_where_available",
        "active_combo_correlation": contrib["active_combo_correlation"],
        "active_combo_blend_total_return_delta": contrib["active_combo_blend_total_return_delta"],
        "active_combo_blend_drawdown_delta": contrib["active_combo_blend_drawdown_delta"],
        "static_all_weather_comparison": "not_available_in_lane_run",
        "duplicate_reference_correlation": duplicate_corr,
        "baseline_correlation": baseline_corr,
        "spy200d_reference_correlation": spy200d_corr,
        "methodology_notes": "fixed patch-v2 risk-control lane; local cache only; non-promotable research evidence",
    }
    row["risk_control_research_label"] = label_result(row)
    return row


def apply_group_artifact_review(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return rows
    for concept, idx in df.groupby("risk_control_concept").groups.items():
        subset = df.loc[idx]
        core = subset[
            (pd.to_numeric(subset["drawdown_reduction_vs_baseline"], errors="coerce") >= 0.25)
            & (pd.to_numeric(subset["cagr_retention_vs_baseline"], errors="coerce") >= 0.60)
            & (pd.to_numeric(subset["calmar_improvement_vs_baseline"], errors="coerce") >= 0.25)
        ]
        one_row_artifact = len(core) < 2
        for row_index in idx:
            row = rows[int(row_index)]
            label = label_result(row, one_row_artifact=one_row_artifact)
            row["risk_control_research_label"] = label
    return rows


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    variants, mappings, methodology_rows, label_rows, audit_manifest = load_design(root)
    mapping_by_variant = {row["variant_id"]: row for row in mappings}
    available = available_symbols(root)
    active_returns = active_combo_returns(root)
    rows = [
        evaluate_variant(root, row, mapping_by_variant.get(row["variant_id"], {}), label_rows, available, active_returns)
        for row in variants
    ]
    rows = apply_group_artifact_review(rows)
    family = summarize_family(rows)
    preflight = {
        "source_design_patch_v2_audit_passed": audit_manifest.get("run_readiness_decision") == "patch_v2_accepted_run_ready",
        "source_next_action_correct": audit_manifest.get("next_action") == "run_high_return_tactical_risk_control_research_lane",
        "variant_count_planned": len(variants),
        "variant_count_exact_24": len(variants) == VARIANT_COUNT_PLANNED,
        "baseline_mapping_rows": len(mappings),
        "methodology_baseline_source_rows": len(methodology_rows),
        "label_baseline_source_rows": len(label_rows),
        "available_symbols_used": sorted({symbol for row in variants for symbol in row["universe"].split("|") if symbol in available}),
    }
    return rows, family, preflight


def median_numeric(rows: list[dict[str, Any]], field: str) -> float:
    values = pd.to_numeric(pd.Series([row.get(field) for row in rows]), errors="coerce").dropna()
    return float(values.median()) if not values.empty else float("nan")


def best_id(rows: list[dict[str, Any]], field: str) -> str:
    if not rows:
        return ""
    df = pd.DataFrame(rows)
    values = pd.to_numeric(df[field], errors="coerce")
    if values.dropna().empty:
        return ""
    return str(df.loc[values.idxmax(), "variant_id"])


def summarize_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    by_family: list[dict[str, Any]] = []
    for concept, subset in pd.DataFrame(rows).groupby("risk_control_concept"):
        part = subset.to_dict("records")
        labels = subset["risk_control_research_label"].value_counts().to_dict()
        by_family.append(
            {
                "lane_id": LANE_ID,
                "source_family": SOURCE_FAMILY,
                "risk_control_concept": concept,
                "variants_evaluated": len(part),
                "data_blocked_variants": labels.get("risk_control_signal_data_blocked", 0),
                "median_cagr": median_numeric(part, "cagr"),
                "median_max_drawdown": median_numeric(part, "max_drawdown"),
                "median_drawdown_reduction_vs_baseline": median_numeric(part, "drawdown_reduction_vs_baseline"),
                "median_cagr_retention_vs_baseline": median_numeric(part, "cagr_retention_vs_baseline"),
                "median_calmar_improvement_vs_baseline": median_numeric(part, "calmar_improvement_vs_baseline"),
                "median_average_bil_cash_share": median_numeric(part, "average_bil_cash_share"),
                "best_variant_by_cagr": best_id(part, "cagr"),
                "best_variant_by_drawdown_reduction": best_id(part, "drawdown_reduction_vs_baseline"),
                "promising_count": labels.get("risk_control_signal_promising", 0),
                "tradeoff_interesting_count": labels.get("risk_control_signal_tradeoff_interesting", 0),
                "return_destroyed_count": labels.get("risk_control_signal_return_destroyed", 0),
                "drawdown_not_fixed_count": labels.get("risk_control_signal_drawdown_not_fixed", 0),
                "duplicate_existing_active_count": labels.get("risk_control_signal_duplicate_existing_active", 0),
                "weak_count": labels.get("risk_control_signal_weak", 0),
                "interpretation": family_interpretation(labels),
            }
        )
    return by_family


def family_interpretation(labels: dict[str, int]) -> str:
    if labels.get("risk_control_signal_promising", 0):
        return "promising_non_promotable_research_signal_requires_audit"
    if labels.get("risk_control_signal_tradeoff_interesting", 0):
        return "tradeoff_interesting_non_promotable_research_signal_requires_audit"
    if labels.get("risk_control_signal_return_destroyed", 0):
        return "risk_control_destroyed_too_much_return_for_many_rows"
    if labels.get("risk_control_signal_drawdown_not_fixed", 0):
        return "drawdown_problem_not_reliably_fixed"
    return "weak_or_inconclusive"


def manifest_payload(created: str, output: Path, rows: list[dict[str, Any]], family: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    label_counts = {label: sum(1 for row in rows if row.get("risk_control_research_label") == label) for label in ALLOWED_LABELS}
    max_exposure = max([parse_float(row.get("max_daily_exposure"), 0.0) for row in rows] or [0.0])
    exposure_passed = all(parse_float(row.get("max_daily_exposure"), 0.0) <= 1.000001 for row in rows)
    cash_passed = all(
        int(parse_float(row.get("weight_sum_violation_count"), 0.0)) == 0
        and int(parse_float(row.get("negative_weight_violation_count"), 0.0)) == 0
        and int(parse_float(row.get("nan_weight_count"), 0.0)) == 0
        and int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) == 0
        for row in rows
    )
    baseline_missing = sum(1 for row in rows if row.get("baseline_variant_id", "") == "" and row.get("risk_control_research_label") != "risk_control_signal_data_blocked")
    hard_invariants_passed = exposure_passed and cash_passed and baseline_missing == 0
    next_action = NEXT_ACTION_AUDIT if hard_invariants_passed and len(rows) == VARIANT_COUNT_PLANNED else NEXT_ACTION_FIX
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "risk_control_lane_run": True,
        "lane_id": LANE_ID,
        "source_design_patch_v2_audit_passed": preflight["source_design_patch_v2_audit_passed"],
        "variant_count_planned": VARIANT_COUNT_PLANNED,
        "new_variants_created": False,
        "new_families_created": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "candidate_exhaustive_run": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "macro_gld_lineage_recovery_run": False,
        "macro_gld_remains_lineage_blocked_visible": True,
        "alpaca_execution_module_delegated": True,
        "variant_count_evaluated": len(rows),
        "data_blocked_variant_count": label_counts["risk_control_signal_data_blocked"],
        "max_daily_exposure": max_exposure,
        "exposure_invariant_passed": exposure_passed,
        "cash_bil_invariant_passed": cash_passed,
        "baseline_comparison_complete_count": len(rows) - baseline_missing - label_counts["risk_control_signal_data_blocked"],
        "baseline_comparison_missing_count": baseline_missing,
        "risk_control_signal_promising_count": label_counts["risk_control_signal_promising"],
        "risk_control_signal_tradeoff_interesting_count": label_counts["risk_control_signal_tradeoff_interesting"],
        "risk_control_signal_return_destroyed_count": label_counts["risk_control_signal_return_destroyed"],
        "risk_control_signal_drawdown_not_fixed_count": label_counts["risk_control_signal_drawdown_not_fixed"],
        "risk_control_signal_duplicate_existing_active_count": label_counts["risk_control_signal_duplicate_existing_active"],
        "risk_control_signal_data_blocked_count": label_counts["risk_control_signal_data_blocked"],
        "risk_control_signal_weak_count": label_counts["risk_control_signal_weak"],
        "family_summary_count": len(family),
        "next_action": next_action,
    }


def rows_md(title: str, rows: list[dict[str, Any]], label: str | None = None) -> str:
    filtered = [row for row in rows if label is None or row.get("risk_control_research_label") == label]
    lines = [f"# {title}", "", f"Rows: `{len(filtered)}`", ""]
    if not filtered:
        lines.append("- None")
    for row in filtered:
        lines.append(
            f"- `{row['variant_id']}`: label `{row['risk_control_research_label']}`, "
            f"CAGR `{parse_float(row.get('cagr')):.4f}`, max DD `{parse_float(row.get('max_drawdown')):.4f}`, "
            f"DD reduction `{parse_float(row.get('drawdown_reduction_vs_baseline')):.4f}`, "
            f"CAGR retention `{parse_float(row.get('cagr_retention_vs_baseline')):.4f}`"
        )
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any], family: list[dict[str, Any]]) -> str:
    label_lines = [
        f"- Promising: `{manifest['risk_control_signal_promising_count']}`",
        f"- Tradeoff interesting: `{manifest['risk_control_signal_tradeoff_interesting_count']}`",
        f"- Return destroyed: `{manifest['risk_control_signal_return_destroyed_count']}`",
        f"- Drawdown not fixed: `{manifest['risk_control_signal_drawdown_not_fixed_count']}`",
        f"- Duplicate existing active/reference: `{manifest['risk_control_signal_duplicate_existing_active_count']}`",
        f"- Data blocked: `{manifest['risk_control_signal_data_blocked_count']}`",
    ]
    family_lines = [
        f"- `{row['risk_control_concept']}`: {row['interpretation']} "
        f"(promising `{row['promising_count']}`, tradeoff `{row['tradeoff_interesting_count']}`)"
        for row in family
    ]
    return f"""# High-Return Tactical Risk-Control Lane Run

Lane ID: `{manifest['lane_id']}`

Variant count planned: `{manifest['variant_count_planned']}`

Variant count evaluated: `{manifest['variant_count_evaluated']}`

Data-blocked variants: `{manifest['data_blocked_variant_count']}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Cash/BIL invariant passed: `{manifest['cash_bil_invariant_passed']}`

Baseline comparison complete count: `{manifest['baseline_comparison_complete_count']}`

Baseline comparison missing count: `{manifest['baseline_comparison_missing_count']}`

Research label counts:

{chr(10).join(label_lines)}

Family/concept interpretation:

{chr(10).join(family_lines)}

No output is promotable or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def preflight_md(preflight: dict[str, Any]) -> str:
    return f"""# Local Cache Run Preflight

- Source patch v2 audit passed: `{preflight['source_design_patch_v2_audit_passed']}`
- Source next action correct: `{preflight['source_next_action_correct']}`
- Variant count planned from design table: `{preflight['variant_count_planned']}`
- Variant count exactly 24: `{preflight['variant_count_exact_24']}`
- Baseline mapping rows: `{preflight['baseline_mapping_rows']}`
- Corrected methodology source rows: `{preflight['methodology_baseline_source_rows']}`
- Corrected label source rows: `{preflight['label_baseline_source_rows']}`
- Available local-cache symbols used: `{', '.join(preflight['available_symbols_used'])}`

No provider download, broker API, intraday data, or live path was used.
"""


def family_md(family: list[dict[str, Any]]) -> str:
    lines = ["# Family Run Summary", ""]
    for row in family:
        lines.append(f"## {row['risk_control_concept']}")
        lines.append("")
        lines.append(f"- Variants evaluated: `{row['variants_evaluated']}`")
        lines.append(f"- Median CAGR: `{row['median_cagr']}`")
        lines.append(f"- Median max drawdown: `{row['median_max_drawdown']}`")
        lines.append(f"- Median drawdown reduction vs baseline: `{row['median_drawdown_reduction_vs_baseline']}`")
        lines.append(f"- Median CAGR retention vs baseline: `{row['median_cagr_retention_vs_baseline']}`")
        lines.append(f"- Interpretation: `{row['interpretation']}`")
        lines.append("")
    return "\n".join(lines)


def baseline_review_md(manifest: dict[str, Any]) -> str:
    return f"""# Baseline Comparison Review

- Complete baseline comparisons: `{manifest['baseline_comparison_complete_count']}`
- Missing baseline comparisons: `{manifest['baseline_comparison_missing_count']}`
- Corrected baseline sources used: methodology-fix CSV and labeling-fix CSV.
- Contaminated original batch v1 outputs were not used.

Same-window baseline comparison is required for each non-data-blocked variant.
"""


def invariant_md(title: str, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    max_weight = max([parse_float(row.get("max_daily_weight_sum"), 0.0) for row in rows] or [0.0])
    impossible_days = sum(int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) for row in rows)
    negative = sum(int(parse_float(row.get("negative_weight_violation_count"), 0.0)) for row in rows)
    nan_count = sum(int(parse_float(row.get("nan_weight_count"), 0.0)) for row in rows)
    return f"""# {title}

- Max daily exposure: `{manifest['max_daily_exposure']}`
- Max daily total weight: `{max_weight}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Cash/BIL invariant passed: `{manifest['cash_bil_invariant_passed']}`
- Impossible BIL plus risky exposure days: `{impossible_days}`
- Negative weight violations: `{negative}`
- NaN weight count: `{nan_count}`
"""


def label_summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Risk-Control Label Summary

- `risk_control_signal_promising`: `{manifest['risk_control_signal_promising_count']}`
- `risk_control_signal_tradeoff_interesting`: `{manifest['risk_control_signal_tradeoff_interesting_count']}`
- `risk_control_signal_return_destroyed`: `{manifest['risk_control_signal_return_destroyed_count']}`
- `risk_control_signal_drawdown_not_fixed`: `{manifest['risk_control_signal_drawdown_not_fixed_count']}`
- `risk_control_signal_duplicate_existing_active`: `{manifest['risk_control_signal_duplicate_existing_active_count']}`
- `risk_control_signal_data_blocked`: `{manifest['risk_control_signal_data_blocked_count']}`
- `risk_control_signal_weak`: `{manifest['risk_control_signal_weak_count']}`

Labels are research-only and cannot create promotion or paper-forward eligibility.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Risk-Control Lane Run

This run is historical research evidence only.

Forbidden direct outcomes:

- promotion-review candidate
- candidate_exhaustive candidate
- paper-forward candidate
- paper-forward activation
- demo/live activation
- real-money recommendation

Any follow-up must pass the explicit next governance step.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Risk-Control Lane Run Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def update_research_metadata(root: Path, created: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    section = f"""## Latest High-Return Tactical Risk-Control Lane Run

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{LANE_ID}`
- Variants evaluated: `{manifest['variant_count_evaluated']}`
- Data-blocked variants: `{manifest['data_blocked_variant_count']}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Cash/BIL invariant passed: `{manifest['cash_bil_invariant_passed']}`
- Promotion candidates created: `{manifest['promotion_candidates_created']}`
- Paper-forward activation: `{manifest['paper_forward_activation']}`
- Provider download: `{manifest['provider_download']}`
- Next action: `{manifest['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Latest High-Return Tactical Risk-Control Lane Run", section))


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["risk_control_lane_run_consistency_check.json"] = True
    labels = {row.get("risk_control_research_label", "") for row in rows}
    check = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "source_design_patch_v2_audit_passed": manifest["source_design_patch_v2_audit_passed"] is True,
        "variant_count_planned_24": manifest["variant_count_planned"] == VARIANT_COUNT_PLANNED,
        "no_new_variants": manifest["new_variants_created"] is False,
        "no_new_families": manifest["new_families_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": (
            manifest["broker_orders_submitted"] is False
            and manifest["broker_orders_cancelled"] is False
            and manifest["broker_orders_reconciled"] is False
        ),
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_promotion": manifest["promotion_candidates_created"] is False and manifest["best_single_variant_promoted"] is False,
        "no_paper_forward": manifest["paper_forward_activation"] is False and manifest["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_lineage_recovery_not_run": manifest["macro_gld_lineage_recovery_run"] is False,
        "alpaca_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "variant_results_exist": (output / "variant_run_results.csv").exists() and bool(rows),
        "family_summary_exists": (output / "family_run_summary.csv").exists(),
        "baseline_comparison_results_exist": (output / "baseline_comparison_results.csv").exists(),
        "exposure_invariant_report_exists": (output / "exposure_invariant_report.md").exists(),
        "cash_bil_invariant_report_exists": (output / "cash_bil_invariant_report.md").exists(),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "cash_bil_invariant_passed": manifest["cash_bil_invariant_passed"] is True,
        "baseline_missing_ok": manifest["baseline_comparison_missing_count"] == 0 or manifest["data_blocked_variant_count"] > 0,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "promotion_eligibility_false": all(row.get("promotion_eligibility") is False for row in rows),
        "paper_forward_eligibility_false": all(row.get("paper_forward_eligibility") is False for row in rows),
        "do_not_promote_exists": (output / "do_not_promote_from_risk_control_lane_run.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def write_outputs(root: Path, created: str, rows: list[dict[str, Any]], family: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, rows, family, preflight)
    baseline_rows = [
        {
            "variant_id": row["variant_id"],
            "baseline_variant_id": row["baseline_variant_id"],
            "baseline_total_return": row.get("baseline_total_return"),
            "baseline_cagr": row.get("baseline_cagr"),
            "baseline_max_drawdown": row.get("baseline_max_drawdown"),
            "drawdown_reduction_vs_baseline": row.get("drawdown_reduction_vs_baseline"),
            "cagr_retention_vs_baseline": row.get("cagr_retention_vs_baseline"),
            "calmar_improvement_vs_baseline": row.get("calmar_improvement_vs_baseline"),
            "risk_control_research_label": row.get("risk_control_research_label"),
        }
        for row in rows
    ]
    write_json(output / "risk_control_lane_run_manifest.json", manifest)
    write_text(output / "risk_control_lane_run_summary.md", summary_md(manifest, family))
    write_text(output / "local_cache_run_preflight.md", preflight_md(preflight))
    write_csv(output / "variant_run_results.csv", rows, list(VARIANT_RESULT_FIELDS))
    write_text(output / "variant_run_results.md", rows_md("Variant Run Results", rows))
    write_csv(output / "family_run_summary.csv", family, list(family[0].keys()) if family else [])
    write_text(output / "family_run_summary.md", family_md(family))
    write_csv(output / "baseline_comparison_results.csv", baseline_rows, list(baseline_rows[0].keys()) if baseline_rows else [])
    write_text(output / "baseline_comparison_review.md", baseline_review_md(manifest))
    write_text(output / "exposure_invariant_report.md", invariant_md("Exposure Invariant Report", manifest, rows))
    write_text(output / "cash_bil_invariant_report.md", invariant_md("Cash/BIL Invariant Report", manifest, rows))
    write_text(output / "risk_control_label_summary.md", label_summary_md(manifest))
    write_text(output / "promising_risk_control_signals.md", rows_md("Promising Risk-Control Signals", rows, "risk_control_signal_promising"))
    write_text(
        output / "tradeoff_interesting_signals.md",
        rows_md("Tradeoff-Interesting Signals", rows, "risk_control_signal_tradeoff_interesting"),
    )
    write_text(output / "return_destroyed_signals.md", rows_md("Return-Destroyed Signals", rows, "risk_control_signal_return_destroyed"))
    write_text(
        output / "drawdown_not_fixed_signals.md",
        rows_md("Drawdown-Not-Fixed Signals", rows, "risk_control_signal_drawdown_not_fixed"),
    )
    write_text(
        output / "duplicate_existing_active_signals.md",
        rows_md("Duplicate Existing Active Signals", rows, "risk_control_signal_duplicate_existing_active"),
    )
    write_text(output / "do_not_promote_from_risk_control_lane_run.md", do_not_promote_md())
    write_text(output / "risk_control_lane_run_next_action.md", next_action_md(manifest["next_action"]))
    consistency = consistency_check(manifest, output, rows)
    write_json(output / "risk_control_lane_run_consistency_check.json", consistency)
    update_research_metadata(root, created, output, manifest)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, family, preflight = evaluate_lane(root)
    return write_outputs(root, created, rows, family, preflight)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "data_blocked_variant_count": result["data_blocked_variant_count"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "cash_bil_invariant_passed": result["cash_bil_invariant_passed"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
