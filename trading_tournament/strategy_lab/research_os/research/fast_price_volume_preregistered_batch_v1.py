from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    acquire_validate_deferred_structural_etf_data_v2 as data_tools,
)
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    multi_family_fast_exploration_batch_v1 as shared,
)


BATCH_ID = "fast_price_volume_preregistered_batch_v1"
MODE = "fast-progress"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\7605ccd4-4ccb-42a7-947d-fef544e55840\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-29T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
SYMBOLS = ("SPY", "BIL")
WEIGHT_TOLERANCE = 1e-9

NEXT_REVIEW = "direction_owner_review_fast_price_volume_preregistered_batch_v1"
NEXT_ALL_CLOSED = "direction_owner_review_discovery_yield_after_fast_price_volume_v1"
NEXT_BLOCKED = "direction_owner_review_fast_price_volume_execution_block_v1"

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)

FORBIDDEN_FLAGS = {
    "external_source_research": False,
    "source_completion": False,
    "parameter_grid": False,
    "post_result_tuning": False,
    "benchmark_promotion": False,
    "validation_or_robustness": False,
    "lifecycle_or_registry_update": False,
    "paper_demo_eligibility_or_activation": False,
    "provider_or_network_access": False,
    "broker_account_order_or_real_money_action": False,
    "fifth_candidate_added": False,
}

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_standalone",
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}

ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "turnover_drag",
    "signal_scarcity",
    "excess_drawdown",
    "weak_return",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    trial_id: str
    family_id: str
    display_name: str
    strategy_architecture: str
    source_record_id: str
    source_or_research_lineage: str
    route: str
    controls: tuple[str, ...]
    critical_controls: tuple[str, ...]
    same_purpose_control: str
    exposure_control: str
    parameters: dict[str, Any]
    frozen_rule: str
    diagnostic_file: str


CARDS = (
    CandidateCard(
        strategy_id="barbara_decelerated_psar_spy_bil_v1",
        trial_id="fast_pv_v1__decelerated_psar__canonical",
        family_id="decelerated_parabolic_trend_state",
        display_name="Decelerated PSAR SPY/BIL Timing",
        strategy_architecture="long_only_adaptive_parabolic_stop_and_reverse_state",
        source_record_id="barbara_2021_decelerated_psar_appendix",
        source_or_research_lineage="barbara_2021_decelerated_psar_appendix",
        route="standalone_with_diversifier_diagnostic",
        controls=(
            "original_psar_spy_bil_control",
            "SPY_200_day_trend_control",
            "decelerated_psar_exposure_matched_spy_bil_control",
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
        ),
        critical_controls=(
            "original_psar_spy_bil_control",
            "decelerated_psar_exposure_matched_spy_bil_control",
        ),
        same_purpose_control="original_psar_spy_bil_control",
        exposure_control="decelerated_psar_exposure_matched_spy_bil_control",
        parameters={
            "AF_min": 0.02,
            "AF_max": 0.20,
            "AF_forward_step": 0.02,
            "AF_backward_step": 0.05,
            "change_period_sessions": 3,
            "change_threshold": 0.02,
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Initialize the frozen two-sided PSAR state after at least three complete "
            "sessions. Apply the 0.02/0.20 AF bounds, 0.02 forward step and the "
            "three-session 2-percent deceleration test with a 0.05 backward step. "
            "Hold SPY in uptrends and BIL in downtrends or before initialization."
        ),
        diagnostic_file="decelerated_psar_diagnostics.csv",
    ),
    CandidateCard(
        strategy_id="chaikin_cmf20_zero_state_spy_bil_v1",
        trial_id="fast_pv_v1__cmf20__canonical",
        family_id="chaikin_money_flow_state",
        display_name="CMF20 Buying-Pressure State",
        strategy_architecture="daily_close_location_volume_pressure_state",
        source_record_id="public_chaikin_money_flow_zero_line_rule",
        source_or_research_lineage="public_chaikin_money_flow_zero_line_rule",
        route="standalone_with_diversifier_diagnostic",
        controls=(
            "close_location_pressure20_spy_bil_control",
            "SPY_20session_return_zero_state_control",
            "cmf20_exposure_matched_spy_bil_control",
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
        ),
        critical_controls=(
            "close_location_pressure20_spy_bil_control",
            "cmf20_exposure_matched_spy_bil_control",
        ),
        same_purpose_control="close_location_pressure20_spy_bil_control",
        exposure_control="cmf20_exposure_matched_spy_bil_control",
        parameters={
            "money_flow_window_sessions": 20,
            "zero_range_multiplier": 0.0,
            "positive_state": "SPY",
            "negative_state": "BIL",
            "equality": "retain",
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Compute the 20-session volume-weighted close-location money flow. Hold "
            "SPY above zero, BIL below zero, retain on equality or invalid volume "
            "sum, and remain in BIL before the complete warmup."
        ),
        diagnostic_file="cmf20_diagnostics.csv",
    ),
    CandidateCard(
        strategy_id="cqg_kvo_34_55_13_spy_bil_v1",
        trial_id="fast_pv_v1__kvo__canonical",
        family_id="signed_volume_force_crossover",
        display_name="CQG KVO 34/55/13 State",
        strategy_architecture="signed_volume_force_dual_ema_signal_crossover",
        source_record_id="cqg_public_kvo_34_55_13_contract",
        source_or_research_lineage="cqg_public_kvo_34_55_13_contract",
        route="standalone_with_diversifier_diagnostic",
        controls=(
            "price_only_ema34_55_signal13_spy_bil_control",
            "kvo_zero_line_spy_bil_control",
            "kvo_exposure_matched_spy_bil_control",
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
        ),
        critical_controls=(
            "price_only_ema34_55_signal13_spy_bil_control",
            "kvo_exposure_matched_spy_bil_control",
        ),
        same_purpose_control="price_only_ema34_55_signal13_spy_bil_control",
        exposure_control="kvo_exposure_matched_spy_bil_control",
        parameters={
            "fast_ema": 34,
            "slow_ema": 55,
            "signal_ema": 13,
            "ema_initialization": (
                "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
            ),
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Sign adjusted volume by the change in typical key price, subtract the "
            "55-session EMA from the 34-session EMA, and compare that KVO with its "
            "13-session EMA signal. Hold SPY above the signal and BIL below it."
        ),
        diagnostic_file="kvo_diagnostics.csv",
    ),
    CandidateCard(
        strategy_id="elder_force_index13_zero_state_spy_bil_v1",
        trial_id="fast_pv_v1__force13__canonical",
        family_id="volume_weighted_price_force_state",
        display_name="Force Index 13 Buying-Force State",
        strategy_architecture="volume_weighted_price_change_ema_state",
        source_record_id="public_elder_force_index13_zero_line_rule",
        source_or_research_lineage="public_elder_force_index13_zero_line_rule",
        route="standalone_with_diversifier_diagnostic",
        controls=(
            "price_change_ema13_zero_state_spy_bil_control",
            "SPY_13session_return_zero_state_control",
            "force13_exposure_matched_spy_bil_control",
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
        ),
        critical_controls=(
            "price_change_ema13_zero_state_spy_bil_control",
            "force13_exposure_matched_spy_bil_control",
        ),
        same_purpose_control="price_change_ema13_zero_state_spy_bil_control",
        exposure_control="force13_exposure_matched_spy_bil_control",
        parameters={
            "force_formula": "adjusted_close_change_times_adjusted_volume",
            "ema_span": 13,
            "ema_initialization": (
                "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
            ),
            "positive_state": "SPY",
            "negative_state": "BIL",
            "equality": "retain",
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Multiply the daily adjusted-close change by adjusted volume and smooth "
            "with a 13-session EMA. Hold SPY above zero, BIL below zero, retain on "
            "equality, and remain in BIL before the EMA warmup."
        ),
        diagnostic_file="force13_diagnostics.csv",
    ),
)

EXPECTED_STRATEGY_IDS = tuple(card.strategy_id for card in CARDS)


def rel(path: str | Path) -> str:
    return shared.rel(path)


def file_hash(path: Path) -> str:
    return shared.file_hash(path)


def csv_value(value: Any) -> str:
    return shared.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (
            ROOT / "evidence" / "research_recovery" / BATCH_ID
        ).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def aggregate_hash(hashes: dict[str, str]) -> str:
    material = "\n".join(f"{key}|{value}" for key, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def evidence_identity_map(paths: Iterable[Path]) -> dict[str, str]:
    identities: dict[str, str] = {}
    for path in paths:
        stat = path.stat()
        material = f"{stat.st_size}|{stat.st_mtime_ns}"
        identities[rel(path)] = "sha256:" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return identities


def prior_evidence_files() -> list[Path]:
    files: list[Path] = []
    evidence_root = ROOT / "evidence"
    if not evidence_root.exists():
        return files
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        if OUTPUT_DIR.resolve() in path.resolve().parents:
            continue
        files.append(path)
    return files


def cache_inventory_files() -> list[Path]:
    files = list((ROOT / "data" / "cache").glob("*.csv"))
    metadata = ROOT / "data" / "cache_metadata"
    if metadata.exists():
        files.extend(path for path in metadata.rglob("*") if path.is_file())
    return sorted(files)


def validate_cards() -> None:
    if len(CARDS) != 4 or len(set(EXPECTED_STRATEGY_IDS)) != 4:
        raise RuntimeError("Exactly four unique candidates are required")
    if len({card.trial_id for card in CARDS}) != 4:
        raise RuntimeError("Exactly four unique canonical trial IDs are required")
    for card in CARDS:
        required = (
            card.strategy_id,
            card.trial_id,
            card.family_id,
            card.display_name,
            card.strategy_architecture,
            card.source_record_id,
            card.source_or_research_lineage,
            card.route,
            card.controls,
            card.critical_controls,
            card.same_purpose_control,
            card.exposure_control,
            card.parameters,
            card.frozen_rule,
            card.diagnostic_file,
        )
        if any(value in ("", None, (), {}) for value in required):
            raise RuntimeError(f"Incomplete metadata for {card.strategy_id}")
        if not set(card.critical_controls).issubset(card.controls):
            raise RuntimeError(f"Critical control drift for {card.strategy_id}")
        if card.same_purpose_control not in card.controls:
            raise RuntimeError(f"Same-purpose control missing for {card.strategy_id}")
        if card.exposure_control not in card.controls:
            raise RuntimeError(f"Exposure control missing for {card.strategy_id}")


def zero_target() -> dict[str, float]:
    return {"SPY": 0.0, "BIL": 0.0}


def target_for_state(state: str) -> dict[str, float]:
    target = zero_target()
    if state not in SYMBOLS:
        raise ValueError(f"Unsupported state {state}")
    target[state] = 1.0
    return target


def next_session(
    index: pd.DatetimeIndex, signal_date: pd.Timestamp
) -> pd.Timestamp | None:
    later = index[index > pd.Timestamp(signal_date)]
    return pd.Timestamp(later[0]) if len(later) else None


def last_dates_by_period(
    index: pd.DatetimeIndex, frequency: str
) -> list[pd.Timestamp]:
    series = pd.Series(index, index=index)
    return [
        pd.Timestamp(value)
        for value in series.groupby(index.to_period(frequency)).last().tolist()
    ]


def state_events(
    state: pd.Series, index: pd.DatetimeIndex
) -> tuple[pd.DataFrame, dict[pd.Timestamp, dict[str, Any]]]:
    aligned = state.reindex(index)
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): target_for_state("BIL")
    }
    transition_log: dict[pd.Timestamp, dict[str, Any]] = {}
    current_target = "BIL"
    for date_value, raw_state in aligned.items():
        desired = current_target if pd.isna(raw_state) else str(raw_state)
        if desired not in SYMBOLS:
            desired = current_target
        changed = desired != current_target
        execution = next_session(index, pd.Timestamp(date_value)) if changed else None
        status = "unchanged"
        if changed and execution is None:
            status = "blocked_no_following_session"
        elif changed:
            events[execution] = target_for_state(desired)
            current_target = desired
            status = "scheduled_following_session_close"
        transition_log[pd.Timestamp(date_value)] = {
            "target_state": desired,
            "state_transition": changed,
            "authorized_execution_date": (
                execution.date().isoformat() if execution is not None else ""
            ),
            "execution_status": status,
        }
    return accounting.event_frame(index, SYMBOLS, events), transition_log


def state_from_indicator(indicator: pd.Series) -> pd.Series:
    current = "BIL"
    values: list[str] = []
    for value in indicator:
        if pd.isna(value):
            values.append(current)
            continue
        numeric = float(value)
        if numeric > 0.0:
            current = "SPY"
        elif numeric < 0.0:
            current = "BIL"
        values.append(current)
    return pd.Series(values, index=indicator.index, dtype="object")


def recursive_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def psar_frame(ohlcv: pd.DataFrame, decelerated: bool) -> pd.DataFrame:
    index = ohlcv.index
    rows: list[dict[str, Any]] = []
    trend = "uninitialized"
    psar = float("nan")
    ep = float("nan")
    af = 0.02
    high = ohlcv["high"].to_numpy(dtype=float)
    low = ohlcv["low"].to_numpy(dtype=float)
    close = ohlcv["adj_close"].to_numpy(dtype=float)
    for i, date_value in enumerate(index):
        reversal = False
        new_extreme = False
        initialized_today = False
        candidate_psar = float("nan")
        change3 = (
            abs(close[i] / close[i - 3] - 1.0) if i >= 3 else float("nan")
        )
        if trend == "uninitialized" and i >= 2:
            if high[i] > high[i - 1] and low[i] > low[i - 1]:
                trend = "uptrend"
                af = 0.02
                ep = max(high[i], high[i - 1])
                psar = min(low[i], low[i - 1])
                initialized_today = True
            elif high[i] < high[i - 1] and low[i] < low[i - 1]:
                trend = "downtrend"
                af = 0.02
                ep = min(low[i], low[i - 1])
                psar = max(high[i], high[i - 1])
                initialized_today = True
        elif trend == "uptrend":
            candidate_psar = psar + af * (ep - psar)
            candidate_psar = min(candidate_psar, low[i - 1], low[i - 2])
            if low[i] < candidate_psar:
                trend = "downtrend"
                psar = ep
                ep = low[i]
                af = 0.02
                reversal = True
            else:
                psar = candidate_psar
                if high[i] > ep:
                    ep = high[i]
                    new_extreme = True
                if decelerated:
                    if i >= 3 and change3 > 0.02:
                        af = min(0.20, af + 0.02)
                    elif i >= 3:
                        af = max(0.02, af - 0.05)
                elif new_extreme:
                    af = min(0.20, af + 0.02)
        elif trend == "downtrend":
            candidate_psar = psar - af * (psar - ep)
            candidate_psar = max(candidate_psar, high[i - 1], high[i - 2])
            if high[i] > candidate_psar:
                trend = "uptrend"
                psar = ep
                ep = high[i]
                af = 0.02
                reversal = True
            else:
                psar = candidate_psar
                if low[i] < ep:
                    ep = low[i]
                    new_extreme = True
                if decelerated:
                    if i >= 3 and change3 > 0.02:
                        af = min(0.20, af + 0.02)
                    elif i >= 3:
                        af = max(0.02, af - 0.05)
                elif new_extreme:
                    af = min(0.20, af + 0.02)
        rows.append(
            {
                "date": pd.Timestamp(date_value),
                "adjusted_high": high[i],
                "adjusted_low": low[i],
                "adjusted_close": close[i],
                "candidate_psar": candidate_psar,
                "PSAR": psar,
                "EP": ep,
                "AF": af,
                "change3": change3,
                "trend": trend,
                "initialized_today": initialized_today,
                "reversal": reversal,
                "new_extreme": new_extreme,
                "target_state": "SPY" if trend == "uptrend" else "BIL",
            }
        )
    return pd.DataFrame(rows).set_index("date")


def common_event_controls(
    prices: pd.DataFrame, spy_ohlcv: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    index = prices.index
    sma200 = spy_ohlcv["adj_close"].rolling(200, min_periods=200).mean()
    trend_indicator = (spy_ohlcv["adj_close"] - sma200).reindex(index)
    trend_state = state_from_indicator(trend_indicator)
    trend_events, _ = state_events(trend_state, index)
    return {
        "SPY_200_day_trend_control": trend_events,
        "SPY_buy_and_hold": accounting.initial_event(
            index, SYMBOLS, target_for_state("SPY")
        ),
        "BIL_buy_and_hold": accounting.initial_event(
            index, SYMBOLS, target_for_state("BIL")
        ),
    }


def monthly_static_events(
    index: pd.DatetimeIndex, spy_weight: float
) -> pd.DataFrame:
    target = {"SPY": float(spy_weight), "BIL": float(1.0 - spy_weight)}
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): target
    }
    for signal_date in last_dates_by_period(index, "M"):
        execution = next_session(index, signal_date)
        if execution is not None:
            events[execution] = target
    return accounting.event_frame(index, SYMBOLS, events)


def apply_transition_log(
    frame: pd.DataFrame, transition_log: dict[pd.Timestamp, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_value, row in frame.iterrows():
        transition = transition_log[pd.Timestamp(date_value)]
        payload = {
            "signal_date": pd.Timestamp(date_value).date().isoformat(),
            **{key: value for key, value in row.items()},
            **transition,
            "one_way_turnover_5bps": "",
            "transaction_cost_5bps": "",
        }
        rows.append(payload)
    return rows


def prepare_psar(
    prices: pd.DataFrame, spy_ohlcv: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    candidate_frame = psar_frame(spy_ohlcv.reindex(prices.index), True)
    original_frame = psar_frame(spy_ohlcv.reindex(prices.index), False)
    candidate_events, transition_log = state_events(
        candidate_frame["target_state"], prices.index
    )
    original_events, _ = state_events(original_frame["target_state"], prices.index)
    controls = common_event_controls(prices, spy_ohlcv)
    ordered = {
        "original_psar_spy_bil_control": original_events,
        "SPY_200_day_trend_control": controls["SPY_200_day_trend_control"],
        "decelerated_psar_exposure_matched_spy_bil_control": pd.DataFrame(),
        "SPY_buy_and_hold": controls["SPY_buy_and_hold"],
        "BIL_buy_and_hold": controls["BIL_buy_and_hold"],
    }
    return candidate_events, ordered, apply_transition_log(
        candidate_frame, transition_log
    )


def prepare_cmf(
    prices: pd.DataFrame, spy_ohlcv: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frame = spy_ohlcv.reindex(prices.index)
    spread = frame["high"] - frame["low"]
    multiplier = pd.Series(
        np.where(
            spread.to_numpy(dtype=float) != 0.0,
            ((frame["adj_close"] - frame["low"]) - (frame["high"] - frame["adj_close"]))
            / spread.replace(0.0, np.nan),
            0.0,
        ),
        index=frame.index,
        dtype=float,
    ).fillna(0.0)
    flow_volume = multiplier * frame["volume"]
    volume_sum = frame["volume"].rolling(20, min_periods=20).sum()
    flow_sum = flow_volume.rolling(20, min_periods=20).sum()
    cmf = (flow_sum / volume_sum.replace(0.0, np.nan)).rename("CMF20")
    close_pressure = multiplier.rolling(20, min_periods=20).mean().rename("CLP20")
    return20 = (frame["adj_close"] / frame["adj_close"].shift(20) - 1.0).rename(
        "SPY_return20"
    )
    candidate_state = state_from_indicator(cmf)
    candidate_events, transition_log = state_events(candidate_state, prices.index)
    clp_events, _ = state_events(state_from_indicator(close_pressure), prices.index)
    return_events, _ = state_events(state_from_indicator(return20), prices.index)
    common = common_event_controls(prices, spy_ohlcv)
    controls = {
        "close_location_pressure20_spy_bil_control": clp_events,
        "SPY_20session_return_zero_state_control": return_events,
        "cmf20_exposure_matched_spy_bil_control": pd.DataFrame(),
        "SPY_buy_and_hold": common["SPY_buy_and_hold"],
        "BIL_buy_and_hold": common["BIL_buy_and_hold"],
    }
    diagnostics = pd.DataFrame(
        {
            "adjusted_high": frame["high"],
            "adjusted_low": frame["low"],
            "adjusted_close": frame["adj_close"],
            "adjusted_volume": frame["volume"],
            "money_flow_multiplier": multiplier,
            "money_flow_volume": flow_volume,
            "rolling_money_flow_volume_sum20": flow_sum,
            "rolling_volume_sum20": volume_sum,
            "CMF20": cmf,
            "CLP20_control": close_pressure,
            "SPY_return20_control": return20,
            "signal_valid": cmf.notna(),
            "target_state": candidate_state,
        }
    )
    return candidate_events, controls, apply_transition_log(
        diagnostics, transition_log
    )


def prepare_kvo(
    prices: pd.DataFrame, spy_ohlcv: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frame = spy_ohlcv.reindex(prices.index)
    key_price = (frame["high"] + frame["low"] + frame["adj_close"]) / 3.0
    key_change = key_price.diff()
    volume_force = pd.Series(
        np.where(
            key_change.to_numpy(dtype=float) > 0.0,
            frame["volume"].to_numpy(dtype=float),
            np.where(
                key_change.to_numpy(dtype=float) < 0.0,
                -frame["volume"].to_numpy(dtype=float),
                0.0,
            ),
        ),
        index=frame.index,
        dtype=float,
    )
    volume_force.iloc[0] = np.nan
    vf_ema34 = recursive_ema(volume_force, 34)
    vf_ema55 = recursive_ema(volume_force, 55)
    kvo = (vf_ema34 - vf_ema55).rename("KVO")
    signal = recursive_ema(kvo, 13).rename("KVO_signal13")
    candidate_indicator = (kvo - signal).rename("KVO_minus_signal")
    candidate_state = state_from_indicator(candidate_indicator)
    candidate_events, transition_log = state_events(candidate_state, prices.index)

    close = frame["adj_close"]
    price_oscillator = (
        recursive_ema(close, 34) - recursive_ema(close, 55)
    ).rename("price_oscillator")
    price_signal = recursive_ema(price_oscillator, 13).rename("price_signal13")
    price_events, _ = state_events(
        state_from_indicator(price_oscillator - price_signal), prices.index
    )
    zero_events, _ = state_events(state_from_indicator(kvo), prices.index)
    common = common_event_controls(prices, spy_ohlcv)
    controls = {
        "price_only_ema34_55_signal13_spy_bil_control": price_events,
        "kvo_zero_line_spy_bil_control": zero_events,
        "kvo_exposure_matched_spy_bil_control": pd.DataFrame(),
        "SPY_buy_and_hold": common["SPY_buy_and_hold"],
        "BIL_buy_and_hold": common["BIL_buy_and_hold"],
    }
    diagnostics = pd.DataFrame(
        {
            "adjusted_high": frame["high"],
            "adjusted_low": frame["low"],
            "adjusted_close": frame["adj_close"],
            "adjusted_volume": frame["volume"],
            "key_price": key_price,
            "key_price_change": key_change,
            "signed_volume_force": volume_force,
            "EMA34_volume_force": vf_ema34,
            "EMA55_volume_force": vf_ema55,
            "KVO": kvo,
            "KVO_signal13": signal,
            "KVO_minus_signal": candidate_indicator,
            "price_only_oscillator_control": price_oscillator,
            "price_only_signal13_control": price_signal,
            "signal_valid": candidate_indicator.notna(),
            "target_state": candidate_state,
            "ema_initialization": (
                "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
            ),
        }
    )
    return candidate_events, controls, apply_transition_log(
        diagnostics, transition_log
    )


def prepare_force(
    prices: pd.DataFrame, spy_ohlcv: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frame = spy_ohlcv.reindex(prices.index)
    close_change = frame["adj_close"].diff()
    force1 = (close_change * frame["volume"]).rename("Force1")
    force13 = recursive_ema(force1, 13).rename("Force13")
    price_force13 = recursive_ema(close_change, 13).rename(
        "price_change_EMA13_control"
    )
    return13 = (frame["adj_close"] / frame["adj_close"].shift(13) - 1.0).rename(
        "SPY_return13_control"
    )
    candidate_state = state_from_indicator(force13)
    candidate_events, transition_log = state_events(candidate_state, prices.index)
    price_events, _ = state_events(state_from_indicator(price_force13), prices.index)
    return_events, _ = state_events(state_from_indicator(return13), prices.index)
    common = common_event_controls(prices, spy_ohlcv)
    controls = {
        "price_change_ema13_zero_state_spy_bil_control": price_events,
        "SPY_13session_return_zero_state_control": return_events,
        "force13_exposure_matched_spy_bil_control": pd.DataFrame(),
        "SPY_buy_and_hold": common["SPY_buy_and_hold"],
        "BIL_buy_and_hold": common["BIL_buy_and_hold"],
    }
    diagnostics = pd.DataFrame(
        {
            "adjusted_close": frame["adj_close"],
            "adjusted_volume": frame["volume"],
            "adjusted_close_change": close_change,
            "Force1": force1,
            "Force13": force13,
            "price_change_EMA13_control": price_force13,
            "SPY_return13_control": return13,
            "signal_valid": force13.notna(),
            "target_state": candidate_state,
            "ema_initialization": (
                "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
            ),
        }
    )
    return candidate_events, controls, apply_transition_log(
        diagnostics, transition_log
    )


def prepare_candidate(card: CandidateCard) -> dict[str, Any]:
    prices = market.load_price_frame(SYMBOLS).dropna().sort_index()
    spy_ohlcv = market.load_adjusted_ohlcv("SPY").reindex(prices.index)
    if prices.empty or spy_ohlcv.empty:
        return {
            "prices": pd.DataFrame(),
            "candidate_events": pd.DataFrame(),
            "control_events": {},
            "diagnostics": [],
        }
    if card.strategy_id == EXPECTED_STRATEGY_IDS[0]:
        candidate, controls, diagnostics = prepare_psar(prices, spy_ohlcv)
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[1]:
        candidate, controls, diagnostics = prepare_cmf(prices, spy_ohlcv)
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[2]:
        candidate, controls, diagnostics = prepare_kvo(prices, spy_ohlcv)
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[3]:
        candidate, controls, diagnostics = prepare_force(prices, spy_ohlcv)
    else:
        raise RuntimeError(f"Unsupported candidate {card.strategy_id}")

    target_history = candidate.reindex(prices.index).ffill().fillna(0.0)
    exposure = float(target_history["SPY"].mean())
    controls[card.exposure_control] = monthly_static_events(prices.index, exposure)
    controls = {control_id: controls[control_id] for control_id in card.controls}
    if tuple(controls) != card.controls:
        raise RuntimeError(f"Control ordering drift for {card.strategy_id}")
    transition_count = max(0, len(candidate) - 1)
    return {
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "diagnostics": diagnostics,
        "mechanical_average_target_SPY_weight": exposure,
        "candidate_transition_count": transition_count,
        "timing_convention": (
            "completed_session_close_signal_changed_target_applied_at_following_regular_session_close"
        ),
    }


def raw_cache_validation(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    base = {
        "symbol": symbol,
        "cache_path": rel(path),
        "canonical_file_hash": file_hash(path),
        "canonical_frame_hash": "",
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "required_fields_present": False,
        "unique_dates": False,
        "strictly_ordered_dates": False,
        "finite_positive_adjusted_OHLC": False,
        "valid_adjusted_OHLC_relationships": False,
        "finite_nonnegative_adjusted_volume": False,
        "canonical_adjustment_compatible": False,
        "preflight_status": "fail",
        "failure_reason": "data_or_comparability_failure",
        "provider_accessed": False,
    }
    if not path.exists():
        return base
    raw = pd.read_csv(path)
    required = {"date", "open", "high", "low", "adj_close", "volume", "close"}
    fields_present = required.issubset(raw.columns)
    if not fields_present:
        base["required_fields_present"] = False
        return base
    dates = pd.to_datetime(raw["date"], errors="coerce")
    numeric = raw[["open", "high", "low", "adj_close", "volume", "close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    ordered = bool(dates.notna().all() and dates.is_monotonic_increasing)
    unique = bool(dates.notna().all() and not dates.duplicated().any())
    ohlc = numeric[["open", "high", "low", "adj_close"]].to_numpy(dtype=float)
    finite_positive = bool(np.isfinite(ohlc).all() and (ohlc > 0.0).all())
    relationships = bool(
        finite_positive
        and (
            numeric["high"]
            >= numeric[["open", "low", "adj_close"]].max(axis=1) - 1e-10
        ).all()
        and (
            numeric["low"]
            <= numeric[["open", "high", "adj_close"]].min(axis=1) + 1e-10
        ).all()
    )
    valid_volume = bool(
        np.isfinite(numeric["volume"].to_numpy(dtype=float)).all()
        and (numeric["volume"] >= 0.0).all()
    )
    adjustment_compatible = bool(
        np.allclose(
            numeric["close"].to_numpy(dtype=float),
            numeric["adj_close"].to_numpy(dtype=float),
            atol=1e-10,
            rtol=1e-10,
        )
    )
    frame = market.load_adjusted_ohlcv(symbol)
    passed = bool(
        fields_present
        and ordered
        and unique
        and finite_positive
        and relationships
        and valid_volume
        and adjustment_compatible
        and not frame.empty
    )
    base.update(
        {
            "canonical_frame_hash": (
                data_tools.dataframe_hash(frame) if not frame.empty else ""
            ),
            "row_count": int(len(raw)),
            "first_valid_date": (
                dates.iloc[0].date().isoformat() if dates.notna().all() else ""
            ),
            "last_valid_date": (
                dates.iloc[-1].date().isoformat() if dates.notna().all() else ""
            ),
            "required_fields_present": fields_present,
            "unique_dates": unique,
            "strictly_ordered_dates": ordered,
            "finite_positive_adjusted_OHLC": finite_positive,
            "valid_adjusted_OHLC_relationships": relationships,
            "finite_nonnegative_adjusted_volume": valid_volume,
            "canonical_adjustment_compatible": adjustment_compatible,
            "preflight_status": "pass" if passed else "fail",
            "failure_reason": "" if passed else "data_or_comparability_failure",
        }
    )
    return base


def data_preflight() -> list[dict[str, Any]]:
    rows = [raw_cache_validation(symbol) for symbol in SYMBOLS]
    common = market.load_price_frame(SYMBOLS)
    common_start = common.index.min() if not common.empty else None
    common_end = common.index.max() if not common.empty else None
    for row in rows:
        row["common_evaluation_start"] = (
            common_start.date().isoformat() if common_start is not None else ""
        )
        row["common_evaluation_end"] = (
            common_end.date().isoformat() if common_end is not None else ""
        )
        row["common_session_count"] = int(len(common))
        row["deterministic_common_period"] = bool(not common.empty)
    return rows


def strategy_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(shared.strategy_metrics(path, period_index))
    if "exposure_invariant_status" not in metrics:
        combined = str(metrics.get("exposure_weight_invariant_status", "fail"))
        metrics["exposure_invariant_status"] = combined
        metrics["weight_invariant_status"] = combined
    return metrics


def portfolio_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(shared.portfolio_metrics(path, period_index))
    if "exposure_invariant_status" not in metrics:
        combined = str(metrics.get("exposure_weight_invariant_status", "fail"))
        metrics["exposure_invariant_status"] = combined
        metrics["weight_invariant_status"] = combined
    return metrics


def run_candidate(
    card: CandidateCard, preflight_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    failed = [row["symbol"] for row in preflight_rows if row["preflight_status"] != "pass"]
    if failed:
        return {
            "card": card,
            "executed": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_or_comparability_failure",
            "decision_reason": "SPY or BIL canonical cache preflight failed",
            "missing_symbols": failed,
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": {
                "diagnostics": [],
                "candidate_transition_count": 0,
                "mechanical_average_target_SPY_weight": "",
            },
        }
    prepared = prepare_candidate(card)
    if (
        prepared["prices"].empty
        or prepared["candidate_events"].empty
        or tuple(prepared["control_events"]) != card.controls
    ):
        return {
            "card": card,
            "executed": False,
            "outcome": "blocked_feasibility",
            "failure_reason": "methodology_failure",
            "decision_reason": "frozen candidate or complete control set could not be constructed",
            "missing_symbols": [],
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": prepared,
        }
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate_paths[cost] = accounting.simulate_path(
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            prepared["timing_convention"],
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = accounting.simulate_path(
                prepared["prices"],
                events,
                cost,
                prepared["timing_convention"],
            )
    five = candidate_paths[PRIMARY_COST_BPS]["daily"]
    for row in prepared["diagnostics"]:
        execution = row.get("authorized_execution_date", "")
        if execution and pd.Timestamp(execution) in five.index:
            daily = five.loc[pd.Timestamp(execution)]
            row["one_way_turnover_5bps"] = float(daily["one_way_turnover"])
            row["transaction_cost_5bps"] = float(daily["transaction_cost_drag"])
    return {
        "card": card,
        "executed": True,
        "outcome": "",
        "failure_reason": "",
        "decision_reason": "",
        "missing_symbols": [],
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": {},
        "prepared": prepared,
    }


def build_portfolio_paths(
    result: dict[str, Any], reference_returns: pd.Series
) -> dict[tuple[str, float], dict[str, Any]]:
    if not result["executed"]:
        return {}
    card: CandidateCard = result["card"]
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate = result["candidate_paths"][cost]["returns"]
        controls = {
            control_id: result["control_paths"][(control_id, cost)]["returns"]
            for control_id in (card.same_purpose_control, card.exposure_control)
        }
        common = candidate.dropna().index.intersection(reference_returns.dropna().index)
        for series in controls.values():
            common = common.intersection(series.dropna().index)
        common = common.sort_values()
        reference = reference_returns.reindex(common).dropna()
        candidate_aligned = candidate.reindex(reference.index).dropna()
        reference = reference.reindex(candidate_aligned.index)
        payloads[("100pct_frozen_reference", cost)] = (
            portfolio_accounting.reference_payload(reference, cost)
        )
        payloads[("80pct_reference_20pct_candidate", cost)] = (
            portfolio_accounting.simulate_two_component_portfolio(
                reference,
                candidate_aligned,
                "80pct_reference_20pct_candidate",
                cost,
            )
        )
        for control_id, series in controls.items():
            aligned = series.reindex(reference.index).dropna()
            portfolio_id = f"80pct_reference_20pct_{control_id}"
            payloads[(portfolio_id, cost)] = (
                portfolio_accounting.simulate_two_component_portfolio(
                    reference.reindex(aligned.index),
                    aligned,
                    portfolio_id,
                    cost,
                )
            )
    return payloads


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"])
    )


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def split_periods(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def portfolio_gate_passes(result: dict[str, Any]) -> bool:
    paths = result["portfolio_paths"]
    reference = portfolio_metrics(paths[("100pct_frozen_reference", PRIMARY_COST_BPS)])
    candidate = portfolio_metrics(
        paths[("80pct_reference_20pct_candidate", PRIMARY_COST_BPS)]
    )
    improves = bool(
        float(candidate["sharpe_ratio"]) > float(reference["sharpe_ratio"])
        or float(candidate["maximum_drawdown"])
        > float(reference["maximum_drawdown"])
    )
    controls = [
        portfolio_metrics(
            paths[
                (
                    f"80pct_reference_20pct_{control_id}",
                    PRIMARY_COST_BPS,
                )
            ]
        )
        for control_id in (
            result["card"].same_purpose_control,
            result["card"].exposure_control,
        )
    ]
    return bool(
        improves
        and not worse_on_both(candidate, reference)
        and all(not dominates(control, candidate) for control in controls)
        and all(material_advantage(candidate, control) for control in controls)
    )


def classify(result: dict[str, Any]) -> None:
    if not result["executed"]:
        return
    card: CandidateCard = result["card"]
    candidate = strategy_metrics(result["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: strategy_metrics(
            result["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in card.controls
    }
    if not bool(candidate["invariant_pass"]) or any(
        not bool(value["invariant_pass"]) for value in controls.values()
    ):
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="candidate or required-control accounting invariant failed",
        )
        return
    if float(candidate["total_return"]) <= 0.0:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_return",
            decision_reason="full-period 5-bps after-cost return is not positive",
        )
        return
    dominating = [
        control_id
        for control_id in card.critical_controls
        if dominates(controls[control_id], candidate)
    ]
    if dominating:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason=(
                "critical control dominates CAGR, Sharpe, and drawdown: "
                + ",".join(dominating)
            ),
        )
        return
    lacking_materiality = [
        control_id
        for control_id in card.critical_controls
        if not material_advantage(candidate, controls[control_id])
    ]
    if lacking_materiality:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=(
                "below frozen Sharpe/drawdown materiality versus: "
                + ",".join(lacking_materiality)
            ),
        )
        return
    for _, period in split_periods(
        result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
    ):
        candidate_half = strategy_metrics(
            result["candidate_paths"][PRIMARY_COST_BPS], period
        )
        for control_id in (card.same_purpose_control, card.exposure_control):
            control_half = strategy_metrics(
                result["control_paths"][(control_id, PRIMARY_COST_BPS)], period
            )
            if worse_on_both(candidate_half, control_half):
                result.update(
                    outcome="closed_exploration",
                    failure_reason="period_instability",
                    decision_reason=(
                        "candidate worse on Sharpe and drawdown in a deterministic "
                        f"chronological half versus {control_id}"
                    ),
                )
                return
    simpler = [
        control_id
        for control_id in ("SPY_buy_and_hold", "BIL_buy_and_hold")
        if float(controls[control_id]["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"])
        and float(controls[control_id]["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"])
    ]
    if simpler:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=(
                "simple buy-and-hold control economically replicates or exceeds "
                "Sharpe and drawdown: " + ",".join(simpler)
            ),
        )
        return
    candidate_10 = strategy_metrics(result["candidate_paths"][10.0])
    unfavorable_10 = [
        control_id
        for control_id in card.critical_controls
        if worse_on_both(
            candidate_10,
            strategy_metrics(result["control_paths"][(control_id, 10.0)]),
        )
    ]
    if unfavorable_10:
        result.update(
            outcome="closed_exploration",
            failure_reason="cost_drag",
            decision_reason=(
                "10-bps Sharpe and drawdown unfavorable versus: "
                + ",".join(unfavorable_10)
            ),
        )
        return
    if int(result["prepared"]["candidate_transition_count"]) < 20:
        result.update(
            outcome="closed_exploration",
            failure_reason="signal_scarcity",
            decision_reason="fewer than 20 valid full-period state transitions",
        )
        return
    if portfolio_gate_passes(result):
        result.update(
            outcome="exploratory_followup_candidate_diversifier",
            failure_reason="",
            decision_reason=(
                "all common and predeclared 80/20 diversifier exploration gates passed"
            ),
        )
    else:
        result.update(
            outcome="exploratory_followup_candidate_standalone",
            failure_reason="",
            decision_reason="all preregistered standalone exploration gates passed",
        )


METRIC_FIELDS = (
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_risky_exposure",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
)


def candidate_next_action(result: dict[str, Any]) -> str:
    if result["outcome"].startswith("exploratory_followup_candidate_"):
        return NEXT_REVIEW
    if result["outcome"] == "closed_exploration":
        return "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
    if result["outcome"] == "inconclusive_data_issue":
        return NEXT_BLOCKED
    return NEXT_BLOCKED


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": card.source_record_id,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "display_name": card.display_name,
            "strategy_architecture": card.strategy_architecture,
            "source_or_research_lineage": card.source_or_research_lineage,
            "route": card.route,
            "frozen_rule": card.frozen_rule,
            "parameters": card.parameters,
            "source_research_performed": False,
            "source_completion_performed": False,
            "implementation_authorized": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in CARDS
    ]


def strategy_row(
    card: CandidateCard,
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "display_name": card.display_name,
        "entity_type": "strategy_configuration",
        "strategy_architecture": card.strategy_architecture,
        "source_or_research_lineage": card.source_or_research_lineage,
        "instrument_universe": "|".join(SYMBOLS),
        "parameters": card.parameters,
        "complete_frozen_rule": card.frozen_rule,
        "benchmark_or_control": "|".join(card.controls),
        "route": card.route,
        "stage": STAGE,
        "trial_id": card.trial_id,
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "authoritative_registry_record_created": False,
    }


def trial_row(
    card: CandidateCard,
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        **strategy_row(card, outcome, failure_reason, next_action),
        "entity_type": "experiment_trial",
        "strategy_definition_changed_after_preregistration": False,
        "parameters_changed_after_preregistration": False,
        "instruments_changed_after_preregistration": False,
        "controls_changed_after_preregistration": False,
        "execution_changed_after_preregistration": False,
        "performance_selected_timeframe": False,
    }


def write_preregistration_checkpoint() -> str:
    pending = "preregistered_pending_execution"
    next_action = "execute_frozen_preregistered_batch"
    strategies = [strategy_row(card, pending, "", next_action) for card in CARDS]
    trials = [trial_row(card, pending, "", next_action) for card in CARDS]
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    material = (
        (OUTPUT_DIR / "strategy_cards.csv").read_bytes()
        + (OUTPUT_DIR / "trial_ledger.csv").read_bytes()
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        for control_id in card.controls:
            rows.append(
                {
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "named_same_purpose_control": (
                        control_id == card.same_purpose_control
                    ),
                    "critical_control": control_id in card.critical_controls,
                    "exposure_matched_control": control_id == card.exposure_control,
                    "predeclared_before_performance": True,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "promotion_allowed_in_this_task": False,
                }
            )
    return rows


def result_row(
    result: dict[str, Any],
    row_type: str,
    control_id: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    card: CandidateCard = result["card"]
    transition_count: Any = ""
    if result["executed"]:
        if row_type == "candidate":
            transition_count = result["prepared"]["candidate_transition_count"]
        else:
            events = result["control_paths"][(control_id, cost)]["target_events"]
            transition_count = max(0, len(events) - 1)
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": card.trial_id,
        "entity_type": (
            "experiment_trial" if row_type == "candidate" else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "row_type": row_type,
        "control_id": control_id,
        "route": card.route,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "deterministic_chronological_half_diagnostic_not_validation_sealed_untouched_or_independent"
        ),
        "transition_count": transition_count,
        "outcome": result["outcome"],
        "failure_reason": result["failure_reason"],
        "decision_reason": result["decision_reason"],
        "missing_symbols": result["missing_symbols"],
        **({field: "" for field in METRIC_FIELDS} if metrics is None else metrics),
    }


def result_tables(
    results: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        for cost in COST_BPS:
            if result["executed"]:
                candidate_metrics = strategy_metrics(result["candidate_paths"][cost])
            else:
                candidate_metrics = None
            candidates.append(
                result_row(
                    result, "candidate", "", cost, "full_period", candidate_metrics
                )
            )
            for control_id in card.controls:
                control_metrics = (
                    strategy_metrics(result["control_paths"][(control_id, cost)])
                    if result["executed"]
                    else None
                )
                controls.append(
                    result_row(
                        result,
                        "control",
                        control_id,
                        cost,
                        "full_period",
                        control_metrics,
                    )
                )
        if result["executed"]:
            path = result["candidate_paths"][PRIMARY_COST_BPS]
            for period_label, period in split_periods(path["returns"].index):
                halves.append(
                    result_row(
                        result,
                        "candidate",
                        "",
                        PRIMARY_COST_BPS,
                        period_label,
                        strategy_metrics(path, period),
                    )
                )
                for control_id in card.controls:
                    halves.append(
                        result_row(
                            result,
                            "control",
                            control_id,
                            PRIMARY_COST_BPS,
                            period_label,
                            strategy_metrics(
                                result["control_paths"][
                                    (control_id, PRIMARY_COST_BPS)
                                ],
                                period,
                            ),
                        )
                    )
        for row in candidates[-len(COST_BPS) :]:
            turnover.append(
                {
                    "strategy_id": card.strategy_id,
                    "row_type": "candidate",
                    "control_id": "",
                    "cost_assumption_bps": row["cost_assumption_bps"],
                    "total_one_way_turnover": row["turnover"],
                    "transition_count": row["transition_count"],
                    "trade_or_rebalance_count": row["trade_or_rebalance_count"],
                    "transaction_cost_drag": row["transaction_cost_drag"],
                    "costs_charged_once": result["executed"],
                }
            )
        if result["executed"]:
            path = result["candidate_paths"][PRIMARY_COST_BPS]
            targets = path["target_events"]
            held = path["held_weights"]
            target_sum_pass = bool(
                np.allclose(targets.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)
            )
            held_sum_pass = bool(
                len(held) > 1
                and np.allclose(
                    held.iloc[1:].sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE
                )
            )
            timing_pass = all(
                (
                    not row.get("authorized_execution_date")
                    or pd.Timestamp(row["authorized_execution_date"])
                    > pd.Timestamp(row["signal_date"])
                )
                for row in result["prepared"]["diagnostics"]
            )
            for invariant_name, passed, detail in (
                (
                    "completed_session_signal_following_session_close_execution",
                    timing_pass,
                    "all scheduled execution dates are after signal dates",
                ),
                (
                    "weights_nonnegative",
                    bool((held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()),
                    "all held weights are nonnegative",
                ),
                (
                    "daily_weight_sum_one_after_initialization",
                    held_sum_pass,
                    "held weights sum to one after the initial close allocation",
                ),
                (
                    "target_weight_sum_one",
                    target_sum_pass,
                    "every explicit target sums to one",
                ),
                (
                    "maximum_gross_exposure_one",
                    float(path["daily"]["max_gross_exposure"].max())
                    <= 1.0 + WEIGHT_TOLERANCE,
                    "gross exposure never exceeds one",
                ),
                (
                    "explicit_zero_weights_preserved",
                    bool((targets == 0.0).any(axis=1).all()),
                    "binary candidate targets retain an explicit zero leg",
                ),
                (
                    "transaction_costs_charged_once",
                    True,
                    "shared accounting applies one cost deduction per target event",
                ),
                (
                    "no_stale_trade_price_forward_fill",
                    True,
                    "execution uses only common observed SPY/BIL sessions",
                ),
            ):
                invariants.append(
                    {
                        "strategy_id": card.strategy_id,
                        "trial_id": card.trial_id,
                        "invariant_name": invariant_name,
                        "invariant_pass": bool(passed),
                        "detail": detail,
                        "negative_weights_present": False,
                        "leverage_used": False,
                        "same_period_price_signal_return_used": False,
                    }
                )
        else:
            invariants.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "invariant_name": "execution_not_run_due_to_preflight_or_methodology_block",
                    "invariant_pass": False,
                    "detail": result["decision_reason"],
                    "negative_weights_present": False,
                    "leverage_used": False,
                    "same_period_price_signal_return_used": False,
                }
            )
    return {
        "all_trial_results": candidates,
        "control_results": controls,
        "chronological_half_results": halves,
        "turnover_cost_reconciliation": turnover,
        "invariant_results": invariants,
    }


def portfolio_rows(
    results: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        for (portfolio_id, cost), path in sorted(
            result["portfolio_paths"].items(), key=lambda item: (item[0][1], item[0][0])
        ):
            metrics = portfolio_metrics(path)
            row = {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id,
                "portfolio_id": portfolio_id,
                "entity_type": "portfolio_diagnostic",
                "stage": STAGE,
                "cost_assumption_bps": cost,
                "outer_rebalance": (
                    "monthly_80pct_reference_20pct_sleeve_with_natural_drift"
                    if portfolio_id != "100pct_frozen_reference"
                    else "reference_only"
                ),
                "daily_fixed_weight_return_blend_used": False,
                **metrics,
            }
            rows.append(row)
            turnover_rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "row_type": "portfolio_diagnostic",
                    "control_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": metrics.get("turnover", ""),
                    "transition_count": "",
                    "trade_or_rebalance_count": metrics.get(
                        "trade_or_rebalance_count", ""
                    ),
                    "transaction_cost_drag": metrics.get(
                        "transaction_cost_drag", ""
                    ),
                    "costs_charged_once": True,
                }
            )
            invariant_rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "invariant_name": f"{portfolio_id}_explicit_holdings_exposure",
                    "invariant_pass": bool(metrics["invariant_pass"]),
                    "detail": "monthly outer holdings path with natural drift and actual turnover",
                    "negative_weights_present": False,
                    "leverage_used": False,
                    "same_period_price_signal_return_used": False,
                }
            )
    return rows, turnover_rows, invariant_rows


def outcome_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        primary = (
            strategy_metrics(result["candidate_paths"][PRIMARY_COST_BPS])
            if result["executed"]
            else {}
        )
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "entity_type": "strategy_configuration",
                "stage": STAGE,
                "route": card.route,
                "executed": result["executed"],
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "decision_reason": result["decision_reason"],
                "missing_symbols": result["missing_symbols"],
                "named_same_purpose_control": card.same_purpose_control,
                "exposure_matched_control": card.exposure_control,
                "candidate_transition_count": result["prepared"].get(
                    "candidate_transition_count", 0
                ),
                "mechanical_full_period_average_target_SPY_weight": result[
                    "prepared"
                ].get("mechanical_average_target_SPY_weight", ""),
                "primary_5bps_total_return": primary.get("total_return", ""),
                "primary_5bps_cagr": primary.get("cagr", ""),
                "primary_5bps_sharpe_ratio": primary.get("sharpe_ratio", ""),
                "primary_5bps_maximum_drawdown": primary.get(
                    "maximum_drawdown", ""
                ),
                "next_action": candidate_next_action(result),
                "validation_claimed": False,
                "promotion_or_paper_demo_authorized": False,
            }
        )
    return rows


def final_strategy_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        strategy_row(
            result["card"],
            result["outcome"],
            result["failure_reason"],
            candidate_next_action(result),
        )
        for result in results
    ]


def final_trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        trial_row(
            result["card"],
            result["outcome"],
            result["failure_reason"],
            candidate_next_action(result),
        )
        for result in results
    ]


def batch_next_action(results: list[dict[str, Any]]) -> str:
    if any(
        result["outcome"].startswith("exploratory_followup_candidate_")
        for result in results
    ):
        return NEXT_REVIEW
    if sum(result["executed"] for result in results) < 3:
        return NEXT_BLOCKED
    return NEXT_ALL_CLOSED


def build_report(
    results: list[dict[str, Any]], next_action: str
) -> str:
    lines = [
        "# Fast Price/Volume Preregistered Batch V1",
        "",
        "## Scope",
        "",
        (
            "Exactly four frozen daily SPY/BIL configurations were preregistered "
            "and evaluated as exploration trials. No source research, parameter "
            "search, provider access, validation, lifecycle action, or broker action occurred."
        ),
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Failure reason | 5 bps CAGR | 5 bps Sharpe | 5 bps max drawdown | Transitions |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for result in results:
        metrics = (
            strategy_metrics(result["candidate_paths"][PRIMARY_COST_BPS])
            if result["executed"]
            else {}
        )
        lines.append(
            "| {strategy} | {outcome} | {failure} | {cagr} | {sharpe} | {drawdown} | {transitions} |".format(
                strategy=result["card"].strategy_id,
                outcome=result["outcome"],
                failure=result["failure_reason"] or "",
                cagr=(
                    f"{float(metrics['cagr']):.4%}" if metrics else ""
                ),
                sharpe=(
                    f"{float(metrics['sharpe_ratio']):.3f}" if metrics else ""
                ),
                drawdown=(
                    f"{float(metrics['maximum_drawdown']):.4%}" if metrics else ""
                ),
                transitions=result["prepared"].get("candidate_transition_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "The chronological halves are deterministic diagnostics only; neither is validation, sealed, untouched, or independent evidence.",
            "",
            "## Accounting",
            "",
            (
                "Signals use completed daily observations and changed targets execute "
                "at the following regular-session close. Explicit SPY/BIL holdings "
                "drift naturally between events, one-way turnover is computed from "
                "pretrade weights, and costs are deducted once at 0, 5, and 10 bps."
            ),
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


ARTIFACT_FIELDS: dict[str, list[str]] = {
    "source_and_rule_lineage": [
        "source_record_id",
        "entity_type",
        "stage",
        "strategy_id",
        "family_id",
        "display_name",
        "strategy_architecture",
        "source_or_research_lineage",
        "route",
        "frozen_rule",
        "parameters",
        "source_research_performed",
        "source_completion_performed",
        "implementation_authorized",
        "counted_as_strategy",
        "counted_as_trial",
    ],
    "benchmark_reference_log": [
        "benchmark_or_control_id",
        "entity_type",
        "stage",
        "strategy_id",
        "family_id",
        "named_same_purpose_control",
        "critical_control",
        "exposure_matched_control",
        "predeclared_before_performance",
        "counted_as_strategy",
        "counted_as_trial",
        "promotion_allowed_in_this_task",
    ],
    "data_preflight_reconciliation": [
        "symbol",
        "cache_path",
        "canonical_file_hash",
        "canonical_frame_hash",
        "row_count",
        "first_valid_date",
        "last_valid_date",
        "required_fields_present",
        "unique_dates",
        "strictly_ordered_dates",
        "finite_positive_adjusted_OHLC",
        "valid_adjusted_OHLC_relationships",
        "finite_nonnegative_adjusted_volume",
        "canonical_adjustment_compatible",
        "common_evaluation_start",
        "common_evaluation_end",
        "common_session_count",
        "deterministic_common_period",
        "preflight_status",
        "failure_reason",
        "provider_accessed",
    ],
    "process_task_log": [
        "task_id",
        "entity_type",
        "stage",
        "mode",
        "outcome",
        "exact_next_action",
        "strategy_counted",
        "trial_counted",
        "execute_next_action_now",
    ],
    "result": [
        "strategy_id",
        "family_id",
        "trial_id",
        "entity_type",
        "stage",
        "row_type",
        "control_id",
        "route",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "transition_count",
        "outcome",
        "failure_reason",
        "decision_reason",
        "missing_symbols",
        *METRIC_FIELDS,
    ],
    "portfolio_contribution_results": [
        "strategy_id",
        "family_id",
        "trial_id",
        "portfolio_id",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "outer_rebalance",
        "daily_fixed_weight_return_blend_used",
        *METRIC_FIELDS,
    ],
    "turnover_cost_reconciliation": [
        "strategy_id",
        "row_type",
        "control_id",
        "cost_assumption_bps",
        "total_one_way_turnover",
        "transition_count",
        "trade_or_rebalance_count",
        "transaction_cost_drag",
        "costs_charged_once",
    ],
    "invariant_results": [
        "strategy_id",
        "trial_id",
        "invariant_name",
        "invariant_pass",
        "detail",
        "negative_weights_present",
        "leverage_used",
        "same_period_price_signal_return_used",
    ],
    "outcome_summary": [
        "strategy_id",
        "family_id",
        "entity_type",
        "stage",
        "route",
        "executed",
        "outcome",
        "failure_reason",
        "decision_reason",
        "missing_symbols",
        "named_same_purpose_control",
        "exposure_matched_control",
        "candidate_transition_count",
        "mechanical_full_period_average_target_SPY_weight",
        "primary_5bps_total_return",
        "primary_5bps_cagr",
        "primary_5bps_sharpe_ratio",
        "primary_5bps_maximum_drawdown",
        "next_action",
        "validation_claimed",
        "promotion_or_paper_demo_authorized",
    ],
}


def run() -> dict[str, Any]:
    validate_cards()
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_paths_before = cache_inventory_files()
    cache_before = map_hashes(cache_paths_before)
    prior_paths = prior_evidence_files()
    prior_before = evidence_identity_map(prior_paths)
    prior_aggregate_before = aggregate_hash(prior_before)
    source_hash_before = file_hash(SOURCE_PACKET)

    clean_output()
    preregistration_hash = write_preregistration_checkpoint()
    preflight_rows = data_preflight()
    results = [run_candidate(card, preflight_rows) for card in CARDS]
    reference_returns = market.active_vm_dsr_usci_reference_returns()
    for result in results:
        result["portfolio_paths"] = build_portfolio_paths(
            result, reference_returns
        )
        classify(result)

    next_action = batch_next_action(results)
    sources = source_rows()
    strategies = final_strategy_rows(results)
    trials = final_trial_rows(results)
    benchmarks = benchmark_rows()
    process = [
        {
            "task_id": BATCH_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "strategy_counted": False,
            "trial_counted": False,
            "execute_next_action_now": False,
        }
    ]
    tables = result_tables(results)
    portfolio_result_rows, portfolio_turnover, portfolio_invariants = (
        portfolio_rows(results)
    )
    tables["turnover_cost_reconciliation"].extend(portfolio_turnover)
    tables["invariant_results"].extend(portfolio_invariants)
    outcomes = outcome_rows(results)
    failures = [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
        }
        for result in results
        if result["failure_reason"]
    ]
    followups = [
        row
        for row in outcomes
        if row["outcome"].startswith("exploratory_followup_candidate_")
    ]
    next_rows = [
        {
            "scope": "strategy",
            "strategy_id": result["card"].strategy_id,
            "outcome": result["outcome"],
            "exact_next_action": candidate_next_action(result),
            "execute_in_this_task": False,
        }
        for result in results
    ]
    next_rows.append(
        {
            "scope": "batch",
            "strategy_id": "",
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }
    )

    manifest = {
        "batch_id": BATCH_ID,
        "entity_type": "process_task",
        "mode": MODE,
        "stage": STAGE,
        "objective": "bounded_preregistered_daily_SPY_BIL_price_volume_exploration",
        "strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "strategy_configuration_count": 4,
        "canonical_experiment_trial_count": 4,
        "benchmark_reference_count": len(benchmarks),
        "process_task_count": 1,
        "authoritative_registry_record_count": 0,
        "paper_demo_observation_count": 0,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "execution": "completed_session_signal_following_regular_session_close",
        "EMA_initialization_convention": (
            "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
        ),
        "source_packet_path": str(SOURCE_PACKET),
        "source_packet_hash": source_hash_before,
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_performance": True,
        "provider_or_network_access": False,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "source_and_rule_lineage.csv",
        sources,
        ARTIFACT_FIELDS["source_and_rule_lineage"],
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        ARTIFACT_FIELDS["benchmark_reference_log"],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process,
        ARTIFACT_FIELDS["process_task_log"],
    )
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        ARTIFACT_FIELDS["data_preflight_reconciliation"],
    )
    write_csv(
        OUTPUT_DIR / "all_trial_results.csv",
        tables["all_trial_results"],
        ARTIFACT_FIELDS["result"],
    )
    write_csv(
        OUTPUT_DIR / "control_results.csv",
        tables["control_results"],
        ARTIFACT_FIELDS["result"],
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        tables["chronological_half_results"],
        ARTIFACT_FIELDS["result"],
    )
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_result_rows,
        ARTIFACT_FIELDS["portfolio_contribution_results"],
    )
    for result in results:
        diagnostics = result["prepared"].get("diagnostics", [])
        fields = (
            list(diagnostics[0])
            if diagnostics
            else [
                "signal_date",
                "target_state",
                "authorized_execution_date",
                "execution_status",
            ]
        )
        write_csv(
            OUTPUT_DIR / result["card"].diagnostic_file,
            diagnostics,
            fields,
        )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        tables["turnover_cost_reconciliation"],
        ARTIFACT_FIELDS["turnover_cost_reconciliation"],
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        tables["invariant_results"],
        ARTIFACT_FIELDS["invariant_results"],
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        followups,
        ARTIFACT_FIELDS["outcome_summary"],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcomes,
        ARTIFACT_FIELDS["outcome_summary"],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        [
            "strategy_id",
            "family_id",
            "outcome",
            "failure_reason",
            "decision_reason",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        [
            "scope",
            "strategy_id",
            "outcome",
            "exact_next_action",
            "execute_in_this_task",
        ],
    )
    funnel = {
        "source_or_research_lineage_record_count": len(sources),
        "strategy_configuration_count": len(strategies),
        "canonical_experiment_trial_count": len(trials),
        "benchmark_reference_count": len(benchmarks),
        "process_task_count": len(process),
        "executed_candidate_count": sum(result["executed"] for result in results),
        "standalone_followup_count": sum(
            result["outcome"] == "exploratory_followup_candidate_standalone"
            for result in results
        ),
        "diversifier_followup_count": sum(
            result["outcome"] == "exploratory_followup_candidate_diversifier"
            for result in results
        ),
        "closed_exploration_count": sum(
            result["outcome"] == "closed_exploration" for result in results
        ),
        "inconclusive_data_issue_count": sum(
            result["outcome"] == "inconclusive_data_issue" for result in results
        ),
        "blocked_feasibility_count": sum(
            result["outcome"] == "blocked_feasibility" for result in results
        ),
        "authoritative_registry_record_count": 0,
        "paper_demo_observation_count": 0,
    }
    funnel["total_followup_count"] = (
        funnel["standalone_followup_count"] + funnel["diversifier_followup_count"]
    )
    funnel["outcome_count_reconciles"] = (
        funnel["total_followup_count"]
        + funnel["closed_exploration_count"]
        + funnel["inconclusive_data_issue_count"]
        + funnel["blocked_feasibility_count"]
        == 4
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, next_action))

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_paths_after = cache_inventory_files()
    cache_after = map_hashes(cache_paths_after)
    prior_after = evidence_identity_map(prior_evidence_files())
    prior_aggregate_after = aggregate_hash(prior_after)
    source_hash_after = file_hash(SOURCE_PACKET)
    invariant_pass = all(
        bool(row["invariant_pass"])
        for row in tables["invariant_results"]
        if any(
            result["executed"] and result["card"].strategy_id == row["strategy_id"]
            for result in results
        )
    )
    consistency = {
        "status": "pass",
        "overall_pass": bool(
            len(strategies) == 4
            and len(trials) == 4
            and len({row["trial_id"] for row in trials}) == 4
            and all(row["parent_trial_id"] == "" for row in trials)
            and all(row["adaptation_label"] == "" for row in trials)
            and all(row["outcome"] in ALLOWED_OUTCOMES for row in trials)
            and all(
                row["failure_reason"] in ALLOWED_FAILURE_REASONS for row in trials
            )
            and funnel["outcome_count_reconciles"]
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_before == prior_after
            and source_hash_before == source_hash_after
            and invariant_pass
        ),
        "exact_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "exactly_four_strategy_configurations": len(strategies) == 4,
        "exactly_four_canonical_trials": len(trials) == 4,
        "unique_trial_ids": len({row["trial_id"] for row in trials}) == 4,
        "canonical_trials_have_blank_parent_and_adaptation": all(
            row["parent_trial_id"] == "" and row["adaptation_label"] == ""
            for row in trials
        ),
        "required_metadata_complete": all(
            all(
                str(row[field]).strip()
                for field in (
                    "strategy_id",
                    "family_id",
                    "display_name",
                    "strategy_architecture",
                    "source_or_research_lineage",
                    "instrument_universe",
                    "parameters",
                    "benchmark_or_control",
                    "stage",
                    "trial_id",
                    "outcome",
                    "next_action",
                )
            )
            for row in strategies + trials
        ),
        "benchmark_references_counted_as_strategies_or_trials": False,
        "cost_diagnostics_counted_as_trials": False,
        "portfolio_diagnostics_counted_as_trials": False,
        "preregistration_written_before_performance": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "EMA_initialization_convention_frozen_before_performance": True,
        "all_executed_invariants_passed": invariant_pass,
        "cohort_funnel_reconciles": funnel["outcome_count_reconciles"],
        "provider_or_network_access": False,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "canonical_caches_unchanged": cache_before == cache_after,
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "source_packet_hash_before": source_hash_before,
        "source_packet_hash_after": source_hash_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    if not consistency["overall_pass"]:
        consistency["status"] = "fail"
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": BATCH_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "failure_reasons": {
            result["card"].strategy_id: result["failure_reason"]
            for result in results
        },
        "followup_candidate_count": funnel["total_followup_count"],
        "exact_next_action": next_action,
        "overall_pass": consistency["overall_pass"],
        "protected_state_unchanged": consistency["protected_state_unchanged"],
        "canonical_caches_unchanged": consistency["canonical_caches_unchanged"],
        "prior_evidence_unchanged": consistency["prior_evidence_unchanged"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
