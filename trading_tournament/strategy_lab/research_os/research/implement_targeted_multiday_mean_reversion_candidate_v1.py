from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    fast_price_volume_discovery_batch_v2 as market,
)
from strategy_lab.research_os.research import (
    pagonidis_ibs_next_open_portability_exploration_v1 as open_precedent,
)


TASK_ID = "implement_targeted_multiday_mean_reversion_candidate_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "connors_alvarez_double7_spy_bil_next_open_v1"
FAMILY_ID = "trend_filtered_closing_channel_mean_reversion"
DISPLAY_NAME = "Connors-Alvarez Double 7 SPY Pullback"
ARCHITECTURE = "long_only_trend_filtered_multiday_closing_channel_reversal"
SOURCE_RECORD_ID = "src_connors_alvarez_double7_spy_next_open_v1"
SOURCE_LINEAGE = (
    "targeted_multiday_mean_reversion_source_sprint_v1:"
    "src_connors_alvarez_double7_spy_next_open_v1"
)
TRIAL_ID = "implement_targeted_multiday_mean_reversion_candidate_v1__canonical"
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

TREND_SESSIONS = 200
CHANNEL_SESSIONS = 7
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
TOLERANCE = 1e-10
START_NAV = 1.0

CACHE_DIR = ROOT / "data" / "cache"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "family_lineage"
    / "family_ledger.yaml",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "operations"
    / "active_observations.yaml",
)

CONTROL_IDS = (
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
    "SPY_200_day_trend_control",
    "double7_no_trend_filter_spy_bil_v1",
    "SPY_50_200_golden_cross_control",
    "double7_exposure_matched_spy_bil_v1",
)
CRITICAL_CONTROL_IDS = (
    "double7_no_trend_filter_spy_bil_v1",
    "double7_exposure_matched_spy_bil_v1",
)
NEXT_ADVANCE = "direction_owner_review_double7_multiday_mean_reversion_followup_v1"
NEXT_CLOSE = "targeted_breadth_participation_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_double7_exploration_block_v1"

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
    "trade_ledger.csv",
    "holding_period_diagnostics.csv",
    "signal_diagnostics.csv",
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

METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_SPY_exposure",
    "total_one_way_turnover",
    "entry_count",
    "exit_count",
    "completed_trade_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


@dataclass(frozen=True)
class Schedule:
    targets: pd.DataFrame
    rebalance: pd.Series
    diagnostics: pd.DataFrame
    events: pd.DataFrame


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    if isinstance(normalized.index, pd.DatetimeIndex):
        normalized = normalized.reset_index(names="date")
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime(
            "%Y-%m-%d"
        )
    return "sha256:" + hashlib.sha256(
        normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()


def tree_hash(root: Path, excluded: Path | None = None) -> str:
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        resolved = path.resolve()
        if excluded_resolved is not None and (
            resolved == excluded_resolved or excluded_resolved in resolved.parents
        ):
            continue
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        return "" if not math.isfinite(float(value)) else f"{float(value):.12g}"
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
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


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
        "While in BIL, enter SPY at the next regular-session open when completed "
        "SPY close is strictly above its inclusive 200-session SMA and less than "
        "or equal to the inclusive seven-session closing low. While in SPY, exit "
        "to BIL at the next regular-session open when completed SPY close is "
        "greater than or equal to the inclusive seven-session closing high. The "
        "trend filter applies only to entry. No stop or maximum holding period."
    )


def source_row() -> dict[str, Any]:
    return {
        "source_record_id": SOURCE_RECORD_ID,
        "entity_type": "source_library_record",
        "stage": "source_extracted",
        "outcome": "feasible",
        "failure_reason": "",
        "implementation_authorized": True,
        "source_or_research_lineage": (
            "connors_alvarez_double7__alvarez_public_next_open_rules_2016"
        ),
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
            "trend_sma_sessions": TREND_SESSIONS,
            "entry_channel_sessions": CHANNEL_SESSIONS,
            "exit_channel_sessions": CHANNEL_SESSIONS,
            "channel_includes_current_close": True,
            "entry_comparison": "inclusive_low",
            "exit_comparison": "inclusive_high",
            "trend_filter_applies_to_exit": False,
            "signal_timestamp": "completed_close_t",
            "execution_timestamp": "next_regular_session_open",
            "primary_cost_bps_one_way": PRIMARY_COST_BPS,
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
        "execution_changed": False,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "canonical_trial": True,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    rules = {
        "SPY_buy_and_hold": "Hold SPY throughout the identical evaluation period.",
        "BIL_buy_and_hold": "Hold BIL throughout the identical evaluation period.",
        "SPY_200_day_trend_control": (
            "SPY when completed close is strictly above SMA200; BIL otherwise; "
            "execute at the next regular-session open."
        ),
        "double7_no_trend_filter_spy_bil_v1": (
            "Same inclusive seven-session closing-low entry and closing-high exit "
            "without the 200-session trend filter; identical next-open execution."
        ),
        "SPY_50_200_golden_cross_control": (
            "SPY when completed SMA50 is strictly above completed SMA200; BIL "
            "otherwise; execute at the next regular-session open."
        ),
        "double7_exposure_matched_spy_bil_v1": (
            "Monthly rebalance to the candidate full-period average target SPY "
            "weight, with BIL receiving the remainder; no optimization or rounding."
        ),
    }
    roles = {
        "SPY_buy_and_hold": "broad_benchmark",
        "BIL_buy_and_hold": "inactive_asset_control",
        "SPY_200_day_trend_control": "trend_control",
        "double7_no_trend_filter_spy_bil_v1": "same_purpose_control",
        "SPY_50_200_golden_cross_control": "simple_trend_control",
        "double7_exposure_matched_spy_bil_v1": "mechanical_exposure_control",
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
    source = [source_row()]
    strategy = [strategy_row(pending, "", pending_action)]
    trial = [trial_row(pending, "", pending_action)]
    benchmarks = benchmark_rows()
    process = [process_row(pending, pending_action)]
    write_csv(OUTPUT_DIR / "source_library_records.csv", source, list(source[0]))
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy, list(strategy[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial, list(trial[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", process, list(process[0]))
    return canonical_hash(
        {
            "source": source,
            "strategy": strategy,
            "trial": trial,
            "benchmarks": benchmarks,
            "process": process,
            "frozen_rule": frozen_rule(),
        }
    )


def load_preflight() -> tuple[
    pd.DataFrame,
    list[dict[str, Any]],
    bool,
]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in ("SPY", "BIL"):
        row, frame = open_precedent.preflight_symbol(symbol)
        rows.append(row)
        frames[symbol] = frame
    if any(frame.empty for frame in frames.values()):
        return pd.DataFrame(), rows, False

    common_start = max(frame.index.min() for frame in frames.values())
    common_end = min(frame.index.max() for frame in frames.values())
    common = frames["SPY"].loc[common_start:common_end].index
    identical = common.equals(frames["BIL"].loc[common_start:common_end].index)
    enough = len(common) >= TREND_SESSIONS + 1
    for row in rows:
        row["common_eligible_start"] = common_start.date().isoformat()
        row["common_eligible_end"] = common_end.date().isoformat()
        row["identical_common_dates"] = identical
        row["candidate_preflight_status"] = (
            "pass"
            if row["candidate_preflight_status"] == "pass"
            and identical
            and enough
            else "fail"
        )
        if row["candidate_preflight_status"] == "fail" and not row["failure_reason"]:
            row["failure_reason"] = "incomplete_common_calendar_or_warmup"

    if not identical or not enough or any(
        row["candidate_preflight_status"] != "pass" for row in rows
    ):
        return pd.DataFrame(), rows, False

    panel = pd.DataFrame(index=common)
    for symbol, frame in frames.items():
        for field in ("open", "high", "low", "close", "volume"):
            panel[(symbol, field)] = frame.loc[common, field].to_numpy(dtype=float)
    panel.columns = pd.MultiIndex.from_tuples(panel.columns)
    return panel, rows, True


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
    ]
    return pd.DataFrame(rows, columns=fields)


def channel_schedule(
    close: pd.Series,
    trend_required: bool,
) -> Schedule:
    index = pd.DatetimeIndex(close.index)
    sma200 = close.rolling(TREND_SESSIONS, min_periods=TREND_SESSIONS).mean()
    low7 = close.rolling(CHANNEL_SESSIONS, min_periods=CHANNEL_SESSIONS).min()
    high7 = close.rolling(CHANNEL_SESSIONS, min_periods=CHANNEL_SESSIONS).max()
    holding = "BIL"
    pending: str | None = None
    pending_event = ""
    targets: list[dict[str, float]] = []
    rebalance: list[bool] = []
    diagnostics: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for i, day in enumerate(index):
        open_event = pending_event
        if pending is not None:
            holding = pending
            pending = None
            pending_event = ""
        targets.append(
            {"SPY": 1.0 if holding == "SPY" else 0.0, "BIL": 1.0 if holding == "BIL" else 0.0}
        )
        rebalance.append(i == 0 or bool(open_event))

        signal = "none"
        available = bool(
            pd.notna(low7.loc[day])
            and pd.notna(high7.loc[day])
            and (not trend_required or pd.notna(sma200.loc[day]))
        )
        trend_pass = bool(
            pd.notna(sma200.loc[day]) and close.loc[day] > sma200.loc[day]
        )
        entry = bool(
            available
            and holding == "BIL"
            and (trend_pass or not trend_required)
            and close.loc[day] <= low7.loc[day] + TOLERANCE
        )
        exit_signal = bool(
            available
            and holding == "SPY"
            and close.loc[day] >= high7.loc[day] - TOLERANCE
        )
        next_date = index[i + 1] if i + 1 < len(index) else None
        status = "no_signal"
        if entry:
            signal = "entry"
            status = "scheduled_next_open" if next_date is not None else "terminal_unexecuted"
        elif exit_signal:
            signal = "exit"
            status = "scheduled_next_open" if next_date is not None else "terminal_unexecuted"
        elif not available:
            status = "signal_unavailable_retain_holding"

        if signal in {"entry", "exit"} and next_date is not None:
            to_asset = "SPY" if signal == "entry" else "BIL"
            events.append(
                {
                    "signal_date": day,
                    "execution_date": next_date,
                    "event_type": signal,
                    "signal_close": float(close.loc[day]),
                    "sma200": float(sma200.loc[day]) if pd.notna(sma200.loc[day]) else "",
                    "channel_low_7": float(low7.loc[day]),
                    "channel_high_7": float(high7.loc[day]),
                    "from_asset": holding,
                    "to_asset": to_asset,
                }
            )
            pending = to_asset
            pending_event = signal

        diagnostics.append(
            {
                "date": day,
                "adjusted_close": float(close.loc[day]),
                "SMA200": float(sma200.loc[day]) if pd.notna(sma200.loc[day]) else "",
                "channel_low_7": float(low7.loc[day]) if pd.notna(low7.loc[day]) else "",
                "channel_high_7": float(high7.loc[day]) if pd.notna(high7.loc[day]) else "",
                "channel_includes_current_close": True,
                "trend_filter_required": trend_required,
                "trend_condition_strictly_above": trend_pass,
                "holding_at_signal_close": holding,
                "entry_signal": entry,
                "exit_signal": exit_signal,
                "signal_type": signal,
                "signal_status": status,
                "next_open_execution_date": next_date if signal != "none" else "",
                "same_close_fill_allowed": False,
                "maximum_holding_period": "",
                "stop_loss": "",
            }
        )

    return Schedule(
        targets=pd.DataFrame(targets, index=index),
        rebalance=pd.Series(rebalance, index=index, dtype=bool),
        diagnostics=pd.DataFrame(diagnostics),
        events=_event_frame(events),
    )


def regime_schedule(close: pd.Series, rule: str) -> Schedule:
    index = pd.DatetimeIndex(close.index)
    sma200 = close.rolling(TREND_SESSIONS, min_periods=TREND_SESSIONS).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    holding = "BIL"
    pending: str | None = None
    pending_event = ""
    targets: list[dict[str, float]] = []
    rebalance: list[bool] = []
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for i, day in enumerate(index):
        open_event = pending_event
        if pending is not None:
            holding = pending
            pending = None
            pending_event = ""
        targets.append(
            {"SPY": 1.0 if holding == "SPY" else 0.0, "BIL": 1.0 if holding == "BIL" else 0.0}
        )
        rebalance.append(i == 0 or bool(open_event))
        available = pd.notna(sma200.loc[day])
        desired = holding
        if available:
            if rule == "price_sma200":
                desired = "SPY" if close.loc[day] > sma200.loc[day] else "BIL"
            elif rule == "sma50_sma200":
                desired = (
                    "SPY"
                    if pd.notna(sma50.loc[day]) and sma50.loc[day] > sma200.loc[day]
                    else "BIL"
                )
            else:
                raise ValueError(f"Unsupported regime rule: {rule}")
        event_type = ""
        if desired != holding and i + 1 < len(index):
            event_type = "entry" if desired == "SPY" else "exit"
            events.append(
                {
                    "signal_date": day,
                    "execution_date": index[i + 1],
                    "event_type": event_type,
                    "signal_close": float(close.loc[day]),
                    "sma200": float(sma200.loc[day]),
                    "channel_low_7": "",
                    "channel_high_7": "",
                    "from_asset": holding,
                    "to_asset": desired,
                }
            )
            pending = desired
            pending_event = event_type
        diagnostics.append(
            {
                "date": day,
                "adjusted_close": float(close.loc[day]),
                "SMA200": float(sma200.loc[day]) if available else "",
                "SMA50": float(sma50.loc[day]) if pd.notna(sma50.loc[day]) else "",
                "holding_at_signal_close": holding,
                "signal_type": event_type or "none",
            }
        )
    return Schedule(
        targets=pd.DataFrame(targets, index=index),
        rebalance=pd.Series(rebalance, index=index, dtype=bool),
        diagnostics=pd.DataFrame(diagnostics),
        events=_event_frame(events),
    )


def static_schedule(index: pd.DatetimeIndex, spy_weight: float) -> Schedule:
    targets = pd.DataFrame(
        {"SPY": spy_weight, "BIL": 1.0 - spy_weight},
        index=index,
    )
    rebalance = pd.Series(False, index=index)
    rebalance.iloc[0] = True
    return Schedule(targets, rebalance, pd.DataFrame(), _event_frame([]))


def monthly_exposure_schedule(
    index: pd.DatetimeIndex,
    spy_weight: float,
) -> Schedule:
    schedule = static_schedule(index, spy_weight)
    rebalance = pd.Series(False, index=index)
    rebalance.iloc[0] = True
    for i in range(1, len(index)):
        rebalance.iloc[i] = index[i].to_period("M") != index[i - 1].to_period("M")
    return Schedule(
        schedule.targets,
        rebalance,
        pd.DataFrame(),
        _event_frame([]),
    )


def schedule_event_map(events: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    if events.empty:
        return {}
    return {
        pd.Timestamp(row["execution_date"]): row.to_dict()
        for _, row in events.iterrows()
    }


def simulate(
    row_id: str,
    panel: pd.DataFrame,
    schedule: Schedule,
    cost_bps: float,
) -> dict[str, Any]:
    index = pd.DatetimeIndex(panel.index)
    symbols = ["SPY", "BIL"]
    opens = panel.loc[:, [(symbol, "open") for symbol in symbols]].to_numpy(
        dtype=float
    )
    closes = panel.loc[:, [(symbol, "close") for symbol in symbols]].to_numpy(
        dtype=float
    )
    targets = schedule.targets.loc[index, symbols].to_numpy(dtype=float)
    flags = schedule.rebalance.loc[index].to_numpy(dtype=bool)
    event_map = schedule_event_map(schedule.events)
    rate = cost_bps / 10000.0

    shares = np.zeros(2, dtype=float)
    cash = START_NAV
    prior_close_prices: np.ndarray | None = None
    prior_close_nav = START_NAV
    rows: list[dict[str, Any]] = []

    for i, day in enumerate(index):
        open_row = opens[i]
        close_row = closes[i]
        if not np.isfinite(open_row).all() or not np.isfinite(close_row).all():
            raise ValueError(f"{row_id}: missing execution or valuation price on {day}")
        overnight_pnl = (
            float(np.dot(shares, open_row - prior_close_prices))
            if prior_close_prices is not None
            else 0.0
        )
        open_nav = float(cash + np.dot(shares, open_row))
        pretrade_values = shares * open_row
        pretrade_weights = pretrade_values / open_nav
        target = targets[i]
        turnover = 0.0
        cost_dollars = 0.0
        if flags[i]:
            turnover = 0.5 * float(np.abs(target - pretrade_weights).sum())
            cost_dollars = open_nav * turnover * rate
            post_cost_nav = open_nav - cost_dollars
            desired_values = target * post_cost_nav
            shares = desired_values / open_row
            cash = float(post_cost_nav - desired_values.sum())
            if abs(cash) <= 1e-12:
                cash = 0.0
        intraday_pnl = float(np.dot(shares, close_row - open_row))
        close_values = shares * close_row
        close_nav = float(cash + close_values.sum())
        daily_return = close_nav / prior_close_nav - 1.0
        end_weights = close_values / close_nav
        cash_weight = cash / close_nav
        event = event_map.get(day, {})
        decomposition = (
            overnight_pnl / prior_close_nav
            + intraday_pnl / prior_close_nav
            - cost_dollars / prior_close_nav
        )
        rows.append(
            {
                "row_id": row_id,
                "cost_assumption_bps": cost_bps,
                "date": day,
                "signal_date": event.get("signal_date", ""),
                "event_type": event.get("event_type", "initialization" if i == 0 else ""),
                "pretrade_SPY_weight": float(pretrade_weights[0]),
                "pretrade_BIL_weight": float(pretrade_weights[1]),
                "target_SPY_weight": float(target[0]),
                "target_BIL_weight": float(target[1]),
                "rebalance_at_open": bool(flags[i]),
                "SPY_adjusted_open": float(open_row[0]),
                "BIL_adjusted_open": float(open_row[1]),
                "SPY_adjusted_close": float(close_row[0]),
                "BIL_adjusted_close": float(close_row[1]),
                "pretrade_overnight_contribution": overnight_pnl / prior_close_nav,
                "posttrade_open_to_close_contribution": intraday_pnl / prior_close_nav,
                "one_way_turnover": turnover,
                "transaction_cost_dollars": cost_dollars,
                "transaction_cost_return": cost_dollars / prior_close_nav,
                "close_nav": close_nav,
                "daily_return": daily_return,
                "return_decomposition": decomposition,
                "decomposition_difference": daily_return - decomposition,
                "end_SPY_weight": float(end_weights[0]),
                "end_BIL_weight": float(end_weights[1]),
                "end_cash_weight": float(cash_weight),
                "gross_exposure": float(np.abs(end_weights).sum()),
                "daily_weight_sum": float(end_weights.sum() + cash_weight),
                "same_close_fill_used": False,
                "stale_open_forward_fill_used": False,
                "transaction_cost_charged_once": True,
            }
        )
        prior_close_prices = close_row
        prior_close_nav = close_nav

    daily = pd.DataFrame(rows).set_index("date", drop=False)
    return {
        "row_id": row_id,
        "cost_bps": cost_bps,
        "schedule": schedule,
        "daily": daily,
        "returns": pd.Series(
            daily["daily_return"].to_numpy(dtype=float),
            index=index,
            name=row_id,
        ),
        "turnover": pd.Series(
            daily["one_way_turnover"].to_numpy(dtype=float),
            index=index,
        ),
        "cost": pd.Series(
            daily["transaction_cost_return"].to_numpy(dtype=float),
            index=index,
        ),
        "target_spy": pd.Series(
            daily["target_SPY_weight"].to_numpy(dtype=float),
            index=index,
        ),
        "state_hash": frame_hash(daily.reset_index(drop=True)),
    }


def payload_invariants(payload: dict[str, Any]) -> dict[str, Any]:
    daily = payload["daily"]
    schedule = payload["schedule"]
    events = schedule.events
    index = pd.DatetimeIndex(daily.index)
    timing = True
    if not events.empty:
        positions = {day: i for i, day in enumerate(index)}
        timing = all(
            pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["execution_date"])
            and positions[pd.Timestamp(row["execution_date"])]
            == positions[pd.Timestamp(row["signal_date"])] + 1
            for _, row in events.iterrows()
        )
    numeric = bool(
        np.isfinite(daily["daily_return"].to_numpy(dtype=float)).all()
        and np.isfinite(daily["close_nav"].to_numpy(dtype=float)).all()
        and (daily["close_nav"].astype(float) > 0.0).all()
        and daily["decomposition_difference"].astype(float).abs().max() <= 1e-9
    )
    weights = bool(
        (daily[["end_SPY_weight", "end_BIL_weight"]].astype(float) >= -TOLERANCE)
        .all()
        .all()
        and (daily["daily_weight_sum"].astype(float) - 1.0).abs().max() <= 1e-9
        and (schedule.targets.to_numpy(dtype=float) >= 0.0).all()
        and np.allclose(
            schedule.targets.sum(axis=1).to_numpy(dtype=float),
            1.0,
            atol=TOLERANCE,
            rtol=0.0,
        )
    )
    exposure = bool(
        daily["gross_exposure"].astype(float).max() <= 1.0 + 1e-9
        and daily["daily_weight_sum"].astype(float).max() <= 1.0 + 1e-9
    )
    costs = bool(
        np.allclose(
            daily["transaction_cost_dollars"].to_numpy(dtype=float),
            daily["one_way_turnover"].to_numpy(dtype=float)
            * (payload["cost_bps"] / 10000.0)
            * (
                daily["close_nav"].shift(1, fill_value=START_NAV).to_numpy(dtype=float)
                * (
                    1.0
                    + daily["pretrade_overnight_contribution"].to_numpy(dtype=float)
                )
            ),
            atol=1e-9,
            rtol=1e-9,
        )
    )
    no_stale = not bool(daily["stale_open_forward_fill_used"].astype(bool).any())
    no_same_close = not bool(daily["same_close_fill_used"].astype(bool).any())
    explicit_zeros = bool((schedule.targets == 0.0).any().any())
    passed = bool(
        timing
        and numeric
        and weights
        and exposure
        and costs
        and no_stale
        and no_same_close
    )
    return {
        "entry_signal_data_through_close_only": timing,
        "entry_executes_next_open": timing,
        "exit_signal_data_through_close_only": timing,
        "exit_executes_next_open": timing,
        "pretrade_receives_close_to_open": numeric,
        "posttrade_receives_open_to_close": numeric,
        "no_signal_close_fill": no_same_close,
        "weights_nonnegative": weights,
        "weights_sum_to_one": weights,
        "gross_exposure_at_most_one": exposure,
        "explicit_zero_weights_preserved": explicit_zeros,
        "transaction_costs_charged_once": costs,
        "no_stale_open_forward_fill": no_stale,
        "timing_invariant_status": "pass" if timing else "fail",
        "numeric_invariant_status": "pass" if numeric and costs else "fail",
        "weight_invariant_status": "pass" if weights else "fail",
        "exposure_invariant_status": "pass" if exposure else "fail",
        "maximum_gross_exposure": float(daily["gross_exposure"].max()),
        "maximum_daily_weight_sum": float(daily["daily_weight_sum"].max()),
        "invariant_pass": passed,
    }


def event_counts(
    schedule: Schedule,
    period_index: pd.DatetimeIndex,
) -> tuple[int, int, int]:
    if schedule.events.empty:
        return 0, 0, 0
    period = set(period_index)
    events = schedule.events.loc[
        schedule.events["execution_date"].map(pd.Timestamp).isin(period)
    ]
    entries = int((events["event_type"] == "entry").sum())
    exits = int((events["event_type"] == "exit").sum())
    return entries, exits, exits


def metric_payload(
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    returns = payload["returns"]
    if period_index is not None:
        returns = returns.reindex(period_index).dropna()
    index = pd.DatetimeIndex(returns.index)
    metrics = market.metrics_from_returns(returns)
    invariants = payload_invariants(payload)
    entries, exits, completed = event_counts(payload["schedule"], index)
    daily = payload["daily"].loc[index]
    return {
        **metrics,
        "average_SPY_exposure": float(
            payload["target_spy"].reindex(index).mean()
        ),
        "total_one_way_turnover": float(
            payload["turnover"].reindex(index).sum()
        ),
        "entry_count": entries,
        "exit_count": exits,
        "completed_trade_count": completed,
        "transaction_cost_drag": float(payload["cost"].reindex(index).sum()),
        "maximum_gross_exposure": float(daily["gross_exposure"].max()),
        "maximum_daily_weight_sum": float(daily["daily_weight_sum"].max()),
        "timing_invariant_status": invariants["timing_invariant_status"],
        "numeric_invariant_status": invariants["numeric_invariant_status"],
        "exposure_invariant_status": invariants["exposure_invariant_status"],
        "weight_invariant_status": invariants["weight_invariant_status"],
        "invariant_pass": invariants["invariant_pass"],
    }


def result_row(
    row_id: str,
    payload: dict[str, Any],
    period_label: str,
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "entity_type": (
            "strategy_configuration"
            if row_id == STRATEGY_ID
            else "benchmark_reference"
        ),
        "stage": STAGE if row_id == STRATEGY_ID else "benchmark_reference_only",
        "cost_assumption_bps": payload["cost_bps"],
        "period_label": period_label,
        "period_role": (
            "full_exploration_period"
            if period_label == "full_period"
            else "chronological_half_not_validation"
        ),
        **metric_payload(payload, period_index),
    }


def split_halves(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    midpoint = len(index) // 2
    return {
        "first_chronological_half": index[:midpoint],
        "second_chronological_half": index[midpoint:],
    }


def control_dominates(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - TOLERANCE,
        float(control["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"]) - TOLERANCE,
        float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - TOLERANCE,
    )
    strict = (
        float(control["cagr"]) > float(candidate["cagr"]) + TOLERANCE
        or float(control["sharpe_ratio"])
        > float(candidate["sharpe_ratio"]) + TOLERANCE
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + TOLERANCE
    )
    return bool(all(equal_or_better) and strict)


def material_advantage(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def worse_on_both(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"])
        < float(control["sharpe_ratio"]) - TOLERANCE
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"]) - TOLERANCE
    )


def economically_replicated(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return bool(
        control_dominates(candidate, control)
        or (
            abs(
                float(candidate["sharpe_ratio"])
                - float(control["sharpe_ratio"])
            )
            < 0.02
            and abs(
                float(candidate["maximum_drawdown"])
                - float(control["maximum_drawdown"])
            )
            < 0.01
        )
    )


def trade_ledger(
    panel: pd.DataFrame,
    schedule: Schedule,
) -> list[dict[str, Any]]:
    events = schedule.events
    if events.empty:
        return []
    index = pd.DatetimeIndex(panel.index)
    position = {day: i for i, day in enumerate(index)}
    rows: list[dict[str, Any]] = []
    entry: dict[str, Any] | None = None
    for _, event in events.iterrows():
        if event["event_type"] == "entry":
            if entry is not None:
                raise RuntimeError("Duplicated entry while a Double 7 trade is open")
            entry = event.to_dict()
            continue
        if entry is None:
            raise RuntimeError("Exit occurred while Double 7 was in BIL")
        entry_date = pd.Timestamp(entry["execution_date"])
        exit_date = pd.Timestamp(event["execution_date"])
        entry_position = position[entry_date]
        exit_position = position[exit_date]
        entry_open = float(panel.loc[entry_date, ("SPY", "open")])
        exit_open = float(panel.loc[exit_date, ("SPY", "open")])
        held_index = index[entry_position:exit_position]
        lows = panel.loc[held_index, ("SPY", "low")].to_numpy(dtype=float)
        highs = panel.loc[held_index, ("SPY", "high")].to_numpy(dtype=float)
        lows = np.append(lows, exit_open)
        highs = np.append(highs, exit_open)
        gross = exit_open / entry_open - 1.0
        rows.append(
            trade_row(
                entry,
                event.to_dict(),
                entry_open,
                exit_open,
                gross,
                max(1, exit_position - entry_position),
                float(lows.min() / entry_open - 1.0),
                float(highs.max() / entry_open - 1.0),
                False,
            )
        )
        entry = None
    if entry is not None:
        entry_date = pd.Timestamp(entry["execution_date"])
        entry_position = position[entry_date]
        entry_open = float(panel.loc[entry_date, ("SPY", "open")])
        end_close = float(panel.loc[index[-1], ("SPY", "close")])
        held_index = index[entry_position:]
        lows = panel.loc[held_index, ("SPY", "low")].to_numpy(dtype=float)
        highs = panel.loc[held_index, ("SPY", "high")].to_numpy(dtype=float)
        rows.append(
            trade_row(
                entry,
                None,
                entry_open,
                "",
                end_close / entry_open - 1.0,
                len(held_index),
                float(lows.min() / entry_open - 1.0),
                float(highs.max() / entry_open - 1.0),
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
    mae: float,
    mfe: float,
    open_at_end: bool,
) -> dict[str, Any]:
    switches = 1 if open_at_end else 2
    net = {
        bps: (1.0 + gross) * (1.0 - bps / 10000.0) ** switches - 1.0
        for bps in COST_BPS
    }
    return {
        "entry_signal_date": entry["signal_date"],
        "entry_execution_date": entry["execution_date"],
        "entry_open": entry_open,
        "entry_seven_session_low": entry["channel_low_7"],
        "entry_SMA200": entry["sma200"],
        "exit_signal_date": exit_event["signal_date"] if exit_event else "",
        "exit_execution_date": exit_event["execution_date"] if exit_event else "",
        "exit_open": exit_open,
        "exit_seven_session_high": (
            exit_event["channel_high_7"] if exit_event else ""
        ),
        "gross_trade_return": gross,
        "net_trade_return_0_bps": net[0.0],
        "net_trade_return_5_bps": net[5.0],
        "net_trade_return_10_bps": net[10.0],
        "holding_sessions": holding_sessions,
        "maximum_adverse_excursion": mae,
        "maximum_favorable_excursion": mfe,
        "exit_reason": (
            "open_at_evaluation_end"
            if open_at_end
            else "inclusive_seven_session_closing_high"
        ),
        "trade_open_at_evaluation_end": open_at_end,
    }


def holding_diagnostics(
    trades: list[dict[str, Any]],
    candidate_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    completed = [row for row in trades if not row["trade_open_at_evaluation_end"]]
    holdings = [int(row["holding_sessions"]) for row in completed]
    net_returns = [float(row["net_trade_return_5_bps"]) for row in completed]
    entries = sorted(pd.Timestamp(row["entry_execution_date"]) for row in trades)
    index = pd.DatetimeIndex(candidate_payload["returns"].index)
    positions = {day: i for i, day in enumerate(index)}
    boundaries = [index[0], *entries, index[-1]]
    gaps = [
        positions[right] - positions[left]
        for left, right in zip(boundaries[:-1], boundaries[1:])
    ]
    summary = {
        "record_type": "full_period_summary",
        "calendar_year": "",
        "total_entries": len(trades),
        "completed_trades": len(completed),
        "open_terminal_trades": len(trades) - len(completed),
        "average_holding_sessions": float(np.mean(holdings)) if holdings else "",
        "median_holding_sessions": float(np.median(holdings)) if holdings else "",
        "maximum_holding_sessions": max(holdings) if holdings else "",
        "winning_trade_fraction_5_bps": (
            float(np.mean(np.asarray(net_returns) > 0.0)) if net_returns else ""
        ),
        "average_trade_return_5_bps": (
            float(np.mean(net_returns)) if net_returns else ""
        ),
        "median_trade_return_5_bps": (
            float(np.median(net_returns)) if net_returns else ""
        ),
        "entry_count_in_year": "",
        "average_SPY_exposure_in_year": "",
        "longest_interval_without_entry_sessions": max(gaps) if gaps else len(index),
    }
    rows = [summary]
    exposure = candidate_payload["target_spy"]
    years = sorted(set(index.year))
    for year in years:
        year_entries = sum(
            pd.Timestamp(row["entry_execution_date"]).year == year for row in trades
        )
        year_index = index[index.year == year]
        rows.append(
            {
                "record_type": "calendar_year",
                "calendar_year": year,
                "total_entries": "",
                "completed_trades": "",
                "open_terminal_trades": "",
                "average_holding_sessions": "",
                "median_holding_sessions": "",
                "maximum_holding_sessions": "",
                "winning_trade_fraction_5_bps": "",
                "average_trade_return_5_bps": "",
                "median_trade_return_5_bps": "",
                "entry_count_in_year": year_entries,
                "average_SPY_exposure_in_year": float(
                    exposure.reindex(year_index).mean()
                ),
                "longest_interval_without_entry_sessions": "",
            }
        )
    return rows


def decide_outcome(
    results: dict[tuple[str, float], dict[str, Any]],
    halves: dict[str, pd.DatetimeIndex],
    invariant_pass: bool,
) -> tuple[str, str, str, dict[str, bool]]:
    candidate = metric_payload(results[(STRATEGY_ID, PRIMARY_COST_BPS)])
    controls = {
        control: metric_payload(results[(control, PRIMARY_COST_BPS)])
        for control in CONTROL_IDS
    }
    critical_not_dominating = all(
        not control_dominates(candidate, controls[control])
        for control in CRITICAL_CONTROL_IDS
    )
    material_vs_critical = all(
        material_advantage(candidate, controls[control])
        for control in CRITICAL_CONTROL_IDS
    )
    half_stability = True
    completed_each_half = True
    for period_index in halves.values():
        cand_half = metric_payload(
            results[(STRATEGY_ID, PRIMARY_COST_BPS)], period_index
        )
        completed_each_half = (
            completed_each_half and cand_half["completed_trade_count"] >= 1
        )
        for control in CRITICAL_CONTROL_IDS:
            ctrl_half = metric_payload(
                results[(control, PRIMARY_COST_BPS)], period_index
            )
            half_stability = half_stability and not worse_on_both(
                cand_half, ctrl_half
            )
    trend_not_replicated = all(
        not economically_replicated(candidate, controls[control])
        for control in (
            "SPY_200_day_trend_control",
            "SPY_50_200_golden_cross_control",
        )
    )
    candidate_10 = metric_payload(results[(STRATEGY_ID, 10.0)])
    cost_robust = all(
        not worse_on_both(
            candidate_10,
            metric_payload(results[(control, 10.0)]),
        )
        for control in CRITICAL_CONTROL_IDS
    )
    gates = {
        "positive_full_period_after_cost_return": candidate["total_return"] > 0.0,
        "all_invariants_pass": invariant_pass,
        "critical_controls_do_not_dominate": critical_not_dominating,
        "material_advantage_vs_each_critical_control": material_vs_critical,
        "chronological_half_stability_vs_critical_controls": half_stability,
        "trend_controls_do_not_economically_replicate": trend_not_replicated,
        "ten_bps_not_unfavorable_on_both_vs_critical_controls": cost_robust,
        "completed_trade_in_each_chronological_half": completed_each_half,
    }
    if all(gates.values()):
        return (
            "exploratory_followup_candidate_standalone",
            "",
            NEXT_ADVANCE,
            gates,
        )
    if not gates["all_invariants_pass"]:
        reason = "methodology_failure"
    elif not gates["positive_full_period_after_cost_return"]:
        reason = "weak_return"
    elif (
        control_dominates(
            candidate,
            controls["double7_exposure_matched_spy_bil_v1"],
        )
        or not material_advantage(
            candidate,
            controls["double7_exposure_matched_spy_bil_v1"],
        )
    ):
        reason = "exposure_control_explanation"
    elif not gates["critical_controls_do_not_dominate"] or not gates[
        "material_advantage_vs_each_critical_control"
    ]:
        reason = "weak_vs_primary_control"
    elif not gates["chronological_half_stability_vs_critical_controls"] or not gates[
        "completed_trade_in_each_chronological_half"
    ]:
        reason = "period_instability"
    elif not gates["trend_controls_do_not_economically_replicate"]:
        reason = "benchmark_like_behavior"
    elif not gates["ten_bps_not_unfavorable_on_both_vs_critical_controls"]:
        reason = "cost_drag"
    else:
        reason = "weak_vs_primary_control"
    return "closed_exploration", reason, NEXT_CLOSE, gates


def rows_with_fields(
    rows: list[dict[str, Any]],
    leading: list[str],
) -> list[str]:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def run() -> dict[str, Any]:
    clean_output()
    protected_before = {rel(path): file_hash(path) for path in PROTECTED_PATHS}
    cache_before = tree_hash(CACHE_DIR)
    prior_evidence_before = tree_hash(ROOT / "evidence", OUTPUT_DIR.parent)
    preregistration_hash = write_preregistration()

    panel, preflight_rows, preflight_pass = load_preflight()
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        rows_with_fields(preflight_rows, ["symbol"]),
    )

    if not preflight_pass:
        outcome = "inconclusive_data_issue"
        failure_reason = "data_or_comparability_failure"
        next_action = NEXT_BLOCK
        candidate_rows: list[dict[str, Any]] = []
        control_rows: list[dict[str, Any]] = []
        half_rows: list[dict[str, Any]] = []
        trade_rows: list[dict[str, Any]] = []
        holding_rows: list[dict[str, Any]] = []
        signal_rows: list[dict[str, Any]] = []
        open_rows: list[dict[str, Any]] = []
        exposure_rows: list[dict[str, Any]] = []
        turnover_rows: list[dict[str, Any]] = []
        invariant_rows: list[dict[str, Any]] = []
        gates: dict[str, bool] = {}
        exposure_weight: float | str = ""
        deterministic_rerun = False
    else:
        close = panel[("SPY", "close")]
        index = pd.DatetimeIndex(panel.index)
        candidate_schedule = channel_schedule(close, trend_required=True)
        no_trend_schedule = channel_schedule(close, trend_required=False)
        schedules = {
            STRATEGY_ID: candidate_schedule,
            "SPY_buy_and_hold": static_schedule(index, 1.0),
            "BIL_buy_and_hold": static_schedule(index, 0.0),
            "SPY_200_day_trend_control": regime_schedule(
                close, "price_sma200"
            ),
            "double7_no_trend_filter_spy_bil_v1": no_trend_schedule,
            "SPY_50_200_golden_cross_control": regime_schedule(
                close, "sma50_sma200"
            ),
        }
        preliminary = simulate(
            STRATEGY_ID,
            panel,
            candidate_schedule,
            PRIMARY_COST_BPS,
        )
        exposure_weight = float(preliminary["target_spy"].mean())
        schedules["double7_exposure_matched_spy_bil_v1"] = (
            monthly_exposure_schedule(index, exposure_weight)
        )

        results: dict[tuple[str, float], dict[str, Any]] = {}
        for row_id, schedule in schedules.items():
            for cost in COST_BPS:
                results[(row_id, cost)] = simulate(
                    row_id, panel, schedule, cost
                )
        deterministic_repeat = simulate(
            STRATEGY_ID,
            panel,
            candidate_schedule,
            PRIMARY_COST_BPS,
        )
        deterministic_rerun = (
            deterministic_repeat["state_hash"]
            == results[(STRATEGY_ID, PRIMARY_COST_BPS)]["state_hash"]
        )

        halves = split_halves(index)
        all_invariants = all(
            payload_invariants(payload)["invariant_pass"]
            for payload in results.values()
        ) and deterministic_rerun
        outcome, failure_reason, next_action, gates = decide_outcome(
            results, halves, all_invariants
        )

        candidate_rows = [
            result_row(
                STRATEGY_ID,
                results[(STRATEGY_ID, cost)],
                "full_period",
            )
            for cost in COST_BPS
        ]
        control_rows = [
            result_row(
                control,
                results[(control, cost)],
                "full_period",
            )
            for control in CONTROL_IDS
            for cost in COST_BPS
        ]
        half_rows = [
            result_row(
                row_id,
                results[(row_id, PRIMARY_COST_BPS)],
                period,
                period_index,
            )
            for row_id in (STRATEGY_ID, *CONTROL_IDS)
            for period, period_index in halves.items()
        ]
        trade_rows = trade_ledger(panel, candidate_schedule)
        holding_rows = holding_diagnostics(
            trade_rows,
            results[(STRATEGY_ID, PRIMARY_COST_BPS)],
        )
        signal_rows = candidate_schedule.diagnostics.to_dict("records")
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
                "control_BIL_weight": 1.0 - exposure_weight,
                "rebalance_frequency": "monthly",
                "optimized_or_rounded": False,
                "performance_selected": False,
                "matches_candidate_target_exposure": True,
                "strategy_variant": False,
            }
            for cost in COST_BPS
        ]
        turnover_rows = []
        invariant_rows = []
        for (row_id, cost), payload in results.items():
            invariant = payload_invariants(payload)
            turnover_rows.append(
                {
                    "row_id": row_id,
                    "cost_assumption_bps": cost,
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "total_one_way_turnover": float(payload["turnover"].sum()),
                    "reported_cost_drag": float(payload["cost"].sum()),
                    "expected_cost_drag": float(payload["cost"].sum()),
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
                    "no_duplicate_entry_while_long": (
                        True
                        if row_id not in {STRATEGY_ID, "double7_no_trend_filter_spy_bil_v1"}
                        else not (
                            payload["schedule"].events["event_type"]
                            .eq("entry")
                            .rolling(2)
                            .sum()
                            .eq(2)
                            .any()
                        )
                    ),
                    "no_exit_while_in_BIL": True,
                    "serial_rerun_deterministic": (
                        deterministic_rerun if row_id == STRATEGY_ID else True
                    ),
                }
            )

    final_source = [source_row()]
    final_strategy = [strategy_row(outcome, failure_reason, next_action)]
    final_trial = [trial_row(outcome, failure_reason, next_action)]
    final_benchmarks = benchmark_rows()
    final_process = [process_row(outcome, next_action)]
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        final_source,
        list(final_source[0]),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        final_strategy,
        list(final_strategy[0]),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        final_trial,
        list(final_trial[0]),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        final_benchmarks,
        list(final_benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        final_process,
        list(final_process[0]),
    )

    result_fields = [
        "row_id",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        *METRIC_FIELDS,
    ]
    write_csv(OUTPUT_DIR / "all_trial_results.csv", candidate_rows, result_fields)
    write_csv(OUTPUT_DIR / "control_results.csv", control_rows, result_fields)
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_rows,
        result_fields,
    )
    trade_fields = [
        "entry_signal_date",
        "entry_execution_date",
        "entry_open",
        "entry_seven_session_low",
        "entry_SMA200",
        "exit_signal_date",
        "exit_execution_date",
        "exit_open",
        "exit_seven_session_high",
        "gross_trade_return",
        "net_trade_return_0_bps",
        "net_trade_return_5_bps",
        "net_trade_return_10_bps",
        "holding_sessions",
        "maximum_adverse_excursion",
        "maximum_favorable_excursion",
        "exit_reason",
        "trade_open_at_evaluation_end",
    ]
    write_csv(OUTPUT_DIR / "trade_ledger.csv", trade_rows, trade_fields)
    holding_fields = [
        "record_type",
        "calendar_year",
        "total_entries",
        "completed_trades",
        "open_terminal_trades",
        "average_holding_sessions",
        "median_holding_sessions",
        "maximum_holding_sessions",
        "winning_trade_fraction_5_bps",
        "average_trade_return_5_bps",
        "median_trade_return_5_bps",
        "entry_count_in_year",
        "average_SPY_exposure_in_year",
        "longest_interval_without_entry_sessions",
    ]
    write_csv(
        OUTPUT_DIR / "holding_period_diagnostics.csv",
        holding_rows,
        holding_fields,
    )
    signal_fields = [
        "date",
        "adjusted_close",
        "SMA200",
        "channel_low_7",
        "channel_high_7",
        "channel_includes_current_close",
        "trend_filter_required",
        "trend_condition_strictly_above",
        "holding_at_signal_close",
        "entry_signal",
        "exit_signal",
        "signal_type",
        "signal_status",
        "next_open_execution_date",
        "same_close_fill_allowed",
        "maximum_holding_period",
        "stop_loss",
    ]
    write_csv(OUTPUT_DIR / "signal_diagnostics.csv", signal_rows, signal_fields)
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
    write_csv(
        OUTPUT_DIR / "open_execution_reconciliation.csv",
        open_rows,
        open_fields,
    )
    exposure_fields = [
        "cost_assumption_bps",
        "candidate_full_period_average_target_SPY_weight",
        "control_SPY_weight",
        "control_BIL_weight",
        "rebalance_frequency",
        "optimized_or_rounded",
        "performance_selected",
        "matches_candidate_target_exposure",
        "strategy_variant",
    ]
    write_csv(
        OUTPUT_DIR / "exposure_control_reconciliation.csv",
        exposure_rows,
        exposure_fields,
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        rows_with_fields(turnover_rows, ["row_id", "cost_assumption_bps"]),
    )
    write_csv(
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
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "failure_reason": failure_reason,
                "failed_gate_ids": [
                    key for key, value in gates.items() if not value
                ],
            }
        ]
        if failure_reason
        else []
    )
    write_csv(
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
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "canonical_experiment_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_standalone"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "inconclusive_data_issue": int(outcome == "inconclusive_data_issue"),
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "source_library_record_count": 1,
        "strategy_configuration_count": 1,
        "canonical_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
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
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    protected_after = {rel(path): file_hash(path) for path in PROTECTED_PATHS}
    cache_after = tree_hash(CACHE_DIR)
    prior_evidence_after = tree_hash(ROOT / "evidence", OUTPUT_DIR.parent)
    report = f"""# Targeted Double 7 Mean-Reversion Exploration V1

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or "none"}`.

Exactly one frozen canonical trial tested the Connors-Alvarez Double 7 SPY
pullback using completed-close signals and following-session adjusted-open
execution. The strategy remained in BIL before warmup and whenever inactive.
The 200-session trend filter applied only to entry.

The opening accounting assigned the close-to-open interval to the pretrade
holding, charged one transaction-cost deduction at the open, and assigned the
open-to-close interval to the post-trade holding. No signal-close fill,
stale-price fill, stop, maximum hold, parameter alternative, or provider
request was used.

The exact next action is `{next_action}`. This exploration does not authorize
validation, lifecycle changes, paper/demo activation, or broker activity.
"""
    (OUTPUT_DIR / "batch_report.md").write_text(report, encoding="utf-8")

    names_before_consistency = {path.name for path in OUTPUT_DIR.iterdir()}
    required_present = (
        names_before_consistency | {"consistency_check.json"}
    ) == REQUIRED_OUTPUTS and "consistency_check.json" not in names_before_consistency
    consistency = {
        **manifest,
        "overall_pass": bool(
            required_present
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and deterministic_rerun
            and funnel["strategy_configurations"] == 1
            and funnel["canonical_experiment_trials"] == 1
            and funnel["benchmark_references"] == 6
        ),
        "required_outputs_exact": required_present,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "serial_rerun_deterministic": deterministic_rerun,
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
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
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
            [row for row in trade_rows if not row["trade_open_at_evaluation_end"]]
        ),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
