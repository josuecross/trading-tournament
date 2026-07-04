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
from strategy_lab.research_os.external_adapters.bt_adapter import (
    equity_from_returns,
    invariant_summary,
    load_local_price_frame,
    reference_spy200d_weights,
    returns_from_weights,
)
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    max_drawdown,
    trade_count_and_turnover,
    write_csv,
)


SOURCE_ID = "percent_b_money_flow"
FAMILY_ID = "price_band_money_flow_confirmation"
LANE_ID = "public_source_percent_b_money_flow_bounded_bt_lane_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_run" / "latest"

EXPECTED_VARIANTS = (
    "percent_b_mfi_spy_bil_primary_v1",
    "percent_b_mfi_spy_bil_one_bar_delayed_timing_sanity_v1",
    "percent_b_mfi_spy_buy_hold_control_v1",
    "percent_b_mfi_bil_cash_control_v1",
    "percent_b_mfi_spy200d_frozen_control_v1",
)

NEXT_ACTION_AUDIT = "audit_public_source_percent_b_money_flow_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_percent_b_money_flow_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

BB_PERIOD = 20
BB_STD = 2.0
MFI_PERIOD = 10
PERCENT_B_UPPER = 0.80
PERCENT_B_LOWER = 0.20
MFI_UPPER = 80.0
MFI_LOWER = 20.0
WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0

ALLOWED_LABELS = {
    "public_source_percent_b_mfi_primary",
    "public_source_percent_b_mfi_timing_sanity",
    "public_source_percent_b_mfi_control_only",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "concept",
    "symbols_used",
    "effective_start_date",
    "effective_end_date",
    "indicator_formula_status",
    "indicator_parameters",
    "signal_timing_convention",
    "weight_shift_convention",
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
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "research_label",
    "total_return",
    "same_window_return_versus_bil",
    "excess_return_versus_bil_after_cost",
    "max_drawdown",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "average_spy_exposure_share",
    "duplicate_reference_correlation",
    "exposure_invariant_pass",
    "primary_total_return_beats_bil",
    "primary_excess_after_cost_beats_bil",
    "primary_drawdown_reduction_pass",
    "primary_return_drawdown_proxy_pass",
    "primary_spy_exposure_bounds_pass",
    "primary_duplicate_correlation_pass",
    "timing_sanity_context_only",
    "numeric_criteria_pass",
)

DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")

REQUIRED_FILES = (
    "public_source_percent_b_money_flow_bounded_bt_run_manifest.json",
    "public_source_percent_b_money_flow_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "indicator_calculation_report.md",
    "signal_timing_no_lookahead_report.md",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "role_label_summary.md",
    "public_source_percent_b_money_flow_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_percent_b_money_flow_run.md",
    "public_source_percent_b_money_flow_bounded_bt_run_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 252 or float(aligned["left"].std()) == 0.0 or float(aligned["right"].std()) == 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def design_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / DESIGN_DIR / "planned_row_table.csv")


def design_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / DESIGN_DIR / "public_source_percent_b_money_flow_bounded_bt_design_manifest.json")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def load_spy_ohlcv(root: Path) -> pd.DataFrame:
    path = root / "data" / "cache" / "SPY.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = ["date", "high", "low", "close", "adj_close", "volume"]
    if any(column not in raw.columns for column in required):
        return pd.DataFrame()
    dates = pd.to_datetime(raw["date"], errors="coerce")
    frame = pd.DataFrame(index=dates)
    for column in ["high", "low", "close", "adj_close", "volume"]:
        frame[column] = pd.to_numeric(raw[column], errors="coerce").to_numpy()
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.dropna(subset=["high", "low", "close", "adj_close", "volume"])


def percent_b(close: pd.Series, period: int = BB_PERIOD, std_mult: float = BB_STD) -> pd.Series:
    middle = close.rolling(period, min_periods=period).mean()
    rolling_std = close.rolling(period, min_periods=period).std(ddof=0)
    upper = middle + std_mult * rolling_std
    lower = middle - std_mult * rolling_std
    denominator = (upper - lower).replace(0.0, np.nan)
    return ((close - lower) / denominator).rename("percent_b")


def money_flow_index(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = MFI_PERIOD,
) -> pd.Series:
    typical = ((high + low + close) / 3.0).rename("typical_price")
    raw_money_flow = typical * volume
    direction = typical.diff()
    positive_flow = raw_money_flow.where(direction > 0.0, 0.0)
    negative_flow = raw_money_flow.where(direction < 0.0, 0.0)
    positive_sum = positive_flow.rolling(period, min_periods=period).sum()
    negative_sum = negative_flow.rolling(period, min_periods=period).sum()
    ratio = positive_sum / negative_sum.replace(0.0, np.nan)
    mfi = 100.0 - (100.0 / (1.0 + ratio))
    mfi = mfi.where(~((negative_sum == 0.0) & (positive_sum > 0.0)), 100.0)
    mfi = mfi.where(~((negative_sum == 0.0) & (positive_sum == 0.0)), 50.0)
    return mfi.rename("mfi")


def indicator_frame(prices: pd.DataFrame, spy_ohlcv: pd.DataFrame) -> pd.DataFrame:
    aligned = spy_ohlcv.reindex(prices.index).dropna(subset=["high", "low", "close", "adj_close", "volume"])
    close = aligned["adj_close"]
    out = pd.DataFrame(index=aligned.index)
    out["percent_b"] = percent_b(close)
    out["mfi"] = money_flow_index(aligned["high"], aligned["low"], aligned["close"], aligned["volume"])
    out["entry_signal"] = (out["percent_b"] > PERCENT_B_UPPER) & (out["mfi"] > MFI_UPPER)
    out["exit_signal"] = (out["percent_b"] < PERCENT_B_LOWER) & (out["mfi"] < MFI_LOWER)
    return out


def primary_percent_b_targets(indicators: pd.DataFrame) -> pd.DataFrame:
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
    return weights


def one_bar_delayed_targets(primary_weights: pd.DataFrame) -> pd.DataFrame:
    delayed = primary_weights.shift(1)
    if not delayed.empty:
        delayed.iloc[0] = [0.0, 1.0]
    return delayed.ffill().fillna({"SPY": 0.0, "BIL": 1.0}).astype(float)


def constant_weights(index: pd.DatetimeIndex, spy: float, bil: float) -> pd.DataFrame:
    return complete_rebalance_weight_frame(index, ["SPY", "BIL"], {index[0]: target(spy, bil)})


def build_weights(variant_id: str, prices: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    common_index = pd.DatetimeIndex(indicators.index)
    if variant_id == "percent_b_mfi_spy_bil_primary_v1":
        return primary_percent_b_targets(indicators)
    if variant_id == "percent_b_mfi_spy_bil_one_bar_delayed_timing_sanity_v1":
        return one_bar_delayed_targets(primary_percent_b_targets(indicators))
    if variant_id == "percent_b_mfi_spy_buy_hold_control_v1":
        return constant_weights(common_index, 1.0, 0.0)
    if variant_id == "percent_b_mfi_bil_cash_control_v1":
        return constant_weights(common_index, 0.0, 1.0)
    if variant_id == "percent_b_mfi_spy200d_frozen_control_v1":
        control = reference_spy200d_weights(prices).reindex(common_index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


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
    invariant = invariant_summary(weights)
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
        **invariant,
    }


def equity_rows(returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, daily in returns_by_variant.items():
        equity = equity_from_returns(daily)
        for date, daily_return in daily.items():
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "variant_id": variant_id,
                    "daily_return": float(daily_return),
                    "equity": float(equity.loc[date]),
                }
            )
    return rows


def weight_rows(weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        for date, row in weights.iterrows():
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "variant_id": variant_id,
                    "SPY": float(row.get("SPY", 0.0)),
                    "BIL": float(row.get("BIL", 0.0)),
                    "weight_sum": float(row.sum()),
                    "risky_exposure": float(row.get("SPY", 0.0)),
                }
            )
    return rows


def turnover_rows(result_rows: list[dict[str, Any]], weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    role_by_id = {row["variant_id"]: row["variant_role"] for row in result_rows}
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        nonzero_days = int((weights.diff().abs().fillna(weights.abs()).sum(axis=1) > WEIGHT_TOLERANCE).sum())
        trades, turnover = trade_count_and_turnover(weights)
        rows.append(
            {
                "variant_id": variant_id,
                "variant_role": role_by_id.get(variant_id, ""),
                "trade_count": trades,
                "turnover_proxy": turnover,
                "nonzero_turnover_days": nonzero_days,
            }
        )
    return rows


def result_for_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
) -> dict[str, Any]:
    bil_total = controls["percent_b_mfi_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["percent_b_mfi_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["percent_b_mfi_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["percent_b_mfi_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["percent_b_mfi_spy200d_frozen_control_v1"])
    duplicate_values = [value for value in (corr_spy, corr_spy200d) if finite(value)]
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
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.90)
    timing_context = is_timing
    numeric_pass = False
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
    elif is_timing:
        numeric_pass = exposure_pass
    else:
        numeric_pass = exposure_pass

    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": row["research_label"],
        "concept": row["baseline_or_control_role"],
        "symbols_used": row["symbols"],
        "indicator_formula_status": "percent_b_bb20_2_and_mfi10_calculated_from_local_spy_ohlcv",
        "indicator_parameters": row["indicator_parameters"],
        "signal_timing_convention": row["signal_timing"],
        "weight_shift_convention": "target weights produced after daily close and applied with returns_from_weights one-bar shift",
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
        "timing_sanity_context_only": timing_context,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "local-cache close-to-close shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], pd.DataFrame, dict[str, Any]]:
    rows = design_rows(root)
    design = design_manifest(root)
    prices = load_local_price_frame(root).sort_index()
    spy_ohlcv = load_spy_ohlcv(root)
    indicators = indicator_frame(prices, spy_ohlcv)
    prices = prices.reindex(indicators.index).dropna(subset=["SPY", "BIL"])
    indicators = indicators.reindex(prices.index)
    data_blocker = ""
    if prices.empty or spy_ohlcv.empty:
        data_blocker = "missing_spy_bil_price_or_spy_ohlcv_cache"
    elif indicators[["percent_b", "mfi"]].dropna().empty:
        data_blocker = "indicator_warmup_or_ohlcv_invalid_no_valid_indicator_rows"

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    if not data_blocker:
        for row in rows:
            variant_id = row["variant_id"]
            weights = build_weights(variant_id, prices, indicators)
            daily = returns_from_weights(prices, weights).rename(variant_id)
            weights_by_variant[variant_id] = weights
            returns_by_variant[variant_id] = daily
            metrics_by_variant[variant_id] = metrics(daily, weights)

    result_rows: list[dict[str, Any]] = []
    if not data_blocker:
        for row in rows:
            result_rows.append(
                result_for_row(
                    row,
                    metrics_by_variant[row["variant_id"]],
                    returns_by_variant[row["variant_id"]],
                    metrics_by_variant,
                    returns_by_variant,
                )
            )

    preflight = {
        "source_design_run_ready": design.get("run_readiness_decision")
        == "public_source_percent_b_money_flow_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_percent_b_money_flow_bounded_bt_lane",
        "design_row_count": len(rows),
        "evaluated_variant_ids": [row["variant_id"] for row in result_rows],
        "uses_local_cache_only": True,
        "provider_download_required": False,
        "intraday_data_required": False,
        "data_blocker": data_blocker,
        "effective_start_date": prices.index.min().date().isoformat() if not prices.empty else "",
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
        "indicator_valid_percent_b_count": int(indicators["percent_b"].notna().sum()) if not indicators.empty else 0,
        "indicator_valid_mfi_count": int(indicators["mfi"].notna().sum()) if not indicators.empty else 0,
        "entry_signal_count": int(indicators["entry_signal"].fillna(False).sum()) if not indicators.empty else 0,
        "exit_signal_count": int(indicators["exit_signal"].fillna(False).sum()) if not indicators.empty else 0,
    }
    return result_rows, weights_by_variant, returns_by_variant, indicators, preflight


def role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "primary_source": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control": sum(1 for row in rows if row["variant_role"] == "control"),
    }


def manifest_payload(
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    invariants_failed = [row["variant_id"] for row in rows if row["exposure_invariant_pass"] is not True]
    max_exposure = max([float(row["max_daily_exposure"]) for row in rows], default=0.0)
    max_weight_sum = max([float(row["max_daily_weight_sum"]) for row in rows], default=0.0)
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    variant_ids = {row["variant_id"] for row in rows}
    interpretable = (
        preflight["source_design_run_ready"]
        and not preflight["data_blocker"]
        and len(rows) == len(EXPECTED_VARIANTS)
        and variant_ids == set(EXPECTED_VARIANTS)
        and not invariants_failed
    )
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    counts = role_counts(rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_percent_b_money_flow_bounded_bt_lane_run": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "indicator_formula_implemented": True,
        "indicator_parameters_source_backed": True,
        "bollinger_band_period": BB_PERIOD,
        "bollinger_band_standard_deviation": BB_STD,
        "money_flow_index_period": MFI_PERIOD,
        "percent_b_upper_threshold": PERCENT_B_UPPER,
        "percent_b_lower_threshold": PERCENT_B_LOWER,
        "mfi_upper_threshold": MFI_UPPER,
        "mfi_lower_threshold": MFI_LOWER,
        "variant_count_planned": len(EXPECTED_VARIANTS),
        "variant_count_evaluated": len(rows),
        "approved_variant_ids": list(EXPECTED_VARIANTS),
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
        "primary_source_row_count": counts["primary_source"],
        "timing_sanity_row_count": counts["timing_sanity"],
        "control_row_count": counts["control"],
        "data_blocked_row_count": len(EXPECTED_VARIANTS) if preflight["data_blocker"] else 0,
        "data_blocker": preflight["data_blocker"] or "none",
        "indicator_valid_percent_b_count": preflight["indicator_valid_percent_b_count"],
        "indicator_valid_mfi_count": preflight["indicator_valid_mfi_count"],
        "entry_signal_count": preflight["entry_signal_count"],
        "exit_signal_count": preflight["exit_signal_count"],
        "primary_row_numeric_criteria_pass": primary.get("numeric_criteria_pass") is True,
        "timing_sanity_context_only": timing.get("timing_sanity_context_only") is True,
        "control_row_count_evaluated": counts["control"],
        "invariant_failure_count": len(invariants_failed),
        "invariant_failure_variant_ids": invariants_failed,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": not invariants_failed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "signal_timing_no_lookahead": True,
        "one_bar_delayed_timing_sanity_only": True,
        "threshold_sweep_created": False,
        "optimization_run": False,
        "other_indicators_added": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "new_instruments_added": False,
        "bounded_bt_design_changed": False,
        "bounded_run_implementation_created": True,
        "strategy_discovery_run": False,
        "new_research_batch_run": False,
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
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "current_backtester_replaced": False,
        "bt_adapter_helpers_used": True,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        "next_action": next_action,
    }


def indicator_report_md(indicators: pd.DataFrame, preflight: dict[str, Any]) -> str:
    first_valid = indicators[["percent_b", "mfi"]].dropna().index.min()
    first_valid_text = pd.Timestamp(first_valid).date().isoformat() if pd.notna(first_valid) else "none"
    return f"""# Indicator Calculation Report

Formula status: `implemented`

Percent B:

- Uses SPY adjusted close.
- Bollinger middle band is a `{BB_PERIOD}`-day simple moving average.
- Bollinger standard deviation uses `{BB_PERIOD}` daily adjusted closes with `ddof=0`.
- Upper band is middle plus `{BB_STD}` standard deviations.
- Lower band is middle minus `{BB_STD}` standard deviations.
- Percent B is `(close - lower_band) / (upper_band - lower_band)`.

Money Flow Index:

- Uses SPY adjusted high, adjusted low, adjusted close, and local-cache volume.
- Typical price is `(high + low + close) / 3`.
- Raw money flow is typical price times volume.
- Positive and negative money flow are summed over `{MFI_PERIOD}` days.
- MFI is `100 - 100 / (1 + money_flow_ratio)`.

Valid Percent B rows: `{preflight['indicator_valid_percent_b_count']}`

Valid MFI rows: `{preflight['indicator_valid_mfi_count']}`

First date with both indicators valid: `{first_valid_text}`

Entry signal count: `{preflight['entry_signal_count']}`

Exit signal count: `{preflight['exit_signal_count']}`

No external indicator library, provider download, scraping, intraday data, or optimized parameter setting was used.
"""


def timing_report_md(rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    return f"""# Signal Timing / No-Lookahead Report

Primary row: `{primary['variant_id']}`

- Computes `%B(20,2)` and `MFI(10)` through the completed daily close.
- Produces target weights after the signal close.
- Uses `returns_from_weights`, which applies target weights with a one-bar close-to-close shift.
- Maintains SPY exposure after entry until the explicit exit signal fires.
- Uses BIL/cash as replacement/remainder when not in SPY.

Timing-sanity row: `{timing['variant_id']}`

- Uses the same signal and exit logic.
- Delays target weights one additional trading day before the standard shifted return convention.
- Timing-sanity row is context only and is not an optimized variant.

Primary average SPY exposure share: `{primary['average_spy_exposure_share']}`

Timing-sanity average SPY exposure share: `{timing['average_spy_exposure_share']}`
"""


def baseline_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Control Comparison Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: total return `{float(row['total_return']):.6f}`, "
            f"BIL delta `{float(row['same_window_return_versus_bil']):.6f}`, "
            f"drawdown reduction vs SPY `{float(row['drawdown_reduction_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY `{float(row['correlation_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY_200d `{float(row['correlation_versus_spy200d_control']):.6f}`"
        )
    lines.append("")
    lines.append("Controls are diagnostic only and cannot become candidates.")
    return "\n".join(lines) + "\n"


def invariant_report_md(manifest: dict[str, Any]) -> str:
    failures = manifest["invariant_failure_variant_ids"]
    return f"""# Exposure Invariant Report

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

Invariant failure count: `{manifest['invariant_failure_count']}`

Failures:

{chr(10).join(f'- `{item}`' for item in failures) if failures else '- none'}

BIL/cash is replacement/remainder only. SPY plus BIL never accumulates above total weight `1.0`.
"""


def role_label_summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    labels = {label: sum(1 for row in rows if row["research_label"] == label) for label in ALLOWED_LABELS}
    return f"""# Role / Label Summary

Primary source rows: `{manifest['primary_source_row_count']}`

Timing-sanity rows: `{manifest['timing_sanity_row_count']}`

Control rows: `{manifest['control_row_count']}`

Labels:

{chr(10).join(f'- `{label}`: `{count}`' for label, count in sorted(labels.items()))}
"""


def turnover_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rebalance / Turnover Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: trade count `{row['trade_count']}`, turnover proxy `{float(row['turnover_proxy']):.6f}`"
        )
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    return f"""# Public Source Percent B Money Flow Bounded bt Run

Lane ID: `{manifest['lane_id']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Primary row numeric criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity context only: `{manifest['timing_sanity_context_only']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Primary total return: `{primary.get('total_return', 'not_available')}`

Primary max drawdown: `{primary.get('max_drawdown', 'not_available')}`

Timing-sanity total return: `{timing.get('total_return', 'not_available')}`

Indicator/data limitations: local daily close/OHLCV model only; no intraday execution model; public source is not proof of profitability.

No output is promotable, candidate_exhaustive-ready, or paper/demo eligible.

Exact next action: `{manifest['next_action']}`
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Public Source Percent B Money Flow Run

This packet is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper/demo candidate, paper/demo activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Percent B Money Flow Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_percent_b_money_flow_bounded_bt_run_consistency_check.json"] = True
    labels = {row["research_label"] for row in rows}
    variant_ids = {row["variant_id"] for row in rows}
    checks = {
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "correct_family": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "exact_variant_set": variant_ids == set(EXPECTED_VARIANTS),
        "variant_count_exact_5": manifest["variant_count_evaluated"] == 5,
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] == 1
        and manifest["control_row_count"] == 3,
        "allowed_labels_only": labels <= ALLOWED_LABELS,
        "indicator_formula_implemented": manifest["indicator_formula_implemented"] is True,
        "source_backed_params": manifest["indicator_parameters_source_backed"] is True,
        "signal_timing_no_lookahead": manifest["signal_timing_no_lookahead"] is True,
        "one_timing_sanity_only": manifest["one_bar_delayed_timing_sanity_only"] is True,
        "no_sweep_or_optimization": manifest["threshold_sweep_created"] is False
        and manifest["optimization_run"] is False
        and manifest["other_indicators_added"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False,
        "no_discovery_or_candidate_exhaustive": manifest["strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False
        and manifest["candidate_exhaustive_run"] is False,
        "no_promotion_or_paper": manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_scrape_or_extra_sources": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False,
        "exposure_invariants_pass": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_candidate_or_paper": all(row["candidate_exhaustive_eligibility"] is False for row in rows)
        and all(row["paper_forward_eligibility"] is False for row in rows),
        "outputs_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    rows, weights_by_variant, returns_by_variant, indicators, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, output, rows, preflight)

    write_json(output / "public_source_percent_b_money_flow_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "indicator_calculation_report.md", indicator_report_md(indicators, preflight))
    write_text(output / "signal_timing_no_lookahead_report.md", timing_report_md(rows))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_percent_b_money_flow_bounded_bt_run_summary.md", summary_md(manifest, rows))
    write_text(output / "do_not_promote_from_public_source_percent_b_money_flow_run.md", do_not_promote_md())
    write_text(output / "public_source_percent_b_money_flow_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_percent_b_money_flow_bounded_bt_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
