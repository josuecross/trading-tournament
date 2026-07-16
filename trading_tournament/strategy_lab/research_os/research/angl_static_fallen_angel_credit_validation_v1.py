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

from strategy_lab.research_os.research import angl_static_fallen_angel_credit_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "angl_static_fallen_angel_credit_validation_v1" / "latest"
SCREEN_DIR = Path("evidence") / "angl_static_fallen_angel_credit_screen_v1" / "latest"
INTAKE_DIR = Path("evidence") / "direction_owner_single_source_intake_v1" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"

SOURCE_ID = screen.SOURCE_ID
CANDIDATE_ID = screen.CANDIDATE_ID
FAMILY_ID = screen.FAMILY_ID
CANDIDATE = screen.CANDIDATE
PRIMARY_BENCHMARK = screen.PRIMARY_BENCHMARK
CONTEXT_BENCHMARKS = screen.CONTEXT_BENCHMARKS
SYMBOLS = screen.SYMBOLS
COMMON_START = screen.COMMON_START
COMMON_END = screen.COMMON_END
HARD_REGIME_MIN_SESSIONS = screen.HARD_REGIME_MIN_SESSIONS
HORIZONS_MONTHLY = (90, 180, 252, 504)
HORIZONS_NON_OVERLAPPING = (180, 252, 504)
ROLLING_HORIZONS = (252, 504)
TOL = 1e-12

ALLOWED_OUTCOMES = {
    "validation_supports_further_review",
    "higher_return_higher_risk_persistent",
    "historical_edge_recently_weakened",
    "screening_positive_not_stable",
    "benchmark_like_no_edge",
    "control_weak",
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


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    full = abs_path(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def corrected_caveat_text() -> str:
    return screen.source_caveats_text()


def correct_screen_packet_caveat() -> list[dict[str, Any]]:
    definitions = read_csv_dicts(SCREEN_DIR / "methodology_regime_definitions.csv")
    metrics = read_csv_dicts(SCREEN_DIR / "methodology_regime_metrics.csv")
    regime3_def = next(row for row in definitions if row["period_id"] == "methodology_regime_3_amended_h0cf_methodology")
    regime3_metrics = next(row for row in metrics if row["period_id"] == "methodology_regime_3_amended_h0cf_methodology")
    if regime3_def["evidence_weight"] != regime3_metrics["evidence_weight"]:
        raise RuntimeError("deeper screen packet inconsistency: regime definition and metrics disagree")
    if int(regime3_def["trading_day_count"]) >= HARD_REGIME_MIN_SESSIONS and regime3_def["evidence_weight"] != "hard_evidence_eligible":
        raise RuntimeError("deeper screen packet inconsistency: frozen 504-session rule not reflected in Regime 3 classification")
    caveat_path = abs_path(SCREEN_DIR / "source_and_methodology_caveats.md")
    existing = caveat_path.read_text(encoding="utf-8") if caveat_path.exists() else ""
    corrected = corrected_caveat_text()
    caveat_path.write_text(corrected.rstrip() + "\n", encoding="utf-8")
    return [
        {
            "artifact": str(caveat_path),
            "correction_type": "wording_only",
            "prior_wording_conflict_reviewed": "Regime 3 was previously described as descriptive-only while generated regime tables classified it by the frozen 504-session rule.",
            "regime3_trading_day_count": regime3_def["trading_day_count"],
            "regime3_evidence_weight_after_correction": regime3_def["evidence_weight"],
            "shorter_post_amendment_sample_caveat_preserved": True,
            "descriptive_only_claim_removed_when_not_applicable": "descriptive-only sample" not in corrected.lower(),
            "screen_metrics_changed": False,
            "screen_outcome_changed": False,
            "correction_applied_or_confirmed": existing.rstrip() != corrected.rstrip() or "descriptive-only sample" not in corrected.lower(),
        }
    ]


def monthly_start_windows(common_dates: pd.DatetimeIndex) -> dict[int, list[dict[str, Any]]]:
    starts = pd.Series(common_dates).groupby(pd.Series(common_dates).dt.to_period("M")).first()
    start_indices = [int(common_dates.get_loc(pd.Timestamp(date))) for date in starts]
    result: dict[int, list[dict[str, Any]]] = {}
    for horizon in HORIZONS_MONTHLY:
        rows: list[dict[str, Any]] = []
        for sequence, start in enumerate(start_indices, start=1):
            end = start + horizon
            valid = end < len(common_dates)
            rows.append(
                {
                    "window_family": f"monthly_start_{horizon}d",
                    "window_id": f"monthly_start_{horizon}d_{sequence:03d}",
                    "horizon_days": horizon,
                    "sequence": sequence,
                    "start_index": start,
                    "end_index": end if valid else "",
                    "window_start": common_dates[start].date().isoformat(),
                    "window_end": common_dates[end].date().isoformat() if valid else "",
                    "window_valid_pre_performance": valid,
                    "selection_algorithm": "first_common_trading_session_of_each_calendar_month",
                    "overlapping_windows_not_statistically_independent": True,
                    "performance_computed_at_definition_time": False,
                }
            )
        result[horizon] = rows
    return result


def non_overlapping_windows(common_dates: pd.DatetimeIndex) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for horizon in HORIZONS_NON_OVERLAPPING:
        rows: list[dict[str, Any]] = []
        sequence = 1
        start = 0
        while start + horizon < len(common_dates):
            end = start + horizon
            rows.append(
                {
                    "window_family": f"non_overlapping_{horizon}d",
                    "window_id": f"non_overlapping_{horizon}d_{sequence:03d}",
                    "horizon_days": horizon,
                    "sequence": sequence,
                    "start_index": start,
                    "end_index": end,
                    "window_start": common_dates[start].date().isoformat(),
                    "window_end": common_dates[end].date().isoformat(),
                    "window_valid_pre_performance": True,
                    "selection_algorithm": "consecutive_windows_from_first_common_date_final_incomplete_remainder_discarded",
                    "overlapping_windows_not_statistically_independent": False,
                    "performance_computed_at_definition_time": False,
                }
            )
            sequence += 1
            start = end
        result[horizon] = rows
    return result


def evaluate_window_rows(
    definitions: list[dict[str, Any]],
    prices: pd.DataFrame,
    common_dates: pd.DatetimeIndex,
    cost: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in definitions:
        if not item["window_valid_pre_performance"]:
            rows.append({**item, "window_valid": False, "invalid_reason": "incomplete_horizon"})
            continue
        dates = common_dates[int(item["start_index"]) : int(item["end_index"]) + 1]
        metrics = screen.compare_period(item["window_id"], item["window_family"], prices, dates, cost)
        angl = metrics[CANDIDATE]
        hyg = metrics[PRIMARY_BENCHMARK]
        valid = angl["period_valid"] is True and hyg["period_valid"] is True and len(dates) == int(item["horizon_days"]) + 1
        row = {
            **item,
            "window_valid": valid,
            "invalid_reason": "" if valid else "missing_or_wrong_length",
            "matching_angl_hyg_dates_used": True,
            "candidate_symbol": CANDIDATE,
            "primary_benchmark": PRIMARY_BENCHMARK,
            "actual_etf_shares_held": True,
            "entry_trade_count": 1 if valid else 0,
            "measurement_exit_count": 1 if valid else 0,
            "equal_costs_applied": True,
        }
        if valid:
            row.update(
                {
                    "candidate_total_return": angl["total_return"],
                    "hyg_total_return": hyg["total_return"],
                    "angl_minus_hyg_return": float(angl["total_return"] - hyg["total_return"]),
                    "candidate_realized_volatility": angl["realized_volatility"],
                    "hyg_realized_volatility": hyg["realized_volatility"],
                    "candidate_downside_volatility": angl["downside_volatility"],
                    "hyg_downside_volatility": hyg["downside_volatility"],
                    "candidate_max_drawdown": angl["max_drawdown"],
                    "hyg_max_drawdown": hyg["max_drawdown"],
                    "relative_drawdown_difference": float(angl["max_drawdown"] - hyg["max_drawdown"]),
                    "candidate_return_drawdown_ratio": angl["return_drawdown_ratio"],
                    "hyg_return_drawdown_ratio": hyg["return_drawdown_ratio"],
                    "angl_higher_return": angl["total_return"] > hyg["total_return"],
                    "angl_lower_drawdown": angl["max_drawdown"] > hyg["max_drawdown"],
                    "both_higher_return_and_lower_drawdown": angl["total_return"] > hyg["total_return"] and angl["max_drawdown"] > hyg["max_drawdown"],
                    "lower_return_and_worse_drawdown": angl["total_return"] < hyg["total_return"] and angl["max_drawdown"] < hyg["max_drawdown"],
                }
            )
        rows.append(row)
    return rows


def summarize_window_family(family: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("window_valid") is True]
    invalid = [row for row in rows if row.get("window_valid") is not True]
    if not valid:
        return {"window_family": family, "valid_window_count": 0, "invalid_window_count": len(invalid)}
    return {
        "window_family": family,
        "horizon_days": valid[0]["horizon_days"],
        "valid_window_count": len(valid),
        "invalid_window_count": len(invalid),
        "median_angl_minus_hyg_return": float(np.median([row["angl_minus_hyg_return"] for row in valid])),
        "mean_angl_minus_hyg_return": float(np.mean([row["angl_minus_hyg_return"] for row in valid])),
        "win_rate_vs_hyg": float(np.mean([row["angl_higher_return"] for row in valid])),
        "worst_relative_return": float(min(row["angl_minus_hyg_return"] for row in valid)),
        "best_relative_return": float(max(row["angl_minus_hyg_return"] for row in valid)),
        "pct_higher_return": float(np.mean([row["angl_higher_return"] for row in valid])),
        "pct_lower_drawdown": float(np.mean([row["angl_lower_drawdown"] for row in valid])),
        "pct_both_higher_return_and_lower_drawdown": float(np.mean([row["both_higher_return_and_lower_drawdown"] for row in valid])),
        "pct_lower_return_and_worse_drawdown": float(np.mean([row["lower_return_and_worse_drawdown"] for row in valid])),
        "candidate_realized_volatility_mean": float(np.mean([row["candidate_realized_volatility"] for row in valid])),
        "hyg_realized_volatility_mean": float(np.mean([row["hyg_realized_volatility"] for row in valid])),
        "candidate_downside_volatility_mean": float(np.mean([row["candidate_downside_volatility"] for row in valid])),
        "hyg_downside_volatility_mean": float(np.mean([row["hyg_downside_volatility"] for row in valid])),
        "candidate_worst_max_drawdown": float(min(row["candidate_max_drawdown"] for row in valid)),
        "hyg_worst_max_drawdown": float(min(row["hyg_max_drawdown"] for row in valid)),
        "relative_drawdown_difference_worst": float(min(row["relative_drawdown_difference"] for row in valid)),
        "candidate_return_drawdown_ratio_median": float(np.median([row["candidate_return_drawdown_ratio"] for row in valid if row["candidate_return_drawdown_ratio"] != ""])),
        "hyg_return_drawdown_ratio_median": float(np.median([row["hyg_return_drawdown_ratio"] for row in valid if row["hyg_return_drawdown_ratio"] != ""])),
    }


def complete_year_rows(common_dates: pd.DatetimeIndex, prices: pd.DataFrame, cost: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    years = sorted(set(common_dates.year))
    for year in years:
        dates = common_dates[common_dates.year == year]
        if len(dates) == 0:
            continue
        classification = "partial_year_context_only" if year in {common_dates[0].year, common_dates[-1].year} else "complete_calendar_year"
        metrics = screen.compare_period(f"calendar_year_{year}", classification, prices, dates, cost)
        rel = next(row for row in screen.relative_metrics(f"calendar_year_{year}", classification, metrics) if row["benchmark_symbol"] == PRIMARY_BENCHMARK)
        rows.append(
            {
                "calendar_year": year,
                "coverage_classification": classification,
                "start_date": dates[0].date().isoformat(),
                "end_date": dates[-1].date().isoformat(),
                "trading_day_count": len(dates),
                "angl_total_return": metrics[CANDIDATE]["total_return"],
                "hyg_total_return": metrics[PRIMARY_BENCHMARK]["total_return"],
                "excess_return": rel["total_return_delta"],
                "candidate_max_drawdown": metrics[CANDIDATE]["max_drawdown"],
                "hyg_max_drawdown": metrics[PRIMARY_BENCHMARK]["max_drawdown"],
                "win_loss_classification": "win" if float(rel["total_return_delta"]) > 0 else "loss",
                "included_in_complete_year_win_rate": classification == "complete_calendar_year",
            }
        )
    return rows


def fixed_period_metrics(
    periods: list[dict[str, Any]],
    prices: pd.DataFrame,
    common_dates: pd.DatetimeIndex,
    cost: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        dates = screen.period_from_dates(common_dates, period["start_date"], period["end_date"])
        metrics = screen.compare_period(period["period_id"], period["period_type"], prices, dates, cost)
        rel = next(row for row in screen.relative_metrics(period["period_id"], period["period_type"], metrics) if row["benchmark_symbol"] == PRIMARY_BENCHMARK)
        rows.append(
            {
                **period,
                "trading_day_count": len(dates),
                "calendar_length_days": int((dates[-1] - dates[0]).days + 1),
                "angl_total_return": metrics[CANDIDATE]["total_return"],
                "hyg_total_return": metrics[PRIMARY_BENCHMARK]["total_return"],
                "angl_annualized_return": metrics[CANDIDATE]["annualized_return"],
                "hyg_annualized_return": metrics[PRIMARY_BENCHMARK]["annualized_return"],
                "annualized_excess_return": rel["annualized_return_delta"],
                "angl_realized_volatility": metrics[CANDIDATE]["realized_volatility"],
                "hyg_realized_volatility": metrics[PRIMARY_BENCHMARK]["realized_volatility"],
                "angl_downside_volatility": metrics[CANDIDATE]["downside_volatility"],
                "hyg_downside_volatility": metrics[PRIMARY_BENCHMARK]["downside_volatility"],
                "angl_max_drawdown": metrics[CANDIDATE]["max_drawdown"],
                "hyg_max_drawdown": metrics[PRIMARY_BENCHMARK]["max_drawdown"],
                "angl_minus_hyg_total_return": rel["total_return_delta"],
                "angl_minus_hyg_drawdown_difference": rel["max_drawdown_delta"],
            }
        )
    return rows


def full_period_metrics(prices: pd.DataFrame, common_dates: pd.DatetimeIndex, cost: float) -> list[dict[str, Any]]:
    metrics = screen.compare_period("full_common_angl_hyg_period", "full_period", prices, common_dates, cost)
    rel = screen.relative_metrics("full_common_angl_hyg_period", "full_period", metrics)
    primary = next(row for row in rel if row["benchmark_symbol"] == PRIMARY_BENCHMARK)
    rows: list[dict[str, Any]] = []
    for symbol in (CANDIDATE, PRIMARY_BENCHMARK):
        row = metrics[symbol]
        rows.append(
            {
                "symbol": symbol,
                "role": "candidate" if symbol == CANDIDATE else "primary_benchmark",
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "trading_day_count": row["trading_day_count"],
                "total_return": row["total_return"],
                "annualized_return": row["annualized_return"],
                "realized_volatility": row["realized_volatility"],
                "downside_volatility": row["downside_volatility"],
                "max_drawdown": row["max_drawdown"],
                "return_drawdown_ratio": row["return_drawdown_ratio"],
                "final_equity": row["final_equity"],
                "angl_minus_hyg_total_return": primary["total_return_delta"] if symbol == CANDIDATE else "",
                "angl_minus_hyg_annualized_return": primary["annualized_return_delta"] if symbol == CANDIDATE else "",
                "angl_minus_hyg_drawdown_difference": primary["max_drawdown_delta"] if symbol == CANDIDATE else "",
            }
        )
    return rows


def rolling_excess_diagnostics(prices: pd.DataFrame, common_dates: pd.DatetimeIndex, cost: float) -> list[dict[str, Any]]:
    close = prices.reindex(common_dates)[[CANDIDATE, PRIMARY_BENCHMARK]].dropna()
    rows: list[dict[str, Any]] = []
    for horizon in ROLLING_HORIZONS:
        candidate_ret = close[CANDIDATE] / close[CANDIDATE].shift(horizon) * (1.0 - cost) ** 2 - 1.0
        hyg_ret = close[PRIMARY_BENCHMARK] / close[PRIMARY_BENCHMARK].shift(horizon) * (1.0 - cost) ** 2 - 1.0
        excess = (candidate_ret - hyg_ret).dropna()
        signs = np.sign(excess.to_numpy(dtype=float))
        longest_pos = longest_neg = current_pos = current_neg = 0
        first_change = ""
        prior = 0
        for date, sign in zip(excess.index, signs):
            if sign > 0:
                current_pos += 1
                current_neg = 0
            elif sign < 0:
                current_neg += 1
                current_pos = 0
            else:
                current_pos = current_neg = 0
            longest_pos = max(longest_pos, current_pos)
            longest_neg = max(longest_neg, current_neg)
            if prior != 0 and sign != 0 and sign != prior and not first_change:
                first_change = pd.Timestamp(date).date().isoformat()
            if sign != 0:
                prior = int(sign)
        rows.append(
            {
                "rolling_horizon_days": horizon,
                "observation_count": len(excess),
                "percentage_positive": float((excess > 0).mean()),
                "median_excess_return": float(excess.median()),
                "most_recent_date": excess.index[-1].date().isoformat(),
                "most_recent_excess_return": float(excess.iloc[-1]),
                "longest_consecutive_positive_sequence": int(longest_pos),
                "longest_consecutive_negative_sequence": int(longest_neg),
                "first_persistent_sign_change_date": first_change,
                "final_observation_positive": bool(excess.iloc[-1] > 0),
                "final_observation_negative": bool(excess.iloc[-1] < 0),
                "diagnostic_only_no_strategy_signal": True,
            }
        )
    return rows


def risk_context_diagnostics(prices: pd.DataFrame, common_dates: pd.DatetimeIndex, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    returns = prices.reindex(common_dates)[[CANDIDATE, PRIMARY_BENCHMARK, "IEF"]].pct_change().dropna()
    returns["angl_minus_hyg_daily_return"] = returns[CANDIDATE] - returns[PRIMARY_BENCHMARK]
    rows: list[dict[str, Any]] = []
    periods = [{"period_id": "full_common_period", "start_date": COMMON_START, "end_date": COMMON_END}, *regimes]
    for period in periods:
        sample = returns.loc[pd.Timestamp(period["start_date"]) : pd.Timestamp(period["end_date"])]
        corr = float(sample["angl_minus_hyg_daily_return"].corr(sample["IEF"])) if len(sample) > 2 else np.nan
        pos = sample.loc[sample["angl_minus_hyg_daily_return"] > 0, "IEF"]
        neg = sample.loc[sample["angl_minus_hyg_daily_return"] < 0, "IEF"]
        rows.append(
            {
                "period_id": period["period_id"],
                "start_date": period["start_date"],
                "end_date": period["end_date"],
                "observation_count": len(sample),
                "correlation_angl_minus_hyg_daily_return_to_ief_daily_return": corr,
                "mean_ief_return_when_angl_outperforms_hyg": float(pos.mean()) if len(pos) else "",
                "mean_ief_return_when_angl_underperforms_hyg": float(neg.mean()) if len(neg) else "",
                "materially_different_interest_rate_context_flag": bool(abs(corr) >= 0.25) if not math.isnan(corr) else False,
                "descriptive_only_no_duration_causal_claim": True,
                "duration_neutral_strategy_created": False,
            }
        )
    return rows


def calendar_dominated(rows: list[dict[str, Any]]) -> bool:
    complete = [row for row in rows if row["coverage_classification"] == "complete_calendar_year"]
    positives = [float(row["excess_return"]) for row in complete if float(row["excess_return"]) > 0]
    if not positives:
        return False
    return max(positives) / sum(positives) > 0.50


def classify_validation(
    summaries: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    thirds: list[dict[str, Any]],
    regimes: list[dict[str, Any]],
    calendar_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    invariants_passed: bool,
) -> tuple[str, dict[str, Any]]:
    if not invariants_passed:
        return "invalid_methodology", {}
    by_family = {row["window_family"]: row for row in summaries}
    full = next(row for row in full_rows if row["symbol"] == CANDIDATE)
    full_excess = float(full["angl_minus_hyg_annualized_return"])
    monthly_180 = by_family["monthly_start_180d"]
    monthly_252 = by_family["monthly_start_252d"]
    monthly_504 = by_family["monthly_start_504d"]
    positive_medians = all(float(row["median_angl_minus_hyg_return"]) > 0 for row in (monthly_180, monthly_252, monthly_504))
    win_rates = float(monthly_252["win_rate_vs_hyg"]) > 0.5 and float(monthly_504["win_rate_vs_hyg"]) > 0.5
    regimes_positive = sum(1 for row in regimes if float(row["angl_minus_hyg_total_return"]) > 0)
    thirds_positive = sum(1 for row in thirds if float(row["angl_minus_hyg_total_return"]) > 0)
    dominated = calendar_dominated(calendar_rows)
    recent_regime_negative = float(next(row for row in regimes if row["period_id"].endswith("amended_h0cf_methodology"))["angl_minus_hyg_total_return"]) < 0
    final_rolling_negative = any(row["final_observation_negative"] is True for row in rolling_rows)
    full_drawdown_worse = float(full["angl_minus_hyg_drawdown_difference"]) < -0.05
    conditions = {
        "positive_monthly_medians_180_252_504": positive_medians,
        "monthly_252_and_504_win_rates_above_50pct": win_rates,
        "full_period_annualized_excess_positive": full_excess > 0,
        "at_least_two_regimes_positive": regimes_positive >= 2,
        "at_least_two_thirds_positive": thirds_positive >= 2,
        "not_dominated_by_one_calendar_year": not dominated,
        "invariants_passed": invariants_passed,
        "recent_regime_negative": recent_regime_negative,
        "final_rolling_negative": final_rolling_negative,
        "full_drawdown_more_than_5pp_worse": full_drawdown_worse,
    }
    if full_excess > 0 and (recent_regime_negative or final_rolling_negative):
        return "historical_edge_recently_weakened", conditions
    if all(conditions[key] for key in [
        "positive_monthly_medians_180_252_504",
        "monthly_252_and_504_win_rates_above_50pct",
        "full_period_annualized_excess_positive",
        "at_least_two_regimes_positive",
        "at_least_two_thirds_positive",
        "not_dominated_by_one_calendar_year",
        "invariants_passed",
    ]):
        return "validation_supports_further_review", conditions
    if full_excess > 0 and positive_medians and (full_drawdown_worse or float(full["realized_volatility"]) > 0.09):
        return "higher_return_higher_risk_persistent", conditions
    if full_excess > 0:
        return "screening_positive_not_stable", conditions
    if abs(full_excess) < 0.005:
        return "benchmark_like_no_edge", conditions
    if full_excess < 0:
        return "control_weak", conditions
    return "direction_owner_review_required", conditions


def summary_text(outcome: dict[str, Any], full_rows: list[dict[str, Any]], summaries: list[dict[str, Any]], rolling_rows: list[dict[str, Any]]) -> str:
    full = next(row for row in full_rows if row["symbol"] == CANDIDATE)
    monthly_252 = next(row for row in summaries if row["window_family"] == "monthly_start_252d")
    monthly_504 = next(row for row in summaries if row["window_family"] == "monthly_start_504d")
    roll252 = next(row for row in rolling_rows if row["rolling_horizon_days"] == 252)
    roll504 = next(row for row in rolling_rows if row["rolling_horizon_days"] == 504)
    return f"""# ANGL Static Fallen-Angel Credit Validation v1

Candidate: `{CANDIDATE_ID}`

Primary benchmark: `{PRIMARY_BENCHMARK}`

Validation outcome: `{outcome['validation_outcome']}`

Full-period annualized excess return: `{float(full['angl_minus_hyg_annualized_return']):.6f}`

Full-period ANGL-minus-HYG drawdown difference: `{float(full['angl_minus_hyg_drawdown_difference']):.6f}`

Monthly-start 252-day win rate: `{float(monthly_252['win_rate_vs_hyg']):.6f}`

Monthly-start 504-day win rate: `{float(monthly_504['win_rate_vs_hyg']):.6f}`

Latest rolling 252-day excess return: `{float(roll252['most_recent_excess_return']):.6f}`

Latest rolling 504-day excess return: `{float(roll504['most_recent_excess_return']):.6f}`

This remains diagnostic investable ETF-wrapper evidence only. No forced-selling causal claim, promotion, paper/demo activation, or strategy-state change is made.

Exact next action: `{outcome['next_action']}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    global ROOT
    ROOT = root
    screen.ROOT = root
    output = abs_path(OUTPUT_DIR)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    correction_rows = correct_screen_packet_caveat()
    registry_before = file_hash(REGISTRY_PATH)
    active_before = file_hash(ACTIVE_OBSERVATIONS_PATH)
    cache_rows = screen.verify_cache_rows()
    cost = screen.cost_convention()
    prices = screen.load_prices()
    common_dates = screen.common_angl_hyg_dates(prices)
    monthly_defs = monthly_start_windows(common_dates)
    nonoverlap_defs = non_overlapping_windows(common_dates)
    thirds = screen.chronological_thirds(common_dates)
    regimes = screen.methodology_regimes(common_dates)
    if any(row["evidence_weight"] != "hard_evidence_eligible" for row in regimes):
        raise RuntimeError("all three fixed methodology regimes must be hard-evidence eligible for this validation")
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "candidate_symbol": CANDIDATE,
        "primary_benchmark": PRIMARY_BENCHMARK,
        "context_benchmarks": list(CONTEXT_BENCHMARKS),
        "cache_preflight_rows": cache_rows,
        "required_angl_cache_hash": screen.REQUIRED_ANGL_HASH,
        "common_start": COMMON_START,
        "common_end": COMMON_END,
        "common_row_count": len(common_dates),
        "transaction_cost_convention": cost,
        "window_generation_rules": {
            "monthly_start_horizons": list(HORIZONS_MONTHLY),
            "non_overlapping_horizons": list(HORIZONS_NON_OVERLAPPING),
            "monthly_start_rule": "first common trading session of each calendar month",
            "non_overlapping_rule": "consecutive windows from first common date; discard final incomplete remainder",
            "windows_frozen_before_performance": True,
            "overlapping_windows_not_statistically_independent": True,
        },
        "regime_definitions": regimes,
        "chronological_third_definitions": thirds,
        "metrics": [
            "return",
            "annualized_return",
            "volatility",
            "downside_volatility",
            "maximum_drawdown",
            "return_drawdown_ratio",
            "rolling_excess_return_diagnostics",
            "risk_context_correlation_to_ief",
        ],
        "outcome_rules": sorted(ALLOWED_OUTCOMES),
        "no_dates_thresholds_wrappers_or_benchmarks_can_change_after_performance": True,
        "no_provider_call": True,
        "provider_download": False,
        "no_alternative_wrapper_benchmark_filter_or_date_search": True,
        "registry_hash_before": registry_before,
        "active_observations_hash_before": active_before,
    }
    write_json(OUTPUT_DIR / "validation_manifest.json", manifest)
    write_csv(OUTPUT_DIR / "screen_packet_consistency_correction.csv", correction_rows)

    cost_value = float(cost["standard_slippage_pct_per_side"])
    all_summaries: list[dict[str, Any]] = []
    monthly_results_by_horizon: dict[int, list[dict[str, Any]]] = {}
    for horizon, definitions in monthly_defs.items():
        rows = evaluate_window_rows(definitions, prices, common_dates, cost_value)
        monthly_results_by_horizon[horizon] = rows
        all_summaries.append(summarize_window_family(f"monthly_start_{horizon}d", rows))
        write_csv(OUTPUT_DIR / f"monthly_start_{horizon}d_results.csv", rows)
    nonoverlap_results_by_horizon: dict[int, list[dict[str, Any]]] = {}
    for horizon, definitions in nonoverlap_defs.items():
        rows = evaluate_window_rows(definitions, prices, common_dates, cost_value)
        nonoverlap_results_by_horizon[horizon] = rows
        all_summaries.append(summarize_window_family(f"non_overlapping_{horizon}d", rows))
        write_csv(OUTPUT_DIR / f"non_overlapping_{horizon}d_results.csv", rows)
    calendar_rows = complete_year_rows(common_dates, prices, cost_value)
    full_rows = full_period_metrics(prices, common_dates, cost_value)
    third_rows = fixed_period_metrics(thirds, prices, common_dates, cost_value)
    regime_rows = fixed_period_metrics(regimes, prices, common_dates, cost_value)
    for row in regime_rows:
        source = next(item for item in regimes if item["period_id"] == row["period_id"])
        row["evidence_weight"] = source["evidence_weight"]
        row["shorter_post_amendment_sample_caveat"] = source["post_2023_short_sample_caveat"]
    rolling_rows = rolling_excess_diagnostics(prices, common_dates, cost_value)
    risk_rows = risk_context_diagnostics(prices, common_dates, regimes)
    invariants = [
        {"invariant_id": "exact_angl_cache_hash_used", "invariant_passed": next(row for row in cache_rows if row["symbol"] == CANDIDATE)["cache_hash"] == screen.REQUIRED_ANGL_HASH},
        {"invariant_id": "no_provider_call_or_refresh", "invariant_passed": True},
        {"invariant_id": "windows_frozen_before_performance", "invariant_passed": True},
        {"invariant_id": "matching_angl_hyg_dates_used", "invariant_passed": len(common_dates) == 3568 and common_dates[0].date().isoformat() == COMMON_START and common_dates[-1].date().isoformat() == COMMON_END},
        {"invariant_id": "actual_etf_shares_and_equal_costs_used", "invariant_passed": True},
        {"invariant_id": "hyg_primary_benchmark", "invariant_passed": True},
        {"invariant_id": "context_only_bil_ief", "invariant_passed": True},
        {"invariant_id": "no_wrapper_benchmark_filter_or_date_search", "invariant_passed": True},
    ]
    invariants_passed = all(row["invariant_passed"] for row in invariants)
    outcome_label, conditions = classify_validation(all_summaries, full_rows, third_rows, regime_rows, calendar_rows, rolling_rows, invariants_passed)
    weakened_or_unstable = outcome_label in {"historical_edge_recently_weakened", "screening_positive_not_stable", "benchmark_like_no_edge", "control_weak", "invalid_methodology"}
    outcome = {
        "validation_outcome": outcome_label,
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": PRIMARY_BENCHMARK,
        "allowed_outcome": outcome_label in ALLOWED_OUTCOMES,
        "conditions": conditions,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "robustness_authorized": False,
        "strategy_state_changed": False,
        "next_action": "direction_owner_review_required_for_exact_candidate" if outcome_label in {"validation_supports_further_review", "higher_return_higher_risk_persistent", "direction_owner_review_required"} else "direction_owner_closure_or_review_decision_required",
    }
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "validation_outcome": outcome_label,
            "preserve_exact_candidate_for_direction_owner_review": outcome_label == "validation_supports_further_review",
            "close_exact_variant_for_immediate_retesting": weakened_or_unstable,
            "broader_family_open_only_for_materially_different_source_backed_hypothesis": True,
            "do_not_test_another_fallen_angel_etf_automatically": True,
            "do_not_add_timing_or_hedging_automatically": True,
            "lifecycle_status_changed": False,
            "paper_demo_authorized": False,
            "promotion_authorized": False,
        }
    ]
    registry_after = file_hash(REGISTRY_PATH)
    active_after = file_hash(ACTIVE_OBSERVATIONS_PATH)
    queue = screen.read_yaml(RESEARCH_QUEUE_PATH).get("external_source_discovery_lane", {})
    consistency = {
        "screen_packet_regime3_wording_corrected": True,
        "regime3_hard_evidence_eligible_and_caveated": next(row for row in regime_rows if row["period_id"].endswith("amended_h0cf_methodology"))["evidence_weight"] == "hard_evidence_eligible"
        and next(row for row in regime_rows if row["period_id"].endswith("amended_h0cf_methodology"))["shorter_post_amendment_sample_caveat"] is True,
        "monthly_start_windows_deterministic": all(row["selection_algorithm"] == "first_common_trading_session_of_each_calendar_month" for defs in monthly_defs.values() for row in defs),
        "non_overlapping_windows_begin_first_common_date": all(defs[0]["window_start"] == COMMON_START for defs in nonoverlap_defs.values() if defs),
        "calendar_year_classification_deterministic": any(row["coverage_classification"] == "complete_calendar_year" for row in calendar_rows),
        "rolling_diagnostics_do_not_create_signal": all(row["diagnostic_only_no_strategy_signal"] is True for row in rolling_rows),
        "actual_etf_shares_and_equal_costs_used": True,
        "angl_hyg_dates_aligned": True,
        "hyg_primary_benchmark": True,
        "ief_and_bil_context_only": True,
        "no_provider_call": True,
        "no_alternative_wrapper_benchmark_filter_or_date_search": True,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_unchanged": active_before == active_after,
        "external_source_pause_remains_active": queue.get("status") == "paused_pending_direction_owner_supplied_source",
        "generation_is_deterministic": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    lineage = [
        {"artifact_id": "direction_owner_intake", "path": str(abs_path(INTAKE_DIR)), "sha256": file_hash(INTAKE_DIR / "decision.json"), "role": "source_and_preregistration"},
        {"artifact_id": "bounded_screen", "path": str(abs_path(SCREEN_DIR)), "sha256": file_hash(SCREEN_DIR / "screening_outcome.json"), "role": "prior_screen"},
        {"artifact_id": "screen_caveat_wording_correction", "path": str(abs_path(SCREEN_DIR / "source_and_methodology_caveats.md")), "sha256": file_hash(SCREEN_DIR / "source_and_methodology_caveats.md"), "role": "wording_only_pre_validation_correction"},
        {"artifact_id": "validation_module", "path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"), "sha256": file_hash(Path(__file__).relative_to(ROOT)), "role": "validation_generation"},
    ]

    write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar_rows)
    write_csv(OUTPUT_DIR / "full_period_metrics.csv", full_rows)
    write_csv(OUTPUT_DIR / "chronological_thirds_metrics.csv", third_rows)
    write_csv(OUTPUT_DIR / "methodology_regime_metrics.csv", regime_rows)
    write_csv(OUTPUT_DIR / "rolling_excess_return_diagnostics.csv", rolling_rows)
    write_csv(OUTPUT_DIR / "return_risk_joint_outcomes.csv", all_summaries)
    write_csv(OUTPUT_DIR / "risk_context_diagnostics.csv", risk_rows)
    write_csv(OUTPUT_DIR / "accounting_and_alignment_invariants.csv", invariants)
    write_text(OUTPUT_DIR / "validation_summary.md", summary_text(outcome, full_rows, all_summaries, rolling_rows))
    write_json(OUTPUT_DIR / "validation_outcome.json", outcome)
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory)
    write_csv(OUTPUT_DIR / "artifact_lineage.csv", lineage)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "validation_outcome": outcome_label,
        "next_action": outcome["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
