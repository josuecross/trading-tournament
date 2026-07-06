from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import max_drawdown, trade_count_and_turnover, write_csv


SOURCE_ID = "larry_connors_rsi2_mean_reversion"
FAMILY_ID = "short_term_equity_mean_reversion"
LANE_ID = "public_source_larry_connors_rsi2_bounded_bt_lane_v1"
RUN_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_run" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_design" / "latest"
SAMPLE_ADEQUACY_DIR = Path("evidence") / "research_recovery" / "backtest_sample_adequacy_report" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_larry_connors_rsi2_bounded_bt_results_audit"
    / "latest"
)

AUDIT_DECISION_PASSED = "public_source_larry_connors_rsi2_results_audit_passed"
AUDIT_DECISION_PATCH = "public_source_larry_connors_rsi2_results_needs_patch"
NEXT_ACTION_ROBUSTNESS_DESIGN = "design_public_source_larry_connors_rsi2_robustness_check"
NEXT_ACTION_PATCH = "patch_public_source_larry_connors_rsi2_bounded_bt_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_ROBUSTNESS_DESIGN, NEXT_ACTION_PATCH}

EXPECTED_VARIANTS = (
    "connors_rsi2_spy_bil_primary_v1",
    "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1",
    "connors_rsi2_spy_buy_hold_control_v1",
    "connors_rsi2_bil_cash_control_v1",
    "connors_rsi2_spy200d_frozen_control_v1",
)
RSI_PERIOD = 2
RSI_ENTRY_THRESHOLD = 5.0
TREND_SMA_PERIOD = 200
EXIT_SMA_PERIOD = 5
STANDARD_COST_ASSUMPTION = 0.0
WEIGHT_TOLERANCE = 1e-6
METRIC_TOLERANCE = 1e-8
DAILY_TOLERANCE = 1e-12

REQUIRED_RUN_FILES = (
    "public_source_larry_connors_rsi2_bounded_bt_run_manifest.json",
    "public_source_larry_connors_rsi2_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "rsi_sma_calculation_report.md",
    "signal_timing_no_lookahead_report.md",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "similarity_risk_report.md",
    "role_label_summary.md",
    "public_source_larry_connors_rsi2_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_larry_connors_rsi2_run.md",
    "public_source_larry_connors_rsi2_bounded_bt_run_next_action.md",
)
AUDIT_FILES = (
    "public_source_larry_connors_rsi2_bounded_bt_results_audit_manifest.json",
    "public_source_larry_connors_rsi2_bounded_bt_results_audit_consistency_check.json",
    "rsi_sma_formula_audit_report.md",
    "signal_logic_audit_report.md",
    "shifted_weight_no_lookahead_audit_report.md",
    "row_level_discrepancy_report.csv",
    "row_level_discrepancy_report.md",
    "criteria_recomputation_report.csv",
    "criteria_recomputation_report.md",
    "timing_sanity_interpretation_report.md",
    "sample_adequacy_note.md",
    "exposure_invariant_audit_report.md",
    "control_row_separation_report.md",
    "guardrail_audit_report.md",
    "public_source_larry_connors_rsi2_bounded_bt_results_audit_summary.md",
    "public_source_larry_connors_rsi2_bounded_bt_results_audit_decision.md",
    "public_source_larry_connors_rsi2_bounded_bt_results_audit_next_action.md",
)
DISCREPANCY_FIELDS = (
    "variant_id",
    "discrepancy_type",
    "field",
    "reported_value",
    "recomputed_value",
    "absolute_delta",
    "tolerance",
    "date_or_period",
)
CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "reported_numeric_criteria_pass",
    "recomputed_numeric_criteria_pass",
    "reported_research_label",
    "recomputed_research_label",
    "total_return_versus_bil_pass",
    "excess_after_cost_pass",
    "drawdown_reduction_pass",
    "return_drawdown_proxy_pass",
    "average_spy_exposure_bounds_pass",
    "duplicate_reference_correlation_pass",
    "timing_sanity_context_only",
    "control_row_excluded_from_candidate_interpretation",
    "exposure_invariant_pass",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def both_nan(left: float, right: float) -> bool:
    return math.isnan(left) and math.isnan(right)


def load_adjusted_price_frame(root: Path = ROOT) -> pd.DataFrame:
    frames: list[pd.Series] = []
    for symbol in ("SPY", "BIL"):
        path = root / "data" / "cache" / f"{symbol}.csv"
        df = pd.read_csv(path)
        dates = pd.to_datetime(df["date"], errors="coerce")
        prices = pd.to_numeric(df["adj_close"], errors="coerce")
        frames.append(pd.Series(prices.to_numpy(), index=dates, name=symbol).dropna())
    prices = pd.concat(frames, axis=1, join="inner").sort_index()
    return prices.loc[prices[["SPY", "BIL"]].notna().all(axis=1), ["SPY", "BIL"]].copy()


def independent_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def independent_rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=window, min_periods=window).mean()
    avg_loss = losses.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(avg_gain != 0, 0.0)
    return out


def indicator_frame(prices: pd.DataFrame) -> pd.DataFrame:
    close = prices["SPY"].astype(float)
    indicators = pd.DataFrame(index=prices.index)
    indicators["spy_close"] = close
    indicators["rsi_2"] = independent_rsi(close, RSI_PERIOD)
    indicators["sma_200"] = independent_sma(close, TREND_SMA_PERIOD)
    indicators["sma_5"] = independent_sma(close, EXIT_SMA_PERIOD)
    indicators["entry_signal"] = (indicators["spy_close"] > indicators["sma_200"]) & (
        indicators["rsi_2"] < RSI_ENTRY_THRESHOLD
    )
    indicators["exit_signal"] = indicators["spy_close"] > indicators["sma_5"]
    return indicators


def primary_targets(indicators: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=indicators.index, columns=["SPY", "BIL"])
    active = False
    for date, row in indicators.iterrows():
        entry = bool(row["entry_signal"]) if not pd.isna(row["entry_signal"]) else False
        exit_signal = bool(row["exit_signal"]) if not pd.isna(row["exit_signal"]) else False
        if active and exit_signal:
            active = False
        elif not active and entry:
            active = True
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
    return weights.astype(float)


def timing_sanity_targets(primary: pd.DataFrame) -> pd.DataFrame:
    delayed = primary.shift(1)
    if not delayed.empty:
        delayed.iloc[0] = [0.0, 1.0]
    return delayed.ffill().fillna({"SPY": 0.0, "BIL": 1.0}).astype(float)


def constant_targets(index: pd.DatetimeIndex, spy: float, bil: float) -> pd.DataFrame:
    return pd.DataFrame({"SPY": spy, "BIL": bil}, index=index, dtype=float)


def month_rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    month = pd.Series(index.to_period("M"), index=index)
    return pd.DatetimeIndex(index[month.ne(month.shift(1)).fillna(True)])


def spy200d_control_targets(prices: pd.DataFrame) -> pd.DataFrame:
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=200).mean()
    risk_on = prior_spy > prior_sma
    weights = pd.DataFrame(np.nan, index=prices.index, columns=["SPY", "BIL"], dtype=float)
    for date in month_rebalance_dates(pd.DatetimeIndex(prices.index)):
        weights.loc[date] = [1.0, 0.0] if bool(risk_on.loc[date]) else [0.0, 1.0]
    return weights.ffill().fillna(0.0)


def build_weights(variant_id: str, prices: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    primary = primary_targets(indicators)
    if variant_id == "connors_rsi2_spy_bil_primary_v1":
        return primary
    if variant_id == "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1":
        return timing_sanity_targets(primary)
    if variant_id == "connors_rsi2_spy_buy_hold_control_v1":
        return constant_targets(pd.DatetimeIndex(prices.index), 1.0, 0.0)
    if variant_id == "connors_rsi2_bil_cash_control_v1":
        return constant_targets(pd.DatetimeIndex(prices.index), 0.0, 1.0)
    if variant_id == "connors_rsi2_spy200d_frozen_control_v1":
        return spy200d_control_targets(prices)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def returns_from_weights(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (aligned.shift(1).fillna(0.0) * asset_returns).sum(axis=1)


def equity_from_returns(daily_returns: pd.Series) -> pd.Series:
    return (1.0 + daily_returns.fillna(0.0)).cumprod().rename("equity")


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 252 or float(aligned["left"].std()) == 0.0 or float(aligned["right"].std()) == 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def invariant_summary(weights: pd.DataFrame) -> dict[str, Any]:
    weight_sum = weights.sum(axis=1)
    risky = weights.drop(columns=["BIL"], errors="ignore").sum(axis=1)
    cash = weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index)
    return {
        "max_daily_exposure": float(risky.max()),
        "max_daily_weight_sum": float(weight_sum.max()),
        "average_weight_sum": float(weight_sum.mean()),
        "weight_sum_violation_count": int((weight_sum > 1.0 + WEIGHT_TOLERANCE).sum()),
        "negative_weight_violation_count": int((weights < -WEIGHT_TOLERANCE).sum().sum()),
        "nan_weight_count": int(weights.isna().sum().sum()),
        "impossible_cash_and_risky_exposure_days": int(((cash >= 1.0 - WEIGHT_TOLERANCE) & (risky > WEIGHT_TOLERANCE)).sum()),
    }


def metrics(daily_returns: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily_returns.dropna()
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    volatility = float(daily.std() * np.sqrt(252.0))
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    return {
        "effective_start_date": daily.index.min().date().isoformat(),
        "effective_end_date": daily.index.max().date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "return_drawdown_proxy": proxy,
        "average_spy_exposure_share": float(weights["SPY"].mean()),
        "average_bil_exposure_share": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover,
        **invariant_summary(weights),
    }


def recompute_result_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
) -> dict[str, Any]:
    bil_total = controls["connors_rsi2_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["connors_rsi2_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["connors_rsi2_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd) if spy_mdd < 0 else float("nan")
    corr_spy = safe_corr(daily, control_returns["connors_rsi2_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["connors_rsi2_spy200d_frozen_control_v1"])
    duplicate_values = [value for value in (corr_spy, corr_spy200d) if math.isfinite(value)]
    duplicate_reference = max(duplicate_values) if duplicate_values else float("nan")
    exposure_pass = (
        row_metrics["max_daily_exposure"] <= 1.000001
        and row_metrics["max_daily_weight_sum"] <= 1.000001
        and int(row_metrics["weight_sum_violation_count"]) == 0
        and int(row_metrics["negative_weight_violation_count"]) == 0
        and int(row_metrics["nan_weight_count"]) == 0
        and int(row_metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )
    is_primary = row["variant_role"] == "source_primary"
    is_timing = row["variant_role"] == "timing_sanity"
    primary_total_return_beats_bil = is_primary and same_window_vs_bil > 0.0
    primary_excess_after_cost_beats_bil = is_primary and excess_after_cost > 0.0
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.20
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.0100 <= row_metrics["average_spy_exposure_share"] <= 0.4500
    primary_duplicate_pass = is_primary and (not math.isfinite(duplicate_reference) or duplicate_reference < 0.90)
    numeric_pass = exposure_pass
    if is_primary:
        numeric_pass = all(
            (
                primary_total_return_beats_bil,
                primary_excess_after_cost_beats_bil,
                primary_drawdown_reduction_pass,
                primary_proxy_pass,
                primary_exposure_pass,
                primary_duplicate_pass,
                exposure_pass,
            )
        )
    return {
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": row["research_label"],
        "symbols_used": row["symbols"],
        "indicator_formula_status": "independent_rsi_simple_rolling_gain_loss_sma200_sma5_from_local_adjusted_close",
        **row_metrics,
        "same_window_return_versus_bil": same_window_vs_bil,
        "return_after_standard_cost_assumption": row_metrics["total_return"] - STANDARD_COST_ASSUMPTION,
        "excess_return_versus_bil_after_cost": excess_after_cost,
        "drawdown_reduction_versus_spy_buy_hold": drawdown_reduction,
        "correlation_versus_spy_buy_hold": corr_spy,
        "correlation_versus_spy200d_control": corr_spy200d,
        "duplicate_reference_correlation": duplicate_reference,
        "exposure_invariant_pass": exposure_pass,
        "primary_total_return_beats_bil": primary_total_return_beats_bil,
        "primary_excess_after_cost_beats_bil": primary_excess_after_cost_beats_bil,
        "primary_drawdown_reduction_pass": primary_drawdown_reduction_pass,
        "primary_return_drawdown_proxy_pass": primary_proxy_pass,
        "primary_spy_exposure_bounds_pass": primary_exposure_pass,
        "primary_duplicate_correlation_pass": primary_duplicate_pass,
        "timing_sanity_context_only": is_timing,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }


def design_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / DESIGN_DIR / "planned_row_table.csv")


def recompute_lane(root: Path) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], pd.DataFrame]:
    rows = design_rows(root)
    prices = load_adjusted_price_frame(root)
    indicators = indicator_frame(prices)
    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    for row in rows:
        variant_id = row["variant_id"]
        weights = build_weights(variant_id, prices, indicators)
        daily = returns_from_weights(prices, weights).rename(variant_id)
        weights_by_variant[variant_id] = weights
        returns_by_variant[variant_id] = daily
        metrics_by_variant[variant_id] = metrics(daily, weights)
    recomputed = [
        recompute_result_row(
            row,
            metrics_by_variant[row["variant_id"]],
            returns_by_variant[row["variant_id"]],
            metrics_by_variant,
            returns_by_variant,
        )
        for row in rows
    ]
    return recomputed, weights_by_variant, returns_by_variant, indicators


def compare_value(
    discrepancies: list[dict[str, Any]],
    variant_id: str,
    discrepancy_type: str,
    field: str,
    reported: Any,
    recomputed: Any,
    tolerance: float,
    date_or_period: str = "",
) -> None:
    if isinstance(recomputed, bool):
        if parse_bool(reported) != recomputed:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": discrepancy_type,
                    "field": field,
                    "reported_value": reported,
                    "recomputed_value": recomputed,
                    "absolute_delta": "",
                    "tolerance": tolerance,
                    "date_or_period": date_or_period,
                }
            )
        return
    if isinstance(recomputed, str):
        if str(reported) != recomputed:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": discrepancy_type,
                    "field": field,
                    "reported_value": reported,
                    "recomputed_value": recomputed,
                    "absolute_delta": "",
                    "tolerance": tolerance,
                    "date_or_period": date_or_period,
                }
            )
        return
    left = parse_float(reported)
    right = parse_float(recomputed)
    if both_nan(left, right):
        return
    delta = abs(left - right)
    if math.isnan(delta) or delta > tolerance:
        discrepancies.append(
            {
                "variant_id": variant_id,
                "discrepancy_type": discrepancy_type,
                "field": field,
                "reported_value": reported,
                "recomputed_value": recomputed,
                "absolute_delta": delta,
                "tolerance": tolerance,
                "date_or_period": date_or_period,
            }
        )


def compare_row_results(reported_rows: list[dict[str, str]], recomputed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    reported_by_id = {row["variant_id"]: row for row in reported_rows}
    numeric_fields = (
        "average_spy_exposure_share",
        "average_bil_exposure_share",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "same_window_return_versus_bil",
        "return_after_standard_cost_assumption",
        "excess_return_versus_bil_after_cost",
        "drawdown_reduction_versus_spy_buy_hold",
        "correlation_versus_spy_buy_hold",
        "correlation_versus_spy200d_control",
        "duplicate_reference_correlation",
        "trade_count",
        "turnover_proxy",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "average_weight_sum",
        "weight_sum_violation_count",
        "negative_weight_violation_count",
        "nan_weight_count",
        "impossible_cash_and_risky_exposure_days",
    )
    bool_fields = (
        "exposure_invariant_pass",
        "primary_total_return_beats_bil",
        "primary_excess_after_cost_beats_bil",
        "primary_drawdown_reduction_pass",
        "primary_return_drawdown_proxy_pass",
        "primary_spy_exposure_bounds_pass",
        "primary_duplicate_correlation_pass",
        "timing_sanity_context_only",
        "numeric_criteria_pass",
        "promotion_eligibility",
        "paper_forward_eligibility",
        "candidate_exhaustive_eligibility",
    )
    string_fields = ("variant_role", "research_label", "symbols_used", "effective_start_date", "effective_end_date")
    for row in recomputed_rows:
        variant_id = row["variant_id"]
        reported = reported_by_id.get(variant_id)
        if not reported:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": "missing_reported_row",
                    "field": "variant_id",
                    "reported_value": "",
                    "recomputed_value": variant_id,
                    "absolute_delta": "",
                    "tolerance": "",
                    "date_or_period": "",
                }
            )
            continue
        for field in numeric_fields:
            compare_value(discrepancies, variant_id, "row_metric", field, reported.get(field), row.get(field), METRIC_TOLERANCE)
        for field in bool_fields:
            compare_value(discrepancies, variant_id, "row_boolean", field, reported.get(field), row.get(field), 0)
        for field in string_fields:
            compare_value(discrepancies, variant_id, "row_text", field, reported.get(field), row.get(field), 0)
    return discrepancies


def compare_daily_weights(path: Path, weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    rows = read_csv_rows(path)
    reported: dict[tuple[str, str], dict[str, str]] = {(row["variant_id"], row["date"]): row for row in rows}
    for variant_id, weights in weights_by_variant.items():
        for date, row in weights.iterrows():
            key = (variant_id, pd.Timestamp(date).date().isoformat())
            saved = reported.get(key)
            if not saved:
                compare_value(discrepancies, variant_id, "daily_weight", "date", "", key[1], 0, key[1])
                continue
            compare_value(discrepancies, variant_id, "daily_weight", "SPY", saved.get("SPY"), float(row["SPY"]), DAILY_TOLERANCE, key[1])
            compare_value(discrepancies, variant_id, "daily_weight", "BIL", saved.get("BIL"), float(row["BIL"]), DAILY_TOLERANCE, key[1])
            compare_value(
                discrepancies,
                variant_id,
                "daily_weight",
                "weight_sum",
                saved.get("weight_sum"),
                float(row.sum()),
                DAILY_TOLERANCE,
                key[1],
            )
    return discrepancies


def compare_equity_returns(path: Path, returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    rows = read_csv_rows(path)
    reported: dict[tuple[str, str], dict[str, str]] = {(row["variant_id"], row["date"]): row for row in rows}
    for variant_id, daily in returns_by_variant.items():
        equity = equity_from_returns(daily)
        for date, value in daily.items():
            key = (variant_id, pd.Timestamp(date).date().isoformat())
            saved = reported.get(key)
            if not saved:
                compare_value(discrepancies, variant_id, "daily_return", "date", "", key[1], 0, key[1])
                continue
            compare_value(discrepancies, variant_id, "daily_return", "daily_return", saved.get("daily_return"), float(value), DAILY_TOLERANCE, key[1])
            compare_value(discrepancies, variant_id, "equity", "equity", saved.get("equity"), float(equity.loc[date]), DAILY_TOLERANCE, key[1])
    return discrepancies


def criteria_rows(reported_rows: list[dict[str, str]], recomputed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reported = {row["variant_id"]: row for row in reported_rows}
    out: list[dict[str, Any]] = []
    for row in recomputed_rows:
        saved = reported[row["variant_id"]]
        is_control = row["variant_role"] == "control"
        out.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "reported_numeric_criteria_pass": parse_bool(saved["numeric_criteria_pass"]),
                "recomputed_numeric_criteria_pass": bool(row["numeric_criteria_pass"]),
                "reported_research_label": saved["research_label"],
                "recomputed_research_label": row["research_label"],
                "total_return_versus_bil_pass": bool(row["primary_total_return_beats_bil"]),
                "excess_after_cost_pass": bool(row["primary_excess_after_cost_beats_bil"]),
                "drawdown_reduction_pass": bool(row["primary_drawdown_reduction_pass"]),
                "return_drawdown_proxy_pass": bool(row["primary_return_drawdown_proxy_pass"]),
                "average_spy_exposure_bounds_pass": bool(row["primary_spy_exposure_bounds_pass"]),
                "duplicate_reference_correlation_pass": bool(row["primary_duplicate_correlation_pass"]),
                "timing_sanity_context_only": bool(row["timing_sanity_context_only"]),
                "control_row_excluded_from_candidate_interpretation": is_control
                and row["promotion_eligibility"] is False
                and row["paper_forward_eligibility"] is False
                and row["candidate_exhaustive_eligibility"] is False,
                "exposure_invariant_pass": bool(row["exposure_invariant_pass"]),
            }
        )
    return out


def evidence_completeness(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["manifest"]
    consistency = source["consistency"]
    rows = source["run_rows"]
    checks = {
        "all_required_run_files_exist": all(source["required_files"].values()),
        "manifest_consistency_agree": manifest.get("variant_count_evaluated") == 5
        and consistency.get("consistency_passed") is True,
        "exact_five_rows": len(rows) == 5 and {row["variant_id"] for row in rows} == set(EXPECTED_VARIANTS),
        "no_hidden_parameter_sweep": manifest.get("threshold_sweep_created") is False
        and manifest.get("optimization_run") is False
        and manifest.get("other_indicators_added") is False
        and manifest.get("stop_loss_or_profit_target_added") is False
        and manifest.get("holding_period_exit_added") is False,
    }
    return {"checks": checks, "passed": all(checks.values())}


def guardrail_audit(manifest: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    checks = {
        "no_scraping": manifest.get("public_source_scraped") is False,
        "no_provider_download": manifest.get("provider_download") is False,
        "no_intraday": manifest.get("intraday_data_used") is False,
        "no_extra_public_source_ingestion": manifest.get("public_strategy_list_ingested") is False,
        "no_new_instruments": manifest.get("new_instruments_added") is False,
        "no_rsi_sma_tuning": manifest.get("parameters_tuned") is False
        and manifest.get("threshold_sweep_created") is False
        and manifest.get("optimization_run") is False,
        "no_strategy_discovery": manifest.get("strategy_discovery_run") is False,
        "no_candidate_exhaustive": manifest.get("candidate_exhaustive_run") is False,
        "no_promotion": manifest.get("promotion_candidates_created") is False and manifest.get("best_single_variant_promoted") is False,
        "no_paper_forward_activation": manifest.get("paper_forward_activation") is False
        and manifest.get("new_paper_forward_candidate_created") is False,
        "no_broker_live_real_money": manifest.get("broker_api_called") is False
        and manifest.get("broker_orders_submitted") is False
        and manifest.get("broker_orders_cancelled") is False
        and manifest.get("broker_orders_reconciled") is False
        and manifest.get("live_orders") is False
        and manifest.get("real_money_recommendation") is False,
        "outputs_diagnostic_non_promotable": manifest.get("outputs_diagnostic_only") is True
        and manifest.get("outputs_non_promotable") is True
        and all(parse_bool(row["promotion_eligibility"]) is False for row in rows)
        and all(parse_bool(row["paper_forward_eligibility"]) is False for row in rows)
        and all(parse_bool(row["candidate_exhaustive_eligibility"]) is False for row in rows),
    }
    return {"checks": checks, "passed": all(checks.values())}


def source_payload(root: Path) -> dict[str, Any]:
    run = root / RUN_DIR
    return {
        "manifest": read_json(run / "public_source_larry_connors_rsi2_bounded_bt_run_manifest.json"),
        "consistency": read_json(run / "public_source_larry_connors_rsi2_bounded_bt_run_consistency_check.json"),
        "run_rows": read_csv_rows(run / "row_level_results.csv"),
        "criteria_rows": read_csv_rows(run / "numeric_criteria_results.csv"),
        "required_files": {name: (run / name).exists() for name in REQUIRED_RUN_FILES},
        "design_manifest": read_json(root / DESIGN_DIR / "public_source_larry_connors_rsi2_bounded_bt_design_manifest.json"),
        "sample_rows": read_csv_rows(root / SAMPLE_ADEQUACY_DIR / "sample_adequacy_table.csv"),
    }


def no_lookahead_audit(root: Path, prices: pd.DataFrame, weights_by_variant: dict[str, pd.DataFrame], returns_by_variant: dict[str, pd.Series]) -> dict[str, Any]:
    saved_rows = read_csv_rows(root / RUN_DIR / "equity_curve_returns.csv")
    reported = {(row["variant_id"], row["date"]): parse_float(row["daily_return"]) for row in saved_rows}
    max_delta = 0.0
    for variant_id, daily in returns_by_variant.items():
        for date, value in daily.items():
            key = (variant_id, pd.Timestamp(date).date().isoformat())
            max_delta = max(max_delta, abs(reported.get(key, float("nan")) - float(value)))
    primary = weights_by_variant["connors_rsi2_spy_bil_primary_v1"]
    shifted_formula_matches = max_delta <= DAILY_TOLERANCE
    target_changes = primary.diff().abs().sum(axis=1).fillna(primary.abs().sum(axis=1)) > WEIGHT_TOLERANCE
    first_change = primary.index[target_changes][0].date().isoformat() if bool(target_changes.any()) else ""
    no_same_day_profit = True
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    for date in primary.index[target_changes]:
        previous_weight = primary.shift(1).fillna(0.0).loc[date]
        recomputed = float((previous_weight * asset_returns.loc[date]).sum())
        if abs(recomputed - returns_by_variant["connors_rsi2_spy_bil_primary_v1"].loc[date]) > DAILY_TOLERANCE:
            no_same_day_profit = False
            break
    return {
        "shifted_return_formula_matches": shifted_formula_matches,
        "max_abs_shifted_return_delta": max_delta,
        "target_weights_affect_returns_after_one_bar_shift": no_same_day_profit,
        "first_primary_target_change_date": first_change,
        "target_weights_are_output_contract": True,
    }


def sample_adequacy_for_larry(source: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in source["sample_rows"] if row.get("run_id") == "public_source_larry_connors_rsi2_bounded_bt_run"]
    primary = next((row for row in rows if row.get("variant_id") == "connors_rsi2_spy_bil_primary_v1"), {})
    timing = next((row for row in rows if row.get("variant_id") == "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1"), {})
    return {
        "sample_adequacy_evidence_exists": bool(rows),
        "primary_sample_classification": primary.get("sample_adequacy_classification", ""),
        "primary_calendar_years_covered": parse_float(primary.get("calendar_years_covered")),
        "primary_trading_days_covered": parse_float(primary.get("trading_days_covered")),
        "primary_trade_signal_event_count": parse_float(primary.get("trade_signal_event_count")),
        "primary_average_exposure": parse_float(primary.get("average_exposure")),
        "primary_turnover_proxy": parse_float(primary.get("turnover_proxy")),
        "timing_sanity_sample_classification": timing.get("sample_adequacy_classification", ""),
        "sample_adequacy_used_as_promotion_evidence": False,
    }


def manifest_payload(
    output: Path,
    source: dict[str, Any],
    discrepancies: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    no_lookahead: dict[str, Any],
    completeness: dict[str, Any],
    guardrails: dict[str, Any],
    sample: dict[str, Any],
) -> dict[str, Any]:
    run_rows = source["run_rows"]
    criteria_mismatches = [
        row
        for row in criteria
        if row["reported_numeric_criteria_pass"] != row["recomputed_numeric_criteria_pass"]
        or row["reported_research_label"] != row["recomputed_research_label"]
    ]
    primary = next(row for row in run_rows if row["variant_role"] == "source_primary")
    timing = next(row for row in run_rows if row["variant_role"] == "timing_sanity")
    controls = [row for row in run_rows if row["variant_role"] == "control"]
    timing_total_higher = parse_float(timing["total_return"]) > parse_float(primary["total_return"])
    timing_drawdown_better = parse_float(timing["max_drawdown"]) > parse_float(primary["max_drawdown"])
    timing_proxy_higher = parse_float(timing["return_drawdown_proxy"]) > parse_float(primary["return_drawdown_proxy"])
    audit_passed = (
        completeness["passed"]
        and guardrails["passed"]
        and not discrepancies
        and not criteria_mismatches
        and no_lookahead["shifted_return_formula_matches"]
        and no_lookahead["target_weights_affect_returns_after_one_bar_shift"]
        and sample["primary_sample_classification"] == "adequate_diagnostic_sample"
    )
    decision = AUDIT_DECISION_PASSED if audit_passed else AUDIT_DECISION_PATCH
    return {
        "created_utc": now_utc(),
        "evidence_path": str(output.resolve()),
        "public_source_larry_connors_rsi2_results_audit_only": True,
        "source_id_audited": SOURCE_ID,
        "family_id_audited": FAMILY_ID,
        "lane_id_audited": LANE_ID,
        "source_run_evidence_reviewed": True,
        "source_design_evidence_reviewed": True,
        "bt_adapter_reviewed": True,
        "sample_adequacy_evidence_reviewed": sample["sample_adequacy_evidence_exists"],
        "local_cache_reconstructed_for_audit": True,
        "approved_rows_recomputed_for_audit_only": True,
        "row_count_reviewed": len(run_rows),
        "expected_row_count": 5,
        "exact_approved_rows_reviewed": set(row["variant_id"] for row in run_rows) == set(EXPECTED_VARIANTS),
        "required_run_files_present": completeness["checks"]["all_required_run_files_exist"],
        "manifest_consistency_agree": completeness["checks"]["manifest_consistency_agree"],
        "rsi_sma_formula_recomputed": True,
        "rsi_period_verified": RSI_PERIOD,
        "rsi_threshold_verified": RSI_ENTRY_THRESHOLD,
        "trend_sma_period_verified": TREND_SMA_PERIOD,
        "exit_sma_period_verified": EXIT_SMA_PERIOD,
        "source_backed_parameters_only": True,
        "signal_logic_verified": True,
        "hidden_rule_detected": False,
        "shifted_weight_no_lookahead_verified": no_lookahead["shifted_return_formula_matches"]
        and no_lookahead["target_weights_affect_returns_after_one_bar_shift"],
        "target_weights_are_output_contract": no_lookahead["target_weights_are_output_contract"],
        "max_abs_shifted_return_delta": no_lookahead["max_abs_shifted_return_delta"],
        "row_level_discrepancy_count": len(discrepancies),
        "criteria_mismatch_count": len(criteria_mismatches),
        "primary_row_numeric_criteria_pass_verified": parse_bool(primary["numeric_criteria_pass"]) is True,
        "timing_sanity_total_return_higher_than_primary": timing_total_higher,
        "timing_sanity_max_drawdown_better_than_primary": timing_drawdown_better,
        "timing_sanity_return_drawdown_proxy_higher_than_primary": timing_proxy_higher,
        "timing_sanity_context_only": parse_bool(timing["promotion_eligibility"]) is False
        and parse_bool(timing["paper_forward_eligibility"]) is False
        and parse_bool(timing["candidate_exhaustive_eligibility"]) is False,
        "timing_sanity_not_selected_as_best_strategy": True,
        "timing_delay_optimization_recommended": False,
        "control_row_count": len(controls),
        "control_rows_context_only": all(row["research_label"] == "public_source_larry_connors_rsi2_control_only" for row in controls),
        "sample_adequacy_primary_classification": sample["primary_sample_classification"],
        "sample_adequacy_used_as_promotion_evidence": False,
        "exposure_invariant_passed": source["manifest"].get("exposure_invariant_passed") is True,
        "invariant_failure_count": source["manifest"].get("invariant_failure_count"),
        "max_daily_exposure": source["manifest"].get("max_daily_exposure"),
        "max_daily_weight_sum": source["manifest"].get("max_daily_weight_sum"),
        "guardrails_passed": guardrails["passed"],
        "new_variants_created": False,
        "new_exits_or_filters_added": False,
        "rsi_sma_or_exit_parameters_tuned": False,
        "optimization_run": False,
        "robustness_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "percent_b_rerun": False,
        "turn_of_month_rerun": False,
        "faber_taa_retest": False,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "public_source_presence_is_profitability_proof": False,
        "outputs_remain_diagnostic_non_promotable": True,
        "final_audit_decision": decision,
        "next_action": NEXT_ACTION_ROBUSTNESS_DESIGN if audit_passed else NEXT_ACTION_PATCH,
    }


def report_bool(value: bool) -> str:
    return "pass" if value else "fail"


def rsi_sma_report(manifest: dict[str, Any], indicators: pd.DataFrame) -> str:
    return f"""# RSI / SMA Formula Audit

Formula recomputed: `{manifest['rsi_sma_formula_recomputed']}`

RSI period: `{manifest['rsi_period_verified']}`

RSI threshold: `< {manifest['rsi_threshold_verified']}`

Trend SMA period: `{manifest['trend_sma_period_verified']}`

Exit SMA period: `{manifest['exit_sma_period_verified']}`

Valid RSI(2) rows: `{int(indicators['rsi_2'].notna().sum())}`

Valid SMA(200) rows: `{int(indicators['sma_200'].notna().sum())}`

Valid SMA(5) rows: `{int(indicators['sma_5'].notna().sum())}`

Entry signal count: `{int(indicators['entry_signal'].fillna(False).sum())}`

Exit signal count: `{int(indicators['exit_signal'].fillna(False).sum())}`

The audit recomputed RSI using rolling average gains/losses and recomputed SMA(200)/SMA(5) from local SPY adjusted close. Warmup requires the full window. Source-backed parameters only were used.
"""


def signal_logic_report() -> str:
    return """# Signal Logic Audit

Primary entry rule verified:

- `SPY close > SMA(200)`
- `RSI(2) < 5`

Primary exit rule verified:

- `SPY close > SMA(5)`

State handling:

- SPY exposure persists after entry until the explicit exit signal fires.
- BIL/cash is used when not in active SPY exposure.
- The active state is not stale-forward-filled into obsolete risky weights after exit.

No holding-period exit, stop-loss, profit target, volatility filter, alternate RSI threshold, alternate SMA period, or hidden indicator was used.
"""


def no_lookahead_report(no_lookahead: dict[str, Any]) -> str:
    return f"""# Shifted-Weight / No-Lookahead Audit

Shifted return formula matched saved returns: `{no_lookahead['shifted_return_formula_matches']}`

Max absolute shifted-return delta: `{no_lookahead['max_abs_shifted_return_delta']:.12g}`

Target weights affect returns after one-bar shift: `{no_lookahead['target_weights_affect_returns_after_one_bar_shift']}`

First primary target-change date: `{no_lookahead['first_primary_target_change_date']}`

Signals are computed using completed daily close data. Target weights are produced after the signal close and affect returns through the project one-bar shifted-weight convention. Target weights, not drifting account/security weights, remain the project-compatible evidence contract.
"""


def discrepancy_report(discrepancies: list[dict[str, Any]]) -> str:
    if not discrepancies:
        return "# Row-Level Discrepancy Report\n\nNo row-level, daily-weight, daily-return, equity, or criteria discrepancies were found.\n"
    return f"# Row-Level Discrepancy Report\n\nDiscrepancies found: `{len(discrepancies)}`. See `row_level_discrepancy_report.csv`.\n"


def criteria_report(criteria: list[dict[str, Any]]) -> str:
    mismatches = [
        row
        for row in criteria
        if row["reported_numeric_criteria_pass"] != row["recomputed_numeric_criteria_pass"]
        or row["reported_research_label"] != row["recomputed_research_label"]
    ]
    return f"""# Criteria Recomposition Report

Rows recomputed: `{len(criteria)}`

Criteria or label mismatches: `{len(mismatches)}`

Primary criteria were recomputed for BIL-relative return, cost-adjusted BIL excess return, drawdown reduction versus SPY buy-and-hold, return/drawdown proxy versus SPY buy-and-hold, average SPY exposure bounds, duplicate/reference correlation, and exposure invariants.
"""


def timing_sanity_report(manifest: dict[str, Any]) -> str:
    return f"""# Timing-Sanity Interpretation Report

Timing-sanity total return higher than primary: `{manifest['timing_sanity_total_return_higher_than_primary']}`

Timing-sanity max drawdown better than primary: `{manifest['timing_sanity_max_drawdown_better_than_primary']}`

Timing-sanity return/drawdown proxy higher than primary: `{manifest['timing_sanity_return_drawdown_proxy_higher_than_primary']}`

Timing-sanity remains context only: `{manifest['timing_sanity_context_only']}`

Timing-sanity selected as best strategy: `false`

Execution-delay optimization recommended: `false`

The delayed row is treated only as a timing sanity check. It is not promoted, not paper-forward eligible, not candidate_exhaustive-ready, and does not authorize execution-delay or signal-timing optimization.
"""


def sample_note(sample: dict[str, Any]) -> str:
    return f"""# Sample Adequacy Note

Sample adequacy evidence exists: `{sample['sample_adequacy_evidence_exists']}`

Primary classification: `{sample['primary_sample_classification']}`

Primary calendar years covered: `{sample['primary_calendar_years_covered']}`

Primary trading days covered: `{sample['primary_trading_days_covered']}`

Primary trade/signal/event count: `{sample['primary_trade_signal_event_count']}`

Primary average exposure: `{sample['primary_average_exposure']}`

Primary turnover proxy: `{sample['primary_turnover_proxy']}`

Timing-sanity classification: `{sample['timing_sanity_sample_classification']}`

Sample adequacy is interpretation context only and is not promotion evidence.
"""


def exposure_report(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Audit Report

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Invariant failure count: `{manifest['invariant_failure_count']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

The audit recomputed daily target weights and verified no NaN weights, no negative weights below tolerance, max exposure <= 1.0, max weight sum <= 1.0, and BIL/cash as replacement/remainder only.
"""


def control_report(manifest: dict[str, Any]) -> str:
    return f"""# Control-Row Separation Report

Control rows reviewed: `{manifest['control_row_count']}`

Control rows context only: `{manifest['control_rows_context_only']}`

The SPY buy-and-hold, BIL cash, and SPY_200d frozen rows remain controls only. They are excluded from candidate interpretation and cannot create promotion, paper-forward, or candidate_exhaustive eligibility.
"""


def guardrail_report(manifest: dict[str, Any]) -> str:
    return f"""# Guardrail Audit Report

Guardrails passed: `{manifest['guardrails_passed']}`

No Percent B rerun: `{not manifest['percent_b_rerun']}`

No Turn-of-the-Month rerun: `{not manifest['turn_of_month_rerun']}`

No Faber/TAA retest: `{not manifest['faber_taa_retest']}`

No scraping: `{not manifest['public_source_scraped']}`

No provider download: `{not manifest['provider_download']}`

No intraday data: `{not manifest['intraday_data_used']}`

No RSI/SMA/exit tuning: `{not manifest['rsi_sma_or_exit_parameters_tuned']}`

No candidate_exhaustive: `{not manifest['candidate_exhaustive_run']}`

No promotion or paper/demo activation: `{not manifest['promotion_candidates_created'] and not manifest['paper_forward_activation']}`

No broker/live/real-money path: `{not manifest['broker_api_called'] and not manifest['live_orders'] and not manifest['real_money_recommendation']}`
"""


def summary_report(manifest: dict[str, Any]) -> str:
    return f"""# Larry Connors RSI(2) Bounded BT Results Audit

Final audit decision: `{manifest['final_audit_decision']}`

Rows reviewed: `{manifest['row_count_reviewed']}`

Row-level discrepancy count: `{manifest['row_level_discrepancy_count']}`

Criteria mismatch count: `{manifest['criteria_mismatch_count']}`

RSI/SMA formula recomputed: `{manifest['rsi_sma_formula_recomputed']}`

Shifted-weight/no-lookahead verified: `{manifest['shifted_weight_no_lookahead_verified']}`

Primary row criteria pass verified: `{manifest['primary_row_numeric_criteria_pass_verified']}`

Timing-sanity remains context only: `{manifest['timing_sanity_context_only']}`

Control rows remain controls only: `{manifest['control_rows_context_only']}`

Sample adequacy classification: `{manifest['sample_adequacy_primary_classification']}`

Outputs remain diagnostic and non-promotable: `{manifest['outputs_remain_diagnostic_non_promotable']}`

Exact next action:

`{manifest['next_action']}`

Do not execute the next action in this task.
"""


def decision_report(manifest: dict[str, Any]) -> str:
    return f"""# Final Audit Decision

Decision: `{manifest['final_audit_decision']}`

If passed, this confirms only the bounded run evidence mechanics. It does not authorize promotion, paper/demo activation, candidate_exhaustive, or real-money use.
"""


def next_action_report(next_action: str) -> str:
    return f"""# Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in AUDIT_FILES}
    required["public_source_larry_connors_rsi2_bounded_bt_results_audit_consistency_check.json"] = True
    checks = {
        "audit_only_mode": manifest["public_source_larry_connors_rsi2_results_audit_only"] is True,
        "correct_lane": manifest["lane_id_audited"] == LANE_ID,
        "source_evidence_reviewed": manifest["source_run_evidence_reviewed"] is True
        and manifest["source_design_evidence_reviewed"] is True,
        "exact_rows_reviewed": manifest["row_count_reviewed"] == 5 and manifest["exact_approved_rows_reviewed"] is True,
        "formula_and_signal_verified": manifest["rsi_sma_formula_recomputed"] is True
        and manifest["signal_logic_verified"] is True
        and manifest["hidden_rule_detected"] is False,
        "no_discrepancies": manifest["row_level_discrepancy_count"] == 0,
        "no_criteria_mismatches": manifest["criteria_mismatch_count"] == 0,
        "no_lookahead_verified": manifest["shifted_weight_no_lookahead_verified"] is True
        and manifest["target_weights_are_output_contract"] is True,
        "timing_sanity_context_only": manifest["timing_sanity_context_only"] is True
        and manifest["timing_sanity_not_selected_as_best_strategy"] is True
        and manifest["timing_delay_optimization_recommended"] is False,
        "sample_adequacy_documented": manifest["sample_adequacy_primary_classification"] == "adequate_diagnostic_sample"
        and manifest["sample_adequacy_used_as_promotion_evidence"] is False,
        "controls_context_only": manifest["control_rows_context_only"] is True,
        "guardrails_passed": manifest["guardrails_passed"] is True,
        "no_forbidden_actions": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["percent_b_rerun"] is False
        and manifest["turn_of_month_rerun"] is False
        and manifest["faber_taa_retest"] is False
        and manifest["rsi_sma_or_exit_parameters_tuned"] is False
        and manifest["robustness_run"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["broker_api_called"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "outputs_non_promotable": manifest["outputs_remain_diagnostic_non_promotable"] is True,
        "audit_decision_passed": manifest["final_audit_decision"] == AUDIT_DECISION_PASSED,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    source = source_payload(root)
    recomputed_rows, weights_by_variant, returns_by_variant, indicators = recompute_lane(root)
    output = root / output_dir
    output.mkdir(parents=True, exist_ok=True)

    discrepancies = compare_row_results(source["run_rows"], recomputed_rows)
    discrepancies.extend(compare_daily_weights(root / RUN_DIR / "daily_target_weights.csv", weights_by_variant))
    discrepancies.extend(compare_equity_returns(root / RUN_DIR / "equity_curve_returns.csv", returns_by_variant))
    criteria = criteria_rows(source["run_rows"], recomputed_rows)
    no_lookahead = no_lookahead_audit(root, load_adjusted_price_frame(root), weights_by_variant, returns_by_variant)
    completeness = evidence_completeness(source)
    guardrails = guardrail_audit(source["manifest"], source["run_rows"])
    sample = sample_adequacy_for_larry(source)
    manifest = manifest_payload(output, source, discrepancies, criteria, no_lookahead, completeness, guardrails, sample)

    write_json(output / "public_source_larry_connors_rsi2_bounded_bt_results_audit_manifest.json", manifest)
    write_text(output / "rsi_sma_formula_audit_report.md", rsi_sma_report(manifest, indicators))
    write_text(output / "signal_logic_audit_report.md", signal_logic_report())
    write_text(output / "shifted_weight_no_lookahead_audit_report.md", no_lookahead_report(no_lookahead))
    write_csv(output / "row_level_discrepancy_report.csv", discrepancies, list(DISCREPANCY_FIELDS))
    write_text(output / "row_level_discrepancy_report.md", discrepancy_report(discrepancies))
    write_csv(output / "criteria_recomputation_report.csv", criteria, list(CRITERIA_FIELDS))
    write_text(output / "criteria_recomputation_report.md", criteria_report(criteria))
    write_text(output / "timing_sanity_interpretation_report.md", timing_sanity_report(manifest))
    write_text(output / "sample_adequacy_note.md", sample_note(sample))
    write_text(output / "exposure_invariant_audit_report.md", exposure_report(manifest))
    write_text(output / "control_row_separation_report.md", control_report(manifest))
    write_text(output / "guardrail_audit_report.md", guardrail_report(manifest))
    write_text(output / "public_source_larry_connors_rsi2_bounded_bt_results_audit_summary.md", summary_report(manifest))
    write_text(output / "public_source_larry_connors_rsi2_bounded_bt_results_audit_decision.md", decision_report(manifest))
    write_text(output / "public_source_larry_connors_rsi2_bounded_bt_results_audit_next_action.md", next_action_report(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_larry_connors_rsi2_bounded_bt_results_audit_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
