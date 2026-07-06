from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_results_audit import (
    AUDIT_DECISION_PASSED,
)
from strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_run import (
    EXPECTED_VARIANTS,
    FAMILY_ID,
    LANE_ID,
    SOURCE_ID,
    WEIGHT_TOLERANCE,
    design_rows as load_design_rows,
    evaluate_lane,
    metrics,
    result_for_row,
)


SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_run" / "latest"
SOURCE_AUDIT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_larry_connors_rsi2_bounded_bt_results_audit"
    / "latest"
)
SAMPLE_ADEQUACY_DIR = Path("evidence") / "research_recovery" / "backtest_sample_adequacy_report" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_larry_connors_rsi2_bounded_bt_robustness"
    / "latest"
)

STRESS_COSTS = {
    "base": 0.0,
    "stress_10bps": 0.0010,
    "stress_25bps": 0.0025,
}
SUBPERIODS = (
    ("subperiod_2007_2014", "2007-01-03", "2014-12-31"),
    ("subperiod_2015_2020", "2015-01-01", "2020-12-31"),
    ("subperiod_2021_latest", "2021-01-01", None),
)
COST_MODEL = "evaluation_only_cost_per_turnover_unit"

NEXT_ACTION_AUDIT = "audit_public_source_larry_connors_rsi2_robustness_results"
NEXT_ACTION_FIX = "patch_public_source_larry_connors_rsi2_robustness_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

ALLOWED_ROBUSTNESS_LABELS = {
    "connors_rsi2_robustness_primary_survives",
    "connors_rsi2_robustness_cost_sensitive",
    "connors_rsi2_robustness_subperiod_weak",
    "connors_rsi2_robustness_rolling_weak",
    "connors_rsi2_robustness_event_unstable",
    "connors_rsi2_robustness_context_only",
    "connors_rsi2_robustness_control_only",
}

REQUIRED_FILES = (
    "public_source_larry_connors_rsi2_bounded_bt_robustness_manifest.json",
    "public_source_larry_connors_rsi2_bounded_bt_robustness_consistency_check.json",
    "base_vs_cost_stress.csv",
    "subperiod_performance.csv",
    "rolling_window_weakness.csv",
    "rolling_window_weakness_report.md",
    "trade_event_stability_report.csv",
    "trade_event_stability_report.md",
    "control_comparison_report.csv",
    "control_comparison_report.md",
    "exposure_invariant_report.md",
    "timing_sanity_context_report.md",
    "sample_adequacy_carry_forward_note.md",
    "public_source_larry_connors_rsi2_bounded_bt_robustness_summary.md",
    "public_source_larry_connors_rsi2_bounded_bt_robustness_next_action.md",
)

STRESS_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "base_research_label",
    "robustness_label",
    "base_total_return",
    "base_cagr",
    "base_max_drawdown",
    "base_return_drawdown_proxy",
    "base_numeric_criteria_pass",
    "stress_10bps_total_return",
    "stress_10bps_cagr",
    "stress_10bps_max_drawdown",
    "stress_10bps_return_drawdown_proxy",
    "stress_10bps_numeric_criteria_pass",
    "stress_25bps_total_return",
    "stress_25bps_cagr",
    "stress_25bps_max_drawdown",
    "stress_25bps_return_drawdown_proxy",
    "stress_25bps_numeric_criteria_pass",
    "average_turnover_unit",
    "total_turnover_unit",
    "cost_model",
    "subperiod_failure_count",
    "rolling_window_weakness",
    "event_unstable",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

SUBPERIOD_FIELDS = (
    "variant_id",
    "variant_role",
    "period_id",
    "start_date",
    "end_date",
    "total_return",
    "cagr",
    "max_drawdown",
    "return_drawdown_proxy",
    "same_window_return_versus_bil",
    "subperiod_weakness_flag",
)

ROLLING_FIELDS = (
    "variant_id",
    "variant_role",
    "worst_180_day_return",
    "worst_252_day_return",
    "positive_180_day_ratio",
    "positive_252_day_ratio",
    "rolling_window_weakness",
)

EVENT_FIELDS = (
    "variant_id",
    "variant_role",
    "event_reconstruction_status",
    "entry_count",
    "exit_count",
    "event_count",
    "average_holding_days",
    "median_holding_days",
    "win_event_count",
    "loss_event_count",
    "positive_event_rate",
    "average_event_return",
    "worst_event_return",
    "event_unstable",
)

CONTROL_FIELDS = (
    "variant_id",
    "variant_role",
    "total_return",
    "cagr",
    "max_drawdown",
    "return_drawdown_proxy",
    "total_return_delta_vs_bil",
    "total_return_delta_vs_spy_buy_hold",
    "total_return_delta_vs_spy200d",
    "max_drawdown_delta_vs_spy_buy_hold",
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


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def equity_from_returns(daily: pd.Series) -> pd.Series:
    return (1.0 + daily.fillna(0.0)).cumprod().rename("equity")


def turnover_units(weights: pd.DataFrame) -> pd.Series:
    if weights.empty:
        return pd.Series(dtype=float)
    return weights.diff().abs().fillna(weights.abs()).sum(axis=1) / 2.0


def apply_cost_stress(daily: pd.Series, weights: pd.DataFrame, cost_per_turnover_unit: float) -> pd.Series:
    costs = turnover_units(weights).reindex(daily.index).fillna(0.0) * cost_per_turnover_unit
    return (daily - costs).rename(daily.name)


def stress_results(
    root: Path,
    rows: list[dict[str, str]],
    weights_by_variant: dict[str, pd.DataFrame],
    returns_by_variant: dict[str, pd.Series],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for stress_id, cost in STRESS_COSTS.items():
        stressed_returns = {
            variant_id: apply_cost_stress(daily, weights_by_variant[variant_id], cost)
            for variant_id, daily in returns_by_variant.items()
        }
        stressed_metrics = {
            variant_id: metrics(stressed_returns[variant_id], weights_by_variant[variant_id])
            for variant_id in stressed_returns
        }
        out[stress_id] = [
            result_for_row(
                row,
                stressed_metrics[row["variant_id"]],
                stressed_returns[row["variant_id"]],
                stressed_metrics,
                stressed_returns,
            )
            for row in rows
        ]
    return out


def subperiod_rows(
    base_results: list[dict[str, Any]],
    weights_by_variant: dict[str, pd.DataFrame],
    returns_by_variant: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    result_by_id = {row["variant_id"]: row for row in base_results}
    bil_returns = returns_by_variant["connors_rsi2_bil_cash_control_v1"]
    rows: list[dict[str, Any]] = []
    for variant_id, daily in returns_by_variant.items():
        latest = daily.index.max().date().isoformat()
        role = result_by_id[variant_id]["variant_role"]
        for period_id, start_text, end_text in SUBPERIODS:
            start = pd.Timestamp(start_text)
            end = pd.Timestamp(end_text) if end_text else daily.index.max()
            subset = daily.loc[(daily.index >= start) & (daily.index <= end)]
            subset_weights = weights_by_variant[variant_id].loc[
                weights_by_variant[variant_id].index.intersection(subset.index)
            ]
            bil_subset = bil_returns.loc[bil_returns.index.intersection(subset.index)]
            if subset.empty:
                rows.append(
                    {
                        "variant_id": variant_id,
                        "variant_role": role,
                        "period_id": period_id,
                        "start_date": start_text,
                        "end_date": end_text or latest,
                        "subperiod_weakness_flag": True,
                    }
                )
                continue
            row_metrics = metrics(subset, subset_weights)
            bil_total = float(equity_from_returns(bil_subset).iloc[-1] - 1.0) if not bil_subset.empty else float("nan")
            same_window_vs_bil = row_metrics["total_return"] - bil_total
            weakness = row_metrics["total_return"] <= 0.0 or same_window_vs_bil <= 0.0 or row_metrics["max_drawdown"] < -0.25
            rows.append(
                {
                    "variant_id": variant_id,
                    "variant_role": role,
                    "period_id": period_id,
                    "start_date": row_metrics["effective_start_date"],
                    "end_date": row_metrics["effective_end_date"],
                    "total_return": row_metrics["total_return"],
                    "cagr": row_metrics["cagr"],
                    "max_drawdown": row_metrics["max_drawdown"],
                    "return_drawdown_proxy": row_metrics["return_drawdown_proxy"],
                    "same_window_return_versus_bil": same_window_vs_bil,
                    "subperiod_weakness_flag": weakness,
                }
            )
    return rows


def rolling_rows(base_results: list[dict[str, Any]], returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    result_by_id = {row["variant_id"]: row for row in base_results}
    rows: list[dict[str, Any]] = []
    for variant_id, daily in returns_by_variant.items():
        equity = equity_from_returns(daily)
        rolling_180 = (equity / equity.shift(180) - 1.0).dropna()
        rolling_252 = (equity / equity.shift(252) - 1.0).dropna()
        worst_180 = float(rolling_180.min()) if not rolling_180.empty else float("nan")
        worst_252 = float(rolling_252.min()) if not rolling_252.empty else float("nan")
        positive_180 = float((rolling_180 > 0.0).mean()) if not rolling_180.empty else float("nan")
        positive_252 = float((rolling_252 > 0.0).mean()) if not rolling_252.empty else float("nan")
        weakness = (
            (finite(worst_180) and worst_180 < -0.10)
            or (finite(worst_252) and worst_252 < -0.12)
            or (finite(positive_252) and positive_252 < 0.50)
        )
        rows.append(
            {
                "variant_id": variant_id,
                "variant_role": result_by_id[variant_id]["variant_role"],
                "worst_180_day_return": worst_180,
                "worst_252_day_return": worst_252,
                "positive_180_day_ratio": positive_180,
                "positive_252_day_ratio": positive_252,
                "rolling_window_weakness": weakness,
            }
        )
    return rows


def trade_segments(weights: pd.DataFrame, daily: pd.Series) -> list[dict[str, Any]]:
    applied_spy = weights["SPY"].reindex(daily.index).ffill().fillna(0.0).shift(1).fillna(0.0) > 0.5
    segments: list[dict[str, Any]] = []
    start: pd.Timestamp | None = None
    prev = False
    for date, active in applied_spy.items():
        active_bool = bool(active)
        if active_bool and not prev:
            start = pd.Timestamp(date)
        if prev and not active_bool and start is not None:
            end = pd.Timestamp(date) - pd.tseries.offsets.BDay(1)
            event_returns = daily.loc[(daily.index >= start) & (daily.index <= end)]
            if not event_returns.empty:
                segments.append(
                    {
                        "start_date": start,
                        "end_date": event_returns.index.max(),
                        "holding_days": int(len(event_returns)),
                        "event_return": float((1.0 + event_returns).prod() - 1.0),
                    }
                )
            start = None
        prev = active_bool
    if prev and start is not None:
        event_returns = daily.loc[daily.index >= start]
        if not event_returns.empty:
            segments.append(
                {
                    "start_date": start,
                    "end_date": event_returns.index.max(),
                    "holding_days": int(len(event_returns)),
                    "event_return": float((1.0 + event_returns).prod() - 1.0),
                }
            )
    return segments


def event_stability_rows(
    base_results: list[dict[str, Any]],
    weights_by_variant: dict[str, pd.DataFrame],
    returns_by_variant: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    result_by_id = {row["variant_id"]: row for row in base_results}
    rows: list[dict[str, Any]] = []
    for variant_id in EXPECTED_VARIANTS:
        role = result_by_id[variant_id]["variant_role"]
        if role == "control":
            rows.append(
                {
                    "variant_id": variant_id,
                    "variant_role": role,
                    "event_reconstruction_status": "control_only_not_source_event_stability",
                    "entry_count": 0,
                    "exit_count": 0,
                    "event_count": 0,
                    "average_holding_days": float("nan"),
                    "median_holding_days": float("nan"),
                    "win_event_count": 0,
                    "loss_event_count": 0,
                    "positive_event_rate": float("nan"),
                    "average_event_return": float("nan"),
                    "worst_event_return": float("nan"),
                    "event_unstable": False,
                }
            )
            continue
        segments = trade_segments(weights_by_variant[variant_id], returns_by_variant[variant_id])
        returns = pd.Series([segment["event_return"] for segment in segments], dtype=float)
        holding = pd.Series([segment["holding_days"] for segment in segments], dtype=float)
        event_count = int(len(segments))
        win_count = int((returns > 0.0).sum()) if event_count else 0
        loss_count = int((returns <= 0.0).sum()) if event_count else 0
        average_return = float(returns.mean()) if event_count else float("nan")
        positive_rate = float(win_count / event_count) if event_count else float("nan")
        unstable = (
            event_count < 30
            or (finite(average_return) and average_return <= 0.0)
            or (finite(positive_rate) and positive_rate < 0.45)
        )
        rows.append(
            {
                "variant_id": variant_id,
                "variant_role": role,
                "event_reconstruction_status": "reconstructed_from_shifted_spy_exposure",
                "entry_count": event_count,
                "exit_count": max(event_count - 1, 0) if bool(weights_by_variant[variant_id]["SPY"].iloc[-1] > 0.5) else event_count,
                "event_count": event_count,
                "average_holding_days": float(holding.mean()) if event_count else float("nan"),
                "median_holding_days": float(holding.median()) if event_count else float("nan"),
                "win_event_count": win_count,
                "loss_event_count": loss_count,
                "positive_event_rate": positive_rate,
                "average_event_return": average_return,
                "worst_event_return": float(returns.min()) if event_count else float("nan"),
                "event_unstable": unstable,
            }
        )
    return rows


def comparison_rows(base_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["variant_id"]: row for row in base_results}
    bil = by_id["connors_rsi2_bil_cash_control_v1"]
    spy = by_id["connors_rsi2_spy_buy_hold_control_v1"]
    spy200d = by_id["connors_rsi2_spy200d_frozen_control_v1"]
    rows: list[dict[str, Any]] = []
    for row in base_results:
        rows.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "total_return": row["total_return"],
                "cagr": row["cagr"],
                "max_drawdown": row["max_drawdown"],
                "return_drawdown_proxy": row["return_drawdown_proxy"],
                "total_return_delta_vs_bil": row["total_return"] - bil["total_return"],
                "total_return_delta_vs_spy_buy_hold": row["total_return"] - spy["total_return"],
                "total_return_delta_vs_spy200d": row["total_return"] - spy200d["total_return"],
                "max_drawdown_delta_vs_spy_buy_hold": row["max_drawdown"] - spy["max_drawdown"],
            }
        )
    return rows


def robustness_label(
    base: dict[str, Any],
    stress_10: dict[str, Any],
    stress_25: dict[str, Any],
    subperiod_failure_count: int,
    rolling_weakness: bool,
    event_unstable: bool,
) -> str:
    if base["variant_role"] == "control":
        return "connors_rsi2_robustness_control_only"
    if base["variant_role"] == "timing_sanity":
        return "connors_rsi2_robustness_context_only"
    if not base["numeric_criteria_pass"]:
        return "connors_rsi2_robustness_context_only"
    if not stress_10["numeric_criteria_pass"] or not stress_25["numeric_criteria_pass"]:
        return "connors_rsi2_robustness_cost_sensitive"
    if subperiod_failure_count:
        return "connors_rsi2_robustness_subperiod_weak"
    if rolling_weakness:
        return "connors_rsi2_robustness_rolling_weak"
    if event_unstable:
        return "connors_rsi2_robustness_event_unstable"
    return "connors_rsi2_robustness_primary_survives"


def stress_summary_rows(
    stress: dict[str, list[dict[str, Any]]],
    weights_by_variant: dict[str, pd.DataFrame],
    subperiod: list[dict[str, Any]],
    rolling: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_stress = {stress_id: {row["variant_id"]: row for row in rows} for stress_id, rows in stress.items()}
    sub_failures: dict[str, int] = {}
    for row in subperiod:
        if row.get("subperiod_weakness_flag") is True:
            sub_failures[row["variant_id"]] = sub_failures.get(row["variant_id"], 0) + 1
    rolling_by_id = {row["variant_id"]: row for row in rolling}
    events_by_id = {row["variant_id"]: row for row in events}
    out: list[dict[str, Any]] = []
    for variant_id in EXPECTED_VARIANTS:
        base = by_stress["base"][variant_id]
        stress_10 = by_stress["stress_10bps"][variant_id]
        stress_25 = by_stress["stress_25bps"][variant_id]
        turnover = turnover_units(weights_by_variant[variant_id])
        rolling_weak = bool(rolling_by_id[variant_id]["rolling_window_weakness"])
        event_unstable = bool(events_by_id[variant_id]["event_unstable"])
        label = robustness_label(
            base,
            stress_10,
            stress_25,
            sub_failures.get(variant_id, 0),
            rolling_weak,
            event_unstable,
        )
        out.append(
            {
                "lane_id": LANE_ID,
                "family_id": FAMILY_ID,
                "source_id": SOURCE_ID,
                "variant_id": variant_id,
                "variant_role": base["variant_role"],
                "base_research_label": base["research_label"],
                "robustness_label": label,
                "base_total_return": base["total_return"],
                "base_cagr": base["cagr"],
                "base_max_drawdown": base["max_drawdown"],
                "base_return_drawdown_proxy": base["return_drawdown_proxy"],
                "base_numeric_criteria_pass": base["numeric_criteria_pass"],
                "stress_10bps_total_return": stress_10["total_return"],
                "stress_10bps_cagr": stress_10["cagr"],
                "stress_10bps_max_drawdown": stress_10["max_drawdown"],
                "stress_10bps_return_drawdown_proxy": stress_10["return_drawdown_proxy"],
                "stress_10bps_numeric_criteria_pass": stress_10["numeric_criteria_pass"],
                "stress_25bps_total_return": stress_25["total_return"],
                "stress_25bps_cagr": stress_25["cagr"],
                "stress_25bps_max_drawdown": stress_25["max_drawdown"],
                "stress_25bps_return_drawdown_proxy": stress_25["return_drawdown_proxy"],
                "stress_25bps_numeric_criteria_pass": stress_25["numeric_criteria_pass"],
                "average_turnover_unit": float(turnover.mean()),
                "total_turnover_unit": float(turnover.sum()),
                "cost_model": COST_MODEL,
                "subperiod_failure_count": sub_failures.get(variant_id, 0),
                "rolling_window_weakness": rolling_weak,
                "event_unstable": event_unstable,
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
                "candidate_exhaustive_eligibility": False,
            }
        )
    return out


def sample_adequacy_rows(root: Path) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv_rows(root / SAMPLE_ADEQUACY_DIR / "sample_adequacy_table.csv")
        if row.get("lane_id") == LANE_ID
    ]


def evaluate(root: Path) -> dict[str, Any]:
    _base_results, weights_by_variant, returns_by_variant, _indicators, preflight = evaluate_lane(root)
    rows = load_design_rows(root)
    stress = stress_results(root, rows, weights_by_variant, returns_by_variant)
    base_rows = stress["base"]
    subperiod = subperiod_rows(base_rows, weights_by_variant, returns_by_variant)
    rolling = rolling_rows(base_rows, returns_by_variant)
    events = event_stability_rows(base_rows, weights_by_variant, returns_by_variant)
    comparisons = comparison_rows(base_rows)
    summary_rows = stress_summary_rows(stress, weights_by_variant, subperiod, rolling, events)
    return {
        "design_rows": rows,
        "preflight": preflight,
        "weights_by_variant": weights_by_variant,
        "returns_by_variant": returns_by_variant,
        "stress_rows": summary_rows,
        "subperiod_rows": subperiod,
        "rolling_rows": rolling,
        "event_rows": events,
        "comparison_rows": comparisons,
        "sample_adequacy_rows": sample_adequacy_rows(root),
    }


def manifest_payload(created: str, output: Path, evaluated: dict[str, Any], source_audit: dict[str, Any]) -> dict[str, Any]:
    stress_rows = evaluated["stress_rows"]
    variant_ids = {row["variant_id"] for row in stress_rows}
    primary = next(row for row in stress_rows if row["variant_id"] == "connors_rsi2_spy_bil_primary_v1")
    timing = next(row for row in stress_rows if row["variant_id"] == "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1")
    primary_subperiod_failures = [
        row
        for row in evaluated["subperiod_rows"]
        if row["variant_id"] == "connors_rsi2_spy_bil_primary_v1" and row["subperiod_weakness_flag"] is True
    ]
    primary_rolling = next(row for row in evaluated["rolling_rows"] if row["variant_id"] == "connors_rsi2_spy_bil_primary_v1")
    primary_event = next(row for row in evaluated["event_rows"] if row["variant_id"] == "connors_rsi2_spy_bil_primary_v1")
    invariant_failures = [
        row["variant_id"]
        for row in stress_rows
        if row["promotion_eligibility"] is not False
        or row["paper_forward_eligibility"] is not False
        or row["candidate_exhaustive_eligibility"] is not False
    ]
    max_exposure = max(
        [float(row["max_daily_exposure"]) for row in stress_results_base(evaluated)],
        default=0.0,
    )
    max_weight_sum = max(
        [float(row["max_daily_weight_sum"]) for row in stress_results_base(evaluated)],
        default=0.0,
    )
    sample_primary = next(
        (
            row
            for row in evaluated["sample_adequacy_rows"]
            if row.get("variant_id") == "connors_rsi2_spy_bil_primary_v1"
        ),
        {},
    )
    usable = (
        source_audit.get("final_audit_decision") == AUDIT_DECISION_PASSED
        and len(stress_rows) == len(EXPECTED_VARIANTS)
        and variant_ids == set(EXPECTED_VARIANTS)
        and not invariant_failures
        and set(row["robustness_label"] for row in stress_rows) <= ALLOWED_ROBUSTNESS_LABELS
        and timing["robustness_label"] == "connors_rsi2_robustness_context_only"
    )
    next_action = NEXT_ACTION_AUDIT if usable else NEXT_ACTION_FIX
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_larry_connors_rsi2_robustness_report": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_results_audit_passed": source_audit.get("final_audit_decision") == AUDIT_DECISION_PASSED,
        "same_5_rows_evaluated": variant_ids == set(EXPECTED_VARIANTS),
        "rows_evaluated": len(stress_rows),
        "approved_variant_ids": list(EXPECTED_VARIANTS),
        "evaluated_variant_ids": [row["variant_id"] for row in stress_rows],
        "primary_row_base_pass": primary["base_numeric_criteria_pass"],
        "primary_row_10bps_stress_pass": primary["stress_10bps_numeric_criteria_pass"],
        "primary_row_25bps_stress_pass": primary["stress_25bps_numeric_criteria_pass"],
        "primary_row_subperiod_failure_count": len(primary_subperiod_failures),
        "primary_row_rolling_window_weakness": bool(primary_rolling["rolling_window_weakness"]),
        "primary_event_trade_count": int(primary_event["event_count"]),
        "primary_average_holding_days": primary_event["average_holding_days"],
        "primary_median_holding_days": primary_event["median_holding_days"],
        "primary_worst_event_return": primary_event["worst_event_return"],
        "primary_event_unstable": bool(primary_event["event_unstable"]),
        "sample_adequacy_primary_classification": sample_primary.get("sample_adequacy_classification", "missing"),
        "sample_adequacy_calendar_years": sample_primary.get("calendar_years_covered", "missing"),
        "sample_adequacy_trading_days": sample_primary.get("trading_days_covered", "missing"),
        "sample_adequacy_event_count": sample_primary.get("trade_signal_event_count", "missing"),
        "timing_sanity_context_result": timing["robustness_label"] == "connors_rsi2_robustness_context_only",
        "timing_delay_optimization_recommended": False,
        "control_row_count": sum(1 for row in stress_rows if row["variant_role"] == "control"),
        "control_rows_control_only": all(
            row["robustness_label"] == "connors_rsi2_robustness_control_only"
            for row in stress_rows
            if row["variant_role"] == "control"
        ),
        "invariant_failures": len(invariant_failures),
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "cost_model": COST_MODEL,
        "cost_stress_bps": [10, 25],
        "robustness_evidence_usable": usable,
        "new_rows_added": False,
        "new_variants_created": False,
        "new_indicators_added": False,
        "new_instruments_added": False,
        "rsi_parameters_optimized": False,
        "sma_parameters_optimized": False,
        "threshold_sweep_created": False,
        "timing_delay_optimized": False,
        "stop_loss_or_profit_target_added": False,
        "holding_period_exit_added": False,
        "volatility_filter_added": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "percent_b_continued": False,
        "turn_of_month_rerun": False,
        "faber_taa_designed_or_retested": False,
        "new_strategy_discovery_run": False,
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
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "next_action": next_action,
    }


def stress_results_base(evaluated: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "variant_id": row["variant_id"],
            "max_daily_exposure": source_row.get("max_daily_exposure", 0.0),
            "max_daily_weight_sum": source_row.get("max_daily_weight_sum", 0.0),
        }
        for row in evaluated["stress_rows"]
        for source_row in read_csv_rows(ROOT / SOURCE_RUN_DIR / "row_level_results.csv")
        if source_row.get("variant_id") == row["variant_id"]
    ]


def rolling_report_md(rows: list[dict[str, Any]]) -> str:
    weak = [row for row in rows if row["rolling_window_weakness"] is True]
    return f"""# Rolling-Window Weakness Report

Rows evaluated: `{len(rows)}`

Rows with rolling-window weakness: `{len(weak)}`

Rolling weakness is reported when worst 180-day return is below `-10%`, worst 252-day return is below `-12%`, or positive 252-day rolling ratio is below `50%`. This is a diagnostic durability screen, not a promotion gate.
"""


def event_report_md(rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_id"] == "connors_rsi2_spy_bil_primary_v1")
    timing = next(row for row in rows if row["variant_id"] == "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1")
    return f"""# Trade / Event Stability Report

Primary reconstructed event count: `{primary['event_count']}`

Primary average holding days: `{primary['average_holding_days']}`

Primary median holding days: `{primary['median_holding_days']}`

Primary worst event return: `{primary['worst_event_return']}`

Primary event unstable: `{primary['event_unstable']}`

Timing-sanity reconstructed event count: `{timing['event_count']}`

Trade events are reconstructed from shifted SPY exposure, preserving the audited no-lookahead execution convention. Control rows remain control-only and are not source event-stability rows.
"""


def control_report_md(rows: list[dict[str, Any]]) -> str:
    return f"""# Control Comparison Report

Rows compared: `{len(rows)}`

Controls: `connors_rsi2_spy_buy_hold_control_v1`, `connors_rsi2_bil_cash_control_v1`, `connors_rsi2_spy200d_frozen_control_v1`

Control rows remain control-only and cannot become promotion, candidate_exhaustive, or paper/demo candidates.
"""


def exposure_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

Invariant failures: `{manifest['invariant_failures']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

BIL/cash remains replacement/remainder only. No output is promotable, candidate_exhaustive-ready, or paper/demo eligible.
"""


def timing_sanity_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Timing-Sanity Context Report

Timing-sanity context result: `{manifest['timing_sanity_context_result']}`

Timing-delay optimization recommended: `{manifest['timing_delay_optimization_recommended']}`

The one-extra-bar delayed row remains a context-only timing sanity check. Its relative performance does not authorize timing-delay optimization or strategy selection.
"""


def sample_adequacy_note_md(manifest: dict[str, Any]) -> str:
    return f"""# Sample Adequacy Carry-Forward Note

Primary sample adequacy classification: `{manifest['sample_adequacy_primary_classification']}`

Calendar years: `{manifest['sample_adequacy_calendar_years']}`

Trading days: `{manifest['sample_adequacy_trading_days']}`

Event count: `{manifest['sample_adequacy_event_count']}`

Sample adequacy is carried forward from the independent sample adequacy report. It supports diagnostic interpretation only and is not proof of profitability or promotion readiness.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Larry Connors RSI(2) Robustness Report

Rows evaluated: `{manifest['rows_evaluated']}`

Primary base pass: `{manifest['primary_row_base_pass']}`

Primary 10 bps stress pass: `{manifest['primary_row_10bps_stress_pass']}`

Primary 25 bps stress pass: `{manifest['primary_row_25bps_stress_pass']}`

Primary subperiod failures: `{manifest['primary_row_subperiod_failure_count']}`

Primary rolling-window weakness: `{manifest['primary_row_rolling_window_weakness']}`

Primary event/trade count: `{manifest['primary_event_trade_count']}`

Primary average holding days: `{manifest['primary_average_holding_days']}`

Primary median holding days: `{manifest['primary_median_holding_days']}`

Primary worst event return: `{manifest['primary_worst_event_return']}`

Timing-sanity context result: `{manifest['timing_sanity_context_result']}`

Control rows control-only: `{manifest['control_rows_control_only']}`

Invariant failures: `{manifest['invariant_failures']}`

Robustness evidence usable: `{manifest['robustness_evidence_usable']}`

Outputs are diagnostic only, non-promotable, not candidate_exhaustive-ready, and not paper/demo eligible.

Exact next action:

`{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Next Action

Exact next action:

`{next_action}`

This robustness report does not authorize promotion, candidate_exhaustive, paper/demo activation, broker/live use, or real-money recommendations.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_larry_connors_rsi2_bounded_bt_robustness_consistency_check.json"] = True
    checks = {
        "robustness_report_mode": manifest["public_source_larry_connors_rsi2_robustness_report"] is True,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "source_audit_passed": manifest["source_results_audit_passed"] is True,
        "same_5_rows": manifest["same_5_rows_evaluated"] is True and manifest["rows_evaluated"] == 5,
        "no_parameter_or_design_expansion": manifest["new_rows_added"] is False
        and manifest["new_variants_created"] is False
        and manifest["new_indicators_added"] is False
        and manifest["new_instruments_added"] is False
        and manifest["rsi_parameters_optimized"] is False
        and manifest["sma_parameters_optimized"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["timing_delay_optimized"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["holding_period_exit_added"] is False
        and manifest["volatility_filter_added"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_scrape_or_other_public_source_work": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["percent_b_continued"] is False
        and manifest["turn_of_month_rerun"] is False
        and manifest["faber_taa_designed_or_retested"] is False,
        "no_discovery_or_candidates": manifest["new_strategy_discovery_run"] is False
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
        "timing_sanity_context_only": manifest["timing_sanity_context_result"] is True
        and manifest["timing_delay_optimization_recommended"] is False,
        "controls_control_only": manifest["control_rows_control_only"] is True,
        "invariants_pass": manifest["invariant_failures"] == 0
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "outputs_non_promotable": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    source_audit = read_json(
        root / SOURCE_AUDIT_DIR / "public_source_larry_connors_rsi2_bounded_bt_results_audit_manifest.json"
    )
    evaluated = evaluate(root)
    output = root / output_dir
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(now_utc(), output, evaluated, source_audit)

    write_json(output / "public_source_larry_connors_rsi2_bounded_bt_robustness_manifest.json", manifest)
    write_csv(output / "base_vs_cost_stress.csv", evaluated["stress_rows"], list(STRESS_FIELDS))
    write_csv(output / "subperiod_performance.csv", evaluated["subperiod_rows"], list(SUBPERIOD_FIELDS))
    write_csv(output / "rolling_window_weakness.csv", evaluated["rolling_rows"], list(ROLLING_FIELDS))
    write_text(output / "rolling_window_weakness_report.md", rolling_report_md(evaluated["rolling_rows"]))
    write_csv(output / "trade_event_stability_report.csv", evaluated["event_rows"], list(EVENT_FIELDS))
    write_text(output / "trade_event_stability_report.md", event_report_md(evaluated["event_rows"]))
    write_csv(output / "control_comparison_report.csv", evaluated["comparison_rows"], list(CONTROL_FIELDS))
    write_text(output / "control_comparison_report.md", control_report_md(evaluated["comparison_rows"]))
    write_text(output / "exposure_invariant_report.md", exposure_report_md(manifest))
    write_text(output / "timing_sanity_context_report.md", timing_sanity_report_md(manifest))
    write_text(output / "sample_adequacy_carry_forward_note.md", sample_adequacy_note_md(manifest))
    write_text(output / "public_source_larry_connors_rsi2_bounded_bt_robustness_summary.md", summary_md(manifest))
    write_text(output / "public_source_larry_connors_rsi2_bounded_bt_robustness_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_larry_connors_rsi2_bounded_bt_robustness_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
