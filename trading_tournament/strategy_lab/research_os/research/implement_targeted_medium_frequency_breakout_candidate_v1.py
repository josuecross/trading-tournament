from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    fast_price_volume_discovery_batch_v2 as market,
)
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as open_engine,
)


TASK_ID = "implement_targeted_medium_frequency_breakout_candidate_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "kaufman_pjk_lr_channel_breakout_spy_bil_v1"
FAMILY_ID = "projected_linear_regression_channel_breakout"
DISPLAY_NAME = "Kaufman PJK 40-Day Regression-Channel Breakout"
ARCHITECTURE = "long_only_projected_linear_regression_envelope_breakout"
SOURCE_RECORD_ID = "src_kaufman_pjk_lr_channel_breakout_spy_v1"
SOURCE_LINEAGE = (
    "targeted_medium_frequency_breakout_source_sprint_v1:"
    "src_kaufman_pjk_lr_channel_breakout_spy_v1"
)
TRIAL_ID = f"{TASK_ID}__canonical"
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

RULE_NUMBER = 2
PERIOD_SESSIONS = 40
WARMUP_SESSIONS = 41
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10

OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
PROTECTED_PATHS = open_engine.PROTECTED_PATHS

CONTROL_IDS = (
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
    "SPY_200_day_trend_control",
    "kaufman_pjk_slope_only_40_spy_bil_v1",
    "donchian_40_close_channel_spy_bil_v1",
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1",
)
CRITICAL_CONTROL_IDS = (
    "donchian_40_close_channel_spy_bil_v1",
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1",
)
PORTFOLIO_SLEEVES = (
    STRATEGY_ID,
    "donchian_40_close_channel_spy_bil_v1",
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1",
)
PORTFOLIO_IDS = {
    "reference": "100pct_frozen_reference",
    STRATEGY_ID: "80pct_reference_20pct_candidate",
    "donchian_40_close_channel_spy_bil_v1": (
        "80pct_reference_20pct_donchian_control"
    ),
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1": (
        "80pct_reference_20pct_exposure_matched_control"
    ),
}

NEXT_ADVANCE = "direction_owner_review_kaufman_channel_breakout_followup_v1"
NEXT_CLOSE = "targeted_defensive_cross_asset_state_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_kaufman_channel_breakout_block_v1"

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "channel_signal_diagnostics.csv",
    "trade_ledger.csv",
    "holding_period_diagnostics.csv",
    "open_execution_reconciliation.csv",
    "exposure_control_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}

RESULT_FIELDS = [
    "row_id",
    "entity_type",
    "stage",
    "cost_assumption_bps",
    "period_label",
    "period_role",
    *open_engine.METRIC_FIELDS,
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def frozen_rule() -> str:
    return (
        "TradingView Rule-2 semantics only: fit OLS to the latest 40 completed "
        "SPY adjusted closes; derive fitted_t and one-session slope; evaluate "
        "high/low deviations for i=0..40 against fitted_t-i*slope; project both "
        "bands one slope step. While in BIL enter SPY when completed close is "
        "strictly above the projected upper band; while in SPY exit to BIL when "
        "completed close is strictly below the projected lower band. Execute "
        "only at the next regular-session adjusted open."
    )


def source_row() -> dict[str, Any]:
    return {
        "source_record_id": SOURCE_RECORD_ID,
        "entity_type": "source_library_record",
        "stage": "source_extracted",
        "outcome": "feasible",
        "failure_reason": "",
        "implementation_authorized": True,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "strategy_id": STRATEGY_ID,
        "external_source_research_performed": False,
        "source_rule_completion_performed": False,
        "next_action": TASK_ID,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    }


def strategy_row(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "SPY|BIL",
        "parameters": {
            "rule": RULE_NUMBER,
            "period_sessions": PERIOD_SESSIONS,
            "price_source": "adjusted_close",
            "long_only": True,
            "use_futures": False,
            "warmup_sessions": WARMUP_SESSIONS,
            "regression_window": "latest_40_completed_closes",
            "deviation_window": "i_0_through_40_inclusive",
            "entry_comparison": "strictly_above",
            "exit_comparison": "strictly_below",
            "execution": "next_regular_session_open",
        },
        "benchmark_or_control": list(CONTROL_IDS),
        "route": "standalone",
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "frozen_rule": frozen_rule(),
        "exact_source_replication_claimed": False,
        "translation_label": "SPY_BIL_long_only_project_translation",
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }


def trial_row(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        **strategy_row(outcome, failure_reason, next_action),
        "entity_type": "experiment_trial",
        "source_rule_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "channel_contract_changed": False,
        "execution_changed": False,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "canonical_trial": True,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    rules = {
        "SPY_buy_and_hold": "Hold SPY throughout the identical period.",
        "BIL_buy_and_hold": "Hold BIL throughout the identical period.",
        "SPY_200_day_trend_control": (
            "SPY when completed close is above SMA200; BIL otherwise; next-open "
            "execution."
        ),
        "kaufman_pjk_slope_only_40_spy_bil_v1": (
            "SPY when the same 40-session OLS slope is positive; BIL when "
            "negative; retain state on equality; next-open execution."
        ),
        "donchian_40_close_channel_spy_bil_v1": (
            "While inactive enter above the maximum of the previous 40 closes; "
            "while active exit below the minimum of the previous 40 closes; "
            "strict comparisons and next-open execution."
        ),
        "kaufman_pjk_breakout_exposure_matched_spy_bil_v1": (
            "Monthly rebalance to the candidate full-period average target SPY "
            "weight; BIL receives the remainder; no optimization or rounding."
        ),
    }
    roles = {
        "SPY_buy_and_hold": "broad_benchmark",
        "BIL_buy_and_hold": "inactive_asset_control",
        "SPY_200_day_trend_control": "ordinary_trend_control",
        "kaufman_pjk_slope_only_40_spy_bil_v1": "regression_slope_control",
        "donchian_40_close_channel_spy_bil_v1": "same_purpose_control",
        "kaufman_pjk_breakout_exposure_matched_spy_bil_v1": (
            "mechanical_exposure_control"
        ),
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "benchmark_role": roles[control_id],
            "frozen_rule": rules[control_id],
            "instrument_universe": "SPY|BIL",
            "cost_assumptions_bps": list(COST_BPS),
            "same_purpose_half_gate_control": (
                control_id == "donchian_40_close_channel_spy_bil_v1"
            ),
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for control_id in CONTROL_IDS
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
        "provider_accessed": False,
        "next_action_executed": False,
    }


def write_preregistration() -> str:
    pending = "preregistered_pending_execution"
    pending_action = "execute_frozen_canonical_trial"
    records = {
        "source": [source_row()],
        "strategy": [strategy_row(pending, "", pending_action)],
        "trial": [trial_row(pending, "", pending_action)],
        "benchmarks": benchmark_rows(),
        "process": [process_row(pending, pending_action)],
    }
    file_map = {
        "source": "source_library_records.csv",
        "strategy": "strategy_cards.csv",
        "trial": "trial_ledger.csv",
        "benchmarks": "benchmark_reference_log.csv",
        "process": "process_task_log.csv",
    }
    for key, filename in file_map.items():
        rows = records[key]
        open_engine.write_csv(OUTPUT_DIR / filename, rows, list(rows[0]))
    return open_engine.canonical_hash({**records, "frozen_rule": frozen_rule()})


def load_preflight() -> tuple[pd.DataFrame, list[dict[str, Any]], bool]:
    panel, rows, passed = open_engine.load_preflight()
    if not passed:
        return panel, rows, passed
    enough = len(panel) >= WARMUP_SESSIONS
    for row in rows:
        row["required_fields"] = (
            "adjusted_open|adjusted_high|adjusted_low|adjusted_close|"
            "adjusted_volume|trading_date"
        )
        row["rule_2_warmup_available"] = enough
        row["network_accessed"] = False
        row["provider_accessed"] = False
        if not enough:
            row["candidate_preflight_status"] = "fail"
            row["failure_reason"] = "insufficient_41_session_channel_warmup"
    return panel, rows, bool(passed and enough)


def _event_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    fields = [
        "signal_date",
        "execution_date",
        "event_type",
        "signal_close",
        "sma200",
        "channel_low_7",
        "channel_high_7",
        "from_asset",
        "to_asset",
        "regression_fitted",
        "regression_slope",
        "projected_upper",
        "projected_lower",
    ]
    return pd.DataFrame(rows, columns=fields)


def regression_channel_values(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
) -> pd.DataFrame:
    index = pd.DatetimeIndex(close.index)
    result = pd.DataFrame(
        np.nan,
        index=index,
        columns=[
            "fitted_regression_value",
            "regression_slope",
            "upper_deviation",
            "lower_deviation",
            "projected_upper_band",
            "projected_lower_band",
            "channel_width",
            "breakout_distance",
        ],
    )
    x = np.arange(PERIOD_SESSIONS, dtype=float)
    centered = x - x.mean()
    denominator = float(np.dot(centered, centered))
    for position in range(WARMUP_SESSIONS - 1, len(index)):
        closes = close.iloc[
            position - PERIOD_SESSIONS + 1 : position + 1
        ].to_numpy(dtype=float)
        highs = high.iloc[
            position - PERIOD_SESSIONS : position + 1
        ].to_numpy(dtype=float)
        lows = low.iloc[
            position - PERIOD_SESSIONS : position + 1
        ].to_numpy(dtype=float)
        if not (
            np.isfinite(closes).all()
            and np.isfinite(highs).all()
            and np.isfinite(lows).all()
        ):
            continue
        slope = float(np.dot(centered, closes - closes.mean()) / denominator)
        intercept = float(closes.mean() - slope * x.mean())
        fitted = intercept + slope * (PERIOD_SESSIONS - 1)
        ages = np.arange(PERIOD_SESSIONS, -1, -1, dtype=float)
        baseline = fitted - ages * slope
        upper_deviation = float(np.max(highs - baseline))
        lower_deviation = float(np.max(baseline - lows))
        upper = fitted + slope + upper_deviation
        lower = fitted + slope - lower_deviation
        result.iloc[position] = [
            fitted,
            slope,
            upper_deviation,
            lower_deviation,
            upper,
            lower,
            upper - lower,
            float(close.iloc[position]) - upper,
        ]
    return result


def regression_channel_schedule(panel: pd.DataFrame) -> open_engine.Schedule:
    index = pd.DatetimeIndex(panel.index)
    close = panel[("SPY", "close")]
    values = regression_channel_values(
        close,
        panel[("SPY", "high")],
        panel[("SPY", "low")],
    )
    holding = "BIL"
    pending: str | None = None
    pending_event = ""
    targets: list[dict[str, float]] = []
    rebalance: list[bool] = []
    diagnostics: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for position, day in enumerate(index):
        executed_event = pending_event
        if pending is not None:
            holding = pending
            pending = None
            pending_event = ""
        targets.append(
            {
                "SPY": 1.0 if holding == "SPY" else 0.0,
                "BIL": 1.0 if holding == "BIL" else 0.0,
            }
        )
        rebalance.append(position == 0 or bool(executed_event))
        row = values.loc[day]
        available = bool(row.notna().all())
        entry = bool(
            available
            and holding == "BIL"
            and close.loc[day] > row["projected_upper_band"]
        )
        exit_signal = bool(
            available
            and holding == "SPY"
            and close.loc[day] < row["projected_lower_band"]
        )
        signal = "entry" if entry else "exit" if exit_signal else "none"
        next_day = index[position + 1] if position + 1 < len(index) else None
        status = (
            "signal_unavailable_retain_holding"
            if not available
            else "scheduled_next_open"
            if signal != "none" and next_day is not None
            else "terminal_unexecuted"
            if signal != "none"
            else "no_signal"
        )
        if signal != "none" and next_day is not None:
            target_asset = "SPY" if signal == "entry" else "BIL"
            events.append(
                {
                    "signal_date": day,
                    "execution_date": next_day,
                    "event_type": signal,
                    "signal_close": float(close.loc[day]),
                    "sma200": "",
                    "channel_low_7": "",
                    "channel_high_7": "",
                    "from_asset": holding,
                    "to_asset": target_asset,
                    "regression_fitted": float(
                        row["fitted_regression_value"]
                    ),
                    "regression_slope": float(row["regression_slope"]),
                    "projected_upper": float(row["projected_upper_band"]),
                    "projected_lower": float(row["projected_lower_band"]),
                }
            )
            pending = target_asset
            pending_event = signal
        diagnostics.append(
            {
                "date": day,
                "fitted_regression_value": (
                    float(row["fitted_regression_value"]) if available else ""
                ),
                "regression_slope": (
                    float(row["regression_slope"]) if available else ""
                ),
                "upper_deviation": (
                    float(row["upper_deviation"]) if available else ""
                ),
                "lower_deviation": (
                    float(row["lower_deviation"]) if available else ""
                ),
                "projected_upper_band": (
                    float(row["projected_upper_band"]) if available else ""
                ),
                "projected_lower_band": (
                    float(row["projected_lower_band"]) if available else ""
                ),
                "channel_width": float(row["channel_width"]) if available else "",
                "breakout_distance": (
                    float(row["breakout_distance"]) if available else ""
                ),
                "adjusted_close": float(close.loc[day]),
                "current_state": holding,
                "entry_signal": entry,
                "exit_signal": exit_signal,
                "intended_execution_date": (
                    next_day if signal != "none" and next_day is not None else ""
                ),
                "execution_status": status,
                "regression_input_count": PERIOD_SESSIONS if available else 0,
                "deviation_input_count": WARMUP_SESSIONS if available else 0,
                "rule_number": RULE_NUMBER,
                "channel_contract": "TradingView_Rule_2_only",
                "strict_entry_comparison": True,
                "strict_exit_comparison": True,
                "same_close_fill_allowed": False,
            }
        )
    return open_engine.Schedule(
        targets=pd.DataFrame(targets, index=index),
        rebalance=pd.Series(rebalance, index=index, dtype=bool),
        diagnostics=pd.DataFrame(diagnostics),
        events=_event_frame(events),
    )


def state_schedule(
    index: pd.DatetimeIndex,
    desired_by_day: pd.Series,
    close: pd.Series,
    diagnostic_name: str,
) -> open_engine.Schedule:
    holding = "BIL"
    pending: str | None = None
    pending_event = ""
    targets: list[dict[str, float]] = []
    flags: list[bool] = []
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for position, day in enumerate(index):
        executed = pending_event
        if pending is not None:
            holding = pending
            pending = None
            pending_event = ""
        targets.append(
            {
                "SPY": 1.0 if holding == "SPY" else 0.0,
                "BIL": 1.0 if holding == "BIL" else 0.0,
            }
        )
        flags.append(position == 0 or bool(executed))
        desired = desired_by_day.loc[day]
        event_type = ""
        next_day = index[position + 1] if position + 1 < len(index) else None
        if isinstance(desired, str) and desired in {"SPY", "BIL"}:
            if desired != holding and next_day is not None:
                event_type = "entry" if desired == "SPY" else "exit"
                events.append(
                    {
                        "signal_date": day,
                        "execution_date": next_day,
                        "event_type": event_type,
                        "signal_close": float(close.loc[day]),
                        "sma200": "",
                        "channel_low_7": "",
                        "channel_high_7": "",
                        "from_asset": holding,
                        "to_asset": desired,
                        "regression_fitted": "",
                        "regression_slope": "",
                        "projected_upper": "",
                        "projected_lower": "",
                    }
                )
                pending = desired
                pending_event = event_type
        diagnostics.append(
            {
                "date": day,
                "control": diagnostic_name,
                "desired_asset": desired if isinstance(desired, str) else "",
                "holding_at_signal_close": holding,
                "signal_type": event_type or "none",
            }
        )
    return open_engine.Schedule(
        pd.DataFrame(targets, index=index),
        pd.Series(flags, index=index, dtype=bool),
        pd.DataFrame(diagnostics),
        _event_frame(events),
    )


def slope_only_schedule(panel: pd.DataFrame) -> open_engine.Schedule:
    close = panel[("SPY", "close")]
    high = panel[("SPY", "high")]
    low = panel[("SPY", "low")]
    slopes = regression_channel_values(close, high, low)["regression_slope"]
    desired = pd.Series("", index=panel.index, dtype=object)
    desired.loc[slopes > 0.0] = "SPY"
    desired.loc[slopes < 0.0] = "BIL"
    return state_schedule(
        pd.DatetimeIndex(panel.index),
        desired,
        close,
        "same_40_session_regression_slope",
    )


def donchian_schedule(panel: pd.DataFrame) -> open_engine.Schedule:
    index = pd.DatetimeIndex(panel.index)
    close = panel[("SPY", "close")]
    prior_high = close.shift(1).rolling(
        PERIOD_SESSIONS, min_periods=PERIOD_SESSIONS
    ).max()
    prior_low = close.shift(1).rolling(
        PERIOD_SESSIONS, min_periods=PERIOD_SESSIONS
    ).min()
    holding = "BIL"
    pending: str | None = None
    pending_event = ""
    targets: list[dict[str, float]] = []
    flags: list[bool] = []
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for position, day in enumerate(index):
        executed = pending_event
        if pending is not None:
            holding = pending
            pending = None
            pending_event = ""
        targets.append(
            {
                "SPY": 1.0 if holding == "SPY" else 0.0,
                "BIL": 1.0 if holding == "BIL" else 0.0,
            }
        )
        flags.append(position == 0 or bool(executed))
        available = pd.notna(prior_high.loc[day]) and pd.notna(prior_low.loc[day])
        entry = bool(
            available and holding == "BIL" and close.loc[day] > prior_high.loc[day]
        )
        exit_signal = bool(
            available and holding == "SPY" and close.loc[day] < prior_low.loc[day]
        )
        event_type = "entry" if entry else "exit" if exit_signal else ""
        next_day = index[position + 1] if position + 1 < len(index) else None
        if event_type and next_day is not None:
            desired = "SPY" if event_type == "entry" else "BIL"
            events.append(
                {
                    "signal_date": day,
                    "execution_date": next_day,
                    "event_type": event_type,
                    "signal_close": float(close.loc[day]),
                    "sma200": "",
                    "channel_low_7": float(prior_low.loc[day]),
                    "channel_high_7": float(prior_high.loc[day]),
                    "from_asset": holding,
                    "to_asset": desired,
                    "regression_fitted": "",
                    "regression_slope": "",
                    "projected_upper": "",
                    "projected_lower": "",
                }
            )
            pending = desired
            pending_event = event_type
        diagnostics.append(
            {
                "date": day,
                "prior_40_close_high": (
                    float(prior_high.loc[day]) if available else ""
                ),
                "prior_40_close_low": (
                    float(prior_low.loc[day]) if available else ""
                ),
                "holding_at_signal_close": holding,
                "signal_type": event_type or "none",
            }
        )
    return open_engine.Schedule(
        pd.DataFrame(targets, index=index),
        pd.Series(flags, index=index, dtype=bool),
        pd.DataFrame(diagnostics),
        _event_frame(events),
    )


def trade_ledger(
    panel: pd.DataFrame,
    schedule: open_engine.Schedule,
) -> list[dict[str, Any]]:
    events = schedule.events
    if events.empty:
        return []
    index = pd.DatetimeIndex(panel.index)
    positions = {day: position for position, day in enumerate(index)}
    rows: list[dict[str, Any]] = []
    entry: dict[str, Any] | None = None
    for _, event_row in events.iterrows():
        event = event_row.to_dict()
        if event["event_type"] == "entry":
            if entry is not None:
                raise RuntimeError("Entry occurred while regression channel was long")
            entry = event
            continue
        if entry is None:
            raise RuntimeError("Exit occurred while regression channel was inactive")
        entry_day = pd.Timestamp(entry["execution_date"])
        exit_day = pd.Timestamp(event["execution_date"])
        entry_pos = positions[entry_day]
        exit_pos = positions[exit_day]
        entry_open = float(panel.loc[entry_day, ("SPY", "open")])
        exit_open = float(panel.loc[exit_day, ("SPY", "open")])
        held = index[entry_pos:exit_pos]
        highs = np.append(
            panel.loc[held, ("SPY", "high")].to_numpy(dtype=float), exit_open
        )
        lows = np.append(
            panel.loc[held, ("SPY", "low")].to_numpy(dtype=float), exit_open
        )
        rows.append(
            trade_row(
                entry,
                event,
                entry_open,
                exit_open,
                exit_open / entry_open - 1.0,
                max(1, exit_pos - entry_pos),
                float(highs.max() / entry_open - 1.0),
                float(lows.min() / entry_open - 1.0),
                False,
            )
        )
        entry = None
    if entry is not None:
        entry_day = pd.Timestamp(entry["execution_date"])
        entry_pos = positions[entry_day]
        entry_open = float(panel.loc[entry_day, ("SPY", "open")])
        held = index[entry_pos:]
        terminal_close = float(panel.loc[index[-1], ("SPY", "close")])
        rows.append(
            trade_row(
                entry,
                None,
                entry_open,
                "",
                terminal_close / entry_open - 1.0,
                len(held),
                float(
                    panel.loc[held, ("SPY", "high")].max() / entry_open - 1.0
                ),
                float(
                    panel.loc[held, ("SPY", "low")].min() / entry_open - 1.0
                ),
                True,
            )
        )
    return rows


def trade_row(
    entry: dict[str, Any],
    exit_event: dict[str, Any] | None,
    entry_open: float,
    exit_open: float | str,
    gross: float,
    holding_sessions: int,
    mfe: float,
    mae: float,
    terminal_open: bool,
) -> dict[str, Any]:
    switches = 1 if terminal_open else 2
    net = {
        cost: (1.0 + gross) * (1.0 - cost / 10000.0) ** switches - 1.0
        for cost in COST_BPS
    }
    return {
        "entry_signal_date": entry["signal_date"],
        "entry_execution_date": entry["execution_date"],
        "entry_open": entry_open,
        "entry_projected_upper_band": entry["projected_upper"],
        "exit_signal_date": exit_event["signal_date"] if exit_event else "",
        "exit_execution_date": exit_event["execution_date"] if exit_event else "",
        "exit_open": exit_open,
        "exit_projected_lower_band": (
            exit_event["projected_lower"] if exit_event else ""
        ),
        "gross_trade_return": gross,
        "net_trade_return_0_bps": net[0.0],
        "net_trade_return_5_bps": net[5.0],
        "net_trade_return_10_bps": net[10.0],
        "holding_sessions": holding_sessions,
        "maximum_favorable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "exit_reason": (
            "open_at_evaluation_end"
            if terminal_open
            else "strict_projected_lower_band_break"
        ),
        "terminal_open_status": terminal_open,
    }


def holding_diagnostics(
    trades: list[dict[str, Any]],
    payload: dict[str, Any],
    diagnostics: pd.DataFrame,
) -> list[dict[str, Any]]:
    completed = [row for row in trades if not row["terminal_open_status"]]
    holdings = [int(row["holding_sessions"]) for row in completed]
    net = [float(row["net_trade_return_5_bps"]) for row in completed]
    eligible = diagnostics.loc[diagnostics["regression_input_count"] == PERIOD_SESSIONS]
    slopes = pd.to_numeric(eligible["regression_slope"], errors="coerce").dropna()
    widths = pd.to_numeric(eligible["channel_width"], errors="coerce").dropna()
    distances = pd.to_numeric(
        eligible["breakout_distance"], errors="coerce"
    ).dropna()
    entries = sorted(pd.Timestamp(row["entry_execution_date"]) for row in trades)
    index = pd.DatetimeIndex(payload["returns"].index)
    positions = {day: i for i, day in enumerate(index)}
    boundaries = [index[0], *entries, index[-1]]
    inactive_gaps = [
        positions[right] - positions[left]
        for left, right in zip(boundaries[:-1], boundaries[1:])
    ]
    return [
        {
            "record_type": "full_period_summary",
            "calendar_year": "",
            "entry_count": len(trades),
            "exit_count": len(completed),
            "completed_trades": len(completed),
            "terminal_open_trades": len(trades) - len(completed),
            "average_holding_sessions": (
                float(np.mean(holdings)) if holdings else ""
            ),
            "median_holding_sessions": (
                float(np.median(holdings)) if holdings else ""
            ),
            "maximum_holding_sessions": max(holdings) if holdings else "",
            "winning_trade_fraction_5_bps": (
                float(np.mean(np.asarray(net) > 0.0)) if net else ""
            ),
            "whipsaw_count": sum(
                holding <= 5 and value <= 0.0
                for holding, value in zip(holdings, net)
            ),
            "whipsaw_definition": (
                "completed_trade_holding_at_most_5_sessions_and_net_5bps_nonpositive"
            ),
            "trades_per_year": (
                len(trades)
                / max(
                    1.0,
                    (index[-1] - index[0]).days / 365.2425,
                )
            ),
            "longest_inactive_period_sessions": (
                max(inactive_gaps) if inactive_gaps else len(index)
            ),
            "average_SPY_exposure": float(payload["target_spy"].mean()),
            "slope_min": float(slopes.min()) if len(slopes) else "",
            "slope_median": float(slopes.median()) if len(slopes) else "",
            "slope_max": float(slopes.max()) if len(slopes) else "",
            "channel_width_min": float(widths.min()) if len(widths) else "",
            "channel_width_median": float(widths.median()) if len(widths) else "",
            "channel_width_max": float(widths.max()) if len(widths) else "",
            "breakout_distance_min": (
                float(distances.min()) if len(distances) else ""
            ),
            "breakout_distance_median": (
                float(distances.median()) if len(distances) else ""
            ),
            "breakout_distance_max": (
                float(distances.max()) if len(distances) else ""
            ),
        },
        *[
            {
                "record_type": "calendar_year",
                "calendar_year": year,
                "entry_count": sum(
                    pd.Timestamp(row["entry_execution_date"]).year == year
                    for row in trades
                ),
                "exit_count": sum(
                    bool(row["exit_execution_date"])
                    and pd.Timestamp(row["exit_execution_date"]).year == year
                    for row in trades
                ),
                "completed_trades": "",
                "terminal_open_trades": "",
                "average_holding_sessions": "",
                "median_holding_sessions": "",
                "maximum_holding_sessions": "",
                "winning_trade_fraction_5_bps": "",
                "whipsaw_count": "",
                "whipsaw_definition": "",
                "trades_per_year": "",
                "longest_inactive_period_sessions": "",
                "average_SPY_exposure": float(
                    payload["target_spy"].loc[index.year == year].mean()
                ),
                "slope_min": "",
                "slope_median": "",
                "slope_max": "",
                "channel_width_min": "",
                "channel_width_median": "",
                "channel_width_max": "",
                "breakout_distance_min": "",
                "breakout_distance_median": "",
                "breakout_distance_max": "",
            }
            for year in sorted(set(index.year))
        ],
    ]


def run_standalone(
    panel: pd.DataFrame,
) -> tuple[
    dict[tuple[str, float], dict[str, Any]],
    dict[str, open_engine.Schedule],
    float,
    bool,
]:
    index = pd.DatetimeIndex(panel.index)
    close = panel[("SPY", "close")]
    candidate = regression_channel_schedule(panel)
    preliminary = open_engine.simulate(
        STRATEGY_ID, panel, candidate, PRIMARY_COST_BPS
    )
    exposure = float(preliminary["target_spy"].mean())
    schedules = {
        STRATEGY_ID: candidate,
        "SPY_buy_and_hold": open_engine.static_schedule(index, 1.0),
        "BIL_buy_and_hold": open_engine.static_schedule(index, 0.0),
        "SPY_200_day_trend_control": open_engine.regime_schedule(
            close, "price_sma200"
        ),
        "kaufman_pjk_slope_only_40_spy_bil_v1": slope_only_schedule(panel),
        "donchian_40_close_channel_spy_bil_v1": donchian_schedule(panel),
        "kaufman_pjk_breakout_exposure_matched_spy_bil_v1": (
            open_engine.monthly_exposure_schedule(index, exposure)
        ),
    }
    results = {
        (row_id, cost): open_engine.simulate(row_id, panel, schedule, cost)
        for row_id, schedule in schedules.items()
        for cost in COST_BPS
    }
    repeat = open_engine.simulate(
        STRATEGY_ID, panel, candidate, PRIMARY_COST_BPS
    )
    deterministic = (
        repeat["state_hash"] == results[(STRATEGY_ID, PRIMARY_COST_BPS)]["state_hash"]
    )
    return results, schedules, exposure, deterministic


def outer_start_weights(
    reference: pd.Series,
    sleeve: pd.Series,
) -> pd.Series:
    returns = pd.concat(
        [reference.rename("reference"), sleeve.rename("sleeve")],
        axis=1,
        join="inner",
    ).dropna()
    weights = np.array([0.0, 0.0], dtype=float)
    starts: list[float] = []
    for position, values in enumerate(returns.to_numpy(dtype=float)):
        starts.append(float(weights[1]))
        drifted = weights * (1.0 + values)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else weights.copy()
        is_month_start = position == 0 or (
            returns.index[position - 1].to_period("M")
            != returns.index[position].to_period("M")
        )
        weights = np.array([0.8, 0.2]) if is_month_start else pretrade
    return pd.Series(starts, index=returns.index, name="outer_sleeve_start_weight")


def portfolio_rows(
    results: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    reference_all = market.active_vm_dsr_usci_reference_returns()
    rows: list[dict[str, Any]] = []
    for cost in COST_BPS:
        candidate_index = results[(STRATEGY_ID, cost)]["returns"].index
        reference = reference_all.reindex(candidate_index).dropna()
        reference_payload = portfolio_accounting.reference_payload(reference, cost)
        metrics = portfolio_accounting.metric_payload(reference_payload)
        rows.append(
            {
                "portfolio_id": PORTFOLIO_IDS["reference"],
                "entity_type": "portfolio_diagnostic",
                "stage": STAGE,
                "cost_assumption_bps": cost,
                "construction": "100pct_frozen_reference",
                "daily_fixed_weight_return_blend_used": False,
                "inner_sleeve_turnover": 0.0,
                "outer_monthly_turnover": 0.0,
                "combined_turnover_diagnostic": 0.0,
                **metrics,
                "inner_sleeve_transaction_cost_drag": 0.0,
                "outer_transaction_cost_drag": 0.0,
                "transaction_cost_drag": 0.0,
            }
        )
        for sleeve_id in PORTFOLIO_SLEEVES:
            sleeve_payload = results[(sleeve_id, cost)]
            sleeve = sleeve_payload["returns"].reindex(reference.index).dropna()
            aligned_reference = reference.reindex(sleeve.index).dropna()
            sleeve = sleeve.reindex(aligned_reference.index)
            portfolio_id = PORTFOLIO_IDS[sleeve_id]
            payload = portfolio_accounting.simulate_two_component_portfolio(
                aligned_reference,
                sleeve,
                portfolio_id,
                cost,
            )
            metrics = portfolio_accounting.metric_payload(payload)
            outer_weights = outer_start_weights(aligned_reference, sleeve)
            inner_turnover = float(
                (
                    outer_weights
                    * sleeve_payload["turnover"].reindex(outer_weights.index).fillna(0.0)
                ).sum()
            )
            inner_cost = float(
                (
                    outer_weights
                    * sleeve_payload["cost"].reindex(outer_weights.index).fillna(0.0)
                ).sum()
            )
            outer_turnover = float(payload["turnover"].sum())
            outer_cost = float(payload["cost"].sum())
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "entity_type": "portfolio_diagnostic",
                    "stage": STAGE,
                    "cost_assumption_bps": cost,
                    "construction": (
                        "monthly_rebalanced_80pct_reference_plus_20pct_explicit_"
                        "strategy_sleeve_with_natural_drift"
                    ),
                    "sleeve_id": sleeve_id,
                    "daily_fixed_weight_return_blend_used": False,
                    "inner_sleeve_turnover": inner_turnover,
                    "outer_monthly_turnover": outer_turnover,
                    "combined_turnover_diagnostic": inner_turnover + outer_turnover,
                    **metrics,
                    "inner_sleeve_transaction_cost_drag": inner_cost,
                    "outer_transaction_cost_drag": outer_cost,
                    "transaction_cost_drag": inner_cost + outer_cost,
                }
            )
    return rows


def decide_outcome(
    results: dict[tuple[str, float], dict[str, Any]],
    halves: dict[str, pd.DatetimeIndex],
    invariant_pass: bool,
) -> tuple[str, str, str, dict[str, bool]]:
    candidate = open_engine.metric_payload(
        results[(STRATEGY_ID, PRIMARY_COST_BPS)]
    )
    controls = {
        control: open_engine.metric_payload(
            results[(control, PRIMARY_COST_BPS)]
        )
        for control in CONTROL_IDS
    }
    not_dominated = all(
        not open_engine.control_dominates(candidate, controls[control])
        for control in CRITICAL_CONTROL_IDS
    )
    material = all(
        open_engine.material_advantage(candidate, controls[control])
        for control in CRITICAL_CONTROL_IDS
    )
    half_stability = True
    five_trades_each_half = True
    for period_index in halves.values():
        candidate_half = open_engine.metric_payload(
            results[(STRATEGY_ID, PRIMARY_COST_BPS)], period_index
        )
        five_trades_each_half = (
            five_trades_each_half
            and int(candidate_half["completed_trade_count"]) >= 5
        )
        for control in CRITICAL_CONTROL_IDS:
            control_half = open_engine.metric_payload(
                results[(control, PRIMARY_COST_BPS)], period_index
            )
            half_stability = half_stability and not open_engine.worse_on_both(
                candidate_half, control_half
            )
    trend_not_replicated = all(
        not open_engine.economically_replicated(candidate, controls[control])
        for control in (
            "kaufman_pjk_slope_only_40_spy_bil_v1",
            "SPY_200_day_trend_control",
        )
    )
    candidate_10 = open_engine.metric_payload(results[(STRATEGY_ID, 10.0)])
    cost_robust = all(
        not open_engine.worse_on_both(
            candidate_10,
            open_engine.metric_payload(results[(control, 10.0)]),
        )
        for control in CRITICAL_CONTROL_IDS
    )
    gates = {
        "positive_full_period_after_cost_return": candidate["total_return"] > 0.0,
        "all_invariants_pass": invariant_pass,
        "critical_controls_do_not_dominate": not_dominated,
        "material_advantage_vs_each_critical_control": material,
        "chronological_half_stability_vs_critical_controls": half_stability,
        "slope_and_ordinary_trend_do_not_replicate": trend_not_replicated,
        "advantage_not_unfavorable_on_both_metrics_at_10bps": cost_robust,
        "at_least_five_completed_trades_in_each_half": five_trades_each_half,
    }
    if all(gates.values()):
        return (
            "exploratory_followup_candidate_standalone",
            "",
            NEXT_ADVANCE,
            gates,
        )
    if not gates["all_invariants_pass"]:
        return "blocked_feasibility", "methodology_failure", NEXT_BLOCK, gates
    if not gates["positive_full_period_after_cost_return"]:
        reason = "weak_return"
    elif not gates["at_least_five_completed_trades_in_each_half"]:
        reason = "signal_scarcity"
    elif not gates["chronological_half_stability_vs_critical_controls"]:
        reason = "period_instability"
    elif not gates["advantage_not_unfavorable_on_both_metrics_at_10bps"]:
        reason = "cost_drag"
    elif not gates["slope_and_ordinary_trend_do_not_replicate"]:
        reason = "benchmark_like_behavior"
    elif not gates["critical_controls_do_not_dominate"]:
        reason = "weak_vs_primary_control"
    else:
        reason = "exposure_control_explanation"
    return "closed_exploration", reason, NEXT_CLOSE, gates


def rows_with_fields(
    rows: list[dict[str, Any]],
    leading: list[str],
) -> list[str]:
    return open_engine.rows_with_fields(rows, leading)


def run() -> dict[str, Any]:
    clean_output()
    protected_before = {
        rel(path): open_engine.file_hash(path) for path in PROTECTED_PATHS
    }
    cache_before = open_engine.tree_hash(CACHE_DIR)
    prior_evidence_before = open_engine.tree_hash(
        ROOT / "evidence", OUTPUT_DIR.parent
    )
    preregistration_hash = write_preregistration()

    panel, preflight_rows, preflight_pass = load_preflight()
    open_engine.write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        rows_with_fields(preflight_rows, ["symbol"]),
    )

    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    open_rows: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    gates: dict[str, bool] = {}
    exposure_weight: float | str = ""
    deterministic = False

    if not preflight_pass:
        outcome = "inconclusive_data_issue"
        failure_reason = "data_or_comparability_failure"
        next_action = NEXT_BLOCK
    else:
        results, schedules, exposure_weight, deterministic = run_standalone(panel)
        index = pd.DatetimeIndex(panel.index)
        halves = open_engine.split_halves(index)
        all_invariants = all(
            open_engine.payload_invariants(payload)["invariant_pass"]
            for payload in results.values()
        ) and deterministic
        outcome, failure_reason, next_action, gates = decide_outcome(
            results, halves, all_invariants
        )
        candidate_rows = [
            open_engine.result_row(
                STRATEGY_ID,
                results[(STRATEGY_ID, cost)],
                "full_period",
            )
            for cost in COST_BPS
        ]
        control_rows = [
            open_engine.result_row(
                control,
                results[(control, cost)],
                "full_period",
            )
            for control in CONTROL_IDS
            for cost in COST_BPS
        ]
        half_rows = [
            open_engine.result_row(
                row_id,
                results[(row_id, PRIMARY_COST_BPS)],
                period,
                period_index,
            )
            for row_id in (STRATEGY_ID, *CONTROL_IDS)
            for period, period_index in halves.items()
        ]
        contribution_rows = portfolio_rows(results)
        signal_rows = schedules[STRATEGY_ID].diagnostics.to_dict("records")
        trade_rows = trade_ledger(panel, schedules[STRATEGY_ID])
        holding_rows = holding_diagnostics(
            trade_rows,
            results[(STRATEGY_ID, PRIMARY_COST_BPS)],
            schedules[STRATEGY_ID].diagnostics,
        )
        open_rows = (
            results[(STRATEGY_ID, PRIMARY_COST_BPS)]["daily"]
            .reset_index(drop=True)
            .to_dict("records")
        )
        exposure_rows = [
            {
                "cost_assumption_bps": cost,
                "candidate_full_period_average_target_SPY_weight": exposure_weight,
                "control_SPY_weight": exposure_weight,
                "control_BIL_weight": 1.0 - float(exposure_weight),
                "rebalance_frequency": "monthly",
                "optimized_or_rounded": False,
                "performance_selected": False,
                "matches_candidate_target_exposure": True,
                "strategy_variant": False,
            }
            for cost in COST_BPS
        ]
        for (row_id, cost), payload in results.items():
            invariant = open_engine.payload_invariants(payload)
            events = payload["schedule"].events
            alternating = bool(
                events.empty
                or not events["event_type"].eq(
                    events["event_type"].shift(1)
                ).any()
            )
            turnover_rows.append(
                {
                    "row_id": row_id,
                    "cost_assumption_bps": cost,
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "total_one_way_turnover": float(payload["turnover"].sum()),
                    "reported_cost_drag": float(payload["cost"].sum()),
                    "transaction_cost_charged_once": invariant[
                        "transaction_costs_charged_once"
                    ],
                    "initial_allocation_included": True,
                    "cost_diagnostic_is_strategy_variant": False,
                }
            )
            invariant_rows.append(
                {
                    "row_id": row_id,
                    "cost_assumption_bps": cost,
                    **invariant,
                    "regression_inputs_completed_sessions_only": True,
                    "channel_inputs_no_future_values": True,
                    "no_duplicate_entry_while_long": alternating,
                    "no_exit_while_inactive": alternating,
                    "serial_rerun_deterministic": (
                        deterministic if row_id == STRATEGY_ID else True
                    ),
                }
            )

    final_records = {
        "source_library_records.csv": [source_row()],
        "strategy_cards.csv": [
            strategy_row(outcome, failure_reason, next_action)
        ],
        "trial_ledger.csv": [trial_row(outcome, failure_reason, next_action)],
        "benchmark_reference_log.csv": benchmark_rows(),
        "process_task_log.csv": [process_row(outcome, next_action)],
    }
    for filename, rows in final_records.items():
        open_engine.write_csv(OUTPUT_DIR / filename, rows, list(rows[0]))

    open_engine.write_csv(
        OUTPUT_DIR / "all_trial_results.csv", candidate_rows, RESULT_FIELDS
    )
    open_engine.write_csv(
        OUTPUT_DIR / "control_results.csv", control_rows, RESULT_FIELDS
    )
    open_engine.write_csv(
        OUTPUT_DIR / "chronological_half_results.csv", half_rows, RESULT_FIELDS
    )
    open_engine.write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        contribution_rows,
        rows_with_fields(
            contribution_rows,
            ["portfolio_id", "cost_assumption_bps"],
        ),
    )
    signal_fields = [
        "date",
        "fitted_regression_value",
        "regression_slope",
        "upper_deviation",
        "lower_deviation",
        "projected_upper_band",
        "projected_lower_band",
        "channel_width",
        "breakout_distance",
        "adjusted_close",
        "current_state",
        "entry_signal",
        "exit_signal",
        "intended_execution_date",
        "execution_status",
        "regression_input_count",
        "deviation_input_count",
        "rule_number",
        "channel_contract",
        "strict_entry_comparison",
        "strict_exit_comparison",
        "same_close_fill_allowed",
    ]
    open_engine.write_csv(
        OUTPUT_DIR / "channel_signal_diagnostics.csv",
        signal_rows,
        signal_fields,
    )
    trade_fields = [
        "entry_signal_date",
        "entry_execution_date",
        "entry_open",
        "entry_projected_upper_band",
        "exit_signal_date",
        "exit_execution_date",
        "exit_open",
        "exit_projected_lower_band",
        "gross_trade_return",
        "net_trade_return_0_bps",
        "net_trade_return_5_bps",
        "net_trade_return_10_bps",
        "holding_sessions",
        "maximum_favorable_excursion",
        "maximum_adverse_excursion",
        "exit_reason",
        "terminal_open_status",
    ]
    open_engine.write_csv(OUTPUT_DIR / "trade_ledger.csv", trade_rows, trade_fields)
    open_engine.write_csv(
        OUTPUT_DIR / "holding_period_diagnostics.csv",
        holding_rows,
        rows_with_fields(holding_rows, ["record_type", "calendar_year"]),
    )
    open_fields = [
        "row_id",
        "cost_assumption_bps",
        "date",
        "signal_date",
        "event_type",
        "pretrade_SPY_weight",
        "pretrade_BIL_weight",
        "target_SPY_weight",
        "target_BIL_weight",
        "rebalance_at_open",
        "SPY_adjusted_open",
        "BIL_adjusted_open",
        "SPY_adjusted_close",
        "BIL_adjusted_close",
        "pretrade_overnight_contribution",
        "posttrade_open_to_close_contribution",
        "one_way_turnover",
        "transaction_cost_dollars",
        "transaction_cost_return",
        "close_nav",
        "daily_return",
        "return_decomposition",
        "decomposition_difference",
        "end_SPY_weight",
        "end_BIL_weight",
        "end_cash_weight",
        "gross_exposure",
        "daily_weight_sum",
        "same_close_fill_used",
        "stale_open_forward_fill_used",
        "transaction_cost_charged_once",
    ]
    open_engine.write_csv(
        OUTPUT_DIR / "open_execution_reconciliation.csv", open_rows, open_fields
    )
    open_engine.write_csv(
        OUTPUT_DIR / "exposure_control_reconciliation.csv",
        exposure_rows,
        rows_with_fields(exposure_rows, ["cost_assumption_bps"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        rows_with_fields(turnover_rows, ["row_id", "cost_assumption_bps"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        rows_with_fields(invariant_rows, ["row_id", "cost_assumption_bps"]),
    )

    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "route": "standalone",
        "stage": STAGE,
        "followup_gate": gates,
        "exposure_matched_SPY_weight": exposure_weight,
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }
    open_engine.write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "failure_reason": failure_reason,
                "failed_gate_ids": [
                    key for key, passed in gates.items() if not passed
                ],
            }
        ]
        if failure_reason
        else []
    )
    open_engine.write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["strategy_id", "failure_reason", "failed_gate_ids"],
    )
    next_row = {
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "next_action": next_action,
        "executed_in_this_task": False,
    }
    open_engine.write_csv(
        OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row)
    )

    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "canonical_experiment_trials": 1,
        "benchmark_references": 6,
        "portfolio_diagnostics": 4,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_standalone"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "inconclusive_data_issue": int(outcome == "inconclusive_data_issue"),
        "blocked_feasibility": int(outcome == "blocked_feasibility"),
    }
    open_engine.write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "source_library_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "portfolio_diagnostic_count": 4,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "channel_contract": "TradingView_Rule_2_only",
        "rule_number": RULE_NUMBER,
        "period_sessions": PERIOD_SESSIONS,
        "warmup_sessions": WARMUP_SESSIONS,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "cost_assumptions_bps": list(COST_BPS),
        "preregistration_hash": preregistration_hash,
        "provider_access": False,
        "network_access": False,
        "parameter_variants": 0,
        "optimization_performed": False,
        "validation_claimed": False,
        "paper_demo_action": False,
        "broker_or_order_action": False,
    }
    open_engine.write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    report = f"""# Kaufman PJK Regression-Channel Breakout Exploration

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or "none"}`.

Exactly one frozen canonical exploration trial used the TradingView Rule-2
contract: a 40-close OLS fit, a 41-session high/low deviation window, strict
projected-band comparisons, and following-session adjusted-open execution.
The EasyLanguage deviation loop was not mixed into the channel.

The open accounting assigned the overnight interval to the pretrade holding,
charged costs once at the execution open, and assigned the open-to-close
interval to the post-trade holding. Controls and 80/20 portfolio
constructions remained benchmark or portfolio diagnostics, not trials.

The exact next action is `{next_action}`. This exploratory result does not
authorize validation, lifecycle changes, paper/demo activation, or broker
activity.
"""
    (OUTPUT_DIR / "batch_report.md").write_text(report, encoding="utf-8")

    protected_after = {
        rel(path): open_engine.file_hash(path) for path in PROTECTED_PATHS
    }
    cache_after = open_engine.tree_hash(CACHE_DIR)
    prior_evidence_after = open_engine.tree_hash(
        ROOT / "evidence", OUTPUT_DIR.parent
    )
    before_consistency = {path.name for path in OUTPUT_DIR.iterdir()}
    required_exact = (
        before_consistency | {"consistency_check.json"}
    ) == REQUIRED_OUTPUTS and "consistency_check.json" not in before_consistency
    consistency = {
        **manifest,
        "overall_pass": bool(
            required_exact
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and deterministic
            and funnel["strategy_configurations"] == 1
            and funnel["canonical_experiment_trials"] == 1
            and funnel["benchmark_references"] == 6
        ),
        "required_outputs_exact": required_exact,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "serial_rerun_deterministic": deterministic,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "provider_access": False,
        "network_access": False,
        "strategies_created": 1,
        "experiment_trials_created": 1,
        "benchmark_references_created": 6,
        "paper_demo_observations_created": 0,
        "lifecycle_state_changed": False,
        "historical_backtest_variants": 1 if preflight_pass else 0,
        "parameter_search_performed": False,
        "broker_orders": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_actions": 0,
        "followup_gate": gates,
    }
    open_engine.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "evaluation_start": (
            panel.index[0].date().isoformat() if preflight_pass else ""
        ),
        "evaluation_end": (
            panel.index[-1].date().isoformat() if preflight_pass else ""
        ),
        "completed_trades": len(
            [row for row in trade_rows if not row["terminal_open_status"]]
        ),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
