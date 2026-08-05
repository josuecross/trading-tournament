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

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    pagonidis_ibs_next_open_portability_exploration_v1 as parent,
)


TASK_ID = "pagonidis_ibs_next_open_incremental_validation_v1"
MODE = "validation"
STAGE = "validation"
STRATEGY_ID = parent.STRATEGY_ID
FAMILY_ID = parent.FAMILY_ID
PARENT_TRIAL_ID = parent.TRIAL_ID
VALIDATION_TRIAL_ID = (
    "pagonidis_ibs_next_open_incremental_validation_v1__child"
)
ADAPTATION_LABEL = "validation_variant"
FROZEN_TIMESTAMP = "2026-07-25T01:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 2.5, 5.0, 7.5, 10.0)
REPRODUCTION_COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
ROLLING_MONTHS = (24, 36, 60)
MIN_ROLLING_ACTIVE_SIGNALS = 25
EXPLORATION_ACTIVE_SESSIONS = 876
EXPLORATION_ELIGIBLE_SESSIONS = 4794
FROZEN_EXPOSURE_FRACTION = (
    EXPLORATION_ACTIVE_SESSIONS / EXPLORATION_ELIGIBLE_SESSIONS
)
TOLERANCE = 1e-12

OUTPUT_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / TASK_ID
    / "latest"
)
PARENT_EVIDENCE_DIR = parent.OUTPUT_DIR
V5_EVIDENCE_DIR = parent.V5_DIR
CACHE_DIR = parent.CACHE_DIR

PROTECTED_STATE_PATHS = parent.PROTECTED_STATE_PATHS
CONTROL_IDS = parent.CONTROL_IDS
CRITICAL_CONTROL_IDS = parent.CRITICAL_CONTROL_IDS

ALLOWED_OUTCOMES = {
    "validation_positive",
    "validation_mixed",
    "validation_failed",
    "validation_data_or_methodology_blocked",
}
ALLOWED_FAILURE_REASONS = {
    "",
    "period_instability",
    "cost_drag",
    "turnover_drag",
    "weak_return",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "overfit_or_unstable",
    "data_or_comparability_failure",
    "methodology_failure",
}

REQUIRED_OUTPUTS = {
    "validation_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "full_period_results.csv",
    "chronological_half_results.csv",
    "rolling_24_month_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "calendar_year_results.csv",
    "cost_sensitivity_results.csv",
    "break_even_cost_results.csv",
    "signal_stability_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "validation_report.md",
}

FORBIDDEN_ACTIONS = {
    "source_research_or_source_completion": False,
    "threshold_or_signal_change": False,
    "instrument_or_execution_change": False,
    "parameter_optimization": False,
    "result_driven_change": False,
    "exact_source_replication_claimed": False,
    "promotion_or_lifecycle_update": False,
    "paper_demo_activation": False,
    "provider_access": False,
    "broker_account_order_or_real_money_action": False,
}

RESULT_METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "active_session_count",
    "active_session_fraction",
    "average_spy_intraday_exposure",
    "total_one_way_turnover",
    "number_open_entries",
    "number_close_exits",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "weight_invariant_status",
    "exposure_invariant_status",
    "invariant_pass",
]


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.12g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            width=120,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def map_hashes(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def tree_content_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def tree_identity_hash(root: Path, excluded: Path | None = None) -> str:
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    if not root.exists():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if excluded_resolved is not None and (
            resolved == excluded_resolved or excluded_resolved in resolved.parents
        ):
            continue
        stat = path.stat()
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "validation" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def deterministic_core_hash() -> str:
    payload = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "parent_frozen_core_hash": parent.deterministic_core_hash(),
        "signal_formula": "(close-low)/(high-low)",
        "strict_threshold": 0.20,
        "zero_range_behavior": "inactive",
        "entry": "regular_session_open_t_plus_1",
        "exit": "regular_session_close_t_plus_1",
        "overnight_asset": "BIL",
        "cost_bps": COST_BPS,
        "rolling_months": ROLLING_MONTHS,
        "minimum_rolling_active_signals": MIN_ROLLING_ACTIVE_SIGNALS,
        "frozen_exposure_fraction": FROZEN_EXPOSURE_FRACTION,
        "controls": CONTROL_IDS,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def strategy_row(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": "SPY IBS Next-Open Intraday Portability",
        "entity_type": "strategy_configuration",
        "strategy_architecture": (
            "completed_close_range_position_signal_next_open_intraday_allocation"
        ),
        "source_or_research_lineage": (
            "strategy_source_library_refresh_v5:"
            "pagonidis_ibs_equity_etf_reversal:execution_portability_test"
        ),
        "instrument_universe": "SPY|BIL",
        "parameters": {
            "ibs_formula": "(adjusted_close-adjusted_low)/(adjusted_high-adjusted_low)",
            "ibs_threshold": 0.20,
            "comparison": "strict_less_than",
            "zero_range_behavior": "inactive",
            "signal_timestamp": "completed_close_t",
            "entry_timestamp": "regular_session_open_t_plus_1",
            "exit_timestamp": "regular_session_close_t_plus_1",
            "overnight_asset": "BIL",
            "validation_cost_bps": list(COST_BPS),
        },
        "benchmark_or_control": list(CONTROL_IDS),
        "route": "standalone",
        "prior_stage": "exploratory_followup_standalone",
        "prior_outcome": "exploratory_followup_candidate_standalone",
        "stage": STAGE,
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "execution_portability_strategy": True,
        "exact_source_replication_claimed": False,
        "promotion_or_paper_demo_authorized": False,
    }


def trial_row(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        **strategy_row(outcome, failure_reason, next_action),
        "entity_type": "experiment_trial",
        "changed_fields_from_parent": (
            "validation_period_cost_and_stability_diagnostics_only"
        ),
        "signal_changed": False,
        "threshold_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "cost_diagnostics_expanded": True,
        "optimization_performed": False,
        "result_driven_change": False,
        "validation_child_trial": True,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    rows = parent.benchmark_rows()
    return [
        {
            **row,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "validation_task_id": TASK_ID,
            "frozen_from_parent_exploration": True,
            "counted_as_validation_trial": False,
        }
        for row in rows
    ]


def process_row(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
        "next_action_executed": False,
    }


def build_paths() -> tuple[
    dict[tuple[str, float], dict[str, Any]],
    dict[str, pd.DataFrame],
    pd.DatetimeIndex,
    pd.Series,
]:
    preflight_rows, frames, preflight_passed = parent.data_preflight()
    if not preflight_passed:
        failures = [
            row["failure_reason"]
            for row in preflight_rows
            if row["candidate_preflight_status"] != "pass"
        ]
        raise RuntimeError(f"Adjusted OHLCV preflight failed: {failures}")
    common = frames["SPY"].index.intersection(frames["BIL"].index).sort_values()
    frames = {
        symbol: frame.reindex(common)
        for symbol, frame in frames.items()
    }
    schedules, ibs = parent.signal_schedules(frames["SPY"], common)
    candidate = schedules[STRATEGY_ID]
    if int(candidate.sum()) != EXPLORATION_ACTIVE_SESSIONS:
        raise RuntimeError("Frozen candidate active-session count changed")
    if len(candidate) != EXPLORATION_ELIGIBLE_SESSIONS:
        raise RuntimeError("Frozen candidate eligible-session count changed")
    schedules["exposure_matched_fractional_spy_intraday_v1"] = pd.Series(
        FROZEN_EXPOSURE_FRACTION,
        index=candidate.index,
        name="exposure_matched_fractional_spy_intraday_v1",
    )
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost_bps in COST_BPS:
        for row_id, schedule in schedules.items():
            payloads[(row_id, cost_bps)] = parent.simulate_intraday_schedule(
                frames["SPY"],
                frames["BIL"],
                common,
                schedule,
                cost_bps,
                row_id,
            )
        payloads[("SPY_buy_and_hold", cost_bps)] = parent.simulate_spy_buy_hold(
            frames["SPY"],
            common,
            cost_bps,
        )
    return payloads, frames, common, ibs


def metric_payload(
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    metrics = parent.metric_payload(payload, period_index)
    if period_index is None:
        exposure = payload["spy_exposure"]
    else:
        exposure = payload["spy_exposure"].reindex(period_index).fillna(0.0)
    return {
        **metrics,
        "active_session_count": int((exposure > 0.0).sum()),
    }


def append_reproduction_comparison(
    output: list[dict[str, Any]],
    scope: str,
    row_id: str,
    cost_bps: float,
    period_label: str,
    metric: str,
    expected: Any,
    actual: Any,
) -> None:
    numeric = metric not in {"evaluation_start", "evaluation_end"}
    if numeric:
        expected_number = float(expected)
        actual_number = float(parent.csv_value(float(actual)))
        difference = abs(expected_number - actual_number)
        passed = bool(difference <= REPRODUCTION_TOLERANCE)
        comparison_basis = (
            "authoritative_parent_csv_precision_12_significant_digits"
        )
    else:
        difference = ""
        passed = str(expected) == str(actual)
        comparison_basis = "exact_string"
    output.append(
        {
            "scope": scope,
            "row_id": row_id,
            "cost_assumption_bps": cost_bps,
            "period_label": period_label,
            "metric": metric,
            "expected_value": expected,
            "actual_value": actual,
            "absolute_difference": difference,
            "tolerance": REPRODUCTION_TOLERANCE if numeric else "exact",
            "comparison_basis": comparison_basis,
            "reproduction_status": "pass" if passed else "fail",
        }
    )


def reproduction_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    expected_full = read_csv_rows(PARENT_EVIDENCE_DIR / "all_trial_results.csv")
    expected_controls = read_csv_rows(PARENT_EVIDENCE_DIR / "control_results.csv")
    expected_halves = read_csv_rows(
        PARENT_EVIDENCE_DIR / "chronological_half_results.csv"
    )
    compared_fields = (
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "active_session_fraction",
        "average_spy_intraday_exposure",
        "total_one_way_turnover",
        "number_open_entries",
        "number_close_exits",
        "transaction_cost_drag",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
    )
    for expected in expected_full + expected_controls:
        row_id = expected["row_id"]
        cost_bps = float(expected["cost_assumption_bps"])
        actual = metric_payload(payloads[(row_id, cost_bps)])
        for metric in compared_fields:
            append_reproduction_comparison(
                output,
                "full_period_candidate_or_control",
                row_id,
                cost_bps,
                "full_period",
                metric,
                expected[metric],
                actual[metric],
            )
    index = payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]["returns"].index
    halves = parent.split_halves(index)
    for expected in expected_halves:
        row_id = expected["row_id"]
        cost_bps = float(expected["cost_assumption_bps"])
        period_label = expected["period_label"]
        actual = metric_payload(
            payloads[(row_id, cost_bps)],
            halves[period_label],
        )
        for metric in compared_fields:
            append_reproduction_comparison(
                output,
                "chronological_half_candidate_or_control",
                row_id,
                cost_bps,
                period_label,
                metric,
                expected[metric],
                actual[metric],
            )
    prompt_values = {
        0.0: {
            "total_return": 2.072895,
            "cagr": 0.060701,
            "sharpe_ratio": 0.770128,
            "maximum_drawdown": -0.128813,
        },
        5.0: {
            "total_return": 0.279413,
            "cagr": 0.013018,
            "sharpe_ratio": 0.201135,
            "maximum_drawdown": -0.284826,
        },
        10.0: {
            "total_return": -0.467545,
            "cagr": -0.032543,
            "sharpe_ratio": -0.370457,
            "maximum_drawdown": -0.576345,
        },
    }
    for cost_bps, expected_metrics in prompt_values.items():
        actual = metric_payload(payloads[(STRATEGY_ID, cost_bps)])
        for metric, expected in expected_metrics.items():
            difference = abs(float(actual[metric]) - expected)
            output.append(
                {
                    "scope": "prompt_approximate_candidate_value",
                    "row_id": STRATEGY_ID,
                    "cost_assumption_bps": cost_bps,
                    "period_label": "full_period",
                    "metric": metric,
                    "expected_value": expected,
                    "actual_value": actual[metric],
                    "absolute_difference": difference,
                    "tolerance": 1e-6,
                    "comparison_basis": "prompt_approximate_value",
                    "reproduction_status": "pass"
                    if difference <= 1e-6
                    else "fail",
                }
            )
    candidate_five = metric_payload(payloads[(STRATEGY_ID, 5.0)])
    for metric, expected, actual in (
        (
            "active_session_count",
            EXPLORATION_ACTIVE_SESSIONS,
            candidate_five["active_session_count"],
        ),
        (
            "total_one_way_turnover",
            1752.0,
            candidate_five["total_one_way_turnover"],
        ),
    ):
        append_reproduction_comparison(
            output,
            "frozen_count_or_turnover",
            STRATEGY_ID,
            5.0,
            "full_period",
            metric,
            expected,
            actual,
        )
    return output


def result_row(
    row_id: str,
    cost_bps: float,
    period_label: str,
    period_role: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": VALIDATION_TRIAL_ID,
        "row_id": row_id,
        "entity_type": (
            "experiment_trial"
            if row_id == STRATEGY_ID
            else "benchmark_reference"
        ),
        "stage": STAGE if row_id == STRATEGY_ID else "benchmark_reference_only",
        "cost_assumption_bps": cost_bps,
        "period_label": period_label,
        "period_role": period_role,
        **metrics,
    }


def full_and_cost_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    full_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for row_id in (STRATEGY_ID, *CONTROL_IDS):
        for cost_bps in COST_BPS:
            row = result_row(
                row_id,
                cost_bps,
                "full_period",
                "validation_full_period",
                metric_payload(payloads[(row_id, cost_bps)]),
            )
            cost_rows.append(row)
            if cost_bps == PRIMARY_COST_BPS:
                full_rows.append(row)
    return full_rows, cost_rows


def half_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    index = payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]["returns"].index
    halves = parent.split_halves(index)
    for period_label, period_index in halves.items():
        for row_id in (STRATEGY_ID, *CONTROL_IDS):
            for cost_bps in COST_BPS:
                output.append(
                    result_row(
                        row_id,
                        cost_bps,
                        period_label,
                        "chronological_half_not_clean_or_sealed_holdout",
                        metric_payload(
                            payloads[(row_id, cost_bps)],
                            period_index,
                        ),
                    )
                )
    return output


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    values = (
        float(control["cagr"]) >= float(candidate["cagr"]) - TOLERANCE,
        float(control["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"]) - TOLERANCE,
        float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - TOLERANCE,
    )
    strict = bool(
        float(control["cagr"]) > float(candidate["cagr"]) + TOLERANCE
        or float(control["sharpe_ratio"])
        > float(candidate["sharpe_ratio"]) + TOLERANCE
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + TOLERANCE
    )
    return bool(all(values) and strict)


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    mask = periods.ne(periods.shift(-1)).fillna(True)
    return [pd.Timestamp(value) for value in index[mask]]


def rolling_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
    months: int,
) -> tuple[list[dict[str, Any]], int]:
    output: list[dict[str, Any]] = []
    candidate_payload = payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]
    index = candidate_payload["returns"].index
    first = pd.Timestamp(index.min())
    possible = 0
    for end_date in month_end_dates(index):
        cutoff = end_date - pd.DateOffset(months=months)
        if cutoff < first:
            continue
        possible += 1
        window_index = index[(index >= cutoff) & (index <= end_date)]
        active_signals = int(
            (
                candidate_payload["spy_exposure"]
                .reindex(window_index)
                .fillna(0.0)
                > 0.0
            ).sum()
        )
        if active_signals < MIN_ROLLING_ACTIVE_SIGNALS:
            continue
        candidate = metric_payload(candidate_payload, window_index)
        prior = metric_payload(
            payloads[
                ("prior_day_negative_return_spy_intraday_v1", PRIMARY_COST_BPS)
            ],
            window_index,
        )
        exposure = metric_payload(
            payloads[
                (
                    "exposure_matched_fractional_spy_intraday_v1",
                    PRIMARY_COST_BPS,
                )
            ],
            window_index,
        )
        output.append(
            {
                "window_months": months,
                "cost_assumption_bps": PRIMARY_COST_BPS,
                "window_start": pd.Timestamp(window_index.min()).date().isoformat(),
                "window_end": pd.Timestamp(window_index.max()).date().isoformat(),
                "trading_days": len(window_index),
                "active_signals": active_signals,
                "minimum_active_signal_requirement": MIN_ROLLING_ACTIVE_SIGNALS,
                "candidate_total_return": candidate["total_return"],
                "candidate_cagr": candidate["cagr"],
                "candidate_annualized_volatility": candidate[
                    "annualized_volatility"
                ],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "candidate_turnover": candidate["total_one_way_turnover"],
                "candidate_transaction_cost_drag": candidate[
                    "transaction_cost_drag"
                ],
                "prior_negative_total_return": prior["total_return"],
                "prior_negative_cagr": prior["cagr"],
                "prior_negative_sharpe_ratio": prior["sharpe_ratio"],
                "prior_negative_maximum_drawdown": prior["maximum_drawdown"],
                "total_return_difference_vs_prior_negative": float(
                    candidate["total_return"]
                )
                - float(prior["total_return"]),
                "cagr_difference_vs_prior_negative": float(candidate["cagr"])
                - float(prior["cagr"]),
                "sharpe_difference_vs_prior_negative": float(
                    candidate["sharpe_ratio"]
                )
                - float(prior["sharpe_ratio"]),
                "drawdown_difference_vs_prior_negative": float(
                    candidate["maximum_drawdown"]
                )
                - float(prior["maximum_drawdown"]),
                "prior_negative_dominates_candidate": dominates(prior, candidate),
                "exposure_matched_total_return": exposure["total_return"],
                "exposure_matched_cagr": exposure["cagr"],
                "exposure_matched_sharpe_ratio": exposure["sharpe_ratio"],
                "exposure_matched_maximum_drawdown": exposure[
                    "maximum_drawdown"
                ],
                "total_return_difference_vs_exposure_matched": float(
                    candidate["total_return"]
                )
                - float(exposure["total_return"]),
                "cagr_difference_vs_exposure_matched": float(candidate["cagr"])
                - float(exposure["cagr"]),
                "sharpe_difference_vs_exposure_matched": float(
                    candidate["sharpe_ratio"]
                )
                - float(exposure["sharpe_ratio"]),
                "drawdown_difference_vs_exposure_matched": float(
                    candidate["maximum_drawdown"]
                )
                - float(exposure["maximum_drawdown"]),
                "exposure_matched_dominates_candidate": dominates(
                    exposure,
                    candidate,
                ),
                "maximum_gross_exposure": candidate["maximum_gross_exposure"],
                "maximum_daily_weight_sum": candidate[
                    "maximum_daily_weight_sum"
                ],
                "timing_invariant_status": candidate[
                    "timing_invariant_status"
                ],
                "numeric_invariant_status": candidate[
                    "numeric_invariant_status"
                ],
                "weight_invariant_status": candidate["weight_invariant_status"],
                "exposure_invariant_status": candidate[
                    "exposure_invariant_status"
                ],
            }
        )
    return output, possible


def rolling_summary_rows(
    rolling: dict[int, list[dict[str, Any]]],
    possible_counts: dict[int, int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for months in ROLLING_MONTHS:
        rows = rolling[months]
        count = len(rows)
        if not rows:
            output.append(
                {
                    "window_months": months,
                    "cost_assumption_bps": PRIMARY_COST_BPS,
                    "possible_monthly_stepped_windows": possible_counts[months],
                    "eligible_window_count": 0,
                    "excluded_below_25_active_signals": possible_counts[months],
                }
            )
            continue
        output.append(
            {
                "window_months": months,
                "cost_assumption_bps": PRIMARY_COST_BPS,
                "possible_monthly_stepped_windows": possible_counts[months],
                "eligible_window_count": count,
                "excluded_below_25_active_signals": (
                    possible_counts[months] - count
                ),
                "median_candidate_total_return": float(
                    pd.Series(
                        [row["candidate_total_return"] for row in rows]
                    ).median()
                ),
                "median_candidate_sharpe_ratio": float(
                    pd.Series(
                        [row["candidate_sharpe_ratio"] for row in rows]
                    ).median()
                ),
                "positive_candidate_total_return_fraction": float(
                    np.mean(
                        [
                            float(row["candidate_total_return"]) > 0.0
                            for row in rows
                        ]
                    )
                ),
                "median_sharpe_difference_vs_prior_negative": float(
                    pd.Series(
                        [
                            row["sharpe_difference_vs_prior_negative"]
                            for row in rows
                        ]
                    ).median()
                ),
                "median_sharpe_difference_vs_exposure_matched": float(
                    pd.Series(
                        [
                            row["sharpe_difference_vs_exposure_matched"]
                            for row in rows
                        ]
                    ).median()
                ),
                "prior_negative_domination_fraction": float(
                    np.mean(
                        [
                            bool(row["prior_negative_dominates_candidate"])
                            for row in rows
                        ]
                    )
                ),
                "exposure_matched_domination_fraction": float(
                    np.mean(
                        [
                            bool(row["exposure_matched_dominates_candidate"])
                            for row in rows
                        ]
                    )
                ),
                "any_critical_control_domination_fraction": float(
                    np.mean(
                        [
                            bool(row["prior_negative_dominates_candidate"])
                            or bool(
                                row[
                                    "exposure_matched_dominates_candidate"
                                ]
                            )
                            for row in rows
                        ]
                    )
                ),
                "all_unfavorable_eligible_windows_retained": True,
            }
        )
    return output


def ledger_period_total_return(
    ledger: pd.DataFrame,
    cost_bps: float,
) -> float:
    rate = float(cost_bps) / 10000.0
    gross_factor = 1.0 + ledger["gross_return_before_cost"].to_numpy(dtype=float)
    open_turnover = ledger["open_one_way_turnover"].to_numpy(dtype=float)
    close_turnover = ledger["close_one_way_turnover"].to_numpy(dtype=float)
    net_factors = (
        gross_factor
        * (1.0 - open_turnover * rate)
        * (1.0 - close_turnover * rate)
    )
    return float(np.prod(net_factors) - 1.0)


def break_even_cost(
    ledger: pd.DataFrame,
) -> tuple[float, int, float]:
    zero_return = ledger_period_total_return(ledger, 0.0)
    if zero_return <= 0.0:
        return 0.0, 0, zero_return
    lower = 0.0
    upper = 10.0
    while ledger_period_total_return(ledger, upper) > 0.0 and upper < 10000.0:
        upper *= 2.0
    if upper >= 10000.0 and ledger_period_total_return(ledger, upper) > 0.0:
        return float("nan"), 0, float("nan")
    iterations = 100
    for _ in range(iterations):
        midpoint = (lower + upper) / 2.0
        if ledger_period_total_return(ledger, midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    root = (lower + upper) / 2.0
    return root, iterations, ledger_period_total_return(ledger, root)


def break_even_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    payload = payloads[(STRATEGY_ID, 0.0)]
    ledger = payload["ledger"]
    index = payload["returns"].index
    periods = {"full_period": index, **parent.split_halves(index)}
    output: list[dict[str, Any]] = []
    for label, period_index in periods.items():
        period_ledger = ledger.reindex(period_index)
        root, iterations, residual = break_even_cost(period_ledger)
        output.append(
            {
                "period_label": label,
                "period_role": (
                    "validation_full_period"
                    if label == "full_period"
                    else "chronological_half_not_clean_or_sealed_holdout"
                ),
                "evaluation_start": pd.Timestamp(
                    period_index.min()
                ).date().isoformat(),
                "evaluation_end": pd.Timestamp(
                    period_index.max()
                ).date().isoformat(),
                "active_signals": int(
                    (payload["spy_exposure"].reindex(period_index) > 0.0).sum()
                ),
                "total_one_way_turnover": float(
                    payload["turnover"].reindex(period_index).sum()
                ),
                "return_at_zero_bps": ledger_period_total_return(
                    period_ledger,
                    0.0,
                ),
                "break_even_one_way_cost_bps": root,
                "root_residual_total_return": residual,
                "root_finding_method": "deterministic_bisection_on_frozen_trade_ledger",
                "root_finding_iterations": iterations,
                "threshold_or_strategy_optimized_from_root": False,
            }
        )
    return output


def calendar_year_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    zero = payloads[(STRATEGY_ID, 0.0)]
    primary = payloads[(STRATEGY_ID, PRIMARY_COST_BPS)]
    output: list[dict[str, Any]] = []
    for year in sorted(primary["returns"].index.year.unique()):
        index = primary["returns"].index[primary["returns"].index.year == year]
        active = primary["spy_exposure"].reindex(index) > 0.0
        active_index = index[active.to_numpy(dtype=bool)]
        gross_active = zero["ledger"].reindex(active_index)[
            "gross_return_before_cost"
        ].astype(float)
        net_active = primary["returns"].reindex(active_index).astype(float)
        output.append(
            {
                "calendar_year": int(year),
                "period_role": "descriptive_calendar_year_validation_diagnostic",
                "evaluation_start": pd.Timestamp(index.min()).date().isoformat(),
                "evaluation_end": pd.Timestamp(index.max()).date().isoformat(),
                "active_signals": int(active.sum()),
                "gross_active_session_return": float(
                    (1.0 + gross_active).prod() - 1.0
                ),
                "net_active_session_return_at_5_bps": float(
                    (1.0 + net_active).prod() - 1.0
                ),
                "profitable_signal_fraction": float(
                    (gross_active > 0.0).mean()
                )
                if len(gross_active)
                else "",
                "total_one_way_turnover": float(
                    primary["turnover"].reindex(index).sum()
                ),
                "transaction_cost_drag": float(
                    primary["cost"].reindex(index).sum()
                ),
                "threshold_changed_from_diagnostic": False,
            }
        )
    return output


def signal_stability_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
    break_even: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    zero = payloads[(STRATEGY_ID, 0.0)]
    index = zero["returns"].index
    periods = {"full_period": index, **parent.split_halves(index)}
    roots = {
        row["period_label"]: row["break_even_one_way_cost_bps"]
        for row in break_even
    }
    output: list[dict[str, Any]] = []
    for label, period_index in periods.items():
        active = zero["spy_exposure"].reindex(period_index) > 0.0
        active_index = period_index[active.to_numpy(dtype=bool)]
        event_returns = zero["ledger"].reindex(active_index)[
            "SPY_intraday_return"
        ].astype(float)
        net_by_cost = {
            str(cost_bps): float(
                (
                    1.0
                    + payloads[(STRATEGY_ID, cost_bps)]["returns"].reindex(
                        period_index
                    )
                ).prod()
                - 1.0
            )
            for cost_bps in COST_BPS
        }
        output.append(
            {
                "period_label": label,
                "period_role": (
                    "validation_full_period"
                    if label == "full_period"
                    else "chronological_half_not_clean_or_sealed_holdout"
                ),
                "evaluation_start": pd.Timestamp(
                    period_index.min()
                ).date().isoformat(),
                "evaluation_end": pd.Timestamp(
                    period_index.max()
                ).date().isoformat(),
                "active_signals": int(active.sum()),
                "gross_return_before_cost": float(
                    (1.0 + zero["returns"].reindex(period_index)).prod() - 1.0
                ),
                "net_return_0_bps": net_by_cost["0.0"],
                "net_return_2_5_bps": net_by_cost["2.5"],
                "net_return_5_bps": net_by_cost["5.0"],
                "net_return_7_5_bps": net_by_cost["7.5"],
                "net_return_10_bps": net_by_cost["10.0"],
                "net_returns_by_cost_json": net_by_cost,
                "break_even_one_way_cost_bps": roots[label],
                "average_gross_SPY_intraday_event_return": float(
                    event_returns.mean()
                ),
                "median_gross_SPY_intraday_event_return": float(
                    event_returns.median()
                ),
                "threshold_changed_from_diagnostic": False,
            }
        )
    return output


def turnover_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row_id in (STRATEGY_ID, *CONTROL_IDS):
        for cost_bps in COST_BPS:
            payload = payloads[(row_id, cost_bps)]
            ledger = payload["ledger"]
            metrics = metric_payload(payload)
            output.append(
                {
                    "row_id": row_id,
                    "entity_type": (
                        "experiment_trial"
                        if row_id == STRATEGY_ID
                        else "benchmark_reference"
                    ),
                    "cost_assumption_bps": cost_bps,
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "separate_open_and_close_switches": (
                        row_id != "SPY_buy_and_hold"
                    ),
                    "total_open_one_way_turnover": (
                        float(ledger["open_one_way_turnover"].sum())
                        if "open_one_way_turnover" in ledger
                        else metrics["total_one_way_turnover"]
                    ),
                    "total_close_one_way_turnover": (
                        float(ledger["close_one_way_turnover"].sum())
                        if "close_one_way_turnover" in ledger
                        else 0.0
                    ),
                    "total_one_way_turnover": metrics[
                        "total_one_way_turnover"
                    ],
                    "open_entry_count": metrics["number_open_entries"],
                    "close_exit_count": metrics["number_close_exits"],
                    "transaction_cost_drag": metrics[
                        "transaction_cost_drag"
                    ],
                    "open_and_close_costs_netted_away": False,
                }
            )
    return output


def invariant_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **parent.payload_invariants(payloads[(row_id, cost_bps)]),
            "validation_trial_id": VALIDATION_TRIAL_ID,
            "frozen_signal": True,
            "frozen_threshold": True,
            "frozen_instruments": True,
            "frozen_execution": True,
            "SPY_overnight_return_in_candidate": False
            if row_id == STRATEGY_ID
            else "not_applicable",
        }
        for row_id in (STRATEGY_ID, *CONTROL_IDS)
        for cost_bps in COST_BPS
    ]


def summary_lookup(
    rows: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    return {int(row["window_months"]): row for row in rows}


def decide(
    reproduction_pass: bool,
    invariants_pass: bool,
    payloads: dict[tuple[str, float], dict[str, Any]],
    full_rows: list[dict[str, Any]],
    halves: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    break_even: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    if not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "data_or_comparability_failure",
            "exploration_results_failed_1e_9_reproduction_gate",
            {"reproduction_pass": False},
        )
    if not invariants_pass:
        return (
            "validation_data_or_methodology_blocked",
            "methodology_failure",
            "one_or_more_timing_numeric_exposure_or_weight_invariants_failed",
            {"reproduction_pass": True, "all_invariants_pass": False},
        )
    full = {
        row["row_id"]: row
        for row in full_rows
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
    }
    half_primary = {
        (row["period_label"], row["row_id"]): row
        for row in halves
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
    }
    candidate = full[STRATEGY_ID]
    critical_dominators = [
        control_id
        for control_id in CRITICAL_CONTROL_IDS
        if dominates(full[control_id], candidate)
    ]
    material: dict[str, bool] = {}
    for control_id in CRITICAL_CONTROL_IDS:
        control = full[control_id]
        material[control_id] = bool(
            float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
            >= 0.02 - TOLERANCE
            or float(candidate["maximum_drawdown"])
            - float(control["maximum_drawdown"])
            >= 0.01 - TOLERANCE
        )
    first = half_primary[("first_chronological_half", STRATEGY_ID)]
    second = half_primary[("second_chronological_half", STRATEGY_ID)]
    roll = summary_lookup(rolling_summary)
    full_break_even = next(
        row
        for row in break_even
        if row["period_label"] == "full_period"
    )
    checks = {
        "reproduction_pass": reproduction_pass,
        "all_invariants_pass": invariants_pass,
        "full_period_5bps_total_return_positive": (
            float(candidate["total_return"]) > 0.0
        ),
        "full_period_5bps_cagr_positive": float(candidate["cagr"]) > 0.0,
        "first_half_5bps_total_return_and_sharpe_positive": (
            float(first["total_return"]) > 0.0
            and float(first["sharpe_ratio"]) > 0.0
        ),
        "second_half_5bps_total_return_and_sharpe_positive": (
            float(second["total_return"]) > 0.0
            and float(second["sharpe_ratio"]) > 0.0
        ),
        "critical_controls_dominating_full_period": critical_dominators,
        "no_critical_control_dominates_full_period": not critical_dominators,
        "material_advantage_by_critical_control": material,
        "material_advantage_over_both_critical_controls": all(
            material.values()
        ),
        "rolling_36_median_sharpe_positive": (
            float(roll[36]["median_candidate_sharpe_ratio"]) > 0.0
        ),
        "rolling_60_median_sharpe_positive": (
            float(roll[60]["median_candidate_sharpe_ratio"]) > 0.0
        ),
        "rolling_36_positive_return_fraction_over_half": (
            float(roll[36]["positive_candidate_total_return_fraction"]) > 0.5
        ),
        "rolling_60_positive_return_fraction_over_half": (
            float(roll[60]["positive_candidate_total_return_fraction"]) > 0.5
        ),
        "rolling_36_critical_domination_not_over_half": (
            float(roll[36]["any_critical_control_domination_fraction"]) <= 0.5
        ),
        "rolling_60_critical_domination_not_over_half": (
            float(roll[60]["any_critical_control_domination_fraction"]) <= 0.5
        ),
        "full_period_10bps_return_nonnegative": (
            metric_payload(payloads[(STRATEGY_ID, 10.0)])["total_return"]
            >= -TOLERANCE
        ),
        "full_period_break_even_at_least_10bps": (
            float(full_break_even["break_even_one_way_cost_bps"])
            >= 10.0 - TOLERANCE
        ),
        "result_not_concentrated_entirely_in_first_half": (
            float(second["total_return"]) > 0.0
            and float(second["sharpe_ratio"]) > 0.0
        ),
        "full_period_primary_metrics": {
            "total_return": candidate["total_return"],
            "cagr": candidate["cagr"],
            "sharpe_ratio": candidate["sharpe_ratio"],
            "maximum_drawdown": candidate["maximum_drawdown"],
        },
        "first_half_primary_metrics": {
            "total_return": first["total_return"],
            "sharpe_ratio": first["sharpe_ratio"],
        },
        "second_half_primary_metrics": {
            "total_return": second["total_return"],
            "sharpe_ratio": second["sharpe_ratio"],
        },
        "full_period_break_even_one_way_cost_bps": full_break_even[
            "break_even_one_way_cost_bps"
        ],
    }
    positive_requirements = [
        value
        for key, value in checks.items()
        if key
        in {
            "reproduction_pass",
            "all_invariants_pass",
            "full_period_5bps_total_return_positive",
            "full_period_5bps_cagr_positive",
            "first_half_5bps_total_return_and_sharpe_positive",
            "second_half_5bps_total_return_and_sharpe_positive",
            "no_critical_control_dominates_full_period",
            "material_advantage_over_both_critical_controls",
            "rolling_36_median_sharpe_positive",
            "rolling_60_median_sharpe_positive",
            "rolling_36_positive_return_fraction_over_half",
            "rolling_60_positive_return_fraction_over_half",
            "rolling_36_critical_domination_not_over_half",
            "rolling_60_critical_domination_not_over_half",
            "full_period_10bps_return_nonnegative",
            "full_period_break_even_at_least_10bps",
            "result_not_concentrated_entirely_in_first_half",
        }
    ]
    if all(bool(value) for value in positive_requirements):
        return (
            "validation_positive",
            "",
            "all_predeclared_validation_requirements_passed",
            checks,
        )
    failure_conditions = {
        "second_half_nonpositive": not checks[
            "second_half_5bps_total_return_and_sharpe_positive"
        ],
        "ten_bps_negative": not checks[
            "full_period_10bps_return_nonnegative"
        ],
        "break_even_below_ten": not checks[
            "full_period_break_even_at_least_10bps"
        ],
        "both_rolling_median_sharpes_nonpositive": (
            not checks["rolling_36_median_sharpe_positive"]
            and not checks["rolling_60_median_sharpe_positive"]
        ),
        "both_rolling_positive_return_fractions_not_over_half": (
            not checks["rolling_36_positive_return_fraction_over_half"]
            and not checks["rolling_60_positive_return_fraction_over_half"]
        ),
        "first_half_concentration": not checks[
            "result_not_concentrated_entirely_in_first_half"
        ],
        "critical_control_dominates_half_or_more_in_both_horizons": (
            not checks["rolling_36_critical_domination_not_over_half"]
            and not checks["rolling_60_critical_domination_not_over_half"]
        ),
    }
    checks["validation_failed_conditions"] = failure_conditions
    if any(failure_conditions.values()):
        if (
            failure_conditions["ten_bps_negative"]
            and failure_conditions["break_even_below_ten"]
        ):
            failure_reason = "cost_drag"
            decision_reason = (
                "full_period_return_is_negative_at_10bps_and_break_even_cost_is_below_10bps"
            )
        elif (
            failure_conditions["second_half_nonpositive"]
            or failure_conditions["first_half_concentration"]
        ):
            failure_reason = "period_instability"
            decision_reason = (
                "second_half_is_nonpositive_and_effect_is_concentrated_in_first_half"
            )
        else:
            failure_reason = "overfit_or_unstable"
            decision_reason = "rolling_window_stability_requirements_failed"
        return "validation_failed", failure_reason, decision_reason, checks
    return (
        "validation_mixed",
        "period_instability",
        "full_period_result_positive_but_stability_or_cost_evidence_conflicts",
        checks,
    )


def next_action_for(outcome: str) -> str:
    return {
        "validation_positive": (
            "direction_owner_review_ibs_paper_demo_eligibility_v1"
        ),
        "validation_mixed": "direction_owner_review_ibs_validation_mixed_v1",
        "validation_failed": (
            "direction_owner_review_close_ibs_after_validation_v1"
        ),
        "validation_data_or_methodology_blocked": (
            "direction_owner_review_ibs_validation_block_v1"
        ),
    }[outcome]


def report_text(
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    next_action: str,
    reproduction_pass: bool,
    checks: dict[str, Any],
) -> str:
    return f"""# Pagonidis IBS Next-Open Incremental Validation V1

## Scope

Exactly one frozen execution-portability strategy was validated as a child of
`{PARENT_TRIAL_ID}`. It remains an execution-portability test and is not an
exact source replication.

## Reproduction

- Parent exploration reproduction within `1e-9`: `{str(reproduction_pass).lower()}`
- Frozen signal, threshold, instruments, entry, exit, and zero-range behavior:
  unchanged.
- Mechanically fixed exposure-control fraction:
  `{EXPLORATION_ACTIVE_SESSIONS}/{EXPLORATION_ELIGIBLE_SESSIONS}`.

## Validation Evidence

- Full-period 5 bps total return:
  `{checks.get('full_period_primary_metrics', {}).get('total_return', '')}`
- Second-half 5 bps total return:
  `{checks.get('second_half_primary_metrics', {}).get('total_return', '')}`
- Second-half 5 bps Sharpe:
  `{checks.get('second_half_primary_metrics', {}).get('sharpe_ratio', '')}`
- Full-period break-even one-way cost:
  `{checks.get('full_period_break_even_one_way_cost_bps', '')}` bps
- Full-period return remains non-negative at 10 bps:
  `{checks.get('full_period_10bps_return_nonnegative', '')}`

All eligible rolling windows are retained. Chronological halves and rolling
windows are validation diagnostics, not clean or sealed holdouts.

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or 'none'}`

Decision basis: `{decision_reason}`

No promotion, lifecycle, or paper/demo decision is authorized by this packet.

## Exact Next Action

`{next_action}`

The next action was recorded and not executed.
"""


def run() -> dict[str, Any]:
    if not PARENT_EVIDENCE_DIR.exists():
        raise RuntimeError("Parent exploration evidence is missing")
    parent_manifest = yaml.safe_load(
        (PARENT_EVIDENCE_DIR / "batch_manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    if (
        parent_manifest.get("strategy_ids") != [STRATEGY_ID]
        or parent_manifest.get("outcome")
        != "exploratory_followup_candidate_standalone"
    ):
        raise RuntimeError("Parent exploration identity or outcome changed")

    protected_before = map_hashes(list(PROTECTED_STATE_PATHS))
    parent_before = tree_content_hash(PARENT_EVIDENCE_DIR)
    v5_before = tree_content_hash(V5_EVIDENCE_DIR)
    cache_before = tree_content_hash(CACHE_DIR)
    prior_before = tree_identity_hash(ROOT / "evidence", excluded=OUTPUT_DIR)

    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    try:
        payloads, _, _, _ = build_paths()
        data_ready = True
        data_error = ""
    except RuntimeError as exc:
        data_ready = False
        data_error = str(exc)
    clean_output()

    if data_ready:
        reproduction = reproduction_rows(payloads)
        reproduction_pass = bool(
            reproduction
            and all(row["reproduction_status"] == "pass" for row in reproduction)
        )
    else:
        reproduction = [
            {
                "scope": "data_preflight",
                "row_id": STRATEGY_ID,
                "cost_assumption_bps": "",
                "period_label": "full_period",
                "metric": "data_comparability",
                "expected_value": "pass",
                "actual_value": data_error,
                "absolute_difference": "",
                "tolerance": "exact",
                "comparison_basis": "exact_string",
                "reproduction_status": "fail",
            }
        ]
        reproduction_pass = False

    full_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    rolling: dict[int, list[dict[str, Any]]] = {
        months: [] for months in ROLLING_MONTHS
    }
    possible_counts = {months: 0 for months in ROLLING_MONTHS}
    rolling_summary: list[dict[str, Any]] = []
    break_even: list[dict[str, Any]] = []
    calendar: list[dict[str, Any]] = []
    stability: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    if reproduction_pass:
        full_rows, cost_rows = full_and_cost_rows(payloads)
        halves = half_rows(payloads)
        for months in ROLLING_MONTHS:
            rolling[months], possible_counts[months] = rolling_rows(
                payloads,
                months,
            )
        rolling_summary = rolling_summary_rows(rolling, possible_counts)
        break_even = break_even_rows(payloads)
        calendar = calendar_year_rows(payloads)
        stability = signal_stability_rows(payloads, break_even)
        turnover = turnover_rows(payloads)
        invariants = invariant_rows(payloads)
    invariants_pass = bool(
        reproduction_pass
        and invariants
        and all(row["invariant_pass"] for row in invariants)
    )
    if reproduction_pass:
        outcome, failure_reason, decision_reason, checks = decide(
            reproduction_pass,
            invariants_pass,
            payloads,
            full_rows,
            halves,
            rolling_summary,
            break_even,
        )
    else:
        outcome = "validation_data_or_methodology_blocked"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "exploration_results_failed_1e_9_reproduction_gate"
        checks = {
            "reproduction_pass": False,
            "all_invariants_pass": False,
            "data_error": data_error,
        }
    next_action = next_action_for(outcome)

    strategies = [strategy_row(outcome, failure_reason, next_action)]
    trials = [trial_row(outcome, failure_reason, next_action)]
    benchmarks = benchmark_rows()
    process = [process_row(outcome, next_action)]
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": VALIDATION_TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "stage": STAGE,
            "route": "standalone",
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "reproduction_pass": reproduction_pass,
            "all_invariants_pass": invariants_pass,
            "validation_checks": checks,
            "exact_source_replication_claimed": False,
            "exact_next_action": next_action,
            "next_action_executed": False,
        }
    ]
    failures = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": VALIDATION_TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "decision_reason": decision_reason,
                "exact_variant_affected": True,
                "family_closed_by_this_task": False,
            }
        ]
        if failure_reason
        else []
    )
    next_rows = [
        {
            "scope": "strategy",
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "scope": "validation_task",
            "strategy_id": "",
            "outcome": "task_completed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
    ]

    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategies,
        list(strategies[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trials,
        list(trials[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process,
        list(process[0]),
    )
    reproduction_fields = [
        "scope",
        "row_id",
        "cost_assumption_bps",
        "period_label",
        "metric",
        "expected_value",
        "actual_value",
        "absolute_difference",
        "tolerance",
        "comparison_basis",
        "reproduction_status",
    ]
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        reproduction_fields,
    )
    result_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "row_id",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        *RESULT_METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "full_period_results.csv",
        full_rows,
        result_fields,
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        halves,
        result_fields,
    )
    rolling_fields = [
        "window_months",
        "cost_assumption_bps",
        "window_start",
        "window_end",
        "trading_days",
        "active_signals",
        "minimum_active_signal_requirement",
        "candidate_total_return",
        "candidate_cagr",
        "candidate_annualized_volatility",
        "candidate_sharpe_ratio",
        "candidate_maximum_drawdown",
        "candidate_turnover",
        "candidate_transaction_cost_drag",
        "prior_negative_total_return",
        "prior_negative_cagr",
        "prior_negative_sharpe_ratio",
        "prior_negative_maximum_drawdown",
        "total_return_difference_vs_prior_negative",
        "cagr_difference_vs_prior_negative",
        "sharpe_difference_vs_prior_negative",
        "drawdown_difference_vs_prior_negative",
        "prior_negative_dominates_candidate",
        "exposure_matched_total_return",
        "exposure_matched_cagr",
        "exposure_matched_sharpe_ratio",
        "exposure_matched_maximum_drawdown",
        "total_return_difference_vs_exposure_matched",
        "cagr_difference_vs_exposure_matched",
        "sharpe_difference_vs_exposure_matched",
        "drawdown_difference_vs_exposure_matched",
        "exposure_matched_dominates_candidate",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "timing_invariant_status",
        "numeric_invariant_status",
        "weight_invariant_status",
        "exposure_invariant_status",
    ]
    for months in ROLLING_MONTHS:
        write_csv(
            OUTPUT_DIR / f"rolling_{months}_month_results.csv",
            rolling[months],
            rolling_fields,
        )
    rolling_summary_fields = [
        "window_months",
        "cost_assumption_bps",
        "possible_monthly_stepped_windows",
        "eligible_window_count",
        "excluded_below_25_active_signals",
        "median_candidate_total_return",
        "median_candidate_sharpe_ratio",
        "positive_candidate_total_return_fraction",
        "median_sharpe_difference_vs_prior_negative",
        "median_sharpe_difference_vs_exposure_matched",
        "prior_negative_domination_fraction",
        "exposure_matched_domination_fraction",
        "any_critical_control_domination_fraction",
        "all_unfavorable_eligible_windows_retained",
    ]
    write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary,
        rolling_summary_fields,
    )
    calendar_fields = [
        "calendar_year",
        "period_role",
        "evaluation_start",
        "evaluation_end",
        "active_signals",
        "gross_active_session_return",
        "net_active_session_return_at_5_bps",
        "profitable_signal_fraction",
        "total_one_way_turnover",
        "transaction_cost_drag",
        "threshold_changed_from_diagnostic",
    ]
    write_csv(
        OUTPUT_DIR / "calendar_year_results.csv",
        calendar,
        calendar_fields,
    )
    write_csv(
        OUTPUT_DIR / "cost_sensitivity_results.csv",
        cost_rows,
        result_fields,
    )
    break_even_fields = [
        "period_label",
        "period_role",
        "evaluation_start",
        "evaluation_end",
        "active_signals",
        "total_one_way_turnover",
        "return_at_zero_bps",
        "break_even_one_way_cost_bps",
        "root_residual_total_return",
        "root_finding_method",
        "root_finding_iterations",
        "threshold_or_strategy_optimized_from_root",
    ]
    write_csv(
        OUTPUT_DIR / "break_even_cost_results.csv",
        break_even,
        break_even_fields,
    )
    stability_fields = [
        "period_label",
        "period_role",
        "evaluation_start",
        "evaluation_end",
        "active_signals",
        "gross_return_before_cost",
        "net_return_0_bps",
        "net_return_2_5_bps",
        "net_return_5_bps",
        "net_return_7_5_bps",
        "net_return_10_bps",
        "net_returns_by_cost_json",
        "break_even_one_way_cost_bps",
        "average_gross_SPY_intraday_event_return",
        "median_gross_SPY_intraday_event_return",
        "threshold_changed_from_diagnostic",
    ]
    write_csv(
        OUTPUT_DIR / "signal_stability_diagnostics.csv",
        stability,
        stability_fields,
    )
    turnover_fields = [
        "row_id",
        "entity_type",
        "cost_assumption_bps",
        "turnover_formula",
        "separate_open_and_close_switches",
        "total_open_one_way_turnover",
        "total_close_one_way_turnover",
        "total_one_way_turnover",
        "open_entry_count",
        "close_exit_count",
        "transaction_cost_drag",
        "open_and_close_costs_netted_away",
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover,
        turnover_fields,
    )
    invariant_fields = [
        "row_id",
        "cost_assumption_bps",
        "numeric_invariant_status",
        "timing_invariant_status",
        "weight_invariant_status",
        "exposure_invariant_status",
        "no_signal_uses_post_close_information",
        "entry_at_next_regular_session_open",
        "exit_at_same_regular_session_close",
        "no_SPY_overnight_return_attributed",
        "every_intraday_entry_has_close_exit",
        "duplicate_trade_detected",
        "weights_nonnegative",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "costs_nonnegative",
        "both_switches_costed_when_positive_bps",
        "explicit_zero_weights_preserved",
        "stale_weight_forward_fill_used",
        "deterministic_schedule_and_accounting",
        "invariant_pass",
        "validation_trial_id",
        "frozen_signal",
        "frozen_threshold",
        "frozen_instruments",
        "frozen_execution",
        "SPY_overnight_return_in_candidate",
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariants,
        invariant_fields,
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "exact_variant_affected",
            "family_closed_by_this_task",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0]),
    )

    parent_after = tree_content_hash(PARENT_EVIDENCE_DIR)
    v5_after = tree_content_hash(V5_EVIDENCE_DIR)
    cache_after = tree_content_hash(CACHE_DIR)
    protected_after = map_hashes(list(PROTECTED_STATE_PATHS))
    prior_after = tree_identity_hash(ROOT / "evidence", excluded=OUTPUT_DIR)
    metadata_complete = all(
        row.get(field) not in ("", "unknown", "unmapped", None)
        for row in strategies + trials
        for field in (
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "strategy_architecture",
            "source_or_research_lineage",
            "instrument_universe",
            "parameters",
            "benchmark_or_control",
            "stage",
            "trial_id",
            "parent_trial_id",
            "adaptation_label",
            "outcome",
            "next_action",
        )
    )
    expected_before_final = REQUIRED_OUTPUTS - {
        "validation_manifest.yaml",
        "consistency_check.json",
        "validation_report.md",
    }
    present_before_final = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    consistency_passed = bool(
        outcome in ALLOWED_OUTCOMES
        and failure_reason in ALLOWED_FAILURE_REASONS
        and len(strategies) == len(trials) == len(process) == 1
        and len(benchmarks) == 4
        and strategies[0]["parent_trial_id"] == PARENT_TRIAL_ID
        and trials[0]["parent_trial_id"] == PARENT_TRIAL_ID
        and metadata_complete
        and parent_before == parent_after
        and v5_before == v5_after
        and cache_before == cache_after
        and protected_before == protected_after
        and prior_before == prior_after
        and expected_before_final.issubset(present_before_final)
        and not any(FORBIDDEN_ACTIONS.values())
    )
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "strategy_configuration_count": 1,
        "validation_trial_count": 1,
        "benchmark_reference_count": 4,
        "process_task_count": 1,
        "parent_trial_id": PARENT_TRIAL_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "reproduction_tolerance": REPRODUCTION_TOLERANCE,
        "rolling_windows_months": list(ROLLING_MONTHS),
        "minimum_rolling_active_signals": MIN_ROLLING_ACTIVE_SIGNALS,
        "frozen_exposure_control_fraction": FROZEN_EXPOSURE_FRACTION,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "exact_source_replication_claimed": False,
        "promotion_lifecycle_or_paper_demo_authorized": False,
    }
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "exactly_one_strategy_configuration": len(strategies) == 1,
        "exactly_one_validation_child_trial": len(trials) == 1,
        "parent_trial_preserved": trials[0]["parent_trial_id"]
        == PARENT_TRIAL_ID,
        "exactly_four_benchmark_references": len(benchmarks) == 4,
        "exactly_one_process_task": len(process) == 1,
        "required_metadata_complete": metadata_complete,
        "reproduction_pass": reproduction_pass,
        "reproduction_failure_count": sum(
            row["reproduction_status"] != "pass" for row in reproduction
        ),
        "all_invariants_pass": invariants_pass,
        "signal_threshold_instruments_and_execution_frozen": True,
        "exposure_control_fraction": FROZEN_EXPOSURE_FRACTION,
        "exposure_control_recomputed_by_validation_subperiod": False,
        "rolling_unfavorable_windows_omitted": False,
        "clean_or_sealed_holdout_claimed": False,
        "exact_source_replication_claimed": False,
        "parent_evidence_content_hash_before": parent_before,
        "parent_evidence_content_hash_after": parent_after,
        "parent_exploration_evidence_unchanged": parent_before == parent_after,
        "V5_evidence_content_hash_before": v5_before,
        "V5_evidence_content_hash_after": v5_after,
        "V5_evidence_unchanged": v5_before == v5_after,
        "cache_tree_content_hash_before": cache_before,
        "cache_tree_content_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_reconciliation_method": (
            "deterministic_path_size_mtime_identity_manifest"
        ),
        "prior_evidence_identity_hash_before": prior_before,
        "prior_evidence_identity_hash_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "deterministic_frozen_core_hash": deterministic_core_hash(),
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "validation_manifest.yaml", manifest)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "validation_report.md",
        report_text(
            outcome,
            failure_reason,
            decision_reason,
            next_action,
            reproduction_pass,
            checks,
        ),
    )
    final_files = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    if final_files != REQUIRED_OUTPUTS:
        raise RuntimeError(
            "Validation artifact mismatch: "
            f"missing={sorted(REQUIRED_OUTPUTS-final_files)}, "
            f"extra={sorted(final_files-REQUIRED_OUTPUTS)}"
        )
    if not consistency_passed:
        raise RuntimeError("Validation consistency check failed")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "reproduction_pass": reproduction_pass,
        "all_invariants_pass": invariants_pass,
        "evidence_dir": str(OUTPUT_DIR),
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
