from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import quantpedia_asset_class_momentum_adaptive_research_v1 as base


ROOT = base.ROOT
PARENT_ID = base.STRATEGY_ID
VARIANT_ID = "faber_global_asset_class_momentum_top3_composite_1_3_6_9_12m_etf_translation_v1"
FAMILY_ID = "cross_asset_relative_momentum_rotation"
RUN_ID = "faber_composite_top3_source_rule_completion_v1"
ADAPTATION_LABEL = "source_rule_completion"
METHODOLOGY_CORRECTION_ID = "faber_composite_cost_stress_command_log_correction_v1"
METHODOLOGY_CORRECTION_LABEL = "methodology_correction"
OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_implementation"
    / PARENT_ID
    / "source_rule_completion_composite_v1"
    / "latest"
)
ARCHIVE_FILE = OUTPUT_DIR.parent / "prior_bad_hashes_v1.json"
PRIOR_DIR = base.OUTPUT_DIR
UNIVERSE = base.BASELINE_UNIVERSE
HORIZONS = (1, 3, 6, 9, 12)
TOP_N = 3
NEXT_ACTION = "direction_owner_review_faber_composite_top3_source_rule_completion_v1_corrected"

PRIMARY_BASELINE_FILES = (
    "baseline_specification.json",
    "baseline_full_sample_results.json",
    "baseline_target_weights.csv",
    "baseline_rankings.csv",
    "baseline_daily_path_and_weights.csv",
    "variant_results.csv",
    "research_outcome.json",
    "consistency_check.json",
)

REQUIRED_CSV_COLUMNS: dict[str, set[str]] = {
    "monthly_component_returns.csv": {"variant_id", "signal_month", "signal_date", "symbol", "composite_momentum", "return_1m", "return_3m", "return_6m", "return_9m", "return_12m", "arithmetic_mean_verified"},
    "monthly_composite_scores.csv": {"variant_id", "signal_month", "signal_date", *UNIVERSE},
    "monthly_rankings.csv": {"variant_id", "signal_month", "signal_date", "rank_order", "selected", "tie_breaker"},
    "monthly_target_weights.csv": {"variant_id", "signal_month", "execution_date", "selected_count", "explicit_zero_targets", "weight_sum", *UNIVERSE},
    "monthly_execution_dates.csv": {"variant_id", "signal_month", "signal_date", "execution_date", "signal_precedes_execution", "same_close_execution", "execution_delay_sessions"},
    "trades.csv": {"variant_id", "execution_date", "turnover", "cost_return"},
    "calendar_year_results.csv": {"variant_id", "calendar_year", "candidate_return", "benchmark_return", "excess_return"},
    "subperiod_results.csv": {"variant_id", "subperiod", "candidate_total_return", "benchmark_total_return", "excess_total_return"},
    "rolling_results.csv": {"variant_id", "window_sessions", "window_end", "candidate_return", "benchmark_return", "excess_return"},
    "transaction_cost_stress.csv": {"variant_id", "cost_bps_per_turnover_unit", "cost_rate", "total_return", "cagr", "max_drawdown", "transaction_cost_return_sum", "total_turnover", "start_date", "end_date", "observations", "source_path"},
    "asset_selection_frequency.csv": {"variant_id", "instrument", "selection_frequency", "rank_one_frequency"},
    "asset_return_attribution.csv": {"variant_id", "instrument", "return_contribution_sum", "absolute_contribution_share"},
    "turnover_attribution.csv": {"variant_id", "instrument", "absolute_target_change_sum", "turnover_contribution_proxy", "turnover_contribution_share"},
    "baseline_relative_calendar_years.csv": {"calendar_year", "candidate_return", "baseline_12m_return", "excess_return"},
    "baseline_relative_rolling_results.csv": {"window_sessions", "window_end", "candidate_return", "baseline_12m_return", "excess_return"},
    "signal_and_membership_agreement.csv": {"signal_month", "execution_date", "new_rank_order", "baseline_12m_rank_order", "membership_agreement", "shared_selected_count"},
    "methodology_and_exposure_invariants.csv": {"variant_id", "invariant", "passed", "observed", "expected"},
    "exact_configuration_trial_ledger.csv": {"variant_id", "lookback_months", "top_n", "universe", "calculated"},
    "family_trial_ledger.csv": {"variant_id", "run_id", "role", "changed_dimension"},
    "command_validation_log.csv": {"command", "return_code", "status", "notes"},
}

CORE_RESULT_FILES = (
    "full_sample_results.json",
    "calendar_year_results.csv",
    "rolling_results.csv",
    "comparison_with_12m_baseline.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def sha256_path(path: Path) -> str:
    full = abs_path(path)
    if not full.exists():
        return "missing"
    digest = hashlib.sha256()
    with full.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(abs_path(path).read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with abs_path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def list_file_hashes(directory: Path) -> list[dict[str, Any]]:
    full = abs_path(directory)
    if not full.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in full.iterdir() if item.is_file()):
        rows.append(
            {
                "file": path.name,
                "relative_path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "sha256": sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


def capture_prior_incorrect_reference() -> dict[str, Any]:
    archive_full = abs_path(ARCHIVE_FILE)
    if archive_full.exists():
        return read_json(ARCHIVE_FILE)

    output_full = abs_path(OUTPUT_DIR)
    full_sample_before: dict[str, Any] = {}
    comparison_before: dict[str, Any] = {}
    stress_rows_before: list[dict[str, str]] = []
    if (output_full / "full_sample_results.json").exists():
        full_sample_before = read_json(OUTPUT_DIR / "full_sample_results.json")
    if (output_full / "comparison_with_12m_baseline.json").exists():
        comparison_before = read_json(OUTPUT_DIR / "comparison_with_12m_baseline.json")
    if (output_full / "transaction_cost_stress.csv").exists():
        stress_rows_before = read_csv_rows(OUTPUT_DIR / "transaction_cost_stress.csv")

    payload = {
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "correction_label": METHODOLOGY_CORRECTION_LABEL,
        "prior_packet_path": str(OUTPUT_DIR),
        "prior_packet_reference_type": "hash_reference_to_pre_correction_latest_packet",
        "prior_files": list_file_hashes(OUTPUT_DIR),
        "prior_full_sample_results": full_sample_before,
        "prior_comparison_with_12m_baseline": comparison_before,
        "prior_transaction_cost_stress_rows": stress_rows_before,
        "known_prior_defects": [
            "transaction_cost_stress.csv was generated from parent 12-month baseline signals while using the composite variant ID",
            "command_validation_log.csv was hand-edited into malformed CSV because notes with commas were not quoted",
        ],
    }
    write_json(ARCHIVE_FILE, payload)
    return payload


def clean_output_dir() -> None:
    output = abs_path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def hash_prior_baseline_files() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for name in PRIMARY_BASELINE_FILES:
        rel = PRIOR_DIR / name
        rows[name] = {
            "file": name,
            "path": str(rel),
            "exists": abs_path(rel).exists(),
            "sha256": sha256_path(rel),
        }
    return rows


def variant_spec() -> base.VariantSpec:
    return base.VariantSpec(
        VARIANT_ID,
        PARENT_ID,
        ADAPTATION_LABEL,
        UNIVERSE,
        12,
        TOP_N,
        1,
        "static_equal_weight_same_five_etfs_monthly",
        ADAPTATION_LABEL,
        "Modern ETF translation of the Faber global-asset-class Top-3 composite 1/3/6/9/12-month relative-strength signal.",
    )


def write_preregistration() -> None:
    write_json(
        OUTPUT_DIR / "experiment_preregistration.json",
        {
            "variant_id": VARIANT_ID,
            "parent_id": PARENT_ID,
            "family_id": FAMILY_ID,
            "adaptation_label": ADAPTATION_LABEL,
            "created_before_result_calculation": True,
            "formula": "arithmetic_mean(return_1m, return_3m, return_6m, return_9m, return_12m)",
            "horizons_months": list(HORIZONS),
            "universe": list(UNIVERSE),
            "selection": "rank higher composite momentum first; ticker ascending final tie-breaker; hold Top 3",
            "targets": "selected ETFs receive one-third; unselected ETFs receive explicit zero",
            "timing": "signal on completed common calendar month-end; execute next common session close",
            "costs": f"same canonical turnover cost as parent baseline: {base.SLIPPAGE}",
            "benchmark": "static_equal_weight_same_five_etfs_monthly",
            "required_comparisons": [PARENT_ID, "static_equal_weight_same_five_etfs_monthly"],
            "prohibited_alternatives": [
                "DBC_or_other_wrapper_substitution",
                "alternate_horizons",
                "horizon_weighting",
                "score_normalization",
                "absolute_momentum",
                "moving_average_filter",
                "cash_rule",
                "parameter_search",
            ],
            "reason_for_experiment": "Source-lineage completion: Faber paper separately reports a composite 1/3/6/9/12-month relative-strength model distinct from Quantpedia's public 12-month ETF rule.",
        },
    )


def build_composite_signals(
    spec: base.VariantSpec,
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    closes, month_dates = base.month_end_frame(prices, spec.universe)
    common_daily = pd.DatetimeIndex(prices[list(spec.universe)].dropna().index)
    target_by_execution: dict[pd.Timestamp, dict[str, float]] = {}
    component_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []

    for pos in range(max(HORIZONS), len(closes.index)):
        period = closes.index[pos]
        current = closes.loc[period, list(spec.universe)].astype(float)
        returns_by_symbol: dict[str, dict[int, float]] = {}
        scores: dict[str, float] = {}
        valid = True
        for symbol in spec.universe:
            returns_by_symbol[symbol] = {}
            for horizon in HORIZONS:
                lag = closes.loc[closes.index[pos - horizon], symbol]
                if pd.isna(current[symbol]) or pd.isna(lag) or float(lag) <= 0:
                    valid = False
                    break
                returns_by_symbol[symbol][horizon] = float(current[symbol] / lag - 1.0)
            if not valid:
                break
            scores[symbol] = float(sum(returns_by_symbol[symbol][horizon] for horizon in HORIZONS) / len(HORIZONS))
        if not valid:
            continue
        ranked = base.rank_symbols(scores)
        selected = ranked[: spec.top_n]
        target = {symbol: 0.0 for symbol in spec.universe}
        for symbol in selected:
            target[symbol] = 1.0 / spec.top_n
        signal_date = month_dates[pd.Period(period, freq="M")]
        candidates = common_daily[common_daily > signal_date]
        if len(candidates) < spec.execution_delay_sessions:
            continue
        execution_date = pd.Timestamp(candidates[spec.execution_delay_sessions - 1])
        target_by_execution[execution_date] = target

        for symbol in spec.universe:
            component = {
                "variant_id": spec.variant_id,
                "signal_month": str(period),
                "signal_date": str(signal_date.date()),
                "symbol": symbol,
                "composite_momentum": scores[symbol],
                "arithmetic_mean_verified": abs(
                    scores[symbol] - sum(returns_by_symbol[symbol][h] for h in HORIZONS) / len(HORIZONS)
                )
                <= base.TOL,
            }
            for horizon in HORIZONS:
                component[f"return_{horizon}m"] = returns_by_symbol[symbol][horizon]
                component[f"horizon_{horizon}m_weight"] = 1.0 / len(HORIZONS)
            component_rows.append(component)

        score_row = {"variant_id": spec.variant_id, "signal_month": str(period), "signal_date": str(signal_date.date())}
        rank_row = {
            "variant_id": spec.variant_id,
            "signal_month": str(period),
            "signal_date": str(signal_date.date()),
            "rank_order": "|".join(ranked),
            "selected": "|".join(selected),
            "tie_breaker": "ticker_symbol_ascending",
        }
        target_row = {
            "variant_id": spec.variant_id,
            "signal_month": str(period),
            "execution_date": str(execution_date.date()),
            "selected_count": len(selected),
            "explicit_zero_targets": True,
            "weight_sum": sum(target.values()),
        }
        for symbol in spec.universe:
            score_row[symbol] = scores[symbol]
            rank_row[f"{symbol}_rank"] = ranked.index(symbol) + 1
            target_row[symbol] = target[symbol]
        score_rows.append(score_row)
        rank_rows.append(rank_row)
        target_rows.append(target_row)
        execution_rows.append(
            {
                "variant_id": spec.variant_id,
                "signal_month": str(period),
                "signal_date": str(signal_date.date()),
                "execution_date": str(execution_date.date()),
                "signal_precedes_execution": signal_date < execution_date,
                "same_close_execution": signal_date == execution_date,
                "execution_delay_sessions": spec.execution_delay_sessions,
            }
        )

    targets = pd.DataFrame.from_dict(target_by_execution, orient="index").sort_index()
    targets = targets.reindex(columns=list(spec.universe), fill_value=0.0).fillna(0.0)
    return targets, component_rows, score_rows, rank_rows, target_rows, execution_rows


def complete_year_relative(candidate: pd.Series, baseline: pd.Series) -> list[dict[str, Any]]:
    aligned = pd.concat([candidate.rename("candidate"), baseline.rename("baseline")], axis=1).dropna()
    rows: list[dict[str, Any]] = []
    for year, frame in aligned.groupby(aligned.index.year):
        if frame.index.min().month != 1 or frame.index.max().month != 12:
            continue
        candidate_return = float((1.0 + frame["candidate"]).prod() - 1.0)
        baseline_return = float((1.0 + frame["baseline"]).prod() - 1.0)
        rows.append(
            {
                "calendar_year": int(year),
                "candidate_return": candidate_return,
                "baseline_12m_return": baseline_return,
                "excess_return": candidate_return - baseline_return,
                "candidate_outperformed_12m_baseline": candidate_return > baseline_return,
            }
        )
    return rows


def rolling_relative(candidate: pd.Series, baseline: pd.Series) -> list[dict[str, Any]]:
    aligned = pd.concat([candidate.rename("candidate"), baseline.rename("baseline")], axis=1).dropna()
    rows: list[dict[str, Any]] = []
    for window in (180, 252, 756):
        c = (1.0 + aligned["candidate"]).rolling(window).apply(np.prod, raw=True) - 1.0
        b = (1.0 + aligned["baseline"]).rolling(window).apply(np.prod, raw=True) - 1.0
        for date in aligned.index[window - 1 :]:
            rows.append(
                {
                    "window_sessions": window,
                    "window_end": str(pd.Timestamp(date).date()),
                    "candidate_return": float(c.loc[date]),
                    "baseline_12m_return": float(b.loc[date]),
                    "excess_return": float(c.loc[date] - b.loc[date]),
                    "candidate_outperformed_12m_baseline": bool(c.loc[date] > b.loc[date]),
                }
            )
    return rows


def baseline_daily_returns() -> pd.Series:
    rows = read_csv_rows(PRIOR_DIR / "baseline_daily_path_and_weights.csv")
    return pd.Series(
        [float(row["daily_return"]) for row in rows],
        index=pd.to_datetime([row["date"] for row in rows]),
        name=PARENT_ID,
    )


def summarize_relative_rolling(rows: list[dict[str, Any]], window: int) -> dict[str, float]:
    selected = [row for row in rows if int(row["window_sessions"]) == window]
    excess = [float(row["excess_return"]) for row in selected]
    if not excess:
        return {"positive_pct": float("nan"), "median_excess": float("nan")}
    return {
        "positive_pct": float(np.mean([value > 0 for value in excess])),
        "median_excess": float(np.median(excess)),
    }


def signal_membership_agreement(new_rank_rows: list[dict[str, Any]], new_target_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prior_rank = {row["signal_month"]: row for row in read_csv_rows(PRIOR_DIR / "baseline_rankings.csv")}
    prior_targets = {row["execution_date"]: row for row in read_csv_rows(PRIOR_DIR / "baseline_target_weights.csv")}
    target_by_execution = {row["execution_date"]: row for row in new_target_rows}
    rows: list[dict[str, Any]] = []
    for row in new_rank_rows:
        signal_month = row["signal_month"]
        old = prior_rank.get(signal_month)
        if old is None:
            continue
        new_selected = set(str(row["selected"]).split("|"))
        old_selected = set(str(old["selected"]).split("|"))
        execution_date = next((target["execution_date"] for target in new_target_rows if target["signal_month"] == signal_month), "")
        new_target = target_by_execution.get(execution_date, {})
        old_target = prior_targets.get(execution_date, {})
        membership_equal = new_selected == old_selected
        target_equal = all(
            abs(float(new_target.get(symbol, 0.0)) - float(old_target.get(symbol, 0.0))) <= base.TOL
            for symbol in UNIVERSE
        )
        rows.append(
            {
                "signal_month": signal_month,
                "execution_date": execution_date,
                "new_rank_order": row["rank_order"],
                "baseline_12m_rank_order": old["rank_order"],
                "exact_rank_order_agreement": row["rank_order"] == old["rank_order"],
                "membership_agreement": membership_equal,
                "target_weight_agreement": target_equal,
                "shared_selected_count": len(new_selected & old_selected),
            }
        )
    return rows


def turnover_attribution(path: base.ReturnPath) -> list[dict[str, Any]]:
    diffs = path.execution_targets.diff().abs().fillna(path.execution_targets.abs())
    totals = diffs.sum()
    total_turnover_proxy = float(totals.sum() / 2.0)
    return [
        {
            "variant_id": path.variant_id,
            "instrument": symbol,
            "absolute_target_change_sum": float(totals[symbol]),
            "turnover_contribution_proxy": float(totals[symbol] / 2.0),
            "turnover_contribution_share": float((totals[symbol] / 2.0) / total_turnover_proxy) if total_turnover_proxy > 0 else 0.0,
        }
        for symbol in path.universe
    ]


def validate_targets_match_design(targets: pd.DataFrame, target_rows: list[dict[str, Any]]) -> None:
    expected_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    for row in target_rows:
        expected_by_date[pd.Timestamp(str(row["execution_date"]))] = {symbol: float(row[symbol]) for symbol in UNIVERSE}
    missing_dates = sorted(set(expected_by_date) - set(pd.DatetimeIndex(targets.index)))
    extra_dates = sorted(set(pd.DatetimeIndex(targets.index)) - set(expected_by_date))
    mismatches: list[str] = []
    for date, expected in expected_by_date.items():
        if date not in targets.index:
            continue
        for symbol, expected_value in expected.items():
            actual = float(targets.loc[date, symbol])
            if abs(actual - expected_value) > base.TOL:
                mismatches.append(f"{date.date()}:{symbol}:{actual:.12g}!={expected_value:.12g}")
                if len(mismatches) >= 5:
                    break
        if len(mismatches) >= 5:
            break
    if missing_dates or extra_dates or mismatches:
        raise ValueError(
            "cost stress targets do not match the composite target design "
            f"(missing_dates={len(missing_dates)}, extra_dates={len(extra_dates)}, mismatches={mismatches})"
        )


def composite_cost_stress_rows(
    spec: base.VariantSpec,
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    signal_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    validate_targets_match_design(targets, target_rows)
    rows: list[dict[str, Any]] = []
    for cost_bps, slip in [(0, 0.0), (5, 0.0005), (10, 0.0010), (25, 0.0025)]:
        path = base.simulate_path(spec, prices, targets, signal_rows, slip)
        metrics = base.metrics_from_returns(path.daily_returns, path.turnover, path.costs)
        expected_cost_sum = metrics["total_turnover"] * slip
        rows.append(
            {
                "variant_id": spec.variant_id,
                "cost_bps_per_turnover_unit": cost_bps,
                "cost_rate": slip,
                "total_return": metrics["total_return"],
                "cagr": metrics["cagr"],
                "max_drawdown": metrics["max_drawdown"],
                "transaction_cost_return_sum": metrics["transaction_cost_return_sum"],
                "total_turnover": metrics["total_turnover"],
                "expected_transaction_cost_return_sum": expected_cost_sum,
                "transaction_cost_sum_difference": metrics["transaction_cost_return_sum"] - expected_cost_sum,
                "start_date": metrics["start_date"],
                "end_date": metrics["end_date"],
                "observations": metrics["observations"],
                "source_path": "composite_targets_and_rankings",
            }
        )
    return rows


def values_close(left: Any, right: Any, tolerance: float = base.TOL) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return str(left) == str(right)


def validate_cost_stress_rows(
    stress_rows: list[dict[str, Any]],
    full_results: dict[str, Any],
    parent_results: dict[str, Any],
) -> dict[str, Any]:
    row_by_bps = {int(row["cost_bps_per_turnover_unit"]): row for row in stress_rows}
    canonical = row_by_bps.get(5, {})
    required_levels_present = sorted(row_by_bps) == [0, 5, 10, 25]
    all_variant_ids_candidate = all(row.get("variant_id") == VARIANT_ID for row in stress_rows)
    canonical_matches_full = bool(canonical) and all(
        values_close(canonical.get(stress_key), full_results.get(full_key))
        for stress_key, full_key in [
            ("cagr", "cagr"),
            ("total_return", "total_return"),
            ("max_drawdown", "max_drawdown"),
            ("transaction_cost_return_sum", "transaction_cost_return_sum"),
            ("observations", "observations"),
            ("start_date", "start_date"),
            ("end_date", "end_date"),
            ("variant_id", "variant_id"),
        ]
    )
    canonical_matches_parent_in_error = bool(canonical) and all(
        values_close(canonical.get(stress_key), parent_results.get(parent_key))
        for stress_key, parent_key in [
            ("cagr", "cagr"),
            ("total_return", "total_return"),
            ("max_drawdown", "max_drawdown"),
            ("transaction_cost_return_sum", "transaction_cost_return_sum"),
        ]
    )
    sorted_rows = [row_by_bps[level] for level in sorted(row_by_bps)]
    cost_sums = [float(row["transaction_cost_return_sum"]) for row in sorted_rows]
    total_returns = [float(row["total_return"]) for row in sorted_rows]
    cagrs = [float(row["cagr"]) for row in sorted_rows]
    cost_sum_formula_checks: list[bool] = []
    for row in stress_rows:
        try:
            cost_sum_formula_checks.append(
                abs(float(row["transaction_cost_return_sum"]) - float(row["total_turnover"]) * float(row["cost_rate"])) <= 1e-10
            )
        except (KeyError, TypeError, ValueError):
            cost_sum_formula_checks.append(False)
    monotonic_checks_passed = (
        all(cost_sums[idx] <= cost_sums[idx + 1] + base.TOL for idx in range(len(cost_sums) - 1))
        and all(total_returns[idx] + base.TOL >= total_returns[idx + 1] for idx in range(len(total_returns) - 1))
        and all(cagrs[idx] + base.TOL >= cagrs[idx + 1] for idx in range(len(cagrs) - 1))
    )
    source_path_candidate = all(row.get("source_path") == "composite_targets_and_rankings" for row in stress_rows)
    return {
        "required_cost_levels_present": required_levels_present,
        "transaction_cost_stress_uses_candidate_path": all_variant_ids_candidate and source_path_candidate,
        "all_transaction_cost_stress_rows_have_candidate_variant_id": all_variant_ids_candidate,
        "canonical_cost_row_matches_full_sample": canonical_matches_full,
        "canonical_cost_row_matches_parent_baseline_in_error": canonical_matches_parent_in_error,
        "cost_sum_formula_checks_passed": all(cost_sum_formula_checks),
        "cost_stress_monotonic_checks_passed": monotonic_checks_passed,
    }


def csv_parse_report(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_parse = True
    all_columns = True
    command_log_parseable = False
    for name, expected in REQUIRED_CSV_COLUMNS.items():
        path = abs_path(output_dir / name)
        csv_module_parseable = False
        pandas_parseable = False
        malformed_row = False
        columns: list[str] = []
        row_count = 0
        missing_columns: list[str] = []
        error = ""
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns = list(reader.fieldnames or [])
                for row in reader:
                    row_count += 1
                    if None in row:
                        malformed_row = True
                csv_module_parseable = bool(columns) and not malformed_row
                missing_columns = sorted(expected - set(columns))
                all_columns = all_columns and not missing_columns
        except Exception as exc:  # pragma: no cover - defensive report path
            error = f"csv:{type(exc).__name__}:{exc}"
        try:
            frame = pd.read_csv(path)
            pandas_parseable = not frame.empty or bool(frame.columns.tolist())
        except Exception as exc:  # pragma: no cover - defensive report path
            pandas_parseable = False
            error = (error + "; " if error else "") + f"pandas:{type(exc).__name__}:{exc}"
        parseable = csv_module_parseable and pandas_parseable and not missing_columns
        all_parse = all_parse and parseable
        if name == "command_validation_log.csv":
            command_log_parseable = parseable
        rows.append(
            {
                "file": name,
                "csv_module_parseable": csv_module_parseable,
                "pandas_parseable": pandas_parseable,
                "malformed_row": malformed_row,
                "row_count": row_count,
                "missing_columns": "|".join(missing_columns),
                "parseable_with_expected_columns": parseable,
                "error": error,
            }
        )
    return {
        "all_required_csv_files_parse": all_parse,
        "all_required_csv_files_have_expected_columns": all_columns,
        "command_validation_log_parseable": command_log_parseable,
        "csv_parse_rows": rows,
    }


def trial_ledger_checks() -> dict[str, Any]:
    exact = read_csv_rows(OUTPUT_DIR / "exact_configuration_trial_ledger.csv")
    family = read_csv_rows(OUTPUT_DIR / "family_trial_ledger.csv")
    exact_count = sum(1 for row in exact if row.get("variant_id") == VARIANT_ID)
    family_count = sum(1 for row in family if row.get("variant_id") == VARIANT_ID)
    return {
        "exact_trial_rows_for_variant": exact_count,
        "family_trial_rows_for_variant": family_count,
        "no_trial_row_duplicated": exact_count == 1 and family_count == 1,
    }


def write_command_validation_log(rows: list[dict[str, Any]]) -> None:
    write_csv(
        OUTPUT_DIR / "command_validation_log.csv",
        rows,
        ["command", "return_code", "status", "notes"],
    )


def corrected_artifact_hash_payload() -> dict[str, Any]:
    corrected_files = [
        row
        for row in list_file_hashes(OUTPUT_DIR)
        if row["file"] != "corrected_artifact_hashes_after.json"
    ]
    return {
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "correction_label": METHODOLOGY_CORRECTION_LABEL,
        "corrected_packet_path": str(OUTPUT_DIR),
        "corrected_files": corrected_files,
    }


def write_corrected_artifact_hashes_after() -> None:
    write_json(OUTPUT_DIR / "corrected_artifact_hashes_after.json", corrected_artifact_hash_payload())


def hash_core_files_from_payload(prior_reference: dict[str, Any]) -> dict[str, str]:
    return {
        row["file"]: row["sha256"]
        for row in prior_reference.get("prior_files", [])
        if row.get("file") in CORE_RESULT_FILES
    }


def core_result_before_after_comparison(
    prior_reference: dict[str, Any],
    full_results: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    before_full = prior_reference.get("prior_full_sample_results", {})
    before_comparison = prior_reference.get("prior_comparison_with_12m_baseline", {})
    before_hashes = hash_core_files_from_payload(prior_reference)
    after_hashes = {name: sha256_path(OUTPUT_DIR / name) for name in CORE_RESULT_FILES}
    fields = [
        ("full_sample_cagr", before_full.get("cagr"), full_results.get("cagr")),
        ("full_sample_total_return", before_full.get("total_return"), full_results.get("total_return")),
        ("maximum_drawdown", before_full.get("max_drawdown"), full_results.get("max_drawdown")),
        ("total_turnover", before_full.get("total_turnover"), full_results.get("total_turnover")),
        ("canonical_transaction_costs", before_full.get("transaction_cost_return_sum"), full_results.get("transaction_cost_return_sum")),
        (
            "comparison_cagr_difference_vs_12m_baseline",
            before_comparison.get("cagr_difference_vs_12m_baseline"),
            comparison.get("cagr_difference_vs_12m_baseline"),
        ),
        (
            "comparison_total_return_difference_vs_12m_baseline",
            before_comparison.get("total_return_difference_vs_12m_baseline"),
            comparison.get("total_return_difference_vs_12m_baseline"),
        ),
    ]
    field_rows = [
        {
            "field": field,
            "before": before,
            "after": after,
            "changed": not values_close(before, after),
        }
        for field, before, after in fields
    ]
    artifact_rows = [
        {
            "file": name,
            "hash_before": before_hashes.get(name, ""),
            "hash_after": after_hashes.get(name, ""),
            "changed": before_hashes.get(name, "") != after_hashes.get(name, ""),
        }
        for name in CORE_RESULT_FILES
    ]
    return {
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "core_composite_backtest_affected": any(row["changed"] for row in field_rows if row["field"].startswith("full_sample") or row["field"] in {"maximum_drawdown", "total_turnover", "canonical_transaction_costs"}),
        "baseline_comparison_affected": any(row["changed"] for row in field_rows if row["field"].startswith("comparison_")),
        "field_comparisons": field_rows,
        "artifact_hash_comparisons": artifact_rows,
        "defect_isolated_to_cost_stress_and_command_log": not any(row["changed"] for row in field_rows),
    }


def methodology_correction_report(core_comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "correction_label": METHODOLOGY_CORRECTION_LABEL,
        "variant_id": VARIANT_ID,
        "root_cause": "transaction_cost_stress.csv called quantpedia_asset_class_momentum_adaptive_research_v1.cost_stress_rows, whose implementation rebuilds signals with the parent module build_signals function. For this composite variant that produced the preserved 12-month baseline path while stamping the composite variant ID onto the stress rows.",
        "affected_files": [
            "transaction_cost_stress.csv",
            "command_validation_log.csv",
            "consistency_check.json",
        ],
        "core_composite_backtest_was_affected": core_comparison["core_composite_backtest_affected"],
        "baseline_comparison_was_affected": core_comparison["baseline_comparison_affected"],
        "trial_ledgers_were_affected": False,
        "exact_correction_performed": "Replaced parent cost_stress_rows call with composite_cost_stress_rows, which validates and simulates the already-built composite targets and rankings at 0, 5, 10, and 25 bps. Regenerated command_validation_log.csv through csv.DictWriter via the repository write_csv helper.",
        "tests_added_to_prevent_recurrence": [
            "baseline daily/target path is rejected by composite cost stress generator",
            "canonical 5-bps stress row must match composite full-sample result",
            "canonical 5-bps stress row must not match parent baseline result",
            "all stress rows must use the composite variant ID and composite target source path",
            "malformed CSV artifacts force consistency failure",
        ],
        "remaining_limitations": [
            "This is still an ETF translation and diagnostic evidence packet; it is not a promotion, paper/demo, or source-paper replication decision."
        ],
    }


def consistency_flags_pass(consistency: dict[str, Any]) -> bool:
    return (
        consistency["prior_baseline_byte_identical"]
        and consistency["only_one_new_variant_calculated"]
        and consistency["universe_exact"]
        and consistency["horizons_exact"]
        and consistency["selected_count_all_rows"]
        and consistency["explicit_zero_targets"]
        and consistency["same_close_execution_count"] == 0
        and consistency["transaction_cost_matches_baseline"]
        and not consistency["sealed_holdout_created"]
        and not consistency["provider_download"]
        and not consistency["paper_demo_activation"]
        and consistency["registry_unchanged"]
        and consistency["active_observations_unchanged"]
        and not consistency["broker_or_live_path"]
        and consistency["all_required_csv_files_parse"]
        and consistency["all_required_csv_files_have_expected_columns"]
        and consistency["command_validation_log_parseable"]
        and consistency["transaction_cost_stress_uses_candidate_path"]
        and consistency["all_transaction_cost_stress_rows_have_candidate_variant_id"]
        and consistency["canonical_cost_row_matches_full_sample"]
        and not consistency["canonical_cost_row_matches_parent_baseline_in_error"]
        and consistency["cost_sum_formula_checks_passed"]
        and consistency["cost_stress_monotonic_checks_passed"]
        and consistency["no_trial_row_duplicated"]
    )


def build_consistency_payload(
    hash_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    stress_rows: list[dict[str, Any]],
    full_results: dict[str, Any],
    registry_hash_before: str,
    active_observations_hash_before: str,
) -> dict[str, Any]:
    parent_results = read_json(PRIOR_DIR / "baseline_full_sample_results.json")
    csv_report = csv_parse_report(OUTPUT_DIR)
    cost_checks = validate_cost_stress_rows(stress_rows, full_results, parent_results)
    ledger_checks = trial_ledger_checks()
    consistency = {
        "variant_id": VARIANT_ID,
        "parent_id": PARENT_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "methodology_correction_label": METHODOLOGY_CORRECTION_LABEL,
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "prior_baseline_byte_identical": all(row["byte_identical"] for row in hash_rows),
        "only_one_new_variant_calculated": True,
        "universe_exact": list(UNIVERSE) == ["SPY", "EFA", "BND", "VNQ", "GSG"],
        "horizons_exact": list(HORIZONS) == [1, 3, 6, 9, 12],
        "no_absolute_momentum": True,
        "no_moving_average_filter": True,
        "no_cash_rule": True,
        "selected_count_all_rows": all(int(row["selected_count"]) == TOP_N for row in target_rows),
        "explicit_zero_targets": all(row["explicit_zero_targets"] for row in target_rows),
        "same_close_execution_count": sum(1 for row in execution_rows if row["same_close_execution"]),
        "transaction_cost_matches_baseline": base.SLIPPAGE == read_json(PRIOR_DIR / "baseline_specification.json")["transaction_cost"],
        "all_results_in_trial_ledgers": True,
        "sealed_holdout_created": abs_path(OUTPUT_DIR / "sealed_holdout_manifest.json").exists(),
        "provider_download": False,
        "paper_demo_activation": False,
        "promotion": False,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": sha256_path(base.REGISTRY_PATH),
        "registry_unchanged": registry_hash_before == sha256_path(base.REGISTRY_PATH),
        "active_observations_hash_before": active_observations_hash_before,
        "active_observations_hash_after": sha256_path(base.ACTIVE_OBSERVATIONS_PATH),
        "active_observations_unchanged": active_observations_hash_before == sha256_path(base.ACTIVE_OBSERVATIONS_PATH),
        "broker_or_live_path": False,
        "next_action": NEXT_ACTION,
        **csv_report,
        **cost_checks,
        **ledger_checks,
    }
    consistency["consistency_passed"] = consistency_flags_pass(consistency)
    return consistency


def write_source_lineage() -> None:
    write_json(
        OUTPUT_DIR / "source_lineage_clarification.json",
        {
            "lineage_items": [
                {
                    "item": "Quantpedia public 12-month ETF rule",
                    "represented_by": PARENT_ID,
                    "description": "SPY/EFA/BND/VNQ/GSG, strongest 12-month momentum, Top 3, equal weight, monthly rebalance.",
                    "project_role": "existing_baseline_preserved",
                },
                {
                    "item": "Faber 12-month historical-index result",
                    "represented_by": "source_lineage_only",
                    "description": "Original-paper historical-index relative-strength result, not the project ETF baseline.",
                    "project_role": "source_context_only",
                },
                {
                    "item": "Faber composite 1/3/6/9/12-month historical-index result",
                    "represented_by": "source_lineage_only",
                    "description": "Original-paper composite relative-strength model; source-reported performance is not copied into project results.",
                    "project_role": "source_context_only",
                },
                {
                    "item": "Project ETF translation of Faber composite signal",
                    "represented_by": VARIANT_ID,
                    "description": "Modern ETF translation using the same five Quantpedia public ETF wrappers and project execution/accounting conventions.",
                    "project_role": ADAPTATION_LABEL,
                },
            ],
            "rules_are_not_corrections_of_each_other": True,
            "source_reported_performance_copied_into_project_results": False,
        },
    )


def write_data_hash_verification() -> None:
    prior = read_json(PRIOR_DIR / "data_files_and_hashes.json")
    rows: list[dict[str, Any]] = []
    for symbol in UNIVERSE:
        old = prior[symbol]
        path = Path(str(old["path"]))
        current_hash = sha256_path(path)
        rows.append(
            {
                "symbol": symbol,
                "path": str(path),
                "baseline_hash": old["sha256"],
                "current_hash": current_hash,
                "hash_match": old["sha256"] == current_hash,
                "baseline_start": old["start"],
                "baseline_end": old["end"],
            }
        )
    write_json(
        OUTPUT_DIR / "data_hash_verification.json",
        {
            "same_verified_local_data_files_as_parent_baseline": all(row["hash_match"] for row in rows),
            "provider_download": False,
            "rows": rows,
        },
    )


def append_trial_ledgers(path: base.ReturnPath) -> None:
    prior_exact = read_csv_rows(PRIOR_DIR / "exact_configuration_trial_ledger.csv")
    prior_family = read_csv_rows(PRIOR_DIR / "family_trial_ledger.csv")
    exact_new = {
        "calculated": "true",
        "execution_delay_sessions": "1",
        "lookback_months": "composite_1_3_6_9_12",
        "omitted_for_poor_performance": "false",
        "top_n": str(TOP_N),
        "universe": "|".join(UNIVERSE),
        "variant_id": VARIANT_ID,
    }
    family_new = {
        "adaptations_run": "1",
        "baseline_implementations_run": "0",
        "changed_dimension": ADAPTATION_LABEL,
        "result_recorded_even_if_weak": "true",
        "role": ADAPTATION_LABEL,
        "run_id": RUN_ID,
        "strategy_page_considered_count": "0",
        "variant_id": VARIANT_ID,
    }
    write_csv(OUTPUT_DIR / "exact_configuration_trial_ledger.csv", [*prior_exact, exact_new], list(prior_exact[0].keys()))
    write_csv(OUTPUT_DIR / "family_trial_ledger.csv", [*prior_family, family_new], list(prior_family[0].keys()))


def run() -> dict[str, Any]:
    prior_incorrect_reference = capture_prior_incorrect_reference()
    prior_hashes_before = hash_prior_baseline_files()
    registry_hash_before = sha256_path(base.REGISTRY_PATH)
    active_observations_hash_before = sha256_path(base.ACTIVE_OBSERVATIONS_PATH)
    clean_output_dir()
    write_json(OUTPUT_DIR / "incorrect_artifact_hashes_before.json", prior_incorrect_reference)
    write_source_lineage()
    write_preregistration()
    write_json(
        OUTPUT_DIR / "composite_signal_specification.json",
        {
            "variant_id": VARIANT_ID,
            "parent_id": PARENT_ID,
            "universe": list(UNIVERSE),
            "horizons_months": list(HORIZONS),
            "formula": "composite_momentum = arithmetic_mean(return_1m, return_3m, return_6m, return_9m, return_12m)",
            "horizon_weights": {f"{horizon}m": 1.0 / len(HORIZONS) for horizon in HORIZONS},
            "no_absolute_momentum": True,
            "no_moving_average_filter": True,
            "no_cash_rule": True,
        },
    )
    write_data_hash_verification()

    prices = base.load_prices(UNIVERSE)
    spec = variant_spec()
    targets, component_rows, score_rows, rank_rows, target_rows, execution_rows = build_composite_signals(spec, prices)
    path = base.simulate_path(spec, prices, targets, rank_rows, base.SLIPPAGE)
    benchmark_spec = base.VariantSpec(
        f"{VARIANT_ID}__static_equal_weight_benchmark",
        VARIANT_ID,
        "benchmark_control",
        UNIVERSE,
        0,
        len(UNIVERSE),
        1,
        "",
        "benchmark",
        "static equal-weight same universe",
    )
    benchmark = base.simulate_path(benchmark_spec, prices, base.benchmark_targets(UNIVERSE, targets.index), [], base.SLIPPAGE)
    baseline_returns = baseline_daily_returns()

    full_results = base.path_metrics(path, benchmark)
    calendar = base.calendar_year_rows(path, benchmark)
    subperiod = base.subperiod_rows(path, benchmark)
    rolling = base.rolling_rows(path, benchmark)
    stress = composite_cost_stress_rows(spec, prices, targets, rank_rows, target_rows)
    attribution = base.attribution_rows(path)
    turnover_attr = turnover_attribution(path)
    invariants = base.invariant_rows({VARIANT_ID: path})
    relative_years = complete_year_relative(path.daily_returns, baseline_returns)
    relative_rolling = rolling_relative(path.daily_returns, baseline_returns)
    agreement = signal_membership_agreement(rank_rows, target_rows)

    baseline_metrics = read_json(PRIOR_DIR / "baseline_full_sample_results.json")
    rolling_180 = summarize_relative_rolling(relative_rolling, 180)
    rolling_252 = summarize_relative_rolling(relative_rolling, 252)
    top_year_abs_share = 0.0
    if relative_years:
        excess_abs = sorted([abs(float(row["excess_return"])) for row in relative_years], reverse=True)
        total_abs = sum(excess_abs)
        top_year_abs_share = sum(excess_abs[:2]) / total_abs if total_abs else 0.0
    largest_contribution_share = max(float(row["absolute_contribution_share"]) for row in attribution) if attribution else 0.0
    comparison = {
        "variant_id": VARIANT_ID,
        "baseline_12m_variant_id": PARENT_ID,
        "cagr_difference_vs_12m_baseline": full_results["cagr"] - baseline_metrics["cagr"],
        "total_return_difference_vs_12m_baseline": full_results["total_return"] - baseline_metrics["total_return"],
        "maximum_drawdown_difference_vs_12m_baseline": full_results["max_drawdown"] - baseline_metrics["max_drawdown"],
        "volatility_difference_vs_12m_baseline": full_results["annualized_volatility"] - baseline_metrics["annualized_volatility"],
        "return_to_drawdown_difference_vs_12m_baseline": full_results["return_to_max_drawdown"] - baseline_metrics["return_to_max_drawdown"],
        "turnover_difference_vs_12m_baseline": full_results["total_turnover"] - baseline_metrics["total_turnover"],
        "complete_years_outperforming_12m_baseline_pct": float(np.mean([row["candidate_outperformed_12m_baseline"] for row in relative_years])) if relative_years else float("nan"),
        "rolling_180_positive_excess_pct": rolling_180["positive_pct"],
        "rolling_180_median_excess": rolling_180["median_excess"],
        "rolling_252_positive_excess_pct": rolling_252["positive_pct"],
        "rolling_252_median_excess": rolling_252["median_excess"],
        "signal_rank_agreement_pct": float(np.mean([row["exact_rank_order_agreement"] for row in agreement])) if agreement else float("nan"),
        "monthly_membership_agreement_pct": float(np.mean([row["membership_agreement"] for row in agreement])) if agreement else float("nan"),
        "performance_differences_concentrated_in_small_number_of_years": top_year_abs_share >= 0.60,
        "top_two_year_abs_excess_share": top_year_abs_share,
        "performance_differences_concentrated_in_one_etf": largest_contribution_share >= 0.60,
        "largest_abs_contribution_share": largest_contribution_share,
        "diagnostic_only_no_winner_selected": True,
    }

    write_csv(OUTPUT_DIR / "monthly_component_returns.csv", component_rows)
    write_csv(OUTPUT_DIR / "monthly_composite_scores.csv", score_rows)
    write_csv(OUTPUT_DIR / "monthly_rankings.csv", rank_rows)
    write_csv(OUTPUT_DIR / "monthly_target_weights.csv", target_rows)
    write_csv(OUTPUT_DIR / "monthly_execution_dates.csv", execution_rows)
    write_csv(OUTPUT_DIR / "trades.csv", base.trade_rows(path))
    write_json(OUTPUT_DIR / "full_sample_results.json", full_results)
    write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar)
    write_csv(OUTPUT_DIR / "subperiod_results.csv", subperiod)
    write_csv(OUTPUT_DIR / "rolling_results.csv", rolling)
    write_csv(OUTPUT_DIR / "transaction_cost_stress.csv", stress)
    write_csv(OUTPUT_DIR / "asset_selection_frequency.csv", [
        {
            "variant_id": VARIANT_ID,
            "instrument": row["instrument"],
            "selection_frequency": row["selection_frequency"],
            "rank_one_frequency": row["rank_one_frequency"],
        }
        for row in attribution
    ])
    write_csv(OUTPUT_DIR / "asset_return_attribution.csv", attribution)
    write_csv(OUTPUT_DIR / "turnover_attribution.csv", turnover_attr)
    write_json(OUTPUT_DIR / "comparison_with_12m_baseline.json", comparison)
    write_csv(OUTPUT_DIR / "baseline_relative_calendar_years.csv", relative_years)
    write_csv(OUTPUT_DIR / "baseline_relative_rolling_results.csv", relative_rolling)
    write_csv(OUTPUT_DIR / "signal_and_membership_agreement.csv", agreement)
    write_csv(OUTPUT_DIR / "methodology_and_exposure_invariants.csv", invariants)
    append_trial_ledgers(path)
    core_comparison = core_result_before_after_comparison(prior_incorrect_reference, full_results, comparison)
    write_json(OUTPUT_DIR / "core_result_before_after_comparison.json", core_comparison)
    write_json(OUTPUT_DIR / "methodology_correction_report.json", methodology_correction_report(core_comparison))

    prior_hashes_after = hash_prior_baseline_files()
    hash_rows = [
        {
            "file": name,
            "path": prior_hashes_before[name]["path"],
            "hash_before": prior_hashes_before[name]["sha256"],
            "hash_after": prior_hashes_after[name]["sha256"],
            "byte_identical": prior_hashes_before[name]["sha256"] == prior_hashes_after[name]["sha256"],
        }
        for name in PRIMARY_BASELINE_FILES
    ]
    write_json(
        OUTPUT_DIR / "prior_baseline_hash_verification.json",
        {
            "parent_baseline_id": PARENT_ID,
            "hashes_recorded_before_calculation": True,
            "existing_baseline_remains_byte_identical": all(row["byte_identical"] for row in hash_rows),
            "files": hash_rows,
        },
    )
    write_command_validation_log(
        [
            {
                "command": ".venv\\Scripts\\python.exe run_faber_composite_top3_source_rule_completion_v1.py",
                "return_code": "",
                "status": "pending_external_execution",
                "notes": "Dedicated runner command is recorded here; final return code reported after command execution.",
            }
        ],
    )
    write_text(
        OUTPUT_DIR / "experiment_summary.md",
        f"""# Faber Composite Top-3 Source-Rule Completion v1

Variant: `{VARIANT_ID}`

Parent baseline: `{PARENT_ID}`

Adaptation label: `{ADAPTATION_LABEL}`

This exploratory source-supported variant computes the arithmetic mean of 1-, 3-, 6-, 9- and 12-month trailing total returns for SPY, EFA, BND, VNQ and GSG, selects the Top 3 each month, and applies the same project timing, turnover and cost conventions as the preserved 12-month baseline.

The result is diagnostic only. It is not a correction of the Quantpedia 12-month ETF baseline, not an exact replication of Faber's 1973-2009 historical-index result, and not a promotion or paper/demo decision.

Exact next action: `{NEXT_ACTION}`
""",
    )
    consistency = build_consistency_payload(
        hash_rows,
        target_rows,
        execution_rows,
        stress,
        full_results,
        registry_hash_before,
        active_observations_hash_before,
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_corrected_artifact_hashes_after()
    return {
        "run_id": RUN_ID,
        "variant_id": VARIANT_ID,
        "methodology_correction_id": METHODOLOGY_CORRECTION_ID,
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "full_sample_total_return": full_results["total_return"],
        "full_sample_cagr": full_results["cagr"],
        "full_sample_max_drawdown": full_results["max_drawdown"],
        "canonical_cost_row_matches_full_sample": consistency["canonical_cost_row_matches_full_sample"],
        "canonical_cost_row_matches_parent_baseline_in_error": consistency["canonical_cost_row_matches_parent_baseline_in_error"],
        "prior_baseline_byte_identical": consistency["prior_baseline_byte_identical"],
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
